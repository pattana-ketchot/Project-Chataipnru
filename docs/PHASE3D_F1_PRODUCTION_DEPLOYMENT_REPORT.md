# Phase 3D — F1 Safe Production Deployment

| | |
|---|---|
| วันที่ | 2026-09-29 → 30 · ช่วงทำงาน **23:50–00:04 UTC** (ไทย 2026-09-30 ราว 06:50–07:04) |
| ขอบเขต | commit + push + build worker image + เตรียม deployment reference + ตรวจ invariants |
| **DEPLOY_REV** | **`7af085b2e8138c5f7d10229af4a68b8e435c0a63`** |
| **F1 COMMIT** | **PASS** |
| **PUSH mko-phase2** | **PASS** |
| **F1 WORKER IMAGE BUILD** | **PASS** |
| **F1 SAFE PRODUCTION DEPLOYMENT** | **PARTIAL — หยุดตามคำสั่งที่ Phase 8** (ดูข้อ 20 และ 31) |
| **PRODUCTION DATA SAFETY** | **PASS** — 15/15 ค่าตรง baseline |
| **PRODUCTION SERVICE SAFETY** | **PASS** — ไม่มีบริการใดถูก restart |
| **PRODUCTION CRAWLER EXECUTED** | **NO** |
| **PRODUCTION WORKER EXECUTED** | **NO** |
| **PRODUCTION INGESTION EXECUTED** | **NO** |
| **PRODUCTION ONE-JOB INGESTION** | **ยัง NO-GO** |

> **อ่านข้อ 20 และ 31 ก่อนสรุป** — ขั้นตอน "เปลี่ยน deployment reference" หยุดไว้โดยเจตนา
> เพราะ `docker-compose.worker.yml` **ไม่มีอยู่บน production** ตามที่ Step 3 ออกแบบไว้
> การเปลี่ยนจึงต้องเลือกทางใดทางหนึ่งที่เกินกว่าที่อนุมัติไว้ ต้องให้เจ้าของตัดสิน

---

## 1. Owner authorization scope

| # | สิ่งที่อนุมัติ | สถานะ |
|---|---|---|
| 1 | ตรวจ final diff ของ F1 | **ทำแล้ว** (ข้อ 3) |
| 2 | commit F1 fix | **ทำแล้ว** `5d8f82b` |
| 3 | commit regression tests | **ทำแล้ว** (อยู่ใน `5d8f82b` เดียวกันตามที่กำหนด) |
| 4 | commit isolated E2E harness 6 ไฟล์ | **ทำแล้ว** `7af085b` |
| 5 | push เฉพาะ `origin/mko-phase2` | **ทำแล้ว** (ข้อ 8) |
| 6 | build worker image revision ใหม่จาก commit ที่ push แล้ว | **ทำแล้ว** (ข้อ 14–16) |
| 7 | deploy เฉพาะสิ่งที่จำเป็นเพื่อให้ production มี F1 fix | **ทำบางส่วน** — อิมเมจอยู่บน production แล้ว · deployment reference **หยุดไว้** (ข้อ 20) |
| 8 | verify ว่า image มี `STAGED_FILE_MODE = 0o644` | **ทำแล้ว** (ข้อ 18) |
| 9 | ตรวจ production invariants หลัง deploy | **ทำแล้ว** (ข้อ 24–26) |

**ที่ยังไม่ได้อนุมัติและไม่ได้ทำ**: production crawler · production worker execution ·
production ingestion · production approve/ignore/undo · production embedding ·
การสร้าง production candidate

**DEPLOY F1 ≠ RUN PIPELINE** — ยึดหลักนี้ทุกขั้น

---

## 2. Pre-commit HEAD / branch

| รายการ | ค่า |
|---|---|
| repo | `D:\workspace\course-advisor-system-mko2` |
| branch | `mko-phase2` |
| HEAD ก่อน commit | `2fdc6f241fc1742047b572ee2ef354cd811f9401` — **ตรงกับที่คาดไว้** |
| `origin/mko-phase2` ก่อน push | `2fdc6f241fc1742047b572ee2ef354cd811f9401` |
| `origin/main` ก่อน push | `b78b3f8bf895685874d9a52c66b45569072f0514` |
| remote | `https://github.com/pattana-ketchot/Project-Chataipnru.git` |

เอกสารหลักทั้งสี่ฉบับอ่านแล้วและมีอยู่จริง: `PHASE3D_F1_STAGING_PERMISSION_FIX_REPORT.md`
(840 บรรทัด) · `PHASE3D_ISOLATED_E2E_TEST_EXECUTION_REPORT.md` (682) ·
`PHASE3D_ISOLATED_E2E_TEST_HARNESS_DESIGN.md` (691) ·
`AUTOMATED_INGESTION_PHASE3D_STEP3_RESUME_REPORT.md` (950)

ไม่พบความต่างอย่างมีนัยสำคัญระหว่าง branch/history/สถาปัตยกรรม กับที่เอกสารหลักบันทึกไว้

---

## 3. Final diff audit

### 3.1 tracked modification — ตรวจจริง ไม่ได้สมมติ

```
git status --porcelain   (ส่วนที่ไม่ใช่ ?? docs/)
   M eval/crawl_download_check.py
   M pipeline/crawl/http.py
  ?? eval/e2e/

git diff --check          ว่าง
git diff --stat           2 files changed, 222 insertions(+), 3 deletions(-)
```

**tracked modification มีเพียงสองไฟล์ที่คาดไว้ ไม่มี unrelated modification**

### 3.2 ยืนยันว่าไม่ได้แก้สิ่งที่ห้ามแตะ

ตรวจด้วย `git diff --name-only HEAD -- <path>` ทีละรายการ ได้ **0 ไฟล์ทุกรายการ**

```
db  backend  frontend  llm  webapi  Caddyfile
docker-compose.prod.yml  docker-compose.staging.yml  docker-compose.worker.yml  docker-compose.yml
pipeline/Dockerfile  backend/Dockerfile
pipeline/crawl/sync.py  pipeline/crawl/approve.py  pipeline/ingest.py
```

ไม่มีการแก้ DB schema · migrations · auth · Caddy · backend · scoring · RAG · Supabase ·
production compose

### 3.3 ตำแหน่งของตัวแก้ใน `pipeline/crawl/http.py` — ตรวจตามลำดับบรรทัดจริง

