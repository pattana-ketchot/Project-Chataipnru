# อัปโหลดรูปประจำสาขาจากหน้าแอดมิน — diff · readiness · แผน deploy

**29 ต.ค. 2569** · ยังไม่ merge ยังไม่ deploy · เขียนไว้ให้ตรวจก่อนตัดสินใจ

| | |
|---|---|
| backend | `course-advisor-system` · commit **`1c4b510`** บน `feature/public-model-choice` |
| หน้าเว็บ | `LastProject` · commit **`70dbdd6`** บน `prep-step8` |
| ไฟล์ที่แตะ | `backend/app/services/file_store.py` · `backend/tests/test_upload_image.py` (ใหม่) · `src/pages/Admin/CourseForm.jsx` |
| migration | **ไม่มี** |
| ค่าตั้งค่าที่ต้องเพิ่ม | **ไม่มี** — `UPLOADS_DIR=/srv/uploads` ตั้งไว้บน production อยู่แล้ว |
| งานค้าง `AiSettings.jsx` | ไม่ถูกแตะ และแผน deploy ข้อ 7 กันไม่ให้ติดไปด้วย |

---

## 1. ตรวจระบบอัปโหลดเดิมก่อน — **มีอยู่แล้ว และใช้ร่วมทั้งหมด**

`POST /api/uploads/{category}` (`backend/app/api/routes/uploads.py`) กับ
`backend/app/services/file_store.py` ใช้งานจริงบน production อยู่แล้ว — ตรวจเมื่อ
29 ต.ค. 2569 พบไฟล์ 105 ไฟล์ รวม 107 MB ในหมวด `logo` และ `course-doc`

หน้าเว็บก็มีตัวเรียกอยู่แล้วที่ `src/lib/courseStorage.js` — `uploadFacultyPhoto`
(รูปคณาจารย์) · `uploadCourseDocument` (เอกสารแนบ) · และ **`uploadCourseLogo` ที่เขียนไว้
แล้วแต่ยังไม่เคยถูกเรียก** · สิ่งที่ขาดคือปุ่มในหน้าแอดมินเท่านั้น

| ข้อที่สั่ง | ของเดิมทำอยู่แล้ว |
|---|---|
| ให้อัปโหลดได้เฉพาะผู้ดูแล | `Depends(require_staff)` — ต้องเป็น `admin`/`editor` **และ** สถานะ `approved` |
| ตรวจชนิดไฟล์จริงฝั่ง backend | `check_type()` ดู **ลายเซ็นไบต์แรก** ไม่ใช่นามสกุล |
| ระบบสร้างชื่อไฟล์ไม่ซ้ำ | ชื่อบนดิสก์ = `sha256` ของเนื้อไฟล์ ชื่อที่ผู้ใช้ส่งมาไม่เคยกลายเป็นพาธ |
| ไม่ลบหรือทับรูปเดิม | ไฟล์คนละเนื้อ = คนละชื่อ · `removeCourseFile()` เป็น no-op โดยตั้งใจ |
| เก็บไฟล์ถาวร | bind mount `~/course-advisor-system/uploads → /srv/uploads` |

**จึงไม่ได้สร้างระบบอัปโหลดใหม่** ที่เพิ่มมีสองอย่างเท่านั้น

1. **หน้าเว็บ** — ปุ่มเลือกรูป ตัวอย่างรูป และการเติม URL ให้ช่องเดิมอัตโนมัติ
2. **backend** — เพดาน 5 MB ของหมวดรูป (ของเดิมใช้เพดานรวม 10 MB) และชุดทดสอบของ
   `file_store` ซึ่งเดิม**ไม่มีเลย** ทั้งที่เป็นเส้นทางที่รับไฟล์จากภายนอกมาเขียนลงดิสก์

---

## 2. readiness — ห้าข้อที่สั่งให้ระบุ

### 2.1 สิทธิ์อัปโหลด

| | |
|---|---|
| ด่าน | `POST /uploads/{category}` ผูก `Depends(require_staff)` ไว้ที่เส้นทาง |
| เงื่อนไข | `can_access_admin(role, status)` = role อยู่ใน (`admin`, `editor`) **และ** status = `approved` |
| ไม่ส่ง token | **401** `missing bearer token` (วัดแล้ว) |
| token ปลอม | **401** `invalid token` (วัดแล้ว) |
| การอ่านรูป | เปิดสาธารณะโดยตั้งใจ เพราะรูปแสดงบนหน้าเว็บที่ใครก็เข้าได้ — หมวด `knowledge` เท่านั้นที่ต้องเข้าสู่ระบบก่อนอ่าน และไม่เกี่ยวกับงานนี้ |

หน้าเว็บซ่อนปุ่มให้ผู้ที่ไม่ใช่ผู้ดูแลอยู่แล้ว แต่**การซ่อนไม่ใช่ด่าน** — ด่านจริงอยู่ที่ backend
และวัดด้วยการยิงตรงโดยไม่ผ่านหน้าเว็บ

### 2.2 ตรวจชนิดไฟล์จริง (ไม่ใช่ตามนามสกุล)

`file_store.check_type()` ตรวจสามชั้น ต้องผ่านครบ

1. หมวดนี้รับนามสกุลนี้ไหม (`logo` รับ `.png .jpg .jpeg .webp .gif`)
2. นามสกุลอยู่ในรายการที่ระบบรู้จักไหม
3. **ลายเซ็นไบต์แรกตรงกับชนิดนั้นไหม** — `\x89PNG\r\n\x1a\n` · `\xff\xd8\xff` · `RIFF`

วัดแล้ว: ไฟล์ชื่อ `evil.png` ที่ข้างในเป็น `<?php system($_GET[0]); ?>` → **400
`เนื้อไฟล์ไม่ตรงกับนามสกุล`** · ไฟล์ PDF ในหมวดรูป → **400 บอกว่าหมวดนี้รับเฉพาะรูป**

> ปุ่มในหน้าแอดมินรับเฉพาะ JPG/PNG/WebP ตามที่สั่ง ส่วนหมวด `logo` ของ backend ยังรับ
> `.gif` ตามเดิม — ไม่ได้ตัดออกเพราะเป็นความสามารถเดิมที่รูปคณาจารย์ใช้ร่วมอยู่
> การตัดคือการเปลี่ยนพฤติกรรมของงานอื่นโดยไม่มีใครขอ

