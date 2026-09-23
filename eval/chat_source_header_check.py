"""
ตรวจ header บอกที่มาของคำตอบใน /chat-web และการพาที่มาจากฐานข้อมูลมาถึงชั้น API

เหตุที่ต้องมี: หน้าเว็บจะทำปุ่ม "เปิดเอกสารต้นฉบับ" ได้ก็ต่อเมื่อรู้ document_id และเลขหน้า
แต่คำตอบที่ส่งถึงหน้าเว็บเป็นข้อความล้วน (ดู docs/FRONTEND_PDF_LINK_INSPECTION.md) จึงส่งที่มา
เป็น header แทน ข้อกำหนดที่ห้ามหลุดคือ **เนื้อความคำตอบต้องเหมือนเดิมทุกตัวอักษร** และ
**ห้ามส่ง header เมื่อไม่รู้เอกสารจริง** เพราะหน้าเว็บจะสร้างลิงก์ที่เปิดไม่ได้ให้ผู้ใช้กด

ทั้งหมดเป็น offline: ไม่เรียกโมเดล ไม่ต่อฐานข้อมูลจริง ไม่แตะ production

    python -m eval.chat_source_header_check
"""
from __future__ import annotations

import base64
import json
import os
import sys
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
from app.api.routes import web_compat as route  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.services.curriculum_facts import EditionFact, FactsResult, Source  # noqa: E402

DOC_ID = "fb2279ac-3139-449f-87dc-51c8e970bcd4"
ANSWER = ("หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาคณิตศาสตร์ (พ.ศ. 2569) "
          "มีจำนวนหน่วยกิตรวมตลอดหลักสูตร 124 หน่วยกิต\nที่มา: ma69.pdf หน้า 1")


def sse(kind: str, data: dict) -> str:
    return f"event: {kind}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def meta(source=None) -> str:
    return sse("meta", {"session_id": str(uuid.uuid4()), "status": "answered", "search_query": "q",
                        "top_score": 0.0, "in_scope": True, "citations": [], "source": source})


class FakeDB:
    """
    db ปลอมที่คืนแถวเดียวจาก course_documents JOIN courses

    row=None แปลว่าหา document_id นั้นไม่เจอ ซึ่งต้องไม่ทำให้ header เดิมหาย
    """

    def __init__(self, row: dict | None):
        self._row = row

    def execute(self, *_args, **_kwargs):
        row = self._row
        return SimpleNamespace(mappings=lambda: SimpleNamespace(first=lambda: row))