```
บรรทัด  334   ตรวจ content-length ที่ประกาศมา เทียบเพดาน
บรรทัด  351   ตรวจลายเซ็น %PDF-
บรรทัด  356   tempfile.mkstemp()            <- สร้างไฟล์หลังผ่านลายเซ็นแล้วเท่านั้น
บรรทัด  361   ตรวจขนาดจริงระหว่างอ่าน เทียบเพดาน
บรรทัด  374   ตรวจว่าอ่านครบตามที่ประกาศ
บรรทัด  387   os.chmod(tmp, STAGED_FILE_MODE)   <-- ตัวแก้
บรรทัด  392   Download(ok=True, ...)            <-- คืนให้ผู้เรียก
บรรทัด   94   STAGED_FILE_MODE = 0o644
```

ตรงตามข้อกำหนด: `os.chmod` อยู่ **หลัง** download complete · PDF validation ·
size/read validation และอยู่ **ก่อน** `Download(ok=True)` ถูกส่งกลับ

### 3.4 ไฟล์ทดสอบ 6 ไฟล์ — ตรวจจริงว่ามีเท่านี้

```
eval/e2e/README.md
eval/e2e/docker-compose.e2e.yml
eval/e2e/fakesite/server.py
eval/e2e/make_test_pdf.py
eval/e2e/run_e2e.py
eval/e2e/seed.py
รวม 6 ไฟล์ — ไม่มี .pdf / .json / .log / .env / .pyc ปน
```

**ค่าที่ดูเหมือน secret ในไฟล์ที่ commit — เปิดเผยให้ตรวจ**

| ที่ | ค่า | ลักษณะ |
|---|---|---|
| `docker-compose.e2e.yml:27` | `POSTGRES_PASSWORD: e2e-throwaway-postgres` | ค่าทดสอบ ใช้เฉพาะในสภาพแวดล้อมแยก ตายไปพร้อม volume |
| `:28` | `ADVISOR_API_PASSWORD: e2e-throwaway-api` | เช่นเดียวกัน |
| `:29` | `ADVISOR_INGEST_PASSWORD: e2e-throwaway-ingest` | เช่นเดียวกัน |
| `:82` | `JWT_SECRET: e2e-isolated-test-only-jwt-secret-not-used-anywhere-else` | เช่นเดียวกัน |

ค้นหาค่าของ production ในไฟล์ทดสอบทั้งหก (`stpnru`, `duckdns`, `161.118`,
DSN ของ production, `ubuntu@`): **ไม่พบเลย** · รหัสผ่านของบัญชีทดสอบสองบัญชีสุ่มด้วย
`secrets.token_urlsafe(18)` ในหน่วยความจำ ไม่เขียนลงไฟล์ ไม่พิมพ์ ไม่ commit

---

## 4. Final local regression

รันกับ working tree ที่กำลังจะ commit · ฐานข้อมูล `crawl_test` ในคอนเทนเนอร์แยก
(PostgreSQL 16.15 — รุ่นเดียวกับ production) · **ไม่แตะฐานข้อมูล production**

| ชุด | ที่รัน | ผ่าน | ไม่ผ่าน | ข้าม |
|---|---|---:|---:|---:|
| `eval/crawl_download_check.py` | Linux (root) | **165** | **0** | **0** |
| `eval/crawl_state_check.py` | Linux + `crawl_test` | **32** | **0** | 0 |
| `eval/crawl_ingest_worker_check.py` | Linux + `crawl_test` | **187** | **0** | **0** |
| `eval/crawl_approval_check.py` | Linux + `crawl_test` | **84** | **0** | **0** |
| `eval/document_endpoint_check.py` | Linux (unittest) | **16** | **0** | 0 |
| **รวม** | | **484** | **0** | **0** |

จำนวนรวมเท่ากับรอบก่อน (484) และ `84`/`187` ยังตรงกับที่บันทึกใน
`AUTOMATED_INGESTION_PHASE3A_REPORT.md` และ `AUTOMATED_INGESTION_PHASE3C_REPORT.md`
ไม่มี FAIL — gate ผ่าน จึง commit ได้

สภาพแวดล้อมทดสอบถูกลบหมดหลังรัน (containers 0 · volumes 0 · images 0)

---

## 5. F1 commit hash

```
F1_FIX_COMMIT = 5d8f82b0894536fdd5ff03d65aa0dc92c5592328
```

```
fix: make staged crawler PDFs readable by the review backend

  pipeline/crawl/http.py        +40  −0
  eval/crawl_download_check.py +182  −3
  2 files changed, 222 insertions(+), 3 deletions(-)
```

`git diff --cached --check` ก่อน commit: ว่าง ·
blob ที่เก็บลง git มี CRLF = **0** ทั้งสองไฟล์ (ตรวจจาก `git cat-file -p :<path>`)

staged แบบระบุ path: `git add -- pipeline/crawl/http.py eval/crawl_download_check.py`
**ไม่ใช้ `git add .`**

---

## 6. E2E harness commit hash

```
E2E_TEST_COMMIT = 7af085b2e8138c5f7d10229af4a68b8e435c0a63
```

```
test: add isolated crawler ingestion e2e harness

  eval/e2e/README.md              117 +
  eval/e2e/docker-compose.e2e.yml 139 +
  eval/e2e/fakesite/server.py     124 +
  eval/e2e/make_test_pdf.py       111 +
  eval/e2e/run_e2e.py             565 +
  eval/e2e/seed.py                170 +
  6 files changed, 1226 insertions(+)
```

staged แบบระบุ path ทั้งหกไฟล์ · `git diff --cached --check`: ว่าง

---

## 7. DEPLOY_REV

```
DEPLOY_REV        = 7af085b2e8138c5f7d10229af4a68b8e435c0a63
DEPLOY_REV (short) = 7af085b
```

= `HEAD` ของ `mko-phase2` หลัง commit ทั้งสอง · working tree **สะอาด** (ไม่มีไฟล์ค้าง
นอกจาก `docs/` ที่ไม่ commit) จึง build จาก revision ที่ตรวจย้อนกลับได้จริง ไม่ใช่จาก dirty tree

ไฟล์ที่ต่างจาก HEAD เดิมทั้งหมด 8 ไฟล์ · 1,448 insertions · 3 deletions

---

## 8. Push result

```
git push origin mko-phase2
  To https://github.com/pattana-ketchot/Project-Chataipnru.git
     2fdc6f2..7af085b  mko-phase2 -> mko-phase2
```

