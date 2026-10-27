# Phase 3D — Isolated E2E Test Harness Design

**DESIGN ONLY · ไม่ได้รันอะไรเลยในรอบนี้ · Production mutation = 0**

| | |
|---|---|
| วันที่ออกแบบ | 2026-09-29 · baseline อ่านเมื่อ **12:49:15Z** (ไทย 19:49) |
| Revision ที่อ่าน source | `2fdc6f241fc1742047b572ee2ef354cd811f9401` (= อิมเมจที่ให้บริการอยู่ · ยืนยันด้วย OCI label) |
| ขอบเขต | ออกแบบวิธีพิสูจน์ pipeline ครบวงจรใน **สภาพแวดล้อมแยกอิสระ** ไม่ปนกับ production |
| คำตัดสิน | **GO สำหรับการรัน isolated E2E test ในรอบถัดไป** เมื่อได้รับอนุมัติ · **ไม่กระทบสถานะ production one-job ingestion ซึ่งยัง NO-GO** |

---

## คำนิยามที่ต้องแยกให้ขาด

| คำ | ความหมาย |
|---|---|
| **PRODUCTION CANDIDATE** | PDF ที่ **ใหม่หรือเปลี่ยนจริง** จาก `sci.pnru.ac.th` · ตรวจพบโดย crawler ที่รันกับเว็บจริง · เป็นสิ่งเดียวที่อนุญาตให้ ingest เข้าคลังจริง |
| **TEST CANDIDATE** | PDF จำลองที่มีอยู่**เฉพาะในสภาพแวดล้อมทดสอบแยก**เท่านั้น · ไม่เคยแตะฐานข้อมูล ไฟล์ หรือเครือข่ายของ production |

**ห้ามนำสองอย่างมาปนกันโดยเด็ดขาด** เอกสารนี้พูดถึง TEST CANDIDATE ล้วน

---

## 1. สถานะ production ที่ยืนยันแล้ว (baseline · อ่านอย่างเดียว)

วัดเมื่อ **2026-09-29T12:49:15Z** ใน `BEGIN TRANSACTION READ ONLY` พร้อม `statement_timeout`

| รายการ | ค่า |
|---|---:|
| `users` / active / admins | 198 / 198 / **1** |
| `public.courses` | **24** |
| `public.course_documents` | **31** |
| `public.course_chunks` | **9039** |
| `mko.crawl_sources` | **12** · unchanged **12** · `staging_path` ไม่ null **0** |
| `mko.crawl_decisions` | **0** |
| `mko.v_crawl_queue` | **6** |
| `chat_messages` / `chat_answer_cache` | 6640 / 160 |
| embedding dimension | **1024** |
| index ของ vector | `ivfflat (embedding vector_cosine_ops) WITH (lists='100')` |
| `courses` ที่รหัสขึ้นต้น `TEST` | **0** |
| `staging/crawl` | **0 ไฟล์** |
| `documents/*.pdf` | **30 ไฟล์** |

สถานะที่ยืนยันจากรอบก่อน: admin promotion PASS · login PASS ·
authenticated crawl-review GET PASS (`pending` 200 / 6 รายการ · `detail` 200 ·
`pdf` 404 fail-closed) · **ไม่มี legitimate candidate** · production one-job ingestion **NO-GO**

> **6 แถวในคิวไม่ใช่ candidate สำหรับ ingestion** — คำตอบของ API เองบอกว่า
> `{total: 6, needs_review: 6, ambiguous: 6, with_staged_file: 0}` คือถูกตั้งธงเพราะ
> **จับคู่หลักสูตรไม่ชัด** ทั้ง 12 แถวเป็น `unchanged` และไม่มีไฟล์ใน staging
> **ห้ามใช้ 6 แถวนี้บังคับทดสอบ ingestion**

### ทรัพยากรที่มี

ดิสก์ว่าง **63G / 97G** · RAM **19Gi ว่างจาก 23Gi** · ฐานข้อมูลในอินสแตนซ์: `course_advisor`, `postgres` ·
Ollama มี `bge-m3:latest` และโมเดลอื่นอีก 5 ตัว · compose project เดียวคือ `course-advisor-system`

---

## 2. ไฟล์ที่ตรวจในรอบนี้ (อ่านจาก revision ที่ deploy จริง)

| # | ไฟล์ | สิ่งที่ยืนยัน |
|---|---|---|
| 1 | `pipeline/crawl/discover.py` | `crawl(client, seeds, allow_host, follow_patterns, max_pages)` — **`seeds` เป็นพารามิเตอร์** · กรอง `urlparse(link).netloc != allow_host` |
| 2 | `pipeline/crawl/sync.py` | state machine · `SEEDS`/`FACULTY_HOST`/`FOLLOW` เป็นค่าคงที่ระดับโมดูล ใช้เฉพาะใน `main()` · `process_link()` เรียกได้ตรง · `--staging` default `staging/crawl` (relative) |
| 3 | `pipeline/crawl/http.py` | `ALLOWED_HOSTS={"sci.pnru.ac.th"}` · `ALLOWED_SCHEMES={"http","https"}` · `ALLOWED_PORTS={None,80,443}` · `MAX_PDF_BYTES=50MB` · `PDF_SIGNATURE=b"%PDF-"` · `httpx.Client(...)` **ไม่ได้ตั้ง `verify=`** · robots.txt 404 = อนุญาต |
| 4 | `pipeline/crawl/state.py` | `CrawlStore.upsert()` `ON CONFLICT (source_url)` · `COALESCE` ค่าที่ไม่ควรหาย · `error_count` สะสม |
| 5 | `db/migrations/003_crawl_sources.sql` | `status CHECK IN ('new','unchanged','changed','downloaded','ingested','ignored','error')` · `match_confidence IN ('high','medium','ambiguous','unknown')` · view `v_crawl_pending` |
| 6 | `db/migrations/004_crawl_decisions.sql` | ตาราง 15 คอลัมน์ · 7 CHECK · 2 FK · `uq_crawl_decisions_active` partial unique `(crawl_source_id, file_sha256) WHERE superseded_at IS NULL` · view `v_crawl_queue` (19 คอลัมน์ มี `has_staged_file` ไม่มี `staging_path`) · grants |
| 7 | `backend/app/services/crawl_review.py` | `list_pending` / `get_pending` / `_for_decision` (404 vs 409) / `staged_file_location` / `resolve_course` (**ต้องมี course อยู่ก่อน**) / `_insert_decision` (UniqueViolation → 409) / `approve` / `ignore` / `undo` |
| 8 | `backend/app/services/staging_store.py` | สามชั้น: `is_relative_to(root)` หลัง `resolve()` → sha256 ตรง → `%PDF-` · `CRAWL_STAGING_DIR` ว่าง = ปิดฟีเจอร์ |
| 9 | `backend/app/api/routes/crawl_review.py` | `prefix="/crawl-review"` · `dependencies=[Depends(require_admin)]` ระดับ router · rate limiter เฉพาะ POST · `decided_by=str(admin.email)` |
| 10 | `pipeline/crawl/approve.py` | `REQUIRED_EMBED_MODEL="bge-m3"` · `REQUIRED_EMBED_DIM=1024` · `check_embedding_contract()` (env → `atttypmod` → probe จริง) · `staging_root/resolve_staged/validate_pdf` · `lock_existing_course` (`FOR SHARE`) · `completed_document` · `publish_document` (`os.replace`, ไม่เขียนทับ) · `CLAIM_SQL` `FOR UPDATE OF d SKIP LOCKED LIMIT 1` · `_ERROR_MAX=300` |
| 11 | `pipeline/ingest.py` | `already_ingested()` เช็ค `extraction_status='done'` · `get_or_create_course` · `insert_document` `ON CONFLICT (course_id, file_sha256)` · `insert_chunks` **DELETE chunks ของ document นั้นก่อน INSERT** · หนึ่ง transaction ต่อเอกสาร |
| 12 | `pipeline/embed.py` + `llm/connector.py` | `embed_chunks()` วน `connector.embed()` · `OllamaConnector.embed()` → `POST /api/embeddings` `{"model": embed_model, "prompt": text}` |
| 13 | `db/schema.sql` | `course_documents UNIQUE (course_id, file_sha256)` · `course_chunks UNIQUE (document_id, chunk_index)` · `embedding VECTOR(1024) NOT NULL` · **`ivfflat ... WITH (lists = 100)`** |
| 14 | `db/20-roles.sh` | `advisor_api`: SELECT อย่างเดียวบน `courses/course_documents/course_chunks` · `advisor_ingest`: SELECT/INSERT/UPDATE บน `courses,course_documents` และ +DELETE บน `course_chunks` |
| 15 | `backend/app/services/vector_search.py` | `search_similar_chunks(db, embedding, top_k, course_ids)` ใช้ `<=>` (cosine) |
| 16 | `backend/app/services/document_store.py` | ดัชนี sha256→path สร้างครั้งเดียวต่อโปรเซสแบบ lazy · **ไม่มีทางล้าง** |
| 17 | `eval/crawl_{state,download,approval,ingest_worker}_check.py` | รูปแบบ harness ที่โปรเจกต์ใช้อยู่ · มี DSN allowlist + `current_database()` recheck |

