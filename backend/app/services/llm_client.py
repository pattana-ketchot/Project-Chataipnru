"""
เลือกและสร้าง connector ที่ backend ใช้ (item 4 ของ requirement)

ระบบนี้ใช้โมเดลสองตัวคนละหน้าที่ และเลือกผู้ให้บริการแยกกันได้:

    embedding (แปลงข้อความเป็นเวกเตอร์)   ใช้ bge-m3 ในเครื่องเสมอ
    การเขียนคำตอบ                        เลือกได้ระหว่างโมเดลในเครื่องกับ Gemini

ทำไม embedding ถึงเปลี่ยนไม่ได้: เวกเตอร์ของเอกสารทั้ง 7,301 ชิ้นในฐานข้อมูลถูกสร้าง
ด้วย bge-m3 ขนาด 1024 มิติ และคอลัมน์ในฐานข้อมูลก็ประกาศขนาดนี้ไว้ตายตัว การเปลี่ยน
โมเดล embedding แปลว่าต้องคำนวณใหม่ทั้งคลังและแก้โครงสร้างตาราง ซึ่งไม่เกี่ยวกับ
ปัญหาความเร็วเลย เพราะการค้นเอกสารใช้เวลาไม่ถึง 3 วินาที

ในระบบจริงแนะนำ package `llm/` แยกเป็น pip package ภายใน (monorepo) แล้ว
`pip install -e ../llm` แทนการ append sys.path — ที่นี่ใช้ sys.path เพื่อความง่าย
ของ scaffold เท่านั้น
"""
import logging
import sys
from pathlib import Path

# monorepo: <root>/backend/app/services/llm_client.py -> <root>/llm
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from llm.connector import (LLMConnectionError, OllamaConnector,  # noqa: E402
                           apply_budget, reserve_budget)
from llm.gemini import GeminiConnector  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.services import llm_usage  # noqa: E402

settings = get_settings()
logger = logging.getLogger("course_advisor")

_connector = None

# ข้อความเมื่อไม่ยอมใช้ตัวสำรอง — ผู้ใช้ต้องเข้าใจว่าให้รอแล้วถามใหม่ ไม่ใช่ระบบพัง
FALLBACK_DECLINED = (
    "ตอนนี้ระบบหลักตอบไม่ได้ชั่วคราว คำถามนี้ต้องตอบโดยอ้างอิงเอกสารหลักสูตร "
    "ระบบจึงขอไม่ตอบด้วยโมเดลสำรอง เพราะคำตอบที่ตรวจสอบกับเอกสารไม่ได้ "
    "เสียหายกว่าการไม่ตอบ รบกวนลองถามใหม่อีกครั้งในอีกสักครู่ครับ"
)


def no_fallback_kwargs(connector, allow: bool) -> dict:
    """
    kwargs สำหรับสั่งห้ามใช้ตัวสำรอง คืน dict ว่างเมื่อสั่งไม่ได้หรือไม่ต้องสั่ง

    มีไว้ให้ services/chat.py ไม่ต้องรู้ว่า connector ตัวไหนมีตัวสำรองบ้าง —
    เมื่อตั้งค่าให้ใช้โมเดลในเครื่องล้วน ตัวที่ตอบก็เป็นตัวหลักอยู่แล้ว ไม่มีตัวสำรอง
    ให้ห้าม และ OllamaConnector ก็ไม่รู้จักพารามิเตอร์นี้
    """
    if allow or not isinstance(connector, _SplitConnector):
        return {}
    return {"allow_fallback": False}


