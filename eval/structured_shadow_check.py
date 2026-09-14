"""
ตรวจโหมด shadow ของคำตอบจากข้อมูลหลักสูตรที่มีโครงสร้าง — MKO Phase 2

    python -m eval.structured_shadow_check

สิ่งที่ต้องจริงเสมอ
    - STRUCTURED_ANSWERS=off (ค่าตั้งต้น) ไม่เปิด thread ไม่แตะฐานข้อมูล และคำตอบเหมือนก่อนมีโหมดนี้ทุกตัวอักษร
    - shadow ไม่เปลี่ยนคำตอบ ไม่เปลี่ยนลำดับเหตุการณ์ของสตรีม และข้อผิดพลาดใดๆ ไม่หลุดไปถึงผู้ใช้
    - on ยังไม่เปิดใน Phase 2 ต้องทำงานเป็น shadow
    - การเทียบคำตอบให้ผลตามกติกาที่เขียนไว้ใน services/structured_shadow.py
ชุดสุดท้ายเขียนแถวลงฐานข้อมูล local ใน transaction แล้ว rollback
"""
from __future__ import annotations

import os
import sys
import threading
import unittest
import uuid
from concurrent.futures import Future
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres@127.0.0.1:55432/course_advisor")
os.environ.setdefault("JWT_SECRET", "local-test-only")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import app.services.chat as chat  # noqa: E402
import app.services.structured_shadow as shadow  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.services.curriculum_facts import ANSWERED, NO_DATA, EditionFact, FactsResult  # noqa: E402

REPLY = "หลักสูตรนี้มีจำนวนหน่วยกิตรวมตลอดหลักสูตร 130 หน่วยกิต"


class FakeConnector:
    answer_token_cap = 256

    def chat(self, messages, **kwargs):
        return f"  {REPLY}  "

    def chat_stream(self, messages, **kwargs):
        yield "หลักสูตรนี้มีจำนวนหน่วยกิต"
        yield "รวมตลอดหลักสูตร 130 หน่วยกิต"


class RecordingExecutor:
    """แทน thread pool เก็บงานที่ส่งเข้ามาไว้ตรวจ ไม่รันจริง"""

    def __init__(self):
        self.calls = []

    def submit(self, fn, kwargs):
        self.calls.append(kwargs)
        future = Future()
        future.set_result(None)
        return future


def prepared(canned=None, interpreted="หลักสูตรวิทยาการคอมพิวเตอร์ต้องเรียนกี่หน่วยกิต"):
    return chat.Prepared(
        session_id=uuid.UUID(int=1),
        status="answered" if canned is None else "not_found",
        search_query="ต้องเรียนกี่หน่วยกิต",
        best_score=0.8123,
        citations=[],
        canned=canned,
        messages=[] if canned else [chat.LLMMessage(role="user", content="x")],
        allow_fallback=canned is not None,
        cacheable=True,
        corpus_version="v1",
        interpreted=interpreted if canned is None else "",
        has_history=False,
    )


class ModeChecks(unittest.TestCase):
    def test_setting_defaults_to_off(self):
        env = {k: v for k, v in os.environ.items() if k != "STRUCTURED_ANSWERS"}
        with mock.patch.dict(os.environ, env, clear=True):
            settings = Settings(_env_file=None)
        self.assertEqual(settings.structured_answers, "off")
        self.assertEqual(shadow.configured_mode(settings.structured_answers), shadow.OFF)

    def test_modes(self):
        self.assertEqual(shadow.configured_mode("off"), shadow.OFF)
        self.assertEqual(shadow.configured_mode(" Shadow "), shadow.SHADOW)
        self.assertEqual(shadow.configured_mode(""), shadow.OFF)

    def test_on_is_held_at_shadow_in_phase2(self):
        self.assertEqual(shadow.configured_mode("on"), shadow.SHADOW)

    def test_unknown_values_are_off(self):
        for raw in ("shaddow", "true", "1", "enabled"):
            with self.subTest(raw=raw):
                self.assertEqual(shadow.configured_mode(raw), shadow.OFF)


