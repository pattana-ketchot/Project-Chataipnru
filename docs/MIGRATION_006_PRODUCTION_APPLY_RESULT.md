# Migration 006 — Production Apply Result

| | |
|---|---|
| วันที่ | **2026-10-03** |
| **Classification** | **`MIGRATION_006_APPLIED_VERIFIED`** |
| เวลา apply | **17:21–17:22 +07** (เซิร์ฟเวอร์ตั้งนาฬิกาเป็น UTC · ชื่อไฟล์ backup จึงเป็น `10:20` UTC) |
| psql exit code | **0** |
| ผลลัพธ์ | **`COMMIT`** — ไม่มี ERROR ไม่มี ROLLBACK |
| SHA-256 ที่ apply | `fb22346bf651312a9025c0553fcb8f2637751633cfd1ae2b6f302e4bdc203376` **ตรงกับที่อนุมัติ** |
| Post-apply verification | **48 ข้อเทียบค่า · ตรงทันที 45 · อีก 3 เป็นค่าคาดหวังของผมที่ผิด** (ข้อ 7) |
| ไฟล์ migration | **ไม่ถูกแก้แม้อักขระเดียวก่อน apply** |

```
แก้ Migration 006     NONE     เติม S1 supabase_user_id   NONE     Data Migration   NONE
แก้ production .env   NONE     แก้ webapi                 NONE     แก้ frontend     NONE
Supabase Write        NONE     Deploy / Restart           NONE     terminate session NONE
CREATE/ALTER/DROP ROLE NONE    GRANT/REVOKE นอก migration NONE     Commit/Push/Merge NONE
```

---

## 1. Backup result

| | |
|---|---|
| คำสั่ง | `pg_dump -U postgres -d course_advisor -Fc` ผ่าน `docker exec` |
| ไฟล์ | `/home/ubuntu/backup-before-006-20261003-102047.dump` |
| เวลาในชื่อไฟล์ | `2026-10-03 10:20:47` **UTC** = `17:20:47 +07` |
| **ขนาด** | **53,868,943 ไบต์** (≈ 51.4 MiB) |
| exit code | **0** |

เก็บไว้บนเซิร์ฟเวอร์ · บันทึก path ไว้ที่ `/home/ubuntu/.last-006-backup`

---

## 2. Backup validation

**ตรวจครบทั้ง 4 ข้อที่สั่ง ผ่านทั้งหมด**

| # | ข้อตรวจ | ผล |
|---|---|---|
| 1 | ไฟล์มีอยู่ | ✅ |
| 2 | **ขนาด > 0** | ✅ **53,868,943 ไบต์** |
| 3 | รูปแบบเป็น custom | ✅ `PostgreSQL custom database dump - v1.15-0` |
| 4 | **`pg_restore -l` อ่านได้** | ✅ **exit 0** |

### 2.1 เนื้อในของ backup

```
Archive created at 2026-10-03 10:20:47 UTC
    dbname: course_advisor
    TOC Entries: 298
    Compression: gzip
    Format: CUSTOM
    Dump Version: 1.15-0
```

รายการใน TOC ที่ไม่ใช่คอมเมนต์ **293 รายการ**

### 2.2 ตารางสำคัญอยู่ครบ

| ตาราง | พบใน TOC |
|---|---|
| `public.users` | ✅ |
| `public.courses` | ✅ |
| `public.course_chunks` | ✅ |
| `web.news` | ✅ |
| `web.site_courses` | ✅ |
| `mko.schema_migrations` | ✅ |
| schema `mko` และ `web` | ✅ ทั้งคู่ |

> `schema public` ไม่ปรากฏเป็นรายการ `CREATE SCHEMA` ใน TOC ซึ่งเป็นเรื่องปกติ
> เพราะ `public` มีอยู่แล้วในทุกฐานข้อมูล `pg_dump` จึงไม่สร้างคำสั่งสร้างมันขึ้นมา

---

## 3. Final SHA-256

```
อนุมัติ   fb22346bf651312a9025c0553fcb8f2637751633cfd1ae2b6f302e4bdc203376
ไฟล์จริง  fb22346bf651312a9025c0553fcb8f2637751633cfd1ae2b6f302e4bdc203376
ผล       ตรงกัน
```

