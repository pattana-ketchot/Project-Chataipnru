"""
ทดสอบการดาวน์โหลดของ crawler — ขอบเขต URL, redirect, เพดานขนาด, ลายเซ็น PDF

    python eval/crawl_download_check.py

ไม่ต้องมีฐานข้อมูล
-----------------
ทั้งไฟล์นี้ทดสอบ pipeline/crawl/http.py กับ pipeline/crawl/sync.py::process_link
โดยใช้ที่เก็บสถานะจำลองในหน่วยความจำ สิ่งที่ต้องพิสูจน์คือ "ดาวน์โหลดอะไรได้/ไม่ได้"
และ "มีไฟล์ค้างไหม" ซึ่งไม่เกี่ยวกับ CHECK constraint ในฐานข้อมูล
ส่วนที่ต้องพิสูจน์กับฐานข้อมูลจริงอยู่ที่ eval/crawl_state_check.py เหมือนเดิม

ใช้เว็บเซิร์ฟเวอร์จริงในเครื่อง ไม่ใช่ตัวจำลอง httpx
--------------------------------------------------
เรื่องที่ต้องพิสูจน์คือ redirect ข้ามโฮสต์ · การทยอยอ่านทีละก้อน · content-length ที่
โกหก · การตัดการเชื่อมต่อกลางทาง ซึ่งเป็นพฤติกรรมระดับโปรโตคอล ตัวจำลองที่คืน
Response สำเร็จรูปพิสูจน์แทนไม่ได้ เซิร์ฟเวอร์จริงบน 127.0.0.1 พิสูจน์ได้ทั้งหมด
และไม่ยิงเว็บคณะแม้แต่คำขอเดียว

ตอบ 404 ให้ /robots.txt เหมือนเว็บคณะจริง ซึ่งตาม RFC 9309 หมายถึงไม่มีข้อห้าม

เรื่องรายการโฮสต์ที่อนุญาต
-------------------------
ระหว่างทดสอบต้องสลับรายการเป็น 127.0.0.1 กับพอร์ตของเซิร์ฟเวอร์ทดสอบ ไม่งั้น
ตัวดึงจะปฏิเสธทุกคำขอตั้งแต่ยังไม่เริ่ม ส่วนรายการจริง (sci.pnru.ac.th) ทดสอบแยกใน
ชุด url_rejection ซึ่งไม่ต้องยิงคำขอเลย
"""
from __future__ import annotations

import hashlib
import http.server
import os
import socket
import stat
import sys
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pipeline.crawl import http as http_mod  # noqa: E402
from pipeline.crawl.discover import PdfLink  # noqa: E402
from pipeline.crawl.http import STAGED_FILE_MODE, PoliteClient, url_rejection  # noqa: E402
from pipeline.crawl.inventory import KnownDocument  # noqa: E402
from pipeline.crawl.sync import process_link  # noqa: E402

# uid/gid ที่อีกสองฝ่ายรันอยู่จริง ใช้พิสูจน์ว่าไฟล์ใน staging อ่านข้าม uid ได้จริง
#   backend/Dockerfile:29   useradd --create-home --uid 1000 appuser
#   pipeline/Dockerfile:54  groupadd --gid 1001 worker && useradd --uid 1001 --gid 1001 worker
BACKEND_UID = BACKEND_GID = 1000
WORKER_UID = WORKER_GID = 1001


def pdf_bytes(marker: str, size: int) -> bytes:
    head = f"%PDF-1.4 {marker} ".encode()
    return head + b"0" * max(0, size - len(head))


SMALL_PDF = pdf_bytes("SMALL", 8 * 1024)
BIG_PDF = pdf_bytes("BIG", 300 * 1024)
HTML_BODY = b"<html><head><title>404 Not Found</title></head><body>no</body></html>"


# ---- เว็บเซิร์ฟเวอร์ทดสอบ ------------------------------------------------
class Handler(http.server.BaseHTTPRequestHandler):
    # HTTP/1.0 ทำให้ทุกคำตอบจบด้วยการปิดการเชื่อมต่อ จึงคุมได้ว่าเส้นทางไหนมี
    # content-length เส้นทางไหนไม่มี ซึ่งจำเป็นต่อการทดสอบเพดานขนาดสองแบบ
    protocol_version = "HTTP/1.0"

    def log_message(self, *a) -> None:  # เงียบ ไม่รบกวนผลการทดสอบ
        pass

    def _send(self, code: int, ctype: str | None = None, body: bytes = b"",
              length: int | None = -1, extra: dict | None = None) -> None:
        self.send_response(code)
        if ctype:
            self.send_header("Content-Type", ctype)
        if length != -1:
            if length is not None:
                self.send_header("Content-Length", str(length))
        else:
            self.send_header("Content-Length", str(len(body)))
        self.send_header("ETag", '"test-etag"')
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _route(self, body_allowed: bool) -> None:
        path = self.path
        host = self.headers.get("Host", "")

        if path == "/robots.txt":
            # เหมือน sci.pnru.ac.th จริง — 404 = ไม่มีข้อห้าม
            self._send(404, "text/html", b"not found" if body_allowed else b"")
        elif path == "/ok.pdf":
            self._send(200, "application/pdf", SMALL_PDF if body_allowed else b"")
        elif path == "/big.pdf":
            self._send(200, "application/pdf", BIG_PDF if body_allowed else b"")
        elif path == "/nolength.pdf":
            # ไม่ประกาศ content-length — เพดานต้องถูกจับระหว่างอ่าน
            self._send(200, "application/pdf", BIG_PDF if body_allowed else b"", length=None)
        elif path == "/octet.pdf":
            # ประกาศผิดแต่เนื้อเป็น PDF จริง
            self._send(200, "application/octet-stream", SMALL_PDF if body_allowed else b"")
        elif path == "/notpdf":
            self._send(200, "text/html", HTML_BODY if body_allowed else b"")
        elif path == "/liar.pdf":
            # ประกาศเป็น PDF แต่เนื้อเป็น HTML
            self._send(200, "application/pdf", HTML_BODY if body_allowed else b"")
        elif path == "/short.pdf":
            self._send(200, "application/pdf", b"%PD" if body_allowed else b"")
        elif path == "/empty.pdf":
            self._send(200, "application/pdf", b"")
        elif path == "/truncated.pdf":
            # ประกาศ 300 KB แล้วส่งแค่ 8 KB จากนั้นปิดการเชื่อมต่อ
            self._send(200, "application/pdf", b"", length=len(BIG_PDF))
            if body_allowed:
                self.wfile.write(SMALL_PDF)
            self.close_connection = True
        elif path == "/redirect-in":
            self._send(302, None, b"", extra={"Location": f"http://{host}/ok.pdf"})
        elif path == "/redirect-out":
            # localhost ชี้มาที่เซิร์ฟเวอร์ตัวเดียวกัน แต่เป็นชื่อโฮสต์ที่ไม่อยู่ในรายการ
            # ถ้าด่านตรวจ redirect ไม่ทำงาน การดาวน์โหลดจะ "สำเร็จ" ซึ่งคือสิ่งที่ต้องจับ
            port = self.server.server_address[1]
            self._send(302, None, b"", extra={"Location": f"http://localhost:{port}/ok.pdf"})
        elif path == "/redirect-page-out":
            port = self.server.server_address[1]
            self._send(302, None, b"", extra={"Location": f"http://localhost:{port}/page.html"})
        elif path == "/page.html":
            self._send(200, "text/html", b"<html><a href='/x.pdf'>x</a></html>" if body_allowed else b"")
        elif path == "/boom":
            # ปิดการเชื่อมต่อทิ้งโดยไม่ตอบอะไรเลย
            self.close_connection = True
            try:
                self.connection.close()
            except OSError:
                pass
        else:
            self._send(404, "text/html", b"not found" if body_allowed else b"")

    def do_GET(self) -> None:
        self._route(body_allowed=True)

    def do_HEAD(self) -> None:
        self._route(body_allowed=False)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ---- ที่เก็บสถานะจำลอง ---------------------------------------------------
