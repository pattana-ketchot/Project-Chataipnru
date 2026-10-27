# Phase 3D ขั้นที่ 1 — Pre-Deploy Audit และแผน Deploy (ตรวจอย่างเดียว ไม่ deploy)

| | |
|---|---|
| ทำเมื่อ | 28 กันยายน 2569 08:44–09:05 (+07) · เซิร์ฟเวอร์รายงานเวลา `2026-09-28 08:48:23+07` |
| workspace ที่ใช้ทำงาน | `D:/workspace/course-advisor-system-mko2` (git worktree บนเครื่องพัฒนา — **ไม่ใช่ production**) |
| ช่องทางตรวจ production | SSH + `docker exec` แบบอ่านอย่างเดียว · query ทุกตัวอยู่ใน `BEGIN TRANSACTION READ ONLY` พร้อม `statement_timeout`/`lock_timeout` |
| ขอบเขต | ตรวจและวางแผนเท่านั้น **ไม่มีการเปลี่ยน production** |

---

## 1. Executive readiness status

# NO-GO

การตรวจ**เสร็จสมบูรณ์** และพร้อมให้คนอ่าน แต่**ยังไม่พร้อม deploy** เพราะมี blocker 7 ข้อ
ที่ต้องปลดก่อน และ 1 ข้อที่พิสูจน์ไม่ได้ (`UNKNOWN`)

> สถานะนี้ไม่ใช่การอนุมัติ deploy และไม่ใช่การอนุมัติให้รันคำสั่งใดในแผนหัวข้อ 16

| # | Blocker (ย่อ) | หลักฐาน |
|---|---|---|
| B1 | **ไม่มีบัญชีผู้ดูแลเลย** — `admin_total = 0` | §5 |
| B2 | **ไม่มีงานที่อนุมัติได้เลย** — `crawl_sources` ทั้ง 12 แถวเป็น `unchanged` และ `staging_path` ว่างทั้งหมด | §4, §12 |
| B3 | **ไม่มีโฟลเดอร์ staging บนเซิร์ฟเวอร์ และ `CRAWL_STAGING_DIR` ไม่ได้ตั้ง** | §6 |
| B4 | **อิมเมจ backend ไม่มี PyMuPDF** — worker รันด้วยอิมเมจที่มีอยู่ไม่ได้ | §7 |
| B5 | **อิมเมจ frontend ที่รันอยู่หายไปจาก image store แล้ว** — recreate แล้วย้อนไม่ได้ | §9 |
| B6 | **backup ฐานข้อมูลล่าสุดเก่า 11 วัน และไม่มีหลักฐานการทดสอบ restore** | §11 |
| B7 | **`DOCUMENTS_DIR` ถูก mount เข้า backend เป็น `:ro`** — worker ยังไม่มีทางเขียนไฟล์ถาวร | §6 |
| U1 | `UNKNOWN` — **อิมเมจ backend ไม่มี provenance label** จึงพิสูจน์ commit ที่ deploy อยู่จาก metadata ไม่ได้ | §2 |

### ⚠️ แก้ข้อความที่ผมเขียนผิดในรายงานเฟสก่อน

1. **`document_store` สร้าง index แบบ lazy ตอนมีคำขอแรก ไม่ใช่ตอนเริ่มโปรเซส**
   `backend/app/services/document_store.py:104-109` เป็น `if self._index is None: ... _build_index()`
   และ `backend/app/main.py` ไม่มีที่ใดเรียก `get_document_store()` ตอน lifespan (ค้นแล้วได้ 0)
   รายงาน Phase 3A/3B/3C เขียนว่า "index ตอนเริ่มโปรเซส" ซึ่ง**ไม่ถูก** ผลลัพธ์ที่ตามมาเหมือนกัน
   (ไฟล์ใหม่ไม่ปรากฏจนกว่าจะมีโปรเซสใหม่) แต่คำอธิบายกลไกผิด
2. **worker ต้องมี PyMuPDF** — รายงาน Phase 3C §2 บอกว่าต้องการเพียง `httpx` + `psycopg` + stdlib
   ซึ่ง**ไม่ครบ** เพราะ `pipeline/crawl/approve.py:66` import `pipeline.extract_pdf` ซึ่ง import `fitz`
   ที่ `pipeline/extract_pdf.py:20` ข้อสรุปในรายงานนั้นว่า "ใช้อิมเมจ backend ที่มีอยู่ได้" จึง**ผิด**

---

## 2. Verified current state

### 2.1 Repository (เครื่องพัฒนา)

| รายการ | ค่าที่ตรวจได้ | สถานะ |
|---|---|---|
| repository root | `D:/workspace/course-advisor-system-mko2` | VERIFIED |
| `git branch --show-current` | `mko-phase2` | VERIFIED |
| `git rev-parse HEAD` | `617110e975dccc94b5e67f77990e34a071ccf9a0` | **VERIFIED — ตรงกับ expected** |
| `git rev-list --parents -n 1 HEAD` | `617110e975… 0b86ef26976710dc3ad7aade86e55b183c821009` (parent 1 ตัว ไม่ใช่ merge) | VERIFIED |
| commit subject | `feat: add approved curriculum ingest worker` | VERIFIED — ตรงกับ expected |
| commit date | `2026-09-28 08:24:05 +0700` | VERIFIED |
| `git diff --name-status` | 0 รายการ | VERIFIED |
| `git diff --cached --name-status` | 0 รายการ | VERIFIED |
| untracked | 39 รายการ **ทั้งหมดอยู่ใน `docs/`** (รายงานของเฟสก่อน + รายงานฉบับนี้) | VERIFIED |

ไฟล์ใน commit `617110e` — **2 ไฟล์**

```
A  eval/crawl_ingest_worker_check.py
A  pipeline/crawl/approve.py
```

`pipeline/ingest.py` **ไม่อยู่ใน commit นี้** (นับได้ 0) และ commit ล่าสุดที่แตะไฟล์นั้นคือ
`38992b2` (2026-09-08) ซึ่งอยู่**ก่อน** Phase 1 · ช่วง `3aa0813..617110e` มี 0 commit ที่แตะไฟล์นี้ → **VERIFIED**

ไฟล์ Phase 3A/3B/3C ที่ตรวจว่าอยู่ใน tree ของ HEAD ครบ 11 ไฟล์ (`git cat-file -e`)

```
db/migrations/004_crawl_decisions.sql      backend/app/api/routes/crawl_review.py
backend/app/services/crawl_review.py       backend/app/services/staging_store.py
backend/app/schemas/crawl_review.py        frontend/app/crawl-review/page.tsx
frontend/lib/crawl-review.ts               frontend/test/crawl-review.test.tsx
pipeline/crawl/approve.py                  eval/crawl_ingest_worker_check.py
eval/crawl_approval_check.py
```

### 2.2 Remote

| รายการ | ค่า | สถานะ |
|---|---|---|
| `refs/remotes/origin/mko-phase2` (ref ในเครื่อง อาจเก่า) | `617110e975dccc94b5e67f77990e34a071ccf9a0` | VERIFIED |
| `git ls-remote origin refs/heads/mko-phase2` (**origin ปัจจุบันจริง ไม่ fetch**) | `617110e975dccc94b5e67f77990e34a071ccf9a0` | **VERIFIED — ไม่มี drift** |
| `git ls-remote origin refs/heads/main` | `b78b3f8bf895685874d9a52c66b45569072f0514` | VERIFIED |
| ahead/behind | ahead 0 / behind 0 | VERIFIED |
| remote URL ฝัง credential ไหม | scheme `https` · host `github.com` · ไม่มี `user@` ก่อน host (นับได้ 0) → **ไม่พิมพ์ URL เต็ม** | VERIFIED |

### 2.3 Production revision

| รายการ | ค่า | สถานะ |
|---|---|---|
| backend image | `sha256:d1d1ba713412d34753a…` · `RepoDigest course-advisor-system-backend@sha256:d1d1ba713412…e37145` · สร้าง `2026-09-23T23:53:40` | VERIFIED |
| backend provenance label | มี label 3 รายการ ทั้งหมดเป็น `com.docker.compose.*` — **ไม่มี `org.opencontainers.image.revision` หรือ label ที่บอก git commit** | **UNKNOWN (U1)** |
| Phase 3A อยู่ในคอนเทนเนอร์ไหม | `app/api/routes/crawl_review.py` **ไม่มี** · `app/services/staging_store.py` **ไม่มี** | VERIFIED — ยังไม่ deploy |
| routes ที่มีในคอนเทนเนอร์ | `auth, chat, compare, courses, documents, match, recommend, search, users, web_compat` (ไม่มี `crawl_review`) | VERIFIED |

หลักฐานทางอ้อมของ revision — เทียบ `sha256` ของไฟล์ในคอนเทนเนอร์กับ blob ใน git

| ไฟล์ | ในคอนเทนเนอร์ | blob ที่ `2cdab40` | blob ที่ HEAD | สรุป |
|---|---|---|---|---|
| `app/main.py` | `b10e84330fd1e3e0` | `b10e84330fd1e3e0` | `0565f831ce9efc27` | ตรงกับ `2cdab40` |
| `app/core/config.py` | `013e0bff9dbb8e7d` | `013e0bff9dbb8e7d` | `dd5719813fc1762e` | ตรงกับ `2cdab40` |
| `app/services/answer_cache.py` | `ad8539eee62b3ca1` | `ad8539eee62b3ca1` | เท่ากัน | ตรงกับ `2cdab40` |
| `app/services/query_expansion.py` | `df7dcbb875824dae` | `df7dcbb875824dae` | เท่ากัน | ตรงกับ `2cdab40` |

**ข้อสรุปที่พูดได้**: เนื้อโค้ด backend ที่รันอยู่ตรงกับเนื้อของไฟล์เหล่านี้ที่ `2cdab40`
และ**ไม่มีโค้ด Phase 3A/3B/3C เลย** · **ข้อสรุปที่พูดไม่ได้**: ไม่มีหลักฐานผูกอิมเมจกับ
commit id ใดอย่างแน่นอน เพราะไม่มี provenance label (U1)

---

## 3. Production topology

```
                         อินเทอร์เน็ต
                              │  :80 / :443
                    ┌─────────▼──────────────────────────────────┐
                    │  caddy:2-alpine  (course-advisor-system-caddy-1)
                    │  mount  ./Caddyfile → /etc/caddy/Caddyfile :ro
                    │         ./web      → /srv/web              :ro
                    └──┬────────────┬───────────────┬────────────┘
       ชื่อโดเมน        │            │               │  ทางเลข IP :80
   /api/chat ──────────┘            │               └────────────────► frontend:3000
   /api/sci-connect-news* ──────────┤                                  (Next.js)
   /api/admin/*  ───────────────────┤► webapi:3001  (Supabase ของทีมออกแบบ)
   /api/*  strip /api ──────────────┴► backend:8000 (FastAPI)
   ที่เหลือ  root /srv/web + try_files → index.html  (SPA ไฟล์นิ่ง)

  backend (FastAPI)   image sha256:d1d1ba713412…  uid 1000 (appuser)
      network course-advisor-system_default  ip 172.18.0.4  expose 8000
      mount /home/ubuntu/course-advisor-system/documents → /srv/documents  **ro**
      DOCUMENTS_DIR=/srv/documents · EMBED_MODEL=bge-m3 · EMBED_DIM=1024
      CRAWL_STAGING_DIR = ไม่ได้ตั้ง
        │
        ├──► postgres (pgvector/pgvector:pg16) ip 172.18.0.2 expose 5432
        └──► ollama (ollama/ollama:latest) expose 11434

  frontend  image sha256:ce65aad64305…  **ไม่มี tag และไม่อยู่ใน image store แล้ว**
  webapi    image sha256:1163e36361d9…  (ไม่เกี่ยวกับงานนี้)
  db-viewer adminer:latest  127.0.0.1:18081→8080 (ผูกกับ loopback เท่านั้น)

  worker ในอนาคต: ต้องอยู่ใน network course-advisor-system_default
      ต้องเห็น staging (ro ก็พอ) และ documents (**rw**) · ต้องมี PyMuPDF
```

พอร์ตที่เปิดออกนอกเครื่องมีเพียง caddy `0.0.0.0:80` และ `0.0.0.0:443`
ส่วน backend/frontend/postgres/ollama/webapi เป็น `expose` ภายในเท่านั้น · `db-viewer`
ผูกกับ `127.0.0.1` — **VERIFIED**

---

## 4. Migration 004 audit

### 4.1 สถานะปัจจุบัน

| ตรวจ | ผล | สถานะ |
|---|---|---|
| ledger `mko.schema_migrations` | `001_mko_structured` (2026-09-15 08:34:52+07) · `002_mko_review_publish` (2026-09-15 08:34:52+07) · `003_crawl_sources` (2026-09-28 01:56:01+07) | **VERIFIED — ไม่มี 004** |
| `to_regclass('mko.crawl_decisions')` | `f` (ไม่มี) | VERIFIED |
| `to_regclass('mko.v_crawl_queue')` | `f` (ไม่มี) | VERIFIED |
| index `uq_crawl_decisions_active` | `f` | VERIFIED |
| index `idx_crawl_decisions_todo` | `f` | VERIFIED |

