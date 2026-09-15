"""
ตรวจคำถามต่อเนื่องที่เปลี่ยนเฉพาะหลักสูตรหรือปี — Phase 2 stabilization (docs/MKO_PHASE2_SHADOW_EVAL.md ข้อ 4)

    python -m eval.follow_up_scope_check

เหตุที่ต้องมี: บนหน้าเว็บจริง "สาขาวิทยาการคอมพิวเตอร์เรียนกี่หน่วยกิต" แล้วต่อด้วย "แล้วคณิตศาสตร์ล่ะ" ถูกตีความเป็น
"สาขาวิทยาการคอมพิวเตอร์เรียนวิชาคณิตศาสตร์อะไรบ้าง" เพราะชื่อหลักสูตรที่เป็นชื่อศาสตร์ถูกอ่านเป็นชื่อรายวิชา และคำถามที่
เขียนใหม่ได้คะแนนค้นหาสูงกว่าจึงถูกเลือก ทั้งที่เปลี่ยนหลักสูตรที่ผู้ใช้ระบุเอง

ข้อความคำถามในไฟล์นี้เป็นกรณีทดสอบ ไม่ได้อยู่ในโค้ดของระบบ ชุดทดสอบแบบวนทุกคู่หลักสูตรใช้ชื่อจากรายการหลักสูตรสมมติ
และจากฐานข้อมูล local (ถ้าต่อได้) เพื่อพิสูจน์ว่าไม่ได้ผูกกับคู่ใดคู่หนึ่ง ไม่เรียกโมเดล
"""
from __future__ import annotations

import itertools
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

import app.services.chat as chat  # noqa: E402
from app.services.course_scope import _distinctive_name  # noqa: E402
from app.services.follow_up import explicit_programmes, rewrite_keeps_explicit, swap_follow_up  # noqa: E402
from app.services.structured_intent import STRUCTURED, detect  # noqa: E402


def course(title):
    return SimpleNamespace(id=uuid.uuid4(), title=title, is_active=True)


COURSES = [course(t) for t in (
    "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาการคอมพิวเตอร์ (พ.ศ. 2561)",
    "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาการคอมพิวเตอร์ (พ.ศ. 2566)",
    "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาเทคโนโลยีสารสนเทศ (พ.ศ. 2561)",
    "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาเทคโนโลยีสารสนเทศ (พ.ศ. 2566)",
    "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาคณิตศาสตร์ (พ.ศ. 2564)",
    "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาคณิตศาสตร์ (พ.ศ. 2569)",
    "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาคอมพิวเตอร์แอนิเมชันและมัลติมีเดีย (พ.ศ. 2564)",
    "หลักสูตรการแพทย์แผนไทยประยุกต์บัณฑิต (พ.ศ. 2565)",
    "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาศาสตร์เครื่องสำอาง (พ.ศ. 2566)",
)]
CS, IT, MATH = "วิทยาการคอมพิวเตอร์", "เทคโนโลยีสารสนเทศ", "คณิตศาสตร์"


class FakeDb:
    def __init__(self, courses=COURSES):
        self.courses = courses

    def scalars(self, *args, **kwargs):
        return SimpleNamespace(all=lambda: self.courses)

    def execute(self, *args, **kwargs):
        # chat._program_names อ่านชื่อหลักสูตรด้วย SQL ตรง
        return SimpleNamespace(all=lambda: [SimpleNamespace(title=c.title) for c in self.courses])


DB = FakeDb()


def user(text):
    return SimpleNamespace(role="user", content=text)


def bot(text="(คำตอบของผู้ช่วย)"):
    return SimpleNamespace(role="assistant", content=text)


def meaning(db, question):
    found = detect(db, question)
    return found.route, found.field, found.programme, found.year_be


class RegressionCases(unittest.TestCase):
    """สามกรณีที่กำหนดในคำขอแก้ไข"""

    def test_A_change_programme_keeps_total_credits(self):
        asked = swap_follow_up(DB, [user("หลักสูตรเทคโนโลยีสารสนเทศเรียนกี่หน่วยกิต"), bot()], "แล้ววิทยาการคอมพิวเตอร์ล่ะ")
        self.assertEqual(meaning(DB, asked), (STRUCTURED, "total_credits", CS, None))
        self.assertNotIn(IT, asked)

    def test_B_programme_name_that_is_also_a_subject(self):
        asked = swap_follow_up(DB, [user("สาขาวิทยาการคอมพิวเตอร์เรียนกี่หน่วยกิต"), bot()], "แล้วคณิตศาสตร์ล่ะ")
        self.assertEqual(meaning(DB, asked), (STRUCTURED, "total_credits", MATH, None))
        self.assertNotIn(CS, asked)
        self.assertNotIn("วิชาคณิตศาสตร์", asked.replace("สาขาวิชาคณิตศาสตร์", ""))

    def test_C_change_edition_year_keeps_programme_and_field(self):
        asked = swap_follow_up(DB, [user("หลักสูตรคณิตศาสตร์ พ.ศ. 2569 เรียนกี่หน่วยกิต"), bot()], "แล้ว พ.ศ. 2564 ล่ะ")
        self.assertEqual(meaning(DB, asked), (STRUCTURED, "total_credits", MATH, 2564))
        self.assertNotIn("2569", asked)


