"""
Phase 1 — สำรวจอย่างเดียว ไม่นำเข้าอะไรทั้งสิ้น

    python -m pipeline.crawl.run --inventory <ไฟล์.tsv> --out <รายงาน.md>

ทำอะไรบ้าง
----------
เดินเว็บคณะ หาลิงก์ PDF หลักสูตร แล้วตอบว่าแต่ละไฟล์อยู่ในสถานะไหน
เทียบกับคลังที่ระบบมีอยู่ ด้วย sha256 เป็นหลัก

สิ่งที่ตั้งใจไม่ทำใน Phase นี้
-----------------------------
ไม่เขียนฐานข้อมูล · ไม่เก็บไฟล์ PDF ไว้ · ไม่แตะ pipeline การนำเข้า
ไฟล์ที่โหลดมาถูกอ่านเป็นสายข้อมูลเพื่อคำนวณ sha256 แล้วทิ้งทันที ไม่เขียนลงดิสก์

ทำไมต้องโหลดไฟล์ถึงจะรู้ว่าซ้ำ
------------------------------
ระบบเก็บลายนิ้วมือของเอกสารเป็น sha256 ของเนื้อไฟล์ ไม่ได้เก็บ URL ต้นทาง
(ดู docs/AUTOMATED_INGESTION_ANALYSIS.md ข้อ 2) การจะตอบว่า "ไฟล์นี้มีในระบบแล้ว"
จึงต้องคำนวณ sha256 ของไฟล์บนเว็บ ซึ่งต้องโหลดมาทั้งไฟล์

ลดภาระเว็บปลายทางด้วยการ HEAD ก่อนทุกครั้ง เพื่อรู้ขนาดไฟล์ไว้รายงาน และเพื่อ
เก็บ ETag/Last-Modified ไว้ให้ Phase 2 ใช้ข้ามการโหลดในรอบถัดไป
"""
from __future__ import annotations

import argparse
import logging
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from pipeline.crawl.discover import PdfLink, crawl  # noqa: E402
from pipeline.crawl.http import PoliteClient, url_rejection  # noqa: E402
from pipeline.crawl.inventory import KnownDocument, MatchResult, load_inventory, match_course  # noqa: E402
from pipeline.crawl.report import write_report  # noqa: E402

logger = logging.getLogger("pipeline.crawl.run")

FACULTY_HOST = "sci.pnru.ac.th"
SEEDS = [
    "https://sci.pnru.ac.th/programs.php",
    "https://sci.pnru.ac.th/index.php",
]
# ตามเฉพาะหน้ารายละเอียดหลักสูตรกับหน้ารวมหลักสูตร ไม่ไล่ทั้งเว็บ
FOLLOW = [r"/program_detail\.php\?id=\d+", r"/programs\.php$"]

# เอกสารหลักสูตรมีอย่างน้อยหลายสิบหน้า ไฟล์เล็กกว่านี้มักเป็นประกาศหรือใบสมัคร
MIN_PLAUSIBLE_BYTES = 200 * 1024


@dataclass
class Finding:
    link: PdfLink
    status: str                    # มีอยู่แล้ว | ไฟล์ใหม่ | อาจเปลี่ยนแปลง | ระบุไม่ได้ | ดึงไม่สำเร็จ
    match: MatchResult
    sha256: str | None = None
    byte_size: int | None = None
    etag: str | None = None
    last_modified: str | None = None
    matched_doc: KnownDocument | None = None
    note: str = ""


