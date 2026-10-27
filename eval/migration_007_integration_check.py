"""
ตรวจ migration 007 กับ **PostgreSQL จริง** — Phase 4

ต่างจากชุดอื่นใน eval/ ตรงที่ชุดนี้ **ต้องมีฐานข้อมูลจริง** ไม่ใช่ของปลอม
เพราะสิ่งที่ตรวจคือพฤติกรรมของ trigger เงื่อนไข WHERE และการรันซ้ำ
ซึ่งของปลอมยืนยันไม่ได้เลย

    TEST_DATABASE_URL=postgresql://postgres:...@127.0.0.1:55433/phase4_test \
        python -m eval.migration_007_integration_check

‼ ชี้ไปที่ฐานข้อมูล **ทดสอบ** เท่านั้น — ชุดนี้สร้างและลบผู้ใช้
   มีด่านกันไว้: ปฏิเสธถ้าชื่อฐานข้อมูลไม่มีคำว่า test

ข้อที่สำคัญที่สุดสามข้อ
    1. **รันซ้ำต้องไม่อนุมัติบัญชีที่สมัครหลัง migration**
       รุ่นแรกเขียน `created_at < now()` ซึ่งเป็นจริงเสมอ การรันซ้ำจึงอนุมัติให้หมด
    2. **trigger ต้องทำงานจริง** รุ่นแรกใช้ `UPDATE SET role = role` ซึ่งไม่ทำให้
       เงื่อนไข IS DISTINCT FROM เป็นจริง จึงไม่เคยซิงค์อะไรเลย
    3. **ถอนกลับต้องคืน is_admin จากหลักฐาน** ไม่ใช่จากการเดา
"""
from __future__ import annotations

import os
import sys
import unittest
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MIGRATION = REPO / "db" / "migrations" / "007_web_auth.sql"

DSN = os.environ.get("TEST_DATABASE_URL", "")


def _guard(dsn: str) -> str:
    """กันการเผลอชี้ไปฐานข้อมูลจริง"""
    if not dsn:
        raise SystemExit("ต้องตั้ง TEST_DATABASE_URL ก่อน")
    name = dsn.rsplit("/", 1)[-1].split("?")[0]
    if "test" not in name.lower():
        raise SystemExit(f"ปฏิเสธ: ชื่อฐานข้อมูล {name!r} ไม่มีคำว่า test — ชุดนี้เขียนข้อมูลจริง")
    return dsn


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg
        cls.conn = psycopg.connect(_guard(DSN), autocommit=True)
        cls.sql = MIGRATION.read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    # ── เครื่องมือ ───────────────────────────────────────────────────
    def run_migration(self):
        """รัน 007 ทั้งไฟล์ (ตัดบล็อกคอมเมนต์ถอนกลับท้ายไฟล์ออก)"""
        body = self.sql.split("-- ถอนกลับ — คืนค่าจากหลักฐาน")[0]
        self.conn.execute(body)

    def reset(self):
        """คืนฐานทดสอบให้เหมือนก่อนเคยรัน 007"""
        self.conn.execute("DROP TRIGGER IF EXISTS trg_sync_user_admin_flag ON public.users")
        self.conn.execute("DROP FUNCTION IF EXISTS public.sync_user_admin_flag()")
        self.conn.execute("DROP TABLE IF EXISTS public.auth_tokens")
        self.conn.execute("DROP TABLE IF EXISTS public.auth_sessions")
        self.conn.execute("DROP TABLE IF EXISTS public.migration_007_user_backup")
        for col in ("role", "status", "email_verified_at", "failed_login_count",
                    "locked_until", "last_login_at", "password_scheme"):
            self.conn.execute(f"ALTER TABLE public.users DROP COLUMN IF EXISTS {col}")
        for name in ("users_role_check", "users_status_check", "users_password_scheme_check"):
            self.conn.execute(f"ALTER TABLE public.users DROP CONSTRAINT IF EXISTS {name}")
        self.conn.execute("DELETE FROM mko.schema_migrations WHERE version = '007_web_auth'")
        self.conn.execute("DELETE FROM public.users")

    def add_user(self, email: str, is_admin: bool = False) -> str:
        uid = str(uuid.uuid4())
        self.conn.execute(
            "INSERT INTO public.users (id, email, password_hash, is_admin) VALUES (%s,%s,%s,%s)",
            (uid, email, "x", is_admin),
        )
        return uid

    def row(self, uid: str) -> dict:
        cur = self.conn.execute(
            "SELECT role, status, is_admin FROM public.users WHERE id = %s", (uid,))
        role, status, is_admin = cur.fetchone()
        return {"role": role, "status": status, "is_admin": is_admin}

    def setUp(self):
        self.reset()


