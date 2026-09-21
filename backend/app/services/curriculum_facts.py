"""
อ่านข้อมูลหลักสูตรที่ผ่านการตรวจและเผยแพร่แล้วจาก PostgreSQL (schema mko) แล้วเรียบเรียงเป็นคำตอบพร้อมที่มา

Phase 2 ของ docs/MKO_STRUCTURED_DATA_DESIGN.md — ใช้ในโหมด shadow เท่านั้น ยังไม่แสดงผลให้ผู้ใช้

หลักการ
    - อ่านเฉพาะ view mko.v_live_values / mko.v_live_list_items (การเผยแพร่ครั้งล่าสุด) ไม่อ่านค่าที่ยังไม่ผ่านการตรวจ
    - ทุกค่าที่ตอบมีไฟล์และหน้าของเอกสารต้นทาง ค่าเดี่ยวมีข้อความที่ยกมาจากเอกสารด้วย
    - ไม่เดา ไม่มีข้อมูลที่เผยแพร่ = no_data ให้ระบบเดิม (RAG) ตอบตามปกติ
    - หลักสูตรเดียวกันหลายปีการศึกษาไม่ปนกัน
        ระบุปี          -> ใช้เฉพาะฉบับปีนั้น ไม่มีฉบับปีนั้น = no_data
        ไม่ระบุปี ค่าเดี่ยว -> แสดงทุกฉบับที่มีข้อมูล ถ้าค่าต่างกันแยกบรรทัดตามฉบับ
        ไม่ระบุปี รายการ  -> แสดงฉบับล่าสุดที่มีข้อมูล และบอกว่ามีฉบับอื่นด้วย (รายการยาว แสดงรวมกันจะอ่านยาก)
      ฉบับที่ไม่มีข้อมูลผ่านการตรวจ ระบุไว้ในคำตอบ ไม่ข้ามไปเงียบๆ
"""
from __future__ import annotations

import re
import uuid
from dataclasses import asdict, dataclass, field as dc_field

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.course import Course
from app.services.course_scope import degree_levels_of
from app.services.structured_intent import STRUCTURED, StructuredIntent

ANSWERED = "answered"
NO_DATA = "no_data"

LIST_FIELDS = {"careers": "career", "objectives": "objective", "admission": "admission"}
_LIST_LABEL = {"careers": "อาชีพที่สามารถประกอบได้หลังสำเร็จการศึกษา",
               "objectives": "วัตถุประสงค์ของหลักสูตร",
               "admission": "คุณสมบัติของผู้เข้าศึกษา"}

_TITLE_YEAR = re.compile(r"25\d{2}")


@dataclass
class Source:
    file: str
    page_start: int
    page_end: int
    quote: str | None = None
    # รหัสเอกสารต้นฉบับใน course_documents ใช้เปิดไฟล์ผ่าน /documents/{id}/pdf
    # เก็บไว้เพื่อ "บอกที่มา" เท่านั้น ไม่ได้ใช้เลือกหรือตัดสินคำตอบ
    document_id: str | None = None

    def label(self) -> str:
        pages = f"หน้า {self.page_start}" if self.page_start == self.page_end else f"หน้า {self.page_start}–{self.page_end}"
        return f"{self.file} {pages}"


@dataclass
class EditionFact:
    course_id: str
    course_title: str
    edition_year: int | None
    value_int: int | None = None
    value_text: str | None = None
    items: list[str] = dc_field(default_factory=list)
    source: Source | None = None
    reviewed_by: str | None = None


@dataclass
class FactsResult:
    status: str
    field: str | None
    facts: list[EditionFact] = dc_field(default_factory=list)
    missing_editions: list[str] = dc_field(default_factory=list)
    other_editions: list[str] = dc_field(default_factory=list)
    publication_id: str | None = None
    answer: str | None = None
    note: str | None = None

    def to_json(self) -> dict:
        return asdict(self)


