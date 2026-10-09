# B1 — `advisor_web` Least-Privilege Role Design

| | |
|---|---|
| วันที่ | 2026-10-03 |
| ขอบเขต | **DESIGN + READ-ONLY VERIFICATION ONLY** |
| **สถานะ** | **`ADVISOR_WEB_ROLE_DESIGN_READY`** |
| ที่วาง `CREATE ROLE` | **production provisioning step แยก** — ไม่ใช่ migration (ข้อ 7) |
| ที่วาง `GRANT` | **migration 006** ห่อด้วย `IF EXISTS` แบบเดียวกับ 005 |
| กระทบ `backend` | **ไม่กระทบเลย** — ไม่ REVOKE อะไรจาก `advisor_api` |
| กระทบ Migration 005 | **ไม่แก้ 005** — ไม่แตะแม้บรรทัดเดียว |
| ⚠ กับดักที่พบ | **2 ข้อที่ทำให้ provisioning ล้มเหลวเงียบ ๆ** — ดูข้อ 7.4 และ 11.3 |

```
CREATE ROLE      NONE   ALTER ROLE          NONE   GRANT / REVOKE     NONE
สร้าง/เปลี่ยน password  NONE   แก้ .env            NONE   แก้ source code    NONE
แก้ docker-compose NONE   Migration 006       NONE   Apply Migration 005 NONE
Data Migration   NONE   Production Write    NONE   Deploy / Restart   NONE
Commit / Push    NONE   Merge               NONE
```

**ไม่มีรหัสผ่าน ไม่มีค่าใน `.env` ไม่มี connection string จริงในเอกสารนี้**

---

## 1. Current privilege findings

ตรวจบน production แบบ `SELECT` อย่างเดียว ครบทั้ง 8 รายการที่สั่ง

### 1.1 เวอร์ชันและความเป็นเจ้าของ

| # | รายการ | ผล |
|---|---|---|
| 1 | PostgreSQL version | **16.15** (Debian 16.15-1.pgdg12+2) |
| 2 | เจ้าของ schema `public` | **`pg_database_owner`** (ค่าตั้งต้นของ PG15+) |
| 2 | เจ้าของ `public.users` | **`postgres`** |
| 2 | เจ้าของ database | **`postgres`** |
| 2 | เจ้าของ schema `mko` | **`postgres`** |
| 2 | `web.touch_updated_at()` | **ยังไม่มี** — 005 ยังไม่ apply |

→ **ทุก object ที่เกี่ยวข้องเป็นของ `postgres`** ดังนั้น `GRANT` ต้องรันในนาม `postgres`
(เจ้าของ object หรือ superuser เท่านั้นที่ GRANT ได้)

### 1.2 ใครสร้าง role ได้

| # | รายการ | ผล |
|---|---|---|
| 3 | role ที่ `rolcreaterole = true` และ login ได้ | **`postgres` เท่านั้น** |
| 3 | superuser ในคลัสเตอร์ | **`postgres` เท่านั้น** |

→ `CREATE ROLE advisor_web` ต้องรันในนาม **`postgres`** · `advisor_api` และ
`advisor_ingest` ทำไม่ได้ (ยืนยันแล้วว่า `rolcreaterole = false` ทั้งคู่)

### 1.3 การสืบทอดสิทธิ์และ default privileges

| # | รายการ | ผล |
|---|---|---|
| 7 | `rolinherit` ของ role ที่มีอยู่ | `advisor_api = true` · `advisor_ingest = true` **แต่ไม่เป็นสมาชิก role ใดเลย** → การสืบทอดไม่มีผลจริง |
| 8 | `pg_default_acl` ทั้งคลัสเตอร์ | **0 รายการ** → **ตารางที่สร้างใหม่ไม่ได้สิทธิ์อัตโนมัติ** ต้อง `GRANT` อย่างตั้งใจทุกครั้ง |

### 1.4 ⚠ สิ่งที่ role ใหม่ "ได้ฟรี" จาก `PUBLIC` — ต้องรู้ไว้

| สิทธิ์ | สถานะ | ผลต่อ role ใหม่ |
|---|---|---|
| `CONNECT` บน database | **`PUBLIC` มี** | role ใหม่ **ต่อฐานข้อมูลได้ทันที** โดยไม่ต้อง GRANT |
| `USAGE ON SCHEMA public` | **`PUBLIC` มี** | role ใหม่ **เห็น schema `public` ได้ทันที** |
| `CREATE ON SCHEMA public` | **`PUBLIC` ไม่มี** (`false`) | role ใหม่ **ทำ DDL ใน `public` ไม่ได้** — ดีแล้ว |

→ `GRANT CONNECT` และ `GRANT USAGE ON SCHEMA public` ในข้อ 4 **ซ้ำซ้อนทางเทคนิค**
แต่ยังใส่ไว้โดยเจตนา เพื่อไม่ให้ความถูกต้องของ design ขึ้นอยู่กับค่าตั้งต้นของ `PUBLIC`
ที่อาจถูกเปลี่ยนภายหลัง

### 1.5 ไม่มีตารางใดเปิด RLS

```
RLS enabled ใน schema public:  ไม่มีตารางใดเลย
```

→ สิทธิ์ของ role ใหม่ถูกตัดสินด้วย `GRANT` อย่างเดียว **ไม่ต้องเขียน policy**
(ต่างจาก Supabase ที่ RLS เป็นด่านหลัก)

### 1.6 ไม่มี sequence ให้ต้องกังวล

```
ค้น SERIAL / BIGSERIAL / nextval / CREATE SEQUENCE ใน 005  ->  ไม่พบเลย
```

`web.*` ทุกตารางใช้ `gen_random_uuid()` และ `ai_settings.id` เป็น `SMALLINT DEFAULT 1`
→ **ไม่ต้อง `GRANT USAGE ON SEQUENCE`** ซึ่งเป็นสิ่งที่มักลืมและทำให้ `INSERT` ล้ม

### 1.7 extension ทั้งหมดอยู่ใน `public`

```
citext    public      <- public.users.email เป็นชนิดนี้
pgcrypto  public
vector    public
plpgsql   pg_catalog
```

→ `USAGE ON SCHEMA public` ครอบคลุมการมองเห็นชนิดข้อมูลแล้ว **ไม่ต้อง GRANT อะไรเพิ่ม**

### 1.8 Migration 005 grants ปัจจุบัน (รายการที่ 4)

จาก `db/migrations/005_web_schema.sql` บรรทัด 339–353 ห่อด้วย
`IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = …)`

```sql
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

**ไม่มี `GRANT DELETE` ให้ใครเลย**

### 1.9 `advisor_api` privileges ที่ `backend` ต้องใช้ (รายการที่ 5)

```
public.users         INSERT · SELECT · UPDATE        (DELETE = false)
public.courses       SELECT
INSERT/UPDATE ที่ใด   chat_answer_cache · chat_messages · chat_sessions
                     crawl_decisions · recommendations · shadow_answers
                     user_profiles · user_requirements · users
DELETE ที่ใด          chat_answer_cache · user_requirements   เท่านั้น
CREATE ON public     false
```

**`UPDATE` บน `public.users` เป็นระดับตาราง ไม่มี grant ระดับคอลัมน์แยก**

---

## 2. Why `advisor_api` is too broad for `webapi`

### 2.1 ปัญหาแกนกลาง

```
advisor_api  ->  public.users  UPDATE (ระดับตาราง)

