"""
หน้าแนะนำสาขาและหน้าเปรียบเทียบต้องมีเพดานเวลาของคำขอ

    cd backend && python tests/test_result_page_budget.py

ไม่ต่อฐานข้อมูล ไม่เรียกโมเดล — แทนงานจริงด้วยของจับพฤติกรรม

ที่มาของชุดนี้ — วัดจาก production เมื่อ 29 ต.ค. 2569
----------------------------------------------------
คำขอ `/recommend-major` เวลา 09:29:01 ตอบกลับ 09:35:16 รวม **6 นาที 15 วินาที**
และหน้าเว็บหมุนรอทั้งหมดนั้น · ลำดับเหตุการณ์จาก log

    09:29:01  embedding เสร็จ (เร็วปกติ)
    09:29:04-16  Gemini ตอบ 503 ครบทั้งสี่รุ่น แล้วถูกพักไว้รุ่นละ 60 วินาที
    09:29:16  ตกไปใช้โมเดลในเครื่อง
    09:31:16 / 09:33:16 / 09:35:16  ollama /api/chat ReadTimeout ครั้งที่ 1/2/3
    09:35:16  คืน 200 พร้อมข้อความมาตรฐานแทนเหตุผล

ต้นเหตุคือสองเส้นทางนี้ไม่เคยตั้งเพดานเวลา ต่างจาก /chat-web ที่ตั้งไว้ตั้งแต่ต้น
เมื่อไม่มีเพดาน `http_timeout()` จะไม่หดเวลาของคำขอ HTTP และ `check_budget()`
ไม่มีอะไรให้ตรวจ คำขอจึงยาวเท่ากับ ReadTimeout ของ Ollama คูณจำนวนครั้งที่ลองซ้ำ
"""
import os
import sys
import unittest
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://unused:unused@127.0.0.1:1/unused")
os.environ.setdefault("JWT_SECRET", "ชุดทดสอบไม่ได้ออก token")
os.environ.setdefault("GEMINI_API_KEY", "คีย์ปลอมสำหรับชุดทดสอบ")

from llm.connector import budget_left_s, reset_budget  # noqa: E402

from app.api.routes import web_compat  # noqa: E402


class ResultPageBudgetTests(unittest.TestCase):
    def setUp(self):
        reset_budget()
        self.real_compare = web_compat._compare_courses
        self.real_recommend = web_compat._recommend_major

    def tearDown(self):
        web_compat._compare_courses = self.real_compare
        web_compat._recommend_major = self.real_recommend
        reset_budget()

    def test_เพดานถูกตั้งไว้สมเหตุผล(self):
        """ยาวพอสำหรับคำขอปกติ (วัดได้ 9-35 วินาที) แต่สั้นกว่าของเดิมหลายเท่า"""
        self.assertGreaterEqual(web_compat.RESULT_PAGE_BUDGET_S, 60)
        self.assertLessEqual(web_compat.RESULT_PAGE_BUDGET_S, 120)

    def test_หน้าเปรียบเทียบ_มีเพดานเวลาระหว่างทำงาน(self):
        seen = {}

        def fake(_payload, _db):
            seen["left"] = budget_left_s()
            return {"ok": True}

        web_compat._compare_courses = fake
        web_compat.compare_courses_web(payload=None, db=None)

        self.assertIsNotNone(seen["left"], "ไม่มีเพดานเวลาระหว่างทำงาน")
        self.assertLessEqual(seen["left"], web_compat.RESULT_PAGE_BUDGET_S)
        self.assertGreater(seen["left"], 0)

    def test_หน้าแนะนำสาขา_มีเพดานเวลาระหว่างทำงาน(self):
        seen = {}

        def fake(_payload, _db):
            seen["left"] = budget_left_s()
            return {"ok": True}

        web_compat._recommend_major = fake
        web_compat.recommend_major_web(payload=None, db=None)

        self.assertIsNotNone(seen["left"], "ไม่มีเพดานเวลาระหว่างทำงาน")
        self.assertLessEqual(seen["left"], web_compat.RESULT_PAGE_BUDGET_S)

    def test_ล้างเพดานหลังจบเสมอ_แม้คำขอจะล้ม(self):
        """เพดานที่ค้างอยู่จะไปตัดงานถัดไปในบริบทเดียวกันโดยไม่มีใครรู้"""
        def ok(_payload, _db):
            return {}

        def boom(_payload, _db):
            raise RuntimeError("จำลองว่างานล้ม")

        web_compat._compare_courses = ok
        web_compat.compare_courses_web(payload=None, db=None)
        self.assertIsNone(budget_left_s(), "ไม่ได้ล้างเพดานหลังสำเร็จ")

        web_compat._recommend_major = boom
        with self.assertRaises(RuntimeError):
            web_compat.recommend_major_web(payload=None, db=None)
        self.assertIsNone(budget_left_s(), "ไม่ได้ล้างเพดานหลังล้ม")


if __name__ == "__main__":
    unittest.main(verbosity=2)
