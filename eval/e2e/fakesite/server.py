"""เว็บจำลองของคณะวิทยาศาสตร์ สำหรับการทดสอบ E2E ที่แยกอิสระเท่านั้น

ทำไมต้องมี
----------
crawler ตัวจริง (pipeline/crawl/http.py) บังคับ ALLOWED_HOSTS = {"sci.pnru.ac.th"}
เราจึงไม่แก้ allowlist แต่ให้ชื่อนั้นชี้มาที่นี่ด้วย network alias ในเครือข่ายทดสอบ
ผลคือได้ทดสอบ crawler ของจริงทั้งชุดรวมถึงด่านกรองโฮสต์ โดยไม่แตะ source แม้บรรทัดเดียว
และไม่มีคำขอใดออกไปถึงเว็บของคณะจริง

เส้นทางที่เสิร์ฟ (เลียนโครงสร้างที่ FOLLOW ของ sync.py เดินตาม)
    GET /robots.txt                -> 404  (RFC 9309: ไม่มีไฟล์ = อนุญาต)
    GET /programs.php              -> HTML ที่มีลิงก์ไป program_detail.php?id=1
    GET /program_detail.php?id=1   -> HTML ที่มีลิงก์ไปไฟล์ PDF ทดสอบ
    GET /TEST_CS_CURRICULUM_E2E.pdf-> ไฟล์ PDF ทดสอบ (application/pdf)

รองรับ HEAD ด้วย เพราะ process_link() เรียก HEAD ก่อนเสมอเพื่ออ่าน ETag/Content-Length
"""
from __future__ import annotations

import hashlib
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

SITE_DIR = os.environ.get("E2E_SITE_DIR", "/srv/site")
PDF_NAME = "TEST_CS_CURRICULUM_E2E.pdf"
PORT = int(os.environ.get("E2E_SITE_PORT", "80"))

PROGRAMS_HTML = """<!DOCTYPE html>
<html lang="th"><head><meta charset="utf-8">
<title>หลักสูตร (ข้อมูลทดสอบ E2E ไม่ใช่ข้อมูลจริง)</title></head>
<body>
<h1>TEST DATA - NOT A REAL PNRU SITE</h1>
<p>หน้านี้มีไว้สำหรับการทดสอบ pipeline แบบแยกอิสระเท่านั้น</p>
<ul>
  <li><a href="/program_detail.php?id=1">E2E Pipeline Testing (TEST101)</a></li>
</ul>
</body></html>
"""

DETAIL_HTML = """<!DOCTYPE html>
<html lang="th"><head><meta charset="utf-8">
<title>E2E Pipeline Testing (TEST101) - TEST DATA</title></head>
<body>
<h1>TEST DATA - NOT A REAL PNRU CURRICULUM</h1>
<p>หลักสูตรจำลองสำหรับทดสอบ pipeline · รหัส TEST101</p>
<p><a href="/{pdf}">ดาวน์โหลดเอกสารทดสอบ (PDF)</a></p>
</body></html>
""".format(pdf=PDF_NAME)


def _pdf_path() -> str:
    return os.path.join(SITE_DIR, PDF_NAME)


class Handler(BaseHTTPRequestHandler):
    # HTTP/1.0 เพื่อให้ปิดการเชื่อมต่อทุกครั้ง ไม่ต้องจัดการ keep-alive
    protocol_version = "HTTP/1.0"
    server_version = "E2EFakeSite/1.0"

    def log_message(self, fmt, *args):  # noqa: A003
        print("[fakesite] " + (fmt % args), flush=True)

    # ---- ตัวช่วยส่งคำตอบ ------------------------------------------------
    def _send(self, status: int, body: bytes, ctype: str, extra: dict | None = None,
              head_only: bool = False) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def _route(self, head_only: bool) -> None:
        path = urlparse(self.path).path

        if path == "/robots.txt":
            # ไม่มีไฟล์ robots = อนุญาตทั้งหมด (pipeline/crawl/http.py ถือแบบนี้)
            self._send(404, b"not found", "text/plain; charset=utf-8", head_only=head_only)
            return

        if path in ("/", "/programs.php", "/index.php"):
            self._send(200, PROGRAMS_HTML.encode("utf-8"),
                       "text/html; charset=utf-8", head_only=head_only)
            return

        if path == "/program_detail.php":
            self._send(200, DETAIL_HTML.encode("utf-8"),
                       "text/html; charset=utf-8", head_only=head_only)
            return

        if path == "/" + PDF_NAME:
            full = _pdf_path()
            if not os.path.isfile(full):
                self._send(404, b"pdf not generated yet", "text/plain; charset=utf-8",
                           head_only=head_only)
                return
            with open(full, "rb") as fh:
                data = fh.read()
            etag = '"' + hashlib.sha256(data).hexdigest()[:32] + '"'
            self._send(200, data, "application/pdf",
                       extra={"ETag": etag, "Last-Modified": "Mon, 29 Sep 2026 00:00:00 GMT"},
                       head_only=head_only)
            return

        self._send(404, b"not found", "text/plain; charset=utf-8", head_only=head_only)

    def do_GET(self):   # noqa: N802
        self._route(head_only=False)

    def do_HEAD(self):  # noqa: N802
        self._route(head_only=True)


def main() -> None:
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"[fakesite] listening on :{PORT} · site dir = {SITE_DIR}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
