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
import os
import re
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

import httpx

from llm.connector import (ChatMessage, LLMBudgetExceeded, LLMConnectionError,
                           budget_left_s, check_budget, http_timeout,
                           note_answered_model, post_json_bounded)

logger = logging.getLogger("llm.gemini")


def _is_daily_limit(resp: httpx.Response) -> bool:
    """
    429 นี้เป็นโควตารายวันหรือแค่ยิงถี่เกินในนาทีนั้น

    ต้องแยกให้ออก เพราะสองอย่างนี้ต้องรับมือคนละแบบ — โควตารายวันหมดแล้วรอไม่ช่วย
    ต้องย้ายโมเดล ส่วนการยิงถี่เกินรอไม่กี่วินาทีก็ผ่าน การเหมาว่าเป็นรายวันทั้งคู่
    ทำให้โมเดลที่ยังใช้ได้ถูกพักไปสี่ชั่วโมงเพราะผู้ใช้บังเอิญถามติดกันเร็วไปหน่อย
    ซึ่งเผาโมเดลสำรองทิ้งทีละตัวโดยไม่จำเป็น

    Google บอกชนิดของโควตามาในเนื้อความอยู่แล้ว (quotaId ที่มีคำว่า PerDay หรือ
    PerMinute) และแนบเวลาที่ควรรอมาด้วย จึงอ่านจากคำตอบจริงแทนการเดา ถ้าอ่านไม่ได้
    ให้ถือว่าเป็นรายวัน เพราะการย้ายโมเดลเสียหายน้อยกว่าการวนรอโควตาที่ไม่มีวันคืนมา

    บันทึกไว้ด้วยว่าตัดสินจากอะไร เพราะเมื่อโมเดลถูกพัก log เดิมเขียนแค่ว่า "ชนโควตา
    รายวัน" ซึ่งเป็นข้อสรุปของโค้ดนี้ ไม่ใช่สิ่งที่ Google บอก ถ้าการตัดสินผิด (เช่น
    เนื้อความไม่ได้บอกชนิดมาเลยแล้วเราเดาว่ารายวัน) จะไม่มีอะไรให้ย้อนดูเลยว่าพักโมเดล
    ไปเพราะอะไร เนื้อความของ 429 เป็นข้อความแจ้งข้อผิดพลาด ไม่มีคำถามของผู้ใช้และไม่มี
    ตัวคีย์ จึงบันทึกบางส่วนได้โดยไม่ทำข้อมูลรั่ว
    """
    try:
        body = resp.text
    except Exception:
        logger.warning("429 อ่านเนื้อความไม่ได้ ถือว่าเป็นโควตารายวัน")
        return True
    if "PerMinute" in body or "perMinute" in body:
        logger.info("429 เป็นเพดานต่อนาที (เจอ PerMinute ในเนื้อความ)")
        return False
    if "PerDay" in body or "per day" in body.lower():
        logger.warning("429 เป็นโควตารายวัน (เจอ PerDay ในเนื้อความ)")
        return True
    m = re.search(r'"retryDelay"\s*:\s*"(\d+(?:\.\d+)?)s"', body)
    # รอไม่ถึงสองนาทีแปลว่าเป็นเพดานระยะสั้น ไม่ใช่โควตาที่หมดไปทั้งวัน
    if m and float(m.group(1)) < 120:
        logger.info("429 ให้รอ %ss ถือว่าเป็นเพดานระยะสั้น", m.group(1))
        return False
    logger.warning("429 ไม่ได้บอกชนิดโควตามา เดาว่าเป็นรายวัน — เนื้อความ: %r", body[:300])
    return True


# ระยะพักเมื่อชนเพดานต่อนาที ใช้เมื่อ Google ไม่ได้บอกเวลามาหรือบอกมาสั้นเกินจริง
_MINUTE_COOLDOWN_S = 45.0


