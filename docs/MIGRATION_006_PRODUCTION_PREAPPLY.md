# Migration 006 — Production Pre-Apply Verification

| | |
|---|---|
| เวลาที่ตรวจ | **2026-10-03 17:11:13 +07** (เวลาจากเซิร์ฟเวอร์ฐานข้อมูลเอง) |
| **Classification** | **`MIGRATION_006_PREAPPLY_READY`** |
| ผลตรวจ | **51 ข้อ** — เทียบค่า 44 ข้อ **ผ่านครบ** · อีก 7 ข้อเป็น baseline/ข้อมูลประกอบ |
| SHA-256 ของ artifact | **ตรงกับรายงาน review** |
| Production write ในรอบนี้ | **ไม่มีแม้คำสั่งเดียว** |

```
Apply Migration 006   NONE     ALTER TABLE            NONE     CREATE INDEX      NONE
GRANT / REVOKE        NONE     INSERT/UPDATE/DELETE   NONE     เติม S1           NONE
Data Migration        NONE     Supabase Write         NONE     แก้ production .env NONE
Deploy / Restart      NONE     terminate session      NONE     Commit/Push/Merge NONE
```

การตรวจทั้งหมดรันภายใต้ `PGOPTIONS='-c default_transaction_read_only=on'`
และ SQL เป็น `SELECT … UNION ALL …` ล้วน

**ไม่มีรหัสผ่าน ไม่มี hash ไม่มี connection string ที่มีรหัสผ่านในเอกสารนี้**

### วิธีนับข้อตรวจ

| ประเภท | จำนวน | ผล |
|---|---|---|
| เทียบค่ากับค่าที่คาดหวังแบบตรงตัว | **43** | ✅ ผ่านครบ |
| เทียบแบบนำหน้า (`server_version` ได้ `16.15 (Debian …)` เทียบกับ `16.15`) | **1** | ✅ |
| **baseline / ข้อมูลประกอบ** ที่ไม่มีค่าคาดหวังตายตัว | **7** | บันทึกไว้เทียบหลัง apply |
| **รวม** | **51** | **ไม่มีข้อใดไม่ผ่าน** |

7 ข้อที่เป็น baseline คือจำนวนสิทธิ์ของ `advisor_api`/`advisor_ingest` (3 ข้อ)
จำนวน session · `lock_timeout` ปัจจุบัน · transaction ที่เปิดนานที่สุด · เวลาที่ตรวจ

---

## 1. Production database identity

| | |
|---|---|
| เซิร์ฟเวอร์ | `ubuntu@161.118.237.37` (OCI) |
| คอนเทนเนอร์ฐานข้อมูล | `course-advisor-system-postgres-1` · image `pgvector/pgvector:pg16` |
| ฐานข้อมูล | **`course_advisor`** (ยืนยันด้วย `current_database()` ไม่ได้เดาจาก URL) |
| เวอร์ชัน | **PostgreSQL 16.15** (Debian 16.15-1.pgdg12+2) |
| ผู้ใช้ที่จะใช้ apply | `postgres` — superuser และเป็นเจ้าของ `public.users` |

**ไม่มีรหัสผ่านในเอกสารนี้** · การเชื่อมต่อใช้ `docker exec` ภายในเครื่อง
ซึ่งไม่ต้องใช้รหัสผ่าน (pg_hba บรรทัด `local` เป็น `trust`)

---

## 2. Migration state

| ข้อตรวจ | ได้ | คาดหวัง | ผล |
|---|---|---|---|
| รายการใน ledger | `001_mko_structured, 002_mko_review_publish, 003_crawl_sources, 004_crawl_decisions, 005_web_schema` | เท่ากัน | ✅ |
| จำนวนรายการ | **5** | 5 | ✅ |
| **มี `006_web_identity_mapping` แล้วหรือยัง** | **0** | 0 | ✅ **ยังไม่ apply** |

---

## 3. Schema state

### 3.1 สิ่งที่ 006 จะสร้าง — ต้องยังไม่มี

| ข้อตรวจ | ได้ | คาดหวัง | ผล |
|---|---|---|---|
| คอลัมน์ `public.users.supabase_user_id` | **0** | 0 | ✅ ยังไม่มี |
| ชื่อ index `uq_users_supabase_user_id` ว่างอยู่ | **0** | 0 | ✅ ไม่ชนกับของเดิม |

