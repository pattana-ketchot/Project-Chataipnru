# Phase 3D Step 3 (RESUME) — Controlled Production Deployment · NO INGESTION / NO EMBEDDING

| | |
|---|---|
| วันที่ | 2026-09-29 · เวลาในรายงานเป็น UTC (ไทย = UTC+7) |
| Repository | `D:/workspace/course-advisor-system-mko2` · branch `mko-phase2` |
| **DEPLOY_REV** | **`2fdc6f241fc1742047b572ee2ef354cd811f9401`** |
| Production | `ubuntu@161.118.237.37` · compose project `course-advisor-system` · project dir `/home/ubuntu/course-advisor-system` |
| ผลรวม | **Deployment สำเร็จครบทุก gate** — migration 004 · backend Phase 3A · frontend Phase 3B · staging mount |
| ingestion / embedding | **ไม่มี ingestion** · embedding เกิดขึ้น **1 ครั้ง** จาก warmup เดิมของบริการ (ดูข้อ 13) |
| GO/NO-GO สำหรับ one-job ingestion ในอนาคต | **NO-GO** (readiness assessment เท่านั้น ไม่ใช่การอนุญาต) |

การแม็ป checkpoint: ใช้เลขเดิมของ Step 3 — CP1 (push + packaging), CP2 (migration 004),
CP3 (build backend), CP4 (build frontend), CP5 (backend cutover + staging mount),
CP6 (frontend cutover + เส้นทางเข้า UI), CP7 (admin), CP8 (smoke/regression),
CP9 (worker คง PREPARED), CP10 (candidate คง DEFERRED), CP11 (ไม่ refresh document_store),
CP12 (ปิดงาน + รายงาน)

---

## 1. Push — การอนุมัติ คำสั่ง ผลลัพธ์ และ ref ก่อน/หลัง

**การอนุมัติที่ใช้:** เจ้าของโปรเจกต์อนุมัติให้ push **เฉพาะ commit `2fdc6f241fc1742047b572ee2ef354cd811f9401`
ไปที่ `origin/mko-phase2`** เท่านั้น ไม่รวม main, ไม่ force, ไม่เปลี่ยน remote, ไม่สร้าง revision ใหม่

### 1.1 Gate ก่อน push (อ่านอย่างเดียว ไม่ reset/stash/clean/amend)

| ข้อตรวจ | ค่าที่ต้องได้ | ค่าจริง | ผล |
|---|---|---|---|
| branch | `mko-phase2` | `mko-phase2` | PASS |
| local HEAD | `2fdc6f24…9401` | `2fdc6f241fc1742047b572ee2ef354cd811f9401` | PASS |
| parent (ต้องมีเดียว) | `617110e9…9f0a` | `617110e975dccc94b5e67f77990e34a071ccf9a0` · 1 parent | PASS |
| live `refs/heads/mko-phase2` | `617110e9…` | `617110e975dccc94b5e67f77990e34a071ccf9a0` | PASS |
| live `refs/heads/main` | `b78b3f8b…` | `b78b3f8bf895685874d9a52c66b45569072f0514` | PASS |
| tracked modified / staged | 0 / 0 | 0 / 0 | PASS |
| diff เทียบ parent | สามไฟล์ที่เพิ่ม 144 บรรทัด | 3 ไฟล์ · `3 files changed, 144 insertions(+)` | PASS |
| untracked นอก `docs/` | ไม่มี | 0 ไฟล์ | PASS |

**push configuration:** `remote.origin.url = https://github.com/pattana-ketchot/Project-Chataipnru.git`
(ไม่มี credential ใน URL) · ไม่มี `pushurl` · `mirror` ไม่ได้ตั้ง · `remote.origin.push` ไม่ได้ตั้ง ·
`push.default` ไม่ได้ตั้ง · `remote.pushDefault` ไม่ได้ตั้ง · `insteadOf`/`pushInsteadOf` 0 รายการ ·
remote มีเพียง `origin`

### 1.2 ไบต์ของ blob ที่ commit (อ่านดิบ ไม่ผ่านการแปลงข้อความของ shell)

| path | ไบต์ | บรรทัด | CRLF | sha256 | ตรงกับที่กำหนด |
|---|---:|---:|---:|---|---|
| `docker-compose.staging.yml` | 2977 | 34 | 0 | `fa85a75762379cb1491965b4801149713dee88b2c4e4ac3b6eda3af193f4c49f` | ตรง |
| `docker-compose.worker.yml` | 4932 | 52 | 0 | `a6a4dd87013ca42f1e462f7880dfb6543b4c7394761a6d5fa1261127a21f5143` | ตรง |
| `pipeline/Dockerfile` | 4395 | 58 | 0 | `ca48cd2da16c7fefcd72edc42fa943b728ad67ec627d425e00db3c91848971a1` | ตรง |

Phase 3A/3B source, Dockerfile ทั้งสอง, dependency manifest และ migration 004
ยืนยันว่ามีอยู่ที่ commit นี้ครบ 13 path ที่ตรวจ

### 1.3 คำสั่ง push และผลลัพธ์

ตรวจซ้ำทันทีก่อน push: HEAD `2fdc6f24…`, tracked/staged = 0/0,
live `mko-phase2` = `617110e9…`, live `main` = `b78b3f8b…`

```bash
git -c push.followTags=false push origin 2fdc6f241fc1742047b572ee2ef354cd811f9401:refs/heads/mko-phase2
```

```
To https://github.com/pattana-ketchot/Project-Chataipnru.git
   617110e..2fdc6f2  2fdc6f241fc1742047b572ee2ef354cd811f9401 -> mko-phase2
exit code: 0
```

fast-forward ปกติ · ไม่ force · ไม่มี `+` นำหน้า refspec · ไม่ push tag · ไม่ mirror · ไม่ push ทุก branch

### 1.4 ยืนยันหลัง push (live ref)

```
origin/mko-phase2 = 2fdc6f241fc1742047b572ee2ef354cd811f9401   = DEPLOY_REV
origin/main       = b78b3f8bf895685874d9a52c66b45569072f0514   ไม่เปลี่ยนจาก baseline
tag บน remote     = 0 รายการ
```

**ไม่มี blocker** — การปฏิเสธที่เกิดขึ้นในรอบก่อนไม่เกิดซ้ำในรอบนี้

---

## 2. Exact deployed revision

```
DEPLOY_REV = 2fdc6f241fc1742047b572ee2ef354cd811f9401
```

deploy ครบทั้งสามชั้นจาก revision เดียวกัน: database schema (migration 004),
backend (Phase 3A) และ frontend (Phase 3B) ไม่มีชั้นใด rollback

---

## 3. Package — path, hash, การโอน และ hash ของ config

### 3.1 Allowlist ที่ review แล้ว

เลือกจาก build input จริงที่อ่านจาก Dockerfile ของ `DEPLOY_REV` ไม่ใช่การเดา

- `backend/` (64 ไฟล์) และ `llm/` (5 ไฟล์) — `backend/Dockerfile` ใช้ context เป็น root ของ repo
  และ `COPY backend/ backend/` + `COPY llm/ llm/`
- `frontend/` (28 ไฟล์) — compose ตั้ง `context: ./frontend`, Dockerfile ใช้
  `COPY package.json package-lock.json ./` แล้ว `COPY . .`
- `db/migrations/004_crawl_decisions.sql`
- `docker-compose.prod.yml`, `docker-compose.staging.yml`

**ที่ตั้งใจไม่ใส่:** `.env` และไฟล์ secret ทุกชนิด · `.git` · `docs/` และรายงานทั้งหมด ·
`documents/` และ `staging/` · build output · **`pipeline/` และ `docker-compose.worker.yml`**
(ไม่จำเป็นต่อ deploy รอบนี้ และการไม่ใส่ทำให้ไม่มีทางรัน worker จาก release directory)

ตรวจไฟล์ที่อาจมีค่าลับใน allowlist: พบชื่อที่เข้าข่ายเพียง `frontend/.env.example`
อ่านแล้วมีเฉพาะ `NEXT_PUBLIC_API_URL=/api` และบรรทัดคอมเมนต์ **ไม่มีค่าลับ**
ไฟล์ `.env*` ที่ track ใน repo มีเพียง `.env.example` สองไฟล์ ไม่มี `.env` จริง

ตรวจ archive rules ใหม่ที่ `DEPLOY_REV`: `.gitattributes` มีเพียง `*.sh text eol=lf`,
`export-ignore` 0 รายการ, `export-subst` 0 รายการ, มี `.gitattributes` ไฟล์เดียวใน tree

### 3.2 Deterministic archive

```bash
git -c core.autocrlf=false archive --format=tar 2fdc6f241fc1742047b572ee2ef354cd811f9401 -- \
    backend llm frontend db/migrations/004_crawl_decisions.sql \
    docker-compose.prod.yml docker-compose.staging.yml > release-2fdc6f2.tar
```

ใช้ tar **ไม่บีบอัด** เพื่อเลี่ยง timestamp ของ gzip ที่ทำให้ผลไม่ deterministic

