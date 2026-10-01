# Migration 005 — schema `web` · เอกสารขอตรวจก่อนอนุมัติ

| | |
|---|---|
| วันที่ | 2026-10-01 |
| สถานะ | **เขียนและทดสอบแล้ว · ยังไม่ apply · ยังไม่ commit · ยังไม่ย้ายข้อมูล** |
| ขอบเขต | สร้าง "ที่ว่าง" สำหรับข้อมูลหน้าเว็บเท่านั้น — **ไม่ย้ายข้อมูลจริงแม้แถวเดียว** |
| ทดสอบที่ | ฐานข้อมูล `web_test` ในคอนเทนเนอร์แยก · ลบทิ้งหมดแล้ว |
| ผลทดสอบ | **47 / 47 ผ่าน · 0 ไม่ผ่าน** |
| เอกสารประกอบ | [`DATABASE_CONSOLIDATION_AUDIT.md`](DATABASE_CONSOLIDATION_AUDIT.md) · [`TARGET_ARCHITECTURE.md`](TARGET_ARCHITECTURE.md) |

> **ยืนยัน production ยังไม่ถูกแตะ** (ตรวจแบบอ่านอย่างเดียวหลังทำงานเสร็จ)
>
> ```
> schema ที่มี        : mko, public                 ← ยังไม่มี web
> migration ที่ลงแล้ว  : 001, 002, 003, 004          ← ยังไม่มี 005
> ```

---

## 1. ไฟล์ที่สร้าง

```
db/migrations/005_web_schema.sql     migration · ยังไม่ apply ที่ใด
eval/web_schema_check.py             ชุดตรวจ 47 ข้อ
```

ทั้งสองไฟล์ยัง untracked · `staged = 0` · `tracked modified = 0` · `HEAD = 7af085b` ไม่เปลี่ยน

---

## 2. schema ที่จะสร้าง

### 2.1 ภาพรวม

| ตาราง | มาจากตารางเดิม | คอลัมน์ | FK | CHECK | index |
|---|---|---:|---:|---:|---:|
| `web.site_courses` | `courses` | 13 | 3 | 0 | 3 |
| `web.news` | `news` | 11 | 2 | 1 | 2 |
| `web.external_news` | `external_news` | 12 | 0 | 0 | 3 |
| `web.knowledge_articles` | `knowledge_articles` | 10 | 2 | 1 | 1 |
| `web.ai_settings` | `ai_settings` | 4 | 1 | 1 | 1 |
| **รวม** | | **50** | **8** | **3** | **10** |

**เทียบกับ schema เดิมฝั่งหน้าเว็บ**

| | เดิม | ที่จะสร้าง |
|---|---:|---:|
| foreign key | **0** | **8** |
| check constraint | **0** | **3** |
| unique index | **1** (ทั้งฐาน) | **7** |

### 2.2 `web.site_courses` — หลักสูตรในมุมของหน้าเว็บ

```sql
id            UUID PRIMARY KEY DEFAULT gen_random_uuid()
course_id     UUID REFERENCES public.courses(id) ON DELETE SET NULL
title         VARCHAR(255) NOT NULL
title_en      VARCHAR(255)
description   TEXT
logo_url      TEXT
careers       TEXT[]      NOT NULL DEFAULT '{}'
detail        JSONB       NOT NULL DEFAULT '{}'
is_published  BOOLEAN     NOT NULL DEFAULT TRUE
created_by    UUID REFERENCES public.users(id) ON DELETE SET NULL
updated_by    UUID REFERENCES public.users(id) ON DELETE SET NULL
created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()

UNIQUE INDEX uq_site_courses_course ON (course_id) WHERE course_id IS NOT NULL
INDEX idx_site_courses_published ON (is_published) WHERE is_published
```

**`course_id` คือสิ่งที่การรวมฐานข้อมูลให้มาจริง ๆ** — ปัจจุบันหน้าเว็บแสดงหลักสูตรจาก
ชุดหนึ่ง แต่ AI ตอบคำถามจากอีกชุดหนึ่ง โดยไม่มีอะไรรับประกันว่าพูดถึงหลักสูตรเดียวกัน
เพราะอยู่คนละฐานข้อมูลจึงเชื่อมกันไม่ได้เลย

เป็น **partial unique** คือหลายแถวที่ยังผูกไม่ได้ (`NULL`) อยู่ร่วมกันได้
แต่หลักสูตรจริงหนึ่งหลักสูตรผูกกับแถวแสดงผลได้ไม่เกินหนึ่งแถว

