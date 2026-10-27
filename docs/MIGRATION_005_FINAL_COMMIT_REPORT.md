# Migration 005 Final Review — Commit Report

| | |
|---|---|
| วันที่ | 2026-10-02 |
| ขอบเขต | COMMIT เท่านั้น |
| **commit** | **`dc5e86035c2b2c3faedd6f79487b308db3513d2b`** (`dc5e860`) |
| branch | `mko-phase2` (ต่อจาก `f72b418`) |
| ไฟล์ | **4 ไฟล์ · +2032 −18** |
| **PUSH** | **NONE — ยังไม่ push** |

```
Push                  NONE        Production Write        NONE
Apply Migration 005   NONE        Deploy / Restart        NONE
Data Migration        NONE        Merge main              NONE
```

---

## 1. Commit

```
hash    dc5e86035c2b2c3faedd6f79487b308db3513d2b
short   dc5e860
branch  mko-phase2
author  popoza11874
date    Fri Oct 2 11:45:54 2026 +0700

subject fix(db): finalize web schema migration from live verification
body    Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
```

```
db/migrations/005_web_schema.sql     | 148 ++++-     (M)
docs/MIGRATION_005_FINAL_REVIEW.md  | 602 ++++++    (A)
docs/SUPABASE_LIVE_VERIFICATION.md  | 1173 +++++++  (A)
eval/web_schema_check.py            | 127 ++++      (M)
4 files changed, 2032 insertions(+), 18 deletions(-)
```

สายของ commit

```
dc5e860  fix(db): finalize web schema migration from live verification   <- ใหม่
f72b418  docs: correct the Supabase facts and record where they came from
de42e38  fix(db): match the source schema's keys in the web schema
97686a1  docs: record the consolidation feasibility study
```

---

## 2. การเลือกไฟล์

**ไม่ใช้ `git add .`** — ระบุทั้ง 4 ไฟล์ด้วย `git add --` ตรง ๆ

| ไฟล์ | ทำไมรวม |
|---|---|
| `db/migrations/005_web_schema.sql` | ตัว migration ที่แก้ตาม Live evidence |
| `eval/web_schema_check.py` | ชุดทดสอบที่กันการถอยหลังของการแก้นั้น |
| `docs/MIGRATION_005_FINAL_REVIEW.md` | รายงาน Final Review ของรอบนี้ |
| `docs/SUPABASE_LIVE_VERIFICATION.md` | หลักฐานที่ทั้งรอบนี้อ้างอิง — ตรวจ production จริง 32 คำสั่ง |

### ไฟล์ที่ไม่รวม และเหตุผล

| ไฟล์ | เหตุผล |
|---|---|
| `docs/MIGRATION_005_CORRECTIVE_PUSH_REPORT.md` | เป็นเอกสาร Migration 005 ที่ค้างจาก **รอบก่อน** ไม่ใช่รอบนี้ — ขอบเขตที่สั่งคือ "หลักฐานของรอบนี้" · **ยังรอคำสั่งว่าจะ commit ด้วยไหม** |
| untracked อีก **54** รายการใน `docs/` | ไม่เกี่ยวกับ Migration 005 Final Review (รายงาน PHASE3D · สไลด์ · ER diagram · audit อื่น ๆ) |

หลัง commit: `tracked ที่ถูกแก้ = 0` · ไม่มีไฟล์อื่นในรีโปถูกแตะ

---

## 3. ผลตรวจ secret / PII

สแกน **จาก git object** (`git show HEAD:<file>`) ไม่ใช่จากไฟล์บนดิสก์ เพื่อให้ตรงกับ
สิ่งที่เข้าไปในประวัติจริง

| สิ่งที่ค้นหา | ผล |
|---|---|
| อีเมล (รูปแบบ `x@y.z`) | **ไม่พบ** |
| `password` / `secret` / `api_key` / `token` / `bearer` / `service_role` / `anon_key` แบบมีค่าตามหลัง | **ไม่พบ** |
| JWT (`eyJ…`) · `sk-…` · base64 ยาวเกิน 60 | **ไม่พบ** |
| password hash (`$2a$` / `$argon2` / `pbkdf2` / `scrypt`) | **ไม่พบ** |
| IP address | **ไม่พบ** (นอกจาก `127.0.0.1` ในตัวอย่างคำสั่งทดสอบ) |
| รหัสผ่านของ role และของ container ที่สร้างตอนรันเทสต์ | **ไม่พบ** — อยู่ในสคริปต์ scratchpad เท่านั้น ไม่เคยเข้ารีโป · เป็นค่าใช้ครั้งเดียวบน `127.0.0.1` ของ container ที่ถูกลบไปแล้ว |
| `POSTGRES_PASSWORD` | **ไม่พบ** |

ทั้ง 4 ไฟล์ขึ้น **สะอาด**

