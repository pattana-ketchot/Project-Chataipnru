"""
ตรวจคำถามที่เอ่ยถึงหลายหลักสูตร เช่น เปรียบเทียบสองสาขา — ขอบเขตการค้น หลักฐาน และเกณฑ์ของด่านตรวจเอกสาร

เหตุที่ต้องมี: คำถาม "วิทยาการคอมพิวเตอร์กับเทคโนโลยีสารสนเทศต่างกันอย่างไร ..." บนหน้าเว็บจริงได้คำตอบว่าไม่พบ
ข้อมูลใน มคอ.2 ทั้งที่ถามแยกทีละสาขาได้คำตอบครบ ตามรอยแล้วมีสามชั้น
    1. resolve_scope คืนหลักสูตรแรกที่เจอหลักสูตรเดียว ได้เนื้อหาของสาขาแรก 25 ชิ้น สาขาที่สอง 0 ชิ้น
    2. คำค้นที่เหลือหลังตัดชื่อแทบไม่มีเรื่องให้ค้น ชิ้นที่ได้ไม่มีอาชีพหรือวัตถุประสงค์ที่ใช้เทียบกัน
    3. ด่านตรวจเอกสารตีการเปรียบเทียบทุกแบบว่าเป็นการอนุมาน เพราะไม่มีเอกสารเขียนเปรียบเทียบไว้เอง

ใช้ชื่อหลักสูตรหลายคู่ ไม่ผูกกับคู่ใดคู่หนึ่ง ข้อความคำถามแต่งขึ้นสำหรับทดสอบ

    python -m eval.multi_program_scope_check
"""
from __future__ import annotations

import sys
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import app.services.chat as chat  # noqa: E402
import app.services.program_match as program_match  # noqa: E402
from app.services.course_scope import resolve_scope, resolve_scopes  # noqa: E402
from llm import prompts  # noqa: E402


def course(title):
    return SimpleNamespace(id=uuid.uuid4(), title=title, is_active=True)


CS_61 = course("หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาการคอมพิวเตอร์ (พ.ศ. 2561)")
CS_66 = course("หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาการคอมพิวเตอร์ (พ.ศ. 2566)")
IT_66 = course("หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาเทคโนโลยีสารสนเทศ (พ.ศ. 2566)")
MATH = course("หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาคณิตศาสตร์ (พ.ศ. 2569)")
COSM = course("หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาศาสตร์เครื่องสำอาง (พ.ศ. 2566)")
THAI = course("หลักสูตรการแพทย์แผนไทยประยุกต์บัณฑิต (พ.ศ. 2565)")
COURSES = [CS_61, CS_66, IT_66, MATH, COSM, THAI]


class FakeDb:
    def scalars(self, *args, **kwargs):
        return SimpleNamespace(all=lambda: COURSES)

    def execute(self, *args, **kwargs):
        return None


