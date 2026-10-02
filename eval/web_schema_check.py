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
        self.pendings: list[tuple[str, str]] = []

    def check(self, name: str, ok: bool, detail: str = "") -> None:
        (self.passed.append(name) if ok else self.failed.append((name, detail)))
        print(f"  {'ผ่าน  ' if ok else 'ไม่ผ่าน'} {name}" + (f"  — {detail}" if detail and not ok else ""))

    def returns(self, conn, name: str, sql: str, params=(), ok=lambda row: row is not None):
        """รัน SQL ที่ต้องคืนแถว แล้วตรวจแถวนั้น — error ของฐานข้อมูลนับเป็นไม่ผ่านข้อเดียว

        ต่างจากการใช้ cursor ตรง ๆ ซึ่งถ้าชนข้อจำกัดจะโยน exception ออกไปทั้งกลุ่ม
        แล้วข้อที่เหลือในกลุ่มนั้นไม่ได้รันเลย ตอนมีคนทำ regression จริง รายงานจะบอกแค่
        "กลุ่มนี้พัง" ซึ่งบอกน้อยกว่า "สามข้อนี้ไม่ผ่านเพราะอะไร" มาก
        """
        try:
            with conn.cursor() as cur:
                row = cur.execute(sql, params).fetchone()
        except psycopg.Error as e:
            conn.rollback()
            self.check(name, False, f"{type(e).__name__}: {str(e).splitlines()[0][:80]}")
            return None
        self.check(name, ok(row), str(row))
        return row

    def pending(self, name: str, why: str) -> None:
        """ข้อที่ยังพิสูจน์ที่นี่ไม่ได้ — ต้องเห็นว่าค้าง ไม่ใช่ถูกนับว่าผ่าน

        ชุดนี้ตรวจ schema ของฐานข้อมูล ข้อที่ด่านจริงอยู่ชั้น API จึงพิสูจน์ที่นี่ไม่ได้
        การนับข้อเหล่านั้นว่าผ่านจะทำให้อ่านรายงานแล้วเข้าใจว่าฐานข้อมูลกันให้แล้ว
        ซึ่งไม่จริง และเป็นความเข้าใจผิดที่อันตรายกว่าการไม่มีข้อตรวจเลย
        """
        self.pendings.append((name, why))
        print(f"  ค้าง   {name}  — {why}")

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
        line = f"  ผ่าน {len(self.passed)} · ไม่ผ่าน {len(self.failed)}"
        if self.pendings:
            line += f" · ค้าง {len(self.pendings)}"
        print(f"\n---- สรุป ----\n{line}")
        for name, detail in self.failed:
            print(f"  ไม่ผ่าน: {name} — {detail}")
        for name, why in self.pendings:
            print(f"  ค้าง: {name} — {why}")
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


# ---- [6] G1 · คอลัมน์ผู้เขียนต้องเป็น NULL ได้ทั้ง 4 ตัว ----------------
#
# การตัดสินใจ RESOLVED_WITH_NULL_LEGACY_AUTHOR (docs/B2_LEGACY_AUTHOR_RESOLUTION.md)
# ทำให้ NULL เป็น "สภาพปกติ" ของแถว legacy 15 แถว (site_courses 12 + news 3)
# ไม่ใช่กรณียกเว้น ถ้าใครเติม NOT NULL ให้คอลัมน์เหล่านี้ในอนาคต การนำเข้าจะล้มทั้งก้อน
#
# ชุดเดิมมีข้อตรวจคุ้มแค่ news.created_by หนึ่งตัวจากสี่ตัว
AUTHOR_COLUMNS = (
    ("site_courses", "created_by"),
    ("site_courses", "updated_by"),
    ("news", "created_by"),
    ("news", "updated_by"),
)


