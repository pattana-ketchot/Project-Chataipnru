# Supabase Pre-Migration Audit

| | |
|---|---|
| วันที่ตรวจ | 2026-10-01 |
| ขอบเขต | รวบรวมข้อเท็จจริงจากต้นทางเพื่อเตรียม Data Migration · **READ-ONLY** |
| **สิทธิ์เข้าถึง Supabase project** | **ไม่มี** — ดูข้อ 0 |
| สิ่งที่ค้นพบระหว่างตรวจ | **พบ repository ของ SPA และไฟล์ schema ของ Supabase** — ดูข้อ 11 |
| **ต้องแก้สิ่งที่เคยรายงานผิด** | **มี 4 เรื่อง** — ดูข้อ 12 **อ่านก่อนใช้เอกสารเก่า** |

```
INSERT / UPDATE / DELETE / ALTER / DROP   NONE
MIGRATION 005 APPLIED                     NONE
DATA MIGRATION                            NONE
RLS / STORAGE / AUTH CHANGES              NONE
RE-EMBED · OLLAMA · RAG CHANGES           NONE
DEPLOY / RESTART                          NONE
COMMIT / PUSH                             NONE
SECRETS แสดงหรือบันทึกลงเอกสาร              NONE  (รายงานเฉพาะ "ชื่อ" ตัวแปร)
```

---

## 0. สถานะสิทธิ์เข้าถึง — **ไม่มีสิทธิ์ · STOP ตามที่สั่ง**

ตรวจทุกช่องทางที่เป็นไปได้แล้ว **ไม่พบสิทธิ์เข้าถึงโปรเจกต์ Supabase ในฐานะ member**

| ช่องทาง | เครื่องผู้พัฒนา | เซิร์ฟเวอร์ production |
|---|---|---|
| Supabase CLI | **ไม่ได้ติดตั้ง** | **ไม่ได้ติดตั้ง** |
| session ของ CLI (`~/.supabase`) | **ไม่มี** | **ไม่มี** |
| service-role key | **ไม่มี** (0 รายการ) | **ไม่มี** (0 รายการ) |
| access token / personal token | **ไม่พบ** | **ไม่พบ** |
| ตัวแปรที่มีอยู่ (ชื่อเท่านั้น) | — | `VITE_SUPABASE_URL` · `VITE_SUPABASE_ANON_KEY` |

### 0.1 ทำไม anon key ใช้แทนไม่ได้ และไม่ได้ใช้

`VITE_SUPABASE_ANON_KEY` ที่มีอยู่คือ **กุญแจสาธารณะที่ฝังอยู่ในไฟล์ที่เบราว์เซอร์ของ
ทุกคนโหลดได้** ไม่ใช่สิทธิ์ของ member

- มันไม่ให้ข้อมูลที่รายงานนี้ต้องการ (row count ทุกตาราง · RLS policy ที่เปิดอยู่จริง ·
  เนื้อ Storage · `auth.users`) เพราะ RLS กันไว้
- การเอามันไปไล่ถามโครงสร้างฐานข้อมูลคือการพยายามดึงข้อมูลเกินกว่าที่แอปตั้งใจให้
  ซึ่งตรงกับข้อห้าม **"ห้าม bypass"**

**จึงไม่ได้ใช้ anon key ยิงฐานข้อมูลแม้แต่คำขอเดียว**

### 0.2 ต้องขอสิทธิ์อะไร

> ขอให้เจ้าของโปรเจกต์ Supabase **เชิญบัญชีของเจ้าของโปรเจกต์นี้เข้าเป็น member**
> ของ Supabase Organization / Project
>
> Supabase Dashboard → Organization → **Team** → **Invite member**
>
> สิทธิ์ที่ต้องการ: **Developer หรือสูงกว่า** (ต้องเห็น Database, Storage, Edge Functions,
> Authentication)

**ห้ามใช้บัญชีหรือ credential ของผู้อื่น** และไม่ได้พยายามทำ

---

## 11. Repository ของ SPA — **พบแล้ว และเข้าถึงได้**

(ตอบข้อ 11 ก่อน เพราะเป็นสิ่งที่เปลี่ยนผลของรายงานทั้งฉบับ)

| | |
|---|---|
| repository | **`https://github.com/FoMake/Univercity.git`** |
| สถานะ | **public** — GitHub API ตอบ `HTTP 200` โดยไม่ต้องยืนยันตัวตน |
| มี clone ในเครื่องแล้ว | **`D:\workspace\LastProject`** |
| branch ของ clone | `prep-step8` · HEAD `94bb84c` (2026-09-23) · 8 commits |
| branch บน remote | `main` ที่ `0f0dfe76…` — **clone ในเครื่องอาจไม่ตรงกับ remote** |
| ดึงจาก remote ได้ไหม | **ได้** |

