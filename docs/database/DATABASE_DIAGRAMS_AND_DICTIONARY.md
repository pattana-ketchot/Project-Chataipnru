# เอกสารฐานข้อมูล — แผนภาพและพจนานุกรมข้อมูล

สร้างจากไฟล์ SQL จริง 2026-09-23 · **ไม่แตะ production · ไม่แก้โค้ด · ไม่แก้ไฟล์ Word**

| ไฟล์ต้นทางที่อ่าน | บรรทัด |
|---|---:|
| `db/schema.sql` | 224 |
| `db/migrations/001_mko_structured.sql` | 310 |
| `db/migrations/002_mko_review_publish.sql` | 142 |
| `supabase_schema.sql` | 441 |

---

## 1. ตัวเลขที่นับได้จาก SQL จริง และความต่างจากรายงานก่อนหน้า

| รายการ | นับจาก SQL จริง | ที่เคยเขียนในรายงาน | ตรงกันไหม |
|---|---:|---:|---|
| ตาราง PostgreSQL | **28** | 28 | ✅ ตรง |
| วิว PostgreSQL | **6** | 6 | ✅ ตรง |
| ตาราง Supabase | **7** | 7 | ✅ ตรง |
| ตารางรวมทั้งสองฐาน | **35** | 35 | ✅ ตรง |
| คอลัมน์รวม | **342** (PostgreSQL 277 · Supabase 65) | ไม่เคยระบุ | — |
| **ความสัมพันธ์ (คีย์นอกที่ประกาศใน SQL)** | **60** (PostgreSQL 53 · Supabase 7) | **26** | ❌ **ไม่ตรง** |
| **ดัชนีที่ประกาศด้วย CREATE INDEX** | **29** (PostgreSQL 15 · Supabase 14) | **10** | ❌ **ไม่ตรง** |

### อธิบายความต่าง

**เรื่องความสัมพันธ์ 26 กับ 60** — ตัวเลข 26 ในเอกสาร `REPORT_SECTION_DATABASE_DESIGN.md`
เป็นการ **สรุปความสัมพันธ์เชิงแนวคิด** โดยยุบคีย์นอกหลายเส้นที่ชี้ไปตารางเดียวกันให้เหลือรายการเดียว
เช่น `mko.field_values` มีคีย์นอก 4 เส้น (`curriculum_id`, `run_id`, `document_id`, `evidence_id`)
แต่ในตารางสรุปนับเป็นรายการเดียว

ส่วน **60** คือจำนวน **ข้อกำหนดคีย์นอกที่เขียนไว้จริงใน SQL** นับทีละเส้น
**เอกสารชุดนี้ใช้ตัวเลข 60 เป็นค่าอ้างอิง** ตามที่สั่งให้ยึดค่าจาก schema จริง

**เรื่องดัชนี 10 กับ 29** — ตัวเลข 10 เดิมนับเฉพาะดัชนีของฝั่ง PostgreSQL ที่หยิบมาอธิบายในตาราง
ไม่ได้นับของ Supabase และไม่ได้นับครบทุกตัว ค่าที่ถูกต้องคือ **29 ตัว**
(ยังไม่รวมดัชนีที่ PostgreSQL สร้างให้เองจาก PRIMARY KEY และ UNIQUE)

> **หากนำตัวเลขไปใส่เล่มรายงาน ให้ใช้ค่าจากตารางนี้** และแก้ตัวเลขในเอกสารเดิมให้ตรงกัน

---

## 2. ตารางสรุปฐานข้อมูลทั้งสองชุด

| หัวข้อ | ฐานข้อมูลฐานความรู้ | ฐานข้อมูลระบบเว็บ |
|---|---|---|
| ระบบจัดการ | PostgreSQL 16 + ส่วนขยาย pgvector | Supabase (PostgreSQL บริการคลาวด์) |
| ติดตั้งที่ | เครื่องแม่ข่าย Oracle Cloud (คอนเทนเนอร์) | บริการคลาวด์ของ Supabase |
| **หน้าที่** | เก็บข้อมูลที่สกัดจากเอกสารหลักสูตรพร้อมหลักฐาน และใช้ตอบคำถามของผู้ใช้ | เก็บข้อมูลที่ผู้ดูแลระบบแก้ไขผ่านหน้าเว็บ |
| ผู้เขียนข้อมูล | กระบวนการสกัดเอกสาร · ผู้ตรวจทาน · ระบบส่วนหลัง | ผู้ดูแลระบบผ่านหน้าจอ Admin |
| ผู้อ่านข้อมูล | FastAPI เท่านั้น (ผ่านวิว `v_live_*`) | หน้าเว็บเรียกตรงจากเบราว์เซอร์ และบริการ webapi |
| สคีมา | `public` 10 ตาราง · `mko` 18 ตาราง | `public` 7 ตาราง |
| วิว | 6 | 0 |
| คอลัมน์ | 277 | 65 |
| คีย์นอกที่ประกาศ | 53 | 7 |
| ดัชนี `CREATE INDEX` | 15 | 14 |
| ความสามารถเด่น | เวกเตอร์ 1,024 มิติ · ทริกเกอร์ตรวจหลักฐาน · การเผยแพร่เป็นชุด · แยกสิทธิ์ 3 บัญชี | Row Level Security 32 นโยบาย · ระบบยืนยันตัวตนสำเร็จรูป · Edge Function |
| ตารางที่มีข้อมูลมากที่สุด | `course_chunks` · `chat_messages` · `mko.document_pages` | `external_news` · `courses` |

**เหตุผลที่แยกเป็นสองฐาน** ลักษณะการใช้งานต่างกันโดยสิ้นเชิง — ข้อมูลฝั่งเว็บถูกแก้ไขบ่อยโดยมนุษย์
และต้องการระบบยืนยันตัวตนกับสิทธิ์ระดับแถว ส่วนข้อมูลฐานความรู้เขียนครั้งเดียวจากกระบวนการสกัด
แล้วอ่านซ้ำจำนวนมากพร้อมการค้นหาเชิงเวกเตอร์ ซึ่งต้องควบคุมดัชนีและหน่วยความจำเอง
การแยกยังทำให้ความเสียหายไม่ลามข้ามกัน หากฝั่งหนึ่งมีปัญหา อีกฝั่งยังทำงานได้

**ตัวเชื่อมระหว่างสองฐาน** ใช้ **ชื่อหลักสูตร** ไม่ใช่รหัสประจำตัว เพราะทั้งสองฐานสร้าง UUID ของตนเองแยกกัน
เป็นความสัมพันธ์เชิงตรรกะที่บังคับในโค้ด ไม่ใช่คีย์นอก (ดูหัวข้อ 5)

---

## 3. ไฟล์แผนภาพที่สร้างให้

ทุกภาพมีทั้ง `.png` (สเกลสูง สำหรับ Word และ PowerPoint) และ `.svg` (ขยายได้ไม่แตก)
พร้อมซอร์ส `.mmd` (Mermaid) ที่แก้ไขแล้วเรนเดอร์ใหม่ได้

| ไฟล์ | เนื้อหา | ตาราง | เส้นความสัมพันธ์ |
|---|---|---:|---:|
| `er_postgres` | **ER ฐานข้อมูลฐานความรู้ ครบทุกตาราง** | 28 | 53 |
| `er_postgres_a_documents` | ER ส่วนผู้ใช้ เอกสาร และการค้นคืน (อ่านง่าย) | 10 | 11 |
| `er_postgres_b_metadata` | ER ส่วนข้อมูลเชิงโครงสร้างและการเผยแพร่ (อ่านง่าย) | 20 | 43 |
| `er_supabase` | **ER ฐานข้อมูลระบบเว็บ** | 7 | 7 |
| `architecture_production` | **สถาปัตยกรรมระบบที่ใช้งานจริง** | — | — |

> **ข้อแนะนำสำหรับใส่เล่ม** ภาพ `er_postgres` มีครบ 28 ตารางตามที่กำหนด แต่หนาแน่นเกินกว่าจะอ่าน
> ได้สบายบนกระดาษ A4 จึงสร้างภาพย่อยอีกสองภาพที่อ่านได้ชัดไว้ให้ด้วย
> แนะนำให้ใช้ภาพเต็มเป็นภาพหลัก แล้วใส่ภาพย่อยสองภาพเป็นภาพขยายในหัวข้อถัดไป

### คำสั่งเรนเดอร์ใหม่หลังแก้ซอร์ส

```bash
npx @mermaid-js/mermaid-cli -i er_postgres.mmd -o er_postgres.png -b white -s 4
npx @mermaid-js/mermaid-cli -i er_postgres.mmd -o er_postgres.svg -b white
```

---

## 4. ความสัมพันธ์ที่ SQL ประกาศไว้จริง (60 รายการ)

### 4.1 ฐานข้อมูลฐานความรู้ — 53 รายการ

