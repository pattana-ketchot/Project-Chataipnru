"""
สกัดข้อมูลพื้นฐานจากเอกสาร มคอ. แล้วเก็บลงฐานข้อมูล local (Phase 1)

    bash scripts/mko_local_db.sh          # สร้างฐานข้อมูล local ครั้งแรก
    python -m pipeline.mko.run            # ทุกเอกสาร
    python -m pipeline.mko.run --only cs61.pdf --only cs66_brief.pdf

ทำงานกับฐานข้อมูลบนเครื่องนี้เท่านั้น: ปฏิเสธ URL ที่ host ไม่ใช่ localhost เพื่อกันการเขียน production โดยไม่ตั้งใจ
ไม่อ่าน DATABASE_URL / INGEST_DATABASE_URL ของระบบเดิม ใช้ MKO_DATABASE_URL หรือค่าตั้งต้นของคอนเทนเนอร์ local

ขั้นตอนต่อเอกสาร (หนึ่ง transaction)
    จับคู่ไฟล์ในเครื่องกับ course_documents ด้วย SHA-256 → สร้างข้อความรายหน้า (pipeline.pages ใช้ extract/OCR/clean เดิม)
    → บันทึก mko.document_pages → ตรวจรูปแบบและแบ่งหมวด → สกัดค่า → บันทึกหลักฐาน ค่า และรายการ
การสกัดรอบใหม่ของเอกสารเดิมลบรอบเก่าของเอกสารนั้นทิ้งก่อน (ตาราง mko เท่านั้น) ไม่แตะ course_chunks หรือตาราง public ใดๆ
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import psycopg  # noqa: E402
from psycopg.rows import dict_row  # noqa: E402
from psycopg.types.json import Jsonb  # noqa: E402

from pipeline.mko.decide import Evidence, consolidate_course  # noqa: E402
from pipeline.mko.doc import DocText  # noqa: E402
from pipeline.mko.extract import PARSER_VERSION, DocumentExtraction, extract_document  # noqa: E402
from pipeline.mko.templates import FULL_TEMPLATES, Section  # noqa: E402
from pipeline.pages import DocumentPages, build_pages  # noqa: E402

DEFAULT_DATABASE_URL = "postgresql://postgres@127.0.0.1:55432/course_advisor"
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
DEFAULT_OCR = _REPO_ROOT / "backups" / "mko_local" / "ocr_pages.json"

logger = logging.getLogger("pipeline.mko.run")


def database_url(explicit: str | None = None) -> str:
    url = explicit or os.environ.get("MKO_DATABASE_URL") or DEFAULT_DATABASE_URL
    host = urlparse(url).hostname
    if host not in LOCAL_HOSTS:
        raise SystemExit(f"ปฏิเสธการเชื่อมต่อ host {host!r}: Phase 1 เขียนได้เฉพาะฐานข้อมูลบนเครื่องนี้")
    return url


def local_files(root: Path) -> dict[str, Path]:
    """ไฟล์เอกสารในเครื่อง จับคู่ด้วย SHA-256 ของไฟล์ (ค่าเดียวกับ course_documents.file_sha256)"""
    found: dict[str, Path] = {}
    for path in sorted([*root.rglob("*.pdf"), *root.rglob("*.txt")]):
        found[hashlib.sha256(path.read_bytes()).hexdigest()] = path
    return found


def _page_range(doc: DocText, start: int, end: int) -> tuple[int, int]:
    pages = doc.pages_of(start, max(start + 1, end))
    return pages[0].page_number, pages[-1].page_number


def _section_for(sections: list[tuple[Section, object]], offset: int):
    containing = [(s, sid) for s, sid in sections if s.start <= offset < s.end]
    if not containing:
        return None
    return min(containing, key=lambda item: item[0].end - item[0].start)[1]


def _insert_evidence(cur, run_id, document_id, doc: DocText, sections, evidence: Evidence):
    start, end = doc.trimmed(evidence.start, evidence.end)
    if end <= start:
        start, end = evidence.start, evidence.end
    page_start, page_end = _page_range(doc, start, end)
    cur.execute(
        """
        INSERT INTO mko.evidence (run_id, document_id, page_start, page_end, section_id, quote, method)
        VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
        """,
        (run_id, document_id, page_start, page_end, _section_for(sections, start), doc.slice(start, end), evidence.method),
    )
    return cur.fetchone()["id"]


def upsert_curriculum(conn, course_id, template: str, primary_document_id):
    with conn.transaction(), conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO mko.curricula (course_id, template_type, primary_document_id)
            VALUES (%s, %s, %s)
            ON CONFLICT (course_id) DO UPDATE
               SET template_type = EXCLUDED.template_type,
                   primary_document_id = EXCLUDED.primary_document_id,
                   updated_at = now()
            RETURNING id
            """,
            (course_id, template, primary_document_id),
        )
        return cur.fetchone()["id"]


