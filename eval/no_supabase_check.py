"""
ตรวจว่าฝั่งเซิร์ฟเวอร์ไม่พึ่ง Supabase แล้ว — Phase 4 ข้อ 8

คู่กับ test/noSupabase.test.mjs ของหน้าเว็บ — ไฟล์นี้ตรวจฝั่ง backend และงานตั้งเวลา

ทำไมการตรวจด้วย hosts entry ไม่พอ
--------------------------------
แผนรุ่นแรกเสนอให้ใส่ `0.0.0.0 supabase.co` ลง /etc/hosts ซึ่ง **พิสูจน์อะไรไม่ได้**
    1. โปรเจกต์จริงอยู่ที่ `<ref>.supabase.co` ซึ่งเป็นคนละชื่อโฮสต์ ไม่ถูกบล็อก
    2. /etc/hosts ไม่รองรับ wildcard จึงครอบ subdomain ไม่ได้เลย
    3. ไม่มีวิธีคืนค่าที่แน่นอน — คอนเทนเนอร์ถูกสร้างใหม่เมื่อไรก็หาย

ของจริงที่พิสูจน์ได้มีสามชั้น
    1. **ซอร์สและ dependency** — ไม่มีการอ้างถึงเลย (ไฟล์นี้)
    2. **ตอนทำงานจริง** — ชุด integration รันผ่านโดย **ไม่มีค่า SUPABASE_* ใด ๆ** ตั้งไว้
       (ดู eval/phase4_integration_check.py)
    3. **ฝั่งเบราว์เซอร์** — ไม่มีคำขอไปโดเมน supabase เลยใน Network tab (ขั้น V ของ deploy)

    python -m eval.no_supabase_check
"""
from __future__ import annotations

import os
import re
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# โฟลเดอร์ที่เป็นโค้ดของระบบหลังย้ายเสร็จ
#
# ไม่รวม webapi/ เพราะเป็นบริการที่กำลังจะเลิกใช้ และยังคงอยู่เพื่อให้ย้อนกลับได้
# ไม่รวม docs/ และ eval/ เพราะเป็นคำอธิบายและชุดทดสอบ ซึ่งพูดถึง Supabase ได้
CODE_DIRS = ("backend", "pipeline", "llm")

# การอ้างถึงที่ยอมรับได้ — สคริปต์ย้ายข้อมูลต้องคุยกับ Supabase โดยธรรมชาติ
MIGRATION_SCRIPTS = {
    "pipeline/web/import_from_supabase.py",
    "pipeline/web/import_accounts.py",
    "pipeline/web/migrate_storage.py",
}

def strip_text(source: str) -> str:
    """
    ตัดคอมเมนต์และ docstring ออก เหลือแต่โค้ดที่ทำงานจริง

    จำเป็นเพราะคำอธิบายที่เล่าว่า "เดิมเคยใช้ Supabase" คือสิ่งที่ **ควรมี**
    การตรวจแบบค้นคำดิบจะจับคำอธิบายเหล่านั้นแล้วล้มทั้งที่ไม่มีอะไรผิด
    """
    import ast
    import io as _io
    import tokenize

    out = []
    try:
        tokens = tokenize.generate_tokens(_io.StringIO(source).readline)
        for kind, text, start, _end, _line in tokens:
            if kind in (tokenize.COMMENT, tokenize.NL):
                continue
            if kind == tokenize.STRING and text.lstrip("rbfuRBFU").startswith(('"""', "'''")):
                continue  # docstring หรือข้อความหลายบรรทัด
            out.append(f"{start[0]}:{text}")
    except tokenize.TokenError:
        return source
    _ = ast  # ใช้เพื่อให้ชัดว่าเราอ่านไฟล์เป็นโค้ด ไม่ใช่ข้อความ
    return "\n".join(out)


def python_files() -> list[Path]:
    out: list[Path] = []
    for folder in CODE_DIRS:
        base = REPO / folder
        if base.exists():
            out.extend(p for p in base.rglob("*.py") if "__pycache__" not in p.parts)
    return out


def hits(pattern: re.Pattern) -> list[str]:
    found = []
    for path in python_files():
        relative = path.relative_to(REPO).as_posix()
        if relative in MIGRATION_SCRIPTS:
            continue
        for entry in strip_text(path.read_text(encoding="utf-8")).split("\n"):
            if pattern.search(entry):
                found.append(f"{relative}:{entry[:90]}")
    return found


