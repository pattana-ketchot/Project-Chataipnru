"""
Vector search บน course_chunks (pgvector) — item 2 ของ requirement
("ดึงข้อมูลจาก Vector Database")

SECURITY: ใช้ SQLAlchemy expression/ORM ทั้งหมด ไม่มี string interpolation
ของ input ผู้ใช้เข้า SQL โดยตรง (ป้องกัน SQL injection)
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.course import Course, CourseChunk
from app.schemas.course import SearchResultChunk


def search_similar_chunks(
    db: Session,
    query_embedding: list[float],
    top_k: int = 8,
    course_id: uuid.UUID | None = None,
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
    if course_id is not None:
        stmt = stmt.where(CourseChunk.course_id == course_id)

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
