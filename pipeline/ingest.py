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
from pgvector.psycopg import register_vector  # noqa: E402

from llm.connector import OllamaConnector  # noqa: E402
from pipeline.chunker import chunk_document  # noqa: E402
from pipeline.clean import clean_document  # noqa: E402
from pipeline.embed import embed_chunks  # noqa: E402
from pipeline.extract_pdf import extract_pdf  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("pipeline.ingest")


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
            ON CONFLICT (course_id, file_sha256) DO NOTHING
            RETURNING id
            """,
            (course_id, filename, sha256, storage_path, page_count),
        )
        row = cur.fetchone()
        return row[0] if row else None  # None = ไฟล์นี้เคย ingest แล้ว (dedupe ด้วย sha256)


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
        cur.executemany(
            """
            INSERT INTO course_chunks
                (course_id, document_id, chunk_index, page_number, content, token_count, embedding)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            rows,
        )


def run(pdf_path: str, title: str, course_code: str | None, provider: str | None) -> None:
    database_url = os.environ["INGEST_DATABASE_URL"]  # ใช้ advisor_ingest role, แยกจาก backend
    ollama_base_url = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    embed_model = os.environ.get("EMBED_MODEL", "nomic-embed-text")

    logger.info("extracting %s", pdf_path)
    raw_doc = extract_pdf(pdf_path)
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