> ตรวจชื่อ index ทั้งฐาน ไม่ใช่แค่ใน `public` เพราะชื่อ index ต้องไม่ซ้ำภายใน schema
> และ `CREATE UNIQUE INDEX IF NOT EXISTS` จะ **ข้ามเงียบ ๆ** ถ้าชื่อถูกใช้ไปแล้ว
> ซึ่งจะได้ฐานข้อมูลที่ ledger บอกว่า 006 ลงแล้วแต่ไม่มี index ที่ต้องการ

### 3.2 `public.users` ปัจจุบัน

| ข้อตรวจ | ได้ | คาดหวัง | ผล |
|---|---|---|---|
| **จำนวนแถว** | **198** | 198 | ✅ |
| คอลัมน์ทั้งหมด | `id, email, password_hash, full_name, is_active, is_admin, created_at, updated_at` | เท่ากับ `db/schema.sql` | ✅ **ไม่มี drift** |
| ชนิดของ `id` | `uuid` | uuid | ✅ |
| ชนิดของ `is_active` | `boolean` | boolean | ✅ |
| เจ้าของตาราง | `postgres` | postgres | ✅ |
| เปิด RLS อยู่ไหม | **false** | false | ✅ |

### 3.3 ทำไมต้องตรวจสามข้อหลังนี้

| ข้อตรวจ | ถ้าไม่ตรงจะเกิดอะไร |
|---|---|
| คอลัมน์ `is_active` มีอยู่และเป็น boolean | `GRANT SELECT (id, is_active, supabase_user_id)` จะล้มทันที — คอลัมน์ที่ระบุใน GRANT ต้องมีอยู่จริง |
| เจ้าของเป็น `postgres` | ผู้ใช้ที่ apply ต้องมีสิทธิ์ `GRANT` บนตาราง ซึ่งต้องเป็นเจ้าของหรือ superuser |
| RLS ปิดอยู่ | ถ้าเปิด RLS ไว้ สิทธิ์ที่ให้ใน 006 จะถูก policy กรองอีกชั้นโดยที่ 006 ไม่รู้ |

---

## 4. advisor_web state

| คุณสมบัติ | ได้ | คาดหวัง | ผล |
|---|---|---|---|
| role มีอยู่ | **1** | 1 | ✅ |
| `rolcanlogin` | **true** | true | ✅ |
| `rolsuper` | **false** | false | ✅ |
| `rolcreatedb` | **false** | false | ✅ |
| `rolcreaterole` | **false** | false | ✅ |
| `rolreplication` | **false** | false | ✅ |
| `rolbypassrls` | **false** | false | ✅ |
| มีรหัสผ่านตั้งไว้ | **true** | true | ✅ |

ข้อสุดท้ายอ่านเฉพาะ predicate `rolpassword IS NOT NULL`
**ไม่อ่านและไม่แสดงตัว hash** ตามที่สั่ง

ความสำคัญ: migration 006 มีด่าน `RAISE EXCEPTION` ถ้าไม่พบ role นี้ →
ถ้า role หายไป การ apply จะล้มทั้ง transaction แทนที่จะข้ามเงียบ ๆ

---

## 5. advisor_web privilege baseline — ต้องว่างทุกช่องก่อน 006

| ข้อตรวจ | ได้ | คาดหวัง | ผล |
|---|---|---|---|
| `information_schema.table_privileges` | **0** | 0 | ✅ |
| `information_schema.column_privileges` | **0** | 0 | ✅ |
| `information_schema.routine_privileges` | **0** | 0 | ✅ |
| `has_table_privilege` SELECT `public.users` | **false** | false | ✅ |
| `has_table_privilege` INSERT `public.users` | **false** | false | ✅ |
| `has_table_privilege` UPDATE `public.users` | **false** | false | ✅ |
| `has_table_privilege` DELETE `public.users` | **false** | false | ✅ |
| **`has_any_column_privilege` SELECT `public.users`** | **false** | false | ✅ |
| `has_schema_privilege` USAGE บน `web` | **false** | false | ✅ |
| DELETE ใน schema `web` ของ advisor role ใด ๆ | **0** | 0 | ✅ |
| เป็นสมาชิก role อื่น | **0** | 0 | ✅ |

> ข้อ `has_any_column_privilege` สำคัญเป็นพิเศษ — มันคืน true ถ้ามีสิทธิ์
> **ระดับตารางหรือระดับคอลัมน์ใดก็ได้** การที่มันเป็น false ยืนยันว่า
> ยังไม่มีสิทธิ์จาก 006 หลงเข้ามาก่อนเวลาแม้คอลัมน์เดียว