```
package  release-2fdc6f2.tar
  ไบต์    1,208,320
  sha256  e64591698aa919c5eccb188a7b76aa28b0dad35b2b9e5275ad23658c6addd814
manifest release-2fdc6f2.manifest.tsv   (sha256 \t bytes \t path ต่อบรรทัด)
  ไบต์    10,031   รายการ 100
  sha256  41d1acbcaeb40381809a76c3b7d918bececd350f2a6ade5c6fe56a3f3ab39b8f
```

ตรวจไส้ archive เทียบ committed blob ทีละไฟล์: **100 ไฟล์ · เกิน 0 · ขาด 0 · hash ต่าง 0**
ไม่มี member ที่ไม่ใช่ไฟล์/โฟลเดอร์ (ไม่มี symlink) · ไม่มี path แบบ absolute หรือมี `..` ·
ownership ในไฟล์ tar เป็น `0:0 root:root` ทั้งหมด (deterministic) ·
top-level = `backend`, `db`, `frontend`, `llm`, `docker-compose.prod.yml`, `docker-compose.staging.yml`

### 3.3 การโอนและการตรวจหลังโอน

ปลายทางเป็น release directory แยกตาม revision **ไม่ extract ทับโฟลเดอร์ production**

```
/home/ubuntu/release-2fdc6f2/          (mode 750)
  release-2fdc6f2.tar                  sha256 e64591698aa919c5… ตรงกับต้นทาง
  release-2fdc6f2.manifest.tsv         sha256 41d1acbcaeb40381… ตรงกับต้นทาง
  src/                                 แตกไฟล์ที่นี่ 100 ไฟล์ · symlink 0
  rollback_004.sql                     sha256 d1d246860eb6705ce6c3c66ee16b5a26226ba116c0f10a44d94babe8090db911
  compose.pin-backend-2fdc6f2.yml      sha256 56e1f03b17aa4c58b3d4b4af45e79849067621b2cc8cb6bd79584db348448abf
  compose.pin-frontend-2fdc6f2.yml     sha256 ea84cb54dfc4ca058d2815f718bd1fea5d1a196ec69719d3f974131a66743421
  compose.rollback-backend.yml         sha256 6954f7154f8f355c3403cf7959ea384386a6adcc50ccd9535c3423eda812b462
  compose.rollback-frontend.yml        sha256 35cab9fd097308e46b8e8cb413caa16080684a0bff606d31a5e37c96264489eb
  build-backend.log  build-frontend.log
```

ตรวจ per-file hash หลังแตกไฟล์เทียบ manifest: **100/100 OK**

ยืนยันว่าไม่มีของที่ไม่ควรมีใน package: `.env` จริง 0 ไฟล์ · `.env.example` 1 ไฟล์ ·
`pipeline/` ไม่มี · `docker-compose.worker.yml` ไม่มี · `.git` ไม่มี

### 3.4 Hash ของ config และ migration (full ไม่ใช่ prefix)

| ไฟล์ | sha256 เต็ม | committed vs production |
|---|---|---|
| `docker-compose.prod.yml` | `d76afeef4ec1383d28f595f600a3383c857f808a95842880c476ff955d0926c8` | **เท่ากันทุกไบต์** (10,606 ไบต์ 162 บรรทัด) |
| `db/migrations/004_crawl_decisions.sql` | `0a689ea3dbe84be941cea39f150f19a64c229e44f4c808d1f19bc35ca0a8605e` | 11,949 ไบต์ · 153 บรรทัด · CRLF 0 |
| `docker-compose.staging.yml` | `fa85a75762379cb1491965b4801149713dee88b2c4e4ac3b6eda3af193f4c49f` | ติดตั้งลง production แล้ว hash ตรง |

prefix เดิม `d76afeef4ec1383d` ที่รายงาน Step 2 ให้ไว้ **ตรงกับ full hash ที่คำนวณใหม่ทั้งสองฝั่ง**
ไม่มีความต่างที่ต้องอธิบาย และไม่ได้เขียนทับ `docker-compose.prod.yml` ของ production

### 3.5 production `.env`

คงอยู่ที่ `/home/ubuntu/course-advisor-system/.env` · `mode 600` · owner `ubuntu:ubuntu` ·
mtime `2026-09-22 21:20:18` **ไม่เปลี่ยน** · ไม่ได้อ่านค่า ไม่ได้คัดลอกเข้า build context
ไม่ได้ฝังในอิมเมจ (ตรวจแล้วว่าอิมเมจใหม่ทั้งสองมีไฟล์ `.env` 0 ไฟล์) และไม่ได้พิมพ์ค่า
resolved ของ compose ลง log — การตรวจ compose ดึงเฉพาะ field ที่ต้องใช้

---

## 4. Production mutation ledger ครบถ้วน

| # | เวลา (UTC) | checkpoint | ชั้น | before | after | ผล | rollback |
|---|---|---|---|---|---|---|---|
| 0 | 2026-09-29 00:30:19 | CP0.3 **(รอบก่อน ไม่ใช่รอบนี้)** | image tag | ไม่มี tag rollback ของ backend | `course-advisor-system-backend:rollback-pre-phase3d` → `sha256:d1d1ba713412…` | สำเร็จ | `docker image rm <tag>` (ลบเฉพาะ tag) |
| 1 | ~00:55 | CP1 | filesystem | ไม่มี `/home/ubuntu/release-2fdc6f2` | release dir + archive + manifest + src (100 ไฟล์) | สำเร็จ | `rm -rf /home/ubuntu/release-2fdc6f2` |
| 2 | 01:00:44 | **CP2** | **database schema** | migrations 001–003 · ไม่มี `crawl_decisions`/`v_crawl_queue` | + `004_crawl_decisions` · ตาราง 15 คอลัมน์ 0 แถว · 4 index · 1 view · grants | สำเร็จ `exit 0` | `psql -f /home/ubuntu/release-2fdc6f2/rollback_004.sql` |
| 3 | 01:02:35 | CP3 | image | ไม่มี `:2fdc6f2` | `course-advisor-system-backend:2fdc6f2` → `sha256:4a45677ec010…` | สำเร็จ | `docker image rm` (tag เดิมไม่ถูกแตะ) |
| 4 | 01:04:54 | CP4 | image | ไม่มี `:2fdc6f2` | `course-advisor-system-frontend:2fdc6f2` → `sha256:591ab6d935bb…` | สำเร็จ | `docker image rm` |
| 5 | ~01:06 (ก่อน cutover ทันที) | CP5 | production config file | ไม่มี `docker-compose.staging.yml` ในโฟลเดอร์ production | ติดตั้งจาก committed bytes · sha256 `fa85a757…4c49f` · mode 644 | สำเร็จ | `rm /home/ubuntu/course-advisor-system/docker-compose.staging.yml` |
| 6 | 01:06:17 | **CP5** | **service backend** | container `3aa33e3b46cf` image `d1d1ba713412` started 2026-09-23T23:53:41Z restarts 0 | container `fda31caa20c4` image `4a45677ec010` started 01:06:17Z restarts 0 | สำเร็จ | ดูข้อ 17 |
| 7 | 01:06:1x | CP5 (ผลพลอยได้) | ollama | — | warmup ของบริการเรียก `POST ollama:11434/api/embeddings` **1 ครั้ง** (สตริง `"warmup"`) | เกิดขึ้นจริง | ไม่มีอะไรต้องย้อน ไม่เขียนฐานข้อมูล |
| 8 | 01:07:21 | **CP6** | **service frontend** | container `58dd38b8338c` image `ce65aad64305` started 2026-09-04T17:27:43Z restarts 0 | container `2886c1bf9183` image `591ab6d935bb` started 01:07:21Z restarts 0 | สำเร็จ | ดูข้อ 17 |

**แยกให้ชัด:** รายการที่ 0 เป็น mutation ของรอบก่อน (Step 3 ครั้งแรกที่หยุดที่ push)
รายการที่ 1–8 เกิดขึ้นในรอบ resume นี้

### สิ่งที่ไม่ได้ทำกับ production

ไม่แตะ `.env` · ไม่แตะ `docker-compose.prod.yml` · ไม่แตะ `Caddyfile` และไม่ restart/recreate Caddy ·
ไม่ restart postgres/ollama/webapi · ไม่เขียนข้อมูลลงตารางใด (INSERT เดียวคือแถว bookkeeping
ของ migration) · ไม่แตะ `users`/`mko.crawl_sources`/knowledge tables · ไม่สร้างไฟล์ใน
`documents/` หรือ `staging/` · ไม่ prune อิมเมจ · ไม่ลบ backup หรือ tag ใด ·
ไม่ push อิมเมจไป registry · ไม่ merge/push main · ไม่สร้าง commit เพิ่ม

---

## 5. Migration 004 — catalog ก่อน/หลัง, transaction, rollback artifact

### 5.1 Before state (จับจาก catalog จริง ไม่ใช่จากรายงานเก่า)

