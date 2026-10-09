# Migration 006 — Identity Mapping & advisor_web Privileges · Review

| | |
|---|---|
| วันที่ | 2026-10-03 |
| **Classification** | **`MIGRATION_006_READY_FOR_PREAPPLY`** |
| ไฟล์ migration | `db/migrations/006_web_identity_mapping.sql` · 148 บรรทัด · LF |
| sha256 | `fb22346bf651312a9025c0553fcb8f2637751633cfd1ae2b6f302e4bdc203376` |
| ชุดทดสอบใหม่ | `eval/web_identity_mapping_check.py` · 525 บรรทัด · **99 ข้อ ผ่านครบ** |
| ชุดทดสอบเดิม (005) | **103 ผ่าน · 0 ไม่ผ่าน · 2 ค้าง** — ไม่ถดถอย |
| Mutation test | **3 รูปแบบ · จับได้ทั้งหมด** (ข้อ 9.3) |
| Production | **ยังไม่ apply** — `supabase_user_id` ไม่มีอยู่จริง ledger ยังเป็น 001–005 |

```
Apply บน Production   NONE     ALTER public.users บน production   NONE
GRANT บน production   NONE     เติม S1 supabase_user_id           NONE
Data Migration        NONE     แก้ production .env                NONE
แก้ webapi            NONE     แก้ frontend                       NONE
Supabase Write        NONE     Deploy / Restart                   NONE
Commit / Push / Merge NONE     แก้ migration 005                  NONE
```

---

## 1. Purpose

migration นี้ทำสองเรื่องที่แยกจากกันไม่ได้

| # | เรื่อง | ทำไมต้องอยู่ไฟล์เดียวกัน |
|---|---|---|
| 1 | เพิ่ม `public.users.supabase_user_id` | เป็นที่เก็บเส้นเชื่อมระหว่างตัวตน Supabase กับผู้ใช้ของฐานข้อมูลนี้ |
| 2 | ให้สิทธิ์ `advisor_web` | `webapi` ต้อง**อ่าน**คอลัมน์นั้นเพื่อแปลงตัวตน — สิทธิ์จะอ้างถึงคอลัมน์ที่ยังไม่มีไม่ได้ |

ถ้าแยกสองไฟล์ จะมีช่วงที่ ledger บอกว่า "ให้สิทธิ์แล้ว" แต่คอลัมน์ยังไม่มี
หรือกลับกัน ซึ่งเป็นสถานะกลางที่ไม่มีประโยชน์และตรวจยาก

### 1.1 ปัญหาที่แก้

ระบบมีตัวตนผู้ใช้สองชุดที่**ไม่มีเส้นเชื่อมกันเลย** (ยืนยันแล้วใน
`docs/B1_SUPABASE_IDENTITY_VERIFICATION.md`)

```
Supabase Auth              PostgreSQL ของระบบนี้
auth.users.id (UUID)  ???  public.users.id (UUID)
user_profiles.role         public.users.is_admin
```

UUID ของสองฝั่งเป็นคนละชุด สุ่มมาคนละที่ ไม่มีอะไรบอกว่าแถวไหนคือคนเดียวกัน
`webapi` ที่ยืนยันตัวตนด้วย Supabase JWT จึงเขียน `created_by` / `updated_by`
ของตารางใน schema `web` ไม่ได้ เพราะคอลัมน์เหล่านั้นเป็น FK ไป `public.users(id)`

คอลัมน์ `supabase_user_id` คือเส้นเชื่อมที่หายไปนั้น

### 1.2 สิ่งที่ migration นี้ **ไม่** ทำ

| ไม่ทำ | เพราะ |
|---|---|
| ไม่เติมค่า `supabase_user_id` ให้ใครเลย | เป็น data migration ที่ต้องขออนุมัติแยก · ไฟล์นี้สร้างที่ว่างอย่างเดียว |
| ไม่สร้าง `advisor_web` | การสร้าง role ต้องมีรหัสผ่าน ซึ่งต้องไม่อยู่ในไฟล์ที่ commit |
| ไม่ `REVOKE` อะไรจาก `advisor_api` / `advisor_ingest` | ของเดิมต้องไม่ถดถอย |
| ไม่แตะ migration 005 | ตามที่สั่ง |

---

## 2. Exact schema change

### 2.1 คำสั่งที่เปลี่ยนโครงสร้าง — มีแค่สองคำสั่ง

```sql
ALTER TABLE public.users
    ADD COLUMN IF NOT EXISTS supabase_user_id UUID;

CREATE UNIQUE INDEX IF NOT EXISTS uq_users_supabase_user_id
    ON public.users (supabase_user_id) WHERE supabase_user_id IS NOT NULL;
```

พร้อม `COMMENT ON COLUMN` อีกหนึ่งคำสั่งที่อธิบายความหมายของ NULL

### 2.2 คุณสมบัติของคอลัมน์ — ตรงตามข้อห้ามทุกข้อ

| ข้อกำหนด | ผลที่วัดได้ | ผล |
|---|---|---|
| ชนิดเป็น `UUID` | `uuid` | ✅ |
| **เป็น NULL ได้** | `is_nullable = YES` | ✅ |
| **ไม่มี DEFAULT** | `column_default IS NULL` | ✅ |
| **ไม่มี NOT NULL** | — | ✅ |
| **ไม่มี FK ไป Supabase** | ไม่มี `REFERENCES` ในไฟล์เลย | ✅ |
| **ไม่เติมค่าใน migration** | ไม่มี `UPDATE public.users` | ✅ |

### 2.3 ทำไมไม่มี FOREIGN KEY

`auth.users` ของ Supabase อยู่**คนละฐานข้อมูลคนละเครื่อง** PostgreSQL บังคับ
ความถูกต้องข้ามฐานข้อมูลไม่ได้ · การประกาศ FK ที่บังคับใช้ไม่ได้จะสร้างความมั่นใจปลอม

ความถูกต้องของค่านี้เป็นหน้าที่ของขั้นตอน mapping ที่ต้องขออนุมัติแยก

### 2.4 ทำไมอยู่ใน `public.users` ไม่ใช่ตารางใหม่

ความสัมพันธ์เป็นหนึ่งต่อหนึ่ง และเป็นคุณสมบัติของผู้ใช้คนนั้นเอง
ตารางแยก (`web.user_identity_map`) เคยถูกพิจารณาใน
`docs/B1_ACTIVE_USER_MAPPING_DESIGN.md` แล้วตัดทิ้ง เพราะจะเพิ่ม JOIN ให้ทุก query
ที่ต้องแปลงตัวตนโดยไม่ได้อะไรกลับมา และเปิดโอกาสให้เกิดแถวกำพร้า

