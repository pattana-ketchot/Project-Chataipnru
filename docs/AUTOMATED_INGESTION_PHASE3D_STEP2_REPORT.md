# Phase 3D Step 2 — แก้ Blocker ก่อน Deploy อย่างปลอดภัย

รายงานผลการดำเนินการตาม `AUTOMATED_INGESTION_PHASE3D_STEP2_AGENT_PROMPT.md`
ยึด `docs/AUTOMATED_INGESTION_PHASE3D_PREDEPLOY_AUDIT.md` เป็น baseline

| | |
|---|---|
| วันที่ดำเนินการ | 2026-09-28 (เวลาไทย 13:02–14:0x) |
| Repository | `D:/workspace/course-advisor-system-mko2` |
| Branch | `mko-phase2` |
| HEAD | `617110e975dccc94b5e67f77990e34a071ccf9a0` (ตรงกับที่กำหนด) |
| Production | `ubuntu@161.118.237.37` · `https://stpnru-advisor.duckdns.org` |
| ผลรวม | **RESOLVED 4 ข้อ · PREPARED 2 ข้อ · DEFERRED 1 ข้อ · HUMAN ACTION REQUIRED 1 ข้อ** |
| คำตัดสิน | **NO-GO สำหรับ end-to-end ingestion · CONDITIONAL GO สำหรับขั้น deploy ที่ไม่ต้องมีงานจริง** |

รอบนี้ **ไม่มี** production ingestion, ไม่มีการสร้าง embedding, ไม่ได้รัน worker,
ไม่ได้ apply migration 004 บน production, ไม่ได้ recreate/restart บริการใด,
ไม่ได้แก้ Caddy, ไม่ได้แก้ `.env`, ไม่ได้แก้ schema ของ production,
ไม่ได้แก้ `users`/`mko.crawl_sources`/knowledge tables, ไม่ได้ commit และไม่ได้ push

---

## 1. Repository / Production baseline ที่ re-verify แล้ว

### 1.1 Repository

| รายการ | ค่าที่ตรวจได้ | ตรงกับที่คาด |
|---|---|---|
| branch | `mko-phase2` | ใช่ |
| HEAD | `617110e975dccc94b5e67f77990e34a071ccf9a0` | ใช่ |
| `origin/mko-phase2` | ชี้ commit เดียวกัน | ใช่ |
| tracked ที่แก้ไว้ | 0 ไฟล์ | ใช่ |
| staged | 0 ไฟล์ | ใช่ |
| untracked นอก `docs/` ตอนเริ่มรอบ | 0 ไฟล์ | ใช่ |

### 1.2 Production database — อ่านอย่างเดียว (`BEGIN TRANSACTION READ ONLY` + `statement_timeout = 15s`)

วัดเมื่อ `2026-09-28 13:27:20` (Asia/Bangkok)

| รายการ | Audit (baseline) | Step 2 | drift |
|---|---|---|---|
| `courses` | 24 | 24 | ไม่มี |
| `course_documents` | 31 | 31 | ไม่มี |
| `course_chunks` | 9039 | 9039 | ไม่มี |
| `course_chunks.embedding` มิติ | 1024 | 1024 | ไม่มี |
| `users` ทั้งหมด | 197 | 197 | ไม่มี |
| `users` ที่ active | 197 | 197 | ไม่มี |
| admin ทั้งหมด | 0 | 0 | ไม่มี |
| admin ที่ active | 0 | 0 | ไม่มี |
| `mko.crawl_sources` | 12 | 12 | ไม่มี |
| สถานะ `unchanged` | 12 | 12 | ไม่มี |
| `needs_review` | 6 | 6 | ไม่มี |
| `staging_path IS NOT NULL` | 0 | 0 | ไม่มี |
| migration ที่ apply แล้ว | 001, 002, 003 | 001, 002, 003 | ไม่มี |
| `mko.crawl_decisions` | ไม่มี | ไม่มี | ไม่มี |
| `mko.v_crawl_queue` | ไม่มี | ไม่มี | ไม่มี |

**สรุป: ไม่พบ drift ทุกค่าตรงกับ Audit**

### 1.3 สิ่งที่พบเพิ่มในรอบนี้ (ไม่ใช่ drift แต่ Audit ยังไม่ได้บันทึก)

1. **`/home/ubuntu/course-advisor-system` บนเซิร์ฟเวอร์ไม่ใช่ git checkout** — ไม่มี `.git`
   และโฟลเดอร์ `db/` มีแค่ `schema.sql` กับ `20-roles.sh` **ไม่มี `db/migrations/` เลย**
   แปลว่า deploy ทำด้วยการส่งไฟล์ (archive) ไม่ใช่ `git pull` และ **ไฟล์ migration 004
   ยังไม่มีอยู่บนเซิร์ฟเวอร์** ต้องนำขึ้นตอน deploy — ดูข้อ 12

2. **backend ที่รันอยู่ไม่มีโค้ด Phase 3A เลย** ตรวจจาก OpenAPI ของคอนเทนเนอร์จริง:
   มี 21 path และ **ไม่มี path ใดที่มีคำว่า `crawl`** ไฟล์
   `app/services/crawl_review.py`, `app/services/staging_store.py`,
   `app/api/routes/crawl_review.py` **ไม่มีในอิมเมจ**

3. **frontend ที่รันอยู่ไม่มีหน้า `/crawl-review`** — ค้นใน `.next` ที่ build ไว้ พบ 0 รายการ
   หน้าที่ build ไว้คือ `index`, `match`, `compare`, `api`, `_not-found`

   ผลจากข้อ 2–3: การเปิดใช้ Phase 3 บน production **ไม่ใช่แค่ recreate เพื่อเพิ่ม mount**
   แต่ต้อง **build อิมเมจ backend และ frontend ใหม่จาก commit ที่มีโค้ด Phase 3A/3B**
   นี่เป็นขั้นที่ใหญ่กว่าที่แผนเดิมสื่อ และยังไม่ได้ทำในรอบนี้

4. `docker-compose.prod.yml` บนเซิร์ฟเวอร์ **เหมือนกับใน HEAD ทุกไบต์**
   (sha256 ขึ้นต้น `d76afeef4ec1383d` ทั้งสองฝั่ง, 162 บรรทัด) และ **ยังไม่มี service
   `ingest-worker`** (นับได้ 0 รายการ)

5. Ollama บน production มีโมเดล: `bge-m3:latest` (`790764642607`, 1.2 GB),
   `llama3.2:3b`, `gemma2:2b`, `qwen2.5:1.5b`, `qwen2.5:3b`, `qwen2.5:7b`
   → ตรงตามสัญญา `bge-m3` / 1024 **ตรวจเฉพาะ metadata ไม่ได้สร้าง embedding**

---

## 2–3. B1–B7 และ U1 · Before → After · สถานะ

| # | เรื่อง | Before | After | สถานะ |
|---|---|---|---|---|
| B1 | ไม่มี admin | `is_admin` = true 0 คน จาก 197 คน | ยังเป็น 0 — เตรียมขั้นตอน promote ไว้ ไม่ได้แก้ข้อมูล | **HUMAN ACTION REQUIRED** |
| B2 | ไม่มีงานให้ทดสอบ | 12 แหล่งเป็น `unchanged` ทั้งหมด, staging 0 | ยังเหมือนเดิม — ไม่สร้างของปลอม เขียนขั้นตอน one-job test ไว้ | **DEFERRED** |
| B3 | ไม่มี staging | โฟลเดอร์ไม่มี, backend ไม่ได้ตั้ง `CRAWL_STAGING_DIR` | สร้างโฟลเดอร์จริง (ว่าง) + พิสูจน์สิทธิ์ + เตรียม overlay config | **PREPARED** |
| B4 | worker image ขาด PyMuPDF | ไม่มีอิมเมจ worker เลย, อิมเมจ backend ไม่มี `fitz` | build อิมเมจเฉพาะทาง ตรวจ dependency และการโหลดโมดูลครบ | **RESOLVED** |
| B5 | ไม่มี rollback ของ frontend | อิมเมจที่รันอยู่หายจาก image store, dangling 0 | `docker commit` เก็บคอนเทนเนอร์ที่รันอยู่เป็นอิมเมจ + ตรวจแล้ว | **RESOLVED** |
| B6 | backup เก่า | ชุดล่าสุดเก่าหลายสัปดาห์ | dump + tar + manifest ใหม่ ตรวจด้วย `pg_restore --list` **และ restore จริงบน DB ชั่วคราว** | **RESOLVED** |
| B7 | `DOCUMENTS_DIR` | backend mount `:ro` (ถูกอยู่แล้ว), ไม่มี mount ของ worker | เตรียม mount `:rw` ให้ worker + พิสูจน์ uid/gid/mode และการอ่านข้ามผู้ใช้ | **PREPARED** |
| U1 | provenance ของอิมเมจ | อิมเมจเดิมไม่มี label บอก commit | ไม่แก้ของเดิม · อิมเมจใหม่ฝัง `org.opencontainers.image.revision` แล้ว | **RESOLVED** (เฉพาะอิมเมจใหม่) |

