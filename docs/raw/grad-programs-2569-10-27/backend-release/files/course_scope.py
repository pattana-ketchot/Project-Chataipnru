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


# ระดับปริญญา — อ่านจากชื่อปริญญาในชื่อหลักสูตร ไม่ผูกกับชื่อสาขาใด
#
# ต้องเรียงจากเฉพาะเจาะจงไปกว้าง เพราะ "ดุษฎีบัณฑิต" และ "มหาบัณฑิต" มีคำว่า "บัณฑิต" อยู่ด้วย
# รูปแบบอักษรย่อ (วท.บ. / วท.ม. / ปร.ด.) ใช้ตัวท้ายเป็นตัวบอกระดับ ไม่ชนกับ "พ.ศ." เพราะตัวท้ายคนละตัว
_DEGREE_LEVEL_PATTERNS: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(r"ดุษฎีบัณฑิต|ดุษฏีบัณฑิต|ปริญญาเอก|ป\.\s*เอก|[ก-๙]{1,6}\.\s*ด\."), "doctoral"),
    (re.compile(r"มหาบัณฑิต|ปริญญาโท|ป\.\s*โท|[ก-๙]{1,6}\.\s*ม\."), "master"),
    # "บัณฑิต" ต้องเป็นส่วนท้ายของชื่อปริญญา (มีอักษรไทยนำหน้า) ไม่ใช่คำว่า "บัณฑิต" ลอยๆ ที่แปลว่าผู้จบการศึกษา
    (re.compile(r"[ก-๙]{2,}บัณฑิต|ปริญญาตรี|ป\.\s*ตรี|[ก-๙]{1,6}\.\s*บ\."), "bachelor"),
)


def degree_of_title(title: str) -> str:
    """
    ชื่อปริญญาจากชื่อหลักสูตรในระบบ

    'หลักสูตรวิทยาศาสตรมหาบัณฑิต สาขาวิชาการจัดการเทคโนโลยีการเกษตรฯ (พ.ศ. 2568)' -> 'วิทยาศาสตรมหาบัณฑิต'
    'หลักสูตรการแพทย์แผนไทยประยุกต์บัณฑิต (พ.ศ. 2560)'                          -> 'การแพทย์แผนไทยประยุกต์บัณฑิต'
    """
    name = re.sub(r"\s*\(.*?\)\s*$", "", title).strip()
    head = name.split("สาขาวิชา", 1)[0]
    return re.sub(r"^หลักสูตร", "", head).strip()


def degree_level_of(text: str) -> str | None:
    """ระดับปริญญาที่ข้อความนี้บอก (bachelor / master / doctoral) คืน None ถ้าไม่ได้บอก"""
    for pattern, level in _DEGREE_LEVEL_PATTERNS:
        if pattern.search(text):
            return level
    return None


def requested_degree_level(question: str) -> str | None:
    """ระดับปริญญาที่ผู้ใช้ระบุในคำถาม — ชื่อปริญญา อักษรย่อ หรือคำว่าปริญญาตรี/โท/เอก"""
    return degree_level_of(question)


def degree_levels_of(ids: list[uuid.UUID], titles: dict[uuid.UUID, str]) -> set[str]:
    """ระดับปริญญาทั้งหมดของหลักสูตรชุดนี้ (ชื่อที่อ่านระดับไม่ได้จะไม่ถูกนับ)"""
    return {level for cid in ids if (level := degree_level_of(degree_of_title(titles.get(cid, "")))) is not None}


