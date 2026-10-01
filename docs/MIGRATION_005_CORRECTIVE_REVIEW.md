# Migration 005 — Corrective Review

| | |
|---|---|
| วันที่ | 2026-10-01 |
| สาเหตุ | `SUPABASE_PRE_MIGRATION_AUDIT.md` พบว่าข้อเท็จจริงที่ใช้สร้าง migration 005 บางส่วนผิด |
| ขอบเขต | แก้เฉพาะสิ่งที่ยืนยันได้จาก `supabase_schema.sql` และ source code จริง |
| **ผลทดสอบ** | **536 ข้อ ผ่าน · 0 ไม่ผ่าน** (เพิ่มจาก 531) |
| **สถานะ** | **แก้ใน working tree แล้ว · ยังไม่ commit · ยังไม่ push** |
| **Production write / deploy / restart** | **NONE** |

```
APPLY 005 กับ PRODUCTION     NONE          เขียน Supabase            NONE
DATA MIGRATION               NONE          ใช้ anon key bypass        NONE
แก้ Auth / RLS / Storage      NONE          RAG migration / re-embed   NONE
DEPLOY / RESTART             NONE          merge main                 NONE
COMMIT / PUSH                NONE
```

---

## 1. Root cause ของข้อมูลเดิมที่ผิด

### 1.1 ต้นตอ

ข้อเท็จจริงเรื่อง schema ของต้นทางที่ใช้ตอนออกแบบ migration 005 มาจาก
**`docs/database/schema.json`** ซึ่งเป็นไฟล์ที่เครื่องมือตัวหนึ่งสร้างไว้ก่อนหน้า

เครื่องมือนั้น **parse constraint ที่ประกาศระดับคอลัมน์ไม่ได้** คือรูปแบบ

```sql
created_by UUID DEFAULT auth.uid() REFERENCES auth.users(id),      -- FK ไม่ถูกนับ
id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),                   -- CHECK ไม่ถูกนับ
user_id UUID UNIQUE,                                               -- UNIQUE ไม่ถูกนับ
detail_url TEXT NOT NULL UNIQUE,                                   -- UNIQUE ไม่ถูกนับ
```

มันนับเฉพาะ constraint ที่ประกาศแยกเป็นบรรทัดของตัวเอง (`UNIQUE (a, b, c)`)
จึงรายงานออกมาเป็น **FK 0 · CHECK 0 · UNIQUE 1** และยังอ่านชนิดเวลาเป็น `TIMESTAMP`
แทนที่จะเป็น `TIMESTAMP WITH TIME ZONE`

### 1.2 ทำไมจึงไม่ถูกจับได้เร็วกว่านี้

ตอนทำ `DATABASE_CONSOLIDATION_AUDIT.md` ผมค้นหา `supabase_schema.sql` ในที่เก็บโค้ดนี้
**ไม่พบ** จึงบันทึกไว้เป็น `UNKNOWN` (ข้อ U10) แล้วใช้ `schema.json` เป็นแหล่งข้อมูลแทน
โดยไม่ได้ตั้งคำถามว่าตัวเลข `0 / 0 / 1` ผิดปกติหรือไม่

ความจริงคือไฟล์นั้นอยู่ใน **รีโปของหน้าเว็บ** (`github.com/FoMake/Univercity`)
ซึ่งมี clone อยู่ในเครื่องผู้พัฒนาที่ `D:\workspace\LastProject` มาตลอด —
พบในรอบ pre-migration audit เพราะคราวนี้ค้น remote ของทุก repo ในเครื่อง

### 1.3 บทเรียนที่บันทึกไว้

ตัวเลข **0 FK · 0 CHECK** สำหรับฐานข้อมูลที่ใช้งานจริง 7 ตารางเป็นค่าที่ผิดปกติพอ
ที่ควรจุดคำถาม แต่กลับถูกนำไปใช้เป็นเหตุผลหลักของการออกแบบและเขียนลงเอกสาร
หลายฉบับโดยไม่ได้ตรวจกับเอกสารต้นทาง