### 2.3 `web.news` — ข่าวที่ทีมเขียนเอง

```sql
id            UUID PRIMARY KEY DEFAULT gen_random_uuid()
title         VARCHAR(255) NOT NULL
description   TEXT
category      VARCHAR(100)
published_on  DATE
image_url     TEXT
status        VARCHAR(50)  NOT NULL DEFAULT 'published'
              CHECK (status IN ('published', 'draft', 'archived'))
created_by    UUID REFERENCES public.users(id) ON DELETE SET NULL
updated_by    UUID REFERENCES public.users(id) ON DELETE SET NULL
created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()

INDEX idx_news_published ON (published_on DESC NULLS LAST) WHERE status = 'published'
```

> **ต้องตรวจก่อนนำข้อมูลเข้า** — ค่า `status` ที่อนุญาตสามค่านี้มาจากค่าเริ่มต้นที่พบ
> (`'published'`) บวกค่าที่สมเหตุสมผล **ยังไม่ได้ยืนยันกับข้อมูลจริง** ถ้าพบค่าอื่น
> ให้แก้รายการใน CHECK ไม่ใช่ถอด CHECK ออก

### 2.4 `web.external_news` — ข่าวที่ดึงมาจากภายนอก (SCI Connect)

```sql
id              UUID PRIMARY KEY DEFAULT gen_random_uuid()
slug            VARCHAR(255) NOT NULL UNIQUE
title           VARCHAR(255) NOT NULL
description     TEXT
image_url       TEXT
detail_url      TEXT
facebook_url    TEXT
source          VARCHAR(100)
published_at    TIMESTAMPTZ
published_text  VARCHAR(255)
synced_at       TIMESTAMPTZ NOT NULL DEFAULT now()
created_at      TIMESTAMPTZ NOT NULL DEFAULT now()

INDEX idx_external_news_published ON (published_at DESC NULLS LAST)
```

`slug` เป็น UNIQUE เพราะหน้ารายละเอียดค้นด้วย `.eq('slug', slug).maybeSingle()`
ถ้ามีสองแถว slug เดียวกัน ผลลัพธ์จะไม่แน่นอน — ของเดิมไม่มี unique ตัวนี้

`published_text` เก็บข้อความวันที่ตามที่เว็บต้นทางแสดงไว้ดิบ ๆ เพราะบางรายการ
ไม่ใช่วันที่ที่แปลงเป็น date ได้

### 2.5 `web.knowledge_articles` — บทความ / คลังความรู้

```sql
id          UUID PRIMARY KEY DEFAULT gen_random_uuid()
title       VARCHAR(255) NOT NULL
content     TEXT
file_path   TEXT
file_name   TEXT
file_size   BIGINT CHECK (file_size IS NULL OR file_size >= 0)
created_by  UUID REFERENCES public.users(id) ON DELETE SET NULL
updated_by  UUID REFERENCES public.users(id) ON DELETE SET NULL
created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
```

> **สามคอลัมน์ `file_*` คือร่องรอยของไฟล์แนบ** ซึ่งไฟล์จริงอยู่ในที่เก็บไฟล์ของ
> ผู้ให้บริการเดิม การย้ายฐานข้อมูล **ไม่ได้ย้ายไฟล์ตามมาด้วย** ต้องตัดสินใจแยกว่า
> ไฟล์จะไปอยู่ที่ใด แล้วค่อยแก้ค่าในคอลัมน์นี้

### 2.6 `web.ai_settings` — ตั้งค่าโมเดลของหน้าเว็บ (ตารางแถวเดียว)

```sql
id          SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1)
model       VARCHAR(255) NOT NULL
updated_by  UUID REFERENCES public.users(id) ON DELETE SET NULL
updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
```

บังคับ `id = 1` ด้วย CHECK ไม่ใช่แค่ค่าเริ่มต้น เพราะโค้ดอ่านด้วย
`.eq('id', 1).single()` ซึ่งจะล้มถ้ามีแถวที่สอง — ให้ฐานข้อมูลกันไว้แทนที่จะหวังว่า
ทุกคนที่เขียนโค้ดต่อจากนี้จะรู้กติกา

---

## 3. เหตุผลของการตัดสินใจหลัก

### 3.1 ทำไมเป็น schema แยก ไม่ยัดลง `public`

1. `public` และ `mko` ทำงานอยู่จริงกับข้อมูลจริง (9,039 chunk · 56 FK · 68 check)
   การไม่แตะเลยทำให้ความเสี่ยงต่อ RAG, crawler และ chat **เป็นศูนย์**
