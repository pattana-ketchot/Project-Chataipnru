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
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.chat import stream_answer
from app.services.program_compare import compare_programs
from app.services.program_match import build_profile_text, confidence_of, match_programs
from app.services.web_compat import label_of, labels_of, match_by_title, normalise_title, shared_user

from llm.connector import LLMConnectionError  # noqa: E402

router = APIRouter(tags=["web-compat"])
logger = logging.getLogger("course_advisor")

BUSY = "ขออภัยครับ ระบบตอบไม่ได้ในขณะนี้ กรุณาลองใหม่อีกครั้ง"

# แถวจากตารางเปรียบเทียบที่นำไปแสดงเป็นข้อดีของแต่ละสาขา เรียงตามที่นักเรียนอยากรู้ก่อน
_PROS_ROWS = ["เรียนอะไรบ้าง", "ทักษะที่ได้รับ", "จบแล้วทำงานอะไร", "จำนวนหน่วยกิต", "ค่าเทอม"]
_BEST_FOR_ROW = "คุณสมบัติผู้เข้าศึกษา"
_MISSING_PREFIX = "ไม่พบข้อมูล"

# หน้าเว็บแสดงสาขาแนะนำ 1 อันดับหลัก กับอีกไม่เกิน 2 อันดับสำรอง แต่ต้องขอมาเผื่อมาก
# เพราะอันดับที่หลังบ้านคืนมาต้องมีอยู่ในรายการสาขาที่หน้าเว็บส่งมาด้วยจึงจะแสดงได้
# ฐานข้อมูลสองฝั่งมีสาขาไม่ตรงกันทั้งหมด ขอมาน้อยแล้วเหลือรอดไม่ถึงสามใบได้ง่าย
#
# เคยตั้งไว้ที่ 6 เพราะยิ่งขอมาเยอะ เหตุผลประกอบยิ่งขาดหาย แต่สาเหตุจริงของอาการนั้น
# คือเพดานความยาวคำตอบที่ไม่ได้กำหนดไว้ ซึ่งแก้ไปแล้ว จึงขยับกลับขึ้นมาได้
_MATCH_LIMIT = 10
_MAX_ALTERNATIVES = 2

NO_REASON = "ระบบจัดอันดับจากความใกล้เคียงกับเนื้อหาในเอกสารหลักสูตรแล้ว แต่ยังเขียนคำอธิบายประกอบให้ไม่ได้ในขณะนี้"


class WebMessage(BaseModel):
    role: str
    content: str


class WebChatRequest(BaseModel):
    messages: list[WebMessage] = Field(min_length=1)


class WebCourse(BaseModel):
    id: str
    title: str = ""


class WebCompareRequest(BaseModel):
    courses: list[WebCourse] = Field(min_length=2)


class WebRecommendRequest(BaseModel):
    answers: dict[str, Any] = Field(default_factory=dict)
    courses: list[WebCourse] = Field(min_length=1)


@router.post("/chat-web")
def chat_web(payload: WebChatRequest, db: Session = Depends(get_db)) -> StreamingResponse:
    """
    แชทในรูปแบบที่หน้าเว็บรออยู่ — ส่งกลับเป็นข้อความดิบ ไม่ใช่ Server-Sent Events

    หน้าเว็บอ่านสตรีมแล้วต่อข้อความเข้าไปในกล่องแชทตรงๆ ไม่ได้แยกเหตุการณ์ จึงต้อง
    แกะเฉพาะเนื้อความออกมาจาก SSE ของ stream_answer() ก่อนส่งออกไป

    รับประวัติมาทั้งก้อนแต่ใช้เฉพาะข้อความล่าสุดของผู้ใช้ เพราะหลังบ้านจำบทสนทนา
    เองด้วย session_id อยู่แล้ว
    """
    message = next((m.content for m in reversed(payload.messages) if m.role == "user"), "")
    if not message.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "ไม่พบคำถามของผู้ใช้")

    user_id = shared_user(db).id

    def text_only():
        try:
            for event in stream_answer(db, user_id=user_id, session_id=None, message=message):
                # รูปแบบหนึ่งเหตุการณ์: "event: <ชื่อ>\ndata: <json>\n\n"
                kind = data = None
                for line in event.split("\n"):
                    if line.startswith("event:"):
                        kind = line[6:].strip()
                    elif line.startswith("data:"):
                        data = line[5:].strip()
                if not data:
                    continue
                try:
                    parsed = json.loads(data)
                except json.JSONDecodeError:
                    continue
                if kind == "token" and parsed.get("t"):
                    yield parsed["t"]
                elif kind == "error":
                    # ส่งเป็นตัวอักษรต่อท้าย เพราะสถานะ HTTP ถูกส่งไปตั้งแต่ตัวอักษรแรกแล้ว
                    yield "\n\n" + parsed.get("detail", BUSY)
        except Exception:
            logger.exception("chat-web ล้มกลางคัน")
            yield "\n\n" + BUSY

    return StreamingResponse(
        text_only(),
        media_type="text/plain; charset=utf-8",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _row_value(rows, dimension: str, index: int) -> str | None:
    for row in rows:
        if row["dimension"] == dimension:
            value = row["values"][index]
            return None if value.startswith(_MISSING_PREFIX) else value
    return None


@router.post("/compare-courses")
def compare_courses_web(payload: WebCompareRequest, db: Session = Depends(get_db)) -> dict:
    """
    เปรียบเทียบสาขาในรูปแบบที่หน้าเว็บรออยู่

    ช่อง cons ส่งกลับเป็นรายการว่างเสมอ เพราะเอกสาร มคอ.2 ไม่ได้เขียนข้อเสียของ
    หลักสูตรตัวเองไว้ การให้โมเดลคิดข้อเสียขึ้นมาเองคือการแต่งข้อมูล ซึ่งเป็นสิ่งที่
    ระบบนี้ตั้งใจไม่ทำ หน้าเว็บตรวจความยาวก่อนแสดงอยู่แล้ว บล็อกนั้นจึงไม่ขึ้นเอง
    """
    sent = [c.model_dump() for c in payload.courses]
    matched, unmatched = match_by_title(db, sent)

    if len(matched) < 2:
        names = ", ".join(c["title"] for c in unmatched) or "ที่เลือกมา"
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"ยังไม่มีเอกสารหลักสูตรของสาขา: {names} จึงเปรียบเทียบให้ไม่ได้",
        )

    try:
        result = compare_programs(db, [c.id for _, c in matched])
    except LLMConnectionError as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e) or BUSY) from e

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
    }


