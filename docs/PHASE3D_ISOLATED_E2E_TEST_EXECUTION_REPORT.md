# Phase 3D — Isolated E2E Test Execution Report

| | |
|---|---|
| วันที่ | 2026-09-29 · ช่วงทำงาน **21:5x–22:4x UTC** (ไทย 2026-09-30 ราว 04:5x–05:4x) |
| สถานที่รัน | **เครื่อง Windows ของผู้พัฒนา** · Docker Desktop 4.86.0 · engine 29.7.2 · compose 5.3.1 |
| compose project | `sci-advisor-e2e` (แยกจาก `course-advisor-system` โดยสมบูรณ์) |
| ผลการทดสอบ | **102 / 102 PASS · 0 FAIL · exit 0** |
| **ISOLATED E2E PIPELINE** | **PASS** |
| **PRODUCTION SAFETY** | **PASS** — ทุกค่าตรง baseline · ไม่มีบริการใดถูก restart |
| **PRODUCTION ONE-JOB INGESTION** | **ยัง NO-GO** |
| ข้อบกพร่องที่พบ | **1 blocker** ของขั้นตรวจสอบโดยคน + **1 ข้อสังเกตเชิงพฤติกรรม** (ข้อ 25) |

> **การที่ E2E ผ่าน ไม่ใช่การอนุญาตให้รัน ingestion บน production**
> PRODUCTION CANDIDATE (PDF ใหม่/เปลี่ยนจริงจาก `sci.pnru.ac.th`) กับ TEST CANDIDATE
> (PDF จำลองในสภาพแวดล้อมแยก) เป็นคนละเรื่องและห้ามนำมาปนกัน

---

## 1. Local preflight

| ข้อตรวจ | ผล |
|---|---|
| repo path | `D:\workspace\course-advisor-system-mko2` |
| branch | `mko-phase2` |
| HEAD | `2fdc6f241fc1742047b572ee2ef354cd811f9401` |
| `origin/mko-phase2` (live) | `2fdc6f241fc1742047b572ee2ef354cd811f9401` — ตรง |
| `origin/main` (live) | `b78b3f8bf895685874d9a52c66b45569072f0514` — ไม่แตะ |
| staged / tracked modified | 0 / 0 |
| untracked นอก `docs/` ตอนเริ่ม | 0 |
| **Docker Desktop** | **ไม่ได้ทำงานตอนเริ่ม** → เปิดให้ (ดูข้อ 25 รายการ D1) · engine พร้อมใน 5 วินาที |
| docker / compose | client 29.7.2 · server 29.7.2 · linux/amd64 · compose 5.3.1 |
| ทรัพยากรของ Docker | CPU 16 · RAM 7.95 GB · storage driver overlayfs |
| ทดสอบรัน `hello-world` | สำเร็จ |
| ดิสก์ `D:` | ว่าง 488G / 954G |
| project `sci-advisor-e2e` ค้างจากรอบก่อน | **ไม่มี** (container 0 · volume 0 · network 0) |
| `.env` ของ production ในเครื่องนี้ | **ไม่มีเลย** — repo มีแต่ `.env.example` จึงไม่มี credential ของ production ให้เผลอใช้ |

**ไม่ได้ย้ายไปรันบนเซิร์ฟเวอร์ production** ตามข้อห้าม

---

## 2. Source revision ที่ทดสอบ

ตรวจไฟล์ที่ Design พึ่งพาครบ 21 ไฟล์ (sha256 12 ตัวแรกของ blob ที่ HEAD)

```
pipeline/crawl/discover.py        022f2dcff611    backend/app/services/crawl_review.py    cdcef63306d6
pipeline/crawl/sync.py            7b574f64933c    backend/app/services/staging_store.py   ea74e2daef46
pipeline/crawl/http.py            6c61fed8430e    backend/app/services/vector_search.py   f10968eee2a1
pipeline/crawl/state.py           0e2fb0796a47    backend/app/core/security.py            55009036fa68
pipeline/crawl/approve.py         c9d73c8217d4    backend/app/api/routes/crawl_review.py  060b04bee0ff
pipeline/ingest.py                90a03872cc88    db/schema.sql                           cfde99685f11
pipeline/embed.py                 c36bf39dabc8    db/20-roles.sh                          c3c4148a4a3c
pipeline/chunker.py               4c050afb3c5c    db/migrations/001_mko_structured.sql    30cf10174d6c
pipeline/extract_pdf.py           5f2290488d80    db/migrations/002_mko_review_publish.sql 93a08af89927
llm/connector.py                  e68ce71e191e    db/migrations/003_crawl_sources.sql     dd2add2937c9
                                                  db/migrations/004_crawl_decisions.sql   0a689ea3dbe8
```

ข้อเท็จจริงที่ Design พึ่งพา — ตรวจซ้ำแล้วยังจริงทุกข้อ

| ข้อ | ผล |
|---|---|
| `discover.crawl()` รับ `seeds` เป็นพารามิเตอร์ | ใช่ |
| `ALLOWED_SCHEMES = {"http","https"}` | ใช่ |
| `ALLOWED_PORTS = {None, 80, 443}` | ใช่ |
| `ALLOWED_HOSTS = {"sci.pnru.ac.th"}` | ใช่ |
| `httpx.Client(...)` ไม่ตั้ง `verify=` | ใช่ → ไม่ต้องทำ TLS |
| `resolve_course` ต้องมี course อยู่ก่อน | ใช่ |
| `ivfflat ... WITH (lists = 100)` | ใช่ |
| `REQUIRED_EMBED_MODEL = "bge-m3"` | ใช่ |
| `FOLLOW = [r"/program_detail\.php\?id=\d+", r"/programs\.php$"]` | ใช่ |

---

## 3. Production baseline **ก่อน** E2E (READ-ONLY)

วัดจริงเมื่อ **2026-09-29T22:09:29Z** — ไม่ได้ใช้ค่าจากรายงานเก่า

