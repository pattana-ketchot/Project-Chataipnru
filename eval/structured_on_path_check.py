"""
ตรวจเส้นทางตอบผู้ใช้ด้วยข้อมูลหลักสูตรที่มีโครงสร้าง (STRUCTURED_ANSWERS=on)

    python -m eval.structured_on_path_check

สิ่งที่ต้องจริงเสมอ
    - off / shadow: ผู้ใช้ได้คำตอบ RAG เดิมทุกตัวอักษร ไม่มีการหาคำตอบจากฐานข้อมูลเพื่อตอบผู้ใช้
    - on: ตอบด้วยฐานข้อมูลเฉพาะเมื่อ route = structured, answered และ field อยู่ใน USER_FACING_FIELDS
      กรณีอื่นทั้งหมด (admission, no_data, route rag, field ที่ไม่อยู่ในรายการ, ข้อผิดพลาด) ได้คำตอบ RAG
    - คำตอบจากฐานข้อมูลไม่ถูกเก็บลงแคช ไม่เรียกโมเดลเขียนคำตอบ และบันทึกได้ว่าคำตอบมาจากไหน
ชุด DB ใช้ฐานข้อมูล local (publication อัตโนมัติ) ผ่าน detect / lookup จริง อ่านอย่างเดียวแล้ว rollback
ไม่ยิง production ไม่เรียก Gemini
"""
from __future__ import annotations

import os
import sys
import unittest
import uuid
from concurrent.futures import Future
from pathlib import Path
from unittest import mock

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres@127.0.0.1:55432/course_advisor")
os.environ.setdefault("JWT_SECRET", "local-test-only")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import app.services.chat as chat  # noqa: E402
import app.services.structured_shadow as shadow  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.services.curriculum_facts import ANSWERED, NO_DATA, EditionFact, FactsResult, Source  # noqa: E402
from app.services.structured_intent import RAG, STRUCTURED, StructuredIntent, detect  # noqa: E402

RAG_REPLY = "คำตอบจากระบบเดิม (RAG)"
AGRI = "การจัดการเทคโนโลยีการเกษตรและบริหารทรัพยากรชุมชน"


class FakeConnector:
    answer_token_cap = 256

    def __init__(self):
        self.calls = 0

    def chat(self, messages, **kwargs):
        self.calls += 1
        return RAG_REPLY

    def chat_stream(self, messages, **kwargs):
        self.calls += 1
        yield RAG_REPLY


class RecordingExecutor:
    def __init__(self):
        self.calls = []

    def submit(self, fn, kwargs):
        self.calls.append(kwargs)
        future = Future()
        future.set_result(None)
        return future


def prepared(interpreted="หลักสูตรวิทยาการคอมพิวเตอร์ต้องเรียนกี่หน่วยกิต", canned=None, status="answered", has_history=False):
    return chat.Prepared(
        session_id=uuid.UUID(int=1),
        status=status,
        search_query="q",
        best_score=0.8,
        citations=[chat.ChatCitation(chunk_id=uuid.UUID(int=9), course_id=uuid.UUID(int=8), course_title="x", page_number=1, score=0.8)],
        canned=canned,
        messages=[] if canned else [chat.LLMMessage(role="user", content="x")],
        allow_fallback=canned is not None,
        cacheable=True,
        corpus_version="v1",
        interpreted=interpreted,
        has_history=has_history,
    )


def facts(field, answer="คำตอบจากฐานข้อมูล\nที่มา: doc.pdf หน้า 1", status=ANSWERED):
    rows = [] if status != ANSWERED else [EditionFact(course_id=str(uuid.uuid4()), course_title="หลักสูตรทดสอบ (พ.ศ. 2566)",
                                                      edition_year=2566, value_int=130, source=Source("doc.pdf", 1, 1))]
    return FactsResult(status, field, rows, publication_id=str(uuid.uuid4()), answer=answer if status == ANSWERED else None)


def intent(field, route=STRUCTURED, reason="single_programme_field"):
    return StructuredIntent(route=route, reason=reason, field=field, course_ids=(uuid.uuid4(),) if route == STRUCTURED else ())


