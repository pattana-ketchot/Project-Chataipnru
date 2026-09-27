"""
Phase 2 — ตรวจเว็บ บันทึกสถานะ และเก็บไฟล์ใหม่ไว้ที่ staging รออนุมัติ

    python -m pipeline.crawl.sync --database-url <url> --staging <โฟลเดอร์>

สิ่งที่ตั้งใจไม่ทำใน Phase นี้
-----------------------------
ไม่เรียก pipeline/ingest.py · ไม่แตะ course_chunks · ไม่แตะ course_documents
ไม่ลบแถวใดในฐานข้อมูล · ไม่ตั้งเวลาทำงานอัตโนมัติ
ไฟล์ที่โหลดมาไปอยู่ที่ staging เฉยๆ รอให้คนเปิดดูแล้วสั่งนำเข้าเองใน Phase 3

ลำดับสถานะ
----------
    พบลิงก์
      ├─ HEAD เหมือนเดิม + เคยรู้ sha แล้ว ──────────► unchanged   (ไม่โหลดไฟล์)
      └─ โหลดมาคำนวณ sha256
            ├─ sha เท่าของเดิมที่เคยบันทึก ──────────► unchanged
            ├─ sha ตรงกับเอกสารในคลัง ───────────────► unchanged + ผูก document_id
            ├─ เคยรู้ sha เดิมแต่ตอนนี้ต่าง ─────────► changed    + เก็บ staging
            └─ ไม่เคยเห็นมาก่อน ─────────────────────► downloaded + เก็บ staging
    ดึงไม่สำเร็จ ───────────────────────────────────► error      (นับครั้งสะสม)

ธง needs_review ตั้งแยกจากสถานะ เมื่อระบุหลักสูตรไม่ได้ ระบุได้ไม่ชัด
หรือเมื่อเนื้อไฟล์เปลี่ยน — สามกรณีนี้คนต้องดูก่อนเสมอ
"""
from __future__ import annotations

import argparse
import hashlib
import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from pipeline.crawl.discover import PdfLink, crawl  # noqa: E402
from pipeline.crawl.http import PoliteClient  # noqa: E402
from pipeline.crawl.inventory import KnownDocument, match_course  # noqa: E402
from pipeline.crawl.state import CONFIDENCE_DB, CrawlStore  # noqa: E402

logger = logging.getLogger("pipeline.crawl.sync")

FACULTY_HOST = "sci.pnru.ac.th"
SEEDS = ["https://sci.pnru.ac.th/programs.php", "https://sci.pnru.ac.th/index.php"]
FOLLOW = [r"/program_detail\.php\?id=\d+", r"/programs\.php$"]

MIN_PLAUSIBLE_BYTES = 200 * 1024


@dataclass
class SyncOutcome:
    url: str
    filename: str
    status: str
    needs_review: bool
    reason: str = ""
    sha256: str | None = None
    previous_sha256: str | None = None
    staging_path: str | None = None
    course_label: str | None = None
    confidence: str = "unknown"


def _safe_name(link: PdfLink, sha: str) -> str:
    """
    ชื่อไฟล์ใน staging — ขึ้นต้นด้วย sha สิบสองตัวแรก ตามด้วยชื่อเดิมบนเว็บ

    ใช้ sha นำหน้าเพราะชื่อไฟล์บนเว็บเป็นค่าแฮชที่เปลี่ยนได้เมื่อคณะอัปโหลดใหม่
    และเพื่อให้ไฟล์คนละเนื้อไม่ทับกันแม้ชื่อเดิมจะซ้ำ
    """
    stem = Path(link.filename).name
    stem = "".join(c for c in stem if c.isalnum() or c in "._-")[:60] or "document.pdf"
    return f"{sha[:12]}_{stem}"


