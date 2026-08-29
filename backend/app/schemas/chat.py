import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    # ไม่ส่งมา = เริ่มบทสนทนาใหม่ ส่งมา = คุยต่อใน session เดิม
    session_id: uuid.UUID | None = None


class ChatCitation(BaseModel):
    chunk_id: uuid.UUID
    course_id: uuid.UUID
    course_title: str
    page_number: int | None
    score: float


class ChatReply(BaseModel):
    session_id: uuid.UUID
    reply: str
    # คำถามที่ถูกเขียนใหม่ก่อนนำไปค้นหา — เปิดเผยไว้เพื่อให้ตรวจสอบและ debug ได้
    # ว่าระบบตีความคำถามต่อเนื่องถูกหรือไม่ (มีประโยชน์มากตอนสาธิต)
    search_query: str
    top_score: float
    # แยกสามสถานะให้ชัด เพราะ "ปฏิเสธเพราะนอกเรื่อง" กับ "อยู่ในเรื่องแต่เอกสาร
    # ไม่มีคำตอบ" เป็นคนละกรณีที่ผู้ใช้ควรได้ข้อความต่างกัน และตอนวัดผลก็ต้อง
    # นับแยกกัน — ก่อนหน้านี้ใช้ in_scope ตัวเดียวจึงแยกไม่ออก
    status: Literal["answered", "not_found", "out_of_scope", "small_talk"]
    in_scope: bool  # ผ่านเกณฑ์ความใกล้เคียงหรือไม่ (not_found ก็ถือว่าผ่าน)
    citations: list[ChatCitation]


# --- ประวัติการสนทนา (แถบข้างในหน้าแชท) ---


class ChatSessionSummary(BaseModel):
    session_id: uuid.UUID
    # ย่อจากคำถามแรกของผู้ใช้ ไม่ได้เก็บในฐานข้อมูล — เหตุผลอยู่ใน services/chat_history.py
    title: str
    started_at: datetime
    # เวลาข้อความล่าสุด ใช้จัดกลุ่ม "วันนี้ / เมื่อวาน / ก่อนหน้านี้" ในแถบข้าง
    last_message_at: datetime
    message_count: int


class ChatSessionList(BaseModel):
    sessions: list[ChatSessionSummary]
    total: int
    # บอกตรงๆ ว่ายังมีของเหลือไหม หน้าเว็บจะได้ไม่ต้องคำนวณจาก total/limit/offset เอง
    has_more: bool


class ChatMessageOut(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str
    created_at: datetime


class ChatSessionDetail(BaseModel):
    session_id: uuid.UUID
    title: str
    started_at: datetime
    messages: list[ChatMessageOut]
