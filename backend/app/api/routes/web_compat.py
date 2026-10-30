"""
เส้นทางที่หน้าเว็บของทีมออกแบบเรียกอยู่ — รับรูปแบบข้อมูลของหน้าเว็บนั้นตรงๆ

    POST /chat-web            แชท (รับประวัติทั้งก้อน คืนข้อความดิบทีละส่วน)
    POST /compare-courses     เปรียบเทียบสาขา (ส่งรายการสาขามาพร้อมชื่อ)
    POST /recommend-major     แนะนำสาขาจากคำตอบแบบสอบถาม

ทำไมไม่ทับเส้นทางเดิม
--------------------
`/chat` ของเราใช้อยู่แล้วโดยชุดประเมิน หน้าทดสอบ และเอกสารสำหรับนักพัฒนา และรับ
คำถามทีละข้อความพร้อม session_id ส่วนหน้าเว็บส่งประวัติทั้งก้อนมาแล้วคาดหวังข้อความดิบ
กลับไป การเอาสองสัญญามาไว้ที่เส้นทางเดียวกันทำให้ทั้งคู่เปราะ

จึงแยกเป็น `/chat-web` แล้วให้ Caddy เป็นตัวแปลงเส้นทาง `/api/chat` ของหน้าเว็บมาที่นี่
ส่วนอีกสองเส้นทางไม่ชนกับของเดิมจึงใช้ชื่อตามที่หน้าเว็บเรียกได้เลย

ทั้งสามเส้นทางไม่ต้องเข้าสู่ระบบ เพราะหน้าเว็บเปิดให้นักเรียนทั่วไปใช้โดยไม่ต้องสมัคร
เบื้องหลังใช้บัญชีกลางบัญชีเดียว (ดูเหตุผลและข้อแลกเปลี่ยนใน services/web_compat.py)
"""
import base64
import json
import logging
import re
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import web_rate_limiter
from app.db.session import get_db
from app.services.chat import PriorTurn, stream_answer
from app.services import ai_settings
from app.services.llm_client import (chat_model_used, chat_models_used, connector_for,
                                     embed_model_used, reset_chat_model)
from app.services.curriculum_facts import LIST_FIELDS
from app.services.program_compare import compare_programs
from app.services.program_match import (CHUNKS_PER_COURSE, build_match_query, build_profile_text,
                                        confidence_of, match_programs)
from app.services.program_names import program_about, program_facts
from app.services.course_scope import degree_level_of, degree_of_title
from app.services.web_compat import canonical_labels, label_of, match_by_title, normalise_title, shared_user

from llm.connector import (LLMConnectionError, reset_budget,  # noqa: E402
                           start_budget)
from llm.prompts import NO_EVIDENCE_MARKER  # noqa: E402

router = APIRouter(tags=["web-compat"])
logger = logging.getLogger("course_advisor")

BUSY = "ขออภัยครับ ระบบตอบไม่ได้ในขณะนี้ กรุณาลองใหม่อีกครั้ง"

# เพดานเวลาของหน้าแนะนำสาขาและหน้าเปรียบเทียบ
#
# สองเส้นทางนี้ไม่เคยตั้งเพดานเวลาเลย ต่างจาก /chat-web ที่ตั้งมาตั้งแต่ต้น ผลคือเมื่อ
# Gemini ตอบ 503 ครบทุกรุ่นแล้วตกไปใช้โมเดลในเครื่อง (ซึ่งช้ามากเพราะเซิร์ฟเวอร์ไม่มี
# การ์ดจอ) คำขอหนึ่งใช้เวลาเท่ากับ ReadTimeout ของ Ollama คูณจำนวนครั้งที่ลองซ้ำ
# วัดจาก production เมื่อ 29 ต.ค. 2569: คำขอ /recommend-major เวลา 09:29:01 ตอบกลับ
# 09:35:16 — **6 นาที 15 วินาที** โดยหน้าเว็บหมุนรออยู่ทั้งหมดนั้น
#
# ตั้งเพดานแล้ว http_timeout() จะหดเวลาของทุกคำขอ HTTP ให้ไม่เกินเวลาที่เหลือ และ
# check_budget() จะหยุดลองรุ่นถัดไปเมื่อหมดเวลา ผู้ใช้จึงได้ข้อความบอกเหตุแทนการรอ
#
# 90 วินาทีเพราะคำขอที่สำเร็จตามปกติใช้ 9-35 วินาที (วัดวันเดียวกัน: compare 31 วินาที
# ตอนที่ Gemini ล่มไปรอบหนึ่งแล้วกลับมา) เผื่อไว้อีกเท่าตัวกว่า แต่ยังสั้นกว่าของเดิมหลายเท่า
RESULT_PAGE_BUDGET_S = 90.0

# แถวจากตารางเปรียบเทียบที่นำไปแสดงเป็นข้อดีของแต่ละสาขา เรียงตามที่นักเรียนอยากรู้ก่อน
_PROS_ROWS = ["เรียนอะไรบ้าง", "ทักษะที่ได้รับ", "จบแล้วทำงานอะไร", "จำนวนหน่วยกิต", "ค่าเทอม"]
_BEST_FOR_ROW = "คุณสมบัติผู้เข้าศึกษา"
_MISSING_PREFIX = "ไม่พบข้อมูล"

# ชนิดของรายการ "อาชีพ" ใน mko.v_live_list_items — อ้างจากที่เดียวกับที่ชั้นคำตอบใช้
# เพื่อไม่ให้สองที่หลุดจากกันเมื่อชื่อชนิดเปลี่ยน
_CAREER_ITEM_TYPE = LIST_FIELDS["careers"]

# หน้าเว็บแสดงสาขาแนะนำ 1 อันดับหลัก กับอีกไม่เกิน 2 อันดับสำรอง แต่ต้องขอมาเผื่อมาก
# เพราะอันดับที่หลังบ้านคืนมาต้องมีอยู่ในรายการสาขาที่หน้าเว็บส่งมาด้วยจึงจะแสดงได้
# ฐานข้อมูลสองฝั่งมีสาขาไม่ตรงกันทั้งหมด ขอมาน้อยแล้วเหลือรอดไม่ถึงสามใบได้ง่าย
#
# เคยตั้งไว้ที่ 6 เพราะยิ่งขอมาเยอะ เหตุผลประกอบยิ่งขาดหาย แต่สาเหตุจริงของอาการนั้น
# คือเพดานความยาวคำตอบที่ไม่ได้กำหนดไว้ ซึ่งแก้ไปแล้ว จึงขยับกลับขึ้นมาได้
_MATCH_LIMIT = 10
_MAX_ALTERNATIVES = 2

NO_REASON = "ระบบจัดอันดับจากความใกล้เคียงกับเนื้อหาในเอกสารหลักสูตรแล้ว แต่ยังเขียนคำอธิบายประกอบให้ไม่ได้ในขณะนี้"