→ **ไม่มี partial apply และไม่มี schema drift ของ 004** ตรวจทั้ง ledger และ catalog

### 4.2 วิเคราะห์ทุก statement (`db/migrations/004_crawl_decisions.sql`)

| บรรทัด | statement | ชนิด |
|---|---|---|
| 36 | `BEGIN;` | เปิด transaction เดียว |
| 38 | `CREATE TABLE IF NOT EXISTS mko.crawl_decisions (...)` | additive · ตารางใหม่ |
| 83 | `CREATE UNIQUE INDEX IF NOT EXISTS uq_crawl_decisions_active … WHERE superseded_at IS NULL` | additive · partial unique index บนตารางใหม่ |
| 87 | `CREATE INDEX IF NOT EXISTS idx_crawl_decisions_todo … (partial)` | additive |
| 91 | `CREATE INDEX IF NOT EXISTS idx_crawl_decisions_source` | additive |
| 103 | `CREATE OR REPLACE VIEW mko.v_crawl_queue AS …` | additive · วิวใหม่ (ยังไม่มีอยู่ จึงเป็น CREATE ไม่ใช่ REPLACE) |
| 132–147 | `DO $$ … GRANT … $$` | ให้สิทธิ์ 7 คำสั่ง (ดู §5) |
| 150 | `INSERT INTO mko.schema_migrations … ON CONFLICT (version) DO NOTHING` | เพิ่มแถว ledger |
| 153 | `COMMIT;` | ปิด transaction |

**การนับ pattern ที่เป็นอันตราย**

| pattern | จำนวน | อธิบาย |
|---|---|---|
| `DROP TABLE` / `DROP VIEW` / `DROP COLUMN` / `ALTER TABLE` / `TRUNCATE` / `DELETE FROM` / `REVOKE` / `CREATE EXTENSION` / `CONCURRENTLY` | **0 ทุกตัว** | ไม่มีคำสั่งทำลายและไม่ต้องการ extension ใหม่ |
| `DROP` (ทั้งไฟล์) | 1 | อยู่ในคอมเมนต์บรรทัด 7 เท่านั้น ไม่ใช่คำสั่ง |
| `UPDATE` | 2 | เป็น `GRANT UPDATE …` (บรรทัด 139, 144) **ไม่ใช่การแก้ข้อมูล** |
| `CASCADE` | 1 | `ON DELETE CASCADE` ของ FK บนคอลัมน์ในตาราง**ใหม่** (บรรทัด 40) ไม่ลบข้อมูลเดิม |
| `SET` | 1 | `ON DELETE SET NULL` ของ FK (บรรทัด 62) |

→ **additive จริง** ไม่มี default/backfill ที่เขียนข้อมูลเดิม ไม่มีการแปลงคอลัมน์

**Dependencies**: `gen_random_uuid()` ต้องมี `pgcrypto` — ตรวจแล้วว่าติดตั้งอยู่
(`pg_extension` = `citext, pgcrypto, plpgsql, vector`) · FK อ้าง `mko.crawl_sources(id)`
(มีจาก 003) และ `public.course_documents(id)` (มีอยู่เดิม) · ไม่ต้องการ `vector` ในตารางนี้

**Transaction boundary**: ทั้งไฟล์อยู่ใน transaction เดียว → ล้มเหลวกลางทางแล้ว rollback
ทั้งชุด ไม่มีสถานะครึ่ง ๆ

**Idempotency**: `IF NOT EXISTS` ทุกตัว · `CREATE OR REPLACE VIEW` · `ON CONFLICT DO NOTHING`
→ **รันซ้ำได้** แต่ GRANT จะถูกให้ซ้ำ (ไม่มีผลเสีย)

**Lock ที่คาดจาก SQL**

| คำสั่ง | lock ที่ต้องได้ | ผลต่อของเดิม |
|---|---|---|
| `CREATE TABLE … REFERENCES mko.crawl_sources / public.course_documents` | `ShareRowExclusiveLock` บนสองตารางที่ถูกอ้าง | **บล็อกการเขียน** สองตารางนั้นชั่วคราว ไม่บล็อกการอ่าน |
| `GRANT SELECT (cols) ON mko.crawl_sources` | **`AccessExclusiveLock` บน `mko.crawl_sources`** | บล็อกทั้งอ่านและเขียนตารางนั้นจนจบ transaction |
| `CREATE OR REPLACE VIEW` / index บนตารางใหม่ | lock บน object ใหม่เท่านั้น | ไม่กระทบของเดิม |

ระยะเวลาที่คาด: ตารางใหม่ว่าง index ว่าง จึงเป็นระดับมิลลิวินาที **แต่ถ้ามี crawler run
กำลังถือ lock บน `mko.crawl_sources` อยู่ migration จะรอ** → ต้องตั้ง `lock_timeout`
ตอน apply และไม่ apply พร้อมกับการรัน crawler

**Rollback implications**: ถ้ายังไม่มีข้อมูลใน `mko.crawl_decisions` การถอนทำได้ด้วย
`DROP VIEW mko.v_crawl_queue; DROP TABLE mko.crawl_decisions;` และลบแถว ledger
**แต่เมื่อมีการอนุมัติจริงแล้ว ตารางนั้นคือประวัติการตัดสินใจของคน** การ drop คือการทำลาย
ประวัติ · เพราะ 004 เป็น additive ล้วนและไม่แตะ schema เดิม **แนวที่เหมาะกว่าคือคง schema ไว้
แล้ว rollback แอปกลับไปเวอร์ชันก่อน** — แอปเก่าไม่รู้จัก `crawl_decisions` จึงไม่ได้รับผลใด
**ห้ามใช้ `DROP … CASCADE`** เพราะ FK จาก `crawl_decisions` ชี้ไป `course_documents`
ซึ่ง cascade จะลามไปโดนของที่ไม่เกี่ยว

### 4.3 จำนวน object ก่อน/หลัง

นับจาก `information_schema.tables` (ไม่รวม system catalog และไม่รวม object ของ extension)

| schema · ชนิด | ก่อน (ตรวจจริง) | 004 เพิ่ม | หลัง (คาด) |
|---|---|---|---|
| `mko` · BASE TABLE | **19** | +1 (`crawl_decisions`) | 20 |
| `mko` · VIEW | **7** | +1 (`v_crawl_queue`) | 8 |
| `public` · BASE TABLE | **10** | 0 | 10 |
| index บน `mko.crawl_decisions` | 0 (ไม่มีตาราง) | +4 (PK + 3) | 4 |

ชื่อ object ใน `mko` ก่อน apply (ตรวจจริง)

- BASE TABLE (19): `crawl_sources, credit_groups, curricula, document_pages, document_sections,
  evidence, extraction_runs, field_value_evidence, field_values, learning_outcomes, list_items,
  programs, publications, published_list_items, published_values, review_decisions,
  schema_migrations, shadow_answers, subjects`
- VIEW (7): `v_crawl_pending, v_live_list_items, v_live_publication, v_live_values,
  v_published_curricula, v_published_field_values, v_published_list_items`

### 4.4 ความเข้ากันได้กับแอปเก่าและใหม่

| กรณี | ผล |
|---|---|
| แอปเก่า (ที่รันอยู่) + schema ใหม่ | ปลอดภัย — แอปเก่าไม่อ้าง `crawl_decisions`/`v_crawl_queue` เลย และ 004 ไม่แก้ของเดิม |
| แอปใหม่ + schema เก่า (ยังไม่ apply 004) | **พัง** — `/crawl-review/*` จะ error เพราะ view/table ไม่มีและ `advisor_api` ไม่มีสิทธิ์ → **ต้อง apply 004 ก่อน deploy backend ใหม่** |
| crawler เดิม (Phase 2) + schema ใหม่ | ปลอดภัย — `pipeline/crawl/state.py` ไม่อ้าง object ของ 004 |

---

## 5. Auth / admin audit

### 5.1 Permission matrix (ตรวจจริงจาก `pg_roles` / `information_schema.role_table_grants` / `has_*_privilege`)

| | `advisor_api` | `advisor_ingest` |
|---|---|---|
| CONNECT `course_advisor` | ✅ | ✅ |
| USAGE `public` / `mko` | ✅ / ✅ | ✅ / ✅ |
| superuser / createrole / bypassrls | ❌ / ❌ / ❌ | ❌ / ❌ / ❌ |
| `public.users` | SELECT, INSERT, UPDATE | — |
| `public.courses` | SELECT | SELECT, INSERT, UPDATE |
| `public.course_documents` | SELECT | SELECT, INSERT, UPDATE |
| `public.course_chunks` | SELECT | SELECT, INSERT, UPDATE, **DELETE** |
| `mko.crawl_sources` | **ไม่มีสิทธิ์ใดเลย** | SELECT, INSERT, UPDATE (ไม่มี DELETE) |
| `mko.v_crawl_pending` | SELECT | SELECT |
| column-level grants ที่มีอยู่จริง (`pg_attribute.attacl`) | **0 รายการทั้งฐานข้อมูล** | |
| sequence grants | 0 | 0 |
| `public.set_updated_at()` EXECUTE | ✅ (จาก PUBLIC ปกติ) | ✅ |
| `pg_default_acl` | 0 แถว (ไม่มี default privileges ตั้งไว้) | |

ยืนยันเชิงลบด้วย `has_table_privilege` — `advisor_api`: `course_documents INSERT/UPDATE = f` ·
`course_chunks INSERT/DELETE = f` · `courses INSERT = f` · `mko.crawl_sources SELECT/UPDATE = f`
→ **backend เขียน knowledge tables ไม่ได้** VERIFIED

ยืนยันเชิงบวก — `advisor_ingest`: `courses SELECT = t` · `courses UPDATE = t`
(จำเป็นเพื่อใช้ `SELECT … FOR SHARE` ที่ `approve.py:260`) · `course_documents INSERT = t` ·
`course_chunks INSERT = t` · `course_chunks DELETE = t` · `mko.crawl_sources UPDATE = t` ·
`mko.crawl_sources DELETE = f` → **worker มีสิทธิ์ครบและไม่เกิน** VERIFIED

### 5.2 Grant ที่ยังขาด (มาพร้อม 004 เท่านั้น)

| role | grant ที่ขาด | ใครต้องใช้ |
|---|---|---|
| `advisor_api` | `SELECT ON mko.v_crawl_queue` | `crawl_review.py:66` (`list_pending`) |
| `advisor_api` | `SELECT (id, file_sha256, staging_path, status) ON mko.crawl_sources` | `crawl_review.py:99` (`staged_file_location`) |
| `advisor_api` | `SELECT, INSERT ON mko.crawl_decisions` | approve/ignore |
| `advisor_api` | `UPDATE (superseded_at, superseded_by) ON mko.crawl_decisions` | undo |
| `advisor_ingest` | `SELECT ON mko.v_crawl_queue` · `SELECT, INSERT, UPDATE ON mko.crawl_decisions` | worker |

**ไม่มี grant ที่เกินจำเป็นใน 004** — `advisor_api` ยังเขียน `crawl_sources` ไม่ได้ และแก้
`ingest_*`/`document_id` ของ decision ไม่ได้ (UPDATE ระดับคอลัมน์เฉพาะสองคอลัมน์ของการถอน)

### 5.3 Phase 3A routes (จาก source)

| Method | Path | บรรทัด | auth |
|---|---|---|---|
| GET | `/crawl-review/pending` | `crawl_review.py:72-73` | `require_admin` ที่ระดับ router (`:53`) |
| GET | `/crawl-review/{crawl_source_id}` | `:77-78` | เดียวกัน |
| GET | `/crawl-review/{crawl_source_id}/pdf` | `:85-86` | เดียวกัน |
| POST | `/crawl-review/{id}/approve` | `:111-114` | + `rate_limiter` (`_decide` ที่ `:65`) |
| POST | `/crawl-review/{id}/ignore` | `:128-131` | + `rate_limiter` |
| POST | `/crawl-review/{id}/undo` | `:143-145` | + `rate_limiter` |

`require_admin` = `deps.py:50-53` → `if not user.is_admin: raise HTTPException(403, "admin only")`
· `decided_by` มาจาก `str(admin.email)` ที่ `:122, :137, :150` **ไม่รับจาก body** (ไม่มี field
นี้ใน `schemas/crawl_review.py`)

state transition ของการอนุมัติ/ปฏิเสธและการ validate อยู่ใน `services/crawl_review.py`
(approve/ignore/undo, optimistic lock ด้วย `file_sha256`, 409/422/404) — ตรวจแล้วใน Phase 3A
และไม่มีการทดสอบ action ที่เปลี่ยนสถานะในรอบ audit นี้

### 5.4 Phase 3B (จาก source)

| เรื่อง | หลักฐาน |
|---|---|
| token | `localStorage["course_advisor_token"]` (`page.tsx:34, 76, 91`) — **ไม่ใช้ cookie** |
| ส่ง token | `apiFetch` แนบ `Authorization: Bearer` · PDF แนบเองที่ `page.tsx:108-109` |
| proxy ส่งต่อ header | `frontend/app/api/[...path]/route.ts:32` ส่งต่อ `authorization, content-type, accept` |
| 401 | `page.tsx:68` ลบ token แล้วกลับหน้าเข้าสู่ระบบ |
| 403 | `page.tsx:67` แสดงหน้า "ไม่มีสิทธิ์" · ไม่มีปุ่มตัดสินใจ |
| trust boundary | หน้าเว็บไม่ตัดสินสิทธิ์เอง (`/users/me` ไม่มี `is_admin`) backend เป็นผู้ตัดสิน |
| CSRF | **NOT APPLICABLE** — ใช้ Bearer token ใน header ไม่ใช่ cookie จึงไม่มี ambient credential |