class Harness(unittest.TestCase):
    """เรียก answer_question / stream_answer จริง โดยแทนเฉพาะขั้นเตรียมคำตอบ โมเดล และการเขียนฐานข้อมูลของคำขอ"""

    def run_chat(self, mode, p, *, detect_result=None, lookup_result=None, stream=False, lookup_side_effect=None):
        executor, connector, fresh = RecordingExecutor(), FakeConnector(), mock.MagicMock()
        detect_mock = mock.Mock(return_value=detect_result)
        lookup_mock = mock.Mock(return_value=lookup_result, side_effect=lookup_side_effect)
        with mock.patch.object(chat, "prepare_answer", return_value=p), \
                mock.patch.object(chat, "get_llm_connector", return_value=connector), \
                mock.patch.object(chat, "no_fallback_kwargs", return_value={}), \
                mock.patch.object(chat, "_persist") as persist, \
                mock.patch.object(chat, "cache_store") as store, \
                mock.patch.object(chat, "SessionLocal", return_value=fresh), \
                mock.patch.object(shadow, "configured_mode", return_value=mode), \
                mock.patch.object(shadow, "SessionLocal", return_value=mock.MagicMock()), \
                mock.patch.object(shadow, "detect", detect_mock), \
                mock.patch.object(shadow, "lookup", lookup_mock), \
                mock.patch.object(shadow, "_get_executor", return_value=executor):
            if stream:
                events = list(chat.stream_answer(mock.MagicMock(), uuid.UUID(int=2), None, "คำถามของผู้ใช้"))
                reply = "".join(__import__("json").loads(e.split("data: ", 1)[1])["t"] for e in events if e.startswith("event: token"))
                meta = __import__("json").loads(events[0].split("data: ", 1)[1])
            else:
                result = chat.answer_question(mock.MagicMock(), uuid.UUID(int=2), None, "คำถามของผู้ใช้")
                reply, meta = result.reply, {"status": result.status, "citations": result.citations}
        return {"reply": reply, "meta": meta, "llm_calls": connector.calls, "persist": [c.args[1:] for c in persist.call_args_list],
                "store": store.call_args_list, "submitted": executor.calls, "detect": detect_mock, "lookup": lookup_mock}

    def assertRag(self, out):
        self.assertEqual(out["reply"], RAG_REPLY)
        self.assertEqual(out["llm_calls"], 1)
        self.assertEqual(len(out["store"]), 1, "RAG answers keep using the cache as before")

    def assertStructured(self, out, answer):
        self.assertEqual(out["reply"], answer)
        self.assertEqual(out["llm_calls"], 0, "structured answers must not call the model")
        self.assertEqual(out["store"], [], "structured answers must never be cached")
        self.assertEqual(out["persist"], [(uuid.UUID(int=1), "คำถามของผู้ใช้", answer)])
        self.assertEqual(out["meta"]["status"], "answered")
        self.assertEqual(list(out["meta"]["citations"]), [])