---

## 3. สถาปัตยกรรม ingestion ปัจจุบัน (จากการอ่าน source)

```
[1] DISCOVERY        pipeline/crawl/sync.py  (crawler)
     discover.crawl(seeds=SEEDS, allow_host="sci.pnru.ac.th", follow=FOLLOW)
       -> เดินเฉพาะหน้าใน FOLLOW  -> เก็บลิงก์ .pdf
     process_link():
       url_rejection()        -> host/scheme/port ไม่ผ่าน = error (ไม่ยิงคำขอ)
       robots.txt             -> 404 = อนุญาต
       HEAD + ETag/Length     -> เหมือนเดิม + รู้ sha แล้ว = unchanged (ไม่โหลด)
       download() streaming   -> cap 50MB · ตรวจ %PDF- · sha256
         sha == ของเดิม                 -> unchanged
         sha ตรงเอกสารในคลัง            -> unchanged + ผูก document_id
         เคยรู้ sha เดิมแต่ต่าง          -> changed    + เก็บ staging
         ไม่เคยเห็น                      -> downloaded + เก็บ staging
     CrawlStore.upsert()  ON CONFLICT (source_url)  -> mko.crawl_sources

[2] QUEUE            mko.v_crawl_queue
     แสดงแถวที่ status IN ('new','changed','downloaded','error') OR needs_review
     AND NOT EXISTS (decision ที่ยังใช้อยู่ของ (source_id, file_sha256) เดียวกัน)
     ไม่เปิด staging_path ออก — มีแค่ has_staged_file

[3] REVIEW           backend  /crawl-review/*   (require_admin ระดับ router)
     GET  /pending                -> v_crawl_queue + counts
     GET  /{id}                   -> รายละเอียดหนึ่งแถว
     GET  /{id}/pdf               -> staging_store สามชั้น (root / sha256 / %PDF-)
     POST /{id}/approve|ignore    -> INSERT mko.crawl_decisions (append-only)
     POST /{id}/undo              -> UPDATE superseded_at, superseded_by เท่านั้น
     approve ต้องระบุ course_code ที่ **มีอยู่แล้ว** (resolve_course -> 422 ถ้าไม่มี)
     _guard_sha: file_sha256 ที่ client ส่งมาต้องตรงกับแถวปัจจุบัน ไม่งั้น 409

[4] WORKER           pipeline/crawl/approve.py   (one-shot, --max-jobs N)
     check_embedding_contract()  env bge-m3/1024 -> atttypmod 1024 -> probe จริง 1024
     CLAIM_SQL  ... FOR UPDATE OF d SKIP LOCKED LIMIT 1
       เงื่อนไข: decision='approve' AND superseded_at IS NULL AND ingest_finished_at IS NULL
       ถือ lock ของแถว decision ไว้ทั้งงาน -> ปิดช่อง undo แข่งกับ worker
     lock_existing_course(course_code)  SELECT ... FOR SHARE   (ไม่สร้าง course ใหม่)
     resolve_staged() + validate_pdf()  ตรวจ root / sha / %PDF-
     publish_document()  copy -> os.replace เข้า DOCUMENTS_DIR (ไม่เขียนทับของเดิม)
     pipeline.ingest.run()  -> extract -> chunk -> embed -> insert (หนึ่ง transaction)
     finalize / record_error   -> ingest_finished_at, document_id, ingest_error

[5] INGEST           pipeline/ingest.py
     already_ingested(sha)  -> ข้ามถ้ามี course_documents.extraction_status='done'
     insert_document  ON CONFLICT (course_id, file_sha256) DO UPDATE ... WHERE <> 'done'
     insert_chunks    DELETE chunks ของ document นี้ก่อน แล้ว INSERT ใหม่
     embedding: connector.embed() ต่อ chunk -> VECTOR(1024)

[6] RETRIEVAL        backend/app/services/vector_search.py
     ORDER BY embedding <=> :query   (cosine) · index ivfflat lists=100
```

### จุดที่กระทบการออกแบบทดสอบโดยตรง

1. **`discover.crawl()` รับ `seeds` เป็นพารามิเตอร์** — harness เรียกฟังก์ชันเดียวกับที่
   `main()` เรียกได้ โดยส่ง seed ของตัวเอง **ไม่ต้องแก้ source แม้บรรทัดเดียว**
2. **`ALLOWED_HOSTS` บังคับชื่อโฮสต์ `sci.pnru.ac.th`** — เว็บจำลองจึงต้องถูกเรียกด้วย
   **ชื่อนั้น** ผ่าน network alias ในเครือข่ายทดสอบ (ไม่ใช่การแก้ allowlist)
3. **`ALLOWED_SCHEMES` มี `http`** และ `ALLOWED_PORTS` มี `80` → เว็บจำลองใช้ **HTTP ธรรมดา**
   ได้ ไม่ต้องทำใบรับรอง TLS (`httpx.Client` ไม่ได้ตั้ง `verify=` จึงไม่ต้องยุ่งกับ CA เลย)
4. **`resolve_course` และ `lock_existing_course` ต้องมี `courses.code` อยู่ก่อน** →
   ฐานข้อมูลทดสอบต้อง seed หลักสูตร `TEST101` ไว้ก่อน
5. **`ivfflat ... lists = 100` กับข้อมูลไม่กี่แถว** เป็นกับดัก — ดูข้อ 12
6. **`document_store` สร้างดัชนีครั้งเดียวต่อโปรเซส** → การเปิด PDF ของเอกสารที่เพิ่งนำเข้า
   ต้อง restart backend (ในสภาพแวดล้อมทดสอบทำได้อิสระ)

---

## 4. เปรียบเทียบกลยุทธ์ isolation

