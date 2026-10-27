"""
อัปโหลดและเปิดไฟล์ของหน้าเว็บ — Phase 4 (มาแทน Supabase Storage)

    POST /uploads/{category}   อัปโหลด (ผู้ดูแลที่อนุมัติแล้วเท่านั้น)
    GET  /uploads/{path}       เปิดไฟล์

หมวดไฟล์: logo (โลโก้หลักสูตร) · news (รูปข่าว) · knowledge (ไฟล์คลังความรู้)

ทำไมการอ่านไม่ต้องเข้าสู่ระบบ
-----------------------------
โลโก้หลักสูตรและรูปข่าวแสดงบนหน้าเว็บสาธารณะอยู่แล้ว การบังคับให้ล็อกอินก่อนดูรูป
จะทำให้หน้าเว็บแสดงรูปไม่ได้ และของเดิมที่ Supabase ก็เป็น public URL เหมือนกัน

**ไฟล์คลังความรู้ที่ไม่ควรเปิดสาธารณะต้องไม่ถูกอัปโหลดมาที่นี่** — ถ้าภายหลังมีไฟล์
ประเภทนั้น ต้องเพิ่มหมวดใหม่ที่ตรวจสิทธิ์ก่อนอ่าน ไม่ใช่เปลี่ยนพฤติกรรมของหมวดเดิม
"""
import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.api.deps import bearer_scheme, get_current_user, require_staff
from app.core.config import get_settings
from app.db.session import get_db
from app.models.user import User
from app.services import file_store
from app.services.auth_service import can_access_admin

router = APIRouter(prefix="/uploads", tags=["uploads"])
logger = logging.getLogger("course_advisor")


def _require_staff_token(credentials: HTTPAuthorizationCredentials | None,
                         db: Session) -> None:
    """
    ตรวจสิทธิ์ของการเปิดไฟล์หมวดที่ไม่เปิดสาธารณะ

    เรียก get_current_user เองแทนการใช้เป็น Depends เพราะเส้นทางนี้ต้องเปิดสาธารณะ
    สำหรับบางหมวด การผูกด่านไว้กับเส้นทางทั้งเส้นจะทำให้รูปบนหน้าเว็บแสดงไม่ได้
    """
    try:
        user = get_current_user(credentials, db)
    except HTTPException:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "ต้องเข้าสู่ระบบก่อน") from None
    if not can_access_admin(user.role, user.status):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "ต้องเป็นผู้ดูแลที่ได้รับอนุมัติแล้ว")


@router.post("/{category}", status_code=status.HTTP_201_CREATED)
async def upload(category: str, file: UploadFile = File(...),
                 _staff: User = Depends(require_staff)) -> dict:
    """
    รับไฟล์หนึ่งไฟล์ คืนพาธที่ต้องเก็บลงฐานข้อมูล

    อ่านทั้งไฟล์เข้าหน่วยความจำได้เพราะเพดานอยู่ที่ไม่กี่เมกะไบต์ (UPLOAD_MAX_BYTES)
    และ FastAPI เองก็เขียนไฟล์ใหญ่ลงดิสก์ชั่วคราวให้อยู่แล้ว
    """
    if category not in file_store.CATEGORIES:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "หมวดไฟล์ไม่ถูกต้อง")

    data = await file.read()
    try:
        stored = file_store.save(category, file.filename or "", data)
    except file_store.StorageNotConfigured:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "ระบบยังไม่ได้ตั้งค่าที่เก็บไฟล์") from None
    except file_store.FileRejected as exc:
        # ข้อความจาก FileRejected เขียนไว้ให้ผู้ใช้อ่านรู้เรื่องและไม่มีรายละเอียดภายใน
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from None

    return {
        "file_path": stored.relative_path,
        "file_name": stored.original_name,
        "file_size": stored.size,
        "url": f"/api/uploads/{stored.relative_path}",
    }


@router.get("/{relative_path:path}")
def download(relative_path: str,
             credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
             db: Session = Depends(get_db)) -> FileResponse:
    """
    เปิดไฟล์

    โลโก้หลักสูตรและรูปข่าวเปิดสาธารณะ เพราะแสดงบนหน้าเว็บที่ใครก็เข้าได้ และของเดิม
    ที่ Supabase ก็เป็น public bucket เหมือนกัน

    **ไฟล์คลังความรู้ต้องเข้าสู่ระบบก่อน** เพราะของเดิมเป็น bucket แบบ private ที่ใช้
    signed URL — เปิดเป็นสาธารณะตอนย้ายคือการลดความปลอดภัยโดยไม่ได้ตั้งใจ
    """
    if file_store.is_private(relative_path):
        _require_staff_token(credentials, db)

    try:
        path, media_type = file_store.open_stored(relative_path)
    except file_store.StorageNotConfigured:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "ระบบยังไม่ได้ตั้งค่าที่เก็บไฟล์") from None
    except (file_store.FileRejected, FileNotFoundError):
        # พาธผิดรูปกับหาไฟล์ไม่เจอ ตอบเหมือนกัน — ไม่บอกว่าไฟล์ไหนมีอยู่จริง
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบไฟล์นี้") from None

    settings = get_settings()
    return FileResponse(
        path,
        media_type=media_type,
        # inline เพราะส่วนใหญ่เป็นรูปที่แสดงบนหน้าเว็บ
        headers={"Cache-Control": f"public, max-age={60 * 60 * 24 * 30}"
                 if settings.uploads_dir else "no-store"},
    )