| รายการ | ค่า |
|---|---|
| users / active / admins | 198 / 198 / 1 |
| courses | 24 |
| course_documents | 31 |
| course_chunks | 9039 |
| crawl_sources | 12 · unchanged 12 · needs_review 6 · staging_path ไม่ null 0 |
| crawl_decisions | 0 |
| v_crawl_queue | 6 |
| chat_messages / chat_answer_cache | 6640 / 160 |
| embedding dimension | 1024 |
| courses code LIKE `TEST%` | **0** |
| migrations | 001, 002, 003, 004_crawl_decisions |
| staging files | 0 |
| documents PDF | 30 |

---

## 4. ไฟล์ทดสอบที่สร้าง (6 ไฟล์ · 84 KB)

```
eval/e2e/docker-compose.e2e.yml     นิยามสภาพแวดล้อมทดสอบ 5 บริการ · network alias · volume แยก
eval/e2e/fakesite/server.py         เว็บจำลองของคณะ · รองรับ GET และ HEAD
eval/e2e/make_test_pdf.py           สร้าง TEST_CS_CURRICULUM_E2E.pdf ด้วย PyMuPDF
eval/e2e/seed.py                    apply migrations 001-004 · seed TEST101 + ผู้ใช้ทดสอบ · ด่านความปลอดภัย
eval/e2e/run_e2e.py                 ชุดทดสอบหลัก 102 assertions · เรียกโค้ด production ตัวจริง
eval/e2e/README.md                  คู่มือ · คำเตือน · ข้อจำกัด
```

**ไม่ได้แก้ไฟล์ production แม้ไบต์เดียว** — `backend/`, `pipeline/`, `llm/`, `db/schema.sql`,
`db/migrations/`, `docker-compose.prod.yml`, `docker-compose.staging.yml`,
`docker-compose.worker.yml`, `Caddyfile`, `.env` ทั้งหมดไม่ถูกแตะ
(ยืนยันด้วย `git diff --name-only` = 0 ไฟล์)

---

## 5. Isolation proof

| ข้อพิสูจน์ | ผล |
|---|---|
| compose project | ทั้งห้าคอนเทนเนอร์มี label `com.docker.compose.project=sci-advisor-e2e` |
| network | ทุกตัวอยู่บน `sci-advisor-e2e_default` **เท่านั้น** |
| **พอร์ตที่ publish ออก host** | **ไม่มีเลยสักบริการ** (`5432/tcp`, `11434/tcp`, `8000/tcp` = ไม่ publish · fakesite/runner ไม่มีพอร์ต) |
| bind mount ที่มีคำว่า `home/ubuntu` | **0** |
| volume | `sci-advisor-e2e_*` ทั้งหมด (pgdata, ollama, site, staging, documents, out) |
| bind mount เดียวที่มี | repo ของผู้พัฒนา `D:\workspace\course-advisor-system-mko2` แบบ **:ro** และ `db/schema.sql`, `db/20-roles.sh` แบบ **:ro** |
| `sci.pnru.ac.th` จากคอนเทนเนอร์ทดสอบ | `172.19.0.4` = IP ของ `e2e-fakesite` พอดี |
| ชื่อบริการของ production จากคอนเทนเนอร์ทดสอบ | `postgres`, `backend`, `ollama`, `caddy`, `frontend`, `webapi` → **resolve ไม่ได้ทั้งหก** |
| ด่าน DSN ชั้นที่ 1 | DSN ที่มี `course_advisor` → `IsolationError` |
| ด่าน DSN ชั้นที่ 2 | `SELECT current_database()` = `e2e_test` |
| ด่าน DSN ชั้นที่ 3 | `course_chunks > 1000` → ปฏิเสธ (production มี 9039) |
| `.env` ของ production | ไม่ถูกใช้ — ไม่มีไฟล์นี้บนเครื่องผู้พัฒนาเลย |

**หลักฐานจาก log ของเว็บจำลอง** — คำขอของ crawler ไปที่เว็บจำลองจริง ไม่ใช่เว็บคณะ

```
[fakesite] "GET /programs.php HTTP/1.1" 200
[fakesite] "GET /robots.txt HTTP/1.1" 404
[fakesite] "GET /program_detail.php?id=1 HTTP/1.1" 200
[fakesite] "HEAD /TEST_CS_CURRICULUM_E2E.pdf HTTP/1.1" 200
[fakesite] "GET /TEST_CS_CURRICULUM_E2E.pdf HTTP/1.1" 200
รวมคำขอที่เว็บจำลองรับตลอดการทดสอบ: 28 ครั้ง
```

---

## 6. Topology ของสภาพแวดล้อมทดสอบ

```
network sci-advisor-e2e_default (bridge · 172.19.0.0/16 · ไม่ผูกกับเครือข่ายอื่น)

  e2e-postgres   pgvector/pgvector:pg16      DB=e2e_test  · initdb ด้วย schema.sql + 20-roles.sh ของ production
  e2e-ollama     ollama/ollama:latest        bge-m3:latest ID 790764642607
  e2e-fakesite   python:3.11-slim            alias: sci.pnru.ac.th   <-- ทำให้ crawler ตัวจริงผ่าน ALLOWED_HOSTS
  e2e-backend    build จาก backend/Dockerfile   staging :ro · documents :ro · WARMUP_INTERVAL_MINUTES=0
  e2e-runner     build จาก pipeline/Dockerfile  staging :rw · documents :rw · site :rw · /repo :ro

ไม่มีบริการใด publish พอร์ตออกสู่ host — harness รันอยู่ใน e2e-runner จึงเรียกทุกอย่างด้วยชื่อ service
```

**bge-m3 ใน test ollama มี ID `790764642607` ซึ่งเป็นค่าเดียวกับของ production**
(`ollama list` ของ production แสดง `bge-m3:latest 790764642607 1.2 GB`) — โมเดลเดียวกัน

---

## 7. ผลการ seed ฐานข้อมูลทดสอบ

