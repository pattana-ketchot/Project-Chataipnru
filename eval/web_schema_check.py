"""
ทดสอบ schema `web` ที่ migration 005 สร้าง (Phase 4 — รวมฐานข้อมูล)

    python eval/web_schema_check.py --database-url postgresql://<owner>@HOST:PORT/web_test

ต้องเป็นฐานข้อมูลทดสอบที่แยกจาก production เท่านั้น
------------------------------------------------
มีด่านสองชั้นก่อนแตะข้อมูลใด
  1. ชื่อฐานข้อมูลใน URL ต้องอยู่ในรายการที่อนุญาต และห้ามมีคำว่า course_advisor
  2. ถามเซิร์ฟเวอร์เองด้วย current_database() ว่าต่ออยู่กับฐานไหนจริง

สิ่งที่ต้องพิสูจน์ที่นี่
----------------------
ชุดนี้ไม่ได้ตรวจแค่ว่าตารางถูกสร้าง แต่ตรวจว่า constraint **ทำงานจริง** คือปฏิเสธ
ข้อมูลที่ผิดรูปได้ ไม่ใช่แค่ประกาศไว้เฉย ๆ เพราะ constraint ที่ประกาศผิดด้าน
(เช่นบังคับคอลัมน์ที่ต้นทางปล่อยว่างได้) จะทำให้นำข้อมูลจริงเข้าไม่ได้ทั้งก้อน

หมายเหตุประวัติ: ชุดนี้รุ่นแรกอ้างว่าต้นทางมี "0 FK · 0 CHECK · 1 UNIQUE" ซึ่งผิด
ของจริงคือ 7 FK · 2 CHECK · 4 UNIQUE (ที่มา: supabase_schema.sql ในรีโปของหน้าเว็บ)
ดูรายละเอียดใน docs/SUPABASE_PRE_MIGRATION_AUDIT.md ข้อ 12

และต้องพิสูจน์ว่า migration นี้ **ไม่แตะ public กับ mko** ซึ่งเป็นสัญญาหลักที่ทำให้
การรวมฐานข้อมูลครั้งนี้ถอนกลับได้และไม่กระทบ RAG, crawler, chat

ไม่ย้ายข้อมูลจริงจากที่ใดทั้งสิ้น ทุกแถวในชุดนี้สร้างขึ้นเองแล้วลบทิ้งเมื่อจบ
"""
from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

import psycopg

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

ALLOWED_DB_NAMES = {"web_test", "crawl_test", "e2e_test"}
FORBIDDEN_IN_URL = "course_advisor"

EXPECTED_TABLES = {
    "ai_settings", "external_news", "knowledge_articles", "news", "site_courses",
}

# (ตารางลูก, คอลัมน์, ตารางแม่, การกระทำตอนลบ)
EXPECTED_FKS = {
    ("site_courses", "course_id", "courses", "n"),
    ("site_courses", "created_by", "users", "n"),
    ("site_courses", "updated_by", "users", "n"),
    ("news", "created_by", "users", "n"),
    ("news", "updated_by", "users", "n"),
    ("knowledge_articles", "created_by", "users", "n"),
    ("knowledge_articles", "updated_by", "users", "n"),
    ("ai_settings", "updated_by", "users", "n"),
}


class Checks:
    def __init__(self) -> None:
        self.passed: list[str] = []
        self.failed: list[tuple[str, str]] = []

    def check(self, name: str, ok: bool, detail: str = "") -> None:
        (self.passed.append(name) if ok else self.failed.append((name, detail)))
        print(f"  {'ผ่าน  ' if ok else 'ไม่ผ่าน'} {name}" + (f"  — {detail}" if detail and not ok else ""))

    def rejects(self, conn, name: str, sql: str, params=()) -> None:
        """ข้อมูลที่ผิดรูปต้องถูกฐานข้อมูลปฏิเสธ ไม่ใช่รับไว้เงียบ ๆ"""
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
            conn.rollback()
            self.check(name, False, "ฐานข้อมูลยอมรับข้อมูลที่ควรถูกปฏิเสธ")
        except psycopg.Error as e:
            conn.rollback()
            code = getattr(e, "sqlstate", "?")
            self.check(name, True, f"ถูกปฏิเสธด้วย SQLSTATE {code}")

    def accepts(self, conn, name: str, sql: str, params=()) -> None:
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
            conn.rollback()
            self.check(name, True)
        except psycopg.Error as e:
            conn.rollback()
            self.check(name, False, f"{type(e).__name__}: {str(e)[:90]}")

    def report(self) -> bool:
        print(f"\n---- สรุป ----\n  ผ่าน {len(self.passed)} · ไม่ผ่าน {len(self.failed)}")
        for name, detail in self.failed:
            print(f"  ไม่ผ่าน: {name} — {detail}")
        return not self.failed