```
objects ที่ 004 จะสร้าง (crawl_decisions, v_crawl_queue, 3 index) : ไม่มีเลย
has_schema_privilege USAGE บน mko : advisor_api = true, advisor_ingest = true   ← มีอยู่ก่อน 004
nspacl mko          : postgres=UC/postgres | advisor_ingest=U/postgres | advisor_api=U/postgres
relacl crawl_sources: postgres=arwdDxt/postgres | advisor_ingest=arw/postgres
   -> advisor_api ไม่มีสิทธิ์ใดบน mko.crawl_sources ก่อน 004
view ใน mko        : v_crawl_pending, v_live_list_items, v_live_publication, v_live_values,
                     v_published_curricula, v_published_field_values, v_published_list_items
schema_migrations  : 001_mko_structured, 002_mko_review_publish, 003_crawl_sources
owner              : schema mko = postgres · mko.crawl_sources = postgres · current_user = postgres
default privileges ใน mko : ไม่มี
```

### 5.2 Transaction boundary

อ่านไฟล์จริงก่อน: มี `BEGIN;` 1 ครั้งและ `COMMIT;` 1 ครั้งอยู่ในไฟล์แล้ว
จึงรันตรง ๆ ด้วย `psql -v ON_ERROR_STOP=1 -f` **ไม่ห่อ transaction ซ้อน** และไม่แก้ SQL

```
PGOPTIONS='-c lock_timeout=5s -c statement_timeout=60s'
psql -U postgres -d course_advisor -v ON_ERROR_STOP=1 -f /tmp/m004.sql
```

ยืนยัน hash ของไฟล์สองชั้นก่อนรัน: บนเซิร์ฟเวอร์และในคอนเทนเนอร์ postgres ได้
`0a689ea3dbe84be941cea39f150f19a64c229e44f4c808d1f19bc35ca0a8605e` ตรงกับ committed bytes

ผลลัพธ์: `BEGIN → CREATE TABLE → CREATE INDEX ×3 → CREATE VIEW → DO → INSERT 0 1 → COMMIT`
**exit 0**

**ข้อจำกัดที่ต้องบันทึก:** ไฟล์ commit ตัวเองใน `COMMIT;` บรรทัดสุดท้าย จึงไม่สามารถแทรก
assertion ไว้ "ก่อน COMMIT ในธุรกรรมเดียวกัน" ได้โดยไม่แก้ SQL ที่อนุมัติไว้
จึงใช้วิธีตรวจ baseline invariants ใน read-only transaction **ทันทีก่อน** apply
แล้วตรวจซ้ำหลัง commit ซึ่งปลอดภัยเพราะ 004 เป็น additive ล้วนและ idempotent

### 5.3 After state

| ข้อตรวจ | ค่าที่ต้องได้ | ค่าจริง | ผล |
|---|---|---|---|
| `mko.crawl_decisions` คอลัมน์ | 15 | 15 | PASS |
| CHECK constraint | 7 | 7 | PASS |
| FOREIGN KEY | — | 2 (`crawl_sources`, `course_documents`) | PASS |
| แถวในตาราง | 0 | **0** | PASS |
| index | 4 รายการที่ระบุ | `crawl_decisions_pkey`, `idx_crawl_decisions_source`, `idx_crawl_decisions_todo`, `uq_crawl_decisions_active` | PASS |
| `mko.v_crawl_queue` | สร้างแล้ว | มี · 19 คอลัมน์ | PASS |
| view มีคอลัมน์ `staging_path` | **ต้องไม่มี** | 0 | PASS |
| view มี `has_staged_file` | ต้องมี | 1 | PASS |
| `mko.v_crawl_pending` ของ 003 | ต้องยังอยู่ | ยังอยู่ | PASS |
| `schema_migrations` | 001–003 + 004 หนึ่งแถว | `001,002,003,004_crawl_decisions` · แถวของ 004 = 1 | PASS |
| mko tables / views | 19→20 · 7→8 | 20 · 8 | PASS |

**สิทธิ์ (ตรวจด้วย privilege introspection ไม่ได้ INSERT ทดสอบ)**

| ข้อตรวจ | ต้องได้ | จริง |
|---|---|---|
| `advisor_api` บน decisions (table) | SELECT, INSERT | SELECT, INSERT |
| `advisor_api` column UPDATE | เฉพาะ `superseded_at`, `superseded_by` | เฉพาะสองคอลัมน์นั้น |
| `advisor_api` UPDATE `decision` | ต้องไม่ได้ | false |
| `advisor_api` UPDATE `ingest_started_at` | ต้องไม่ได้ | false |
| `advisor_api` UPDATE `document_id` | ต้องไม่ได้ | false |
| `advisor_api` DELETE บน decisions | ต้องไม่ได้ | false |
| `advisor_api` บน `crawl_sources` | SELECT เฉพาะ `id`, `file_sha256`, `staging_path`, `status` | ตรงทั้งสี่ · table-level ไม่มี |
| `advisor_ingest` บน decisions | SELECT, INSERT, UPDATE | SELECT, INSERT, UPDATE |
| `advisor_ingest` บน queue | SELECT | true |
| `advisor_api` บน queue | SELECT | true |

ACL ดิบหลัง apply

```
relacl crawl_sources   : postgres=arwdDxt/postgres | advisor_ingest=arw/postgres   (ไม่เปลี่ยน — สิทธิ์ใหม่เป็นระดับคอลัมน์ซึ่งเก็บใน pg_attribute.attacl)
relacl crawl_decisions : postgres=arwdDxt/postgres | advisor_api=ar/postgres | advisor_ingest=arw/postgres
nspacl mko             : postgres=UC/postgres | advisor_ingest=U/postgres | advisor_api=U/postgres   (ไม่เปลี่ยน)
```

**Baseline invariants หลัง apply:** `courses=24`, `course_documents=31`, `course_chunks=9039`,
`embedding_dim=1024`, `crawl_sources=12` (unchanged 12, needs_review 6, staging_path NOT NULL 0),
`users=197` active 197 admin 0 — **ไม่เปลี่ยนแม้ค่าเดียว**

### 5.4 Rollback artifact (เตรียมและ review ก่อน apply)

```
path    /home/ubuntu/release-2fdc6f2/rollback_004.sql
ไบต์     3,828   บรรทัด 58
sha256  d1d246860eb6705ce6c3c66ee16b5a26226ba116c0f10a44d94babe8090db911
```

คำสั่งที่เปลี่ยนสภาพในสคริปต์ (ตามลำดับ)

```
BEGIN;
SET LOCAL lock_timeout = '5s';  SET LOCAL statement_timeout = '60s';
LOCK TABLE mko.crawl_decisions IN ACCESS EXCLUSIVE MODE;      -- ถือ lock จนจบธุรกรรม
DO $$ ... IF count(*) <> 0 THEN RAISE EXCEPTION ... END $$;    -- ด่านกันข้อมูลหาย
REVOKE SELECT (id, file_sha256, staging_path, status) ON mko.crawl_sources FROM advisor_api;
DROP VIEW IF EXISTS mko.v_crawl_queue;
DROP TABLE IF EXISTS mko.crawl_decisions;
DELETE FROM mko.schema_migrations WHERE version = '004_crawl_decisions';
COMMIT;
```

จุดที่สร้างจาก catalog จริง ไม่ใช่การคัดลอกตัวอย่าง

- **ไม่ REVOKE `USAGE ON SCHEMA mko`** เพราะ before state แสดงว่า `advisor_api` มีสิทธิ์นี้
  มาก่อน 004 แล้ว (`nspacl` ข้างบน) การถอนจะทำให้สิทธิ์แย่กว่าเดิม
- **ไม่สร้าง "v_crawl_queue รุ่น 003" คืน** เพราะ before state ยืนยันว่า view นี้ไม่มีอยู่เลย
  (003 มีเพียง `v_crawl_pending` ซึ่ง 004 ไม่แตะ) — ตรงตามที่ prompt เตือนไว้
- **ไม่ใช้ CASCADE** เลย ลำดับ DROP ให้ view ไปก่อนตารางเพราะ view อ้างตารางนี้
- **ด่าน non-empty:** ถือ `ACCESS EXCLUSIVE` ก่อนนับแถวและถือไว้จนจบ จึงไม่มีทางมี INSERT
  แทรกระหว่างตรวจกับ DROP ถ้ามีแม้แถวเดียวธุรกรรมล้มทั้งชุด ไม่มีการลบข้อมูล
- ไม่แตะ migration 001–003 และไม่ restore ฐานข้อมูลทั้งก้อน

---

## 6. Build — tag, image ID, OCI label, provenance และการตรวจก่อน cutover

### 6.1 Backend (CP3)

```
tag        course-advisor-system-backend:2fdc6f2          (immutable ไม่ทับ latest/rollback)
image ID   sha256:4a45677ec010fc076e283b1e556bd4c1b0b25bc66786b32ec6f64a76ad0cca46
repoDigest course-advisor-system-backend@sha256:4a45677ec010fc076e283b1e556bd4c1b0b25bc66786b32ec6f64a76ad0cca46 (local ไม่ได้ push registry)
created    2026-09-29T01:02:35Z    ขนาด 324MB    arch amd64/linux
user       appuser    workdir /app/backend
cmd        ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]
labels     org.opencontainers.image.revision = 2fdc6f241fc1742047b572ee2ef354cd811f9401
           org.opencontainers.image.title    = SCI Advisor backend (Phase 3A)
build      context = /home/ubuntu/release-2fdc6f2/src (100 ไฟล์จาก DEPLOY_REV)
           base FROM python:3.11-slim   build arg: ไม่มีค่าลับ
           log /home/ubuntu/release-2fdc6f2/build-backend.log
```