---

## 4. Production mutation ที่เกิดขึ้นจริงทั้งหมดในรอบนี้

รายการครบถ้วน ไม่มีการเปลี่ยนแปลงอื่นนอกจากนี้

| # | สิ่งที่เกิดขึ้น | ประเภท | ย้อนกลับได้ |
|---|---|---|---|
| 1 | สร้าง `/home/ubuntu/backups/prod_pre_phase3d_step2_20260928T060312Z.dump` (+ `.sha256`) | เพิ่มไฟล์ | ลบไฟล์ |
| 2 | สร้าง `documents_manifest_20260928T060342Z.tsv` (+ `.sha256`) | เพิ่มไฟล์ | ลบไฟล์ |
| 3 | สร้าง `documents_20260928T060342Z.tar.gz` (+ `.sha256`) | เพิ่มไฟล์ | ลบไฟล์ |
| 4 | `docker commit --pause=false` คอนเทนเนอร์ frontend → tag `course-advisor-system-frontend:rollback-pre-phase3d` | เพิ่มอิมเมจ | ลบ tag |
| 5 | สร้าง `/home/ubuntu/workerbuild-617110e/` (build context จาก HEAD: `pipeline/`, `llm/`, `pipeline/Dockerfile`) | เพิ่มไฟล์ | ลบโฟลเดอร์ |
| 6 | build อิมเมจ `course-advisor-system-ingest-worker:617110e` | เพิ่มอิมเมจ | ลบอิมเมจ |
| 7 | สร้างโฟลเดอร์ `/home/ubuntu/course-advisor-system/staging/` และ `staging/crawl/` (ว่าง) + `chmod 755` | เพิ่มโฟลเดอร์ | ลบโฟลเดอร์ |
| 8 | สร้างและ **ลบแล้ว** ฐานข้อมูลชั่วคราว `phase3d_restore_test`, `phase3d_grant_test`, `phase3d_grant_test2` | ชั่วคราว | ลบแล้ว |
| 9 | ไฟล์ชั่วคราว `/tmp/004_crawl_decisions.sql`, `/home/ubuntu/phase3d_restore_test.sh`, `/home/ubuntu/phase3d_restore_test.log` | เพิ่มไฟล์ | ลบไฟล์ |
| 10 | ไฟล์ทดสอบสิทธิ์ `documents/.phase3d_write_probe` และ `staging/crawl/.crawler_write_probe` | ชั่วคราว | **ลบแล้ว** |
| 11 | คอนเทนเนอร์ชั่วคราว `--rm` (`python:3.11-slim`, อิมเมจ worker) สำหรับทดสอบสิทธิ์และ dependency | ชั่วคราว | จบแล้ว |

ยืนยันหลังทำงาน: `documents/` มี `.pdf` **30 ไฟล์เท่าเดิม** · `staging/crawl/` มี **0 รายการ** ·
ฐานข้อมูลที่เหลือคือ `course_advisor, postgres` เท่านั้น · `course_chunks` = 9039 เท่าเดิม ·
คอนเทนเนอร์ frontend ยัง `running`, `RestartCount=0`, `StartedAt=2026-09-04T17:27:43` ·
เนื้อที่ดิสก์ว่าง 64G / 97G (ใช้ 35%)

### สิ่งที่ "ไม่ได้" ทำกับ production

ไม่ apply migration · ไม่ INSERT/UPDATE/DELETE ข้อมูลจริงแม้แถวเดียว · ไม่แตะ `users` ·
ไม่แตะ `mko.crawl_sources` · ไม่แตะ `courses`/`course_documents`/`course_chunks` ·
ไม่ ingest · ไม่สร้าง embedding · ไม่รัน worker · ไม่ start/stop/restart/recreate บริการใด ·
ไม่แก้ `docker-compose.prod.yml` บนเซิร์ฟเวอร์ · ไม่แก้ `.env` · ไม่แก้ `Caddyfile` ·
ไม่ pull อิมเมจจากภายนอกนอกจาก `python:3.11-slim` ที่ใช้ทดสอบแล้วทิ้ง ·
ไม่เปิดเผยหรือคัดลอกค่า secret ใด ๆ (ตรวจ `.env` เฉพาะ "มีคีย์ชื่อนี้กี่บรรทัด" ไม่อ่านค่า)

---

## 5. Backup artifacts + checksum / การตรวจสอบ

เก็บที่ `/home/ubuntu/backups/` mode `600` ทั้งหมด

### 5.1 ฐานข้อมูล

```
prod_pre_phase3d_step2_20260928T060312Z.dump
  ขนาด   53,843,793 ไบต์ (52 MB)
  รูปแบบ  pg_dump custom format (-Fc)
  sha256  7be0c9c9f20de109d0c74497440622a37e50a6fe88041559c64ae4b3dfd83144
```

การตรวจสอบ 3 ชั้น

1. `sha256sum -c prod_pre_phase3d_step2_20260928T060312Z.dump.sha256` → **ผ่าน**
2. `pg_restore --list` → **244 บรรทัด, 29 รายการ TABLE DATA** อ่านสารบัญได้ปกติ
3. **restore จริงลงฐานข้อมูลชั่วคราวที่แยกจาก production** (`phase3d_restore_test`)
   — ไม่แตะ `course_advisor` เลย

   | ตาราง | restore | production | ผล |
   |---|---|---|---|
   | `courses` | 24 | 24 | ตรงกัน |
   | `course_documents` | 31 | 31 | ตรงกัน |
   | `course_chunks` | 9039 | 9039 | ตรงกัน |
   | `users` | 197 | 197 | ตรงกัน |
   | `mko.crawl_sources` | 12 | 12 | ตรงกัน |

   - `pg_restore` จบด้วย `rc=0` และ **0 บรรทัดที่มีคำว่า error/warning**
   - `course_chunks.embedding` ไม่เป็น NULL ครบ **9039 แถว**
   - ค้นด้วย vector บนสำเนา (`ORDER BY embedding <=> ...`) ได้ผล 5 แถว
     → pgvector และ index ใช้งานได้จริงบนสำเนา ไม่ใช่แค่ข้อมูลดิบ
   - `mko.schema_migrations` ในสำเนา = `001_mko_structured, 002_mko_review_publish, 003_crawl_sources`
   - ลบฐานข้อมูลชั่วคราวแล้ว — เหลือ `course_advisor, postgres`

   นี่คือการยืนยันว่า backup **กู้คืนได้จริง** ไม่ใช่เพียงอ่านสารบัญผ่าน

### 5.2 เอกสารต้นฉบับ

```
documents_20260928T060342Z.tar.gz
  ขนาด   78,086,887 ไบต์ (75 MB)
  sha256  c7aa8ae42ab37419bc6d589162bbb3df0d4331a20c81b1110932b58f85585450

documents_manifest_20260928T060342Z.tsv
  ขนาด   3,238 ไบต์
  sha256  1b12ad0309c6915b86ad137866d106bd0871c3b6230a62844d3170e3a57d35e6
```

