"""
ตรวจว่าคำอ้างอิงอย่าง "สาขานี้" "หลักสูตรนี้" ชี้ไปที่สาขาที่บทสนทนากำลังคุยอยู่

บทสนทนาจริงจากหน้าเว็บที่ทำให้ต้องมีไฟล์นี้:

    ผู้ใช้  อยากเรียน วิทคอม
    ผู้ใช้  มีวิชาเกี่ยวกับ AI ไหม
    ผู้ใช้  แล้วมีวิชาเกี่ยวกับ Cybersecurity ไหม
    ผู้ใช้  แล้วจบไปทำงานอะไรได้บ้าง
    ผู้ใช้  ถ้าอยากเป็น Web Developer สาขานี้เหมาะไหม เพราะอะไร
            -> ระบบตอบเรื่องเทคโนโลยีสารสนเทศ

สาเหตุที่ตามรอยได้
  - ขั้นเขียนคำถามใหม่เห็นเฉพาะคำถามของผู้ใช้ในหกข้อความล่าสุด ซึ่งไม่มีชื่อสาขาเลย จึงคืน
    คำถามเดิม 3/3 รอบ แล้วการค้นทั้งคลังเจอหน้าอาชีพของเทคโนโลยีสารสนเทศก่อน
  - คำย่อ "it" ถูกเทียบแบบมีอยู่ในข้อความ จึงตรงกับกลางคำ "Cybersecurity" และ "digital"

ตรวจแบบไม่เรียกฐานข้อมูลและโมเดล ส่วนที่ต้องถามระบบจริงหลายเทิร์นอยู่ใน eval/behaviour_check.py

    python -m eval.conversation_context_check
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

NAMES = [
    "คณิตศาสตร์",
    "คอมพิวเตอร์แอนิเมชันและมัลติมีเดีย",
    "วิทยาการคอมพิวเตอร์",
    "เทคโนโลยีสารสนเทศ",
    "การแพทย์แผนไทยประยุกต์",
    "เทคโนโลยีการจัดการสุขภาพ",
]
CS, IT = "วิทยาการคอมพิวเตอร์", "เทคโนโลยีสารสนเทศ"
WEB_DEV_QUESTION = "ถ้าอยากเป็น Web Developer สาขานี้เหมาะไหม เพราะอะไร"

# บทสนทนาจริงตามลำดับเวลา คำตอบของผู้ช่วยตัดมาเฉพาะช่วงต้นที่บันทึกไว้ในฐานข้อมูล
REAL_CONVERSATION = [
    ("user", "อยากเรียน วิทคอม"),
    ("assistant", "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาการคอมพิวเตอร์ (Bachelor of Science Program in "
                  "Computer Science) ของคณะวิทยาศาสตร์และเทคโนโลยี มหาวิทยาลัยราชภัฏ"),
    ("user", "มีวิชาเกี่ยวกับ AI ไหม"),
    ("assistant", "ในหลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาการคอมพิวเตอร์ (Bachelor of Science Program in "
                  "Computer Science) มีวิชาปัญญาประดิษฐ์ (Artificial Intelligence)"),
    ("user", "แล้วมีวิชาเกี่ยวกับ Cybersecurity ไหม"),
    ("assistant", "มีรายวิชาเกี่ยวกับ Cybersecurity (ความมั่นคงปลอดภัยไซเบอร์) ในหลักสูตรวิทยาศาสตรบัณฑิต "
                  "สาขาวิชาวิทยาการคอมพิวเตอร์ (Bachelor of Science Program in Com"),
    ("user", "แล้วจบไปทำงานอะไรได้บ้าง"),
    ("assistant", "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาการคอมพิวเตอร์ (Bachelor of Science Program in "
                  "Computer Science) จบไปสามารถประกอบอาชีพได้ดังนี้:\n- นักพัฒนาซอฟต์แวร์"),
]

RECOMMENDATION_REPLY = (
    "จากความสนใจที่บอกมา สาขาในคณะที่เกี่ยวข้อง ได้แก่\n"
    f"1. {CS}\n   หลักสูตรนี้มุ่งเน้นหลักการทางวิทยาการคอมพิวเตอร์\n"
    f"2. {IT}\n   หลักสูตรนี้มุ่งผลิตบัณฑิตด้านเทคโนโลยีสารสนเทศ\n\n"
    "เพื่อให้แนะนำได้ตรงขึ้น บอกเพิ่มได้ไหมครับว่าชอบงานแบบไหนหรือวิชาอะไรเป็นพิเศษ"
)


def turns(pairs):
    from app.services.chat import PriorTurn
    return [PriorTurn(role, content) for role, content in pairs]


class _WithNames(unittest.TestCase):
    def setUp(self):
        import app.services.chat as chat
        self._saved = chat._PROGRAM_NAMES
        chat._PROGRAM_NAMES = NAMES

    def tearDown(self):
        import app.services.chat as chat
        chat._PROGRAM_NAMES = self._saved


class RealConversationChecks(_WithNames):
    def test_หน้าต่างประวัติไม่มีชื่อสาขาในคำถามของผู้ใช้เลย(self):
        """ยืนยันสาเหตุ: ขั้นเขียนคำถามใหม่เห็นแต่คำถามเหล่านี้ จึงไม่มีทางรู้ว่าคุยสาขาไหน"""
        from app.services.chat import HISTORY_LIMIT
        from app.services.course_scope import programmes_named
        window = REAL_CONVERSATION[-HISTORY_LIMIT:]
        for role, content in window:
            if role == "user":
                self.assertEqual(programmes_named(content, NAMES, from_assistant=False), [], content)

    def test_สาขาที่กำลังคุยคือวิทยาการคอมพิวเตอร์(self):
        from app.services.chat import HISTORY_LIMIT, _context_programme
        history = turns(REAL_CONVERSATION[-HISTORY_LIMIT:])
        self.assertEqual(_context_programme(None, history), CS)

    def test_สาขานี้ถูกแทนด้วยสาขาที่กำลังคุย(self):
        from app.services.chat import HISTORY_LIMIT, _context_programme, _resolve_reference
        history = turns(REAL_CONVERSATION[-HISTORY_LIMIT:])
        resolved = _resolve_reference(WEB_DEV_QUESTION, _context_programme(None, history))
        self.assertIn(f"สาขา{CS}", resolved)
        self.assertNotIn("สาขานี้", resolved)
        self.assertNotIn(IT, resolved)

    def test_ขั้นเขียนคำถามใหม่ได้เห็นสาขาที่กำลังคุย(self):
        from app.services.chat import HISTORY_LIMIT, _format_history_for_condense
        history = turns(REAL_CONVERSATION[-HISTORY_LIMIT:])
        self.assertIn(CS, _format_history_for_condense(history, CS))
        self.assertNotIn(CS, _format_history_for_condense(history))


class ReferenceFormChecks(unittest.TestCase):
    def test_คำอ้างอิงหลายรูปแบบถูกแทนด้วยชื่อสาขา(self):
        from app.services.chat import _resolve_reference
        cases = {
            "แล้วสาขานี้ล่ะ": f"แล้วสาขา{CS}ล่ะ",
            "หลักสูตรนี้เรียนกี่ปี": f"หลักสูตร{CS}เรียนกี่ปี",
            "สาขาวิชานี้มีวิชาอะไรบ้าง": f"สาขา{CS}มีวิชาอะไรบ้าง",
            "สาขาดังกล่าวจบแล้วทำงานอะไร": f"สาขา{CS}จบแล้วทำงานอะไร",
        }
        for question, expected in cases.items():
            self.assertEqual(_resolve_reference(question, CS), expected)

    def test_คำถามที่ไม่ได้อ้างถึงสาขาเดิมไม่ถูกจับ(self):
        from app.services.chat import _REFERENCE
        for question in ("สาขาไหนเหมาะกับคนชอบคำนวณ", "คณะมีสาขาอะไรบ้าง", "แล้วจบไปทำงานอะไรได้บ้าง"):
            self.assertIsNone(_REFERENCE.search(question), question)

    def test_รูปภาษาอังกฤษต่อชื่อสาขาท้ายคำถาม(self):
        from app.services.chat import _REFERENCE, _resolve_reference
        self.assertIsNotNone(_REFERENCE.search("Is this programme good for web developers?"))
        self.assertIn(CS, _resolve_reference("Is this programme good for web developers?", CS))


class ContextAmbiguityChecks(_WithNames):
    def test_หลังคำแนะนำหลายสาขาถือว่ากำกวม_ไม่ย้อนไปหยิบสาขาเก่า(self):
        """"สาขานี้" หลังรายการหลายสาขาไม่ได้หมายถึงสาขาที่คุยกันก่อนหน้านั้น"""
        from app.services.chat import _context_programme
        history = turns(REAL_CONVERSATION + [
            ("user", "สาขาไหนเหมาะกับคนชอบทำงานกับคอมพิวเตอร์"),
            ("assistant", RECOMMENDATION_REPLY),
        ])
        self.assertIsNone(_context_programme(None, history))

    def test_ชื่อรายวิชาในคำตอบไม่นับเป็นสาขา(self):
        from app.services.course_scope import programmes_named
        reply = (
            f"หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชา{CS} มีรายวิชาดังนี้\n"
            "- คณิตศาสตร์ไม่ต่อเนื่อง (Discrete Mathematics)\n"
            "- สถิติสำหรับวิทยาการข้อมูล"
        )
        self.assertEqual(programmes_named(reply, NAMES, from_assistant=True), [CS])

    def test_ไม่มีประวัติคืนค่าว่าง(self):
        from app.services.chat import _context_programme
        self.assertIsNone(_context_programme(None, []))


class AliasBoundaryChecks(unittest.TestCase):
    """คำย่ออักษรโรมันต้องไม่ตรงกับกลางคำอังกฤษอื่น"""

    def test_it_ไม่ตรงกับกลางคำ(self):
        from app.services.course_scope import programmes_named
        for text in ("แล้วมีวิชาเกี่ยวกับ Cybersecurity ไหม", "มีวิชา digital marketing ไหม"):
            self.assertEqual(programmes_named(text, NAMES, from_assistant=False), [], text)

    def test_คำย่อที่พิมพ์แยกคำยังจับได้(self):
        from app.services.course_scope import programmes_named
        self.assertEqual(programmes_named("อยากเรียน IT", NAMES, from_assistant=False), [IT])
        self.assertEqual(programmes_named("อยากเรียน วิทคอม", NAMES, from_assistant=False), [CS])


if __name__ == "__main__":
    unittest.main(verbosity=2)
