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
from dataclasses import dataclass, replace

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.course_scope import degree_level_of, degree_of_title
from app.services.curriculum_facts import ANSWERED, FactsResult, lookup
from app.services.structured_intent import (STRUCTURED, comparison_sides, detect,
                                            matched_fields, only_field)

logger = logging.getLogger(__name__)

OFF, SHADOW, ON = "off", "shadow", "on"
SERVED_STRUCTURED, SERVED_RAG = "structured", "rag"

# field ที่คำตอบจากฐานข้อมูลตอบผู้ใช้ได้ในโหมด on — ระบุทีละ field โดยตั้งใจ ไม่ใช่ "ทุก field ยกเว้น"
# field ที่ routing รองรับเพิ่มในอนาคตจึงยังตอบด้วย RAG จนกว่าจะเพิ่มชื่อไว้ที่นี่
#
# admission เพิ่มเข้ามาเมื่อ 14 ต.ค. 2569 — เดิมถูกกันไว้ด้วยเหตุผลเรื่องขอบเขตของคำตอบ ไม่ใช่ข้อมูลผิด
# (docs/MKO_PHASE2_FINAL_SHADOW_VALIDATION.md ข้อ B): รายการคุณสมบัติจากหัวข้อเดียวของ มคอ.2 อ่านได้ว่าเป็น
# เงื่อนไขครบถ้วนในการสมัคร ขณะที่เล่มเดียวกันมีเกณฑ์อื่นอยู่หัวข้ออื่นด้วย · ข้อนั้นถูกปิดด้วยสองอย่างใน
# curriculum_facts._compose: (1) ต่อท้ายด้วยหมายเหตุบอกขอบเขตว่าเป็นหัวข้อหนึ่งของเล่มหลักสูตร ไม่ใช่
# ประกาศรับสมัครของปีปัจจุบัน และมหาวิทยาลัยอาจมีเงื่อนไขเพิ่ม (2) ตอบแยกทุกฉบับที่มีข้อมูลเมื่อไม่ระบุปี
# พร้อมบอกฉบับที่ยังไม่มีข้อมูลที่ผ่านการตรวจ
#
# เหตุที่ย้ายมาเส้นทางฐานข้อมูลดีกว่าปล่อยให้ RAG ตอบ: วัดเมื่อ 14 ต.ค. 2569 (ข้อ r1-07 ของชุด 37 ข้อ
# 13 รอบ) คำตอบจาก RAG ไม่ครบ 3/13 รอบ และ 1/13 รอบดึงเงื่อนไขจากภาคผนวกข้อบังคับมหาวิทยาลัย
# (it66.pdf หน้า 161 เรื่องประวัติอาชญากรรม) มาตอบแทนคุณสมบัติของหลักสูตร · ข้อมูลที่ตรวจรับแล้ว
# ของ IT 2566 มีครบ 3 ข้อจาก it66.pdf หน้า 16 โดยผู้ตรวจเป็นคน (human:project-owner)
USER_FACING_FIELDS = frozenset({"total_credits", "edition_year", "careers", "objectives", "admission"})

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


@dataclass(frozen=True)
class ServedAnswer:
    """คำตอบจากฐานข้อมูล พร้อมที่มาของเอกสารสำหรับปุ่มเปิดเอกสารต้นฉบับ"""

    answer: str
    document_id: str | None = None
    page_start: int | None = None
    # ที่มาของทุกฉบับที่คำตอบนี้อ้างถึง ต่างจาก document_id/page_start ด้านบนที่มีค่า
    # เฉพาะคำตอบฉบับเดียว (ปุ่มเปิดเอกสารแสดงได้ปุ่มเดียว) รายการนี้มีครบทุกฉบับ
    # จึงใช้ตรวจความถูกต้องของแหล่งอ้างอิงได้แม้คำตอบครอบหลายฉบับ
    sources: tuple[dict, ...] = ()


def _source_of(result) -> tuple[str | None, int | None]:
    """
    เอกสารต้นฉบับของคำตอบนี้ — บอกได้เมื่อคำตอบอ้างถึงฉบับเดียวเท่านั้น

    คำตอบบางแบบครอบหลายฉบับ เช่น "มีหลักสูตรฉบับ พ.ศ. 2569 และ พ.ศ. 2564" ซึ่งมีที่มา
    สองเล่ม การเลือกเล่มใดเล่มหนึ่งมาเป็นปุ่มเดียวจะชี้ผู้ใช้ไปผิดเล่มครึ่งหนึ่งของกรณี
    จึงไม่บอกที่มาเลยดีกว่า (หน้าเว็บจะไม่แสดงปุ่ม)
    """
    if len(result.facts) != 1:
        return None, None
    source = result.facts[0].source
    if source is None:
        return None, None
    return source.document_id, source.page_start