class SubmitChecks(unittest.TestCase):
    kwargs = dict(question="q", interpreted="q", has_history=False, served_status="answered", served_reply="r")

    def test_off_touches_nothing(self):
        with mock.patch.object(shadow, "configured_mode", return_value=shadow.OFF), \
                mock.patch.object(shadow, "_get_executor", side_effect=AssertionError("executor used")), \
                mock.patch.object(shadow, "SessionLocal", side_effect=AssertionError("database used")), \
                mock.patch.object(shadow, "run_shadow", side_effect=AssertionError("shadow ran")):
            self.assertIsNone(shadow.submit(**self.kwargs))

    def test_errors_inside_the_worker_are_swallowed(self):
        with mock.patch.object(shadow, "configured_mode", return_value=shadow.SHADOW), \
                mock.patch.object(shadow, "SessionLocal", side_effect=RuntimeError("database down")):
            future = shadow.submit(**self.kwargs)
            self.assertIsNotNone(future)
            self.assertIsNone(future.result(timeout=10))

    def test_submit_itself_never_raises(self):
        with mock.patch.object(shadow, "configured_mode", side_effect=RuntimeError("settings broken")):
            self.assertIsNone(shadow.submit(**self.kwargs))
        with mock.patch.object(shadow, "configured_mode", return_value=shadow.SHADOW), \
                mock.patch.object(shadow, "_get_executor", side_effect=RuntimeError("no threads")):
            self.assertIsNone(shadow.submit(**self.kwargs))

    def test_full_queue_drops_work_instead_of_waiting(self):
        full = threading.BoundedSemaphore(1)
        full.acquire()
        with mock.patch.object(shadow, "configured_mode", return_value=shadow.SHADOW), \
                mock.patch.object(shadow, "_pending", full), \
                mock.patch.object(shadow, "_get_executor", side_effect=AssertionError("executor used")):
            self.assertIsNone(shadow.submit(**self.kwargs))


class ChatHookChecks(unittest.TestCase):
    """คำตอบและลำดับเหตุการณ์ต้องเหมือนกันทุกตัวอักษรไม่ว่าโหมดใด"""

    def run_chat(self, mode, fn, p, executor=None):
        executor = executor or RecordingExecutor()
        fresh = mock.MagicMock()
        with mock.patch.object(chat, "prepare_answer", return_value=p), \
                mock.patch.object(chat, "get_llm_connector", return_value=FakeConnector()), \
                mock.patch.object(chat, "no_fallback_kwargs", return_value={}), \
                mock.patch.object(chat, "_persist") as persist, \
                mock.patch.object(chat, "cache_store") as store, \
                mock.patch.object(chat, "SessionLocal", return_value=fresh), \
                mock.patch.object(shadow, "configured_mode", return_value=mode), \
                mock.patch.object(shadow, "_get_executor", return_value=executor):
            result = fn()
            if not isinstance(result, chat.ChatReply):
                result = list(result)
            # ตัด session ฐานข้อมูล (อาร์กิวเมนต์แรก) ออก เพราะเป็น mock คนละตัวในแต่ละรอบ
            return (result, executor, [c.args[1:] for c in persist.call_args_list],
                    [c.args[1:] for c in store.call_args_list])

    def answer(self, p):
        return lambda: chat.answer_question(mock.MagicMock(), uuid.UUID(int=2), None, "คำถามของผู้ใช้")

    def stream(self, p):
        return lambda: chat.stream_answer(mock.MagicMock(), uuid.UUID(int=2), None, "คำถามของผู้ใช้")

    def test_answer_question_is_identical_with_flag_off_and_shadow(self):
        for p in (prepared(), prepared(canned="ไม่พบข้อมูล")):
            with self.subTest(canned=p.canned):
                off, off_exec, off_persist, off_store = self.run_chat(shadow.OFF, self.answer(p), p)
                on, on_exec, on_persist, on_store = self.run_chat(shadow.SHADOW, self.answer(p), p)
                self.assertEqual(off.model_dump(), on.model_dump())
                self.assertEqual((off_persist, off_store), (on_persist, on_store))
                self.assertEqual(off_exec.calls, [])
                self.assertEqual(len(on_exec.calls), 1)
                self.assertEqual(on_exec.calls[0]["served_reply"], off.reply)
                self.assertEqual(on_exec.calls[0]["served_status"], p.status)
                self.assertEqual(on_exec.calls[0]["interpreted"], p.interpreted)

    def test_stream_answer_is_identical_with_flag_off_and_shadow(self):
        for p in (prepared(), prepared(canned="ไม่พบข้อมูล")):
            with self.subTest(canned=p.canned):
                off, off_exec, off_persist, off_store = self.run_chat(shadow.OFF, self.stream(p), p)
                on, on_exec, on_persist, on_store = self.run_chat(shadow.SHADOW, self.stream(p), p)
                self.assertEqual(off, on)
                self.assertEqual((off_persist, off_store), (on_persist, on_store))
                self.assertEqual(off_exec.calls, [])
                self.assertEqual(len(on_exec.calls), 1)
                self.assertTrue(off[-1].startswith("event: done"))

    def test_stream_submits_only_after_the_last_token(self):
        p = prepared()
        seen: list[str] = []

        class OrderExecutor(RecordingExecutor):
            def submit(self, fn, kwargs):
                self.tokens_before_submit = sum("event: token" in e for e in seen)
                return super().submit(fn, kwargs)

        executor = OrderExecutor()

        def consume():
            for event in chat.stream_answer(mock.MagicMock(), uuid.UUID(int=2), None, "คำถามของผู้ใช้"):
                seen.append(event)
            return seen

        self.run_chat(shadow.SHADOW, consume, p, executor)
        self.assertEqual(executor.tokens_before_submit, sum("event: token" in e for e in seen))

    def test_shadow_failure_does_not_change_the_reply(self):
        p = prepared()
        off, *_ = self.run_chat(shadow.OFF, self.answer(p), p)

        class BrokenExecutor:
            def submit(self, *args, **kwargs):
                raise RuntimeError("thread pool broken")

        broken, *_ = self.run_chat(shadow.SHADOW, self.answer(p), p, BrokenExecutor())
        self.assertEqual(off.model_dump(), broken.model_dump())


