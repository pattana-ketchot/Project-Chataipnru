"""
ทดสอบ migration 006 — คอลัมน์ supabase_user_id และสิทธิ์ของ advisor_web

    python eval/web_identity_mapping_check.py --database-url postgresql://<owner>@HOST:PORT/web_test

ต้องเป็นฐานข้อมูลทดสอบที่แยกจาก production เท่านั้น
------------------------------------------------
ด่านเดียวกับ eval/web_schema_check.py
  1. ชื่อฐานข้อมูลใน URL ต้องอยู่ในรายการที่อนุญาต และห้ามมีคำว่า course_advisor
  2. ถามเซิร์ฟเวอร์เองด้วย current_database() ว่าต่ออยู่กับฐานไหนจริง

สิ่งที่ต้องพิสูจน์ที่นี่
----------------------
ชุดนี้ไม่ตรวจแค่ว่า GRANT ถูกบันทึกใน catalog แต่ **สวมบทเป็น advisor_web แล้วลองจริง**
ด้วย SET ROLE เพราะข้อตรวจที่อ่านแต่ catalog จะผ่านแม้สิทธิ์ใช้งานจริงไม่เป็นอย่างที่คิด

วิธีแยก "ถูกปฏิเสธเพราะไม่มีสิทธิ์" ออกจาก "ข้อมูลที่ยัดเข้าไปผิดรูป" คือดู SQLSTATE
42501 = insufficient_privilege เท่านั้นที่นับว่าถูกปฏิเสธด้วยสิทธิ์ ข้อผิดพลาดอื่น
เช่น 23502 not_null_violation แปลว่าสิทธิ์ผ่านแล้วแต่ข้อมูลไม่ครบ ซึ่งคือ "ทำได้"

ทำไมต้องพิสูจน์เชิงพฤติกรรม
---------------------------
has_table_privilege คืน false ให้ advisor_web บน public.users ก็จริง แต่ตัวมันเอง
ไม่ได้บอกว่า SELECT id ทำได้หรือไม่ เพราะสิทธิ์อยู่ระดับคอลัมน์ การยิง SQL จริง
เป็นทางเดียวที่พิสูจน์ได้ว่าอ่าน id ได้และอ่าน email ไม่ได้ในเวลาเดียวกัน

ไม่ย้ายข้อมูลจริงจากที่ใดทั้งสิ้น ทุกแถวในชุดนี้สร้างขึ้นเองแล้วถอนกลับเมื่อจบ
"""
from __future__ import annotations

import argparse
import re
import sys
import uuid
from pathlib import Path

import psycopg

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

MIGRATION = _ROOT / "db" / "migrations" / "006_web_identity_mapping.sql"

ALLOWED_DB_NAMES = {"web_test", "crawl_test", "e2e_test"}
FORBIDDEN_IN_URL = "course_advisor"

INSUFFICIENT_PRIVILEGE = "42501"

# คอลัมน์ของ public.users ที่ advisor_web ต้องอ่านได้ และที่ต้องอ่านไม่ได้
USERS_ALLOWED = ("id", "is_active", "supabase_user_id")
USERS_DENIED = ("email", "password_hash", "full_name", "is_admin")

# (ตาราง, คอลัมน์ที่ใส่ได้ขั้นต่ำ, สิทธิ์ที่ต้องมี, สิทธิ์ที่ต้องไม่มี)
WEB_MATRIX = (
    ("site_courses",       "title", ("SELECT", "INSERT", "UPDATE"), ("DELETE",)),
    ("news",               "title", ("SELECT", "INSERT", "UPDATE"), ("DELETE",)),
    ("knowledge_articles", "title", ("SELECT", "INSERT", "UPDATE"), ("DELETE",)),
    ("ai_settings",        "model", ("SELECT", "UPDATE"),           ("INSERT", "DELETE")),
    ("external_news",      "title", ("SELECT",),                    ("INSERT", "UPDATE", "DELETE")),
)