| ตารางลูก | คอลัมน์ | ชี้ไปยัง | เมื่อลบต้นทาง | ชนิด |
|---|---|---|---|---|
| `mko.credit_groups` | `curriculum_id` | `mko.curricula(id)` | CASCADE | คอลัมน์ |
| `mko.credit_groups` | `run_id` | `mko.extraction_runs(id)` | CASCADE | คอลัมน์ |
| `mko.credit_groups` | `evidence_id` | `mko.evidence(id)` | — | คอลัมน์ |
| `mko.credit_groups` | `parent_id` | `mko.credit_groups(id)` | CASCADE | **วนกลับตนเอง** |
| `mko.curricula` | `course_id` | `public.courses(id)` | CASCADE | คอลัมน์ · ห้ามซ้ำ (1:1) |
| `mko.curricula` | `program_id` | `mko.programs(id)` | — | คอลัมน์ |
| `mko.curricula` | `primary_document_id` | `public.course_documents(id)` | — | คอลัมน์ |
| `mko.document_pages` | `document_id` | `public.course_documents(id)` | CASCADE | คอลัมน์ |
| `mko.document_sections` | `run_id` | `mko.extraction_runs(id)` | CASCADE | คอลัมน์ |
| `mko.document_sections` | `document_id` | `public.course_documents(id)` | CASCADE | คอลัมน์ |
| `mko.evidence` | `run_id` | `mko.extraction_runs(id)` | CASCADE | คอลัมน์ |
| `mko.evidence` | `section_id` | `mko.document_sections(id)` | SET NULL | คอลัมน์ |
| `mko.evidence` | `document_id, page_start` | `mko.document_pages(document_id, page_number)` | CASCADE | **คีย์นอกแบบผสม** |
| `mko.evidence` | `document_id, page_end` | `mko.document_pages(document_id, page_number)` | CASCADE | **คีย์นอกแบบผสม** |
| `mko.extraction_runs` | `document_id` | `public.course_documents(id)` | CASCADE | คอลัมน์ |
| `mko.field_value_evidence` | `field_value_id` | `mko.field_values(id)` | CASCADE | **ตารางเชื่อม N:M** |
| `mko.field_value_evidence` | `evidence_id` | `mko.evidence(id)` | CASCADE | **ตารางเชื่อม N:M** |
| `mko.field_values` | `curriculum_id` | `mko.curricula(id)` | CASCADE | คอลัมน์ |
| `mko.field_values` | `run_id` | `mko.extraction_runs(id)` | CASCADE | คอลัมน์ |
| `mko.field_values` | `document_id` | `public.course_documents(id)` | CASCADE | คอลัมน์ |
| `mko.field_values` | `evidence_id` | `mko.evidence(id)` | — | คอลัมน์ |
| `mko.learning_outcomes` | `curriculum_id` | `mko.curricula(id)` | CASCADE | คอลัมน์ |
| `mko.learning_outcomes` | `run_id` | `mko.extraction_runs(id)` | CASCADE | คอลัมน์ |
| `mko.learning_outcomes` | `evidence_id` | `mko.evidence(id)` | — | คอลัมน์ |
| `mko.learning_outcomes` | `parent_id` | `mko.learning_outcomes(id)` | CASCADE | **วนกลับตนเอง** |
| `mko.list_items` | `curriculum_id` | `mko.curricula(id)` | CASCADE | คอลัมน์ |
| `mko.list_items` | `run_id` | `mko.extraction_runs(id)` | CASCADE | คอลัมน์ |
| `mko.list_items` | `document_id` | `public.course_documents(id)` | CASCADE | คอลัมน์ |
| `mko.list_items` | `evidence_id` | `mko.evidence(id)` | — | คอลัมน์ |
| `mko.published_list_items` | `publication_id` | `mko.publications(id)` | CASCADE | คอลัมน์ |
| `mko.published_list_items` | `course_id` | `public.courses(id)` | CASCADE | คอลัมน์ |
| `mko.published_list_items` | `document_id` | `public.course_documents(id)` | CASCADE | คอลัมน์ |
| `mko.published_values` | `publication_id` | `mko.publications(id)` | CASCADE | คอลัมน์ |
| `mko.published_values` | `course_id` | `public.courses(id)` | CASCADE | คอลัมน์ |
| `mko.published_values` | `document_id` | `public.course_documents(id)` | CASCADE | คอลัมน์ |
| `mko.review_decisions` | `document_id` | `public.course_documents(id)` | CASCADE | คอลัมน์ |
| `mko.shadow_answers` | `publication_id` | `mko.publications(id)` | SET NULL | คอลัมน์ |
| `mko.subjects` | `curriculum_id` | `mko.curricula(id)` | CASCADE | คอลัมน์ |
| `mko.subjects` | `run_id` | `mko.extraction_runs(id)` | CASCADE | คอลัมน์ |
| `mko.subjects` | `credit_group_id` | `mko.credit_groups(id)` | SET NULL | คอลัมน์ |
| `mko.subjects` | `listing_evidence_id` | `mko.evidence(id)` | — | คอลัมน์ |
| `mko.subjects` | `description_evidence_id` | `mko.evidence(id)` | — | คอลัมน์ |
| `public.chat_messages` | `session_id` | `public.chat_sessions(id)` | CASCADE | คอลัมน์ |
| `public.chat_sessions` | `user_id` | `public.users(id)` | CASCADE | คอลัมน์ |
| `public.course_chunks` | `course_id` | `public.courses(id)` | CASCADE | คอลัมน์ |
| `public.course_chunks` | `document_id` | `public.course_documents(id)` | CASCADE | คอลัมน์ |
| `public.course_documents` | `course_id` | `public.courses(id)` | CASCADE | คอลัมน์ |
| `public.course_documents` | `uploaded_by` | `public.users(id)` | — | คอลัมน์ |
| `public.recommendations` | `user_id` | `public.users(id)` | CASCADE | คอลัมน์ |
| `public.recommendations` | `course_id` | `public.courses(id)` | CASCADE | คอลัมน์ |
| `public.recommendations` | `session_id` | `public.chat_sessions(id)` | SET NULL | คอลัมน์ |
| `public.user_profiles` | `user_id` | `public.users(id)` | CASCADE | คอลัมน์ · เป็นคีย์หลักด้วย (1:1) |
| `public.user_requirements` | `user_id` | `public.users(id)` | CASCADE | คอลัมน์ |

### 4.2 ฐานข้อมูลระบบเว็บ — 7 รายการ

| ตารางลูก | คอลัมน์ | ชี้ไปยัง | เมื่อลบต้นทาง |
|---|---|---|---|
| `ai_settings` | `updated_by` | `auth.users(id)` | — |
| `courses` | `created_by` | `auth.users(id)` | — |
| `courses` | `updated_by` | `public.user_profiles(user_id)` | — |
| `knowledge_articles` | `created_by` | `auth.users(id)` | — |
| `knowledge_articles` | `updated_by` | `auth.users(id)` | — |
| `news` | `created_by` | `auth.users(id)` | — |
| `news` | `updated_by` | `public.user_profiles(user_id)` | — |

> `auth.users` เป็นตารางของระบบยืนยันตัวตนที่ Supabase สร้างให้เอง ไม่ได้ประกาศใน `supabase_schema.sql`
> จึงแสดงในแผนภาพเป็นกล่องที่ไม่มีรายละเอียดคอลัมน์

---

## 5. ความสัมพันธ์เชิงตรรกะ — มีในทางความหมาย แต่ **ไม่มีคีย์นอกใน SQL**

รายการเหล่านี้ **ไม่ได้ถูกวาดเป็นเส้นในแผนภาพ ER** เพราะฐานข้อมูลไม่ได้บังคับไว้
ความถูกต้องขึ้นกับโค้ดของระบบเท่านั้น

| # | ความสัมพันธ์ | บังคับที่ไหน | เหตุผลที่ไม่มีคีย์นอก |
|:--:|---|---|---|
| 1 | **`supabase.courses.title` ↔ `postgres.courses.title`** | ฟังก์ชัน `normalise_title()` และ `match_by_title()` ในระบบส่วนหลัง | อยู่คนละฐานข้อมูลกัน คีย์นอกข้ามฐานทำไม่ได้ |
| 2 | `supabase.rag_documents.source_id` → `courses.id` หรือ `news.id` หรือ `knowledge_articles.id` | โค้ดฝั่ง `api/_lib/ingest.js` | เป็นการอ้างอิงแบบหลายรูปแบบ ตารางปลายทางขึ้นกับค่าใน `source_type` |
| 3 | `public.recommendations.retrieved_chunk_ids` → `public.course_chunks.id` | โค้ดฝั่งระบบส่วนหลัง | เก็บเป็นอาร์เรย์ `UUID[]` ซึ่งประกาศคีย์นอกไม่ได้ |
| 4 | `mko.shadow_answers.course_ids` → `public.courses.id` | โค้ดฝั่งระบบส่วนหลัง | เก็บเป็นอาร์เรย์ `UUID[]` |
| 5 | `public.course_documents.file_sha256` → ไฟล์ใน `/srv/documents` | `FilesystemDocumentStore` ตรวจลายนิ้วมือก่อนส่งไฟล์ | ปลายทางเป็นไฟล์ในระบบไฟล์ ไม่ใช่แถวในตาราง |
| 6 | `supabase.courses.logo` → ไฟล์ภาพใน `/assets/courses/*.png` | หน้าเว็บโหลดตามที่อยู่ที่เก็บไว้ | ปลายทางเป็นไฟล์นิ่ง ไม่ใช่แถวในตาราง |
| 7 | `mko.published_values` / `published_list_items` เก็บ `source_filename`, `page_start`, `quote` ซ้ำจากตาราง `evidence` | ขั้นตอนเผยแพร่ในโค้ด | **ลดรูปบรรทัดฐานโดยเจตนา** เพื่อให้ภาพถ่ายข้อมูลคงที่ ไม่เปลี่ยนตามต้นทาง |

---

## 6. วิว (View) ทั้ง 6 รายการ

| วิว | อ่านจาก | ใช้ทำอะไร |
|---|---|---|
| `mko.v_live_publication` | `mko.publications` | การเผยแพร่ครั้งล่าสุดเพียงรายการเดียว (เรียงตามเวลา แล้วเอาแถวแรก) |
| `mko.v_live_values` | `published_values` + `v_live_publication` + `courses` | ค่าเดี่ยวของชุดที่ใช้อยู่จริง กรองเฉพาะหลักสูตรที่ `is_active` |
| `mko.v_live_list_items` | `published_list_items` + `v_live_publication` + `courses` | รายการของชุดที่ใช้อยู่จริง กรองเฉพาะหลักสูตรที่ `is_active` |
| `mko.v_published_curricula` | `mko.curricula` | หลักสูตรที่มีสถานะ `published` |
| `mko.v_published_field_values` | `field_values` + `curricula` | ค่าที่ `verified` ของหลักสูตรที่เผยแพร่แล้ว |
| `mko.v_published_list_items` | `list_items` + `curricula` | รายการที่ `verified` ของหลักสูตรที่เผยแพร่แล้ว |

**หลักสำคัญ** บัญชี `advisor_api` ที่ระบบส่วนหลังใช้ **ได้สิทธิ์อ่านเฉพาะวิว `v_live_*` สามรายการแรก**
และเขียนได้เฉพาะตาราง `mko.shadow_answers` เท่านั้น ข้อมูลที่ยังไม่ผ่านการตรวจจึงไม่มีทางไปถึงผู้ใช้

