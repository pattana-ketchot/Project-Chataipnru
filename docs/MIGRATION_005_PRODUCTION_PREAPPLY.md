# Migration 005 — Production Pre-Apply Gate

| | |
|---|---|
| วันที่ | 2026-10-03 |
| ขอบเขต | **READ-ONLY VERIFICATION ONLY** — ไม่ apply |
| **Classification** | **`MIGRATION_005_READY_TO_APPLY`** |
| ไฟล์ที่จะ apply | `db/migrations/005_web_schema.sql` · **376 บรรทัด · 31,265 ไบต์** |
| git blob | **`9b917ea1e1adb81b597e5b9db2b294ea3ec1354e`** — ตรงกันทั้ง working tree · HEAD · `dc5e860` · `origin/mko-phase2` |
| object collision | **ไม่มีเลย** ทั้ง 7 รายการ |
| prerequisite | **ครบทุกข้อ** |
| ⚠ ต้องเพิ่มในคำสั่ง apply | **`lock_timeout`** — production ตั้งไว้ `0` (รอไม่จำกัด) ดูข้อ 9.3 |

```
Apply Migration 005  NONE   CREATE SCHEMA/TABLE  NONE   ALTER            NONE
INSERT/UPDATE/DELETE NONE   CREATE ROLE          NONE   GRANT / REVOKE   NONE
ADVISOR_WEB_PASSWORD NONE   แก้ .env              NONE   Provision role   NONE
Migration 006        NONE   Data Migration       NONE   แก้ source       NONE
Deploy / Restart     NONE   Commit / Push / Merge NONE
```

**รอบนี้มีแต่ `SELECT` · การตรวจไฟล์ · และ git verification**

---

## 1. Git artifact verification

### 1.1 branch / HEAD (รายการ 1)

```
branch       mko-phase2
HEAD         cf4fb168a6acd7c9b948b4d8b8a41cc76a52ac12   (cf4fb16)
```

### 1.2 ไฟล์ 005 ตรงกับ commit ที่ review และ push แล้ว (รายการ 2)

| ที่ | git blob ของ `005_web_schema.sql` |
|---|---|
| working tree | `9b917ea1e1adb81b597e5b9db2b294ea3ec1354e` |
| `HEAD` (`cf4fb16`) | `9b917ea1e1adb81b597e5b9db2b294ea3ec1354e` |
| `dc5e860` (commit ที่ review + push) | `9b917ea1e1adb81b597e5b9db2b294ea3ec1354e` |
| **`origin/mko-phase2`** | **`9b917ea1e1adb81b597e5b9db2b294ea3ec1354e`** |

**ตรงกันทั้งสี่ที่** → ไฟล์ที่จะ apply คือไฟล์เดียวกับที่ผ่าน review และอยู่บน remote แล้ว
ไม่มีเวอร์ชันแฝง

### 1.3 checksum (รายการ 3)

```
sha256   64aaa21812086ab58835419a57fcbbbbe421e3729a0ca35d4857bb90723c273e
บรรทัด    376
ไบต์      31,265
```

> ใช้ค่านี้ยืนยันก่อนรันบน production ว่าไฟล์ที่ส่งขึ้นไปไม่ถูกแก้ระหว่างทาง
> (บทเรียนเดิมของโปรเจกต์: `git archive` บน Windows เคยแปลง LF เป็น CRLF)

### 1.4 ไม่มี uncommitted change (รายการ 4)

```
git diff -- db/migrations/005_web_schema.sql           ว่าง
git diff --cached -- db/migrations/005_web_schema.sql   ว่าง
git diff dc5e860 HEAD -- db/migrations/005_web_schema.sql   ว่าง
```

### 1.5 commit ที่ยังไม่ push — **ไม่มี 005 ปน**

```
cf4fb16  feat: add webapi authorization foundation
117a6f7  test: harden legacy author migration checks

ไฟล์ที่เปลี่ยนในสองคอมมิตนี้
  eval/web_schema_check.py
  webapi/Dockerfile · auth.mjs · auth.test.mjs · package.json · server.mjs · server.test.mjs
```

**ไม่มีไฟล์ migration ใดในสองคอมมิตที่ยังไม่ push** → สถานะของ 005 บน remote
เท่ากับที่จะ apply

### 1.6 ประวัติของไฟล์

```
dc5e860  fix(db): finalize web schema migration from live verification   <- ล่าสุด
de42e38  fix(db): match the source schema's keys in the web schema
67c6f99  feat(db): add a web schema for the website data that lives elsewhere
```

---

## 2. Production DB current state

### 2.1 เวอร์ชันและสุขภาพพื้นฐาน (รายการ 5)

| | |
|---|---|
| PostgreSQL | **16.15** (Debian 16.15-1.pgdg12+2) |
| `pg_is_in_recovery()` | **`false`** — เป็น primary ไม่ใช่ replica |
| `default_transaction_read_only` | **`off`** — เขียนได้ |

### 2.2 `web` schema ปัจจุบัน (รายการ 6)

```
web schema exists          false
schema ที่มีอยู่             mko, public
```

**ยืนยันด้วยการ query จริง ไม่ได้สมมติ** — `web` ยังไม่มี

### 2.3 Migration ledger

| | |
|---|---|
| `mko.schema_migrations` มีอยู่ | **true** |
| version ที่ลงแล้ว | `001_mko_structured` · `002_mko_review_publish` · `003_crawl_sources` · `004_crawl_decisions` |
| **มี `005_web_schema` แล้วหรือยัง** | **ยังไม่มี** |
| `version` มี unique/PK ไหม | **มี** → `ON CONFLICT (version)` ทำงานได้ |

---

