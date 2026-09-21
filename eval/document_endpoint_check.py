"""
ตรวจเส้นทางเปิดเอกสารต้นฉบับ /documents/{document_id}/pdf

เหตุที่ต้องมี: เส้นทางนี้ส่งไฟล์จากดิสก์ให้ผู้ใช้ทั่วไป ความผิดพลาดของมันคือการเปิดไฟล์
ที่ไม่ควรเปิด หรือเปิดไฟล์ผิดเล่มในนามของเอกสารที่ผู้ใช้ขอ ทั้งสองอย่างตรวจด้วยตาไม่ได้
ชุดนี้จึงตรึงกติกาไว้: ผู้ใช้ส่งได้เพียง UUID · ไฟล์ต้องอยู่ใต้โฟลเดอร์ที่อนุญาต ·
ลายนิ้วมือต้องตรงกับที่ฐานข้อมูลบันทึกไว้ · ไม่ตั้งค่า DOCUMENTS_DIR = ปิดฟีเจอร์

และตรึงข้อตกลงของ ROUND 2 ไว้ด้วย (docs/PDF_ENDPOINT_PRE_IMPLEMENT_REPORT.md):
เปลี่ยนที่เก็บไฟล์จากดิสก์เป็นฐานข้อมูลได้โดยไม่ต้องแก้ route และหน้าเว็บ

ไม่ต่อฐานข้อมูลจริงและไม่อ่านเอกสารจริง ใช้ไฟล์ชั่วคราวที่สร้างในเทสต์

    python -m eval.document_endpoint_check
"""
from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres@127.0.0.1:55432/course_advisor")
os.environ.setdefault("JWT_SECRET", "local-test-only")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.api.deps import web_rate_limiter  # noqa: E402
from app.api.routes import documents as route  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.services.document_store import FilesystemDocumentStore, StoredDocument, sha256_of  # noqa: E402

PDF_BYTES = "%PDF-1.4\n% เอกสารทดสอบ ไม่ใช่ไฟล์จริง\n%%EOF\n".encode("utf-8")
OTHER_BYTES = "%PDF-1.4\n% อีกเล่มหนึ่ง\n%%EOF\n".encode("utf-8")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class FakeDb:
    """แทนฐานข้อมูล: คืนแถว course_documents ตาม id ที่กำหนดไว้"""

    def __init__(self, rows: dict[uuid.UUID, dict]):
        self.rows = rows
        self.queries: list[str] = []

    def execute(self, statement, params=None):
        self.queries.append(str(statement))
        row = self.rows.get((params or {}).get("id"))
        return SimpleNamespace(mappings=lambda: SimpleNamespace(first=lambda: row))


class _Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        (self.root / "curriculum").mkdir()
        (self.root / "curriculum-brief").mkdir()
        self.full = self.root / "curriculum" / "ma64.pdf"
        self.brief = self.root / "curriculum-brief" / "ma69.pdf"
        self.full.write_bytes(PDF_BYTES)
        self.brief.write_bytes(OTHER_BYTES)
        # ไฟล์ข้อความในที่เก็บเดียวกัน ต้องไม่ถูกเปิดผ่านเส้นทางนี้
        (self.root / "web").mkdir()
        (self.root / "web" / "ph_web.txt").write_bytes(b"plain text")

        self.doc_full = uuid.uuid4()
        self.doc_brief = uuid.uuid4()
        self.doc_txt = uuid.uuid4()
        self.doc_missing = uuid.uuid4()
        self.db = FakeDb({
            self.doc_full: {"original_filename": "ma64.pdf", "file_sha256": sha(PDF_BYTES)},
            self.doc_brief: {"original_filename": "ma69.pdf", "file_sha256": sha(OTHER_BYTES)},
            self.doc_txt: {"original_filename": "ph_web.txt", "file_sha256": sha(b"plain text")},
            self.doc_missing: {"original_filename": "gone.pdf", "file_sha256": sha(b"not on disk")},
        })

    def client(self, store=None, root=None):
        app = FastAPI()
        app.include_router(route.router)
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[web_rate_limiter] = lambda: None
        the_store = store if store is not None else FilesystemDocumentStore(root if root is not None else self.root)
        patcher = mock.patch.object(route, "get_document_store", return_value=the_store)
        patcher.start()
        self.addCleanup(patcher.stop)
        return TestClient(app)