ก่อน push ตรวจแล้วว่า `origin/mko-phase2` เป็น ancestor ของ HEAD → **fast-forward ปกติ**
ไม่ใช้ `--force` · ไม่ใช้ `--all` · ไม่ push tag (local tags = 0) · ไม่ merge main · ไม่ push main

---

## 9. origin/mko-phase2 before / after

| | ค่า |
|---|---|
| ก่อน push | `2fdc6f241fc1742047b572ee2ef354cd811f9401` |
| หลัง push | `7af085b2e8138c5f7d10229af4a68b8e435c0a63` |
| เทียบกับ DEPLOY_REV | **เท่ากัน** |

---

## 10. origin/main before / after

| | ค่า |
|---|---|
| ก่อน push | `b78b3f8bf895685874d9a52c66b45569072f0514` |
| หลัง push | `b78b3f8bf895685874d9a52c66b45569072f0514` |
| เปลี่ยนหรือไม่ | **ไม่เปลี่ยน** |

branch บน remote ทั้งหมดหลัง push มีสองอันตามเดิม

```
b78b3f8bf895  refs/heads/main
7af085b2e813  refs/heads/mko-phase2
```

---

## 11. Production pre-deploy baseline

วัดเมื่อ **2026-09-29T23:56:54Z** (READ-ONLY)

| รายการ | ค่า |
|---|---|
| users / active / admins | 198 / 198 / 1 |
| courses | 24 |
| course_documents | 31 |
| course_chunks | 9039 |
| crawl_sources | 12 · unchanged 12 · needs_review 6 · staging_path ไม่ null **0** |
| crawl_decisions | 0 |
| v_crawl_queue | 6 |
| chat_messages | 6640 |
| chat_answer_cache | 160 |
| embedding dimension | 1024 |
| courses code `TEST%` | **0** |
| staging files | **0** |
| documents PDF | 30 |

---

## 12. Production pre-deploy containers

| service | container ID | image | StartedAt | restarts | status |
|---|---|---|---|---:|---|
| backend | `fda31caa20c4` | `4a45677ec010` | 2026-09-29T01:06:17.872Z | 0 | running |
| frontend | `2886c1bf9183` | `591ab6d935bb` | 2026-09-29T01:07:21.190Z | 0 | running |
| caddy | `a2957d7b8fc3` | `5f5c8640aae0` | 2026-09-22T21:23:48.949Z | 0 | running |
| postgres | `e8c091a4fc60` | `ccc6e83d6e35` | 2026-08-18T14:17:25.705Z | 0 | running |
| ollama | `e6ac0350c722` | `9d30908e4114` | 2026-08-18T14:17:25.705Z | 0 | running |
| webapi | `6a73308d4f39` | `1163e36361d9` | 2026-09-22T21:21:35.624Z | 0 | running |

คอนเทนเนอร์ `ingest-worker`: **0** (ไม่มีอยู่)
อิมเมจ worker ที่มีก่อน deploy: `course-advisor-system-ingest-worker:617110e` · ID `c80cc9b21141`

---

## 13. Staging precondition

```
/home/ubuntu/course-advisor-system/staging/crawl
  mode=755 owner=ubuntu:ubuntu
  ไฟล์: 0                       <- ไม่มีไฟล์ pre-fix ที่ยังเป็น 0600
```

**precondition ผ่าน** — ไม่มีไฟล์ขึ้นมาใหม่หลังรายงานล่าสุด จึงไม่ต้องหยุดขอ review

### 13.1 ตรวจเพิ่ม: `pipeline/` ที่มีอยู่บน production ไม่ใช่ทางที่จะรันโค้ดเก่า

พบว่า `/home/ubuntu/course-advisor-system/pipeline/` มีอยู่จริง 17 ไฟล์ (mtime 2026-09-07)
แต่เป็นชุด ingest เดิมก่อน Phase 3 ซึ่ง **ไม่มีโฟลเดอร์ `pipeline/crawl/` เลย**

```
pipeline/__init__.py  chunker.py  clean.py  embed.py  extract_pdf.py
ingest.py  ingest_batch.py  ocr.py  requirements.txt  (+ __pycache__)
  pipeline/crawl/http.py : ไม่มีไฟล์นี้บน production
```

จึงไม่มีทางที่ใครจะรัน crawler ด้วยโค้ดเก่าที่ยังมีข้อบกพร่อง F1 จากโฟลเดอร์นี้

---

## 14. Build method

สร้าง archive แบบ deterministic จาก **commit** ไม่ใช่จาก working tree

```bash
git -c core.autocrlf=false archive --format=tar 7af085b2e8138c5f7d10229af4a68b8e435c0a63 \
    -- pipeline llm > release-7af085b-worker.tar
```

ใช้ `-c core.autocrlf=false` เพราะบน Windows ค่าเริ่มต้นจะใส่ CRLF ลง archive ·
ใช้ tar ไม่บีบอัดเพื่อเลี่ยง timestamp ของ gzip

| | |
|---|---|
| package | `release-7af085b-worker.tar` · 501,760 ไบต์ |
| sha256 | `ad3f55189a479c922bea7a09c7ba7cdb40c557a89b5a153dce3560996b6ce28a` |
| manifest | `release-7af085b-worker.manifest.tsv` · 3,499 ไบต์ · 38 รายการ |
| sha256 | `12dc74420f5641bc424046c8d66b800a85a62cd34dae3821fb0a8536972476af` |

**ไส้ archive**: top-level เป็น `pipeline` และ `llm` เท่านั้น · สมาชิก 42 (ไฟล์ 38 · โฟลเดอร์ 4) ·
symlink 0 · path ที่ขึ้นต้นด้วย `/` = 0 · path ที่มี `..` = 0 · ownership `root/root` ทั้งหมด ·
ไม่พบ `.env` / `.pem` / `.key` / `credential` / `secret` / `__pycache__` / `.pyc`

**การโอนและตรวจหลังโอน** — ปลายทางเป็น release directory แยก **ไม่ extract ทับโฟลเดอร์ production**

```
/home/ubuntu/release-7af085b-worker/        (mode 750)
  release-7af085b-worker.tar          sha256 ad3f5518… ตรงกับต้นทาง
  release-7af085b-worker.manifest.tsv sha256 12dc7442… ตรงกับต้นทาง
  src/                                แตกไฟล์ที่นี่ 38 ไฟล์ · symlink 0
  build-worker-7af085b.log
  compose.worker-candidate-7af085b.yml   (ดูข้อ 20)
```

ตรวจ per-file hash หลังแตกไฟล์เทียบ manifest: **ตรง 38 · ไม่ตรง 0**

