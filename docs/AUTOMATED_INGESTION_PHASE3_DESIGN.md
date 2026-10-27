# Phase 3 — Admin Review & Approval → Ingestion (แบบที่เสนอ)

| | |
|---|---|
| วันที่ | 28 กันยายน 2569 |
| branch | `mko-phase2` (`2cdab40`) |
| สถานะ | **ออกแบบเท่านั้น ยังไม่ implement** |
| ไม่ได้ทำในรอบนี้ | แก้ source code · แก้ schema · deploy · ingest · สร้าง embedding · restart · ตั้ง cron/systemd · แตะ Supabase |

เป้าหมายปลายทาง

```
Crawler → New/Changed PDF → Staging → Admin Review → Approve
        → Existing Ingestion Pipeline → Extract → Chunk → Embedding
        → PostgreSQL/pgvector → RAG
```

---

## 0. สรุปสำหรับคนรีบ

ระบบเดิมพร้อมกว่าที่คิดในส่วน pipeline แต่ **ยังไม่พร้อมเลยในส่วน Admin** — ไม่มีหน้า admin
ไม่มี API admin ของเราเอง และสิทธิ์ฐานข้อมูลของ backend ยังเขียนตาราง crawl ไม่ได้

พบอุปสรรคจริง 9 ข้อจากการอ่านโค้ด (หัวข้อ 1) ที่สำคัญสามข้อ

1. **`/api/admin/*` ถูกจองไปแล้วทั้งก้อน** — [Caddyfile:37](Caddyfile:37) ส่งไป `webapi` ของเพื่อน
   ซึ่งคุยกับ Supabase API ใหม่จึงต้องใช้ prefix อื่น ไม่ใช่ `/api/admin`
2. **crawler เขียนทับการตัดสินใจของคน** — [state.py:150](pipeline/crawl/state.py:150)
   ตั้ง `status = EXCLUDED.status` และ `needs_review = EXCLUDED.needs_review` ทุกรอบไม่มีเงื่อนไข
   ถ้าเก็บผลอนุมัติไว้ในคอลัมน์ของ `crawl_sources` การ crawl รอบถัดไปจะลบทิ้ง
3. **`advisor_api` เขียน `mko.crawl_sources` ไม่ได้** — [003:131-135](db/migrations/003_crawl_sources.sql:131)
   ให้แค่ `SELECT ON mko.v_crawl_pending`

แนวทางที่เสนอแก้ทั้งสามข้อด้วยหลักเดียว: **แยก "เจตนาของคน" ออกจาก "สถานะของไฟล์"**
เก็บผลอนุมัติในตารางใหม่แบบเพิ่มเท่านั้น (`mko.crawl_decisions`) ผูกกับ `file_sha256`
crawler จึงเขียนทับไม่ได้เพราะอยู่คนละตาราง และ backend ไม่ต้องมีสิทธิ์แตะ `crawl_sources` เลย

ผลพลอยได้ที่สำคัญ: **backend บันทึกเจตนาได้อย่างเดียว ทำ ingestion ไม่ได้** ซึ่งตอบข้อห้าม
"ห้าม client/frontend เรียก ingestion โดยตรง" ที่ระดับสิทธิ์ฐานข้อมูล ไม่ใช่ที่ระดับโค้ด

สถาปัตยกรรม production ที่เสนอ: **ingest-worker เป็นคอนเทนเนอร์แบบรันครั้งเดียวแล้วจบ**
(`profiles: ["ingest"]`) ไม่ใช่บริการที่รันค้าง และไม่เพิ่ม dependency ใด ๆ เข้า backend

---

## 1. ผลวิเคราะห์ระบบปัจจุบัน — อุปสรรคที่พบ

| # | เรื่อง | หลักฐาน | ผลถ้าไม่แก้ |
|---|---|---|---|
| B1 | `/api/admin/*` ทั้ง prefix ถูก proxy ไป `webapi` (Supabase ของเพื่อน) | [Caddyfile:37](Caddyfile:37) | API admin ใหม่ได้ 404 ทั้งหมด |
| B2 | `advisor_api` มีแค่ `SELECT ON mko.v_crawl_pending` ไม่มีสิทธิ์บนตารางจริง | [003:131](db/migrations/003_crawl_sources.sql:131) | บันทึกการอนุมัติไม่ได้ |
| B3 | `upsert()` ตั้ง `status`/`needs_review` ทับทุกรอบ | [state.py:148-150](pipeline/crawl/state.py:148) | คนกด Ignore แล้วรอบหน้ากลับเข้าคิวอีก |
| B4 | แถวที่ ingest แล้วจะกลายเป็น `unchanged` แต่ `needs_review` ยังค้าง `true` ถ้า match กำกวม | [sync.py:166-175](pipeline/crawl/sync.py:166) | แถวติดอยู่ในคิวตรวจตลอดไป |
| B5 | `ingest.run()` คืน `None` ไม่คืน `document_id` | [ingest.py:170](pipeline/ingest.py:170) | ผูก `crawl_sources.document_id` ไม่ได้ตรง ๆ |
| B6 | `ingest.run()` ใช้ `raise SystemExit` เมื่อไม่มี env | [ingest.py:174](pipeline/ingest.py:174) | เรียกใน process ของเว็บจะฆ่า worker ทิ้ง |
| B7 | backend image ไม่มี `pymupdf`/`tqdm` · mount เอกสารเป็น `:ro` · ไม่มี `INGEST_DATABASE_URL` | [backend/requirements.txt](backend/requirements.txt), [prod:86](docker-compose.prod.yml:86) | backend ทำ ingest เองไม่ได้ (และไม่ควรได้) |
| B8 | โหลดไฟล์ไม่จำกัดขนาด · `follow_redirects=True` ไม่ตรวจ host ปลายทาง · ไม่ตรวจว่าเป็น PDF จริง | [http.py:54](pipeline/crawl/http.py:54), [sync.py:151](pipeline/crawl/sync.py:151) | ไฟล์นอก host หรือไฟล์ยักษ์เข้ามาถึง staging ได้ |
| B9 | `v_crawl_pending` เปิดเผย `staging_path` | [003:116](db/migrations/003_crawl_sources.sql:116) | ส่ง path บนเซิร์ฟเวอร์ออกไปให้เบราว์เซอร์ถ้าเผลอส่งดิบ |

### สิ่งที่พร้อมใช้อยู่แล้ว

| เรื่อง | ที่อยู่ | หมายเหตุ |
|---|---|---|
| `require_admin` | [deps.py:50](backend/app/api/deps.py:50) | **เขียนไว้แล้วแต่ยังไม่มี route ไหนใช้** Phase 3 จะเป็นผู้ใช้รายแรก |
| `User.is_admin` | [models/user.py:19](backend/app/models/user.py:19) | มีคอลัมน์แล้ว |
| JWT + bcrypt | [core/security.py](backend/app/core/security.py) | HS256, access 30 นาที, bcrypt cost 12 |
| แบบแผนส่ง PDF อย่างปลอดภัย | [documents.py](backend/app/api/routes/documents.py), [document_store.py](backend/app/services/document_store.py) | ไม่รับ path จากผู้ใช้ · ตรวจ `is_relative_to(root)` · ตรวจ sha256 ซ้ำก่อนส่ง · 404 ทุกกรณี |
| แบบแผนบันทึกการตัดสินของคน | `mko.review_decisions` ใน [002](db/migrations/002_mko_review_publish.sql:21) | `reviewer TEXT NOT NULL` + `superseded_at` + partial unique index |
| เรียก ingest ซ้ำโดยไม่ duplicate logic | [ingest_batch.py:33](pipeline/ingest_batch.py:33) | `from pipeline.ingest import run` — มีตัวอย่างอยู่แล้ว |
| กันนำเข้าซ้ำ | [ingest.py:80](pipeline/ingest.py:80), [ingest.py:125](pipeline/ingest.py:125) | เช็ค sha256 ก่อน embed + `ON CONFLICT (course_id, file_sha256)` |
| ตัวตั้งขนาดไฟล์สูงสุด | [config.py:54](backend/app/core/config.py:54) `max_pdf_size_mb = 50` | ประกาศไว้แล้วแต่ยังไม่มีใครใช้ |

### Admin UI ปัจจุบันอยู่ไหน

**ไม่มี** — และมีสองทางเข้าเว็บที่ต้องแยกให้ชัด ([Caddyfile](Caddyfile))

