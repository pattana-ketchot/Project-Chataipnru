"""
สนทนาถาม-ตอบหลายเทิร์นเกี่ยวกับหลักสูตร (/chat)

ต่างจาก services/rag.py ที่ทำหน้าที่จัดอันดับหลักสูตรแบบครั้งเดียวจบและบังคับ
ผลลัพธ์เป็น JSON — ไฟล์นี้ตอบเป็นภาษาคน จำบทสนทนาได้ และตอบคำถามต่อเนื่องได้

ลำดับการทำงานต่อหนึ่งเทิร์น:
  1. โหลดประวัติของ session (และตรวจว่า session เป็นของผู้ใช้คนนี้จริง)
  2. เขียนคำถามใหม่ให้สมบูรณ์ด้วย LLM ถ้ามีประวัติอยู่แล้ว (query condensation)
  3. embed คำถามที่เขียนใหม่ -> vector search
  4. ถ้าคะแนนความใกล้เคียงสูงสุดต่ำกว่าเกณฑ์ = คำถามอยู่นอกขอบเขต
     ตอบข้อความมาตรฐานกลับไปโดยไม่เรียก LLM
  5. ถ้าผ่านเกณฑ์ ส่ง context + ประวัติ + คำถาม ให้ LLM ตอบ
  6. บันทึกทั้งข้อความผู้ใช้และคำตอบลง chat_messages
"""
import json
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chat import ChatMessage, ChatSession
from app.schemas.chat import ChatReply, ChatCitation
from app.services.llm_client import get_llm_connector
from app.services.query_expansion import expand_query
from app.services.small_talk import match_small_talk
from app.services.vector_search import search_similar_chunks

from llm.connector import ChatMessage as LLMMessage, LLMConnectionError  # noqa: E402  (sys.path ตั้งโดย llm_client)
from llm.prompts import (  # noqa: E402
    CHAT_SYSTEM_PROMPT,
    CONDENSE_SYSTEM_PROMPT,
    GROUNDING_CHECK_SYSTEM_PROMPT,
    NOT_FOUND_REPLY,
    OUT_OF_SCOPE_REPLY,
    build_chat_prompt,
    build_condense_prompt,
    build_grounding_check_prompt,
)

# เกณฑ์คะแนนความใกล้เคียง (similarity = 1 - cosine distance) ที่ถือว่าคำถาม
# อยู่ในขอบเขต วัดจากคำถามจริง 12 ข้อกับคลังเอกสาร 18 หลักสูตร:
#   คำถามเกี่ยวกับหลักสูตร  ได้ 0.625 - 0.721
#   คำถามนอกเรื่อง          ได้ 0.411 - 0.525
# ตั้งไว้ตรงกลางช่องว่างเพื่อให้มีระยะเผื่อทั้งสองฝั่ง
RELEVANCE_THRESHOLD = 0.58

# จำนวนข้อความย้อนหลังที่ส่งเข้า prompt — มากกว่านี้ทำให้ prompt ยาวและช้าขึ้น
# โดยได้บริบทเพิ่มไม่มาก เพราะคำถามมักอ้างถึงไม่กี่เทิร์นล่าสุด
HISTORY_LIMIT = 6

TOP_K_CHUNKS = 6


def _load_session(db: Session, user_id: uuid.UUID, session_id: uuid.UUID | None) -> ChatSession:
    if session_id is None:
        session = ChatSession(user_id=user_id)
        db.add(session)
        db.flush()
        return session

    session = db.get(ChatSession, session_id)
    # SECURITY: ต้องเช็คว่า session เป็นของผู้ใช้ที่เรียกมาจริง ไม่งั้นใครก็เดา
    # session_id เพื่ออ่านบทสนทนาของคนอื่นได้ — คืน 404 เหมือนกรณีไม่พบ เพื่อไม่
    # บอกผู้โจมตีว่า id นี้มีอยู่จริงแต่เป็นของคนอื่น
    if session is None or session.user_id != user_id:
        raise ValueError("ไม่พบบทสนทนานี้")
    return session


