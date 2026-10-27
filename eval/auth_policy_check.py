"""
ตรวจนโยบายของระบบเข้าสู่ระบบที่มาแทน Supabase Auth — Phase 4

เหตุที่ต้องมี: ด่านสิทธิ์ทั้งระบบตัดสินจากฟังก์ชันไม่กี่ตัวในไฟล์นี้ ถ้าพลาดคือ
ผู้ใช้ทั่วไปเข้าหน้าผู้ดูแลได้ หรือผู้ดูแลตัวจริงเข้าไม่ได้ ซึ่งร้ายทั้งคู่

ข้อกำหนดที่ห้ามหลุด
    - เข้าส่วนผู้ดูแลได้ต้องเป็น staff **และ** อนุมัติแล้ว ขาดข้อใดข้อหนึ่งไม่ผ่าน
    - ลบได้เฉพาะ admin — ตรงกับที่หน้าเว็บซ่อนปุ่มลบจาก editor
    - token เก็บเป็น hash เสมอ ค่าดิบห้ามเท่ากับค่าที่เก็บ
    - การล็อกบัญชีต้องมีวันสิ้นสุด ไม่ใช่ล็อกถาวร

ทั้งหมดเป็น offline: ไม่ต่อฐานข้อมูล ไม่แตะ production

    python -m eval.auth_policy_check
"""
from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres@127.0.0.1:55432/course_advisor")
os.environ.setdefault("JWT_SECRET", "local-test-only")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.services import auth_service as a  # noqa: E402

NOW = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)


class AdminGateChecks(unittest.TestCase):
    def test_admin_ที่อนุมัติแล้วเข้าได้(self):
        self.assertTrue(a.can_access_admin("admin", "approved"))

    def test_editor_ที่อนุมัติแล้วเข้าได้(self):
        self.assertTrue(a.can_access_admin("editor", "approved"))

    def test_ผู้ใช้ทั่วไปเข้าไม่ได้แม้อนุมัติแล้ว(self):
        self.assertFalse(a.can_access_admin("user", "approved"))

    def test_admin_ที่ยังไม่อนุมัติเข้าไม่ได้(self):
        self.assertFalse(a.can_access_admin("admin", "pending"))

    def test_admin_ที่ถูกปฏิเสธเข้าไม่ได้(self):
        self.assertFalse(a.can_access_admin("admin", "rejected"))

    def test_ค่าว่างเข้าไม่ได้(self):
        self.assertFalse(a.can_access_admin(None, None))
        self.assertFalse(a.can_access_admin("", ""))

    def test_ค่าที่ไม่รู้จักเข้าไม่ได้(self):
        self.assertFalse(a.can_access_admin("superuser", "approved"))
        self.assertFalse(a.can_access_admin("admin", "active"))

    def test_ตัวพิมพ์ต่างกันไม่ผ่าน(self):
        """เทียบตรงตัว ถ้ายอมรับ Admin จะกลายเป็นสองค่าที่หมายถึงอย่างเดียวกัน"""
        self.assertFalse(a.can_access_admin("Admin", "approved"))
        self.assertFalse(a.can_access_admin("admin", "Approved"))


class DeleteGateChecks(unittest.TestCase):
    def test_admin_ลบได้(self):
        self.assertTrue(a.can_delete("admin", "approved"))

    def test_editor_ลบไม่ได้(self):
        """หน้าเว็บซ่อนปุ่มลบจาก editor — หลังบ้านต้องปฏิเสธด้วย ไม่ใช่พึ่งการซ่อนปุ่ม"""
        self.assertFalse(a.can_delete("editor", "approved"))
        self.assertTrue(a.can_edit("editor", "approved"))

    def test_admin_ที่ยังไม่อนุมัติลบไม่ได้(self):
        self.assertFalse(a.can_delete("admin", "pending"))


class TokenChecks(unittest.TestCase):
    def test_token_ใหม่ยาวพอและไม่ซ้ำ(self):
        tokens = {a.new_token() for _ in range(200)}
        self.assertEqual(len(tokens), 200)
        self.assertTrue(all(len(t) >= 32 for t in tokens))

    def test_hash_ไม่เท่ากับค่าดิบ(self):
        raw = a.new_token()
        self.assertNotEqual(a.hash_token(raw), raw)

    def test_hash_เท่าเดิมทุกครั้ง(self):
        raw = a.new_token()
        self.assertEqual(a.hash_token(raw), a.hash_token(raw))

    def test_ค่าต่างกันได้_hash_ต่างกัน(self):
        self.assertNotEqual(a.hash_token("ก"), a.hash_token("ข"))

    def test_hash_เป็น_sha256_ความยาวคงที่(self):
        self.assertEqual(len(a.hash_token(a.new_token())), 64)


