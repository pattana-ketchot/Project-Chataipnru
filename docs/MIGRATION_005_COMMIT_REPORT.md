# Migration 005 — รายงานการตรวจ ทดสอบ และ commit

| | |
|---|---|
| วันที่ | 2026-10-01 |
| ขอบเขตที่ได้รับอนุมัติ | ตรวจ migration 005 + tests รอบสุดท้าย · รัน tests ในสภาพแวดล้อมแยก · commit migration + tests + เอกสารที่เกี่ยวข้อง |
| **ผลทดสอบ** | **531 ข้อ ผ่าน · 0 ไม่ผ่าน** |
| **Commit** | **`67c6f99a8c11c90d89b625b447a5350b9663860d`** |
| **Production write / deploy / restart** | **ไม่มีทั้งสามอย่าง** |
| สถานะถัดไป | **ยังไม่ apply กับ production · ยังไม่ย้ายข้อมูล · ยังไม่ push** |


> ## ⚠ มีข้อมูลในรายงานนี้ที่ภายหลังพบว่าผิด
>
> รายงานนี้บันทึกสิ่งที่เกิดขึ้น ณ เวลานั้นไว้ตามเดิมโดยเจตนา **ไม่แก้เนื้อใน**
> แต่ข้อเท็จจริงสี่เรื่องต่อไปนี้ผิด และได้แก้ในเอกสารอ้างอิงแล้ว
>
> | ที่รายงานไว้ | ความจริง |
> |---|---|
> | Supabase มี FK 0 · CHECK 0 · UNIQUE 1 | **FK 7 · CHECK 2 · UNIQUE 4** |
> | ต้นทางเป็น `TIMESTAMP` ไม่มีเขตเวลา · เสี่ยงคลาด 7 ชั่วโมง | เป็น `TIMESTAMP WITH TIME ZONE` อยู่แล้ว · **ไม่มีความเสี่ยงนี้** |
> | `rag_documents` เป็น `vector(768)` | คอลัมน์เป็น `vector` **ไม่ล็อกมิติ** · 768 เป็นค่าของแอป · มิติจริง **UNKNOWN** |
> | `external_news` ใช้ `slug` เป็นกุญแจ unique | ต้นทางใช้ **`detail_url` NOT NULL UNIQUE** · `slug` เป็น NULL ได้ |
>
> ดู [`SUPABASE_PRE_MIGRATION_AUDIT.md`](SUPABASE_PRE_MIGRATION_AUDIT.md) ข้อ 12
> และ [`MIGRATION_005_CORRECTIVE_REVIEW.md`](MIGRATION_005_CORRECTIVE_REVIEW.md)


---

## 1. ผลการตรวจและทดสอบ

### 1.1 ตรวจ migration รอบสุดท้าย

| ข้อตรวจ | ผล |
|---|---|
| คำสั่งที่แตะของเดิม (`DROP` / `ALTER` / `DELETE` / `TRUNCATE` / `UPDATE`) | **0 บรรทัด** |
| `public.*` ถูกอ้างในบริบทไหน | 9 จุด · **ทุกจุดเป็น `REFERENCES` ของ foreign key** ไม่ใช่การเขียน |
| DDL ที่มีในไฟล์ | `CREATE SCHEMA` 1 · `CREATE TABLE` 5 · `CREATE INDEX` 4 · `COMMENT` 4 · `GRANT` 8 · `INSERT` 1 (ลงทะเบียน migration) |
| CRLF ในไฟล์ | **0** ทุกไฟล์ |
| `git diff --cached --check` | ว่าง |
| idempotent | ลง 005 ซ้ำสองครั้งติดกัน **ไม่ error** |
| สร้างใหม่ตั้งแต่ศูนย์ | 001 → 002 → 003 → 004 → 005 **ผ่านครบทุกตัว** |

### 1.2 ผลการรัน tests — 531 / 531 ผ่าน

