"""
GET /documents/{document_id}/pdf — เปิดเอกสาร มคอ.2 ต้นฉบับที่ระบบใช้สกัดข้อมูล

ทำไมอ้างด้วย document_id ไม่ใช่ชื่อไฟล์
--------------------------------------
ผู้ใช้ส่งมาได้เพียงรหัสของเอกสารซึ่งเป็น UUID ถ้ารับชื่อไฟล์หรือ path จะเปิดช่องให้
เดินออกนอกโฟลเดอร์ที่อนุญาต (path traversal) ที่นี่จึงไม่มีการประกอบ path จากสิ่งที่
ผู้ใช้ส่งมาเลยแม้แต่จุดเดียว path ทั้งหมดมาจากดัชนีที่ระบบสแกนไว้เอง

และ document_id คือสิ่งที่ข้อมูลหลักสูตรอ้างถึงอยู่แล้ว (mko.v_live_values.document_id)
บรรทัด "ที่มา: ma69.pdf หน้า 1" จึงลิงก์มาที่นี่ได้ในอนาคตโดยไม่ต้องแก้ตรรกะใด

ทำไม 404 กับทุกกรณีที่เปิดไม่ได้
-------------------------------
ไม่มีเอกสารนี้ · ไฟล์ไม่อยู่ในที่เก็บ · ลายนิ้วมือไม่ตรง · ยังไม่ได้เปิดใช้ฟีเจอร์ —
ทั้งหมดตอบ 404 ข้อความเดียวกัน เพื่อไม่บอกผู้ถามว่าระบบมีอะไรอยู่บ้างหรือเก็บไว้ที่ไหน
รายละเอียดจริงอยู่ใน log ฝั่งเซิร์ฟเวอร์เท่านั้น
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import web_rate_limiter
from app.db.session import get_db
from app.services.document_store import get_document_store

router = APIRouter(prefix="/documents", tags=["documents"])

NOT_FOUND = "ไม่พบเอกสารที่ขอ"


@router.get("/{document_id}/pdf", dependencies=[Depends(web_rate_limiter)])
def document_pdf(document_id: uuid.UUID, db: Session = Depends(get_db)) -> FileResponse:
    row = db.execute(
        text("SELECT original_filename, file_sha256 FROM course_documents WHERE id = :id"),
        {"id": document_id},
    ).mappings().first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)

    stored = get_document_store().open(document_id, row["original_filename"], row["file_sha256"])
    if stored is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)

    # inline เพื่อให้เบราว์เซอร์เปิดด้วยตัวอ่าน PDF ของตัวเอง ซึ่งทำให้ลิงก์แบบ #page=6
    # กระโดดไปหน้าที่อ้างถึงได้ ถ้าใช้ attachment เบราว์เซอร์จะดาวน์โหลดแล้วจบ
    #
    # FileResponse ของ Starlette ตอบ accept-ranges และรองรับ Range เองอยู่แล้ว
    # ตัวอ่าน PDF จึงขอเฉพาะช่วงไบต์ที่ต้องใช้ได้ ไม่ต้องรอทั้งเล่ม
    return FileResponse(
        stored.path,
        media_type=stored.media_type,
        filename=stored.filename,
        content_disposition_type="inline",
    )
