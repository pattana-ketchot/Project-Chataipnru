"""
ตรวจเส้นทางเข้าสู่ระบบที่มาแทน Supabase Auth — Phase 4

เหตุที่ต้องมี: นี่คือด่านหน้าสุดของระบบ ถ้าพลาดคือใครก็เข้าได้ หรือเจ้าของเข้าไม่ได้

ข้อกำหนดที่ห้ามหลุด
    - รหัสผิดต้องได้ 401 และ **ต้องนับความล้มเหลว** ไม่งั้นการล็อกบัญชีไม่มีผล
    - บัญชีที่ถูกล็อกต้องได้ 429 พร้อม Retry-After **ก่อน** ตรวจรหัสผ่าน
    - อีเมลที่ไม่มีในระบบกับรหัสผิด ต้องได้ข้อความเดียวกัน
    - ขอรีเซ็ตรหัสผ่านต้องตอบเหมือนกันเสมอ ไม่ว่าอีเมลจะมีจริงหรือไม่
    - ตั้งรหัสผ่านใหม่สำเร็จต้องถอนทุกเซสชัน
    - refresh ต้องหมุน token — ใบเดิมถูกเพิกถอน

ทั้งหมดเป็น offline: ไม่ต่อฐานข้อมูลจริง ไม่ส่งอีเมล ไม่แตะ production

    python -m eval.auth_routes_check
"""
from __future__ import annotations

import os
import sys
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres@127.0.0.1:55432/course_advisor")
os.environ.setdefault("JWT_SECRET", "local-test-only")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.api import deps  # noqa: E402
from app.api.routes import auth as route  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.session import get_db  # noqa: E402

PASSWORD = "รหัสผ่านทดสอบ-12345"
OTHER = "รหัสผ่านผิด-99999"


def make_user(**over):
    user = SimpleNamespace(
        id=uuid.uuid4(), email="staff@example.ac.th", full_name="ผู้ดูแล",
        password_hash=hash_password(PASSWORD), is_active=True, is_admin=False,
        role="editor", status="approved", email_verified_at=None,
        failed_login_count=0, locked_until=None, last_login_at=None,
    )
    for k, v in over.items():
        setattr(user, k, v)
    return user


class FakeQuery:
    def __init__(self, user):
        self._user = user

    def filter(self, *_a, **_k):
        return self

    def first(self):
        return self._user


class FakeDB:
    def __init__(self, user=None):
        self.user = user
        self.statements: list[str] = []
        self.params: list[dict] = []
        self.commits = 0

    def query(self, *_a, **_k):
        return FakeQuery(self.user)

    def get(self, _model, _id):
        return self.user

    def execute(self, statement, params=None):
        self.statements.append(" ".join(str(statement).split()))
        self.params.append(params or {})
        return SimpleNamespace(
            mappings=lambda: SimpleNamespace(first=lambda: None),
            rowcount=1,
        )

    def commit(self):
        self.commits += 1

    def add(self, _obj):
        pass

    def refresh(self, _obj):
        pass

    def ran(self, fragment: str) -> bool:
        return any(fragment in s for s in self.statements)


class Base(unittest.TestCase):
    def setUp(self):
        # ตัวจำกัดตาม IP เป็น state ระดับโมดูล — ล้างก่อนทุกข้อ ไม่งั้นข้อหลัง ๆ ได้ 429
        # จากการนับของข้อก่อนหน้า ซึ่งไม่ใช่สิ่งที่ข้อนั้นตั้งใจทดสอบ
        deps._login_bucket.clear()

    def client(self, db):
        app = FastAPI()
        app.include_router(route.router)
        app.dependency_overrides[get_db] = lambda: db
        self.db = db
        return TestClient(app)

    def login(self, db, password=PASSWORD, email="staff@example.ac.th"):
        return self.client(db).post("/auth/login", json={"email": email, "password": password})


