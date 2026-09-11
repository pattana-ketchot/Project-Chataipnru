"""
ตรวจตรรกะการตอบคำแนะนำสาขา โดยไม่เรียกเซิร์ฟเวอร์และไม่เรียกโมเดล

ทำไมต้องเป็นการทดสอบแบบไม่เรียกเซิร์ฟเวอร์
------------------------------------------
อาการที่ไฟล์นี้ตรวจเกิดเป็นครั้งคราว ไม่ใช่ทุกครั้ง — ขั้นเขียนเหตุผลเรียกโมเดลหนึ่งครั้ง
แล้วอ่านผลเป็น JSON ซึ่งบางรอบตอบไม่ครบหรือคีย์ไม่ตรง การถามผ่านเว็บซ้ำๆ เพื่อให้เจอ
จึงทั้งเปลืองโควตาและไม่รับประกันว่าจะเจอ ทดสอบตรงที่ตรรกะจึงเป็นวิธีเดียวที่ยืนยันได้
ทุกครั้ง

กรณีที่ทำให้เกิดข้อผิดพลาดจริง
-----------------------------
1. ชุดตรวจพฤติกรรมถาม "สาขาไหนเหมาะกับคนชอบทำงานกับคอมพิวเตอร์" แล้วได้คำตอบว่าไม่พบ
   สาขาที่ตรงกับความสนใจ ทั้งที่อันดับ 1-3 ถูกต้อง เพราะเหมา "ขั้นเขียนเหตุผลล้ม" กับ
   "เอกสารไม่รองรับ" เป็นเรื่องเดียวกัน

2. ผู้ตรวจอีกคนทักว่าประโยค "สาขาที่ใกล้เคียงที่สุด" สรุปแรงเกินข้อมูลประโยคเดียว และ
   ควรถามต่อ แต่ถ้าถามต่อได้แล้วเอาคำตอบไปใช้ไม่ได้ จะแย่กว่าไม่ถาม — วัดจากระบบจริง
   ผู้ใช้ตอบว่า "ชอบเขียนโปรแกรมมากกว่า" แล้วได้คำตอบว่าไม่พบข้อมูลในเอกสาร

3. หลังเพิ่มการจับคู่ใหม่จากคำตอบต่อยอด ผู้ใช้ที่ตอบว่า "ไม่แน่ใจครับ" ได้คำตอบว่าไม่พบ
   สาขาที่ตรงกับความสนใจ ขัดกับสองสาขาที่เพิ่งแนะนำไปในเทิร์นก่อน

    python -m eval.recommendation_reply_check
"""
from __future__ import annotations

import sys
import types
import unittest
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from llm.prompts import NO_EVIDENCE_MARKER  # noqa: E402

# ชื่อหลักสูตรที่ใช้แทนการอ่านจากฐานข้อมูล
PROGRAM_NAMES = ["คณิตศาสตร์", "คอมพิวเตอร์แอนิเมชันและมัลติมีเดีย", "วิทยาการคอมพิวเตอร์", "เทคโนโลยีสารสนเทศ"]

CS = "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาการคอมพิวเตอร์ (พ.ศ. 2566)"
IT = "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาเทคโนโลยีสารสนเทศ (พ.ศ. 2566)"
ANIM = "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาคอมพิวเตอร์แอนิเมชันและมัลติมีเดีย (พ.ศ. 2566)"
MATH = "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาคณิตศาสตร์ (พ.ศ. 2564)"


@dataclass
class FakeMatch:
    title: str
    rationale: str
    course_id: str = "x"


class _WithProgramNames(unittest.TestCase):
    def setUp(self):
        import app.services.chat as chat
        self._saved = chat._PROGRAM_NAMES
        chat._PROGRAM_NAMES = PROGRAM_NAMES

    def tearDown(self):
        import app.services.chat as chat
        chat._PROGRAM_NAMES = self._saved