หลัง migration 006 เพิ่มคอลัมน์ supabase_user_id
    -> คอลัมน์นั้นถูกครอบคลุมโดย UPDATE ระดับตารางโดยอัตโนมัติ
    -> บริการที่ "อ่าน" การจับคู่ตัวตน ก็ "เขียน" การจับคู่นั้นได้ด้วย
```

`supabase_user_id` **คือสิ่งที่ตัดสินว่าใครเป็นใคร** ถ้ามีข้อบกพร่องหรือช่องโหว่ใน
`webapi` (ซึ่งรับคำขอจากอินเทอร์เน็ตโดยตรง) การเขียนทับคอลัมน์นี้คือการผูกบัญชี Supabase
เข้ากับผู้ใช้ production คนอื่น — **เป็นการยกระดับสิทธิ์ ไม่ใช่แค่ข้อมูลเสีย**

### 2.2 สิ่งที่ `advisor_api` ให้เกินความจำเป็นของ `webapi`

| สิทธิ์ | `webapi` ต้องใช้ไหม | ความเสี่ยงถ้ามี |
|---|---|---|
| `UPDATE public.users` | **ไม่** | **สูง** — เขียนทับ `supabase_user_id` ได้ → ยกระดับสิทธิ์ |
| `INSERT public.users` | **ไม่** | สร้างผู้ใช้ใหม่ได้ ซึ่งขัดกับทุกการตัดสินใจเรื่อง provisioning |
| `SELECT public.users` **ทุกคอลัมน์** | **ไม่** — ต้องการแค่ 3 คอลัมน์ | **อ่าน `password_hash` (bcrypt) และ `email` ได้** โดยไม่มีเหตุผลใด ๆ |
| `INSERT/UPDATE` 8 ตารางของ `backend` | **ไม่** | `chat_*` · `recommendations` · `shadow_answers` · `crawl_decisions` · `user_requirements` — ไม่เกี่ยวกับหน้าเว็บเลย |
| `DELETE chat_answer_cache` · `user_requirements` | **ไม่** | ลบข้อมูลของระบบอื่นได้ |

### 2.3 ทำไมไม่ REVOKE จาก `advisor_api` แทน

ตามการตัดสินใจของเจ้าของ — และหลักฐานหนุนว่าถูก

```
advisor_api UPDATE public.users เป็นระดับตาราง
   -> ถ้า REVOKE แล้ว GRANT ระดับคอลัมน์กลับ ต้องรู้ให้ครบว่า backend แก้คอลัมน์ไหนจริง
   -> ระบุไม่ครบ = backend พังตอนแก้โปรไฟล์ผู้ใช้  และพังในทาง production ไม่ใช่ตอนทดสอบ
```

**การเพิ่ม role ใหม่เป็นการเปลี่ยนแบบ additive** ไม่มีทางทำให้ `backend` พัง
ส่วนการ REVOKE เป็นการเปลี่ยนแบบ subtractive ซึ่งมีความเสี่ยงต่อระบบที่ทำงานอยู่

### 2.4 ประโยชน์ด้าน audit

`advisor_api` ถูกใช้ร่วมกันจะทำให้แยกไม่ออกใน `pg_stat_activity` ว่า connection ไหน
มาจาก `backend` ไหนมาจาก `webapi` · ตอนนี้มี 4 connection ที่แสดงเป็น "ไม่ระบุชื่อ"
ซึ่งตามรอยไม่ได้

role แยก + `application_name=webapi` → **ตามรอยได้สองชั้น**

---

## 3. `advisor_web` target privilege matrix

### 3.1 schema `public`

| object | สิทธิ์ | เหตุผล |
|---|---|---|
| database `course_advisor` | **`CONNECT`** | ต่อฐานข้อมูล (ซ้ำซ้อนกับ `PUBLIC` แต่ระบุชัด — ข้อ 1.4) |
| schema `public` | **`USAGE`** | มองเห็น object และชนิดข้อมูล (`citext`) |
| `public.users` | **`SELECT (id, is_active, supabase_user_id)`** ⬅ **ระดับคอลัมน์** | resolve identity · ตรวจว่าผู้ใช้ยัง active |
| `public.users` | **ไม่มี `INSERT`** | ห้ามสร้างผู้ใช้ |
| `public.users` | **ไม่มี `UPDATE`** | **หัวใจของการแยก role นี้** |
| `public.users` | **ไม่มี `DELETE`** | |
| schema `public` | **ไม่มี `CREATE`** | ห้าม DDL |
| ตารางอื่นใน `public` | **ไม่มีสิทธิ์ใดเลย** | `courses` · `course_chunks` · `chat_*` · `recommendations` · ฯลฯ |

#### ⚠ ทำไม `SELECT` ระดับคอลัมน์ ไม่ใช่ระดับตาราง

```
public.users มีคอลัมน์   id · email · password_hash · full_name · is_active · is_admin
                                     ^^^^^^^^^^^^^  bcrypt hash
```

`GRANT SELECT ON public.users` ระดับตารางจะทำให้ `webapi` **อ่าน bcrypt hash และอีเมล
ของผู้ใช้ทั้ง 198 คนได้** ซึ่งไม่มีเหตุผลใดรองรับ

Option C ใช้ **uuid** ไม่ใช้อีเมล → `webapi` ไม่ต้องเห็น `email` เลย
และไม่ต้องเห็น `password_hash` แน่นอน

| คอลัมน์ | ให้ไหม | เหตุผล |
|---|---|---|
| `id` | **ให้** | ค่าที่จะเขียนลง `created_by` / `updated_by` |
| `supabase_user_id` | **ให้** | กุญแจที่ใช้ค้นหา |
| `is_active` | **ให้** | ปฏิเสธผู้ใช้ที่ถูกปิดใช้งาน |
| `email` | **ไม่ให้** | Option C ไม่ใช้อีเมล · และ `auth.mjs` ตั้งใจไม่เก็บอีเมลใน context |
| `password_hash` | **ไม่ให้** | ไม่มีเหตุผลใดเลย |
| `full_name` | **ไม่ให้ตอนนี้** | ถ้าวันหนึ่งต้องแสดง "แก้ไขล่าสุดโดย" ให้เพิ่มตอนนั้นอย่างตั้งใจ |
| `is_admin` | **ไม่ให้** | สิทธิ์ของผู้ใช้หน้าเว็บมาจาก Supabase `user_profiles.role` ไม่ใช่คอลัมน์นี้ |

> **ข้อแลกเปลี่ยนที่ยอมรับ**: grant ระดับคอลัมน์ต้องแก้เมื่อโค้ดต้องการคอลัมน์เพิ่ม
> ซึ่งจะพังเป็น `permission denied for column` ที่อ่านเข้าใจได้ **ไม่ใช่พังเงียบ ๆ**
> จึงยอมรับได้ · ทางเลือกสำรองคือระดับตาราง (ข้อ 13.4)

### 3.2 schema `web` (หลัง Migration 005 apply)

| object | SELECT | INSERT | UPDATE | DELETE |
|---|---|---|---|---|
| schema `web` | `USAGE` | — | — | — |
| `web.site_courses` | ✅ | ✅ | ✅ | ❌ |
| `web.news` | ✅ | ✅ | ✅ | ❌ |
| `web.knowledge_articles` | ✅ | ✅ | ✅ | ❌ |
| `web.ai_settings` | ✅ | ✅ | ✅ | ❌ |
| `web.external_news` | ✅ | ❌ | ❌ | ❌ |
| `web.touch_updated_at()` | `EXECUTE` | | | |

**ห้ามทั้งหมด**: `DELETE` ทุกตาราง · `INSERT`/`UPDATE` บน `web.external_news`
(เป็นของ `advisor_ingest` โดยเจตนา) · `CREATE`/`ALTER`/`DROP`

### 3.3 สิ่งที่ตรวจแล้วว่าไม่ต้อง GRANT

```
USAGE ON SEQUENCE        ไม่ต้อง — 005 ไม่มี sequence เลย (ข้อ 1.6)
USAGE บน schema อื่น      ไม่ต้อง — extension ทั้งหมดอยู่ใน public (ข้อ 1.7)
RLS policy               ไม่ต้อง — ไม่มีตารางใดเปิด RLS (ข้อ 1.5)
สมาชิก role อื่น          ไม่ต้อง — ไม่ต้อง inherit จากใคร (ข้อ 1.3 · รายการที่ 7)
REFERENCES               ไม่ต้อง — PostgreSQL ตรวจ FK ในนามเจ้าของ constraint
                         ไม่ใช่ในนามผู้ INSERT