class FirstRunChecks(Base):
    def test_ผู้ดูแลเดิมได้_role_admin(self):
        uid = self.add_user("admin@example.ac.th", is_admin=True)
        self.run_migration()
        self.assertEqual(self.row(uid), {"role": "admin", "status": "approved", "is_admin": True})

    def test_ผู้ใช้เดิมได้_role_user_และอนุมัติแล้ว(self):
        uid = self.add_user("user@example.ac.th", is_admin=False)
        self.run_migration()
        self.assertEqual(self.row(uid), {"role": "user", "status": "approved", "is_admin": False})

    def test_บันทึกสภาพเดิมไว้ครบทุกแถว(self):
        a = self.add_user("a@example.ac.th", is_admin=True)
        b = self.add_user("b@example.ac.th", is_admin=False)
        self.run_migration()
        cur = self.conn.execute(
            "SELECT user_id, is_admin FROM public.migration_007_user_backup ORDER BY is_admin")
        got = {str(r[0]): r[1] for r in cur.fetchall()}
        self.assertEqual(got, {a: True, b: False})

    def test_บันทึก_version_ลง_schema_migrations(self):
        self.run_migration()
        cur = self.conn.execute(
            "SELECT count(*) FROM mko.schema_migrations WHERE version = '007_web_auth'")
        self.assertEqual(cur.fetchone()[0], 1)


class RerunChecks(Base):
    def test_รันซ้ำไม่อนุมัติบัญชีที่สมัครหลัง_migration(self):
        """
        ข้อสำคัญที่สุดของไฟล์นี้

        รุ่นแรกใช้เงื่อนไข `created_at < now()` ซึ่งเป็นจริงเสมอ
        การรันซ้ำจึงอนุมัติบัญชีที่ยังรออนุมัติทั้งหมดโดยไม่มีใครกด
        """
        self.add_user("old@example.ac.th", is_admin=False)
        self.run_migration()

        # สมัครใหม่หลัง migration — ต้องเป็น pending ตามค่าตั้งต้น
        newbie = self.add_user("newbie@example.ac.th")
        self.assertEqual(self.row(newbie)["status"], "pending")

        self.run_migration()  # รันซ้ำ

        self.assertEqual(self.row(newbie)["status"], "pending",
                         "การรันซ้ำอนุมัติบัญชีที่ยังรออนุมัติ — เป็นการให้สิทธิ์โดยไม่มีใครกด")

    def test_รันซ้ำไม่เปลี่ยน_role_ที่ผู้ดูแลตั้งไว้(self):
        uid = self.add_user("editor@example.ac.th", is_admin=False)
        self.run_migration()
        self.conn.execute("UPDATE public.users SET role = 'editor' WHERE id = %s", (uid,))

        self.run_migration()

        self.assertEqual(self.row(uid)["role"], "editor",
                         "การรันซ้ำลดสิทธิ์ที่ผู้ดูแลตั้งไว้")

    def test_รันซ้ำไม่เปลี่ยนสถานะที่ถูกปฏิเสธไว้(self):
        uid = self.add_user("rejected@example.ac.th")
        self.run_migration()
        self.conn.execute("UPDATE public.users SET status = 'rejected' WHERE id = %s", (uid,))

        self.run_migration()

        self.assertEqual(self.row(uid)["status"], "rejected",
                         "การรันซ้ำปลดการปฏิเสธบัญชี")

    def test_รันซ้ำไม่เขียนทับสภาพเดิมที่บันทึกไว้(self):
        uid = self.add_user("a@example.ac.th", is_admin=True)
        self.run_migration()
        self.conn.execute("UPDATE public.users SET role = 'user' WHERE id = %s", (uid,))

        self.run_migration()

        cur = self.conn.execute(
            "SELECT is_admin FROM public.migration_007_user_backup WHERE user_id = %s", (uid,))
        self.assertTrue(cur.fetchone()[0],
                        "บันทึกสภาพเดิมถูกเขียนทับด้วยสภาพหลังย้าย — ถอนกลับไม่ได้แล้ว")

    def test_รันซ้ำสามรอบไม่เพิ่มแถวในตารางบันทึก(self):
        self.add_user("a@example.ac.th")
        for _ in range(3):
            self.run_migration()
        cur = self.conn.execute("SELECT count(*) FROM public.migration_007_user_backup")
        self.assertEqual(cur.fetchone()[0], 1)

    def test_รันซ้ำไม่ทำให้ข้อมูล_session_หาย(self):
        uid = self.add_user("a@example.ac.th")
        self.run_migration()
        self.conn.execute(
            "INSERT INTO public.auth_sessions (user_id, token_hash, expires_at)"
            " VALUES (%s, 'hash1', now() + interval '1 day')", (uid,))

        self.run_migration()

        cur = self.conn.execute("SELECT count(*) FROM public.auth_sessions")
        self.assertEqual(cur.fetchone()[0], 1)