migrations ที่ apply: `001_mko_structured` · `002_mko_review_publish` ·
`003_crawl_sources` · `004_crawl_decisions`

| assertion | คาด | จริง |
|---|---:|---:|
| courses | 1 | **1** |
| course_documents | 0 | **0** |
| course_chunks | 0 | **0** |
| crawl_sources | 0 | **0** |
| crawl_decisions | 0 | **0** |
| v_crawl_queue | 0 | **0** |
| users | 2 | **2** |
| admins | 1 | **1** |

ผู้ใช้ทดสอบ: `e2e-admin@example.com` (admin) และ `e2e-user@example.com` (ไม่ใช่ admin)
สร้างผ่าน **`POST /auth/register` ของ backend ตัวจริง** แล้วตั้ง `is_admin` ด้วย SQL หนึ่งแถว
รหัสผ่านสุ่มด้วย `secrets.token_urlsafe(18)` **ในหน่วยความจำ ไม่เขียนลงไฟล์ ไม่พิมพ์ ไม่ลงรายงาน**
และหายไปพร้อม volume ตอน cleanup

---

## 8. Test PDF

```
ชื่อไฟล์   TEST_CS_CURRICULUM_E2E.pdf
ขนาด       7,571 ไบต์ · 1 หน้า
sha256     66cf0be5fd24296f20f3688ebad7f205a56cf38215c79268e32bc46d10135d38
marker     E2E-MARKER-TEST101-PIPELINE-VERIFICATION
```

เนื้อหาขึ้นต้นด้วย `TEST DATA / NOT A REAL PNRU CURRICULUM / FOR ISOLATED E2E TEST ONLY`
ไม่มีชื่อหลักสูตรจริง ไม่มีข้อมูลบุคคลจริง ไม่มีตราคณะหรือเลขที่เอกสารจริง

**sha256 คำนวณจากไฟล์จริงทุกครั้ง ไม่ hard-code** — PyMuPDF ฝัง `creationDate`/`modDate`
ลง metadata ทำให้ไบต์ต่างกันทุกครั้งที่สร้าง (สังเกตได้จริงระหว่างการรันซ้ำ:
`4f1081a5…` → `ee02fcec…` → `88a37083…` → `66cf0be5…`) ซึ่งเป็นเหตุผลที่ Design
กำหนดห้าม hard-code ไว้ตั้งแต่แรก

---

## 9. ผลการ crawl

```
เดินเว็บ 2 หน้า · พบลิงก์ PDF 1 · error 0
```

| assertion | คาด | จริง |
|---|---|---|
| พบลิงก์ PDF | 1 | **1** |
| `status` ที่ `process_link` คืน | `downloaded` | **downloaded** |
| `sha256` ที่ crawler คำนวณ | ตรงกับไฟล์ที่สร้าง | **ตรง** |
| `mko.crawl_sources` | 1 แถว | **1** |
| `status` ในฐานข้อมูล | `downloaded` | **downloaded** |
| `file_sha256` ในฐานข้อมูล | ตรง | **ตรง** |
| `staging_path` | ไม่เป็น null | **`/srv/staging/66cf0be5fd24_TEST_CS_CURRICULUM_E2E.pdf`** |
| `needs_review` | true | **true** |
| ไฟล์ staged มีอยู่จริง | ใช่ | **ใช่** |
| sha ของไฟล์ staged | ตรงกับที่บันทึก | **ตรง** |
| `v_crawl_queue` | 1 | **1** |
| `has_staged_file` | true | **true** |
| `match_confidence` | — | `unknown` (ฐานทดสอบไม่มีเอกสารให้จับคู่ จึงตั้งธง `needs_review` ตามที่ควร) |

เส้นทางที่ทดสอบครบ: `robots.txt` 404 → ถือว่าอนุญาต · `HEAD` อ่าน ETag/Content-Length ·
`download()` แบบ streaming · ตรวจ `%PDF-` · เพดาน 50 MB · คำนวณ sha256 ·
`os.replace()` เข้า staging · `upsert` `ON CONFLICT (source_url)`

---

## 10. ผลการทดสอบ authentication

| การทดสอบ | คาด | จริง |
|---|---:|---:|
| anonymous `GET /crawl-review/pending` | 401 | **401** |
| anonymous `GET /crawl-review/{id}` | 401 | **401** |
| anonymous `GET /crawl-review/{id}/pdf` | 401 | **401** |
| non-admin login | 200 | **200** |
| **non-admin `GET /pending`** | **403** | **403** |
| admin login | 200 | **200** |

> **`non-admin → 403` ทดสอบได้สำเร็จเป็นครั้งแรก** — บน production รายการนี้ค้างเป็น
> NOT TESTED มาตลอดเพราะไม่มี session ของผู้ใช้ non-admin ที่ปลอดภัยให้ใช้

---

## 11. ผลการทดสอบ Admin Review

| การทดสอบ | คาด | จริง |
|---|---|---|
| `GET /pending` | 200 · 1 รายการ | **200 · 1** |
| `counts.with_staged_file` | 1 | **1** |
| `GET /{id}` | 200 | **200** |
| payload ไม่เปิดเผย `staging_path` | ไม่มีคีย์นี้ | **ไม่มี** (คีย์ที่คืนมา 19 ตัว ไม่รวม `staging_path`) |
| โหมดไฟล์ staged ที่ crawler สร้าง | — | **`0o600`** uid **1001** |
| **`GET /{id}/pdf` ตามสภาพจริง** | — | **404** ← **ข้อบกพร่อง F1 ดูข้อ 25** |
| `GET /{id}/pdf` หลัง `chmod 644` | 200 | **200** |
| content-type | `application/pdf` | **application/pdf** |
| เนื้อไฟล์ขึ้นต้น | `%PDF-` | **%PDF-** |
| sha ของ PDF ที่ส่งออก | ตรงกับที่ staged | **ตรง** |