---

## 3. Index design

```sql
CREATE UNIQUE INDEX IF NOT EXISTS uq_users_supabase_user_id
    ON public.users (supabase_user_id) WHERE supabase_user_id IS NOT NULL;
```

### 3.1 ทำไมเป็น partial ไม่ใช่ `UNIQUE` ธรรมดา

`UNIQUE` ธรรมดาใน PostgreSQL ยอมให้มีหลาย NULL อยู่แล้ว **ผลลัพธ์เชิงพฤติกรรม
จึงเหมือนกัน** แต่ partial index ดีกว่าด้วยสองเหตุผล

| เหตุผล | รายละเอียด |
|---|---|
| **เขียนเจตนาออกมาตรง ๆ** | อ่านแล้วรู้ทันทีว่า "ข้อห้ามซ้ำบังคับเฉพาะค่าที่ไม่ใช่ NULL" ไม่ต้องรู้พฤติกรรม NULL ของ PostgreSQL ก่อน |
| **ไม่เก็บแถว NULL ไว้ใน index** | วันนี้ผู้ใช้ production ทั้ง **198 คนเป็น NULL ทั้งหมด** · `UNIQUE` ธรรมดาจะเก็บทั้ง 198 รายการไว้โดยไม่มีประโยชน์ |

รูปแบบเดียวกับ `uq_site_courses_course` และ `uq_external_news_slug` ใน 005
ซึ่งใช้ `WHERE … IS NOT NULL` เหมือนกัน — ตั้งชื่อตามแบบ `uq_<ตาราง>_<คอลัมน์>` ของโปรเจกต์

### 3.2 พิสูจน์แล้วว่าทำงานจริง

| ข้อตรวจ | ผล |
|---|---|
| `indisunique` | ✅ true |
| `indpred IS NOT NULL` (เป็น partial จริง) | ✅ true |
| เงื่อนไขคือ `supabase_user_id IS NOT NULL` | ✅ |
| อยู่บนคอลัมน์เดียว | ✅ |
| **ยัดค่าซ้ำที่ไม่ใช่ NULL → ถูกปฏิเสธ** | ✅ `sqlstate 23505` |
| **ยัด NULL หลายแถว → ใส่ได้** | ✅ |

---

## 4. advisor_web privilege matrix

### 4.1 ตารางสิทธิ์ทั้งหมดที่ 006 ให้

| วัตถุ | SELECT | INSERT | UPDATE | DELETE |
|---|---|---|---|---|
| `public.users` | **เฉพาะ 3 คอลัมน์** | ✗ | ✗ | ✗ |
| `web.site_courses` | ✓ | ✓ | ✓ | ✗ |
| `web.news` | ✓ | ✓ | ✓ | ✗ |
| `web.knowledge_articles` | ✓ | ✓ | ✓ | ✗ |
| `web.ai_settings` | ✓ | ✗ | ✓ | ✗ |
| `web.external_news` | ✓ | ✗ | ✗ | ✗ |

เพิ่มเติม: `USAGE ON SCHEMA web` · `EXECUTE ON FUNCTION web.touch_updated_at()`

**ไม่มี DELETE แม้ที่เดียว** — หลักเดียวกับ 002, 004 และ 005

### 4.2 สิ่งที่ `advisor_web` **ไม่ได้** และต้องไม่ได้

```
public.courses · course_documents · course_chunks   ไม่มีสิทธิ์
public.chat_* · recommendations · user_requirements  ไม่มีสิทธิ์
schema mko ทั้งหมด                                   ไม่มีสิทธิ์
public.users ระดับตาราง                              ไม่มีสิทธิ์  (มีเฉพาะระดับคอลัมน์)
DELETE ทุกที่ทั้งฐาน                                  ไม่มีสิทธิ์
```

migration ไม่มีคำสั่ง `GRANT` ไปยังวัตถุเหล่านี้เลย — ตรวจได้จากตัวไฟล์ 148 บรรทัด

---

## 5. Column-level SELECT behavior

### 5.1 สามคอลัมน์ที่ให้ และเหตุผลของแต่ละตัว

```sql
GRANT SELECT (id, is_active, supabase_user_id) ON public.users TO advisor_web;
```

| คอลัมน์ | `webapi` ใช้ทำอะไร |
|---|---|
| `id` | เขียนลง `created_by` / `updated_by` ของตารางใน `web` |
| `is_active` | ปฏิเสธผู้ใช้ที่ถูกปิดบัญชี |
| `supabase_user_id` | แปลงผู้ใช้ Supabase เป็นผู้ใช้ของฐานข้อมูลนี้ |

**ไม่มีคอลัมน์ที่สี่ที่ endpoint ใดต้องใช้** — `full_name` ไม่จำเป็นเพราะชื่อที่แสดง
บนหน้าเว็บมาจาก Supabase · `is_admin` ไม่จำเป็นเพราะสิทธิ์ของหน้าเว็บตัดสินจาก
`user_profiles.role` ฝั่ง Supabase ตามที่ออกแบบไว้ใน `B1_AUTHORIZATION_PHASE1_IMPLEMENTATION.md`

### 5.2 `SELECT *` ถูกปฏิเสธ — เป็นผลพลอยได้ที่ตั้งใจ

สิทธิ์ระดับคอลัมน์ทำให้ `SELECT *` ถูกปฏิเสธด้วย เพราะ `*` ขยายเป็นทุกคอลัมน์
รวมคอลัมน์ที่ไม่ได้ให้

**นี่คือสิ่งที่ต้องการ** — โค้ดที่เผลอเขียน `SELECT *` จะพังตั้งแต่ทดสอบ
ไม่ใช่หลุด `email` กับ `password_hash` ออกไปเงียบ ๆ

### 5.3 พิสูจน์เชิงพฤติกรรม ไม่ใช่แค่อ่าน catalog

ชุดทดสอบ **สวมบทเป็น `advisor_web` ด้วย `SET ROLE`** แล้วยิง SQL จริง

