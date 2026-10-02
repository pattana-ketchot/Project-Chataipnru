# Migration 005 — Final Review (รอบสอง · อิง Live Verification จริง)

| | |
|---|---|
| วันที่ | 2026-10-02 |
| ขอบเขต | REVIEW + CODE CORRECTION เท่านั้น |
| Source of truth | `docs/SUPABASE_LIVE_VERIFICATION.md` — **1,165 บรรทัด · 32 คำสั่งบน production จริง** |
| **ผลทดสอบ** | **535 ข้อ ผ่าน · 0 ไม่ผ่าน** (+25 ข้อที่รันได้แค่บน Linux — ดูข้อ 4) |
| **สถานะ** | **แก้ใน working tree แล้ว · ยังไม่ commit · ยังไม่ push** |
| HEAD | `f72b418` บน `mko-phase2` (ไม่ขยับ) |
| M1–M17 | **CLOSED 9 · ACCEPTED 4 · BLOCKED 4** |

```
Apply Migration บน Production   NONE        Re-embed                NONE
Data Migration                  NONE        Deploy / Restart        NONE
Production Write                NONE        Merge main              NONE
แก้ Supabase Production          NONE        Commit / Push           NONE
```

---

## 0. แก้ความเข้าใจผิดของรายงานรอบก่อน

รายงานฉบับก่อนสรุปว่า **Production Verification = 0/10** ซึ่ง **ผิด**

สาเหตุ: ไฟล์ `SUPABASE_LIVE_VERIFICATION.md` ฉบับจริงถูกเขียนลง **repo คนละตัว**
ผมค้นแต่ใน worktree นี้แล้วเจอฉบับเก่าของตัวเองที่ยังเขียนว่า 0/10 จึงรายงานตามนั้น

| | ฉบับเก่า (ที่รายงานก่อนใช้) | **ฉบับจริง** |
|---|---|---|
| ที่อยู่ | `course-advisor-system-mko2/docs/` | `course-advisor-system/docs/` |
| ขนาด | 28,524 ไบต์ · 438 บรรทัด | **82,869 ไบต์ · 1,165 บรรทัด** |
| เวลา | 09:34 | **10:24** |
| เนื้อหา | "VERIFIED จาก production: ไม่มี 0/10" | **ตรวจจริง 32 คำสั่งผ่าน Supabase MCP (`read_only=true`)** |
| sha256 | `5ced0499…` | `70ca1a42…` |

**จัดการแล้ว**: คัดลอกฉบับจริงมาวางที่ `docs/SUPABASE_LIVE_VERIFICATION.md` ของ worktree นี้
ฉบับเก่าเก็บสำรองไว้ใน scratchpad ของ session ไม่ได้ลบทิ้ง

**แก้ไขก่อน commit หนึ่งจุด**: รีโปนี้เป็น **public** และไฟล์หลักฐานอธิบายแบบจำลองสิทธิ์
ของ production ไว้ครบ (RLS เป็นด่านเดียว · `user_profiles` อ่านได้โดยทุกคนขณะที่เก็บ
`email`/`full_name` · `anon` เรียก security-definer function ได้ 3 ตัว) ค่า Supabase
project ref จริงจึงถูกแทนด้วย `<SUPABASE_PROJECT_REF>` ตามแนวเดียวกับที่
`SUPABASE_PRE_MIGRATION_AUDIT.md` แทนอีเมลเจ้าของด้วย `<OWNER_EMAIL>` —
กระทบ 1 บรรทัด **ไม่มีข้อสรุป ตัวเลข หรือ SQL ใดเปลี่ยน** ฉบับที่มี ref ครบเก็บไว้ใน
scratchpad และต้นฉบับยังอยู่ที่ `course-advisor-system/docs/`

> ข้อที่รายงานก่อนพูดถูก: ตัวเลขที่ยังไม่ได้ตรวจกับต้นทาง **ห้ามรับมาใช้** —
> หลักการถูก แต่ผมค้นไม่ครบ ไม่ได้ดู repo พี่น้องทั้งที่ 005 กับหน้าเว็บอยู่คนละ repo
> มาตั้งแต่ต้น

---

## 1. สิ่งที่แก้

`+257 −18` · 2 ไฟล์ (รวมของรอบก่อนที่ Live evidence ยืนยันว่าถูกแล้ว)

```
db/migrations/005_web_schema.sql   +148 −18
eval/web_schema_check.py           +127 −0
```

### 1.1 รอบนี้ — ขยาย `title` 3 คอลัมน์ `VARCHAR(255)` → `VARCHAR(500)` ⬅ ใหม่

```sql
web.news.title                VARCHAR(255) -> VARCHAR(500)
web.external_news.title       VARCHAR(255) -> VARCHAR(500)
web.knowledge_articles.title  VARCHAR(255) -> VARCHAR(500)
```

`web.site_courses.title` และ `title_en` **คง 255 ไว้** — ต้นทางเป็น `varchar(255)` อยู่แล้ว
ไม่ขยายเหมารวมทั้งไฟล์

### 1.2 รอบนี้ — ปิดเคส `news.status` ที่ค้างเป็น `PENDING DECISION` ⬅ ใหม่

คอมเมนต์เดิมเขียนว่า *"ทางที่ถูกคือรัน `SELECT DISTINCT status FROM public.news`
บนต้นทางก่อน"* — รันแล้ว เอาผลจริงมาแทนคำถาม **ไม่เปลี่ยนตัว CHECK**
(เหตุผลที่ไม่เปลี่ยนอยู่ในข้อ 3.1)

### 1.3 รอบนี้ — แก้คอมเมนต์ที่ให้เหตุผลผิด 2 จุด ⬅ ใหม่

| คอมเมนต์เดิมอ้างว่า | ของจริง |
|---|---|
| `careers` ต้อง nullable เพราะ *"ถ้าข้อมูลจริงมีแถวที่ค่าเหล่านี้เป็น NULL การนำเข้าจะล้ม"* | `careers IS NULL` = **0** · `careers = '{}'` = **12** — ข้อมูลไม่บังคับ ที่ทำ nullable เพราะตรงกับ **ชนิดที่ต้นทางประกาศ** |
| `slug` ต้อง nullable เพราะ *"ถ้าข้อมูลจริงมีแถวที่ slug เป็น NULL การนำเข้าจะล้มทั้งก้อน"* | `slug IS NULL` = **0** ทั้ง 15 แถว — เหตุผลเดียวกัน |

