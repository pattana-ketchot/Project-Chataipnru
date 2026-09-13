"""
ตรวจการตัดสินว่าข้อความเป็น "การขอคำแนะนำว่าจะเรียนสาขาไหนจากความสนใจ" หรือไม่

เหตุที่ต้องมี: เดิมตัดสินด้วยรายการคำ ข้อความเล่าความสนใจที่นักเรียนพิมพ์จริง เช่น
"สนใจสุขภาพและอยากทำงานช่วยคน" จึงไม่เข้าเส้นทางแนะนำเลย ไปทางค้นเอกสารแล้วได้ข้อมูลของ
สาขาเดียว (บางครั้งเป็นสาขาที่คณะเลิกเปิดแล้ว) หรือถูกปฏิเสธว่าถามนอกเรื่อง

ไฟล์นี้ตรวจส่วนที่ไม่ขึ้นกับโมเดล: ด่านที่ตัดสินได้เองโดยไม่เรียกโมเดล การอ่านผลของโมเดล และ
การนำความสนใจไปใช้ ความแม่นของโมเดลเองต้องวัดกับระบบจริงหลายรอบ (ดู eval/behaviour_check.py)

    python -m eval.recommend_intent_check
"""
from __future__ import annotations

import json
import sys
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

NAMES = [
    "คณิตศาสตร์",
    "คอมพิวเตอร์แอนิเมชันและมัลติมีเดีย",
    "วิทยาการคอมพิวเตอร์",
    "เทคโนโลยีสารสนเทศ",
    "การประกอบอาหารและการบริการอาหาร",
    "การแพทย์แผนไทยประยุกต์",
]


class FakeConnector:
    """คืนคำตอบที่กำหนด และนับว่าถูกเรียกกี่ครั้ง"""

    def __init__(self, reply=None, error=None):
        self.reply, self.error, self.calls = reply, error, 0

    def chat(self, messages, **kwargs):
        self.calls += 1
        if self.error:
            raise self.error
        return self.reply


def verdict(recommendation: bool, interest: str = "") -> str:
    return json.dumps({"recommendation": recommendation, "interest": interest}, ensure_ascii=False)


class _WithNames(unittest.TestCase):
    def setUp(self):
        import app.services.chat as chat
        self._saved = chat._PROGRAM_NAMES
        chat._PROGRAM_NAMES = NAMES

    def tearDown(self):
        import app.services.chat as chat
        chat._PROGRAM_NAMES = self._saved

    def intent(self, message, conn):
        from app.services.chat import _recommendation_intent
        return _recommendation_intent(None, conn, message)


class FactualQuestionGateChecks(_WithNames):
    """คำถามข้อเท็จจริงของสาขาที่ระบุชื่อ ต้องไม่ถูกตีเป็นการขอคำแนะนำ และไม่เรียกโมเดลเลย"""

    def test_ถามข้อเท็จจริงของสาขาที่ระบุไม่ใช่การขอคำแนะนำ(self):
        for message in (
            "คณิตศาสตร์เรียนกี่หน่วยกิต",
            "วิทยาการคอมพิวเตอร์มีวิชาอะไร",
            "แอนิเมชันเรียนอะไรบ้าง",
            "จบวิทคอมไปทำงานอะไรได้บ้าง",
            "การแพทย์แผนไทยประยุกต์เรียนกี่ปี",
        ):
            # ถ้าโมเดลถูกเรียก คำตอบปลอมนี้จะพาไปเส้นทางแนะนำ ซึ่งต้องไม่เกิด
            conn = FakeConnector(verdict(True, message))
            self.assertIsNone(self.intent(message, conn), message)
            self.assertEqual(conn.calls, 0, f"ไม่ควรเรียกโมเดลกับ {message!r}")

    def test_คำอ้างถึงสาขาที่คุยกันอยู่ไม่ใช่การขอคำแนะนำ(self):
        """อาชีพที่อยากเป็นในประโยคต้องไม่พาไปแนะนำสาขาใหม่ แล้วเสียบริบทของ "สาขานี้" """
        for message in ("ถ้าอยากเป็นนักพัฒนาเว็บ สาขานี้เหมาะไหม", "แล้วหลักสูตรนี้ล่ะ ชอบคำนวณจะไหวไหม"):
            conn = FakeConnector(verdict(True, message))
            self.assertIsNone(self.intent(message, conn), message)
            self.assertEqual(conn.calls, 0, f"ไม่ควรเรียกโมเดลกับ {message!r}")

    def test_เล่าความสนใจที่มีชื่อศาสตร์ปนยังให้โมเดลตัดสิน(self):
        """ชื่อสาขาอยู่ในความสนใจ แต่ไม่ได้ถามข้อเท็จจริง จึงต้องไม่ถูกตัดทิ้งก่อนถึงโมเดล"""
        conn = FakeConnector(verdict(True, "ชอบออกแบบ/ทำสื่อ/แอนิเมชัน"))
        self.assertEqual(self.intent("ชอบออกแบบ/ทำสื่อ/แอนิเมชัน", conn), "ชอบออกแบบ/ทำสื่อ/แอนิเมชัน")
        self.assertEqual(conn.calls, 1)