---

## 6. Dependency verification

006 อ้างถึง object เหล่านี้ · ถ้าขาดตัวใดการ apply จะล้ม

| object | ได้ | ผล |
|---|---|---|
| `public.users` | พบ (relkind = `r`) | ✅ |
| ตารางใน schema `web` | `ai_settings, external_news, knowledge_articles, news, site_courses` | ✅ ครบ 5 |
| **`web.touch_updated_at()`** | พบ · **`pronargs = 0`** | ✅ |
| `mko.schema_migrations` | พบ | ✅ |
| constraint ของ `version` (รองรับ `ON CONFLICT`) | **1** | ✅ |

> ตรวจ `pronargs = 0` เพราะ 006 เขียน `GRANT EXECUTE ON FUNCTION web.touch_updated_at()`
> ซึ่งระบุ signature แบบไม่มี argument · ถ้าฟังก์ชันถูกเปลี่ยน signature
> คำสั่งนี้จะล้มด้วย `function does not exist`
>
> ตรวจ constraint ของ `version` เพราะบรรทัดสุดท้ายใช้ `ON CONFLICT (version) DO NOTHING`
> ซึ่งต้องมี unique หรือ primary key บนคอลัมน์นั้น ไม่งั้นจะล้ม

---

## 7. Existing roles regression baseline

**บันทึกไว้เพื่อเทียบหลัง apply** — ค่าทั้งหมดนี้ต้องไม่เปลี่ยน

| รายการ | ค่า baseline |
|---|---|
| `advisor_api` บน `public.users` | **`INSERT,SELECT,UPDATE`** |
| `advisor_api` ใน schema `web` (จำนวนรายการสิทธิ์) | **13** |
| `advisor_api` `EXECUTE` บน `web.touch_updated_at()` | **true** |
| `advisor_ingest` ใน schema `web` (จำนวนรายการสิทธิ์) | **7** |
| `advisor_ingest` `EXECUTE` บน `web.touch_updated_at()` | **true** |
| **`advisor_ingest` DELETE ใน schema `mko`** | **24 ตาราง** |
| DELETE ใน schema `web` ของ advisor role ใด ๆ | **0** |

> รายการสุดท้ายของ `advisor_ingest` บน `mko` มาจาก migration 001/002 ตั้งแต่ต้น
> ไม่เกี่ยวกับ 006 · บันทึกไว้เพราะเคยทำให้ข้อตรวจของผมเองรายงานผิดมาแล้ว
> (ดู `MIGRATION_006_IDENTITY_MAPPING_REVIEW.md` ข้อ 9.4)

---

## 8. Lock / activity check

**ไม่มีการ terminate session ใด ๆ** — อ่านอย่างเดียว

| ข้อตรวจ | ได้ | คาดหวัง | ผล |
|---|---|---|---|
| session อื่นในฐานนี้ | **2** | — | ดูรายละเอียดข้างล่าง |
| **`idle in transaction`** | **0** | 0 | ✅ |
| **transaction ที่เปิดค้างอยู่** | **ไม่มีเลย** | ไม่มี | ✅ |
| **lock บน `public.users`** | **0** | 0 | ✅ |
| query ที่กำลังรอ lock | **0** | 0 | ✅ |
| prepared transaction ค้าง | **0** | 0 | ✅ |
| `lock_timeout` ปัจจุบันของเซิร์ฟเวอร์ | `0` (ไม่จำกัด) | จะตั้งเป็น 10s ตอน apply | — |

### 8.1 รายละเอียด session ทั้งสอง

| ผู้ใช้ | application | state | ไม่เปลี่ยนสถานะมานาน | transaction | รอ |
|---|---|---|---|---|---|
| `advisor_api` | — | **`idle`** | ~53,179 วิ (≈ 14.8 ชม.) | **ไม่มี** | Client |
| `postgres` | `psql` | **`idle`** | ~1,348,782 วิ (≈ 15.6 วัน) | **ไม่มี** | Client |

### 8.2 ⚠ อ่านผลให้ถูก — `idle` ไม่ใช่ `idle in transaction`

