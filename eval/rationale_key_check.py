"""
ตรวจการจับคู่เหตุผลที่โมเดลเขียนกับหลักสูตรในรายการ

เหตุที่ต้องมี: พรอมต์คั่นแต่ละหลักสูตรด้วย "### ชื่อหลักสูตร" บนระบบจริงโมเดลคัดลอก "### " ติดมาในคีย์
1 ใน 12 ครั้ง คีย์นั้นไม่ตรงกับชื่อหลักสูตรทั้งแบบตรงตัวและแบบหลวม เหตุผลจึงหายไป ผู้ใช้ได้ข้อความว่า
ระบบยังเขียนคำอธิบายไม่ได้ ทั้งที่โมเดลเขียนมาครบ

    python -m eval.rationale_key_check
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.services.program_match import _rationale_for  # noqa: E402

CS_2561 = "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาการคอมพิวเตอร์ (พ.ศ. 2561)"
CS_2566 = "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาการคอมพิวเตอร์ (พ.ศ. 2566)"


class RationaleKeyChecks(unittest.TestCase):
    def test_คีย์ที่มีเครื่องหมายหัวข้อติดมายังจับคู่ได้(self):
        self.assertEqual(_rationale_for({f"### {CS_2561}": "เหตุผล"}, CS_2561), "เหตุผล")
        self.assertEqual(_rationale_for({f"##{CS_2561}  ": "เหตุผล"}, CS_2561), "เหตุผล")

    def test_ฉบับต่างปีของสาขาเดียวกันได้เหตุผลของตัวเอง(self):
        rationales = {f"### {CS_2561}": "ของ 2561", f"### {CS_2566}": "ของ 2566"}
        self.assertEqual(_rationale_for(rationales, CS_2561), "ของ 2561")
        self.assertEqual(_rationale_for(rationales, CS_2566), "ของ 2566")

    def test_คีย์แบบตรงตัวและแบบย่อยังทำงานเหมือนเดิม(self):
        self.assertEqual(_rationale_for({CS_2561: "ตรงตัว"}, CS_2561), "ตรงตัว")
        self.assertEqual(_rationale_for({"วิทยาการคอมพิวเตอร์": "ย่อ"}, CS_2561), "ย่อ")

    def test_คีย์ของสาขาอื่นไม่ถูกหยิบมาใช้(self):
        self.assertEqual(_rationale_for({"### หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาคณิตศาสตร์": "x"}, CS_2561), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