ตรวจ tag collision ก่อน build: `:2fdc6f2` ยังไม่มี · tag ที่ต้องไม่ถูกแตะยืนยันก่อนและหลังว่า
`backend:latest` และ `backend:rollback-pre-phase3d` ยังชี้ `d1d1ba713412` เหมือนเดิม

**พบเพิ่มและต้องบันทึก:** โฟลเดอร์อิมเมจของเซิร์ฟเวอร์มี tag `rollback-<sha>` ของ backend
อยู่ก่อนแล้วหลายรายการ (เช่น `rollback-17abce0`, `rollback-b78b3f8` …) เป็น artifact
ของการ deploy ครั้งก่อน ๆ **ไม่ได้แตะ ไม่ได้ลบ และไม่อนุมานที่มาของอิมเมจจากชื่อ tag**

**การตรวจก่อน cutover (isolated: `--network none`, env ปลอม, `WARMUP_INTERVAL_MINUTES=0`, ไม่รัน lifespan)**

- ไฟล์ Phase 3A อยู่ที่ `/app/backend/app/` ครบ: `services/crawl_review.py`,
  `services/staging_store.py`, `api/routes/crawl_review.py` (รวมไฟล์ที่มีคำว่า crawl/staging 4 ไฟล์)
  พร้อม `services/document_store.py`, `main.py`, `api/deps.py` และ `/app/llm/` 5 ไฟล์
- `.env` ในอิมเมจ **0 ไฟล์**
- **OpenAPI ที่ generate จริง 27 path = 21 เดิม + 6 crawl-review** ครบตามที่ source กำหนด:
  `GET /crawl-review/pending`, `GET /crawl-review/{crawl_source_id}`,
  `GET /crawl-review/{crawl_source_id}/pdf`, `POST …/approve`, `POST …/ignore`, `POST …/undo`
- ตรวจ startup hook ก่อนรันจริง: `lifespan` ทำสองอย่างคือ `_check_embedding_dim()`
  (SELECT `atttypmod` อ่านอย่างเดียว) และเปิด task `_keep_models_warm()` —
  **ไม่มี auto-migration ไม่มีการเขียนฐานข้อมูล ไม่มี job นำเข้า**

**ข้อจำกัดของ provenance:** revision tag และ label ยืนยันได้ว่าอิมเมจ build จาก source ของ
`DEPLOY_REV` แต่ **ไม่ได้อ้างว่า reproducible แบบ bit-for-bit** เพราะ base image
`python:3.11-slim` เป็น floating tag และ `pip install` ดึงรุ่นตามช่วงที่ requirements ระบุ

### 6.2 Frontend (CP4)

```
tag        course-advisor-system-frontend:2fdc6f2
image ID   sha256:591ab6d935bbbdf533ec3fc9e8a50b1378b59e9f849ab6d3303a91b638240eec
created    2026-09-29T01:04:54Z    ขนาด 372MB    arch amd64/linux
user       node    workdir /app    cmd ["node","server.js"]  entrypoint ["docker-entrypoint.sh"]
labels     org.opencontainers.image.revision = 2fdc6f241fc1742047b572ee2ef354cd811f9401
           org.opencontainers.image.title    = SCI Advisor frontend (Phase 3B)
build arg  NEXT_PUBLIC_API_URL=/api  (ตรงกับที่ docker-compose.prod.yml บรรทัด 95 ใช้ · ไม่มีค่าลับ)
log        /home/ubuntu/release-2fdc6f2/build-frontend.log
```

- ตรวจ hook ก่อน build: `frontend/package.json` มี script เพียง dev/build/start/lint/test
  **ไม่มี postinstall/preinstall/prepare** จึงไม่มีสคริปต์แฝงตอนติดตั้ง
- route artifact ของ `/crawl-review` ในอิมเมจ **9 รายการ**:
  `.next/server/app/crawl-review/page.js`, `page_client-reference-manifest.js`,
  `page.js.nft.json`, `crawl-review.html`, `crawl-review.meta`, `crawl-review.rsc`,
  `.next/static/chunks/app/crawl-review` …
- หน้าเดิมยัง build ครบ: `index`, `match`, `compare`, `api`, `_not-found`
- `/app/server.js` 6,377 ไบต์ · `.env` ในอิมเมจ 0 ไฟล์
- frontend rollback snapshot `6b85413d6a03…` ตรวจแล้วว่ายังชี้ ID เดิม ไม่ถูก rebuild/retag/ลบ

---

## 7. Backup และ rollback artifacts

### 7.1 ความสดของ backup — พิสูจน์ใหม่ในรอบนี้ ไม่อ้างรายงานเก่า

ตรวจกิจกรรมการเขียนเทียบเวลาสำรอง `2026-09-28T06:03:12Z`

| ตาราง | เขียนหลัง backup | เวลาล่าสุด |
|---|---|---|
| `chat_messages` (6,640 แถว) | **0** | 2026-09-28 01:59:53 +07 |
| `chat_answer_cache` (160 แถว) | **0** | 2026-09-24 08:31:23 +07 |
| `users` (สร้าง/อัปเดต) | **0 / 0** | 2026-09-18 02:32:49 +07 |
| `recommendations` | **0** | 2026-08-28 14:35:08 +07 |
| `mko.crawl_sources` updated | — | 2026-09-28 05:46:17 +07 |

ทุกค่าอยู่ก่อนเวลาสำรอง → **backup ยังครอบคลุมข้อมูลปัจจุบันครบ** จึงไม่สร้างชุดใหม่
(เงื่อนไขของ prompt ให้สร้างใหม่เมื่อพิสูจน์ความสดไม่ได้) และยืนยันซ้ำหลัง deploy ว่า
`chat_messages`/`chat_answer_cache` **เพิ่ม 0 แถว** ตลอดรอบนี้

### 7.2 ตรวจ backup ใหม่ ณ รอบนี้

| Artifact | ไบต์ | mode | sha256 คำนวณใหม่ | sidecar |
|---|---:|---|---|---|
| `prod_pre_phase3d_step2_20260928T060312Z.dump` | 53,843,793 | 600 | `7be0c9c9f20de109d0c74497440622a37e50a6fe88041559c64ae4b3dfd83144` | OK |
| `documents_20260928T060342Z.tar.gz` | 78,086,887 | 600 | `c7aa8ae42ab37419bc6d589162bbb3df0d4331a20c81b1110932b58f85585450` | OK |
| `documents_manifest_20260928T060342Z.tsv` | 3,238 | 600 | `1b12ad0309c6915b86ad137866d106bd0871c3b6230a62844d3170e3a57d35e6` | OK |

อ่าน archive ใหม่: `pg_restore --list` → **244 บรรทัด · 29 TABLE DATA · 0 error ·
Format CUSTOM · dbname course_advisor** · owner `ubuntu:ubuntu` · **ไม่ restore ทับ production**
และไม่สร้างฐานข้อมูลชั่วคราวในรอบนี้ (ผลการทดสอบ restore จริงที่บันทึกไว้เป็นของ Step 2
ไม่ได้นำมานับเป็นการทดสอบใหม่)

ตรวจเอกสาร production เทียบ manifest ทีละไฟล์ **ทั้งก่อนและหลัง deploy: 32/32 hash และขนาดตรง ·
ขาด 0 · เกิน 0 · `.pdf` 30 ไฟล์**

### 7.3 Rollback artifacts ที่รักษาไว้

```
backend   course-advisor-system-backend:rollback-pre-phase3d
          -> sha256:d1d1ba713412d34753a3969bee7f087508fae425f32bd17f1fe81d4a74e37145
          (ยังถือ tag :latest ด้วย ทั้งสอง tag ชี้อิมเมจเดียวกัน)
frontend  course-advisor-system-frontend:rollback-pre-phase3d
          -> sha256:6b85413d6a03e9f33a1466b761c4b9d41460fe2d8eb3d29e5498e8eaf552b400
worker    course-advisor-system-ingest-worker:617110e
          -> sha256:c80cc9b2114139cc38ef91c044a8517b2cf4f30611c663d55de3b99747ae4588
```

ตรวจซ้ำหลัง deploy: ทั้งสาม tag ยัง resolve ได้ ไม่ถูกทับ ไม่ถูกลบ ไม่ได้ prune อิมเมจใด
อิมเมจ frontend เดิมที่เคยรัน `sha256:ce65aad64305…` **ยังไม่มีใน image store** จึงไม่ใช่
rollback target ที่ใช้ได้ — ต้องใช้ snapshot ข้างบนเท่านั้น

**ข้อจำกัด provenance ของอิมเมจเก่า:** อิมเมจ backend เดิม `d1d1ba713412…` ไม่มี
`org.opencontainers.image.revision` (ค่าว่าง) จึงพิสูจน์ไม่ได้ว่า build จาก commit ไหน
ไม่ได้เขียน label ย้อนหลังและไม่ได้อ้างว่ารู้ frontend เดิมเช่นกัน

---

## 8. สถานะบริการ ก่อน → หลัง