| สถานะ | ถือ lock ไหม | ขวาง `ACCESS EXCLUSIVE` ไหม |
|---|---|---|
| `idle` | **ไม่ถือ** | **ไม่ขวาง** |
| `idle in transaction` | **ถือ** จนกว่าจะ commit/rollback | **ขวางได้ไม่จำกัดเวลา** |

ทั้งสอง session เป็น `idle` และ **ไม่มี transaction เปิดอยู่** (`xact_start` เป็น NULL)
→ **ไม่ถือ lock ใด ๆ** ยืนยันซ้ำด้วยข้อตรวจ `lock บน public.users = 0`

### 8.3 ข้อสังเกตที่ต้องรายงาน — session `psql` ที่ค้างมา 15.6 วัน

เป็น session ของผู้ใช้ `postgres` ที่เปิดค้างไว้ ไม่ได้ทำอะไร

| | |
|---|---|
| เป็นตัวขวางการ apply ไหม | **ไม่** — `idle` ไม่ถือ lock และไม่มี transaction |
| ความเสี่ยงที่เหลือ | ถ้ามีคนไปพิมพ์คำสั่งใน session นั้น**ระหว่าง**ที่ 006 กำลัง apply อาจชน lock กันได้ |
| จะทำอะไรกับมัน | **ไม่ทำอะไร** — รอบนี้ห้าม terminate session และมันไม่ขวางอยู่แล้ว |
| ข้อเสนอ | ก่อน apply ให้เจ้าของตรวจว่าไม่มีใครกำลังใช้ session นั้นอยู่ |

### 8.4 ความเสี่ยงเรื่อง lock ที่เหลือ

`ALTER TABLE … ADD COLUMN` ต้องการ **ACCESS EXCLUSIVE** บน `public.users`
ซึ่งเป็นตารางที่ `advisor_api` ใช้ยืนยันตัวตนของ backend

| ปัจจัย | สถานะตอนนี้ |
|---|---|
| มี transaction ค้างที่จะทำให้รอนาน | **ไม่มี** |
| มี lock บนตารางนั้น | **ไม่มี** |
| เวลาที่ต้องถือ lock | **≈ 16.7 ms** (วัดจริงบนตาราง 198 แถว ดู review ข้อ 12.3) |
| ถ้ารอ lock ไม่ได้ | `lock_timeout = 10s` จะทำให้ล้มและถอนกลับ แทนที่จะค้างและบล็อกการเข้าสู่ระบบ |

---

## 9. Migration artifact — SHA-256

| | |
|---|---|
| ไฟล์ | `db/migrations/006_web_identity_mapping.sql` |
| บรรทัด | **148** |
| line ending | **LF** (ไม่มี CRLF) |
| **SHA-256 ของไฟล์จริงตอนนี้** | `fb22346bf651312a9025c0553fcb8f2637751633cfd1ae2b6f302e4bdc203376` |
| **SHA-256 ที่บันทึกใน review report** | `fb22346bf651312a9025c0553fcb8f2637751633cfd1ae2b6f302e4bdc203376` |
| **ผลเทียบ** | **ตรงกัน** ✅ |

```
A=$(sha256sum db/migrations/006_web_identity_mapping.sql | cut -d' ' -f1)
B=$(grep -oE '\b[0-9a-f]{64}\b' docs/MIGRATION_006_IDENTITY_MAPPING_REVIEW.md | head -1)
[ "$A" = "$B" ]  ->  ตรงกัน
```

**ไฟล์ที่จะ apply คือไฟล์เดียวกับที่ผ่าน review** ไม่มีการแก้ไขหลังจากนั้น
(เวลาแก้ไขล่าสุดของไฟล์ `16:47:01` ก่อนเวลาที่เขียนรายงาน review `17:00:52`)

ไฟล์ยังเป็น **untracked** ใน git — ยังไม่ commit ตามที่สั่ง

---

## 10. Risks

### 10.1 ความเสี่ยงที่ประเมินแล้ว