def guard(url: str, conn: psycopg.Connection) -> str:
    if FORBIDDEN_IN_URL in url:
        raise SystemExit(f"ปฏิเสธ: URL มีคำว่า {FORBIDDEN_IN_URL!r} — ห้ามชี้ไปฐานข้อมูลจริง")
    with conn.cursor() as cur:
        db = cur.execute("SELECT current_database()").fetchone()[0]
    if db not in ALLOWED_DB_NAMES:
        raise SystemExit(f"ปฏิเสธ: ต่ออยู่กับฐานข้อมูล {db!r} ซึ่งไม่อยู่ในรายการที่อนุญาต "
                         f"{sorted(ALLOWED_DB_NAMES)}")
    return db


# ---- [1] โครงสร้างที่ประกาศไว้ ---------------------------------------
def structure(c: Checks, conn) -> None:
    print("\n[1] โครงสร้างที่ migration ประกาศไว้")
    with conn.cursor() as cur:
        tables = {r[0] for r in cur.execute(
            "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='web' AND c.relkind='r'").fetchall()}
    c.check("มี schema web และตารางครบตามที่ออกแบบ", tables == EXPECTED_TABLES,
            f"เกิน {sorted(tables - EXPECTED_TABLES)} ขาด {sorted(EXPECTED_TABLES - tables)}")

    with conn.cursor() as cur:
        fks = {(r[0], r[1], r[2], r[3]) for r in cur.execute("""
            SELECT cl.relname, a.attname, pr.relname, con.confdeltype::text
            FROM pg_constraint con
            JOIN pg_class cl ON cl.oid = con.conrelid
            JOIN pg_namespace cn ON cn.oid = cl.relnamespace
            JOIN pg_class pr ON pr.oid = con.confrelid
            JOIN unnest(con.conkey) AS k(attnum) ON TRUE
            JOIN pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = k.attnum
            WHERE cn.nspname = 'web' AND con.contype::text = 'f'
        """).fetchall()}
    c.check(f"foreign key ครบ {len(EXPECTED_FKS)} เส้น", fks == EXPECTED_FKS,
            f"เกิน {sorted(fks - EXPECTED_FKS)} ขาด {sorted(EXPECTED_FKS - fks)}")
    c.check("ทุก FK ตั้ง ON DELETE SET NULL (ลบผู้ใช้แล้วเนื้อหาต้องไม่หาย)",
            all(f[3] == "n" for f in fks), str(sorted(f for f in fks if f[3] != "n")))

    with conn.cursor() as cur:
        n_chk = cur.execute(
            "SELECT count(*) FROM pg_constraint con JOIN pg_class c ON c.oid=con.conrelid "
            "JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='web' AND con.contype::text='c'").fetchone()[0]
        n_uq = cur.execute(
            "SELECT count(*) FROM pg_index i JOIN pg_class c ON c.oid=i.indrelid "
            "JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='web' AND i.indisunique").fetchone()[0]
    # ต้นทางมี CHECK 2 · UNIQUE 4 — ปลายทางต้องไม่น้อยกว่านั้นในสัดส่วนที่เทียบได้
    c.check("มี check constraint อย่างน้อย 3 ตัว", n_chk >= 3, f"{n_chk} ตัว")
    c.check("มี unique index อย่างน้อย 7 ตัว", n_uq >= 7, f"{n_uq} ตัว")

    with conn.cursor() as cur:
        bad_ts = cur.execute("""
            SELECT count(*) FROM pg_attribute a
            JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace
            JOIN pg_type t ON t.oid=a.atttypid
            WHERE n.nspname='web' AND c.relkind='r' AND a.attnum>0 AND NOT a.attisdropped
              AND t.typname = 'timestamp'
        """).fetchone()[0]
    # ต้นทางใช้ TIMESTAMP WITH TIME ZONE อยู่แล้ว ปลายทางต้องเป็น timestamptz เหมือนกัน
    # จึงย้ายได้โดยไม่ต้องตีความเขตเวลา ข้อนี้กันไม่ให้มีคอลัมน์ไร้เขตเวลาหลุดเข้ามา
    c.check("ทุกคอลัมน์เวลาเป็น timestamptz", bad_ts == 0, f"พบคอลัมน์ไร้เขตเวลา {bad_ts}")


