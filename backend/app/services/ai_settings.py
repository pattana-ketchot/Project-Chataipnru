"""
ตัดสินว่าคำขอใหม่จะใช้ผู้ให้บริการและรุ่นไหนเขียนคำตอบ

ทำไมต้องมีไฟล์นี้
-----------------
หน้าผู้ดูแลมีช่องตั้งค่าโมเดลและบันทึกลง `web.ai_settings` ได้ตั้งแต่ Phase 4
แต่ไม่มีโค้ดส่วนใดอ่านค่านั้นเลย — `get_llm_connector()` สร้าง connector ครั้งเดียว
จาก env แล้วเก็บเป็น singleton ผลคือหน้าเว็บขึ้นว่าบันทึกสำเร็จ ขณะที่โมเดลที่ตอบจริง
ไม่เปลี่ยน และเปลี่ยนไม่ได้จนกว่าจะ restart ทั้งคอนเทนเนอร์

ไฟล์นี้เป็นจุดเดียวที่ตอบคำถามว่า "ตอนนี้ใช้อะไร" โดยรวมสามแหล่งเข้าด้วยกัน:

    ค่าที่ผู้ดูแลบันทึก (ฐานข้อมูล)  ->  ตรวจความถูกต้อง  ->  ค่าตั้งต้นจาก env

กฎที่ตั้งใจให้ "deploy แล้วพฤติกรรมไม่เปลี่ยน"
---------------------------------------------
ค่าที่บันทึกจะถูกใช้ก็เมื่อ `provider` ถูกระบุไว้เท่านั้น แถวเดิมในฐาน production
มีแต่ `model` (ค่าที่ไม่มีใครอ่านมาตลอด และชี้ไปรุ่นที่ env ไม่ได้ใช้) ถ้าถือว่า
คอลัมน์นั้นมีความหมายทันทีที่โค้ดนี้ขึ้น ระบบจะเริ่มส่งชื่อรุ่นที่ไม่เคยถูกตรวจ
ไปให้ผู้ให้บริการจริงตั้งแต่วินาทีแรกของการ deploy ซึ่งเป็นการเปลี่ยนพฤติกรรม
โดยที่ไม่มีใครสั่ง จึงกำหนดว่า model ที่ไม่มี provider กำกับ = ยังไม่ได้เลือก

embedding เปลี่ยนไม่ได้
----------------------
สวิตช์นี้แตะ "โมเดลที่เขียนคำตอบ" เท่านั้น ฝั่ง embedding ยังอ่านจาก env
(`EMBED_MODEL` = bge-m3 ขนาด 1024 มิติ) เสมอ เพราะเวกเตอร์ของเอกสารทั้งคลัง
และขนาดคอลัมน์ในฐานข้อมูลผูกกับโมเดลตัวนั้น การเปลี่ยนแปลว่าต้องสร้างเวกเตอร์ใหม่
ทั้งคลัง ดู services/llm_client.py
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, replace

from sqlalchemy import text

from app.core.config import get_settings

logger = logging.getLogger("course_advisor")
settings = get_settings()

# ผู้ให้บริการที่โค้ดนี้สร้าง connector ให้ได้จริง — ต้องตรงกับ CHECK ของ
# db/migrations/010_ai_settings_provider.sql และกับ _build() ใน llm_client.py
PROVIDERS = ("gemini", "ollama")

# ค่าที่บันทึกมีผลกับคำขอใหม่ภายในเวลานี้โดยไม่ต้อง restart
#
# ตั้งไว้สั้นเพราะต้นทุนคือการอ่านหนึ่งแถวจากตารางที่มีแถวเดียว แต่ไม่ตั้งเป็นศูนย์
# เพราะ get_llm_connector() ถูกเรียกหลายครั้งต่อหนึ่งคำขอ (ขั้นเขียนคำถามใหม่
# ด่านตรวจเอกสาร ขั้นเขียนคำตอบ) การอ่านฐานทุกครั้งคือการต่อคิว connection
# เพิ่มในเส้นทางที่ผู้ใช้รออยู่ โดยไม่ได้ความถูกต้องเพิ่มขึ้นเลย
#
# เส้นทางบันทึกจาก /site-admin/ai-settings เรียก invalidate() ให้อยู่แล้ว
# ค่าใหม่จึงมีผลทันทีในกระบวนการที่รับคำขอบันทึก TTL นี้เป็นเพียงตัวกันพลาด
# สำหรับการแก้ค่าในฐานโดยตรงหรือกรณีมีหลายกระบวนการ
CACHE_TTL_S = 10.0

_SELECT = text("select provider, model, updated_at from web.ai_settings where id = 1")


@dataclass(frozen=True)
class Choice:
    """ผลการตัดสิน — แยก “ที่ผู้ดูแลสั่ง” ออกจาก “ที่ใช้จริง” ให้เห็นทั้งสองค่า"""

    provider: str          # ที่ใช้จริงกับคำขอใหม่
    model: str             # ที่ใช้จริงกับคำขอใหม่
    source: str            # db = มาจากค่าที่บันทึก · env = มาจาก environment
    saved_provider: str | None = None   # ที่บันทึกไว้ (None = ยังไม่เลือก)
    saved_model: str | None = None
    # เหตุผลเมื่อค่าที่ใช้จริงไม่ตรงกับที่บันทึก — ว่างเมื่อใช้ได้ตามที่สั่ง
    # หน้าผู้ดูแลต้องแสดงข้อความนี้ ไม่ใช่แสดงแค่ว่าบันทึกสำเร็จ
    note: str = ""

    @property
    def key(self) -> tuple[str, str]:
        return (self.provider, self.model)

    @property
    def honoured(self) -> bool:
        """ค่าที่บันทึกถูกใช้ตามนั้นหรือไม่"""
        return self.saved_provider is not None and not self.note


# ===========================================================================
# ตัวเลือกที่ "ผู้ใช้หน้าเว็บ" เลือกเองได้ — คนละชุดกับที่ผู้ดูแลตั้ง
#
# ผู้ดูแลตั้งค่าตั้งต้นของทั้งระบบ (ตาราง web.ai_settings) ส่วนรายการนี้คือตัวเลือก
# ที่ยอมให้นักศึกษาสลับเองเป็นรายคำขอ · แยกกันเพราะสองเรื่องนี้ต้องการการควบคุม
# คนละระดับ: ค่าตั้งต้นกระทบทุกคน ส่วนตัวเลือกรายคำขอกระทบแค่คนที่กด
#
# **รับเฉพาะ id ในรายการนี้เท่านั้น ไม่รับชื่อรุ่นที่ส่งมาจากหน้าเว็บตรง ๆ**
# ไม่งั้นใครก็ยิงชื่อรุ่นแพง ๆ เข้ามาเผาโควตาของคณะได้
#
# budget_s = เพดานเวลาของคำขอที่เลือกตัวนั้น · None = ใช้ค่าตั้งต้น (RAG_TIME_BUDGET_S)
# โมเดลในเครื่องต้องได้เพดานของตัวเองเพราะวัดแล้วว่าใช้เวลาหลักนาทีบนเครื่องที่
# ไม่มีการ์ดจอ ถ้าใช้เพดาน 30 วินาทีเท่าคลาวด์คือรับประกันว่าไม่มีวันตอบทัน
# (ตัวเลขอยู่ใน docs/SWITCH_PLUS_FALLBACK_READINESS_2569-10-28.md ข้อ 4)
# ===========================================================================
PUBLIC_CHOICES: tuple[dict, ...] = (
    {
        "id": "fast",
        "provider": "gemini",
        "model": "",                 # ว่าง = ใช้รุ่นตั้งต้นของ env (ตัวที่ใช้อยู่จริง)
        "label": "ตอบเร็ว",
        "hint": "แนะนำ · ตอบภายในไม่กี่วินาที",
        "budget_s": None,
    },
    {
        "id": "detailed",
        "provider": "gemini",
        "model": "gemini-3.5-flash",
        "label": "ตอบละเอียด",
        "hint": "ใช้รุ่นใหญ่กว่า ช้ากว่าเล็กน้อย",
        "budget_s": None,
    },
    {
        "id": "local",
        "provider": "ollama",
        "model": "",                 # ว่าง = รุ่นตั้งต้นของ env (LLM_MODEL)
        "label": "ประมวลผลในเครื่อง",
        "hint": "ทดลอง · ข้อมูลไม่ออกนอกเซิร์ฟเวอร์ แต่ช้ามาก ต้องรอ 2–4 นาที",
        "budget_s": 240.0,
    },
)

# id ที่ใช้เมื่อผู้ใช้ไม่ได้เลือก — ต้องมีอยู่ใน PUBLIC_CHOICES เสมอ
DEFAULT_PUBLIC_CHOICE = "fast"


def public_choices() -> list[dict]:
    """
    รายการที่หน้าเว็บเอาไปทำปุ่มได้ — ซ่อนตัวที่เซิร์ฟเวอร์นี้ใช้ไม่ได้ออกไปเลย

    ซ่อนดีกว่าแสดงแล้วให้กดไม่ได้ เพราะผู้ใช้ไม่มีทางรู้ว่าทำไมมันไม่ทำงาน
    เช่นเซิร์ฟเวอร์ที่ไม่ได้ตั้ง GEMINI_API_KEY จะไม่เห็นตัวเลือกของ Gemini เลย
    """
    out = []
    for c in PUBLIC_CHOICES:
        if c["provider"] == "gemini" and not has_gemini_key():
            continue
        out.append({
            "id": c["id"],
            "label": c["label"],
            "hint": c["hint"],
            "model": c["model"] or default_model_of(c["provider"]),
            "default": c["id"] == DEFAULT_PUBLIC_CHOICE,
        })
    return out


def public_choice(choice_id: str | None) -> tuple[Choice, float | None] | None:
    """
    แปลง id ที่หน้าเว็บส่งมาเป็นตัวเลือกจริง คืน (Choice, เพดานเวลา)

    คืน None เมื่อ id ไม่อยู่ในรายการหรือใช้ไม่ได้บนเซิร์ฟเวอร์นี้ — ผู้เรียกต้อง
    ถอยไปใช้ค่าของผู้ดูแลแทน ไม่ใช่โยนข้อผิดพลาดใส่ผู้ใช้ เพราะ id ที่ไม่รู้จัก
    มักเกิดจากหน้าเว็บรุ่นเก่าที่ยังจำตัวเลือกเดิมไว้ ไม่ใช่การโจมตี
    """
    if not choice_id:
        return None
    allowed = {c["id"] for c in public_choices()}
    for c in PUBLIC_CHOICES:
        if c["id"] != choice_id or c["id"] not in allowed:
            continue
        model = c["model"] or default_model_of(c["provider"])
        return Choice(provider=c["provider"], model=model, source="user"), c["budget_s"]
    return None


def default_model_of(provider: str) -> str:
    return settings.gemini_model if provider == "gemini" else settings.llm_model


def has_gemini_key() -> bool:
    """มีคีย์ในเซิร์ฟเวอร์หรือไม่ — คืนเฉพาะจริง/เท็จ ตัวคีย์ไม่ออกจากหลังบ้าน"""
    return bool((settings.gemini_api_key or "").strip())


def env_default() -> Choice:
    """ค่าตั้งต้นจาก environment — ใช้เมื่อยังไม่เลือก หรือเมื่อค่าที่เลือกใช้ไม่ได้"""
    provider = (settings.llm_provider or "").strip().lower()
    if provider not in PROVIDERS:
        # env เองก็ตั้งผิดได้ ถ้าปล่อยผ่านจะไปล้มตอนสร้าง connector ซึ่งไกลจากต้นเหตุ
        logger.warning(
            "LLM_PROVIDER=%r ไม่ใช่ค่าที่รองรับ (%s) — ใช้ ollama",
            settings.llm_provider, ", ".join(PROVIDERS),
        )
        provider = "ollama"
    return Choice(provider=provider, model=default_model_of(provider), source="env")


def resolve(db) -> Choice:
    """
    อ่านค่าที่บันทึกแล้วตัดสินว่าจะใช้อะไร — ไม่โยนข้อผิดพลาดออกมาเลย

    ฐานข้อมูลล่มต้องไม่ทำให้ตอบคำถามไม่ได้ เพราะค่าตั้งต้นจาก env ใช้งานได้อยู่แล้ว
    """
    try:
        row = db.execute(_SELECT).mappings().first()
    except Exception:  # noqa: BLE001 — การอ่านค่าตั้งค่าห้ามทำให้คำตอบพัง
        logger.warning("อ่าน web.ai_settings ไม่ได้ — ใช้ค่าจาก env", exc_info=True)
        return replace(env_default(), note="อ่านค่าที่บันทึกไม่ได้ จึงใช้ค่าจาก environment")

    data = dict(row) if row else {}
    saved_provider = str(data.get("provider") or "").strip().lower() or None
    saved_model = str(data.get("model") or "").strip() or None
    env = env_default()

    if saved_provider is None:
        # ยังไม่เลือก — รวมถึงแถวเดิมที่มีแต่ model ซึ่งไม่รู้ว่าหมายถึงเจ้าไหน
        note = ""
        if saved_model:
            note = ("ค่า {0} ที่บันทึกไว้ยังไม่ถูกใช้ เพราะไม่ได้ระบุผู้ให้บริการกำกับ "
                    "เลือกผู้ให้บริการแล้วกดบันทึกอีกครั้งเพื่อให้มีผล").format(saved_model)
        return replace(env, saved_model=saved_model, note=note)

    if saved_provider not in PROVIDERS:
        logger.warning("provider ที่บันทึกไว้ (%r) ไม่รองรับ — ใช้ค่าจาก env", saved_provider)
        return replace(
            env, saved_provider=saved_provider, saved_model=saved_model,
            note="ผู้ให้บริการ {0} ที่บันทึกไว้ไม่รองรับ จึงใช้ค่าจาก environment".format(saved_provider),
        )

    if saved_provider == "gemini" and not has_gemini_key():
        # บันทึกสำเร็จไม่เท่ากับใช้งานได้ ต้องบอกให้ชัดว่าของจริงคือเจ้าไหน
        logger.warning("เลือก gemini ไว้แต่เซิร์ฟเวอร์ไม่มี GEMINI_API_KEY — ใช้ ollama")
        local = Choice(provider="ollama", model=default_model_of("ollama"), source="env")
        return replace(
            local, saved_provider=saved_provider, saved_model=saved_model,
            note="เลือก Gemini ไว้ แต่เซิร์ฟเวอร์ไม่มี GEMINI_API_KEY "
                 "จึงยังใช้โมเดลในเครื่องตอบ ต้องตั้งคีย์ที่ environment ก่อน",
        )

    model = saved_model or default_model_of(saved_provider)
    return Choice(
        provider=saved_provider, model=model, source="db",
        saved_provider=saved_provider, saved_model=saved_model,
        note="" if saved_model else "ไม่ได้ระบุรุ่น จึงใช้รุ่นตั้งต้นของผู้ให้บริการจาก environment",
    )


# ---------------------------------------------------------------------
# แคชอายุสั้น — ให้ค่าใหม่มีผลโดยไม่ต้อง restart แต่ไม่อ่านฐานทุกครั้งที่ถาม
# ---------------------------------------------------------------------
_lock = threading.Lock()
_cached: tuple[float, Choice] | None = None


def current() -> Choice:
    """
    ตัวเลือกที่ใช้กับคำขอใหม่ — เปิดคอนเนกชันของตัวเองเพราะผู้เรียกบางรายไม่มี session

    get_llm_connector() ถูกเรียกจาก rag.py / search.py / match.py ซึ่งไม่ได้รับ
    Session มาด้วย การบังคับให้ส่ง db เข้ามาแปลว่าต้องแก้ทุกจุดที่เรียก และยังทำให้
    ขั้นที่ไม่เกี่ยวกับฐานข้อมูลต้องรู้จักฐานข้อมูล จึงเลือกอ่านเองที่นี่แล้วแคชไว้
    """
    global _cached
    now = time.monotonic()
    with _lock:
        if _cached is not None and now - _cached[0] < CACHE_TTL_S:
            return _cached[1]

    # อ่านนอก lock เพื่อไม่ให้คำขออื่นค้างรอการอ่านฐาน · อ่านซ้อนกันได้ ผลเหมือนกัน
    from app.db.session import SessionLocal  # ภายในฟังก์ชัน เลี่ยง import วน

    db = SessionLocal()
    try:
        choice = resolve(db)
    finally:
        db.close()

    with _lock:
        _cached = (time.monotonic(), choice)
    return choice


def invalidate() -> None:
    """ทิ้งแคชทันที — เรียกหลังผู้ดูแลบันทึกค่าใหม่ ให้คำขอถัดไปเห็นค่าใหม่เลย"""
    global _cached
    with _lock:
        _cached = None


def reset_for_test() -> None:
    invalidate()
