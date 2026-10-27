"""
ตรวจเส้นทาง /site/courses ที่มาแทนการที่หน้าเว็บเรียก Supabase ตรง (Phase 4)

เหตุที่ต้องมี: หกหน้าของเว็บสาธารณะอ่านหลักสูตรจากเส้นทางนี้ ถ้าพลาดคือหน้าหลักสูตร
หน้ารายละเอียด หน้าเปรียบเทียบ หน้าแนะนำสาขา และหน้าอาชีพหลังจบ ดับพร้อมกัน

ข้อกำหนดที่ห้ามหลุด
    - อ่านไม่ได้ต้องเป็น 503 **ห้ามคืนรายการว่างเงียบ ๆ** เพราะหน้าเว็บจะดูเหมือน
      "ยังไม่มีหลักสูตร" ทั้งที่จริงคืออ่านฐานข้อมูลไม่ได้
    - คืนเฉพาะแถวที่ is_published — การกรองย้ายจาก RLS มาอยู่ที่โค้ดแล้ว ลืมแล้วของหลุด
    - careers ที่เป็น NULL ต้องกลายเป็นรายการว่าง หน้าเว็บคาดว่าเป็นรายการเสมอ
    - รหัสที่ไม่ใช่ UUID ต้องได้ 404 ไม่ใช่ 500

ทั้งหมดเป็น offline: ไม่ต่อฐานข้อมูลจริง ไม่แตะ production

    python -m eval.site_courses_check
"""
from __future__ import annotations

import datetime as dt
import os
import sys
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres@127.0.0.1:55432/course_advisor")
os.environ.setdefault("JWT_SECRET", "local-test-only")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.api.routes import site as route  # noqa: E402
from app.db.session import get_db  # noqa: E402

CID = "4caeb377-0845-46ab-9c80-010795a00389"
PGID = "11111111-0000-0000-0000-000000000001"
NOW = dt.datetime(2026, 10, 11, 12, 0, tzinfo=dt.timezone.utc)


def row(**over):
    base = {"id": uuid.UUID(CID), "course_id": uuid.UUID(PGID), "title": "วิทยาการคอมพิวเตอร์",
            "title_en": "Computer Science", "description": "คำบรรยาย",
            "logo_url": "https://example/logo.png", "careers": ["นักพัฒนาซอฟต์แวร์"],
            "detail": {"ก": "ข"}, "created_at": NOW, "updated_at": NOW}
    base.update(over)
    return base


class FakeDB:
    """rows=None แปลว่าอ่านไม่ได้ (schema web ยังไม่มี หรือสิทธิ์ไม่ถึง)"""

    def __init__(self, rows):
        self._rows = rows
        self.queries: list[str] = []

    def execute(self, statement, params=None):
        self.queries.append(str(statement))
        if self._rows is None:
            raise RuntimeError('relation "web.site_courses" does not exist')
        rows = self._rows
        return SimpleNamespace(mappings=lambda: SimpleNamespace(
            all=lambda: rows, first=lambda: rows[0] if rows else None))


class Base(unittest.TestCase):
    def client(self, rows):
        db = FakeDB(rows)
        app = FastAPI()
        app.include_router(route.router)
        app.dependency_overrides[get_db] = lambda: db
        self.db = db
        return TestClient(app)


class ListChecks(Base):
    def test_คืนรายการหลักสูตร(self):
        r = self.client([row()]).get("/site/courses")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()["courses"]), 1)

    def test_รหัสถูกแปลงเป็นข้อความ(self):
        c = self.client([row()]).get("/site/courses").json()["courses"][0]
        self.assertEqual(c["id"], CID)
        self.assertEqual(c["course_id"], PGID)

    def test_course_id_ที่เป็น_NULL_คืน_null(self):
        c = self.client([row(course_id=None)]).get("/site/courses").json()["courses"][0]
        self.assertIsNone(c["course_id"])

    def test_careers_ที่เป็น_NULL_กลายเป็นรายการว่าง(self):
        c = self.client([row(careers=None)]).get("/site/courses").json()["courses"][0]
        self.assertEqual(c["careers"], [])

    def test_เวลาเป็นข้อความ_isoformat(self):
        c = self.client([row()]).get("/site/courses").json()["courses"][0]
        self.assertTrue(c["updated_at"].startswith("2026-10-11"))
        self.assertTrue(c["created_at"].startswith("2026-10-11"))

    def test_มี_created_at_ให้แถบหน้าแรกเรียงตามลำดับเดิม(self):
        c = self.client([row()]).get("/site/courses").json()["courses"][0]
        self.assertIn("created_at", c)

    def test_เวลาที่เป็น_NULL_คืน_null_ไม่พัง(self):
        c = self.client([row(created_at=None)]).get("/site/courses").json()["courses"][0]
        self.assertIsNone(c["created_at"])

    def test_ไม่มีหลักสูตรเลยคืนรายการว่างพร้อม_200(self):
        r = self.client([]).get("/site/courses")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"courses": []})

    def test_ใช้ชื่อฟิลด์ของปลายทางไม่ใช่ของ_supabase(self):
        c = self.client([row()]).get("/site/courses").json()["courses"][0]
        self.assertIn("logo_url", c)
        self.assertNotIn("logo", c)


