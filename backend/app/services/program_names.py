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
_FACTS_FILE = Path(__file__).resolve().parent.parent / "data" / "program_facts.json"


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


@lru_cache(maxsize=1)
def _facts() -> dict[str, dict]:
    raw = json.loads(_FACTS_FILE.read_text(encoding="utf-8"))["programs"]
    return {normalise_title(k): v for k, v in raw.items()}


def program_facts(course_title: str) -> dict:
    """
    ข้อมูลสรุปของหลักสูตรสำหรับหน้ารายละเอียด — ประกอบจากสามแหล่งที่ตรวจแล้ว

    ทุกค่ามีที่มาชัดเจน ไม่มีค่าไหนที่โมเดลเป็นคนคิด:
        หน่วยกิต ภาษาที่ใช้   เอกสาร มคอ.2 (data/program_facts.json)
        ชื่อปริญญาอังกฤษ      เอกสาร มคอ.2 (data/program_names_en.json)
        ค่าเทอม รูปแบบการเรียน ประกาศของคณะ (data/tuition.json)

    ไม่คำนวณ "ค่าใช้จ่ายตลอดหลักสูตร" ให้ แม้หน้าเว็บจะมีช่องนั้น เพราะต้องเดาว่า
    เรียนกี่ภาคการศึกษาและไม่มีเอกสารฉบับใดระบุยอดรวมไว้ การคูณค่าเทอมด้วยแปดแล้ว
    แสดงเป็นตัวเลขทางการคือการสร้างข้อมูลขึ้นเอง
    """
    from app.services.tuition import describe, fee_for

    facts = _facts().get(normalise_title(course_title))
    if facts is None:
        return {}

    out: dict[str, object] = {
        "level": "ปริญญาตรี",
        "duration": "4 ปี",
        "credits": f"{facts['credits']} หน่วยกิต",
        "language": facts["language"],
    }
    if (en := english_name(course_title)) is not None:
        out["degree_en"] = en

    fee = fee_for(course_title)
    if fee is not None:
        out["degree"] = fee["degree"]
        out["tuition_per_semester"] = f"{fee['regular']:,} บาท"
        out["study_format"] = describe(fee)
    return out
