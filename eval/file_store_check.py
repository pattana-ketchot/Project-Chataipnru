"""
ตรวจที่เก็บไฟล์ที่มาแทน Supabase Storage — Phase 4

เหตุที่ต้องมี: นี่คือจุดเดียวในระบบที่รับไฟล์จากภายนอกแล้วเขียนลงดิสก์ของเซิร์ฟเวอร์
ถ้าพลาดคือเขียนทับไฟล์ระบบหรือให้คนนอกอ่านไฟล์นอกโฟลเดอร์ได้

ข้อกำหนดที่ห้ามหลุด
    - ชื่อไฟล์ที่ผู้ใช้ส่งมา **ห้าม** กลายเป็นพาธบนดิสก์ ไม่ว่าจะมี ../ หรืออะไรก็ตาม
    - ตรวจชนิดจากเนื้อไฟล์ ไม่ใช่จากนามสกุลอย่างเดียว
    - ไฟล์ใหญ่เกินและไฟล์ว่างต้องถูกปฏิเสธ
    - อ่านไฟล์ต้องยืนยันอีกครั้งว่าพาธอยู่ใต้โฟลเดอร์ที่กำหนด

ทั้งหมดเป็น offline: เขียนลงโฟลเดอร์ชั่วคราว ไม่แตะ production

    python -m eval.file_store_check
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres@127.0.0.1:55432/course_advisor")
os.environ.setdefault("JWT_SECRET", "local-test-only")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.config import get_settings  # noqa: E402
from app.services import file_store as fs  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64
JPG = b"\xff\xd8\xff" + b"0" * 64
PDF = b"%PDF-1.7\n" + b"0" * 64


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="filestore-check-"))
        settings = get_settings()
        self._old_dir = settings.uploads_dir
        self._old_max = settings.upload_max_bytes
        settings.uploads_dir = str(self.tmp)
        settings.upload_max_bytes = 1024

    def tearDown(self):
        settings = get_settings()
        settings.uploads_dir = self._old_dir
        settings.upload_max_bytes = self._old_max
        shutil.rmtree(self.tmp, ignore_errors=True)


class NameChecks(Base):
    def test_ชื่อที่มีพาธถูกตัดเหลือชื่อฐาน(self):
        self.assertEqual(fs.safe_display_name("../../etc/passwd"), "passwd")
        self.assertEqual(fs.safe_display_name(r"C:\windows\system32\x.png"), "x.png")

    def test_อักขระควบคุมถูกแทนที่(self):
        self.assertNotIn("\n", fs.safe_display_name("a\nb.png"))
        self.assertNotIn("\x00", fs.safe_display_name("a\x00b.png"))

    def test_ชื่อว่างยังได้ชื่อที่ใช้ได้(self):
        self.assertTrue(fs.safe_display_name(""))
        self.assertTrue(fs.safe_display_name("   "))

    def test_ชื่อยาวมากถูกตัด(self):
        self.assertLessEqual(len(fs.safe_display_name("ก" * 500 + ".png")), 120)

    def test_ชื่อบนดิสก์ไม่ได้มาจากชื่อที่ผู้ใช้ส่ง(self):
        """ข้อสำคัญสุด — ชื่อบนดิสก์คือ hash ของเนื้อไฟล์เท่านั้น"""
        stored = fs.save("logo", "../../../evil.png", PNG)
        self.assertNotIn("evil", stored.relative_path)
        self.assertNotIn("..", stored.relative_path)


class TraversalChecks(Base):
    def test_พาธที่ออกนอกโฟลเดอร์ถูกปฏิเสธ(self):
        for bad in ("../outside.png", "logo/../../outside.png", "/etc/passwd",
                    "logo/../../../../etc/passwd"):
            with self.assertRaises(fs.FileRejected, msg=bad):
                fs.resolve_within_root(bad)

    def test_พาธปกติผ่าน(self):
        path = fs.resolve_within_root("logo/ab/abcdef.png")
        self.assertTrue(str(path).startswith(str(self.tmp.resolve())))

    def test_อ่านไฟล์นอกโฟลเดอร์ไม่ได้(self):
        outside = self.tmp.parent / "outside-secret.png"
        outside.write_bytes(PNG)
        try:
            with self.assertRaises(fs.FileRejected):
                fs.open_stored("../outside-secret.png")
        finally:
            outside.unlink(missing_ok=True)

    def test_หมวดไฟล์ที่ไม่รู้จักถูกปฏิเสธ(self):
        with self.assertRaises(fs.FileRejected):
            fs.relative_path_for("อื่น", "a" * 64, ".png")


class TypeChecks(Base):
    def test_รับชนิดที่อนุญาต(self):
        self.assertEqual(fs.check_type("a.png", PNG), "image/png")
        self.assertEqual(fs.check_type("a.jpg", JPG), "image/jpeg")
        self.assertEqual(fs.check_type("a.pdf", PDF), "application/pdf")

    def test_นามสกุลที่ไม่อนุญาตถูกปฏิเสธ(self):
        for name in ("a.exe", "a.js", "a.html", "a.svg", "a.php", "a"):
            with self.assertRaises(fs.FileRejected, msg=name):
                fs.check_type(name, PNG)

    def test_นามสกุลถูกแต่เนื้อไฟล์ไม่ตรงถูกปฏิเสธ(self):
        """ไฟล์ .png ที่ข้างในเป็นสคริปต์ต้องไม่ผ่าน"""
        with self.assertRaises(fs.FileRejected):
            fs.check_type("a.png", b"<?php system($_GET[0]); ?>")

    def test_ตัวพิมพ์ใหญ่ในนามสกุลยังผ่าน(self):
        self.assertEqual(fs.check_type("A.PNG", PNG), "image/png")

    def test_นามสกุลซ้อนใช้ตัวท้ายสุด(self):
        with self.assertRaises(fs.FileRejected):
            fs.check_type("a.png.exe", PNG)


class SizeChecks(Base):
    def test_ไฟล์ว่างถูกปฏิเสธ(self):
        with self.assertRaises(fs.FileRejected):
            fs.check_size(0)

    def test_ไฟล์ใหญ่เกินถูกปฏิเสธ(self):
        with self.assertRaises(fs.FileRejected):
            fs.check_size(get_settings().upload_max_bytes + 1)

    def test_ขนาดพอดีเพดานยังผ่าน(self):
        fs.check_size(get_settings().upload_max_bytes)

    def test_บันทึกไฟล์ใหญ่เกินไม่สำเร็จ(self):
        big = b"\x89PNG\r\n\x1a\n" + b"0" * 4096
        with self.assertRaises(fs.FileRejected):
            fs.save("logo", "big.png", big)


class SaveChecks(Base):
    def test_บันทึกแล้วอ่านกลับได้(self):
        stored = fs.save("logo", "โลโก้.png", PNG)
        path, media = fs.open_stored(stored.relative_path)
        self.assertEqual(path.read_bytes(), PNG)
        self.assertEqual(media, "image/png")

    def test_เก็บชื่อเดิมไว้แสดงผล(self):
        self.assertEqual(fs.save("logo", "โลโก้สาขา.png", PNG).original_name, "โลโก้สาขา.png")

    def test_ไฟล์เนื้อเดียวกันใช้พาธเดียวกัน(self):
        a = fs.save("logo", "one.png", PNG)
        b = fs.save("logo", "two.png", PNG)
        self.assertEqual(a.relative_path, b.relative_path)

    def test_ไฟล์เนื้อต่างกันได้คนละพาธ(self):
        a = fs.save("logo", "a.png", PNG)
        b = fs.save("logo", "b.png", PNG + b"x")
        self.assertNotEqual(a.relative_path, b.relative_path)

    def test_หมวดต่างกันแยกโฟลเดอร์(self):
        self.assertTrue(fs.save("logo", "a.png", PNG).relative_path.startswith("logo/"))
        self.assertTrue(fs.save("news", "a.png", PNG).relative_path.startswith("news/"))

    def test_ไม่ทิ้งไฟล์ชั่วคราวไว้(self):
        fs.save("logo", "a.png", PNG)
        self.assertEqual(list(self.tmp.rglob("*.part")), [])

    def test_ขนาดที่คืนตรงกับไฟล์จริง(self):
        stored = fs.save("knowledge", "a.pdf", PDF)
        self.assertEqual(stored.size, len(PDF))
        self.assertEqual(fs.open_stored(stored.relative_path)[0].stat().st_size, len(PDF))


class CategoryChecks(Base):
    def test_หมวดรูปไม่รับเอกสาร(self):
        for name in ("a.pdf", "a.txt", "a.md", "a.docx"):
            with self.assertRaises(fs.FileRejected, msg=name):
                fs.check_type(name, PDF, "logo")

    def test_หมวดคลังความรู้ไม่รับรูป(self):
        with self.assertRaises(fs.FileRejected):
            fs.check_type("a.png", PNG, "knowledge")

    def test_หมวดคลังความรู้รับเอกสาร(self):
        self.assertEqual(fs.check_type("a.pdf", PDF, "knowledge"), "application/pdf")

    def test_บันทึกข้ามหมวดถูกปฏิเสธ(self):
        with self.assertRaises(fs.FileRejected):
            fs.save("logo", "a.pdf", PDF)
        with self.assertRaises(fs.FileRejected):
            fs.save("knowledge", "a.png", PNG)

    def test_ไฟล์คลังความรู้ถูกทำเครื่องหมายว่าไม่สาธารณะ(self):
        stored = fs.save("knowledge", "a.pdf", PDF)
        self.assertTrue(fs.is_private(stored.relative_path))

    def test_โลโก้กับรูปข่าวเปิดสาธารณะ(self):
        self.assertFalse(fs.is_private(fs.save("logo", "a.png", PNG).relative_path))
        self.assertFalse(fs.is_private(fs.save("news", "a.png", PNG).relative_path))

    def test_พาธที่ไม่มีหมวดถือว่าไม่สาธารณะไม่ได้(self):
        self.assertFalse(fs.is_private(""))
        self.assertFalse(fs.is_private("อื่น/x.png"))


class ConfigChecks(unittest.TestCase):
    def test_ยังไม่ตั้งค่าโฟลเดอร์ต้องล้มอย่างชัดเจน(self):
        settings = get_settings()
        old = settings.uploads_dir
        settings.uploads_dir = ""
        try:
            with self.assertRaises(fs.StorageNotConfigured):
                fs.root()
        finally:
            settings.uploads_dir = old

    def test_ชนิดที่อนุญาตไม่มีไฟล์ที่รันได้(self):
        """กันไม่ให้มีใครเผลอเพิ่มชนิดที่เสิร์ฟแล้วเบราว์เซอร์รันโค้ด"""
        for ext in fs.ALLOWED:
            self.assertNotIn(ext, (".html", ".htm", ".svg", ".js", ".exe", ".sh", ".php"))

    def test_ชนิดที่ตรวจลายเซ็นไม่ได้ต้องไม่อยู่ในหมวดสาธารณะ(self):
        """
        ไฟล์ข้อความไม่มีลายเซ็นให้ตรวจ จึงยืนยันเนื้อไฟล์ไม่ได้
        ชนิดแบบนั้นต้องอยู่เฉพาะหมวดที่ต้องเข้าสู่ระบบก่อนอ่านเท่านั้น
        """
        unverifiable = {ext for ext, (_m, sig) in fs.ALLOWED.items() if not sig}
        for category, types in fs.CATEGORY_TYPES.items():
            if category in fs.PRIVATE_CATEGORIES:
                continue
            self.assertFalse(unverifiable & set(types),
                             f"หมวดสาธารณะ {category} รับชนิดที่ตรวจเนื้อไฟล์ไม่ได้")

    def test_หมวดโลโก้และข่าวรับเฉพาะรูป(self):
        for category in ("logo", "news"):
            for ext in fs.CATEGORY_TYPES[category]:
                self.assertTrue(fs.ALLOWED[ext][0].startswith("image/"),
                                f"{category} รับ {ext} ซึ่งไม่ใช่รูป")

    def test_หมวดเอกสารหลักสูตรรับเฉพาะ_pdf(self):
        self.assertEqual(fs.CATEGORY_TYPES["course-doc"], (".pdf",))

    def test_ทุกชนิดในทุกหมวดอยู่ในรายการกลาง(self):
        for category, types in fs.CATEGORY_TYPES.items():
            for ext in types:
                self.assertIn(ext, fs.ALLOWED, f"{category} อ้าง {ext} ที่ไม่มีในรายการกลาง")

    def test_หมวดที่ต้องล็อกอินมีอยู่จริง(self):
        for category in fs.PRIVATE_CATEGORIES:
            self.assertIn(category, fs.CATEGORIES)


if __name__ == "__main__":
    unittest.main()
