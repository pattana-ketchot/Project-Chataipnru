"""
สร้างชุดไฟล์สำหรับ deploy Phase 4 — รันบนเครื่องพัฒนา

    python -m tools.make_phase4_bundle

ทำไมต้องมีสคริปต์ ไม่ใช่ tar มือ
--------------------------------
1. **ส่งแค่ Phase 4** — tree บนเครื่องพัฒนามีงาน crawl review และ MKO pipeline
   ที่ยังไม่ได้ตรวจรับบน production อยู่ด้วย `tar` ทั้งโฟลเดอร์จะพา
   ของเหล่านั้นขึ้น production ไปโดยไม่มีใครเห็น

2. **`main.py` ต้องแก้ก่อนส่ง** — ฉบับบนเครื่องพัฒนา `import crawl_review`
   ซึ่งไม่มีบนเซิร์ฟเวอร์ ส่งไปตรง ๆ แล้ว backend **ขึ้นไม่ได้เลย**
   สคริปต์ตัดเฉพาะสองบรรทัดนั้นออกและ **ยืนยันว่าตัดได้จริงทั้งสองจุด**
   ถ้าตัดไม่ได้จะหยุด ไม่สร้างไฟล์ที่พังเงียบ ๆ

3. **CRLF** — ไฟล์บนเครื่อง Windows เป็น CRLF ถ้าส่งขึ้นไปอย่างนั้น
   `20-roles.sh` และ shebang ต่าง ๆ จะรันไม่ได้ และ diff จะดูเหมือนเปลี่ยนทุกบรรทัด
   สคริปต์แปลงเป็น LF ให้ทุกไฟล์ข้อความ

4. **manifest** — มี sha256 ของทุกไฟล์ ให้ฝั่งเซิร์ฟเวอร์เทียบได้ว่าได้ของครบและตรง

สิ่งที่ **ไม่** ใส่ลงชุด และเพราะอะไร
-----------------------------------
| ไฟล์ | เหตุผล |
|---|---|
| `backend/app/api/routes/crawl_review.py` + `services/crawl_review.py` + `services/staging_store.py` + `schemas/crawl_review.py` | งาน crawl review ยังไม่ตรวจรับบน production |
| `pipeline/mko/*` · `pipeline/crawl/*` | งาน MKO/crawler ไม่เกี่ยวกับ Phase 4 |
| `db/migrations/001`–`006` | รันบน production ไปแล้ว (ดู docs/MIGRATION_00*_PRODUCTION_APPLY_RESULT.md) |
| `db/schema.sql` · `db/20-roles.sh` | ใช้ตอนสร้างฐานข้อมูลใหม่เท่านั้น ฐานปัจจุบันมีข้อมูลอยู่แล้วจึงไม่ถูกเรียกใช้ · ส่งไปก็ไม่มีผล แต่เพิ่มความเสี่ยงเปล่า ๆ |
| `backend/app/api/routes/web_compat.py` | มีงาน careers อยู่ข้างใน ซึ่งยังไม่ตรวจรับ — ใส่ด้วย `--with-careers` ถ้าเจ้าของสั่ง |
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import sys
import tarfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "dist-deploy"

# วงปิดของ Phase 4 — ได้จากการเดินตาม import จริงของ 5 router + งานตั้งเวลา
# (ตรวจแล้วว่าไม่พึ่ง crawl/staging เลย ดู docs/PHASE4_PREFLIGHT_RESULT_2569-10-12.md ข้อ 7)
BACKEND_FILES = (
    "backend/app/main.py",                      # ถูกแก้ก่อนใส่ชุด ดู strip_crawl_review()
    "backend/app/api/deps.py",
    "backend/app/api/routes/auth.py",
    "backend/app/api/routes/extract.py",
    "backend/app/api/routes/site.py",
    "backend/app/api/routes/site_admin.py",
    "backend/app/api/routes/uploads.py",
    "backend/app/core/config.py",
    "backend/app/core/security.py",
    "backend/app/db/session.py",
    "backend/app/jobs/__init__.py",
    "backend/app/jobs/sync_sci_news.py",
    "backend/app/models/user.py",
    "backend/app/schemas/user.py",
    "backend/app/services/__init__.py",
    "backend/app/services/auth_service.py",
    "backend/app/services/file_store.py",
    "backend/app/services/mailer.py",
    "backend/app/services/sci_news.py",
    "backend/requirements.txt",
)

OTHER_FILES = (
    "db/migrations/007_web_auth.sql",
    "docker-compose.prod.yml",
    "pipeline/__init__.py",
    "pipeline/web/__init__.py",
    "pipeline/web/import_from_supabase.py",
    "pipeline/web/import_accounts.py",
    "pipeline/web/migrate_storage.py",
    "pipeline/web/programme_links.json",
)

OPTIONAL_CAREERS = ("backend/app/api/routes/web_compat.py",)

# ส่งค่านี้ให้ newline= ทุกครั้งที่เขียนไฟล์ข้อความ
#
# Windows แปลง LF เป็น CRLF ให้เองตอนเขียนไฟล์ข้อความ ถ้าปล่อยไว้
# `sha256sum -c` บน Linux จะอ่านชื่อไฟล์ติดอักขระ CR ไปด้วยแล้วฟ้องว่าไม่พบไฟล์
# ทั้งที่ checksum ถูกต้อง — เจอจากการทดสอบคำสั่งฝั่งเซิร์ฟเวอร์จริง
LF = chr(10)

# นามสกุลที่ถือเป็นไฟล์ข้อความ — ต้องแปลง CRLF เป็น LF ก่อนใส่ชุด
TEXT_SUFFIXES = {".py", ".sql", ".yml", ".yaml", ".json", ".txt", ".sh", ".md"}

CRAWL_IMPORT_OLD = """from app.api.routes import (auth, chat, compare, courses, crawl_review, documents, extract,
                            match, recommend, search, site, site_admin, uploads, users,
                            web_compat)"""
CRAWL_IMPORT_NEW = """from app.api.routes import (auth, chat, compare, courses, documents, extract,
                            match, recommend, search, site, site_admin, uploads, users,
                            web_compat)"""
CRAWL_ROUTER_OLD = """# คิวตรวจไฟล์หลักสูตรที่ crawler พบ — ผู้ดูแลเท่านั้น (ดู routes/crawl_review.py)
app.include_router(crawl_review.router)
"""


def strip_crawl_review(source: str) -> str:
    """
    ตัด router ของ crawl review ออกจาก main.py ก่อนส่ง

    **ยืนยันว่าตัดได้ทั้งสองจุดจริง** ถ้าหาไม่เจอให้หยุด — main.py ที่ import
    โมดูลซึ่งไม่มีบนเซิร์ฟเวอร์ทำให้ backend ขึ้นไม่ได้ และจะรู้ตอน restart แล้ว
    ซึ่งสายไปแล้วเพราะคอนเทนเนอร์เดิมถูกแทนที่ไปแล้ว
    """
    for needle in (CRAWL_IMPORT_OLD, CRAWL_ROUTER_OLD):
        if source.count(needle) != 1:
            raise SystemExit(
                "หยุด: หา crawl_review ใน main.py ไม่เจอตามที่คาด "
                "(เจอ %d ครั้ง) — main.py เปลี่ยนไปจากที่สคริปต์นี้รู้จัก "
                "ตรวจด้วยมือก่อนส่ง" % source.count(needle)
            )
    source = source.replace(CRAWL_IMPORT_OLD, CRAWL_IMPORT_NEW)
    source = source.replace(CRAWL_ROUTER_OLD, "")
    if "crawl_review" in source:
        raise SystemExit("หยุด: ยังเหลือคำว่า crawl_review ใน main.py หลังตัด")
    return source


def read_for_bundle(rel: str) -> bytes:
    path = REPO / rel
    if not path.is_file():
        raise SystemExit(f"หยุด: ไม่มีไฟล์ {rel}")
    data = path.read_bytes()
    if path.suffix.lower() in TEXT_SUFFIXES:
        data = data.replace(b"\r\n", b"\n")
    if rel == "backend/app/main.py":
        data = strip_crawl_review(data.decode("utf-8")).encode("utf-8")
    return data


def add(tar: tarfile.TarFile, rel: str, data: bytes, mtime: int) -> dict:
    info = tarfile.TarInfo(name=rel)
    info.size = len(data)
    info.mtime = mtime
    # 0644 สำหรับไฟล์ทั่วไป · สคริปต์ .sh ต้องรันได้
    info.mode = 0o755 if rel.endswith(".sh") else 0o644
    info.uid = info.gid = 0
    info.uname = info.gname = "root"
    tar.addfile(info, io.BytesIO(data))
    return {"path": rel, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def main() -> int:
    # คอนโซลของ Windows เป็น cp1252 ซึ่งเขียนภาษาไทยไม่ได้ และจะ throw
    # ตอน print หลังสร้างไฟล์เสร็จแล้ว ทำให้ดูเหมือนสคริปต์ล้มทั้งที่ชุดไฟล์ถูกสร้างแล้ว
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

    parser = argparse.ArgumentParser(description="สร้างชุดไฟล์ deploy Phase 4")
    parser.add_argument("--with-careers", action="store_true",
                        help="ใส่ web_compat.py (เส้นทางรายการอาชีพ) ลงไปด้วย")
    args = parser.parse_args()

    files = list(BACKEND_FILES) + list(OTHER_FILES)
    if args.with_careers:
        files += list(OPTIONAL_CAREERS)

    OUT_DIR.mkdir(exist_ok=True)
    bundle = OUT_DIR / "phase4-source.tar.gz"
    # mtime คงที่เพื่อให้ไฟล์ชุดเดิมได้ checksum เดิมทุกครั้งที่สร้าง
    mtime = int(time.mktime((2026, 10, 12, 0, 0, 0, 0, 0, 0)))

    # gzip ฝังเวลาที่สร้างไฟล์ลงใน header ด้วย ถ้าปล่อยไว้ archive ที่มีเนื้อหา
    # เหมือนกันเป๊ะจะได้ checksum ต่างกันทุกครั้งที่ build — เอกสารจึงอ้าง checksum ไม่ได้
    # ตั้ง mtime=0 และไม่ฝังชื่อไฟล์ เพื่อให้ build ซ้ำได้ checksum เดิมและตรวจย้อนได้
    manifest = []
    with open(bundle, "wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
            with tarfile.open(fileobj=gz, mode="w") as tar:
                for rel in files:
                    manifest.append(add(tar, rel, read_for_bundle(rel), mtime))

    (OUT_DIR / "phase4-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8", newline=LF)

    digest = hashlib.sha256(bundle.read_bytes()).hexdigest()
    (OUT_DIR / "phase4-source.tar.gz.sha256").write_text(
        digest + "  phase4-source.tar.gz" + LF, encoding="utf-8", newline=LF)

    print(f"สร้าง {bundle.name} · {len(manifest)} ไฟล์ · "
          f"{bundle.stat().st_size:,} ไบต์")
    print(f"sha256: {digest}")
    print(f"careers: {'ใส่' if args.with_careers else 'ไม่ใส่'}")
    print(f"\nไฟล์ทั้งหมดอยู่ที่ {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
