"""
POST /recommend — end-to-end RAG: profile+requirements -> vector search ->
Local LLM (Qwen/Llama) -> ranked+explained course list

dependencies=[rate_limiter] เพราะ endpoint นี้แพงที่สุด (เรียก LLM generation)
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, rate_limiter
from app.db.session import get_db
from app.models.user import User
from app.schemas.course import RecommendRequest, RecommendResponse
from app.services.rag import recommend_for_user

router = APIRouter(prefix="/recommend", tags=["recommend"])


@router.post("", response_model=RecommendResponse, dependencies=[Depends(rate_limiter)])
def recommend(
    payload: RecommendRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecommendResponse:
    try:
        return recommend_for_user(
            db,
            user_id=user.id,
            top_k_chunks=payload.top_k_chunks,
            top_n_courses=payload.top_n_courses,
            extra_query=payload.extra_query,
        )
    except ValueError as e:
        raise HTTPException(404, str(e))
