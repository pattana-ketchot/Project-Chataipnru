"""
คำถามต่อเนื่องที่ผู้ใช้เปลี่ยนเฉพาะหลักสูตรหรือปีของหลักสูตร เช่น "แล้ว <ชื่อหลักสูตร> ล่ะ" หรือ "แล้ว พ.ศ. 2564 ล่ะ"

ปัญหาที่แก้ (docs/MKO_PHASE2_SHADOW_EVAL.md ข้อ 4)
---------------------------------------------------
บนหน้าเว็บจริง ถาม "สาขาวิทยาการคอมพิวเตอร์เรียนกี่หน่วยกิต" แล้วต่อด้วย "แล้วคณิตศาสตร์ล่ะ" ระบบตีความเป็น
"สาขาวิทยาการคอมพิวเตอร์เรียนวิชาคณิตศาสตร์อะไรบ้าง" แล้วตอบรายวิชาคณิตศาสตร์ของอีกหลักสูตร ตามรอยได้สามชั้น
  1. ข้อความมีชื่อหลักสูตรอยู่แล้ว ระบบจึงไม่ส่งหลักสูตรที่กำลังคุยให้ขั้นเขียนคำถามใหม่ และข้อความเหลือแต่ชื่อ
     ไม่มีเรื่องที่ถาม ขั้นเขียนคำถามใหม่ต้องเดาเรื่องที่ถามเอง
  2. ชื่อหลักสูตรบางชื่อเป็นชื่อศาสตร์ทั่วไปที่มีรายวิชาชื่อเดียวกัน โมเดลอ่านเป็นชื่อรายวิชา
  3. คำถามที่เขียนใหม่ได้คะแนนค้นหาสูงกว่าจึงถูกเลือก ทั้งที่เปลี่ยนหลักสูตรที่ผู้ใช้เอ่ยเองไปเป็นหลักสูตรอื่น

วิธีทำ
------
- ข้อความที่ตัดชื่อหลักสูตร ปี และคำลงท้าย (แล้ว ล่ะ ครับ ...) ออกแล้วไม่เหลืออะไร คือการเปลี่ยนตัวแปรของคำถามก่อนหน้า
  ประกอบคำถามใหม่ด้วยโค้ดจากคำถามก่อนหน้าที่มีเนื้อหาจริง: เรื่องที่ถามคงเดิม เปลี่ยนเฉพาะหลักสูตรหรือปี ไม่ต้องให้โมเดลเดา
- ข้อความที่มีเนื้อหาอื่นยังให้โมเดลเขียนใหม่ แต่ผลที่เปลี่ยนชุดหลักสูตรที่ผู้ใช้เอ่ยเองต้องถูกทิ้ง (rewrite_keeps_explicit)
  ไม่ว่าคะแนนค้นหาจะสูงกว่าแค่ไหน
- ชื่อหลักสูตรที่ตามหลังคำว่า "วิชา" (ที่ไม่ใช่ "สาขาวิชา") คือชื่อรายวิชา ไม่นับเป็นหลักสูตรที่ผู้ใช้ระบุ

ไม่มีชื่อหลักสูตรหรือประโยคคำถามในไฟล์นี้ ชื่อหลักสูตรมาจากตาราง courses ผ่าน course_scope ทุกครั้ง
"""
from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.course import Course
from app.services.course_scope import _distinctive_name, resolve_scopes, without_programme_names
from app.services.query_expansion import ALIASES, _alias_present
from app.services.structured_intent import years_in

_THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")
# ปีที่ระบุ พร้อมคำนำหน้า พ.ศ./ค.ศ. ถ้ามี
_YEAR_PHRASE = re.compile(r"(?:[พค]\.?\s*ศ\.?\s*)?(?<!\d)(?:25|19|20)\d{2}(?!\d)")
# คำที่ไม่บอกเรื่องที่ถาม: คำเชื่อม คำลงท้าย คำห่อชื่อหลักสูตร และเครื่องหมาย
_FILLER = re.compile(
    r"แล้ว|ล่ะ|หละ|ละ|ครับ|คับ|ค่ะ|คะ|จ้ะ|จ้า|นะ|อ่ะ|อะ|หลักสูตร|สาขาวิชา|สาขา|ฉบับ|ปี|ของ|ด้วย"
    r"|[\s?？!.,ๆ\"'()\[\]:;-]"
)
# ชื่อที่ตามหลัง "วิชา"/"รายวิชา" คือชื่อรายวิชา ส่วน "สาขาวิชา" เป็นคำห่อชื่อหลักสูตร
_SUBJECT_BEFORE = re.compile(r"(?<!สาขา)วิชา\s*$")
_EXTRA_SPACE = re.compile(r"\s{2,}")


def _programme_names(db: Session) -> list[str]:
    courses = db.scalars(select(Course).where(Course.is_active.is_(True))).all()
    return sorted({_distinctive_name(c.title) for c in courses} - {""})


