"""
ตอบคำถามรายวิชาจากข้อมูลที่ตรวจรับและเผยแพร่แล้ว — รหัส ชื่อ หน่วยกิต ข้อกำหนด และวิชาบังคับก่อน

อ่านเฉพาะ `mko.v_live_subjects` และ `mko.v_live_subject_prerequisites` ของการเผยแพร่
ครั้งล่าสุด (ดู db/migrations/002_mko_subjects_published.sql) ไม่อ่านตารางฝั่งสกัด

สามเรื่องที่โมดูลนี้ตั้งใจไม่ทำ
-----------------------------
1. **ไม่เรียกรายวิชาที่ต้องเลือกจากกลุ่มว่าเป็นวิชาบังคับ** ข้อกำหนดในข้อมูลมีสามค่า
   required (บังคับ/แกน/เฉพาะด้าน) · elective (กลุ่มวิชาเลือก/เลือกเสรี) ·
   choose_group (เลือกจากกลุ่มให้ครบหน่วยกิตขั้นต่ำ เช่น ฝึกประสบการณ์/สหกิจศึกษา)
   คำตอบ "วิชาบังคับมีอะไรบ้าง" จึงนับเฉพาะ required แล้วบอกกลุ่มที่ต้องเลือกแยกให้เห็น

2. **ไม่สรุปว่าไม่มีวิชาบังคับก่อนเพียงเพราะตารางว่าง** แยกสองกรณีให้ชัด
   - หลักสูตรนี้มีแถววิชาบังคับก่อนอยู่แล้ว (แปลว่าเอกสารถูกอ่านครบ) แต่ไม่มีของวิชานี้
     -> "เอกสารไม่ได้ระบุวิชาบังคับก่อนของวิชานี้"
   - หลักสูตรนี้ยังไม่มีแถววิชาบังคับก่อนเลย -> "ข้อมูลยังไม่ครบ ยังสรุปไม่ได้"

3. **ไม่สรุปว่าหลักสูตรไม่มีรายวิชา** ถ้าหลักสูตรนั้นยังไม่มีข้อมูลรายวิชาในระบบเลย
   จะคืน None เพื่อให้ผู้เรียกไปเส้นทางค้นเอกสารตามเดิม

ทนกับฐานที่ยัง **ไม่ได้รัน migration 002**: ถ้าไม่มีวิวจะคืน None เงียบ ๆ (เตือนครั้งเดียว)
เพราะการ deploy โค้ดกับการรัน migration เป็นสองขั้นที่แยกกัน
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from app.services.course_scope import resolve_scopes
from app.services.structured_intent import years_in

logger = logging.getLogger("course_advisor")

_WARNED: set[str] = set()

# รหัสวิชาเจ็ดหลัก ("4121202") — ต้องไม่ชนกับปี พ.ศ. สี่หลัก
_CODE = re.compile(r"(?<!\d)(\d{7})(?!\d)")

_ASKS_NAME = re.compile(r"ชื่อว่าอะไร|ชื่ออะไร|ชื่อวิชา|วิชาอะไร|คือวิชา|คืออะไร")
_ASKS_CREDITS = re.compile(r"กี่หน่วยกิต|หน่วยกิตเท่าไ|จำนวนหน่วยกิต")
_ASKS_PREREQ = re.compile(r"บังคับก่อน|ต้องเรียน.{0,12}?มาก่อน|เรียนมาก่อน|prerequisite", re.I)
# "วิชาบังคับ" ที่ไม่ได้ตามด้วย "ก่อน"
_ASKS_REQUIRED = re.compile(r"วิชาบังคับ(?!ก่อน)")
_ASKS_ELECTIVE = re.compile(r"วิชาเลือก")
_LIST_TAIL = re.compile(r"อะไรบ้าง|มีอะไร|บ้าง|ประกอบด้วย|รายการ|รายชื่อ|กี่วิชา")

# คำที่บอกว่ากำลังถามถึง "ชุดของวิชา" ไม่ใช่วิชาเดียว
_GROUP_WORD = re.compile(r"กลุ่ม|หมวดวิชา")


def _is_group_question(question: str) -> bool:
    """
    คำถามระดับกลุ่ม/หมวด เช่น "กลุ่มวิชาฝึกประสบการณ์วิชาชีพหรือสหกิจศึกษา มีวิชาอะไรบ้าง"

    ต้องแยกออกจากคำถามรายวิชา เพราะ**ชื่อกลุ่มกับชื่อวิชามักมีคำซ้ำกัน** —
    กลุ่ม "ฝึกประสบการณ์วิชาชีพหรือสหกิจศึกษา" มีวิชาชื่อ "สหกิจศึกษา" อยู่ข้างใน
    การจับคู่ด้วยชื่อจึงเจอวิชาเดียวแล้วตอบรายละเอียดของวิชานั้น ทั้งที่ผู้ถามขอทั้งกลุ่ม
    (พบจากการใช้งานจริง 19 ต.ค. 2569: ถามรายชื่อ 3 วิชาในกลุ่ม ได้คำตอบเฉพาะ 4124815)

    ต้องเข้าเงื่อนไขทั้งสองอย่าง: เอ่ยถึงกลุ่ม/หมวด **และ** ถามแบบรายการ
    ถ้าถามแค่ว่า "วิชานี้อยู่กลุ่มไหน" ยังเป็นคำถามรายวิชาตามเดิม
    """
    return bool(_GROUP_WORD.search(question) and _LIST_TAIL.search(question))

_SOURCE_LABEL = "ที่มา:"


@dataclass
class SubjectAnswer:
    text: str
    sources: list[dict] = field(default_factory=list)


def _rows(db: Session, sql: str, params: dict) -> list[dict] | None:
    """คืน None เมื่อยังไม่มีวิวในฐานนี้ (ยังไม่ได้รัน migration 002)"""
    try:
        return [dict(r) for r in db.execute(text(sql), params).mappings().all()]
    except ProgrammingError:
        db.rollback()
        if "subjects_view" not in _WARNED:
            _WARNED.add("subjects_view")
            logger.warning("ยังไม่มี mko.v_live_subjects ในฐานนี้ — ข้ามการตอบรายวิชา "
                           "(ต้องรัน db/migrations/002_mko_subjects_published.sql ก่อน)")
        return None


def _scope_ids(db: Session, question: str) -> list[str]:
    return [str(cid) for scope in resolve_scopes(db, question) for cid in scope.course_ids]


def _source_of(row: dict) -> dict:
    return {"file": row["source_filename"], "page_start": row["page_start"],
            "page_end": row["page_end"], "course_title": row["course_title"],
            "document_id": str(row["document_id"]) if row.get("document_id") else None}


def _cite(rows: list[dict]) -> str:
    seen: list[str] = []
    for r in rows:
        label = f"{r['source_filename']} หน้า {r['page_start']}"
        if label not in seen:
            seen.append(label)
    return f"{_SOURCE_LABEL} " + "; ".join(seen)


def _requirement_label(value: str) -> str:
    return {"required": "วิชาบังคับ",
            "elective": "วิชาเลือก",
            "choose_group": "วิชาในกลุ่มที่ต้องเลือกให้ครบหน่วยกิตขั้นต่ำ",
            # ต้องเรียนแน่นอน แต่กลุ่มของมันมีเพดานขั้นต่ำกำกับอยู่ จึงไม่ถูกนับรวม
            # ในยอด "วิชาบังคับ" ที่เล่มพิมพ์ไว้ (ดู db/migrations/009)
            "required_in_group": "วิชาที่ต้องเรียนในกลุ่มที่มีหน่วยกิตขั้นต่ำ"}.get(value, value)


def _prerequisites(db: Session, row: dict) -> list[dict]:
    """รายการวิชาบังคับก่อนของวิชานี้ (เฉพาะที่มีหลักฐาน)"""
    return _rows(db, """
        SELECT subject_code, prerequisite_code, prerequisite_name_th,
               source_filename, page_start, page_end, document_id, course_title
          FROM mko.v_live_subject_prerequisites
         WHERE course_id = :c AND subject_code = :code
         ORDER BY prerequisite_code
    """, {"c": row["course_id"], "code": row["code"]}) or []


def _answer_one(db: Session, row: dict, question: str) -> SubjectAnswer:
    """คำตอบของรายวิชาหนึ่งวิชา ตามสิ่งที่คำถามถาม"""
    head = f"วิชา {row['code']} {row['name_th']}"
    if row.get("name_en"):
        head += f" ({row['name_en']})"

    lines: list[str] = []
    sources = [_source_of(row)]

    if _ASKS_PREREQ.search(question):
        mine = _prerequisites(db, row)
        checked_page = row.get("prereq_checked_page")
        lines.append(head)
        if mine:
            lines.append("มีวิชาบังคับก่อน ดังนี้")
            for p in mine:
                name = p.get("prerequisite_name_th") or ""
                lines.append(f"- {p['prerequisite_code']}" + (f" {name}" if name else ""))
            sources += [_source_of(p) for p in mine]
            lines.append(_cite([row] + mine))
        elif checked_page:
            # มีหลักฐานว่าอ่านคำอธิบายของ "วิชานี้" แล้ว จึงพูดแทนเอกสารได้
            #
            # ห้ามใช้จำนวนแถวของวิชาอื่นมาตัดสินความครบของวิชานี้ — รอบแรกทำแบบนั้น
            # แล้ววิชา 33 ตัวที่ไม่มีคำอธิบายในเล่มจะถูกสรุปว่า "เอกสารไม่ได้ระบุ"
            # ทั้งที่ยังไม่มีใครอ่าน (วัดเมื่อ 14 ต.ค. 2569)
            lines.append(f"เอกสารที่ตรวจแล้วไม่ได้ระบุวิชาบังคับก่อนของวิชานี้ครับ "
                         f"(ตรวจคำอธิบายรายวิชาของวิชานี้ที่ {row['source_filename']} "
                         f"หน้า {checked_page} แล้วไม่พบข้อความระบุวิชาบังคับก่อน)")
            sources.append({"file": row["source_filename"], "page_start": checked_page,
                            "page_end": checked_page, "course_title": row["course_title"],
                            "document_id": (str(row["document_id"])
                                            if row.get("document_id") else None)})
            lines.append(f"{_SOURCE_LABEL} {row['source_filename']} หน้า {row['page_start']}; "
                         f"{row['source_filename']} หน้า {checked_page}")
        else:
            lines.append("ยังไม่พบข้อมูลวิชาบังคับก่อนของวิชานี้ในข้อมูลของระบบครับ "
                         "และยังไม่มีหลักฐานว่าได้ตรวจคำอธิบายรายวิชาของวิชานี้แล้ว "
                         "จึงยังสรุปไม่ได้ว่ามีวิชาบังคับก่อนหรือไม่ "
                         "รบกวนสอบถามฝ่ายวิชาการของคณะเพื่อความแน่นอน")
            lines.append(_cite([row]))
        return SubjectAnswer("\n".join(lines), sources)

    detail = [f"{row['credits']} หน่วยกิต" if row["credits"] is not None else None,
              row.get("hours_pattern"),
              _requirement_label(row["requirement"])]
    lines.append(head)
    lines.append(" · ".join(d for d in detail if d))
    if row.get("category_path"):
        lines.append("หมวด: " + " > ".join([row["section"]] + list(row["category_path"])
                                            if row.get("section") else list(row["category_path"])))
    lines.append(f"อยู่ในหลักสูตร: {row['course_title']}")
    lines.append(_cite([row]))
    return SubjectAnswer("\n".join(lines), sources)


def _answer_list(db: Session, ids: list[str], question: str, want: str) -> SubjectAnswer | None:
    rows = _rows(db, """
        SELECT code, name_th, credits, requirement, section, category_path,
               source_filename, page_start, page_end, document_id, course_title, course_id
          FROM mko.v_live_subjects
         WHERE course_id = ANY(:ids)
         ORDER BY course_title, requirement, category_path, code
    """, {"ids": ids})
    if not rows:
        return None

    picked = [r for r in rows if r["requirement"] == want]
    if not picked:
        return None

    by_group: dict[str, list[dict]] = {}
    for r in picked:
        group = " > ".join(r["category_path"]) if r["category_path"] else "ไม่ระบุกลุ่ม"
        by_group.setdefault(group, []).append(r)

    title = rows[0]["course_title"]
    label = _requirement_label(want)
    lines = [f"{label}ของ{title} แยกตามกลุ่ม", ""]
    total = 0
    for group, items in by_group.items():
        credits = sum(i["credits"] or 0 for i in items)
        lines.append(f"{group} ({len(items)} วิชา รวม {credits} หน่วยกิต)")
        for i in items:
            lines.append(f"- {i['code']} {i['name_th']} "
                         f"{i['credits'] if i['credits'] is not None else '-'} หน่วยกิต")
        lines.append("")
        total += credits

    lines.append(f"รวม{label} {len(picked)} วิชา {total} หน่วยกิต")

    # กลุ่มที่มีเพดานขั้นต่ำไม่ได้นับรวมในยอดข้างบน จึงต้องบอกแยกให้เห็น ไม่ใช่เงียบไป
    #
    # แยกสองอย่างในกลุ่มเดียวกันด้วย: วิชาที่ต้องเรียนแน่นอน กับวิชาที่ให้เลือก
    # ถ้ารวมเป็นก้อนเดียว ผู้อ่านจะเข้าใจว่าทั้งกลุ่มเป็นของให้เลือก ซึ่งไม่ตรงกับเล่ม
    if want == "required":
        in_group = [r for r in rows if r["requirement"] == "required_in_group"]
        choose = [r for r in rows if r["requirement"] == "choose_group"]
        if in_group or choose:
            groups = sorted({" > ".join(r["category_path"]) if r["category_path"]
                             else "ไม่ระบุกลุ่ม" for r in in_group + choose})
            lines.append("")
            lines.append(f"ยอดข้างบนไม่รวม {', '.join(groups)} ซึ่งเล่มนับแยกต่างหาก")
            for r in in_group:
                lines.append(f"- {r['code']} {r['name_th']} "
                             f"{r['credits'] if r['credits'] is not None else '-'} หน่วยกิต "
                             f"(ต้องเรียน)")
            if choose:
                names = ", ".join(f"{c['code']} {c['name_th']} "
                                  f"{c['credits'] if c['credits'] is not None else '-'} หน่วยกิต"
                                  for c in choose)
                lines.append(f"- เลือกจาก: {names}")
            lines.append("หน่วยกิตขั้นต่ำของกลุ่มนี้ดูได้จากเอกสารหลักสูตร "
                         "ข้อมูลที่ตรวจรับแล้วยังไม่ได้เก็บตัวเลขนั้นไว้")
    lines.append(_cite(picked))
    return SubjectAnswer("\n".join(lines), [_source_of(r) for r in picked[:12]])


def answer_subject_question(db: Session, question: str) -> SubjectAnswer | None:
    """
    คำตอบเรื่องรายวิชาจากข้อมูลที่เผยแพร่แล้ว หรือ None = ให้ผู้เรียกไปเส้นทางเดิม

    ไม่โยน exception — ความผิดพลาดของการตอบรายวิชาห้ามทำให้ตอบผู้ใช้ไม่ได้
    """
    try:
        codes = _CODE.findall(question)
        ids = _scope_ids(db, question)
        years = years_in(question)

        # 1) ถามถึงรหัสวิชาตรง ๆ
        if codes:
            rows = _rows(db, """
                SELECT code, name_th, name_en, credits, hours_pattern, requirement,
                       prereq_checked_page, section, category_path, source_filename,
                       page_start, page_end, document_id, course_title, course_id
                  FROM mko.v_live_subjects WHERE code = ANY(:codes)
                 ORDER BY course_title
            """, {"codes": codes})
            if rows is None:
                return None
            if ids:
                narrowed = [r for r in rows if str(r["course_id"]) in ids]
                rows = narrowed or rows
            if rows:
                return _answer_one(db, rows[0], question)
            # ไม่พบรหัสนี้ — บอกได้ว่ายังไม่พบ "ก็เมื่อระบบมีข้อมูลรายวิชาอยู่แล้ว"
            any_rows = _rows(db, "SELECT 1 FROM mko.v_live_subjects LIMIT 1", {})
            if any_rows:
                return SubjectAnswer(
                    f"ยังไม่พบรายวิชารหัส {codes[0]} ในข้อมูลของระบบครับ "
                    f"ตอนนี้ระบบมีข้อมูลรายวิชาของบางหลักสูตรเท่านั้น "
                    f"กรุณาตรวจรหัสอีกครั้ง หรือสอบถามฝ่ายวิชาการของคณะ")
            return None

        if not ids:
            return None

        # 2) รายการวิชาบังคับ / วิชาเลือกของหลักสูตร
        if _LIST_TAIL.search(question):
            if _ASKS_REQUIRED.search(question) and not _ASKS_PREREQ.search(question):
                return _answer_list(db, ids, question, "required")
            if _ASKS_ELECTIVE.search(question):
                return _answer_list(db, ids, question, "elective")

        # 3) ถามถึงวิชาด้วยชื่อ (ต้องถามเรื่องที่ข้อมูลตอบได้: ชื่อ หน่วยกิต หรือบังคับก่อน)
        #
        # คำถามระดับกลุ่มห้ามตกมาถึงตรงนี้ เพราะการจับคู่ด้วยชื่อจะยุบคำถามทั้งกลุ่ม
        # ให้เหลือวิชาเดียวเสมอ (ดู _is_group_question)
        #
        # ปล่อยให้ไปเส้นทางค้นเอกสารแทนการตอบรายการจากฐานข้อมูล เพราะ**เงื่อนไขของกลุ่ม
        # ไม่ได้อยู่ในข้อมูลที่มีโครงสร้าง** — หน่วยกิตขั้นต่ำของกลุ่มและกติกาการเลือก
        # อยู่ในเนื้อความของเอกสารเท่านั้น (cs66.pdf หน้า 19: "ไม่น้อยกว่า 7 หน่วยกิต"
        # และ "ให้เลือกรายวิชาต่อไปนี้ ไม่น้อยกว่า 5 หน่วยกิต") ถ้าตอบจากตารางรายวิชา
        # อย่างเดียวจะได้รายชื่อครบแต่**ขาดเงื่อนไข** ซึ่งอ่านแล้วเข้าใจผิดได้
        if _is_group_question(question):
            return None
        if not (_ASKS_PREREQ.search(question) or _ASKS_CREDITS.search(question)
                or _ASKS_NAME.search(question)):
            return None
        rows = _rows(db, """
            SELECT code, name_th, name_en, credits, hours_pattern, requirement,
                   prereq_checked_page, section, category_path, source_filename,
                   page_start, page_end, document_id, course_title, course_id
              FROM mko.v_live_subjects WHERE course_id = ANY(:ids)
        """, {"ids": ids})
        if not rows:
            return None
        hits = [r for r in rows if r["name_th"] and r["name_th"] in question]
        if not hits:
            return None
        # ชื่อที่ยาวที่สุดคือชื่อที่เจาะจงที่สุด ("ระบบฐานข้อมูลขั้นสูง" ชนะ "ระบบฐานข้อมูล")
        hits.sort(key=lambda r: len(r["name_th"]), reverse=True)
        if years:
            same_year = [r for r in hits if str(years[0]) in (r["course_title"] or "")]
            hits = same_year or hits
        return _answer_one(db, hits[0], question)
    except Exception:  # noqa: BLE001
        logger.warning("ตอบคำถามรายวิชาไม่สำเร็จ — ใช้เส้นทางเดิมแทน", exc_info=True)
        return None