| ทางเข้า | ปลายทาง | ของใคร |
|---|---|---|
| ชื่อโดเมน `stpnru-advisor.duckdns.org` | ไฟล์นิ่งใน `/srv/web` (SPA ของทีมออกแบบ) + API | เพื่อน — อยู่คนละ repo ไม่ได้ track ที่นี่ |
| เลข IP พอร์ต 80 | `frontend:3000` (Next.js ของเรา) | ทีมหลังบ้าน — มี `/match` กับ `/compare` อยู่แล้ว |

หน้าตรวจของ Phase 3 จึงควรอยู่ใน **Next.js ของเรา** ไม่ใช่ SPA ของเพื่อน เพราะเป็นเครื่องมือของ
ทีมหลังบ้านแบบเดียวกับ `/match` และ `/compare` และเพราะ SPA ของเพื่อนอยู่คนละ repo

### ควรให้ FastAPI หรือ webapi จัดการ

**FastAPI** ชัดเจน ด้วยเหตุผลสามข้อ

1. `webapi` คุยกับ Supabase เท่านั้น ไม่ได้ต่อฐานข้อมูลของเราเลย ([prod:106-114](docker-compose.prod.yml:106))
2. `webapi/api/` เป็นโค้ดของเพื่อนที่ **gitignore ไว้** ([.gitignore:49](.gitignore:49)) แก้ไม่ได้และไม่ควรแก้
3. auth ของเราคือ JWT + `users.is_admin` ใน PostgreSQL ซึ่ง `webapi` ไม่รู้จัก

---

## 2. Architecture ที่เสนอ

```
                        ┌──────────────────────────────────────────┐
                        │  เครื่องผู้ดูแล (เบราว์เซอร์)              │
                        │  http://<ip>/crawl-review                │
                        └───────────────┬──────────────────────────┘
                                        │ Bearer JWT (is_admin)
                        ┌───────────────▼──────────────────────────┐
                        │  frontend (Next.js)                      │
                        │  app/crawl-review/page.tsx               │
                        │  /api/* ──► proxy ส่งต่อ authorization    │
                        └───────────────┬──────────────────────────┘
                                        │
                        ┌───────────────▼──────────────────────────┐
                        │  backend (FastAPI)  role: advisor_api    │
                        │  /crawl-review/…                         │
                        │                                          │
                        │  สิทธิ์ที่มี:                              │
                        │    SELECT  mko.v_crawl_queue             │
                        │    INSERT  mko.crawl_decisions           │
                        │    UPDATE  mko.crawl_decisions           │
                        │              (superseded_at เท่านั้น)      │
                        │  สิทธิ์ที่ไม่มีโดยเจตนา:                    │
                        │    เขียน mko.crawl_sources               │
                        │    เขียน course_documents / course_chunks │
                        │    เรียก pipeline.ingest                 │
                        └───────────────┬──────────────────────────┘
                                        │ เขียนเจตนาลง DB เท่านั้น
                        ┌───────────────▼──────────────────────────┐
                        │  PostgreSQL 16 + pgvector                │
                        │  mko.crawl_sources     (crawler เขียน)    │
                        │  mko.crawl_decisions   (backend เขียน)    │
                        │  public.course_*       (worker เขียน)     │
                        └───────────────▲──────────────────────────┘
                                        │
     ┌──────────────────────────────────┴───────────────────────────┐
     │  ingest-worker (คอนเทนเนอร์แบบรันครั้งเดียวแล้วจบ)             │
     │  docker compose run --rm ingest-worker                       │
     │  role: advisor_ingest                                        │
     │                                                              │
     │  1. หา decision ที่ approve แล้วยังไม่ ingest                  │
     │  2. ตรวจไฟล์ใน staging (ใต้ root · sha256 ตรง · เป็น PDF จริง) │
     │  3. เรียก pipeline.ingest.run()  ◄── โค้ดเดิม ไม่แก้           │
     │  4. อัปเดต crawl_sources เป็น ingested + document_id          │
     └──────────────────────────────────────────────────────────────┘
```

### หลักการที่ถือไว้สามข้อ

1. **เจตนาของคน ≠ สถานะของไฟล์** อยู่คนละตาราง crawler เขียนทับกันไม่ได้
2. **ใครทำอะไรได้ บังคับที่สิทธิ์ฐานข้อมูล ไม่ใช่ที่โค้ด** backend ทำ ingest ไม่ได้เพราะไม่มีสิทธิ์
   ไม่ใช่เพราะเราไม่ได้เขียนโค้ดให้มันทำ
3. **ไม่แก้ `pipeline/ingest.py`** worker เรียกผ่าน `from pipeline.ingest import run` เหมือน
   `ingest_batch.py` ทำอยู่แล้ว

---

## 3. Workflow ตั้งแต่ Crawler จนถึง RAG

```
[1] crawler (มีอยู่แล้ว · Phase 2)
    python -m pipeline.crawl.sync --database-url $CRAWL_DATABASE_URL --staging /srv/staging
      → เขียน mko.crawl_sources
      → ไฟล์ใหม่/ไฟล์ที่เปลี่ยน ลง /srv/staging/<sha12>_<ชื่อเดิม>.pdf
      → ไม่แตะ course_* · ไม่ ingest

[2] คนดูแลเปิดหน้าตรวจ   GET /crawl-review/pending
      → เห็นคิวจาก mko.v_crawl_queue (แถวที่ยังไม่มี decision ที่ยังใช้อยู่)

[3] กดดูไฟล์            GET /crawl-review/{id}/pdf
      → backend อ่าน staging_path จาก DB (ไม่ใช่จาก client)
      → ตรวจใต้ root · ตรวจ sha256 · ตรวจ %PDF- แล้วส่ง inline

[4] ตัดสินใจ
      POST /crawl-review/{id}/approve  {course_code?, title?, note?, file_sha256}
      POST /crawl-review/{id}/ignore   {reason, file_sha256}
      → INSERT mko.crawl_decisions (เพิ่มเท่านั้น ไม่ UPDATE crawl_sources)
      → แถวหายจากคิวทันทีเพราะ view กรองด้วย decision

[5] ingest-worker (รันเมื่อมีของรออนุมัติ)
      docker compose -f docker-compose.prod.yml run --rm ingest-worker
      → SELECT … FOR UPDATE SKIP LOCKED  งานที่ approve แล้วยังไม่เสร็จ
      → ตรวจไฟล์ซ้ำ (root · sha256 · %PDF-)
      → pipeline.ingest.run(pdf, title, course_code, provider)   ◄ โค้ดเดิม
      → หา document_id จาก sha256
      → UPDATE crawl_sources SET status='ingested', document_id=…
      → UPDATE crawl_decisions SET ingested_at=…, document_id=…

[6] RAG ใช้ได้ทันที (ไม่ต้องทำอะไรเพิ่ม)
      course_chunks มี embedding ใหม่แล้ว → search_similar_chunks เห็นเอง
      ⚠ ต้อง bump answer_cache._LOGIC_VERSION? — ไม่ต้อง
         corpus_version ผูกกับ MAX(updated_at) ของคลังอยู่แล้ว
         เอกสารใหม่เปลี่ยน corpus_version เอง แคชเก่าหมดอายุอัตโนมัติ
```

### จุดที่ crawler รอบถัดไปต้องไม่ทำลายของ

รอบถัดไปหลัง ingest สำเร็จ `sha` จะอยู่ใน `known_by_sha` แล้ว → [sync.py:166](pipeline/crawl/sync.py:166)
ตั้ง `status='unchanged'` + ผูก `document_id` ซึ่งถูกต้อง

แต่ `needs_review` จะถูกตั้งกลับเป็น `true` ถ้า match เดิมกำกวม (B4) — **แก้ด้วย view ไม่ใช่แก้ crawler**
`v_crawl_queue` กรองแถวที่มี decision ที่ยังใช้อยู่ออก จึงไม่กลับเข้าคิวแม้ `needs_review` ยังเป็น true
ข้อดีคือไม่ต้องแตะ `pipeline/crawl/state.py` เลย

---

## 4. Admin UI / API design

### API — prefix `/crawl-review` (ไม่ใช่ `/api/admin` เพราะ B1)

เส้นทางจริงที่ผู้ใช้เรียกคือ `/api/crawl-review/…` ซึ่ง Caddy `handle /api/*` ตัด `/api` แล้วส่งให้
backend เป็น `/crawl-review/…` **ไม่ต้องแก้ Caddyfile** และไม่เสี่ยงกระทบเส้นทางของเพื่อน