คีย์ที่ `GET /{id}` คืนมา (19 ตัว): `content_length, course_code, course_label,
file_sha256, first_seen_at, has_staged_file, id, last_checked_at, link_text,
match_candidates, match_confidence, match_score, needs_review, page_title,
page_url, previous_sha256, review_reason, source_url, status`

---

## 12. ผลการ approve

| การทดสอบ | คาด | จริง |
|---|---:|---:|
| approve ด้วย sha ผิด | 409 | **409** |
| approve ด้วย `course_code = NOPE999` | 422 | **422** |
| `crawl_decisions` หลังกรณีที่ถูกปฏิเสธ | 0 | **0** |
| approve สำเร็จ | 201 | **201** |
| `crawl_decisions` | 1 แถว | **1** |
| `decision` | `approve` | **approve** |
| `superseded_at` | null | **null** |
| `course_code` | `TEST101` | **TEST101** |
| `decided_by` | อีเมลของ admin ทดสอบ | **e2e-admin@example.com** |
| `file_sha256` ของ decision | ตรง | **ตรง** |
| `ingest_started_at` / `ingest_finished_at` / `document_id` | ว่างทั้งสาม | **ว่างทั้งสาม** |
| **approve ซ้ำ** | **409** | **409** (partial unique `uq_crawl_decisions_active`) |
| decision หลัง approve ซ้ำ | ยัง 1 แถว | **1** |
| คิวหลังตัดสินใจ | 0 รายการ | **0** |

---

## 13. ผลการรัน worker

```
worker ใช้เวลา 2.2 วินาที · exit=0

ยึดงาน decision=45cddb47-… source=http://sci.pnru.ac.th/TEST_CS_CURRICULUM_E2E.pdf
POST http://e2e-ollama:11434/api/embeddings  200   <- probe ของ check_embedding_contract
extracting /tmp/ingest_worker_4q25dc__/66cf0be5fd24_TEST_CS_CURRICULUM_E2E.pdf
produced 2 chunks from 1 pages
POST http://e2e-ollama:11434/api/embeddings  200   <- chunk 1
POST http://e2e-ollama:11434/api/embeddings  200   <- chunk 2
ingest complete: course_id=97328c1a-… document_id=18b9a50f-… chunks=2
งานสำเร็จ decision=45cddb47-… · ingested
---- สรุป ---- สำเร็จ 1 · ล้มเหลว 0
```

| assertion | คาด | จริง |
|---|---|---|
| exit code | 0 | **0** |
| `ingest_started_at` | ถูกเติม | **ใช่** |
| `ingest_finished_at` | ถูกเติม | **ใช่** |
| `document_id` | ถูกเติม | **ใช่** |
| `ingest_error` | null | **null** |
| `crawl_sources.status` สุดท้าย | — | **`ingested`** |

---

## 14. ผลการ ingestion

| assertion | คาด | จริง |
|---|---|---|
| `course_documents` | 1 | **1** |
| `extraction_status` | `done` | **done** |
| `file_sha256` ของเอกสาร | ตรงกับที่ approve | **ตรง** |
| `page_count` | ≥ 1 | **1** |
| `document_id` ของ decision | ตรงกับเอกสารที่สร้าง | **ตรง** |
| เอกสารผูกกับ `TEST101` | ใช่ | **ใช่** |
| ไฟล์ถูก publish | 1 ไฟล์ | **1** (`/srv/documents/66cf0be5fd24_TEST_CS_CURRICULUM_E2E.pdf`) |
| sha ของไฟล์ที่ publish | ตรงกับที่ approve | **ตรง** |
| ไฟล์อยู่ใน `DOCUMENTS_DIR` ของ test เท่านั้น | ใช่ | **ใช่** |

---

## 15. จำนวน document / chunk

| รายการ | ก่อน | หลัง |
|---|---:|---:|
| `course_documents` | 0 | **1** |
| `course_chunks` | 0 | **2** |
| `chunk_index` ต่ำสุด | — | **0** |
| chunk ที่ `embedding IS NULL` | — | **0** |

---

## 16. โมเดลและมิติของ embedding

| รายการ | ค่า |
|---|---|
| `EMBED_MODEL` | **bge-m3** |
| `EMBED_DIM` | **1024** |
| โมเดลใน e2e-ollama | `bge-m3:latest` ID **790764642607** (ID เดียวกับ production) |
| `vector_dims(embedding)` ของทุก chunk | **1024** (แถวที่ไม่ใช่ 1024 = 0) |
| คอลัมน์ในฐานทดสอบ | `VECTOR(1024) NOT NULL` |
| `check_embedding_contract` | ผ่านทั้งสามชั้น (env → `atttypmod` → probe จริง) |

---

## 17. ผลการค้นด้วย pgvector

```
query  = "E2E-MARKER-TEST101-PIPELINE-VERIFICATION"  (embed ด้วย bge-m3 ของ test ollama)
มิติ    = 1024
SQL    = ORDER BY embedding <=> :query   (cosine · ตัวดำเนินการเดียวกับ vector_search.py)
probes = SET LOCAL ivfflat.probes = 100
```

| assertion | คาด | จริง |
|---|---|---|
| มิติของ query embedding | 1024 | **1024** |
| การค้นคืนผลลัพธ์ | > 0 | **2 แถว** |
| อันดับ 1 มาจากเอกสารทดสอบ | ใช่ | **ใช่** (`document_id=18b9a50f-…`) |
| ระยะห่างของอันดับ 1 | — | **0.296686** |
| เนื้อหาของอันดับ 1 มี `TEST101` | ใช่ | **ใช่** |
| ผลลัพธ์รวมมี marker | ใช่ | **ใช่** |

**สิ่งที่การทดสอบนี้พิสูจน์**: vector ถูกสร้าง · มิติถูกต้อง · ถูกเก็บลง pgvector ·
และค้นคืนกลับมาได้ถูกเอกสาร

