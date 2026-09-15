"""
ตรวจหลักฐานและพฤติกรรมของคำถามที่เอ่ยถึงหลายหลักสูตร — Phase 2 stabilization (docs/MKO_PHASE2_SHADOW_EVAL.md ข้อ 5–6)

    python -m eval.comparison_evidence_check

ส่วนแรกใช้แถวปลอม ไม่ต้องมีฐานข้อมูล: การเลือกหลักฐานรายด้าน ฉบับปี สารบัญ ชิ้นที่อ่านไม่ออก และความสอดคล้องของ prompt
ส่วน prepare_answer ใช้ตัวปลอมทั้งหมด: เกณฑ์ของคำถามหลายหลักสูตร คำถามหลักสูตรเดียวต้องได้ prompt เดิมทุกตัวอักษร และ
คำถามนอกขอบเขตยังถูกปฏิเสธ
ส่วนท้ายใช้ฐานข้อมูล local ที่มี course_chunks ชุดเดียวกับ production (ข้ามถ้าไม่มี) และ embedding bge-m3 ของ Ollama ในเครื่อง
(ข้ามถ้าต่อไม่ได้) ทุกหลักสูตรและทุกคู่หลักสูตรมาจากฐานข้อมูล ไม่มีชื่อหลักสูตรผูกไว้ ยกเว้นคำถามถดถอยที่กำหนดในคำขอแก้ไข
ไม่เรียกโมเดลภาษา
"""
from __future__ import annotations