---

## 2. ไฟล์ที่แก้ — 6 ไฟล์

```
db/migrations/005_web_schema.sql          +53 −20   schema + คอมเมนต์
eval/web_schema_check.py                  +37  −9   ข้อตรวจ + docstring
docs/MIGRATION_005_WEB_SCHEMA_REVIEW.md   +33 −22
docs/TARGET_ARCHITECTURE.md                +6  −6
docs/DATABASE_CONSOLIDATION_AUDIT.md       +8  −1
docs/EMBEDDING_PATH_AUDIT.md               +1  −1
```

และใส่ **แบนเนอร์แจ้งข้อผิดพลาด** ไว้หัวรายงานเชิงประวัติสองฉบับ โดย **ไม่แก้เนื้อใน**
เพราะเป็นบันทึกว่าเกิดอะไรขึ้นตอนนั้น

```
docs/MIGRATION_005_COMMIT_REPORT.md
docs/MIGRATION_005_PUSH_REPORT.md
```

**ไม่แก้** `docs/SUPABASE_PRE_MIGRATION_AUDIT.md` เพราะเป็นเอกสารที่ทำหน้าที่แก้เอง

---

## 3. SQL ก่อน / หลัง

### 3.1 `web.external_news` — ข้อ 1 ของงานรอบนี้

**ก่อน** — กลับด้านกับต้นทาง

```sql
slug            VARCHAR(255) NOT NULL UNIQUE,
detail_url      TEXT,
source          VARCHAR(100),
```

**หลัง** — ตรงกับต้นทาง

```sql
slug            VARCHAR(255),
detail_url      TEXT         NOT NULL UNIQUE,
source          VARCHAR(100) NOT NULL,
```

เพิ่ม partial unique index

```sql
CREATE UNIQUE INDEX IF NOT EXISTS uq_external_news_slug
    ON web.external_news (slug) WHERE slug IS NOT NULL;
```

**เทียบกับต้นทางทีละข้อ**

| | ต้นทาง (`supabase_schema.sql:138-155`) | 005 ก่อนแก้ | 005 หลังแก้ |
|---|---|---|---|
| `detail_url` | `TEXT NOT NULL UNIQUE` | `TEXT` nullable | **`TEXT NOT NULL UNIQUE`** ✓ |
| `slug` | `VARCHAR(255)` nullable | `NOT NULL UNIQUE` | **nullable** ✓ |
| unique ของ `slug` | `UNIQUE INDEX … WHERE (slug IS NOT NULL)` | เป็น column UNIQUE | **partial unique** ✓ |
| `source` | `VARCHAR(100) NOT NULL` | nullable | **`NOT NULL`** ✓ |

**ความเสี่ยงที่ปิดไป**: ถ้าปล่อยของเดิมไว้แล้วข้อมูลจริงมีแถวที่ `slug` เป็น NULL
การนำเข้าจะล้มทั้งก้อน · ต้นทางให้ `slug` เป็น NULL ได้ จึงเป็นไปได้สูงว่ามีแถวแบบนั้น

### 3.2 `web.news.status` — ข้อ 2 · **ยังไม่แก้ · Pending Decision**

**ไม่เปลี่ยน SQL** คงไว้เป็น

```sql
status VARCHAR(50) NOT NULL DEFAULT 'published'
       CHECK (status IN ('published', 'draft', 'archived')),
```

**เหตุผลของการวิเคราะห์**