**สิ่งที่ไม่ได้พิสูจน์**: คุณภาพของ ANN ที่ scale ของ production
เพราะตั้ง `ivfflat.probes = 100` เพื่อชดเชยข้อมูลที่มีน้อย (`lists = 100` กับ 2 แถว
ทำให้ list ส่วนใหญ่ว่าง และค่าเริ่มต้น `probes = 1` อาจคืน 0 แถว)
**ไม่ได้แก้ `db/schema.sql` หรือ index ใด** — เป็นการตั้งค่าเฉพาะคำค้นของ harness

---

## 18. ผลการทดสอบการกันซ้ำ

รัน worker ซ้ำหลังงานเสร็จ

| assertion | คาด | จริง |
|---|---|---|
| exit code | 0 | **0** |
| `ingest_finished_at` ไม่ถูกเขียนทับ | เท่าเดิม | **เท่าเดิม** (`2026-09-29 22:37:34.083487+00`) |
| `course_documents` | ไม่เพิ่ม (1) | **1** |
| `course_chunks` | ไม่เพิ่ม (2) | **2** |
| `crawl_decisions` | ไม่เพิ่ม (1) | **1** |
| ไฟล์ใน `DOCUMENTS_DIR` | ไม่เพิ่ม (1) | **1** |

กลไกที่กัน: `CLAIM_SQL` มีเงื่อนไข `ingest_finished_at IS NULL` · `already_ingested()`
เช็ค `extraction_status='done'` · `ON CONFLICT (course_id, file_sha256)` ·
`uq_crawl_decisions_active` · `insert_chunks` DELETE ก่อน INSERT

---

## 19. ผลการทดสอบเส้นทางความล้มเหลว

| # | สถานการณ์ | คาด | จริง |
|---|---|---:|---:|
| 1 | ไฟล์ staged หาย → `GET /{id}/pdf` | 404 | **404** |
| 2 | เนื้อไฟล์เปลี่ยน (sha ไม่ตรง) → `GET /{id}/pdf` | 404 | **404** |
| 3 | ไฟล์ไม่ใช่ PDF แต่ sha ตรง → `GET /{id}/pdf` | 404 | **404** |
| 4 | `resolve_staged()` กับ path นอก root (`/etc/passwd`) | `JobError` | **`path_outside_staging_root`** |
| 5 | คืนสภาพแล้วเปิด PDF ได้เหมือนเดิม | 200 | **200** |
| 6 | approve ด้วย sha ผิด | 409 | **409** |
| 7 | approve ด้วยรหัสหลักสูตรที่ไม่มี | 422 | **422** |
| 8 | approve ซ้ำ | 409 | **409** |
| 9 | `EMBED_MODEL` ผิด | worker ล้ม | **ล้ม · `embed_model_mismatch`** |
| 10 | `EMBED_DIM = 768` | worker ล้ม | **ล้ม · `embed_dim_mismatch`** |
| 11 | หลัง worker ล้มจากสัญญา งานยังยึดใหม่ได้ | `ingest_finished_at` ยังว่าง | **ว่าง · และรันครั้งถัดไปสำเร็จ** |

> ข้อ 1–3 มีค่าในฐานะหลักฐาน **เพราะข้อ 5 พิสูจน์ว่า 200 เป็นไปได้จริง** —
> ถ้าไม่มีข้อ 5 การได้ 404 ทั้งสามกรณีจะแยกไม่ออกจาก "endpoint พังเฉย ๆ"
> ประเด็นนี้สำคัญและเป็นเหตุให้พบข้อบกพร่อง F1

### ที่ยังไม่ได้ทดสอบ

| รายการ | เหตุผล |
|---|---|
| `lock_existing_course` ล้มเมื่อ course หายระหว่างงาน | ต้องมี candidate ที่สองเพื่อไม่ให้ทำลายสถานะของการทดสอบหลัก |
| `publish_name_collision` | ต้องประดิษฐ์ไฟล์ชื่อซ้ำเนื้อต่างเพิ่ม |
| ollama ล่มกลางการ embed | ต้องจังหวะที่ควบคุมยาก · ไม่ deterministic |
| worker ถูกฆ่ากลางคัน | ต้องจังหวะที่ควบคุมยาก · ไม่ deterministic |
| `SKIP LOCKED` กับ worker สองตัวพร้อมกัน | ต้องรันขนานและจับจังหวะ · ไม่ deterministic ในชุดนี้ |

---

## 20. Production baseline **หลัง** E2E (READ-ONLY)

วัดเมื่อ **2026-09-29T22:38:17Z**

| รายการ | ค่า |
|---|---|
| users / active / admins | 198 / 198 / 1 |
| courses | 24 |
| course_documents | 31 |
| course_chunks | 9039 |
| crawl_sources | 12 · unchanged 12 · needs_review 6 · staging_path ไม่ null 0 |
| crawl_decisions | 0 |
| v_crawl_queue | 6 |
| chat_messages / chat_answer_cache | 6640 / 160 |
| embedding dimension | 1024 |
| courses code LIKE `TEST%` | **0** |
| migrations | 001, 002, 003, 004_crawl_decisions |
| staging files | 0 |
| documents PDF | 30 |

---

## 21. Production before / after diff

| รายการ | ก่อน | หลัง | ต่าง |
|---|---|---|---|
| users / active / admins | 198/198/1 | 198/198/1 | **ไม่มี** |
| courses | 24 | 24 | **ไม่มี** |
| course_documents | 31 | 31 | **ไม่มี** |
| course_chunks | 9039 | 9039 | **ไม่มี** |
| crawl_sources (+ สถานะย่อย) | 12/12/6/0 | 12/12/6/0 | **ไม่มี** |
| crawl_decisions | 0 | 0 | **ไม่มี** |
| v_crawl_queue | 6 | 6 | **ไม่มี** |
| chat_messages | 6640 | 6640 | **ไม่มี** |
| chat_answer_cache | 160 | 160 | **ไม่มี** |
| embedding dimension | 1024 | 1024 | **ไม่มี** |
| **courses code `TEST%`** | **0** | **0** | **ไม่มี** ← ข้อพิสูจน์ว่าไม่มี test data รั่ว |
| migrations | 001–004 | 001–004 | **ไม่มี** |
| staging files | 0 | 0 | **ไม่มี** |
| documents PDF | 30 | 30 | **ไม่มี** |