### 2.3 เพดาน 5 MB

* เดิมมีเพดานเดียวทั้งระบบคือ `UPLOAD_MAX_BYTES` = **10 MB** (ตั้งไว้ใน env ของ production)
* เพิ่ม `CATEGORY_MAX_BYTES = {"logo": 5 MB}` · `max_bytes_for()` คืน **ค่าที่แคบกว่าเสมอ**
  (`min(ระบบ, หมวด)`) เพดานของหมวดจึงไม่มีทางกว้างกว่าเพดานระบบ
* หน้าเว็บตรวจก่อนส่งด้วย เพื่อบอกทันทีโดยไม่ต้องรออัปโหลดจบ — **แต่ด่านจริงอยู่ที่ backend**
* วัดแล้ว: ไฟล์ 6 MB → **400 `ไฟล์ใหญ่เกิน 5 MB`** · ไฟล์ขนาด 5 MB พอดี → ผ่าน
* คู่ควบคุมในชุดทดสอบ: `course-doc` และ `knowledge` **ยังใช้เพดาน 10 MB เท่าเดิม**

> **ผลข้างเคียงที่ต้องรู้**: หมวด `logo` ใช้ร่วมกับ**รูปคณาจารย์** เพดานของรูปคณาจารย์จึง
> ลดจาก 10 MB เหลือ 5 MB ไปด้วย · ถ้าไม่ต้องการ แยกหมวดใหม่ให้รูปประจำสาขาได้ แต่
> ต้องแก้ทั้งสองฝั่งและไม่อยู่ในขอบเขตที่สั่งรอบนี้

### 2.4 ที่เก็บไฟล์ถาวร

| | |
|---|---|
| ในคอนเทนเนอร์ | `UPLOADS_DIR=/srv/uploads` (อ่านจาก env ของคอนเทนเนอร์ที่รันอยู่จริง) |
| บนเครื่องจริง | bind mount `/home/ubuntu/course-advisor-system/uploads` |
| เหตุที่ไม่หายตอน restart/deploy | ไฟล์อยู่**นอกอิมเมจ** การสร้างอิมเมจใหม่หรือ `up -d` จึงไม่แตะ |
| ของที่มีอยู่แล้ว | 105 ไฟล์ · 107 MB (หมวด `logo`, `course-doc`) |
| ถ้าไม่ได้ตั้ง `UPLOADS_DIR` | เส้นทางอัปโหลดตอบ **503 พร้อมข้อความว่ายังไม่ได้ตั้งค่าที่เก็บไฟล์** ไม่ใช่เขียนลงที่ชั่วคราวเงียบ ๆ |

### 2.5 รูปเดิมไม่เปลี่ยนจนกว่าจะบันทึกสำเร็จ

สองชั้นที่ทำให้จริง

1. **การอัปโหลดไม่แตะข้อมูลหลักสูตร** — `POST /uploads/logo` แค่เขียนไฟล์ใหม่แล้วคืน URL
   ตัวแฮนเดิลเลอร์ในหน้าเว็บเอา URL ไปใส่ `form.logo` ซึ่งเป็น **state ของฟอร์ม**
   `logo_url` ของหลักสูตรเปลี่ยนตอนกด "บันทึก" เท่านั้น
2. **ไฟล์เดิมไม่ถูกทับ** — ชื่อไฟล์มาจาก hash ของเนื้อไฟล์ ไฟล์คนละเนื้อจึงคนละชื่อเสมอ
   และระบบไม่ลบไฟล์เก่าทิ้ง รูปที่หน้าอื่นอ้างอยู่จึงไม่หาย

วัดจริงที่หน้าแอดมิน (ฟอร์ม `/admin/courses/create` ต่อกับ backend บนฐานทดสอบ)

```
เลือกรูปที่ 1 (PNG)      -> URL = /api/uploads/logo/f5/f55bad…png · ตัวอย่างรูปโหลดขึ้น
เลือกรูปที่ 2 (JPG) ทับ   -> URL = /api/uploads/logo/c8/c8e4da…jpg  · เปลี่ยนได้ก่อนบันทึก
เลือก PDF                -> URL เดิมไม่เปลี่ยน · ตัวอย่างรูปเดิมยังอยู่ · ขึ้นข้อความว่ารับเฉพาะ JPG/PNG/WebP
เลือกไฟล์ 6 MB           -> URL เดิมไม่เปลี่ยน · ตัวอย่างรูปเดิมยังอยู่ · ขึ้นข้อความว่าเกินเพดาน 5 MB
```

ทั้งสองกรณีที่ไม่ผ่าน ค่าที่จะถูกบันทึก (`form.logo`) **ไม่ถูกแตะเลย** (ยืนยันด้วยการอ่านค่า
ช่อง URL ก่อนและหลัง) และไม่มีคำขอใดถูกส่งไป backend

---

## 3. ผลทดสอบ (ของรอบที่รันไปแล้ว ไม่ได้รันซ้ำ)

ฐาน `course_advisor_test` · backend ในเครื่องที่ `127.0.0.1:8099` · `UPLOADS_DIR` ชี้
โฟลเดอร์ชั่วคราว · token ของผู้ดูแลทดสอบ (`switch-check@test.local` · admin · approved)

| ชุด | ผล |
|---|---|
| `backend/tests/test_upload_image.py` (ใหม่ 11 ข้อ · ดูข้อ 9.1 เรื่อง exit code) | **ผ่าน 11 / 11** |
| ยิงผ่าน HTTP จริง 20 จุดตรวจ | **ผ่าน 20 / 20** |
| ผ่านหน้าแอดมินจริงในเบราว์เซอร์ | ผ่านทุกข้อในข้อ 2.5 |

จุดที่ยิงผ่าน HTTP จริง

