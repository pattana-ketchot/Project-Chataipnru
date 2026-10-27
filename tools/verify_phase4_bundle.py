"""
ทดสอบ bundle ที่จะส่งจริง — ไม่ใช่ไฟล์ต้นฉบับในเครื่อง

    python -m tools.verify_phase4_bundle

ทำไมต้องทดสอบจาก bundle ไม่ใช่จากไฟล์ในเครื่อง
----------------------------------------------
`main.py` ในเครื่องพัฒนา `import crawl_review` แล้ว**ผ่าน** เพราะเครื่องนี้มีไฟล์นั้น
แต่เซิร์ฟเวอร์ไม่มี การทดสอบจากไฟล์ในเครื่องจึงพิสูจน์อะไรไม่ได้เลย

สคริปต์นี้ประกอบ "ต้นไม้ไฟล์เหมือนเซิร์ฟเวอร์หลัง deploy" ขึ้นมาจริง
    1. คัดลอกไฟล์ที่เซิร์ฟเวอร์มีอยู่แล้ว (อ่านรายการจาก --server-files)
    2. ทับด้วยไฟล์จาก bundle
    3. **ไม่ใส่** ไฟล์ที่เซิร์ฟเวอร์ไม่มีและ bundle ไม่ได้ส่ง (crawl_review ฯลฯ)
แล้วจึง import `app.main` จากต้นไม้นั้น และตรวจว่าเส้นทางที่ต้องใช้มีครบ

ถ้าขั้นนี้ผ่าน แปลว่า backend จะขึ้นได้บนเซิร์ฟเวอร์ — ถ้าไม่ผ่าน จะรู้ตอนนี้
ไม่ใช่ตอนที่คอนเทนเนอร์เดิมถูกแทนที่ไปแล้ว
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BUNDLE = REPO / "dist-deploy" / "phase4-source.tar.gz"

# เส้นทางที่ต้องมีหลัง deploy — ชื่อตามที่ FastAPI เห็น (ยังไม่ผ่าน Caddy ที่ตัด /api)
REQUIRED_ROUTES = (
    # Phase 4
    "/site/courses", "/site/courses/{course_id}", "/site/news",
    "/site/external-news", "/site/external-news/{slug}",
    "/site-admin/courses", "/site-admin/news", "/site-admin/knowledge",
    "/site-admin/ai-settings", "/site-admin/users", "/site-admin/sync-news",
    "/auth/login", "/auth/refresh", "/auth/logout", "/auth/me",
    "/auth/password-reset/request", "/auth/password-reset/confirm",
    "/auth/admin/reset-link",
    # อัปโหลดคือ POST /uploads/{category} · เปิดไฟล์คือ GET /uploads/{relative_path}
    # ไม่มีเส้นทาง /uploads เปล่า ๆ
    "/uploads/{category}", "/uploads/{relative_path}", "/extract-file",
    # careers (เลือกรวมในรอบนี้)
    "/career-lists",
    # ของเดิมที่ต้องไม่หาย
    "/chat-web", "/compare-courses", "/recommend-major", "/health",
)

# เส้นทางที่ **ต้องไม่มี** เพราะเลือก main.py ฉบับ Phase 4-only
FORBIDDEN_PREFIXES = ("/crawl-review", "/crawl_review")


def build_tree(dest: Path, server_files: Path) -> tuple[int, int]:
    """ประกอบต้นไม้ไฟล์ให้เหมือนเซิร์ฟเวอร์หลัง deploy"""
    wanted = set()
    for line in server_files.read_text(encoding="utf-8").splitlines():
        if line.strip():
            wanted.add(line.split(" ", 1)[1].strip())

    copied = 0
    for rel in sorted(wanted):
        src = REPO / rel
        if not src.is_file():
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
        copied += 1

    with tarfile.open(BUNDLE) as tar:
        names = [n for n in tar.getnames() if not n.endswith("/")]
        tar.extractall(dest)
    return copied, len(names)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

    parser = argparse.ArgumentParser()
    parser.add_argument("--server-files", required=True,
                        help="ไฟล์รายการที่เซิร์ฟเวอร์มี (ผลจาก hashtree.py)")
    args = parser.parse_args()

    if not BUNDLE.is_file():
        raise SystemExit(f"หยุด: ไม่มี {BUNDLE} — รัน tools.make_phase4_bundle ก่อน")

    with tempfile.TemporaryDirectory(prefix="phase4-verify-") as tmp:
        root = Path(tmp)
        copied, from_bundle = build_tree(root, Path(args.server_files))
        print(f"ประกอบต้นไม้จำลองเซิร์ฟเวอร์: จากเซิร์ฟเวอร์ {copied} ไฟล์ · "
              f"ทับด้วย bundle {from_bundle} ไฟล์")

        # ยืนยันว่าไฟล์ที่ไม่ควรมี ไม่มีจริง
        ghosts = [p for p in ("backend/app/api/routes/crawl_review.py",
                              "backend/app/services/crawl_review.py",
                              "backend/app/services/staging_store.py",
                              "backend/app/schemas/crawl_review.py")
                  if (root / p).exists()]
        if ghosts:
            print(f"ไม่ผ่าน: ต้นไม้จำลองมีไฟล์ที่เซิร์ฟเวอร์ไม่มี: {ghosts}")
            return 1
        print("ยืนยัน: ต้นไม้จำลองไม่มีไฟล์ของ crawl review เลย (เหมือนเซิร์ฟเวอร์)")

        probe = root / "_probe.py"
        # ใช้ app.openapi() เป็นแหล่งความจริง ไม่ใช่การเดินดู app.routes
        #
        # FastAPI รุ่นใหม่ห่อ router ที่ include เข้ามาเป็นอ็อบเจกต์ _IncludedRouter
        # ซึ่ง **ไม่มี .path** การเดิน app.routes จึงเห็นแต่ /docs /openapi.json /health
        # แล้วสรุปผิดว่า router ไม่ได้ลงทะเบียน · openapi() คือสิ่งเดียวกับที่
        # /api/openapi.json บนเซิร์ฟเวอร์คืนออกมา จึงตรงกับที่ขั้น B ตรวจ
        probe.write_text(
            "import json, sys\n"
            "sys.path.insert(0, 'backend')\n"
            "sys.path.insert(0, '.')\n"
            "import app.main as m\n"
            "paths = sorted(m.app.openapi()['paths'])\n"
            "print('@@ROUTES@@' + json.dumps(paths, ensure_ascii=False))\n",
            encoding="utf-8")

        env = dict(os.environ)
        # ค่าหลอกสำหรับการ import เท่านั้น ไม่ได้ต่อฐานข้อมูลหรือส่งออกไปไหน
        env.update({
            "JWT_SECRET": "x" * 48,
            "DATABASE_URL": "postgresql+psycopg://u:p@127.0.0.1:1/none",
            "PYTHONIOENCODING": "utf-8",
        })
        for name in list(env):
            if "SUPABASE" in name.upper():
                env.pop(name)

        result = subprocess.run([sys.executable, "-I", str(probe)], cwd=root,
                                capture_output=True, text=True,
                                encoding="utf-8", errors="replace", env=env)

        marker = next((l for l in (result.stdout or "").splitlines()
                       if l.startswith("@@ROUTES@@")), None)
        if marker is None:
            print("ไม่ผ่าน: import app.main จากต้นไม้จำลองไม่สำเร็จ")
            print("--- stderr ---")
            print((result.stderr or "")[-2500:])
            return 1

        import json
        routes = json.loads(marker[len("@@ROUTES@@"):])
        print(f"import app.main สำเร็จ · FastAPI ลงทะเบียน {len(routes)} เส้นทาง")

        missing = [r for r in REQUIRED_ROUTES if r not in routes]
        forbidden = [r for r in routes if r.startswith(FORBIDDEN_PREFIXES)]

        print("\nเส้นทางที่ต้องมี:",
              "ครบทั้ง %d รายการ" % len(REQUIRED_ROUTES) if not missing else f"ขาด {missing}")
        print("เส้นทางที่ต้องไม่มี (crawl review):",
              "ไม่มีเลย ถูกต้อง" if not forbidden else f"พบ {forbidden}")

        if missing or forbidden:
            print("\nเส้นทางทั้งหมดที่ได้:")
            for r in routes:
                print("  ", r)
            return 1

        print("\nผ่าน — backend จะขึ้นได้บนเซิร์ฟเวอร์ และมีเส้นทางที่ต้องใช้ครบ")
        return 0


if __name__ == "__main__":
    sys.exit(main())