### 11.1 สิ่งที่อยู่ใน repository นี้

```
api/                     ฟังก์ชันฝั่งเซิร์ฟเวอร์ 13 ไฟล์ (เป็นที่มาของ webapi/api/)
src/                     source ของ SPA  — มี src/lib/supabase.js, adminAuth.js ฯลฯ
supabase/functions/sync-sci-news/index.ts     Edge Function (224 บรรทัด)
supabase_schema.sql      snapshot ของ schema ทั้งหมด (441 บรรทัด)
vite.config.js · vercel.json · package.json · index.html · public/ · Ex/
```

**ไม่มีโฟลเดอร์ `supabase/migrations/`** — มีแต่ `supabase_schema.sql` ไฟล์เดียว

### 11.2 `supabase_schema.sql` คืออะไร — อ่านหัวไฟล์

> ไฟล์นี้ถูกสร้างใหม่โดยการดึงโครงสร้างจริงจาก Supabase project ที่ใช้งานอยู่
> (ผ่าน Supabase MCP tools แบบ read-only) เนื่องจากไฟล์ schema/migration ชุดเดิม
> (ที่ไม่เคย commit เข้า git) หายไปจากเครื่อง ไฟล์นี้จึงเป็น **"snapshot"** รวมของ
> schema ปัจจุบัน **ไม่ใช่ประวัติ migration ทีละขั้น**

**ผลต่อความน่าเชื่อถือของรายงานนี้**

| ระดับ | หมายถึง |
|---|---|
| **VERIFIED FROM SCHEMA SNAPSHOT** | อ่านจาก `supabase_schema.sql` ซึ่งถูกดึงจากโปรเจกต์จริง **ณ วันที่ไม่เกิน 2026-09-23** · ถ้ามีคนแก้ schema หลังจากนั้น ไฟล์นี้จะไม่สะท้อน |
| **UNKNOWN** | ต้องเข้าโปรเจกต์จริงเท่านั้น |

---

## 1. ตารางและ row count

**row count ทุกตาราง = `UNKNOWN`**
เหตุผล: ต้อง query ฐานข้อมูลจริง ซึ่งไม่มีสิทธิ์เข้าถึง · ไม่มีไฟล์ dump ที่มีข้อมูล ·
`docs/backups/supabase_courses_backup_20260923.json` มีขนาดเพียง 1,006 ไบต์ ซึ่งเล็ก
เกินกว่าจะเป็นข้อมูลทั้งตาราง และไม่ครอบตารางอื่น

ตารางที่เกี่ยวข้อง **7 ตาราง** (VERIFIED FROM SCHEMA SNAPSHOT) + schema ของ Supabase เอง

| schema.table | หน้าที่ | row count |
|---|---|---|
| `public.user_profiles` | role/status ของผู้ดูแล Admin Panel | UNKNOWN |
| `public.courses` | หลักสูตรในมุมของหน้าเว็บ | UNKNOWN |
| `public.news` | ข่าวที่ทีมเขียนเอง | UNKNOWN |
| `public.ai_settings` | ตั้งค่าโมเดล — ออกแบบให้มีแถวเดียว (`CHECK id = 1`) | UNKNOWN (คาดว่า 1) |
| `public.rag_documents` | chunk + embedding ของ RAG ฝั่งหน้าเว็บ | UNKNOWN |
| `public.knowledge_articles` | คลังความรู้ + ไฟล์แนบ | UNKNOWN |
| `public.external_news` | ข่าว SCI Connect ที่ sync มาอัตโนมัติ | UNKNOWN |
| `auth.users` | ผู้ใช้ของ Supabase Auth | UNKNOWN |

---

## 2. Schema / column / type / PK / FK / UNIQUE / CHECK

**VERIFIED FROM SCHEMA SNAPSHOT** ทั้งหมดในหัวข้อนี้

### 2.1 สรุปจำนวน

| | จำนวน |
|---|---:|
| ตาราง | 7 |
| **foreign key** | **7** |
| **check constraint (ระดับตาราง)** | **2** |
| **unique** | **4** |
| index | 13 |
| trigger | 6 |
| RLS policy | 32 |
| extension | 2 (`pgcrypto`, `vector`) |

### 2.2 `public.user_profiles`

```sql
id          UUID PRIMARY KEY DEFAULT gen_random_uuid()
user_id     UUID UNIQUE                      -- ไม่มี FK ไป auth.users
role        VARCHAR(50)  DEFAULT 'user'
full_name   VARCHAR(255)
email       TEXT
status      VARCHAR(50)  NOT NULL DEFAULT 'approved'
created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
updated_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()

INDEX idx_user_profiles_user_id / _role / _status
```

