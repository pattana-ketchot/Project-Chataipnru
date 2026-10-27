"""
ความเกี่ยวข้องของแต่ละหน้าที่แสดงเป็นที่มา — หน้าที่ซ้ำแต่ชื่อหลักสูตรหรือคำเชื่อมต้องไม่ถูกอ้าง

    cd backend && python tests/test_source_relevance.py

ที่มาของชุดนี้ — ข้อสังเกต 6.1 ใน DEPLOY_RESULT_ROUND17 (15 ต.ค. 2569)
    คำตอบ "โครงสร้างหลักสูตรเทคโนโลยีสารสนเทศ 2566 มี 3 หมวดวิชา" แสดงที่มาเป็น
    it66.pdf หน้า 19 (ซึ่งมีโครงสร้างครบทุกข้อ) **และหน้า 137** ซึ่งเป็นหน้าภาคผนวก
    ผลสำรวจความเห็นอาจารย์ ไม่มีเรื่องโครงสร้างหลักสูตรเลย

    สองสาเหตุที่วัดได้
      1. การตัด "กรอบของคำตอบ" ทำที่ระดับชุดกราม จึงลบกรามที่คาบรอยต่อไม่ได้ และชื่อ
         หลักสูตรในคำตอบ (ที่แทรกชื่อภาษาอังกฤษไว้ในวงเล็บ) ไม่ตรงกับชื่อในคลังเป็น
         สตริงเดียว · หน้า 137 ได้คะแนนจากกราม "สาขาวิชาเทคโนโลยีสารสนเทศ(" และ
         "รประกอบด้วย" ซึ่งเป็นถ้อยคำกรอบทั้งคู่ (coverage 0.119)
      2. เมื่อคำตอบ "โดยรวม" มีหลักฐานรองรับแล้ว ทุกหน้าที่ถูกเลือกถูกแสดงเป็นที่มา
         โดยไม่ได้ถามว่าหน้านั้นรองรับอะไรของคำตอบนี้บ้าง

ชุดนี้ไม่เรียกโมเดลและไม่ใช้ฐานข้อมูลจริง — ข้อความของหน้าเป็นข้อความจริงจากคลัง
(tests/fixtures/round20_pages.json) ส่วนด่านตัดหน้าทดสอบผ่าน _with_rag_sources ด้วย
ฐานข้อมูลจำลองที่ตอบเฉพาะสองคำสั่งที่ฟังก์ชันนั้นใช้
"""
import json
import os
import sys
import unittest
import uuid
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# services/chat.py สร้าง engine ตอน import จึงต้องมีค่าตั้งต้นให้ครบ · ชุดนี้ไม่เปิดการเชื่อมต่อ
# จริง (ใช้ฐานข้อมูลจำลอง) ค่าพวกนี้จึงไม่ถูกใช้ — ไม่เขียนทับค่าที่ตั้งไว้แล้วในสภาพแวดล้อม
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://ไม่ใช้งาน/ไม่ใช้งาน")
os.environ.setdefault("JWT_SECRET", "ชุดทดสอบไม่ได้ออก token")

from app.services.answer_claims import CONTENT_CLAIMS, supported_by, verify  # noqa: E402
from app.services.answer_evidence import (_masked_grams, _split_items, answer_body,  # noqa: E402
                                          list_items, supporting)
from app.services.chat import _with_rag_sources  # noqa: E402

PAGES = json.loads((Path(__file__).parent / "fixtures" / "round20_pages.json")
                   .read_text(encoding="utf-8"))

IT_TITLE = "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาเทคโนโลยีสารสนเทศ (พ.ศ. 2566)"
CS_TITLE = "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาการคอมพิวเตอร์ (พ.ศ. 2566)"
MA_TITLE = "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาคณิตศาสตร์ (พ.ศ. 2564)"


class Chunk:
    """รูปร่างเดียวกับ SearchResultChunk เท่าที่ชั้นเลือกหลักฐานใช้"""

    def __init__(self, doc: str, page: int, content: str, title: str,
                 score: float = 0.6, course: uuid.UUID | None = None) -> None:
        self.chunk_id = uuid.uuid4()
        self.course_id = course or uuid.uuid4()
        self.course_title = title
        self.page_number = page
        self.content = content
        self.score = score
        self.document_id = uuid.uuid4()
        self.file = doc

    def model_copy(self, update: dict):
        """SearchResultChunk เป็น pydantic — ชั้นรวมหน้าใช้ model_copy เพื่อใส่ข้อความทั้งหน้า"""
        twin = Chunk(self.file, self.page_number, update.get("content", self.content),
                     self.course_title, self.score, self.course_id)
        twin.chunk_id = self.chunk_id
        twin.document_id = self.document_id
        return twin


