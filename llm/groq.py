"""
ตัวเชื่อมต่อ Groq — **ของทดลอง ยังไม่ได้ใช้ใน production**

สร้างไว้เพื่อ "วัด" ว่าควรใช้ Groq เป็นผู้ให้บริการสำรองของ Gemini หรือไม่
ตัวไฟล์นี้ยังไม่ถูกเรียกจากที่ใดในระบบจริง — `services/llm_client.py` ยังไม่รู้จักมัน
ผู้ที่เรียกใช้มีเพียง `eval/groq_candidate_check.py` ซึ่งเป็นชุดวัดที่รันแยกจาก production

ขอบเขต
------
รับผิดชอบเฉพาะการ "เขียนคำตอบ" เท่านั้น **ไม่มี embed() โดยตั้งใจ** เหมือน GeminiConnector
เวกเตอร์ของเอกสารทั้งคลังสร้างด้วย bge-m3 ขนาด 1024 มิติผ่าน Ollama ในเครื่อง
การเปลี่ยนโมเดล embedding แปลว่าต้องคำนวณใหม่ทั้งคลังและแก้ชนิดคอลัมน์ในฐานข้อมูล
**Ollama จึงยังเป็นผู้ทำ embedding เสมอไม่ว่าจะเลือกผู้ให้บริการใดมาเขียนคำตอบ**

API ของ Groq เข้ากันได้กับรูปแบบของ OpenAI (`/openai/v1/chat/completions`)
จึงแปลงข้อความตรงไปตรงมา ไม่ต้องแยก systemInstruction ออกมาเหมือน Gemini

SECURITY
--------
  - คีย์ส่งผ่าน header `Authorization: Bearer …` และ **ต้องมาจากตัวแปรสภาพแวดล้อม
    เท่านั้น** ห้ามเขียนลงไฟล์นี้หรือไฟล์ตั้งค่าใด ๆ ที่เข้า git
  - `api_key` ตั้ง `repr=False` เหมือน GeminiConnector เพราะ @dataclass สร้าง __repr__
    ที่พิมพ์ทุกฟิลด์ ถ้าไม่กันไว้ คีย์จะหลุดออกไปทุกที่ที่มีการ repr ตัวเชื่อมต่อ
    ทั้ง traceback, logger.exception หรือการ debug ด้วยมือ (เคยหลุดมาแล้วเมื่อ 13 ต.ค. 2569)
  - ไม่ log เนื้อหา prompt/response และไม่ log ตัวคีย์

สิ่งที่ตัวนี้ "ไม่" ทำ
--------------------
ไม่มีการหมุนโมเดลสำรองในตัวเองแบบ GeminiConnector เพราะหน้าที่ของมันในการทดลองนี้คือ
เป็น "ผู้ให้บริการรายที่สอง" ซึ่งการหมุนภายในจะทำให้แยกไม่ออกว่าผลที่วัดได้มาจากโมเดลใด
"""
from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

import httpx

from llm.connector import (ChatMessage, LLMConnectionError, check_budget,
                           http_timeout, post_json_bounded)

logger = logging.getLogger("llm.groq")

_BASE_URL = "https://api.groq.com/openai/v1"

# header ที่ Groq ส่งกลับมาบอกโควตาที่เหลือ — เก็บไว้รายงาน ไม่ได้ใช้ตัดสินใจอะไรในโค้ด
#
# ต้องอ่านจากของจริงเพราะเอกสารหน้า rate-limits ไม่ได้บอกเพดานของบัญชีเรา
# มันบอกแค่ว่าให้ดูหน้า /settings/limits ของบัญชีตัวเอง
QUOTA_HEADERS = (
    "x-ratelimit-limit-requests",
    "x-ratelimit-remaining-requests",
    "x-ratelimit-reset-requests",
    "x-ratelimit-limit-tokens",
    "x-ratelimit-remaining-tokens",
    "x-ratelimit-reset-tokens",
    "retry-after",
)