> คอมเมนต์ในไฟล์ระบุว่า production มี unique index **ซ้ำอีกหนึ่งตัว** บน `user_id`
> (`user_profiles_user_id_key` และ `user_profiles_user_id_unique`)

### 2.3 `public.courses`

```sql
id          UUID PRIMARY KEY DEFAULT gen_random_uuid()
title       VARCHAR(255) NOT NULL
title_en    VARCHAR(255) NOT NULL
description TEXT         NOT NULL
logo        TEXT
careers     TEXT[]
detail      JSONB
created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
updated_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
created_by  UUID DEFAULT auth.uid() REFERENCES auth.users(id)
updated_by  UUID REFERENCES public.user_profiles(user_id)     ← ชี้คนละตารางกับ created_by

INDEX idx_courses_created_at (created_at DESC)
```

`detail JSONB` มีคอมเมนต์อธิบายโครงไว้

```
{ level, duration, tuition_per_semester, tuition_total, about, qualifications[],
  highlights[{title, description}],
  faculty[{name, nameEn, positionTh, positionEn, email, image, image_path}],
  documents[{name, size, type, url, path}], important_info[{label, value}] }
```

> **มี PII อยู่ใน `detail`** — `faculty[].email` คืออีเมลของอาจารย์
> ต้องวางแผนจัดการก่อนย้ายเข้าฐานข้อมูลที่ repo เป็น public

### 2.4 `public.news`

```sql
id          UUID PRIMARY KEY DEFAULT gen_random_uuid()
title       VARCHAR(255) NOT NULL
description TEXT         NOT NULL
category    VARCHAR(100) NOT NULL
date        DATE         NOT NULL
image       TEXT
status      VARCHAR(50)  NOT NULL DEFAULT 'published'   -- คอมเมนต์: published | draft
created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
updated_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
created_by  UUID DEFAULT auth.uid() REFERENCES auth.users(id)
updated_by  UUID REFERENCES public.user_profiles(user_id)

INDEX idx_news_date / _created_at / _category / _status
```

### 2.5 `public.ai_settings`

```sql
id          INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1)
model       VARCHAR(255) NOT NULL
updated_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
updated_by  UUID REFERENCES auth.users(id)
```

### 2.6 `public.rag_documents`

```sql
id           UUID PRIMARY KEY DEFAULT gen_random_uuid()
source_type  VARCHAR(50) NOT NULL CHECK (source_type IN ('major','news','article','knowledge'))
source_id    UUID                       -- ไม่มี FK (ชี้ได้หลายตารางตาม source_type)
title        VARCHAR(255) NOT NULL
content      TEXT         NOT NULL
chunk_index  INTEGER      NOT NULL DEFAULT 0
embedding    vector                     -- ไม่ระบุมิติ ดูหมายเหตุ
created_at   TIMESTAMP WITH TIME ZONE DEFAULT NOW()
updated_at   TIMESTAMP WITH TIME ZONE DEFAULT NOW()
UNIQUE (source_type, source_id, chunk_index)

INDEX idx_rag_documents_source (source_type, source_id)
INDEX idx_rag_documents_embedding USING ivfflat (embedding vector_cosine_ops) WITH (lists='100')
```

> **สำคัญ**: คอลัมน์ประกาศเป็น `vector` **ไม่ระบุมิติ** คอมเมนต์ในไฟล์เขียนว่า
> "ขนาด vector ขึ้นกับโมเดล embedding ที่ใช้ (ปรับ dimension ตาม provider จริง)"
>
> ตัวเลข **768** ที่เคยรายงานมาจาก `api/_lib/rag.js` → `EMBEDDING_DIMENSIONS = 768`
> ซึ่งเป็น **ค่าคงที่ของแอปพลิเคชัน ไม่ใช่ข้อบังคับของคอลัมน์**
> มิติจริงของข้อมูลที่เก็บอยู่ = **UNKNOWN** ต้องวัดจากฐานข้อมูลจริง
>
> น่าสังเกต: ใช้ `ivfflat` + `vector_cosine_ops` + `lists = 100` **เหมือนกับฝั่งเราทุกอย่าง**

### 2.7 `public.knowledge_articles`

```sql
id          UUID PRIMARY KEY DEFAULT gen_random_uuid()
title       VARCHAR(255) NOT NULL
content     TEXT         NOT NULL
file_path   TEXT
file_name   TEXT
file_size   BIGINT
created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
updated_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
created_by  UUID REFERENCES auth.users(id)
updated_by  UUID REFERENCES auth.users(id)

INDEX idx_knowledge_articles_created_at (created_at DESC)
```

### 2.8 `public.external_news`