## 3. Object collision check (รายการ 7)

ตรวจทั้ง 7 รายการที่สั่ง **ไม่พบการชนแม้รายการเดียว**

| object ที่ 005 จะสร้าง | สถานะบน production |
|---|---|
| `schema web` | **ไม่มี** → ไม่ชน |
| `web.site_courses` | **ไม่มี** |
| `web.news` | **ไม่มี** |
| `web.knowledge_articles` | **ไม่มี** |
| `web.ai_settings` | **ไม่มี** |
| `web.external_news` | **ไม่มี** |
| `web.touch_updated_at()` | **ไม่มี** |

### 3.1 ตรวจชื่อซ้ำทั้งฐาน ไม่ใช่แค่ใน `web`

```sql
-- ตารางชื่อเดียวกันใน schema ใดก็ได้
WHERE c.relname IN ('site_courses','external_news','knowledge_articles','ai_settings')
  ->  ไม่พบชื่อเหล่านี้ที่ใดเลย

WHERE c.relname = 'news'
  ->  ไม่มีตารางชื่อ news ที่ใด

WHERE p.proname = 'touch_updated_at'
  ->  ไม่มีฟังก์ชันชื่อนี้ที่ใด
```

**ไม่มีชื่อซ้ำแม้ใน schema อื่น** → แม้ `search_path` จะเพี้ยนก็ไม่มีโอกาสชี้ผิด object

### 3.2 `IF NOT EXISTS` ครอบทุกคำสั่งสร้าง

| คำสั่ง | จำนวน | กันการชนไหม |
|---|---:|---|
| `CREATE SCHEMA IF NOT EXISTS` | 1 | ✅ |
| `CREATE TABLE IF NOT EXISTS` | 5 | ✅ |
| `CREATE UNIQUE INDEX IF NOT EXISTS` | 2 | ✅ |
| `CREATE INDEX IF NOT EXISTS` | 3 | ✅ |
| `CREATE OR REPLACE FUNCTION` | 1 | ✅ |
| `CREATE OR REPLACE TRIGGER` | 4 | ✅ (PG14+ · production เป็น 16.15) |

→ **005 รันซ้ำได้** (ยืนยันแล้วในการทดสอบรอบก่อน: ลง 005 สองครั้งไม่ error)

---

## 4. Prerequisite check (รายการ 8)

| prerequisite | สถานะ |
|---|---|
| `public.users` มีอยู่ | ✅ `true` · **198 แถว** |
| `public.courses` มีอยู่ | ✅ `true` · **24 แถว** |
| `pgcrypto` | ✅ ติดตั้งแล้ว · schema **`public`** · version **1.3** |
| `gen_random_uuid()` เรียกได้ | ✅ `true` |
| `mko.schema_migrations` | ✅ มีอยู่ · `version` มี unique |

### 4.1 FK target — ชนิดและ constraint ตรงกัน

| FK target | ชนิดจริงบน production | 005 ประกาศ | ตรงกัน |
|---|---|---|---|
| `public.users(id)` | **`uuid`** · `NOT NULL` · **เป็น PK** | `UUID REFERENCES public.users(id)` | ✅ |
| `public.courses(id)` | **`uuid`** · `NOT NULL` · **เป็น PK** | `UUID REFERENCES public.courses(id)` | ✅ |

**ทั้งสองเป็น PK** → FK อ้างอิงได้ (PostgreSQL ต้องการ unique index บนคอลัมน์เป้าหมาย)
และชนิดตรงกันเป๊ะ → **ไม่มี implicit cast ที่อาจทำให้ index ใช้ไม่ได้**

---

## 5. FK / type compatibility

### 5.1 FK ทั้ง 8 เส้นที่ 005 สร้าง

| ตารางลูก | คอลัมน์ | ตารางแม่ | ON DELETE |
|---|---|---|---|
| `web.site_courses` | `course_id` | `public.courses(id)` | `SET NULL` |
| `web.site_courses` | `created_by` | `public.users(id)` | `SET NULL` |
| `web.site_courses` | `updated_by` | `public.users(id)` | `SET NULL` |
| `web.news` | `created_by` | `public.users(id)` | `SET NULL` |
| `web.news` | `updated_by` | `public.users(id)` | `SET NULL` |
| `web.knowledge_articles` | `created_by` | `public.users(id)` | `SET NULL` |
| `web.knowledge_articles` | `updated_by` | `public.users(id)` | `SET NULL` |
| `web.ai_settings` | `updated_by` | `public.users(id)` | `SET NULL` |

```
REFERENCES ในไฟล์           8
ON DELETE SET NULL          9   (8 FK + 1 ในคอมเมนต์อธิบาย)
```

**ทุก FK ตั้ง `ON DELETE SET NULL`** → ลบผู้ใช้แล้วเนื้อหาไม่หาย
ยืนยันเชิงพฤติกรรมแล้วในชุดตรวจ G2 (`eval/web_schema_check.py` 103 ข้อ)

### 5.2 ไม่มีการตรวจข้อมูลตอนสร้าง FK

ตารางลูกทั้ง 5 **ถูกสร้างใหม่และว่างเปล่า** → PostgreSQL ไม่ต้อง scan ข้อมูลเพื่อ validate FK
→ **การสร้าง FK เสร็จทันที** ไม่ขึ้นกับจำนวนแถวใน `public.users` / `public.courses`

---

## 6. Constraint / index / trigger review (รายการ 9)

### 6.1 สิ่งที่ 005 ประกาศทั้งหมด