class _SplitConnector:
    """
    ใช้ผู้ให้บริการคนละเจ้าสำหรับ embedding กับการเขียนคำตอบ พร้อมตัวสำรอง

    มีเพื่อให้โค้ดที่เรียกใช้ไม่ต้องรู้เรื่องนี้เลย ทุกที่ยังเรียก connector.embed()
    และ connector.chat() บนวัตถุเดียวเหมือนเดิม การสลับผู้ให้บริการจึงไม่กระทบ
    services/chat.py หรือ services/rag.py แม้แต่บรรทัดเดียว

    ตัวสำรองแก้ปัญหาที่เจอจริง: ชั้นใช้งานฟรีของ Gemini มีเพดานคำขอต่อนาที พอชน
    แล้วผู้ใช้เห็นข้อความแดงแทนคำตอบ ซึ่งแย่กว่าการรอนาน โมเดลในเครื่องไม่มีเพดาน
    เลยเพราะรันอยู่บนเครื่องเราเอง จึงเอามารับช่วงต่อได้ ผลคือ "เร็วเป็นปกติ ช้าบ้าง
    เป็นบางครั้ง แต่ไม่พังให้เห็น"
    """

    def __init__(self, embedder: OllamaConnector, chatter: GeminiConnector) -> None:
        self._embedder = embedder
        self._chatter = chatter
        # ตัวเดียวกับที่ใช้ embed — เป็นโมเดลในเครื่องที่พร้อมใช้อยู่แล้ว
        self._fallback = embedder

    # --- ฝั่ง embedding: โมเดลในเครื่อง ---
    def embed(self, text):
        return self._embedder.embed(text)

    def embed_batch(self, texts):
        return self._embedder.embed_batch(texts)

    # --- ฝั่งเขียนคำตอบ: ใช้เจ้าหลักก่อน ล้มแล้วค่อยตกมาที่โมเดลในเครื่อง ---
    def _fallback_kwargs(self, kwargs: dict) -> dict:
        """
        ปรับเพดานความยาวให้เข้ากับโมเดลในเครื่องก่อนส่งต่อ

        ผู้เรียกส่ง num_predict มาเป็นเพดานของ Gemini (2048) ซึ่งเผื่อไว้สำหรับโทเคน
        ที่โมเดลใช้คิดในใจ โมเดลในเครื่องไม่มีขั้นตอนนั้นและเขียนช้ากว่ามาก ถ้าปล่อย
        ค่าเดิมไปคำตอบสำรองอาจยาวจนใช้เวลาหลายนาที
        """
        out = dict(kwargs)
        if out.get("num_predict") is not None:
            out["num_predict"] = min(out["num_predict"], self._fallback.answer_token_cap)
        return out

    def chat(self, *args, allow_fallback: bool = True, **kwargs):
        # กันเวลาไว้ให้ตัวสำรองก่อนปล่อยเจ้าหลักออกวิ่ง ไม่งั้นเจ้าหลักใช้เพดานเวลาหมด
        # เองแล้วตัวสำรองถูกปฏิเสธก่อนยิงคำขอแรก (ดู connector.reserve_budget)
        # ขั้นที่ห้ามใช้ตัวสำรองไม่ต้องกัน เพราะไม่มีใครมารับช่วงต่อ
        full = reserve_budget() if allow_fallback else None
        try:
            return self._chatter.chat(*args, **kwargs)
        except LLMConnectionError as e:
            if not allow_fallback:
                llm_usage.record("fallback_declined")
                raise LLMConnectionError(FALLBACK_DECLINED) from e
            apply_budget(full)
            logger.warning("เจ้าหลักตอบไม่ได้ (%s) — ใช้โมเดลในเครื่องแทน", e)
            return self._call_fallback(*args, **self._fallback_kwargs(kwargs))
        finally:
            # คืนเวลาที่กันไว้ให้ขั้นถัดไปของคำขอเดียวกัน ทั้งตอนเจ้าหลักตอบได้และตอนล้ม
            if allow_fallback:
                apply_budget(full)

    def _call_fallback(self, *args, **kwargs):
        """
        เรียกโมเดลในเครื่องพร้อมนับผลจริง — "เรียกตัวสำรอง" ไม่เท่ากับ "ผู้ใช้ได้คำตอบ"

        โมเดลในเครื่องล้มได้เหมือนกัน โดยเฉพาะเมื่อเพดานเวลาของคำขอหมดก่อนมันเขียนจบ
        ซึ่งเกิดได้จริงเพราะมันช้ากว่าเจ้าหลักมาก ถ้านับแค่ "ตกมาที่ตัวสำรอง" ครั้งเดียว
        ความล้มเหลวจะถูกนับรวมเป็นความสำเร็จ แล้วตัวเลขจะบอกว่าระบบรับมือได้ดีกว่าจริง
        """
        llm_usage.record("fallback_local_attempt")
        try:
            out = self._fallback.chat(*args, **kwargs)
        except Exception:
            llm_usage.record("fallback_local_failed")
            raise
        llm_usage.record("fallback_local_ok")
        return out

    def chat_stream(self, *args, allow_fallback: bool = True, **kwargs):
        """
        สตรีมจากเจ้าหลัก ถ้าล้ม "ก่อน" ตัวอักษรแรกออกไปค่อยเปลี่ยนไปใช้ตัวสำรอง

        ต้องเช็กว่ายังไม่ได้ส่งอะไรออกไป เพราะถ้าสลับกลางคันผู้ใช้จะเห็นคำตอบสองชุด
        ต่อกันจากคนละโมเดล ซึ่งอ่านไม่รู้เรื่องยิ่งกว่าเห็นข้อความผิดพลาด
        """
        started = False
        # เหตุผลเดียวกับใน chat() — กันเวลาไว้ให้ตัวสำรองก่อน แล้วคืนให้ขั้นถัดไปเสมอ
        full = reserve_budget() if allow_fallback else None
        try:
            for chunk in self._chatter.chat_stream(*args, **kwargs):
                started = True
                yield chunk
            return
        except LLMConnectionError as e:
            if started:
                llm_usage.record("stream_failed_midway")
                raise
            if not allow_fallback:
                llm_usage.record("fallback_declined")
                raise LLMConnectionError(FALLBACK_DECLINED) from e
            logger.warning("เจ้าหลักสตรีมไม่ได้ (%s) — ใช้โมเดลในเครื่องแทน", e)
        finally:
            if allow_fallback:
                apply_budget(full)

        # สตรีม "สำเร็จ" คือเดินจนจบโดยไม่โยนข้อผิดพลาด ไม่ใช่แค่เริ่มส่งตัวอักษรแรกได้
        #
        # ผู้ใช้ปิดหน้าเว็บกลางคันทำให้เกิด GeneratorExit ซึ่งไม่ใช่ทั้งความสำเร็จและ
        # ความล้มเหลวของโมเดล จึงไม่นับทั้งสองทาง — `except Exception` ไม่จับมันอยู่แล้ว
        # เพราะ GeneratorExit สืบทอดจาก BaseException ไม่ใช่ Exception
        llm_usage.record("fallback_local_attempt")
        try:
            yield from self._fallback.chat_stream(*args, **self._fallback_kwargs(kwargs))
        except Exception:
            llm_usage.record("fallback_local_failed")
            raise
        llm_usage.record("fallback_local_ok")

    @property
    def chat_model(self) -> str:
        return self._chatter.chat_model

    @property
    def answer_token_cap(self) -> int:
        return self._chatter.answer_token_cap


def _build_ollama() -> OllamaConnector:
    return OllamaConnector(
        base_url=settings.ollama_base_url,
        chat_model=settings.llm_model,
        embed_model=settings.embed_model,
        timeout_s=settings.llm_request_timeout_s,
    )


def get_llm_connector():
    """Singleton connector — reuse the underlying httpx client/connection pool."""
    global _connector
    if _connector is None:
        ollama = _build_ollama()
        if settings.llm_provider == "gemini":
            _connector = _SplitConnector(
                embedder=ollama,
                chatter=GeminiConnector(
                    api_key=settings.gemini_api_key,
                    chat_model=settings.gemini_model,
                    timeout_s=settings.llm_request_timeout_s,
                    # แพ็กเกจ llm/ ไม่รู้จักฐานข้อมูลของเรา จึงส่งตัวนับเข้าไปจากที่นี่
                    on_event=llm_usage.record,
                ),
            )
        else:
            _connector = ollama
    return _connector