def _cooldown_for(resp: httpx.Response) -> float:
    """
    พักโมเดลนี้ไว้กี่วินาทีหลังเจอ 429

    อ่านเวลาที่ Google แนะนำมาก่อน (retryDelay) เพราะเป็นค่าที่ผู้ให้บริการรู้ดีที่สุด
    แล้วยกพื้นขึ้นเล็กน้อย เพราะกลับไปยิงตรงวินาทีที่เขาบอกพอดีมักโดนซ้ำ
    """
    if _is_daily_limit(resp):
        return 4 * 3600.0
    try:
        m = re.search(r'"retryDelay"\s*:\s*"(\d+(?:\.\d+)?)s"', resp.text)
    except Exception:
        m = None
    return max(float(m.group(1)) + 2 if m else 0.0, _MINUTE_COOLDOWN_S)


class _QuotaExhausted(RuntimeError):
    """
    โมเดลหนึ่งชนเพดานคำขอ — ลองซ้ำกับตัวเดิมทันทีไม่ช่วย ต้องพักไว้ก่อน

    พก cooldown_s มาด้วยเพราะ "พักนานแค่ไหน" ต่างกันมากตามชนิดของเพดาน เพดานต่อนาที
    หายไปในไม่กี่สิบวินาที ส่วนโควตารายวันต้องรอถึงวันรุ่งขึ้น การใช้ระยะเดียวกันทั้งคู่
    คือสาเหตุที่โมเดลที่ยังใช้ได้ถูกพักทิ้งไปสี่ชั่วโมงเพราะยิงเร็วไปไม่กี่วินาที
    """

    def __init__(self, model: str, cooldown_s: float, kind: str | None = None):
        super().__init__(model)
        self.model = model
        self.cooldown_s = cooldown_s
        # ชนิดของเหตุการณ์สำหรับตัวนับ (services/llm_usage.py) — อ่านจากระยะพักที่
        # _cooldown_for ตัดสินไว้แล้ว ไม่ไปอ่านเนื้อความของคำตอบซ้ำอีกรอบ เพราะการ
        # ตัดสินซ้ำแปลว่ามีที่บอกชนิดโควตาสองแห่ง ซึ่งเพี้ยนจากกันได้
        #
        # เส้นแบ่งที่ 10 นาทีปลอดภัย: รายวันตั้งไว้ 4 ชั่วโมง ส่วนเพดานต่อนาทีถูกจำกัด
        # ไม่ให้เกินสองนาทีอยู่แล้ว (_is_daily_limit ถือว่าเกิน 120 วินาทีคือรายวัน)
        self.kind = kind or ("quota_day" if cooldown_s >= 600 else "quota_minute")


# พักโมเดลที่ตอบ 503 ไว้สั้น ๆ เพราะ Google บอกเองว่า "Spikes in demand are usually
# temporary" — ต่างจากโควตาที่ต้องรอเป็นชั่วโมง ตั้งสั้นไว้เพื่อกลับไปใช้ตัวที่ตั้งค่าไว้
# ให้เร็วที่สุดเมื่อมันว่าง ตั้งทับได้ด้วย GEMINI_OVERLOAD_COOLDOWN_S
_OVERLOAD_COOLDOWN_S = float(os.getenv("GEMINI_OVERLOAD_COOLDOWN_S", "60"))


