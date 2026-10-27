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
    # คะแนนความใกล้ของชิ้นเอกสารที่ใกล้คำถามมากสุด (1 - cosine distance)
    # **ไม่ใช่ความมั่นใจว่าคำตอบถูก** และไม่ใช่สัดส่วนข้อความที่มีหลักฐานรองรับ
    # สัดส่วนที่รองรับคำตอบอยู่ในช่อง answer_coverage ของแต่ละรายใน sources
    # คำตอบที่ไม่ได้ค้นเอกสาร (ทักทาย ตอบจากฐาน หรือปฏิเสธ) ค่านี้เป็น 0.0 เพราะไม่ได้ค้น
    top_score: float
    # แยกสามสถานะให้ชัด เพราะ "ปฏิเสธเพราะนอกเรื่อง" กับ "อยู่ในเรื่องแต่เอกสาร
    # ไม่มีคำตอบ" เป็นคนละกรณีที่ผู้ใช้ควรได้ข้อความต่างกัน และตอนวัดผลก็ต้อง
    # นับแยกกัน — ก่อนหน้านี้ใช้ in_scope ตัวเดียวจึงแยกไม่ออก
    status: Literal["answered", "not_found", "out_of_scope", "small_talk"]
    in_scope: bool  # ผ่านเกณฑ์ความใกล้เคียงหรือไม่ (not_found ก็ถือว่าผ่าน)
    citations: list[ChatCitation]
    # ที่มาของคำตอบที่มาจากฐานข้อมูลหลักสูตร (โหมด STRUCTURED_ANSWERS=on) ซึ่งไม่ได้
    # ผ่านการค้นเอกสาร จึงไม่มี citations — สองช่องนี้ไม่มีทางมีค่าพร้อมกับ citations
    #
    #   source   ฉบับเดียวที่ใช้ทำปุ่มเปิดเอกสาร (None เมื่อคำตอบครอบหลายฉบับ)
    #   sources  ครบทุกฉบับที่คำตอบอ้างถึง ใช้ตรวจความถูกต้องของแหล่งอ้างอิง
    #
    # เพิ่มเข้ามาเป็นค่าตั้งต้น ผู้เรียกเดิมที่ไม่รู้จักสองคีย์นี้ทำงานได้เหมือนเดิม
    #
    # ตั้งแต่ 14 ต.ค. 2569 คำตอบที่มาจากการค้นเอกสารก็มี sources ด้วย โดยเป็นชิ้นที่รองรับ
    # ข้อความคำตอบจริง ซึ่งเป็นชุดย่อยของ citations · สองช่องมีพร้อมกันได้สำหรับคำตอบสายนี้
    source: dict | None = None
    sources: list[dict] = Field(default_factory=list)


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
