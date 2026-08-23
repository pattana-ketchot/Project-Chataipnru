"""
ตัวเชื่อมต่อโมเดล Gemini ของ Google — ทางเลือกแทนโมเดลในเครื่องสำหรับ "การเขียนคำตอบ"

ทำไมต้องมี
----------
เซิร์ฟเวอร์ที่ deploy จริงไม่มีการ์ดจอ วัดได้ว่าอ่านพรอมต์เข้าโมเดลได้ราว 40 โทเคน
ต่อวินาที และเขียนคำตอบได้ราว 6.5 โทเคนต่อวินาที คำถามหนึ่งข้อจึงใช้เวลาราว 70 วินาที
กว่าตัวอักษรแรกจะออกมา ซึ่งช้าเกินกว่าจะให้คนทั่วไปลองใช้

คลาสนี้ใช้ interface เดียวกับ OllamaConnector ทุกประการ (chat / chat_stream) จึงสลับ
ไปมาได้ด้วยค่าตั้งค่าเดียว ไม่ต้องแก้โค้ดที่เรียกใช้เลย — เป็นเหตุผลที่แยก connector
ออกมาเป็นคลาสของตัวเองตั้งแต่แรก

ขอบเขต
------
รับผิดชอบเฉพาะการ "เขียนคำตอบ" เท่านั้น ไม่มี embed() โดยตั้งใจ เพราะเวกเตอร์ของ
เอกสารทั้ง 7,301 ชิ้นในฐานข้อมูลถูกสร้างด้วย bge-m3 ขนาด 1024 มิติ การเปลี่ยนโมเดล
embedding แปลว่าต้องคำนวณใหม่ทั้งหมดและแก้ชนิดคอลัมน์ในฐานข้อมูล ซึ่งไม่จำเป็น
ต่อการแก้ปัญหาความเร็ว การค้นเอกสารใช้เวลาไม่ถึง 3 วินาทีอยู่แล้ว

SECURITY
--------
  - API key ส่งผ่าน header `x-goog-api-key` ไม่ใช่ query string ตามที่ตัวอย่างใน
    เอกสารของ Google ใช้ เพราะ query string มักถูกบันทึกลง log ของ proxy และ
    เซิร์ฟเวอร์ระหว่างทางโดยที่เราควบคุมไม่ได้
  - ไม่ log เนื้อหา prompt/response และไม่ log ตัว key
  - ข้อควรรู้ที่ไม่ใช่เรื่องโค้ด: ชั้นใช้งานฟรีของ Google ระบุว่านำเนื้อหาไปพัฒนา
    ผลิตภัณฑ์ของเขา ต่างจากชั้นเสียเงินที่ระบุว่าไม่นำไปใช้ คำถามของผู้ใช้จึงออกจาก
    เครื่องเราไปด้วย ไม่เหมือนตอนใช้โมเดลในเครื่อง
"""
from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import httpx

from llm.connector import ChatMessage, LLMConnectionError

logger = logging.getLogger("llm.gemini")

_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