| คำสั่งที่ยิงจริง | ผล |
|---|---|
| `SELECT id, is_active, supabase_user_id FROM public.users` | ✅ **ทำได้** ได้แถวกลับมา |
| `SELECT email FROM public.users` | ✅ **ถูกปฏิเสธ** `42501` |
| `SELECT password_hash FROM public.users` | ✅ **ถูกปฏิเสธ** `42501` |
| `SELECT full_name FROM public.users` | ✅ **ถูกปฏิเสธ** `42501` |
| `SELECT is_admin FROM public.users` | ✅ **ถูกปฏิเสธ** `42501` |
| `SELECT * FROM public.users` | ✅ **ถูกปฏิเสธ** `42501` |
| `UPDATE public.users …` | ✅ **ถูกปฏิเสธ** `42501` |
| `INSERT INTO public.users …` | ✅ **ถูกปฏิเสธ** `42501` |
| `DELETE FROM public.users …` | ✅ **ถูกปฏิเสธ** `42501` |

### 5.4 ⚠ เรื่อง `has_table_privilege` ที่ต้องเข้าใจให้ถูก

| ฟังก์ชัน | ตอบอะไร | ค่าสำหรับ `advisor_web` บน `public.users` |
|---|---|---|
| `has_table_privilege` | สิทธิ์**ระดับตาราง**เท่านั้น | **`false`** ← ตรงตามที่สั่งว่าต้องไม่มี |
| `has_column_privilege` | สิทธิ์ของคอลัมน์ที่ระบุ | `true` สำหรับ 3 คอลัมน์ · `false` สำหรับที่เหลือ |
| `has_any_column_privilege` | ตารางหรือคอลัมน์ใดก็ได้ | `true` — **ไม่ใช่ตัวที่ควรใช้ตรวจข้อนี้** |

ข้อตรวจใช้ `has_table_privilege` สำหรับข้อ "ต้องไม่มี SELECT ระดับตาราง"
และใช้ `has_column_privilege` รายคอลัมน์สำหรับข้อที่เหลือ **พร้อมยิง SQL จริงกำกับทุกข้อ**

---

## 6. web schema grants

```sql
GRANT USAGE ON SCHEMA web TO advisor_web;

GRANT SELECT, INSERT, UPDATE ON web.site_courses        TO advisor_web;
GRANT SELECT, INSERT, UPDATE ON web.news                TO advisor_web;
GRANT SELECT, INSERT, UPDATE ON web.knowledge_articles  TO advisor_web;
GRANT SELECT,         UPDATE ON web.ai_settings         TO advisor_web;
GRANT SELECT                 ON web.external_news       TO advisor_web;

GRANT EXECUTE ON FUNCTION web.touch_updated_at() TO advisor_web;
```

### 6.1 เหตุผลรายตาราง

| ตาราง | สิทธิ์ | เหตุผล |
|---|---|---|
| `site_courses` · `news` · `knowledge_articles` | อ่าน เพิ่ม แก้ | เป็นเนื้อหาที่หน้าผู้ดูแลสร้างและแก้ไขจริง |
| `ai_settings` | อ่าน แก้ · **ไม่ให้เพิ่ม** | เป็นตารางค่าตั้งแถวเดียว · การเพิ่มแถวใหม่คือการสร้างชุดค่าตั้งคู่ขนาน ซึ่งไม่ควรเกิดจากโค้ด |
| `external_news` | **อ่านอย่างเดียว** | เป็นข้อมูลที่ตัวดึงข่าวภายนอก (`advisor_ingest`) เป็นคนเขียน ไม่ใช่บริการหน้าเว็บ |

### 6.2 ทำไมต้องให้ `EXECUTE` บน trigger function

trigger `touch_updated_at` ทำงานด้วยสิทธิ์ของ**ผู้เรียก** ไม่ใช่ของเจ้าของฟังก์ชัน
ถ้าไม่ให้ `EXECUTE` ทุก `UPDATE` ของ `advisor_web` จะถูกปฏิเสธที่ตัว trigger
ทั้งที่มีสิทธิ์ UPDATE บนตารางแล้ว

**พิสูจน์แล้วเชิงพฤติกรรม** — สวมบทเป็น `advisor_web` สั่ง `UPDATE web.news`
แล้วตรวจว่า `updated_at` ถูกเลื่อนมาเป็นเวลาปัจจุบันจริง

### 6.3 ไม่มี DELETE — และข้อตรวจก็ยืนยันเชิงพฤติกรรม

ยิง `DELETE FROM web.<ตาราง> WHERE false` ทั้ง 5 ตารางในฐานะ `advisor_web`
**ถูกปฏิเสธด้วย `42501` ทั้งหมด**

การซ่อนเนื้อหาจากหน้าเว็บทำได้ด้วย `is_published` / `status` อยู่แล้ว ไม่ต้องลบ

---

## 7. Security rationale

### 7.1 สิ่งที่ป้องกันได้จริงถ้าโค้ด `webapi` มีบั๊ก

| สถานการณ์ | ถ้าให้ SELECT ระดับตาราง | ที่ 006 ทำจริง |
|---|---|---|
| เขียน `SELECT * FROM users` แล้ว log ทั้งแถว | **email + password hash ทั้ง 198 คนหลุดลง log** | คำสั่งถูกปฏิเสธตั้งแต่ฐานข้อมูล |
| endpoint คืน object ผู้ใช้ทั้งก้อนให้ frontend | **email หลุดออกทาง API** | อ่าน email ไม่ได้ตั้งแต่แรก |
| SQL injection ที่อ่านตารางได้ | อ่าน `password_hash` ได้ทั้งตาราง | อ่านได้แค่ 3 คอลัมน์ที่ไม่มีความลับ |
| โค้ดเผลอ `UPDATE users SET is_admin=true` | **ยกระดับสิทธิ์ได้** | ไม่มีสิทธิ์ UPDATE เลย |

### 7.2 ทำไมไม่ใช้ RLS แทน

RLS กรองเป็น**แถว** ไม่ใช่**คอลัมน์** · ปัญหาที่นี่คือ "อ่านคอลัมน์ไหนได้"
ไม่ใช่ "อ่านแถวไหนได้" · column-level GRANT ตรงกับปัญหามากกว่า
และไม่ต้องเปิด RLS บนตารางที่ `advisor_api` ใช้งานอยู่ ซึ่งจะกระทบของเดิม

### 7.3 ⚠ สิ่งที่ 006 **ไม่** ครอบคลุม — ต้องรู้ไว้