class VerdictReadingChecks(_WithNames):
    def test_ใช้ส่วนที่บอกความสนใจเมื่ออยู่ในข้อความเดิมจริง(self):
        message = "ผมยังไม่รู้ว่าจะเรียนอะไร แต่ชอบคำนวณและตัวเลข"
        conn = FakeConnector(verdict(True, "ชอบคำนวณและตัวเลข"))
        self.assertEqual(self.intent(message, conn), "ชอบคำนวณและตัวเลข")

    def test_ความสนใจที่ไม่ได้อยู่ในข้อความเดิมใช้ข้อความเดิมแทน(self):
        """โมเดลเรียบเรียงใหม่หรือเติมเอง ต้องไม่เอาถ้อยคำที่ผู้ใช้ไม่ได้พูดไปจับคู่สาขา"""
        message = "ชอบทำอาหารและงานบริการ ควรเรียนอะไร"
        conn = FakeConnector(verdict(True, "สนใจธุรกิจร้านอาหารระดับโลก"))
        self.assertEqual(self.intent(message, conn), message)

    def test_ช่องว่างต่างกันยังนับว่าอยู่ในข้อความเดิม(self):
        conn = FakeConnector(verdict(True, "ชอบเทคโนโลยี และระบบในองค์กร"))
        self.assertEqual(self.intent("ชอบเทคโนโลยีและระบบในองค์กร", conn), "ชอบเทคโนโลยี และระบบในองค์กร")

    def test_ความสนใจที่มีแค่ชื่อสาขาไม่ใช่การขอคำแนะนำ(self):
        """ผู้ใช้เลือกสาขาแล้ว วัดบนระบบจริงโมเดลตีว่าขอคำแนะนำ 1 ใน 2 รอบ โดยคัดมาได้แค่ชื่อสาขา"""
        for message, picked in (
            ("อยากเรียน วิทคอม", "วิทคอม"),
            ("สนใจสาขาเทคโนโลยีสารสนเทศ", "เทคโนโลยีสารสนเทศ"),
        ):
            self.assertIsNone(self.intent(message, FakeConnector(verdict(True, picked))), message)

    def test_ความสนใจที่มีชื่อศาสตร์แต่มีเนื้อหาอื่นยังเป็นการขอคำแนะนำ(self):
        conn = FakeConnector(verdict(True, "ชอบคณิตศาสตร์"))
        self.assertEqual(self.intent("ชอบคณิตศาสตร์ ควรเรียนอะไร", conn), "ชอบคณิตศาสตร์")

    def test_โมเดลบอกว่าไม่ใช่(self):
        self.assertIsNone(self.intent("คณะมีสาขาอะไรบ้าง", FakeConnector(verdict(False))))

    def test_ตัดสินไม่ได้ให้ถือว่าไม่ใช่(self):
        """การตอบว่าใช่คือการเปลี่ยนเส้นทางทั้งคำตอบ จึงห้ามปล่อยผ่านเมื่อตัดสินไม่ได้"""
        from llm.connector import LLMConnectionError
        self.assertIsNone(self.intent("สนใจสุขภาพ", FakeConnector("ไม่ใช่ JSON")))
        self.assertIsNone(self.intent("สนใจสุขภาพ", FakeConnector(error=LLMConnectionError("ล่ม"))))
        self.assertIsNone(self.intent("สนใจสุขภาพ", FakeConnector(json.dumps({"recommendation": "true"}))))


class InterestUsageChecks(unittest.TestCase):
    def test_ระบบจับคู่สาขาได้ความสนใจ_ไม่ใช่คำขอทั้งประโยค(self):
        """คำขอที่ปนไปกับความสนใจทำให้ขั้นเขียนเหตุผลปฏิเสธทุกสาขาได้ (วัดไว้ 6/30 รอบ)"""
        import app.services.chat as chat
        seen = {}

        def fake_match(db, answers, limit=3, relevant_only=False, profile_text=None):
            seen["answers"] = answers
            return []

        fake = types.ModuleType("app.services.program_match")
        fake.match_programs = fake_match
        fake.confidence_of = lambda ms: "high"
        real = sys.modules.get("app.services.program_match")
        sys.modules["app.services.program_match"] = fake
        try:
            chat._recommendation_reply(None, "ชอบทำอาหารและงานบริการ ควรเรียนอะไร", interest="ชอบทำอาหารและงานบริการ")
        finally:
            if real is not None:
                sys.modules["app.services.program_match"] = real
            else:
                del sys.modules["app.services.program_match"]
        self.assertEqual(seen["answers"], {"extra": "ชอบทำอาหารและงานบริการ"})


class NoKeywordListChecks(unittest.TestCase):
    def test_ไม่มีรายการคำตัดสินการขอคำแนะนำเหลืออยู่(self):
        """กันไม่ให้เส้นทางแนะนำกลับไปพึ่งรายการคำ ซึ่งไม่มีวันครบ"""
        import app.services.chat as chat
        self.assertFalse(hasattr(chat, "_RECOMMEND_WORDS"))
        self.assertFalse(hasattr(chat, "_asks_for_a_recommendation"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