| service | container ก่อน | container หลัง | image ก่อน | image หลัง | restarts | startedAt หลัง | เปลี่ยนโดยเจตนา |
|---|---|---|---|---|---|---|---|
| **backend** | `3aa33e3b46cf` | **`fda31caa20c4`** | `d1d1ba713412` | **`4a45677ec010`** | 0 → 0 | 2026-09-29T01:06:17.872Z | **ใช่ — recreate ตามแผน** |
| **frontend** | `58dd38b8338c` | **`2886c1bf9183`** | `ce65aad64305` | **`591ab6d935bb`** | 0 → 0 | 2026-09-29T01:07:21.190Z | **ใช่ — recreate ตามแผน** |
| caddy | `a2957d7b8fc3` | `a2957d7b8fc3` | `5f5c8640aae0` | เดิม | 0 | 2026-09-22T21:23:48.949Z | ไม่ |
| postgres | `e8c091a4fc60` | `e8c091a4fc60` | `ccc6e83d6e35` | เดิม | 0 | 2026-08-18T14:17:25.705Z | ไม่ |
| ollama | `e6ac0350c722` | `e6ac0350c722` | `9d30908e4114` | เดิม | 0 | 2026-08-18T14:17:25.705Z | ไม่ |
| webapi | `6a73308d4f39` | `6a73308d4f39` | `1163e36361d9` | เดิม | 0 (healthy) | 2026-09-22T21:21:35.624Z | ไม่ |

**RestartCount = 0 ของ backend/frontend หลัง cutover ไม่ได้หมายความว่า "ไม่มีการ restart"** —
คอนเทนเนอร์ถูกแทนที่ด้วยตัวใหม่โดยเจตนา ตัวนับจึงเริ่มจากศูนย์ หลักฐานที่ใช้จริงคือ
**container ID และ StartedAt ที่เปลี่ยน** ตามตารางข้างบน

บริการที่ไม่เกี่ยวข้องทั้งสี่ยืนยันว่า **container ID และ StartedAt ไม่เปลี่ยนเลย**
คำสั่งที่ใช้เป็น service-targeted พร้อม `--no-deps --no-build` จึงไม่มี stack-wide down/up
`backend` และ `frontend` ไม่มี Docker healthcheck ตั้งแต่เดิม (ไม่ได้เพิ่มในรอบนี้)

---

## 9. API / OpenAPI / UI — แยก public domain กับ direct route

### 9.1 Backend runtime

| ข้อตรวจ | ก่อน cutover | หลัง cutover |
|---|---|---|
| จำนวน path ใน OpenAPI | 21 | **27** |
| path ที่มีคำว่า `crawl` | ไม่มี | **6 path** พร้อม method ตรง source |
| `/health` | 200 `{"status":"ok"}` | 200 `{"status":"ok"}` |
| `/courses` | 200 | 200 |
| `/crawl-review/pending` (ไม่มี token) | **404** | **401** `{"detail":"missing bearer token"}` |
| `/crawl-review/{uuid}` (ไม่มี token) | 404 | **401** |
| `/crawl-review/{uuid}/pdf` (ไม่มี token) | 404 | **401** |
| `/users/me` (ไม่มี token) | 401 | 401 |

401 แทน 404 คือหลักฐานว่า route มีจริงและบังคับ auth · ไม่มีการเปิดเผยเนื้อคิวหรือ PDF

log ตอนเริ่มบริการ (redact แล้ว): `embedding dim = 1024 ตรงกับ bge-m3` ·
`เปิด warmup ทุก 20 นาที` · `Application startup complete.`

### 9.2 Public domain (HTTPS) — API ผ่าน `/api/*`

| endpoint | ก่อน | หลัง |
|---|---|---|
| `https://…/api/health` | 200 | 200 |
| `https://…/api/courses` | — | 200 |
| `https://…/api/crawl-review/pending` | **404** | **401** `{"detail":"missing bearer token"}` |
| `https://…/api/documents/{id}/pdf` | — | **200** `application/pdf` 5,519,475 ไบต์ ขึ้นต้น `%PDF-` |

Caddy มี `handle /api/*` ที่ทำ `uri strip_prefix /api` แล้วส่งไป `backend:8000` อยู่ก่อนแล้ว
**API ของ crawl-review จึงใช้งานผ่าน HTTPS ได้โดยไม่ต้องแก้ Caddy** ตามเกณฑ์ของ prompt
(401 = ผ่าน, 404 = ล้มเหลว)

### 9.3 Next.js page — ตรวจผ่าน loopback ของเซิร์ฟเวอร์ ไม่ส่ง token ผ่าน HTTP

Caddy มี `:80 { reverse_proxy frontend:3000 }` เป็นเส้นทางเดียวที่ถึงคอนเทนเนอร์ frontend

| path | ก่อน | หลัง | ไบต์ |
|---|---|---|---|
| `/` | 200 | 200 | 14,530 |
| `/match` | 200 | 200 | 18,572 |
| `/compare` | 200 | 200 | 7,922 |
| **`/crawl-review`** | **404** | **200** | 7,356 |
| path ที่ไม่มีจริง | — | **404** | 6,060 |

**หลักฐานว่าเป็น route จริงไม่ใช่ fallback** (ไม่ถือ HTTP 200 เป็นข้อพิสูจน์)

- HTML อ้าง chunk เฉพาะ route: `/_next/static/chunks/app/crawl-review/page-a6096f0244f418a5.js`
- sha256 ของหน้าต่างจากหน้าแรก (`71b6a743…` ≠ `2e42d468…`)
- path ที่ไม่มีจริงตอบ 404 คนละขนาด จึงไม่ใช่ catch-all
- ดึง chunk มาตรวจ (22,577 ไบต์ HTTP 200) พบข้อความ UI ของ Phase 3B ครบ:
  `คิว`, `อนุมัติ`, `ไม่เกี่ยวข้อง`, `ถอนการตัดสินใจ`, `เข้าสู่ระบบ`, `รหัสผ่าน`
  และอ้าง endpoint `/crawl-review`

HTML ที่ server ส่งมาไม่มีข้อความไทยเพราะหน้านี้เป็น client component — ตรวจ effect ก่อนเปิด
แล้วพบว่า `useEffect` เรียก `load(token)` ซึ่งไม่ยิงอะไรถ้าไม่มี token และ approve/ignore/undo
อยู่หลังปุ่มพร้อมกล่องยืนยัน **การเปิดหน้าแบบ anonymous จึงไม่ยิง API ใดเลย**

### 9.4 Public domain — หน้าเว็บ (คนละ deployment surface)

| path | ก่อน | หลัง | ความหมาย |
|---|---|---|---|
| `https://…/` `/match` `/compare` | 200 | 200 | SPA ของทีมออกแบบที่ `/srv/web` |
| `https://…/crawl-review` | **200** | **200** | **fallback ของ `try_files … /index.html` ไม่ใช่หน้า Next.js** |

โดเมนยังเสิร์ฟ SPA เดิม **จึงไม่อ้างว่าโดเมนได้ Phase 3B แล้ว** การเปิดหน้านี้บนโดเมน
ยังเป็น separate decision

---

## 10. Staging / documents — path, env, RO และ fail-closed

| รายการ | ค่า |
|---|---|
| `CRAWL_STAGING_DIR` ของ backend | `/srv/staging` (ก่อน deploy: ไม่ได้ตั้ง) |
| `DOCUMENTS_DIR` ของ backend | `/srv/documents` |
| mount staging | `/home/ubuntu/course-advisor-system/staging/crawl` → `/srv/staging` · **RW=false** |
| mount documents | `/home/ubuntu/course-advisor-system/documents` → `/srv/documents` · **RW=false** |
| `staging/crawl` | **0 รายการ** ทั้งก่อนและหลัง — ไม่ได้สร้างไฟล์/PDF/probe/candidate ใด |
| `documents` | 32/32 ตรง manifest · `.pdf` 30 ไฟล์ ทั้งก่อนและหลัง |

ตรวจ resolved config ก่อน recreate (ดึงเฉพาะ field ที่ต้องดู ไม่พิมพ์ค่าลับ):
service ใน resolved config = `backend, caddy, frontend, ollama, postgres, webapi` ·
**ไม่มี `ingest-worker`** · `backend.image = course-advisor-system-backend:2fdc6f2` ·
mount สองรายการ `read_only=True` ทั้งคู่ · env ของ backend มี 14 คีย์ (แสดงเฉพาะสองคีย์ที่ต้องตรวจ)

### Fail-closed ของ staging — ทดสอบแบบ isolated 9/9 PASS

production ไม่มีไฟล์ใน staging และ auth กั้นอยู่ จึงยิงผ่าน API ไม่ถึงด่านลึก
ทดสอบด้วย **อิมเมจ backend ใหม่ตัวเดียวกัน** ในคอนเทนเนอร์ทิ้ง (`--network none`, ไม่มี DB,
โฟลเดอร์ชั่วคราว) เรียก `StagingStore.open()` ตรง ๆ

