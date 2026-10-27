"""
ตรวจด่านสิทธิ์ของเส้นทางจัดการเนื้อหาผู้ดูแล — Phase 4

เหตุที่ต้องมี: หน้าเว็บซ่อนปุ่มตามสิทธิ์ แต่การซ่อนปุ่มไม่ใช่ด่าน ใครก็ยิง API ตรงได้
ด่านจริงต้องอยู่ที่นี่ และต้องครบทุกเส้นทาง ไม่ใช่เฉพาะที่นึกออก

ข้อกำหนดที่ห้ามหลุด
    - ทุกเส้นทางต้องมีด่าน ไม่มีเส้นทางไหนเปิดโล่ง
    - อ่าน/เขียน = staff ที่อนุมัติแล้ว · ลบ = admin เท่านั้น
    - รายชื่อผู้ใช้ = admin เท่านั้น (เป็นข้อมูลส่วนบุคคล)
    - ผู้ดูแลลดสิทธิ์หรือถอนอนุมัติของตัวเองไม่ได้ — กันเหลือศูนย์คน
    - ถอนอนุมัติใครต้องถอนเซสชันของคนนั้นด้วย ไม่ใช่รอ token หมดอายุ

ทั้งหมดเป็น offline: ไม่ต่อฐานข้อมูลจริง ไม่แตะ production

    python -m eval.site_admin_check
"""
from __future__ import annotations

import os
import sys
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres@127.0.0.1:55432/course_advisor")
os.environ.setdefault("JWT_SECRET", "local-test-only")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.api.deps import get_current_user  # noqa: E402
from app.api.routes import site_admin as route  # noqa: E402
from app.db.session import get_db  # noqa: E402

ADMIN_ID = uuid.uuid4()
OTHER_ID = uuid.uuid4()


def user(role="admin", status="approved", uid=None):
    return SimpleNamespace(id=uid or ADMIN_ID, email="a@example.ac.th", full_name="ก",
                           role=role, status=status, is_active=True, is_admin=role == "admin")


class FakeDB:
    def __init__(self, row=None, rowcount=1):
        self._row = row if row is not None else {"id": str(uuid.uuid4()), "title": "ก"}
        self._rowcount = rowcount
        self.statements: list[str] = []

    def execute(self, statement, params=None):
        self.statements.append(" ".join(str(statement).split()))
        row = self._row
        return SimpleNamespace(
            mappings=lambda: SimpleNamespace(first=lambda: row, all=lambda: [row]),
            rowcount=self._rowcount,
        )

    def commit(self):
        pass

    def ran(self, fragment):
        return any(fragment in s for s in self.statements)


class Base(unittest.TestCase):
    def client(self, actor, db=None):
        self.db = db or FakeDB()
        app = FastAPI()
        app.include_router(route.router)
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: actor
        return TestClient(app)


# ทุกเส้นทางที่ต้องมีด่าน พร้อมตัวอย่าง body ที่ผ่านการตรวจรูปแบบ
WRITE_BODY = {
    "/site-admin/courses": {"title": "หลักสูตรทดสอบ"},
    "/site-admin/news": {"title": "ข่าวทดสอบ"},
    "/site-admin/knowledge": {"title": "บทความทดสอบ"},
}


class StaffGateChecks(Base):
    def test_staff_ที่อนุมัติแล้วอ่านได้(self):
        for path in ("/site-admin/courses", "/site-admin/news", "/site-admin/knowledge",
                     "/site-admin/ai-settings"):
            r = self.client(user("editor", "approved")).get(path)
            self.assertEqual(r.status_code, 200, path)

    def test_ผู้ใช้ทั่วไปอ่านไม่ได้(self):
        for path in ("/site-admin/courses", "/site-admin/news", "/site-admin/knowledge",
                     "/site-admin/ai-settings"):
            r = self.client(user("user", "approved")).get(path)
            self.assertEqual(r.status_code, 403, path)

    def test_staff_ที่ยังไม่อนุมัติอ่านไม่ได้(self):
        r = self.client(user("admin", "pending")).get("/site-admin/courses")
        self.assertEqual(r.status_code, 403)

    def test_staff_ที่ถูกปฏิเสธอ่านไม่ได้(self):
        r = self.client(user("editor", "rejected")).get("/site-admin/news")
        self.assertEqual(r.status_code, 403)

    def test_editor_สร้างได้(self):
        for path, body in WRITE_BODY.items():
            r = self.client(user("editor", "approved")).post(path, json=body)
            self.assertEqual(r.status_code, 201, path)

    def test_ผู้ใช้ทั่วไปสร้างไม่ได้(self):
        for path, body in WRITE_BODY.items():
            r = self.client(user("user", "approved")).post(path, json=body)
            self.assertEqual(r.status_code, 403, path)

    def test_editor_แก้ได้(self):
        for path, body in WRITE_BODY.items():
            r = self.client(user("editor", "approved")).put(f"{path}/{uuid.uuid4()}", json=body)
            self.assertEqual(r.status_code, 200, path)