| | |
|---|---|
| ไฟล์ | `db/migrations/006_web_identity_mapping.sql` |
| บรรทัด | **148** |
| line ending | **LF** |

**ตรวจทันทีก่อน apply ไม่ใช่ค่าเก่าจากรอบ pre-apply** — เป็นค่าที่คำนวณใหม่ในขั้นที่ 2

---

## 4. Final safety check (READ-ONLY · 17:21:30 +07)

| # | ข้อตรวจ | ได้ | คาดหวัง | ผล |
|---|---|---|---|---|
| S1 | ledger **ยังไม่มี** `006_web_identity_mapping` | **0** | 0 | ✅ |
| S2 | `advisor_web` ยังมีอยู่ | **1** | 1 | ✅ |
| S3 | `idle in transaction` | **0** | 0 | ✅ |
| S4 | **transaction ที่เปิดค้าง** | **0** | 0 | ✅ |
| S5 | **lock บน `public.users`** | **0** | 0 | ✅ |
| S6 | query ที่รอ lock | **0** | 0 | ✅ |
| S7 | จำนวนแถว `public.users` | **198** | 198 | ✅ |

ครบทั้ง 6 ข้อที่สั่ง (+ จำนวนแถวไว้เทียบหลัง apply)

---

## 5. Exact apply result

### 5.1 คำสั่งที่รันจริง

```bash
ssh -i ~/.ssh/oci.key ubuntu@161.118.237.37 \
  "docker exec -i -e PGOPTIONS='-c lock_timeout=10s' course-advisor-system-postgres-1 \
   psql -U postgres -d course_advisor -v ON_ERROR_STOP=1" \
  < db/migrations/006_web_identity_mapping.sql
```

| ข้อบังคับ | มีครบ |
|---|---|
| `-v ON_ERROR_STOP=1` | ✅ |
| `lock_timeout=10s` | ✅ ผ่าน `PGOPTIONS` ตอนเชื่อมต่อ |
| ใช้ artifact เดิมที่ hash ผ่าน | ✅ ส่งไฟล์ทาง **stdin ตรง ๆ ไม่มีขั้นคัดลอกขึ้นเซิร์ฟเวอร์** จึงไม่มีโอกาสที่เนื้อไฟล์จะต่างจากที่ตรวจ hash |
| ไม่แก้ SQL สดบน production | ✅ ไม่มีการพิมพ์ SQL เข้าไปเอง |

### 5.2 ผลลัพธ์ — ตรงกับที่คาดไว้ทุกบรรทัด

```
BEGIN
ALTER TABLE
COMMENT
CREATE INDEX
DO
GRANT
GRANT
GRANT
GRANT
GRANT
GRANT
GRANT
GRANT
INSERT 0 1
COMMIT
```

```
PSQL_EXIT = 0
```

| สิ่งที่ต้องไม่เกิด | เกิดไหม |
|---|---|
| `ERROR` | **ไม่** |
| `ROLLBACK` | **ไม่** |
| `lock timeout` | **ไม่** |
| `role advisor_web missing` | **ไม่** — `DO` block ผ่าน |
| output ที่ไม่คาดคิด | **ไม่** — ตรงกับที่ระบุไว้ใน pre-apply ข้อ 11.4 ทุกบรรทัด |

`GRANT` 8 ครั้งตรงกับจำนวนคำสั่ง GRANT ในไฟล์พอดี
(`public.users` 1 · `USAGE ON SCHEMA web` 1 · ตารางใน `web` 5 · ฟังก์ชัน 1)

`INSERT 0 1` = บันทึกลง ledger สำเร็จหนึ่งแถว ไม่ชนของเดิม

---

## 6. Post-apply verification (READ-ONLY · 17:22:31 +07)

รันใต้ `PGOPTIONS='-c default_transaction_read_only=on'` · SQL เป็น `SELECT` ล้วน
**ไม่มี behavioral write-like test** ตามที่สั่ง

### 6.1 ข้อ 1–9 — ledger และโครงสร้าง