# ---- [1b] ความกว้างคอลัมน์ต้องไม่แคบกว่าต้นทาง -----------------------
# ตัวเลขทุกตัวมาจาก information_schema.columns ของ Supabase production
# (SUPABASE_LIVE_VERIFICATION ข้อ 5.1) ไม่ใช่จากไฟล์ snapshot
LIVE_WIDTHS = {
    ("site_courses", "title"): 255,
    ("site_courses", "title_en"): 255,
    ("news", "title"): 500,
    ("news", "category"): 100,
    ("news", "status"): 20,
    ("external_news", "title"): 500,
    ("external_news", "slug"): 255,
    ("external_news", "published_text"): 100,
    ("external_news", "source"): 100,
    ("knowledge_articles", "title"): 500,
    ("ai_settings", "model"): 255,
}


def column_widths(c: Checks, conn) -> None:
    """คอลัมน์ข้อความที่แคบกว่าต้นทางจะพังตอน sync ไม่ใช่ตอน migrate

    ถ้าปลายทางรับได้น้อยกว่าต้นทาง ข้อมูลชุดแรกอาจผ่านทั้งหมด แล้วไปล้ม
    ตอนที่มีแถวยาวเกินเข้ามาภายหลัง ซึ่งหาสาเหตุยากกว่ามาก
    """
    print("\n[1b] ความกว้างคอลัมน์เทียบกับต้นทาง")

    with conn.cursor() as cur:
        got = dict(((r[0], r[1]), r[2]) for r in cur.execute("""
            SELECT c.relname, a.attname, a.atttypmod - 4
            FROM pg_attribute a
            JOIN pg_class c ON c.oid = a.attrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            JOIN pg_type t ON t.oid = a.atttypid
            WHERE n.nspname = 'web' AND c.relkind = 'r'
              AND a.attnum > 0 AND NOT a.attisdropped
              AND t.typname = 'varchar' AND a.atttypmod > 0
        """).fetchall())

    for (table, col), src in sorted(LIVE_WIDTHS.items()):
        tgt = got.get((table, col))
        c.check(f"{table}.{col} กว้างพอสำหรับต้นทาง varchar({src})",
                tgt is not None and tgt >= src,
                f"ปลายทาง {tgt}" if tgt is not None else "ไม่พบคอลัมน์")

    narrower = sorted(f"{t}.{col} {got[(t, col)]}<{w}"
                      for (t, col), w in LIVE_WIDTHS.items()
                      if (t, col) in got and got[(t, col)] < w)
    c.check("ไม่มีคอลัมน์ใดแคบกว่าต้นทางเลย", not narrower, ", ".join(narrower))

    # พิสูจน์เชิงพฤติกรรม ไม่ใช่แค่อ่าน catalog
    long500 = "ก" * 500
    c.accepts(conn, "news รับ title ยาว 500 ตัวอักษรได้",
              "INSERT INTO web.news (title) VALUES (%s)", (long500,))
    c.accepts(conn, "external_news รับ title ยาว 500 ตัวอักษรได้",
              "INSERT INTO web.external_news (title, detail_url, source) "
              "VALUES (%s, 'https://example.invalid/a', 'test')", (long500,))
    c.accepts(conn, "knowledge_articles รับ title ยาว 500 ตัวอักษรได้",
              "INSERT INTO web.knowledge_articles (title) VALUES (%s)", (long500,))
    c.rejects(conn, "news ปฏิเสธ title ที่ยาวเกิน 500",
              "INSERT INTO web.news (title) VALUES (%s)", ("ก" * 501,))


