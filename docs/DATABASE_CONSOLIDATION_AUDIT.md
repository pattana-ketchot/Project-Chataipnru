# SCI Advisor — Database Consolidation Audit

| | |
|---|---|
| วันที่ตรวจ | **2026-10-01** · 01:3x–02:0x UTC |
| ขอบเขต | **READ-ONLY** — ประเมินว่ารวมสองฐานข้อมูลเป็น PostgreSQL + pgvector เดียวได้หรือไม่ |
| สิ่งที่แตะ | อ่าน schema ของ PostgreSQL production · อ่าน source ใน repo · อ่านไฟล์ในคอนเทนเนอร์ `webapi` · อ่าน bundle ของ SPA |
| สิ่งที่ไม่ได้แตะ | ไม่เขียนฐานข้อมูลใด ไม่แก้ source ไม่แก้ Supabase ไม่ migrate ไม่ restart ไม่ deploy ไม่ commit |
| **คำตัดสินสั้น** | **รวมได้ในทางเทคนิค แต่ไม่ควรทำก่อนส่งโครงงาน** |

---

## 1. Executive Summary

**รวมได้จริงในทางเทคนิค** — ฐานข้อมูล PostgreSQL ปัจจุบันแข็งแรงพอจะเป็นฐานหลักเดียว
มี 38 relation, 56 foreign key, 68 check constraint และ pgvector ที่ทำงานอยู่จริง
สิ่งที่อยู่ใน Supabase มีเพียง 7 ตาราง ซึ่งเล็กกว่าฝั่ง PostgreSQL มาก

**แต่ตัวขัดขวางที่ใหญ่ที่สุดไม่ใช่เรื่องฐานข้อมูล** — มันคือเรื่องสิทธิ์เข้าถึง source code

> **source ของ SPA ไม่อยู่ในที่เก็บโค้ดนี้** — `.gitignore` บรรทัด 45 กัน `/web/` ออก
> และบนเซิร์ฟเวอร์มีเพียง **bundle ที่ build แล้ว** (40 ไฟล์ 8.5 MB) ไม่มี source
> SPA นี้เรียก Supabase **โดยตรงจากเบราว์เซอร์** เพื่อทำ auth, อ่านเขียน 6 ตาราง,
> ใช้ Storage และเรียก Edge Function การย้ายฐานข้อมูลจึงต้องแก้ SPA ซึ่งทำไม่ได้
> โดยไม่มี source และไม่ได้รับความร่วมมือจากเจ้าของโค้ดส่วนนั้น

**ตัวขัดขวางอันดับสองเป็นเรื่องเทคนิคจริง** — มี RAG สองระบบที่ vector เข้ากันไม่ได้

```
ของเรา   course_chunks   vector(1024)  bge-m3 (Ollama ในเครื่อง)       ivfflat vector_cosine_ops
ของเพื่อน rag_documents   vector(768)   gemini-embedding-001 (Google)   RPC match_rag_documents
```

มิติต่างกัน โมเดลต่างกัน จึง **ย้าย vector ตรง ๆ ไม่ได้เลย** ต้อง embed เนื้อหาทั้งหมด
ของ `rag_documents` ใหม่ด้วย bge-m3 — ไม่ใช่การคัดลอกข้อมูล แต่เป็นการสร้างใหม่

**ตัวขัดขวางอันดับสาม** — รหัสผ่านใน Supabase Auth เอาออกมาไม่ได้ (เป็น hash
ที่ Supabase เก็บเอง ไม่มี API ส่งออก) ผู้ใช้ทุกคนต้องสมัครใหม่หรือรีเซ็ตรหัสผ่าน

**คำแนะนำ**: บันทึกผลการตรวจนี้ไว้เป็นแผนหลังส่งโครงงาน ไม่ใช่งานก่อนส่ง
เหตุผลอยู่ในข้อ 15 ข้อ F

---

## 2. Current Architecture

```
                   ┌──────────── Caddy (80 / 443) ────────────┐
โดเมน HTTPS        │ /api/chat             → backend /chat-web │
stpnru-advisor…    │ /api/sci-connect-news*→ webapi:3001       │
                   │ /api/admin/*          → webapi:3001       │
                   │ /api/*                → backend:8000      │
                   │ /assets/* และที่เหลือ  → /srv/web (SPA)    │
http://<IP>:80     │ ทุกเส้นทาง             → frontend:3000     │
                   └──────────────────────────────────────────┘

ระบบ A — Supabase (ของทีมออกแบบ)          ระบบ B — FastAPI + PostgreSQL (ของเรา)
──────────────────────────────────         ─────────────────────────────────────
SPA (bundle เท่านั้น ไม่มี source ใน repo)   Next.js frontend/ (ไม่มี dependency ของ Supabase เลย)
  เรียก Supabase ตรงจากเบราว์เซอร์            POST /auth/login · /auth/register
  signInWithPassword / signUp                 token → localStorage "course_advisor_token"
  resetPasswordForEmail / updateUser          Authorization: Bearer <FastAPI JWT HS256>
  getSession / onAuthStateChange
       │                                              │
       ▼                                              ▼
webapi:3001 (Node · 10 ไฟล์ 478 บรรทัด)       backend:8000 (FastAPI)
  _lib/adminAuth.js → supabase.auth.getUser    deps.py → decode_token() ด้วย JWT_SECRET ของเรา
  คุม /api/admin/* 3 เส้นทาง                    require_admin() คลุม /crawl-review ทั้ง router
       │                                              │
       ▼                                              ▼
Supabase (7 ตาราง + auth.users               PostgreSQL 16 + pgvector
  + RPC + Edge Function + Storage)              public: 10 ตาราง
  courses · user_profiles · news                mko:    20 ตาราง + 8 view
  external_news · knowledge_articles            56 FK · 68 check constraint
  rag_documents (vector 768) · ai_settings      course_chunks vector(1024) 174 MB
```

**ไม่มีเส้นใดลากข้ามระหว่างสองคอลัมน์** — ยืนยันซ้ำในรอบนี้

จุดเดียวที่สองฝั่งมาบรรจบคือ **Caddy** ซึ่งเป็นตัวแยกเส้นทางเท่านั้น ไม่ได้แชร์ข้อมูล

---

## 3. PostgreSQL Inventory

**VERIFIED FROM DATABASE** — อ่านจาก production เมื่อ 2026-10-01 ด้วย `pg_class`,
`pg_constraint`, `pg_index`, `pg_attribute` และนับแถวจริงด้วย `query_to_xml`

### 3.1 ภาพรวม

| schema | table | view | รวม |
|---|---:|---:|---:|
| `public` | 10 | 0 | 10 |
| `mko` | 20 | 8 | 28 |
| **รวม** | **30** | **8** | **38** |

PostgreSQL 16.15 · extension `vector` (pgvector) · `citext`

### 3.2 ตารางและจำนวนแถวจริง

| schema.table | ขนาด | แถว | หน้าที่ |
|---|---|---:|---|
| `public.course_chunks` | **174 MB** | **9,039** | ก้อนข้อความ + embedding สำหรับ RAG |
| `public.chat_messages` | 4.5 MB | 6,640 | ประวัติข้อความแชท |
| `public.chat_sessions` | 440 kB | 3,424 | เซสชันแชท |
| `public.users` | 96 kB | 198 | บัญชีผู้ใช้ของ FastAPI |
| `public.chat_answer_cache` | 720 kB | 160 | แคชคำตอบตาม `question_key` + `corpus_version` |
| `public.recommendations` | 96 kB | 53 | ผลการแนะนำหลักสูตร |
| `public.course_documents` | 80 kB | 31 | เอกสารต้นฉบับ (PDF) |
| `public.courses` | 104 kB | 24 | หลักสูตร |
| `public.user_profiles` | 32 kB | 11 | โปรไฟล์การศึกษา/อาชีพ (ของเรา) |
| `public.user_requirements` | 64 kB | 10 | เงื่อนไขที่ผู้ใช้ระบุ |
| `mko.document_pages` | **11 MB** | 4,129 | ข้อความรายหน้าของเอกสาร |
| `mko.evidence` | 600 kB | 787 | หลักฐานอ้างอิงตำแหน่งในเอกสาร |
| `mko.shadow_answers` | 1 MB | 501 | บันทึกเทียบคำตอบ structured vs RAG |
| `mko.field_values` | 352 kB | 403 | ค่าฟิลด์ที่สกัดได้ |
| `mko.published_values` | 200 kB | 398 | ค่าที่เผยแพร่แล้ว |
| `mko.published_list_items` | 232 kB | 330 | รายการที่เผยแพร่แล้ว |
| `mko.list_items` | 360 kB | 294 | รายการที่สกัดได้ |
| `mko.document_sections` | 112 kB | 203 | หัวข้อในเอกสาร |
| `mko.field_value_evidence` | 56 kB | 137 | ตารางเชื่อมค่า↔หลักฐาน |
| `mko.review_decisions` | 112 kB | 37 | การตัดสินของผู้ตรวจ |
| `mko.extraction_runs` | 96 kB | 31 | รอบการสกัด |
| `mko.curricula` | 96 kB | 24 | หลักสูตรเชิงโครงสร้าง |
| `mko.crawl_sources` | 152 kB | 12 | สถานะไฟล์บนเว็บคณะ |
| `mko.publications` | 32 kB | 4 | รอบการเผยแพร่ |
| `mko.schema_migrations` | 32 kB | 4 | migration 001–004 |
| `mko.crawl_decisions` | 40 kB | **0** | การอนุมัติ/ไม่สนใจ (append-only) |
| `mko.programs` · `subjects` · `credit_groups` · `learning_outcomes` | 16–24 kB | **0** | ตารางที่เตรียมไว้ ยังไม่ใช้ |