class ModeChecks(Harness):
    def test_01_off_serves_rag_and_does_no_structured_work(self):
        for stream in (False, True):
            with self.subTest(stream=stream):
                out = self.run_chat(shadow.OFF, prepared(), detect_result=intent("total_credits"), lookup_result=facts("total_credits"), stream=stream)
                self.assertRag(out)
                out["detect"].assert_not_called()
                self.assertEqual(out["submitted"], [])

    def test_02_shadow_serves_rag_and_logs(self):
        for stream in (False, True):
            with self.subTest(stream=stream):
                out = self.run_chat(shadow.SHADOW, prepared(), detect_result=intent("total_credits"), lookup_result=facts("total_credits"), stream=stream)
                self.assertRag(out)
                out["detect"].assert_not_called()  # การตัดสินเพื่อตอบผู้ใช้ไม่ทำงาน งานเทียบผลอยู่ใน thread ของ shadow
                self.assertEqual(len(out["submitted"]), 1)
                self.assertEqual((out["submitted"][0]["served_source"], out["submitted"][0]["configured"]), ("rag", "shadow"))

    def test_03_to_06_on_serves_structured_for_each_allowed_field(self):
        for field in ("total_credits", "edition_year", "careers", "objectives"):
            for stream in (False, True):
                with self.subTest(field=field, stream=stream):
                    answer = f"คำตอบ {field}\nที่มา: doc.pdf หน้า 1"
                    out = self.run_chat(shadow.ON, prepared(), detect_result=intent(field), lookup_result=facts(field, answer), stream=stream)
                    self.assertStructured(out, answer)
                    self.assertEqual(out["submitted"][0]["served_source"], "structured")
                    self.assertEqual(out["submitted"][0]["served_reply"], answer)
                    self.assertEqual(out["submitted"][0]["configured"], "on")

    def test_on_uses_the_interpreted_question_and_falls_back_to_the_message(self):
        out = self.run_chat(shadow.ON, prepared(interpreted="หลักสูตรคณิตศาสตร์ พ.ศ. 2564 เรียนกี่หน่วยกิต", has_history=True),
                            detect_result=intent("total_credits"), lookup_result=facts("total_credits"))
        self.assertEqual(out["detect"].call_args.args[1], "หลักสูตรคณิตศาสตร์ พ.ศ. 2564 เรียนกี่หน่วยกิต")
        # คำตอบจากแคชหรือคำตอบสำเร็จรูปไม่มีคำถามที่ตีความแล้ว ใช้ข้อความของผู้ใช้ (เหมือนโหมด shadow)
        out = self.run_chat(shadow.ON, prepared(interpreted="", canned="คำตอบจากแคช"), detect_result=intent("total_credits"),
                            lookup_result=facts("total_credits"))
        self.assertEqual(out["detect"].call_args.args[1], "คำถามของผู้ใช้")


class AdmissionChecks(Harness):
    def test_07_on_admission_answered_is_always_rag(self):
        for stream in (False, True):
            with self.subTest(stream=stream):
                out = self.run_chat(shadow.ON, prepared(), detect_result=intent("admission"), lookup_result=facts("admission"), stream=stream)
                self.assertRag(out)
                out["lookup"].assert_not_called()
                self.assertEqual(out["submitted"][0]["served_source"], "rag")

    def test_admission_is_not_in_the_allow_list(self):
        self.assertNotIn("admission", shadow.USER_FACING_FIELDS)


class FallbackChecks(Harness):
    def test_08_on_no_data_is_rag(self):
        out = self.run_chat(shadow.ON, prepared(), detect_result=intent("total_credits"), lookup_result=facts("total_credits", status=NO_DATA))
        self.assertRag(out)

    def test_answered_without_text_is_rag(self):
        out = self.run_chat(shadow.ON, prepared(), detect_result=intent("careers"), lookup_result=facts("careers", answer="  "))
        self.assertRag(out)

    def test_09_on_route_rag_is_rag(self):
        out = self.run_chat(shadow.ON, prepared(), detect_result=intent(None, route=RAG, reason="narrative_or_comparison"),
                            lookup_result=facts("total_credits"))
        self.assertRag(out)
        out["lookup"].assert_not_called()

    def test_10_on_field_not_in_allow_list_is_rag(self):
        # field ที่ routing อาจรองรับในอนาคต ต้องได้ RAG จนกว่าจะเพิ่มชื่อไว้ใน USER_FACING_FIELDS
        for field in ("study_plan", "tuition", "program_name_th", None):
            with self.subTest(field=field):
                out = self.run_chat(shadow.ON, prepared(), detect_result=intent(field), lookup_result=facts(field))
                self.assertRag(out)
                out["lookup"].assert_not_called()

    def test_11_on_multiple_degree_levels_is_rag(self):
        out = self.run_chat(shadow.ON, prepared(), detect_result=intent("total_credits", route=RAG, reason="multiple_degree_levels"),
                            lookup_result=facts("total_credits"))
        self.assertRag(out)

    def test_12_structured_errors_fall_back_to_rag(self):
        for stream in (False, True):
            with self.subTest(where="lookup", stream=stream):
                out = self.run_chat(shadow.ON, prepared(), detect_result=intent("total_credits"), lookup_side_effect=RuntimeError("db down"), stream=stream)
                self.assertRag(out)
        with mock.patch.object(shadow, "SessionLocal", side_effect=RuntimeError("no database")), \
                mock.patch.object(shadow, "configured_mode", return_value=shadow.ON):
            self.assertIsNone(shadow.structured_reply(question="q", interpreted=None))
        with mock.patch.object(shadow, "configured_mode", side_effect=RuntimeError("settings broken")):
            self.assertIsNone(shadow.structured_reply(question="q", interpreted=None))

    def test_off_and_shadow_never_open_a_database_session_for_serving(self):
        for mode in (shadow.OFF, shadow.SHADOW):
            with self.subTest(mode=mode), \
                    mock.patch.object(shadow, "configured_mode", return_value=mode), \
                    mock.patch.object(shadow, "SessionLocal", side_effect=AssertionError("database used")):
                self.assertIsNone(shadow.structured_reply(question="หลักสูตรวิทยาการคอมพิวเตอร์เรียนกี่หน่วยกิต", interpreted=None))

    def test_allow_list_is_explicit(self):
        self.assertEqual(shadow.USER_FACING_FIELDS, frozenset({"total_credits", "edition_year", "careers", "objectives"}))
        self.assertIsInstance(shadow.USER_FACING_FIELDS, frozenset)