# ต่างจาก NO_REASON ตรงที่อันนั้นคือ "เขียนคำอธิบายไม่ได้ตอนนี้" (โมเดลล่ม)
# ส่วนอันนี้คือ "เอกสารไม่มีข้อมูลให้เขียน" ซึ่งเป็นข้อเท็จจริงเกี่ยวกับเอกสาร ไม่ใช่
# ความขัดข้องชั่วคราว ผู้อ่านควรแยกสองอย่างนี้ออกจากกันได้
NO_EVIDENCE_REASON = "เอกสารหลักสูตรของสาขานี้ไม่ได้ระบุข้อมูลที่เชื่อมโยงกับสิ่งที่คุณเลือกไว้โดยตรง"


class WebMessage(BaseModel):
    role: str
    content: str


class WebChatRequest(BaseModel):
    messages: list[WebMessage] = Field(min_length=1)
    # id ของตัวเลือกโมเดลที่ผู้ใช้กดเลือก (ดู GET /ai-options)
    #
    # รับเป็น "id" ไม่ใช่ชื่อรุ่น เพราะชื่อรุ่นที่รับจากหน้าเว็บตรง ๆ แปลว่าใครก็สั่ง
    # ให้เซิร์ฟเวอร์ไปเรียกรุ่นไหนก็ได้ · ค่าว่างหรือ id ที่ไม่รู้จัก = ใช้ค่าที่ผู้ดูแลตั้งไว้
    model_choice: str = ""


class WebCourse(BaseModel):
    id: str
    title: str = ""
    # ระดับการศึกษาที่หน้าเว็บส่งมา ("ปริญญาโท" / "ปริญญาเอก" / "ปริญญาตรี")
    #
    # จำเป็นเพราะคณะมีสาขาที่ชื่อและปีเดียวกันแต่คนละระดับปริญญา ถ้าไม่มีช่องนี้
    # match_by_title() จะเลือกเล่มเดียวกันให้ทั้งสองรายการ แล้วเอาเล่มนั้นมาเทียบ
    # กับตัวเอง · ค่าว่างยังรับได้ ผู้เรียกรุ่นเก่าจึงไม่พัง
    level: str = ""


class WebCompareRequest(BaseModel):
    courses: list[WebCourse] = Field(min_length=2)


class WebRecommendRequest(BaseModel):
    answers: dict[str, Any] = Field(default_factory=dict)
    courses: list[WebCourse] = Field(min_length=1)


def _parse_event(event: str) -> tuple[str | None, dict | None]:
    """แกะเหตุการณ์ SSE หนึ่งก้อน — รูปแบบ: event: <ชื่อ> ขึ้นบรรทัดใหม่ data: <json>"""
    kind = data = None
    for line in event.split(chr(10)):
        if line.startswith("event:"):
            kind = line[6:].strip()
        elif line.startswith("data:"):
            data = line[5:].strip()
    if not data:
        return kind, None
    try:
        return kind, json.loads(data)
    except json.JSONDecodeError:
        return kind, None


def _b64(value: str) -> str:
    """
    ค่า header ถูกเข้ารหัสเป็น latin-1 ตอนส่งออก ข้อความไทยจึงใส่ตรงๆ ไม่ได้ (UnicodeEncodeError)
    หุ้มด้วย base64 ของ UTF-8 ซึ่งเป็นวิธีเดียวกับที่หน้าเว็บถอด X-RAG-Sources อยู่แล้ว
    """
    return base64.b64encode(value.encode("utf-8")).decode("ascii")


def _source_headers(db: Session, source: dict | None) -> dict[str, str]:
    """
    header บอกที่มาของคำตอบ ให้หน้าเว็บทำปุ่ม "เปิดเอกสารต้นฉบับ" ได้

    ส่งเฉพาะเมื่อรู้เอกสารจริงเท่านั้น ไม่มี document_id ก็ไม่ส่งอะไรเลย ห้ามเดาหรือส่งค่าว่าง
    เพราะหน้าเว็บจะสร้างลิงก์ที่เปิดไม่ได้ให้ผู้ใช้กด (ดู docs/FRONTEND_PDF_LINK_INSPECTION.md)

    เลขหน้าเป็นของเสริม ไม่มีก็ยังเปิดเอกสารที่หน้าแรกได้

    ชื่อเอกสารและชื่อหลักสูตรอ่านจากฐานข้อมูลด้วย document_id ที่ได้มาเท่านั้น
    ไม่ได้เดาจากข้อความที่ AI ตอบ ถ้าหาแถวไม่เจอก็ไม่ส่งสองค่านี้ แต่ยังส่ง
    X-Source-Document/X-Source-Page ตามเดิม เพื่อไม่ให้พฤติกรรมที่มีอยู่เปลี่ยน
    """
    if not isinstance(source, dict):
        return {}
    document_id = str(source.get("document_id") or "").strip()
    if not document_id:
        return {}
    headers = {"X-Source-Document": document_id}
    page = source.get("page_start")
    if isinstance(page, int) and page > 0:
        headers["X-Source-Page"] = str(page)

    # ชื่อไฟล์เอกสาร + ชื่อหลักสูตรที่เอกสารนั้นสังกัด มาจาก FK course_documents.course_id
    # จึงเป็นความจริงจากฐานข้อมูล ไม่ใช่การจับคู่จากข้อความ
    #
    # ล้มเหลวตรงนี้ต้องไม่ทำให้ทั้งคำตอบล้ม — คำตอบสำคัญกว่าปุ่มเสริม
    try:
        row = db.execute(
            text(
                "SELECT d.original_filename, c.title "
                "FROM course_documents d JOIN courses c ON c.id = d.course_id "
                "WHERE d.id = :id"
            ),
            {"id": document_id},
        ).mappings().first()
    except Exception:  # noqa: BLE001
        logger.exception("อ่านชื่อเอกสาร/หลักสูตรของ %s ไม่สำเร็จ", document_id)
        return headers

    if row is None:
        return headers
    filename = (row["original_filename"] or "").strip()
    programme = (row["title"] or "").strip()
    if filename:
        headers["X-Source-Title"] = _b64(filename)
    if programme:
        headers["X-Source-Programme"] = _b64(programme)
    return headers


@router.get("/ai-options")
def ai_options() -> dict:
    """
    ตัวเลือกโมเดลที่ผู้ใช้หน้าเว็บเลือกได้ — หน้าเว็บเอาไปทำปุ่ม ไม่ต้อง hardcode เอง

    เปิดสาธารณะเพราะเป็นรายชื่อตัวเลือกกับคำอธิบาย ไม่มีคีย์หรือค่าตั้งค่าใดหลุดออกไป
    และหน้าเว็บต้องเรียกได้ก่อนผู้ใช้ล็อกอิน · ตัวที่เซิร์ฟเวอร์นี้ใช้ไม่ได้จะไม่อยู่ในรายการ
    """
    return {"options": ai_settings.public_choices()}