class DeleteGateChecks(Base):
    def test_admin_ลบได้(self):
        for path in WRITE_BODY:
            r = self.client(user("admin", "approved")).delete(f"{path}/{uuid.uuid4()}")
            self.assertEqual(r.status_code, 204, path)

    def test_editor_ลบไม่ได้(self):
        """หน้าเว็บซ่อนปุ่มลบจาก editor — หลังบ้านต้องปฏิเสธจริง"""
        for path in WRITE_BODY:
            r = self.client(user("editor", "approved")).delete(f"{path}/{uuid.uuid4()}")
            self.assertEqual(r.status_code, 403, path)

    def test_ลบของที่ไม่มีได้_404(self):
        r = self.client(user("admin"), FakeDB(rowcount=0)).delete(
            f"/site-admin/courses/{uuid.uuid4()}")
        self.assertEqual(r.status_code, 404)

    def test_รหัสที่ไม่ใช่_uuid_ได้_404_ไม่ใช่_500(self):
        r = self.client(user("admin")).delete("/site-admin/courses/ไม่ใช่รหัส")
        self.assertEqual(r.status_code, 404)


class UserManagementChecks(Base):
    def test_admin_ดูรายชื่อผู้ใช้ได้(self):
        r = self.client(user("admin")).get("/site-admin/users")
        self.assertEqual(r.status_code, 200)

    def test_editor_ดูรายชื่อผู้ใช้ไม่ได้(self):
        """รายชื่อผู้ใช้เป็นข้อมูลส่วนบุคคล"""
        r = self.client(user("editor", "approved")).get("/site-admin/users")
        self.assertEqual(r.status_code, 403)

    def test_เปลี่ยนสิทธิ์คนอื่นได้(self):
        r = self.client(user("admin")).put(f"/site-admin/users/{OTHER_ID}/role",
                                           json={"role": "editor"})
        self.assertEqual(r.status_code, 200)

    def test_ลดสิทธิ์ตัวเองไม่ได้(self):
        """กันผู้ดูแลคนสุดท้ายเผลอลดสิทธิ์ตัวเองแล้วไม่มีใครเข้าได้อีก"""
        r = self.client(user("admin")).put(f"/site-admin/users/{ADMIN_ID}/role",
                                           json={"role": "user"})
        self.assertEqual(r.status_code, 400)

    def test_ตั้งตัวเองเป็น_admin_ซ้ำได้(self):
        r = self.client(user("admin")).put(f"/site-admin/users/{ADMIN_ID}/role",
                                           json={"role": "admin"})
        self.assertEqual(r.status_code, 200)

    def test_ถอนอนุมัติตัวเองไม่ได้(self):
        r = self.client(user("admin")).put(f"/site-admin/users/{ADMIN_ID}/status",
                                           json={"status": "rejected"})
        self.assertEqual(r.status_code, 400)

    def test_ถอนอนุมัติคนอื่นต้องถอนเซสชันด้วย(self):
        """ไม่ถอนเซสชัน = คนที่ถูกปลดยังใช้งานต่อได้จนกว่า token จะหมดอายุ"""
        db = FakeDB()
        self.client(user("admin"), db).put(f"/site-admin/users/{OTHER_ID}/status",
                                           json={"status": "rejected"})
        self.assertTrue(db.ran("update public.auth_sessions set revoked_at"))

    def test_อนุมัติคนอื่นไม่ถอนเซสชัน(self):
        db = FakeDB()
        self.client(user("admin"), db).put(f"/site-admin/users/{OTHER_ID}/status",
                                           json={"status": "approved"})
        self.assertFalse(db.ran("auth_sessions"))

    def test_ค่าสิทธิ์ที่ไม่รู้จักถูกปฏิเสธ(self):
        r = self.client(user("admin")).put(f"/site-admin/users/{OTHER_ID}/role",
                                           json={"role": "superuser"})
        self.assertEqual(r.status_code, 422)

    def test_ค่าสถานะที่ไม่รู้จักถูกปฏิเสธ(self):
        r = self.client(user("admin")).put(f"/site-admin/users/{OTHER_ID}/status",
                                           json={"status": "active"})
        self.assertEqual(r.status_code, 422)


