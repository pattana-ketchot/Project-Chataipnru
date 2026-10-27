# Migration 005 — Production Apply Result

| | |
|---|---|
| วันที่ | 2026-10-03 |
| **Classification** | **`MIGRATION_005_APPLIED_VERIFIED`** |
| ไฟล์ที่ apply | `db/migrations/005_web_schema.sql` · **376 บรรทัด · 31,265 ไบต์** |
| SHA256 | **`64aaa21812086ab58835419a57fcbbbbe421e3729a0ca35d4857bb90723c273e`** — ตรงกับที่ผ่าน review |
| ผล apply | **`PSQL_EXIT = 0`** · `COMMIT` · **ไม่มี ERROR ไม่มี ROLLBACK ไม่มี WARNING** |
| Post-apply verification | **ผ่าน 36 ข้อ · ไม่ผ่าน 0** |
| Backup | **53,851,203 ไบต์ · 251 TOC entries** · ยืนยันอ่านได้ด้วย `pg_restore -l` |
| ข้อมูลธุรกิจที่เปลี่ยน | **ไม่มี** — `public.users` 198 → 198 · `public.courses` 24 → 24 |
| แถวใน `web.*` | **0** — ไม่มี data migration ตามที่สั่ง |

```
Data Migration   NONE   INSERT ข้อมูลเนื้อหา  NONE   CREATE ROLE advisor_web  NONE
ADVISOR_WEB_PASSWORD NONE   แก้ .env         NONE   Migration 006            NONE
ALTER public.users NONE   เติม supabase_user_id NONE   Supabase Write        NONE
แก้ source       NONE   แก้ docker-compose   NONE   Deploy / Restart         NONE
Commit / Push / Merge NONE
```

**Production write ในรอบนี้มีเฉพาะสิ่งที่อยู่ภายใน Migration 005 และการ backup**

---

## 1. Pre-apply state

### 1.1 ตรวจไฟล์ก่อน apply

| ข้อตรวจ | ได้ | คาดหวัง | ผล |
|---|---|---|---|
| SHA256 ของ `005_web_schema.sql` | `64aaa218…c273e` | `64aaa218…c273e` | ✅ |
| uncommitted change | ไม่มี (working tree + index) | ไม่มี | ✅ |
| git blob | `9b917ea1e1adb81b597e5b9db2b294ea3ec1354e` | เท่ากับ `origin/mko-phase2` | ✅ |

### 1.2 ตรวจ production ก่อน apply — **ผ่านครบ 10 ข้อ**

| ข้อตรวจ | ได้ | คาดหวัง | ผล |
|---|---|---|---|
| `web` schema | **0** | 0 | ✅ |
| ledger มี `005_web_schema` | **0** | 0 | ✅ |
| `idle in transaction` | **0** | 0 | ✅ |
| waiting locks | **0** | 0 | ✅ |
| `public.users` | **198** | 198 | ✅ |
| `public.courses` | **24** | 24 | ✅ |
| ledger ทั้งหมด | **4** | 4 | ✅ |
| `advisor_api` มีอยู่ | **1** | 1 | ✅ |
| `advisor_ingest` มีอยู่ | **1** | 1 | ✅ |
| `pg_is_in_recovery()` | **false** | false | ✅ |

**เงื่อนไขทั้ง 5 ข้อที่เจ้าของกำหนดว่าไม่ตรงต้อง STOP — ตรงทุกข้อ**

### 1.3 ⚠ บันทึกความผิดพลาดของผมในขั้นนี้

การรายงานผล precheck ครั้งแรกแสดง `❌` ทั้ง 10 ข้อ ซึ่ง **ไม่ใช่ precheck ล้ม**
เป็นบั๊กของ `awk` ที่ผมเขียน (`-F' \\| '` ตีความ escape sequence ผิด) ทำให้ field
ว่างทั้งหมด · รันใหม่ด้วยตัวคั่นที่ถูกแล้วได้ผลตามตารางข้อ 1.2

**ไม่มีการ apply เกิดขึ้นระหว่างนั้น** — การ apply เริ่มหลังจาก precheck ผ่านครบแล้วเท่านั้น

---

## 2. Backup result

```
ไฟล์    backup_before_005_20261003_122625.dump   (ใน scratchpad ของ session)
ขนาด    53,851,203 ไบต์   (~51 MB)
sha256  c8a1731a5c35678cd5b0830514ca275505882b1aca855e0853f50a2ea7668b05
```

