"""
ตรวจการตัดสินเส้นทางคำถาม: ตอบจากข้อมูลหลักสูตรที่มีโครงสร้าง หรือส่งไป RAG ตามเดิม — MKO Phase 2

    python -m eval.structured_routing_check

ชุดแรกใช้หลักสูตรสมมติ ไม่ต้องมีฐานข้อมูล ข้อความคำถามแต่งขึ้นสำหรับทดสอบ
ชุดสุดท้ายสร้างคำถามจากรายชื่อหลักสูตรจริงในฐานข้อมูล local ทุกหลักสูตร ไม่ผูกชื่อไว้ในโค้ด
"""
from __future__ import annotations

import os
import sys
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres@127.0.0.1:55432/course_advisor")
os.environ.setdefault("JWT_SECRET", "local-test-only")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.services.course_scope import _distinctive_name  # noqa: E402
from app.services.structured_intent import RAG, STRUCTURED, detect, years_in  # noqa: E402


def course(title):
    return SimpleNamespace(id=uuid.uuid4(), title=title, is_active=True)


CS_61 = course("หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาการคอมพิวเตอร์ (พ.ศ. 2561)")
CS_66 = course("หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาการคอมพิวเตอร์ (พ.ศ. 2566)")
IT_61 = course("หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาเทคโนโลยีสารสนเทศ (พ.ศ. 2561)")
IT_66 = course("หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาเทคโนโลยีสารสนเทศ (พ.ศ. 2566)")
MATH_64 = course("หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาคณิตศาสตร์ (พ.ศ. 2564)")
MATH_69 = course("หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาคณิตศาสตร์ (พ.ศ. 2569)")
COSM = course("หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาศาสตร์เครื่องสำอาง (พ.ศ. 2566)")
THAI = course("หลักสูตรการแพทย์แผนไทยประยุกต์บัณฑิต (พ.ศ. 2565)")
# ชื่อสาขาสมมติที่มีคำของ field อยู่ในชื่อ ใช้ตรวจว่าชื่อหลักสูตรไม่ถูกนับเป็นคำถาม
CAREER_NAMED = course("หลักสูตรศิลปศาสตรบัณฑิต สาขาวิชาการพัฒนาอาชีพ (พ.ศ. 2565)")
COURSES = [CS_61, CS_66, IT_61, IT_66, MATH_64, MATH_69, COSM, THAI, CAREER_NAMED]


class FakeDb:
    def scalars(self, *args, **kwargs):
        return SimpleNamespace(all=lambda: COURSES)


DB = FakeDb()


class RoutingCase(unittest.TestCase):
    def assertStructured(self, question, field, courses, year=None):
        intent = detect(DB, question)
        self.assertEqual((intent.route, intent.field), (STRUCTURED, field), f"{question} -> {intent}")
        self.assertEqual(set(intent.course_ids), {c.id for c in courses}, question)
        self.assertEqual(intent.year_be, year, question)
        return intent

    def assertRag(self, question, reason=None):
        intent = detect(DB, question)
        self.assertEqual(intent.route, RAG, f"{question} -> {intent}")
        self.assertEqual(intent.course_ids, ())
        if reason is not None:
            self.assertEqual(intent.reason, reason, question)
        return intent


class CreditChecks(RoutingCase):
    def test_total_credit_questions(self):
        self.assertStructured("หลักสูตรวิทยาการคอมพิวเตอร์ต้องเรียนกี่หน่วยกิต", "total_credits", [CS_61, CS_66])
        self.assertStructured("สาขาคณิตศาสตร์เรียนทั้งหมดกี่หน่วยกิต", "total_credits", [MATH_64, MATH_69])
        self.assertStructured("จำนวนหน่วยกิตรวมของหลักสูตรการแพทย์แผนไทยประยุกต์", "total_credits", [THAI])

    def test_credit_structure_is_not_answered_from_totals(self):
        self.assertRag("หมวดวิชาศึกษาทั่วไปของคณิตศาสตร์กี่หน่วยกิต", "unsupported_topic")
        self.assertRag("วิทยาการคอมพิวเตอร์วิชาเลือกเสรีกี่หน่วยกิต", "unsupported_topic")
        self.assertRag("เทคโนโลยีสารสนเทศลงทะเบียนเทอมละกี่หน่วยกิต", "unsupported_topic")

    def test_programme_name_words_are_not_question_words(self):
        # ชื่อสาขามีคำว่า "อาชีพ" แต่คำถามถามหน่วยกิตอย่างเดียว
        self.assertStructured("สาขาการพัฒนาอาชีพเรียนกี่หน่วยกิต", "total_credits", [CAREER_NAMED])


