"""
หลักฐานของคำถามที่เอ่ยถึงหลายหลักสูตร: ข้อเท็จจริงของแต่ละหลักสูตรแยกตามด้านที่เทียบกันได้ พร้อมปีของฉบับ

ปัญหาที่แก้ (docs/MKO_PHASE2_SHADOW_EVAL.md ข้อ 5)
---------------------------------------------------
"วิทยาการคอมพิวเตอร์กับคอมพิวเตอร์แอนิเมชันและมัลติมีเดียต่างกันอย่างไร" ได้คำตอบว่าไม่พบข้อมูลเปรียบเทียบ ทั้งที่ระบุ
ขอบเขตได้ครบทั้งสองหลักสูตร ตามรอยแล้วหลักฐานของคำถามเปรียบเทียบมาจากสองแหล่ง
  - ชิ้นที่ค้นด้วยคำค้นหลังตัดชื่อหลักสูตร ซึ่งเหลือแค่ "กับ ต่างกันอย่างไร" จึงได้แต่เศษ เช่น วิชาสมาธิ หน้า OCR
    ที่อ่านไม่ออก และตารางสัญลักษณ์
  - "แก่นของหลักสูตร" ไม่เกินสองชิ้นจากฉบับล่าสุดเท่านั้น ฉบับล่าสุดของบางหลักสูตรเป็นเอกสารสรุปที่ไม่มีหัวข้ออาชีพ
    หลักฐานของสองฝั่งจึงไม่เท่ากัน และข้อมูลที่มีในฉบับก่อนหน้าไม่ถูกใช้เลย

วิธีทำ
------
แต่ละหลักสูตรหาหลักฐานแยกกันตามด้านที่ มคอ.2 ทุกเล่มมีหัวข้อกำกับ: ปรัชญา วัตถุประสงค์ อาชีพหลังสำเร็จการศึกษา และ
โครงสร้างหลักสูตร ด้านละหนึ่งฉบับ เลือกฉบับล่าสุดที่มีหัวข้อนั้น ถ้าฉบับล่าสุดไม่มีจึงใช้ฉบับก่อนหน้า ชิ้นเอกสารใช้ชื่อ
หลักสูตรพร้อมปีของฉบับที่มาจริง ขั้นตรวจเอกสารและขั้นเขียนคำตอบจึงเห็นเสมอว่าข้อเท็จจริงแต่ละข้อมาจากฉบับใด ไม่ปน
ฉบับโดยไม่ระบุปี (describe_evidence สรุปให้ทั้งสองขั้นเห็นตรงกันว่าด้านใดมีหลักฐานของหลักสูตรใด)

ตัดชิ้นที่เป็นสารบัญและชิ้นที่อ่านไม่ออกทิ้ง เกณฑ์ชิ้นที่อ่านไม่ออกวัดจากคลังจริง 9,039 ชิ้น: ความหนาแน่นของสัญลักษณ์
ตั้งแต่ 0.05 มี 38 ชิ้น เป็นหน้า OCR ที่อ่านไม่ออกและตารางสัญลักษณ์ทั้งหมด ส่วนคำอธิบายรายวิชาภาษาอังกฤษอยู่ราว 0.015

หัวข้อที่ใช้เป็นหัวข้อตามแบบ มคอ.2 ไม่ใช่ชื่อหลักสูตรหรือคำถาม — วัดจากคลังจริงว่าหัวข้อเหล่านี้คือบรรทัดขึ้นต้นที่พบบ่อย
ปรัชญาต้องเป็นทั้งบรรทัด เพราะคำอธิบายรายวิชาศึกษาทั่วไปขึ้นต้นบรรทัดด้วย "ปรัชญา แนวคิด..." และ "ปรัชญาเศรษฐกิจพอเพียง"
โครงสร้างหลักสูตรต้องเป็นทั้งบรรทัดและมีหน่วยกิต เพราะภาคผนวกมีตาราง "โครงสร้างหลักสูตร มคอ. 1 ..." ที่เทียบกับเกณฑ์กลาง
"""
from __future__ import annotations