def store(conn, row: dict, pages: DocumentPages, doc: DocText, extraction: DocumentExtraction, curriculum_id) -> Counter:
    document_id = row["id"]
    counts: Counter = Counter()
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM mko.extraction_runs WHERE document_id = %s", (document_id,))
        cur.executemany(
            """
            INSERT INTO mko.document_pages
                (document_id, page_number, text_raw, text_clean, text_source, is_toc, encoding_suspect, text_sha256)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (document_id, page_number) DO UPDATE
               SET text_raw = EXCLUDED.text_raw, text_clean = EXCLUDED.text_clean,
                   text_source = EXCLUDED.text_source, is_toc = EXCLUDED.is_toc,
                   encoding_suspect = EXCLUDED.encoding_suspect, text_sha256 = EXCLUDED.text_sha256
            """,
            [
                (document_id, record.page_number, record.text_raw, record.text_clean, record.text_source,
                 page.is_toc, page.encoding_suspect, hashlib.sha256(record.text_clean.encode("utf-8")).hexdigest())
                for record, page in zip(pages.pages, doc.pages)
            ],
        )
        cur.execute("DELETE FROM mko.document_pages WHERE document_id = %s AND page_number > %s",
                    (document_id, pages.page_count))

        cur.execute(
            "INSERT INTO mko.extraction_runs (document_id, parser_version, template_type) VALUES (%s, %s, %s) RETURNING id",
            (document_id, PARSER_VERSION, extraction.template),
        )
        run_id = cur.fetchone()["id"]

        sections: list[tuple[Section, object]] = []
        for section in extraction.sections:
            page_start, page_end = _page_range(doc, section.start, section.end)
            cur.execute(
                """
                INSERT INTO mko.document_sections (run_id, document_id, section_key, heading_text, page_start, page_end, is_appendix)
                VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
                """,
                (run_id, document_id, section.key, section.heading or None, page_start, page_end, section.is_appendix),
            )
            sections.append((section, cur.fetchone()["id"]))

        insert_value = """
            INSERT INTO mko.field_values
                (curriculum_id, run_id, document_id, field_key, value_text, value_int, status, reason,
                 evidence_id, reviewed_by, reviewed_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CASE WHEN %s::text IS NULL THEN NULL ELSE now() END)
            RETURNING id
        """
        for decision in extraction.scalars:
            evidence_ids = [_insert_evidence(cur, run_id, document_id, doc, sections, ev) for ev in decision.evidence]
            cur.execute(insert_value, (
                curriculum_id, run_id, document_id, decision.field_key, decision.value_text, decision.value_int,
                decision.status, decision.reason, evidence_ids[0] if evidence_ids else None,
                decision.reviewed_by, decision.reviewed_by,
            ))
            value_id = cur.fetchone()["id"]
            for extra in evidence_ids[1:]:
                cur.execute("INSERT INTO mko.field_value_evidence (field_value_id, evidence_id) VALUES (%s, %s)",
                            (value_id, extra))
            counts[(decision.field_key, decision.status)] += 1

        for decision in extraction.lists:
            if decision.status == "not_found":
                cur.execute(insert_value, (curriculum_id, run_id, document_id, decision.field_key, None, None,
                                           "not_found", decision.reason, None, None, None))
                counts[(decision.field_key, "not_found")] += 1
                continue
            block_id = _insert_evidence(cur, run_id, document_id, doc, sections, decision.block)
            cur.execute(insert_value, (curriculum_id, run_id, document_id, decision.field_key, None, len(decision.items),
                                       decision.status, decision.reason, block_id,
                                       decision.reviewed_by, decision.reviewed_by))
            for item in decision.items:
                item_evidence = _insert_evidence(cur, run_id, document_id, doc, sections, item.evidence)
                cur.execute(
                    """
                    INSERT INTO mko.list_items
                        (curriculum_id, run_id, document_id, item_type, seq, text, status, reason, evidence_id,
                         reviewed_by, reviewed_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CASE WHEN %s::text IS NULL THEN NULL ELSE now() END)
                    """,
                    (curriculum_id, run_id, document_id, decision.item_type, item.seq, item.text, decision.status,
                     decision.reason, item_evidence, decision.reviewed_by, decision.reviewed_by),
                )
            counts[(decision.field_key, decision.status)] += 1

        summary = {
            "parser_version": PARSER_VERSION,
            "template": extraction.template,
            "pages": pages.page_count,
            "ocr_pages": sum(1 for p in doc.pages if p.source in ("ocr", "text_layer+ocr")),
            "encoding_suspect_pages": sum(1 for p in doc.pages if p.encoding_suspect),
            "sections": [s.key for s in extraction.sections],
            "statuses": {f"{field}:{status}": n for (field, status), n in sorted(counts.items())},
        }
        cur.execute("UPDATE mko.extraction_runs SET status = 'done', finished_at = now(), summary = %s WHERE id = %s",
                    (Jsonb(summary), run_id))
    return counts


