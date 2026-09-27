"""
ทดสอบการบันทึกสถานะของ crawler (Phase 2)

    python eval/crawl_state_check.py --database-url postgresql://...

ใช้ HTTP จำลอง ไม่ยิงเว็บจริง
-----------------------------
สถานการณ์อย่าง "ไฟล์เดิมแต่เนื้อหาเปลี่ยน" กับ "เซิร์ฟเวอร์ตอบ 500" สร้างขึ้นเองบน
เว็บจริงไม่ได้ และการยิงเว็บคณะซ้ำ ๆ เพื่อทดสอบก็ไม่สุภาพ ตัวจำลองจึงคุมได้ทุกกรณี
และผลการทดสอบเดิมทุกครั้งที่รัน

ทดสอบกับฐานข้อมูลจริง ไม่ใช่ของปลอม
-----------------------------------
ต่อกับ PostgreSQL จริงที่ลง migration 003 แล้ว เพราะสิ่งที่ต้องพิสูจน์คือ CHECK
constraint, ตัวกันซ้ำ และ trigger ทำงานถูกหรือไม่ ซึ่งของปลอมพิสูจน์แทนไม่ได้

⚠️ ต้องชี้ไปที่ฐานข้อมูลทดสอบเท่านั้น สคริปต์นี้เขียนและลบข้อมูลในตาราง
   mko.crawl_sources — มีด่านกันไว้ไม่ให้เผลอรันใส่ course_advisor
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import psycopg  # noqa: E402

from pipeline.crawl.discover import PdfLink  # noqa: E402
from pipeline.crawl.http import MAX_PDF_BYTES, PDF_SIGNATURE, Download, url_rejection  # noqa: E402
from pipeline.crawl.inventory import KnownDocument  # noqa: E402
from pipeline.crawl.state import CrawlStore  # noqa: E402
from pipeline.crawl.sync import process_link  # noqa: E402


# ---- HTTP จำลอง ---------------------------------------------------------
@dataclass
class FakeResponse:
    status_code: int
    headers: dict
    content: bytes = b""


class StubClient:
    """
    เลียนแบบ PoliteClient เท่าที่ process_link ใช้ — head() · get() · download()

    download() ที่นี่ทำแค่พอให้สถานะในฐานข้อมูลถูกต้อง ไม่ใช่ตัวแทนของด่านตรวจจริง
    ด่านตรวจจริง (ขอบเขต URL · redirect · เพดานขนาดแบบทยอยอ่าน · ลายเซ็น %PDF-)
    ทดสอบกับเว็บเซิร์ฟเวอร์จริงใน eval/crawl_download_check.py
    """

    def __init__(self, table: dict[str, FakeResponse]):
        self.table = table
        self.requests_made = 0

    def head(self, url: str):
        self.requests_made += 1
        r = self.table.get(url)
        if r is None:
            return None
        return FakeResponse(r.status_code, r.headers)

    def get(self, url: str):
        self.requests_made += 1
        return self.table.get(url)

    def download(self, url: str, dest_dir: Path, max_bytes: int = MAX_PDF_BYTES) -> Download:
        reason = url_rejection(url)
        if reason:
            return Download(ok=False, reason=reason)
        self.requests_made += 1
        r = self.table.get(url)
        if r is None or r.status_code != 200:
            code = r.status_code if r is not None else "-"
            return Download(ok=False, reason=f"GET http {code}",
                            status_code=r.status_code if r is not None else None)
        body = r.content
        if len(body) > max_bytes:
            return Download(ok=False, reason=f"ไฟล์ใหญ่เกินเพดาน ({len(body)} ไบต์)")
        if not body.startswith(PDF_SIGNATURE):
            return Download(ok=False, reason="ไม่ใช่ PDF")
        dest_dir.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=".part_", suffix=".pdf", dir=dest_dir)
        with os.fdopen(fd, "wb") as handle:
            handle.write(body)
        ctype = (r.headers.get("content-type") or "").split(";")[0].strip().lower() or None
        return Download(ok=True, status_code=200, size=len(body),
                        sha256=hashlib.sha256(body).hexdigest(),
                        etag=r.headers.get("etag"),
                        last_modified=r.headers.get("last-modified"),
                        content_type=ctype, final_url=url, path=Path(name))


def pdf_body(marker: str, size: int = 300 * 1024) -> bytes:
    """เนื้อไฟล์ปลอมขนาดสมจริง marker ต่างกัน = sha ต่างกัน"""
    head = f"%PDF-1.4 {marker} ".encode()
    return head + b"0" * (size - len(head))


def make_resp(body: bytes, etag: str) -> FakeResponse:
    return FakeResponse(200, {"etag": etag, "content-length": str(len(body)),
                              "content-type": "application/pdf",
                              "last-modified": "Mon, 01 Jun 2026 00:00:00 GMT"}, body)


def link(url: str, page_id: int, title: str) -> PdfLink:
    return PdfLink(url=url, filename=url.rsplit("/", 1)[-1], link_text="ดาวน์โหลดหลักสูตร",
                   page_url=f"https://sci.pnru.ac.th/program_detail.php?id={page_id}",
                   page_title=title)


# ---- ชุดทดสอบ -----------------------------------------------------------
class Checks:
    def __init__(self, database_url: str, staging: Path):
        self.url = database_url
        self.staging = staging
        self.passed: list[str] = []
        self.failed: list[tuple[str, str]] = []

    def check(self, name: str, ok: bool, detail: str = "") -> None:
        (self.passed.append(name) if ok else self.failed.append((name, detail)))
        print(f"  {'ผ่าน' if ok else 'ไม่ผ่าน'}  {name}" + (f"  — {detail}" if detail and not ok else ""))

    def row(self, store: CrawlStore, url: str) -> dict:
        with store.conn.cursor() as cur:
            cur.execute("SELECT * FROM mko.crawl_sources WHERE source_url = %s", (url,))
            return cur.fetchone()

    def run(self) -> bool:
        # เตรียมข้อมูลตั้งต้น
        known_sha = hashlib.sha256(pdf_body("EXISTING")).hexdigest()
        with psycopg.connect(self.url, autocommit=True) as c, c.cursor() as cur:
            cur.execute("DELETE FROM mko.crawl_sources")
            cur.execute("DELETE FROM course_documents")
            cur.execute("DELETE FROM courses")
            cur.execute("""INSERT INTO courses (code, title) VALUES
                ('cs61','หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาการคอมพิวเตอร์ (พ.ศ. 2561)'),
                ('cs66','หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาการคอมพิวเตอร์ (พ.ศ. 2566)'),
                ('ma69','หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาคณิตศาสตร์ (พ.ศ. 2569)')""")
            cur.execute("""INSERT INTO course_documents
                    (course_id, original_filename, file_sha256, storage_path, page_count)
                VALUES ((SELECT id FROM courses WHERE code='ma69'),
                        'ma69.pdf', %s, '/srv/documents/ma69.pdf', 120)""", (known_sha,))
            # เอกสารเก่าที่ crawler จะไม่เจอบนเว็บ — ใช้ทดสอบข้อ 6
            cur.execute("""INSERT INTO course_documents
                    (course_id, original_filename, file_sha256, storage_path, page_count)
                VALUES ((SELECT id FROM courses WHERE code='cs61'),
                        'cs61.pdf', %s, '/srv/documents/cs61.pdf', 211)""",
                        (hashlib.sha256(b"OLD-ONLY-IN-KB").hexdigest(),))
            # ฉบับที่สองของวิทยาการคอมพิวเตอร์ — ต้องมีสองฉบับถึงจะเกิดความกำกวมจริง
            # ตรงกับของจริงที่มี มคอ.2 ทั้งฉบับ 2561 และ 2566
            cur.execute("""INSERT INTO course_documents
                    (course_id, original_filename, file_sha256, storage_path, page_count)
                VALUES ((SELECT id FROM courses WHERE code='cs66'),
                        'cs66.pdf', %s, '/srv/documents/cs66.pdf', 55)""",
                        (hashlib.sha256(b"CS66-IN-KB").hexdigest(),))

        known_docs = [
            KnownDocument(known_sha, "ma69.pdf", 120, "ma69",
                          "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาคณิตศาสตร์ (พ.ศ. 2569)"),
            KnownDocument(hashlib.sha256(b"OLD-ONLY-IN-KB").hexdigest(), "cs61.pdf", 211, "cs61",
                          "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาการคอมพิวเตอร์ (พ.ศ. 2561)"),
            KnownDocument(hashlib.sha256(b"CS66-IN-KB").hexdigest(), "cs66.pdf", 55, "cs66",
                          "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาการคอมพิวเตอร์ (พ.ศ. 2566)"),
        ]

        U_SAME = "https://sci.pnru.ac.th/uploads/programs/same.pdf"
        U_NEW = "https://sci.pnru.ac.th/uploads/programs/brandnew.pdf"
        U_CHG = "https://sci.pnru.ac.th/uploads/programs/willchange.pdf"
        U_ERR = "https://sci.pnru.ac.th/uploads/programs/broken.pdf"
        # ลิงก์ .pdf บนหน้าของคณะที่ชี้ออกไปโฮสต์อื่น — เกิดขึ้นได้จริงและเคยดาวน์โหลดได้
        U_OUT = "https://drive.example.com/uploads/programs/elsewhere.pdf"

        body_same = pdf_body("EXISTING")
        body_v1 = pdf_body("VERSION-ONE")
        body_v2 = pdf_body("VERSION-TWO")
        body_new = pdf_body("BRAND-NEW")

        round1 = {
            U_SAME: make_resp(body_same, '"same-1"'),
            U_NEW: make_resp(body_new, '"new-1"'),
            U_CHG: make_resp(body_v1, '"chg-1"'),
            U_ERR: FakeResponse(500, {}),
        }
        links = {
            U_SAME: link(U_SAME, 2, "คณิตศาสตร์"),
            U_NEW: link(U_NEW, 9, "เทคโนโลยีสารสนเทศ"),          # ไม่มีในคลัง -> ระบุไม่ได้
            U_CHG: link(U_CHG, 8, "วิทยาการคอมพิวเตอร์"),         # กำกวม 2 ฉบับ
            U_ERR: link(U_ERR, 7, "วิทยาศาสตร์เครื่องสำอาง"),
        }

        print("\n--- รอบที่ 1 ---")
        with CrawlStore(self.url) as store:
            by_sha = store.known_sha256()
            client = StubClient(round1)
            for u, lk in links.items():
                try:
                    process_link(client, store, lk, known_docs, by_sha, self.staging, download=True)
                    store.conn.commit()
                except Exception as e:                     # ข้อ 4 — ต้องไม่พังทั้งรอบ
                    store.conn.rollback()
                    print(f"    ! {u} เกิดข้อผิดพลาด {e}")

            # 1. PDF เดิม -> unchanged
            r = self.row(store, U_SAME)
            self.check("1. PDF เดิม (sha ตรงกับคลัง) ได้สถานะ unchanged",
                       r["status"] == "unchanged", f"ได้ {r['status']}")
            self.check("1b. ผูก document_id กับเอกสารในคลังให้ด้วย",
                       r["document_id"] is not None)
            self.check("1c. ไม่เก็บไฟล์ลง staging",
                       r["staging_path"] is None)

            # 2. PDF ใหม่ -> staging + รออนุมัติ
            r = self.row(store, U_NEW)
            self.check("2. PDF ใหม่ ได้สถานะ downloaded",
                       r["status"] == "downloaded", f"ได้ {r['status']}")
            self.check("2b. เก็บไฟล์ลง staging จริง",
                       bool(r["staging_path"]) and Path(r["staging_path"]).is_file())
            self.check("2c. ตั้งธงรอคนตรวจ", r["needs_review"] is True)
            self.check("2d. ยังไม่ผูกกับเอกสารในคลัง (ยังไม่ได้นำเข้า)",
                       r["document_id"] is None)
            self.check("2e. ยังไม่มีข้อมูลการอนุมัติ",
                       r["approved_at"] is None and r["approved_by"] is None)

            # 4. HTTP error
            r = self.row(store, U_ERR)
            self.check("4. HTTP 500 ได้สถานะ error", r["status"] == "error", f"ได้ {r['status']}")
            self.check("4b. นับจำนวนครั้งที่ผิดพลาด", r["error_count"] == 1, f"ได้ {r['error_count']}")
            self.check("4c. ลิงก์อื่นในรอบเดียวกันยังทำงานต่อได้",
                       self.row(store, U_NEW)["status"] == "downloaded")

            # 4e. ลิงก์ .pdf ที่ชี้ออกนอกเว็บคณะ — discover.crawl() เก็บลิงก์พวกนี้มาด้วย
            # เพราะกรองโฮสต์เฉพาะหน้าที่จะเดินต่อ ตัวดึงต้องปฏิเสธโดยไม่ยิงคำขอเลย
            # (ด่านตรวจเต็มชุดอยู่ใน eval/crawl_download_check.py)
            before = client.requests_made
            process_link(client, store, link(U_OUT, 3, "คณิตศาสตร์"),
                         known_docs, by_sha, self.staging, download=True)
            store.conn.commit()
            r = self.row(store, U_OUT)
            self.check("4e. ลิงก์นอกเว็บคณะได้สถานะ error", r["status"] == "error",
                       f"ได้ {r['status']}")
            self.check("4f. ไม่เก็บไฟล์ของลิงก์นอกเว็บคณะ", r["staging_path"] is None)
            self.check("4g. ไม่ยิงคำขอไปหาโฮสต์นอกขอบเขตเลย",
                       client.requests_made == before, f"ยิงไป {client.requests_made - before}")
            self.check("4h. บันทึกเหตุผลว่าโฮสต์ไม่อนุญาต",
                       "โฮสต์" in (r["last_error"] or ""), str(r["last_error"]))

            # 5. หลักสูตรกำกวม
            r = self.row(store, U_CHG)
            self.check("5. ชื่อหลักสูตรกำกวม ถูกทำเครื่องหมาย ambiguous",
                       r["match_confidence"] == "ambiguous", f"ได้ {r['match_confidence']}")
            self.check("5b. เก็บตัวเลือกทั้งหมดไว้ ไม่เลือกเอง",
                       len(r["match_candidates"]) == 2, f"ได้ {len(r['match_candidates'])} ตัวเลือก")
            self.check("5c. ตั้งธงรอคนตรวจ", r["needs_review"] is True)
            r2 = self.row(store, U_NEW)
            self.check("5d. หลักสูตรที่ไม่มีในคลัง ไม่ถูกเดาให้ผิด",
                       r2["match_confidence"] == "unknown" and r2["course_code"] is None,
                       f"ได้ {r2['match_confidence']} / {r2['course_code']}")

        # ---- รอบที่ 2 — เนื้อหาเปลี่ยน --------------------------------
        print("\n--- รอบที่ 2 (เนื้อหาของ willchange.pdf เปลี่ยน) ---")
        round2 = dict(round1)
        round2[U_CHG] = make_resp(body_v2, '"chg-2"')
        round2[U_ERR] = make_resp(pdf_body("RECOVERED"), '"err-ok"')   # กลับมาปกติ

        with CrawlStore(self.url) as store:
            by_sha = store.known_sha256()
            client = StubClient(round2)
            for u, lk in links.items():
                process_link(client, store, lk, known_docs, by_sha, self.staging, download=True)
                store.conn.commit()

            # 3. URL เดิม เนื้อหาเปลี่ยน
            r = self.row(store, U_CHG)
            self.check("3. URL เดิมแต่เนื้อหาเปลี่ยน ได้สถานะ changed",
                       r["status"] == "changed", f"ได้ {r['status']}")
            self.check("3b. เก็บ sha ของเดิมไว้เทียบได้",
                       r["previous_sha256"] == hashlib.sha256(body_v1).hexdigest())
            self.check("3c. sha ใหม่ถูกบันทึก",
                       r["file_sha256"] == hashlib.sha256(body_v2).hexdigest())
            self.check("3d. เก็บไฟล์ใหม่ลง staging",
                       bool(r["staging_path"]) and Path(r["staging_path"]).is_file())

            # 1 (รอบสอง) — ETag เท่าเดิมต้องข้ามการโหลด
            r = self.row(store, U_SAME)
            self.check("1d. รอบสอง ETag เท่าเดิม ยังเป็น unchanged",
                       r["status"] == "unchanged", f"ได้ {r['status']}")

            # 4 (รอบสอง) — หายผิดพลาดแล้วต้องรีเซ็ตตัวนับ
            r = self.row(store, U_ERR)
            self.check("4d. เมื่อกลับมาดึงได้ ตัวนับข้อผิดพลาดถูกรีเซ็ต",
                       r["error_count"] == 0, f"ได้ {r['error_count']}")

            # 6. เอกสารเก่าที่ crawler ไม่เจอ ต้องไม่ถูกลบ
            with store.conn.cursor() as cur:
                cur.execute("SELECT count(*) AS n FROM course_documents")
                n_docs = cur.fetchone()["n"]
                cur.execute("SELECT count(*) AS n FROM course_documents WHERE original_filename='cs61.pdf'")
                n_old = cur.fetchone()["n"]
            self.check("6. เอกสารในคลังยังอยู่ครบหลัง crawl สองรอบ", n_docs == 3, f"เหลือ {n_docs}")
            self.check("6b. เอกสารที่ไม่พบบนเว็บไม่ถูกลบ", n_old == 1)

            # ตรวจว่า view คิวงานทำงาน
            pending = store.pending()
            self.check("7. วิว v_crawl_pending แสดงเฉพาะงานที่ต้องตัดสินใจ",
                       len(pending) >= 3 and all(p["needs_review"] or
                       p["status"] in ("new", "changed", "downloaded", "error") for p in pending),
                       f"ได้ {len(pending)} แถว")

        # ---- ข้อบังคับของฐานข้อมูล -----------------------------------
        print("\n--- ข้อบังคับของฐานข้อมูล ---")
        with psycopg.connect(self.url) as c:
            for name, sql in [
                ("CHECK กันสถานะที่ไม่รู้จัก",
                 "INSERT INTO mko.crawl_sources (source_url, status) VALUES ('x://bad-status','ไม่รู้จัก')"),
                ("CHECK กัน sha256 ที่ผิดรูปแบบ",
                 "INSERT INTO mko.crawl_sources (source_url, file_sha256) VALUES ('x://bad-sha','ไม่ใช่แฮช')"),
                ("CHECK บังคับว่าอนุมัติแล้วต้องมีชื่อผู้อนุมัติ",
                 "INSERT INTO mko.crawl_sources (source_url, approved_at) VALUES ('x://half-approve', now())"),
                ("UNIQUE กัน source_url ซ้ำ",
                 "INSERT INTO mko.crawl_sources (source_url) VALUES ('" + U_SAME + "')"),
            ]:
                try:
                    with c.cursor() as cur:
                        cur.execute(sql)
                    c.rollback()
                    self.check(name, False, "ฐานข้อมูลยอมรับข้อมูลที่ควรถูกปฏิเสธ")
                except psycopg.errors.Error:
                    c.rollback()
                    self.check(name, True)

        print()
        print(f"สรุป: ผ่าน {len(self.passed)} · ไม่ผ่าน {len(self.failed)}")
        for n, d in self.failed:
            print(f"   ไม่ผ่าน: {n} — {d}")
        return not self.failed


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", required=True)
    ap.add_argument("--staging", default=None)
    args = ap.parse_args()

    if "course_advisor" in args.database_url:
        raise SystemExit("ปฏิเสธ: สคริปต์นี้ลบข้อมูลในตารางทดสอบ ห้ามชี้ไปที่ course_advisor")

    staging = Path(args.staging) if args.staging else Path(tempfile.mkdtemp(prefix="crawl_staging_"))
    print(f"ฐานข้อมูลทดสอบ: {args.database_url.split('@')[-1]}")
    print(f"staging: {staging}")
    ok = Checks(args.database_url, staging).run()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
