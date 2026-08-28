"""
รูปแบบข้อมูลของ /match — จับคู่นักเรียนกับสาขาจากคำตอบแบบสอบถาม

ทุกช่องเป็นตัวเลือกทั้งหมดโดยตั้งใจ เพราะหน้าเว็บให้ผู้ใช้ทำแบบสอบถามทีละขั้นและ
ข้ามข้อได้ ถ้าบังคับให้ครบทุกช่องจะเรียกดูผลระหว่างทางไม่ได้เลย ระบบต้องการเพียง
มีคำตอบสักข้อหนึ่งจึงจะจัดอันดับได้
"""
import uuid

from pydantic import BaseModel, Field


class MatchRequest(BaseModel):
    # ชื่อช่องตรงกับขั้นตอนในแบบสอบถามของหน้าเว็บ เพื่อให้ฝั่งหน้าเว็บส่งมาได้ตรงๆ
    study_track: str | None = Field(default=None, max_length=64)          # ขั้น 1 สายการเรียน
    favorite_subjects: list[str] = Field(default_factory=list)            # ขั้น 1 วิชาที่ชอบ
    interests: list[str] = Field(default_factory=list)                    # ขั้น 2 ความสนใจ
    aptitudes: list[str] = Field(default_factory=list)                    # ขั้น 3 ความถนัด
    career_goal: list[str] = Field(default_factory=list)                  # ขั้น 4 เป้าหมายอาชีพ
    work_environment: list[str] = Field(default_factory=list)             # ขั้น 4 สภาพแวดล้อมการทำงาน
    extra: str | None = Field(default=None, max_length=1000)              # ข้อความอิสระเพิ่มเติม
    limit: int = Field(default=5, ge=1, le=10)


class ProgramMatchOut(BaseModel):
    course_id: uuid.UUID
    title: str
    # ความใกล้เคียงดิบระหว่างเวกเตอร์โปรไฟล์กับเนื้อหาหลักสูตร เก็บไว้ให้ตรวจสอบย้อนหลังได้
    score: float
    # ค่าเดียวกันแปลงเป็นเปอร์เซ็นต์เพื่อแสดงผล (ดูสูตรใน services/program_match.py)
    match_percent: int
    rationale: str
    evidence_chunk_ids: list[uuid.UUID]


class MatchResponse(BaseModel):
    profile_text: str          # ข้อความที่ใช้แปลงเป็นเวกเตอร์จริง — เปิดให้ตรวจสอบได้ว่าระบบเข้าใจว่าอย่างไร
    model_used: str
    # "high"  = อันดับ 1 ทิ้งห่างชัดเจน แสดงเป็นคำตอบหลักได้
    # "low"   = ผลลัพธ์เกาะกลุ่มกัน ควรชวนผู้ใช้ดูหลายตัวเลือกแทนการชูอันดับ 1
    #           (ดูที่มาของเกณฑ์ใน services/program_match.py -> confidence_of)
    confidence: str
    matches: list[ProgramMatchOut]