import itertools
import os
import sys
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres@127.0.0.1:55432/course_advisor")
os.environ.setdefault("JWT_SECRET", "local-test-only")
os.environ.setdefault("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
os.environ.setdefault("EMBED_MODEL", "bge-m3")
os.environ.setdefault("EMBED_DIM", "1024")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import app.services.chat as chat  # noqa: E402
from app.services import comparison_evidence as ce  # noqa: E402
from app.services.course_scope import _distinctive_name, resolve_scopes  # noqa: E402
from app.services.program_match import _looks_like_table_of_contents  # noqa: E402
from llm import prompts  # noqa: E402

NEW = SimpleNamespace(id=uuid.uuid4(), title="หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาศาสตร์ทดสอบ (พ.ศ. 2569)")
OLD = SimpleNamespace(id=uuid.uuid4(), title="หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาศาสตร์ทดสอบ (พ.ศ. 2564)")
OTHER = SimpleNamespace(id=uuid.uuid4(), title="หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาศาสตร์เปรียบเทียบ (พ.ศ. 2566)")

PHILOSOPHY_AND_OBJECTIVES = "1. ปรัชญา ความสำคัญ และวัตถุประสงค์ของหลักสูตร\n1.1 ปรัชญา\nผลิตบัณฑิต...\n1.3 วัตถุประสงค์ของหลักสูตร\n1) ..."
CAREERS = "8. อาชีพที่สามารถประกอบได้หลังสำเร็จการศึกษา\n8.1 นักวิจัย\n8.2 ..."
STRUCTURE = "3.1.2 โครงสร้างหลักสูตร\nหมวดวิชาศึกษาทั่วไป ไม่น้อยกว่า 30 หน่วยกิต"
TOC = "สารบัญ\nวัตถุประสงค์ของหลักสูตร ........ 5\nอาชีพที่สามารถประกอบได้หลังสำเร็จการศึกษา ........ 7\n........ 9"
GARBLED = "(~U\"'l\"M,~,.,vriiltn ut'W~1tH) 'i)~D5n11\\l;;'.J~'1$...\",n11\"\"\\l \"\"\"ull!mmu,KtJ,,,,,II'D\"'·"
# รายการวิชาในเอกสารจริงยาวพอ ถ้าสั้นและมีตัวเลขเป็นสัดส่วนสูง ตัวตรวจสารบัญเดิมจะนับเป็นสารบัญ
PROGRAMMING_COURSE = ("4121202 การเขียนโปรแกรมภาษาคอมพิวเตอร์ 1 Computer Language Programming 1 "
                      "ขั้นตอนการเขียนและการพัฒนาโปรแกรม การเขียนผังงาน การวิเคราะห์และออกแบบขั้นตอนวิธี")


def row(owner, content, page, idx, doc=None):
    return SimpleNamespace(id=uuid.uuid4(), course_id=owner.id, document_id=doc or owner.id, chunk_index=idx,
                           page_number=page, content=content, title=owner.title)


class RowsDb:
    """ฐานข้อมูลปลอมที่ตอบสอง query ของ programme_evidence"""

    def __init__(self, rows):
        self.rows = rows

    def execute(self, stmt, params):
        if "ANY(:ids)" in str(stmt):
            ids = set(params["ids"])
            likes = [params[f"f{i}"].strip("%") for i in range(len(ce.FIELDS))]
            hits = sorted((r for r in self.rows if r.course_id in ids and any(k in r.content for k in likes)),
                          key=lambda r: (r.page_number, r.chunk_index))
            return SimpleNamespace(all=lambda: hits)
        match = next((r for r in self.rows if r.document_id == params["doc"] and r.chunk_index == params["idx"]), None)
        return SimpleNamespace(first=lambda: match)


class FieldMatcherChecks(unittest.TestCase):
    def field(self, key):
        return next(f for f in ce.FIELDS if f.key == key)

    def test_philosophy_is_a_heading_line_not_a_course_description(self):
        matches = self.field("philosophy").matches
        for text in ("1.1 ปรัชญา\nผลิตบัณฑิต", "ปรัชญาของหลักสูตร\n...", "1. ปรัชญา ความสำคัญ และวัตถุประสงค์ของหลักสูตร"):
            self.assertTrue(matches(text), text)
        for text in ("0020101 ปรัชญา แนวคิดเกี่ยวกับสิทธิและหน้าที่", "ปรัชญาเศรษฐกิจพอเพียง\nการประยุกต์", "ปริญญาปรัชญาดุษฎีบัณฑิต"):
            self.assertFalse(matches(text), text)

    def test_structure_is_a_heading_line_with_credits(self):
        matches = self.field("structure").matches
        self.assertTrue(matches(STRUCTURE))
        self.assertFalse(matches("โครงสร้างหลักสูตร มคอ. 1 สาขาคอมพิวเตอร์ พ.ศ. 2552\nหน่วยกิต"))
        self.assertFalse(matches("3.1.2 โครงสร้างหลักสูตร\nรายละเอียด"))

    def test_garbled_detection_threshold(self):
        self.assertTrue(ce.is_garbled(GARBLED))
        self.assertFalse(ce.is_garbled("course aims to develop listening, reading, speaking and writing skills; basic 3D modeling"))
        self.assertFalse(ce.is_garbled(PHILOSOPHY_AND_OBJECTIVES))


class ProgrammeEvidenceChecks(unittest.TestCase):
    def test_each_field_comes_from_the_newest_edition_that_has_it_and_keeps_its_year(self):
        db = RowsDb([
            row(NEW, PHILOSOPHY_AND_OBJECTIVES, page=1, idx=0),
            row(NEW, STRUCTURE, page=2, idx=2),
            row(OLD, PHILOSOPHY_AND_OBJECTIVES, page=13, idx=20),
            row(OLD, CAREERS, page=8, idx=12),
        ])
        evidence = ce.programme_evidence(db, [NEW.id, OLD.id], score=0.5)
        by_title = {}
        for c in evidence:
            by_title.setdefault(c.course_title, []).append(c.content)
        self.assertEqual(by_title[NEW.title], [PHILOSOPHY_AND_OBJECTIVES, STRUCTURE])
        # ฉบับล่าสุดไม่มีหัวข้ออาชีพ จึงใช้ฉบับก่อนหน้า และชิ้นนั้นยังมีปีของฉบับก่อนหน้ากำกับ
        self.assertEqual(by_title[OLD.title], [CAREERS])
        self.assertTrue(all(c.score == 0.5 for c in evidence))

    def test_following_chunk_is_included_once_and_toc_and_garbled_are_skipped(self):
        db = RowsDb([
            row(NEW, TOC, page=1, idx=0),
            row(NEW, GARBLED + "\nอาชีพที่สามารถประกอบได้หลังสำเร็จการศึกษา", page=2, idx=1),
            row(NEW, CAREERS, page=7, idx=5),
            row(NEW, "8.3 นักวิชาการ\n8.4 ผู้ประกอบการ", page=7, idx=6),
            row(NEW, PHILOSOPHY_AND_OBJECTIVES, page=9, idx=9),
        ])
        contents = [c.content for c in ce.programme_evidence(db, [NEW.id], score=0.4)]
        self.assertNotIn(TOC, contents)
        self.assertFalse(any(ce.is_garbled(c) for c in contents))
        self.assertEqual(contents.count(PHILOSOPHY_AND_OBJECTIVES), 1)
        self.assertEqual(contents[:1], [PHILOSOPHY_AND_OBJECTIVES])
        self.assertIn("8.3 นักวิชาการ\n8.4 ผู้ประกอบการ", contents)

    def test_editions_of_the_same_year_are_all_used_and_labelled_by_degree(self):
        master = SimpleNamespace(id=uuid.uuid4(), title="หลักสูตรวิทยาศาสตรมหาบัณฑิต สาขาวิชาศาสตร์ทดสอบ (พ.ศ. 2568)")
        doctor = SimpleNamespace(id=uuid.uuid4(), title="หลักสูตรปรัชญาดุษฎีบัณฑิต สาขาวิชาศาสตร์ทดสอบ (พ.ศ. 2568)")
        db = RowsDb([row(master, CAREERS, page=8, idx=3), row(doctor, CAREERS.replace("นักวิจัย", "อาจารย์"), page=8, idx=3)])
        evidence = ce.programme_evidence(db, [master.id, doctor.id], score=0.5)
        self.assertEqual({c.course_title for c in evidence}, {master.title, doctor.title})
        note = ce.describe_evidence(evidence + [SimpleNamespace(course_title=OTHER.title, content=CAREERS)])
        self.assertIn("หลักสูตรวิทยาศาสตรมหาบัณฑิต พ.ศ. 2568", note)
        self.assertIn("หลักสูตรปรัชญาดุษฎีบัณฑิต พ.ศ. 2568", note)

    def test_describe_evidence_names_fields_years_and_gaps(self):
        chunks = [
            SimpleNamespace(course_title=NEW.title, content=PHILOSOPHY_AND_OBJECTIVES),
            SimpleNamespace(course_title=OLD.title, content=CAREERS),
            SimpleNamespace(course_title=OTHER.title, content=PHILOSOPHY_AND_OBJECTIVES),
        ]
        note = ce.describe_evidence(chunks)
        self.assertIn("ศาสตร์ทดสอบ: ปรัชญา (พ.ศ. 2569); วัตถุประสงค์ (พ.ศ. 2569); อาชีพหลังสำเร็จการศึกษา (พ.ศ. 2564)", note)
        self.assertIn("ศาสตร์เปรียบเทียบ: ปรัชญา (พ.ศ. 2566); วัตถุประสงค์ (พ.ศ. 2566); อาชีพหลังสำเร็จการศึกษา (ไม่พบในเนื้อหาที่ค้นได้)", note)
        self.assertEqual(ce.describe_evidence(chunks[:2]), "", "หลักสูตรเดียวไม่ต้องมีสรุป")


class PromptConsistencyChecks(unittest.TestCase):
    def test_gate_and_writer_share_the_comparison_criteria(self):
        gate, writer = prompts.GROUNDING_COMPARISON_SYSTEM_PROMPT, prompts.CHAT_COMPARISON_RULES
        for gate_clause, writer_clause in (
            ("ข้อเท็จจริงของทุกหลักสูตรเพียงบางด้าน", "เทียบเฉพาะด้านที่เนื้อหามีข้อเท็จจริงของทุกหลักสูตร"),
            ("ตัดสินเชิงปริมาณหรือจัดอันดับ", "ตัดสินเชิงปริมาณหรือจัดอันดับ"),
            ("ยังจัดอันดับจากเอกสารไม่ได้", "ยังสรุปจากเอกสารที่มีไม่ได้"),
            ("ต้องเดาหรืออนุมานข้อเท็จจริงที่เนื้อหาไม่ได้ระบุไว้", "ห้ามสรุปความแตกต่าง"),
        ):
            self.assertIn(gate_clause, gate)
            self.assertIn(writer_clause, writer)
        self.assertIn("ห้ามเดาหรือจัดอันดับเอง", writer)
        self.assertIn("ระบุปีของฉบับ", writer)

    def test_single_programme_prompts_are_untouched(self):
        self.assertNotIn("หลายหลักสูตร", prompts.CHAT_SYSTEM_PROMPT)
        self.assertNotIn("จัดอันดับ", prompts.GROUNDING_CHECK_SYSTEM_PROMPT)
        self.assertNotIn("คำถามมีหลายส่วน", prompts.GROUNDING_CHECK_SYSTEM_PROMPT)


COURSES = [
    SimpleNamespace(id=uuid.uuid4(), title="หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาการคอมพิวเตอร์ (พ.ศ. 2566)", is_active=True),
    SimpleNamespace(id=uuid.uuid4(), title="หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาเทคโนโลยีสารสนเทศ (พ.ศ. 2566)", is_active=True),
    SimpleNamespace(id=uuid.uuid4(), title="หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาคณิตศาสตร์ (พ.ศ. 2564)", is_active=True),
]


class CatalogueDb:
    def scalars(self, *args, **kwargs):
        return SimpleNamespace(all=lambda: COURSES)

    def execute(self, *args, **kwargs):
        return SimpleNamespace(all=lambda: [SimpleNamespace(title=c.title) for c in COURSES])


class PrepareAnswerChecks(unittest.TestCase):
    def setUp(self):
        self.gate_calls = []
        self.gate_verdict = True
        self.retrieved = []
        self.saved_names = chat._PROGRAM_NAMES
        chat._PROGRAM_NAMES = None

        self.extra_content = None
        self.only_first_programme = False

        def fake_retrieve(db, connector, question):
            scopes = resolve_scopes(db, question)
            if not scopes:
                self.retrieved = [SimpleNamespace(chunk_id=uuid.uuid4(), course_id=None, course_title="ทั้งคลัง",
                                                  page_number=1, content="ไม่เกี่ยวข้อง", score=0.3)]
                return self.retrieved
            self.retrieved = []
            for scope in scopes[:1] if self.only_first_programme else scopes:
                owner = next(c for c in COURSES if c.id in scope.course_ids)
                for content in (PHILOSOPHY_AND_OBJECTIVES, CAREERS, *([self.extra_content] if self.extra_content else [])):
                    self.retrieved.append(SimpleNamespace(chunk_id=uuid.uuid4(), course_id=owner.id, course_title=owner.title,
                                                          page_number=1, content=content, score=0.8))
            return self.retrieved

        def fake_gate(connector, chunks, question, comparison=False, note=""):
            self.gate_calls.append((comparison, note))
            return self.gate_verdict

        for p in (
            mock.patch.object(chat, "_load_session", return_value=SimpleNamespace(id=uuid.uuid4())),
            mock.patch.object(chat, "_load_history", return_value=[]),
            mock.patch.object(chat, "corpus_version", return_value="test"),
            mock.patch.object(chat, "cache_lookup", return_value=None),
            mock.patch.object(chat, "get_llm_connector", return_value=object()),
            mock.patch.object(chat, "_refinement_of_recommendation", return_value=None),
            mock.patch.object(chat, "_recommendation_intent", return_value=None),
            mock.patch.object(chat, "_names_an_unknown_program", return_value=None),
            mock.patch.object(chat, "_needs_a_program_named", return_value=False),
            mock.patch.object(chat, "_is_about_scope", return_value=False),
            mock.patch.object(chat, "_retrieve", side_effect=fake_retrieve),
            mock.patch.object(chat, "_can_answer_from", side_effect=fake_gate),
        ):
            p.start()
            self.addCleanup(p.stop)

    def tearDown(self):
        chat._PROGRAM_NAMES = self.saved_names

    def ask(self, message):
        return chat.prepare_answer(CatalogueDb(), uuid.uuid4(), None, message, None)

    def test_comparison_with_evidence_for_every_programme_passes_without_the_model_gate(self):
        """เดิมให้โมเดลตัดสิน ตอนนี้ผลตัดสินมาจากหลักฐานด้วยโค้ด (docs/MKO_PHASE2_MODEL_VALIDATION.md เคส 6)"""
        p = self.ask("วิทยาการคอมพิวเตอร์กับเทคโนโลยีสารสนเทศต่างกันอย่างไร")
        self.assertEqual(p.status, "answered")
        self.assertEqual(p.messages[0].content, f"{prompts.CHAT_SYSTEM_PROMPT}\n\n{prompts.CHAT_COMPARISON_RULES}")
        note = ce.describe_evidence(self.retrieved)
        self.assertTrue(note)
        self.assertEqual(self.gate_calls, [])
        self.assertIn(note, p.messages[-1].content)
        self.assertIn("ตรวจแล้วว่าเนื้อหามีหัวข้อที่เทียบกันได้อย่างน้อยหนึ่งด้านของทุกหลักสูตรที่ถาม", p.messages[-1].content)

    def test_ranking_question_with_topic_evidence_passes_and_tells_the_writer_not_to_rank(self):
        self.extra_content = PROGRAMMING_COURSE
        p = self.ask("วิทยาการคอมพิวเตอร์กับเทคโนโลยีสารสนเทศ สาขาไหนเรียนเขียนโปรแกรมมากกว่ากัน")
        self.assertEqual((p.status, self.gate_calls), ("answered", []))
        self.assertIn('ตรวจแล้วว่าเนื้อหามีเรื่อง "เขียนโปรแกรม" ของทุกหลักสูตรที่ถาม', p.messages[-1].content)
        self.assertIn("ยังสรุปไม่ได้ว่าหลักสูตรใดมากกว่า", p.messages[-1].content)

    def test_programme_without_usable_evidence_is_not_found_without_the_model_gate(self):
        self.only_first_programme = True
        p = self.ask("วิทยาการคอมพิวเตอร์กับเทคโนโลยีสารสนเทศต่างกันอย่างไร")
        self.assertEqual((p.status, p.canned, self.gate_calls), ("not_found", prompts.NOT_FOUND_REPLY, []))

    def test_single_programme_prompt_is_identical_to_before(self):
        question = "หลักสูตรคณิตศาสตร์เรียนกี่หน่วยกิต"
        p = self.ask(question)
        self.assertEqual(p.messages[0].content, prompts.CHAT_SYSTEM_PROMPT)
        self.assertEqual(p.messages[-1].content, prompts.build_chat_prompt(chat._format_chunks(self.retrieved), question))
        self.assertEqual(self.gate_calls, [(False, "")])

    def test_gate_rejection_still_returns_not_found(self):
        self.gate_verdict = False
        p = self.ask("วิทยาการคอมพิวเตอร์กับเทคโนโลยีสารสนเทศ สาขาไหนเรียนเขียนโปรแกรมมากกว่ากัน")
        self.assertEqual((p.status, p.canned, p.messages), ("not_found", prompts.NOT_FOUND_REPLY, []))

    def test_out_of_scope_is_still_refused_without_calling_the_gate(self):
        p = self.ask("ทีมลิเวอร์พูลเป็นยังไงบ้าง")
        self.assertEqual((p.status, p.canned), ("out_of_scope", prompts.OUT_OF_SCOPE_REPLY))
        self.assertEqual(self.gate_calls, [])



def chunk_of(title, content):
    return SimpleNamespace(course_title=title, content=content)


A_TITLE = "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาศาสตร์ทดสอบ (พ.ศ. 2566)"
B_TITLE = "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาศาสตร์เปรียบเทียบ (พ.ศ. 2566)"
A, B = "ศาสตร์ทดสอบ", "ศาสตร์เปรียบเทียบ"


class ComparisonSupportChecks(unittest.TestCase):
    """ผลตัดสินต้องมาจากหลักฐานและคำถามเท่านั้น เรียกซ้ำได้ผลเดิม"""

    def decide(self, question, a_contents, b_contents):
        chunks = [chunk_of(A_TITLE, c) for c in a_contents] + [chunk_of(B_TITLE, c) for c in b_contents]
        first = ce.comparison_support(question, [A, B], chunks)
        self.assertEqual(first, ce.comparison_support(question, [A, B], chunks), "ต้องได้ผลเดิมทุกครั้ง")
        return first

    def test_topic_found_for_every_programme_is_supported_and_flags_ranking(self):
        found = self.decide(f"{A}กับ{B} สาขาไหนเรียนเขียนโปรแกรมมากกว่ากัน",
                            [PROGRAMMING_COURSE], ["ทักษะการเขียน โปรแกรม คอมพิวเตอร์ แนวคิดการแก้ปัญหาและการออกแบบขั้นตอนวิธี"])
        self.assertEqual((found.decision, found.topic, found.field, found.ranking), (ce.SUPPORTED, "เขียนโปรแกรม", None, True))
        self.assertIn("ยังสรุปไม่ได้ว่าหลักสูตรใดมากกว่า", found.note_line())

    def test_topic_missing_in_one_programme_goes_to_the_model_gate(self):
        found = self.decide(f"{A}กับ{B} สาขาไหนมีทุนการศึกษามากกว่ากัน", ["ทุนการศึกษาของคณะ"], [CAREERS])
        self.assertEqual(found.decision, ce.UNDETERMINED)
        self.assertEqual(found.note_line(), "")

    def test_programme_with_only_unusable_chunks_is_missing(self):
        found = self.decide(f"{A}กับ{B}ต่างกันอย่างไร", [PHILOSOPHY_AND_OBJECTIVES], [TOC, GARBLED])
        self.assertEqual(found.decision, ce.MISSING_PROGRAMME)

    def test_field_questions_use_the_heading_of_that_field(self):
        supported = self.decide(f"{A}กับ{B}จบไปทำงานต่างกันอย่างไร", [CAREERS], [CAREERS])
        self.assertEqual((supported.decision, supported.field), (ce.SUPPORTED, "careers"))
        lacking = self.decide(f"{A}กับ{B}จบไปทำงานต่างกันอย่างไร", [CAREERS], [PHILOSOPHY_AND_OBJECTIVES])
        self.assertEqual((lacking.decision, lacking.field), (ce.UNDETERMINED, "careers"))

    def test_general_comparison_needs_a_common_field(self):
        self.assertEqual(self.decide(f"{A}กับ{B}ต่างกันอย่างไร", [CAREERS], [CAREERS]).decision, ce.SUPPORTED)
        self.assertEqual(self.decide(f"{A}กับ{B}ต่างกันอย่างไร", [CAREERS], [PHILOSOPHY_AND_OBJECTIVES]).decision,
                         ce.UNDETERMINED)

    def test_short_or_missing_subjects_are_not_decided_by_text(self):
        self.assertEqual(self.decide(f"{A}กับ{B} สาขาไหนมากกว่ากัน", [CAREERS], [CAREERS]).decision, ce.UNDETERMINED)
        self.assertEqual(self.decide(f"{A}กับ{B} สาขาไหนทุนมากกว่ากัน", ["ทุน"], ["ทุน"]).decision, ce.UNDETERMINED)
        ai = self.decide(f"{A}กับ{B} สาขาไหนเรียน AI มากกว่ากัน", ["วิชา AI เบื้องต้น"], ["course aims to maintain"])
        self.assertEqual(ai.decision, ce.UNDETERMINED, "คำอังกฤษต้องตรงทั้งคำ ไม่ใช่ส่วนหนึ่งของคำอื่น")


def _local_db():
    from sqlalchemy import text

    from app.db.session import SessionLocal

    try:
        db = SessionLocal()
        if db.execute(text("SELECT count(*) FROM course_chunks")).scalar() == 0:
            db.close()
            return None
        return db
    except Exception:  # noqa: BLE001
        return None


class RealCorpusEvidenceChecks(unittest.TestCase):
    """course_chunks ชุดเดียวกับ production ในฐานข้อมูล local"""

    @classmethod
    def setUpClass(cls):
        from sqlalchemy import text

        cls.db = _local_db()
        if cls.db is None:
            raise unittest.SkipTest("ฐานข้อมูล local ไม่มี course_chunks")
        rows = cls.db.execute(text("SELECT id, title FROM courses WHERE is_active")).all()
        cls.programmes = {}
        cls.titles = {}
        for course_id, title in rows:
            cls.programmes.setdefault(_distinctive_name(title), []).append(course_id)
            cls.titles[course_id] = title
        cls.evidence = {name: ce.programme_evidence(cls.db, ids, score=0.5) for name, ids in cls.programmes.items()}

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def fields_of(self, chunks):
        return {f.key for f in ce.FIELDS for c in chunks if f.matches(c.content)}

    def test_every_programme_has_usable_evidence_from_its_own_editions(self):
        self.assertGreater(len(self.programmes), 10)
        for name, chunks in self.evidence.items():
            with self.subTest(programme=name):
                self.assertTrue(chunks)
                self.assertTrue(all(c.course_id in self.programmes[name] for c in chunks))
                self.assertTrue(all(c.course_title == self.titles[c.course_id] for c in chunks))
                self.assertFalse(any(ce.is_garbled(c.content) or _looks_like_table_of_contents(c.content) for c in chunks))

    def test_each_field_comes_from_the_newest_edition_that_has_it(self):
        from sqlalchemy import text

        for name, ids in self.programmes.items():
            rows = self.db.execute(text("SELECT course_id, content FROM course_chunks WHERE course_id = ANY(:ids)"),
                                   {"ids": ids}).all()
            for field in ce.FIELDS:
                editions = {r.course_id for r in rows
                            if field.matches(r.content) and not ce.is_garbled(r.content)
                            and not _looks_like_table_of_contents(r.content)}
                if not editions:
                    continue
                newest_year = max(ce.edition_year(self.titles[cid]) or 0 for cid in editions)
                # ฉบับที่ปีเท่ากันต้องได้ทุกฉบับ ไม่ใช่ฉบับใดฉบับหนึ่ง
                expected = {cid for cid in editions if (ce.edition_year(self.titles[cid]) or 0) == newest_year}
                with self.subTest(programme=name, field=field.key):
                    for cid in expected:
                        self.assertTrue(any(c.course_id == cid and field.matches(c.content) for c in self.evidence[name]),
                                        self.titles[cid])
                    older = {c.course_id for c in self.evidence[name] if field.matches(c.content)} - editions
                    self.assertEqual(older, set())

    def test_general_comparison_of_every_pair_is_supported_by_code(self):
        for a, b in itertools.combinations(sorted(self.evidence), 2):
            with self.subTest(pair=(a, b)):
                found = ce.comparison_support(f"{a}กับ{b}ต่างกันอย่างไร", [a, b], self.evidence[a] + self.evidence[b])
                self.assertEqual(found.decision, ce.SUPPORTED, found.reason)

    def test_every_pair_of_programmes_has_a_field_to_compare(self):
        without_common = [
            (a, b) for a, b in itertools.combinations(sorted(self.evidence), 2)
            if not self.fields_of(self.evidence[a]) & self.fields_of(self.evidence[b])
        ]
        self.assertEqual(without_common, [])


class RealRetrievalChecks(unittest.TestCase):
    """_retrieve จริงกับฐานข้อมูล local และ embedding bge-m3 ของ Ollama ในเครื่อง"""

    @classmethod
    def setUpClass(cls):
        from sqlalchemy import text

        from app.services.llm_client import get_llm_connector

        cls.db = _local_db()
        if cls.db is None:
            raise unittest.SkipTest("ฐานข้อมูล local ไม่มี course_chunks")
        cls.connector = get_llm_connector()
        try:
            cls.connector.embed("ทดสอบ")
        except Exception as exc:  # noqa: BLE001
            cls.db.close()
            raise unittest.SkipTest(f"embedding ในเครื่องใช้ไม่ได้: {type(exc).__name__}")
        names = sorted({_distinctive_name(t) for (t,) in cls.db.execute(text("SELECT title FROM courses WHERE is_active")).all()})
        cls.names = names

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def check_comparison(self, question):
        scopes = resolve_scopes(self.db, question)
        self.assertGreaterEqual(len(scopes), 2)
        chunks = chat._retrieve(self.db, self.connector, question)
        groups = []
        for c in chunks:
            name = _distinctive_name(c.course_title)
            if not groups or groups[-1][0] != name:
                groups.append((name, []))
            groups[-1][1].append(c)
        self.assertEqual([g[0] for g in groups], [s.matched_name for s in scopes], "หลักฐานต้องจัดกลุ่มตามหลักสูตร")
        self.assertFalse(any(ce.is_garbled(c.content) or _looks_like_table_of_contents(c.content) for c in chunks))
        self.assertEqual(len({c.chunk_id for c in chunks}), len(chunks))
        note = ce.describe_evidence(chunks)
        for scope in scopes:
            self.assertIn(f"- {scope.matched_name}:", note)
        return chunks, groups

    def test_regression_pairs_from_the_report(self):
        for question in ("วิทยาการคอมพิวเตอร์กับเทคโนโลยีสารสนเทศต่างกันอย่างไร",
                         "วิทยาการคอมพิวเตอร์กับคอมพิวเตอร์แอนิเมชันและมัลติมีเดียต่างกันอย่างไร"):
            with self.subTest(question=question):
                _, groups = self.check_comparison(question)
                for name, group in groups:
                    fields = {f.key for f in ce.FIELDS for c in group if f.matches(c.content)}
                    self.assertTrue({"objectives", "careers"} <= fields, f"{name}: {fields}")

    def test_pairs_not_used_to_design_the_fix(self):
        design = {s.matched_name for q in ("วิทยาการคอมพิวเตอร์กับเทคโนโลยีสารสนเทศ", "คอมพิวเตอร์แอนิเมชันและมัลติมีเดียกับคณิตศาสตร์")
                  for s in resolve_scopes(self.db, q)}
        others = [n for n in self.names if n not in design]
        pairs = [(others[i], others[-1 - i]) for i in range(3)]
        for a, b in pairs:
            with self.subTest(pair=(a, b)):
                self.check_comparison(f"{a}กับ{b}ต่างกันอย่างไร")

    def decision_for(self, question):
        scopes = resolve_scopes(self.db, question)
        chunks = chat._retrieve(self.db, self.connector, question)
        return ce.comparison_support(question, [s.matched_name for s in scopes], chunks)

    def test_quantitative_question_is_decided_the_same_way_every_time(self):
        question = "วิทยาการคอมพิวเตอร์กับเทคโนโลยีสารสนเทศ สาขาไหนเรียนเขียนโปรแกรมมากกว่ากัน"
        decisions = [self.decision_for(question) for _ in range(3)]
        self.assertEqual(len(set(decisions)), 1)
        self.assertEqual((decisions[0].decision, decisions[0].topic, decisions[0].ranking), (ce.SUPPORTED, "เขียนโปรแกรม", True))

    def test_other_wordings_topics_and_negative_control(self):
        for question, expected in (
            ("เทคโนโลยีสารสนเทศกับวิทยาการคอมพิวเตอร์ หลักสูตรไหนเรียนเขียนโปรแกรมเยอะกว่า", ce.SUPPORTED),
            ("คณิตศาสตร์กับวิทยาการคอมพิวเตอร์ สาขาไหนเรียนสถิติมากกว่ากัน", ce.SUPPORTED),
            ("วิทยาการคอมพิวเตอร์กับเทคโนโลยีสารสนเทศ สาขาไหนมีทุนการศึกษามากกว่ากัน", ce.UNDETERMINED),
        ):
            with self.subTest(question=question):
                self.assertEqual(self.decision_for(question).decision, expected)

    def test_quantitative_question_has_course_evidence_for_both_programmes(self):
        _, groups = self.check_comparison("วิทยาการคอมพิวเตอร์กับเทคโนโลยีสารสนเทศ สาขาไหนเรียนเขียนโปรแกรมมากกว่ากัน")
        for name, group in groups:
            self.assertTrue(any("โปรแกรม" in c.content for c in group), name)


if __name__ == "__main__":
    unittest.main(verbosity=1)
