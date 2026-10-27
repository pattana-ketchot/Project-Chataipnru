"""
นโยบายและเครื่องมือของระบบเข้าสู่ระบบ — Phase 4 (ถอด Supabase Auth)

แยกเป็นสองชั้นโดยตั้งใจ
    ส่วนบน  ตรรกะล้วน ไม่แตะฐานข้อมูล — ทดสอบได้โดยไม่ต้องมีฐานข้อมูล
    ส่วนล่าง คำสั่งที่คุยกับฐานข้อมูล — บางเบาที่สุดเท่าที่ทำได้

**ห้ามเขียนรหัสผ่านหรือ token ลง log ไม่ว่ากรณีใด** ทุกฟังก์ชันในไฟล์นี้รับค่าดิบแล้ว
แปลงเป็น hash ทันที ค่าดิบไม่เคยถูกเก็บและไม่เคยถูกส่งต่อไปที่อื่นนอกจากผู้ใช้เจ้าของ
"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

# ── นโยบาย ───────────────────────────────────────────────────────────
#
# ล็อกหลังพลาดกี่ครั้ง และล็อกนานเท่าไร
#
# ตั้งให้สั้นโดยตั้งใจ เพราะการล็อกยาวเปิดช่องให้คนร้ายจงใจทำให้เจ้าของบัญชีเข้าไม่ได้
# ด้วยการใส่รหัสผิดซ้ำ ๆ ด่านหลักที่กันการเดารหัสคือการจำกัดตาม IP ซึ่งอยู่ใน deps.py
FAILURES_BEFORE_LOCK = 5
LOCK_MINUTES = 15
FAILURES_BEFORE_LONG_LOCK = 10
LONG_LOCK_MINUTES = 60

PASSWORD_RESET_TTL = timedelta(hours=1)
EMAIL_VERIFY_TTL = timedelta(hours=24)

STAFF_ROLES = ("admin", "editor")
APPROVED = "approved"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def new_token() -> str:
    """token ดิบสำหรับส่งให้เจ้าของบัญชี — เก็บลงฐานข้อมูลเป็น hash เท่านั้น"""
    return secrets.token_urlsafe(32)


def hash_token(raw: str) -> str:
    """
    sha256 ของ token

    ไม่ใช้ bcrypt เพราะ token เป็นค่าสุ่ม 256 บิตอยู่แล้ว การเดาด้วยพจนานุกรมไม่มีความหมาย
    และ bcrypt ช้าเกินไปสำหรับการค้นหาแถวด้วยค่านี้
    """
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def can_access_admin(role: str | None, status: str | None) -> bool:
    """
    ด่านเดียวที่ตัดสินว่าเข้าส่วนผู้ดูแลได้ไหม

    ต้องเป็นทั้ง staff **และ** อนุมัติแล้ว — เงื่อนไขเดียวกับที่ระบบเดิมใช้
    (ดู webapi/api/_lib/adminAuth.js และ src/lib/adminAuth.js)
    """
    return role in STAFF_ROLES and status == APPROVED


def can_edit(role: str | None, status: str | None) -> bool:
    """สร้างและแก้เนื้อหาได้ — ทั้ง admin และ editor ที่อนุมัติแล้ว"""
    return can_access_admin(role, status)


def can_delete(role: str | None, status: str | None) -> bool:
    """
    ลบได้เฉพาะ admin

    ตรงกับหน้าเว็บที่ปุ่มลบขึ้นเฉพาะ admin — ถ้าหลังบ้านยอมให้ editor ลบ
    ปุ่มที่ซ่อนไว้จะไม่ใช่ด่านจริง
    """
    return role == "admin" and status == APPROVED


@dataclass(frozen=True)
class LockState:
    locked: bool
    retry_after_seconds: int


def lock_state(locked_until: datetime | None, now: datetime | None = None) -> LockState:
    """บัญชีถูกล็อกอยู่ไหม และต้องรออีกกี่วินาที"""
    now = now or now_utc()
    if locked_until is None or locked_until <= now:
        return LockState(False, 0)
    return LockState(True, max(1, int((locked_until - now).total_seconds())))


def next_failure(failed_count: int, now: datetime | None = None) -> tuple[int, datetime | None]:
    """
    นับความล้มเหลวครั้งถัดไป แล้วบอกว่าต้องล็อกถึงเมื่อไร

    คืน (จำนวนครั้งใหม่, เวลาปลดล็อก) — เวลาปลดล็อกเป็น None แปลว่ายังไม่ล็อก
    """
    now = now or now_utc()
    count = failed_count + 1
    if count >= FAILURES_BEFORE_LONG_LOCK:
        return count, now + timedelta(minutes=LONG_LOCK_MINUTES)
    if count >= FAILURES_BEFORE_LOCK:
        return count, now + timedelta(minutes=LOCK_MINUTES)
    return count, None


def token_expiry(purpose: str, now: datetime | None = None) -> datetime:
    now = now or now_utc()
    if purpose == "password_reset":
        return now + PASSWORD_RESET_TTL
    if purpose == "email_verify":
        return now + EMAIL_VERIFY_TTL
    raise ValueError(f"ไม่รู้จัก purpose: {purpose}")


# ── ส่วนที่คุยกับฐานข้อมูล ───────────────────────────────────────────

def record_login_failure(db: Session, user_id: uuid.UUID, failed_count: int) -> None:
    count, locked_until = next_failure(failed_count)
    db.execute(
        text("update public.users set failed_login_count = :c, locked_until = :u where id = :id"),
        {"c": count, "u": locked_until, "id": str(user_id)},
    )


def record_login_success(db: Session, user_id: uuid.UUID) -> None:
    db.execute(
        text("update public.users set failed_login_count = 0, locked_until = null,"
             " last_login_at = now() where id = :id"),
        {"id": str(user_id)},
    )


def issue_session(db: Session, user_id: uuid.UUID, refresh_token: str,
                  expires_at: datetime, user_agent: str | None = None) -> None:
    """บันทึกทะเบียน refresh token — ทำให้การออกจากระบบมีผลจริง"""
    db.execute(
        text("insert into public.auth_sessions (user_id, token_hash, user_agent, expires_at)"
             " values (:u, :h, :a, :e)"),
        {"u": str(user_id), "h": hash_token(refresh_token),
         "a": (user_agent or "")[:300] or None, "e": expires_at},
    )


def session_user_id(db: Session, refresh_token: str) -> str | None:
    """คืนรหัสผู้ใช้ถ้า refresh token นี้ยังใช้ได้ — ยังไม่ถูกเพิกถอนและยังไม่หมดอายุ"""
    row = db.execute(
        text("select user_id from public.auth_sessions"
             " where token_hash = :h and revoked_at is null and expires_at > now()"),
        {"h": hash_token(refresh_token)},
    ).mappings().first()
    return str(row["user_id"]) if row else None


def revoke_session(db: Session, refresh_token: str) -> bool:
    result = db.execute(
        text("update public.auth_sessions set revoked_at = now()"
             " where token_hash = :h and revoked_at is null"),
        {"h": hash_token(refresh_token)},
    )
    return (result.rowcount or 0) > 0


def revoke_all_sessions(db: Session, user_id: uuid.UUID) -> int:
    """
    ถอนทุกอุปกรณ์ของผู้ใช้คนหนึ่ง

    ใช้ตอนเปลี่ยนรหัสผ่าน ตอนถูกปลดสิทธิ์ และตอนผู้ดูแลสั่งถอน
    """
    result = db.execute(
        text("update public.auth_sessions set revoked_at = now()"
             " where user_id = :u and revoked_at is null"),
        {"u": str(user_id)},
    )
    return result.rowcount or 0


def issue_auth_token(db: Session, user_id: uuid.UUID, purpose: str) -> str:
    """
    ออก token ใช้ครั้งเดียว แล้วคืน **ค่าดิบ** ให้ผู้เรียกส่งต่อให้เจ้าของบัญชี

    ยกเลิก token เก่าที่ยังไม่ถูกใช้ของ purpose เดียวกันก่อน เพื่อให้มีใบที่ใช้ได้ใบเดียว
    """
    db.execute(
        text("update public.auth_tokens set used_at = now()"
             " where user_id = :u and purpose = :p and used_at is null"),
        {"u": str(user_id), "p": purpose},
    )
    raw = new_token()
    db.execute(
        text("insert into public.auth_tokens (user_id, purpose, token_hash, expires_at)"
             " values (:u, :p, :h, :e)"),
        {"u": str(user_id), "p": purpose, "h": hash_token(raw), "e": token_expiry(purpose)},
    )
    return raw


def consume_auth_token(db: Session, raw: str, purpose: str) -> str | None:
    """
    ใช้ token หนึ่งใบแล้วทำเครื่องหมายว่าใช้แล้ว คืนรหัสผู้ใช้ถ้าใช้ได้

    ทำเป็นคำสั่งเดียวเพื่อให้ใช้ซ้ำพร้อมกันสองครั้งไม่ผ่านทั้งคู่
    """
    row = db.execute(
        text("update public.auth_tokens set used_at = now()"
             " where token_hash = :h and purpose = :p and used_at is null and expires_at > now()"
             " returning user_id"),
        {"h": hash_token(raw), "p": purpose},
    ).mappings().first()
    return str(row["user_id"]) if row else None
