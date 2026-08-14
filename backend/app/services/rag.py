"""
RAG orchestration สำหรับ /recommend:
  1. โหลด user_profile + user_requirements จาก DB
  2. ประกอบเป็น query text -> embed -> vector_search (course_chunks)
  3. ส่ง (profile, requirements, retrieved chunks) ไปยัง llm/rag_pipeline
     เพื่อสร้างคำแนะนำแบบมีเหตุผลอ้างอิง
  4. map ผลลัพธ์กลับเป็น Course rows + บันทึกลง `recommendations` (audit)
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chat import ChatSession, Recommendation
from app.models.course import Course
from app.models.user import User, UserRequirement
from app.schemas.course import RecommendedCourse, RecommendResponse
from app.services.llm_client import get_llm_connector
from app.services.vector_search import search_similar_chunks

from llm.rag_pipeline import generate_recommendations  # noqa: E402  (path set up by llm_client)


def _build_query_text(user: User, requirements: list[UserRequirement], extra_query: str | None) -> str:
    profile = user.profile
    parts: list[str] = []
    if profile:
        if profile.field_of_study:
            parts.append(f"สาขา: {profile.field_of_study}")
        if profile.career_goal:
            parts.append(f"เป้าหมายอาชีพ: {profile.career_goal}")
        if profile.interests:
            parts.append("ความสนใจ: " + ", ".join(profile.interests))
        if profile.skills:
            parts.append("ทักษะปัจจุบัน: " + ", ".join(profile.skills))
    for req in requirements:
        parts.append(f"{req.req_type}: {req.req_value}")
    if extra_query:
        parts.append(extra_query)
    return " | ".join(parts) or "หลักสูตรทั่วไป"


def recommend_for_user(
    db: Session,
    user_id: uuid.UUID,
    top_k_chunks: int,
    top_n_courses: int,
    extra_query: str | None,
) -> RecommendResponse:
    user = db.get(User, user_id)
    if user is None:
        raise ValueError("user not found")

    requirements = db.scalars(select(UserRequirement).where(UserRequirement.user_id == user_id)).all()
    query_text = _build_query_text(user, requirements, extra_query)

    connector = get_llm_connector()
    query_embedding = connector.embed(query_text)

    retrieved = search_similar_chunks(db, query_embedding, top_k=top_k_chunks)

    session = ChatSession(user_id=user_id)
    db.add(session)
    db.flush()  # get session.id without committing yet

    llm_result = generate_recommendations(
        connector=connector,
        profile=user.profile,
        requirements=[{"type": r.req_type, "value": r.req_value, "priority": r.priority} for r in requirements],
        retrieved_chunks=[c.model_dump() for c in retrieved],
        extra_query=extra_query,
        top_n=top_n_courses,
    )

    out: list[RecommendedCourse] = []
    seen_course_ids: set[uuid.UUID] = set()
    for item in llm_result.items:
        try:
            course = db.get(Course, uuid.UUID(item.course_id))
        except ValueError:
            continue  # ค่าที่ไม่ใช่ UUID ที่ถูกต้อง -> ทิ้งอย่างเงียบๆ (ไม่ trust LLM output ตรงๆ)
        if course is None:
            continue  # LLM อาจ hallucinate id ที่ไม่มีจริง -> ทิ้งอย่างเงียบๆ (ไม่ trust LLM output ตรงๆ)

        if course.id in seen_course_ids:
            # โมเดลมักแนะนำหลักสูตรเดิมซ้ำหลายอันดับเมื่อ chunk ที่ retrieve มา
            # หลายก้อนมาจากหลักสูตรเดียวกัน — เก็บเฉพาะอันดับแรก (คะแนนสูงสุด
            # เพราะ prompt สั่งให้เรียงจากมากไปน้อยอยู่แล้ว) ไม่งั้นผู้ใช้จะเห็น
            # หลักสูตรเดียวกันโผล่ซ้ำในรายการแนะนำ
            continue
        seen_course_ids.add(course.id)

        cited_uuids = [uuid.UUID(c) for c in item.cited_chunk_ids]
        rec = Recommendation(
            user_id=user_id,
            course_id=course.id,
            session_id=session.id,
            score=item.score,
            rationale=item.rationale,
            retrieved_chunk_ids=cited_uuids,
            model_used=connector.chat_model,
        )
        db.add(rec)
        out.append(
            RecommendedCourse(
                course=course,  # pydantic from_attributes
                score=item.score,
                rationale=item.rationale,
                cited_chunk_ids=item.cited_chunk_ids,
            )
        )

    db.commit()

    return RecommendResponse(
        session_id=session.id,
        model_used=connector.chat_model,
        generated_at=datetime.now(timezone.utc),
        recommendations=out,
    )