---

## 7. ดัชนีที่ประกาศไว้ 29 รายการ

### 7.1 ฐานข้อมูลฐานความรู้ (15)

| ดัชนี | ตาราง | ชนิด | คอลัมน์ | วัตถุประสงค์ |
|---|---|---|---|---|
| `idx_course_chunks_embedding` | `course_chunks` | **IVFFlat** | `embedding vector_cosine_ops` | ค้นส่วนข้อความที่ใกล้เคียงคำถามเชิงความหมาย |
| `idx_courses_tags` | `courses` | **GIN** | `tags` | ค้นภายในข้อมูล JSON |
| `idx_course_chunks_course` | `course_chunks` | B-tree | `course_id` | กรองตามหลักสูตร |
| `idx_chat_messages_session` | `chat_messages` | B-tree | `session_id` | ดึงข้อความตามรอบสนทนา |
| `idx_recommendations_user` | `recommendations` | B-tree | `user_id` | ประวัติคำแนะนำของผู้ใช้ |
| `idx_chat_answer_cache_version` | `chat_answer_cache` | B-tree | `corpus_version` | ทำให้คำตอบของคลังรุ่นเก่าหมดอายุเอง |
| `idx_user_requirements_user` | `user_requirements` | B-tree | `user_id` | เงื่อนไขของผู้ใช้ |
| `idx_user_requirements_type` | `user_requirements` | B-tree | `req_type` | กรองตามประเภทเงื่อนไข |
| `idx_field_values_lookup` | `mko.field_values` | B-tree ผสม | `curriculum_id, field_key, status` | ค้นค่าตามหลักสูตรและช่องข้อมูล |
| `idx_field_values_run` | `mko.field_values` | B-tree | `run_id` | ค้นตามรอบสกัด |
| `idx_list_items_lookup` | `mko.list_items` | B-tree ผสม | `curriculum_id, item_type, status` | ค้นรายการตามหลักสูตรและประเภท |
| `idx_document_sections_run` | `mko.document_sections` | B-tree ผสม | `run_id, section_key` | ค้นหัวข้อของรอบสกัด |
| `idx_extraction_runs_document` | `mko.extraction_runs` | B-tree ผสม | `document_id, started_at DESC` | ดูรอบสกัดล่าสุดของเอกสาร |
| `idx_shadow_answers_created` | `mko.shadow_answers` | B-tree | `created_at DESC` | ดูบันทึกล่าสุดก่อน |
| `uq_review_decisions_active` | `mko.review_decisions` | **UNIQUE บางส่วน** | `document_id, field_key, value_key` **WHERE `superseded_at IS NULL`** | เก็บประวัติการตรวจได้ไม่จำกัด แต่บังคับว่าการตัดสินที่ยังมีผลมีได้รายการเดียว |

### 7.2 ฐานข้อมูลระบบเว็บ (14)

| ดัชนี | ตาราง | ชนิด | คอลัมน์ |
|---|---|---|---|
| `idx_rag_documents_embedding` | `rag_documents` | **IVFFlat** | `embedding vector_cosine_ops` |
| `idx_rag_documents_source` | `rag_documents` | B-tree ผสม | `source_type, source_id` |
| `idx_external_news_slug` | `external_news` | **UNIQUE** | `slug` |
| `idx_external_news_published_at` | `external_news` | B-tree | `published_at DESC` |
| `idx_external_news_source` | `external_news` | B-tree | `source` |
| `idx_news_date` · `idx_news_category` · `idx_news_status` · `idx_news_created_at` | `news` | B-tree | ตามชื่อ |
| `idx_courses_created_at` | `courses` | B-tree | `created_at DESC` |
| `idx_knowledge_articles_created_at` | `knowledge_articles` | B-tree | `created_at DESC` |
| `idx_user_profiles_user_id` · `idx_user_profiles_role` · `idx_user_profiles_status` | `user_profiles` | B-tree | ตามชื่อ |

> ยังไม่นับดัชนีที่ PostgreSQL สร้างให้เองโดยอัตโนมัติจาก `PRIMARY KEY` และ `UNIQUE`
> ซึ่งมีอีกอย่างน้อย 35 รายการจากคีย์หลักของทุกตาราง

---


## 8. พจนานุกรมข้อมูล (Data Dictionary)

คอลัมน์ PK และ FK แสดงเฉพาะที่ SQL ประกาศไว้จริง ไม่มีการเดาเพิ่ม


## ส่วนที่ 1 — ฐานข้อมูลฐานความรู้ (PostgreSQL 16 + pgvector)

### ตาราง `mko.credit_groups`

| คอลัมน์ | ชนิดข้อมูล | PK | FK | Null ได้ | คำอธิบาย |
|---|---|:--:|---|:--:|---|
| `id` | UUID | ✔ |  | ไม่ได้ | รหัสประจำแถว (คีย์หลัก) |
| `curriculum_id` | UUID |  | → mko.curricula(id) cascade | ไม่ได้ | หลักสูตรรายฉบับปีที่แถวนี้สังกัด |
| `run_id` | UUID |  | → mko.extraction_runs(id) cascade | ไม่ได้ | รอบการสกัดข้อมูลที่ทำให้เกิดแถวนี้ |
| `parent_id` | UUID |  | → mko.credit_groups(id) cascade | ได้ | หมวดหน่วยกิตแม่ ใช้สร้างโครงสร้างลำดับชั้น |
| `seq` | SMALLINT |  |  | ไม่ได้ | ลำดับของรายการภายในกลุ่มเดียวกัน เริ่มที่ 1 |
| `name_th` | TEXT |  |  | ไม่ได้ | ชื่อหมวดหน่วยกิต |
| `min_credits` | SMALLINT |  |  | ได้ | จำนวนหน่วยกิตขั้นต่ำของหมวดนี้ |
| `status` | TEXT |  |  | ไม่ได้ | สถานะการตรวจ |
| `reason` | TEXT |  |  | ได้ | เหตุผลของสถานะที่ระบุไว้ |
| `evidence_id` | UUID |  | → mko.evidence(id) | ไม่ได้ | หลักฐานหลักที่รองรับค่านี้ |
| `reviewed_by` | TEXT |  |  | ได้ | ผู้ยืนยันค่า ขึ้นต้นด้วย human: เมื่อคนตรวจ หรือ auto: เมื่อกฎอัตโนมัติยืนยัน |
| `reviewed_at` | TIMESTAMPTZ |  |  | ได้ | เวลาที่ตรวจยืนยัน |

### ตาราง `mko.curricula`

| คอลัมน์ | ชนิดข้อมูล | PK | FK | Null ได้ | คำอธิบาย |
|---|---|:--:|---|:--:|---|
| `id` | UUID | ✔ |  | ไม่ได้ | รหัสประจำแถว (คีย์หลัก) |
| `course_id` | UUID |  | → public.courses(id) cascade | ไม่ได้ | หลักสูตรที่เกี่ยวข้อง |
| `program_id` | UUID |  | → mko.programs(id) | ได้ | สาขาที่หลักสูตรฉบับนี้สังกัด ห้ามซ้ำเมื่อรวมกับปีของฉบับ |
| `edition_year_be` | SMALLINT |  |  | ได้ | ปีพุทธศักราชของฉบับหลักสูตร ต้องอยู่ระหว่าง 2500 ถึง 2700 |
| `revision_type` | TEXT |  |  | ได้ | ชนิดของฉบับ new หรือ revised |
| `template_type` | TEXT |  |  | ได้ | รูปแบบของเล่มที่ใช้สกัด |
| `primary_document_id` | UUID |  | → public.course_documents(id) | ได้ | เอกสารหลักของหลักสูตรฉบับนี้ |
| `program_name_th` | TEXT |  |  | ได้ | ชื่อหลักสูตรภาษาไทยที่เติมตอนเผยแพร่ |
| `program_name_en` | TEXT |  |  | ได้ | ชื่อหลักสูตรภาษาอังกฤษที่เติมตอนเผยแพร่ |
| `degree_name_th` | TEXT |  |  | ได้ | ชื่อปริญญาภาษาไทย |
| `degree_name_en` | TEXT |  |  | ได้ | ชื่อปริญญาภาษาอังกฤษ |
| `degree_abbr_th` | TEXT |  |  | ได้ | ชื่อย่อปริญญาภาษาไทย |
| `degree_abbr_en` | TEXT |  |  | ได้ | ชื่อย่อปริญญาภาษาอังกฤษ |
| `degree_level` | TEXT |  |  | ได้ | ระดับปริญญา bachelor, master หรือ doctoral |
| `total_credits` | SMALLINT |  |  | ได้ | จำนวนหน่วยกิตรวมตลอดหลักสูตร ต้องอยู่ระหว่าง 1 ถึง 400 |
| `study_years` | NUMERIC(3, 1) |  |  | ได้ | จำนวนปีที่ใช้ศึกษา |
| `language` | TEXT |  |  | ได้ | ภาษาที่ใช้ในการเรียนการสอน |
| `status` | TEXT |  |  | ไม่ได้ | สถานะของหลักสูตรฉบับนี้ draft, in_review หรือ published |
| `published_at` | TIMESTAMPTZ |  |  | ได้ | เวลาที่เผยแพร่ |
| `created_at` | TIMESTAMPTZ |  |  | ไม่ได้ | เวลาที่สร้างแถวนี้ |
| `updated_at` | TIMESTAMPTZ |  |  | ไม่ได้ | เวลาที่แก้ไขแถวนี้ล่าสุด |

**ห้ามซ้ำ:** (program_id, edition_year_be)

### ตาราง `mko.document_pages`