### 5.5 Admin state (aggregate ไม่มี PII)

```
users_total = 197 · admin_total = 0 · admin_active = 0
```

→ **B1: ไม่มีบัญชีผู้ดูแลแม้แต่บัญชีเดียว** ทุกคำขอไป `/crawl-review/*` จะได้ 403
วิธีให้ผู้ดูแลยืนยันบัญชีเป้าหมายในรอบอนาคต**โดยไม่ใส่ identity ลงรายงาน**: ให้เจ้าของโปรเจค
เลือกบัญชีเองแล้วส่ง `UPDATE users SET is_admin = true WHERE email = :email` ด้วยค่าที่เขา
พิมพ์เอง จากนั้นยืนยันด้วย aggregate (`admin_active` เปลี่ยน 0 → 1) เท่านั้น

**การ rollback flag**: คืนเฉพาะบัญชีที่เปลี่ยนในรอบนั้นด้วย `UPDATE … SET is_admin = false`
โดยบันทึกค่าเดิมไว้ก่อน **ไม่ลบบัญชี และไม่แตะ admin คนอื่น** (ปัจจุบันไม่มีคนอื่น)

---

## 6. Staging / documents filesystem audit

### 6.1 `CRAWL_STAGING_DIR` — semantics จาก source

| ที่ | พฤติกรรม |
|---|---|
| `backend/app/core/config.py:76` | `crawl_staging_dir: str = Field("", alias="CRAWL_STAGING_DIR")` — ค่าว่าง = ปิดการเปิดดูไฟล์ |
| `backend/app/services/staging_store.py` | root ว่าง/ไม่ใช่โฟลเดอร์ → `enabled = False` → `/crawl-review/{id}/pdf` ตอบ 404 เสมอ |
| `pipeline/crawl/approve.py:148` | ค่าว่าง → `JobError("staging_dir_unset")` — **fail closed ไม่ถอยไป cwd** |
| `pipeline/crawl/sync.py` (crawler) | ใช้ `--staging` เป็น CLI arg ค่าเริ่มต้น `staging/crawl` **ไม่ได้อ่าน env นี้** |

> ข้อสังเกตจาก source: crawler เขียนโฟลเดอร์ที่ระบุด้วย `--staging` ส่วน backend และ worker
> อ่านจาก `CRAWL_STAGING_DIR` **สองฝั่งต้องชี้ที่เดียวกันด้วยการตั้งค่า ไม่มีอะไรบังคับให้ตรงกัน**

### 6.2 Host / container path matrix (ตรวจจริง)

| path | ที่ host | ที่ container | mode | เจ้าของ | สถานะ |
|---|---|---|---|---|---|
| documents | `/home/ubuntu/course-advisor-system/documents` | `/srv/documents` ใน backend | **ro** | `ubuntu:ubuntu` (1001:1001) โฟลเดอร์ 755 | VERIFIED |
| ไฟล์ `.pdf` ในนั้น | 30 ไฟล์ mode **644** เจ้าของ `ubuntu:ubuntu` | backend อ่านได้ **30/30** | | | VERIFIED |
| โฟลเดอร์ย่อย | `curriculum`, `curriculum-brief`, `web` mode 755 | | | | VERIFIED |
| `MANIFEST.tsv` | mode 600 | `document_store` glob เฉพาะ `*.pdf` จึงไม่เกี่ยว | | | VERIFIED |
| symlink ใน documents | 0 | | | | VERIFIED |
| staging | `…/staging` **ไม่มี** · `/home/ubuntu/staging` **ไม่มี** · `/srv/staging` **ไม่มี** | ไม่ได้ mount | — | — | **B3** |
| `CRAWL_STAGING_DIR` ใน backend | — | **ไม่ได้ตั้ง** | | | **B3** |

UID/GID: backend รันเป็น `uid=1000(appuser)` · host `ubuntu` เป็น `1001:1001`
→ ไฟล์ mode 644 ทำให้ appuser อ่านได้ (ยืนยันด้วยการนับ `-readable` ในคอนเทนเนอร์: 30/30)
**ข้อบังคับสำหรับไฟล์ที่ worker จะเขียน: ต้อง world-readable (644) ไม่งั้น backend อ่านไม่ได้**

### 6.3 Disk / inodes (จาก metadata ไม่สร้างไฟล์ทดสอบ)

| รายการ | ค่าจริง |
|---|---|
| `/` | 97 G ใช้ 33 G ว่าง **65 G** (34%) |
| inodes | 12,902,400 ใช้ 364,693 ว่าง 12,537,707 (3%) |
| `/var/lib/docker` | 19 G |
| `documents/` | 85 M (30 PDF) |

ประมาณการ headroom (แยกจากค่าจริงชัดเจน — **เป็นประมาณการ ไม่ใช่ค่าที่วัด**)

| สิ่งที่จะเพิ่ม | ประมาณ |
|---|---|
| staging ของ 12 ไฟล์ปัจจุบัน | ~85 M (เท่ากับ documents) |
| documents ต่อเอกสารใหม่หนึ่งฉบับ | ~3–5 M |
| อิมเมจ worker ใหม่ (python slim + pymupdf + deps) | ~250–350 M |
| backup ฐานข้อมูลใหม่หนึ่งชุด | ~52 M (เท่าชุดเดิม) |
| **รวมที่ต้องใช้** | **< 1 G เทียบกับว่าง 65 G → เพียงพอมาก** |

### 6.4 แผนโอน staging (ยังไม่ทำ)

`FUTURE — DO NOT EXECUTE IN THIS AUDIT`

1. สร้าง manifest ที่ต้นทาง: ชื่อไฟล์ + `sha256` + ขนาด (ไฟล์ข้อความธรรมดา)
2. โอนขึ้นปลายทางใหม่ที่มีเวอร์ชันในชื่อ เช่น `/home/ubuntu/staging-<วันเวลา>/crawl/`
   **ไม่เขียนทับของเดิมและไม่ลบอะไร**
3. ตรวจ `sha256` ที่ปลายทางเทียบ manifest ทุกไฟล์ ต้องตรง 100% ก่อนทำต่อ
4. ตั้ง mode ไฟล์ 644 และโฟลเดอร์ 755 เจ้าของ `ubuntu:ubuntu`
5. mount เข้า backend แบบ **ro** ที่ path เดียวกับที่จะตั้งใน `CRAWL_STAGING_DIR`
   และ mount เข้า worker (ro ก็พอ เพราะ worker คัดลอกเป็นสำเนาของตัวเองก่อนตรวจ)
6. ข้อบังคับเรื่อง path: `mko.crawl_sources.staging_path` ที่ crawler บันทึกไว้ต้องอยู่**ใต้**
   `CRAWL_STAGING_DIR` ที่ทั้ง backend และ worker เห็น ไม่งั้น `staging_store`/`resolve_staged`
   จะปฏิเสธด้วย `path_outside_staging_root` — **ค่า `staging_path` ของ 12 แถวปัจจุบันเป็น NULL
   ทั้งหมด จึงยังไม่มีปัญหานี้ แต่จะมีทันทีที่ crawler รันจากเครื่องอื่นด้วย path ของเครื่องนั้น**

### 6.5 ทางให้ worker เขียน documents

`DOCUMENTS_DIR` ถูก mount เข้า backend เป็น `:ro` (ตรวจแล้ว) และ**ควรคงเป็น ro ต่อไป**
→ worker ต้อง mount host path เดียวกันแบบ **rw** ในคอนเทนเนอร์ของตัวเอง

```
backend : /home/ubuntu/course-advisor-system/documents → /srv/documents   ro   (เดิม)
worker  : /home/ubuntu/course-advisor-system/documents → /srv/documents   rw   (ใหม่)
```

**ห้ามใช้ path ชั่วคราวในคอนเทนเนอร์เป็นที่เก็บถาวร** — ถ้าเขียนลง layer ของคอนเทนเนอร์
ที่ใช้ `--rm` ไฟล์จะหายไปพร้อมคอนเทนเนอร์ และ `/documents/{id}/pdf` จะเปิดไม่ได้ตลอดไป
ขณะที่ฐานข้อมูลยังบอกว่ามีเอกสาร

### 6.6 Rollback ของไฟล์

ใช้ manifest ที่บันทึก**เฉพาะไฟล์ที่รอบนั้นเพิ่ม** (path + sha256 + เวลา) แล้วลบตาม manifest
**ห้ามลบไฟล์เดิม ห้ามลบไฟล์ที่ยังมี `course_documents` อ้างถึง และห้ามลบทั้งโฟลเดอร์หรือ volume**
ก่อนลบต้องตรวจว่า sha256 ของไฟล์ตรงกับที่ manifest บันทึก เพื่อไม่ลบไฟล์ที่คนอื่นเขียนทับ

---

## 7. Worker / runtime / dependency audit

### 7.1 Invocation จาก source (ไม่ได้รัน แม้แต่ `--help`)

`pipeline/crawl/approve.py`

| รายการ | หลักฐาน |
|---|---|
| module | `python -m pipeline.crawl.approve` (docstring บรรทัด 4) |
| `--database-url` | `:513` ค่าเริ่มต้นอ่านจาก `INGEST_DATABASE_URL` |
| `--max-jobs` | `:515` ค่าเริ่มต้น **1** · `:523` ปฏิเสธถ้า `< 1` |
| ไม่มี flag อื่น | ตรวจ `add_argument` ทั้งไฟล์ได้ 2 ตัวเท่านั้น |
| exit code | `:521` `SystemExit("ต้องระบุ --database-url …")` · `:523` `SystemExit("--max-jobs …")` · `:531` `SystemExit(1 if failed else 0)` |
| ตั้ง env ให้ `run()` | `:527` `os.environ["INGEST_DATABASE_URL"] = args.database_url` เพื่อให้ `ingest.py:172` อ่านค่าเดียวกัน |
| working directory | ต้องอยู่ที่ราก repo หรือให้ `pipeline`/`llm` อยู่ใน `sys.path` — `:58-60` เติม `parents[2]` ให้เอง |

### 7.2 Environment ที่ต้องมี (ชื่อ ไม่ใช่ค่า)

| ตัวแปร | ใครอ่าน | ผลถ้าไม่มี |
|---|---|---|
| `INGEST_DATABASE_URL` | `approve.py:513` · `ingest.py:172` | `SystemExit` ก่อนเริ่ม |
| `EMBED_MODEL` | `approve.py:112` · `ingest.py:179` | `embed_model_mismatch` (worker กันไว้ก่อน) |
| `EMBED_DIM` | `approve.py:117` | `embed_dim_mismatch` |
| `OLLAMA_BASE_URL` | `approve.py:131` · `ingest.py:178` | ใช้ค่าเริ่มต้น `http://127.0.0.1:11434` ซึ่ง**ผิดในคอนเทนเนอร์** ต้องตั้งเป็น `http://ollama:11434` |
| `CRAWL_STAGING_DIR` | `approve.py:148` | `staging_dir_unset` |
| `DOCUMENTS_DIR` | `approve.py:268` | `documents_dir_unset` |
| `OCR_TEXT_JSON` | `ingest.py:190` | ไม่จำเป็น (ข้ามขั้น OCR) |

### 7.3 หนึ่งงานต่อรอบ และ transaction (จาก source)

| เรื่อง | หลักฐาน |
|---|---|
| จำกัดหนึ่งงาน | `CLAIM_SQL` มี `LIMIT 1` และ `FOR UPDATE OF d SKIP LOCKED` · `work()` `:469` วน `while done + failed < max_jobs` โดยยึด**ทีละงานต่อ transaction** · `--max-jobs` ค่าเริ่มต้น 1 → **จำกัดหนึ่งงานได้จริง** |
| ไม่มี loop รอ | `:488` `break` เมื่อ `claim` คืน `None` · ไม่มี `sleep` ไม่มี scheduler (ค้นแล้ว) |
| ownership | ถือ row lock ของแถว decision ตลอดงาน (ดู Phase 3C §4) → คำสั่ง undo ของ backend รอที่แถวเดียวกัน |
| idempotency | `already_ingested()` (`ingest.py:186`) + `ON CONFLICT (course_id, file_sha256)` (`:125`) + เงื่อนไขยึดงาน `ingest_finished_at IS NULL` |
| DB writes ของ worker | เฉพาะ `mko.crawl_decisions` และ `mko.crawl_sources` (conditional update + ตรวจ `rowcount`) |
| document writes | `publish_document()` `:268` เขียนใต้ `DOCUMENTS_DIR` แบบ atomic (`os.replace`) หลัง ingestion สำเร็จ |
| embedding calls | ผ่าน `run()` เท่านั้น (`ingest.py:196`) + การ probe หนึ่งครั้งใน `check_embedding_contract` `:131-136` |

### 7.4 Dependency ของอิมเมจ — **B4**