| ชุด | ผ่าน | ไม่ผ่าน | หมายเหตุ |
|---|---:|---:|---|
| `eval/web_schema_check.py` | **47** | **0** | ชุดใหม่ของ migration นี้ |
| `eval/crawl_download_check.py` | 165 | 0 | regression |
| `eval/crawl_ingest_worker_check.py` | 187 | 0 | regression |
| `eval/crawl_approval_check.py` | 84 | 0 | regression |
| `eval/crawl_state_check.py` | 32 | 0 | regression |
| `eval/document_endpoint_check.py` | 16 | 0 | regression |
| **รวม** | **531** | **0** | |

ชุด regression ทั้งหมดรันบนฐานข้อมูลที่ **ลง migration 005 แล้ว** เพื่อพิสูจน์ว่า
schema ใหม่ไม่ทำให้ของเดิมพัง

### 1.3 สภาพแวดล้อมที่ใช้ทดสอบ

```
PostgreSQL 16.15 ในคอนเทนเนอร์แยก (compose project sci-advisor-e2e)
ฐานข้อมูล  web_test · crawl_test        ← ไม่ใช่ production
ด่านกัน     URL ห้ามมีคำว่า course_advisor · ถาม current_database() ซ้ำอีกชั้น
ทุกแถวที่ใช้ สร้างขึ้นเองในเทสต์แล้วย้อนทิ้งเมื่อจบ ไม่ได้ย้ายข้อมูลจริงจากที่ใด
```

**ทำความสะอาดแล้ว**: containers 0 · volumes 0 · images 0

### 1.4 สิ่งที่ชุดตรวจใหม่พิสูจน์ (47 ข้อ)

| หมวด | ข้อ | พิสูจน์อะไร |
|---|---:|---|
| โครงสร้าง | 6 | ตารางครบ 5 ไม่เกินไม่ขาด · FK ครบ 8 เส้นและชี้ถูกที่ · ทุก FK เป็น `ON DELETE SET NULL` · ไม่มีคอลัมน์ `timestamp` ไร้เขตเวลาหลงเหลือ |
| **constraint ทำงานจริง** | 13 | ยิงข้อมูลผิดรูปเข้าไปแล้ว **ต้องถูกปฏิเสธจริง** — `status` สะกดผิด · `title` NULL · `slug` ซ้ำ · `ai_settings` แถวที่สอง · `file_size` ติดลบ · FK ชี้ของที่ไม่มีอยู่ |
| การผูกหลักสูตร | 5 | หลายแถว `NULL` อยู่ร่วมกันได้ · ผูกหลักสูตรเดียวกันสองแถวถูกปฏิเสธ · **ลบหลักสูตรแล้วแถวแสดงผลยังอยู่และ `course_id` กลายเป็น NULL** |
| **ไม่แตะ `public`/`mko`** | 6 | `public` ยัง 10 ตาราง · `mko` ยัง 20 ตาราง + 8 view · `course_chunks.embedding` ยัง **1024 มิติ** · index `ivfflat vector_cosine_ops` เหมือนเดิม · ไม่มี FK จาก `public` ชี้มาหา `web` |
| สิทธิ์ | 17 | `advisor_api` อ่านได้หมด เขียนได้เฉพาะสี่ตาราง · เขียน `external_news` ไม่ได้ · **ไม่มีใคร DELETE ได้สักตาราง** · `advisor_ingest` เขียนได้ตารางเดียว |

หมวด "constraint ทำงานจริง" สำคัญกว่าหมวดโครงสร้าง เพราะเหตุผลหลักของ schema นี้
คือ **ของเดิมมี FK 0 · CHECK 0 · UNIQUE 1 ทั้งฐาน** การประกาศไว้เฉย ๆ จึงไม่พอ
ต้องพิสูจน์ว่ามันปฏิเสธข้อมูลผิดรูปได้จริง

---

## 2. Commit

```
hash     67c6f99a8c11c90d89b625b447a5350b9663860d
branch   mko-phase2
parent   7af085b2e8138c5f7d10229af4a68b8e435c0a63
subject  feat(db): add a web schema for the website data that lives elsewhere
```

---

## 3. ไฟล์ที่ commit — 5 ไฟล์ · +1,386 บรรทัด · 0 ลบ

