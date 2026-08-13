"""
Password hashing + JWT helpers.

SECURITY:
  - bcrypt ผ่าน passlib (cost factor default 12) — ห้ามใช้ md5/sha1/plain
  - JWT ใช้ algorithm HS256 กับ secret ที่สุ่มยาวพอ (>=32 bytes) เก็บใน env เท่านั้น
  - access token อายุสั้น (30 นาที default) แยกจาก refresh token
"""
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)


def create_access_token(subject: str, extra_claims: dict[str, Any] | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
        **(extra_claims or {}),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=settings.refresh_token_expire_days),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    # PyJWT ตรวจ exp ให้อัตโนมัติและจะ raise jwt.ExpiredSignatureError / jwt.InvalidTokenError
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