class _Base(unittest.TestCase):
    def client(self, events, db=None):
        app = FastAPI()
        app.include_router(route.router)
        app.dependency_overrides[get_db] = lambda: db if db is not None else SimpleNamespace()
        app.dependency_overrides[web_rate_limiter] = lambda: None
        patches = [
            mock.patch.object(route, "shared_user", return_value=SimpleNamespace(id=uuid.uuid4())),
            mock.patch.object(route, "stream_answer", side_effect=lambda *a, **k: iter(events)),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        return TestClient(app)

    def ask(self, events, message="หลักสูตรคณิตศาสตร์ พ.ศ. 2569 เรียนกี่หน่วยกิต", db=None):
        return self.client(events, db=db).post(
            "/chat-web", json={"messages": [{"role": "user", "content": message}]}
        )


STRUCTURED_EVENTS = [
    meta({"document_id": DOC_ID, "page_start": 1}),
    sse("token", {"t": ANSWER}),
    sse("done", {}),
]
PLAIN_EVENTS = [meta(None), sse("token", {"t": "ส่วนหนึ่ง "}), sse("token", {"t": "อีกส่วน"}), sse("done", {})]


class HeaderChecks(_Base):
    def test_คำตอบจากฐานข้อมูลที่มีที่มาได้_header_ครบสองตัว(self):
        r = self.ask(STRUCTURED_EVENTS)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["X-Source-Document"], DOC_ID)
        self.assertEqual(r.headers["X-Source-Page"], "1")

    def test_document_id_ตรงกับเอกสารที่เป็นที่มาจริง(self):
        r = self.ask(STRUCTURED_EVENTS)
        self.assertEqual(r.headers["X-Source-Document"], DOC_ID)
        self.assertIn("ma69.pdf", r.text)

    def test_เลขหน้าตรงกับที่ฐานข้อมูลบันทึก(self):
        r = self.ask([meta({"document_id": DOC_ID, "page_start": 6}), sse("token", {"t": "x"}), sse("done", {})])
        self.assertEqual(r.headers["X-Source-Page"], "6")

    def test_สร้าง_url_ของเอกสารจาก_header_ได้ตรงรูปแบบ(self):
        r = self.ask(STRUCTURED_EVENTS)
        url = f"/api/documents/{r.headers['X-Source-Document']}/pdf#page={r.headers['X-Source-Page']}"
        self.assertEqual(url, f"/api/documents/{DOC_ID}/pdf#page=1")

    def test_ไม่มีที่มาต้องไม่มี_header(self):
        r = self.ask(PLAIN_EVENTS)
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("x-source-document", {k.lower() for k in r.headers})
        self.assertNotIn("x-source-page", {k.lower() for k in r.headers})

    def test_ที่มาไม่ครบห้ามส่ง_header_ปลอม(self):
        for source in ({"document_id": None, "page_start": 3}, {"document_id": "", "page_start": 3},
                       {"page_start": 3}, {}, None, "ไม่ใช่ dict"):
            with self.subTest(source=source):
                r = self.ask([meta(source), sse("token", {"t": "x"}), sse("done", {})])
                self.assertNotIn("x-source-document", {k.lower() for k in r.headers})

    def test_มีเอกสารแต่ไม่มีเลขหน้า_ส่งเฉพาะ_document(self):
        r = self.ask([meta({"document_id": DOC_ID}), sse("token", {"t": "x"}), sse("done", {})])
        self.assertEqual(r.headers["X-Source-Document"], DOC_ID)
        self.assertNotIn("x-source-page", {k.lower() for k in r.headers})

    def test_เลขหน้าที่ไม่ใช่จำนวนเต็มบวกถูกตัดทิ้ง(self):
        for page in (0, -1, "1", None, 1.5):
            with self.subTest(page=page):
                r = self.ask([meta({"document_id": DOC_ID, "page_start": page}), sse("token", {"t": "x"}),
                              sse("done", {})])
                self.assertEqual(r.headers["X-Source-Document"], DOC_ID)
                self.assertNotIn("x-source-page", {k.lower() for k in r.headers})


PROGRAMME = "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาคณิตศาสตร์ (พ.ศ. 2569)"
FILENAME = "ma69.pdf"
FOUND = FakeDB({"original_filename": FILENAME, "title": PROGRAMME})


def unb64(value: str) -> str:
    return base64.b64decode(value).decode("utf-8")


class SourceMetadataChecks(_Base):
    """
    X-Source-Title / X-Source-Programme — ชื่อเอกสารและชื่อหลักสูตรที่อ่านจากฐานข้อมูล

    ใช้ทำปุ่ม "ดูเอกสารหลักสูตร" และ "ดูรายละเอียดสาขา" ใต้คำตอบ AI
    ข้อกำหนดที่ห้ามหลุด: ทั้งสองค่ามาจาก document_id เท่านั้น ห้ามเดาจากข้อความที่ AI ตอบ
    """

    def test_ส่งชื่อเอกสารและชื่อหลักสูตรเมื่อรู้จริง(self):
        r = self.ask(STRUCTURED_EVENTS, db=FOUND)
        self.assertEqual(unb64(r.headers["X-Source-Title"]), FILENAME)
        self.assertEqual(unb64(r.headers["X-Source-Programme"]), PROGRAMME)

    def test_ภาษาไทยผ่าน_header_แล้วถอดกลับได้ครบ(self):
        # ค่า header ถูกเข้ารหัส latin-1 ตอนส่ง ถ้าไม่หุ้ม base64 จะ UnicodeEncodeError ทั้งคำตอบ
        r = self.ask(STRUCTURED_EVENTS, db=FOUND)
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("à", r.headers["X-Source-Programme"])
        self.assertEqual(unb64(r.headers["X-Source-Programme"]), PROGRAMME)

    def test_หาเอกสารไม่เจอต้องไม่ส่งสองค่านี้_แต่ของเดิมยังอยู่(self):
        r = self.ask(STRUCTURED_EVENTS, db=FakeDB(None))
        self.assertEqual(r.headers["X-Source-Document"], DOC_ID)
        self.assertEqual(r.headers["X-Source-Page"], "1")
        lower = {k.lower() for k in r.headers}
        self.assertNotIn("x-source-title", lower)
        self.assertNotIn("x-source-programme", lower)

    def test_ค่าว่างในฐานข้อมูลต้องไม่กลายเป็น_header_ว่าง(self):
        for row in ({"original_filename": "", "title": ""},
                    {"original_filename": None, "title": None},
                    {"original_filename": "  ", "title": "  "}):
            with self.subTest(row=row):
                r = self.ask(STRUCTURED_EVENTS, db=FakeDB(row))
                lower = {k.lower() for k in r.headers}
                self.assertNotIn("x-source-title", lower)
                self.assertNotIn("x-source-programme", lower)

    def test_ไม่มีที่มาก็ไม่ต้องไปอ่านฐานข้อมูล(self):
        r = self.ask(PLAIN_EVENTS, db=FOUND)
        lower = {k.lower() for k in r.headers}
        self.assertNotIn("x-source-title", lower)
        self.assertNotIn("x-source-programme", lower)

    def test_ฐานข้อมูลล้มต้องไม่ทำให้คำตอบล้ม(self):
        class Broken:
            def execute(self, *_a, **_k):
                raise RuntimeError("db down")

        r = self.ask(STRUCTURED_EVENTS, db=Broken())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, ANSWER)
        self.assertEqual(r.headers["X-Source-Document"], DOC_ID)

    def test_เนื้อความคำตอบไม่เปลี่ยนเมื่อมี_header_เพิ่ม(self):
        self.assertEqual(self.ask(STRUCTURED_EVENTS, db=FOUND).text, ANSWER)


