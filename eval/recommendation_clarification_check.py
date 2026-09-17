"""
ตรวจด่านถามกลับเมื่อผู้ใช้ขอให้ช่วยเลือกสาขาแต่ยังไม่ได้บอกความสนใจ

เหตุที่ต้องมี: บนระบบจริง "เรียนไรดี" (ไม่มีบทสนทนาก่อนหน้า) ได้คำแนะนำสามสาขาทันที คือคณิตศาสตร์
เทคโนโลยีสารสนเทศ และวิทยาศาสตร์เครื่องสำอาง โดยทั้งสามบรรทัดใต้ชื่อเขียนเองว่าเอกสารไม่ได้ระบุความ
เชื่อมโยงไว้ (log 2026-09-17 19:57Z) ต้นเหตุคือขั้นจำแนกเจตนาคืน interest ว่าง แล้วโค้ดแทนที่ด้วย
ข้อความทั้งประโยคก่อนส่งไปจับคู่ ดู docs/CHAT_RECOMMENDATION_CLARIFICATION_RCA.md

ค่าที่โมเดลคืนจริงถูกวัดไว้แล้ว (docs/CHAT_RECOMMENDATION_CLARIFICATION_VALIDATION.md)
    "เรียนไรดี" / "แนะนำสาขาหน่อย"   -> interest ""
    "ชอบเขียนโปรแกรม เรียนอะไรดี"     -> interest "ชอบเขียนโปรแกรม"
ไฟล์นี้จึงจำลองคำตอบของโมเดลตามนั้น แล้วตรวจว่าโค้ดตัดสินใจถูก ไม่เรียกโมเดลจริงและไม่ต่อฐานข้อมูล

    python -m eval.recommendation_clarification_check
"""
from __future__ import annotations

import json
import os
import sys
import types
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres@127.0.0.1:55432/course_advisor")
os.environ.setdefault("JWT_SECRET", "local-test-only")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import app.services.chat as chat  # noqa: E402

COURSES = [
    "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาการคอมพิวเตอร์ (พ.ศ. 2566)",
    "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาเทคโนโลยีสารสนเทศ (พ.ศ. 2566)",
    "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาคณิตศาสตร์ (พ.ศ. 2569)",
    "หลักสูตรศิลปศาสตรบัณฑิต สาขาวิชาการประกอบอาหารและการบริการอาหาร (พ.ศ. 2565)",
]
NAMES = ["วิทยาการคอมพิวเตอร์", "เทคโนโลยีสารสนเทศ", "คณิตศาสตร์", "การประกอบอาหารและการบริการอาหาร"]

NO_PREFERENCE_MESSAGES = [
    "เรียนไรดี",
    "เรียนอะไรดี",
    "แนะนำสาขาหน่อย",
    "ไม่รู้จะเรียนอะไร",
    "มีสาขาไหนน่าเรียน",
    "ช่วยเลือกสาขาให้หน่อย",
]

# ข้อความที่มีความสนใจ คู่กับส่วนที่ขั้นจำแนกเจตนาคัดมาได้ (ต้องเป็นข้อความย่อยของคำถามจริง)
WITH_PREFERENCE = [
    ("ชอบคอม เรียนอะไรดี", "ชอบคอม"),
    ("ชอบเขียนโปรแกรมควรเรียนสาขาไหน", "ชอบเขียนโปรแกรม"),
    ("ชอบคณิตศาสตร์และวิเคราะห์ข้อมูล เรียนอะไรดี", "ชอบคณิตศาสตร์และวิเคราะห์ข้อมูล"),
    ("อยากทำงานด้านอาหารควรเรียนอะไร", "อยากทำงานด้านอาหาร"),
]


class FakeDb:
    def scalars(self, *args, **kwargs):
        return SimpleNamespace(all=lambda: [SimpleNamespace(id=uuid.uuid4(), title=t, is_active=True) for t in COURSES])

    def execute(self, *args, **kwargs):
        return SimpleNamespace(all=lambda: [SimpleNamespace(title=t) for t in COURSES])