- manifest มี **32 ไฟล์** (30 `.pdf` + `MANIFEST.tsv` + `ph_web.txt`) พร้อม sha256 ต่อไฟล์
- ตรวจในไฟล์ archive แล้วมี **30 `.pdf` ครบ**
- ไม่มี credential หรือ secret ในรายงานนี้และในไฟล์ manifest

---

## 6. Frontend rollback artifact (B5)

**ปัญหาเดิม:** คอนเทนเนอร์ frontend ที่ให้บริการอยู่ชี้อิมเมจ
`sha256:ce65aad64305…` ซึ่ง **ไม่มีอยู่ใน image store แล้ว** และ dangling image เป็น 0
ถ้า recreate ไปแล้วจะไม่มีทางย้อนกลับ (ยืนยันซ้ำในรอบนี้: `docker image inspect`
อิมเมจนั้นตอบ `No such image`)

**สิ่งที่ทำ:** `docker commit --pause=false course-advisor-system-frontend-1` — ไม่หยุด
ไม่ restart และไม่ recreate คอนเทนเนอร์

```
tag      course-advisor-system-frontend:rollback-pre-phase3d
image ID sha256:6b85413d6a03e9f33a1466b761c4b9d41460fe2d8eb3d29e5498e8eaf552b400
ขนาด     372 MB (ตามที่ docker images แสดง)
```

ตรวจแล้วว่าอ้างถึงได้จริง

- `Cmd = ["node","server.js"]`, `WorkingDir = /app`
- `/app/server.js` มีอยู่ (6,377 ไบต์)
- ชื่อตัวแปร environment เดิมติดมาครบ (ไม่แสดงค่า)
- `.next` ที่ build ไว้ **ไม่มี** `crawl-review` → ยืนยันว่านี่คือรุ่นก่อน Phase 3B จริง
- คอนเทนเนอร์เดิมไม่ถูกกระทบ: `status=running`, `RestartCount=0`,
  `StartedAt=2026-09-04T17:27:43`

**รอบนี้ไม่ได้ recreate frontend ตามข้อห้าม**

---

## 7. Worker image — ID / digest + การตรวจ dependency (B4, U1)

### 7.1 ที่มา

สร้างไฟล์ใหม่ `pipeline/Dockerfile` (ยัง untracked ใน working tree) แล้ว build บนเซิร์ฟเวอร์
จาก build context ที่ดึงจาก HEAD ด้วย
`git -c core.autocrlf=false archive` เพื่อไม่ให้ Windows แปลงเป็น CRLF

- โอนไฟล์ `pipeline/` + `llm/` จาก HEAD → `/home/ubuntu/workerbuild-617110e`
- ตรวจแล้ว: **36 ไฟล์ `.py`, 0 ไฟล์ที่มี CR**, สุ่มตรวจ 5 ไฟล์ hash ตรงกับ HEAD ทั้งหมด
- คำสั่ง build ฝัง revision:
  `docker build -f pipeline/Dockerfile --build-arg GIT_REVISION=617110e975dccc94b5e67f77990e34a071ccf9a0 -t course-advisor-system-ingest-worker:617110e .`

### 7.2 ข้อมูลอิมเมจ

```
tag        course-advisor-system-ingest-worker:617110e
image ID   sha256:c80cc9b2114139cc38ef91c044a8517b2cf4f30611c663d55de3b99747ae4588
ขนาด        330 MB (ตามที่ docker images แสดง)
สถาปัตยกรรม amd64/linux
ผู้ใช้        worker (uid/gid 1001)
CMD        ["python","-u","-m","pipeline.crawl.approve","--max-jobs","1"]
```

**U1 — OCI provenance label** (ตรวจหลัง build)

```
org.opencontainers.image.revision = 617110e975dccc94b5e67f77990e34a071ccf9a0
org.opencontainers.image.title    = SCI Advisor approved-curriculum ingest worker
```

อิมเมจนี้ build ในเครื่องเซิร์ฟเวอร์ ไม่ได้ push ขึ้น registry ใด
**image ID ข้างบนคือหลักอ้างอิงสำหรับ reproducibility และ rollback**

### 7.3 dependency ที่ตรวจในคอนเทนเนอร์ (`--network none` ไม่ต่อ DB ไม่ต่อ Ollama)

| โมดูล | ผล | แพ็กเกจ / รุ่น |
|---|---|---|
| `fitz` | import ได้ | PyMuPDF 1.28.2 |
| `psycopg` | import ได้ | psycopg 3.3.6 (+ `psycopg_binary` 3.3.6) |
| `pgvector` | import ได้ | pgvector 0.5.0 |
| `httpx` | import ได้ | httpx 0.28.1 |
| `dotenv` | import ได้ | python-dotenv 1.2.3 |
| Python | — | 3.11.16 |

ครบตาม `pipeline/requirements.txt` (`pymupdf>=1.24`, `psycopg[binary]>=3.2`,
`pgvector>=0.3`, `httpx>=0.27`, `tqdm>=4.66`, `python-dotenv>=1.0`)

หมายเหตุ: `import fitz` ขึ้นคำเตือน `The fitz API is deprecated … use import pymupdf`
เป็นคำเตือนของ PyMuPDF 1.28 ไม่ใช่ข้อผิดพลาด โค้ดใช้งานได้ปกติ
(ยังไม่แก้ `pipeline/extract_pdf.py` เพราะอยู่นอกขอบเขตรอบนี้)

### 7.4 โมดูล worker โหลดได้

- `pipeline.crawl.approve` โหลดจาก `/app/pipeline/crawl/approve.py`
- ค่าสัญญาในโค้ด: `REQUIRED_EMBED_MODEL = bge-m3`, `REQUIRED_EMBED_DIM = 1024`
- `pipeline.ingest`, `pipeline.extract_pdf`, `llm.connector` โหลดได้ทั้งหมด
  → โครงสร้าง `/app/pipeline` + `/app/llm` ในอิมเมจถูกต้อง
- `python -m pipeline.crawl.approve --help` แสดง `usage: approve.py [-h]
  [--database-url DATABASE_URL] [--max-jobs MAX_JOBS]` ตามที่ควร

**ไม่ได้รัน worker กับ production · ไม่ได้ ingest · ไม่ได้สร้าง embedding**

### 7.5 ตรวจว่าอิมเมจไม่มี secret ติดไป

- ไฟล์ชื่อ `.env` ในอิมเมจ: **0 ไฟล์**
- ตัวแปร environment ที่ฝังในอิมเมจ: `GPG_KEY HOME HOSTNAME LANG PATH PWD
  PYTHONDONTWRITEBYTECODE PYTHONUNBUFFERED PYTHON_SHA256 PYTHON_VERSION`
  (ของ base image ทั้งหมด ไม่มีค่าของโปรเจกต์)

---

## 8. Staging configuration (B3)

### 8.1 โฟลเดอร์บนเครื่องจริง

```
/home/ubuntu/course-advisor-system/staging/crawl
  mode   drwxr-xr-x (755)
  owner  ubuntu:ubuntu (1001:1001)
  ไฟล์    0 รายการ   ← ไม่มีข้อมูล crawl ปลอมแม้ไฟล์เดียว
```

ตรงกับแบบเดียวกับ `documents/` ที่ใช้อยู่ (755, `ubuntu:ubuntu`)

### 8.2 การตรวจสิทธิ์ — และการแก้ผลตรวจที่เข้าใจผิดครั้งแรก

ครั้งแรกผมทดสอบด้วย `sudo -u '#1000' test -r … -a -x …` บนเครื่อง host แล้วได้ผลว่า
uid 1000 **เข้าไม่ได้** ผลนั้น**อ่านไม่ได้ความ** เพราะการเดินทางบน host ต้องผ่าน
`/home/ubuntu` ซึ่งเป็น `drwxr-x---` (750) — uid 1000 ติดตั้งแต่ชั้นนั้น ยังไม่ถึง staging