```

ข้อสุดท้ายสำคัญ: `web.site_courses.created_by → public.users(id)` และ
`course_id → public.courses(id)` **ไม่ต้องการสิทธิ์บนตารางแม่** จาก role ที่ INSERT

---

## 4. Proposed SQL — **DESIGN ONLY ยังไม่รัน**

### 4.1 ขั้น provisioning (รันในนาม `postgres` บน production ครั้งเดียว)

```sql
-- ไม่อยู่ใน migration เพราะต้องใช้ secret  (ดูเหตุผลข้อ 7)
-- รหัสผ่านมาจาก $ADVISOR_WEB_PASSWORD ของ production .env เท่านั้น
-- ** ห้ามเขียนค่าจริงลงไฟล์ใด ๆ ที่เข้า Git **

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'advisor_web') THEN
        -- ค่ารหัสผ่านถูกส่งเข้ามาเป็น psql variable  :'web_password'
        -- รูปแบบเดียวกับที่ db/20-roles.sh ใช้กับ :'api_password'
        EXECUTE format('CREATE ROLE advisor_web LOGIN PASSWORD %L', :'web_password');
        RAISE NOTICE 'สร้าง role advisor_web แล้ว';
    ELSE
        RAISE NOTICE 'role advisor_web มีอยู่แล้ว ไม่ทำอะไร';
    END IF;
END $$;

-- ไม่ให้สิทธิ์พิเศษใด ๆ
ALTER ROLE advisor_web NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
```

> `CREATE ROLE` ไม่รองรับ `IF NOT EXISTS` ใน PostgreSQL จึงต้องห่อด้วย `DO $$` เพื่อให้
> รันซ้ำได้ · ใช้ `%L` ของ `format()` เพื่อ quote ค่าให้ปลอดภัย ไม่ใช่การต่อ string

### 4.2 GRANT ที่จะอยู่ใน migration 006 (ยังไม่สร้าง)

```sql
-- ห่อด้วย IF EXISTS แบบเดียวกับที่ 005 ทำ เพื่อให้ dev/test ที่ไม่มี role นี้ไม่ล้ม
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'advisor_web') THEN

        -- ---- schema public : อ่านอย่างเดียว และอ่านแค่ 3 คอลัมน์ ----
        GRANT CONNECT ON DATABASE course_advisor TO advisor_web;
        GRANT USAGE   ON SCHEMA public           TO advisor_web;
        GRANT SELECT (id, is_active, supabase_user_id)
              ON public.users                    TO advisor_web;

        -- ---- schema web ----
        GRANT USAGE ON SCHEMA web TO advisor_web;

        -- อ่านได้ทั้ง 5 ตาราง (ระบุชื่อ ไม่ใช้ ALL TABLES เพื่อให้เจตนาชัด
        -- และเพื่อไม่ให้ตารางที่เพิ่มในอนาคตได้สิทธิ์โดยไม่ได้ตั้งใจ)
        GRANT SELECT ON web.site_courses, web.news, web.knowledge_articles,
                        web.ai_settings, web.external_news TO advisor_web;

        -- เขียนได้ 4 ตาราง  ไม่รวม external_news
        GRANT INSERT, UPDATE ON web.site_courses, web.news,
                                web.knowledge_articles, web.ai_settings TO advisor_web;

        -- trigger ทำงานในสิทธิ์ของผู้เรียก ถ้าไม่ให้ EXECUTE ทุก UPDATE จะล้ม
        GRANT EXECUTE ON FUNCTION web.touch_updated_at() TO advisor_web;

        RAISE NOTICE 'ให้สิทธิ์ advisor_web เรียบร้อย';
    ELSE
        RAISE NOTICE 'ไม่พบ role advisor_web — ข้ามการให้สิทธิ์';
    END IF;
END $$;
```

### 4.3 สิ่งที่ตั้งใจ **ไม่** ใส่

```sql
-- ห้ามใส่ทั้งหมดนี้
GRANT INSERT, UPDATE, DELETE ON public.users TO advisor_web;   -- แกนของการแยก role
GRANT DELETE ON ALL TABLES IN SCHEMA web TO advisor_web;       -- ตามการตัดสินใจเดิม
GRANT INSERT, UPDATE ON web.external_news TO advisor_web;      -- เป็นของ advisor_ingest
GRANT CREATE ON SCHEMA public TO advisor_web;                  -- DDL
GRANT CREATE ON SCHEMA web TO advisor_web;                     -- DDL
GRANT advisor_api TO advisor_web;                              -- ห้าม inherit
ALTER ROLE advisor_web SUPERUSER;                              -- ไม่ต้องพูดถึง
GRANT SELECT ON ALL TABLES IN SCHEMA public TO advisor_web;     -- กว้างเกินมาก
```

### 4.4 ลำดับที่บังคับ

```
1. Apply Migration 005        สร้าง schema web + ตาราง + ฟังก์ชัน
2. Provisioning step (4.1)    CREATE ROLE advisor_web
3. Migration 006              ADD COLUMN supabase_user_id  แล้วจึง GRANT (4.2)
```

**GRANT ของข้อ 4.2 อ้างถึงทั้ง `web.*` (จาก 005) และ `public.users.supabase_user_id`
(จาก 006)** → ต้องอยู่ **หลัง** `ADD COLUMN` ในไฟล์ 006 เดียวกัน
ถ้า GRANT ระดับคอลัมน์รันก่อน `ADD COLUMN` จะล้มด้วย `column … does not exist`

---

## 5. Secret / env design

### 5.1 ตัวแปรใหม่ 1 ตัว

```
ADVISOR_WEB_PASSWORD
```

| | |
|---|---|
| ที่เก็บ | `/home/ubuntu/course-advisor-system/.env` บน production (mode **`600 ubuntu:ubuntu`** ตรวจแล้ว) |
| เข้า Git ไหม | **ไม่** — `.env` ถูก gitignore (`.gitignore:17`) และ `git ls-files .env` = **0** |
| ต้องเพิ่มใน `.env.example` ไหม | **ควร** — เพิ่ม **ชื่อตัวแปรเท่านั้น ไม่มีค่า** เพื่อให้คนตั้งสภาพแวดล้อมใหม่รู้ว่าต้องมี |
| ใครสร้างค่า | **เจ้าของ** · ไม่ใช่ผม — ผมไม่สร้างและไม่เปลี่ยนรหัสผ่านใด |
| ความยาวที่แนะนำ | สุ่มอย่างน้อย 32 ไบต์ (เช่น `openssl rand -base64 32`) — รูปแบบเดียวกับที่ `.env.example` แนะนำสำหรับ `JWT_SECRET` |

### 5.2 เส้นทางที่รหัสผ่านเดินทาง

```
.env (600)  ->  docker compose interpolate ${ADVISOR_WEB_PASSWORD}
            ->  environment ของ container webapi
            ->  process.env.DATABASE_URL
            ->  pg.Pool