| Method | Path | ใคร | ทำอะไร |
|---|---|---|---|
| `GET` | `/crawl-review/pending` | `require_admin` | คิวรอตรวจ พร้อมตัวนับสรุป |
| `GET` | `/crawl-review/{id}` | `require_admin` | รายละเอียดแถวเดียว รวม `match_candidates` |
| `GET` | `/crawl-review/{id}/pdf` | `require_admin` | เปิดไฟล์ staging แบบ inline |
| `POST` | `/crawl-review/{id}/approve` | `require_admin` | บันทึก decision = approve |
| `POST` | `/crawl-review/{id}/ignore` | `require_admin` | บันทึก decision = ignore |
| `POST` | `/crawl-review/{id}/undo` | `require_admin` | ตั้ง `superseded_at` ของ decision ล่าสุด |

**สิ่งที่ตอบกลับ** (ตัดฟิลด์ที่ไม่ควรออกนอกเซิร์ฟเวอร์)

```json
{
  "id": "…uuid…",
  "source_url": "https://sci.pnru.ac.th/upload/….pdf",
  "page_url": "https://sci.pnru.ac.th/program_detail.php?id=12",
  "page_title": "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชา…",
  "course_code": "sci-cs-66",
  "course_label": "วิทยาการคอมพิวเตอร์ (พ.ศ. 2566)",
  "match_confidence": "ambiguous",
  "match_score": 0.912,
  "match_candidates": ["วิทยาการคอมพิวเตอร์ (พ.ศ. 2561)", "วิทยาการคอมพิวเตอร์ (พ.ศ. 2566)"],
  "status": "downloaded",
  "needs_review": true,
  "review_reason": "ชื่อหลักสูตรตรงกับ 2 ฉบับ แยกจากชื่ออย่างเดียวไม่ได้ · ไฟล์ใหม่ ยังไม่มีในคลัง",
  "file_sha256": "…64 hex…",
  "previous_sha256": null,
  "content_length": 4718592,
  "last_checked_at": "2026-09-28T01:56:01Z",
  "has_staged_file": true
}
```

- **ไม่ส่ง `staging_path`** (B9) ส่ง `has_staged_file` เป็น boolean แทน
- ส่ง `file_sha256` เพราะ client ต้องส่งกลับมาตอน approve เป็น optimistic lock

### กัน Approve ซ้ำ และกันสองคนกดพร้อมกัน — สามชั้น

| ชั้น | กลไก | ผลเมื่อชน |
|---|---|---|
| 1 | client ส่ง `file_sha256` ที่เห็นบนหน้าจอมาด้วย backend เทียบกับค่าในฐานข้อมูล | `409` "ไฟล์เปลี่ยนไปแล้ว กรุณาโหลดคิวใหม่" |
| 2 | partial unique index `(crawl_source_id, file_sha256) WHERE superseded_at IS NULL` | `INSERT` ตัวที่สองได้ `23505` → `409` |
| 3 | `ingest.already_ingested(sha256)` + `ON CONFLICT (course_id, file_sha256)` ใน pipeline เดิม | ข้ามการ embed ทันที ไม่เสียเวลาเป็นชั่วโมง |

ชั้นที่ 3 มีอยู่แล้วและเป็นด่านที่ถูกที่สุด — [ingest.py:80-101](pipeline/ingest.py:80)

### UI — `frontend/app/crawl-review/page.tsx`

โครงเดียวกับ `app/match/page.tsx` ที่มีอยู่ (client component + `lib/api.ts`)

```
┌─ คิวรอตรวจ ───────────────────────────── 6 รายการ · 2 กำกวม ─┐
│                                                               │
│ ⚠ ระบุหลักสูตรไม่ได้                          [ดู PDF]        │
│   หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชา…                          │
│   sci.pnru.ac.th/upload/24d048df….pdf   4.5 MB   ใหม่         │
│   จับคู่:  (เลือก) ─────────────────────────────────┐          │
│           ◦ วิทยาการคอมพิวเตอร์ (พ.ศ. 2561)         │          │
│           ◦ วิทยาการคอมพิวเตอร์ (พ.ศ. 2566)         │          │
│           ◦ ไม่ใช่หลักสูตร / ไม่เกี่ยวข้อง            │          │
│   เหตุผล: ชื่อหลักสูตรตรงกับ 2 ฉบับ แยกจากชื่อเดียวไม่ได้        │
│                          [อนุมัติ]  [ไม่เกี่ยวข้อง]            │
└───────────────────────────────────────────────────────────────┘
```

กติกาของหน้านี้

- ปุ่ม **อนุมัติ** ปิดอยู่จนกว่าจะเลือกหลักสูตร เมื่อ `match_confidence` เป็น `ambiguous`
  หรือ `unknown` — บังคับให้คนเลือก ไม่ให้ระบบเดา (ตรงกับข้อกำหนด Phase 2)
- เปิด PDF ในแท็บใหม่ ไม่ใช่ iframe เพราะ proxy ของ Next ไม่ส่งต่อ `range`/`accept-ranges`
  ([route.ts:49](frontend/app/api/[...path]/route.ts:49)) ตัวอ่าน PDF จะโหลดทั้งเล่มเสมอ
- หลังกดปุ่มแล้วโหลดคิวใหม่ ไม่ลบแถวออกจากหน้าจอเอง เพื่อให้เห็นผลจริงจากเซิร์ฟเวอร์
- แสดงเฉพาะสิ่งที่ API ส่งมา ไม่คำนวณสถานะเองในเบราว์เซอร์

### อ่าน `mko.v_crawl_pending` อย่างปลอดภัยอย่างไร

1. **ผ่าน view ไม่ใช่ตารางจริง** — `advisor_api` ได้สิทธิ์เฉพาะ view จึงอ่านคอลัมน์
   `approved_by`, `last_error`, `http_etag` ไม่ได้เลยแม้เขียนโค้ดผิด
2. **เสนอ view ใหม่ `mko.v_crawl_queue`** ที่ **ไม่มี `staging_path`** แทนการใช้
   `v_crawl_pending` ตรง ๆ (B9) — `v_crawl_pending` เก็บไว้เป็นของ crawler เหมือนเดิม
3. **query ด้วย SQLAlchemy `text()` + bind parameter** เหมือน
   [documents.py:37](backend/app/api/routes/documents.py:37) ไม่ต่อสตริง
4. **ไม่สร้าง SQLAlchemy model ให้ `crawl_sources`** เพื่อไม่ให้มีทางเขียนโดยบังเอิญ

---

## 5. Ingestion workflow

### เรียก ingestion เดิมอย่างไรโดยไม่ duplicate logic

`pipeline/ingest.py` ไม่ต้องแก้แม้บรรทัดเดียว worker import `run()` ตรง ๆ แบบเดียวกับที่
[ingest_batch.py:33](pipeline/ingest_batch.py:33) ทำอยู่แล้ว

```python
# pipeline/crawl/approve.py (ไฟล์ใหม่)
from pipeline.ingest import run as ingest_run

ingest_run(str(staged_file), title=title, course_code=course_code, provider=provider)
```

### ปัญหาที่ต้องจัดการรอบ `run()`

| ปัญหา | วิธีแก้ที่เสนอ (ไม่แก้ `ingest.py`) |
|---|---|
| `run()` คืน `None` (B5) | หลังรันเสร็จ `SELECT id FROM course_documents WHERE file_sha256 = %s AND extraction_status = 'done'` — deterministic เพราะ sha256 เป็น unique key ที่ pipeline ใช้ dedupe อยู่แล้ว |
| `run()` ใช้ `SystemExit` (B6) | worker ตรวจ `INGEST_DATABASE_URL` เองก่อนเรียก และ `except SystemExit` แปลงเป็น error ของงานนั้น ไม่ให้ฆ่า process ทั้งตัว |
| `run()` อ่าน env `EMBED_MODEL` เอง ค่า default คือ `nomic-embed-text` (768 มิติ) แต่ production ใช้ `bge-m3` (1024 มิติ) | worker ต้องส่ง `EMBED_MODEL=bge-m3` เข้ามาใน environment เสมอ **และ** ตรวจว่า `EMBED_DIM` ตรงกับคอลัมน์ `vector(1024)` ก่อนเริ่ม ไม่งั้น insert จะพังหลัง embed เสร็จ (เสียเวลาเป็นชั่วโมงฟรี) |
| `storage_path` จะถูกบันทึกเป็น path ใน staging | ยอมรับได้ — [document_store.py](backend/app/services/document_store.py) หาไฟล์ด้วย sha256 ไม่ใช่ path อยู่แล้ว แต่ **หลัง ingest สำเร็จต้องคัดลอกไฟล์ไป `documents/`** ไม่งั้น `/documents/{id}/pdf` จะเปิดไม่ได้ |