| # | ความเสี่ยง | ระดับ | เหตุผล / สิ่งที่รองรับไว้ |
|---|---|---|---|
| 1 | `ALTER TABLE` ถือ ACCESS EXCLUSIVE แล้วบล็อกการเข้าสู่ระบบ | **ต่ำ** | ไม่มี transaction ค้าง · ไม่มี lock · ใช้เวลา ≈ 16.7 ms · มี `lock_timeout=10s` รองรับ |
| 2 | ล้มกลางคันแล้วเหลือสถานะครึ่ง ๆ | **ต่ำมาก** | ทั้งไฟล์อยู่ใน transaction เดียว · ทดสอบเส้นทางล้มเหลวแล้วถอนกลับครบ |
| 3 | `advisor_web` หายไประหว่างทาง | **ต่ำมาก** | ยืนยันแล้วว่ามีอยู่ · และถ้าหายจริง migration จะ `RAISE EXCEPTION` ไม่ใช่ข้ามเงียบ |
| 4 | ชื่อ index ชนของเดิม | **ไม่มี** | ตรวจแล้วชื่อว่าง |
| 5 | schema drift ทำให้ GRANT ล้ม | **ไม่มี** | คอลัมน์ทั้ง 8 ตรงกับ `db/schema.sql` · `is_active` เป็น boolean |
| 6 | สิทธิ์ของ `advisor_api`/`advisor_ingest` ถดถอย | **ไม่มี** | ไฟล์ไม่มีคำว่า `REVOKE` เลย · มี baseline ไว้เทียบแล้ว |
| 7 | ข้อมูลผู้ใช้ 198 แถวถูกแก้ | **ไม่มี** | ไฟล์เขียนข้อมูลที่เดียวคือ ledger · คอลัมน์ใหม่เป็น NULL ทั้งหมด |

### 10.2 ⚠ ความเสี่ยงที่ยังเปิดอยู่ — ต้องรู้ก่อนตัดสินใจ

| # | เรื่อง | ผลกระทบ |
|---|---|---|
| 1 | **`advisor_web` พึ่ง `CONNECT` และ `USAGE ON SCHEMA public` ที่ได้จาก `PUBLIC`** | 006 ไม่ได้ให้สองอย่างนี้โดยตรง · วันนี้ใช้ได้ แต่ถ้ามีใคร `REVOKE … FROM PUBLIC` ภายหลัง `webapi` จะพังโดยที่ ledger ยังบอกว่า 006 ลงเรียบร้อย · **รอการตัดสินใจจากรอบ review** |
| 2 | session `psql` ค้างมา 15.6 วัน | ไม่ขวาง แต่ควรยืนยันว่าไม่มีใครใช้อยู่ก่อน apply (ข้อ 8.3) |
| 3 | หลัง apply แล้ว `webapi` ยังใช้งานจริงไม่ได้ | ค่า `supabase_user_id` ยังไม่มีของใคร และ `ADVISOR_WEB_PASSWORD` ยังไม่อยู่ใน production `.env` — เป็นรอบแยกทั้งคู่ |

### 10.3 สิ่งที่ยังไม่มีและเสนอให้ทำตอน apply

**ยังไม่มีการสำรองฐานข้อมูลสำหรับรอบนี้** — ตอน apply 005 มีการสำรองก่อน
ควรทำแบบเดียวกัน (อยู่ในคำสั่งข้อ 11)

---

## 11. Exact proposed apply command

**ยังไม่รัน** — รอการอนุมัติเป็นรอบแยก

### 11.1 ขั้นที่ 1 — สำรองก่อน

```bash
ssh -i ~/.ssh/oci.key ubuntu@161.118.237.37 \
  'docker exec -i course-advisor-system-postgres-1 pg_dump -U postgres -d course_advisor -Fc' \
  > backup-before-006-$(date +%Y%m%d-%H%M%S).dump
```

ตรวจว่าไฟล์มีขนาดสมเหตุสมผลก่อนไปขั้นต่อไป

### 11.2 ขั้นที่ 2 — ยืนยัน hash อีกครั้งทันทีก่อน apply

```bash
sha256sum db/migrations/006_web_identity_mapping.sql
```

ต้องได้ `fb22346bf651312a9025c0553fcb8f2637751633cfd1ae2b6f302e4bdc203376`
**ถ้าไม่ตรง ห้าม apply**

### 11.3 ขั้นที่ 3 — apply

```bash
ssh -i ~/.ssh/oci.key ubuntu@161.118.237.37 \
  "docker exec -i -e PGOPTIONS='-c lock_timeout=10s' course-advisor-system-postgres-1 \
   psql -U postgres -d course_advisor -v ON_ERROR_STOP=1" \
  < db/migrations/006_web_identity_mapping.sql
```