class ScopesChecks(unittest.TestCase):
    def test_คำถามเทียบสองหลักสูตรได้ขอบเขตครบทั้งสอง(self):
        for question, expected in (
            ("คณิตศาสตร์กับวิทยาศาสตร์เครื่องสำอางต่างกันอย่างไร", {"คณิตศาสตร์", "วิทยาศาสตร์เครื่องสำอาง"}),
            ("การแพทย์แผนไทยประยุกต์ต่างจากวิทยาศาสตร์เครื่องสำอางตรงไหน", {"การแพทย์แผนไทยประยุกต์", "วิทยาศาสตร์เครื่องสำอาง"}),
            ("วิทยาการคอมพิวเตอร์กับเทคโนโลยีสารสนเทศเรียนต่างกันไหม", {"วิทยาการคอมพิวเตอร์", "เทคโนโลยีสารสนเทศ"}),
        ):
            scopes = resolve_scopes(FakeDb(), question)
            self.assertEqual({s.matched_name for s in scopes}, expected, question)

    def test_คำค้นตัดชื่อทุกหลักสูตรออก(self):
        scopes = resolve_scopes(FakeDb(), "คณิตศาสตร์กับวิทยาศาสตร์เครื่องสำอางจบไปทำงานต่างกันอย่างไร")
        text = scopes[0].search_text
        self.assertNotIn("คณิตศาสตร์", text)
        self.assertNotIn("เครื่องสำอาง", text)
        self.assertIn("ทำงาน", text)
        self.assertTrue(all(s.search_text == text for s in scopes))

    def test_คำย่อคู่กับชื่อเต็ม(self):
        scopes = resolve_scopes(FakeDb(), "วิทคอมกับเทคโนโลยีสารสนเทศต่างกันยังไง")
        self.assertEqual({s.matched_name for s in scopes}, {"วิทยาการคอมพิวเตอร์", "เทคโนโลยีสารสนเทศ"})
        self.assertNotIn("วิทคอม", scopes[0].search_text)

    def test_แต่ละหลักสูตรรวมทุกฉบับ_และเลือกปีได้(self):
        scopes = {s.matched_name: s for s in resolve_scopes(FakeDb(), "วิทยาการคอมพิวเตอร์กับคณิตศาสตร์ต่างกันไหม")}
        self.assertEqual(set(scopes["วิทยาการคอมพิวเตอร์"].course_ids), {CS_61.id, CS_66.id})
        self.assertEqual(scopes["คณิตศาสตร์"].course_ids, [MATH.id])
        by_year = {s.matched_name: s for s in resolve_scopes(FakeDb(), "วิทยาการคอมพิวเตอร์ พ.ศ. 2566 กับเทคโนโลยีสารสนเทศ")}
        self.assertEqual(by_year["วิทยาการคอมพิวเตอร์"].course_ids, [CS_66.id])

    def test_หลักสูตรเดียวผลเหมือน_resolve_scope_เดิม(self):
        question = "วิทยาศาสตร์เครื่องสำอางจบแล้วทำงานอะไรได้บ้าง"
        many, one = resolve_scopes(FakeDb(), question), resolve_scope(FakeDb(), question)
        self.assertEqual(len(many), 1)
        self.assertEqual((many[0].matched_name, many[0].course_ids, many[0].search_text),
                         (one.matched_name, one.course_ids, one.search_text))
        self.assertEqual(resolve_scopes(FakeDb(), "ค่าเทอมเท่าไหร่"), [])


def chunk(owner, score, tag):
    return SimpleNamespace(chunk_id=f"{owner.id}-{tag}", course_id=owner.id, course_title=owner.title, score=score)


