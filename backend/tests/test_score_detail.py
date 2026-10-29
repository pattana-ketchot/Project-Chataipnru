"""
รายละเอียดที่มาของคะแนนในหน้าแนะนำสาขา ต้องตรงกับคะแนนที่แสดง และเป็นของสาขาใบนั้นจริง

    cd backend && python tests/test_score_detail.py

ไม่ต่อฐานข้อมูล ไม่เรียกโมเดลจริง — ใช้ของจำลองแทนทั้งสองอย่าง

ทำไมต้องมีชุดนี้
---------------
หน้าผลลัพธ์เปิด "ทำไมได้คะแนนนี้" ให้ผู้ใช้อ่าน สามอย่างที่ผิดแล้วผู้ใช้ถูกบอกข้อมูลเท็จ

1. **ตัวเลขในรายละเอียดไม่ตรงกับเปอร์เซ็นต์ที่แสดง** — ผู้ใช้คิดตามแล้วไม่ได้เลขเดิม
2. **หลักฐานข้ามสาขาหรือข้ามฉบับ** — ไฟล์/หน้าของสาขาอื่นไปโผล่ในใบนี้ ซึ่งเป็นการ
   อ้างอิงเท็จที่จับได้ยากที่สุด เพราะข้อความรอบข้างยังดูสมเหตุสมผล
3. **โมเดลล่มแล้วรายละเอียดการคำนวณหายไปด้วย** — คะแนนไม่ได้มาจากโมเดล จึงต้องยัง
   อธิบายได้ครบแม้ไม่มีข้อความจาก AI เลย
"""
import os
import sys
import unittest
import uuid
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://unused:unused@127.0.0.1:1/unused")
os.environ.setdefault("JWT_SECRET", "ชุดทดสอบไม่ได้ออก token")
os.environ.setdefault("GEMINI_API_KEY", "คีย์ปลอมสำหรับชุดทดสอบ")

from llm.connector import LLMConnectionError  # noqa: E402

from app.api.routes.web_compat import (_SCORED_FIELDS, _UNSCORED_FIELDS,  # noqa: E402
                                       _answer_rows, _engine)
from app.services import llm_client, program_match  # noqa: E402
from app.services.program_match import (CHUNKS_PER_COURSE, _breakdown_of,  # noqa: E402
                                        _evidence_of, _to_percent, build_match_query,
                                        match_programs)

MATH = uuid.UUID("11111111-1111-1111-1111-111111111111")
ANIMATION = uuid.UUID("22222222-2222-2222-2222-222222222222")

# ชิ้นเอกสารของสองสาขา — คนละไฟล์ คนละหน้า เพื่อให้การสลับกันมองเห็นได้ทันที
CHUNKS = {
    uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001"): (MATH, "มคอ2-คณิตศาสตร์-2565.pdf", 11),
    uuid.UUID("aaaaaaaa-0000-0000-0000-000000000002"): (MATH, "มคอ2-คณิตศาสตร์-2565.pdf", 12),
    uuid.UUID("bbbbbbbb-0000-0000-0000-000000000001"): (ANIMATION, "มคอ2-แอนิเมชัน-2566.pdf", 7),
    uuid.UUID("bbbbbbbb-0000-0000-0000-000000000002"): (ANIMATION, "มคอ2-แอนิเมชัน-2566.pdf", 8),
}
TITLES = {MATH: "วิทยาศาสตรบัณฑิต สาขาวิชาคณิตศาสตร์",
          ANIMATION: "วิทยาศาสตรบัณฑิต สาขาวิชาคอมพิวเตอร์แอนิเมชันและมัลติมีเดีย"}
ANSWERS = {
    "study_track": "วิทย์-คณิต",
    "favorite_subjects": ["คณิตศาสตร์"],
    "interests": ["การวิเคราะห์ข้อมูล"],
    "aptitudes": ["คิดคำนวณ"],
    "career_goal": ["นักวิเคราะห์ข้อมูล"],
    "work_environment": ["ทำงานเป็นทีม"],
}