@router.post("/chat-web", dependencies=[Depends(web_rate_limiter)])
def chat_web(payload: WebChatRequest, db: Session = Depends(get_db)) -> StreamingResponse:
    """
    แชทในรูปแบบที่หน้าเว็บรออยู่ — ส่งกลับเป็นข้อความดิบ ไม่ใช่ Server-Sent Events

    หน้าเว็บอ่านสตรีมแล้วต่อข้อความเข้าไปในกล่องแชทตรงๆ ไม่ได้แยกเหตุการณ์ จึงต้อง
    แกะเฉพาะเนื้อความออกมาจาก SSE ของ stream_answer() ก่อนส่งออกไป

    รับประวัติมาทั้งก้อนแล้วส่งต่อให้หลังบ้านทั้งหมด เพราะหน้าเว็บไม่ได้เก็บ session_id
    ไว้ หลังบ้านจึงจำบทสนทนาแทนให้ไม่ได้ — ประวัติที่ใช้ตอบต้องมาจากที่หน้าเว็บส่งมา
    """
    message = next((m.content for m in reversed(payload.messages) if m.role == "user"), "")
    if not message.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "ไม่พบคำถามของผู้ใช้")

    # ส่งบทสนทนาก่อนหน้าที่หน้าเว็บแนบมาด้วยเข้าไปให้หลังบ้านใช้
    #
    # เดิมหยิบเฉพาะข้อความล่าสุดแล้วเรียกด้วย session_id=None โดยมีคอมเมนต์กำกับว่า
    # "หลังบ้านจำบทสนทนาเองด้วย session_id อยู่แล้ว" ซึ่งไม่จริง — session_id เป็น None
    # ทุกครั้ง หลังบ้านจึงสร้างบทสนทนาใหม่ทุกคำถาม ประวัติที่หน้าเว็บอุตส่าห์ส่งมาถูกทิ้ง
    # ทั้งหมด ผลคือถามต่อว่า "แล้วจบไปทำงานอะไรได้บ้าง" หลังถามถึงวิทยาการคอมพิวเตอร์
    # จะได้คำถามกลับว่าสนใจสาขาไหน ทั้งที่เพิ่งคุยกันไป
    #
    # หน้าเว็บไม่ได้เก็บ session_id ไว้ จึงรับประวัติจากที่มันส่งมาแทนการอ่านฐานข้อมูล
    # ตัดข้อความสุดท้ายออกเพราะนั่นคือคำถามปัจจุบัน ไม่ใช่ประวัติ
    prior = [
        PriorTurn(role="assistant" if m.role == "assistant" else "user", content=m.content)
        for m in payload.messages[:-1]
        if m.content.strip()
    ]

    user_id = shared_user(db).id

    # ดึงเหตุการณ์แรก (meta) ออกมาก่อน เพื่ออ่านที่มาของคำตอบไปใส่เป็น header
    #
    # ต้องทำก่อนสร้าง StreamingResponse เพราะ header ถูกส่งไปพร้อมสถานะ HTTP ตั้งแต่ไบต์แรก
    # meta มาก่อน token เสมอ (ดู services/chat.py::stream_answer) การดึงหนึ่งเหตุการณ์จึงไม่ทำให้
    # เสียตัวอักษรของคำตอบ เนื้อความที่ผู้ใช้เห็นเหมือนเดิมทุกตัว
    #
    # ข้อผิดพลาดระหว่างดึง meta ต้องยังตอบเป็นข้อความสถานะ 200 เหมือนเดิม ไม่ใช่ 500
    # เพราะหน้าเว็บอ่านสตรีมเป็นข้อความล้วนแล้วแสดงให้ผู้ใช้ตรงๆ
    source_headers: dict[str, str] = {}
    prelude: str | None = None
    stream = iter(())
    try:
        # ตัวเลือกของผู้ใช้ — ถ้า id ไม่รู้จักหรือใช้ไม่ได้ ให้ถอยไปใช้ค่าที่ผู้ดูแลตั้งไว้
        # เงียบ ๆ ดีกว่าโยนข้อผิดพลาด เพราะหน้าเว็บรุ่นเก่าอาจยังจำ id เดิมไว้
        picked = ai_settings.public_choice(payload.model_choice)
        chosen, budget_s = (connector_for(picked[0]), picked[1]) if picked else (None, None)
        stream = stream_answer(db, user_id=user_id, session_id=None, message=message,
                               prior=prior, connector=chosen, budget_s=budget_s)
        kind, parsed = _parse_event(next(stream, ""))
        if kind == "meta" and parsed:
            source_headers = _source_headers(db, parsed.get("source"))
    except LLMConnectionError as e:
        # ส่งต่อเฉพาะข้อความที่ "เขียนไว้ให้ผู้ใช้" ไม่ใช่ str(exc) ซึ่งมีรายละเอียด
        # วินิจฉัยและอาจพาเนื้อหาจากปลายทางออกมา (ดู LLMConnectionError.user_text)
        prelude = (getattr(e, "user_text", None) or "").strip() or BUSY
    except Exception:  # noqa: BLE001
        logger.exception("chat-web ล้มตั้งแต่ก่อนเริ่มสตรีม")
        prelude = BUSY

    def text_only():
        if prelude is not None:
            yield prelude
            return
        try:
            for event in stream:
                kind, parsed = _parse_event(event)
                if parsed is None:
                    continue
                if kind == "token" and parsed.get("t"):
                    yield parsed["t"]
                elif kind == "error":
                    # ส่งเป็นตัวอักษรต่อท้าย เพราะสถานะ HTTP ถูกส่งไปตั้งแต่ตัวอักษรแรกแล้ว
                    yield "\n\n" + parsed.get("detail", BUSY)
        except LLMConnectionError as e:
            # ส่งเหตุผลให้ผู้ใช้เมื่อตัวเชื่อมต่อเขียนไว้ให้ (user_text) เพื่อไม่ให้ผู้ใช้
            # เห็นแค่ "ระบบตอบไม่ได้ในขณะนี้" ทั้งที่ระบบตั้งใจไม่ตอบและมีเหตุผลอยู่
            # แต่ไม่ส่ง str(exc) ต่อ เพราะข้อความวินิจฉัยไม่ได้เขียนให้ผู้ใช้อ่าน
            # และอาจพาเนื้อหาจากปลายทางออกมา — เจอจาก n1-05 เมื่อ 14 ต.ค. 2569
            yield "\n\n" + ((getattr(e, "user_text", None) or "").strip() or BUSY)
        except Exception:
            logger.exception("chat-web ล้มกลางคัน")
            yield "\n\n" + BUSY

    return StreamingResponse(
        text_only(),
        media_type="text/plain; charset=utf-8",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", **source_headers},
    )


