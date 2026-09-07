"""
CLI orchestrator: PDF -> extract -> clean -> chunk -> embed -> insert DB

รัน:
    python -m pipeline.ingest --pdf samples/course101.pdf --title "AI Fundamentals" --course-code CS101

SECURITY:
  - เชื่อมต่อ DB ด้วย role `advisor_ingest` (สิทธิ์จำกัดเฉพาะ courses/
    course_documents/course_chunks — ดู db/schema.sql ท้ายไฟล์) ไม่ใช่ superuser
  - ทุกคำสั่ง SQL เป็น parameterized query ผ่าน psycopg (ไม่ string-format ค่า
    ที่มาจากเนื้อหา PDF เข้า SQL โดยตรง)
  - ทำงานแบบ transaction เดียวต่อเอกสาร: ถ้า insert chunk ล้มเหลวกลางทาง
    จะ rollback ทั้งหมด ไม่ทิ้งข้อมูลครึ่งๆ กลางๆ ไว้ใน DB
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import uuid
from pathlib import Path

# monorepo bootstrap: ให้ import `llm.*` และ `pipeline.*` ทำงานได้ไม่ว่าจะรันจากที่ไหน
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import psycopg  # noqa: E402
from dotenv import load_dotenv  # noqa: E402
from pgvector.psycopg import register_vector  # noqa: E402

from llm.connector import OllamaConnector  # noqa: E402
from pipeline.chunker import chunk_document  # noqa: E402
from pipeline.clean import clean_document  # noqa: E402
from pipeline.embed import embed_chunks  # noqa: E402
from pipeline.extract_pdf import ExtractedDocument, ExtractedPage, extract_document  # noqa: E402
from pipeline.ocr import UNREADABLE  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("pipeline.ingest")

# อ่าน .env ที่ root ของ repo (override=False -> env var จริงที่ตั้งไว้แล้วชนะเสมอ
# เพื่อให้ override ตอนรันใน CI/container ได้)
load_dotenv(_REPO_ROOT / ".env", override=False)


def apply_ocr(doc: ExtractedDocument, filename: str, ocr_path: str | None) -> ExtractedDocument:
    """
    เติมข้อความจาก OCR ลงหน้าที่เป็นภาพสแกน

    รับผลที่ pipeline/ocr.py ถอดไว้ล่วงหน้าเป็นไฟล์ JSON แทนการเรียก OCR ตอนนำเข้า
    ด้วยเหตุผลสองข้อ: การนำเข้าใหม่แต่ละรอบจะได้ไม่ต้องจ่ายค่า OCR ซ้ำ และผลของ OCR
    ตรวจด้วยตาได้ก่อนว่าจะให้เข้าคลังหรือไม่ ซึ่งจำเป็นเพราะ OCR ผิดคือข้อมูลผิด
    ที่ระบบจะเอาไปตอบอย่างมั่นใจ

    ต่อท้ายข้อความเดิมของหน้านั้น ไม่ทับ เพราะหน้าสแกนมักมีหัวกระดาษกับเลขหน้าเป็น
    ข้อความจริงอยู่แล้ว ซึ่งเป็นตัวบอกว่าเนื้อหาอยู่หน้าไหนของเล่ม
    """
    if not ocr_path:
        return doc
    table = json.loads(Path(ocr_path).read_text(encoding="utf-8"))

    pages, filled = [], 0
    for page in doc.pages:
        extra = table.get(f"{filename}#{page.page_number}", "").strip()
        # หน้าที่ OCR อ่านไม่ออกให้ปล่อยว่างไว้ตามเดิม ดีกว่าใส่ข้อความที่ไม่มีความหมาย
        if extra and UNREADABLE not in extra:
            pages.append(ExtractedPage(page.page_number, f"{page.text}\n{extra}"))
            filled += 1
        else:
            pages.append(page)

    if filled:
        logger.info("เติมข้อความจาก OCR ลง %d หน้า", filled)
    return ExtractedDocument(file_sha256=doc.file_sha256, page_count=doc.page_count, pages=pages)


def already_ingested(database_url: str, sha256: str) -> bool:
    """
    เคยนำเข้าไฟล์นี้ไปแล้วหรือยัง — ถามก่อนเริ่มทำ embedding

    เดิมโค้ดเช็คซ้ำหลังทำ embedding เสร็จ เพราะ ON CONFLICT อยู่ตอน insert อยู่แล้ว
    ผลคือการนำเข้าซ้ำทั้งโฟลเดอร์ต้องเสีย embedding ใหม่ทุก chunk ก่อนจะรู้ว่าไม่ต้องใช้
    วัดจริงตอนเพิ่มไฟล์เดียวเข้าคลัง 19 เล่ม: ต้องคำนวณ 7,301 chunk ทิ้งบนเครื่องที่
    ไม่มีการ์ดจอ ราวสองชั่วโมง เพื่อจะเก็บของจริงแค่ 140 chunk

    เช็คด้วย sha256 ของไฟล์เหมือนกับที่ ON CONFLICT ใช้ ผลจึงตรงกันเสมอ และยังเก็บ
    ON CONFLICT ไว้เป็นด่านสุดท้ายกันสองงานที่รันพร้อมกันเขียนซ้ำ

    นับเฉพาะที่ทำเสร็จแล้ว (status = done) การนำเข้าที่ค้างหรือพังกลางทางจะเหลือ
    แถวที่ยังไม่มี chunk อยู่ ถ้านับว่า "เคยนำเข้าแล้ว" ด้วย เอกสารเล่มนั้นจะถูกข้าม
    ตลอดไปและหายไปจากคลังเงียบๆ โดยไม่มีอะไรฟ้อง
    """
    with psycopg.connect(database_url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM course_documents WHERE file_sha256 = %s AND extraction_status = 'done'",
            (sha256,),
        )
        return cur.fetchone() is not None


def get_or_create_course(conn: psycopg.Connection, course_code: str | None, title: str, provider: str | None) -> uuid.UUID:
    with conn.cursor() as cur:
        if course_code:
            cur.execute("SELECT id FROM courses WHERE code = %s", (course_code,))
            row = cur.fetchone()
            if row:
                return row[0]
        cur.execute(
            "INSERT INTO courses (code, title, provider) VALUES (%s, %s, %s) RETURNING id",
            (course_code, title, provider),
        )
        return cur.fetchone()[0]


def insert_document(conn: psycopg.Connection, course_id: uuid.UUID, filename: str, sha256: str, storage_path: str, page_count: int) -> uuid.UUID | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO course_documents
                (course_id, original_filename, file_sha256, storage_path, page_count, extraction_status)
            VALUES (%s, %s, %s, %s, %s, 'processing')
            ON CONFLICT (course_id, file_sha256) DO UPDATE
                SET extraction_status = 'processing',
                    extraction_error = NULL,
                    page_count = EXCLUDED.page_count
                WHERE course_documents.extraction_status <> 'done'
            RETURNING id
            """,
            (course_id, filename, sha256, storage_path, page_count),
        )
        row = cur.fetchone()
        # None = มีแถวนี้อยู่แล้วและทำเสร็จไปแล้ว จึงไม่ต้องทำซ้ำ
        #
        # ถ้าแถวเดิมยังไม่ done (ค้างหรือพังกลางทาง) จะยึดแถวนั้นมาทำต่อแทนการข้าม
        # เดิมใช้ DO NOTHING ซึ่งทำให้เอกสารที่นำเข้าไม่สำเร็จติดค้างถาวร — รันใหม่
        # กี่ครั้งก็ถูกมองว่าซ้ำ ต้องเข้าไปลบแถวใน DB เองถึงจะแก้ได้
        return row[0] if row else None