| | A. Temporary isolated database (ในอินสแตนซ์เดิม) | B. Temporary schema | C. Transaction + rollback | **D. Dedicated test compose project + postgres ของตัวเอง** |
|---|---|---|---|---|
| ระดับการแยก | ฐานข้อมูลแยก แต่ **โปรเซส postgres เดียวกัน** | schema แยก **ฐานข้อมูลเดียวกัน** | ไม่มีการแยกจริง | **แยกทั้งโปรเซส เครือข่าย และ volume** |
| พิมพ์ DSN ผิดแล้วโดน production ไหม | **เสี่ยง** — ต่างกันแค่ชื่อ database | **เสี่ยงมาก** — ต่างกันแค่ `search_path` | เสี่ยง | **ไม่ได้** — ไม่มีเส้นทางเครือข่ายไปหา production |
| role `advisor_api` / `advisor_ingest` | เป็น role ระดับ cluster **ใช้ร่วมกับ production** | ใช้ร่วมกัน | ใช้ร่วมกัน | **สร้างใหม่ในอินสแตนซ์ของตัวเอง** |
| ไฟล์ที่ worker publish ลง `DOCUMENTS_DIR` | ต้องชี้โฟลเดอร์อื่น ถ้าพลาดคือเขียนลง production | เหมือน A | **rollback ไม่ได้** — ไฟล์ถูกเขียนไปแล้ว | **volume ของตัวเอง** |
| ทดสอบ `SKIP LOCKED` / สองงานพร้อมกัน | ทำได้ | ทำได้ | **ทำไม่ได้** — คนละ transaction |ทำได้ |
| ทดสอบ crawler discovery จริง | ต้องมีเว็บจำลอง + alias อยู่ดี | เหมือน A | ทำไม่ได้ | **ทำได้เต็มรูปแบบ** |
| ทดสอบ `/crawl-review` API จริง | ต้องมี backend ชี้ DB ทดสอบ | เหมือน A | ทำไม่ได้ | **ทำได้ด้วยอิมเมจเดียวกับ production** |
| การเก็บกวาด | ต้อง `DROP DATABASE` + ลบไฟล์เอง | ต้อง `DROP SCHEMA` + ลบไฟล์เอง | ไฟล์ค้าง | **`compose down -v` ลบทุกอย่างในคราวเดียว** |
| ต้อง "หวังว่าจะลบ test data ทีหลัง" ไหม | บางส่วน (ไฟล์) | บางส่วน | **ใช่** | **ไม่ต้องเลย** |

**C ใช้ไม่ได้โดยหลักการ**: pipeline commit เอง · worker ใช้คนละ connection และ `SKIP LOCKED` ·
และ `publish_document()` เขียนไฟล์ลงดิสก์ซึ่ง `ROLLBACK` ย้อนไม่ได้

**B แย่ที่สุด**: อยู่ฐานข้อมูลเดียวกับ production · พลาด `search_path` ครั้งเดียวคือเขียนทับของจริง

**A พอใช้แต่ไม่ดีพอ**: ยังใช้โปรเซส postgres และ role ร่วมกับ production ·
ในรอบก่อน ๆ เคยใช้วิธีนี้ทดสอบ migration ซึ่งเหมาะกับงานอ่าน/DDL สั้น ๆ
แต่ E2E เขียนไฟล์ลงดิสก์ด้วย จึงไม่พอ

---

## 5. กลยุทธ์ที่เลือก

### **D — Dedicated isolated test environment (compose project แยก + postgres ของตัวเอง)**

สร้างจาก **schema/migration ชุดเดียวกับ production** (`db/schema.sql` + `001`–`004`)
และใช้ **อิมเมจเดียวกับ production** (`course-advisor-system-backend:2fdc6f2` และ
`course-advisor-system-ingest-worker:617110e`) เพื่อให้สิ่งที่ทดสอบคือโค้ดชุดเดียวกับที่รันจริง

### ควรรันที่ไหน

| ตัวเลือก | ข้อดี | ข้อเสีย | คำแนะนำ |
|---|---|---|---|
| **เครื่องของผู้พัฒนา (Windows + Docker Desktop)** | **แยกจาก production คนละเครื่อง — ไม่มีทางแตะได้เลยแม้ตั้งใจ** | ต้อง build อิมเมจเอง (Dockerfile ชุดเดียวกัน) · ต้อง `ollama pull bge-m3` 1.2 GB | **ตัวเลือกแรก** |
| เซิร์ฟเวอร์ production (compose project แยก) | มีอิมเมจและ bge-m3 อยู่แล้ว · ทรัพยากรเหลือเยอะ (RAM 19Gi ว่าง · ดิสก์ 63G) | อยู่เครื่องเดียวกับ production จึงต้องมีด่านกันพลาดเพิ่ม | ตัวเลือกสำรอง — ใช้ด่านในข้อ 6 ครบทุกข้อ |

---

## 6. การออกแบบการแยกเครือข่ายและฐานข้อมูล

### 6.1 โครงสร้าง compose project ทดสอบ

```
project name : sci-advisor-e2e          (คนละ project กับ course-advisor-system)
network      : sci-advisor-e2e_default  (bridge ของตัวเอง — ไม่ผูกกับเครือข่าย production)

services
  e2e-postgres   pgvector/pgvector:pg16     DB=e2e_test   ไม่ publish port
                 volume: e2e_pgdata          (volume ของตัวเอง)
                 initdb: db/schema.sql, db/20-roles.sh  (ชุดเดียวกับ production)
  e2e-ollama     ollama/ollama:latest       ไม่ publish port
                 volume: e2e_ollama          (volume ของตัวเอง · ollama pull bge-m3)
  e2e-fakesite   python:3.11-slim + สคริปต์  ไม่ publish port
                 networks: default:
                             aliases: [sci.pnru.ac.th]     <-- หัวใจของการทดสอบ crawler
  e2e-backend    course-advisor-system-backend:2fdc6f2     ไม่ publish port
                 DATABASE_URL -> e2e-postgres/e2e_test
                 CRAWL_STAGING_DIR=/srv/staging  DOCUMENTS_DIR=/srv/documents
                 volumes: e2e_staging:/srv/staging:ro   e2e_documents:/srv/documents:ro
  e2e-runner     course-advisor-system-ingest-worker:617110e  (มี PyMuPDF ครบ)
                 ใช้รันทั้ง harness และ worker
                 volumes: e2e_staging:/srv/staging:rw  e2e_documents:/srv/documents:rw
```

### 6.2 ทำไมเครือข่ายนี้เขียน production ไม่ได้

1. **คนละ bridge network** — ไม่ได้ `external: true` ไปหา `course-advisor-system_default`
   จึง resolve ชื่อ `postgres` / `backend` / `ollama` ของ production ไม่ได้เลย
2. **ไม่ publish port ใด** ออกสู่ host → ไม่มีทางถูกเรียกจากภายนอกโดยบังเอิญ
3. **volume แยกทั้งหมด** (`e2e_pgdata`, `e2e_staging`, `e2e_documents`, `e2e_ollama`)
   ไม่มี bind mount ไปยัง `/home/ubuntu/course-advisor-system/*` แม้แต่จุดเดียว
4. **ไม่ให้ไฟล์ `.env` ของ production เข้าไปใน project ทดสอบ** — ใช้ env ของตัวเองล้วน
5. `sci.pnru.ac.th` ถูก alias ให้ชี้ `e2e-fakesite` **ภายในเครือข่ายทดสอบเท่านั้น**
   ไม่กระทบ DNS ของ host และไม่กระทบ production