ของจริงคือคอนเทนเนอร์เห็นโฟลเดอร์นี้ผ่าน bind mount ซึ่ง**เริ่มเดินทางที่จุด mount**
ไม่ผ่าน `/home/ubuntu` จึงไม่เกี่ยวกัน ทดสอบใหม่ด้วยคอนเทนเนอร์ชั่วคราว
(`--rm --network none --user 1000:1000`) ที่ mount โฟลเดอร์จริงเป็น `:ro`

| ข้อตรวจ | ผลที่ต้องได้ | ผลจริง |
|---|---|---|
| uid 1000 อ่านโฟลเดอร์ได้ | ได้ | **ได้** |
| uid 1000 traverse ได้ | ได้ | **ได้** |
| uid 1000 เขียนได้ | **ต้องไม่ได้** | **ไม่ได้** |
| เห็นไฟล์ | 0 รายการ | 0 รายการ |
| uid 1001 เขียนได้เมื่อ mount `:rw` (กรณี crawler) | ได้ และไฟล์เป็น 644 | **ได้ mode 644** |

ไฟล์ทดสอบถูกลบทั้งหมด staging เหลือ 0 รายการ

### 8.3 ใครเห็น staging แบบไหน

| ผู้ใช้ | โหมด | เหตุผล |
|---|---|---|
| crawler (`pipeline.crawl.sync`) | `:rw` | เป็นตัวเดียวที่ดาวน์โหลดไฟล์เข้ามา ต้องเขียนได้ |
| backend | `:ro` | แค่เปิด PDF ให้คนตรวจดู การอนุมัติทั้งหมดเขียนลงฐานข้อมูล ไม่เขียนไฟล์ |
| ingest-worker | `:ro` | แค่อ่านไฟล์ที่อนุมัติไปคัดลอกเข้าคลังเอกสาร ไม่ลบไม่ย้ายไฟล์ใน staging |

### 8.4 logical path ต้องตรงกัน — และเงื่อนไขที่มักพลาด

`mko.crawl_sources.staging_path` เก็บ **path ในมุมของคอนเทนเนอร์ที่ crawler รัน**
(`pipeline/crawl/sync.py` เขียน `str(out)` โดย `out = staging / ชื่อไฟล์`) ทั้งสามฝ่าย
จึงต้องเห็น path เดียวกัน คือ **`/srv/staging`**

- backend อ่านผ่าน `CRAWL_STAGING_DIR` (`backend/app/core/config.py:80`)
- worker อ่านผ่าน `CRAWL_STAGING_DIR` (`pipeline/crawl/approve.py:148`)
- **crawler ต้องถูกสั่งด้วย `--staging /srv/staging` (absolute)** ไม่ใช่ค่าเริ่มต้น
  `staging/crawl` ที่เป็น relative ไม่งั้นค่าที่บันทึกลงฐานข้อมูลจะเป็น path ที่
  backend/worker เปิดไม่ได้

ข้อดีของสถานะปัจจุบัน: `staging_path IS NOT NULL` = **0 แถว** จึง**ไม่มี path เก่าค้างที่ต้องแก้**
เริ่มจากศูนย์ได้สะอาด

### 8.5 config ที่เตรียมไว้ (ยังไม่ได้ใช้บนเครื่องจริง)

ไฟล์ใหม่ **`docker-compose.staging.yml`** (overlay แยก ไม่แก้ `docker-compose.prod.yml`)

```yaml
services:
  backend:
    environment:
      CRAWL_STAGING_DIR: /srv/staging
    volumes:
      - ./staging/crawl:/srv/staging:ro
```

ตรวจการผสม overlay แล้วด้วย `docker compose config` โดยใช้ **ไฟล์ env ปลอมในสแครตช์แพด**
(ไม่ใช้ `.env` จริง ไม่มี secret ปรากฏ) ผลที่ได้ในไฟล์รวม:

```
backend.environment.CRAWL_STAGING_DIR = /srv/staging
backend.environment.DOCUMENTS_DIR     = /srv/documents
backend.volumes[0]  documents -> /srv/documents  read_only: true
backend.volumes[1]  staging/crawl -> /srv/staging  read_only: true
```

คือ mount เดิมยังอยู่และยังเป็น read-only ส่วน staging ถูกเพิ่มเข้ามาแบบ read-only

**สถานะ: PREPARED — ยังไม่ apply เพราะการเพิ่ม mount ต้อง recreate backend
ซึ่งเป็นข้อห้ามของรอบนี้ (STOP ก่อน recreate ตามที่กำหนด)**

ผลกระทบระหว่างที่ยังไม่ apply: `CRAWL_STAGING_DIR` ของ backend เป็นค่าว่าง
(ยืนยันจากคอนเทนเนอร์ที่รันอยู่: ไม่ได้ตั้งค่านี้เลย) `staging_store` จึงปิดตัวเองและ
`GET /crawl-review/{id}/pdf` จะตอบ 404 ทุกคำขอ (ล้มแบบปิดประตู ไม่ใช่เปิดช่อง)
ส่วนคิว/อนุมัติ/ไม่สนใจ ทำงานได้โดยไม่ต้องมี mount นี้

---

## 9. `DOCUMENTS_DIR` mount strategy (B7)

### 9.1 หลักการ

| ผู้ใช้ | mount | uid ที่รัน | เหตุผล |
|---|---|---|---|
| backend | `./documents:/srv/documents:ro` | 1000 | อ่านเพื่อส่ง PDF ให้ผู้ใช้เท่านั้น **ห้ามเปลี่ยนเป็น rw** |
| ingest-worker | `./documents:/srv/documents:rw` | 1001 | เป็นตัวเดียวที่วางไฟล์ใหม่เข้าคลัง (`publish_document`) |

ยืนยันสถานะปัจจุบันของ backend ที่รันอยู่: mount เดียวคือ
`/home/ubuntu/course-advisor-system/documents -> /srv/documents` และ **`RW=false`**
**ไม่ได้แก้ให้เป็น rw ตามข้อห้าม**

### 9.2 UID / GID / file mode ที่ตรวจได้

ไฟล์ปัจจุบันใน `documents/`

| mode | เจ้าของ | จำนวน | หมายเหตุ |
|---|---|---|---|
| 644 | `ubuntu:ubuntu` | 30 | `.pdf` ทั้งหมด — other อ่านได้ |
| 600 | `ubuntu:ubuntu` | 2 | `MANIFEST.tsv`, `ph_web.txt` — ไม่ใช่ `.pdf` จึงไม่อยู่ในดัชนีเอกสาร |

ตรวจแล้วว่า **ไม่มีไฟล์ `.pdf` ใดที่ห้าม other อ่าน** (ค้นด้วย `! -perm -o=r` ได้ผลว่าง)
สอดคล้องกับผลใน Pre-Deploy Audit ที่ยืนยันว่า backend อ่าน PDF ได้ครบ 30/30

### 9.3 พิสูจน์ว่าไฟล์ที่ worker เขียน backend อ่านได้จริง

ทดสอบด้วยคอนเทนเนอร์ชั่วคราวสองตัว (`--rm --network none`) ไม่แตะบริการที่รันอยู่

1. uid **1001** mount `:rw` → เขียนไฟล์สำเร็จ ได้ `mode=644 owner=1001:1001`
2. uid **1000** mount `:ro` → **อ่านไฟล์นั้นได้** และ **เขียนไม่ได้** (ถูกต้อง)
3. ลบไฟล์ทดสอบแล้ว — `.pdf` ใน `documents/` ยังเป็น **30 ไฟล์เท่าเดิม**

สรุป: worker เขียนเป็น uid 1001 mode 644 ซึ่ง backend (uid 1000, กลุ่มไม่ตรงกัน) อ่านได้ผ่านสิทธิ์ other

### 9.4 ข้อจำกัดที่ต้องรู้ก่อน deploy — ดัชนีเอกสารของ backend สร้างครั้งเดียวต่อโปรเซส

`backend/app/services/document_store.py:104-109` สร้างดัชนี sha256 → path **ครั้งเดียว
แบบ lazy** แล้วเก็บไว้ในหน่วยความจำ **และไม่มีทางล้างดัชนี**

