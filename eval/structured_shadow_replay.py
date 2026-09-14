"""
เล่นคำตอบที่ระบบเดิมเคยตอบจริงซ้ำผ่านโหมด shadow บนฐานข้อมูล local แล้วสรุปผล — ตัวอย่างก่อนเปิด shadow บน production

    python -m eval.structured_shadow_replay --input eval/result_final_v16.json [--input ...]

ไม่เรียก LLM และไม่แตะ production — ปฏิเสธ DATABASE_URL ที่ไม่ใช่เครื่องนี้
คำตอบของระบบเดิมมาจากไฟล์ผลประเมินที่บันทึกไว้ (question, reply และ got/status ถ้ามี)
บันทึกแถวลง mko.shadow_answers ของฐานข้อมูล local ด้วย mode='replay' (ใส่ --no-write เพื่อไม่บันทึก)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres@127.0.0.1:55432/course_advisor")
os.environ.setdefault("JWT_SECRET", "local-test-only")
if urlparse(os.environ["DATABASE_URL"]).hostname not in ("127.0.0.1", "localhost"):
    raise SystemExit("structured_shadow_replay ใช้กับฐานข้อมูลในเครื่องเท่านั้น")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.db.session import SessionLocal  # noqa: E402
from app.services.structured_shadow import run_shadow  # noqa: E402

KNOWN_STATUSES = {"answered", "not_found", "out_of_scope"}


def load_rows(paths: list[str]) -> list[dict]:
    rows = []
    for path in paths:
        for row in json.loads(Path(path).read_text(encoding="utf-8")):
            if not row.get("question") or row.get("reply") is None:
                continue
            status = row.get("status") or row.get("got")
            rows.append({"source": Path(path).name, "question": row["question"], "reply": row["reply"],
                         "status": status if status in KNOWN_STATUSES else None})
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", action="append", required=True)
    parser.add_argument("--out", default="eval/structured_shadow_replay.json")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args(argv)

    records = []
    with SessionLocal() as db:
        for row in load_rows(args.input):
            record = run_shadow(db, question=row["question"], served_status=row["status"], served_reply=row["reply"],
                                mode="replay", commit=False)
            records.append({"source": row["source"], **record})
        if args.no_write:
            db.rollback()
        else:
            db.commit()

    summary = {
        "questions": len(records),
        "route": dict(Counter(r["route"] for r in records)),
        "route_reason": dict(Counter(r["route_reason"] for r in records)),
        "structured_status": dict(Counter(r["structured_status"] for r in records if r["route"] == "structured")),
        "comparison": dict(Counter(r["comparison"] for r in records if r["structured_status"] == "answered")),
    }
    Path(args.out).write_text(json.dumps({"summary": summary, "records": records}, ensure_ascii=False, indent=2),
                              encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