### 6.3 ด่านในตัว harness (แบบเดียวกับที่ `eval/crawl_ingest_worker_check.py` ใช้อยู่แล้ว)

```python
ALLOWED_DB = {"e2e_test"}
FORBIDDEN_SUBSTRINGS = ("course_advisor",)          # ชื่อ DB ของ production

# 1) ตรวจ DSN ก่อนต่อ
if any(s in dsn for s in FORBIDDEN_SUBSTRINGS):
    raise SystemExit("หยุด: DSN ชี้ไปที่ฐานข้อมูล production")
# 2) ตรวจซ้ำหลังต่อ ด้วยค่าที่เซิร์ฟเวอร์ตอบเอง
db = conn.execute("SELECT current_database()").scalar()
if db not in ALLOWED_DB:
    raise SystemExit(f"หยุด: ต่อกับ {db!r} ไม่ใช่ฐานข้อมูลทดสอบ")
# 3) ตรวจว่าไม่มีข้อมูล production ปนอยู่
if conn.execute("SELECT count(*) FROM course_chunks").scalar() > 1000:
    raise SystemExit("หยุด: ฐานข้อมูลนี้มีข้อมูลมากผิดปกติ อาจไม่ใช่ฐานทดสอบ")
```

ด่านที่ 3 สำคัญ: production มี 9039 chunks ส่วนฐานทดสอบควรมีหลักสิบ
ถ้าเผลอชี้ผิดจะถูกจับได้ก่อนเขียนอะไร

### 6.4 ถ้ารันบนเซิร์ฟเวอร์ production ต้องเพิ่มการพิสูจน์

ก่อนเริ่มทดสอบ ให้รันคำสั่งพิสูจน์เหล่านี้และบันทึกผล

```bash
# เครือข่ายของ project ทดสอบต้องไม่ใช่เครือข่ายของ production
docker inspect sci-advisor-e2e-e2e-runner-1 --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}'
#   ต้องได้ sci-advisor-e2e_default เท่านั้น

# จากคอนเทนเนอร์ทดสอบ ต้อง resolve ชื่อของ production ไม่ได้
docker exec sci-advisor-e2e-e2e-runner-1 getent hosts postgres
#   ต้องได้ IP ของ e2e-postgres เท่านั้น (ตรวจเทียบกับ docker inspect ของทั้งสองตัว)

# ชื่อ sci.pnru.ac.th ต้องชี้เว็บจำลองในเครือข่ายทดสอบ
docker exec sci-advisor-e2e-e2e-runner-1 getent hosts sci.pnru.ac.th
#   ต้องได้ IP ของ e2e-fakesite ไม่ใช่ IP จริงบนอินเทอร์เน็ต

# ไม่มี bind mount ไปยังโฟลเดอร์ production
docker inspect sci-advisor-e2e-e2e-runner-1 --format '{{range .Mounts}}{{.Source}} {{end}}'
#   ต้องไม่มี /home/ubuntu/course-advisor-system อยู่ในผลลัพธ์
```

---

## 7. ข้อกำหนดของ Test PDF

### 7.1 ไฟล์

```
ชื่อไฟล์   TEST_CS_CURRICULUM_E2E.pdf
ขนาด       ตั้งใจให้เล็ก (< 100 KB) เพื่อให้ extract + chunk + embed เร็ว
จำนวนหน้า  1-2 หน้า
สร้างด้วย  PyMuPDF ซึ่งมีอยู่แล้วในอิมเมจ ingest-worker (ไม่ต้องเพิ่ม dependency)
```

### 7.2 เนื้อหา (ต้องอ่านออกว่าเป็นข้อมูลทดสอบตั้งแต่บรรทัดแรก)

```
TEST DATA
NOT A REAL PNRU CURRICULUM
FOR ISOLATED E2E TEST ONLY

Course:       TEST101
Title:        E2E Pipeline Testing
Credits:      3
Description:  This document exists only to verify the automated
              PDF ingestion pipeline. It is not a curriculum document
              and must never be published to any real knowledge base.

Marker:       E2E-MARKER-TEST101-PIPELINE-VERIFICATION
```

ข้อกำหนดของเนื้อหา

- **ห้ามมีชื่อหลักสูตรจริง ชื่ออาจารย์จริง หรือรหัสวิชาจริงของ PNRU**
- **ห้ามใช้รูปแบบเอกสารที่ทำให้เข้าใจผิดว่าเป็น มคอ.2** (ไม่มีตราคณะ ไม่มีเลขที่เอกสารจริง)
- ต้องมี **marker string ที่ไม่ซ้ำกับสิ่งใดในคลังจริง** (`E2E-MARKER-TEST101-PIPELINE-VERIFICATION`)
  เพื่อใช้ยืนยันผลการค้นด้วย vector ในข้อ 12
- ต้องยาวพอให้ chunker ตัดได้อย่างน้อย 1 chunk (ตรวจ `pipeline/chunker.py` ตอนเขียน harness)

### 7.3 ความสามารถในการทำซ้ำ (reproducibility)

PyMuPDF ใส่ `creationDate`/`modDate` ลง metadata ทำให้ sha256 ต่างกันทุกครั้งที่สร้าง
harness จึงต้องทำอย่างใดอย่างหนึ่ง

- ตั้ง metadata เป็นค่าคงที่ (`doc.set_metadata({...})` พร้อม date คงที่) เพื่อให้ sha คงที่ **หรือ**
- **คำนวณ sha256 จากไฟล์ที่สร้างจริงในแต่ละรอบ** แล้วใช้ค่านั้นตลอดการทดสอบ (แนะนำ —
  ง่ายกว่าและสะท้อนพฤติกรรมจริงของ crawler ที่คำนวณ sha เอง)

**ห้าม hard-code sha256 ของ test PDF ไว้ในสคริปต์**

---

## 8. วงจรชีวิตของ TEST CANDIDATE

```
[0] seed ฐานข้อมูลทดสอบ
      - schema.sql + migrations 001..004
      - courses: INSERT (code='TEST101', title='E2E Pipeline Testing')     <- จำเป็น
      - users:   admin ทดสอบ 1 บัญชี (hash_password ของ production)         <- จำเป็น
      - course_documents = 0 · course_chunks = 0 · crawl_sources = 0 · crawl_decisions = 0

[1] เว็บจำลองเสิร์ฟ
      GET /robots.txt            -> 404          (crawler ถือว่าอนุญาต)
      GET /programs.php          -> HTML ที่มีลิงก์ไป program_detail.php?id=1
      GET /program_detail.php?id=1 -> HTML ที่มีลิงก์ไป TEST_CS_CURRICULUM_E2E.pdf
      GET /TEST_CS_CURRICULUM_E2E.pdf -> ไฟล์ PDF ทดสอบ (Content-Type: application/pdf)

[2] harness เรียก production code ตรง ๆ (ไม่แก้ source)
      from pipeline.crawl.discover import crawl
      from pipeline.crawl.sync import process_link, FOLLOW
      from pipeline.crawl.state import CrawlStore
      from pipeline.crawl.http import PoliteClient
      crawl(client, seeds=["http://sci.pnru.ac.th/programs.php"],
            allow_host="sci.pnru.ac.th", follow_patterns=FOLLOW, max_pages=10)
      -> process_link(...) -> CrawlStore.upsert(...)
      ผล: mko.crawl_sources 1 แถว status='downloaded' + staging_path + file_sha256

[3] Admin Review (e2e-backend)
      login -> GET /crawl-review/pending -> GET /{id} -> GET /{id}/pdf

[4] Approve
      POST /crawl-review/{id}/approve  {file_sha256, course_code:"TEST101"}
      -> mko.crawl_decisions 1 แถว decision='approve' superseded_at IS NULL

[5] Worker (e2e-runner)
      python -m pipeline.crawl.approve --max-jobs 1
      -> claim -> validate -> publish -> ingest -> finalize

[6] ผลลัพธ์
      course_documents 1 แถว · course_chunks > 0 · embedding 1024 มิติ
      mko.crawl_decisions.ingest_finished_at และ document_id ถูกเติม
```