| ไฟล์ | บรรทัด | หน้าที่ |
|---|---:|---|
| `db/migrations/005_web_schema.sql` | 231 | สร้าง schema `web` — สร้างที่ว่างอย่างเดียว |
| `eval/web_schema_check.py` | 320 | ชุดตรวจ 47 ข้อ |
| `docs/MIGRATION_005_WEB_SCHEMA_REVIEW.md` | 339 | เอกสารขอตรวจก่อนอนุมัติ |
| `docs/TARGET_ARCHITECTURE.md` | 263 | ภาพปัจจุบันและภาพปลายทาง |
| `docs/EMBEDDING_PATH_AUDIT.md` | 233 | ข้อกำหนดเรื่อง embedding — ใช้อ้างอิงใน phase ถัดไป |

stage แบบระบุ path ทุกไฟล์ · **ไม่ใช้ `git add .`**

### 3.1 ยังไม่ push

```
HEAD              67c6f99…        ← commit แล้วในเครื่อง
origin/mko-phase2 7af085b…        ← ยังไม่ push
origin/main       b78b3f8…        ← ไม่แตะ
```

รายการที่อนุญาตรอบนี้มีแค่ **commit** จึงหยุดไว้ตรงนี้

### 3.2 ⚠ หนึ่งไฟล์ถือไว้ไม่ commit — ต้องให้เจ้าของตัดสิน

`docs/DATABASE_CONSOLIDATION_AUDIT.md` **ไม่ได้ commit**

| เหตุผล | รายละเอียด |
|---|---|
| มีอีเมลจริงของเจ้าของโปรเจกต์ | ปรากฏ 2 จุด (บรรทัด 447 และ 628) |
| repo นี้เป็น **public** | ยืนยันแล้ว — GitHub API ตอบโดยไม่ต้องยืนยันตัวตน |
| อีเมลนี้ยังไม่เคยอยู่ในไฟล์ที่ commit แล้ว | **0 ไฟล์** — การ commit จะเป็นการเผยแพร่สู่สาธารณะเป็นครั้งแรก |
| ถอนยาก | git history เก็บไว้ถาวร ลบทีหลังต้องเขียนประวัติใหม่ |

ไม่แก้ไฟล์ให้เองเพราะเป็นเอกสารที่เจ้าของอาจต้องการตามเดิม **สองทางเลือก**

1. แทนที่อีเมลด้วย placeholder แล้ว commit (ความหมายของประโยคไม่เปลี่ยน —
   ประเด็นคือ "บัญชีนี้อยู่ในระบบหนึ่งแต่ไม่อยู่ในอีกระบบ")
2. ปล่อยไว้ untracked ต่อไป

**ผลข้างเคียงระหว่างนี้**: `MIGRATION_005_WEB_SCHEMA_REVIEW.md` และ
`TARGET_ARCHITECTURE.md` มีลิงก์ไปหาไฟล์นั้น ซึ่งจะเปิดไม่ได้บน GitHub
จนกว่าจะ commit — ในเครื่องยังเปิดได้ปกติ

---

## 4. Production Write / Deployment / Restart

**ไม่มีทั้งสามอย่าง** — ยืนยันแบบอ่านอย่างเดียวหลังทำงานเสร็จ

```
schema ที่มีบน production   : mko, public                      ← ยังไม่มี web
migration ที่ลงแล้ว          : 001, 002, 003, 004               ← ยังไม่มี 005
คอนเทนเนอร์                  : 7 ตัวทำงานอยู่ ไม่มีการ restart
```

| รายการ | สถานะ |
|---|---|
| apply migration 005 กับ production | **ไม่ได้ทำ** |
| ย้าย/นำเข้าข้อมูลจริง | **ไม่ได้ทำ** |
| เขียนหรือแก้ฐานข้อมูล production | **ไม่ได้ทำ** |
| deploy / restart service | **ไม่ได้ทำ** |
| แก้ Ollama configuration | **ไม่ได้ทำ** |
| แก้ RAG / embedding implementation | **ไม่ได้ทำ** |
| re-embed ข้อมูล | **ไม่ได้ทำ** |
| เปลี่ยน auth หรือ storage | **ไม่ได้ทำ** |
| push / merge เข้า `main` | **ไม่ได้ทำ** |
| เริ่ม phase ถัดไปเอง | **ไม่ได้ทำ** |