| ทางเลือก | ผล | ตัดสิน |
|---|---|---|
| ตัดเหลือ `('published','draft')` ตามคอมเมนต์ต้นทาง | **เสี่ยงกว่าเดิม** — ถ้าข้อมูลจริงมีค่าที่สาม การนำเข้าจะล้มทั้งก้อน · ขัดกับข้อห้าม "ห้ามทำการเปลี่ยนแปลงที่อาจทำให้ข้อมูลจริง import ไม่ได้" | **ไม่ทำ** |
| เพิ่มค่าอื่นเข้าไปอีก | เป็นการเดาซ้อนเดา · ขัดกับข้อห้าม "ห้ามเดาค่าเพิ่ม" | **ไม่ทำ** |
| ถอด CHECK ออกทั้งหมด | ตรงกับต้นทางที่สุด (ต้นทางไม่มี CHECK) และ import ไม่มีทางล้ม แต่เสียการป้องกันที่เป็นเหตุผลหนึ่งของ schema นี้ | **ไม่ทำในรอบนี้** |
| **คงไว้ + บันทึกเป็น Pending Decision** | ไม่เพิ่มความเสี่ยงจากสถานะปัจจุบัน และไม่ยืนยันสิ่งที่ยังพิสูจน์ไม่ได้ | **เลือกทางนี้** |

**แก้คอมเมนต์ให้ตรงความจริงแทน** — ระบุชัดใน migration ว่า

- ต้นทาง **ไม่มี CHECK** บนคอลัมน์นี้เลย ฐานข้อมูลจึงไม่เคยบังคับค่า
- คอมเมนต์ต้นทางระบุเพียง `published | draft`
- **`archived` ยังไม่มีหลักฐานว่ามีอยู่จริง** — เป็นค่าที่ใส่ไว้เองโดยไม่ได้ตรวจข้อมูล
- ทางที่ถูกคือรัน `SELECT DISTINCT status FROM public.news` บนต้นทางก่อน
  **ซึ่งต้องมีสิทธิ์ member ของโปรเจกต์ต้นทาง**

> **ห้ามนำเข้าข้อมูลตาราง `news` จนกว่าจะยืนยันค่านี้**

### 3.3 คอมเมนต์เรื่อง constraint — ข้อ 4

**ก่อน**

```
-- ทำไมใส่ FK ทั้งที่ของเดิมไม่มี
-- schema เดิมฝั่งหน้าเว็บมี foreign key 0 ตัว check constraint 0 ตัว และ unique
-- 1 ตัวทั้งฐาน (ที่มา: docs/database/schema.json)
```

**หลัง**

```
-- ความสัมพันธ์ที่ประกาศไว้ และที่เพิ่มเข้ามา
-- schema ต้นทางมี foreign key 7 เส้น check constraint 2 ตัว และ unique 4 ตัว
-- (ที่มา: supabase_schema.sql ในรีโปของหน้าเว็บ ซึ่งเป็น snapshot ที่ดึงจากโปรเจกต์จริง
-- แบบ read-only ไม่เกิน 2026-09-23)
--
-- หมายเหตุประวัติ: เอกสารรุ่นก่อนหน้าเคยระบุว่าต้นทางมี "FK 0 · CHECK 0 · UNIQUE 1"
-- ซึ่งผิด …
```

### 3.4 คอมเมนต์เรื่องเวลา — ข้อ 3

**ก่อน**

```
-- ทำไม timestamptz ไม่ใช่ timestamp
-- ของเดิมเป็น TIMESTAMP ไม่มีเขตเวลา …
-- ตอนนำข้อมูลเข้าต้องระบุเขตเวลาให้ชัดว่าค่าที่เก็บไว้เดิมเป็นเวลาอะไร
```

**หลัง**

```
-- เรื่องเวลา
-- ต้นทางใช้ TIMESTAMP WITH TIME ZONE ทุกคอลัมน์เวลา และที่นี่ใช้ timestamptz
-- ซึ่งเป็นชนิดเดียวกัน การย้ายจึงไม่ต้องตีความหรือระบุเขตเวลาเพิ่ม
--
-- หมายเหตุประวัติ: เอกสารรุ่นก่อนหน้าเคยระบุว่า … เตือนว่าเวลาอาจคลาด 7 ชั่วโมง
-- ข้อนั้นผิด ไม่มีความเสี่ยงดังกล่าว
```