### 2.1 ยืนยันว่า dump ใช้งานได้จริง — ไม่ได้เชื่อขนาดไฟล์

```
pg_restore -l ของ dump นั้น คืน
    Archive created at 2026-10-03 05:26:27 UTC
    dbname: course_advisor
    TOC Entries: 251
    Compression: gzip
    Dump Version: 1.15-0
    Format: CUSTOM
```

**อ่าน table of contents ได้ 251 รายการ** → เป็น dump ที่สมบูรณ์ ไม่ใช่ไฟล์ที่เขียนไม่จบ

> ไฟล์ขนาดถูกต้องแต่เสียหายเป็นสิ่งที่เกิดได้ (เช่น ssh ตัดกลางทาง) การตรวจด้วย
> `pg_restore -l` จึงไม่ใช่ขั้นตอนเสริม

### 2.2 วิธี backup

```bash
ssh … 'docker exec course-advisor-system-postgres-1 \
  pg_dump -U postgres -d course_advisor -Fc' > backup_before_005_<timestamp>.dump
```

รูปแบบ `-Fc` (custom) เพื่อให้ `pg_restore` เลือกกู้บางส่วนได้ และบีบอัดในตัว

---

## 3. Applied artifact SHA256

ยืนยัน **สามจุด** ว่าไฟล์เดียวกันตลอดเส้นทาง

| จุด | SHA256 | บรรทัด / ไบต์ | CRLF |
|---|---|---|---|
| รีโปในเครื่อง | `64aaa218…c273e` | 376 / 31,265 | 0 |
| **บน production (`/tmp/m005/…`)** | **`64aaa218…c273e`** | **376 / 31,265** | **0** |
| ค่าที่เจ้าของระบุให้ตรวจ | `64aaa218…c273e` | — | — |

### 3.1 วิธีส่งไฟล์ — บังคับ LF

```bash
git -c core.autocrlf=false archive --format=tar HEAD db/migrations/005_web_schema.sql \
  | ssh … 'rm -rf /tmp/m005 && mkdir -p /tmp/m005 && tar -x -C /tmp/m005'
```

`core.autocrlf=false` จำเป็นเพราะเป็นบทเรียนเดิมของโปรเจกต์: `git archive` บน Windows
แปลง LF เป็น CRLF ซึ่งทำให้ checksum ไม่ตรงและอาจทำให้ SQL เพี้ยน
**ยืนยันแล้วว่า CRLF = 0 ฝั่ง production**

---

## 4. Apply command structure

```bash
ssh … "cat /tmp/m005/db/migrations/005_web_schema.sql \
  | docker exec -i -e PGOPTIONS='-c lock_timeout=10s' \
      course-advisor-system-postgres-1 \
      psql -U postgres -d course_advisor -v ON_ERROR_STOP=1 -f -"
```

**ไม่มี secret ในคำสั่ง** — `psql -U postgres` ใช้ trust auth ภายใน container
ไม่มีรหัสผ่านใดถูกส่งผ่าน command line

### 4.1 สองเงื่อนไขที่เจ้าของกำหนด — มีครบ

| เงื่อนไข | วิธีที่ใช้ | ยืนยันแล้วไหม |
|---|---|---|
| **`-v ON_ERROR_STOP=1`** | ใส่ตรงในคำสั่ง `psql` | ✅ เห็นในคำสั่ง |
| **`lock_timeout = '10s'`** | `PGOPTIONS='-c lock_timeout=10s'` ผ่าน `docker exec -e` | ✅ **พิสูจน์ก่อนรัน** ดูข้อ 4.2 |

### 4.2 พิสูจน์ว่า `lock_timeout` มีผลจริง — ไม่ได้เชื่อว่ามี

รันก่อน apply เพื่อยืนยันกลไก

```
ส่ง PGOPTIONS='-c lock_timeout=10s'  ->  SHOW lock_timeout  =  10s
ไม่ส่ง PGOPTIONS                      ->  SHOW lock_timeout  =  0
```

**ค่าตั้งต้นของ production เป็น `0` (รอไม่จำกัด)** และ `PGOPTIONS` เป็นสิ่งที่เปลี่ยนให้
เป็น `10s` จริง · ถ้าไม่พิสูจน์ขั้นนี้ก็ไม่รู้ว่าการป้องกันทำงานหรือเปล่า