| คอลัมน์ | ชนิดข้อมูล | PK | FK | Null ได้ | คำอธิบาย |
|---|---|:--:|---|:--:|---|
| `document_id` | UUID | ✔ | → public.course_documents(id) cascade | ไม่ได้ | เอกสารต้นทาง |
| `page_number` | INTEGER | ✔ |  | ไม่ได้ | เลขหน้าในเอกสาร ต้องมากกว่าหรือเท่ากับ 1 |
| `text_raw` | TEXT |  |  | ไม่ได้ | ข้อความของหน้าหลังเติม OCR แต่ยังไม่ทำความสะอาด |
| `text_clean` | TEXT |  |  | ไม่ได้ | ข้อความที่ตัวสกัดอ่าน และเป็นข้อความที่หลักฐานต้องยกมาจาก |
| `text_source` | TEXT |  |  | ไม่ได้ | ที่มาของข้อความ text_layer, ocr, text_layer+ocr หรือ plain_text |
| `is_toc` | BOOLEAN |  |  | ไม่ได้ | เป็นหน้าสารบัญหรือไม่ ใช้ข้ามตอนสกัด |
| `encoding_suspect` | BOOLEAN |  |  | ไม่ได้ | พบรูปอักษรที่เพี้ยนจากฟอนต์หรือไม่ |
| `text_sha256` | TEXT |  |  | ไม่ได้ | ลายนิ้วมือของข้อความหน้านี้ |
| `created_at` | TIMESTAMPTZ |  |  | ไม่ได้ | เวลาที่สร้างแถวนี้ |

### ตาราง `mko.document_sections`

| คอลัมน์ | ชนิดข้อมูล | PK | FK | Null ได้ | คำอธิบาย |
|---|---|:--:|---|:--:|---|
| `id` | UUID | ✔ |  | ไม่ได้ | รหัสประจำแถว (คีย์หลัก) |
| `run_id` | UUID |  | → mko.extraction_runs(id) cascade | ไม่ได้ | รอบการสกัดข้อมูลที่ทำให้เกิดแถวนี้ |
| `document_id` | UUID |  | → public.course_documents(id) cascade | ไม่ได้ | เอกสารต้นทาง |
| `section_key` | TEXT |  |  | ไม่ได้ | รหัสหัวข้อ เช่น chapter.1, general.careers, appendix |
| `heading_text` | TEXT |  |  | ได้ | ข้อความหัวข้อตามที่ปรากฏในเล่ม |
| `page_start` | INTEGER |  |  | ไม่ได้ | หน้าเริ่มต้นในเอกสารต้นฉบับ |
| `page_end` | INTEGER |  |  | ไม่ได้ | หน้าสิ้นสุดในเอกสารต้นฉบับ ต้องไม่น้อยกว่าหน้าเริ่มต้น |
| `is_appendix` | BOOLEAN |  |  | ไม่ได้ | เป็นภาคผนวกหรือไม่ |

**ข้อกำหนดระดับตาราง:** `CHECK (page_end >= page_start)`

### ตาราง `mko.evidence`

| คอลัมน์ | ชนิดข้อมูล | PK | FK | Null ได้ | คำอธิบาย |
|---|---|:--:|---|:--:|---|
| `id` | UUID | ✔ |  | ไม่ได้ | รหัสประจำแถว (คีย์หลัก) |
| `run_id` | UUID |  | → mko.extraction_runs(id) cascade | ไม่ได้ | รอบการสกัดข้อมูลที่ทำให้เกิดแถวนี้ |
| `document_id` | UUID |  | → mko.document_pages(document_id,page_number) ผสม | ไม่ได้ | เอกสารต้นทาง |
| `page_start` | INTEGER |  | → mko.document_pages(document_id,page_number) ผสม | ไม่ได้ | หน้าเริ่มต้นในเอกสารต้นฉบับ |
| `page_end` | INTEGER |  | → mko.document_pages(document_id,page_number) ผสม | ไม่ได้ | หน้าสิ้นสุดในเอกสารต้นฉบับ ต้องไม่น้อยกว่าหน้าเริ่มต้น |
| `section_id` | UUID |  | → mko.document_sections(id) set null | ได้ | หัวข้อที่หลักฐานชิ้นนี้อยู่ ถ้าระบุได้ |
| `quote` | TEXT |  |  | ไม่ได้ | ข้อความที่ยกมาจากเอกสารต้นฉบับ |
| `method` | TEXT |  |  | ไม่ได้ | วิธีที่ได้หลักฐานมา regex, table_parser, list_parser, llm_span หรือ manual |
| `created_at` | TIMESTAMPTZ |  |  | ไม่ได้ | เวลาที่สร้างแถวนี้ |

**ข้อกำหนดระดับตาราง:** `CHECK (page_end >= page_start)`

### ตาราง `mko.extraction_runs`

| คอลัมน์ | ชนิดข้อมูล | PK | FK | Null ได้ | คำอธิบาย |
|---|---|:--:|---|:--:|---|
| `id` | UUID | ✔ |  | ไม่ได้ | รหัสประจำแถว (คีย์หลัก) |
| `document_id` | UUID |  | → public.course_documents(id) cascade | ไม่ได้ | เอกสารต้นทาง |
| `parser_version` | TEXT |  |  | ไม่ได้ | รุ่นของตัวสกัดที่ใช้ในรอบนี้ |
| `template_type` | TEXT |  |  | ไม่ได้ | รูปแบบของเล่ม tqf2, std2565, brief, web_page หรือ unknown |
| `status` | TEXT |  |  | ไม่ได้ | สถานะของรอบสกัด running, done หรือ failed |
| `summary` | JSONB |  |  | ไม่ได้ | สรุปผลของรอบสกัด เก็บเป็น JSON |
| `error` | TEXT |  |  | ได้ | ข้อความผิดพลาดเมื่อรอบสกัดล้มเหลว |
| `started_at` | TIMESTAMPTZ |  |  | ไม่ได้ | เวลาที่เริ่มรอบสกัด |
| `finished_at` | TIMESTAMPTZ |  |  | ได้ | เวลาที่จบรอบสกัด |

### ตาราง `mko.field_value_evidence`

| คอลัมน์ | ชนิดข้อมูล | PK | FK | Null ได้ | คำอธิบาย |
|---|---|:--:|---|:--:|---|
| `field_value_id` | UUID | ✔ | → mko.field_values(id) cascade | ไม่ได้ | ค่าที่ถูกอ้างถึง |
| `evidence_id` | UUID | ✔ | → mko.evidence(id) cascade | ไม่ได้ | หลักฐานที่รองรับค่านั้น |

### ตาราง `mko.field_values`

| คอลัมน์ | ชนิดข้อมูล | PK | FK | Null ได้ | คำอธิบาย |
|---|---|:--:|---|:--:|---|
| `id` | UUID | ✔ |  | ไม่ได้ | รหัสประจำแถว (คีย์หลัก) |
| `curriculum_id` | UUID |  | → mko.curricula(id) cascade | ไม่ได้ | หลักสูตรรายฉบับปีที่แถวนี้สังกัด |
| `run_id` | UUID |  | → mko.extraction_runs(id) cascade | ไม่ได้ | รอบการสกัดข้อมูลที่ทำให้เกิดแถวนี้ |
| `document_id` | UUID |  | → public.course_documents(id) cascade | ไม่ได้ | เอกสารต้นทาง |
| `field_key` | TEXT |  |  | ไม่ได้ | ชื่อช่องข้อมูล เช่น total_credits, edition_year, degree_level |
| `value_text` | TEXT |  |  | ได้ | ค่าที่เป็นข้อความ |
| `value_int` | INTEGER |  |  | ได้ | ค่าที่เป็นจำนวนเต็ม |
| `status` | TEXT |  |  | ไม่ได้ | สถานะของค่า candidate, needs_review, verified, rejected, not_found หรือ not_applicable |
| `reason` | TEXT |  |  | ได้ | เหตุผลของสถานะที่ระบุไว้ |
| `confidence` | NUMERIC(4, 3) |  |  | ได้ | ระดับความมั่นใจของตัวสกัดระหว่าง 0 ถึง 1 |
| `evidence_id` | UUID |  | → mko.evidence(id) | ได้ | หลักฐานหลักที่รองรับค่านี้ |
| `reviewed_by` | TEXT |  |  | ได้ | ผู้ยืนยันค่า ขึ้นต้นด้วย human: เมื่อคนตรวจ หรือ auto: เมื่อกฎอัตโนมัติยืนยัน |
| `reviewed_at` | TIMESTAMPTZ |  |  | ได้ | เวลาที่ตรวจยืนยัน |
| `created_at` | TIMESTAMPTZ |  |  | ไม่ได้ | เวลาที่สร้างแถวนี้ |

**ข้อกำหนดระดับตาราง:** `CONSTRAINT field_value_evidence_rule CHECK ( (status IN ('not_found', 'not_applicable') AND value_text IS NULL AND value_int IS NULL AND evidence_id I` · `CONSTRAINT field_value_verified_reviewer CHECK (status <> 'verified' OR reviewed_by IS NOT NULL)`

### ตาราง `mko.learning_outcomes`

| คอลัมน์ | ชนิดข้อมูล | PK | FK | Null ได้ | คำอธิบาย |
|---|---|:--:|---|:--:|---|
| `id` | UUID | ✔ |  | ไม่ได้ | รหัสประจำแถว (คีย์หลัก) |
| `curriculum_id` | UUID |  | → mko.curricula(id) cascade | ไม่ได้ | หลักสูตรรายฉบับปีที่แถวนี้สังกัด |
| `run_id` | UUID |  | → mko.extraction_runs(id) cascade | ไม่ได้ | รอบการสกัดข้อมูลที่ทำให้เกิดแถวนี้ |
| `framework` | TEXT |  |  | ไม่ได้ | กรอบของผลลัพธ์การเรียนรู้ PLO, SubPLO, YLO หรือ TQF_domain |
| `code` | TEXT |  |  | ได้ | รหัสผลลัพธ์การเรียนรู้ |
| `parent_id` | UUID |  | → mko.learning_outcomes(id) cascade | ได้ | ผลลัพธ์การเรียนรู้แม่ ใช้สร้างลำดับชั้น |
| `seq` | SMALLINT |  |  | ไม่ได้ | ลำดับของรายการภายในกลุ่มเดียวกัน เริ่มที่ 1 |
| `text` | TEXT |  |  | ไม่ได้ | เนื้อความของผลลัพธ์การเรียนรู้ |
| `status` | TEXT |  |  | ไม่ได้ | สถานะการตรวจ |
| `reason` | TEXT |  |  | ได้ | เหตุผลของสถานะที่ระบุไว้ |
| `evidence_id` | UUID |  | → mko.evidence(id) | ไม่ได้ | หลักฐานหลักที่รองรับค่านี้ |
| `reviewed_by` | TEXT |  |  | ได้ | ผู้ยืนยันค่า ขึ้นต้นด้วย human: เมื่อคนตรวจ หรือ auto: เมื่อกฎอัตโนมัติยืนยัน |
| `reviewed_at` | TIMESTAMPTZ |  |  | ได้ | เวลาที่ตรวจยืนยัน |