def process_link(client: PoliteClient, store: CrawlStore, link: PdfLink,
                 known_docs: list[KnownDocument], known_by_sha: dict[str, dict],
                 staging: Path, download: bool) -> SyncOutcome:
    existing = store.get_source(link.url)

    # ---- จับคู่หลักสูตร ------------------------------------------------
    m = match_course(link.page_title, known_docs)
    confidence = CONFIDENCE_DB.get(m.confidence, "unknown")
    needs_review = confidence in ("ambiguous", "unknown")
    reason = ""
    if confidence == "ambiguous":
        reason = f"ชื่อหลักสูตรตรงกับ {len(m.candidates)} ฉบับ แยกจากชื่ออย่างเดียวไม่ได้"
    elif confidence == "unknown":
        reason = "ระบุหลักสูตรจากหัวเรื่องของหน้าไม่ได้"

    common = dict(
        source_url=link.url, page_url=link.page_url, page_title=link.page_title,
        link_text=link.link_text, course_code=m.course_code, course_label=m.course_title,
        match_confidence=confidence, match_score=m.score, match_candidates=m.candidates,
    )

    # ---- HEAD ------------------------------------------------------------
    etag = last_mod = None
    length = None
    head = client.head(link.url)
    if head is not None and head.status_code == 200:
        etag = head.headers.get("etag")
        last_mod = head.headers.get("last-modified")
        cl = head.headers.get("content-length")
        length = int(cl) if cl and cl.isdigit() else None
    elif head is not None and head.status_code >= 400:
        store.upsert(**common, needs_review=True, review_reason="ดึงไฟล์ไม่สำเร็จ",
                     status="error", last_error=f"HEAD http {head.status_code}", bump_error=True,
                     http_etag=None, http_last_modified=None, content_length=None,
                     file_sha256=None, previous_sha256=None, staging_path=None, document_id=None)
        return SyncOutcome(link.url, link.filename, "error", True,
                           f"HEAD http {head.status_code}", confidence=confidence)

    # ---- ข้ามการโหลดถ้าไม่มีอะไรเปลี่ยนเลย -------------------------------
    if (existing and existing.file_sha256 and etag and existing.http_etag == etag
            and (length is None or existing.content_length == length)):
        store.upsert(**common, needs_review=needs_review, review_reason=reason or None,
                     status="unchanged", last_error=None, bump_error=False,
                     http_etag=etag, http_last_modified=last_mod, content_length=length,
                     file_sha256=None, previous_sha256=None, staging_path=None, document_id=None)
        return SyncOutcome(link.url, link.filename, "unchanged", needs_review,
                           "ETag และขนาดไฟล์เท่าเดิม ไม่ต้องโหลด",
                           sha256=existing.file_sha256, course_label=m.course_title,
                           confidence=confidence)

    if not download:
        store.upsert(**common, needs_review=needs_review, review_reason=reason or None,
                     status=existing.status if existing else "new",
                     last_error=None, bump_error=False,
                     http_etag=etag, http_last_modified=last_mod, content_length=length,
                     file_sha256=None, previous_sha256=None, staging_path=None, document_id=None)
        return SyncOutcome(link.url, link.filename, existing.status if existing else "new",
                           needs_review, "โหมดไม่โหลดไฟล์", confidence=confidence)

    # ---- โหลดมาคำนวณ sha256 ---------------------------------------------
    resp = client.get(link.url)
    if resp is None or resp.status_code != 200:
        code = resp.status_code if resp is not None else "-"
        store.upsert(**common, needs_review=True, review_reason="ดึงไฟล์ไม่สำเร็จ",
                     status="error", last_error=f"GET http {code}", bump_error=True,
                     http_etag=etag, http_last_modified=last_mod, content_length=length,
                     file_sha256=None, previous_sha256=None, staging_path=None, document_id=None)
        return SyncOutcome(link.url, link.filename, "error", True, f"GET http {code}",
                           confidence=confidence)

    body = resp.content
    sha = hashlib.sha256(body).hexdigest()
    size = len(body)

    # เหมือนของที่เคยบันทึกไว้เอง
    if existing and existing.file_sha256 == sha:
        store.upsert(**common, needs_review=needs_review, review_reason=reason or None,
                     status="unchanged", last_error=None, bump_error=False,
                     http_etag=etag, http_last_modified=last_mod, content_length=size,
                     file_sha256=sha, previous_sha256=None, staging_path=None, document_id=None)
        return SyncOutcome(link.url, link.filename, "unchanged", needs_review,
                           "เนื้อไฟล์เหมือนรอบก่อน", sha256=sha,
                           course_label=m.course_title, confidence=confidence)

    # มีอยู่ในคลังความรู้แล้ว
    if sha in known_by_sha:
        doc = known_by_sha[sha]
        store.upsert(**common, needs_review=needs_review, review_reason=reason or None,
                     status="unchanged", last_error=None, bump_error=False,
                     http_etag=etag, http_last_modified=last_mod, content_length=size,
                     file_sha256=sha, previous_sha256=None, staging_path=None,
                     document_id=str(doc["id"]))
        return SyncOutcome(link.url, link.filename, "unchanged", needs_review,
                           f"มีในคลังแล้ว ({doc['original_filename']})", sha256=sha,
                           course_label=doc["course_title"], confidence=confidence)

    # ---- ของใหม่หรือของที่เปลี่ยน — เก็บไว้ที่ staging --------------------
    staging.mkdir(parents=True, exist_ok=True)
    out = staging / _safe_name(link, sha)
    out.write_bytes(body)

    changed = bool(existing and existing.file_sha256 and existing.file_sha256 != sha)
    status = "changed" if changed else "downloaded"
    why = "เนื้อไฟล์เปลี่ยนจากรอบก่อน" if changed else "ไฟล์ใหม่ ยังไม่มีในคลัง"
    if size < MIN_PLAUSIBLE_BYTES:
        why += f" · ไฟล์เล็กผิดปกติ ({size/1024:.0f} KB) อาจไม่ใช่เอกสารหลักสูตร"

    store.upsert(**common,
                 needs_review=True,                 # ของใหม่และของที่เปลี่ยนต้องให้คนดูเสมอ
                 review_reason=(reason + " · " if reason else "") + why,
                 status=status, last_error=None, bump_error=False,
                 http_etag=etag, http_last_modified=last_mod, content_length=size,
                 file_sha256=sha,
                 previous_sha256=existing.file_sha256 if changed else None,
                 staging_path=str(out), document_id=None)
    return SyncOutcome(link.url, link.filename, status, True, why, sha256=sha,
                       previous_sha256=existing.file_sha256 if changed else None,
                       staging_path=str(out), course_label=m.course_title, confidence=confidence)


