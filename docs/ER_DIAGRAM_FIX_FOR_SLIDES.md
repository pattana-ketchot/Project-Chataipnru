# แก้ ER Diagram ในสไลด์ให้ตรงกับฐานข้อมูลจริง

ตรวจกับฐานข้อมูล production เมื่อ 24 กันยายน 2569
ทุกค่าในไฟล์นี้อ่านจาก `information_schema` และ `pg_constraint` โดยตรง ไม่ได้เดา

---

## ✅ ภาพที่แก้แล้วพร้อมใช้งาน — เอาไปใส่สไลด์ได้เลย

| ไฟล์ | ใช้ตอนไหน |
|---|---|
| **`ER_DIAGRAM_PUBLIC_SCHEMA.svg`** | **แนะนำให้ใช้ตัวนี้** PowerPoint 2016 ขึ้นไป Insert > Picture ได้ตรง ๆ ขยายเท่าไรก็ไม่แตก |
| `ER_DIAGRAM_PUBLIC_SCHEMA.png` | 3140 × 2150 px สำหรับโปรแกรมที่ไม่รองรับ SVG เช่น Google Slides รุ่นเก่า |

ทั้งสองไฟล์สร้างจากสคริปต์ที่ป้อนชื่อคอลัมน์จากผลคิวรีฐานข้อมูลโดยตรง
จึงไม่มีโอกาสผิดแบบที่เกิดกับภาพที่ AI สร้าง ตรวจแล้วได้ **10 ตาราง / 83 คอลัมน์ / 11 เส้น** ครบถ้วน

> ถ้าต้องแก้ภายหลัง แก้ที่สคริปต์แล้วสร้างใหม่ อย่าแก้ที่ SVG โดยตรง
> เพราะตำแหน่งกล่องกับเส้นคำนวณจากจำนวนคอลัมน์

---

## 1. สิ่งที่ต้องแก้ 4 จุด

### 🔴 จุดที่ 1 — ชื่อตารางผิด

| ในสไลด์ | ที่ถูกต้อง |
|---|---|
| `PUBLIC_COURSE_CLINICS` | **`PUBLIC_COURSE_CHUNKS`** |
| "ข้อมูลคลินิกหลักสูตร" (กล่องคำอธิบาย) | **"ข้อมูลส่วนข้อความของหลักสูตร"** |
| "ข้อมูลคลินิกหลักสูตร" (ใน legend ล่างซ้าย) | **"ข้อมูลส่วนข้อความที่สกัดจากเอกสาร"** |

คอลัมน์ข้างในกล่อง (`chunk_index`, `page_number`, `embedding`) คือตาราง `course_chunks` ชัดเจน
คำว่า clinic (คลินิก) กับ chunk (ส่วนข้อความ) คนละความหมายกันโดยสิ้นเชิง

### 🔴 จุดที่ 2 — เส้นความสัมพันธ์ที่ไม่มีอยู่จริง

**ลบเส้น `PUBLIC_USERS → PUBLIC_CHAT_ANSWER_CACHE` ที่ติดป้าย `user_id cascade` ออก**

ตาราง `chat_answer_cache` **ไม่มีคีย์นอกเลยสักตัว และไม่มีคอลัมน์ `user_id`** คอลัมน์จริงทั้ง 8 ตัวคือ

```
question_key · corpus_version · status · reply · citations · hits · created_at · last_used_at
```

เป็นตารางแคชคำตอบที่ใช้ `question_key` เป็นคีย์หลัก ไม่ผูกกับผู้ใช้
เพราะคำถามเดียวกันใช้คำตอบเดิมซ้ำได้กับผู้ใช้ทุกคน

### 🔴 จุดที่ 3 — legend บอกว่าครึ่งหนึ่งเป็น Supabase

ทุกกล่องในแผนภาพขึ้นต้นด้วย `PUBLIC_` ซึ่งคือ schema `public` ของ **PostgreSQL ทั้งหมด**
ไม่มีตารางไหนเป็นของ Supabase เลย

Supabase มีตารางของตัวเองคนละชุด 7 ตาราง
`ai_settings` · `courses` · `external_news` · `knowledge_articles` · `news` · `rag_documents` · `user_profiles`

