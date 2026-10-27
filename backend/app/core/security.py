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
import secrets
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


# รูปแบบการเก็บรหัสผ่านที่รองรับ
#
# bcrypt_sha256  ของระบบนี้ — bcrypt(base64(sha256(pw))) รองรับรหัสผ่านยาวและภาษาไทย
# bcrypt         ของ Supabase Auth — bcrypt(pw) ตรง ๆ ไม่มีการ prehash
#
# รองรับสองแบบเพื่อให้ **ย้ายบัญชีจาก Supabase ได้โดยผู้ใช้ไม่ต้องตั้งรหัสใหม่**
# แถวที่นำเข้ามาถูกทำเครื่องหมายเป็น bcrypt แล้วอัปเกรดเป็น bcrypt_sha256
# อัตโนมัติในครั้งแรกที่เจ้าของเข้าสู่ระบบสำเร็จ (ดู routes/auth.py)
SCHEME_CURRENT = "bcrypt_sha256"
SCHEME_LEGACY_BCRYPT = "bcrypt"


def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(_prehash(plain_password), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("ascii")


def verify_password(plain_password: str, password_hash: str,
                    scheme: str = SCHEME_CURRENT) -> bool:
    """
    ตรวจรหัสผ่านตามรูปแบบที่แถวนั้นระบุไว้

    **ต้องส่ง scheme ให้ตรงกับที่เก็บ** — ใช้รูปแบบผิดจะไม่ผ่านทั้งที่รหัสถูก
    ค่าตั้งต้นเป็นรูปแบบของระบบนี้ เพื่อให้โค้ดเดิมที่ยังไม่ส่ง scheme ทำงานเหมือนเดิม
    """
    try:
        candidate = (plain_password.encode("utf-8") if scheme == SCHEME_LEGACY_BCRYPT
                     else _prehash(plain_password))
        return bcrypt.checkpw(candidate, password_hash.encode("ascii"))
    except ValueError:
        # hash ใน DB ผิดรูปแบบ (ข้อมูลเสีย/ถูกแก้มือ) — ถือว่า verify ไม่ผ่าน
        # ไม่โยน exception ออกไปเป็น 500 ซึ่งจะบอกผู้โจมตีว่า record นี้ผิดปกติ
        return False


def needs_rehash(scheme: str) -> bool:
    """แถวนี้ควรถูกอัปเกรดเป็นรูปแบบปัจจุบันไหม — เรียกหลังตรวจรหัสผ่านผ่านแล้วเท่านั้น"""
    return scheme != SCHEME_CURRENT


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
    """
    refresh token หนึ่งใบ — **ต้องไม่ซ้ำกับใบอื่นเด็ดขาด**

    jti เป็นค่าสุ่มที่ทำให้สองใบต่างกันเสมอ ถึงแม้จะออกให้ผู้ใช้คนเดียวกันในวินาทีเดียวกัน
    ซึ่งเกิดได้จริงเมื่อเข้าสู่ระบบสองอุปกรณ์พร้อมกันหรือกดซ้ำ

    ถ้าไม่มี jti เนื้อ JWT จะเหมือนกันทุกไบต์ (sub/type/iat/exp เท่ากันหมด) ผลคือ
      1. ทะเบียนเซสชันชน unique constraint แล้วการเข้าสู่ระบบล้มเป็น 500
      2. สองเซสชันใช้ token ใบเดียวกัน การออกจากระบบที่หนึ่งจึงถอนอีกที่หนึ่งไปด้วย

    พบจากการทดสอบกับฐานข้อมูลจริง — ของปลอมไม่มี unique constraint จึงไม่เคยฟ้อง
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=settings.refresh_token_expire_days),
        "jti": secrets.token_urlsafe(16),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    # PyJWT ตรวจ exp ให้อัตโนมัติและจะ raise jwt.ExpiredSignatureError / jwt.InvalidTokenError
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