class DbCase(unittest.TestCase):
    """detect / lookup จริงบนฐานข้อมูล local อ่านอย่างเดียว"""

    def setUp(self):
        self.db = SessionLocal()

    def tearDown(self):
        self.db.rollback()
        self.db.close()

    def serve(self, asked):
        return shadow.servable_answer(self.db, asked)

    def reply_via(self, question, interpreted):
        """structured_reply แบบเต็ม (โหมด on) โดยใช้ session ของชุดทดสอบ"""
        session = mock.MagicMock()
        session.__enter__ = mock.Mock(return_value=self.db)
        session.__exit__ = mock.Mock(return_value=False)
        with mock.patch.object(shadow, "configured_mode", return_value=shadow.ON), \
                mock.patch.object(shadow, "SessionLocal", return_value=session):
            return shadow.structured_reply(question=question, interpreted=interpreted)


class ContextChecks(DbCase):
    def test_13_bachelor_total_credits(self):
        answer = self.serve("หลักสูตรวิทยาการคอมพิวเตอร์ พ.ศ. 2566 เรียนกี่หน่วยกิต")
        self.assertIn("130 หน่วยกิต", answer)
        self.assertIn("วิทยาการคอมพิวเตอร์ (พ.ศ. 2566)", answer)
        self.assertIn("ที่มา:", answer)

    def test_14_master_total_credits(self):
        answer = self.serve(f"หลักสูตรวิทยาศาสตรมหาบัณฑิต สาขาวิชา{AGRI} เรียนกี่หน่วยกิต")
        self.assertIn("36 หน่วยกิต", answer)
        self.assertIn("มหาบัณฑิต", answer)
        self.assertNotIn("ดุษฎีบัณฑิต", answer)

    def test_15_doctoral_total_credits(self):
        answer = self.serve(f"หลักสูตรปรัชญาดุษฎีบัณฑิต สาขาวิชา{AGRI} เรียนกี่หน่วยกิต")
        self.assertIn("48 หน่วยกิต", answer)
        self.assertIn("ดุษฎีบัณฑิต", answer)
        self.assertNotIn("มหาบัณฑิต", answer)

    def test_16_multi_edition(self):
        answer = self.serve("หลักสูตรเทคโนโลยีสารสนเทศเรียนกี่หน่วยกิต")
        self.assertIn("(พ.ศ. 2566): 130 หน่วยกิต", answer)
        self.assertIn("(พ.ศ. 2561): 127 หน่วยกิต", answer)
        years = self.serve("หลักสูตรเทคโนโลยีสารสนเทศปรับปรุงปีไหน")
        self.assertIn("2566", years)
        self.assertIn("2561", years)

    def test_17_programme_follow_up_swap(self):
        # คำถามต่อเนื่อง "แล้วสาขาเทคโนโลยีสารสนเทศล่ะ" หลังถามวิทยาการคอมพิวเตอร์: ใช้คำถามที่ตีความแล้วเท่านั้น
        answer = self.reply_via("แล้วสาขาเทคโนโลยีสารสนเทศล่ะ", "หลักสูตรเทคโนโลยีสารสนเทศ พ.ศ. 2566 เรียนกี่หน่วยกิต")
        self.assertIn("เทคโนโลยีสารสนเทศ (พ.ศ. 2566)", answer)
        self.assertNotIn("วิทยาการคอมพิวเตอร์", answer)

    def test_18_year_follow_up_swap(self):
        answer = self.reply_via("แล้วฉบับ พ.ศ. 2561 ล่ะ", "หลักสูตรเทคโนโลยีสารสนเทศ พ.ศ. 2561 เรียนกี่หน่วยกิต")
        self.assertIn("127 หน่วยกิต", answer)
        self.assertNotIn("130", answer)
        # ข้อความต่อเนื่องที่ยังไม่ได้ตีความ (ไม่มีชื่อหลักสูตร) ต้องไม่ถูกตอบจากฐานข้อมูล
        self.assertIsNone(self.reply_via("แล้วฉบับ พ.ศ. 2561 ล่ะ", None))

    def test_objectives_answer_from_database(self):
        answer = self.serve("หลักสูตรวิทยาศาสตร์เครื่องสำอาง พ.ศ. 2566 มีวัตถุประสงค์อะไรบ้าง")
        self.assertIn("วิทยาศาสตร์เครื่องสำอาง (พ.ศ. 2566)", answer)
        self.assertIn("ที่มา:", answer)

    def test_no_data_and_missing_year_are_rag(self):
        self.assertIsNone(self.serve("หลักสูตรเทคโนโลยีสารสนเทศ พ.ศ. 2570 เรียนกี่หน่วยกิต"))
        self.assertIsNone(self.serve("หลักสูตรวิทยาการคอมพิวเตอร์จบไปทำอาชีพอะไรได้บ้าง"))  # ยังไม่เผยแพร่ใน local

    def test_serving_answer_equals_the_shadow_answer(self):
        # เส้นทางตอบผู้ใช้ไม่เรียบเรียงคำตอบใหม่: ข้อความเดียวกับ structured_answer ที่โหมด shadow บันทึก
        question = "หลักสูตรเทคโนโลยีสารสนเทศเรียนกี่หน่วยกิต"
        record = shadow.run_shadow(self.db, question=question, served_status="answered", served_reply="x", mode="replay", commit=False)
        self.assertEqual(self.serve(question), record["structured_answer"])