```
POST /uploads/logo (PNG / JPG / WebP)  -> 201 · url /api/uploads/logo/<hash>.<ext>
GET  รูปทั้งสาม (ไม่ต้องเข้าสู่ระบบ)      -> 200 · ไบต์ตรงกับที่อัปโหลดทุกไฟล์ · content-type image/*
POST .png ที่ข้างในเป็นสคริปต์          -> 400 เนื้อไฟล์ไม่ตรงกับนามสกุล
POST รูป > 5 MB                        -> 400 ไฟล์ใหญ่เกิน 5 MB
POST .pdf ในหมวดรูป                    -> 400 หมวดนี้รับเฉพาะ .gif .jpeg .jpg .png .webp
POST ไม่มี token / token ปลอม           -> 401 ทั้งสองกรณี
POST เนื้อไฟล์เดิมซ้ำ                    -> 201 · url เดิม (ไม่สร้างไฟล์ใหม่ ไม่ทับ)
ชื่อไฟล์ไทย "โลโก้ทดสอบ.png"              -> ไม่ปรากฏในพาธบนดิสก์เลย
```

**ไม่ได้ทดสอบบน production และไม่ได้แตะไฟล์ใน production** — ของจริงรอหลัง deploy

---

## 4. diff — backend (`1c4b510`)

