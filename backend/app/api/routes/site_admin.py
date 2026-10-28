"""
จัดการเนื้อหาหน้าเว็บสำหรับผู้ดูแล — Phase 4 (มาแทนการที่หน้าผู้ดูแลเขียน Supabase ตรง)

    GET/POST/PUT/DELETE  /site-admin/courses[/{id}]
    GET/POST/PUT/DELETE  /site-admin/news[/{id}]
    GET/POST/PUT/DELETE  /site-admin/knowledge[/{id}]
    GET/PUT              /site-admin/ai-settings
    POST                 /site-admin/ai-settings/check
    GET                  /site-admin/users
    PUT                  /site-admin/users/{id}/role|status

ด่านสิทธิ์
----------
อ่านและเขียน  `require_staff`      — admin หรือ editor ที่อนุมัติแล้ว
ลบ            `require_admin_role` — admin เท่านั้น

ตรงกับที่หน้าเว็บซ่อนปุ่มลบจาก editor **แต่การซ่อนปุ่มไม่ใช่ด่าน** ด่านจริงอยู่ที่นี่

ร่างต้องไม่หลุดสาธารณะ
---------------------
เส้นทางในไฟล์นี้เห็นทุกแถวรวมร่าง เพราะผู้ดูแลต้องแก้ร่างได้
เส้นทางสาธารณะอยู่คนละไฟล์ (`site.py`) และกรอง `is_published` / `status='published'` เสมอ
การแยกไฟล์ทำให้ไม่มีทางเผลอเปิดร่างให้คนทั่วไปด้วยการแก้ query ผิดที่
"""
import logging
import os
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import require_admin_role, require_staff
from app.core.config import get_settings
from app.db.session import get_db
from app.models.user import User
from app.services import ai_settings, llm_client

router = APIRouter(prefix="/site-admin", tags=["site-admin"])
logger = logging.getLogger("course_advisor")


