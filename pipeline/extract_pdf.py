"""
Step 1: ดึงข้อความดิบ + metadata จาก PDF หลักสูตร

ใช้ PyMuPDF (fitz) เพราะเร็วและดึง layout/page number ได้แม่นกว่า PyPDF2 ทั่วไป
สำหรับ PDF ที่เป็นภาพสแกน (ไม่มี text layer) ฟังก์ชันนี้จะได้ข้อความว่าง —
ถ้าต้องรองรับสแกน ต้องต่อ OCR (เช่น pytesseract) เพิ่มเป็นอีกขั้นก่อน extract_pdf

SECURITY:
  - ตรวจ MIME/magic bytes จริงของไฟล์ ไม่เชื่อแค่นามสกุล .pdf (กัน path/content
    spoofing ที่ผู้ใช้อัปโหลดไฟล์ประเภทอื่นแล้วเปลี่ยนนามสกุล)
  - จำกัดขนาดไฟล์ก่อนเปิดอ่าน (กัน decompression-bomb / resource exhaustion)
  - เปิดไฟล์แบบ read-only เท่านั้น
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF

MAX_PDF_BYTES = 50 * 1024 * 1024  # 50MB, ต้องตรงกับ settings.max_pdf_size_mb ฝั่ง backend
PDF_MAGIC = b"%PDF-"


class InvalidPdfError(ValueError):
    pass


@dataclass
class ExtractedPage:
    page_number: int  # เริ่มที่ 1
    text: str


@dataclass
class ExtractedDocument:
    file_sha256: str
    page_count: int
    pages: list[ExtractedPage]


def _validate_file(path: Path) -> bytes:
    if not path.is_file():
        raise InvalidPdfError(f"file not found: {path}")

    size = path.stat().st_size
    if size == 0 or size > MAX_PDF_BYTES:
        raise InvalidPdfError(f"file size {size} bytes out of allowed range (0, {MAX_PDF_BYTES}]")

    with path.open("rb") as f:
        header = f.read(len(PDF_MAGIC))
    if header != PDF_MAGIC:
        # เช็ค magic bytes จริง ไม่ใช่แค่ .pdf extension
        raise InvalidPdfError("file does not have a valid PDF header (magic bytes mismatch)")

    return path.read_bytes()


def extract_pdf(path: str | Path) -> ExtractedDocument:
    path = Path(path)
    raw_bytes = _validate_file(path)
    file_hash = hashlib.sha256(raw_bytes).hexdigest()

    pages: list[ExtractedPage] = []
    with fitz.open(stream=raw_bytes, filetype="pdf") as doc:
        if doc.is_encrypted:
            raise InvalidPdfError("encrypted PDFs are not supported by this pipeline")
        for i, page in enumerate(doc, start=1):
            text = page.get_text("text")
            pages.append(ExtractedPage(page_number=i, text=text))

    return ExtractedDocument(file_sha256=file_hash, page_count=len(pages), pages=pages)


if __name__ == "__main__":
    import sys

    result = extract_pdf(sys.argv[1])
    print(f"pages={result.page_count} sha256={result.file_sha256}")
    print(result.pages[0].text[:500] if result.pages else "(empty)")