```
CREATE SCHEMA                1
CREATE TABLE                 5
PRIMARY KEY                  5     (ตารางละ 1)
FOREIGN KEY                  8     ทุกเส้น ON DELETE SET NULL
CHECK                        3
UNIQUE (inline)              3
CREATE UNIQUE INDEX          2
CREATE INDEX                 3
CREATE OR REPLACE FUNCTION   1
CREATE OR REPLACE TRIGGER    4
COMMENT ON                   5
GRANT                        9     (USAGE 2 · SELECT 3 · INSERT/UPDATE 2 · EXECUTE 2)
DO $$ … $$                   1     (ห่อ GRANT ด้วย IF EXISTS)
INSERT                       1     (mko.schema_migrations · ON CONFLICT DO NOTHING)
```

### 6.2 CHECK constraint ทั้ง 3

| บรรทัด | constraint |
|---:|---|
| 206 | `news.status CHECK (status IN ('published','draft','archived'))` |
| 274 | `knowledge_articles.file_size CHECK (file_size IS NULL OR file_size >= 0)` |
| 292 | `ai_settings.id SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1)` — singleton |

### 6.3 Index ทั้ง 5

```
uq_site_courses_course          UNIQUE  partial (course_id WHERE NOT NULL)
idx_site_courses_published      btree
idx_news_published              btree
uq_external_news_slug           UNIQUE  partial (slug WHERE NOT NULL)
idx_external_news_published     btree
```

**index ทั้งหมดสร้างบนตารางว่าง** → เสร็จทันที ไม่ต้อง `CONCURRENTLY`
(และ `CONCURRENTLY` ใช้ใน transaction ไม่ได้อยู่แล้ว)

### 6.4 Trigger ทั้ง 4 + ฟังก์ชัน 1

```
web.touch_updated_at()                      BEFORE UPDATE  ตั้ง updated_at = now()
trg_site_courses_updated_at
trg_news_updated_at
trg_knowledge_articles_updated_at
trg_ai_settings_updated_at
```

ยืนยันแล้วในการทดสอบว่า `tgtype = 19` ทุกตัว = `1 (ROW) + 2 (BEFORE) + 16 (UPDATE)`
**ไม่มีบิต 4 (INSERT)** → นำเข้าข้อมูลเก่าได้โดยคงเวลาเดิม

---

## 7. GRANT review (รายการ 11)

### 7.1 สิ่งที่ 005 GRANT

```sql
-- ห่อด้วย DO $$ … IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = …)
-- advisor_api
GRANT USAGE  ON SCHEMA web TO advisor_api;
GRANT SELECT ON ALL TABLES IN SCHEMA web TO advisor_api;
GRANT INSERT, UPDATE ON web.site_courses, web.news,
                        web.knowledge_articles, web.ai_settings TO advisor_api;
GRANT EXECUTE ON FUNCTION web.touch_updated_at() TO advisor_api;
GRANT SELECT ON web.external_news TO advisor_api;
-- advisor_ingest
GRANT USAGE  ON SCHEMA web TO advisor_ingest;
GRANT SELECT ON ALL TABLES IN SCHEMA web TO advisor_ingest;
GRANT INSERT, UPDATE ON web.external_news TO advisor_ingest;
GRANT EXECUTE ON FUNCTION web.touch_updated_at() TO advisor_ingest;
```

### 7.2 ยืนยันว่า **ไม่มี `DELETE`**

```
ค้น "GRANT DELETE" ในไฟล์   ->  ไม่พบแม้รายการเดียว
```

ตรงตามการตัดสินใจเดิมของเจ้าของ

### 7.3 role ทั้งสองมีอยู่บน production

```
advisor_api     login=true  super=false  createdb=false  createrole=false
advisor_ingest  login=true  super=false  createdb=false  createrole=false
```

→ บล็อก `IF EXISTS` จะ**ไม่ถูกข้าม** GRANT จะลงจริงทั้งสองชุด

### 7.4 ⚠ `advisor_web` ยังไม่มี — และนั่นถูกต้องสำหรับรอบนี้

005 **ไม่พูดถึง `advisor_web` เลย** → GRANT ของ role นั้นจะอยู่ใน migration 006
(ตาม `B1_ADVISOR_WEB_ROLE_DESIGN.md`) · การ apply 005 ตอนนี้จึงไม่ต้องรอ `advisor_web`

---

## 8. Transaction / rollback analysis (รายการ 13)

### 8.1 005 อยู่ใน transaction เดียว

```
บรรทัด  79   BEGIN;
บรรทัด 376   COMMIT;
```

**ทุกคำสั่งอยู่ระหว่างสองบรรทัดนี้** — ไม่มี `COMMIT` กลางทาง ไม่มี `SAVEPOINT`

### 8.2 ถ้าคำสั่งใดล้ม — rollback ครบไหม

**ครบ** และนี่เป็นคุณสมบัติที่ PostgreSQL ให้ ไม่ใช่สิ่งที่ต้องเขียนเอง

| คำสั่ง | transactional ใน PostgreSQL ไหม |
|---|---|
| `CREATE SCHEMA` | ✅ |
| `CREATE TABLE` | ✅ |
| `CREATE INDEX` (ไม่ใช่ `CONCURRENTLY`) | ✅ |
| `CREATE FUNCTION` | ✅ |
| `CREATE TRIGGER` | ✅ |
| `COMMENT ON` | ✅ |
| `GRANT` | ✅ |
| `INSERT` | ✅ |

**PostgreSQL รองรับ transactional DDL** → ถ้าคำสั่งที่ 7 ล้ม คำสั่งที่ 1–6 ถูกย้อนทั้งหมด
ฐานข้อมูลกลับไปอยู่สภาพเดิมเป๊ะ **ไม่มีสภาพครึ่ง ๆ กลาง ๆ**