class SwapChecks(unittest.TestCase):
    def test_chain_of_follow_ups_keeps_the_last_real_question(self):
        history = [user("หลักสูตรเทคโนโลยีสารสนเทศเรียนกี่หน่วยกิต"), bot(), user("แล้ววิทยาการคอมพิวเตอร์ล่ะ"), bot()]
        self.assertEqual(meaning(DB, swap_follow_up(DB, history, "แล้วคณิตศาสตร์ล่ะ")), (STRUCTURED, "total_credits", MATH, None))

    def test_aliases_in_either_turn(self):
        asked = swap_follow_up(DB, [user("วิทคอมเรียนกี่หน่วยกิต"), bot()], "แล้วไอทีล่ะครับ")
        self.assertEqual(meaning(DB, asked), (STRUCTURED, "total_credits", IT, None))
        self.assertNotIn("วิทคอม", asked)

    def test_other_fields_are_kept_too(self):
        asked = swap_follow_up(DB, [user("จบสาขาคณิตศาสตร์ทำงานอะไรได้บ้าง"), bot()], "แล้วเทคโนโลยีสารสนเทศล่ะ")
        self.assertEqual(meaning(DB, asked), (STRUCTURED, "careers", IT, None))

    def test_year_of_the_old_programme_is_dropped_when_programme_changes(self):
        asked = swap_follow_up(DB, [user("หลักสูตรคณิตศาสตร์ พ.ศ. 2569 เรียนกี่หน่วยกิต"), bot()], "แล้ววิทยาการคอมพิวเตอร์ล่ะ")
        self.assertEqual(meaning(DB, asked), (STRUCTURED, "total_credits", CS, None))

    def test_programme_and_year_together(self):
        asked = swap_follow_up(DB, [user("หลักสูตรเทคโนโลยีสารสนเทศเรียนกี่หน่วยกิต"), bot()], "แล้ววิทยาการคอมพิวเตอร์ ๒๕๖๑ ล่ะ")
        self.assertEqual(meaning(DB, asked), (STRUCTURED, "total_credits", CS, 2561))

    def test_year_only_uses_programme_of_the_conversation_when_question_has_none(self):
        asked = swap_follow_up(DB, [user("เรียนกี่หน่วยกิต"), bot()], "แล้ว พ.ศ. 2564 ล่ะ", context_programme=MATH)
        self.assertEqual(meaning(DB, asked), (STRUCTURED, "total_credits", MATH, 2564))
        self.assertIsNone(swap_follow_up(DB, [user("เรียนกี่หน่วยกิต"), bot()], "แล้ว พ.ศ. 2564 ล่ะ"))

    def test_not_a_pure_swap(self):
        history = [user("สาขาวิทยาการคอมพิวเตอร์เรียนกี่หน่วยกิต"), bot()]
        for message in ("แล้วคณิตศาสตร์เรียนกี่ปี", "แล้ววิชาคณิตศาสตร์ล่ะ", "แล้วค่าเทอมล่ะ", "แล้วสาขานี้ล่ะ",
                        "ขอบคุณครับ", "แล้ววิทยาการคอมพิวเตอร์กับคณิตศาสตร์ล่ะ"):
            with self.subTest(message=message):
                self.assertIsNone(swap_follow_up(DB, history, message))

    def test_no_history_or_comparison_base(self):
        self.assertIsNone(swap_follow_up(DB, [], "แล้วคณิตศาสตร์ล่ะ"))
        base = [user("วิทยาการคอมพิวเตอร์กับเทคโนโลยีสารสนเทศต่างกันอย่างไร"), bot()]
        self.assertIsNone(swap_follow_up(DB, base, "แล้วคณิตศาสตร์ล่ะ"))

    def test_every_ordered_pair_of_programmes(self):
        names = sorted({_distinctive_name(c.title) for c in COURSES})
        for old, new in itertools.permutations(names, 2):
            with self.subTest(old=old, new=new):
                asked = swap_follow_up(DB, [user(f"หลักสูตร{old}เรียนกี่หน่วยกิต"), bot()], f"แล้ว{new}ล่ะ")
                self.assertEqual(meaning(DB, asked), (STRUCTURED, "total_credits", new, None))