class GroqQuotaExceeded(LLMConnectionError):
    """
    ชนเพดานของผู้ให้บริการ (HTTP 429) — ต้องแยกออกจาก "ตอบผิด" เสมอ

    ถ้านับรวมกัน ผลวัดจะบอกว่าโมเดลคุณภาพแย่ ทั้งที่จริงแล้วมันไม่เคยได้ตอบเลย
    """

    def __init__(self, message: str, retry_after_s: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_s = retry_after_s


class GroqServiceError(LLMConnectionError):
    """ฝั่งผู้ให้บริการขัดข้อง (5xx) — คนละเรื่องกับคำตอบผิดเช่นกัน"""


def api_key_from_env(var: str = "GROQ_API_KEY") -> str:
    """
    อ่านคีย์จากตัวแปรสภาพแวดล้อม — ไม่มีทางอื่นโดยตั้งใจ

    ตัดช่องว่างและอักขระขึ้นบรรทัดใหม่ทิ้ง เพราะการคัดลอกคีย์จากเบราว์เซอร์บน Windows
    พ่วง CR (\\r) มาด้วย แล้ว httpx จะปฏิเสธตั้งแต่ตอนประกอบคำขอด้วย "Illegal header
    value" ซึ่งพ่นค่าของหัวข้อความออกมาใน traceback — คีย์รั่วทันที (บทเรียนจาก gemini.py)
    """
    raw = (os.getenv(var) or "").strip()
    if not raw:
        raise LLMConnectionError(
            f"ไม่ได้ตั้ง {var} — ตั้งผ่านตัวแปรสภาพแวดล้อมเท่านั้น ห้ามเขียนลงไฟล์ในโปรเจกต์"
        )
    return raw


@dataclass
class GroqConnector:
    api_key: str = field(repr=False)

    # ชื่อโมเดลต้องส่งเข้ามาเสมอ ไม่มีค่าตั้งต้นโดยตั้งใจ
    #
    # รายชื่อโมเดลของ Groq เปลี่ยนบ่อยและบางตัวถูกปลดระวางโดยแจ้งล่วงหน้าไม่นาน
    # การฝังชื่อไว้เป็นค่าตั้งต้นทำให้โค้ดชี้ไปยังโมเดลที่อาจไม่มีอยู่แล้ว
    # ให้ผู้เรียกอ่านรายชื่อที่ใช้ได้จริงจาก list_models() ก่อนเสมอ
    chat_model: str = ""

    timeout_s: int = 120
    max_retries: int = 2
    answer_token_cap: int = 2048

    # ตัวรับแจ้งเหตุการณ์สำหรับนับสถิติ — รูปแบบเดียวกับ GeminiConnector
    on_event: Callable[[str], None] | None = field(default=None, repr=False)

    _client: httpx.Client = field(init=False, repr=False)

    # โควตาที่อ่านได้จากคำตอบครั้งล่าสุด — ใช้รายงาน ไม่ได้ใช้ตัดสินใจ
    last_quota: dict[str, str] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        self.api_key = self.api_key.strip()
        if not self.api_key:
            raise LLMConnectionError("ไม่ได้ตั้ง GROQ_API_KEY")
        if not self.chat_model:
            raise LLMConnectionError("ต้องระบุชื่อโมเดล — อ่านรายชื่อที่ใช้ได้จาก list_models() ก่อน")
        self._client = httpx.Client(
            base_url=_BASE_URL,
            timeout=self.timeout_s,
            headers={"Authorization": f"Bearer {self.api_key}",
                     "Content-Type": "application/json"},
        )

    # ------------------------------------------------------------------
    def _note(self, event: str) -> None:
        """บอกตัวนับว่าเกิดอะไรขึ้น — ห้ามทำให้การตอบคำถามล้ม"""
        if self.on_event is None:
            return
        try:
            self.on_event(event)
        except Exception:  # noqa: BLE001
            logger.debug("ตัวนับภายนอกทำงานไม่ได้", exc_info=True)

    def _remember_quota(self, headers) -> None:
        self.last_quota = {k: headers[k] for k in QUOTA_HEADERS if k in headers}

    def _raise_for(self, resp: httpx.Response) -> None:
        """
        แปลงคำตอบที่ผิดพลาดเป็นข้อยกเว้นที่ "แยกชนิดได้"

        แยกสามอย่างออกจากกันเสมอ: ชนเพดาน (429) · ฝั่งผู้ให้บริการพัง (5xx) ·
        เราส่งผิดเอง (4xx อื่น) เพราะสามอย่างนี้นำไปสู่คนละข้อสรุปในการประเมิน
        """
        self._remember_quota(resp.headers)
        code = resp.status_code
        body = ""
        try:
            body = resp.text[:300]
        except Exception:  # noqa: BLE001
            pass
        if code == 429:
            wait = resp.headers.get("retry-after")
            raise GroqQuotaExceeded(
                f"groq ชนเพดานคำขอ (429) retry-after={wait or 'ไม่ระบุ'} · {body}",
                retry_after_s=float(wait) if wait and wait.replace(".", "", 1).isdigit() else None,
            )
        if code >= 500:
            raise GroqServiceError(f"groq ขัดข้องฝั่งผู้ให้บริการ ({code}) · {body}")
        if code in (401, 403):
            raise LLMConnectionError("groq ปฏิเสธคีย์ — ตรวจค่า GROQ_API_KEY ในตัวแปรสภาพแวดล้อม")
        if code == 404:
            raise LLMConnectionError(
                f"groq ไม่รู้จักโมเดล {self.chat_model!r} — อ่านรายชื่อที่ใช้ได้จริงจาก list_models()"
            )
        raise LLMConnectionError(f"groq ตอบรหัส {code}: {body}")

    @staticmethod
    def _to_payload(messages: list[ChatMessage], temperature: float,
                    json_mode: bool, num_predict: int | None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
        }
        if num_predict is not None:
            payload["max_completion_tokens"] = num_predict
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        return payload

    # ------------------------------------------------------------------
    def chat(self, messages: list[ChatMessage], temperature: float = 0.2,
             json_mode: bool = False, num_predict: int | None = None) -> str:
        payload = self._to_payload(messages, temperature, json_mode, num_predict)
        payload["model"] = self.chat_model
        last_exc: Exception | None = None

        for attempt in range(1, self.max_retries + 2):
            check_budget(f"เรียก groq {self.chat_model} ครั้งที่ {attempt}")
            try:
                resp = self._client.post(
                    "/chat/completions", json=payload,
                    timeout=http_timeout(self.timeout_s, f"เรียก groq ครั้งที่ {attempt}"),
                )
                if resp.is_error:
                    self._raise_for(resp)
                self._remember_quota(resp.headers)
                data = resp.json()
                text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
                if not text:
                    reason = (data.get("choices") or [{}])[0].get("finish_reason", "ไม่ทราบสาเหตุ")
                    raise LLMConnectionError(f"groq ไม่คืนข้อความ (finish_reason={reason})")
                self._note(f"groq_ok:{self.chat_model}")
                return text
            except (GroqQuotaExceeded, GroqServiceError) as e:
                # ไม่ลองซ้ำกับเพดานหรือบริการขัดข้อง — ผู้เรียกต้องรู้ว่าเกิดอะไรขึ้นจริง
                self._note("groq_quota" if isinstance(e, GroqQuotaExceeded) else "groq_service_error")
                raise
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_exc = e
                self._note("groq_timeout")
                logger.warning("groq attempt %d/%d failed: %s",
                               attempt, self.max_retries + 1, type(e).__name__)
                if attempt <= self.max_retries:
                    time.sleep(2 * attempt)
        raise LLMConnectionError(f"groq ล้มเหลวหลังลอง {self.max_retries + 1} ครั้ง: {last_exc}") from last_exc

    def chat_stream(self, messages: list[ChatMessage], temperature: float = 0.2,
                    num_predict: int | None = None) -> Iterator[str]:
        """
        สตรีมคำตอบ — ลองใหม่ได้เฉพาะเมื่อยังไม่ได้ส่งตัวอักษรแรกออกไป

        เหตุผลเดียวกับ GeminiConnector: ถ้าลองใหม่หลังส่งข้อความไปแล้ว ผู้ใช้จะเห็น
        คำตอบซ้ำสองรอบ
        """
        payload = self._to_payload(messages, temperature, json_mode=False, num_predict=num_predict)
        payload["model"] = self.chat_model
        payload["stream"] = True
        last_exc: Exception | None = None

        for attempt in range(1, self.max_retries + 2):
            check_budget(f"สตรีมจาก groq {self.chat_model} ครั้งที่ {attempt}")
            started = False
            try:
                with self._client.stream(
                    "POST", "/chat/completions", json=payload,
                    timeout=http_timeout(self.timeout_s, f"เริ่มสตรีมจาก groq ครั้งที่ {attempt}"),
                ) as resp:
                    if resp.is_error:
                        # ต้องอ่านเนื้อความก่อน ไม่งั้นแยกชนิดข้อผิดพลาดไม่ได้
                        resp.read()
                        self._raise_for(resp)
                    self._remember_quota(resp.headers)
                    for line in resp.iter_lines():
                        check_budget(f"อ่านสตรีมจาก groq {self.chat_model}")
                        if not line.startswith("data: "):
                            continue
                        chunk = line[6:].strip()
                        if chunk == "[DONE]":
                            break
                        try:
                            delta = (json.loads(chunk).get("choices") or [{}])[0].get("delta", {})
                        except json.JSONDecodeError:
                            continue
                        if piece := delta.get("content"):
                            started = True
                            yield piece
                self._note(f"groq_ok:{self.chat_model}")
                return
            except (GroqQuotaExceeded, GroqServiceError) as e:
                self._note("groq_quota" if isinstance(e, GroqQuotaExceeded) else "groq_service_error")
                raise
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                if started or attempt > self.max_retries:
                    raise LLMConnectionError(f"groq stream ล้มเหลว: {type(e).__name__}") from e
                last_exc = e
                self._note("groq_timeout")
                time.sleep(2 * attempt)
        raise LLMConnectionError(f"groq stream ล้มเหลวหลังลอง {self.max_retries + 1} ครั้ง: {last_exc}")


def list_models(api_key: str, timeout_s: int = 30) -> list[dict[str, Any]]:
    """
    รายชื่อโมเดลที่ **บัญชีนี้** เรียกใช้ได้จริง พร้อมข้อมูลที่ API คืนมา

    ต้องเรียกตัวนี้ก่อนเลือกชื่อโมเดลเสมอ ห้ามยึดชื่อจากเอกสารหรือจากบทสนทนา
    เพราะรายชื่อของ Groq เปลี่ยนบ่อย และบางตัวที่อยู่ในเอกสารก็ถูกปลดระวางไปแล้ว
    """
    with httpx.Client(base_url=_BASE_URL, timeout=timeout_s,
                      headers={"Authorization": f"Bearer {api_key.strip()}"}) as client:
        resp = client.get("/models")
        if resp.status_code in (401, 403):
            raise LLMConnectionError("groq ปฏิเสธคีย์ — ตรวจค่า GROQ_API_KEY")
        resp.raise_for_status()
        return resp.json().get("data", [])