class RecommendationReplyChecks(_WithProgramNames):
    """
    เรียก _recommendation_reply โดยแทนที่ program_match ด้วยผลที่กำหนดเอง

    ตัวฟังก์ชันนำเข้า program_match ไว้ในตัวมันเอง (import ภายในฟังก์ชัน) จึงแทนที่ได้
    ด้วยการใส่มอดูลปลอมไว้ใน sys.modules ก่อนเรียก ไม่ต้องต่อฐานข้อมูลหรือเรียกโมเดล
    """

    def reply_for(self, matches, refinement=False, confidence="high"):
        import app.services.chat as chat

        self.match_calls = []

        def fake_match(db, answers, limit=3, relevant_only=False, profile_text=None):
            self.match_calls.append({"answers": answers, "profile_text": profile_text})
            return matches

        fake = types.ModuleType("app.services.program_match")
        fake.match_programs = fake_match
        fake.confidence_of = lambda ms: confidence
        real = sys.modules.get("app.services.program_match")
        sys.modules["app.services.program_match"] = fake
        try:
            return chat._recommendation_reply(
                None, "สาขาไหนเหมาะกับคนชอบทำงานกับคอมพิวเตอร์", refinement=refinement
            )
        finally:
            if real is not None:
                sys.modules["app.services.program_match"] = real
            else:
                del sys.modules["app.services.program_match"]

    # --- ขั้นเขียนเหตุผลล้ม กับ เอกสารไม่รองรับ ---

    def test_รายการที่อธิบายได้ถูกแสดง(self):
        reply = self.reply_for([FakeMatch(CS, "เน้นการพัฒนาซอฟต์แวร์"), FakeMatch(IT, "เน้นระบบสารสนเทศ")])
        self.assertIn("วิทยาการคอมพิวเตอร์", reply)
        self.assertIn("เทคโนโลยีสารสนเทศ", reply)
        self.assertNotIn("ยังไม่พบสาขา", reply)

    def test_เหตุผลว่างทั้งหมดต้องคงอันดับไว้(self):
        """ขั้นเขียนเหตุผลล้มทั้งชุด — การจัดอันดับไม่ได้พึ่งขั้นนี้ จึงต้องยังแสดงผล"""
        reply = self.reply_for([FakeMatch(CS, ""), FakeMatch(IT, "")])
        self.assertIn("วิทยาการคอมพิวเตอร์", reply)
        self.assertIn("ยังเขียนคำอธิบายประกอบให้ไม่ได้", reply)
        self.assertNotIn("ยังไม่พบสาขา", reply)

    def test_กรณีผสมต้องไม่บอกว่าไม่พบสาขา(self):
        """บางรายการว่าง ที่เหลือไม่มีหลักฐาน ระบบยังไม่ได้ดูเอกสารของรายการที่ว่าง"""
        reply = self.reply_for([FakeMatch(CS, ""), FakeMatch(ANIM, NO_EVIDENCE_MARKER), FakeMatch(IT, "")])
        self.assertNotIn("ยังไม่พบสาขา", reply)
        self.assertIn("วิทยาการคอมพิวเตอร์", reply)
        self.assertIn("ยังเขียนคำอธิบายประกอบให้ไม่ได้", reply)

    def test_ไม่มีหลักฐานทุกรายการจึงปฏิเสธได้(self):
        """ทุกรายการถูกตรวจแล้วและไม่มีหลักฐาน — เป็นคำตอบจริง ต้องยังปฏิเสธได้"""
        reply = self.reply_for([FakeMatch(MATH, NO_EVIDENCE_MARKER), FakeMatch(ANIM, NO_EVIDENCE_MARKER)])
        self.assertIn("ยังไม่พบสาขา", reply)

    def test_ไม่มีผลการจัดอันดับต้องคืนค่าว่าง(self):
        self.assertIsNone(self.reply_for([]))

    # --- ประโยคนำและคำถามต่อยอด ---

    def test_ประโยคนำไม่สรุปแรงเกินข้อมูล(self):
        two = self.reply_for([FakeMatch(CS, "เน้นซอฟต์แวร์"), FakeMatch(IT, "เน้นระบบสารสนเทศ")])
        one = self.reply_for([FakeMatch(MATH, "เน้นการคำนวณ")])
        self.assertNotIn("ใกล้เคียงที่สุด", two)
        self.assertNotIn("ใกล้เคียงที่สุด", one)
        self.assertTrue(two.splitlines()[0].endswith("ได้แก่"))
        self.assertTrue(one.splitlines()[0].endswith("คือ"))

    def test_แนะนำหลายสาขาต้องถามต่อท้ายคำตอบ(self):
        import app.services.chat as chat
        reply = self.reply_for([FakeMatch(CS, "เน้นซอฟต์แวร์"), FakeMatch(IT, "เน้นระบบสารสนเทศ")])
        self.assertEqual(reply.splitlines()[-1], f"{chat._FOLLOW_UP_LEAD} {chat._FOLLOW_UP_QUESTION}")

    def test_สาขาเดียวก็ถามต่อและไม่บอกว่าหลายสาขาใกล้เคียง(self):
        """
        เดิมขึ้นประโยค 'หลายสาขาใกล้เคียงกันมาก' ใต้รายการที่มีสาขาเดียว และไม่ถามต่อเลย ผู้ตรวจ
        ทักว่า "ชอบทำงานด้านบริการ" ได้สาขาอาหารสาขาเดียวแล้วจบ ผู้ใช้อาจเข้าใจว่างานบริการคือ
        งานอาหาร ทั้งที่ไม่ได้บอกเลยว่าชอบอาหาร
        """
        import app.services.chat as chat
        reply = self.reply_for([FakeMatch(MATH, "เน้นการคำนวณ")], confidence="low")
        self.assertEqual(reply.splitlines()[-1], f"{chat._FOLLOW_UP_LEAD} {chat._FOLLOW_UP_QUESTION_SINGLE}")
        self.assertNotIn("ใกล้เคียงกันมาก", reply)

    def test_รอบที่ตอบกลับมาแล้วไม่ถามซ้ำ(self):
        """ถามซ้ำทุกรอบ ผู้ใช้ที่ตอบว่าไม่แน่ใจจะวนอยู่กับคำถามเดิมไม่รู้จบ"""
        import app.services.chat as chat
        reply = self.reply_for(
            [FakeMatch(CS, "เน้นซอฟต์แวร์"), FakeMatch(IT, "เน้นระบบสารสนเทศ")],
            refinement=True, confidence="low",
        )
        self.assertNotIn(chat._FOLLOW_UP_LEAD, reply)
        self.assertTrue(reply.startswith("เมื่อรวมกับที่บอกเพิ่มมา"))
        self.assertIn("ใกล้เคียงกันมาก", reply)

    def test_ตอบว่าไม่แน่ใจต้องไม่ขัดกับคำแนะนำรอบก่อน(self):
        """
        เจอจากหน้าเว็บจริง: ตอบคำถามต่อยอดว่า "ไม่แน่ใจครับ" แล้วได้ "ยังไม่พบสาขาที่ตรงกับ
        ความสนใจ" ทั้งที่เทิร์นก่อนเพิ่งแนะนำไปสองสาขา
        """
        reply = self.reply_for(
            [FakeMatch(CS, NO_EVIDENCE_MARKER), FakeMatch(IT, NO_EVIDENCE_MARKER)], refinement=True,
        )
        self.assertNotIn("ยังไม่พบสาขา", reply)
        self.assertIn("ยังหาสาขาที่ตรงกว่าเดิมไม่ได้", reply)
        self.assertIn("แนะนำไปก่อนหน้านี้", reply)

    def test_รอบต่อยอดส่งข้อความเต็มให้ขั้นเขียนเหตุผล(self):
        """
        คำตอบต่อยอดอย่าง "ชอบเขียนโปรแกรมมากกว่า" อ่านรู้เรื่องเมื่อเห็นคำถามเดิมด้วย วัดแล้ว
        ส่งเฉพาะความสนใจทำให้ปฏิเสธทุกสาขา 12/12 รอบ ส่วนข้อความเต็ม 4/12
        """
        self.reply_for([FakeMatch(CS, "เน้นซอฟต์แวร์")], refinement=True)
        self.assertEqual(self.match_calls[-1]["profile_text"], "สาขาไหนเหมาะกับคนชอบทำงานกับคอมพิวเตอร์")

    def test_คำถามแรกให้ขั้นเขียนเหตุผลใช้เฉพาะความสนใจ(self):
        """คำถามแรกส่งทั้งประโยคทำให้ปฏิเสธทุกสาขา 6/30 รอบ ส่วนเฉพาะความสนใจ 0/30"""
        self.reply_for([FakeMatch(CS, "เน้นซอฟต์แวร์")])
        self.assertIsNone(self.match_calls[-1]["profile_text"])