class BodyUnchangedChecks(_Base):
    def test_เนื้อความคำตอบเหมือนเดิมทุกตัวอักษร(self):
        self.assertEqual(self.ask(STRUCTURED_EVENTS).text, ANSWER)

    def test_คำตอบที่มาหลายชิ้นต่อกันเหมือนเดิม(self):
        self.assertEqual(self.ask(PLAIN_EVENTS).text, "ส่วนหนึ่ง อีกส่วน")

    def test_ชนิดข้อมูลยังเป็น_text_plain(self):
        r = self.ask(STRUCTURED_EVENTS)
        self.assertTrue(r.headers["content-type"].startswith("text/plain"))
        self.assertEqual(r.headers["Cache-Control"], "no-cache")
        self.assertEqual(r.headers["X-Accel-Buffering"], "no")

    def test_มีหรือไม่มี_header_เนื้อความก็เท่ากัน(self):
        with_source = self.ask(STRUCTURED_EVENTS).text
        without = self.ask([meta(None), sse("token", {"t": ANSWER}), sse("done", {})]).text
        self.assertEqual(with_source, without)

    def test_event_ที่ไม่รู้จักไม่ถูกส่งออกไปให้ผู้ใช้(self):
        r = self.ask([meta(None), sse("citations", {"citations": []}), sse("token", {"t": "ok"}), sse("done", {})])
        self.assertEqual(r.text, "ok")


class ErrorFlowChecks(_Base):
    def test_ข้อผิดพลาดของโมเดลยังตอบ_200_เป็นข้อความ(self):
        from llm.connector import LLMConnectionError

        def boom(*a, **k):
            raise LLMConnectionError("ระบบตอบไม่ได้ตอนนี้")

        app = FastAPI()
        app.include_router(route.router)
        app.dependency_overrides[get_db] = lambda: SimpleNamespace()
        app.dependency_overrides[web_rate_limiter] = lambda: None
        with mock.patch.object(route, "shared_user", return_value=SimpleNamespace(id=uuid.uuid4())), \
             mock.patch.object(route, "stream_answer", side_effect=boom):
            r = TestClient(app).post("/chat-web", json={"messages": [{"role": "user", "content": "ถาม"}]})
        self.assertEqual(r.status_code, 200)
        self.assertIn("ระบบตอบไม่ได้ตอนนี้", r.text)
        self.assertNotIn("x-source-document", {k.lower() for k in r.headers})

    def test_event_error_กลางสตรีมยังต่อท้ายข้อความเหมือนเดิม(self):
        r = self.ask([meta(None), sse("token", {"t": "บางส่วน"}), sse("error", {"detail": "ขัดข้อง"})])
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, "บางส่วน\n\nขัดข้อง")


