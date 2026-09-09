"""
ตรวจว่าตัวเชื่อม Gemini รับมือกับ 429 สองชนิดต่างกันจริง

ทำไมต้องทดสอบแบบไม่เรียกของจริง
-------------------------------
การทำให้ Google ส่ง 429 ชนิดที่ต้องการกลับมาตามสั่งนั้นทำไม่ได้ และการยิงจนชนเพดาน
จริงก็เผาโควตาที่มีจำกัด จึงปลอมคำตอบด้วย MockTransport แล้วดูว่าโค้ดตัดสินใจอย่างไร

เหตุที่ต้องมี
------------
เพดานต่อนาทีกับโควตารายวันมาเป็น HTTP 429 เหมือนกัน แต่ต้องรับมือคนละแบบสิ้นเชิง
ตอนแรกเหมาเป็นรายวันทั้งคู่ โมเดลที่ยังใช้ได้จึงถูกพักทีละตัวจนหมดเพราะยิงเร็วไป
ไม่กี่วินาที แก้รอบสองแล้วนั่งรอกับตัวเดิม 2-4-8 วินาทีแล้วยอมแพ้ ซึ่งไม่พอเพราะ
Google ขอให้รอราวสามสิบวินาที ผลคือตกไปใช้โมเดลในเครื่องทั้งที่ยังมีตัวอื่นว่างอยู่

    python -m eval.gemini_quota_check
"""
from __future__ import annotations

import unittest

import httpx

from llm.connector import ChatMessage
from llm.gemini import GeminiConnector, _cooldown_for, _is_daily_limit

DAILY = ('{"error":{"code":429,"details":[{"@type":"type.googleapis.com/google.rpc.QuotaFailure",'
         '"violations":[{"quotaId":"GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]},'
         '{"@type":"type.googleapis.com/google.rpc.RetryInfo","retryDelay":"24s"}]}}')
PER_MINUTE = ('{"error":{"code":429,"details":[{"@type":"type.googleapis.com/google.rpc.QuotaFailure",'
              '"violations":[{"quotaId":"GenerateRequestsPerMinutePerProjectPerModel-FreeTier"}]},'
              '{"@type":"type.googleapis.com/google.rpc.RetryInfo","retryDelay":"31s"}]}}')
OPAQUE = '{"error":{"code":429,"message":"Resource has been exhausted."}}'

OK_BODY = {"candidates": [{"content": {"parts": [{"text": "คำตอบ"}]}}]}


def connector(handler) -> GeminiConnector:
    c = GeminiConnector(api_key="test-key", chat_model="main")
    c.fallback_models = ("backup1", "backup2")
    c._client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://test")
    return c


class QuotaKindChecks(unittest.TestCase):
    def test_แยกชนิดของ429ได้(self):
        self.assertTrue(_is_daily_limit(httpx.Response(429, text=DAILY)))
        self.assertFalse(_is_daily_limit(httpx.Response(429, text=PER_MINUTE)))
        # ไม่บอกชนิดมา ให้เดาเป็นรายวัน เพราะย้ายโมเดลเสียหายน้อยกว่าวนรอ
        self.assertTrue(_is_daily_limit(httpx.Response(429, text=OPAQUE)))

    def test_ระยะพักต่างกันตามชนิด(self):
        self.assertEqual(_cooldown_for(httpx.Response(429, text=DAILY)), 4 * 3600.0)
        # ต่อนาที: ยาวพอจะพ้นเพดานจริง แต่ไม่ใช่หลักชั่วโมง
        minute = _cooldown_for(httpx.Response(429, text=PER_MINUTE))
        self.assertGreaterEqual(minute, 33.0)
        self.assertLess(minute, 120.0)

    def test_เพดานต่อนาทีต้องย้ายไปโมเดลถัดไปไม่ใช่ยอมแพ้(self):
        """
        อาการที่เจอจริง: ตัวหลักชนเพดานต่อนาที แล้วทั้งคำขอล้มไปใช้โมเดลในเครื่อง
        ทั้งที่ตัวสำรองยังยิงได้ เพราะเพดานต่อนาทีเป็นแบบต่อโมเดล
        """
        seen = []

        def handler(request: httpx.Request) -> httpx.Response:
            model = request.url.path.split("/models/")[1].split(":")[0]
            seen.append(model)
            if model == "main":
                return httpx.Response(429, text=PER_MINUTE)
            return httpx.Response(200, json=OK_BODY)

        text = connector(handler).chat([ChatMessage(role="user", content="ถาม")])
        self.assertEqual(text, "คำตอบ")
        self.assertEqual(seen, ["main", "backup1"])

    def test_พักตัวที่ชนเพดานต่อนาทีไว้ไม่นาน(self):
        """พักสั้น ไม่ใช่สี่ชั่วโมง ไม่งั้นยิงรัวทีเดียวก็เผาโมเดลสำรองหมด"""
        def handler(request: httpx.Request) -> httpx.Response:
            model = request.url.path.split("/models/")[1].split(":")[0]
            if model == "main":
                return httpx.Response(429, text=PER_MINUTE)
            return httpx.Response(200, json=OK_BODY)

        c = connector(handler)
        c.chat([ChatMessage(role="user", content="ถาม")])
        remaining = c._exhausted["main"] - __import__("time").time()
        self.assertLess(remaining, 120.0, "เพดานต่อนาทีไม่ควรพักโมเดลเป็นชั่วโมง")

    def test_โควตารายวันพักยาว(self):
        def handler(request: httpx.Request) -> httpx.Response:
            model = request.url.path.split("/models/")[1].split(":")[0]
            if model == "main":
                return httpx.Response(429, text=DAILY)
            return httpx.Response(200, json=OK_BODY)

        c = connector(handler)
        c.chat([ChatMessage(role="user", content="ถาม")])
        remaining = c._exhausted["main"] - __import__("time").time()
        self.assertGreater(remaining, 3000.0, "โควตารายวันต้องพักยาว ไม่ใช่กลับไปยิงซ้ำ")


if __name__ == "__main__":
    unittest.main(verbosity=2)