**วิธีแก้:** เปลี่ยนหัวข้อเป็น **"ER Diagram — PostgreSQL schema public (10 ตาราง)"**
แล้วตัดกล่อง legend ฝั่ง Supabase ออก หรือทำแผนภาพ Supabase แยกอีกหน้า

### 🟠 จุดที่ 4 — เส้นที่หายไป และชนิดข้อมูลที่พิมพ์ผิด

- **เพิ่มเส้น** `course_documents.uploaded_by → users` ป้ายกำกับ **`uploaded_by NO ACTION`**
  (เส้นนี้น่าสนใจเพราะต่างจากเส้นอื่นที่เป็น CASCADE — แปลว่าลบผู้ใช้ไม่ได้ถ้ายังมีเอกสารที่เขาอัปโหลดค้างอยู่)
- **แก้ชนิดข้อมูล** `users.email` จาก `cltext` เป็น **`citext`** (case-insensitive text)

---

## 2. โครงสร้างที่ถูกต้อง — ใช้อ้างอิงตอนแก้

### ตารางและจำนวนคอลัมน์

| ตาราง | คอลัมน์ | หมายเหตุ |
|---|---|---|
| `courses` | 13 | หลักสูตรในคลังความรู้ |
| `course_documents` | 10 | เอกสาร มคอ.2 ต้นฉบับ |
| `course_chunks` | 10 | ส่วนข้อความ + เวกเตอร์ |
| `users` | 8 | ผู้ใช้ระบบ |
| `user_profiles` | 10 | โปรไฟล์ (PK = FK) |
| `user_requirements` | 6 | ความต้องการของผู้ใช้ |
| `chat_sessions` | 4 | บทสนทนา |
| `chat_messages` | 5 | ข้อความในบทสนทนา |
| `chat_answer_cache` | 8 | แคชคำตอบ **ไม่มี FK** |
| `recommendations` | 9 | ผลการแนะนำสาขา |

### คีย์นอกทั้งหมด 11 เส้น (ของจริง ไม่มีมากไม่มีน้อยกว่านี้)

| จาก | ไป | เมื่อลบต้นทาง |
|---|---|---|
| `course_documents.course_id` | `courses` | CASCADE |
| `course_documents.uploaded_by` | `users` | **NO ACTION** |
| `course_chunks.course_id` | `courses` | CASCADE |
| `course_chunks.document_id` | `course_documents` | CASCADE |
| `chat_sessions.user_id` | `users` | CASCADE |
| `chat_messages.session_id` | `chat_sessions` | CASCADE |
| `user_profiles.user_id` | `users` | CASCADE |
| `user_requirements.user_id` | `users` | CASCADE |
| `recommendations.user_id` | `users` | CASCADE |
| `recommendations.course_id` | `courses` | CASCADE |
| `recommendations.session_id` | `chat_sessions` | **SET NULL** |

---

## 3. โค้ด Mermaid — วางแล้วได้ภาพถูกต้องทันที

วางที่ <https://mermaid.live> แล้วกด Export เป็น PNG/SVG ได้เลย
**วิธีนี้แม่นที่สุดเพราะไม่ต้องให้ AI เดา** ทุกเส้นและทุกคอลัมน์มาจากฐานข้อมูลจริง