# ---- [2] constraint ต้องทำงานจริง ไม่ใช่แค่ประกาศไว้ ------------------
def enforcement(c: Checks, conn) -> None:
    print("\n[2] constraint ปฏิเสธข้อมูลผิดรูปได้จริง")

    c.rejects(conn, "news: status ที่ไม่รู้จักถูกปฏิเสธ",
              "INSERT INTO web.news (title, status) VALUES ('t', 'publsihed')")
    c.accepts(conn, "news: status ที่ถูกต้องผ่าน",
              "INSERT INTO web.news (title, status) VALUES ('t', 'draft')")
    c.rejects(conn, "news: title เป็น NULL ถูกปฏิเสธ",
              "INSERT INTO web.news (title) VALUES (NULL)")

    # กุญแจธรรมชาติของต้นทางคือ detail_url ไม่ใช่ slug
    c.rejects(conn, "external_news: detail_url ซ้ำถูกปฏิเสธ",
              "INSERT INTO web.external_news (detail_url, title, source) "
              "VALUES ('u1','a','s'),('u1','b','s')")
    c.rejects(conn, "external_news: detail_url เป็น NULL ถูกปฏิเสธ",
              "INSERT INTO web.external_news (detail_url, title, source) VALUES (NULL,'a','s')")
    c.rejects(conn, "external_news: source เป็น NULL ถูกปฏิเสธ",
              "INSERT INTO web.external_news (detail_url, title, source) VALUES ('u1','a',NULL)")
    c.accepts(conn, "external_news: detail_url ต่างกันผ่าน",
              "INSERT INTO web.external_news (detail_url, title, source) "
              "VALUES ('u1','a','s'),('u2','b','s')")

    # slug ต้นทางเป็น NULL ได้ และ unique เฉพาะแถวที่มีค่า (partial unique)
    c.accepts(conn, "external_news: หลายแถวที่ slug เป็น NULL อยู่ร่วมกันได้",
              "INSERT INTO web.external_news (detail_url, title, source, slug) "
              "VALUES ('u1','a','s',NULL),('u2','b','s',NULL),('u3','c','s',NULL)")
    c.rejects(conn, "external_news: slug ที่มีค่าซ้ำกันถูกปฏิเสธ",
              "INSERT INTO web.external_news (detail_url, title, source, slug) "
              "VALUES ('u1','a','s','x'),('u2','b','s','x')")
    c.accepts(conn, "external_news: slug ที่มีค่าต่างกันผ่าน",
              "INSERT INTO web.external_news (detail_url, title, source, slug) "
              "VALUES ('u1','a','s','x'),('u2','b','s','y')")

    c.rejects(conn, "ai_settings: แถวที่สอง (id=2) ถูกปฏิเสธ",
              "INSERT INTO web.ai_settings (id, model) VALUES (2, 'x')")
    c.accepts(conn, "ai_settings: แถวเดียว id=1 ผ่าน",
              "INSERT INTO web.ai_settings (id, model) VALUES (1, 'x')")
    c.rejects(conn, "ai_settings: model เป็น NULL ถูกปฏิเสธ",
              "INSERT INTO web.ai_settings (id, model) VALUES (1, NULL)")

    c.rejects(conn, "knowledge_articles: file_size ติดลบถูกปฏิเสธ",
              "INSERT INTO web.knowledge_articles (title, file_size) VALUES ('t', -1)")
    c.accepts(conn, "knowledge_articles: file_size เป็น NULL ได้ (ไม่มีไฟล์แนบ)",
              "INSERT INTO web.knowledge_articles (title, file_size) VALUES ('t', NULL)")

    ghost = str(uuid.uuid4())
    # ต้นทางปล่อยให้ careers และ detail เป็น NULL ได้ (supabase_schema.sql:50,56)
    # ถ้าปลายทางบังคับ NOT NULL ข้อมูลจริงที่ยังไม่ได้กรอกจะนำเข้าไม่ได้ทั้งก้อน
    c.accepts(conn, "site_courses: careers และ detail เป็น NULL ได้ตามต้นทาง",
              "INSERT INTO web.site_courses (title, careers, detail) "
              "VALUES ('t', NULL, NULL)")
    c.accepts(conn, "site_courses: title_en กับ description เป็น NULL ได้",
              "INSERT INTO web.site_courses (title, title_en, description) "
              "VALUES ('t', NULL, NULL)")

    c.rejects(conn, "site_courses: course_id ที่ไม่มีอยู่จริงถูกปฏิเสธ",
              "INSERT INTO web.site_courses (title, course_id) VALUES ('t', %s)", (ghost,))
    c.rejects(conn, "news: created_by ที่ไม่มีอยู่จริงถูกปฏิเสธ",
              "INSERT INTO web.news (title, created_by) VALUES ('t', %s)", (ghost,))
    c.accepts(conn, "news: created_by เป็น NULL ได้ (ผู้เขียนเดิมแมปไม่ได้)",
              "INSERT INTO web.news (title, created_by) VALUES ('t', NULL)")