> ⚠ **ไม่มีคำสั่งใดใน 005 ที่ใช้ `CONCURRENTLY`** — ตรวจแล้ว · ถ้ามีจะใช้ใน transaction ไม่ได้
> และจะทำให้ rollback ไม่ครบ

### 8.3 เงื่อนไขที่ต้องมีเพื่อให้ atomicity เป็นจริง

```
ต้องรันทั้งไฟล์ในหนึ่ง session        -> psql -f ไฟล์เดียว
ต้องใช้ -v ON_ERROR_STOP=1           -> ถ้าไม่ใส่ psql จะข้าม error แล้วรันคำสั่งถัดไป
                                        แล้ว COMMIT ตอนท้ายจะ commit สิ่งที่ไม่ครบ
```

**`ON_ERROR_STOP=1` ไม่ใช่ของเสริม** — ขาดไปแล้ว atomicity หายทันที

---

## 9. Production impact / lock analysis (รายการ 14)

### 9.1 สิ่งที่ 005 ไม่แตะเลย (รายการ 12)

| ระบบ | 005 แตะไหม |
|---|---|
| Supabase | **ไม่** — ไม่มีคำสั่งใดคุยกับระบบภายนอก |
| Auth / Storage | **ไม่** |
| RAG (`public.course_chunks` · embedding) | **ไม่** |
| Ollama | **ไม่** |
| **ข้อมูลใน `public.users`** | **ไม่** — ไม่มี `INSERT`/`UPDATE`/`DELETE` บนตารางนี้ |
| **ข้อมูลใน `public.courses`** | **ไม่** — เช่นเดียวกัน |
| `schema mko` | **เขียน 1 แถว** — `mko.schema_migrations` (ledger) |
| `schema public` | **ไม่สร้าง/แก้/ลบ object ใด** |

#### การเขียน `mko.schema_migrations` เป็นแบบแผนเดิมของโปรเจกต์

```sql
INSERT INTO mko.schema_migrations (version) VALUES ('005_web_schema')
    ON CONFLICT (version) DO NOTHING;
```

migration **001–004 ทำแบบเดียวกันทุกไฟล์** → เป็น ledger ไม่ใช่การแตะข้อมูลธุรกิจ
และ `ON CONFLICT DO NOTHING` ทำให้รันซ้ำได้

### 9.2 Lock ที่จะเกิดขึ้น

| object | lock | กระทบอะไร |
|---|---|---|
| `web.*` (5 ตารางใหม่) | สร้างใหม่ | **ไม่กระทบใคร** — ยังไม่มีใครใช้ |
| **`public.users`** | **`ShareRowExclusiveLock`** (จากการสร้าง FK) | **บล็อก `INSERT`/`UPDATE`/`DELETE` ชั่วคราว** · **ไม่บล็อก `SELECT`** |
| **`public.courses`** | **`ShareRowExclusiveLock`** | เช่นเดียวกัน |
| `mko.schema_migrations` | `RowExclusiveLock` (จาก INSERT) | ไม่มีใครใช้ขณะนั้น |

**ระยะเวลาที่คาด: สั้นมาก** เพราะตารางลูกว่างเปล่า → ไม่ต้อง validate FK กับข้อมูล
(ข้อ 5.2) · `public.users` มี 198 แถว `public.courses` มี 24 แถว ซึ่งไม่เกี่ยวกับความเร็ว
เพราะไม่มีการ scan

### 9.3 ⚠ ความเสี่ยงจริงข้อเดียว — ไม่มี `lock_timeout`

ตรวจบน production

```
statement_timeout    0     (ไม่จำกัด)
lock_timeout         0     (ไม่จำกัด)
```

**ถ้ามี transaction อื่นถือ lock บน `public.users` อยู่ migration จะรอไปเรื่อย ๆ**
และที่แย่กว่านั้นคือ **คำขออื่นที่ต้องการ lock บน `public.users` จะต่อคิวอยู่หลัง migration**
→ กลายเป็นคิวที่บล็อกการเขียนทั้งระบบโดยที่ migration เองก็ยังไม่ได้เริ่ม

**สภาพปัจจุบันปลอดภัย** (ตรวจแล้ว)

```
idle in transaction      0
longest running tx       ไม่มี transaction ค้าง
locks waiting            0
lock บน users/courses     AccessShareLock เท่านั้น (การอ่านปกติ)
```

**แต่ต้องกันไว้** → คำสั่ง apply ในข้อ 11 ตั้ง `lock_timeout` ให้ล้มเร็วแทนการรอ

### 9.4 ภาระ connection

```
connections ใช้อยู่    8 / 100
```

การ apply ใช้ 1 connection เพิ่ม → ไม่มีปัญหา

### 9.5 ควร restart บริการไหม — **ไม่ต้อง**

| บริการ | กระทบไหม |
|---|---|
| `backend` | **ไม่** — ไม่มีโค้ดใดอ้างถึง `web.*` (ตรวจแล้วในรอบ B1: `grep` ไม่พบเลย) |
| `webapi` | **ไม่** — ยังไม่ต่อ PostgreSQL ด้วยซ้ำ |
| `frontend` · `caddy` · `ollama` | **ไม่** |

005 เป็นการ **เพิ่ม** schema ใหม่ที่ยังไม่มีใครใช้ → ไม่มีพฤติกรรมของระบบที่ทำงานอยู่เปลี่ยน

---

## 10. DB health (รายการ 15)

