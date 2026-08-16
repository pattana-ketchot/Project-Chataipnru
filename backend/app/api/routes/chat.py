"""
POST /chat — ถาม-ตอบหลายเทิร์นเกี่ยวกับหลักสูตร

ต่างจาก /recommend ที่รับโปรไฟล์แล้วคืนรายการหลักสูตรจัดอันดับแบบครั้งเดียวจบ
endpoint นี้จำบทสนทนาได้และตอบเป็นภาษาคน เหมาะกับการถามต่อเนื่อง

ใช้ rate_limiter เช่นเดียวกับ /recommend เพราะเรียก LLM (หนึ่งเทิร์นอาจเรียกถึง
สองครั้ง: เขียนคำถามใหม่ + ตอบ)
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, rate_limiter
from app.db.session import get_db
from app.models.user import User
from app.schemas.chat import ChatReply, ChatRequest
from app.services.chat import answer_question

from llm.connector import LLMConnectionError  # noqa: E402  (sys.path ตั้งโดย llm_client)

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
    except LLMConnectionError as e:
        # แยกจาก 500 ทั่วไป เพื่อให้หน้าเว็บบอกผู้ใช้ได้ตรงว่าเกิดอะไรขึ้น
        # แทนข้อความ "เกิดข้อผิดพลาด" ที่ไม่ช่วยให้ตัดสินใจว่าควรลองใหม่ไหม
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "ระบบ AI ยังไม่พร้อมตอบในขณะนี้ (โมเดลกำลังโหลดหรือหน่วยความจำไม่พอ) "
            "กรุณารอสักครู่แล้วลองถามใหม่อีกครั้งครับ",
        ) from e