**คำเตือนเรื่อง 7 ชั่วโมงถูกลบออกจากทุกที่ที่เป็นข้ออ้าง** เหลือเฉพาะในหมายเหตุที่บอกว่า
ข้ออ้างนั้นผิด

### 3.5 RAG / `vector` — ข้อ 4

แก้ทุกที่ที่เคยเขียนว่า `rag_documents` เป็น `vector(768)` ในฐานะข้อบังคับของคอลัมน์
ให้ระบุให้ถูกว่า

| ข้อเท็จจริง | สถานะ |
|---|---|
| คอลัมน์ต้นทางประกาศเป็น **`vector` ไม่ล็อกมิติใน schema snapshot** | VERIFIED (`supabase_schema.sql:107`) |
| คอมเมนต์ในไฟล์เขียนว่า "ขนาด vector ขึ้นกับโมเดล embedding ที่ใช้" | VERIFIED |
| application ตั้ง `EMBEDDING_DIMENSIONS = 768` | VERIFIED (`api/_lib/rag.js:7`) |
| **มิติของข้อมูลจริงที่เก็บอยู่** | **UNKNOWN** |
| ข้อกำหนดปลายทาง `bge-m3` / `1024` / cosine / IVFFlat | **ไม่เปลี่ยน** |
| RAG migration / re-embedding | **ยังห้าม** |

ที่ `docs/DATABASE_CONSOLIDATION_AUDIT.md` ยังคงยกคอมเมนต์ในโค้ดของทีมออกแบบมาตามจริง
(`// Must match the vector(768) column …`) เพราะเป็นข้อความที่เขาเขียนไว้จริง
แต่เพิ่มหมายเหตุใต้บล็อกนั้นว่าคอลัมน์จริงไม่ได้ล็อกมิติ

ข้อสรุปหลักไม่เปลี่ยน: **ห้าม copy/convert เข้า `vector(1024)` โดยตรง
ต้องนำ source content มา re-embed ด้วย `bge-m3` ใหม่ และออกแบบให้ resume/retry ได้**

---

## 4. Tests

### 4.1 ผลรวม — **536 / 536 ผ่าน · 0 ไม่ผ่าน**

| ชุด | ก่อนแก้ | **หลังแก้** |
|---|---:|---:|
| `eval/web_schema_check.py` | 47 | **52** (+5) |
| `eval/crawl_download_check.py` | 165 | 165 |
| `eval/crawl_ingest_worker_check.py` | 187 | 187 |
| `eval/crawl_approval_check.py` | 84 | 84 |
| `eval/crawl_state_check.py` | 32 | 32 |
| `eval/document_endpoint_check.py` | 16 | 16 |
| **รวม** | 531 | **536** |

### 4.2 Migration 001 → 005 จากฐานทดสอบใหม่

```
001_mko_structured      OK
002_mko_review_publish  OK
003_crawl_sources       OK
004_crawl_decisions     OK
005_web_schema          OK
```

### 4.3 Idempotency

ลง `005` ซ้ำอีกครั้งทันที — **ไม่ error**

### 4.4 constraint ที่ได้หลังแก้

```
ก่อน   ตาราง 5 · FK 8 · CHECK 3 · UNIQUE 7
หลัง   ตาราง 5 · FK 8 · CHECK 3 · UNIQUE 8     (+1 จาก detail_url UNIQUE)
```

### 4.5 ข้อตรวจใหม่ที่เพิ่มเข้ามา 5 ข้อ

```
external_news: detail_url ซ้ำถูกปฏิเสธ
external_news: detail_url เป็น NULL ถูกปฏิเสธ
external_news: source เป็น NULL ถูกปฏิเสธ
external_news: หลายแถวที่ slug เป็น NULL อยู่ร่วมกันได้      ← ข้อสำคัญที่สุด
external_news: slug ที่มีค่าซ้ำกันถูกปฏิเสธ
```