| # | ข้อตรวจ | ได้ | คาดหวัง | ผล |
|---|---|---|---|---|
| 1 | ledger มี `006_web_identity_mapping` | **1** | 1 | ✅ |
| 2 | จำนวน migration ใน ledger | **6** | 6 | ✅ |
| 2 | รายการทั้งหมด | `001, 002, 003, 004, 005, 006` ครบตามลำดับ | เท่ากัน | ✅ |
| 3 | คอลัมน์ `supabase_user_id` มีอยู่ | **1** | 1 | ✅ |
| 4 | ชนิด | **`uuid`** | uuid | ✅ |
| 5 | `is_nullable` | **`YES`** | YES | ✅ |
| 6 | `column_default` | **`NULL`** | NULL | ✅ |
| 7 | index `uq_users_supabase_user_id` มีอยู่ | **1** | 1 | ✅ |
| 7 | `indisunique` | **true** | true | ✅ |
| 7 | เป็น partial | **true** | true | ✅ |
| 7 | อยู่บนตาราง | **`users`** | users | ✅ |
| 8 | **จำนวนแถว `public.users`** | **198** | **198 เท่าเดิม** | ✅ |
| 9 | **แถวที่ `supabase_user_id` ไม่ใช่ NULL** | **0** | 0 | ✅ **ไม่มี backfill** |

คอลัมน์ทั้งหมดของ `public.users` หลัง apply

```
id, email, password_hash, full_name, is_active, is_admin, created_at, updated_at, supabase_user_id
```

คอลัมน์ใหม่ต่อท้าย ของเดิมทั้ง 8 ไม่ถูกแตะ

### 6.2 ข้อ 10–13 — สิทธิ์บน `public.users`

| # | ข้อตรวจ | ได้ | คาดหวัง | ผล |
|---|---|---|---|---|
| 10 | **`has_table_privilege` SELECT** | **false** | false | ✅ **ไม่มี SELECT ระดับตาราง** |
| 11 | `has_column_privilege` `id` | **true** | true | ✅ |
| 11 | `has_column_privilege` `is_active` | **true** | true | ✅ |
| 11 | `has_column_privilege` `supabase_user_id` | **true** | true | ✅ |
| 11 | **รายชื่อคอลัมน์ที่ได้สิทธิ์** | **`id, is_active, supabase_user_id`** | เท่ากัน | ✅ **ไม่มีคอลัมน์ที่สี่** |
| 11 | จำนวนรายการสิทธิ์ระดับคอลัมน์บน `users` | **3** | 3 | ✅ |
| 11 | ชนิดสิทธิ์บน `users` | **`SELECT`** | SELECT | ✅ **อ่านอย่างเดียว** |
| 12 | `email` | **false** | false | ✅ |
| 12 | `password_hash` | **false** | false | ✅ |
| 12 | `full_name` | **false** | false | ✅ |
| 12 | `is_admin` | **false** | false | ✅ |
| 13 | `has_table_privilege` INSERT | **false** | false | ✅ |
| 13 | `has_table_privilege` UPDATE | **false** | false | ✅ |
| 13 | `has_table_privilege` DELETE | **false** | false | ✅ |
| 13 | **`has_any_column_privilege` UPDATE** | **false** | false | ✅ **ไม่มี UPDATE แม้ระดับคอลัมน์** |

### 6.3 ข้อ 14–16 — สิทธิ์ใน schema `web`

| # | วัตถุ | ได้ | ตรงกับ matrix ของ 006 |
|---|---|---|---|
| 14 | `USAGE ON SCHEMA web` | **true** | ✅ |
| 14 | `web.site_courses` | **`INSERT,SELECT,UPDATE`** | ✅ |
| 14 | `web.news` | **`INSERT,SELECT,UPDATE`** | ✅ |
| 14 | `web.knowledge_articles` | **`INSERT,SELECT,UPDATE`** | ✅ |
| 14 | **`web.ai_settings`** | **`SELECT,UPDATE`** | ✅ **ไม่มี INSERT ตามที่ออกแบบ** |
| 14 | **`web.external_news`** | **`SELECT`** | ✅ **อ่านอย่างเดียว** |
| 15 | **DELETE ของ `advisor_web` ทั้งฐาน** | **0** | ✅ |
| 15 | DELETE ใน schema `web` ของ advisor role ใด ๆ | **0** | ✅ |
| 16 | `EXECUTE` บน `web.touch_updated_at()` | **true** | ✅ |