class RationaleTemperatureChecks(unittest.TestCase):
    """
    ขั้นเขียนเหตุผลต้องเรียกโมเดลที่ temperature 0

    ขั้นนี้เป็นตัวตัดสินว่าสาขาไหนมีหลักฐานรองรับ ไม่ได้แค่เรียบเรียงคำ วัดโดยตรึงทุกอย่างก่อน
    หน้าไว้: temperature 0.2 ปฏิเสธทุกสาขา 1/12 รอบ ส่วน temperature 0 ได้ 0/12 และไม่ปล่อย
    สาขาที่ไม่เกี่ยวข้องผ่านแบบสุ่มๆ

    แต่ temperature 0 อย่างเดียวไม่ได้แก้อาการ "ยังไม่พบสาขา" ที่ผู้ใช้เจอ (ยังเกิด 1/20 รอบ
    ผ่านเว็บจริง) ต้นเหตุจริงอยู่ที่ข้อความที่ส่งเข้าขั้นนี้ ดู InterestExtractionChecks

    ตรวจแบบไม่เรียกโมเดล เพราะอาการเกิดราวหนึ่งในสิบรอบ การถามระบบจริงไม่กี่ครั้งจับไม่ได้
    """

    def test_ขั้นเขียนเหตุผลใช้temperatureศูนย์(self):
        from app.services.program_match import _generate_rationales

        seen = {}

        class FakeConnector:
            answer_token_cap = 2048

            def chat(self, messages, **kwargs):
                seen.update(kwargs)
                return '{"rationales": {}}'

        _generate_rationales(FakeConnector(), "ชอบทำงานกับคอมพิวเตอร์", [{"title": CS, "excerpt": "เนื้อหา"}])
        self.assertEqual(seen.get("temperature"), 0.0)