def probe(client: PoliteClient, link: PdfLink, known: list[KnownDocument], do_hash: bool,
          scratch: Path) -> Finding:
    m = match_course(link.page_title, known)
    f = Finding(link=link, status="ระบุไม่ได้", match=m)

    # ลิงก์นอกขอบเขต — รายงานไว้แต่ไม่ยิงคำขอ (ดู pipeline/crawl/http.py)
    out_of_scope = url_rejection(link.url)
    if out_of_scope:
        f.status = "ดึงไม่สำเร็จ"
        f.note = f"นอกขอบเขตที่อนุญาต — {out_of_scope}"
        return f

    head = client.head(link.url)
    if head is not None and head.status_code == 200:
        f.etag = head.headers.get("etag")
        f.last_modified = head.headers.get("last-modified")
        cl = head.headers.get("content-length")
        if cl and cl.isdigit():
            f.byte_size = int(cl)

    if not do_hash:
        f.status = "ยังไม่ได้ตรวจ"
        f.note = "ข้ามการคำนวณ sha256 (--no-hash)"
        return f

    # ใช้ตัวดาวน์โหลดตัวเดียวกับ Phase 2 เพื่อให้ได้ด่านตรวจชุดเดียวกัน (โฮสต์ปลายทางหลัง
    # redirect · เพดานขนาด · ลายเซ็น %PDF-) เดิมที่นี่ใช้ resp.content ซึ่งอ่านทั้งไฟล์เข้า
    # หน่วยความจำก่อนแล้วจึงรู้ขนาด และไม่ได้ตรวจว่าไฟล์เป็น PDF จริงหรือไม่
    dl = client.download(link.url, scratch)
    if not dl.ok:
        f.status = "ดึงไม่สำเร็จ"
        f.note = dl.reason
        return f

    f.byte_size = dl.size
    f.sha256 = dl.sha256
    if dl.content_type_mismatch:
        f.note = f"เซิร์ฟเวอร์ประกาศ content-type เป็น {dl.content_type or 'ไม่ระบุ'}"
    # Phase 1 ตรวจอย่างเดียว ไม่เก็บไฟล์ไว้
    if dl.path is not None:
        dl.path.unlink(missing_ok=True)

    by_sha = {k.sha256: k for k in known if k.sha256}
    if f.sha256 in by_sha:
        f.status = "มีอยู่แล้ว"
        f.matched_doc = by_sha[f.sha256]
        return f

    # sha ไม่ตรงสักแถว แต่ถ้าจับคู่หลักสูตรได้ แปลว่าหลักสูตรนี้เคยมีเอกสารแล้ว
    # และไฟล์บนเว็บเป็นคนละเนื้อ — อาจเป็นฉบับปรับปรุงใหม่ ต้องให้คนดู
    same_course = [k for k in known if m.course_code and k.course_code == m.course_code]
    if same_course:
        f.status = "อาจเปลี่ยนแปลง"
        f.matched_doc = same_course[0]
        f.note = "หลักสูตรนี้มีเอกสารในระบบแล้ว แต่เนื้อไฟล์ไม่ตรงกัน"
        return f

    f.status = "ไฟล์ใหม่" if m.confidence != "ระบุไม่ได้" else "ระบุไม่ได้"
    if f.byte_size and f.byte_size < MIN_PLAUSIBLE_BYTES:
        f.note = (f.note + " · " if f.note else "") + \
                 f"ไฟล์เล็กผิดปกติ ({f.byte_size/1024:.0f} KB) อาจไม่ใช่เอกสารหลักสูตร"
    return f


def main() -> None:
    ap = argparse.ArgumentParser(description="Phase 1 — สำรวจ PDF หลักสูตรบนเว็บคณะ (ไม่นำเข้า)")
    ap.add_argument("--inventory", required=True, help="ไฟล์ TSV ของเอกสารที่ระบบมีอยู่")
    ap.add_argument("--out", default="CRAWL_PDF_DISCOVERY_REPORT.md")
    ap.add_argument("--delay", type=float, default=1.5, help="วินาทีที่หน่วงระหว่างคำขอ")
    ap.add_argument("--max-pages", type=int, default=80)
    ap.add_argument("--no-hash", action="store_true", help="ไม่โหลดไฟล์มาคำนวณ sha256")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    known = load_inventory(args.inventory)
    logger.info("คลังที่ระบบมี: %d เอกสาร", len(known))

    started = datetime.now(timezone.utc)
    # โฟลเดอร์ชั่วคราวสำหรับไฟล์ที่โหลดมาคำนวณ sha256 — Phase 1 ไม่เก็บไฟล์ไว้
    # ตัวดาวน์โหลดต้องมีที่เขียนไฟล์เพราะทยอยอ่านทีละก้อนแทนการถือทั้งไฟล์ในหน่วยความจำ
    with PoliteClient(delay=args.delay) as client, tempfile.TemporaryDirectory(
            prefix="crawl_probe_") as tmp:
        scratch = Path(tmp)
        pages, links, errors = crawl(client, SEEDS, FACULTY_HOST, FOLLOW, args.max_pages)
        logger.info("เดินเว็บ %d หน้า พบลิงก์ PDF ไม่ซ้ำ %d รายการ", len(pages), len(links))

        findings = []
        for i, link in enumerate(links, 1):
            logger.info("[%d/%d] ตรวจ %s", i, len(links), link.filename)
            findings.append(probe(client, link, known, do_hash=not args.no_hash,
                                  scratch=scratch))

        requests_made = client.requests_made

    out = Path(args.out)
    write_report(
        out, findings=findings, pages=pages, errors=errors, known=known,
        started=started, finished=datetime.now(timezone.utc),
        requests_made=requests_made, delay=args.delay, hashed=not args.no_hash,
    )
    logger.info("เขียนรายงานที่ %s", out)


if __name__ == "__main__":
    main()