def legacy_author_nullability(c: Checks, conn) -> None:
    """G1_SCHEMA_NULLABILITY"""
    print("\n[6] G1 · คอลัมน์ผู้เขียนเป็น NULL ได้ และไม่มีค่าแทนให้เงียบ ๆ")

    with conn.cursor() as cur:
        meta = {(r[0], r[1]): (r[2], r[3]) for r in cur.execute("""
            SELECT c.relname, a.attname, a.attnotnull, a.atthasdef
            FROM pg_attribute a
            JOIN pg_class c ON c.oid = a.attrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'web' AND c.relkind = 'r'
              AND a.attname IN ('created_by', 'updated_by')
              AND a.attnum > 0 AND NOT a.attisdropped
        """).fetchall()}

    for table, col in AUTHOR_COLUMNS:
        got = meta.get((table, col))
        c.check(f"G1 {table}.{col} เป็น NULL ได้",
                got is not None and got[0] is False,
                "ไม่พบคอลัมน์" if got is None else f"attnotnull={got[0]}")

    # ต้นทาง Supabase ตั้ง courses.created_by DEFAULT auth.uid() — ถ้าปลายทางมี DEFAULT
    # ทำนองเดียวกัน การ INSERT ที่ละคอลัมน์นี้จะได้ "ใครก็ตามที่กำลังรันคำสั่งนำเข้า"
    # ยัดเข้ามาเงียบ ๆ ซึ่งคือการยัดเจ้าของผิดคนที่การตัดสินใจนี้สั่งห้ามโดยตรง
    for table, col in AUTHOR_COLUMNS:
        got = meta.get((table, col))
        c.check(f"G1 {table}.{col} ไม่มี DEFAULT (ละคอลัมน์แล้วต้องได้ NULL ไม่ใช่ค่าแทน)",
                got is not None and got[1] is False,
                "ไม่พบคอลัมน์" if got is None else f"atthasdef={got[1]}")

    # เชิงพฤติกรรม: ต้องได้แถวจริงที่ author เป็น NULL ไม่ใช่แค่ "ไม่ error"
    def both_null(row):
        return row is not None and row[-2] is None and row[-1] is None

    for table in ("site_courses", "news"):
        c.returns(conn, f"G1 {table}: ใส่ author เป็น NULL ตรง ๆ แล้วได้แถวจริง",
                  f"INSERT INTO web.{table} (title, created_by, updated_by) "
                  "VALUES ('G1 ใส่ NULL ตรง ๆ', NULL, NULL) "
                  "RETURNING id, created_by, updated_by", ok=both_null)
        conn.rollback()
        # รูปแบบที่การนำเข้า legacy จะใช้จริง — ละคอลัมน์ไปเลย
        c.returns(conn, f"G1 {table}: ละคอลัมน์ผู้เขียนแล้วได้ NULL ทั้งคู่",
                  f"INSERT INTO web.{table} (title) VALUES ('G1 ละคอลัมน์ผู้เขียน') "
                  "RETURNING created_by, updated_by", ok=both_null)
        conn.rollback()