2. **ชื่อชนกันสองคู่** — ฝั่งหน้าเว็บมีทั้ง `courses` และ `user_profiles` ซึ่ง `public`
   ก็มีทั้งคู่และความหมายคนละอย่าง การยัดรวมต้องเปลี่ยนชื่อหรือรวมตาราง ซึ่งทั้งสองทาง
   แตะของที่ใช้งานอยู่
3. ถอนกลับด้วย `DROP SCHEMA web CASCADE` คำสั่งเดียว
4. `mko` มี **19 FK ชี้เข้า `public`** อยู่แล้ว พิสูจน์ว่าโครงหลาย schema ในฐานเดียว
   ใช้งานได้ดีในโปรเจกต์นี้

### 3.2 ทำไมชื่อ `site_courses` ไม่ใช่ `courses`

`public.courses` เก็บ **ข้อเท็จจริงของหลักสูตร** ที่ pipeline สกัดมาจากเอกสาร มคอ.
ส่วนตารางนี้เก็บ **ของที่เอาไว้แสดงบนหน้าเว็บ** — โลโก้ คำบรรยาย อาชีพที่ทำได้

ตั้งชื่อให้ต่างกันเพื่อให้คนอ่าน query แล้วรู้ทันทีว่ากำลังอ่านอะไร ไม่ต้องจำว่า
schema ไหนคืออันไหน

### 3.3 ทำไมใส่ FK ทั้งที่ของเดิมไม่มี

schema เดิมฝั่งหน้าเว็บมี **FK 0 ตัว · CHECK 0 ตัว · UNIQUE 1 ตัวทั้งฐาน**
(ที่มา: `docs/database/schema.json` · source `supabase_schema.sql`)

ความสัมพันธ์มีอยู่จริงในการออกแบบ (`user_id`, `created_by`, `source_id`) แต่
**ฐานข้อมูลไม่รู้จักมัน** เครื่องมือจึงวาด ER ให้อัตโนมัติไม่ได้ ต้องเดาจากชื่อคอลัมน์ —
ซึ่งเป็นสิ่งที่ `docs/database/er_supabase.svg` ที่มีอยู่ทำ

ที่นี่ประกาศให้ครบตั้งแต่ต้น **ER จึงวาดเองได้และข้อมูลเสียรูปไม่ได้**

### 3.4 ทำไม `created_by` / `updated_by` เป็น NULL ได้

ของเดิมอ้างถึงผู้ใช้ในระบบ auth ของหน้าเว็บ ซึ่งเป็น **คนละชุด** กับ `public.users`
(ยืนยันแล้วว่าไม่มีเส้นเชื่อมกันเลย) ตอนนำข้อมูลเข้าจึงจะมีบางแถวที่หาเจ้าของไม่เจอ

ปล่อยให้เป็น NULL ดีกว่าทิ้งแถวนั้นหรือยัดเจ้าของผิดคน

ทุก FK เป็น `ON DELETE SET NULL` เพราะ **การลบบัญชีผู้ใช้ไม่ควรลบข่าวที่เขาเคยเขียน**

### 3.5 ทำไม `timestamptz` ไม่ใช่ `timestamp`

ของเดิมเป็น `TIMESTAMP` ไม่มีเขตเวลา ส่วนฐานข้อมูลนี้ใช้ `timestamptz` ทุกตาราง
การเก็บแบบไม่มีเขตเวลาต่อไปจะทำให้ข้อมูลสองชุดในฐานเดียวกันเทียบเวลากันไม่ได้

> **ตอนนำเข้าต้องระบุให้ชัดว่าค่าที่เก็บไว้เดิมเป็นเวลาอะไร** (UTC หรือเวลาไทย)
> ถ้าเดาผิดเวลาจะคลาดไป 7 ชั่วโมงทั้งก้อน

---

## 4. สิ่งที่ตั้งใจยังไม่สร้าง