| | ค่า | ประเมิน |
|---|---|---|
| PostgreSQL | 16.15 | ✅ |
| `pg_is_in_recovery()` | `false` | ✅ primary |
| `default_transaction_read_only` | `off` | ✅ เขียนได้ |
| ขนาดฐานข้อมูล | **204 MB** | ✅ เล็ก |
| disk ที่เหลือ | **62 GB ว่าง จาก 97 GB (ใช้ 37%)** | ✅ เหลือเฟือ — 005 เพิ่มตารางว่าง 5 ตาราง ใช้พื้นที่หลัก KB |
| connections | **8 / 100** | ✅ |
| `idle in transaction` | **0** | ✅ ไม่มี transaction ค้างที่จะบล็อก |
| transaction ที่รันนานสุด | **ไม่มี** | ✅ |
| lock ที่รอ | **0** | ✅ |
| lock บน `users`/`courses` | `AccessShareLock` เท่านั้น | ✅ อ่านปกติ |
| `statement_timeout` / `lock_timeout` | `0` / `0` | ⚠ ดูข้อ 9.3 |

**สุขภาพพร้อม** — ข้อเดียวที่ต้องจัดการคือ timeout ซึ่งแก้ได้ที่คำสั่ง apply ไม่ต้องแก้ config

---

## 11. Exact apply plan — **ยังไม่รัน** (รายการ 16)

### 11.1 ขั้นก่อน apply

```bash
# 1. ยืนยัน checksum ของไฟล์ที่จะส่งขึ้น production
sha256sum db/migrations/005_web_schema.sql
# ต้องได้ 64aaa21812086ab58835419a57fcbbbbe421e3729a0ca35d4857bb90723c273e
```

```bash
# 2. ส่งไฟล์ขึ้น production โดยบังคับ LF ไม่ให้กลายเป็น CRLF
#    (บทเรียนเดิม: git archive บน Windows แปลง LF -> CRLF)
git -c core.autocrlf=false archive --format=tar HEAD db/migrations/005_web_schema.sql \
  | ssh ubuntu@<HOST> 'tar -x -C /tmp'
```

```bash
# 3. ยืนยัน checksum ฝั่ง production ว่าตรงกัน  ** ถ้าไม่ตรง หยุด **
ssh ubuntu@<HOST> 'sha256sum /tmp/db/migrations/005_web_schema.sql'
```

```bash
# 4. สำรองฐานข้อมูลก่อน  (ตารางที่จะถูกแตะมีแค่ ledger แต่สำรองไว้เพื่อความสบายใจ)
ssh ubuntu@<HOST> 'docker exec course-advisor-system-postgres-1 \
  pg_dump -U postgres -d course_advisor -Fc' > backup_before_005.dump
```

```sql
-- 5. ยืนยันสภาพก่อนรัน (SELECT อย่างเดียว) ** ถ้าค่าใดไม่ตรง หยุด **
SELECT (SELECT count(*) FROM pg_namespace WHERE nspname='web')            AS web_exists,  -- ต้อง 0
       (SELECT count(*) FROM mko.schema_migrations WHERE version='005_web_schema') AS already, -- ต้อง 0
       (SELECT count(*) FROM pg_stat_activity WHERE state='idle in transaction')   AS idle_tx, -- ต้อง 0
       (SELECT count(*) FROM pg_locks WHERE NOT granted)                  AS waiting;  -- ต้อง 0
```

### 11.2 คำสั่ง apply

```bash
ssh ubuntu@<HOST> 'docker exec -i course-advisor-system-postgres-1 \
  psql -U postgres -d course_advisor \
       -v ON_ERROR_STOP=1 \
       --single-transaction \
       -c "SET lock_timeout = '"'"'10s'"'"';" \
       -f /tmp/db/migrations/005_web_schema.sql' 2>&1 | tee apply_005.log
```

| ส่วนของคำสั่ง | ทำไมจำเป็น |
|---|---|
| **`-v ON_ERROR_STOP=1`** | **ขาดไปแล้ว atomicity หายทันที** — `psql` จะข้าม error แล้วรันต่อ แล้ว `COMMIT` สิ่งที่ไม่ครบ (ข้อ 8.3) |
| **`SET lock_timeout = '10s'`** | production ตั้งไว้ `0` = รอไม่จำกัด · ตั้ง 10 วินาทีเพื่อ **ล้มเร็วแทนการสร้างคิวที่บล็อกการเขียนทั้งระบบ** (ข้อ 9.3) |
| `--single-transaction` | ซ้ำซ้อนกับ `BEGIN/COMMIT` ในไฟล์ แต่ใส่ไว้เป็นชั้นที่สอง ไม่เสียหาย |
| `-f` ไฟล์เดียว | ต้องรันทั้งไฟล์ในหนึ่ง session เพื่อให้ `BEGIN/COMMIT` ครอบได้ |
| `tee` | เก็บ log ไว้ตรวจ |

> ⚠ **ห้ามใช้ `-c` หลายคำสั่งแยกกัน** และ **ห้าม `cat` ไฟล์ผ่าน pipe หลายทอด**
> เพราะทั้งสองทำให้คำสั่งกระจายไปหลาย transaction

### 11.3 สิ่งที่คาดว่าจะเห็นใน log

```
CREATE SCHEMA
COMMENT
CREATE TABLE        x5
COMMENT             x5
CREATE INDEX        x5
CREATE FUNCTION
CREATE TRIGGER      x4
NOTICE / DO
INSERT 0 1          <- ledger
COMMIT
```

**ถ้าเห็น `ROLLBACK` หรือ `ERROR` ที่ใด → ไปข้อ 13**

---

## 12. Exact post-apply verification (รายการ 17)

ทุกข้อเป็น `SELECT` — **ตรวจผลลัพธ์ ไม่ใช่ตรวจว่าคำสั่งรันผ่าน**

### 12.1 ยืนยันว่า object เกิดครบ

