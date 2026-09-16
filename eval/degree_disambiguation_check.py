"""
ตรวจการแยกหลักสูตรที่ชื่อสาขาและปีเดียวกันแต่คนละระดับปริญญา — MKO Phase 2 stabilization

    python -m eval.degree_disambiguation_check

ชุดแรกใช้หลักสูตรสมมติ ไม่ต้องมีฐานข้อมูล (ชื่อสาขาที่ใช้เป็นชื่อสมมติ ไม่ใช่ชื่อจริงในคลัง)
ชุดหลังอ่านหลักสูตรจริงจากฐานข้อมูล local หา "ชื่อสาขา + ปี ที่มีหลายระดับปริญญา" เองทุกกลุ่ม
ไม่ผูกชื่อสาขาหรือคำถามตัวอย่างไว้ในโค้ดที่แก้
"""
from __future__ import annotations

import os
import sys
import unittest
import uuid
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres@127.0.0.1:55432/course_advisor")
os.environ.setdefault("JWT_SECRET", "local-test-only")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.services.course_scope import (  # noqa: E402
    _distinctive_name,
    degree_level_of,
    degree_levels_of,
    degree_of_title,
    requested_degree_level,
    resolve_scope,
    resolve_scopes,
)
from app.services.curriculum_facts import LIST_FIELDS, NO_DATA, lookup  # noqa: E402
from app.services.structured_intent import RAG, STRUCTURED, StructuredIntent, detect  # noqa: E402

SUPPORTED_SINGLE_VALUE = "total_credits"


def course(title):
    return SimpleNamespace(id=uuid.uuid4(), title=title, is_active=True)


# ชื่อสาขาสมมติ: สาขาเดียว ปีเดียว แต่มีสามระดับปริญญา
BACHELOR = course("หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาการจัดการทดสอบ (พ.ศ. 2568)")
MASTER = course("หลักสูตรวิทยาศาสตรมหาบัณฑิต สาขาวิชาการจัดการทดสอบ (พ.ศ. 2568)")
DOCTORAL = course("หลักสูตรปรัชญาดุษฎีบัณฑิต สาขาวิชาการจัดการทดสอบ (พ.ศ. 2568)")
# สาขาที่มีระดับเดียวแต่สองปี — พฤติกรรมเดิมต้องไม่เปลี่ยน
SOLO_64 = course("หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาเคมีทดสอบ (พ.ศ. 2564)")
SOLO_69 = course("หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาเคมีทดสอบ (พ.ศ. 2569)")
COURSES = [BACHELOR, MASTER, DOCTORAL, SOLO_64, SOLO_69]


class FakeDb:
    def scalars(self, *args, **kwargs):
        return SimpleNamespace(all=lambda: COURSES)


DB = FakeDb()


class DegreeMetadataChecks(unittest.TestCase):
    """อ่านระดับปริญญาจากชื่อหลักสูตรและจากคำถาม"""

    def test_degree_name_is_taken_from_the_title(self):
        self.assertEqual(degree_of_title(MASTER.title), "วิทยาศาสตรมหาบัณฑิต")
        self.assertEqual(degree_of_title(DOCTORAL.title), "ปรัชญาดุษฎีบัณฑิต")
        self.assertEqual(degree_of_title(BACHELOR.title), "วิทยาศาสตรบัณฑิต")
        # ชื่อหลักสูตรที่ไม่มีคำว่า "สาขาวิชา" ทั้งชื่อคือชื่อปริญญา
        self.assertEqual(degree_of_title("หลักสูตรการแพทย์แผนไทยประยุกต์บัณฑิต (พ.ศ. 2560)"),
                         "การแพทย์แผนไทยประยุกต์บัณฑิต")

    def test_degree_level_from_names_and_abbreviations(self):
        for text, level in (
            ("วิทยาศาสตรมหาบัณฑิต", "master"), ("ปริญญาโท", "master"), ("ป.โท", "master"), ("วท.ม.", "master"),
            ("ปรัชญาดุษฎีบัณฑิต", "doctoral"), ("ปริญญาเอก", "doctoral"), ("ป.เอก", "doctoral"), ("ปร.ด.", "doctoral"),
            ("วิทยาศาสตรบัณฑิต", "bachelor"), ("ปริญญาตรี", "bachelor"), ("ป.ตรี", "bachelor"), ("วท.บ.", "bachelor"),
            ("การแพทย์แผนไทยประยุกต์บัณฑิต", "bachelor"), ("ศศ.บ.", "bachelor"),
        ):
            with self.subTest(text=text):
                self.assertEqual(degree_level_of(text), level)

    def test_words_that_are_not_a_degree_request(self):
        # "บัณฑิต" ลอยๆ แปลว่าผู้จบการศึกษา ไม่ใช่การระบุระดับปริญญา และ พ.ศ. ต้องไม่ถูกอ่านเป็นอักษรย่อปริญญา
        for text in ("บัณฑิตจบไปทำอาชีพอะไรได้บ้าง", "หลักสูตร พ.ศ. 2568 เรียนกี่หน่วยกิต", "เรียนกี่หน่วยกิต"):
            with self.subTest(text=text):
                self.assertIsNone(requested_degree_level(text))

    def test_levels_of_a_group(self):
        titles = {c.id: c.title for c in COURSES}
        self.assertEqual(degree_levels_of([BACHELOR.id, MASTER.id, DOCTORAL.id], titles),
                         {"bachelor", "master", "doctoral"})
        self.assertEqual(degree_levels_of([SOLO_64.id, SOLO_69.id], titles), {"bachelor"})