### 4.3 ⚠ ตั้งใจไม่ใส่ `--single-transaction` — ต่างจากแผนในเอกสาร pre-apply

`MIGRATION_005_PRODUCTION_PREAPPLY.md` ข้อ 11.2 เสนอให้ใส่ `--single-transaction`
**รอบนี้ไม่ใส่** และนี่เป็นการเปลี่ยนอย่างตั้งใจ

| | |
|---|---|
| เหตุผล | ไฟล์ 005 มี `BEGIN;` (บรรทัด 79) และ `COMMIT;` (บรรทัด 376) **ของตัวเองอยู่แล้ว** |
| ถ้าใส่จะเกิดอะไร | `psql` เปิด transaction ก่อน แล้วเจอ `BEGIN;` ของไฟล์ → `WARNING: there is already a transaction in progress` และตอนจบจะได้ `WARNING: there is no transaction in progress` อีกครั้ง |
| ทำไมเลี่ยง | **คำเตือนสองอันนั้นไม่ได้ทำให้พัง แต่มันกลบ log** ถ้ามี warning จริงเกิดขึ้น จะแยกออกจาก warning ที่คาดไว้ยาก |
| atomicity ยังครบไหม | **ครบ** — `BEGIN/COMMIT` ในไฟล์ + `ON_ERROR_STOP=1` ให้ atomicity เต็ม · `--single-transaction` เป็นชั้นซ้ำซ้อน |
| ขัดอำนาจที่ได้รับไหม | **ไม่** — เจ้าของกำหนดเฉพาะ `ON_ERROR_STOP=1` และ `lock_timeout` ซึ่งมีครบทั้งสอง |

**ผล log ยืนยันว่าถูก**: มี `BEGIN` หนึ่งครั้งและ `COMMIT` หนึ่งครั้ง **ไม่มี WARNING ใดเลย**

---

## 5. Migration output summary

```
BEGIN
CREATE SCHEMA
COMMENT
CREATE TABLE      CREATE INDEX   CREATE INDEX   COMMENT      <- site_courses
CREATE TABLE      CREATE INDEX                               <- news
CREATE TABLE      CREATE INDEX   CREATE INDEX   COMMENT      <- external_news
CREATE TABLE      COMMENT                                    <- knowledge_articles
CREATE TABLE                                                 <- ai_settings
CREATE FUNCTION   COMMENT
CREATE TRIGGER    CREATE TRIGGER   CREATE TRIGGER   CREATE TRIGGER
DO
INSERT 0 1
COMMIT

PSQL_EXIT=0
```

### 5.1 นับคำสั่งที่สำเร็จ

| คำสั่ง | จำนวน | ตรงกับที่ไฟล์ประกาศ |
|---|---:|---|
| `BEGIN` | 1 | ✅ |
| `CREATE SCHEMA` | 1 | ✅ |
| `CREATE TABLE` | 5 | ✅ |
| `CREATE INDEX` | 5 | ✅ |
| `CREATE FUNCTION` | 1 | ✅ |
| `CREATE TRIGGER` | 4 | ✅ |
| `COMMENT` | 5 | ✅ |
| `DO` | 1 | ✅ (บล็อก GRANT) |
| `INSERT 0 1` | 1 | ✅ (ledger) |
| `COMMIT` | 1 | ✅ |

**ไม่มี `ERROR` · ไม่มี `ROLLBACK` · ไม่มี `WARNING` · ไม่มี `NOTICE` ที่บ่งชี้ปัญหา**

---

## 6. Post-apply object counts

| # | ข้อตรวจ | ได้ | คาดหวัง | ผล |
|---|---|---|---|---|
| 1 | `web` schema | **1** | 1 | ✅ |
| 2 | ตารางใน `web` | **5** | 5 | ✅ |
| 7 | `web.touch_updated_at()` | **1** | 1 | ✅ |
| 15 | index ใน `web` | **11** | 11 | ✅ |
| 15 | CHECK constraint | **3** | 3 | ✅ |
| 15 | **แถวข้อมูลใน `web.*` ทั้งหมด** | **0** | 0 | ✅ |
| 15 | schema ทั้งหมด | **`mko, public, web`** | `mko,public,web` | ✅ |
| 15 | เจ้าของ `web` | **`postgres`** | postgres | ✅ |
| 15 | RLS ใน `web` | **0** | 0 | ✅ |

