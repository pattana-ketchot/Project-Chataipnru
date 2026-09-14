"""
ขั้นตรวจค่าที่สกัดได้ — Phase 2 ของ docs/MKO_STRUCTURED_DATA_DESIGN.md

    python -m pipeline.mko.review status
    python -m pipeline.mko.review export --out backups/mko_local/review_queue.csv
    python -m pipeline.mko.review apply --file backups/mko_local/review_queue.csv --reviewer "ชื่อผู้ตรวจ"

ไฟล์คิวเป็น CSV (UTF-8 BOM เปิดใน Excel ได้) หนึ่งแถวต่อหนึ่งค่า มีค่าที่สกัดได้ หน้า และข้อความที่ยกมา
ผู้ตรวจกรอกช่อง decision เป็น verified / rejected (หรือ ผ่าน / ไม่ผ่าน) และช่อง note ถ้ามี แถวที่เว้นว่างไม่ถูกแตะ

ทำไมผลตรวจเก็บแยกตาราง
----------------------
การสกัดรอบใหม่ลบแถวของรอบเก่าทิ้ง ถ้าเก็บผลตรวจไว้ที่แถวโดยตรง ผลตรวจของคนจะหายทุกครั้งที่รันตัวสกัดใหม่ จึงเก็บใน
mko.review_decisions ผูกกับ (เอกสาร, field, ค่า) แล้วนำกลับไปใช้กับรอบล่าสุดทุกครั้ง (run.py เรียก reapply หลังสกัดเสร็จ)

ถ้าค่าที่สกัดได้รอบใหม่ไม่ตรงกับค่าที่คนตรวจไว้ ผลตรวจเดิมไม่ถูกใช้ ค่าใหม่กลับเข้าคิว — ระบบไม่ยืนยันค่าที่คนไม่เคยเห็น
ผู้ตรวจที่เป็นคนบันทึกเป็น reviewed_by = "human:<ชื่อ>" แยกจากกฎอัตโนมัติ ("auto:...") ได้เสมอ
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from collections import Counter
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import psycopg  # noqa: E402
from psycopg.rows import dict_row  # noqa: E402

from pipeline.mko.decide import normalise_text  # noqa: E402
from pipeline.mko.run import database_url  # noqa: E402

LIST_ITEM_TYPES = {"objectives": "objective", "careers": "career", "admission": "admission"}
HUMAN_PREFIX = "human:"
DECISION_WORDS = {
    "verified": "verified", "verify": "verified", "ผ่าน": "verified",
    "rejected": "rejected", "reject": "rejected", "ไม่ผ่าน": "rejected",
}
CSV_COLUMNS = ("review_key", "course_title", "file", "template", "field", "status", "reviewed_by", "reason",
               "pages", "value", "quote", "decision", "note")

LATEST_RUNS = """
    SELECT DISTINCT ON (document_id) id, document_id, template_type
      FROM mko.extraction_runs WHERE status = 'done'
     ORDER BY document_id, started_at DESC