| ส่วนประกอบ | ทำไมต้องมี |
|---|---|
| **`-v ON_ERROR_STOP=1`** | **บังคับ** — ไม่งั้น psql จะรันคำสั่งถัดไปทั้งที่ล้มไปแล้ว |
| **`PGOPTIONS='-c lock_timeout=10s'`** | **บังคับ** — กันกรณี `ALTER TABLE` รอ ACCESS EXCLUSIVE ค้างแล้วบล็อกการเข้าสู่ระบบ |
| ส่งไฟล์ทาง stdin ตรง ๆ | **ไม่มีขั้นคัดลอกไฟล์ขึ้นเซิร์ฟเวอร์** จึงไม่มีโอกาสที่ไฟล์จะต่างจากที่ตรวจ hash ไว้ |

### 11.4 ผลลัพธ์ที่ต้องเห็น

```
BEGIN
ALTER TABLE
COMMENT
CREATE INDEX
DO
GRANT          (8 ครั้ง)
INSERT 0 1
COMMIT
```

### 11.5 ถ้าเกิดอะไรขึ้นให้หยุดทันที

| อาการ | ความหมาย | ทำอะไร |
|---|---|---|
| `ERROR: ไม่พบ role advisor_web` | role หายไประหว่างทาง | **STOP** · ทุกอย่างถอนกลับแล้ว · ตรวจว่าเกิดอะไรกับ role |
| `ERROR: canceling statement due to lock timeout` | มีอะไรถือ lock บน `public.users` | **STOP** · ถอนกลับแล้ว · หาว่าใครถือ lock **ห้าม terminate เอง** |
| `ROLLBACK` หรือ ERROR อื่นใด | — | **STOP ทันที · ห้ามแก้ production สด ๆ · ห้าม retry อัตโนมัติ** |

---

## 12. Exact post-apply verification plan

รันทันทีหลัง apply · **READ-ONLY ทั้งหมด** ภายใต้ `default_transaction_read_only=on`

### 12.1 ชุดตรวจบน production (20 ข้อ)

| # | ข้อตรวจ | คาดหวัง |
|---|---|---|
| 1 | ledger มี `006_web_identity_mapping` | 1 |
| 2 | จำนวนรายการใน ledger | 6 |
| 3 | คอลัมน์ `supabase_user_id` มีอยู่ | 1 |
| 4 | ชนิดเป็น `uuid` | uuid |
| 5 | `is_nullable` | YES |
| 6 | `column_default` | NULL |
| 7 | index `uq_users_supabase_user_id` มีอยู่ | 1 |
| 8 | `indisunique` | true |
| 9 | เป็น partial และเงื่อนไขคือ `supabase_user_id IS NOT NULL` | true |
| 10 | **จำนวนแถว `public.users`** | **198 เท่าเดิม** |
| 11 | **แถวที่ `supabase_user_id` ไม่ใช่ NULL** | **0** (ไม่มี backfill) |
| 12 | `has_table_privilege` SELECT `public.users` ของ `advisor_web` | **false** |
| 13 | `has_column_privilege` `id` / `is_active` / `supabase_user_id` | true ทั้งสาม |
| 14 | `has_column_privilege` `email` / `password_hash` / `full_name` / `is_admin` | **false ทั้งสี่** |
| 15 | `has_table_privilege` INSERT/UPDATE/DELETE `public.users` | false ทั้งสาม |
| 16 | สิทธิ์ `advisor_web` ในแต่ละตารางของ `web` ตรงตาราง endpoint | ตามเมทริกซ์ |
| 17 | DELETE ของ advisor role ใด ๆ ใน schema `web` | **0** |
| 18 | `has_function_privilege` `web.touch_updated_at()` ของ `advisor_web` | true |
| 19 | **`advisor_api` บน `public.users`** | **`INSERT,SELECT,UPDATE` เท่า baseline** |
| 20 | `advisor_api` ใน `web` = 13 · `advisor_ingest` ใน `web` = 7 · `advisor_ingest` DELETE ใน `mko` = 24 | **เท่า baseline ข้อ 7** |

### 12.2 ⚠ ข้อที่ต้องระวังตอนเขียน query ตรวจ

