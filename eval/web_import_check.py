"""
ตรวจตัวแปลงข้อมูลของขั้นนำข้อมูลเข้า schema web (Phase 4)

เหตุที่ต้องมี: ขั้นนี้เขียนข้อมูลจริงลงฐานข้อมูลจริง และมีจุดที่พลาดแล้วเงียบอยู่สามจุด
    1. ชื่อคอลัมน์ต่างกันสามคู่ — logo->logo_url, date->published_on, image->image_url
       แปลงพลาดคือรูปหายทั้งเว็บโดยไม่มี error
    2. course_id จับคู่ผิดคือหน้าเว็บแสดงอาชีพและเอกสารของสาขาอื่น
    3. created_by/updated_by ต้นทางชี้ไปคนละระบบผู้ใช้ ยัดค่าดิบลงไปคือ FK พังหรือชี้ผิดคน

ทั้งหมดเป็น offline: ไม่ต่อฐานข้อมูล ไม่อ่าน Supabase ไม่แตะ production

    python -m eval.web_import_check
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.web.import_from_supabase import (  # noqa: E402
    LINKS_FILE,
    RENAMES,
    SELECTS,
    TABLES,
    UPSERTS,
    build_course_index,
    build_user_index,
    load_links,
    transform,
)

CS_SUPA = "cccccccc-0000-0000-0000-000000000001"
CS_PG = "11111111-0000-0000-0000-000000000001"
IT_SUPA = "cccccccc-0000-0000-0000-000000000002"
IT_PG = "11111111-0000-0000-0000-000000000002"

LINKS = [
    {"supabase_course_id": CS_SUPA, "supabase_title": "วิทยาการคอมพิวเตอร์",
     "postgres_titles": ["หลักสูตร ... วิทยาการคอมพิวเตอร์ (พ.ศ. 2566)",
                         "หลักสูตร ... วิทยาการคอมพิวเตอร์ (พ.ศ. 2561)"]},
    {"supabase_course_id": IT_SUPA, "supabase_title": "เทคโนโลยีสารสนเทศ",
     "postgres_titles": ["หลักสูตร ... เทคโนโลยีสารสนเทศ (พ.ศ. 2566)"]},
]

PG_COURSES = [
    {"id": CS_PG, "title": "หลักสูตร ... วิทยาการคอมพิวเตอร์ (พ.ศ. 2566)"},
    {"id": IT_PG, "title": "หลักสูตร ... เทคโนโลยีสารสนเทศ (พ.ศ. 2566)"},
    {"id": "11111111-0000-0000-0000-000000000009", "title": "หลักสูตรที่ไม่อยู่ในตารางจับคู่"},
]

SUPA_USER = "aaaaaaaa-0000-0000-0000-000000000001"
PG_USER = "bbbbbbbb-0000-0000-0000-000000000001"
PG_USERS = [
    {"id": PG_USER, "supabase_user_id": SUPA_USER},
    {"id": "bbbbbbbb-0000-0000-0000-000000000002", "supabase_user_id": None},
]


def course_row(**over):
    row = {"id": CS_SUPA, "title": "วิทยาการคอมพิวเตอร์", "title_en": "Computer Science",
           "description": "คำบรรยาย", "logo": "https://example/logo.png", "careers": [],
           "detail": None, "created_by": SUPA_USER, "updated_by": None,
           "created_at": "2026-01-01", "updated_at": "2026-01-02"}
    row.update(over)
    return row


def news_row(**over):
    row = {"id": "dddddddd-0000-0000-0000-000000000001", "title": "ข่าวหนึ่ง",
           "description": "เนื้อหา", "category": "ทั่วไป", "date": "2026-10-01",
           "image": "https://example/news.png", "status": "published",
           "created_by": SUPA_USER, "updated_by": SUPA_USER,
           "created_at": "2026-01-01", "updated_at": "2026-01-02"}
    row.update(over)
    return row


class Base(unittest.TestCase):
    def setUp(self):
        self.courses = build_course_index(PG_COURSES, LINKS)
        self.users = build_user_index(PG_USERS)

    def t(self, table, row):
        return transform(table, row, self.courses, self.users)


class RenameChecks(Base):
    def test_logo_กลายเป็น_logo_url(self):
        out = self.t("site_courses", course_row())
        self.assertEqual(out["logo_url"], "https://example/logo.png")
        self.assertNotIn("logo", out)

    def test_date_กลายเป็น_published_on(self):
        out = self.t("news", news_row())
        self.assertEqual(out["published_on"], "2026-10-01")
        self.assertNotIn("date", out)

    def test_image_กลายเป็น_image_url(self):
        out = self.t("news", news_row())
        self.assertEqual(out["image_url"], "https://example/news.png")
        self.assertNotIn("image", out)

    def test_คอลัมน์ที่ชื่อเหมือนกันไม่ถูกแตะ(self):
        out = self.t("news", news_row())
        self.assertEqual(out["category"], "ทั่วไป")
        self.assertEqual(out["status"], "published")

    def test_ค่าว่างยังแปลงชื่อให้(self):
        out = self.t("site_courses", course_row(logo=None))
        self.assertIn("logo_url", out)
        self.assertIsNone(out["logo_url"])


class CourseMatchChecks(Base):
    def test_จับคู่จากตารางที่ยืนยันแล้ว(self):
        self.assertEqual(self.t("site_courses", course_row())["course_id"], CS_PG)

    def test_จับคู่ได้แม้ชื่อหนึ่งในหลายชื่อไม่มีในฐาน(self):
        """หลักสูตรเปลี่ยนชื่อ/หลายฉบับปี — มีชื่อเดียวตรงก็พอ"""
        self.assertEqual(self.courses[CS_SUPA], CS_PG)

    def test_ไม่อยู่ในตารางจับคู่_course_id_เป็น_NULL(self):
        out = self.t("site_courses", course_row(id="ffffffff-0000-0000-0000-000000000000"))
        self.assertIsNone(out["course_id"])

    def test_ชื่อในตารางจับคู่ไม่มีในฐานปลายทาง_ไม่จับคู่(self):
        idx = build_course_index([], LINKS)
        self.assertEqual(idx, {})

    def test_ชื่อชี้ไปหลายหลักสูตรที่ต่างกัน_ถือว่าคลุมเครือ(self):
        """กันไม่ให้จับคู่มั่วเมื่อข้อมูลขัดกัน — ยอมให้เป็น NULL ดีกว่าผิดคน"""
        ambiguous = [{"supabase_course_id": CS_SUPA, "supabase_title": "x",
                      "postgres_titles": ["ก", "ข"]}]
        idx = build_course_index([{"id": CS_PG, "title": "ก"},
                                  {"id": IT_PG, "title": "ข"}], ambiguous)
        self.assertEqual(idx, {})

    def test_ไม่จับคู่หลักสูตรที่ไม่ได้อยู่ในตาราง(self):
        self.assertNotIn("11111111-0000-0000-0000-000000000009", self.courses.values())


class OwnerChecks(Base):
    def test_แปลงผู้ใช้ที่จับคู่ไว้แล้ว(self):
        self.assertEqual(self.t("site_courses", course_row())["created_by"], PG_USER)

    def test_ผู้ใช้ที่จับคู่ไม่ได้เป็น_NULL(self):
        out = self.t("site_courses", course_row(created_by="ffffffff-0000-0000-0000-00000000ffff"))
        self.assertIsNone(out["created_by"])

    def test_ค่าว่างยังเป็นค่าว่าง(self):
        self.assertIsNone(self.t("site_courses", course_row())["updated_by"])

    def test_ไม่เคยปล่อย_uuid_ของ_supabase_ผ่านไปปลายทาง(self):
        """ข้อสำคัญสุด — ยัดค่าดิบลงไปคือ FK พังหรือชี้ผิดคน"""
        out = self.t("news", news_row())
        for key in ("created_by", "updated_by"):
            self.assertNotEqual(out[key], SUPA_USER)

    def test_ผู้ใช้ที่ยังไม่มี_supabase_user_id_ไม่เข้าดัชนี(self):
        self.assertEqual(len(self.users), 1)


class DetailChecks(Base):
    def test_detail_ที่เป็น_dict_ถูกแปลงเป็นข้อความ_json(self):
        out = self.t("site_courses", course_row(detail={"ก": "ข"}))
        self.assertIsInstance(out["detail"], str)
        self.assertEqual(json.loads(out["detail"]), {"ก": "ข"})

    def test_detail_ภาษาไทยไม่ถูกแปลงเป็น_escape(self):
        out = self.t("site_courses", course_row(detail={"ชื่อ": "ไทย"}))
        self.assertIn("ไทย", out["detail"])

    def test_detail_ว่างไม่ถูกแตะ(self):
        self.assertIsNone(self.t("site_courses", course_row(detail=None))["detail"])


class ShapeChecks(unittest.TestCase):
    def test_ทุกตารางมีทั้ง_select_และ_upsert(self):
        for t in TABLES:
            self.assertIn(t, SELECTS, f"{t} ไม่มี select")
            self.assertIn(t, UPSERTS, f"{t} ไม่มี upsert")

    def test_upsert_ทุกตัวเป็นแบบรันซ้ำได้(self):
        """รันซ้ำต้องอัปเดต ไม่ใช่เพิ่มแถวซ้ำ"""
        for t in TABLES:
            self.assertIn("on conflict (id) do update", UPSERTS[t], f"{t} ไม่ใช่ upsert")

    def test_select_อ่านจาก_public_ของต้นทางเท่านั้น(self):
        for t in TABLES:
            self.assertIn("from public.", SELECTS[t])
            self.assertNotIn("web.", SELECTS[t])

    def test_upsert_เขียนลง_web_เท่านั้น(self):
        """ห้ามเขียนทับ public หรือ mko ซึ่งเป็นข้อมูลที่ใช้งานอยู่จริง"""
        for t in TABLES:
            self.assertIn(f"into web.{t}", UPSERTS[t])
            self.assertNotIn("into public.", UPSERTS[t])
            self.assertNotIn("into mko.", UPSERTS[t])

    def test_ไม่มีคำสั่งลบหรือแก้โครงในสคริปต์(self):
        for t in TABLES:
            sql = (SELECTS[t] + UPSERTS[t]).lower()
            for word in ("drop ", "truncate", "alter table", "delete from"):
                self.assertNotIn(word, sql, f"{t} มีคำสั่งอันตราย: {word}")

    def test_ชื่อที่เปลี่ยนมีครบสามคู่(self):
        pairs = {(k, v) for table in RENAMES for k, v in RENAMES[table].items()}
        self.assertEqual(pairs, {("logo", "logo_url"), ("date", "published_on"), ("image", "image_url")})


class LinksFileChecks(unittest.TestCase):
    def test_ไฟล์ตารางจับคู่มีอยู่และอ่านได้(self):
        self.assertTrue(LINKS_FILE.exists())
        self.assertEqual(len(load_links()), 12)

    def test_ทุกรายการมีรหัสและชื่อครบ(self):
        for item in load_links():
            self.assertTrue(item["supabase_course_id"])
            self.assertTrue(item["supabase_title"])
            self.assertTrue(item["postgres_titles"])

    def test_รหัสหลักสูตรไม่ซ้ำ(self):
        ids = [i["supabase_course_id"] for i in load_links()]
        self.assertEqual(len(ids), len(set(ids)))

    def test_ชื่อฝั่ง_postgres_ไม่ถูกใช้ซ้ำข้ามหลักสูตร(self):
        """ชื่อซ้ำข้ามหลักสูตรคือจับคู่ผิดคนได้"""
        seen = {}
        for item in load_links():
            for title in item["postgres_titles"]:
                self.assertNotIn(title, seen, f"ชื่อซ้ำ: {title}")
                seen[title] = item["supabase_course_id"]


if __name__ == "__main__":
    unittest.main()
