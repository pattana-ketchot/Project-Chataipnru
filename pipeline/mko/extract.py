"""
สกัดข้อมูลพื้นฐานของหลักสูตรจากเอกสารหนึ่งไฟล์ (Phase 1) — ไม่แตะฐานข้อมูล

ข้อมูลที่สกัด: ชื่อหลักสูตร/สาขา (ไทย-อังกฤษ), ชื่อปริญญาและอักษรย่อ, ระดับการศึกษา, ปีหลักสูตรและประเภท,
จำนวนหน่วยกิตรวม, วัตถุประสงค์, อาชีพหลังสำเร็จการศึกษา, คุณสมบัติผู้เข้าศึกษา

รายวิชาและ PLO ยังไม่มีตัวสกัดใน Phase 1 (มีตารางเตรียมไว้ใน db/migrations/001_mko_structured.sql)
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from pipeline.mko import fields
from pipeline.mko.decide import FieldDecision, ListDecision, decide_list, decide_scalar, derive
from pipeline.mko.doc import DocText
from pipeline.mko.fields import Located
from pipeline.mko.normalize import fold
from pipeline.mko.templates import Section, build_sections, detect_template

PARSER_VERSION = "mko-phase1-2026.09.15"

SCALAR_FIELDS = (
    "program_name_th", "program_name_en",
    "degree_name_th", "degree_abbr_th", "degree_name_en", "degree_abbr_en", "degree_level",
    "edition_year", "revision_type", "total_credits",
)
LIST_FIELDS = (("objectives", "objective"), ("careers", "career"), ("admission", "admission"))


@dataclass
class DocumentExtraction:
    template: str
    sections: list[Section]
    body_end: int
    scalars: list[FieldDecision]
    lists: list[ListDecision]


def distinctive_name(course_title: str) -> str:
    """ชื่อสาขาจากชื่อหลักสูตรในระบบ เช่น "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาคณิตศาสตร์ (พ.ศ. 2569)" -> "คณิตศาสตร์" """
    name = re.sub(r"\s*\(.*?\)\s*$", "", course_title).strip()
    if "สาขาวิชา" in name:
        return name.split("สาขาวิชา", 1)[1].strip()
    return re.sub(r"^หลักสูตร", "", name).replace("บัณฑิต", "").strip()


def title_year(course_title: str) -> int | None:
    m = re.search(r"25\d{2}", course_title)
    return int(m.group(0)) if m else None


def degree_level_of(text: str) -> str | None:
    folded = fold(text)
    if fold("ดุษฎีบัณฑิต") in folded:
        return "doctoral"
    if fold("มหาบัณฑิต") in folded:
        return "master"
    if fold("บัณฑิต") in folded:
        return "bachelor"
    return None


def extract_document(doc: DocText, course_title: str) -> DocumentExtraction:
    template = detect_template(doc)
    sections, body_end = build_sections(doc, template)
    args = (doc, template, sections, body_end)

    expected_name = distinctive_name(course_title)
    expected_year = title_year(course_title)

    def name_check(loc: Located) -> str | None:
        if fold(expected_name) in fold(loc.value_text or ""):
            return None
        return f"ชื่อไม่มีชื่อสาขา \"{expected_name}\" ของหลักสูตรในระบบ"

    def english_check(loc: Located) -> str | None:
        return None if re.match(r"(Bachelor|Master|Doctor) of", loc.value_text or "") else "ไม่ขึ้นต้นด้วยชื่อระดับปริญญาภาษาอังกฤษ"

    def thai_degree_check(loc: Located) -> str | None:
        return None if fold("บัณฑิต") in fold(loc.value_text or "") else "ชื่อปริญญาไม่มีคำว่าบัณฑิต"

    def thai_abbr_check(loc: Located) -> str | None:
        return None if re.match(r"[ก-๙]{1,6}\.\s*[ก-๙]{0,3}\.?", loc.value_text or "") else "อักษรย่อปริญญาภาษาไทยผิดรูปแบบ"

    def english_abbr_check(loc: Located) -> str | None:
        return None if re.match(r"[A-Za-z]{1,6}\.", loc.value_text or "") else "อักษรย่อปริญญาภาษาอังกฤษผิดรูปแบบ"

    def year_check(loc: Located) -> str | None:
        year = loc.value_int or 0
        if not 2500 <= year <= 2700:
            return f"ปี {year} อยู่นอกช่วงที่เป็นไปได้"
        if expected_year and year != expected_year:
            return f"ปีในเอกสาร ({year}) ไม่ตรงกับปีในชื่อหลักสูตรในระบบ ({expected_year})"
        return None

    def credit_check(loc: Located) -> str | None:
        return None if 1 <= (loc.value_int or 0) <= 250 else f"จำนวนหน่วยกิต {loc.value_int} อยู่นอกช่วงที่เป็นไปได้"

    names = fields.extract_names(*args)
    degree = fields.extract_degree(*args)
    years = fields.extract_year(*args)
    credits = fields.extract_total_credits(*args)

    scalars: list[FieldDecision] = []
    scalars += decide_scalar(doc, "program_name_th", names["program_name_th"], name_check)
    scalars += decide_scalar(doc, "program_name_en", names["program_name_en"], english_check)
    scalars += decide_scalar(doc, "degree_name_th", degree["degree_name_th"], thai_degree_check)
    scalars += decide_scalar(doc, "degree_abbr_th", degree["degree_abbr_th"], thai_abbr_check)
    scalars += decide_scalar(doc, "degree_name_en", degree["degree_name_en"], english_check)
    scalars += decide_scalar(doc, "degree_abbr_en", degree["degree_abbr_en"], english_abbr_check)

    # ระดับการศึกษาอนุมานจากชื่อปริญญา ถ้าเอกสารไม่มีชื่อปริญญาเต็ม (ใบสรุป) ใช้ชื่อหลักสูตร
    degree_source = [d for d in scalars if d.field_key == "degree_name_th" and d.status != "not_found"] or \
        [d for d in scalars if d.field_key == "program_name_th"]
    scalars += derive("degree_level", degree_source, degree_level_of)

    year_values = [Located(None, loc.value_int, loc.start, loc.end, loc.location) for loc in years]
    revision_values = [Located(loc.value_text, None, loc.start, loc.end, loc.location) for loc in years]
    scalars += decide_scalar(doc, "edition_year", year_values, year_check)
    scalars += decide_scalar(doc, "revision_type", revision_values)
    scalars += decide_scalar(doc, "total_credits", credits, credit_check)

    extractors = {
        "objectives": fields.extract_objectives,
        "careers": fields.extract_careers,
        "admission": fields.extract_admission,
    }
    lists = [decide_list(doc, key, item_type, extractors[key](*args)) for key, item_type in LIST_FIELDS]
    return DocumentExtraction(template, sections, body_end, scalars, lists)