| กับดัก | วิธีเลี่ยง |
|---|---|
| `information_schema.table_privileges` รายงานสิทธิ์โดยปริยายของ **เจ้าของตาราง** (`postgres`) ด้วย | **กรอง `grantee` เสมอ** — เคยทำให้ post-apply ของ 005 รายงานผิดมาแล้ว |
| `has_table_privilege` ไม่ได้ดูสิทธิ์ระดับคอลัมน์ | ใช้ `has_column_privilege` สำหรับข้อ 13–14 และใช้ `has_table_privilege` เฉพาะข้อ 12 |
| ใช้ `||` ต่อสตริงกับตัวคั่น `~` | **ห้าม** — PostgreSQL ตีความ `~` เป็น regex operator ทำให้ทุกข้อผ่านโดยไม่ได้ตรวจอะไร (เคยเกิดกับ 005) · ใช้ `SELECT` สามคอลัมน์แทน |

### 12.3 ตรวจเชิงพฤติกรรมด้วย — ไม่ใช่แค่ catalog

หลังผ่าน 20 ข้อข้างบน ให้สวมบทเป็น `advisor_web` ด้วย `SET ROLE` ใน transaction
ที่ **ปิดท้ายด้วย `ROLLBACK`** แล้วยืนยัน

```
SELECT id, is_active, supabase_user_id FROM public.users LIMIT 1   ->  ต้องได้ผล
SELECT email FROM public.users LIMIT 1                             ->  ต้องถูกปฏิเสธ 42501
SELECT * FROM public.users LIMIT 1                                 ->  ต้องถูกปฏิเสธ 42501
UPDATE public.users SET is_active = is_active WHERE false          ->  ต้องถูกปฏิเสธ 42501
DELETE FROM web.news WHERE false                                   ->  ต้องถูกปฏิเสธ 42501
```

> ทั้งหมดใช้ `WHERE false` และจบด้วย `ROLLBACK` จึงไม่แตะข้อมูลจริงแม้แถวเดียว
> **ต้องขออนุมัติแยก** เพราะเปิด transaction บน production แม้จะ rollback

### 12.4 ถ้าข้อใดไม่ผ่าน

**STOP ทันที · ห้ามแก้ production สด ๆ · ห้าม `GRANT`/`REVOKE` เพิ่มเอง**
รายงานผลแล้วรอการตัดสินใจ · มีสคริปต์ถอนกลับพร้อมใช้ใน
`MIGRATION_006_IDENTITY_MAPPING_REVIEW.md` ข้อ 13.1 (ทดสอบแล้ว)

---

## บันทึกการเข้าถึงข้อมูลในรอบนี้

| ระบบ | การเข้าถึง | รายละเอียด |
|---|---|---|
| production PostgreSQL | **`SELECT` อย่างเดียว** | 51 ข้อตรวจ + รายละเอียด session · รันใต้ `default_transaction_read_only=on` · **ไม่มี DDL / DML / GRANT / REVOKE** |
| production session | **อ่าน `pg_stat_activity` เท่านั้น** | **ไม่ terminate ใคร** |
| ไฟล์ในรีโป | **อ่านอย่างเดียว** | ตรวจ SHA-256 ของ migration |
| Supabase | **ไม่ได้เข้าถึงเลย** | — |
| git | ไม่ commit ไม่ push | ไฟล์ของ 006 ยัง untracked |

---

## STOP

# `MIGRATION_006_PREAPPLY_READY`

**เทียบค่า 44 ข้อผ่านครบ · SHA-256 ตรงกับ artifact ที่ผ่าน review · ไม่พบสิ่งกีดขวาง**

```
Apply Migration 006   NONE     ALTER TABLE            NONE     CREATE INDEX      NONE
GRANT / REVOKE        NONE     INSERT/UPDATE/DELETE   NONE     เติม S1           NONE
Data Migration        NONE     Supabase Write         NONE     แก้ production .env NONE
Deploy / Restart      NONE     terminate session      NONE     Commit/Push/Merge NONE
```

เรื่องที่รอการตัดสินใจก่อน apply

1. ⚠ **ข้อ 10.2 #1** — จะใส่ `GRANT CONNECT` และ `GRANT USAGE ON SCHEMA public`
   ลง 006 ไหม · **ถ้าเอา ต้องแก้ไฟล์ก่อน apply และ SHA-256 จะเปลี่ยน**
2. ยืนยันว่าไม่มีใครกำลังใช้ session `psql` ที่ค้างมา 15.6 วัน (ข้อ 8.3)
3. อนุมัติรอบ **Apply** — คำสั่งพร้อมแล้วในข้อ 11 รวมขั้นสำรองและขั้นยืนยัน hash
4. อนุมัติ **commit** ไฟล์ของ 006 (ตอนนี้ยัง untracked ทั้งหมด)