class SafetyChecks(DbCase):
    def test_19_comparison_is_rag(self):
        for q in ("เปรียบเทียบคุณสมบัติผู้เข้าศึกษาของสาขาเทคโนโลยีสารสนเทศกับสาขาวิทยาการคอมพิวเตอร์",
                  "สาขาเทคโนโลยีสารสนเทศกับสาขาวิทยาการคอมพิวเตอร์เรียนกี่หน่วยกิต"):
            with self.subTest(q=q):
                self.assertEqual(detect(self.db, q).route, RAG)
                self.assertIsNone(self.serve(q))

    def test_20_recommendation_is_rag(self):
        for q in ("แนะนำสาขาสำหรับคนที่ชอบเขียนโปรแกรมหน่อย", "แนะนำสาขาที่จบไปทำอาชีพโปรแกรมเมอร์ได้"):
            with self.subTest(q=q):
                self.assertEqual(detect(self.db, q).route, RAG)
                self.assertIsNone(self.serve(q))

    def test_21_ranking_or_winner_is_rag(self):
        for q in ("สาขาไหนเรียนหน่วยกิตน้อยที่สุด", "สาขาไหนเรียนกี่หน่วยกิตน้อยที่สุด", "หลักสูตรไหนจบไปทำอาชีพได้มากที่สุด"):
            with self.subTest(q=q):
                self.assertEqual(detect(self.db, q).route, RAG)
                self.assertIsNone(self.serve(q))

    def test_22_admission_stays_rag_even_when_published_data_exists(self):
        q = "หลักสูตรเทคโนโลยีสารสนเทศ พ.ศ. 2566 คุณสมบัติของผู้เข้าศึกษามีอะไรบ้าง"
        routed = detect(self.db, q)
        self.assertEqual((routed.route, routed.field), (STRUCTURED, "admission"))
        published = facts("admission", "คุณสมบัติของผู้เข้าศึกษา ตามหลักสูตร…\nที่มา: it66.pdf หน้า 16")
        with mock.patch.object(shadow, "lookup", return_value=published) as lookup:
            self.assertIsNone(self.serve(q))
            self.assertIsNone(self.reply_via(q, None))
            lookup.assert_not_called()

    def test_multiple_degree_levels_is_rag(self):
        q = f"สาขา{AGRI} เรียนกี่หน่วยกิต"
        self.assertEqual(detect(self.db, q).reason, "multiple_degree_levels")
        self.assertIsNone(self.serve(q))

    def test_unsupported_topic_is_rag(self):
        self.assertIsNone(self.serve("ค่าเทอมสาขาวิทยาการคอมพิวเตอร์เท่าไหร่"))