class Checks:
    def __init__(self) -> None:
        self.passed = 0
        self.failed: list[tuple[str, str]] = []

    def check(self, name: str, ok: bool, detail: str = "") -> bool:
        if ok:
            self.passed += 1
            print(f"  ผ่าน  {name}")
        else:
            self.failed.append((name, detail))
            print(f"  ไม่ผ่าน {name}  {detail}")
        return ok

    def report(self) -> bool:
        print(f"\nผ่าน {self.passed} ข้อ · ไม่ผ่าน {len(self.failed)} ข้อ")
        for name, detail in self.failed:
            print(f"  - {name}  {detail}")
        return not self.failed


def guard(url: str, conn: psycopg.Connection) -> str:
    """ปฏิเสธการรันกับฐานข้อมูลที่ไม่ใช่ฐานทดสอบ — ตรวจทั้ง URL และตัวเซิร์ฟเวอร์เอง"""
    if FORBIDDEN_IN_URL in url:
        raise SystemExit(f"ปฏิเสธ: URL มีคำว่า {FORBIDDEN_IN_URL}")
    with conn.cursor() as cur:
        db = cur.execute("SELECT current_database()").fetchone()[0]
    if db not in ALLOWED_DB_NAMES:
        raise SystemExit(f"ปฏิเสธ: ต่ออยู่กับฐาน {db} ซึ่งไม่อยู่ในรายการฐานทดสอบ")
    return db


def attempt(conn, sql: str, params=()) -> tuple[bool, str, object]:
    """
    รัน SQL ใน savepoint คืน (สำเร็จ, sqlstate, แถวแรก)

    ใช้ savepoint เพื่อให้คำสั่งที่ถูกปฏิเสธไม่ทำให้ transaction ทั้งก้อนใช้ต่อไม่ได้
    """
    with conn.cursor() as cur:
        cur.execute("SAVEPOINT sp_try")
        try:
            cur.execute(sql, params)
            row = cur.fetchone() if cur.description else None
            cur.execute("RELEASE SAVEPOINT sp_try")
            return True, "", row
        except psycopg.Error as e:
            state = e.sqlstate or ""
            cur.execute("ROLLBACK TO SAVEPOINT sp_try")
            cur.execute("RELEASE SAVEPOINT sp_try")
            return False, state, None


def denied_by_privilege(conn, sql: str) -> tuple[bool, str]:
    """
    จริงเมื่อคำสั่งถูกปฏิเสธ **เพราะสิทธิ์** เท่านั้น

    ข้อผิดพลาดอื่นไม่นับ เพราะ not_null_violation แปลว่าสิทธิ์ผ่านแล้ว
    แต่ข้อมูลไม่ครบ ซึ่งตรงข้ามกับสิ่งที่ต้องการพิสูจน์
    """
    ok, state, _ = attempt(conn, sql)
    if ok:
        return False, "คำสั่งสำเร็จ"
    return state == INSUFFICIENT_PRIVILEGE, f"sqlstate={state}"


def allowed_by_privilege(conn, sql: str) -> tuple[bool, str]:
    """จริงเมื่อคำสั่งไม่ถูกปฏิเสธด้วยสิทธิ์ — สำเร็จ หรือพังด้วยสาเหตุอื่นก็นับว่าผ่าน"""
    ok, state, _ = attempt(conn, sql)
    if ok:
        return True, ""
    return state != INSUFFICIENT_PRIVILEGE, f"sqlstate={state}"


def make_user(conn, supabase_id) -> uuid.UUID:
    """สร้างผู้ใช้ทดสอบหนึ่งแถว คืน id — ถอนกลับทั้งหมดตอนจบสคริปต์"""
    uid = uuid.uuid4()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO public.users (id, email, password_hash, supabase_user_id)"
            " VALUES (%s, %s, %s, %s)",
            (uid, f"m006-{uid}@test.invalid", "ไม่ใช่ hash จริง", supabase_id),
        )
    return uid