```sql
SELECT (SELECT count(*) FROM pg_namespace WHERE nspname='web')                        AS schema_web,      -- 1
       (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='web' AND c.relkind='r')                                      AS tables,          -- 5
       (SELECT count(*) FROM pg_constraint con JOIN pg_class c ON c.oid=con.conrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='web' AND con.contype='f')                                    AS fks,             -- 8
       (SELECT count(*) FROM pg_constraint con JOIN pg_class c ON c.oid=con.conrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='web' AND con.contype='c')                                    AS checks,          -- >= 3
       (SELECT count(*) FROM pg_indexes WHERE schemaname='web')                       AS indexes,         -- >= 10
       (SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='web' AND NOT t.tgisinternal)                                 AS triggers,        -- 4
       (SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
        WHERE n.nspname='web' AND p.proname='touch_updated_at')                       AS trg_function;    -- 1
```

### 12.2 ยืนยัน FK ทุกเส้นตั้ง `ON DELETE SET NULL`

```sql
SELECT count(*) AS fk_not_set_null
FROM pg_constraint con JOIN pg_class c ON c.oid=con.conrelid
JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='web' AND con.contype='f' AND con.confdeltype <> 'n';
-- ต้องได้ 0
```

### 12.3 ยืนยัน trigger เป็น UPDATE-only

```sql
SELECT count(*) AS trigger_wrong_type
FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='web' AND NOT t.tgisinternal AND t.tgtype <> 19;
-- ต้องได้ 0   (19 = ROW + BEFORE + UPDATE  ไม่มีบิต INSERT)
```

### 12.4 ยืนยัน legacy NULL author contract (รายการ 10)

```sql
SELECT count(*) AS author_columns_wrong
FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='web' AND a.attname IN ('created_by','updated_by')
  AND a.attnum>0 AND NOT a.attisdropped
  AND (a.attnotnull OR a.atthasdef);
-- ต้องได้ 0   -> ทุกคอลัมน์ผู้เขียน nullable และไม่มี DEFAULT
```

**ยืนยันในไฟล์แล้วล่วงหน้า**: `grep` หา `(created_by|updated_by).*NOT NULL` = **0 รายการ**
และ `.*DEFAULT` = **0 รายการ** → สัญญา `RESOLVED_WITH_NULL_LEGACY_AUTHOR` ยังรองรับ

### 12.5 ยืนยัน GRANT และ **ไม่มี DELETE**

```sql
SELECT grantee, privilege_type, count(*) AS tables
FROM information_schema.table_privileges
WHERE table_schema='web' GROUP BY 1,2 ORDER BY 1,2;
-- คาดหวัง: advisor_api SELECT 5 · INSERT 4 · UPDATE 4
--          advisor_ingest SELECT 5 · INSERT 1 · UPDATE 1
--          ** ไม่มีแถว DELETE เลย **

SELECT count(*) AS delete_grants FROM information_schema.table_privileges
WHERE table_schema='web' AND privilege_type='DELETE';
-- ต้องได้ 0
```

### 12.6 ยืนยันว่า `public` และ `mko` ไม่ถูกแตะ

```sql
SELECT (SELECT count(*) FROM public.users)   AS users,    -- ต้องยังเป็น 198
       (SELECT count(*) FROM public.courses) AS courses,  -- ต้องยังเป็น 24
       (SELECT count(*) FROM mko.schema_migrations)       AS migrations;  -- ต้องเป็น 5
```

### 12.7 ยืนยัน ledger

```sql
SELECT version FROM mko.schema_migrations ORDER BY version;
-- ต้องมี 001 · 002 · 003 · 004 · 005_web_schema
```

### 12.8 รันชุดตรวจอัตโนมัติ — **ไม่ชี้ production**

```
eval/web_schema_check.py  มี 103 ข้อ และมีด่านสองชั้นกันไม่ให้ชี้ฐานจริง
(ชื่อฐานต้องอยู่ใน {web_test, crawl_test, e2e_test} และ URL ห้ามมีคำว่า course_advisor)

-> รันในคอนเทนเนอร์ทดสอบ ไม่ใช่บน production
-> ข้อตรวจในข้อ 12.1-12.7 เป็นเวอร์ชันที่รันบน production ได้เพราะเป็น SELECT ล้วน
```

---

## 13. Abort / rollback plan (รายการ 18)

### 13.1 ถ้า apply ล้มกลางทาง

```
PostgreSQL ย้อน transaction ให้เองทั้งหมด  ->  ไม่ต้องทำอะไร
```

**ยืนยันด้วย**

```sql
SELECT count(*) FROM pg_namespace WHERE nspname='web';                            -- ต้องเป็น 0
SELECT count(*) FROM mko.schema_migrations WHERE version='005_web_schema';        -- ต้องเป็น 0
```

ถ้าทั้งสองเป็น 0 → **ฐานข้อมูลกลับสภาพเดิมสมบูรณ์** อ่าน log หาสาเหตุแล้วแก้ก่อนลองใหม่

### 13.2 ถ้าล้มเพราะ `lock_timeout`

```
อาการ    ERROR: canceling statement due to lock timeout
สาเหตุ    มี transaction อื่นถือ lock บน public.users หรือ public.courses
```

```sql
-- หาว่าใครถืออยู่ (SELECT อย่างเดียว ไม่ kill)
SELECT pid, usename, application_name, state,
       now()-xact_start AS tx_age, left(query, 80) AS query
FROM pg_stat_activity
WHERE state <> 'idle' AND pid <> pg_backend_pid()
ORDER BY xact_start;
```