`approve.py` import ที่ระดับโมดูล: `psycopg`, `psycopg.rows`, `llm.connector`
(→ `httpx`), **`pipeline.extract_pdf` (→ `fitz` / PyMuPDF)** และ lazily `pipeline.ingest`
(→ `pgvector.psycopg`, `dotenv`, `fitz`)

| แพ็กเกจ | ประกาศใน `pipeline/requirements.txt` | ประกาศใน `backend/requirements.txt` | **มีในอิมเมจ backend ที่รันอยู่** (pip metadata) |
|---|---|---|---|
| `psycopg[binary]` | ✅ | ✅ | ✅ `psycopg 3.3.6`, `psycopg-binary 3.3.6` |
| `pgvector` | ✅ | ✅ | ✅ `0.5.0` |
| `httpx` | ✅ | ✅ | ✅ `0.28.1` |
| `python-dotenv` | ✅ | ✅ | (ไม่ได้ query ชื่อนี้ — อยู่ใน requirements ทั้งสองฝั่ง) |
| **`pymupdf`** | ✅ | ❌ | ❌ **ไม่มี** (`pip show PyMuPDF` / `pymupdf` ไม่พบ) |
| `tqdm` | ✅ | ❌ | ❌ ไม่มี (ใช้เฉพาะ `ingest_batch.py` ไม่ใช่ worker) |

→ **อิมเมจ backend ที่มีอยู่รัน worker ไม่ได้** ต้องมีอิมเมจที่ลง `pipeline/requirements.txt`
(ยังไม่มี `Dockerfile` ของ pipeline ในโปรเจค — ตรวจแล้วมีแค่ `backend/`, `frontend/`, `webapi/`)

ตรวจโดยใช้ **pip metadata ไม่ import แอป** ตามข้อกำหนด

---

## 8. Embedding / Ollama readiness

| รายการ | ค่าที่ตรวจได้ | ที่มา | สถานะ |
|---|---|---|---|
| `EMBED_MODEL` ที่ backend เห็น | `bge-m3` | `printenv` ในคอนเทนเนอร์ (ค่าไม่เป็นความลับ) | VERIFIED |
| `EMBED_DIM` ที่ backend เห็น | `1024` | เดียวกัน | VERIFIED |
| มิติของคอลัมน์จริง | `course_chunks.embedding` `atttypmod = 1024` | query เดียวกับ `backend/app/main.py:32-34` | VERIFIED |
| ค่าที่ worker บังคับ | `REQUIRED_EMBED_MODEL = "bge-m3"` · `REQUIRED_EMBED_DIM = 1024` (`approve.py:75-76`) | source | VERIFIED |
| `pipeline/ingest.py` ตรวจสองค่านี้ไหม | **ไม่** — อ่านแค่ `EMBED_MODEL` (`:179`) ค่าเริ่มต้น `nomic-embed-text` (768 มิติ) และไม่อ่าน `EMBED_DIM` เลย | source | VERIFIED (เป็นเหตุที่ worker ต้องกันเอง) |
| Ollama ติดต่อได้จากเครือข่ายเดียวกับ worker | `GET http://ollama:11434/api/tags` → **HTTP 200** | รันจากคอนเทนเนอร์ backend ซึ่งอยู่ network `course-advisor-system_default` เดียวกับที่ worker จะอยู่ | VERIFIED |
| โมเดลที่มีในเครื่อง | `bge-m3:latest` (1.2 GB) · `qwen2.5:7b` · `qwen2.5:3b` · `qwen2.5:1.5b` · `llama3.2:3b` · `gemma2:2b` | `/api/tags` | VERIFIED |
| ความเข้ากันได้กับข้อมูลเดิม | `course_chunks` 9,039 แถวถูกสร้างด้วย 1024 มิติ (คอลัมน์เป็น `VECTOR(1024) NOT NULL`) การใช้ `bge-m3` ต่อจึงเข้ากัน | — | VERIFIED |

**สิ่งที่ยังไม่ได้ตรวจ**: ยังไม่เคยเรียก embedding จริงเพื่อดูว่าความยาวเวกเตอร์ที่ `bge-m3`
คืนมาเป็น 1024 จริง — **ตั้งใจไม่ทำ** เพราะเป็นการ generate ด่านนี้อยู่ใน worker เอง
(`approve.py:131-138`) และจะทำงานตอนรันจริงก่อนเขียนอะไรลงคลัง

**`/api/tags` ใช้เป็น health check ได้เพราะเป็น metadata อย่างเดียว** ไม่ generate ไม่ pull
ไม่โหลดโมเดลเข้าหน่วยความจำ · **ไม่ใช้ embedding request เป็น health check**

---

## 9. Build / deploy audit

### 9.1 ต้อง build/deploy อะไร

| ส่วน | ต้องทำอะไร | เหตุผลจาก source |
|---|---|---|
| **backend** | **build + recreate** | Phase 3A เพิ่ม `routes/crawl_review.py`, `services/crawl_review.py`, `services/staging_store.py`, `schemas/crawl_review.py` และแก้ `main.py`, `core/config.py` · `backend/Dockerfile:25-26` `COPY backend/ backend/` และ `COPY llm/ llm/` → โค้ดฝังในอิมเมจ ต้อง build ใหม่ · ต้องเพิ่ม env `CRAWL_STAGING_DIR` และ mount staging `:ro` |
| **frontend** | **build + recreate** | Phase 3B เพิ่ม `app/crawl-review/page.tsx`, `lib/crawl-review.ts` · `frontend/Dockerfile` build แบบ `output: "standalone"` (`next.config.ts:10`) → โค้ดฝังในอิมเมจ · build arg `NEXT_PUBLIC_API_URL=/api` (`docker-compose.prod.yml:95`) ถูกฝังตอน build |
| **worker** | **สร้างอิมเมจใหม่** | ไม่มี Dockerfile ของ pipeline · อิมเมจ backend ขาด PyMuPDF (B4) |
| **caddy / postgres / ollama / webapi** | **ไม่ต้องแตะ** | ไม่มีการเปลี่ยนที่เกี่ยวข้อง |

### 9.2 Artifact สำหรับ rollback

| ส่วน | artifact ที่มีอยู่ | สถานะ |
|---|---|---|
| backend | `course-advisor-system-backend:latest` = `d1d1ba713412` (ตัวที่รันอยู่) และ tag `rollback-*` 14 ตัว (ใหม่สุด `rollback-17abce0` = `638bc49d5aee`) | ✅ พร้อม rollback |
| **frontend** | อิมเมจที่รันอยู่ `sha256:ce65aad64305…` **ไม่อยู่ใน `docker images -a` แล้ว** (นับได้ 0 · dangling images = 0) · `course-advisor-system-frontend:latest` = `f87960ad1da2` เป็น**อิมเมจอื่น** อายุ 4 สัปดาห์ | ❌ **B5 — ไม่มี artifact ให้ย้อน** |
| Caddyfile / compose | มีสำเนาเก่าใน `/home/ubuntu/backups/` (เช่น `docker-compose.prod.yml.before_source_header_20260921T021009Z`) | ✅ |

**B5 อธิบาย**: คอนเทนเนอร์ frontend ยังรันจาก layer ของอิมเมจที่ถูกลบออกจาก image store ไปแล้ว
ถ้า recreate คอนเทนเนอร์นี้ อิมเมจเดิมจะหายไปอย่างถาวร **ต้องเก็บ artifact ก่อนแตะ**
(`docker commit` แล้ว tag — เป็น mutation จึงอยู่ในแผนอนาคต)

### 9.3 การ pin revision

แผน deploy ต้องอ้าง `617110e975dccc94b5e67f77990e34a071ccf9a0` เป็น revision เดียว
และหลัง build ต้องบันทึก image ID/digest ของทั้งสอง service ลงบันทึกการ deploy
**ข้อเสนอ (แผนอนาคต)**: เพิ่ม `--label org.opencontainers.image.revision=<commit>` ตอน build
เพื่อปิด U1 สำหรับครั้งต่อไป — เป็นการเปลี่ยนวิธี build ต้องอนุมัติแยก

### 9.4 ความเข้ากันได้ของแอปเก่ากับ schema ใหม่

แอปเก่า (ที่รันอยู่) ไม่อ้าง object ของ 004 เลย → **apply 004 ก่อนแล้วค่อย deploy แอปได้อย่างปลอดภัย**
และถ้าต้อง rollback แอป ก็ทำได้โดยไม่ต้องถอน schema

---

## 10. Caddy / API routing audit

| ตรวจ | ผล | สถานะ |
|---|---|---|
| Caddyfile ที่ deploy เทียบกับ repo HEAD | sha256 ต่างกัน (`da2e26fd948d2a7143c85d1e` vs `14ffb3748c0d04121151f91c`) **แต่หลังตัด CR แล้วเท่ากันทั้งสองฝั่ง = `14ffb3748c0d04121151f91c`** · ไฟล์ที่ deploy มี CR ทั้ง 74 บรรทัด (scp จาก Windows) | **VERIFIED — เนื้อหาตรงกัน** |
| ไฟล์ใน container เทียบกับ host | `da2e26fd948d2a7143c85d1e` ทั้งคู่ | VERIFIED |
| `/api/crawl-review/*` → FastAPI | `handle /api/*` (บรรทัด 43) → `uri strip_prefix /api` (44) → `reverse_proxy backend:8000` (45) → backend เห็น `/crawl-review/*` ตรงกับ `prefix="/crawl-review"` (`crawl_review.py:51`) | **VERIFIED — ไม่ต้องแก้ Caddy สำหรับ API** |
| ไม่ชนกับ `/api/admin/*` | `handle /api/admin/*` (37) อยู่ก่อนและส่งไป `webapi:3001` — prefix ของเราไม่ใช่ `/api/admin` จึงไม่ชน | VERIFIED |
| **`/crawl-review` (หน้าเว็บ) ที่ชื่อโดเมน** | ตกลง `handle { root * /srv/web; try_files {path} /index.html }` (63-67) → `/home/ubuntu/course-advisor-system/web` มีแค่ `assets` และ `index.html` · **ไม่มี `crawl-review`** → จะได้ SPA ของทีมออกแบบ ไม่ใช่หน้าของเรา | **FAIL — เข้าถึงที่ชื่อโดเมนไม่ได้** |
| `/crawl-review` ที่ทางเลข IP | `:80 { reverse_proxy frontend:3000 }` (72-73) → Next.js เสิร์ฟ route นี้ได้ | VERIFIED |

### สรุปเรื่อง Caddy

**ไม่ต้องแก้ Caddy** ถ้ายอมรับว่าผู้ดูแลเข้าหน้าตรวจทางเลข IP (`http://<IP>/crawl-review`)
ซึ่งเป็นทางเดียวกับที่ `/match` และ `/compare` ใช้อยู่แล้ว

ถ้าต้องการให้เข้าทางชื่อโดเมนได้ **ต้องแก้ Caddy** — ข้อเสนอที่เล็กที่สุด (แผนเท่านั้น):

```
FUTURE — DO NOT EXECUTE IN THIS AUDIT
เพิ่มบล็อกนี้ "ก่อน" handle /assets/* (บรรทัด 50) ในบล็อกของชื่อโดเมน:

    handle /crawl-review* {
        reverse_proxy frontend:3000
    }
```

- ต้องอยู่ก่อน `handle` ตัวสุดท้าย เพราะ Caddy เลือกบล็อกแรกที่ตรง (คอมเมนต์บรรทัด 27 ระบุไว้)
- verification: `curl -sS -o /dev/null -w '%{http_code}' https://<domain>/crawl-review` ต้องได้ 200
  และหน้าต้องมีหัวเรื่องของเรา ไม่ใช่ SPA ของทีมออกแบบ
- rollback: คืนไฟล์จากสำเนาที่เก็บไว้ แล้ว `docker compose ... up -d caddy` (recreate caddy)
- ความเสี่ยง: ถ้าไวยากรณ์ผิด **Caddy จะไม่เริ่มทำงานและเว็บล่มทั้งเว็บ** (คอมเมนต์บรรทัด 11-14
  บันทึกเหตุการณ์นี้ไว้แล้ว) จึงต้องตรวจไวยากรณ์ก่อนด้วย `caddy validate` ในคอนเทนเนอร์ชั่วคราว

**ข้อเสนอของผม: รอบแรกไม่แก้ Caddy** ใช้ทางเลข IP ให้ผู้ดูแลก่อน แล้วค่อยพิจารณาแยก

---

## 11. Backup / rollback

### 11.1 Backup ที่มีอยู่ (metadata อย่างเดียว ไม่เปิดเนื้อหา)