# ปี พ.ศ. ของฉบับในชื่อหลักสูตร เช่น "…สาขาวิชาวิทยาการคอมพิวเตอร์ (พ.ศ. 2566)"
_EDITION_IN_TITLE = re.compile(r"\(\s*พ\s*\.?\s*ศ\s*\.?\s*(25\d\d)\s*\)")


def _course_for_site_title(db: Session, title: str, level: str = "") -> "Course | None":
    """
    หาหลักสูตรในคลังเอกสารของสาขาที่หน้าเว็บถามถึง — **ยึด course_id ของแถวบนเว็บก่อน**

    แถวใน web.site_courses มีคอลัมน์ course_id ซึ่งเป็นการจับคู่ที่ทำไว้ตอนย้ายข้อมูล
    และเป็นของที่ถูกต้องกว่าเดาจากชื่อ เพราะชื่อบนเว็บกับชื่อในเอกสารไม่ตรงกันเสมอไป
    วัดจริงเมื่อ 15 ต.ค. 2569: สาขา "เทคโนโลยีการเกษตรสมัยใหม่" บนเว็บ คู่กับ
    "หลักสูตร…สาขาวิชาการจัดการเทคโนโลยีการเกษตรสมัยใหม่ (พ.ศ. 2564)" ในคลัง
    การเทียบด้วยชื่ออย่างเดียวจึงไม่เจอ และหน้านั้นได้ {} กลับไปทั้งที่มีเอกสารอยู่

    **ชื่อซ้ำกันหลายแถวถือว่าใช้ไม่ได้** ไม่ใช่หยิบแถวแรก เพราะสองแถวนั้นอาจเป็นคนละ
    หลักสูตร แล้วค่าที่ได้จะเป็นของอีกตัวโดยไม่มีอะไรบอก · กรณีนั้นถอยไปใช้ตัวจับคู่
    ที่แยกระดับปริญญาได้แทน

    ถ้าหาแถวบนเว็บไม่เจอ (ผู้เรียกอื่นที่ไม่ใช่หน้ารายละเอียด) ก็ถอยไปเทียบชื่อเช่นกัน
    โดยส่งระดับปริญญาที่ผู้เรียกบอกมาต่อไปด้วย — match_by_title() ใช้มันแยกเล่มโท
    ออกจากเล่มเอกของสาขาที่ชื่อเหมือนกันทุกตัวอักษร และถ้าไม่มีใครบอกระดับมาเลย
    มันจะถือว่าจับคู่ไม่ได้แทนการเดาให้ (ดูหมายเหตุในฟังก์ชันนั้น)
    """
    from app.models.course import Course

    rows = db.execute(
        text("select course_id from web.site_courses where title = :t and course_id is not null"),
        {"t": title},
    ).mappings().all()
    if len(rows) == 1:
        course = db.get(Course, rows[0]["course_id"])
        if course is not None:
            return course
    matched, _ = match_by_title(db, [{"id": "", "title": title, "level": level}])
    return matched[0][1] if matched else None


def _course_documents(db: Session, course_id) -> list[dict]:
    """
    เอกสารของหลักสูตรนั้นสำหรับแท็บ "เอกสารหลักสูตร" ของหน้าเว็บ

    ชื่อที่แสดงคือชื่อหลักสูตรพร้อมปีฉบับจากคลัง (courses.title) ผู้ใช้จึงเห็นว่ากำลังเปิด
    เอกสารของฉบับไหน · ไม่ตั้งชื่อประเภทเอกสารเอง นอกจาก "ฉบับย่อ" ซึ่งดูจากชื่อไฟล์
    ที่ลงท้าย _brief และตรวจแล้วว่าเนื้อหาเป็นฉบับสรุป

    ลิงก์ชี้ไปที่ /api/documents/{id}/pdf ซึ่งเป็นเส้นทางเปิดเอกสารที่มีอยู่แล้ว
    (เปิดแบบ inline รองรับ #page=N) ไม่ได้สร้างที่เก็บไฟล์ใหม่
    """
    rows = db.execute(
        text("""
            select d.id::text as id, d.original_filename as file, d.page_count, c.title as course_title
              from course_documents d join courses c on c.id = d.course_id
             where d.course_id = :cid
             order by d.original_filename
        """),
        {"cid": course_id},
    ).mappings().all()
    out = []
    for r in rows:
        # ไฟล์ที่ไม่ใช่ PDF เปิดผ่านเส้นทางนี้ไม่ได้ (เช่นข้อความที่คัดมาจากหน้าเว็บคณะ)
        # จึงไม่แสดงเป็นเอกสารให้กด เพราะลิงก์จะพาไปหน้า 404
        if not r["file"].lower().endswith(".pdf"):
            continue
        # ฉบับย่อดูจาก "brief" ที่ใดก็ได้ในชื่อไฟล์ ไม่ใช่เฉพาะที่ลงท้าย _brief.pdf
        #
        # ส่งออกเป็นธงของตัวเอง ไม่ให้ผู้เรียกไปแกะคำว่า "ฉบับย่อ" จากข้อความที่แสดง
        # ซึ่งเป็นการเดาจากถ้อยคำ และพังทันทีที่ถ้อยคำเปลี่ยน
        brief = "brief" in r["file"].lower()
        name = r["course_title"] + (" (ฉบับย่อ)" if brief else "")
        bits = [f"ไฟล์ {r['file']}"]
        if r["page_count"]:
            bits.append(f"{r['page_count']} หน้า")
        out.append({
            "name": name,
            "type": bits[0],
            "size": bits[1] if len(bits) > 1 else "",
            "url": f"/api/documents/{r['id']}/pdf",
            "brief": brief,
        })
    return out


def _faculty_for(course_title: str, about: dict) -> list[dict]:
    """
    รายชื่ออาจารย์ผู้รับผิดชอบหลักสูตรสำหรับการ์ดบนหน้าเว็บ — เฉพาะที่ตรงฉบับเท่านั้น

    กฎสองข้อที่ตั้งไว้หลังตรวจเมื่อ 15 ต.ค. 2569
      1. **ฉบับต้องตรงกัน** ชุดรายชื่อมี faculty_source บอกว่ามาจากเล่มไหนปีไหน ถ้าไม่ตรงกับ
         ฉบับของหลักสูตรที่หน้านั้นแสดงอยู่ ให้ไม่แสดงเลย ดีกว่ายืมรายชื่อฉบับเก่ามาอ้างว่า
         เป็นชุดปัจจุบัน (คอมพิวเตอร์แอนิเมชันฯ: รายชื่อมาจากฉบับ 2564 แต่หน้าแสดงฉบับ 2569)
      2. **ป้ายต้องไม่อ้างเกินต้นทาง** ค่าที่มีคือคอลัมน์ "ตำแหน่งทางวิชาการ" ของตารางในเล่ม
         ซึ่งเขียนเป็น "ผู้ช่วยศาสตราจารย์ (เทคโนโลยีสารสนเทศ)" — วงเล็บคือสาขาที่ได้รับ
         ตำแหน่ง ไม่ใช่ความเชี่ยวชาญและไม่ใช่สังกัด จึงติดป้ายว่า "ตำแหน่งทางวิชาการ"

    ไม่ใส่ช่องรูปและอีเมล เพราะเอกสารไม่มีข้อมูลนั้น การ์ดของหน้าเว็บขึ้นไอคอนแทนรูปเองอยู่แล้ว
    """
    source = about.get("faculty_source") or {}
    edition = source.get("edition")
    year = _EDITION_IN_TITLE.search(course_title or "")
    if not edition or not year or edition != year.group(1):
        return []
    out = []
    for person in about.get("faculty", []):
        label = f"อาจารย์ผู้รับผิดชอบหลักสูตร ฉบับ พ.ศ. {edition}"
        if (position := (person.get("academic_position") or "").strip()):
            label += f" · ตำแหน่งทางวิชาการ: {position}"
        out.append({"name": person["name"], "positionTh": label})
    return out