### 4.1 ข้อกำหนดเรื่อง embedding — คงเดิมทุกข้อ

ไม่มีอะไรใน commit นี้แตะส่วนนี้ ยืนยันด้วยชุดตรวจหมวด "ไม่แตะ public/mko"

```
Model      bge-m3            ไม่เปลี่ยน
Dimension  1024              ไม่เปลี่ยน · ชุดตรวจยืนยันว่า course_chunks ยังเป็น 1024
Distance   cosine <=>        ไม่เปลี่ยน
Index      IVFFlat vector_cosine_ops   ไม่เปลี่ยน · ชุดตรวจอ่าน indexdef มายืนยัน
check_embedding_contract()   ไม่แตะ ไม่ปิด
```

migration 005 **ไม่มีคอลัมน์ vector แม้คอลัมน์เดียว** และตารางเก็บ chunk/embedding
ของหน้าเว็บถูกตั้งใจไม่สร้างในรอบนี้ — ดูเหตุผลในข้อ 5

---

## 5. Phase ถัดไป — ต้องการอะไรก่อนเริ่ม Data Migration

| # | ต้องการ | ทำไมขาดไม่ได้ |
|---|---|---|
| 1 | **สิทธิ์เข้าโปรเจกต์ Supabase ในฐานะ member ด้วยบัญชีของเจ้าของเอง** | ต้อง export ข้อมูลออกมา · ขอเป็น member ไม่ใช่ยืม login ของผู้อื่น เพราะถอนสิทธิ์ทีหลังได้และตรวจย้อนได้ |
| 2 | **ค่าที่ `news.status` ใช้จริงทั้งหมด** | CHECK ที่ใส่ไว้คือ `published` / `draft` / `archived` แต่ยืนยันได้แค่ `published` (ค่า default) อีกสองค่าเป็นการเดาที่สมเหตุสมผล — ถ้าพบค่าอื่นต้องแก้รายการ **ห้ามถอด CHECK ออก** |
| 3 | **เขตเวลาของคอลัมน์ `TIMESTAMP` เดิม** | ของเดิมไม่มีเขตเวลา ปลายทางเป็น `timestamptz` ถ้าเดาผิดเวลาคลาด 7 ชั่วโมงทั้งก้อน |
| 4 | **วิธีแมปผู้ใช้สองชุด** | `created_by` / `updated_by` อ้างผู้ใช้คนละชุดกับ `public.users` แถวที่แมปไม่ได้จะเป็น NULL ตามที่ออกแบบ แต่ต้องรู้ก่อนว่าจะแมปอย่างไร |
| 5 | **ที่อยู่ใหม่ของไฟล์แนบ** | `knowledge_articles` เก็บแค่ `file_path` / `file_name` / `file_size` ไฟล์จริงอยู่ในที่เก็บไฟล์เดิม — การย้ายฐานข้อมูลไม่ได้ย้ายไฟล์ตามมา |
| 6 | **จำนวนแถวจริงทุกตาราง** | ประเมินเวลาและความเสี่ยงไม่ได้ · backup ที่มีอยู่ขนาด 1 KB บอกอะไรไม่ได้ |

### 5.1 ข้อกำหนดที่แผน RAG migration ต้องยึด (ยังไม่ถึงรอบนี้)

อ้างอิง [`EMBEDDING_PATH_AUDIT.md`](EMBEDDING_PATH_AUDIT.md)

- `vector(768)` ของเดิม **ห้าม copy/convert เข้า `vector(1024)` โดยตรง**
- ต้องนำ **source content** มา re-embed ด้วย `bge-m3` ใหม่
- ต้องออกแบบให้ **resume / retry ได้** เพราะไม่มี automatic failover
  (`_post_with_retry` ลองซ้ำที่โฮสต์เดิม 3 ครั้งแล้วโยน error · 4xx/5xx ไม่ลองซ้ำเลย)