ปล่อยไว้จะทำให้คนอ่านย้อนหลังเข้าใจว่าเคยมีแถว NULL อยู่จริง ซึ่งไม่เคยมี

### 1.4 รอบนี้ — บันทึกว่า `is_published` ไม่มีคอลัมน์ต้นทาง ⬅ ใหม่

### 1.5 รอบก่อน — Live evidence ยืนยันว่าถูก ไม่ย้อน

| การแก้รอบก่อน | Live evidence | คำตัดสิน |
|---|---|---|
| `detail` → nullable | `detail IS NULL` = **11 / 12** | **ยืนยัน — ข้อมูลบังคับ** ถ้าคง NOT NULL จะล้ม 11 แถว |
| `careers` → nullable | `careers IS NULL` = 0 | **คงไว้** แต่เปลี่ยนเหตุผลเป็น "ตรงกับชนิดต้นทาง" |
| trigger 4 ตัว `BEFORE UPDATE` | ต้นทางมี `update_updated_at_column()` บน 4 ตาราง เปิดใช้งานครบ | **ยืนยัน** |
| `GRANT EXECUTE` ฟังก์ชัน trigger | จำเป็นทางเทคนิค | **ยืนยัน** |

---

## 2. เหตุผลที่แก้ และหลักฐานจาก Live Verification

### 2.1 ความกว้าง `title` — M5

```sql
-- information_schema.columns บน production (ข้อ 5.1)
news.title                varchar(500)
external_news.title       varchar(500)
knowledge_articles.title  varchar(500)
courses.title             varchar(255)   <- ต่างจากสามตัวบน
courses.title_en          varchar(255)
```

ความยาวจริงที่วัดได้ (ข้อ M5)

| คอลัมน์ | ต้นทาง | 005 เดิม | ยาวสุดตอนนี้ | เกิน 255 |
|---|---|---|---:|---:|
| `news.title` | varchar(500) | VARCHAR(255) | 74 | 0 |
| `external_news.title` | varchar(500) | VARCHAR(255) | 120 | 0 |
| `knowledge_articles.title` | varchar(500) | VARCHAR(255) | — (0 แถว) | 0 |

**ข้อมูลชุดนี้ import ผ่านทุกแถว** — ถ้าวัดแค่ "migrate สำเร็จไหม" จะมองไม่เห็นปัญหานี้เลย

เหตุผลที่ยังต้องแก้: วันที่มีข่าวชื่อยาวเกิน 255 ต้นทางจะรับได้แต่ปลายทางจะไม่รับ
และ **จะพังตอน sync ไม่ใช่ตอน migrate** ซึ่งหายากกว่ามาก — ตอนนั้นไม่มีใครเชื่อมโยง
กลับมาถึง migration ที่รันผ่านไปหลายเดือนแล้ว

`external_news.title` ยาวสุด 120 อยู่แล้ว คือเกินครึ่งทางไป 255 แล้ว และข่าวมาจาก
เว็บคณะที่ไม่มีใครคุมความยาวหัวข้อ

### 2.2 `news.status` — M1 ปิดเคสได้

```sql
SELECT status, count(*) FROM public.news GROUP BY status;
-- published  3     ไม่พบ draft   ไม่พบ archived
```

| | ต้นทาง (ตรวจจริง) | 005 |
|---|---|---|
| ชนิด | `VARCHAR(20)` | `VARCHAR(50)` — กว้างกว่า ไม่ตัดค่า |
| NOT NULL | ใช่ | ใช่ |
| DEFAULT | `'published'` | `'published'` |
| CHECK | **ไม่มีเลย** | `IN ('published','draft','archived')` |

ทั้งฐาน Supabase มี CHECK แค่ **2 ตัว** คือ `ai_settings_singleton` และ
`rag_documents_source_type_check` — ยืนยันแล้วว่า `news.status` ไม่มี CHECK

**ผล: CHECK ของ 005 ไม่บล็อกข้อมูลชุดนี้** ทุกแถวผ่าน → M1 **CLOSED**

### 2.3 `detail` — M2 คือตัวเดียวที่จะทำให้ import ล้มจริง

```sql
-- ข้อ 10 ของรายงาน (count บน 12 แถว)
detail IS NULL            = 11      <- NOT NULL จะล้ม 11 แถว
careers IS NULL           = 0
careers = '{}'            = 12
logo IS NULL              = 0
created_by / updated_by IS NULL = 0 / 0
```

`DEFAULT '{}'` ช่วยได้เฉพาะตอน **ละคอลัมน์** ถ้า `INSERT ... SELECT` จากต้นทางตรง ๆ
ค่า NULL จะถูกส่งเข้ามาจริงและชน `NOT NULL`

ไฟล์ยังระบุด้วยว่า **ห้ามใช้ `COALESCE(detail, '{}')` ตอน import** เพราะ NULL
("ยังไม่ได้กรอก") กับ `'{}'` ("กรอกแล้วว่าไม่มี") ความหมายต่างกัน และแปลงแล้วกู้ไม่ได้

> หลักฐานเพิ่ม: มีแค่ **1 ใน 12 แถว** ที่ `detail` มีข้อมูล (วิทยาการคอมพิวเตอร์ 5 คีย์)

### 2.4 trigger `updated_at` — M12

```
ต้นทาง  update_updated_at_column()  BEFORE UPDATE  บน 4 ตาราง  tgenabled='O' ทั้งหมด
          courses · news · knowledge_articles · user_profiles
          external_news / rag_documents / ai_settings ไม่มี trigger
005 เดิม  0 trigger
```

ยืนยันว่าถูก และหลักฐานว่าปัญหานี้เกิดขึ้นได้จริง: ต้นทางเอง `rag_documents.updated_at`
มีคอลัมน์แต่ไม่มี trigger → ค่าค้างอยู่ที่เวลาสร้าง

**`ai_settings` ได้ trigger ด้วยทั้งที่ต้นทางไม่มี** — ยืนยันจาก live ว่าต้นทางไม่มีจริง
เป็นส่วนที่ต่างจากต้นทางโดยเจตนา (ให้ฐานข้อมูลทำเองเชื่อถือได้กว่าพึ่งแอป)
และเป็น UPDATE-only จึงไม่กระทบการนำเข้า