```diff
diff --git a/backend/app/services/file_store.py b/backend/app/services/file_store.py
index 4ed9988..d69921c 100644
--- a/backend/app/services/file_store.py
+++ b/backend/app/services/file_store.py
@@ -62,6 +62,15 @@ CATEGORY_TYPES: dict[str, tuple[str, ...]] = {
 
 CATEGORIES = tuple(CATEGORY_TYPES)
 
+# เพดานขนาดของบางหมวด — แคบกว่า UPLOAD_MAX_BYTES ของทั้งระบบเท่านั้น ไม่เคยกว้างกว่า
+#
+# รูปที่แสดงบนหน้าเว็บสาธารณะ (โลโก้หลักสูตร รูปประจำสาขา รูปคณาจารย์) ไม่ควรเกิน
+# ไม่กี่เมกะไบต์ เพราะผู้ใช้ปลายทางต้องโหลดทุกครั้งที่เปิดหน้า · เอกสารแนบกับไฟล์
+# คลังความรู้ยังใช้เพดานของทั้งระบบตามเดิม เพราะเป็นไฟล์ที่ผู้ใช้เลือกจะดาวน์โหลดเอง
+CATEGORY_MAX_BYTES: dict[str, int] = {
+    "logo": 5 * 1024 * 1024,
+}
+
 # หมวดที่ต้องเข้าสู่ระบบก่อนอ่าน
 #
 # ของเดิม bucket `knowledge-files` เป็นแบบ private และใช้ signed URL
@@ -137,8 +146,14 @@ def check_type(name: str, head: bytes, category: str | None = None) -> str:
     return media_type
 
 
-def check_size(size: int) -> None:
+def max_bytes_for(category: str | None = None) -> int:
+    """เพดานขนาดของหมวดนี้ — หมวดที่มีเพดานของตัวเองใช้ค่าที่แคบกว่าเสมอ"""
     limit = get_settings().upload_max_bytes
+    return min(limit, CATEGORY_MAX_BYTES.get(category or "", limit))
+
+
+def check_size(size: int, category: str | None = None) -> None:
+    limit = max_bytes_for(category)
     if size <= 0:
         raise FileRejected("ไฟล์ว่าง")
     if size > limit:
@@ -178,7 +193,7 @@ def save(category: str, original_name: str, data: bytes) -> StoredFile:
     ไฟล์เดิมที่เนื้อเหมือนกันทุกไบต์จะใช้ไฟล์เดียวกัน (ชื่อมาจาก hash)
     จึงไม่มีไฟล์ซ้ำและการอัปโหลดซ้ำไม่ทำให้ของเดิมเสีย
     """
-    check_size(len(data))
+    check_size(len(data), category)
     media_type = check_type(original_name, data[:16], category)
     digest = hashlib.sha256(data).hexdigest()
     relative = relative_path_for(category, digest, extension_of(original_name))
diff --git a/backend/tests/test_upload_image.py b/backend/tests/test_upload_image.py
new file mode 100644
index 0000000..97bf086
--- /dev/null
+++ b/backend/tests/test_upload_image.py
@@ -0,0 +1,127 @@
+"""
+รูปที่ผู้ดูแลอัปโหลดเองต้องผ่านด่านจริง — ชนิดไฟล์ ขนาด และชื่อบนดิสก์
+
+    cd backend && python tests/test_upload_image.py
+
+ไม่ต่อฐานข้อมูล ไม่เรียกโมเดล — เขียนไฟล์ลงโฟลเดอร์ชั่วคราวแล้วลบทิ้ง
+
+ทำไมต้องมีชุดนี้
+---------------
+ตั้งแต่ย้ายจาก Supabase Storage มาเก็บไฟล์เอง (Phase 4) ยังไม่มีชุดทดสอบของ
+`file_store` เลย ทั้งที่เป็นเส้นทางที่รับไฟล์จากภายนอกเข้ามาเขียนลงดิสก์ · สามข้อ
+ที่พังแล้วจะไม่มีใครเห็นจนกว่าจะสาย
+
+1. **ตรวจชนิดจากนามสกุลอย่างเดียวไม่พอ** นามสกุลเป็นสิ่งที่ผู้ส่งตั้งเอง ไฟล์ชื่อ
+   `.png` ที่ข้างในเป็นสคริปต์จึงผ่านด่านนามสกุลได้ง่าย ต้องดูลายเซ็นไบต์แรกด้วย
+2. **ชื่อไฟล์ที่ผู้ใช้ส่งมาต้องไม่กลายเป็นพาธบนดิสก์** ไม่ว่าจะส่ง `../../` มาแค่ไหน
+3. **ไฟล์เดิมต้องไม่ถูกทับ** รูปที่หน้าเว็บอ้างอยู่ต้องไม่เปลี่ยนเพราะมีคนอัปโหลด
+   ไฟล์ชื่อเดียวกันทับเข้ามา
+"""
+import os
+import sys
+import tempfile
+import unittest
+from pathlib import Path
+
+sys.stdout.reconfigure(encoding="utf-8", errors="replace")
+sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
+
+_TEMP = tempfile.TemporaryDirectory()
+os.environ["UPLOADS_DIR"] = _TEMP.name
+os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://unused:unused@127.0.0.1:1/unused")
+os.environ.setdefault("JWT_SECRET", "ชุดทดสอบไม่ได้ออก token")
+
+from app.core.config import get_settings  # noqa: E402
+from app.services import file_store  # noqa: E402
+
+get_settings.cache_clear()
+
+# ไฟล์จริงขนาดเล็กของแต่ละชนิด — ลายเซ็นไบต์แรกคือของจริง ไม่ใช่ชื่อที่ตั้งเอง
+PNG = (b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + b"\x00" * 64)
+JPG = (b"\xff\xd8\xff\xe0" + b"\x00\x10JFIF\x00" + b"\x00" * 64)
+WEBP = (b"RIFF" + b"\x24\x00\x00\x00" + b"WEBPVP8 " + b"\x00" * 64)
+
+
+class UploadImageTests(unittest.TestCase):
+    def test_รับรูปสามชนิดที่หน้าแอดมินบอกไว้(self):
+        for name, data, media in (("โลโก้สาขา.png", PNG, "image/png"),
+                                  ("photo.jpg", JPG, "image/jpeg"),
+                                  ("cover.webp", WEBP, "image/webp")):
+            stored = file_store.save("logo", name, data)
+            self.assertEqual(stored.media_type, media, name)
+            self.assertTrue(file_store.resolve_within_root(stored.relative_path).is_file())
+
+    def test_นามสกุลรูปแต่เนื้อไม่ใช่รูป_ต้องไม่ผ่าน(self):
+        """ด่านที่นามสกุลอย่างเดียวจับไม่ได้ — ไฟล์ตั้งชื่อ .png แต่ข้างในเป็นสคริปต์"""
+        with self.assertRaises(file_store.FileRejected) as caught:
+            file_store.save("logo", "evil.png", b"<?php system($_GET[0]); ?>")
+        self.assertIn("เนื้อไฟล์", str(caught.exception))
+
+    def test_ชนิดที่หมวดรูปไม่รับ_ต้องไม่ผ่าน(self):
+        """หมวดของรูปต้องไม่รับเอกสาร แม้เนื้อไฟล์จะตรงกับนามสกุลก็ตาม"""
+        with self.assertRaises(file_store.FileRejected):
+            file_store.save("logo", "manual.pdf", b"%PDF-1.4\n" + b"\x00" * 32)
+        with self.assertRaises(file_store.FileRejected):
+            file_store.save("logo", "note.txt", b"plain text")
+
+    def test_เพดานขนาดของหมวดรูปคือ_5_MB(self):
+        five = 5 * 1024 * 1024
+        self.assertEqual(file_store.max_bytes_for("logo"), five)
+        ok = PNG + b"\x00" * (five - len(PNG))
+        self.assertEqual(len(ok), five)
+        self.assertEqual(file_store.save("logo", "พอดีเพดาน.png", ok).size, five)
+
+        with self.assertRaises(file_store.FileRejected) as caught:
+            file_store.save("logo", "ใหญ่เกิน.png", PNG + b"\x00" * five)
+        # ข้อความต้องบอกเพดานจริงของหมวดนั้น ไม่ใช่เพดานของทั้งระบบ
+        self.assertIn("5 MB", str(caught.exception))
+
+    def test_หมวดอื่นยังใช้เพดานของทั้งระบบตามเดิม(self):
+        """คู่ควบคุม — การใส่เพดานให้หมวดรูปต้องไม่ไปบีบหมวดเอกสารด้วย"""
+        self.assertEqual(file_store.max_bytes_for("course-doc"),
+                         get_settings().upload_max_bytes)
+        self.assertEqual(file_store.max_bytes_for("knowledge"),
+                         get_settings().upload_max_bytes)
+
+    def test_ไฟล์ว่างไม่ผ่าน(self):
+        with self.assertRaises(file_store.FileRejected):
+            file_store.save("logo", "empty.png", b"")
+
+    def test_ชื่อไฟล์ที่ผู้ใช้ส่งมาไม่กลายเป็นพาธบนดิสก์(self):
+        stored = file_store.save("logo", "../../../etc/passwd.png", PNG)
+        self.assertNotIn("..", stored.relative_path)
+        self.assertTrue(stored.relative_path.startswith("logo/"))
+        path = file_store.resolve_within_root(stored.relative_path)
+        self.assertTrue(path.is_file())
+        self.assertTrue(str(path).startswith(str(file_store.root())))
+
+    def test_อัปโหลดชื่อซ้ำแต่เนื้อต่าง_ต้องไม่ทับไฟล์เดิม(self):
+        """รูปที่หน้าเว็บอ้างอยู่ต้องไม่เปลี่ยนเพราะมีคนอัปโหลดชื่อเดียวกันทับ"""
+        first = file_store.save("logo", "cover.png", PNG + "หนึ่ง".encode())
+        second = file_store.save("logo", "cover.png", PNG + "สอง".encode())
+        self.assertNotEqual(first.relative_path, second.relative_path)
+        self.assertEqual(file_store.resolve_within_root(first.relative_path).read_bytes(),
+                         PNG + "หนึ่ง".encode())
+
+    def test_เนื้อไฟล์เหมือนกันทุกไบต์ใช้ไฟล์เดียวกัน(self):
+        a = file_store.save("logo", "a.png", PNG + b"x")
+        b = file_store.save("logo", "b.png", PNG + b"x")
+        self.assertEqual(a.relative_path, b.relative_path)
+
+    def test_เปิดไฟล์ที่เก็บไว้ได้ด้วย_media_type_ที่ถูกต้อง(self):
+        stored = file_store.save("logo", "cover.webp", WEBP)
+        path, media_type = file_store.open_stored(stored.relative_path)
+        self.assertEqual(media_type, "image/webp")
+        self.assertEqual(path.read_bytes(), WEBP)
+
+    def test_หมวดรูปเปิดสาธารณะ_ไม่ต้องเข้าสู่ระบบก่อนดู(self):
+        """รูปประจำสาขาแสดงบนหน้าเว็บสาธารณะ ถ้าต้องล็อกอินก่อนดู รูปจะไม่ขึ้น"""
+        stored = file_store.save("logo", "cover.png", PNG)
+        self.assertFalse(file_store.is_private(stored.relative_path))
+
+
+if __name__ == "__main__":
+    try:
+        unittest.main(verbosity=2, exit=False)
+    finally:
+        _TEMP.cleanup()
```

## 5. diff — หน้าเว็บ (`70dbdd6`)

