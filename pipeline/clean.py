"""
Step 2: Data Cleaning ก่อนนำเข้าสู่ Database

งานหลัก:
  - ลบ header/footer ที่ซ้ำทุกหน้า (เช่น "Confidential - Company X - Page N")
  - normalize whitespace/line-break, ลบ hyphenation ที่ตัดคำข้ามบรรทัด
  - ลบอักขระควบคุม/null byte ที่อาจติดมาจาก PDF ที่สร้างไม่สมบูรณ์
  - ลบ header/footer ซ้ำเป็น heuristic ที่ดีพอสำหรับ PDF หลักสูตรทั่วไป
    (บรรทัดที่ปรากฏซ้ำใน >60% ของหน้าทั้งหมด มักเป็น header/footer ไม่ใช่เนื้อหา)

SECURITY:
  - เนื้อหาที่ clean แล้วยังคง "ข้อมูลที่ไม่น่าเชื่อถือ" อยู่ (มาจากไฟล์ user
    อัปโหลด) — ห้าม eval/exec เนื้อหานี้ และตอน insert DB ต้องผ่าน parameterized
    query เท่านั้น (ดู ingest.py)
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter

from pipeline.extract_pdf import ExtractedDocument, ExtractedPage

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_MULTI_SPACE_RE = re.compile(r"[ \t]+")
_MULTI_BLANK_LINE_RE = re.compile(r"\n{3,}")
_HYPHEN_LINEBREAK_RE = re.compile(r"(\w)-\n(\w)")  # "informa-\ntion" -> "information"


def _strip_control_chars(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    return _CONTROL_CHARS_RE.sub("", text)


def _normalize_whitespace(text: str) -> str:
    text = _HYPHEN_LINEBREAK_RE.sub(r"\1\2", text)
    text = _MULTI_SPACE_RE.sub(" ", text)
    text = _MULTI_BLANK_LINE_RE.sub("\n\n", text)
    return text.strip()


def _detect_repeated_lines(pages: list[ExtractedPage], min_ratio: float = 0.6) -> set[str]:
    """หาบรรทัดที่ซ้ำในหลายหน้า (มักคือ header/footer) เพื่อตัดทิ้ง"""
    if len(pages) < 3:
        return set()  # เอกสารสั้นเกินไปจะ false-positive ง่าย ข้ามการตัด header/footer
    line_counts: Counter[str] = Counter()
    for page in pages:
        lines = {line.strip() for line in page.text.splitlines() if line.strip()}
        line_counts.update(lines)
    threshold = max(2, int(len(pages) * min_ratio))
    return {line for line, count in line_counts.items() if count >= threshold and len(line) < 120}


def clean_document(doc: ExtractedDocument) -> ExtractedDocument:
    repeated = _detect_repeated_lines(doc.pages)

    cleaned_pages: list[ExtractedPage] = []
    for page in doc.pages:
        text = _strip_control_chars(page.text)
        if repeated:
            lines = [ln for ln in text.splitlines() if ln.strip() not in repeated]
            text = "\n".join(lines)
        text = _normalize_whitespace(text)
        cleaned_pages.append(ExtractedPage(page_number=page.page_number, text=text))

    return ExtractedDocument(file_sha256=doc.file_sha256, page_count=doc.page_count, pages=cleaned_pages)