---

## 3. สิ่งที่ยังไม่แก้ และเหตุผล

### 3.1 ตัดสินใจไม่แก้ (ACCEPTED)

| # | ไม่แก้ | เหตุผลจาก Live evidence |
|---|---|---|
| 1 | **คง CHECK `news.status` 3 ค่า** ทั้งที่ต้นทางไม่มี CHECK | live เผยเหตุผลใหม่ที่หนักกว่าเดิม: RLS policy ที่ให้คนทั่วไปอ่าน `news` ใช้ `USING (status = 'published')` **ตรง ๆ** → คอลัมน์นี้คือ **ขอบเขตความปลอดภัย** ไม่ใช่ธงแสดงผล · เมื่อย้ายมาปลายทาง การกรองจะไปอยู่ที่โค้ดแอปซึ่งพลาดง่ายกว่า ให้ฐานข้อมูลปฏิเสธค่าที่ไม่รู้จักจึงยังคุ้ม · `archived` คงไว้เป็นค่าเผื่ออนาคต ความเสี่ยงต่อข้อมูลชุดนี้ = 0 (U2 ระบุว่าพิสูจน์ไม่ได้ทั้งสองทาง) |
| 2 | **คง `is_published BOOLEAN NOT NULL DEFAULT TRUE`** | M3: `public.courses` ไม่มีคอลัมน์ไหนสื่อความหมายนี้เลย และ RLS ของ `courses` เปิดให้ทุกคนอ่าน **ไร้เงื่อนไข** (`USING true`) ต่างจาก `news` → ของจริงหลักสูตรเผยแพร่หมด `DEFAULT TRUE` ให้ผลตรง · เป็นคอลัมน์ใหม่ ไม่มีข้อมูลต้นทางจะย้ายลงไป |
| 3 | **คง NOT NULL ที่ผ่อนลงจากต้นทาง** (`title_en`, `description`, `category`, `published_on`, `content`) | M4: ปลายทางหลวมกว่าต้นทาง → import ไม่ล้ม · บังคับเพิ่มตอนนี้เพิ่มความเสี่ยงโดยไม่มีประโยชน์ |
| 4 | **คง `synced_at` / `created_at` NOT NULL** ที่เข้มกว่าต้นทาง | M9: ต้นทาง nullable แต่ **NULL จริง = 0 ทั้งคู่** ทั้ง 15 แถว → ปลอดภัย |

### 3.2 Authorization / RLS — ตอนนี้มีหลักฐานครบแล้ว

ต่างจากรอบก่อนที่ต้อง STOP เพราะไม่รู้ว่า policy จริงเป็นอย่างไร **ตอนนี้รู้แล้ว**

```
RLS เปิดครบทั้ง 7 ตาราง · ไม่มีตารางใดตั้ง FORCE ROW SECURITY
policy บนตาราง 24 ตัว  +  policy บน storage.objects 8 ตัว  =  32 ตัว
ทุกตัวเป็น PERMISSIVE และผูกกับ role {public} — แยกสิทธิ์ด้วย auth.uid() ใน USING/WITH_CHECK
```

แม่แบบเดียวทั้งระบบ

```sql
EXISTS (SELECT 1 FROM user_profiles
        WHERE user_id = auth.uid() AND role IN ('admin','editor'))   -- insert / update
EXISTS (... AND role = 'admin')                                      -- delete
```

**พฤติกรรมที่ต้องรักษา — และสองข้อที่รายงานรอบก่อนเขียนผิด**

| ตาราง | ใครอ่านได้ที่ต้นทาง | หลังย้ายต้องบังคับที่ไหน |
|---|---|---|
| `courses` | **ทุกคน** `USING (true)` | API — เปิดสาธารณะ |
| `external_news` | **ทุกคน** `USING (true)` | API — เปิดสาธารณะ |
| `ai_settings` | **ทุกคน** `USING (true)` | API |
| `rag_documents` | **ทุกคน** `USING (true)` + policy `ALL` สำหรับ admin/editor | ยังไม่ย้าย |
| `news` | **`USING (status = 'published')`** · admin/editor เห็นทั้งหมด (policy แยกอีกตัว รวม 5 ตัว) | ⚠ API — **เป็นขอบเขตความปลอดภัย** |
| `knowledge_articles` | ⚠ **ไม่เปิดสาธารณะ** — SELECT ต้องเป็น `role IN (admin, editor)` | ⚠ API — ต้องกันการอ่าน ไม่ใช่แค่การเขียน |
| `user_profiles` | ทุกคน `USING (true)` **ขณะที่เก็บ `email` + `full_name`** | ยังไม่ย้าย — บันทึกไว้ |

> **สองข้อที่รายงานรอบก่อนผิด** — เคยเขียนว่า `knowledge_articles` อ่านได้สาธารณะ
> (ของจริงต้องเป็น admin/editor) และเคยนับ policy บนตารางเป็น 32 (ของจริง 24 บนตาราง
> + 8 บน storage) ข้อ `knowledge_articles` สำคัญเพราะเป็นเรื่องข้อมูลรั่ว ไม่ใช่เรื่องนับเลข

**Storage 8 policy** ใช้แม่แบบเดียวกัน · `course-assets` อ่านได้ทุกคน ·
`knowledge-files` อ่านได้เฉพาะ admin/editor · ไม่มี policy บน `storage.buckets`
(สร้าง/ลบ bucket ได้เฉพาะ service role)

**ชั้นที่ 005 ทำไว้แล้ว** — ยังถูกในขอบเขตของมัน

```
advisor_api      SELECT ทุกตาราง · INSERT/UPDATE 4 ตารางที่หน้าผู้ดูแลแก้ · เขียน external_news ไม่ได้
advisor_ingest   SELECT ทุกตาราง · INSERT/UPDATE เฉพาะ external_news
ไม่ให้ DELETE แก่ใครทั้งสิ้น  (ต้นทางให้ admin ลบได้ — เป็นการเปลี่ยนที่ตั้งใจ ตามหลัก 002/004)
```

GRANT กันได้ว่า *"บริการไหนเขียนตารางไหนได้"* แต่กันไม่ได้ว่า *"ผู้ใช้คนไหน"*