ไฟล์สองไฟล์ที่สำคัญที่สุด — hash ตรงกับ committed blob ทุกไบต์

```
src/pipeline/Dockerfile      ca48cd2da16c7fefcd72edc42fa943b728ad67ec627d425e00db3c91848971a1
src/pipeline/crawl/http.py   d81394e45f5b043ddd3071eb2def4990f71e0cc668bf72fb93ff5d8181dc726d
                             มี STAGED_FILE_MODE = 0o644 · มี os.chmod · CRLF 0
```

`pipeline/Dockerfile` ที่ DEPLOY_REV เหมือนกับที่ `2fdc6f2` ทุกไบต์ (`ca48cd2da16c7fef…`)
ดังนั้นความต่างของอิมเมจใหม่มาจากโค้ดที่แก้ ไม่ใช่จาก Dockerfile

**คำสั่ง build**

```bash
sudo docker build -f src/pipeline/Dockerfile \
  --build-arg GIT_REVISION=7af085b2e8138c5f7d10229af4a68b8e435c0a63 \
  -t course-advisor-system-ingest-worker:7af085b \
  src
```

เริ่ม `2026-09-29T23:59:04Z` → จบ `23:59:11Z` · exit 0 · log เก็บไว้ที่
`build-worker-7af085b.log` (7,497 ไบต์) · เร็วเพราะ layer `pip install` ถูก cache
จาก build เดิม (`requirements.txt` และ Dockerfile เหมือนกันทุกไบต์)

**ไม่ได้ relabel อิมเมจเก่า** และ **ไม่ได้ tag อิมเมจเก่าเป็น revision ใหม่** — build ใหม่จริง

---

## 15. New worker image tag

```
course-advisor-system-ingest-worker:7af085b
```

---

## 16. New worker image ID

```
sha256:9d5c623b7e0a8a0f88873b170bfc697ac4edd039bdaaf6771c45322c3bbfb2a4
short: 9d5c623b7e0a   ·   330MB   ·   สร้าง 2026-09-29 23:59:08 UTC
```

อิมเมจเก่ายังอยู่ครบสำหรับ rollback

```
course-advisor-system-ingest-worker:617110e
sha256:c80cc9b2114139cc38ef91c044a8517b2cf4f30611c663d55de3b99747ae4588
short: c80cc9b21141   ·   330MB   ·   สร้าง 2026-09-28 06:15:45 UTC
```

---

## 17. OCI revision verification

| อิมเมจ | `org.opencontainers.image.revision` | ตรงกับ |
|---|---|---|
| `:7af085b` | `7af085b2e8138c5f7d10229af4a68b8e435c0a63` | **= DEPLOY_REV** |
| `:617110e` | `617110e975dccc94b5e67f77990e34a071ccf9a0` | revision เดิม ไม่ถูกแตะ |

`org.opencontainers.image.title` ของอิมเมจใหม่: `SCI Advisor approved-curriculum ingest worker`

---

## 18. STAGED_FILE_MODE runtime verification

ตรวจด้วย **entrypoint ปลอดภัย** ไม่ใช้ CMD เดิม · `--network none` · ไม่มี env ของ DB/Ollama ·
ไม่มี volume · `--rm` ยืนยันแล้วว่า `Config.Entrypoint` เป็น `null` จึง override CMD ได้แน่นอน

```bash
sudo docker run --rm --network none --entrypoint python \
  course-advisor-system-ingest-worker:7af085b -c "..."
```

```
STAGED_FILE_MODE                    = 0o644          <-- ตรงตามที่ต้องการ
os.chmod อยู่ใน download()           = True
chmod มาก่อน Download(ok=True)       = True
chmod มาหลังด่านอ่านครบ               = True
python                              = 3.11.16
umask                               = 0o22
```

### 18.1 พิสูจน์ว่าอิมเมจใหม่ต่างจากเก่าจริง ไม่ใช่การ relabel

รันคำสั่งเดียวกันกับอิมเมจเก่า

```
:7af085b  STAGED_FILE_MODE = 0o644
:617110e  ImportError — ไม่มีค่านี้ในอิมเมจเก่า (ยังเป็นโค้ดที่มีข้อบกพร่อง)
```

ค่าคงที่นี้ไม่มีอยู่เลยในอิมเมจเก่า ความต่างจึงเป็นความต่างของโค้ด ไม่ใช่ของ label

---

## 19. Worker UID/GID verification

```
uid / gid = 1001 / 1001
groups    = [1001]
User      = worker        (เหมือนอิมเมจเก่า)
WorkDir   = /app          (เหมือนอิมเมจเก่า)
Cmd       = ["python","-u","-m","pipeline.crawl.approve","--max-jobs","1"]   (เหมือนอิมเมจเก่า)
```

สถาปัตยกรรมเดิมทั้งหมด · `groups = [1001]` ยังยืนยันเหตุผลที่เลือก `0644` ไม่ใช่ `0640`
(ไม่มีกลุ่มร่วมกับ backend ที่เป็น gid 1000)

---

## 20. Deployment reference change — **หยุดไว้ตามคำสั่ง**

### 20.1 สิ่งที่พบ

`docker-compose.worker.yml` **ไม่มีอยู่บนเซิร์ฟเวอร์ production เลย**

```
/home/ubuntu/course-advisor-system/
  docker-compose.gpu.yml  docker-compose.prod.yml
  docker-compose.staging.yml  docker-compose.yml
  ไม่มี docker-compose.worker.yml

ค้นทั้ง /home/ubuntu (ลึก 3 ชั้น) หาไฟล์ *worker*.yml/*worker*.yaml : ไม่พบเลย
โฟลเดอร์ production ไม่ใช่ git repo
```

นี่ **ไม่ใช่ความผิดพลาด** — เป็นสิ่งที่ Step 3 ตั้งใจทำ รายงาน
`AUTOMATED_INGESTION_PHASE3D_STEP3_RESUME_REPORT.md` ระบุไว้ตรง ๆ ว่า
`pipeline/` และ `docker-compose.worker.yml` ถูกกันออกจาก release
"ไม่จำเป็นต่อ deploy รอบนี้ และการไม่ใส่ทำให้ไม่มีทางรัน worker จาก release directory"

deployment reference จึงมีอยู่ที่เดียวคือไฟล์ในโปรเจกต์ ซึ่งยังชี้
`course-advisor-system-ingest-worker:617110e` (บรรทัด 30)

### 20.2 ทำไมจึงหยุด