### ตาราง `mko.list_items`

| คอลัมน์ | ชนิดข้อมูล | PK | FK | Null ได้ | คำอธิบาย |
|---|---|:--:|---|:--:|---|
| `id` | UUID | ✔ |  | ไม่ได้ | รหัสประจำแถว (คีย์หลัก) |
| `curriculum_id` | UUID |  | → mko.curricula(id) cascade | ไม่ได้ | หลักสูตรรายฉบับปีที่แถวนี้สังกัด |
| `run_id` | UUID |  | → mko.extraction_runs(id) cascade | ไม่ได้ | รอบการสกัดข้อมูลที่ทำให้เกิดแถวนี้ |
| `document_id` | UUID |  | → public.course_documents(id) cascade | ไม่ได้ | เอกสารต้นทาง |
| `item_type` | TEXT |  |  | ไม่ได้ | ประเภทของรายการ philosophy, objective, career หรือ admission |
| `seq` | SMALLINT |  |  | ไม่ได้ | ลำดับของรายการภายในกลุ่มเดียวกัน เริ่มที่ 1 |
| `text` | TEXT |  |  | ไม่ได้ | เนื้อความของรายการ ห้ามเป็นข้อความว่าง |
| `status` | TEXT |  |  | ไม่ได้ | สถานะการตรวจ candidate, needs_review, verified หรือ rejected |
| `reason` | TEXT |  |  | ได้ | เหตุผลของสถานะที่ระบุไว้ |
| `evidence_id` | UUID |  | → mko.evidence(id) | ไม่ได้ | หลักฐานหลักที่รองรับค่านี้ |
| `reviewed_by` | TEXT |  |  | ได้ | ผู้ยืนยันค่า ขึ้นต้นด้วย human: เมื่อคนตรวจ หรือ auto: เมื่อกฎอัตโนมัติยืนยัน |
| `reviewed_at` | TIMESTAMPTZ |  |  | ได้ | เวลาที่ตรวจยืนยัน |
| `created_at` | TIMESTAMPTZ |  |  | ไม่ได้ | เวลาที่สร้างแถวนี้ |

**ห้ามซ้ำ:** (run_id, item_type, seq)
**ข้อกำหนดระดับตาราง:** `CONSTRAINT list_item_verified_reviewer CHECK (status <> 'verified' OR reviewed_by IS NOT NULL)`

### ตาราง `mko.programs`

| คอลัมน์ | ชนิดข้อมูล | PK | FK | Null ได้ | คำอธิบาย |
|---|---|:--:|---|:--:|---|
| `id` | UUID | ✔ |  | ไม่ได้ | รหัสประจำแถว (คีย์หลัก) |
| `name_th` | TEXT |  |  | ไม่ได้ | ชื่อสาขาภาษาไทย ห้ามซ้ำเมื่อรวมกับระดับปริญญา |
| `name_en` | TEXT |  |  | ได้ | ชื่อสาขาภาษาอังกฤษ |
| `degree_level` | TEXT |  |  | ไม่ได้ | ระดับปริญญา bachelor, master หรือ doctoral |
| `created_at` | TIMESTAMPTZ |  |  | ไม่ได้ | เวลาที่สร้างแถวนี้ |

**ห้ามซ้ำ:** (name_th, degree_level)

### ตาราง `mko.publications`

| คอลัมน์ | ชนิดข้อมูล | PK | FK | Null ได้ | คำอธิบาย |
|---|---|:--:|---|:--:|---|
| `id` | UUID | ✔ |  | ไม่ได้ | รหัสประจำแถว (คีย์หลัก) |
| `published_at` | TIMESTAMPTZ |  |  | ไม่ได้ | เวลาที่เผยแพร่ชุดนี้ |
| `published_by` | TEXT |  |  | ไม่ได้ | ผู้สั่งเผยแพร่ ห้ามเป็นข้อความว่าง |
| `policy` | TEXT |  |  | ไม่ได้ | นโยบายที่ใช้คัดข้อมูล verified_any หรือ verified_human_only |
| `parser_version` | TEXT |  |  | ไม่ได้ | รุ่นของตัวสกัดที่ข้อมูลในชุดนี้มาจาก |
| `summary` | JSONB |  |  | ไม่ได้ | สรุปจำนวนและรายละเอียดของชุดที่เผยแพร่ |

### ตาราง `mko.published_list_items`

| คอลัมน์ | ชนิดข้อมูล | PK | FK | Null ได้ | คำอธิบาย |
|---|---|:--:|---|:--:|---|
| `publication_id` | UUID | ✔ | → mko.publications(id) cascade | ไม่ได้ | ชุดการเผยแพร่ที่แถวนี้อยู่ |
| `course_id` | UUID | ✔ | → public.courses(id) cascade | ไม่ได้ | หลักสูตรที่เกี่ยวข้อง |
| `item_type` | TEXT | ✔ |  | ไม่ได้ | ประเภทของรายการที่เผยแพร่ objective, career หรือ admission |
| `seq` | SMALLINT | ✔ |  | ไม่ได้ | ลำดับของรายการภายในกลุ่มเดียวกัน เริ่มที่ 1 |
| `text` | TEXT |  |  | ไม่ได้ | เนื้อความของรายการ ห้ามเป็นข้อความว่าง |
| `document_id` | UUID |  | → public.course_documents(id) cascade | ไม่ได้ | เอกสารต้นทาง |
| `source_filename` | TEXT |  |  | ไม่ได้ | ชื่อไฟล์เอกสารต้นฉบับ เก็บซ้ำไว้เพื่อให้ภาพถ่ายข้อมูลคงที่ |
| `page_start` | INTEGER |  |  | ไม่ได้ | หน้าเริ่มต้นในเอกสารต้นฉบับ |
| `page_end` | INTEGER |  |  | ไม่ได้ | หน้าสิ้นสุดในเอกสารต้นฉบับ ต้องไม่น้อยกว่าหน้าเริ่มต้น |
| `reviewed_by` | TEXT |  |  | ไม่ได้ | ผู้ยืนยันค่า ขึ้นต้นด้วย human: เมื่อคนตรวจ หรือ auto: เมื่อกฎอัตโนมัติยืนยัน |

**ข้อกำหนดระดับตาราง:** `CHECK (page_end >= page_start)`

### ตาราง `mko.published_values`

| คอลัมน์ | ชนิดข้อมูล | PK | FK | Null ได้ | คำอธิบาย |
|---|---|:--:|---|:--:|---|
| `publication_id` | UUID | ✔ | → mko.publications(id) cascade | ไม่ได้ | ชุดการเผยแพร่ที่แถวนี้อยู่ |
| `course_id` | UUID | ✔ | → public.courses(id) cascade | ไม่ได้ | หลักสูตรที่เกี่ยวข้อง |
| `field_key` | TEXT | ✔ |  | ไม่ได้ | ช่องข้อมูลที่เผยแพร่ |
| `value_text` | TEXT |  |  | ได้ | ค่าที่เป็นข้อความ |
| `value_int` | INTEGER |  |  | ได้ | ค่าที่เป็นจำนวนเต็ม |
| `document_id` | UUID |  | → public.course_documents(id) cascade | ไม่ได้ | เอกสารต้นทาง |
| `source_filename` | TEXT |  |  | ไม่ได้ | ชื่อไฟล์เอกสารต้นฉบับ เก็บซ้ำไว้เพื่อให้ภาพถ่ายข้อมูลคงที่ |
| `page_start` | INTEGER |  |  | ไม่ได้ | หน้าเริ่มต้นในเอกสารต้นฉบับ |
| `page_end` | INTEGER |  |  | ไม่ได้ | หน้าสิ้นสุดในเอกสารต้นฉบับ ต้องไม่น้อยกว่าหน้าเริ่มต้น |
| `quote` | TEXT |  |  | ไม่ได้ | ข้อความที่ยกมาจากเอกสารต้นฉบับ |
| `reviewed_by` | TEXT |  |  | ไม่ได้ | ผู้ยืนยันค่า ขึ้นต้นด้วย human: เมื่อคนตรวจ หรือ auto: เมื่อกฎอัตโนมัติยืนยัน |

**ข้อกำหนดระดับตาราง:** `CHECK (value_text IS NOT NULL OR value_int IS NOT NULL)` · `CHECK (page_end >= page_start)`

### ตาราง `mko.review_decisions`

| คอลัมน์ | ชนิดข้อมูล | PK | FK | Null ได้ | คำอธิบาย |
|---|---|:--:|---|:--:|---|
| `id` | UUID | ✔ |  | ไม่ได้ | รหัสประจำแถว (คีย์หลัก) |
| `document_id` | UUID |  | → public.course_documents(id) cascade | ไม่ได้ | เอกสารต้นทาง |
| `document_sha256` | TEXT |  |  | ไม่ได้ | ลายนิ้วมือของเอกสารตอนที่ตรวจ ทำให้ผลตรวจไม่หายเมื่อสกัดใหม่ |
| `field_key` | TEXT |  |  | ไม่ได้ | ช่องข้อมูลที่ถูกตรวจ |
| `value_key` | TEXT |  |  | ไม่ได้ | ค่าที่ตรวจในรูปที่ใช้เทียบ เช่น ตัวเลข ข้อความที่ปรับรูปแล้ว หรือแฮชของรายการ |
| `shown_value` | TEXT |  |  | ได้ | ค่าที่ผู้ตรวจเห็นตอนตัดสิน |
| `decision` | TEXT |  |  | ไม่ได้ | ผลการตัดสิน verified หรือ rejected |
| `reviewer` | TEXT |  |  | ไม่ได้ | ผู้ตรวจ ห้ามเป็นข้อความว่าง |
| `note` | TEXT |  |  | ได้ | บันทึกเพิ่มเติมของผู้ตรวจ |
| `decided_at` | TIMESTAMPTZ |  |  | ไม่ได้ | เวลาที่ตัดสิน |
| `superseded_at` | TIMESTAMPTZ |  |  | ได้ | เวลาที่การตัดสินนี้ถูกแทนที่ ถ้ายังมีผลอยู่จะเป็นค่าว่าง |