```mermaid
erDiagram
    COURSES ||--o{ COURSE_DOCUMENTS : "course_id (CASCADE)"
    COURSES ||--o{ COURSE_CHUNKS : "course_id (CASCADE)"
    COURSES ||--o{ RECOMMENDATIONS : "course_id (CASCADE)"
    COURSE_DOCUMENTS ||--o{ COURSE_CHUNKS : "document_id (CASCADE)"
    USERS ||--o{ COURSE_DOCUMENTS : "uploaded_by (NO ACTION)"
    USERS ||--o{ CHAT_SESSIONS : "user_id (CASCADE)"
    USERS ||--|| USER_PROFILES : "user_id (CASCADE)"
    USERS ||--o{ USER_REQUIREMENTS : "user_id (CASCADE)"
    USERS ||--o{ RECOMMENDATIONS : "user_id (CASCADE)"
    CHAT_SESSIONS ||--o{ CHAT_MESSAGES : "session_id (CASCADE)"
    CHAT_SESSIONS ||--o{ RECOMMENDATIONS : "session_id (SET NULL)"

    COURSES {
        uuid id PK
        text code
        text title "NOT NULL"
        text provider
        text summary
        text mode
        numeric duration_weeks
        numeric price
        text currency
        jsonb tags
        boolean is_active
        timestamptz created_at
        timestamptz updated_at
    }

    COURSE_DOCUMENTS {
        uuid id PK
        uuid course_id FK
        text original_filename "NOT NULL"
        text file_sha256 "NOT NULL"
        text storage_path "NOT NULL"
        integer page_count
        text extraction_status "NOT NULL"
        text extraction_error
        uuid uploaded_by FK
        timestamptz uploaded_at
    }

    COURSE_CHUNKS {
        uuid id PK
        uuid course_id FK
        uuid document_id FK
        integer chunk_index "NOT NULL"
        integer page_number
        text content "NOT NULL"
        integer token_count
        vector_1024 embedding "NOT NULL, ivfflat cosine"
        jsonb metadata
        timestamptz created_at
    }

    USERS {
        uuid id PK
        citext email "NOT NULL"
        text password_hash "NOT NULL"
        text full_name
        boolean is_active
        boolean is_admin
        timestamptz created_at
        timestamptz updated_at
    }

    USER_PROFILES {
        uuid user_id PK_FK
        text education_level
        text field_of_study
        text current_role
        text career_goal
        jsonb skills
        jsonb interests
        text language_preference
        jsonb metadata
        timestamptz updated_at
    }

    USER_REQUIREMENTS {
        uuid id PK
        uuid user_id FK
        text req_type "NOT NULL"
        text req_value "NOT NULL"
        smallint priority "NOT NULL"
        timestamptz created_at
    }

    CHAT_SESSIONS {
        uuid id PK
        uuid user_id FK
        timestamptz started_at "NOT NULL"
        timestamptz ended_at
    }

    CHAT_MESSAGES {
        uuid id PK
        uuid session_id FK
        text role "NOT NULL"
        text content "NOT NULL"
        timestamptz created_at
    }

    RECOMMENDATIONS {
        uuid id PK
        uuid user_id FK
        uuid course_id FK
        uuid session_id FK
        numeric score "NOT NULL"
        text rationale
        uuid[] retrieved_chunk_ids
        text model_used
        timestamptz created_at
    }

    CHAT_ANSWER_CACHE {
        text question_key PK
        text corpus_version "NOT NULL"
        text status "NOT NULL"
        text reply "NOT NULL"
        jsonb citations
        integer hits
        timestamptz created_at
        timestamptz last_used_at
    }
```

> **สังเกต:** `CHAT_ANSWER_CACHE` ลอยอยู่เดี่ยว ๆ ไม่มีเส้นเชื่อมไปไหน — ถูกต้องแล้ว
> เพราะไม่มีคีย์นอกจริง อย่าลากเส้นเชื่อมเข้าไป

---

## 4. Prompt สำหรับให้ AI สร้างภาพ

> ⚠️ **บทเรียนจากรอบแรก** — prompt เวอร์ชันแรกเขียนย่อว่า "+ อีก 9 คอลัมน์"
> ผลคือ AI **แต่งชื่อคอลัมน์ขึ้นมาเอง 7 จาก 10 ตาราง** เช่นใส่ `student_id`, `faculty`,
> `major_interest` ใน `user_profiles` ซึ่งดูสมเหตุสมผลมากจนไม่มีใครเอะใจ แต่ไม่มีจริงสักตัว
> prompt ข้างล่างนี้จึง**ไล่ชื่อคอลัมน์ครบทุกตัว ห้ามย่อเด็ดขาด**