| กรณี | ต้องได้ | ผล |
|---|---|---|
| ไฟล์ถูกต้อง + sha ตรง | คืนไฟล์ | PASS |
| ไฟล์ไม่มีอยู่ | None | PASS |
| path หลุดออกนอก root | None | PASS |
| path traversal ด้วย `..` | None | PASS |
| sha256 ไม่ตรง | None | PASS |
| ไฟล์ไม่ใช่ PDF (sha ตรง) | None | PASS |
| `staging_path` เป็น None | None | PASS |
| `sha256` เป็น None | None | PASS |
| `CRAWL_STAGING_DIR` ว่าง = ปิดฟีเจอร์ | None | PASS |

**ไม่ได้ทดสอบด่านนี้บน production** จึงระบุว่า production authenticated 404 = **NOT TESTED**
(ต้องมี admin ก่อน) · การได้ 401 อย่างเดียวพิสูจน์แค่ auth ไม่ได้พิสูจน์การกันไฟล์หลุดโฟลเดอร์

---

## 11. DB baseline ก่อน / หลัง และสถานะ auth แบบ aggregate

| รายการ | ก่อน deploy | หลัง deploy | ผล |
|---|---|---|---|
| `courses` | 24 | **24** | คงเดิม |
| `course_documents` | 31 | **31** | คงเดิม |
| `course_chunks` | 9039 | **9039** | คงเดิม |
| `embedding_dim` | 1024 | **1024** | คงเดิม |
| `mko.crawl_sources` | 12 | **12** | คงเดิม |
| status `unchanged` | 12 | 12 | คงเดิม |
| `needs_review` | 6 | 6 | คงเดิม |
| `staging_path IS NOT NULL` | 0 | 0 | คงเดิม |
| `mko.crawl_decisions` | ตารางไม่มี | มีตาราง · **0 แถว** | ตามแผน |
| `mko.v_crawl_queue` | view ไม่มี | มี view · 6 แถวในคิว | ตามแผน |
| `schema_migrations` | 001–003 | 001–003 + **004** | ตามแผน |
| `chat_messages` | 6640 | 6640 · **เพิ่มหลัง deploy 0** | คงเดิม |
| `chat_answer_cache` | 160 | 160 · **เพิ่มหลัง deploy 0** | คงเดิม |
| `users` / active | 197 / 197 | 197 / 197 | คงเดิม |
| `is_admin = true` | 0 | **0** | คงเดิม |

คิวมี 6 แถวเพราะเป็นแหล่งที่ `needs_review = true` และยังไม่มีการตัดสินใจใด — ถูกต้องตามนิยามของ view

---

## 12. Admin (CP7) — HUMAN ACTION REQUIRED

prompt รอบนี้ **ไม่ได้ระบุ identity ที่อนุมัติ** จึงคง **HUMAN ACTION REQUIRED**

ไม่ได้เลือกบัญชี ไม่ได้ promote ไม่ได้สร้างบัญชี ไม่ได้ออก token ไม่ได้ลดความเข้มของ guard
และไม่ได้เปิดเผย PII — รายงานเฉพาะ aggregate: `users = 197`, `active = 197`,
`is_admin = true` → **0**

สิ่งที่ทดสอบได้โดยไม่มี admin: anonymous ถูกปฏิเสธด้วย 401 บนทั้งสาม GET ของ `/crawl-review`
(ทั้งใน container และผ่าน HTTPS)

สิ่งที่ **BLOCKED / NOT TESTED** เพราะไม่มี approved identity:

- non-admin 403 บน `/crawl-review`
- authenticated admin UI (คิว, การเปิด PDF, ปุ่มอนุมัติ/ไม่สนใจ/ถอน)
- production authenticated 404 ของ staging PDF endpoint

ทั้งหมดนี้ไม่รายงานเป็น PASS

---

## 13. Smoke / regression และหลักฐานว่าไม่มี ingestion / embedding ของเนื้อหา

ตรวจ implementation ก่อนเรียกทุก endpoint

| # | เป้าหมาย | วิธี | คาด | จริง | สถานะ |
|---|---|---|---|---|---|
| 1 | backend health | `GET /health` ในคอนเทนเนอร์ | 200 | 200 `{"status":"ok"}` | **PASS** |
| 2 | frontend ตอบสนอง | `GET :80/` loopback | 200 | 200 · 14,530 ไบต์ | **PASS** |
| 3 | หน้าเดิม `/match` `/compare` | loopback | 200 | 200 · 18,572 / 7,922 ไบต์ | **PASS** |
| 4 | course อ่านได้ | `GET /courses` (ตรวจแล้วว่าอ่านอย่างเดียว) | 200 | 200 | **PASS** |
| 5 | เอกสารเดิมเปิดได้ | `GET /api/documents/{id}/pdf` (ตรวจแล้ว: SELECT + อ่านไฟล์) | 200 PDF | 200 `application/pdf` 5,519,475 ไบต์ `%PDF-` | **PASS** |
| 6 | OpenAPI ก่อน cutover (จากอิมเมจ) | import ไม่รัน lifespan | 27 path · 6 crawl-review | ตรง | **PASS** |
| 7 | OpenAPI runtime | `GET /openapi.json` | 27 path · 6 crawl-review | ตรง | **PASS** |
| 8 | บังคับ auth · ไม่รั่วข้อมูล | 3 GET ของ crawl-review ไม่มี token | 401 | 401 `missing bearer token` ทั้งสาม | **PASS** |
| 9 | API ผ่าน HTTPS | `GET /api/crawl-review/pending` | 401 (ไม่ใช่ 404) | 401 | **PASS** |
| 10 | Next.js route จริง | chunk + 404 control + hash | เป็น route จริง | ยืนยันแล้ว (ข้อ 9.3) | **PASS** |
| 11 | staging fail-closed | isolated 9 กรณี | ปฏิเสธทุกกรณีที่ควรปฏิเสธ | 9/9 | **PASS (isolated)** |
| 12 | mount RO ทั้งสอง | `docker inspect` | RW=false | RW=false ทั้งคู่ | **PASS** |
| 13 | staging ว่าง · documents ตรง manifest | `ls` + `sha256sum -c` | 0 รายการ · 32/32 | ตรง | **PASS** |
| 14 | DB invariants | read-only transaction | 24/31/9039/12 · decisions 0 | ตรง | **PASS** |
| 15 | ไม่มี worker/crawler | `docker ps -a` + `pgrep` | 0 · 0 | 0 · 0 | **PASS** |
| 16 | บริการอื่นไม่เปลี่ยน | container ID + StartedAt | ไม่เปลี่ยน | ไม่เปลี่ยน | **PASS** |
| 17 | **chat / RAG / recommend / search / match / compare แบบ live** | — | — | — | **NOT TESTED** |
| 18 | non-admin 403 · admin UI · production staging 404 | — | — | — | **BLOCKED** (ไม่มี approved admin) |

### ทำไมข้อ 17 เป็น NOT TESTED

ตรวจ source ก่อนเรียกแล้วพบว่าเส้นทางเหล่านี้ **สร้าง embedding และเขียนประวัติ**

```
backend/app/services/chat.py:283  vector = connector.embed(scopes[0].search_text)
backend/app/services/chat.py:301  search_similar_chunks(db, connector.embed(expand_query(question)), ...)
backend/app/services/chat.py:304  connector.embed(scope.search_text)
backend/app/services/chat.py:146  db.add(session)
backend/app/services/chat.py:150  db.commit()
backend/app/services/chat.py:1029 db.add(ChatMessage(... role="user" ...))
backend/app/services/chat.py:1030 db.add(ChatMessage(... role="assistant" ...))
backend/app/services/chat.py:1031 db.commit()
```

จึง **ไม่เรียกเลย** ตามข้อกำหนด no-embedding และห้ามสร้าง test data
ไม่ได้แต่ง PASS และไม่ได้เพิ่มฟีเจอร์ใดเพื่อเลี่ยงข้อกำหนด
หลักฐานเชิงลบ: `chat_messages` และ `chat_answer_cache` **เพิ่ม 0 แถว** ตลอดรอบ
และ log ของ backend นับคำขอ `/chat` ได้ **0 ครั้ง**

### กิจกรรม embedding ที่เกิดขึ้นจริง — รายงานตามตรง

```
จำนวนครั้งที่ backend เรียก ollama /api/embeddings ตั้งแต่ cutover : 1
จำนวนครั้งที่เรียก /api/generate หรือ /api/chat ของ ollama        : 0
คำขอ /chat ที่เข้าถึง backend                                    : 0
```

ครั้งเดียวนั้นมาจาก `_keep_models_warm()` ใน `backend/app/main.py:68` ซึ่งเรียก
`connector.embed("warmup")` — เป็น **พฤติกรรมเดิมของบริการ** ที่ทำอยู่แล้วทุก 20 นาที
ตั้งแต่ก่อนรอบนี้ การ recreate จึงเริ่ม task นี้ใหม่อย่างเลี่ยงไม่ได้ ถ้าไม่ให้เกิดต้องตั้ง
`WARMUP_INTERVAL_MINUTES=0` ซึ่งเป็นการเปลี่ยน config ของ production ที่ **ไม่ได้รับอนุมัติ**
จึงคงพฤติกรรมเดิมไว้

สิ่งที่การ embed ครั้งนี้ **ไม่ได้ทำ**: ไม่เขียนแถวใดลงฐานข้อมูล ไม่แตะ `course_chunks`
ไม่เกี่ยวกับเนื้อหาเอกสาร ไม่ใช่ ingestion (embed สตริง `"warmup"` แล้วทิ้ง)
ยืนยันด้วย `course_chunks = 9039` เท่าเดิม