```diff
diff --git a/src/pages/Admin/CourseForm.jsx b/src/pages/Admin/CourseForm.jsx
index 208cec6..11ac59d 100644
--- a/src/pages/Admin/CourseForm.jsx
+++ b/src/pages/Admin/CourseForm.jsx
@@ -4,8 +4,8 @@ import { apiJson } from '../../lib/apiAuth'
 import { useAdminAuth } from '../../hooks/useAdminAuth'
 import AdminLayout from '../../components/admin/AdminLayout'
 import { useToast } from '../../components/admin/Toast'
-import { uploadFacultyPhoto, uploadCourseDocument, removeCourseFile, formatFileSize } from '../../lib/courseStorage'
-import { ArrowLeft, AlertCircle, Plus, Trash2, Upload, Loader2, FileText, User, Users, Info, FileEdit } from 'lucide-react'
+import { uploadFacultyPhoto, uploadCourseLogo, uploadCourseDocument, removeCourseFile, formatFileSize } from '../../lib/courseStorage'
+import { ArrowLeft, AlertCircle, Plus, Trash2, Upload, Loader2, FileText, User, Users, Info, FileEdit, Image as ImageIcon } from 'lucide-react'
 
 const FORM_TABS = [
   { id: 'basic', label: 'ข้อมูลหลักสูตร', icon: FileEdit },
@@ -16,6 +16,13 @@ const FORM_TABS = [
 // ตัวแบ่งบรรทัดของช่องที่กรอกเป็นรายการ — ประกาศไว้ที่เดียวเพื่อไม่ให้เขียนผิดคนละแบบ
 const LINE_BREAK = String.fromCharCode(10)
 
+// รูปประจำสาขา — ชนิดและขนาดที่รับ
+//
+// ด่านจริงอยู่ที่หลังบ้าน (ตรวจลายเซ็นไบต์แรกของไฟล์ ไม่ใช่นามสกุล และมีเพดานของหมวดนี้
+// เป็น 5 MB) ด่านตรงนี้มีไว้บอกผู้ใช้ทันทีโดยไม่ต้องรออัปโหลดเสร็จก่อนถึงจะรู้ว่าไม่ผ่าน
+const LOGO_MIME = { 'image/jpeg': 'JPG', 'image/png': 'PNG', 'image/webp': 'WebP' }
+const LOGO_MAX_BYTES = 5 * 1024 * 1024
+
 const LEVEL_OPTIONS = ['ปริญญาตรี', 'ปริญญาโท', 'ปริญญาเอก', 'ประกาศนียบัตรบัณฑิต', 'อนุปริญญา']
 const DURATION_OPTIONS = ['2 ปี', '3 ปี', '4 ปี', '4.5 ปี', '5 ปี', '6 ปี']
 
@@ -91,6 +98,10 @@ const CourseFormContent = ({ user }) => {
   const [saving, setSaving] = useState(false)
   const [error, setError] = useState('')
   const [activeTab, setActiveTab] = useState('basic')
+  // สถานะของการอัปโหลดรูปประจำสาขา — แยกจาก error ของทั้งฟอร์ม เพราะต้องขึ้นตรงช่องนั้น
+  const [logoUploading, setLogoUploading] = useState(false)
+  const [logoError, setLogoError] = useState('')
+  const [logoBroken, setLogoBroken] = useState(false)
 
   useEffect(() => {
     if (!isEdit) return
@@ -159,6 +170,43 @@ const CourseFormContent = ({ user }) => {
     }))
   }
 
+  // รูปประจำสาขา: อัปโหลดแล้วเติม URL ลงช่องเดิม
+  //
+  // **ยังไม่เปลี่ยนรูปของหลักสูตรจนกว่าจะกดบันทึกสำเร็จ** — ที่นี่แก้แต่ค่าในฟอร์ม
+  // ไฟล์ที่อัปโหลดถูกตั้งชื่อจาก hash ของเนื้อไฟล์ จึงไม่ทับของเดิมและไม่ชนกันเอง
+  // ถ้าเลือกรูปแล้วเปลี่ยนใจ เลือกใหม่หรือแก้ URL เองได้ก่อนบันทึก
+  const handleLogoFileChange = async (file, input) => {
+    // ล้างค่าของ input ทันที เพื่อให้เลือก "ไฟล์เดิม" ซ้ำแล้วยัง onChange อีกครั้ง
+    if (input) input.value = ''
+    if (!file) return
+    setLogoError('')
+    if (!LOGO_MIME[file.type]) {
+      setLogoError(`รับเฉพาะไฟล์ ${Object.values(LOGO_MIME).join(', ')} — ` +
+        `ไฟล์ที่เลือกเป็น ${file.type || 'ชนิดที่อ่านไม่ออก'}`)
+      return
+    }
+    if (file.size > LOGO_MAX_BYTES) {
+      setLogoError(`ไฟล์ขนาด ${formatFileSize(file.size)} ใหญ่เกินเพดาน 5 MB — ย่อรูปก่อนแล้วลองใหม่`)
+      return
+    }
+    setLogoUploading(true)
+    try {
+      const uploaded = await uploadCourseLogo(file)
+      setForm((prev) => ({ ...prev, logo: uploaded.url }))
+      setLogoBroken(false)
+    } catch (err) {
+      setLogoError('อัปโหลดรูปไม่สำเร็จ: ' + err.message)
+    } finally {
+      setLogoUploading(false)
+    }
+  }
+
+  const handleLogoUrlChange = (e) => {
+    setLogoError('')
+    setLogoBroken(false)
+    handleChange(e)
+  }
+
   const handleFacultyPhotoChange = async (index, file) => {
     if (!file) return
     const prevPath = form.faculty[index]?.image_path
@@ -384,14 +432,70 @@ const CourseFormContent = ({ user }) => {
         </div>
 
         <div>
-          <label className="block text-sm font-medium text-gray-700 mb-1.5">URL โลโก้/รูปภาพ</label>
-          <input
-            name="logo"
-            value={form.logo}
-            onChange={handleChange}
-            placeholder="/assets/courses/example.png"
-            className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-pnru"
-          />
+          <label className="block text-sm font-medium text-gray-700 mb-1.5">รูปประจำสาขา</label>
+          <div className="flex items-start gap-3">
+            {/* ตัวอย่างรูป — โหลดจาก URL จริงที่จะถูกบันทึก ถ้าโหลดไม่ขึ้นแปลว่าหน้าเว็บ
+                ก็จะแสดงไม่ขึ้นเหมือนกัน จึงบอกผู้ใช้ตรงนี้เลย ไม่ปล่อยให้ไปเจอทีหลัง */}
+            <div className="flex h-20 w-20 flex-shrink-0 items-center justify-center overflow-hidden rounded-lg border border-gray-200 bg-gray-50">
+              {logoUploading ? (
+                <Loader2 className="w-6 h-6 text-gray-400 animate-spin" />
+              ) : form.logo && !logoBroken ? (
+                <img
+                  src={form.logo}
+                  alt="ตัวอย่างรูปประจำสาขา"
+                  className="h-full w-full object-cover"
+                  onError={() => setLogoBroken(true)}
+                  onLoad={() => setLogoBroken(false)}
+                />
+              ) : (
+                <ImageIcon className="w-7 h-7 text-gray-300" />
+              )}
+            </div>
+
+            <div className="flex-1 space-y-2">
+              <div className="flex flex-wrap items-center gap-2">
+                <label className={`inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-gray-300 text-xs font-medium transition-colors ${
+                  logoUploading ? 'text-gray-400 cursor-not-allowed' : 'text-gray-700 hover:bg-gray-50 cursor-pointer'
+                }`}>
+                  <Upload className="w-3.5 h-3.5" />
+                  {logoUploading ? 'กำลังอัปโหลด…' : form.logo ? 'เปลี่ยนรูป' : 'เลือกรูปจากคอมพิวเตอร์'}
+                  <input
+                    type="file"
+                    accept="image/jpeg,image/png,image/webp"
+                    className="hidden"
+                    disabled={logoUploading}
+                    onChange={(e) => handleLogoFileChange(e.target.files?.[0], e.target)}
+                  />
+                </label>
+                <span className="text-xs text-gray-400">JPG, PNG หรือ WebP ไม่เกิน 5 MB</span>
+              </div>
+
+              {/* ยังวาง URL เองได้เหมือนเดิม — รูปที่โฮสต์ไว้ที่อื่นหรือไฟล์ใน /assets ยังใช้ได้ */}
+              <input
+                name="logo"
+                value={form.logo}
+                onChange={handleLogoUrlChange}
+                placeholder="หรือวาง URL เอง เช่น /assets/courses/example.png"
+                className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-pnru"
+              />
+
+              {logoError ? (
+                <p className="flex items-start gap-1.5 text-xs text-red-600">
+                  <AlertCircle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
+                  {logoError}
+                </p>
+              ) : form.logo && logoBroken ? (
+                <p className="flex items-start gap-1.5 text-xs text-amber-600">
+                  <AlertCircle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
+                  เปิดรูปจาก URL นี้ไม่ได้ — ตรวจ URL อีกครั้ง หรือกดเลือกรูปจากคอมพิวเตอร์
+                </p>
+              ) : (
+                <p className="text-xs text-gray-400">
+                  รูปบนหน้าเว็บจะเปลี่ยนเมื่อกดบันทึกสำเร็จเท่านั้น · รูปเดิมไม่ถูกลบหรือเขียนทับ
+                </p>
+              )}
+            </div>
+          </div>
         </div>
 
         <div>
```

