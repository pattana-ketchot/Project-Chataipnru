"""
รูปแบบข้อมูลของเส้นทาง /crawl-review

สิ่งที่ตั้งใจ "ไม่" ส่งออก
------------------------
staging_path · last_error · http_etag · http_last_modified · approved_by
ที่อยู่ไฟล์บนเซิร์ฟเวอร์และข้อความผิดพลาดดิบไม่ควรออกไปถึงเบราว์เซอร์ คิวส่ง
has_staged_file เป็นค่าจริง/เท็จแทน ให้หน้าเว็บรู้แค่ว่ามีไฟล์ให้กดดูหรือไม่

สิ่งที่ตั้งใจ "ไม่" รับเข้า
-------------------------
decided_by — ชื่อผู้ตัดสินมาจาก JWT ที่ฝั่งเซิร์ฟเวอร์ถอดแล้วเท่านั้น
ถ้ารับจาก body ใครก็บันทึกในนามคนอื่นได้ ประวัติการอนุมัติจะเชื่อถือไม่ได้ทั้งตาราง
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

# sha256 เป็นเลขฐานสิบหก 64 ตัวเสมอ ตรงกับ CHECK ในฐานข้อมูล
SHA256_PATTERN = r"^[0-9a-f]{64}$"


class QueueItem(BaseModel):
    id: uuid.UUID
    source_url: str
    page_url: str | None
    page_title: str | None
    link_text: str | None
    course_code: str | None
    course_label: str | None
    match_confidence: str | None
    match_score: float | None
    match_candidates: list[str]
    needs_review: bool
    review_reason: str | None
    status: str
    content_length: int | None
    file_sha256: str | None
    previous_sha256: str | None
    has_staged_file: bool
    last_checked_at: datetime | None
    first_seen_at: datetime


class QueueCounts(BaseModel):
    total: int
    needs_review: int
    ambiguous: int
    with_staged_file: int


class QueuePage(BaseModel):
    counts: QueueCounts
    items: list[QueueItem]


class DecisionRequest(BaseModel):
    """ฐานของคำขอที่ตัดสินใจ — file_sha256 คือตัวล็อกว่าคนเห็นไฟล์เดียวกับที่ยังอยู่จริง"""

    file_sha256: str = Field(pattern=SHA256_PATTERN)
    note: str | None = Field(default=None, max_length=2000)


class ApproveRequest(DecisionRequest):
    # รหัสหลักสูตรที่มีอยู่แล้วใน public.courses เท่านั้น — Phase 3 v1 ไม่สร้างหลักสูตรใหม่
    course_code: str = Field(min_length=1, max_length=200)


class IgnoreRequest(DecisionRequest):
    reason: str = Field(min_length=1, max_length=2000)


class UndoRequest(BaseModel):
    file_sha256: str = Field(pattern=SHA256_PATTERN)


class DecisionOut(BaseModel):
    id: uuid.UUID
    crawl_source_id: uuid.UUID
    file_sha256: str
    decision: str
    decided_by: str
    decided_at: datetime
    note: str | None
    course_code: str | None
    course_title: str | None
    superseded_at: datetime | None
    ingest_finished_at: datetime | None
    document_id: uuid.UUID | None