class LoginChecks(Base):
    def test_รหัสถูกได้_token_ครบ(self):
        r = self.login(FakeDB(make_user()))
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["access_token"])
        self.assertTrue(body["refresh_token"])

    def test_คืนสิทธิ์มาพร้อม_token(self):
        body = self.login(FakeDB(make_user())).json()
        self.assertEqual(body["user"]["role"], "editor")
        self.assertEqual(body["user"]["status"], "approved")

    def test_ไม่คืน_password_hash_กลับไป(self):
        self.assertNotIn("password_hash", self.login(FakeDB(make_user())).text)

    def test_รหัสผิดได้_401(self):
        self.assertEqual(self.login(FakeDB(make_user()), OTHER).status_code, 401)

    def test_รหัสผิดต้องนับความล้มเหลว(self):
        """ไม่นับ = การล็อกบัญชีไม่มีผลเลย"""
        db = FakeDB(make_user())
        self.login(db, OTHER)
        self.assertTrue(db.ran("set failed_login_count = :c"))

    def test_รหัสถูกต้องล้างตัวนับ(self):
        db = FakeDB(make_user(failed_login_count=3))
        self.login(db)
        self.assertTrue(db.ran("set failed_login_count = 0"))

    def test_ไม่พบอีเมลได้_401_ข้อความเดียวกับรหัสผิด(self):
        a = self.login(FakeDB(None)).json()["detail"]
        b = self.login(FakeDB(make_user()), OTHER).json()["detail"]
        self.assertEqual(a, b)

    def test_ไม่พบอีเมลไม่พยายามนับความล้มเหลว(self):
        db = FakeDB(None)
        self.login(db)
        self.assertFalse(db.ran("failed_login_count"))

    def test_บัญชีถูกปิดใช้งานเข้าไม่ได้(self):
        self.assertEqual(self.login(FakeDB(make_user(is_active=False))).status_code, 401)

    def test_บัญชีที่ยังไม่อนุมัติยังเข้าสู่ระบบได้(self):
        """เข้าสู่ระบบได้แต่เข้าส่วนผู้ดูแลไม่ได้ — ด่านนั้นอยู่ที่ require_staff"""
        r = self.login(FakeDB(make_user(status="pending")))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["user"]["status"], "pending")

    def test_บันทึกทะเบียนเซสชันทุกครั้งที่เข้าได้(self):
        db = FakeDB(make_user())
        self.login(db)
        self.assertTrue(db.ran("insert into public.auth_sessions"))

    def test_ไม่เก็บ_refresh_token_ดิบลงฐานข้อมูล(self):
        """ข้อสำคัญสุด — ฐานข้อมูลรั่วแล้ว token ที่เก็บไว้ต้องใช้ไม่ได้"""
        db = FakeDB(make_user())
        raw = self.login(db).json()["refresh_token"]
        for params in db.params:
            for value in params.values():
                self.assertNotEqual(value, raw)


class LockoutChecks(Base):
    def test_บัญชีที่ถูกล็อกได้_429(self):
        locked = make_user(locked_until=datetime.now(timezone.utc) + timedelta(minutes=10))
        self.assertEqual(self.login(FakeDB(locked)).status_code, 429)

    def test_ล็อกแล้วแจ้งเวลาที่ต้องรอ(self):
        locked = make_user(locked_until=datetime.now(timezone.utc) + timedelta(minutes=10))
        r = self.login(FakeDB(locked))
        self.assertIn("Retry-After", r.headers)
        self.assertGreater(int(r.headers["Retry-After"]), 0)

    def test_ถูกล็อกแล้วแม้รหัสถูกก็เข้าไม่ได้(self):
        locked = make_user(locked_until=datetime.now(timezone.utc) + timedelta(minutes=10))
        self.assertEqual(self.login(FakeDB(locked), PASSWORD).status_code, 429)

    def test_ล็อกหมดอายุแล้วเข้าได้ตามปกติ(self):
        expired = make_user(locked_until=datetime.now(timezone.utc) - timedelta(minutes=1))
        self.assertEqual(self.login(FakeDB(expired)).status_code, 200)


class ResetChecks(Base):
    def test_ขอรีเซ็ตตอบเหมือนกันเมื่อมีอีเมลจริง(self):
        with mock.patch.object(route, "send_account_email"):
            r = self.client(FakeDB(make_user())).post(
                "/auth/password-reset/request", json={"email": "staff@example.ac.th"})
        self.assertEqual(r.status_code, 202)
        self.assertIn("ถ้าอีเมลนี้มีในระบบ", r.json()["detail"])

    def test_ขอรีเซ็ตตอบเหมือนกันเมื่อไม่มีอีเมลนั้น(self):
        """ตอบต่างกัน = หน้านี้กลายเป็นเครื่องมือตรวจว่าใครเป็นสมาชิก"""
        a = self.client(FakeDB(make_user())).post(
            "/auth/password-reset/request", json={"email": "staff@example.ac.th"})
        b = self.client(FakeDB(None)).post(
            "/auth/password-reset/request", json={"email": "ไม่มี@example.ac.th"})
        self.assertEqual(a.status_code, b.status_code)
        self.assertEqual(a.json(), b.json())

    def test_ส่งอีเมลไม่ได้ก็ยังตอบเหมือนเดิม(self):
        with mock.patch.object(route, "send_account_email",
                               side_effect=route.EmailNotConfigured("x")):
            r = self.client(FakeDB(make_user())).post(
                "/auth/password-reset/request", json={"email": "staff@example.ac.th"})
        self.assertEqual(r.status_code, 202)

    def test_token_ผิดตั้งรหัสใหม่ไม่ได้(self):
        db = FakeDB(make_user())
        r = self.client(db).post("/auth/password-reset/confirm",
                                 json={"token": "มั่ว", "new_password": "รหัสใหม่12345"})
        self.assertEqual(r.status_code, 400)

    def test_รหัสใหม่สั้นเกินไปถูกปฏิเสธ(self):
        r = self.client(FakeDB(make_user())).post(
            "/auth/password-reset/confirm", json={"token": "x", "new_password": "สั้น"})
        self.assertEqual(r.status_code, 422)

    def test_ตั้งรหัสใหม่สำเร็จต้องถอนทุกเซสชัน(self):
        user = make_user()
        db = FakeDB(user)
        with mock.patch.object(route.auth, "consume_auth_token", return_value=str(user.id)):
            r = self.client(db).post("/auth/password-reset/confirm",
                                     json={"token": "ok", "new_password": "รหัสใหม่12345"})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(db.ran("update public.auth_sessions set revoked_at"))

    def test_ตั้งรหัสใหม่สำเร็จต้องปลดล็อกบัญชี(self):
        user = make_user(failed_login_count=9,
                         locked_until=datetime.now(timezone.utc) + timedelta(hours=1))
        db = FakeDB(user)
        with mock.patch.object(route.auth, "consume_auth_token", return_value=str(user.id)):
            self.client(db).post("/auth/password-reset/confirm",
                                 json={"token": "ok", "new_password": "รหัสใหม่12345"})
        self.assertEqual(user.failed_login_count, 0)
        self.assertIsNone(user.locked_until)


