"""
เลือกและสร้าง connector ที่ backend ใช้ (item 4 ของ requirement)

ระบบนี้ใช้โมเดลสองตัวคนละหน้าที่ และเลือกผู้ให้บริการแยกกันได้:

    embedding (แปลงข้อความเป็นเวกเตอร์)   ใช้ bge-m3 ในเครื่องเสมอ
    การเขียนคำตอบ                        เลือกได้ระหว่างโมเดลในเครื่องกับ Gemini

ตัวเลือกของฝั่งเขียนคำตอบมาจากค่าที่ผู้ดูแลบันทึกไว้ในหน้าหลังบ้าน โดยถอยไปใช้ค่า
จาก env เมื่อยังไม่ได้เลือกหรือค่าที่เลือกใช้ไม่ได้ — การตัดสินทั้งหมดอยู่ที่
services/ai_settings.py ไฟล์นี้รับหน้าที่แค่ "สร้างของตามตัวเลือกที่ได้มา"

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
import threading
import time
from contextvars import ContextVar
from pathlib import Path

# monorepo: <root>/backend/app/services/llm_client.py -> <root>/llm
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from llm.connector import (_DEFAULT_BUDGET_S, ChatMessage,  # noqa: E402
                           LLMConnectionError, OllamaConnector,
                           answered_model, apply_budget, reserve_budget,
                           reset_answered_model, reset_budget, start_budget)
from llm.gemini import GeminiConnector  # noqa: E402
from llm.prompts import (GROUNDING_CHECK_SYSTEM_PROMPT,  # noqa: E402
                         build_grounding_check_prompt)
from app.core.config import get_settings  # noqa: E402
from app.services import ai_settings, llm_usage  # noqa: E402

settings = get_settings()
logger = logging.getLogger("course_advisor")

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
        out = self._embedder.embed(text)
        self._note_embedder()
        return out

    def embed_batch(self, texts):
        out = self._embedder.embed_batch(texts)
        self._note_embedder()
        return out

    def _note_embedder(self) -> None:
        """บันทึกรุ่นที่แปลงเวกเตอร์ให้คำขอนี้ — เรียกหลังสำเร็จเท่านั้น"""
        record_embed_model(EMBED_PROVIDER, self.embed_model)

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
            out = self._chatter.chat(*args, **kwargs)
            # ตัวที่ตอบสำเร็จจริง ไม่ใช่ chat_model ที่ตั้งไว้ — Gemini วนลองรุ่นสำรองของ
            # ตัวเองได้เมื่อรุ่นหลักชนโควตา (ดู gemini._models_to_try)
            record_chat_model(self.provider_name,
                              answered_model() or self._chatter.chat_model)
            return out
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
        # ข้อความที่ผู้ใช้จะเห็นมาจากตัวสำรอง ไม่ใช่เจ้าหลักที่ถูกเลือกไว้
        record_chat_model("ollama",
                          answered_model() or getattr(self._fallback, "chat_model", ""))
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
    def provider_name(self) -> str:
        return "gemini"

    @property
    def chat_model(self) -> str:
        return self._chatter.chat_model

    @property
    def embed_model(self) -> str:
        """รุ่นที่แปลงข้อความเป็นเวกเตอร์จริง — คนละตัวกับรุ่นที่เขียนคำตอบเสมอ"""
        return getattr(self._embedder, "embed_model", "")

    @property
    def answer_token_cap(self) -> int:
        return self._chatter.answer_token_cap


class _LocalPrimary:
    """
    โมเดลในเครื่องเป็นตัวหลัก — ห่อไว้เพื่อนับว่า "เรียกจริง" และ "ได้คำตอบจริง"

    ทำไมต้องห่อ: ตัวนับเดิมรู้จักแต่เหตุการณ์ของ Gemini (`gemini_ok`) และของโมเดล
    ในเครื่องในฐานะ "ตัวสำรอง" (`fallback_local_*`) ไม่มีเหตุการณ์ใดบอกว่าโมเดล
    ในเครื่องถูกเลือกเป็นตัวหลัก เมื่อเปิดสวิตช์ให้ผู้ดูแลเลือกได้ การพิสูจน์ว่า
    "เลือก Ollama แล้วเรียก Ollama จริง" จึงไม่มีหลักฐานจากบัญชีของระบบเอง

    ตัวสำรองของเส้นทางนี้: ไม่มี — ดูเหตุผลที่ _build()

    **ตัวเลขนี้นับ "การเรียกโมเดล" ไม่ใช่ "คำตอบที่ผู้ใช้ได้"** หนึ่งคำขอเรียกโมเดล
    ได้หลายครั้ง (เขียนคำถามใหม่ ด่านตรวจขอบเขต ด่านตรวจหลักฐาน แล้วจึงเขียนคำตอบ)
    จะดูว่าคำตอบหนึ่งข้อมาจากโมเดลตัวไหน ให้ดูช่อง answer_model ของคำตอบนั้น
    """

    def __init__(self, local: OllamaConnector) -> None:
        self._local = local

    def embed(self, text):
        out = self._local.embed(text)
        record_embed_model(EMBED_PROVIDER, self.embed_model)
        return out

    def embed_batch(self, texts):
        out = self._local.embed_batch(texts)
        record_embed_model(EMBED_PROVIDER, self.embed_model)
        return out

    @property
    def embed_model(self) -> str:
        return getattr(self._local, "embed_model", "")

    def chat(self, *args, **kwargs):
        llm_usage.record("local_primary_attempt")
        try:
            out = self._local.chat(*args, **kwargs)
        except Exception:
            llm_usage.record("local_primary_failed")
            raise
        llm_usage.record("local_primary_ok")
        record_chat_model("ollama",
                          answered_model() or getattr(self._local, "chat_model", ""))
        return out

    def chat_stream(self, *args, **kwargs):
        # นับ "สำเร็จ" เมื่อเดินจนจบเท่านั้น เหมือนเส้นทางตัวสำรองของ _SplitConnector
        # ผู้ใช้ปิดหน้าเว็บกลางคันเกิด GeneratorExit ซึ่งสืบทอดจาก BaseException
        # จึงไม่ถูกนับเป็นความล้มเหลวของโมเดล
        llm_usage.record("local_primary_attempt")
        try:
            yield from self._local.chat_stream(*args, **kwargs)
        except Exception:
            llm_usage.record("local_primary_failed")
            raise
        llm_usage.record("local_primary_ok")

    def warm_chat(self) -> None:
        """
        อุ่นโมเดลให้ค้างใน VRAM — ตั้งใจไม่นับในตัวนับการใช้งาน

        งานเบื้องหลังยิงคำขอนี้ทุก 20 นาทีไม่ว่าจะมีผู้ใช้หรือไม่ ถ้านับรวมด้วย
        ตัวเลข local_primary_* จะบวกวันละ 72 ครั้งจากคำขอที่ไม่มีใครถาม แล้ว
        สถิติจะตอบคำถาม "ผู้ใช้ได้คำตอบจากโมเดลไหน" ผิดไปทั้งหมด

        มีเฉพาะบนเส้นทางนี้โดยเจตนา — ฝั่ง Gemini ไม่มีโมเดลค้างในหน่วยความจำ
        ให้อุ่น การยิงคำขอเปล่าไปที่นั้นมีแต่กินโควตา (ดู main.py: _keep_models_warm)
        """
        self._local.chat([ChatMessage(role="user", content="hi")], 0.0, False)

    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def chat_model(self) -> str:
        return self._local.chat_model

    @property
    def answer_token_cap(self) -> int:
        return self._local.answer_token_cap

    def close(self) -> None:
        self._local.close()


def _build_ollama(chat_model: str | None = None) -> OllamaConnector:
    """
    โมเดลในเครื่อง — `embed_model` มาจาก env เสมอ ไม่เคยมาจากค่าที่ผู้ดูแลตั้ง

    สวิตช์ของผู้ดูแลเปลี่ยนได้แค่โมเดลที่เขียนคำตอบ (`chat_model`) เพราะเวกเตอร์
    ของเอกสารทั้งคลังถูกสร้างด้วย bge-m3 ขนาด 1024 มิติ และคอลัมน์ในฐานข้อมูล
    ประกาศขนาดนั้นไว้ตายตัว การเปลี่ยน embed_model จึงไม่ใช่การตั้งค่า แต่คือ
    การสร้างเวกเตอร์ใหม่ทั้งคลังพร้อมแก้โครงสร้างตาราง
    """
    return OllamaConnector(
        base_url=settings.ollama_base_url,
        chat_model=chat_model or settings.llm_model,
        embed_model=settings.embed_model,
        timeout_s=settings.llm_request_timeout_s,
    )


def _build(choice: ai_settings.Choice):
    """
    สร้าง connector ตามตัวเลือกหนึ่งชุด — ตัวสำรองของแต่ละเส้นทางต่างกันโดยเจตนา

    เลือก Gemini แล้วล้ม  ->  ตกมาที่โมเดลในเครื่อง (พฤติกรรมเดิม ไม่เปลี่ยน)
                              เฉพาะเมื่อยังไม่ได้ส่งตัวอักษรแรกออกไป และเฉพาะคำถาม
                              ที่ยอมให้ตอบด้วยตัวสำรองได้ (ดู no_fallback_kwargs)

    เลือก Ollama แล้วล้ม  ->  แจ้งข้อผิดพลาด ไม่ไปเรียก Gemini แทน
                              เพราะการเลือกโมเดลในเครื่องคือการเลือกไม่ส่งคำถามของ
                              ผู้ใช้ออกนอกเครื่อง ถ้าแอบตกไปหาเจ้าบนคลาวด์ตอนมีปัญหา
                              ระบบจะละเมิดเงื่อนไขนั้นเงียบ ๆ ในจังหวะที่ไม่มีใครดู
    """
    if choice.provider == "gemini":
        return _SplitConnector(
            # ฝั่ง embedding และตัวสำรองยังเป็นค่าจาก env เหมือนเดิมทุกตัว
            embedder=_build_ollama(),
            chatter=GeminiConnector(
                api_key=settings.gemini_api_key,
                chat_model=choice.model,
                timeout_s=settings.llm_request_timeout_s,
                # แพ็กเกจ llm/ ไม่รู้จักฐานข้อมูลของเรา จึงส่งตัวนับเข้าไปจากที่นี่
                on_event=llm_usage.record,
            ),
        )
    return _LocalPrimary(_build_ollama(choice.model))


# connector หนึ่งตัวต่อหนึ่งตัวเลือก เพื่อให้ httpx client และคิวคอนเนกชันถูกใช้ซ้ำ
# ไม่ใช่สร้างใหม่ทุกคำขอ · จำกัดจำนวนไว้เพราะแต่ละตัวถือ httpx client ของตัวเอง
# และผู้ดูแลเปลี่ยนชื่อรุ่นได้ไม่จำกัดครั้ง
_connectors: dict[tuple[str, str], object] = {}
_connectors_lock = threading.Lock()
MAX_CACHED_CONNECTORS = 4

# ช่องให้ชุดทดสอบใส่ connector ปลอมแทนของจริง — production ปล่อยเป็น None เสมอ
#
# ชุดทดสอบเดิมหลายไฟล์ตั้งค่านี้ตรง ๆ (`llm_client._connector = DEAD`) เพื่อจำลอง
# โมเดลล่มหรือเพื่อยืนยันว่าเส้นทางหนึ่งไม่เรียกโมเดลเลย ก่อนรอบนี้ชื่อนี้คือ
# singleton ตัวจริงของระบบ จึงใช้แทนกันได้พอดี
#
# **ห้ามตัดทิ้ง** ถ้าตัด การตั้งค่าในชุดทดสอบจะไม่มีผลโดยไม่มี error ให้เห็น
# แล้วชุดทดสอบจะไปเรียกโมเดลจริง — เจอจริงตอนรันชุดเดิมในคอนเทนเนอร์เมื่อ
# 28 ต.ค. 2569: test_model_outage_n1 ตก 6 จุดเพราะได้คำตอบจริงมาแทนข้อความ
# บริการขัดข้องที่มันตรวจอยู่
_connector = None


def get_llm_connector():
    """
    connector สำหรับตัวเลือกที่ใช้อยู่ "ตอนที่เรียก" — คืนวัตถุเดิมเมื่อตัวเลือกไม่เปลี่ยน

    ไม่เคยแก้ไขวัตถุที่แจกไปแล้ว การเปลี่ยนค่าจึงสร้าง connector ตัวใหม่ให้ผู้เรียก
    รายถัดไปเท่านั้น · ภายในหนึ่ง chat() หรือ chat_stream() ที่กำลังทำงานอยู่
    จึงไม่มีทางสลับโมเดลกลางทาง

    **แต่ฟังก์ชันนี้ไม่รับประกันว่าหนึ่งคำขอจะใช้เจ้าเดียว** หนึ่งคำขอเรียกโมเดล
    หลายขั้น ถ้าแต่ละขั้นมาขอ connector เองก็ได้คนละตัวเมื่อค่าเปลี่ยนระหว่างนั้น
    การตรึงให้เป็นเจ้าเดียวต่อคำขอเป็นหน้าที่ของผู้เรียก — services/chat.py พา
    connector ที่ขั้นแรกได้ไปกับ Prepared.connector แล้วขั้นเขียนคำตอบใช้ตัวนั้น
    (เจอจริงตอนทดสอบ 28 ต.ค. 2569 ว่าถ้าไม่ตรึง คำขอเดียวใช้ ollama ตรวจหลักฐาน
    แล้วใช้ gemini เขียนคำตอบ)
    """
    if _connector is not None:
        return _connector          # ชุดทดสอบใส่ของปลอมไว้ (ดูหมายเหตุที่ _connector)
    return connector_for(ai_settings.current())


def connector_for(choice: ai_settings.Choice):
    """
    connector ของตัวเลือกที่ระบุมาเอง — ใช้แคชชุดเดียวกับ get_llm_connector()

    มีไว้ให้คำขอที่ผู้ใช้เลือกโมเดลเองระบุตัวที่ต้องการได้ โดยไม่ต้องไปแตะค่าที่
    ผู้ดูแลตั้งไว้ · ใช้แคชร่วมกันเพราะ connector หนึ่งตัวถือ httpx client ของตัวเอง
    ถ้าสร้างใหม่ทุกคำขอจะเปิดการเชื่อมต่อทิ้งไว้เรื่อย ๆ จนหมดโควตา file descriptor
    """
    key = choice.key
    with _connectors_lock:
        found = _connectors.get(key)
    if found is not None:
        return found

    built = _build(choice)
    evicted = None
    with _connectors_lock:
        # มีคำขออื่นสร้างตัวเดียวกันพร้อมกันได้ ใช้ตัวที่เข้าก่อนเพื่อไม่ให้มีสองตัว
        if key in _connectors:
            built_dup, built = built, _connectors[key]
            _close_quietly(built_dup)
            return built
        if len(_connectors) >= MAX_CACHED_CONNECTORS:
            evicted = _connectors.pop(next(iter(_connectors)))
        _connectors[key] = built
    if evicted is not None:
        _close_quietly(evicted)
    logger.info("ใช้โมเดลเขียนคำตอบ: %s / %s (ที่มา: %s)",
                choice.provider, choice.model, choice.source)
    return built


# รุ่นที่ "เขียนข้อความให้คำขอนี้จริง" — บันทึกตอนเรียกสำเร็จ ไม่ใช่ตอนเลือก
#
# ต่างจาก answer_model_label() ที่บอกตัวที่ถูก **สั่ง** ให้เขียน · ถ้าเจ้าหลักล้มแล้ว
# โมเดลในเครื่องรับช่วงต่อ ค่าที่นี่จะเป็นโมเดลในเครื่อง เพราะข้อความที่ผู้ใช้เห็นมาจาก
# ตัวนั้นจริง · ไม่ได้เรียกโมเดลเลย = None ซึ่งต้องไม่ถูกแปลงเป็นชื่อรุ่นค่าตั้งต้น
#
# เก็บใน ContextVar ไม่ใช่ตัวแปรโมดูล เพราะหลายคำขอทำงานพร้อมกัน — endpoint แบบ sync
# ของ FastAPI รันใน threadpool ซึ่งคัดลอก context ให้ทีละคำขออยู่แล้ว (กลไกเดียวกับที่
# เพดานเวลาของคำขอใช้อยู่) ค่าของคำขอหนึ่งจึงไม่รั่วไปอีกคำขอ
_chat_model_used: ContextVar[tuple[str, str] | None] = ContextVar(
    "chat_model_used", default=None)

# ทุกรุ่นที่ตอบสำเร็จในคำขอนี้ เรียงตามลำดับที่ถูกใช้ครั้งแรก
#
# หนึ่งคำขอเรียกโมเดลได้หลายครั้ง — หน้าเปรียบเทียบสกัดตารางทีละหลักสูตรแล้วค่อยสรุป
# ถ้าเจ้าหลักล้มกลางทาง บางส่วนของหน้าจะมาจากคนละรุ่นกับส่วนที่เหลือ การรายงานแค่
# ตัวสุดท้ายจึงบอกผู้ใช้ไม่ครบว่าข้อความที่เขาอ่านอยู่มาจากใครบ้าง
_chat_models_used: ContextVar[tuple[tuple[str, str], ...]] = ContextVar(
    "chat_models_used", default=())


def record_chat_model(provider: str, model: str) -> None:
    """บันทึกว่าใครเพิ่งเขียนข้อความสำเร็จให้คำขอนี้ — เรียกหลังได้ผลลัพธ์เท่านั้น"""
    pair = (provider or "unknown", model or "?")
    _chat_model_used.set(pair)
    seen = _chat_models_used.get()
    if pair not in seen:
        _chat_models_used.set(seen + (pair,))


def reset_chat_model() -> None:
    """
    ล้างค่าก่อนเริ่มงานของคำขอใหม่ ไม่งั้นค่าที่ค้างอยู่จะถูกรายงานว่าเป็นของคำขอนี้

    ล้างรุ่นที่เทียบความคล้ายด้วย เพราะเป็นจุดเริ่มคำขอจุดเดียวกัน
    """
    _chat_model_used.set(None)
    _chat_models_used.set(())
    _embed_model_used.set(None)
    reset_answered_model()


def chat_model_used() -> dict | None:
    """{'provider', 'model'} ของการเขียนข้อความครั้งล่าสุดในคำขอนี้ · None = ไม่ได้เรียกโมเดล"""
    pair = _chat_model_used.get()
    return None if pair is None else {"provider": pair[0], "model": pair[1]}


# รุ่นที่ "แปลงคำตอบเป็นเวกเตอร์ให้คำขอนี้จริง" — บันทึกตอนเรียกสำเร็จเหมือนกัน
#
# คนละตัวกับรุ่นที่เขียนข้อความเสมอ และเป็นโมเดลในเครื่องโดยโครงสร้าง เพราะเวกเตอร์
# ของเอกสารทั้งคลังถูกสร้างด้วยรุ่นนี้และคอลัมน์ pgvector ตรึงจำนวนมิติไว้ (ดู _build_ollama)
#
# ไม่ได้เทียบความคล้ายเลยในคำขอนี้ = None ซึ่งต้องไม่ถูกแปลงเป็นชื่อรุ่นค่าตั้งต้น
EMBED_PROVIDER = "ollama"

_embed_model_used: ContextVar[tuple[str, str] | None] = ContextVar(
    "embed_model_used", default=None)


def record_embed_model(provider: str, model: str) -> None:
    """บันทึกว่ารุ่นไหนเพิ่งแปลงเวกเตอร์สำเร็จให้คำขอนี้ — เรียกหลังได้ผลลัพธ์เท่านั้น"""
    _embed_model_used.set((provider or "unknown", model or "?"))


def embed_model_used() -> dict | None:
    """{'provider', 'model'} ของการเทียบความคล้ายในคำขอนี้ · None = ไม่ได้ใช้เวกเตอร์"""
    pair = _embed_model_used.get()
    return None if pair is None else {"provider": pair[0], "model": pair[1]}


def chat_models_used() -> list[dict]:
    """ทุกรุ่นที่เขียนข้อความให้คำขอนี้ เรียงตามลำดับที่ถูกใช้ครั้งแรก · ไม่ได้เรียกเลย = []"""
    return [{"provider": p, "model": m} for p, m in _chat_models_used.get()]


def answer_model_label(connector) -> str:
    """
    ชื่อผู้ให้บริการและรุ่นที่ถูก "สั่งให้เขียน" คำตอบของคำขอนี้

    ย้ำว่าเป็นตัวที่ถูกสั่ง ไม่ใช่ตัวที่เขียนสำเร็จ — เส้นทาง Gemini มีตัวสำรองเป็น
    โมเดลในเครื่องที่รับช่วงต่อได้เมื่อเจ้าหลักล้มก่อนตัวอักษรแรก กรณีนั้นค่านี้ยัง
    เป็น gemini อยู่ และการรับช่วงถูกบันทึกไว้ที่ตัวนับ (`fallback_local_ok`)
    การยืนยันว่า "เจ้าที่เลือกเขียนเองจริง" จึงต้องดูสองอย่างประกอบกัน
    """
    provider = getattr(connector, "provider_name", "") or "unknown"
    return "{0}:{1}".format(provider, getattr(connector, "chat_model", "") or "?")


def _close_quietly(connector) -> None:
    try:
        close = getattr(connector, "close", None)
        if callable(close):
            close()
    except Exception:  # noqa: BLE001 — ปิดคอนเนกชันไม่สำเร็จห้ามทำให้คำขอพัง
        logger.debug("ปิด connector เดิมไม่สำเร็จ", exc_info=True)


# เพดานเวลาของขั้น "เรียกได้ไหม" — สั้นได้เพราะพรอมต์สั้น
PROBE_HELLO_BUDGET_S = 25.0
PROBE_HELLO_PROMPT = "ตอบกลับสั้น ๆ ว่า พร้อม"
# คำถามที่ใช้วัดขั้น work — เป็นคำถามที่ต้องอ่านเอกสารจริง ไม่ใช่คำทักทาย
PROBE_WORK_QUESTION = "หลักสูตรนี้เรียนเกี่ยวกับอะไร และมีกี่หน่วยกิต"


def _probe_chatter(choice: ai_settings.Choice):
    """ตัวที่จะถูกเรียกจริงตามตัวเลือก — ไม่ผ่านตัวสำรอง และไม่ส่ง on_event"""
    if choice.provider == "gemini":
        return GeminiConnector(
            api_key=settings.gemini_api_key,
            chat_model=choice.model,
            timeout_s=settings.llm_request_timeout_s,
            on_event=None,
        )
    return _build_ollama(choice.model)


def _probe_once(connector, messages, budget_s, *, json_mode=False, cap_tokens=True) -> dict:
    """
    เรียกหนึ่งครั้งแล้ววัดเวลา — พารามิเตอร์ต้องตรงกับขั้นที่กำลังเลียนแบบ

    cap_tokens=False สำหรับขั้นที่เลียนด่านตรวจหลักฐาน เพราะด่านจริงไม่ส่ง
    num_predict เลย (ดู services/chat.py::_grounding_verdict) การใส่เพดานให้
    ตอนตรวจจะทำให้ตรวจผ่านทั้งที่ของจริงล้ม
    """
    budget = start_budget(budget_s)
    started = time.monotonic()
    try:
        reply = connector.chat(
            messages, 0.0, json_mode,
            connector.answer_token_cap if cap_tokens else None,
        ).strip()
        ok, error = bool(reply), "" if reply else "ผู้ให้บริการตอบกลับแต่ไม่มีเนื้อหา"
    except Exception as e:  # noqa: BLE001 — หน้าผู้ดูแลต้องได้เห็นเหตุผลจริง
        ok, error, reply = False, "{0}: {1}".format(type(e).__name__, e)[:300], ""
    finally:
        reset_budget(budget)
    return {"ok": ok, "ms": int((time.monotonic() - started) * 1000),
            "reply": reply[:160], "error": error}


def probe(choice: ai_settings.Choice, sample_chunks: list[str] | None = None) -> dict:
    """
    เรียกผู้ให้บริการที่เลือกไว้จริง เพื่อแยก "บันทึกแล้ว" ออกจาก "ใช้งานได้"

    ตรวจสองขั้น เพราะสองคำถามนี้ไม่เท่ากัน และเคยตอบสวนทางกันจริง:

        hello  เรียกได้ไหม (พรอมต์สั้น เพดานเวลาของตัวเอง)
        work   ผ่าน "ด่านตรวจหลักฐาน" ได้ทันเพดานเวลาไหม — เรียกแบบเดียวกับ
               _grounding_verdict(): พรอมต์ชุดเดียวกัน json_mode=True ไม่จำกัด
               ความยาวผลลัพธ์ และ RAG_TIME_BUDGET_S ชุดเดียวกับคำขอของผู้ใช้

               เลือกขั้นนี้เพราะวัดแล้วพบว่าเวลาที่หายไปทั้งหมดอยู่ที่นี่ ไม่ใช่ขั้นเขียนคำตอบ
               (timing: decide=179,488ms จากเพดาน 180,000ms ส่วน write_answer ไม่ได้เริ่มเลย)

    **ผลของขั้น work เป็นสัญญาณ ไม่ใช่การรับประกัน** เนื้อหาที่ส่งเข้าไปวัดหยิบจากคลัง
    ตามลำดับ id ไม่ใช่ชิ้นที่การค้นเลือกให้คำถามจริง และด่านนี้ไม่จำกัดความยาวผลลัพธ์
    ความยาวที่โมเดลเขียนจึงแปรตามเนื้อหาที่ได้รับ · วัดเทียบกันที่ CHAT_TOP_K=12:

        ขั้น work ของการตรวจ (8,588 ตัวอักษร)        6,823 ms
        ด่านตรวจหลักฐานของคำขอจริง (12 ชิ้นที่ค้นมา)  100,815 ms

    ต่างกันราว 15 เท่า · การตรวจที่ไม่ผ่านจึงเชื่อถือได้ว่าใช้งานไม่ได้จริง
    แต่การตรวจที่ผ่าน **ไม่ได้ยืนยันว่าคำถามจริงทุกข้อจะทันเพดาน**

    วัดเมื่อ 28 ต.ค. 2569 บนฐานทดสอบ: qwen2.5:3b ผ่านขั้น hello ทุกครั้งในเวลาไม่ถึง
    หนึ่งวินาที แต่ด่านตรวจหลักฐานที่ CHAT_TOP_K=25 ใช้เวลาเกินเพดานทุกครั้ง คำขอจึงตาย
    ก่อนถึงขั้นเขียนคำตอบ ถ้ารายงานแค่ขั้น hello หน้าผู้ดูแลจะขึ้นเขียวให้ผู้ให้บริการที่
    ตอบคำถามจริงไม่ได้ ซึ่งเป็นการโกหกชนิดเดียวกับการขึ้นว่า "พร้อม" เพราะบันทึกสำเร็จ
    ตัวเลขที่วัดได้ทั้งหมดอยู่ที่ docs/MODEL_SWITCH_2569-10-28.md

    ตั้งใจไม่ส่ง on_event — การตรวจของผู้ดูแลไม่ใช่การใช้งานของผู้ใช้ ถ้านับรวม
    ตัวเลขสถิติจะเพิ่มขึ้นทุกครั้งที่มีคนกดปุ่มตรวจ · แต่ยังกินโควตาของผู้ให้บริการจริง
    """
    if choice.provider == "gemini" and not ai_settings.has_gemini_key():
        no_key = "เซิร์ฟเวอร์ไม่มี GEMINI_API_KEY"
        return {"ok": False, "provider": choice.provider, "model": choice.model,
                "hello": {"ok": False, "ms": 0, "reply": "", "error": no_key},
                "work": None, "budget_s": _DEFAULT_BUDGET_S,
                "ms": 0, "reply": "", "error": no_key}

    connector = _probe_chatter(choice)
    try:
        hello = _probe_once(
            connector, [ChatMessage(role="user", content=PROBE_HELLO_PROMPT)],
            PROBE_HELLO_BUDGET_S)
        work = None
        if hello["ok"] and sample_chunks:
            # เลียนด่านตรวจหลักฐานของคำขอจริงทุกอย่าง: พรอมต์ชุดเดียวกัน json_mode=True
            # ไม่จำกัดความยาวผลลัพธ์ และเพดานเวลา None = RAG_TIME_BUDGET_S ของผู้ใช้
            block = "\n\n".join(
                "[{0}] {1}".format(i + 1, c) for i, c in enumerate(sample_chunks))
            work = _probe_once(
                connector,
                [ChatMessage(role="system", content=GROUNDING_CHECK_SYSTEM_PROMPT),
                 ChatMessage(role="user", content=build_grounding_check_prompt(
                     block, PROBE_WORK_QUESTION))],
                None, json_mode=True, cap_tokens=False)
    finally:
        _close_quietly(connector)

    ok = hello["ok"] and (work is not None and work["ok"])
    if not hello["ok"]:
        error = hello["error"]
    elif work is None:
        error = "ไม่มีเนื้อหาในคลังเอกสารให้วัดขั้นตอบงานจริง จึงตรวจได้แค่ว่าเรียกได้"
    elif not work["ok"]:
        error = ("เรียกได้ แต่ด่านตรวจหลักฐานไม่ทันเพดาน {0:.0f} วินาที ({1}) — "
                 "เลือกไว้ได้ แต่ผู้ใช้จะได้ข้อความว่าระบบใช้เวลานานเกินไป"
                 ).format(_DEFAULT_BUDGET_S, work["error"] or "ไม่ทราบสาเหตุ")
    else:
        error = ""
    if not ok:
        logger.info("ตรวจผู้ให้บริการ %s/%s ไม่ผ่าน: %s", choice.provider, choice.model, error)
    return {"ok": ok, "provider": choice.provider, "model": choice.model,
            "hello": hello, "work": work, "budget_s": _DEFAULT_BUDGET_S,
            "error": error, "ms": hello["ms"] + (work["ms"] if work else 0),
            "reply": (work or hello)["reply"]}


def reset_connectors_for_test() -> None:
    global _connectors, _connector
    _connector = None
    with _connectors_lock:
        old, _connectors = _connectors, {}
    for c in old.values():
        _close_quietly(c)
    ai_settings.invalidate()