def _sources_of(result) -> tuple[dict, ...]:
    """
    ที่มาของทุกฉบับที่คำตอบนี้อ้างถึง — เรียงตามลำดับที่ปรากฏในคำตอบ

    มีไว้ให้ตรวจสอบแหล่งอ้างอิงได้ ไม่ได้ใช้ตัดสินหรือเปลี่ยนข้อความคำตอบ
    คำตอบที่อ้างถึงสองฉบับจะได้สองรายการ ต่างจาก _source_of ที่คืน None ในกรณีนั้น
    ใส่ course_id และชื่อหลักสูตรมาด้วย เพราะชื่อไฟล์อย่างเดียวแยกฉบับที่หน่วยกิต
    เท่ากันไม่ได้ (วิทยาการคอมพิวเตอร์ 2561 กับ 2566 เป็น 130 เท่ากันทั้งคู่)
    """
    out = []
    for f in result.facts:
        if f.source is None:
            continue
        out.append({
            "course_id": f.course_id,
            "course_title": f.course_title,
            "file": f.source.file,
            "page_start": f.source.page_start,
            "page_end": f.source.page_end,
            "document_id": f.source.document_id,
        })
    return tuple(out)


def servable_result(db: Session, asked: str):
    """ผลจากฐานข้อมูลที่ใช้ตอบผู้ใช้ได้ (FactsResult) หรือ None = ต้องใช้ RAG"""
    intent = detect(db, asked)
    if intent.route != STRUCTURED or intent.field not in USER_FACING_FIELDS:
        return None
    result = lookup(db, intent)
    if result.status != ANSWERED or not (result.answer or "").strip():
        return None
    return result


