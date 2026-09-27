"""
คิวตรวจไฟล์ที่ crawler พบ และการบันทึกการตัดสินใจของคน (Phase 3A)

ขอบเขตของโมดูลนี้
-----------------
อ่าน mko.v_crawl_queue · อ่านสองคอลัมน์ของ mko.crawl_sources เพื่อเปิดไฟล์ให้ดู ·
เขียน mko.crawl_decisions เท่านั้น

ไม่แตะ course_documents · ไม่แตะ course_chunks · ไม่แตะ mko.crawl_sources ·
ไม่เรียก pipeline.ingest · ไม่สร้าง embedding — และ role `advisor_api` ก็ไม่มีสิทธิ์ทำ
สิ่งเหล่านั้นอยู่แล้วตั้งแต่ระดับฐานข้อมูล (ดู db/migrations/004_crawl_decisions.sql)

ทำไมไม่ทำ SQLAlchemy model ให้ crawl_sources
--------------------------------------------
ตั้งใจให้เขียนตารางนั้นไม่ได้แม้โดยบังเอิญ การมี model ที่ map ทั้งตารางเปิดทางให้
session.add() หรือการแก้ attribute กลายเป็น UPDATE โดยไม่มีใครตั้งใจ ที่นี่จึงอ่านด้วย
text() ที่ระบุคอลัมน์เอง พร้อม bind parameter ทุกค่า

การอนุมัติกับสถานะไฟล์แยกกัน
---------------------------
โมดูลนี้บันทึกเพียงว่า "คนอนุญาตแล้ว" ไม่ได้ทำให้ไฟล์เดินหน้า การเปลี่ยน
crawl_sources.status เป็น ingested เป็นงานของ worker ใน Phase 3B ซึ่งรันด้วย
role อื่น ผลคือกดอนุมัติแล้วยังไม่มีอะไรเข้าคลังความรู้จนกว่า worker จะทำงานสำเร็จ
"""
from __future__ import annotations

import logging

from psycopg.errors import UniqueViolation
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

logger = logging.getLogger("course_advisor")

NOT_FOUND = "ไม่พบรายการที่ขอ"

# คอลัมน์ของคิว — เขียนไว้ที่เดียวเพื่อให้ list กับ get ส่งรูปแบบเดียวกันเสมอ
_QUEUE_COLUMNS = """
    id, source_url, page_url, page_title, link_text,
    course_code, course_label, match_confidence, match_score, match_candidates,
    needs_review, review_reason, status,
    content_length, file_sha256, previous_sha256, has_staged_file,
    last_checked_at, first_seen_at
"""


class ReviewError(Exception):
    """ข้อผิดพลาดที่ route แปลเป็นรหัสสถานะ HTTP"""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


# ---- อ่านคิว ------------------------------------------------------------
def list_pending(db: Session, limit: int = 100, offset: int = 0) -> dict:
    limit = max(1, min(limit, 200))
    rows = db.execute(
        text(f"SELECT {_QUEUE_COLUMNS} FROM mko.v_crawl_queue LIMIT :limit OFFSET :offset"),
        {"limit": limit, "offset": offset},
    ).mappings().all()

    counts = db.execute(text("""
        SELECT count(*) AS total,
               count(*) FILTER (WHERE needs_review) AS needs_review,
               count(*) FILTER (WHERE match_confidence IN ('ambiguous', 'unknown')) AS ambiguous,
               count(*) FILTER (WHERE has_staged_file) AS with_staged_file
          FROM mko.v_crawl_queue
    """)).mappings().one()

    return {"counts": dict(counts), "items": [dict(r) for r in rows]}


def get_pending(db: Session, crawl_source_id) -> dict:
    row = db.execute(
        text(f"SELECT {_QUEUE_COLUMNS} FROM mko.v_crawl_queue WHERE id = :id"),
        {"id": crawl_source_id},
    ).mappings().first()
    if row is None:
        # ไม่มีแถวนี้ หรือมีแต่ถูกตัดสินใจไปแล้วจึงหลุดจากคิว — ตอบเหมือนกันทั้งสองกรณี
        raise ReviewError(404, NOT_FOUND)
    return dict(row)