| ไม่สร้าง | เหตุผล |
|---|---|
| ตาราง role / สิทธิ์ของผู้ใช้หน้าเว็บ | ต้องตัดสินใจเรื่อง auth ก่อนว่าตัวตนผู้ใช้จะอยู่ที่ใด ถ้าสร้างตอนนี้จะกลายเป็น **"ที่บอกสิทธิ์สองแห่ง"** ซ้ำกับ `public.users.is_admin` ที่มีอยู่แล้ว — เป็นปัญหาเดิมในรูปแบบใหม่ |
| ตาราง chunk / embedding ของหน้าเว็บ | ของเดิมเป็น `vector(768)` จาก `gemini-embedding-001` ส่วนระบบนี้ใช้ `bge-m3` **1024 มิติ** · **ย้ายค่าเวกเตอร์ตรง ๆ ไม่ได้** ต้องสร้าง embedding ใหม่ทั้งหมด ซึ่งทำให้คำตอบของระบบเปลี่ยนและต้องวัดคุณภาพใหม่ — เป็นการตัดสินใจแยก |

ผลคือ migration นี้ **เป็นกลางต่อการตัดสินใจเรื่อง auth** จะเลือกเก็บ auth ไว้ที่เดิม
หรือย้ายมาทั้งหมด ก็ใช้ไฟล์นี้ได้เหมือนกัน

---

## 5. สิทธิ์ที่ให้

```
advisor_api      USAGE ON SCHEMA web
                 SELECT ทุกตาราง
                 INSERT, UPDATE  site_courses · news · knowledge_articles · ai_settings
                 (external_news เขียนไม่ได้ — เป็นของตัวดึงข่าว)

advisor_ingest   USAGE ON SCHEMA web
                 SELECT ทุกตาราง
                 INSERT, UPDATE  external_news เท่านั้น

ไม่ให้ DELETE แก่ใครทั้งสิ้น
```

ไม่ให้ `DELETE` เป็นหลักเดียวกับ migration 002 และ 004 — การลบต้องเป็นการตัดสินใจ
ที่ทำด้วยมือโดยผู้มีสิทธิ์ระดับ owner ไม่ใช่สิ่งที่โค้ดทำได้เอง

---

## 6. ผลทดสอบ — 47 / 47 ผ่าน

| หมวด | ข้อ | ตรวจอะไร |
|---|---:|---|
| **[1] โครงสร้าง** | 6 | ตารางครบ 5 ไม่เกินไม่ขาด · FK ครบ 8 เส้นและชี้ถูกที่ · ทุก FK เป็น `SET NULL` · มี CHECK และ UNIQUE มากกว่าของเดิม · ไม่มีคอลัมน์ `timestamp` ไร้เขตเวลาหลงเหลือ |
| **[2] constraint ทำงานจริง** | 13 | ยิงข้อมูลผิดรูปเข้าไปแล้ว **ต้องถูกปฏิเสธจริง** — `status` สะกดผิด · `title` NULL · `slug` ซ้ำ · `ai_settings` แถวที่สอง · `file_size` ติดลบ · FK ชี้ของที่ไม่มี |
| **[3] การผูกหลักสูตร** | 5 | หลายแถว `NULL` อยู่ร่วมกันได้ · ผูกหลักสูตรเดียวกันสองแถวถูกปฏิเสธ · **ลบหลักสูตรแล้วแถวแสดงผลยังอยู่และ `course_id` กลายเป็น NULL** |
| **[4] ไม่แตะ `public`/`mko`** | 6 | `public` ยัง 10 ตาราง · `mko` ยัง 20 ตาราง + 8 view · `course_chunks.embedding` ยัง 1024 มิติ · index `ivfflat vector_cosine_ops` เหมือนเดิม · **ไม่มี FK จาก `public` ชี้มาหา `web`** |
| **[5] สิทธิ์** | 17 | `advisor_api` อ่านได้หมด · เขียนได้เฉพาะสี่ตาราง · เขียน `external_news` ไม่ได้ · **ไม่มีใคร DELETE ได้สักตาราง** · `advisor_ingest` เขียนได้ตารางเดียว |

### 6.1 วิธีทดสอบ

```
ฐานข้อมูล    web_test ในคอนเทนเนอร์ PostgreSQL 16.15 แยก (ไม่ใช่ production)
ด่านกัน       URL ห้ามมีคำว่า course_advisor · ถาม current_database() ซ้ำอีกชั้น
idempotent   ลง 005 สองครั้งติดกัน ไม่ error
สร้างใหม่     drop แล้วสร้างตั้งแต่ศูนย์ 001 → 005 ผ่านครบทุกตัว
ทุกแถวที่ใช้   สร้างขึ้นเองในเทสต์แล้วย้อนทิ้งเมื่อจบ ไม่ได้ย้ายข้อมูลจริงจากที่ใด
```

### 6.2 regression — ชุดเดิมไม่พัง

รันบนฐานข้อมูลที่ลง migration 005 แล้ว