และอีกเส้นหนึ่ง (ครั้งเดียวตอน provisioning)
.env (600)  ->  psql -v web_password="$ADVISOR_WEB_PASSWORD"
            ->  CREATE ROLE … PASSWORD :'web_password'
```

**รหัสผ่านไม่เคยอยู่ใน**: repo · image · migration file · log · เอกสารนี้

### 5.3 กฎตอน implement

```
ห้าม console.log ค่า DATABASE_URL หรือส่วนใดของมัน
ห้ามส่ง error ดิบของ driver ออกไปใน response  (ข้อความอาจมี host/user)
ห้าม echo ค่า $ADVISOR_WEB_PASSWORD ตอนรัน provisioning
ห้ามใส่รหัสผ่านใน command line ที่ ps เห็นได้  -> ใช้ psql -v จาก env ไม่ใช่ -c ที่มีค่าฝัง
```

ข้อสุดท้ายสำคัญ: `psql -c "CREATE ROLE … PASSWORD 'ค่าจริง'"` จะทำให้รหัสผ่าน
**ปรากฏใน `ps` และใน shell history** · ใช้ `-v` ที่อ่านจาก env แทน

---

## 6. `DATABASE_URL` design

### 6.1 รูปแบบ

```
postgresql://advisor_web:${ADVISOR_WEB_PASSWORD}@postgres:5432/course_advisor?application_name=webapi
```

| ส่วน | ค่า | เหตุผล |
|---|---|---|
| scheme | **`postgresql://`** | **ไม่ใช่ `postgresql+psycopg://`** — `+psycopg` เป็นรูปแบบของ SQLAlchemy ที่ `pg` parse ไม่ได้ · **ห้ามคัดลอกค่าของ `backend` มาตรง ๆ** |
| user | `advisor_web` | |
| password | `${ADVISOR_WEB_PASSWORD}` | interpolate โดย compose · **ไม่มีค่าจริงที่ใด** |
| host | **`postgres`** | ชื่อ service ใน compose · **ห้ามใช้ `localhost`** (ใน container หมายถึงตัวเอง) |
| port | `5432` | พอร์ตภายใน · postgres ไม่ publish ออกนอกเครื่อง |
| database | `course_advisor` | |
| `application_name` | **`webapi`** | แยกใน `pg_stat_activity` ได้ว่า connection ไหนมาจากบริการไหน — **ชั้นที่สองของ audit** นอกจากชื่อ role |

### 6.2 ที่วางใน compose (ยังไม่แก้)

```yaml
  webapi:
    environment:
      VITE_SUPABASE_URL: ${VITE_SUPABASE_URL}
      VITE_SUPABASE_ANON_KEY: ${VITE_SUPABASE_ANON_KEY}
      GOOGLE_GENERATIVE_AI_API_KEY: ${GOOGLE_GENERATIVE_AI_API_KEY:-}
      DATABASE_URL: postgresql://advisor_web:${ADVISOR_WEB_PASSWORD}@postgres:5432/course_advisor?application_name=webapi
    depends_on:
      postgres:
        condition: service_healthy
```

> `webapi` วันนี้ **ไม่มี `depends_on` เลย** → ต้องเพิ่มด้วย ไม่ใช่แค่ `DATABASE_URL`

### 6.3 ถ้าไม่ได้ตั้งค่า — fail closed

```
ไม่มี DATABASE_URL  ->  endpoint ที่ต้อง resolve identity ตอบ 500
                        /healthz รายงาน dbConfigured: false
                        ** ห้าม fallback ไปค่าใด และห้ามข้ามการ resolve **
```

เป็นรูปแบบเดียวกับที่ `auth.mjs` ทำอยู่แล้วกับ `supabaseEnv()`

---

## 7. Migration vs provisioning placement decision

# **`CREATE ROLE` = provisioning step แยก · `GRANT` = migration 006**

### 7.1 ทำไมแยกเช่นนี้ — เทียบ 5 มิติที่สั่งให้พิจารณา

| มิติ | `CREATE ROLE` ใน migration | **`CREATE ROLE` ใน provisioning** |
|---|---|---|
| **password / secret** | **ปัญหาร้ายแรง** — migration file เข้า Git ถ้ามีรหัสผ่านก็รั่ว · ถ้าไม่มีก็สร้าง role ที่ล็อกอินไม่ได้ | ✅ อ่านจาก `.env` ที่ไม่เข้า Git |
| **idempotency** | ทำได้ด้วย `DO $$ IF NOT EXISTS` แต่ไม่ได้แก้ปัญหา secret | ✅ ทำได้เหมือนกัน |
| **dev / test** | ต้องมีรหัสผ่านใน repo เพื่อให้ dev ใช้ได้ = รั่ว | ✅ dev/test ได้ role จาก `db/20-roles.sh` ซึ่งอ่านจาก env เหมือนกัน |
| **rollback** | ลบ role ที่มี object ขึ้นอยู่ด้วยยาก และ role เป็นวัตถุระดับ **cluster** ไม่ใช่ระดับ schema | ✅ ถอนแยกจาก schema ได้ |
| **แยก schema migration ออกจาก infrastructure** | role เป็น **cluster-level** · migration ควรจัดการ **schema-level** | ✅ ตรงกับหลักนี้ |

### 7.2 ที่สำคัญกว่าเหตุผลข้างบน — **repo นี้ทำแบบนี้อยู่แล้ว**

```
db/20-roles.sh        สร้าง advisor_api / advisor_ingest  อ่านรหัสผ่านจาก env
                      คอมเมนต์ในไฟล์อธิบายเองว่าทำไมเป็น .sh ไม่ใช่ .sql:
                      "ไฟล์ .sql ใน initdb ไม่รองรับการอ่าน environment variable
                       ถ้าจะใส่รหัสผ่านต้อง hardcode ลงไฟล์ที่ commit เข้า git ซึ่งห้ามทำ"

005_web_schema.sql    GRANT เท่านั้น ห่อด้วย IF EXISTS (… pg_roles …)
                      -> สมมติว่า role ถูกสร้างมาก่อนแล้ว และข้ามไปอย่างสุภาพถ้าไม่มี
```