> ข้อสุดท้ายสำคัญ: `DOCUMENTS_DIR=/srv/documents` และ backend ทำดัชนี sha256 **ครั้งเดียวต่อ
> โปรเซส** ([document_store.py:73-76](backend/app/services/document_store.py:73)) เอกสารใหม่จึงจะ
> เปิดดูไม่ได้จนกว่าจะ restart backend — ต้องเขียนไว้ใน runbook ว่าเป็นขั้นตอนสุดท้าย

### map `course_code` / `course_id` อย่างไร

`get_or_create_course()` ([ingest.py:104](pipeline/ingest.py:104)) หา course จาก `code` ก่อน
ถ้าไม่เจอจะสร้างใหม่ — แปลว่า **ส่ง `course_code` ผิดจะสร้างหลักสูตรซ้ำขึ้นมาเงียบ ๆ**

กติกาที่เสนอ

| `match_confidence` | ทำอะไร |
|---|---|
| `high` | ใช้ `crawl_sources.course_code` ได้ แต่ยังต้องให้คนกดอนุมัติ |
| `medium` | หน้าจอ preselect ค่าที่จับคู่ได้ คนยืนยัน |
| `ambiguous` | **บังคับให้คนเลือกจาก `match_candidates`** ปุ่มอนุมัติปิดจนกว่าจะเลือก |
| `unknown` | คนต้องพิมพ์/เลือก `course_code` จากรายการ `courses` ที่มีจริง |

`course_code` ที่ส่งเข้า `run()` ต้อง**ยืนยันว่ามีอยู่จริงใน `courses` ก่อน**
ถ้าคนตั้งใจสร้างหลักสูตรใหม่ ต้องส่ง flag `create_new_course: true` มาอย่างชัดเจน
ไม่ใช่ปล่อยให้เกิดจากการพิมพ์ผิด

### update `crawl_sources` เป็น `ingested` และผูก `document_id`

worker ใช้ role `advisor_ingest` ซึ่งมี `UPDATE ON mko.crawl_sources` อยู่แล้ว

```sql
UPDATE mko.crawl_sources
   SET status = 'ingested', document_id = %(document_id)s
 WHERE id = %(id)s
   AND file_sha256 = %(sha)s;   -- กันกรณีไฟล์เปลี่ยนระหว่างทำงาน
```

---

## 6. Database / status transitions

### migration 004 — เพิ่มเท่านั้น ไม่ ALTER ไม่ DROP

```sql
-- 004_crawl_decisions.sql
BEGIN;

CREATE TABLE IF NOT EXISTS mko.crawl_decisions (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    crawl_source_id  UUID NOT NULL REFERENCES mko.crawl_sources(id) ON DELETE CASCADE,

    -- ผูกกับเนื้อไฟล์ ไม่ใช่ผูกกับลิงก์ — ไฟล์เปลี่ยนแล้วการอนุมัติเดิมต้องไม่ใช้ต่อ
    -- หลักเดียวกับ mko.review_decisions ใน 002 ที่ผูกกับ (เอกสาร, field, ค่า)
    file_sha256      TEXT NOT NULL CHECK (file_sha256 ~ '^[0-9a-f]{64}$'),

    decision         TEXT NOT NULL CHECK (decision IN ('approve', 'ignore')),
    decided_by       TEXT NOT NULL CHECK (length(btrim(decided_by)) > 0),
    decided_at       TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    note             TEXT,

    -- หลักสูตรที่คนยืนยัน ไม่ใช่ที่ระบบเดา
    course_code      TEXT,
    course_title     TEXT,

    -- ผลการนำเข้า (worker เขียน)
    ingest_started_at  TIMESTAMPTZ,
    ingest_finished_at TIMESTAMPTZ,
    ingest_error       TEXT,
    document_id        UUID REFERENCES public.course_documents(id) ON DELETE SET NULL,

    -- ถอนการตัดสินใจด้วยการ supersede ไม่ใช่ลบ
    superseded_at    TIMESTAMPTZ,
    superseded_by    TEXT,

    CONSTRAINT crawl_decisions_supersede_complete
        CHECK ((superseded_at IS NULL) = (superseded_by IS NULL)),
    -- approve ต้องระบุหลักสูตร ส่วน ignore ไม่ต้อง
    CONSTRAINT crawl_decisions_approve_has_course
        CHECK (decision <> 'approve' OR course_code IS NOT NULL),
    CONSTRAINT crawl_decisions_finished_after_started
        CHECK (ingest_finished_at IS NULL OR ingest_started_at IS NOT NULL)
);

-- หนึ่งไฟล์มีการตัดสินใจที่ยังใช้อยู่ได้ครั้งเดียว — กันสองคนกดพร้อมกันที่ระดับฐานข้อมูล
CREATE UNIQUE INDEX IF NOT EXISTS uq_crawl_decisions_active
    ON mko.crawl_decisions (crawl_source_id, file_sha256) WHERE superseded_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_crawl_decisions_todo
    ON mko.crawl_decisions (decided_at)
    WHERE superseded_at IS NULL AND decision = 'approve' AND ingest_finished_at IS NULL;

-- คิวของคนตรวจ: แถวที่ยังไม่มีการตัดสินใจที่ใช้อยู่ · ไม่มี staging_path
CREATE OR REPLACE VIEW mko.v_crawl_queue AS
SELECT s.id, s.source_url, s.page_url, s.page_title, s.link_text,
       s.course_code, s.course_label, s.match_confidence, s.match_score, s.match_candidates,
       s.needs_review, s.review_reason, s.status,
       s.content_length, s.file_sha256, s.previous_sha256,
       (s.staging_path IS NOT NULL) AS has_staged_file,
       s.last_checked_at, s.first_seen_at
  FROM mko.crawl_sources s
 WHERE (s.status IN ('new', 'changed', 'downloaded', 'error') OR s.needs_review)
   AND NOT EXISTS (
        SELECT 1 FROM mko.crawl_decisions d
         WHERE d.crawl_source_id = s.id
           AND d.file_sha256 = s.file_sha256
           AND d.superseded_at IS NULL)
 ORDER BY s.needs_review DESC, s.last_checked_at DESC NULLS LAST;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'advisor_api') THEN
        GRANT SELECT ON mko.v_crawl_queue TO advisor_api;
        GRANT SELECT, INSERT ON mko.crawl_decisions TO advisor_api;
        -- ถอนการตัดสินใจได้ แต่แก้เนื้อการตัดสินใจเดิมไม่ได้ และแตะผลการ ingest ไม่ได้
        GRANT UPDATE (superseded_at, superseded_by) ON mko.crawl_decisions TO advisor_api;
        -- อ่านชื่อหลักสูตรเพื่อยืนยัน course_code — มีสิทธิ์อยู่แล้วจาก 20-roles.sh
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'advisor_ingest') THEN
        GRANT SELECT, INSERT, UPDATE ON mko.crawl_decisions TO advisor_ingest;
        GRANT SELECT ON mko.v_crawl_queue TO advisor_ingest;
    END IF;
END;
$$;

INSERT INTO mko.schema_migrations (version) VALUES ('004_crawl_decisions')
    ON CONFLICT (version) DO NOTHING;

COMMIT;
```

**สิ่งที่ 004 ไม่ทำ** ไม่ `ALTER` ตารางเดิม · ไม่แก้ `v_crawl_pending` · ไม่แก้ CHECK ของ `status`
(ค่า `ingested`/`ignored` มีอยู่ใน enum เดิมแล้ว) · ไม่ให้ `DELETE` แก่ใคร · ไม่แตะ `public`

### ตารางการเปลี่ยนสถานะ