ผลคือ PDF ที่ worker เพิ่งวางลง `documents/` จะ**ยังเปิดผ่าน `/documents/{id}/pdf`
ไม่ได้จนกว่า backend จะเริ่มโปรเซสใหม่**

- คำตอบของระบบ (`/api/chat` และอื่น ๆ) **ไม่กระทบ** เพราะอ่านจาก `course_chunks` ในฐานข้อมูล
- กระทบเฉพาะปุ่มเปิดเอกสารต้นฉบับของเอกสารที่เพิ่งนำเข้า
- ทางแก้ที่ไม่ต้องเขียนโค้ดเพิ่ม: หลังนำเข้าเสร็จ ให้ restart backend หนึ่งครั้งในช่วงที่
  ไม่มีผู้ใช้ — ต้องบรรจุเป็นขั้นตอนใน deployment runbook (ยังไม่ทำในรอบนี้)

### 9.5 config ที่เตรียมไว้

ไฟล์ใหม่ **`docker-compose.worker.yml`** — overlay แยก ต้องสั่งเองทุกครั้ง

```yaml
services:
  ingest-worker:
    image: course-advisor-system-ingest-worker:617110e
    profiles: ["worker"]
    restart: "no"
    user: "1001:1001"
    environment:
      INGEST_DATABASE_URL: ${INGEST_DATABASE_URL:?ต้องตั้งค่าใน .env}
      OLLAMA_BASE_URL: http://ollama:11434
      EMBED_MODEL: ${EMBED_MODEL:-bge-m3}
      EMBED_DIM: ${EMBED_DIM:-1024}
      CRAWL_STAGING_DIR: /srv/staging
      DOCUMENTS_DIR: /srv/documents
    volumes:
      - ./staging/crawl:/srv/staging:ro
      - ./documents:/srv/documents:rw
```

การตัดสินใจเชิงออกแบบและเหตุผล

- **แยกไฟล์ ไม่ใส่ลง `docker-compose.prod.yml`** เพราะไฟล์นั้นถูกใช้กับ `up -d` เป็นปกติ
  ถ้าใส่ไว้ที่นั่นวันหนึ่งจะมีคนสั่ง `up` แล้วได้ ingestion ทำงานโดยไม่ตั้งใจ
- **`profiles: ["worker"]`** เป็นด่านที่สอง — ตรวจแล้วว่า `docker compose config --services`
  ของ `prod + worker` คืนเพียง `ollama postgres backend frontend webapi caddy`
  **ไม่มี `ingest-worker`** จึงไม่ถูกสร้างจาก `up -d` เฉย ๆ
- **`restart: "no"`** เพราะ worker ออกด้วยรหัส 1 เมื่อมีงานล้มเหลว ถ้าให้ restart อัตโนมัติ
  งานที่ล้มจะถูกลองใหม่วนไปโดยไม่มีคนเห็น
- **ไม่ใช้ `:latest`** ผูกกับ tag `617110e` เพื่อให้ rollback ชี้อิมเมจเดิมได้
- **ไม่มี scheduler / cron / entrypoint ที่วนรอ** ตามข้อกำหนดของ Phase 3
- **`INGEST_DATABASE_URL` อ่านจาก `.env` ของโปรเจกต์** ไม่ประกอบ DSN ขึ้นใหม่ในไฟล์นี้
  (ตรวจแล้วว่า `.env` มีคีย์นี้อยู่ 1 บรรทัด — ไม่ได้อ่านค่า)

ตรวจการผสมแล้วด้วย `docker compose --profile worker … config` (env ปลอม) ได้ตามนี้:
`staging` เป็น `read_only: true`, `documents` เป็น rw, `user 1001:1001`,
`networks: default` (จึงเรียก `postgres` / `ollama` ด้วยชื่อ service ได้)

เงื่อนไขก่อนใช้: โฟลเดอร์ `staging/crawl` ต้องมีอยู่ก่อน (สร้างแล้วในข้อ 8.1) ไม่งั้น
Docker จะสร้างให้เองโดยเป็นของ `root`

**สถานะ: PREPARED — ยังไม่ start worker ตามข้อห้าม**

---

## 10. Admin prerequisite (B1) — HUMAN ACTION REQUIRED

### 10.1 สถานะ (aggregate เท่านั้น ไม่เปิดเผย PII)

| รายการ | จำนวน |
|---|---|
| ผู้ใช้ทั้งหมด | 197 |
| ผู้ใช้ที่ active | 197 |
| `is_admin = true` | **0** |
| `is_admin = true AND is_active` | **0** |

ไม่ได้ดึงอีเมล ชื่อ หรือข้อมูลระบุตัวบุคคลใด ๆ ออกมา

### 10.2 ทำไมเรื่องนี้ปิดกั้น Phase 3

`backend/app/api/routes/crawl_review.py:53` ใส่ `dependencies=[Depends(require_admin)]`
ไว้ที่ระดับ router ทุกเส้นทางของ `/crawl-review` จึงต้องเป็น admin
และ `require_admin` (`backend/app/api/deps.py:50-53`) ตรวจ `user.is_admin` ตรง ๆ

เมื่อไม่มีบัญชี admin แม้บัญชีเดียว **ไม่มีใครเปิดคิว ดู PDF หรืออนุมัติได้เลย**
และเนื่องจาก `decided_by` มาจากตัวตนฝั่งเซิร์ฟเวอร์ (`str(admin.email)`) ไม่ใช่จาก request body
จึงไม่มีทางข้ามขั้นนี้ด้วยการยิง API เอง — ซึ่งเป็นพฤติกรรมที่ต้องการ

### 10.3 ขั้นตอนที่เตรียมไว้ (ยังไม่ได้รัน)

**ผมไม่เลือกบัญชีเอง ไม่สร้าง admin ใหม่ และไม่ `UPDATE is_admin`**
รอเจ้าของโปรเจกต์ระบุบัญชีและอนุมัติ

เมื่อได้รับอนุมัติแล้ว ขั้นตอนคือ (แทน `<อีเมล>` ด้วยบัญชีที่เจ้าของโปรเจกต์ระบุ)

```sql
-- 1) ยืนยันว่ามีบัญชีนั้นจริงและ active (ควรได้ 1 แถว)
SELECT id, is_active, is_admin FROM users WHERE email = '<อีเมล>';

-- 2) ยกระดับในธุรกรรมเดียว ตรวจผลก่อน COMMIT
BEGIN;
UPDATE users SET is_admin = true WHERE email = '<อีเมล>' AND is_active;
--    ต้องได้ UPDATE 1 — ถ้าเป็น 0 ให้ ROLLBACK แล้วตรวจอีเมลอีกครั้ง
SELECT count(*) AS admin_total FROM users WHERE is_admin;   -- ต้องได้ 1
COMMIT;
```

ข้อควรรู้

- **ไม่ต้อง restart backend** — `get_current_user` อ่านแถวผู้ใช้จากฐานข้อมูลทุกคำขอ
  (`db.get(User, …)` ที่ `deps.py:44`) สิทธิ์จึงมีผลทันที
- ย้อนกลับได้ด้วย `UPDATE users SET is_admin = false WHERE email = '<อีเมล>';`
- ควรยกระดับ **บัญชีเดียว** ก่อน แล้วทดสอบ จึงพิจารณาเพิ่ม
- แต่ต้องรู้ด้วยว่าแม้ยกระดับแล้ว **`/crawl-review` ยังใช้ไม่ได้จนกว่าจะ build backend/frontend
  ใหม่** (ข้อ 1.3) — การยกระดับ admin เพียงอย่างเดียวยังไม่ทำให้ระบบใช้งานได้

---

## 11. Legitimate candidate strategy สำหรับ B2 — DEFERRED

### 11.1 สถานะ

12 แหล่งใน `mko.crawl_sources` เป็น `unchanged` ทั้งหมด, `staging_path` ว่างทั้ง 12 แถว
จึง **ไม่มีงานจริงให้ทดสอบ**

