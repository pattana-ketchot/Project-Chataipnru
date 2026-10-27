"""
ตรวจสคริปต์ย้ายบัญชีและย้ายไฟล์ — Phase 4

ทั้งสองสคริปต์เขียนข้อมูลจริงและแตะค่าลับ ชุดนี้ตรวจตรรกะล้วนแบบ offline
ส่วนการรันจริงอยู่ในขั้น deploy

ข้อกำหนดที่ห้ามหลุด
    - **ไม่มีค่าลับหลุดออกมาทางข้อความที่พิมพ์** (อีเมล · hash · คีย์ · URL)
    - role/status ที่ไม่รู้จักต้องถูกลดเป็นสิทธิ์ต่ำสุด ไม่ใช่ปล่อยผ่าน
    - ผู้ใช้ที่ไม่มีรหัสผ่าน (OAuth) ต้องถูกข้าม ไม่ใช่สร้างบัญชีที่เข้าไม่ได้
    - การแก้ URL ในฐานข้อมูลต้องทำ **หลังไฟล์ครบแล้วเท่านั้น**
    - พาธปลายทางต้องอยู่ใต้โฟลเดอร์ที่กำหนดเสมอ

    python -m eval.migration_scripts_check
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pipeline.web import import_accounts as acc  # noqa: E402
from pipeline.web import migrate_storage as st  # noqa: E402

SUPA_ID = "11111111-2222-3333-4444-555555555555"
HASH = "$2a$10$abcdefghijklmnopqrstuvwxyz0123456789ABCDEFGHIJKLMNOPQR"


def account(**over):
    row = {"id": SUPA_ID, "email": "someone@example.ac.th", "encrypted_password": HASH,
           "email_confirmed_at": "2026-01-01", "full_name": "ชื่อ",
           "profile_role": "editor", "profile_status": "approved"}
    row.update(over)
    return row


class AccountChecks(unittest.TestCase):
    def test_แปลงแถวปกติได้ครบ(self):
        out = acc.normalise(account())
        self.assertEqual(out["email"], "someone@example.ac.th")
        self.assertEqual(out["password_hash"], HASH)
        self.assertEqual(out["role"], "editor")
        self.assertEqual(out["status"], "approved")
        self.assertEqual(out["supabase_user_id"], SUPA_ID)

    def test_ไม่มีรหัสผ่านถูกข้าม(self):
        """บัญชีที่สมัครด้วย OAuth — สร้างให้ก็เข้าไม่ได้ และจะบังรายการจริง"""
        self.assertIsNone(acc.normalise(account(encrypted_password=None)))
        self.assertIsNone(acc.normalise(account(encrypted_password="")))

    def test_ไม่มีโปรไฟล์ได้สิทธิ์ต่ำสุด(self):
        out = acc.normalise(account(profile_role=None, profile_status=None))
        self.assertEqual((out["role"], out["status"]), ("user", "pending"))

    def test_role_ที่ไม่รู้จักถูกลดเป็นผู้ใช้ทั่วไป(self):
        """ให้สิทธิ์เกินอันตรายกว่าให้น้อยไป"""
        for bad in ("superuser", "ADMIN", "owner", ""):
            self.assertEqual(acc.normalise(account(profile_role=bad))["role"], "user", bad)

    def test_status_ที่ไม่รู้จักถูกลดเป็นรออนุมัติ(self):
        for bad in ("active", "APPROVED", "ok", ""):
            self.assertEqual(acc.normalise(account(profile_status=bad))["status"], "pending", bad)

    def test_role_admin_ที่ถูกต้องยังเป็น_admin(self):
        self.assertEqual(acc.normalise(account(profile_role="admin"))["role"], "admin")

    def test_สรุปผลไม่มีอีเมลหรือ_hash_ปนออกมา(self):
        """รายงานต้องบอกจำนวน ไม่ใช่ตัวตน"""
        report = str(acc.summarise([account(), account(encrypted_password=None)]))
        self.assertNotIn("example.ac.th", report)
        self.assertNotIn(HASH[:20], report)
        self.assertNotIn(SUPA_ID, report)

    def test_สรุปผลนับถูก(self):
        report = acc.summarise([account(), account(profile_role="admin"),
                                account(encrypted_password=None)])
        self.assertEqual(report["ทั้งหมด"], 3)
        self.assertEqual(report["ย้ายได้"], 2)
        self.assertEqual(report["ข้าม (ไม่มีรหัสผ่าน)"], 1)

    def test_คำสั่งเขียนไม่ทับรหัสผ่านของบัญชีที่มีอยู่แล้ว(self):
        """เขียนทับคือย้อนรหัสผ่านกลับเป็นของเก่า ซึ่งเจ้าของอาจเปลี่ยนไปแล้ว"""
        self.assertNotIn("password_hash = excluded", acc.UPSERT)
        self.assertNotIn("password_scheme = excluded", acc.UPSERT)

    def test_คำสั่งเขียนไม่ทับ_role_หรือ_status_ที่ตั้งไว้แล้ว(self):
        self.assertNotIn("role = excluded", acc.UPSERT)
        self.assertNotIn("status = excluded", acc.UPSERT)

    def test_แถวที่นำเข้าถูกทำเครื่องหมายเป็นรูปแบบ_bcrypt(self):
        self.assertIn("'bcrypt'", acc.UPSERT)

    def test_อ่านจาก_auth_users_ของต้นทาง(self):
        self.assertIn("from auth.users", acc.SELECT_ACCOUNTS)
        self.assertNotIn("insert", acc.SELECT_ACCOUNTS.lower())


class StorageUrlChecks(unittest.TestCase):
    def test_รู้จัก_url_ของ_supabase(self):
        self.assertTrue(st.is_supabase_url("https://abc.supabase.co/storage/v1/object/x.png"))
        self.assertTrue(st.is_supabase_url("https://abc.supabase.in/storage/v1/object/x.png"))

    def test_url_ที่ย้ายแล้วไม่ถูกย้ายซ้ำ(self):
        self.assertFalse(st.is_supabase_url("/api/uploads/logo/ab/abc.png"))
        self.assertFalse(st.is_supabase_url("https://sci.pnru.ac.th/x.png"))
        self.assertFalse(st.is_supabase_url(""))

    def test_รู้จัก_key_ภายใน_bucket(self):
        self.assertTrue(st.is_storage_key("abc-123.pdf", "knowledge"))
        self.assertFalse(st.is_storage_key("https://x/y.pdf", "knowledge"))
        self.assertFalse(st.is_storage_key("/api/uploads/x.pdf", "knowledge"))

    def test_ประกอบ_url_ดาวน์โหลดจาก_key_ได้(self):
        item = st.Item(table="web.knowledge_articles", column="file_path",
                       category="knowledge", original="abc 123.pdf")
        url = st.download_url_for("https://abc.supabase.co", item)
        self.assertIn("/storage/v1/object/knowledge-files/", url)
        self.assertIn("abc%20123.pdf", url, "ชื่อไฟล์ต้องถูก encode")

    def test_url_เต็มถูกใช้ตามเดิม(self):
        item = st.Item(table="web.site_courses", column="logo_url", category="logo",
                       original="https://abc.supabase.co/storage/v1/object/public/a.png")
        self.assertEqual(st.download_url_for("https://abc.supabase.co", item), item.original)

    def test_หมวดของแต่ละคอลัมน์ถูกต้อง(self):
        by_column = {(s["table"], s["column"]): s["category"] for s in st.SOURCES}
        self.assertEqual(by_column[("web.knowledge_articles", "file_path")], "knowledge")
        self.assertEqual(by_column[("web.site_courses", "logo_url")], "logo")

    def test_ไฟล์คลังความรู้อยู่ในหมวดที่ต้องล็อกอิน(self):
        sys.path.insert(0, str(REPO / "backend"))
        import os
        os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://x@127.0.0.1/x")
        os.environ.setdefault("JWT_SECRET", "t")
        from app.services import file_store
        self.assertIn("knowledge", file_store.PRIVATE_CATEGORIES)


class StorageSafetyChecks(unittest.TestCase):
    def setUp(self):
        self.src = (REPO / "pipeline" / "web" / "migrate_storage.py").read_text(encoding="utf-8")

    def test_แก้_url_ในฐานข้อมูลหลังไฟล์ครบเท่านั้น(self):
        """ไฟล์ขาดแล้วแก้ URL = ลิงก์เสียถาวร"""
        self.assertIn("ยังไม่แก้ URL ในฐานข้อมูล", self.src)
        before_rewrite = self.src.index("rewrite_urls(conn, done)")
        guard = self.src.index('if failed:')
        self.assertLess(guard, before_rewrite, "ด่านตรวจไฟล์ครบต้องมาก่อนการแก้ URL")

    def test_ไม่พิมพ์ค่าคีย์หรือ_url_ออกมา(self):
        for bad in ('print(service_key', 'print(url', 'print(base_url',
                    'print(f"{url', "print(f'{url"):
            self.assertNotIn(bad, self.src)

    def test_คีย์ส่งทาง_header_ไม่ใช่ใน_url(self):
        self.assertIn('"Authorization": f"Bearer {service_key}"', self.src)
        self.assertNotIn("?apikey=", self.src)
        self.assertNotIn("&apikey=", self.src)

    def test_มีการ_retry(self):
        self.assertGreaterEqual(st.RETRIES, 2)
        self.assertIn("time.sleep", self.src)

    def test_ไม่ลองซ้ำเมื่อสิทธิ์ไม่พอหรือไม่มีไฟล์(self):
        """401/403/404 ลองใหม่กี่ครั้งก็ไม่ช่วย"""
        self.assertIn("if exc.code in (401, 403, 404)", self.src)

    def test_ตรวจ_checksum_จากไฟล์บนดิสก์จริง(self):
        self.assertIn("hashlib.sha256(target.read_bytes())", self.src)

    def test_กันพาธออกนอกโฟลเดอร์(self):
        self.assertIn("ออกนอกโฟลเดอร์ที่กำหนด", self.src)

    def test_มี_manifest(self):
        self.assertIn("MANIFEST_NAME", self.src)
        self.assertIn("json.dumps", self.src)

    def test_ไม่เขียนทับไฟล์ที่มีอยู่แล้ว(self):
        self.assertIn("if not target.exists()", self.src)

    def test_ค่าตั้งต้นคือโหมดลอง(self):
        for src in (self.src, (REPO / "pipeline" / "web"
                               / "import_accounts.py").read_text(encoding="utf-8")):
            self.assertIn("args.apply and not args.dry_run", src)


if __name__ == "__main__":
    unittest.main()