```
สร้างแผนภาพ ER Diagram สไตล์โมเดิร์น พื้นหลังขาว โทนสีน้ำเงิน-ม่วงอ่อน
หัวข้อ: "ER Diagram — PostgreSQL schema public (10 ตาราง)"

วาดกล่องตาราง 10 กล่อง แต่ละกล่องมีหัวสีเข้ม ชื่อตารางตัวพิมพ์ใหญ่
แสดงคอลัมน์เป็นแถว 3 ช่อง: ชื่อคอลัมน์ | ชนิดข้อมูล | ป้าย PK/FK

*** กฎข้อสำคัญที่สุด ***
คอลัมน์ทุกตัวอยู่ในรายการข้างล่างนี้แล้ว ต้องลอกชื่อมาตรงตัวอักษรทุกตัว
ห้ามเพิ่ม ห้ามตัดออก ห้ามเปลี่ยนชื่อ ห้ามเติมคอลัมน์ที่ "น่าจะมี" เช่น
created_at หรือ updated_at ถ้าไม่ได้อยู่ในรายการของตารางนั้น
จำนวนแถวในแต่ละกล่องต้องเท่ากับตัวเลขในวงเล็บเป๊ะ ๆ

1. USERS (8 คอลัมน์)
   id uuid PK / email citext UNIQUE / password_hash text / full_name text /
   is_active boolean / is_admin boolean / created_at timestamptz / updated_at timestamptz

2. COURSES (13 คอลัมน์)
   id uuid PK / code text / title text NOT NULL / provider text / summary text /
   mode text / duration_weeks numeric / price numeric / currency text / tags jsonb /
   is_active boolean / created_at timestamptz / updated_at timestamptz

3. COURSE_DOCUMENTS (10 คอลัมน์)
   id uuid PK / course_id uuid FK / original_filename text / file_sha256 text /
   storage_path text / page_count integer / extraction_status text /
   extraction_error text / uploaded_by uuid FK / uploaded_at timestamptz

4. COURSE_CHUNKS (10 คอลัมน์)
   id uuid PK / course_id uuid FK / document_id uuid FK / chunk_index integer /
   page_number integer / content text / token_count integer /
   embedding vector(1024) / metadata jsonb / created_at timestamptz

5. USER_PROFILES (10 คอลัมน์)
   user_id uuid PK FK / education_level text / field_of_study text /
   current_role text / career_goal text / skills jsonb / interests jsonb /
   language_preference text / metadata jsonb / updated_at timestamptz

6. USER_REQUIREMENTS (6 คอลัมน์)
   id uuid PK / user_id uuid FK / req_type text / req_value text /
   priority smallint / created_at timestamptz

7. CHAT_SESSIONS (4 คอลัมน์)
   id uuid PK / user_id uuid FK / started_at timestamptz / ended_at timestamptz

8. CHAT_MESSAGES (5 คอลัมน์)
   id uuid PK / session_id uuid FK / role text / content text / created_at timestamptz

9. RECOMMENDATIONS (9 คอลัมน์)
   id uuid PK / user_id uuid FK / course_id uuid FK / session_id uuid FK /
   score numeric / rationale text / retrieved_chunk_ids uuid[] /
   model_used text / created_at timestamptz

10. CHAT_ANSWER_CACHE (8 คอลัมน์)
    question_key text PK / corpus_version text / status text / reply text /
    citations jsonb / hits integer / created_at timestamptz / last_used_at timestamptz

เส้นความสัมพันธ์ที่ต้องวาด มีเพียง 11 เส้นนี้เท่านั้น
นับให้ครบ 11 เส้นก่อนส่งงาน ทุกคอลัมน์ที่ติดป้าย FK ต้องมีเส้นลากออกไปจริง:
COURSES 1—N COURSE_DOCUMENTS ป้าย "course_id CASCADE"
COURSES 1—N COURSE_CHUNKS ป้าย "course_id CASCADE"
COURSES 1—N RECOMMENDATIONS ป้าย "course_id CASCADE"
COURSE_DOCUMENTS 1—N COURSE_CHUNKS ป้าย "document_id CASCADE"
USERS 1—N COURSE_DOCUMENTS ป้าย "uploaded_by NO ACTION"
USERS 1—N CHAT_SESSIONS ป้าย "user_id CASCADE"
USERS 1—1 USER_PROFILES ป้าย "user_id CASCADE"
USERS 1—N USER_REQUIREMENTS ป้าย "user_id CASCADE"
USERS 1—N RECOMMENDATIONS ป้าย "user_id CASCADE"
CHAT_SESSIONS 1—N CHAT_MESSAGES ป้าย "session_id CASCADE"
CHAT_SESSIONS 1—N RECOMMENDATIONS ป้าย "session_id SET NULL"

ข้อห้ามเด็ดขาด:
- ห้ามแต่งชื่อคอลัมน์ขึ้นเอง ใช้เฉพาะชื่อในรายการ 10 ข้อข้างบนเท่านั้น
- ห้ามลากเส้นใด ๆ เข้าหรือออกจาก CHAT_ANSWER_CACHE ให้วางลอยไว้มุมขวาล่าง
- ห้ามใช้คำว่า CLINIC หรือ คลินิก ที่ใดก็ตาม ตารางชื่อ COURSE_CHUNKS
- ห้ามเขียนว่าตารางใดเป็นของ Supabase ทุกตารางอยู่ใน PostgreSQL
- ห้ามเพิ่มตารางหรือเส้นความสัมพันธ์นอกเหนือจากรายการข้างบน

เพิ่มกล่องสัญลักษณ์มุมขวาล่าง: PK = Primary Key, FK = Foreign Key,
1 = หนึ่ง, N = หลาย, CASCADE = ลบต้นทางแล้วลบตาม, SET NULL = ลบต้นทางแล้วตั้งเป็นค่าว่าง
```