**view ของ `mko` 8 รายการ**: `v_crawl_pending` · `v_crawl_queue` · `v_live_list_items` ·
`v_live_publication` · `v_live_values` · `v_published_curricula` · `v_published_field_values` ·
`v_published_list_items`

### 3.3 คอลัมน์ของตารางหลัก

**`public.users`** — PK `id uuid DEFAULT gen_random_uuid()`

| col | type | หมายเหตุ |
|---|---|---|
| `id` | `uuid` NOT NULL | PK |
| `email` | **`citext`** NOT NULL | UNIQUE (`users_email_key`) — เทียบแบบไม่สนตัวพิมพ์ |
| `password_hash` | `text` NOT NULL | bcrypt |
| `full_name` | `text` | |
| `is_active` | `boolean` NOT NULL DEFAULT true | |
| `is_admin` | `boolean` NOT NULL DEFAULT false | **สิทธิ์ admin อยู่ที่นี่** |
| `created_at` / `updated_at` | `timestamptz` NOT NULL DEFAULT now() | |

**`public.courses`** — PK `id uuid` · UNIQUE `code`

`code text` · `title text NOT NULL` · `provider text` · `summary text` · `mode text` ·
`duration_weeks numeric` · `price numeric` · `currency text DEFAULT 'THB'` ·
`tags jsonb NOT NULL DEFAULT '[]'` (index GIN `idx_courses_tags`) ·
`is_active boolean NOT NULL DEFAULT true` · `created_at` / `updated_at`

**`public.course_documents`** — PK `id uuid` · UNIQUE `(course_id, file_sha256)`

`course_id uuid NOT NULL` → FK `courses` CASCADE · `original_filename text NOT NULL` ·
`file_sha256 text NOT NULL` · `storage_path text NOT NULL` · `page_count integer` ·
`extraction_status text NOT NULL DEFAULT 'pending'` · `extraction_error text` ·
`uploaded_by uuid` → FK `users` · `uploaded_at timestamptz NOT NULL`

**`public.course_chunks`** — PK `id uuid` · UNIQUE `(document_id, chunk_index)`

`course_id uuid NOT NULL` → FK `courses` CASCADE · `document_id uuid NOT NULL` → FK
`course_documents` CASCADE · `chunk_index integer NOT NULL` · `page_number integer` ·
`content text NOT NULL` · `token_count integer` · **`embedding vector(1024) NOT NULL`** ·
`metadata jsonb NOT NULL DEFAULT '{}'` · `created_at timestamptz NOT NULL`

**`public.chat_messages`** — PK `id uuid` · `session_id uuid NOT NULL` → FK `chat_sessions`
CASCADE · `role text NOT NULL` (CHECK `chat_messages_role_check`) · `content text NOT NULL` ·
`created_at timestamptz NOT NULL` · index `idx_chat_messages_session (session_id)`

**`public.chat_answer_cache`** — PK **`question_key text`** (ไม่ใช่ uuid)
`corpus_version text NOT NULL` (index `idx_chat_answer_cache_version`) · `status text NOT NULL` ·
`reply text NOT NULL` · `citations jsonb NOT NULL DEFAULT '[]'` · `hits integer NOT NULL DEFAULT 0` ·
`created_at` / `last_used_at timestamptz NOT NULL DEFAULT now()`

**`public.user_profiles`** (ของเรา) — PK `user_id uuid` → FK `users` CASCADE
`education_level` · `field_of_study` · `current_role` · `career_goal` · `skills jsonb` ·
`interests jsonb` · `language_preference text DEFAULT 'th'` · `metadata jsonb` · `updated_at`

> **กับดักชื่อซ้ำ** — Supabase ก็มีตารางชื่อ `user_profiles` แต่เก็บ `role`/`status`
> สำหรับคุมสิทธิ์ admin **ความหมายต่างกันโดยสิ้นเชิง** ดูข้อ 7

### 3.4 Constraint

| ชนิด | จำนวน |
|---|---:|
| foreign key | **56** |
| check constraint | **68** กระจายใน 20 ตาราง |
| unique index | 7 ในตารางหลัก (`users.email`, `courses.code`, `(course_id,file_sha256)`, `(document_id,chunk_index)` ฯลฯ) |

**ตารางที่ constraint หนาที่สุด**: `mko.crawl_sources` (9 check) · `mko.crawl_decisions` (7) ·
`mko.curricula` (6) · `mko.list_items` (5) · `mko.field_values` (4) · `mko.shadow_answers` (4) ·
`mko.published_list_items` (4)

**ข้อค้นพบสำคัญ**: `mko` มี **19 FK ที่ชี้เข้า `public.courses` และ `public.course_documents`**
สองสคีมานี้จึง **เป็นฐานข้อมูลเดียวกันและผูกกันแน่นอยู่แล้ว** ไม่มีอะไรต้อง "รวม"
การรวมที่เป็นประเด็นจริงคือ Supabase → PostgreSQL เท่านั้น

### 3.5 pgvector — ยืนยันจากฐานข้อมูลและจาก source

| รายการ | ค่าที่ยืนยันแล้ว | ยืนยันจาก |
|---|---|---|
| คอลัมน์ vector ทั้งฐานข้อมูล | **มีคอลัมน์เดียว** `public.course_chunks.embedding` | `pg_attribute` + `pg_type.typname='vector'` |
| ชนิด | `vector(1024)` **NOT NULL** · `atttypmod = 1024` | ฐานข้อมูล |
| index | `idx_course_chunks_embedding` · method **`ivfflat`** | `pg_index` + `pg_am` |
| นิยาม index | `USING ivfflat (embedding vector_cosine_ops) WITH (lists='100')` | `pg_get_indexdef()` |
| ตัวดำเนินการที่โค้ดใช้ | **`<=>` cosine distance** — `CourseChunk.embedding.cosine_distance(...)` | `backend/app/services/vector_search.py:24,27` |
| โมเดลที่สัญญาบังคับ | `REQUIRED_EMBED_MODEL = "bge-m3"` | `pipeline/crawl/approve.py:75` |
| มิติที่สัญญาบังคับ | `REQUIRED_EMBED_DIM = 1024` | `pipeline/crawl/approve.py:76` |
| การบังคับตอนรัน | `embed_model_mismatch` / `embed_dim_mismatch` ก่อนนำเข้า | `approve.py:112-119` |

ไม่มีค่าใดในตารางนี้มาจากการอนุมาน

### 3.6 ไฟล์ source ที่แตะแต่ละตาราง

| ตาราง | จำนวนไฟล์ใน `backend/app`, `pipeline`, `llm` |
|---|---:|
| `courses` | 25 |
| `course_documents` | 16 |
| `course_chunks` | 13 |
| `users` | 6 |
| `chat_messages` | 3 · `recommendations` 3 |
| `chat_sessions` 2 · `user_profiles` 2 · `user_requirements` 2 | |
| `chat_answer_cache` | 1 |

`mko.*` ที่ **backend** (ไม่ใช่แค่ pipeline) แตะ: `crawl_sources` (7) · `shadow_answers` (5) ·
`crawl_decisions` (5) · `v_live_values` (4) · `v_crawl_queue` (4) · `v_live_list_items` (2)

---

## 4. Supabase Inventory

> **สถานะการยืนยัน** — ไม่มีสิทธิ์เข้าถึงฐานข้อมูล Supabase และการขอเข้าถึงอยู่นอกขอบเขต
> READ-ONLY รอบนี้ ทุกอย่างในหัวข้อนี้จึงเป็น **VERIFIED FROM SOURCE** เว้นที่ระบุว่า UNKNOWN
> schema จริง (type, PK, FK, index, RLS policy, จำนวนแถว) **ยังไม่ได้ยืนยัน**

### 4.1 ตารางที่ source อ้างถึง

| ตาราง | ใครเรียก | คอลัมน์ที่เห็นในโค้ด | สถานะ |
|---|---|---|---|
| `courses` | SPA (~15 จุด) | `id, title, title_en, description, logo, careers` และ `select("*")` | VERIFIED FROM SOURCE |
| `user_profiles` | SPA (~9) + `webapi/_lib/adminAuth.js` | `user_id, full_name, email, role, status, id` | VERIFIED FROM SOURCE |
| `knowledge_articles` | SPA (~6) | `id, title, created_at` | VERIFIED FROM SOURCE |
| `news` | SPA (~6) | `id, title, date` | VERIFIED FROM SOURCE |
| `external_news` | `webapi/sci-connect-news.js`, `…-detail.js` | `slug, title, description, image_url, published_text, published_at, detail_url, facebook_url` | VERIFIED FROM SOURCE |
| `rag_documents` | SPA (~4) + `webapi/_lib/ingest.js`, `rag.js` | `source_type, source_id, title, content, chunk_index, embedding, updated_at` | VERIFIED FROM SOURCE |
| `ai_settings` | SPA (~3) + `webapi/_lib/aiConfig.js` | `id` (ใช้ `.eq('id',1)` — ตารางเดี่ยว), `model` | VERIFIED FROM SOURCE |
| `auth.users` | Supabase Auth | `id` (uuid) ใช้เป็น `user_profiles.user_id` | VERIFIED FROM SOURCE |

**`news` กับ `external_news` เป็นคนละตาราง** — SPA อ่าน `news`, webapi อ่าน `external_news`
ความสัมพันธ์ระหว่างสองตารางนี้ **UNKNOWN**

### 4.2 สิ่งที่ไม่ใช่ตาราง