class _Row:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows

    def mappings(self):
        return _Result([r.__dict__ for r in self._rows])


class _FakeDB:
    """ฐานข้อมูลจำลอง — ตอบตามคำสั่ง SQL ที่ถูกถาม ไม่ได้ต่อฐานจริง"""

    def __init__(self, sims):
        self.sims = sims   # {course_id: [ความใกล้เคียงรายชิ้น เรียงมากไปน้อย]}

    def execute(self, statement, params=None):
        sql = str(statement)
        params = params or {}
        if "array_agg" in sql:
            rows = []
            for course_id, sims in self.sims.items():
                ids = [c for c, v in CHUNKS.items() if v[0] == course_id][:len(sims)]
                rows.append(_Row(course_id=course_id, title=TITLES[course_id],
                                 score=sum(sims) / len(sims), chunk_ids=ids, sims=sims))
            return _Result(rows)
        if "SELECT id, title FROM courses" in sql:
            return _Result([_Row(id=c, title=t) for c, t in TITLES.items()])
        if "original_filename" in sql:
            wanted = {str(i) for i in params["ids"]}
            return _Result([
                _Row(chunk_id=cid, page_number=page, file=name)
                for cid, (_course, name, page) in CHUNKS.items() if str(cid) in wanted
            ])
        if "content LIKE" in sql:            # แก่นของหลักสูตร
            return _Result([])
        if "page_number, content" in sql:    # เนื้อหาของชิ้นหลักฐาน
            return _Result([])
        raise AssertionError("คำสั่ง SQL ที่ชุดทดสอบยังไม่รู้จัก: " + sql[:80])


class _FakeConnector:
    """เวกเตอร์คงที่ และบังคับให้ขั้นเขียนเหตุผลล้มได้ตามต้องการ"""

    answer_token_cap = 512
    chat_model = "gemini-3.5-flash-lite"
    embed_model = "bge-m3"
    provider_name = "gemini"

    def __init__(self, chat_fails=False):
        self.chat_fails = chat_fails
        self.chat_calls = 0

    def embed(self, text):
        # เวกเตอร์ของชื่อสาขาต่างกันตามชื่อ เพื่อให้ title_similarity ไม่เท่ากันทุกใบ
        return [1.0, 0.5] if "คณิตศาสตร์" in text else [0.5, 1.0]

    def chat(self, *_args, **_kwargs):
        self.chat_calls += 1
        if self.chat_fails:
            raise LLMConnectionError("จำลองว่าโมเดลล่ม")
        return "{}"


class _ScoreDetailBase(unittest.TestCase):
    def setUp(self):
        program_match._TITLE_CACHE = None   # เวกเตอร์ชื่อหลักสูตรถูกแคชไว้ตลอดอายุโปรเซส
        llm_client.reset_chat_model()


class BreakdownMathTests(_ScoreDetailBase):
    def test_ค่าที่ส่งออกคำนวณย้อนกลับได้เปอร์เซ็นต์เดิม(self):
        """ผู้ใช้คิดตามสูตรที่หน้าเว็บแสดงแล้วต้องได้เลขเดียวกับที่เห็นบนการ์ด"""
        weight = program_match._TITLE_WEIGHT
        for content, title in [(0.62, 0.41), (0.30, 0.20), (0.71, 0.80), (0.55, 0.55)]:
            blended = (1 - weight) * content + weight * title
            s = {"content_similarity": content, "title_similarity": title,
                 "score": blended, "chunk_ids": [uuid.uuid4()] * 5}
            b = _breakdown_of(s)
            again = ((1 - b["title_weight"]) * b["content_similarity"]
                     + b["title_weight"] * b["title_similarity"])
            ratio = (again - b["percent_floor"]) / (b["percent_ceiling"] - b["percent_floor"])
            self.assertEqual(max(0, min(100, round(ratio * 100))), b["percent"],
                             "คำนวณย้อนกลับไม่ตรงที่ {0}/{1}".format(content, title))
            self.assertEqual(b["percent"], _to_percent(blended))

    def test_ไม่ส่งคีย์หรือข้อมูลภายในที่ไม่เกี่ยวออกไป(self):
        s = {"content_similarity": 0.6, "title_similarity": 0.4, "score": 0.5,
             "chunk_ids": [uuid.uuid4()] * 7}
        self.assertEqual(set(_breakdown_of(s)), {
            "content_similarity", "title_similarity", "title_weight", "blended_score",
            "percent", "percent_floor", "percent_ceiling", "chunks_used"})
        # นับเฉพาะชิ้นที่ถูกใช้จริง ไม่ใช่จำนวนที่ค้นเจอทั้งหมด
        self.assertEqual(_breakdown_of(s)["chunks_used"], CHUNKS_PER_COURSE)


