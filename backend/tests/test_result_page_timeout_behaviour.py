"""
สองหน้าผลลัพธ์ "เมื่อหมดเวลา" ตอบอะไรกลับไปกันแน่

    cd backend && python tests/test_result_page_timeout_behaviour.py

ไม่ต่อฐานข้อมูล ไม่เรียกโมเดล — แทนขั้นที่เรียกโมเดลด้วยของจำลองที่โยน
LLMBudgetExceeded เหมือนตอนเพดานเวลาหมดจริง

ทำไมต้องมีชุดนี้
---------------
"หมดเวลา" ของสองหน้านี้ไม่ได้จบเหมือนกัน และการเขียนรายงานว่า "ได้ 503 เสมอ" คือ
การบอกพฤติกรรมผิด

    /compare-courses   ข้อความเปรียบเทียบคือตัวผลลัพธ์ทั้งหมด ถ้าเขียนไม่ได้ก็ไม่มีอะไร
                       จะแสดง จึงต้องเป็น 503 พร้อมข้อความบอกเหตุ
    /recommend-major   อันดับและคะแนนคำนวณเสร็จก่อนเรียกโมเดล และไม่ได้พึ่งโมเดลเลย
                       เมื่อหมดเวลาตอนเขียนคำอธิบาย ผู้ใช้ยังควรได้อันดับครบ จึงเป็น
                       **200 พร้อมข้อความมาตรฐานแทนเหตุผล** ไม่ใช่ 503
                       แต่ถ้าหมดเวลาตั้งแต่ขั้นจัดอันดับ (ซึ่งต้องใช้ embedding) จะไม่มี
                       อะไรให้แสดงเลย กรณีนั้นถึงจะเป็น 503
"""
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://unused:unused@127.0.0.1:1/unused")
os.environ.setdefault("JWT_SECRET", "ชุดทดสอบไม่ได้ออก token")
os.environ.setdefault("GEMINI_API_KEY", "คีย์ปลอมสำหรับชุดทดสอบ")

from fastapi.testclient import TestClient  # noqa: E402

from llm.connector import LLMBudgetExceeded  # noqa: E402

from app.api.routes import web_compat  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402

TITLE = "วิทยาการคอมพิวเตอร์"
SENT = [{"id": "web-1", "title": TITLE}, {"id": "web-2", "title": "เทคโนโลยีสารสนเทศ"}]
# ข้อความที่ระบบใช้แทนเหตุผลเมื่อโมเดลเขียนให้ไม่ได้ (ของเดิม ไม่ได้แก้ในรอบนี้)
NO_REASON = web_compat.NO_REASON

TIMED_OUT = LLMBudgetExceeded(
    "ระบบใช้เวลาตอบเกินเพดานที่ตั้งไว้ขณะที่ผู้ให้บริการโมเดลขัดข้อง จึงหยุดรอ",
    user_text="ระบบใช้เวลาตอบนานเกินเพดานที่ตั้งไว้ จึงหยุดรอครับ",
)


def _fake_course(title: str):
    return SimpleNamespace(id="course-1", title=title)


class TimeoutBehaviourTests(unittest.TestCase):
    def setUp(self):
        app.dependency_overrides[get_db] = lambda: None
        self.client = TestClient(app, raise_server_exceptions=False)
        self.saved = {name: getattr(web_compat, name) for name in
                      ("match_by_title", "match_programs", "compare_programs",
                       "build_profile_text", "confidence_of")}
        web_compat.match_by_title = lambda db, sent: (
            [({"id": c["id"]}, _fake_course(c["title"])) for c in sent], [])
        web_compat.build_profile_text = lambda answers: "โปรไฟล์ทดสอบ"
        web_compat.confidence_of = lambda matches: "high"

    def tearDown(self):
        for name, value in self.saved.items():
            setattr(web_compat, name, value)
        app.dependency_overrides.clear()

    # ---------------- หน้าเปรียบเทียบ ----------------

    def test_เปรียบเทียบ_หมดเวลา_ต้องเป็น_503_พร้อมข้อความบอกเหตุ(self):
        def timed_out(*_a, **_k):
            raise TIMED_OUT

        web_compat.compare_programs = timed_out
        res = self.client.post("/compare-courses", json={"courses": SENT})

        self.assertEqual(res.status_code, 503, res.text)
        detail = res.json().get("detail", "")
        # ต้องเป็นข้อความที่เขียนไว้ให้ผู้ใช้อ่าน ไม่ใช่ข้อความวินิจฉัยภายใน
        self.assertEqual(detail, TIMED_OUT.user_text)
        self.assertNotIn("ขั้นที่กำลังทำ", detail)

    # ---------------- หน้าแนะนำสาขา ----------------

    def test_แนะนำสาขา_หมดเวลาตอนจัดอันดับ_ต้องเป็น_503(self):
        """ขั้นจัดอันดับใช้ embedding ถ้าล้มตรงนี้ไม่มีอะไรให้แสดงเลย"""
        def timed_out(*_a, **_k):
            raise TIMED_OUT

        web_compat.match_programs = timed_out
        res = self.client.post("/recommend-major", json={"answers": {}, "courses": SENT})

        self.assertEqual(res.status_code, 503, res.text)
        self.assertEqual(res.json().get("detail"), TIMED_OUT.user_text)

    def test_แนะนำสาขา_หมดเวลาตอนเขียนคำอธิบาย_ได้_200_พร้อมอันดับ(self):
        """
        อันดับกับคะแนนคำนวณเสร็จก่อนเรียกโมเดลและไม่ได้พึ่งโมเดล — ผู้ใช้ยังได้ผลครบ

        นี่คือจุดที่รายงานฉบับแรกเขียนผิดว่า "หมดเวลาแล้วได้ 503"
        """
        def ranked_without_rationale(*_a, **_k):
            # เหมือนกับที่ match_programs คืนเมื่อ _generate_rationales ล้ม: เหตุผลว่าง
            return [SimpleNamespace(title=TITLE, match_percent=72, rationale="")]

        web_compat.match_programs = ranked_without_rationale
        res = self.client.post("/recommend-major", json={"answers": {}, "courses": SENT})

        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual(body["primary"]["matchScore"], 72)
        self.assertEqual(body["primary"]["reason"], NO_REASON,
                         "ต้องเป็นข้อความมาตรฐานของระบบ ไม่ใช่ข้อความว่าง")
        # ไม่ได้ใช้ข้อความของโมเดลเลย จึงต้องไม่ติดป้ายชื่อรุ่น
        self.assertIsNone(body["engine"]["explanation"])
        self.assertEqual(body["engine"]["scoring"], "embedding_and_rules")


if __name__ == "__main__":
    unittest.main(verbosity=2)