class TriggerChecks(Base):
    def setUp(self):
        super().setUp()
        self.run_migration()

    def test_ตั้ง_role_admin_แล้ว_is_admin_เป็นจริง(self):
        uid = self.add_user("x@example.ac.th")
        self.conn.execute("UPDATE public.users SET role = 'admin' WHERE id = %s", (uid,))
        self.assertTrue(self.row(uid)["is_admin"])

    def test_ลด_role_แล้ว_is_admin_เป็นเท็จ(self):
        uid = self.add_user("x@example.ac.th", is_admin=True)
        self.conn.execute("UPDATE public.users SET role = 'editor' WHERE id = %s", (uid,))
        self.assertFalse(self.row(uid)["is_admin"])

    def test_เขียน_is_admin_อย่างเดียวไม่มีผล(self):
        """role เป็นแหล่งความจริง — เขียนที่เงาสะท้อนต้องไม่เปลี่ยนสิทธิ์"""
        uid = self.add_user("x@example.ac.th")
        self.conn.execute("UPDATE public.users SET role = 'user' WHERE id = %s", (uid,))
        self.conn.execute("UPDATE public.users SET is_admin = true WHERE id = %s", (uid,))
        self.assertEqual(self.row(uid), {"role": "user", "status": "pending", "is_admin": False})

    def test_เขียนขัดกันในคำสั่งเดียว_role_ชนะ(self):
        uid = self.add_user("x@example.ac.th")
        self.conn.execute(
            "UPDATE public.users SET role = 'editor', is_admin = true WHERE id = %s", (uid,))
        self.assertEqual(self.row(uid)["role"], "editor")
        self.assertFalse(self.row(uid)["is_admin"], "is_admin ชนะ role ซึ่งขัดกับกฎที่ประกาศไว้")

    def test_เขียนขัดกันอีกทาง_role_ก็ยังชนะ(self):
        uid = self.add_user("x@example.ac.th")
        self.conn.execute(
            "UPDATE public.users SET role = 'admin', is_admin = false WHERE id = %s", (uid,))
        self.assertTrue(self.row(uid)["is_admin"])

    def test_แถวใหม่ที่ใส่_is_admin_มาขัดกับ_role(self):
        uid = str(uuid.uuid4())
        self.conn.execute(
            "INSERT INTO public.users (id, email, password_hash, role, is_admin)"
            " VALUES (%s, 'new@example.ac.th', 'x', 'user', true)", (uid,))
        self.assertFalse(self.row(uid)["is_admin"])

    def test_แถวใหม่ที่ตั้ง_role_admin(self):
        uid = str(uuid.uuid4())
        self.conn.execute(
            "INSERT INTO public.users (id, email, password_hash, role)"
            " VALUES (%s, 'new2@example.ac.th', 'x', 'admin')", (uid,))
        self.assertTrue(self.row(uid)["is_admin"])

    def test_แก้ฟิลด์อื่นไม่ทำให้สิทธิ์เพี้ยน(self):
        uid = self.add_user("x@example.ac.th")
        self.conn.execute("UPDATE public.users SET role = 'editor' WHERE id = %s", (uid,))
        self.conn.execute("UPDATE public.users SET full_name = 'ชื่อใหม่' WHERE id = %s", (uid,))
        self.assertEqual(self.row(uid)["role"], "editor")
        self.assertFalse(self.row(uid)["is_admin"])