### 6.1 index ทั้ง 11 ตัว

```
site_courses_pkey              UNIQUE   PK
news_pkey                      UNIQUE   PK
external_news_pkey             UNIQUE   PK
knowledge_articles_pkey        UNIQUE   PK
ai_settings_pkey               UNIQUE   PK
external_news_detail_url_key   UNIQUE   จาก detail_url TEXT NOT NULL UNIQUE (inline)
uq_site_courses_course         UNIQUE   partial  WHERE course_id IS NOT NULL
uq_external_news_slug          UNIQUE   partial  WHERE slug IS NOT NULL
idx_site_courses_published     btree
idx_news_published             btree
idx_external_news_published    btree
```

---

## 7. FK verification

| # | ข้อตรวจ | ได้ | คาดหวัง | ผล |
|---|---|---|---|---|
| 3 | FK ใน `web` | **8** | 8 | ✅ |
| 4 | **FK ที่ไม่ใช่ `ON DELETE SET NULL`** | **0** | 0 | ✅ |

**ทุกเส้นตั้ง `ON DELETE SET NULL`** (`confdeltype = 'n'`) → ลบผู้ใช้แล้วเนื้อหาไม่หาย

```
web.site_courses        course_id   -> public.courses(id)   SET NULL
web.site_courses        created_by  -> public.users(id)     SET NULL
web.site_courses        updated_by  -> public.users(id)     SET NULL
web.news                created_by  -> public.users(id)     SET NULL
web.news                updated_by  -> public.users(id)     SET NULL
web.knowledge_articles  created_by  -> public.users(id)     SET NULL
web.knowledge_articles  updated_by  -> public.users(id)     SET NULL
web.ai_settings         updated_by  -> public.users(id)     SET NULL
```

---

## 8. Trigger verification

| # | ข้อตรวจ | ได้ | คาดหวัง | ผล |
|---|---|---|---|---|
| 5 | trigger ใน `web` | **4** | 4 | ✅ |
| 6 | **trigger ที่ `tgtype <> 19`** | **0** | 0 | ✅ |
| 9 | `advisor_api` `EXECUTE` ฟังก์ชัน trigger | **true** | true | ✅ |
| 10 | `advisor_ingest` `EXECUTE` ฟังก์ชัน trigger | **true** | true | ✅ |

`tgtype = 19` = `1 (ROW) + 2 (BEFORE) + 16 (UPDATE)` → **ไม่มีบิต 4 (INSERT)**

→ **trigger ไม่ทำงานตอน INSERT** ซึ่งเป็นเงื่อนไขที่ทำให้นำข้อมูลเก่าเข้ามาได้
โดยคง `created_at` / `updated_at` เดิมไว้ (สัญญาของ B2)

```
trg_site_courses_updated_at         BEFORE UPDATE
trg_news_updated_at                 BEFORE UPDATE
trg_knowledge_articles_updated_at   BEFORE UPDATE
trg_ai_settings_updated_at          BEFORE UPDATE
```

---

## 9. Legacy author contract verification

| # | ข้อตรวจ | ได้ | คาดหวัง | ผล |
|---|---|---|---|---|
| 8 | คอลัมน์ `created_by`/`updated_by` ใน `web` ทั้งหมด | **7** | 7 | ✅ |
| 8 | **คอลัมน์ที่ `NOT NULL` หรือมี `DEFAULT`** | **0** | 0 | ✅ |

```sql
-- ข้อตรวจที่ใช้
SELECT count(*) FROM pg_attribute a …
WHERE n.nspname='web' AND a.attname IN ('created_by','updated_by')
  AND (a.attnotnull OR a.atthasdef);
-- ได้ 0
```

**สัญญา `RESOLVED_WITH_NULL_LEGACY_AUTHOR` รองรับได้จริงบน production**

| | |
|---|---|
| ทุกคอลัมน์ผู้เขียน nullable | ✅ → `created_by = NULL` ของแถว legacy ใส่ได้ |
| ไม่มี `DEFAULT` | ✅ → **การละคอลัมน์ตอน INSERT ให้ NULL ไม่ใช่ค่าแทน** — ป้องกันการยัดเจ้าของผิดคน |

7 คอลัมน์ = `site_courses` 2 + `news` 2 + `knowledge_articles` 2 + `ai_settings` 1
(`ai_settings` มีแต่ `updated_by`) · `external_news` ไม่มีคอลัมน์ผู้เขียน