**การแยก "role = infrastructure · grant = migration" เป็นหลักที่โปรเจกต์นี้ตั้งไว้แล้ว**
`advisor_web` ควรเดินตามแบบเดียวกัน ไม่ใช่สร้างแบบใหม่

### 7.3 แล้ว `db/20-roles.sh` ควรเพิ่ม `advisor_web` ไหม — **ควร แต่ไม่พอ**

| สภาพแวดล้อม | ได้ role จากไหน |
|---|---|
| dev / test / e2e (volume ใหม่) | ✅ `20-roles.sh` รันอัตโนมัติตอน initdb |
| **production (volume มีอยู่แล้ว)** | ❌ **`20-roles.sh` ไม่รันอีก** → ต้องรันขั้น provisioning ด้วยมือครั้งเดียว |

### 7.4 ⚠ กับดักที่ 1 — `20-roles.sh` ไม่รันบน production

`docker-compose.prod.yml:26` mount `./db/20-roles.sh` เข้า `/docker-entrypoint-initdb.d/`
ซึ่ง PostgreSQL image รัน **เฉพาะเมื่อ data directory ว่าง**

production มี volume `pgdata` ที่มีข้อมูลอยู่แล้ว → **การเพิ่ม `advisor_web` ลงใน
`20-roles.sh` แล้ว deploy จะไม่สร้าง role บน production เลย** และ `webapi` จะต่อฐานข้อมูล
ไม่ได้ด้วย error `role "advisor_web" does not exist`

**ต้องทำทั้งสองอย่าง**

```
1. เพิ่มใน db/20-roles.sh        -> เพื่อ dev/test/e2e และเพื่อการติดตั้งใหม่ในอนาคต
2. รันขั้น provisioning ด้วยมือ   -> เพื่อ production ที่มี volume อยู่แล้ว  ครั้งเดียว
```

### 7.5 ⚠ กับดักที่ 2 — `IF EXISTS` ทำให้ GRANT หายเงียบ ๆ

GRANT ใน 006 ห่อด้วย `IF EXISTS (… pg_roles …)` ซึ่งดีสำหรับ dev/test
แต่หมายความว่า **ถ้า apply 006 ก่อนสร้าง role → GRANT ถูกข้ามไปทั้งก้อนโดยไม่มี error**

migration จะรายงานว่าสำเร็จ แล้ว `webapi` จะพังทีหลังด้วย `permission denied for table`
ซึ่งดูเหมือนปัญหาของโค้ด ไม่ใช่ปัญหาของลำดับการติดตั้ง

**ทางป้องกัน**

```
ลำดับที่บังคับ    005  ->  provisioning (CREATE ROLE)  ->  006 (ADD COLUMN + GRANT)
และ              ขั้นตรวจหลัง provisioning ต้องยืนยัน "สิทธิ์" ไม่ใช่แค่ "role มีอยู่"
                 (ดูข้อ 11)
```

---

## 8. Impact on `backend`

# **ไม่กระทบเลย**

| | |
|---|---|
| REVOKE อะไรจาก `advisor_api` ไหม | **ไม่** — ไม่มีคำสั่ง REVOKE ใดในการออกแบบนี้ |
| เปลี่ยนสิทธิ์ของ `advisor_api` ไหม | **ไม่** |
| เปลี่ยน `DATABASE_URL` ของ `backend` ไหม | **ไม่** |
| `backend` ต้อง restart ไหม | **ไม่** |
| เป็นการเปลี่ยนแบบใด | **additive เท่านั้น** — เพิ่ม role ใหม่ ไม่แตะของเดิม |

### 8.1 สิ่งเดียวที่ `backend` จะ "รู้สึก"

```
connection pool ของ advisor_web  max 4
max_connections                   100
ใช้อยู่ตอนนี้                      8    (advisor_api=1 · postgres=3 · ไม่ระบุชื่อ 4)
backend สูงสุด                    30   (pool_size 10 + max_overflow 20)
รวมแย่สุดหลังเพิ่ม webapi           ~42  <  100
```

เหลือพื้นที่พอ · และ `advisor_web` มี `rolconnlimit` ที่ตั้งได้ถ้าต้องการเพดานแข็ง
(ไม่ได้เสนอในรอบนี้เพราะ pool `max = 4` คุมอยู่แล้ว)

---

## 9. Impact on Migration 005

# **ไม่แก้ 005 แม้บรรทัดเดียว**

| | |
|---|---|
| ต้องแก้ GRANT ของ 005 ไหม | **ไม่** — GRANT ของ `advisor_api`/`advisor_ingest` คงเดิมทั้งหมด |
| 005 ต้องรู้จัก `advisor_web` ไหม | **ไม่** — GRANT ของ role ใหม่อยู่ใน 006 |
| ถ้า apply 005 ก่อนสร้าง role | **ไม่มีผล** — 005 ไม่พูดถึง `advisor_web` เลย |
| 005 ยัง apply บน production แล้วหรือยัง | **ยังไม่** — `web` schema ยังไม่มี (ยืนยันแล้ว) |

### 9.1 005 ยังเป็น prerequisite

GRANT ใน 006 อ้างถึง `web.site_courses` · `web.news` · `web.knowledge_articles` ·
`web.ai_settings` · `web.external_news` · `web.touch_updated_at()`
→ **ทั้งหมดต้องมีอยู่ก่อน** มิฉะนั้น GRANT จะล้มด้วย `relation does not exist`

---

## 10. Impact on Migration 006

006 จะมี **3 ส่วน** ตามลำดับนี้ (ยังไม่สร้าง)

```sql
-- ส่วน 1  คอลัมน์ identity mapping  (Option C ที่เจ้าของอนุมัติ)
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS supabase_user_id UUID;
CREATE UNIQUE INDEX IF NOT EXISTS uq_users_supabase_user_id
    ON public.users (supabase_user_id) WHERE supabase_user_id IS NOT NULL;
COMMENT ON COLUMN public.users.supabase_user_id IS '…';

-- ส่วน 2  GRANT ให้ advisor_web   (ข้อ 4.2)
--         ** ต้องอยู่หลังส่วน 1 ** เพราะ GRANT ระดับคอลัมน์อ้างถึงคอลัมน์ที่เพิ่งเพิ่ม

-- ส่วน 3  ไม่มี — ไม่ REVOKE อะไรจาก advisor_api
```

### 10.1 partial unique index ไม่ใช่ `UNIQUE` ธรรมดา

ผู้ใช้ 196 จาก 198 คนจะมี `supabase_user_id = NULL` (มีแต่ S1 ที่ถูกจับคู่)
→ `UNIQUE` ธรรมดายอมให้ NULL ซ้ำได้อยู่แล้วใน PostgreSQL **แต่** partial index
(`WHERE supabase_user_id IS NOT NULL`) ทำให้เจตนาชัดและ index เล็กกว่า
เป็นรูปแบบเดียวกับที่ 005 ใช้กับ `external_news.slug`

### 10.2 ข้อตรวจที่ 006 ต้องมาพร้อม