class EvidenceIsolationTests(_ScoreDetailBase):
    def _sources(self):
        return {str(cid): {"file": name, "page": page}
                for cid, (_c, name, page) in CHUNKS.items()}

    def test_หลักฐานของแต่ละสาขาไม่ข้ามไปอีกสาขา(self):
        math_ids = [c for c, v in CHUNKS.items() if v[0] == MATH]
        anim_ids = [c for c, v in CHUNKS.items() if v[0] == ANIMATION]
        sources = self._sources()
        math = _evidence_of({"chunk_ids": math_ids, "sims": [0.6, 0.5]}, sources)
        anim = _evidence_of({"chunk_ids": anim_ids, "sims": [0.4, 0.3]}, sources)

        self.assertEqual({i["file"] for i in math}, {"มคอ2-คณิตศาสตร์-2565.pdf"})
        self.assertEqual({i["file"] for i in anim}, {"มคอ2-แอนิเมชัน-2566.pdf"})
        self.assertEqual([i["page"] for i in math], [11, 12])
        self.assertEqual([i["similarity"] for i in anim], [0.4, 0.3])

    def test_ชิ้นที่ไม่รู้ที่มาถูกตัดออก_ไม่เดาไฟล์ให้(self):
        out = _evidence_of({"chunk_ids": [uuid.uuid4()], "sims": [0.9]}, self._sources())
        self.assertEqual(out, [])

    def test_ความใกล้เคียงจับคู่กับชิ้นของตัวเอง(self):
        ids = [c for c, v in CHUNKS.items() if v[0] == MATH]
        out = _evidence_of({"chunk_ids": ids, "sims": [0.61, 0.42]}, self._sources())
        self.assertEqual([(i["page"], i["similarity"]) for i in out], [(11, 0.61), (12, 0.42)])


class WholeResultTests(_ScoreDetailBase):
    def _match(self, chat_fails=False):
        connector = _FakeConnector(chat_fails=chat_fails)
        db = _FakeDB({MATH: [0.62, 0.58], ANIMATION: [0.47, 0.44]})
        program_match.get_llm_connector = lambda: connector      # แทนตัวเชื่อมต่อจริง
        return match_programs(db, ANSWERS, limit=5), connector

    def test_ทุกใบมีรายละเอียดที่ตรงกับเปอร์เซ็นต์ของใบตัวเอง(self):
        matches, _ = self._match()
        self.assertEqual(len(matches), 2)
        for m in matches:
            self.assertEqual(m.breakdown["percent"], m.match_percent)
            self.assertEqual(m.breakdown["blended_score"], round(m.score, 4))

    def test_ไฟล์หลักฐานของทุกใบเป็นเอกสารของสาขาใบนั้น(self):
        matches, _ = self._match()
        for m in matches:
            own = {CHUNKS[c][1] for c in CHUNKS if CHUNKS[c][0] == m.course_id}
            self.assertTrue(m.evidence, "ใบนี้ไม่มีหลักฐานเลย")
            self.assertEqual({i["file"] for i in m.evidence}, own)
            self.assertEqual([i["page"] for i in m.evidence],
                             [CHUNKS[c][2] for c in m.evidence_chunk_ids])

    def test_โมเดลล่ม_ยังได้คะแนนและรายละเอียดการคำนวณครบ(self):
        matches, connector = self._match(chat_fails=True)
        self.assertEqual(connector.chat_calls, 1)
        for m in matches:
            self.assertEqual(m.rationale, "")          # ไม่มีข้อความจากโมเดล
            self.assertEqual(m.breakdown["percent"], m.match_percent)
            self.assertTrue(m.evidence)
            self.assertEqual(m.breakdown["chunks_used"], 2)

    def test_สององค์ประกอบต่างกันจริง_ไม่ใช่ค่าเดียวซ้ำสองช่อง(self):
        matches, _ = self._match()
        top = matches[0]
        self.assertNotEqual(top.breakdown["content_similarity"],
                            top.breakdown["title_similarity"])


