"""
ชื่อรุ่นที่หน้าผลลัพธ์แสดง ต้องเป็นตัวที่เขียนข้อความให้คำขอนั้นจริง

    cd backend && python tests/test_result_model_label.py

ไม่ต่อฐานข้อมูล ไม่เรียกโมเดลจริง — ใช้ของจับพฤติกรรมแทน connector ชั้นใน

ทำไมต้องมีชุดนี้
---------------
หน้า "ค้นหาสาขาที่เหมาะกับฉัน" และ "เปรียบเทียบสาขา" จะติดป้ายว่าใครเขียนคำอธิบาย
ให้ผู้ใช้เห็น · สามอย่างที่ผิดแล้วผู้ใช้จะถูกบอกข้อมูลเท็จโดยไม่มีใครรู้

1. **ติดป้ายด้วยค่าตั้งต้นแทนตัวที่ทำงานจริง** — เส้นทาง Gemini มีโมเดลในเครื่อง
   รับช่วงต่อเมื่อเจ้าหลักล้ม ถ้ารายงานตามค่าที่เลือกไว้ ผู้ใช้จะเห็นว่า Gemini เขียน
   ทั้งที่ข้อความมาจากโมเดลในเครื่อง
2. **ติดป้ายทั้งที่ไม่ได้เรียกโมเดลเลย** — ถ้าโมเดลล่ม ผลยังออกได้ด้วยข้อความมาตรฐาน
   ของระบบ กรณีนั้นต้องไม่มีชื่อรุ่น
3. **ค่าของคำขอหนึ่งรั่วไปอีกคำขอ** — หลายคำขอทำงานพร้อมกัน
"""
import os
import sys
import unittest
from contextvars import copy_context
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://unused:unused@127.0.0.1:1/unused")
os.environ.setdefault("JWT_SECRET", "ชุดทดสอบไม่ได้ออก token")
os.environ.setdefault("GEMINI_API_KEY", "คีย์ปลอมสำหรับชุดทดสอบ")

from llm.connector import ChatMessage, LLMConnectionError  # noqa: E402
from llm.gemini import GeminiConnector, _QuotaExhausted  # noqa: E402

from app.api.routes.web_compat import _engine  # noqa: E402
from app.services import llm_client  # noqa: E402


class _Fake:
    """connector ชั้นในแบบปลอม — ตอบสำเร็จหรือล้มตามที่สั่ง"""

    answer_token_cap = 512

    def __init__(self, model: str, fail: bool = False) -> None:
        self.chat_model = model
        self._fail = fail
        self.calls = 0

    def chat(self, *_args, **_kwargs):
        self.calls += 1
        if self._fail:
            raise LLMConnectionError("จำลองว่าเจ้าหลักล้ม")
        return "ข้อความจาก " + self.chat_model

    def embed(self, _text):
        return [0.0]