def facts(field, *values, items=None):
    rows = [EditionFact(course_id=str(uuid.uuid4()), course_title=f"ฉบับ {n}", edition_year=2560 + n, value_int=v)
            for n, v in enumerate(values)]
    if items is not None:
        rows = [EditionFact(course_id=str(uuid.uuid4()), course_title="ฉบับ", edition_year=2566, items=items)]
    return FactsResult(ANSWERED, field, rows)


class CompareChecks(unittest.TestCase):
    def test_total_credits(self):
        result = facts("total_credits", 130)
        self.assertEqual(shadow.compare(result, "answered", "ไม่น้อยกว่า 130 หน่วยกิต หมวดศึกษาทั่วไป 30 หน่วยกิต")[0], "agree")
        self.assertEqual(shadow.compare(result, "answered", "ต้องเรียน ๑๓๐ หน่วยกิต")[0], "agree")
        self.assertEqual(shadow.compare(result, "answered", "ต้องเรียน 127 หน่วยกิต")[0], "disagree")
        self.assertEqual(shadow.compare(result, "answered", "ขึ้นกับแผนการเรียน")[0], "unclear")
        self.assertEqual(shadow.compare(facts("total_credits", 127, 130), "answered", "130 หน่วยกิต")[0], "partial")

    def test_edition_year(self):
        result = facts("edition_year", 2566)
        self.assertEqual(shadow.compare(result, "answered", "หลักสูตรปรับปรุง พ.ศ. 2566")[0], "agree")
        self.assertEqual(shadow.compare(result, "answered", "หลักสูตร พ.ศ. 2561")[0], "disagree")

    def test_lists(self):
        result = facts("careers", items=["นักวิเคราะห์ข้อมูล", "นักพัฒนาซอฟต์แวร์", "ผู้ดูแลระบบเครือข่าย"])
        self.assertEqual(shadow.compare(result, "answered", "นักวิเคราะห์ข้อมูล นักพัฒนาซอฟต์แวร์ และผู้ดูแลระบบเครือข่าย")[0], "agree")
        self.assertEqual(shadow.compare(result, "answered", "เป็นนักวิเคราะห์ข้อมูลได้")[0], "partial")
        self.assertEqual(shadow.compare(result, "answered", "ครูสอนคณิตศาสตร์")[0], "disagree")

    def test_served_no_answer_and_not_compared(self):
        self.assertEqual(shadow.compare(facts("total_credits", 130), "not_found", "ไม่พบข้อมูล")[0], "served_no_answer")
        self.assertEqual(shadow.compare(FactsResult(NO_DATA, "careers"), "answered", "x")[0], "not_compared")
        self.assertEqual(shadow.compare(None, "answered", "x")[0], "not_compared")


class ShadowRecordChecks(unittest.TestCase):
    """เขียนแถวจริงลงฐานข้อมูล local ใน transaction แล้ว rollback"""

    def setUp(self):
        from app.db.session import SessionLocal

        self.db = SessionLocal()

    def tearDown(self):
        self.db.rollback()
        self.db.close()

    def count(self, question):
        from sqlalchemy import text

        return self.db.execute(text("SELECT count(*) FROM mko.shadow_answers WHERE question = :q"), {"q": question}).scalar()

    def test_structured_question_is_recorded_with_facts(self):
        question = f"หลักสูตรวิทยาการคอมพิวเตอร์ต้องเรียนกี่หน่วยกิต [test {uuid.uuid4()}]"
        record = shadow.run_shadow(self.db, question=question, served_status="answered", served_reply=REPLY,
                                   mode="replay", commit=False)
        self.assertEqual(self.count(question), 1)
        self.assertEqual((record["route"], record["intent_field"]), ("structured", "total_credits"))
        if record["structured_status"] == ANSWERED:
            self.assertIn("ที่มา:", record["structured_answer"])
            self.assertTrue(all(f["source"]["quote"] for f in record["facts"]["facts"]))

    def test_rag_question_is_recorded_as_not_applicable(self):
        question = f"ทำไมต้องเรียนวิทยาการคอมพิวเตอร์ [test {uuid.uuid4()}]"
        record = shadow.run_shadow(self.db, question=question, served_status="answered", served_reply="x",
                                   mode="replay", commit=False)
        self.assertEqual(self.count(question), 1)
        self.assertEqual((record["route"], record["structured_status"], record["comparison"]),
                         ("rag", "not_applicable", "not_compared"))


if __name__ == "__main__":
    unittest.main(verbosity=1)