```sql
id              UUID PRIMARY KEY DEFAULT gen_random_uuid()
title           VARCHAR(255) NOT NULL
description     TEXT
image_url       TEXT
detail_url      TEXT         NOT NULL UNIQUE      ← กุญแจที่ unique จริงคือตัวนี้
published_at    TIMESTAMP WITH TIME ZONE
published_text  VARCHAR(255)
source          VARCHAR(100) NOT NULL
slug            VARCHAR(255)                      ← NULL ได้
facebook_url    TEXT
synced_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW()
created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()

INDEX idx_external_news_published_at / _source
UNIQUE INDEX idx_external_news_slug ON (slug) WHERE (slug IS NOT NULL)   ← partial
```

### 2.9 Trigger

| trigger | บนตาราง |
|---|---|
| `update_courses_updated_at` | `courses` |
| `update_news_updated_at` | `news` |
| `update_knowledge_articles_updated_at` | `knowledge_articles` |
| `update_user_profiles_updated_at` | `user_profiles` |
| `on_auth_user_created` | `auth.users` — สร้าง `user_profiles` ให้อัตโนมัติ |
| `guard_user_profile_privileges_trigger` | `user_profiles` — กันการยกระดับสิทธิ์ตัวเอง |

> trigger สองตัวท้ายสำคัญต่อการวางแผน auth — ถ้าย้าย auth ต้องมีกลไกแทน

---

## 3. ค่า `news.status` ที่มีอยู่จริง

**`UNKNOWN`** — ต้อง `SELECT DISTINCT status FROM public.news` บนฐานข้อมูลจริง

สิ่งที่ยืนยันได้จาก source

| แหล่ง | บอกอะไร |
|---|---|
| `supabase_schema.sql:75` | `status VARCHAR(50) NOT NULL DEFAULT 'published'` · คอมเมนต์ `-- published \| draft` |
| **ไม่มี CHECK constraint** บนคอลัมน์นี้ | ฐานข้อมูลไม่ได้บังคับค่า จึงอาจมีค่าอื่นหลุดเข้าไปได้ |

> **ผลต่อ migration 005**: CHECK ที่ผมใส่ไว้คือ `('published','draft','archived')`
> คอมเมนต์ต้นทางระบุเพียงสองค่า — **`archived` เป็นค่าที่ผมเพิ่มเอง**
> ต้อง `SELECT DISTINCT` ของจริงก่อน แล้วปรับรายการให้ตรง

---

## 4. ชนิดและ timezone semantics ของ timestamp

**VERIFIED FROM SCHEMA SNAPSHOT — และนี่คือเรื่องที่ต้องแก้จากรายงานเดิม**

ทุกคอลัมน์เวลาในทั้ง 7 ตารางประกาศเป็น

```
TIMESTAMP WITH TIME ZONE        (= timestamptz)
```

ไม่มีคอลัมน์ `TIMESTAMP` แบบไม่มีเขตเวลาเลยแม้คอลัมน์เดียว

| คอลัมน์ | ชนิด |
|---|---|
| `created_at`, `updated_at` ทุกตาราง | `TIMESTAMP WITH TIME ZONE DEFAULT NOW()` |
| `external_news.published_at`, `synced_at` | `TIMESTAMP WITH TIME ZONE` |
| `news.date` | `DATE` (ไม่ใช่ timestamp) |

**ผลที่สำคัญ**: ไม่ต้องเดาเขตเวลาตอนย้าย ทั้งต้นทางและปลายทางเป็น `timestamptz`
เหมือนกัน — **ความเสี่ยงเรื่องเวลาคลาด 7 ชั่วโมงที่เคยระบุไว้ ไม่มีจริง**

---

## 5. RLS — เปิดที่ตารางใด และ policy ที่มีอยู่

**VERIFIED FROM SCHEMA SNAPSHOT** · สถานะ **ที่เปิดอยู่จริงในขณะนี้** = `UNKNOWN`

### 5.1 ตารางที่ประกาศเปิด RLS — **ทั้ง 7 ตาราง**

```
public.user_profiles · public.courses · public.news · public.ai_settings
public.rag_documents · public.knowledge_articles · public.external_news
```

### 5.2 policy ที่ประกาศไว้ — **32 รายการ**

| ตาราง | SELECT | INSERT | UPDATE | DELETE | ALL |
|---|---:|---:|---:|---:|---:|
| `public.courses` | 1 | 1 | 1 | 1 | — |
| `public.news` | **2** | 1 | 1 | 1 | — |
| `public.external_news` | 1 | 1 | 1 | 1 | — |
| `public.knowledge_articles` | 1 | 1 | 1 | 1 | — |
| `public.user_profiles` | 1 | — | **2** | — | — |
| `public.ai_settings` | 1 | — | 1 | — | — |
| `public.rag_documents` | 1 | — | — | — | **1** |
| `storage.objects` | 2 | 2 | 2 | 2 | — |
| **รวม** | **10** | **6** | **9** | **6** | **1** |