def _load_history(db: Session, session_id: uuid.UUID) -> list[ChatMessage]:
    rows = db.scalars(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(HISTORY_LIMIT)
    ).all()
    return list(reversed(rows))  # เรียงเก่า -> ใหม่ ก่อนส่งเข้า prompt


def _format_history_for_condense(history: list[ChatMessage]) -> str:
    """
    ส่งเฉพาะคำถามของผู้ใช้เข้า prompt เขียนคำถามใหม่ ไม่ส่งคำตอบของผู้ช่วย

    จากการทดสอบ: ถ้าใส่คำตอบของผู้ช่วยลงไปด้วย โมเดลจะลอกเนื้อความยาวๆ จาก
    คำตอบเก่ามาต่อกับคำถามใหม่ ทำให้ query ที่ได้ยาวผิดปกติและความหมายเพี้ยน
    """
    users = [m.content for m in history if m.role == "user"]
    return "\n".join(f"- {q}" for q in users) if users else "(ไม่มี)"


def _condense(connector, history: list[ChatMessage], message: str) -> str:
    """เขียนคำถามใหม่ให้สมบูรณ์ คืนคำถามเดิมถ้าทำไม่สำเร็จ"""
    try:
        raw = connector.chat(
            [
                LLMMessage(role="system", content=CONDENSE_SYSTEM_PROMPT),
                LLMMessage(
                    role="user",
                    content=build_condense_prompt(_format_history_for_condense(history), message),
                ),
            ],
            temperature=0.0,
            json_mode=True,
        )
        rewritten = (json.loads(raw).get("query") or "").strip()
    except (LLMConnectionError, json.JSONDecodeError, AttributeError, TypeError):
        # ขั้นตอนนี้เป็นแค่ตัวช่วย ล้มแล้วไม่ควรทำให้ทั้งเทิร์นพัง
        return message

    # กันผลลัพธ์ที่ยาวผิดปกติ ซึ่งแปลว่าโมเดลเขียนคำอธิบายหรือคำตอบมาแทนคำถาม
    if not rewritten or len(rewritten) > 200:
        return message
    return rewritten


def _format_chunks(chunks) -> str:
    return "\n\n".join(
        f'[หลักสูตร: {c.course_title} | หน้า {c.page_number}]\n{c.content}' for c in chunks
    )


def _can_answer_from(connector, chunks, question: str) -> bool:
    """
    ถามโมเดลเป็นคำถามปิดว่าเนื้อหาที่ค้นเจอตอบคำถามนี้ได้จริงไหม

    ถ้าตรวจไม่สำเร็จให้ถือว่าตอบได้ (fail-open) เพราะการปิดกั้นคำถามที่ตอบได้จริง
    ทำให้ระบบดูใช้งานไม่ได้ ซึ่งเสียหายกว่าการปล่อยผ่านบางกรณีแล้วให้ system
    prompt ชั้นถัดไปช่วยคุมต่อ
    """
    try:
        raw = connector.chat(
            [
                LLMMessage(role="system", content=GROUNDING_CHECK_SYSTEM_PROMPT),
                LLMMessage(role="user", content=build_grounding_check_prompt(_format_chunks(chunks), question)),
            ],
            temperature=0.0,
            json_mode=True,
        )
        return bool(json.loads(raw).get("can_answer", True))
    except (LLMConnectionError, json.JSONDecodeError, AttributeError, TypeError):
        return True


