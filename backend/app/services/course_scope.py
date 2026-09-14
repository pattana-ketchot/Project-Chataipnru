"""
ระบุว่าคำถามถามถึงหลักสูตรใด แล้วตัดชื่อหลักสูตรออกจากข้อความที่ใช้ค้นหา

ปัญหาที่แก้
-----------
คลังเอกสารเป็นเอกสาร 18 เล่มที่แยกจากกันชัดเจน และคำถามส่วนใหญ่เจาะจงเล่มใดเล่มหนึ่ง
เมื่อค้นทั้งคลังพร้อมกันด้วยคำถามที่มีชื่อหลักสูตรอยู่ด้วย ชื่อหลักสูตรจะครอบงำเวกเตอร์
จนไปแมตช์กับ chunk ทุกก้อนที่เอ่ยชื่อนั้น (ซึ่งมีหลายร้อยก้อน รวมถึงภาคผนวกที่เป็น
ตารางประเมินความพึงพอใจ) แทนที่จะแมตช์เนื้อหาที่ถามถึงจริง

วัดจากคำถาม "สาขาวิชาเทคโนโลยีการจัดการสุขภาพ เรียนจบทำอาชีพไหนได้บ้าง"
กับ chunk ที่มีรายชื่ออาชีพจริงในเอกสาร ht61 หน้า 7

    ค้นทั้งคลัง ด้วยคำถามเต็ม              อันดับแย่กว่า 200
    ค้นเฉพาะ ht61 ด้วยคำถามเต็ม            อันดับแย่กว่า 60
    ค้นเฉพาะ ht61 ตัดชื่อหลักสูตรออก       อันดับ 3

วิธีทำ
------
จับคู่ชื่อหลักสูตรจากตาราง courses กับข้อความคำถาม ถ้าเจอให้จำกัดขอบเขตการค้นหา
ไว้ที่หลักสูตรนั้น (รวมทุกปีการศึกษาของหลักสูตรเดียวกัน) แล้วตัดชื่อออกจากข้อความค้นหา
ถ้าไม่เจอก็ค้นทั้งคลังตามเดิม
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.course import Course
from app.services.query_expansion import ALIASES, _alias_present


@dataclass
class CourseScope:
    course_ids: list[uuid.UUID]
    matched_name: str
    search_text: str


# คำห่อที่ไม่มีความหมายในการจัดอันดับเมื่อรู้แล้วว่าถามถึงหลักสูตรใด
#
# แยกเป็นสองชั้นโดยตั้งใจ เพราะเคยตัด "หลักสูตร" ทุกตำแหน่งแล้วพัง:
# คำถาม "ใครเป็นอาจารย์ผู้รับผิดชอบหลักสูตรวิทยาการคอมพิวเตอร์บ้าง" กลายเป็น
# "ใครเป็นอาจารย์ผู้รับผิดชอบ บ้าง" ซึ่งทำลายศัพท์เฉพาะ "อาจารย์ผู้รับผิดชอบ
# หลักสูตร" ที่ใช้ในเอกสาร มคอ.2 จนค้นรายชื่ออาจารย์ไม่เจอ
#
# ชื่อปริญญา (ลงท้าย "บัณฑิต") และคำว่า "สาขาวิชา/สาขา" เป็นคำห่อเสมอ ตัดได้ทุกตำแหน่ง
_DEGREE_AND_WRAPPER = re.compile(r"([ก-๙]*บัณฑิต|สาขาวิชา|สาขา|วิชาเอก)")
# ส่วน "หลักสูตร" ตัดเฉพาะเมื่ออยู่ต้นประโยค (เป็นคำนำที่ผู้ใช้พิมพ์นำหน้าชื่อ)
# ถ้าอยู่กลางประโยคมักเป็นส่วนของศัพท์เฉพาะ จึงต้องเก็บไว้
_LEADING_COURSE_WORD = re.compile(r"^หลักสูตร\s*")
_EXTRA_SPACE = re.compile(r"\s{2,}")
# "พ.ศ. 2566" หรือเลขปีลอยๆ — ใช้เลือกเล่มแล้วจึงตัดออกจากคำค้น (ดู _build)
_YEAR_PHRASE = re.compile(r"(พ\.?\s*ศ\.?\s*)?25\d{2}")

# ความยาวขั้นต่ำของข้อความที่เหลือหลังตัดชื่อหลักสูตร ถ้าสั้นกว่านี้แปลว่าคำถามแทบไม่มี
# เนื้อหาอื่นเลย (เช่น "หลักสูตรวิทยาการคอมพิวเตอร์") การค้นด้วยข้อความที่เหลือจะไร้ความหมาย
_MIN_REMAINDER = 8


def _distinctive_name(title: str) -> str:
    """
    ดึงชื่อเฉพาะของหลักสูตรออกจากชื่อเต็ม

    'หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาเทคโนโลยีการจัดการสุขภาพ (พ.ศ. 2561)'
        -> 'เทคโนโลยีการจัดการสุขภาพ'
    'หลักสูตรการแพทย์แผนไทยประยุกต์บัณฑิต (พ.ศ. 2560)'
        -> 'การแพทย์แผนไทยประยุกต์'
    """
    name = re.sub(r"\s*\(.*?\)\s*$", "", title).strip()
    if "สาขาวิชา" in name:
        return name.split("สาขาวิชา", 1)[1].strip()
    # ไม่มีคำว่าสาขาวิชา แปลว่าชื่อปริญญาคือชื่อหลักสูตร ตัดคำห่อออก
    return re.sub(r"^หลักสูตร", "", name).replace("บัณฑิต", "").strip()


def _year_in(text: str) -> str | None:
    """ดึงปีพุทธศักราชจากข้อความ คืน None ถ้าไม่มี"""
    m = re.search(r"25\d{2}", text)
    return m.group(0) if m else None


def _narrow_by_year(
    ids: list[uuid.UUID], titles: dict[uuid.UUID, str], question: str
) -> list[uuid.UUID]:
    """
    ถ้าคำถามระบุปีการศึกษา ให้เหลือเฉพาะเล่มของปีนั้น

    คลังนี้มี 4 หลักสูตรที่มีสองปีการศึกษา (การแพทย์แผนไทยประยุกต์ 2560/2565,
    วิทยาการคอมพิวเตอร์ 2561/2566, เทคโนโลยีสารสนเทศ 2561/2566,
    วิทยาศาสตร์เครื่องสำอาง 2561/2566) เดิมจับคู่จากชื่ออย่างเดียวจึงดึงทั้งสองปี
    มาปนกัน เมื่อผู้ใช้ถามเจาะจงปี โมเดลจะเห็นเนื้อหาของอีกปีแล้วตอบว่า
    "ข้อมูลที่มีเป็นของอีกปีหนึ่ง" ทั้งที่เอกสารปีที่ถามมีอยู่ในคลัง

    ถ้าปีที่ระบุไม่ตรงกับเล่มใดเลย ให้คงรายการเดิมไว้ ดีกว่าตัดจนไม่เหลืออะไรค้น
    """
    year = _year_in(question)
    if year is None:
        return ids
    matched = [cid for cid in ids if year in titles.get(cid, "")]
    return matched or ids


def resolve_scope(db: Session, question: str) -> CourseScope | None:
    """คืนขอบเขตหลักสูตรถ้าระบุได้ มิฉะนั้นคืน None (แปลว่าให้ค้นทั้งคลัง)"""
    courses = db.scalars(select(Course).where(Course.is_active.is_(True))).all()
    titles = {c.id: c.title for c in courses}

    # ชื่อเฉพาะ -> รายการ course id (หลักสูตรเดียวกันหลายปีจะรวมอยู่ด้วยกัน)
    by_name: dict[str, list[uuid.UUID]] = {}
    for c in courses:
        by_name.setdefault(_distinctive_name(c.title), []).append(c.id)

    lowered = question.lower()

    # หาชื่อที่ปรากฏในคำถามโดยตรง เลือกชื่อที่ยาวที่สุดก่อนเพื่อไม่ให้ชื่อสั้นที่เป็น
    # ส่วนหนึ่งของชื่อยาวชนะ (เช่น 'คณิตศาสตร์' อยู่ใน 'คหกรรมศาสตร์' ไม่ได้ แต่กันไว้)
    for name in sorted(by_name, key=len, reverse=True):
        if name and name.lower() in lowered:
            return _build(_narrow_by_year(by_name[name], titles, question), name, question)

    # ไม่เจอชื่อตรงๆ ลองผ่านคำย่อ เช่น 'วิทคอม' -> 'วิทยาการคอมพิวเตอร์'
    #
    # คำย่ออักษรโรมันต้องเทียบแบบมีขอบเขตคำ เดิมเทียบแค่ว่ามีอยู่ในข้อความ คำว่า "it" จึงไป
    # ตรงกับกลางคำ "Cybersecurity" และ "digital" แล้วจำกัดการค้นไว้ที่เทคโนโลยีสารสนเทศ
    # ทั้งที่ผู้ใช้กำลังคุยเรื่องวิทยาการคอมพิวเตอร์อยู่ (เจอจริงในบทสนทนาหลายเทิร์นบนหน้าเว็บ)
    for alias, full in ALIASES.items():
        if not _alias_present(alias, lowered):
            continue
        for name in by_name:
            if name and name in full:
                # ตัดคำย่อออกจากคำถามแทนชื่อเต็ม เพราะในคำถามมีแค่คำย่อ
                ids = _narrow_by_year(by_name[name], titles, question)
                return _build(ids, name, question, strip=alias)
    return None


def resolve_scopes(db: Session, question: str) -> list[CourseScope]:
    """
    ขอบเขตของ "ทุก" หลักสูตรที่คำถามเอ่ยถึง คืนรายการว่างถ้าไม่เอ่ยถึงเลย

    resolve_scope คืนหลักสูตรแรกที่เจอหลักสูตรเดียว ซึ่งถูกสำหรับคำถามส่วนใหญ่ แต่คำถามที่เทียบ
    สองหลักสูตรจะถูกค้นเฉพาะเล่มแรก เจอบนหน้าเว็บจริง: "วิทยาการคอมพิวเตอร์กับเทคโนโลยีสารสนเทศ
    ต่างกันอย่างไร ..." ได้เนื้อหาของวิทยาการคอมพิวเตอร์ 25 ชิ้น เทคโนโลยีสารสนเทศ 0 ชิ้น และคำค้นยังมี
    ชื่อหลักสูตรที่สองค้างอยู่ ด่านตรวจเอกสารจึงตัดสินว่าตอบไม่ได้

    ทุกขอบเขตใช้คำค้นเดียวกันที่ตัดชื่อของทุกหลักสูตรออกแล้ว เทียบชื่อเต็มก่อน (ยาวก่อนสั้น) แล้วค่อย
    ดูคำย่อในข้อความที่เหลือ ด้วยกติกาเดียวกับ resolve_scope
    """
    courses = db.scalars(select(Course).where(Course.is_active.is_(True))).all()
    titles = {c.id: c.title for c in courses}
    by_name: dict[str, list[uuid.UUID]] = {}
    for c in courses:
        by_name.setdefault(_distinctive_name(c.title), []).append(c.id)

    remaining = question.lower()
    found: list[tuple[str, str]] = []  # (ชื่อเฉพาะ, ข้อความในคำถามที่ต้องตัดออกจากคำค้น)
    for name in sorted(by_name, key=len, reverse=True):
        if name and name.lower() in remaining:
            found.append((name, name))
            remaining = remaining.replace(name.lower(), " ")
    for alias, full in ALIASES.items():
        if not _alias_present(alias, remaining):
            continue
        for name in by_name:
            if name and name in full and all(name != f for f, _ in found):
                found.append((name, alias))
        remaining = re.sub(rf"(?<![a-z0-9]){re.escape(alias.lower())}(?![a-z0-9])", " ", remaining)

    search_text = _search_text(question, [target for _, target in found])
    return [
        CourseScope(course_ids=_narrow_by_year(by_name[name], titles, question), matched_name=name, search_text=search_text)
        for name, _ in found
    ]


def _build(ids: list[uuid.UUID], name: str, question: str, strip: str | None = None) -> CourseScope:
    return CourseScope(course_ids=ids, matched_name=name, search_text=_search_text(question, [strip or name]))


def _search_text(question: str, targets: list[str]) -> str:
    """คำค้นหลังตัดชื่อหลักสูตรหรือคำย่อที่ระบุ ปีการศึกษา และคำห่อออก"""
    remainder = question
    for target in targets:
        # ตัดแบบไม่สนตัวพิมพ์เล็กใหญ่ เพราะคำย่ออาจเป็นอักษรโรมัน
        remainder = re.sub(re.escape(target), " ", remainder, flags=re.IGNORECASE)
    # ปีการศึกษาทำหน้าที่เลือกเล่มไปแล้ว เหลือไว้ในคำค้นมีแต่โทษ เพราะจะไปจับคู่กับ
    # หน้าปกและมติอนุมัติหลักสูตรที่เอ่ยปีซ้ำๆ แทนที่จะจับคู่เนื้อหาที่ถามถึง
    remainder = _YEAR_PHRASE.sub(" ", remainder)
    remainder = _DEGREE_AND_WRAPPER.sub(" ", remainder)
    remainder = _EXTRA_SPACE.sub(" ", remainder).strip()
    remainder = _LEADING_COURSE_WORD.sub("", remainder).strip()

    # เหลือน้อยเกินไปแปลว่าคำถามคือชื่อหลักสูตรล้วน ใช้ข้อความเดิมค้นต่อไป
    return remainder if len(remainder) >= _MIN_REMAINDER else question


# ตำแหน่งที่คำตอบของผู้ช่วยเอ่ยชื่อหลักสูตร: ตามหลังคำนำหน้า หรือเป็นหัวรายการ
_TITLE_PREFIX = r"(?:สาขาวิชา|สาขา|หลักสูตร)\s*"
_LIST_ITEM = r"^[ \t]*(?:\d+\.|[-•*])[ \t]*"


def programmes_named(text: str, names: list[str], *, from_assistant: bool) -> list[str]:
    """
    ชื่อหลักสูตรทุกตัวที่ข้อความนี้เอ่ยถึง ไม่ซ้ำ — ใช้หาว่าบทสนทนากำลังคุยถึงสาขาไหน

    ข้อความของผู้ใช้เทียบแบบหลวม ทั้งชื่อเต็มและคำย่อ เพราะผู้ใช้พิมพ์ชื่อลอยๆ เช่น
    "อยากเรียน วิทคอม"

    ข้อความของผู้ช่วยนับเฉพาะชื่อที่อยู่ในตำแหน่งชื่อหลักสูตร คือตามหลัง "สาขาวิชา" "สาขา"
    "หลักสูตร" หรือเป็นหัวรายการที่ชื่อจบบรรทัดหรือตามด้วยวงเล็บ เพราะคำตอบของผู้ช่วยมีชื่อ
    รายวิชาปนอยู่มาก เช่น "คณิตศาสตร์ไม่ต่อเนื่อง" ในคำตอบเรื่องวิทยาการคอมพิวเตอร์ ถ้านับแบบ
    หลวมจะเข้าใจผิดว่าคุยถึงสองสาขา แล้วเลิกหาสาขาที่กำลังคุยทั้งที่ชัดเจนอยู่
    """
    found: list[str] = []
    ordered = sorted(names, key=len, reverse=True)
    if from_assistant:
        remaining = text
        for name in ordered:
            pattern = re.compile(
                rf"{_TITLE_PREFIX}{re.escape(name)}|{_LIST_ITEM}{re.escape(name)}(?=[ \t]*(?:\(|$))",
                re.MULTILINE,
            )
            if pattern.search(remaining):
                found.append(name)
                remaining = pattern.sub(" ", remaining)
        return found

    lowered = text.lower()
    for name in ordered:
        if name.lower() in lowered:
            found.append(name)
            lowered = lowered.replace(name.lower(), " ")
    for alias, full in ALIASES.items():
        if _alias_present(alias, lowered):
            found.extend(n for n in ordered if n in full and n not in found)
    return found


def without_programme_names(text: str, names: list[str]) -> str:
    """
    ข้อความที่เหลือหลังตัดชื่อหลักสูตรและคำย่อทุกตัวที่ผู้ใช้เอ่ยถึงออก (ตัวพิมพ์เล็ก)

    ใช้ดูว่าข้อความมีเนื้อหาอื่นนอกจากชื่อสาขาหรือไม่ เทียบชื่อแบบเดียวกับ programmes_named
    เพื่อให้สองฟังก์ชันเห็นชื่อชุดเดียวกันเสมอ
    """
    lowered = text.lower()
    for name in sorted(names, key=len, reverse=True):
        lowered = lowered.replace(name.lower(), " ")
    for alias in sorted(ALIASES, key=len, reverse=True):
        if _alias_present(alias, lowered):
            lowered = re.sub(rf"(?<![a-z0-9]){re.escape(alias.lower())}(?![a-z0-9])", " ", lowered)
    return lowered