# ---- [3] partial unique index ของ course_id --------------------------
def partial_unique(c: Checks, conn) -> None:
    print("\n[3] การผูกกับหลักสูตรจริง — หนึ่งต่อหนึ่ง แต่ยังไม่ผูกก็ได้")
    # ต้อง commit แถวตั้งต้นก่อน เพราะ accepts()/rejects() ย้อน transaction ทุกครั้ง
    # ถ้าไม่ commit แถวนี้จะหายไปพร้อมการย้อนครั้งแรก แล้วข้อตรวจที่เหลือจะล้มเพราะ
    # ของตั้งต้นหาย ไม่ใช่เพราะ constraint ผิด
    with conn.cursor() as cur:
        cid = cur.execute(
            "INSERT INTO courses (code, title) VALUES ('WEBCHK1','ทดสอบ') RETURNING id").fetchone()[0]
    conn.commit()
    try:
        c.accepts(conn, "หลายแถวที่ยังไม่ผูกหลักสูตร (course_id NULL) อยู่ร่วมกันได้",
                  "INSERT INTO web.site_courses (title, course_id) VALUES ('a',NULL),('b',NULL),('c',NULL)")
        c.rejects(conn, "ผูกหลักสูตรเดียวกันสองแถวถูกปฏิเสธ",
                  "INSERT INTO web.site_courses (title, course_id) VALUES ('a',%s),('b',%s)", (cid, cid))
        c.accepts(conn, "ผูกหลักสูตรหนึ่งแถวผ่าน",
                  "INSERT INTO web.site_courses (title, course_id) VALUES ('a',%s)", (cid,))

        # ลบหลักสูตรแล้วแถวแสดงผลต้องไม่หาย แค่ขาดการผูก
        with conn.cursor() as cur:
            cur.execute("INSERT INTO web.site_courses (title, course_id) VALUES ('keepme', %s)", (cid,))
            cur.execute("DELETE FROM courses WHERE id = %s", (cid,))
            row = cur.execute(
                "SELECT title, course_id FROM web.site_courses WHERE title='keepme'").fetchone()
        # ยังไม่ commit — ข้อตรวจนี้ดูผลภายใน transaction แล้วย้อนทิ้งทั้งหมด
        c.check("ลบหลักสูตรแล้วแถวแสดงผลยังอยู่", row is not None, str(row))
        c.check("และ course_id กลายเป็น NULL ไม่ใช่ค้างชี้ของที่ไม่มีแล้ว",
                row is not None and row[1] is None, str(row))
        conn.rollback()
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM courses WHERE code = 'WEBCHK1'")
        conn.commit()


