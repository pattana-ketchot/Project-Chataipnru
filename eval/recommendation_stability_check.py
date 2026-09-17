"""
ตรวจว่ารายชื่อสาขาที่แชทแนะนำ ไม่ขึ้นกับผลของขั้นเขียนเหตุผล (Gemini)

เหตุที่ต้องมี: log จริงของคำถาม "สาขาไหนเหมาะกับคนชอบทำงานกับคอมพิวเตอร์" (mko.shadow_answers
ทุกแถว has_history=false ห่างกันไม่ถึงนาที) ให้ผลสี่แบบ — ไม่มีสาขาเลย / วิทยาการคอมพิวเตอร์ /
+เทคโนโลยีสารสนเทศ / +คอมพิวเตอร์แอนิเมชัน — ทั้งที่การจัดอันดับด้วยเวกเตอร์ให้ผลเดิมทุกครั้ง
(.561 / .542 / .528) ต้นเหตุคือโค้ดตัดสาขาที่ขั้นเขียนเหตุผลไม่ได้ให้ข้อความออกจากคำตอบ
รายละเอียดใน docs/CHAT_BROAD_RECOMMENDATION_RCA.md

ชุดนี้ตรึงสัญญาไว้ว่า: ถ้อยคำของเหตุผลเปลี่ยนได้ แต่ "รายชื่อและลำดับของสาขา" ต้องมาจาก
program_match.match_programs() เท่านั้น ไม่เรียกฐานข้อมูลและไม่เรียกโมเดล

    python -m eval.recommendation_stability_check
"""
from __future__ import annotations

import os
import re
import sys
import types
import unittest
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
os.environ.setdefault("JWT_SECRET", "local-test-only")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres@127.0.0.1:55432/course_advisor")

from llm.prompts import NO_EVIDENCE_MARKER  # noqa: E402

CS = "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาการคอมพิวเตอร์ (พ.ศ. 2566)"
IT = "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาเทคโนโลยีสารสนเทศ (พ.ศ. 2566)"
ANIM = "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาคอมพิวเตอร์แอนิเมชันและมัลติมีเดีย (พ.ศ. 2566)"
PROGRAM_NAMES = ["วิทยาการคอมพิวเตอร์", "เทคโนโลยีสารสนเทศ", "คอมพิวเตอร์แอนิเมชันและมัลติมีเดีย"]

# อันดับที่ระบบจัดได้สำหรับคำถามนี้ (ค่าที่วัดไว้ใน program_match._RELEVANCE_MARGIN)
CANDIDATES = [CS, ANIM, IT]
QUESTION = "สาขาไหนเหมาะกับคนชอบทำงานกับคอมพิวเตอร์"


@dataclass
class FakeMatch:
    title: str
    rationale: str
    course_id: str = "x"


def reply_for(rationales, refinement=False, confidence="high", titles=CANDIDATES):
    """เรียก _recommendation_reply โดยแทน program_match ด้วยอันดับที่กำหนดเอง"""
    import app.services.chat as chat

    matches = [FakeMatch(t, r) for t, r in zip(titles, rationales)]
    fake = types.ModuleType("app.services.program_match")
    fake.match_programs = lambda db, answers, limit=3, relevant_only=False, profile_text=None: matches
    fake.confidence_of = lambda ms: confidence
    real = sys.modules.get("app.services.program_match")
    saved_names = chat._PROGRAM_NAMES
    chat._PROGRAM_NAMES = PROGRAM_NAMES
    sys.modules["app.services.program_match"] = fake
    try:
        return chat._recommendation_reply(None, QUESTION, refinement=refinement)
    finally:
        chat._PROGRAM_NAMES = saved_names
        if real is not None:
            sys.modules["app.services.program_match"] = real
        else:
            del sys.modules["app.services.program_match"]


def listed_programmes(reply: str) -> list[str]:
    """ชื่อสาขาตามลำดับที่ปรากฏในคำตอบ อ่านจากบรรทัดที่ขึ้นต้นด้วยเลขอันดับ"""
    return [m.group(1).strip() for m in re.finditer(r"^\d+\.\s*(.+)$", reply, re.MULTILINE)]


EXPECTED = ["วิทยาการคอมพิวเตอร์", "คอมพิวเตอร์แอนิเมชันและมัลติมีเดีย", "เทคโนโลยีสารสนเทศ"]

FULL = ["เน้นการพัฒนาซอฟต์แวร์", "เน้นงานแอนิเมชันและมัลติมีเดีย", "เน้นระบบสารสนเทศ"]