class PublishedFilterChecks(Base):
    def test_กรองเฉพาะที่เผยแพร่(self):
        """การกรองย้ายจาก RLS มาอยู่ที่โค้ดแล้ว ลืมแล้วของที่ยังไม่พร้อมหลุดออกสาธารณะ"""
        self.client([row()]).get("/site/courses")
        self.assertIn("is_published", self.db.queries[0])

    def test_รายตัวก็กรองเช่นกัน(self):
        self.client([row()]).get(f"/site/courses/{CID}")
        self.assertIn("is_published", self.db.queries[0])


class DetailChecks(Base):
    def test_หาเจอคืนหลักสูตรเดียว(self):
        r = self.client([row()]).get(f"/site/courses/{CID}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["title"], "วิทยาการคอมพิวเตอร์")

    def test_หาไม่เจอได้_404(self):
        r = self.client([]).get(f"/site/courses/{CID}")
        self.assertEqual(r.status_code, 404)

    def test_รหัสที่ไม่ใช่_uuid_ได้_404_ไม่ใช่_500(self):
        r = self.client([row()]).get("/site/courses/ไม่ใช่รหัส")
        self.assertEqual(r.status_code, 404)

    def test_รหัสที่ไม่ใช่_uuid_ไม่ยิงฐานข้อมูลเลย(self):
        c = self.client([row()])
        c.get("/site/courses/abc")
        self.assertEqual(len(self.db.queries), 0)


class FailureChecks(Base):
    def test_อ่านฐานข้อมูลไม่ได้ได้_503_ไม่ใช่รายการว่าง(self):
        """ข้อสำคัญสุด — คืนว่างเงียบ ๆ คือหน้าเว็บดูเหมือนไม่มีหลักสูตร ทั้งที่อ่านไม่ได้"""
        r = self.client(None).get("/site/courses")
        self.assertEqual(r.status_code, 503)

    def test_รายตัวอ่านไม่ได้ก็_503(self):
        r = self.client(None).get(f"/site/courses/{CID}")
        self.assertEqual(r.status_code, 503)

    def test_ข้อความผิดพลาดไม่มีรายละเอียดภายใน(self):
        r = self.client(None).get("/site/courses")
        self.assertNotIn("web.site_courses", r.text)
        self.assertNotIn("relation", r.text)


class QueryChecks(Base):
    def test_อ่านจาก_web_site_courses_เท่านั้น(self):
        self.client([row()]).get("/site/courses")
        sql = self.db.queries[0]
        self.assertIn("web.site_courses", sql)
        self.assertNotIn("public.courses", sql)

    def test_ไม่มีคำสั่งเขียนในเส้นทางอ่าน(self):
        self.client([row()]).get("/site/courses")
        sql = self.db.queries[0].lower()
        # เทียบเป็นวลีของคำสั่ง ไม่ใช่คำโดด — คอลัมน์ updated_at มีคำว่า update อยู่ข้างใน
        for phrase in ("insert into", "update web", "update public", "delete from", "drop "):
            self.assertNotIn(phrase, sql)
        self.assertTrue(sql.strip().startswith("select"))

    def test_เรียกฐานข้อมูลครั้งเดียวต่อคำขอ(self):
        self.client([row()]).get("/site/courses")
        self.assertEqual(len(self.db.queries), 1)


if __name__ == "__main__":
    unittest.main()