def admission_gap(db: Session, asked: str) -> str | None:
    """
    คำถามคุณสมบัติผู้เข้าศึกษาที่ชั้นข้อมูลที่ตรวจรับแล้วตอบไม่ได้ -> ข้อความที่ระบุชัด หรือ None

    ทำไมไม่ปล่อยให้เส้นทางเอกสารตอบเหมือนหัวข้ออื่น
    ------------------------------------------------
    เล่ม มคอ.2 เย็บภาคผนวกข้อบังคับของมหาวิทยาลัยไว้ท้ายเล่ม (เรื่องผู้มีสิทธิ์สมัคร
    ประวัติอาชญากรรม โรคติดต่อ) ซึ่งใช้กับทุกหลักสูตร ไม่ใช่คุณสมบัติของหลักสูตรนี้
    การค้นเอกสารหยิบหน้าเหล่านั้นมาได้โดยชอบเพราะอยู่ในเล่มเดียวกัน แล้วคำตอบจะกลายเป็น
    เงื่อนไขทั่วไปที่ดูเหมือนเป็นของหลักสูตร — วัดจริงเมื่อ 14 ต.ค. 2569 (ข้อ r1-07
    13 รอบ): 1 รอบดึง it66.pdf หน้า 161 มาตอบ และ 3 รอบตอบไม่ครบ
    (docs/MKO_PHASE2_FINAL_SHADOW_VALIDATION.md ข้อ A2/A3/A4 ยืนยันว่าหน้าภาคผนวกชุดนี้
    อยู่ใน 8 ของ 10 เล่มปริญญาตรี)

    หัวข้อนี้เป็นเงื่อนไขที่ผู้ใช้เอาไปตัดสินใจสมัคร การบอกว่า "ยังไม่พบในข้อมูลของระบบ"
    จึงถูกต้องกว่าการตอบด้วยเงื่อนไขของมหาวิทยาลัยที่ไม่ได้ผูกกับหลักสูตร · ด่านนี้ทำงาน
    เฉพาะเมื่อระบุหลักสูตรได้แล้วเท่านั้น คำถามลอย ๆ ยังไหลไปด่านถามกลับตามเดิม
    """
    intent = detect(db, asked)
    if intent.field != "admission":
        return None
    # ชื่อสาขาที่มีทั้งปริญญาโทและเอก: routing ไม่เลือกระดับแทนผู้ใช้ (reason=multiple_degree_levels)
    # เดิมไหลไปเส้นทางเอกสารซึ่งหยิบเล่มใดเล่มหนึ่งมาตอบ · ถามกลับตรง ๆ ดีกว่าเดาให้
    if intent.reason == "multiple_degree_levels":
        return ("ชื่อสาขานี้มีหลายระดับปริญญาในข้อมูลของระบบครับ "
                "ระบุระดับ (ปริญญาตรี ปริญญาโท หรือปริญญาเอก) แล้วผมจะตอบคุณสมบัติผู้เข้าศึกษาของระดับนั้นให้")
    if intent.route != STRUCTURED or not intent.course_ids:
        return None
    result = lookup(db, intent)
    if result.status == ANSWERED and (result.answer or "").strip():
        return None   # ตอบได้อยู่แล้ว — ด่านตอบจากฐานจัดการไปก่อนหน้านี้
    note = (result.note or "").strip()
    programme = intent.programme or "หลักสูตรนี้"
    if "หลายระดับปริญญา" in note:
        return f"{note}ครับ แล้วผมจะตอบคุณสมบัติผู้เข้าศึกษาของระดับนั้นให้"
    if note.startswith("ไม่มีหลักสูตรฉบับ"):
        return (f"{note} ในข้อมูลของระบบครับ "
                f"ระบุปีของฉบับที่มีอยู่ หรือถามโดยไม่ระบุปีเพื่อดูฉบับที่ระบบมีข้อมูล")
    # ระบุฉบับที่ถามให้ชัด และบอกฉบับที่ระบบมีข้อมูล — ไม่ให้เข้าใจว่าทั้งสาขาไม่มีข้อมูลเลย
    # (IT ฉบับ 2561 ยังไม่มี แต่ฉบับ 2566 มีครบสามข้อ)
    edition = f" ฉบับ พ.ศ. {intent.year_be}" if intent.year_be else ""
    hint = ""
    if intent.year_be is not None:
        wider = lookup(db, replace(intent, year_be=None))
        have = [f.course_title for f in wider.facts if f.items] if wider.status == ANSWERED else []
        if have:
            hint = " ฉบับที่ระบบมีข้อมูลคือ " + " และ ".join(have) + " ถามฉบับนั้นได้ · "
    return (f"ยังไม่พบข้อมูลคุณสมบัติผู้เข้าศึกษาของ{programme}{edition} ที่ผ่านการตรวจในข้อมูลของระบบครับ\n"
            f"ผมไม่ตอบจากข้อบังคับทั่วไปของมหาวิทยาลัยที่แนบไว้ท้ายเล่มหลักสูตร "
            f"เพราะนั่นไม่ใช่คุณสมบัติเฉพาะของหลักสูตรนี้ ·{hint or ' '}"
            f"สอบถามฝ่ายวิชาการของคณะหรือดูประกาศรับสมัครของมหาวิทยาลัยได้")


# ชื่อหัวข้อที่ผู้ใช้อ่านรู้เรื่อง ใช้บอกว่าส่วนไหนของคำถามยังตอบจากข้อมูลไม่ได้
_FIELD_LABEL = {
    "total_credits": "จำนวนหน่วยกิต",
    "edition_year": "ปีของหลักสูตร",
    "careers": "อาชีพหลังสำเร็จการศึกษา",
    "objectives": "วัตถุประสงค์ของหลักสูตร",
    "admission": "คุณสมบัติผู้สมัคร",
}