**ที่หายไปจริงถ้าย้ายตามโครงนี้** (M11)

1. **การแยก `admin` กับ `editor`** — ปลายทางเหลือแค่ "แอปเขียนได้ / เขียนไม่ได้"
2. `news` ที่คนทั่วไปเห็นเฉพาะ `published` → กลายเป็นหน้าที่โค้ดแอป **ไม่ใช่ฐานข้อมูล**
3. `knowledge_articles` ที่คนทั่วไป **อ่านไม่ได้เลย** → `advisor_api` SELECT ได้หมด
   การกรองย้ายไปอยู่ที่แอป

**ยังไม่แก้ 005 เรื่องนี้** — เป็นงานออกแบบชั้น API ที่ต้องทำก่อน import ไม่ใช่หลัง
และ **ไม่ใช่สิ่งที่ migration ไฟล์เดียวแก้ได้** แต่ไม่ใช่ blocker ที่ขาดหลักฐานอีกแล้ว
กลายเป็นงานที่ทำได้ทันทีเมื่อได้รับอนุมัติ

### 3.3 ที่ไม่แตะเลยตามคำสั่ง

`user_profiles` / Auth (M13) · Storage (M7) · embedding (M6) · ฟังก์ชัน
`match_rag_documents` / `rls_auto_enable` (M16) · `ivfflat lists` (M17) ·
anomaly A1–A3 ของต้นทาง

---

## 4. ผล Tests — **535 ผ่าน · 0 ไม่ผ่าน**

| ชุด | รอบก่อน | **รอบนี้** | หมายเหตุ |
|---|---:|---:|---|
| `web_schema_check` | 60 | **76** | +16 ข้อ (ความกว้างคอลัมน์) |
| `crawl_download_check` | 165 | **140** + ข้าม 1 | ⚠ ต่างเพราะแพลตฟอร์ม ดูข้างล่าง |
| `crawl_ingest_worker_check` | 187 | **187** | |
| `crawl_approval_check` | 84 | **84** | |
| `crawl_state_check` | 32 | **32** | |
| `document_endpoint_check` | 16 | **16** | |
| **รวมที่รันได้** | 544 | **535** | |

### ⚠ ตัวเลขเทียบกับรอบก่อนตรง ๆ ไม่ได้

`crawl_download_check` รอบก่อนรายงาน 165 — นั่นรันบน **Linux** รอบนี้รันบน **Windows**
ชุด `[5] สิทธิ์ของไฟล์ใน staging` (ข้อบกพร่อง F1) ข้ามทั้งกลุ่มด้วยเหตุผลที่ชัดเจน:

```
ข้าม  F1: ทั้งชุด — ระบบนี้ไม่ใช่ POSIX (os.name='nt') บิตโหมดไม่มีความหมาย
                    ต้องรันในคอนเทนเนอร์ Linux
```

**140 + 25 ข้อที่เป็น Linux-only = 165** ตัวเลขตรงกัน ไม่มีข้อใดเปลี่ยนจากผ่านเป็นไม่ผ่าน
และไม่มีข้อใดถูกนับว่าผ่านโดยที่ไม่ได้รัน (ชุดทดสอบแยก `ข้าม` ออกจาก `ผ่าน` ชัดเจน)

**รวมถ้ารันบน Linux = 560 ข้อ**

### ข้อที่เพิ่มรอบนี้ (16 ข้อ)

```
[1b] ความกว้างคอลัมน์เทียบกับต้นทาง
  11 ข้อ  คอลัมน์ varchar ทุกตัวที่เทียบได้ กว้างพอสำหรับต้นทาง
           (ตัวเลขทุกตัวมาจาก information_schema.columns ของ production)
   1 ข้อ  ไม่มีคอลัมน์ใดแคบกว่าต้นทางเลย
   3 ข้อ  news / external_news / knowledge_articles รับ title ยาว 500 ได้จริง
   1 ข้อ  news ปฏิเสธ title ที่ยาวเกิน 500
```

สามข้อสุดท้ายเป็นการพิสูจน์เชิงพฤติกรรม ไม่ใช่แค่อ่าน catalog

### สภาพแวดล้อม

```
PostgreSQL 16.15 (pgvector/pgvector:pg16) ในคอนเทนเนอร์แยก  127.0.0.1:55439
db/schema.sql (ฐานจริง)              OK
001 -> 005 จากฐานใหม่                 OK ทุกไฟล์
005 ลงซ้ำ (idempotency)               OK ไม่ error
role advisor_api / advisor_ingest     LOGIN + GRANT ตาม db/20-roles.sh

trigger ที่ได้  4 ตัว · tgtype = 19 ทุกตัว  (1 ROW + 2 BEFORE + 16 UPDATE — ไม่มีบิต 4 INSERT)
ความกว้าง title  external_news 500 · knowledge_articles 500 · news 500
                 site_courses.title 255 · site_courses.title_en 255

ทำความสะอาดแล้ว  containers 0 · volumes 0
```

---

## 5. M1–M17 — CLOSED / ACCEPTED / BLOCKED

