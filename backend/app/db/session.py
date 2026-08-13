"""
SQLAlchemy engine/session setup.

SECURITY: engine ถูกสร้างจาก DATABASE_URL เดียว (ใช้ role จำกัดสิทธิ์ตาม
db/schema.sql, ตัวอย่าง `advisor_api`) — ทุก query ต้องผ่าน ORM/parameterized
statement เท่านั้น ห้าม string-format ค่าจาก user เข้า SQL ตรงๆ
"""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(settings.database_url, pool_pre_ping=True, pool_size=10, max_overflow=20)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