def _uuid_or_404(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบรายการนี้") from None


def _rows(db: Session, sql: str, params: dict | None = None) -> list[dict]:
    return [dict(r) for r in db.execute(text(sql), params or {}).mappings().all()]


def _one(db: Session, sql: str, params: dict) -> dict:
    row = db.execute(text(sql), params).mappings().first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบรายการนี้")
    return dict(row)


# ── หลักสูตร ─────────────────────────────────────────────────────────

class CourseIn(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    title_en: str | None = Field(default=None, max_length=255)
    description: str | None = None
    logo_url: str | None = None
    careers: list[str] = Field(default_factory=list)
    detail: Any = None
    is_published: bool = True
    # เชื่อมกับหลักสูตรจริงใน public.courses — ผู้ดูแลตั้งเองได้ถ้ารู้
    course_id: str | None = None


_COURSE_COLS = ("id, course_id, title, title_en, description, logo_url, careers, detail,"
                " is_published, created_at, updated_at")


@router.get("/courses")
def list_courses(_s: User = Depends(require_staff), db: Session = Depends(get_db)) -> dict:
    """เห็นทุกแถวรวมที่ยังไม่เผยแพร่ — ต่างจากเส้นทางสาธารณะโดยตั้งใจ"""
    return {"courses": _rows(db, f"select {_COURSE_COLS} from web.site_courses order by title")}


@router.get("/courses/{item_id}")
def get_course(item_id: str, _s: User = Depends(require_staff),
               db: Session = Depends(get_db)) -> dict:
    return _one(db, f"select {_COURSE_COLS} from web.site_courses where id = :id",
                {"id": str(_uuid_or_404(item_id))})


@router.post("/courses", status_code=status.HTTP_201_CREATED)
def create_course(payload: CourseIn, staff: User = Depends(require_staff),
                  db: Session = Depends(get_db)) -> dict:
    row = db.execute(
        text(f"""insert into web.site_courses
                 (course_id, title, title_en, description, logo_url, careers, detail,
                  is_published, created_by, updated_by)
                 values (:course_id, :title, :title_en, :description, :logo_url, :careers,
                         cast(:detail as jsonb), :is_published, :who, :who)
                 returning {_COURSE_COLS}"""),
        _course_params(payload, staff),
    ).mappings().first()
    db.commit()
    return dict(row)


@router.put("/courses/{item_id}")
def update_course(item_id: str, payload: CourseIn, staff: User = Depends(require_staff),
                  db: Session = Depends(get_db)) -> dict:
    params = _course_params(payload, staff)
    params["id"] = str(_uuid_or_404(item_id))
    row = db.execute(
        text(f"""update web.site_courses set
                   course_id = :course_id, title = :title, title_en = :title_en,
                   description = :description, logo_url = :logo_url, careers = :careers,
                   detail = cast(:detail as jsonb), is_published = :is_published,
                   updated_by = :who, updated_at = now()
                 where id = :id returning {_COURSE_COLS}"""),
        params,
    ).mappings().first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบรายการนี้")
    db.commit()
    return dict(row)


@router.delete("/courses/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_course(item_id: str, _a: User = Depends(require_admin_role),
                  db: Session = Depends(get_db)) -> None:
    _delete(db, "web.site_courses", item_id)


def _course_params(payload: CourseIn, staff: User) -> dict:
    import json
    return {
        "course_id": str(uuid.UUID(payload.course_id)) if payload.course_id else None,
        "title": payload.title,
        "title_en": payload.title_en,
        "description": payload.description,
        "logo_url": payload.logo_url,
        "careers": payload.careers,
        "detail": json.dumps(payload.detail, ensure_ascii=False) if payload.detail is not None else None,
        "is_published": payload.is_published,
        "who": str(staff.id),
    }


# ── ข่าวของคณะ ───────────────────────────────────────────────────────

class NewsIn(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    category: str | None = Field(default=None, max_length=100)
    published_on: str | None = None
    image_url: str | None = None
    # ฐานข้อมูลมี CHECK อยู่แล้ว ตรวจที่นี่ด้วยเพื่อให้ได้ 422 ที่อ่านรู้เรื่องแทน 500
    status: str = Field(default="published", pattern="^(published|draft|archived)$")


_NEWS_COLS = ("id, title, description, category, published_on, image_url, status,"
              " created_at, updated_at")


@router.get("/news")
def list_news(_s: User = Depends(require_staff), db: Session = Depends(get_db)) -> dict:
    return {"news": _rows(db, f"select {_NEWS_COLS} from web.news order by created_at desc")}


@router.get("/news/{item_id}")
def get_news(item_id: str, _s: User = Depends(require_staff),
             db: Session = Depends(get_db)) -> dict:
    return _one(db, f"select {_NEWS_COLS} from web.news where id = :id",
                {"id": str(_uuid_or_404(item_id))})


@router.post("/news", status_code=status.HTTP_201_CREATED)
def create_news(payload: NewsIn, staff: User = Depends(require_staff),
                db: Session = Depends(get_db)) -> dict:
    row = db.execute(
        text(f"""insert into web.news
                 (title, description, category, published_on, image_url, status,
                  created_by, updated_by)
                 values (:title, :description, :category, cast(:published_on as date),
                         :image_url, :status, :who, :who)
                 returning {_NEWS_COLS}"""),
        {**payload.model_dump(), "who": str(staff.id)},
    ).mappings().first()
    db.commit()
    return dict(row)


@router.put("/news/{item_id}")
def update_news(item_id: str, payload: NewsIn, staff: User = Depends(require_staff),
                db: Session = Depends(get_db)) -> dict:
    row = db.execute(
        text(f"""update web.news set
                   title = :title, description = :description, category = :category,
                   published_on = cast(:published_on as date), image_url = :image_url,
                   status = :status, updated_by = :who, updated_at = now()
                 where id = :id returning {_NEWS_COLS}"""),
        {**payload.model_dump(), "who": str(staff.id), "id": str(_uuid_or_404(item_id))},
    ).mappings().first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบรายการนี้")
    db.commit()
    return dict(row)


@router.delete("/news/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_news(item_id: str, _a: User = Depends(require_admin_role),
                db: Session = Depends(get_db)) -> None:
    _delete(db, "web.news", item_id)


# ── คลังความรู้ ──────────────────────────────────────────────────────

class KnowledgeIn(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    content: str | None = None
    file_path: str | None = None
    file_name: str | None = None
    file_size: int | None = Field(default=None, ge=0)


_KNOWLEDGE_COLS = "id, title, content, file_path, file_name, file_size, created_at, updated_at"


@router.get("/knowledge")
def list_knowledge(_s: User = Depends(require_staff), db: Session = Depends(get_db)) -> dict:
    return {"articles": _rows(
        db, f"select {_KNOWLEDGE_COLS} from web.knowledge_articles order by created_at desc")}


@router.get("/knowledge/{item_id}")
def get_knowledge(item_id: str, _s: User = Depends(require_staff),
                  db: Session = Depends(get_db)) -> dict:
    return _one(db, f"select {_KNOWLEDGE_COLS} from web.knowledge_articles where id = :id",
                {"id": str(_uuid_or_404(item_id))})


@router.post("/knowledge", status_code=status.HTTP_201_CREATED)
def create_knowledge(payload: KnowledgeIn, staff: User = Depends(require_staff),
                     db: Session = Depends(get_db)) -> dict:
    row = db.execute(
        text(f"""insert into web.knowledge_articles
                 (title, content, file_path, file_name, file_size, created_by, updated_by)
                 values (:title, :content, :file_path, :file_name, :file_size, :who, :who)
                 returning {_KNOWLEDGE_COLS}"""),
        {**payload.model_dump(), "who": str(staff.id)},
    ).mappings().first()
    db.commit()
    return dict(row)


@router.put("/knowledge/{item_id}")
def update_knowledge(item_id: str, payload: KnowledgeIn, staff: User = Depends(require_staff),
                     db: Session = Depends(get_db)) -> dict:
    row = db.execute(
        text(f"""update web.knowledge_articles set
                   title = :title, content = :content, file_path = :file_path,
                   file_name = :file_name, file_size = :file_size,
                   updated_by = :who, updated_at = now()
                 where id = :id returning {_KNOWLEDGE_COLS}"""),
        {**payload.model_dump(), "who": str(staff.id), "id": str(_uuid_or_404(item_id))},
    ).mappings().first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบรายการนี้")
    db.commit()
    return dict(row)


@router.delete("/knowledge/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_knowledge(item_id: str, _a: User = Depends(require_admin_role),
                     db: Session = Depends(get_db)) -> None:
    _delete(db, "web.knowledge_articles", item_id)


# ── ตั้งค่า AI ───────────────────────────────────────────────────────

class AiSettingsIn(BaseModel):
    """
    ค่าที่หน้าผู้ดูแลส่งมาได้ — มีแค่ "เลือกเจ้าไหน" กับ "รุ่นชื่ออะไร"

    ไม่มีช่องสำหรับ API key หรือ base URL โดยเจตนา สองอย่างนั้นอยู่ที่ environment
    ของเซิร์ฟเวอร์เท่านั้น ถ้าเก็บลงตารางนี้ คีย์จะไหลออกทาง GET ของเส้นทางนี้
    ไปอยู่ในเบราว์เซอร์ของทุกคนที่เป็น staff และอยู่ใน log ของ proxy ทุกชั้นที่ผ่าน
    """

    # None = ล้างค่าที่เลือกไว้ กลับไปใช้ค่าจาก environment
    provider: str | None = Field(default=None, pattern="^(gemini|ollama)$")
    # None หรือค่าว่าง = ใช้รุ่นตั้งต้นของผู้ให้บริการนั้นจาก environment
    model: str | None = Field(default=None, max_length=255)


def _ai_settings_view(db: Session) -> dict:
    """
    สภาพปัจจุบันของสวิตช์ — แยก "ที่บันทึกไว้" ออกจาก "ที่ใช้จริง" ให้เห็นทั้งคู่

    ต้องแยก เพราะสองค่านี้ต่างกันได้จริง เช่นเลือก Gemini ไว้แต่เซิร์ฟเวอร์ไม่มีคีย์
    หน้าเว็บที่แสดงแต่ค่าที่บันทึกจะบอกว่าใช้ Gemini ทั้งที่คำตอบทุกข้อมาจากโมเดล
    ในเครื่อง — ซึ่งเป็นอาการเดียวกับที่ทำให้สวิตช์นี้ดูเหมือนทำงานมาตลอด

    ตั้งใจไม่คืนค่าคีย์ คืนแค่ว่ามีคีย์อยู่หรือไม่
    """
    choice = ai_settings.resolve(db)
    row = db.execute(
        text("select updated_at from web.ai_settings where id = 1")
    ).mappings().first()
    env = ai_settings.env_default()
    return {
        "saved": {
            "provider": choice.saved_provider,
            "model": choice.saved_model,
            "updated_at": (dict(row).get("updated_at") if row else None),
        },
        "effective": {
            "provider": choice.provider,
            "model": choice.model,
            "source": choice.source,
            "honoured": choice.honoured,
            "note": choice.note,
        },
        "defaults": {
            "provider": env.provider,
            "model": env.model,
            "gemini_model": ai_settings.default_model_of("gemini"),
            "ollama_model": ai_settings.default_model_of("ollama"),
            "has_gemini_key": ai_settings.has_gemini_key(),
        },
        # สวิตช์นี้ไม่แตะฝั่ง embedding — แสดงไว้ให้เห็นว่าเวกเตอร์ไม่ถูกสร้างใหม่
        "embedding": {"model": get_settings().embed_model, "changeable": False},
        "providers": list(ai_settings.PROVIDERS),
    }


@router.get("/ai-settings")
def get_ai_settings(_s: User = Depends(require_staff), db: Session = Depends(get_db)) -> dict:
    return _ai_settings_view(db)


@router.put("/ai-settings")
def update_ai_settings(payload: AiSettingsIn, staff: User = Depends(require_staff),
                       db: Session = Depends(get_db)) -> dict:
    """
    บันทึกตัวเลือก แล้วทิ้งแคชให้คำขอถัดไปเห็นค่าใหม่ทันทีโดยไม่ต้อง restart

    ตารางนี้มีแถวเดียวโดยบังคับด้วย CHECK (id = 1) จึงเขียนแบบ upsert

    คืนสภาพที่ใช้จริงกลับไปด้วย ไม่ใช่คืนแค่ค่าที่เพิ่งเขียน เพราะ "เขียนสำเร็จ"
    ไม่ได้แปลว่าค่านั้นถูกนำไปใช้ — หน้าเว็บต้องมีข้อมูลพอจะบอกผู้ใช้ตามจริง
    """
    model = (payload.model or "").strip() or None
    db.execute(
        text("""insert into web.ai_settings (id, provider, model, updated_by)
                values (1, :provider, :model, :who)
                on conflict (id) do update set
                  provider = excluded.provider, model = excluded.model,
                  updated_by = excluded.updated_by, updated_at = now()"""),
        {"provider": payload.provider, "model": model, "who": str(staff.id)},
    )
    db.commit()
    ai_settings.invalidate()
    view = _ai_settings_view(db)
    logger.info("ผู้ดูแล %s ตั้งโมเดลคำตอบเป็น %s/%s — ที่ใช้จริง %s/%s",
                staff.id, payload.provider, model,
                view["effective"]["provider"], view["effective"]["model"])
    return view


# จำนวนชิ้นเนื้อหาที่คำถามจริงหนึ่งข้อส่งเข้าโมเดล — ต้องเท่ากับที่ขั้นตอบใช้
# ไม่งั้นการตรวจจะวัดงานที่เบากว่าของจริง แล้วรายงานว่าไหวทั้งที่ไม่ไหว
_PROBE_CHUNKS = int(os.getenv("CHAT_TOP_K", "8"))


@router.post("/ai-settings/check")
def check_ai_settings(_s: User = Depends(require_staff), db: Session = Depends(get_db)) -> dict:
    """
    ยิงคำขอจริงไปที่ผู้ให้บริการที่ใช้อยู่ แล้วบอกผลตามที่เกิดขึ้น

    แยกออกจาก GET เพราะการตรวจมีค่าใช้จ่าย (กินโควตาของผู้ให้บริการ และใช้เวลา
    ได้หลายสิบวินาที) การเปิดหน้าเว็บเฉย ๆ ไม่ควรจุดชนวนมันทุกครั้ง

    ส่งเนื้อหาจริงจากคลังเอกสารเข้าไปเท่าจำนวนชิ้นที่คำถามหนึ่งข้อใช้ เพื่อให้ขั้น
    "ตอบทันเพดานเวลาไหม" วัดงานขนาดเท่าของจริง ไม่ใช่พรอมต์สั้นที่ใครก็ผ่าน

    ผลจากที่นี่คือสิ่งเดียวที่ยืนยันว่าใช้งานได้ การบันทึกสำเร็จไม่ยืนยันอะไรเลย
    """
    sample = [r["content"] for r in db.execute(
        text("select content from public.course_chunks "
             "where content is not null and length(content) > 200 "
             "order by id limit :n"),
        {"n": _PROBE_CHUNKS},
    ).mappings()]
    view = _ai_settings_view(db)
    view["check"] = llm_client.probe(ai_settings.resolve(db), sample)
    view["check"]["sample_chars"] = sum(len(c) for c in sample)
    return view


# ── ผู้ใช้และสิทธิ์ ───────────────────────────────────────────────────

class RoleIn(BaseModel):
    role: str = Field(pattern="^(admin|editor|user)$")


class StatusIn(BaseModel):
    status: str = Field(pattern="^(pending|approved|rejected)$")


@router.get("/users")
def list_users(_a: User = Depends(require_admin_role), db: Session = Depends(get_db)) -> dict:
    """เฉพาะ admin — รายชื่อผู้ใช้เป็นข้อมูลส่วนบุคคล editor ไม่ควรเห็นทั้งหมด"""
    return {"users": _rows(db, """
        select id, email, full_name, role, status, is_active,
               email_verified_at, last_login_at, created_at
          from public.users order by created_at desc""")}


@router.put("/users/{user_id}/role")
def set_role(user_id: str, payload: RoleIn, admin: User = Depends(require_admin_role),
             db: Session = Depends(get_db)) -> dict:
    """
    เปลี่ยนสิทธิ์ — **ลดสิทธิ์ตัวเองไม่ได้**

    กันกรณีผู้ดูแลคนสุดท้ายเผลอลดสิทธิ์ตัวเองแล้วไม่มีใครเข้าหน้าผู้ดูแลได้อีกเลย
    """
    target = str(_uuid_or_404(user_id))
    if target == str(admin.id) and payload.role != "admin":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "ลดสิทธิ์ของตัวเองไม่ได้")
    return _update_user(db, target, "role", payload.role)


@router.put("/users/{user_id}/status")
def set_status(user_id: str, payload: StatusIn, admin: User = Depends(require_admin_role),
               db: Session = Depends(get_db)) -> dict:
    target = str(_uuid_or_404(user_id))
    if target == str(admin.id) and payload.status != "approved":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "ถอนการอนุมัติของตัวเองไม่ได้")
    result = _update_user(db, target, "status", payload.status)
    if payload.status != "approved":
        # ถูกถอนอนุมัติแล้วต้องออกจากระบบทันที ไม่ใช่รอจนกว่า token จะหมดอายุ
        db.execute(
            text("update public.auth_sessions set revoked_at = now()"
                 " where user_id = :u and revoked_at is null"),
            {"u": target},
        )
        db.commit()
    return result


def _update_user(db: Session, user_id: str, column: str, value: str) -> dict:
    # ชื่อคอลัมน์มาจากรายการปิดในโค้ดนี้เท่านั้น ไม่เคยมาจากผู้ใช้
    assert column in ("role", "status")
    row = db.execute(
        text(f"update public.users set {column} = :v, updated_at = now()"
             " where id = :id returning id, email, role, status"),
        {"v": value, "id": user_id},
    ).mappings().first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบผู้ใช้นี้")
    db.commit()
    return dict(row)


def _delete(db: Session, table: str, item_id: str) -> None:
    # ชื่อตารางมาจากผู้เรียกในไฟล์นี้เท่านั้น ไม่เคยมาจากผู้ใช้
    assert table in ("web.site_courses", "web.news", "web.knowledge_articles")
    result = db.execute(text(f"delete from {table} where id = :id"),
                        {"id": str(_uuid_or_404(item_id))})
    if (result.rowcount or 0) == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบรายการนี้")
    db.commit()


@router.post("/sync-news")
def sync_news(_s: User = Depends(require_staff), db: Session = Depends(get_db)) -> dict:
    """
    สั่งดึงข่าว SCI Connect ทันที — มาแทนปุ่มที่เคยเรียก Edge Function ของ Supabase

    ตรรกะเดียวกับงานตั้งเวลาทุกข้อ รวมถึงกฎที่ว่า **ตัดข่าวเก่าทิ้งเฉพาะเมื่อเพิ่มของใหม่ได้จริง**
    (ดู pipeline/web/sync_sci_news.py) จึงไม่มีทางที่การกดปุ่มตอนเว็บต้นทางล่มจะลบข่าวทิ้ง

    ต้องเป็นผู้ดูแลที่อนุมัติแล้ว — เงื่อนไขเดียวกับที่ C2 บังคับไว้กับ Edge Function
    """
    from app.services.sci_news import (KEEP_LATEST, SOURCE_URL, detail_url_for, extract_slug,
                                       fetch_url, parse_detail_page, parse_news_cards,
                                       row_for, should_prune)

    html = fetch_url(SOURCE_URL)
    if html is None:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "ดึงหน้าเว็บต้นทางไม่สำเร็จ")

    parsed = [c for c in parse_news_cards(html) if c.detail_url]
    if not parsed:
        # โครงหน้าเว็บต้นทางอาจเปลี่ยน — หยุดโดยไม่ลบอะไร
        raise HTTPException(status.HTTP_502_BAD_GATEWAY,
                            "ไม่พบข่าวในหน้าเว็บต้นทาง (โครงหน้าเว็บอาจเปลี่ยน)")

    urls = [c.detail_url for c in parsed]
    existing = {r["detail_url"] for r in db.execute(
        text("select detail_url from web.external_news where detail_url = any(:urls)"),
        {"urls": urls},
    ).mappings().all()}

    inserted = 0
    for card in [c for c in parsed if c.detail_url not in existing]:
        slug = extract_slug(card.detail_url or "")
        description, facebook_url = (None, None)
        if slug:
            detail_html = fetch_url(detail_url_for(slug))
            if detail_html:
                description, facebook_url = parse_detail_page(detail_html)
        result = db.execute(
            text("""insert into web.external_news
                    (title, description, image_url, detail_url, published_text,
                     published_at, source, slug, facebook_url)
                    values (:title, :description, :image_url, :detail_url, :published_text,
                            cast(:published_at as timestamptz), :source, :slug, :facebook_url)
                    on conflict (detail_url) do nothing"""),
            row_for(card, description, facebook_url),
        )
        inserted += result.rowcount or 0

    total = db.execute(text("select count(*) as n from web.external_news")).mappings().first()["n"]
    deleted = 0
    if should_prune(inserted, total):
        deleted = db.execute(
            text("""delete from web.external_news where id in (
                        select id from web.external_news
                        order by published_at desc nulls last, synced_at desc
                        offset :keep)"""),
            {"keep": KEEP_LATEST},
        ).rowcount or 0
    db.commit()

    return {"parsed": len(parsed), "already_existed": len(existing),
            "inserted": inserted, "deleted": deleted, "total_in_table": total - deleted}
