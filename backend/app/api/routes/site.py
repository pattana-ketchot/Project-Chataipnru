"""
ข้อมูลหน้าเว็บจาก schema web — Phase 4 ขั้นที่หน้าเว็บเลิกคุยกับ Supabase

    GET /site/courses        รายการหลักสูตรที่เผยแพร่
    GET /site/courses/{id}   หลักสูตรเดียว

ทำไมต้องมีเส้นทางนี้
-------------------
หน้าเว็บเป็น SPA ที่เรียก `supabase.from('courses').select()` จากในเบราว์เซอร์โดยตรง
ซึ่งทำได้เพราะ Supabase แปลงตารางเป็น REST API ให้ เมื่อย้ายข้อมูลมาที่ PostgreSQL ของเรา
เบราว์เซอร์ต่อฐานข้อมูลตรง ๆ ไม่ได้ จึงต้องมีชั้นนี้มาแทน

ชื่อฟิลด์ที่คืนไปใช้ชื่อของปลายทาง (`logo_url` ไม่ใช่ `logo`) หน้าเว็บมีที่แปลงชื่อ
อยู่ที่เดียวคือ src/lib/siteCourses.js การคงชื่อเก่าไว้เพื่อให้แก้น้อยลงจะลากหนี้เดิม
ต่อไปอีกนาน

ไม่ต้องเข้าสู่ระบบ เพราะเป็นข้อมูลที่เปิดให้นักเรียนทั่วไปดูอยู่แล้ว — เหมือนที่
policy ของต้นทางเปิดให้ทุกคนอ่าน `courses`

คืนเฉพาะแถวที่ `is_published` เพราะต้นทางไม่มีธงนี้ (ทุกแถวถือว่าเผยแพร่) แต่ปลายทางมี
และการกรองย้ายจาก RLS มาอยู่ที่นี่แล้ว — ถ้าลืมกรอง ของที่ยังไม่พร้อมจะหลุดออกสาธารณะ
"""
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter(prefix="/site", tags=["site"])
logger = logging.getLogger("course_advisor")

# course_id คือสิ่งที่การรวมฐานข้อมูลให้มา — เชื่อมหลักสูตรที่แสดงบนเว็บเข้ากับหลักสูตร
# ที่ AI ตอบจากเอกสาร หน้าเว็บใช้มันเรียก /course-facts และ /documents ได้ตรง ๆ
# โดยไม่ต้องเทียบชื่อข้ามฐานอีก
# created_at มีไว้ให้แถบหลักสูตรหน้าแรกเรียงตามลำดับที่เพิ่มเข้ามา ซึ่งเป็นพฤติกรรมเดิม
_COLUMNS = "id, course_id, title, title_en, description, logo_url, careers, detail, created_at, updated_at"


def _row(row) -> dict:
    out = dict(row)
    out["id"] = str(out["id"])
    out["course_id"] = str(out["course_id"]) if out["course_id"] else None
    # careers เป็น TEXT[] ที่อาจเป็น NULL — หน้าเว็บคาดว่าเป็นรายการเสมอ จะได้ไม่ต้องกัน null ทุกที่
    out["careers"] = list(out["careers"] or [])
    for key in ("created_at", "updated_at"):
        out[key] = out[key].isoformat() if out[key] else None
    return out


@router.get("/courses")
def list_courses(db: Session = Depends(get_db)) -> dict:
    """
    รายการหลักสูตรทั้งหมดที่เผยแพร่ เรียงตามชื่อไทย

    คืนทั้งก้อนครั้งเดียวเพราะมี 12 แถว การแบ่งหน้าไม่คุ้มความซับซ้อน
    ถ้าวันหนึ่งมีหลักสูตรหลักร้อย ค่อยเพิ่ม limit/offset ตอนนั้น
    """
    try:
        rows = db.execute(
            text(f"select {_COLUMNS} from web.site_courses where is_published order by title")
        ).mappings().all()
    except Exception:  # noqa: BLE001
        # ยังไม่ได้นำข้อมูลเข้า หรือ schema web ยังไม่มี — บอกให้ชัดว่าอ่านไม่ได้
        # **ห้ามคืนรายการว่างเงียบ ๆ** เพราะหน้าเว็บจะดูเหมือน "ไม่มีหลักสูตร" ทั้งที่อ่านไม่ได้
        logger.exception("อ่าน web.site_courses ไม่สำเร็จ")
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "ยังอ่านข้อมูลหลักสูตรไม่ได้ในขณะนี้") from None
    return {"courses": [_row(r) for r in rows]}