class ResultModelLabelTests(unittest.TestCase):
    def setUp(self):
        llm_client.reset_chat_model()

    def test_ยังไม่ได้เรียกโมเดล_ต้องไม่มีชื่อรุ่น(self):
        self.assertIsNone(llm_client.chat_model_used())

    def test_เจ้าหลักเขียนสำเร็จ_รายงานเจ้าหลัก(self):
        split = llm_client._SplitConnector(_Fake("bge-m3"), _Fake("gemini-3.5-flash"))
        split.chat([])
        self.assertEqual(llm_client.chat_model_used(),
                         {"provider": "gemini", "model": "gemini-3.5-flash"})

    def test_เจ้าหลักล้มแล้วตัวสำรองรับช่วง_ต้องรายงานตัวสำรอง(self):
        """ข้อความที่ผู้ใช้เห็นมาจากโมเดลในเครื่อง การติดป้ายว่า Gemini คือการบอกผิด"""
        local = _Fake("qwen2.5:3b")
        split = llm_client._SplitConnector(local, _Fake("gemini-3.5-flash", fail=True))
        out = split.chat([])
        self.assertIn("qwen2.5:3b", out)
        self.assertEqual(llm_client.chat_model_used(),
                         {"provider": "ollama", "model": "qwen2.5:3b"})

    def test_ทั้งเจ้าหลักและตัวสำรองล้ม_ต้องไม่มีชื่อรุ่น(self):
        split = llm_client._SplitConnector(_Fake("qwen2.5:3b", fail=True),
                                           _Fake("gemini-3.5-flash", fail=True))
        with self.assertRaises(LLMConnectionError):
            split.chat([])
        self.assertIsNone(llm_client.chat_model_used())

    def test_เลือกโมเดลในเครื่องเป็นตัวหลัก_รายงานตัวนั้น(self):
        local = llm_client._LocalPrimary(_Fake("qwen2.5:3b"))
        local.chat([])
        self.assertEqual(llm_client.chat_model_used(),
                         {"provider": "ollama", "model": "qwen2.5:3b"})

    def test_ค่าของคำขอหนึ่งไม่รั่วไปอีกคำขอ(self):
        """endpoint แบบ sync รันใน threadpool ซึ่งคัดลอก context ให้ทีละคำขอ"""
        def one():
            llm_client.reset_chat_model()
            llm_client._SplitConnector(_Fake("bge-m3"), _Fake("gemini-3.5-flash")).chat([])
            return llm_client.chat_model_used()

        self.assertEqual(copy_context().run(one)["model"], "gemini-3.5-flash")
        # คำขอนี้ไม่ได้เรียกโมเดลเอง จึงต้องไม่เห็นของคำขอก่อนหน้า
        self.assertIsNone(llm_client.chat_model_used())

    # ---------------- Gemini วนลองรุ่นของตัวเอง ----------------

    def _gemini_that_falls_back(self):
        """
        GeminiConnector จริง แต่แทนการยิง HTTP ด้วยของจำลอง

        รุ่นหลักชนโควตา (429 ของ Google เป็นแบบต่อโมเดล) รุ่นสำรองตอบสำเร็จ
        """
        # คีย์ต้องเป็น ASCII เพราะมันถูกใส่ลงส่วนหัวของ HTTP ตอนสร้างตัวเชื่อมต่อ
        conn = GeminiConnector(api_key="not-a-real-key", chat_model="gemini-3.5-flash-lite",
                               fallback_models=("gemini-3.6-flash",))
        tried: list[str] = []

        def fake_call(model, _payload):
            tried.append(model)
            if model == conn.chat_model:
                raise _QuotaExhausted(model, 1.0)
            return "ข้อความจากรุ่นสำรอง " + model

        conn._chat_one_model = fake_call
        return conn, tried

    def test_รุ่นหลักของ_gemini_ชนโควตา_ต้องรายงานรุ่นสำรองที่ตอบจริง(self):
        """
        ค่าที่ตั้งไว้คือ gemini-3.5-flash-lite แต่ตัวที่เขียนคำตอบคือ gemini-3.6-flash

        ถ้ารายงานตามค่าที่ตั้งไว้ ผู้ใช้จะเห็นชื่อรุ่นที่ไม่ได้เขียนข้อความนั้นเลย
        """
        gemini, tried = self._gemini_that_falls_back()
        split = llm_client._SplitConnector(_Fake("bge-m3"), gemini)
        out = split.chat([ChatMessage(role="user", content="ทดสอบ")])

        self.assertEqual(tried, ["gemini-3.5-flash-lite", "gemini-3.6-flash"])
        self.assertIn("gemini-3.6-flash", out)
        self.assertEqual(llm_client.chat_model_used(),
                         {"provider": "gemini", "model": "gemini-3.6-flash"})

    def test_ค่าของคำขอที่ใช้รุ่นสำรองไม่รั่วไปคำขออื่นที่ใช้ตัวเชื่อมต่อเดียวกัน(self):
        """
        ตัวเชื่อมต่อถูกแคชไว้ใช้ร่วมทุกคำขอ — ถ้าเก็บรุ่นที่ตอบไว้บนวัตถุนั้น
        คำขอที่ทำงานพร้อมกันจะอ่านค่าของกันและกัน
        """
        gemini, _ = self._gemini_that_falls_back()
        split = llm_client._SplitConnector(_Fake("bge-m3"), gemini)

        def request_with_backup():
            llm_client.reset_chat_model()
            split.chat([ChatMessage(role="user", content="คำขอที่ใช้รุ่นสำรอง")])
            return llm_client.chat_model_used()

        def request_without_model():
            llm_client.reset_chat_model()
            return llm_client.chat_model_used()

        self.assertEqual(copy_context().run(request_with_backup)["model"], "gemini-3.6-flash")
        # คำขอนี้ใช้ตัวเชื่อมต่อตัวเดียวกันแต่ไม่ได้เรียกโมเดล ต้องไม่เห็นรุ่นของคำขอก่อนหน้า
        self.assertIsNone(copy_context().run(request_without_model))
        self.assertIsNone(llm_client.chat_model_used())

    # ---------------- รูปร่างที่ส่งให้หน้าเว็บ ----------------

    def test_ส่งชื่อรุ่นที่ทำงานจริงไปกับผล(self):
        llm_client._SplitConnector(_Fake("bge-m3"), _Fake("gemini-3.5-flash-lite")).chat([])
        engine = _engine(explained=True, scoring="embedding_and_rules")
        self.assertEqual(engine["explanation"],
                         {"provider": "gemini", "model": "gemini-3.5-flash-lite"})
        self.assertEqual(engine["scoring"], "embedding_and_rules")

    def test_ข้อความของโมเดลไม่ได้ถูกใช้_ต้องไม่ติดป้ายชื่อรุ่น(self):
        """โมเดลเขียนมาแล้วไม่ผ่านด่านตรวจข้อความอ้างอิง ผู้ใช้เห็นข้อความมาตรฐานของระบบ"""
        llm_client._SplitConnector(_Fake("bge-m3"), _Fake("gemini-3.5-flash")).chat([])
        self.assertIsNone(_engine(explained=False)["explanation"])

    def test_ไม่เรียกโมเดลเลย_ผลยังบอกวิธีให้คะแนนได้(self):
        engine = _engine(explained=True, scoring="embedding_and_rules")
        self.assertIsNone(engine["explanation"])
        self.assertEqual(engine["scoring"], "embedding_and_rules")

    def test_ไม่มีคีย์หรือข้อมูลการเชื่อมต่อหลุดไปกับผล(self):
        """
        เกณฑ์ข้อนี้ถูกแก้สองครั้งเมื่อ 29-30 ต.ค. 2569 — เพิ่ม "embedding" แล้วตามด้วย
        "writers" เข้าไปในชุดคีย์ที่ยอมรับ

        ทั้งสองช่องคือชื่อผู้ให้บริการกับชื่อรุ่น เหมือนช่อง explanation ที่มีอยู่เดิม
        ไม่ใช่คีย์หรือข้อมูลการเชื่อมต่อ (writers คือรายชื่อทุกรุ่นที่เขียนข้อความให้คำขอนี้
        ซึ่งมีได้มากกว่าหนึ่งเมื่อเจ้าหลักล้มกลางทาง ดู test_score_detail.py) · ข้อตรวจเดิม
        ที่ว่า "ไม่มีช่องอื่นหลุดออกไป" ยังอยู่ครบ เพราะยังเทียบชุดคีย์แบบตรงตัวทุกชั้น
        """
        llm_client._SplitConnector(_Fake("bge-m3"), _Fake("gemini-3.5-flash")).chat([])
        engine = _engine(explained=True, scoring="embedding_and_rules")
        self.assertEqual(set(engine), {"explanation", "writers", "scoring", "embedding"})
        self.assertEqual(set(engine["explanation"]), {"provider", "model"})
        self.assertEqual([set(w) for w in engine["writers"]], [{"provider", "model"}])


if __name__ == "__main__":
    unittest.main(verbosity=2)
