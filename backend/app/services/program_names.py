"""
ชื่อภาษาอังกฤษของหลักสูตร — กำหนดไว้ตายตัว ไม่ให้โมเดลหยิบเอง

ทำไมไม่ปล่อยให้โมเดลอ่านจากเอกสารที่ค้นเจอ
------------------------------------------
เอกสาร มคอ.2 เล่มหนึ่งเอ่ยชื่อภาษาอังกฤษของหลักสูตรอื่นด้วยเสมอ ทั้งในตารางเปรียบเทียบ
กับหลักสูตรฉบับเดิมและในรายชื่อหลักสูตรที่เกี่ยวข้อง โมเดลจึงหยิบผิดเล่มได้ง่าย

ตัวอย่างจริงจากคลัง: เอกสารคหกรรมศาสตร์มีทั้งสองชื่อนี้อยู่
    Bachelor of Arts Program in Home Economics      ← ถูก (หลักสูตรศิลปศาสตรบัณฑิต)
    Bachelor of Science Program in Home Economics   ← ไม่ใช่ปริญญาที่หลักสูตรนี้ให้

ตอนดึงชื่อออกมาทำตารางนี้ วิธีเลือก "ชื่อที่ยาวที่สุด" ก็หยิบผิดเป็นอันหลัง จึงต้องมี
คนตรวจแล้วกำหนดไว้ทีละหลักสูตร เหมือนที่ทำกับตารางค่าเทอม
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.services.tuition import _normalise as normalise_title

_DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "program_names_en.json"


@lru_cache(maxsize=1)
def _table() -> dict[str, str]:
    raw = json.loads(_DATA_FILE.read_text(encoding="utf-8"))["programs"]
    return {normalise_title(k): v for k, v in raw.items()}


def english_name(course_title: str) -> str | None:
    """
    ชื่อภาษาอังกฤษของหลักสูตรนี้ คืน None ถ้าไม่มีในตาราง

    เทียบด้วยชื่อที่ตัดคำนำหน้าและปีออกแล้ว ฉบับเดิมกับฉบับปรับปรุงของหลักสูตรเดียวกัน
    จึงได้ชื่อภาษาอังกฤษเดียวกัน ซึ่งตรงกับความจริง — การปรับปรุงหลักสูตรไม่ได้เปลี่ยน
    ชื่อภาษาอังกฤษในกรณีของคณะนี้
    """
    return _table().get(normalise_title(course_title))