class ValidationChecks(Base):
    def test_สถานะข่าวที่ไม่รู้จักถูกปฏิเสธ(self):
        """ค่าพิมพ์ผิดแม้ตัวเดียวทำให้ข่าวหายจากหน้าเว็บโดยไม่มีอะไรฟ้อง"""
        r = self.client(user("editor", "approved")).post(
            "/site-admin/news", json={"title": "ก", "status": "publish"})
        self.assertEqual(r.status_code, 422)

    def test_ชื่อว่างถูกปฏิเสธ(self):
        for path in WRITE_BODY:
            r = self.client(user("editor", "approved")).post(path, json={"title": ""})
            self.assertEqual(r.status_code, 422, path)

    def test_ขนาดไฟล์ติดลบถูกปฏิเสธ(self):
        r = self.client(user("editor", "approved")).post(
            "/site-admin/knowledge", json={"title": "ก", "file_size": -1})
        self.assertEqual(r.status_code, 422)


def dependency_names(dependant, seen=None) -> set[str]:
    """ไล่ต้นไม้ dependency ทั้งหมดของเส้นทางหนึ่ง — ด่านอาจอยู่ลึกกว่าชั้นแรก"""
    seen = seen if seen is not None else set()
    for sub in dependant.dependencies:
        if sub.call is not None:
            # บาง dependency เป็นอ็อบเจกต์ (เช่น HTTPBearer) ไม่ใช่ฟังก์ชัน จึงไม่มี __name__
            seen.add(getattr(sub.call, "__name__", type(sub.call).__name__))
        dependency_names(sub, seen)
    return seen


class CoverageChecks(unittest.TestCase):
    def test_ทุกเส้นทางมีด่านสิทธิ์(self):
        """เส้นทางที่ลืมใส่ด่านคือเส้นทางที่ใครก็เรียกได้"""
        for r in route.router.routes:
            names = dependency_names(r.dependant)
            self.assertTrue(
                {"require_staff", "require_admin_role"} & names,
                f"{list(r.methods)[0]} {r.path} ไม่มีด่านสิทธิ์ (พบ: {sorted(names)})",
            )

    def test_เส้นทางลบใช้ด่าน_admin_ทุกเส้น(self):
        deletes = [r for r in route.router.routes if "DELETE" in r.methods]
        self.assertGreaterEqual(len(deletes), 3, "ควรมีเส้นทางลบอย่างน้อยสามเส้น")
        for r in deletes:
            self.assertIn("require_admin_role", dependency_names(r.dependant),
                          f"{r.path} ลบได้โดยไม่ใช่ admin")

    def test_เส้นทางที่เกี่ยวกับผู้ใช้ใช้ด่าน_admin(self):
        for r in route.router.routes:
            if "/users" not in r.path:
                continue
            self.assertIn("require_admin_role", dependency_names(r.dependant), r.path)

    def test_ไม่มีการต่อสตริงชื่อตารางจากผู้ใช้(self):
        src = (Path(__file__).resolve().parents[1] / "backend" / "app" / "api" / "routes"
               / "site_admin.py").read_text(encoding="utf-8")
        # ชื่อตารางและคอลัมน์ที่ใส่ลง f-string ต้องมี assert คุมค่าไว้ก่อนเสมอ
        self.assertIn('assert table in (', src)
        self.assertIn('assert column in (', src)


if __name__ == "__main__":
    unittest.main()