```
คอลัมน์เป็น nullable                     (196/198 แถวจะเป็น NULL)
partial unique index ทำงานจริง            สอง uuid เดียวกันถูกปฏิเสธ · หลาย NULL อยู่ร่วมกันได้
advisor_web SELECT ได้แค่ 3 คอลัมน์        อ่าน email / password_hash ต้องถูกปฏิเสธ
advisor_web UPDATE public.users ไม่ได้     ** ข้อสำคัญที่สุด **
advisor_web DELETE web.* ไม่ได้
advisor_web INSERT/UPDATE web.external_news ไม่ได้
advisor_api ไม่ถูกแตะ                     สิทธิ์เดิมครบเท่าเดิมทุกข้อ
```

ข้อสุดท้ายสำคัญ — **ต้องพิสูจน์ว่าไม่กระทบ `backend` ไม่ใช่แค่เชื่อ**

---

## 11. Verification plan after provisioning

ทุกข้อเป็น `SELECT` / `has_*_privilege()` — **อ่านอย่างเดียว ไม่เขียนข้อมูล**

### 11.1 ยืนยันว่า role ถูกสร้างและไม่มีสิทธิ์พิเศษ

```sql
SELECT rolname, rolcanlogin, rolsuper, rolcreatedb, rolcreaterole,
       rolreplication, rolbypassrls, rolconnlimit
FROM pg_roles WHERE rolname = 'advisor_web';
-- คาดหวัง: login=t · อื่น ๆ = f ทั้งหมด

SELECT count(*) AS memberships FROM pg_auth_members m
JOIN pg_roles r ON r.oid = m.member WHERE r.rolname = 'advisor_web';
-- คาดหวัง: 0  (ไม่ inherit จากใคร)
```

### 11.2 ยืนยันสิทธิ์ที่ **ต้องมี**

```sql
SELECT has_database_privilege('advisor_web','course_advisor','CONNECT')  AS connect_db,
       has_schema_privilege  ('advisor_web','public','USAGE')            AS usage_public,
       has_schema_privilege  ('advisor_web','web','USAGE')               AS usage_web,
       has_column_privilege  ('advisor_web','public.users','id','SELECT')               AS sel_id,
       has_column_privilege  ('advisor_web','public.users','supabase_user_id','SELECT') AS sel_map,
       has_column_privilege  ('advisor_web','public.users','is_active','SELECT')        AS sel_active,
       has_table_privilege   ('advisor_web','web.site_courses','SELECT')  AS sel_courses,
       has_table_privilege   ('advisor_web','web.site_courses','INSERT')  AS ins_courses,
       has_table_privilege   ('advisor_web','web.site_courses','UPDATE')  AS upd_courses,
       has_function_privilege('advisor_web','web.touch_updated_at()','EXECUTE') AS exec_trg;
-- คาดหวัง: true ทุกคอลัมน์
```

### 11.3 ⚠ ยืนยันสิทธิ์ที่ **ต้องไม่มี** — ข้อนี้สำคัญที่สุด

```sql
SELECT has_table_privilege ('advisor_web','public.users','UPDATE')        AS upd_users,
       has_table_privilege ('advisor_web','public.users','INSERT')        AS ins_users,
       has_table_privilege ('advisor_web','public.users','DELETE')        AS del_users,
       has_column_privilege('advisor_web','public.users','supabase_user_id','UPDATE') AS upd_map,
       has_column_privilege('advisor_web','public.users','email','SELECT')         AS sel_email,
       has_column_privilege('advisor_web','public.users','password_hash','SELECT')  AS sel_hash,
       has_table_privilege ('advisor_web','web.site_courses','DELETE')    AS del_courses,
       has_table_privilege ('advisor_web','web.news','DELETE')            AS del_news,
       has_table_privilege ('advisor_web','web.external_news','INSERT')    AS ins_extnews,
       has_table_privilege ('advisor_web','web.external_news','UPDATE')    AS upd_extnews,
       has_schema_privilege('advisor_web','public','CREATE')              AS create_public,
       has_schema_privilege('advisor_web','web','CREATE')                 AS create_web,
       has_table_privilege ('advisor_web','public.courses','SELECT')      AS sel_courses_pub;
-- คาดหวัง: false ทุกคอลัมน์
```

**ข้อตรวจกลุ่มนี้เป็นเหตุผลทั้งหมดของการแยก role** — ถ้าข้อใดเป็น `true`
การแยก role ไม่ได้ให้ประโยชน์อะไรและต้องหยุดแก้ก่อนใช้งาน

### 11.4 ยืนยันว่า `advisor_api` ไม่ถูกแตะ

```sql
SELECT privilege_type FROM information_schema.table_privileges
WHERE grantee = 'advisor_api' AND table_schema = 'public' AND table_name = 'users'
ORDER BY privilege_type;
-- คาดหวัง: INSERT · SELECT · UPDATE   (เท่าเดิมทุกข้อ ไม่หายไปข้อใด)
```

### 11.5 ยืนยันเชิงพฤติกรรม ไม่ใช่แค่ catalog

`has_*_privilege()` อ่านประกาศ — ควรพิสูจน์ผลจริงในสภาพแวดล้อมทดสอบด้วย

```
ต่อด้วย advisor_web แล้วลอง
    SELECT id FROM public.users LIMIT 1                     -> ต้องผ่าน
    SELECT email FROM public.users LIMIT 1                   -> ต้องถูกปฏิเสธ
    SELECT password_hash FROM public.users LIMIT 1            -> ต้องถูกปฏิเสธ
    UPDATE public.users SET supabase_user_id = NULL          -> ต้องถูกปฏิเสธ
    DELETE FROM web.news WHERE false                          -> ต้องถูกปฏิเสธ
    INSERT INTO web.external_news (…) …                       -> ต้องถูกปฏิเสธ
    INSERT INTO web.news (title) VALUES ('x')                 -> ต้องผ่าน
** ทำในคอนเทนเนอร์ทดสอบที่ทิ้งได้ ไม่ทำบน production **
```

เป็นบทเรียนเดียวกับที่ใช้กับ `ON DELETE SET NULL` ในรอบ G2 — **การอ่านประกาศ
ไม่เท่ากับการพิสูจน์ผล**

---

## 12. Rollback plan

### 12.1 ถอนทีละชั้น จากบนลงล่าง

```
ชั้น 1  webapi ใช้ advisor_web ไม่ได้
        -> เปลี่ยน DATABASE_URL กลับเป็น advisor_api ใน .env/compose แล้ว restart webapi
        -> ใช้งานได้ทันที เพราะ advisor_api มีสิทธิ์ครอบคลุมอยู่แล้ว (ข้อ 1.9)
        -> ** นี่คือทางถอนที่เร็วที่สุดและไม่แตะฐานข้อมูลเลย **

ชั้น 2  GRANT ของ advisor_web มีปัญหา
        -> REVOKE ALL PRIVILEGES ON … FROM advisor_web
        -> ไม่กระทบ advisor_api เพราะสิทธิ์แยกกันสมบูรณ์

ชั้น 3  ต้องลบ role
        -> ต้อง REVOKE ทุกอย่างก่อน แล้ว DROP ROLE advisor_web
        -> role ไม่ได้เป็นเจ้าของ object ใดเลย (ไม่มี CREATE) จึงไม่มี object กำพร้า
        -> ถ้า DROP ไม่สำเร็จให้ใช้ REASSIGN OWNED / DROP OWNED ก่อน
           (ตามหลักการ ไม่ควรจำเป็นเพราะ role นี้สร้าง object ไม่ได้)

ชั้น 4  คอลัมน์ supabase_user_id
        -> เป็นเรื่องของ rollback migration 006 ไม่ใช่ของ role
        -> DROP COLUMN จะทำให้ GRANT ระดับคอลัมน์หายไปด้วยอัตโนมัติ
```