| ช่องว่าง | สถานะ |
|---|---|
| `advisor_web` พึ่ง `CONNECT` บน database และ `USAGE ON SCHEMA public` ที่ได้จาก `PUBLIC` | **006 ไม่ได้ให้สองอย่างนี้โดยตรง** — ถ้าวันหนึ่งมีใคร `REVOKE … FROM PUBLIC` จะพังโดยที่ ledger ยังบอกว่า 006 ลงแล้ว · ดูข้อ 14 |
| ค่า `supabase_user_id` ยังไม่มีของใครเลย | `webapi` จะแปลงตัวตนไม่ได้จนกว่าจะทำ data migration · เป็นรอบแยก |
| การบังคับ `created_by` ไม่ให้แก้ย้อนหลัง | ยังเป็น `G3_API_ENFORCEMENT_PENDING_B1` ใน `web_schema_check.py` — ต้องทำพร้อม endpoint |

---

## 8. Migration transaction / fail behavior

### 8.1 อยู่ใน transaction เดียวทั้งไฟล์

```
BEGIN;        บรรทัด 69
...
COMMIT;       บรรทัด 148
```

PostgreSQL ทำ DDL แบบ transactional → **ถ้าล้มที่ไหนก็ตาม ทุกอย่างถอนกลับหมด**

### 8.2 ⚠ หยุดเสียงดังถ้าไม่มี `advisor_web` — ต่างจาก 002–005 โดยเจตนา

```sql
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'advisor_web') THEN
        RAISE EXCEPTION 'ไม่พบ role advisor_web — migration 006 ให้สิทธิ์ใครไม่ได้'
            USING HINT = 'สร้าง role ก่อนด้วยขั้นตอนใน docs/B1_ADVISOR_WEB_PROVISION_RESULT.md ข้อ 10.1 …',
                  ERRCODE = 'undefined_object';
    END IF;
END;
$$;
```

| | 002–005 | **006** |
|---|---|---|
| ถ้าไม่มี role | `IF EXISTS … THEN GRANT` → **ข้ามเงียบ ๆ** | **`RAISE EXCEPTION` → ถอนกลับทั้งหมด** |
| เพราะ | สิทธิ์เป็นของแถม ไม่มีก็ไม่พัง | **สิทธิ์คือเหตุผลครึ่งหนึ่งที่ migration นี้มีอยู่** |

ถ้าข้ามเงียบ ๆ จะได้ฐานข้อมูลที่ ledger บอกว่า "006 ลงแล้ว" แต่ `webapi` ต่อไม่ได้
และไม่มีใครรู้จนกว่าจะ deploy แล้วพัง

### 8.3 พิสูจน์แล้วทั้งสองเส้นทาง

**เส้นทางล้มเหลว** — apply ทั้งที่ยังไม่มี `advisor_web`

```
BEGIN
ALTER TABLE
COMMENT
CREATE INDEX
ERROR:  ไม่พบ role advisor_web — migration 006 ให้สิทธิ์ใครไม่ได้
HINT:   สร้าง role ก่อนด้วยขั้นตอนใน docs/B1_ADVISOR_WEB_PROVISION_RESULT.md ข้อ 10.1 …
exit=3
```

ตรวจหลังจากนั้น — **ไม่มีอะไรหลงเหลือเลย**

| | ค่า |
|---|---|
| คอลัมน์ `supabase_user_id` | **0** (ไม่ถูกเพิ่ม) |
| index `uq_users_supabase_user_id` | **0** |
| ledger `006_web_identity_mapping` | **0** |

สังเกตว่า `ALTER TABLE` และ `CREATE INDEX` **สำเร็จไปแล้ว** ก่อนจะถึงด่านตรวจ
แต่ถูกถอนกลับทั้งหมดเพราะอยู่ใน transaction เดียวกัน — นี่คือสิ่งที่ต้องการ

**เส้นทางสำเร็จ** — apply เมื่อมี role

```
BEGIN · ALTER TABLE · COMMENT · CREATE INDEX · DO · GRANT ×8 · INSERT 0 1 · COMMIT
exit=0
```

### 8.4 รันซ้ำได้

| คำสั่ง | กลไก |
|---|---|
| `ALTER TABLE … ADD COLUMN` | `IF NOT EXISTS` |
| `CREATE UNIQUE INDEX` | `IF NOT EXISTS` |
| `GRANT` ทั้ง 8 รายการ | PostgreSQL ถือว่าการ GRANT ซ้ำเป็น no-op ไม่ error |
| `INSERT` ลง ledger | `ON CONFLICT (version) DO NOTHING` |

ทดสอบแล้ว — apply ซ้ำได้ `exit=0` และ ledger ยังมีแถวเดียว

**การรันซ้ำได้ไม่ขัดกับ "fail loudly"** — ด่านตรวจ role ยังทำงานทุกครั้ง
สิ่งที่ข้ามแบบไม่ error คือสิ่งที่**ทำสำเร็จไปแล้ว** ไม่ใช่สิ่งที่**ทำไม่ได้**

---

## 9. Test results

### 9.1 สภาพแวดล้อมทดสอบ — แยกจาก production สนิท

คอนเทนเนอร์ทิ้ง `pgvector/pgvector:pg16` → **PostgreSQL 16.15 เวอร์ชันเดียวกับ production**
ฐานข้อมูลชื่อ `web_test` (ชุดทดสอบปฏิเสธการรันถ้าชื่อฐานไม่อยู่ในรายการที่อนุญาต
หรือ URL มีคำว่า `course_advisor`)

ลำดับการตั้งฐาน — เหมือน production ทุกขั้น

```
1. db/schema.sql
2. CREATE ROLE advisor_api / advisor_ingest  (+ GRANT บน public.users ตาม 20-roles.sh)
3. migration 001 → 002 → 003 → 004 → 005
4. CREATE ROLE advisor_web  (รหัสผ่านทิ้ง)
5. migration 006
```

ก่อน apply 006 ยืนยันสถานะตั้งต้น: คอลัมน์ `supabase_user_id` = 0 ·
สิทธิ์ของ `advisor_web` = 0 · `advisor_api` บน `users` = `INSERT,SELECT,UPDATE` ·
ledger = 001–005

### 9.2 ผลชุดทดสอบใหม่ — **99 ข้อ ผ่านครบ**

```
PYTHONIOENCODING=utf-8 python eval/web_identity_mapping_check.py \
    --database-url postgresql://postgres@127.0.0.1:55406/web_test
```

