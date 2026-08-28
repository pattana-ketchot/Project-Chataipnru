"""
เปรียบเทียบหลักสูตร 2-4 สาขาแบบอ้างอิงเอกสาร (/compare)

ทำไมไม่ใช้วิธีถามโมเดลตรงๆ ว่า "สองสาขานี้ต่างกันยังไง"
------------------------------------------------------
โมเดลรู้จักชื่อสาขาอย่าง "วิทยาการคอมพิวเตอร์" กับ "เทคโนโลยีสารสนเทศ" อยู่แล้วจาก
ความรู้ทั่วไป ถ้าถามลอยๆ มันจะตอบด้วยความแตกต่างของสองสาขานี้ "โดยทั่วไป" ซึ่งฟังดู
น่าเชื่อถือมากแต่ไม่ได้มาจากหลักสูตรของคณะนี้เลย ผู้อ่านแยกไม่ออกว่าส่วนไหนจริง

จึงบังคับให้ทุกช่องในตารางมาจากเอกสาร มคอ.2 ของเล่มนั้นๆ เท่านั้น โดยค้นเนื้อหาที่
เกี่ยวข้องของแต่ละหลักสูตรมาก่อน แล้วให้โมเดลทำหน้าที่ "สรุปสิ่งที่อ่านเจอ" ไม่ใช่
"ตอบจากที่รู้" — วิธีเดียวกับที่ใช้ใน services/chat.py ซึ่งวัดแล้วว่ากันการแต่งข้อมูลได้

ช่องที่เอกสารไม่มีข้อมูลจะขึ้นว่าไม่พบ ไม่เดาให้ เพราะตารางเปรียบเทียบที่มีข้อมูลผิด
ปนอยู่อันตรายกว่าตารางที่มีช่องว่าง — ผู้ใช้กำลังใช้มันตัดสินใจเลือกที่เรียน

ข้อจำกัดที่ทราบ
--------------
หัวข้อ "คุณสมบัติผู้เข้าศึกษา" ยังค้นพลาดในบางเล่ม บางเล่มขึ้นว่าไม่พบทั้งที่มีข้อมูล
และบางเล่มได้ระเบียบวินัย (ไม่เคยรับโทษจำคุก) ปนมากับวุฒิที่รับเข้า เพราะสองเรื่องนี้
อยู่ในหัวข้อเดียวกันของเอกสารและใช้ถ้อยคำใกล้เคียงกัน

อีกสามหัวข้อ (หน่วยกิต รายวิชาของสาขา อาชีพหลังจบ) ตรวจแล้วถูกต้อง จึงยังใช้งานได้
ทางแก้ที่ถูกต้องคือทำชุดทดสอบสำหรับหัวข้อนี้โดยเฉพาะก่อน แล้วจึงปรับ ไม่ใช่ไล่แก้
จากการดูผลไม่กี่ครั้งซึ่งแยกไม่ออกว่าดีขึ้นจริงหรือบังเอิญ
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.course import Course
from app.services.llm_client import get_llm_connector
from app.services.vector_search import search_similar_chunks

from llm.connector import ChatMessage as LLMMessage, LLMConnectionError  # noqa: E402
from llm.prompts import COMPARE_SYSTEM_PROMPT, build_compare_prompt  # noqa: E402

# หัวข้อที่นำมาเทียบ พร้อมข้อความที่ใช้ค้นเนื้อหาของหัวข้อนั้นในแต่ละเล่ม
#
# เลือกสี่หัวข้อนี้เพราะเป็นสิ่งที่นักเรียนใช้ตัดสินใจจริง และตรวจแล้วว่าเอกสาร มคอ.2
# มีข้อมูลครบแทบทุกเล่ม ต่างจากค่าเทอมหรือสถานที่เรียนซึ่งเอกสารส่วนใหญ่ไม่ได้ระบุ
#
# ข้อความค้นต้องเขียนด้วย "ถ้อยคำที่ปรากฏจริงในเอกสาร" ไม่ใช่ภาษาที่คนทั่วไปใช้ถาม
# เพราะการค้นเทียบความใกล้เคียงของข้อความ ไม่ได้เข้าใจเจตนา รอบแรกที่เขียนตามภาษา
# คนทั่วไปได้ผลผิดทั้งสามหัวข้อ:
#   "รายวิชาเฉพาะด้านที่ต้องเรียน"      -> ได้วิชาภาษาไทยและภาษาอังกฤษของหมวดศึกษาทั่วไป
#   "คุณสมบัติของผู้เข้าศึกษา"           -> ได้ระเบียบวินัย เช่น ไม่เคยรับโทษจำคุก
#   "จำนวนหน่วยกิตรวมตลอดหลักสูตร"      -> ไม่เจอหน้าที่มีตัวเลขจริง
DIMENSIONS: list[tuple[str, str]] = [
    ("จำนวนหน่วยกิต",
     "จำนวนหน่วยกิตรวมตลอดหลักสูตร ไม่น้อยกว่า หน่วยกิต โครงสร้างหลักสูตร หมวดวิชาศึกษาทั่วไป หมวดวิชาเฉพาะ หมวดวิชาเลือกเสรี"),
    ("เรียนอะไรบ้าง",
     "หมวดวิชาเฉพาะ กลุ่มวิชาเฉพาะด้าน กลุ่มวิชาแกน รายวิชาบังคับของสาขาวิชา"),
    ("จบแล้วทำงานอะไร",
     "อาชีพที่สามารถประกอบได้หลังสำเร็จการศึกษา แนวทางการประกอบอาชีพของบัณฑิต"),
    ("คุณสมบัติผู้เข้าศึกษา",
     "สำเร็จการศึกษาระดับมัธยมศึกษาตอนปลายหรือเทียบเท่า คุณสมบัติของผู้เข้าศึกษาและการคัดเลือกผู้เข้าศึกษา"),
]

MIN_PROGRAMS, MAX_PROGRAMS = 2, 4

# จำนวนเนื้อหาที่ดึงมาต่อหนึ่งหัวข้อต่อหนึ่งหลักสูตร
#
# เริ่มที่ 2 แล้วขยับเป็น 4 เพราะตารางรายวิชาและโครงสร้างหลักสูตรใน มคอ.2 ยาวข้ามหน้า
# เนื้อหาที่ต้องอ่านคู่กันจึงถูกตัดเป็นคนละชิ้น — อาการเดียวกับที่เจอในการค้นตอบคำถาม
# มากกว่านี้ไม่คุ้มเพราะ 4 หลักสูตร x 4 หัวข้อ คูณกันเร็วมากจนพรอมต์ยาวเกินจำเป็น
CHUNKS_PER_DIMENSION = 4
CHUNK_CHARS = 700


@dataclass
class ComparedProgram:
    course_id: uuid.UUID
    title: str


def compare_programs(db: Session, course_ids: list[uuid.UUID]) -> dict:
    if not MIN_PROGRAMS <= len(course_ids) <= MAX_PROGRAMS:
        raise ValueError(f"เลือกได้ครั้งละ {MIN_PROGRAMS}-{MAX_PROGRAMS} สาขา")

    courses = db.scalars(select(Course).where(Course.id.in_(course_ids))).all()
    found = {c.id: c for c in courses}
    missing = [str(cid) for cid in course_ids if cid not in found]
    if missing:
        raise ValueError(f"ไม่พบหลักสูตร: {', '.join(missing)}")

    # เรียงตามลำดับที่ผู้ใช้เลือกมา ไม่ใช่ลำดับที่ฐานข้อมูลคืน เพื่อให้คอลัมน์ในตาราง
    # ตรงกับลำดับการ์ดที่ผู้ใช้กดเลือกบนหน้าเว็บ
    ordered = [found[cid] for cid in course_ids]

    connector = get_llm_connector()

    # แปลงข้อความค้นหาของแต่ละหัวข้อเป็นเวกเตอร์เพียงครั้งเดียว แล้วใช้ซ้ำกับทุกหลักสูตร
    # ประหยัดการเรียกโมเดลจาก (หัวข้อ x หลักสูตร) ครั้ง เหลือเท่าจำนวนหัวข้อ
    dimension_vectors = {label: connector.embed(query) for label, query in DIMENSIONS}

    evidence: list[dict] = []
    for course in ordered:
        per_dimension: dict[str, str] = {}
        for label, _ in DIMENSIONS:
            chunks = search_similar_chunks(
                db,
                dimension_vectors[label],
                top_k=CHUNKS_PER_DIMENSION,
                course_ids=[course.id],
            )
            per_dimension[label] = "\n".join(
                f"[หน้า {c.page_number}] {c.content[:CHUNK_CHARS]}" for c in chunks
            ) or "(ไม่พบเนื้อหาที่เกี่ยวข้อง)"
        evidence.append({"title": course.title, "sections": per_dimension})

    extracted = _extract(connector, evidence)

    return {
        "programs": [{"course_id": c.id, "title": c.title} for c in ordered],
        "rows": [
            {
                "dimension": label,
                "values": [
                    extracted.get(c.title, {}).get(label, "ไม่พบข้อมูลในเอกสาร")
                    for c in ordered
                ],
            }
            for label, _ in DIMENSIONS
        ],
        "summary": extracted.get("__summary__", ""),
    }


def _extract(connector, evidence: list[dict]) -> dict:
    """
    ให้โมเดลสรุปเนื้อหาที่ค้นมาลงในแต่ละช่องของตาราง คืน dict ว่างถ้าล้ม

    ถ้าขั้นนี้ล้ม ผู้ใช้จะยังได้ตารางที่มีชื่อหลักสูตรและหัวข้อครบ เพียงแต่ทุกช่องขึ้นว่า
    ไม่พบข้อมูล ซึ่งอ่านแล้วรู้ว่าระบบมีปัญหา ดีกว่าหน้าจอว่างเปล่าที่ไม่บอกอะไรเลย
    """
    try:
        raw = connector.chat(
            [
                LLMMessage(role="system", content=COMPARE_SYSTEM_PROMPT),
                LLMMessage(role="user", content=build_compare_prompt(evidence)),
            ],
            temperature=0.1,
            json_mode=True,
            num_predict=connector.answer_token_cap,
        )
        data = json.loads(raw)
    except (LLMConnectionError, json.JSONDecodeError, AttributeError, TypeError):
        return {}

    out: dict = {str(k): v for k, v in (data.get("programs") or {}).items() if isinstance(v, dict)}
    out["__summary__"] = str(data.get("summary") or "")
    return out