### ตาราง `mko.schema_migrations`

| คอลัมน์ | ชนิดข้อมูล | PK | FK | Null ได้ | คำอธิบาย |
|---|---|:--:|---|:--:|---|
| `version` | TEXT | ✔ |  | ไม่ได้ | รหัสรุ่นของโครงสร้างฐานข้อมูลที่ติดตั้งแล้ว |
| `applied_at` | TIMESTAMPTZ |  |  | ไม่ได้ | เวลาที่ติดตั้งรุ่นนี้ |

### ตาราง `mko.shadow_answers`

| คอลัมน์ | ชนิดข้อมูล | PK | FK | Null ได้ | คำอธิบาย |
|---|---|:--:|---|:--:|---|
| `id` | UUID | ✔ |  | ไม่ได้ | รหัสประจำแถว (คีย์หลัก) |
| `created_at` | TIMESTAMPTZ |  |  | ไม่ได้ | เวลาที่สร้างแถวนี้ |
| `mode` | TEXT |  |  | ไม่ได้ | โหมดที่บันทึก shadow หรือ replay |
| `question` | TEXT |  |  | ไม่ได้ | คำถามที่ผู้ใช้ถาม |
| `interpreted_question` | TEXT |  |  | ได้ | คำถามหลังตีความบริบทการสนทนาก่อนหน้า |
| `has_history` | BOOLEAN |  |  | ไม่ได้ | คำถามนี้มีบทสนทนาก่อนหน้าหรือไม่ |
| `intent_field` | TEXT |  |  | ได้ | ช่องข้อมูลที่ระบบตีความว่าผู้ใช้ถามถึง |
| `route` | TEXT |  |  | ไม่ได้ | เส้นทางที่ใช้ตอบ structured หรือ rag |
| `route_reason` | TEXT |  |  | ไม่ได้ | เหตุผลที่เลือกเส้นทางนั้น |
| `course_ids` | UUID[] |  |  | ไม่ได้ | รายการหลักสูตรที่เกี่ยวข้องกับคำถาม |
| `structured_status` | TEXT |  |  | ไม่ได้ | ผลของเส้นทางข้อมูลเชิงโครงสร้าง answered, no_data หรือ not_applicable |
| `structured_answer` | TEXT |  |  | ได้ | คำตอบที่ได้จากข้อมูลเชิงโครงสร้าง |
| `facts` | JSONB |  |  | ไม่ได้ | รายการข้อเท็จจริงที่ใช้ประกอบคำตอบ |
| `publication_id` | UUID |  | → mko.publications(id) set null | ได้ | ชุดการเผยแพร่ที่แถวนี้อยู่ |
| `served_status` | TEXT |  |  | ได้ | สถานะของคำตอบที่ผู้ใช้ได้รับจริง |
| `served_reply` | TEXT |  |  | ได้ | คำตอบที่ผู้ใช้ได้รับจริง |
| `comparison` | TEXT |  |  | ไม่ได้ | ผลเทียบสองคำตอบ agree, partial, disagree, served_no_answer, unclear หรือ not_compared |
| `comparison_detail` | JSONB |  |  | ไม่ได้ | รายละเอียดการเทียบ |
| `latency_ms` | INTEGER |  |  | ได้ | เวลาที่ใช้ตอบเป็นมิลลิวินาที |

### ตาราง `mko.subjects`

| คอลัมน์ | ชนิดข้อมูล | PK | FK | Null ได้ | คำอธิบาย |
|---|---|:--:|---|:--:|---|
| `id` | UUID | ✔ |  | ไม่ได้ | รหัสประจำแถว (คีย์หลัก) |
| `curriculum_id` | UUID |  | → mko.curricula(id) cascade | ไม่ได้ | หลักสูตรรายฉบับปีที่แถวนี้สังกัด |
| `run_id` | UUID |  | → mko.extraction_runs(id) cascade | ไม่ได้ | รอบการสกัดข้อมูลที่ทำให้เกิดแถวนี้ |
| `code` | TEXT |  |  | ไม่ได้ | รหัสวิชา เก็บเป็นข้อความเพราะขึ้นต้นด้วยเลขศูนย์ได้ |
| `name_th` | TEXT |  |  | ได้ | ชื่อวิชาภาษาไทย |
| `name_en` | TEXT |  |  | ได้ | ชื่อวิชาภาษาอังกฤษ |
| `credits` | SMALLINT |  |  | ได้ | จำนวนหน่วยกิตของวิชา |
| `hours_pattern` | TEXT |  |  | ได้ | รูปแบบชั่วโมง เช่น 3(3-0-6) |
| `lecture_hours` | SMALLINT |  |  | ได้ | ชั่วโมงบรรยาย |
| `practice_hours` | SMALLINT |  |  | ได้ | ชั่วโมงปฏิบัติ |
| `self_study_hours` | SMALLINT |  |  | ได้ | ชั่วโมงศึกษาด้วยตนเอง |
| `credit_group_id` | UUID |  | → mko.credit_groups(id) set null | ได้ | หมวดหน่วยกิตที่วิชานี้สังกัด |
| `description_th` | TEXT |  |  | ได้ | คำอธิบายรายวิชาภาษาไทย |
| `description_en` | TEXT |  |  | ได้ | คำอธิบายรายวิชาภาษาอังกฤษ |
| `status` | TEXT |  |  | ไม่ได้ | สถานะการตรวจ |
| `reason` | TEXT |  |  | ได้ | เหตุผลของสถานะที่ระบุไว้ |
| `listing_evidence_id` | UUID |  | → mko.evidence(id) | ได้ | หลักฐานจากรายการรายวิชา |
| `description_evidence_id` | UUID |  | → mko.evidence(id) | ได้ | หลักฐานจากคำอธิบายรายวิชา |
| `reviewed_by` | TEXT |  |  | ได้ | ผู้ยืนยันค่า ขึ้นต้นด้วย human: เมื่อคนตรวจ หรือ auto: เมื่อกฎอัตโนมัติยืนยัน |
| `reviewed_at` | TIMESTAMPTZ |  |  | ได้ | เวลาที่ตรวจยืนยัน |

**ห้ามซ้ำ:** (run_id, code)
**ข้อกำหนดระดับตาราง:** `CHECK (listing_evidence_id IS NOT NULL OR description_evidence_id IS NOT NULL)`

### ตาราง `public.chat_answer_cache`

| คอลัมน์ | ชนิดข้อมูล | PK | FK | Null ได้ | คำอธิบาย |
|---|---|:--:|---|:--:|---|
| `question_key` | TEXT | ✔ |  | ไม่ได้ | คำถามที่ตัดช่องว่างและวรรคตอนออกแล้ว ใช้เป็นคีย์หลัก |
| `corpus_version` | TEXT |  |  | ไม่ได้ | สภาพคลังเอกสารและรุ่นตรรกะตอนที่ตอบ ทำให้คำตอบเก่าหมดอายุเองเมื่อคลังเปลี่ยน |
| `status` | TEXT |  |  | ไม่ได้ | สถานะของคำตอบ เช่น answered, out_of_scope |
| `reply` | TEXT |  |  | ไม่ได้ | เนื้อความคำตอบที่เก็บไว้ |
| `citations` | JSONB |  |  | ไม่ได้ | รายการอ้างอิงที่ใช้ตอบ เก็บเป็น JSON |
| `hits` | INTEGER |  |  | ไม่ได้ | จำนวนครั้งที่คำตอบนี้ถูกใช้ซ้ำ |
| `created_at` | TIMESTAMPTZ |  |  | ไม่ได้ | เวลาที่สร้างแถวนี้ |
| `last_used_at` | TIMESTAMPTZ |  |  | ไม่ได้ | เวลาที่ใช้ซ้ำล่าสุด |

### ตาราง `public.chat_messages`

| คอลัมน์ | ชนิดข้อมูล | PK | FK | Null ได้ | คำอธิบาย |
|---|---|:--:|---|:--:|---|
| `id` | UUID | ✔ |  | ไม่ได้ | รหัสประจำแถว (คีย์หลัก) |
| `session_id` | UUID |  | → chat_sessions(id) cascade | ไม่ได้ | รอบการสนทนาที่เกี่ยวข้อง |
| `role` | TEXT |  |  | ไม่ได้ | ผู้พูด ต้องเป็น user, assistant หรือ system |
| `content` | TEXT |  |  | ไม่ได้ | เนื้อความของข้อความ |
| `created_at` | TIMESTAMPTZ |  |  | ไม่ได้ | เวลาที่สร้างแถวนี้ |

### ตาราง `public.chat_sessions`

| คอลัมน์ | ชนิดข้อมูล | PK | FK | Null ได้ | คำอธิบาย |
|---|---|:--:|---|:--:|---|
| `id` | UUID | ✔ |  | ไม่ได้ | รหัสประจำแถว (คีย์หลัก) |
| `user_id` | UUID |  | → users(id) cascade | ไม่ได้ | ผู้ใช้เจ้าของแถวนี้ |
| `started_at` | TIMESTAMPTZ |  |  | ไม่ได้ | เวลาที่เริ่มบทสนทนา |
| `ended_at` | TIMESTAMPTZ |  |  | ได้ | เวลาที่จบบทสนทนา |

### ตาราง `public.course_chunks`