import re
import unicodedata
import uuid
from collections import defaultdict
from dataclasses import dataclass
from typing import Callable

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.course import SearchResultChunk
from app.services.course_scope import _distinctive_name, without_programme_names
from app.services.structured_intent import _FIELD_PATTERNS, _normalise

_SYMBOLS = set("'\"~`\\|^{}<>#$@*_=+!;")
GARBLED_SYMBOL_DENSITY = 0.05
_TITLE_YEAR = re.compile(r"25\d{2}")
_DEGREE_SUFFIX = re.compile(r"\s*(สาขาวิชา.*|\(.*\))$")

_PHILOSOPHY_LINE = re.compile(r"^[ \t]*(?:\d+(?:\.\d+)*\.?[ \t]*)?ปรัชญา(?:ของหลักสูตร)?[ \t]*(?:ความสำคัญ[^\n]*)?$", re.M)
_STRUCTURE_LINE = re.compile(r"^[ \t]*(?:\d+(?:\.\d+)*\.?[ \t]*)?โครงสร้างหลักสูตร[ \t]*$", re.M)


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    matches: Callable[[str], bool]
    # คำที่ใช้กรองในฐานข้อมูลก่อนตรวจรูปแบบหัวข้อ
    like: str


FIELDS: tuple[Field, ...] = (
    Field("philosophy", "ปรัชญา", lambda c: _PHILOSOPHY_LINE.search(c) is not None, "%ปรัชญา%"),
    Field("objectives", "วัตถุประสงค์", lambda c: "วัตถุประสงค์ของหลักสูตร" in c, "%วัตถุประสงค์ของหลักสูตร%"),
    Field("careers", "อาชีพหลังสำเร็จการศึกษา", lambda c: "อาชีพที่สามารถประกอบได้หลัง" in c, "%อาชีพที่สามารถประกอบได้หลัง%"),
    Field("structure", "โครงสร้างหลักสูตร",
          lambda c: _STRUCTURE_LINE.search(c) is not None and "หน่วยกิต" in c, "%โครงสร้างหลักสูตร%"),
)


def is_garbled(content: str) -> bool:
    chars = [c for c in content if not c.isspace()]
    return bool(chars) and sum(c in _SYMBOLS for c in chars) / len(chars) >= GARBLED_SYMBOL_DENSITY


def edition_year(title: str) -> int | None:
    m = _TITLE_YEAR.search(title)
    return int(m.group(0)) if m else None


def _usable(content: str) -> bool:
    from app.services.program_match import _looks_like_table_of_contents

    return not is_garbled(content) and not _looks_like_table_of_contents(content)