class SourceChecks(unittest.TestCase):
    """
    ตรวจ **การเรียกใช้จริง** ไม่ใช่การเอ่ยถึง

    `supabase_user_id` เป็นชื่อคอลัมน์ของเราเอง (migration 006) ไว้แปลงตัวตนตอนย้าย
    จึงไม่ถือเป็นการพึ่ง Supabase
    """

    def test_ไม่มีการ_import_ไลบรารีของ_supabase(self):
        found = hits(re.compile(r"\b(import|from)\b.*\bsupabase\b", re.I))
        self.assertEqual(found, [], "\n".join(found))

    def test_ไม่มีการเรียกเมท็อดของ_client(self):
        found = hits(re.compile(r"supabase\s*\.\s*(from|auth|storage|rpc|functions|table)", re.I))
        self.assertEqual(found, [], "\n".join(found))

    def test_ไม่มี_url_ของ_supabase(self):
        found = hits(re.compile(r"[a-z0-9-]*\.?supabase\.(co|in)", re.I))
        self.assertEqual(found, [], "\n".join(found))

    def test_ไม่มีการอ่านค่าตั้งค่าของ_supabase(self):
        found = hits(re.compile(r"SUPABASE_[A-Z_]+"))
        self.assertEqual(found, [], "\n".join(found))

    def test_ไม่มีการเรียก_edge_function(self):
        found = hits(re.compile(r"functions/v1/"))
        self.assertEqual(found, [], "\n".join(found))

    def test_ไม่มี_dependency_ของ_supabase(self):
        text = (REPO / "backend" / "requirements.txt").read_text(encoding="utf-8")
        self.assertNotIn("supabase", text.lower())

    def test_การตั้งค่าของ_backend_ไม่มีค่าของ_supabase(self):
        code = strip_text((REPO / "backend" / "app" / "core" / "config.py")
                          .read_text(encoding="utf-8"))
        self.assertNotIn("SUPABASE", code.upper())


class ComposeChecks(unittest.TestCase):
    """อ่าน compose ด้วยตัวแปล YAML ไม่ใช่การตัดสตริง ซึ่งพลาดขอบเขตได้ง่าย"""

    @classmethod
    def setUpClass(cls):
        try:
            import yaml
        except ImportError:
            raise unittest.SkipTest("ไม่มี pyyaml — ข้ามการตรวจ compose")
        cls.services = yaml.safe_load(
            (REPO / "docker-compose.prod.yml").read_text(encoding="utf-8"))["services"]

    def env_of(self, service: str) -> str:
        return " ".join(f"{k}={v}" for k, v in
                        (self.services[service].get("environment") or {}).items()).upper()

    def test_backend_ไม่ได้รับค่าของ_supabase(self):
        """ถ้า backend ไม่เคยได้รับค่า มันก็เรียกไม่ได้แม้อยากเรียก"""
        self.assertNotIn("SUPABASE", self.env_of("backend"))

    def test_backend_มีโฟลเดอร์ไฟล์อัปโหลดที่เขียนได้(self):
        volumes = self.services["backend"].get("volumes") or []
        uploads = [v for v in volumes if "/srv/uploads" in v]
        self.assertTrue(uploads, "ไม่มี volume ของไฟล์อัปโหลด")
        self.assertFalse(uploads[0].endswith(":ro"), "โฟลเดอร์อัปโหลดถูก mount แบบอ่านอย่างเดียว")

    def test_เอกสารยังอ่านอย่างเดียวเหมือนเดิม(self):
        volumes = self.services["backend"].get("volumes") or []
        documents = [v for v in volumes if "/srv/documents" in v]
        self.assertTrue(documents[0].endswith(":ro"), "เอกสาร มคอ.2 เขียนได้ ซึ่งไม่ควร")

    def test_webapi_ยังได้รับค่าเดิมไว้ย้อนกลับ(self):
        """
        webapi ยังอยู่เพื่อให้ย้อนกลับได้ — ยังไม่ถอดออกในรอบนี้
        แต่หน้าเว็บใหม่ไม่เรียกมันแล้ว
        """
        self.assertIn("SUPABASE", self.env_of("webapi"),
                      "webapi ถูกถอดค่าไปแล้ว — ย้อนกลับไม่ได้")


class RuntimeEvidenceChecks(unittest.TestCase):
    def test_ชุด_integration_ไม่ตั้งค่า_supabase_เลย(self):
        """
        หลักฐานตอนทำงานจริง — ชุด integration ยิงผ่าน FastAPI ลงฐานข้อมูลจริงทั้งชุด
        โดยไม่มีค่า SUPABASE_* ตั้งไว้เลย ถ้ามีอะไรยังพึ่งอยู่ ชุดนั้นจะล้ม
        """
        text = (REPO / "eval" / "phase4_integration_check.py").read_text(encoding="utf-8")
        # มองหาการ **ตั้งค่า** จริง ไม่ใช่การเอ่ยถึงในชื่อข้อทดสอบหรือคำอธิบาย
        settings = re.findall(r'(?:environ\[|environ\.get\(|getenv\()\s*["\'][^"\']*SUPABASE[^"\']*',
                              text, re.I)
        self.assertEqual(settings, [], f"ชุด integration ตั้งค่า Supabase: {settings}")

    def test_สภาพแวดล้อมตอนรันไม่มีค่าของ_supabase(self):
        leaked = [k for k in os.environ if "SUPABASE" in k.upper()]
        self.assertEqual(leaked, [], f"มีค่าตั้งไว้: {leaked}")


if __name__ == "__main__":
    unittest.main()