| รายการ | ค่าจริง | สถานะ |
|---|---|---|
| โฟลเดอร์ | `/home/ubuntu/backups` · 136 รายการ | VERIFIED |
| dump ฐานข้อมูลที่ใหม่สุด | `prod_pre_find_major_fix_20260917T171410Z.dump` — **2026-09-17 17:14 (11 วันก่อน)** | **B6** |
| dump ถัดไป | `prod_pre_on_path_20260917T073953Z.dump` (17 ก.ย. 07:40) · `mko_pre_p3_publication_20260916T213958Z.dump` (16 ก.ย. 21:40) | VERIFIED |
| ขนาดตัวอย่าง | `prod_pre_shadow_credit_fix_…dump` = 52 M · สิทธิ์ `-rw-------` (600) เจ้าของ ubuntu | VERIFIED |
| checksum คู่กัน | 12 ไฟล์ `*.dump.sha256` | VERIFIED |
| retention | **ไม่พบนโยบายที่ตรวจได้** (ไม่มีไฟล์นโยบายหรือ cron ที่ตรวจในรอบนี้) | UNKNOWN |
| encrypted | **ไม่** — mode 600 ควบคุมด้วยสิทธิ์ไฟล์เท่านั้น ไม่มีร่องรอยการเข้ารหัส | VERIFIED (จาก metadata) |
| หลักฐานการทดสอบ restore | **ไม่มีไฟล์ใดที่ชื่อมีคำว่า restore (นับได้ 0)** | **B6 — UNVERIFIED** |
| สำเนา config | มี เช่น `docker-compose.prod.yml.before_source_header_20260921T021009Z`, `web.before_score_explanation_…tar.gz` + `.sha256` | VERIFIED |
| backup ของ documents/staging | **ไม่พบ** | UNKNOWN |

→ **ห้ามใช้ backup เดิมเป็นหลักฐาน GO** ต้องทำชุดใหม่ก่อน mutation ครั้งแรก

### 11.2 Fresh backup plan

`FUTURE — DO NOT EXECUTE IN THIS AUDIT`

| ครอบคลุม | วิธี | verification |
|---|---|---|
| ฐานข้อมูล | `pg_dump -Fc` ทั้งฐาน `course_advisor` ลง `/home/ubuntu/backups/prod_pre_phase3d_<ISO>.dump` | `sha256sum` เก็บคู่กัน + `pg_restore --list` (อ่านอย่างเดียว) ต้องอ่าน TOC ได้ |
| documents | `tar` โฟลเดอร์ `documents/` + manifest `sha256` ทุกไฟล์ | เทียบจำนวนไฟล์ (30) และ sha ทุกไฟล์ |
| staging | manifest `sha256` (ยังไม่มีไฟล์ — จะมีหลังโอน) | เทียบกับ manifest ต้นทาง |
| deployment metadata | บันทึก image ID/digest ของ backend/frontend ปัจจุบัน + สำเนา `docker-compose.prod.yml` และ `Caddyfile` + `docker commit` อิมเมจ frontend ที่รันอยู่ (ปิด B5) | `docker images` แสดง tag ใหม่ |
| ผู้รับผิดชอบ | เจ้าของโปรเจค (คนเดียวที่มีสิทธิ์อนุมัติ mutation) | |
| RPO / RTO | **RPO** = เวลาที่ทำ backup ถึงเวลา deploy (ควร < 30 นาที) · **RTO** = ยังไม่ทดสอบ ประมาณจากขนาด dump 52 M น่าจะ < 10 นาที แต่ **เป็นประมาณการ ไม่ใช่ค่าที่วัด** | UNVERIFIED |
| prerequisite ของการ restore | พื้นที่ว่าง ≥ 2× ขนาด dump (มี 65 G) · ต้องหยุดการเขียนก่อน restore · ต้องมีรหัสผ่าน superuser ซึ่งอยู่กับเจ้าของโปรเจค | |

### 11.3 Rollback matrix

| # | สิ่งที่เปลี่ยน | Trigger ให้ rollback | Precondition | Action (อ้าง source) | Validation | ความเสี่ยง / จุดที่ต้องให้คนตัดสิน |
|---|---|---|---|---|---|---|
| R1 | **migration 004** | apply แล้ว object/grant ไม่ตรงที่คาด **และยังไม่มีแถวใน `crawl_decisions`** | ยืนยัน `SELECT count(*) FROM mko.crawl_decisions = 0` | `DROP VIEW mko.v_crawl_queue; DROP TABLE mko.crawl_decisions; DELETE FROM mko.schema_migrations WHERE version='004_crawl_decisions';` **ห้ามใส่ CASCADE** | object counts กลับเป็น 19/7 · ledger เหลือ 001–003 | **ถ้ามีแถวการอนุมัติแล้ว ห้าม drop** เพราะเป็นประวัติการตัดสินใจของคน — ให้คง schema แล้ว rollback แอปแทน (§4.2) · ต้องให้คนตัดสิน |
| R2 | **deploy backend** | health/auth/route ไม่ผ่าน | มี tag ของอิมเมจเดิม (`d1d1ba713412`) | ชี้ service กลับไปที่อิมเมจเดิมแล้ว recreate เฉพาะ backend | `/health` 200 · route เดิม 27 เส้นทาง · `/chat-web` ตอบได้ | ผู้ใช้เห็น downtime สั้น ๆ · แอปเก่า + schema ใหม่ปลอดภัย (§4.4) |
| R3 | **deploy frontend** | หน้าเว็บพัง | **ต้องมี artifact ก่อน** — ปัจจุบัน**ไม่มี** (B5) | ชี้กลับไปที่ tag ที่ `docker commit` เก็บไว้ก่อน build | หน้าแรก 200 · `/match`, `/compare` ใช้งานได้ | **ถ้าไม่ทำ artifact ก่อน จะย้อนไม่ได้เลย — blocker** |
| R4 | **admin flag** | ตั้งผิดบัญชี | บันทึกค่าเดิมของบัญชีนั้นไว้ | `UPDATE users SET is_admin = false WHERE id = <บัญชีที่เปลี่ยน>` | `admin_active` กลับเป็น 0 | **ห้ามลบบัญชี ห้ามแตะ admin คนอื่น** · ไม่ใส่ identity ลงรายงาน |
| R5 | **staged files** | โอนไฟล์ผิดชุด | มี manifest ของไฟล์ที่รอบนั้นเพิ่ม | ลบตาม manifest หลังตรวจ sha256 ตรง | จำนวนไฟล์กลับเป็นก่อนโอน | **ห้ามลบทั้งโฟลเดอร์** · ห้ามลบไฟล์ที่ไม่อยู่ใน manifest |
| R6 | **worker / knowledge writes** | ingest หนึ่งงานแล้วผลไม่ถูก | ต้องแยกข้อมูลของงานนั้นได้ | ดู §11.4 | counts กลับเป็น baseline | **เสี่ยงสูงสุด** — ดู §11.4 |
| R7 | **backend restart (รีเฟรช index)** | restart แล้วบริการไม่กลับมา | มี tag อิมเมจเดิม | recreate ด้วยอิมเมจเดิม | `/health` 200 | downtime สั้น |

### 11.4 Rollback ของ worker — วิเคราะห์ตาม implementation จริง

งานหนึ่งงานที่สำเร็จจะทิ้งร่องรอย 5 อย่าง

| ร่องรอย | ที่ไหน | แยกของงานเดียวได้ไหม |
|---|---|---|
| แถว `course_documents` | 1 แถว ระบุด้วย `(course_id, file_sha256)` ซึ่งเป็น unique key | ✅ แยกได้แน่นอน |
| แถว `course_chunks` | N แถว ระบุด้วย `document_id` | ✅ แยกได้แน่นอน (`insert_chunks` ที่ `ingest.py:159` ลบ/ใส่ตาม `document_id`) |
| `mko.crawl_decisions` | `document_id`, `ingest_finished_at`, `ingest_error` ของแถวเดียว | ✅ |
| `mko.crawl_sources` | `status='ingested'`, `document_id` ของแถวเดียว | ✅ |
| ไฟล์ใน `DOCUMENTS_DIR` | 1 ไฟล์ **หรือไม่มีเลยถ้าใช้ไฟล์เดิมซ้ำ** (`publish_document` `:278-283` reuse เมื่อ sha ตรง) | ✅ ถ้าบันทึก path ที่ `publish_document` คืนมาไว้ตอนรัน |
| in-memory index ของ `document_store` | ในโปรเซส backend | ⚠️ ล้างได้ด้วยการเริ่มโปรเซสใหม่เท่านั้น (§5 ของ Phase 3C / §7 นี้) |

→ **แยกข้อมูลของหนึ่งงานได้ทั้งหมด จึงไม่เป็น blocker** ขั้นตอน rollback (แผนอนาคต ต้องอนุมัติ):

```
FUTURE — DO NOT EXECUTE IN THIS AUDIT
1. บันทึก document_id, file_sha256, course_id และ path ที่ publish ไว้ ก่อนเริ่ม rollback
2. DELETE FROM course_chunks  WHERE document_id = :document_id;      -- advisor_ingest มีสิทธิ์
3. DELETE FROM course_documents WHERE id = :document_id;             -- ต้องใช้ superuser
                                                                     (advisor_ingest ไม่มี DELETE)
4. UPDATE mko.crawl_sources SET status='downloaded', document_id=NULL WHERE id=:source_id;
5. UPDATE mko.crawl_decisions SET document_id=NULL, ingest_finished_at=NULL,
          ingest_error='rolled_back' WHERE id=:decision_id;
6. ลบไฟล์ที่ publish "เฉพาะกรณีที่รอบนี้สร้างขึ้นใหม่" และ sha ตรงกับที่บันทึก
7. recreate backend เพื่อล้าง in-memory index
```

- **ห้ามลบด้วย predicate กว้าง** เช่น `DELETE FROM course_chunks WHERE created_at > …`
- **ห้าม restore ทั้ง DB ทับงานอื่นโดยอัตโนมัติ** — ถ้ามี concurrent write เกิดขึ้นระหว่างนั้น
  ต้องเลือกระหว่าง coordinated restore (หยุดทุกอย่างก่อน) หรือ forward repair
  **ทั้งสองทางต้องมีคนอนุมัติ**
- `course_documents` DELETE ต้องใช้ superuser เพราะ `advisor_ingest` ไม่มีสิทธิ์ (ตรวจแล้ว)
  → เป็นจุดที่ต้องหยุดรอคน

---

## 12. Baseline metrics

เก็บภายใน `BEGIN TRANSACTION READ ONLY` เดียวกัน (snapshot เดียว) ด้วย
`statement_timeout=15s`, `lock_timeout=3s` · ไม่แสดงเนื้อหาแถวใด

| ตาราง | exact count | ที่มา |
|---|---|---|
| `public.courses` | **24** | `SELECT count(*)` |
| `public.course_documents` | **31** | `SELECT count(*)` |
| `public.course_chunks` | **9039** | `SELECT count(*)` |
| `mko.crawl_sources` | **12** | `SELECT count(*)` |
| `mko.crawl_decisions` | **NOT APPLICABLE** — ตารางยังไม่มี (จะมีหลัง 004) | `to_regclass` = f |

| รายละเอียดของ `mko.crawl_sources` | ค่า |
|---|---|
| `status = 'unchanged'` | 12 (ทั้งหมด) |
| `needs_review = true` | 6 |
| **`staging_path IS NOT NULL`** | **0** |
| `document_id IS NOT NULL` | 12 |

| สภาพแวดล้อมที่ตรวจ | ค่า |
|---|---|
| database | `course_advisor` |
| role ที่ใช้ตรวจ | `postgres` (ผ่าน `docker exec` unix socket) |
| เวลาเซิร์ฟเวอร์ | `2026-09-28 08:48:23.852368+07` |
| version | PostgreSQL 16.15 (Debian 16.15-1.pgdg12+2) |
| extensions | `citext, pgcrypto, plpgsql, vector` |
| `course_chunks.embedding` dim | 1024 |

### Post-migration expected baseline (เป็น **ความคาดหมาย** ไม่ใช่ผลตรวจ)

| รายการ | คาดว่าเป็น |
|---|---|
| `mko.crawl_decisions` | 0 แถว (ตารางว่างเมื่อสร้างใหม่) |
| `mko.v_crawl_queue` | 6 แถว — เท่ากับจำนวนแถวที่ `needs_review` เพราะทั้ง 12 แถวเป็น `unchanged` (ไม่เข้าเงื่อนไข status) และยังไม่มี decision ใดให้กรองออก |
| `mko` BASE TABLE / VIEW | 20 / 8 |
| `courses` / `course_documents` / `course_chunks` | **ไม่เปลี่ยน** 24 / 31 / 9039 |

> **ต้อง recheck ทันทีก่อน deploy จริง** ตัวเลขทั้งหมดนี้เป็นค่า ณ 2026-09-28 08:48 (+07)
> และเปลี่ยนได้ทุกเมื่อถ้ามีการรัน crawler หรือมีผู้ใช้เข้าใช้งาน

---

## 13. Risk register

