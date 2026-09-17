"""
โหมด shadow ของคำตอบจากข้อมูลหลักสูตรที่มีโครงสร้าง — Phase 2 ของ docs/MKO_STRUCTURED_DATA_DESIGN.md

STRUCTURED_ANSWERS
    off     (ค่าตั้งต้น) ไม่ทำอะไรเลย ไม่เปิด thread ไม่แตะฐานข้อมูล
    shadow  หลังระบบเดิมได้คำตอบแล้ว คำนวณคำตอบจากฐานข้อมูลใน thread แยก เทียบกับคำตอบที่ผู้ใช้ได้รับจริง
            แล้วบันทึกลง mko.shadow_answers — คำตอบที่ผู้ใช้เห็นไม่เปลี่ยน
    on      ใช้คำตอบจากฐานข้อมูลตอบผู้ใช้ เฉพาะเมื่อครบทุกข้อ (ดู structured_reply)
              route = structured · ฐานข้อมูลตอบได้ (answered) · field อยู่ใน USER_FACING_FIELDS
            กรณีอื่นทั้งหมดใช้คำตอบ RAG เดิม และยังบันทึกผลลง mko.shadow_answers เหมือนโหมด shadow
    ค่าอื่น   ถือเป็น off และเตือนใน log

ข้อรับประกันต่อระบบเดิม
    - submit() ถูกเรียกหลังได้คำตอบครบแล้วเท่านั้น และคืนค่าที่ผู้เรียกไม่ได้ใช้
    - ทุกข้อผิดพลาดถูกจับไว้แล้วลง log ไม่โยนกลับไปที่ขั้นตอบ (รวมถึงกรณียังไม่มี schema mko)
    - ใช้ session ฐานข้อมูลของตัวเอง คิวมีเพดาน งานที่เกินเพดานถูกทิ้งทันทีไม่รอ
    - structured_reply() ไม่โยน exception และไม่แตะ session ของคำขอ ถ้าพังหรือไม่แน่ใจ คืน None = ใช้คำตอบ RAG

ผลการเทียบ (comparison)
    agree             คำตอบเดิมมีค่าเดียวกับฐานข้อมูลครบ
    partial           ตรงบางส่วน เช่น ฐานข้อมูลมีสองฉบับแต่คำตอบเดิมบอกค่าเดียว หรือมีรายการครบเพียงบางข้อ
    disagree          คำตอบเดิมให้ค่าอื่น หรือไม่มีรายการใดตรงเลย
    served_no_answer  ระบบเดิมตอบว่าไม่พบข้อมูลหรือนอกขอบเขต แต่ฐานข้อมูลตอบได้
    unclear           หาค่าที่เทียบได้ในคำตอบเดิมไม่เจอ
    not_compared      ฐานข้อมูลไม่มีคำตอบ (ไม่ใช่คำถามแบบ structured หรือยังไม่มีข้อมูลที่เผยแพร่)
การเทียบเป็นกฎตรวจข้อความแบบง่าย ใช้ดูแนวโน้ม ไม่ใช่ตัวตัดสินความถูกต้อง ทุกแถวเก็บคำตอบทั้งสองฝั่งไว้ให้คนอ่านซ้ำได้
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.course_scope import degree_level_of, degree_of_title
from app.services.curriculum_facts import ANSWERED, FactsResult, lookup
from app.services.structured_intent import STRUCTURED, detect

logger = logging.getLogger(__name__)

OFF, SHADOW, ON = "off", "shadow", "on"
SERVED_STRUCTURED, SERVED_RAG = "structured", "rag"

# field ที่คำตอบจากฐานข้อมูลตอบผู้ใช้ได้ในโหมด on — ระบุทีละ field โดยตั้งใจ ไม่ใช่ "ทุก field ยกเว้น"
# field ที่ routing รองรับเพิ่มในอนาคตจึงยังตอบด้วย RAG จนกว่าจะเพิ่มชื่อไว้ที่นี่
# admission ไม่อยู่ในรายการ: คำตอบแสดงเฉพาะหัวข้อคุณสมบัติผู้เข้าศึกษาใน มคอ.2 โดยไม่บอกขอบเขต ขณะที่เล่มเดียวกันมีเกณฑ์อื่น
# (docs/MKO_PHASE2_FINAL_SHADOW_VALIDATION.md ข้อ B) จึงยังตอบด้วย RAG
USER_FACING_FIELDS = frozenset({"total_credits", "edition_year", "careers", "objectives"})

_MAX_PENDING = 32
_SERVED_NO_ANSWER = ("not_found", "out_of_scope")
# หน่วยกิตรวมตลอดหลักสูตรปริญญาตรีมากกว่านี้เสมอ ตัวเลขที่น้อยกว่าในคำตอบคือหน่วยกิตรายหมวด ไม่ใช่ยอดรวม
_TOTAL_CREDIT_FLOOR = 100
_ITEM_COVERED = 0.6
_THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")
_CREDIT_NUMBER = re.compile(r"(\d{2,3})\s*หน่วยกิต")
_YEAR = re.compile(r"(?<!\d)25\d{2}(?!\d)")

# หลักสูตรบัณฑิตศึกษามียอดรวมต่ำกว่าเพดานข้างบน (เช่น ป.โท 36, ป.เอก 48) เพดานเดียวจึงใช้กับทุกระดับไม่ได้
# แต่การลดเพดานทั้งระบบจะทำให้หน่วยกิตรายหมวดของปริญญาตรี (24, 30, 6) ถูกนับเป็นยอดรวม
# จึงรับตัวเลขที่ต่ำกว่าเพดานเฉพาะเมื่อ (1) ทุกฉบับที่เทียบเป็นบัณฑิตศึกษา และ (2) ตัวเลขอยู่ในบริบท "ยอดรวมตลอดหลักสูตร"
_GRADUATE_LEVELS = frozenset({"master", "doctoral"})
_TOTAL_CREDIT_CONTEXT = re.compile(
    r"(?:ตลอดหลักสูตร|หน่วยกิตรวม)[^0-9\n]{0,40}?(\d{1,3})\s*หน่วยกิต"
    r"|(\d{1,3})\s*หน่วยกิต(?:รวม)?ตลอดหลักสูตร"
)

_executor: ThreadPoolExecutor | None = None
_executor_lock = threading.Lock()
_pending = threading.BoundedSemaphore(_MAX_PENDING)
_warned: set[str] = set()


def _warn_once(key: str, message: str, *args) -> None:
    if key not in _warned:
        _warned.add(key)
        logger.warning(message, *args)


def configured_mode(raw: str | None = None) -> str:
    value = ((get_settings().structured_answers if raw is None else raw) or OFF).strip().lower()
    if value in (OFF, SHADOW, ON):
        return value
    _warn_once(value, "STRUCTURED_ANSWERS=%r ไม่รู้จัก — ถือเป็น off", value)
    return OFF


def _fold(value: str) -> str:
    value = value.translate(_THAI_DIGITS).lower().replace("ํา", "ำ").replace("ำ", "า")
    return re.sub(r"\s+", "", value)


def _coverage(item: str, folded_reply: str, size: int = 4) -> float:
    folded = _fold(item)
    if len(folded) <= size:
        return 1.0 if folded and folded in folded_reply else 0.0
    grams = {folded[i:i + size] for i in range(len(folded) - size + 1)}
    return sum(g in folded_reply for g in grams) / len(grams)


def _fact_levels(result: FactsResult) -> set[str | None]:
    """ระดับปริญญาของทุกฉบับที่กำลังเทียบ — ฉบับที่อ่านระดับจากชื่อไม่ได้จะให้ None เพื่อให้ตัดสินแบบระมัดระวัง"""
    return {degree_level_of(degree_of_title(f.course_title or "")) for f in result.facts}


def _total_credits_in_reply(reply: str, levels: set[str | None]) -> list[int]:
    """
    ตัวเลขในคำตอบเดิมที่ถือว่าเป็น "หน่วยกิตรวมตลอดหลักสูตร"

    ปริญญาตรี (และกรณีที่อ่านระดับไม่ได้) ใช้กฎเดิมคือเลข >= _TOTAL_CREDIT_FLOOR เท่านั้น
    ถ้าทุกฉบับที่เทียบเป็นบัณฑิตศึกษา ให้รับเลขที่อยู่ในบริบทยอดรวมเพิ่มด้วย เพราะยอดรวมของระดับนี้
    อยู่ต่ำกว่าเพดาน — บริบทเป็นตัวกันไม่ให้หน่วยกิตรายหมวดหรือหน่วยกิตวิทยานิพนธ์ถูกนับเป็นยอดรวม
    """
    plain = reply.replace(",", "")
    found = {int(n) for n in _CREDIT_NUMBER.findall(plain) if int(n) >= _TOTAL_CREDIT_FLOOR}
    if levels and levels <= _GRADUATE_LEVELS:
        for match in _TOTAL_CREDIT_CONTEXT.finditer(plain):
            found.add(int(match.group(1) or match.group(2)))
    return sorted(found)


def _set_verdict(expected: list[int], found: list[int]) -> str:
    if not found:
        return "unclear"
    if set(expected) == set(found):
        return "agree"
    return "partial" if set(expected) & set(found) else "disagree"


def compare(result: FactsResult | None, served_status: str | None, served_reply: str | None) -> tuple[str, dict]:
    if result is None or result.status != ANSWERED:
        return "not_compared", {}
    if served_status in _SERVED_NO_ANSWER:
        return "served_no_answer", {"served_status": served_status}
    reply = (served_reply or "").translate(_THAI_DIGITS)

    if result.field == "total_credits":
        expected = sorted({f.value_int for f in result.facts})
        levels = _fact_levels(result)
        found = _total_credits_in_reply(reply, levels)
        detail = {"expected": expected, "found_in_reply": found,
                  "degree_levels": sorted(lv for lv in levels if lv is not None)}
        return _set_verdict(expected, found), detail
    if result.field == "edition_year":
        expected = sorted({f.value_int for f in result.facts})
        found = sorted({int(y) for y in _YEAR.findall(reply)})
        return _set_verdict(expected, found), {"expected": expected, "found_in_reply": found}

    folded = _fold(reply)
    coverage = [_coverage(item, folded) for item in result.facts[0].items]
    covered = sum(c >= _ITEM_COVERED for c in coverage)
    detail = {"items": len(coverage), "covered": covered, "coverage": [round(c, 2) for c in coverage]}
    if not coverage:
        return "unclear", detail
    if covered / len(coverage) >= 0.8:
        return "agree", detail
    if covered:
        return "partial", detail
    # ไม่มีข้อใดตรงพอ แต่ถ้อยคำใกล้เคียงมาก = อาจเป็นการเรียบเรียงใหม่ ตัดสินจากกฎนี้ไม่ได้
    return ("unclear" if sum(coverage) / len(coverage) >= 0.3 else "disagree"), detail


def servable_answer(db: Session, asked: str) -> str | None:
    """
    คำตอบจากฐานข้อมูลที่ใช้ตอบผู้ใช้ได้ หรือ None = ต้องตอบด้วย RAG

    ใช้ detect / lookup ตัวเดียวกับโหมด shadow ไม่ได้ตีความคำถามหรือเรียบเรียงคำตอบใหม่
    ตรวจ field ก่อน lookup เพื่อให้ field ที่ไม่อยู่ในรายการ (เช่น admission) ไม่ถูกดึงข้อมูลมาตอบเลย
    """
    intent = detect(db, asked)
    if intent.route != STRUCTURED or intent.field not in USER_FACING_FIELDS:
        return None
    result = lookup(db, intent)
    if result.status != ANSWERED or not (result.answer or "").strip():
        return None
    return result.answer


def structured_reply(*, question: str, interpreted: str | None) -> str | None:
    """
    โหมด on: คำตอบจากฐานข้อมูลที่จะส่งให้ผู้ใช้แทนคำตอบ RAG · โหมดอื่นหรือตอบไม่ได้ คืน None

    ไม่โยน exception — ฐานข้อมูลล่ม ยังไม่มี schema mko หรือบั๊กใดๆ ต้องได้คำตอบ RAG ตามเดิม
    ใช้ session ของตัวเอง ถ้าใช้ session ของคำขอ query ที่ล้มจะทำให้ transaction ของคำขอเสีย
    แล้วขั้นบันทึกบทสนทนาหลังจากนี้พังตาม
    """
    try:
        if configured_mode() != ON:
            return None
        with SessionLocal() as db:
            try:
                return servable_answer(db, interpreted or question)
            finally:
                db.rollback()
    except Exception:  # noqa: BLE001 — ข้อผิดพลาดของ structured ห้ามทำให้ตอบผู้ใช้ไม่ได้
        logger.warning("หาคำตอบจากฐานข้อมูลไม่สำเร็จ — ใช้คำตอบ RAG แทน", exc_info=True)
        return None


def run_shadow(
    db: Session,
    *,
    question: str,
    interpreted: str | None = None,
    has_history: bool = False,
    served_status: str | None = None,
    served_reply: str | None = None,
    served_source: str = SERVED_RAG,
    configured: str = SHADOW,
    mode: str = SHADOW,
    commit: bool = True,
) -> dict:
    """
    คำนวณคำตอบจากฐานข้อมูล เทียบกับคำตอบที่ผู้ใช้ได้รับ แล้วบันทึกหนึ่งแถว คืนค่าที่บันทึก

    served_source / configured บันทึกไว้ใน comparison_detail เพราะคอลัมน์ mode รับได้เฉพาะ shadow / replay
    (ไม่เพิ่ม migration) — ผู้ใช้ได้คำตอบจากฐานข้อมูลเมื่อ served_source = structured ซึ่งไม่มีคำตอบ RAG ให้เทียบ
    """
    started = time.perf_counter()
    asked = interpreted or question
    intent = detect(db, asked)
    result = lookup(db, intent) if intent.route == STRUCTURED else None
    if served_source == SERVED_STRUCTURED:
        comparison, detail = "not_compared", {}
    else:
        comparison, detail = compare(result, served_status, served_reply)
    detail = {**detail, "served_source": served_source, "configured_mode": configured}
    facts = result.to_json() if result is not None else {}
    facts.pop("answer", None)

    record = {
        "mode": mode,
        "question": question,
        "interpreted_question": asked if asked != question else None,
        "has_history": has_history,
        "intent_field": intent.field,
        "route": intent.route,
        "route_reason": intent.reason,
        "course_ids": [str(c) for c in intent.course_ids],
        "year_be": intent.year_be,
        "structured_status": "not_applicable" if result is None else result.status,
        "structured_answer": result.answer if result is not None else None,
        "facts": facts,
        "publication_id": result.publication_id if result is not None else None,
        "served_status": served_status,
        "served_reply": served_reply,
        "comparison": comparison,
        "comparison_detail": detail,
        "latency_ms": int((time.perf_counter() - started) * 1000),
    }
    db.execute(
        text(
            """
            INSERT INTO mko.shadow_answers
                (mode, question, interpreted_question, has_history, intent_field, route, route_reason, course_ids,
                 structured_status, structured_answer, facts, publication_id, served_status, served_reply,
                 comparison, comparison_detail, latency_ms)
            VALUES
                (:mode, :question, :interpreted_question, :has_history, :intent_field, :route, :route_reason,
                 CAST(:course_ids AS uuid[]), :structured_status, :structured_answer, CAST(:facts AS jsonb),
                 CAST(:publication_id AS uuid), :served_status, :served_reply, :comparison,
                 CAST(:comparison_detail AS jsonb), :latency_ms)
            """
        ),
        {
            **{k: v for k, v in record.items() if k != "year_be"},
            "facts": json.dumps({**facts, "year_be": intent.year_be}, ensure_ascii=False),
            "comparison_detail": json.dumps(detail, ensure_ascii=False),
        },
    )
    if commit:
        db.commit()
    return record


def _run_logged(kwargs: dict) -> None:
    try:
        with SessionLocal() as db:
            try:
                run_shadow(db, **kwargs)
            except Exception:
                db.rollback()
                raise
    except Exception:  # noqa: BLE001 — โหมด shadow ห้ามกระทบระบบเดิมไม่ว่าพังแบบไหน
        logger.warning("บันทึกผลโหมด shadow ไม่สำเร็จ", exc_info=True)


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    with _executor_lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="structured-shadow")
        return _executor


def submit(
    *,
    question: str,
    interpreted: str | None,
    has_history: bool,
    served_status: str | None,
    served_reply: str | None,
    served_source: str = SERVED_RAG,
) -> Future | None:
    """ส่งงานบันทึกผลเข้าคิว (โหมด shadow และ on) คืน None เมื่อปิดอยู่ คิวเต็ม หรือมีข้อผิดพลาด ไม่โยน exception"""
    try:
        configured = configured_mode()
        if configured not in (SHADOW, ON):
            return None
        if not _pending.acquire(blocking=False):
            _warn_once("queue_full", "คิวโหมด shadow เต็ม — ทิ้งงานที่เกินจนกว่าคิวจะว่าง")
            return None
        try:
            future = _get_executor().submit(
                _run_logged,
                {"question": question, "interpreted": interpreted, "has_history": has_history,
                 "served_status": served_status, "served_reply": served_reply,
                 "served_source": served_source, "configured": configured},
            )
        except Exception:
            _pending.release()
            raise
        future.add_done_callback(lambda _f: _pending.release())
        return future
    except Exception:  # noqa: BLE001
        logger.warning("ส่งงานโหมด shadow ไม่สำเร็จ", exc_info=True)
        return None