```
eval/crawl_state_check.py          32 / 32 ผ่าน
eval/crawl_ingest_worker_check.py  187 / 187 ผ่าน
```

### 6.3 ข้อบกพร่องที่พบระหว่างทดสอบ และแก้แล้ว

ชุดตรวจรอบแรกล้มที่หมวด [3] เพราะ **เทสต์เขียนผิดเอง ไม่ใช่ migration ผิด** —
ฟังก์ชันช่วยตรวจย้อน transaction ทุกครั้ง ทำให้แถวหลักสูตรตั้งต้นที่สร้างไว้หายไป
ด้วย แก้โดย commit แถวตั้งต้นก่อนเริ่มตรวจ แล้วลบทิ้งเมื่อจบ

---

## 7. การทำความสะอาด

```
containers : 0        volumes : 0        images : 0        (ของ sci-advisor-e2e)
```

ฐานข้อมูลทดสอบ `web_test` และ `crawl_test` อยู่ใน volume ที่ถูกลบไปพร้อมกัน

---

## 8. ที่ยังติดอยู่ — ต้องมีก่อนทำขั้นต่อไป

ขั้นต่อไปคือ **นำข้อมูลเข้า** ซึ่งยังทำไม่ได้จนกว่าจะมี

| # | ต้องการอะไร | ทำไมจำเป็น |
|---|---|---|
| 1 | **สิทธิ์เข้าฐานข้อมูลเดิมของหน้าเว็บ** | ต้อง export ข้อมูลออกมา · ขอเป็น member ด้วยบัญชีตัวเอง ไม่ใช่ยืมบัญชีคนอื่น |
| 2 | **ค่าที่ `news.status` ใช้จริง** | ยืนยันว่า CHECK ครอบครบ ถ้าพบค่าอื่นต้องแก้รายการก่อน ไม่ใช่ถอด CHECK |
| 3 | **การแมปผู้ใช้สองชุด** | `created_by`/`updated_by` อ้างผู้ใช้คนละชุดกับ `public.users` ต้องตัดสินว่าแมปอย่างไร แถวที่แมปไม่ได้จะเป็น NULL ตามที่ออกแบบ |
| 4 | **เขตเวลาของ `TIMESTAMP` เดิม** | ถ้าเดาผิดเวลาจะคลาด 7 ชั่วโมงทั้งก้อน |
| 5 | **ไฟล์แนบของ `knowledge_articles` จะไปอยู่ที่ใด** | ฐานข้อมูลเก็บแค่ชื่อกับขนาด ไฟล์จริงอยู่ที่เก็บไฟล์เดิม |

---

## 9. การอนุมัติหมายถึงอะไร

ถ้าอนุมัติไฟล์นี้ **ยังไม่มีอะไรเกิดขึ้นกับ production** สิ่งที่จะทำต่อคือ

```
1. commit สองไฟล์นี้                              (ยังไม่แตะฐานข้อมูลใด)
2. ทดสอบซ้ำในสภาพแวดล้อมแยกอีกรอบ                  (ยังไม่แตะ production)
3. ขออนุมัติแยกอีกครั้งก่อน apply กับ production      ← ขั้นนี้ต้องขอใหม่
4. ขออนุมัติแยกอีกครั้งก่อนนำข้อมูลเข้า               ← ขั้นนี้ต้องขอใหม่
```

**การอนุมัติเอกสารนี้ไม่ใช่การอนุมัติให้ apply กับ production** และไม่ใช่การอนุมัติ
ให้ย้ายข้อมูล ทั้งสองอย่างเป็นการตัดสินใจแยกที่ต้องขอใหม่

---

## สรุปการเปลี่ยนแปลงในรอบนี้

```
PRODUCTION WRITES:    NONE      (ยืนยัน: production มีแค่ schema mko, public · migration 001-004)
MIGRATIONS APPLIED:   NONE      (apply เฉพาะฐานข้อมูลทดสอบในคอนเทนเนอร์ ซึ่งลบทิ้งแล้ว)
DATA MIGRATED:        NONE
DEPLOYMENTS:          NONE
SERVICE RESTARTS:     NONE
COMMITS / PUSHES:     NONE
ไฟล์ที่ลบหรือแก้:        NONE      (สร้างใหม่ 2 ไฟล์ ไม่แก้ไฟล์เดิมแม้ไฟล์เดียว)
```

---

## STOP

รออนุมัติ — ยังไม่ apply · ยังไม่ commit · ยังไม่ย้ายข้อมูล