class SessionChecks(Base):
    def test_refresh_ที่ใช้ไม่ได้ได้_401(self):
        db = FakeDB(make_user())
        with mock.patch.object(route.auth, "session_user_id", return_value=None):
            r = self.client(db).post("/auth/refresh", json={"refresh_token": "มั่ว"})
        self.assertEqual(r.status_code, 401)

    def test_refresh_สำเร็จต้องเพิกถอนใบเดิม(self):
        user = make_user()
        db = FakeDB(user)
        with mock.patch.object(route.auth, "session_user_id", return_value=str(user.id)):
            r = self.client(db).post("/auth/refresh", json={"refresh_token": "ใบเดิม"})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(db.ran("update public.auth_sessions set revoked_at"))
        self.assertTrue(db.ran("insert into public.auth_sessions"))

    def test_refresh_ได้ใบใหม่ที่ไม่ซ้ำของเดิม(self):
        user = make_user()
        db = FakeDB(user)
        with mock.patch.object(route.auth, "session_user_id", return_value=str(user.id)):
            body = self.client(db).post("/auth/refresh", json={"refresh_token": "ใบเดิม"}).json()
        self.assertNotEqual(body["refresh_token"], "ใบเดิม")

    def test_ออกจากระบบตอบ_204_เสมอ(self):
        for valid in (True, False):
            db = FakeDB(make_user())
            with mock.patch.object(route.auth, "revoke_session", return_value=valid):
                r = self.client(db).post("/auth/logout", json={"refresh_token": "x"})
            self.assertEqual(r.status_code, 204)


class RegisterChecks(Base):
    def test_สมัครแล้วได้สถานะรออนุมัติเสมอ(self):
        created = {}

        class DB(FakeDB):
            def add(self, obj):
                created["role"] = obj.role
                created["status"] = obj.status
                # ฐานข้อมูลจริงเติมสองค่านี้ตอน flush — ของปลอมต้องเติมเอง
                # ไม่งั้น UserOut ตรวจไม่ผ่านด้วยเหตุที่ไม่เกี่ยวกับสิ่งที่ข้อนี้ทดสอบ
                obj.id = uuid.uuid4()
                obj.created_at = datetime.now(timezone.utc)

        with mock.patch.object(route, "send_account_email"):
            self.client(DB(None)).post("/auth/register", json={
                "email": "new@example.ac.th", "password": "รหัสผ่าน12345", "full_name": "คนใหม่"})
        self.assertEqual(created["role"], "user")
        self.assertEqual(created["status"], "pending")

    def test_อีเมลซ้ำได้_409(self):
        r = self.client(FakeDB(make_user())).post("/auth/register", json={
            "email": "staff@example.ac.th", "password": "รหัสผ่าน12345", "full_name": "ซ้ำ"})
        self.assertEqual(r.status_code, 409)


class SecretHygieneChecks(unittest.TestCase):
    def test_ไฟล์เส้นทางไม่มีการเขียน_log(self):
        src = (Path(__file__).resolve().parents[1] / "backend" / "app" / "api" / "routes"
               / "auth.py").read_text(encoding="utf-8")
        for word in ("logger.", "logging.", "print("):
            self.assertNotIn(word, src)

    def test_ตัวส่งอีเมลไม่มีการเขียน_log(self):
        src = (Path(__file__).resolve().parents[1] / "backend" / "app" / "services"
               / "mailer.py").read_text(encoding="utf-8")
        for word in ("logger.", "logging.", "print("):
            self.assertNotIn(word, src)


if __name__ == "__main__":
    unittest.main()
