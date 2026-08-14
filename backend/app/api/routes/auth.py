import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.core.security import create_access_token, create_refresh_token, hash_password, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])

# hash ของรหัสผ่านสุ่มที่ไม่มีใครรู้ ใช้เทียบตอนหา user ไม่เจอ เพื่อให้ /login
# ใช้เวลาใกล้เคียงกันทั้งกรณีมีและไม่มีอีเมลนั้นในระบบ
# สร้างตอน import ด้วยฟังก์ชันจริง (ไม่ hardcode สตริง) เพราะ hash ที่เขียนมือ
# อาจผิดรูปแบบจน checkpw คืนค่าทันที แล้ว timing จะต่างกันจนเดาได้ว่าอีเมลมีจริงไหม
_DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(32))


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> User:
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        # SECURITY: ข้อความ error ไม่บอกว่า "อีเมลนี้มีอยู่แล้ว" มากเกินไปเพื่อลด user
        # enumeration แต่ในระบบ registration ทั่วไปมักยอมรับ trade-off นี้ได้ —
        # ปรับตาม threat model จริงของระบบ
        raise HTTPException(status.HTTP_409_CONFLICT, "email already registered")

    user = User(email=payload.email, password_hash=hash_password(payload.password), full_name=payload.full_name)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenPair)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenPair:
    user = db.query(User).filter(User.email == payload.email).first()
    # SECURITY: เทียบ hash เสมอแม้ user ไม่พบ (constant-shape response) เพื่อลด
    # timing/enumeration signal — ใช้ dummy hash เมื่อไม่พบ user
    password_hash = user.password_hash if user else _DUMMY_PASSWORD_HASH
    ok = verify_password(payload.password, password_hash)

    if not user or not ok or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")

    return TokenPair(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )
