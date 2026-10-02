# SUPABASE LIVE VERIFICATION

| | |
|---|---|
| วันที่ตรวจ | 2026-10-02 |
| โปรเจกต์ | `<SUPABASE_PROJECT_REF>` · `https://<SUPABASE_PROJECT_REF>.supabase.co` (ปิดไว้ — ดูหมายเหตุท้ายหัวเอกสาร) |
| ช่องทาง | Supabase MCP (HTTP) — `read_only=true` ตาม `.mcp.json` |
| โหมด | READ-ONLY ตลอดงาน · ไม่มี INSERT / UPDATE / DELETE / DDL / deploy / restart |
| เทียบกับ | `course-advisor-system-mko2/db/migrations/005_web_schema.sql` |

> ที่อยู่ไฟล์: รายงานนี้ถูกสั่งให้เขียนลง `course-advisor-system/docs/`
> แต่ Migration 005 ที่ถูกเทียบอยู่ในรีโปพี่น้อง `course-advisor-system-mko2/`
> ถ้าต้องการให้เอกสารอยู่ข้างไฟล์ที่มันอ้างถึง ต้องย้ายด้วยมือเอง

> หมายเหตุเรื่อง project ref: รีโปนี้เป็น **public** และเอกสารฉบับนี้อธิบายแบบจำลอง
> สิทธิ์ของ production ไว้ครบ (RLS เป็นด่านเดียว · `user_profiles` อ่านได้โดยทุกคนขณะที่
> เก็บ `email`/`full_name` · `anon` เรียก security-definer function ได้ 3 ตัว)
> ค่า project ref จริงจึงถูกแทนด้วย `<SUPABASE_PROJECT_REF>` ก่อน commit
> ตามแนวเดียวกับที่ `SUPABASE_PRE_MIGRATION_AUDIT.md` แทนอีเมลเจ้าของด้วย `<OWNER_EMAIL>`
> ค่าจริงหาได้จาก Supabase Dashboard หรือ `.mcp.json` ของรีโปหน้าเว็บ
> **ไม่มีข้อสรุป ตัวเลข หรือ SQL ใดในเอกสารนี้ถูกเปลี่ยน**

## สิ่งที่ไม่ทำในรอบนี้ (ตามที่สั่ง)

ไม่มี Data Migration · ไม่มี Re-embed · ไม่มี Deploy · ไม่มี Restart ·
ไม่แก้ Schema / Auth / RLS / Storage · ไม่ `git commit` · ไม่ `git push` ·
ไม่สร้าง mapping ระหว่าง `public.courses` กับฝั่ง PostgreSQL · ไม่แก้ข้อมูลแม้แถวเดียว

ทุกคำสั่งที่รันเป็น `SELECT` หรือ MCP read tool · SQL ที่ใช้อยู่ครบในแต่ละหัวข้อ

---

# ส่วนที่ 1 — LIVE VERIFIED

ทุกตัวเลขในส่วนนี้มาจากการรันบนฐานข้อมูลจริง ไม่ใช่การอ่านไฟล์ snapshot

## 1. Row count ของ 7 ตารางที่สั่งตรวจ

```sql
SELECT 'user_profiles' AS t, count(*) AS n FROM public.user_profiles
UNION ALL SELECT 'courses', count(*) FROM public.courses
UNION ALL SELECT 'news', count(*) FROM public.news
UNION ALL SELECT 'ai_settings', count(*) FROM public.ai_settings
UNION ALL SELECT 'rag_documents', count(*) FROM public.rag_documents
UNION ALL SELECT 'knowledge_articles', count(*) FROM public.knowledge_articles
UNION ALL SELECT 'external_news', count(*) FROM public.external_news
ORDER BY t;
```

| ตาราง | จำนวนแถว |
|---|---:|
| `ai_settings` | 1 |
| `courses` | 12 |
| `external_news` | 15 |
| `knowledge_articles` | **0** |
| `news` | 3 |
| `rag_documents` | 12 |
| `user_profiles` | 3 |

ของจริงทั้งฐานคือ **46 แถว** ใน 7 ตาราง เป็นฐานข้อมูลขนาดเล็กมาก
`knowledge_articles` ว่างเปล่า แต่ถังไฟล์ของมันไม่ว่าง — ดูข้อ 7

## 2. ค่าจริงและจำนวนของ `news.status`

```sql
SELECT status, count(*) AS n FROM public.news GROUP BY status ORDER BY n DESC;
```

| status | n |
|---|---:|
| `published` | 3 |

**ค่าที่มีอยู่จริงมีค่าเดียวคือ `published`** ไม่พบ `draft` ไม่พบ `archived`

และต้นทาง **ไม่มี CHECK constraint บน `news.status` เลย** (ยืนยันจากข้อ 5.2)
มีแต่ `DEFAULT 'published'` กับ `NOT NULL` และชนิดเป็น `VARCHAR(20)`

ข้อนี้คือคำตอบของ `PENDING DECISION` ที่ค้างอยู่ในหัวไฟล์ 005 — ดูส่วนที่ 3 ข้อ M1

## 3. `external_news` — slug ที่เป็น NULL และความไม่ซ้ำของ `detail_url`

```sql
SELECT
  count(*) AS total,
  count(*) FILTER (WHERE slug IS NULL) AS slug_null,
  count(*) FILTER (WHERE slug IS NOT NULL) AS slug_not_null,
  count(DISTINCT slug) AS distinct_slug_nonnull,
  count(*) FILTER (WHERE detail_url IS NULL) AS detail_url_null,
  count(DISTINCT detail_url) AS distinct_detail_url,
  count(*) - count(DISTINCT detail_url) AS detail_url_dup_surplus
FROM public.external_news;
```

| metric | ค่า |
|---|---:|
| total | 15 |
| `slug IS NULL` | **0** |
| `slug IS NOT NULL` | 15 |
| distinct slug (ที่ไม่ NULL) | 15 |
| `detail_url IS NULL` | **0** |
| distinct `detail_url` | **15** |
| แถวเกินจากการซ้ำของ `detail_url` | **0** |

`detail_url` ไม่ซ้ำเลยและไม่ NULL เลย · `slug` ก็ไม่ซ้ำและไม่ NULL เลยในข้อมูลชุดนี้
กุญแจที่ 005 เลือก (`detail_url NOT NULL UNIQUE` + `slug` partial unique) ตรงกับของจริง

การกระจายของแหล่งข่าว:

```sql
SELECT source, count(*) AS n, min(published_at) AS earliest, max(published_at) AS latest,
       max(synced_at) AS last_synced,
       count(*) FILTER (WHERE published_at IS NULL) AS published_at_null,
       count(*) FILTER (WHERE facebook_url IS NOT NULL) AS has_facebook_url,
       count(*) FILTER (WHERE image_url IS NULL) AS image_url_null
FROM public.external_news GROUP BY source ORDER BY n DESC;
```

| source | n | published_at ต้นสุด | ท้ายสุด | synced_at ล่าสุด | published_at NULL | มี facebook_url | image_url NULL |
|---|---:|---|---|---|---:|---:|---:|
| `sci_connect` | 15 | 2026-08-04 | 2026-09-15 | **2026-09-22 04:46:47+00** | 0 | 14 | 0 |

## 4. มิติจริงของ `rag_documents.embedding` และจำนวนที่เป็น NULL

ชนิดที่ประกาศไว้ อ่านจาก catalog:

```sql
SELECT a.attname AS column_name,
       format_type(a.atttypid, a.atttypmod) AS declared_type,
       a.atttypmod AS typmod_dim
FROM pg_attribute a
JOIN pg_class c ON c.oid = a.attrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relname = 'rag_documents'
  AND a.attnum > 0 AND NOT a.attisdropped
ORDER BY a.attnum;
```

→ `embedding` คือ **`vector(768)`** (`atttypmod = 768`)

มิติของค่าที่เก็บอยู่จริง ไม่ใช่แค่ที่ประกาศ:

```sql
SELECT count(*) AS total_rows,
       count(embedding) AS embedding_not_null,
       count(*) - count(embedding) AS embedding_null,
       min(vector_dims(embedding)) AS min_dims,
       max(vector_dims(embedding)) AS max_dims,
       count(DISTINCT vector_dims(embedding)) AS distinct_dims
FROM public.rag_documents;
```

| metric | ค่า |
|---|---:|
| total_rows | 12 |
| `embedding` ไม่ NULL | **12** |
| `embedding` เป็น NULL | **0** |
| min / max dims | **768 / 768** |
| จำนวนมิติที่พบ (distinct) | **1** |

ไม่มีแถวที่ embedding หาย และทุกแถวเป็น 768 มิติเท่ากันหมด ไม่มีแถวมิติเพี้ยน

การกระจายของแหล่งที่มา:

```sql
SELECT r.source_type, count(*) AS n, count(DISTINCT r.source_id) AS distinct_source_id,
       count(*) FILTER (WHERE r.source_id IS NULL) AS source_id_null,
       count(*) FILTER (WHERE r.source_type='major' AND NOT EXISTS
            (SELECT 1 FROM public.courses c WHERE c.id = r.source_id)) AS orphan_vs_courses,
       max(r.chunk_index) AS max_chunk_index
FROM public.rag_documents r GROUP BY r.source_type ORDER BY r.source_type;
```

| source_type | n | distinct source_id | source_id NULL | orphan เทียบ courses | max chunk_index |
|---|---:|---:|---:|---:|---:|
| `major` | 12 | 12 | 0 | **0** | **0** |

ใช้ `source_type` แค่ค่าเดียวจากสี่ค่าที่ CHECK อนุญาต · 1 หลักสูตร = 1 chunk พอดี
ไม่มีการแบ่งย่อย · ไม่มี chunk กำพร้า — ทั้ง 12 ชี้ไปหลักสูตรที่มีอยู่จริงครบ

ส่วนขยายที่เกี่ยวข้อง (จาก MCP `list_extensions`): `vector 0.8.2` ติดตั้งอยู่ **ใน schema `public`**
ที่ติดตั้งอยู่จริงทั้งหมดมี 8 ตัว — `pgcrypto 1.3`, `vector 0.8.2`, `pg_stat_statements 1.11`,
`pg_net 0.20.4`, `supabase_vault 0.3.1`, `uuid-ossp 1.1`, `pg_cron 1.6.4`, `plpgsql 1.0`

## 5. Live schema — columns, constraints, indexes, triggers

### 5.1 Columns

```sql
SELECT table_name, ordinal_position AS pos, column_name, data_type,
       character_maximum_length AS maxlen, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = 'public'
ORDER BY table_name, ordinal_position;
```

**`public.courses`** — `ordinal_position` ข้าม 6 และ 8 (คอลัมน์ที่ถูก DROP ไปแล้ว)

| pos | column | type | null? | default |
|---:|---|---|---|---|
| 1 | `id` | uuid | NO | `gen_random_uuid()` |
| 2 | `title` | varchar(255) | NO | — |
| 3 | `title_en` | varchar(255) | **NO** | — |
| 4 | `description` | text | **NO** | — |
| 5 | **`logo`** | text | YES | — |
| 7 | `careers` | text[] | YES | — |
| 9 | `created_at` | timestamptz | YES | `now()` |
| 10 | `updated_at` | timestamptz | YES | `now()` |
| 11 | `created_by` | uuid | YES | **`auth.uid()`** |
| 12 | `updated_by` | uuid | YES | — |
| 13 | `detail` | jsonb | YES | — |

**ไม่มีคอลัมน์ `is_published`** และ **ไม่มีคอลัมน์ `category`** ·
ชื่อคอลัมน์โลโก้คือ `logo` ไม่ใช่ `logo_url`

**`public.news`**

| pos | column | type | null? | default |
|---:|---|---|---|---|
| 1 | `id` | uuid | NO | `gen_random_uuid()` |
| 2 | `title` | **varchar(500)** | NO | — |
| 3 | `description` | text | **NO** | — |
| 4 | `category` | varchar(100) | **NO** | — |
| 5 | **`date`** | date | **NO** | — |
| 6 | **`image`** | text | YES | — |
| 7 | `created_at` | timestamptz | YES | `now()` |
| 8 | `updated_at` | timestamptz | YES | `now()` |
| 9 | `created_by` | uuid | YES | **`auth.uid()`** |
| 10 | `updated_by` | uuid | YES | — |
| 11 | `status` | **varchar(20)** | NO | `'published'` |

ชื่อคอลัมน์วันที่คือ `date` ไม่ใช่ `published_on` · ชื่อคอลัมน์รูปคือ `image` ไม่ใช่ `image_url`

**`public.external_news`**

| pos | column | type | null? | default |
|---:|---|---|---|---|
| 1 | `id` | uuid | NO | `gen_random_uuid()` |
| 2 | `title` | **varchar(500)** | NO | — |
| 3 | `description` | text | YES | — |
| 4 | `image_url` | text | YES | — |
| 5 | `detail_url` | text | **NO** | — |
| 6 | `published_at` | timestamptz | YES | — |
| 7 | `published_text` | **varchar(100)** | YES | — |
| 8 | `source` | varchar(100) | **NO** | — |
| 9 | `synced_at` | timestamptz | **YES** | `now()` |
| 10 | `created_at` | timestamptz | **YES** | `now()` |
| 11 | `slug` | varchar(255) | **YES** | — |
| 12 | `facebook_url` | text | YES | — |

**`public.knowledge_articles`**

| pos | column | type | null? | default |
|---:|---|---|---|---|
| 1 | `id` | uuid | NO | `gen_random_uuid()` |
| 2 | `title` | **varchar(500)** | NO | — |
| 3 | `content` | text | **NO** | — |
| 4 | `created_at` | timestamptz | YES | `now()` |
| 5 | `updated_at` | timestamptz | YES | `now()` |
| 6 | `created_by` | uuid | YES | — |
| 7 | `updated_by` | uuid | YES | — |
| 8 | `file_path` | text | YES | — |
| 9 | `file_name` | text | YES | — |
| 10 | `file_size` | bigint | YES | — |

**`public.ai_settings`**

| pos | column | type | null? | default |
|---:|---|---|---|---|
| 1 | `id` | **integer** | NO | `1` |
| 2 | `model` | varchar(255) | NO | — |
| 3 | `updated_at` | timestamptz | YES | `now()` |
| 4 | `updated_by` | uuid | YES | — |

**`public.user_profiles`**

| pos | column | type | null? | default |
|---:|---|---|---|---|
| 1 | `id` | uuid | NO | `gen_random_uuid()` |
| 2 | `user_id` | uuid | YES | — |
| 3 | `role` | varchar(50) | YES | `'user'` |
| 4 | `full_name` | varchar(255) | YES | — |
| 5 | `created_at` | timestamptz | YES | `now()` |
| 6 | `updated_at` | timestamptz | YES | `now()` |
| 7 | `email` | text | YES | — |
| 8 | `status` | varchar(20) | NO | `'approved'` |

**`public.rag_documents`**

| pos | column | type | null? | default |
|---:|---|---|---|---|
| 1 | `id` | uuid | NO | `gen_random_uuid()` |
| 2 | `source_type` | varchar(20) | NO | — |
| 3 | `source_id` | uuid | YES | — |
| 4 | `title` | varchar(500) | NO | — |
| 5 | `content` | text | NO | — |
| 6 | `chunk_index` | integer | NO | `0` |
| 7 | `embedding` | **vector(768)** | YES | — |
| 8 | `created_at` | timestamptz | YES | `now()` |
| 9 | `updated_at` | timestamptz | YES | `now()` |

### 5.2 Constraints

```sql
SELECT n.nspname AS schema, rel.relname AS table_name, con.conname AS constraint_name,
       CASE con.contype WHEN 'p' THEN 'PRIMARY KEY' WHEN 'u' THEN 'UNIQUE'
            WHEN 'f' THEN 'FOREIGN KEY' WHEN 'c' THEN 'CHECK' ELSE con.contype::text END AS kind,
       pg_get_constraintdef(con.oid) AS definition
FROM pg_constraint con
JOIN pg_class rel ON rel.oid = con.conrelid
JOIN pg_namespace n ON n.oid = rel.relnamespace
WHERE n.nspname = 'public'
ORDER BY rel.relname, con.contype, con.conname;
```

รวม **21 constraint**: PK 7 · UNIQUE 4 · FK 7 · CHECK 2

| ตาราง | ชนิด | นิยาม |
|---|---|---|
| `ai_settings` | CHECK | `ai_settings_singleton` → `CHECK (id = 1)` |
| `ai_settings` | FK | `updated_by` → `auth.users(id)` |
| `ai_settings` | PK | `(id)` |
| `courses` | FK | `created_by` → **`auth.users(id)`** |
| `courses` | FK | `updated_by` → **`user_profiles(user_id)`** `ON DELETE SET NULL` |
| `courses` | PK | `(id)` |
| `external_news` | PK | `(id)` |
| `external_news` | UNIQUE | `external_news_detail_url_key` → `UNIQUE (detail_url)` |
| `knowledge_articles` | FK | `created_by` → `auth.users(id)` |
| `knowledge_articles` | FK | `updated_by` → `auth.users(id)` |
| `knowledge_articles` | PK | `(id)` |
| `news` | FK | `created_by` → **`auth.users(id)`** |
| `news` | FK | `updated_by` → **`user_profiles(user_id)`** `ON DELETE SET NULL` |
| `news` | PK | `(id)` |
| `rag_documents` | CHECK | `source_type IN ('major','news','article','knowledge')` |
| `rag_documents` | PK | `(id)` |
| `rag_documents` | UNIQUE | `(source_type, source_id, chunk_index)` |
| `user_profiles` | FK | `user_id` → **`user_profiles(user_id)`** ← ชี้กลับตัวเอง ดูข้อ A1 |
| `user_profiles` | PK | `(id)` |
| `user_profiles` | UNIQUE | `user_profiles_user_id_key` → `UNIQUE (user_id)` |
| `user_profiles` | UNIQUE | `user_profiles_user_id_unique` → `UNIQUE (user_id)` ← ซ้ำกับอันบน ดูข้อ A2 |

**ยืนยันชัดเจน: `public.news` ไม่มี CHECK บน `status`** — มี CHECK แค่ 2 ตัวในฐานทั้งหมด
คือ `ai_settings_singleton` และ `rag_documents_source_type_check`

### 5.3 Indexes

```sql
SELECT schemaname, tablename, indexname, indexdef
FROM pg_indexes WHERE schemaname = 'public' ORDER BY tablename, indexname;
```

รวม **24 index**

| ตาราง | index | นิยาม |
|---|---|---|
| `ai_settings` | `ai_settings_pkey` | UNIQUE btree (id) |
| `courses` | `courses_pkey` | UNIQUE btree (id) |
| `courses` | `idx_courses_created_at` | btree (created_at DESC) |
| `external_news` | `external_news_pkey` | UNIQUE btree (id) |
| `external_news` | `external_news_detail_url_key` | UNIQUE btree (detail_url) |
| `external_news` | `idx_external_news_published_at` | btree (published_at DESC) |
| `external_news` | `idx_external_news_slug` | **UNIQUE btree (slug) WHERE slug IS NOT NULL** |
| `external_news` | `idx_external_news_source` | btree (source) |
| `knowledge_articles` | `knowledge_articles_pkey` | UNIQUE btree (id) |
| `knowledge_articles` | `idx_knowledge_articles_created_at` | btree (created_at DESC) |
| `news` | `news_pkey` | UNIQUE btree (id) |
| `news` | `idx_news_category` | btree (category) |
| `news` | `idx_news_created_at` | btree (created_at DESC) |
| `news` | `idx_news_date` | btree (date DESC) |
| `news` | `idx_news_status` | btree (status) |
| `rag_documents` | `rag_documents_pkey` | UNIQUE btree (id) |
| `rag_documents` | `rag_documents_source_type_source_id_chunk_index_key` | UNIQUE btree (source_type, source_id, chunk_index) |
| `rag_documents` | `idx_rag_documents_embedding` | **ivfflat (embedding vector_cosine_ops) WITH (lists='100')** |
| `rag_documents` | `idx_rag_documents_source` | btree (source_type, source_id) |
| `user_profiles` | `user_profiles_pkey` | UNIQUE btree (id) |
| `user_profiles` | `user_profiles_user_id_key` | UNIQUE btree (user_id) |
| `user_profiles` | `user_profiles_user_id_unique` | UNIQUE btree (user_id) ← ซ้ำ |
| `user_profiles` | `idx_user_profiles_role` | btree (role) |
| `user_profiles` | `idx_user_profiles_status` | btree (status) |
| `user_profiles` | `idx_user_profiles_user_id` | btree (user_id) |

`idx_external_news_slug` เป็น partial unique index แบบเดียวกับที่ 005 เขียนไว้เป๊ะ ·
`ivfflat lists=100` บนข้อมูล 12 แถวคือค่าที่ตั้งไว้สำหรับชุดข้อมูลใหญ่กว่านี้มาก (ไม่กระทบความถูกต้อง)

### 5.4 Triggers

```sql
SELECT c.relname AS table_name, t.tgname AS trigger_name, t.tgenabled::text AS tgenabled,
       pg_get_triggerdef(t.oid) AS definition
FROM pg_trigger t
JOIN pg_class c ON c.oid = t.tgrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname IN ('public','auth') AND NOT t.tgisinternal
ORDER BY n.nspname, c.relname, t.tgname;
```

เปิดใช้งานอยู่ทั้ง 6 ตัว (`tgenabled = 'O'`)

| ตาราง | trigger | เมื่อไร | ฟังก์ชัน |
|---|---|---|---|
| `auth.users` | `on_auth_user_created` | AFTER INSERT | `handle_new_user()` |
| `public.courses` | `update_courses_updated_at` | BEFORE UPDATE | `update_updated_at_column()` |
| `public.knowledge_articles` | `update_knowledge_articles_updated_at` | BEFORE UPDATE | `update_updated_at_column()` |
| `public.news` | `update_news_updated_at` | BEFORE UPDATE | `update_updated_at_column()` |
| `public.user_profiles` | `guard_user_profile_privileges_trigger` | BEFORE UPDATE | `guard_user_profile_privileges()` |
| `public.user_profiles` | `update_user_profiles_updated_at` | BEFORE UPDATE | `update_updated_at_column()` |

`external_news`, `rag_documents`, `ai_settings` **ไม่มี trigger** — `rag_documents.updated_at`
มีคอลัมน์อยู่แต่ไม่มีอะไรอัปเดตให้

### 5.5 Migration history ฝั่ง Supabase

```
MCP: list_migrations
```

| version | name |
|---|---|
| `20260904162441` | `drop_course_category_detail` |
| `20260904165800` | `restore_course_detail` |
| `20260904170950` | `course_assets_bucket` |

นี่อธิบายช่องว่าง `ordinal_position` 6 และ 8 ใน `courses`: `category` กับ `detail` ถูก DROP
แล้ว `detail` ถูกเพิ่มกลับ (ไปอยู่ pos 13) ส่วน **`category` ไม่ถูกเพิ่มกลับ** จึงไม่มีอยู่แล้ว

## 6. RLS และ policies ที่ใช้งานจริง

```sql
SELECT c.relname AS table_name, c.relrowsecurity AS rls_enabled,
       c.relforcerowsecurity AS rls_forced,
       (SELECT count(*) FROM pg_policies p
         WHERE p.schemaname='public' AND p.tablename=c.relname) AS policy_count
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='public' AND c.relkind='r' ORDER BY c.relname;
```

**RLS เปิดครบทั้ง 7 ตาราง** · ไม่มีตารางใดตั้ง FORCE ROW SECURITY

| ตาราง | RLS | FORCE | จำนวน policy |
|---|---|---|---:|
| `ai_settings` | เปิด | ไม่ | 2 |
| `courses` | เปิด | ไม่ | 4 |
| `external_news` | เปิด | ไม่ | 4 |
| `knowledge_articles` | เปิด | ไม่ | 4 |
| `news` | เปิด | ไม่ | **5** |
| `rag_documents` | เปิด | ไม่ | 2 |
| `user_profiles` | เปิด | ไม่ | 3 |

```sql
SELECT tablename, policyname, permissive, roles::text AS roles, cmd, qual, with_check
FROM pg_policies WHERE schemaname='public' ORDER BY tablename, cmd, policyname;
```

รวม **24 policy** · ทุก policy เป็น `PERMISSIVE` และผูกกับ role `{public}` ทั้งหมด
(ไม่มี policy ใดจำกัดเฉพาะ `authenticated` หรือ `anon` ที่ชั้น role — การแยกสิทธิ์
ทำผ่านเงื่อนไข `auth.uid()` ใน `USING`/`WITH CHECK` ทั้งหมด)

แม่แบบที่ใช้ซ้ำทั้งระบบ — สิทธิ์ทุกอย่างตัดสินจาก `user_profiles.role`:

```sql
EXISTS (SELECT 1 FROM user_profiles
        WHERE user_profiles.user_id = auth.uid()
          AND user_profiles.role IN ('admin','editor'))   -- insert / update
EXISTS (... AND user_profiles.role = 'admin')             -- delete
```

| ตาราง | cmd | policy | เงื่อนไขย่อ |
|---|---|---|---|
| `ai_settings` | SELECT | AI settings are viewable by everyone | `true` |
| `ai_settings` | UPDATE | Admins can update AI settings | role = admin |
| `courses` | SELECT | Courses are viewable by everyone | `true` |
| `courses` | INSERT | Admins and editors can insert courses | role in (admin, editor) |
| `courses` | UPDATE | Admins and editors can update courses | role in (admin, editor) |
| `courses` | DELETE | Admins can delete courses | role = admin |
| `external_news` | SELECT | External news are viewable by everyone | `true` |
| `external_news` | INSERT | Admins and editors can insert external news | role in (admin, editor) |
| `external_news` | UPDATE | Admins and editors can update external news | role in (admin, editor) |
| `external_news` | DELETE | Admins can delete external news | role = admin |
| `knowledge_articles` | SELECT | Admins and editors can view knowledge articles | role in (admin, editor) ← **ไม่เปิดสาธารณะ** |
| `knowledge_articles` | INSERT | Admins and editors can insert knowledge articles | role in (admin, editor) |
| `knowledge_articles` | UPDATE | Admins and editors can update knowledge articles | role in (admin, editor) |
| `knowledge_articles` | DELETE | Admins can delete knowledge articles | role = admin |
| `news` | SELECT | Published news are viewable by everyone | `status = 'published'` |
| `news` | SELECT | Admins and editors can view all news | role in (admin, editor) |
| `news` | INSERT | Admins and editors can insert news | role in (admin, editor) |
| `news` | UPDATE | Admins and editors can update news | role in (admin, editor) |
| `news` | DELETE | Admins can delete news | role = admin |
| `rag_documents` | SELECT | RAG documents are viewable by everyone | `true` |
| `rag_documents` | ALL | Admins and editors can manage RAG documents | role in (admin, editor) |
| `user_profiles` | SELECT | Public profiles are viewable by everyone | `true` |
| `user_profiles` | UPDATE | Users can update own profile | `auth.uid() = user_id` |
| `user_profiles` | UPDATE | Approved admins can update any profile | role = admin **AND status = approved** |

จุดที่ต้องรู้เวลาย้าย: `news` ใช้ `status` เป็นตัวตัดสินสิทธิ์อ่านของคนทั่วไปโดยตรง
(`USING (status = 'published')`) คอลัมน์นี้จึงไม่ใช่แค่ธงแสดงผล มันคือขอบเขตความปลอดภัย

`user_profiles` ถูกอ่านได้โดยทุกคน (`qual = true`) ขณะที่เก็บ `email` และ `full_name` —
ไม่ใช่ขอบเขตของงานนี้ แต่บันทึกไว้เพราะกระทบการตัดสินใจเรื่อง auth ในขั้นต่อไป

### 6.1 Security advisors ที่ Supabase รายงานเอง

```
MCP: get_advisors(type = "security")
```

ทั้งหมดระดับ `WARN` ไม่มี `ERROR`:

| lint | count | รายละเอียด |
|---|---:|---|
| `function_search_path_mutable` | 4 | `update_updated_at_column`, `handle_new_user`, `match_rag_documents`, `guard_user_profile_privileges` |
| `extension_in_public` | 1 | `vector` ติดตั้งใน `public` |
| `anon_security_definer_function_executable` | 3 | `guard_user_profile_privileges()`, `handle_new_user()`, `rls_auto_enable()` เรียกได้โดย `anon` ผ่าน `/rest/v1/rpc/...` |
| `authenticated_security_definer_function_executable` | 3 | สามฟังก์ชันเดิม เรียกได้โดย `authenticated` |
| `auth_leaked_password_protection` | 1 | ปิดอยู่ |

ลิงก์วิธีแก้:
- https://supabase.com/docs/guides/database/database-linter?lint=0011_function_search_path_mutable
- https://supabase.com/docs/guides/database/database-linter?lint=0014_extension_in_public
- https://supabase.com/docs/guides/database/database-linter?lint=0028_anon_security_definer_function_executable
- https://supabase.com/docs/guides/database/database-linter?lint=0029_authenticated_security_definer_function_executable
- https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection

หมายเหตุ: มีฟังก์ชัน `public.match_rag_documents` และ `public.rls_auto_enable` อยู่ในฐานข้อมูล
ซึ่งไม่ได้อยู่ในรายการที่สั่งตรวจ และ Migration 005 ไม่ได้สร้างอะไรแทนมัน

## 7. Storage buckets · จำนวน objects · ขนาดรวม

```sql
SELECT b.id AS bucket_id, b.name, b.public, b.file_size_limit,
       b.allowed_mime_types::text, b.created_at,
       count(o.id) AS object_count,
       COALESCE(sum((o.metadata->>'size')::bigint), 0) AS total_bytes,
       ROUND(COALESCE(sum((o.metadata->>'size')::bigint), 0) / 1024.0, 1) AS total_kib
FROM storage.buckets b
LEFT JOIN storage.objects o ON o.bucket_id = b.id
GROUP BY b.id, b.name, b.public, b.file_size_limit, b.allowed_mime_types, b.created_at
ORDER BY b.id;
```

| bucket | public | objects | ขนาดรวม | file_size_limit | allowed_mime_types | created_at |
|---|---|---:|---:|---|---|---|
| `course-assets` | **true** | 1 | 663,449 B (647.9 KiB) | ไม่จำกัด | ไม่จำกัด | 2026-09-04 17:09:50+00 |
| `knowledge-files` | false | 4 | 10,864,464 B (10,609.8 KiB ~ 10.4 MiB) | ไม่จำกัด | ไม่จำกัด | 2026-08-29 06:57:23+00 |

รวม **2 bucket · 5 object · 11,527,913 B ~ 11.0 MiB**

```sql
SELECT o.bucket_id, o.name, (o.metadata->>'size')::bigint AS size_bytes,
       o.metadata->>'mimetype' AS mimetype, o.created_at, (o.owner IS NOT NULL) AS has_owner
FROM storage.objects o ORDER BY o.bucket_id, o.name;
```

| bucket | object | ขนาด | mimetype | created_at |
|---|---|---:|---|---|
| `course-assets` | `faculty/3fe27ab3-...-ba0118c3eceb.png` | 663,449 | image/png | 2026-09-05 04:17:09+00 |
| `knowledge-files` | `1f6796fe-...-f21e25d6f2ba.pdf` | 6,227,431 | application/pdf | 2026-08-29 15:14:30+00 |
| `knowledge-files` | `52d9418c-...-1cd66332a45c.pdf` | 4,451,468 | application/pdf | 2026-09-16 09:32:47+00 |
| `knowledge-files` | `9ec81c31-...-083f9ff8f41b.pdf` | 71,200 | application/pdf | 2026-08-29 06:59:02+00 |
| `knowledge-files` | `f2900223-...-12878fe69f0f.pdf` | 114,365 | application/pdf | 2026-08-29 15:15:06+00 |

ทุก object มี `owner` ครบ

**ข้อที่ต้องสังเกต: `knowledge-files` มี PDF 4 ไฟล์ (10.4 MiB) แต่ `public.knowledge_articles`
มี 0 แถว** ไฟล์ทั้งสี่จึงไม่มีแถวใดในฐานข้อมูลชี้ถึง — เป็นไฟล์กำพร้า ดูส่วนที่ 3 ข้อ M7

### 7.1 Storage policies

```sql
SELECT tablename, policyname, roles::text AS roles, cmd, qual, with_check
FROM pg_policies WHERE schemaname='storage' ORDER BY tablename, cmd, policyname;
```

8 policy ทั้งหมดอยู่บน `storage.objects` · ใช้แม่แบบ `user_profiles.role` ตัวเดียวกับฝั่งตาราง

| cmd | policy | bucket | เงื่อนไข |
|---|---|---|---|
| SELECT | Course assets are viewable by everyone | `course-assets` | ไม่มีเงื่อนไขผู้ใช้ |
| SELECT | Admins and editors can view knowledge files | `knowledge-files` | role in (admin, editor) |
| INSERT | Admins and editors can upload course assets | `course-assets` | role in (admin, editor) |
| INSERT | Admins and editors can upload knowledge files | `knowledge-files` | role in (admin, editor) |
| UPDATE | Admins and editors can update course assets | `course-assets` | role in (admin, editor) |
| UPDATE | Admins and editors can update knowledge files | `knowledge-files` | role in (admin, editor) |
| DELETE | Admins and editors can delete course assets | `course-assets` | role in (admin, editor) |
| DELETE | Admins and editors can delete knowledge files | `knowledge-files` | role in (admin, editor) |

ไม่มี policy บน `storage.buckets` — การสร้าง/ลบ bucket ทำได้เฉพาะ service role

## 8. Edge Functions ที่ deploy อยู่จริง

```
MCP: list_edge_functions
```

| slug | status | version | verify_jwt | import_map |
|---|---|---:|---|---|
| `sync-sci-news` | **ACTIVE** | 1 | **true** | false |

- id: `e33c15af-398e-4e3f-964c-87d8d4dbbbca`
- created / updated: `1788537434443` (epoch ms, ทั้งสองค่าเท่ากัน → ยังไม่เคย redeploy)
- entrypoint: `source/index.ts`
- `ezbr_sha256`: `c7c5a406e88514684093c6e113f4d032566c823c5de85de5955f4435c48ea260`

**มี Edge Function อยู่ฟังก์ชันเดียว** และมันคือตัวดึงข่าว SCI Connect ที่เขียนลง `external_news`

### 8.1 ตัวตั้งเวลาที่เรียกมัน (pg_cron)

```sql
SELECT jobid, jobname, schedule, active, database, username,
       length(command) AS command_len,
       (command ILIKE '%bearer%' OR command ILIKE '%key%' OR command ILIKE '%token%')
         AS command_may_contain_secret
FROM cron.job ORDER BY jobid;
```

| jobid | jobname | schedule | active | database | username | command_len | อาจมี secret |
|---:|---|---|---|---|---|---:|---|
| 1 | `sync-sci-news-every-30-min` | `*/30 * * * *` | **true** | postgres | postgres | 405 | **true** |

**ไม่ได้อ่านเนื้อ `command` และไม่นำมาแสดง** เพราะตรวจพบว่ามีคำที่บ่งชี้ token/key อยู่ข้างใน
ซึ่งอยู่ในขอบเขตที่สั่งห้ามเปิดเผย · รายงานเฉพาะว่า job นี้มีอยู่ เปิดใช้งาน และยิงทุก 30 นาที

ตัวเลขที่ชนกันเองและต้องอธิบาย: cron เปิดอยู่ยิงทุก 30 นาที แต่ `max(synced_at)`
ของ `external_news` คือ **2026-09-22** ซึ่งห่างจากวันตรวจ (2026-10-02) ประมาณ **10 วัน**
→ ดูส่วนที่ 2 ข้อ U3 ตีความไม่ได้ด้วยข้อมูลที่มี

## 9. Auth metadata (เฉพาะตัวเลขรวม — ไม่มี email / hash / token / secret)

```sql
SELECT count(*) AS users_total,
       count(*) FILTER (WHERE email_confirmed_at IS NOT NULL) AS email_confirmed,
       count(*) FILTER (WHERE email_confirmed_at IS NULL) AS email_unconfirmed,
       count(*) FILTER (WHERE banned_until IS NOT NULL AND banned_until > now()) AS banned_now,
       count(*) FILTER (WHERE deleted_at IS NOT NULL) AS soft_deleted,
       count(*) FILTER (WHERE last_sign_in_at IS NOT NULL) AS has_signed_in,
       count(DISTINCT role) AS distinct_auth_roles,
       count(*) FILTER (WHERE is_sso_user) AS sso_users,
       count(*) FILTER (WHERE is_anonymous) AS anonymous_users
FROM auth.users;
```

| metric | ค่า |
|---|---:|
| users ทั้งหมด | **3** |
| ยืนยันอีเมลแล้ว | **3** |
| ยังไม่ยืนยันอีเมล | 0 |
| ถูกแบนอยู่ตอนนี้ | 0 |
| soft deleted | 0 |
| เคยเข้าสู่ระบบ | 3 |
| จำนวน auth role ที่ต่างกัน | 1 |
| SSO users | 0 |
| anonymous users | 0 |

role / status ฝั่งแอป (ไม่มี email ไม่มีชื่อ):

```sql
SELECT role, status, count(*) AS n,
       count(*) FILTER (WHERE user_id IS NULL) AS user_id_null
FROM public.user_profiles GROUP BY role, status ORDER BY role, status;
```

| role | status | n | `user_id` NULL |
|---|---|---:|---:|
| `admin` | `approved` | **2** | 0 |
| `user` | `approved` | **1** | 0 |

ไม่พบ `editor` แม้ว่า policy ครึ่งระบบจะอ้างถึง role นี้ · ไม่พบ status ที่ไม่ใช่ `approved`

ความเชื่อมโยงระหว่าง auth กับ profile และผู้เขียนเนื้อหา:

```sql
SELECT
  (SELECT count(*) FROM public.user_profiles p
     JOIN auth.users u ON u.id = p.user_id) AS profiles_matching_auth_user,
  (SELECT count(*) FROM public.user_profiles p
     WHERE NOT EXISTS (SELECT 1 FROM auth.users u WHERE u.id = p.user_id)) AS profiles_orphan,
  (SELECT count(*) FROM auth.users u
     WHERE NOT EXISTS (SELECT 1 FROM public.user_profiles p WHERE p.user_id = u.id)) AS auth_users_without_profile,
  (SELECT count(DISTINCT created_by) FROM public.courses) AS courses_distinct_created_by,
  (SELECT count(DISTINCT updated_by) FROM public.courses) AS courses_distinct_updated_by,
  (SELECT count(DISTINCT created_by) FROM public.news) AS news_distinct_created_by,
  (SELECT count(*) FROM public.courses c
     WHERE NOT EXISTS (SELECT 1 FROM auth.users u WHERE u.id = c.created_by)) AS courses_created_by_orphan;
```

| metric | ค่า |
|---|---:|
| profile ที่จับคู่ auth user ได้ | **3 / 3** |
| profile กำพร้า | 0 |
| auth user ที่ไม่มี profile | 0 |
| `courses.created_by` ที่ต่างกัน | **1** |
| `courses.updated_by` ที่ต่างกัน | **1** |
| `news.created_by` ที่ต่างกัน | **1** |
| `courses.created_by` ที่ชี้ไปผู้ใช้ที่ไม่มีอยู่ | **0** |

เนื้อหาทั้งหมดในฐานนี้สร้างโดยบัญชีเดียว · ไม่มี FK ค้าง

## 10. `courses` — ของจริงทั้ง 12 แถว (ไว้เทียบกับ PostgreSQL ภายหลัง)

**ไม่มีการสร้าง mapping และไม่แก้ข้อมูล** — บันทึกสภาพปัจจุบันไว้เป็นหลักฐานเท่านั้น

```sql
SELECT id, title, title_en, length(description) AS description_len,
       (logo IS NOT NULL) AS has_logo,
       COALESCE(array_length(careers,1),0) AS careers_count,
       (detail IS NOT NULL) AS has_detail,
       CASE WHEN detail IS NULL THEN 0
            ELSE (SELECT count(*) FROM jsonb_object_keys(detail)) END AS detail_keys,
       created_at, updated_at
FROM public.courses ORDER BY title;
```

| id | title | title_en | desc_len | logo | careers | detail keys |
|---|---|---|---:|:---:|---:|---:|
| `a3fafaf6-98b7-4b16-9820-b317f2df092f` | การจัดการสิ่งแวดล้อมและทรัพยากรธรรมชาติ | Environmental and Natural Resource Management | 354 | มี | 0 | 0 |
| `61dab43c-3bff-44ef-985a-efde94ba24c1` | การแพทย์แผนไทยประยุกต์ | Applied Thai Traditional Medicine | 220 | มี | 0 | 0 |
| `3b104f6a-7d4b-4ec3-9b0b-c71316c78c37` | คณิตศาสตร์ | Mathematics | 183 | มี | 0 | 0 |
| `f1ba7709-2c8b-489a-ad6a-8c9ea10e5c5b` | คอมพิวเตอร์แอนิเมชันและมัลติมีเดีย | Computer Animation and Multimedia | 663 | มี | 0 | 0 |
| `eb3812e5-24ee-42f9-9448-bc538deb207f` | เทคโนโลยีการเกษตรสมัยใหม่ | Modern Agricultural Technology | 231 | มี | 0 | 0 |
| `3aaea8f8-977f-4341-bdc1-7a0827f3ecb3` | เทคโนโลยีผลิตภัณฑ์ชีวภาพกับการประกอบธุรกิจ | Bioproduct Technology and Business Entrepreneurship | 570 | มี | 0 | 0 |
| `3a6e8085-6bcd-45a7-a6c5-5d6d0206dcd7` | เทคโนโลยีสารสนเทศ | **Bachelor of Science** | 294 | มี | 0 | 0 |
| `20c3ca9c-ff08-4e0a-8685-f782fafdc580` | วิทยาการคอมพิวเตอร์ | Computer Science | 661 | มี | 0 | **5** |
| `3ba89209-e915-4271-be19-36837a292d39` | วิทยาศาสตร์เครื่องสำอาง | Cosmetic Science | 782 | มี | 0 | 0 |
| `1bda2d03-402a-4f64-b5b7-1291a9ea9cf7` | สาขาวิชาการประกอบอาหารและการบริการอาหาร | Culinary Arts and Service | 187 | มี | 0 | 0 |
| `7a7e017a-e1bc-4722-bf88-6d070e3a09f5` | สาขาวิชาเทคโนโลยีอาหารและความเป็นผู้ประกอบการสมัยใหม่ | Food Technology and Modern Entrepreneurship | 371 | มี | 0 | 0 |
| `b64e613b-f14a-4bfd-8bf3-c047848dfeb2` | สาขาวิชาสาธารณสุขศาสตร์ | Bachelor of Public Health Program in Public Health | 559 | มี | 0 | 0 |