class InterestExtractionChecks(unittest.TestCase):
    """
    ขั้นจัดอันดับกับขั้นเขียนเหตุผลต้องได้ความสนใจชุดเดียวกัน ไม่ใช่คำถามทั้งประโยค

    ผู้ใช้จริงได้คำตอบว่า "ยังไม่พบสาขา" กับ "สาขาไหนเหมาะกับคนชอบทำงานกับคอมพิวเตอร์" เพราะ
    ขั้นเขียนเหตุผลได้คำถามทั้งประโยคไปในฐานะคำตอบแบบสอบถามของนักเรียน วัดโดยตรึงอันดับกับ
    หลักฐานไว้: ส่งทั้งประโยคถูกปฏิเสธทุกสาขา 6/30 รอบ ส่งเฉพาะความสนใจ 0/30 รอบ
    """

    Q = "สาขาไหนเหมาะกับคนชอบทำงานกับคอมพิวเตอร์"

    def test_ขั้นเขียนเหตุผลได้เฉพาะความสนใจ(self):
        from app.services.program_match import build_profile_text
        self.assertEqual(build_profile_text({"extra": self.Q}), "ชอบทำงานกับคอมพิวเตอร์")

    def test_พรอมต์เขียนเหตุผลไม่มีคำขอเลือกสาขา(self):
        from app.services.program_match import build_match_rationale_prompt, build_profile_text
        prompt = build_match_rationale_prompt(build_profile_text({"extra": self.Q}), [])
        self.assertNotIn("สาขาไหนเหมาะกับ", prompt)
        self.assertIn("ชอบทำงานกับคอมพิวเตอร์", prompt)

    def test_จัดอันดับกับเขียนเหตุผลได้ข้อความเดียวกัน(self):
        """เดิมสองขั้นได้ข้อความต่างกันโดยตั้งใจ ซึ่งเป็นต้นเหตุของอาการ"""
        from app.services.program_match import build_match_query, build_profile_text
        for q in (self.Q, f"{self.Q} ชอบเขียนโปรแกรมมากกว่า", "ชอบวาดรูปและออกแบบ"):
            self.assertEqual(build_profile_text({"extra": q}), build_match_query({"extra": q}))

    def test_คำตอบต่อยอดตัดเฉพาะคำขอข้างหน้า(self):
        from app.services.program_match import build_profile_text
        self.assertEqual(
            build_profile_text({"extra": f"{self.Q} ชอบเขียนโปรแกรมมากกว่า"}),
            "ชอบทำงานกับคอมพิวเตอร์ ชอบเขียนโปรแกรมมากกว่า",
        )

    def test_ข้อความที่มีแต่คำขอไม่กลายเป็นค่าว่าง(self):
        from app.services.program_match import build_profile_text
        self.assertEqual(build_profile_text({"extra": "สาขาไหนเหมาะกับคน"}), "สาขาไหนเหมาะกับคน")