# ---- [3b] trigger รักษา updated_at -----------------------------------
def updated_at_trigger(c: Checks, conn) -> None:
    """updated_at ต้องขยับเองตอน UPDATE แต่ต้องไม่แตะค่าที่ใส่มาตอน INSERT

    ข้อที่สองสำคัญต่อการนำเข้าข้อมูล — ถ้า trigger ทำงานตอน INSERT ด้วย
    ค่าเวลาเดิมของทุกแถวจะถูกเขียนทับด้วยเวลาที่นำเข้า ประวัติว่าแถวไหน
    แก้ล่าสุดเมื่อไหร่จะหายทั้งตาราง
    """
    print("\n[3b] trigger รักษา updated_at")

    with conn.cursor() as cur:
        n = cur.execute("""
            SELECT count(*) FROM pg_trigger t
            JOIN pg_class c ON c.oid = t.tgrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'web' AND NOT t.tgisinternal
        """).fetchone()[0]
    c.check("มี trigger ครบ 4 ตัวใน schema web", n == 4, f"{n} ตัว")

    with conn.cursor() as cur:
        only_update = cur.execute("""
            SELECT bool_and(t.tgtype & 4 = 0 AND t.tgtype & 16 <> 0)
            FROM pg_trigger t
            JOIN pg_class c ON c.oid = t.tgrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'web' AND NOT t.tgisinternal
        """).fetchone()[0]
    c.check("ทุก trigger ทำงานเฉพาะ UPDATE ไม่ทำงานตอน INSERT",
            only_update is True, str(only_update))

    old = "2020-01-02 03:04:05+00"
    try:
        # นำเข้าแถวที่มีเวลาเดิมติดมา — trigger ต้องไม่แตะ
        with conn.cursor() as cur:
            row = cur.execute(
                "INSERT INTO web.news (title, created_at, updated_at) "
                "VALUES ('import', %s, %s) RETURNING created_at, updated_at",
                (old, old)).fetchone()
        c.check("นำเข้าแถวแล้ว created_at เดิมไม่ถูกเขียนทับ",
                row[0].year == 2020, str(row[0]))
        c.check("นำเข้าแถวแล้ว updated_at เดิมไม่ถูกเขียนทับ",
                row[1].year == 2020, str(row[1]))

        # แก้แถวนั้น — updated_at ต้องขยับ แต่ created_at ต้องไม่ขยับ
        with conn.cursor() as cur:
            row2 = cur.execute(
                "UPDATE web.news SET title = 'changed' WHERE title = 'import' "
                "RETURNING created_at, updated_at").fetchone()
        c.check("แก้แถวแล้ว updated_at ขยับเอง", row2[1].year > 2020, str(row2[1]))
        c.check("แก้แถวแล้ว created_at ไม่ขยับ", row2[0].year == 2020, str(row2[0]))
    finally:
        conn.rollback()


# ---- [4] สัญญาหลัก: ไม่แตะ public และ mko ----------------------------
def untouched(c: Checks, conn) -> None:
    print("\n[4] สัญญาหลักของ migration — ไม่แตะ public และ mko")
    with conn.cursor() as cur:
        pub = cur.execute("SELECT count(*) FROM information_schema.tables "
                          "WHERE table_schema='public' AND table_type='BASE TABLE'").fetchone()[0]
        mko = cur.execute("SELECT count(*) FROM information_schema.tables "
                          "WHERE table_schema='mko' AND table_type='BASE TABLE'").fetchone()[0]
        mko_v = cur.execute("SELECT count(*) FROM information_schema.views "
                            "WHERE table_schema='mko'").fetchone()[0]
    c.check("public ยังมี 10 ตารางเท่าเดิม", pub == 10, f"{pub} ตาราง")
    c.check("mko ยังมี 20 ตารางเท่าเดิม", mko == 20, f"{mko} ตาราง")
    c.check("mko ยังมี 8 view เท่าเดิม", mko_v == 8, f"{mko_v} view")

    with conn.cursor() as cur:
        dim = cur.execute(
            "SELECT a.atttypmod FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid "
            "WHERE c.relname='course_chunks' AND a.attname='embedding'").fetchone()
        idx = cur.execute(
            "SELECT pg_get_indexdef(i.indexrelid) FROM pg_index i JOIN pg_class c ON c.oid=i.indrelid "
            "JOIN pg_class ic ON ic.oid=i.indexrelid "
            "WHERE c.relname='course_chunks' AND ic.relname='idx_course_chunks_embedding'").fetchone()
    c.check("course_chunks.embedding ยังเป็น 1024 มิติ", dim is not None and dim[0] == 1024, str(dim))
    c.check("index ivfflat ของ pgvector ยังเหมือนเดิม",
            idx is not None and "ivfflat" in idx[0] and "vector_cosine_ops" in idx[0],
            str(idx)[:90])

    # ไม่มี FK ของ web ที่ชี้เข้ามาแล้วบังคับให้ public ต้องเปลี่ยนอะไร
    with conn.cursor() as cur:
        inbound = cur.execute("""
            SELECT count(*) FROM pg_constraint con
            JOIN pg_class cl ON cl.oid = con.conrelid
            JOIN pg_namespace cn ON cn.oid = cl.relnamespace
            WHERE cn.nspname='public' AND con.contype::text='f'
              AND con.confrelid IN (SELECT c.oid FROM pg_class c
                                    JOIN pg_namespace n ON n.oid=c.relnamespace
                                    WHERE n.nspname='web')
        """).fetchone()[0]
    c.check("ไม่มี FK จาก public ชี้มาหา web (ทิศทางพึ่งพาถูกต้อง)", inbound == 0, f"{inbound} เส้น")


