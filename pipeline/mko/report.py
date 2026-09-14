"""
รายงานผลการสกัดข้อมูล มคอ. Phase 1 จากฐานข้อมูล local

    python -m pipeline.mko.report
    python -m pipeline.mko.report --out docs/MKO_PHASE1_EXTRACTION_REPORT.md
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import psycopg  # noqa: E402
from psycopg.rows import dict_row  # noqa: E402

from pipeline.mko.decide import AUTO_DOCUMENTS, AUTO_TWO_LOCATIONS  # noqa: E402
from pipeline.mko.extract import LIST_FIELDS, PARSER_VERSION, SCALAR_FIELDS  # noqa: E402
from pipeline.mko.gold import LATEST_VALUES_SQL, compare, load_gold  # noqa: E402
from pipeline.mko.run import database_url  # noqa: E402

STATUS_ORDER = ("verified", "candidate", "needs_review", "not_found", "not_applicable", "rejected")
FIELD_LABELS = {
    "program_name_th": "ชื่อหลักสูตร (ไทย)",
    "program_name_en": "ชื่อหลักสูตร (อังกฤษ)",
    "degree_name_th": "ชื่อปริญญา (ไทย)",
    "degree_abbr_th": "อักษรย่อปริญญา (ไทย)",
    "degree_name_en": "ชื่อปริญญา (อังกฤษ)",
    "degree_abbr_en": "อักษรย่อปริญญา (อังกฤษ)",
    "degree_level": "ระดับการศึกษา",
    "edition_year": "ปีหลักสูตร (พ.ศ.)",
    "revision_type": "ประเภทหลักสูตร (ใหม่/ปรับปรุง)",
    "total_credits": "จำนวนหน่วยกิตรวม",
    "objectives": "วัตถุประสงค์ (จำนวนข้อ)",
    "careers": "อาชีพหลังสำเร็จการศึกษา (จำนวนข้อ)",
    "admission": "คุณสมบัติผู้เข้าศึกษา (จำนวนข้อ)",
}
ALL_FIELDS = (*SCALAR_FIELDS, *(key for key, _ in LIST_FIELDS))


def _cell(text, limit: int = 90) -> str:
    if text is None:
        return "—"
    text = " ".join(str(text).split()).replace("|", "\\|")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _best(statuses: list[str]) -> str:
    return min(statuses, key=STATUS_ORDER.index) if statuses else "not_found"


def build(conn, gold_path: Path | None) -> str:
    rows = conn.execute(LATEST_VALUES_SQL).fetchall()
    pages = conn.execute(
        """
        SELECT count(*) AS pages,
               count(*) FILTER (WHERE text_source IN ('ocr', 'text_layer+ocr')) AS ocr_pages,
               count(*) FILTER (WHERE is_toc) AS toc_pages,
               count(*) FILTER (WHERE encoding_suspect) AS suspect_pages,
               count(DISTINCT document_id) AS documents
          FROM mko.document_pages
        """
    ).fetchone()
    templates = conn.execute(
        """
        SELECT template_type, count(*) AS n FROM (
            SELECT DISTINCT ON (document_id) document_id, template_type
              FROM mko.extraction_runs ORDER BY document_id, started_at DESC) t
         GROUP BY template_type ORDER BY template_type
        """
    ).fetchall()
    failed = [r for r in rows if r["run_status"] != "done"]
    items = conn.execute("SELECT item_type, status, count(*) AS n FROM mko.list_items GROUP BY 1, 2 ORDER BY 1, 2").fetchall()

    by_course: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_course[row["course_title"]].append(row)

    out: list[str] = []
    out.append("# รายงานผลการสกัดข้อมูล มคอ. — Phase 1")
    out.append("")
    out.append(f"สร้างเมื่อ {datetime.now():%Y-%m-%d %H:%M} จากฐานข้อมูล local · ตัวสกัดรุ่น `{PARSER_VERSION}`")
    out.append("")
    out.append("> ทำงานเฉพาะบนเครื่อง local ไม่ได้แตะฐานข้อมูล production ไม่มีการเรียกโมเดลภาษาในการสกัดค่า "
               "ค่าที่สถานะ `verified` ทั้งหมดเป็นการยืนยันอัตโนมัติด้วยกฎ ยังไม่มีคนตรวจ "
               f"(`{AUTO_TWO_LOCATIONS}` = ค่าเดียวกันจากอย่างน้อยสองหน้าของเล่มเดียวกัน, "
               f"`{AUTO_DOCUMENTS}` = ค่าตรงกันระหว่างฉบับเต็มกับใบสรุปของหลักสูตรฉบับปีเดียวกัน)")
    out.append("")

    out.append("## ภาพรวม")
    out.append("")
    out.append("| รายการ | จำนวน |")
    out.append("|---|---|")
    out.append(f"| หลักสูตร (ฉบับปี) | {len(by_course)} |")
    out.append(f"| เอกสาร | {pages['documents']} |")
    out.append(f"| หน้าใน `mko.document_pages` | {pages['pages']:,} |")
    out.append(f"| หน้าที่มีข้อความจาก OCR เดิม | {pages['ocr_pages']} |")
    out.append(f"| หน้าสารบัญ (ไม่ใช้สกัดค่า) | {pages['toc_pages']} |")
    out.append(f"| หน้าที่ข้อความมีร่องรอยฟอนต์เพี้ยน | {pages['suspect_pages']} |")
    out.append(f"| การสกัดที่ล้มเหลว | {len({r['file'] for r in failed})} |")
    out.append("")
    out.append("รูปแบบเอกสารที่ตรวจพบ: " + ", ".join(f"`{t['template_type']}` {t['n']}" for t in templates))
    out.append("")

    # ---- สรุปราย field ระดับหลักสูตร ----
    out.append("## สรุปราย field (ระดับหลักสูตร)")
    out.append("")
    out.append("นับสถานะที่ดีที่สุดของแต่ละหลักสูตรจากทุกเอกสารของหลักสูตรนั้น "
               "(verified > candidate > needs_review > not_found) · \"สกัดได้\" = verified หรือ candidate")
    out.append("")
    out.append("| field | สกัดได้ | verified | candidate | needs_review | not_found |")
    out.append("|---|---|---|---|---|---|")
    for field_key in ALL_FIELDS:
        best = Counter()
        for course_rows in by_course.values():
            best[_best([r["status"] for r in course_rows if r["field_key"] == field_key])] += 1
        extracted = best["verified"] + best["candidate"]
        out.append(f"| {FIELD_LABELS[field_key]} | **{extracted}/{len(by_course)}** | {best['verified']} | "
                   f"{best['candidate']} | {best['needs_review']} | {best['not_found']} |")
    out.append("")

    # ---- สรุปราย field ระดับเอกสาร ----
    out.append("## สรุปราย field (ระดับเอกสาร)")
    out.append("")
    out.append("| field | verified | candidate | needs_review | not_found |")
    out.append("|---|---|---|---|---|")
    for field_key in ALL_FIELDS:
        per_doc = defaultdict(list)
        for r in rows:
            if r["field_key"] == field_key:
                per_doc[r["file"]].append(r["status"])
        counts = Counter(_best(statuses) for statuses in per_doc.values())
        out.append(f"| {FIELD_LABELS[field_key]} | {counts['verified']} | {counts['candidate']} | "
                   f"{counts['needs_review']} | {counts['not_found']} |")
    out.append("")
    if items:
        out.append("รายการข้อความที่เก็บใน `mko.list_items`: " +
                   ", ".join(f"{i['item_type']} {i['status']} {i['n']}" for i in items))
        out.append("")

    # ---- เทียบชุดตรวจ ----
    if gold_path and gold_path.is_file():
        verdicts = compare(rows, load_gold(gold_path))
        out.append("## ผลเทียบกับชุดค่าที่ตรวจด้วยมือ (`eval/mko_gold.json`)")
        out.append("")
        out.append("| field | ตรวจ | correct | needs_review | not_found | wrong | ไม่ควรมีค่าแต่มี | verified ที่ผิด |")
        out.append("|---|---|---|---|---|---|---|---|")
        by_field = defaultdict(list)
        for v in verdicts:
            by_field[v.field_key].append(v)
        for field_key in ALL_FIELDS:
            vs = by_field.get(field_key)
            if not vs:
                continue
            c = Counter(v.verdict for v in vs)
            out.append(f"| {FIELD_LABELS[field_key]} | {len(vs)} | {c['correct']} | {c['needs_review']} | "
                       f"{c['not_found']} | {c['wrong']} | {c['unexpected_value']} | {sum(v.wrong_verified for v in vs)} |")
        out.append("")
        misses = [v for v in verdicts if v.verdict not in ("correct",)]
        if misses:
            out.append("<details><summary>รายการที่ไม่ใช่ correct</summary>")
            out.append("")
            out.append("| ไฟล์ | field | ค่าที่ตรวจไว้ | ผลของระบบ | ผล |")
            out.append("|---|---|---|---|---|")
            for v in misses:
                got = "; ".join(f"{_cell(value, 40)} ({status})" for value, status in v.got) or "—"
                out.append(f"| {v.file} | {v.field_key} | {_cell(v.expected, 50)} | {got} | {v.verdict} |")
            out.append("")
            out.append("</details>")
            out.append("")

    # ---- needs_review ----
    review = [r for r in rows if r["status"] == "needs_review"]
    out.append(f"## ค่าที่ต้องให้คนตรวจ (needs_review) — {len(review)} รายการ")
    out.append("")
    if review:
        out.append("| ไฟล์ | field | ค่า | หน้า | เหตุผล | ข้อความที่ยกมา |")
        out.append("|---|---|---|---|---|---|")
        for r in review:
            value = r["value_int"] if r["value_int"] is not None else r["value_text"]
            page = f"{r['page_start']}" if r["page_start"] == r["page_end"] else f"{r['page_start']}–{r['page_end']}"
            out.append(f"| {r['file']} | {r['field_key']} | {_cell(value, 50)} | {page} | {_cell(r['reason'], 70)} | "
                       f"{_cell(r['quote'], 80)} |")
        out.append("")

    # ---- รายหลักสูตร ----
    out.append("## รายละเอียดรายหลักสูตร")
    out.append("")
    for title in sorted(by_course):
        course_rows = by_course[title]
        files = sorted({r["file"] for r in course_rows})
        templates_of = {r["file"]: r["template_type"] for r in course_rows}
        out.append(f"### {title}")
        out.append("")
        out.append("เอกสาร: " + ", ".join(f"`{f}` ({templates_of[f]})" for f in files))
        out.append("")
        out.append("| field | ไฟล์ | ค่า | สถานะ | หน้า | หมายเหตุ |")
        out.append("|---|---|---|---|---|---|")
        for field_key in ALL_FIELDS:
            for r in [r for r in course_rows if r["field_key"] == field_key]:
                value = r["value_int"] if r["value_int"] is not None else r["value_text"]
                if field_key in dict(LIST_FIELDS) and r["status"] != "not_found":
                    value = f"{value} ข้อ"
                page = "—" if r["page_start"] is None else (
                    f"{r['page_start']}" if r["page_start"] == r["page_end"] else f"{r['page_start']}–{r['page_end']}")
                note = r["reason"] if r["status"] != "verified" else f"{r['reviewed_by']}: {r['reason']}"
                out.append(f"| {FIELD_LABELS[field_key]} | {r['file']} | {_cell(value, 70)} | {r['status']} | {page} | "
                           f"{_cell(note, 80)} |")
        out.append("")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="รายงานผลการสกัดข้อมูล มคอ. Phase 1")
    parser.add_argument("--database-url")
    parser.add_argument("--gold", default=str(_REPO_ROOT / "eval" / "mko_gold.json"))
    parser.add_argument("--out", default=str(_REPO_ROOT / "docs" / "MKO_PHASE1_EXTRACTION_REPORT.md"))
    args = parser.parse_args(argv)
    with psycopg.connect(database_url(args.database_url), row_factory=dict_row) as conn:
        text = build(conn, Path(args.gold))
    Path(args.out).write_text(text, encoding="utf-8")
    print(f"เขียนรายงาน {args.out} ({len(text):,} ตัวอักษร)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
