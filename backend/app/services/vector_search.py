"""
Vector search บน course_chunks (pgvector) — item 2 ของ requirement
("ดึงข้อมูลจาก Vector Database")

SECURITY: ใช้ SQLAlchemy expression/ORM ทั้งหมด ไม่มี string interpolation
ของ input ผู้ใช้เข้า SQL โดยตรง (ป้องกัน SQL injection)
"""
import uuid

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.course import Course, CourseChunk
from app.schemas.course import SearchResultChunk


def search_similar_chunks(
    db: Session,
    query_embedding: list[float],
    top_k: int = 8,
    course_ids: list[uuid.UUID] | None = None,
) -> list[SearchResultChunk]:
    """
    Cosine-distance ANN search ผ่าน pgvector operator `<=>`.
    similarity = 1 - distance (ค่ายิ่งมากยิ่งใกล้เคียง)
    """
    distance = CourseChunk.embedding.cosine_distance(query_embedding)

    stmt = (
        select(CourseChunk, Course.title, distance.label("distance"))
        .join(Course, Course.id == CourseChunk.course_id)
        .where(Course.is_active.is_(True))
        .order_by(distance)
        .limit(top_k)
    )
    # จำกัดขอบเขตเมื่อระบุได้ว่าคำถามถามถึงหลักสูตรใด (ดู services/course_scope.py)
    if course_ids:
        stmt = stmt.where(CourseChunk.course_id.in_(course_ids))

    if course_ids:
        # ivfflat เลือก candidate จากดัชนีก่อนแล้วจึงกรองด้วย WHERE ผลคือเมื่อกรอง
        # ให้เหลือหลักสูตรเดียว (422 จาก 7,301 chunk) candidate ที่ดัชนีเลือกมา
        # อาจไม่มีของหลักสูตรนั้นเลย แล้วคืนผลลัพธ์ว่างโดยไม่แจ้งข้อผิดพลาด
        # — ทดสอบแล้วได้ 0 แถวทั้งที่หลักสูตรนั้นมี chunk อยู่จริง 422 ก้อน
        #
        # เมื่อกรองแล้วเหลือข้อมูลน้อย การไล่คำนวณระยะทางตรงๆ ทั้งชุดเร็วอยู่แล้ว
        # และให้ผลที่ถูกต้องแน่นอน จึงปิดการใช้ดัชนีเฉพาะกรณีนี้
        # (SET LOCAL มีผลเฉพาะใน transaction ปัจจุบัน ไม่กระทบ query อื่น)
        db.execute(text("SET LOCAL enable_indexscan = off"))
        db.execute(text("SET LOCAL enable_bitmapscan = off"))

    rows = db.execute(stmt).all()
    return [
        SearchResultChunk(
            chunk_id=chunk.id,
            course_id=chunk.course_id,
            course_title=title,
            page_number=chunk.page_number,
            content=chunk.content,
            score=round(1.0 - float(dist), 4),
        )
        for chunk, title, dist in rows
    ]