@dataclass
class StubRow:
    id: str = "00000000-0000-0000-0000-000000000000"
    source_url: str = ""
    status: str = "new"
    file_sha256: str | None = None
    http_etag: str | None = None
    http_last_modified: str | None = None
    content_length: int | None = None
    staging_path: str | None = None
    needs_review: bool = False
    approved_at: object = None
    error_count: int = 0


class StubStore:
    """
    เก็บสิ่งที่ process_link เขียน ไม่ต่อฐานข้อมูล — ดู docstring หัวไฟล์

    เลียนความหมายของ state.py::upsert() ตรงที่ status/needs_review ถูกเขียนทับ
    ส่วน http_etag / content_length / file_sha256 / staging_path ใช้ COALESCE
    คือค่าเดิมอยู่ต่อถ้ารอบนี้ไม่ได้ส่งมา และ error_count นับสะสมหรือรีเซ็ตเป็นศูนย์
    ถ้าไม่เลียนให้ตรง การเล่นสถานการณ์หลายรอบจะให้ผลต่างจากของจริง
    """

    def __init__(self, existing: dict[str, StubRow] | None = None):
        self.existing = dict(existing or {})
        self.writes: list[dict] = []

    def get_source(self, source_url: str) -> StubRow | None:
        return self.existing.get(source_url)

    def upsert(self, **kw) -> str:
        self.writes.append(kw)
        url = kw["source_url"]
        row = self.existing.get(url) or StubRow(source_url=url)
        keep = lambda new, old: old if new is None else new  # noqa: E731 — COALESCE
        row.status = kw["status"]
        row.needs_review = kw["needs_review"]
        row.http_etag = keep(kw["http_etag"], row.http_etag)
        row.http_last_modified = keep(kw["http_last_modified"], row.http_last_modified)
        row.content_length = keep(kw["content_length"], row.content_length)
        row.file_sha256 = keep(kw["file_sha256"], row.file_sha256)
        row.staging_path = keep(kw["staging_path"], row.staging_path)
        row.error_count = row.error_count + 1 if kw["bump_error"] else 0
        self.existing[url] = row
        return "stub-id"

    @property
    def last(self) -> dict:
        return self.writes[-1]

    def written(self, url: str) -> dict:
        """สิ่งที่เขียนครั้งล่าสุดของ URL นี้"""
        return [w for w in self.writes if w["source_url"] == url][-1]


def make_link(url: str) -> PdfLink:
    return PdfLink(url=url, filename=url.rsplit("/", 1)[-1], link_text="ดาวน์โหลด",
                   page_url="http://127.0.0.1/program_detail.php?id=1",
                   page_title="หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาการคอมพิวเตอร์ (พ.ศ. 2566)")


KNOWN = [KnownDocument(sha256="0" * 64, filename="cs66.pdf", page_count=120,
                       course_code="cs66",
                       course_title="หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาการคอมพิวเตอร์ (พ.ศ. 2566)")]


# ---- อ่านไฟล์ในนามของ uid อื่นจริง ๆ ------------------------------------
def read_as_uid(path: Path, uid: int, gid: int) -> tuple[bool, str]:
    """fork แล้วลดสิทธิ์ในลูก เพื่อพิสูจน์ว่า uid อื่นเปิดไฟล์นี้ได้จริง

    ทำไมต้อง fork + setuid ไม่ใช่ดูแค่บิตโหมด
    ----------------------------------------
    บิตโหมดคือกลไก แต่สิ่งที่ต้องพิสูจน์คือผลลัพธ์ — ว่า backend ซึ่งรันคนละ uid
    เปิดไฟล์นี้ได้จริง การอ่านในนาม uid จริงพิสูจน์บิตโหมด เจ้าของไฟล์ และการ
    traverse โฟลเดอร์เหนือขึ้นไปพร้อมกันในข้อเดียว

    ต้องเป็น root จึงจะลดสิทธิ์ได้ ผู้เรียกต้องตรวจก่อนเรียก
    คืน (อ่านได้, รายละเอียด)
    """
    r, w = os.pipe()
    pid = os.fork()
    if pid == 0:                                    # ---- โปรเซสลูก ----
        os.close(r)
        try:
            os.setgroups([])
            os.setgid(gid)
            os.setuid(uid)
            with open(path, "rb") as fh:
                head = fh.read(len(http_mod.PDF_SIGNATURE))
            os.write(w, b"ok:" + head)
        except BaseException as e:                  # noqa: BLE001 — ต้องรายงานทุกชนิด
            try:
                os.write(w, f"err:{type(e).__name__}".encode())
            except Exception:
                pass
        finally:
            os._exit(0)                             # ห้ามให้ลูกรันชุดทดสอบต่อ
    os.close(w)                                     # ---- โปรเซสพ่อ ----
    buf = b""
    while True:
        part = os.read(r, 4096)
        if not part:
            break
        buf += part
    os.close(r)
    os.waitpid(pid, 0)
    if buf.startswith(b"ok:"):
        return True, repr(buf[3:])
    return False, buf.decode("utf-8", "replace") or "ไม่ได้คำตอบจากโปรเซสลูก"