สรุปเชิงรวม:

```sql
SELECT count(*) AS total,
       count(*) FILTER (WHERE careers IS NULL) AS careers_null,
       count(*) FILTER (WHERE careers = '{}') AS careers_empty_array,
       count(*) FILTER (WHERE detail IS NULL) AS detail_null,
       count(*) FILTER (WHERE logo IS NULL) AS logo_null,
       count(*) FILTER (WHERE created_by IS NULL) AS created_by_null,
       count(*) FILTER (WHERE updated_by IS NULL) AS updated_by_null,
       count(DISTINCT title) AS distinct_title,
       count(DISTINCT title_en) AS distinct_title_en
FROM public.courses;
```

| metric | ค่า |
|---|---:|
| total | 12 |
| `careers IS NULL` | **0** |
| `careers = '{}'` (array ว่าง) | **12** |
| `detail IS NULL` | **11** |
| `logo IS NULL` | 0 |
| `created_by IS NULL` | 0 |
| `updated_by IS NULL` | 0 |
| `title` ที่ไม่ซ้ำ | 12 / 12 |
| `title_en` ที่ไม่ซ้ำ | 12 / 12 |

สามข้อที่ต้องจำไปใช้ตอนทำ mapping รอบหน้า:
1. **`careers` ว่างทั้ง 12 แถว** เป็น array ว่าง ไม่ใช่ NULL — ข้อมูลอาชีพที่ UI แสดงไม่ได้มาจากคอลัมน์นี้
2. **`detail` มีข้อมูลแค่ 1 ใน 12 แถว** (วิทยาการคอมพิวเตอร์ 5 คีย์) อีก 11 แถวเป็น NULL
3. **`title` ไม่ซ้ำกันเลยทั้ง 12** จึงพอใช้เป็นกุญแจชั่วคราวในการเทียบได้ แต่ `title_en` ของ
   "เทคโนโลยีสารสนเทศ" คือ `Bachelor of Science` ซึ่งเป็นชื่อปริญญา ไม่ใช่ชื่อสาขา —
   **อย่าใช้ `title_en` เป็นกุญแจจับคู่**

ข้อมูลเสริมที่ตรวจไปด้วยเพราะเกี่ยวกับการย้าย:

```sql
SELECT status, category, date, length(title) AS title_len, (image IS NOT NULL) AS has_image,
       created_at, updated_at, (created_by IS NOT NULL) AS has_created_by,
       (updated_by IS NOT NULL) AS has_updated_by
FROM public.news ORDER BY date DESC;
```

`news` ทั้ง 3 แถว: `published` ทั้งหมด · category = ข่าวรับสมัคร / กิจกรรม / ทุนการศึกษา ·
`date` = 2024-01-15 / 2024-01-10 / 2024-01-05 · มีรูปครบ · มี `created_by` และ `updated_by` ครบ ·
`created_at` = 2026-08-25 ทั้งสามแถว
**(วันที่ในคอลัมน์ `date` เป็นปี 2024 แต่แถวถูกสร้างปี 2026 — ดู U4)**

```sql
SELECT id, model, updated_at, (updated_by IS NOT NULL) AS has_updated_by FROM public.ai_settings;
```

`ai_settings`: 1 แถว · `id = 1` · `model = 'gemini-3.1-flash-lite'` ·
`updated_at` 2026-08-25 · มี `updated_by`

ความพร้อมของคอลัมน์เวลาเทียบกับ NOT NULL ที่ปลายทางบังคับ:

```sql
SELECT
  (SELECT count(*) FROM public.external_news WHERE synced_at IS NULL) AS extnews_synced_at_null,
  (SELECT count(*) FROM public.external_news WHERE created_at IS NULL) AS extnews_created_at_null,
  (SELECT count(*) FROM public.news WHERE created_at IS NULL OR updated_at IS NULL) AS news_ts_null,
  (SELECT count(*) FROM public.courses WHERE created_at IS NULL OR updated_at IS NULL) AS courses_ts_null,
  (SELECT count(*) FROM public.external_news WHERE description IS NULL) AS extnews_description_null,
  (SELECT count(*) FROM public.ai_settings WHERE updated_at IS NULL) AS ai_settings_ts_null;
```

ทุกค่าเป็น **0** — ไม่มีคอลัมน์เวลาใดเป็น NULL ในข้อมูลจริง

---

# ส่วนที่ 2 — UNKNOWN / UNVERIFIED

สิ่งที่ยัง **ไม่** ได้พิสูจน์ในรอบนี้ และเหตุผล

**U1 — `read_only=true` บังคับใช้จริงที่ชั้นเซิร์ฟเวอร์หรือไม่ · UNVERIFIED โดยเจตนา**
หลักฐานทางอ้อมแน่น: ชุดเครื่องมือที่เซิร์ฟเวอร์ประกาศมีเฉพาะฝั่งอ่าน — ไม่มี
`apply_migration`, `create_branch`, `deploy_edge_function`, `merge_branch`, `reset_branch`
การพิสูจน์ตรงต้องลองเขียนจริง ซึ่งขัดคำสั่ง จึงไม่ทำ

**U2 — ค่า `draft` และ `archived` ของ `news.status` มีใช้จริงไหม · ไม่มีหลักฐาน**
ข้อมูลตอนนี้มีแต่ `published` (3/3) และต้นทางไม่มี CHECK จึงไม่มีทั้งข้อมูลและ constraint
ที่จะยืนยันว่าสองค่านั้นเป็นค่าที่ระบบตั้งใจรองรับ ตรวจซ้ำได้เฉพาะเมื่อมีข่าวที่ไม่ published เกิดขึ้น

**U3 — ทำไม `max(synced_at)` ค้างที่ 2026-09-22 ขณะที่ cron เปิดอยู่ยิงทุก 30 นาที · ตีความไม่ได้**
เป็นไปได้ทั้งสองทาง: (ก) ฟังก์ชันล้มเหลวเงียบ ๆ มา ~10 วัน หรือ (ข) ทำงานปกติแต่ upsert
ไม่อัปเดต `synced_at` ของแถวเดิมและไม่มีข่าวใหม่ แยกสองกรณีนี้ต้องอ่าน Edge Function logs
หรือ `cron.job_run_details` ซึ่งเกินสิ่งที่ 10 ข้อสั่งไว้

**U4 — `news.date` เป็นปี 2024 แต่ `created_at` เป็นปี 2026 · ไม่ได้ตัดสิน**
เข้าข่ายข้อมูลตัวอย่าง/seed แต่ไม่มีอะไรในฐานข้อมูลที่ระบุได้ว่าเป็น seed
หรือเป็นข่าวเก่าที่กรอกย้อนหลัง ต้องถามคนที่ใส่ข้อมูล

**U5 — เนื้อ `command` ของ cron job · ไม่อ่านโดยเจตนา**
ตรวจแล้วว่ามีคำบ่งชี้ token/key อยู่ข้างใน การดึงมาแสดงจะขัดข้อ 9 ที่ห้ามแสดง token/secret

**U6 — โมเดลที่สร้าง embedding 768 มิติคือตัวไหนแน่ · อนุมานไม่ได้จากฐานข้อมูล**
`ai_settings.model` คือโมเดลสำหรับตอบคำถาม (`gemini-3.1-flash-lite`) ไม่ใช่โมเดล embedding
ฐานข้อมูลไม่เก็บชื่อโมเดล embedding ไว้ที่ใด ต้องดูจากโค้ดฝั่งแอป

**U7 — ฝั่ง PostgreSQL ปลายทาง (schema `web`, `mko`, `public.users`) · ไม่ได้ตรวจ**
MCP นี้ต่อกับโปรเจกต์ Supabase เท่านั้น ยืนยันได้ว่า `web.*` **ไม่มี** ในฐานนี้
(`list_tables` คืนแค่ `public` / `auth` / `storage`) การเทียบสองฝั่งจริงต้องมี connection
ฝั่งปลายทางด้วย ซึ่งยังไม่มีในรอบนี้

**U8 — ไฟล์ PDF 4 ไฟล์ใน `knowledge-files` เป็นของอะไร · ไม่ทราบ**
ชื่อไฟล์เป็น UUID ล้วน และไม่มีแถวใน `knowledge_articles` ให้อ้างอิง จึงไม่มีทางรู้
จาก metadata ว่าแต่ละไฟล์คือเอกสารอะไร

**U9 — Performance advisors · ไม่ได้เรียก**
เรียกแต่ `get_advisors(security)` ตามที่ข้อ 6 ถามถึงเรื่องสิทธิ์
ไม่ได้เรียก `performance` เพราะไม่อยู่ใน 10 ข้อ

**U10 — ข้อมูลใน `detail` (jsonb) ของวิทยาการคอมพิวเตอร์ · นับคีย์ได้ 5 คีย์ แต่ไม่ได้อ่านเนื้อ**
นับจำนวนคีย์พอสำหรับการประเมินผลกระทบ การ dump เนื้อ jsonb ไม่จำเป็นต่อ 10 ข้อ

---

# ส่วนที่ 3 — ข้อที่กระทบ Migration 005

เทียบ `005_web_schema.sql` กับของจริงที่เพิ่งตรวจ
`005` สร้าง schema `web` เปล่า ๆ ไม่ย้ายข้อมูล ข้อสรุปข้างล่างจึงเป็นเรื่อง
**"ถ้านำเข้าข้อมูลด้วยโครงนี้ จะเกิดอะไร"** ไม่ใช่ข้อผิดของตัวไฟล์ที่รันไปแล้ว

## 3.1 สรุปเป็นตาราง