# ---- [5] สิทธิ์ของ role ----------------------------------------------
def privileges(c: Checks, conn) -> None:
    print("\n[5] สิทธิ์ของ role")
    with conn.cursor() as cur:
        has_api = cur.execute("SELECT 1 FROM pg_roles WHERE rolname='advisor_api'").fetchone()
    if not has_api:
        c.check("role advisor_api มีอยู่", False, "ไม่พบ role — ข้ามชุดสิทธิ์")
        return

    def granted(role: str, table: str, priv: str) -> bool:
        with conn.cursor() as cur:
            return cur.execute("SELECT has_table_privilege(%s, %s, %s)",
                               (role, f"web.{table}", priv)).fetchone()[0]

    for t in sorted(EXPECTED_TABLES):
        c.check(f"advisor_api อ่าน web.{t} ได้", granted("advisor_api", t, "SELECT"))
    for t in ("site_courses", "news", "knowledge_articles", "ai_settings"):
        c.check(f"advisor_api เขียน web.{t} ได้", granted("advisor_api", t, "INSERT"))
    c.check("advisor_api เขียน web.external_news ไม่ได้ (เป็นของตัวดึงข่าว)",
            not granted("advisor_api", "external_news", "INSERT"))
    for t in sorted(EXPECTED_TABLES):
        c.check(f"ไม่มีใครลบ web.{t} ได้ — advisor_api", not granted("advisor_api", t, "DELETE"))

    with conn.cursor() as cur:
        has_ing = cur.execute("SELECT 1 FROM pg_roles WHERE rolname='advisor_ingest'").fetchone()
    if has_ing:
        c.check("advisor_ingest เขียน web.external_news ได้",
                granted("advisor_ingest", "external_news", "INSERT"))
        c.check("advisor_ingest เขียน web.news ไม่ได้",
                not granted("advisor_ingest", "news", "INSERT"))


def main() -> None:
    ap = argparse.ArgumentParser(description="ทดสอบ schema web ของ migration 005")
    ap.add_argument("--database-url", required=True, help="ฐานข้อมูลทดสอบเท่านั้น")
    args = ap.parse_args()

    with psycopg.connect(args.database_url) as conn:
        db = guard(args.database_url, conn)
        print(f"ฐานข้อมูลที่ใช้ทดสอบ: {db}")
        checks = Checks()
        structure(checks, conn)
        column_widths(checks, conn)
        enforcement(checks, conn)
        partial_unique(checks, conn)
        updated_at_trigger(checks, conn)
        untouched(checks, conn)
        privileges(checks, conn)
        conn.rollback()
        sys.exit(0 if checks.report() else 1)


if __name__ == "__main__":
    main()