รูปแบบที่ใช้: policy เขียนแบบ `WITH CHECK (EXISTS (SELECT … FROM user_profiles
WHERE user_id = auth.uid() AND role IN (…) AND status = 'approved'))` — คือตรวจสิทธิ์
จากตาราง `user_profiles` ด้วยตัวตนของผู้เรียก

> **ผลต่อแผนย้าย**: ถ้าเอา Supabase ออก **ต้องเขียน authorization 32 เงื่อนไขนี้
> ใหม่ที่ชั้น API** พลาดข้อเดียว = ข้อมูลเปิดโล่ง · เนื้อ policy เต็มอยู่ใน
> `supabase_schema.sql` บรรทัด 160–440 ซึ่งตอนนี้อ่านได้แล้ว

---

## 6. Storage bucket

**VERIFIED FROM SCHEMA SNAPSHOT** · จำนวนไฟล์และขนาดจริง = `UNKNOWN`

```sql
INSERT INTO storage.buckets (id, name, public) VALUES
  ('course-assets',   'course-assets',   true),      -- สาธารณะ
  ('knowledge-files', 'knowledge-files', false);     -- ไม่สาธารณะ
```

| bucket | public | เก็บอะไร (จากคอมเมนต์) | file count | ขนาดรวม |
|---|---|---|---|---|
| `course-assets` | **true** | โลโก้หลักสูตร · รูปอาจารย์ · เอกสารหลักสูตร | UNKNOWN | UNKNOWN |
| `knowledge-files` | **false** | ไฟล์ของคลังความรู้ | UNKNOWN | UNKNOWN |

policy ของ `storage.objects` มี **8 รายการ** (SELECT/INSERT/UPDATE/DELETE อย่างละ 2
— คือ bucket ละหนึ่งชุด) · `course-assets` อ่านได้ทุกคน แต่แก้/ลบได้เฉพาะ admin/editor

**ความเชื่อมโยงกับฐานข้อมูล**: `knowledge_articles.file_path` และ
`courses.detail.documents[].path` / `faculty[].image_path` ชี้ไปที่ไฟล์ใน bucket เหล่านี้
— **การย้ายฐานข้อมูลไม่ได้ย้ายไฟล์ตามมา**

---

## 7. Edge Functions

**VERIFIED FROM SOURCE** — source อยู่ใน repository ของ SPA แล้ว

| ฟังก์ชัน | source | บรรทัด | หน้าที่ |
|---|---|---:|---|
| `sync-sci-news` | `supabase/functions/sync-sci-news/index.ts` | 224 | ดึงข่าวจาก `sci.pnru.ac.th` มาเขียนลง `external_news` |

**มีฟังก์ชันอื่นอีกหรือไม่ = `UNKNOWN`** — ใน repo มีตัวเดียว แต่ฟังก์ชันที่ deploy
บนโปรเจกต์จริงอาจมีมากกว่านี้ ต้องดูที่ Dashboard → Edge Functions

(ร่องรอย `functions/v1` ที่พบใน bundle 4 ครั้ง ยังไม่สามารถระบุได้ว่าชี้ไปฟังก์ชันใดบ้าง)

---

## 8. `auth.users` — metadata ที่จำเป็นต่อการวางแผน

**`UNKNOWN` ทั้งหมด** — ต้องเข้าโปรเจกต์จริง

| สิ่งที่ต้องรู้ | สถานะ |
|---|---|
| จำนวนผู้ใช้ | UNKNOWN |
| รายการอีเมล (เพื่อเทียบกับ `public.users` 198 บัญชี) | UNKNOWN |
| วิธี sign-in ที่ใช้ (email/password · OAuth · magic link) | UNKNOWN |
| `email_confirmed_at` มีกี่คน | UNKNOWN |
| ผู้ใช้ที่มี `user_profiles.role ∈ (admin, editor)` | UNKNOWN |

**ไม่ได้อ่านและจะไม่อ่าน** password hash, token, refresh token, หรือ secret ใด ๆ

สิ่งที่ยืนยันได้จาก schema: มี trigger `on_auth_user_created` ที่สร้างแถวใน
`user_profiles` ให้อัตโนมัติเมื่อมีผู้ใช้ใหม่ — แปลว่า `user_profiles` ควรมีจำนวนแถว
เท่ากับหรือใกล้เคียง `auth.users`

---

## 9. แนวทาง mapping `created_by` / `updated_by`

**วิเคราะห์เท่านั้น ยังไม่สร้าง mapping จริง และไม่ได้แก้ข้อมูลใด**

### 9.1 ปลายทางของแต่ละคอลัมน์ไม่เหมือนกัน