| # | หัวข้อ | ระดับ | ผล |
|---|---|---|---|
| **M1** | `news.status` CHECK — `PENDING DECISION` ในไฟล์ | **ปิดเคสได้** | ค่าจริงมีแค่ `published` → CHECK ของ 005 ไม่บล็อกข้อมูลชุดนี้ |
| **M2** | `web.site_courses.detail NOT NULL DEFAULT '{}'` | **บล็อกการ import** | ต้นทาง `detail` เป็น NULL **11 ใน 12 แถว** |
| **M3** | `web.site_courses.is_published` | **คอลัมน์ไม่มีต้นทาง** | `public.courses` ไม่มีคอลัมน์นี้เลย |
| **M4** | ชื่อคอลัมน์ไม่ตรง 3 คู่ | **ต้องเขียน mapping** | `logo`→`logo_url` · `date`→`published_on` · `image`→`image_url` |
| **M5** | `VARCHAR(255)` ของ 005 แคบกว่าต้นทาง `VARCHAR(500)` 3 จุด | **ยังไม่พัง แต่แคบลง** | `news.title` (สูงสุดตอนนี้ 74) · `external_news.title` (120) · `knowledge_articles.title` (0 แถว) |
| **M6** | `rag_documents` 768 มิติ | **ยืนยันตรงกับที่ไฟล์เขียนไว้** | 12/12 เป็น 768 ครบ ไม่มี NULL → ย้ายค่าตรงไป bge-m3 1024 ไม่ได้ ต้อง re-embed |
| **M7** | `knowledge_articles` 0 แถว แต่มี PDF 4 ไฟล์ | **ปัญหาเปลี่ยนรูป** | ไม่มีแถวให้ย้าย แต่มีไฟล์ 10.4 MiB ที่ไม่มีใครอ้างถึง |
| **M8** | `external_news` กุญแจ | **ตรงกับของจริงเป๊ะ** | `detail_url` 15/15 unique ไม่ NULL · `slug` 0 NULL · partial unique index เหมือนกัน |
| **M9** | `external_news.synced_at / created_at` NOT NULL ใน 005 | **ปลอดภัย** | ต้นทาง nullable แต่ของจริง NULL = 0 ทั้งคู่ |
| **M10** | FK `created_by` / `updated_by` เปลี่ยนเป้า | **เสียข้อมูลผู้เขียน** | ต้นทางชี้ `auth.users` / `user_profiles(user_id)` · 005 ชี้ `public.users` |
| **M11** | RLS 24 policy + storage 8 policy ไม่มีคู่ใน `web` | **แบบจำลองสิทธิ์หายทั้งชุด** | 005 ใช้ GRANT ให้ `advisor_api`/`advisor_ingest` แทน RLS ที่อิง `user_profiles.role` |
| **M12** | ไม่มี trigger ใน schema `web` | **`updated_at` หยุดทำงาน** | ต้นทางมี 4 trigger ที่ดูแล `updated_at` · 005 ไม่สร้าง trigger ใดเลย |
| **M13** | `user_profiles` ไม่มีที่ไปใน 005 (ตั้งใจ) | **ค้างรอตัดสินใจ** | ของจริงมี 3 แถว (admin 2, user 1) ที่ทุก policy ทั้งระบบพึ่งพา |
| **M14** | Edge Function + cron ที่เขียน `external_news` | **ไม่มีคู่ที่ปลายทาง** | 005 ให้สิทธิ์ `advisor_ingest` เขียน แต่ไม่มีตัวดึงข่าว/ตัวตั้งเวลาฝั่งปลายทาง |
| **M15** | `public.courses.category` ถูก DROP ไปแล้ว | **สอดคล้อง** | 005 ไม่มี `category` ใน `site_courses` ตรงกับของจริง |
| **M16** | ฟังก์ชัน `match_rag_documents` / `rls_auto_enable` | **อยู่นอกขอบเขต 005** | เป็นของจริงที่ใช้งานอยู่ แต่ไม่มีการพูดถึงใน 005 |
| **M17** | `index ivfflat lists=100` | **ตั้งใจไว้สำหรับข้อมูลใหญ่** | ของจริงมี 12 แถว ถ้า re-embed และสร้าง index ใหม่ที่ปลายทาง ควรทบทวนค่านี้ |

## 3.2 รายละเอียดข้อที่ต้องลงมือ

### M1 — `news.status`: คำถามที่ค้างในหัวไฟล์ 005 ตอบได้แล้ว

หัวไฟล์ 005 เขียนไว้ว่า
*"ทางที่ถูกคือรัน `SELECT DISTINCT status FROM public.news` บนต้นทางก่อน"*
รันแล้ว ผลคือ **`published` อย่างเดียว 3 แถว** และต้นทางไม่มี CHECK บนคอลัมน์นี้

ผลต่อ 005: `CHECK (status IN ('published','draft','archived'))` ที่เขียนไว้
**ไม่ทำให้ import ล้ม** เพราะข้อมูลทุกแถวผ่าน และ `VARCHAR(50)` ของ 005 กว้างกว่า
`VARCHAR(20)` ของต้นทาง จึงไม่ตัดค่า

ส่วนที่ยังค้าง: `archived` **ยังไม่มีหลักฐานว่ามีอยู่จริง** เหมือนที่ไฟล์เตือนตัวเองไว้
ข้อมูลไม่ได้พิสูจน์ว่ามี และไม่ได้พิสูจน์ว่าไม่มี — มันแค่ยังไม่ถูกใช้
ตัดสินใจได้สองทาง (ทั้งสองทางยังไม่ทำในรอบนี้):
- คงรายการสามค่าไว้ → เผื่ออนาคต ความเสี่ยงต่อข้อมูลชุดนี้เป็นศูนย์
- ตัดเหลือ `published`, `draft` → ตรงกับคอมเมนต์ใน `supabase_schema.sql` มากกว่า
  แต่ถ้าแอปเคยเขียน `archived` ลงไปในอนาคตจะล้ม

### M2 — ตัวที่จะทำให้ import ล้มจริง: `site_courses.detail`

005 เขียนว่า `detail JSONB NOT NULL DEFAULT '{}'`
ของจริง: **`detail IS NULL` 11 จาก 12 แถว**

`DEFAULT` ช่วยได้เฉพาะตอนไม่ระบุคอลัมน์ ถ้า INSERT แบบ `SELECT ... FROM public.courses`
ตรง ๆ ค่า NULL จะถูกส่งเข้ามาและชน `NOT NULL` → **ล้ม 11 แถว**

เรื่องเดียวกันแต่ปลอดภัย: `careers TEXT[] NOT NULL DEFAULT '{}'` — ของจริง
`careers IS NULL` = 0 และ `careers = '{}'` = 12 **ผ่านทั้ง 12 แถว ไม่ต้องทำอะไร**

ทางแก้ตอน import (ยังไม่ทำ แค่บันทึกไว้): ใช้ `COALESCE(detail, '{}'::jsonb)`

### M3 — `is_published` เป็นคอลัมน์ที่ไม่มีต้นทาง

005 สร้าง `is_published BOOLEAN NOT NULL DEFAULT TRUE` แต่ `public.courses`
**ไม่มีคอลัมน์ไหนที่สื่อความหมายนี้** (ไม่มี `is_published`, `published`, `status`, `visible`)
และ RLS ของ `courses` ก็เปิดให้ทุกคนอ่านแบบไร้เงื่อนไข (`qual = true`)
ต่างจาก `news` ที่กรองด้วย `status = 'published'`

แปลว่าในระบบปัจจุบัน **หลักสูตรทุกอันเผยแพร่หมด** ค่า `DEFAULT TRUE` จึงให้ผลตรงกับของจริง
แต่ต้องรู้ว่านี่เป็นคอลัมน์ใหม่ที่ 005 เพิ่มเข้ามา ไม่ใช่การย้ายข้อมูล — ไม่มีอะไรจะย้ายลงไป

### M4 — ชื่อคอลัมน์ที่ต้องแปลงตอน import

| ต้นทาง (Supabase) | ปลายทาง (005) | หมายเหตุ |
|---|---|---|
| `courses.logo` | `site_courses.logo_url` | ของจริงไม่ NULL ทั้ง 12 แถว |
| `news.date` (DATE, **NOT NULL**) | `news.published_on` (DATE, nullable) | ปลายทางหลวมกว่า ปลอดภัย |
| `news.image` | `news.image_url` | ของจริงไม่ NULL ทั้ง 3 แถว |

NOT NULL ที่ปลายทางผ่อนลง (ปลอดภัยทุกข้อ): `courses.title_en` และ `courses.description`
ต้นทาง NOT NULL แต่ 005 ยอม NULL · `news.description`, `news.category`, `news.date`
ต้นทาง NOT NULL แต่ 005 ยอม NULL · `knowledge_articles.content` ต้นทาง NOT NULL แต่ 005 ยอม NULL

### M5 — ความกว้าง VARCHAR ที่ 005 แคบกว่าต้นทาง

```sql
SELECT 'external_news.title' AS col, max(length(title)) AS max_len,
       count(*) FILTER (WHERE length(title) > 255) AS over_255 FROM public.external_news
UNION ALL SELECT 'external_news.published_text', max(length(published_text)),
       count(*) FILTER (WHERE length(published_text) > 255) FROM public.external_news
UNION ALL SELECT 'news.title', max(length(title)),
       count(*) FILTER (WHERE length(title) > 255) FROM public.news
UNION ALL SELECT 'courses.title', max(length(title)),
       count(*) FILTER (WHERE length(title) > 255) FROM public.courses
UNION ALL SELECT 'courses.title_en', max(length(title_en)),
       count(*) FILTER (WHERE length(title_en) > 255) FROM public.courses
UNION ALL SELECT 'rag_documents.title', max(length(title)),
       count(*) FILTER (WHERE length(title) > 255) FROM public.rag_documents;
```

| คอลัมน์ | ต้นทาง | 005 | ยาวสุดตอนนี้ | เกิน 255 |
|---|---|---|---:|---:|
| `news.title` | varchar(500) | varchar(255) | 74 | **0** |
| `external_news.title` | varchar(500) | varchar(255) | 120 | **0** |
| `knowledge_articles.title` | varchar(500) | varchar(255) | — (0 แถว) | 0 |
| `external_news.published_text` | varchar(100) | varchar(255) | 12 | 0 (ปลายทางกว้างกว่า — ปลอดภัย) |
| `courses.title` / `title_en` | varchar(255) | varchar(255) | 53 / 51 | 0 (เท่ากัน) |
| `rag_documents.title` | varchar(500) | — (005 ไม่สร้างตารางนี้) | 53 | 0 |

