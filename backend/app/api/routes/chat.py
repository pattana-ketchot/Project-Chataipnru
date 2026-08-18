"""
POST /chat — ถาม-ตอบหลายเทิร์นเกี่ยวกับหลักสูตร

ต่างจาก /recommend ที่รับโปรไฟล์แล้วคืนรายการหลักสูตรจัดอันดับแบบครั้งเดียวจบ
endpoint นี้จำบทสนทนาได้และตอบเป็นภาษาคน เหมาะกับการถามต่อเนื่อง

ใช้ rate_limiter เช่นเดียวกับ /recommend เพราะเรียก LLM (หนึ่งเทิร์นอาจเรียกถึง
สองครั้ง: เขียนคำถามใหม่ + ตอบ)
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, rate_limiter
from app.db.session import get_db
from app.models.user import User
from app.schemas.chat import ChatReply, ChatRequest
from app.services.chat import answer_question, stream_answer

from llm.connector import LLMConnectionError  # noqa: E402  (sys.path ตั้งโดย llm_client)

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger("course_advisor")

MODEL_BUSY = (
    "ระบบ AI ยังไม่พร้อมตอบในขณะนี้ (โมเดลกำลังโหลดหรือหน่วยความจำไม่พอ) "
    "กรุณารอสักครู่แล้วลองถามใหม่อีกครั้งครับ"
)


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
            MODEL_BUSY,
        ) from e


@router.post("/stream", dependencies=[Depends(rate_limiter)])
def chat_stream(
    payload: ChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """
    เหมือน POST /chat แต่ทยอยส่งคำตอบทีละส่วนตามรูปแบบ Server-Sent Events

    มีไว้ให้หน้าเว็บใช้ ส่วน POST /chat ยังคงอยู่เพราะชุดประเมินและการทดสอบ
    ต้องการคำตอบทั้งก้อนพร้อมสถานะในครั้งเดียว

    ข้อผิดพลาดที่เกิด "ระหว่าง" สตรีมส่งเป็น HTTP status ไม่ได้แล้ว เพราะหัวข้อความ
    ถูกส่งออกไปตั้งแต่ตัวอักษรแรก จึงต้องส่งเป็นเหตุการณ์ error ให้หน้าเว็บอ่านแทน
    """

    def events():
        try:
            yield from stream_answer(db, user_id=user.id, session_id=payload.session_id, message=payload.message)
        except ValueError as e:
            yield f'event: error\ndata: {{"detail": "{e}"}}\n\n'
        except LLMConnectionError:
            yield f'event: error\ndata: {{"detail": "{MODEL_BUSY}"}}\n\n'
        except Exception:
            # ต้องจับให้หมด ไม่ปล่อยให้ข้อยกเว้นหลุดออกจาก generator เพราะหัวข้อความ
            # ถูกส่งไปแล้ว การโยนต่อจะทำให้การเชื่อมต่อค้างจนหน้าเว็บรอไม่จบ
            # แทนที่จะเห็นข้อความบอกว่าเกิดอะไรขึ้น
            logger.exception("chat stream ล้มกลางคัน")
            yield 'event: error\ndata: {"detail": "ระบบขัดข้องระหว่างเรียบเรียงคำตอบ กรุณาลองใหม่อีกครั้งครับ"}\n\n'

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        # กัน proxy ที่อยู่ระหว่างทางเก็บคำตอบไว้จนครบก้อนแล้วค่อยส่ง ซึ่งจะทำให้
        # การทยอยส่งไม่มีผลอะไรเลย ผู้ใช้ยังคงเห็นหน้าจอว่างจนกว่าจะเขียนเสร็จ
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
