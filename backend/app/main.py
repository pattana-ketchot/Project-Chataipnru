import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.routes import auth, chat, compare, courses, match, recommend, search, users, web_compat
from app.core.config import get_settings
from app.db.session import engine

from llm.connector import ChatMessage  # noqa: E402  (sys.path ตั้งโดย llm_client)

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


async def _keep_models_warm() -> None:
    """
    ยิงคำขอเล็กๆ ไปที่ Ollama เป็นระยะเพื่อไม่ให้โมเดลถูกถอดออกจาก VRAM

    ปัญหาที่แก้: Ollama ถอดโมเดลทิ้งเมื่อไม่ถูกใช้ครบ OLLAMA_KEEP_ALIVE (ตั้งไว้
    30 นาที) คำถามแรกหลังจากนั้นต้องโหลดกลับเข้า VRAM ซึ่งวัดได้ 118 วินาที
    นานจนฝั่ง Next ตัดการเชื่อมต่อด้วย ECONNRESET แล้วผู้ใช้เห็นเป็น
    "เกิดข้อผิดพลาด กรุณาลองใหม่" ทั้งที่ระบบยังทำงานปกติ

    ยิงถี่กว่าเวลาหมดอายุเพื่อให้ตัวนับถูกรีเซ็ตก่อนเสมอ ค่าใช้จ่ายต่อครั้งต่ำมาก
    (embed ข้อความสั้นหนึ่งครั้ง) แลกกับการที่โมเดลค้างอยู่ใน VRAM ตลอดเวลาที่
    เซิร์ฟเวอร์เปิด ซึ่งเป็นสิ่งที่ต้องการอยู่แล้วบนเครื่องที่ตั้งใจใช้สาธิต

    ปิดได้ด้วย WARMUP_INTERVAL_MINUTES=0 ถ้าต้องการคืน VRAM ให้งานอื่น
    """
    from app.services.llm_client import get_llm_connector

    interval = settings.warmup_interval_minutes * 60
    connector = get_llm_connector()
    while True:
        try:
            # embed อย่างเดียวไม่พอ ต้องแตะโมเดลตอบคำถามด้วยเพราะนับเวลาแยกกัน
            await asyncio.to_thread(connector.embed, "warmup")
            # อุ่นโมเดลเขียนคำตอบเฉพาะตอนที่รันในเครื่อง — ถ้าใช้ Gemini การยิงคำขอ
            # ทุก 20 นาทีมีแต่กินโควตาเปล่าๆ เพราะฝั่งนั้นไม่มีโมเดลให้ค้างในหน่วยความจำ
            if settings.llm_provider != "gemini":
                await asyncio.to_thread(
                    connector.chat, [ChatMessage(role="user", content="hi")], 0.0, False
                )
            logger.debug("warmup ping สำเร็จ")
        except Exception as e:  # noqa: BLE001 — งานเบื้องหลัง ห้ามทำให้เซิร์ฟเวอร์ล้ม
            logger.warning("warmup ping ไม่สำเร็จ: %s", type(e).__name__)
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(_: FastAPI):
    _check_embedding_dim()

    task = None
    if settings.warmup_interval_minutes > 0:
        task = asyncio.create_task(_keep_models_warm())
        logger.info("เปิด warmup ทุก %d นาที", settings.warmup_interval_minutes)

    yield

    if task is not None:
        task.cancel()


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
app.include_router(match.router)
app.include_router(compare.router)
# เส้นทางในรูปแบบที่หน้าเว็บของทีมออกแบบเรียก — ดู routes/web_compat.py
app.include_router(web_compat.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