| รายการ | รายละเอียด | สถานะ |
|---|---|---|
| RPC `match_rag_documents` | พารามิเตอร์ `query_embedding`, `match_count`, `filter_source_type` · คืน `source_type, source_id, title, content` | VERIFIED FROM SOURCE (`_lib/rag.js:39-43`) |
| Edge Function `sync-sci-news` | เรียกผ่าน `${url}/functions/v1/sync-sci-news` ด้วย anon key | VERIFIED FROM SOURCE (`admin/sync-sci-news.js:18-22`) |
| Supabase Storage | พบ `storage.from` ใน bundle (18 ครั้งใน 4 bundle ≈ 4–5 จุดเรียก) | **ชื่อ bucket และการใช้งาน UNKNOWN** — bundle ถูก minify จนดึงชื่อออกมาไม่ได้ |
| Edge Function อื่น | พบ `functions/v1` ใน bundle 4 ครั้ง | **UNKNOWN** ว่ามีฟังก์ชันอื่นนอกจาก `sync-sci-news` |
| RLS policy | โค้ดใช้ **anon key เท่านั้น** (ไม่มี service-role key ที่ใดเลย) และคอมเมนต์ใน `adminAuth.js:6-7` ระบุว่าตั้งใจให้ RLS บังคับด้วยตัวตนจริงของผู้เรียก | **สรุปได้ว่า RLS เป็นชั้นความปลอดภัยที่รับน้ำหนักจริง** · ตัว policy เอง UNKNOWN |
| จำนวนแถวทุกตาราง | — | **UNKNOWN** · มีเพียง backup เก่า `docs/backups/supabase_courses_backup_20260923.json` ขนาด 1,006 ไบต์ (3 คีย์) ซึ่งเล็กมาก |

### 4.3 RAG ของฝั่ง Supabase — ยืนยันจาก source ครบ

```javascript
// webapi/_lib/rag.js:5-7
// Must match the `vector(768)` column + match_rag_documents RPC in supabase_migration_rag.sql
const EMBEDDING_MODEL = 'gemini-embedding-001';
const EMBEDDING_DIMENSIONS = 768;
```

| รายการ | ค่า |
|---|---|
| โมเดล | `gemini-embedding-001` (Google · ผ่าน `@ai-sdk/google`) |
| มิติ | **768** |
| taskType | `RETRIEVAL_QUERY` ตอนค้น · `RETRIEVAL_DOCUMENT` ตอนเก็บ |
| ขนาด chunk | 800 ตัวอักษร · overlap 100 (`_lib/ingest.js:89-90`) |
| unique key | `(source_type, source_id, chunk_index)` — จาก `onConflict` ของ upsert |
| `source_type` ที่อนุญาต | `major`, `news`, `article`, `knowledge` (`admin/ingest.js:4`) |
| ไฟล์ migration ที่อ้างถึง | `supabase_migration_rag.sql` — **ไม่อยู่ใน repo นี้** |

### 4.4 Environment variable (ชื่อเท่านั้น — ไม่แสดงค่า)

```
VITE_SUPABASE_URL
VITE_SUPABASE_ANON_KEY
GOOGLE_GENERATIVE_AI_API_KEY      (docker-compose.prod.yml · ค่าว่างได้)
```

**ไม่พบ service-role key ที่ใดเลย** — ยืนยันว่าทุกการเข้าถึง Supabase ใช้ anon key
ซึ่งหมายความว่า RLS คือสิ่งที่กันข้อมูลอยู่จริง

### 4.5 ที่อยู่ของ source แต่ละส่วน

| ส่วน | อยู่ที่ไหน | อยู่ใน git ไหม |
|---|---|---|
| `webapi/server.mjs` (ตัวครอบ) | repo | **ใช่** |
| `webapi/api/**` (10 ไฟล์ 478 บรรทัด) | เฉพาะในคอนเทนเนอร์ production `/app/api` | **ไม่** — `.gitignore:49` กัน `webapi/api/` |
| SPA source | **ไม่พบที่ใด** | **ไม่** — `.gitignore:45` กัน `/web/` |
| SPA bundle | `/home/ubuntu/course-advisor-system/web` (40 ไฟล์ 8.5 MB) mount เป็น `/srv/web:ro` ใน Caddy | ไม่ |
| `supabase_migration_rag.sql` | **ไม่พบ** | ไม่ |

---

## 5. Authentication Architecture

### 5.1 ระบบ A — Supabase Auth

| หัวข้อ | รายละเอียด | ยืนยันจาก |
|---|---|---|
| สมัคร | `supabase.auth.signUp()` เรียกจากเบราว์เซอร์ | bundle (8 ครั้ง ≈ 2 จุด) |
| เข้าสู่ระบบ | `signInWithPassword()` จากเบราว์เซอร์ | bundle (8) |
| ลืมรหัสผ่าน | `resetPasswordForEmail()` | bundle (8) |
| แก้บัญชี | `updateUser()` | bundle (22) |
| คงสถานะ | `getSession()` (74) · `onAuthStateChange()` (24) | bundle |
| รูปแบบ token | JWT ที่ Supabase ออก | — |
| การตรวจ token | `supabase.auth.getUser(token)` — เรียกกลับไปที่ Supabase | `adminAuth.js:25` |
| ตาราง user | `auth.users` (ของ Supabase) | source |
| ตาราง profile | `user_profiles` · `user_id` → `auth.users.id` | `adminAuth.js:31-34` |
| สิทธิ์ admin | `role ∈ {'admin','editor'}` **และ** `status = 'approved'` | `adminAuth.js:3,36` |
| เส้นทางที่คุ้มครอง | `/api/admin/extract-file` · `/api/admin/ingest` · `/api/admin/sync-sci-news` | `server.mjs:19-21` |
| frontend ที่พึ่งพา | SPA ทั้งตัว (หน้า login/register/reset/admin) | bundle |

### 5.2 ระบบ B — FastAPI + PostgreSQL Auth

| หัวข้อ | รายละเอียด | ยืนยันจาก |
|---|---|---|
| สมัคร | `POST /auth/register` (เปิดสาธารณะ) | route list |
| เข้าสู่ระบบ | `POST /auth/login` | route list |
| hash รหัสผ่าน | bcrypt บน `base64(sha256(utf8(pw)))` cost 12 | `core/security.py` |
| รูปแบบ token | JWT **HS256** · claims `sub`/`type`/`iat`/`exp` · **ไม่ตรวจ `iss`/`aud`** | `core/security.py` |
| เก็บ token ที่ไหน | `localStorage` คีย์ `course_advisor_token` | `frontend/` (7 จุด) |
| ตาราง user | `public.users` (198 แถว) | ฐานข้อมูล |
| สิทธิ์ admin | `public.users.is_admin` (boolean) · ปัจจุบัน admin = **1 คน** | ฐานข้อมูล |
| การตรวจ | `deps.py` → `decode_token()` → โหลด `User` ใหม่ทุกคำขอ | source |
| เส้นทางที่คุ้มครอง | `require_admin` คลุม **router `/crawl-review` ทั้งตัว** (6 เส้นทาง) | `crawl_review.py:53` |
| frontend ที่พึ่งพา | Next.js `frontend/` — หน้า `/crawl-review` (29 จุดอ้างอิง) | source |

### 5.3 เส้นทางที่ไม่มี auth เลย

`POST /api/chat` → Caddy rewrite → `POST /chat-web` **ไม่ต้องยืนยันตัวตน**
ใช้บัญชีกลาง `SHARED_USER_EMAIL = "public-web@stpnru.local"` (`web_compat.py:38`)
และกัน abuse ด้วย `web_rate_limiter` เท่านั้น (`web_compat.py:167`)

**ผลต่อการรวมระบบ**: ฟีเจอร์แชทของ SPA **ไม่ได้พึ่ง Supabase Auth เลย** อยู่แล้ว
นี่เป็นข่าวดี — ส่วนที่ผู้ใช้ทั่วไปใช้มากที่สุดไม่ผูกกับ auth ที่จะย้าย

### 5.4 ถ้าเอา Supabase Auth ออก — อะไรพัง

| พัง | ความรุนแรง |
|---|---|
| หน้า login / register / reset password ของ SPA | **พังทั้งหมด** |
| `/api/admin/*` 3 เส้นทาง (`adminAuth.js` เรียก `supabase.auth.getUser`) | **พังทั้งหมด** |
| การอ่าน/เขียน 6 ตารางจากเบราว์เซอร์ที่พึ่ง RLS ตามตัวตนผู้ใช้ | **พังหรือเปิดโล่ง** |
| RAG ของ SPA (`rag_documents` + RPC) ถ้า RLS ผูกกับผู้ใช้ | ขึ้นกับ policy — **UNKNOWN** |
| `/api/chat` (แชทของผู้ใช้ทั่วไป) | **ไม่พัง** — ไม่ได้ใช้ auth อยู่แล้ว |
| `/api/sci-connect-news*` | **ไม่พัง** — ไม่ผ่าน `requireAdminUser` |

### 5.5 ถ้าเอา FastAPI Auth ออก — อะไรพัง

| พัง | ความรุนแรง |
|---|---|
| `/crawl-review/*` ทั้ง 6 เส้นทาง (คิวตรวจ · เปิด PDF · approve/ignore/undo) | **พังทั้งหมด** — Phase 3 ใช้งานไม่ได้เลย |
| หน้า `/crawl-review` ใน Next.js | **พังทั้งหมด** |
| `/auth/me`, `/me/profile`, `/me/requirements` | **พังทั้งหมด** |
| `chat_sessions.user_id` → FK `users` (3,424 แถว) | FK ชี้ไปตารางที่จะหาย — **ต้องย้ายข้อมูลก่อน** |
| `recommendations.user_id`, `user_requirements.user_id`, `user_profiles.user_id`, `course_documents.uploaded_by` | FK ทั้งสี่ชี้ `users` |
| `/api/chat` | **ไม่พัง** แต่บัญชีกลางอยู่ใน `users` จึงต้องมีที่อยู่ใหม่ |