| กลุ่ม | จำนวน | ผล |
|---|---|---|
| คอลัมน์ `supabase_user_id` (ชนิด · nullable · ไม่มี default) | 4 | ✅ |
| partial unique index | 5 | ✅ |
| ข้อห้ามซ้ำ — ยัดข้อมูลจริง | 3 | ✅ |
| สิทธิ์บน `public.users` (catalog 8 + ของจริง 9) | 17 | ✅ |
| สิทธิ์บน schema `web` (catalog 21 + ของจริง 20) | 41 | ✅ |
| `EXECUTE` บน trigger function | 3 | ✅ |
| สิทธิ์เดิมของ `advisor_api` / `advisor_ingest` | 10 | ✅ |
| ตรวจตัวไฟล์ migration เอง | 16 | ✅ |
| **รวม** | **99** | **ผ่านครบ · exit 0** |

ครอบคลุมข้อที่สั่งมาทั้ง 20 ข้อ

| ข้อที่สั่ง | อยู่ในกลุ่ม |
|---|---|
| 1–3 ชนิด UUID · nullable · ไม่มี default | คอลัมน์ |
| 4 partial unique index | partial index |
| 5–6 ซ้ำถูกปฏิเสธ · NULL หลายแถวได้ | ข้อห้ามซ้ำ |
| 7–10 column-level SELECT · email · `SELECT *` · UPDATE | `public.users` |
| 11–16 สิทธิ์ 5 ตาราง + DELETE ถูกปฏิเสธทุกตาราง | schema `web` |
| 17 function EXECUTE | trigger function |
| 18 `advisor_api` ไม่ถดถอย | สิทธิ์เดิม |
| 19–20 ไม่มี secret · ไม่มี data backfill | ตัวไฟล์ |

### 9.3 ⚠ Mutation test — พิสูจน์ว่าข้อตรวจ "ล้มได้จริง"

ข้อตรวจที่ไม่เคยเห็นมันล้ม คือข้อตรวจที่ยังไม่รู้ว่าตรวจอะไรอยู่

| # | จงใจทำให้ผิด | ชุดทดสอบจับได้ไหม |
|---|---|---|
| M1 | `GRANT SELECT ON public.users TO advisor_web` (ระดับตาราง) | ✅ **จับได้** — `SELECT email` · `password_hash` · `full_name` · `is_admin` · `SELECT *` กลายเป็น "คำสั่งสำเร็จ" ทั้งหมด |
| M2 | `GRANT DELETE ON web.news TO advisor_web` | ✅ **จับได้ 4 ข้อ** — catalog · เชิงพฤติกรรม · และข้อรวมอีกสองข้อ |
| M3 | เปลี่ยน partial index เป็น `UNIQUE` เต็ม | ✅ **จับได้ 2 ข้อ** — "เป็น partial" และ "เงื่อนไข IS NOT NULL" |
| — | ถอนการแก้ทั้งหมดกลับ | ✅ กลับมา **99 ผ่าน · 0 ไม่ผ่าน** |

### 9.4 ⚠ ข้อตรวจของผมเองผิดสองข้อในรอบแรก — แก้แล้ว

**ทั้งสองข้อเป็นข้อตรวจผิด ไม่ใช่ migration ผิด** บันทึกไว้ให้ครบ

| # | ข้อตรวจที่เขียนผิด | สาเหตุจริง | แก้เป็น |
|---|---|---|---|
| 1 | "ไม่มี role ใดได้ DELETE ที่ไหนเลย" → พบ 24 รายการ | **ขอบเขตผิด** · `advisor_ingest` มี DELETE บน schema `mko` มาตั้งแต่ migration 001/002 เพราะเป็น worker ที่สร้างข้อมูลสกัดใหม่ทั้งชุด — ไม่เกี่ยวกับ 006 | แยกเป็น 4 ข้อ: ไม่มี advisor role ได้ DELETE ใน `web` · `advisor_web` ไม่ได้ DELETE ที่ใดเลย · ไม่มีใครได้ DELETE บน `public.users` · **DELETE เดิมบน `mko` ยังอยู่ครบ** |
| 2 | "เขียนข้อมูลที่เดียวคือ ledger" → ได้ `['on','on','on','on','mko.schema_migrations']` | **regex ผิด** · จับคำว่า `UPDATE` ใน `GRANT SELECT, INSERT, UPDATE ON web.…` เป็นการเขียนข้อมูล แล้วได้เป้าหมายเป็นคำว่า `on` | แยกประโยคด้วย `;` · ตัดประโยคที่ขึ้นต้นด้วย `GRANT` ออก · จับเฉพาะกริยาที่ต้นประโยค |

หลังแก้ยังเหลืออีก 2 ข้อไม่ผ่าน ซึ่งเป็น**กับดักเดียวกับที่เคยทำให้ post-apply ของ 005
รายงานผิด**

> `information_schema.table_privileges` รายงานสิทธิ์โดยปริยายของ **เจ้าของตาราง** ด้วย
> เจ้าของคือ `postgres` ซึ่งมี DELETE ทุกตาราง → ข้อตรวจที่ไม่กรอง `grantee`
> จะไม่ผ่านตลอดกาลโดยที่ไม่มีใครได้สิทธิ์เพิ่มจริง

แก้โดยกรอง `grantee IN ('advisor_api','advisor_ingest','advisor_web')` และเขียน
คอมเมนต์เตือนไว้ในไฟล์ทดสอบเพื่อไม่ให้พลาดซ้ำ

### 9.5 วิธีแยก "ถูกปฏิเสธเพราะสิทธิ์" ออกจาก "ข้อมูลผิดรูป"

ข้อตรวจเชิงพฤติกรรมดู **SQLSTATE** ไม่ใช่แค่ "ล้มเหลวหรือไม่"

| SQLSTATE | ความหมาย | นับเป็น |
|---|---|---|
| `42501` `insufficient_privilege` | ถูกปฏิเสธเพราะไม่มีสิทธิ์ | **ถูกปฏิเสธจริง** |
| `23502` `not_null_violation` ฯลฯ | สิทธิ์ผ่านแล้วแต่ข้อมูลไม่ครบ | **ทำได้** |

ถ้านับแค่ "ล้มเหลว = ถูกปฏิเสธ" ข้อตรวจจะผ่านทั้งที่สิทธิ์เปิดอยู่ เพียงเพราะ
ยัดข้อมูลไม่ครบคอลัมน์

---

## 10. Regression results

### 10.1 ชุดทดสอบของ 005 — รันบนฐานเดียวกันหลัง apply 006

```
ผ่าน 103 · ไม่ผ่าน 0 · ค้าง 2
exit=0
```

2 ข้อที่ค้างเป็น `G3_API_ENFORCEMENT_PENDING_B1` ซึ่ง**ค้างมาก่อน 006 แล้ว**
(ต้องรอ endpoint จริง) ไม่ใช่การถดถอยจากรอบนี้