class ExpiryChecks(unittest.TestCase):
    def test_รีเซ็ตรหัสผ่านหมดอายุใน_1_ชั่วโมง(self):
        self.assertEqual(a.token_expiry("password_reset", NOW), NOW + timedelta(hours=1))

    def test_ยืนยันอีเมลหมดอายุใน_24_ชั่วโมง(self):
        self.assertEqual(a.token_expiry("email_verify", NOW), NOW + timedelta(hours=24))

    def test_purpose_ที่ไม่รู้จักต้องล้ม(self):
        with self.assertRaises(ValueError):
            a.token_expiry("อย่างอื่น", NOW)

    def test_รีเซ็ตรหัสผ่านอายุสั้นกว่ายืนยันอีเมล(self):
        self.assertLess(a.token_expiry("password_reset", NOW), a.token_expiry("email_verify", NOW))


class LockChecks(unittest.TestCase):
    def test_ยังไม่เคยถูกล็อก(self):
        self.assertFalse(a.lock_state(None, NOW).locked)

    def test_ล็อกหมดอายุแล้วถือว่าไม่ล็อก(self):
        self.assertFalse(a.lock_state(NOW - timedelta(seconds=1), NOW).locked)

    def test_ยังอยู่ในช่วงล็อก(self):
        st = a.lock_state(NOW + timedelta(minutes=5), NOW)
        self.assertTrue(st.locked)
        self.assertEqual(st.retry_after_seconds, 300)

    def test_เวลารอต้องไม่เป็นศูนย์เมื่อยังล็อกอยู่(self):
        st = a.lock_state(NOW + timedelta(milliseconds=1), NOW)
        self.assertTrue(st.locked)
        self.assertGreaterEqual(st.retry_after_seconds, 1)

    def test_พลาดไม่กี่ครั้งยังไม่ล็อก(self):
        for n in range(a.FAILURES_BEFORE_LOCK - 1):
            count, until = a.next_failure(n, NOW)
            self.assertEqual(count, n + 1)
            self.assertIsNone(until, f"พลาด {n + 1} ครั้งไม่ควรล็อก")

    def test_ครบจำนวนแล้วล็อกสั้น(self):
        count, until = a.next_failure(a.FAILURES_BEFORE_LOCK - 1, NOW)
        self.assertEqual(count, a.FAILURES_BEFORE_LOCK)
        self.assertEqual(until, NOW + timedelta(minutes=a.LOCK_MINUTES))

    def test_พลาดมากขึ้นล็อกนานขึ้น(self):
        _, until = a.next_failure(a.FAILURES_BEFORE_LONG_LOCK - 1, NOW)
        self.assertEqual(until, NOW + timedelta(minutes=a.LONG_LOCK_MINUTES))

    def test_การล็อกมีวันสิ้นสุดเสมอ(self):
        """ล็อกถาวรคือเปิดช่องให้คนร้ายทำให้เจ้าของบัญชีเข้าไม่ได้ตลอดไป"""
        for n in range(0, 50):
            _, until = a.next_failure(n, NOW)
            if until is not None:
                self.assertLessEqual(until, NOW + timedelta(hours=2))

    def test_ล็อกสั้นกว่าหนึ่งวันเสมอ(self):
        self.assertLess(a.LONG_LOCK_MINUTES, 24 * 60)


class SecretHygieneChecks(unittest.TestCase):
    def test_ไม่มีการเขียน_log_ในไฟล์นโยบาย(self):
        """กันรหัสผ่านหรือ token หลุดลง log โดยไม่ตั้งใจ"""
        src = (Path(__file__).resolve().parents[1] / "backend" / "app" / "services"
               / "auth_service.py").read_text(encoding="utf-8")
        for word in ("logger.", "logging.", "print("):
            self.assertNotIn(word, src, f"ไฟล์นโยบายไม่ควรมี {word}")

    def test_เก็บลงฐานข้อมูลด้วย_hash_token_เสมอ(self):
        src = (Path(__file__).resolve().parents[1] / "backend" / "app" / "services"
               / "auth_service.py").read_text(encoding="utf-8")
        # ทุกที่ที่ผูกค่า token เข้ากับ SQL ต้องผ่าน hash_token
        self.assertIn('"h": hash_token(refresh_token)', src)
        self.assertIn('"h": hash_token(raw)', src)
        self.assertNotIn('"h": refresh_token', src)
        self.assertNotIn('"h": raw', src)


if __name__ == "__main__":
    unittest.main()
