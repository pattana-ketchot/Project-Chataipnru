"""
คำตอบที่ไล่รายการ: ทุกรายการต้องมีหน้าที่รองรับ และหน้าที่ไม่รองรับต้องไม่ถูกอ้าง

    cd backend && python tests/test_source_items.py

ที่มาของชุดนี้ — ข้อ r1-05 บน production เมื่อ 15 ต.ค. 2569
    คำตอบ "มีแคลคูลัส 1-4" ได้ที่มาเป็น ma64.pdf หน้า 139 (ตารางเปรียบเทียบที่ไม่มีคำว่า
    แคลคูลัสเลย) กับหน้า 20 (มีแคลคูลัส 1-3) · หน้าที่มีครบทั้งสี่วิชา (หน้า 142) ไม่ถูกอ้าง
    เพราะ
      1. หน้า 139 ทวนชื่อหลักสูตรไทย-อังกฤษ ซึ่งกินสัดส่วนกรามของคำตอบมากกว่าชื่อวิชา
         (วัดได้ coverage 0.292 ต่อ 0.0796)
      2. ชื่อวิชาซ้ำกันหลายหน้า ตัวกรองกรามที่โปล่จึงตัดมันออกจากชุดที่ใช้วัด
      3. รายชื่อทั้งสี่วิชาของหน้า 142 กระจายอยู่หลายชิ้นของหน้านั้น ไม่มีชิ้นเดียวที่ครบ

ชุดนี้ไม่ใช้ฐานข้อมูลและไม่เรียกโมเดล — ใช้ชิ้นเอกสารจำลองที่เขียนข้อความแบบเดียวกับ
เอกสารจริง (มีรหัสวิชาคั่น ไม่มีช่องว่างสม่ำเสมอ)
"""
import sys
import unittest
import uuid
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.answer_claims import verify  # noqa: E402
from app.services.answer_evidence import list_items, supporting  # noqa: E402

COURSE = uuid.uuid4()
TITLE = "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาคณิตศาสตร์ (พ.ศ. 2564)"


class Chunk:
    """รูปร่างเดียวกับ SearchResultChunk เท่าที่ชั้นเลือกหลักฐานใช้"""

    def __init__(self, page: int, content: str, score: float = 0.6) -> None:
        self.chunk_id = uuid.uuid4()
        self.course_id = COURSE
        self.course_title = TITLE
        self.page_number = page
        self.content = content
        self.score = score


# หน้าที่ทวนชื่อหลักสูตรไทย-อังกฤษ แต่ไม่มีชื่อวิชาเลย (แบบ ma64.pdf หน้า 139)
NAME_ONLY = Chunk(139, "ตารางเปรียบเทียบหลักสูตรเดิม พ.ศ. 2559 กับหลักสูตรปรับปรุง พ.ศ. 2564 "
                       "ชื่อหลักสูตร ภาษาไทย : หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาคณิตศาสตร์ "
                       "ภาษาอังกฤษ : Bachelor of Science Program in Mathematics", score=0.62)
# หน้าที่มีแคลคูลัส 1-3 (แบบ ma64.pdf หน้า 20)
PAGE_123 = Chunk(20, "2.1) กลุ่มวิชาแกน 30 หน่วยกิต 4091403 แคลคูลัส 1 3(3-0-6) Calculus 1 "
                     "4092403 แคลคูลัส 2 3(3-0-6) Calculus 2 4093407 แคลคูลัส 3 3(3-0-6) Calculus 3",
                 score=0.57)
# หน้าที่มีแคลคูลัส 4 อยู่หน้าเดียว (แบบ ma64.pdf หน้า 21)
PAGE_4 = Chunk(21, "2.2.1) บังคับ 39 หน่วยกิต 4093408 แคลคูลัส 4 3(3-0-6) Calculus 4 "
                   "4094204 ทฤษฎีจำนวน 1 3(3-0-6)", score=0.55)
# หน้าที่มีครบทั้งสี่วิชาในตารางเดียว (แบบ ma64.pdf หน้า 142)
PAGE_ALL = Chunk(142, "4091403 แคลคูลัส 1 3(3-0-6) 4091403 แคลคูลัส 1 3(3-0-6) "
                      "4092403 แคลคูลัส 2 3(3-0-6) 4093407 แคลคูลัส 3 3(3-0-6) "
                      "4093408 แคลคูลัส 4 3(3-0-6)", score=0.63)

LIST_REPLY = ("หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาคณิตศาสตร์ (Bachelor of Science Program in "
              "Mathematics) พ.ศ. 2564 มีรายวิชาแคลคูลัส ได้แก่ แคลคูลัส 1 (Calculus 1), "
              "แคลคูลัส 2 (Calculus 2), แคลคูลัส 3 (Calculus 3) และแคลคูลัส 4 (Calculus 4)")
QUESTION = "หลักสูตรคณิตศาสตร์ พ.ศ. 2564 มีวิชาแคลคูลัสไหม"