def _narrow_by_degree(ids: list[uuid.UUID], titles: dict[uuid.UUID, str], question: str) -> list[uuid.UUID]:
    """
    ถ้าคำถามระบุระดับปริญญา ให้เหลือเฉพาะหลักสูตรระดับนั้น

    คลังนี้มีสาขาที่ชื่อสาขาและปีเดียวกันแต่คนละระดับปริญญา (การจัดการเทคโนโลยีการเกษตรและบริหาร
    ทรัพยากรชุมชน พ.ศ. 2568 มีทั้งปริญญาโทและปริญญาเอก) ชื่อเฉพาะของทั้งสองเล่มเท่ากัน และปีก็เท่ากัน
    ตัวกรองเดิมจึงแยกไม่ได้ ผู้ใช้ที่พิมพ์ "วิทยาศาสตรมหาบัณฑิต" มาจะได้เล่มปริญญาเอก

    **ถ้าระดับที่ระบุไม่ตรงกับเล่มใดเลย ต้องคืนรายการว่าง ไม่ใช่คงรายการเดิม**

    ต่างจากการกรองปีโดยเจตนา · เดิมเขียน `matched or ids` เหมือนกันทั้งคู่ แล้ววัดเจอ
    เมื่อ 13 ต.ค. 2569: ถาม "หลักสูตรปริญญาโทการจัดการเทคโนโลยีการเกษตรเรียนกี่หน่วยกิต"
    ได้คำตอบของ **ปริญญาตรี** 130 หน่วยกิต ทั้งที่ปริญญาโทคือ 36 — การถอยไปใช้รายการ
    เดิมคือการตอบคนละระดับปริญญาโดยไม่มีสัญญาณเตือน ซึ่งผิดมากกว่าการไม่ตอบ
    ผู้เรียกต้องเห็นรายการว่างแล้วไปบอกผู้ใช้ว่าไม่มีข้อมูลระดับนั้น
    """
    level = requested_degree_level(question)
    if level is None:
        return ids
    return [cid for cid in ids if degree_level_of(degree_of_title(titles.get(cid, ""))) == level]


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


def _narrow(ids: list[uuid.UUID], titles: dict[uuid.UUID, str], question: str) -> list[uuid.UUID]:
    """จำกัดขอบเขตด้วยสิ่งที่คำถามระบุ: ปีการศึกษาก่อน แล้วจึงระดับปริญญา"""
    return _narrow_by_degree(_narrow_by_year(ids, titles, question), titles, question)


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
            return _build(_narrow(by_name[name], titles, question), name, question)

    # ไม่เจอชื่อตรงๆ ลองผ่านคำย่อ เช่น 'วิทคอม' -> 'วิทยาการคอมพิวเตอร์'
    #
    # คำย่ออักษรโรมันต้องเทียบแบบมีขอบเขตคำ เดิมเทียบแค่ว่ามีอยู่ในข้อความ คำว่า "it" จึงไป
    # ตรงกับกลางคำ "Cybersecurity" และ "digital" แล้วจำกัดการค้นไว้ที่เทคโนโลยีสารสนเทศ
    # ทั้งที่ผู้ใช้กำลังคุยเรื่องวิทยาการคอมพิวเตอร์อยู่ (เจอจริงในบทสนทนาหลายเทิร์นบนหน้าเว็บ)
    for alias, full in ALIASES.items():
        if not _alias_present(alias, lowered):
            continue
        for name in _names_for_alias(alias, full, by_name):
            # ตัดคำย่อออกจากคำถามแทนชื่อเต็ม เพราะในคำถามมีแค่คำย่อ
            ids = _narrow(by_name[name], titles, question)
            if ids:
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
        for name in _names_for_alias(alias, full, by_name):
            if all(name != f for f, _ in found):
                found.append((name, alias))
        remaining = re.sub(rf"(?<![a-z0-9]){re.escape(alias.lower())}(?![a-z0-9])", " ", remaining)

    search_text = _search_text(question, [target for _, target in found])
    scopes = [
        CourseScope(course_ids=_narrow(by_name[name], titles, question), matched_name=name, search_text=search_text)
        for name, _ in found
    ]
    # ขอบเขตที่ไม่มีเล่มเหลือเลย เกิดจากคำถามระบุระดับปริญญาที่หลักสูตรนั้นไม่มี
    # (ดู _narrow_by_degree) — ทิ้งไป ดีกว่าส่งขอบเขตว่างให้ผู้เรียกไปค้นทั้งคลัง
    return [sc for sc in scopes if sc.course_ids]