| # | ความเสี่ยง | Severity | หลักฐาน | ผลถ้าเกิด | Mitigation | Owner | Residual |
|---|---|---|---|---|---|---|---|
| R-1 | อิมเมจ frontend ที่รันอยู่หายไปจาก image store | **HIGH** | `docker images -a -q` ไม่มี `ce65aad6…` · dangling 0 | recreate frontend แล้วย้อนไม่ได้ | `docker commit` + tag ก่อน build (แผน ขั้น 3) | เจ้าของโปรเจค | ต่ำหลังทำ artifact |
| R-2 | backup ฐานข้อมูลเก่า 11 วัน และไม่เคยทดสอบ restore | **HIGH** | §11.1 | กู้ไม่ได้จริงเมื่อต้องกู้ | backup ใหม่ + `pg_restore --list` + ประเมิน RTO (แผน ขั้น 2) | เจ้าของโปรเจค | ปานกลาง (ยังไม่ทดสอบ restore เต็มรูปแบบ) |
| R-3 | ไม่มีบัญชีผู้ดูแล | **HIGH** | `admin_total=0` | Phase 3A/3B ใช้ไม่ได้เลย | ตั้ง flag หนึ่งบัญชี (แผน ขั้น 7) | เจ้าของโปรเจค | ต่ำ |
| R-4 | ไม่มีงานที่อนุมัติได้ | **HIGH** | `staging_path IS NOT NULL = 0` | รอบ controlled one-job ทำไม่ได้ | ต้องรัน crawler ให้พบไฟล์ใหม่/เปลี่ยน ซึ่ง**ขึ้นกับเว็บคณะ** ไม่ใช่สิ่งที่เราสร้างได้ | เจ้าของโปรเจค | **สูง — ควบคุมไม่ได้** |
| R-5 | worker ไม่มีอิมเมจที่รันได้ | **HIGH** | ไม่มี PyMuPDF ในอิมเมจ backend | รัน worker ไม่ได้ | สร้างอิมเมจ worker จาก `pipeline/requirements.txt` (แผน ขั้น 3) | เจ้าของโปรเจค | ต่ำ |
| R-6 | `GRANT SELECT (cols) ON mko.crawl_sources` ใน 004 ต้อง `AccessExclusiveLock` | MEDIUM | §4.2 | migration ค้างถ้ามี crawler run พร้อมกัน | ตั้ง `lock_timeout` ตอน apply · ไม่ apply พร้อม crawler | เจ้าของโปรเจค | ต่ำ |
| R-7 | ไฟล์ที่ worker เขียนต้อง world-readable | MEDIUM | backend เป็น uid 1000 · ไฟล์เดิม 644 เจ้าของ 1001 | `/documents/{id}/pdf` เปิดไม่ได้ | รัน worker ด้วย `--user 1001:1001` หรือ `chmod 644` หลังเขียน + ตรวจใน container | เจ้าของโปรเจค | ต่ำ |
| R-8 | `document_store` ต้องเริ่มโปรเซสใหม่จึงเห็นไฟล์ใหม่ | MEDIUM | `document_store.py:104-109` ไม่มี refresh (ค้นแล้ว 0) | เอกสารใหม่เปิดดูไม่ได้ทันที | recreate backend หลัง ingest สำเร็จ (แผน ขั้น 11) | เจ้าของโปรเจค | ต่ำ (downtime สั้น) |
| R-9 | `/crawl-review` เข้าทางชื่อโดเมนไม่ได้ | MEDIUM | §10 | ผู้ดูแลต้องใช้ทางเลข IP | ยอมรับในรอบแรก หรือแก้ Caddy แบบที่เสนอ (เสี่ยงเว็บล่ม) | เจ้าของโปรเจค | ต่ำถ้ายอมรับ IP |
| R-10 | ไม่มี provenance label บนอิมเมจ | MEDIUM | §2.3 | พิสูจน์ revision ที่ deploy ไม่ได้ในอนาคต | เพิ่ม `--label …revision` ตอน build | เจ้าของโปรเจค | ต่ำหลังเพิ่ม |
| R-11 | `staging_path` ที่ crawler บันทึกเป็น path ของเครื่องที่รัน crawler | MEDIUM | §6.4 · `sync.py` ใช้ `--staging` ไม่ใช่ env | worker/backend ปฏิเสธด้วย `path_outside_staging_root` | ต้องรัน crawler ด้วย `--staging` ที่เป็น path เดียวกับที่ mount ในเซิร์ฟเวอร์ | เจ้าของโปรเจค | ปานกลาง |
| R-12 | `advisor_ingest` ไม่มี DELETE บน `course_documents` | LOW | §5.1 | rollback ของ worker ต้องใช้ superuser | ระบุไว้ในขั้นตอน rollback ว่าต้องมีคนทำ | เจ้าของโปรเจค | ต่ำ |
| R-13 | retention/encryption ของ backup ไม่ทราบ | LOW | §11.1 | ไฟล์ backup อาจถูกลบหรืออ่านได้โดยคนที่เข้าถึงเครื่อง | ตรวจนโยบายและสิทธิ์แยก | เจ้าของโปรเจค | ต่ำ |

---

## 14. Blockers

| # | Blocker | หลักฐานที่ขาด / ที่พบ | วิธีปลด | ผู้ที่ต้องทำ |
|---|---|---|---|---|
| **B1** | ไม่มีบัญชีผู้ดูแล | `admin_total = 0`, `admin_active = 0` | เจ้าของโปรเจคเลือกบัญชีแล้วตั้ง `is_admin = true` หนึ่งบัญชี บันทึกค่าเดิมไว้ · ยืนยันด้วย aggregate เท่านั้น | เจ้าของโปรเจค |
| **B2** | ไม่มีงานที่อนุมัติได้ | `crawl_sources`: 12 แถว `unchanged`, `staging_path IS NOT NULL = 0` · `approve()` ต้องการ `has_staged_file` (`services/crawl_review.py:196`) · worker ต้องการ `staging_path` (`approve.py:161`) | ต้องมีรอบ crawl ที่พบไฟล์ใหม่หรือไฟล์ที่เปลี่ยน ซึ่งขึ้นกับเว็บคณะ · ทางเลือกคือทดสอบ end-to-end บนฐานข้อมูลทดสอบต่อไปก่อน | เจ้าของโปรเจค (ตัดสินว่าจะรอหรือยอมรับว่ายังทดสอบ production ไม่ได้) |
| **B3** | ไม่มี staging บนเซิร์ฟเวอร์ · `CRAWL_STAGING_DIR` ไม่ได้ตั้ง | ตรวจ 3 path แล้วไม่มี · `printenv` บอกว่าไม่ได้ตั้ง | โอน staging ตาม §6.4 + เพิ่ม env และ mount `:ro` ใน compose | เจ้าของโปรเจค |
| **B4** | อิมเมจ backend ไม่มี PyMuPDF | `pip show PyMuPDF`/`pymupdf` ไม่พบ · `approve.py:66` → `extract_pdf.py:20` `import fitz` | สร้างอิมเมจ worker จาก `pipeline/requirements.txt` (ต้องเขียน Dockerfile ใหม่ — งานเพิ่ม ต้องอนุมัติ) | เจ้าของโปรเจค |
| **B5** | ไม่มี artifact ให้ย้อน frontend | อิมเมจที่รันอยู่ไม่อยู่ใน image store | `docker commit` คอนเทนเนอร์ที่รันอยู่ แล้ว tag เก็บ **ก่อน** build ใหม่ | เจ้าของโปรเจค |
| **B6** | backup เก่า + ไม่มีหลักฐาน restore | dump ใหม่สุด 2026-09-17 · ไม่มีไฟล์ชื่อ restore | ทำ backup ใหม่ + `pg_restore --list` + บันทึกผล | เจ้าของโปรเจค |
| **B7** | `DOCUMENTS_DIR` เป็น `:ro` สำหรับ backend | `docker inspect` mount mode = ro | mount host path เดียวกันแบบ rw ให้ **worker เท่านั้น** คง backend เป็น ro | เจ้าของโปรเจค |
| **U1** | พิสูจน์ commit ที่ deploy อยู่ไม่ได้ | ไม่มี provenance label | ยอมรับหลักฐานทางอ้อม (§2.3) ในรอบนี้ และเพิ่ม label ตอน build ครั้งหน้า | เจ้าของโปรเจค |

---

## 15. GO / NO-GO checklist

| # | ข้อ | ผล | หลักฐาน |
|---|---|---|---|
| 1 | HEAD = expected commit และไม่มี drift กับ origin | **PASS** | §2.1, §2.2 |
| 2 | working tree/staged สะอาด | **PASS** | §2.1 |
| 3 | `pipeline/ingest.py` ไม่ถูกแก้ | **PASS** | §2.1 |
| 4 | ไฟล์ Phase 3A/3B/3C อยู่ใน HEAD ครบ | **PASS** | §2.1 |
| 5 | production ยังเป็น 001–003 · 004 ไม่ถูก apply · ไม่มี partial | **PASS** | §4.1 |
| 6 | 004 เป็น additive จริง ไม่มี destructive | **PASS** | §4.2 |
| 7 | permission matrix ของ `advisor_ingest` ครบสำหรับ worker | **PASS** | §5.1 |
| 8 | `advisor_api` เขียน knowledge tables ไม่ได้ | **PASS** | §5.1 |
| 9 | สัญญา embedding `bge-m3` / 1024 ตรงทุกชั้นที่ตรวจได้ | **PASS** | §8 |
| 10 | Ollama ติดต่อได้จากเครือข่ายของ worker และมี `bge-m3` | **PASS** | §8 |
| 11 | Caddy รองรับ `/api/crawl-review/*` แล้ว ไม่ต้องแก้ | **PASS** | §10 |
| 12 | worker จำกัดหนึ่งงานต่อรอบได้จริง | **PASS** | §7.3 |
| 13 | rollback แยกข้อมูลของหนึ่งงานได้ | **PASS** | §11.4 |
| 14 | disk/inodes เพียงพอ | **PASS** | §6.3 |
| 15 | baseline exact counts เก็บได้ | **PASS** | §12 |
| 16 | **มีบัญชีผู้ดูแล** | **FAIL (B1)** | §5.5 |
| 17 | **มีงานที่อนุมัติได้สำหรับรอบ controlled** | **FAIL (B2)** | §12 |
| 18 | **staging พร้อมและ `CRAWL_STAGING_DIR` ตั้งแล้ว** | **FAIL (B3)** | §6.2 |
| 19 | **มีอิมเมจที่รัน worker ได้** | **FAIL (B4)** | §7.4 |
| 20 | **มี artifact ให้ย้อน frontend** | **FAIL (B5)** | §9.2 |
| 21 | **backup สดและยืนยัน recovery แล้ว** | **FAIL (B6)** | §11.1 |
| 22 | **worker มีทางเขียน documents แบบถาวร** | **FAIL (B7)** | §6.5 |
| 23 | พิสูจน์ revision ที่ deploy อยู่จาก metadata | **UNKNOWN (U1)** | §2.3 |
| 24 | `/crawl-review` เข้าถึงได้ที่ชื่อโดเมน | **FAIL (ยอมรับได้ถ้าใช้ทางเลข IP)** | §10 |

**ข้อ 16–22 เป็นข้อสำคัญและ FAIL · ข้อ 23 เป็น UNKNOWN → NO-GO**

---

## 16. แผน deploy Phase 3D (ทุกขั้นเป็นแผน ห้ามรันในรอบนี้)

> ทุกขั้นที่เปลี่ยนระบบมีป้าย **`FUTURE — DO NOT EXECUTE IN THIS AUDIT`**
> การส่ง prompt ของรอบนี้ไม่ใช่การอนุมัติให้รันขั้นใดเลย
> `<PLACEHOLDER>` ทุกตัวต้อง resolve ด้วยคำสั่งอ่านอย่างเดียวที่ระบุไว้ก่อนใช้

### ขั้น 1 — Human review และยืนยันสถานะใหม่

- **Target**: ไม่มี (งานเอกสาร)
- **Prerequisite**: รายงานฉบับนี้
- **Action**: เจ้าของโปรเจคอ่าน §14 แล้วตัดสินว่าจะปลด blocker ใดและอนุมัติขั้นใด
- **Verification (SAFE READ-ONLY)**: รันตาราง `SAFE READ-ONLY NOW` (§17) ซ้ำเพื่อยืนยันว่า
  revision/topology/สิทธิ์ยังเหมือนในรายงาน
- **Stop condition**: revision drift หรือ blocker ใดยังไม่มีเจ้าภาพ → หยุด
- **Checkpoint**: บันทึกผลการ recheck พร้อมเวลา

### ขั้น 2 — Recheck baseline และทำ backup ใหม่  `FUTURE — DO NOT EXECUTE IN THIS AUDIT`

- **Target**: postgres, filesystem บนเซิร์ฟเวอร์
- **Prerequisite**: ขั้น 1 ผ่าน · ตกลงช่วงเวลาที่ไม่มีคนใช้งาน · **ยืนยันว่าไม่มี crawler run ค้างอยู่**
- **Action**:
  1. recheck baseline (§17 ตาราง read-only)
  2. `pg_dump -Fc` ทั้งฐาน + `sha256sum` + `pg_restore --list` (อ่าน TOC อย่างเดียว)
  3. `tar` + manifest ของ `documents/`
  4. สำเนา `docker-compose.prod.yml`, `Caddyfile` และบันทึก image ID/digest ปัจจุบัน
- **Expected**: dump ใหม่ + checksum + TOC อ่านได้ · counts เท่ากับ §12 หรืออธิบายส่วนต่างได้
- **Verification**: `sha256sum -c` ผ่าน · `pg_restore --list` ไม่ error
- **Stop condition**: checksum ไม่ตรง หรือ TOC อ่านไม่ได้ → หยุด ห้ามไปขั้นต่อไป
- **Rollback**: ไม่ต้อง (อ่านอย่างเดียว + สร้างไฟล์ใหม่)

### ขั้น 3 — เตรียม artifact (ปิด B4, B5)  `FUTURE — DO NOT EXECUTE IN THIS AUDIT`