def main() -> None:
    ap = argparse.ArgumentParser(description="Phase 2 — ตรวจ บันทึกสถานะ และเก็บไฟล์รออนุมัติ")
    ap.add_argument("--database-url", default=os.environ.get("CRAWL_DATABASE_URL"),
                    help="ค่าเริ่มต้นอ่านจาก CRAWL_DATABASE_URL")
    ap.add_argument("--staging", default="staging/crawl", help="โฟลเดอร์เก็บไฟล์รออนุมัติ")
    ap.add_argument("--delay", type=float, default=1.5)
    ap.add_argument("--max-pages", type=int, default=80)
    ap.add_argument("--no-download", action="store_true",
                    help="ตรวจและบันทึกสถานะอย่างเดียว ไม่โหลดไฟล์")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not args.database_url:
        raise SystemExit("ต้องระบุ --database-url หรือตั้ง CRAWL_DATABASE_URL")

    staging = Path(args.staging)
    started = datetime.now(timezone.utc)

    with CrawlStore(args.database_url) as store:
        by_sha = store.known_sha256()
        known_docs = [
            KnownDocument(sha256=k, filename=v["original_filename"], page_count=v["page_count"],
                          course_code=v["course_code"] or "", course_title=v["course_title"] or "")
            for k, v in by_sha.items()
        ]
        logger.info("คลังที่ระบบมี: %d เอกสาร", len(known_docs))

        with PoliteClient(delay=args.delay) as client:
            pages, links, errors = crawl(client, SEEDS, FACULTY_HOST, FOLLOW, args.max_pages)
            logger.info("เดินเว็บ %d หน้า พบลิงก์ PDF ไม่ซ้ำ %d", len(pages), len(links))

            outcomes = []
            for i, link in enumerate(links, 1):
                logger.info("[%d/%d] %s", i, len(links), link.filename)
                try:
                    o = process_link(client, store, link, known_docs, by_sha, staging,
                                     download=not args.no_download)
                except Exception as e:
                    # ลิงก์เดียวพังต้องไม่ทำให้ทั้งรอบหยุด
                    store.conn.rollback()
                    logger.error("[%d/%d] ล้มเหลว: %s", i, len(links), e)
                    o = SyncOutcome(link.url, link.filename, "error", True, f"{type(e).__name__}: {e}")
                    try:
                        store.upsert(
                            source_url=link.url, page_url=link.page_url, page_title=link.page_title,
                            link_text=link.link_text, course_code=None, course_label=None,
                            match_confidence=None, match_score=None, match_candidates=[],
                            needs_review=True, review_reason="เกิดข้อผิดพลาดระหว่างตรวจ",
                            status="error", last_error=str(e)[:500], bump_error=True,
                            http_etag=None, http_last_modified=None, content_length=None,
                            file_sha256=None, previous_sha256=None, staging_path=None,
                            document_id=None)
                        store.conn.commit()
                    except Exception as inner:
                        store.conn.rollback()
                        logger.error("บันทึกสถานะ error ไม่สำเร็จ: %s", inner)
                else:
                    store.conn.commit()
                outcomes.append(o)

            requests_made = client.requests_made

    # ---- สรุปท้ายรอบ -----------------------------------------------------
    tally: dict[str, int] = {}
    for o in outcomes:
        tally[o.status] = tally.get(o.status, 0) + 1
    review = sum(1 for o in outcomes if o.needs_review)

    logger.info("---- สรุป ----")
    for k in ("unchanged", "downloaded", "changed", "error", "new"):
        if k in tally:
            logger.info("  %-11s %d", k, tally[k])
    logger.info("  รอคนตรวจ   %d", review)
    logger.info("  คำขอ HTTP  %d · ใช้เวลา %.0f วินาที",
                requests_made, (datetime.now(timezone.utc) - started).total_seconds())
    if not args.no_download:
        logger.info("  ไฟล์รออนุมัติอยู่ที่ %s", staging.resolve())
    logger.info("Phase 2 ไม่นำเข้าคลังความรู้ — ต้องให้คนอนุมัติก่อน")


if __name__ == "__main__":
    main()
