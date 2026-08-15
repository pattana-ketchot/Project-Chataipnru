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
from app.services.course_scope import resolve_scope
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
    SCOPE_CHECK_SYSTEM_PROMPT,
    build_chat_prompt,
    build_condense_prompt,
    build_grounding_check_prompt,
    build_scope_check_prompt,
)

# เกณฑ์คัดกรองชั้นแรก — ใช้ตัดเฉพาะคำถามที่ "ไม่มีอะไรในคลังใกล้เคียงเลย"
#
# เดิมใช้เกณฑ์เดียวที่ 0.58 ตัดสินว่าอยู่นอกขอบเขตหรือไม่ ซึ่งผิดหลักการ เพราะ
# คะแนนความใกล้เคียงตอบได้แค่ว่า "คลังมีข้อความคล้ายคำถามนี้ไหม" ไม่ใช่ "คำถามนี้
# เกี่ยวกับมหาวิทยาลัยไหม" — คนละเรื่องกัน คำถามที่เกี่ยวกับหลักสูตรจริงแต่เอกสาร
# ไม่ครอบคลุม (เช่น อัตราการได้งานของบัณฑิต) จึงได้คะแนนกลางๆ แล้วถูกเหมาว่า
# นอกเรื่อง ทั้งที่ควรตอบว่า "ไม่มีข้อมูลนี้ในเอกสาร"
#
# วัดจากชุดประเมิน 14 คำถาม:
#   ตอบได้จากเอกสาร      0.708 - 0.771
#   ในเรื่องแต่ไม่มีข้อมูล  0.539 - 0.634
#   นอกเรื่อง             0.441 - 0.517
# ช่องว่างระหว่างสองกลุ่มหลังกว้างเพียง 0.022 ซึ่งแคบเกินกว่าจะวางเกณฑ์ให้เชื่อถือ
# ได้จากตัวอย่างเท่านี้ จึงลดบทบาทของตัวเลขลงเหลือแค่ทางลัดสำหรับกรณีที่ชัดเจนมาก
# แล้วให้ _gate() เป็นคนตัดสินจริงในช่วงที่ก้ำกึ่ง
OFF_TOPIC_THRESHOLD = 0.50

# ขอบบนของช่วงที่คะแนนแยกไม่ออกว่านอกเรื่องหรือแค่เอกสารไม่ครอบคลุม
# เหนือค่านี้ถือว่าอยู่ในเรื่องแน่นอน (คำถามที่ตอบได้จริงทั้งหมดในชุดประเมินได้
# 0.708 ขึ้นไป) จึงข้ามการตรวจหัวข้อไปตรวจแค่ว่าเอกสารตอบได้ไหม
AMBIGUOUS_UNTIL = 0.65

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


def _retrieve(db: Session, connector, question: str):
    """
    ค้นเนื้อหาที่เกี่ยวข้อง โดยจำกัดขอบเขตไว้ที่หลักสูตรเดียวถ้าระบุได้จากคำถาม

    เมื่อรู้แล้วว่าถามถึงหลักสูตรใด ชื่อหลักสูตรในคำถามกลายเป็นตัวรบกวนการจัดอันดับ
    เพราะไปแมตช์กับทุก chunk ที่เอ่ยชื่อนั้น (รวมภาคผนวกที่เป็นตารางประเมิน ซึ่งพูดชื่อ
    หลักสูตรซ้ำแทบทุกบรรทัด) จึงตัดชื่อออกแล้วค้นด้วยส่วนที่เป็นคำถามจริง

    วัดกับคำถาม "สาขาวิชาเทคโนโลยีการจัดการสุขภาพ เรียนจบทำอาชีพไหนได้บ้าง":
    chunk ที่มีรายชื่ออาชีพจริงเคยอยู่อันดับแย่กว่า 200 ของทั้งคลัง เมื่อจำกัดขอบเขต
    และตัดชื่อออกแล้วขึ้นมาอยู่อันดับ 3
    """
    scope = resolve_scope(db, question)
    if scope is None:
        return search_similar_chunks(db, connector.embed(expand_query(question)), top_k=TOP_K_CHUNKS)
    return search_similar_chunks(
        db,
        connector.embed(scope.search_text),
        top_k=TOP_K_CHUNKS,
        course_ids=scope.course_ids,
    )