DB = FakeDb()


class FakeConnector:
    """ตอบแทนขั้นจำแนกเจตนาด้วยผลที่วัดมาจากระบบจริง และนับจำนวนครั้งที่ถูกเรียก"""

    def __init__(self, interest: str, recommendation: bool = True):
        self.reply = json.dumps({"recommendation": recommendation, "interest": interest}, ensure_ascii=False)
        self.calls = 0

    def chat(self, messages, **kwargs):
        self.calls += 1
        return self.reply


class _Base(unittest.TestCase):
    """เรียก prepare_answer จริง โดยดัก match_programs ไว้ดูว่าถูกเรียกหรือไม่"""

    def setUp(self):
        self.saved_names = chat._PROGRAM_NAMES
        chat._PROGRAM_NAMES = NAMES
        self.match_calls = []
        self.matches = []

        def fake_match(db, answers, limit=3, relevant_only=False, profile_text=None):
            self.match_calls.append({"answers": answers, "limit": limit, "relevant_only": relevant_only,
                                     "profile_text": profile_text})
            return self.matches

        fake = types.ModuleType("app.services.program_match")
        fake.match_programs = fake_match
        fake.confidence_of = lambda ms: "high"
        self.real_module = sys.modules.get("app.services.program_match")
        sys.modules["app.services.program_match"] = fake
        self.addCleanup(self._restore_module)

        patches = [
            mock.patch.object(chat, "_load_session", return_value=SimpleNamespace(id=uuid.uuid4())),
            mock.patch.object(chat, "_load_history", return_value=[]),  # บทสนทนามาจาก prior เท่านั้น
            mock.patch.object(chat, "corpus_version", return_value="test"),
            mock.patch.object(chat, "cache_lookup", return_value=None),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def _restore_module(self):
        if self.real_module is not None:
            sys.modules["app.services.program_match"] = self.real_module
        else:
            sys.modules.pop("app.services.program_match", None)

    def tearDown(self):
        chat._PROGRAM_NAMES = self.saved_names

    def ask(self, message, interest, *turns, matches=None):
        self.matches = matches if matches is not None else []
        conn = FakeConnector(interest)
        prior = [chat.PriorTurn(role=role, content=text) for role, text in turns]
        with mock.patch.object(chat, "get_llm_connector", return_value=conn):
            prepared = chat.prepare_answer(DB, uuid.uuid4(), None, message, prior)
        return prepared


def match(title, rationale="เหตุผลตัวอย่าง"):
    return SimpleNamespace(title=title, rationale=rationale, course_id=uuid.uuid4())


class NoPreferenceChecks(_Base):
    def test_ขอคำแนะนำโดยไม่บอกความสนใจได้คำถามกลับ_และไม่จับคู่สาขา(self):
        for message in NO_PREFERENCE_MESSAGES:
            with self.subTest(message=message):
                self.match_calls.clear()
                prepared = self.ask(message, "")
                self.assertEqual(prepared.canned, chat._NO_PREFERENCE_REPLY, message)
                self.assertEqual(prepared.status, "answered", message)
                self.assertEqual(self.match_calls, [], f"ต้องไม่เรียก match_programs กับ {message!r}")

    def test_คำถามกลับถามสี่หัวข้อที่ใช้จับคู่จริง(self):
        reply = chat._NO_PREFERENCE_REPLY
        for topic in ("วิชา", "สนใจ", "ถนัด", "ทำงาน"):
            self.assertIn(topic, reply)
        self.assertIn("รายชื่อสาขาทั้งหมด", reply)

    def test_คำถามกลับขึ้นต้นด้วยคำนำเดิมของคำถามต่อยอด(self):
        self.assertTrue(chat._NO_PREFERENCE_REPLY.startswith(chat._FOLLOW_UP_LEAD))

    def test_ไม่เก็บคำถามกลับลงแคช(self):
        self.assertFalse(self.ask("เรียนไรดี", "").cacheable)

    def test_สถานะแยกจากไม่ใช่การขอคำแนะนำ(self):
        """recommendation ยังเป็น true อยู่ แค่ยังไม่มีความสนใจ — ต้องไม่ถูกตีเป็น None"""
        conn = FakeConnector("")
        self.assertIs(chat._recommendation_intent(DB, conn, "เรียนไรดี"), chat.NO_PREFERENCE)
        not_recommendation = FakeConnector("", recommendation=False)
        self.assertIsNone(chat._recommendation_intent(DB, not_recommendation, "คณะมีสาขาอะไรบ้าง"))

    def test_ไม่ส่งข้อความทั้งประโยคไปจับคู่อีก(self):
        prepared = self.ask("เรียนไรดี", "")
        self.assertEqual(self.match_calls, [])
        self.assertNotIn("เรียนไรดี", prepared.canned)


class WithPreferenceChecks(_Base):
    def test_มีความสนใจยังจับคู่สาขาเหมือนเดิม(self):
        for message, interest in WITH_PREFERENCE:
            with self.subTest(message=message):
                self.match_calls.clear()
                prepared = self.ask(message, interest, matches=[match(COURSES[0])])
                self.assertEqual(len(self.match_calls), 1, f"ต้องเรียก match_programs กับ {message!r}")
                self.assertEqual(self.match_calls[0]["answers"], {"extra": interest})
                self.assertNotEqual(prepared.canned, chat._NO_PREFERENCE_REPLY)
                self.assertIn("วิทยาการคอมพิวเตอร์", prepared.canned)

    def test_ค่าที่ส่งให้การจัดอันดับไม่เปลี่ยน(self):
        """limit=3 และ relevant_only=True ต้องคงเดิม — รอบนี้ไม่แตะการจัดอันดับ"""
        self.ask("ชอบเขียนโปรแกรมควรเรียนสาขาไหน", "ชอบเขียนโปรแกรม", matches=[match(COURSES[0])])
        self.assertEqual(self.match_calls[0]["limit"], 3)
        self.assertTrue(self.match_calls[0]["relevant_only"])
        self.assertIsNone(self.match_calls[0]["profile_text"])

    def test_ความสนใจที่โมเดลเรียบเรียงใหม่ยังใช้ข้อความเดิม(self):
        """พฤติกรรมเดิม: interest ที่ไม่ได้อยู่ในข้อความเดิมถูกแทนด้วยทั้งประโยค ไม่ใช่ถามกลับ"""
        self.ask("ชอบเขียนโปรแกรมควรเรียนสาขาไหน", "สนใจงานพัฒนาซอฟต์แวร์", matches=[match(COURSES[0])])
        self.assertEqual(self.match_calls[0]["answers"], {"extra": "ชอบเขียนโปรแกรมควรเรียนสาขาไหน"})


class FollowUpChecks(_Base):
    def test_ตอบความสนใจหลังถูกถามกลับแล้วได้คำแนะนำจริง(self):
        """เทิร์นถัดไปต้องเข้าเส้นทางคำตอบต่อยอดเดิม โดยรวมคำถามแรกกับคำตอบใหม่"""
        prepared = self.ask(
            "ชอบเขียนโปรแกรม", "",
            ("user", "เรียนไรดี"), ("assistant", chat._NO_PREFERENCE_REPLY),
            matches=[match(COURSES[0])],
        )
        self.assertEqual(len(self.match_calls), 1)
        self.assertEqual(self.match_calls[0]["answers"], {"extra": "เรียนไรดี ชอบเขียนโปรแกรม"})
        self.assertEqual(self.match_calls[0]["profile_text"], "เรียนไรดี ชอบเขียนโปรแกรม")
        self.assertNotEqual(prepared.canned, chat._NO_PREFERENCE_REPLY)
        self.assertIn("วิทยาการคอมพิวเตอร์", prepared.canned)

    def test_ตอบว่าไม่รู้ต่อจากคำถามกลับยังไปทางคำตอบต่อยอดเหมือนเดิม(self):
        """
        ตรึงพฤติกรรมที่ยังไม่ได้แก้ในรอบนี้ไว้ให้เห็นชัด

        เส้นทางคำตอบต่อยอด (_refinement_of_recommendation) ตัดสินก่อนขั้นจำแนกเจตนา และรวมคำถามเดิม
        กับคำตอบใหม่เสมอ ด่านถามกลับรอบนี้จึงไม่ครอบคลุมกรณีที่ผู้ใช้ตอบว่า "ไม่รู้" ต่อจากคำถามกลับ
        ซึ่งยังถูกนำไปจับคู่ด้วยข้อความที่ไม่มีความสนใจ — บันทึกเป็นข้อจำกัดใน
        docs/CHAT_RECOMMENDATION_CLARIFICATION_FIX.md ถ้าจะแก้ต้องเป็นรอบแยกที่มีการอนุมัติ
        """
        self.ask(
            "ไม่รู้", "",
            ("user", "เรียนไรดี"), ("assistant", chat._NO_PREFERENCE_REPLY),
        )
        self.assertEqual(len(self.match_calls), 1)
        self.assertEqual(self.match_calls[0]["answers"], {"extra": "เรียนไรดี ไม่รู้"})


class NonRecommendationChecks(_Base):
    def test_คำถามรายชื่อสาขาไม่โดนด่านนี้(self):
        with mock.patch.object(chat, "program_list_answer", return_value="รายชื่อสาขา..."):
            prepared = self.ask("คณะมีสาขาอะไรบ้าง", "")
        self.assertEqual(prepared.canned, "รายชื่อสาขา...")
        self.assertEqual(self.match_calls, [])

    def test_คำถามค่าเทอมไม่โดนด่านนี้(self):
        prepared = self.ask("ค่าเทอมสาขาวิทยาการคอมพิวเตอร์เท่าไร", "")
        self.assertNotEqual(prepared.canned, chat._NO_PREFERENCE_REPLY)
        self.assertEqual(self.match_calls, [])

    def test_คำถามข้อเท็จจริงของสาขาไม่โดนด่านนี้(self):
        """ด่านที่ไม่ใช้โมเดลตัดสินก่อนอยู่แล้ว จึงต้องไม่เรียกโมเดลและไม่ถามกลับ"""
        conn = FakeConnector("")
        for message in ("หลักสูตรคณิตศาสตร์เรียนกี่หน่วยกิต",
                        "สาขาวิทยาการคอมพิวเตอร์จบไปทำอาชีพอะไรได้บ้าง"):
            with self.subTest(message=message):
                self.assertIsNone(chat._recommendation_intent(DB, conn, message))
        self.assertEqual(conn.calls, 0)


class NoKeywordListChecks(unittest.TestCase):
    def test_ด่านถามกลับไม่ได้ใช้รายการคำ(self):
        """กันไม่ให้ด่านนี้กลายเป็นรายการประโยค ซึ่งไม่มีวันครบ"""
        import ast
        import inspect
        import textwrap

        # เทียบเฉพาะโค้ดที่ทำงานจริง — คอมเมนต์และ docstring อ้างถึงตัวอย่างคำถามได้ตามปกติ
        code = []
        for fn in (chat._recommendation_intent, chat.prepare_answer):
            tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
                    body = node.body
                    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                            and isinstance(body[0].value.value, str):
                        node.body = body[1:] or [ast.Pass()]
            code.append(ast.unparse(tree))
        executable = "\n".join(code)
        for phrase in NO_PREFERENCE_MESSAGES:
            self.assertNotIn(phrase, executable)


if __name__ == "__main__":
    unittest.main()