def _edition_years(db: Session, ids: list[uuid.UUID]) -> dict[uuid.UUID, int | None]:
    """ปีของแต่ละฉบับ ใช้ค่า edition_year ที่เผยแพร่แล้วก่อน ถ้าไม่มีใช้ปีในชื่อหลักสูตร"""
    titles = dict(db.execute(select(Course.id, Course.title).where(Course.id.in_(ids))).all())
    published = dict(
        db.execute(
            text("SELECT course_id, value_int FROM mko.v_live_values WHERE field_key = 'edition_year' AND course_id = ANY(:ids)"),
            {"ids": ids},
        ).all()
    )
    years: dict[uuid.UUID, int | None] = {}
    for course_id in ids:
        if published.get(course_id) is not None:
            years[course_id] = published[course_id]
        else:
            m = _TITLE_YEAR.search(titles.get(course_id, ""))
            years[course_id] = int(m.group(0)) if m else None
    return years


def _titles(db: Session, ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    return dict(db.execute(select(Course.id, Course.title).where(Course.id.in_(ids))).all())


def _scalar_facts(db: Session, field_key: str, ids: list[uuid.UUID], years: dict) -> tuple[list[EditionFact], str | None]:
    rows = db.execute(
        text(
            """
            SELECT course_id, course_title, value_int, value_text, source_filename, page_start, page_end, quote,
                   reviewed_by, publication_id, document_id
              FROM mko.v_live_values WHERE field_key = :field AND course_id = ANY(:ids)
            """
        ),
        {"field": field_key, "ids": ids},
    ).mappings().all()
    facts = [
        EditionFact(
            course_id=str(r["course_id"]), course_title=r["course_title"], edition_year=years.get(r["course_id"]),
            value_int=r["value_int"], value_text=r["value_text"],
            source=Source(r["source_filename"], r["page_start"], r["page_end"], r["quote"],
                          document_id=str(r["document_id"]) if r["document_id"] else None),
            reviewed_by=r["reviewed_by"],
        )
        for r in rows
    ]
    return facts, (str(rows[0]["publication_id"]) if rows else None)


def _list_facts(db: Session, field_key: str, ids: list[uuid.UUID], years: dict) -> tuple[list[EditionFact], str | None]:
    rows = db.execute(
        text(
            """
            SELECT course_id, course_title, seq, text, source_filename, page_start, page_end, reviewed_by,
                   publication_id, document_id
              FROM mko.v_live_list_items WHERE item_type = :item_type AND course_id = ANY(:ids)
             ORDER BY course_id, seq
            """
        ),
        {"item_type": LIST_FIELDS[field_key], "ids": ids},
    ).mappings().all()
    grouped: dict[uuid.UUID, list] = {}
    for r in rows:
        grouped.setdefault(r["course_id"], []).append(r)
    facts = []
    for course_id, items in grouped.items():
        first = items[0]
        facts.append(
            EditionFact(
                course_id=str(course_id), course_title=first["course_title"], edition_year=years.get(course_id),
                items=[i["text"] for i in items],
                source=Source(first["source_filename"], min(i["page_start"] for i in items),
                              max(i["page_end"] for i in items),
                              document_id=str(first["document_id"]) if first["document_id"] else None),
                reviewed_by=first["reviewed_by"],
            )
        )
    return facts, (str(rows[0]["publication_id"]) if rows else None)


def _edition_label(fact: EditionFact) -> str:
    return fact.course_title


def _compose(field_key: str, programme: str, facts: list[EditionFact], missing: list[str]) -> tuple[str, list[str]]:
    lines: list[str] = []
    others: list[str] = []
    if field_key == "total_credits":
        values = {f.value_int for f in facts}
        if len(facts) == 1 or len(values) == 1:
            titles = " และ ".join(_edition_label(f) for f in facts)
            lines.append(f"{titles} มีจำนวนหน่วยกิตรวมตลอดหลักสูตร {facts[0].value_int} หน่วยกิต")
        else:
            lines.append(f"จำนวนหน่วยกิตรวมตลอดหลักสูตรของ{programme} แยกตามหลักสูตร")
            lines.extend(f"- {_edition_label(f)}: {f.value_int} หน่วยกิต" for f in facts)
    elif field_key == "edition_year":
        years = [f"พ.ศ. {f.value_int}" for f in facts]
        if len(facts) == 1:
            lines.append(f"{_edition_label(facts[0])} เป็นหลักสูตรฉบับ {years[0]}")
        else:
            lines.append(f"{programme} มีหลักสูตรฉบับ " + " และ ".join(years))
    else:
        chosen, rest = facts[0], facts[1:]
        lines.append(f"{_LIST_LABEL[field_key]} ตาม{_edition_label(chosen)}")
        lines.extend(f"{n}. {item}" for n, item in enumerate(chosen.items, start=1))
        others = [_edition_label(f) for f in rest]
        if others:
            lines.append("มีข้อมูลของ " + " และ ".join(others) + " ด้วย ระบุปีของหลักสูตรเพื่อดูฉบับนั้น")
        facts = [chosen]
    if missing:
        lines.append("ยังไม่มีข้อมูลที่ผ่านการตรวจของ " + " และ ".join(missing))
    lines.append("ที่มา: " + "; ".join(f.source.label() for f in facts if f.source))
    return "\n".join(lines), others


def lookup(db: Session, intent: StructuredIntent) -> FactsResult:
    """ค่าของ field ที่ถาม เฉพาะที่เผยแพร่แล้ว คืน no_data เมื่อไม่มี"""
    if intent.route != STRUCTURED or not intent.course_ids or intent.field is None:
        return FactsResult(NO_DATA, intent.field, note="not_structured")

    ids = list(intent.course_ids)
    years = _edition_years(db, ids)
    titles = _titles(db, ids)
    if intent.year_be is not None:
        ids = [cid for cid in ids if years.get(cid) == intent.year_be]
        if not ids:
            return FactsResult(NO_DATA, intent.field, note=f"ไม่มีหลักสูตรฉบับ พ.ศ. {intent.year_be} ของ{intent.programme}")

    # ค่าเดี่ยวแสดงทุกฉบับพร้อมชื่อหลักสูตรเต็ม (ซึ่งมีชื่อปริญญาอยู่) จึงไม่มีการเลือกแทนผู้ใช้
    # แต่รายการแสดงฉบับเดียว ถ้าชุดนี้มีหลายระดับปริญญาการหยิบฉบับแรกคือการเดาให้ผู้ใช้ จึงบอกว่ากำกวมแทน
    if intent.field in LIST_FIELDS and len(degree_levels_of(ids, titles)) > 1:
        return FactsResult(NO_DATA, intent.field,
                           note="ชื่อสาขานี้มีหลายระดับปริญญา (" + " และ ".join(sorted(titles[cid] for cid in ids))
                                + ") ระบุระดับปริญญาที่ต้องการ")

    if intent.field in LIST_FIELDS:
        facts, publication_id = _list_facts(db, intent.field, ids, years)
    elif intent.field == "edition_year":
        # ปีของแต่ละฉบับอ่านจาก field edition_year เหมือนค่าเดี่ยวอื่น เพื่อให้มีหลักฐานกำกับ
        facts, publication_id = _scalar_facts(db, "edition_year", ids, years)
    else:
        facts, publication_id = _scalar_facts(db, intent.field, ids, years)

    if not facts:
        return FactsResult(NO_DATA, intent.field, note="ยังไม่มีข้อมูลที่เผยแพร่")

    # ฉบับใหม่ก่อน ปีเดียวกัน (เช่น ปริญญาโทกับเอกที่ใช้ชื่อสาขาเดียวกัน) เรียงตามชื่อเต็มให้ผลคงที่
    facts.sort(key=lambda f: (f.edition_year is None, -(f.edition_year or 0), f.course_title))
    with_data = {f.course_id for f in facts}
    missing = sorted(titles[cid] for cid in ids if str(cid) not in with_data)
    answer, others = _compose(intent.field, intent.programme or "", facts, missing)
    if intent.field in LIST_FIELDS:
        facts = facts[:1]
    return FactsResult(ANSWERED, intent.field, facts, missing, others, publication_id, answer)
