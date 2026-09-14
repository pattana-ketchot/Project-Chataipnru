"""
เผยแพร่ค่าที่ผ่านการตรวจ — Phase 2 ของ docs/MKO_STRUCTURED_DATA_DESIGN.md

    python -m pipeline.mko.publish --by "ชื่อผู้เผยแพร่" --dry-run
    python -m pipeline.mko.publish --by "ชื่อผู้เผยแพร่"
    python -m pipeline.mko.publish --by "ชื่อผู้เผยแพร่" --human-only

เผยแพร่เฉพาะค่าที่สถานะ verified ในรอบสกัดล่าสุด candidate / needs_review / rejected ไม่ถูกเผยแพร่เลย

นโยบาย
    verified_any         (ค่าตั้งต้น) verified จากกฎอัตโนมัติหรือจากคน ใช้กับโหมด shadow ซึ่งไม่แสดงผลให้ผู้ใช้
    verified_human_only  (--human-only) เฉพาะค่าที่คนตรวจแล้ว — ควรใช้ก่อนเปิดคำตอบให้ผู้ใช้จริง (Phase 3)

แต่ละครั้งสร้างภาพถ่ายใหม่ใน mko.published_values / published_list_items พร้อมไฟล์ หน้า และข้อความที่ยกมา backend
อ่านเฉพาะการเผยแพร่ครั้งล่าสุดผ่าน mko.v_live_* การสกัดหรือตรวจใหม่จึงไม่เปลี่ยนข้อมูลที่ backend เห็นจนกว่าจะเผยแพร่อีกครั้ง
ย้อนกลับได้ด้วยการลบการเผยแพร่ครั้งล่าสุด (--rollback-latest)

หลักสูตรที่มีหลายเอกสาร (ฉบับเต็มกับใบสรุป) ใช้หลักฐานจากเอกสารหลักของหลักสูตร ถ้าเอกสารให้ค่า verified ต่างกัน field นั้น
ไม่ถูกเผยแพร่และถูกรายงานไว้ ไม่เลือกค่าใดค่าหนึ่งให้
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import psycopg  # noqa: E402
from psycopg.rows import dict_row  # noqa: E402
from psycopg.types.json import Jsonb  # noqa: E402

from pipeline.mko.extract import PARSER_VERSION  # noqa: E402
from pipeline.mko.review import HUMAN_PREFIX, LATEST_RUNS, LIST_ITEM_TYPES, list_key, scalar_key  # noqa: E402
from pipeline.mko.run import database_url  # noqa: E402

VALUES_SQL = f"""
    WITH latest AS ({LATEST_RUNS})
    SELECT d.course_id, fv.run_id, fv.document_id, d.original_filename, fv.field_key, fv.value_text, fv.value_int,
           fv.reviewed_by, e.page_start, e.page_end, e.quote, cur.primary_document_id
      FROM latest l
      JOIN mko.field_values fv ON fv.run_id = l.id
      JOIN public.course_documents d ON d.id = fv.document_id
      JOIN mko.curricula cur ON cur.id = fv.curriculum_id
      JOIN mko.evidence e ON e.id = fv.evidence_id
     WHERE fv.status = 'verified'