def _record_failure(conn, document_id, error: str) -> None:
    with conn.transaction(), conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO mko.extraction_runs (document_id, parser_version, template_type, status, error, finished_at)
            VALUES (%s, %s, 'unknown', 'failed', %s, now())
            """,
            (document_id, PARSER_VERSION, error[:2000]),
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="สกัดข้อมูลพื้นฐานจาก มคอ. ลงฐานข้อมูล local (Phase 1)")
    parser.add_argument("--samples", default=str(_REPO_ROOT / "samples"), help="โฟลเดอร์เอกสารในเครื่อง")
    parser.add_argument("--ocr", default=str(DEFAULT_OCR), help="ไฟล์ผล OCR เดิม (ocr_pages.json)")
    parser.add_argument("--database-url", help="ค่าตั้งต้น MKO_DATABASE_URL หรือคอนเทนเนอร์ local พอร์ต 55432")
    parser.add_argument("--only", action="append", help="ชื่อไฟล์ที่ต้องการ (ใส่ซ้ำได้)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    url = database_url(args.database_url)
    ocr_path = Path(args.ocr) if args.ocr and Path(args.ocr).is_file() else None
    if ocr_path is None:
        logger.warning("ไม่พบไฟล์ OCR %s — หน้าที่เป็นภาพสแกนจะไม่มีข้อความ", args.ocr)
    files = local_files(Path(args.samples))

    problems: list[str] = []
    totals: Counter = Counter()
    with psycopg.connect(url, autocommit=True, row_factory=dict_row) as conn:
        rows = conn.execute(
            """
            SELECT d.id, d.course_id, d.original_filename, d.file_sha256, d.page_count, c.title
              FROM public.course_documents d
              JOIN public.courses c ON c.id = d.course_id
             ORDER BY c.title, d.original_filename
            """
        ).fetchall()
        by_course: dict[object, list[dict]] = defaultdict(list)
        for row in rows:
            if args.only and row["original_filename"] not in args.only:
                continue
            by_course[row["course_id"]].append(row)

        for course_id, documents in by_course.items():
            prepared = []
            for row in documents:
                path = files.get(row["file_sha256"])
                if path is None:
                    problems.append(f"{row['original_filename']}: ไม่พบไฟล์ในเครื่องที่ SHA-256 ตรงกับฐานข้อมูล")
                    continue
                pages = build_pages(path, ocr_path)
                if pages.page_count != row["page_count"]:
                    problems.append(f"{row['original_filename']}: จำนวนหน้า {pages.page_count} ไม่ตรงกับฐานข้อมูล {row['page_count']}")
                doc = DocText.from_records(row["original_filename"], pages.pages)
                prepared.append((row, pages, doc, extract_document(doc, row["title"])))
            if not prepared:
                continue

            consolidate_course([item[3] for item in prepared])
            primary = max(prepared, key=lambda item: (item[3].template in FULL_TEMPLATES, item[1].page_count))
            curriculum_id = upsert_curriculum(conn, course_id, primary[3].template, primary[0]["id"])

            for row, pages, doc, extraction in prepared:
                try:
                    counts = store(conn, row, pages, doc, extraction, curriculum_id)
                except Exception as exc:  # noqa: BLE001 — เอกสารเดียวพังไม่ควรหยุดทั้งชุด
                    logger.exception("บันทึก %s ไม่สำเร็จ", row["original_filename"])
                    problems.append(f"{row['original_filename']}: {type(exc).__name__}: {exc}")
                    _record_failure(conn, row["id"], f"{type(exc).__name__}: {exc}")
                    continue
                for (_, status), n in counts.items():
                    totals[status] += n
                logger.info("%-20s %-8s %s", row["original_filename"], extraction.template,
                            json.dumps({f"{k}:{s}": n for (k, s), n in sorted(counts.items())}, ensure_ascii=False))

    logger.info("สรุปสถานะทั้งหมด: %s", dict(totals))
    for problem in problems:
        logger.error(problem)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