**ต่างกัน 0 รายการจาก 14 รายการที่ตรวจ**

---

## 22. Production container before / after

| service | container | image | restarts | StartedAt | เปลี่ยน |
|---|---|---|---:|---|---|
| backend | `fda31caa20c4` | `4a45677ec010` | 0 → 0 | 2026-09-29T01:06:17.872Z | **ไม่** |
| frontend | `2886c1bf9183` | `591ab6d935bb` | 0 → 0 | 2026-09-29T01:07:21.190Z | **ไม่** |
| caddy | `a2957d7b8fc3` | `5f5c8640aae0` | 0 → 0 | 2026-09-22T21:23:48.949Z | **ไม่** |
| postgres | `e8c091a4fc60` | `ccc6e83d6e35` | 0 → 0 | 2026-08-18T14:17:25.705Z | **ไม่** |
| ollama | `e6ac0350c722` | `9d30908e4114` | 0 → 0 | 2026-08-18T14:17:25.705Z | **ไม่** |
| webapi | `6a73308d4f39` | `1163e36361d9` | 0 → 0 | 2026-09-22T21:21:35.624Z | **ไม่** |

**ไม่มีบริการใดถูก recreate หรือ restart เพราะการทดสอบ** — เทียบทั้ง container ID
และ StartedAt ไม่ใช่ดู RestartCount อย่างเดียว

บนเซิร์ฟเวอร์ production: คอนเทนเนอร์ชื่อ `sci-advisor-e2e` = **0** · volume = **0**
→ สภาพแวดล้อมทดสอบไม่เคยไปปรากฏบนเซิร์ฟเวอร์เลย

---

## 23. Cleanup proof

```
docker compose -p sci-advisor-e2e -f eval/e2e/docker-compose.e2e.yml down -v --remove-orphans
```

ลบแล้ว: คอนเทนเนอร์ 5 ตัว · volume 6 ตัว (`e2e_pgdata`, `e2e_ollama`, `e2e_site`,
`e2e_staging`, `e2e_documents`, `e2e_out`) · network 1 วง
และลบอิมเมจที่ build เพื่อการทดสอบอีกสองตัว
(`sci-advisor-e2e-e2e-backend:latest` `sha256:bc5a5ffa09fb…` ·
`sci-advisor-e2e-e2e-runner:latest` `sha256:539e7b0f6769…`)

| ตรวจหลัง cleanup | ผล |
|---|---:|
| images ชื่อ `sci-advisor-e2e*` | **0** |
| containers ชื่อ `sci-advisor-e2e` | **0** |
| volumes ชื่อ `sci-advisor-e2e` | **0** |
| networks ชื่อ `sci-advisor-e2e` | **0** |

**ไม่ได้ลบอิมเมจของ production** — `course-advisor-system-backend:2fdc6f2`,
`course-advisor-system-frontend:2fdc6f2`, `course-advisor-system-ingest-worker:617110e`,
อิมเมจ `rollback-*` และไฟล์ backup ทั้งหมดอยู่บน **เซิร์ฟเวอร์** ไม่ใช่เครื่องนี้ จึงไม่ถูกแตะเลย

compose project `course-advisor-system` ที่เห็นบนเครื่องผู้พัฒนามีคอนเทนเนอร์สองตัว
(`ollama` สร้าง 2026-08-18 · `postgres` สร้าง 2026-08-14) เป็น stack พัฒนาเดิมของเจ้าของเครื่อง
**มีอยู่ก่อนเริ่มงานรอบนี้และไม่ถูกแตะ**

---

## 24. Git diff / status

```
branch            mko-phase2
HEAD              2fdc6f241fc1742047b572ee2ef354cd811f9401   (ไม่เปลี่ยน)
origin/mko-phase2 2fdc6f241fc1742047b572ee2ef354cd811f9401   (ไม่เปลี่ยน)
origin/main       b78b3f8bf895685874d9a52c66b45569072f0514   (ไม่แตะ)

staged                0 ไฟล์
tracked modified      0 ไฟล์     <-- ไม่มี source ของ production ถูกแก้
untracked นอก docs/   eval/e2e/   (6 ไฟล์ · 84 KB)
```

**ไม่ commit · ไม่ push · ไม่ merge main** ตามข้อกำหนด
ไฟล์ทดสอบทั้ง 6 ไฟล์ค้างไว้ใน working tree เพื่อให้เจ้าของโปรเจกต์ตรวจก่อน

---

## 25. สิ่งที่เบี่ยงจาก Design และข้อค้นพบ

### 25.1 ข้อบกพร่องที่พบ

#### **F1 — ไฟล์ที่ crawler เก็บไว้ที่ staging เป็นโหมด 0600 จึงถูก backend อ่านไม่ได้** · **blocker ของขั้นตรวจสอบโดยคน**

```
ที่มา     pipeline/crawl/http.py:330  tempfile.mkstemp(prefix=".part_", suffix=".pdf", dir=dest_dir)
          mkstemp สร้างไฟล์ด้วยโหมด 0600 เสมอ · sync.py ใช้ os.replace() ซึ่งรักษาโหมดเดิมไว้
ผลที่วัดได้  ไฟล์ staged = -rw------- 1001:1001
          backend รันเป็น uid 1000 (appuser) จึงอ่านไม่ได้
          staging_store จับ OSError แล้วคืน None -> GET /crawl-review/{id}/pdf ตอบ 404 เสมอ
พิสูจน์สาเหตุ chmod 644 ไฟล์เดิม -> endpoint ตอบ 200 · content-type application/pdf · sha ตรง
worker ไม่กระทบ worker รันเป็น uid 1001 ซึ่งเป็นเจ้าของไฟล์ จึงอ่านได้ปกติ (ยืนยันจากการ ingest สำเร็จ)
```