def programme_evidence(db: Session, course_ids: list[uuid.UUID], score: float) -> list[SearchResultChunk]:
    """
    หลักฐานของหลักสูตรหนึ่ง (รวมทุกฉบับใน course_ids) ด้านละหนึ่งฉบับ เรียงตามลำดับด้าน ไม่มีชิ้นซ้ำ

    แต่ละด้านใช้ชิ้นแรกที่มีหัวข้อ (ตามลำดับหน้า) และชิ้นถัดไปของเอกสารเดียวกัน เพราะรายการใต้หัวข้อมักยาวเลยขอบชิ้น
    ฉบับที่ปีเท่ากัน (เช่น ปริญญาต่างระดับที่ใช้ชื่อสาขาเดียวกัน) ใช้ทุกฉบับในปีนั้น ไม่เลือกฉบับใดฉบับหนึ่งเอง
    score คือคะแนนที่ให้กับชิ้นเหล่านี้ ผู้เรียกส่งคะแนนสูงสุดของการค้นมา เพื่อไม่ให้เกณฑ์ขอบเขตสูงเกินจริง
    """
    if not course_ids:
        return []
    rows = db.execute(
        text(
            """
            SELECT ch.id, ch.course_id, ch.document_id, ch.chunk_index, ch.page_number, ch.content, c.title
              FROM course_chunks ch JOIN courses c ON c.id = ch.course_id
             WHERE ch.course_id = ANY(:ids)
               AND (ch.content LIKE :f0 OR ch.content LIKE :f1 OR ch.content LIKE :f2 OR ch.content LIKE :f3)
             ORDER BY ch.page_number, ch.chunk_index
            """
        ),
        {"ids": list(course_ids), **{f"f{i}": f.like for i, f in enumerate(FIELDS)}},
    ).all()
    by_edition: dict[uuid.UUID, list] = defaultdict(list)
    titles: dict[uuid.UUID, str] = {}
    for r in rows:
        if _usable(r.content):
            by_edition[r.course_id].append(r)
            titles[r.course_id] = r.title
    by_year: dict[int, list[uuid.UUID]] = defaultdict(list)
    for course_id in by_edition:
        by_year[edition_year(titles[course_id]) or 0].append(course_id)

    picked: list = []
    for field in FIELDS:
        for year in sorted(by_year, reverse=True):
            hits = [
                hit for course_id in sorted(by_year[year], key=lambda cid: titles[cid])
                if (hit := next((r for r in by_edition[course_id] if field.matches(r.content)), None)) is not None
            ]
            for hit in hits:
                picked.append(hit)
                following = db.execute(
                    text(
                        """
                        SELECT ch.id, ch.course_id, ch.document_id, ch.chunk_index, ch.page_number, ch.content, c.title
                          FROM course_chunks ch JOIN courses c ON c.id = ch.course_id
                         WHERE ch.document_id = :doc AND ch.chunk_index = :idx
                        """
                    ),
                    {"doc": hit.document_id, "idx": hit.chunk_index + 1},
                ).first()
                if following is not None and _usable(following.content):
                    picked.append(following)
            if hits:
                break

    seen: set = set()
    evidence = []
    for r in picked:
        if r.id in seen:
            continue
        seen.add(r.id)
        evidence.append(
            SearchResultChunk(chunk_id=r.id, course_id=r.course_id, course_title=r.title,
                              page_number=r.page_number, content=r.content, score=score)
        )
    return evidence


def describe_evidence(chunks) -> str:
    """
    สรุปว่าเนื้อหาที่ส่งให้ขั้นตรวจเอกสารและขั้นเขียนคำตอบมีหัวข้อด้านใดของหลักสูตรใด จากฉบับปีใด

    สรุปจากชิ้นที่ส่งจริง ไม่ได้ค้นใหม่ จึงตรงกับเนื้อหาเสมอ ด้านที่ไม่มีหัวข้อในเนื้อหาระบุว่าไม่พบ ไม่ใช่ว่าเอกสารไม่มี
    """
    found: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    order: list[str] = []
    titles_per_year: dict[tuple[str, int | None], set[str]] = defaultdict(set)
    for c in chunks:
        titles_per_year[(_distinctive_name(c.course_title), edition_year(c.course_title))].add(c.course_title)
    for c in chunks:
        name = _distinctive_name(c.course_title)
        if name not in found:
            order.append(name)
        year = edition_year(c.course_title)
        label = f"พ.ศ. {year}" if year else "ไม่ระบุปี"
        if len(titles_per_year[(name, year)]) > 1:
            # ต่างระดับปริญญาแต่ชื่อสาขาและปีเดียวกัน ต้องบอกระดับให้แยกกันออก
            label = f"{_DEGREE_SUFFIX.sub('', c.course_title).strip()} {label}"
        for field in FIELDS:
            if field.matches(c.content):
                found[name][field.key].add(label)
        found[name]  # ให้หลักสูตรที่ไม่มีหัวข้อใดเลยยังอยู่ในสรุป
    if len(order) < 2:
        return ""
    lines = ["[สรุปจากระบบ: หัวข้อที่พบในเนื้อหาด้านล่าง แยกตามหลักสูตรและปีของฉบับ]"]
    for name in order:
        parts = []
        for field in FIELDS:
            years = sorted(found[name].get(field.key, ()))
            parts.append(f"{field.label} ({', '.join(years)})" if years else f"{field.label} (ไม่พบในเนื้อหาที่ค้นได้)")
        lines.append(f"- {name}: " + "; ".join(parts))
    return "\n".join(lines)