class ExplicitProgrammeGuardChecks(unittest.TestCase):
    def test_subject_mentions_are_not_programmes(self):
        self.assertEqual(explicit_programmes(DB, "สาขาวิทยาการคอมพิวเตอร์เรียนวิชาคณิตศาสตร์อะไรบ้าง"), [CS])
        self.assertEqual(explicit_programmes(DB, "หลักสูตรคณิตศาสตร์มีรายวิชาอะไรบ้าง"), [MATH])
        self.assertEqual(explicit_programmes(DB, "แล้ววิชาคณิตศาสตร์ล่ะ"), [])

    def test_rewrite_that_changes_the_named_programme_is_rejected(self):
        self.assertFalse(rewrite_keeps_explicit(DB, "แล้วคณิตศาสตร์ล่ะ", "สาขาวิทยาการคอมพิวเตอร์เรียนวิชาคณิตศาสตร์อะไรบ้าง"))
        self.assertTrue(rewrite_keeps_explicit(DB, "แล้วคณิตศาสตร์ล่ะ", "หลักสูตรคณิตศาสตร์เรียนกี่หน่วยกิต"))
        self.assertTrue(rewrite_keeps_explicit(DB, "แล้วต้องเรียนกี่ปี", "หลักสูตรวิทยาการคอมพิวเตอร์ต้องเรียนกี่ปี"))

    def test_condense_prompt_names_the_programme_only_when_the_user_named_one(self):
        history = [user("สาขาวิทยาการคอมพิวเตอร์เรียนกี่หน่วยกิต"), bot()]
        plain = chat._format_history_for_condense(history, CS)
        self.assertEqual(plain, f"(หลักสูตรที่กำลังคุยกันล่าสุด: {CS})\n- สาขาวิทยาการคอมพิวเตอร์เรียนกี่หน่วยกิต")
        named = chat._format_history_for_condense(history, CS, [MATH])
        self.assertTrue(named.startswith(plain))
        self.assertIn(f"คำถามล่าสุดระบุชื่อหลักสูตรเอง: {MATH}", named)


def result(course_obj, score, content="เนื้อหาทดสอบ"):
    return SimpleNamespace(chunk_id=uuid.uuid4(), course_id=course_obj.id, course_title=course_obj.title,
                           page_number=1, content=content, score=score)