# ---- [7] G2 · ลบผู้ใช้แล้วเนื้อหาต้องไม่หาย ----------------------------
#
# ชุดเดิมตรวจ ON DELETE SET NULL ด้วยการอ่าน pg_constraint (confdeltype = 'n')
# ซึ่งเป็นการอ่าน "ประกาศ" ไม่ใช่การพิสูจน์ "ผล" — ข้อนี้ลบผู้ใช้จริงแล้วดูว่าเกิดอะไรขึ้น
def author_fk_delete_behaviour(c: Checks, conn) -> None:
    """G2_FK_DELETE_BEHAVIOR"""
    print("\n[7] G2 · ลบผู้ใช้แล้วเนื้อหายังอยู่ และ author กลายเป็น NULL")

    # fixture ขั้นต่ำ: users บังคับแค่ email กับ password_hash
    # ต้อง commit ก่อน เพราะข้อตรวจอื่นในชุดนี้ย้อน transaction ทุกครั้ง
    with conn.cursor() as cur:
        uid = cur.execute(
            "INSERT INTO users (email, password_hash) "
            "VALUES ('webchk-g2@test.invalid', 'ไม่ใช่ hash จริง ใช้ทดสอบ') "
            "RETURNING id").fetchone()[0]
    conn.commit()

    try:
        after_steps = ("ผู้ใช้ถูกลบจริง (ไม่ใช่ลบไม่สำเร็จแล้วผ่านไปเฉย ๆ)",
                       "ลบผู้ใช้แล้วแถวเนื้อหายังอยู่",
                       "created_by กลายเป็น NULL",
                       "updated_by กลายเป็น NULL")

        for table in ("site_courses", "news"):
            # ข้อนี้กันการผ่านแบบว่างเปล่า — ถ้า author ไม่ได้ถูกตั้งตั้งแต่ต้น
            # ข้อที่เหลือจะผ่านโดยไม่ได้พิสูจน์อะไรเลย
            before = c.returns(
                conn, f"G2 {table}: ก่อนลบ author ถูกตั้งเป็นผู้ใช้จริงทั้งสองคอลัมน์",
                f"INSERT INTO web.{table} (title, created_by, updated_by) "
                "VALUES ('G2 เนื้อหาที่ต้องรอด', %s, %s) RETURNING created_by, updated_by",
                (uid, uid), ok=lambda r: r is not None and r[0] == uid and r[1] == uid)

            if before is None:
                # ตั้ง author ตั้งต้นไม่ได้ จึงไม่มีอะไรให้พิสูจน์ต่อ
                # ต้องรายงานว่าไม่ผ่าน ไม่ใช่ข้ามไปเงียบ ๆ ให้ดูเหมือนไม่มีปัญหา
                for step in after_steps:
                    c.check(f"G2 {table}: {step}", False, "ตั้ง author ตั้งต้นไม่ได้")
                conn.rollback()
                continue

            try:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM users WHERE id = %s", (uid,))
                    gone = cur.execute(
                        "SELECT count(*) FROM users WHERE id = %s", (uid,)).fetchone()[0]
                    after = cur.execute(
                        f"SELECT title, created_by, updated_by FROM web.{table} "
                        "WHERE title = 'G2 เนื้อหาที่ต้องรอด'").fetchone()
            except psycopg.Error as e:
                conn.rollback()
                detail = f"{type(e).__name__}: {str(e).splitlines()[0][:80]}"
                for step in after_steps:
                    c.check(f"G2 {table}: {step}", False, detail)
                continue

            c.check(f"G2 {table}: {after_steps[0]}", gone == 0, f"ยังเหลือ {gone} แถว")
            c.check(f"G2 {table}: {after_steps[1]}", after is not None, str(after))
            c.check(f"G2 {table}: {after_steps[2]}",
                    after is not None and after[1] is None, str(after))
            c.check(f"G2 {table}: {after_steps[3]}",
                    after is not None and after[2] is None, str(after))
            # ย้อนทั้งการลบผู้ใช้และแถวเนื้อหา เพื่อให้ตารางถัดไปเริ่มจากผู้ใช้เดิม
            conn.rollback()
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE email = 'webchk-g2@test.invalid'")
        conn.commit()


# ---- [8] G3 · created_by ห้ามเปลี่ยนตอน UPDATE -------------------------
#
# ด่านของข้อนี้ "ไม่ได้" อยู่ที่ฐานข้อมูล
# ----------------------------------------------
# Migration 005 ไม่มี trigger หรือ rule ที่ห้ามแก้ created_by และไม่ควรมี —
# การบังคับ authorization เป็นหน้าที่ของชั้น API ไม่ใช่ของ schema
#
# ข้อตรวจกลุ่มนี้จึงทำสองอย่าง
#   1. บันทึกไว้ว่าฐานข้อมูล "ยอมให้แก้" เพื่อไม่ให้ใครอ่าน G1/G2 แล้วเข้าใจผิดว่า
#      ฐานข้อมูลกันเรื่องนี้ให้แล้ว
#   2. ตรวจว่าสัญญาในเอกสารยังอยู่ครบ
# ส่วนการบังคับจริงยังค้างรอ B1 — รายงานเป็น "ค้าง" ไม่ใช่ "ผ่าน"
G3_PENDING_TAG = "G3_API_ENFORCEMENT_PENDING_B1"

_DESIGN_DOC = _ROOT / "docs" / "AUTHORIZATION_USER_MAPPING_DESIGN.md"