Phase 8 สั่งว่า "หากจำเป็นต้องแก้อะไรมากกว่านั้น: STOP และรายงานก่อน"
การเปลี่ยน reference ต้องเลือกทางใดทางหนึ่ง และทั้งสองทางเกินกว่าที่อนุมัติไว้

| ทาง | ผลที่ตามมา |
|---|---|
| **A — commit แก้ `docker-compose.worker.yml` ในโปรเจกต์** | จะทำให้ `HEAD ≠ DEPLOY_REV` ทันที ขัดกับ Phase 4 ที่กำหนดว่า `origin/mko-phase2 == DEPLOY_REV` และขัดกับ Phase 6 ที่กำหนดว่าอิมเมจต้อง build จาก **exact** DEPLOY_REV · และ commit ที่สามไม่อยู่ในรายการที่เจ้าของอนุมัติ (ข้อ 2–4 มีเพียงสามอย่าง) |
| **B — ติดตั้งไฟล์ลงโฟลเดอร์ production** | จะย้อนคุณสมบัติความปลอดภัยที่ Step 3 ตั้งใจสร้าง — ทำให้การ start worker เหลือเพียงคำสั่งเดียว ซึ่งขัดกับ **CRITICAL — DO NOT START WORKER** ของรอบนี้ |

### 20.3 สิ่งที่ทำแทน — เตรียมไว้ให้ตรวจ ยังไม่นำไปใช้

สร้างไฟล์ candidate จาก `docker-compose.worker.yml` ที่ DEPLOY_REV โดยเปลี่ยน
**บรรทัดเดียว** แล้ววางไว้ใน **release directory** ไม่ใช่โฟลเดอร์ production

```diff
     # build ด้วย: docker build -f pipeline/Dockerfile \
     #   --build-arg GIT_REVISION=<commit> -t course-advisor-system-ingest-worker:<tag> .
-    image: course-advisor-system-ingest-worker:617110e
+    image: course-advisor-system-ingest-worker:7af085b
     # ต้องระบุ --profile worker หรือใช้ `run` จึงจะถูกสร้าง — `up -d` เฉย ๆ จะข้ามไป
     profiles: ["worker"]
```

จำนวนบรรทัดที่ต่าง: **1** (ลบ 1 เพิ่ม 1) · ไม่แตะ `command` · `environment` · `volumes` ·
`user` · `restart` · `profiles` · DB config · Ollama config

```
/home/ubuntu/release-7af085b-worker/compose.worker-candidate-7af085b.yml
  4,932 ไบต์ · sha256 db97a3621f3fe9050b7ab6518a787ad23ae5bfa3b175bae7f213ee8ea89c873c
  image reference: course-advisor-system-ingest-worker:7af085b
```

ไฟล์นี้ **ไม่ได้ทำให้เกิด service ใด** — ยืนยันว่าคอนเทนเนอร์ที่มีคำว่า `worker` = **0**
และโฟลเดอร์ production ยัง **ไม่มี** `docker-compose.worker.yml`

**การนำ candidate ไปใช้เป็นการตัดสินใจของเจ้าของโปรเจกต์** — ดูทางเลือกในข้อ 31

---

## 21. Proof worker was NOT started

```
คอนเทนเนอร์ที่มีคำว่า ingest-worker หรือ worker : 0
คอนเทนเนอร์ที่กำลังรันบน production (7 ตัว):
  course-advisor-system-backend-1    Up 23 hours
  course-advisor-system-caddy-1      Up 7 days
  course-advisor-system-frontend-1   Up 23 hours
  course-advisor-system-ollama-1     Up 6 weeks (healthy)
  course-advisor-system-postgres-1   Up 6 weeks (healthy)
  course-advisor-system-webapi-1     Up 7 days (healthy)
  db-viewer                          Up 2 weeks
```

ไม่มี `docker compose up worker` · ไม่มี `--profile worker up` · ไม่มีการ `docker run`
อิมเมจด้วย CMD เดิม — การตรวจอิมเมจทุกครั้งใช้ `--entrypoint python` กับ `--rm`
และ `--network none` จึงไม่มีทางแตะฐานข้อมูลหรือ Ollama

ไม่มี `docker compose down` และไม่มี `docker compose up` ทั้ง stack

---

## 22. Proof crawler was NOT run

