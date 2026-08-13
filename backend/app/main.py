import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, courses, recommend, search, users
from app.core.config import get_settings

settings = get_settings()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("course_advisor")

app = FastAPI(
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


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