**ข้อสรุป**: `public.users` มี **5 FK ชี้เข้ามา** และเป็นรากของข้อมูลแชท 6,640 ข้อความ
การถอด FastAPI Auth แพงกว่าการถอด Supabase Auth อย่างชัดเจน

---

## 6. Data Access Map

```
ผู้ใช้ทั่วไป ─ เบราว์เซอร์ ─┬─> SPA (/srv/web)
                           │     │
                           │     ├─ supabase-js ─> Supabase: courses            [แสดงหลักสูตร]
                           │     ├─ supabase-js ─> Supabase: news               [ข่าว]
                           │     ├─ supabase-js ─> Supabase: knowledge_articles [บทความ]
                           │     ├─ supabase-js ─> Supabase: rag_documents      [RAG ของ SPA]
                           │     ├─ supabase-js ─> Supabase: ai_settings        [เลือกโมเดล]
                           │     ├─ supabase-js ─> Supabase: user_profiles      [role/status]
                           │     ├─ supabase.auth ─> Supabase auth.users        [login/register]
                           │     ├─ supabase.storage ─> ? bucket UNKNOWN        [ไฟล์]
                           │     │
                           │     ├─ POST /api/chat ──Caddy──> backend /chat-web ──> PostgreSQL
                           │     │        (ไม่มี auth · บัญชีกลาง public-web@stpnru.local)
                           │     │        └─> course_chunks (pgvector) · chat_sessions
                           │     │            chat_messages · chat_answer_cache · mko.v_live_*
                           │     │
                           │     ├─ GET /api/sci-connect-news ──> webapi ──> Supabase: external_news
                           │     └─ GET /api/sci-connect-news-detail ──> webapi ──> external_news
                           │
ผู้ดูแล (SPA) ──────────────┘
                                 POST /api/admin/ingest        ──> webapi ─ adminAuth ─> user_profiles
                                                                        └─> rag_documents (embed 768)
                                 POST /api/admin/extract-file  ──> webapi ─ adminAuth
                                 POST /api/admin/sync-sci-news ──> webapi ─ adminAuth
                                                                        └─> Edge Function sync-sci-news

ผู้ดูแล (ของเรา) ─ เบราว์เซอร์ ──> Next.js frontend:3000
                                   ├─ POST /auth/login ──> backend ──> public.users (bcrypt + HS256)
                                   └─ /crawl-review ──> backend (require_admin)
                                         ├─ GET  /crawl-review/pending        ──> mko.v_crawl_queue
                                         ├─ GET  /crawl-review/{id}           ──> mko.crawl_sources
                                         ├─ GET  /crawl-review/{id}/pdf       ──> staging/crawl (ไฟล์)
                                         ├─ POST /crawl-review/{id}/approve   ──> mko.crawl_decisions
                                         ├─ POST /crawl-review/{id}/ignore    ──> mko.crawl_decisions
                                         └─ POST /crawl-review/{id}/undo      ──> mko.crawl_decisions

crawler / worker (สั่งด้วยมือ) ──> mko.crawl_sources · mko.crawl_decisions
                                   course_documents · course_chunks (embed 1024 ด้วย bge-m3)

เอกสาร PDF ──> GET /documents/{id}/pdf ──> backend ──> documents/ (ไฟล์บนดิสก์)
```

### 6.1 ฟีเจอร์ต่อฐานข้อมูล

| ฟีเจอร์ | ฐานข้อมูลที่ใช้ | หมายเหตุ |
|---|---|---|
| AI chat | **PostgreSQL** | `course_chunks` + `chat_*` + `mko.v_live_*` |
| ข้อมูลหลักสูตร (SPA) | **Supabase** `courses` | คนละตารางกับ `public.courses` |
| ข้อมูลหลักสูตร (คำตอบของ AI) | **PostgreSQL** `courses` + `mko.*` | |
| recommendation | **PostgreSQL** | `recommendations`, `user_requirements` |
| compare courses | **PostgreSQL** | `POST /compare-courses` |
| Sci Connect news | **Supabase** `external_news` | ผ่าน webapi |
| news / บทความ (SPA) | **Supabase** `news`, `knowledge_articles` | |
| admin ของ SPA | **Supabase** `user_profiles` + `rag_documents` | |
| crawl review | **PostgreSQL** `mko.*` | |
| auth ของ SPA | **Supabase** `auth.users` | |
| auth ของเรา | **PostgreSQL** `public.users` | |
| เปิด PDF | ไฟล์บนดิสก์ + **PostgreSQL** `course_documents` | |

---

## 7. Overlap Analysis

| ข้อมูล | Supabase | PostgreSQL | ประเภทการทับ | เหตุผล |
|---|---|---|---|---|
| ผู้ใช้ | `auth.users` + `user_profiles(role,status)` | `public.users(is_admin)` + `public.user_profiles(การศึกษา)` | **PARTIALLY OVERLAPPING** | ทั้งสองเก็บตัวตนผู้ใช้และสิทธิ์ แต่ชุดผู้ใช้ไม่เหมือนกัน (`<OWNER_EMAIL>` อยู่ใน Supabase หาไม่เจอใน `public.users` — เหตุที่ Step 3.5 เคยหยุด) · `id` เป็น uuid ทั้งคู่แต่ **ค่าไม่เกี่ยวกัน** |
| ชื่อตาราง `user_profiles` | `user_id, full_name, email, role, status` | `user_id, education_level, field_of_study, career_goal, skills, interests` | **DIFFERENT PURPOSE** | ชื่อเดียวกันแต่ไม่มีคอลัมน์ร่วมนอกจาก `user_id` · **ห้ามถือว่าเป็นตารางเดียวกัน** |
| หลักสูตร | `courses(id,title,title_en,description,logo,careers)` | `courses(code,title,provider,summary,mode,duration_weeks,price,currency,tags)` | **PARTIALLY OVERLAPPING** | ทับกันที่ `id`, `title` เท่านั้น · ฝั่ง Supabase เน้นการแสดงผลบนเว็บ (โลโก้ อาชีพ คำบรรยาย) ฝั่งเราเน้นข้อมูลหลักสูตรเชิงข้อเท็จจริง · **ยังไม่ยืนยันว่าแถวตรงกันหรือไม่** |
| RAG / embedding | `rag_documents` vector(768) gemini | `course_chunks` vector(1024) bge-m3 | **DIFFERENT PURPOSE** (และเข้ากันไม่ได้) | ขอบเขตเนื้อหาต่างกัน (ของเพื่อนครอบ major/news/article/knowledge · ของเราครอบเฉพาะเอกสารหลักสูตร) และ **vector เทียบกันไม่ได้เลย** |
| ข่าว | `news` (SPA) และ `external_news` (webapi) | ไม่มี | **UNKNOWN** | สองตารางในฝั่ง Supabase เอง ความสัมพันธ์ยังไม่ยืนยัน · ฝั่งเราไม่มีข่าวเลย |
| บทความ | `knowledge_articles` | ไม่มี | **DIFFERENT PURPOSE** | ฝั่งเราไม่มี |
| ตั้งค่า AI | `ai_settings(id=1, model)` | ค่าอยู่ใน env + `llm/connector.py` | **PARTIALLY OVERLAPPING** | ทำเรื่องเดียวกัน (เลือกโมเดล) ด้วยกลไกต่างกัน |
| สิทธิ์ admin | `user_profiles.role ∈ {admin,editor}` + `status='approved'` | `users.is_admin` boolean | **PARTIALLY OVERLAPPING** | ฝั่ง Supabase มีสองระดับ (admin/editor) + สถานะรออนุมัติ · ฝั่งเรามีแค่ใช่/ไม่ใช่ · **การรวมต้องตัดสินว่าจะเก็บโมเดลไหน** |
| ไฟล์ / Storage | Supabase Storage (bucket UNKNOWN) | ไฟล์บนดิสก์ `documents/`, `staging/crawl` + `course_documents.storage_path` | **UNKNOWN** | ยังไม่รู้ว่า Supabase Storage เก็บอะไร |

**ไม่มีคู่ใดที่เป็น IDENTICAL** — ไม่มีตารางใดที่ย้ายข้ามได้โดยไม่ต้องแปลง

---

## 8. Proposed Target Architecture

ยึดหลัก **เก็บโครงสร้าง PostgreSQL ที่พิสูจน์แล้วไว้ ไม่ออกแบบใหม่ทั้งหมด**

```
PostgreSQL 16 + pgvector  (ฐานเดียว)
│
├── schema public         ── คงไว้ทั้งหมด ไม่แก้ (10 ตาราง · 198 users · 9,039 chunks)
│     users · user_profiles · user_requirements · courses · course_documents
│     course_chunks(vector 1024) · chat_sessions · chat_messages
│     chat_answer_cache · recommendations
│
├── schema mko            ── คงไว้ทั้งหมด ไม่แก้ (20 ตาราง · 8 view · 56 FK)
│     crawl_sources · crawl_decisions · curricula · document_pages · …
│
└── schema web            ── ใหม่: ของที่ย้ายมาจาก Supabase
      web.site_courses         <- Supabase courses        (ข้อมูลเพื่อการแสดงผล)
      web.news                 <- Supabase news
      web.external_news        <- Supabase external_news
      web.knowledge_articles   <- Supabase knowledge_articles
      web.ai_settings          <- Supabase ai_settings
      web.user_roles           <- Supabase user_profiles(role,status)
      web.storage_objects      <- Supabase Storage metadata (ถ้ามี)
```

### 8.1 เหตุผลของการใช้ schema `web` แยก

1. **ไม่แตะของที่ทำงานอยู่** — `public` และ `mko` ไม่ต้องเปลี่ยนแม้คอลัมน์เดียว
   ความเสี่ยงต่อ RAG, crawler, chat จึงเป็นศูนย์
