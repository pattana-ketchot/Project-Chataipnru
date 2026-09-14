"""
ตรวจว่าหลักฐาน "แก่นของหลักสูตร" ที่ส่งให้ขั้นเขียนเหตุผลไม่ใช่สารบัญ

เหตุที่ต้องมี: _fetch_program_core เคยเลือกสองชิ้นแรกที่มีหัวข้ออาชีพหรือวัตถุประสงค์ตามลำดับหน้า
ซึ่งคือสารบัญต้นเล่ม ฉบับที่เปิดสอนราวหนึ่งในสามจึงส่งสารบัญไปแทนวัตถุประสงค์จริง ขั้นเขียนเหตุผล
ตัดสินว่าไม่มีข้อมูลรองรับ ผู้ใช้บนหน้าเว็บได้คำตอบว่าไม่พบสาขาที่ตรง

ข้อความตัวอย่างแต่งขึ้นตามรูปแบบที่พบในเอกสารจริง ไม่ได้คัดลอกมาจากเล่มใด

    python -m eval.program_core_check
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.services.program_match import _fetch_program_core, _looks_like_table_of_contents  # noqa: E402

TOC_WITH_LEADERS = (
    "หมวดที่ 2 ข้อมูลเฉพาะของหลักสูตร ........................................ 8\n"
    "1. ปรัชญา ความสำคัญ และวัตถุประสงค์ของหลักสูตร ......................... 8\n"
    "2. แผนพัฒนาและปรับปรุง ................................................ 9\n"
    "8. อาชีพที่สามารถประกอบได้หลังสำเร็จการศึกษา ............................ 3\n"
)
TOC_WITHOUT_LEADERS = (
    "สารบัญ หน้า หมวดที่ 1 ข้อมูลทั่วไป 1 1 ชื่อหลักสูตร 1 2 ชื่อปริญญา 1 3 วิชาเอก 1 "
    "8 อาชีพที่สามารถประกอบได้หลังสำเร็จการศึกษา 2 9 อาจารย์ผู้รับผิดชอบ 2 "
    "หมวดที่ 2 1 ปรัชญา ความสำคัญ และวัตถุประสงค์ของหลักสูตร 7 2 แผนพัฒนาปรับปรุง 8"
)
CAREERS = (
    "8. อาชีพที่สามารถประกอบได้หลังสำเร็จการศึกษา 8.1 นักพัฒนาระบบ 8.2 นักวิเคราะห์ข้อมูล "
    "8.3 ผู้ดูแลเครือข่าย 8.4 นักวิชาการในหน่วยงานรัฐและเอกชน"
)
OBJECTIVES = (
    "1. ปรัชญา ความสำคัญ และวัตถุประสงค์ของหลักสูตร 1.1 ปรัชญา มุ่งผลิตบัณฑิตที่มีความรู้ทันสมัย "
    "1.3 วัตถุประสงค์ของหลักสูตร เพื่อผลิตบัณฑิตให้มีคุณลักษณะ 1.3.1 มีความรู้และทักษะในศาสตร์ของสาขา "
    "สามารถนำไปประยุกต์ใช้ในการทำงานได้จริง"
)


class FakeDb:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, *args, **kwargs):
        return SimpleNamespace(all=lambda: self.rows)


def row(page, content):
    return SimpleNamespace(page_number=page, content=content)


class TableOfContentsChecks(unittest.TestCase):
    def test_สารบัญทั้งแบบมีและไม่มีจุดนำถูกจับได้(self):
        self.assertTrue(_looks_like_table_of_contents(TOC_WITH_LEADERS))
        self.assertTrue(_looks_like_table_of_contents(TOC_WITHOUT_LEADERS))

    def test_เนื้อหาที่มีเลขข้อย่อยไม่ถูกตีเป็นสารบัญ(self):
        """รายการอาชีพ 8.1 8.2 ... มีตัวเลขเยอะ แต่เป็นเลขข้อทศนิยม ไม่ใช่เลขหน้า"""
        self.assertFalse(_looks_like_table_of_contents(CAREERS))
        self.assertFalse(_looks_like_table_of_contents(OBJECTIVES))
        self.assertFalse(_looks_like_table_of_contents(""))


class ProgramCoreChecks(unittest.TestCase):
    def test_ข้ามสารบัญต้นเล่มแล้วใช้เนื้อหาจริง(self):
        db = FakeDb([row(3, TOC_WITH_LEADERS), row(3, TOC_WITHOUT_LEADERS), row(8, CAREERS), row(13, OBJECTIVES)])
        core = _fetch_program_core(db, None)
        self.assertIn("8.1 นักพัฒนาระบบ", core)
        self.assertIn("1.3.1", core)
        self.assertNotIn("........", core)
        self.assertNotIn("[หน้า 3]", core)

    def test_ใช้ไม่เกินสองชิ้น(self):
        db = FakeDb([row(8, CAREERS), row(13, OBJECTIVES), row(14, OBJECTIVES)])
        self.assertEqual(_fetch_program_core(db, None).count("[หน้า"), 2)

    def test_มีแต่สารบัญให้คืนค่าว่าง_ไม่ส่งสารบัญแทน(self):
        self.assertEqual(_fetch_program_core(FakeDb([row(3, TOC_WITH_LEADERS)]), None), "")


class NewestCoreChunksChecks(unittest.TestCase):
    """แก่นของหลักสูตรในรูปชิ้นเอกสารที่อ้างอิงได้ ใช้เป็นหลักฐานของคำถามเปรียบเทียบหลายหลักสูตร"""

    class Db:
        def __init__(self, editions, rows_by_course):
            self.editions, self.rows_by_course, self.asked_for = editions, rows_by_course, []

        def execute(self, statement, params):
            if "FROM courses" in str(statement):
                return SimpleNamespace(all=lambda: self.editions)
            self.asked_for.append(params["course_id"])
            return SimpleNamespace(all=lambda: self.rows_by_course[params["course_id"]])

    def test_ใช้ฉบับล่าสุด_ข้ามสารบัญ_และอ้างอิงได้(self):
        import uuid
        from app.services.program_match import newest_core_chunks

        old, new = uuid.uuid4(), uuid.uuid4()
        editions = [SimpleNamespace(id=old, title="หลักสูตร ก (พ.ศ. 2561)"), SimpleNamespace(id=new, title="หลักสูตร ก (พ.ศ. 2566)")]
        rows = [SimpleNamespace(id=uuid.uuid4(), course_id=new, page_number=p, content=c)
                for p, c in ((3, TOC_WITH_LEADERS), (8, CAREERS), (13, OBJECTIVES))]
        db = self.Db(editions, {new: rows, old: []})
        chunks = newest_core_chunks(db, [old, new], score=0.61)
        self.assertEqual(db.asked_for, [new])
        self.assertEqual([c.page_number for c in chunks], [8, 13])
        self.assertTrue(all(c.course_id == new and c.course_title.endswith("2566)") and c.score == 0.61 for c in chunks))
        self.assertEqual({c.chunk_id for c in chunks}, {rows[1].id, rows[2].id})

    def test_ไม่มีหลักสูตรคืนรายการว่าง(self):
        from app.services.program_match import newest_core_chunks
        self.assertEqual(newest_core_chunks(self.Db([], {}), [], score=0.5), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