| ตาราง | `created_by` ชี้ไป | `updated_by` ชี้ไป |
|---|---|---|
| `courses` | `auth.users(id)` | **`public.user_profiles(user_id)`** |
| `news` | `auth.users(id)` | **`public.user_profiles(user_id)`** |
| `knowledge_articles` | `auth.users(id)` | `auth.users(id)` |
| `ai_settings` | — | `auth.users(id)` |

เนื่องจาก `user_profiles.user_id` อ้างถึง `auth.users.id` อยู่แล้วโดยความหมาย
ค่าทั้งสองแบบจึงเป็น **uuid ของผู้ใช้ Supabase เหมือนกัน** แต่ประกาศ FK ไปคนละตาราง

### 9.2 ทางเลือกการ map ไปยัง `public.users`

| ทาง | วิธี | ข้อดี | ข้อเสีย |
|---|---|---|---|
| **A — map ด้วยอีเมล** | `user_profiles.email` ↔ `public.users.email` (citext) | ใช้ค่าที่มีความหมายกับคน · `public.users.email` เป็น citext จึงไม่สนตัวพิมพ์ | `user_profiles.email` **ไม่ NOT NULL และไม่ UNIQUE** · ผู้ใช้สองชุดอาจไม่ทับกันเลย |
| **B — ปล่อย NULL ทั้งหมด** | ไม่ map เลย | ง่ายที่สุด ไม่มีทางผิดคน | เสียข้อมูลว่าใครเขียนอะไร |
| **C — map เฉพาะที่ชัดเจน** | map ด้วยอีเมลที่ตรงกันเป๊ะเท่านั้น ที่เหลือเป็น NULL | ได้ข้อมูลเท่าที่ยืนยันได้ ไม่เดา | ต้องมีรายงานว่า map ได้กี่แถว ไม่ได้กี่แถว |

**ความเห็น**: ทาง C สอดคล้องกับที่ migration 005 ออกแบบไว้ (ทุก FK เป็น nullable
และ `ON DELETE SET NULL`) และเป็นทางเดียวที่ไม่ต้องเดา

**ยังตัดสินไม่ได้** เพราะไม่รู้ว่าอีเมลสองชุดทับกันกี่รายการ (ต้องการข้อมูลจาก
`auth.users` / `user_profiles` ซึ่งเป็น UNKNOWN)

---

## 10. เปรียบเทียบ Supabase `courses` กับ `public.courses`

**matched / unmatched / ambiguous = `UNKNOWN` ทั้งหมด** — ต้องมีข้อมูลจริงทั้งสองฝั่ง
**ยังไม่สร้าง mapping ใด ๆ**

### 10.1 สิ่งที่เทียบได้ตอนนี้คือ "โครงสร้าง" ไม่ใช่ "แถว"

| | Supabase `courses` | PostgreSQL `public.courses` |
|---|---|---|
| จำนวนแถว | UNKNOWN | **24** (วัดจริง) |
| PK | `id UUID` | `id UUID` |
| กุญแจธรรมชาติ | **ไม่มี** | `code` UNIQUE |
| ชื่อ | `title` NOT NULL · `title_en` NOT NULL | `title` NOT NULL (ไม่มีชื่ออังกฤษ) |
| คำบรรยาย | `description` NOT NULL | `summary` |
| เนื้อหาเสริม | `detail JSONB` (ค่าเล่าเรียน อาจารย์ เอกสาร) | — |
| อาชีพ | `careers TEXT[]` | — |
| โลโก้ | `logo TEXT` | — |
| ข้อมูลที่ฝั่งเรามีแต่เขาไม่มี | — | `provider` · `mode` · `duration_weeks` · `price` · `currency` · `tags` · `is_active` |

**ไม่มีคอลัมน์ใดที่เป็นกุญแจร่วมโดยธรรมชาติ** — `id` ของสองฝั่งเป็น uuid ที่สร้าง
แยกกัน ไม่เกี่ยวกัน · จึงต้องจับคู่ด้วย **ชื่อหลักสูตร** ซึ่งเป็นงานที่ต้องมีคนตรวจ

### 10.2 สิ่งที่บอกได้ว่าการจับคู่จะยาก

ฝั่งเรามีประสบการณ์ตรงแล้ว — `mko.crawl_sources` มี **6 แถวติดค้างในคิว** ด้วยเหตุผล
`"ชื่อหลักสูตรตรงกับ 2 ฉบับ แยกจากชื่ออย่างเดียวไม่ได้"` การจับคู่ด้วยชื่อหลักสูตร
**พิสูจน์แล้วว่ากำกวมในข้อมูลจริงของโปรเจกต์นี้**

ต้องคาดหมายว่าจะมีกลุ่ม **ambiguous** และต้องมีคนตัดสิน ไม่ใช่ให้สคริปต์เดา

---

## 12. ⚠ ต้องแก้สิ่งที่เคยรายงานผิด — **4 เรื่อง**