class AnswerDisclosureTests(_ScoreDetailBase):
    def test_ส่งเฉพาะคำตอบที่เข้าไปคิดคะแนนจริง(self):
        used = _answer_rows(ANSWERS, _SCORED_FIELDS)
        self.assertEqual([r["field"] for r in used],
                         ["favorite_subjects", "interests", "aptitudes", "career_goal"])
        query = build_match_query(ANSWERS)
        for row in used:
            for value in row["values"]:
                self.assertIn(value, query)

    def test_คำตอบที่ไม่ได้คิดคะแนนต้องไม่ถูกนับว่าใช้คิดคะแนน(self):
        not_scored = _answer_rows(ANSWERS, _UNSCORED_FIELDS)
        self.assertEqual([r["field"] for r in not_scored], ["study_track", "work_environment"])
        query = build_match_query(ANSWERS)
        for row in not_scored:
            for value in row["values"]:
                self.assertNotIn(value, query)

    def test_ช่องที่ผู้ใช้ไม่ได้ตอบไม่ถูกส่งไปเป็นบรรทัดว่าง(self):
        rows = _answer_rows({"interests": [], "aptitudes": ["คิดคำนวณ"], "career_goal": None},
                            _SCORED_FIELDS)
        self.assertEqual([r["field"] for r in rows], ["aptitudes"])


class EmbeddingLabelTests(_ScoreDetailBase):
    def test_ป้ายรุ่นที่เทียบความคล้ายมาจากตัวที่แปลงเวกเตอร์จริง(self):
        llm_client._SplitConnector(_FakeConnector(), _FakeConnector()).embed("ทดสอบ")
        self.assertEqual(_engine(explained=False, embedded=True)["embedding"],
                         {"provider": "ollama", "model": "bge-m3"})

    def test_ไม่ได้เทียบความคล้ายในคำขอนี้_ต้องไม่ติดป้าย(self):
        self.assertIsNone(_engine(explained=False, embedded=True)["embedding"])

    def test_ผลที่คะแนนไม่ได้มาจากเวกเตอร์ต้องไม่ติดป้ายนี้(self):
        """หน้าเปรียบเทียบไม่ได้ให้คะแนนด้วยเวกเตอร์ จึงต้องไม่มีบรรทัดนี้"""
        llm_client._SplitConnector(_FakeConnector(), _FakeConnector()).embed("ทดสอบ")
        self.assertIsNone(_engine(explained=True)["embedding"])

    def test_ล้างค่าเมื่อเริ่มคำขอใหม่(self):
        llm_client._SplitConnector(_FakeConnector(), _FakeConnector()).embed("ทดสอบ")
        llm_client.reset_chat_model()
        self.assertIsNone(llm_client.embed_model_used())


if __name__ == "__main__":
    run = unittest.main(verbosity=2, exit=False)
    raise SystemExit(0 if run.result.wasSuccessful() else 1)
