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
import os
import uuid
from collections.abc import Iterator
from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.chat import ChatMessage, ChatSession
from app.schemas.chat import ChatReply, ChatCitation
from app.services.chat_history import user_first
from app.services.course_scope import _distinctive_name, resolve_scope
from app.services.llm_client import get_llm_connector, no_fallback_kwargs
from app.services.program_names import english_name
from app.services.query_expansion import expand_query, thai_only_query
from app.services.small_talk import match_small_talk
from app.services.tuition import answer as tuition_answer, is_tuition_question
from app.services.vector_search import search_similar_chunks

from llm.connector import ChatMessage as LLMMessage, LLMConnectionError  # noqa: E402  (sys.path ตั้งโดย llm_client)
from llm.prompts import (  # noqa: E402
    CHAT_SYSTEM_PROMPT,
    CONDENSE_SYSTEM_PROMPT,
    GROUNDING_CHECK_SYSTEM_PROMPT,
    NOT_FOUND_REPLY,
    NOT_FOUND_REPLY_EN,
    OUT_OF_SCOPE_REPLY,
    OUT_OF_SCOPE_REPLY_EN,
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

# จำนวนเอกสารที่ส่งเข้าโมเดล — ตัวกำหนดความเร็วที่แท้จริงของระบบนี้
#
# บนเซิร์ฟเวอร์ที่ไม่มีการ์ดจอ การอ่านพรอมต์เข้าโมเดลช้ากว่าการเขียนคำตอบมาก
# เมื่อคิดรวมทั้งเทิร์น เพราะพรอมต์ยาวกว่าคำตอบหลายเท่า วัดบนเครื่องจริง:
#
#   อ่านพรอมต์   40 โทเคน/วินาที   6 chunk = 3,649 โทเคน = 92 วินาที
#   เขียนคำตอบ  6.5 โทเคน/วินาที   คำตอบทั่วไป 130 โทเคน = 20 วินาที
#
# และเนื้อหาชุดนี้ถูกส่งเข้าโมเดลสองรอบต่อหนึ่งคำถาม (ตรวจว่าเอกสารตอบได้ไหม
# แล้วจึงเขียนคำตอบ) ทุก chunk ที่ตัดออกจึงประหยัดเวลาสองเท่าของตัวมันเอง
#
# เคยลดเหลือ 3 ตอนที่ยังใช้โมเดลในเครื่องเป็นตัวหลัก แล้วชุดประเมินตกจาก 109 เหลือ
# 99 ทันที ข้อที่ตกทั้งสิบข้อเป็นอาการเดียวกันหมด: ตอบว่า "ไม่พบข้อมูลในเอกสาร"
# ทั้งที่มีอยู่จริง โดยคะแนนค้นหาอยู่กลางๆ (0.55-0.71) ล้วนเป็นคำถามที่คำตอบกระจาย
# อยู่หลายหน้า เช่น รายวิชาบังคับ จำนวนหน่วยกิตรวม และอาชีพหลังจบ — เอกสารสามชิ้น
# ไม่พอให้ด่านตรวจมั่นใจว่าตอบได้
#
# กลับมาที่ 6 เมื่อย้ายไปใช้ Gemini เป็นตัวหลัก เพราะเหตุผลที่เคยลดหมดไปแล้ว:
# คอขวดคือ CPU อ่านพรอมต์ที่ 40 โทเคน/วินาที ซึ่งไม่ใช่ปัญหาของผู้ให้บริการที่อ่าน
# พรอมต์ได้ในเสี้ยววินาที
#
# แล้วขยับเป็น 8 เพราะเจอกรณีที่คำตอบหลุดขอบไปอย่างเฉียดฉิว: คำถามเรื่องวิชาบังคับ
# ของวิทยาการคอมพิวเตอร์ 2561 ต้องใช้เนื้อหาหน้า 19 (หมวดวิชาเฉพาะ 94 หน่วยกิต)
# ซึ่งได้ 0.563 ขณะที่อันดับ 6 ได้ 0.565 — ห่างกัน 0.002 ระบบจึงส่งเข้าไปแต่หน้า 20
# ที่เป็นวิชาศึกษาทั่วไป แล้วด่านตรวจปฏิเสธอย่างถูกต้องเพราะเอกสารที่ให้ไปตอบไม่ได้จริง
#
# เกิดจากธรรมชาติของเอกสาร: ตารางรายวิชายาวข้ามหน้า เนื้อหาที่ต้องอ่านคู่กันจึงถูก
# ตัดเป็นคนละชิ้นและได้คะแนนใกล้เคียงกันมาก การเผื่อช่วงให้กว้างขึ้นอีกนิดจึงคุ้มกว่า
# การไปปรับเกณฑ์ของด่านตรวจ ซึ่งเสี่ยงทำให้ระบบยอมตอบทั้งที่เอกสารไม่มีคำตอบ
#
# ตั้งค่าผ่าน .env ได้ (CHAT_TOP_K) เพื่อให้วัดผลค่าอื่นได้โดยไม่ต้อง build ใหม่ทุกครั้ง
# ค่าที่ใช้จริงต้องมาจากการวัดกับชุดประเมินเสมอ ไม่ใช่จากความรู้สึกว่ามากไว้ก่อนดีกว่า
TOP_K_CHUNKS = int(os.getenv("CHAT_TOP_K", "8"))

# เพดานความยาวคำตอบมาจาก connector ที่ใช้อยู่ (connector.answer_token_cap)
# ไม่ได้ตั้งไว้ตรงนี้ เพราะแต่ละเจ้าต้องใช้ค่าไม่เท่ากัน — โมเดลตระกูล Gemini 3
# ใช้โทเคนไปกับการคิดในใจก่อนเขียนคำตอบ และนับรวมในเพดานเดียวกัน


def _load_session(db: Session, user_id: uuid.UUID, session_id: uuid.UUID | None) -> ChatSession:
    if session_id is None:
        session = ChatSession(user_id=user_id)
        db.add(session)
        # commit ทันที ไม่ใช่แค่ flush เพราะโหมดสตรีมบันทึกข้อความด้วย session
        # ฐานข้อมูลคนละตัวกับที่สร้างแถวนี้ ถ้ายังไม่ commit แถวบทสนทนาจะยังไม่มีจริง
        # สำหรับ connection อื่น แล้วการบันทึกข้อความจะติด foreign key
        db.commit()
        db.refresh(session)
        return session

    session = db.get(ChatSession, session_id)
    # SECURITY: ต้องเช็คว่า session เป็นของผู้ใช้ที่เรียกมาจริง ไม่งั้นใครก็เดา
    # session_id เพื่ออ่านบทสนทนาของคนอื่นได้ — คืน 404 เหมือนกรณีไม่พบ เพื่อไม่
    # บอกผู้โจมตีว่า id นี้มีอยู่จริงแต่เป็นของคนอื่น
    if session is None or session.user_id != user_id:
        raise ValueError("ไม่พบบทสนทนานี้")
    return session


def _load_history(db: Session, session_id: uuid.UUID) -> list[ChatMessage]:
    """
    ดึงข้อความล่าสุดมาใส่ prompt

    เรียงย้อนหลังก่อนแล้วค่อยกลับด้าน เพราะต้องการ "ล่าสุด HISTORY_LIMIT ข้อความ"
    ไม่ใช่ข้อความแรกๆ ตัวช่วย user_first() จึงต้องกลับด้านตามไปด้วย เพื่อให้ผลที่
    กลับด้านแล้วได้คำถามมาก่อนคำตอบในคู่ที่บันทึกเวลาเดียวกัน (ดูเหตุผลใน
    chat_history.user_first)
    """
    rows = db.scalars(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc(), user_first().desc())
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
    """
    จัดเนื้อหาที่ค้นเจอให้โมเดลอ่าน พร้อมกำกับชื่อภาษาอังกฤษของหลักสูตรไว้ในหัวข้อ

    ใส่ชื่อภาษาอังกฤษจากตารางที่ตรวจแล้ว ไม่ปล่อยให้โมเดลไปหยิบจากเนื้อหาเอง เพราะ
    เอกสารเล่มหนึ่งเอ่ยชื่อภาษาอังกฤษของหลักสูตรอื่นปนอยู่ด้วย (ดู services/program_names.py)
    """
    parts = []
    for c in chunks:
        en = english_name(c.course_title)
        head = f"[หลักสูตร: {c.course_title}"
        if en:
            head += f" | ชื่อภาษาอังกฤษ: {en}"
        parts.append(f"{head} | หน้า {c.page_number}]\n{c.content}")
    return "\n\n".join(parts)


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


# ชื่อเฉพาะของหลักสูตรทุกเล่มในคลัง อ่านครั้งเดียวต่อโปรเซส
_PROGRAM_NAMES: list[str] | None = None


def _names_a_program(db: Session, question: str) -> bool:
    """
    คำถามนี้เอ่ยชื่อหลักสูตรที่มีอยู่จริงในคลังหรือไม่

    ใช้ลัดการถามโมเดลว่าคำถามอยู่ในขอบเขตไหม เพราะถ้าผู้ใช้เอ่ยชื่อหลักสูตรของคณะ
    มาตรงๆ คำถามนั้นอยู่ในขอบเขตแน่นอน ไม่มีกรณีที่ต้องตีความ

    ที่ต้องมีเพราะตัวคัดกรองที่เป็นโมเดลตัดสินผิดกับชื่อสาขาที่พ้องกับชื่อศาสตร์
    ทั่วไป วัดได้กับคำถามจริง: "สาขาสาธารณสุขศาสตร์มีวิชาบังคับอะไรบ้าง" ถูกตอบว่า
    อยู่นอกขอบเขต ทั้งที่ถามถึงหลักสูตรของคณะตรงๆ — โมเดลอ่านคำว่าสาธารณสุขเป็น
    เรื่องสุขภาพ ไม่ใช่เรื่องมหาวิทยาลัย ส่วนคำถามเดียวกันที่ขึ้นต้นด้วยคำว่า
    "หลักสูตร" กลับผ่าน ความต่างระดับนี้ไม่ควรเป็นตัวตัดสินว่าผู้ใช้จะได้คำตอบไหม

    เทียบแบบตรงตัวพอ เพราะผู้ใช้ที่ถามถึงสาขาหนึ่งมักพิมพ์ชื่อสาขานั้นตามที่เห็น
    ในหน้าเว็บ และการเดาชื่อที่พิมพ์ผิดจะทำให้ด่านนี้กว้างเกินจนไม่กรองอะไรเลย
    """
    global _PROGRAM_NAMES
    if _PROGRAM_NAMES is None:
        rows = db.execute(text("SELECT title FROM courses WHERE is_active")).all()
        # ชื่อสั้นๆ ตัดทิ้ง เพราะเสี่ยงไปตรงกับคำทั่วไปในประโยคที่ไม่ได้พูดถึงหลักสูตร
        _PROGRAM_NAMES = sorted({n for r in rows if len(n := _distinctive_name(r.title)) >= 6})
    return any(name in question for name in _PROGRAM_NAMES)


def _can_answer_from(connector, chunks, question: str) -> bool:
    """เนื้อหาที่ค้นเจอมีข้อเท็จจริงตอบคำถามนี้ได้จริงไหม"""
    return _ask_json_flag(
        connector,
        GROUNDING_CHECK_SYSTEM_PROMPT,
        build_grounding_check_prompt(_format_chunks(chunks), question),
        "can_answer",
    )


@dataclass
class Prepared:
    """
    ผลของทุกขั้นก่อนลงมือเขียนคำตอบ

    แยกออกมาเพื่อให้โหมด "รอจนจบ" กับโหมด "ทยอยส่ง" เดินตรรกะเดียวกันทั้งหมด
    ตั้งแต่การค้น การตัดสินขอบเขต ไปจนถึงการตรวจว่าเอกสารตอบได้ไหม ต่างกันแค่
    ขั้นสุดท้ายว่าจะรอข้อความทั้งก้อนหรือส่งทีละส่วน ถ้าปล่อยให้สองโหมดมีตรรกะ
    ของตัวเอง ผลประเมินกับสิ่งที่ผู้ใช้เห็นจริงจะค่อยๆ ห่างกันโดยไม่มีใครรู้
    """

    session_id: uuid.UUID
    status: str
    search_query: str
    best_score: float
    citations: list[ChatCitation]
    # ถ้าไม่ใช่ None คือได้คำตอบแล้วโดยไม่ต้องให้โมเดลเขียน (ทักทาย/นอกขอบเขต/ไม่พบข้อมูล)
    canned: str | None
    # ข้อความที่จะส่งให้โมเดลเขียนคำตอบ — ว่างเมื่อ canned ไม่ใช่ None
    messages: list[LLMMessage]
    # False = ห้ามตกไปใช้โมเดลสำรอง ดูเหตุผลใน _asks_for_a_number()
    allow_fallback: bool = True


# คำที่บ่งชี้ว่าผู้ใช้ถามหาตัวเลขเจาะจง ไม่ใช่คำอธิบายกว้างๆ
_NUMERIC_WORDS = (
    "กี่หน่วยกิต", "จำนวนหน่วยกิต", "กี่ปี", "กี่เทอม", "กี่ภาคการศึกษา",
    "กี่วิชา", "กี่รายวิชา", "กี่ชั่วโมง", "กี่คน", "เท่าไหร่", "เท่าไร",
)


def written_in_thai(text: str) -> bool:
    """
    ข้อความนี้เขียนด้วยอักษรไทยหรือไม่ ใช้เลือกภาษาของข้อความที่ตอบจากโค้ดโดยตรง

    ตรวจจากตัวอักษรไทยแม้แต่ตัวเดียว ไม่ได้นับสัดส่วน เพราะคนไทยพิมพ์คำอังกฤษปนไทย
    เป็นปกติ ("comsci ล่ะ", "เรียน AI ไหม") ซึ่งควรได้คำตอบภาษาไทย ส่วนคำถามที่เป็น
    อังกฤษล้วนจะไม่มีอักษรไทยเลยจึงแยกออกจากกันได้ชัด
    """
    return any("฀" <= ch <= "๿" for ch in text)


# คำที่บ่งชี้ว่าผู้ใช้กำลังขอ "คำแนะนำว่าควรเรียนสาขาไหน" ไม่ใช่ถามข้อเท็จจริงในเอกสาร
_RECOMMEND_WORDS = (
    "เหมาะกับ", "เหมาะสำหรับ", "แนะนำสาขา", "แนะนำหลักสูตร", "ควรเรียนสาขา",
    "ควรเลือกสาขา", "เลือกสาขาไหน", "สาขาไหนดี", "เรียนอะไรดี", "เรียนสาขาไหนดี",
    "which major", "which program", "what should i study", "recommend a major",
)


def _asks_for_a_recommendation(text: str) -> bool:
    """
    คำถามนี้ขอให้ช่วยเลือกสาขาหรือไม่

    ทำไมต้องแยกออกมา
    ---------------
    ด่านตรวจ _can_answer_from() ถามโมเดลว่า "เนื้อหาที่ค้นเจอมีข้อเท็จจริงตอบคำถามนี้
    ได้จริงไหม" ซึ่งเป็นคำถามที่ถูกต้องสำหรับคำถามเชิงข้อเท็จจริง แต่ผิดสำหรับคำถามขอ
    คำแนะนำ เพราะไม่มีเอกสารเล่มไหนเขียนว่า "หลักสูตรนี้เหมาะกับคนชอบคอมพิวเตอร์"

    ผลคือคำถามที่เป็นหัวใจของเว็บนี้ถูกปฏิเสธแบบสุ่ม วัดจากระบบจริงด้วยคำถามเดียวกัน
    หกครั้ง: ปฏิเสธ 3 ตอบได้ 3

    คำถามแบบนี้จึงส่งไปให้ระบบจับคู่สาขาแทน ซึ่งคิดคะแนนจากความใกล้เคียงระหว่างสิ่งที่
    ผู้ใช้บอกกับเนื้อหาจริงในเอกสารทุกเล่ม เป็นการคำนวณที่ทำซ้ำได้ ไม่ใช่ให้โมเดลเดา
    """
    lowered = text.lower()
    return any(w in lowered for w in _RECOMMEND_WORDS)


def _recommendation_reply(db: Session, message: str) -> str | None:
    """
    ตอบคำถามขอคำแนะนำด้วยผลจากระบบจับคู่สาขา คืน None ถ้าจัดอันดับไม่ได้

    บอกที่มาของอันดับไว้ในคำตอบเสมอ และถ้าคะแนนเกาะกลุ่มกันจนแยกไม่ออกก็บอกตรงๆ
    ไม่ชูอันดับ 1 ราวกับมั่นใจ
    """
    from app.services.program_match import confidence_of, match_programs

    try:
        matches = match_programs(db, {"extra": message}, limit=3)
    except (ValueError, LLMConnectionError):
        return None
    if not matches:
        return None

    lines = ["จากสิ่งที่คุณบอกมา สาขาที่ใกล้เคียงที่สุดในคณะคือ"]
    for i, m in enumerate(matches, 1):
        name = _distinctive_name(m.title)
        lines.append(f"{i}. {name} ({m.match_percent}%)")
        if m.rationale.strip():
            lines.append(f"   {m.rationale.strip()}")

    if confidence_of(matches) == "low":
        lines.append("")
        lines.append("คะแนนของหลายสาขาใกล้เคียงกันมาก แนะนำให้ดูทุกสาขาประกอบกัน ไม่ควรยึดอันดับ 1 อย่างเดียว")

    lines.append("")
    lines.append("อันดับนี้คำนวณจากความใกล้เคียงกับเนื้อหาในเอกสารหลักสูตรของทุกสาขา "
                 "ถามรายละเอียดของสาขาไหนต่อได้เลยครับ")
    return "\n".join(lines)


def _asks_for_a_number(text: str) -> bool:
    """
    คำถามนี้ต้องการตัวเลขที่ผิดไม่ได้หรือไม่

    ใช้ตัดสินว่าจะยอมให้ตกไปใช้โมเดลสำรองไหม เมื่อเจ้าหลักตอบไม่ได้

    ที่มา: ตอนรันชุดประเมิน 113 ข้อ คำถาม "หลักสูตรการแพทย์แผนไทยประยุกต์ พ.ศ. 2565
    ต้องเรียนทั้งหมดกี่หน่วยกิต" ตกไปที่โมเดลสำรองแล้วตอบว่า 180 หน่วยกิต ทั้งที่
    เอกสารเขียนไว้ 147 — เลข 180 ในเอกสารนั้นเป็นเลขหน้า เป็นยอดเงินค่าลงทะเบียน
    และเป็นชั่วโมงฝึกปฏิบัติ ไม่มีที่ไหนเป็นหน่วยกิตเลย

    ชุดประเมินนับข้อนั้นว่า "ผ่าน" เพราะมันวัดแค่ว่ายอมตอบหรือปฏิเสธ ไม่ได้ตรวจว่า
    ตัวเลขถูกไหม ความผิดพลาดแบบนี้จึงมองไม่เห็นจากคะแนนรวม

    เหตุผลที่ยอมไม่ตอบดีกว่า: คนที่ได้ตัวเลขผิดไปวางแผนเรียนต่อไม่มีทางรู้ว่าผิด
    ส่วนคนที่ได้ข้อความว่ายังตอบไม่ได้ตอนนี้ รู้ทันทีว่าต้องถามใหม่หรือไปหาจากที่อื่น

    ข้อจำกัด: กันได้เฉพาะตอนที่เจ้าหลักล้มแล้วจะตกไปตัวสำรองเท่านั้น ถ้าตั้งค่าให้ใช้
    โมเดลในเครื่องเป็นตัวหลักอยู่แล้ว ตัวกรองนี้ไม่ช่วยอะไร
    """
    return any(w in text for w in _NUMERIC_WORDS)


def _persist(db: Session, session_id: uuid.UUID, question: str, reply: str) -> None:
    db.add(ChatMessage(session_id=session_id, role="user", content=question))
    db.add(ChatMessage(session_id=session_id, role="assistant", content=reply))
    db.commit()


def prepare_answer(
    db: Session,
    user_id: uuid.UUID,
    session_id: uuid.UUID | None,
    message: str,
) -> Prepared:
    connector = get_llm_connector()
    session = _load_session(db, user_id, session_id)
    history = _load_history(db, session.id)

    # --- 0. คำทักทาย/ขอบคุณ/ถามตัวตน -> ตอบทันทีโดยไม่ค้นเอกสารและไม่เรียก LLM ---
    if (canned := match_small_talk(message)) is not None:
        return Prepared(
            session_id=session.id,
            status="small_talk",
            search_query=message,
            best_score=0.0,
            citations=[],
            canned=canned,
            messages=[],
        )

    # --- 0.5 คำถามค่าเทอม -> ตอบจากตารางประกาศของคณะ ไม่ค้นเอกสาร มคอ.2 ---
    #
    # เอกสาร มคอ.2 ไม่มีค่าเทอม มีแต่งบประมาณที่มหาวิทยาลัยใช้ต่อนักศึกษาหนึ่งคน
    # (ราว 22,000 บาท) ซึ่งเคยถูกหยิบมาตอบแทนค่าเทอมจริง (12,000 บาท) มาแล้ว
    # การลัดมาตอบจากตารางจึงกันความเข้าใจผิดนั้นตั้งแต่ต้นทาง ดูเหตุผลเต็มใน
    # services/tuition.py
    if is_tuition_question(message):
        return Prepared(
            session_id=session.id,
            status="answered",
            search_query=message,
            best_score=0.0,
            citations=[],
            canned=tuition_answer(message),
            messages=[],
        )

    # --- 0.7 คำถามขอคำแนะนำว่าควรเรียนสาขาไหน -> ใช้ระบบจับคู่สาขา ไม่ใช่ถาม-ตอบเอกสาร ---
    # ด่านตรวจว่าเอกสารตอบได้ไหมใช้ไม่ได้กับคำถามประเภทนี้ (ดูเหตุผลใน
    # _asks_for_a_recommendation) ถ้าจัดอันดับไม่สำเร็จก็ปล่อยให้ไหลไปทางปกติ
    if _asks_for_a_recommendation(message) and (advice := _recommendation_reply(db, message)):
        return Prepared(
            session_id=session.id,
            status="answered",
            search_query=message,
            best_score=0.0,
            citations=[],
            canned=advice,
            messages=[],
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

    # --- 2.5 คำถามภาษาอังกฤษ: ลองค้นด้วยคำไทยที่แปลได้ แล้วเลือกอันที่ดีกว่า ---
    # เอกสารเป็นภาษาไทยล้วน การเติมคำไทยต่อท้ายคำถามอังกฤษยังไม่พอเพราะถ้อยคำอังกฤษ
    # กินสัดส่วนส่วนใหญ่ของเวกเตอร์ (ดูตัวเลขที่วัดไว้ใน query_expansion.thai_only_query)
    if not written_in_thai(message) and (thai_query := thai_only_query(message)):
        alt = _retrieve(db, connector, thai_query)
        alt_score = alt[0].score if alt else 0.0
        if alt_score > best_score:
            chunks, best_score, search_query = alt, alt_score, thai_query

    # --- 3. ตัดสินว่าจะตอบ ปฏิเสธ หรือบอกว่าไม่มีข้อมูล ---
    citations: list[ChatCitation] = []
    status: str
    # ข้อความสำเร็จรูปด้านล่างไม่ผ่านโมเดล จึงต้องเลือกภาษาเองจากคำถามของผู้ใช้
    thai = written_in_thai(message)
    out_of_scope = OUT_OF_SCOPE_REPLY if thai else OUT_OF_SCOPE_REPLY_EN
    not_found = NOT_FOUND_REPLY if thai else NOT_FOUND_REPLY_EN
    # ผู้ใช้เอ่ยชื่อหลักสูตรของคณะมาเอง คำถามจึงอยู่ในขอบเขตแน่นอน ไม่ว่าคะแนนค้นหา
    # จะต่ำแค่ไหน คะแนนต่ำในกรณีนี้แปลว่า "เอกสารไม่มีเรื่องที่ถาม" ไม่ใช่ "ถามนอกเรื่อง"
    # ซึ่งต้องตอบคนละแบบ — เจอจริงกับหลักสูตรสาธารณสุขศาสตร์ที่คลังมีแต่ข้อมูลจากหน้าเว็บ
    # ไม่มีรายวิชา ผู้ใช้ถามถึงวิชาบังคับแล้วถูกตอบว่าถามนอกเรื่อง
    names_program = _names_a_program(db, message)
    if best_score < OFF_TOPIC_THRESHOLD and not names_program:
        # ต่ำขนาดนี้คือไม่มีอะไรในคลังใกล้เคียงเลย ตัดจบโดยไม่ต้องเสียเวลาเรียก LLM
        reply_text, status = out_of_scope, "out_of_scope"
    # ช่วงก้ำกึ่ง: คะแนนแยกไม่ออกว่า "นอกเรื่อง" หรือ "ในเรื่องแต่เอกสารไม่ครอบคลุม"
    # จึงถามเรื่องหัวข้อเพิ่มอีกหนึ่งคำถาม เฉพาะในช่วงนี้เท่านั้น เพื่อไม่ให้คำถาม
    # ที่คะแนนสูงอยู่แล้ว (ซึ่งอยู่ในเรื่องแน่นอน) ต้องเสียเวลาเรียก LLM เพิ่ม
    elif (
        best_score < AMBIGUOUS_UNTIL
        and not names_program
        and not _is_about_scope(connector, search_query)
    ):
        reply_text, status = out_of_scope, "out_of_scope"
    elif not _can_answer_from(connector, chunks, search_query):
        reply_text, status = not_found, "not_found"
    else:
        status = "answered"

    messages: list[LLMMessage] = []
    if status == "answered":
        reply_text = None
        messages = [LLMMessage(role="system", content=CHAT_SYSTEM_PROMPT)]
        for m in history:
            messages.append(LLMMessage(role=m.role, content=m.content))
        messages.append(
            LLMMessage(role="user", content=build_chat_prompt(_format_chunks(chunks), message))
        )
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

    return Prepared(
        session_id=session.id,
        status=status,
        search_query=search_query,
        best_score=round(best_score, 4),
        citations=citations,
        canned=reply_text,
        messages=messages,
        allow_fallback=not _asks_for_a_number(message),
    )


def answer_question(
    db: Session,
    user_id: uuid.UUID,
    session_id: uuid.UUID | None,
    message: str,
) -> ChatReply:
    """ตอบแบบรอจนเขียนเสร็จแล้วส่งทีเดียว — ใช้โดยชุดประเมินและผู้เรียกที่ไม่ต้องการสตรีม"""
    p = prepare_answer(db, user_id, session_id, message)
    if p.canned is not None:
        reply_text = p.canned
    else:
        # temperature ต่ำเพื่อลดการแต่งเติม — งานนี้ต้องการความตรงกับเอกสาร
        # มากกว่าความหลากหลายของสำนวน
        connector = get_llm_connector()
        reply_text = connector.chat(
            p.messages,
            temperature=0.1,
            num_predict=connector.answer_token_cap,
            **no_fallback_kwargs(connector, p.allow_fallback),
        ).strip()

    _persist(db, p.session_id, message, reply_text)

    return ChatReply(
        session_id=p.session_id,
        reply=reply_text,
        search_query=p.search_query,
        top_score=p.best_score,
        status=p.status,
        in_scope=p.status in ("answered", "not_found"),
        citations=p.citations,
    )


def stream_answer(
    db: Session,
    user_id: uuid.UUID,
    session_id: uuid.UUID | None,
    message: str,
) -> Iterator[str]:
    """
    ตอบแบบทยอยส่ง คืนเป็นบรรทัดตามรูปแบบ Server-Sent Events

    ลำดับเหตุการณ์: meta (หนึ่งครั้ง) -> token (หลายครั้ง) -> done
    ฝั่งหน้าเว็บใช้ meta ตั้งค่าสถานะกับรายการอ้างอิงได้ทันทีก่อนตัวอักษรแรกมาถึง

    การบันทึกบทสนทนาต้องเปิด session ฐานข้อมูลใหม่ ไม่ใช้ตัวที่รับเข้ามา เพราะ
    FastAPI ปิด session ของ dependency ทิ้งตั้งแต่ตอนที่ route คืนค่า ซึ่งเกิดก่อน
    generator นี้ทำงานจบ ถ้าใช้ตัวเดิมจะได้ error เรื่อง session ถูกปิดไปแล้ว
    """
    p = prepare_answer(db, user_id, session_id, message)
    yield _sse(
        "meta",
        {
            "session_id": str(p.session_id),
            "status": p.status,
            "search_query": p.search_query,
            "top_score": p.best_score,
            "in_scope": p.status in ("answered", "not_found"),
            "citations": [c.model_dump(mode="json") for c in p.citations],
        },
    )

    if p.canned is not None:
        yield _sse("token", {"t": p.canned})
        reply_text = p.canned
    else:
        parts: list[str] = []
        connector = get_llm_connector()
        for chunk in connector.chat_stream(
            p.messages,
            temperature=0.1,
            num_predict=connector.answer_token_cap,
            **no_fallback_kwargs(connector, p.allow_fallback),
        ):
            parts.append(chunk)
            yield _sse("token", {"t": chunk})
        reply_text = "".join(parts).strip()

    with SessionLocal() as fresh:
        _persist(fresh, p.session_id, message, reply_text)
    yield _sse("done", {})


def _sse(event: str, data: dict) -> str:
    # ต้องแปลงเป็น JSON เสมอ เพราะรูปแบบ SSE ใช้ขึ้นบรรทัดใหม่เป็นตัวจบเหตุการณ์
    # ข้อความภาษาไทยที่มีการขึ้นบรรทัดใหม่จึงทำให้ผู้รับตีความผิดถ้าส่งดิบๆ
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
