"""สร้าง PDF ทดสอบสำหรับ E2E ที่แยกอิสระ

ข้อกำหนดของไฟล์นี้
------------------
* ต้องอ่านออกตั้งแต่บรรทัดแรกว่าเป็นข้อมูลทดสอบ
* ห้ามมีชื่อหลักสูตรจริง ชื่อบุคคลจริง หรือรหัสวิชาจริงของ PNRU
* ห้ามจัดรูปแบบให้เหมือนเอกสาร มคอ.2 ของจริง (ไม่มีตราคณะ ไม่มีเลขที่เอกสารจริง)
* ต้องมี marker ที่ไม่ซ้ำกับสิ่งใดในคลังจริง ไว้ใช้ยืนยันผลการค้นด้วย vector
* ต้องยาวพอให้ chunker ตัดได้อย่างน้อยหนึ่งช่วง

sha256 ของไฟล์คำนวณจากไฟล์จริงทุกครั้ง ไม่ hard-code
(PyMuPDF ใส่ creationDate/modDate ลง metadata ทำให้ไบต์ต่างกันทุกครั้งที่สร้าง)
"""
from __future__ import annotations

import hashlib
import os
import sys

import fitz  # PyMuPDF — มีอยู่แล้วในอิมเมจ ingest worker

MARKER = "E2E-MARKER-TEST101-PIPELINE-VERIFICATION"
PDF_NAME = "TEST_CS_CURRICULUM_E2E.pdf"

HEADER = [
    "TEST DATA",
    "NOT A REAL PNRU CURRICULUM",
    "FOR ISOLATED E2E TEST ONLY",
    "",
    "Course:       TEST101",
    "Title:        E2E Pipeline Testing",
    "Credits:      3",
    "",
    "Marker:       " + MARKER,
    "",
]

BODY = [
    "Description",
    "This document exists only to verify the automated PDF ingestion pipeline.",
    "It is not a curriculum document and must never be published to any real",
    "knowledge base. Every value on this page is fabricated for testing.",
    "",
    "Scope of this test document",
    "The ingestion pipeline reads this file, extracts its text, splits the text",
    "into chunks, sends each chunk to the bge-m3 embedding model, and stores the",
    "resulting 1024-dimensional vectors in PostgreSQL with the pgvector extension.",
    "This paragraph exists so that the chunker has enough text to produce at least",
    "one chunk, and so that a vector search for the marker string above can be",
    "matched back to this document with confidence.",
    "",
    "Course TEST101 - E2E Pipeline Testing",
    "Credits: 3. Prerequisite: none. This course code is fictitious and is used",
    "only to exercise the approval path, which requires an existing course row in",
    "the test database. No real programme of study is described here.",
    "",
    "Expected verification points",
    "1. The crawler discovers this file and records status downloaded.",
    "2. The reviewer can open this file through the staged PDF endpoint.",
    "3. Approving it creates exactly one active decision row.",
    "4. The worker claims the job, publishes the file, and ingests it.",
    "5. Chunks are written with embeddings of exactly 1024 dimensions.",
    "6. A vector search for the marker returns a chunk from this document.",
    "7. Running the worker again creates no duplicate document or chunks.",
    "",
    "End of test document. " + MARKER,
]


def build(out_path: str) -> tuple[str, int]:
    doc = fitz.open()
    page = doc.new_page()
    y = 60.0
    for line in HEADER:
        page.insert_text((60, y), line, fontname="helv", fontsize=12)
        y += 18
    for line in BODY:
        if y > 760:
            page = doc.new_page()
            y = 60.0
        page.insert_text((60, y), line, fontname="helv", fontsize=10)
        y += 14

    doc.set_metadata({
        "title": "E2E Pipeline Testing (TEST DATA)",
        "author": "isolated e2e harness",
        "subject": "TEST DATA - NOT A REAL PNRU CURRICULUM",
        "keywords": MARKER,
    })
    doc.save(out_path)
    doc.close()

    with open(out_path, "rb") as fh:
        data = fh.read()
    return hashlib.sha256(data).hexdigest(), len(data)


def main() -> int:
    site_dir = os.environ.get("E2E_SITE_DIR", "/srv/site")
    os.makedirs(site_dir, exist_ok=True)
    out = os.path.join(site_dir, PDF_NAME)
    sha, size = build(out)
    print(f"สร้าง {out}")
    print(f"  ขนาด   {size} ไบต์")
    print(f"  sha256 {sha}")
    print(f"  marker {MARKER}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