- Local Ollama บนเครื่องผู้พัฒนาเป็นสภาพแวดล้อมคนละชุดที่เลือกด้วย env var
  **ไม่ใช่ automatic failover ของ production**
- ห้ามเพิ่ม automatic embedding failover ใน phase นี้

---

## 6. Unknown ที่ยังต้องตรวจจากข้อมูลจริง

| # | ยังยืนยันไม่ได้ | ต้องดูที่ | ผลถ้าไม่รู้ |
|---|---|---|---|
| U1 | **RLS policy ทั้งหมดของ Supabase** | dashboard | โค้ดใช้ anon key เท่านั้น แปลว่า RLS รับน้ำหนักจริงอยู่ — ไม่รู้ว่ามีอะไรบ้าง = ประเมินงาน authorization ที่ต้องเขียนใหม่ไม่ได้ |
| U2 | **Supabase Storage เก็บอะไร bucket ชื่ออะไร ขนาดเท่าไหร่** | dashboard | ดึงชื่อ bucket จาก bundle ที่ minify แล้วไม่ได้ · กระทบข้อ 5 รายการที่ 5 |
| U3 | **จำนวนแถวจริงทุกตาราง** | query ฝั่ง Supabase | ประเมินเวลาและความเสี่ยงไม่ได้ |
| U4 | **แถวใน Supabase `courses` ตรงกับ `public.courses` (24 แถว) กี่แถว** | เทียบข้อมูลจริงสองฝั่ง | เป็นตัวตัดสินว่า `site_courses.course_id` มีประโยชน์จริงแค่ไหน |
| U5 | **`news` กับ `external_news` ต่างกันอย่างไร** | schema + ข้อมูลตัวอย่าง | ยังไม่รู้ว่าซ้ำซ้อนหรือคนละเรื่อง — กระทบว่าจะย้ายทั้งคู่หรือรวมเป็นหนึ่ง |
| U6 | **Edge Function มีกี่ตัว** | dashboard | ยืนยันแล้วหนึ่งตัว (`sync-sci-news`) พบร่องรอย `functions/v1` อีก 4 ครั้งใน bundle |
| U7 | **source ของ SPA ขอใช้ได้ไหม** | เจ้าของโค้ด | `.gitignore` ระบุว่าอยู่คนละ repo คนละเจ้าของ — **เป็นตัวขัดขวางที่ใหญ่ที่สุด** เพราะทุกทางเลือกต้องแก้ SPA |

**ไม่มีค่าใดในรายงานฉบับนี้ที่มาจากการเดา** — ทุกตัวเลขมาจาก source code, การ query
ฐานข้อมูลจริงแบบอ่านอย่างเดียว หรือการรัน test จริง

---

## สรุปการเปลี่ยนแปลงในรอบนี้

```
MIGRATION APPLIED TO PRODUCTION:  NONE
PRODUCTION WRITES:                NONE
DATA MIGRATED FROM SUPABASE:      NONE
DEPLOYMENTS:                      NONE
SERVICE RESTARTS:                 NONE
OLLAMA / RAG / EMBEDDING CHANGES: NONE
AUTH / STORAGE CHANGES:           NONE
PUSH / MERGE TO main:             NONE
PUSH TO mko-phase2:               NONE  (รายการที่อนุญาตมีแค่ commit)

COMMITS:  1 — 67c6f99a8c11c90d89b625b447a5350b9663860d  (5 ไฟล์ · +1,386 บรรทัด · 0 ลบ)
```

---

## STOP

**ห้ามเริ่ม Data Migration จนกว่าจะได้รับคำสั่งอนุมัติรอบใหม่**

สองเรื่องที่รอการตัดสินใจ

1. **`docs/DATABASE_CONSOLIDATION_AUDIT.md`** — จะให้แทนที่อีเมลด้วย placeholder
   แล้ว commit หรือปล่อยไว้ untracked (ข้อ 3.2)
2. **จะ push `mko-phase2` ขึ้น origin หรือยัง** — รอบนี้อนุญาตแค่ commit จึงหยุดไว้