**ไม่สร้าง `crawl_source` ปลอม · ไม่แก้ `status` เพื่อหลอกระบบ · ไม่เอา PDF เก่ามาทำเป็นไฟล์ใหม่ ·
ไม่ force ingestion** — คงสถานะ DEFERRED ตามที่กำหนด

### 11.2 งานจริงจะเกิดขึ้นเมื่อไหร่

crawler (`pipeline/crawl/sync.py`) จะตั้งสถานะให้เอง

- `downloaded` — เจอ URL ของ PDF ที่ไม่เคยเห็น
- `changed` — `file_sha256` ต่างจาก `previous_sha256` ของ URL เดิม

ทั้งสองกรณีจะเขียน `staging_path` ให้ด้วย เงื่อนไขคือ **ทางเว็บ `sci.pnru.ac.th` ต้องมี
มคอ. ใหม่หรือมีการแก้ไฟล์เดิมจริง** ซึ่งควบคุมจากฝั่งเราไม่ได้และไม่ควรปลอม

### 11.3 ขั้นตอน controlled one-job test เมื่อมี legitimate candidate

ทำตามลำดับนี้ และหยุดทันทีเมื่อข้อใดไม่เป็นไปตามคาด

**ก่อนเริ่ม**

1. ต้องผ่านทุกข้อนี้แล้ว: migration 004 apply บน production, backend/frontend build ใหม่
   จาก commit ที่มีโค้ด Phase 3A/3B, backend มี mount staging และ `CRAWL_STAGING_DIR`,
   มีบัญชี admin 1 บัญชี
2. `pg_dump -Fc` ใหม่ + sha256 ก่อนแตะอะไร
3. บันทึก baseline: `courses`, `course_documents`, `course_chunks`,
   `mko.crawl_sources` แยกตามสถานะ, `mko.crawl_decisions`

**รัน crawler หนึ่งรอบ**

4. รันในคอนเทนเนอร์ชั่วคราว (`--rm`) ส่ง credential ด้วย `--env-file` เท่านั้น ห้ามพิมพ์ค่า
   และต้องสั่ง `--staging /srv/staging` แบบ absolute
5. ตรวจว่าได้ `downloaded`/`changed` **เพียง 1 แถว** ถ้าได้มากกว่านั้น
   ให้เลือกทดสอบทีละแถวและปล่อยแถวที่เหลือไว้
6. ตรวจไฟล์ใน staging: มีจริง, `%PDF-` ถูกต้อง, sha256 ตรงกับในฐานข้อมูล, ขนาด ≤ 50 MB

**ให้คนตรวจและอนุมัติ**

7. เข้าหน้า `/crawl-review` ด้วยบัญชี admin (เข้าทางประตู IP เพราะโดเมนเสิร์ฟ `/srv/web`
   ของทีมออกแบบ ซึ่งไม่มีเส้นทางนี้ — ดูข้อ 14)
8. **เปิด PDF ดูจริงก่อนอนุมัติ** ยืนยันว่าเป็น มคอ. ของหลักสูตรที่ระบบจับคู่มา
9. จับคู่กับ `courses` ที่มีอยู่แล้วเท่านั้น (Phase 3 v1 ห้ามสร้าง course ใหม่)
10. กดอนุมัติ 1 แถว — ตรวจว่าเกิด 1 แถวใน `mko.crawl_decisions` ที่
    `decision='approve'`, `superseded_at IS NULL`, `decided_by` เป็นอีเมลของ admin จริง

**รัน worker หนึ่งงาน**

11. ```
    docker compose -f docker-compose.prod.yml -f docker-compose.worker.yml \
      run --rm ingest-worker
    ```
    (ค่าเริ่มต้นคือ `--max-jobs 1` — งานเดียวแล้วจบ)
12. ตรวจรหัสออก: 0 = สำเร็จ, 1 = มีงานล้มเหลว ถ้าได้ 1 ให้อ่าน `ingest_error`
    แล้ว**หยุด** ไม่ลองซ้ำจนรู้สาเหตุ
13. ตรวจผลลัพธ์: `ingest_finished_at` และ `document_id` ถูกเติม, `course_documents`
    เพิ่มขึ้น 1, `course_chunks` เพิ่มขึ้นตามจำนวนช่วงของเอกสารนั้น,
    มีไฟล์ใหม่ใน `documents/` เป็น mode 644 owner 1001
14. ตรวจว่า **ไม่มีเอกสารเดิมถูกเขียนทับ** — sha256 ของ 30 ไฟล์เดิมต้องตรงกับ manifest
15. ยิง `/api/chat` ด้วยคำถามที่ควรตอบจากเอกสารใหม่ และคำถามเดิมที่เคยตอบได้
    **ทั้งสองต้องยังถูก** (การถดถอยของคำถามเดิมสำคัญกว่าคำถามใหม่)
16. restart backend หนึ่งครั้งเพื่อให้ดัชนีเอกสารเห็นไฟล์ใหม่ (ข้อ 9.4) แล้วทดสอบเปิด PDF

**ถ้าล้มเหลว**

17. rollback ด้วย dump จากข้อ 2 (ดูข้อ 18) และเก็บไฟล์ใน staging ไว้เป็นหลักฐาน
    ห้ามลบก่อนสรุปสาเหตุ

---

## 12. Migration 004 readiness

**รอบนี้ไม่ได้ apply บน production ตาม DEFAULT ที่กำหนด** — ตรวจความพร้อมเท่านั้น

### 12.1 ไฟล์

```
db/migrations/004_crawl_decisions.sql
  153 บรรทัด
  sha256 (LF) 0a689ea3dbe84be9…  ← ตรงกันทั้งฝั่ง HEAD และฝั่งที่ส่งขึ้นทดสอบ
  ไม่มี CR ปน (0 บรรทัด)
```

**ข้อที่ต้องทำก่อน deploy:** เซิร์ฟเวอร์**ยังไม่มีโฟลเดอร์ `db/migrations/` เลย**
(มีแค่ `db/schema.sql`, `db/20-roles.sh`) จึงต้องนำไฟล์ 004 ขึ้นไปพร้อม deploy
และควรใช้ `git -c core.autocrlf=false archive` เพื่อไม่ให้ Windows แปลงเป็น CRLF

### 12.2 ทดสอบ apply บนฐานข้อมูลชั่วคราวที่แยกจาก production

ทดสอบบนสำเนาที่ restore จาก dump ของวันนี้ (ข้อมูลจริง 9039 chunks) **ไม่แตะ `course_advisor`**

| ข้อตรวจ | ผล |
|---|---|
| apply บน DB ที่มี 001–003 | **สำเร็จ (`rc=0`)** |
| `mko.crawl_decisions` ถูกสร้าง | ใช่ |
| จำนวนคอลัมน์ | 15 |
| CHECK constraint | 7 |
| index | `crawl_decisions_pkey`, `idx_crawl_decisions_source`, `idx_crawl_decisions_todo`, `uq_crawl_decisions_active` |
| `mko.v_crawl_queue` ถูกสร้าง | ใช่ |
| view **ไม่มี** คอลัมน์ `staging_path` | ถูกต้อง (0) — ไม่รั่ว path ออก API |
| `mko.schema_migrations` หลัง apply | `001, 002, 003, 004_crawl_decisions` |

### 12.3 รันซ้ำได้ (ผมคาดผิดในตอนแรก)

ผมคาดว่าการ apply ซ้ำจะล้มเหลว **ผลจริงคือ `rc=0` ทั้งสองรอบ** เพราะไฟล์ออกแบบให้
idempotent ไว้แล้ว: `CREATE TABLE IF NOT EXISTS`, `CREATE … INDEX IF NOT EXISTS`,
`CREATE OR REPLACE VIEW`, และ `ON CONFLICT (version) DO NOTHING`
ตรวจสภาพหลัง apply สองรอบแล้วไม่มีของซ้ำ:

```
schema_migrations ที่ version='004_crawl_decisions' : 1 แถว
คอลัมน์ 15 · index 4 · CHECK 7 · แถวในตาราง 0
```