2. **เลี่ยงชื่อชนกันสองคู่** — `courses` และ `user_profiles` มีอยู่แล้วทั้งสองฝั่ง
   ถ้ายัดลง `public` จะต้องเปลี่ยนชื่อหรือรวมตาราง ซึ่งทั้งสองทางแตะของที่ใช้งานอยู่
3. **ถอนกลับง่าย** — `DROP SCHEMA web CASCADE` ไม่กระทบอะไรเลย
4. ตั้งชื่อ `web.site_courses` ไม่ใช่ `web.courses` เพื่อให้คนอ่าน query แล้วรู้ทันทีว่า
   เป็นข้อมูลเพื่อแสดงบนเว็บ ไม่ใช่ข้อเท็จจริงของหลักสูตร

### 8.2 ตารางที่เสนอ

**`web.user_roles`** — แทน Supabase `user_profiles`

```
user_id   uuid PRIMARY KEY REFERENCES public.users(id) ON DELETE CASCADE
role      text NOT NULL CHECK (role IN ('admin','editor','viewer'))
status    text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected'))
created_at / updated_at  timestamptz NOT NULL DEFAULT now()
INDEX (role, status) WHERE status = 'approved'
```

> หมายเหตุสำคัญ: ตารางนี้ทำให้มี **สองที่** ที่บอกสิทธิ์ (`users.is_admin` และ
> `web.user_roles.role`) ซึ่งเป็นปัญหาเดิมในรูปใหม่ ทางที่สะอาดกว่าคือย้าย
> `is_admin` มาเป็น `role` ที่เดียว — แต่นั่นแตะ `public.users` และ `require_admin`
> ที่ใช้งานอยู่ **ต้องตัดสินใจก่อนลงมือ** (ดูข้อ 9)

**`web.site_courses`** — แทน Supabase `courses`

```
id            uuid PRIMARY KEY DEFAULT gen_random_uuid()
course_id     uuid REFERENCES public.courses(id) ON DELETE SET NULL   -- เชื่อมถ้าจับคู่ได้
title         text NOT NULL
title_en      text
description   text
logo_url      text
careers       jsonb NOT NULL DEFAULT '[]'
is_published  boolean NOT NULL DEFAULT true
created_at / updated_at
UNIQUE (course_id) WHERE course_id IS NOT NULL
```

คอลัมน์ `course_id` คือสิ่งที่ปัจจุบัน **ไม่มีเลย** — เป็นประโยชน์ที่ได้จากการรวมจริง ๆ
คือเชื่อมข้อมูลแสดงผลกับข้อเท็จจริงของหลักสูตรเข้าด้วยกันได้

**`web.news`, `web.external_news`, `web.knowledge_articles`**

คงคอลัมน์ตามที่ source ใช้ (`slug` UNIQUE สำหรับ `external_news`, `published_at` สำหรับเรียง)
เพิ่ม `id uuid PK`, `created_at/updated_at`, index บนคอลัมน์ที่ใช้เรียงและกรอง

**`web.ai_settings`** — `id smallint PK CHECK (id = 1)` · `model text NOT NULL` · `updated_at`
(คง singleton pattern ที่ `aiConfig.js` คาดไว้)

### 8.3 RAG — ข้อเสนอที่ตรงไปตรงมาที่สุด

**ไม่สร้างตาราง vector ที่สอง** ให้ขยาย `course_chunks` ด้วยที่มาของเนื้อหาแทน

```
ALTER TABLE public.course_chunks
  ADD COLUMN source_kind text NOT NULL DEFAULT 'curriculum'
      CHECK (source_kind IN ('curriculum','news','article','knowledge'));
```

เหตุผล: มี index `ivfflat` ตัวเดียว · มีมิติเดียว (1024) · มีโมเดลเดียว (bge-m3) ·
มีสัญญา `check_embedding_contract()` ตัวเดียวที่บังคับอยู่แล้ว · การค้นข้ามเนื้อหาทุกชนิด
ทำได้ด้วย query เดียว

**แต่ต้องยอมรับว่า**: `document_id NOT NULL` และ FK ไป `course_documents` จะเป็นปัญหา
สำหรับเนื้อหาที่ไม่ใช่ PDF (ข่าว บทความ) จึงต้องผ่อน NOT NULL หรือสร้างแถวตัวแทนใน
`course_documents` — **นี่คือการแตะตารางที่ใช้งานอยู่ และเป็นเหตุผลหนึ่งที่งานนี้ไม่เล็ก**

ทางเลือกที่แตะของเดิมน้อยกว่า: `web.content_chunks` แยกตาราง มี `vector(1024)` และ
`ivfflat` ของตัวเอง แล้ว union กันที่ชั้น query — แลกด้วย index สองตัวและ query ซับซ้อนขึ้น

### 8.4 KEEP / MIGRATE / MERGE / REMOVE

| Supabase | การจัดการ | เหตุผล |
|---|---|---|
| `auth.users` | **MERGE** เข้า `public.users` | ต้องสมัคร/รีเซ็ตใหม่ — hash ย้ายไม่ได้ (ข้อ 10) |
| `user_profiles` | **MIGRATE** → `web.user_roles` | เก็บเฉพาะ `role`, `status` · `full_name`/`email` ซ้ำกับ `public.users` |
| `courses` | **MIGRATE** → `web.site_courses` + พยายามจับคู่ `public.courses` | schema ต่างกันมาก |
| `news` | **MIGRATE** → `web.news` | |
| `external_news` | **MIGRATE** → `web.external_news` | |
| `knowledge_articles` | **MIGRATE** → `web.knowledge_articles` | |
| `ai_settings` | **MIGRATE** → `web.ai_settings` | |
| `rag_documents` | **REMOVE แล้วสร้างใหม่** | **ย้าย vector ไม่ได้** ต้อง embed เนื้อหาใหม่ด้วย bge-m3 |
| RPC `match_rag_documents` | **REMOVE** | แทนด้วย `vector_search.py` ที่มีอยู่แล้ว |
| Edge Function `sync-sci-news` | **MIGRATE** → งานที่รันบนเซิร์ฟเวอร์เราเอง | ต้องเขียนใหม่ |
| Supabase Storage | **UNKNOWN** | ต้องรู้ก่อนว่าเก็บอะไร |
| RLS policies | **REMOVE** → ย้ายการบังคับสิทธิ์ไปที่ชั้น API | ดูข้อ 10 ความเสี่ยงสูง |

---

## 9. Auth Options

### OPTION A — คง Supabase Auth ไว้ ย้ายเฉพาะข้อมูลแอปมา PostgreSQL

| หัวข้อ | รายละเอียด |
|---|---|
| โค้ดที่ต้องแก้ | SPA: เปลี่ยนทุก `supabase.from(...)` เป็นการเรียก API ใหม่ (~39 จุด) · backend: เพิ่ม endpoint ใหม่ราว 10–15 เส้นทาง + ตัวตรวจ Supabase JWT · webapi: เปลี่ยน `adminAuth.js` ให้ตรวจแล้วแมปมาที่ `public.users` |
| ความปลอดภัย | ต้องเขียนตัวตรวจ Supabase JWT ฝั่งเรา (JWKS / shared secret) ให้ถูก · **ต้องตรวจ `iss`/`aud`** ซึ่ง FastAPI ตอนนี้ยังไม่ตรวจเลย · RLS หายไป ต้องย้าย authorization ขึ้น API ให้ครบทุกเส้นทาง |
| ความซับซ้อนการย้าย | **กลาง** — ไม่ต้องย้ายผู้ใช้ ไม่ต้องรีเซ็ตรหัสผ่าน |
| ความเสี่ยง | **กลาง** |
| frontend ที่กระทบ | SPA ทั้งตัว (ยังต้องมี source) · Next.js ไม่กระทบ |
| backend ที่กระทบ | backend + webapi |
| ข้อดีเฉพาะตัว | **ผู้ใช้ไม่ต้องทำอะไรเลย** ไม่มีใครถูกบังคับให้ตั้งรหัสผ่านใหม่ |
| ข้อเสียเฉพาะตัว | ยังเหลือ Supabase เป็น dependency ภายนอก · ยัง "ไม่ได้รวมเป็นหนึ่ง" จริง ๆ |

### OPTION B — ย้าย authentication มาที่ FastAPI/PostgreSQL ทั้งหมด

| หัวข้อ | รายละเอียด |
|---|---|
| โค้ดที่ต้องแก้ | SPA: เขียนชั้น auth ใหม่ทั้งหมด (login/register/reset/session ~6 จุดเรียก + UI) และเปลี่ยนทุก `from(...)` เป็น API (~39 จุด) · backend: เพิ่ม endpoint ของข้อมูลแอป + ขยายโมเดลสิทธิ์จาก `is_admin` เป็น role/status + เพิ่ม flow รีเซ็ตรหัสผ่านทางอีเมล (ปัจจุบัน **ไม่มี**) · webapi: เลิกใช้ Supabase ทั้งไฟล์ |
| ความปลอดภัย | ได้ระบบเดียวที่ตรวจที่เดียว เข้าใจง่ายกว่า · แต่ต้องสร้างสิ่งที่ Supabase ให้ฟรีขึ้นมาเอง: ยืนยันอีเมล · รีเซ็ตรหัสผ่าน · rate limit การ login · ล็อกบัญชี |
| ความซับซ้อนการย้าย | **สูง** — ต้องย้ายผู้ใช้ และ **รหัสผ่านย้ายไม่ได้** |
| ความเสี่ยง | **สูง** |
| frontend ที่กระทบ | SPA ทั้งตัวรวมหน้า auth |
| backend ที่กระทบ | backend (เพิ่มงานมาก) + webapi (รื้อ) |
| ข้อดีเฉพาะตัว | **รวมเป็นฐานเดียวจริง** · ไม่มี dependency ภายนอก · ค่าใช้จ่าย Supabase เป็นศูนย์ · อธิบายในโครงงานได้ง่ายที่สุด |
| ข้อเสียเฉพาะตัว | **ผู้ใช้ทุกคนต้องตั้งรหัสผ่านใหม่** · ต้องเขียน flow อีเมลเองซึ่งตอนนี้ยังไม่มีโครงสร้างรองรับ |