class YearChecks(RoutingCase):
    def test_edition_year_questions(self):
        self.assertStructured("หลักสูตรคณิตศาสตร์เป็นหลักสูตรปีอะไร", "edition_year", [MATH_64, MATH_69])
        self.assertStructured("หลักสูตรเทคโนโลยีสารสนเทศ พ.ศ. อะไร", "edition_year", [IT_61, IT_66])
        self.assertStructured("วิทยาการคอมพิวเตอร์ปรับปรุงล่าสุดเมื่อไหร่", "edition_year", [CS_61, CS_66])

    def test_study_duration_is_not_edition_year(self):
        self.assertRag("คณิตศาสตร์เรียนกี่ปีจบ", "unsupported_topic")


class CareerObjectiveAdmissionChecks(RoutingCase):
    def test_careers(self):
        self.assertStructured("จบสาขาคณิตศาสตร์สามารถประกอบอาชีพอะไรได้บ้าง", "careers", [MATH_64, MATH_69])
        self.assertStructured("เรียนวิทยาการคอมพิวเตอร์จบไปทำงานอะไรได้บ้าง", "careers", [CS_61, CS_66])
        # ถ้อยคำจากชุดประเมินที่เคยหลุดไป RAG ในการเล่นซ้ำครั้งแรก
        self.assertStructured("บัณฑิตที่จบจากสาขาวิชาเทคโนโลยีสารสนเทศ สามารถทำงานในตำแหน่งไหนได้บ้าง", "careers", [IT_61, IT_66])

    def test_objectives(self):
        self.assertStructured("หลักสูตรเทคโนโลยีสารสนเทศมีวัตถุประสงค์อะไร", "objectives", [IT_61, IT_66])
        self.assertStructured("หลักสูตรวิทยาศาสตร์เครื่องสำอางมีวัตถุประสงค์อย่างไร", "objectives", [COSM])

    def test_admission(self):
        self.assertStructured("คุณสมบัติผู้เข้าศึกษาหลักสูตรคณิตศาสตร์มีอะไรบ้าง", "admission", [MATH_64, MATH_69])
        self.assertStructured("ใครสมัครเรียนสาขาเทคโนโลยีสารสนเทศได้บ้าง", "admission", [IT_61, IT_66])
        self.assertStructured("ผู้ที่จะสมัครเรียนหลักสูตรวิทยาการคอมพิวเตอร์ต้องจบการศึกษาระดับใด หรือจบจากสายการเรียนใดบ้าง",
                              "admission", [CS_61, CS_66])

    def test_application_process_is_not_admission_field(self):
        self.assertRag("วิธีการสมัครเข้าศึกษาต่อรอบโควตาต้องดำเนินการอย่างไร")
        self.assertRag("เกรดเฉลี่ยขั้นต่ำ GPAX ที่ใช้ในการสมัครเข้าศึกษาต่อหลักสูตรเทคโนโลยีสารสนเทศคือเท่าไหร่")

    def test_graduate_attributes_are_not_admission(self):
        self.assertRag("คุณสมบัติของบัณฑิตสาขาคณิตศาสตร์", "unsupported_topic")


class MultiYearChecks(RoutingCase):
    def test_year_is_kept_for_edition_selection(self):
        # ขอบเขตยังเป็นทุกฉบับของหลักสูตร การเลือกฉบับทำใน curriculum_facts จากปีของฉบับที่เผยแพร่
        self.assertStructured("วิทยาการคอมพิวเตอร์ พ.ศ. 2566 เรียนกี่หน่วยกิต", "total_credits", [CS_61, CS_66], 2566)
        self.assertStructured("คณิตศาสตร์ ๒๕๖๔ เรียนทั้งหมดกี่หน่วยกิต", "total_credits", [MATH_64, MATH_69], 2564)

    def test_common_era_year_becomes_buddhist_era(self):
        self.assertStructured("comsci ปี 2023 กี่หน่วยกิต", "total_credits", [CS_61, CS_66], 2566)
        self.assertEqual(years_in("หลักสูตร ค.ศ. 2018"), [2561])
        self.assertEqual(years_in("พ.ศ.๒๕๖๑ และ 2561"), [2561])

    def test_two_editions_in_one_question_go_to_rag(self):
        self.assertRag("วิทยาการคอมพิวเตอร์ 2561 กับ 2566 เรียนกี่หน่วยกิต", "multiple_years")
        self.assertRag("วิทยาการคอมพิวเตอร์ 2561 กับ 2566 ต่างกันอย่างไร")