def _names_for_alias(alias: str, full: str, by_name: dict[str, list[uuid.UUID]]) -> list[str]:
    """
    ชื่อเฉพาะทุกชื่อที่คำย่อนี้ควรหมายถึง — เรียงชื่อยาวก่อนเพื่อให้ตัวที่เฉพาะกว่ามาก่อน

    ตารางคำย่อชี้ไปที่ชื่อเต็ม **เล่มเดียว** ซึ่งไม่พอเมื่อคณะมีหลายหลักสูตรที่ชื่อมีคำนั้น
    วัดเจอเมื่อ 13 ต.ค. 2569: ALIASES["เกษตร"] ชี้ไปที่ "การจัดการเทคโนโลยีการเกษตร
    สมัยใหม่" (ปริญญาตรี) เท่านั้น คำถามที่พิมพ์ "เกษตร" จึงไม่เคยเห็นเล่มปริญญาโทและ
    ปริญญาเอกที่ชื่อ "การจัดการเทคโนโลยีการเกษตรและบริหารทรัพยากรชุมชน" เลย

    จึงรับสองทาง
      1. ชื่อที่เป็นส่วนหนึ่งของชื่อเต็มที่ตารางชี้ไว้ (พฤติกรรมเดิม)
      2. ชื่อที่ **มีคำย่อนั้นอยู่ในตัวเอง** — ทำให้คำย่อกว้าง ๆ เห็นทุกหลักสูตรในตระกูล
         เดียวกัน แล้วให้ตัวกรองปีและระดับปริญญาเลือกเล่มที่ถูกต่อไป
    """
    direct = [n for n in by_name if n and n in full]
    family = [n for n in by_name if n and alias in n and n not in direct]
    return sorted(direct, key=len, reverse=True) + sorted(family, key=len, reverse=True)


def ambiguous_degree_level(db: Session, question: str) -> tuple[str, list[str]] | None:
    """
    คำถามเอ่ยชื่อหลักสูตรที่มีหลายระดับปริญญา แต่ **ไม่ได้บอกว่าระดับไหน** หรือไม่
    คืน (ชื่อหลักสูตร, รายชื่อระดับที่มี) เรียงจากต่ำไปสูง

    คู่กับ missing_degree_level() ซึ่งดูกรณี "ระบุระดับที่ไม่มี"
    อันนี้ดูกรณี "ไม่ระบุทั้งที่มีให้เลือกมากกว่าหนึ่ง"

    ทำไมต้องถามกลับแทนที่จะตอบ
    ---------------------------
    คลังนี้มีสาขาที่ชื่อสาขาและปีเดียวกันแต่คนละระดับ (การจัดการเทคโนโลยีการเกษตรและ
    บริหารทรัพยากรชุมชน พ.ศ. 2568 มีทั้งปริญญาโท 36 หน่วยกิต และปริญญาเอก 48 หน่วยกิต)
    ขอบเขตจะเหลือทั้งสองเล่ม แล้วส่งต่อให้เส้นทางเอกสารเขียนคำตอบจากทั้งคู่

    ผลคือคำตอบอาจเอาตัวเลขของสองระดับมาปนกัน หรือหยิบเล่มใดเล่มหนึ่งมาตอบโดยไม่บอก
    ว่าเป็นระดับไหน ซึ่งผู้อ่านแยกไม่ออกว่าได้คำตอบของระดับที่ตัวเองถามหรือเปล่า
    **การถามกลับหนึ่งประโยคถูกกว่าการตอบผิดโดยไม่มีสัญญาณเตือน**

    คืน None เมื่อ: คำถามระบุระดับแล้ว · ไม่เอ่ยถึงหลักสูตรใด · หรือหลักสูตรนั้นมีระดับเดียว
    (หลักสูตรปริญญาตรีที่มีหลายฉบับปีจึงไม่เข้าเงื่อนไขนี้ เพราะทุกฉบับระดับเดียวกัน)
    """
    if requested_degree_level(question) is not None:
        return None

    courses = db.scalars(select(Course).where(Course.is_active.is_(True))).all()
    titles = {c.id: c.title for c in courses}
    by_name: dict[str, list[uuid.UUID]] = {}
    for c in courses:
        by_name.setdefault(_distinctive_name(c.title), []).append(c.id)

    candidates = _candidate_names(question, by_name)
    if not candidates:
        return None

    ids = [cid for name in candidates for cid in by_name[name]]
    have = degree_levels_of(ids, titles)
    if len(have) < 2:
        return None

    order = {"bachelor": 0, "master": 1, "doctoral": 2}
    return candidates[0], sorted(have, key=lambda lv: order.get(lv, 99))


