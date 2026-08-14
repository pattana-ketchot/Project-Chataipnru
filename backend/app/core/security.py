"""
Password hashing + JWT helpers.

SECURITY:
  - bcrypt (cost factor 12) — ห้ามใช้ md5/sha1/plain
  - JWT ใช้ algorithm HS256 กับ secret ที่สุ่มยาวพอ (>=32 bytes) เก็บใน env เท่านั้น
  - access token อายุสั้น (30 นาที default) แยกจาก refresh token

หมายเหตุ: เดิมใช้ passlib ห่อ bcrypt อีกชั้น แต่ passlib 1.7.4 (release ล่าสุด
ปี 2020) เข้ากันไม่ได้กับ bcrypt >= 4.1 — ตอนตรวจ backend ตัวเองจะส่งรหัสผ่านยาว
เกิน 72 ไบต์เข้า bcrypt ทำให้ ValueError ตั้งแต่ import จึงเรียก bcrypt ตรงๆ แทน
"""
import base64
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.core.config import get_settings

settings = get_settings()

BCRYPT_ROUNDS = 12


def _prehash(plain_password: str) -> bytes:
    """
    bcrypt รับ input ได้สูงสุด 72 ไบต์เท่านั้น (ส่วนเกินถูกตัดทิ้งเงียบๆ ใน bcrypt
    รุ่นเก่า ส่วนรุ่น 5 ขึ้นไป raise ValueError) ซึ่งเป็นปัญหากับรหัสผ่านภาษาไทย
    เพราะ 1 ตัวอักษร = 3 ไบต์ใน UTF-8 จะชนเพดานตั้งแต่ 24 ตัวอักษร

    แก้โดย hash ด้วย SHA-256 ก่อน แล้วเข้ารหัส base64 ให้ได้ความยาวคงที่ 44 ไบต์
    (ไม่มี NUL byte ที่จะทำให้ bcrypt ตัดสตริงกลางคัน) — เป็นรูปแบบเดียวกับ
    bcrypt_sha256 ของ passlib รหัสผ่านยาวเท่าไหร่ก็ใช้ได้จริงโดยไม่ถูกตัด
    """
    digest = hashlib.sha256(plain_password.encode("utf-8")).digest()
    return base64.b64encode(digest)


def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(_prehash(plain_password), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("ascii")


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(_prehash(plain_password), password_hash.encode("ascii"))
    except ValueError:
        # hash ใน DB ผิดรูปแบบ (ข้อมูลเสีย/ถูกแก้มือ) — ถือว่า verify ไม่ผ่าน
        # ไม่โยน exception ออกไปเป็น 500 ซึ่งจะบอกผู้โจมตีว่า record นี้ผิดปกติ
        return False


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