def _for_decision(db: Session, crawl_source_id) -> dict:
    """หาแถวในคิวเพื่อตัดสินใจ พร้อมแยกแยะสาเหตุเมื่อไม่อยู่ในคิว

    ต่างจาก get_pending ตรงที่ถ้าแถวหลุดจากคิวเพราะ "ถูกตัดสินใจไปแล้ว" จะตอบ 409
    ไม่ใช่ 404 — คนกดปุ่มซ้ำ (หรือกดพร้อมกับคนอื่น) ต้องได้คำตอบที่บอกได้ว่าเกิดอะไรขึ้น
    ไม่ใช่ "ไม่พบรายการ" ซึ่งทำให้เข้าใจว่าข้อมูลหายไป

    ยังไม่รั่วข้อมูลให้คนนอก เพราะทุกเส้นทางผ่าน require_admin มาแล้ว
    """
    try:
        return get_pending(db, crawl_source_id)
    except ReviewError:
        exists = db.execute(
            text("SELECT id FROM mko.crawl_sources WHERE id = :id"),
            {"id": crawl_source_id},
        ).first()
        if exists is None:
            raise ReviewError(404, NOT_FOUND) from None
        active = db.execute(text("""
            SELECT decision FROM mko.crawl_decisions
             WHERE crawl_source_id = :id AND superseded_at IS NULL
        """), {"id": crawl_source_id}).first()
        if active is not None:
            raise ReviewError(409, "รายการนี้มีการตัดสินใจที่ยังใช้อยู่แล้ว") from None
        # มีแถวจริงแต่ไม่อยู่ในคิว เช่น unchanged ที่ไม่ต้องให้คนตรวจ
        raise ReviewError(404, NOT_FOUND) from None


def staged_file_location(db: Session, crawl_source_id) -> tuple[str | None, str | None]:
    """คืน (staging_path, file_sha256) จากฐานข้อมูล — ค่าที่ผู้ใช้ส่งมาไม่เกี่ยวข้องเลย

    อ่านจากตารางจริงเพราะ v_crawl_queue ตั้งใจไม่มี staging_path
    role advisor_api มีสิทธิ์ SELECT เฉพาะสี่คอลัมน์ของตารางนี้
    """
    row = db.execute(
        text("SELECT staging_path, file_sha256 FROM mko.crawl_sources WHERE id = :id"),
        {"id": crawl_source_id},
    ).mappings().first()
    if row is None:
        raise ReviewError(404, NOT_FOUND)
    return row["staging_path"], row["file_sha256"]


# ---- ตรวจก่อนบันทึก ----------------------------------------------------
def _guard_sha(item: dict, client_sha: str) -> None:
    """ไฟล์ที่คนเห็นบนหน้าจอต้องเป็นไฟล์เดียวกับที่ยังอยู่ในฐานข้อมูล

    ถ้า crawler โหลดไฟล์ใหม่ทับระหว่างที่คนกำลังดูอยู่ sha จะไม่ตรง การอนุมัติจึงต้อง
    ไม่ผ่าน ไม่งั้นคนจะอนุมัติไฟล์ที่ตัวเองไม่ได้เห็น
    """
    current = item.get("file_sha256")
    if not current:
        raise ReviewError(409, "รายการนี้ยังไม่มีไฟล์ที่โหลดสำเร็จ ยังตัดสินใจไม่ได้")
    if current != client_sha:
        raise ReviewError(409, "ไฟล์เปลี่ยนไปแล้วหลังจากที่คุณเปิดดู กรุณาโหลดคิวใหม่")


def resolve_course(db: Session, course_code: str) -> str:
    """คืนชื่อหลักสูตรของรหัสนี้ ถ้าไม่มีในระบบให้ปฏิเสธ

    Phase 3 v1 ไม่สร้างหลักสูตรใหม่ ไม่เรียก get_or_create_course() และ role
    advisor_api ก็ไม่มีสิทธิ์ INSERT ลง courses อยู่แล้ว การพิมพ์รหัสผิดจึงต้อง
    กลายเป็นข้อผิดพลาด ไม่ใช่หลักสูตรใหม่ที่โผล่มาในระบบเงียบ ๆ
    """
    row = db.execute(
        text("SELECT title FROM courses WHERE code = :code"),
        {"code": course_code},
    ).mappings().first()
    if row is None:
        raise ReviewError(422, f"ไม่มีหลักสูตรรหัส {course_code!r} ในระบบ "
                               "ต้องเลือกจากหลักสูตรที่มีอยู่แล้วเท่านั้น")
    return row["title"]