"""


def _pick(rows: list[dict]) -> dict:
    """ใช้หลักฐานจากเอกสารหลักของหลักสูตรก่อน ถ้าไม่มีใช้ไฟล์แรกตามชื่อ"""
    primary = [r for r in rows if r["document_id"] == r["primary_document_id"]]
    return (primary or sorted(rows, key=lambda r: r["original_filename"]))[0]


def collect(conn, human_only: bool) -> tuple[list[dict], list[dict], list[str]]:
    rows = conn.execute(VALUES_SQL).fetchall()
    if human_only:
        rows = [r for r in rows if (r["reviewed_by"] or "").startswith(HUMAN_PREFIX)]

    scalars: dict[tuple, list[dict]] = defaultdict(list)
    lists: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        target = lists if row["field_key"] in LIST_ITEM_TYPES else scalars
        target[(row["course_id"], row["field_key"])].append(row)

    values, items, conflicts = [], [], []
    for (course_id, field_key), group in scalars.items():
        if len({scalar_key(r["value_text"], r["value_int"]) for r in group}) > 1:
            conflicts.append(f"{field_key} ของหลักสูตร {course_id}: เอกสารให้ค่า verified ต่างกัน")
            continue
        values.append(_pick(group))

    for (course_id, field_key), group in lists.items():
        item_type = LIST_ITEM_TYPES[field_key]
        loaded = []
        for row in group:
            row_items = conn.execute(
                """
                SELECT li.seq, li.text, li.status, li.reviewed_by, e.page_start, e.page_end
                  FROM mko.list_items li JOIN mko.evidence e ON e.id = li.evidence_id
                 WHERE li.run_id = %s AND li.item_type = %s ORDER BY li.seq
                """,
                (row["run_id"], item_type),
            ).fetchall()
            if row_items and all(i["status"] == "verified" for i in row_items):
                loaded.append((row, row_items))
        if not loaded:
            continue
        if len({list_key([i["text"] for i in row_items]) for _, row_items in loaded}) > 1:
            conflicts.append(f"{field_key} ของหลักสูตร {course_id}: รายการ verified ต่างกันระหว่างเอกสาร")
            continue
        chosen = _pick([row for row, _ in loaded])
        for row, row_items in loaded:
            if row is chosen:
                for item in row_items:
                    items.append({**item, "course_id": course_id, "item_type": item_type,
                                  "document_id": row["document_id"], "original_filename": row["original_filename"]})
    return values, items, conflicts


def publish(conn, published_by: str, human_only: bool = False, dry_run: bool = False) -> dict:
    if not published_by.strip():
        raise SystemExit("ต้องระบุชื่อผู้เผยแพร่ (--by)")
    values, items, conflicts = collect(conn, human_only)
    policy = "verified_human_only" if human_only else "verified_any"
    reviewer_kinds = Counter(
        "human" if (r["reviewed_by"] or "").startswith(HUMAN_PREFIX) else "auto" for r in values
    )
    summary = {
        "policy": policy,
        "parser_version": PARSER_VERSION,
        "courses": len({r["course_id"] for r in values} | {i["course_id"] for i in items}),
        "values_by_field": dict(Counter(r["field_key"] for r in values)),
        "list_items_by_type": dict(Counter(i["item_type"] for i in items)),
        "lists_by_type": dict(Counter(i["item_type"] for i in items if i["seq"] == 1)),
        "values_reviewed_by": dict(reviewer_kinds),
        "conflicts": conflicts,
    }
    if dry_run:
        return {"dry_run": True, **summary}
    if not values and not items:
        raise SystemExit("ไม่มีค่า verified ให้เผยแพร่")

    with conn.transaction():
        publication_id = conn.execute(
            """
            INSERT INTO mko.publications (published_by, policy, parser_version, summary)
            VALUES (%s, %s, %s, %s) RETURNING id
            """,
            (published_by.strip(), policy, PARSER_VERSION, Jsonb(summary)),
        ).fetchone()["id"]
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO mko.published_values
                    (publication_id, course_id, field_key, value_text, value_int, document_id, source_filename,
                     page_start, page_end, quote, reviewed_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [(publication_id, r["course_id"], r["field_key"], r["value_text"], r["value_int"], r["document_id"],
                  r["original_filename"], r["page_start"], r["page_end"], r["quote"], r["reviewed_by"]) for r in values],
            )
            cur.executemany(
                """
                INSERT INTO mko.published_list_items
                    (publication_id, course_id, item_type, seq, text, document_id, source_filename,
                     page_start, page_end, reviewed_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [(publication_id, i["course_id"], i["item_type"], i["seq"], i["text"], i["document_id"],
                  i["original_filename"], i["page_start"], i["page_end"], i["reviewed_by"]) for i in items],
            )
        conn.execute(
            """
            UPDATE mko.curricula SET status = 'published', published_at = now(), updated_at = now()
             WHERE course_id = ANY(%s)
            """,
            (list({r["course_id"] for r in values} | {i["course_id"] for i in items}),),
        )
    return {"publication_id": str(publication_id), **summary}


def rollback_latest(conn) -> dict:
    with conn.transaction():
        row = conn.execute("SELECT id, published_at FROM mko.publications ORDER BY published_at DESC LIMIT 1").fetchone()
        if row is None:
            return {"rolled_back": None}
        conn.execute("DELETE FROM mko.publications WHERE id = %s", (row["id"],))
    return {"rolled_back": str(row["id"]), "published_at": str(row["published_at"])}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="เผยแพร่ค่าที่ผ่านการตรวจจาก มคอ.")
    parser.add_argument("--database-url")
    parser.add_argument("--by", help="ชื่อผู้เผยแพร่")
    parser.add_argument("--human-only", action="store_true", help="เผยแพร่เฉพาะค่าที่คนตรวจแล้ว")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--rollback-latest", action="store_true", help="ลบการเผยแพร่ครั้งล่าสุด")
    args = parser.parse_args(argv)
    with psycopg.connect(database_url(args.database_url), autocommit=True, row_factory=dict_row) as conn:
        if args.rollback_latest:
            print(rollback_latest(conn))
        else:
            print(publish(conn, args.by or "", args.human_only, args.dry_run))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