def servable_results(db: Session, asked: str) -> tuple[list[FactsResult], list[str]]:
    """
    ผลจากฐานข้อมูลของคำถามนี้ · คืน (ผลที่ตอบได้เรียงตามที่ถาม, หัวข้อที่ตอบจากฐานไม่ได้)

    คำถามหัวข้อเดียวได้ผลหนึ่งรายการเหมือนเดิมทุกประการ

    คำถามหลายหัวข้อของหลักสูตรเดียว ("เรียนกี่หน่วยกิต และจบไปทำงานอะไรได้บ้าง")
    เดิม detect() คืน multiple_fields แล้วส่งทั้งคำถามไปเส้นทางเอกสาร ทั้งที่ข้อมูล
    ที่ตรวจรับแล้วมีครบทั้งสองหัวข้อ ผลคือคำถามแบบนี้พึ่งโมเดลทั้งหมด
    ที่นี่จึงถามฐานทีละหัวข้อโดยตัดวลีของหัวข้ออื่นออก แล้วต่อคำตอบเข้าด้วยกัน

    หัวข้อที่ตอบไม่ได้จะถูกคืนออกไปให้ผู้เรียกบอกผู้ใช้ชัด ๆ ไม่ใช่หายไปเงียบ ๆ
    ถ้ามีหัวข้อที่ไม่เปิดให้ตอบจากฐานปนอยู่ (หัวข้อที่ไม่อยู่ใน USER_FACING_FIELDS เช่น
    รายวิชาหรือโครงสร้างหลักสูตร) จะไม่ตอบจากฐานเลย เพื่อไม่ให้ผู้ใช้ได้คำตอบครึ่งเดียว
    โดยไม่รู้ว่าอีกครึ่งถูกข้าม
    """
    intent = detect(db, asked)
    if intent.route == STRUCTURED:
        if intent.field not in USER_FACING_FIELDS:
            return [], []
        result = lookup(db, intent)
        if result.status != ANSWERED or not (result.answer or "").strip():
            return [], []
        return [result], []

    if intent.reason != "multiple_fields":
        return [], []


    fields = matched_fields(db, asked)
    if len(fields) < 2 or any(f not in USER_FACING_FIELDS for f in fields):
        return [], []

    got: list[FactsResult] = []
    missing: list[str] = []
    for field in fields:
        sub = only_field(asked, field)
        sub_intent = detect(db, sub)
        # ยืนยันด้วย detect() อีกครั้ง ไม่เชื่อการตัดวลีลอย ๆ — ถ้าตัดแล้วชั้นข้อมูล
        # ยังไม่รับ หรือได้หัวข้ออื่น ให้ถือว่าหัวข้อนี้ตอบจากฐานไม่ได้
        if sub_intent.route != STRUCTURED or sub_intent.field != field:
            missing.append(field)
            continue
        result = lookup(db, sub_intent)
        if result.status != ANSWERED or not (result.answer or "").strip():
            missing.append(field)
            continue
        got.append(result)
    return (got, missing) if got else ([], [])


def compare_results(db: Session, asked: str) -> tuple[str, list[FactsResult]] | None:
    """
    คำตอบเทียบข้อเท็จจริงสองฝั่งจากฐาน · คืน (ข้อความคำตอบ, ผลแต่ละฝั่ง) หรือ None

    ทำไมต้องมี: "ฉบับ 2561 กับ 2566 หน่วยกิตต่างกันไหม" ฐานมีค่าทั้งสองฝั่งครบ แต่
    detect() ติดคำเชิงเทียบ (_NARRATIVE) และ multiple_years จึงไม่รับ แล้วเส้นทาง
    เอกสารตอบว่าไม่พบข้อมูล — วัดจากชุด 37 ข้อ (c1-02) เมื่อ 14 ต.ค. 2569

    **ห้ามสรุปว่าหลักสูตรเหมือนกันเพราะหน่วยกิตเท่ากัน** คำตอบจึงบอกเท่าที่เทียบได้
    (ค่าของหัวข้อที่ถาม) แล้วกำกับไว้ว่าเท่ากันเฉพาะตัวเลขนี้ ไม่ใช่ทั้งหลักสูตร
    """
    sides = comparison_sides(db, asked)
    if sides is None:
        return None
    field, questions = sides
    if field not in USER_FACING_FIELDS:
        return None

    results: list[FactsResult] = []
    for q in questions:
        intent = detect(db, q)
        if intent.route != STRUCTURED or intent.field != field:
            return None
        result = lookup(db, intent)
        if result.status != ANSWERED or not (result.answer or "").strip():
            return None
        results.append(result)
    if len(results) != 2:
        return None

    label = _FIELD_LABEL.get(field, field)
    lines = [f"เทียบ{label}", ""]
    lines += [r.answer.strip() for r in results]

    # เทียบได้เป็นตัวเลขก็บอกตรง ๆ ว่าเท่ากันหรือไม่ · ถ้าฝั่งใดมีหลายค่า (เช่นหลายฉบับ
    # ในฝั่งเดียว) ไม่สรุปตัวเลขให้ เพราะการเลือกค่าใดมาเทียบคือการตัดสินแทนผู้ใช้
    numbers = [sorted({f.value_int for f in r.facts if f.value_int is not None})
               for r in results]
    if all(len(n) == 1 for n in numbers):
        a, b = numbers[0][0], numbers[1][0]
        lines.append("")
        if a == b:
            lines.append(f"สรุป: {label}เท่ากันทั้งสองฝั่ง ({a})")
            lines.append("หมายเหตุ: ตัวเลขนี้เท่ากันไม่ได้หมายความว่ารายวิชา โครงสร้าง "
                         "หรือเนื้อหาของหลักสูตรเหมือนกัน ถามรายวิชาของแต่ละฝั่งแยกได้")
        else:
            lines.append(f"สรุป: {label}ต่างกัน {abs(a - b)} (ฝั่งละ {a} และ {b})")
    return "\n".join(lines), results


