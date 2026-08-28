"""รูปแบบข้อมูลของ /compare — ตารางเปรียบเทียบหลักสูตร 2-4 สาขา"""
import uuid

from pydantic import BaseModel, Field


class CompareRequest(BaseModel):
    # เรียงตามลำดับที่ผู้ใช้กดเลือกบนหน้าเว็บ ลำดับนี้ถูกใช้เป็นลำดับคอลัมน์ในตาราง
    course_ids: list[uuid.UUID] = Field(min_length=2, max_length=4)


class ComparedProgramOut(BaseModel):
    course_id: uuid.UUID
    title: str


class CompareRow(BaseModel):
    dimension: str
    # เรียงตรงกับลำดับใน programs เสมอ ฝั่งหน้าเว็บจึงจับคู่คอลัมน์ด้วยตำแหน่งได้เลย
    # ช่องที่เอกสารไม่มีข้อมูลจะเป็นข้อความ "ไม่พบข้อมูลในเอกสาร" ไม่ใช่ค่าว่าง
    values: list[str]


class CompareResponse(BaseModel):
    programs: list[ComparedProgramOut]
    rows: list[CompareRow]
    # สรุปความต่างเป็นภาษาคน อาจเป็นสตริงว่างถ้าโมเดลเรียกไม่สำเร็จ
    summary: str