---

## 9. การทดสอบ Admin Review

| # | สิ่งที่ทดสอบ | วิธี | คาดหวัง |
|---|---|---|---|
| 9.1 | anonymous ถูกปฏิเสธ | `GET /crawl-review/pending` ไม่มี token | **401** `missing bearer token` |
| 9.2 | non-admin ถูกปฏิเสธ | สร้างผู้ใช้ทดสอบ `is_admin=false` ในฐานทดสอบ แล้ว login | **403** `admin only` — **ทำได้ในสภาพแวดล้อมทดสอบ ต่างจาก production ที่ยังทดสอบไม่ได้** |
| 9.3 | admin อ่านคิวได้ | `GET /pending` | 200 · `items.length = 1` · `counts.with_staged_file = 1` |
| 9.4 | รายละเอียด | `GET /{id}` | 200 · ไม่มีฟิลด์ `staging_path` ใน payload |
| 9.5 | เปิด PDF ที่ staged ได้ | `GET /{id}/pdf` | **200** `application/pdf` ขึ้นต้น `%PDF-` — ต่างจาก production ที่ต้องเป็น 404 เพราะไม่มีไฟล์ |
| 9.6 | fail-closed เมื่อ sha ไม่ตรง | แก้ไฟล์ใน staging ของฐานทดสอบแล้วเรียก `/pdf` ซ้ำ | **404** (ชั้นที่ 2 ของ staging_store) |
| 9.7 | fail-closed เมื่อไม่ใช่ PDF | วางไฟล์ที่ไม่ขึ้นต้น `%PDF-` | **404** (ชั้นที่ 3) |
| 9.8 | path หลุด root | ตั้ง `staging_path` ให้ชี้นอก root **ในฐานทดสอบ** | **404** (ชั้นที่ 1) |
| 9.9 | approve ด้วยรหัสหลักสูตรที่ไม่มี | `course_code="NOPE999"` | **422** `ไม่มีหลักสูตรรหัส …` |
| 9.10 | approve ด้วย sha ที่ไม่ตรง | ส่ง `file_sha256` ผิด | **409** `ไฟล์เปลี่ยนไปแล้ว…` |
| 9.11 | approve สำเร็จ | `course_code="TEST101"` + sha ถูก | **201** · decision 1 แถว · `decided_by` = อีเมล admin ทดสอบ |
| 9.12 | approve ซ้ำ | ยิง approve อีกครั้งบนแถวเดิม | **409** (partial unique index `uq_crawl_decisions_active`) |
| 9.13 | คิวหายหลังตัดสินใจ | `GET /pending` อีกครั้ง | `items.length = 0` |
| 9.14 | undo คืนคิวได้ | `POST /{id}/undo` แล้ว `GET /pending` | 200 · `superseded_at` ถูกเติม · คิวกลับมา 1 รายการ |

> ข้อ 9.6–9.8 และ 9.10 เป็นการ**ทำลายข้อมูลโดยตั้งใจในฐานทดสอบ** ซึ่งทำได้เพราะแยกจริง —
> **ห้ามทำกับ production เด็ดขาด**

---

## 10. การทดสอบ Worker

| # | สิ่งที่ทดสอบ | วิธี | คาดหวัง |
|---|---|---|---|
| 10.1 | สัญญา embedding | รัน worker โดยตั้ง `EMBED_MODEL` ผิด | ล้มด้วย `embed_model_mismatch` **ก่อน**แตะงานใด |
| 10.2 | สัญญามิติ | ตั้ง `EMBED_DIM=768` | ล้มด้วย `embed_dim_mismatch` |
| 10.3 | probe จริง | ปิด e2e-ollama แล้วรัน | ล้มที่ขั้น probe ไม่ใช่ตอนกลางงาน |
| 10.4 | claim งาน | รัน `--max-jobs 1` | ยึดได้ 1 งาน · `ingest_started_at` ถูกเติม |
| 10.5 | `SKIP LOCKED` | รัน worker สองตัวพร้อมกันบนงานเดียว | ตัวหนึ่งได้งาน อีกตัวได้ `None` **ไม่ใช่ทั้งคู่ทำงานเดียวกัน** |
| 10.6 | undo ระหว่าง worker ทำงาน | ยิง `undo` ขณะ worker ถือ lock | undo ต้องรอ lock แล้วถูกปฏิเสธด้วย 409 หลัง worker commit |
| 10.7 | ไม่สร้าง course ใหม่ | approve ด้วยรหัสที่มีแต่ลบ course ออกก่อน worker รัน | worker ล้มด้วย `course_missing` **ไม่ใช่สร้างหลักสูตรใหม่** |
| 10.8 | ไฟล์ถูกสลับหลัง approve | เปลี่ยนเนื้อไฟล์ใน staging หลัง approve | `validate_pdf` ล้ม · **ไม่มี document ถูกสร้าง** |
| 10.9 | ไม่เขียนทับเอกสารเดิม | วางไฟล์ชื่อซ้ำแต่เนื้อต่างใน `DOCUMENTS_DIR` | `publish_name_collision` · ไฟล์เดิมไม่ถูกแตะ |
| 10.10 | รหัสออกของโปรเซส | งานล้มเหลว | `SystemExit(1)` · งานสำเร็จ `SystemExit(0)` |
| 10.11 | ความยาว error | ทำให้เกิด error ยาวมาก | ถูกตัดที่ `_ERROR_MAX = 300` |

---

## 11. การทดสอบ Ingestion

| # | สิ่งที่ทดสอบ | คาดหวัง |
|---|---|---|
| 11.1 | extract PDF | `page_count >= 1` · ข้อความมี `TEST101` และ marker |
| 11.2 | chunk | `course_chunks` > 0 · `chunk_index` ต่อเนื่องจาก 0 |
| 11.3 | สร้าง document | `course_documents` 1 แถว · `extraction_status='done'` · `file_sha256` ตรงกับ sha ที่ approve |
| 11.4 | ผูกกับ course ที่ระบุ | `course_documents.course_id` = id ของ `TEST101` |
| 11.5 | embedding | ทุกแถวมี `embedding` ไม่เป็น NULL |
| 11.6 | มิติ | `vector_dims(embedding) = 1024` ทุกแถว |
| 11.7 | โมเดล | log ของ worker ระบุ `bge-m3` และ `check_embedding_contract` ผ่าน |
| 11.8 | ไฟล์ถูก publish | มีไฟล์ใน `DOCUMENTS_DIR` ที่ sha256 ตรงกับที่ approve · mode 644 |
| 11.9 | decision ถูกปิดงาน | `ingest_finished_at` ไม่ null · `document_id` ชี้เอกสารที่สร้าง · `ingest_error` null |
| 11.10 | ไม่มีผลข้างเคียง | `users` / `chat_messages` ในฐานทดสอบไม่เปลี่ยน |

---

## 12. การทดสอบการค้นด้วย pgvector