def _ask_json_flag(connector, system: str, user: str, key: str) -> bool:
    """
    ถามคำถามปิดหนึ่งข้อแล้วอ่านค่า boolean จาก JSON

    fail-open: ถ้าเรียกไม่สำเร็จหรืออ่านค่าไม่ได้ให้ถือว่า true เพราะการปิดกั้น
    คำถามที่ตอบได้จริงทำให้ระบบดูใช้งานไม่ได้ ซึ่งเสียหายกว่าการปล่อยผ่านแล้วให้
    ชั้นถัดไปช่วยคุมต่อ
    """
    try:
        raw = connector.chat(
            [LLMMessage(role="system", content=system), LLMMessage(role="user", content=user)],
            temperature=0.0,
            json_mode=True,
        )
        return bool(json.loads(raw).get(key, True))
    except (LLMConnectionError, json.JSONDecodeError, AttributeError, TypeError):
        return True


def _is_about_scope(connector, question: str) -> bool:
    """คำถามนี้เป็นเรื่องของมหาวิทยาลัยหรือไม่ (ไม่เกี่ยวกับว่าเอกสารมีคำตอบไหม)"""
    return _ask_json_flag(
        connector, SCOPE_CHECK_SYSTEM_PROMPT, build_scope_check_prompt(question), "about_scope"
    )


def _can_answer_from(connector, chunks, question: str) -> bool:
    """เนื้อหาที่ค้นเจอมีข้อเท็จจริงตอบคำถามนี้ได้จริงไหม"""
    return _ask_json_flag(
        connector,
        GROUNDING_CHECK_SYSTEM_PROMPT,
        build_grounding_check_prompt(_format_chunks(chunks), question),
        "can_answer",
    )


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
    # ใช้ข้อความดิบก่อน เพราะเป็นสิ่งที่ผู้ใช้พิมพ์จริงและเป็นฐานที่ใช้สอบเทียบ
    # OFF_TOPIC_THRESHOLD ไว้
    chunks = _retrieve(db, connector, message)
    best_score = chunks[0].score if chunks else 0.0
    search_query = message

    # --- 2. ถ้ามีประวัติ ลองเขียนคำถามใหม่แล้วค้นซ้ำ ---
    # คำถามต่อเนื่องอย่าง "แล้วกี่หน่วยกิต" คะแนนดิบจะต่ำเพราะขาดบริบท จึงให้
    # คะแนนที่ดีกว่าระหว่างสองแบบเป็นตัวตัดสิน คำถามนอกเรื่องจะได้คะแนนต่ำทั้งคู่
    if history:
        rewritten = _condense(connector, history, message)
        if rewritten != message:
            alt = _retrieve(db, connector, rewritten)
            alt_score = alt[0].score if alt else 0.0
            if alt_score > best_score:
                chunks, best_score, search_query = alt, alt_score, rewritten

    # --- 3. ตัดสินว่าจะตอบ ปฏิเสธ หรือบอกว่าไม่มีข้อมูล ---
    citations: list[ChatCitation] = []
    status: str
    if best_score < OFF_TOPIC_THRESHOLD:
        # ต่ำขนาดนี้คือไม่มีอะไรในคลังใกล้เคียงเลย ตัดจบโดยไม่ต้องเสียเวลาเรียก LLM
        reply_text, status = OUT_OF_SCOPE_REPLY, "out_of_scope"
    # ช่วงก้ำกึ่ง: คะแนนแยกไม่ออกว่า "นอกเรื่อง" หรือ "ในเรื่องแต่เอกสารไม่ครอบคลุม"
    # จึงถามเรื่องหัวข้อเพิ่มอีกหนึ่งคำถาม เฉพาะในช่วงนี้เท่านั้น เพื่อไม่ให้คำถาม
    # ที่คะแนนสูงอยู่แล้ว (ซึ่งอยู่ในเรื่องแน่นอน) ต้องเสียเวลาเรียก LLM เพิ่ม
    elif best_score < AMBIGUOUS_UNTIL and not _is_about_scope(connector, search_query):
        reply_text, status = OUT_OF_SCOPE_REPLY, "out_of_scope"
    elif not _can_answer_from(connector, chunks, search_query):
        reply_text, status = NOT_FOUND_REPLY, "not_found"
    else:
        status = "answered"
    if status == "answered":
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
        in_scope=status in ("answered", "not_found"),
        citations=citations,
    )