class SourcePlumbingChecks(unittest.TestCase):
    """ที่มาต้องเดินทางจากฐานข้อมูลมาถึง Prepared โดยไม่แตะคำตอบ"""

    def test_source_มาจากฐานข้อมูลผ่าน_structured_answer(self):
        import app.services.chat as chat
        from app.services.structured_shadow import ServedAnswer

        p = chat.Prepared(session_id=uuid.uuid4(), status="not_found", search_query="q", best_score=0.0,
                          citations=[], canned=None, messages=[])
        with mock.patch.object(chat, "structured_answer", return_value=ServedAnswer(ANSWER, DOC_ID, 1)):
            out = chat._with_structured(p, "ถาม")
        self.assertEqual(out.canned, ANSWER)
        self.assertEqual(out.source, {"document_id": DOC_ID, "page_start": 1})

    def test_ไม่มี_document_id_ต้องไม่ตั้ง_source(self):
        import app.services.chat as chat
        from app.services.structured_shadow import ServedAnswer

        p = chat.Prepared(session_id=uuid.uuid4(), status="not_found", search_query="q", best_score=0.0,
                          citations=[], canned=None, messages=[])
        with mock.patch.object(chat, "structured_answer", return_value=ServedAnswer(ANSWER, None, 1)):
            out = chat._with_structured(p, "ถาม")
        self.assertEqual(out.canned, ANSWER)
        self.assertIsNone(out.source)

    def test_คำตอบที่ไม่ใช่ฐานข้อมูลไม่มี_source(self):
        import app.services.chat as chat

        p = chat.Prepared(session_id=uuid.uuid4(), status="answered", search_query="q", best_score=0.5,
                          citations=[], canned="คำตอบจากเอกสาร", messages=[])
        with mock.patch.object(chat, "structured_answer", return_value=None):
            out = chat._with_structured(p, "ถาม")
        self.assertIs(out, p)
        self.assertIsNone(out.source)

    def test_ที่มาบอกได้เมื่ออ้างถึงฉบับเดียวเท่านั้น(self):
        """คำตอบที่ครอบหลายฉบับมีที่มาหลายเล่ม การเลือกเล่มเดียวจะชี้ผู้ใช้ผิดเล่ม"""
        import app.services.structured_shadow as shadow

        one = FactsResult("answered", "total_credits", [
            EditionFact(course_id="c1", course_title="t1", edition_year=2569, value_int=124,
                        source=Source("ma69.pdf", 1, 1, None, document_id=DOC_ID)),
        ], answer=ANSWER)
        self.assertEqual(shadow._source_of(one), (DOC_ID, 1))

        two = FactsResult("answered", "edition_year", [
            EditionFact(course_id="c1", course_title="t1", edition_year=2569,
                        source=Source("ma69.pdf", 1, 1, None, document_id=DOC_ID)),
            EditionFact(course_id="c2", course_title="t2", edition_year=2564,
                        source=Source("ma64.pdf", 2, 2, None, document_id="other")),
        ], answer="สองฉบับ")
        self.assertEqual(shadow._source_of(two), (None, None))

        no_source = FactsResult("answered", "careers", [
            EditionFact(course_id="c1", course_title="t1", edition_year=2569, source=None),
        ], answer="x")
        self.assertEqual(shadow._source_of(no_source), (None, None))

    def test_source_ไม่เปลี่ยนข้อความคำตอบ(self):
        """ที่มาเป็นข้อมูลเสริม ไม่ได้ถูกนำไปต่อในคำตอบ"""
        import app.services.chat as chat
        from app.services.structured_shadow import ServedAnswer

        p = chat.Prepared(session_id=uuid.uuid4(), status="not_found", search_query="q", best_score=0.0,
                          citations=[], canned=None, messages=[])
        with mock.patch.object(chat, "structured_answer", return_value=ServedAnswer(ANSWER, DOC_ID, 1)):
            with_source = chat._with_structured(p, "ถาม").canned
        with mock.patch.object(chat, "structured_answer", return_value=ServedAnswer(ANSWER, None, None)):
            without = chat._with_structured(p, "ถาม").canned
        self.assertEqual(with_source, without)
        self.assertEqual(with_source, ANSWER)


class FrozenEndpointChecks(unittest.TestCase):
    def test_pdf_endpoint_ที่_freeze_ไว้ไม่ถูกแก้(self):
        import hashlib

        src = Path(__file__).resolve().parents[1] / "backend" / "app" / "api" / "routes" / "documents.py"
        digest = hashlib.sha256(src.read_bytes()).hexdigest()
        # ลายนิ้วมือของไฟล์ตอน deploy ROUND 1 (docs/PDF_ENDPOINT_DEPLOYMENT_REPORT.md)
        self.assertEqual(digest, "4d95d4b1ea2f5e839c8db84483e73dc8cc8d8025ff18a0b950ce65e2b1ec4226")


if __name__ == "__main__":
    unittest.main()