"""


def scalar_key(value_text: str | None, value_int: int | None) -> str:
    return str(value_int) if value_int is not None else normalise_text(value_text)


def list_key(texts: list[str]) -> str:
    joined = "\n".join(normalise_text(text) for text in texts)
    return "items:" + hashlib.sha256(joined.encode("utf-8")).hexdigest()[:20]


def current_values(conn) -> list[dict]:
    """ค่าทุกค่าในรอบสกัดล่าสุดของแต่ละเอกสาร (ยกเว้น not_found) พร้อม value_key ที่ใช้ผูกผลตรวจ"""
    rows = conn.execute(
        f"""
        WITH latest AS ({LATEST_RUNS})
        SELECT fv.id, fv.run_id, fv.document_id, d.file_sha256, d.original_filename, c.title AS course_title,
               l.template_type, fv.field_key, fv.value_text, fv.value_int, fv.status, fv.reason, fv.reviewed_by,
               e.page_start, e.page_end, e.quote
          FROM latest l
          JOIN mko.field_values fv ON fv.run_id = l.id
          JOIN public.course_documents d ON d.id = fv.document_id
          JOIN public.courses c ON c.id = d.course_id
          LEFT JOIN mko.evidence e ON e.id = fv.evidence_id
         WHERE fv.status <> 'not_found'
         ORDER BY c.title, d.original_filename, fv.field_key
        """
    ).fetchall()
    for row in rows:
        if row["field_key"] in LIST_ITEM_TYPES:
            items = conn.execute(
                "SELECT seq, text FROM mko.list_items WHERE run_id = %s AND item_type = %s ORDER BY seq",
                (row["run_id"], LIST_ITEM_TYPES[row["field_key"]]),
            ).fetchall()
            row["items"] = [item["text"] for item in items]
            row["value_key"] = list_key(row["items"])
            row["shown"] = f"{len(items)} ข้อ: " + " | ".join(f"{item['seq']}) {item['text']}" for item in items)
        else:
            row["value_key"] = scalar_key(row["value_text"], row["value_int"])
            row["shown"] = str(row["value_int"]) if row["value_int"] is not None else row["value_text"]
    return rows


def review_key(row: dict) -> str:
    return f"{row['document_id']}|{row['field_key']}|{row['value_key']}"


def export_queue(conn, out: Path, statuses: tuple[str, ...]) -> int:
    rows = [r for r in current_values(conn) if r["status"] in statuses]
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            pages = "" if row["page_start"] is None else (
                str(row["page_start"]) if row["page_start"] == row["page_end"] else f"{row['page_start']}-{row['page_end']}")
            writer.writerow({
                "review_key": review_key(row),
                "course_title": row["course_title"],
                "file": row["original_filename"],
                "template": row["template_type"],
                "field": row["field_key"],
                "status": row["status"],
                "reviewed_by": row["reviewed_by"] or "",
                "reason": row["reason"] or "",
                "pages": pages,
                "value": row["shown"],
                "quote": " ".join((row["quote"] or "").split())[:500],
                "decision": "",
                "note": "",
            })
    return len(rows)


def reapply(conn) -> dict:
    """นำผลตรวจที่ยังมีผลไปใช้กับรอบสกัดล่าสุด ค่าที่เปลี่ยนไปจากที่ตรวจไว้ไม่ถูกแตะ"""
    decisions = conn.execute(
        "SELECT * FROM mko.review_decisions WHERE superseded_at IS NULL ORDER BY decided_at"
    ).fetchall()
    current: dict[tuple, list[dict]] = {}
    for row in current_values(conn):
        current.setdefault((row["document_id"], row["field_key"], row["value_key"]), []).append(row)

    applied, stale = 0, []
    for decision in decisions:
        rows = current.get((decision["document_id"], decision["field_key"], decision["value_key"]))
        if not rows:
            stale.append(f"{decision['field_key']} ({decision['shown_value']})")
            continue
        reviewer = HUMAN_PREFIX + decision["reviewer"]
        reason = f"ตรวจโดย {decision['reviewer']}" + (f": {decision['note']}" if decision["note"] else "")
        for row in rows:
            conn.execute(
                "UPDATE mko.field_values SET status = %s, reviewed_by = %s, reviewed_at = %s, reason = %s WHERE id = %s",
                (decision["decision"], reviewer, decision["decided_at"], reason, row["id"]),
            )
            if row["field_key"] in LIST_ITEM_TYPES:
                conn.execute(
                    """
                    UPDATE mko.list_items SET status = %s, reviewed_by = %s, reviewed_at = %s, reason = %s
                     WHERE run_id = %s AND item_type = %s
                    """,
                    (decision["decision"], reviewer, decision["decided_at"], reason, row["run_id"],
                     LIST_ITEM_TYPES[row["field_key"]]),
                )
        applied += 1
    return {"decisions": len(decisions), "applied": applied, "stale": stale}


def apply_file(conn, path: Path, reviewer: str) -> dict:
    """บันทึกผลตรวจจากไฟล์คิว ตรวจทุกแถวก่อนเขียน ถ้ามีแถวผิดรูปแบบจะไม่บันทึกอะไรเลย"""
    if not reviewer.strip():
        raise SystemExit("ต้องระบุชื่อผู้ตรวจ (--reviewer)")
    current = {review_key(row): row for row in current_values(conn)}
    pending, invalid, stale, blank = [], [], [], 0
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for line_no, line in enumerate(csv.DictReader(handle), start=2):
            raw = (line.get("decision") or "").strip().lower()
            if not raw:
                blank += 1
                continue
            decision = DECISION_WORDS.get(raw)
            if decision is None:
                invalid.append(f"บรรทัด {line_no}: decision {raw!r} ต้องเป็น verified/rejected/ผ่าน/ไม่ผ่าน")
                continue
            row = current.get((line.get("review_key") or "").strip())
            if row is None:
                stale.append(f"บรรทัด {line_no}: {line.get('file')} {line.get('field')} — ค่าเปลี่ยนไปจากตอนส่งออกคิว")
                continue
            pending.append((row, decision, (line.get("note") or "").strip() or None))
    if invalid:
        raise SystemExit("ไม่บันทึกผลตรวจ เพราะมีแถวผิดรูปแบบ:\n" + "\n".join(invalid))

    with conn.transaction():
        for row, decision, note in pending:
            conn.execute(
                """
                UPDATE mko.review_decisions SET superseded_at = now()
                 WHERE document_id = %s AND field_key = %s AND superseded_at IS NULL
                """,
                (row["document_id"], row["field_key"]),
            )
            conn.execute(
                """
                INSERT INTO mko.review_decisions
                    (document_id, document_sha256, field_key, value_key, shown_value, decision, reviewer, note)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (row["document_id"], row["file_sha256"], row["field_key"], row["value_key"], row["shown"][:2000],
                 decision, reviewer.strip(), note),
            )
        result = reapply(conn)
    return {"recorded": len(pending), "blank": blank, "stale_rows": stale, **result}