@router.get("/courses/{course_id}")
def get_course(course_id: str, db: Session = Depends(get_db)) -> dict:
    """
    หลักสูตรเดียวตามรหัส

    รหัสที่ใช้คือรหัสเดิมจากต้นทาง (ขั้นนำข้อมูลเข้าคงรหัสไว้) ลิงก์ /courses/<id>
    ที่คนเคยบันทึกไว้จึงยังเปิดได้เหมือนเดิมหลังย้าย
    """
    try:
        key = uuid.UUID(course_id)
    except ValueError:
        # ไม่ใช่รหัสที่เป็นไปได้ — ตอบ 404 เหมือนหาไม่เจอ ไม่ใช่ 500
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบหลักสูตรนี้") from None

    try:
        row = db.execute(
            text(f"select {_COLUMNS} from web.site_courses where id = :id and is_published"),
            {"id": str(key)},
        ).mappings().first()
    except Exception:  # noqa: BLE001
        logger.exception("อ่าน web.site_courses รายตัวไม่สำเร็จ")
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "ยังอ่านข้อมูลหลักสูตรไม่ได้ในขณะนี้") from None

    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบหลักสูตรนี้")
    return _row(row)


# ── ข่าวของคณะที่ทีมเขียนเอง ─────────────────────────────────────────

_NEWS_COLUMNS = "id, title, description, category, published_on, image_url, created_at"


@router.get("/news")
def list_news(limit: int = 20, db: Session = Depends(get_db)) -> dict:
    """
    ข่าวที่เผยแพร่แล้วเท่านั้น

    ที่ต้นทาง การกรองนี้เป็น RLS policy `USING (status = 'published')` เมื่อย้ายมาที่นี่
    มันกลายเป็นเงื่อนไขในโค้ด — ลืมเมื่อไรข่าวร่างหลุดออกสาธารณะทันที
    """
    try:
        rows = db.execute(
            text(f"select {_NEWS_COLUMNS} from web.news where status = 'published'"
                 " order by published_on desc nulls last, created_at desc limit :n"),
            {"n": max(1, min(limit, 100))},
        ).mappings().all()
    except Exception:  # noqa: BLE001
        logger.exception("อ่าน web.news ไม่สำเร็จ")
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "ยังอ่านข่าวไม่ได้ในขณะนี้") from None

    out = []
    for row in rows:
        item = dict(row)
        item["id"] = str(item["id"])
        item["published_on"] = item["published_on"].isoformat() if item["published_on"] else None
        item["created_at"] = item["created_at"].isoformat() if item["created_at"] else None
        out.append(item)
    return {"news": out}


# ── ข่าว SCI Connect ที่ดึงมาจากเว็บต้นทางอัตโนมัติ ──────────────────

_EXTERNAL_COLUMNS = ("slug, title, description, image_url, published_text, detail_url,"
                     " facebook_url, published_at")


@router.get("/external-news")
def list_external_news(limit: int = 15, db: Session = Depends(get_db)) -> dict:
    try:
        rows = db.execute(
            text(f"select {_EXTERNAL_COLUMNS} from web.external_news"
                 " order by published_at desc nulls last, synced_at desc limit :n"),
            {"n": max(1, min(limit, 100))},
        ).mappings().all()
    except Exception:  # noqa: BLE001
        logger.exception("อ่าน web.external_news ไม่สำเร็จ")
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "ยังอ่านข่าวไม่ได้ในขณะนี้") from None
    return {"news": [_external_row(r) for r in rows]}


@router.get("/external-news/{slug}")
def get_external_news(slug: str, db: Session = Depends(get_db)) -> dict:
    try:
        row = db.execute(
            text(f"select {_EXTERNAL_COLUMNS} from web.external_news where slug = :slug"),
            {"slug": slug},
        ).mappings().first()
    except Exception:  # noqa: BLE001
        logger.exception("อ่าน web.external_news รายตัวไม่สำเร็จ")
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "ยังอ่านข่าวไม่ได้ในขณะนี้") from None

    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบข่าวนี้")
    return _external_row(row)


def _external_row(row) -> dict:
    item = dict(row)
    item["published_at"] = item["published_at"].isoformat() if item["published_at"] else None
    return item
