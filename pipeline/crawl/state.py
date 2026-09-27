"""
บันทึกสถานะของลิงก์ PDF ที่เฝ้าดู ลงตาราง mko.crawl_sources

ขอบเขตของโมดูลนี้
-----------------
แตะเฉพาะ mko.crawl_sources เท่านั้น อ่าน public.course_documents แบบอ่านอย่างเดียว
เพื่อเทียบ sha256 ไม่เขียนอะไรใน public เลย และไม่มีคำสั่ง DELETE สักจุด
(สิทธิ์ DELETE ก็ไม่ได้ให้ไว้ใน migration 003 ด้วย)

ทำไมสถานะกับธงรอตรวจแยกกัน
--------------------------
status บอกว่าไฟล์เดินทางไปถึงไหนแล้ว ส่วน needs_review บอกว่าคนต้องเข้ามาดูก่อนไปต่อ
เป็นคนละเรื่องและเกิดพร้อมกันได้ — ไฟล์ที่โหลดเก็บไว้แล้วแต่ยังระบุหลักสูตรไม่ได้
คือ status='downloaded' และ needs_review=true

ถ้ายัดรวมเป็นค่าเดียวจะต้องมีสถานะลูกผสมเพิ่มขึ้นเรื่อยๆ และคิวงานของคนตรวจจะ
กรองยากขึ้นทุกครั้งที่เพิ่มสถานะใหม่
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg.rows import dict_row

logger = logging.getLogger("pipeline.crawl.state")

# แปลงคำบอกความมั่นใจฝั่ง Python เป็นค่าที่ CHECK constraint ยอมรับ
CONFIDENCE_DB = {"สูง": "high", "ปานกลาง": "medium", "กำกวม": "ambiguous", "ระบุไม่ได้": "unknown"}


@dataclass
class SourceRow:
    id: str
    source_url: str
    status: str
    file_sha256: str | None
    http_etag: str | None
    http_last_modified: str | None
    content_length: int | None
    staging_path: str | None
    needs_review: bool
    approved_at: Any


class CrawlStore:
    """ชั้นเข้าถึงฐานข้อมูลของ crawler — เปิด/ปิดด้วย with"""

    def __init__(self, database_url: str) -> None:
        self._url = database_url
        self._conn: psycopg.Connection | None = None

    def __enter__(self) -> "CrawlStore":
        self._conn = psycopg.connect(self._url, row_factory=dict_row)
        return self

    def __exit__(self, *exc) -> None:
        if self._conn:
            self._conn.close()

    @property
    def conn(self) -> psycopg.Connection:
        assert self._conn is not None, "ต้องใช้ผ่าน with CrawlStore(...) as store:"
        return self._conn

    # ---- อ่านคลังเอกสารเดิม (อ่านอย่างเดียว) ----------------------------
    def known_sha256(self) -> dict[str, dict]:
        """sha256 -> ข้อมูลเอกสารในคลัง ใช้ตอบว่า 'ไฟล์นี้มีในระบบแล้ว'"""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT d.id, d.file_sha256, d.original_filename, d.page_count,
                       c.code AS course_code, c.title AS course_title
                FROM course_documents d
                JOIN courses c ON c.id = d.course_id
            """)
            return {r["file_sha256"]: r for r in cur.fetchall()}

    # ---- อ่านสถานะเดิมของลิงก์ -------------------------------------------
    def get_source(self, source_url: str) -> SourceRow | None:
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT id::text, source_url, status, file_sha256, http_etag,
                       http_last_modified, content_length, staging_path,
                       needs_review, approved_at
                FROM mko.crawl_sources WHERE source_url = %s
            """, (source_url,))
            r = cur.fetchone()
        return SourceRow(**r) if r else None

    # ---- บันทึก ----------------------------------------------------------
    def upsert(self, *, source_url: str, page_url: str | None, page_title: str | None,
               link_text: str | None, course_code: str | None, course_label: str | None,
               match_confidence: str | None, match_score: float | None,
               match_candidates: list[str], needs_review: bool, review_reason: str | None,
               status: str, last_error: str | None, bump_error: bool,
               http_etag: str | None, http_last_modified: str | None,
               content_length: int | None, file_sha256: str | None,
               previous_sha256: str | None, staging_path: str | None,
               document_id: str | None) -> str:
        """
        เขียนสถานะล่าสุดของลิงก์หนึ่ง คืน id ของแถว

        ใช้ ON CONFLICT (source_url) เพราะลิงก์เดียวกันจะถูกตรวจซ้ำทุกรอบ
        คอลัมน์ที่ COALESCE ไว้คือค่าที่ไม่ควรหายเมื่อรอบนี้หาไม่เจอ เช่น
        ตรวจรอบนี้แล้ว HEAD ไม่คืน ETag มา ค่าเดิมต้องอยู่ต่อ ไม่ใช่ถูกล้างเป็น NULL
        """
        params = {
            "source_url": source_url, "page_url": page_url, "page_title": page_title,
            "link_text": link_text, "course_code": course_code, "course_label": course_label,
            "match_confidence": match_confidence, "match_score": match_score,
            "match_candidates": json.dumps(match_candidates, ensure_ascii=False),
            "needs_review": needs_review, "review_reason": review_reason,
            "status": status, "last_error": last_error,
            "err_inc": 1 if bump_error else 0,
            "http_etag": http_etag, "http_last_modified": http_last_modified,
            "content_length": content_length, "file_sha256": file_sha256,
            "previous_sha256": previous_sha256, "staging_path": staging_path,
            "document_id": document_id,
        }
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO mko.crawl_sources (
                    source_url, page_url, page_title, link_text,
                    course_code, course_label, match_confidence, match_score, match_candidates,
                    needs_review, review_reason, status, last_checked_at, last_error, error_count,
                    http_etag, http_last_modified, content_length,
                    file_sha256, previous_sha256, staging_path, document_id
                ) VALUES (
                    %(source_url)s, %(page_url)s, %(page_title)s, %(link_text)s,
                    %(course_code)s, %(course_label)s, %(match_confidence)s, %(match_score)s,
                    %(match_candidates)s::jsonb,
                    %(needs_review)s, %(review_reason)s, %(status)s, now(), %(last_error)s, %(err_inc)s,
                    %(http_etag)s, %(http_last_modified)s, %(content_length)s,
                    %(file_sha256)s, %(previous_sha256)s, %(staging_path)s, %(document_id)s
                )
                ON CONFLICT (source_url) DO UPDATE SET
                    page_url         = EXCLUDED.page_url,
                    page_title       = EXCLUDED.page_title,
                    link_text        = EXCLUDED.link_text,
                    course_code      = EXCLUDED.course_code,
                    course_label     = EXCLUDED.course_label,
                    match_confidence = EXCLUDED.match_confidence,
                    match_score      = EXCLUDED.match_score,
                    match_candidates = EXCLUDED.match_candidates,
                    needs_review     = EXCLUDED.needs_review,
                    review_reason    = EXCLUDED.review_reason,
                    status           = EXCLUDED.status,
                    last_checked_at  = now(),
                    last_error       = EXCLUDED.last_error,
                    error_count      = CASE WHEN %(err_inc)s = 1
                                            THEN mko.crawl_sources.error_count + 1
                                            ELSE 0 END,
                    -- ค่าที่ไม่ควรหายถ้ารอบนี้ไม่ได้มา
                    http_etag          = COALESCE(EXCLUDED.http_etag, mko.crawl_sources.http_etag),
                    http_last_modified = COALESCE(EXCLUDED.http_last_modified, mko.crawl_sources.http_last_modified),
                    content_length     = COALESCE(EXCLUDED.content_length, mko.crawl_sources.content_length),
                    file_sha256        = COALESCE(EXCLUDED.file_sha256, mko.crawl_sources.file_sha256),
                    previous_sha256    = COALESCE(EXCLUDED.previous_sha256, mko.crawl_sources.previous_sha256),
                    staging_path       = COALESCE(EXCLUDED.staging_path, mko.crawl_sources.staging_path),
                    document_id        = COALESCE(EXCLUDED.document_id, mko.crawl_sources.document_id)
                RETURNING id::text
            """, params)
            return cur.fetchone()["id"]

    def pending(self) -> list[dict]:
        with self.conn.cursor() as cur:
            cur.execute("SELECT * FROM mko.v_crawl_pending")
            return cur.fetchall()

    def counts_by_status(self) -> dict[str, int]:
        with self.conn.cursor() as cur:
            cur.execute("SELECT status, count(*) AS n FROM mko.crawl_sources GROUP BY status")
            return {r["status"]: r["n"] for r in cur.fetchall()}
