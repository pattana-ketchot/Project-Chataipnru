"""
ประวัติการสนทนา — อ่านบทสนทนาเก่าของผู้ใช้กลับมาแสดงในแถบข้าง

ฐานข้อมูลเก็บทั้ง chat_sessions และ chat_messages มาตั้งแต่ต้นอยู่แล้ว โมดูลนี้
ไม่ได้เพิ่มตารางใหม่ แค่เปิดทางให้อ่านออกมาได้

ทำไมชื่อบทสนทนาไม่ได้เก็บไว้ในฐานข้อมูล
--------------------------------------
แถบข้างต้องมีชื่อกำกับแต่ละบทสนทนา วิธีที่ตรงที่สุดคือเพิ่มคอลัมน์ title แล้วให้
โมเดลตั้งชื่อให้ตอนจบเทิร์นแรก แต่นั่นแปลว่าต้องเรียก LLM เพิ่มอีกหนึ่งครั้งต่อ
บทสนทนา ซึ่งกินทั้งเวลาและโควตา และเพิ่มจุดที่พังได้อีกจุดหนึ่ง

ใช้คำถามแรกของผู้ใช้เป็นชื่อแทน อ่านรู้เรื่องพอกัน ("แนะนำสาขาที่เหมาะกับฉัน",
"เรียน IT ต้องเก่งคณิตไหม") ไม่ต้องแก้โครงสร้างฐานข้อมูล และไม่มีทางเพี้ยนเพราะ
เป็นข้อความที่ผู้ใช้พิมพ์เอง

ทำไมต้องตัดบทสนทนาที่ไม่มีข้อความออก
-----------------------------------
แถวใน chat_sessions ถูกสร้างทันทีที่มีคนเรียก /chat โดยยังไม่มีข้อความสักอัน ถ้า
คำขอนั้นล้มกลางทาง (โควตาหมด โมเดลไม่ตอบ ผู้ใช้ปิดหน้าจอ) จะเหลือแถวเปล่าค้างไว้
การ join แบบปกติกับ chat_messages ตัดแถวพวกนี้ทิ้งไปเองโดยไม่ต้องมีเงื่อนไขพิเศษ
ไม่งั้นแถบข้างจะเต็มไปด้วยรายการว่างที่กดแล้วไม่มีอะไร
"""
from __future__ import annotations

import re
import uuid

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models.chat import ChatMessage, ChatSession
from app.schemas.chat import ChatMessageOut, ChatSessionDetail, ChatSessionList, ChatSessionSummary

# ความยาวชื่อที่แถบข้างแสดงได้โดยไม่ล้น เผื่อไว้ให้หน้าเว็บตัดเพิ่มเองได้ถ้าจอแคบกว่านี้
TITLE_MAX_CHARS = 60

# จำนวนบทสนทนาต่อหนึ่งครั้ง แบบร่างของหน้าเว็บมีปุ่ม "ดูเพิ่มเติม" อยู่ท้ายรายการ
# จึงต้องแบ่งหน้าได้ ไม่ใช่ส่งทั้งหมดมาทีเดียว
DEFAULT_LIMIT = 20
MAX_LIMIT = 100


def _title(first_question: str | None) -> str:
    """
    ย่อคำถามแรกให้เป็นชื่อบรรทัดเดียว

    ยุบช่องว่างและตัดการขึ้นบรรทัดใหม่ทิ้ง เพราะผู้ใช้วางข้อความหลายบรรทัดมาถามได้
    ซึ่งจะทำให้แถบข้างเสียรูปถ้าเอามาแสดงตรงๆ
    """
    text = re.sub(r"\s+", " ", (first_question or "").strip())
    if not text:
        return "บทสนทนาใหม่"
    return text if len(text) <= TITLE_MAX_CHARS else text[: TITLE_MAX_CHARS - 1].rstrip() + "…"


def user_first():
    """
    ตัวช่วยเรียงลำดับ ให้คำถามมาก่อนคำตอบเมื่อเวลาเท่ากันเป๊ะ

    คำถามกับคำตอบถูกบันทึกใน transaction เดียวกัน และ now() ของ PostgreSQL คืนค่า
    เวลาที่ transaction เริ่ม ไม่ใช่เวลาที่รันคำสั่ง ทั้งสองแถวจึงได้ created_at
    เท่ากันทุกหลักทศนิยม การเรียงตามเวลาอย่างเดียวจึงไม่แน่นอน — ฐานข้อมูลคืนแถวไหน
    ก่อนก็ได้ และเคยเห็นคำตอบขึ้นก่อนคำถามในผลทดสอบ

    ใช้ร่วมกับ created_at เสมอ ไม่ใช้เดี่ยวๆ: มันแยกลำดับได้เฉพาะภายในคู่ถาม-ตอบ
    ที่เกิดพร้อมกันเท่านั้น
    """
    return case((ChatMessage.role == "user", 0), else_=1)