def _course_by_id(db: Session, course_id: str | None) -> "Course | None":
    """หลักสูตรในคลังตามรหัสที่หน้าเว็บส่งมา — คืน None เมื่อรหัสไม่ถูกรูปหรือไม่มีแถวนั้น"""
    from app.models.course import Course

    if not course_id:
        return None
    try:
        key = uuid.UUID(course_id)
    except ValueError:
        return None
    return db.get(Course, key)


def _latest_edition_of(db: Session, course: "Course") -> "Course":
    """
    ฉบับล่าสุดของสาขาเดียวกันและระดับเดียวกัน

    ผู้ใช้ที่กำลังเลือกที่เรียนต้องเห็นเล่มที่ใช้อยู่จริง ไม่ใช่ฉบับก่อนหน้า · การจับคู่ด้วย
    ชื่อเลือกฉบับล่าสุดให้อยู่แล้ว แต่เส้นทางที่ผูกด้วย course_id ของแถวบนเว็บจะตรึงอยู่
    กับเล่มที่ผูกไว้ตลอด ถ้าคณะปรับปรุงหลักสูตรแล้วนำเล่มใหม่เข้าคลัง หน้าเว็บจะยัง
    แสดงของเก่าโดยไม่มีอะไรบอก

    ตัดปีออกจากชื่อแล้วให้ match_by_title หาใหม่ — ระดับปริญญาอ่านได้จากชื่อปริญญา
    ที่ยังติดอยู่ในชื่อเล่ม เล่มโทกับเล่มเอกของสาขาเดียวกันจึงไม่ปนกัน
    หาไม่เจอก็คืนเล่มเดิม ดีกว่าคืนค่าว่างทั้งที่มีข้อมูลอยู่
    """
    base = _EDITION_IN_TITLE.sub("", course.title or "").strip()
    if not base:
        return course
    matched, _ = match_by_title(db, [{"id": "", "title": base}])
    return matched[0][1] if matched else course


@router.get("/course-facts")
def course_facts_web(title: str, course_id: str | None = None, level: str | None = None,
                     db: Session = Depends(get_db)) -> dict:
    """
    ข้อมูลสรุปของหลักสูตรหนึ่ง สำหรับเติมช่องที่ว่างในหน้ารายละเอียดของหน้าเว็บ

    หน้าเว็บดึงข้อมูลชุดนี้จากฐานข้อมูลของตัวเองซึ่งยังไม่มีใครกรอก จึงขึ้นว่า
    "ไม่ระบุ" ทุกช่อง ทั้งที่เอกสาร มคอ.2 ระบุไว้ครบ

    **ถ้าผู้เรียกรู้รหัสหลักสูตรให้ส่ง course_id มาด้วย** — คือค่าในคอลัมน์ course_id
    ของแถวบนเว็บ ซึ่ง /site/courses ส่งไปให้อยู่แล้ว · ชื่อสาขาอย่างเดียวแยกระดับ
    ปริญญาไม่ได้ คณะมีสาขาที่ชื่อเหมือนกันทุกตัวอักษรแต่เป็นคนละระดับ (โท/เอก)
    การเทียบด้วยชื่อจะหยิบแถวไหนก็ได้ในสองแถวนั้น แล้วปี หน่วยกิต และเอกสารจะเป็น
    ของอีกหลักสูตรโดยไม่มีอะไรบอก

    title ยังต้องส่งมาเสมอ เพราะใช้เป็นทางถอยเมื่อรหัสไม่ตรงกับแถวใดในคลัง · ทางถอยนั้น
    ใช้ level ที่ส่งมาด้วย (เช่น "ปริญญาโท") ซึ่งจำเป็นจริงกับสองสาขาที่แถวบนเว็บยังไม่มี
    course_id คือหลักสูตรโทกับเอกของการจัดการเทคโนโลยีการเกษตรและบริหารทรัพยากรชุมชน

    คืน {} เมื่อไม่มีเอกสารของสาขานั้น ผู้เรียกต้องคงค่าเดิมของตัวเองไว้
    """
    course = _course_by_id(db, course_id) or _course_for_site_title(db, title, level or "")
    if course is None:
        return {}
    # ผูกไว้ที่ฉบับไหนก็ตาม ให้แสดงฉบับล่าสุดของสาขานั้นเสมอ
    course = _latest_edition_of(db, course)
    about = dict(program_about(course.title))
    about.pop("faculty_source", None)
    about["faculty"] = _faculty_for(course.title, program_about(course.title))
    if not about["faculty"]:
        about.pop("faculty")
    out = {**program_facts(course.title), **about}
    if (docs := _course_documents(db, course.id)):
        out["documents"] = docs
    # ฉบับของหลักสูตรที่ข้อมูลชุดนี้มาจาก — ส่งแยกเป็นช่องของตัวเอง ไม่ให้หน้าเว็บ
    # ต้องไปแกะปีออกจากชื่อเล่มเอง (ซึ่งจะกลายเป็นกฎการแกะชื่อที่กระจายอยู่สองที่)
    #
    # edition_title คือชื่อเล่มเต็มตามคลังเอกสาร ใช้เป็น "แหล่งอ้างอิง" ที่ผู้ใช้ตรวจต่อได้
    out["edition_title"] = course.title
    if (year := _EDITION_IN_TITLE.search(course.title or "")):
        out["edition_year"] = year.group(1)
    return out