# ---------------------------------------------------------------------
# 1–3  รูปร่างของคอลัมน์
# ---------------------------------------------------------------------
def column_shape(c: Checks, conn) -> None:
    print("\nคอลัมน์ public.users.supabase_user_id")
    with conn.cursor() as cur:
        row = cur.execute(
            "SELECT data_type, udt_name, is_nullable, column_default"
            " FROM information_schema.columns"
            " WHERE table_schema='public' AND table_name='users'"
            "   AND column_name='supabase_user_id'"
        ).fetchone()
    if not c.check("คอลัมน์ supabase_user_id มีอยู่", row is not None):
        return
    data_type, udt, nullable, default = row
    c.check("ชนิดเป็น UUID", udt == "uuid", f"{data_type}/{udt}")
    c.check("เป็น NULL ได้", nullable == "YES", str(nullable))
    c.check("ไม่มี DEFAULT", default is None, str(default))


# ---------------------------------------------------------------------
# 4  partial unique index
# ---------------------------------------------------------------------
def partial_index(c: Checks, conn) -> None:
    print("\npartial unique index")
    with conn.cursor() as cur:
        row = cur.execute(
            "SELECT i.indisunique, i.indpred IS NOT NULL,"
            "       pg_get_expr(i.indpred, i.indrelid),"
            "       pg_get_indexdef(i.indexrelid)"
            " FROM pg_index i JOIN pg_class ic ON ic.oid = i.indexrelid"
            " WHERE ic.relname = 'uq_users_supabase_user_id'"
        ).fetchone()
    if not c.check("index uq_users_supabase_user_id มีอยู่", row is not None):
        return
    is_unique, is_partial, pred, definition = row
    c.check("เป็น unique", bool(is_unique))
    c.check("เป็น partial (มี WHERE)", bool(is_partial))
    c.check("เงื่อนไขคือ supabase_user_id IS NOT NULL",
            pred is not None and "supabase_user_id IS NOT NULL" in pred, str(pred))
    c.check("อยู่บนคอลัมน์ supabase_user_id คอลัมน์เดียว",
            "(supabase_user_id)" in (definition or ""), str(definition))


# ---------------------------------------------------------------------
# 5–6  ข้อห้ามซ้ำทำงานจริง
# ---------------------------------------------------------------------
def uniqueness_behaviour(c: Checks, conn) -> None:
    print("\nข้อห้ามซ้ำ — ทดสอบด้วยการยัดข้อมูลจริง")
    shared = uuid.uuid4()
    make_user(conn, shared)
    ok, state, _ = attempt(
        conn,
        "INSERT INTO public.users (email, password_hash, supabase_user_id)"
        " VALUES (%s, %s, %s)",
        (f"dup-{uuid.uuid4()}@test.invalid", "x", shared),
    )
    c.check("supabase_user_id ซ้ำถูกปฏิเสธ", (not ok) and state == "23505", f"sqlstate={state}")

    make_user(conn, None)
    ok2, state2, _ = attempt(
        conn,
        "INSERT INTO public.users (email, password_hash, supabase_user_id)"
        " VALUES (%s, %s, NULL)",
        (f"null2-{uuid.uuid4()}@test.invalid", "x"),
    )
    c.check("NULL หลายแถวใส่ได้", ok2, f"sqlstate={state2}")

    with conn.cursor() as cur:
        n = cur.execute(
            "SELECT count(*) FROM public.users WHERE supabase_user_id IS NULL"
        ).fetchone()[0]
    c.check("แถว NULL อยู่ร่วมกันได้มากกว่าหนึ่ง", n >= 2, f"{n} แถว")