| # | หัวข้อ | สถานะ | เหตุผล |
|---|---|---|---|
| **M1** | `news.status` CHECK | **CLOSED** | ค่าจริง `published` 3/3 · ไม่มี CHECK ต้นทาง · CHECK ของ 005 ไม่บล็อก · ปิดคอมเมนต์ PENDING DECISION แล้ว |
| **M2** | `detail NOT NULL` | **CLOSED** | `detail IS NULL` 11/12 → แก้เป็น nullable แล้ว |
| **M3** | `is_published` ไม่มีต้นทาง | **ACCEPTED** | RLS ของ `courses` เปิดสาธารณะไร้เงื่อนไข → `DEFAULT TRUE` ตรงกับของจริง · บันทึกในไฟล์แล้ว |
| **M4** | ชื่อคอลัมน์ไม่ตรง 3 คู่ | **CLOSED** | mapping ครบในข้อ 6 (`logo`→`logo_url` · `date`→`published_on` · `image`→`image_url`) |
| **M5** | `VARCHAR(255)` แคบกว่าต้นทาง 3 จุด | **CLOSED** | ขยายเป็น 500 แล้ว + ข้อตรวจ 16 ข้อกันถอยหลัง |
| **M6** | embedding 768 มิติ | **CLOSED** | ยืนยัน 12/12 เป็น 768 ไม่มี NULL → ห้าม copy ตรง · ขอบเขต re-embed = **12 chunk** ไม่ใช่ 9,039 |
| **M7** | `knowledge_articles` 0 แถว + PDF 4 ไฟล์ | **BLOCKED** | ต้องตัดสินใจเรื่องไฟล์ 10.4 MiB ที่ไม่มีแถวชี้ถึง · **ห้ามลบ** |
| **M8** | `external_news` กุญแจ | **CLOSED** | `detail_url` unique 15/15 ไม่ NULL · `slug` NULL 0 · partial unique เหมือนต้นทางเป๊ะ · แก้คอมเมนต์ที่ให้เหตุผลผิดแล้ว |
| **M9** | `synced_at`/`created_at` NOT NULL | **ACCEPTED** | ต้นทาง nullable แต่ NULL จริง 0 ทั้งคู่ → เข้มกว่าได้ ปลอดภัย |
| **M10** | `created_by`/`updated_by` เปลี่ยนเป้า FK | **BLOCKED** | ทั้ง 15 แถวจะได้ NULL ถ้าไม่ map ด้วยมือ (ดู B2) |
| **M11** | RLS 24+8 policy ไม่มีคู่ใน `web` | **BLOCKED** | หลักฐานครบแล้ว (ข้อ 3.2) แต่ต้องออกแบบชั้น API ก่อน import ไม่ใช่งานของ migration |
| **M12** | ไม่มี trigger ใน `web` | **CLOSED** | เพิ่ม 4 trigger + 8 ข้อตรวจแล้ว |
| **M13** | `user_profiles` ไม่มีที่ไป | **BLOCKED** | 3 แถว (admin 2 · user 1 · ไม่มี editor) ที่ทุก policy พึ่งพา — ต้องตัดสินใจเรื่อง auth |
| **M14** | Edge Function + cron | **ACCEPTED** | 005 ให้สิทธิ์ `advisor_ingest` ถูกแล้ว · แผน cutover อยู่ในข้อ 7.2 · ⚠ มีปัญหาที่มีอยู่ก่อนแล้ว (U3) |
| **M15** | `courses.category` ถูก DROP | **CLOSED** | `migration 20260904162441 drop_course_category_detail` · 005 ไม่มี `category` → ตรงกัน |
| **M16** | `match_rag_documents` / `rls_auto_enable` | **ACCEPTED** | อยู่นอกขอบเขต 005 · ต้องตัดสินใจตอนย้าย RAG ไม่ใช่ตอนนี้ |
| **M17** | `ivfflat lists=100` บน 12 แถว | **CLOSED** | ไม่กระทบความถูกต้อง · 005 ไม่สร้าง index นี้ · เลือกค่าใหม่ตอน re-embed |

```
CLOSED    9   M1 M2 M4 M5 M6 M8 M12 M15 M17
ACCEPTED  4   M3 M9 M14 M16
BLOCKED   4   M7 M10 M11 M13
```

ทั้ง 4 ข้อที่ BLOCKED เป็นเรื่อง **การตัดสินใจของเจ้าของ** ไม่ใช่การขาดหลักฐานอีกแล้ว

---

## 6. Proposed Import Mapping (แก้ตามคอลัมน์จริง)

**ยังไม่นำเข้า** · ทุกชนิดในคอลัมน์ "ต้นทาง" มาจาก `information_schema.columns` ของ production

### 6.1 `public.courses` (12 แถว) → `web.site_courses`

| ต้นทาง | ชนิดต้นทาง | ปลายทาง | ชนิดปลายทาง | การแปลง |
|---|---|---|---|---|
| `id` | `uuid` | — | — | **ไม่นำเข้า** — ปลายทางสร้างใหม่ |
| `title` | `varchar(255)` NOT NULL | `title` | `VARCHAR(255)` NOT NULL | ตรง · **ไม่ซ้ำ 12/12 ใช้เป็นกุญแจเทียบชั่วคราวได้** |
| `title_en` | `varchar(255)` **NOT NULL** | `title_en` | `VARCHAR(255)` null | หลวมกว่า · ⚠ **ห้ามใช้เป็นกุญแจจับคู่** — "เทคโนโลยีสารสนเทศ" มีค่าเป็น `Bachelor of Science` ซึ่งเป็นชื่อปริญญา |
| `description` | `text` **NOT NULL** | `description` | `TEXT` null | หลวมกว่า |
| **`logo`** | `text` | **`logo_url`** | `TEXT` | **เปลี่ยนชื่อ** · NULL 0/12 |
| `careers` | `text[]` null | `careers` | `TEXT[]` null | ตรง · ของจริงเป็น `'{}'` ทั้ง 12 แถว ไม่ใช่ NULL → **คัดลอกตรงได้** |
| `detail` | `jsonb` null | `detail` | `JSONB` null | ตรง · **NULL 11/12 ต้องคง NULL ไว้ ห้าม COALESCE** · 1 แถวมี 5 คีย์ · ⚠ PII (B4) |
| `created_at` / `updated_at` | `timestamptz` null | เหมือนกัน | NOT NULL | NULL จริง 0 → **คงค่าเดิม** (trigger ไม่ทำงานตอน INSERT) |
| `created_by` | `uuid` → **`auth.users(id)`** DEFAULT `auth.uid()` | `created_by` | `uuid` → `public.users(id)` | **ต้อง map** · ของจริงไม่ NULL 12/12 แต่ชี้บัญชีเดียวกันหมด (distinct = 1) |
| `updated_by` | `uuid` → **`user_profiles(user_id)`** | `updated_by` | `uuid` → `public.users(id)` | เช่นเดียวกัน |
| — | — | **`course_id`** | `uuid` → `public.courses(id)` | **ใหม่** · ตั้งเฉพาะคู่ `MATCHED` · `AMBIGUOUS`/`UNMATCHED` = NULL |
| — | — | **`is_published`** | `BOOLEAN NOT NULL DEFAULT TRUE` | **ใหม่ ไม่มีต้นทาง** (M3) |

### 6.2 `public.news` (3 แถว) → `web.news`

