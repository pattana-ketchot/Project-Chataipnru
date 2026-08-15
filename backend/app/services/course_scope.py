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
from app.services.query_expansion import ALIASES


@dataclass
class CourseScope:
    course_ids: list[uuid.UUID]
    matched_name: str
    search_text: str


# คำนำหน้าที่ตัดทิ้งได้เมื่อเอาชื่อหลักสูตรออกแล้ว เพื่อไม่ให้เหลือเศษคำ
_LEADING_NOISE = re.compile(r"^(หลักสูตร|สาขาวิชา|สาขา|คณะ|เอก)\s*")
_EXTRA_SPACE = re.compile(r"\s{2,}")

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


def resolve_scope(db: Session, question: str) -> CourseScope | None:
    """คืนขอบเขตหลักสูตรถ้าระบุได้ มิฉะนั้นคืน None (แปลว่าให้ค้นทั้งคลัง)"""
    courses = db.scalars(select(Course).where(Course.is_active.is_(True))).all()

    # ชื่อเฉพาะ -> รายการ course id (หลักสูตรเดียวกันหลายปีจะรวมอยู่ด้วยกัน)
    by_name: dict[str, list[uuid.UUID]] = {}
    for c in courses:
        by_name.setdefault(_distinctive_name(c.title), []).append(c.id)

    lowered = question.lower()

    # หาชื่อที่ปรากฏในคำถามโดยตรง เลือกชื่อที่ยาวที่สุดก่อนเพื่อไม่ให้ชื่อสั้นที่เป็น
    # ส่วนหนึ่งของชื่อยาวชนะ (เช่น 'คณิตศาสตร์' อยู่ใน 'คหกรรมศาสตร์' ไม่ได้ แต่กันไว้)
    for name in sorted(by_name, key=len, reverse=True):
        if name and name.lower() in lowered:
            return _build(by_name[name], name, question)

    # ไม่เจอชื่อตรงๆ ลองผ่านคำย่อ เช่น 'วิทคอม' -> 'วิทยาการคอมพิวเตอร์'
    for alias, full in ALIASES.items():
        if alias not in lowered:
            continue
        for name in by_name:
            if name and name in full:
                # ตัดคำย่อออกจากคำถามแทนชื่อเต็ม เพราะในคำถามมีแค่คำย่อ
                return _build(by_name[name], name, question, strip=alias)
    return None


def _build(ids: list[uuid.UUID], name: str, question: str, strip: str | None = None) -> CourseScope:
    target = strip or name
    # ตัดแบบไม่สนตัวพิมพ์เล็กใหญ่ เพราะคำย่ออาจเป็นอักษรโรมัน
    remainder = re.sub(re.escape(target), " ", question, flags=re.IGNORECASE)
    remainder = _LEADING_NOISE.sub("", _EXTRA_SPACE.sub(" ", remainder).strip()).strip()

    # เหลือน้อยเกินไปแปลว่าคำถามคือชื่อหลักสูตรล้วน ใช้ข้อความเดิมค้นต่อไป
    search_text = remainder if len(remainder) >= _MIN_REMAINDER else question
    return CourseScope(course_ids=ids, matched_name=name, search_text=search_text)
