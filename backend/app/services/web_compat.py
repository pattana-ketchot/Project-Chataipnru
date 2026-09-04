"""
ตัวแปลงให้หน้าเว็บของทีมออกแบบเรียกหลังบ้านนี้ได้โดยไม่ต้องแก้โค้ดหน้าเว็บ

ที่มา
-----
หน้าเว็บถูกเขียนขึ้นคู่กับหลังบ้านอีกชุดหนึ่งที่ทำงานบน Vercel + Supabase จึงเรียก
เส้นทางและใช้รูปแบบข้อมูลคนละแบบกับที่นี่ การจะเอาหน้าเว็บนั้นมาใช้จริงมีสองทาง:
แก้หน้าเว็บให้เรียกแบบเรา หรือให้เรารับแบบของหน้าเว็บ

เลือกทางหลัง เพราะหน้าเว็บยังถูกพัฒนาต่อโดยอีกคน การไปแก้ไฟล์ในนั้นทำให้โค้ดสองชุด
แตกกันแล้วรวมกลับยากขึ้นเรื่อยๆ ส่วนไฟล์นี้อยู่ฝั่งเรา แก้เองได้โดยไม่กระทบใคร

ผู้ใช้ร่วมสำหรับหน้าเว็บสาธารณะ
----------------------------
หน้าเว็บนี้ไม่มีระบบเข้าสู่ระบบสำหรับนักเรียน ทุกคนที่เปิดเว็บใช้งานได้เลย แต่ตาราง
บทสนทนาผูกกับผู้ใช้เสมอเพราะออกแบบไว้ตั้งแต่แรกให้เก็บประวัติรายคน จึงใช้บัญชีกลาง
หนึ่งบัญชีแทน

ข้อแลกเปลี่ยนที่ต้องรู้: ประวัติการสนทนาของทุกคนจะกองรวมกันในบัญชีเดียว และตัวจำกัด
อัตราการเรียกก็นับรวมกันทั้งเว็บ ยอมรับได้สำหรับการสาธิตและการใช้งานจริงระดับคณะ
แต่ถ้าจะเปิดใช้วงกว้างควรทำระบบผู้ใช้ให้หน้าเว็บนี้ก่อน
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.course import Course
from app.models.user import User
# ใช้ตัวย่อชื่อตัวเดียวกับที่ตารางค่าเทอมใช้ เพื่อให้การเทียบชื่อสาขาทั้งระบบให้ผล
# เหมือนกัน รวมถึงกรณีที่ชื่อสาขาเป็นคำเดียวกับชื่อปริญญา (การแพทย์แผนไทยประยุกต์)
from app.services.tuition import _normalise as normalise_title

# อีเมลของบัญชีกลาง ไม่ได้ใช้ส่งอีเมลจริง เป็นเพียงคีย์ที่หาแถวเดิมเจอทุกครั้ง
SHARED_USER_EMAIL = "public-web@stpnru.local"


def shared_user(db: Session) -> User:
    """
    บัญชีกลางของหน้าเว็บสาธารณะ สร้างให้อัตโนมัติในการเรียกครั้งแรก

    ตั้งรหัสผ่านเป็นค่าสุ่มที่ไม่มีใครรู้และไม่เก็บไว้ที่ไหน เพราะไม่มีใครต้องเข้าสู่ระบบ
    ด้วยบัญชีนี้ — มันถูกใช้จากภายในเท่านั้น การเว้นช่องรหัสผ่านไว้ว่างจะเปิดช่องให้
    เข้าสู่ระบบด้วยบัญชีนี้ได้ถ้ามีใครเดาถูก
    """
    user = db.scalar(select(User).where(User.email == SHARED_USER_EMAIL))
    if user is None:
        user = User(
            email=SHARED_USER_EMAIL,
            password_hash=hash_password(uuid.uuid4().hex + uuid.uuid4().hex),
            full_name="ผู้ใช้เว็บไซต์",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


# ชื่อเดิมของสาขาที่คณะปรับปรุงหลักสูตรแล้วเปลี่ยนชื่อ — ฐานข้อมูลของหน้าเว็บอาจใช้
# ชื่อใดชื่อหนึ่ง ถ้าไม่ผูกไว้จะกลายเป็นคนละสาขากันทั้งที่เป็นหลักสูตรเดียวกัน
_ALIASES: list[tuple[str, str]] = [
    ("เทคโนโลยีอาหารและความเป็นผู้ประกอบการสมัยใหม่", "วิทยาศาสตร์และเทคโนโลยีการอาหาร"),
    ("เทคโนโลยีผลิตภัณฑ์ชีวภาพกับการประกอบธุรกิจ", "นวัตกรรมและเทคโนโลยีผลิตภัณฑ์"),
    ("การจัดการสิ่งแวดล้อมและทรัพยากรธรรมชาติ", "วิทยาศาสตร์และเทคโนโลยีสิ่งแวดล้อม"),
]


def _edition_year(title: str) -> int:
    import re

    m = re.search(r"\(พ\.ศ\.\s*(\d{4})\)", title)
    return int(m.group(1)) if m else 0


def _keys_for(title: str) -> list[str]:
    base = normalise_title(title)
    keys = [base]
    for pair in _ALIASES:
        if any(normalise_title(name) == base for name in pair):
            keys.extend(normalise_title(name) for name in pair)
    return list(dict.fromkeys(keys))


def match_by_title(db: Session, sent: list[dict]) -> tuple[list[tuple[dict, Course]], list[dict]]:
    """
    จับคู่สาขาที่หน้าเว็บส่งมากับหลักสูตรในคลังเอกสาร โดยเทียบจากชื่อ

    เทียบด้วยชื่อ ไม่ใช่รหัส เพราะสองฐานข้อมูลใช้รหัสคนละชุดกันโดยสิ้นเชิง

    เมื่อสาขาหนึ่งมีเอกสารสองฉบับ เลือกฉบับปีล่าสุด เพราะเป็นหลักสูตรที่ใช้อยู่จริง

    คืนทั้งรายการที่จับคู่ได้และไม่ได้ ผู้เรียกต้องบอกผู้ใช้ว่าสาขาไหนไม่มีเอกสาร
    ไม่ใช่เงียบๆ แล้วตอบเฉพาะที่เหลือ
    """
    latest: dict[str, Course] = {}
    for c in db.scalars(select(Course).where(Course.is_active)).all():
        key = normalise_title(c.title)
        seen = latest.get(key)
        if seen is None or _edition_year(c.title) > _edition_year(seen.title):
            latest[key] = c

    matched: list[tuple[dict, Course]] = []
    unmatched: list[dict] = []
    for item in sent:
        hit = next((latest[k] for k in _keys_for(item.get("title", "")) if k in latest), None)
        if hit is not None:
            matched.append((item, hit))
        else:
            unmatched.append(item)
    return matched, unmatched