| จาก | เหตุการณ์ | ไป | ใครทำ |
|---|---|---|---|
| — | crawler พบลิงก์ครั้งแรก | `new` | crawler |
| any | HEAD/sha เหมือนเดิม | `unchanged` | crawler |
| any | sha ตรงกับเอกสารในคลัง | `unchanged` + `document_id` | crawler |
| any | sha ต่างจากที่เคยบันทึก | `changed` + staging | crawler |
| — | ไฟล์ใหม่ไม่มีในคลัง | `downloaded` + staging | crawler |
| any | ดึงไม่สำเร็จ | `error` + `error_count+1` | crawler |
| `downloaded`/`changed` | **คนกดอนุมัติ** | สถานะ **ไม่เปลี่ยน** · เพิ่มแถว `crawl_decisions(approve)` | backend |
| `downloaded`/`changed` | **คนกดไม่เกี่ยวข้อง** | สถานะ **ไม่เปลี่ยน** · เพิ่มแถว `crawl_decisions(ignore)` | backend |
| `downloaded`/`changed` | worker ingest สำเร็จ | `ingested` + `document_id` | worker |
| `downloaded`/`changed` | worker ingest ล้มเหลว | สถานะ **ไม่เปลี่ยน** · `crawl_decisions.ingest_error` | worker |
| `ingested` | crawler รอบถัดไปเจอ sha เดิม | `unchanged` (ปกติ ไม่ใช่ปัญหา) | crawler |

จุดสำคัญ: **backend ไม่เปลี่ยน `status` เลย** การกดอนุมัติไม่ได้ทำให้ไฟล์เดินหน้า
มันแค่บันทึกว่าคนอนุญาตแล้ว ไฟล์เดินหน้าเมื่อ worker ทำงานสำเร็จเท่านั้น

---

## 7. Security considerations

### 7.1 Admin authorization

| เรื่อง | ที่เสนอ |
|---|---|
| ทุก endpoint | `dependencies=[Depends(require_admin)]` — ใช้ [deps.py:50](backend/app/api/deps.py:50) ที่มีอยู่ |
| ใครเป็น admin | ต้อง `UPDATE users SET is_admin = true WHERE email = …` หนึ่งคน — **เป็นการเปลี่ยนข้อมูล production ต้องขออนุมัติแยก** |
| `decided_by` | เอาจาก `user.email` ฝั่งเซิร์ฟเวอร์ **ห้ามรับจาก request body** |
| rate limit | ใส่ `rate_limiter` (ต่อบัญชี) ไม่ใช่ `web_rate_limiter` (ต่อ IP) |
| audit | `crawl_decisions` เป็น append-only + ไม่มีสิทธิ์ `DELETE` ประวัติลบไม่ได้ |

> ข้อสังเกต: ถ้า `/register` ยังเปิดอยู่ ใคร ๆ ก็สมัครได้ แต่ `is_admin` default เป็น `false`
> ([models/user.py:19](backend/app/models/user.py:19)) จึงเข้าหน้านี้ไม่ได้ — ยอมรับได้
> แต่ควรตรวจว่ามีบัญชีไหน `is_admin = true` อยู่แล้วโดยไม่ตั้งใจ

### 7.2 Path traversal ของ staging file

**ไม่รับ path จากผู้ใช้เลยแม้จุดเดียว** ผู้ใช้ส่งมาได้แค่ `crawl_source_id` (UUID)
คัดลอกกติกาจาก [document_store.py](backend/app/services/document_store.py) ทั้งชุด

```
1. อ่าน staging_path จากฐานข้อมูล (ไม่ใช่จาก request)
2. Path(staging_path).resolve()
3. ต้อง resolved.is_relative_to(STAGING_DIR.resolve())   ← กัน symlink และ ../
4. ต้อง sha256_of(resolved) == file_sha256 ในฐานข้อมูล
5. ต้องเปิดอ่าน 5 ไบต์แรกได้เป็น b"%PDF-"
6. ผิดข้อใดข้อหนึ่ง → 404 ข้อความเดียวกันทุกกรณี · รายละเอียดอยู่ใน log เท่านั้น
```

ข้อ 4 สำคัญเป็นพิเศษ: ไฟล์ใน staging ถูกเขียนโดย crawler ซึ่งรันคนละ process
ถ้าไฟล์ถูกสลับหลัง crawl ระบบต้องไม่ส่งของที่ไม่ได้ตรวจให้คนดูแลเห็นแล้วกดอนุมัติ

### 7.3 SSRF / URL validation