@router.get("/career-lists")
def career_lists_web(db: Session = Depends(get_db)) -> dict:
    """
    รายการอาชีพของทุกหลักสูตรที่ผ่านการตรวจและเผยแพร่แล้ว — ให้หน้า "อาชีพหลังจบ" ของหน้าเว็บใช้

    ทำไมต้องมีเส้นทางนี้
    -------------------
    หน้าเว็บเก็บอาชีพไว้ในคอลัมน์ `careers` ของฐานข้อมูลตัวเอง ซึ่งยังว่างทุกแถว หน้านั้นจึง
    ขึ้นว่า "ยังไม่มีข้อมูลหลักสูตร" ทั้งที่เอกสาร มคอ.2 ระบุอาชีพไว้และเราตรวจกับเอกสาร
    แล้วเผยแพร่เก็บไว้ใน schema mko เรียบร้อย

    อ่านจาก `mko.v_live_list_items` ตรงๆ **ไม่เรียกโมเดลภาษา** จึงได้ผลเดิมทุกครั้งและเร็วพอ
    ให้หน้าเว็บขอครั้งเดียวตอนเปิดหน้า ต่างจาก /compare-courses ที่ให้โมเดลสกัดข้อความจาก
    เอกสารทีละหัวข้อ — ซึ่งช้าและไม่คงที่ จึงใช้ทำหน้ารวมไม่ได้

    คืนเฉพาะหลักสูตรที่ **มีรายการอาชีพที่ผ่านการตรวจแล้วจริง** หลักสูตรที่ยังไม่มีจะไม่อยู่ใน
    ผลลัพธ์เลย ผู้เรียกต้องแสดงสถานะของตัวเอง ห้ามเดาแทน (เหตุผลเดียวกับ _source_headers)

    ทุกรายการมีไฟล์และหน้าของเอกสารต้นทางมาด้วย เพื่อให้หน้าเว็บทำปุ่มเปิดเอกสารได้
    """
    try:
        rows = db.execute(
            text(
                """
                SELECT course_title, seq, text AS item, source_filename, page_start, page_end, document_id
                  FROM mko.v_live_list_items
                 WHERE item_type = :item_type
                 ORDER BY course_title, seq
                """
            ),
            {"item_type": _CAREER_ITEM_TYPE},
        ).mappings().all()
    except Exception:  # noqa: BLE001
        # ยังไม่ได้ลง migration ของ schema mko หรืออ่านไม่ได้ — หน้าเว็บต้องยังเปิดได้
        logger.exception("อ่านรายการอาชีพที่เผยแพร่แล้วไม่สำเร็จ")
        return {"programmes": []}

    grouped: dict[str, list] = {}
    for row in rows:
        grouped.setdefault(row["course_title"], []).append(row)

    programmes = []
    for course_title, items in grouped.items():
        first = items[0]
        source: dict[str, Any] = {
            "file": first["source_filename"],
            "page_start": min(i["page_start"] for i in items),
            "page_end": max(i["page_end"] for i in items),
        }
        # ส่ง document_id เฉพาะเมื่อรู้จริง เพราะหน้าเว็บเอาไปทำลิงก์ /documents/{id}/pdf
        if first["document_id"]:
            source["document_id"] = str(first["document_id"])
        programmes.append({
            "course_title": course_title,
            "careers": [i["item"] for i in items],
            "source": source,
        })
    return {"programmes": programmes}


# ที่มาของสิ่งที่ผู้ใช้เห็นในผลชุดหนึ่ง — ส่งเป็นโครงสร้าง ไม่ใช่ประโยคสำเร็จรูป
#
# หน้าเว็บเลือกถ้อยคำเอง แต่ **ชื่อรุ่นต้องมาจากที่นี่เท่านั้น** ห้ามหน้าเว็บเขียนทับไว้เอง
# เพราะผู้ดูแลเปลี่ยนรุ่นได้ตลอด และเส้นทาง Gemini มีโมเดลในเครื่องรับช่วงต่อได้
#
# explanation เป็น None เมื่อ "ไม่ได้เรียกโมเดล" หรือ "เรียกแล้วแต่ข้อความของมันไม่ได้ถูกใช้"
# หน้าเว็บจะได้ไม่ติดป้ายชื่อรุ่นให้ผลที่ไม่ได้มาจากโมเดล
SCORING_EMBEDDING_RULES = "embedding_and_rules"

# หน้าเปรียบเทียบไม่มีคะแนน แต่ก็ไม่ใช่ข้อมูลดิบจากฐานล้วน ๆ เหมือนกัน — ช่องในตาราง
# ถูก "สกัด" จากเอกสาร มคอ.2 ด้วยโมเดลทีละหลักสูตร ส่วนค่าเทอมมาจากประกาศของคณะ
# ซึ่งไม่ผ่านโมเดลเลย · ผู้ใช้ควรรู้ว่าตารางที่เขาอ่านผ่านมือโมเดลมาแล้ว ไม่ใช่ตารางที่
# พิมพ์อยู่ในเอกสารตรง ๆ
SCORING_DOCUMENT_EXTRACTION = "document_extraction"


def _user_message(exc: Exception) -> str:
    """ข้อความที่ส่งให้ผู้ใช้อ่านเมื่อเรียกโมเดลไม่สำเร็จ — ไม่ใช่ข้อความวินิจฉัยภายใน"""
    return (getattr(exc, "user_text", None) or "").strip() or BUSY


def _engine(explained: bool, scoring: str | None = None, embedded: bool = False) -> dict:
    return {
        "explanation": chat_model_used() if explained else None,
        # ทุกรุ่นที่ตอบสำเร็จในคำขอนี้ ไม่ใช่แค่ตัวสุดท้าย — หนึ่งหน้าอาจผ่านหลายรุ่นเมื่อ
        # เจ้าหลักล้มกลางทางแล้วตัวสำรองรับช่วงต่อ · ไม่ใช่รายชื่อผู้เขียนข้อความที่แสดง
        # เพราะบางคำตอบถูกตัดทิ้งที่ด่านตรวจข้อความอ้างอิง (ดู llm_client._chat_models_used)
        "writers": chat_models_used() if explained else [],
        "scoring": scoring,
        # รุ่นที่เทียบความคล้ายให้ผลชุดนี้จริง — ส่งเฉพาะผลที่คะแนนมาจากเวกเตอร์
        # ผลที่ไม่ได้ใช้เวกเตอร์ต้องไม่ได้ป้ายนี้ติดไป
        "embedding": embed_model_used() if embedded else None,
    }


# ช่องคำตอบที่ "เข้าเวกเตอร์" จริง เทียบกับช่องที่ใช้เฉพาะตอนให้โมเดลเขียนคำอธิบาย
#
# แยกไว้ที่นี่เพราะหลังบ้านเป็นฝ่ายรู้ความจริงข้อนี้ (ดู program_match.build_match_query)
# หน้าเว็บเดาเองไม่ได้ และถ้าวันหนึ่งสูตรเปลี่ยนช่อง ที่นี่ต้องเปลี่ยนตามในที่เดียว
_SCORED_FIELDS = (
    ("favorite_subjects", "วิชาที่ชอบ"),
    ("interests", "ความสนใจ"),
    ("aptitudes", "ความถนัด"),
    ("career_goal", "เป้าหมายอาชีพ"),
)
_UNSCORED_FIELDS = (
    ("study_track", "สายการเรียน"),
    ("work_environment", "สภาพแวดล้อมการทำงาน"),
)