---

## 10. GRANT verification

### 10.1 `advisor_api`

| # | ข้อตรวจ | ได้ | คาดหวัง | ผล |
|---|---|---|---|---|
| 9 | `SELECT` กี่ตาราง | **5** | 5 | ✅ (ทุกตาราง) |
| 9 | `INSERT` กี่ตาราง | **4** | 4 | ✅ (ไม่รวม `external_news`) |
| 9 | `UPDATE` กี่ตาราง | **4** | 4 | ✅ |
| 9 | `EXECUTE` ฟังก์ชัน trigger | **true** | true | ✅ |
| 11 | **เขียน `web.external_news` ได้ไหม** | **false** | false | ✅ |

### 10.2 `advisor_ingest`

| # | ข้อตรวจ | ได้ | คาดหวัง | ผล |
|---|---|---|---|---|
| 10 | `SELECT` กี่ตาราง | **5** | 5 | ✅ |
| 10 | `INSERT` กี่ตาราง | **1** | 1 | ✅ (เฉพาะ `external_news`) |
| 10 | `UPDATE` กี่ตาราง | **1** | 1 | ✅ |
| 10 | `EXECUTE` ฟังก์ชัน trigger | **true** | true | ✅ |
| 11 | **เขียน `web.external_news` ได้ไหม** | **true** | true | ✅ |

**การแบ่งงานถูกต้อง** — `advisor_api` เขียน 4 ตารางที่หน้าผู้ดูแลแก้ ·
`advisor_ingest` เขียนเฉพาะตารางข่าวที่ตัวดึงข้อมูลรับผิดชอบ

### 10.3 `advisor_web` — **ยังไม่มี ตามที่สั่ง**

005 ไม่พูดถึง `advisor_web` เลย · GRANT ของ role นั้นจะอยู่ใน migration 006
**ไม่ได้สร้าง role และไม่ได้ GRANT อะไรให้ในรอบนี้**

---

## 11. DELETE privilege verification

| # | ข้อตรวจ | ได้ | คาดหวัง | ผล |
|---|---|---|---|---|
| 11 | **`DELETE` ที่ให้แก่ `advisor_api` / `advisor_ingest` / `PUBLIC`** | **0** | 0 | ✅ |
| 11 | grantee ของ `DELETE` ใน `web` | **`postgres` เท่านั้น** | postgres | ✅ |
| 11 | `advisor_api` ลบ `web.news` ได้ไหม | **false** | false | ✅ |

### 11.1 ⚠ แก้เกณฑ์ที่ผมตั้งไว้ผิด — ต้องบันทึก

เกณฑ์เดิมที่ผมเขียนในเอกสาร pre-apply คือ

```sql
SELECT count(*) FROM information_schema.table_privileges
WHERE table_schema='web' AND privilege_type='DELETE';
-- ผมคาดว่าจะได้ 0
```

**ได้ 5 ไม่ใช่ 0** → ตรวจต่อแล้วพบว่า grantee คือ **`postgres` เท่านั้น** ซึ่งเป็น
**เจ้าของตาราง** ที่มีสิทธิ์ทุกอย่างโดยปริยาย · `information_schema.table_privileges`
รวมสิทธิ์ของเจ้าของไว้ด้วย

```
grantee  | tables
---------+-----------------------------------------------------------------
postgres | ai_settings, external_news, knowledge_articles, news, site_courses
```

**เกณฑ์ที่ถูกต้องคือกรองตาม grantee** ซึ่งให้ **0** ตามที่ต้องการ

| | |
|---|---|
| เป็นปัญหาของ production ไหม | **ไม่** — ไม่มี role ของบริการใดได้ `DELETE` |
| เป็นปัญหาของ 005 ไหม | **ไม่** — `grep "GRANT DELETE"` ในไฟล์ = 0 รายการ |
| เป็นอะไร | **เกณฑ์ตรวจของผมเขียนผิด** — ลืมว่าเจ้าของตารางปรากฏในมุมมองนั้นด้วย |

> **แก้เกณฑ์ไว้สำหรับรอบหน้า**: ข้อตรวจ `DELETE` ต้องกรอง
> `grantee IN ('advisor_api','advisor_ingest','advisor_web','PUBLIC')` ไม่ใช่นับทั้งมุมมอง

