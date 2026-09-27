"""
/crawl-review — คิวตรวจไฟล์หลักสูตรที่ crawler พบ และการอนุมัติของผู้ดูแล (Phase 3A)

ทำไม prefix ไม่ใช่ /admin
-------------------------
Caddy ส่ง /api/admin/* ทั้ง prefix ไปที่บริการ webapi ซึ่งเป็นโค้ดของทีมออกแบบและคุยกับ
Supabase (ดู Caddyfile) ถ้าตั้งเส้นทางใหม่ไว้ใต้ /api/admin คำขอจะไม่มาถึง FastAPI เลย
prefix /crawl-review ตกลง `handle /api/*` เดิมซึ่งตัด /api ออกแล้วส่งมาที่นี่
จึงใช้งานได้โดยไม่ต้องแก้ Caddyfile และไม่เสี่ยงกระทบเส้นทางของทีมอื่น

ขอบเขตของเส้นทางเหล่านี้
-----------------------
บันทึก "เจตนาของคน" ได้เท่านั้น ไม่มีเส้นทางใดเรียก pipeline.ingest ไม่สร้าง embedding
ไม่เขียน course_documents / course_chunks และไม่เปลี่ยน mko.crawl_sources
role advisor_api ที่ backend ใช้ก็ไม่มีสิทธิ์ทำสิ่งเหล่านั้นอยู่แล้ว การห้ามจึงมีสองชั้น
ไม่ใช่แค่ชั้นที่เราเขียนโค้ดเอง

การนำเข้าจริงเป็นงานของ worker ใน Phase 3B ซึ่งรันด้วย role advisor_ingest คนละตัว

ทำไมทุกเส้นทางตอบ 404 ข้อความเดียวกันเมื่อหาไม่เจอ
------------------------------------------------
ไม่มีรายการนี้ · มีแต่ถูกตัดสินใจไปแล้ว · ไฟล์หาย · ลายนิ้วมือไม่ตรง · ไม่ใช่ PDF ·
ยังไม่ได้เปิดฟีเจอร์ — ทั้งหมดตอบเหมือนกัน เพื่อไม่บอกผู้ถามว่าระบบมีอะไรอยู่บ้าง
หรือเก็บไว้ที่ไหน รายละเอียดจริงอยู่ใน log ฝั่งเซิร์ฟเวอร์เท่านั้น
(กติกาเดียวกับ routes/documents.py)
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import rate_limiter, require_admin
from app.db.session import get_db
from app.models.user import User
from app.schemas.crawl_review import (
    ApproveRequest,
    DecisionOut,
    IgnoreRequest,
    QueuePage,
    QueueItem,
    UndoRequest,
)
from app.services import crawl_review
from app.services.crawl_review import NOT_FOUND, ReviewError
from app.services.staging_store import get_staging_store

# require_admin คลุมทั้ง router ไม่ใช่ทีละเส้นทาง — เส้นทางที่เพิ่มในอนาคตจะถูกคลุมด้วย
# โดยไม่ต้องจำ ถ้าใส่ทีละเส้นทางแล้วลืมหนึ่งที่ คิวงานภายในจะหลุดออกไปให้ใครก็อ่านได้
router = APIRouter(
    prefix="/crawl-review",
    tags=["crawl-review"],
    dependencies=[Depends(require_admin)],
)

# ตัวจำกัดจำนวนคำขอใส่เฉพาะเส้นทางที่ "ตัดสินใจ" ไม่ใส่กับเส้นทางที่อ่าน
#
# rate_limiter ยอมให้ 30 คำขอต่อนาทีต่อบัญชี (settings.rate_limit_per_minute) ซึ่งพอ
# สำหรับการกดอนุมัติ — คนตรวจกดไม่กี่ครั้งต่อรอบ แต่ไม่พอสำหรับการอ่าน เพราะการเปิด
# หน้าคิวหนึ่งครั้งแล้วไล่เปิด PDF ดูทีละเล่มใช้คำขอเกินสามสิบได้ง่าย ๆ ถ้าคลุมทั้ง
# router คนตรวจจะโดน 429 กลางงานทั้งที่ใช้ตามปกติ
#
# เส้นทางที่อ่านยังกัน abuse ด้วย require_admin อยู่แล้ว ผู้ใช้ทั่วไปเข้าไม่ถึงเลย
# (หมายเหตุ: ตัวจำกัดนี้นับแยกต่อโปรเซสตามที่ deps.py เขียนไว้ จึงเป็นของระดับ dev)
_decide = [Depends(rate_limiter)]


def _handle(err: ReviewError) -> HTTPException:
    return HTTPException(err.status_code, err.detail)


@router.get("/pending", response_model=QueuePage)
def pending(db: Session = Depends(get_db), limit: int = 100, offset: int = 0) -> dict:
    return crawl_review.list_pending(db, limit=limit, offset=offset)


@router.get("/{crawl_source_id}", response_model=QueueItem)
def detail(crawl_source_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    try:
        return crawl_review.get_pending(db, crawl_source_id)
    except ReviewError as e:
        raise _handle(e) from e


@router.get("/{crawl_source_id}/pdf")
def staged_pdf(crawl_source_id: uuid.UUID, db: Session = Depends(get_db)) -> FileResponse:
    """เปิดไฟล์ที่รออนุมัติให้ผู้ดูแลดูก่อนตัดสินใจ

    ผู้ใช้ส่งมาได้เพียง UUID ที่อยู่ไฟล์มาจากฐานข้อมูล และ services/staging_store.py
    ตรวจสามชั้นก่อนส่ง (อยู่ใต้โฟลเดอร์ที่อนุญาต · sha256 ตรง · ขึ้นต้นด้วย %PDF-)
    """
    try:
        staging_path, sha256 = crawl_review.staged_file_location(db, crawl_source_id)
    except ReviewError as e:
        raise _handle(e) from e

    staged = get_staging_store().open(crawl_source_id, staging_path, sha256)
    if staged is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)

    # inline เพื่อให้เบราว์เซอร์เปิดด้วยตัวอ่าน PDF ของตัวเอง ผู้ดูแลจะได้พลิกดูทั้งเล่ม
    # ก่อนกดอนุมัติ ไม่ใช่ดาวน์โหลดแล้วต้องเปิดจากเครื่องตัวเอง
    return FileResponse(
        staged.path,
        media_type=staged.media_type,
        filename=staged.filename,
        content_disposition_type="inline",
    )


@router.post("/{crawl_source_id}/approve", response_model=DecisionOut,
             status_code=status.HTTP_201_CREATED, dependencies=_decide)
def approve(crawl_source_id: uuid.UUID, payload: ApproveRequest,
            db: Session = Depends(get_db), admin: User = Depends(require_admin)) -> dict:
    try:
        return crawl_review.approve(
            db, crawl_source_id,
            file_sha256=payload.file_sha256,
            course_code=payload.course_code,
            note=payload.note,
            # มาจาก JWT ที่ถอดฝั่งเซิร์ฟเวอร์ ไม่ใช่จาก body — ดู schemas/crawl_review.py
            decided_by=str(admin.email),
        )
    except ReviewError as e:
        raise _handle(e) from e


@router.post("/{crawl_source_id}/ignore", response_model=DecisionOut,
             status_code=status.HTTP_201_CREATED, dependencies=_decide)
def ignore(crawl_source_id: uuid.UUID, payload: IgnoreRequest,
           db: Session = Depends(get_db), admin: User = Depends(require_admin)) -> dict:
    try:
        return crawl_review.ignore(
            db, crawl_source_id,
            file_sha256=payload.file_sha256,
            reason=payload.reason,
            decided_by=str(admin.email),
        )
    except ReviewError as e:
        raise _handle(e) from e


@router.post("/{crawl_source_id}/undo", response_model=DecisionOut, dependencies=_decide)
def undo(crawl_source_id: uuid.UUID, payload: UndoRequest,
         db: Session = Depends(get_db), admin: User = Depends(require_admin)) -> dict:
    try:
        return crawl_review.undo(
            db, crawl_source_id,
            file_sha256=payload.file_sha256,
            decided_by=str(admin.email),
        )
    except ReviewError as e:
        raise _handle(e) from e