| คอลัมน์ | ชนิดข้อมูล | PK | FK | Null ได้ | คำอธิบาย |
|---|---|:--:|---|:--:|---|
| `id` | UUID | ✔ |  | ไม่ได้ | รหัสประจำแถว (คีย์หลัก) |
| `course_id` | UUID |  | → courses(id) cascade | ไม่ได้ | หลักสูตรที่เกี่ยวข้อง |
| `document_id` | UUID |  | → course_documents(id) cascade | ไม่ได้ | เอกสารต้นทาง |
| `chunk_index` | INTEGER |  |  | ไม่ได้ | ลำดับของส่วนข้อความภายในเอกสาร ห้ามซ้ำภายในเอกสารเดียวกัน |
| `page_number` | INTEGER |  |  | ได้ | เลขหน้าที่ข้อความส่วนนี้มาจาก |
| `content` | TEXT |  |  | ไม่ได้ | เนื้อความของส่วนข้อความหลังทำความสะอาด |
| `token_count` | INTEGER |  |  | ได้ | จำนวนโทเคน ใช้ควบคุมความยาวบริบทที่ส่งให้โมเดล |
| `embedding` | VECTOR(1024) |  |  | ไม่ได้ | เวกเตอร์ความหมาย 1,024 มิติจากโมเดล bge-m3 มีดัชนี IVFFlat แบบระยะโคไซน์ |
| `metadata` | JSONB |  |  | ไม่ได้ | ข้อมูลประกอบของส่วนข้อความ |
| `created_at` | TIMESTAMPTZ |  |  | ไม่ได้ | เวลาที่สร้างแถวนี้ |

**ห้ามซ้ำ:** (document_id, chunk_index)

### ตาราง `public.course_documents`

| คอลัมน์ | ชนิดข้อมูล | PK | FK | Null ได้ | คำอธิบาย |
|---|---|:--:|---|:--:|---|
| `id` | UUID | ✔ |  | ไม่ได้ | รหัสประจำแถว (คีย์หลัก) |
| `course_id` | UUID |  | → courses(id) cascade | ไม่ได้ | หลักสูตรที่เกี่ยวข้อง |
| `original_filename` | TEXT |  |  | ไม่ได้ | ชื่อไฟล์เดิมของเอกสาร |
| `file_sha256` | TEXT |  |  | ไม่ได้ | ลายนิ้วมือของไฟล์ ใช้กันไฟล์ซ้ำและตรวจความถูกต้องก่อนส่งให้ผู้ใช้ |
| `storage_path` | TEXT |  |  | ไม่ได้ | ตำแหน่งจัดเก็บไฟล์ ผู้ใช้ไม่สามารถกำหนดค่านี้ได้โดยตรง |
| `page_count` | INTEGER |  |  | ได้ | จำนวนหน้าของเอกสาร |
| `extraction_status` | TEXT |  |  | ไม่ได้ | สถานะการสกัด pending, processing, done หรือ failed |
| `extraction_error` | TEXT |  |  | ได้ | ข้อความผิดพลาดเมื่อการสกัดล้มเหลว |
| `uploaded_by` | UUID |  | → users(id) | ได้ | ผู้ใช้ที่นำเอกสารเข้าระบบ |
| `uploaded_at` | TIMESTAMPTZ |  |  | ไม่ได้ | เวลาที่นำเอกสารเข้าระบบ |

**ห้ามซ้ำ:** (course_id, file_sha256)

### ตาราง `public.courses`

| คอลัมน์ | ชนิดข้อมูล | PK | FK | Null ได้ | คำอธิบาย |
|---|---|:--:|---|:--:|---|
| `id` | UUID | ✔ |  | ไม่ได้ | รหัสประจำแถว (คีย์หลัก) |
| `code` | TEXT |  |  | ได้ | รหัสหลักสูตร ถ้ามี ห้ามซ้ำ |
| `title` | TEXT |  |  | ไม่ได้ | ชื่อหลักสูตร ใช้เป็นคีย์เชื่อมเชิงตรรกะกับฐานข้อมูลฝั่งเว็บ |
| `provider` | TEXT |  |  | ได้ | หน่วยงานที่จัดหลักสูตร |
| `summary` | TEXT |  |  | ได้ | คำสรุปสั้นของหลักสูตร |
| `mode` | TEXT |  |  | ได้ | รูปแบบการเรียน เช่น online, onsite, hybrid |
| `duration_weeks` | NUMERIC |  |  | ได้ | ระยะเวลาเรียนเป็นสัปดาห์ |
| `price` | NUMERIC |  |  | ได้ | ค่าใช้จ่าย |
| `currency` | TEXT |  |  | ได้ | สกุลเงินของค่าใช้จ่าย |
| `tags` | JSONB |  |  | ไม่ได้ | ป้ายกำกับ เก็บเป็น JSON และมีดัชนีชนิด GIN |
| `is_active` | BOOLEAN |  |  | ไม่ได้ | ยังเปิดใช้งานอยู่หรือไม่ วิว v_live_* จะกรองเฉพาะที่เป็นจริง |
| `created_at` | TIMESTAMPTZ |  |  | ไม่ได้ | เวลาที่สร้างแถวนี้ |
| `updated_at` | TIMESTAMPTZ |  |  | ไม่ได้ | เวลาที่แก้ไขแถวนี้ล่าสุด |

### ตาราง `public.recommendations`

| คอลัมน์ | ชนิดข้อมูล | PK | FK | Null ได้ | คำอธิบาย |
|---|---|:--:|---|:--:|---|
| `id` | UUID | ✔ |  | ไม่ได้ | รหัสประจำแถว (คีย์หลัก) |
| `user_id` | UUID |  | → users(id) cascade | ไม่ได้ | ผู้ใช้เจ้าของแถวนี้ |
| `course_id` | UUID |  | → courses(id) cascade | ไม่ได้ | หลักสูตรที่เกี่ยวข้อง |
| `session_id` | UUID |  | → chat_sessions(id) set null | ได้ | รอบการสนทนาที่เกี่ยวข้อง |
| `score` | NUMERIC |  |  | ไม่ได้ | คะแนนความเหมาะสมระหว่าง 0 ถึง 1 |
| `rationale` | TEXT |  |  | ได้ | คำอธิบายเหตุผลที่แนะนำ เขียนโดยโมเดลภาษา |
| `retrieved_chunk_ids` | UUID[] |  |  | ไม่ได้ | รายการรหัสส่วนข้อความที่ใช้ประกอบคำแนะนำ เก็บเป็นอาร์เรย์เพื่อให้ย้อนตรวจได้ |
| `model_used` | TEXT |  |  | ได้ | ชื่อโมเดลที่ใช้ตอนสร้างคำแนะนำ |
| `created_at` | TIMESTAMPTZ |  |  | ไม่ได้ | เวลาที่สร้างแถวนี้ |

### ตาราง `public.user_profiles`

| คอลัมน์ | ชนิดข้อมูล | PK | FK | Null ได้ | คำอธิบาย |
|---|---|:--:|---|:--:|---|
| `user_id` | UUID | ✔ | → users(id) cascade | ไม่ได้ | ผู้ใช้เจ้าของแถวนี้ |
| `education_level` | TEXT |  |  | ได้ | ระดับการศึกษา เช่น high_school, bachelor, master |
| `field_of_study` | TEXT |  |  | ได้ | สาขาที่เคยศึกษา |
| `current_role` | TEXT |  |  | ได้ | บทบาทหรืออาชีพปัจจุบัน ต้องใส่เครื่องหมายคำพูดในคำสั่ง SQL เพราะเป็นคำสงวน |
| `career_goal` | TEXT |  |  | ได้ | เป้าหมายอาชีพที่ผู้ใช้ระบุ |
| `skills` | JSONB |  |  | ไม่ได้ | รายการทักษะ เก็บเป็น JSON |
| `interests` | JSONB |  |  | ไม่ได้ | รายการความสนใจ เก็บเป็น JSON |
| `language_preference` | TEXT |  |  | ได้ | ภาษาที่ผู้ใช้ต้องการให้ระบบตอบ |
| `metadata` | JSONB |  |  | ไม่ได้ | ช่องขยายสำหรับข้อมูลเพิ่มเติมในอนาคต |
| `updated_at` | TIMESTAMPTZ |  |  | ไม่ได้ | เวลาที่แก้ไขแถวนี้ล่าสุด |

### ตาราง `public.user_requirements`

| คอลัมน์ | ชนิดข้อมูล | PK | FK | Null ได้ | คำอธิบาย |
|---|---|:--:|---|:--:|---|
| `id` | UUID | ✔ |  | ไม่ได้ | รหัสประจำแถว (คีย์หลัก) |
| `user_id` | UUID |  | → users(id) cascade | ไม่ได้ | ผู้ใช้เจ้าของแถวนี้ |
| `req_type` | TEXT |  |  | ไม่ได้ | ประเภทเงื่อนไข เช่น budget_max, duration_max_weeks, mode, location |
| `req_value` | TEXT |  |  | ไม่ได้ | ค่าของเงื่อนไข เก็บเป็นข้อความแล้วแปลงชนิดตอนใช้งาน |
| `priority` | SMALLINT |  |  | ไม่ได้ | ระดับความสำคัญ 1 ถึง 5 โดย 5 คือจำเป็นที่สุด |
| `created_at` | TIMESTAMPTZ |  |  | ไม่ได้ | เวลาที่สร้างแถวนี้ |

### ตาราง `public.users`

| คอลัมน์ | ชนิดข้อมูล | PK | FK | Null ได้ | คำอธิบาย |
|---|---|:--:|---|:--:|---|
| `id` | UUID | ✔ |  | ไม่ได้ | รหัสประจำแถว (คีย์หลัก) |
| `email` | CITEXT |  |  | ไม่ได้ | อีเมลผู้ใช้ ใช้ชนิด CITEXT จึงไม่แยกตัวพิมพ์เล็กใหญ่ และห้ามซ้ำ |
| `password_hash` | TEXT |  |  | ไม่ได้ | รหัสผ่านที่ผ่านการแฮชด้วย bcrypt ห้ามเก็บรหัสผ่านจริง |
| `full_name` | TEXT |  |  | ได้ | ชื่อ-นามสกุลของผู้ใช้ |
| `is_active` | BOOLEAN |  |  | ไม่ได้ | สถานะใช้งานของบัญชี |
| `is_admin` | BOOLEAN |  |  | ไม่ได้ | เป็นผู้ดูแลระบบหรือไม่ |
| `created_at` | TIMESTAMPTZ |  |  | ไม่ได้ | เวลาที่สร้างแถวนี้ |
| `updated_at` | TIMESTAMPTZ |  |  | ไม่ได้ | เวลาที่แก้ไขแถวนี้ล่าสุด |

