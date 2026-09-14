"""
เทียบผลการสกัดล่าสุดในฐานข้อมูล local กับชุดค่าที่ตรวจด้วยมือ (eval/mko_gold.json)

ผลต่อ (ไฟล์, field)
    correct           ค่าที่เป็น candidate/verified ตรงกับที่ตรวจไว้ หรือ field ที่ควรไม่พบก็ไม่พบจริง
    needs_review      ระบบไม่ยืนยันค่า (ยอมรับได้ตามเกณฑ์ Phase 1 เพราะไม่ได้ให้ค่าผิดออกไป)
    not_found         ควรมีค่าแต่ระบบหาไม่เจอ (ไม่ผิด แต่ยังไม่ครบ)
    wrong             ค่าที่เป็น candidate/verified ไม่ตรงกับที่ตรวจไว้
    unexpected_value  ควรไม่พบ แต่ระบบให้ค่าออกมา (เท่ากับการเดา)
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from pipeline.mko.normalize import fold

GOLD_PATH = Path(__file__).resolve().parents[2] / "eval" / "mko_gold.json"

LATEST_VALUES_SQL = """
WITH latest AS (
    SELECT DISTINCT ON (document_id) id, document_id, template_type, status
      FROM mko.extraction_runs
     ORDER BY document_id, started_at DESC
)
SELECT d.original_filename AS file, c.title AS course_title, l.template_type, l.status AS run_status,
       fv.field_key, fv.value_text, fv.value_int, fv.status, fv.reason, fv.reviewed_by,
       e.page_start, e.page_end, e.quote
  FROM latest l
  JOIN public.course_documents d ON d.id = l.document_id
  JOIN public.courses c ON c.id = d.course_id
  LEFT JOIN mko.field_values fv ON fv.run_id = l.id
  LEFT JOIN mko.evidence e ON e.id = fv.evidence_id
 ORDER BY c.title, d.original_filename, fv.field_key, fv.status
"""

ACCEPTED = ("candidate", "verified")


def load_gold(path: Path = GOLD_PATH) -> dict[str, dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))["documents"]


def normalise(value) -> object:
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        return value
    return re.sub(r"\s+", "", fold(str(value))).lower().rstrip(".")


@dataclass(frozen=True)
class Verdict:
    file: str
    field_key: str
    expected: object
    got: tuple[tuple[object, str], ...]
    verdict: str

    @property
    def wrong_verified(self) -> bool:
        if self.verdict not in ("wrong", "unexpected_value"):
            return False
        if self.expected == "not_found":
            return any(status == "verified" for _, status in self.got)
        return any(status == "verified" and normalise(value) != normalise(self.expected) for value, status in self.got)


def judge(expected, got: list[tuple[object, str]]) -> str:
    accepted = [(value, status) for value, status in got if status in ACCEPTED]
    review = [item for item in got if item[1] == "needs_review"]
    if expected == "not_found":
        if accepted:
            return "unexpected_value"
        return "needs_review" if review else "correct"
    if accepted:
        return "correct" if all(normalise(value) == normalise(expected) for value, _ in accepted) else "wrong"
    return "needs_review" if review else "not_found"


def compare(rows: list[dict], gold: dict[str, dict]) -> list[Verdict]:
    by_key: dict[tuple[str, str], list[tuple[object, str]]] = defaultdict(list)
    for row in rows:
        if row.get("field_key") is None:
            continue
        value = row["value_int"] if row["value_int"] is not None else row["value_text"]
        by_key[(row["file"], row["field_key"])].append((value, row["status"]))
    verdicts = []
    for file, expectations in sorted(gold.items()):
        for field_key, expected in sorted(expectations.items()):
            if field_key.startswith("_") or field_key.endswith("_last_item"):
                continue
            got = by_key.get((file, field_key), [])
            verdicts.append(Verdict(file, field_key, expected, tuple(got), judge(expected, got)))
    return verdicts