def _answer_rows(answers: dict, fields: tuple) -> list[dict]:
    """คำตอบที่ผู้ใช้กรอกไว้จริงในช่องชุดหนึ่ง — ช่องที่ว่างไม่ต้องส่งไปให้หน้าเว็บ"""
    rows = []
    for key, label in fields:
        value = answers.get(key)
        values = [value] if isinstance(value, str) else list(value or [])
        values = [v for v in values if v]
        if values:
            rows.append({"field": key, "label": label, "values": values})
    return rows


def _rank_key(title: str) -> tuple[str, str | None]:
    """คีย์เทียบชื่อสาขาที่แยกระดับปริญญาด้วย — ใช้จับคู่อันดับกลับไปที่การ์ดบนหน้าเว็บ"""
    return normalise_title(title), degree_level_of(degree_of_title(title))


def _row_value(rows, dimension: str, index: int) -> str | None:
    for row in rows:
        if row["dimension"] == dimension:
            value = row["values"][index]
            return None if value.startswith(_MISSING_PREFIX) else value
    return None


@router.post("/compare-courses", dependencies=[Depends(web_rate_limiter)])
def compare_courses_web(payload: WebCompareRequest, db: Session = Depends(get_db)) -> dict:
    """เปรียบเทียบสาขา — ห่อด้วยเพดานเวลาของคำขอ (ดู RESULT_PAGE_BUDGET_S)"""
    budget = start_budget(RESULT_PAGE_BUDGET_S)
    try:
        return _compare_courses(payload, db)
    finally:
        # ล้างเสมอ ไม่ว่าจะสำเร็จหรือไม่ ไม่งั้นเพดานค้างไปถึงงานถัดไปในบริบทเดียวกัน
        reset_budget(budget)


def _compare_courses(payload: WebCompareRequest, db: Session) -> dict:
    """
    เปรียบเทียบสาขาในรูปแบบที่หน้าเว็บรออยู่

    ช่อง cons ส่งกลับเป็นรายการว่างเสมอ เพราะเอกสาร มคอ.2 ไม่ได้เขียนข้อเสียของ
    หลักสูตรตัวเองไว้ การให้โมเดลคิดข้อเสียขึ้นมาเองคือการแต่งข้อมูล ซึ่งเป็นสิ่งที่
    ระบบนี้ตั้งใจไม่ทำ หน้าเว็บตรวจความยาวก่อนแสดงอยู่แล้ว บล็อกนั้นจึงไม่ขึ้นเอง
    """
    reset_chat_model()
    sent = [c.model_dump() for c in payload.courses]
    matched, unmatched = match_by_title(db, sent)

    if len(matched) < 2:
        names = ", ".join(c["title"] for c in unmatched) or "ที่เลือกมา"
        # สาขาที่มีหลายระดับปริญญาแต่ไม่ได้บอกระดับมา จะอยู่ใน unmatched เช่นกัน
        # ข้อความต้องบอกทางออกให้ด้วย ไม่ใช่บอกแค่ว่าไม่มีเอกสาร ซึ่งไม่จริงในกรณีนี้
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"ยังไม่มีเอกสารหลักสูตรของสาขา: {names} จึงเปรียบเทียบให้ไม่ได้ "
            f"(ถ้าสาขานั้นเปิดสอนหลายระดับปริญญา ต้องระบุระดับมาด้วย)",
        )

    try:
        result = compare_programs(db, [c.id for _, c in matched])
    except LLMConnectionError as e:
        # ส่งข้อความที่เขียนไว้ให้ผู้ใช้อ่าน ไม่ใช่ str(exc) ซึ่งมีรายละเอียดวินิจฉัย
        # ต่อท้ายและอาจพาเนื้อหาจากปลายทางออกมา (ดู LLMConnectionError.user_text)
        # — เส้นทางแชทใช้แบบนี้อยู่แล้ว ตรงนี้เพิ่งมามีผลเพราะหน้าเว็บเริ่มแสดง detail
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            _user_message(e)) from e

    rows = [r if isinstance(r, dict) else r.model_dump() for r in result["rows"]]
    courses = []
    for index, (item, _) in enumerate(matched):
        pros = [
            f"{dim}: {value}"
            for dim in _PROS_ROWS
            if (value := _row_value(rows, dim, index)) is not None
        ]
        courses.append({
            "courseId": item["id"],
            "bestFor": _row_value(rows, _BEST_FOR_ROW, index) or "",
            "pros": pros,
            "cons": [],
        })

    note = ""
    if unmatched:
        missing = ", ".join(c["title"] for c in unmatched)
        note = f" (ยังไม่มีเอกสารหลักสูตรของ {missing} จึงไม่ได้นำมาเปรียบเทียบ)"

    return {
        "summary": (result.get("summary") or "") + note,
        "courses": courses,
        "verdict": "ข้อมูลทั้งหมดสรุปจากเอกสารหลักสูตร (มคอ.2) ของแต่ละสาขา ยกเว้นค่าเทอมที่มาจากประกาศของคณะ",
        # หน้านี้ไม่มีคะแนน แต่มีทั้งขั้นค้นเนื้อหาด้วยเวกเตอร์และขั้นสกัดตารางด้วยโมเดล
        # จึงบอกให้ครบว่าแต่ละขั้นใช้รุ่นไหน (ดู SCORING_DOCUMENT_EXTRACTION)
        "engine": _engine(explained=True, scoring=SCORING_DOCUMENT_EXTRACTION, embedded=True),
    }


@router.post("/recommend-major", dependencies=[Depends(web_rate_limiter)])
def recommend_major_web(payload: WebRecommendRequest, db: Session = Depends(get_db)) -> dict:
    """แนะนำสาขา — ห่อด้วยเพดานเวลาของคำขอ (ดู RESULT_PAGE_BUDGET_S)"""
    budget = start_budget(RESULT_PAGE_BUDGET_S)
    try:
        return _recommend_major(payload, db)
    finally:
        reset_budget(budget)