## ส่วนที่ 2 — ฐานข้อมูลระบบเว็บ (Supabase)

### ตาราง `public.ai_settings`

| คอลัมน์ | ชนิดข้อมูล | PK | FK | Null ได้ | คำอธิบาย |
|---|---|:--:|---|:--:|---|
| `id` | INTEGER | ✔ |  | ไม่ได้ | คีย์หลัก บังคับให้มีค่าเท่ากับ 1 เสมอ จึงมีได้เพียงแถวเดียว |
| `model` | VARCHAR(255) |  |  | ไม่ได้ | ชื่อโมเดลที่หน้าแอดมินเลือกไว้ |
| `updated_at` | TIMESTAMP |  |  | ได้ | เวลาที่แก้ไขแถวนี้ล่าสุด |
| `updated_by` | UUID |  | → auth.users(id) | ได้ | ผู้แก้ไขแถวนี้ล่าสุด |

### ตาราง `public.courses`

| คอลัมน์ | ชนิดข้อมูล | PK | FK | Null ได้ | คำอธิบาย |
|---|---|:--:|---|:--:|---|
| `id` | UUID | ✔ |  | ไม่ได้ | รหัสประจำแถว (คีย์หลัก) |
| `title` | VARCHAR(255) |  |  | ไม่ได้ | ชื่อสาขาภาษาไทย ใช้เชื่อมกับฐานข้อมูลฝั่ง AI ด้วยชื่อ |
| `title_en` | VARCHAR(255) |  |  | ไม่ได้ | ชื่อสาขาภาษาอังกฤษ |
| `description` | TEXT |  |  | ไม่ได้ | คำอธิบายสาขาที่แสดงบนหน้าเว็บ |
| `logo` | TEXT |  |  | ได้ | ที่อยู่ภาพประจำสาขา |
| `careers` | TEXT[] |  |  | ได้ | รายการอาชีพหลังจบ เก็บเป็นอาร์เรย์ข้อความ |
| `detail` | JSONB |  |  | ได้ | ข้อมูลเสริมของหน้ารายละเอียด เก็บเป็น JSON โครงสร้างยืดหยุ่น เช่น level, duration, tuition, about, faculty, documents |
| `created_at` | TIMESTAMP |  |  | ได้ | เวลาที่สร้างแถวนี้ |
| `updated_at` | TIMESTAMP |  |  | ได้ | เวลาที่แก้ไขแถวนี้ล่าสุด |
| `created_by` | UUID |  | → auth.users(id) | ได้ | ผู้สร้างแถวนี้ |
| `updated_by` | UUID |  | → public.user_profiles(user_id) | ได้ | ผู้แก้ไขแถวนี้ล่าสุด |

### ตาราง `public.external_news`

| คอลัมน์ | ชนิดข้อมูล | PK | FK | Null ได้ | คำอธิบาย |
|---|---|:--:|---|:--:|---|
| `id` | UUID | ✔ |  | ไม่ได้ | รหัสประจำแถว (คีย์หลัก) |
| `title` | VARCHAR(255) |  |  | ไม่ได้ | หัวข้อข่าวจากแหล่งภายนอก |
| `description` | TEXT |  |  | ได้ | เนื้อหาย่อของข่าว |
| `image_url` | TEXT |  |  | ได้ | ที่อยู่ภาพประกอบ |
| `detail_url` | TEXT |  |  | ไม่ได้ | ที่อยู่ข่าวต้นทาง ห้ามซ้ำ ใช้เป็นตัวกันข่าวซ้ำ |
| `published_at` | TIMESTAMP |  |  | ได้ | เวลาที่ข่าวถูกเผยแพร่ที่ต้นทาง |
| `published_text` | VARCHAR(255) |  |  | ได้ | วันที่ของข่าวในรูปข้อความตามที่ต้นทางแสดง |
| `source` | VARCHAR(100) |  |  | ไม่ได้ | ชื่อแหล่งข่าว |
| `slug` | VARCHAR(255) |  |  | ได้ | ตัวระบุข่าวสำหรับใช้ในที่อยู่เว็บ |
| `facebook_url` | TEXT |  |  | ได้ | ที่อยู่โพสต์ต้นทางบนเฟซบุ๊ก |
| `synced_at` | TIMESTAMP |  |  | ได้ | เวลาที่ซิงค์ข่าวนี้เข้ามาล่าสุด |
| `created_at` | TIMESTAMP |  |  | ได้ | เวลาที่สร้างแถวนี้ |

### ตาราง `public.knowledge_articles`

| คอลัมน์ | ชนิดข้อมูล | PK | FK | Null ได้ | คำอธิบาย |
|---|---|:--:|---|:--:|---|
| `id` | UUID | ✔ |  | ไม่ได้ | รหัสประจำแถว (คีย์หลัก) |
| `title` | VARCHAR(255) |  |  | ไม่ได้ | ชื่อบทความในคลังความรู้ |
| `content` | TEXT |  |  | ไม่ได้ | เนื้อหาบทความ |
| `file_path` | TEXT |  |  | ได้ | ตำแหน่งไฟล์ต้นฉบับในที่เก็บไฟล์ |
| `file_name` | TEXT |  |  | ได้ | ชื่อไฟล์ต้นฉบับ |
| `file_size` | BIGINT |  |  | ได้ | ขนาดไฟล์เป็นไบต์ |
| `created_at` | TIMESTAMP |  |  | ได้ | เวลาที่สร้างแถวนี้ |
| `updated_at` | TIMESTAMP |  |  | ได้ | เวลาที่แก้ไขแถวนี้ล่าสุด |
| `created_by` | UUID |  | → auth.users(id) | ได้ | ผู้สร้างแถวนี้ |
| `updated_by` | UUID |  | → auth.users(id) | ได้ | ผู้แก้ไขแถวนี้ล่าสุด |

### ตาราง `public.news`

| คอลัมน์ | ชนิดข้อมูล | PK | FK | Null ได้ | คำอธิบาย |
|---|---|:--:|---|:--:|---|
| `id` | UUID | ✔ |  | ไม่ได้ | รหัสประจำแถว (คีย์หลัก) |
| `title` | VARCHAR(255) |  |  | ไม่ได้ | หัวข้อข่าว |
| `description` | TEXT |  |  | ไม่ได้ | เนื้อหาข่าว |
| `category` | VARCHAR(100) |  |  | ไม่ได้ | หมวดหมู่ข่าว |
| `date` | DATE |  |  | ไม่ได้ | วันที่ของข่าว |
| `image` | TEXT |  |  | ได้ | ที่อยู่ภาพประกอบข่าว |
| `status` | VARCHAR(50) |  |  | ไม่ได้ | สถานะการเผยแพร่ published หรือ draft |
| `created_at` | TIMESTAMP |  |  | ได้ | เวลาที่สร้างแถวนี้ |
| `updated_at` | TIMESTAMP |  |  | ได้ | เวลาที่แก้ไขแถวนี้ล่าสุด |
| `created_by` | UUID |  | → auth.users(id) | ได้ | ผู้สร้างแถวนี้ |
| `updated_by` | UUID |  | → public.user_profiles(user_id) | ได้ | ผู้แก้ไขแถวนี้ล่าสุด |

### ตาราง `public.rag_documents`

| คอลัมน์ | ชนิดข้อมูล | PK | FK | Null ได้ | คำอธิบาย |
|---|---|:--:|---|:--:|---|
| `id` | UUID | ✔ |  | ไม่ได้ | รหัสประจำแถว (คีย์หลัก) |
| `source_type` | VARCHAR(50) |  |  | ไม่ได้ | ประเภทของแหล่งข้อมูล major, news, article หรือ knowledge |
| `source_id` | UUID |  |  | ได้ | รหัสของแถวต้นทางตามประเภทที่ระบุ ไม่มีคีย์นอกบังคับ |
| `title` | VARCHAR(255) |  |  | ไม่ได้ | ชื่อเรื่องของส่วนข้อความ |
| `content` | TEXT |  |  | ไม่ได้ | เนื้อความของส่วนข้อความ |
| `chunk_index` | INTEGER |  |  | ไม่ได้ | ลำดับของส่วนข้อความภายในเอกสารเดียวกัน |
| `embedding` | vector |  |  | ได้ | เวกเตอร์ความหมายของส่วนข้อความนี้ |
| `created_at` | TIMESTAMP |  |  | ได้ | เวลาที่สร้างแถวนี้ |
| `updated_at` | TIMESTAMP |  |  | ได้ | เวลาที่แก้ไขแถวนี้ล่าสุด |

**ห้ามซ้ำ:** (source_type, source_id, chunk_index)

### ตาราง `public.user_profiles`

| คอลัมน์ | ชนิดข้อมูล | PK | FK | Null ได้ | คำอธิบาย |
|---|---|:--:|---|:--:|---|
| `id` | UUID | ✔ |  | ไม่ได้ | รหัสประจำแถว (คีย์หลัก) |
| `user_id` | UUID |  |  | ได้ | รหัสผู้ใช้จากระบบยืนยันตัวตนของ Supabase ห้ามซ้ำ |
| `role` | VARCHAR(50) |  |  | ได้ | บทบาท เช่น admin, editor, user |
| `full_name` | VARCHAR(255) |  |  | ได้ | ชื่อ-นามสกุล |
| `email` | TEXT |  |  | ได้ | อีเมลของผู้ดูแลระบบ |
| `status` | VARCHAR(50) |  |  | ไม่ได้ | สถานะการอนุมัติบัญชี ค่าเริ่มต้นคือ approved |
| `created_at` | TIMESTAMP |  |  | ได้ | เวลาที่สร้างแถวนี้ |
| `updated_at` | TIMESTAMP |  |  | ได้ | เวลาที่แก้ไขแถวนี้ล่าสุด |