- **Target**: docker image store บนเซิร์ฟเวอร์
- **Prerequisite**: ขั้น 2 ผ่าน
- **Action**:
  1. **เก็บอิมเมจ frontend ที่รันอยู่ก่อน** — `docker commit course-advisor-system-frontend-1
     course-advisor-system-frontend:rollback-predeploy3d`
  2. tag อิมเมจ backend ที่รันอยู่ — `docker tag <IMAGE_ID> course-advisor-system-backend:rollback-predeploy3d`
     (`<IMAGE_ID>` จาก `docker inspect … --format '{{.Image}}'`)
  3. build backend และ frontend จาก revision `617110e975dccc94b5e67f77990e34a071ccf9a0`
     พร้อม label revision
  4. **สร้างอิมเมจ worker** — ต้องเขียน `Dockerfile` ใหม่ที่ลง `pipeline/requirements.txt`
     และคัดลอก `pipeline/` + `llm/` (ยังไม่มีไฟล์นี้ในโปรเจค → เป็นงานเพิ่มที่ต้องอนุมัติ)
- **Expected**: มี tag rollback ของทั้งสอง service · มีอิมเมจ worker ที่ `python -c "import fitz, psycopg, pgvector"` ผ่าน
- **Verification**: `docker images` แสดง tag ครบ · ตรวจแพ็กเกจในอิมเมจ worker ด้วย `pip show`
- **Stop condition**: `docker commit` ของ frontend ไม่สำเร็จ → **หยุด** เพราะจะย้อนไม่ได้
- **Rollback**: ลบ tag/อิมเมจใหม่ ไม่กระทบ service ที่รันอยู่

### ขั้น 4 — เตรียม staging และ mounts (ปิด B3, B7)  `FUTURE — DO NOT EXECUTE IN THIS AUDIT`

- **Target**: filesystem + `docker-compose.prod.yml`
- **Prerequisite**: ขั้น 3 ผ่าน
- **Action**: ตาม §6.4 (โอนตาม manifest + ตรวจ sha256 + ตั้งสิทธิ์) แล้วแก้ compose
  เพิ่มให้ backend: `CRAWL_STAGING_DIR=<STAGING_IN_CONTAINER>` และ mount staging `:ro`
- **Expected**: ไฟล์ทุกไฟล์ sha ตรง manifest · mode 644 · โฟลเดอร์ 755
- **Verification (read-only)**: นับไฟล์ + `sha256sum -c` + `docker exec backend ls -l <path>`
  (หลัง recreate ในขั้น 6 เท่านั้น)
- **Stop condition**: sha ไม่ตรงแม้ไฟล์เดียว → หยุด
- **Rollback**: ลบตาม manifest (§6.6) · คืน compose จากสำเนา

### ขั้น 5 — Apply migration 004  `FUTURE — DO NOT EXECUTE IN THIS AUDIT`

- **Target**: postgres `course_advisor`
- **Prerequisite**: ขั้น 2 ผ่าน (มี backup สด) · ยืนยันว่าไม่มี crawler run กำลังทำงาน
- **Action**: apply `db/migrations/004_crawl_decisions.sql` ด้วย superuser โดย
  **ตั้ง `lock_timeout` ก่อน** (เพราะมี `GRANT` ที่ต้อง `AccessExclusiveLock` บน `mko.crawl_sources`)
- **Expected**: ledger มี `004_crawl_decisions` · `mko` = 20 table / 8 view · index 4 ตัวบนตารางใหม่
  · `courses/course_documents/course_chunks` = 24/31/9039 **ไม่เปลี่ยน** · `crawl_decisions` 0 แถว
  · grant ใหม่ปรากฏใน `information_schema.role_table_grants` และ column grant ใน `pg_attribute.attacl`
- **Verification (read-only)**: ตาราง §17
- **Stop condition**: counts ของ knowledge tables เปลี่ยน · object ไม่ครบ · grant ขาด → หยุดและใช้ R1
- **Rollback**: R1 (§11.3) — ทำได้เฉพาะตอน `crawl_decisions` ยังว่าง

### ขั้น 6 — Deploy backend แล้วจึง frontend  `FUTURE — DO NOT EXECUTE IN THIS AUDIT`

- **Target**: service `backend` แล้ว `frontend`
- **Prerequisite**: ขั้น 5 ผ่าน (schema ใหม่ต้องมาก่อนแอปใหม่ — §4.4)
- **Action**: recreate `backend` ด้วยอิมเมจใหม่ · ตรวจให้ผ่าน · แล้วจึง recreate `frontend`
- **Expected**: `/health` 200 · `/crawl-review/pending` ตอบ **401** เมื่อไม่ส่ง token (ไม่ใช่ 404/500)
  · route เดิมยังทำงาน · หน้าเว็บทางเลข IP เปิด `/crawl-review` ได้ (แสดงหน้าเข้าสู่ระบบ)
- **Verification (read-only)**: ตาราง §17
- **Stop condition**: `/health` ไม่ 200 · route เดิมพัง · `/crawl-review/pending` ตอบ 500 → R2/R3
- **Rollback**: R2 แล้ว R3

### ขั้น 7 — ตั้งบัญชีผู้ดูแล (ปิด B1)  `FUTURE — DO NOT EXECUTE IN THIS AUDIT`

- **Target**: `public.users`
- **Prerequisite**: ขั้น 6 ผ่าน · เจ้าของโปรเจคเลือกบัญชีเอง
- **Action**: **เจ้าของโปรเจคเป็นผู้รัน** `UPDATE users SET is_admin = true WHERE email = :email`
  ด้วยค่าที่เขาพิมพ์เอง · บันทึกค่าเดิมไว้ก่อน · **ไม่ใส่ identity ลงบันทึกหรือรายงาน**
- **Expected**: `admin_active` เปลี่ยน 0 → 1
- **Verification (read-only)**: `SELECT count(*) FILTER (WHERE is_admin AND is_active) FROM users`
  และทดสอบว่า `/crawl-review/pending` ด้วย token ของบัญชีนั้นได้ 200 ส่วนบัญชีอื่นได้ 403
- **Stop condition**: `admin_active` ไม่เป็น 1 หรือเปลี่ยนเกินหนึ่งบัญชี → R4
- **Rollback**: R4

### ขั้น 8 — ตรวจ review UI/API และเลือกงานหนึ่งรายการ  `FUTURE — DO NOT EXECUTE IN THIS AUDIT`

- **Target**: frontend + backend
- **Prerequisite**: ขั้น 7 ผ่าน · **B2 ถูกปลด** (มีแถวที่ `staging_path IS NOT NULL` และ
  `status IN ('new','changed','downloaded')`)
- **Action**: ผู้ดูแลเปิด `/crawl-review` ดูคิว เปิด PDF แล้ว**เลือก**หนึ่งรายการ
  · **การกด approve เป็น mutation ต้องอนุมัติในรอบนั้นแยก**
- **Expected**: คิวแสดงรายการได้ · เปิด PDF ได้ (ต้องตั้ง `CRAWL_STAGING_DIR` แล้ว)
  · response ไม่มี `staging_path`
- **Verification (read-only)**: `SELECT count(*) FROM mko.v_crawl_queue` · ตรวจ body ที่ตอบกลับ
- **Stop condition**: เปิด PDF ไม่ได้ → ตรวจ path/permission ก่อน ห้ามกด approve
- **Rollback**: ถ้า approve ไปแล้วและต้องถอน ใช้ `/crawl-review/{id}/undo` (ทำได้ก่อน ingest)

### ขั้น 9 — ตรวจ Ollama และสัญญา embedding จากเครือข่ายของ worker  `FUTURE — DO NOT EXECUTE IN THIS AUDIT`

- **Target**: คอนเทนเนอร์ worker ชั่วคราว
- **Prerequisite**: ขั้น 3 ผ่าน (มีอิมเมจ worker)
- **Action**: จากคอนเทนเนอร์ worker เรียก `GET http://ollama:11434/api/tags` (metadata)
  และตรวจ `atttypmod` ของ `course_chunks.embedding`
- **Expected**: HTTP 200 · มี `bge-m3` · dim 1024
- **Verification**: เท่ากับ Action (อ่านอย่างเดียว)
- **Stop condition**: ติดต่อไม่ได้ หรือไม่มี `bge-m3` → หยุด ห้ามรัน worker
- **หมายเหตุ**: การยืนยันว่า `bge-m3` คืนเวกเตอร์ 1024 มิติจริงต้องเรียก embedding ซึ่งเป็น
  inference — **เป็นงานของขั้น 10** ที่ worker ทำเองก่อนเขียนอะไรลงคลัง ไม่ทำแยกในขั้นนี้

### ขั้น 10 — รัน worker หนึ่งงาน  `FUTURE — DO NOT EXECUTE IN THIS AUDIT`

- **Target**: คอนเทนเนอร์ worker ชั่วคราว (`--rm`) บน network `course-advisor-system_default`
- **Prerequisite**: ขั้น 5–9 ผ่านทุกข้อ · มี backup สด · บันทึก baseline ล่าสุดไว้แล้ว
- **Action (โครง ต้องเติม placeholder ด้วยค่าที่ resolve แบบอ่านอย่างเดียว)**:

```
FUTURE — DO NOT EXECUTE IN THIS AUDIT
docker run --rm \
  --network course-advisor-system_default \
  --env-file <ENV_FILE_PATH>            # Docker อ่านเอง ไม่ต้องพิมพ์ค่า
  -e EMBED_MODEL=bge-m3 -e EMBED_DIM=1024 \
  -e OLLAMA_BASE_URL=http://ollama:11434 \
  -e CRAWL_STAGING_DIR=<STAGING_IN_CONTAINER> \
  -e DOCUMENTS_DIR=<DOCUMENTS_IN_CONTAINER> \
  --user <UID:GID ที่ทำให้ไฟล์ world-readable>  \
  -v <STAGING_HOST>:<STAGING_IN_CONTAINER>:ro \
  -v <DOCUMENTS_HOST>:<DOCUMENTS_IN_CONTAINER>:rw \
  -v <CODE_HOST>:/work -w /work \
  <WORKER_IMAGE> \
  sh -c 'CRAWL_DATABASE_URL=… python -u -m pipeline.crawl.approve --max-jobs 1'
```

- `INGEST_DATABASE_URL` ต้องมาจาก `--env-file` ไม่พิมพ์ค่า (วิธีเดียวกับที่ใช้ใน
  `docs/CRAWLER_PRODUCTION_VERIFY_REPORT.md`)
- รันแบบ detach เขียน log ลงไฟล์ (`nohup … > run.log 2>&1 &`) ไม่ pipe ผ่าน ssh
- **Expected**: exit 0 · `course_documents` +1 · `course_chunks` +N (N > 0) · `courses` **ไม่เปลี่ยน**
  · `crawl_decisions`: `document_id` ไม่ว่าง, `ingest_finished_at` ไม่ว่าง, `ingest_error` ว่าง
  · `crawl_sources`: `status='ingested'` หนึ่งแถว · มีไฟล์ใหม่ใน documents หนึ่งไฟล์ (หรือใช้ของเดิมซ้ำ)
- **Verification (read-only)**: ตาราง §17 · อ่าน `run.log` โดย redact
- **Stop condition**: exit ไม่เป็น 0 · counts ไม่ตรงที่คาด · `ingest_error` ไม่ว่าง
  → **หยุด ไม่รันงานถัดไป** ใช้ R6
- **Duplicate prevention**: `--max-jobs 1` + เงื่อนไขยึดงาน + `already_ingested()`
- **Rollback**: R6 (§11.4)

### ขั้น 11 — รีเฟรช `document_store`  `FUTURE — DO NOT EXECUTE IN THIS AUDIT`

- **Target**: service `backend` (ชื่อจากหลักฐาน: `course-advisor-system-backend-1`)
- **Prerequisite**: ขั้น 10 สำเร็จและไฟล์อยู่ใน documents แล้ว
- **Action**: **ไม่มี endpoint รีเฟรช** (ค้นแล้วไม่มี — §7) วิธีเดียวคือเริ่มโปรเซสใหม่
  `docker compose -f docker-compose.prod.yml restart backend` (หรือ `up -d --force-recreate backend`)
- **Expected**: บริการกลับมาใน < 30 วินาที
- **Verification (read-only)**: `/health` 200 · `GET /documents/<NEW_DOCUMENT_ID>/pdf` ได้ 200
  และ `content-type: application/pdf` · เอกสารเดิมยังเปิดได้
- **Stop condition**: `/health` ไม่กลับมา → R7 · เปิดเอกสารใหม่ไม่ได้ → ตรวจสิทธิ์ไฟล์ (R-7)
- **Rollback**: R7

### ขั้น 12 — ตรวจ end-to-end แล้วหยุด  `FUTURE — DO NOT EXECUTE IN THIS AUDIT`

- **Target**: ทั้งระบบ
- **Action**: เทียบ counts กับ baseline + delta ที่คาด · ตรวจ mounts · ตรวจ auth (401/403/200)
  · ตรวจว่าบริการทุกตัวยัง `Up` · ถามคำถามที่ต้องใช้เอกสารใหม่เพื่อดูว่า RAG เห็นข้อมูลแล้ว