### 12.1 วิธี

```python
from llm.connector import OllamaConnector
conn_llm = OllamaConnector(base_url="http://e2e-ollama:11434", embed_model="bge-m3")
q = conn_llm.embed("E2E-MARKER-TEST101-PIPELINE-VERIFICATION")
# ใช้ SQL แบบเดียวกับ backend/app/services/vector_search.py
rows = cur.execute("""
    SELECT id, document_id, chunk_index, content
      FROM course_chunks
     ORDER BY embedding <=> %s::vector
     LIMIT 5
""", (q,)).fetchall()
```

**คาดหวัง**: chunk อันดับ 1 ต้องเป็นของ `document_id` ของเอกสารทดสอบ และเนื้อหามี `TEST101`

### 12.2 กับดักที่ต้องจัดการ — `ivfflat lists = 100` กับข้อมูลไม่กี่แถว

`db/schema.sql` สร้าง `ivfflat ... WITH (lists = 100)` ซึ่งเหมาะกับคลังหลายพันแถว
แต่ฐานทดสอบมี chunk แค่หลักสิบ ผลคือ **list ส่วนใหญ่ว่าง** และค่าเริ่มต้น
`ivfflat.probes = 1` จะตรวจเพียง list เดียว → **อาจคืน 0 แถวทั้งที่ข้อมูลมีอยู่**

นี่เป็นพฤติกรรมปกติของ ivfflat ไม่ใช่ความผิดพลาดของ pipeline
ถ้าไม่จัดการจะได้ "การทดสอบล้มเหลว" ที่ตีความผิด

**วิธีจัดการใน harness** (เลือกอย่างใดอย่างหนึ่ง และบันทึกไว้ในรายงาน)

```sql
-- ก) บังคับให้ตรวจทุก list  (ตรงไปตรงมาที่สุด)
SET LOCAL ivfflat.probes = 100;

-- ข) บังคับค้นแบบตรงตัว ไม่ใช้ ANN index
SET LOCAL enable_indexscan = off;
SET LOCAL enable_bitmapscan = off;
```

**ห้ามแก้ `db/schema.sql` เพื่อให้การทดสอบผ่าน** — index ของ production ต้องเหมือนเดิม
และต้องบันทึกในรายงานว่าการค้นในฐานทดสอบใช้ `probes` ที่ต่างจากค่าเริ่มต้น
จึงพิสูจน์ได้เพียงว่า **vector ถูกเขียนและค้นเจอ** ไม่ได้พิสูจน์คุณภาพ ANN ที่ scale จริง

---

## 13. การทดสอบการกันซ้ำ

| # | สถานการณ์ | กลไกที่ควรกัน | คาดหวัง |
|---|---|---|---|
| 13.1 | รัน worker ซ้ำหลังงานเสร็จ | `CLAIM_SQL` มี `ingest_finished_at IS NULL` | ไม่มีงานให้ยึด · `course_documents` และ `course_chunks` **ไม่เพิ่ม** |
| 13.2 | approve ไฟล์เดิมซ้ำ | `uq_crawl_decisions_active` partial unique | **409** ไม่เกิด decision ที่สอง |
| 13.3 | ingest sha เดิมซ้ำ | `already_ingested()` + `ON CONFLICT (course_id, file_sha256)` | ข้าม ไม่คำนวณ embedding ใหม่ · ไม่เกิด document ที่สอง |
| 13.4 | เอกสารเดียวกันคนละ course | `UNIQUE (course_id, file_sha256)` ยอมให้ได้ | ต้องบันทึกว่าเป็นพฤติกรรมที่ออกแบบไว้ ไม่ใช่บั๊ก |
| 13.5 | เขียน chunk ซ้ำ | `insert_chunks` DELETE ก่อน INSERT + `UNIQUE (document_id, chunk_index)` | จำนวน chunk เท่าเดิม ไม่ซ้อน |
| 13.6 | publish ไฟล์ที่มีเนื้อเดียวกัน | `publish_document` วนหา sha ที่ตรงก่อน | ใช้ไฟล์เดิม ไม่เขียนไฟล์ใหม่ |

---

## 14. การทดสอบเส้นทางความล้มเหลว

| # | สถานการณ์ | คาดหวัง |
|---|---|---|
| 14.1 | ไฟล์ staging หายก่อน worker รัน | `staged_missing` · **ไม่มี document ถูกสร้าง** · `ingest_error` ถูกบันทึก |
| 14.2 | ไฟล์ถูกสลับหลัง approve (sha ไม่ตรง) | `validate_pdf` ล้ม · ไม่มี partial document |
| 14.3 | ไฟล์ไม่ใช่ PDF | ล้มที่ `%PDF-` · ไม่มี document |
| 14.4 | ollama ล่มกลางการ embed | `pipeline.ingest.run()` ล้มในหนึ่ง transaction → **ไม่มี chunk ค้างครึ่ง ๆ** · `course_documents` ของงานนั้นไม่ควรเป็น `done` |
| 14.5 | course ถูกลบระหว่างงาน | `lock_existing_course` ล้ม · ไม่มีการสร้าง course ใหม่ |
| 14.6 | ดิสก์เต็มตอน publish | `publish_failed` · ไฟล์ชั่วคราว `.publish_*` ถูกลบ |
| 14.7 | worker ถูกฆ่ากลางคัน | งานกลับเป็นงานที่ยังไม่มีใครยึด (เพราะ `ingest_started_at` อยู่ใน transaction เดียวกับ lock) · รันใหม่แล้วทำต่อได้ |

ข้อ 14.4 และ 14.7 สำคัญที่สุด เพราะเป็นสิ่งที่ทดสอบในสภาพแวดล้อมจริงไม่ได้เลย

---

## 15. Assertions ก่อน / หลัง

### 15.1 ในฐานข้อมูลทดสอบ

| จุดเวลา | assertion |
|---|---|
| **ก่อนเริ่ม** | `courses = 1` (TEST101) · `course_documents = 0` · `course_chunks = 0` · `crawl_sources = 0` · `crawl_decisions = 0` · `v_crawl_queue = 0` · `users = 2` (admin + non-admin ทดสอบ) |
| **หลัง crawl** | `crawl_sources = 1` · `status = 'downloaded'` · `file_sha256` = sha ของไฟล์ทดสอบ · `staging_path` ไม่ null · มีไฟล์จริงใน staging · `v_crawl_queue = 1` · `counts.with_staged_file = 1` |
| **หลัง approve** | `crawl_decisions = 1` · `decision = 'approve'` · `superseded_at IS NULL` · `course_code = 'TEST101'` · `v_crawl_queue = 0` |
| **หลัง worker** | `course_documents = 1` · `extraction_status = 'done'` · `course_chunks > 0` · ทุกแถว `vector_dims(embedding) = 1024` · `ingest_finished_at` ไม่ null · `document_id` ตรงกับเอกสารที่สร้าง · `ingest_error IS NULL` |
| **vector retrieval** | ค้นด้วย marker → อันดับ 1 เป็น chunk ของเอกสารทดสอบ · เนื้อหามี `TEST101` |
| **รัน worker ซ้ำ** | `course_documents` และ `course_chunks` **เท่าเดิมทุกตัว** · ไม่มี decision ใหม่ |
| **หลังทดสอบเส้นทางล้มเหลว** | จำนวน document/chunk ไม่เพิ่มจากกรณีที่ล้มเหลว |

### 15.2 กับ production (ทั้งก่อนและหลัง)