พฤติกรรมนี้**ดีกว่า**ที่ผมคาด เพราะ deploy ซ้ำโดยไม่ตั้งใจจะไม่ทำอะไรเสียหาย

### 12.4 สิทธิ์ที่ 004 มอบ — ตรวจด้วยสิทธิ์จริง

`advisor_api` บน `mko.crawl_decisions`

| ระดับ | สิทธิ์ |
|---|---|
| table | `SELECT`, `INSERT` |
| column `UPDATE` | **`superseded_at`, `superseded_by` เท่านั้น** |

ทดสอบด้วย `SET ROLE advisor_api` แล้วถาม `has_column_privilege` / `has_table_privilege`

| ข้อตรวจ | ผลที่ต้องได้ | ผลจริง |
|---|---|---|
| `UPDATE superseded_at` | อนุญาต | อนุญาต |
| `UPDATE decision` | ปฏิเสธ | **ปฏิเสธ** |
| `UPDATE ingest_started_at` | ปฏิเสธ | **ปฏิเสธ** |
| `UPDATE document_id` | ปฏิเสธ | **ปฏิเสธ** |
| `DELETE` บนตาราง | ปฏิเสธ | **ปฏิเสธ** |

นี่คือสิ่งที่ทำให้รูปแบบ append-only ทำงานได้จริง: backend ยกเลิกการตัดสินใจได้
(ตั้ง `superseded_at`) แต่แก้เนื้อการตัดสินใจเดิมไม่ได้ และลบไม่ได้

`advisor_api` บน `mko.crawl_sources` — `SELECT` เฉพาะ 4 คอลัมน์
`id`, `file_sha256`, `staging_path`, `status` (ไม่เห็นคอลัมน์อื่น)
`advisor_ingest` ได้ `SELECT, INSERT, UPDATE` ระดับตารางบน `mko.crawl_decisions`
และ `SELECT` บน `mko.v_crawl_queue`

### 12.5 สรุปความพร้อม

migration 004 **พร้อม apply** — apply ได้บนสำเนาข้อมูลจริง, รันซ้ำปลอดภัย,
สิทธิ์ถูกต้องตามการออกแบบ, เป็น additive ล้วน (ไม่มี DROP/ALTER ของเดิม),
ทั้งไฟล์อยู่ใน `BEGIN … COMMIT` เดียว
**เหลือเพียงการนำไฟล์ขึ้นเซิร์ฟเวอร์และการอนุมัติให้ apply**

---

## 13. GO / NO-GO หลัง Step 2

### **NO-GO** สำหรับเส้นทาง ingestion แบบ end-to-end

เหตุผลที่ปิดกั้น (ทั้งสองข้อแก้เองไม่ได้ในรอบนี้)

1. **ไม่มีบัญชี admin** — ต้องให้เจ้าของโปรเจกต์ระบุบัญชี (B1)
2. **ไม่มีงานจริงให้ทดสอบ** — ต้องรอ มคอ. ใหม่หรือของที่เปลี่ยนจริง (B2)

และข้อที่พบใหม่ในรอบนี้ ซึ่งทำให้ขอบเขตของ deployment ใหญ่กว่าที่แผนเดิมสื่อ

3. **อิมเมจ backend และ frontend ที่ให้บริการอยู่ไม่มีโค้ด Phase 3A/3B เลย**
   ต้อง **build ใหม่** ไม่ใช่แค่ recreate เพื่อเพิ่ม mount

### **CONDITIONAL GO** สำหรับขั้นตอน deploy ที่ไม่ต้องมีงานจริง

พร้อมทำได้เมื่อได้รับอนุมัติเป็นข้อ ๆ เพราะมี backup ที่กู้ได้จริงและมี rollback artifact ครบ

| ขั้น | ความพร้อม | ต้องได้อนุมัติเรื่อง |
|---|---|---|
| นำไฟล์ 004 ขึ้นเซิร์ฟเวอร์ | พร้อม | การเขียนไฟล์ลงโฟลเดอร์แอป |
| apply migration 004 | พร้อม (ทดสอบบนสำเนาแล้ว) | การแก้ schema ของ production |
| build + recreate backend จาก `617110e` | ยังไม่ได้ build | การ recreate บริการที่ให้บริการอยู่ |
| build + recreate frontend จาก `617110e` | ยังไม่ได้ build (มี rollback แล้ว) | การ recreate บริการที่ให้บริการอยู่ |
| ยกระดับ admin 1 บัญชี | พร้อม (มี SQL) | การระบุบัญชีจากเจ้าของโปรเจกต์ |
| รัน worker หนึ่งงาน | อิมเมจพร้อม config พร้อม | ต้องมี candidate จริงก่อน |

**ข้อเสนอลำดับที่ปลอดภัยที่สุด:** apply 004 ก่อน (additive, ย้อนกลับง่าย, ไม่กระทบโค้ดที่รันอยู่
เพราะ backend ปัจจุบันไม่รู้จักตารางใหม่เลย) → แล้วจึงพิจารณา build/recreate เป็นขั้นถัดไป

---

## 14. Blocker ที่ยังเหลือ

| # | เรื่อง | ใครแก้ | หมายเหตุ |
|---|---|---|---|
| 1 | ไม่มีบัญชี admin | **เจ้าของโปรเจกต์** | ระบุบัญชี แล้วรัน SQL ในข้อ 10.3 |
| 2 | ไม่มี legitimate candidate | **รอเว็บต้นทาง** | ห้ามปลอม ใช้ขั้นตอนข้อ 11.3 เมื่อมี |
| 3 | อิมเมจ backend/frontend ที่รันอยู่ไม่มีโค้ด Phase 3A/3B | ต้อง build + recreate | พบใหม่ในรอบนี้ ดูข้อ 1.3 |
| 4 | backend ยังไม่มี mount staging + `CRAWL_STAGING_DIR` | ต้อง recreate | config พร้อมแล้ว (`docker-compose.staging.yml`) |
| 5 | ดัชนีเอกสารของ backend ล้างไม่ได้ | ต้อง restart หลัง ingest | ดูข้อ 9.4 — ควรใส่ใน runbook |
| 6 | `/crawl-review` เข้าได้เฉพาะทางประตู IP | **เป็นการตัดสินใจแยก** | โดเมนเสิร์ฟ `/srv/web` ของทีมออกแบบ ซึ่งไม่มีเส้นทางนี้ · **ไม่แก้ Caddy ในรอบนี้ตามข้อห้าม** |
| 7 | อิมเมจเดิมพิสูจน์ commit ไม่ได้ | ยอมรับตามสภาพ | **ไม่ rewrite provenance** ของเก่า · ของใหม่มี label แล้ว |

---

## 15. ไฟล์ที่เปลี่ยนใน working tree

เพิ่มใหม่ 3 ไฟล์ · **ไม่แก้ไฟล์ที่ track ไว้แม้ไฟล์เดียว** · ไม่แตะโค้ด RAG /
recommendation / scoring / Gemini

| ไฟล์ | สถานะ | บรรทัด | หน้าที่ |
|---|---|---|---|
| `pipeline/Dockerfile` | untracked (ใหม่) | 59 | อิมเมจ one-shot ของ ingest worker (B4, U1) |
| `docker-compose.worker.yml` | untracked (ใหม่) | 52 | overlay ของ worker — staging `:ro`, documents `:rw`, profile `worker` (B7) |
| `docker-compose.staging.yml` | untracked (ใหม่) | 34 | overlay ให้ backend เห็น staging แบบ `:ro` (B3) |

รายงานนี้: `docs/AUTOMATED_INGESTION_PHASE3D_STEP2_REPORT.md` (untracked)

**ไม่ได้ `git add`, ไม่ได้ commit, ไม่ได้ push, ไม่ได้ merge, ไม่มีอะไรค้างใน staging area**

---

## 16. git status