**ผลกระทบต่อ production**: ฟีเจอร์ "เปิด PDF ดูก่อนอนุมัติ" จะใช้ไม่ได้เลย
ผู้ตรวจจะได้ 404 ทุกครั้งแม้ไฟล์จะมีอยู่และ sha ถูกต้อง — ซึ่งขัดกับขั้นตอนที่ Phase 3
ออกแบบไว้ว่าคนต้องเปิดดูไฟล์ก่อนกดอนุมัติ

**ทำไมถึงไม่เคยถูกพบ**: `staging/crawl` ของ production ว่างมาตลอด
(`staging_path` ไม่ null = 0 แถว) ข้อบกพร่องนี้จึงไม่เคยถูกกระตุ้น

**ต้องแก้ที่รายงานเดิม**: รายงาน Step 3 และ Step 3.5 ระบุว่า `/pdf` ตอบ 404
"เพราะ staging ว่าง" — ข้อสรุปนั้นถูกสำหรับกรณีที่ไม่มีไฟล์ แต่ **ไม่ครบ**
เพราะแม้มีไฟล์อยู่จริงก็ยังจะได้ 404 อยู่ดี

**ไม่ได้แก้ source ในรอบนี้ตามข้อห้าม** — เสนอให้เจ้าของพิจารณาเป็นงานแยก

#### **F2 — `check_embedding_contract()` ทำงานหลัง `claim()` ไม่ใช่ก่อน** · ข้อสังเกตเชิงพฤติกรรม ไม่ใช่ข้อบกพร่อง

```
ที่มา   pipeline/crawl/approve.py:448  check_embedding_contract() อยู่ใน process()
        ซึ่งถูกเรียกที่บรรทัด 492 หลัง claim() ที่บรรทัด 485
ผล     worker ที่ตั้งค่า embedding ผิดจะยึดงานก่อนแล้วจึงล้ม
       ingest_started_at และ ingest_error ถูกเขียน · ingest_finished_at ยังว่าง
       งานจึงยังถูกยึดใหม่ได้ และการรันครั้งถัดไปที่ตั้งค่าถูกก็สำเร็จ (พิสูจน์แล้วในรอบนี้)
```

**ต้องแก้ที่เอกสารเดิม**: Design และรายงาน Step 2 ระบุว่า "ล้มด้วย `embed_model_mismatch`
**ก่อน**แตะงานใด" ซึ่งไม่ตรงกับโค้ดจริง

### 25.2 สิ่งที่เบี่ยงจาก Design

| # | เรื่อง | รายละเอียด |
|---|---|---|
| D1 | **Docker Desktop ไม่ได้ทำงาน** | ตอนเริ่ม preflight ต่อ engine ไม่ได้ · เปิดโปรแกรมให้ (เครื่องของผู้พัฒนา ไม่กระทบใคร) engine พร้อมใน 5 วินาที · **ไม่ได้ย้ายไปรันบนเซิร์ฟเวอร์** |
| D2 | **ต้อง chown volume เป็น 1001** | Docker สร้าง volume ใหม่เป็นของ root แต่อิมเมจ worker ตั้ง `USER worker` (1001) · เพิ่มขั้นตอนนี้ลง README แล้ว · การตั้งเป็น 1001 ยังตรงกับ production ที่ `documents/` เป็นของ uid 1001 |
| D3 | **สร้างผู้ใช้ทดสอบผ่าน `/auth/register` แทนการ INSERT** | อิมเมจ worker ไม่มี `bcrypt` (เป็น dependency ของ backend) จะ import `hash_password()` มาใช้ตรง ๆ ไม่ได้ · **การเรียก API แทนให้ผลที่ดีกว่า** เพราะใช้เส้นทางสมัครของ production จริงทั้งเส้น ไม่ได้ปลอม hash |
| D4 | **อีเมลทดสอบใช้ `example.com`** | `EmailStr` ปฏิเสธ `.invalid` และ `.local` เพราะเป็น special-use domain (`The part after the @-sign is a special-use or reserved name`) · ทดสอบแล้ว `example.com` และ `.dev` ผ่าน · เป็นเหตุผลว่าทำไมบัญชีกลาง `public-web@stpnru.local` ของ production ต้อง INSERT ด้วย SQL ไม่ผ่าน API |
| D5 | **harness ต้อง `commit()` หลัง `process_link()`** | `CrawlStore.__exit__` เรียกแค่ `close()` · `sync.py::main()` จึง `store.conn.commit()` หลังทุกลิงก์ · harness ต้องทำเหมือนกัน (บั๊กของ harness ผมเองในรอบแรก ไม่ใช่ของ production) |
| D6 | `e2e-runner` mount repo `:ro` | ตาม Design คาดไว้แล้ว — อิมเมจ worker มีแต่ `pipeline/` และ `llm/` จึงต้อง mount เพื่อเข้าถึง `backend/`, `db/`, `eval/` |
| D7 | `e2e-runner` mount staging `:rw` | ตาม Design คาดไว้แล้ว — production แยก crawler (rw) กับ worker (ro) เป็นคนละคอนเทนเนอร์ · ที่นี่รวมเป็นตัวเดียว · **`e2e-backend` ยังเป็น `:ro` เหมือน production** |
| D8 | ลบข้อตรวจที่เป็นจริงเสมอออก 2 ข้อ | ข้อตรวจ `len(MARKER) > 0` และข้อตรวจที่มี `or rc == 0` ผ่านโดยไม่พิสูจน์อะไร · ลบทิ้งเพื่อไม่ให้จำนวน PASS ดูดีเกินจริง |

---

## 26. ข้อจำกัดที่ทราบ