ต้อง **เท่ากันทุกค่า** กับ baseline ในข้อ 1

```
users 198/198/1 · courses 24 · course_documents 31 · course_chunks 9039
crawl_sources 12 (unchanged 12 · staging_path ไม่ null 0) · crawl_decisions 0
v_crawl_queue 6 · chat_messages 6640 · chat_answer_cache 160 · embedding_dim 1024
staging/crawl 0 ไฟล์ · documents/*.pdf 30 ไฟล์
courses ที่รหัสขึ้นต้น TEST = 0
```

ข้อสุดท้ายสำคัญเป็นพิเศษ: **ถ้า production มี `courses.code` ขึ้นต้นด้วย `TEST` แม้แถวเดียว
แปลว่าการแยกล้มเหลว** ให้หยุดและรายงานทันที

---

## 16. การพิสูจน์ความปลอดภัยต่อ production

### ลำดับที่ต้องทำในรอบที่รันจริง

1. **ก่อนเริ่ม** — อ่าน baseline ของ production แบบ read-only และเก็บไว้ (ค่าตามข้อ 1)
2. **ระหว่างทาง** — ไม่มีคำสั่งใดของการทดสอบที่อ้างถึง
   `course_advisor`, `/home/ubuntu/course-advisor-system/*`, หรือ compose project
   `course-advisor-system` เลย · ตรวจด้วยคำสั่งในข้อ 6.4
3. **หลังเสร็จ** — อ่าน baseline ของ production ซ้ำ **ต้องเท่ากันทุกค่า**
4. **หลังเก็บกวาด** — อ่านอีกครั้ง ต้องยังเท่าเดิม และคอนเทนเนอร์ production ทั้งหกต้องมี
   container ID และ StartedAt เท่าเดิม (RestartCount อย่างเดียวไม่พอ)

### สิ่งที่การทดสอบนี้ **ไม่** แตะเลย

ฐานข้อมูล `course_advisor` · `/home/ubuntu/course-advisor-system/{documents,staging,.env,Caddyfile,docker-compose*.yml}` ·
คอนเทนเนอร์และเครือข่ายของ production · Supabase · Ollama ของ production ·
อิมเมจ `rollback-*` และไฟล์ใน `/home/ubuntu/backups/`

---

## 17. คำสั่งที่ **จะ** ใช้ในรอบถัดไป (ห้ามรันในรอบนี้)

> ทั้งหมดนี้เป็นแผน · **รอบนี้ไม่ได้รันแม้คำสั่งเดียว**

```bash
# ---------- 0) เตรียม (บนเครื่องที่จะรันทดสอบ) ----------
cd <repo>
docker compose -p sci-advisor-e2e -f eval/e2e/docker-compose.e2e.yml up -d e2e-postgres e2e-ollama
docker compose -p sci-advisor-e2e -f eval/e2e/docker-compose.e2e.yml exec e2e-ollama ollama pull bge-m3

# ---------- 1) พิสูจน์การแยกก่อนทำอะไร ----------
docker inspect sci-advisor-e2e-e2e-runner-1 --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}'
docker exec sci-advisor-e2e-e2e-runner-1 getent hosts sci.pnru.ac.th
docker exec sci-advisor-e2e-e2e-runner-1 sh -c 'getent hosts postgres || echo "resolve ไม่ได้ = ดี"'

# ---------- 2) สร้าง schema + seed ----------
docker compose -p sci-advisor-e2e -f eval/e2e/docker-compose.e2e.yml \
  run --rm e2e-runner python -m eval.e2e.seed          # schema 001-004 + TEST101 + users ทดสอบ

# ---------- 3) สร้าง Test PDF และเปิดเว็บจำลอง ----------
docker compose -p sci-advisor-e2e -f eval/e2e/docker-compose.e2e.yml \
  run --rm e2e-runner python -m eval.e2e.make_test_pdf
docker compose -p sci-advisor-e2e -f eval/e2e/docker-compose.e2e.yml up -d e2e-fakesite e2e-backend

# ---------- 4) รัน E2E ทั้งชุด ----------
docker compose -p sci-advisor-e2e -f eval/e2e/docker-compose.e2e.yml \
  run --rm e2e-runner python -m eval.e2e.run_e2e --report /out/e2e_report.json

# ---------- 5) เก็บกวาด ----------
docker compose -p sci-advisor-e2e -f eval/e2e/docker-compose.e2e.yml down -v --remove-orphans
docker volume ls | grep sci-advisor-e2e     # ต้องไม่เหลือ

# ---------- 6) ตรวจ production ซ้ำ (read-only) ----------
# ใช้ query ชุดเดียวกับข้อ 1 แล้วเทียบทีละค่า
```

---

## 18. ไฟล์ที่ต้องเพิ่ม (test-only) — diff plan · **ยังไม่สร้างในรอบนี้**

| ไฟล์ | บทบาท | แตะ production ไหม |
|---|---|---|
| `eval/e2e/docker-compose.e2e.yml` | นิยาม project ทดสอบ · network alias `sci.pnru.ac.th` · volume แยก | ไม่ |
| `eval/e2e/fakesite/server.py` | เว็บจำลอง — เสิร์ฟ `programs.php`, `program_detail.php?id=1`, PDF · ตอบ 404 ให้ `robots.txt` | ไม่ |
| `eval/e2e/make_test_pdf.py` | สร้าง `TEST_CS_CURRICULUM_E2E.pdf` ด้วย PyMuPDF | ไม่ |
| `eval/e2e/seed.py` | สร้าง schema จาก `db/schema.sql` + migrations 001–004 · seed `TEST101` และผู้ใช้ทดสอบ | อ่านไฟล์ schema เท่านั้น |
| `eval/e2e/run_e2e.py` | harness หลัก · import โค้ด production · ด่าน DSN · assertions ทั้งหมด | ไม่ |
| `eval/e2e/README.md` | อธิบายว่านี่คือ TEST CANDIDATE เท่านั้น · ห้ามชี้ไป production | ไม่ |

**ไม่ต้องแก้ไฟล์ production แม้ไฟล์เดียว** — เพราะ

- `discover.crawl()` รับ `seeds` เป็นพารามิเตอร์อยู่แล้ว
- `ALLOWED_HOSTS` ผ่านได้ด้วย network alias ไม่ใช่ด้วยการแก้ allowlist
- `ALLOWED_SCHEMES` มี `http` อยู่แล้ว จึงไม่ต้องทำ TLS และไม่ต้องยุ่งกับ CA
- `process_link()`, `CrawlStore`, `PoliteClient`, `pipeline.ingest.run()`,
  `pipeline.crawl.approve` เรียกใช้จากภายนอกได้ทั้งหมด

---

## 19. ความเสี่ยงและข้อจำกัด