def _recommend_major(payload: WebRecommendRequest, db: Session) -> dict:
    """
    แนะนำสาขาในรูปแบบที่หน้าเว็บรออยู่

    ชื่อช่องในแบบสอบถามของหน้าเว็บไม่ตรงกับของเรา (skills/goals/track) จึงแปลงก่อน
    """
    reset_chat_model()
    a = payload.answers
    # แปลรหัสตัวเลือกเป็นข้อความไทยที่ผู้ใช้เห็นก่อนเสมอ — หน้าเว็บส่งรหัสอย่าง "tech"
    # หรือ "career-growth" มา ซึ่งแทบไม่มีความหมายให้เทียบกับเอกสารภาษาไทย
    # (ดูเหตุผลและตารางใน services/web_compat.py)
    #
    # ข้อที่เลือกได้หลายข้อต้องผ่าน canonical_labels เพื่อให้คำตอบชุดเดียวกันได้คะแนนเดียวกัน
    # ไม่ว่าผู้ใช้จะกดเลือกลำดับไหน
    answers = {
        "study_track": label_of("track", a["track"]) if a.get("track") else None,
        # ข้อวิชาที่ชอบส่งเป็นชื่อวิชาภาษาไทยอยู่แล้ว label_of จึงคืนค่าเดิมไป
        "favorite_subjects": canonical_labels("subjects", a.get("subjects")),
        "interests": canonical_labels("interests", a.get("interests")),
        "aptitudes": canonical_labels("skills", a.get("skills")),
        "career_goal": canonical_labels("goals", a.get("goals")),
        "work_environment": [label_of("environment", a["environment"])] if a.get("environment") else [],
    }

    try:
        matches = match_programs(db, answers, limit=_MATCH_LIMIT)
    except LLMConnectionError as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            _user_message(e)) from e

    matched, _ = match_by_title(db, [c.model_dump() for c in payload.courses])
    # เทียบกลับด้วยชื่อ ไม่ใช่รหัสของหลักสูตร เพราะการจัดอันดับมองเอกสารทุกฉบับรวม
    # ฉบับเก่า แต่ตารางจับคู่เก็บเฉพาะฉบับล่าสุด — เทียบด้วยรหัสจะทำให้อันดับที่ชนะ
    # ด้วยเอกสารฉบับเก่าหายไปเงียบๆ
    # คีย์รวมระดับปริญญาด้วย เพราะ normalise_title() ตัดชื่อปริญญาทิ้ง สาขาที่มีทั้ง
    # โทและเอกจะได้คีย์เดียวกันแล้วทับกันเหลือใบเดียว
    back = {_rank_key(course.title): item["id"] for item, course in matched}

    ranked: list[tuple[str, object]] = []
    used: set[str] = set()
    for m in matches:
        web_id = back.get(_rank_key(m.title))
        # เอกสารสองฉบับของสาขาเดียวกันชี้ไปที่การ์ดใบเดียวกัน แสดงซ้ำไม่ได้
        if web_id is None or web_id in used:
            continue
        used.add(web_id)
        ranked.append((web_id, m))

    if not ranked:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "ยังไม่มีเอกสารหลักสูตรของสาขาที่เปิดสอนอยู่ จึงแนะนำให้ไม่ได้",
        )

    def card(entry):
        web_id, m = entry
        reason = (m.rationale or "").strip()
        # เครื่องหมายที่โมเดลใช้บอกว่าเอกสารไม่มีข้อมูลรองรับ เป็นภาษาของระบบภายใน
        # ต้องไม่หลุดไปถึงหน้าจอ แปลงเป็นข้อความที่ผู้ใช้อ่านรู้เรื่องแทน
        if not reason or NO_EVIDENCE_MARKER in reason:
            reason = NO_EVIDENCE_REASON if NO_EVIDENCE_MARKER in reason else NO_REASON
        return {
            "courseId": web_id,
            "matchScore": m.match_percent,
            "reason": reason,
            # ที่มาของคะแนนใบนี้ — ค่าที่ระบบคำนวณจริงล้วน ๆ ไม่มีตัวเลขใดมาจากโมเดล
            # และหน้าเว็บคำนวณย้อนกลับเองได้จากค่าชุดนี้
            "why": {
                **m.breakdown,
                "evidence": m.evidence,
                # เหตุผลใบนี้เป็นข้อความที่โมเดลเขียนจริงไหม — ใช้ตัดสินว่าจะติดป้าย
                # ชื่อรุ่นให้ใบนี้ได้หรือไม่ ไม่ใช่เดาจากว่ามีข้อความอยู่หรือเปล่า
                "reason_from_model": reason not in (NO_REASON, NO_EVIDENCE_REASON),
                "no_evidence": reason == NO_EVIDENCE_REASON,
            },
        }

    low = confidence_of(matches) == "low"
    summary = (
        "คะแนนของหลายสาขาใกล้เคียงกันมาก แนะนำให้ดูทุกสาขาที่แสดงประกอบกัน "
        "ไม่ควรยึดอันดับ 1 อย่างเดียว — ผลนี้คำนวณจากเอกสารหลักสูตรจริงของแต่ละสาขา"
        if low else
        "ผลนี้คำนวณจากความใกล้เคียงระหว่างคำตอบของคุณกับเนื้อหาจริงในเอกสารหลักสูตรของแต่ละสาขา"
    )

    cards = [card(e) for e in ranked[:1 + _MAX_ALTERNATIVES]]
    # ติดป้ายชื่อรุ่นเฉพาะเมื่อข้อความของโมเดลถูกใช้จริงอย่างน้อยหนึ่งใบ — โมเดลล่ม
    # หรือเขียนมาแล้วไม่ผ่านด่านตรวจข้อความอ้างอิง ทุกใบจะเป็นข้อความมาตรฐานของระบบ
    explained = any(c["reason"] not in (NO_REASON, NO_EVIDENCE_REASON) for c in cards)

    return {
        "primary": cards[0],
        "alternatives": cards[1:],
        "summary": summary,
        # เปิดไว้ให้ตรวจสอบได้ว่าระบบเข้าใจคำตอบของนักเรียนว่าอย่างไร
        "profileText": build_profile_text(answers),
        # คะแนนไม่ได้มาจากโมเดลที่เขียนคำอธิบาย — มาจากความใกล้เคียงของเวกเตอร์กับ
        # เกณฑ์ของระบบ (ตัดหลักสูตรที่ปิดรับ ยุบฉบับซ้ำ ถ่วงน้ำหนักชื่อหลักสูตร)
        "engine": _engine(explained, scoring=SCORING_EMBEDDING_RULES, embedded=True),
        # ที่มาของคะแนนที่เป็นของ "ทุกใบร่วมกัน" — ส่วนที่เป็นของแต่ละใบอยู่ใน card["why"]
        #
        # ผู้ใช้เทียบย้อนกลับได้ว่าคำตอบข้อไหนเข้าไปอยู่ในเวกเตอร์ และข้อไหนไม่ได้เข้า
        # ไม่มีการคำนวณใหม่ตรงนี้ ทุกค่ามาจากขั้นจัดอันดับที่เพิ่งรันไป
        "scoringDetail": {
            "queryText": build_match_query(answers),
            "answersUsed": _answer_rows(answers, _SCORED_FIELDS),
            "answersNotScored": _answer_rows(answers, _UNSCORED_FIELDS),
            "chunksPerCourse": CHUNKS_PER_COURSE,
        },
    }