# ---------------------------------------------------------------------------------------------------------------------
# ด่านตรวจเอกสารแบบกำหนดผลได้ของคำถามหลายหลักสูตร (docs/MKO_PHASE2_MODEL_VALIDATION.md เคส 6)
#
# ปัญหาที่แก้: "วิทยาการคอมพิวเตอร์กับเทคโนโลยีสารสนเทศ สาขาไหนเรียนเขียนโปรแกรมมากกว่ากัน" ส่งหลักฐานชุดเดียวกันทุกชิ้นให้
# ด่านตรวจเอกสารที่เป็นโมเดลสองครั้ง (temperature 0) ได้ false หนึ่งครั้งและ true หนึ่งครั้ง เหตุผลของครั้งที่ false เองยอมรับว่า
# "เนื้อหามีข้อมูลรายวิชาและโครงสร้างหลักสูตรของทั้งสองสาขา" ผู้ใช้จึงได้ "ไม่พบข้อมูล" แบบสุ่ม ทั้งที่มีข้อเท็จจริงให้ตอบ
#
# คำถามว่า "เนื้อหามีเรื่องที่ถามของทุกหลักสูตรไหม" ตัดสินจากหลักฐานได้ด้วยโค้ด จึงไม่ต้องให้โมเดลตัดสิน
#   supported          ทุกหลักสูตรมีเนื้อหาในเรื่องที่ถาม -> ผ่านไปขั้นเขียนคำตอบเสมอ ไม่เรียกโมเดลตรวจ
#   missing_programme  มีหลักสูตรที่ไม่มีเนื้อหาที่ใช้ได้เลย -> ไม่พบข้อมูลเสมอ (เทียบไม่ได้แน่นอน)
#   undetermined       โค้ดตัดสินไม่ได้ เช่น ถ้อยคำในคำถามไม่ตรงกับเอกสาร -> ใช้ด่านตรวจที่เป็นโมเดลตามเดิม
# ส่วนที่ตัดสินไม่ได้ยังไปทางเดิม เพื่อไม่ให้การตรวจแบบข้อความหลวมกว่าเดิมในกรณีที่ไม่แน่ใจ
#
# "มากกว่า" ตัดสินจากหลักฐานที่ค้นเจอไม่ได้ เพราะเนื้อหาเป็นชิ้นส่วนของเอกสาร ไม่ใช่รายการครบ ระบบจึงไม่นับหรือจัดอันดับให้
# และบอกขั้นเขียนคำตอบให้ตอบว่ายังสรุปไม่ได้ พร้อมข้อเท็จจริงที่มี เว้นแต่เนื้อหามีตัวเลขครบที่เทียบกันได้ตรงๆ
#
# ไม่มีชื่อหลักสูตรหรือคำถามในส่วนนี้: เรื่องที่ถามได้จากการตัดชื่อหลักสูตร ปี และคำที่ใช้ถามเปรียบเทียบออกจากคำถามของผู้ใช้
# ---------------------------------------------------------------------------------------------------------------------

SUPPORTED = "supported"
MISSING_PROGRAMME = "missing_programme"
UNDETERMINED = "undetermined"