### 3.1 สิ่งที่ต้อง redact — Supabase project ref

**รีโปนี้เป็น public** ยืนยันด้วย GitHub API แบบไม่ต้อง auth

```
curl -s -o /dev/null -w '%{http_code}' https://api.github.com/repos/pattana-ketchot/Project-Chataipnru
-> 200
```

และ `SUPABASE_LIVE_VERIFICATION.md` อธิบาย **แบบจำลองสิทธิ์ของ production ไว้ครบ**

| สิ่งที่ไฟล์เปิดเผย | ทำไมสำคัญเมื่ออยู่ในรีโป public |
|---|---|
| RLS เป็นด่านเดียว ไม่มีตารางใดตั้ง FORCE ROW SECURITY | ถ้ารู้ว่าโปรเจกต์ไหน ก็รู้ว่าต้องเจาะอะไร |
| `user_profiles` อ่านได้โดยทุกคน (`USING (true)`) ขณะที่เก็บ `email` + `full_name` | ชี้ตรงไปที่จุดที่ดึง PII ได้ |
| `anon` เรียก security-definer function ได้ 3 ตัว ผ่าน `/rest/v1/rpc/...` | ชื่อฟังก์ชันครบ พร้อมช่องทางเรียก |
| bucket `course-assets` เป็น public · ชื่อ object ครบ | ดึงไฟล์ได้ตรงถ้ารู้ ref |
| `auth_leaked_password_protection` ปิดอยู่ | บอกสภาพการตั้งค่าของ auth |

**การแก้**: แทนค่า project ref จริงด้วย `<SUPABASE_PROJECT_REF>`

```diff
-| โปรเจกต์ | `<ref จริง>` · https://<ref จริง>.supabase.co |
+| โปรเจกต์ | `<SUPABASE_PROJECT_REF>` · `https://<SUPABASE_PROJECT_REF>.supabase.co` (ปิดไว้ — ดูหมายเหตุท้ายหัวเอกสาร) |
```

พร้อมเพิ่มหมายเหตุ 7 บรรทัดอธิบายว่าปิดเพราะอะไรและหาค่าจริงได้ที่ไหน
(Supabase Dashboard หรือ `.mcp.json` ของรีโปหน้าเว็บ)

| | |
|---|---|
| กระทบ | **1 บรรทัด** (+ หมายเหตุ 8 บรรทัด) |
| ข้อสรุป / ตัวเลข / SQL ที่เปลี่ยน | **ไม่มีเลย** |
| แนวที่ใช้ | เหมือนที่ `SUPABASE_PRE_MIGRATION_AUDIT.md` แทนอีเมลเจ้าของด้วย `<OWNER_EMAIL>` ในรอบก่อน |
| ฉบับที่มี ref ครบ | เก็บไว้ใน scratchpad ของ session · ต้นฉบับยังอยู่ที่ `course-advisor-system/docs/` |

> **ถ้าต้องการให้ ref จริงอยู่ในไฟล์** บอกได้ — แก้แล้ว `--amend` ได้ทันทีเพราะยังไม่ push

### 3.2 สิ่งที่พิจารณาแล้วว่าไม่ใช่ความลับ

| | เหตุผล |
|---|---|
| `ezbr_sha256` ของ Edge Function | เป็น checksum ของ bundle ไม่ใช่ credential |
| id ของ Edge Function · jobid/jobname ของ pg_cron | ตัวระบุ ไม่ใช่กุญแจ · ไฟล์ **ไม่ได้อ่านเนื้อ `cron.job.command`** โดยเจตนาเพราะตรวจพบว่ามีคำบ่งชี้ token |
| UUID ของ 12 หลักสูตร · ชื่อ object ใน storage | เป็น id ของแถว ไม่ใช่ความลับ และเมื่อ ref ถูกปิดแล้วก็ไม่มีความหมายกับคนนอก |
| ชื่อหลักสูตรทั้ง 12 | เป็นข้อมูลสาธารณะบนเว็บคณะอยู่แล้ว |

---

## 4. การตรวจก่อน commit

```
git status --short          58 รายการ (2 modified + 56 untracked)
git diff                   เทียบทุกบรรทัดกับที่รายงานไว้ — ตรงทั้งหมด
git diff --cached           4 ไฟล์เท่านั้น  M / A / A / M
git diff --cached --check   ว่าง (ไม่มี whitespace ผิด)
git diff --name-only        ว่าง (ไม่มีการแก้ค้างที่ไม่ได้ stage)
CRLF ทั้ง 4 ไฟล์            0
```

### การเปลี่ยนแปลงเชิงเนื้อหาใน `005` — ไม่นับคอมเมนต์

```diff
-    careers       TEXT[]       NOT NULL DEFAULT '{}',
-    detail        JSONB        NOT NULL DEFAULT '{}',
+    careers       TEXT[],
+    detail        JSONB,

