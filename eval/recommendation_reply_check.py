"""
ตรวจว่า _recommendation_reply แยก "ขั้นเขียนเหตุผลล้ม" ออกจาก "เอกสารไม่รองรับ"

ทำไมต้องเป็นการทดสอบแบบไม่เรียกเซิร์ฟเวอร์
------------------------------------------
อาการที่ทำให้ต้องมีไฟล์นี้เกิดเป็นครั้งคราว ไม่ใช่ทุกครั้ง — ขั้นเขียนเหตุผลเรียกโมเดล
หนึ่งครั้งแล้วอ่านผลเป็น JSON ซึ่งบางรอบตอบไม่ครบหรือคีย์ไม่ตรง การถามผ่านเว็บซ้ำๆ
เพื่อให้เจอจึงทั้งเปลืองโควตาและไม่รับประกันว่าจะเจอ ทดสอบตรงที่ตรรกะจึงเป็นวิธีเดียว
ที่ยืนยันได้ทุกครั้ง

กรณีที่ทำให้เกิดข้อผิดพลาดจริง
-----------------------------
ชุดตรวจพฤติกรรมถาม "สาขาไหนเหมาะกับคนชอบทำงานกับคอมพิวเตอร์" แล้วได้คำตอบว่าไม่พบ
สาขาที่ตรงกับความสนใจ ทั้งที่ตามรอยการจัดอันดับแล้วอันดับ 1-3 คือวิทยาการคอมพิวเตอร์
คอมพิวเตอร์แอนิเมชันและมัลติมีเดีย และเทคโนโลยีสารสนเทศ ตามลำดับ

สาเหตุคือด่านเดิมจับเฉพาะกรณีที่เหตุผล "ว่างทั้งหมด" กรณีผสม (บางรายการว่างเพราะขั้น
เขียนเหตุผลล้ม ที่เหลือติดเครื่องหมายไม่มีหลักฐาน) จึงหลุดไปเจอข้อความปฏิเสธ ซึ่งบอก
ผู้ใช้ว่าคณะไม่มีสาขาที่ตรงกับความสนใจของเขา ทั้งที่ระบบไม่เคยดูเอกสารของรายการที่ว่าง
เลยสักครั้ง — เป็นการรายงานความล้มเหลวของระบบเป็นข้อเท็จจริงของคณะ

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


@dataclass
class FakeMatch:
    title: str
    rationale: str


class RecommendationReplyChecks(unittest.TestCase):
    """
    เรียก _recommendation_reply โดยแทนที่ match_programs ด้วยผลที่กำหนดเอง

    ตัวฟังก์ชันนำเข้า match_programs ไว้ในตัวมันเอง (import ภายในฟังก์ชัน) จึงแทนที่ได้
    ด้วยการใส่มอดูลปลอมไว้ใน sys.modules ก่อนเรียก ไม่ต้องต่อฐานข้อมูลหรือเรียกโมเดล
    """

    def reply_for(self, matches: list[FakeMatch]) -> str | None:
        import app.services.chat as chat

        fake = types.ModuleType("app.services.program_match")
        fake.match_programs = lambda db, answers, limit=3, relevant_only=False: matches
        fake.confidence_of = lambda ms: "high"
        real = sys.modules.get("app.services.program_match")
        sys.modules["app.services.program_match"] = fake
        try:
            return chat._recommendation_reply(None, "สาขาไหนเหมาะกับคนชอบทำงานกับคอมพิวเตอร์")
        finally:
            if real is not None:
                sys.modules["app.services.program_match"] = real
            else:
                del sys.modules["app.services.program_match"]

    def test_รายการที่อธิบายได้ถูกแสดง(self):
        reply = self.reply_for([
            FakeMatch("หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาการคอมพิวเตอร์ (พ.ศ. 2566)", "เน้นการพัฒนาซอฟต์แวร์"),
            FakeMatch("หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาเทคโนโลยีสารสนเทศ (พ.ศ. 2566)", "เน้นระบบสารสนเทศ"),
        ])
        self.assertIn("วิทยาการคอมพิวเตอร์", reply)
        self.assertIn("เทคโนโลยีสารสนเทศ", reply)
        self.assertNotIn("ยังไม่พบสาขา", reply)

    def test_เหตุผลว่างทั้งหมดต้องคงอันดับไว้(self):
        """ขั้นเขียนเหตุผลล้มทั้งชุด — การจัดอันดับไม่ได้พึ่งขั้นนี้ จึงต้องยังแสดงผล"""
        reply = self.reply_for([
            FakeMatch("หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาการคอมพิวเตอร์ (พ.ศ. 2566)", ""),
            FakeMatch("หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาเทคโนโลยีสารสนเทศ (พ.ศ. 2566)", ""),
        ])
        self.assertIn("วิทยาการคอมพิวเตอร์", reply)
        self.assertIn("ยังเขียนคำอธิบายประกอบให้ไม่ได้", reply)
        self.assertNotIn("ยังไม่พบสาขา", reply)

    def test_กรณีผสมต้องไม่บอกว่าไม่พบสาขา(self):
        """
        นี่คือกรณีที่พลาดจริง — บางรายการว่าง (ขั้นเขียนเหตุผลล้ม) ที่เหลือติดเครื่องหมาย
        ไม่มีหลักฐาน ระบบยังไม่ได้ดูเอกสารของรายการที่ว่าง จึงสรุปว่าไม่มีสาขาที่ตรงไม่ได้
        """
        reply = self.reply_for([
            FakeMatch("หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาการคอมพิวเตอร์ (พ.ศ. 2566)", ""),
            FakeMatch("หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาคอมพิวเตอร์แอนิเมชันและมัลติมีเดีย (พ.ศ. 2566)",
                      NO_EVIDENCE_MARKER),
            FakeMatch("หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาเทคโนโลยีสารสนเทศ (พ.ศ. 2566)", ""),
        ])
        self.assertNotIn("ยังไม่พบสาขา", reply)
        self.assertIn("วิทยาการคอมพิวเตอร์", reply)
        self.assertIn("ยังเขียนคำอธิบายประกอบให้ไม่ได้", reply)

    def test_ไม่มีหลักฐานทุกรายการจึงปฏิเสธได้(self):
        """
        ทุกรายการถูกตรวจแล้วและไม่มีหลักฐานรองรับ — อันนี้เป็นคำตอบจริง ไม่ใช่ความล้มเหลว
        จึงต้องยังปฏิเสธได้ ไม่ใช่แก้จนกลายเป็นแนะนำทุกอย่างเสมอ
        """
        reply = self.reply_for([
            FakeMatch("หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาคณิตศาสตร์ (พ.ศ. 2564)", NO_EVIDENCE_MARKER),
            FakeMatch("หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาศาสตร์เครื่องสำอาง (พ.ศ. 2566)", NO_EVIDENCE_MARKER),
        ])
        self.assertIn("ยังไม่พบสาขา", reply)

    def test_ไม่มีผลการจัดอันดับต้องคืนค่าว่าง(self):
        self.assertIsNone(self.reply_for([]))


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
        """
        "โครงสร้างหลักสูตรของสาขาวิชา X" จับคำว่าหลักสูตรได้ก่อน ที่เหลือจึงเป็น
        "ของสาขาวิชา X" ทั้งดุ้น เคยได้คำตอบว่า "ไม่มีสาขาของสาขาวิชาคอมพิวเตอร์ธุรกิจ"
        """
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