- **Stop condition**: อะไรไม่ตรง → หยุดและรายงาน
- **ห้าม**: เพิ่ม scheduler · ขยายเป็น bulk ingestion · รัน worker งานที่สอง

---

## 17. Verification commands / checks

### ตาราง A — `SAFE READ-ONLY NOW` (ใช้ในรอบนี้แล้ว และใช้ recheck ได้)

| # | Working dir / env | คำสั่ง | สิ่งที่คาดว่าได้ |
|---|---|---|---|
| A1 | เครื่องพัฒนา · repo root | `git status --short --branch` | บรรทัดแรก `## mko-phase2...origin/mko-phase2` และไม่มีบรรทัด ` M`/` A` |
| A2 | เดียวกัน | `git rev-parse HEAD` | `617110e975dccc94b5e67f77990e34a071ccf9a0` |
| A3 | เดียวกัน | `git branch --show-current` | `mko-phase2` |
| A4 | เดียวกัน | `git rev-list --parents -n 1 HEAD` | สอง hash (parent 1 ตัว) |
| A5 | เดียวกัน | `git diff --name-status` / `git diff --cached --name-status` | ว่างทั้งคู่ |
| A6 | เดียวกัน | `git show --name-only --format= 617110e` | สองไฟล์ ไม่มี `pipeline/ingest.py` |
| A7 | เดียวกัน | `git ls-remote origin refs/heads/mko-phase2` | hash เดียวกับ A2 (**ไม่ fetch**) |
| A8 | เซิร์ฟเวอร์ | `sudo docker ps --format '{{.Names}}\|{{.Image}}\|{{.Status}}'` | 7 คอนเทนเนอร์ `Up` |
| A9 | เซิร์ฟเวอร์ | `sudo docker inspect <ชื่อ> --format '{{.Image}}'` | image id (เฉพาะ field นี้) |
| A10 | เซิร์ฟเวอร์ | `sudo docker inspect course-advisor-system-backend-1 --format '{{range .Mounts}}{{.Source}} {{.Destination}} {{.RW}}{{"\n"}}{{end}}'` | documents → /srv/documents, RW=false |
| A11 | เซิร์ฟเวอร์ | `sudo docker exec course-advisor-system-backend-1 printenv EMBED_MODEL EMBED_DIM DOCUMENTS_DIR` | `bge-m3` / `1024` / `/srv/documents` |
| A12 | เซิร์ฟเวอร์ | `sudo docker exec … pip --disable-pip-version-check list \| grep -iE '^(psycopg\|pgvector\|PyMuPDF)'` | psycopg, pgvector มี · PyMuPDF ไม่มี |
| A13 | เซิร์ฟเวอร์ | `sudo docker exec … python -c "import httpx; print(httpx.get('http://ollama:11434/api/tags').status_code)"` | `200` (metadata เท่านั้น) |
| A14 | เซิร์ฟเวอร์ | `df -h /` และ `df -i /` | ว่าง ~65 G · inode ใช้ 3% |
| A15 | เซิร์ฟเวอร์ | `ls -lt /home/ubuntu/backups/*.dump \| head -3` | dump ใหม่สุด 2026-09-17 |
| A16 | เซิร์ฟเวอร์ | `sudo docker exec course-advisor-system-caddy-1 sha256sum /etc/caddy/Caddyfile` | ตรงกับไฟล์บน host |
| A17 | postgres | SQL block ใน `BEGIN TRANSACTION READ ONLY` (ดูด้านล่าง) | ตาม §4.1, §5.1, §12 |

SQL ที่ใช้ (ทุกครั้งต้องอยู่ใน read-only transaction พร้อม timeout · **ไม่ใส่ DSN/รหัสผ่านในคำสั่ง**
เพราะเชื่อมผ่าน unix socket ใน `docker exec`)

```sql
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout = '15s';
SET LOCAL lock_timeout = '3s';

SELECT version, applied_at FROM mko.schema_migrations ORDER BY version;
SELECT table_schema, table_type, count(*) FROM information_schema.tables
 WHERE table_schema IN ('public','mko') GROUP BY 1,2 ORDER BY 1,2;
SELECT to_regclass('mko.crawl_decisions') IS NOT NULL,
       to_regclass('mko.v_crawl_queue')  IS NOT NULL;
SELECT 'courses' t, count(*) FROM courses
 UNION ALL SELECT 'course_documents', count(*) FROM course_documents
 UNION ALL SELECT 'course_chunks',    count(*) FROM course_chunks
 UNION ALL SELECT 'mko.crawl_sources',count(*) FROM mko.crawl_sources ORDER BY 1;
SELECT status, count(*), count(*) FILTER (WHERE staging_path IS NOT NULL)
  FROM mko.crawl_sources GROUP BY 1;
SELECT count(*) FILTER (WHERE is_admin AND is_active) AS admin_active FROM users;
SELECT atttypmod FROM pg_attribute
 WHERE attrelid='course_chunks'::regclass AND attname='embedding';
SELECT grantee, table_schema||'.'||table_name,
       string_agg(DISTINCT privilege_type, ',' ORDER BY privilege_type)
  FROM information_schema.role_table_grants
 WHERE grantee IN ('advisor_api','advisor_ingest')
   AND (table_schema='mko' OR table_name IN ('courses','course_documents','course_chunks','users'))
 GROUP BY 1,2 ORDER BY 2,1;
COMMIT;
```

### ตาราง B — `FUTURE — DO NOT EXECUTE IN THIS AUDIT`

| # | Target | คำสั่ง (ต้องได้อนุมัติแยกก่อนรัน) |
|---|---|---|
| B-1 | postgres | `pg_dump -Fc` + `sha256sum` + `pg_restore --list` |
| B-2 | image store | `docker commit course-advisor-system-frontend-1 course-advisor-system-frontend:rollback-predeploy3d` |
| B-3 | image store | `docker tag <BACKEND_IMAGE_ID> course-advisor-system-backend:rollback-predeploy3d` |
| B-4 | build | build backend/frontend จาก `617110e975…` พร้อม label revision |
| B-5 | build | สร้าง Dockerfile + อิมเมจ worker จาก `pipeline/requirements.txt` |
| B-6 | filesystem | โอน staging ตาม manifest แล้วตั้งสิทธิ์ |
| B-7 | compose | เพิ่ม `CRAWL_STAGING_DIR` + mount staging `:ro` ให้ backend |
| B-8 | postgres | apply `004_crawl_decisions.sql` (ตั้ง `lock_timeout` ก่อน) |
| B-9 | services | recreate `backend` แล้ว `frontend` |
| B-10 | postgres | `UPDATE users SET is_admin = true WHERE email = :email` (**เจ้าของโปรเจครัน**) |
| B-11 | worker | `docker run --rm … python -u -m pipeline.crawl.approve --max-jobs 1` |
| B-12 | services | `docker compose … restart backend` (รีเฟรช `document_store`) |
| B-13 | Caddy (ทางเลือก) | เพิ่ม `handle /crawl-review*` แล้ว `caddy validate` ก่อน recreate |

---

## 18. Stop / rollback criteria

หยุดทันทีและไม่ไปขั้นถัดไป เมื่อ

1. **revision drift** — HEAD หรือ `git ls-remote` ไม่ใช่ `617110e975dccc94b5e67f77990e34a071ccf9a0`
2. **migration state ไม่ตรง** — ledger ไม่ใช่ 001–003 หรือพบ object ของ 004 อยู่ก่อน apply
3. **backup/recovery ยังไม่ยืนยัน** — checksum ไม่ตรง หรือ `pg_restore --list` error
4. **grant/auth ไม่พร้อม** — grant ของ 004 ไม่ครบ หรือ `admin_active ≠ 1` หลังขั้น 7
5. **path/mount ไม่ตรง** — `staging_path` ในฐานข้อมูลไม่อยู่ใต้ `CRAWL_STAGING_DIR` ที่ mount
6. **disk ไม่พอ** — ว่าง < 5 G หรือ inode ใช้ > 80%
7. **runtime dependency ขาด** — อิมเมจ worker `import fitz` ไม่ผ่าน
8. **embedding ไม่ตรงสัญญา** — `EMBED_MODEL ≠ bge-m3`, `EMBED_DIM ≠ 1024`, `atttypmod ≠ 1024`
   หรือ `bge-m3` ไม่อยู่ใน `/api/tags`
9. **worker จำกัดหนึ่งงานไม่ได้** — `--max-jobs` ไม่ทำงาน หรือมีสัญญาณว่ายึดเกินหนึ่งงาน
10. **rollback แยกข้อมูลไม่ได้** — ไม่ทราบ `document_id` ของงานที่รัน
11. **counts ของ knowledge tables เปลี่ยนโดยไม่คาด** ในขั้นที่ไม่ควรเปลี่ยน
12. **critical evidence ยัง `UNKNOWN`**

กฎการ rollback

- ใช้ rollback ที่ผูกกับ checkpoint ของขั้นนั้นเท่านั้น (R1–R7 §11.3)
- **ห้าม retry mutation แบบสุ่ม** — ต้องเข้าใจสาเหตุก่อน
- **ห้าม rollback schema/DB ที่มีข้อมูลใหม่หรือมี concurrent write** โดยไม่ประเมินและไม่มีคนอนุมัติ
- เก็บหลักฐาน (log, counts, เวลา) ทุกครั้งก่อน rollback

---

## 19. Files / repository status

### ก่อน audit (เวลา 08:44 +07)

```
branch      mko-phase2
HEAD        617110e975dccc94b5e67f77990e34a071ccf9a0
tracked     git diff --name-status        → 0 รายการ
staged      git diff --cached --name-status → 0 รายการ
untracked   39 รายการ ทั้งหมดอยู่ใน docs/ (รายงานของเฟสก่อน)
```

### หลัง audit

```
branch      mko-phase2                                       (ไม่เปลี่ยน)
HEAD        617110e975dccc94b5e67f77990e34a071ccf9a0          (ไม่เปลี่ยน)
tracked     0 รายการ                                          (ไม่เปลี่ยน)
staged      0 รายการ                                          (ไม่เปลี่ยน)
untracked   40 รายการ — เพิ่มขึ้น 1 คือรายงานฉบับนี้
```

ไฟล์ที่รอบนี้สร้าง — **หนึ่งไฟล์เท่านั้น**

```
docs/AUTOMATED_INGESTION_PHASE3D_PREDEPLOY_AUDIT.md   (untracked)
```

การเปลี่ยนแปลงที่มีอยู่เดิม (ไม่ใช่ของรอบนี้): ไม่มี tracked change เลย · untracked 39 รายการ
ใน `docs/` เป็นรายงานของเฟสก่อนซึ่ง**ไม่ได้แตะในรอบนี้**

### ยืนยัน

- **ไม่ได้ `git add` ในรูปแบบใดเลย · ไม่ commit · ไม่ push · ไม่ stage**
- **ไม่ได้ `git fetch`** — ตรวจ origin ด้วย `git ls-remote` ตามข้อกำหนด
- **ไม่ได้ checkout/reset/clean/stash** และไม่แก้ source/dependency/lockfile ใด
- **ไม่ได้แก้ production**: ไม่ migration · ไม่เขียนฐานข้อมูล · ไม่สร้าง/แก้ admin ·
  ไม่ upload/copy/move ไฟล์เข้า production · ไม่สร้าง backup ใหม่ ·
  ไม่ deploy/build/recreate/restart service หรือ container · ไม่รัน worker ·
  ไม่ ingestion/embedding · ไม่แก้ Caddy · ไม่แก้ env · ไม่เพิ่ม scheduler · ไม่แตะ Supabase ·
  ไม่ merge `main`
- **ไม่ได้อ่านหรือพิมพ์ secret**: ไม่เปิด `.env` · ไม่ dump process environment (อ่านเฉพาะ
  `EMBED_MODEL`, `EMBED_DIM`, `DOCUMENTS_DIR`, `STRUCTURED_ANSWERS` ซึ่งไม่เป็นความลับ
  และตรวจ `CRAWL_STAGING_DIR` ว่า "ตั้งไว้ไหม" โดยไม่อ่านค่า) · ไม่ `docker inspect` เต็มชุด
  (เลือก field ทีละตัว) · ไม่พิมพ์ remote URL · ไม่เปิดเนื้อหา backup
- **DB query ทุกตัวอยู่ใน `BEGIN TRANSACTION READ ONLY`** พร้อม `statement_timeout`/`lock_timeout`
  และไม่มี function ที่มี side effect
- **ไม่ได้รัน worker หรือ `--help` ของ worker** — ข้อมูล CLI/env/exit code มาจากการอ่าน source
- **ไม่ได้รัน test ใด** ในรอบนี้
- คำสั่งเดียวที่ยิงออกเครือข่ายภายนอกคือ `git ls-remote` (อ่าน ref) และ
  `GET http://ollama:11434/api/tags` ภายในเครือข่ายของ compose ซึ่งเป็น metadata
  ไม่ generate ไม่ pull ไม่โหลดโมเดล

---

**รอบนี้ตรวจแบบ read-only และสร้างรายงานใน local workspace เท่านั้น ไม่มีการเปลี่ยนแปลง Production ใด ๆ และหยุดรอ human review ก่อนดำเนิน Phase 3D ขั้นถัดไป**