| ต้นทาง | ชนิดต้นทาง | ปลายทาง | ชนิดปลายทาง | การแปลง |
|---|---|---|---|---|
| `title` | **`varchar(500)`** NOT NULL | `title` | **`VARCHAR(500)`** NOT NULL | ตรง (แก้รอบนี้) |
| `description` | `text` **NOT NULL** | `description` | `TEXT` null | หลวมกว่า |
| `category` | `varchar(100)` **NOT NULL** | `category` | `VARCHAR(100)` null | หลวมกว่า · ค่าจริง: ข่าวรับสมัคร / กิจกรรม / ทุนการศึกษา |
| **`date`** | `date` **NOT NULL** | **`published_on`** | `DATE` null | **เปลี่ยนชื่อ** · ค่าจริงปี 2024 ขณะที่ `created_at` ปี 2026 (U4 — ยังไม่ตัดสินว่าเป็น seed) |
| **`image`** | `text` | **`image_url`** | `TEXT` | **เปลี่ยนชื่อ** · NULL 0/3 |
| `status` | `varchar(20)` NOT NULL DEFAULT `published` **ไม่มี CHECK** | `status` | `VARCHAR(50)` NOT NULL DEFAULT `published` + CHECK 3 ค่า | **นำเข้าได้** — ค่าจริง `published` ทั้ง 3 แถวผ่าน CHECK |
| `created_at` / `updated_at` | `timestamptz` null | เหมือนกัน | NOT NULL | คงค่าเดิม |
| `created_by` / `updated_by` | → `auth.users` / `user_profiles` | เหมือนกัน | → `public.users` | ต้อง map · ไม่ NULL 3/3 |

### 6.3 `public.external_news` (15 แถว) → `web.external_news`

| ต้นทาง | ชนิดต้นทาง | ปลายทาง | การแปลง |
|---|---|---|---|
| `detail_url` | `text` NOT NULL UNIQUE | `TEXT NOT NULL UNIQUE` | **กุญแจธรรมชาติ ใช้เป็น conflict key** · unique 15/15 NULL 0 → **B4 เดิมปิดแล้ว** |
| `slug` | `varchar(255)` null + partial unique | เหมือนกันเป๊ะ | NULL 0/15 · distinct 15/15 |
| `title` | **`varchar(500)`** NOT NULL | **`VARCHAR(500)`** NOT NULL | ตรง (แก้รอบนี้) |
| `source` | `varchar(100)` NOT NULL | เหมือนกัน | ค่าเดียว `sci_connect` ทั้ง 15 แถว |
| `published_text` | `varchar(100)` | `VARCHAR(255)` | ปลายทางกว้างกว่า ปลอดภัย · ยาวสุด 12 |
| `description` / `image_url` / `facebook_url` | `text` | เหมือนกัน | `image_url` NULL 0 · `facebook_url` มี 14/15 |
| `published_at` | `timestamptz` | เหมือนกัน | NULL 0 · ช่วง 2026-08-04 ถึง 2026-09-15 |
| `synced_at` / `created_at` | `timestamptz` **null** | **NOT NULL** | NULL จริง 0 → ผ่าน (M9) · `max(synced_at)` = **2026-09-22** ⚠ U3 |

### 6.4 `public.knowledge_articles` (**0 แถว**) → `web.knowledge_articles`

**ไม่มีแถวให้ย้าย** (M7) · ชื่อคอลัมน์ตรงกันทั้งหมด · `title` ขยายเป็น 500 แล้ว ·
`content` ต้นทาง NOT NULL ปลายทาง null (หลวมกว่า) ·
⚠ แต่ bucket `knowledge-files` มี **PDF 4 ไฟล์ 10,864,464 B (~10.4 MiB)**
ที่ไม่มีแถวใดชี้ถึง — **ห้ามลบ** ชื่อไฟล์เป็น UUID ล้วน ไม่มีทางรู้ว่าแต่ละไฟล์คืออะไร (U8)

### 6.5 `public.ai_settings` (1 แถว) → `web.ai_settings`

`id` `integer` DEFAULT 1 + CHECK `(id = 1)` → `SMALLINT` DEFAULT 1 + CHECK `(id = 1)`
— singleton เทียบเท่ากัน · `model` = `gemini-3.1-flash-lite` · `updated_at` 2026-08-25 ·
`updated_by` ไม่ NULL (ต้อง map)

### 6.6 `public.rag_documents` (12 แถว) → **ไม่นำเข้า**

```
embedding   vector(768) · ค่าจริง 768 มิติ 12/12 · NULL 0 · distinct dims 1
source_type 'major' ทั้ง 12 แถว (CHECK อนุญาต 4 ค่า — ข่าว/บทความยังไม่เคยเข้า RAG เลย)
source_id   distinct 12 · orphan เทียบ courses = 0
chunk_index max = 0  ->  1 หลักสูตร = 1 chunk
```

**ห้าม copy 768 → 1024** · ต้องนำ **source content** มา re-embed ด้วย `bge-m3` ·
**ขอบเขตงานจริง 12 chunk** ไม่ใช่ 9,039 เหมือนฝั่ง `mko` → งานเล็กมาก ·
ต้องตัดสินใจเรื่องฟังก์ชันค้นหา `match_rag_documents` ด้วย ไม่ใช่แค่ตาราง (M16) ·
**ยังไม่อนุญาตในรอบนี้**

### 6.7 `auth.users` (3) / `public.user_profiles` (3) → **ไม่นำเข้า**

```
auth.users     3 คน · ยืนยันอีเมลครบ 3 · เคยเข้าสู่ระบบครบ 3 · ไม่มี SSO · ไม่มี anonymous
user_profiles  admin/approved 2 · user/approved 1 · ไม่พบ editor เลย
linkage        profile จับคู่ auth user ได้ 3/3 · กำพร้า 0 · auth user ไร้ profile 0
ผู้เขียนเนื้อหา  distinct = 1 ทุกคอลัมน์ — เนื้อหาทั้งฐานสร้างโดยบัญชีเดียว
```

**ยังไม่ตัด Supabase Auth** · 005 ไม่มีตาราง role/สิทธิ์โดยเจตนา ·
map เฉพาะเพื่อเติม `created_by`/`updated_by` · **ห้ามเดา** (ดู B2)

---

## 7. ขั้นตอนถัดไป