`advisor_web` **ไม่มีสิทธิ์ตารางนอก schema `web` เลย** (ตรวจแล้ว = ไม่มี) ·
สิทธิ์บน `public.users` เป็นระดับคอลัมน์ล้วนจึงไม่ปรากฏใน `table_privileges`

### 6.4 ข้อ 17–18 — ของเดิมต้องไม่เปลี่ยน

| # | รายการ | baseline ก่อน apply | หลัง apply | ผล |
|---|---|---|---|---|
| 17 | `advisor_api` บน `public.users` | `INSERT,SELECT,UPDATE` | **`INSERT,SELECT,UPDATE`** | ✅ เท่าเดิม |
| 17 | `advisor_api` ใน schema `web` | 13 | **13** | ✅ เท่าเดิม |
| 17 | `advisor_api` `EXECUTE` ฟังก์ชัน | true | **true** | ✅ |
| 18 | `advisor_ingest` ใน schema `web` | 7 | **7** | ✅ เท่าเดิม |
| 18 | `advisor_ingest` `EXECUTE` ฟังก์ชัน | true | **true** | ✅ |
| 18 | **`advisor_ingest` DELETE ใน `mko`** | 24 ตาราง | **24 ตาราง** | ✅ เท่าเดิม |

### 6.5 ตรวจเพิ่มนอกเหนือจากที่สั่ง

| ข้อตรวจ | ได้ | ผล |
|---|---|---|
| `advisor_web` เป็นสมาชิก role อื่น | **0** | ✅ |
| `advisor_web` `rolsuper` | **false** | ✅ |
| `advisor_web` `rolbypassrls` | **false** | ✅ |

`ALTER TABLE` และ `GRANT` ไม่ได้ทำให้คุณสมบัติของ role เปลี่ยน

---

## 7. ⚠ ค่าคาดหวังของผมผิด 3 ข้อ — ไม่ใช่ production ผิด

ข้อตรวจ 48 ข้อ **ตรงทันที 45 ข้อ** · อีก 3 ข้อค่าที่ได้ต่างจากที่ผมเขียนไว้
**ตรวจสาเหตุทีละข้อแล้วพบว่าค่าบน production ถูกต้องทั้งหมด ค่าคาดหวังของผมต่างหากที่ผิด**

### 7.1 `11_web_col_priv_types` ได้ `INSERT,SELECT,UPDATE` แทนที่จะเป็น `SELECT`

**สาเหตุ: query ของผมไม่ได้กรองตาราง**

`information_schema.column_privileges` **กระจายสิทธิ์ระดับตารางออกมาเป็นรายคอลัมน์ด้วย**
→ `INSERT`/`UPDATE` ระดับตารางบน `web.news` ฯลฯ จึงโผล่มาเป็นสิทธิ์ระดับคอลัมน์
ของทุกคอลัมน์ในตารางนั้น

ตรวจซ้ำแบบกรองตาราง

| ข้อตรวจ | ค่า |
|---|---|
| ชนิดสิทธิ์ระดับคอลัมน์บน **`public.users`** | **`SELECT`** เท่านั้น |
| จำนวนรายการบน `public.users` | **3** |
| ตารางอื่นที่มีสิทธิ์ระดับคอลัมน์ | `web.ai_settings, web.external_news, web.knowledge_articles, web.news, web.site_courses` — **มาจากสิทธิ์ระดับตารางที่ 006 ให้ ไม่ใช่ column-level grant** |

**ผลสรุป: ถูกต้อง** — `advisor_web` อ่านได้อย่างเดียวบน `public.users`

### 7.2 `14_web_total_rows` ได้ **12** แทนที่จะเป็น 13

**สาเหตุ: ผมเดาเลขมาจาก `advisor_api` โดยไม่ได้บวกเอง**

| role | รายละเอียด | รวม |
|---|---|---|
| `advisor_api` | SELECT 5 ตาราง + INSERT 4 + UPDATE 4 | **13** |
| **`advisor_web`** | SELECT 5 + **INSERT 3** + UPDATE 4 | **12** |