class RetrieveChecks(unittest.TestCase):
    def setUp(self):
        self.search_calls, self.core_calls = [], []
        self._saved = (chat.search_similar_chunks, program_match.newest_core_chunks)

        def fake_search(db, vector, top_k=8, course_ids=None):
            self.search_calls.append((top_k, course_ids))
            owner = next((c for c in COURSES if course_ids and c.id in course_ids), None) or SimpleNamespace(
                id="all", title="ทั้งคลัง")
            # ชิ้นแรกซ้ำกับชิ้นแก่นของหลักสูตร เพื่อตรวจว่าไม่ถูกใส่ซ้ำ
            return [chunk(owner, 0.9, "core-0")] + [chunk(owner, 0.8 - i * 0.01, f"found-{i}") for i in range(top_k - 1)]

        def fake_core(db, course_ids, score):
            self.core_calls.append((tuple(course_ids), score))
            owner = next(c for c in COURSES if c.id in course_ids)
            return [chunk(owner, score, "core-0"), chunk(owner, score, "core-1")]

        chat.search_similar_chunks = fake_search
        program_match.newest_core_chunks = fake_core
        self.connector = SimpleNamespace(embed=lambda text: [0.0])

    def tearDown(self):
        chat.search_similar_chunks, program_match.newest_core_chunks = self._saved

    def test_สองหลักสูตรได้แก่นของหลักสูตรนำหน้าชิ้นที่ค้นเจอของแต่ละหลักสูตร(self):
        chunks = chat._retrieve(FakeDb(), self.connector, "คณิตศาสตร์กับวิทยาศาสตร์เครื่องสำอางต่างกันอย่างไร")
        per = -(-chat.TOP_K_CHUNKS // 2)
        self.assertEqual({top_k for top_k, _ in self.search_calls}, {per})
        self.assertEqual({tuple(ids) for _, ids in self.search_calls}, {(MATH.id,), (COSM.id,)})
        self.assertEqual({ids for ids, _ in self.core_calls}, {(MATH.id,), (COSM.id,)})
        # คะแนนของชิ้นแก่นหลักสูตรคือคะแนนสูงสุดของการค้น ไม่ใช่ค่าที่สูงเกินจริง
        self.assertTrue(all(score == 0.9 for _, score in self.core_calls))
        # จัดกลุ่มตามหลักสูตร แก่นของหลักสูตรมาก่อน และไม่มีชิ้นซ้ำ
        owners = [c.course_id for c in chunks]
        first_owner_end = owners.index(owners[-1])
        self.assertEqual(len(set(owners[:first_owner_end])), 1)
        self.assertEqual([c.chunk_id.split("-", 5)[-1] for c in chunks[:2]], ["core-0", "core-1"])
        self.assertEqual(len({c.chunk_id for c in chunks}), len(chunks))
        self.assertEqual({c.course_title for c in chunks}, {MATH.title, COSM.title})

    def test_หลักสูตรเดียวและไม่ระบุหลักสูตรใช้ทางเดิม(self):
        chat._retrieve(FakeDb(), self.connector, "คณิตศาสตร์เรียนกี่หน่วยกิต")
        self.assertEqual(self.search_calls, [(chat.TOP_K_CHUNKS, [MATH.id])])
        self.search_calls.clear()
        chat._retrieve(FakeDb(), self.connector, "ค่าเทอมเท่าไหร่")
        self.assertEqual(self.search_calls, [(chat.TOP_K_CHUNKS, None)])
        self.assertEqual(self.core_calls, [], "คำถามหลักสูตรเดียวต้องไม่เพิ่มแก่นของหลักสูตร")


class GateChecks(unittest.TestCase):
    class Connector:
        def __init__(self):
            self.systems = []

        def chat(self, messages, **kwargs):
            self.systems.append(messages[0].content)
            return '{"can_answer": true}'

    def test_เลือกเกณฑ์เปรียบเทียบเฉพาะคำถามที่เอ่ยถึงหลายหลักสูตร(self):
        self.assertTrue(chat._compares_programmes(FakeDb(), "คณิตศาสตร์กับวิทยาศาสตร์เครื่องสำอางต่างกันอย่างไร"))
        self.assertFalse(chat._compares_programmes(FakeDb(), "คณิตศาสตร์เรียนกี่หน่วยกิต"))
        self.assertFalse(chat._compares_programmes(FakeDb(), "ค่าเทอมเท่าไหร่"))

    def test_ด่านตรวจใช้พรอมต์ตามชนิดคำถาม(self):
        conn = self.Connector()
        chat._can_answer_from(conn, [], "q", comparison=True)
        chat._can_answer_from(conn, [], "q")
        self.assertEqual(conn.systems, [prompts.GROUNDING_COMPARISON_SYSTEM_PROMPT, prompts.GROUNDING_CHECK_SYSTEM_PROMPT])

    def test_ด่านตรวจคืนเหตุผลพร้อมผลตัดสิน(self):
        class Reply:
            def __init__(self, raw):
                self.raw = raw

            def chat(self, messages, **kwargs):
                if isinstance(self.raw, Exception):
                    raise self.raw
                return self.raw

        verdict = chat._grounding_verdict(Reply('{"reason": "ไม่มีอาชีพของหลักสูตรที่สอง", "can_answer": false}'), [], "q", True)
        self.assertEqual(verdict, (False, "ไม่มีอาชีพของหลักสูตรที่สอง"))
        self.assertFalse(chat._can_answer_from(Reply('{"reason": "x", "can_answer": false}'), [], "q"))
        # ล้มหรืออ่านไม่ได้ ปล่อยผ่านเหมือนเดิม
        self.assertEqual(chat._grounding_verdict(Reply("ไม่ใช่ JSON"), [], "q"), (True, ""))
        from llm.connector import LLMConnectionError
        self.assertEqual(chat._grounding_verdict(Reply(LLMConnectionError("ล่ม")), [], "q"), (True, ""))

    def test_พรอมต์ด่านตรวจทั้งสองแบบขอเหตุผลก่อนผลตัดสิน(self):
        for prompt in (prompts.GROUNDING_CHECK_SYSTEM_PROMPT, prompts.GROUNDING_COMPARISON_SYSTEM_PROMPT):
            self.assertLess(prompt.index('"reason"'), prompt.index('"can_answer"'))

    def test_เกณฑ์ของคำถามหลักสูตรเดียวไม่ถูกผ่อนลง(self):
        """การแก้คำถามเปรียบเทียบต้องไม่ทำให้คำถามหลักสูตรเดียวผ่านด่านตรวจเอกสารง่ายขึ้น"""
        single = prompts.GROUNDING_CHECK_SYSTEM_PROMPT
        self.assertIn("ต้องเดา อนุมาน หรือเปรียบเทียบสิ่งที่เนื้อหาไม่ได้ระบุไว้", single)
        self.assertNotIn("คำถามมีหลายส่วน", single)
        self.assertIn("ไม่มีข้อเท็จจริงในเรื่องที่ถามของหลักสูตรใดหลักสูตรหนึ่ง", prompts.GROUNDING_COMPARISON_SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main(verbosity=2)