### 10.2 สิทธิ์เดิมไม่ถูกแตะ

| ข้อตรวจ | ผล |
|---|---|
| `advisor_api` บน `public.users` ยังเป็น `INSERT,SELECT,UPDATE` | ✅ |
| `advisor_api` ยังเขียน `web.site_courses` · `news` · `knowledge_articles` · `ai_settings` ได้ | ✅ ทั้ง 4 |
| `advisor_ingest` ยังเขียน `web.external_news` ได้ | ✅ |
| **DELETE เดิมของ `advisor_ingest` บน schema `mko` ยังอยู่ครบ** | ✅ 24 ตาราง |
| ไม่มี advisor role ใดได้ DELETE ใน schema `web` | ✅ 0 |
| ไม่มี advisor role ใดได้ DELETE บน `public.users` | ✅ 0 |

**ไฟล์ 006 ไม่มีคำว่า `REVOKE` เลย** — ตรวจด้วย regex ในชุดทดสอบ

---

## 11. Diff summary

| ไฟล์ | สถานะ | บรรทัด |
|---|---|---|
| `db/migrations/006_web_identity_mapping.sql` | **ใหม่** · untracked | 148 |
| `eval/web_identity_mapping_check.py` | **ใหม่** · untracked | 525 |

**ไม่มีไฟล์เดิมถูกแก้แม้ไฟล์เดียว** — `git status` แสดงเฉพาะสองไฟล์นี้ (นอกจาก
`db/20-roles.sh` ที่ค้างจากรอบก่อนและเอกสาร)

### 11.1 โครงของ migration

| ส่วน | บรรทัด | เนื้อหา |
|---|---|---|
| หัวไฟล์ (คำอธิบายเหตุผล) | 1–68 | ทำไมอยู่ใน `public.users` · ทำไม NULL ได้ · ทำไม partial · ทำไมไม่มี FK · **ทำไมต้องหยุดถ้าไม่มี role** |
| `BEGIN;` | 69 | |
| คอลัมน์ + comment + index | 71–81 | `ALTER TABLE` 74 · `CREATE UNIQUE INDEX` 80 |
| ด่านตรวจ role | 83–96 | `DO` block จบที่ 96 |
| `GRANT` บน `public.users` | 98–116 | column-level · ตัว `GRANT` อยู่บรรทัด 116 |
| `GRANT` บน schema `web` | 118–143 | `USAGE ON SCHEMA web` บรรทัด 133 |
| ledger + `COMMIT;` | 145–148 | |

**อัตราส่วนคำอธิบายต่อคำสั่ง ≈ 2:1** — ตามแบบเดียวกับ 001–005

### 11.2 ไฟล์สะอาด

| ข้อตรวจ | ผล |
|---|---|
| CRLF | **ไม่มี** — เป็น LF ล้วน |
| คำว่า PASSWORD / SECRET / TOKEN / API_KEY / SERVICE_ROLE ในคำสั่ง | **ไม่มี** |
| `CREATE ROLE` / `ALTER ROLE` | **ไม่มี** |
| `REVOKE` / `DROP` / `DELETE` | **ไม่มี** |
| การเขียนข้อมูล | **ที่เดียวคือ `mko.schema_migrations`** |

---

## 12. Production impact

### 12.1 สถานะ production ขณะเขียนรายงาน (READ-ONLY)

```
public.users                198 แถว
supabase_user_id            ยังไม่มี  (0)
ledger                      001, 002, 003, 004, 005
advisor_web                 มีอยู่ · ยังไม่มีสิทธิ์ใด ๆ
```

### 12.2 การล็อกตาราง — จุดที่ต้องระวังที่สุด

| คำสั่ง | ล็อกชนิด | กระทบใคร |
|---|---|---|
| `ALTER TABLE … ADD COLUMN` (nullable ไม่มี default) | **ACCESS EXCLUSIVE** | **บล็อกทุกการอ่านและเขียน `public.users` ชั่วขณะ** |
| `CREATE UNIQUE INDEX` (ไม่ใช่ CONCURRENTLY) | **SHARE** | บล็อกการเขียน `public.users` ระหว่างสร้าง |
| `GRANT` | ACCESS EXCLUSIVE บนแต่ละตาราง | สั้นมาก |

`public.users` ถูกใช้โดย `advisor_api` ในการยืนยันตัวตนของ backend →
ช่วงที่ล็อกอยู่ การเข้าสู่ระบบจะรอ

### 12.3 เวลาที่วัดได้จริง บนตาราง 198 แถว (เท่า production)

| คำสั่ง | เวลา |
|---|---|
| `ALTER TABLE … ADD COLUMN` | **1.139 ms** |
| `COMMENT ON COLUMN` | 1.456 ms |
| **`CREATE UNIQUE INDEX`** | **7.010 ms** ← นานที่สุด |
| `DO` (ด่านตรวจ role) | 2.635 ms |
| `GRANT` ×8 | รวม 1.457 ms |
| `INSERT` ledger | 0.326 ms |
| `COMMIT` | 2.425 ms |
| **รวมทั้ง migration** | **≈ 16.7 ms** |

`ADD COLUMN` แบบ nullable ไม่มี default เป็นการแก้ **metadata อย่างเดียว**
ตั้งแต่ PostgreSQL 11 ไม่ต้องเขียนทุกแถวใหม่ → เวลาไม่ขึ้นกับจำนวนแถว

### 12.4 ไม่ต้องใช้ `CONCURRENTLY`

`CREATE INDEX CONCURRENTLY` รันใน transaction ไม่ได้ ซึ่งจะทำให้เสียคุณสมบัติ
"ล้มแล้วถอนกลับทั้งหมด" ที่สำคัญกว่ามากในกรณีนี้ · ที่ 198 แถว 7 ms
การล็อกสั้นเกินกว่าจะเป็นปัญหา

### 12.5 สิ่งที่ **ไม่** กระทบ

```
RAG / chat / embedding        ไม่แตะ course_chunks, course_documents, courses
crawler                       ไม่แตะ schema mko
ข้อมูลผู้ใช้เดิม 198 แถว        ไม่มี UPDATE แม้แถวเดียว · คอลัมน์ใหม่เป็น NULL ทั้งหมด
advisor_api / advisor_ingest   ไม่มี REVOKE · สิทธิ์เท่าเดิม
Supabase                      ไม่แตะเลย
```

### 12.6 ข้อเสนอสำหรับรอบ apply (ยังไม่ทำ)

ใช้แบบเดียวกับตอน apply 005 ซึ่งผ่านมาแล้ว