ส่วนต่าง 1 รายการพอดีคือ **`INSERT` บน `web.ai_settings` ที่ `advisor_api` มีแต่
`advisor_web` ตั้งใจไม่ให้** (เป็นตารางค่าตั้งแถวเดียว การเพิ่มแถวคือการสร้าง
ชุดค่าตั้งคู่ขนาน)

เทียบรายตารางจาก production

```
advisor_web  ai_settings:SELECT,UPDATE          | external_news:SELECT | knowledge_articles:INSERT,SELECT,UPDATE | news:INSERT,SELECT,UPDATE | site_courses:INSERT,SELECT,UPDATE
advisor_api  ai_settings:INSERT,SELECT,UPDATE   | external_news:SELECT | knowledge_articles:INSERT,SELECT,UPDATE | news:INSERT,SELECT,UPDATE | site_courses:INSERT,SELECT,UPDATE
```

**ผลสรุป: 12 คือค่าที่ถูก** และส่วนต่างที่หายไปคือสิ่งที่การออกแบบตั้งใจตัดออกพอดี

### 7.3 `07_index_predicate` ได้ `(supabase_user_id IS NOT NULL)` มีวงเล็บเพิ่ม

**สาเหตุ: PostgreSQL ใส่วงเล็บเองตอนแสดงผล `pg_get_expr`**

```
CREATE UNIQUE INDEX uq_users_supabase_user_id ON public.users
    USING btree (supabase_user_id) WHERE (supabase_user_id IS NOT NULL)
```

เหมือนกันทุกประการกับที่เขียนในไฟล์ · **ผลสรุป: ถูกต้อง** · ค่าคาดหวังของผมแค่ลืมวงเล็บ

### 7.4 บทเรียนเดิมที่กลับมาอีก

ทั้ง 7.1 และ 7.2 เป็นอาการเดียวกับที่เคยเกิดตอน post-apply ของ 005 —
**เขียนค่าคาดหวังจากการเดา แทนที่จะคำนวณจากสิ่งที่ migration ทำจริง**
ครั้งนี้จับได้เพราะข้อตรวจเทียบค่าจริงกับค่าคาดหวังแบบแสดงทั้งสองฝั่ง
ไม่ใช่แค่ขึ้นว่า "ผ่าน"

---

## 8. Row counts

| ตาราง | ก่อน apply | หลัง apply | ผล |
|---|---|---|---|
| `public.users` | **198** | **198** | ✅ ไม่เปลี่ยน |
| `public.users` ที่ `supabase_user_id` ไม่ใช่ NULL | — | **0** | ✅ ไม่มี backfill |
| `mko.schema_migrations` | 5 | **6** | ✅ เพิ่มเฉพาะแถว ledger ของ 006 |

**ข้อมูลที่ถูกเขียนลง production ในรอบนี้มีแถวเดียว คือแถว ledger**

---

## 9. Privilege comparison

| grantee | รายการ | ก่อน | หลัง | เปลี่ยนไหม |
|---|---|---|---|---|
| **`advisor_web`** | สิทธิ์ตารางใน `web` | 0 | **12** | เพิ่มตามที่ 006 ให้ |
| **`advisor_web`** | สิทธิ์ระดับคอลัมน์บน `public.users` | 0 | **3 (SELECT)** | เพิ่มตามที่ 006 ให้ |
| **`advisor_web`** | `USAGE ON SCHEMA web` | false | **true** | เพิ่มตามที่ 006 ให้ |
| **`advisor_web`** | `EXECUTE` ฟังก์ชัน | false | **true** | เพิ่มตามที่ 006 ให้ |
| **`advisor_web`** | DELETE ที่ใดก็ตาม | 0 | **0** | **ไม่เปลี่ยน** |
| `advisor_api` | `public.users` | `INSERT,SELECT,UPDATE` | **เท่าเดิม** | **ไม่เปลี่ยน** |
| `advisor_api` | schema `web` | 13 | **13** | **ไม่เปลี่ยน** |
| `advisor_ingest` | schema `web` | 7 | **7** | **ไม่เปลี่ยน** |
| `advisor_ingest` | DELETE ใน `mko` | 24 | **24** | **ไม่เปลี่ยน** |

**ไม่มี `REVOKE` เกิดขึ้นเลย** — ไฟล์ไม่มีคำสั่งนั้น และตัวเลขทุกตัวของ role เดิมเท่าเดิม

