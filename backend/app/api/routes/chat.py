"""
POST /chat — ถาม-ตอบหลายเทิร์นเกี่ยวกับหลักสูตร

ต่างจาก /recommend ที่รับโปรไฟล์แล้วคืนรายการหลักสูตรจัดอันดับแบบครั้งเดียวจบ
endpoint นี้จำบทสนทนาได้และตอบเป็นภาษาคน เหมาะกับการถามต่อเนื่อง

ใช้ rate_limiter เช่นเดียวกับ /recommend เพราะเรียก LLM (หนึ่งเทิร์นอาจเรียกถึง
สองครั้ง: เขียนคำถามใหม่ + ตอบ)
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, rate_limiter
from app.db.session import get_db
from app.models.user import User
from app.schemas.chat import ChatReply, ChatRequest
from app.services.chat import answer_question

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatReply, dependencies=[Depends(rate_limiter)])
def chat(
    payload: ChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatReply:
    try:
        return answer_question(db, user_id=user.id, session_id=payload.session_id, message=payload.message)
    except ValueError as e:
        raise HTTPException(404, str(e))
