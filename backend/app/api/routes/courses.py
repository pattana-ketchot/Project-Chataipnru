import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.course import Course
from app.schemas.course import CourseOut

router = APIRouter(prefix="/courses", tags=["courses"])

# หมายเหตุ: endpoint สำหรับ "ingest" (upload PDF ใหม่) ไม่ได้อยู่ในไฟล์นี้โดยตรง —
# การ extract/clean/chunk/embed เป็นงานหนักและควรรันแบบ offline/async job
# (ดู pipeline/ingest.py) แล้วให้ pipeline เขียนผลลัพธ์ลง DB โดยตรงด้วย role
# `advisor_ingest` ที่สิทธิ์จำกัด (ดู db/schema.sql) แทนที่จะทำ synchronous ผ่าน
# HTTP request เดียว ซึ่งจะ block worker และเสี่ยง DoS ถ้าเปิดให้ upload ได้อิสระ


@router.get("", response_model=list[CourseOut])
def list_courses(db: Session = Depends(get_db), limit: int = 50, offset: int = 0) -> list[Course]:
    limit = min(limit, 100)  # กัน client ขอ limit ใหญ่เกินจน query หนัก
    return db.query(Course).filter(Course.is_active.is_(True)).offset(offset).limit(limit).all()


@router.get("/{course_id}", response_model=CourseOut)
def get_course(course_id: uuid.UUID, db: Session = Depends(get_db)) -> Course:
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(404, "course not found")
    return course
