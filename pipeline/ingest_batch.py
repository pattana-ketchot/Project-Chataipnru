"""
นำเข้าเอกสารหลักสูตรทีละหลายไฟล์จากโฟลเดอร์เดียว

    python -m pipeline.ingest_batch --dir samples --provider "มหาวิทยาลัยราชภัฏพระนคร"

ชื่อหลักสูตร (title) อ่านจาก <dir>/titles.json ถ้ามี — รูปแบบ {"<ชื่อไฟล์ไม่รวม .pdf>": "<ชื่อหลักสูตร>"}
ถ้าไม่มีไฟล์นั้นหรือไม่มี key ของไฟล์นั้น จะใช้ชื่อไฟล์เป็น title แทน

รหัสหลักสูตร (course_code) ปกติใช้ชื่อไฟล์ แต่ override ได้ที่ <dir>/codes.json
รูปแบบเดียวกัน — จำเป็นเมื่อเอกสารคนละไฟล์เป็นหลักสูตรเดียวกัน เช่น มคอ.2 ฉบับเต็ม
กับใบสรุปหลักสูตรของสาขาเดียวกัน ต้องผูกเข้า course เดิม ไม่งั้นหน้าเว็บจะขึ้นสาขา
เดียวกันสองรายการ

ทำไมต้องมีสคริปต์นี้: ingest.py รับทีละไฟล์ตาม design (หนึ่งเอกสาร = หนึ่ง
transaction) แต่การ ingest คลังทั้งชุดต้องทำซ้ำทุกครั้งที่แก้ pipeline การพิมพ์
คำสั่งเองทีละ 18 บรรทัดทั้งช้าและพลาดง่าย

ไฟล์ที่เคยนำเข้าแล้วจะถูกข้ามอัตโนมัติ (ingest.py เช็คซ้ำด้วย sha256 ของไฟล์)
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from pipeline.ingest import run  # noqa: E402

logger = logging.getLogger("pipeline.ingest_batch")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest ทุกไฟล์ PDF ในโฟลเดอร์")
    parser.add_argument("--dir", required=True, help="โฟลเดอร์ที่เก็บไฟล์ PDF")
    parser.add_argument("--provider", help="ชื่อสถาบัน/หน่วยงานที่จัดหลักสูตร")
    parser.add_argument("--titles", help="ไฟล์ JSON แม็ปชื่อไฟล์ -> ชื่อหลักสูตร (ค่าเริ่มต้น: <dir>/titles.json)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    folder = Path(args.dir)
    # รับไฟล์ข้อความด้วย สำหรับหลักสูตรที่คณะไม่ได้เผยแพร่ มคอ.2 เป็นไฟล์
    pdfs = sorted([*folder.glob("*.pdf"), *folder.glob("*.txt")])
    if not pdfs:
        raise SystemExit(f"ไม่พบไฟล์เอกสารใน {folder}")

    titles_path = Path(args.titles) if args.titles else folder / "titles.json"
    titles: dict[str, str] = {}
    if titles_path.is_file():
        titles = json.loads(titles_path.read_text(encoding="utf-8"))
        logger.info("อ่านชื่อหลักสูตรจาก %s (%d รายการ)", titles_path, len(titles))
    else:
        logger.warning("ไม่พบ %s — จะใช้ชื่อไฟล์เป็นชื่อหลักสูตรแทน", titles_path)

    codes_path = folder / "codes.json"
    codes: dict[str, str] = {}
    if codes_path.is_file():
        codes = json.loads(codes_path.read_text(encoding="utf-8"))
        logger.info("อ่านรหัสหลักสูตรจาก %s (%d รายการ)", codes_path, len(codes))

    ok, failed = 0, []
    started = time.time()
    for i, pdf in enumerate(pdfs, start=1):
        title = titles.get(pdf.stem, pdf.stem)
        code = codes.get(pdf.stem, pdf.stem)
        logger.info("[%d/%d] %s — %s (รหัส %s)", i, len(pdfs), pdf.name, title, code)
        t0 = time.time()
        try:
            run(str(pdf), title=title, course_code=code, provider=args.provider)
            ok += 1
            logger.info("[%d/%d] เสร็จใน %.1f วินาที", i, len(pdfs), time.time() - t0)
        except Exception as e:
            # ไฟล์เดียวพังไม่ควรทำให้ทั้งชุดหยุด — เก็บไว้รายงานท้ายสุด
            failed.append((pdf.name, f"{type(e).__name__}: {e}"))
            logger.error("[%d/%d] ล้มเหลว: %s", i, len(pdfs), e)

    logger.info("รวม %.1f นาที | สำเร็จ %d/%d ไฟล์", (time.time() - started) / 60, ok, len(pdfs))
    if failed:
        logger.error("ไฟล์ที่ล้มเหลว:")
        for name, err in failed:
            logger.error("  %s -> %s", name, err)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