**จึงไม่อ้างว่า "ไม่มี embedding เกิดขึ้นเลย"** — มี 1 ครั้งตามที่อธิบาย

---

## 14. Caddy และโดเมน

**ไม่ได้แก้ ไม่ได้ reload ไม่ได้ recreate ไม่ได้ restart Caddy** และไม่ได้เปลี่ยน DNS,
พอร์ตสาธารณะ หรือ routing

```
container   a2957d7b8fc3      (ไม่เปลี่ยน)
startedAt   2026-09-22T21:23:48.949053581Z   (ไม่เปลี่ยน)
restarts    0
Caddyfile   sha256 da2e26fd948d2a7143c85d1ee7dde204c774569d6f2e49130ea9bd059aec0f0d
            (ค่าเดียวกันทั้งก่อนและหลัง deploy) · mtime 2026-09-22 21:23:34
พอร์ต        80:80 และ 443:443 เท่าเดิม ไม่ได้เปิดพอร์ตเพิ่ม
```

**ข้อจำกัดที่ยังอยู่:** โดเมน HTTPS เสิร์ฟ SPA จาก `/srv/web` และมี `try_files … /index.html`
จึงตอบ 200 ให้ `/crawl-review` เป็น fallback ทั้งก่อนและหลัง deploy
**ไม่ใช่หลักฐานของหน้า Next.js** การเปิดหน้านี้บนโดเมนเป็น **separate decision / blocker**
ที่ต้องให้คนตัดสิน ไม่ได้แก้ Caddy เพื่อให้ smoke test ผ่าน

หน้า Next.js เข้าถึงได้ทาง `:80 → frontend:3000` ซึ่งเป็น **HTTP ไม่เข้ารหัส** การทดสอบในรอบนี้
ทำผ่าน loopback ของเซิร์ฟเวอร์เท่านั้นและ **ไม่ส่ง token หรือ credential ใดผ่านเส้นทางนี้**

---

## 15. ไฟล์ที่เปลี่ยน / สร้าง / commit และ git status

### 15.1 commit

**ไม่ได้สร้าง commit ใหม่ในรอบ resume นี้** (`git rev-list 2fdc6f24..HEAD` = 0 รายการ)
commit เดียวที่เกี่ยวคือ `2fdc6f241fc1742047b572ee2ef354cd811f9401` ซึ่งสร้างในรอบก่อนและ
push ในรอบนี้ตามที่ได้รับอนุมัติ

### 15.2 ไฟล์ที่สร้างใหม่ในเครื่อง (ไม่ commit)

`docs/AUTOMATED_INGESTION_PHASE3D_STEP3_RESUME_REPORT.md` (รายงานฉบับนี้)
และ artifact ชั่วคราวในสแครตช์แพดของ session (archive + manifest)
**ไม่มีรายงานหรือ operational artifact อยู่ใน commit ที่อนุมัติ**

### 15.3 git status

```
branch            mko-phase2
HEAD              2fdc6f241fc1742047b572ee2ef354cd811f9401
origin/mko-phase2 2fdc6f241fc1742047b572ee2ef354cd811f9401   = DEPLOY_REV
origin/main       b78b3f8bf895685874d9a52c66b45569072f0514   ไม่เปลี่ยน
staged                0 ไฟล์
tracked modified      0 ไฟล์
untracked นอก docs/    0 ไฟล์
untracked ใน docs/     42 ไฟล์ (รายงานเก่า + ฉบับนี้)
tag local / remote    0 / 0
```

---

## 16. Worker (CP9) · Candidate (CP10) · document_store (CP11)

### Worker คง PREPARED — ไม่ถูกรัน

**ไม่ได้ start/run/rebuild worker** ไม่ได้เปิด profile `worker` ไม่ได้ `compose run`
ไม่ได้เรียก `pipeline.crawl.approve` ไม่ว่ารูปแบบใดรวมทั้ง `--help`
และ `docker-compose.worker.yml` **ไม่ได้อยู่ในคำสั่ง compose ใดของรอบนี้**
(ยืนยันจาก resolved config ว่าไม่มี service `ingest-worker`)
`pipeline/` และ `docker-compose.worker.yml` **ไม่ได้อยู่ใน deployment package** ด้วย

ตรวจ metadata อย่างเดียว: `course-advisor-system-ingest-worker:617110e` →
`sha256:c80cc9b2114139cc38ef91c044a8517b2cf4f30611c663d55de3b99747ae4588`
ยังอยู่ครบ ไม่ถูกแตะ · สัญญา `bge-m3 / 1024` · uid/gid `1001:1001` ·
`restart: "no"` · `profiles: ["worker"]` · staging `:ro` documents `:rw` ·
logical paths `/srv/staging` และ `/srv/documents`

**Provenance ตามจริง:** อิมเมจ worker build จาก code ของ `617110e9…` ตอนที่
`pipeline/Dockerfile` **ยัง untracked** ในรอบนี้ตรวจแล้วว่า blob ที่ commit มี sha256
`ca48cd2da16c7fef…` **ตรงกับไฟล์ build context บนเซิร์ฟเวอร์ทุกไบต์** จึงยืนยันได้ว่า
build input ตรงกับ committed source แต่ **ไม่อ้างว่า reproducible ทั้งหมด** เพราะ base image
และ pip resolution เป็น floating · label ของอิมเมจยังชี้ `617110e9…` ตามความจริง
**ไม่ได้ rewrite label หรือ retag ให้ดูเหมือน build จาก commit ใหม่**

### Candidate คง DEFERRED

`mko.crawl_sources` = 12 แถว `unchanged` ทั้งหมด · `staging_path` ว่างทั้ง 12 ·
`staging/crawl` ว่าง · `mko.crawl_decisions` = 0 แถว

**ไม่ได้สร้าง/แก้ `crawl_sources`, status, hash หรือ `staging_path` · ไม่ได้เอา PDF เก่า
มาปลอมเป็นใหม่ · ไม่ได้ force ingestion · ไม่ได้รัน crawler · ไม่ได้สร้าง decision ทดสอบ**
และไม่พบ candidate จากภายนอกเข้ามาระหว่างงาน

### document_store (CP11) — NOT APPLICABLE

รอบนี้ไม่มี ingestion จึง **ไม่มีเหตุให้ refresh `document_store`**
การ recreate backend ที่เกิดขึ้นเป็นส่วนของ cutover ตามแผน ไม่ใช่การ restart เพื่อ refresh index
(ข้อจำกัดของ `document_store.py` ที่สร้าง index ครั้งเดียวต่อ process ยังคงอยู่
และเป็น runbook ของรอบที่มี ingestion จริง)

---

## 17. Blocker ที่เหลือ

### 17.1 Deployment — **ไม่มี blocker ที่เหลือ**

ทุก gate ของ Step 3 ผ่าน: push · packaging · migration 004 · build backend · build frontend ·
backend cutover + staging mount · frontend cutover · smoke/regression
ไม่มีชั้นใด FAIL และไม่มีการ rollback

### 17.2 Future controlled one-job ingestion

| # | เรื่อง | ผู้รับผิดชอบขั้นถัดไป |
|---|---|---|
| 1 | **ไม่มีบัญชี admin** | **เจ้าของโปรเจกต์** ต้องระบุบัญชีและอนุมัติแยกเป็นคำสั่งเฉพาะ |
| 2 | **ไม่มี legitimate candidate** | รอต้นทาง `sci.pnru.ac.th` มีไฟล์ใหม่หรือเปลี่ยนจริง พร้อม staged PDF/hash ที่ตรวจได้ |
| 3 | admin UI และ authenticated flow ยังไม่ถูกทดสอบ | ทำได้หลังข้อ 1 |
| 4 | production staging PDF fail-closed ยังไม่ถูกทดสอบบนของจริง | ทำได้หลังข้อ 1 (ผลแบบ isolated ผ่าน 9/9 แล้ว) |
| 5 | ต้อง restart backend หลัง ingest เพื่อให้ดัชนีเอกสารเห็นไฟล์ใหม่ | ใส่ใน runbook ของรอบที่มี ingestion |
| 6 | หน้า `/crawl-review` บนโดเมน HTTPS | **separate decision** — ปัจจุบันเข้าได้ทาง `:80` เท่านั้น |

---

## 18. GO / NO-GO สำหรับ future controlled one-job ingestion

### **NO-GO**

เป็น readiness assessment **ไม่ใช่การอนุญาตให้เริ่ม** และไม่มีการตั้งเวลารอบ ingestion ใด

เหตุผล

1. **ไม่มี approved admin** — ไม่มีใครเปิดคิว ดู PDF หรืออนุมัติได้
2. **ไม่มี legitimate candidate** — ไม่มีงานจริง และห้ามปลอม
3. การทดสอบที่ต้องใช้ตัวตนที่อนุมัติยังเป็น BLOCKED ทั้งหมด (ข้อ 12)

สิ่งที่ **พร้อมแล้ว** และไม่ใช่เหตุปิดกั้นอีกต่อไป: schema 004 · backend Phase 3A ·
frontend Phase 3B · staging mount read-only · worker image และ config · backup และ rollback ครบทุกชั้น

