import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CourseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str | None
    title: str
    provider: str | None
    summary: str | None
    mode: str | None
    duration_weeks: float | None
    price: float | None
    currency: str
    tags: list[str]


class SearchQuery(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=8, ge=1, le=50)


class SearchResultChunk(BaseModel):
    chunk_id: uuid.UUID
    course_id: uuid.UUID
    course_title: str
    page_number: int | None
    content: str
    score: float  # similarity (1 - cosine distance)


class RecommendRequest(BaseModel):
    top_k_chunks: int = Field(default=12, ge=1, le=50)
    top_n_courses: int = Field(default=5, ge=1, le=20)
    extra_query: str | None = Field(default=None, max_length=1000)  # ข้อความเพิ่มเติมจากผู้ใช้ ณ ตอนถาม


class RecommendedCourse(BaseModel):
    course: CourseOut
    score: float
    rationale: str
    cited_chunk_ids: list[uuid.UUID]


class RecommendResponse(BaseModel):
    session_id: uuid.UUID
    model_used: str
    generated_at: datetime
    recommendations: list[RecommendedCourse]