### 12.2 คุณสมบัติที่ทำให้ถอนกลับง่าย

| | |
|---|---|
| ไม่มี REVOKE จาก `advisor_api` | **ไม่มีอะไรต้องคืนให้ `backend`** |
| role ใหม่ไม่เป็นเจ้าของ object ใด | ลบได้โดยไม่มี object กำพร้า |
| `webapi` ยังต่อด้วย `advisor_api` ได้ | **ทางถอนฉุกเฉินที่ไม่ต้องแตะฐานข้อมูล** |
| GRANT เป็น idempotent | รันซ้ำได้ไม่เสียหาย |

### 12.3 สิ่งที่ถอนกลับ **ไม่** ได้

```
ค่า supabase_user_id ที่เติมไปแล้ว   ->  ถ้า DROP COLUMN ข้อมูลการจับคู่หายไป
                                        ต้องบันทึกไว้ก่อนถอน (ซึ่งมีแค่ 1 แถวคือ S1)
รหัสผ่านที่สร้างไปแล้ว                ->  ไม่ใช่เรื่องที่ต้องถอน แต่ควรเพิกถอนถ้าเลิกใช้ role
```

---

## 13. Security risks

| # | ความเสี่ยง | ระดับ | ทางลด |
|---|---|---|---|
| **W1** | **`20-roles.sh` ไม่รันบน production** → deploy แล้ว role ไม่เกิด `webapi` ต่อฐานข้อมูลไม่ได้ | **สูง** | ข้อ 7.4 — ต้องรันขั้น provisioning ด้วยมือครั้งเดียว · **fail closed** (บริการเข้าไม่ได้ ไม่ใช่เข้าได้โดยไม่มีสิทธิ์) |
| **W2** | **`IF EXISTS` ทำให้ GRANT หายเงียบ ๆ** ถ้า apply 006 ก่อนสร้าง role | **สูง** | ข้อ 7.5 — ลำดับที่บังคับ + ขั้นตรวจที่ยืนยัน **สิทธิ์** ไม่ใช่แค่ว่า role มีอยู่ (ข้อ 11.3) |
| **W3** | **รหัสผ่านหลุดใน `ps` / shell history** ตอน provisioning | **สูง** | ข้อ 5.3 — ใช้ `psql -v` อ่านจาก env **ห้าม** `-c` ที่มีค่าฝังในคำสั่ง |
| **W4** | **GRANT ระดับคอลัมน์พังเมื่อโค้ดต้องการคอลัมน์เพิ่ม** | กลาง | พังเป็น `permission denied for column` ที่อ่านเข้าใจได้ · ต้องบันทึกในเอกสารว่าการเพิ่มคอลัมน์ที่อ่านต้องแก้ GRANT ด้วย |
| **W5** | **`PUBLIC` มี `CONNECT` และ `USAGE ON SCHEMA public`** → role ใหม่ได้สองอย่างนี้ฟรี | ต่ำ | ข้อ 1.4 — ไม่ใช่ความเสี่ยงใหม่ที่เกิดจาก role นี้ · การ REVOKE จาก `PUBLIC` จะกระทบ role อื่นทั้งหมด **อยู่นอกขอบเขต** |
| **W6** | **`advisor_web` ยังอ่าน `web.external_news` ได้** | ต่ำ | จำเป็นจริงสำหรับ `GET /api/sci-connect-news*` ซึ่งเป็น endpoint สาธารณะ · เขียนไม่ได้ |
| **W7** | **ใช้รหัสผ่านซ้ำกับ role อื่น** | กลาง | ต้องเป็นค่าสุ่มใหม่ ไม่ใช่ค่าเดียวกับ `ADVISOR_API_PASSWORD` · **ผมไม่สร้างค่า เจ้าของสร้าง** |
| **W8** | **การเติม `supabase_user_id` ทำโดย `webapi`** | **สูงถ้าพลาด** | **`advisor_web` ไม่มี `UPDATE` บน `public.users` → ทำไม่ได้โดยโครงสร้าง** ไม่ต้องพึ่งวินัยของโค้ด · ขั้นเติมค่าต้องรันในนาม `postgres` โดยเจ้าของ |

### 13.1 W8 คือเหตุผลที่การแยก role นี้คุ้ม

```
ก่อนแยก   webapi ใช้ advisor_api  ->  มี UPDATE public.users  ->  เขียน supabase_user_id ได้
                                      กันได้ด้วย "โค้ดไม่เขียน" เท่านั้น = พึ่งวินัย

หลังแยก   webapi ใช้ advisor_web   ->  ไม่มี UPDATE public.users  ->  ฐานข้อมูลปฏิเสธ
                                      กันได้ด้วยโครงสร้าง = ไม่พึ่งวินัย
```

**ย้ายการป้องกันจากชั้นที่พลาดได้ ไปอยู่ชั้นที่พลาดไม่ได้**

### 13.2 สิ่งที่ไม่ได้แก้และไม่ได้อ้างว่าแก้

```
R1  createSupabaseVerifier ยังไม่เคยคุยกับ Supabase จริง      ค้างจากรอบ foundation
R6  ครึ่งหนึ่งของงาน B1 อยู่ในรีโปหน้าเว็บที่ยังไม่อนุมัติ        ค้างจากรอบ foundation
S2-PRIV  S2 ยังมีสิทธิ์ admin เต็มบน Supabase                 เป็น Supabase write รอบแยก
```

ทั้งสามไม่เกี่ยวกับ role ของฐานข้อมูลปลายทาง

---

## 14. Final classification

# `ADVISOR_WEB_ROLE_DESIGN_READY`

### 14.1 ทำไมไม่ใช่ `ADVISOR_WEB_ROLE_VERIFICATION_REQUIRED`

ตรวจครบทั้ง 8 รายการที่สั่ง ไม่มีข้อใดเหลือเป็น "ยังไม่รู้"

```
1 version                 16.15
2 ownership               public=pg_database_owner · users/mko/db=postgres
3 ใครสร้าง role ได้          postgres เท่านั้น (เป็น superuser เดียวด้วย)
4 005 grants              ครบ ยกมาแล้ว (ข้อ 1.8)
5 advisor_api privileges  ครบ ยกมาแล้ว (ข้อ 1.9)
6 แยกได้โดยไม่กระทบ backend  ได้ — additive เท่านั้น ไม่มี REVOKE (ข้อ 8)
7 ต้อง inherit ไหม          ไม่ต้อง — role ที่มีอยู่ไม่เป็นสมาชิกใครเลย
8 default privileges       0 รายการทั้งคลัสเตอร์ — ไม่มีสิทธิ์เกินโดยไม่ตั้งใจ
```