class NarrativeStaysOnRagChecks(RoutingCase):
    def test_narrative_questions(self):
        for question in (
            "ทำไมต้องเรียนวิทยาการคอมพิวเตอร์",
            "อธิบายหลักสูตรคณิตศาสตร์ให้ฟังหน่อย",
            "สาขาเทคโนโลยีสารสนเทศเหมาะกับคนแบบไหน",
            "หลักสูตรคณิตศาสตร์เรียนเกี่ยวกับอะไร",
            "เรียนวิทยาการคอมพิวเตอร์จบไปทำงานอะไรได้บ้าง และทำไมถึงเหมาะกับยุคนี้",
            "จบเทคโนโลยีสารสนเทศแล้วเป็นโปรแกรมเมอร์ได้ไหม",
        ):
            with self.subTest(question=question):
                self.assertRag(question)

    def test_unsupported_topics(self):
        for question in (
            "วิทยาการคอมพิวเตอร์ต้องเรียนวิชาอะไรบ้าง",
            "ค่าเทอมวิทยาการคอมพิวเตอร์เท่าไหร่",
            "PLO ของหลักสูตรเทคโนโลยีสารสนเทศมีอะไรบ้าง",
            "อาจารย์ผู้รับผิดชอบหลักสูตรคณิตศาสตร์มีใครบ้าง",
        ):
            with self.subTest(question=question):
                self.assertRag(question, "unsupported_topic")

    def test_questions_without_programme(self):
        self.assertRag("ต้องเรียนกี่หน่วยกิต", "no_programme")
        self.assertRag("", "empty")


class ComparisonIsNotForcedToDatabaseChecks(RoutingCase):
    def test_two_programmes(self):
        self.assertRag("วิทยาการคอมพิวเตอร์กับเทคโนโลยีสารสนเทศเรียนกี่หน่วยกิต", "multiple_programmes")
        self.assertRag("อาชีพของคณิตศาสตร์กับวิทยาการคอมพิวเตอร์", "multiple_programmes")

    def test_comparison_words(self):
        self.assertRag("วิทยาการคอมพิวเตอร์กับเทคโนโลยีสารสนเทศต่างกันอย่างไร")
        self.assertRag("เปรียบเทียบจำนวนหน่วยกิตของวิทยาการคอมพิวเตอร์", "narrative_or_comparison")

    def test_questions_across_programmes(self):
        self.assertRag("สาขาไหนเรียนหน่วยกิตน้อยที่สุด")
        self.assertRag("หลักสูตรใดมีหน่วยกิตมากกว่าคณิตศาสตร์")


class RealCatalogueChecks(unittest.TestCase):
    """คำถามที่สร้างจากรายชื่อหลักสูตรจริงในฐานข้อมูล local — ทุกหลักสูตรต้องถูกระบุได้ถูกตัวและไม่ปนกับหลักสูตรอื่น"""

    @classmethod
    def setUpClass(cls):
        from sqlalchemy import select

        from app.db.session import SessionLocal
        from app.models.course import Course

        cls.db = SessionLocal()
        cls.courses = cls.db.scalars(select(Course).where(Course.is_active.is_(True))).all()
        cls.by_name = {}
        for c in cls.courses:
            cls.by_name.setdefault(_distinctive_name(c.title), set()).add(c.id)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_every_programme_routes_to_itself(self):
        self.assertGreater(len(self.by_name), 10)
        for name, ids in self.by_name.items():
            with self.subTest(programme=name):
                intent = detect(self.db, f"หลักสูตร{name}ต้องเรียนทั้งหมดกี่หน่วยกิต")
                self.assertEqual((intent.route, intent.field, intent.programme), (STRUCTURED, "total_credits", name))
                self.assertEqual(set(intent.course_ids), ids)

    def test_every_pair_is_left_to_rag(self):
        names = sorted(self.by_name)
        for first, second in zip(names, names[1:]):
            with self.subTest(pair=(first, second)):
                self.assertEqual(detect(self.db, f"{first}กับ{second}เรียนกี่หน่วยกิต").route, RAG)


if __name__ == "__main__":
    unittest.main(verbosity=1)