class ServingChecks(_Base):
    def test_เอกสารที่มีจริงเปิดได้และไบต์ตรงกับไฟล์ต้นฉบับ(self):
        r = self.client().get(f"/documents/{self.doc_full}/pdf")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content, PDF_BYTES)
        self.assertEqual(sha(r.content), sha256_of(self.full))

    def test_หัวข้อมูลตอบถูกต้องสำหรับตัวอ่าน_pdf_ของเบราว์เซอร์(self):
        r = self.client().get(f"/documents/{self.doc_full}/pdf")
        self.assertEqual(r.headers["content-type"], "application/pdf")
        disposition = r.headers["content-disposition"]
        self.assertTrue(disposition.startswith("inline"), disposition)
        self.assertIn("ma64.pdf", disposition)

    def test_เอกสารในโฟลเดอร์ฉบับย่อก็เปิดได้(self):
        """เอกสารบางเล่มถูกสกัดจากฉบับย่อ ถ้าปิดไว้ ผู้ใช้จะเปิดเอกสารของเล่มนั้นไม่ได้เลย"""
        r = self.client().get(f"/documents/{self.doc_brief}/pdf")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content, OTHER_BYTES)

    def test_รองรับ_http_range(self):
        """ตัวอ่าน PDF ขอเฉพาะช่วงไบต์ได้ จึงเปิดหน้าที่อ้างถึง (#page=N) ได้โดยไม่ต้องโหลดทั้งเล่ม"""
        c = self.client()
        head = c.get(f"/documents/{self.doc_full}/pdf")
        self.assertEqual(head.headers.get("accept-ranges"), "bytes")
        r = c.get(f"/documents/{self.doc_full}/pdf", headers={"Range": "bytes=0-7"})
        self.assertEqual(r.status_code, 206)
        self.assertEqual(r.content, PDF_BYTES[:8])
        self.assertIn("bytes 0-7/", r.headers.get("content-range", ""))


class NotFoundChecks(_Base):
    def test_รหัสเอกสารที่ไม่มีในฐานข้อมูล(self):
        r = self.client().get(f"/documents/{uuid.uuid4()}/pdf")
        self.assertEqual(r.status_code, 404)

    def test_มีแถวในฐานข้อมูลแต่ไม่มีไฟล์ในที่เก็บ(self):
        r = self.client().get(f"/documents/{self.doc_missing}/pdf")
        self.assertEqual(r.status_code, 404)

    def test_ไฟล์ข้อความไม่ถูกเปิดผ่านเส้นทางนี้(self):
        r = self.client().get(f"/documents/{self.doc_txt}/pdf")
        self.assertEqual(r.status_code, 404)

    def test_ไม่ตั้งค่า_documents_dir_เท่ากับปิดฟีเจอร์(self):
        r = self.client(store=FilesystemDocumentStore("")).get(f"/documents/{self.doc_full}/pdf")
        self.assertEqual(r.status_code, 404)

    def test_โฟลเดอร์ที่ตั้งไว้ไม่มีอยู่จริงก็ยังตอบไม่พบ(self):
        r = self.client(root=self.root / "ไม่มีโฟลเดอร์นี้").get(f"/documents/{self.doc_full}/pdf")
        self.assertEqual(r.status_code, 404)

    def test_ลายนิ้วมือไม่ตรงต้องไม่ส่งไฟล์(self):
        """ไฟล์ถูกสลับหลังสร้างดัชนี — ไฟล์นั้นไม่ใช่เอกสารที่ใช้สกัดข้อมูลแล้ว"""
        store = FilesystemDocumentStore(self.root)
        self.assertIsNotNone(store.open(self.doc_full, "ma64.pdf", sha(PDF_BYTES)))
        self.full.write_bytes("%PDF-1.4\n% ไฟล์ถูกแก้\n%%EOF\n".encode("utf-8"))
        r = self.client(store=store).get(f"/documents/{self.doc_full}/pdf")
        self.assertEqual(r.status_code, 404)