# ---------------------------------------------------------------------
# 7–10  สิทธิ์บน public.users
# ---------------------------------------------------------------------
def users_privileges(c: Checks, conn) -> None:
    print("\nสิทธิ์ของ advisor_web บน public.users")
    with conn.cursor() as cur:
        table_level = cur.execute(
            "SELECT has_table_privilege('advisor_web','public.users','SELECT')"
        ).fetchone()[0]
    c.check("ไม่มี SELECT ระดับตาราง", table_level is False, str(table_level))

    with conn.cursor() as cur:
        for col in USERS_ALLOWED:
            got = cur.execute(
                "SELECT has_column_privilege('advisor_web','public.users',%s,'SELECT')",
                (col,),
            ).fetchone()[0]
            c.check(f"catalog: อ่านคอลัมน์ {col} ได้", got is True, str(got))
        for col in USERS_DENIED:
            got = cur.execute(
                "SELECT has_column_privilege('advisor_web','public.users',%s,'SELECT')",
                (col,),
            ).fetchone()[0]
            c.check(f"catalog: อ่านคอลัมน์ {col} ไม่ได้", got is False, str(got))

    make_user(conn, uuid.uuid4())
    with conn.cursor() as cur:
        cur.execute("SET ROLE advisor_web")
    try:
        ok, _, row = attempt(
            conn, "SELECT id, is_active, supabase_user_id FROM public.users LIMIT 1"
        )
        c.check("ของจริง: SELECT id, is_active, supabase_user_id ทำได้", ok and row is not None)

        for col in USERS_DENIED:
            got, detail = denied_by_privilege(conn, f"SELECT {col} FROM public.users LIMIT 1")
            c.check(f"ของจริง: SELECT {col} ถูกปฏิเสธ", got, detail)

        got, detail = denied_by_privilege(conn, "SELECT * FROM public.users LIMIT 1")
        c.check("ของจริง: SELECT * ถูกปฏิเสธ", got, detail)

        got, detail = denied_by_privilege(
            conn, "UPDATE public.users SET is_active = is_active WHERE false"
        )
        c.check("ของจริง: UPDATE public.users ถูกปฏิเสธ", got, detail)

        got, detail = denied_by_privilege(
            conn,
            "INSERT INTO public.users (email, password_hash) VALUES ('x@test.invalid','x')",
        )
        c.check("ของจริง: INSERT public.users ถูกปฏิเสธ", got, detail)

        got, detail = denied_by_privilege(conn, "DELETE FROM public.users WHERE false")
        c.check("ของจริง: DELETE public.users ถูกปฏิเสธ", got, detail)
    finally:
        with conn.cursor() as cur:
            cur.execute("RESET ROLE")


# ---------------------------------------------------------------------
# 11–16  สิทธิ์บน schema web
# ---------------------------------------------------------------------
def web_privileges(c: Checks, conn) -> None:
    print("\nสิทธิ์ของ advisor_web บน schema web")
    with conn.cursor() as cur:
        usage = cur.execute(
            "SELECT has_schema_privilege('advisor_web','web','USAGE')"
        ).fetchone()[0]
    c.check("มี USAGE ON SCHEMA web", usage is True, str(usage))

    with conn.cursor() as cur:
        for table, _col, wanted, unwanted in WEB_MATRIX:
            for priv in wanted:
                got = cur.execute(
                    "SELECT has_table_privilege('advisor_web',%s,%s)",
                    (f"web.{table}", priv),
                ).fetchone()[0]
                c.check(f"catalog: {priv} บน web.{table}", got is True, str(got))
            for priv in unwanted:
                got = cur.execute(
                    "SELECT has_table_privilege('advisor_web',%s,%s)",
                    (f"web.{table}", priv),
                ).fetchone()[0]
                c.check(f"catalog: ไม่มี {priv} บน web.{table}", got is False, str(got))

    with conn.cursor() as cur:
        cur.execute("SET ROLE advisor_web")
    try:
        for table, col, wanted, unwanted in WEB_MATRIX:
            got, detail = allowed_by_privilege(conn, f"SELECT * FROM web.{table} LIMIT 1")
            c.check(f"ของจริง: SELECT web.{table} ทำได้", got, detail)

            stmt_insert = f"INSERT INTO web.{table} ({col}) VALUES ('ทดสอบ 006')"
            stmt_update = f"UPDATE web.{table} SET {col} = {col} WHERE false"
            stmt_delete = f"DELETE FROM web.{table} WHERE false"

            if "INSERT" in wanted:
                got, detail = allowed_by_privilege(conn, stmt_insert)
                c.check(f"ของจริง: INSERT web.{table} ทำได้", got, detail)
            else:
                got, detail = denied_by_privilege(conn, stmt_insert)
                c.check(f"ของจริง: INSERT web.{table} ถูกปฏิเสธ", got, detail)

            if "UPDATE" in wanted:
                got, detail = allowed_by_privilege(conn, stmt_update)
                c.check(f"ของจริง: UPDATE web.{table} ทำได้", got, detail)
            else:
                got, detail = denied_by_privilege(conn, stmt_update)
                c.check(f"ของจริง: UPDATE web.{table} ถูกปฏิเสธ", got, detail)

            got, detail = denied_by_privilege(conn, stmt_delete)
            c.check(f"ของจริง: DELETE web.{table} ถูกปฏิเสธ", got, detail)
    finally:
        with conn.cursor() as cur:
            cur.execute("RESET ROLE")