def page(doc: str, pg: int, title: str, score: float = 0.6, course=None) -> Chunk:
    return Chunk(doc, pg, PAGES[f"{doc}|{pg}"], title, score, course)


# ---- สภาพจริงของข้อสังเกต 6.1 ----
IT_Q = "หลักสูตรเทคโนโลยีสารสนเทศ พ.ศ. 2566 โครงสร้างหลักสูตรมีหมวดวิชาใดบ้าง"
IT_REPLY = (
    "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาเทคโนโลยีสารสนเทศ (Bachelor of Science Program in "
    "Information Technology) พ.ศ. 2566 มีโครงสร้างหลักสูตรประกอบด้วย 3 หมวดวิชาหลัก ดังนี้ครับ:\n"
    "1. หมวดวิชาศึกษาทั่วไป ไม่น้อยกว่า 30 หน่วยกิต\n"
    "2. หมวดวิชาเฉพาะ ไม่น้อยกว่า 94 หน่วยกิต\n"
    "3. หมวดวิชาเลือกเสรี ไม่น้อยกว่า 6 หน่วยกิต")

# ---- คำตอบไล่รายการวิชาข้ามหน้า (เกณฑ์ที่ต้องไม่เสียจากรอบ 17) ----
MA_Q = "หลักสูตรคณิตศาสตร์ พ.ศ. 2564 มีแคลคูลัสอะไรบ้าง"
MA_REPLY = ("หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาคณิตศาสตร์ (Bachelor of Science Program in "
            "Mathematics) พ.ศ. 2564 มีรายวิชาแคลคูลัส ได้แก่ แคลคูลัส 1, แคลคูลัส 2, "
            "แคลคูลัส 3 และแคลคูลัส 4")


class FakeResult:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


class FakeDB:
    """ฐานข้อมูลจำลองที่ตอบเฉพาะสองคำสั่งที่ _with_rag_sources ใช้ (อ่านอย่างเดียว)"""

    def __init__(self, chunks) -> None:
        self.chunks = list(chunks)

    def execute(self, stmt, params=None):
        sql = str(stmt)
        if "original_filename" in sql:
            want = set(params["ids"])
            return FakeResult([
                {"chunk_id": c.chunk_id, "document_id": c.document_id, "file": c.file}
                for c in self.chunks if str(c.chunk_id) in want])
        if "string_agg" in sql:
            docs, pgs = set(params["docs"]), set(params["pages"])
            rows = {}
            for c in self.chunks:
                if str(c.document_id) in docs and c.page_number in pgs:
                    key = (c.document_id, c.page_number)
                    rows.setdefault(key, []).append(c.content)
            return FakeResult([
                {"document_id": d, "page_number": pg, "page_text": " ".join(parts)}
                for (d, pg), parts in rows.items()])
        raise AssertionError(f"คำสั่งที่ไม่ได้เตรียมไว้: {sql[:60]}")


class Prepared:
    """เท่าที่ _with_rag_sources อ่าน"""

    def __init__(self, chunks, question: str) -> None:
        self.status = "answered"
        self.retrieved = list(chunks)
        self.citations = list(chunks)
        self.sources: list[dict] = []
        self.search_query = question


def pages_of(reply, chunks, question):
    return [s.page_number for s in
            supporting(reply, chunks, question, items=list_items(reply))]


def served(reply, chunks, question):
    """ข้อความที่ผู้ใช้เห็น + รายการที่มาแบบมีโครงสร้าง (เดินเส้นทางจริงของ /chat)"""
    db = FakeDB(chunks)
    text, sources = _with_rag_sources(db, Prepared(chunks, question), reply)
    return text, sources