---

## 6. แผน deploy (ยังไม่รัน รอการอนุมัติ)

ลำดับเดียวกับรอบก่อน — **backend ก่อน หน้าเว็บทีหลัง** เพราะหน้าเว็บใหม่ต้องมีเพดาน
5 MB ของหลังบ้านรองรับ ส่วนหลังบ้านใหม่รับหน้าเว็บเก่าได้ตามปกติ

### 6.1 ค่าที่ต้องคงไว้

| | |
|---|---|
| `UPLOADS_DIR` | **ไม่แตะ** — `/srv/uploads` อยู่แล้ว ถ้าแก้ รูปเดิมทั้ง 105 ไฟล์จะหาย |
| `UPLOAD_MAX_BYTES` | **ไม่แตะ** — ยังเป็น 10 MB เพดาน 5 MB เป็นของหมวดรูปเท่านั้น |
| bind mount ของ `uploads` | **ไม่แตะ** |
| ฐานข้อมูล | ไม่มี migration ไม่มีการแก้ข้อมูล |
| `src/pages/Admin/AiSettings.jsx` | งานค้างที่ยังไม่ commit — ต้องรอดทั้งก่อนและหลัง (ดูข้อ 7) |

### 6.2 backend

1. merge `feature/public-model-choice` (head ที่มี `1c4b510`) เข้า `mko-phase2` แบบ fast-forward
2. สร้างอิมเมจซ้อนจากตัวที่รันอยู่ **ไม่ build จาก working tree ทั้งก้อน**
   `FROM course-advisor-system-backend:public-choice-2569-10-29` ทับ 2 ไฟล์
   `app/services/file_store.py` · `tests/test_upload_image.py`
   พาธในอิมเมจคือ `/app/backend/app/...` และ `/app/backend/tests/...`
   · tag `image-upload-2569-10-29`
3. ตรวจ SHA256 ของทั้งสองไฟล์ในอิมเมจให้ตรงกับ blob ของ commit ก่อนสลับ
4. รันในอิมเมจใหม่ (บนฐาน `course_advisor_test` ไม่ใช่ production)
   `python tests/test_upload_image.py` ต้องผ่าน 11 ข้อ
5. สลับ tag ใน compose แล้ว `up -d --no-build --no-deps backend` · ดู dry-run ก่อนว่าไม่แตะบริการอื่น
6. ตรวจ `/api/health` = 200 และรูปเดิมยังเปิดได้ — หยิบไฟล์จาก `~/course-advisor-system/uploads/logo`
   มาหนึ่งไฟล์แล้วเปิดผ่าน `https://stpnru-advisor.duckdns.org/api/uploads/logo/<path>` ต้องได้ 200

### 6.3 หน้าเว็บ

> ขั้นที่ 1–2 **ทำไปแล้ว** เมื่อ 29 ต.ค. 2569 — ชุดพร้อมอัปโหลด รายละเอียดอยู่ในข้อ 9.2

1. **build จาก worktree แยกที่ commit `70dbdd6` เท่านั้น** (ดูข้อ 7)
2. ทำ `SHA256SUMS` ของชุด แล้ว `sha256sum -c` ให้ผ่านครบก่อนอัปโหลด
3. อัปโหลดด้วย `deploy_web.sh` — วาง `assets` ให้ครบ ดึงผ่านเว็บจริงมาตรวจ hash ทุกไฟล์
   **แล้วค่อยสลับ `index.html` เป็นขั้นสุดท้าย**