# ---------------------------------------------------------------------
# 17  EXECUTE บน trigger function
# ---------------------------------------------------------------------
def function_execute(c: Checks, conn) -> None:
    print("\nสิทธิ์เรียกฟังก์ชัน web.touch_updated_at()")
    with conn.cursor() as cur:
        got = cur.execute(
            "SELECT has_function_privilege('advisor_web','web.touch_updated_at()','EXECUTE')"
        ).fetchone()[0]
    c.check("catalog: มี EXECUTE", got is True, str(got))

    # พิสูจน์ว่า trigger ทำงานได้จริงตอน advisor_web สั่ง UPDATE
    with conn.cursor() as cur:
        cur.execute("INSERT INTO web.news (title) VALUES ('แถวทดสอบ trigger') RETURNING id")
        news_id = cur.fetchone()[0]
        cur.execute("UPDATE web.news SET updated_at = now() - interval '1 day' WHERE id = %s",
                    (news_id,))
        cur.execute("SET ROLE advisor_web")
    try:
        ok, state, _ = attempt(
            conn, "UPDATE web.news SET title = 'แก้โดย advisor_web' WHERE id = %s", (news_id,)
        )
        c.check("ของจริง: advisor_web สั่ง UPDATE แล้ว trigger ไม่ขวาง", ok, f"sqlstate={state}")
    finally:
        with conn.cursor() as cur:
            cur.execute("RESET ROLE")
    with conn.cursor() as cur:
        moved = cur.execute(
            "SELECT updated_at > now() - interval '1 minute' FROM web.news WHERE id = %s",
            (news_id,),
        ).fetchone()[0]
    c.check("trigger ตั้ง updated_at ให้จริง", moved is True, str(moved))


