"""
Shared FastAPI dependencies: DB session, current-user auth, simple rate limiter.

SECURITY:
  - get_current_user validates JWT signature+exp ทุกครั้ง (ไม่ trust client claim เฉยๆ)
  - rate_limiter เป็น in-memory token bucket ต่อ "บัญชีผู้ใช้" สำหรับ dev;
    production ควรใช้ Redis-backed limiter แทน (in-memory ใช้ไม่ได้ถ้ามีหลาย
    worker/instance เพราะแต่ละ process นับแยกกัน)
"""
import time
import uuid
from collections import defaultdict

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import ExpiredSignatureError, InvalidTokenError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User

settings = get_settings()
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    try:
        payload = decode_token(credentials.credentials)
    except ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token expired")
    except InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token")

    if payload.get("type") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "wrong token type")

    user = db.get(User, uuid.UUID(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user not found or inactive")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "admin only")
    return user


# --- naive per-process rate limiter (dev only, see SECURITY note above) ---
_bucket: dict[str, list[float]] = defaultdict(list)


def rate_limiter(user: User = Depends(get_current_user)) -> None:
    """
    จำกัดจำนวนคำขอต่อนาที "ต่อหนึ่งบัญชี"

    เดิมนับจาก IP ซึ่งใช้ไม่ได้เมื่อ frontend ส่งต่อคำขอให้ backend (rewrite ใน
    next.config.ts) เพราะ backend จะเห็นเป็น IP ของเซิร์ฟเวอร์ Next เหมือนกันหมด
    ผู้ใช้ทุกคนจึงแชร์โควตาก้อนเดียวกัน — คนหนึ่งยิงถี่แล้วคนอื่นโดน 429 ไปด้วย

    การนับจาก user id ยังปลอมไม่ได้ด้วย ต่างจาก X-Forwarded-For ที่ client
    ตั้งค่าเองได้ถ้า backend ถูกเปิดออกสู่ภายนอกโดยตรง

    ทุก endpoint ที่ใช้ตัวนี้ต้องผ่าน authentication อยู่แล้ว และ FastAPI cache
    ผลของ get_current_user ภายใน request เดียวกัน จึงไม่ได้ query DB ซ้ำ
    """
    now = time.time()
    window = 60.0
    hits = _bucket[str(user.id)]
    hits[:] = [t for t in hits if now - t < window]
    if len(hits) >= settings.rate_limit_per_minute:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "rate limit exceeded")
    hits.append(now)