การตรวจรอบนี้พบว่าข้อมูลที่ใช้ในเอกสารก่อนหน้ามาจาก `docs/database/schema.json`
ซึ่ง **parse schema ของ Supabase ได้ไม่ครบ** — ไม่ได้อ่าน constraint ที่ประกาศระดับ
คอลัมน์ (`REFERENCES` / `CHECK` / `UNIQUE` ที่เขียนต่อท้ายคอลัมน์) และอ่านชนิดเวลาผิด

### E1 — "Supabase มี 0 FK · 0 CHECK · 1 UNIQUE" **ผิด**

| | เคยรายงาน | **ความจริง** |
|---|---:|---:|
| foreign key | 0 | **7** |
| check constraint | 0 | **2** |
| unique | 1 | **4** |
| index | ไม่ได้รายงาน | **13** |
| RLS policy | UNKNOWN | **32** |

**แพร่ไปที่ไหนบ้าง** — ทั้งหมด commit แล้วและ push แล้ว

```
db/migrations/005_web_schema.sql          คอมเมนต์หัวไฟล์ และหัวข้อ "ทำไมใส่ FK ทั้งที่ของเดิมไม่มี"
eval/web_schema_check.py                  คอมเมนต์ docstring และชื่อข้อตรวจสองข้อ
docs/DATABASE_CONSOLIDATION_AUDIT.md      ข้อ 4.3 และตารางเปรียบเทียบ
docs/MIGRATION_005_WEB_SCHEMA_REVIEW.md   ข้อ 2.1 และ 3.3
docs/TARGET_ARCHITECTURE.md               หัวข้อ "ข้อค้นพบที่เปลี่ยนความเข้าใจ"
commit 67c6f99 ข้อความ commit             "zero foreign keys, zero check constraints"
```

**และผมบอกเรื่องนี้กับเจ้าของโปรเจกต์ตอนคุยเรื่อง MongoDB ด้วย** — ข้อสรุปที่ว่า
"ไม่ควรย้ายไป MongoDB" ยังถูกต้อง แต่**เหตุผลที่ว่า "schema เราไม่มี FK เลย"
ใช้ไม่ได้** เพราะมี 7 เส้น

### E2 — "timestamp ไม่มีเขตเวลา ต้องเดาตอนย้าย" **ผิด**

ทุกคอลัมน์เวลาเป็น `TIMESTAMP WITH TIME ZONE` อยู่แล้ว **ไม่ต้องเดาเขตเวลา**
ความเสี่ยง "เวลาคลาด 7 ชั่วโมง" ที่ระบุไว้ในเอกสารหลายฉบับ **ไม่มีจริง**

### E3 — "`rag_documents` เป็น `vector(768)`" **ไม่แม่นยำ**

คอลัมน์ประกาศเป็น `vector` **ไม่ระบุมิติ** · เลข 768 มาจากค่าคงที่ของแอป
(`EMBEDDING_DIMENSIONS` ใน `api/_lib/rag.js`) ไม่ใช่ข้อบังคับของคอลัมน์
มิติจริงของข้อมูลที่เก็บอยู่ยังเป็น **UNKNOWN**

ข้อสรุปหลักยังไม่เปลี่ยน: **ห้าม copy/convert เข้า `vector(1024)` ต้อง re-embed ใหม่**

### E4 — ผลต่อ migration 005 ที่ commit ไปแล้ว

| จุด | ของเดิมในต้นทาง | migration 005 ที่เขียนไว้ | ต้องทำอะไร |
|---|---|---|---|
| `external_news` กุญแจ unique | `detail_url` **NOT NULL UNIQUE** · `slug` nullable + partial unique | `slug` **NOT NULL UNIQUE** · `detail_url` ไม่มี unique | **ต้องแก้** — ถ้ามีแถว `slug` เป็น NULL การนำเข้าจะล้มทั้งก้อน |
| `news.status` CHECK | ไม่มี CHECK · คอมเมนต์ระบุ `published \| draft` | `CHECK IN ('published','draft','archived')` | ตรวจค่าจริงก่อน · `archived` อาจไม่มีอยู่จริง |
| `courses.title_en`, `description` | **NOT NULL** ทั้งคู่ | nullable | หลวมกว่า — ยอมรับได้ แต่ควรรู้ |
| `external_news.source` | **NOT NULL** | nullable | หลวมกว่า — ยอมรับได้ |
| `courses.detail JSONB` | มีข้อมูลค่าเล่าเรียน อาจารย์ เอกสาร **และอีเมลอาจารย์** | `detail JSONB NOT NULL DEFAULT '{}'` | **ต้องวางแผนเรื่อง PII** ก่อนนำเข้า |

