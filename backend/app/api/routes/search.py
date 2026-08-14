"""
GET/POST /search — item 2 ของ requirement: "ดึงข้อมูลจาก Vector Database"
เปิดสำหรับ authenticated user เท่านั้น (ป้องกันคนนอกยิง embedding model รัวๆ
เป็นการโจมตี resource-exhaustion ต่อ local LLM)
"""
from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, rate_limiter
from app.db.session import get_db
from app.schemas.course import SearchQuery, SearchResultChunk
from app.services.llm_client import get_llm_connector
from app.services.query_expansion import expand_query
from app.services.vector_search import search_similar_chunks
from sqlalchemy.orm import Session

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=list[SearchResultChunk], dependencies=[Depends(rate_limiter)])
def search_courses(
    payload: SearchQuery,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
) -> list[SearchResultChunk]:
    connector = get_llm_connector()
    query_embedding = connector.embed(expand_query(payload.query))
    return search_similar_chunks(db, query_embedding, top_k=payload.top_k)