class RefinementDetectionChecks(_WithProgramNames):
    """ข้อความของผู้ใช้เป็นคำตอบของคำถามต่อยอด หรือเป็นคำถามใหม่"""

    FIRST = "สาขาไหนเหมาะกับคนชอบทำงานกับคอมพิวเตอร์"

    def history(self, assistant_text):
        from app.services.chat import PriorTurn
        return [PriorTurn("user", self.FIRST), PriorTurn("assistant", assistant_text)]

    def refine(self, history, message):
        from app.services.chat import _refinement_of_recommendation
        return _refinement_of_recommendation(None, history, message)

    def asked_reply(self):
        from app.services.chat import _FOLLOW_UP_LEAD, _FOLLOW_UP_QUESTION
        return (
            "จากความสนใจที่บอกมา สาขาในคณะที่เกี่ยวข้อง ได้แก่\n1. วิทยาการคอมพิวเตอร์\n"
            f"2. เทคโนโลยีสารสนเทศ\n\n{_FOLLOW_UP_LEAD} {_FOLLOW_UP_QUESTION}"
        )

    def test_คำตอบของคำถามต่อยอดรวมกับความสนใจเดิม(self):
        """อาการเดิม: ตอบว่า 'ชอบเขียนโปรแกรมมากกว่า' แล้วได้ 'ไม่พบข้อมูลในเอกสาร'"""
        got = self.refine(self.history(self.asked_reply()), "ชอบเขียนโปรแกรมมากกว่า")
        self.assertEqual(got, f"{self.FIRST} ชอบเขียนโปรแกรมมากกว่า")

    def test_ไม่ได้ถามต่อไว้ไม่ถือเป็นคำตอบต่อยอด(self):
        self.assertIsNone(self.refine(self.history("หลักสูตรนี้เรียน 130 หน่วยกิต"), "ชอบเขียนโปรแกรม"))

    def test_เอ่ยชื่อสาขาคือคำถามใหม่(self):
        self.assertIsNone(self.refine(self.history(self.asked_reply()), "วิทยาการคอมพิวเตอร์ต่างจากที่อื่นยังไง"))

    def test_ถามข้อเท็จจริงคือคำถามใหม่(self):
        self.assertIsNone(self.refine(self.history(self.asked_reply()), "แล้วต้องเรียนกี่ปี"))

    def test_ไม่มีบทสนทนาก่อนหน้า(self):
        self.assertIsNone(self.refine([], "ชอบเขียนโปรแกรม"))


class UnknownProgramNameChecks(unittest.TestCase):
    """
    ชื่อที่ตัดมาต้องต่อท้าย "คณะ...ไม่มีสาขา" แล้วอ่านรู้เรื่อง

    ภาษาไทยไม่เว้นวรรคระหว่างคำ การตัดชื่อจึงพลาดได้หลายแบบ และทุกแบบหลุดไปถึงผู้ใช้
    เป็นประโยคที่อ่านแล้วสะดุด ชุดตรวจในไฟล์นี้เก็บรูปประโยคที่เคยพลาดจริงไว้
    """

    def trim(self, message: str) -> str:
        from app.services.chat import _NAMES_SOMETHING, _trim_program_name
        m = _NAMES_SOMETHING.search(message)
        self.assertIsNotNone(m, f"จับชื่อสาขาจาก {message!r} ไม่ได้")
        return _trim_program_name(m.group(1))

    def test_ตัดคำถามท้ายชื่อออก(self):
        self.assertEqual(self.trim("สาขาคอมพิวเตอร์ธุรกิจเรียนกี่หน่วยกิต"), "คอมพิวเตอร์ธุรกิจ")

    def test_ตัดคำนำหน้าที่ซ้อนกัน(self):
        """เคยได้คำตอบว่า 'ไม่มีสาขาของสาขาวิชาคอมพิวเตอร์ธุรกิจ'"""
        self.assertEqual(
            self.trim("โครงสร้างหลักสูตรของสาขาวิชาคอมพิวเตอร์ธุรกิจ ต้องเรียนทั้งหมดกี่หน่วยกิต"),
            "คอมพิวเตอร์ธุรกิจ",
        )

    def test_ชื่อที่ไม่มีคำนำหน้าต้องไม่ถูกแตะ(self):
        self.assertEqual(self.trim("สาขาวิชาการตลาดดิจิทัลจบแล้วทำงานอะไร"), "การตลาดดิจิทัล")

    def test_ไม่ปอกจนเหลือค่าว่าง(self):
        """ปอกคำนำหน้าได้ต่อเมื่อยังเหลือชื่อจริง ไม่งั้นจะได้ประโยค 'ไม่มีสาขา' ลอยๆ"""
        from app.services.chat import _trim_program_name
        for lone in ("สาขาวิชา", "หลักสูตร", "ของ"):
            self.assertEqual(_trim_program_name(lone), lone)


if __name__ == "__main__":
    unittest.main(verbosity=2)
