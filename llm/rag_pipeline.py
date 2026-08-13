"""
RAG orchestration ที่ไม่ผูกกับ DB/FastAPI โดยตรง — รับข้อมูลที่ retrieve มาแล้ว
(list of dict) เข้ามา ประกอบ prompt แล้วเรียก connector เพื่อสร้างคำแนะนำ

การไม่ import SQLAlchemy models ที่นี่ตั้งใจให้ package `llm/` reuse ได้จากที่อื่น
นอก backend ด้วย (batch job, notebook, CLI อื่นๆ)
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from llm.connector import ChatMessage, LLMConnectionError, OllamaConnector
from llm.prompts import SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger("llm.rag_pipeline")


@dataclass
class RecommendationItem:
    course_id: str
    score: float
    rationale: str
    cited_chunk_ids: list[str]


@dataclass
class RecommendationResult:
    items: list[RecommendationItem]
    raw_response: str


def _format_profile(profile) -> str:  # profile: UserProfile ORM obj หรือ None
    if profile is None:
        return "(ไม่มีข้อมูล profile)"
    lines = [
        f"ระดับการศึกษา: {profile.education_level or '-'}",
        f"สาขา: {profile.field_of_study or '-'}",
        f"เป้าหมายอาชีพ: {profile.career_goal or '-'}",
        f"ทักษะ: {', '.join(profile.skills or []) or '-'}",
        f"ความสนใจ: {', '.join(profile.interests or []) or '-'}",
    ]
    return "\n".join(lines)


def _format_requirements(requirements: list[dict]) -> str:
    if not requirements:
        return "(ไม่มีการระบุเงื่อนไขเพิ่มเติม)"
    sorted_reqs = sorted(requirements, key=lambda r: -r["priority"])
    return "\n".join(f"- [{r['priority']}/5] {r['type']}: {r['value']}" for r in sorted_reqs)


def _format_chunks(chunks: list[dict]) -> str:
    # แต่ละ chunk มาจาก SearchResultChunk.model_dump(): chunk_id, course_id,
    # course_title, page_number, content, score
    blocks = []
    for c in chunks:
        blocks.append(
            f"[course_id={c['course_id']} | chunk_id={c['chunk_id']} | "
            f"course=\"{c['course_title']}\" | page={c.get('page_number', '-')}]\n{c['content']}"
        )
    return "\n\n".join(blocks) if blocks else "(ไม่พบเนื้อหาหลักสูตรที่เกี่ยวข้อง)"


def generate_recommendations(
    connector: OllamaConnector,
    profile,
    requirements: list[dict],
    retrieved_chunks: list[dict],
    extra_query: str | None,
    top_n: int = 5,
) -> RecommendationResult:
    user_prompt = build_user_prompt(
        profile_text=_format_profile(profile),
        requirements_text=_format_requirements(requirements),
        course_content_block=_format_chunks(retrieved_chunks),
        extra_query=extra_query,
        top_n=top_n,
    )

    messages = [
        ChatMessage(role="system", content=SYSTEM_PROMPT),
        ChatMessage(role="user", content=user_prompt),
    ]

    raw = connector.chat(messages, temperature=0.2, json_mode=True)

    try:
        parsed = json.loads(raw)
        raw_items = parsed.get("items", [])
    except (json.JSONDecodeError, AttributeError) as e:
        logger.error("LLM ตอบ JSON ไม่ถูกต้อง: %s", e)
        raise LLMConnectionError("model returned malformed JSON") from e

    # valid course_id ต้องอยู่ใน chunk ที่ retrieve มาเท่านั้น (กัน hallucinated id
    # และกัน prompt injection ที่พยายามให้โมเดลแนะนำ course_id ที่ไม่ได้ retrieve)
    # เทียบกันเป็น str เสมอ เพราะ retrieved_chunks มาจาก model_dump() (uuid.UUID
    # objects) ส่วนค่าที่โมเดลตอบกลับมาเป็น string จาก JSON
    allowed_course_ids = {str(c["course_id"]) for c in retrieved_chunks}
    allowed_chunk_ids = {str(c["chunk_id"]) for c in retrieved_chunks}

    items: list[RecommendationItem] = []
    for it in raw_items[:top_n]:
        cid = str(it.get("course_id", ""))
        if cid not in allowed_course_ids:
            logger.warning("dropping hallucinated course_id from LLM output: %r", cid)
            continue
        cited = [str(c) for c in it.get("cited_chunk_ids", []) if str(c) in allowed_chunk_ids]
        try:
            score = max(0.0, min(1.0, float(it.get("score", 0.0))))
        except (TypeError, ValueError):
            score = 0.0
        items.append(
            RecommendationItem(
                course_id=cid,
                score=score,
                rationale=str(it.get("rationale", ""))[:2000],
                cited_chunk_ids=cited,
            )
        )

    return RecommendationResult(items=items, raw_response=raw)