class ScopeNarrowingChecks(unittest.TestCase):
    """resolve_scope / resolve_scopes ต้องเหลือเฉพาะระดับที่ผู้ใช้ระบุ"""

    def assertScope(self, question, courses):
        scope = resolve_scope(DB, question)
        self.assertIsNotNone(scope, question)
        self.assertEqual(set(scope.course_ids), {c.id for c in courses}, question)

    def test_master_is_selected_by_degree_name(self):
        self.assertScope("หลักสูตรวิทยาศาสตรมหาบัณฑิต สาขาวิชาการจัดการทดสอบ เรียนกี่หน่วยกิต", [MASTER])

    def test_doctoral_is_selected_by_degree_name(self):
        self.assertScope("หลักสูตรปรัชญาดุษฎีบัณฑิต สาขาวิชาการจัดการทดสอบ เรียนกี่หน่วยกิต", [DOCTORAL])

    def test_level_words_select_the_right_curriculum(self):
        self.assertScope("สาขาการจัดการทดสอบ ปริญญาโท เรียนกี่หน่วยกิต", [MASTER])
        self.assertScope("สาขาการจัดการทดสอบ ป.เอก เรียนกี่หน่วยกิต", [DOCTORAL])
        self.assertScope("สาขาการจัดการทดสอบ ปริญญาตรี เรียนกี่หน่วยกิต", [BACHELOR])

    def test_abbreviations_select_the_right_curriculum(self):
        self.assertScope("วท.ม. การจัดการทดสอบ เรียนกี่หน่วยกิต", [MASTER])
        self.assertScope("ปร.ด. การจัดการทดสอบ เรียนกี่หน่วยกิต", [DOCTORAL])
        self.assertScope("วท.บ. การจัดการทดสอบ เรียนกี่หน่วยกิต", [BACHELOR])

    def test_without_a_degree_every_level_stays_in_scope(self):
        # ไม่เลือกให้เอง — ขอบเขตยังมีครบทุกระดับ (ขั้นตัดสินเส้นทางเป็นผู้จัดการความกำกวม)
        self.assertScope("สาขาการจัดการทดสอบ เรียนกี่หน่วยกิต", [BACHELOR, MASTER, DOCTORAL])

    def test_single_level_programme_is_unchanged(self):
        self.assertScope("สาขาเคมีทดสอบ เรียนกี่หน่วยกิต", [SOLO_64, SOLO_69])
        self.assertScope("สาขาเคมีทดสอบ พ.ศ. 2569 เรียนกี่หน่วยกิต", [SOLO_69])
        # คำว่าปริญญาที่ตรงกับระดับเดียวที่มีอยู่ ไม่ทำให้ขอบเขตหาย
        self.assertScope("หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาเคมีทดสอบ เรียนกี่หน่วยกิต", [SOLO_64, SOLO_69])

    def test_a_level_that_does_not_exist_keeps_the_scope(self):
        self.assertScope("สาขาเคมีทดสอบ ปริญญาเอก เรียนกี่หน่วยกิต", [SOLO_64, SOLO_69])

    def test_resolve_scopes_narrows_each_programme(self):
        scopes = resolve_scopes(DB, "วท.ม. การจัดการทดสอบ กับ สาขาเคมีทดสอบ ต่างกันอย่างไร")
        by_name = {s.matched_name: set(s.course_ids) for s in scopes}
        self.assertEqual(by_name.get("การจัดการทดสอบ"), {MASTER.id})
        self.assertEqual(by_name.get("เคมีทดสอบ"), {SOLO_64.id, SOLO_69.id})