```
psql -v ON_ERROR_STOP=1   และ   PGOPTIONS='-c lock_timeout=10s'
```

`lock_timeout` สำคัญเพราะ `ALTER TABLE` ต้องรอ ACCESS EXCLUSIVE — ถ้ามี transaction
ค้างอยู่ จะได้ล้มใน 10 วินาทีแทนที่จะค้างและบล็อกการเข้าสู่ระบบทั้งระบบ

---

## 13. Rollback plan

### 13.1 สคริปต์ถอนกลับ — **ทดสอบจริงแล้ว**

```sql
BEGIN;
REVOKE ALL ON web.site_courses, web.news, web.knowledge_articles,
              web.ai_settings, web.external_news FROM advisor_web;
REVOKE EXECUTE ON FUNCTION web.touch_updated_at() FROM advisor_web;
REVOKE USAGE ON SCHEMA web FROM advisor_web;
REVOKE ALL (id, is_active, supabase_user_id) ON public.users FROM advisor_web;
DROP INDEX IF EXISTS public.uq_users_supabase_user_id;
ALTER TABLE public.users DROP COLUMN IF EXISTS supabase_user_id;
DELETE FROM mko.schema_migrations WHERE version = '006_web_identity_mapping';
COMMIT;
```

ผลหลังรันในฐานทดสอบ — **กลับสู่สภาพก่อน 006 ทุกช่อง**

| | ค่า |
|---|---|
| คอลัมน์ `supabase_user_id` | 0 |
| index | 0 |
| ledger `006` | 0 |
| สิทธิ์ระดับตารางของ `advisor_web` | 0 |
| **สิทธิ์ระดับคอลัมน์ของ `advisor_web`** | **0** |
| `advisor_api` บน `public.users` | `INSERT,SELECT,UPDATE` เท่าเดิม |

### 13.2 ⚠ เงื่อนไขเวลาที่ถอนกลับได้อย่างปลอดภัย

| ช่วงเวลา | ถอนกลับได้ไหม |
|---|---|
| **ก่อนทำ data migration** (ตอนนี้) | **ได้ ไม่มีอะไรเสียหาย** — ทุกแถวเป็น NULL อยู่แล้ว |
| **หลังเติมค่า `supabase_user_id` แล้ว** | `DROP COLUMN` จะ**ลบข้อมูลการจับคู่ทั้งหมดทิ้ง** · ต้องสำรองค่าออกมาก่อน |
| **หลัง `webapi` ขึ้น production แล้ว** | `webapi` จะใช้งานไม่ได้ทันที — ต้องหยุดบริการก่อน |

### 13.3 ไม่ต้องถอน role

สคริปต์นี้**ไม่** `DROP ROLE advisor_web` เพราะ role เป็นคนละเรื่องกับ migration
และถูกสร้างแยกไปแล้ว (ดู `B1_ADVISOR_WEB_PROVISION_RESULT.md`)
หลังถอนกลับ role จะอยู่ในสภาพ "มีอยู่แต่ไม่มีสิทธิ์" เหมือนก่อน 006 พอดี

### 13.4 ไม่เก็บสคริปต์ถอนกลับไว้ในรีโป

ตามแบบของ 001–005 ที่ไม่มีไฟล์ down migration — การถอนกลับเป็นการตัดสินใจที่ต้อง
ทำด้วยมือพร้อมดูสถานะจริง ไม่ใช่สิ่งที่รันอัตโนมัติได้ · สคริปต์อยู่ในรายงานนี้
เพื่อให้มีของพร้อมใช้โดยไม่ต้องเขียนใหม่ตอนฉุกเฉิน

---

## 14. Remaining blockers

### 14.1 ไม่ขวางการ apply 006

| # | เรื่อง | สถานะ |
|---|---|---|
| 1 | ค่า `supabase_user_id` ยังไม่มีของใคร | data migration รอบแยก · 006 ตั้งใจไม่เติม |
| 2 | `ADVISOR_WEB_PASSWORD` ยังไม่อยู่ใน production `.env` | จำเป็นสำหรับ M3 (`webapi` ต่อฐาน) **ไม่จำเป็นสำหรับ 006** |
| 3 | compose ทั้ง 3 ไฟล์ยังไม่ส่ง `ADVISOR_WEB_PASSWORD` | กระทบ dev/e2e ไม่กระทบ production apply |
| 4 | `G3_API_ENFORCEMENT_PENDING_B1` | ค้างมาก่อน 006 · ต้องทำพร้อม endpoint |

### 14.2 ⚠ เรื่องที่ควรตัดสินใจก่อน `webapi` ขึ้นจริง

**`advisor_web` พึ่งสิทธิ์ที่ได้จาก `PUBLIC` สองอย่าง**

| สิทธิ์ | ที่มา | ถ้าหายไป |
|---|---|---|
| `CONNECT` บน database | `PUBLIC` (ค่าตั้งต้น) | `webapi` ต่อฐานไม่ได้เลย |
| `USAGE ON SCHEMA public` | `PUBLIC` (ค่าตั้งต้น) | อ่าน `public.users` ไม่ได้แม้มีสิทธิ์ระดับคอลัมน์ |

006 **ไม่ได้ให้สองอย่างนี้โดยตรง** ตามขอบเขตที่สั่งมา ซึ่งระบุรายการ GRANT ไว้ชัดเจน
และไม่มีสองข้อนี้

วันนี้ไม่มีปัญหาเพราะ `PUBLIC` ยังมีทั้งคู่ (ตรวจแล้วบน production) แต่ถ้าวันหนึ่ง
มีการ `REVOKE … FROM PUBLIC` เพื่อความปลอดภัย `webapi` จะพังโดยที่ ledger ยังบอกว่า
006 ลงเรียบร้อย

**ข้อเสนอ: เพิ่มสองบรรทัดนี้ใน 006 หรือใน migration ถัดไป** — ต้องการการอนุมัติ

```sql
GRANT CONNECT ON DATABASE course_advisor TO advisor_web;
GRANT USAGE ON SCHEMA public TO advisor_web;
```

ทั้งสองคำสั่ง**ไม่ให้สิทธิ์ใหม่ใด ๆ ในทางปฏิบัติ** (role มีอยู่แล้วผ่าน `PUBLIC`)
แต่ทำให้ไม่ต้องพึ่งค่าตั้งต้นที่คนอื่นเปลี่ยนได้

**ยังไม่ใส่ลงไฟล์** เพราะอยู่นอกรายการที่สั่งมา