def missing_degree_level(db: Session, question: str) -> tuple[str, str] | None:
    """
    คำถามระบุระดับปริญญาที่หลักสูตรนั้น **ไม่มี** หรือไม่ · คืน (ชื่อหลักสูตร, ระดับที่ขอ)

    มีไว้ให้ผู้เรียกบอกผู้ใช้ตรง ๆ ว่าไม่มีข้อมูลระดับนั้น แทนการเดาเล่มอื่นมาตอบ
    คืน None เมื่อไม่ได้ระบุระดับ หรือระบุแล้วมีเล่มระดับนั้นจริง หรือไม่เอ่ยถึงหลักสูตรใดเลย
    """
    level = requested_degree_level(question)
    if level is None:
        return None
    courses = db.scalars(select(Course).where(Course.is_active.is_(True))).all()
    titles = {c.id: c.title for c in courses}
    by_name: dict[str, list[uuid.UUID]] = {}
    for c in courses:
        by_name.setdefault(_distinctive_name(c.title), []).append(c.id)

    lowered = question.lower()
    candidates: list[str] = [n for n in sorted(by_name, key=len, reverse=True)
                             if n and n.lower() in lowered]
    if not candidates:
        for alias, full in ALIASES.items():
            if _alias_present(alias, lowered):
                candidates = _names_for_alias(alias, full, by_name)
                break
    if not candidates:
        return None

    ids = [cid for name in candidates for cid in by_name[name]]
    have = degree_levels_of(ids, titles)
    if level in have:
        return None
    return candidates[0], level


def _candidate_names(question: str, by_name: dict[str, list[uuid.UUID]]) -> list[str]:
    """ชื่อหลักสูตรที่คำถามนี้เอ่ยถึง — ชื่อเต็มก่อน ถ้าไม่มีจึงลองคำย่อ"""
    lowered = question.lower()
    found = [n for n in sorted(by_name, key=len, reverse=True) if n and n.lower() in lowered]
    if found:
        return found
    for alias, full in ALIASES.items():
        if _alias_present(alias, lowered):
            return _names_for_alias(alias, full, by_name)
    return []


def _year_of_title(title: str) -> int | None:
    m = re.search(r"25\d{2}", title)
    return int(m.group(0)) if m else None


def missing_edition_year(db: Session, question: str) -> tuple[str, int, list[int]] | None:
    """
    คำถามระบุปีฉบับที่ยัง **ไม่มี** ในข้อมูลหรือไม่ · คืน (ชื่อหลักสูตร, ปีที่ขอ, ปีที่มี)

    มีไว้ให้ผู้เรียกบอกตรง ๆ ว่ายังไม่พบฉบับปีนั้นพร้อมบอกปีที่มี แทนการตกไปเส้นทาง
    เอกสารซึ่งต้องพึ่งโมเดล ทั้งที่รายการฉบับเป็นข้อมูลที่ระบบรู้แน่นอนที่สุด

    คืน None เมื่อ: คำถามไม่ได้ระบุปี · ระบุหลายปี (เป็นคำถามเทียบฉบับ ไม่ใช่ถามฉบับเดียว)
    · ไม่เอ่ยถึงหลักสูตรใด · หรือมีฉบับปีนั้นอยู่จริง
    """
    years = sorted({int(m.group(0)) for m in re.finditer(r"(?<!\d)25\d{2}(?!\d)", question)})
    if len(years) != 1:
        return None
    asked = years[0]

    courses = db.scalars(select(Course).where(Course.is_active.is_(True))).all()
    by_name: dict[str, list[uuid.UUID]] = {}
    titles: dict[uuid.UUID, str] = {}
    for c in courses:
        by_name.setdefault(_distinctive_name(c.title), []).append(c.id)
        titles[c.id] = c.title

    candidates = _candidate_names(question, by_name)
    if not candidates:
        return None

    ids = [cid for name in candidates[:1] for cid in by_name[name]]
    # ถ้าคำถามระบุระดับปริญญาด้วย ให้ดูเฉพาะเล่มระดับนั้น ไม่งั้นจะบอกปีของอีกระดับ
    ids = _narrow_by_degree(ids, titles, question) or ids
    have = sorted({y for cid in ids if (y := _year_of_title(titles[cid])) is not None})
    if not have or asked in have:
        return None
    return candidates[0], asked, have


