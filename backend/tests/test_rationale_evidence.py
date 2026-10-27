"""
เหตุผลของคำแนะนำต้องไม่อ้างเกินเอกสาร — ตรวจ quote อย่างเดียวไม่พอ

    cd backend && python tests/test_rationale_evidence.py

ที่มาของชุดนี้ — ข้อบกพร่องที่ตรวจพบจากรอบ 13: ชั้นตรวจเหตุผลตรวจเพียงว่า "ข้อความ
อ้างอิงมีอยู่ในเอกสารของหลักสูตรนั้นจริง" ซึ่งยืนยันได้แค่ว่าโมเดลไม่ได้แต่ง quote ขึ้นมา
แต่ไม่ได้ยืนยันว่า **ข้ออ้างในเหตุผล** มีหลักฐานรองรับ · โมเดลยก quote มาถูกหนึ่งประโยค
แล้วเติมตัวเลขหรือเงื่อนไขที่เอกสารไม่ได้เขียนไว้ได้ และผู้อ่านจะเข้าใจว่าเอกสารระบุไว้

เมื่อยืนยันเหตุผลไม่ได้ ระบบต้องไม่ทิ้งเหตุผลไปเงียบ ๆ แต่ต้องแสดงข้อความที่บอกชัดว่า
อันดับนี้มาจากความใกล้เคียงของเนื้อหา (การอนุมาน) ไม่ใช่ข้อความที่เอกสารกล่าวไว้

ชุดนี้ไม่ใช้ฐานข้อมูลและไม่เรียกโมเดล — ตั้งค่าแวดล้อมหลอกเพื่อให้ import ผ่านเท่านั้น
"""
import os
import sys
import unittest
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# ไม่ต่อฐานและไม่อ่านค่าจริง — app.config บังคับให้มีสองค่านี้ตอน import เท่านั้น
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://unused:unused@127.0.0.1:1/unused")
os.environ.setdefault("JWT_SECRET", "unused-in-this-test")

from app.services.chat import _RATIONALE_NO_EVIDENCE, _rationale_line  # noqa: E402
from app.services.program_match import _verified_rationales  # noqa: E402
from llm.prompts import NO_EVIDENCE_MARKER  # noqa: E402

CS = "วิทยาศาสตรบัณฑิต สาขาวิชาวิทยาการคอมพิวเตอร์ (พ.ศ. 2566)"
IT = "วิทยาศาสตรบัณฑิต สาขาวิชาเทคโนโลยีสารสนเทศ (พ.ศ. 2566)"

# ข้อความจริงจากเอกสารของสองหลักสูตร — วลี "ภาคทฤษฎีและปฏิบัติ" อยู่ในเล่มของ
# เทคโนโลยีสารสนเทศเท่านั้น ซึ่งเป็นการยืมข้ามหลักสูตรที่พบในข้อ a1-05
EVIDENCE = [
    {"title": CS, "excerpt": "หลักสูตรมุ่งผลิตบัณฑิตที่มีความรู้ด้านการเขียนโปรแกรม "
                             "การพัฒนาซอฟต์แวร์ และการจัดการข้อมูล จำนวนหน่วยกิตรวม"
                             "ตลอดหลักสูตรไม่น้อยกว่า 130 หน่วยกิต"},
    {"title": IT, "excerpt": "จัดการเรียนการสอนทั้งภาคทฤษฎีและปฏิบัติ เน้นการประยุกต์ใช้"
                             "เทคโนโลยีสารสนเทศในองค์กร"},
]


def one(reason: str, quote: str, key: str = CS) -> dict:
    return _verified_rationales({key: {"เหตุผล": reason, "ข้อความอ้างอิง": quote}}, EVIDENCE)