**migration 005 ยังไม่ถูก apply ที่ใด** จึงยังแก้ได้โดยไม่กระทบอะไร
แต่ **ต้องแก้ก่อนนำข้อมูลเข้า** — ขอให้ถือว่าเอกสารนี้เป็นคำขอให้ทบทวน 005 อีกรอบ

---

## 13. สิ่งที่ยังต้องการก่อนเริ่ม Data Migration

### 13.1 ต้องมีสิทธิ์เข้า Supabase (ขาดไม่ได้)

| # | ต้องการ | ใช้ตอบข้อ |
|---|---|---|
| 1 | row count ทุกตาราง | ข้อ 1 |
| 2 | `SELECT DISTINCT status FROM news` | ข้อ 3 · แก้ CHECK ของ 005 |
| 3 | `SELECT vector_dims(embedding) FROM rag_documents LIMIT 1` | ข้อ 2.6 · E3 |
| 4 | สถานะ RLS ที่เปิดอยู่จริง (เทียบกับ snapshot) | ข้อ 5 |
| 5 | จำนวนไฟล์และขนาดใน 2 bucket | ข้อ 6 |
| 6 | รายการ Edge Functions ที่ deploy อยู่จริง | ข้อ 7 |
| 7 | อีเมลใน `auth.users` / `user_profiles` (ไม่เอา hash/token) | ข้อ 8 · 9 |
| 8 | ข้อมูล `courses` ทั้งตาราง | ข้อ 10 |

### 13.2 ตรวจได้ทันทีโดยไม่ต้องขอสิทธิ์เพิ่ม

| # | งาน | หมายเหตุ |
|---|---|---|
| 1 | อ่าน RLS policy ทั้ง 32 รายการจาก `supabase_schema.sql:160-440` | เพื่อออกแบบ authorization ฝั่ง API |
| 2 | อ่าน `supabase/functions/sync-sci-news/index.ts` (224 บรรทัด) | เพื่อเขียนตัวแทน |
| 3 | อ่าน `src/` ของ SPA เพื่อนับจุดที่เรียก Supabase ให้แม่นยำ | ของเดิมประมาณจาก bundle ที่ minify แล้ว |
| 4 | **ทบทวน migration 005 ตาม E4** | ทำได้เลย ยังไม่ apply ที่ใด |
| 5 | ตรวจว่า clone ในเครื่อง (`prep-step8` `94bb84c`) ตรงกับ `main` บน remote หรือไม่ | remote อยู่ที่ `0f0dfe76…` |

---

## สรุปสถานะ

| ข้อ | หัวข้อ | สถานะ |
|---|---|---|
| 0 | สิทธิ์เข้า Supabase | **ไม่มี — STOP** |
| 1 | ตาราง + row count | ตาราง **VERIFIED** · row count **UNKNOWN** |
| 2 | schema / column / PK / FK / UNIQUE / CHECK | **VERIFIED FROM SCHEMA SNAPSHOT** |
| 3 | ค่า `news.status` จริง | **UNKNOWN** |
| 4 | timestamp semantics | **VERIFIED** — เป็น `timestamptz` ทั้งหมด |
| 5 | RLS + policy | ประกาศไว้ **VERIFIED (32 policy)** · สถานะจริง **UNKNOWN** |
| 6 | Storage bucket | ชื่อ bucket **VERIFIED (2 ตัว)** · เนื้อใน **UNKNOWN** |
| 7 | Edge Functions | `sync-sci-news` **VERIFIED** · รายการทั้งหมด **UNKNOWN** |
| 8 | `auth.users` metadata | **UNKNOWN** |
| 9 | แนวทาง map `created_by`/`updated_by` | **วิเคราะห์แล้ว** · ตัดสินไม่ได้จนกว่าจะมีข้อมูล |
| 10 | เทียบ `courses` สองฝั่ง | โครงสร้าง **VERIFIED** · matched/unmatched **UNKNOWN** |
| 11 | repository ของ SPA | **พบแล้ว · public · มี clone ในเครื่อง** |
| 12 | แก้สิ่งที่รายงานผิด | **4 เรื่อง** |

---

## STOP

**ไม่เริ่มออกแบบหรือรัน Data Migration** จนกว่าจะได้รับอนุมัติรอบใหม่

สองเรื่องที่ขอให้ตัดสินก่อน

1. **ขอสิทธิ์ member ของ Supabase project** — ข้อ 1, 3, 5, 6, 7, 8, 10 ตอบไม่ได้ถ้าไม่มี
2. **อนุมัติให้ทบทวน migration 005 ตามข้อ E4 หรือไม่** — โดยเฉพาะกุญแจ unique ของ
   `external_news` ซึ่งถ้าไม่แก้ การนำเข้าจะล้มทั้งก้อนเมื่อเจอแถวที่ `slug` เป็น NULL