# คำที่ถ้าตามหลังชื่อหลักสูตร แปลว่า "ชื่อจบแล้ว" ส่วนที่ตามมาเป็นตัวคำถาม
#
# ใช้กับ more_specific_unknown_name() เท่านั้น · ภาษาไทยไม่เว้นวรรคระหว่างคำ การดู
# ว่ามีอักษรไทยต่อท้ายชื่อจึงแยกไม่ออกเองว่าเป็น "ชื่อที่ยาวกว่า" หรือ "คำถามที่ต่อมา"
_CONTINUES_QUESTION = (
    "มี", "เรียน", "ต้อง", "จบ", "ของ", "กับ", "และ", "ที่", "ใน", "คือ", "เป็น",
    "ไหม", "หรือ", "กี่", "แล้ว", "ด้วย", "นี้", "นั้น", "สอน", "ใช้", "ค่า", "หน่วย",
    "วิชา", "หลักสูตร", "สาขา", "ปี", "พ", "ทำงาน", "รับ", "เปิด", "อะไร", "ยัง",
    "ไป", "มา", "ดี", "เหมาะ", "แนะนำ", "ต่าง", "เท่า", "เทียบ", "ระดับ", "ปริญญา",
    "ฉบับ", "ภาค", "คณะ", "ตอน", "ถ้า", "ช่วย", "ขอ", "อยาก", "ควร",
)

# คำที่บอกว่าคำถามนี้เป็นการ "เทียบสองฝั่ง"
_COMPARES = re.compile(r"ต่างกัน|ต่าง|เท่ากัน|เหมือน|เทียบ|มากกว่า|น้อยกว่า|\bvs\b", re.I)
_SIDE_JOINER = re.compile(r"\s*(?:กับ|และ|หรือ|vs\.?|versus)\s*", re.I)


def more_specific_unknown_name(db: Session, question: str) -> str | None:
    """
    คำถามเทียบที่เอ่ยชื่อ "เจาะจงกว่า" ชื่อที่ระบบมี -> คืนชื่อนั้น · ไม่ใช่ก็คืน None

    ทำไมต้องมี — ชุด 37 ข้อ ข้อ a1-04 เมื่อ 14 ต.ค. 2569:
        "คณิตศาสตร์ กับ คณิตศาสตร์ประยุกต์ ต่างกันไหม"
    คณะไม่มีหลักสูตร "คณิตศาสตร์ประยุกต์" แต่ด่านเอ่ยชื่อสาขาที่ไม่มีไม่ทำงาน เพราะ
    "คณิตศาสตร์ประยุกต์" มีคำว่า "คณิตศาสตร์" ที่มีจริงเป็นสตริงย่อยอยู่ข้างใน
    ตัวจับชื่อจึงถือว่าเจอหลักสูตรแล้ว · ผลคือคำถามไหลไปเส้นทางเอกสารแล้วตอบว่า
    "ไม่พบข้อมูล" ทั้งที่คำตอบที่ถูกคือบอกว่ายังไม่พบหลักสูตรนั้นในข้อมูลของระบบ

    จำกัดให้ทำงานเฉพาะคำถามเทียบ เพราะที่นั่นเท่านั้นที่ผู้ใช้ตั้งใจเอ่ยสองชื่อ
    และการเดาผิดในคำถามแบบอื่นมีราคาสูงกว่าประโยชน์
    """
    if not _COMPARES.search(question):
        return None
    sides = [s for s in _SIDE_JOINER.split(question) if s.strip()]
    if len(sides) < 2:
        return None

    courses = db.scalars(select(Course).where(Course.is_active.is_(True))).all()
    names = sorted({_distinctive_name(c.title) for c in courses} - {""}, key=len, reverse=True)
    lowered_names = {n.lower() for n in names}

    for side in sides:
        for name in names:
            for m in re.finditer(re.escape(name), side):
                tail = side[m.end():]
                extra = re.match(r"[ก-๎]+", tail)
                if not extra or len(extra.group(0)) < 3:
                    continue
                if extra.group(0).startswith(_CONTINUES_QUESTION):
                    continue
                candidate = name + extra.group(0)
                # ต้องไม่ใช่ชื่อที่ระบบมี และไม่ใช่ส่วนหัวของชื่อที่ระบบมี
                if candidate.lower() in lowered_names:
                    continue
                if any(candidate.lower() in n for n in lowered_names):
                    continue
                return candidate
    return None


_LEVEL_LABEL = {"bachelor": "ปริญญาตรี", "master": "ปริญญาโท", "doctoral": "ปริญญาเอก"}


def degree_level_label(level: str) -> str:
    return _LEVEL_LABEL.get(level, level)


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