# คำที่ใช้ถามหรือเปรียบเทียบ ไม่ใช่เรื่องที่ถาม ไม่ใส่คำสั้นที่มักเป็นส่วนหนึ่งของคำอื่น (มี ที่ ได้ กัน)
_QUESTION_WORDS = (
    "มากกว่ากัน", "น้อยกว่ากัน", "เยอะกว่ากัน", "มากกว่า", "น้อยกว่า", "เยอะกว่า", "ที่สุด",
    "เปรียบเทียบ", "แตกต่างกัน", "แตกต่าง", "ต่างกัน", "เหมือนกัน", "ระหว่าง", "อย่างไร", "ยังไง",
    "สาขาไหน", "หลักสูตรไหน", "ไหน", "อะไรบ้าง", "อะไร", "บ้าง", "สาขาวิชา", "สาขา", "หลักสูตร", "เรียน",
    "กับ", "และ", "หรือไม่", "หรือ", "ครับ", "ค่ะ", "คะ", "ไหม", "มั้ย",
)
_QUESTION_WORDS_RX = re.compile("|".join(map(re.escape, sorted(_QUESTION_WORDS, key=len, reverse=True))))
_RANKING_RX = re.compile(r"มากกว่า|น้อยกว่า|เยอะกว่า|ที่สุด|กว่ากัน")
_YEAR_RX = re.compile(r"(?:[พค]\.?\s*ศ\.?\s*)?(?<!\d)(?:25|19|20)\d{2}(?!\d)")
_NOT_TOPIC = re.compile(r"[\s?？!.,ๆ\"'()\[\]:;-]+")
_THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")
# เรื่องที่ถามที่มีตัวอักษรหลัก (ไม่นับสระบน-ล่างและวรรณยุกต์) น้อยกว่านี้ตรงกับส่วนหนึ่งของคำอื่นได้ง่าย ตรวจด้วยข้อความไม่ได้
# วัดเป็นตัวอักษรหลัก เพราะคำไทยสั้นอย่าง "สถิติ" มีห้าอักขระแต่ตัวอักษรหลักสามตัว
_MIN_TOPIC_LETTERS = 3


def _field(key: str) -> Field:
    return next(f for f in FIELDS if f.key == key)


# field ของ structured_intent ที่มีหัวข้อตามแบบ มคอ.2 ให้ตรวจ ส่วน field อื่นตรวจด้วยข้อความของเรื่องที่ถาม
_FIELD_EVIDENCE: dict[str, Callable[[str], bool]] = {
    "careers": lambda c: _field("careers").matches(c),
    "objectives": lambda c: _field("objectives").matches(c),
    "total_credits": lambda c: "หน่วยกิตรวม" in c or _field("structure").matches(c),
}
_FIELD_LABEL = {"careers": "อาชีพหลังสำเร็จการศึกษา", "objectives": "วัตถุประสงค์", "total_credits": "หน่วยกิตรวม"}


@dataclass(frozen=True)
class ComparisonSupport:
    decision: str
    reason: str
    topic: str = ""
    field: str | None = None
    ranking: bool = False

    def note_line(self) -> str:
        """ข้อความให้ขั้นเขียนคำตอบ เฉพาะเมื่อผ่านด้วยโค้ด"""
        if self.decision != SUPPORTED:
            return ""
        if self.field:
            subject = f"หัวข้อ{_FIELD_LABEL[self.field]}"
        elif self.topic:
            subject = f'เรื่อง "{self.topic}" '
        else:
            subject = "หัวข้อที่เทียบกันได้อย่างน้อยหนึ่งด้าน"
        lines = [f"[สรุปจากระบบ: ตรวจแล้วว่าเนื้อหามี{subject}ของทุกหลักสูตรที่ถาม]"]
        if self.ranking:
            lines.append(
                "[สรุปจากระบบ: คำถามขอให้เทียบเชิงปริมาณหรือจัดอันดับ ระบบไม่ได้นับหรือจัดอันดับให้ จัดอันดับได้เฉพาะเมื่อเนื้อหามี"
                "ตัวเลขหรือรายการครบที่เทียบกันได้ตรงๆ ถ้าไม่ถึงขั้นนั้นให้ตอบว่ายังสรุปไม่ได้ว่าหลักสูตรใดมากกว่า แล้วยกข้อเท็จจริง"
                "ที่มีของทุกหลักสูตร และบอกเกณฑ์ที่ต้องกำหนดก่อน]"
            )
        return "\n".join(lines)


