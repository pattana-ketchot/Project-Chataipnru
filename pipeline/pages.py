"""
ข้อความรายหน้าของเอกสารหลักสูตร — input ของการสกัดข้อมูลเชิงโครงสร้าง (docs/MKO_STRUCTURED_DATA_DESIGN.md)

ใช้ขั้นตอนเดียวกับตอนนำเข้าเอกสารเพื่อทำ chunk ทุกขั้น (extract_document → apply_ocr → clean_document)
ข้อความที่ตัวสกัดข้อมูลอ่านจึงเป็นชุดเดียวกับที่ระบบค้นด้วย RAG และเลขหน้าที่อ้างอิงตรงกับเลขหน้าของ chunk

เก็บทั้งข้อความก่อนและหลังทำความสะอาด เพราะขั้นทำความสะอาดตัดบรรทัดที่ซ้ำหลายหน้าทิ้ง ซึ่งอาจเป็นหัวตาราง
ที่ตัวสกัดรายวิชาต้องใช้ในภายหลัง

text_source บอกว่าข้อความของหน้านั้นมาจากไหน หน้าที่มีข้อความจาก OCR ทุกหน้าถือว่าต้องให้คนตรวจ เพราะ OCR
ที่อ่านผิดคือข้อมูลผิดที่ดูน่าเชื่อถือ (ดูเหตุผลใน pipeline/ocr.py)
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pipeline.clean import clean_document
from pipeline.extract_pdf import extract_document
from pipeline.ingest import apply_ocr
from pipeline.ocr import UNREADABLE


@dataclass(frozen=True)
class PageRecord:
    page_number: int
    text_raw: str  # หลังเติม OCR ก่อนทำความสะอาด
    text_clean: str
    text_source: str  # text_layer | ocr | text_layer+ocr | plain_text


@dataclass(frozen=True)
class DocumentPages:
    filename: str
    file_sha256: str
    page_count: int
    pages: list[PageRecord]


def _ocr_table(ocr_path: str | Path | None) -> dict[str, str]:
    if not ocr_path:
        return {}
    return json.loads(Path(ocr_path).read_text(encoding="utf-8"))


def build_pages(path: str | Path, ocr_path: str | Path | None = None) -> DocumentPages:
    """อ่านเอกสารหนึ่งไฟล์เป็นข้อความรายหน้า ด้วยขั้นตอนเดียวกับ pipeline.ingest"""
    path = Path(path)
    raw = extract_document(path)
    with_ocr = apply_ocr(raw, path.name, str(ocr_path) if ocr_path else None)
    cleaned = clean_document(with_ocr)
    table = _ocr_table(ocr_path)

    records: list[PageRecord] = []
    for before, merged, final in zip(raw.pages, with_ocr.pages, cleaned.pages):
        if path.suffix.lower() == ".txt":
            source = "plain_text"
        else:
            ocr_text = table.get(f"{path.name}#{before.page_number}", "").strip()
            # เงื่อนไขเดียวกับ apply_ocr: หน้าที่ OCR อ่านไม่ออกไม่ได้ถูกเติมข้อความ
            used_ocr = bool(ocr_text) and UNREADABLE not in ocr_text
            if not used_ocr:
                source = "text_layer"
            else:
                source = "text_layer+ocr" if before.text.strip() else "ocr"
        records.append(PageRecord(before.page_number, merged.text, final.text, source))

    return DocumentPages(path.name, raw.file_sha256, raw.page_count, records)