class ReconcileChecks(Base):
    def test_แถวที่ค่าขัดกันถูกทำให้ตรงกันตอนรัน(self):
        """
        รุ่นแรกใช้ `UPDATE SET role = role` โดยไม่มี WHERE คู่กับ trigger ที่เช็ค
        IS DISTINCT FROM ซึ่งไม่เคยเป็นจริง จึงไม่เคยซิงค์อะไรเลย
        """
        uid = self.add_user("x@example.ac.th", is_admin=False)
        self.run_migration()
        # จำลองค่าที่ขัดกันด้วยการปิด trigger ชั่วคราว
        self.conn.execute("ALTER TABLE public.users DISABLE TRIGGER trg_sync_user_admin_flag")
        self.conn.execute("UPDATE public.users SET role = 'admin' WHERE id = %s", (uid,))
        self.conn.execute("ALTER TABLE public.users ENABLE TRIGGER trg_sync_user_admin_flag")
        self.assertFalse(self.row(uid)["is_admin"], "ตั้งต้นของข้อนี้ต้องขัดกันก่อน")

        self.run_migration()

        self.assertTrue(self.row(uid)["is_admin"], "ขั้นทำให้ตรงกันไม่ทำงาน")

    def test_แถวที่ตรงกันอยู่แล้วไม่ถูกแตะ(self):
        uid = self.add_user("x@example.ac.th", is_admin=True)
        self.run_migration()
        before = self.conn.execute(
            "SELECT updated_at FROM public.users WHERE id = %s", (uid,)).fetchone()[0]
        self.run_migration()
        after = self.conn.execute(
            "SELECT updated_at FROM public.users WHERE id = %s", (uid,)).fetchone()[0]
        self.assertEqual(before, after)


class RollbackChecks(Base):
    def test_ถอนกลับคืน_is_admin_ได้ตรงของเดิม(self):
        keep_admin = self.add_user("admin@example.ac.th", is_admin=True)
        plain = self.add_user("user@example.ac.th", is_admin=False)
        self.run_migration()
        # ผู้ดูแลลดสิทธิ์คนหนึ่งหลังย้าย — is_admin จึงต่างจากของเดิม
        self.conn.execute("UPDATE public.users SET role = 'user' WHERE id = %s", (keep_admin,))
        self.assertFalse(self.row(keep_admin)["is_admin"])

        # ถอนกลับตามที่ไฟล์ระบุ
        self.conn.execute("DROP TRIGGER IF EXISTS trg_sync_user_admin_flag ON public.users")
        self.conn.execute("""
            UPDATE public.users u SET is_admin = b.is_admin
              FROM public.migration_007_user_backup b
             WHERE b.user_id = u.id AND u.is_admin IS DISTINCT FROM b.is_admin
        """)

        cur = self.conn.execute("SELECT is_admin FROM public.users WHERE id = %s", (keep_admin,))
        self.assertTrue(cur.fetchone()[0], "ถอนกลับไม่คืน is_admin ของเดิม")
        cur = self.conn.execute("SELECT is_admin FROM public.users WHERE id = %s", (plain,))
        self.assertFalse(cur.fetchone()[0])

    def test_ผู้ใช้ที่สมัครหลัง_migration_ไม่มีในบันทึกและไม่ถูกแตะ(self):
        self.add_user("old@example.ac.th")
        self.run_migration()
        newbie = self.add_user("new@example.ac.th")

        cur = self.conn.execute(
            "SELECT count(*) FROM public.migration_007_user_backup WHERE user_id = %s", (newbie,))
        self.assertEqual(cur.fetchone()[0], 0)
        self.assertFalse(self.row(newbie)["is_admin"])


class ConstraintChecks(Base):
    def setUp(self):
        super().setUp()
        self.run_migration()

    def test_role_ที่ไม่รู้จักถูกปฏิเสธ(self):
        uid = self.add_user("x@example.ac.th")
        import psycopg
        with self.assertRaises(psycopg.errors.CheckViolation):
            self.conn.execute("UPDATE public.users SET role = 'superuser' WHERE id = %s", (uid,))

    def test_status_ที่ไม่รู้จักถูกปฏิเสธ(self):
        uid = self.add_user("x@example.ac.th")
        import psycopg
        with self.assertRaises(psycopg.errors.CheckViolation):
            self.conn.execute("UPDATE public.users SET status = 'active' WHERE id = %s", (uid,))

    def test_password_scheme_ที่ไม่รู้จักถูกปฏิเสธ(self):
        uid = self.add_user("x@example.ac.th")
        import psycopg
        with self.assertRaises(psycopg.errors.CheckViolation):
            self.conn.execute(
                "UPDATE public.users SET password_scheme = 'md5' WHERE id = %s", (uid,))

    def test_บัญชีใหม่เป็น_pending_และ_bcrypt_sha256(self):
        uid = self.add_user("x@example.ac.th")
        cur = self.conn.execute(
            "SELECT status, password_scheme FROM public.users WHERE id = %s", (uid,))
        self.assertEqual(cur.fetchone(), ("pending", "bcrypt_sha256"))


if __name__ == "__main__":
    unittest.main()
