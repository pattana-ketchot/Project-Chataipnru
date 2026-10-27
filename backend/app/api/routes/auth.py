"""
เข้าสู่ระบบและจัดการบัญชี — Phase 4 (มาแทน Supabase Auth)

    POST /auth/register                  สมัคร (ได้สถานะ pending เสมอ)
    POST /auth/login                     เข้าสู่ระบบ
    POST /auth/refresh                   ต่ออายุ (หมุน token ทุกครั้ง)
    POST /auth/logout                    ออกจากระบบอุปกรณ์นี้
    POST /auth/logout-all                ออกจากระบบทุกอุปกรณ์
    GET  /auth/me                        ข้อมูลผู้ใช้ปัจจุบัน
    POST /auth/password-reset/request    ขอลิงก์ตั้งรหัสผ่านใหม่
    POST /auth/password-reset/confirm    ตั้งรหัสผ่านใหม่ด้วย token
    POST /auth/email/verify              ยืนยันอีเมลด้วย token
    POST /auth/admin/reset-link          ผู้ดูแลออกลิงก์ให้ (ใช้เมื่อยังส่งอีเมลไม่ได้)

**ห้ามเขียนรหัสผ่านหรือ token ลง log** — ทั้งไฟล์นี้ไม่มีการ log ค่าใดที่เป็นความลับ
"""
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, login_rate_limiter, require_admin_role
from app.core.config import get_settings
from app.core.security import (SCHEME_CURRENT, create_access_token, create_refresh_token,
                               hash_password, needs_rehash, verify_password)
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserOut
from app.services import auth_service as auth
from app.services.mailer import EmailNotConfigured, send_account_email

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()

# hash ของรหัสผ่านสุ่มที่ไม่มีใครรู้ ใช้เทียบตอนหา user ไม่เจอ เพื่อให้ /login
# ใช้เวลาใกล้เคียงกันทั้งกรณีมีและไม่มีอีเมลนั้นในระบบ
# สร้างตอน import ด้วยฟังก์ชันจริง (ไม่ hardcode สตริง) เพราะ hash ที่เขียนมือ
# อาจผิดรูปแบบจน checkpw คืนค่าทันที แล้ว timing จะต่างกันจนเดาได้ว่าอีเมลมีจริงไหม
_DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(32))

_INVALID = "อีเมลหรือรหัสผ่านไม่ถูกต้อง"


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class SessionOut(TokenPair):
    """ส่งสิทธิ์กลับไปพร้อม token เพื่อให้หน้าเว็บไม่ต้องยิงถามซ้ำทันทีหลังเข้าสู่ระบบ"""
    user: dict


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class ResetRequest(BaseModel):
    email: EmailStr


class ResetConfirm(BaseModel):
    token: str
    # ความยาวขั้นต่ำเป็นด่านเดียวที่บังคับได้โดยไม่รบกวนผู้ใช้เกินไป
    new_password: str = Field(min_length=8)


class VerifyRequest(BaseModel):
    token: str


def _user_dict(user: User) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "status": user.status,
        "email_verified": user.email_verified_at is not None,
    }


def _issue(db: Session, user: User, request: Request) -> SessionOut:
    refresh = create_refresh_token(str(user.id))
    expires = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    auth.issue_session(db, user.id, refresh, expires, request.headers.get("user-agent"))
    return SessionOut(
        access_token=create_access_token(str(user.id), {"role": user.role, "status": user.status}),
        refresh_token=refresh,
        user=_user_dict(user),
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(login_rate_limiter)])
def register(payload: UserCreate, db: Session = Depends(get_db)) -> User:
    """
    สมัครบัญชีใหม่ — ได้ `role=user` และ `status=pending` เสมอ

    ไม่มีทางสมัครแล้วได้สิทธิ์ผู้ดูแลทันที ผู้ดูแลที่มีอยู่ต้องเลื่อนสิทธิ์ให้
    """
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "email already registered")

    user = User(email=payload.email, password_hash=hash_password(payload.password),
                full_name=payload.full_name, role="user", status="pending")
    db.add(user)
    db.commit()
    db.refresh(user)

    # ส่งอีเมลยืนยันถ้าตั้งค่าไว้ — ส่งไม่ได้ก็ไม่ทำให้การสมัครล้ม
    try:
        raw = auth.issue_auth_token(db, user.id, "email_verify")
        db.commit()
        send_account_email(user.email, "email_verify", raw)
    except EmailNotConfigured:
        pass
    return user