def pages_of(reply, chunks, question=QUESTION):
    items = list_items(reply)
    return [s.page_number for s in supporting(reply, chunks, question, items=items)]


class SourceItemTests(unittest.TestCase):

    def test_รายการที่คำตอบไล่ชื่อถูกดึงออกมาได้(self):
        self.assertEqual(list_items(LIST_REPLY),
                         ("แคลคูลัส 1", "แคลคูลัส 2", "แคลคูลัส 3", "แคลคูลัส 4"))

    def test_คำตอบความเรียงไม่ถูกตีความว่าเป็นรายการ(self):
        prose = ("ผู้เข้าศึกษาต้องสำเร็จการศึกษาระดับมัธยมศึกษาตอนปลายหรือเทียบเท่า "
                 "หรือเป็นไปตามประกาศของมหาวิทยาลัย")
        self.assertEqual(list_items(prose), ())

    def test_รายการจากหลายหน้าต้องมีหลักฐานรองรับครบ(self):
        """แคลคูลัส 1-3 อยู่หน้า 20 · แคลคูลัส 4 อยู่หน้า 21 — ต้องอ้างทั้งสองหน้า"""
        chunks = [NAME_ONLY, PAGE_123, PAGE_4]
        pages = pages_of(LIST_REPLY, chunks)
        self.assertIn(20, pages, pages)
        self.assertIn(21, pages, pages)
        texts = [c.content + " · " + c.course_title for c in chunks
                 if c.page_number in pages]
        v = verify(LIST_REPLY, texts)
        unsupported = [c.shown for c in v.unsupported]
        self.assertEqual([c.shown for c in v.checked if c.kind == "item" and not c.supported],
                         [], unsupported)

    def test_หน้าที่ไม่มีเนื้อหารองรับต้องไม่ถูกอ้างเป็นที่มา(self):
        """หน้า 139 ทวนแต่ชื่อหลักสูตร — ห้ามถูกเลือกแม้ถ้อยคำซ้ำกับคำนำของคำตอบ"""
        pages = pages_of(LIST_REPLY, [NAME_ONLY, PAGE_123, PAGE_4, PAGE_ALL])
        self.assertNotIn(139, pages, pages)

    def test_หน้าเดียวที่ครอบครบต้องถูกเลือกก่อน(self):
        pages = pages_of(LIST_REPLY, [NAME_ONLY, PAGE_123, PAGE_ALL])
        self.assertEqual(pages, [142], pages)

    def test_รองรับไม่ครบต้องบอกว่าข้อไหนยังยืนยันไม่ได้(self):
        """มีแต่หน้าที่รองรับแคลคูลัส 1-3 — ต้องชี้ว่าแคลคูลัส 4 ยังยืนยันไม่ได้"""
        chunks = [NAME_ONLY, PAGE_123]
        pages = pages_of(LIST_REPLY, chunks)
        self.assertEqual(pages, [20], pages)
        v = verify(LIST_REPLY, [PAGE_123.content + " · " + PAGE_123.course_title])
        shown = [c.shown for c in v.unsupported]
        self.assertIn("แคลคูลัส 4", shown, [c.shown for c in v.checked])
        self.assertNotIn("แคลคูลัส 1", shown, shown)
        self.assertEqual(v.status, "รองรับบางส่วน", shown)

    def test_คำตอบความเรียงยังใช้เส้นทางเทียบกรามตามเดิม(self):
        """คู่ควบคุม: ไม่มีรายการ -> ต้องเลือกหน้าที่ข้อความรองรับ ไม่ใช่หน้าที่มีแต่ชื่อหลักสูตร"""
        prose = ("กลุ่มวิชาแกนของหลักสูตรกำหนด 30 หน่วยกิต โดยมีรายวิชา 4091403 แคลคูลัส 1 "
                 "3(3-0-6) Calculus 1 อยู่ในกลุ่มนี้")
        pages = pages_of(prose, [NAME_ONLY, PAGE_123, PAGE_4])
        self.assertEqual(pages, [20], pages)

    def test_รายการที่มีรหัสวิชากำกับต้องหาหน้าที่มาได้(self):
        """คำตอบเขียน "แคลคูลัส 1 (Calculus 1) รหัสวิชา 4091403" — ตารางในเอกสารวางรหัสไว้หน้าชื่อ

        เจอจากการรันในอิมเมจของ release รอบ 17: ตอนเลือกหน้าใช้การเทียบตรงตัว จึงหาไม่เจอ
        แล้วระบบขึ้นข้อความว่าจับคู่หน้าที่รองรับไม่ได้ ทั้งที่หน้า 142 มีวิชานั้นอยู่
        """
        reply = ("ปรากฏรายวิชาแคลคูลัสในเนื้อหา ดังนี้:\n"
                 "- แคลคูลัส 1 (Calculus 1) รหัสวิชา 4091403\n"
                 "- แคลคูลัส 2 (Calculus 2) รหัสวิชา 4092403\n"
                 "- แคลคูลัส 4 (Calculus 4) รหัสวิชา 4093408")
        pages = pages_of(reply, [NAME_ONLY, PAGE_123, PAGE_ALL])
        self.assertEqual(pages, [142], pages)
        v = verify(reply, [PAGE_ALL.content + " · " + PAGE_ALL.course_title])
        self.assertEqual(v.status, "รองรับครบ", [c.shown for c in v.unsupported])

    def test_รหัสวิชาผิดต้องไม่ถูกยืนยัน(self):
        """คู่ควบคุม — ยึดรหัสเป็นเกณฑ์ ดังนั้นรหัสที่ไม่มีในหน้าต้องไม่รองรับ"""
        reply = ("รายวิชาแคลคูลัส ดังนี้:\n"
                 "- แคลคูลัส 1 รหัสวิชา 4091403\n"
                 "- แคลคูลัส 9 รหัสวิชา 9999999")
        v = verify(reply, [PAGE_ALL.content])
        shown = [c.shown for c in v.unsupported]
        self.assertTrue(any("9999999" in x for x in shown), [c.shown for c in v.checked])

    def test_ชื่อรายการที่เขียนติดกันโดยไม่มีจุลภาค(self):
        """โมเดลเขียน "ได้แก่ ก ข และ ค" — ชิ้นแรกถูกดึงมาติดกัน ต้องยอมรับเมื่อทุกชื่อมีในหน้า"""
        page = ("โครงสร้างหลักสูตร 1. หมวดวิชาศึกษาทั่วไป ไม่น้อยกว่า 30 หน่วยกิต "
                "2. หมวดวิชาเฉพาะ ไม่น้อยกว่า 94 หน่วยกิต "
                "3. หมวดวิชาเลือกเสรี ไม่น้อยกว่า 6 หน่วยกิต")
        answer = ("โครงสร้างหลักสูตรแบ่งเป็น 3 หมวดวิชา ได้แก่ หมวดวิชาศึกษาทั่วไป "
                  "หมวดวิชาเฉพาะ และหมวดวิชาเลือกเสรี")
        v = verify(answer, [page])
        self.assertEqual(v.status, "รองรับครบ", [c.shown for c in v.unsupported])

    def test_เลขของรายการผิดต้องยังจับได้(self):
        """คู่ควบคุมของข้อบน — การยอมรับชื่อที่ติดกันต้องไม่ทำให้เลขวิชาผิดหลุดผ่าน"""
        v = verify("หลักสูตรนี้มีวิชาแคลคูลัส ได้แก่ แคลคูลัส 1, แคลคูลัส 9",
                   [PAGE_123.content])
        self.assertIn("แคลคูลัส 9", [c.shown for c in v.unsupported])
        self.assertEqual(v.status, "รองรับบางส่วน", [c.shown for c in v.checked])

    def test_ประโยคนำของรายการไม่ถูกนับเป็นข้ออ้าง(self):
        """ "…มีโครงสร้างหลักสูตรแบ่งเป็น 3 หมวดวิชา ดังนี้:" เป็นประโยคนำ ไม่ใช่ข้ออ้างที่ตรวจได้เอง"""
        page = "โครงสร้างหลักสูตร 1. หมวดวิชาศึกษาทั่วไป 2. หมวดวิชาเฉพาะ 3. หมวดวิชาเลือกเสรี"
        answer = ("หลักสูตรนี้มีโครงสร้างหลักสูตรแบ่งเป็น 3 หมวดวิชา ดังนี้:\n"
                  "1. หมวดวิชาศึกษาทั่วไป\n2. หมวดวิชาเฉพาะ\n3. หมวดวิชาเลือกเสรี")
        v = verify(answer, [page])
        self.assertNotIn("มีโครงสร้างหลักสูตรแบ่งเป็น", [c.shown for c in v.checked])
        self.assertEqual(v.status, "รองรับครบ", [c.shown for c in v.unsupported])

    def test_ข้ออ้างที่มีคำลักษณนามนำหน้าต้องเทียบกับชื่อจริงได้(self):
        """"มีรายวิชาแคลคูลัส" ต้องรองรับได้จากหน้าที่เขียน "4091403 แคลคูลัส 1"

        ก่อนแก้: ชั้นตรวจหาคำว่า "รายวิชาแคลคูลัส" ตรงตัวในหน้า จึงรายงานว่ายืนยันไม่ได้
        ทั้งที่หน้านั้นรองรับ (เจอจากข้อ r1-05 ในผลรอบ 16)
        """
        v = verify("หลักสูตรนี้มีรายวิชาแคลคูลัส", [PAGE_123.content])
        self.assertEqual([c.shown for c in v.unsupported], [], [c.shown for c in v.checked])


if __name__ == "__main__":
    unittest.main(verbosity=2)