### 6.4 ตรวจรับหลัง deploy

1. เข้าหน้าแอดมิน → แก้หลักสูตรสักหลักสูตร → ช่องขึ้นว่า **"รูปประจำสาขา"** พร้อมปุ่ม
   `เลือกรูปจากคอมพิวเตอร์`
2. เลือกรูปจริง (JPG หรือ PNG ขนาดปกติ) → URL ต้องเติมให้เอง และ**ตัวอย่างรูปต้องขึ้น**
3. **ยังไม่กดบันทึก** แล้วเปิดหน้าสาธารณะของหลักสูตรนั้น → รูปต้องยังเป็นรูปเดิม
4. กลับมากดบันทึก → เปิดหน้าสาธารณะอีกครั้ง → รูปเปลี่ยนเป็นรูปใหม่
5. เปิด URL ของรูปตรง ๆ (`/api/uploads/logo/…`) → ต้องได้ 200 และเป็นรูปจริง
6. ลองเลือกไฟล์ PDF และไฟล์เกิน 5 MB → ต้องขึ้นข้อความบอกเหตุ และ**URL เดิมไม่เปลี่ยน**
7. เปิดหน้า "ตั้งค่า AI" ของผู้ดูแล → ต้องเหมือนเดิมทุกอย่าง (ด่านของข้อ 7)

### 6.5 rollback

| ส่วน | วิธีย้อน |
|---|---|
| backend | สลับ tag กลับเป็น `public-choice-2569-10-29` แล้ว `up -d --no-build --no-deps backend` · **ไม่มีอะไรต้องย้อนในฐานข้อมูลและไม่ต้องลบไฟล์ที่อัปโหลดไปแล้ว** (ไฟล์อยู่นอกอิมเมจ และรุ่นเก่าก็เปิดไฟล์เหล่านั้นได้ปกติ) |
| หน้าเว็บ | `rollback_web.sh --run <โฟลเดอร์ web-run ของรอบนี้>` — ย้อนเฉพาะ `index.html` ให้ชี้ bundle เดิม (js/css เก่ายังอยู่บนเซิร์ฟเวอร์) |
| ย้อนเฉพาะหน้าเว็บได้ไหม | ได้ — หน้าเว็บเก่าไม่มีปุ่มอัปโหลด แต่ backend ใหม่ยังรับคำขอเดิมทุกอย่าง |
| ย้อนเฉพาะ backend ได้ไหม | ได้ — ปุ่มยังอยู่ แต่เพดานกลับเป็น 10 MB ตามรุ่นเก่า ไฟล์ที่อัปโหลดไปแล้วไม่ได้รับผลกระทบ |

---

## 7. ด่านที่กันงานค้าง `AiSettings.jsx` ไม่ให้ติดไปกับชุด deploy

งานค้างของเจ้าของเครื่องอยู่ที่ `D:\workspace\LastProject\src\pages\Admin\AiSettings.jsx`
(+223 บรรทัด ยังไม่ commit) ถ้า build จาก checkout หลัก **มันจะถูกรวมเข้า bundle ทันที**
โดยไม่มีอะไรเตือน

**ห้าม** `cd D:\workspace\LastProject && npm run build` แล้วเอา `dist` นั้นไปใช้
(ระหว่างทดสอบรอบนี้มี `dist` แบบนั้นอยู่จริงในเครื่อง — ใช้ตรวจ UI เท่านั้น **ห้ามนำไป deploy**)

ให้ทำแบบที่สองรอบก่อนใช้แล้วได้ผล

```bash
git -C D:/workspace/LastProject worktree add --detach D:/workspace/lastproject-rel-70dbdd6 70dbdd6
# node_modules ใช้ junction ชี้ไปที่ของ checkout หลัก และคัดลอก .env / .env.local มา
cd D:/workspace/lastproject-rel-70dbdd6 && git status --porcelain   # ต้องว่าง
npm run build
```

ด่านที่ต้องผ่านก่อนอัปโหลด

1. `git status --porcelain` ใน worktree นั้น **ต้องว่าง** — ว่าง = ไม่มีงานค้างปนแน่นอน
2. `git -C D:/workspace/LastProject status --porcelain` ต้องยังขึ้น ` M src/pages/Admin/AiSettings.jsx`
   อยู่เหมือนเดิมหลัง build เสร็จ (แปลว่า checkout หลักไม่ถูกแตะ)
3. หลัง deploy เปิดหน้า "ตั้งค่า AI" ของผู้ดูแลแล้วต้องเหมือนเดิม (ข้อ 6.4.7)

---

## 8. ที่ยังไม่ได้ทำ / ข้อควรรู้

* **ยังไม่ merge ยังไม่ deploy** — ทั้งสอง repo อยู่บน branch ของตัวเอง
* commit ของหน้าเว็บยัง push ขึ้น GitHub ไม่ได้ — repo คือ `FoMake/Univercity` แต่บัญชี
  ในเครื่องคือ `pattana-ketchot` ซึ่งไม่มีสิทธิ์เขียน (`403`) · ต้องขอสิทธิ์หรือ push
  จากบัญชีเจ้าของ
* เพดาน 5 MB มีผลกับ**ทุกอย่างในหมวด `logo`** รวมรูปคณาจารย์ (เดิม 10 MB) — ถ้าไม่ต้องการ
  ต้องแยกหมวดใหม่ ซึ่งเป็นงานอีกรอบ
* หมวด `logo` ของ backend ยังรับ `.gif` ตามเดิม ส่วนปุ่มในหน้าแอดมินรับเฉพาะ JPG/PNG/WebP
* ยังไม่มีปุ่มอัปโหลดรูปที่หน้าอื่น (ข่าว/คลังความรู้ยังใช้ของเดิมที่มีอยู่แล้ว)
* ยังไม่ได้ทดสอบกับรูปขนาดจริงจากกล้อง/มือถือ (HEIC ไม่รองรับ — ต้องแปลงเป็น JPG ก่อน)

---

## 9. รอบแก้เพิ่ม (29 ต.ค. 2569) — exit code ของชุดทดสอบ และชุด frontend ที่ build แล้ว