class FrameLeakTests(unittest.TestCase):
    """ข้อ 1 — คำเกริ่นและชื่อหลักสูตรต้องไม่รั่วเข้าการเทียบถ้อยคำ"""

    def test_ประโยคนำที่มีแต่ชื่อหลักสูตรกับคำเกริ่นไม่เหลือสาระให้วัด(self):
        rest = _split_items(answer_body(IT_REPLY))[1]
        frames = [IT_Q, IT_TITLE, "Bachelor of Science Program in Information Technology"]
        self.assertEqual(_masked_grams(rest, frames), set())

    def test_ชื่อหลักสูตรที่แทรกวงเล็บอังกฤษยังถูกตัดเป็นกรอบ(self):
        """คำตอบเขียน "…สารสนเทศ (Bachelor…) พ.ศ. 2566" แต่ชื่อในคลังเขียน "…สารสนเทศ (พ.ศ. 2566)"

        สตริงทั้งชื่อจึงไม่ตรงกัน การตัดกรอบต้องทำทีละกราม ไม่ใช่แทนที่สตริงเดียว
        """
        written = "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาเทคโนโลยีสารสนเทศ (Bachelor of Science) พ.ศ. 2566"
        self.assertEqual(_masked_grams(written, [IT_TITLE, "Bachelor of Science"]), set())

    def test_กรอบไม่กินสาระของคำตอบ(self):
        """คู่ควบคุม — ข้อความที่มีสาระต้องยังเหลือกรามไว้วัด"""
        body = ("หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาเทคโนโลยีสารสนเทศ พ.ศ. 2566 กำหนด"
                "หมวดวิชาเฉพาะ ไม่น้อยกว่า 94 หน่วยกิต และกลุ่มวิชาแกน 15 หน่วยกิต")
        left = _masked_grams(body, [IT_Q, IT_TITLE])
        self.assertTrue(left)
        self.assertTrue(any("94" in g for g in left), sorted(left))


class PageRelevanceTests(unittest.TestCase):
    """ข้อ 2 — ความเกี่ยวข้องของแต่ละหน้า ไม่ใช่ของคำตอบโดยรวม"""

    def test_หน้าที่เนื้อหาไม่รองรับข้ออ้างใดเลยต้องไม่มีข้ออ้างติดมา(self):
        got = supported_by(IT_REPLY, [PAGES["it66.pdf|19"], PAGES["it66.pdf|137"]])
        self.assertEqual([c.shown for c in got[1]], [])
        self.assertGreaterEqual(len([c for c in got[0] if c.kind in CONTENT_CLAIMS]), 3,
                                [c.shown for c in got[0]])

    def test_ชื่อหลักสูตรที่ต่อท้ายหน่วยหลักฐานทำให้ทุกหน้ารองรับปีได้(self):
        """เหตุผลที่ด่านนี้ต้องเทียบด้วยเนื้อหาหน้าเท่านั้น — ชื่อเล่มติดอยู่กับทุกหน้า"""
        with_title = supported_by(IT_REPLY, [PAGES["it66.pdf|137"] + " · " + IT_TITLE])
        self.assertEqual([c.shown for c in with_title[0]], ["พ.ศ. 2566"])

    def test_ที่มาที่ผู้ใช้เห็นเหลือเฉพาะหน้าที่รองรับเนื้อหา(self):
        chunks = [page("it66.pdf", 19, IT_TITLE, 0.58),
                  page("it66.pdf", 137, IT_TITLE, 0.61)]
        text, sources = served(IT_REPLY, chunks, IT_Q)
        self.assertIn("ที่มา: it66.pdf หน้า 19", text)
        self.assertNotIn("137", text)
        self.assertEqual([(s["file"], s["page_start"]) for s in sources],
                         [("it66.pdf", 19)])

    def test_หน้าที่ไม่รองรับต้องหายไปแม้ถูกเลือกมาก่อนหน้าที่รองรับ(self):
        """คะแนนการค้นของหน้าที่ไม่เกี่ยวสูงกว่า ลำดับจึงสลับ — ผลต้องเหมือนกัน"""
        chunks = [page("it66.pdf", 137, IT_TITLE, 0.99),
                  page("it66.pdf", 19, IT_TITLE, 0.20)]
        text, sources = served(IT_REPLY, chunks, IT_Q)
        self.assertEqual([(s["file"], s["page_start"]) for s in sources],
                         [("it66.pdf", 19)], text)

    def test_ด่านตัดหน้าไม่ตัดจนไม่เหลือที่มา(self):
        """ถ้าไม่มีหน้าใดรองรับข้ออ้างเลย ต้องคงชุดเดิมไว้ให้ชั้นตรวจติดป้ายตามจริง"""
        chunks = [page("it66.pdf", 137, IT_TITLE, 0.61)]
        text, sources = served(IT_REPLY, chunks, IT_Q)
        self.assertTrue(sources or "ยังจับคู่คำตอบนี้กับหน้าเอกสารที่รองรับไม่ได้" in text, text)
        if sources:
            self.assertIn("ยังยืนยันคำตอบไม่ได้", text)