### เช็กลิสต์ตรวจภาพที่ได้ ก่อนเอาไปใส่สไลด์

ไล่ทีละข้อ ถ้าตกข้อใดข้อหนึ่งให้สั่งสร้างใหม่

- [ ] นับแถวในกล่องให้ตรงเลขในวงเล็บทั้ง 10 กล่อง (8 / 13 / 10 / 10 / 10 / 6 / 4 / 5 / 9 / 8)
- [ ] `users` มี `is_admin` **ไม่ใช่** `role`
- [ ] `course_documents` มี `extraction_status`, `extraction_error`, `uploaded_at` **ไม่มี** `file_size`
- [ ] `course_chunks` แถวสุดท้ายคือ `metadata` กับ `created_at` **ไม่มี** `updated_at`
- [ ] `user_profiles` ขึ้นต้นด้วย `education_level` **ไม่ใช่** `student_id`
- [ ] `user_requirements` ใช้ `req_type` / `req_value` **ไม่ใช่** `requirement_type` / `value`
- [ ] `chat_sessions` มี `started_at` กับ `ended_at` **ไม่มี** `title`
- [ ] `recommendations` มี `rationale`, `retrieved_chunk_ids`, `model_used` **ไม่ใช่** `reason`
- [ ] นับเส้นได้ 11 เส้น และคอลัมน์ที่ติดป้าย FK ทุกตัวมีเส้นลากออกจริง
- [ ] `chat_answer_cache` ไม่มีเส้นเชื่อมเลยสักเส้น

---

## 5. ถ้าจะเพิ่ม schema `mko` เข้าไปด้วย

สไลด์ "ตัวอย่างการเรียกใช้ข้อมูลด้วย SQL (2)" ใช้ตาราง `mko.field_values` กับ `mko.evidence`
ซึ่ง**ยังไม่มีใน ER diagram** กรรมการอาจถามว่ามาจากไหน

ทางเลือกที่เบาที่สุดคือ**เพิ่มอีกหนึ่งกล่องในสไลด์** อธิบายสั้น ๆ ว่า

> นอกจาก schema `public` 10 ตารางในแผนภาพนี้ ระบบยังมี schema `mko` อีก **18 ตาราง** กับ **6 วิว**
> สำหรับเก็บข้อมูลที่สกัดจากเอกสาร พร้อมหลักฐานอ้างอิงและสถานะการตรวจทาน
> รวมทั้งหมด **28 ตาราง** ในฝั่ง PostgreSQL

ถ้าต้องการแผนภาพของ `mko` เต็ม ๆ มีไฟล์พร้อมแล้วที่
`docs/database/er_postgres_b_metadata.png` และ `er_postgres_a_documents.png`