### 7.1 ลำดับงาน

```
1. อนุมัติ commit การแก้ 2 ไฟล์ในรอบนี้

2. ตัดสินใจ 4 ข้อที่ BLOCKED — เป็นการตัดสินใจ ไม่ใช่การหาหลักฐานแล้ว
     M11 + M13  ออกแบบ authorization ชั้น API (สองข้อนี้คือข้อเดียวกันสองมุม)
     M10        จับคู่ผู้ใช้ 1 บัญชี (หรือยอมให้ created_by เป็น NULL ทั้ง 15 แถว)
     M7         ตัดสินใจเรื่อง PDF 4 ไฟล์ — ห้ามลบจนกว่าจะตัดสิน

3. ขออนุมัติแยกสำหรับ apply 005 กับ production database

4. ขออนุมัติแยกสำหรับ data migration ทีละตาราง
     เริ่มจาก ai_settings (1 แถว) -> courses (12) -> news (3)
     knowledge_articles ข้ามไปเลย (0 แถว)
     external_news ไว้ท้ายสุด เพราะมีผู้เขียนอัตโนมัติอยู่

5. cutover ของ sync-sci-news ตามข้อ 7.2

6. re-embed 12 chunk ด้วย bge-m3 (ขออนุมัติแยก)
```

### 7.2 Cutover ของ `sync-sci-news` — **แผนรอบก่อนไม่ครบ**

**ของจริงที่เพิ่งยืนยัน**

| | |
|---|---|
| Edge Function | `sync-sci-news` · **ACTIVE** · version 1 · `verify_jwt = true` · ยังไม่เคย redeploy |
| ตัวเรียก | **pg_cron job `sync-sci-news-every-30-min`** · `*/30 * * * *` · **active** · database `postgres` |
| เขียนตาราง | `external_news` ตารางเดียว · `source = 'sci_connect'` · `KEEP_LATEST = 15` |
| ของจริงตอนนี้ | 15 แถว · `source` ค่าเดียว · `max(synced_at)` = **2026-09-22** |

> ⚠ **แผนรอบก่อนบอกให้ปิดแค่ Edge Function ซึ่งไม่พอ** — ตัวที่ยิงจริงคือ **pg_cron job**
> ถ้าปิดแต่ Edge Function โดยไม่ปิด cron job ตัว cron จะยิงไปที่ endpoint ที่ไม่มีอยู่
> ทุก 30 นาทีไปเรื่อย ๆ และถ้ามีใคร deploy ฟังก์ชันกลับมาภายหลัง มันจะเริ่มเขียนทันที
> โดยไม่มีใครตั้งใจ · **ต้องปิดทั้งสองอย่าง**

**⚠ ปัญหาที่มีอยู่ก่อนแล้ว — ต้องแก้ก่อนคิดเรื่องย้าย**

cron เปิดอยู่ยิงทุก 30 นาที แต่ `max(synced_at)` ค้างที่ **2026-09-22** ห่างจากวันตรวจ
ประมาณ **10 วัน** (U3) ตีความไม่ได้ด้วยข้อมูลที่มี — เป็นไปได้ทั้ง

- **(ก)** ฟังก์ชันล้มเหลวเงียบ ๆ มา ~10 วัน
- **(ข)** ทำงานปกติแต่ไม่มีข่าวใหม่ และ upsert ไม่อัปเดต `synced_at` ของแถวเดิม

แยกสองกรณีต้องอ่าน Edge Function logs หรือ `cron.job_run_details`
**ถ้าเป็น (ก) การย้ายจะพาปัญหาไปด้วย** ควรรู้คำตอบก่อน

**ลำดับที่เสนอ**

```
สถานะ 0  pg_cron (*/30) -> Edge Function -> Supabase.external_news      <- ตอนนี้
         web.external_news ว่าง ไม่มีใครเขียน

ขั้น 0   ตรวจ U3 ก่อน — cron.job_run_details / Edge Function logs
         ถ้าตัวดึงข่าวพังอยู่ แก้ให้ได้ก่อน หรือยอมรับอย่างรู้ตัวว่าจะย้ายของที่พัง

ขั้น 1   เขียนงานดึงข่าวฝั่ง FastAPI ให้เสร็จ แต่ยังไม่เปิด
         ทดสอบในสภาพแวดล้อมแยก ยืนยันว่าได้ผลเหมือน Edge Function

ขั้น 2   นำเข้า external_news 15 แถว เข้า web.external_news ครั้งเดียว
         ใช้ detail_url เป็น conflict key (unique 15/15 ยืนยันแล้ว)

ขั้น 3   ⚠ จุดตัด — ต้องทำสามอย่างนี้ในหน้าต่างเดียวกัน
           ก. ปิด pg_cron job   (UPDATE cron.job SET active=false ... หรือ cron.unschedule)
           ข. ปิด/ถอน Edge Function
           ค. เปิดงานดึงข่าวฝั่ง FastAPI
         ห้ามให้ทั้งสองฝั่งเปิดพร้อมกันแม้ชั่วครู่

ขั้น 4   เฝ้าดูอย่างน้อย 2 รอบ sync (1 ชั่วโมง) ว่าจำนวนและเนื้อหาตรงกับที่เคยเป็น
         เทียบ 15 แถวเดิมด้วย detail_url

ขั้น 5   เปลี่ยน /api/sci-connect-news* ให้อ่านจาก web.external_news

ขั้น 6   เมื่อมั่นใจแล้วค่อยลบ Edge Function — ไม่ใช่ก่อนหน้านั้น
```

**ถ้าทั้งคู่เปิดพร้อมกัน**

| ปัญหา | ผล |
|---|---|
| เขียนคนละฐานข้อมูล | ข้อมูลสองชุดไม่ตรงกัน หน้าเว็บเห็นชุดหนึ่ง AI เห็นอีกชุด |
| ทั้งคู่ prune ให้เหลือ 15 | ลบของกันเอง นับจำนวนไม่ตรง |
| ทั้งคู่ insert | `detail_url UNIQUE` กันซ้ำได้ แต่ฝั่งที่แพ้จะ error รัว |

**จุดถอนกลับ**: จนถึงขั้น 4 ยังเปิด cron + Edge Function กลับและปิดงานใหม่ได้
โดยข้อมูลฝั่ง Supabase ยังครบ