def answer_question(
    db: Session,
    user_id: uuid.UUID,
    session_id: uuid.UUID | None,
    message: str,
) -> ChatReply:
    connector = get_llm_connector()
    session = _load_session(db, user_id, session_id)
    history = _load_history(db, session.id)

    # --- 0. คำทักทาย/ขอบคุณ/ถามตัวตน -> ตอบทันทีโดยไม่ค้นเอกสารและไม่เรียก LLM ---
    if (canned := match_small_talk(message)) is not None:
        db.add(ChatMessage(session_id=session.id, role="user", content=message))
        db.add(ChatMessage(session_id=session.id, role="assistant", content=canned))
        db.commit()
        return ChatReply(
            session_id=session.id,
            reply=canned,
            search_query=message,
            top_score=0.0,
            status="small_talk",
            in_scope=True,
            citations=[],
        )

    # --- 1. ค้นด้วยคำถามดิบก่อนเสมอ ---
    # เกณฑ์ RELEVANCE_THRESHOLD สอบเทียบจากคำถามที่ผู้ใช้พิมพ์จริง จึงต้องวัดกับ
    # ข้อความดิบ ไม่ใช่ข้อความที่ผ่านการเขียนใหม่ (ซึ่งคะแนนจะเลื่อนไปจากที่วัดไว้)
    chunks = search_similar_chunks(db, connector.embed(expand_query(message)), top_k=TOP_K_CHUNKS)
    best_score = chunks[0].score if chunks else 0.0
    search_query = message

    # --- 2. ถ้ามีประวัติ ลองเขียนคำถามใหม่แล้วค้นซ้ำ ---
    # คำถามต่อเนื่องอย่าง "แล้วกี่หน่วยกิต" คะแนนดิบจะต่ำเพราะขาดบริบท จึงให้
    # คะแนนที่ดีกว่าระหว่างสองแบบเป็นตัวตัดสิน คำถามนอกเรื่องจะได้คะแนนต่ำทั้งคู่
    if history:
        rewritten = _condense(connector, history, message)
        if rewritten != message:
            alt = search_similar_chunks(db, connector.embed(expand_query(rewritten)), top_k=TOP_K_CHUNKS)
            alt_score = alt[0].score if alt else 0.0
            if alt_score > best_score:
                chunks, best_score, search_query = alt, alt_score, rewritten

    # --- 3. นอกขอบเขต -> ตอบเองโดยไม่เรียก LLM ---
    citations: list[ChatCitation] = []
    status: str
    if best_score < RELEVANCE_THRESHOLD:
        reply_text, status = OUT_OF_SCOPE_REPLY, "out_of_scope"
    # --- 4. อยู่ในขอบเขตแต่เอกสารไม่มีคำตอบ -> ตอบเองเช่นกัน ---
    # ตัดสินด้วยคำถามปิดก่อนเสมอ ไม่ปล่อยให้โมเดลตัดสินใจกลางคันตอนเขียนคำตอบ
    elif not _can_answer_from(connector, chunks, search_query):
        reply_text, status = NOT_FOUND_REPLY, "not_found"
    else:
        status = "answered"
        messages = [LLMMessage(role="system", content=CHAT_SYSTEM_PROMPT)]
        for m in history:
            messages.append(LLMMessage(role=m.role, content=m.content))
        messages.append(
            LLMMessage(role="user", content=build_chat_prompt(_format_chunks(chunks), message))
        )
        # temperature ต่ำเพื่อลดการแต่งเติม — งานนี้ต้องการความตรงกับเอกสาร
        # มากกว่าความหลากหลายของสำนวน
        reply_text = connector.chat(messages, temperature=0.1).strip()
        citations = [
            ChatCitation(
                chunk_id=c.chunk_id,
                course_id=c.course_id,
                course_title=c.course_title,
                page_number=c.page_number,
                score=c.score,
            )
            for c in chunks
        ]

    # --- 4. บันทึกบทสนทนา ---
    db.add(ChatMessage(session_id=session.id, role="user", content=message))
    db.add(ChatMessage(session_id=session.id, role="assistant", content=reply_text))
    db.commit()

    return ChatReply(
        session_id=session.id,
        reply=reply_text,
        search_query=search_query,
        top_score=round(best_score, 4),
        status=status,
        in_scope=best_score >= RELEVANCE_THRESHOLD,
        citations=citations,
    )