class _Overloaded(_QuotaExhausted):
    """
    โมเดลหนึ่งตอบ 503 ซ้ำ ๆ — ฝั่งผู้ให้บริการรับไม่ไหว ต้องย้ายไปโมเดลอื่น

    สืบทอดจาก _QuotaExhausted โดยตั้งใจ เพราะวิธีรับมือเหมือนกันทุกอย่าง: พักตัวนี้ไว้
    แล้วไปลองตัวถัดไปในรายการ ผู้เรียกที่ดักจับ _QuotaExhausted อยู่แล้วจึงทำถูกทันที
    ต่างกันแค่ระยะเวลาพัก

    ที่มา: 13 ต.ค. 2569 `gemini-3.5-flash-lite` ตอบ 503 ว่า "This model is currently
    experiencing high demand" ทุกครั้ง 15 ครั้งจาก 15 ครั้ง ขณะที่ `gemini-3.5-flash`
    และ `gemini-3.6-flash` ในรายการสำรองตอบ 200 ใน 1.3–1.5 วินาที แต่โค้ดเดิมย้ายโมเดล
    เมื่อเจอ 429 เท่านั้น — 5xx ลองซ้ำตัวเดิมสามครั้งแล้วโยน LLMConnectionError ซึ่งลูป
    เลือกโมเดลไม่ได้ดักจับ จึงตกไปใช้โมเดลในเครื่องบน CPU ที่ใช้เวลา 27 วินาทีต่อครั้ง
    ทั้งที่ยังมีโมเดลบนคลาวด์ว่างอยู่
    """

    def __init__(self, model: str, cooldown_s: float):
        # ตั้งชนิดให้ตัวนับเอง ไม่ให้ไปเดาจากระยะพัก เพราะ 503 กับเพดานต่อนาทีพักใกล้
        # เคียงกัน (60 กับ 45 วินาที) แต่เป็นคนละปัญหาและแก้คนละทาง
        super().__init__(model, cooldown_s, kind="overload")


_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