เพิ่มที่ตรวจเองเพราะจำเป็น: ไม่มี RLS · ไม่มี sequence · extension อยู่ใน `public` ทั้งหมด ·
`PUBLIC` มี CONNECT + USAGE อยู่แล้ว

### 14.2 ทำไมไม่ใช่ `ADVISOR_WEB_ROLE_BLOCKED`

```
ไม่ต้องแก้ 005                     ไม่ต้อง REVOKE อะไร
ไม่ต้องแก้ backend                 ไม่ต้องแก้ network
ไม่ต้องรอใครอนุมัติเรื่อง schema     role เป็นวัตถุระดับ cluster แยกจาก migration
```

ต้องการแค่ **1 secret ใหม่** (`ADVISOR_WEB_PASSWORD` ที่เจ้าของสร้าง) และ
**ขั้น provisioning ครั้งเดียวบน production**

### 14.3 สิ่งที่ยังไม่ได้ทำและจะไม่ทำจนได้รับอนุมัติ

```
ไม่ CREATE ROLE  ไม่ ALTER ROLE  ไม่ GRANT  ไม่ REVOKE
ไม่สร้าง/เปลี่ยนรหัสผ่าน  ไม่แก้ .env  ไม่แก้ source  ไม่แก้ compose
ไม่สร้าง migration 006  ไม่ apply 005  ไม่ deploy  ไม่ commit  ไม่ push
```

### 14.4 ทางเลือกสำรองถ้าไม่ต้องการ GRANT ระดับคอลัมน์

ถ้าเห็นว่า grant ระดับคอลัมน์เปราะเกินไป (W4) ใช้ระดับตารางแทนได้

```sql
GRANT SELECT ON public.users TO advisor_web;    -- แทนที่ GRANT SELECT (id, is_active, supabase_user_id)
```

**ยังได้ประโยชน์หลักครบ** — ไม่มี `UPDATE`/`INSERT`/`DELETE` บน `public.users`
ซึ่งเป็นแกนของการแยก role · **แต่เสีย** การกัน `webapi` ไม่ให้อ่าน `password_hash` และ `email`

**ข้อเสนอ: ใช้ระดับคอลัมน์** เพราะ bcrypt hash ไม่ควรอยู่ในมือบริการที่ไม่ต้องใช้
แต่เป็นการตัดสินใจของเจ้าของ

---

## 15. Exact next step

```
1. เจ้าของสร้างค่า ADVISOR_WEB_PASSWORD แล้วใส่ใน production .env
     openssl rand -base64 32    (ผมไม่สร้างและไม่เห็นค่า)
     ** ห้ามใช้ค่าเดียวกับ ADVISOR_API_PASSWORD **

2. ตัดสินข้อ 14.4            GRANT SELECT ระดับคอลัมน์ หรือระดับตาราง
                             (ข้อเสนอ: ระดับคอลัมน์)

3. ขออนุมัติ Apply Migration 005 บน production      ** ยังไม่เคย apply **
                             เป็น prerequisite ของ GRANT ใน 006 (ข้อ 9.1)

4. ขออนุมัติขั้น provisioning  CREATE ROLE advisor_web (ข้อ 4.1) รันในนาม postgres
                             + เพิ่มใน db/20-roles.sh สำหรับ dev/test (ข้อ 7.3)
                             ** ทั้งสองอย่าง ไม่ใช่อย่างเดียว — ดู W1 **

5. ขออนุมัติ migration 006    ADD COLUMN supabase_user_id + partial unique index
                             + GRANT ของข้อ 4.2 + ข้อตรวจของข้อ 10.2
                             ** ห้ามแก้ 005 **

6. รันขั้นตรวจของข้อ 11       โดยเฉพาะ 11.3 ที่ยืนยันสิทธิ์ที่ "ต้องไม่มี"
                             ถ้าข้อใดเป็น true ให้หยุดและแก้ก่อนใช้งาน

7. ขออนุมัติ implement M3     6 ไฟล์ตาม B1_M3_POSTGRES_CONNECTION_DESIGN.md ข้อ 10
                             แต่ DATABASE_URL ใช้ advisor_web ไม่ใช่ advisor_api

8. ขั้นเติมค่า supabase_user_id ของ S1   รันในนาม postgres โดยเจ้าของ
                             ** ไม่ใช่ webapi — advisor_web ทำไม่ได้โดยโครงสร้าง **
```

### 15.1 ลำดับที่สลับไม่ได้

```
005  ->  CREATE ROLE  ->  006 (ADD COLUMN + GRANT)  ->  ตรวจข้อ 11  ->  implement M3
```

สลับข้อ 2 กับ 3 จะทำให้ GRANT ใน 006 ถูกข้ามเงียบ ๆ ตาม W2

---

## บันทึกการเข้าถึงข้อมูลในรอบนี้

| ระบบ | การเข้าถึง | รายละเอียด |
|---|---|---|
| source / config ในรีโป | **อ่านอย่างเดียว** | `005_web_schema.sql` · `db/20-roles.sh` · `db/schema.sql` · `docker-compose.prod.yml` · `webapi/*` · `.gitignore` |
| production PostgreSQL | **`SELECT` อย่างเดียว** | `pg_roles` · `pg_namespace` · `pg_class` · `pg_proc` · `pg_default_acl` · `pg_extension` · `information_schema.*_privileges` · `has_*_privilege()` · `pg_stat_activity` |
| ข้อมูลที่ดึงออกมา | ชื่อ role · ชื่อสิทธิ์ · ชื่อเจ้าของ · ชื่อ schema · จำนวน · boolean | **ไม่มีรหัสผ่าน ไม่มีค่าใน `.env` ไม่มี connection string จริง ไม่มีอีเมล ไม่มี uuid** |
| คำสั่งเขียน / DDL / DCL | **ไม่มีแม้คำสั่งเดียว** | ไม่มี `CREATE` · `ALTER` · `GRANT` · `REVOKE` · `INSERT` · `UPDATE` · `DELETE` |

---

## STOP

**`ADVISOR_WEB_ROLE_DESIGN_READY`**

เรื่องที่รอการตัดสินใจ

1. **ข้อ 14.4** — `GRANT SELECT` ระดับคอลัมน์ (กัน `password_hash` และ `email`)
   หรือระดับตาราง (ข้อเสนอ: **ระดับคอลัมน์**)
2. **สร้าง `ADVISOR_WEB_PASSWORD`** ใส่ production `.env` (เจ้าของทำ ผมไม่เห็นค่า)
3. **อนุมัติ Apply Migration 005 บน production** — prerequisite ของ 006
4. **อนุมัติขั้น provisioning** `CREATE ROLE` + เพิ่มใน `20-roles.sh` **ทั้งสองอย่าง**
5. **อนุมัติ migration 006** (`ADD COLUMN` + `GRANT` + ข้อตรวจ)
6. **อนุมัติ implement M3** โดยใช้ `advisor_web`

```
CREATE ROLE      NONE   ALTER ROLE          NONE   GRANT / REVOKE     NONE
สร้าง/เปลี่ยน password  NONE   แก้ .env            NONE   แก้ source code    NONE
แก้ docker-compose NONE   Migration 006       NONE   Apply Migration 005 NONE
Data Migration   NONE   Production Write    NONE   Deploy / Restart   NONE
Commit / Push    NONE   Merge               NONE
```
