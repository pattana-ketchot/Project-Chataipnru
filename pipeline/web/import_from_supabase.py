"""
นำข้อมูลหน้าเว็บจาก Supabase เข้ามาที่ schema web — Phase 4 ขั้นนำข้อมูลเข้า

    python -m pipeline.web.import_from_supabase --dry-run
    python -m pipeline.web.import_from_supabase --apply

ต่อจาก db/migrations/005_web_schema.sql ซึ่งสร้าง "ที่ว่าง" ไว้แล้วและเขียนไว้เองว่า
"การนำข้อมูลเข้าเป็นขั้นตอนแยกที่ต้องขออนุมัติเอง" — ไฟล์นี้คือขั้นตอนนั้น

หลักการ
-------
1. **ต่อฐานข้อมูลตรง ไม่ผ่าน PostgREST** เพราะต้องอ่านให้ครบทุกแถว
   RLS ของ Supabase ซ่อนข่าวที่ยังเป็นร่างจากผู้ใช้ทั่วไป และ C1 จำกัด user_profiles
   การอ่านผ่าน API จะได้ข้อมูลไม่ครบโดยไม่มีอะไรเตือน
2. **ใช้ id ของต้นทางเป็น id ปลายทาง** — ทำให้รันซ้ำได้ (ON CONFLICT DO UPDATE)
   และที่สำคัญกว่านั้น ลิงก์ที่มีอยู่แล้วอย่าง /courses/<id> ยังใช้ได้เหมือนเดิมหลังย้าย
3. **ทั้งหมดอยู่ใน transaction เดียว** ล้มกลางคันคือไม่มีอะไรเปลี่ยน
4. **ไม่แตะ public และ mko เลย** อ่าน public.courses กับ public.users อย่างเดียว
5. **ไม่พิมพ์ค่า connection string หรือค่าคีย์ใด ๆ ออกมา**

การจับคู่ course_id
------------------
site_courses.course_id คือสิ่งที่การรวมฐานข้อมูลให้มาจริง ๆ (005 บอกไว้เอง) — มันเชื่อม
"หลักสูตรที่แสดงบนเว็บ" เข้ากับ "หลักสูตรที่ AI ตอบจากเอกสาร" ซึ่งเมื่อก่อนอยู่คนละฐาน

ใช้ตารางจับคู่ที่ยืนยันแล้วใน programme_links.json **ไม่ใช่การเทียบชื่อแบบคลุมเครือ**
ที่มาของไฟล์นั้นคือ src/data/programmeLinks.js ของรีโปหน้าเว็บ ซึ่งหน้าเว็บใช้งานจริงอยู่

    สร้างใหม่ได้ด้วย (รันในรีโปหน้าเว็บ):
        node -e "import('./src/data/programmeLinks.js').then(m=>process.stdout.write(
          JSON.stringify(m.PROGRAMMES.map(p=>({supabase_course_id:p.courseId,
          supabase_title:p.courseTitle,postgres_titles:p.sourceTitles})),null,2)))"

หลักสูตรที่จับคู่ไม่ได้ course_id เป็น NULL ซึ่ง 005 อนุญาตไว้ — ดีกว่าจับคู่ผิดคน

เจ้าของแถว (created_by / updated_by)
-----------------------------------
ต้นทางชี้ไป auth.users ของ Supabase ปลายทางชี้ไป public.users แปลงผ่าน
public.users.supabase_user_id (เพิ่มไว้ใน 006) หาไม่เจอให้เป็น NULL ตามที่ 005 ระบุ
"ปล่อยให้เป็น NULL ได้ดีกว่าทิ้งแถวนั้นหรือยัดเจ้าของผิดคน"
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

LINKS_FILE = Path(__file__).resolve().parent / "programme_links.json"

# ลำดับสำคัญ: ตารางที่ไม่มีใครอ้างถึงมาก่อน — ชุดนี้ไม่มี FK ระหว่างกันจึงเรียงตามความสำคัญ
TABLES = ("site_courses", "news", "external_news", "knowledge_articles", "ai_settings")

# คอลัมน์ที่อ่านจากต้นทาง -> คอลัมน์ปลายทาง
# ชื่อที่ต่างกันสามคู่: logo->logo_url, date->published_on, image->image_url
SELECTS = {
    "site_courses": (
        "select id, title, title_en, description, logo, careers, detail,"
        " created_by, updated_by, created_at, updated_at from public.courses order by title"
    ),
    "news": (
        "select id, title, description, category, date, image, status,"
        " created_by, updated_by, created_at, updated_at from public.news order by created_at"
    ),
    "external_news": (
        "select id, slug, title, description, image_url, detail_url, facebook_url, source,"
        " published_at, published_text, synced_at, created_at from public.external_news order by created_at"
    ),
    "knowledge_articles": (
        "select id, title, content, file_path, file_name, file_size,"
        " created_by, updated_by, created_at, updated_at from public.knowledge_articles order by created_at"
    ),
    "ai_settings": "select id, model, updated_by, updated_at from public.ai_settings order by id",
}

UPSERTS = {
    "site_courses": """
        insert into web.site_courses
          (id, course_id, title, title_en, description, logo_url, careers, detail,
           created_by, updated_by, created_at, updated_at)
        values (%(id)s, %(course_id)s, %(title)s, %(title_en)s, %(description)s, %(logo_url)s,
                %(careers)s, %(detail)s, %(created_by)s, %(updated_by)s, %(created_at)s, %(updated_at)s)
        on conflict (id) do update set
          course_id = excluded.course_id, title = excluded.title, title_en = excluded.title_en,
          description = excluded.description, logo_url = excluded.logo_url, careers = excluded.careers,
          detail = excluded.detail, created_by = excluded.created_by, updated_by = excluded.updated_by,
          created_at = excluded.created_at, updated_at = excluded.updated_at
    """,
    "news": """
        insert into web.news
          (id, title, description, category, published_on, image_url, status,
           created_by, updated_by, created_at, updated_at)
        values (%(id)s, %(title)s, %(description)s, %(category)s, %(published_on)s, %(image_url)s,
                %(status)s, %(created_by)s, %(updated_by)s, %(created_at)s, %(updated_at)s)
        on conflict (id) do update set
          title = excluded.title, description = excluded.description, category = excluded.category,
          published_on = excluded.published_on, image_url = excluded.image_url, status = excluded.status,
          created_by = excluded.created_by, updated_by = excluded.updated_by,
          created_at = excluded.created_at, updated_at = excluded.updated_at
    """,
    "external_news": """
        insert into web.external_news
          (id, slug, title, description, image_url, detail_url, facebook_url, source,
           published_at, published_text, synced_at, created_at)
        values (%(id)s, %(slug)s, %(title)s, %(description)s, %(image_url)s, %(detail_url)s,
                %(facebook_url)s, %(source)s, %(published_at)s, %(published_text)s, %(synced_at)s, %(created_at)s)
        on conflict (id) do update set
          slug = excluded.slug, title = excluded.title, description = excluded.description,
          image_url = excluded.image_url, detail_url = excluded.detail_url,
          facebook_url = excluded.facebook_url, source = excluded.source,
          published_at = excluded.published_at, published_text = excluded.published_text,
          synced_at = excluded.synced_at, created_at = excluded.created_at
    """,
    "knowledge_articles": """
        insert into web.knowledge_articles
          (id, title, content, file_path, file_name, file_size,
           created_by, updated_by, created_at, updated_at)
        values (%(id)s, %(title)s, %(content)s, %(file_path)s, %(file_name)s, %(file_size)s,
                %(created_by)s, %(updated_by)s, %(created_at)s, %(updated_at)s)
        on conflict (id) do update set
          title = excluded.title, content = excluded.content, file_path = excluded.file_path,
          file_name = excluded.file_name, file_size = excluded.file_size,
          created_by = excluded.created_by, updated_by = excluded.updated_by,
          created_at = excluded.created_at, updated_at = excluded.updated_at
    """,
    "ai_settings": """
        insert into web.ai_settings (id, model, updated_by, updated_at)
        values (%(id)s, %(model)s, %(updated_by)s, %(updated_at)s)
        on conflict (id) do update set
          model = excluded.model, updated_by = excluded.updated_by, updated_at = excluded.updated_at
    """,
}

# ชื่อต้นทาง -> ชื่อปลายทาง เฉพาะคู่ที่ไม่เหมือนกัน
RENAMES = {
    "site_courses": {"logo": "logo_url"},
    "news": {"date": "published_on", "image": "image_url"},
}


def load_links() -> list[dict]:
    return json.loads(LINKS_FILE.read_text(encoding="utf-8"))


def build_course_index(dest_rows: list[dict], links: list[dict]) -> dict[str, str]:
    """
    คืน {supabase_course_id: public.courses.id}

    dest_rows คือ [{id, title}, ...] จาก public.courses
    จับคู่ด้วยชื่อที่ยืนยันแล้วเท่านั้น หลักสูตรหนึ่งมีได้หลายชื่อ (เปลี่ยนชื่อ/หลายฉบับปี)
    ถ้าชื่อในตารางจับคู่ชี้ไปหลายหลักสูตรที่ต่างกัน ถือว่าคลุมเครือและไม่จับคู่ให้เลย
    """
    by_title = {r["title"]: str(r["id"]) for r in dest_rows}
    index: dict[str, str] = {}
    for link in links:
        found = {by_title[t] for t in link["postgres_titles"] if t in by_title}
        if len(found) == 1:
            index[link["supabase_course_id"]] = found.pop()
    return index


def build_user_index(dest_rows: list[dict]) -> dict[str, str]:
    """คืน {supabase_user_id: public.users.id} จากแถวที่เติม supabase_user_id ไว้แล้ว"""
    return {str(r["supabase_user_id"]): str(r["id"]) for r in dest_rows if r.get("supabase_user_id")}


def transform(table: str, row: dict, course_index: dict, user_index: dict) -> dict:
    out = dict(row)
    for src, dst in RENAMES.get(table, {}).items():
        out[dst] = out.pop(src, None)

    if table == "site_courses":
        out["course_id"] = course_index.get(str(row["id"]))
        if isinstance(out.get("detail"), (dict, list)):
            out["detail"] = json.dumps(out["detail"], ensure_ascii=False)

    for key in ("created_by", "updated_by"):
        if key in out:
            out[key] = user_index.get(str(out[key])) if out[key] else None
    return out


def _counts(rows_by_table: dict[str, list]) -> str:
    return " · ".join(f"{t} {len(rows_by_table[t])}" for t in TABLES)


def run(source_url: str, dest_url: str, apply: bool) -> int:
    import psycopg
    from psycopg.rows import dict_row

    links = load_links()

    with psycopg.connect(source_url, row_factory=dict_row) as src:
        rows_by_table = {t: src.execute(SELECTS[t]).fetchall() for t in TABLES}

    print("อ่านจากต้นทางได้: " + _counts(rows_by_table))

    with psycopg.connect(dest_url, row_factory=dict_row) as dest:
        courses = dest.execute("select id, title from public.courses").fetchall()
        users = dest.execute(
            "select id, supabase_user_id from public.users where supabase_user_id is not null"
        ).fetchall()
        course_index = build_course_index(courses, links)
        user_index = build_user_index(users)

        print(f"จับคู่หลักสูตรได้ {len(course_index)} จาก {len(links)} รายการในตารางจับคู่")
        print(f"จับคู่ผู้ใช้ได้ {len(user_index)} คน (ที่เหลือ created_by/updated_by เป็น NULL)")

        prepared = {
            t: [transform(t, r, course_index, user_index) for r in rows_by_table[t]]
            for t in TABLES
        }

        unmatched = [r["title"] for r in prepared["site_courses"] if not r["course_id"]]
        if unmatched:
            print("หลักสูตรที่ยังไม่มี course_id: " + ", ".join(unmatched))

        if not apply:
            print("\n-- โหมดลองเท่านั้น ไม่ได้เขียนอะไร ใช้ --apply เมื่อพร้อม --")
            return 0

        with dest.transaction():
            for t in TABLES:
                for row in prepared[t]:
                    dest.execute(UPSERTS[t], row)
            after = {
                t: dest.execute(f"select count(*) as n from web.{t}").fetchone()["n"] for t in TABLES
            }

        print("นำเข้าสำเร็จ · จำนวนแถวในปลายทาง: " + " · ".join(f"{t} {after[t]}" for t in TABLES))
        for t in TABLES:
            if after[t] < len(prepared[t]):
                print(f"‼ {t} ปลายทางมีน้อยกว่าที่นำเข้า ({after[t]} < {len(prepared[t])})")
                return 1
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="นำข้อมูลหน้าเว็บจาก Supabase เข้า schema web")
    p.add_argument("--apply", action="store_true", help="เขียนจริง (ค่าตั้งต้นคือลองเท่านั้น)")
    p.add_argument("--dry-run", action="store_true", help="ลองเท่านั้น (ค่าตั้งต้น)")
    args = p.parse_args()

    source_url = os.environ.get("SUPABASE_DB_URL", "")
    dest_url = os.environ.get("DATABASE_URL", "")
    if not source_url or not dest_url:
        print("ต้องตั้ง SUPABASE_DB_URL และ DATABASE_URL ก่อน (ไม่ต้องใส่ในคำสั่ง)")
        return 2

    # SQLAlchemy ใช้ postgresql+psycopg:// ส่วน psycopg ต้องการ postgresql://
    dest_url = dest_url.replace("postgresql+psycopg://", "postgresql://")
    return run(source_url, dest_url, apply=args.apply and not args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