class PrepareAnswerChecks(unittest.TestCase):
    """เส้นทางใน prepare_answer ด้วยตัวปลอม: คะแนนค้นหาของคำถามที่ผิดหลักสูตรตั้งใจให้สูงกว่าเสมอ"""

    def setUp(self):
        self.condense_calls = []
        self.condense_reply = None
        self.gate_calls = []
        self.saved_names = chat._PROGRAM_NAMES
        chat._PROGRAM_NAMES = None
        by_name = {}
        for c in COURSES:
            by_name.setdefault(_distinctive_name(c.title), c)

        def fake_retrieve(db, connector, question):
            named = explicit_programmes(db, question)
            owner = by_name[named[0]] if named else COURSES[0]
            # คำถามที่เอ่ยถึงวิทยาการคอมพิวเตอร์ได้คะแนนสูงกว่าเสมอ เพื่อพิสูจน์ว่าคะแนนไม่ใช่ตัวตัดสินอีกต่อไป
            # คำถามที่สมบูรณ์ในตัว (ไม่ขึ้นต้นด้วย "แล้ว") ได้คะแนนสูงกว่าคำถามต่อเนื่องดิบ ตามที่เกิดกับการค้นจริง
            if CS in question:
                return [result(owner, 0.9)]
            return [result(owner, 0.6 if question.startswith("แล้ว") else 0.7)]

        def fake_condense(connector, history, message, programme=None, explicit=None):
            self.condense_calls.append((message, programme, explicit))
            return self.condense_reply or message

        def fake_gate(connector, chunks, question, comparison=False, note=""):
            self.gate_calls.append((question, comparison, note))
            return True

        patches = [
            mock.patch.object(chat, "_load_session", return_value=SimpleNamespace(id=uuid.uuid4())),
            mock.patch.object(chat, "corpus_version", return_value="test"),
            mock.patch.object(chat, "cache_lookup", return_value=None),
            mock.patch.object(chat, "get_llm_connector", return_value=object()),
            mock.patch.object(chat, "_refinement_of_recommendation", return_value=None),
            mock.patch.object(chat, "_recommendation_intent", return_value=None),
            mock.patch.object(chat, "_names_an_unknown_program", return_value=None),
            mock.patch.object(chat, "_needs_a_program_named", return_value=False),
            mock.patch.object(chat, "_is_about_scope", return_value=True),
            mock.patch.object(chat, "_retrieve", side_effect=fake_retrieve),
            mock.patch.object(chat, "_condense", side_effect=fake_condense),
            mock.patch.object(chat, "_can_answer_from", side_effect=fake_gate),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def tearDown(self):
        chat._PROGRAM_NAMES = self.saved_names

    def ask(self, message, *turns):
        prior = [chat.PriorTurn(role=role, content=text) for role, text in turns]
        return chat.prepare_answer(DB, uuid.uuid4(), None, message, prior)

    def test_B_end_to_end_uses_the_named_programme_without_the_model(self):
        p = self.ask("แล้วคณิตศาสตร์ล่ะ", ("user", "สาขาวิทยาการคอมพิวเตอร์เรียนกี่หน่วยกิต"), ("assistant", "130 หน่วยกิต"))
        self.assertEqual(meaning(DB, p.interpreted), (STRUCTURED, "total_credits", MATH, None))
        self.assertEqual(self.condense_calls, [])
        self.assertEqual(self.gate_calls[0][0], p.interpreted)

    def test_rewrite_that_moves_to_another_programme_is_discarded_even_with_higher_score(self):
        self.condense_reply = "สาขาวิทยาการคอมพิวเตอร์เรียนวิชาคณิตศาสตร์อะไรบ้าง"
        message = "แล้วคณิตศาสตร์มีวิชาอะไรบ้าง"
        p = self.ask(message, ("user", "สาขาวิทยาการคอมพิวเตอร์เรียนกี่หน่วยกิต"), ("assistant", "130 หน่วยกิต"))
        self.assertEqual(p.interpreted, message)
        # ขั้นเขียนคำถามใหม่ได้ทั้งหลักสูตรที่คุยก่อนหน้าและหลักสูตรที่ผู้ใช้ระบุ
        self.assertEqual(self.condense_calls, [(message, CS, [MATH])])

    def test_rewrite_that_keeps_the_named_programme_is_used(self):
        self.condense_reply = "หลักสูตรคณิตศาสตร์มีวิชาอะไรบ้าง"
        p = self.ask("แล้วคณิตศาสตร์มีวิชาอะไรบ้าง", ("user", "สาขาวิทยาการคอมพิวเตอร์เรียนกี่หน่วยกิต"), ("assistant", "."))
        self.assertEqual(p.interpreted, "หลักสูตรคณิตศาสตร์มีวิชาอะไรบ้าง")

    def test_follow_up_without_a_named_programme_behaves_as_before(self):
        self.condense_reply = "หลักสูตรคณิตศาสตร์ต้องเรียนกี่ปี"
        p = self.ask("แล้วต้องเรียนกี่ปี", ("user", "หลักสูตรคณิตศาสตร์เรียนกี่หน่วยกิต"), ("assistant", "."))
        self.assertEqual(p.interpreted, "หลักสูตรคณิตศาสตร์ต้องเรียนกี่ปี")
        self.assertEqual(self.condense_calls, [("แล้วต้องเรียนกี่ปี", MATH, [])])

    def test_swapped_tuition_follow_up_goes_to_the_fee_table(self):
        p = self.ask("แล้วคณิตศาสตร์ล่ะ", ("user", "ค่าเทอมวิทคอมเท่าไหร่"), ("assistant", "."))
        self.assertIsNotNone(p.canned)
        self.assertIn(MATH, p.canned)
        self.assertEqual(self.gate_calls, [])


class RealCatalogueChecks(unittest.TestCase):
    """ทุกคู่หลักสูตรจริงในฐานข้อมูล local — ไม่มีชื่อหลักสูตรในชุดทดสอบนี้"""

    @classmethod
    def setUpClass(cls):
        from sqlalchemy import select

        from app.db.session import SessionLocal
        from app.models.course import Course

        try:
            cls.db = SessionLocal()
            cls.courses = cls.db.scalars(select(Course).where(Course.is_active.is_(True))).all()
        except Exception as exc:  # noqa: BLE001
            raise unittest.SkipTest(f"ต่อฐานข้อมูล local ไม่ได้: {type(exc).__name__}")

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_every_ordered_pair_keeps_field_and_changes_programme(self):
        names = sorted({_distinctive_name(c.title) for c in self.courses})
        self.assertGreater(len(names), 10)
        for old, new in itertools.permutations(names, 2):
            with self.subTest(old=old, new=new):
                asked = swap_follow_up(self.db, [user(f"หลักสูตร{old}เรียนกี่หน่วยกิต"), bot()], f"แล้ว{new}ล่ะ")
                self.assertEqual(meaning(self.db, asked)[:3], (STRUCTURED, "total_credits", new))


if __name__ == "__main__":
    unittest.main(verbosity=1)