ข้อที่สี่คือข้อที่พิสูจน์ว่าความเสี่ยง "นำเข้าล้มทั้งก้อนเพราะ slug เป็น NULL"
ถูกปิดแล้วจริง — ของเดิมข้อนี้จะไม่ผ่าน

### 4.6 สภาพแวดล้อมที่ใช้

```
PostgreSQL 16.15 ในคอนเทนเนอร์แยก (compose project sci-advisor-e2e)
ฐานข้อมูล  web_test · crawl_test        ← ไม่ใช่ production
ด่านกัน     URL ห้ามมีคำว่า course_advisor · ถาม current_database() ซ้ำอีกชั้น
ทำความสะอาดแล้ว: containers 0 · volumes 0 · images 0
```

---

## 5. สิ่งที่ยัง UNKNOWN

| # | ยังไม่รู้ | ผลต่อ migration 005 |
|---|---|---|
| U1 | **ค่า `news.status` ที่มีอยู่จริง** | CHECK ยังเป็น Pending Decision · **ห้ามนำเข้าตาราง `news` จนกว่าจะรู้** |
| U2 | **มิติจริงของ `rag_documents.embedding`** | ไม่กระทบ 005 (ไม่มีตาราง vector) · กระทบแผน RAG ในอนาคต |
| U3 | row count ทุกตาราง | ประเมินเวลานำเข้าไม่ได้ |
| U4 | **มีแถวที่ `slug` เป็น NULL จริงกี่แถว** | แก้แล้วให้รองรับ แต่ยังไม่รู้ว่ามีจริงกี่แถว |
| U5 | **มีแถวที่ `detail_url` ซ้ำกันไหม** | ถ้ามี การนำเข้าจะล้มเพราะ UNIQUE ใหม่ — แต่ต้นทางก็มี UNIQUE นี้อยู่แล้ว จึงไม่ควรมี |
| U6 | **มีแถวที่ `source` เป็น NULL ไหม** | ต้นทางบังคับ NOT NULL อยู่แล้ว จึงไม่ควรมี |
| U7 | สถานะ RLS ที่เปิดอยู่จริง (เทียบกับ snapshot) | ไม่กระทบ 005 · กระทบการออกแบบ authorization |
| U8 | จำนวนไฟล์และขนาดใน 2 storage bucket | กระทบแผนย้ายไฟล์แนบ |
| U9 | อีเมลใน `auth.users` ทับกับ `public.users` กี่ราย | กระทบการ map `created_by`/`updated_by` |
| U10 | `supabase_schema.sql` ตรงกับ schema ปัจจุบันหรือยัง | snapshot ลงวันที่ไม่เกิน 2026-09-23 · อาจมีการแก้หลังจากนั้น |

**U10 สำคัญกว่าที่เห็น** — การแก้รอบนี้ทั้งหมดอิง snapshot นั้น ถ้า schema เปลี่ยน
หลังวันที่นั้น การแก้นี้ก็จะคลาดอีก ต้องยืนยันกับของจริงเมื่อมีสิทธิ์เข้าถึง

---

## 6. สิ่งที่ยังต้องรอ Supabase Member access

| # | คำสั่งที่ต้องรัน | ใช้ตอบ | ปลดล็อกอะไร |
|---|---|---|---|
| 1 | `SELECT DISTINCT status FROM public.news` | U1 | **ปลดล็อกการนำเข้าตาราง `news`** |
| 2 | `SELECT count(*) FROM <ทุกตาราง>` | U3 | ประเมินเวลา |
| 3 | `SELECT count(*) FROM external_news WHERE slug IS NULL` | U4 | ยืนยันว่าการแก้รอบนี้จำเป็นจริง |
| 4 | `SELECT vector_dims(embedding) FROM rag_documents LIMIT 1` | U2 | แผน RAG |
| 5 | `SELECT relrowsecurity FROM pg_class …` | U7 | ออกแบบ authorization |
| 6 | รายการไฟล์ใน 2 bucket | U8 | แผนย้ายไฟล์ |
| 7 | อีเมลใน `auth.users` / `user_profiles` | U9 | แผน map ผู้ใช้ |
| 8 | `pg_dump --schema-only` เทียบกับ snapshot | U10 | ยืนยันว่า snapshot ยังตรง |

