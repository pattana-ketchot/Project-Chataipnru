"""
รูปที่ผู้ดูแลอัปโหลดเองต้องผ่านด่านจริง — ชนิดไฟล์ ขนาด และชื่อบนดิสก์

    cd backend && python tests/test_upload_image.py

ไม่ต่อฐานข้อมูล ไม่เรียกโมเดล — เขียนไฟล์ลงโฟลเดอร์ชั่วคราวแล้วลบทิ้ง

ทำไมต้องมีชุดนี้
---------------
ตั้งแต่ย้ายจาก Supabase Storage มาเก็บไฟล์เอง (Phase 4) ยังไม่มีชุดทดสอบของ
`file_store` เลย ทั้งที่เป็นเส้นทางที่รับไฟล์จากภายนอกเข้ามาเขียนลงดิสก์ · สามข้อ
ที่พังแล้วจะไม่มีใครเห็นจนกว่าจะสาย

1. **ตรวจชนิดจากนามสกุลอย่างเดียวไม่พอ** นามสกุลเป็นสิ่งที่ผู้ส่งตั้งเอง ไฟล์ชื่อ
   `.png` ที่ข้างในเป็นสคริปต์จึงผ่านด่านนามสกุลได้ง่าย ต้องดูลายเซ็นไบต์แรกด้วย
2. **ชื่อไฟล์ที่ผู้ใช้ส่งมาต้องไม่กลายเป็นพาธบนดิสก์** ไม่ว่าจะส่ง `../../` มาแค่ไหน
3. **ไฟล์เดิมต้องไม่ถูกทับ** รูปที่หน้าเว็บอ้างอยู่ต้องไม่เปลี่ยนเพราะมีคนอัปโหลด
   ไฟล์ชื่อเดียวกันทับเข้ามา
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_TEMP = tempfile.TemporaryDirectory()
os.environ["UPLOADS_DIR"] = _TEMP.name
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://unused:unused@127.0.0.1:1/unused")
os.environ.setdefault("JWT_SECRET", "ชุดทดสอบไม่ได้ออก token")

from app.core.config import get_settings  # noqa: E402
from app.services import file_store  # noqa: E402

get_settings.cache_clear()

# ไฟล์จริงขนาดเล็กของแต่ละชนิด — ลายเซ็นไบต์แรกคือของจริง ไม่ใช่ชื่อที่ตั้งเอง
PNG = (b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + b"\x00" * 64)
JPG = (b"\xff\xd8\xff\xe0" + b"\x00\x10JFIF\x00" + b"\x00" * 64)
WEBP = (b"RIFF" + b"\x24\x00\x00\x00" + b"WEBPVP8 " + b"\x00" * 64)


class UploadImageTests(unittest.TestCase):
    def test_รับรูปสามชนิดที่หน้าแอดมินบอกไว้(self):
        for name, data, media in (("โลโก้สาขา.png", PNG, "image/png"),
                                  ("photo.jpg", JPG, "image/jpeg"),
                                  ("cover.webp", WEBP, "image/webp")):
            stored = file_store.save("logo", name, data)
            self.assertEqual(stored.media_type, media, name)
            self.assertTrue(file_store.resolve_within_root(stored.relative_path).is_file())

    def test_นามสกุลรูปแต่เนื้อไม่ใช่รูป_ต้องไม่ผ่าน(self):
        """ด่านที่นามสกุลอย่างเดียวจับไม่ได้ — ไฟล์ตั้งชื่อ .png แต่ข้างในเป็นสคริปต์"""
        with self.assertRaises(file_store.FileRejected) as caught:
            file_store.save("logo", "evil.png", b"<?php system($_GET[0]); ?>")
        self.assertIn("เนื้อไฟล์", str(caught.exception))

    def test_ชนิดที่หมวดรูปไม่รับ_ต้องไม่ผ่าน(self):
        """หมวดของรูปต้องไม่รับเอกสาร แม้เนื้อไฟล์จะตรงกับนามสกุลก็ตาม"""
        with self.assertRaises(file_store.FileRejected):
            file_store.save("logo", "manual.pdf", b"%PDF-1.4\n" + b"\x00" * 32)
        with self.assertRaises(file_store.FileRejected):
            file_store.save("logo", "note.txt", b"plain text")

    def test_เพดานขนาดของหมวดรูปคือ_5_MB(self):
        five = 5 * 1024 * 1024
        self.assertEqual(file_store.max_bytes_for("logo"), five)
        ok = PNG + b"\x00" * (five - len(PNG))
        self.assertEqual(len(ok), five)
        self.assertEqual(file_store.save("logo", "พอดีเพดาน.png", ok).size, five)

        with self.assertRaises(file_store.FileRejected) as caught:
            file_store.save("logo", "ใหญ่เกิน.png", PNG + b"\x00" * five)
        # ข้อความต้องบอกเพดานจริงของหมวดนั้น ไม่ใช่เพดานของทั้งระบบ
        self.assertIn("5 MB", str(caught.exception))

    def test_หมวดอื่นยังใช้เพดานของทั้งระบบตามเดิม(self):
        """คู่ควบคุม — การใส่เพดานให้หมวดรูปต้องไม่ไปบีบหมวดเอกสารด้วย"""
        self.assertEqual(file_store.max_bytes_for("course-doc"),
                         get_settings().upload_max_bytes)
        self.assertEqual(file_store.max_bytes_for("knowledge"),
                         get_settings().upload_max_bytes)

    def test_ไฟล์ว่างไม่ผ่าน(self):
        with self.assertRaises(file_store.FileRejected):
            file_store.save("logo", "empty.png", b"")

    def test_ชื่อไฟล์ที่ผู้ใช้ส่งมาไม่กลายเป็นพาธบนดิสก์(self):
        stored = file_store.save("logo", "../../../etc/passwd.png", PNG)
        self.assertNotIn("..", stored.relative_path)
        self.assertTrue(stored.relative_path.startswith("logo/"))
        path = file_store.resolve_within_root(stored.relative_path)
        self.assertTrue(path.is_file())
        self.assertTrue(str(path).startswith(str(file_store.root())))

    def test_อัปโหลดชื่อซ้ำแต่เนื้อต่าง_ต้องไม่ทับไฟล์เดิม(self):
        """รูปที่หน้าเว็บอ้างอยู่ต้องไม่เปลี่ยนเพราะมีคนอัปโหลดชื่อเดียวกันทับ"""
        first = file_store.save("logo", "cover.png", PNG + "หนึ่ง".encode())
        second = file_store.save("logo", "cover.png", PNG + "สอง".encode())
        self.assertNotEqual(first.relative_path, second.relative_path)
        self.assertEqual(file_store.resolve_within_root(first.relative_path).read_bytes(),
                         PNG + "หนึ่ง".encode())

    def test_เนื้อไฟล์เหมือนกันทุกไบต์ใช้ไฟล์เดียวกัน(self):
        a = file_store.save("logo", "a.png", PNG + b"x")
        b = file_store.save("logo", "b.png", PNG + b"x")
        self.assertEqual(a.relative_path, b.relative_path)

    def test_เปิดไฟล์ที่เก็บไว้ได้ด้วย_media_type_ที่ถูกต้อง(self):
        stored = file_store.save("logo", "cover.webp", WEBP)
        path, media_type = file_store.open_stored(stored.relative_path)
        self.assertEqual(media_type, "image/webp")
        self.assertEqual(path.read_bytes(), WEBP)

    def test_หมวดรูปเปิดสาธารณะ_ไม่ต้องเข้าสู่ระบบก่อนดู(self):
        """รูปประจำสาขาแสดงบนหน้าเว็บสาธารณะ ถ้าต้องล็อกอินก่อนดู รูปจะไม่ขึ้น"""
        stored = file_store.save("logo", "cover.png", PNG)
        self.assertFalse(file_store.is_private(stored.relative_path))


if __name__ == "__main__":
    try:
        unittest.main(verbosity=2, exit=False)
    finally:
        _TEMP.cleanup()