| # | เรื่อง |
|---|---|
| 1 | **ไม่ได้พิสูจน์คุณภาพ ANN ที่ scale จริง** — ตั้ง `ivfflat.probes = 100` เพื่อชดเชยข้อมูล 2 แถวกับ `lists = 100` |
| 2 | **Test PDF ไม่เหมือน มคอ.2 จริง** — พิสูจน์กลไกของ pipeline ไม่ใช่คุณภาพการสกัดข้อมูลจากเอกสารจริงที่ซับซ้อน (ได้ 2 chunks จาก 1 หน้า) |
| 3 | **เว็บจำลองไม่เหมือนเว็บคณะจริง** — การทดสอบกับเว็บจริงอยู่ใน `CRAWLER_PRODUCTION_VERIFY_REPORT.md` |
| 4 | **ไม่ได้ทดสอบ `SKIP LOCKED` แบบขนาน** และเส้นทางล้มเหลวที่ต้องจับจังหวะ (ollama ล่มกลางคัน · worker ถูกฆ่า) — ดูข้อ 19 |
| 5 | **bge-m3 คนละ instance กับ production** — ID ของโมเดลตรงกัน (`790764642607`) แต่ไม่ได้พิสูจน์ว่าค่า vector เท่ากัน bit-for-bit · assertion ที่ใช้คือมิติและการค้นเจอ |
| 6 | **ไม่ได้ทดสอบ `document_store` ของ backend เห็นไฟล์ที่เพิ่ง ingest** — ต้อง restart backend ตามข้อจำกัดที่ทราบอยู่แล้ว |
| 7 | **รันทั้งหมด 5 รอบ** — 3 รอบแรกล้มจากบั๊กของ harness (D3/D4/D5) 1 รอบได้ 91/97 (ก่อนแก้การบันทึก F1/F2) และ **รอบสุดท้าย 102/102 บนฐานข้อมูลที่รีเซ็ตใหม่** ซึ่งเป็นรอบที่ใช้เป็นผลทางการ |

---

## 27. คำตัดสิน

### **ISOLATED E2E PIPELINE: PASS**

102 / 102 assertion ผ่าน · exit 0 · เส้นทางครบวงจรทำงานได้จริง

```
Test PDF -> crawler ตัวจริง -> TEST CANDIDATE (downloaded) -> staged file + sha256
        -> Admin Review (401 / 403 / 200) -> approve (201) -> worker claim
        -> validate -> publish -> extract -> 2 chunks -> bge-m3 -> vector 1024 มิติ
        -> pgvector -> ค้นด้วย marker เจอเอกสารที่ถูกต้องเป็นอันดับ 1
        -> รันซ้ำไม่เกิดของซ้ำ -> crawl_sources.status = ingested
```

พร้อมกันนั้นพบ **ข้อบกพร่องจริงหนึ่งข้อ (F1)** ที่จะทำให้ขั้นตรวจสอบโดยคนใช้งานไม่ได้บน production
ซึ่งเป็นสิ่งที่มีแต่การทดสอบแบบ E2E เท่านั้นที่จะพบได้

### **PRODUCTION SAFETY: PASS**

14 / 14 ค่าของ production ตรง baseline เป๊ะ · `courses code TEST%` = 0 ·
คอนเทนเนอร์ทั้งหก container ID และ StartedAt ไม่เปลี่ยน · ไม่มี resource ของ e2e
บนเซิร์ฟเวอร์เลย · Production access ในรอบนี้เป็น **READ-ONLY ล้วน**

### **PRODUCTION ONE-JOB INGESTION: ยัง NO-GO**

เหตุผลที่ปิดกั้น

1. **ไม่มี PRODUCTION CANDIDATE** — `crawl_sources` ทั้ง 12 แถวยังเป็น `unchanged` ·
   `staging_path` null ทั้งหมด · staging ว่าง · **6 แถวในคิวไม่ใช่ candidate**
   (ถูกตั้งธงเพราะจับคู่หลักสูตรไม่ชัด ไม่ใช่เพราะมีไฟล์ใหม่)
2. **ข้อบกพร่อง F1 ยังไม่ถูกแก้** — ถ้ามี candidate จริงขึ้นมาวันนี้ ผู้ตรวจจะเปิด PDF
   ดูก่อนอนุมัติไม่ได้ ซึ่งเป็นขั้นตอนบังคับของกระบวนการ

**E2E PASS ไม่ใช่การอนุญาตให้รัน ingestion บน production**

---

## สิ่งที่ไม่ได้ทำ

ไม่ได้รัน crawler/worker/ingestion บน production · ไม่ได้สร้าง PRODUCTION CANDIDATE ·
ไม่ได้ POST approve/ignore/undo บน production · ไม่ได้สร้าง embedding บน production ·
ไม่ได้ INSERT/UPDATE/DELETE ข้อมูลใดบน production · ไม่ได้แตะ `crawl_sources`,
`courses`, `course_documents`, `course_chunks` ของ production · ไม่ได้อัปโหลดไฟล์ใด
เข้า staging ของ production · ไม่ได้แก้ Supabase · ไม่ได้แก้ auth · ไม่ได้แก้ Caddy ·
ไม่ได้ deploy · ไม่ได้ restart บริการใด · ไม่ได้ทำ migration บน production ·
ไม่ได้ commit/push/merge · ไม่ได้แก้ source ของ production แม้ไบต์เดียว ·
ไม่ได้ลบอิมเมจหรือ backup ของ production

---

## STOP

รอ **owner review** ก่อนดำเนินการต่อ

สองเรื่องที่ต้องให้เจ้าของโปรเจกต์ตัดสิน

1. **ข้อบกพร่อง F1** — จะแก้อย่างไรและเมื่อไหร่ (เป็นงานแยกที่ต้องได้รับอนุมัติ)
2. **ไฟล์ทดสอบ 6 ไฟล์ใน `eval/e2e/`** — จะ commit เก็บไว้หรือไม่

STOP