### 11.2 อีกสองเกณฑ์ที่ผมตั้งไว้ผิดเช่นกัน

| ข้อตรวจ | ผมคาดไว้ | ของจริง | สาเหตุที่คาดผิด |
|---|---|---|---|
| `15_indexes` | 10 | **11** | ลืมนับ `external_news_detail_url_key` ที่เกิดจาก `detail_url TEXT NOT NULL UNIQUE` แบบ inline |
| `15_public_tables` | 12 | **10** | เดาตัวเลขโดยไม่ได้ตรวจ · ของจริงคือ 10 ตารางเดิมครบถ้วน **ไม่มีตารางใดถูกเพิ่มเข้า `public`** |

**ทั้งสามข้อเป็นความผิดพลาดของเกณฑ์ที่ผมเขียน ไม่ใช่ความผิดพลาดของการ apply**
รันซ้ำด้วยเกณฑ์ที่แก้แล้ว → **ผ่านทั้ง 8 ข้อ**

---

## 12. `public.users` / `public.courses` counts before-after

| ตาราง | ก่อน apply | **หลัง apply** | เปลี่ยนไหม |
|---|---:|---:|---|
| `public.users` | 198 | **198** | **ไม่** ✅ |
| `public.courses` | 24 | **24** | **ไม่** ✅ |

### 12.1 ตารางใน `public` ครบถ้วนเท่าเดิม

```
chat_answer_cache · chat_messages · chat_sessions · course_chunks · course_documents
courses · recommendations · user_profiles · user_requirements · users

รวม 10 ตาราง  ->  ตรงกับที่ db/schema.sql สร้างไว้ทุกตัว  ไม่มีตารางใหม่ ไม่มีตารางหาย
```

### 12.2 `schema mko` ไม่ถูกแตะ

```
ตารางใน mko  20 ตาราง  ->  เท่าเดิม
```

การเปลี่ยนแปลงเดียวใน `mko` คือ **1 แถวใน `mko.schema_migrations`** ซึ่งเป็น ledger
ตามแบบแผนที่ migration 001–004 ทำทุกไฟล์

---

## 13. Migration ledger

| # | ข้อตรวจ | ได้ | คาดหวัง | ผล |
|---|---|---|---|---|
| 14 | มี `005_web_schema` | **1** | 1 | ✅ |
| 14 | จำนวน version ทั้งหมด | **5** | 5 | ✅ |

```
001_mko_structured
002_mko_review_publish
003_crawl_sources
004_crawl_decisions
005_web_schema          <- เพิ่มในรอบนี้
```

`INSERT 0 1` ใน log ยืนยันว่าเป็นการเพิ่มแถวใหม่จริง ไม่ได้ชน `ON CONFLICT`

---

## 14. Errors / warnings

### 14.1 จาก migration

```
ERROR      0
ROLLBACK   0
WARNING    0
lock timeout  0
PSQL_EXIT  0
```

**ไม่มีข้อผิดพลาดใดเลยในการ apply**

### 14.2 ข้อผิดพลาดของผม 2 จุด — ไม่กระทบ production

| # | เกิดอะไร | กระทบ production ไหม | แก้แล้วอย่างไร |
|---|---|---|---|
| 1 | รายงาน precheck ครั้งแรกแสดง `❌` ทั้ง 10 ข้อ เพราะ `awk -F' \\| '` ตีความ escape ผิด | **ไม่** — เป็นแค่การแสดงผล และ **ไม่มีการ apply ระหว่างนั้น** | รันใหม่ด้วยตัวคั่น `~` แล้วได้ผลถูกต้อง |
| 2 | ชุด post-apply ชุดแรกใช้ `~'~'||` ซึ่ง PostgreSQL ตีความ `~` เป็น regex operator → ทุก field ว่าง และ **แสดง "ผ่านครบทุกข้อ" โดยไม่ได้ตรวจอะไรเลย** | **ไม่** — เป็น `SELECT` ล้วน | เขียน SQL ใหม่เป็น 3 คอลัมน์แยก แล้วรันซ้ำ |

> **ข้อที่ 2 อันตรายกว่าข้อที่ 1** — ชุดตรวจที่รายงานว่าผ่านโดยไม่ได้ตรวจอะไร
> เป็นสิ่งที่แย่กว่าการไม่มีชุดตรวจ · ผลที่รายงานในเอกสารนี้มาจากการรันชุดที่แก้แล้ว
> ทุกค่าจับคู่กับเกณฑ์ที่ระบุชัด

