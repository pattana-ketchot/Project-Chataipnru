"""
ย้ายไฟล์จาก Supabase Storage มาเก็บบนเซิร์ฟเวอร์ — Phase 4

    python -m pipeline.web.migrate_storage --dry-run
    python -m pipeline.web.migrate_storage --apply
    python -m pipeline.web.migrate_storage --apply --retry-failed

รับค่าผ่าน environment ทั้งหมด **ไม่ต้องใส่ค่าลับในคำสั่ง และไม่มีอะไรพิมพ์ค่าลับออกมา**

    SUPABASE_URL                 เช่น https://xxxx.supabase.co
    SUPABASE_SERVICE_ROLE_KEY    ต้องใช้สิทธิ์นี้เพราะ bucket knowledge-files เป็นแบบ private
    DATABASE_URL                 ฐานข้อมูลปลายทาง
    UPLOADS_DIR                  โฟลเดอร์ปลายทางบนเซิร์ฟเวอร์

ทำอะไรบ้าง
----------
1. อ่าน URL ของไฟล์ที่ถูกอ้างถึงจริงในฐานข้อมูล (ไม่กวาดทั้ง bucket — ไฟล์ที่ไม่มีใคร
   อ้างถึงไม่ต้องย้าย)
2. ดาวน์โหลดทีละไฟล์ พร้อม retry
3. ตรวจ **checksum ของไฟล์ที่ได้** แล้วเก็บด้วยชื่อตาม sha256 แบบเดียวกับที่ระบบใช้
4. เขียน **manifest** บันทึกทุกไฟล์: URL เดิม → พาธใหม่ · ขนาด · sha256 · สถานะ
5. แก้ URL ที่อ้างถึงในฐานข้อมูลให้ชี้มาที่ `/api/uploads/...`

ทุกขั้นแยกจากกัน — `--dry-run` ดูรายการได้โดยไม่ดาวน์โหลด และการแก้ URL ในฐานข้อมูล
ทำ **หลังจาก** ไฟล์ครบแล้วเท่านั้น ถ้าดาวน์โหลดพลาดแม้ไฟล์เดียวจะไม่แก้ URL ใด ๆ เลย
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

MANIFEST_NAME = "storage_migration_manifest.json"
RETRIES = 3
RETRY_WAIT = 2
TIMEOUT = 60

# คอลัมน์ที่เก็บ URL ของไฟล์ และหมวดปลายทางของแต่ละคอลัมน์
#
# หมวดกำหนดทั้งชนิดไฟล์ที่ยอมรับและความเป็นส่วนตัว — knowledge ต้องเข้าสู่ระบบก่อนอ่าน
# เหมือน bucket เดิมที่เป็น private
SOURCES = (
    {"table": "web.site_courses", "column": "logo_url", "category": "logo"},
    {"table": "web.news", "column": "image_url", "category": "news"},
    {"table": "web.external_news", "column": "image_url", "category": "news"},
    {"table": "web.knowledge_articles", "column": "file_path", "category": "knowledge"},
)


@dataclass
class Item:
    table: str
    column: str
    category: str
    original: str
    new_path: str = ""
    sha256: str = ""
    size: int = 0
    status: str = "pending"
    reason: str = ""


def is_supabase_url(value: str) -> bool:
    """ค่านี้ชี้ไปที่ Supabase ไหม — ค่าที่ชี้ไปที่อื่นอยู่แล้วไม่ต้องย้าย"""
    return bool(value) and ".supabase." in value


def is_storage_key(value: str, category: str) -> bool:
    """
    ค่านี้เป็น key ภายใน bucket (ไม่ใช่ URL เต็ม) ไหม

    `knowledge_articles.file_path` ของเดิมเก็บเป็น key เพราะ bucket เป็น private
    และต้องสร้าง signed URL ตอนเปิด
    """
    return bool(value) and "://" not in value and not value.startswith("/")


def download_url_for(base_url: str, item: Item) -> str:
    """URL ที่ใช้ดาวน์โหลดไฟล์หนึ่ง — key ภายใน bucket ต้องประกอบ URL เอง"""
    if is_supabase_url(item.original):
        return item.original
    bucket = "knowledge-files" if item.category == "knowledge" else "course-assets"
    key = urllib.parse.quote(item.original)
    return f"{base_url.rstrip('/')}/storage/v1/object/{bucket}/{key}"


def fetch(url: str, service_key: str) -> bytes:
    """
    ดาวน์โหลดหนึ่งไฟล์ พร้อม retry

    ใส่ service role key ใน header เสมอ — bucket แบบ private ต้องใช้ และ bucket แบบ
    public ก็ไม่เสียหาย **ค่าคีย์ไม่เคยถูกพิมพ์หรือใส่ใน URL**
    """
    last = ""
    for attempt in range(1, RETRIES + 1):
        request = urllib.request.Request(url, headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "User-Agent": "sci-advisor-storage-migration/1.0",
        })
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                if response.status == 200:
                    return response.read()
                last = f"HTTP {response.status}"
        except urllib.error.HTTPError as exc:
            last = f"HTTP {exc.code}"
            if exc.code in (401, 403, 404):
                break  # ลองใหม่ไม่ช่วย
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = type(exc).__name__
        if attempt < RETRIES:
            time.sleep(RETRY_WAIT * attempt)
    raise RuntimeError(last or "ดาวน์โหลดไม่สำเร็จ")


def collect(conn) -> list[Item]:
    """หา URL ของไฟล์ที่ถูกอ้างถึงจริงในฐานข้อมูล"""
    items: list[Item] = []
    for source in SOURCES:
        rows = conn.execute(
            f"select distinct {source['column']} as value from {source['table']}"
            f" where {source['column']} is not null and {source['column']} <> ''"
        ).fetchall()
        for row in rows:
            value = row["value"]
            if is_supabase_url(value) or is_storage_key(value, source["category"]):
                items.append(Item(table=source["table"], column=source["column"],
                                  category=source["category"], original=value))
    return items


def store(data: bytes, item: Item, uploads_dir: Path) -> Item:
    """เก็บไฟล์ด้วยชื่อตาม sha256 — รูปแบบเดียวกับที่ services/file_store.py ใช้"""
    digest = hashlib.sha256(data).hexdigest()
    suffix = Path(item.original.split("?")[0]).suffix.lower() or ".bin"
    relative = f"{item.category}/{digest[:2]}/{digest}{suffix}"

    target = (uploads_dir / relative).resolve()
    if not str(target).startswith(str(uploads_dir.resolve())):
        raise RuntimeError("พาธปลายทางออกนอกโฟลเดอร์ที่กำหนด")

    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        temporary = target.with_suffix(target.suffix + ".part")
        temporary.write_bytes(data)
        temporary.replace(target)

    # ตรวจซ้ำจากไฟล์ที่เขียนลงดิสก์จริง ไม่ใช่จากตัวแปรในหน่วยความจำ
    on_disk = hashlib.sha256(target.read_bytes()).hexdigest()
    if on_disk != digest:
        raise RuntimeError("checksum ของไฟล์บนดิสก์ไม่ตรงกับที่ดาวน์โหลดมา")

    item.new_path = relative
    item.sha256 = digest
    item.size = len(data)
    item.status = "ok"
    return item


def rewrite_urls(conn, items: list[Item]) -> int:
    """
    แก้ค่าที่อ้างถึงไฟล์ในฐานข้อมูลให้ชี้มาที่เซิร์ฟเวอร์

    `knowledge_articles.file_path` เก็บเป็นพาธสัมพัทธ์เหมือนเดิม (ไม่ใช่ URL) เพราะ
    หน้าเว็บประกอบ URL เองและต้องแนบ token ตอนเปิด
    """
    changed = 0
    for item in items:
        if item.status != "ok":
            continue
        new_value = (item.new_path if item.column == "file_path"
                     else f"/api/uploads/{item.new_path}")
        result = conn.execute(
            f"update {item.table} set {item.column} = %s where {item.column} = %s",
            (new_value, item.original),
        )
        changed += result.rowcount or 0
    return changed


def run(dsn: str, base_url: str, service_key: str, uploads_dir: Path,
        apply: bool, retry_failed: bool) -> int:
    import psycopg
    from psycopg.rows import dict_row

    manifest_path = uploads_dir / MANIFEST_NAME
    previous: dict[str, dict] = {}
    if manifest_path.exists():
        previous = {entry["original"]: entry
                    for entry in json.loads(manifest_path.read_text(encoding="utf-8"))}

    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        items = collect(conn)
        print(f"ไฟล์ที่ถูกอ้างถึงและยังอยู่ที่ Supabase: {len(items)}")
        for source in SOURCES:
            count = sum(1 for i in items if i.table == source["table"]
                        and i.column == source["column"])
            if count:
                print(f"  {source['table']}.{source['column']} ({source['category']}): {count}")

        if not items:
            print("ไม่มีไฟล์ที่ต้องย้าย")
            return 0

        if not apply:
            print("\n-- โหมดลองเท่านั้น ไม่ได้ดาวน์โหลดและไม่ได้แก้ฐานข้อมูล --")
            return 0

        uploads_dir.mkdir(parents=True, exist_ok=True)
        done: list[Item] = []
        for index, item in enumerate(items, 1):
            cached = previous.get(item.original)
            if cached and cached.get("status") == "ok" and not retry_failed:
                item.__dict__.update({k: cached[k] for k in
                                      ("new_path", "sha256", "size", "status")})
                done.append(item)
                continue
            try:
                data = fetch(download_url_for(base_url, item), service_key)
                done.append(store(data, item, uploads_dir))
            except Exception as exc:  # noqa: BLE001
                item.status = "failed"
                # ข้อความแสดงเฉพาะชนิดของข้อผิดพลาด ไม่มี URL หรือค่าคีย์
                item.reason = str(exc)[:120]
                done.append(item)
            print(f"  [{index}/{len(items)}] {item.status}"
                  + (f" — {item.reason}" if item.reason else ""))

        manifest_path.write_text(
            json.dumps([asdict(i) for i in done], ensure_ascii=False, indent=2),
            encoding="utf-8")
        print(f"\nบันทึก manifest ไว้ที่ {manifest_path}")

        failed = [i for i in done if i.status != "ok"]
        if failed:
            print(f"‼ ดาวน์โหลดไม่สำเร็จ {len(failed)} ไฟล์ — **ยังไม่แก้ URL ในฐานข้อมูล**")
            print("  แก้สาเหตุแล้วรันซ้ำด้วย --apply --retry-failed")
            return 1

        with conn.transaction():
            changed = rewrite_urls(conn, done)
        print(f"ย้ายครบ {len(done)} ไฟล์ · แก้ค่าที่อ้างถึงในฐานข้อมูล {changed} แถว")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="ย้ายไฟล์จาก Supabase Storage")
    parser.add_argument("--apply", action="store_true", help="ดาวน์โหลดและแก้ฐานข้อมูลจริง")
    parser.add_argument("--dry-run", action="store_true", help="ดูรายการเท่านั้น (ค่าตั้งต้น)")
    parser.add_argument("--retry-failed", action="store_true",
                        help="ลองไฟล์ที่เคยพลาดใหม่ แทนที่จะข้ามไฟล์ที่เคยสำเร็จ")
    args = parser.parse_args()

    missing = [name for name in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY",
                                 "DATABASE_URL", "UPLOADS_DIR")
               if not os.environ.get(name)]
    if missing:
        print("ต้องตั้งค่าเหล่านี้ก่อน: " + ", ".join(missing))
        return 2

    return run(
        dsn=os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://"),
        base_url=os.environ["SUPABASE_URL"],
        service_key=os.environ["SUPABASE_SERVICE_ROLE_KEY"],
        uploads_dir=Path(os.environ["UPLOADS_DIR"]),
        apply=args.apply and not args.dry_run,
        retry_failed=args.retry_failed,
    )


if __name__ == "__main__":
    sys.exit(main())