# ---------------------------------------------------------------------
# 18  ของเดิมต้องไม่ถอยหลัง
# ---------------------------------------------------------------------
def no_regression(c: Checks, conn) -> None:
    print("\nสิทธิ์เดิมของ advisor_api / advisor_ingest")
    with conn.cursor() as cur:
        api_users = cur.execute(
            "SELECT string_agg(DISTINCT privilege_type, ',' ORDER BY privilege_type)"
            " FROM information_schema.table_privileges"
            " WHERE grantee='advisor_api' AND table_schema='public' AND table_name='users'"
        ).fetchone()[0]
    c.check("advisor_api บน public.users ยังเป็น INSERT,SELECT,UPDATE",
            api_users == "INSERT,SELECT,UPDATE", str(api_users))

    with conn.cursor() as cur:
        for table in ("site_courses", "news", "knowledge_articles", "ai_settings"):
            got = cur.execute(
                "SELECT has_table_privilege('advisor_api',%s,'SELECT')"
                "   AND has_table_privilege('advisor_api',%s,'INSERT')",
                (f"web.{table}", f"web.{table}"),
            ).fetchone()[0]
            c.check(f"advisor_api ยังเขียน web.{table} ได้", got is True, str(got))
        ing = cur.execute(
            "SELECT has_table_privilege('advisor_ingest','web.external_news','INSERT')"
        ).fetchone()[0]
        c.check("advisor_ingest ยังเขียน web.external_news ได้", ing is True, str(ing))

        # ข้อห้าม DELETE ของโปรเจกต์นี้อยู่ที่ schema web และตารางที่ 002/004 ระบุ
        # ไม่ใช่ข้อห้ามทั่วทั้งฐาน — advisor_ingest มี DELETE บน schema mko มาตั้งแต่
        # migration 001/002 เพราะเป็น worker ที่สร้างข้อมูลสกัดใหม่ทั้งชุด
        # ข้อตรวจรุ่นแรกเขียนว่า "ไม่มีใครได้ DELETE ที่ไหนเลย" ซึ่งผิดขอบเขต
        # ต้องกรอง grantee เสมอ — information_schema.table_privileges รายงานสิทธิ์
        # โดยปริยายของ "เจ้าของตาราง" ด้วย ซึ่งคือ postgres และมี DELETE ทุกตาราง
        # ถ้าไม่กรอง ข้อตรวจนี้จะไม่ผ่านตลอดกาลโดยที่ไม่มีใครได้สิทธิ์เพิ่มจริง
        # (กับดักเดียวกับที่เคยทำให้ post-apply ของ 005 รายงานผิด)
        web_delete = cur.execute(
            "SELECT count(*) FROM information_schema.table_privileges"
            " WHERE privilege_type='DELETE' AND table_schema='web'"
            "   AND grantee IN ('advisor_api','advisor_ingest','advisor_web')"
        ).fetchone()[0]
        c.check("ไม่มี advisor role ใดได้ DELETE ใน schema web",
                web_delete == 0, f"{web_delete} รายการ")

        web_role_delete = cur.execute(
            "SELECT count(*) FROM information_schema.table_privileges"
            " WHERE privilege_type='DELETE' AND grantee='advisor_web'"
        ).fetchone()[0]
        c.check("advisor_web ไม่ได้ DELETE ที่ใดเลยทั้งฐาน",
                web_role_delete == 0, f"{web_role_delete} รายการ")

        users_delete = cur.execute(
            "SELECT count(*) FROM information_schema.table_privileges"
            " WHERE privilege_type='DELETE' AND table_schema='public' AND table_name='users'"
            "   AND grantee IN ('advisor_api','advisor_ingest','advisor_web')"
        ).fetchone()[0]
        c.check("ไม่มี advisor role ใดได้ DELETE บน public.users",
                users_delete == 0, f"{users_delete} รายการ")

        # DELETE บน mko ของ advisor_ingest เป็นของเดิม — ตรวจว่า 006 ไม่ได้ไปแตะ
        mko_delete = cur.execute(
            "SELECT count(DISTINCT table_name) FROM information_schema.table_privileges"
            " WHERE privilege_type='DELETE' AND table_schema='mko' AND grantee='advisor_ingest'"
        ).fetchone()[0]
        c.check("DELETE เดิมของ advisor_ingest บน mko ยังอยู่ครบ",
                mko_delete > 0, f"{mko_delete} ตาราง")


# ---------------------------------------------------------------------
# 19–20  ตรวจตัวไฟล์ migration เอง
# ---------------------------------------------------------------------
def _statements_only(text: str) -> str:
    """
    ตัดคอมเมนต์ -- ออก เหลือเฉพาะคำสั่ง

    ใช้ได้เพราะไฟล์นี้ไม่มี -- อยู่ในสตริง (ข้อความภาษาไทยใช้ — em dash)
    ถ้าวันหนึ่งมีสตริงที่มี -- ต้องเปลี่ยนไปใช้ตัวแยกประโยค SQL จริง
    """
    return "\n".join(
        part for line in text.splitlines()
        if (part := line.split("--", 1)[0]).strip()
    )