class SecurityChecks(_Base):
    def test_ค่าที่ไม่ใช่_uuid_ถูกปฏิเสธก่อนถึงชั้นไฟล์(self):
        """
        422 = FastAPI ปฏิเสธเพราะชนิดไม่ใช่ UUID · 404 = ไม่ตรงกับเส้นทางใดเลย
        ทั้งสองแบบยอมรับได้ ที่ต้องเป็นจริงเสมอคือไม่มีไฟล์ถูกส่งออก และไม่มีการค้นฐานข้อมูล
        """
        c = self.client()
        for bad in ("../../etc/passwd", "..%2f..%2fetc%2fpasswd", "ma64.pdf",
                    "/srv/documents/curriculum/ma64.pdf", "abc", "1234", "%00",
                    "00000000-0000-0000-0000-00000000000z"):
            with self.subTest(value=bad):
                r = c.get(f"/documents/{bad}/pdf")
                self.assertIn(r.status_code, (404, 422), bad)
                self.assertNotEqual(r.headers.get("content-type"), "application/pdf")
                self.assertNotIn(b"%PDF", r.content)
                self.assertEqual(self.db.queries, [], "ต้องไม่ถึงชั้นฐานข้อมูลเลย")

    def test_ข้อความตอบกลับไม่บอก_path_ของเซิร์ฟเวอร์(self):
        for doc in (self.doc_missing, uuid.uuid4()):
            body = self.client().get(f"/documents/{doc}/pdf").text
            for leak in (str(self.root), "curriculum", "/srv/", "documents/"):
                self.assertNotIn(leak, body)

    def test_ไฟล์นอกโฟลเดอร์ที่อนุญาตไม่ถูกส่งออก(self):
        """จำลองดัชนีที่ชี้ออกนอกโฟลเดอร์ (เช่นตั้งค่าผิดหรือมี symlink)"""
        outside = Path(self.tmp.name).parent / f"outside_{uuid.uuid4().hex}.pdf"
        outside.write_bytes(PDF_BYTES)
        self.addCleanup(outside.unlink)
        store = FilesystemDocumentStore(self.root)
        store._index = {sha(PDF_BYTES): outside}
        self.assertIsNone(store.open(self.doc_full, "ma64.pdf", sha(PDF_BYTES)))

    def test_ดัชนีเก็บเฉพาะไฟล์_pdf(self):
        store = FilesystemDocumentStore(self.root)
        self.assertEqual(sorted(p.name for p in store._files().values()), ["ma64.pdf", "ma69.pdf"])


class Round2CompatibilityChecks(_Base):
    def test_เปลี่ยนที่เก็บไฟล์ได้โดยไม่ต้องแก้_route(self):
        """
        ROUND 2 จะเก็บสำเนาไฟล์ในฐานข้อมูล ตรึงไว้ว่าเปลี่ยนคลาสที่เก็บแล้ว
        เส้นทาง พารามิเตอร์ และหัวข้อมูลที่ผู้ใช้ได้รับต้องเหมือนเดิมทุกประการ
        """
        payload = self.root / "curriculum" / "from_other_store.pdf"
        payload.write_bytes(PDF_BYTES)

        class MemoryStore:
            """แทน DatabaseDocumentStore ในอนาคต — สัญญาเดียวกับ DocumentStore"""

            def __init__(self, path):
                self.path = path
                self.calls = []

            def open(self, document_id, filename, sha256):
                self.calls.append((document_id, filename, sha256))
                return StoredDocument(path=self.path, filename=filename)

        store = MemoryStore(payload)
        r = self.client(store=store).get(f"/documents/{self.doc_full}/pdf")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content, PDF_BYTES)
        self.assertEqual(r.headers["content-type"], "application/pdf")
        self.assertTrue(r.headers["content-disposition"].startswith("inline"))
        self.assertEqual(store.calls, [(self.doc_full, "ma64.pdf", sha(PDF_BYTES))])

    def test_route_ไม่รู้จักดิสก์เลย(self):
        """route ต้องไม่อ้างถึง path, โฟลเดอร์ หรือการอ่านไฟล์โดยตรง"""
        import inspect
        src = inspect.getsource(route)
        # `get_document_store().open(...)` คือสัญญาของชั้นที่เก็บ ไม่ใช่การเปิดไฟล์เอง
        for forbidden in ("Path(", "os.", "DOCUMENTS_DIR", "rglob", "read_bytes", "settings", "FilesystemDocumentStore"):
            self.assertNotIn(forbidden, src.split('"""', 2)[-1], forbidden)


if __name__ == "__main__":
    unittest.main()