@router.post("/login", response_model=SessionOut, dependencies=[Depends(login_rate_limiter)])
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> SessionOut:
    user = db.query(User).filter(User.email == payload.email).first()

    # เทียบ hash เสมอแม้ไม่พบผู้ใช้ เพื่อให้เวลาที่ใช้ใกล้เคียงกันทั้งสองกรณี
    #
    # scheme บอกว่าแถวนี้เก็บรหัสผ่านแบบไหน — บัญชีที่ย้ายมาจาก Supabase เป็น bcrypt ตรง ๆ
    # ส่วนของระบบนี้เป็น bcrypt_sha256 ใช้ผิดแบบจะไม่ผ่านทั้งที่รหัสถูก
    password_hash = user.password_hash if user else _DUMMY_PASSWORD_HASH
    scheme = getattr(user, "password_scheme", SCHEME_CURRENT) if user else SCHEME_CURRENT
    ok = verify_password(payload.password, password_hash, scheme)

    if user is not None:
        locked = auth.lock_state(user.locked_until)
        if locked.locked:
            # บอกว่าถูกล็อกได้ เพราะคนที่เห็นข้อความนี้ต้องใส่รหัสผิดมาแล้วหลายครั้ง
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                f"บัญชีถูกล็อกชั่วคราว ลองใหม่ในอีก {locked.retry_after_seconds // 60 + 1} นาที",
                headers={"Retry-After": str(locked.retry_after_seconds)},
            )

    if user is None or not ok or not user.is_active:
        if user is not None and not ok:
            auth.record_login_failure(db, user.id, user.failed_login_count)
            db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, _INVALID)

    # อัปเกรดรูปแบบการเก็บรหัสผ่านตอนที่รู้รหัสจริง ๆ เท่านั้น
    #
    # ทำให้บัญชีที่ย้ายมาจาก Supabase ค่อย ๆ เปลี่ยนมาเป็นรูปแบบของระบบนี้เองโดย
    # เจ้าของไม่ต้องทำอะไร และไม่ต้องให้ใครตั้งรหัสใหม่
    if needs_rehash(scheme):
        user.password_hash = hash_password(payload.password)
        user.password_scheme = SCHEME_CURRENT

    auth.record_login_success(db, user.id)
    out = _issue(db, user, request)
    db.commit()
    return out


@router.post("/refresh", response_model=SessionOut)
def refresh(payload: RefreshRequest, request: Request, db: Session = Depends(get_db)) -> SessionOut:
    """
    ต่ออายุด้วย refresh token — **หมุนทุกครั้ง** ใบเดิมถูกเพิกถอนทันที

    ใบที่ถูกใช้ไปแล้วใช้ซ้ำไม่ได้ ถ้ามีคนขโมยไปใช้ก่อน เจ้าของจะใช้ไม่ได้แล้วรู้ตัว
    """
    user_id = auth.session_user_id(db, payload.refresh_token)
    if user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "เซสชันหมดอายุหรือถูกเพิกถอนแล้ว")

    user = db.get(User, uuid.UUID(user_id))
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "เซสชันหมดอายุหรือถูกเพิกถอนแล้ว")

    auth.revoke_session(db, payload.refresh_token)
    out = _issue(db, user, request)
    db.commit()
    return out


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(payload: RefreshRequest, db: Session = Depends(get_db)) -> None:
    """
    ออกจากระบบอุปกรณ์นี้

    ตอบ 204 เสมอแม้ token ใช้ไม่ได้อยู่แล้ว — ผลลัพธ์ที่ผู้ใช้ต้องการคือ "ออกแล้ว"
    และการบอกว่าใบนี้ใช้ได้หรือไม่เป็นการให้ข้อมูลโดยไม่จำเป็น
    """
    auth.revoke_session(db, payload.refresh_token)
    db.commit()


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
def logout_all(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> None:
    auth.revoke_all_sessions(db, user.id)
    db.commit()


@router.get("/me")
def me(user: User = Depends(get_current_user)) -> dict:
    return _user_dict(user)


@router.post("/password-reset/request", status_code=status.HTTP_202_ACCEPTED,
             dependencies=[Depends(login_rate_limiter)])
def password_reset_request(payload: ResetRequest, db: Session = Depends(get_db)) -> dict:
    """
    ขอลิงก์ตั้งรหัสผ่านใหม่

    **ตอบเหมือนกันเสมอ** ไม่ว่าอีเมลนั้นจะมีในระบบหรือไม่ มิฉะนั้นหน้านี้จะกลายเป็น
    เครื่องมือตรวจว่าอีเมลใดเป็นสมาชิก
    """
    message = {"detail": "ถ้าอีเมลนี้มีในระบบ เราได้ส่งลิงก์ตั้งรหัสผ่านใหม่ไปให้แล้ว"}
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None:
        return message

    raw = auth.issue_auth_token(db, user.id, "password_reset")
    db.commit()
    try:
        send_account_email(user.email, "password_reset", raw)
    except EmailNotConfigured:
        # ยังตอบข้อความเดิม เพื่อไม่ให้ต่างจากกรณีไม่มีอีเมลนั้น
        # ผู้ดูแลออกลิงก์ให้ได้ที่ /auth/admin/reset-link
        pass
    return message


@router.post("/password-reset/confirm")
def password_reset_confirm(payload: ResetConfirm, db: Session = Depends(get_db)) -> dict:
    """
    ตั้งรหัสผ่านใหม่ แล้ว **ถอนทุกเซสชันของบัญชีนั้น**

    เพราะถ้ารหัสผ่านถูกเปลี่ยนเนื่องจากบัญชีถูกยึด การปล่อยเซสชันเดิมไว้คือปล่อยให้
    คนที่ยึดไปใช้ต่อได้
    """
    user_id = auth.consume_auth_token(db, payload.token, "password_reset")
    if user_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "ลิงก์หมดอายุหรือถูกใช้ไปแล้ว")

    user = db.get(User, uuid.UUID(user_id))
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "ลิงก์หมดอายุหรือถูกใช้ไปแล้ว")

    user.password_hash = hash_password(payload.new_password)
    user.password_scheme = SCHEME_CURRENT
    user.failed_login_count = 0
    user.locked_until = None
    auth.revoke_all_sessions(db, user.id)
    db.commit()
    return {"detail": "ตั้งรหัสผ่านใหม่เรียบร้อยแล้ว กรุณาเข้าสู่ระบบอีกครั้ง"}