**import ชุดนี้ผ่านทุกแถว** แต่ปลายทางรับได้แค่ครึ่งของต้นทาง ถ้าในอนาคตมีข่าวชื่อยาวเกิน 255
ฝั่ง Supabase จะรับได้แต่ฝั่ง `web` จะไม่รับ — เป็นหนี้ที่ยังไม่ถึงกำหนดชำระ

### M6 — embedding: ยืนยันข้อสันนิษฐานในไฟล์ 005 ว่าถูก

หัวไฟล์ 005 เขียนว่า *"ของเดิมเป็น vector 768 มิติจากโมเดลคนละตัวกับที่ระบบนี้ใช้
(bge-m3 1024 มิติ) ย้ายค่าเวกเตอร์ตรง ๆ ไม่ได้"*

ตรวจแล้ว **ถูกต้องทุกจุด**: ประกาศเป็น `vector(768)` · ค่าที่เก็บจริง 768 ทั้ง 12 แถว ·
ไม่มี NULL · มิติเดียวสม่ำเสมอ การตัดสินใจ "ไม่สร้างตาราง embedding ของหน้าเว็บในไฟล์นี้"
จึงเป็นการตัดสินใจที่อิงข้อเท็จจริงที่ถูกต้อง

ขนาดงาน re-embed ถ้าตัดสินใจทำ: **12 chunk** (1 chunk ต่อ 1 หลักสูตร, `max(chunk_index) = 0`)
เป็นงานเล็กมาก ไม่ใช่ 9,039 chunk เหมือนฝั่ง `mko`
**ยังไม่ re-embed ในรอบนี้ตามที่สั่งห้าม**

### M7 — `knowledge_articles` ว่าง แต่ไฟล์ไม่ว่าง

สภาพจริง: ตาราง **0 แถว** · bucket `knowledge-files` มี **PDF 4 ไฟล์ 10,864,464 B (~10.4 MiB)**

หัวไฟล์ 005 เตรียมรับมือเรื่อง "ไฟล์แนบไม่ย้ายตามฐานข้อมูล" ไว้แล้วผ่าน
`COMMENT ON COLUMN web.knowledge_articles.file_path` แต่ของจริงกลับกลายเป็นปัญหาอีกแบบ:
**ไม่มีแถวให้ย้ายเลย** ส่วนไฟล์ 4 ไฟล์นั้นไม่มีอะไรในฐานข้อมูลชี้ถึง

ผลต่อการย้าย: `web.knowledge_articles` จะว่างเปล่าหลัง import (ถูกต้องตามต้นทาง)
แต่ต้องตัดสินใจแยกว่าจะทำอย่างไรกับ PDF 4 ไฟล์นั้น — ทิ้ง หรือเก็บ หรือสร้างแถวให้ใหม่
ข้อมูลที่จะบอกได้ว่าไฟล์ไหนคืออะไรไม่มีอยู่ในฐานข้อมูล (ดู U8)

### M8 / M9 — `external_news`: 005 เขียนถูกแล้ว

| สิ่งที่ 005 เลือก | ของจริง | ตรงกัน |
|---|---|---|
| `detail_url TEXT NOT NULL UNIQUE` | NOT NULL · unique 15/15 · มี `external_news_detail_url_key` | ตรง |
| `slug VARCHAR(255)` nullable | nullable · ของจริง NULL 0 แถว | ตรง |
| partial unique บน `slug WHERE slug IS NOT NULL` | ต้นทางมี `idx_external_news_slug` แบบเดียวกันเป๊ะ | ตรง |
| `source VARCHAR(100) NOT NULL` | varchar(100) NOT NULL · ค่าเดียว `sci_connect` | ตรง |
| `synced_at TIMESTAMPTZ NOT NULL` | ต้นทาง nullable แต่ NULL จริง 0 แถว | ผ่าน |
| `created_at TIMESTAMPTZ NOT NULL` | ต้นทาง nullable แต่ NULL จริง 0 แถว | ผ่าน |
| `published_text VARCHAR(255)` | ต้นทาง varchar(100) — ปลายทางกว้างกว่า | ตรง |

ส่วนที่ 005 แก้ตัวเองในรุ่นก่อน (เคยตั้ง `slug NOT NULL UNIQUE`) **เป็นการแก้ที่ถูกทาง**
แต่เหตุผลที่ให้ไว้ในคอมเมนต์ (*"ถ้าข้อมูลจริงมีแถวที่ slug เป็น NULL การนำเข้าจะล้มทั้งก้อน"*)
ปรากฏว่าข้อมูลจริงไม่มี NULL เลย — การแก้ยังถูกเพราะตรงกับ **ชนิดของต้นทาง**
ไม่ใช่เพราะข้อมูลบังคับ บันทึกไว้เพื่อไม่ให้ใครอ่านคอมเมนต์แล้วเข้าใจว่าเคยมีแถว NULL จริง

### M10 — `created_by` / `updated_by`: ปลายทางชี้คนละตาราง

| คอลัมน์ | ต้นทางชี้ไป | 005 ชี้ไป |
|---|---|---|
| `courses.created_by` | `auth.users(id)` (default `auth.uid()`) | `public.users(id)` |
| `courses.updated_by` | `user_profiles(user_id)` ON DELETE SET NULL | `public.users(id)` ON DELETE SET NULL |
| `news.created_by` | `auth.users(id)` (default `auth.uid()`) | `public.users(id)` |
| `news.updated_by` | `user_profiles(user_id)` ON DELETE SET NULL | `public.users(id)` ON DELETE SET NULL |
| `knowledge_articles.created_by` / `updated_by` | `auth.users(id)` ทั้งคู่ | `public.users(id)` |
| `ai_settings.updated_by` | `auth.users(id)` | `public.users(id)` |

ของจริง: `created_by` และ `updated_by` **ไม่ NULL ทุกแถว** (courses 12/12, news 3/3)
และชี้ไป **บัญชีเดียวกันทั้งหมด** (distinct = 1 ทุกคอลัมน์) · ไม่มี FK กำพร้า

005 ยอมให้ NULL และเขียนเหตุผลไว้ชัดว่า *"ตอนนำข้อมูลเข้าจึงจะมีบางแถวที่หาเจ้าของไม่เจอ"*
ของจริงคือ **หาไม่เจอทุกแถว** เพราะมีผู้เขียนคนเดียวและไม่มีเส้นเชื่อมไป `public.users`
ผลลัพธ์จริงหลัง import: ทั้ง 15 แถว (12 courses + 3 news) จะมี `created_by = NULL`
เว้นแต่จะตัดสินใจจับคู่ผู้ใช้คนนั้นกับแถวใน `public.users` ด้วยมือ
**ยังไม่สร้าง mapping ผู้ใช้ในรอบนี้**

### M11 — แบบจำลองสิทธิ์: RLS 32 policy ไม่มีคู่เลย

ต้นทางควบคุมสิทธิ์ด้วย **RLS 24 policy บนตาราง + 8 policy บน `storage.objects`**
ที่ทุกตัวตัดสินจาก `user_profiles.role in (admin, editor)` และ `auth.uid()`

005 ควบคุมด้วย **GRANT ให้ role ฐานข้อมูล** `advisor_api` / `advisor_ingest`
ไม่เปิด RLS ไม่สร้าง policy และ `web.*` ไม่มี `user_profiles` ให้อ้าง

สิ่งที่หายไปจริง ๆ ถ้าย้ายตามโครงนี้:
1. การแยก **admin กับ editor** — ปลายทางเหลือแค่ "แอปเขียนได้" / "แอปเขียนไม่ได้"
2. `news` ที่คนทั่วไปเห็นเฉพาะ `status='published'` — กลายเป็นเรื่องที่โค้ดแอปต้องกรองเอง
   **ไม่ใช่ฐานข้อมูลกรองให้** ซึ่งคือการเปลี่ยนขอบเขตความปลอดภัย ไม่ใช่แค่ย้ายที่
3. `knowledge_articles` ที่ต้นทางคนทั่วไป **อ่านไม่ได้เลย** (SELECT ต้องเป็น admin/editor) —
   ปลายทางให้ `advisor_api` SELECT ได้ทั้งหมด การกรองย้ายไปอยู่ที่แอป
4. การ DELETE ที่ต้นทางให้ admin ทำได้ — 005 ตั้งใจไม่ให้ใคร DELETE (ตรงตามหลัก 002/004)
   เป็นการเปลี่ยนที่ตั้งใจ ไม่ใช่ของตก

ข้อนี้ไม่ใช่ข้อผิดพลาดของ 005 (ไฟล์เลือกแนวทาง GRANT โดยเจตนาและอธิบายไว้)
แต่เป็นสิ่งที่ **ต้องตัดสินใจก่อน import** ไม่ใช่หลัง เพราะเกี่ยวกับใครเห็นอะไรได้

### M12 — ไม่มี trigger ที่ปลายทาง → `updated_at` จะหยุดนิ่ง

ต้นทางมี `update_updated_at_column()` ติดอยู่กับ **4 ตาราง**
(`courses`, `news`, `knowledge_articles`, `user_profiles`) ทำให้ `updated_at` ถูกต้องเสมอ

005 ประกาศ `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()` ทุกตาราง แต่ **ไม่สร้าง trigger ใด**
→ ค่าจะถูกตั้งแค่ตอน INSERT และไม่ขยับอีกเลยเมื่อ UPDATE จนกว่าจะมีใครเขียนค่าให้เอง
หลักฐานว่าปัญหานี้เกิดขึ้นได้จริง: `rag_documents` ที่ต้นทางก็มี `updated_at`
แต่ไม่มี trigger เหมือนกัน

ถ้ายอมรับได้ต้องเขียนไว้ให้ชัด ถ้ารับไม่ได้ต้องเพิ่ม trigger ในไฟล์ถัดไป
(`moddatetime` มีให้ใช้แต่ **ยังไม่ติดตั้ง** ในฐาน Supabase นี้ — ปลายทางเป็นอีกฐาน ต้องตรวจแยก)

### M13 — `user_profiles`: 005 ตั้งใจไม่สร้าง แต่ของจริงมีข้อมูลและทุกอย่างพึ่งมัน

005 เขียนไว้ชัดในหัวว่าไม่สร้างตาราง role/สิทธิ์ เพราะต้องตัดสินใจเรื่อง auth ก่อน
เหตุผลที่ให้คือ *"ถ้าสร้างตอนนี้จะกลายเป็นที่บอกสิทธิ์สองแห่ง (public.users.is_admin มีอยู่แล้ว)"*

ของจริงที่ค้างอยู่: **3 แถว** — `admin`/`approved` 2 คน · `user`/`approved` 1 คน ·
`user_id` ครบทุกแถวและจับคู่ `auth.users` ได้ 3/3 · เก็บ `email` และ `full_name` ด้วย
และ **32 policy ทั้งระบบอ่านตารางนี้** เพื่อตัดสินสิทธิ์