def _residue(text: str, names: list[str]) -> str:
    """ส่วนที่เหลือของข้อความหลังตัดชื่อหลักสูตร คำย่อ ปี และคำที่ไม่บอกเรื่องที่ถามออก"""
    remainder = without_programme_names(text.translate(_THAI_DIGITS), names)
    remainder = _YEAR_PHRASE.sub(" ", remainder)
    return _FILLER.sub("", remainder)


def explicit_programmes(db: Session, text: str) -> list[str]:
    """ชื่อหลักสูตรที่ข้อความระบุในฐานะหลักสูตร (ไม่นับชื่อที่ใช้เป็นชื่อรายวิชา) ตามลำดับที่ course_scope พบ"""
    found = []
    for scope in resolve_scopes(db, text):
        at = text.find(scope.matched_name)
        if at >= 0 and _SUBJECT_BEFORE.search(text[:at]):
            continue
        found.append(scope.matched_name)
    return found


def rewrite_keeps_explicit(db: Session, message: str, rewritten: str) -> bool:
    """คำถามที่เขียนใหม่ต้องถามถึงชุดหลักสูตรเดียวกับที่ผู้ใช้ระบุเองในข้อความล่าสุด ถ้าผู้ใช้ไม่ได้ระบุ ถือว่าผ่าน"""
    explicit = set(explicit_programmes(db, message))
    return not explicit or set(explicit_programmes(db, rewritten)) == explicit


def _base_question(history: list, names: list[str]) -> str | None:
    """คำถามล่าสุดของผู้ใช้ที่มีเรื่องที่ถามจริง ข้ามคำถามที่เปลี่ยนแค่หลักสูตรหรือปี"""
    for turn in reversed(history):
        if turn.role == "user" and _residue(turn.content, names):
            return turn.content
    return None


def _replace_programme(question: str, old: str, new: str) -> str | None:
    if old in question:
        return question.replace(old, new, 1)
    lowered = question.lower()
    for alias, full in sorted(ALIASES.items(), key=lambda item: -len(item[0])):
        if old in full and _alias_present(alias, lowered):
            pattern = rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])" if alias.isascii() else re.escape(alias)
            if m := re.search(pattern, question, flags=re.IGNORECASE):
                return f"{question[:m.start()]}{new}{question[m.end():]}"
    return None


def _without_years(question: str) -> str:
    return _EXTRA_SPACE.sub(" ", _YEAR_PHRASE.sub(" ", question.translate(_THAI_DIGITS))).strip()


def _with_year(question: str, year_be: int, programme: str | None) -> str:
    stripped = _without_years(question)
    phrase = f"พ.ศ. {year_be}"
    if programme and programme in stripped:
        end = stripped.index(programme) + len(programme)
        return _EXTRA_SPACE.sub(" ", f"{stripped[:end]} {phrase} {stripped[end:]}").strip()
    return f"{stripped} {phrase}"


def swap_follow_up(db: Session, history: list, message: str, context_programme: str | None = None) -> str | None:
    """
    คำถามที่ประกอบใหม่เมื่อข้อความล่าสุดเปลี่ยนแค่หลักสูตรหรือปีของคำถามก่อนหน้า คืน None ถ้าไม่ใช่กรณีนี้

    context_programme คือหลักสูตรที่บทสนทนากำลังคุย ใช้เมื่อผู้ใช้เปลี่ยนแค่ปีและคำถามก่อนหน้าไม่ได้เอ่ยชื่อหลักสูตร
    """
    if not history:
        return None
    new_programmes = explicit_programmes(db, message)
    years = years_in(message)
    if not new_programmes and not years:
        return None
    # เปลี่ยนหลายหลักสูตรหรือหลายปีพร้อมกันคือคำถามใหม่ ไม่ใช่การเปลี่ยนตัวแปรตัวเดียว
    if len(new_programmes) > 1 or len(years) > 1:
        return None
    names = _programme_names(db)
    if _residue(message, names):
        return None
    base = _base_question(history, names)
    if base is None:
        return None
    base_programmes = explicit_programmes(db, base)
    # คำถามก่อนหน้าเทียบหลายหลักสูตร: การเปลี่ยนเป็นหลักสูตรเดียวกำกวม ให้ขั้นเขียนคำถามใหม่ตัดสิน
    if len(base_programmes) > 1:
        return None

    question = base
    if new_programmes:
        new = new_programmes[0]
        replaced = _replace_programme(question, base_programmes[0], new) if base_programmes else None
        question = replaced if replaced is not None else f"{question} (หลักสูตร{new})"
        if not years:
            # ปีในคำถามเดิมเป็นฉบับของหลักสูตรเดิม ไม่ใช่ของหลักสูตรใหม่
            question = _without_years(question)
        programme = new
    else:
        programme = base_programmes[0] if base_programmes else context_programme
        if programme is None:
            return None
        if not base_programmes:
            question = f"{question} (หลักสูตร{programme})"
    if years:
        question = _with_year(question, years[0], programme)
    question = _EXTRA_SPACE.sub(" ", question).strip()
    return question if question != message else None