---

## 15. Final classification

# `MIGRATION_005_APPLIED_VERIFIED`

### 15.1 สรุปผล

```
Pre-apply check         ผ่าน 10 / 10     (เงื่อนไข STOP ของเจ้าของครบทุกข้อ)
Backup                  สำเร็จ · ยืนยันอ่านได้ 251 TOC entries
Apply                   PSQL_EXIT = 0 · COMMIT · ไม่มี ERROR/ROLLBACK/WARNING
Post-apply verification ผ่าน 36 / 36     (28 ชุดแรก + 8 ชุดที่แก้เกณฑ์)
ข้อมูลธุรกิจที่เปลี่ยน    ไม่มี
แถวใน web.*             0
```

### 15.2 ครบตามรายการ 15 ข้อที่เจ้าของสั่งตรวจ

| # | ที่สั่ง | ผล |
|---|---|---|
| 1 | `schema web = 1` | ✅ **1** |
| 2 | `tables = 5` | ✅ **5** |
| 3 | `FK = 8` | ✅ **8** |
| 4 | FK ทุกเส้น `ON DELETE SET NULL` | ✅ **ที่ไม่ใช่ = 0** |
| 5 | `trigger = 4` | ✅ **4** |
| 6 | trigger เป็น UPDATE-only | ✅ **`tgtype <> 19` = 0** |
| 7 | `touch_updated_at() = 1` | ✅ **1** |
| 8 | author nullable และไม่มี default | ✅ **7 คอลัมน์ · ที่ผิด = 0** |
| 9 | `advisor_api` grants ถูกต้อง | ✅ SELECT 5 · INSERT 4 · UPDATE 4 · EXECUTE true |
| 10 | `advisor_ingest` grants ถูกต้อง | ✅ SELECT 5 · INSERT 1 · UPDATE 1 · EXECUTE true |
| 11 | `DELETE grants = 0` | ✅ **0 สำหรับ role ของบริการ** (ดูข้อ 11.1) |
| 12 | `public.users` ยัง 198 | ✅ **198** |
| 13 | `public.courses` ยัง 24 | ✅ **24** |
| 14 | ledger มี `005_web_schema` | ✅ **มี · ทั้งหมด 5** |
| 15 | ไม่มี unexpected object/change | ✅ `public` 10 ตารางเดิมครบ · `mko` 20 ตารางเดิมครบ · `web.*` 0 แถว · RLS 0 · เจ้าของ `postgres` |

### 15.3 ทำไมไม่ใช่สถานะอื่น

| สถานะ | ทำไมไม่ใช่ |
|---|---|
| `MIGRATION_005_APPLY_FAILED` | apply สำเร็จ `PSQL_EXIT = 0` · `COMMIT` · ไม่มี ERROR |
| `MIGRATION_005_APPLIED_VERIFICATION_FAILED` | ข้อตรวจผ่านครบ · 3 ข้อที่ขึ้น FAIL ตอนแรกเป็น **เกณฑ์ที่ผมเขียนผิด** ตรวจต่อแล้วยืนยันว่า production ถูกต้อง (ข้อ 11.1–11.2) |
| `MIGRATION_005_ABORTED_PRECHECK` | precheck ผ่านครบ 10 ข้อ **ก่อน** เริ่ม apply |

---

## 16. Exact next step

### 16.1 ⛔ หยุดที่นี่ตามที่สั่ง

```
ห้ามไป CREATE ROLE advisor_web ต่อเอง
ห้ามไป Migration 006 ต่อเอง
รอ owner อนุมัติรอบถัดไป
```

**ยืนยันว่าไม่ได้ทำ**

```
advisor_web บน production          ไม่มี  (ตรวจแล้ว)
public.users.supabase_user_id      ไม่มี
migration 006                      ไม่มีไฟล์
แถวใน web.*                        0  ทุกตาราง
Supabase                           ไม่ได้แตะเลย
source code / compose / .env       ไม่ได้แตะ
git                                HEAD = cf4fb16  ไม่ขยับ  staged 0
```

### 16.2 ลำดับที่รออนุมัติ