def migration_hygiene(c: Checks) -> None:
    print("\nตัวไฟล์ migration")
    if not c.check("ไฟล์ migration 006 มีอยู่", MIGRATION.is_file(), str(MIGRATION)):
        return
    raw = MIGRATION.read_text(encoding="utf-8")
    body = _statements_only(raw)

    for word in ("PASSWORD", "SECRET", "TOKEN", "API_KEY", "SERVICE_ROLE"):
        c.check(f"ไม่มีคำว่า {word} ในคำสั่ง",
                not re.search(word, body, re.IGNORECASE),
                "พบในคำสั่ง")

    c.check("ไม่มี CREATE ROLE / ALTER ROLE",
            not re.search(r"\b(CREATE|ALTER)\s+ROLE\b", body, re.IGNORECASE))
    c.check("ไม่มี REVOKE", not re.search(r"\bREVOKE\b", body, re.IGNORECASE))
    c.check("ไม่มี DROP", not re.search(r"\bDROP\b", body, re.IGNORECASE))
    c.check("ไม่ให้ DELETE แก่ใคร", not re.search(r"\bDELETE\b", body, re.IGNORECASE))

    # ต้องตัดคำสั่ง GRANT ออกก่อน ไม่งั้นคำว่า UPDATE ใน "GRANT SELECT, INSERT, UPDATE ON …"
    # จะถูกนับเป็นการเขียนข้อมูล และจับเป้าหมายได้เป็นคำว่า on
    # (ข้อตรวจรุ่นแรกพลาดตรงนี้ รายงานเป้าหมายออกมาเป็น ['on','on','on','on', …])
    statements = [s.strip() for s in body.split(";") if s.strip()]
    targets = []
    for stmt in statements:
        if re.match(r"^\s*GRANT\b", stmt, re.IGNORECASE):
            continue
        m = re.match(r"^\s*(INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+([a-z_.]+)", stmt, re.IGNORECASE)
        if m:
            targets.append(m.group(2).lower())
    c.check("เขียนข้อมูลที่เดียวคือ ledger",
            targets == ["mko.schema_migrations"], str(targets))

    c.check("ไม่มี NOT NULL หรือ DEFAULT บนคอลัมน์ใหม่",
            not re.search(r"supabase_user_id\s+UUID\s+(NOT\s+NULL|DEFAULT)", body, re.IGNORECASE))
    c.check("ไม่มี FOREIGN KEY / REFERENCES",
            not re.search(r"\b(FOREIGN\s+KEY|REFERENCES)\b", body, re.IGNORECASE))
    c.check("อยู่ใน transaction (BEGIN และ COMMIT)",
            re.search(r"^\s*BEGIN;", body, re.MULTILINE) is not None
            and re.search(r"^\s*COMMIT;", body, re.MULTILINE) is not None)
    c.check("หยุดเสียงดังถ้าไม่มี advisor_web (RAISE EXCEPTION)",
            "RAISE EXCEPTION" in body)
    c.check("บันทึกลง ledger ด้วยชื่อ 006_web_identity_mapping",
            "006_web_identity_mapping" in body)


def main() -> None:
    ap = argparse.ArgumentParser(description="ทดสอบ migration 006")
    ap.add_argument("--database-url", required=True, help="ฐานข้อมูลทดสอบเท่านั้น")
    args = ap.parse_args()

    with psycopg.connect(args.database_url) as conn:
        db = guard(args.database_url, conn)
        print(f"ฐานข้อมูลที่ใช้ทดสอบ: {db}")
        checks = Checks()
        column_shape(checks, conn)
        partial_index(checks, conn)
        uniqueness_behaviour(checks, conn)
        users_privileges(checks, conn)
        web_privileges(checks, conn)
        function_execute(checks, conn)
        no_regression(checks, conn)
        migration_hygiene(checks)
        conn.rollback()
        sys.exit(0 if checks.report() else 1)


if __name__ == "__main__":
    main()
