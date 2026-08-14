import uuid

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
    in_scope: bool
    citations: list[ChatCitation]
