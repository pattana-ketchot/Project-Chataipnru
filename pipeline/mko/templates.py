"""
ตรวจรูปแบบของเอกสาร มคอ. และแบ่งหมวด / ส่วนหน้า / ภาคผนวก

รูปแบบที่พบในคลังจริง (ดู docs/MKO_STRUCTURED_DATA_DESIGN.md หัวข้อ D)
    tqf2      มคอ.2 แบบ TQF เดิม หมวด 1–8 เช่น "หมวดที่ 3 ระบบการจัดการศึกษา การดำเนินการ และโครงสร้างของหลักสูตร"
    std2565   มคอ.2 ตามเกณฑ์ 2565 หมวด 1–9 เช่น "หมวดที่ 3 โครงสร้างหลักสูตร รายวิชา และหน่วยกิต"
    brief     ใบสรุปหลักสูตร ไม่มีหมวด ชื่อหลักสูตรอยู่บรรทัดแรกของหน้าแรก
    web_page  ข้อความจากหน้าเว็บคณะ (.txt)

ตรวจรูปแบบจากหัวข้อที่พบ ไม่ใช่จากปี เพราะเล่มปรับปรุงปี 2565 บางเล่มยังเป็น TQF ที่เพิ่ม PLO เข้าไป

หาหมวดเรียงจาก 1 ขึ้นไป เริ่มค้นหมวดถัดไปหลังหมวดก่อนหน้า และข้ามหน้าสารบัญ เพราะคำว่า "หมวดที่ 1–11" ปรากฏซ้ำใน
ภาคผนวก (ข้อบังคับมหาวิทยาลัยมีหมวดของตัวเอง) และในตารางเปรียบเทียบหลักสูตรเดิม ถ้าหาแบบไม่เรียงลำดับจะได้หมวดจาก
ภาคผนวกมาแทนหมวดจริง
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from pipeline.mko.doc import PAGE_JOIN, DocText
from pipeline.mko.normalize import fold

FULL_TEMPLATES = ("tqf2", "std2565")
TEMPLATES = ("tqf2", "std2565", "brief", "web_page", "unknown")

_CHAPTERS: dict[str, dict[int, tuple[str, ...]]] = {
    "tqf2": {
        1: ("ข้อมูลทั่วไป",),
        2: ("ข้อมูลเฉพาะ",),
        3: ("ระบบการจัดการศึกษา",),
        4: ("ผลการเรียนรู้", "กลยุทธ์การสอน"),
        5: ("หลักเกณฑ์ในการประเมินผล",),
        6: ("การพัฒนาคณาจารย์",),
        7: ("การประกันคุณภาพ",),
        8: ("การประเมินและปรับปรุง",),
    },
    "std2565": {
        1: ("ข้อมูลทั่วไป",),
        2: ("ปรัชญา",),
        3: ("โครงสร้างหลักสูตร",),
        4: ("การจัดกระบวนการเรียนรู้",),
        5: ("ความพร้อม",),
        6: ("คุณสมบัติของผู้เข้าศึกษา",),
        7: ("การประเมินผลการเรียน",),
        8: ("การประกันคุณภาพ",),
        9: ("ระบบกลไก",),
    },
}

# หมวดที่ชื่อไม่ซ้ำกับอีกรูปแบบ ใช้ตัดสินว่าเป็นรูปแบบไหน
_DISTINCTIVE = {"tqf2": (2, 3), "std2565": (3, 6)}
# หมวดที่ใช้เป็นจุดเริ่มหาภาคผนวก (หมวดสุดท้ายที่ตัวสกัดใช้ ถ้าไม่พบให้ถอยไปหมวดก่อนหน้า)
_APPENDIX_ANCHOR = {"tqf2": (3, 2, 1), "std2565": (6, 3, 1)}

_APPENDIX = fold("ภาคผนวก")
_HEADER_NOISE = re.compile(r"[\d.|:()]|มคอ")


@dataclass(frozen=True)
class Section:
    key: str
    heading: str
    start: int
    end: int
    is_appendix: bool = False


def section_named(sections: list[Section], key: str) -> Section | None:
    return next((s for s in sections if s.key == key), None)


def _chapter_pattern(number: int, names: tuple[str, ...]) -> re.Pattern:
    alternatives = "|".join(re.escape(fold(name)) for name in names)
    return re.compile(re.escape(fold("หมวดที่")) + str(number) + r"(?!\d)[:.]?(?:" + alternatives + ")")


def locate_chapters(doc: DocText, template: str) -> dict[int, tuple[int, int]]:
    """หมวดที่พบ: เลขหมวด -> (ตำแหน่งเริ่มหัวข้อ, ตำแหน่งจบหัวข้อ) ในข้อความต้นฉบับ"""
    found: dict[int, tuple[int, int]] = {}
    pos = 0
    for number, names in _CHAPTERS[template].items():
        hit = doc.find(_chapter_pattern(number, names), pos)
        if hit:
            found[number] = (hit[0], hit[1])
            pos = hit[1]
    return found


def _is_appendix_page(text: str) -> bool:
    """หน้าเริ่มภาคผนวก: บรรทัดช่วงต้นหน้าขึ้นต้นด้วย "ภาคผนวก" (ยอมให้มีเลขหน้าหรือคำว่า มคอ.2 นำหน้าได้)"""
    lines = [line for line in text.split("\n") if line.strip()][:5]
    for line in lines:
        folded = fold(line)
        at = folded.find(_APPENDIX)
        if at >= 0 and not _HEADER_NOISE.sub("", folded[:at]):
            return True
    return False


def appendix_start(doc: DocText, after: int) -> int | None:
    for index in range(doc.page_index(after) + 1, len(doc.pages)):
        page = doc.pages[index]
        if not page.is_toc and _is_appendix_page(page.text):
            return doc.page_start(index)
    return None


def detect_template(doc: DocText) -> str:
    if doc.filename.lower().endswith(".txt"):
        return "web_page"
    # เลือกรูปแบบที่หมวดเฉพาะของตัวเองปรากฏเร็วที่สุด เพราะภาคผนวกของเล่มใหม่อาจแนบเล่มเดิมที่เป็นอีกรูปแบบไว้
    best: tuple[str, int] | None = None
    for template in FULL_TEMPLATES:
        chapters = locate_chapters(doc, template)
        if 1 not in chapters:
            continue
        positions = [chapters[n][0] for n in _DISTINCTIVE[template] if n in chapters]
        if positions and (best is None or min(positions) < best[1]):
            best = (template, min(positions))
    if best:
        return best[0]
    early = fold(PAGE_JOIN.join(page.text for page in doc.pages[:3]))
    if fold("วัตถุประสงค์ของหลักสูตร") in early and fold("จำนวนหน่วยกิต") in early:
        return "brief"
    return "unknown"


def build_sections(doc: DocText, template: str) -> tuple[list[Section], int]:
    """หมวดทั้งหมดที่พบ พร้อมตำแหน่งจบของเนื้อหาหลัก (ก่อนภาคผนวก)"""
    end_of_doc = len(doc.text)
    if template not in FULL_TEMPLATES:
        return [Section("document", "", 0, end_of_doc)], end_of_doc

    chapters = locate_chapters(doc, template)
    anchor = next((chapters[n][0] for n in _APPENDIX_ANCHOR[template] if n in chapters), 0)
    appendix = appendix_start(doc, anchor)
    body_end = appendix if appendix is not None else end_of_doc

    ordered = sorted(((n, s, e) for n, (s, e) in chapters.items() if s < body_end), key=lambda item: item[1])
    sections: list[Section] = []
    if ordered and ordered[0][1] > 0:
        sections.append(Section("front", "", 0, ordered[0][1]))
    for i, (number, start, heading_end) in enumerate(ordered):
        end = ordered[i + 1][1] if i + 1 < len(ordered) else body_end
        heading = re.sub(r"\s+", " ", doc.slice(start, heading_end)).strip()
        sections.append(Section(f"chapter.{number}", heading, start, max(end, heading_end)))
    if appendix is not None:
        sections.append(Section("appendix", "ภาคผนวก", appendix, end_of_doc, True))
    return sections, body_end
