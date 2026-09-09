import json
import tempfile
import unittest
import unittest.mock
from pathlib import Path

import httpx

from eval.chat_eval import EvaluationUnavailable, _ask_with_retry, save_records


class EvaluationChecks(unittest.TestCase):
    def test_unavailable_service_stops_without_retry(self):
        """503 คือฝั่งโมเดลตอบไม่ได้จริง ยิงต่อไปก็ได้ผลเดิม จึงหยุดทันที"""
        calls = []
        def respond(request):
            calls.append(request)
            return httpx.Response(503)
        with httpx.Client(transport=httpx.MockTransport(respond), base_url="http://test") as client:
            with self.assertRaises(EvaluationUnavailable):
                _ask_with_retry(client, {}, "question")
        self.assertEqual(len(calls), 1)

    def test_rate_limit_waits_instead_of_stopping(self):
        """
        429 มาจากตัวจำกัดคำขอของเราเอง (30 ต่อนาทีต่อบัญชี) ไม่ใช่จากผู้ให้บริการโมเดล

        เดิมข้อนี้รวมอยู่กับ 503 เพราะตอนเขียนเข้าใจว่า 429 แปลว่าโควตา Gemini หมด
        log ที่มีเวลาประทับพิสูจน์แล้วว่าไม่ใช่ — ชุดประเมินยิงจากบัญชีเดียว พอคำตอบ
        มาจากแคชซึ่งเร็วมากก็ทะลุเพดานของตัวเอง การหยุดทั้งชุดตรงนั้นทำให้รายงานว่า
        ประเมินได้ 30 จาก 118 ข้อ ทั้งที่ระบบตอบได้ปกติ
        """
        calls = []
        def respond(request):
            calls.append(request)
            # ชนเพดานครั้งแรก ครั้งที่สองผ่าน
            if len(calls) == 1:
                return httpx.Response(429)
            return httpx.Response(200, json={"reply": "ข้อมูลหลักสูตร", "status": "answered"})

        with httpx.Client(transport=httpx.MockTransport(respond), base_url="http://test") as client:
            with unittest.mock.patch("eval.chat_eval.time.sleep") as slept:
                data = _ask_with_retry(client, {}, "question")
        self.assertEqual(data["reply"], "ข้อมูลหลักสูตร")
        self.assertEqual(len(calls), 2, "ต้องถามซ้ำหลังรอ ไม่ใช่ยอมแพ้")
        slept.assert_called_once_with(60)

    def test_degraded_success_is_not_scored(self):
        transport = httpx.MockTransport(lambda request: httpx.Response(
            200, json={"reply": "ระบบหลักตอบไม่ได้ชั่วคราว"},
        ))
        with httpx.Client(transport=transport, base_url="http://test") as client:
            with self.assertRaises(EvaluationUnavailable):
                _ask_with_retry(client, {}, "question")

    def test_checkpoint_contains_completed_records(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "results.json"
            records = [{"reply": "ข้อมูลหลักสูตร"}]
            save_records(str(path), records)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), records)
            self.assertFalse(path.with_suffix(".json.tmp").exists())


if __name__ == "__main__":
    unittest.main()