def question_topic(question: str, programmes: list[str]) -> tuple[str | None, str]:
    """(field ที่ตรวจด้วยหัวข้อได้ หรือ None, เรื่องที่ถามหลังตัดชื่อหลักสูตร ปี และคำที่ใช้ถาม)"""
    stripped = without_programme_names(question.translate(_THAI_DIGITS), programmes)
    normal = _normalise(stripped)
    field = next((key for key, pattern in _FIELD_PATTERNS.items() if key in _FIELD_EVIDENCE and pattern.search(normal)), None)
    topic = _NOT_TOPIC.sub("", _QUESTION_WORDS_RX.sub(" ", _YEAR_RX.sub(" ", stripped)))
    return field, topic


def _checkable(topic: str) -> bool:
    if topic.isascii():
        return len(topic) >= 2
    return sum(unicodedata.category(ch)[0] in "LN" for ch in topic) >= _MIN_TOPIC_LETTERS


def _mentions(content: str, topic: str) -> bool:
    if topic.isascii():
        return re.search(rf"(?<![a-z0-9]){re.escape(topic)}(?![a-z0-9])", content.lower()) is not None
    return topic in re.sub(r"\s+", "", content.replace("ํา", "ำ"))


def comparison_support(question: str, programmes: list[str], chunks) -> ComparisonSupport:
    """
    ตัดสินจากหลักฐานที่ส่งจริงว่าคำถามหลายหลักสูตรมีเรื่องที่ถามของทุกหลักสูตรไหม ผลเดิมทุกครั้งเมื่อคำถามและหลักฐานเดิม

    programmes คือชื่อหลักสูตรตาม course_scope.resolve_scopes ชิ้นที่เป็นสารบัญหรืออ่านไม่ออกไม่นับเป็นหลักฐาน
    """
    ranking = _RANKING_RX.search(question) is not None
    usable: dict[str, list[str]] = defaultdict(list)
    for c in chunks:
        if _usable(c.content):
            usable[_distinctive_name(c.course_title)].append(c.content)
    missing = [p for p in programmes if not usable.get(p)]
    if missing:
        return ComparisonSupport(MISSING_PROGRAMME, "ไม่มีเนื้อหาที่ใช้ได้ของ " + ", ".join(missing), ranking=ranking)

    field, topic = question_topic(question, programmes)
    if field:
        lacking = [p for p in programmes if not any(_FIELD_EVIDENCE[field](c) for c in usable[p])]
        if lacking:
            return ComparisonSupport(UNDETERMINED, f"ไม่พบหัวข้อ{_FIELD_LABEL[field]}ของ " + ", ".join(lacking),
                                     topic, field, ranking)
        return ComparisonSupport(SUPPORTED, f"พบหัวข้อ{_FIELD_LABEL[field]}ของทุกหลักสูตร", topic, field, ranking)

    if not topic:
        if ranking:
            # ขอให้จัดอันดับโดยไม่บอกว่าเรื่องอะไร โค้ดไม่รู้ว่าต้องหาอะไร
            return ComparisonSupport(UNDETERMINED, "คำถามขอให้จัดอันดับแต่ไม่ระบุเรื่อง", ranking=ranking)
        common = set.intersection(*({f.key for f in FIELDS for c in usable[p] if f.matches(c)} for p in programmes))
        if common:
            labels = ", ".join(f.label for f in FIELDS if f.key in common)
            return ComparisonSupport(SUPPORTED, f"พบหัวข้อที่มีครบทุกหลักสูตร: {labels}", ranking=ranking)
        return ComparisonSupport(UNDETERMINED, "ไม่พบหัวข้อที่มีครบทุกหลักสูตร", ranking=ranking)

    if not _checkable(topic):
        return ComparisonSupport(UNDETERMINED, f'เรื่องที่ถาม "{topic}" สั้นเกินกว่าจะตรวจด้วยข้อความ', topic, None, ranking)
    lacking = [p for p in programmes if not any(_mentions(c, topic) for c in usable[p])]
    if lacking:
        return ComparisonSupport(UNDETERMINED, f'ไม่พบ "{topic}" ในเนื้อหาของ ' + ", ".join(lacking), topic, None, ranking)
    return ComparisonSupport(SUPPORTED, f'พบ "{topic}" ในเนื้อหาของทุกหลักสูตร', topic, None, ranking)