สิ่งที่การเลื่อนการตัดสินใจนี้แปลว่า: ข้อมูล role 3 แถวนี้ยังไม่มีที่ไป และตราบใดที่ยังไม่มี
ข้อ M11 ก็ยังแก้ไม่ได้ **สองข้อนี้คือข้อเดียวกันในสองมุม**
ไม่พบ role `editor` ในข้อมูลจริงเลย แม้ policy ครึ่งระบบจะเขียนรองรับไว้ —
ถ้าตัดสินใจย้ายแบบรักษา role ควรรู้ว่า `editor` เป็นสิทธิ์ที่ออกแบบไว้แต่ยังไม่มีใครถือ

### M14 — ตัวดึงข่าวอยู่ใน Supabase ไม่ได้อยู่ในของที่ 005 สร้าง

005 ให้สิทธิ์ `advisor_ingest` เขียน `web.external_news` ได้ตารางเดียว
พร้อมคอมเมนต์ *"ตัวดึงข้อมูลเป็นคนเขียน ไม่ใช่ backend"* — ถูกต้องตามของจริง

แต่ตัวที่เขียนจริงคือ **Edge Function `sync-sci-news` (ACTIVE, v1, verify_jwt=true)**
ที่ถูกเรียกโดย **pg_cron job `sync-sci-news-every-30-min` (`*/30 * * * *`, active)**
ทั้งสองอย่างเป็นของในแพลตฟอร์ม Supabase ไม่ใช่สิ่งที่ย้ายตาม schema ไปได้

ผลต่อการย้าย: ถ้าย้าย `external_news` ไปปลายทางแล้วไม่ทำอะไรต่อ ข่าวจะ **หยุดอัปเดต**
หรือแย่กว่านั้นคือ **ข้อมูลแตกเป็นสองชุด** (Edge Function ยังเขียน Supabase ต่อ
ขณะที่หน้าเว็บอ่านจากปลายทาง) ต้องตัดสินใจย้าย/เขียนใหม่/ปิด ตัวดึงข่าวพร้อมกัน
ไม่ใช่หลังจากนั้น · และโปรดดู U3 — ตอนนี้ `synced_at` ค้างอยู่ที่ 2026-09-22 แล้ว
ซึ่งอาจหมายความว่าตัวดึงข่าวมีปัญหาอยู่ก่อนที่จะคิดเรื่องย้ายด้วยซ้ำ

### M15 / M16 / M17 — ข้อย่อยที่เหลือ

**M15 (สอดคล้อง)** — `drop_course_category_detail` ทำให้ `courses.category` ไม่มีอยู่จริงแล้ว
005 ไม่มี `category` ใน `site_courses` → ตรงกัน ไม่ต้องทำอะไร

**M16 (อยู่นอกขอบเขต)** — ฐานจริงมี `public.match_rag_documents` (ฟังก์ชันค้นแบบ vector
ที่หน้าเว็บเรียกใช้) และ `public.rls_auto_enable` ทั้งคู่ไม่มีการพูดถึงใน 005
ถ้าย้ายข้อมูล RAG ไปปลายทาง ต้องมีคนตัดสินใจเรื่องฟังก์ชันค้นหาด้วย ไม่ใช่แค่ตาราง

**M17 (ทบทวนตอนสร้างใหม่)** — `idx_rag_documents_embedding` เป็น
`ivfflat (embedding vector_cosine_ops) WITH (lists='100')` บนข้อมูล 12 แถว
ค่า `lists=100` ตั้งไว้เกินขนาดข้อมูลมาก (ไม่กระทบความถูกต้อง แต่ไม่ได้ช่วยอะไร)
ถ้า re-embed และสร้าง index ที่ปลายทาง ควรเลือกค่าจากขนาดข้อมูลจริงตอนนั้น

## 3.3 ข้อสังเกตเพิ่มเติม (anomaly) — ไม่เกี่ยวกับ 005 โดยตรง

**A1 — FK ชี้กลับตัวเอง**

```
user_profiles_user_id_fkey: FOREIGN KEY (user_id) REFERENCES user_profiles(user_id)
```

`user_profiles.user_id` อ้างอิง `user_profiles.user_id` ของตัวเอง ซึ่งเป็น constraint
ที่ผ่านได้เสมอโดยไม่ตรวจอะไรเลย (แถวหนึ่งอ้างตัวเองได้) เทียบกับอีกสองตารางที่ใช้
`FOREIGN KEY ... REFERENCES user_profiles(user_id)` อย่างมีความหมาย
รูปแบบนี้เข้าข่ายตั้งใจจะชี้ `auth.users(id)` แต่พิมพ์ผิด
**ไม่แก้ในรอบนี้** (ห้ามแก้ schema) แต่ควรตรวจสอบ — ตอนนี้ `user_id` ของทุกแถวจับคู่
`auth.users` ได้ครบ 3/3 จึงยังไม่เกิดผลเสีย

**A2 — unique index ซ้ำซ้อน**

`user_profiles_user_id_key` และ `user_profiles_user_id_unique` เป็น
`UNIQUE btree (user_id)` เหมือนกันทั้งคู่ บวก `idx_user_profiles_user_id` ที่เป็น btree
ธรรมดาบนคอลัมน์เดิมอีกตัว → **3 index บนคอลัมน์เดียว** ที่ 2 ตัวซ้ำกันสนิท
บนข้อมูล 3 แถวไม่มีผลต่อประสิทธิภาพ แต่เป็นร่องรอยว่า migration ถูกรันทับกัน
**ไม่ลบในรอบนี้**

**A3 — `rag_documents.source_type` ใช้ค่าเดียวจากสี่ค่าที่อนุญาต**

CHECK อนุญาต `major`, `news`, `article`, `knowledge` แต่ของจริงมีแต่ `major` 12 แถว
แปลว่า RAG ปัจจุบัน **ตอบได้แต่เรื่องหลักสูตร** ข่าวและบทความยังไม่เคยถูก index เข้า RAG เลย
(สอดคล้องกับ `knowledge_articles` ที่มี 0 แถว)

---

# ภาคผนวก — รายการคำสั่งที่รันทั้งหมดในรอบนี้

ทั้งหมดเป็น `SELECT` หรือ MCP read tool · ไม่มีคำสั่งเขียนแม้คำสั่งเดียว

| ลำดับ | เครื่องมือ | เป้าหมาย | ตอบข้อ |
|---:|---|---|---|
| 1 | `execute_sql` | `GROUP BY status` บน `public.news` (คำสั่งเริ่มต้นที่สั่งไว้) | 2 |
| 2 | `execute_sql` | row count 7 ตาราง (UNION ALL) | 1 |
| 3 | `execute_sql` | `external_news` slug / detail_url uniqueness | 3 |
| 4 | `execute_sql` | `pg_attribute` + `format_type` ของ `rag_documents` | 4 |
| 5 | `list_tables` | สำรวจ `public`, `storage`, `auth` | 1, 5 |
| 6 | `execute_sql` | `vector_dims` + NULL count ของ embedding | 4 |
| 7 | `execute_sql` | `information_schema.columns` ทั้ง schema `public` | 5.1 |
| 8 | `execute_sql` | `pg_constraint` + `pg_get_constraintdef` | 5.2 |
| 9 | `execute_sql` | `max(length(...))` หลายคอลัมน์ เทียบขีด 255 | M5 |
| 10 | `execute_sql` | `pg_indexes` | 5.3 |
| 11 | `execute_sql` | `pg_trigger` + `pg_get_triggerdef` | 5.4 |
| 12 | `execute_sql` | `pg_class.relrowsecurity` + นับ policy | 6 |
| 13 | `execute_sql` | `pg_policies` schema `public` | 6 |
| 14 | `execute_sql` | `storage.buckets` LEFT JOIN `storage.objects` | 7 |
| 15 | `list_edge_functions` | Edge Functions ที่ deploy อยู่ | 8 |
| 16 | `execute_sql` | `auth.users` aggregate (ไม่ดึงข้อมูลระบุตัวบุคคล) | 9 |
| 17 | `execute_sql` | `user_profiles` role x status | 9 |
| 18 | `execute_sql` | `courses` 12 แถว (เชิงโครงสร้าง) | 10 |
| 19 | `list_extensions` | ส่วนขยายที่ติดตั้ง | 4 |
| 20 | `list_migrations` | migration history ฝั่ง Supabase | 5.5 |
| 21 | `execute_sql` | `courses` aggregate (NULL / distinct) | 10, M2 |
| 22 | `execute_sql` | `rag_documents` source_type + orphan check | 4, A3 |
| 23 | `execute_sql` | `storage.objects` รายไฟล์ | 7 |
| 24 | `execute_sql` | `cron.job` (metadata เท่านั้น ไม่อ่าน `command`) | 8.1 |
| 25 | `execute_sql` | `pg_policies` schema `storage` | 7.1 |
| 26 | `execute_sql` | `external_news` group by source | 3 |
| 27 | `execute_sql` | `news` 3 แถว (เชิงโครงสร้าง) | 10 |
| 28 | `execute_sql` | `ai_settings` 1 แถว | 10 |
| 29 | `get_advisors` | security lints | 6.1 |
| 30 | `get_project_url` | API URL | หัวเอกสาร |
| 31 | `execute_sql` | auth ↔ profile linkage + author distinct | 9, M10 |
| 32 | `execute_sql` | NOT NULL readiness ของคอลัมน์เวลา | M9 |

**หนึ่งคำสั่งที่ล้ม** (ไม่กระทบข้อมูล): ครั้งแรกที่ query `pg_trigger` ใช้
`'disabled/'||t.tgenabled` แล้วได้ `ERROR 42725: operator is not unique: unknown || "char"`
แก้โดยเปลี่ยนเป็น `t.tgenabled::text` แล้วรันผ่าน — เป็น error ตอน parse ฝั่งเซิร์ฟเวอร์
ไม่มีการเปลี่ยนแปลงใด ๆ เกิดขึ้น

## ข้อมูลที่ตั้งใจไม่เก็บลงรายงานนี้

ตามข้อ 9 ที่สั่งไว้ · ไม่มีรายการอีเมล · ไม่มี password hash · ไม่มี refresh token /
session token / one-time token · ไม่มี API key · ไม่มีเนื้อ `cron.job.command`
(ตรวจพบว่ามีคำบ่งชี้ secret) · ไม่มีเนื้อหา `user_profiles.email` และ `full_name`
สิ่งที่รายงานคือ **จำนวน** และ **โครงสร้าง** เท่านั้น
