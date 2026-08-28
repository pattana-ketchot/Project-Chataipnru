"""
POST /match — จับคู่นักเรียนกับสาขาที่เหมาะสมจากคำตอบแบบสอบถาม

ต่างจาก /recommend อย่างไร
-------------------------
/recommend ต้องบันทึกโปรไฟล์ผู้ใช้ลงฐานข้อมูลก่อนแล้วจึงเรียกได้ และให้โมเดลเป็นคน
เลือกหลักสูตรจากผลการค้นหา ซึ่งวัดแล้วพบว่าให้ผลผิด (ดูเหตุผลใน services/program_match.py)

endpoint นี้รับคำตอบแบบสอบถามมาตรงๆ ในคำขอเดียว ไม่ต้องบันทึกโปรไฟล์ก่อน เพื่อให้
หน้าเว็บเรียกดูผลได้ทันทีที่ผู้ใช้ตอบครบ และให้คะแนนทุกหลักสูตรด้วยการคำนวณเวกเตอร์
แทนการให้โมเดลเลือก
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, rate_limiter
from app.db.session import get_db
from app.models.user import User
from app.schemas.match import MatchRequest, MatchResponse, ProgramMatchOut
from app.services.llm_client import get_llm_connector
from app.services.program_match import build_profile_text, match_programs

from llm.connector import LLMConnectionError  # noqa: E402

router = APIRouter(prefix="/match", tags=["match"])
logger = logging.getLogger("course_advisor")


@router.post("", response_model=MatchResponse, dependencies=[Depends(rate_limiter)])
def match(
    payload: MatchRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MatchResponse:
    answers = payload.model_dump(exclude={"limit"})
    try:
        matches = match_programs(db, answers, limit=payload.limit)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    except LLMConnectionError as e:
        # ขั้นตอนเดียวที่ต้องพึ่งโมเดลคือการแปลงโปรไฟล์เป็นเวกเตอร์ ถ้าล้มก็จัดอันดับไม่ได้เลย
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "ระบบวิเคราะห์ยังไม่พร้อมในขณะนี้ กรุณาลองใหม่อีกครั้งครับ",
        ) from e

    return MatchResponse(
        profile_text=build_profile_text(answers),
        model_used=get_llm_connector().chat_model,
        matches=[ProgramMatchOut(**m.__dict__) for m in matches],
    )