def status_summary(conn) -> dict:
    rows = current_values(conn)
    by_status = Counter(row["status"] for row in rows)
    by_reviewer = Counter(
        ("human" if (row["reviewed_by"] or "").startswith(HUMAN_PREFIX) else "auto")
        for row in rows if row["status"] in ("verified", "rejected")
    )
    active = conn.execute("SELECT count(*) AS n FROM mko.review_decisions WHERE superseded_at IS NULL").fetchone()["n"]
    return {"values": len(rows), "by_status": dict(by_status), "verified_or_rejected_by": dict(by_reviewer),
            "active_human_decisions": active}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ขั้นตรวจค่าที่สกัดได้จาก มคอ.")
    parser.add_argument("--database-url")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    export = sub.add_parser("export")
    export.add_argument("--out", required=True)
    export.add_argument("--statuses", default="candidate,needs_review",
                        help="สถานะที่ส่งออก คั่นด้วยจุลภาค (ใส่ verified เพื่อให้คนตรวจค่าที่กฎยืนยันไว้ด้วย)")
    apply = sub.add_parser("apply")
    apply.add_argument("--file", required=True)
    apply.add_argument("--reviewer", required=True)
    sub.add_parser("reapply")
    args = parser.parse_args(argv)

    with psycopg.connect(database_url(args.database_url), autocommit=True, row_factory=dict_row) as conn:
        if args.command == "status":
            print(status_summary(conn))
        elif args.command == "export":
            statuses = tuple(s.strip() for s in args.statuses.split(",") if s.strip())
            count = export_queue(conn, Path(args.out), statuses)
            print(f"ส่งออกคิวตรวจ {count} แถวไปที่ {args.out}")
        elif args.command == "apply":
            print(apply_file(conn, Path(args.file), args.reviewer))
        elif args.command == "reapply":
            with conn.transaction():
                print(reapply(conn))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