class RoutingChecks(unittest.TestCase):
    """structured_intent: ระบุระดับ -> ตอบจากฐานข้อมูลของระดับนั้น, ไม่ระบุและกำกวม -> ไม่เดา"""

    def assertStructured(self, question, field, courses):
        intent = detect(DB, question)
        self.assertEqual((intent.route, intent.field), (STRUCTURED, field), f"{question} -> {intent}")
        self.assertEqual(set(intent.course_ids), {c.id for c in courses}, question)
        return intent

    def assertRag(self, question, reason):
        intent = detect(DB, question)
        self.assertEqual((intent.route, intent.reason), (RAG, reason), f"{question} -> {intent}")
        self.assertEqual(intent.course_ids, ())

    def test_total_credits_with_each_degree(self):
        self.assertStructured("หลักสูตรวิทยาศาสตรมหาบัณฑิต สาขาวิชาการจัดการทดสอบ เรียนกี่หน่วยกิต",
                              "total_credits", [MASTER])
        self.assertStructured("หลักสูตรปรัชญาดุษฎีบัณฑิต สาขาวิชาการจัดการทดสอบ เรียนกี่หน่วยกิต",
                              "total_credits", [DOCTORAL])
        self.assertStructured("วท.บ. การจัดการทดสอบ เรียนกี่หน่วยกิต", "total_credits", [BACHELOR])

    def test_careers_with_each_degree(self):
        self.assertStructured("จบ วท.ม. การจัดการทดสอบ ทำอาชีพอะไรได้บ้าง", "careers", [MASTER])
        self.assertStructured("จบปริญญาเอก สาขาการจัดการทดสอบ ทำอาชีพอะไรได้บ้าง", "careers", [DOCTORAL])

    def test_objectives_with_each_degree(self):
        self.assertStructured("หลักสูตรวิทยาศาสตรมหาบัณฑิต สาขาวิชาการจัดการทดสอบ มีวัตถุประสงค์อะไร",
                              "objectives", [MASTER])
        self.assertStructured("หลักสูตรปรัชญาดุษฎีบัณฑิต สาขาวิชาการจัดการทดสอบ มีวัตถุประสงค์อะไร",
                              "objectives", [DOCTORAL])

    def test_ambiguous_degree_is_not_guessed(self):
        for question, field in (
            ("สาขาการจัดการทดสอบ เรียนกี่หน่วยกิต", "total_credits"),
            ("จบสาขาการจัดการทดสอบ ทำอาชีพอะไรได้บ้าง", "careers"),
            ("สาขาการจัดการทดสอบ มีวัตถุประสงค์อะไร", "objectives"),
            ("คุณสมบัติผู้เข้าศึกษาสาขาการจัดการทดสอบ", "admission"),
        ):
            with self.subTest(question=question):
                self.assertRag(question, "multiple_degree_levels")

    def test_single_level_programme_still_goes_to_the_database(self):
        self.assertStructured("สาขาเคมีทดสอบ เรียนกี่หน่วยกิต", "total_credits", [SOLO_64, SOLO_69])
        self.assertStructured("จบสาขาเคมีทดสอบ ทำอาชีพอะไรได้บ้าง", "careers", [SOLO_64, SOLO_69])

    def test_year_and_degree_can_be_used_together(self):
        intent = self.assertStructured("วท.ม. การจัดการทดสอบ พ.ศ. 2568 เรียนกี่หน่วยกิต", "total_credits", [MASTER])
        self.assertEqual(intent.year_be, 2568)


class LookupGuardChecks(unittest.TestCase):
    """curriculum_facts.lookup: รายการต้องไม่หยิบฉบับแรกเงียบๆ เมื่อชุดนั้นมีหลายระดับปริญญา"""

    @classmethod
    def setUpClass(cls):
        from app.db.session import SessionLocal

        cls.db = SessionLocal()
        cls.titles = {row.id: row.title for row in cls.db.execute(
            __import__("sqlalchemy").text("SELECT id, title FROM public.courses WHERE is_active")).all()}
        groups = defaultdict(list)
        for cid, title in cls.titles.items():
            groups[(_distinctive_name(title), title[title.rfind("(") + 1:title.rfind(")")])].append(cid)
        cls.mixed = [ids for ids in groups.values() if len(degree_levels_of(ids, cls.titles)) > 1]

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_list_field_reports_ambiguity_instead_of_choosing(self):
        if not self.mixed:
            self.skipTest("ฐานข้อมูลนี้ไม่มีสาขา/ปีที่มีหลายระดับปริญญา")
        for ids in self.mixed:
            for field in LIST_FIELDS:
                with self.subTest(field=field, ids=len(ids)):
                    result = lookup(self.db, StructuredIntent(STRUCTURED, "test", field, "x", tuple(ids)))
                    self.assertEqual(result.status, NO_DATA)
                    self.assertIn("ระดับปริญญา", result.note or "")
                    self.assertEqual(result.facts, [])

    def test_single_degree_level_is_unaffected(self):
        single = [cid for cid, title in self.titles.items()
                  if all(cid not in ids for ids in self.mixed)]
        self.assertTrue(single)
        result = lookup(self.db, StructuredIntent(STRUCTURED, "test", "careers", "x", (single[0],)))
        self.assertNotIn("ระดับปริญญา", result.note or "")

    def test_scalar_field_still_lists_every_edition(self):
        if not self.mixed:
            self.skipTest("ฐานข้อมูลนี้ไม่มีสาขา/ปีที่มีหลายระดับปริญญา")
        ids = self.mixed[0]
        result = lookup(self.db, StructuredIntent(STRUCTURED, "test", SUPPORTED_SINGLE_VALUE, "x", tuple(ids)))
        # ค่าเดี่ยวไม่ถูกบล็อก เพราะแต่ละบรรทัดมีชื่อหลักสูตรเต็มกำกับอยู่แล้ว
        self.assertNotIn("ระดับปริญญา", result.note or "")