---

## 10. Ledger

```
001_mko_structured
002_mko_review_publish
003_crawl_sources
004_crawl_decisions
005_web_schema
006_web_identity_mapping     <- เพิ่มในรอบนี้
```

รวม **6 รายการ** · `006_web_identity_mapping` ปรากฏ **1 ครั้ง**

---

## 11. Unexpected findings

### 11.1 ไม่พบสิ่งผิดปกติบน production

ไม่มี privilege เกิน ไม่มี attribute ผิด ไม่มีข้อมูลเปลี่ยน ไม่มี object ที่ไม่ได้ตั้งใจสร้าง

### 11.2 สิ่งที่พบและควรบันทึก

| # | เรื่อง | ระดับ |
|---|---|---|
| 1 | **`information_schema.column_privileges` กระจายสิทธิ์ระดับตารางเป็นรายคอลัมน์** | ไม่ใช่ปัญหา แต่ทำให้ query ที่ไม่กรองตารางอ่านผิด (ข้อ 7.1) |
| 2 | `advisor_web` มี 12 สิทธิ์ใน `web` ส่วน `advisor_api` มี 13 | **ถูกต้องตามออกแบบ** — ส่วนต่างคือ `INSERT` บน `ai_settings` (ข้อ 7.2) |
| 3 | นาฬิกา OS ของเซิร์ฟเวอร์เป็น **UTC** แต่ session ของ PostgreSQL เป็น **+07** | ชื่อไฟล์ backup จึงดูเหมือนย้อนหลัง 7 ชั่วโมง · ไม่ใช่ความผิดพลาด |
| 4 | session `psql` ที่ค้างมา 15.6 วัน (พบตอน pre-apply) | **ไม่ได้ขวางการ apply** · ยังไม่ terminate ตามที่สั่ง |

---

## 12. Remaining blockers

### 12.1 ⚠ `webapi` ยังใช้งานจริงไม่ได้ — ต้องผ่านอีกสองรอบ

| # | สิ่งที่ยังขาด | จำเป็นสำหรับ |
|---|---|---|
| 1 | **`ADVISOR_WEB_PASSWORD` ยังไม่อยู่ใน production `.env`** | M3 — `webapi` ต่อฐานข้อมูล |
| 2 | **ค่า `supabase_user_id` ยังไม่มีของผู้ใช้คนใด (0 จาก 198)** | การแปลงตัวตน Supabase → `public.users` |

ทั้งสองเป็นรอบแยกที่ต้องขออนุมัติ · **006 ตั้งใจไม่ทำทั้งคู่**

### 12.2 เรื่องที่ค้างจากรอบก่อน ๆ

| # | เรื่อง | สถานะ |
|---|---|---|
| 1 | **`advisor_web` พึ่ง `CONNECT` และ `USAGE ON SCHEMA public` ที่ได้จาก `PUBLIC`** | Owner ตัดสินใจแล้วว่า **ไม่ใส่ใน 006** · ยังเป็นความเสี่ยงที่เปิดอยู่ถ้ามีการ `REVOKE … FROM PUBLIC` ภายหลัง |
| 2 | compose ทั้ง 3 ไฟล์ยังไม่ส่ง `ADVISOR_WEB_PASSWORD` | กระทบ dev/e2e ไม่กระทบ production |
| 3 | `G3_API_ENFORCEMENT_PENDING_B1` | ต้องทำพร้อม endpoint |
| 4 | **ยังไม่ commit อะไรเลย** | `db/20-roles.sh` (`+46 −0`) · ไฟล์ของ 006 ทั้งหมดยัง untracked |

### 12.3 ยังไม่ได้ทดสอบเชิงพฤติกรรมบน production

ตามที่สั่ง รอบนี้ใช้ **catalog query อย่างเดียว** ยังไม่ได้ยิง `SELECT email` หรือ
`UPDATE … WHERE false` ในฐานะ `advisor_web` บน production

การทดสอบแบบนั้นพิสูจน์แล้วในคอนเทนเนอร์ทดสอบ (99 ข้อผ่านครบ) แต่**ยังไม่ได้ยืนยัน
บนเครื่องจริง** · ถ้าต้องการ ต้องขออนุมัติแยกเพราะต้องเปิด transaction บน production
แม้จะปิดท้ายด้วย `ROLLBACK`