class LoggingChecks(DbCase):
    def test_structured_served_row_records_source_and_mode(self):
        question = f"หลักสูตรวิทยาการคอมพิวเตอร์ พ.ศ. 2566 เรียนกี่หน่วยกิต [test {uuid.uuid4()}]"
        answer = self.serve("หลักสูตรวิทยาการคอมพิวเตอร์ พ.ศ. 2566 เรียนกี่หน่วยกิต")
        record = shadow.run_shadow(self.db, question=question, interpreted="หลักสูตรวิทยาการคอมพิวเตอร์ พ.ศ. 2566 เรียนกี่หน่วยกิต",
                                   served_status="answered", served_reply=answer, served_source=shadow.SERVED_STRUCTURED,
                                   configured=shadow.ON, commit=False)
        self.assertEqual(record["mode"], "shadow")  # คอลัมน์ mode รับได้เฉพาะ shadow / replay — ไม่มี migration
        self.assertEqual(record["comparison"], "not_compared")
        self.assertEqual(record["comparison_detail"], {"served_source": "structured", "configured_mode": "on"})
        self.assertEqual((record["route"], record["intent_field"], record["structured_status"]), ("structured", "total_credits", "answered"))
        self.assertEqual(record["served_reply"], answer)

    def test_rag_served_row_keeps_the_comparison(self):
        question = f"หลักสูตรวิทยาการคอมพิวเตอร์ พ.ศ. 2566 เรียนกี่หน่วยกิต [test {uuid.uuid4()}]"
        record = shadow.run_shadow(self.db, question=question, interpreted="หลักสูตรวิทยาการคอมพิวเตอร์ พ.ศ. 2566 เรียนกี่หน่วยกิต",
                                   served_status="answered", served_reply="ต้องเรียน 130 หน่วยกิต", configured=shadow.ON, commit=False)
        self.assertEqual(record["comparison"], "agree")
        self.assertEqual(record["comparison_detail"]["served_source"], "rag")
        self.assertEqual(record["comparison_detail"]["configured_mode"], "on")

    def test_submit_runs_in_on_mode(self):
        executor = RecordingExecutor()
        with mock.patch.object(shadow, "configured_mode", return_value=shadow.ON), \
                mock.patch.object(shadow, "_get_executor", return_value=executor):
            self.assertIsNotNone(shadow.submit(question="q", interpreted=None, has_history=False, served_status="answered",
                                               served_reply="r", served_source=shadow.SERVED_STRUCTURED))
        self.assertEqual((executor.calls[0]["served_source"], executor.calls[0]["configured"]), ("structured", "on"))


if __name__ == "__main__":
    unittest.main(verbosity=1)