def _first_question_subquery():
    """
    คำถามแรกของแต่ละบทสนทนา ในรูปแบบที่ใช้ร่วมกับ GROUP BY ได้

    เขียนเป็น correlated subquery ที่อ้างถึงเฉพาะ chat_sessions.id ซึ่งเป็นคอลัมน์
    ที่ group อยู่แล้ว PostgreSQL จึงยอมให้อยู่ในรายการ select ได้
    """
    return (
        select(ChatMessage.content)
        .where(ChatMessage.session_id == ChatSession.id, ChatMessage.role == "user")
        .order_by(ChatMessage.created_at, user_first())
        .limit(1)
        .correlate(ChatSession)
        .scalar_subquery()
    )


def list_sessions(
    db: Session,
    user_id: uuid.UUID,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> ChatSessionList:
    """
    รายการบทสนทนาของผู้ใช้ เรียงจากที่คุยล่าสุดก่อน

    เรียงตามเวลาข้อความล่าสุด ไม่ใช่เวลาที่เริ่มบทสนทนา เพราะผู้ใช้ที่กลับมาคุยต่อ
    ในบทสนทนาเก่าคาดหวังว่ามันจะขึ้นมาอยู่บนสุด
    """
    limit = max(1, min(limit, MAX_LIMIT))
    offset = max(0, offset)

    rows = db.execute(
        select(
            ChatSession.id,
            ChatSession.started_at,
            func.count(ChatMessage.id).label("message_count"),
            func.max(ChatMessage.created_at).label("last_message_at"),
            _first_question_subquery().label("first_question"),
        )
        .join(ChatMessage, ChatMessage.session_id == ChatSession.id)
        .where(ChatSession.user_id == user_id)
        .group_by(ChatSession.id, ChatSession.started_at)
        .order_by(func.max(ChatMessage.created_at).desc())
        .limit(limit)
        .offset(offset)
    ).all()

    # นับยอดรวมแยกอีกครั้ง เพื่อให้หน้าเว็บรู้ว่าควรแสดงปุ่ม "ดูเพิ่มเติม" หรือไม่
    # โดยไม่ต้องยิงซ้ำแล้วดูว่าได้ของว่างกลับมา
    total = db.scalar(
        select(func.count(func.distinct(ChatSession.id)))
        .select_from(ChatSession)
        .join(ChatMessage, ChatMessage.session_id == ChatSession.id)
        .where(ChatSession.user_id == user_id)
    )

    return ChatSessionList(
        sessions=[
            ChatSessionSummary(
                session_id=r.id,
                title=_title(r.first_question),
                started_at=r.started_at,
                last_message_at=r.last_message_at,
                message_count=r.message_count,
            )
            for r in rows
        ],
        total=total or 0,
        has_more=offset + len(rows) < (total or 0),
    )


def get_session(db: Session, user_id: uuid.UUID, session_id: uuid.UUID) -> ChatSessionDetail:
    """
    ข้อความทั้งหมดในบทสนทนาหนึ่ง เรียงจากเก่าไปใหม่ตามที่หน้าจอต้องแสดง

    SECURITY: ตรวจว่าบทสนทนาเป็นของผู้เรียกจริง และคืนข้อความเดียวกับกรณีไม่พบ
    ไม่งั้นใครก็สุ่ม id เพื่อดูว่าบทสนทนานั้นมีอยู่จริงไหม แล้วอ่านของคนอื่นได้
    (เงื่อนไขเดียวกับใน chat._load_session)
    """
    session = db.get(ChatSession, session_id)
    if session is None or session.user_id != user_id:
        raise ValueError("ไม่พบบทสนทนานี้")

    rows = db.scalars(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at, user_first())
    ).all()

    first_question = next((m.content for m in rows if m.role == "user"), None)
    return ChatSessionDetail(
        session_id=session.id,
        title=_title(first_question),
        started_at=session.started_at,
        messages=[
            ChatMessageOut(role=m.role, content=m.content, created_at=m.created_at)
            for m in rows
        ],
    )