### 9.1 ชุดทดสอบไม่เคยทำให้ด่านล้ม แม้มีข้อที่ตก — แก้แล้ว

`unittest.main(exit=False)` ใส่ไว้เพื่อให้ลบโฟลเดอร์ชั่วคราวก่อนจบ แต่ไม่มีใครอ่านผลของมัน
สคริปต์จึง **exit 0 เสมอ** แม้มีเทสต์ตก · ด่าน deploy ที่ดู exit code (ข้อ 6.2 ขั้นที่ 4)
จะเห็นว่า "ผ่าน" ทุกครั้ง ซึ่งคือการไม่ตรวจที่ถูกรายงานเป็นการผ่าน

```diff
 if __name__ == "__main__":
+    # ต้องคืน exit code ตามผลจริง ไม่งั้นด่าน deploy ที่ดู exit code จะเห็นว่า "ผ่าน"
+    # ทุกครั้งแม้มีข้อที่ตก · exit=False มีไว้เพื่อให้ลบโฟลเดอร์ชั่วคราวก่อนจบเท่านั้น
     try:
-        unittest.main(verbosity=2, exit=False)
+        run = unittest.main(verbosity=2, exit=False)
     finally:
         _TEMP.cleanup()
+    raise SystemExit(0 if run.result.wasSuccessful() else 1)
```

ยืนยันสองทาง **โดยไม่แตะ assertion ข้อใดเลย**

| รัน | ผล | exit |
|---|---|---|
| `python tests/test_upload_image.py` | `Ran 11 tests · OK` | **0** |
| `UPLOAD_MAX_BYTES=1024 python tests/test_upload_image.py` | `FAILED (failures=1)` · ตกที่ `test_เพดานขนาดของหมวดรูปคือ_5_MB` | **1** |

การจำลองตกใช้ตัวแปรสภาพแวดล้อมล้วน ๆ — บีบเพดานของทั้งระบบเหลือ 1024 ไบต์ ทำให้
`max_bytes_for("logo")` คืน 1024 แล้วข้อที่ยืนยันว่า "5 MB พอดีต้องผ่าน" ตกจริง
ไม่ได้แก้เกณฑ์ใดเพื่อให้ตก

ตรวจชุดอื่นด้วย — `test_answer_claims` และ `test_answer_evidence` ใช้ `unittest.main()`
ตรง ๆ ส่วน `test_public_model_choice` ใช้ `raise SystemExit(main())` ทั้งสามคืน exit code
ถูกต้องอยู่แล้ว ชุดที่พลาดมีเฉพาะตัวใหม่ตัวนี้

commit **`a22a496`**

### 9.2 ชุด frontend — build จาก worktree แยกที่ `70dbdd6` แล้ว

```
git -C D:/workspace/LastProject worktree add --detach D:/workspace/lastproject-rel-70dbdd6 70dbdd6
git status --porcelain   ->  ว่าง
npm run build            ->  vite 5.4.21 · 1888 modules · 7.05s
```

| | |
|---|---|
| ชุดอยู่ที่ | `D:\workspace\lastproject-rel-70dbdd6\dist` · **19 ไฟล์** |
| js | `assets/index-CByV8S-P.js` · `789550cb7d8c68c74f3ee5edaa9199625d34182bc45eae73b67def2b59f47c76` |
| css | `assets/index-DSTdGTxh.css` · `6d5b433917407354…` — **ตัวเดียวกับที่ production เสิร์ฟอยู่** ไม่ต้องเปลี่ยน |
| ด่าน hash | `sha256sum -c SHA256SUMS` **ผ่าน 19 / 19** |
| ต่างจากชุดที่ deploy อยู่ | **js ใหม่ กับ `index.html` เท่านั้น** — อีก 17 ไฟล์ไบต์ตรงกับของบนเซิร์ฟเวอร์ (รวม `assets/README.md` ที่เทียบแบบ LF ตามที่ทำมาทุกรอบ) |

ด่านกันงานค้าง (ข้อ 7) ผ่านครบ

1. `git status --porcelain` ใน worktree ที่ใช้ build → **ว่าง**
2. `git status --porcelain` ของ checkout หลักหลัง build → ยังขึ้น ` M src/pages/Admin/AiSettings.jsx`
   (+198 −25) เหมือนเดิม — checkout หลักไม่ถูกแตะ
3. ข้อ 3 (เปิดหน้า "ตั้งค่า AI" หลัง deploy) ยังค้างอยู่ เพราะยังไม่ deploy

### 9.3 ฟีเจอร์เลือกโมเดลหน้าแชทที่ปล่อยไปแล้วต้องไม่หาย — ตรวจแล้ว

`70dbdd6` ต่อยอดจากคอมมิตที่ปล่อยไปแล้วโดยตรง ยืนยันด้วย `git merge-base --is-ancestor`

```
bf69f38  feat(chat): ให้ผู้ใช้เลือกโมเดลที่จะตอบได้ที่หน้าแชท      (deploy แล้ว)
16de266  feat(chat): บอกชื่อรุ่นที่จะเขียนคำตอบข้างตัวเลือก "ตอบด้วย"  (deploy แล้ว)
70dbdd6  feat(admin): อัปโหลดรูปประจำสาขาจากเครื่องได้ที่หน้าแก้หลักสูตร  (ชุดนี้)
```

และตรวจในไฟล์ js ที่ build ออกมาจริง ไม่ใช่เชื่อจากลำดับ commit อย่างเดียว

| สตริงที่ต้องมี | พบใน `index-CByV8S-P.js` |
|---|---|
| `ai-options` · `model_choice` | 1 · 1 |
| `รุ่นที่ใช้เขียนคำตอบ` (ของ `16de266`) | 1 |
| `ตอบด้วย` | 2 |
| `รูปประจำสาขา` · `เลือกรูปจากคอมพิวเตอร์` (ของรอบนี้) | 2 · 2 |
| `ใหญ่เกินเพดาน 5 MB` | 1 |

ชุดนี้จึงมีทั้งของเดิมที่ปล่อยไปแล้วและของใหม่ · ไม่ได้รันชุดทดสอบใหญ่ซ้ำตามที่สั่ง
ใช้ผลตรวจของรอบก่อนในข้อ 3 ประกอบ

**ยังไม่ merge ยังไม่ deploy**