@dataclass
class GeminiConnector:
    api_key: str
    chat_model: str = "gemini-3.5-flash-lite"
    timeout_s: int = 120
    max_retries: int = 2
    _client: httpx.Client = field(init=False, repr=False)

    # เพดานความยาวคำตอบ ตั้งสูงกว่าฝั่งโมเดลในเครื่องมากโดยตั้งใจ
    #
    # โมเดลตระกูล Gemini 3 ใช้โทเคนไป "คิดในใจ" ก่อนเขียนคำตอบ และโทเคนส่วนนั้น
    # นับรวมในเพดานเดียวกัน วัดกับ gemini-3.6-flash: ตั้งเพดาน 400 แล้วถูกใช้ไปกับ
    # การคิด 381 เหลือเขียนคำตอบจริง 15 โทเคน คำตอบจึงขาดกลางประโยคโดยไม่มีสัญญาณ
    # เตือน (finishReason=MAX_TOKENS) ต้องเผื่อที่ให้ส่วนที่คิดด้วย
    #
    # รุ่น lite ไม่ใช้โทเคนคิดเลย ค่านี้จึงไม่มีผลกับมัน เป็นเพียงตาข่ายรองรับ
    answer_token_cap: int = 2048

    def __post_init__(self) -> None:
        # ตัดช่องว่างและอักขระขึ้นบรรทัดใหม่ที่อาจติดมาตอนวางคีย์ลงไฟล์ตั้งค่า
        #
        # เคยเจอมาแล้ว: การคัดลอกจากเบราว์เซอร์บน Windows พ่วง CR (\r) มาด้วย
        # httpx จึงปฏิเสธตั้งแต่ตอนประกอบคำขอด้วย "Illegal header value" ซึ่งพ่นค่า
        # ของหัวข้อความออกมาใน traceback — นั่นแปลว่า API key หลุดลง log ทันที
        # การตัดตรงนี้จึงกันทั้งข้อผิดพลาดที่ชี้ผิดทางและการทำคีย์รั่ว
        self.api_key = self.api_key.strip()
        if not self.api_key:
            raise LLMConnectionError("ไม่ได้ตั้ง GEMINI_API_KEY")
        self._client = httpx.Client(
            base_url=_BASE_URL,
            timeout=self.timeout_s,
            headers={"x-goog-api-key": self.api_key, "Content-Type": "application/json"},
        )

    # ------------------------------------------------------------------
    # แปลงรูปแบบข้อความ
    # ------------------------------------------------------------------
    @staticmethod
    def _to_payload(
        messages: list[ChatMessage],
        temperature: float,
        json_mode: bool,
        num_predict: int | None,
    ) -> dict[str, Any]:
        """
        แปลงข้อความรูปแบบเดียวกับ Ollama ให้เป็นรูปแบบของ Gemini

        ต่างกันสองจุด: Gemini แยกข้อความระบบออกมาเป็น systemInstruction ต่างหาก
        ไม่ปนอยู่ในลำดับบทสนทนา และเรียกฝั่งผู้ช่วยว่า "model" ไม่ใช่ "assistant"
        """
        system_parts = [m.content for m in messages if m.role == "system"]
        contents = [
            {"role": "model" if m.role == "assistant" else "user", "parts": [{"text": m.content}]}
            for m in messages
            if m.role != "system"
        ]

        config: dict[str, Any] = {"temperature": temperature}
        if num_predict is not None:
            config["maxOutputTokens"] = num_predict
        if json_mode:
            config["responseMimeType"] = "application/json"

        payload: dict[str, Any] = {"contents": contents, "generationConfig": config}
        if system_parts:
            payload["systemInstruction"] = {"parts": [{"text": "\n\n".join(system_parts)}]}
        return payload

    @staticmethod
    def _text_of(data: dict[str, Any]) -> str:
        """ดึงข้อความออกจากคำตอบหนึ่งก้อน คืนสตริงว่างถ้าก้อนนั้นไม่มีข้อความ"""
        for candidate in data.get("candidates", []):
            parts = candidate.get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts)
            if text:
                return text
        return ""

    # ------------------------------------------------------------------
    # Chat / generation
    # ------------------------------------------------------------------
    def chat(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.2,
        json_mode: bool = False,
        num_predict: int | None = None,
    ) -> str:
        payload = self._to_payload(messages, temperature, json_mode, num_predict)
        path = f"/models/{self.chat_model}:generateContent"

        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 2):
            try:
                resp = self._client.post(path, json=payload)
                resp.raise_for_status()
                data = resp.json()
                text = self._text_of(data)
                if not text:
                    # เกิดได้เมื่อคำตอบถูกตัวกรองความปลอดภัยบล็อก หรือชนเพดานความยาว
                    # ตั้งแต่ก่อนเขียนข้อความแรก — แยกให้เห็นเหตุผลจะแก้ปัญหาง่ายกว่า
                    reason = (data.get("candidates") or [{}])[0].get("finishReason", "ไม่ทราบสาเหตุ")
                    raise LLMConnectionError(f"Gemini ไม่คืนข้อความ (finishReason={reason})")
                return text
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_exc = e
                logger.warning("gemini attempt %d/%d failed: %s", attempt, self.max_retries + 1, type(e).__name__)
            except httpx.HTTPStatusError as e:
                # 429 = ใช้เกินโควตา ลองใหม่มีโอกาสผ่าน / 4xx อื่นคือเราส่งผิดเอง ลองใหม่ก็เท่าเดิม
                if e.response.status_code != 429 and e.response.status_code < 500:
                    raise LLMConnectionError(self._explain(e)) from e
                last_exc = e
                logger.warning("gemini HTTP %d attempt %d", e.response.status_code, attempt)
        raise LLMConnectionError(f"gemini ล้มเหลวหลังลอง {self.max_retries + 1} ครั้ง: {last_exc}") from last_exc

    def chat_stream(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.2,
        num_predict: int | None = None,
    ) -> Iterator[str]:
        """
        เหมือน chat() แต่ทยอยคืนข้อความระหว่างที่โมเดลกำลังเขียน

        ลองใหม่ได้เฉพาะกรณีที่ล้มก่อนข้อความแรกจะออกไป ซึ่งครอบคลุมการชนโควตา
        (429) ที่เจอบ่อยในชั้นใช้งานฟรี ถ้าล้มหลังส่งข้อความไปแล้วจะไม่ลองใหม่
        เพราะผู้ใช้จะเห็นคำตอบซ้ำสองรอบ (เหตุผลเดียวกับ OllamaConnector.chat_stream)
        """
        for attempt in range(1, self.max_retries + 2):
            started = False
            try:
                for chunk in self._stream_once(messages, temperature, num_predict):
                    started = True
                    yield chunk
                return
            except LLMConnectionError:
                if started or attempt > self.max_retries:
                    raise
                logger.warning("gemini stream ลองใหม่ครั้งที่ %d", attempt + 1)
                time.sleep(2 * attempt)

    def _stream_once(
        self,
        messages: list[ChatMessage],
        temperature: float,
        num_predict: int | None,
    ) -> Iterator[str]:
        payload = self._to_payload(messages, temperature, json_mode=False, num_predict=num_predict)
        path = f"/models/{self.chat_model}:streamGenerateContent"
        try:
            with self._client.stream("POST", path, json=payload, params={"alt": "sse"}) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    # รูปแบบ SSE: สนใจเฉพาะบรรทัด data: ส่วนบรรทัดว่างคือตัวคั่นเหตุการณ์
                    if not line.startswith("data: "):
                        continue
                    if text := self._text_of(json.loads(line[6:])):
                        yield text
        except httpx.HTTPStatusError as e:
            raise LLMConnectionError(self._explain(e)) from e
        except (httpx.HTTPError, json.JSONDecodeError) as e:
            raise LLMConnectionError(f"gemini stream ล้มเหลว: {type(e).__name__}: {e}"[:200]) from e

    @staticmethod
    def _explain(e: httpx.HTTPStatusError) -> str:
        """แปลงรหัสข้อผิดพลาดเป็นข้อความที่บอกได้ว่าต้องไปแก้ตรงไหน"""
        code = e.response.status_code
        if code in (401, 403):
            return "Gemini ปฏิเสธ API key — ตรวจว่า GEMINI_API_KEY ถูกต้องและเปิดใช้งานอยู่"
        if code == 429:
            return "ใช้เกินโควตาของ Gemini ในช่วงเวลานี้ กรุณารอสักครู่แล้วลองใหม่ครับ"
        if code == 404:
            return f"ไม่พบโมเดลชื่อ {e.request.url.path.split('/')[-1]} — ตรวจค่า GEMINI_MODEL"
        return f"Gemini ตอบรหัส {code}: {e.response.text[:150]}"