### OPTION C — ไม่เสนอทางที่สาม

Audit นี้ไม่พบหลักฐานใน source ที่สนับสนุนทางที่สาม (เช่น identity mapping สองทาง
หรือ SSO) ว่าคุ้มกว่า A หรือ B ในบริบทนี้ — เพราะตัวขัดขวางหลักคือ **การเข้าถึง source
ของ SPA** ซึ่งไม่ว่าจะเลือกทางไหนก็ต้องแก้ SPA เท่ากัน

ทางที่สมเหตุสมผลและพบหลักฐานรองรับคือ **"ยังไม่รวม"** — คงสถาปัตยกรรมเดิมไว้
แล้วแก้ปัญหาที่เจ็บจริงทีละเรื่องโดยไม่ต้องย้ายฐานข้อมูล (ดูข้อ 15 ข้อ E)

**ยังไม่เลือกและยังไม่ลงมือทำข้อใด** ตามที่สั่ง

---

## 10. Migration Risks

| # | ความเสี่ยง | ระดับ | เหตุผล |
|---|---|---|---|
| R1 | **source ของ SPA ไม่อยู่ในมือ** | **HIGH** | `.gitignore:45` กัน `/web/` · บนเซิร์ฟเวอร์มีแต่ bundle ที่ minify แล้ว · ไม่ว่าเลือกทางไหนต้องแก้ SPA ~39 จุด + ชั้น auth · **ถ้าไม่ได้ source งานนี้เริ่มไม่ได้** |
| R2 | **vector เข้ากันไม่ได้ (768 vs 1024)** | **HIGH** | ต้อง embed `rag_documents` ใหม่ทั้งหมดด้วย bge-m3 · ไม่ใช่การคัดลอก · คุณภาพการค้นหาของ SPA จะเปลี่ยนไปและต้องวัดใหม่ |
| R3 | **รหัสผ่านย้ายไม่ได้ (Option B)** | **HIGH** | Supabase ไม่มี API ส่ง hash ออก · ผู้ใช้ทุกคนต้องสมัครใหม่หรือรีเซ็ต · และ FastAPI **ยังไม่มี flow รีเซ็ตรหัสผ่านทางอีเมลเลย** ต้องสร้างใหม่ |
| R4 | **RLS หายไป** | **HIGH** | โค้ดใช้ anon key เท่านั้น แปลว่าปัจจุบัน RLS คือสิ่งที่กันข้อมูลอยู่จริง · ย้ายมาแล้วต้องเขียน authorization ที่ชั้น API ให้ครบทุกเส้นทาง · **พลาดหนึ่งเส้นทาง = ข้อมูลเปิดโล่ง** · policy จริงยัง UNKNOWN จึงยังไม่รู้ว่าต้องทำอะไรเท่าไหร่ |
| R5 | **ตัวตนผู้ใช้ไม่ตรงกัน** | **HIGH** | `<OWNER_EMAIL>` อยู่ใน Supabase หาไม่เจอใน `public.users` (พบในงาน Step 3.5) · ชุดผู้ใช้สองฝั่งคนละชุด · ต้องตัดสินใจทีละคนว่าใครเป็นใคร |
| R6 | **`user_profiles` ชื่อซ้ำ ความหมายต่าง** | **MEDIUM** | ถ้าใครเขียน migration แบบเทียบชื่อตาราง จะเขียนข้อมูล role/status ทับโปรไฟล์การศึกษา 11 แถว |
| R7 | **โมเดลสิทธิ์ไม่ตรงกัน** | **MEDIUM** | Supabase: `role ∈ {admin,editor}` + `status='approved'` · ของเรา: `is_admin` boolean · ต้องตัดสินว่าเก็บแบบไหน และ `require_admin` ที่ใช้งานอยู่จะต้องเปลี่ยนตาม |
| R8 | **ชนิด id** | **LOW** | ทั้ง `auth.users.id` และ `public.users.id` เป็น `uuid` · ไม่มีปัญหา integer vs uuid · แต่ **ค่าไม่เกี่ยวกัน** จึงต้องแมป ไม่ใช่คัดลอก |
| R9 | **Edge Function `sync-sci-news`** | **MEDIUM** | ต้องเขียนใหม่ให้รันบนเซิร์ฟเวอร์เราเอง · โค้ดของมันอยู่ใน Supabase ไม่ได้อยู่ใน repo |
| R10 | **Supabase Storage** | **MEDIUM** | ยังไม่รู้ว่าเก็บอะไร ขนาดเท่าไหร่ · ถ้าเก็บรูปหลักสูตร/โลโก้ ต้องย้ายไฟล์และแก้ URL ทุกที่ |
| R11 | **FK ที่ชี้ `public.users`** | **MEDIUM** | 5 FK (`chat_sessions` 3,424 · `recommendations` 53 · `user_requirements` 10 · `user_profiles` 11 · `course_documents.uploaded_by`) · การเพิ่ม/แมปผู้ใช้ต้องไม่ทำให้ FK พัง |
| R12 | **API compatibility** | **MEDIUM** | เส้นทาง `/api/sci-connect-news*` และ `/api/admin/*` ต้องคืนรูปร่าง JSON เดิมทุกฟิลด์ ไม่งั้น SPA ที่ยัง deploy อยู่พังทันที |
| R13 | **downtime** | **LOW** | ย้ายทีละตารางได้ · ตารางที่ SPA อ่านอย่างเดียว (news, articles) ย้ายแบบไม่มี downtime ได้ · ส่วน auth ต้องมีช่วงตัดสลับ |
| R14 | **data loss** | **MEDIUM** | ถ้าทำ backup ก่อนทุกครั้งความเสี่ยงต่ำ · แต่ `rag_documents` ที่ต้อง re-embed ถ้าเนื้อหาต้นฉบับไม่ได้เก็บไว้ที่อื่น จะกู้ไม่ได้ |
| R15 | **rollback complexity** | **LOW-MEDIUM** | ถ้าใช้ schema `web` แยก → `DROP SCHEMA web CASCADE` ถอนได้สะอาด · แต่ถ้าแตะ `public.users` หรือ `course_chunks` การถอนจะยากขึ้นมาก |
| R16 | **secret / config** | **MEDIUM** | ต้องจัดการ `VITE_SUPABASE_*` ที่ฝังอยู่ใน bundle ของ SPA ด้วย — anon key อยู่ในไฟล์ที่เบราว์เซอร์โหลดได้อยู่แล้ว การเลิกใช้ต้อง rebuild SPA |
| R17 | **token เข้ากันไม่ได้** | **MEDIUM** | Supabase JWT กับ FastAPI JWT (HS256 ไม่ตรวจ `iss`/`aud`) คนละระบบ · ช่วงเปลี่ยนผ่านถ้ารับทั้งสองแบบ ต้องระวังอย่างยิ่งว่าไม่เผลอยอมรับ token ที่ไม่ควรยอมรับ |

**สรุประดับ**: HIGH 5 · MEDIUM 9 · LOW 2 · LOW-MEDIUM 1

---

## 11. Safe Migration Plan

> แผนนี้ **ไม่ได้ลงมือทำ** และห้ามใช้ production เป็นที่ทดลอง

**Phase 0 — Backup / snapshot**
`pg_dump` ของ `course_advisor` ทั้งก้อน + export ทุกตารางจาก Supabase เป็นไฟล์ +
บันทึก `pg_dump --schema-only` ไว้เทียบ + เก็บ bundle ของ SPA ชุดปัจจุบัน
**จุดถอนกลับ 0**: ยังไม่แตะอะไร

**Phase 1 — Schema preparation**
เขียน migration `005_web_schema.sql` สร้าง `schema web` + ตารางเปล่า + constraint + index
รันใน **environment แยก** (ชุด `sci-advisor-e2e` ที่มีอยู่แล้วใช้ได้ทันที)
**จุดถอนกลับ 1**: `DROP SCHEMA web CASCADE`

**Phase 2 — Data migration ใน environment แยก**
นำ export จาก Supabase เข้า `web.*` · จับคู่ `web.site_courses.course_id` ↔ `public.courses`
แล้ว **รายงานว่าจับคู่ได้กี่แถว จับไม่ได้กี่แถว** · re-embed เนื้อหาของ `rag_documents`
ด้วย bge-m3 แล้ว **วัดคุณภาพการค้นเทียบกับของเดิม** ก่อนไปต่อ
**จุดถอนกลับ 2**: ลบ environment ทิ้ง ไม่กระทบ production

**Phase 3 — API compatibility layer**
เพิ่ม endpoint ใน backend ที่คืน **รูปร่าง JSON เดิมทุกฟิลด์** ที่ SPA คาดไว้
เขียน contract test เทียบ response ของเดิมกับของใหม่ทีละฟิลด์
**จุดถอนกลับ 3**: endpoint ใหม่ไม่มีใครเรียก ลบได้

**Phase 4 — Frontend migration** ← **ต้องมี source ของ SPA ก่อน**
เปลี่ยน `supabase.from(...)` เป็นเรียก API ใหม่ทีละตาราง เริ่มจากตารางอ่านอย่างเดียว
(`news`, `knowledge_articles`) ซึ่งถอนกลับง่ายที่สุด
**จุดถอนกลับ 4**: deploy bundle เดิมกลับ