class KeepWorkingTests(unittest.TestCase):
    """ข้อ 4 — เกณฑ์ที่ได้มาก่อนหน้านี้ต้องไม่เสีย"""

    def test_แคลคูลัสยังได้หน้าที่มีรายชื่อครบ(self):
        chunks = [page("ma64.pdf", 142, MA_TITLE, 0.63),
                  page("ma64.pdf", 140, MA_TITLE, 0.60)]
        text, sources = served(MA_REPLY, chunks, MA_Q)
        self.assertEqual([(s["file"], s["page_start"]) for s in sources],
                         [("ma64.pdf", 142)], text)
        self.assertIn("ที่มา: ma64.pdf หน้า 142", text)

    def test_หน้าที่รองรับเพียงปีของเล่มไม่นับว่าเกี่ยวข้อง(self):
        """หน้า 140 ไม่มีคำว่าแคลคูลัสเลย แต่มี "พ.ศ. 2564" อยู่ในหัวตารางเปรียบเทียบ

        ข้ออ้างปีจึงรองรับได้จากเนื้อหาหน้านั้นเอง — ถ้านับรวม หน้านี้จะกลายเป็นที่มาของ
        คำตอบเรื่องรายวิชาได้ จึงต้องนับเฉพาะข้ออ้างที่เป็นสาระ (CONTENT_CLAIMS)
        """
        self.assertNotIn("แคลคูลัส", PAGES["ma64.pdf|140"])
        got = supported_by(MA_REPLY, [PAGES["ma64.pdf|140"]])
        self.assertEqual([c.shown for c in got[0]], ["พ.ศ. 2564"])
        self.assertEqual([c.shown for c in got[0] if c.kind in CONTENT_CLAIMS], [])

    def test_รายการที่กระจายสองหน้ายังแสดงครบทั้งสองหน้า(self):
        """แคลคูลัส 1-3 อยู่หน้าหนึ่ง แคลคูลัส 4 อยู่อีกหน้า — ต้องได้ทั้งคู่"""
        p20 = Chunk("ma64.pdf", 20,
                    "2.1) กลุ่มวิชาแกน 30 หน่วยกิต 4091403 แคลคูลัส 1 3(3-0-6) Calculus 1 "
                    "4092403 แคลคูลัส 2 3(3-0-6) Calculus 2 4093407 แคลคูลัส 3 3(3-0-6)",
                    MA_TITLE, 0.57)
        p21 = Chunk("ma64.pdf", 21,
                    "2.2.1) บังคับ 39 หน่วยกิต 4093408 แคลคูลัส 4 3(3-0-6) Calculus 4",
                    MA_TITLE, 0.55)
        text, sources = served(MA_REPLY, [p20, p21], MA_Q)
        self.assertEqual(sorted(s["page_start"] for s in sources), [20, 21], text)

    def test_คำตอบเปรียบเทียบสองหลักสูตรยังได้ที่มาทั้งสองฝั่ง(self):
        cs = Chunk("cs66_brief.pdf", 1,
                   "โครงสร้างหลักสูตร 1. หมวดวิชาศึกษาทั่วไป ไม่น้อยกว่า 30 หน่วยกิต "
                   "2. หมวดวิชาเฉพาะ ไม่น้อยกว่า 94 หน่วยกิต 2.1 กลุ่มวิชาแกน 18 หน่วยกิต "
                   "2.2 กลุ่มวิชาเฉพาะด้าน 54 หน่วยกิต", CS_TITLE, 0.60)
        it = page("it66.pdf", 19, IT_TITLE, 0.58)
        reply = ("วิทยาการคอมพิวเตอร์ พ.ศ. 2566 มีกลุ่มวิชาแกน 18 หน่วยกิต และกลุ่มวิชา"
                 "เฉพาะด้าน 54 หน่วยกิต ส่วนเทคโนโลยีสารสนเทศ พ.ศ. 2566 มีกลุ่มวิชาแกน "
                 "15 หน่วยกิต และกลุ่มวิชาเฉพาะด้าน 57 หน่วยกิต")
        question = "วิทยาการคอมพิวเตอร์กับเทคโนโลยีสารสนเทศ ต่างกันที่โครงสร้างหลักสูตรอย่างไร"
        text, sources = served(reply, [cs, it], question)
        self.assertEqual(sorted(s["file"] for s in sources),
                         ["cs66_brief.pdf", "it66.pdf"], text)

    def test_คำตอบความเรียงยังหาหน้าที่รองรับได้(self):
        it = page("it66.pdf", 19, IT_TITLE, 0.58)
        other = page("it66.pdf", 137, IT_TITLE, 0.70)
        reply = ("หลักสูตรนี้กำหนดกลุ่มวิชาเฉพาะด้าน 57 หน่วยกิต โดยมีกลุ่มเทคโนโลยี"
                 "เพื่องานประยุกต์ 21 หน่วยกิต")
        self.assertEqual(pages_of(reply, [it, other], IT_Q), [19])
        v = verify(reply, [it.content + " · " + IT_TITLE])
        self.assertEqual(v.status, "รองรับครบ", [c.shown for c in v.unsupported])


if __name__ == "__main__":
    unittest.main(verbosity=2)