---

## 8. Blockers ที่เหลือจริงก่อน Data Migration

รอบก่อนมี 8 ข้อ **ปิดได้ 4 ข้อจาก Live evidence** เหลือ 4 ข้อ ทุกข้อเป็นการตัดสินใจ

| # | Blocker | ต้องตัดสินอะไร | ระดับ |
|---|---|---|---|
| **B1** | **Authorization ชั้น API** (M11 + M13) | 32 policy ต้องกลายเป็นเงื่อนไขที่ API ตรวจ · จุดที่พลาดไม่ได้: `news` ที่คนทั่วไปเห็นเฉพาะ `published` และ `knowledge_articles` ที่คนทั่วไป**อ่านไม่ได้เลย** · ต้องตัดสินด้วยว่าจะรักษาการแยก admin/editor ไหม (ของจริง**ยังไม่มีใครถือ editor**) | **สูงสุด** |
| **B2** | **จับคู่ผู้ใช้** (M10) | เนื้อหาทั้งฐานเขียนโดย **บัญชีเดียว** (distinct = 1) → ตัดสินแค่ 1 ราย ไม่ใช่ 3 · ทางเลือก: จับคู่ด้วยมือ 1 ราย **หรือ** ยอมให้ `created_by`/`updated_by` เป็น NULL ทั้ง 15 แถวแล้วเสียข้อมูลผู้เขียน | **สูง** |
| **B3** | **PDF กำพร้า 4 ไฟล์ 10.4 MiB** (M7) | `knowledge_articles` 0 แถว แต่ bucket มี 4 ไฟล์ที่ไม่มีใครชี้ถึง · ชื่อเป็น UUID ล้วน ไม่มีทางรู้ว่าคืออะไร (U8) · **ห้ามลบ** — ตัดสินว่าเก็บไว้ที่เดิม / ย้าย / สร้างแถวให้ใหม่ | **กลาง** |
| **B4** | **PII ใน `courses.detail`** | มี 1 แถวที่มี `detail` (5 คีย์) ซึ่งมี `faculty[].email` · รีโปหน้าเว็บเป็น public · ตัดสินก่อนนำเข้า | **กลาง** |

### Blockers รอบก่อนที่ปิดได้แล้ว

| เดิม | ปิดด้วยอะไร |
|---|---|
| ~~ยังไม่มีผล Live Verification~~ | ได้ไฟล์ 1,165 บรรทัด ตรวจ production จริง 32 คำสั่ง |
| ~~`news.status` Pending Decision~~ | `published` 3/3 · ไม่มี CHECK ต้นทาง (M1) |
| ~~schema drift ของ snapshot~~ | อ่านจาก catalog จริง ไม่ใช่ snapshot แล้ว · `list_migrations` ยืนยัน 3 migration ล่าสุด |
| ~~`detail_url` อาจซ้ำ~~ | unique 15/15 · NULL 0 (M8) |

### ที่ยังไม่พิสูจน์ แต่ไม่บล็อก

`U1` `read_only` บังคับที่เซิร์ฟเวอร์จริงไหม · `U2` `draft`/`archived` มีใช้จริงไหม ·
`U3` ⚠ ตัวดึงข่าวค้าง 10 วัน (ดูข้อ 7.2 ขั้น 0) · `U4` `news.date` ปี 2024 เป็น seed ไหม ·
`U6` โมเดลที่สร้าง embedding 768 · `U7` ฝั่งปลายทางยังไม่ถูกตรวจด้วย MCP ตัวนี้ ·
`U9` performance advisors ยังไม่เรียก

### Anomaly ของต้นทางที่พบระหว่างทาง — ไม่เกี่ยวกับ 005 ไม่แก้ในรอบนี้

| | |
|---|---|
| **A1** | `user_profiles_user_id_fkey` ชี้ `user_profiles(user_id)` **กลับตัวเอง** — ผ่านได้เสมอโดยไม่ตรวจอะไร เข้าข่ายตั้งใจจะชี้ `auth.users(id)` แต่พิมพ์ผิด · ตอนนี้ยังไม่เกิดผลเสีย (จับคู่ครบ 3/3) |
| **A2** | `user_id` มี **3 index** โดย 2 ตัวซ้ำกันสนิท (`user_profiles_user_id_key` + `user_profiles_user_id_unique`) — ร่องรอยว่า migration ถูกรันทับกัน |
| **A3** | `rag_documents.source_type` ใช้ `major` ค่าเดียวจาก 4 ค่าที่อนุญาต → RAG ปัจจุบัน **ตอบได้แต่เรื่องหลักสูตร** ข่าวและบทความยังไม่เคย index เข้า RAG |
| **advisors** | Supabase รายงาน security lint ระดับ `WARN` 5 ชนิด ไม่มี `ERROR` — รวม `function_search_path_mutable` 4 ฟังก์ชัน และ `auth_leaked_password_protection` ปิดอยู่ |

---

## สรุปการเปลี่ยนแปลงในรอบนี้

```
FILES CHANGED:                    2  (+257 −18)
TESTS:                            535 ผ่าน · 0 ไม่ผ่าน   (+25 Linux-only = 560)
M1-M17:                           CLOSED 9 · ACCEPTED 4 · BLOCKED 4

APPLY MIGRATION ON PRODUCTION:    NONE
DATA MIGRATION:                   NONE
PRODUCTION WRITE:                 NONE
SUPABASE WRITE:                   NONE
RE-EMBED:                         NONE
DEPLOY / RESTART:                 NONE
MERGE main:                       NONE
COMMIT / PUSH:                    NONE
```

---

## STOP

**รออนุมัติก่อนดำเนินการขั้นถัดไป**

1. **อนุมัติ commit การแก้ 2 ไฟล์ในรอบนี้หรือไม่**
2. **B1 — Authorization ชั้น API**: จะรักษาการแยก admin/editor ไหม ทั้งที่ของจริง
   ยังไม่มีใครถือ `editor`
3. **B2 — ผู้เขียนเนื้อหา 1 บัญชี**: จับคู่ด้วยมือ หรือยอมให้เป็น NULL ทั้ง 15 แถว
4. **U3 — ตัวดึงข่าวค้าง 10 วัน**: ให้ตรวจก่อนวางแผน cutover ไหม