def servable_answer(db: Session, asked: str) -> str | None:
    """
    คำตอบจากฐานข้อมูลที่ใช้ตอบผู้ใช้ได้ หรือ None = ต้องตอบด้วย RAG

    ใช้ detect / lookup ตัวเดียวกับโหมด shadow ไม่ได้ตีความคำถามหรือเรียบเรียงคำตอบใหม่
    ตรวจ field ก่อน lookup เพื่อให้ field ที่ไม่อยู่ใน USER_FACING_FIELDS ไม่ถูกดึงข้อมูลมาตอบเลย
    """
    result = servable_result(db, asked)
    return result.answer if result is not None else None


def structured_answer(*, question: str, interpreted: str | None) -> ServedAnswer | None:
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
                asked = interpreted or question
                # ด่านเทียบสองฝั่งมาก่อน เพราะคำถามเทียบมีหัวข้อเดียวแต่สองฝั่ง
                # servable_results() จะไม่รับ (detect คืน multiple_years หรือ narrative)
                compared = compare_results(db, asked)
                if compared is not None:
                    answer, results = compared
                    missing: list[str] = []
                else:
                    results, missing = servable_results(db, asked)
                    if not results:
                        return None
                    answer = "\n\n".join(r.answer for r in results)
                if missing:
                    # บอกชัดว่าส่วนไหนของคำถามยังไม่ได้ตอบ ไม่ปล่อยให้เข้าใจว่าตอบครบ
                    #
                    # ไม่สัญญาว่าจะไปค้นเอกสารให้ถ้าหัวข้อที่ขาดคือคุณสมบัติผู้เข้าศึกษา เพราะด่าน
                    # admission_gap ไม่ตอบหัวข้อนี้จากเอกสาร (เหตุผลอยู่ในฟังก์ชันนั้น) การสัญญา
                    # แล้วไม่ทำคือการบอกผู้ใช้ไม่ตรงกับพฤติกรรมจริงของระบบ
                    labels = " และ ".join(_FIELD_LABEL.get(f, f) for f in missing)
                    tail = ("สอบถามฝ่ายวิชาการของคณะหรือดูประกาศรับสมัครของมหาวิทยาลัยได้"
                            if missing == ["admission"] else
                            "ถามแยกอีกครั้งได้ เดี๋ยวผมค้นจากเอกสารหลักสูตรให้")
                    answer += f"\n\nยังไม่พบข้อมูล{labels}ที่ผ่านการตรวจของหลักสูตรนี้ในระบบครับ {tail}"
                document_id, page_start = _source_of(results[0])
                seen: set[tuple] = set()
                sources: list[dict] = []
                for r in results:
                    for s in _sources_of(r):
                        key = tuple(sorted(s.items()))
                        if key not in seen:
                            seen.add(key)
                            sources.append(s)
                return ServedAnswer(answer, document_id, page_start, tuple(sources))
            finally:
                db.rollback()
    except Exception:  # noqa: BLE001 — ข้อผิดพลาดของ structured ห้ามทำให้ตอบผู้ใช้ไม่ได้
        logger.warning("หาคำตอบจากฐานข้อมูลไม่สำเร็จ — ใช้คำตอบ RAG แทน", exc_info=True)
        return None


def structured_reply(*, question: str, interpreted: str | None) -> str | None:
    """ข้อความคำตอบอย่างเดียว — คงไว้ให้ผู้เรียกเดิมที่ไม่ต้องการที่มาของเอกสาร"""
    served = structured_answer(question=question, interpreted=interpreted)
    return served.answer if served is not None else None


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