@router.post("/recommend-major")
def recommend_major_web(payload: WebRecommendRequest, db: Session = Depends(get_db)) -> dict:
    """
    แนะนำสาขาในรูปแบบที่หน้าเว็บรออยู่

    ชื่อช่องในแบบสอบถามของหน้าเว็บไม่ตรงกับของเรา (skills/goals/track) จึงแปลงก่อน
    """
    a = payload.answers
    # แปลรหัสตัวเลือกเป็นข้อความไทยที่ผู้ใช้เห็นก่อนเสมอ — หน้าเว็บส่งรหัสอย่าง "tech"
    # หรือ "career-growth" มา ซึ่งแทบไม่มีความหมายให้เทียบกับเอกสารภาษาไทย
    # (ดูเหตุผลและตารางใน services/web_compat.py)
    answers = {
        "study_track": label_of("track", a["track"]) if a.get("track") else None,
        # ข้อวิชาที่ชอบส่งเป็นชื่อวิชาภาษาไทยอยู่แล้ว label_of จึงคืนค่าเดิมไป
        "favorite_subjects": labels_of("subjects", a.get("subjects")),
        "interests": labels_of("interests", a.get("interests")),
        "aptitudes": labels_of("skills", a.get("skills")),
        "career_goal": labels_of("goals", a.get("goals")),
        "work_environment": [label_of("environment", a["environment"])] if a.get("environment") else [],
    }

    try:
        matches = match_programs(db, answers, limit=_MATCH_LIMIT)
    except LLMConnectionError as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e) or BUSY) from e

    matched, _ = match_by_title(db, [c.model_dump() for c in payload.courses])
    # เทียบกลับด้วยชื่อ ไม่ใช่รหัสของหลักสูตร เพราะการจัดอันดับมองเอกสารทุกฉบับรวม
    # ฉบับเก่า แต่ตารางจับคู่เก็บเฉพาะฉบับล่าสุด — เทียบด้วยรหัสจะทำให้อันดับที่ชนะ
    # ด้วยเอกสารฉบับเก่าหายไปเงียบๆ
    back = {normalise_title(course.title): item["id"] for item, course in matched}

    ranked: list[tuple[str, object]] = []
    used: set[str] = set()
    for m in matches:
        web_id = back.get(normalise_title(m.title))
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
        return {
            "courseId": web_id,
            "matchScore": m.match_percent,
            "reason": (m.rationale or "").strip() or NO_REASON,
        }

    low = confidence_of(matches) == "low"
    summary = (
        "คะแนนของหลายสาขาใกล้เคียงกันมาก แนะนำให้ดูทุกสาขาที่แสดงประกอบกัน "
        "ไม่ควรยึดอันดับ 1 อย่างเดียว — ผลนี้คำนวณจากเอกสารหลักสูตรจริงของแต่ละสาขา"
        if low else
        "ผลนี้คำนวณจากความใกล้เคียงระหว่างคำตอบของคุณกับเนื้อหาจริงในเอกสารหลักสูตรของแต่ละสาขา"
    )

    return {
        "primary": card(ranked[0]),
        "alternatives": [card(e) for e in ranked[1:1 + _MAX_ALTERNATIVES]],
        "summary": summary,
        # เปิดไว้ให้ตรวจสอบได้ว่าระบบเข้าใจคำตอบของนักเรียนว่าอย่างไร
        "profileText": build_profile_text(answers),
    }