---

## 15. Final classification

# `MIGRATION_006_READY_FOR_PREAPPLY`

### 15.1 เกณฑ์ที่ผ่านครบ

| เกณฑ์ | ผล |
|---|---|
| คอลัมน์ตรงสเปก (UUID · nullable · ไม่มี default · ไม่มี FK) | ✅ |
| partial unique index ถูกต้องและบังคับได้จริง | ✅ |
| `advisor_web` อ่าน `public.users` ได้แค่ 3 คอลัมน์ · `email` และ `SELECT *` ถูกปฏิเสธ | ✅ พิสูจน์เชิงพฤติกรรม |
| สิทธิ์ schema `web` ตรงตาราง endpoint ทุกช่อง | ✅ |
| ไม่มี DELETE ที่ใดเลยสำหรับ `advisor_web` | ✅ |
| `EXECUTE` บน trigger function และ trigger ทำงานจริง | ✅ |
| อยู่ใน transaction · ล้มแล้วถอนกลับหมด · หยุดเสียงดังถ้าไม่มี role | ✅ ทดสอบทั้งสองเส้นทาง |
| รันซ้ำได้ | ✅ |
| ไม่มี secret · ไม่มี data backfill · ไม่มี `REVOKE` | ✅ |
| ของเดิมไม่ถดถอย (005: 103 ผ่าน · `advisor_api` เท่าเดิม) | ✅ |
| ชุดทดสอบล้มได้จริง | ✅ mutation 3 รูปแบบ จับได้ทั้งหมด |
| ทดสอบแบบ isolated ครบลำดับ 005 → provision → 006 | ✅ |

### 15.2 ทำไมไม่ใช่ `READY_FOR_APPLY`

ยังไม่ผ่าน **pre-apply gate บน production** ซึ่งเป็นขั้นแยกเหมือนที่ทำกับ 005
(`docs/MIGRATION_005_PRODUCTION_PREAPPLY.md`) — ต้องตรวจสถานะจริงก่อน apply
ไม่ใช่เชื่อผลจากคอนเทนเนอร์ทดสอบอย่างเดียว

### 15.3 ไม่ใช่ `REVIEW_FAILED` หรือ `BLOCKED`

ไม่มีข้อตรวจใดไม่ผ่าน และไม่มีสิ่งใดขวางการ apply · เรื่องค้างในข้อ 14
เป็นงานของรอบถัด ๆ ไป ไม่ใช่เงื่อนไขก่อน apply

---

## 16. Exact next step

### 16.1 รอ Owner review ก่อน — ยังไม่ทำอะไรต่อ

```
1. Owner อ่าน migration 148 บรรทัดและรายงานนี้
2. ตัดสินใจเรื่องข้อ 14.2 (GRANT CONNECT / USAGE ON SCHEMA public)
     -> ถ้าเอา ต้องแก้ไฟล์ก่อน apply
3. อนุมัติ commit  db/migrations/006_web_identity_mapping.sql
                   eval/web_identity_mapping_check.py
                   docs/MIGRATION_006_IDENTITY_MAPPING_REVIEW.md
4. อนุมัติรอบ Pre-Apply Gate (READ-ONLY บน production)
5. อนุมัติรอบ Apply
6. รอบแยก: เติม ADVISOR_WEB_PASSWORD ลง .env + compose  (M3)
7. รอบแยก: data migration เติม S1 supabase_user_id
```

### 16.2 คำสั่งทำซ้ำการทดสอบ

```bash
docker run -d --name m006test -e POSTGRES_PASSWORD=x -e POSTGRES_DB=web_test \
    -p 55406:5432 pgvector/pgvector:pg16

docker exec -i m006test psql -U postgres -d web_test -q -v ON_ERROR_STOP=1 < db/schema.sql
docker exec -i m006test psql -U postgres -d web_test -q -v ON_ERROR_STOP=1 <<'SQL'
CREATE ROLE advisor_api    LOGIN PASSWORD 'throwaway-api';
CREATE ROLE advisor_ingest LOGIN PASSWORD 'throwaway-ingest';
GRANT SELECT, INSERT, UPDATE ON public.users TO advisor_api;
SQL

for m in 001_mko_structured 002_mko_review_publish 003_crawl_sources \
         004_crawl_decisions 005_web_schema; do
  docker exec -i m006test psql -U postgres -d web_test -q -v ON_ERROR_STOP=1 \
      < db/migrations/$m.sql
done

docker exec -i m006test psql -U postgres -d web_test -q -c \
  "CREATE ROLE advisor_web LOGIN PASSWORD 'throwaway-web' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS"

docker exec -i m006test psql -U postgres -d web_test -v ON_ERROR_STOP=1 \
    < db/migrations/006_web_identity_mapping.sql

PYTHONIOENCODING=utf-8 python eval/web_identity_mapping_check.py \
    --database-url postgresql://postgres:x@127.0.0.1:55406/web_test
PYTHONIOENCODING=utf-8 python eval/web_schema_check.py \
    --database-url postgresql://postgres:x@127.0.0.1:55406/web_test

docker rm -f m006test
```

> `PYTHONIOENCODING=utf-8` จำเป็นบน Windows เพราะ console เริ่มต้นเป็น cp1252
> ซึ่งพิมพ์ข้อความภาษาไทยไม่ได้

---

## STOP

# `MIGRATION_006_READY_FOR_PREAPPLY`

**ไม่ apply บน production** · **ไม่ commit** · **ไม่ push** · รอ Owner อนุมัติ

```
Apply บน Production   NONE     ALTER public.users บน production   NONE
GRANT บน production   NONE     เติม S1 supabase_user_id           NONE
Data Migration        NONE     แก้ production .env                NONE
แก้ webapi            NONE     แก้ frontend                       NONE
Supabase Write        NONE     Deploy / Restart                   NONE
Commit / Push / Merge NONE     แก้ migration 005                  NONE
```

เรื่องที่รอการตัดสินใจ

1. **ข้อ 14.2** — จะใส่ `GRANT CONNECT` และ `GRANT USAGE ON SCHEMA public` ลง 006 ไหม
   (ตอนนี้พึ่งค่าตั้งต้นของ `PUBLIC` อยู่) · **ถ้าเอา ต้องแก้ก่อน apply**
2. อนุมัติ **commit** 3 ไฟล์ของรอบนี้ (+ `db/20-roles.sh` ที่ค้างจากรอบก่อน)
3. อนุมัติรอบ **Pre-Apply Gate** แบบ READ-ONLY บน production