class RationaleEvidenceTests(unittest.TestCase):

    def test_quote_ถูก_และ_ข้ออ้างมีหลักฐาน_เก็บเหตุผลไว้(self):
        out = one("คุณบอกว่าชอบเขียนโค้ด สาขานี้เน้นการเขียนโปรแกรมและการพัฒนาซอฟต์แวร์ "
                  "เรียนรวมไม่น้อยกว่า 130 หน่วยกิต",
                  "การเขียนโปรแกรม การพัฒนาซอฟต์แวร์")
        self.assertIn("การเขียนโปรแกรม", out[CS])
        self.assertNotIn(NO_EVIDENCE_MARKER, out[CS])

    def test_quote_ถูก_แต่_reason_มีข้ออ้างที่หลักฐานไม่รองรับ(self):
        """กรณีที่ชั้นตรวจ quote อย่างเดียวปล่อยผ่าน — ตัวเลขที่เอกสารไม่ได้เขียนไว้"""
        out = one("สาขานี้เน้นการเขียนโปรแกรม เรียน 8 ภาคการศึกษา และมีทุนการศึกษา 40 ทุน",
                  "การเขียนโปรแกรม การพัฒนาซอฟต์แวร์")
        self.assertEqual(out[CS], NO_EVIDENCE_MARKER)

    def test_quote_ถูก_แต่_reason_อ้างระดับปริญญาผิด(self):
        out = one("สาขานี้เน้นการเขียนโปรแกรม เป็นหลักสูตรปริญญาโทที่ต่อยอดจากงานวิจัย",
                  "การเขียนโปรแกรม การพัฒนาซอฟต์แวร์")
        self.assertEqual(out[CS], NO_EVIDENCE_MARKER)

    def test_quote_มาจากเอกสารของหลักสูตรอื่น(self):
        """ข้อ a1-05: ยก "ภาคทฤษฎีและปฏิบัติ" ของเทคโนโลยีสารสนเทศมาใช้กับวิทยาการคอมพิวเตอร์"""
        out = one("สาขานี้สอนทั้งภาคทฤษฎีและปฏิบัติเพื่อพัฒนานวัตกรรมทางคอมพิวเตอร์",
                  "ภาคทฤษฎีและปฏิบัติ")
        self.assertEqual(out[CS], NO_EVIDENCE_MARKER)

    def test_เหตุผลไม่มี_quote(self):
        out = one("สาขานี้เหมาะกับคุณเพราะตรงกับความสนใจด้านคอมพิวเตอร์", "")
        self.assertEqual(out[CS], NO_EVIDENCE_MARKER)

    def test_สรุปความถูกต้องแม้ถ้อยคำต่างจากต้นฉบับ(self):
        """ไม่บังคับให้ลอก — เหตุผลที่สรุปความโดยไม่เติมข้ออ้างที่ตรวจไม่ได้ต้องผ่าน"""
        out = one("งานที่คุณชอบคือการสร้างโปรแกรม ซึ่งเป็นแกนของสาขานี้ตั้งแต่ต้น",
                  "การเขียนโปรแกรม การพัฒนาซอฟต์แวร์")
        self.assertNotIn(NO_EVIDENCE_MARKER, out[CS])

    def test_เหตุผลของหลักสูตรที่ไม่ได้ส่งหลักฐานไปถูกทิ้ง(self):
        out = one("สาขานี้เหมาะกับคุณ", "การเขียนโปรแกรม", key="สาขาที่ไม่ได้ส่งหลักฐาน")
        self.assertEqual(out, {})

    def test_ข้อความแทนต้องบอกว่าเป็นการอนุมาน_ไม่อ้างว่าเอกสารกล่าวไว้(self):
        line = _rationale_line(NO_EVIDENCE_MARKER)
        self.assertEqual(line, _RATIONALE_NO_EVIDENCE)
        self.assertIn("ไม่ได้ระบุไว้ตรงๆ", line)
        self.assertIn("ความใกล้เคียงของเนื้อหา", line)
        for claimy in ("เอกสารระบุว่า", "ตามเอกสาร", "เอกสารกล่าวว่า"):
            self.assertNotIn(claimy, line)


if __name__ == "__main__":
    unittest.main(verbosity=2)
