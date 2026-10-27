"""
ตัดสินว่าคำถามควรตอบจากข้อมูลหลักสูตรที่มีโครงสร้าง (schema mko) หรือจากการค้นเอกสาร (RAG)

Phase 2 ของ docs/MKO_STRUCTURED_DATA_DESIGN.md ใช้ผลของโมดูลนี้ในโหมด shadow เท่านั้น
ไม่มีผลต่อคำตอบที่ผู้ใช้เห็น (ดู services/structured_shadow.py)

ส่งไปฐานข้อมูลเฉพาะเมื่อครบทุกข้อ
    1. ถามหา field ที่รองรับเพียง field เดียว คือ หน่วยกิตรวมตลอดหลักสูตร ปีของหลักสูตร อาชีพ วัตถุประสงค์
       หรือคุณสมบัติผู้เข้าศึกษา
    2. ไม่ถามถึงเรื่องที่ฐานข้อมูลยังไม่มี (หน่วยกิตรายหมวด รายวิชา ผลลัพธ์การเรียนรู้ ระยะเวลาเรียน ค่าเทอม ...)
    3. ไม่ใช่คำถามเชิงบรรยาย เปรียบเทียบ ขอคำแนะนำ หรือให้ตัดสินแทน
    4. เอ่ยถึงหลักสูตรเดียว — หลายปีการศึกษาของหลักสูตรเดียวกันนับเป็นหลักสูตรเดียว และระบุปีได้ไม่เกินหนึ่งปี
ขาดข้อใดข้อหนึ่ง ไป RAG ตามเดิม ถ้าไม่แน่ใจให้พลาดไปทาง RAG เพราะเป็นพฤติกรรมที่ใช้อยู่แล้ว

ไม่มีชื่อหลักสูตรอยู่ในโมดูลนี้ ชื่อมาจากตาราง courses ผ่าน course_scope ทุกครั้ง คำที่ใช้ตัดสินเป็นคำถามทั่วไป
และตัดชื่อหลักสูตรออกจากข้อความก่อนตรวจคำ เพื่อไม่ให้คำในชื่อหลักสูตรถูกนับเป็นคำถาม
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.course import Course
from app.services.course_scope import (
    _distinctive_name,
    degree_levels_of,
    requested_degree_level,
    resolve_scopes,
    without_programme_names,
)

STRUCTURED = "structured"
RAG = "rag"

SUPPORTED_FIELDS = ("total_credits", "edition_year", "careers", "objectives", "admission")

_THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")

# คำถามที่ถามหา field — ตรวจกับข้อความที่ตัดชื่อหลักสูตรและช่องว่างออกแล้ว
_FIELD_PATTERNS: dict[str, re.Pattern] = {
    # คำเชิงเทียบ (ต่างกัน/เท่ากัน/มากกว่า/เทียบ) นับเป็นการถามถึงหัวข้อนี้ด้วย
    #
    # เดิม "หน่วยกิตต่างกันไหม" ไม่เข้าเงื่อนไขเลย เพราะไม่มีคำบอกปริมาณตามหลัง
    # ชั้นข้อมูลจึงมองไม่เห็นว่าคำถามถามเรื่องหน่วยกิต แล้วคืน no_supported_field
    # (วัดจากชุด 37 ข้อ c1-02 เมื่อ 14 ต.ค. 2569) · คำถามฝั่งเดียวที่มีคำเชิงเทียบ
    # ยังไปเส้นทางเอกสารตามเดิม เพราะ _NARRATIVE ดักไว้อีกชั้น
    "total_credits": re.compile(r"หน่วยกิต.{0,20}?(กี่|เท่าไ|เท่าใด|ทั้งหมด|รวม|ตลอดหลักสูตร"
                                r"|ต่างกัน|เท่ากัน|มากกว่า|น้อยกว่า)"
                                r"|(กี่|จำนวน|ทั้งหมด|รวม|ตลอดหลักสูตร|ไม่น้อยกว่า|เทียบ)"
                                r".{0,20}?หน่วยกิต"
                                r"|credits?"),
    "edition_year": re.compile(r"(หลักสูตร|ฉบับ|ปรับปรุง|เล่ม).{0,12}?(ปี|พ\.?ศ\.?)(อะไร|ไหน|ใด|เท่าไ)"
                               r"|ปีของหลักสูตร|ปีหลักสูตร|ปรับปรุง(ล่าสุด|เมื่อ)|ฉบับ(ล่าสุด|ไหน|ใด)"),
    "careers": re.compile(r"อาชีพ|ทำงานอะไร|ทำงานได้|ทำงานที่ไหน|ทำงานด้าน|ทำงาน(ใน|เป็น)?ตำแหน่ง|ทำงานเป็นอะไร"
                          r"|งานอะไร|ตำแหน่งงาน|สายงาน|จบ(ไป|แล้ว|มา)?ทำ|careers?|jobs?"),
    "objectives": re.compile(r"วัตถุประสงค์|จุดมุ่งหมาย|เป้าหมายของหลักสูตร|objectives?"),
    # เพิ่มสำนวนพูดเมื่อ 14 ต.ค. 2569 — วัดแล้วว่า "สมัครเรียน X ต้องจบอะไรมา" ไม่เข้าเงื่อนไขเดิม
    # จึงไหลไปเส้นทางเอกสาร ซึ่งเป็นทางที่ดึงภาคผนวกข้อบังคับมาตอบได้ · บังคับให้มีกรรมตามหลัง
    # "ต้องจบ" เพื่อไม่ให้คำถามหน่วยกิตอย่าง "ต้องจบกี่หน่วยกิต" ถูกจับมาเป็นหัวข้อนี้
    "admission": re.compile(r"คุณสมบัติ(ของ)?(ผู้)?(เข้า|สมัคร)|ผู้เข้าศึกษา|ผู้(ที่)?(จะ)?สมัคร|ใครสมัคร|รับสมัครใคร"
                            r"|ต้องจบ(อะไร|ชั้น|ระดับ|จาก|สาย|ม\.|ปว)|รับ(ผู้|คน|นักเรียน)(ที่)?จบ"
                            r"|คุณสมบัติ(?!(ของ)?บัณฑิต)"),
}

# เรื่องที่ฐานข้อมูลยังไม่มี แม้จะมีคำของ field ที่รองรับปนอยู่ เช่น "หมวดวิชาศึกษาทั่วไปกี่หน่วยกิต"
# "วิชา" ที่ไม่ได้ตามหลัง "สาขา" คือรายวิชาหรือหมวดวิชา
_UNSUPPORTED = re.compile(
    r"(?<!สาขา)วิชา|หมวด|ศึกษาทั่วไป|เลือกเสรี|ฝึกประสบการณ์|สหกิจ|แผนการเรียน|โครงสร้างหลักสูตร"
    r"|ต่อภาค|ต่อเทอม|ต่อปี|ภาคละ|เทอมละ|ปีละ|ลงทะเบียน"
    r"|ค่าเทอม|ค่าธรรมเนียม|ค่าใช้จ่าย|ค่าเรียน|บาท|เงินเดือน|รายได้|ทุน"
    r"|กี่ปี|กี่ภาค|กี่เทอม|ระยะเวลา|เรียนนาน"
    r"|อาจารย์|ผลลัพธ์การเรียนรู้|plo|clo|ปรัชญา(?!ดุษฎี)|คุณสมบัติ(ของ)?บัณฑิต"
    r"|เปิดรับ|รับสมัครเมื่อ|วันรับสมัคร|รอบรับ|tcas|สอบ"
)

# คำถามเชิงบรรยาย เปรียบเทียบ ขอคำแนะนำ หรือให้ระบบตัดสินแทน — ต้องใช้เนื้อหาเอกสาร ไม่ใช่ค่าเดียวจากตาราง
_NARRATIVE = re.compile(
    r"ทำไม|เพราะอะไร|อย่างไร|ยังไง|อธิบาย|แนะนำ|เหมาะ|ควร|ดีไหม|ดีมั้ย|ข้อดี|ข้อเสีย|จุดเด่น|น่าสนใจ"
    r"|เปรียบเทียบ|เทียบ|ต่างกัน|แตกต่าง|เหมือนกัน|ความหมาย|หมายถึง|ยากไหม|ยากมั้ย"
    r"|ได้ไหม|ได้มั้ย|ได้หรือไม่|หรือเปล่า|หรือไม่|เล่า|รายละเอียด|ตัวอย่าง"
    r"|why|how|explain|recommend|compare|difference"
)

# ถามข้ามหลักสูตร เช่น "สาขาไหนเรียนหน่วยกิตน้อยที่สุด" แม้จะเอ่ยชื่อเพียงหลักสูตรเดียว
_ACROSS = re.compile(r"สาขาไหน|สาขาใด|หลักสูตรไหน|หลักสูตรใด|ทุกสาขา|ทุกหลักสูตร|ทั้งสอง|ทั้ง2|ที่สุด|อันดับ")

# คำถามว่า field เป็นอย่างไร เช่น "มีวัตถุประสงค์อย่างไร" เป็นการถามหา field ไม่ใช่ขอคำอธิบาย
_FIELD_QUESTION_TAIL = re.compile(r"(อย่างไร|ยังไง|อะไรบ้าง|อะไร|บ้าง)")

_BE_YEAR = re.compile(r"(?<!\d)(25\d{2})(?!\d)")
_CE_YEAR = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")


@dataclass(frozen=True)
class StructuredIntent:
    route: str                     # STRUCTURED หรือ RAG
    reason: str                    # รหัสเหตุผล ใช้ในบันทึกผลโหมด shadow
    field: str | None = None
    programme: str | None = None
    course_ids: tuple[uuid.UUID, ...] = ()
    year_be: int | None = None


def _normalise(text: str) -> str:
    return re.sub(r"\s+", "", text.translate(_THAI_DIGITS).lower())


def matched_fields(db: Session, question: str) -> list[str]:
    """
    หัวข้อทั้งหมดที่คำถามนี้ถามถึง เรียงตามลำดับที่ปรากฏในคำถาม

    ใช้กับคำถามที่ถามหลายหัวข้อพร้อมกัน ("เรียนกี่หน่วยกิต และจบไปทำงานอะไรได้บ้าง")
    ซึ่ง detect() คืน multiple_fields แล้วปล่อยไปเส้นทางเอกสารทั้งคำถาม ทั้งที่ทุกหัวข้อ
    มีข้อมูลที่ตรวจรับแล้วครบ — ตรวจทางตอบเร็ว 14 ต.ค. 2569
    """
    courses = db.scalars(select(Course).where(Course.is_active.is_(True))).all()
    names = sorted({_distinctive_name(c.title) for c in courses} - {""})
    text = _normalise(without_programme_names(_without_years(question), names))
    if _UNSUPPORTED.search(text):
        return []
    hits = [(m.start(), key) for key, pat in _FIELD_PATTERNS.items()
            if (m := pat.search(text)) is not None]
    return [key for _pos, key in sorted(hits)]


# รูปคำถามฝั่งเดียวที่ชั้นข้อมูลรับแน่นอน ใช้ประกอบคำถามย่อยของการเทียบ
# edition_year ไม่อยู่ในนี้ เพราะ "เทียบปีของหลักสูตร" ไม่ได้ถามข้อเท็จจริงที่เทียบได้
_COMPARE_TEMPLATE = {
    "total_credits": "หลักสูตร{name}{year} มีจำนวนหน่วยกิตรวมตลอดหลักสูตรเท่าไร",
    "careers": "หลักสูตร{name}{year} จบไปทำงานอะไรได้บ้าง",
    "objectives": "วัตถุประสงค์ของหลักสูตร{name}{year} มีอะไร",
}


def comparison_sides(db: Session, question: str) -> tuple[str, list[str]] | None:
    """
    คำถามเทียบข้อเท็จจริง "สองฝั่ง" -> (หัวข้อ, คำถามย่อยฝั่งละข้อ) · ไม่เรียกโมเดล

    รับสองรูปแบบ
        สองฉบับของหลักสูตรเดียว  "ฉบับ 2561 กับ 2566 หน่วยกิตต่างกันไหม"
        สองหลักสูตรฉบับเดียว     "คณิตศาสตร์กับวิทยาการคอมพิวเตอร์ หน่วยกิตต่างกันไหม"

    คืน None เมื่อไม่ใช่สองฝั่งชัด ๆ หรือถามหลายหัวข้อ — แล้วผู้เรียกไปเส้นทางเอกสาร
    ตามเดิม · การเทียบที่ต้องตีความเนื้อหา ("ต่างกันยังไง") ไม่ใช่งานของชั้นนี้
    """
    fields = matched_fields(db, question)
    if len(fields) != 1:
        return None
    field = fields[0]

    years = sorted(set(years_in(question)))
    courses = db.scalars(select(Course).where(Course.is_active.is_(True))).all()
    names = sorted({_distinctive_name(c.title) for c in courses} - {""}, key=len, reverse=True)
    lowered = question.lower()
    present = [n for n in names if n and n.lower() in lowered]
    # ตัดชื่อที่เป็นส่วนย่อยของชื่อที่ยาวกว่าออก ไม่ให้นับซ้ำเป็นสองหลักสูตร
    distinct = [n for n in present if not any(n != o and n in o for o in present)]

    # ประกอบคำถามฝั่งละข้อ "แบบมาตรฐาน" ไม่ตัดสตริงจากคำถามเดิม
    #
    # ที่ต้องทำแบบนี้: คำถามเดิมมีคำเชิงเทียบ ("ต่างกันไหม") ซึ่ง _NARRATIVE ดักไว้
    # ถ้าเอาคำถามเดิมไปใส่ปีแล้วส่งเข้า detect() อีกครั้ง จะถูกตีกลับเป็น RAG ทุกครั้ง
    # การประกอบใหม่ยังทำให้คำถามฝั่งย่อยอยู่ในรูปที่ชั้นข้อมูลรับแน่นอน ไม่ขึ้นกับสำนวน
    if field not in _COMPARE_TEMPLATE:
        return None
    template = _COMPARE_TEMPLATE[field]

    if len(years) == 2 and len(distinct) == 1:
        name = distinct[0]
        return field, [template.format(name=name, year=f" พ.ศ. {y}") for y in years]
    if len(distinct) == 2 and len(years) <= 1:
        year = f" พ.ศ. {years[0]}" if years else ""
        return field, [template.format(name=n, year=year) for n in distinct]
    return None


def only_field(question: str, keep: str) -> str:
    """
    ตัดวลีของหัวข้ออื่นออกจากคำถาม เหลือเฉพาะหัวข้อที่ต้องการ

    เก็บชื่อหลักสูตรและปีไว้ครบ เพราะชั้นข้อมูลต้องใช้เลือกเล่ม · ผู้เรียกต้องเอาผลไป
    ผ่าน detect() อีกครั้งเพื่อยืนยันว่าได้หัวข้อที่ต้องการจริง ไม่ใช่เชื่อการตัดคำลอย ๆ
    """
    out = question
    for key, pat in _FIELD_PATTERNS.items():
        if key != keep:
            out = pat.sub(" ", out)
    return re.sub(r"\s{2,}", " ", out).strip()


def years_in(text: str) -> list[int]:
    """ปีที่คำถามระบุ แปลงเป็นพุทธศักราชทั้งหมด ไม่ซ้ำ ตามลำดับที่พบ"""
    normal = text.translate(_THAI_DIGITS)
    found = [int(y) for y in _BE_YEAR.findall(normal)]
    found += [int(y) + 543 for y in _CE_YEAR.findall(normal)]
    return list(dict.fromkeys(found))


def _without_years(text: str) -> str:
    """ตัดปีที่ระบุออก เก็บ "พ.ศ." ที่ไม่มีเลขตามไว้ เพราะ "หลักสูตร พ.ศ. อะไร" คือคำถามหาปี"""
    normal = text.translate(_THAI_DIGITS)
    normal = re.sub(r"(พ\.?\s*ศ\.?|ค\.?\s*ศ\.?)\s*(?=\d)", " ", normal)
    return _CE_YEAR.sub(" ", _BE_YEAR.sub(" ", normal))


def detect(db: Session, question: str) -> StructuredIntent:
    """คืนเส้นทางของคำถาม ไม่แตะฐานข้อมูลนอกจากอ่านรายชื่อหลักสูตร"""
    if not question or not question.strip():
        return StructuredIntent(RAG, "empty")

    courses = db.scalars(select(Course).where(Course.is_active.is_(True))).all()
    names = sorted({_distinctive_name(c.title) for c in courses} - {""})
    text = _normalise(without_programme_names(_without_years(question), names))

    if _UNSUPPORTED.search(text):
        return StructuredIntent(RAG, "unsupported_topic")

    fields = [key for key, pattern in _FIELD_PATTERNS.items() if pattern.search(text)]
    if not fields:
        return StructuredIntent(RAG, "no_supported_field")
    if len(fields) > 1:
        return StructuredIntent(RAG, "multiple_fields")
    field_key = fields[0]

    # ตัดวลีที่ถามหา field พร้อมคำถามที่ตามหลังวลีนั้นทันทีออกก่อนตรวจคำเชิงบรรยาย
    # "อย่างไร" ที่อยู่ส่วนอื่นของประโยคยังนับเป็นคำถามเชิงบรรยาย
    field_phrase = re.compile(rf"(?:{_FIELD_PATTERNS[field_key].pattern}){_FIELD_QUESTION_TAIL.pattern}?")
    remainder = field_phrase.sub(" ", text)
    if _NARRATIVE.search(remainder):
        return StructuredIntent(RAG, "narrative_or_comparison", field_key)
    if _ACROSS.search(text):
        return StructuredIntent(RAG, "across_programmes", field_key)

    years = years_in(question)
    if len(years) > 1:
        return StructuredIntent(RAG, "multiple_years", field_key)

    scopes = resolve_scopes(db, _without_years(question))
    if not scopes:
        return StructuredIntent(RAG, "no_programme", field_key)
    if len(scopes) > 1:
        return StructuredIntent(RAG, "multiple_programmes", field_key)

    scope = scopes[0]

    # ชื่อสาขาเดียวกันอาจมีหลายระดับปริญญา (โท/เอก ปีเดียวกัน) ถ้าผู้ใช้ไม่ได้บอกระดับ
    # การเลือกเล่มใดเล่มหนึ่งคือการเดา ให้ไป RAG ตามหลักของโมดูลนี้ (ไม่แน่ใจ = ไม่ตอบจากฐานข้อมูล)
    titles = {c.id: c.title for c in courses}
    if requested_degree_level(question) is None and len(degree_levels_of(list(scope.course_ids), titles)) > 1:
        return StructuredIntent(RAG, "multiple_degree_levels", field_key)

    return StructuredIntent(
        STRUCTURED,
        "single_programme_field",
        field_key,
        scope.matched_name,
        tuple(scope.course_ids),
        years[0] if years else None,
    )