```
โปรเซสที่ตรงกับ 'pipeline.crawl' : 0
โปรเซส python ที่ไม่ใช่ของระบบบนโฮสต์ทั้งหมด:
  3126055 opc  22:56:32  /usr/local/bin/python3.11 /usr/local/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

มีโปรเซส python ที่ไม่ใช่ของ OS เพียงตัวเดียวคือ uvicorn ของ backend ซึ่งรันมา 22 ชั่วโมง
56 นาที คือรันมาตั้งแต่ก่อนงานรอบนี้เริ่ม

คำขอที่ไปถึง `sci.pnru.ac.th` จากงานรอบนี้: **ไม่มี** — ไม่ได้รัน crawler ทั้งบน
production และบนเครื่องผู้พัฒนาในรอบนี้

### 22.1 แก้ผลการวัดครั้งแรก

การวัดครั้งแรกด้วย `pgrep -fc "pipeline.crawl"` ให้ค่า **2** ซึ่งดูน่ากังวล
ตรวจแล้วพบว่าเป็นการที่ `pgrep -f` จับ **command line ของคำสั่ง ssh ของผมเอง**
เพราะสตริงที่ค้นอยู่ในบรรทัดคำสั่งนั้นด้วย

วัดซ้ำด้วยวิธีที่สตริงค้นไม่ปรากฏใน command line (เขียนสคริปต์เป็นไฟล์ก่อน
แล้วประกอบสตริงด้วย `printf` ในสคริปต์) ได้ **0 ทั้งสามแบบ** และ `ps` ของโฮสต์ทั้งหมด
ก็ยืนยันว่าไม่มีโปรเซส pipeline อยู่จริง

---

## 23. Proof ingestion was NOT run

```
โปรเซสที่ตรงกับ 'pipeline.ingest'  : 0
โปรเซสที่ตรงกับ 'crawl.approve'    : 0
```

หลักฐานจากข้อมูลซึ่งหนักกว่าการนับโปรเซส

| ตัวชี้ว่ามี ingestion | ก่อน | หลัง |
|---|---:|---:|
| `mko.crawl_decisions` | 0 | **0** |
| `course_documents` | 31 | **31** |
| `course_chunks` | 9039 | **9039** |
| `documents` PDF | 30 | **30** |
| `staging` files | 0 | **0** |
| `crawl_sources` ที่ไม่ใช่ `unchanged` | 0 | **0** |

ถ้ามี ingestion เกิดขึ้นแม้งานเดียว ค่าเหล่านี้ต้องเปลี่ยน — ไม่เปลี่ยนแม้ค่าเดียว

---

## 24. Production post-deploy baseline

วัดเมื่อ **2026-09-30T00:03:23Z** (ตรวจครั้งสุดท้ายหลังการตรวจอิมเมจทุกครั้งเสร็จแล้ว)

| รายการ | ค่า |
|---|---|
| users / active / admins | 198 / 198 / 1 |
| courses | 24 |
| course_documents | 31 |
| course_chunks | 9039 |
| crawl_sources | 12 · unchanged 12 · needs_review 6 · staging_path ไม่ null 0 |
| crawl_decisions | 0 |
| v_crawl_queue | 6 |
| chat_messages | 6640 |
| chat_answer_cache | 160 |
| embedding dimension | 1024 |
| courses code `TEST%` | 0 |
| staging files | 0 |
| documents PDF | 30 |

---

## 25. Before / after data diff

| รายการ | ก่อน (23:56:54Z) | หลัง (00:03:23Z) | ต่าง |
|---|---|---|---|
| users | 198 | 198 | **ไม่มี** |
| active | 198 | 198 | **ไม่มี** |
| admins | 1 | 1 | **ไม่มี** |
| courses | 24 | 24 | **ไม่มี** |
| course_documents | 31 | 31 | **ไม่มี** |
| course_chunks | 9039 | 9039 | **ไม่มี** |
| crawl_sources | 12 | 12 | **ไม่มี** |
| unchanged | 12 | 12 | **ไม่มี** |
| needs_review | 6 | 6 | **ไม่มี** |
| staging_path ไม่ null | 0 | 0 | **ไม่มี** |
| crawl_decisions | 0 | 0 | **ไม่มี** |
| v_crawl_queue | 6 | 6 | **ไม่มี** |
| chat_messages | 6640 | 6640 | **ไม่มี** |
| chat_answer_cache | 160 | 160 | **ไม่มี** |
| embedding dimension | 1024 | 1024 | **ไม่มี** |
| staging files | 0 | 0 | **ไม่มี** |
| documents PDF | 30 | 30 | **ไม่มี** |
| courses code `TEST%` | 0 | 0 | **ไม่มี** |

**ต่างกัน 0 รายการจาก 18 รายการที่ตรวจ** — ไม่มี data mutation จากการ deploy

โหมดและเจ้าของของโฟลเดอร์สำคัญไม่เปลี่ยน:
`staging/crawl` = `755 ubuntu:ubuntu` · `documents` = `755 ubuntu:ubuntu`

---

## 26. Before / after container diff

| service | container ID | StartedAt | restarts | เปลี่ยน |
|---|---|---|---:|---|
| backend | `fda31caa20c4` → `fda31caa20c4` | `2026-09-29T01:06:17.872Z` → เท่าเดิม | 0 → 0 | **ไม่** |
| frontend | `2886c1bf9183` → `2886c1bf9183` | `2026-09-29T01:07:21.190Z` → เท่าเดิม | 0 → 0 | **ไม่** |
| caddy | `a2957d7b8fc3` → `a2957d7b8fc3` | `2026-09-22T21:23:48.949Z` → เท่าเดิม | 0 → 0 | **ไม่** |
| postgres | `e8c091a4fc60` → `e8c091a4fc60` | `2026-08-18T14:17:25.705Z` → เท่าเดิม | 0 → 0 | **ไม่** |
| ollama | `e6ac0350c722` → `e6ac0350c722` | `2026-08-18T14:17:25.705Z` → เท่าเดิม | 0 → 0 | **ไม่** |
| webapi | `6a73308d4f39` → `6a73308d4f39` | `2026-09-22T21:21:35.624Z` → เท่าเดิม | 0 → 0 | **ไม่** |

เทียบทั้ง container ID และ StartedAt ไม่ใช่ดู `RestartCount` อย่างเดียว เพราะการ recreate
จะรีเซ็ต `RestartCount` เป็น 0 ด้วย

**ไม่มีบริการใดถูก restart หรือ recreate** — ถูกต้องตามที่ควร เพราะ F1 อยู่ใน
`pipeline/crawl/http.py` ซึ่งอยู่ในอิมเมจ worker/crawler เท่านั้น backend · frontend ·
Caddy · PostgreSQL · Ollama · webapi ไม่เกี่ยวเลย

---

## 27. Rollback image / reference

| | ค่า |
|---|---|
| อิมเมจสำหรับ rollback | `course-advisor-system-ingest-worker:617110e` |
| image ID | `sha256:c80cc9b2114139cc38ef91c044a8517b2cf4f30611c663d55de3b99747ae4588` |
| OCI revision | `617110e975dccc94b5e67f77990e34a071ccf9a0` |
| สถานะ | **ยังอยู่บนเซิร์ฟเวอร์ ไม่ถูกลบ ไม่ถูก relabel** |
| reference สำหรับ rollback | `docker-compose.worker.yml` ที่ commit ไว้ยังชี้ `:617110e` อยู่แล้ว |

**rollback ในสถานะปัจจุบันไม่ต้องทำอะไรเลย** เพราะ deployment reference ยังไม่ถูกเปลี่ยน
(ข้อ 20) ถ้าภายหลังเปลี่ยนแล้วพบปัญหา ให้ชี้กลับ `:617110e` — เป็นการ rollback
ระดับ config/image reference เท่านั้น

**ไม่ต้อง rollback ฐานข้อมูล** — รอบนี้ไม่มี migration ไม่มีการเปลี่ยน schema
และไม่มีการเปลี่ยนข้อมูลแม้แถวเดียว

---

## 28. Local git final state

```
branch            mko-phase2
HEAD              7af085b2e8138c5f7d10229af4a68b8e435c0a63   = DEPLOY_REV
origin/mko-phase2 7af085b2e8138c5f7d10229af4a68b8e435c0a63   ตรงกับ DEPLOY_REV
origin/main       b78b3f8bf895685874d9a52c66b45569072f0514   ไม่เปลี่ยน