---

## 19. Rollback instructions ที่รันได้จริง (ไม่มี placeholder)

ใช้ค่าจริงทั้งหมด ตรวจแล้วบนเซิร์ฟเวอร์ ไม่มีค่าลับในคำสั่ง

### 19.1 Frontend (ย้อนก่อน เพราะเป็นชั้นบนสุด)

```bash
sudo docker compose \
  --project-name course-advisor-system \
  --project-directory /home/ubuntu/course-advisor-system \
  -f /home/ubuntu/course-advisor-system/docker-compose.prod.yml \
  -f /home/ubuntu/course-advisor-system/docker-compose.staging.yml \
  -f /home/ubuntu/release-2fdc6f2/compose.pin-backend-2fdc6f2.yml \
  -f /home/ubuntu/release-2fdc6f2/compose.rollback-frontend.yml \
  up -d --no-deps --no-build --force-recreate frontend

# ตรวจ
sudo docker inspect course-advisor-system-frontend-1 --format '{{.Image}} {{.State.Status}}'
#   ต้องได้ sha256:6b85413d6a03e9f33a1466b761c4b9d41460fe2d8eb3d29e5498e8eaf552b400 running
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1/          # ต้องได้ 200
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1/crawl-review  # จะกลับเป็น 404
```

อิมเมจเดิมที่เคยรัน `sha256:ce65aad64305…` **ไม่มีใน image store** ใช้เป็น target ไม่ได้

### 19.2 Backend (คืน image และคืน mount topology เดิม)

```bash
# ห้ามใส่ docker-compose.staging.yml — mount staging และ CRAWL_STAGING_DIR อยู่ในไฟล์นั้นไฟล์เดียว
sudo docker compose \
  --project-name course-advisor-system \
  --project-directory /home/ubuntu/course-advisor-system \
  -f /home/ubuntu/course-advisor-system/docker-compose.prod.yml \
  -f /home/ubuntu/release-2fdc6f2/compose.rollback-backend.yml \
  up -d --no-deps --no-build --force-recreate backend

# ตรวจว่า topology กลับเป็นก่อน deploy จริง
sudo docker inspect course-advisor-system-backend-1 \
  --format '{{.Image}}{{range .Mounts}} | {{.Source}}->{{.Destination}} RW={{.RW}}{{end}}'
#   ต้องได้ sha256:d1d1ba713412d34753a3969bee7f087508fae425f32bd17f1fe81d4a74e37145
#   และมี mount เดียวคือ .../documents -> /srv/documents RW=false (ไม่มี /srv/staging)
sudo docker exec course-advisor-system-backend-1 sh -c 'printenv CRAWL_STAGING_DIR || echo "ไม่ได้ตั้ง (ถูกต้อง)"'
sudo docker exec course-advisor-system-backend-1 python -c "import json,urllib.request;print(len(json.load(urllib.request.urlopen('http://127.0.0.1:8000/openapi.json'))['paths']))"
#   ต้องได้ 21
```

ตรวจแล้วด้วย `docker compose config` ว่าชุดไฟล์ rollback นี้ให้ backend ที่
**ไม่มี `CRAWL_STAGING_DIR` และมี mount เดียวเป็น read-only** ตรงกับ topology ก่อน deploy

### 19.3 ถอนไฟล์ config ที่ติดตั้งลง production

```bash
rm /home/ubuntu/course-advisor-system/docker-compose.staging.yml
```

ทำเฉพาะเมื่อ rollback backend แล้ว ไม่งั้น backend ที่ใช้ mount นี้จะหา config ไม่ครบ

### 19.4 Migration 004 (ทำเป็นชั้นสุดท้ายและเฉพาะเมื่อจำเป็นด้านข้อมูลจริง)

**service/config ที่ล้มเหลวไม่ใช่เหตุให้ย้อน migration ที่สำเร็จ**

```bash
# ด่านกันข้อมูลหาย: ต้องเป็น 0 ก่อน ถ้าไม่ใช่ 0 ให้หยุดให้คนตรวจ ห้าม DROP
sudo docker exec course-advisor-system-postgres-1 psql -U postgres -d course_advisor -At \
  -c "SELECT count(*) FROM mko.crawl_decisions;"

# สคริปต์มีด่านนับแถวในตัวและถือ ACCESS EXCLUSIVE lock จนจบธุรกรรม ถ้ามีแถวจะ RAISE EXCEPTION เอง
sudo docker cp /home/ubuntu/release-2fdc6f2/rollback_004.sql \
  course-advisor-system-postgres-1:/tmp/rollback_004.sql
sudo docker exec course-advisor-system-postgres-1 \
  psql -U postgres -d course_advisor -v ON_ERROR_STOP=1 -f /tmp/rollback_004.sql

# ตรวจว่าคืนสภาพตรง before state
sudo docker exec course-advisor-system-postgres-1 psql -U postgres -d course_advisor -At -c \
 "SELECT array_to_string(relacl,' | ') FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
   WHERE n.nspname='mko' AND c.relname='crawl_sources';"
#   ต้องได้ postgres=arwdDxt/postgres | advisor_ingest=arw/postgres
sudo docker exec course-advisor-system-postgres-1 psql -U postgres -d course_advisor -At -c \
 "SELECT string_agg(version,',' ORDER BY version) FROM mko.schema_migrations;"
#   ต้องได้ 001_mko_structured,002_mko_review_publish,003_crawl_sources
```

**ไม่ใช้ whole-DB restore เป็นค่าเริ่มต้น** การ restore จาก
`/home/ubuntu/backups/prod_pre_phase3d_step2_20260928T060312Z.dump`
(sha256 `7be0c9c9f20de109d0c74497440622a37e50a6fe88041559c64ae4b3dfd83144`)
สงวนไว้สำหรับกรณีข้อมูลเสียหายจริงเท่านั้น และต้อง `sha256sum -c` ก่อนทุกครั้ง

### 19.5 ถอน artifact ที่ไม่กระทบบริการ (ไม่แนะนำให้ทำจนจบ Phase 3D)

```bash
# อิมเมจใหม่ (ทำได้เฉพาะเมื่อไม่มีคอนเทนเนอร์ใช้อยู่แล้ว)
sudo docker image rm course-advisor-system-backend:2fdc6f2
sudo docker image rm course-advisor-system-frontend:2fdc6f2
# release directory
rm -rf /home/ubuntu/release-2fdc6f2
```

**ห้ามลบ** `course-advisor-system-backend:rollback-pre-phase3d`,
`course-advisor-system-frontend:rollback-pre-phase3d`,
`course-advisor-system-ingest-worker:617110e`, tag `rollback-<sha>` เดิมทั้งหมด
และไฟล์ทั้งหมดใน `/home/ubuntu/backups/` · **ไม่ prune อิมเมจ**
และ **ไม่ลบประวัติบน remote** เป็นวิธี rollback ของการ deploy

---

## สรุปสั้น

- **push ผ่าน** `617110e..2fdc6f2` → `DEPLOY_REV = 2fdc6f241fc1742047b572ee2ef354cd811f9401`
  · main ไม่เปลี่ยน · ไม่ push tag · ไม่มี commit ใหม่ในรอบนี้
- **package** 100 ไฟล์จาก committed bytes เท่านั้น · hash ตรง 100/100 หลังโอนและแตกไฟล์ ·
  ไม่มี `.env`/`pipeline`/worker overlay/`.git`
- **migration 004 apply สำเร็จ** ในธุรกรรมของไฟล์เอง · 15 คอลัมน์ 7 CHECK 4 index 1 view
  0 แถว · สิทธิ์ตรงทุกข้อรวมทั้งที่ต้อง "ไม่ได้" · invariants 24/31/9039/12 ไม่ขยับ ·
  rollback script สร้างจาก catalog จริงพร้อมด่านกันข้อมูลหาย
- **backend + frontend cutover สำเร็จ** ด้วยอิมเมจ immutable ที่มี OCI revision label ตรง
  DEPLOY_REV · mount staging และ documents **read-only ทั้งคู่** · บริการอื่นสี่ตัวไม่ถูกแตะเลย
- **`/crawl-review` ทำงานจริง**: API ตอบ 401 (ไม่ใช่ 404) ทั้งใน container และผ่าน HTTPS ·
  หน้า Next.js เป็น route จริงพิสูจน์ด้วย chunk เฉพาะ route ไม่ใช่ 200 ลอย ๆ
- **ไม่มี ingestion · ไม่มีการสร้าง embedding ของเนื้อหา** — embedding เกิด **1 ครั้ง**
  จาก warmup เดิมของบริการ (สตริง `"warmup"` ไม่เขียนฐานข้อมูล) รายงานไว้ตรง ๆ ไม่กลบ
- **chat/RAG live = NOT TESTED** เพราะเส้นทางนั้นสร้าง embedding และเขียน `ChatMessage`
- **admin = HUMAN ACTION REQUIRED** · **candidate = DEFERRED** · **worker = PREPARED ไม่ถูกรัน**
- **GO/NO-GO สำหรับ one-job ingestion: NO-GO**

**STOP**