**Phase 5 — Auth migration** (ถ้าเลือก Option B)
เปิดให้ผู้ใช้ตั้งรหัสผ่านใหม่โดยยังเข้าระบบเดิมได้ · ช่วงเปลี่ยนผ่านรับ token ได้สองแบบ
พร้อมบันทึกว่าใครยังใช้แบบเก่า · ตัดแบบเก่าออกเมื่อเหลือศูนย์
**จุดถอนกลับ 5**: กลับไปรับ Supabase token เท่านั้น

**Phase 6 — Full regression / E2E**
รันชุดที่มีอยู่ทั้งหมด (484 ข้อ) + isolated E2E (107 ข้อ) + ชุดใหม่สำหรับ `web.*`
+ ชุดวัดคุณภาพคำตอบ RAG เทียบก่อน/หลัง
**ห้ามไปต่อถ้ามีข้อใดไม่ผ่าน**

**Phase 7 — Production cutover**
ทีละตาราง ไม่ใช่ทีเดียวทั้งหมด · แต่ละครั้งวัด invariant ก่อน/หลังแบบที่ทำใน Phase 3D
**จุดถอนกลับ 7**: ชี้ SPA กลับไปที่ Supabase (ตารางเดิมยังอยู่ ยังไม่ลบ)

**Phase 8 — Observation period**
อย่างน้อย 2 สัปดาห์ · Supabase ยังอยู่ครบ ไม่ลบอะไร · เทียบจำนวนแถวสองฝั่งทุกวัน

**Phase 9 — Supabase retirement**
ลบเมื่อผ่านช่วงสังเกตแล้วเท่านั้น · เก็บ export ฉบับสุดท้ายไว้ถาวร

---

## 12. Project Impact

| ส่วน | ผลกระทบ | เอกสารที่จะล้าสมัย |
|---|---|---|
| คำอธิบายสถาปัตยกรรม | **เปลี่ยนมาก** — จาก "สองฐานข้อมูล" เป็น "ฐานเดียว" ซึ่งอธิบายง่ายกว่าเดิมมาก | `AUTH_ARCHITECTURE_AUDIT.md` · `PROJECT_HANDOFF_AND_DIAGRAM_GUIDE.md` |
| นำเสนอวิชา Advanced Database | **ดีขึ้น** ถ้าทำเสร็จ — ฐานเดียวที่มี 3 schema, 56 FK, 68 check, pgvector เป็นเรื่องเล่าที่หนักแน่น · **แย่ลงมาก** ถ้าทำไม่เสร็จ เพราะจะมีสถาปัตยกรรมครึ่ง ๆ | `PRESENTATION_*` ทุกฉบับ |
| ER diagram | **ต้องวาดใหม่ทั้งหมด** — เพิ่ม schema `web` และเส้น FK ใหม่ | `ER_DIAGRAM_PUBLIC_SCHEMA.*` (6 ไฟล์) · `docs/database/*` · `SLIDE_DATABASE_STRUCTURE.*` |
| เอกสารฐานข้อมูล | **ต้องเขียนใหม่** | `docs/database/DATABASE_DIAGRAMS_AND_DICTIONARY.md` (82 KB) · `SUBMISSION_AUDIT_DATABASE_COURSE.md` |
| RAG | **ต้องวัดคุณภาพใหม่ทั้งหมด** ถ้ารวม `rag_documents` เข้ามา เพราะเปลี่ยนโมเดล embedding | รายงานผลประเมินทุกฉบับ |
| pgvector | ไม่กระทบ — ยังเป็น 1024/cosine/ivfflat เดิม | — |
| crawler / ingestion | **ไม่กระทบเลย** ถ้าใช้ schema `web` แยก | — |
| authentication | **เปลี่ยนมาก** ถ้าเลือก Option B | `ADMIN_PASSWORD_RECOVERY_PLAN.md` · `PHASE3D_ADMIN_*` |
| รายงาน / สไลด์ที่มีอยู่ | ~15 ไฟล์ที่พูดถึงสองระบบจะต้องแก้ | ดูรายการข้างบน |
| ภาระการทดสอบ | **เพิ่มมาก** — ต้องมีชุดใหม่สำหรับ `web.*` + ชุดวัด RAG ก่อน/หลัง + contract test ของ API | — |

**ข้อสังเกตที่สำคัญต่อโครงงาน**: ตอนนี้เอกสารชุด presentation และ ER diagram
อธิบายสถาปัตยกรรมปัจจุบันไว้ครบและสอดคล้องกัน การเริ่มรวมฐานข้อมูลจะทำให้
เอกสารเหล่านั้นผิดทันที ก่อนที่ของใหม่จะเสร็จ — ช่วงระหว่างนั้นคือช่วงที่อธิบายยากที่สุด

---

## 13. Effort Classification

| งาน | ระดับ | เหตุผลหลัก |
|---|---|---|
| schema migration (สร้าง `web.*`) | **SMALL** | เขียน SQL ตามรูปแบบ migration 001–004 ที่มีอยู่ · ไม่แตะของเดิม · ถอนกลับด้วยคำสั่งเดียว |
| application data migration | **MEDIUM** | ข้อมูลน้อย (ตารางเล็ก) แต่ต้องจับคู่ `courses` สองฝั่งด้วยมือ และยังไม่รู้จำนวนแถวจริงฝั่ง Supabase |
| re-embed `rag_documents` | **MEDIUM** | กลไกมีอยู่แล้วครบ (`pipeline/embed.py`, bge-m3, Ollama) แต่ต้องวัดคุณภาพเทียบของเดิม ซึ่งเป็นงานประเมินไม่ใช่งานเขียนโค้ด |
| frontend changes (SPA) | **LARGE** | ~39 จุดเรียก Supabase + ชั้น auth ทั้งชุด + **ยังไม่มี source** · นี่คือก้อนที่ใหญ่ที่สุดและควบคุมไม่ได้ด้วยตัวเอง |
| backend changes | **MEDIUM–LARGE** | เพิ่ม endpoint 10–15 เส้นทาง + ย้าย authorization ที่ RLS เคยทำมาอยู่ที่ API ให้ครบ ซึ่งเป็นงานที่พลาดไม่ได้ |
| authentication migration | **LARGE** (Option B) · **MEDIUM** (Option A) | Option B ต้องสร้างสิ่งที่ Supabase ให้ฟรี: ยืนยันอีเมล รีเซ็ตรหัสผ่าน rate limit ล็อกบัญชี — ปัจจุบัน **ยังไม่มีเลยแม้ชิ้นเดียว** |
| testing | **LARGE** | ชุดเดิม 484 + E2E 107 ยังต้องผ่าน · บวกชุดใหม่สำหรับ `web.*` · บวกการวัดคุณภาพ RAG ก่อน/หลัง ซึ่งต้องรันหลายรอบเพราะผลมีความผันผวน |
| production cutover | **MEDIUM** | มีแบบแผนที่พิสูจน์แล้วจาก Phase 3D (release directory · วัด invariant ก่อน/หลัง · rollback ด้วย reference) ใช้ซ้ำได้ |
| documentation updates | **LARGE** | ER diagram 6 ไฟล์ · dictionary 82 KB · สไลด์ · รายงาน ~15 ไฟล์ |

**LARGE 5 · MEDIUM–LARGE 1 · MEDIUM 4 · SMALL 1**

---

## 14. Unknowns

สิ่งที่ยังไม่รู้และ **ต้องรู้ก่อนตัดสินใจ**

| # | ไม่รู้อะไร | ทำไมสำคัญ | ได้มาอย่างไร |
|---|---|---|---|
| U1 | **source ของ SPA อยู่ที่ไหน และเจ้าของยินยอมให้แก้ไหม** | ถ้าไม่ได้ source งานนี้เริ่มไม่ได้เลย ไม่ว่าเลือกทางไหน | ถามเจ้าของโค้ดส่วนนั้น |
| U2 | schema จริงของ Supabase ทั้ง 7 ตาราง (type, PK, FK, index, constraint) | ออกแบบตารางปลายทางให้ถูกต้องไม่ได้ถ้าไม่รู้ | เข้าถึง Supabase dashboard หรือ `pg_dump --schema-only` |
| U3 | **จำนวนแถวจริงของทุกตารางใน Supabase** | ประเมินเวลาและความเสี่ยงไม่ได้ · backup เก่าที่มีขนาดเพียง 1 KB บอกอะไรไม่ได้ | query ฝั่ง Supabase |
| U4 | **RLS policy ทั้งหมด** | เป็นตัวกำหนดว่าต้องเขียน authorization ที่ API เท่าไหร่ · ความเสี่ยง R4 วัดไม่ได้ถ้าไม่รู้ | ดู policy ใน Supabase |
| U5 | **Supabase Storage เก็บอะไร bucket ชื่ออะไร ขนาดเท่าไหร่** | ถ้ามีไฟล์จำนวนมากจะเปลี่ยนการประเมินทั้งหมด | ดู Storage ใน dashboard |
| U6 | Edge Function มีกี่ตัว ทำอะไร | พบ `sync-sci-news` หนึ่งตัว และร่องรอย `functions/v1` อีก 4 ครั้งใน bundle | ดู Functions ใน dashboard |
| U7 | `news` กับ `external_news` ต่างกันอย่างไร | ซ้ำซ้อนหรือไม่ · ย้ายทั้งคู่หรือรวมเป็นหนึ่ง | ดู schema + ข้อมูลตัวอย่าง |
| U8 | แถวใน Supabase `courses` ตรงกับ `public.courses` (24 แถว) กี่แถว | เป็นตัวตัดสินว่า `web.site_courses.course_id` จะมีประโยชน์จริงไหม | เทียบข้อมูลจริงสองฝั่ง |
| U9 | ผู้ใช้ใน Supabase มีกี่คน และทับกับ 198 คนในของเราเท่าไหร่ | เป็นตัวตัดสินว่าการบังคับรีเซ็ตรหัสผ่านกระทบคนเท่าไหร่ | เทียบอีเมลสองฝั่ง |
| U10 | `supabase_migration_rag.sql` อยู่ที่ไหน | เป็นเอกสารเดียวที่บอก schema จริงของ `rag_documents` | ถามเจ้าของโค้ด |