git status (ไม่นับ ?? docs/)   ว่าง — working tree สะอาด
```

```
git log -5 --oneline
  7af085b test: add isolated crawler ingestion e2e harness
  5d8f82b fix: make staged crawler PDFs readable by the review backend
  2fdc6f2 chore: version the deployment files for the crawler review rollout
  617110e feat: add approved curriculum ingest worker
  0b86ef2 feat: add crawler admin review interface
```

ไฟล์ทดสอบที่อยู่ใน tree ของ HEAD แล้ว ครบหกไฟล์ตามที่อนุมัติ

```
eval/e2e/README.md  eval/e2e/docker-compose.e2e.yml  eval/e2e/fakesite/server.py
eval/e2e/make_test_pdf.py  eval/e2e/run_e2e.py  eval/e2e/seed.py
```

บนเครื่องผู้พัฒนา: ไม่มี resource ของ `sci-advisor-e2e` ค้าง (containers 0 · volumes 0 · images 0)
รายงานทั้งหมดใน `docs/` ยัง untracked ตามเดิม — **ไม่ commit**

---

## 29. Server final state

### 29.1 อิมเมจ worker

```
course-advisor-system-ingest-worker:7af085b | 9d5c623b7e0a | 2026-09-29 23:59:08 UTC | 330MB
  OCI revision = 7af085b2e8138c5f7d10229af4a68b8e435c0a63
  STAGED_FILE_MODE = 0o644

course-advisor-system-ingest-worker:617110e | c80cc9b21141 | 2026-09-28 06:15:45 UTC | 330MB
  OCI revision = 617110e975dccc94b5e67f77990e34a071ccf9a0
  STAGED_FILE_MODE = ImportError (โค้ดเก่า)          <- เก็บไว้สำหรับ rollback
```

### 29.2 Release directory

```
/home/ubuntu/release-7af085b-worker/   (mode 750 ubuntu:ubuntu)
  build-worker-7af085b.log                7,497 ไบต์
  compose.worker-candidate-7af085b.yml    4,932 ไบต์   <- เตรียมไว้ ยังไม่นำไปใช้
  release-7af085b-worker.manifest.tsv     3,499 ไบต์
  release-7af085b-worker.tar            501,760 ไบต์
  src/                                   38 ไฟล์
```

### 29.3 โฟลเดอร์ production

```
/home/ubuntu/course-advisor-system/
  docker-compose.gpu.yml  docker-compose.prod.yml
  docker-compose.staging.yml  docker-compose.yml
  ยังไม่มี docker-compose.worker.yml
  staging/crawl : 0 ไฟล์ · mode 755 ubuntu:ubuntu