---

## 13. Final classification

# `MIGRATION_006_APPLIED_VERIFIED`

| เกณฑ์ | ผล |
|---|---|
| backup สำเร็จและ validate ผ่านครบ 4 ข้อ | ✅ |
| SHA-256 ตรงกับที่อนุมัติ ตรวจซ้ำก่อน apply | ✅ |
| final safety check ผ่านครบ 6 ข้อ | ✅ |
| apply สำเร็จ `COMMIT` · exit 0 · ไม่มี ERROR/ROLLBACK/lock timeout | ✅ |
| post-apply verification 18 หัวข้อที่สั่ง | ✅ **ผ่านครบ** |
| ข้อมูลไม่เปลี่ยน (198 แถวเท่าเดิม · ไม่มี backfill) | ✅ |
| สิทธิ์ของ `advisor_api` / `advisor_ingest` ไม่เปลี่ยนแม้ตัวเลขเดียว | ✅ |
| ไม่มีการแก้ไฟล์ migration · ไม่มีคำสั่งนอก artifact | ✅ |

**3 ข้อที่ค่าไม่ตรงตอนแรกเป็นค่าคาดหวังของผมที่ผิด ตรวจสาเหตุครบแล้วทั้งสามข้อ**
(ข้อ 7) ไม่ใช่ `POSTVERIFY_FAILED`

---

## บันทึกการเข้าถึงข้อมูลในรอบนี้

| ระบบ | การเข้าถึง |
|---|---|
| production PostgreSQL | `pg_dump` (อ่าน) · **apply artifact 006 หนึ่งครั้ง** · `SELECT` สำหรับ safety check และ post-apply verification |
| คำสั่งเขียนที่รัน | **เฉพาะที่อยู่ในไฟล์ 006 เท่านั้น** — `ALTER TABLE` 1 · `COMMENT` 1 · `CREATE INDEX` 1 · `DO` 1 · `GRANT` 8 · `INSERT` ledger 1 |
| คำสั่งเขียนนอก artifact | **ไม่มีแม้คำสั่งเดียว** |
| session | อ่าน `pg_stat_activity` · **ไม่ terminate ใคร** |
| ไฟล์ในรีโป | **ไม่แก้ไฟล์ migration** · สร้างเอกสารนี้ไฟล์เดียว |
| Supabase | **ไม่ได้เข้าถึงเลย** |
| git | ไม่ commit ไม่ push |

---

## STOP

# `MIGRATION_006_APPLIED_VERIFIED`

```
Migration 006       apply สำเร็จ · COMMIT · exit 0
public.users        198 แถวเท่าเดิม · supabase_user_id เป็น NULL ทั้งหมด
advisor_web         อ่าน public.users ได้ 3 คอลัมน์ · ไม่มี SELECT ระดับตาราง
                    สิทธิ์ใน web ตรง matrix ทุกช่อง · ไม่มี DELETE ที่ใดเลย
advisor_api         ไม่เปลี่ยนแม้ตัวเลขเดียว
advisor_ingest      ไม่เปลี่ยนแม้ตัวเลขเดียว
backup              /home/ubuntu/backup-before-006-20261003-102047.dump  (51.4 MiB)
```

**ไม่เริ่มขั้นถัดไปเอง — รอ Owner อนุมัติ**

เรื่องที่รอการตัดสินใจ

1. **อนุมัติ commit** — ตอนนี้ยังไม่ commit อะไรเลย ทั้ง `db/20-roles.sh` (`+46 −0`)
   และไฟล์ของ 006 ทั้ง 4 ไฟล์
2. **รอบแยก**: เพิ่ม `ADVISOR_WEB_PASSWORD` ลง production `.env` (จำเป็นสำหรับ M3)
3. **รอบแยก**: data migration เติม `supabase_user_id` ให้ S1
4. ต้องการให้ทดสอบเชิงพฤติกรรมบน production ด้วยไหม (ข้อ 12.3) — ต้องเปิด
   transaction ที่ปิดท้ายด้วย `ROLLBACK`
