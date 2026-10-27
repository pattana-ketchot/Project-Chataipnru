"""
ส่งอีเมลของระบบบัญชี — Phase 4 (มาแทนอีเมลที่ Supabase Auth เคยส่งให้)

ขอบเขตแคบโดยตั้งใจ: ส่งได้สองแบบคือลิงก์ตั้งรหัสผ่านใหม่กับลิงก์ยืนยันอีเมล
ไม่ใช่ระบบอีเมลทั่วไป

**ห้ามเขียน token ลง log** ไฟล์นี้จึงไม่ log เนื้ออีเมลและไม่ log ค่าที่ส่งเลย
ส่งไม่สำเร็จจะโยน EmailNotConfigured ให้ผู้เรียกตัดสินใจ ไม่ใช่กลืนแล้วเงียบ
"""
from __future__ import annotations

import smtplib
from email.message import EmailMessage

from app.core.config import get_settings


class EmailNotConfigured(RuntimeError):
    """ยังไม่ได้ตั้งค่าการส่งอีเมล หรือส่งไม่สำเร็จ"""


_SUBJECTS = {
    "password_reset": "ตั้งรหัสผ่านใหม่ — ระบบแนะแนวหลักสูตร คณะวิทยาศาสตร์และเทคโนโลยี",
    "email_verify": "ยืนยันอีเมล — ระบบแนะแนวหลักสูตร คณะวิทยาศาสตร์และเทคโนโลยี",
}

_PATHS = {
    "password_reset": "/admin/reset-password",
    "email_verify": "/admin/verify-email",
}

_BODIES = {
    "password_reset": (
        "มีการขอตั้งรหัสผ่านใหม่สำหรับบัญชีนี้\n\n"
        "เปิดลิงก์นี้เพื่อตั้งรหัสผ่านใหม่ ใช้ได้ครั้งเดียวและหมดอายุใน 1 ชั่วโมง\n\n"
        "{link}\n\n"
        "ถ้าไม่ได้เป็นผู้ขอ ไม่ต้องทำอะไร รหัสผ่านเดิมยังใช้ได้ตามปกติ\n"
    ),
    "email_verify": (
        "ขอบคุณที่สมัครใช้งาน\n\n"
        "เปิดลิงก์นี้เพื่อยืนยันอีเมล ใช้ได้ครั้งเดียวและหมดอายุใน 24 ชั่วโมง\n\n"
        "{link}\n\n"
        "ถ้าไม่ได้เป็นผู้สมัคร ไม่ต้องทำอะไร\n"
    ),
}


def is_configured() -> bool:
    s = get_settings()
    return bool(s.smtp_host and s.smtp_from and s.public_base_url)


def build_link(purpose: str, token: str) -> str:
    s = get_settings()
    if purpose not in _PATHS:
        raise ValueError(f"ไม่รู้จัก purpose: {purpose}")
    return f"{s.public_base_url.rstrip('/')}{_PATHS[purpose]}?token={token}"


def send_account_email(to_email: str, purpose: str, token: str) -> None:
    """
    ส่งอีเมลหนึ่งฉบับ

    โยน EmailNotConfigured เมื่อยังตั้งค่าไม่ครบหรือส่งไม่สำเร็จ — ผู้เรียกต้องจัดการเอง
    **ไม่กลืนข้อผิดพลาดเงียบ ๆ** เพราะผู้ใช้จะรอลิงก์ที่ไม่มีวันมาถึง
    """
    if purpose not in _SUBJECTS:
        raise ValueError(f"ไม่รู้จัก purpose: {purpose}")
    if not is_configured():
        raise EmailNotConfigured("ยังไม่ได้ตั้งค่า SMTP_HOST / SMTP_FROM / PUBLIC_BASE_URL")

    s = get_settings()
    message = EmailMessage()
    message["Subject"] = _SUBJECTS[purpose]
    message["From"] = s.smtp_from
    message["To"] = to_email
    message.set_content(_BODIES[purpose].format(link=build_link(purpose, token)))

    try:
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as server:
            server.starttls()
            if s.smtp_user:
                server.login(s.smtp_user, s.smtp_password)
            server.send_message(message)
    except Exception as exc:  # noqa: BLE001
        # ไม่แนบรายละเอียดของข้อความที่ส่ง และไม่แนบ token
        raise EmailNotConfigured(f"ส่งอีเมลไม่สำเร็จ: {type(exc).__name__}") from None
