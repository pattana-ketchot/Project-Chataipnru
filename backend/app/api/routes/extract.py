"""
แตกข้อความจากไฟล์ที่ผู้ดูแลอัปโหลด — Phase 4 (มาแทน webapi/api/admin/extract-file)

    POST /extract-file   รับไฟล์หนึ่งไฟล์ คืนข้อความข้างใน

ใช้เติมช่องเนื้อหาในฟอร์มคลังความรู้ ไม่ได้บันทึกอะไรลงฐานข้อมูลและไม่เก็บไฟล์ไว้
รองรับ .pdf .docx .txt .md เหมือนของเดิมทุกประการ

ไฟล์ถูกอ่านในหน่วยความจำแล้วทิ้ง ไม่เขียนลงดิสก์ จึงไม่มีเรื่อง path ให้กังวล
"""
import io
import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.api.deps import require_staff
from app.core.config import get_settings
from app.models.user import User
from app.services.file_store import extension_of

router = APIRouter(tags=["extract"])
logger = logging.getLogger("course_advisor")

SUPPORTED = (".pdf", ".docx", ".txt", ".md")


def _from_pdf(data: bytes) -> str:
    import pymupdf

    with pymupdf.open(stream=data, filetype="pdf") as document:
        return "\n".join(page.get_text() for page in document)


def _from_docx(data: bytes) -> str:
    import docx

    document = docx.Document(io.BytesIO(data))
    return "\n".join(p.text for p in document.paragraphs)


def _from_text(data: bytes) -> str:
    # ไฟล์ที่ทีมส่งมาเป็น UTF-8 เสมอในทางปฏิบัติ แต่ถ้าไม่ใช่ก็ต้องไม่ล้มทั้งคำขอ
    return data.decode("utf-8", "replace")


@router.post("/extract-file")
async def extract_file(file: UploadFile = File(...),
                       _staff: User = Depends(require_staff)) -> dict:
    extension = extension_of(file.filename or "")
    if extension not in SUPPORTED:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            f"รองรับเฉพาะไฟล์ {', '.join(SUPPORTED)}")

    data = await file.read()
    limit = get_settings().upload_max_bytes
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "ไฟล์ว่าง")
    if len(data) > limit:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            f"ไฟล์ใหญ่เกิน {limit // (1024 * 1024)} MB")

    try:
        if extension == ".pdf":
            text = _from_pdf(data)
        elif extension == ".docx":
            text = _from_docx(data)
        else:
            text = _from_text(data)
    except Exception:  # noqa: BLE001
        # ไม่ส่งรายละเอียดภายในกลับไป — ไฟล์เสียกับไฟล์ที่เข้ารหัสไว้ให้ข้อความต่างกัน
        # ซึ่งบอกเรื่องภายในระบบโดยไม่จำเป็น
        logger.exception("แตกข้อความจากไฟล์ไม่สำเร็จ (%s)", extension)
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "อ่านไฟล์นี้ไม่สำเร็จ อาจเสียหายหรือถูกใส่รหัสไว้") from None

    return {"text": text.strip(), "chars": len(text.strip())}