```

ไม่ได้ลบ release directory หรือ backup ของรอบก่อนใด ๆ

---

## 30. Known limitation S1 — ไม่แก้ในรอบนี้

`publish_document()` ที่ `pipeline/crawl/approve.py:296` ใช้ `shutil.copyfile` ซึ่ง
**เคารพ umask** ไฟล์ในคลังเอกสารจึงเป็น `0644` เพราะอิมเมจ worker มี umask `0022`
(ยืนยันแล้วในอิมเมจใหม่: `umask = 0o22`)

ถ้าวันหนึ่งมีใครรัน worker บนโฮสต์ในนามผู้ใช้ `ubuntu` ซึ่งมี umask `0002`
ไฟล์ที่ publish จะกลายเป็น **`0664` — group-writable**

**บันทึกไว้เป็น known observation เท่านั้น ไม่แก้ในรอบนี้ ไม่ขยาย scope**

ปัจจุบันยังไม่เกิดเพราะ `docker-compose.worker.yml:36` บังคับ `user: "1001:1001"`
ในคอนเทนเนอร์เสมอ และ CMD ของอิมเมจไม่ถูกรันบนโฮสต์

---

## 31. Deviations / blockers

### B1 — deployment reference ไม่มีอยู่บน production · **ต้องให้เจ้าของตัดสิน**

รายละเอียดทั้งหมดอยู่ในข้อ 20 สรุปทางเลือก

| ทางเลือก | ต้องทำอะไร | ข้อแลก |
|---|---|---|
| **A** | commit ที่สามแก้บรรทัด `image:` ในโปรเจกต์ แล้ว push | `HEAD` จะเลย DEPLOY_REV ไป 1 commit · ต้องยอมรับว่า image ที่ build มาจาก commit ก่อนหน้า (ซึ่งไม่ผิดอะไร เพราะ commit ที่สามไม่แตะโค้ดที่อยู่ในอิมเมจ) หรือ rebuild ใหม่ให้ตรง |
| **B** | ติดตั้ง `compose.worker-candidate-7af085b.yml` เป็น `docker-compose.worker.yml` ในโฟลเดอร์ production | การ start worker จะเหลือคำสั่งเดียว — ย้อนคุณสมบัติความปลอดภัยที่ Step 3 ตั้งใจสร้าง |
| **C** | ไม่ติดตั้งอะไร ใช้ `-f` ชี้ไฟล์ใน release directory ตอนที่จะรัน worker จริง | reference ไม่อยู่ในโปรเจกต์ ต้องจำ path เอง แต่ปลอดภัยที่สุดและไม่ต้อง commit เพิ่ม |

**ผมไม่ได้เลือกให้** เพราะทั้งสามทางมีผลต่างกันในเรื่องที่เจ้าของเป็นคนตัดสิน
(ประวัติ git · ความปลอดภัยของ production · ความสะดวกตอนใช้งาน)
ในสถานะปัจจุบันอิมเมจพร้อมอยู่บน production แล้ว และไม่มีอะไรทำงานอยู่

### D1 — `pipeline/` ต้องอยู่ใน release ของรอบนี้

Step 3 กัน `pipeline/` ออกจาก release โดยเจตนาเพื่อให้ไม่มีทางรัน worker จาก release
directory แต่รอบนี้ **ต้องมี** `pipeline/` เพราะเป็น input ของการ build อิมเมจ worker

ลดความเสี่ยงด้วย: วางใน release directory ที่ mode 750 แยกจากโฟลเดอร์ production ·
ไม่ติดตั้ง `docker-compose.worker.yml` ลงโฟลเดอร์ production · ทุกการรันอิมเมจใช้
`--entrypoint python --network none --rm` ไม่เคยใช้ CMD เดิม

### D2 — แก้ผลการวัดโปรเซส

`pgrep -f` ครั้งแรกให้ค่า 2 ซึ่งเป็นการจับ command line ของ ssh เอง
วัดซ้ำด้วยวิธีที่ไม่จับตัวเองได้ 0 ทั้งสามแบบ — รายละเอียดในข้อ 22.1
รายงานไว้เพราะค่าแรกถ้าอ่านผ่าน ๆ จะเข้าใจผิดว่ามีอะไรทำงานอยู่

### D3 — `db-viewer` เป็นคอนเทนเนอร์ตัวที่เจ็ดบน production

`db-viewer` (adminer) สร้างเมื่อ 2026-09-14 ไม่อยู่ใน compose project ของโปรเจกต์
เป็นของเจ้าของเครื่องที่มีอยู่ก่อนงานรอบนี้ · ใส่ไว้ในข้อ 21 เพื่อความครบถ้วน ไม่ได้แตะ

### ที่ไม่ใช่ deviation

- อิมเมจ build เร็ว (7 วินาที) เพราะ layer `pip install` ถูก cache จาก build เดิม
  `requirements.txt` และ `pipeline/Dockerfile` เหมือนกันทุกไบต์กับที่ build `:617110e`
  จึงไม่มีการติดตั้ง dependency ใหม่ ซึ่งถูกต้องตามที่ควรเป็น

---

## 32. Final verdict

### **F1 COMMIT: PASS**

`5d8f82b` (F1 fix + regression, +222 −3) และ `7af085b` (E2E harness 6 ไฟล์, +1226)
stage แบบระบุ path ทุกไฟล์ · `git diff --cached --check` ว่างทั้งสองครั้ง ·
CRLF ใน blob = 0 · ไม่มี unrelated file · ไม่มี `.env`/credential ของ production ·
ไม่มี PDF/test output/log/`__pycache__`/backup

### **PUSH mko-phase2: PASS**

`2fdc6f2..7af085b` fast-forward · ไม่ force · ไม่ push tag · ไม่ push main ·
`origin/mko-phase2 == DEPLOY_REV` · `origin/main` ไม่เปลี่ยน

### **F1 WORKER IMAGE BUILD: PASS**

build จาก archive ของ exact DEPLOY_REV (per-file hash ตรง 38/38) ·
`course-advisor-system-ingest-worker:7af085b` · ID `9d5c623b7e0a` ·
OCI revision = DEPLOY_REV · `STAGED_FILE_MODE = 0o644` ยืนยันตอนรันจริง ·
uid/gid `1001:1001` เดิม · CMD/User/WorkDir เดิม ·
อิมเมจเก่าไม่ถูกลบ ไม่ถูก relabel และพิสูจน์ได้ว่าเนื้อโค้ดต่างกันจริง

### **F1 SAFE PRODUCTION DEPLOYMENT: PARTIAL**

| องค์ประกอบที่ Phase 8/9 นิยามว่าคือการ deploy | สถานะ |
|---|---|
| อิมเมจใหม่มีอยู่บน production host | **ครบ** |
| source/config พร้อม | **ครบ** (release directory + candidate file ตรวจ hash แล้ว) |
| deployment reference ชี้ revision ใหม่ | **หยุดไว้** — ดูข้อ 20 และ 31 (B1) |

หยุดตามคำสั่ง "หากจำเป็นต้องแก้อะไรมากกว่านั้น: STOP และรายงานก่อน"
ไม่ใช่เพราะมีอะไรล้มเหลว

### **PRODUCTION DATA SAFETY: PASS**

18 / 18 ค่าตรง baseline · `crawl_decisions` = 0 · `courses code TEST%` = 0 ·
staging = 0 ไฟล์ · โหมด/เจ้าของของโฟลเดอร์ไม่เปลี่ยน · ไม่มี migration

### **PRODUCTION SERVICE SAFETY: PASS**

คอนเทนเนอร์ทั้งหก container ID และ StartedAt ไม่เปลี่ยน · restarts = 0 ทุกตัว ·
ไม่มี `docker compose down` · ไม่มี `docker compose up` ทั้ง stack ·
backend/frontend/Caddy/PostgreSQL/Ollama/webapi ไม่ถูก restart แม้ตัวเดียว

### **PRODUCTION CRAWLER EXECUTED: NO**

### **PRODUCTION WORKER EXECUTED: NO**

### **PRODUCTION INGESTION EXECUTED: NO**

โปรเซสที่ตรงกับ `pipeline.crawl` / `pipeline.ingest` / `crawl.approve` = **0 ทั้งสามแบบ** ·
คอนเทนเนอร์ worker = 0 · และหลักฐานจากข้อมูล: `crawl_decisions` · `course_documents` ·
`course_chunks` · `documents` PDF · staging ไม่เปลี่ยนแม้ค่าเดียว

### **PRODUCTION ONE-JOB INGESTION: ยัง NO-GO**

`crawl_sources` ทั้ง 12 แถวยังเป็น `unchanged` · `staging_path` null ทั้งหมด ·
staging ว่าง · **6 แถวในคิวไม่ใช่ candidate** (ถูกตั้งธงเพราะจับคู่หลักสูตรไม่ชัด
ไม่ใช่เพราะมีไฟล์ใหม่) ยังไม่มี legitimate new/changed PDF จากเว็บคณะ

---

## สิ่งที่ไม่ได้ทำ

ไม่ได้รัน production crawler · ไม่ได้รัน production worker · ไม่ได้ ingestion ·
ไม่ได้สร้าง embedding · ไม่ได้ POST approve/ignore/undo · ไม่ได้สร้าง fake production
candidate · ไม่ได้เปลี่ยน `crawl_sources`/`crawl_decisions`/`courses`/`documents`/`chunks` ·
ไม่ได้แก้ Supabase · ไม่ได้แก้ auth · ไม่ได้แก้ Caddy · ไม่ได้ restart backend/frontend/
PostgreSQL/Ollama/webapi · ไม่ได้ทำ migration · ไม่ได้ merge main · ไม่ได้ force push ·
ไม่ได้ลบอิมเมจสำหรับ rollback · ไม่ได้แก้ S1

---

## STOP

รอ **OWNER REVIEW**

เรื่องที่ต้องให้เจ้าของโปรเจกต์ตัดสิน

1. **B1 — จะเปลี่ยน deployment reference ด้วยทาง A, B หรือ C** (ข้อ 31)
   สถานะปัจจุบัน: อิมเมจพร้อมบน production · reference ยังชี้ `:617110e` · ไม่มีอะไรทำงานอยู่
2. **S1** — จะทำเป็นงานแยกหรือปล่อยไว้ (ข้อ 30)

ห้ามรัน crawler · ห้ามรัน worker · ห้าม ingestion จนกว่าจะได้รับอนุมัติแยก

STOP