# ---- บันทึกการตัดสินใจ -------------------------------------------------
def _insert_decision(db: Session, *, crawl_source_id, file_sha256: str, decision: str,
                     decided_by: str, note: str | None, course_code: str | None,
                     course_title: str | None) -> dict:
    try:
        row = db.execute(text("""
            INSERT INTO mko.crawl_decisions
                (crawl_source_id, file_sha256, decision, decided_by, note,
                 course_code, course_title)
            VALUES (:sid, :sha, :decision, :who, :note, :code, :title)
            RETURNING id, crawl_source_id, file_sha256, decision, decided_by, decided_at,
                      note, course_code, course_title, superseded_at,
                      ingest_finished_at, document_id
        """), {"sid": crawl_source_id, "sha": file_sha256, "decision": decision,
               "who": decided_by, "note": note, "code": course_code,
               "title": course_title}).mappings().one()
    except IntegrityError as e:
        db.rollback()
        # ดัชนี uq_crawl_decisions_active กันสองคนกดพร้อมกันที่ระดับฐานข้อมูล
        if isinstance(e.orig, UniqueViolation):
            raise ReviewError(409, "รายการนี้มีการตัดสินใจที่ยังใช้อยู่แล้ว") from e
        raise
    db.commit()
    return dict(row)


def approve(db: Session, crawl_source_id, *, file_sha256: str, course_code: str,
            note: str | None, decided_by: str) -> dict:
    item = _for_decision(db, crawl_source_id)
    _guard_sha(item, file_sha256)
    if not item["has_staged_file"]:
        raise ReviewError(409, "รายการนี้ไม่มีไฟล์รออนุมัติ จึงไม่มีอะไรให้นำเข้า")
    course_title = resolve_course(db, course_code)
    out = _insert_decision(db, crawl_source_id=crawl_source_id, file_sha256=file_sha256,
                           decision="approve", decided_by=decided_by, note=note,
                           course_code=course_code, course_title=course_title)
    logger.info("อนุมัติไฟล์ในคิว crawl_source_id=%s course_code=%s", crawl_source_id, course_code)
    return out


def ignore(db: Session, crawl_source_id, *, file_sha256: str, reason: str,
           decided_by: str) -> dict:
    item = _for_decision(db, crawl_source_id)
    _guard_sha(item, file_sha256)
    out = _insert_decision(db, crawl_source_id=crawl_source_id, file_sha256=file_sha256,
                           decision="ignore", decided_by=decided_by, note=reason,
                           course_code=None, course_title=None)
    logger.info("ทำเครื่องหมายไม่เกี่ยวข้อง crawl_source_id=%s", crawl_source_id)
    return out


def undo(db: Session, crawl_source_id, *, file_sha256: str, decided_by: str) -> dict:
    """ถอนการตัดสินใจที่ยังใช้อยู่ — ทำได้ก่อนนำเข้าเท่านั้น

    ถอนหลังนำเข้าแล้วไม่ได้ เพราะการถอนไม่ย้อนคลังความรู้ ถ้ายอมให้ถอน คนจะเข้าใจว่า
    เอกสารถูกเอาออกจากระบบแล้วซึ่งไม่จริง การเอาเอกสารออกเป็นงานแยกที่ต้องใช้สิทธิ์อื่น
    """
    current = db.execute(text("""
        SELECT id, decision, ingest_finished_at, document_id
          FROM mko.crawl_decisions
         WHERE crawl_source_id = :sid AND file_sha256 = :sha AND superseded_at IS NULL
    """), {"sid": crawl_source_id, "sha": file_sha256}).mappings().first()
    if current is None:
        raise ReviewError(404, "ไม่พบการตัดสินใจที่ยังใช้อยู่ของไฟล์นี้")
    if current["ingest_finished_at"] is not None or current["document_id"] is not None:
        raise ReviewError(409, "รายการนี้นำเข้าคลังความรู้แล้ว ถอนการอนุมัติไม่ได้")

    row = db.execute(text("""
        UPDATE mko.crawl_decisions
           SET superseded_at = clock_timestamp(), superseded_by = :who
         WHERE id = :id AND superseded_at IS NULL AND ingest_finished_at IS NULL
        RETURNING id, crawl_source_id, file_sha256, decision, decided_by, decided_at,
                  note, course_code, course_title, superseded_at,
                  ingest_finished_at, document_id
    """), {"id": current["id"], "who": decided_by}).mappings().first()
    if row is None:
        # มีใครถอนหรือ worker นำเข้าไปแล้วระหว่างสองคำสั่งนี้
        db.rollback()
        raise ReviewError(409, "สถานะของรายการนี้เปลี่ยนไปแล้ว กรุณาโหลดคิวใหม่")
    db.commit()
    logger.info("ถอนการตัดสินใจ crawl_source_id=%s", crawl_source_id)
    return dict(row)