# ---- ชุดทดสอบ -----------------------------------------------------------
class Checks:
    def __init__(self) -> None:
        self.passed: list[str] = []
        self.failed: list[tuple[str, str]] = []
        self.skipped: list[tuple[str, str]] = []

    def skip(self, name: str, why: str) -> None:
        """ข้อที่เครื่องนี้พิสูจน์ไม่ได้ — ต้องเห็นว่าข้าม ไม่ใช่ถูกนับเป็นผ่าน"""
        self.skipped.append((name, why))
        print(f"  ข้าม   {name}  — {why}")

    def check(self, name: str, ok: bool, detail: str = "") -> None:
        (self.passed.append(name) if ok else self.failed.append((name, detail)))
        print(f"  {'ผ่าน  ' if ok else 'ไม่ผ่าน'} {name}" + (f"  — {detail}" if detail and not ok else ""))

    # ---- ขอบเขต URL (ไม่ยิงคำขอ ใช้รายการจริง) -------------------------
    def url_scope(self) -> None:
        print("\n[1] ขอบเขต URL — ใช้รายการจริง ไม่ยิงคำขอ")
        cases = [
            ("https ของคณะ", "https://sci.pnru.ac.th/upload/a.pdf", True),
            ("http ของคณะ", "http://sci.pnru.ac.th/upload/a.pdf", True),
            ("ตัวพิมพ์ใหญ่", "https://SCI.PNRU.AC.TH/a.pdf", True),
            ("พอร์ต 443", "https://sci.pnru.ac.th:443/a.pdf", True),
            ("โฮสต์อื่น", "https://evil.example.com/a.pdf", False),
            ("โฮสต์ที่ขึ้นต้นเหมือน", "https://sci.pnru.ac.th.evil.com/a.pdf", False),
            ("โฮสต์ที่ลงท้ายเหมือน", "https://evilsci.pnru.ac.th/a.pdf", False),
            ("ftp", "ftp://sci.pnru.ac.th/a.pdf", False),
            ("file", "file:///etc/passwd", False),
            ("ไม่มี scheme", "//sci.pnru.ac.th/a.pdf", False),
            ("พอร์ตอื่น", "https://sci.pnru.ac.th:8080/a.pdf", False),
            ("loopback", "http://127.0.0.1/a.pdf", False),
            ("metadata ของคลาวด์", "http://169.254.169.254/latest/meta-data/", False),
        ]
        for name, url, should_pass in cases:
            reason = url_rejection(url)
            ok = (reason == "") if should_pass else (reason != "")
            self.check(f"{name}: {'ยอมรับ' if should_pass else 'ปฏิเสธ'}", ok,
                       f"{url} -> {reason!r}")

    # ---- ดาวน์โหลด ----------------------------------------------------
    def downloads(self, base: str, staging: Path) -> None:
        print("\n[2] ดาวน์โหลด — เซิร์ฟเวอร์จริงในเครื่อง")

        def leftovers() -> list[str]:
            return sorted(p.name for p in staging.glob(".part_*"))

        def run(path: str, **kw):
            with PoliteClient(delay=0.0, timeout=5.0) as c:
                return c.download(f"{base}{path}", staging, **kw)

        # PDF ปกติ
        dl = run("/ok.pdf")
        self.check("PDF ปกติ: สำเร็จ", dl.ok, dl.reason)
        self.check("PDF ปกติ: sha256 ตรงกับเนื้อจริง",
                   dl.sha256 == hashlib.sha256(SMALL_PDF).hexdigest(), str(dl.sha256))
        self.check("PDF ปกติ: ขนาดตรง", dl.size == len(SMALL_PDF), f"{dl.size} != {len(SMALL_PDF)}")
        self.check("PDF ปกติ: มีไฟล์ให้ผู้เรียก",
                   dl.path is not None and dl.path.exists(), str(dl.path))
        self.check("PDF ปกติ: content-type ตรง ไม่ต้องเตือน", not dl.content_type_mismatch,
                   str(dl.content_type))
        self.check("PDF ปกติ: เก็บ etag ไว้", dl.etag == '"test-etag"', str(dl.etag))
        if dl.path:
            dl.path.unlink(missing_ok=True)

        # redirect ภายในโฮสต์ที่อนุญาต
        dl = run("/redirect-in")
        self.check("redirect ในโฮสต์เดิม: สำเร็จ", dl.ok, dl.reason)
        self.check("redirect ในโฮสต์เดิม: ได้เนื้อของปลายทาง",
                   dl.sha256 == hashlib.sha256(SMALL_PDF).hexdigest(), str(dl.sha256))
        self.check("redirect ในโฮสต์เดิม: บันทึก URL ปลายทาง",
                   (dl.final_url or "").endswith("/ok.pdf"), str(dl.final_url))
        if dl.path:
            dl.path.unlink(missing_ok=True)

        # redirect ออกนอกโฮสต์ที่อนุญาต
        dl = run("/redirect-out")
        self.check("redirect ออกนอกโฮสต์: ปฏิเสธ", not dl.ok, "ยอมรับทั้งที่ออกนอกโฮสต์")
        self.check("redirect ออกนอกโฮสต์: เหตุผลบอกว่า redirect",
                   "redirect" in dl.reason, dl.reason)
        self.check("redirect ออกนอกโฮสต์: ไม่มีไฟล์ค้าง", not leftovers(), str(leftovers()))
        self.check("redirect ออกนอกโฮสต์: ไม่คืนไฟล์", dl.path is None, str(dl.path))

        # เกินเพดาน — ประกาศมาเกิน (ไม่ต้องอ่านเนื้อ)
        dl = run("/big.pdf", max_bytes=64 * 1024)
        self.check("เกินเพดาน (ประกาศเกิน): ปฏิเสธ", not dl.ok, "ยอมรับไฟล์ที่ประกาศว่าใหญ่เกิน")
        self.check("เกินเพดาน (ประกาศเกิน): เหตุผลบอกเพดาน",
                   "เพดาน" in dl.reason, dl.reason)
        self.check("เกินเพดาน (ประกาศเกิน): ไม่มีไฟล์ค้าง", not leftovers(), str(leftovers()))

        # เกินเพดาน — ไม่ประกาศขนาด ต้องจับได้ระหว่างอ่าน
        dl = run("/nolength.pdf", max_bytes=64 * 1024)
        self.check("เกินเพดาน (ไม่ประกาศขนาด): ปฏิเสธระหว่างอ่าน", not dl.ok,
                   "ยอมรับไฟล์ที่ใหญ่เกินโดยไม่ประกาศขนาด")
        self.check("เกินเพดาน (ไม่ประกาศขนาด): อ่านไม่เกินเพดานมากนัก",
                   dl.size <= 64 * 1024 + (1 << 16), f"อ่านไป {dl.size} ไบต์")
        self.check("เกินเพดาน (ไม่ประกาศขนาด): ไม่มีไฟล์ค้าง", not leftovers(), str(leftovers()))

        # ขนาดพอดีเพดาน ต้องผ่าน
        dl = run("/big.pdf", max_bytes=len(BIG_PDF))
        self.check("ขนาดเท่าเพดานพอดี: ผ่าน", dl.ok, dl.reason)
        if dl.path:
            dl.path.unlink(missing_ok=True)

        # content-type ไม่ใช่ PDF และเนื้อก็ไม่ใช่
        dl = run("/notpdf")
        self.check("ไม่ใช่ PDF (text/html): ปฏิเสธ", not dl.ok, "ยอมรับ HTML")
        self.check("ไม่ใช่ PDF (text/html): เหตุผลบอกลายเซ็น",
                   "ไม่ใช่ PDF" in dl.reason, dl.reason)
        self.check("ไม่ใช่ PDF (text/html): ไม่มีไฟล์ค้าง", not leftovers(), str(leftovers()))

        # ประกาศเป็น PDF แต่เนื้อเป็น HTML — เนื้อไฟล์ชนะ header
        dl = run("/liar.pdf")
        self.check("ประกาศ PDF แต่เนื้อเป็น HTML: ปฏิเสธ", not dl.ok,
                   "เชื่อ header มากกว่าเนื้อไฟล์")
        self.check("ประกาศ PDF แต่เนื้อเป็น HTML: ไม่มีไฟล์ค้าง", not leftovers(), str(leftovers()))

        # content-type ผิดแต่เนื้อเป็น PDF จริง — รับไว้ แต่ต้องทำเครื่องหมาย
        dl = run("/octet.pdf")
        self.check("content-type ผิดแต่เนื้อเป็น PDF: รับไว้", dl.ok, dl.reason)
        self.check("content-type ผิดแต่เนื้อเป็น PDF: ทำเครื่องหมายไว้ให้คนตรวจ",
                   dl.content_type_mismatch, str(dl.content_type))
        if dl.path:
            dl.path.unlink(missing_ok=True)

        # ลายเซ็นไม่ครบ
        dl = run("/short.pdf")
        self.check("เนื้อสั้นกว่าลายเซ็น: ปฏิเสธ", not dl.ok, "ยอมรับไฟล์ 3 ไบต์")
        self.check("เนื้อสั้นกว่าลายเซ็น: ไม่มีไฟล์ค้าง", not leftovers(), str(leftovers()))

        dl = run("/empty.pdf")
        self.check("ไฟล์ว่าง: ปฏิเสธ", not dl.ok, "ยอมรับไฟล์ว่าง")
        self.check("ไฟล์ว่าง: ไม่มีไฟล์ค้าง", not leftovers(), str(leftovers()))

        # ดาวน์โหลดไม่ครบ
        dl = run("/truncated.pdf")
        self.check("ดาวน์โหลดไม่ครบ: ปฏิเสธ", not dl.ok, "ยอมรับไฟล์ที่โหลดไม่ครบ")
        self.check("ดาวน์โหลดไม่ครบ: ไม่มีไฟล์ค้าง", not leftovers(), str(leftovers()))
        self.check("ดาวน์โหลดไม่ครบ: ไม่คืนไฟล์", dl.path is None, str(dl.path))

        # เน็ตพัง
        dl = run("/boom")
        self.check("การเชื่อมต่อถูกตัด: ปฏิเสธ", not dl.ok, "ยอมรับทั้งที่ต่อไม่ติด")
        self.check("การเชื่อมต่อถูกตัด: ไม่มีไฟล์ค้าง", not leftovers(), str(leftovers()))

        # 404
        dl = run("/missing.pdf")
        self.check("http 404: ปฏิเสธ", not dl.ok, "ยอมรับ 404")
        self.check("http 404: เหตุผลมีรหัสสถานะ", "404" in dl.reason, dl.reason)

        # URL นอกขอบเขต — ต้องไม่ยิงคำขอเลย
        with PoliteClient(delay=0.0, timeout=5.0) as c:
            before = c.requests_made
            dl = c.download("https://evil.example.com/a.pdf", staging)
            self.check("โฮสต์นอกขอบเขต: ปฏิเสธ", not dl.ok, "ยอมรับโฮสต์นอกขอบเขต")
            self.check("โฮสต์นอกขอบเขต: ไม่ยิงคำขอแม้แต่ครั้งเดียว",
                       c.requests_made == before, f"ยิงไป {c.requests_made - before} คำขอ")
        self.check("โฮสต์นอกขอบเขต: ไม่มีไฟล์ค้าง", not leftovers(), str(leftovers()))

        # ไม่มีไฟล์อะไรค้างเลยเมื่อจบทุกเคส
        self.check("จบทุกเคส: โฟลเดอร์ staging ไม่มีไฟล์ค้าง",
                   not sorted(p.name for p in staging.iterdir() if p.is_file()),
                   str(sorted(p.name for p in staging.iterdir() if p.is_file())))

    # ---- get() / head() ตาม redirect ออกนอกโฮสต์ ----------------------
    def page_requests(self, base: str) -> None:
        print("\n[3] get() และ head() — ด่านเดียวกันต้องคุมการดึงหน้าเว็บด้วย")
        with PoliteClient(delay=0.0, timeout=5.0) as c:
            self.check("get() หน้าปกติ: ได้คำตอบ", c.get(f"{base}/page.html") is not None)
            self.check("get() redirect ออกนอกโฮสต์: คืน None",
                       c.get(f"{base}/redirect-page-out") is None, "ตาม redirect ออกนอกโฮสต์")
            self.check("get() โฮสต์นอกขอบเขต: คืน None",
                       c.get("https://evil.example.com/x.html") is None)
            self.check("head() ไฟล์ปกติ: ได้คำตอบ", c.head(f"{base}/ok.pdf") is not None)
            self.check("head() redirect ออกนอกโฮสต์: คืน None",
                       c.head(f"{base}/redirect-out") is None, "ตาม redirect ออกนอกโฮสต์")
            self.check("head() โฮสต์นอกขอบเขต: คืน None",
                       c.head("https://evil.example.com/x.pdf") is None)

    # ---- process_link บันทึกสถานะและไม่ทิ้งไฟล์ค้าง --------------------
    def sync_behaviour(self, base: str, staging: Path) -> None:
        print("\n[4] process_link — สถานะที่บันทึก และไฟล์ใน staging")

        def run(path: str, existing: dict | None = None, known: dict | None = None):
            store = StubStore(existing)
            with PoliteClient(delay=0.0, timeout=5.0) as c:
                o = process_link(c, store, make_link(f"{base}{path}"), KNOWN, known or {},
                                 staging, download=True)
            return o, store

        def files() -> list[str]:
            return sorted(p.name for p in staging.iterdir() if p.is_file())

        # ไฟล์ใหม่ปกติ
        o, store = run("/ok.pdf")
        sha = hashlib.sha256(SMALL_PDF).hexdigest()
        self.check("ไฟล์ใหม่: สถานะ downloaded", o.status == "downloaded", o.status)
        self.check("ไฟล์ใหม่: ต้องให้คนตรวจ", o.needs_review)
        self.check("ไฟล์ใหม่: เก็บไฟล์ชื่อขึ้นต้นด้วย sha",
                   files() == [f"{sha[:12]}_ok.pdf"], str(files()))
        self.check("ไฟล์ใหม่: ไม่เหลือ .part_", not list(staging.glob(".part_*")))
        self.check("ไฟล์ใหม่: staging_path ชี้ไฟล์ที่มีจริง",
                   o.staging_path is not None and Path(o.staging_path).is_file(), str(o.staging_path))
        self.check("ไฟล์ใหม่: เนื้อไฟล์ที่เก็บตรงกับที่โหลด",
                   Path(o.staging_path).read_bytes() == SMALL_PDF if o.staging_path else False)
        self.check("ไฟล์ใหม่: บันทึก sha ลงสถานะ", store.last["file_sha256"] == sha,
                   str(store.last["file_sha256"]))
        for p in staging.iterdir():
            if p.is_file():
                p.unlink()

        # เนื้อเหมือนรอบก่อน — ต้องไม่เก็บไฟล์ไว้
        o, store = run("/ok.pdf", existing={f"{base}/ok.pdf": StubRow(
            source_url=f"{base}/ok.pdf", status="downloaded", file_sha256=sha)})
        self.check("เนื้อเหมือนรอบก่อน: สถานะ unchanged", o.status == "unchanged", o.status)
        self.check("เนื้อเหมือนรอบก่อน: ไม่เก็บไฟล์ไว้", not files(), str(files()))
        self.check("เนื้อเหมือนรอบก่อน: ไม่เหลือ .part_", not list(staging.glob(".part_*")))

        # มีในคลังแล้ว — ต้องไม่เก็บไฟล์ไว้
        o, store = run("/ok.pdf", known={sha: {"id": "11111111-1111-1111-1111-111111111111",
                                               "original_filename": "cs66.pdf",
                                               "course_title": "วิทยาการคอมพิวเตอร์"}})
        self.check("มีในคลังแล้ว: สถานะ unchanged", o.status == "unchanged", o.status)
        self.check("มีในคลังแล้ว: ไม่เก็บไฟล์ไว้", not files(), str(files()))
        self.check("มีในคลังแล้ว: ผูก document_id",
                   store.last["document_id"] == "11111111-1111-1111-1111-111111111111",
                   str(store.last["document_id"]))

        # เนื้อเปลี่ยน — เก็บไฟล์ใหม่ และบันทึก sha เดิม
        o, store = run("/ok.pdf", existing={f"{base}/ok.pdf": StubRow(
            source_url=f"{base}/ok.pdf", status="downloaded", file_sha256="a" * 64)})
        self.check("เนื้อเปลี่ยน: สถานะ changed", o.status == "changed", o.status)
        self.check("เนื้อเปลี่ยน: บันทึก sha เดิมไว้",
                   store.last["previous_sha256"] == "a" * 64, str(store.last["previous_sha256"]))
        self.check("เนื้อเปลี่ยน: เก็บไฟล์ไว้ 1 ไฟล์", len(files()) == 1, str(files()))
        for p in staging.iterdir():
            if p.is_file():
                p.unlink()

        # ทุกกรณีที่ถูกปฏิเสธต้องเป็น error และไม่มีไฟล์เหลือ
        for path, label in [("/notpdf", "ไม่ใช่ PDF"), ("/liar.pdf", "ประกาศ PDF แต่เนื้อ HTML"),
                            ("/short.pdf", "สั้นกว่าลายเซ็น"), ("/truncated.pdf", "โหลดไม่ครบ"),
                            ("/boom", "การเชื่อมต่อถูกตัด"), ("/redirect-out", "redirect ออกนอกโฮสต์"),
                            ("/missing.pdf", "http 404")]:
            o, store = run(path)
            self.check(f"{label}: สถานะ error", o.status == "error", o.status)
            self.check(f"{label}: ไม่สร้างไฟล์ใน staging", not files(), str(files()))
            self.check(f"{label}: staging_path เป็น None ในสถานะที่บันทึก",
                       store.last["staging_path"] is None, str(store.last["staging_path"]))
            self.check(f"{label}: นับจำนวนครั้งที่ผิดพลาด", store.last["bump_error"] is True)
            self.check(f"{label}: บันทึกเหตุผลไว้",
                       bool(store.last["last_error"]), str(store.last["last_error"]))

        # ลิงก์นอกขอบเขต — ไม่ยิงคำขอเลยแต่ยังบันทึกสถานะ
        store = StubStore()
        with PoliteClient(delay=0.0, timeout=5.0) as c:
            o = process_link(c, store, make_link("https://evil.example.com/a.pdf"),
                             KNOWN, {}, staging, download=True)
            self.check("ลิงก์นอกขอบเขต: ไม่ยิงคำขอเลย", c.requests_made == 0,
                       f"ยิงไป {c.requests_made}")
        self.check("ลิงก์นอกขอบเขต: สถานะ error", o.status == "error", o.status)
        self.check("ลิงก์นอกขอบเขต: ต้องให้คนตรวจ", o.needs_review)
        self.check("ลิงก์นอกขอบเขต: ไม่สร้างไฟล์", not files(), str(files()))

        # content-type ผิดแต่เนื้อเป็น PDF — เก็บไว้และเขียนเหตุผลให้คนอ่าน
        o, store = run("/octet.pdf")
        self.check("content-type ผิดแต่เนื้อ PDF: เก็บไว้เป็น downloaded",
                   o.status == "downloaded", o.status)
        self.check("content-type ผิดแต่เนื้อ PDF: เหตุผลบอกเรื่อง content-type",
                   "content-type" in (store.last["review_reason"] or ""),
                   str(store.last["review_reason"]))
        for p in staging.iterdir():
            if p.is_file():
                p.unlink()

        # โหมดไม่โหลดไฟล์ยังทำงานเหมือนเดิม
        store = StubStore()
        with PoliteClient(delay=0.0, timeout=5.0) as c:
            o = process_link(c, store, make_link(f"{base}/ok.pdf"), KNOWN, {}, staging,
                             download=False)
        self.check("โหมดไม่โหลดไฟล์: ไม่สร้างไฟล์", not files(), str(files()))
        self.check("โหมดไม่โหลดไฟล์: เหตุผลบอกโหมด", "ไม่โหลด" in o.reason, o.reason)

    # ---- Phase 2 regression — เล่นสถานการณ์เดิมซ้ำโดยไม่ต้องมีฐานข้อมูล ----
    # ---- F1: สิทธิ์ของไฟล์ที่ส่งมอบให้ staging ---------------------------
    def staged_permissions(self, base: str, staging: Path) -> None:
        """พิสูจน์ว่าไฟล์ที่ crawler เก็บไว้ที่ staging ถูกอ่านได้จากอีก uid

        ข้อบกพร่อง F1 ที่ชุดนี้กันไม่ให้กลับมา
        -------------------------------------
        tempfile.mkstemp() สร้างไฟล์เป็น 0600 โดยไม่สนใจ umask และ os.replace()
        ไม่แตะโหมด ไฟล์ใน staging จึงเคยเป็น 0600 ของ uid ที่รัน crawler ทำให้
        backend (uid 1000) อ่านไม่ได้ และ GET /crawl-review/{id}/pdf ตอบ 404 ทุกครั้ง
        แม้ไฟล์จะครบถ้วนและ sha256 ถูกต้อง คนตรวจจึงเปิดดูก่อนอนุมัติไม่ได้เลย

        ทำไมชุดเดิมไม่จับได้
        -------------------
        ข้อตรวจเดิมถามแค่ "มีไฟล์ไหม เนื้อตรงไหม ไม่มี .part_ ค้างใช่ไหม" ไม่มีข้อใด
        แตะบิตโหมดเลย และ staging บน production ว่างมาตลอดจึงไม่มีใครเห็นอาการ
        """
        print("\n[5] สิทธิ์ของไฟล์ใน staging — กันข้อบกพร่อง F1 กลับมา")

        if os.name != "posix":
            self.skip("F1: ทั้งชุด",
                      f"ระบบนี้ไม่ใช่ POSIX (os.name={os.name!r}) บิตโหมดไม่มีความหมาย "
                      "ต้องรันในคอนเทนเนอร์ Linux")
            return

        sha_expected = hashlib.sha256(SMALL_PDF).hexdigest()

        # โฟลเดอร์ต้องให้ uid อื่น traverse ได้ก่อน ไม่งั้นข้อตรวจจะล้มเพราะโฟลเดอร์
        # ไม่ใช่เพราะไฟล์ — 0755 ตรงกับ staging/crawl บน production
        # แตะเฉพาะโฟลเดอร์ ไม่แตะไฟล์ PDF ที่กำลังทดสอบแม้ไฟล์เดียว
        for d in (staging.parent, staging):
            try:
                os.chmod(d, 0o755)
            except OSError:
                pass

        with PoliteClient(delay=0.0, timeout=5.0) as c:
            dl = c.download(f"{base}/ok.pdf", staging)
        self.check("F1: ดาวน์โหลดสำเร็จ", dl.ok, dl.reason)
        if not dl.ok or dl.path is None:
            return

        tmp = dl.path
        mode = stat.S_IMODE(tmp.stat().st_mode)

        # --- บิตโหมดของไฟล์ที่ download() ส่งมอบให้ผู้เรียก ---
        self.check("F1: ไฟล์ที่ส่งมอบมีโหมดตามที่ประกาศไว้",
                   mode == STAGED_FILE_MODE, f"{mode:04o} != {STAGED_FILE_MODE:04o}")
        self.check("F1: ไม่ใช่ 0600 อย่างที่ mkstemp ตั้งไว้",
                   mode != 0o600, f"{mode:04o} — ข้อบกพร่อง F1 กลับมาแล้ว")
        self.check("F1: other อ่านได้", bool(mode & 0o004), f"{mode:04o}")
        self.check("F1: group อ่านได้", bool(mode & 0o040), f"{mode:04o}")
        self.check("F1: other เขียนไม่ได้", mode & 0o002 == 0, f"{mode:04o}")
        self.check("F1: group เขียนไม่ได้", mode & 0o020 == 0, f"{mode:04o}")
        self.check("F1: ไม่มี execute bit", mode & 0o111 == 0, f"{mode:04o}")
        self.check("F1: ไม่มี setuid/setgid/sticky", mode & 0o7000 == 0, f"{mode:04o}")

        # --- การตั้งสิทธิ์ต้องไม่แตะเนื้อไฟล์ ---
        on_disk = tmp.read_bytes()
        self.check("F1: sha256 ของไฟล์บนดิสก์ตรงกับที่ crawler รายงาน",
                   hashlib.sha256(on_disk).hexdigest() == dl.sha256, str(dl.sha256))
        self.check("F1: sha256 ตรงกับเนื้อที่เซิร์ฟเวอร์ส่งมา",
                   dl.sha256 == sha_expected, f"{dl.sha256} != {sha_expected}")
        self.check("F1: ขนาดไฟล์ไม่เปลี่ยน", len(on_disk) == len(SMALL_PDF),
                   f"{len(on_disk)} != {len(SMALL_PDF)}")
        self.check("F1: ลายเซ็น %PDF- ยังอยู่",
                   on_disk.startswith(http_mod.PDF_SIGNATURE), repr(on_disk[:8]))

        # --- os.replace() ต้องรักษาโหมดไว้ — เหตุผลที่ต้องตั้งก่อน replace ---
        final = staging / f"{dl.sha256[:12]}_perm_check.pdf"
        os.replace(tmp, final)
        mode_after = stat.S_IMODE(final.stat().st_mode)
        self.check("F1: โหมดคงเดิมหลัง os.replace()",
                   mode_after == mode, f"{mode_after:04o} != {mode:04o}")
        self.check("F1: sha256 คงเดิมหลัง os.replace()",
                   hashlib.sha256(final.read_bytes()).hexdigest() == dl.sha256)

        # --- พิสูจน์ด้วยการอ่านในนาม uid จริง ---
        if os.geteuid() == 0:
            for label, uid, gid in (("backend", BACKEND_UID, BACKEND_GID),
                                    ("worker", WORKER_UID, WORKER_GID)):
                ok, detail = read_as_uid(final, uid, gid)
                self.check(f"F1: uid {uid} ({label}) เปิดไฟล์ได้จริง", ok, detail)
                self.check(f"F1: uid {uid} ({label}) อ่านได้ลายเซ็น %PDF-",
                           ok and repr(http_mod.PDF_SIGNATURE) in detail, detail)
        else:
            self.skip(f"F1: อ่านในนาม uid {BACKEND_UID}/{WORKER_UID}",
                      f"ต้องรันเป็น root จึงจะลดสิทธิ์ได้ (euid={os.geteuid()}) "
                      "— พิสูจน์จริงใน isolated E2E ด้วย backend ตัวจริง")
        final.unlink()

        # --- เส้นทางจริงทั้งเส้น: process_link ต้องได้ไฟล์โหมดเดียวกัน ---
        store = StubStore(None)
        with PoliteClient(delay=0.0, timeout=5.0) as c:
            o = process_link(c, store, make_link(f"{base}/ok.pdf"), KNOWN, {},
                             staging, download=True)
        self.check("F1: process_link เก็บไฟล์ไว้จริง", o.staging_path is not None, str(o.status))
        if o.staging_path:
            staged = Path(o.staging_path)
            m = stat.S_IMODE(staged.stat().st_mode)
            self.check("F1: ไฟล์จาก process_link มีโหมดตามที่ประกาศไว้",
                       m == STAGED_FILE_MODE, f"{m:04o} != {STAGED_FILE_MODE:04o}")
            self.check("F1: ไฟล์จาก process_link ไม่ world-writable", m & 0o002 == 0, f"{m:04o}")
            if os.geteuid() == 0:
                ok, detail = read_as_uid(staged, BACKEND_UID, BACKEND_GID)
                self.check("F1: backend uid เปิดไฟล์จาก process_link ได้", ok, detail)
            staged.unlink()

        # --- ทางที่ล้มต้องไม่ทิ้งอะไรไว้ เหมือนเดิม ---
        with PoliteClient(delay=0.0, timeout=5.0) as c:
            bad = c.download(f"{base}/html.pdf", staging)
        leftovers = [q.name for q in staging.glob(".part_*")]
        self.check("F1: ดาวน์โหลดที่ถูกปฏิเสธไม่ทิ้งไฟล์ค้าง",
                   not bad.ok and not leftovers and bad.path is None,
                   f"ok={bad.ok} leftovers={leftovers}")
        rest = [q.name for q in staging.iterdir() if q.is_file()]
        self.check("F1: จบชุดนี้ staging ว่าง", not rest, str(rest))

    def phase2_regression(self, staging: Path) -> None:
        """
        เล่นสถานการณ์สองรอบของ eval/crawl_state_check.py ซ้ำด้วย StubClient ตัวเดียวกัน

        ทำที่นี่เพราะ crawl_state_check.py ต้องมี PostgreSQL ที่ลง migration 003 แล้ว
        ซึ่งเครื่องพัฒนาไม่มี ผลที่ได้ตรงนี้พิสูจน์ว่า "ตรรกะลำดับสถานะไม่ถอยหลัง"
        ส่วนที่พิสูจน์แทนไม่ได้คือ CHECK constraint กับ UNIQUE ในฐานข้อมูลจริง
        ซึ่งงานรอบนี้ไม่ได้แตะ schema เลย
        """
        print("\n[6] Phase 2 regression — ลำดับสถานะเดิมสองรอบ (ไม่ใช้ฐานข้อมูล)")
        sys.path.insert(0, str(_ROOT / "eval"))
        import crawl_state_check as csc  # noqa: E402

        U_SAME = "https://sci.pnru.ac.th/uploads/programs/same.pdf"
        U_NEW = "https://sci.pnru.ac.th/uploads/programs/brandnew.pdf"
        U_CHG = "https://sci.pnru.ac.th/uploads/programs/willchange.pdf"
        U_ERR = "https://sci.pnru.ac.th/uploads/programs/broken.pdf"

        body_same = csc.pdf_body("EXISTING")
        body_v1, body_v2 = csc.pdf_body("VERSION-ONE"), csc.pdf_body("VERSION-TWO")
        body_new = csc.pdf_body("BRAND-NEW")
        sha_same = hashlib.sha256(body_same).hexdigest()

        known = [csc.KnownDocument(sha_same, "ma69.pdf", 120, "ma69",
                                   "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาคณิตศาสตร์ (พ.ศ. 2569)"),
                 csc.KnownDocument("b" * 64, "cs61.pdf", 211, "cs61",
                                   "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาการคอมพิวเตอร์ (พ.ศ. 2561)"),
                 csc.KnownDocument("c" * 64, "cs66.pdf", 55, "cs66",
                                   "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาการคอมพิวเตอร์ (พ.ศ. 2566)")]
        by_sha = {sha_same: {"id": "22222222-2222-2222-2222-222222222222",
                             "original_filename": "ma69.pdf", "course_title": "คณิตศาสตร์"}}
        links = {U_SAME: csc.link(U_SAME, 2, "คณิตศาสตร์"),
                 U_NEW: csc.link(U_NEW, 9, "เทคโนโลยีสารสนเทศ"),
                 U_CHG: csc.link(U_CHG, 8, "วิทยาการคอมพิวเตอร์"),
                 U_ERR: csc.link(U_ERR, 7, "วิทยาศาสตร์เครื่องสำอาง")}

        store = StubStore()
        round1 = {U_SAME: csc.make_resp(body_same, '"same-1"'),
                  U_NEW: csc.make_resp(body_new, '"new-1"'),
                  U_CHG: csc.make_resp(body_v1, '"chg-1"'),
                  U_ERR: csc.FakeResponse(500, {})}
        client = csc.StubClient(round1)
        for lk in links.values():
            process_link(client, store, lk, known, by_sha, staging, download=True)

        w = store.written
        self.check("รอบ 1 · ข้อ 1  sha ตรงกับคลัง -> unchanged",
                   w(U_SAME)["status"] == "unchanged", w(U_SAME)["status"])
        self.check("รอบ 1 · ข้อ 1b ผูก document_id ให้ด้วย",
                   w(U_SAME)["document_id"] is not None)
        self.check("รอบ 1 · ข้อ 1c ไม่เก็บไฟล์ลง staging",
                   w(U_SAME)["staging_path"] is None)
        self.check("รอบ 1 · ข้อ 2  ไฟล์ใหม่ -> downloaded",
                   w(U_NEW)["status"] == "downloaded", w(U_NEW)["status"])
        self.check("รอบ 1 · ข้อ 2b เก็บไฟล์ลง staging จริง",
                   bool(w(U_NEW)["staging_path"]) and Path(w(U_NEW)["staging_path"]).is_file())
        self.check("รอบ 1 · ข้อ 2c ตั้งธงรอคนตรวจ", w(U_NEW)["needs_review"] is True)
        self.check("รอบ 1 · ข้อ 2d ยังไม่ผูกเอกสารในคลัง", w(U_NEW)["document_id"] is None)
        self.check("รอบ 1 · ข้อ 4  http 500 -> error", w(U_ERR)["status"] == "error",
                   w(U_ERR)["status"])
        self.check("รอบ 1 · ข้อ 4b นับจำนวนครั้งที่ผิดพลาด",
                   store.existing[U_ERR].error_count == 1, str(store.existing[U_ERR].error_count))
        self.check("รอบ 1 · ข้อ 5  ชื่อกำกวม -> ambiguous",
                   w(U_CHG)["match_confidence"] == "ambiguous", str(w(U_CHG)["match_confidence"]))
        self.check("รอบ 1 · ข้อ 5b เก็บตัวเลือกไว้ทั้งสอง ไม่เลือกเอง",
                   len(w(U_CHG)["match_candidates"]) == 2, str(w(U_CHG)["match_candidates"]))
        self.check("รอบ 1 · ข้อ 5d ไม่มีในคลัง -> unknown ไม่เดา",
                   w(U_NEW)["match_confidence"] == "unknown" and w(U_NEW)["course_code"] is None,
                   f"{w(U_NEW)['match_confidence']} / {w(U_NEW)['course_code']}")

        # รอบที่ 2 — willchange.pdf เนื้อเปลี่ยน · broken.pdf กลับมาปกติ
        round2 = dict(round1)
        round2[U_CHG] = csc.make_resp(body_v2, '"chg-2"')
        round2[U_ERR] = csc.make_resp(csc.pdf_body("RECOVERED"), '"err-ok"')
        client2 = csc.StubClient(round2)
        before = client2.requests_made
        for lk in links.values():
            process_link(client2, store, lk, known, by_sha, staging, download=True)

        self.check("รอบ 2 · ข้อ 3  เนื้อเปลี่ยน -> changed",
                   w(U_CHG)["status"] == "changed", w(U_CHG)["status"])
        self.check("รอบ 2 · ข้อ 3b เก็บ sha เดิมไว้เทียบได้",
                   w(U_CHG)["previous_sha256"] == hashlib.sha256(body_v1).hexdigest(),
                   str(w(U_CHG)["previous_sha256"]))
        self.check("รอบ 2 · ข้อ 3c บันทึก sha ใหม่",
                   w(U_CHG)["file_sha256"] == hashlib.sha256(body_v2).hexdigest())
        self.check("รอบ 2 · ข้อ 3d เก็บไฟล์ใหม่ลง staging",
                   bool(w(U_CHG)["staging_path"]) and Path(w(U_CHG)["staging_path"]).is_file())
        self.check("รอบ 2 · ข้อ 1d ETag เท่าเดิม ยังเป็น unchanged",
                   w(U_SAME)["status"] == "unchanged", w(U_SAME)["status"])
        self.check("รอบ 2 · ข้อ 4d ดึงได้แล้ว ตัวนับข้อผิดพลาดรีเซ็ต",
                   store.existing[U_ERR].error_count == 0, str(store.existing[U_ERR].error_count))
        self.check("รอบ 2 · ETag เท่าเดิมแล้วไม่โหลดไฟล์ซ้ำ",
                   client2.requests_made - before < len(links) * 2,
                   f"ยิงไป {client2.requests_made - before} คำขอ")
        self.check("รอบ 2 · ไม่มี .part_ ค้างหลังสองรอบ",
                   not list(staging.glob(".part_*")), str(list(staging.glob(".part_*"))))

        for p in staging.iterdir():
            if p.is_file():
                p.unlink()

    def report(self) -> bool:
        print(f"\n---- สรุป ----\n  ผ่าน {len(self.passed)} · ไม่ผ่าน {len(self.failed)} · ข้าม {len(self.skipped)}")
        for name, detail in self.failed:
            print(f"  ไม่ผ่าน: {name} — {detail}")
        for name, why in self.skipped:
            print(f"  ข้าม: {name} — {why}")
        return not self.failed


def main() -> None:
    port = free_port()
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"

    checks = Checks()
    checks.url_scope()   # ใช้รายการจริงก่อนสลับ

    real_hosts, real_ports = http_mod.ALLOWED_HOSTS, http_mod.ALLOWED_PORTS
    http_mod.ALLOWED_HOSTS = frozenset({"127.0.0.1"})
    http_mod.ALLOWED_PORTS = frozenset({None, 80, 443, port})
    try:
        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp) / "crawl"
            staging.mkdir(parents=True)
            checks.downloads(base, staging)
            checks.page_requests(base)
            checks.sync_behaviour(base, staging)
            checks.staged_permissions(base, staging)
            # ชุดนี้ใช้ URL ของคณะจริงกับ StubClient จึงต้องคืนรายการจริงก่อน
            http_mod.ALLOWED_HOSTS, http_mod.ALLOWED_PORTS = real_hosts, real_ports
            checks.phase2_regression(staging)
    finally:
        http_mod.ALLOWED_HOSTS, http_mod.ALLOWED_PORTS = real_hosts, real_ports
        server.shutdown()
        server.server_close()

    sys.exit(0 if checks.report() else 1)


if __name__ == "__main__":
    main()