ปัจจุบัน ([B8](#1-ผลวิเคราะห์ระบบปัจจุบัน--อุปสรรคที่พบ))

- [discover.py:134](pipeline/crawl/discover.py:134) กรอง `urlparse(link).netloc != allow_host` — ดีแล้ว
- แต่ [http.py:54](pipeline/crawl/http.py:54) ตั้ง `follow_redirects=True` **โดยไม่ตรวจ host ปลายทาง**
  redirect ออกนอก `sci.pnru.ac.th` จะถูกตามไปและเนื้อไฟล์ถูกเก็บลง staging

ที่เสนอเพิ่มใน Phase 3

```python
ALLOWED_HOSTS = {"sci.pnru.ac.th"}
ALLOWED_SCHEMES = {"http", "https"}

# ก่อนยิง
assert urlparse(url).scheme in ALLOWED_SCHEMES
assert urlparse(url).netloc in ALLOWED_HOSTS
# หลังได้ response — host ปลายทางหลังตาม redirect ต้องยังอยู่ในรายการ
if urlparse(str(resp.url)).netloc not in ALLOWED_HOSTS:
    → status='error', last_error='redirect ออกนอกโดเมนที่อนุญาต', ไม่เขียนไฟล์
```

**Admin ไม่มีช่องกรอก URL เอง** ระบบดึงไฟล์จาก URL ที่ crawler พบเท่านั้น
ถ้าอนาคตอยากให้เพิ่ม URL เองได้ ต้องออกแบบใหม่ทั้งชุด — ไม่อยู่ใน Phase 3

### 7.4 PDF / content validation

| ด่าน | ตรวจอะไร | ที่ไหน |
|---|---|---|
| ตอนโหลด | `content-type` เป็น `application/pdf` หรือขึ้นต้นด้วย `%PDF-` | crawler ก่อนเขียน staging |
| ตอนโหลด | ขนาด ≤ `max_pdf_size_mb` (50 MB) | crawler |
| ตอนโหลด | ขนาด ≥ `MIN_PLAUSIBLE_BYTES` (200 KB) → ขึ้นเป็นเหตุผลให้คนดู | มีอยู่แล้ว [sync.py:185](pipeline/crawl/sync.py:185) |
| ตอนเปิดดู | `%PDF-` + sha256 ตรง | backend |
| ตอน ingest | `%PDF-` + sha256 ตรง + `fitz.open()` สำเร็จ + `page_count > 0` | worker ก่อนเรียก `run()` |

ไม่แตะเนื้อ PDF ด้วยวิธีอื่น ไม่รัน JavaScript ใน PDF ไม่แปลงเป็นภาพ — `pymupdf` อ่านข้อความเท่านั้น

### 7.5 File size limit

**ปัจจุบันไม่มีเลย** [sync.py:151](pipeline/crawl/sync.py:151) ใช้ `resp.content` ซึ่งอ่านทั้งไฟล์
เข้าหน่วยความจำ บนเครื่อง Oracle Always Free (ARM, RAM จำกัด) ไฟล์ใหญ่ผิดปกติทำให้ process ตาย

ที่เสนอ: ใช้ `client.stream()` อ่านทีละก้อน นับไบต์ไปด้วย เกิน 50 MB ให้หยุดและบันทึก
`status='error'` โดยไม่เขียนไฟล์ — เป็นการแก้ `pipeline/crawl/http.py` และ `sync.py`
ซึ่งต้องขออนุมัติแยกเพราะแตะโค้ด Phase 2

### 7.6 Concurrent approval

| สถานการณ์ | กลไก |
|---|---|
| สอง admin กดอนุมัติแถวเดียวกันพร้อมกัน | partial unique index → ตัวที่สองได้ `23505` → `409` |
| worker สองตัวรันพร้อมกัน | `SELECT … FOR UPDATE SKIP LOCKED` บน `crawl_decisions` |
| crawler รันพร้อม worker | คนละตาราง · `UPDATE … AND file_sha256 = %s` กันเขียนทับของที่เปลี่ยนไปแล้ว |
| admin อนุมัติตอน crawler กำลังเขียนไฟล์ใหม่ทับ | decision ผูกกับ `file_sha256` เก่า → ไม่ตรงกับแถวปัจจุบัน → worker ข้ามและแถวกลับเข้าคิว |

### 7.7 Database permissions

| role | `crawl_sources` | `crawl_decisions` | `course_*` |
|---|---|---|---|
| `advisor_api` (backend) | ไม่มีสิทธิ์บนตารางจริง · อ่านผ่าน view | `SELECT, INSERT` + `UPDATE (superseded_at, superseded_by)` | `SELECT` เท่านั้น (เดิม) |
| `advisor_ingest` (crawler + worker) | `SELECT, INSERT, UPDATE` (เดิม) | `SELECT, INSERT, UPDATE` | `SELECT, INSERT, UPDATE` + `DELETE` เฉพาะ `course_chunks` (เดิม) |
| ทั้งคู่ | ไม่มี `DELETE` บน crawl · ไม่มี DDL | | |

นี่คือหัวใจของข้อ **"ห้าม client/frontend เรียก ingestion โดยตรง"**: backend เขียน
`course_documents`/`course_chunks` ไม่ได้ และไม่มี `pymupdf` ในอิมเมจ แม้มีคนแก้โค้ด backend
ให้เรียก ingest มันก็ทำไม่ได้ — ห้ามที่สองชั้นไม่ใช่ชั้นเดียว

### 7.8 อื่น ๆ

- ไม่ log `source_url` พร้อม token หรือข้อมูลผู้ใช้ · log `crawl_source_id` กับ sha256 เท่านั้น
- ไม่ส่ง `staging_path`, `last_error`, `http_etag` ออกนอกเซิร์ฟเวอร์
- `staging` mount เข้า backend เป็น **`:ro`** เหมือน `documents` ([prod:86](docker-compose.prod.yml:86))
- `note`/`reason` ที่คนพิมพ์: เก็บดิบใน DB (parameterized) แต่หน้าเว็บ render เป็นข้อความ
  ไม่ใช่ HTML — React escape ให้อยู่แล้ว

---

## 8. Failure / rollback handling

| จุดที่พัง | เกิดอะไร | กู้อย่างไร |
|---|---|---|
| crawler ดึงไฟล์ไม่ได้ | `status='error'`, `error_count+1`, `needs_review=true` | รอบถัดไปลองใหม่เอง · คนเห็นใน UI |
| ไฟล์ใน staging หาย/ถูกแก้ | worker ตรวจ sha256 ไม่ผ่าน → `ingest_error`, ไม่เรียก `run()` | crawl ใหม่เพื่อโหลดไฟล์ลง staging อีกครั้ง |
| `extract` พัง (PDF เสีย) | `fitz.open()` โยน exception ก่อน embed → `ingest_error` | คนดูใน UI แล้วกด Ignore หรือแก้ที่ต้นทาง |
| `embed` พัง (Ollama ล่ม) | `run()` โยน exception **ก่อน** เขียน DB ([ingest.py:196](pipeline/ingest.py:196) อยู่ก่อน `psycopg.connect`) → ไม่มีข้อมูลค้างใน DB | รัน worker ใหม่ · ไฟล์ยังอยู่ · decision ยังอยู่ |
| `insert_chunks` พัง | pipeline เดิม rollback transaction B แล้วเขียน `extraction_status='failed'` ใน transaction C ([ingest.py:214-223](pipeline/ingest.py:214)) | รัน worker ใหม่ — `insert_document` ยึดแถวที่ยังไม่ `done` มาทำต่อ ([ingest.py:129](pipeline/ingest.py:129)) |
| worker ตายกลางทาง | `ingest_started_at` มีค่า แต่ `ingest_finished_at` ว่าง | worker รอบถัดไปหยิบงานที่ค้างเกิน N ชั่วโมงมาทำใหม่ · `already_ingested()` กันงานซ้ำ |
| คนอนุมัติผิด **ก่อน** ingest | `POST /undo` → `superseded_at` → แถวกลับเข้าคิว | ไม่มีผลข้างเคียงใด ๆ |
| คนอนุมัติผิด **หลัง** ingest แล้ว | **undo ไม่ย้อนคลังความรู้** | ต้องลบ `course_documents`/`course_chunks` ด้วยมือ ซึ่ง `advisor_api` และ `advisor_ingest` ทำไม่ได้ทั้งคู่ — ต้องใช้ superuser และควรมีขั้นตอนแยกใน Phase 4 |

**ข้อจำกัดที่ยอมรับอย่างชัดเจน**: Phase 3 ไม่มีการถอนการนำเข้า (un-ingest) การกดอนุมัติเป็น
การตัดสินใจที่ย้อนไม่ได้ในทางปฏิบัติ จึงต้องให้คนเปิด PDF ดูก่อนเสมอ และ UI ต้องเขียนไว้ตรง ๆ

---

## 9. ไฟล์ที่จะต้องเพิ่ม / แก้

### เพิ่มใหม่

| ไฟล์ | หน้าที่ | ประมาณ |
|---|---|---|
| `db/migrations/004_crawl_decisions.sql` | ตาราง + view + grants (เพิ่มเท่านั้น) | ~110 บรรทัด |
| `backend/app/api/routes/crawl_review.py` | 6 endpoints ทั้งหมดใช้ `require_admin` | ~220 |
| `backend/app/services/crawl_review.py` | query `v_crawl_queue` · เขียน `crawl_decisions` · ยืนยัน `course_code` | ~180 |
| `backend/app/services/staging_store.py` | หาไฟล์ staging อย่างปลอดภัย (แบบเดียวกับ `document_store.py`) | ~120 |
| `backend/app/schemas/crawl_review.py` | pydantic ของ request/response | ~70 |
| `pipeline/crawl/approve.py` | worker — หา decision · ตรวจไฟล์ · เรียก `ingest.run()` · อัปเดตสถานะ | ~260 |
| `frontend/app/crawl-review/page.tsx` | หน้าคิวตรวจ | ~320 |
| `frontend/lib/crawl-review.ts` | ตัวเรียก API + types | ~90 |
| `ingest/Dockerfile` | อิมเมจของ worker (pipeline deps + repo) | ~35 |
| `eval/crawl_approval_check.py` | เทสต์ (ดูหัวข้อ 10) | ~400 |
| `docs/AUTOMATED_INGESTION_PHASE3_REPORT.md` | รายงานหลัง implement | — |

### แก้ของเดิม

| ไฟล์ | แก้อะไร | ความเสี่ยง |
|---|---|---|
| `backend/app/main.py` | `include_router(crawl_review.router)` 1 บรรทัด | ต่ำ |
| `backend/app/core/config.py` | เพิ่ม `crawl_staging_dir: str = Field("", alias="CRAWL_STAGING_DIR")` — ค่าว่าง = ปิดฟีเจอร์ แบบเดียวกับ `documents_dir` | ต่ำ |
| `docker-compose.prod.yml` | เพิ่ม service `ingest-worker` (profile) + mount `./staging:/srv/staging:ro` เข้า backend | กลาง — แตะไฟล์ที่ใช้ deploy จริง |
| `.env.example` | เพิ่ม `CRAWL_DATABASE_URL`, `CRAWL_STAGING_DIR` | ต่ำ |
| `frontend/components/site-nav.tsx` | ลิงก์ไปหน้าตรวจ | ต่ำ |
| `pipeline/crawl/http.py` | จำกัดขนาด · ตรวจ host หลัง redirect · ตรวจ `%PDF-` | **กลาง-สูง — แตะโค้ด Phase 2 ที่ทดสอบแล้ว ต้องขออนุมัติแยก** |
| `pipeline/crawl/sync.py` | ใช้ `stream()` แทน `resp.content` | **กลาง-สูง — เหมือนข้างบน** |

### ที่ **ไม่** แก้

`pipeline/ingest.py` · `pipeline/extract_pdf.py` · `pipeline/chunker.py` · `pipeline/embed.py` ·
`pipeline/crawl/state.py` · `pipeline/crawl/inventory.py` · `pipeline/crawl/discover.py` ·
`db/migrations/001-003` · `db/schema.sql` · `db/20-roles.sh` · `Caddyfile` ·
`webapi/*` · Supabase · RAG / Gemini / embedding logic

> `Caddyfile` ไม่ต้องแก้เพราะเลือก prefix `/crawl-review` ที่ตกลง `handle /api/*` เดิมอยู่แล้ว
> ถ้าเปลี่ยนใจไปใช้ `/api/admin/crawl/*` จะต้องเพิ่ม `handle` ก่อนบรรทัด 37 ซึ่งเสี่ยงกระทบ
> เส้นทางของเพื่อน — ไม่แนะนำ

---

## 10. Production deployment plan

### เทียบสามทางเลือก

#### ทางเลือก 1 — `ingest-worker` เป็นคอนเทนเนอร์แยก ✅ **เสนอทางนี้**

```yaml
  ingest-worker:
    build: { context: ., dockerfile: ingest/Dockerfile }
    profiles: ["ingest"]          # ไม่ start พร้อม stack ปกติ
    depends_on: [postgres, ollama]
    environment:
      INGEST_DATABASE_URL: postgresql://advisor_ingest:${ADVISOR_INGEST_PASSWORD}@postgres:5432/course_advisor
      OLLAMA_BASE_URL: http://ollama:11434
      EMBED_MODEL: ${EMBED_MODEL:-bge-m3}
      EMBED_DIM: ${EMBED_DIM:-1024}
      CRAWL_STAGING_DIR: /srv/staging
    volumes:
      - ./staging:/srv/staging          # เขียนได้ (crawler เขียน worker อ่าน)
      - ./documents:/srv/documents      # เขียนได้ — คัดลอกไฟล์เข้าคลังหลัง ingest สำเร็จ
```

รันเมื่อมีของรออนุมัติ

```bash
docker compose -f docker-compose.prod.yml run --rm ingest-worker --once
```

| ข้อดี | ข้อเสีย |
|---|---|
| backend ไม่ต้องเพิ่ม dependency และไม่ได้สิทธิ์เขียนคลัง | มีอิมเมจเพิ่มอีกหนึ่ง (~+150 MB จาก pymupdf) |
| `profiles` ทำให้ไม่มีบริการรันค้างเพิ่ม ไม่กิน RAM ตอนไม่ใช้ | ต้องมีคนสั่งรัน หรือมี trigger |
| embedding กินเวลาเป็นชั่วโมงได้โดยไม่กระทบเว็บ | |
| งานพังก็แค่คอนเทนเนอร์นั้นตาย เว็บไม่กระเทือน | |
| เป็นที่เดียวกับที่ควรรัน `pipeline.crawl.sync` ด้วย — รวมงาน pipeline ไว้ที่เดียว | |

#### ทางเลือก 2 — เพิ่ม dependency เข้า backend + `BackgroundTasks`

| ข้อดี | ข้อเสีย |
|---|---|
| ไม่มีอิมเมจใหม่ · delta แค่ `pymupdf` + `tqdm` | **backend ต้องได้สิทธิ์เขียน `course_documents`/`course_chunks`** = ขยายผิวการโจมตีของบริการที่เปิดสู่อินเทอร์เน็ต |
| กดอนุมัติแล้วเริ่มทันที | uvicorn restart / deploy ระหว่างทาง = งานหายกลางคัน ไม่มีใครรู้ |
| | embedding 300 chunk บน ARM CPU กิน worker ของเว็บไปเป็นชั่วโมง ผู้ใช้จริงได้รับผลกระทบ |
| | mount `documents` เป็น `:rw` ทำลายคุณสมบัติ "backend ไม่เขียนโฟลเดอร์นี้" |
| | ขัดข้อ "ห้าม client/frontend เรียก ingestion โดยตรง" ในทางปฏิบัติ |

**ไม่แนะนำ**

#### ทางเลือก 3 — รันจากเครื่อง dev เหมือนทุกวันนี้ (ทำแต่ UI อนุมัติ)

| ข้อดี | ข้อเสีย |
|---|---|
| ไม่แตะ production architecture เลย · ทำ Phase 3 ได้เร็วที่สุด | ต้องมีคนเปิดเครื่อง dev · staging อยู่คนละเครื่องกับ backend จึงเปิด PDF จากหน้าเว็บไม่ได้ |
| ทดสอบง่าย | ไม่ใช่ automated pipeline ตามเป้าหมาย |

ใช้เป็น **ขั้นกลาง** ได้ ถ้าต้องการให้ UI อนุมัติใช้งานได้ก่อนโดยไม่แตะ compose
แต่ต้องยอมรับว่าเปิด PDF ในหน้าเว็บไม่ได้จนกว่า staging จะย้ายขึ้นเซิร์ฟเวอร์

### ทำไมเลือกทางเลือก 1

1. **ผิวการโจมตีไม่โต** — บริการที่รับคำขอจากอินเทอร์เน็ตยังเขียนคลังความรู้ไม่ได้เหมือนเดิม
2. **ไม่มีบริการรันค้างเพิ่ม** — `profiles` ทำให้ `up -d` ปกติไม่เปลี่ยนพฤติกรรมเลย
3. **ดูแลง่าย** — pipeline ทั้งหมด (crawl + ingest) รันจากที่เดียวด้วยอิมเมจเดียว
4. **ไม่ต้องตั้ง cron** ตามข้อห้าม — เป็นการรันด้วยคำสั่งเดียวเมื่อมีของรอ

### ลำดับ deploy (เมื่อได้อนุมัติ implement)

```
ขั้น 0  สำรองฐานข้อมูล + จดอิมเมจปัจจุบันไว้เป็น rollback tag
ขั้น 1  รัน 004_crawl_decisions.sql (additive) แล้วตรวจ
          - tables 29 → 30 · views 7 → 8
          - courses/course_documents/course_chunks = 24/31/9039 ไม่เปลี่ยน
          - \dp mko.crawl_decisions  ตรวจว่า advisor_api ไม่มี UPDATE ทั้งตาราง
ขั้น 2  ตั้ง admin หนึ่งบัญชี (UPDATE users SET is_admin = true)  ◄ ขออนุมัติแยก
ขั้น 3  build + deploy backend ใหม่ (มี /crawl-review) — ยังไม่ตั้ง CRAWL_STAGING_DIR
          → ฟีเจอร์ปิดอยู่ ตรวจว่าเว็บเดิมไม่กระเทือน
ขั้น 4  ย้าย staging ขึ้นเซิร์ฟเวอร์ · mount :ro เข้า backend · ตั้ง CRAWL_STAGING_DIR
          → ทดสอบ GET /crawl-review/pending และเปิด PDF
ขั้น 5  build ingest-worker · รัน --dry-run (ไม่ ingest จริง) ตรวจว่าหาไฟล์และตรวจ sha ผ่าน
ขั้น 6  ingest จริง 1 ไฟล์ · ตรวจ chunks เพิ่มขึ้นสมเหตุผล · ถามคำถามที่ต้องใช้เอกสารนั้น
ขั้น 7  restart backend เพื่อให้ดัชนี sha256 ของ document_store เห็นไฟล์ใหม่
ขั้น 8  เขียนรายงานผลจริง
```

**เกณฑ์หยุด**: ถ้าผลจริงต่างจากที่คาดในขั้นใดก็หยุดทันทีและรายงาน ห้ามแก้ production ต่อเอง

**หมายเหตุจากบทเรียนเดิม**: งานยาวบนเซิร์ฟเวอร์ต้องรันแบบ detach พร้อมเขียน log ลงไฟล์
(`nohup … python -u … > log 2>&1 &`) ไม่ pipe ผ่าน ssh · และการ deploy ต้อง build image ใหม่
การ `scp` แล้ว restart จะยังรันโค้ดเก่า ต้องตรวจในคอนเทนเนอร์เสมอ

---

## 11. Test plan

### `eval/crawl_approval_check.py` — ตามแบบ `eval/crawl_state_check.py`

ใช้ PostgreSQL จริงบนฐานข้อมูลทดสอบ · **ปฏิเสธรันถ้า `"course_advisor" in database_url`**
(กติกาเดียวกับ [crawl_state_check.py](eval/crawl_state_check.py)) · ไม่เรียก Ollama จริง (stub connector)

| กลุ่ม | ข้อที่ต้องผ่าน |
|---|---|
| **สิทธิ์** | `advisor_api` `INSERT crawl_decisions` ได้ · `UPDATE crawl_sources` **ไม่ได้** · `INSERT course_chunks` **ไม่ได้** · `DELETE crawl_decisions` **ไม่ได้** |
| **คิว** | แถว `downloaded` อยู่ในคิว · อนุมัติแล้วหายจากคิว · กด Ignore แล้วหายจากคิว · `undo` แล้วกลับเข้าคิว |
| **crawler เขียนทับไม่ได้** | อนุมัติ → รัน `upsert()` แบบรอบใหม่ → แถวยัง**ไม่**กลับเข้าคิว (ครอบ B3/B4 โดยตรง) |
| **ไฟล์เปลี่ยน** | อนุมัติด้วย sha A → crawler พบ sha B → แถวกลับเข้าคิว · worker ไม่ ingest ของที่อนุมัติไว้ด้วย sha A |
| **กดซ้ำ** | อนุมัติสองครั้งติด → ครั้งที่สอง `409` · สอง connection พร้อมกัน → ตัวเดียวสำเร็จ |
| **บังคับเลือกหลักสูตร** | `match_confidence='ambiguous'` + ไม่ส่ง `course_code` → `422`/`400` ไม่ใช่การเดา |
| **`course_code` ไม่มีจริง** | ส่ง code ที่ไม่มีใน `courses` โดยไม่ส่ง `create_new_course` → ปฏิเสธ ไม่สร้างหลักสูตรซ้ำ |
| **path traversal** | `staging_path` ชี้ออกนอก root (รวม symlink) → 404 ไม่ส่งไฟล์ |
| **sha ไม่ตรง** | แก้ไฟล์ใน staging 1 ไบต์ → เปิดดูได้ 404 · worker ไม่ ingest |
| **ไม่ใช่ PDF** | ไฟล์ขึ้นต้นด้วย `<html` → ปฏิเสธทั้งตอนเปิดดูและตอน ingest |
| **ขนาด** | ไฟล์ > `max_pdf_size_mb` → ปฏิเสธ |
| **ไม่รั่ว** | response ของทุก endpoint ไม่มีคำว่า `staging`, `/srv/`, `last_error`, `http_etag` |
| **authz** | ไม่มี token → 401 · token ของ user ที่ `is_admin=false` → 403 · refresh token → 401 |
| **worker ล้มเหลว** | `run()` โยน exception → `ingest_error` ถูกบันทึก · `status` ไม่กลายเป็น `ingested` · decision ไม่หาย |
| **worker สำเร็จ** | `status='ingested'` · `document_id` ผูกถูกแถว · `crawl_decisions.document_id` ตรงกัน |
| **รัน worker ซ้ำ** | งานที่ `ingest_finished_at` แล้วไม่ถูกหยิบอีก · `already_ingested()` ทำงาน |

### ทดสอบด้วยมือก่อน deploy

1. migration บนฐานข้อมูลทดสอบที่สร้างใหม่ (แบบเดียวกับที่ทำใน Phase 2 ด้วย `bootstrap_test.sql`)
2. เปิดหน้า `/crawl-review` ด้วยบัญชีที่ `is_admin=false` → ต้องเห็น 403 ไม่ใช่หน้าคิว
3. อนุมัติ 1 ไฟล์จริงบน staging ของ dev แล้วรัน worker `--dry-run`
4. ตรวจ `behaviour_check` **หลัง** ingest จริงเท่านั้น และตรวจว่า `corpus_version` เปลี่ยนเอง
   ทำให้แคชคำตอบเก่าหมดอายุ (ไม่ต้อง bump `_LOGIC_VERSION`)

### สิ่งที่ต้องวัดซ้ำ ไม่ใช่รันครั้งเดียว

ขั้นที่ LLM ตัดสิน (คำตอบหลัง ingest เอกสารใหม่) ต้องยิงหลายครั้งแล้วรายงานเป็นอัตรา
ไม่ใช่ผลรันเดียว — และคะแนนประเมินแกว่งได้เองราว 3 ข้อโดยไม่ได้แก้อะไร

---

## 12. สิ่งที่ reuse จากระบบเดิม

| ของเดิม | ใช้ทำอะไรใน Phase 3 | แก้ไหม |
|---|---|---|
| `pipeline/ingest.py::run()` | ตัว ingest ทั้งหมด | **ไม่แก้** |
| `pipeline/ingest.py::already_ingested()` | ด่านกันนำเข้าซ้ำที่ถูกที่สุด | ไม่แก้ |
| `pipeline/ingest_batch.py` | แบบอย่างการ import `run()` ข้ามโมดูล | ไม่แก้ |
| `pipeline/crawl/*` (Phase 2) | หา · ดาวน์โหลด · จับคู่ · บันทึกสถานะ | เฉพาะ `http.py`/`sync.py` เรื่องความปลอดภัย |
| `backend/app/api/deps.py::require_admin` | authz ทุก endpoint — **ผู้ใช้รายแรก** | ไม่แก้ |
| `backend/app/api/deps.py::rate_limiter` | จำกัดต่อบัญชี | ไม่แก้ |
| `backend/app/services/document_store.py` | แบบแผนหาไฟล์ปลอดภัย → `staging_store.py` | ไม่แก้ (คัดลอกกติกา) |
| `backend/app/api/routes/documents.py` | แบบแผนส่ง PDF inline + 404 ทุกกรณี | ไม่แก้ |
| `mko.review_decisions` (002) | แบบแผน append-only + `superseded_at` + partial unique index | ไม่แก้ |
| `mko.crawl_sources` (003) | สถานะไฟล์ทั้งหมด | ไม่แก้ |
| `public.set_updated_at()` | trigger ของตารางใหม่ (ถ้าต้องการ) | ไม่แก้ |
| `answer_cache.corpus_version` | เอกสารใหม่ทำให้แคชหมดอายุเอง ไม่ต้อง bump อะไร | ไม่แก้ |
| `frontend/app/match/page.tsx` | โครงหน้า client component | ไม่แก้ |
| `frontend/app/api/[...path]/route.ts` | proxy ที่ส่งต่อ `authorization` ให้แล้ว | ไม่แก้ |
| `eval/crawl_state_check.py` | โครงเทสต์ + กติกาห้ามรันบนฐานข้อมูลจริง | ไม่แก้ |
| `config.py::max_pdf_size_mb` | เพดานขนาดไฟล์ — ประกาศไว้แล้วยังไม่มีใครใช้ | ไม่แก้ |

---

## 13. คำถามที่ต้องตอบก่อน implement

| # | คำถาม | ทางเลือก | ที่แนะนำ |
|---|---|---|---|
| 1 | ใครเป็น admin | สร้างบัญชีใหม่ / ตั้ง `is_admin` ให้บัญชีที่มี | บัญชีใหม่แยกจากบัญชีทดสอบ |
| 2 | staging เก็บไว้กี่วัน | ลบเมื่อ ingest สำเร็จ / เก็บ N วัน / เก็บถาวร | เก็บ 30 วันหลัง ingest แล้วลบด้วยมือ — Phase 3 ไม่ลบอัตโนมัติ |
| 3 | ใครสั่งรัน worker | คนสั่งด้วยมือ / trigger จาก backend / timer | คนสั่งด้วยมือใน Phase 3 (timer ต้องขออนุมัติแยกเพราะเข้าข้อห้าม cron) |
| 4 | แจ้งเตือนเมื่อมีของรอตรวจ | ไม่แจ้ง / อีเมล / ตัวเลขบนหน้าเว็บ | ตัวเลขบนหน้าเว็บก่อน ไม่เพิ่มช่องทางใหม่ |
| 5 | จะแก้ `http.py`/`sync.py` เรื่องขนาดและ redirect ในรอบนี้ไหม | แก้พร้อม Phase 3 / แยกเป็นงานย่อยก่อน | **แยกทำก่อน** เป็น commit เล็กที่มีเทสต์ของตัวเอง เพราะแตะโค้ดที่ผ่านการทดสอบแล้ว |
| 6 | อนุญาตให้ Approve สร้างหลักสูตรใหม่ได้ไหม | ได้ด้วย flag / ไม่ได้เลย | ได้ด้วย flag ที่ต้องส่งมาชัดเจน กันหลักสูตรซ้ำจากพิมพ์ผิด |

---

## 14. สรุปสิ่งที่ยังไม่ได้ทำในรอบนี้

- ไม่แก้ source code แม้บรรทัดเดียว
- ไม่แก้ schema · ไม่รัน migration
- ไม่ deploy · ไม่ restart · ไม่ตั้ง cron/systemd
- ไม่ ingest PDF · ไม่สร้าง embedding
- ไม่แตะ Supabase
- ไม่ query production (การอ่าน `courses` จาก production ถูกปฏิเสธ — จำนวน 24/31/9039
  ในเอกสารนี้อ้างจากรายงาน Phase 2 deploy ที่ตรวจไว้เมื่อ 28 ก.ย. 2569)

**หยุดรออนุมัติก่อน implement Phase 3**