**ไม่ใช่ความล้มเหลว เป็นการป้องกันที่ทำงาน** — ฐานข้อมูลไม่ถูกแตะเลย
รอให้ transaction นั้นจบแล้วลองใหม่ · **ห้าม `pg_terminate_backend` โดยไม่รู้ว่ากำลัง kill อะไร**

### 13.3 ถ้า apply สำเร็จแต่ post-apply ไม่ผ่าน

```sql
-- ถอนทั้ง schema ได้เพราะไม่มีใครใช้และไม่มีข้อมูล
BEGIN;
  DROP SCHEMA web CASCADE;
  DELETE FROM mko.schema_migrations WHERE version = '005_web_schema';
COMMIT;
```

| | |
|---|---|
| ปลอดภัยไหม | **ปลอดภัย ณ จุดนี้** — `web.*` ว่างเปล่า ไม่มีบริการใดอ้างถึง |
| `CASCADE` จะลบอะไรนอก `web` ไหม | **ไม่** — FK ชี้ **จาก** `web.*` **ไป** `public.*` ทิศทางเดียว การลบตารางลูกไม่กระทบตารางแม่ |
| `public.users` / `public.courses` | **ไม่ถูกแตะ** |
| **เงื่อนไขที่ทำให้ใช้ไม่ได้** | **หลังจากทำ data migration แล้ว** — ตอนนั้น `DROP SCHEMA web CASCADE` จะลบข้อมูลจริง · ต้องกู้จาก dump แทน |

### 13.4 ถ้าต้องกู้จาก dump

```bash
# ใช้เฉพาะเมื่อข้อ 13.3 ใช้ไม่ได้แล้ว
# ** ทำลายข้อมูลที่เกิดขึ้นหลังจากเวลาที่ dump ** จึงเป็นทางสุดท้าย
ssh ubuntu@<HOST> 'docker exec -i course-advisor-system-postgres-1 \
  pg_restore -U postgres -d course_advisor --clean --if-exists' < backup_before_005.dump
```

### 13.5 ลำดับความรุนแรงของทางถอน

```
1. ไม่ต้องทำอะไร        apply ล้ม -> PostgreSQL ย้อนให้เอง              ไม่เสียอะไร
2. รอแล้วลองใหม่        lock timeout                                   ไม่เสียอะไร
3. DROP SCHEMA web      post-apply ไม่ผ่าน และยังไม่ย้ายข้อมูล           ไม่เสียอะไร
4. pg_restore           ทางสุดท้าย                                     เสียข้อมูลหลังเวลา dump
```

---

## 14. Final classification

# `MIGRATION_005_READY_TO_APPLY`

### 14.1 เกณฑ์ที่ผ่านครบ

| # | รายการที่สั่งตรวจ | ผล |
|---|---|---|
| 1 | git branch / HEAD | ✅ `mko-phase2` / `cf4fb16` |
| 2 | 005 ตรงกับ commit ที่ review/push | ✅ blob `9b917ea1` ตรงกันทั้ง 4 ที่ |
| 3 | checksum | ✅ `64aaa218…c273e` · 376 บรรทัด · 31,265 ไบต์ |
| 4 | ไม่มี uncommitted change | ✅ ว่างทั้ง working tree และ index |
| 5 | PostgreSQL version | ✅ 16.15 |
| 6 | `web` schema ปัจจุบัน | ✅ **ยังไม่มี** (query จริง ไม่ได้สมมติ) |
| 7 | object collision 7 รายการ | ✅ **ไม่ชนแม้รายการเดียว** · ตรวจชื่อซ้ำทั้งฐานด้วย |
| 8 | prerequisite | ✅ `users` 198 · `courses` 24 · `pgcrypto` 1.3 · FK target เป็น PK ชนิด `uuid` ตรงกัน |
| 9 | FK/CHECK/UNIQUE/INDEX/TRIGGER | ✅ 8 FK (SET NULL ทุกเส้น) · 3 CHECK · 2 unique index · 3 index · 4 trigger · 1 function |
| 10 | legacy NULL author contract | ✅ author ทุกคอลัมน์ nullable · **ไม่มี NOT NULL · ไม่มี DEFAULT** |
| 11 | GRANT · ไม่มี DELETE | ✅ role ทั้งสองมีอยู่ · **`GRANT DELETE` = 0 รายการ** |
| 12 | ไม่แตะ Supabase/Auth/Storage/RAG/Ollama/ข้อมูล `users`/`courses` | ✅ แตะเฉพาะ `mko.schema_migrations` 1 แถว ซึ่งเป็น ledger ตามแบบแผนเดิม |
| 13 | transaction safety | ✅ `BEGIN` บรรทัด 79 · `COMMIT` บรรทัด 376 · ไม่มี `CONCURRENTLY` · DDL เป็น transactional ทั้งหมด |
| 14 | lock / risk | ✅ lock สั้นมากเพราะตารางลูกว่าง · **ต้องตั้ง `lock_timeout`** |
| 15 | DB health | ✅ 204 MB · disk ว่าง 62 GB · 8/100 connections · 0 idle-in-tx · 0 waiting locks |
| 16 | apply command | ✅ ข้อ 11 |
| 17 | post-apply checklist | ✅ ข้อ 12 |
| 18 | rollback procedure | ✅ ข้อ 13 — 4 ระดับ |

### 14.2 ทำไมไม่ใช่ `MIGRATION_005_VERIFICATION_REQUIRED`

ตรวจครบทั้ง 18 รายการ **ไม่มีข้อใดเหลือเป็น "ยังไม่รู้"**
ค่าทุกค่าในรายงานนี้มาจากการรันจริง ไม่มีค่าใดที่สมมติหรืออ้างจากรอบก่อนโดยไม่ตรวจซ้ำ

