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

from fastapi import Depends, HTTPException, Request, status
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


# --- ตัวจำกัดสำหรับหน้าเว็บสาธารณะ ซึ่งไม่มีบัญชีผู้ใช้ให้นับ ---
#
# หน้าเว็บเปิดให้นักเรียนทั่วไปถามได้โดยไม่ต้องสมัคร เส้นทาง /chat-web จึงใช้
# rate_limiter ข้างบนไม่ได้เพราะมันต้องการบัญชี ผลคือก่อนหน้านี้เส้นทางที่ผู้ใช้จริง
# ใช้กันทั้งหมด "ไม่มีตัวจำกัดเลย" คนเดียวยิงสคริปต์รัวๆ เผาโควตารายวันของ Gemini
# ให้หมดได้ในไม่กี่นาที แล้วทั้งคณะใช้ไม่ได้ไปทั้งวัน
#
# นับจาก IP เพราะไม่มีอย่างอื่นให้นับ ข้อเสียที่ยอมรับ: นักศึกษาที่ใช้เน็ตของ
# มหาวิทยาลัยออกเน็ตด้วย IP เดียวกันจะแชร์โควตาก้อนเดียวกัน เพดานจึงตั้งไว้สูงพอที่
# ห้องเรียนทั้งห้องใช้พร้อมกันได้ แต่ยังต่ำพอจะหยุดสคริปต์ที่ยิงรัวๆ
#
# ตัวคูณความจุที่แท้จริงคือแคชคำตอบ (services/answer_cache.py) ไม่ใช่ตัวนี้ —
# ตัวนี้มีไว้กันการใช้ผิดวิธี ไม่ใช่กันคนใช้เยอะ
_ip_bucket: dict[str, list[float]] = defaultdict(list)

_IP_LIMITS = ((60.0, 20), (3600.0, 200))  # (ช่วงเวลาเป็นวินาที, จำนวนที่ยอมให้)


def _client_ip(request: Request) -> str:
    """
    IP จริงของผู้ใช้ อ่านจากรายการท้ายสุดของ X-Forwarded-For

    Caddy ต่อ IP ของคู่สนทนาที่มันเห็นจริงไว้ "ท้าย" header เสมอ ค่าท้ายสุดจึงเป็นค่าที่
    ผู้ใช้ปลอมไม่ได้ ต่างจากค่าแรกซึ่งมาจากสิ่งที่ผู้ใช้ส่งมาเอง — ถ้าอ่านค่าแรก ใครก็
    ตั้ง X-Forwarded-For เป็นค่าสุ่มทุกครั้งเพื่อหนีตัวจำกัดนี้ได้

    เชื่อ header นี้ได้เพราะ backend ไม่ได้เปิดพอร์ตออกนอกเครื่อง (ดู
    docker-compose.prod.yml) ทางเดียวที่คำขอจะเข้ามาถึงคือผ่าน Caddy
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def web_rate_limiter(request: Request) -> None:
    """จำกัดจำนวนคำถามต่อ IP สำหรับเส้นทางที่เปิดให้ใช้โดยไม่ต้องสมัคร"""
    now = time.time()
    hits = _ip_bucket[_client_ip(request)]
    longest = max(window for window, _ in _IP_LIMITS)
    hits[:] = [t for t in hits if now - t < longest]
    for window, allowed in _IP_LIMITS:
        if sum(1 for t in hits if now - t < window) >= allowed:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "ตอนนี้มีคำถามเข้ามาถี่เกินไปจากเครือข่ายเดียวกัน รบกวนรอสักครู่แล้วถามใหม่ครับ",
            )
    hits.append(now)