-    title         VARCHAR(255) NOT NULL,      web.news
+    title         VARCHAR(500) NOT NULL,
-    title         VARCHAR(255) NOT NULL,      web.external_news
+    title         VARCHAR(500) NOT NULL,
-    title         VARCHAR(255) NOT NULL,      web.knowledge_articles
+    title         VARCHAR(500) NOT NULL,

+CREATE OR REPLACE FUNCTION web.touch_updated_at() ...
+CREATE OR REPLACE TRIGGER trg_site_courses_updated_at       BEFORE UPDATE
+CREATE OR REPLACE TRIGGER trg_news_updated_at               BEFORE UPDATE
+CREATE OR REPLACE TRIGGER trg_knowledge_articles_updated_at BEFORE UPDATE
+CREATE OR REPLACE TRIGGER trg_ai_settings_updated_at        BEFORE UPDATE
+GRANT EXECUTE ON FUNCTION web.touch_updated_at() TO advisor_api;
+GRANT EXECUTE ON FUNCTION web.touch_updated_at() TO advisor_ingest;
```

ที่เหลือใน `+148` เป็นคอมเมนต์อธิบายหลักฐาน — รวมการปิดเคส `PENDING DECISION`
ของ `news.status` และการแก้คอมเมนต์ที่เคยให้เหตุผลผิดเรื่อง `careers` และ `slug`

### ชุดทดสอบที่เพิ่ม

```
[1b] column_widths()        16 ข้อ   ความกว้างคอลัมน์เทียบกับต้นทาง
[3b] updated_at_trigger()    8 ข้อ   trigger ทำงานเฉพาะ UPDATE
     + 2 ข้อใน enforcement()        careers / detail / title_en / description เป็น NULL ได้
```

ผลที่รายงานไว้ก่อน commit: **535 ผ่าน · 0 ไม่ผ่าน** (+25 ข้อที่รันได้แค่บน Linux = 560)

---

## 5. ข้อผิดพลาดที่เกิดขึ้นและแก้แล้ว

**commit message เพี้ยนในครั้งแรก** — ผมใช้ here-string ของ PowerShell (`@'...'@`)
ใน Bash tool ซึ่งไม่รู้จักรูปแบบนั้น subject จึงกลายเป็น

```
@ fix(db): finalize web schema migration from live verification
```

แก้ด้วย `git commit --amend -F -` พร้อม heredoc ของ bash ที่ถูกต้อง

| | |
|---|---|
| commit แรก (ทิ้งแล้ว) | `95f602b` |
| **commit ที่ใช้** | **`dc5e860`** |
| เนื้อหาไฟล์ | เหมือนกันทุกไบต์ — เปลี่ยนแค่ข้อความ commit |
| ปลอดภัยที่ amend | commit ยังไม่ถูก push ไม่มีใครดึงไปใช้ |

---

## 6. สภาพ working tree หลัง commit

```
HEAD                    dc5e860  mko-phase2
origin/mko-phase2       f72b418
local นำหน้า origin     1 commit

staged ที่เหลือ          0
แก้ค้างยังไม่ stage      0
tracked ที่ถูกแก้        0
untracked ที่เหลือ       54   (ไม่เกี่ยวกับรอบนี้)
```

**สะอาด** — ไม่มีการแก้ค้างอยู่

---

## 7. ขั้นถัดไป

```
1. ขออนุมัติ push  mko-phase2  ->  origin
   (ยังไม่ push · ถ้าต้องการให้ ref จริงกลับเข้าไฟล์ ให้บอกก่อน push
    เพราะ amend ได้เฉพาะตอนยังไม่ push)

2. ตัดสิน 4 ข้อที่ BLOCKED ใน Final Review
     B1  Authorization ชั้น API — จะรักษาการแยก admin/editor ไหม
         ทั้งที่ของจริงยังไม่มีใครถือ editor
     B2  ผู้เขียนเนื้อหา 1 บัญชี — จับคู่ด้วยมือ หรือยอมให้เป็น NULL ทั้ง 15 แถว
     B3  PDF กำพร้า 4 ไฟล์ 10.4 MiB — ห้ามลบ ตัดสินว่าจะทำอย่างไร
     B4  PII ใน courses.detail (faculty[].email)

3. U3 — ตัวดึงข่าวค้าง 10 วัน ให้ตรวจ cron.job_run_details ก่อนวางแผน cutover ไหม

4. ขออนุมัติแยกสำหรับ apply 005 กับ production database

5. ขออนุมัติแยกสำหรับ data migration ทีละตาราง
```

---

## STOP

**รออนุมัติก่อน push**

```
PUSH: NONE                APPLY MIGRATION: NONE      DATA MIGRATION: NONE
PRODUCTION WRITE: NONE    DEPLOY / RESTART: NONE     MERGE main: NONE
```
