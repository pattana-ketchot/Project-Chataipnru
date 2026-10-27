"""
ตรวจ Phase 4 ทั้งระบบกับ **PostgreSQL จริง** — login · session · CRUD · ไฟล์ · sync

ต่างจากชุดอื่นใน eval/ ที่ใช้ฐานข้อมูลปลอม ชุดนี้ยิงผ่าน FastAPI จริงลงฐานข้อมูลจริง
จึงยืนยันสิ่งที่ของปลอมยืนยันไม่ได้ — คำสั่ง SQL รันผ่านจริงไหม · constraint ทำงานไหม ·
transaction ย้อนจริงไหม · trigger มีผลกับเส้นทาง API ไหม

    TEST_DATABASE_URL=postgresql://postgres:...@127.0.0.1:55433/phase4_test \
        python -m eval.phase4_integration_check

‼ ชี้ไปที่ฐานข้อมูล **ทดสอบ** เท่านั้น — ชุดนี้สร้างและลบข้อมูล
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DSN = os.environ.get("TEST_DATABASE_URL", "")


def _guard(dsn: str) -> str:
    if not dsn:
        raise SystemExit("ต้องตั้ง TEST_DATABASE_URL ก่อน")
    name = dsn.rsplit("/", 1)[-1].split("?")[0]
    if "test" not in name.lower():
        raise SystemExit(f"ปฏิเสธ: ชื่อฐานข้อมูล {name!r} ไม่มีคำว่า test")
    return dsn


_guard(DSN)
UPLOADS = Path(tempfile.mkdtemp(prefix="phase4-uploads-"))

# ต้องตั้งก่อน import app เพราะการตั้งค่าถูก cache ตอน import
os.environ["DATABASE_URL"] = DSN.replace("postgresql://", "postgresql+psycopg://")
os.environ["JWT_SECRET"] = "integration-test-only"
os.environ["UPLOADS_DIR"] = str(UPLOADS)
os.environ["UPLOAD_MAX_BYTES"] = "1048576"
sys.path.insert(0, str(REPO / "backend"))

import psycopg  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.api import deps  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.main import app  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64
PDF = b"%PDF-1.7\n" + b"0" * 64
PASSWORD = "IntegrationTest!2026"


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = psycopg.connect(_guard(DSN), autocommit=True)
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.raw.close()
        shutil.rmtree(UPLOADS, ignore_errors=True)

    def setUp(self):
        deps._login_bucket.clear()
        self.raw.execute("DELETE FROM public.auth_sessions")
        self.raw.execute("DELETE FROM public.auth_tokens")
        self.raw.execute("DELETE FROM web.site_courses")
        self.raw.execute("DELETE FROM web.news")
        self.raw.execute("DELETE FROM web.knowledge_articles")
        self.raw.execute("DELETE FROM web.external_news")
        self.raw.execute("DELETE FROM public.users")

    # ── เครื่องมือ ───────────────────────────────────────────────────
    def make_user(self, role="admin", status="approved", email=None, scheme="bcrypt_sha256",
                  password_hash=None) -> tuple[str, str]:
        email = email or f"{uuid.uuid4().hex[:8]}@example.ac.th"
        uid = str(uuid.uuid4())
        self.raw.execute(
            "INSERT INTO public.users (id, email, password_hash, password_scheme, role, status)"
            " VALUES (%s,%s,%s,%s,%s,%s)",
            (uid, email, password_hash or hash_password(PASSWORD), scheme, role, status))
        return uid, email

    def login(self, email, password=PASSWORD):
        return self.client.post("/auth/login", json={"email": email, "password": password})

    def token_for(self, role="admin", status="approved") -> str:
        _uid, email = self.make_user(role=role, status=status)
        return self.login(email).json()["access_token"]

    def auth(self, token):
        return {"Authorization": f"Bearer {token}"}


class LoginChecks(Base):
    def test_อีเมลที่มีตัวพิมพ์ใหญ่เข้าสู่ระบบด้วยตัวพิมพ์เล็กได้(self):
        """
        คอลัมน์ email เป็น citext ฐานข้อมูลจึงเทียบโดยไม่สนตัวพิมพ์

        ถ้าโมเดลประกาศคอลัมน์นี้เป็น String SQLAlchemy จะผูกพารามิเตอร์เป็น varchar
        แล้ว `where email = 'x'::varchar` กลายเป็นเทียบ **ตรงตัวพิมพ์** เพราะ Postgres
        ต้อง cast citext -> text ก่อน ผลคือหาแถวไม่เจอและตอบ 401 ทั้งที่รหัสผ่านถูก

        เจอบนระบบจริง: บัญชีผู้ดูแล Tester@gmail.com เข้าไม่ได้เลย และสังเกตได้จาก
        failed_login_count ที่ **ไม่เพิ่ม** ซึ่งแปลว่าหาผู้ใช้ไม่เจอ ไม่ใช่รหัสผิด
        """
        _uid, email = self.make_user(email="MixedCase@example.ac.th")
        response = self.login(email.lower())
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["user"]["email"].lower(), email.lower())

    def test_รหัสผิดเพิ่มตัวนับ_ไม่ใช่หาผู้ใช้ไม่เจอ(self):
        """
        แยกสองสาเหตุของ 401 ออกจากกัน

        รหัสผิดต้องทำให้ failed_login_count เพิ่ม — ถ้าไม่เพิ่มแปลว่าหาแถวไม่เจอ
        ซึ่งเป็นคนละปัญหาและกลไกล็อกบัญชีจะไม่ทำงานเลย
        """
        uid, email = self.make_user(email="CountMe@example.ac.th")
        self.assertEqual(self.login(email.lower(), "ผิดแน่นอน").status_code, 401)
        row = self.raw.execute(
            "SELECT failed_login_count FROM public.users WHERE id = %s", (uid,)).fetchone()
        self.assertEqual(row[0], 1)

    def test_เข้าสู่ระบบสำเร็จและได้สิทธิ์กลับมา(self):
        _uid, email = self.make_user(role="editor")
        r = self.login(email)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["user"]["role"], "editor")

    def test_รหัสผิดได้_401_และนับความล้มเหลวจริงในฐานข้อมูล(self):
        uid, email = self.make_user()
        self.assertEqual(self.login(email, "ผิด").status_code, 401)
        cur = self.raw.execute("SELECT failed_login_count FROM public.users WHERE id=%s", (uid,))
        self.assertEqual(cur.fetchone()[0], 1)

    def test_ใส่รหัสผิดครบจำนวนแล้วถูกล็อกจริง(self):
        uid, email = self.make_user()
        for _ in range(5):
            self.login(email, "ผิด")
        cur = self.raw.execute("SELECT locked_until FROM public.users WHERE id=%s", (uid,))
        self.assertIsNotNone(cur.fetchone()[0], "ไม่ถูกล็อกทั้งที่ผิดครบจำนวน")
        self.assertEqual(self.login(email).status_code, 429, "ถูกล็อกแล้วแต่ยังเข้าได้")

    def test_เข้าสำเร็จล้างตัวนับและบันทึกเวลาเข้าสู่ระบบ(self):
        uid, email = self.make_user()
        self.login(email, "ผิด")
        self.login(email)
        cur = self.raw.execute(
            "SELECT failed_login_count, last_login_at FROM public.users WHERE id=%s", (uid,))
        count, last = cur.fetchone()
        self.assertEqual(count, 0)
        self.assertIsNotNone(last)

    def test_บัญชีที่ย้ายจาก_supabase_ใช้รหัสเดิมได้(self):
        """ข้อสำคัญ — พิสูจน์ว่าไม่ต้องให้ใครตั้งรหัสใหม่"""
        import bcrypt
        legacy = bcrypt.hashpw(PASSWORD.encode("utf-8"), bcrypt.gensalt(rounds=10)).decode()
        _uid, email = self.make_user(scheme="bcrypt", password_hash=legacy)
        self.assertEqual(self.login(email).status_code, 200)

    def test_เข้าสำเร็จครั้งแรกอัปเกรดรูปแบบรหัสผ่านเอง(self):
        import bcrypt
        legacy = bcrypt.hashpw(PASSWORD.encode("utf-8"), bcrypt.gensalt(rounds=10)).decode()
        uid, email = self.make_user(scheme="bcrypt", password_hash=legacy)
        self.login(email)
        cur = self.raw.execute(
            "SELECT password_scheme, password_hash FROM public.users WHERE id=%s", (uid,))
        scheme, new_hash = cur.fetchone()
        self.assertEqual(scheme, "bcrypt_sha256")
        self.assertNotEqual(new_hash, legacy)
        self.assertEqual(self.login(email).status_code, 200, "อัปเกรดแล้วเข้าไม่ได้")

    def test_รหัสผิดกับบัญชีที่ย้ายมาก็ยังไม่ผ่าน(self):
        import bcrypt
        legacy = bcrypt.hashpw(PASSWORD.encode("utf-8"), bcrypt.gensalt(rounds=10)).decode()
        _uid, email = self.make_user(scheme="bcrypt", password_hash=legacy)
        self.assertEqual(self.login(email, "ผิด").status_code, 401)


class SessionChecks(Base):
    def test_เข้าสู่ระบบแล้วมีทะเบียนเซสชันในฐานข้อมูล(self):
        _uid, email = self.make_user()
        self.login(email)
        cur = self.raw.execute("SELECT count(*) FROM public.auth_sessions")
        self.assertEqual(cur.fetchone()[0], 1)

    def test_เข้าสู่ระบบสองครั้งติดกันได้_token_คนละใบ(self):
        """
        กันบั๊กที่เจอตอนทดสอบกับฐานข้อมูลจริง

        เดิม JWT ของ refresh ประกอบจาก sub/type/iat/exp ล้วน ซึ่งเท่ากันหมดเมื่อออก
        ให้คนเดียวกันในวินาทีเดียวกัน ผลคือทะเบียนเซสชันชน unique constraint
        แล้วการเข้าสู่ระบบล้มเป็น 500 — และถ้าไม่ชน สองเซสชันจะใช้ token ใบเดียวกัน
        """
        _uid, email = self.make_user()
        first = self.login(email)
        second = self.login(email)
        self.assertEqual((first.status_code, second.status_code), (200, 200))
        self.assertNotEqual(first.json()["refresh_token"], second.json()["refresh_token"])
        cur = self.raw.execute("SELECT count(*) FROM public.auth_sessions")
        self.assertEqual(cur.fetchone()[0], 2, "สองเซสชันถูกนับเป็นใบเดียว")

    def test_ออกจากระบบอุปกรณ์หนึ่งไม่กระทบอีกอุปกรณ์(self):
        _uid, email = self.make_user()
        first = self.login(email).json()
        second = self.login(email).json()
        self.client.post("/auth/logout", json={"refresh_token": first["refresh_token"]})
        self.assertEqual(self.client.post("/auth/refresh",
                                          json={"refresh_token": second["refresh_token"]})
                         .status_code, 200, "ออกจากระบบที่หนึ่งถอนอีกที่หนึ่งไปด้วย")

    def test_ไม่เก็บ_refresh_token_ดิบ(self):
        _uid, email = self.make_user()
        raw_token = self.login(email).json()["refresh_token"]
        cur = self.raw.execute("SELECT token_hash FROM public.auth_sessions")
        self.assertNotEqual(cur.fetchone()[0], raw_token)

    def test_refresh_หมุน_token_และเพิกถอนใบเดิม(self):
        _uid, email = self.make_user()
        old = self.login(email).json()["refresh_token"]
        r = self.client.post("/auth/refresh", json={"refresh_token": old})
        self.assertEqual(r.status_code, 200)
        self.assertNotEqual(r.json()["refresh_token"], old)
        self.assertEqual(self.client.post("/auth/refresh", json={"refresh_token": old}).status_code,
                         401, "ใบเดิมยังใช้ได้หลังหมุนแล้ว")

    def test_ออกจากระบบแล้ว_refresh_ใช้ไม่ได้(self):
        _uid, email = self.make_user()
        token = self.login(email).json()["refresh_token"]
        self.client.post("/auth/logout", json={"refresh_token": token})
        self.assertEqual(self.client.post("/auth/refresh", json={"refresh_token": token})
                         .status_code, 401)

    def test_ถอนอนุมัติแล้วเซสชันถูกเพิกถอนจริง(self):
        admin_token = self.token_for("admin")
        victim_id, victim_email = self.make_user(role="editor")
        victim_refresh = self.login(victim_email).json()["refresh_token"]

        r = self.client.put(f"/site-admin/users/{victim_id}/status",
                            json={"status": "rejected"}, headers=self.auth(admin_token))
        self.assertEqual(r.status_code, 200)

        self.assertEqual(self.client.post("/auth/refresh",
                                          json={"refresh_token": victim_refresh}).status_code,
                         401, "ถูกถอนอนุมัติแล้วยังต่ออายุเซสชันได้")

    def test_ถอนอนุมัติแล้วเข้าส่วนผู้ดูแลไม่ได้ทันที(self):
        admin_token = self.token_for("admin")
        victim_id, victim_email = self.make_user(role="editor")
        victim_access = self.login(victim_email).json()["access_token"]
        self.assertEqual(self.client.get("/site-admin/courses",
                                         headers=self.auth(victim_access)).status_code, 200)

        self.client.put(f"/site-admin/users/{victim_id}/status",
                        json={"status": "rejected"}, headers=self.auth(admin_token))

        self.assertEqual(self.client.get("/site-admin/courses",
                                         headers=self.auth(victim_access)).status_code, 403)

    def test_เปลี่ยนรหัสผ่านถอนทุกเซสชัน(self):
        _uid, email = self.make_user()
        first = self.login(email).json()
        second = self.login(email).json()
        r = self.client.post("/auth/password/change",
                             json={"current_password": PASSWORD, "new_password": "NewPass!2026"},
                             headers=self.auth(first["access_token"]))
        self.assertEqual(r.status_code, 200)
        for old in (first["refresh_token"], second["refresh_token"]):
            self.assertEqual(self.client.post("/auth/refresh",
                                              json={"refresh_token": old}).status_code, 401)

    def test_รีเซ็ตรหัสผ่านครบวงจร(self):
        uid, email = self.make_user()
        self.client.post("/auth/password-reset/request", json={"email": email})
        cur = self.raw.execute(
            "SELECT count(*) FROM public.auth_tokens WHERE user_id=%s AND purpose='password_reset'",
            (uid,))
        self.assertEqual(cur.fetchone()[0], 1, "ไม่ได้ออก token")

        # จำลองการกดลิงก์ — ดึง token ดิบไม่ได้เพราะเก็บเป็น hash จึงออกผ่านเส้นทางผู้ดูแล
        admin_token = self.token_for("admin")
        link = self.client.post("/auth/admin/reset-link", json={"user_id": uid},
                                headers=self.auth(admin_token)).json()
        r = self.client.post("/auth/password-reset/confirm",
                             json={"token": link["token"], "new_password": "Reset!2026x"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.login(email, "Reset!2026x").status_code, 200)
        self.assertEqual(self.login(email, PASSWORD).status_code, 401)

    def test_token_รีเซ็ตใช้ซ้ำไม่ได้(self):
        uid, _email = self.make_user()
        admin_token = self.token_for("admin")
        link = self.client.post("/auth/admin/reset-link", json={"user_id": uid},
                                headers=self.auth(admin_token)).json()
        self.client.post("/auth/password-reset/confirm",
                         json={"token": link["token"], "new_password": "Once!2026xx"})
        r = self.client.post("/auth/password-reset/confirm",
                             json={"token": link["token"], "new_password": "Twice!2026x"})
        self.assertEqual(r.status_code, 400, "token ใช้ซ้ำได้")


class CrudChecks(Base):
    def test_สร้างอ่านแก้ลบหลักสูตรครบวงจร(self):
        token = self.token_for("admin")
        created = self.client.post("/site-admin/courses", json={"title": "หลักสูตรทดสอบ"},
                                   headers=self.auth(token))
        self.assertEqual(created.status_code, 201)
        cid = created.json()["id"]

        self.assertEqual(self.client.get(f"/site-admin/courses/{cid}",
                                         headers=self.auth(token)).json()["title"],
                         "หลักสูตรทดสอบ")

        updated = self.client.put(f"/site-admin/courses/{cid}",
                                  json={"title": "แก้แล้ว", "careers": ["ก", "ข"]},
                                  headers=self.auth(token))
        self.assertEqual(updated.json()["title"], "แก้แล้ว")
        self.assertEqual(updated.json()["careers"], ["ก", "ข"])

        self.assertEqual(self.client.delete(f"/site-admin/courses/{cid}",
                                            headers=self.auth(token)).status_code, 204)
        self.assertEqual(self.client.get(f"/site-admin/courses/{cid}",
                                         headers=self.auth(token)).status_code, 404)

    def test_editor_ลบไม่ได้จริง(self):
        admin = self.token_for("admin")
        editor = self.token_for("editor")
        cid = self.client.post("/site-admin/courses", json={"title": "ก"},
                               headers=self.auth(admin)).json()["id"]
        self.assertEqual(self.client.delete(f"/site-admin/courses/{cid}",
                                            headers=self.auth(editor)).status_code, 403)
        cur = self.raw.execute("SELECT count(*) FROM web.site_courses WHERE id=%s", (cid,))
        self.assertEqual(cur.fetchone()[0], 1, "ถูกลบทั้งที่ควรถูกปฏิเสธ")

    def test_ร่างไม่หลุดเส้นทางสาธารณะ(self):
        token = self.token_for("admin")
        self.client.post("/site-admin/courses",
                         json={"title": "ยังไม่เผยแพร่", "is_published": False},
                         headers=self.auth(token))
        self.client.post("/site-admin/news", json={"title": "ข่าวร่าง", "status": "draft"},
                         headers=self.auth(token))

        public_courses = self.client.get("/site/courses").json()["courses"]
        public_news = self.client.get("/site/news").json()["news"]
        self.assertEqual([c for c in public_courses if c["title"] == "ยังไม่เผยแพร่"], [])
        self.assertEqual([n for n in public_news if n["title"] == "ข่าวร่าง"], [])

        self.assertEqual(len(self.client.get("/site-admin/courses",
                                             headers=self.auth(token)).json()["courses"]), 1)

    def test_สถานะข่าวที่ไม่รู้จักถูกฐานข้อมูลปฏิเสธด้วย(self):
        token = self.token_for("admin")
        nid = self.client.post("/site-admin/news", json={"title": "ก"},
                               headers=self.auth(token)).json()["id"]
        with self.assertRaises(psycopg.errors.CheckViolation):
            self.raw.execute("UPDATE web.news SET status='publish' WHERE id=%s", (nid,))

    def test_ตั้งค่า_ai_เขียนแล้วอ่านกลับได้(self):
        token = self.token_for("admin")
        self.client.put("/site-admin/ai-settings", json={"model": "qwen2.5:7b"},
                        headers=self.auth(token))
        self.assertEqual(self.client.get("/site-admin/ai-settings",
                                         headers=self.auth(token)).json()["model"], "qwen2.5:7b")

    def test_ตั้งค่า_ai_เขียนซ้ำไม่สร้างแถวใหม่(self):
        token = self.token_for("admin")
        for model in ("a", "b", "c"):
            self.client.put("/site-admin/ai-settings", json={"model": model},
                            headers=self.auth(token))
        cur = self.raw.execute("SELECT count(*) FROM web.ai_settings")
        self.assertEqual(cur.fetchone()[0], 1)

    def test_ผู้ดูแลลดสิทธิ์ตัวเองไม่ได้จริง(self):
        uid, email = self.make_user(role="admin")
        token = self.login(email).json()["access_token"]
        r = self.client.put(f"/site-admin/users/{uid}/role", json={"role": "user"},
                            headers=self.auth(token))
        self.assertEqual(r.status_code, 400)
        cur = self.raw.execute("SELECT role, is_admin FROM public.users WHERE id=%s", (uid,))
        self.assertEqual(cur.fetchone(), ("admin", True))

    def test_เปลี่ยน_role_แล้ว_is_admin_ตามจริงผ่าน_api(self):
        admin = self.token_for("admin")
        target_id, _ = self.make_user(role="user")
        self.client.put(f"/site-admin/users/{target_id}/role", json={"role": "admin"},
                        headers=self.auth(admin))
        cur = self.raw.execute("SELECT is_admin FROM public.users WHERE id=%s", (target_id,))
        self.assertTrue(cur.fetchone()[0], "trigger ไม่ทำงานผ่านเส้นทาง API")


class UploadChecks(Base):
    def test_อัปโหลดรูปแล้วเปิดได้โดยไม่ต้องล็อกอิน(self):
        token = self.token_for("editor")
        r = self.client.post("/uploads/logo", files={"file": ("a.png", PNG, "image/png")},
                             headers=self.auth(token))
        self.assertEqual(r.status_code, 201)
        path = r.json()["file_path"]
        self.assertTrue((UPLOADS / path).is_file(), "ไฟล์ไม่ได้ถูกเขียนลงดิสก์")
        self.assertEqual(self.client.get(f"/uploads/{path}").status_code, 200)

    def test_ไฟล์คลังความรู้ต้องล็อกอินก่อนเปิด(self):
        token = self.token_for("editor")
        path = self.client.post("/uploads/knowledge", files={"file": ("a.pdf", PDF, "application/pdf")},
                                headers=self.auth(token)).json()["file_path"]
        self.assertEqual(self.client.get(f"/uploads/{path}").status_code, 401)
        self.assertEqual(self.client.get(f"/uploads/{path}",
                                         headers=self.auth(token)).status_code, 200)

    def test_ผู้ใช้ทั่วไปอัปโหลดไม่ได้(self):
        token = self.token_for("user")
        self.assertEqual(self.client.post("/uploads/logo",
                                          files={"file": ("a.png", PNG, "image/png")},
                                          headers=self.auth(token)).status_code, 403)

    def test_นามสกุลถูกแต่เนื้อไฟล์ไม่ตรงถูกปฏิเสธ(self):
        token = self.token_for("editor")
        r = self.client.post("/uploads/logo",
                             files={"file": ("evil.png", b"MZ\x90\x00not-an-image", "image/png")},
                             headers=self.auth(token))
        self.assertEqual(r.status_code, 400)

    def test_ไฟล์ใหญ่เกินถูกปฏิเสธ(self):
        token = self.token_for("editor")
        big = b"\x89PNG\r\n\x1a\n" + b"0" * (2 * 1024 * 1024)
        self.assertEqual(self.client.post("/uploads/logo",
                                          files={"file": ("big.png", big, "image/png")},
                                          headers=self.auth(token)).status_code, 400)

    def test_พาธที่พยายามออกนอกโฟลเดอร์ได้_404(self):
        for bad in ("../../etc/passwd", "logo/../../../etc/passwd"):
            self.assertIn(self.client.get(f"/uploads/{bad}").status_code, (404, 400), bad)

    def test_อัปโหลดไฟล์เดียวกันสองครั้งได้พาธเดียวกัน(self):
        token = self.token_for("editor")
        a = self.client.post("/uploads/logo", files={"file": ("a.png", PNG, "image/png")},
                             headers=self.auth(token)).json()["file_path"]
        b = self.client.post("/uploads/logo", files={"file": ("b.png", PNG, "image/png")},
                             headers=self.auth(token)).json()["file_path"]
        self.assertEqual(a, b)


class SyncChecks(Base):
    """ทดสอบส่วนที่แตะฐานข้อมูลโดยป้อน HTML เอง — ไม่ยิงเว็บต้นทางจริง"""

    HTML = """
    <article class="news-card">
      <img src="https://example/a.jpg">
      <h2>ข่าวหนึ่ง</h2><p>เนื้อหา</p>
      <div class="card-meta"><span>2 ก.ย. 2569</span></div>
      <a class="card-primary-link" href="https://sci.pnru.ac.th/sciconnect_detail.php?slug=a">x</a>
    </article>
    """

    def sync(self, html, times=1):
        from unittest import mock
        from app.api.routes import site_admin
        token = self.token_for("admin")
        results = []
        with mock.patch("app.services.sci_news.fetch_url", return_value=html):
            for _ in range(times):
                results.append(self.client.post("/site-admin/sync-news", headers=self.auth(token)))
        return results

    def test_ดึงข่าวแล้วบันทึกลงฐานข้อมูลจริง(self):
        r = self.sync(self.HTML)[0]
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["inserted"], 1)
        cur = self.raw.execute("SELECT title, published_at FROM web.external_news")
        title, published = cur.fetchone()
        self.assertEqual(title, "ข่าวหนึ่ง")
        self.assertEqual(str(published)[:10], "2026-09-02")

    def test_รันซ้ำไม่เพิ่มข่าวซ้ำ(self):
        results = self.sync(self.HTML, times=3)
        self.assertEqual(results[0].json()["inserted"], 1)
        self.assertEqual(results[2].json()["inserted"], 0)
        cur = self.raw.execute("SELECT count(*) FROM web.external_news")
        self.assertEqual(cur.fetchone()[0], 1)

    def test_เว็บต้นทางล่มไม่ลบข่าวเดิม(self):
        self.sync(self.HTML)
        from unittest import mock
        token = self.token_for("admin")
        with mock.patch("app.services.sci_news.fetch_url", return_value=None):
            r = self.client.post("/site-admin/sync-news", headers=self.auth(token))
        self.assertEqual(r.status_code, 502)
        cur = self.raw.execute("SELECT count(*) FROM web.external_news")
        self.assertEqual(cur.fetchone()[0], 1, "ข่าวหายตอนเว็บต้นทางล่ม")

    def test_โครงหน้าเว็บเปลี่ยนไม่ลบข่าวเดิม(self):
        self.sync(self.HTML)
        r = self.sync("<div>โครงใหม่</div>")[0]
        self.assertEqual(r.status_code, 502)
        cur = self.raw.execute("SELECT count(*) FROM web.external_news")
        self.assertEqual(cur.fetchone()[0], 1)

    def test_ผู้ใช้ทั่วไปสั่งดึงข่าวไม่ได้(self):
        token = self.token_for("user")
        self.assertEqual(self.client.post("/site-admin/sync-news",
                                          headers=self.auth(token)).status_code, 403)

    def test_ข่าวที่ดึงมาโผล่ในเส้นทางสาธารณะ(self):
        self.sync(self.HTML)
        news = self.client.get("/site/external-news").json()["news"]
        self.assertEqual(len(news), 1)
        self.assertEqual(news[0]["slug"], "a")


if __name__ == "__main__":
    unittest.main()