class RealCatalogueChecks(unittest.TestCase):
    """หากลุ่ม 'ชื่อสาขา + ปี ที่มีหลายระดับปริญญา' จากฐานข้อมูลจริง แล้วตรวจทุกกลุ่ม ทุกระดับ"""

    @classmethod
    def setUpClass(cls):
        from sqlalchemy import select

        from app.db.session import SessionLocal
        from app.models.course import Course

        cls.db = SessionLocal()
        cls.courses = cls.db.scalars(select(Course).where(Course.is_active.is_(True))).all()
        cls.titles = {c.id: c.title for c in cls.courses}
        groups = defaultdict(list)
        for c in cls.courses:
            year = c.title[c.title.rfind("(") + 1:c.title.rfind(")")]
            groups[(_distinctive_name(c.title), year)].append(c.id)
        cls.mixed = {key: ids for key, ids in groups.items() if len(degree_levels_of(ids, cls.titles)) > 1}

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_report_groups(self):
        print(f"\nกลุ่มชื่อสาขา+ปีที่มีหลายระดับปริญญาในฐานข้อมูล: {len(self.mixed)}")
        for (name, year), ids in self.mixed.items():
            print(f"  {name} {year}: " + ", ".join(sorted(degree_of_title(self.titles[cid]) for cid in ids)))
        self.assertIsInstance(self.mixed, dict)

    def test_every_mixed_group_is_separated_by_its_degree_name(self):
        if not self.mixed:
            self.skipTest("ฐานข้อมูลนี้ไม่มีสาขา/ปีที่มีหลายระดับปริญญา")
        for (name, _year), ids in self.mixed.items():
            for cid in ids:
                degree = degree_of_title(self.titles[cid])
                question = f"หลักสูตร{degree} สาขาวิชา{name} เรียนกี่หน่วยกิต"
                with self.subTest(question=question):
                    intent = detect(self.db, question)
                    self.assertEqual(intent.route, STRUCTURED, f"{question} -> {intent}")
                    self.assertEqual(set(intent.course_ids), {cid})

    def test_every_mixed_group_without_a_degree_is_not_guessed(self):
        if not self.mixed:
            self.skipTest("ฐานข้อมูลนี้ไม่มีสาขา/ปีที่มีหลายระดับปริญญา")
        for (name, _year), _ids in self.mixed.items():
            for template in ("สาขา{} เรียนกี่หน่วยกิต", "จบสาขา{} ทำอาชีพอะไรได้บ้าง"):
                question = template.format(name)
                with self.subTest(question=question):
                    intent = detect(self.db, question)
                    self.assertEqual((intent.route, intent.reason), (RAG, "multiple_degree_levels"),
                                     f"{question} -> {intent}")

    def test_programmes_with_one_degree_level_still_reach_the_database(self):
        checked = 0
        for name, ids in _by_name(self.courses).items():
            if len(degree_levels_of(ids, self.titles)) > 1:
                continue
            question = f"สาขา{name} เรียนกี่หน่วยกิต"
            with self.subTest(question=question):
                intent = detect(self.db, question)
                self.assertEqual(intent.route, STRUCTURED, f"{question} -> {intent}")
                self.assertEqual(set(intent.course_ids), set(ids))
            checked += 1
        self.assertGreaterEqual(checked, 15)


def _by_name(courses):
    out = defaultdict(list)
    for c in courses:
        out[_distinctive_name(c.title)].append(c.id)
    return out


if __name__ == "__main__":
    unittest.main(verbosity=2)