```
1. ขออนุมัติ provision advisor_web
     ต้องการ ADVISOR_WEB_PASSWORD จากเจ้าของก่อน (เจ้าของสร้าง ผมไม่เห็นค่า)
     CREATE ROLE ในนาม postgres  +  เพิ่มใน db/20-roles.sh สำหรับ dev/test
     ** ทั้งสองอย่าง — ดู B1_ADVISOR_WEB_ROLE_DESIGN.md W1 **

2. ขออนุมัติ migration 006
     ADD COLUMN public.users.supabase_user_id + partial unique index
     + GRANT ให้ advisor_web  (ต้องอยู่หลัง ADD COLUMN ในไฟล์เดียวกัน)
     + ข้อตรวจตาม B1_ADVISOR_WEB_ROLE_DESIGN.md ข้อ 11
     ** ห้ามแก้ 005 **

3. ขออนุมัติ implement M3  (6 ไฟล์ · DATABASE_URL ใช้ advisor_web)

4. ขออนุมัติเติม supabase_user_id ของ S1  — รันในนาม postgres โดยเจ้าของ

5. ขออนุมัติเขียนรีโปหน้าเว็บ (R6)  แล้วจึงสร้าง write endpoint

6. ขออนุมัติ commit เอกสารของรอบนี้ (ยังไม่ commit)
```

### 16.3 สิ่งที่ควรทำเร็ว ๆ นี้แม้ไม่ใช่ขั้นถัดไป

| | |
|---|---|
| **แก้เกณฑ์ `DELETE grants` ใน `eval/`** | ข้อตรวจต้องกรองตาม grantee ไม่ใช่นับทั้งมุมมอง (ข้อ 11.1) · ชุด `eval/web_schema_check.py` 103 ข้อใช้เกณฑ์ที่ถูกอยู่แล้ว (ตรวจผ่าน `has_table_privilege`) แต่เอกสารต้องแก้ |
| **เก็บ backup ไว้ที่ปลอดภัย** | ไฟล์อยู่ใน scratchpad ของ session ซึ่งเป็นที่ชั่วคราว · ถ้าต้องการเก็บไว้ ให้ย้ายออกมา |

---

## บันทึกการเข้าถึงข้อมูลในรอบนี้

| ระบบ | การเข้าถึง | รายละเอียด |
|---|---|---|
| production PostgreSQL | **เขียนเฉพาะที่อยู่ใน 005** | `CREATE SCHEMA/TABLE/INDEX/FUNCTION/TRIGGER` · `COMMENT` · `GRANT` · `INSERT` 1 แถวใน ledger · **ไม่มีคำสั่งเขียนอื่นนอกไฟล์ 005** |
| production PostgreSQL (ตรวจ) | `SELECT` / `has_*_privilege()` / `SHOW` | precheck 10 ข้อ · post-apply 36 ข้อ · สืบหาสาเหตุ 3 ข้อ |
| production filesystem | เขียน `/tmp/m005/` · อ่าน | ไฟล์ migration ชั่วคราว |
| backup | `pg_dump -Fc` → ไฟล์ใน scratchpad | 53,851,203 ไบต์ · ยืนยัน 251 TOC |
| Supabase | **ไม่ได้เข้าถึงเลย** | — |
| git / source / compose / `.env` | **ไม่ได้แตะเลย** | HEAD = `cf4fb16` · staged 0 · tracked ที่แก้ 0 |

---

## STOP

# `MIGRATION_005_APPLIED_VERIFIED`

**Migration 005 apply สำเร็จและตรวจผ่านครบแล้ว — หยุดตามที่สั่ง**

```
Data Migration   NONE   INSERT ข้อมูลเนื้อหา  NONE   CREATE ROLE advisor_web  NONE
ADVISOR_WEB_PASSWORD NONE   แก้ .env         NONE   Migration 006            NONE
ALTER public.users NONE   เติม supabase_user_id NONE   Supabase Write        NONE
แก้ source       NONE   แก้ docker-compose   NONE   Deploy / Restart         NONE
Commit / Push / Merge NONE
```

เรื่องที่รออนุมัติรอบถัดไป

1. **provision `advisor_web`** — ต้องการ `ADVISOR_WEB_PASSWORD` จากเจ้าของก่อน
2. **migration 006** — `ADD COLUMN supabase_user_id` + `GRANT` + ข้อตรวจ
3. **implement M3** — 6 ไฟล์ โดย `DATABASE_URL` ใช้ `advisor_web`
4. **commit เอกสารของรอบนี้** — ยังไม่ commit