class CandidateStabilityChecks(unittest.TestCase):
    """A-F ตามที่ตกลงไว้ — รายชื่อและลำดับต้องเท่ากับที่ backend จัดมาเสมอ"""

    def test_A_เหตุผลครบทุกสาขา(self):
        self.assertEqual(listed_programmes(reply_for(FULL)), EXPECTED)

    def test_B_เหตุผลหายไปหนึ่งสาขา(self):
        for i in range(3):
            with self.subTest(missing=EXPECTED[i]):
                rationales = list(FULL)
                rationales[i] = ""
                self.assertEqual(listed_programmes(reply_for(rationales)), EXPECTED)

    def test_C_เหตุผลหายหลายสาขา(self):
        self.assertEqual(listed_programmes(reply_for(["", "", ""])), EXPECTED)
        self.assertEqual(listed_programmes(reply_for(["เน้นการพัฒนาซอฟต์แวร์", "", ""])), EXPECTED)

    def test_D_เหตุผลเป็นเครื่องหมายไม่มีข้อมูลรองรับ(self):
        marker = [NO_EVIDENCE_MARKER] * 3
        self.assertEqual(listed_programmes(reply_for(marker)), EXPECTED)
        mixed = ["เน้นการพัฒนาซอฟต์แวร์", NO_EVIDENCE_MARKER, ""]
        self.assertEqual(listed_programmes(reply_for(mixed)), EXPECTED)

    def test_E_ถ้อยคำของเหตุผลต่างกันแต่รายชื่อเท่าเดิม(self):
        wording_a = ["หลักสูตรนี้มุ่งเน้นการพัฒนาซอฟต์แวร์", "เน้นงานแอนิเมชัน", "เน้นระบบสารสนเทศ"]
        wording_b = ["เน้นหลักการทางวิทยาการคอมพิวเตอร์ทั้งทฤษฎีและปฏิบัติ",
                     "สร้างสรรค์งานแอนิเมชันและมัลติมีเดีย", "ออกแบบและพัฒนาระบบสารสนเทศ"]
        a, b = reply_for(wording_a), reply_for(wording_b)
        self.assertEqual(listed_programmes(a), listed_programmes(b))
        self.assertNotEqual(a, b)  # ถ้อยคำต่างกันได้จริง

    def test_F_ลำดับมาจาก_backend_ไม่ใช่จากเหตุผล(self):
        """สลับลำดับที่ backend ส่งมา คำตอบต้องสลับตาม และเหตุผลที่ยาวกว่าไม่ดันอันดับขึ้น"""
        swapped = reply_for(FULL, titles=[IT, CS, ANIM])
        self.assertEqual(listed_programmes(swapped),
                         ["เทคโนโลยีสารสนเทศ", "วิทยาการคอมพิวเตอร์", "คอมพิวเตอร์แอนิเมชันและมัลติมีเดีย"])
        long_first = ["สั้น", "ยาวมาก " * 20, "กลาง"]
        self.assertEqual(listed_programmes(reply_for(long_first)), EXPECTED)

    def test_รอบตอบต่อยอดก็คงรายชื่อไว้เหมือนกัน(self):
        self.assertEqual(listed_programmes(reply_for([NO_EVIDENCE_MARKER] * 3, refinement=True)), EXPECTED)
        self.assertEqual(listed_programmes(reply_for(["", "", ""], refinement=True)), EXPECTED)


class FallbackTextChecks(unittest.TestCase):
    def test_เครื่องหมายภายในต้องไม่หลุดถึงผู้ใช้(self):
        reply = reply_for([NO_EVIDENCE_MARKER, "", "เน้นระบบสารสนเทศ"])
        self.assertNotIn(NO_EVIDENCE_MARKER, reply)
        self.assertNotIn("[[", reply)

    def test_แยกสองสาเหตุออกจากกัน(self):
        import app.services.chat as chat
        reply = reply_for([NO_EVIDENCE_MARKER, "", "เน้นระบบสารสนเทศ"])
        self.assertIn(chat._RATIONALE_NO_EVIDENCE, reply)
        self.assertIn(chat._RATIONALE_UNAVAILABLE, reply)

    def test_ข้อความแทนไม่ได้เพิ่มข้อเท็จจริงของหลักสูตร(self):
        import app.services.chat as chat
        for text in (chat._RATIONALE_NO_EVIDENCE, chat._RATIONALE_UNAVAILABLE):
            for claim in ("เหมาะ", "ดีที่สุด", "รายวิชา", "อาชีพ", "หน่วยกิต", "ค่าเทอม"):
                self.assertNotIn(claim, text)

    def test_ข้อความแทนคงที่สำหรับอินพุตเดียวกัน(self):
        import app.services.chat as chat
        self.assertEqual(chat._rationale_line(""), chat._rationale_line("   "))
        self.assertEqual(chat._rationale_line(NO_EVIDENCE_MARKER), chat._rationale_line(f" {NO_EVIDENCE_MARKER} "))
        self.assertEqual(chat._rationale_line("เน้นซอฟต์แวร์"), "เน้นซอฟต์แวร์")
        self.assertEqual(reply_for(FULL), reply_for(FULL))

    def test_ทุกสาขาในรายการมีข้อความใต้ชื่อเสมอ(self):
        reply = reply_for(["", NO_EVIDENCE_MARKER, "เน้นระบบสารสนเทศ"])
        lines = [l for l in reply.splitlines() if l.strip()]
        for i, line in enumerate(lines):
            if re.match(r"^\d+\.\s", line):
                self.assertTrue(lines[i + 1].startswith("   "), line)


if __name__ == "__main__":
    unittest.main()