| # | เรื่อง | ผลกระทบ | การจัดการ |
|---|---|---|---|
| 1 | **ivfflat `lists=100` กับข้อมูลน้อย** | การค้นอาจคืน 0 แถวทั้งที่ข้อมูลถูกต้อง | ตั้ง `ivfflat.probes` หรือปิด index scan ในคำค้นของ harness · บันทึกว่าไม่ได้พิสูจน์คุณภาพ ANN ที่ scale จริง |
| 2 | **Test PDF ไม่เหมือน มคอ.2 จริง** | ไม่ได้พิสูจน์คุณภาพการ extract/chunk กับเอกสารจริงที่ซับซ้อน | ระบุชัดว่าทดสอบ **กลไกของ pipeline** ไม่ใช่คุณภาพการสกัดข้อมูล |
| 3 | **เว็บจำลองไม่เหมือน `sci.pnru.ac.th` จริง** | ไม่ได้พิสูจน์การเดินเว็บจริง (โครงสร้าง HTML, redirect, ETag ของ IIS/Apache จริง) | การทดสอบกับเว็บจริงทำไปแล้วใน Phase 2 (`CRAWLER_PRODUCTION_VERIFY_REPORT.md`) · ระบุขอบเขตให้ชัด |
| 4 | **ถ้ารันบนเครื่อง production** | ใช้ CPU/RAM/ดิสก์ร่วมกับบริการจริง · embedding กิน CPU หนัก | รันนอกเวลาใช้งาน · จำกัด `--max-jobs 1` · ถ้าเป็นไปได้ให้รันบนเครื่องผู้พัฒนาแทน |
| 5 | **bge-m3 ใน e2e-ollama เป็นคนละ instance** | ผลลัพธ์ embedding ควรเหมือนกันเพราะโมเดลเดียวกัน แต่ไม่ได้พิสูจน์ว่าเหมือน bit-for-bit | ยืนยันด้วย digest ของโมเดล (`ollama list` แสดง ID) · assertion ที่ใช้คือมิติและการค้นเจอ ไม่ใช่ค่าตัวเลขเป๊ะ |
| 6 | **`document_store` ต้อง restart จึงเห็นไฟล์ใหม่** | ทดสอบเปิด PDF ของเอกสารที่เพิ่งนำเข้าต้อง restart `e2e-backend` | ทำได้อิสระในสภาพแวดล้อมทดสอบ · **ยืนยันข้อจำกัดนี้ให้เป็นหลักฐานสำหรับ runbook ของ production** |
| 7 | **sha256 ของ Test PDF ไม่คงที่** | ถ้า hard-code ไว้จะพังทุกครั้งที่สร้างใหม่ | คำนวณจากไฟล์จริงทุกครั้ง (ข้อ 7.3) |
| 8 | **ผู้ใช้ทดสอบมีรหัสผ่านที่ harness สร้าง** | เป็น credential ที่มีอยู่เฉพาะในฐานทดสอบซึ่งถูกลบทิ้งตอนเก็บกวาด | สร้างด้วย `secrets.token_urlsafe()` ในโปรเซส · ไม่เขียนลงไฟล์ · ไม่ใช้ซ้ำที่อื่น · ไม่ใช่รหัสผ่านของใครจริง |
| 9 | **ต้องลบ volume ให้หมด** | volume ค้างกินดิสก์และอาจสับสนรอบหน้า | `down -v --remove-orphans` แล้วตรวจ `docker volume ls` |

---

## 20. Cleanup strategy

```bash
docker compose -p sci-advisor-e2e -f eval/e2e/docker-compose.e2e.yml down -v --remove-orphans
docker volume ls    | grep sci-advisor-e2e   # ต้องว่าง
docker network ls   | grep sci-advisor-e2e   # ต้องว่าง
docker ps -a        | grep sci-advisor-e2e   # ต้องว่าง
docker image rm sci-advisor-e2e-fakesite     # ถ้า build อิมเมจ fakesite เอง
```

**จุดแข็งของกลยุทธ์ D**: ทุกอย่างอยู่ใน project/volume/network ของตัวเอง
การเก็บกวาดจึงเป็นคำสั่งเดียวที่ลบได้หมดจริง **ไม่มีอะไรที่ต้อง "หวังว่าจะลบ test data
ออกจาก production ทีหลัง"** ซึ่งเป็นเกณฑ์ที่โจทย์กำหนดไว้

อิมเมจที่ **ห้ามลบ**: `course-advisor-system-backend:2fdc6f2` ·
`course-advisor-system-frontend:2fdc6f2` · `*:rollback-pre-phase3d` ·
`course-advisor-system-ingest-worker:617110e` · ไฟล์ใน `/home/ubuntu/backups/`

---

## 21. GO / NO-GO

| เรื่อง | คำตัดสิน | เหตุผล |
|---|---|---|
| **รัน isolated E2E test ในรอบถัดไป** | **GO** (เมื่อเจ้าของอนุมัติ) | แยกได้จริงทุกชั้น · ไม่ต้องแก้ source production · ไม่ต้องแตะ production แม้แต่การอ่าน (นอกจากเก็บ baseline อ่านอย่างเดียว) · เก็บกวาดได้หมดด้วยคำสั่งเดียว · ทรัพยากรพอ |
| **production one-job ingestion** | **ยัง NO-GO — ไม่เปลี่ยนแปลง** | ยังไม่มี PRODUCTION CANDIDATE · การที่ E2E ผ่านในสภาพแวดล้อมทดสอบ **ไม่ใช่เหตุให้รัน ingestion บน production** |
| **ใช้ 6 แถวในคิวเป็น candidate** | **ห้ามถาวร** | เป็นแถว `unchanged` ที่ `ambiguous` ไม่มีไฟล์ staged |

### เงื่อนไขก่อนเริ่มรอบถัดไป

1. เจ้าของอนุมัติให้สร้างไฟล์ทดสอบ 6 ไฟล์ในข้อ 18 (ยังไม่ commit)
2. ตัดสินใจว่าจะรันบน **เครื่องผู้พัฒนา** (แนะนำ) หรือ **เซิร์ฟเวอร์ production**
3. ถ้าเลือกเซิร์ฟเวอร์ ต้องรันคำสั่งพิสูจน์การแยกในข้อ 6.4 และบันทึกผลก่อนเริ่ม
4. เก็บ production baseline แบบอ่านอย่างเดียวก่อนและหลัง แล้วเทียบทีละค่า

---

## สิ่งที่ไม่ได้ทำในรอบนี้

**รอบนี้เป็น DESIGN ONLY · production mutation = 0**

ไม่ได้รัน crawler · ไม่ได้รัน worker · ไม่ได้ ingestion · ไม่ได้สร้าง embedding ·
ไม่ได้ POST approve/ignore/undo · ไม่ได้สร้าง candidate ใด ๆ ทั้ง production และ test ·
ไม่ได้ INSERT แถวใดลง `mko.crawl_sources` · ไม่ได้เปลี่ยน status/hash/staging_path ·
ไม่ได้อัปโหลด PDF ใดเข้า staging · ไม่ได้แก้ `courses`/`course_documents`/`course_chunks` ·
ไม่ได้แก้ Supabase · ไม่ได้แก้ auth · ไม่ได้แก้ Caddy · ไม่ได้ restart · ไม่ได้ deploy ·
ไม่ได้ migration · ไม่ได้ commit/push · ไม่ได้ merge main ·
**ไม่ได้สร้างไฟล์ทดสอบทั้ง 6 ไฟล์ในข้อ 18** (เป็นแผนเท่านั้น) ·
ไม่ได้สร้าง compose project หรือ volume ใด

การดำเนินการทั้งหมดในรอบนี้: `git show` / `git grep` / `git ls-tree` บน revision ที่ deploy ·
`docker exec` ที่รัน `psql` ใน `BEGIN TRANSACTION READ ONLY` พร้อม `statement_timeout` ·
`docker inspect` · `df` / `free` · และ `ollama list` ซึ่งอ่าน metadata อย่างเดียว

---

## STOP

รอ **owner review / approval** ก่อนเริ่ม Phase ถัดไป

ห้าม execute test · ห้ามสร้าง test candidate จริง · ห้าม run worker · ห้าม ingestion ·
ห้ามแก้ production

STOP