```
branch  mko-phase2
HEAD    617110e975dccc94b5e67f77990e34a071ccf9a0
origin/mko-phase2  ชี้ commit เดียวกัน

staged            0 ไฟล์
modified tracked  0 ไฟล์

untracked นอก docs/
  ?? docker-compose.staging.yml
  ?? docker-compose.worker.yml
  ?? pipeline/Dockerfile

untracked ใน docs/   40 ไฟล์ (+ รายงานฉบับนี้)
```

---

## 17. สิ่งที่ยังไม่ได้ทำ (โดยเจตนา)

ตามข้อห้ามของรอบนี้

- ไม่ apply migration 004 บน production
- ไม่ recreate / restart / deploy backend, frontend, Caddy, postgres, ollama, webapi
- ไม่ build อิมเมจ backend/frontend ใหม่
- ไม่รัน ingest worker กับ production
- ไม่ ingest PDF และไม่สร้าง embedding ใด ๆ (ตรวจ Ollama เฉพาะ metadata)
- ไม่สร้าง admin และไม่ `UPDATE is_admin`
- ไม่สร้าง candidate ปลอมและไม่แก้ `mko.crawl_sources`
- ไม่แก้ Caddy และไม่เพิ่มเส้นทาง `/crawl-review` บนโดเมน
- ไม่แก้ Supabase
- ไม่แก้ `.env` และไม่แสดง/คัดลอกค่า secret
- ไม่ merge main, ไม่ push, ไม่ commit, ไม่ `git add`
- ไม่ตั้ง scheduler / cron / systemd และไม่เพิ่มฟีเจอร์ใหม่
- ไม่ restore ทับ production (การทดสอบ restore ทำบนฐานข้อมูลชั่วคราวที่ลบแล้ว)
- ไม่แก้ `pipeline/ingest.py` และไม่แก้โค้ด RAG / Gemini

ค้างอยู่สำหรับรอบถัดไป

- นำไฟล์ 004 ขึ้นเซิร์ฟเวอร์ แล้ว apply
- build + recreate backend/frontend จาก `617110e`
- apply `docker-compose.staging.yml` (ต้อง recreate backend)
- ยกระดับ admin หลังเจ้าของโปรเจกต์ระบุบัญชี
- controlled one-job test เมื่อมี candidate จริง
- ตัดสินใจเรื่องเส้นทาง `/crawl-review` บนโดเมน
- เพิ่มขั้น restart backend หลัง ingest ลงใน runbook (ข้อ 9.4)

---

## 18. Rollback instructions สำหรับ mutation ที่เกิดใน Step 2

mutation ทั้งหมดเป็นแบบ **เพิ่มของใหม่** ไม่มีข้อใดแก้หรือลบของเดิม จึงย้อนกลับได้ครบ
และการ**ไม่ย้อนกลับ**ก็ไม่กระทบระบบที่ให้บริการอยู่

```bash
# 1) ลบอิมเมจ worker (ถ้าไม่ใช้ต่อ)
sudo docker image rm course-advisor-system-ingest-worker:617110e

# 2) ลบ tag rollback ของ frontend
#    เก็บไว้ก่อนดีกว่า จนกว่า Phase 3D จะจบและระบบใหม่นิ่งแล้ว
sudo docker image rm course-advisor-system-frontend:rollback-pre-phase3d

# 3) ลบ build context
rm -rf /home/ubuntu/workerbuild-617110e

# 4) ลบโฟลเดอร์ staging (ต้องว่างอยู่)
rmdir /home/ubuntu/course-advisor-system/staging/crawl \
      /home/ubuntu/course-advisor-system/staging

# 5) ลบไฟล์ชั่วคราว
rm -f /tmp/004_crawl_decisions.sql \
      /home/ubuntu/phase3d_restore_test.sh \
      /home/ubuntu/phase3d_restore_test.log

# 6) ลบ backup ของรอบนี้ (ไม่แนะนำ — เก็บไว้จนจบ Phase 3D)
#    /home/ubuntu/backups/prod_pre_phase3d_step2_20260928T060312Z.dump{,.sha256}
#    /home/ubuntu/backups/documents_20260928T060342Z.tar.gz{,.sha256}
#    /home/ubuntu/backups/documents_manifest_20260928T060342Z.tsv{,.sha256}
```

ฝั่ง repository — ลบไฟล์ที่เพิ่มใหม่ (ยังไม่ commit จึงไม่ต้อง revert)

```bash
rm docker-compose.worker.yml docker-compose.staging.yml pipeline/Dockerfile
```

ฐานข้อมูลชั่วคราวถูก `DROP` ไปแล้วทั้งสามตัว ตรวจซ้ำได้ด้วย

```sql
SELECT string_agg(datname, ',' ORDER BY datname)
FROM pg_database WHERE NOT datistemplate;
-- ต้องได้ course_advisor,postgres
```

### ถ้า Production Deployment รอบหน้าล้มเหลว

```bash
# กู้ฐานข้อมูลจาก dump ของวันนี้ (ตรวจ checksum ก่อนทุกครั้ง)
cd /home/ubuntu/backups
sha256sum -c prod_pre_phase3d_step2_20260928T060312Z.dump.sha256
# แล้วจึง restore ตามขั้นตอนของ runbook

# ย้อน frontend กลับรุ่นก่อน Phase 3D
#   แก้ image ของ service frontend ให้ชี้
#   course-advisor-system-frontend:rollback-pre-phase3d
#   (sha256:6b85413d6a03e9f33a1466b761c4b9d41460fe2d8eb3d29e5498e8eaf552b400)

# ย้อน migration 004 (additive ล้วน จึงถอนได้ตรง ๆ ถ้ายังไม่มีข้อมูลในตาราง)
#   DROP VIEW mko.v_crawl_queue;      -- แล้วสร้างรุ่นของ 003 กลับ
#   DROP TABLE mko.crawl_decisions;
#   DELETE FROM mko.schema_migrations WHERE version = '004_crawl_decisions';
```

**คำเตือนสำหรับอิมเมจ backend:** อิมเมจที่รันอยู่คือ `sha256:d1d1ba713412…`
(สร้าง 2026-09-23T23:53:40Z) **ยังอยู่ใน image store** ต่างจากกรณี frontend
จึงย้อนกลับได้ด้วยการชี้ image ID นี้ แต่ **ไม่มี label บอก commit** จึงยืนยันไม่ได้ว่า
build จาก commit ไหน (U1) — ก่อน recreate backend ควร `docker commit` เก็บไว้ด้วย
แบบเดียวกับที่ทำกับ frontend

---

## สรุปสั้น

- baseline ตรงกับ Audit ทุกค่า **ไม่พบ drift**
- **RESOLVED**: B4 (worker image), B5 (frontend rollback), B6 (backup + ทดสอบ restore จริง), U1 (label ของอิมเมจใหม่)
- **PREPARED**: B3 (staging + config), B7 (mount strategy + พิสูจน์สิทธิ์)
- **DEFERRED**: B2 (ไม่มี candidate จริง — ไม่ปลอม)
- **HUMAN ACTION REQUIRED**: B1 (เจ้าของโปรเจกต์ต้องระบุบัญชี admin)
- พบเพิ่ม: อิมเมจ backend/frontend ที่รันอยู่**ไม่มีโค้ด Phase 3A/3B** และเซิร์ฟเวอร์
  **ไม่มีโฟลเดอร์ `db/migrations/`** → ขอบเขต deployment ใหญ่กว่าที่แผนเดิมสื่อ
- แก้ผลตรวจของตัวเองหนึ่งข้อ: การทดสอบสิทธิ์ staging จาก host อ่านไม่ได้ความ
  เพราะ `/home/ubuntu` เป็น 750 — พิสูจน์ใหม่ด้วยคอนเทนเนอร์ที่ mount จริงแล้วผ่าน
- คาดผิดหนึ่งข้อ: migration 004 **รันซ้ำได้** (ออกแบบให้ idempotent) ไม่ได้ล้มเหลวอย่างที่ผมคาด

**STOP** — ไม่เริ่ม Phase 3D Deployment ต่อ ไม่ commit ไม่ push รอการตรวจรายงานนี้
