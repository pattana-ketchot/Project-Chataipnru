"""
ตัวสกัดค่าจากเอกสาร มคอ. — หาตำแหน่งตามหัวข้อของรูปแบบเอกสาร แล้วตัดค่าจากข้อความต้นฉบับ

ทุกฟังก์ชันคืน "ตำแหน่งที่พบ" พร้อมช่วงข้อความต้นฉบับเท่านั้น ไม่ตัดสินสถานะ (ดู decide.py) และไม่เรียกโมเดลภาษา
ถ้าหาหัวข้อไม่เจอจะคืนรายการว่างหรือ None ไม่มีค่าตั้งต้นหรือค่าที่เดาจากที่อื่น

รูปแบบที่ค้นเขียนในรูปที่ใช้ค้น (normalize.fold: ตัดช่องว่าง, ำ → า, เลขไทย → อารบิก) ผ่านฟังก์ชัน lit
ส่วนเลขข้อและเครื่องหมายเขียนเป็น regex ตรงๆ เพราะ fold ไม่เปลี่ยนตัวอักษรเหล่านั้น

ตำแหน่งที่ค้นอิงจากเอกสารจริงในคลัง (สำรวจทั้ง 31 ไฟล์ก่อนเขียน) เช่น
    หน่วยกิตรวม  หมวด 1 ข้อ 4 และหมวด 3 ข้อ 3.1.1 (TQF) / หมวด 3 ข้อ 1.1 (เกณฑ์ 2565) — ไม่ค้นในภาคผนวก เพราะ
                ตารางเปรียบเทียบหลักสูตรเดิมมีตัวเลขของฉบับเก่า (เช่น cs61 หน้า 185 "ไม่น้อยกว่า 120")
    ปีหลักสูตร   ส่วนหน้าก่อนหมวด 1 และหมวด 1 ข้อ 6.1 — ต้องอยู่ติด "หลักสูตรปรับปรุง/ใหม่ พ.ศ." ไม่เอาปีที่ตามหลัง
                "ปรับปรุงจากหลักสูตร ... พ.ศ. 2555"
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from pipeline.mko.doc import DocText
from pipeline.mko.normalize import fold, squash
from pipeline.mko.templates import FULL_TEMPLATES, Section, section_named


def lit(text: str) -> str:
    return re.escape(fold(text))


def rx(*parts: str) -> re.Pattern:
    return re.compile("".join(parts))


@dataclass(frozen=True)
class Located:
    """ค่าหนึ่งค่าที่พบ พร้อมช่วงข้อความต้นฉบับที่ใช้เป็นหลักฐาน"""

    value_text: str | None
    value_int: int | None
    start: int
    end: int
    location: str
    method: str = "regex"


@dataclass(frozen=True)
class ListLocated:
    """รายการข้อความที่พบ: ช่วงของหัวข้อทั้งก้อน และช่วงของแต่ละข้อ"""

    location: str
    start: int
    end: int
    items: tuple[tuple[int, int], ...]
    items_method: str  # numbered | bullet | paragraph
    irregular_numbering: bool = False  # เลขข้อในเอกสารข้ามหรือซ้ำ เช่น 8.7, 8.9, 8.9 (it66)


# --------------------------------------------------------------------------------------------
# หน่วยกิตรวม
# --------------------------------------------------------------------------------------------

CREDIT_RX = rx(
    lit("จำนวนหน่วยกิต"), "(?:", lit("รวม"), ")?(?:", lit("ที่เรียน"), ")?", lit("ตลอดหลักสูตร"),
    r"[^0-9]{0,40}?(\d{2,3})", lit("หน่วยกิต"),
)


def _collect_ints(doc: DocText, pattern: re.Pattern, start: int, end: int, location: str,
                  group: int = 1, first_only: bool = False) -> list[Located]:
    found: list[Located] = []
    if start >= end:
        return found
    for s, e, m in doc.find_all(pattern, start, end):
        found.append(Located(None, int(m.group(group)), s, e, location))
        if first_only:
            break
    return found


def _first_page_end(doc: DocText, pages: int) -> int:
    return doc.page_end(min(pages, len(doc.pages)) - 1)


def extract_total_credits(doc: DocText, template: str, sections: list[Section], body_end: int) -> list[Located]:
    found: list[Located] = []
    chapter1 = section_named(sections, "chapter.1")
    if template in FULL_TEMPLATES and chapter1:
        head = doc.find(rx(r"4\.", lit("จำนวนหน่วยกิต")), chapter1.start, chapter1.end)
        if head:
            stop = doc.find(rx(r"5\.", lit("รูปแบบ")), head[1], chapter1.end)
            end = stop[0] if stop else min(chapter1.end, head[1] + 800)
            found += _collect_ints(doc, CREDIT_RX, head[0], end, "chapter1.item4")
    if template == "tqf2":
        after = chapter1.end if chapter1 else 0
        head = doc.find(rx(r"3\.1\.1", lit("จำนวนหน่วยกิต")), after, body_end)
        if head:
            stop = doc.find(rx(r"3\.1\.2"), head[1], body_end)
            end = stop[0] if stop else min(body_end, head[1] + 600)
            found += _collect_ints(doc, CREDIT_RX, head[0], end, "chapter3.item3.1.1")
    elif template == "std2565":
        chapter3 = section_named(sections, "chapter.3")
        if chapter3:
            stop = doc.find(rx(r"1\.2", lit("โครงสร้าง")), chapter3.start, chapter3.end)
            found += _collect_ints(doc, CREDIT_RX, chapter3.start, stop[0] if stop else chapter3.end, "chapter3.item1.1")
    elif template == "brief":
        found += _collect_ints(doc, CREDIT_RX, 0, min(body_end, _first_page_end(doc, 3)), "summary", first_only=True)
    elif template == "web_page":
        found += _collect_ints(doc, CREDIT_RX, 0, body_end, "web.page", first_only=True)
    return found


# --------------------------------------------------------------------------------------------
# ปีหลักสูตรและประเภท (ใหม่ / ปรับปรุง)
# --------------------------------------------------------------------------------------------

YEAR_RX = rx(
    lit("หลักสูตร"), "(", lit("ปรับปรุง"), "|", lit("ใหม่"), r")(?:พ\.ศ\.?|", lit("พุทธศักราช"), r")(\d{4})",
)
_REVISED = fold("ปรับปรุง")


def extract_year(doc: DocText, template: str, sections: list[Section], body_end: int) -> list[Located]:
    """คืน Located ที่ value_int เป็นปี และ value_text เป็นประเภทหลักสูตร (revised / new)"""
    found: list[Located] = []

    def add(hit, location: str) -> None:
        s, e, m = hit
        found.append(Located("revised" if m.group(1) == _REVISED else "new", int(m.group(2)), s, e, location))

    if template in FULL_TEMPLATES:
        chapter1 = section_named(sections, "chapter.1")
        front_end = chapter1.start if chapter1 else min(body_end, _first_page_end(doc, 6))
        for hit in doc.find_all(YEAR_RX, 0, front_end):
            add(hit, "front")
        if chapter1:
            head = doc.find(rx(r"6\.", lit("สถานภาพของหลักสูตร")), chapter1.start, chapter1.end)
            if head:
                stop = doc.find(rx(r"7\.", lit("ความพร้อม")), head[1], chapter1.end)
                hit = doc.find(YEAR_RX, head[0], stop[0] if stop else min(chapter1.end, head[1] + 400))
                if hit:
                    add(hit, "chapter1.item6")
    elif template in ("brief", "web_page"):
        hit = doc.find(YEAR_RX, 0, min(body_end, _first_page_end(doc, 1)))
        if hit:
            add(hit, "summary")
    return found


# --------------------------------------------------------------------------------------------
# ชื่อหลักสูตรและชื่อปริญญา
# --------------------------------------------------------------------------------------------

_THAI_NAME = rx("(?:", lit("หลักสูตร"), r")?[ก-๙]*?", lit("บัณฑิต"))
_EN_START = re.compile(r"(?:Bachelor|Master|Doctor)of")
_DEGREE_LABELS = (
    ("degree_name_th", "ชื่อเต็ม (ภาษาไทย)"),
    ("degree_abbr_th", "ชื่อย่อ (ภาษาไทย)"),
    ("degree_name_en", "ชื่อเต็ม (ภาษาอังกฤษ)"),
    ("degree_abbr_en", "ชื่อย่อ (ภาษาอังกฤษ)"),
)
NAME_FIELDS = ("program_name_th", "program_name_en")
DEGREE_FIELDS = tuple(key for key, _ in _DEGREE_LABELS)


def _located_text(doc: DocText, start: int, end: int, location: str) -> Located | None:
    a, b = doc.trimmed(start, end)
    if b <= a:
        return None
    return Located(squash(doc.slice(a, b)), None, a, b, location)


def extract_names(doc: DocText, template: str, sections: list[Section], body_end: int) -> dict[str, list[Located]]:
    out: dict[str, list[Located]] = {key: [] for key in NAME_FIELDS}
    if template in FULL_TEMPLATES:
        chapter1 = section_named(sections, "chapter.1")
        if not chapter1:
            return out
        head = doc.find(rx(r"1\.(?:", lit("รหัสและ"), ")?", lit("ชื่อหลักสูตร")), chapter1.start, chapter1.end)
        if not head:
            return out
        stop = doc.find(rx(r"2\.", lit("ชื่อปริญญา")), head[1], chapter1.end)
        end = stop[0] if stop else min(chapter1.end, head[1] + 600)
        thai = doc.find(_THAI_NAME, head[1], end)
        english = doc.find(_EN_START, thai[1] if thai else head[1], end)
        if thai:
            label = doc.find(rx(lit("ภาษาอังกฤษ")), thai[1], end)
            thai_end = min(label[0] if label else end, english[0] if english else end)
            if (found := _located_text(doc, thai[0], thai_end, "chapter1.item1")) is not None:
                out["program_name_th"].append(found)
        if english and (found := _located_text(doc, english[0], end, "chapter1.item1")) is not None:
            out["program_name_en"].append(found)
    elif template in ("brief", "web_page"):
        summary = _summary(doc)
        for key in NAME_FIELDS:
            out[key] = summary[key]
    return out


def extract_degree(doc: DocText, template: str, sections: list[Section], body_end: int) -> dict[str, list[Located]]:
    out: dict[str, list[Located]] = {key: [] for key in DEGREE_FIELDS}
    if template in FULL_TEMPLATES:
        chapter1 = section_named(sections, "chapter.1")
        if not chapter1:
            return out
        head = doc.find(rx(r"2\.", lit("ชื่อปริญญา")), chapter1.start, chapter1.end)
        if not head:
            return out
        stop = doc.find(rx(r"3\.", lit("วิชาเอก")), head[1], chapter1.end) or \
            doc.find(rx(r"4\.", lit("จำนวนหน่วยกิต")), head[1], chapter1.end)
        end = stop[0] if stop else min(chapter1.end, head[1] + 800)
        labels = []
        for key, label in _DEGREE_LABELS:
            hit = doc.find(rx(lit(label)), head[1], end)
            if hit:
                labels.append((hit[0], hit[1], key))
        labels.sort()
        for i, (_, label_end, key) in enumerate(labels):
            value_end = labels[i + 1][0] if i + 1 < len(labels) else end
            if (found := _located_text(doc, label_end, value_end, "chapter1.item2")) is not None:
                out[key].append(found)
    elif template in ("brief", "web_page"):
        summary = _summary(doc)
        for key in DEGREE_FIELDS:
            out[key] = summary[key]
    return out


_BUNTHIT_LINE = rx("(?:", lit("หลักสูตร"), r")?[ก-๙]*?", lit("บัณฑิต"))
_EN_LINE = re.compile(r"(?:Bachelor|Master|Doctor)of")
_TH_ABBR = re.compile(r"[ก-๙]{1,6}\.[ก-๙]{0,3}\.?\(")
_EN_ABBR = re.compile(r"[A-Z][A-Za-z]{0,6}\.[A-Za-z.]*\(")
# ชื่อปริญญาเต็มที่ตามด้วยอักษรย่อในวงเล็บทั้งบรรทัด เช่น "การแพทย์แผนไทยประยุกต์บัณฑิต (พทป.บ.)" (attm65_brief)
_TH_DEGREE_WITH_ABBR = rx(r"([ก-๙]*", lit("บัณฑิต"), r")\(([ก-๙]{1,6}\.[ก-๙.]{0,4})\)")
_EN_DEGREE_WITH_ABBR = re.compile(r"((?:Bachelor|Master|Doctor)of[A-Za-z]+)\(([A-Za-z.]{2,12})\)")
_SUMMARY_STOP = tuple(fold(word) for word in ("ปรัชญา", "วัตถุประสงค์", "วิชาเอก"))


def _degree_with_abbr(doc: DocText, pattern: re.Pattern, start: int, end: int, out: dict, name_key: str, abbr_key: str) -> bool:
    """บรรทัดที่ทั้งบรรทัดเป็นชื่อปริญญาตามด้วยอักษรย่อในวงเล็บ แยกเป็นสองค่าจากตำแหน่งของแต่ละส่วน"""
    folded = fold(doc.slice(start, end))
    if not pattern.fullmatch(folded):
        return False
    hit = doc.find(pattern, start, end, skip_toc=False)
    if not hit:
        return False
    _, _, m = hit
    for group, key in ((1, name_key), (2, abbr_key)):
        s, e = doc.folded.span(m.start(group), m.end(group))
        if not out[key] and (found := _located_text(doc, s, e, "summary")) is not None:
            out[key].append(found)
    return True


def _summary(doc: DocText) -> dict[str, list[Located]]:
    """ชื่อหลักสูตรและชื่อ/อักษรย่อปริญญาจากบรรทัดต้นหน้าแรกของใบสรุปหรือหน้าเว็บ (ก่อนหัวข้อปรัชญา/วัตถุประสงค์)"""
    out: dict[str, list[Located]] = {key: [] for key in (*NAME_FIELDS, *DEGREE_FIELDS)}
    if not doc.pages:
        return out
    base, pos = doc.page_start(0), 0
    for line in doc.pages[0].text.split("\n"):
        start = base + pos
        end = start + len(line)
        pos += len(line) + 1
        folded = fold(line)
        if not folded:
            continue
        if any(re.match(r"^[\d.]*" + re.escape(stop), folded) for stop in _SUMMARY_STOP):
            break
        if out["program_name_th"] and not out["degree_name_th"] and \
                _degree_with_abbr(doc, _TH_DEGREE_WITH_ABBR, start, end, out, "degree_name_th", "degree_abbr_th"):
            continue
        if out["program_name_en"] and not out["degree_name_en"] and \
                _degree_with_abbr(doc, _EN_DEGREE_WITH_ABBR, start, end, out, "degree_name_en", "degree_abbr_en"):
            continue
        if not out["program_name_th"] and _BUNTHIT_LINE.match(folded):
            if (found := _located_text(doc, start, end, "summary")) is not None:
                out["program_name_th"].append(found)
        elif not out["program_name_en"] and _EN_LINE.match(folded):
            if (found := _located_text(doc, start, end, "summary")) is not None:
                out["program_name_en"].append(found)
        elif not out["degree_abbr_th"] and _TH_ABBR.match(folded):
            ascii_at = re.search(r"[A-Za-z]", line)
            thai_end = start + ascii_at.start() if ascii_at else end
            if (found := _located_text(doc, start, thai_end, "summary")) is not None:
                out["degree_abbr_th"].append(found)
            if ascii_at and _EN_ABBR.match(fold(line[ascii_at.start():])):
                if (found := _located_text(doc, start + ascii_at.start(), end, "summary")) is not None:
                    out["degree_abbr_en"].append(found)
        elif not out["degree_abbr_en"] and _EN_ABBR.match(folded):
            if (found := _located_text(doc, start, end, "summary")) is not None:
                out["degree_abbr_en"].append(found)
    return out


# --------------------------------------------------------------------------------------------
# รายการ: วัตถุประสงค์ อาชีพ คุณสมบัติผู้เข้าศึกษา
# --------------------------------------------------------------------------------------------

def _at_line_start(doc: DocText, start: int, pos: int) -> bool:
    return pos == start or not doc.text[doc.text.rfind("\n", 0, pos) + 1:pos].strip()


def _boundary_ok(doc: DocText, pos: int) -> bool:
    """
    เลขหัวข้อที่ตำแหน่งนี้เป็นหัวข้อจริง: ขึ้นต้นบรรทัด หรืออักขระก่อนหน้า (ข้ามช่องว่าง) ไม่ใช่ตัวเลขหรือจุด

    ตัดสินจากข้อความต้นฉบับ ไม่ใช้ lookbehind บนรูปที่ใช้ค้น เพราะรูปที่ใช้ค้นตัดขึ้นบรรทัดใหม่ทิ้ง เลขหน้าของหน้าถัดไป
    จึงต่อกับเลขหัวข้อ เจอในคลังจริง 6 เล่ม เช่น agri68_master หน้า 20 ขึ้นต้นด้วย "15" แล้วตามด้วย
    "2. ผลลัพธ์การเรียนรู้" กลายเป็น "152.ผลลัพธ์" หัวข้อถัดไปจึงไม่ถูกนับเป็นจุดจบ วัตถุประสงค์ข้อสุดท้ายยาวไปถึง PLO
    """
    i = pos - 1
    while i >= 0 and doc.text[i] in " \t":
        i -= 1
    return i < 0 or doc.text[i] == "\n" or not (doc.text[i].isdigit() or doc.text[i] == ".")


def _find_stop(doc: DocText, pattern: re.Pattern, start: int, end: int):
    """หัวข้อถัดไปที่เป็นจุดจบของรายการ (ตัวแรกที่ผ่าน _boundary_ok)"""
    for hit in doc.find_all(pattern, start, end):
        if _boundary_ok(doc, hit[0]):
            return hit
    return None


def _numbered_markers(doc: DocText, start: int, end: int, prefix: str,
                      suffix: str = r"(?!\d)") -> list[tuple[int, int, int]]:
    """
    ตำแหน่งเลขข้อ (เริ่ม, จบ, เลข) เช่น prefix "8\\." ได้ 8.1, 8.2, ...

    เลขข้อต้องมีช่องว่างหรือขึ้นบรรทัดใหม่นำหน้าในข้อความต้นฉบับ และต้องเป็นข้อถัดไปพอดี ตัวเลขที่อยู่กลางข้อความ
    เช่น "พ.ศ. 2558.1" หรือเลขข้ออ้างอิงจึงไม่ถูกนับเป็นข้อใหม่

    ยกเว้นเลขข้อที่ขึ้นต้นบรรทัดแต่ข้ามหรือซ้ำเลข (ไม่ถอยหลัง) ให้นับเป็นข้อใหม่ เพราะเอกสารจริงพิมพ์เลขผิดได้:
    it66 เรียง 8.7, 8.9, 8.9 ถ้าบังคับให้เรียงพอดี สองข้อสุดท้ายจะถูกรวมเข้าไปในข้อ 8.7 ผู้เรียกตรวจเลขที่ได้
    แล้วส่งให้คนตรวจการแบ่งรายการ (ดู _list)
    """
    markers: list[tuple[int, int, int]] = []
    last = 0
    for s, e, m in doc.find_all(rx(prefix, r"(\d{1,2})", suffix), start, end, skip_toc=False):
        number = int(m.group(1))
        if s > start and not doc.text[s - 1].isspace():
            continue
        if number == last + 1 or (markers and number >= last and _at_line_start(doc, start, s)):
            markers.append((s, e, number))
            last = number
    return markers


def _line_numbered_markers(doc: DocText, start: int, end: int) -> list[tuple[int, int, int]]:
    """เลขข้อแบบ "1." หรือ "1 " ที่ต้นบรรทัด เรียงต่อกัน (ใช้กับใบสรุปหลักสูตร)"""
    markers: list[tuple[int, int, int]] = []
    expected = 1
    block = doc.text[start:end]
    for m in re.finditer(r"(?m)^[ \t]*(\d{1,2})(?:\.(?!\d))?[ \t]+", block):
        if int(m.group(1)) != expected:
            continue
        markers.append((start + m.start(1), start + m.end(), expected))
        expected += 1
    return markers


def _bullet_items(doc: DocText, start: int, end: int) -> list[tuple[int, int]]:
    block = doc.text[start:end]
    items = []
    for m in re.finditer(r"(?m)^[ \t]*[-•][ \t]+(\S.*?)[ \t]*$", block):
        items.append((start + m.start(1), start + m.end(1)))
    return items


def _trim_page_furniture(doc: DocText, start: int, end: int) -> tuple[int, int]:
    """
    ถ้าช่วงข้ามไปหน้าถัดไปแต่ส่วนที่อยู่ในหน้าถัดไปมีแค่หัวกระดาษหรือเลขหน้า ให้จบที่หน้าเดิม
    และตัดท้ายกระดาษ/เลขหน้าที่อยู่ท้ายช่วงออก — ช่วงที่มีเนื้อหาต่อจริงข้ามหน้าไม่ถูกตัด
    """
    first = doc.page_index(start)
    last = doc.page_index(max(start, end - 1))
    while last > first and doc.content_start(last) >= end:
        end = doc.page_end(last - 1)
        last -= 1
    content_end = doc.content_end(last)
    if start < content_end < end:
        end = content_end
    return doc.trimmed(start, end)


def _items_between(doc: DocText, markers: list[tuple[int, int, int]], end: int) -> list[tuple[int, int]]:
    items = []
    for i, (_, marker_end, _) in enumerate(markers):
        stop = markers[i + 1][0] if i + 1 < len(markers) else end
        a, b = _trim_page_furniture(doc, marker_end, stop)
        if b > a:
            items.append((a, b))
    return items


def _list(doc: DocText, location: str, head: tuple, end: int, markers: list[tuple[int, int, int]],
          allow_paragraph: bool = True, keep_intro: bool = False) -> ListLocated:
    heading_end = head[1]
    # จบก้อนหลักฐานก่อนหัวกระดาษ/เลขหน้าของหน้าถัดไป ไม่งั้นเลขหน้าที่อ้างอิงจะรวมหน้าที่ไม่มีเนื้อหาของหัวข้อนี้
    end = _trim_page_furniture(doc, head[0], end)[1]
    if markers:
        items = _items_between(doc, markers, end)
        if keep_intro:
            a, b = _trim_page_furniture(doc, heading_end, markers[0][0])
            if b - a >= 15:
                items.insert(0, (a, b))
        numbers = [number for _, _, number in markers]
        irregular = numbers != list(range(1, len(numbers) + 1))
        return ListLocated(location, head[0], end, tuple(items), "numbered", irregular)
    bullets = _bullet_items(doc, heading_end, end)
    if bullets:
        return ListLocated(location, head[0], end, tuple(bullets), "bullet")
    a, b = _trim_page_furniture(doc, heading_end, end)
    items = ((a, b),) if allow_paragraph and b > a else ()
    return ListLocated(location, head[0], end, items, "paragraph")


def _earliest(hits) -> int | None:
    positions = [hit[0] for hit in hits if hit]
    return min(positions) if positions else None


def extract_careers(doc: DocText, template: str, sections: list[Section], body_end: int) -> ListLocated | None:
    if template in FULL_TEMPLATES:
        chapter1 = section_named(sections, "chapter.1")
        area = (chapter1.start, chapter1.end) if chapter1 else (0, body_end)
        head = doc.find(rx(r"8\.", lit("อาชีพที่"), r".{0,25}?", lit("สำเร็จการศึกษา")), *area)
        if not head:
            return None
        stop = _find_stop(doc, rx(r"9\.[ก-๙]"), head[1], area[1])
        end = stop[0] if stop else area[1]
        return _list(doc, "chapter1.item8", head, end, _numbered_markers(doc, head[1], end, r"8\."))
    if template in ("brief", "web_page"):
        limit = body_end if template == "web_page" else min(body_end, _first_page_end(doc, 3))
        head = doc.find(rx(lit("อาชีพที่"), r".{0,25}?", lit("สำเร็จการศึกษา")), 0, limit)
        if not head:
            return None
        end = doc.page_end(doc.page_index(head[0]))
        markers = _line_numbered_markers(doc, head[1], end)
        return _list(doc, "summary", head, end, markers, allow_paragraph=False)
    return None


_OBJECTIVE_STOP = re.compile(r"(?:1\.4|2\.)(?=[ก-๙A-Za-z(])")


def extract_objectives(doc: DocText, template: str, sections: list[Section], body_end: int) -> ListLocated | None:
    if template in FULL_TEMPLATES:
        chapter2 = section_named(sections, "chapter.2")
        area = (chapter2.start, chapter2.end) if chapter2 else (0, body_end)
        head = doc.find(rx(r"1\.3", lit("วัตถุประสงค์")), *area)
        if not head:
            return None
        stop = _find_stop(doc, _OBJECTIVE_STOP, head[1], area[1])
        end = stop[0] if stop else area[1]
        return _list(doc, "chapter2.item1.3", head, end, _numbered_markers(doc, head[1], end, r"1\.3\."))
    if template == "brief":
        limit = min(body_end, _first_page_end(doc, 3))
        head = doc.find(rx(lit("วัตถุประสงค์ของหลักสูตร")), 0, limit)
        if not head:
            return None
        stops = (
            doc.find(rx(lit("จำนวนหน่วยกิต")), head[1], body_end),
            doc.find(rx(lit("โครงสร้างหลักสูตร")), head[1], body_end),
            _find_stop(doc, re.compile(r"(?:1\.4|3\.1)(?!\d)"), head[1], body_end),
            doc.find(rx(lit("ผลลัพธ์การเรียนรู้")), head[1], body_end),
        )
        end = _earliest(stops) or doc.page_end(doc.page_index(head[0]))
        markers = _numbered_markers(doc, head[1], end, r"1\.3\.") or _line_numbered_markers(doc, head[1], end)
        return _list(doc, "summary", head, end, markers)
    return None


def extract_admission(doc: DocText, template: str, sections: list[Section], body_end: int) -> ListLocated | None:
    if template == "tqf2":
        chapter3 = section_named(sections, "chapter.3")
        chapter2 = section_named(sections, "chapter.2")
        area = (chapter3.start, chapter3.end) if chapter3 else ((chapter2.end if chapter2 else 0), body_end)
        head = doc.find(rx(r"2\.2", lit("คุณสมบัติของผู้เข้าศึกษา")), *area)
        if not head:
            return None
        end = _earliest((
            _find_stop(doc, re.compile(r"2\.3(?!\d)"), head[1], area[1]),
            _find_stop(doc, rx(r"3\.", lit("หลักสูตรและอาจารย์")), head[1], area[1]),
        )) or area[1]
        markers = _numbered_markers(doc, head[1], end, r"2\.2\.")
        return _list(doc, "chapter3.item2.2", head, end, markers, keep_intro=True)
    if template == "std2565":
        chapter6 = section_named(sections, "chapter.6")
        if not chapter6:
            return None
        head = doc.find(rx(r"1\.", lit("คุณสมบัติของผู้เข้าศึกษา")), chapter6.start, chapter6.end)
        if not head:
            return None
        stop = _find_stop(doc, re.compile(r"2\.(?=[ก-๙])"), head[1], chapter6.end)
        end = stop[0] if stop else chapter6.end
        markers = _numbered_markers(doc, head[1], end, r"1\.", suffix=r"(?!\d|\.\d)")
        return _list(doc, "chapter6.item1", head, end, markers, keep_intro=True)
    return None