@router.post("/email/verify")
def email_verify(payload: VerifyRequest, db: Session = Depends(get_db)) -> dict:
    user_id = auth.consume_auth_token(db, payload.token, "email_verify")
    if user_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "ลิงก์หมดอายุหรือถูกใช้ไปแล้ว")

    user = db.get(User, uuid.UUID(user_id))
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "ลิงก์หมดอายุหรือถูกใช้ไปแล้ว")

    user.email_verified_at = datetime.now(timezone.utc)
    db.commit()
    return {"detail": "ยืนยันอีเมลเรียบร้อยแล้ว"}


class AdminResetRequest(BaseModel):
    user_id: str


@router.post("/admin/reset-link")
def admin_reset_link(payload: AdminResetRequest,
                     _admin: User = Depends(require_admin_role),
                     db: Session = Depends(get_db)) -> dict:
    """
    ผู้ดูแลออกลิงก์ตั้งรหัสผ่านใหม่ให้ผู้ใช้คนหนึ่ง

    มีไว้สำหรับช่วงที่ยังไม่ได้ตั้งค่าการส่งอีเมล — ผู้ดูแลส่งลิงก์ให้เจ้าของบัญชี
    ทางช่องทางอื่นเอง ดีกว่าเขียน token ลง log ซึ่งห้ามเด็ดขาด

    เฉพาะ `admin` เท่านั้น เพราะเท่ากับการเข้าถึงบัญชีคนอื่นได้
    """
    try:
        target = db.get(User, uuid.UUID(payload.user_id))
    except ValueError:
        target = None
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบผู้ใช้นี้")

    raw = auth.issue_auth_token(db, target.id, "password_reset")
    db.commit()
    base = settings.public_base_url.rstrip("/")
    return {
        "email": target.email,
        "reset_url": f"{base}/admin/reset-password?token={raw}" if base else None,
        "token": raw,
        "expires_in_minutes": int(auth.PASSWORD_RESET_TTL.total_seconds() // 60),
        "detail": "ส่งลิงก์นี้ให้เจ้าของบัญชีทางช่องทางที่ปลอดภัย ใช้ได้ครั้งเดียว",
    }


class ProfileIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)


@router.put("/me")
def update_me(payload: ProfileIn, user: User = Depends(get_current_user),
              db: Session = Depends(get_db)) -> dict:
    """แก้ชื่อที่แสดงของตัวเอง — แก้ role หรือ status ที่นี่ไม่ได้โดยออกแบบ"""
    user.full_name = payload.full_name.strip()
    db.commit()
    db.refresh(user)
    return _user_dict(user)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


@router.post("/password/change")
def change_password(payload: PasswordChange, request: Request,
                    user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)) -> SessionOut:
    """
    เปลี่ยนรหัสผ่านของตัวเอง — **ต้องใส่รหัสผ่านเดิม**

    ถ้าไม่ตรวจรหัสเดิม คนที่ยืมเครื่องที่เปิดค้างไว้จะยึดบัญชีได้ทันที

    สำเร็จแล้วถอนทุกเซสชันแล้วออกใบใหม่ให้อุปกรณ์นี้ — อุปกรณ์อื่นหลุดทั้งหมด
    ซึ่งเป็นสิ่งที่ต้องการถ้าเหตุผลที่เปลี่ยนคือสงสัยว่าบัญชีถูกยึด
    """
    if not verify_password(payload.current_password, user.password_hash,
                           getattr(user, "password_scheme", SCHEME_CURRENT)):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "รหัสผ่านเดิมไม่ถูกต้อง")

    user.password_hash = hash_password(payload.new_password)
    user.password_scheme = SCHEME_CURRENT
    auth.revoke_all_sessions(db, user.id)
    out = _issue(db, user, request)
    db.commit()
    return out
