"""
ตรวจเส้นทาง /career-lists ที่ให้หน้า "อาชีพหลังจบ" ของหน้าเว็บใช้

เหตุที่ต้องมี: หน้านั้นอ่านคอลัมน์ careers ของฐานข้อมูลหน้าเว็บ ซึ่งว่างทุกแถว จึงขึ้นว่า
"ยังไม่มีข้อมูลหลักสูตร" ทั้งที่เอกสาร มคอ.2 ระบุอาชีพไว้และผ่านการตรวจเผยแพร่แล้วใน schema mko

ข้อกำหนดที่ห้ามหลุด
    - รวมรายการของหลักสูตรเดียวกันเป็นก้อนเดียว เรียงตาม seq ของต้นฉบับ
    - ช่วงหน้าของที่มาต้องครอบทุกรายการในก้อนนั้น (หน้าแรกน้อยสุด หน้าท้ายมากสุด)
    - **ห้ามส่ง document_id เมื่อไม่รู้เอกสารจริง** เพราะหน้าเว็บเอาไปทำลิงก์ /documents/{id}/pdf
      แล้วผู้ใช้จะกดลิงก์ที่เปิดไม่ได้ (เหตุผลเดียวกับ _source_headers)
    - อ่านฐานข้อมูลไม่ได้ ต้องคืนรายการว่าง ไม่ใช่ 500 — หน้าเว็บต้องยังเปิดได้
    - ไม่เรียกโมเดลภาษา: ผลต้องเหมือนกันทุกครั้งที่เรียก

ทั้งหมดเป็น offline: ไม่เรียกโมเดล ไม่ต่อฐานข้อมูลจริง ไม่แตะ production

    python -m eval.career_lists_check
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres@127.0.0.1:55432/course_advisor")
os.environ.setdefault("JWT_SECRET", "local-test-only")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.api.deps import web_rate_limiter  # noqa: E402
from app.api.routes import web_compat as route  # noqa: E402
from app.db.session import get_db  # noqa: E402

CS_DOC = "7e06cd12-87ee-49ab-9687-c5dc51114474"
CS_TITLE = "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาการคอมพิวเตอร์ (พ.ศ. 2566)"
IT_TITLE = "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาเทคโนโลยีสารสนเทศ (พ.ศ. 2566)"


def item(course_title, seq, text, *, file="cs66.pdf", page_start=3, page_end=3, document_id=CS_DOC):
    return {"course_title": course_title, "seq": seq, "item": text, "source_filename": file,
            "page_start": page_start, "page_end": page_end, "document_id": document_id}


class FakeDB:
    """
    db ปลอมที่คืนแถวจาก mko.v_live_list_items

    rows=None แปลว่าอ่านไม่ได้ (เช่นยังไม่ได้ลง migration ของ schema mko)
    """

    def __init__(self, rows):
        self._rows = rows
        self.queries: list[str] = []
        self.params: list[dict] = []

    def execute(self, statement, params=None):
        self.queries.append(str(statement))
        self.params.append(params or {})
        if self._rows is None:
            raise RuntimeError("relation \"mko.v_live_list_items\" does not exist")
        rows = self._rows
        return SimpleNamespace(mappings=lambda: SimpleNamespace(all=lambda: rows))


class _Base(unittest.TestCase):
    def get(self, rows):
        db = FakeDB(rows)
        app = FastAPI()
        app.include_router(route.router)
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[web_rate_limiter] = lambda: None
        self.db = db
        return TestClient(app).get("/career-lists")


ONE_PROGRAMME = [
    item(CS_TITLE, 1, "นักพัฒนาซอฟต์แวร์"),
    item(CS_TITLE, 2, "นักวิชาการคอมพิวเตอร์"),
    item(CS_TITLE, 3, "นักวิเคราะห์และออกแบบระบบ"),
]

TWO_PROGRAMMES = ONE_PROGRAMME + [
    item(IT_TITLE, 1, "นักเทคโนโลยีสารสนเทศ", file="it66.pdf", page_start=6, page_end=6, document_id=None),
    item(IT_TITLE, 2, "นักพัฒนาเว็บไซต์", file="it66.pdf", page_start=6, page_end=7, document_id=None),
]


class ShapeChecks(_Base):
    def test_คืนหลักสูตรที่มีรายการอาชีพครบตามจำนวน(self):
        r = self.get(TWO_PROGRAMMES)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()["programmes"]), 2)

    def test_รวมรายการของหลักสูตรเดียวกันเป็นก้อนเดียว(self):
        r = self.get(ONE_PROGRAMME)
        progs = r.json()["programmes"]
        self.assertEqual(len(progs), 1)
        self.assertEqual(len(progs[0]["careers"]), 3)

    def test_เรียงรายการตาม_seq_ของต้นฉบับ(self):
        r = self.get(ONE_PROGRAMME)
        self.assertEqual(r.json()["programmes"][0]["careers"],
                         ["นักพัฒนาซอฟต์แวร์", "นักวิชาการคอมพิวเตอร์", "นักวิเคราะห์และออกแบบระบบ"])

    def test_ชื่อหลักสูตรเป็นชื่อเต็มของต้นฉบับ(self):
        r = self.get(ONE_PROGRAMME)
        self.assertEqual(r.json()["programmes"][0]["course_title"], CS_TITLE)

    def test_แยกสองหลักสูตรไม่ปนรายการกัน(self):
        r = self.get(TWO_PROGRAMMES)
        by_title = {p["course_title"]: p for p in r.json()["programmes"]}
        self.assertEqual(len(by_title[CS_TITLE]["careers"]), 3)
        self.assertEqual(len(by_title[IT_TITLE]["careers"]), 2)
        self.assertNotIn("นักพัฒนาเว็บไซต์", by_title[CS_TITLE]["careers"])


class SourceChecks(_Base):
    def test_ที่มามีไฟล์ต้นฉบับ(self):
        r = self.get(ONE_PROGRAMME)
        self.assertEqual(r.json()["programmes"][0]["source"]["file"], "cs66.pdf")

    def test_ช่วงหน้าครอบทุกรายการในก้อน(self):
        rows = [
            item(CS_TITLE, 1, "ก", page_start=3, page_end=3),
            item(CS_TITLE, 2, "ข", page_start=4, page_end=5),
            item(CS_TITLE, 3, "ค", page_start=2, page_end=2),
        ]
        source = self.get(rows).json()["programmes"][0]["source"]
        self.assertEqual(source["page_start"], 2)
        self.assertEqual(source["page_end"], 5)

    def test_ส่ง_document_id_เมื่อรู้เอกสารจริง(self):
        r = self.get(ONE_PROGRAMME)
        self.assertEqual(r.json()["programmes"][0]["source"]["document_id"], CS_DOC)

    def test_ไม่ส่ง_document_id_เมื่อไม่รู้เอกสาร(self):
        """ข้อสำคัญสุด — ส่งค่าว่างไปจะกลายเป็นลิงก์ที่เปิดไม่ได้ให้ผู้ใช้กด"""
        r = self.get(TWO_PROGRAMMES)
        it = next(p for p in r.json()["programmes"] if p["course_title"] == IT_TITLE)
        self.assertNotIn("document_id", it["source"])
        self.assertEqual(it["source"]["file"], "it66.pdf")

    def test_ไม่มี_document_id_แต่ยังบอกไฟล์และหน้าได้(self):
        r = self.get(TWO_PROGRAMMES)
        it = next(p for p in r.json()["programmes"] if p["course_title"] == IT_TITLE)
        self.assertEqual(it["source"]["page_start"], 6)
        self.assertEqual(it["source"]["page_end"], 7)


class EmptyAndFailureChecks(_Base):
    def test_ยังไม่มีข้อมูลที่เผยแพร่_คืนรายการว่าง(self):
        r = self.get([])
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"programmes": []})

    def test_อ่านฐานข้อมูลไม่ได้_ยังตอบ_200_พร้อมรายการว่าง(self):
        """หน้าเว็บต้องยังเปิดได้แม้ schema mko ยังไม่มี"""
        r = self.get(None)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"programmes": []})


class QueryChecks(_Base):
    def test_อ่านจาก_view_ที่เผยแพร่แล้วเท่านั้น(self):
        """
        v_live_list_items = published_list_items JOIN v_live_publication (db/migrations/002)
        จึงเห็นเฉพาะการเผยแพร่ครั้งล่าสุด

        ส่วนค่าที่ยังเป็น candidate อยู่ใน mko.list_items ซึ่ง role advisor_api
        **ไม่ได้รับสิทธิ์ SELECT เลย** — ห้ามเขียน query ไปแตะ
        """
        self.get(ONE_PROGRAMME)
        sql = self.db.queries[0]
        self.assertIn("mko.v_live_list_items", sql)
        without_view = sql.replace("mko.v_live_list_items", "")
        for candidate_table in ("mko.list_items", "mko.field_values", "mko.evidence"):
            self.assertNotIn(candidate_table, without_view)

    def test_กรองเฉพาะรายการชนิดอาชีพ(self):
        self.get(ONE_PROGRAMME)
        self.assertEqual(self.db.params[0]["item_type"], "career")

    def test_ชนิดรายการอ้างจากที่เดียวกับชั้นคำตอบ(self):
        from app.services.curriculum_facts import LIST_FIELDS
        self.assertEqual(route._CAREER_ITEM_TYPE, LIST_FIELDS["careers"])

    def test_เรียกครั้งเดียวต่อหนึ่งคำขอ(self):
        """หน้าเว็บขอทั้งหน้าในครั้งเดียว ไม่ยิงต่อหลักสูตร"""
        self.get(TWO_PROGRAMMES)
        self.assertEqual(len(self.db.queries), 1)

    def test_ไม่เรียกโมเดลภาษา(self):
        """ต่างจาก /compare-courses — ผลต้องเหมือนกันทุกครั้ง"""
        first = self.get(TWO_PROGRAMMES).json()
        second = self.get(TWO_PROGRAMMES).json()
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