**วิธีขอ**: Supabase Dashboard → Organization → **Team** → **Invite member**
ระดับ **Developer ขึ้นไป** · **ห้ามใช้บัญชีหรือ credential ของผู้อื่น**

---

## 7. `git diff --stat`

```
 db/migrations/005_web_schema.sql        | 73 ++++++++++++++++++++++++---------
 docs/DATABASE_CONSOLIDATION_AUDIT.md    |  9 +++-
 docs/EMBEDDING_PATH_AUDIT.md            |  2 +-
 docs/MIGRATION_005_WEB_SCHEMA_REVIEW.md | 55 +++++++++++++++----------
 docs/TARGET_ARCHITECTURE.md             | 12 +++---
 eval/web_schema_check.py                | 46 ++++++++++++++++-----
 6 files changed, 135 insertions(+), 62 deletions(-)
```

`git diff --check`: ว่าง · CRLF ในทุกไฟล์ที่แก้: **0**

ไฟล์ untracked ที่เกี่ยวข้อง (ยังไม่ commit)

```
docs/SUPABASE_PRE_MIGRATION_AUDIT.md     ← ที่มาของการแก้รอบนี้
docs/MIGRATION_005_COMMIT_REPORT.md      ← ใส่แบนเนอร์แจ้งข้อผิดพลาดแล้ว
docs/MIGRATION_005_PUSH_REPORT.md        ← ใส่แบนเนอร์แจ้งข้อผิดพลาดแล้ว
docs/MIGRATION_005_CORRECTIVE_REVIEW.md  ← เอกสารฉบับนี้
```

> **หมายเหตุ**: commit `67c6f99` ที่ push ไปแล้วมีข้อความ commit ที่ระบุว่าต้นทางมี
> "zero foreign keys, zero check constraints" ซึ่งผิด · **ไม่แก้ประวัติ git**
> เพราะต้องเขียนประวัติใหม่ซึ่งมีความเสี่ยงมากกว่าประโยชน์ · การแก้อยู่ในไฟล์
> และในเอกสารแทน

---

## 8. Production write / deploy / restart

**NONE ทั้งหมด** — ยืนยันแบบอ่านอย่างเดียวหลังทำงานเสร็จ

```
schema ที่มีบน production   : mko, public                   ← ยังไม่มี web
migration ที่ลงแล้ว          : 001, 002, 003, 004            ← ยังไม่มี 005
```

| รายการ | สถานะ |
|---|---|
| apply 005 กับ production | **ไม่ได้ทำ** |
| data migration | **ไม่ได้ทำ** |
| เขียน Supabase | **ไม่ได้ทำ** |
| ใช้ anon key เพื่อ bypass member access | **ไม่ได้ทำ** |
| แก้ Auth / RLS / Storage | **ไม่ได้ทำ** |
| RAG migration / re-embed | **ไม่ได้ทำ** |
| deploy / restart | **ไม่ได้ทำ** |
| merge `main` | **ไม่ได้ทำ** |
| **commit / push** | **ไม่ได้ทำ** |

---

## STOP

รออนุมัติก่อน commit / push

สองเรื่องที่ขอให้ตัดสิน

1. **อนุมัติให้ commit การแก้ชุดนี้หรือไม่** — 6 ไฟล์ที่แก้ + 4 ไฟล์ untracked ที่เกี่ยวข้อง
2. **`news.status`** — รับทราบว่าคงไว้เป็น Pending Decision และ **ห้ามนำเข้าตาราง `news`
   จนกว่าจะรัน `SELECT DISTINCT status` บนต้นทาง** ซึ่งต้องมีสิทธิ์ member ก่อน