**ข้อ U1 สำคัญกว่าทุกข้อรวมกัน** — ถ้าคำตอบคือ "ไม่ได้" การประเมินที่เหลือไม่มีความหมาย

---

## 15. Final Assessment

### A. รวมได้ในทางเทคนิคไหม

**ได้** — และฐานปลายทางพร้อมกว่าที่คาด

- PostgreSQL 16 + pgvector ทำงานอยู่จริงกับข้อมูลจริง 9,039 chunk · 174 MB
- schema แข็งแรง: 56 FK · 68 check constraint · 7 unique index ในตารางหลัก
- `mko` กับ `public` **ผูกกันแน่นในฐานเดียวอยู่แล้ว** (19 FK ข้ามสคีมา) พิสูจน์ว่าโครงสร้างแบบ
  หลาย schema ในฐานเดียวทำงานได้ดีในโปรเจกต์นี้
- ของที่ต้องย้ายมีเพียง 7 ตาราง + 1 RPC + 1 Edge Function + Storage
- มีแบบแผนการ deploy และวัด invariant ที่พิสูจน์แล้วจาก Phase 3D ใช้ซ้ำได้ทันที

### B. ตัวขัดขวางที่ใหญ่ที่สุด

**ไม่ใช่เรื่องฐานข้อมูล — คือการเข้าถึง source ของ SPA**

SPA เรียก Supabase ตรงจากเบราว์เซอร์ที่ ~39 จุด + ชั้น auth ทั้งชุด
แต่ `/web/` ถูก gitignore และบนเซิร์ฟเวอร์มีแต่ bundle ที่ minify แล้ว
**ไม่มี source = แก้ไม่ได้ = ย้ายฐานข้อมูลไม่ได้** ไม่ว่าจะเลือก Option A หรือ B

อันดับสองคือ **vector 768 vs 1024** ซึ่งทำให้ `rag_documents` ย้ายไม่ได้ ต้องสร้างใหม่
และคุณภาพการค้นหาจะเปลี่ยน ต้องวัดใหม่ทั้งหมด

### C. การตัดสินใจเรื่อง auth ที่ต้องทำก่อน

**คำถามเดียวที่ต้องตอบก่อนอย่างอื่น: ใครคือเจ้าของตัวตนผู้ใช้**

- ถ้าตอบ "Supabase" → Option A · ผู้ใช้ไม่กระทบ · ยังเหลือ dependency ภายนอก
- ถ้าตอบ "PostgreSQL ของเรา" → Option B · รวมเป็นหนึ่งจริง · **ผู้ใช้ทุกคนต้องตั้งรหัสผ่านใหม่**
  และต้องสร้าง flow ยืนยันอีเมล/รีเซ็ตรหัสผ่านซึ่งปัจจุบันยังไม่มีเลย

ตอบข้อนี้ก่อนจะกำหนดทุกอย่างที่เหลือ และตอบได้โดยไม่ต้องเขียนโค้ดแม้บรรทัดเดียว

### D. ข้อมูลที่ยังขาด

10 รายการในข้อ 14 · **U1 (source ของ SPA) สำคัญกว่าทุกข้อรวมกัน** ·
รองลงมาคือ U4 (RLS policy) เพราะเป็นตัวกำหนดปริมาณงาน authorization ที่ต้องเขียนใหม่
และ U3 (จำนวนแถวจริง) เพราะเป็นตัวกำหนดเวลา

ทั้งสามข้อตอบได้ด้วยการเข้าถึง Supabase dashboard และคุยกับเจ้าของโค้ด SPA
**ไม่ต้องเขียนโค้ดหรือแตะฐานข้อมูลเลย**

### E. เส้นทางที่ปลอดภัยที่สุด

**ไม่ใช่การรวมทั้งก้อน แต่เป็นการแก้เรื่องที่เจ็บจริงโดยไม่ย้ายฐานข้อมูล**

เรียงจากคุ้มที่สุด

1. **ตอบ U1, U3, U4 ก่อน** — ไม่มีความเสี่ยง ไม่ต้องเขียนโค้ด และอาจทำให้คำตอบเปลี่ยนทั้งหมด
2. ถ้าจะรวมจริง **เริ่มจากตารางที่อ่านอย่างเดียว** (`news`, `knowledge_articles`,
   `external_news`) ใน schema `web` แยก — ถอนกลับด้วย `DROP SCHEMA web CASCADE`
   ไม่แตะ auth ไม่แตะ RAG ไม่แตะ `public` และ `mko`
3. **เลื่อน auth ไว้ท้ายสุด** — เป็นส่วนที่เสี่ยงที่สุดและกระทบผู้ใช้จริง
4. **เลื่อน `rag_documents` ไว้ท้ายสุดเช่นกัน** — ต้อง re-embed และวัดคุณภาพใหม่

### F. ควรทำก่อนกำหนดส่งโครงงานไหม

## **ไม่ควร**

เหตุผลที่อิงหลักฐานจาก audit นี้

| # | เหตุผล |
|---|---|
| 1 | **ตัวขัดขวางที่ใหญ่ที่สุดควบคุมด้วยตัวเองไม่ได้** — source ของ SPA ไม่อยู่ในมือ ต้องรอความร่วมมือจากคนอื่น ซึ่งเป็นสิ่งที่ประเมินเวลาไม่ได้ |
| 2 | **งานระดับ LARGE มีถึง 5 ก้อน** (frontend · auth · testing · documentation · backend) ไม่ใช่งานที่บีบลงช่วงก่อนส่งได้ |
| 3 | **สิ่งที่จะพังคือสิ่งที่โครงงานถูกวัด** — RAG + pgvector + crawler ตอนนี้ทำงานได้และมีหลักฐานการทดสอบครบ (regression 484 ข้อ · E2E 107 ข้อ) การรวมฐานข้อมูลแตะทั้งสามอย่าง |
| 4 | **เอกสารและสไลด์จะผิดทันทีที่เริ่ม** แต่ของใหม่จะยังไม่เสร็จ — ช่วงกลางนั้นคือช่วงที่อธิบายในการนำเสนอยากที่สุด |
| 5 | **ความเสี่ยงระดับ HIGH มี 5 ข้อ** และสามข้อ (R1 R3 R4) ไม่มีทางลดได้ด้วยความระมัดระวังอย่างเดียว ต้องได้ข้อมูลหรือความร่วมมือเพิ่ม |
| 6 | **ไม่มีอะไรพังอยู่ตอนนี้** — สถาปัตยกรรมสองฐานข้อมูลทำงานได้ และ "สองระบบที่แยกกันชัดเจน" อธิบายในการนำเสนอได้ตรงไปตรงมา ไม่ใช่จุดอ่อนที่ต้องซ่อน |

**ข้อเสนอแทน**: เขียนการรวมฐานข้อมูลไว้เป็น **"งานในอนาคต"** ในรายงานโครงงาน
โดยอ้างเอกสารฉบับนี้เป็นผลการศึกษาความเป็นไปได้ — การแสดงว่าประเมินแล้วและ
**ตัดสินใจไม่ทำโดยมีเหตุผล** เป็นเนื้อหาที่หนักแน่นกว่าการรวมที่ทำไม่เสร็จ

> **GO ในข้อ A ไม่ได้หมายถึงให้เริ่ม** — ห้ามเริ่ม migration แม้ผลประเมินจะเป็นไปได้
> จนกว่าจะได้รับอนุมัติจากเจ้าของโปรเจกต์อย่างชัดแจ้ง

---

## สรุปการเปลี่ยนแปลงในรอบนี้

```
CHANGES MADE:        NONE
PRODUCTION WRITES:   NONE
DATABASE MIGRATIONS: NONE
DEPLOYMENTS:         NONE
COMMITS:             NONE
PUSHES:              NONE
```

วิธีการตรวจ: อ่าน catalog ของ PostgreSQL (`pg_class`, `pg_constraint`, `pg_index`,
`pg_attribute`, `pg_am`, `pg_type`) ด้วย `SELECT` เท่านั้น · นับแถวด้วย `query_to_xml` ซึ่งเป็น
การอ่าน · อ่านไฟล์ในคอนเทนเนอร์ `webapi` ด้วย `cat`/`grep` · อ่าน bundle ของ SPA ด้วย `grep` ·
อ่าน source ใน repo · **ไม่มีคำสั่ง INSERT/UPDATE/DELETE/CREATE/ALTER/DROP แม้คำสั่งเดียว**
ไม่ได้แตะ Supabase เลย (ไม่มี credential และอยู่นอกขอบเขต) · ไม่ได้ restart บริการใด ·
ไม่ได้แสดงค่าของ secret ใด — รายงานเฉพาะ **ชื่อ** environment variable

---

## STOP

จบการตรวจ · **ห้ามเริ่ม implementation จนได้รับอนุมัติจากเจ้าของโปรเจกต์อย่างชัดแจ้ง**

สิ่งที่ควรทำต่อโดยไม่มีความเสี่ยง: ตอบคำถาม **U1** (source ของ SPA อยู่ที่ไหน
และเจ้าของยินยอมให้แก้ไหม) · **U4** (RLS policy) · **U3** (จำนวนแถวจริง)
ทั้งสามข้อตอบได้โดยไม่ต้องเขียนโค้ดและไม่ต้องแตะฐานข้อมูล

STOP
