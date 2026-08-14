import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.routes import auth, chat, courses, recommend, search, users
from app.core.config import get_settings
from app.db.session import engine

settings = get_settings()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("course_advisor")


def _check_embedding_dim() -> None:
    """
    ตรวจว่า EMBED_DIM ตรงกับมิติจริงของคอลัมน์ course_chunks.embedding

    ถ้าไม่ตรงแล้วปล่อยผ่าน ระบบจะยังตอบ 200 ได้ตามปกติแต่ผลลัพธ์ผิดทั้งหมด
    (insert จะ error ส่วน query จะเทียบ vector คนละสเปซกัน) — เป็นความพังแบบ
    ไม่มีอาการซึ่งหาสาเหตุยากมาก จึงเลือกให้ fail ตั้งแต่ตอนสตาร์ทพร้อมบอกค่า
    ที่ขัดกัน แทนที่จะปล่อยให้ค้นเจอตอนสาธิตหน้างาน
    """
    with engine.connect() as conn:
        db_dim = conn.execute(
            text("SELECT atttypmod FROM pg_attribute WHERE attrelid = 'course_chunks'::regclass AND attname = 'embedding'")
        ).scalar()

    if db_dim != settings.embed_dim:
        raise RuntimeError(
            f"มิติของ embedding ไม่ตรงกัน: คอลัมน์ course_chunks.embedding = {db_dim} "
            f"แต่ EMBED_DIM ใน .env = {settings.embed_dim} "
            f"(โมเดลปัจจุบัน: {settings.embed_model}) — "
            "ต้องแก้ db/schema.sql ให้ตรง แล้วสร้าง DB ใหม่และ ingest ใหม่ทั้งหมด"
        )
    logger.info("embedding dim = %d ตรงกับ %s", db_dim, settings.embed_model)


@asynccontextmanager
async def lifespan(_: FastAPI):
    _check_embedding_dim()
    yield


app = FastAPI(
    lifespan=lifespan,
    title="Course Advisor API",
    version="0.1.0",
    # SECURITY: ปิด /docs, /redoc ใน production หรือใส่ auth คลุมไว้ ถ้า API
    # ไม่ได้ตั้งใจให้เป็น public — ปรับผ่าน settings ได้ตามต้องการ
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(courses.router)
app.include_router(search.router)
app.include_router(recommend.router)
app.include_router(chat.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
