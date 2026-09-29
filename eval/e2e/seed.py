"""เตรียมฐานข้อมูลทดสอบ e2e_test ให้พร้อมสำหรับ E2E

ทำสามอย่าง
1. apply migrations 001-004 (ชุดเดียวกับ production) ต่อจาก schema.sql ที่ initdb ทำไปแล้ว
2. seed หลักสูตร TEST101 — จำเป็นเพราะ crawl_review.resolve_course() และ
   approve.lock_existing_course() ปฏิเสธรหัสที่ไม่มีอยู่ (Phase 3 v1 ไม่สร้าง course ใหม่)
3. seed ผู้ใช้ทดสอบสองบัญชี (admin หนึ่ง · ไม่ใช่ admin หนึ่ง)

รหัสผ่านของผู้ใช้ทดสอบถูกส่งเข้ามาเป็นพารามิเตอร์ ผู้เรียก (run_e2e.py) สุ่มขึ้น
ในหน่วยความจำและไม่เขียนลงไฟล์ใด — ฟังก์ชันนี้จึงไม่พิมพ์และไม่เก็บค่าเหล่านั้น

ด่านความปลอดภัย: ทุกฟังก์ชันที่เขียนข้อมูลต้องผ่าน guard_test_database() ก่อน
"""
from __future__ import annotations

import os
import pathlib

import psycopg

# ชื่อฐานข้อมูลที่อนุญาตให้เขียนได้เท่านั้น
ALLOWED_DB = {"e2e_test"}
# สตริงที่บ่งชี้ว่าเป็นฐานข้อมูลของ production — เจอเมื่อไหร่ให้หยุดทันที
FORBIDDEN_IN_DSN = ("course_advisor",)

MIGRATIONS = [
    "001_mko_structured.sql",
    "002_mko_review_publish.sql",
    "003_crawl_sources.sql",
    "004_crawl_decisions.sql",
]

TEST_COURSE_CODE = "TEST101"
TEST_COURSE_TITLE = "E2E Pipeline Testing"
TEST_ADMIN_EMAIL = "e2e-admin@example.com"   # .invalid/.local ถูก EmailStr ปฏิเสธ (special-use)
TEST_USER_EMAIL = "e2e-user@example.com"


class IsolationError(RuntimeError):
    """ชี้ไปฐานข้อมูลที่ไม่ใช่ฐานทดสอบ"""


def guard_dsn(dsn: str) -> None:
    """ด่านที่ 1 — ตรวจ DSN ก่อนต่อ"""
    low = dsn.lower()
    for bad in FORBIDDEN_IN_DSN:
        if bad in low:
            raise IsolationError(
                f"หยุด: DSN มีคำว่า {bad!r} ซึ่งเป็นฐานข้อมูลของ production")


def guard_connection(conn: psycopg.Connection) -> str:
    """ด่านที่ 2 และ 3 — ตรวจจากค่าที่เซิร์ฟเวอร์ตอบเอง ไม่ใช่จากสตริงที่เราเขียน"""
    with conn.cursor() as cur:
        db = cur.execute("SELECT current_database()").fetchone()[0]
        if db not in ALLOWED_DB:
            raise IsolationError(
                f"หยุด: ต่ออยู่กับฐานข้อมูล {db!r} ซึ่งไม่ใช่ฐานทดสอบ {ALLOWED_DB}")
        # production มี course_chunks 9039 แถว ฐานทดสอบควรมีหลักสิบ
        n = cur.execute("SELECT count(*) FROM course_chunks").fetchone()[0]
        if n > 1000:
            raise IsolationError(
                f"หยุด: ฐานข้อมูลนี้มี course_chunks {n} แถว มากผิดปกติสำหรับฐานทดสอบ")
    return db


def apply_migrations(conn: psycopg.Connection, repo_root: pathlib.Path) -> list[str]:
    applied = []
    for name in MIGRATIONS:
        path = repo_root / "db" / "migrations" / name
        sql = path.read_text(encoding="utf-8")
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
        applied.append(name)
    return applied


def seed_course(conn: psycopg.Connection) -> str:
    with conn.cursor() as cur:
        row = cur.execute(
            "INSERT INTO courses (code, title, provider) VALUES (%s, %s, %s) "
            "ON CONFLICT (code) DO UPDATE SET title = EXCLUDED.title RETURNING id::text",
            (TEST_COURSE_CODE, TEST_COURSE_TITLE, "E2E TEST"),
        ).fetchone()
    conn.commit()
    return row[0]