def author_immutability_contract(c: Checks, conn) -> None:
    """G3_API_AUTHOR_IMMUTABILITY"""
    print("\n[8] G3 · created_by ห้ามเปลี่ยนตอน UPDATE — ด่านอยู่ที่ API")

    # ไม่มี trigger บนสองตารางนี้นอกจากตัวที่ดูแล updated_at
    with conn.cursor() as cur:
        names = sorted(r[0] for r in cur.execute("""
            SELECT t.tgname FROM pg_trigger t
            JOIN pg_class c ON c.oid = t.tgrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'web' AND NOT t.tgisinternal
              AND c.relname IN ('site_courses', 'news')
        """).fetchall())
    c.check("G3 ฐานข้อมูลไม่มี trigger ที่ตั้งใจกัน created_by (มีแต่ตัวดูแล updated_at)",
            names == ["trg_news_updated_at", "trg_site_courses_updated_at"], str(names))

    # ยืนยันเชิงพฤติกรรมว่าฐานข้อมูลยอมให้ UPDATE เปลี่ยน created_by ได้
    # นี่คือ "สภาพที่เป็นจริง" ไม่ใช่สิ่งที่ต้องการ — บันทึกไว้ให้ชัดว่าด่านอยู่ที่อื่น
    with conn.cursor() as cur:
        uid = cur.execute(
            "INSERT INTO users (email, password_hash) "
            "VALUES ('webchk-g3@test.invalid', 'ไม่ใช่ hash จริง ใช้ทดสอบ') "
            "RETURNING id").fetchone()[0]
    conn.commit()
    name = ("G3 ฐานข้อมูลยอมให้ UPDATE เปลี่ยน created_by จาก NULL เป็นค่าอื่นได้ "
            "(จึงต้องกันที่ API ไม่ใช่ที่ schema)")
    try:
        # ต้องเป็นสองคำสั่งแยกกัน — แถวที่ INSERT ใน CTE ที่เขียนข้อมูลจะไม่อยู่ใน
        # snapshot ของ UPDATE ในคำสั่งเดียวกัน UPDATE จะไม่เจอแถวนั้นและแก้ 0 แถว
        with conn.cursor() as cur:
            rid = cur.execute(
                "INSERT INTO web.news (title, created_by) "
                "VALUES ('G3 แถว legacy', NULL) RETURNING id").fetchone()[0]
            after = cur.execute(
                "UPDATE web.news SET created_by = %s WHERE id = %s RETURNING created_by",
                (uid, rid)).fetchone()
    except psycopg.Error as e:
        conn.rollback()
        c.check(name, False, f"{type(e).__name__}: {str(e).splitlines()[0][:80]}")
    else:
        c.check(name, after is not None and after[0] == uid, str(after))
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE email = 'webchk-g3@test.invalid'")
        conn.commit()

    # สัญญาที่เอกสารออกแบบเขียนไว้ ต้องยังอยู่ ถ้าใครลบทิ้งต้องมีอะไรฟ้อง
    try:
        doc = _DESIGN_DOC.read_text(encoding="utf-8")
    except OSError as e:
        doc = ""
        c.check("G3 อ่านเอกสารสัญญา authorization ได้", False, f"{type(e).__name__}: {e}")
    if doc:
        c.check("G3 เอกสารระบุว่า CREATE ตั้งทั้ง created_by และ updated_by จากผู้เรียก",
                "1a. CREATE" in doc and "created_by และ updated_by" in doc, "ไม่พบกฎ 1a")
        c.check("G3 เอกสารระบุว่า UPDATE ห้ามแตะ created_by",
                "1b. UPDATE" in doc and "ห้ามแตะ created_by" in doc, "ไม่พบกฎ 1b")
        c.check("G3 เอกสารระบุว่าห้ามเชื่อ created_by/updated_by จาก request body",
                "ห้ามรับจาก request body" in doc, "ไม่พบกฎข้อ 1")

    # ด่านจริงยังไม่มี — ไม่มีโค้ดบริการใดอ้างถึง web.site_courses หรือ web.news เลย
    c.pending(f"G3 API บังคับ created_by immutability — {G3_PENDING_TAG}",
              "ยังไม่มี endpoint POST/PATCH ของ web.site_courses / web.news "
              "จึงยังไม่มีอะไรให้ทดสอบ ต้องรอ B1 เฟส 1")
    c.pending(f"G3 PATCH ที่ส่ง created_by ปลอมมาใน body ต้องไม่มีผล — {G3_PENDING_TAG}",
              "ต้องเขียนพร้อม endpoint ในรอบ B1 ห้ามสร้าง API เพียงเพื่อให้ข้อนี้ผ่าน")


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
        legacy_author_nullability(checks, conn)
        author_fk_delete_behaviour(checks, conn)
        author_immutability_contract(checks, conn)
        conn.rollback()
        sys.exit(0 if checks.report() else 1)


if __name__ == "__main__":
    main()