def mark_document_status(conn: psycopg.Connection, document_id: uuid.UUID, status: str, error: str | None = None) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE course_documents SET extraction_status = %s, extraction_error = %s WHERE id = %s",
            (status, error, document_id),
        )


def insert_chunks(conn: psycopg.Connection, course_id: uuid.UUID, document_id: uuid.UUID, chunks, embeddings) -> None:
    rows = [
        (course_id, document_id, c.chunk_index, c.page_number, c.content, c.token_count, emb)
        for c, emb in zip(chunks, embeddings)
    ]
    with conn.cursor() as cur:
        # ล้างของเดิมก่อน เผื่อเป็นการทำซ้ำเอกสารที่นำเข้าค้างไว้ ไม่งั้นจะชน
        # unique (document_id, chunk_index) หรือได้เนื้อหาซ้ำสองชุดในคลัง
        cur.execute("DELETE FROM course_chunks WHERE document_id = %s", (document_id,))
        cur.executemany(
            """
            INSERT INTO course_chunks
                (course_id, document_id, chunk_index, page_number, content, token_count, embedding)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            rows,
        )


def run(pdf_path: str, title: str, course_code: str | None, provider: str | None) -> None:
    # ใช้ advisor_ingest role, แยกจาก backend (ดู .env.example)
    database_url = os.environ.get("INGEST_DATABASE_URL")
    if not database_url:
        raise SystemExit(
            "ไม่พบ INGEST_DATABASE_URL — ตั้งค่าใน .env ที่ root ของ repo หรือ export เป็น env var\n"
            "ตัวอย่าง: postgresql://advisor_ingest:<password>@localhost:5432/course_advisor"
        )
    ollama_base_url = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    embed_model = os.environ.get("EMBED_MODEL", "nomic-embed-text")

    logger.info("extracting %s", pdf_path)
    raw_doc = extract_document(pdf_path)

    # ถามก่อนว่าเคยนำเข้าไฟล์นี้แล้วหรือยัง การ extract ใช้เวลาไม่กี่วินาที
    # แต่การ embed ใช้เป็นชั่วโมงบนเครื่องที่ไม่มีการ์ดจอ
    if already_ingested(database_url, raw_doc.file_sha256):
        logger.info("document already ingested (sha256 match) — skipping before embedding")
        return

    raw_doc = apply_ocr(raw_doc, Path(pdf_path).name, os.environ.get("OCR_TEXT_JSON"))
    cleaned_doc = clean_document(raw_doc)
    chunks = chunk_document(cleaned_doc)
    logger.info("produced %d chunks from %d pages", len(chunks), cleaned_doc.page_count)

    connector = OllamaConnector(base_url=ollama_base_url, embed_model=embed_model)
    embeddings = embed_chunks(connector, chunks)

    with psycopg.connect(database_url) as conn:
        register_vector(conn)

        # Transaction A: จอง course + document row (status=processing) แยกจาก
        # การ insert chunk เพื่อให้ dedupe (ON CONFLICT ... sha256) เห็นผลทันที
        # และเพื่อให้ transaction B ด้านล่าง fail ได้โดยไม่ลบ record นี้ทิ้งไปด้วย
        with conn.transaction():
            course_id = get_or_create_course(conn, course_code, title, provider)
            document_id = insert_document(
                conn, course_id, Path(pdf_path).name, cleaned_doc.file_sha256, str(pdf_path), cleaned_doc.page_count
            )
        if document_id is None:
            logger.info("document already ingested (sha256 match) — skipping")
            return

        # Transaction B: insert chunks ทั้งหมด + mark done แบบ atomic
        try:
            with conn.transaction():
                insert_chunks(conn, course_id, document_id, chunks, embeddings)
                mark_document_status(conn, document_id, "done")
        except Exception as e:
            # Transaction C (แยกออกมา เพราะ transaction B ข้างบน rollback ไปแล้ว):
            # บันทึกสถานะ failed ไว้เพื่อ debug/retry ทีหลัง
            with conn.transaction():
                mark_document_status(conn, document_id, "failed", str(e)[:500])
            raise

    logger.info("ingest complete: course_id=%s document_id=%s chunks=%d", course_id, document_id, len(chunks))


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest a course PDF into the vector DB")
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--course-code")
    parser.add_argument("--provider")
    args = parser.parse_args()
    run(args.pdf, args.title, args.course_code, args.provider)


if __name__ == "__main__":
    main()
