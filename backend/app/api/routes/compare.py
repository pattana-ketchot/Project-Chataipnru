"""
POST /compare — ตารางเปรียบเทียบหลักสูตร 2-4 สาขา

ทุกช่องในตารางมาจากเอกสาร มคอ.2 ของหลักสูตรนั้นโดยตรง ไม่ใช่ความรู้ทั่วไปของโมเดล
เหตุผลอยู่ในหมายเหตุของ services/program_compare.py
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, rate_limiter
from app.db.session import get_db
from app.models.user import User
from app.schemas.compare import CompareRequest, CompareResponse
from app.services.program_compare import compare_programs

from llm.connector import LLMConnectionError  # noqa: E402

router = APIRouter(prefix="/compare", tags=["compare"])


@router.post("", response_model=CompareResponse, dependencies=[Depends(rate_limiter)])
def compare(
    payload: CompareRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CompareResponse:
    try:
        return CompareResponse(**compare_programs(db, payload.course_ids))
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    except LLMConnectionError as e:
        # การค้นเนื้อหาต้องใช้โมเดลแปลงข้อความเป็นเวกเตอร์ ถ้าล้มก็หาเนื้อหามาเทียบไม่ได้เลย
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "ระบบวิเคราะห์ยังไม่พร้อมในขณะนี้ กรุณาลองใหม่อีกครั้งครับ",
        ) from e