### 14.3 ทำไมไม่ใช่ `MIGRATION_005_BLOCKED`

```
ไม่มี object ชน            ไม่มี prerequisite ขาด       ไม่มี FK ชนิดไม่ตรง
ไม่มี transaction ค้าง      ไม่มี lock รอ                disk/connection เหลือเฟือ
ไม่ต้องรอ advisor_web      ไม่ต้องรอ migration 006      ไม่ต้อง restart บริการใด
```

### 14.4 เงื่อนไขเดียวที่ต้องทำให้ครบตอน apply

**ต้องมีสองอย่างนี้ในคำสั่ง มิฉะนั้นอย่า apply**

```
-v ON_ERROR_STOP=1        ขาดไป -> atomicity หาย -> อาจได้ schema ครึ่ง ๆ ที่ commit แล้ว
SET lock_timeout = '10s'  ขาดไป -> ถ้าชน lock จะรอไม่จำกัด และสร้างคิวที่บล็อกการเขียนทั้งระบบ
```

ทั้งสองเป็นสิ่งที่ **ไม่มีในค่าตั้งต้นของ production** (`lock_timeout = 0`) และ
**ไม่ใช่สิ่งที่ `psql` ทำให้เอง** (`ON_ERROR_STOP` ปิดโดยค่าตั้งต้น)

---

## 15. Exact next step

```
1. ขออนุมัติ apply Migration 005 บน production
     ** รอบนี้เป็น pre-apply gate เท่านั้น ยังไม่ได้ apply **

2. เมื่อได้รับอนุมัติ  ทำตามข้อ 11 ตามลำดับ
     11.1 ขั้นก่อน apply      checksum -> ส่งไฟล์ (LF) -> ยืนยัน checksum -> dump -> ยืนยันสภาพ
     11.2 คำสั่ง apply        ต้องมี ON_ERROR_STOP=1 และ lock_timeout
     11.3 อ่าน log            ถ้ามี ERROR/ROLLBACK -> ข้อ 13

3. รันขั้นตรวจหลัง apply ข้อ 12 ทั้ง 7 ชุด
     โดยเฉพาะ 12.2 (FK SET NULL) · 12.3 (trigger tgtype=19)
     12.4 (legacy NULL contract) · 12.5 (ไม่มี DELETE grant)

4. ถ้าผ่านครบ  จึงไปขั้นถัดไปของ B1
     provision advisor_web (ต้องการ ADVISOR_WEB_PASSWORD จากเจ้าของ)
     -> migration 006 (ADD COLUMN supabase_user_id + GRANT)
     -> implement M3
```

### 15.1 ลำดับที่สลับไม่ได้

```
Apply 005  ->  CREATE ROLE advisor_web  ->  Migration 006 (ADD COLUMN + GRANT)  ->  M3
```

GRANT ใน 006 อ้างถึง `web.*` (ต้องมาจาก 005) และ `public.users.supabase_user_id`
(ต้องมาจาก 006 เอง) · และถ้า 006 รันก่อนสร้าง role GRANT จะถูกข้ามเงียบ ๆ
(ดู `B1_ADVISOR_WEB_ROLE_DESIGN.md` W2)

---

## บันทึกการเข้าถึงข้อมูลในรอบนี้

| ระบบ | การเข้าถึง | รายละเอียด |
|---|---|---|
| git | **อ่านอย่างเดียว** | `rev-parse` · `diff` · `log` · `hash-object` · `fetch --quiet` (ไม่เปลี่ยน working tree) |
| ไฟล์ในรีโป | **อ่านอย่างเดียว** | `005_web_schema.sql` · `001–004` · `sha256sum` · `grep` |
| production PostgreSQL | **`SELECT` อย่างเดียว** | `pg_namespace` · `pg_class` · `pg_proc` · `pg_constraint` · `pg_attribute` · `pg_locks` · `pg_stat_activity` · `pg_extension` · `mko.schema_migrations` · `current_setting()` · `pg_database_size()` · `count(*)` |
| production filesystem | **อ่านอย่างเดียว** | `df -h` |
| คำสั่งเขียน / DDL / DCL | **ไม่มีแม้คำสั่งเดียว** | ไม่มี `CREATE` · `ALTER` · `DROP` · `GRANT` · `REVOKE` · `INSERT` · `UPDATE` · `DELETE` |

---

## STOP

# `MIGRATION_005_READY_TO_APPLY`

**ยังไม่ apply** — รอบนี้เป็น gate เท่านั้น

```
Apply Migration 005  NONE   CREATE SCHEMA/TABLE  NONE   ALTER            NONE
INSERT/UPDATE/DELETE NONE   CREATE ROLE          NONE   GRANT / REVOKE   NONE
ADVISOR_WEB_PASSWORD NONE   แก้ .env              NONE   Provision role   NONE
Migration 006        NONE   Data Migration       NONE   แก้ source       NONE
Deploy / Restart     NONE   Commit / Push / Merge NONE
```

เรื่องที่รอการตัดสินใจ

1. **อนุมัติ apply Migration 005 บน production** หรือไม่
2. **ยืนยันว่าคำสั่ง apply จะมี `ON_ERROR_STOP=1` และ `lock_timeout`** (ข้อ 14.4)
   — ทั้งสองไม่มีในค่าตั้งต้น และขาดข้อใดข้อหนึ่งทำให้ความปลอดภัยที่วิเคราะห์ไว้หายไป
3. **จะสำรองฐานข้อมูลก่อน apply ไหม** (ข้อ 11.1 ขั้นที่ 4) — แนะนำว่าทำ ถึงแม้ 005
   จะไม่แตะข้อมูลธุรกิจ