def seed_users(conn: psycopg.Connection, backend_url: str,
               admin_password: str, user_password: str) -> dict:
    """สร้างผู้ใช้ทดสอบสองบัญชีผ่าน POST /auth/register ของ backend ตัวจริง

    ทำไมไม่ INSERT ลงตารางเอง
    -------------------------
    อิมเมจของ ingest worker ไม่มี bcrypt (เป็น dependency ของ backend ไม่ใช่ของ pipeline)
    จะ import hash_password() มาใช้ตรง ๆ ไม่ได้ · การเรียก /auth/register แทน
    ได้ผลที่ดีกว่าเพราะใช้เส้นทางสมัครของ production จริงทั้งเส้น ไม่ได้ปลอม hash ขึ้นเอง

    จากนั้นตั้ง is_admin ให้บัญชีเดียวด้วย SQL เพราะ API ไม่เปิดช่องให้ตั้งค่านี้
    (โดยตั้งใจ — ดู backend/app/api/routes/auth.py:41)
    """
    import httpx

    out = {}
    for email, pw in ((TEST_ADMIN_EMAIL, admin_password), (TEST_USER_EMAIL, user_password)):
        r = httpx.post(f"{backend_url}/auth/register", timeout=30.0,
                       json={"email": email, "password": pw, "full_name": "E2E test account"})
        if r.status_code != 201:
            raise RuntimeError(f"สมัครผู้ใช้ทดสอบไม่สำเร็จ: {email} -> {r.status_code}")
        out[email] = r.json()["id"]

    with conn.cursor() as cur:
        n = cur.execute("UPDATE users SET is_admin = TRUE WHERE email = %s",
                        (TEST_ADMIN_EMAIL,)).rowcount
        if n != 1:
            raise RuntimeError(f"ตั้ง is_admin ได้ {n} แถว ต้องเป็น 1")
    conn.commit()
    return out


def snapshot(conn: psycopg.Connection) -> dict:
    """นับของในฐานทดสอบ — ใช้เป็น assertion ทั้งก่อนและหลังแต่ละขั้น"""
    q = {
        "courses": "SELECT count(*) FROM courses",
        "course_documents": "SELECT count(*) FROM course_documents",
        "course_chunks": "SELECT count(*) FROM course_chunks",
        "users": "SELECT count(*) FROM users",
        "admins": "SELECT count(*) FROM users WHERE is_admin",
        "crawl_sources": "SELECT count(*) FROM mko.crawl_sources",
        "crawl_decisions": "SELECT count(*) FROM mko.crawl_decisions",
        "v_crawl_queue": "SELECT count(*) FROM mko.v_crawl_queue",
    }
    out = {}
    with conn.cursor() as cur:
        for k, sql in q.items():
            out[k] = cur.execute(sql).fetchone()[0]
    return out


def seed_database(dsn: str, repo_root: pathlib.Path, backend_url: str,
                  admin_password: str, user_password: str) -> dict:
    guard_dsn(dsn)
    with psycopg.connect(dsn) as conn:
        db = guard_connection(conn)
        applied = apply_migrations(conn, repo_root)
        course_id = seed_course(conn)
        users = seed_users(conn, backend_url, admin_password, user_password)
        snap = snapshot(conn)
    return {
        "database": db,
        "migrations_applied": applied,
        "test_course_id": course_id,
        "test_user_ids": users,
        "snapshot": snap,
    }


if __name__ == "__main__":
    # โหมดเดี่ยวสำหรับดีบัก — ไม่ได้ใช้ในการรันจริง (run_e2e.py เรียกฟังก์ชันตรง)
    import secrets

    root = pathlib.Path(os.environ.get("E2E_REPO_ROOT", "/repo"))
    info = seed_database(os.environ["E2E_DSN"], root,
                         os.environ.get("E2E_BACKEND_URL", "http://e2e-backend:8000"),
                         secrets.token_urlsafe(18), secrets.token_urlsafe(18))
    print("database:", info["database"])
    print("migrations:", ", ".join(info["migrations_applied"]))
    print("snapshot:", info["snapshot"])
    print("หมายเหตุ: โหมดนี้สุ่มรหัสผ่านแล้วทิ้ง ใช้ล็อกอินไม่ได้")
