"""
สร้าง archive ของหน้าเว็บสำหรับ deploy — รันบนเครื่องพัฒนาหลัง `npm run build`

    python -m tools.make_web_bundle --dist ../LastProject/dist

ทำไมไม่ใช้ `tar` ตรง ๆ
---------------------
1. **ตรวจว่า build สะอาดก่อนห่อ** — ถ้ามีคำว่า supabase ในไฟล์ที่ build ออกมา
   แปลว่า build ผิดชุด สคริปต์จะ **ไม่สร้าง archive เลย** ดีกว่าสร้างแล้วไปเจอบนเซิร์ฟเวอร์
2. **manifest + checksum จากของจริงรอบนี้** — ไม่ใช้ค่าคงที่จากรอบก่อน
   ชื่อไฟล์ asset มี hash ของเนื้อหาอยู่ในชื่อ เปลี่ยนทุกครั้งที่ build
3. **ไม่แปลง CRLF** — ไฟล์ใน dist เป็น asset ที่ build แล้ว การแปลงจะทำให้ checksum
   ไม่ตรงกับไฟล์ที่เบราว์เซอร์โหลด (ต่างจากซอร์สที่ต้องแปลง)
"""
from __future__ import annotations

import argparse
import gzip
import io
import hashlib
import json
import sys
import tarfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "dist-deploy"

# ส่งค่านี้ให้ newline= ทุกครั้งที่เขียนไฟล์ข้อความ — ดูเหตุผลใน make_phase4_bundle.py
LF = chr(10)

# ไฟล์ที่ไม่ควรติดไปกับ archive
SKIP_NAMES = {".DS_Store", "Thumbs.db"}


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

    parser = argparse.ArgumentParser(description="ห่อ dist ของหน้าเว็บ")
    parser.add_argument("--dist", required=True, help="โฟลเดอร์ dist ที่ build แล้ว")
    args = parser.parse_args()

    dist = Path(args.dist).resolve()
    if not (dist / "index.html").is_file():
        raise SystemExit(f"หยุด: ไม่พบ index.html ใน {dist} — รัน npm run build ก่อน")

    files = sorted(p for p in dist.rglob("*")
                   if p.is_file() and p.name not in SKIP_NAMES)
    if not files:
        raise SystemExit("หยุด: ไม่มีไฟล์ใน dist")

    # ด่านที่สำคัญที่สุด — build ที่ยังมีร่องรอย Supabase ห้ามถูกห่อ
    dirty = []
    for p in files:
        try:
            if b"supabase" in p.read_bytes().lower():
                dirty.append(str(p.relative_to(dist)).replace("\\", "/"))
        except OSError:
            continue
    if dirty:
        raise SystemExit(
            "หยุด: ไฟล์ที่ build ออกมายังมีคำว่า supabase อยู่ — build ผิดชุด "
            "ไม่สร้าง archive\n  " + "\n  ".join(dirty))

    OUT_DIR.mkdir(exist_ok=True)
    bundle = OUT_DIR / "phase4-web.tgz"
    mtime = int(time.mktime((2026, 10, 12, 0, 0, 0, 0, 0, 0)))

    # mtime=0 และไม่ฝังชื่อไฟล์ใน header ของ gzip เพื่อให้ build ซ้ำได้ checksum เดิม
    # ดูเหตุผลเต็มใน make_phase4_bundle.py
    manifest = []
    with open(bundle, "wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
            with tarfile.open(fileobj=gz, mode="w") as tar:
                for p in files:
                    rel = str(p.relative_to(dist)).replace("\\", "/")
                    data = p.read_bytes()
                    info = tarfile.TarInfo(name="./" + rel)
                    info.size = len(data)
                    info.mtime = mtime
                    info.mode = 0o644
                    info.uid = info.gid = 0
                    info.uname = info.gname = "root"
                    tar.addfile(info, io.BytesIO(data))
                    manifest.append({"path": rel,
                                     "sha256": hashlib.sha256(data).hexdigest(),
                                     "bytes": len(data)})

    (OUT_DIR / "phase4-web-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8", newline=LF)

    digest = hashlib.sha256(bundle.read_bytes()).hexdigest()
    (OUT_DIR / "phase4-web.tgz.sha256").write_text(
        digest + "  phase4-web.tgz" + LF, encoding="utf-8", newline=LF)

    total = sum(m["bytes"] for m in manifest)
    print(f"สร้าง {bundle.name} · {len(manifest)} ไฟล์ · "
          f"เนื้อหารวม {total:,} ไบต์ · archive {bundle.stat().st_size:,} ไบต์")
    print(f"sha256: {digest}")
    print("ตรวจแล้ว: ไม่มีคำว่า supabase ในไฟล์ที่ build ออกมาเลย")
    print("\nไฟล์ในชุด:")
    for m in manifest:
        print(f"  {m['bytes']:>9,}  {m['path']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