@dataclass
class GeminiConnector:
    # repr=False สำคัญ: @dataclass สร้าง __repr__ ที่พิมพ์ทุกฟิลด์ ถ้าไม่กันไว้ คีย์จะหลุด
    # ออกไปทุกที่ที่มีการ repr ตัวเชื่อมต่อ — traceback, logger.exception หรือการ debug
    # ด้วยมือ · 13 ต.ค. 2569 คีย์หลุดออกมาจริงตอนสั่งพิมพ์โครงสร้างของ _SplitConnector
    # เพื่อดูชื่อโมเดล · ฟิลด์ _client ถูกกันไว้แล้วแต่ api_key ไม่ได้กัน
    api_key: str = field(repr=False)
    chat_model: str = "gemini-3.5-flash-lite"
    timeout_s: int = 120
    max_retries: int = 2

    # ตัวรับแจ้งเหตุการณ์สำหรับนับสถิติ — ไม่ตั้งก็ทำงานได้ตามปกติ
    #
    # เป็น callback แทนการเรียกตัวนับตรง ๆ เพราะแพ็กเกจ llm/ ต้องไม่รู้จัก backend
    # ของเรา (ไม่งั้นมันใช้นอกโปรเจกต์นี้ไม่ได้ และผูกกับฐานข้อมูลโดยไม่จำเป็น)
    # ผู้ประกอบเป็นคนส่ง services/llm_usage.record เข้ามา — ดู services/llm_client.py
    on_event: Callable[[str], None] | None = field(default=None, repr=False)

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

    # โมเดลที่จะใช้ต่อเมื่อตัวหลักชนโควตารายวัน
    #
    # โควตาชั้นใช้งานฟรีเป็นแบบ "ต่อโมเดล ต่อโปรเจกต์" ตามที่ Google กำหนดเอง
    # (quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier) การย้ายไปโมเดลอื่น
    # จึงได้โควตาก้อนใหม่ ไม่ใช่การหลบเลี่ยงเพดานของโปรเจกต์
    #
    # ที่ต้องมีเพราะเดิมพอชน 429 ระบบยอมแพ้ทั้งวัน คำถามเรื่องหลักสูตรทุกข้อถูกปฏิเสธ
    # จนกว่าโควตาจะรีเซ็ต — เกิดขึ้นสองวันติดระหว่างพัฒนา และจะเกิดกับผู้ใช้จริงด้วย
    #
    # เรียงจากใกล้เคียงตัวหลักที่สุดไปหาไกลสุด เพื่อให้คำตอบเปลี่ยนสำนวนน้อยที่สุด
    # เมื่อสลับ ตั้งทับได้ด้วย GEMINI_FALLBACK_MODELS (คั่นด้วยจุลภาค)
    fallback_models: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            m.strip()
            for m in os.getenv(
                "GEMINI_FALLBACK_MODELS",
                "gemini-3.1-flash-lite,gemini-3.5-flash,gemini-3.6-flash",
            ).split(",")
            if m.strip()
        )
    )

    # ระยะเวลาที่ถือว่าโมเดลหนึ่ง "โควตาหมด" หลังเจอ 429
    #
    # โควตาจริงรีเซ็ตวันละครั้งตามเวลาของ Google ซึ่งเราไม่รู้แน่ชัดว่าตรงกับกี่โมงของ
    # เครื่องนี้ จึงใช้ระยะเวลาโดยประมาณแทนการคำนวณเวลารีเซ็ต ถ้าเดาสั้นไปก็แค่ลอง
    # โมเดลที่ยังไม่ว่างอีกครั้งแล้วตกไปตัวถัดไปทันที ไม่มีอะไรเสียหาย
    exhausted_for_s: float = 4 * 3600.0

    # รอนานที่สุดเท่าไหร่เมื่อทุกโมเดลติดเพดานต่อนาทีพร้อมกัน
    #
    # ตั้งให้ยาวกว่าเวลาที่ Google มักขอให้รอ (ราว 30 วินาที) เล็กน้อย แต่สั้นพอที่ผู้ใช้
    # จะยังรอไหว ถ้านานกว่านี้แปลว่าไม่ใช่เพดานต่อนาทีแล้ว ปล่อยให้ตกไปโมเดลในเครื่อง
    max_cooldown_wait_s: float = 75.0

    # โมเดลที่ชนโควตาไปแล้ว -> เวลาที่จะกลับมาลองใหม่ได้
    _exhausted: dict[str, float] = field(default_factory=dict, repr=False)

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
    # Chat / generation — พร้อมการสลับโมเดลเมื่อชนโควตา
    # ------------------------------------------------------------------
    def _models_to_try(self) -> list[str]:
        """
        โมเดลที่ยังไม่ชนโควตา เรียงจากตัวหลักไปตัวสำรอง

        ถ้าชนหมดทุกตัว ให้ล้างบันทึกแล้วเริ่มจากตัวหลักใหม่ ดีกว่าปฏิเสธทันทีโดยไม่ลอง
        เพราะบันทึกนี้เป็นการเดาเวลารีเซ็ต ไม่ใช่ข้อมูลจริงจากผู้ให้บริการ
        """
        now = time.time()
        order = [self.chat_model, *(m for m in self.fallback_models if m != self.chat_model)]
        usable = [m for m in order if self._exhausted.get(m, 0.0) <= now]
        if usable:
            return usable

        # ทุกตัวติดคูลดาวน์อยู่ ถ้าตัวที่ใกล้ครบที่สุดเหลืออีกไม่นาน ให้รอแล้วไปต่อ
        #
        # เพดานต่อนาทีของ Google เป็นแบบต่อโมเดล การยิงชุดคำถามรัวๆ จึงไล่ชนทีละตัว
        # จนครบทุกตัวได้ภายในไม่กี่วินาที การล้มทั้งคำขอตรงนั้นแล้วตกไปใช้โมเดลในเครื่อง
        # (ซึ่งใช้เวลาเป็นนาทีบนเครื่องที่ไม่มีการ์ดจอ) แพงกว่าการรออีกครึ่งนาทีมาก
        soonest = min(self._exhausted.values())
        wait = soonest - now
        # เพดานเวลารวมของคำขอมีสิทธิ์ตัดการรอนี้ — รอจนครบ cooldown แล้วผู้ใช้ได้คำตอบ
        # ช้ากว่าเพดานที่ตั้งไว้ ไม่ต่างจากไม่มีเพดาน
        left = budget_left_s()
        if left is not None and wait + 1 >= left:
            check_budget("รอให้โมเดลพ้นช่วงพัก")
            raise LLMConnectionError(
                "ผู้ให้บริการโมเดลขัดข้องและเวลาที่เหลือของคำขอนี้ไม่พอรอให้พ้นช่วงพัก"
            )
        if wait <= self.max_cooldown_wait_s:
            logger.warning("ทุกโมเดลติดเพดานชั่วคราว รออีก %.0f วินาที", max(wait, 0))
            time.sleep(max(wait, 0) + 1)
            # ตัวที่ครบกำหนดแล้วจะกลับเข้า usable รอบนี้ จึงไม่วนซ้ำอีกชั้น
            return self._models_to_try()

        # เหลือแต่คูลดาวน์ยาว (โควตารายวัน) การรอไม่ใช่คำตอบ ลองใหม่ทั้งหมดดีกว่า
        # ปฏิเสธทันที เพราะบันทึกนี้เป็นการเดาเวลารีเซ็ต ไม่ใช่ข้อมูลจริงจากผู้ให้บริการ
        self._exhausted.clear()
        return order

    def _note(self, event: str) -> None:
        """
        บอกตัวนับว่าเกิดอะไรขึ้น — ห้ามทำให้การตอบคำถามล้มเด็ดขาด

        ตัวนับเป็นของเสริมที่มีไว้ตัดสินใจเรื่องผู้ให้บริการ ไม่ใช่ส่วนหนึ่งของการตอบ
        ถ้ามันพัง สิ่งที่ควรเสียคือสถิติ ไม่ใช่คำตอบของผู้ใช้ที่กำลังรออยู่
        """
        if self.on_event is None:
            return
        try:
            self.on_event(event)
        except Exception:  # noqa: BLE001
            logger.debug("ตัวนับภายนอกทำงานไม่ได้", exc_info=True)

    def _mark_exhausted(self, model: str, cooldown_s: float | None = None) -> None:
        cooldown = self.exhausted_for_s if cooldown_s is None else cooldown_s
        self._exhausted[model] = time.time() + cooldown
        logger.warning("พักโมเดล %s ไว้ %.0f วินาที จะไปใช้ตัวถัดไปก่อน", model, cooldown)

    def chat(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.2,
        json_mode: bool = False,
        num_predict: int | None = None,
    ) -> str:
        payload = self._to_payload(messages, temperature, json_mode, num_predict)
        last_exc: Exception | None = None
        for model in self._models_to_try():
            check_budget(f"เรียกโมเดล {model}")
            try:
                text = self._chat_one_model(model, payload)
                if model != self.chat_model:
                    logger.info("ตอบด้วยโมเดลสำรอง %s", model)
                self._note("gemini_ok" if model == self.chat_model else f"gemini_backup:{model}")
                # ตัวที่ตอบสำเร็จจริง ซึ่งไม่ใช่ chat_model ที่ตั้งไว้เสมอ — ผู้เรียกที่จะ
                # บอกผู้ใช้ว่า "รุ่นไหนเขียนคำตอบนี้" ต้องใช้ค่านี้ ไม่ใช่ค่าที่ตั้งไว้
                note_answered_model(model)
                return text
            except _QuotaExhausted as e:
                self._note(f"gemini_{e.kind}:{model}")
                self._mark_exhausted(model, e.cooldown_s)
                last_exc = e.__cause__ or e
        self._note("gemini_all_failed")
        raise LLMConnectionError(
            f"โมเดล Gemini ทุกตัวใช้ไม่ได้ (โควตาหมดหรือรับไม่ไหว) ล่าสุด: {last_exc}",
            user_text="ตอนนี้ผู้ให้บริการโมเดลใช้ไม่ได้ทุกตัว (โควตาหมดหรือรับไม่ไหว) "
                      "รบกวนลองใหม่อีกครั้งในอีกสักครู่ครับ",
        ) from last_exc

    def _chat_one_model(self, model: str, payload: dict[str, Any]) -> str:
        path = f"/models/{model}:generateContent"

        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 2):
            try:
                # ตรวจทุกครั้งที่ลองใหม่ ไม่ใช่แค่ก่อนเลือกโมเดล · และจำกัดเวลาของคำขอ
                # HTTP ครั้งนี้ตามเวลาที่เหลือ ไม่ใช่ timeout เดิมของตัวเชื่อมต่อ
                # อ่าน body แบบสตรีมพร้อมตรวจเพดานทุกก้อน — ดูเหตุผลใน post_json_bounded
                data = post_json_bounded(
                    self._client, path, payload, timeout_s=self.timeout_s,
                    doing=f"เรียก {model} ครั้งที่ {attempt}",
                )
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
                if e.response.status_code == 429:
                    # ชนเพดานแล้วย้ายโมเดลเสมอ ต่างกันแค่ "พักตัวนี้ไว้นานแค่ไหน"
                    #
                    # เพดานต่อนาทีเป็นแบบต่อโมเดล ตัวถัดไปจึงยังยิงได้ทันที การนั่งรอ
                    # กับตัวเดิมสองสี่แปดวินาทีแล้วยอมแพ้ (ของเดิม) ช้ากว่าและมักไม่พอ
                    # เพราะ Google บอกให้รอราวสามสิบวินาที ผลคือตกไปใช้โมเดลในเครื่อง
                    # ทั้งที่ยังมีโมเดลบนคลาวด์ว่างอยู่อีกสามตัว
                    raise _QuotaExhausted(model, _cooldown_for(e.response)) from e
                # 4xx อื่นคือเราส่งผิดเอง ลองใหม่ก็ได้ผลเท่าเดิม
                if e.response.status_code < 500:
                    raise LLMConnectionError(self._explain(e)) from e
                # 5xx = ฝั่งผู้ให้บริการรับไม่ไหว ย้ายโมเดลทันทีเหมือน 429 ไม่ลองซ้ำตัวเดิม
                #
                # วัดเมื่อ 13 ต.ค. 2569: ลองซ้ำตัวเดิมสามครั้งก่อนย้าย ทำให้กรณีที่ทุกโมเดล
                # ล่มใช้เวลาเป็นสี่เท่าของจำนวนโมเดล โดยไม่เคยเห็นว่าการลองซ้ำตัวเดิมทันที
                # ช่วยอะไรเลย ส่วนกรณีที่พบจริง (ตัวหลักล่ม ตัวสำรองว่าง) การย้ายทันที
                # ทำให้ได้คำตอบใน ~1.5 วินาทีแทนที่จะเสียเวลาลองตัวที่รู้แล้วว่าล่ม
                logger.warning("gemini HTTP %d ที่โมเดล %s", e.response.status_code, model)
                raise _Overloaded(model, _OVERLOAD_COOLDOWN_S) from e
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
        last_exc: Exception | None = None
        for model in self._models_to_try():
            check_budget(f"เรียกโมเดล {model} แบบสตรีม")
            for attempt in range(1, self.max_retries + 2):
                started = False
                try:
                    for chunk in self._stream_once(model, messages, temperature, num_predict):
                        started = True
                        yield chunk
                    if model != self.chat_model:
                        logger.info("สตรีมด้วยโมเดลสำรอง %s", model)
                    self._note("gemini_ok" if model == self.chat_model else f"gemini_backup:{model}")
                    return
                except _QuotaExhausted as e:
                    # ชนโควตากลางสตรีมหลังส่งข้อความไปแล้ว สลับโมเดลไม่ได้ เพราะผู้ใช้
                    # จะเห็นคำตอบต่อกันจากคนละโมเดล ซึ่งอ่านไม่รู้เรื่องยิ่งกว่าข้อผิดพลาด
                    if started:
                        self._note("gemini_quota_midstream")
                        raise LLMConnectionError(f"โควตาหมดกลางคำตอบ: {e}") from e
                    self._note(f"gemini_{e.kind}:{model}")
                    self._mark_exhausted(model, e.cooldown_s)
                    last_exc = e.__cause__ or e
                    break  # ไปโมเดลถัดไป ไม่ลองซ้ำตัวเดิม
                except LLMBudgetExceeded:
                    # เกินเพดานเวลารวม — ห้ามลองใหม่ ไม่ว่าจะเหลือ attempt อยู่หรือไม่
                    # เพราะการลองใหม่คือการใช้เวลาเพิ่มในสิ่งที่หมดเวลาไปแล้ว
                    raise
                except LLMConnectionError as e:
                    if started or attempt > self.max_retries:
                        raise
                    last_exc = e
                    logger.warning("gemini stream ลองใหม่ครั้งที่ %d", attempt + 1)
                    left = budget_left_s()
                    if left is not None and left <= 2 * attempt:
                        check_budget("หน่วงเวลาก่อนลองสตรีมใหม่")
                    time.sleep(2 * attempt)
        self._note("gemini_all_failed")
        raise LLMConnectionError(
            f"โมเดล Gemini ทุกตัวใช้ไม่ได้ (โควตาหมดหรือรับไม่ไหว) ล่าสุด: {last_exc}",
            user_text="ตอนนี้ผู้ให้บริการโมเดลใช้ไม่ได้ทุกตัว (โควตาหมดหรือรับไม่ไหว) "
                      "รบกวนลองใหม่อีกครั้งในอีกสักครู่ครับ",
        ) from last_exc

    def _stream_once(
        self,
        model: str,
        messages: list[ChatMessage],
        temperature: float,
        num_predict: int | None,
    ) -> Iterator[str]:
        payload = self._to_payload(messages, temperature, json_mode=False, num_predict=num_predict)
        path = f"/models/{model}:streamGenerateContent"
        try:
            with self._client.stream(
                "POST", path, json=payload, params={"alt": "sse"},
                timeout=http_timeout(self.timeout_s, f"เริ่มสตรีมจาก {model}"),
            ) as resp:
                if resp.is_error:
                    # คำตอบแบบ stream ยังไม่ได้อ่านเนื้อความ ถ้าไม่อ่านก่อน _is_daily_limit จะอ่านไม่ได้
                    # แล้วเดาว่าเป็นโควตารายวัน เจอจริงบนเซิร์ฟเวอร์: 429 ต่อนาทีระหว่างเขียนคำตอบ
                    # ทำให้โมเดลหลักถูกพักไปสี่ชั่วโมง ทั้งที่ 429 แบบไม่ stream ทุกครั้งเป็นเพดานต่อนาที
                    resp.read()
                resp.raise_for_status()
                for line in resp.iter_lines():
                    # ต้องตรวจทุกบรรทัด ไม่ใช่พึ่ง read timeout — สตรีมที่ทยอยส่งข้อมูล
                    # เรื่อย ๆ จะไม่เคยชน read timeout แต่ยืดเวลารวมได้ไม่จำกัด
                    check_budget(f"อ่านสตรีมจาก {model}")
                    # รูปแบบ SSE: สนใจเฉพาะบรรทัด data: ส่วนบรรทัดว่างคือตัวคั่นเหตุการณ์
                    if not line.startswith("data: "):
                        continue
                    if text := self._text_of(json.loads(line[6:])):
                        yield text
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise _QuotaExhausted(model, _cooldown_for(e.response)) from e
            # 503 ฝั่งผู้ให้บริการรับไม่ไหว — ย้ายโมเดลเหมือน 429 ดูเหตุผลใน _Overloaded
            if e.response.status_code >= 500:
                raise _Overloaded(model, _OVERLOAD_COOLDOWN_S) from e
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
