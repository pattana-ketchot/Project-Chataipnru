# Phase 3D Step 3 — Controlled Production Deployment (NO INGESTION)

**สถานะ: หยุดที่ Checkpoint 1 — ยังไม่มีการ deploy ใด ๆ**

| | |
|---|---|
| วันที่ | 2026-09-29 (preflight เริ่ม 00:25:19Z = 07:25:19 ไทย) |
| Repository | `D:/workspace/course-advisor-system-mko2` · branch `mko-phase2` |
| HEAD ตอนเริ่ม | `617110e975dccc94b5e67f77990e34a071ccf9a0` (ตรงตามที่กำหนด) |
| HEAD ตอนนี้ | `2fdc6f241fc1742047b572ee2ef354cd811f9401` (commit ใหม่ **ยังไม่ push**) |
| Production | `ubuntu@161.118.237.37` · compose project `course-advisor-system` |
| ผลรวม | Checkpoint 0 **PASS** · Checkpoint 1 **BLOCKED ที่ขั้น push** · Checkpoint 2–12 **ไม่ได้เริ่ม** |

**เหตุที่หยุด:** คำสั่ง `git push origin HEAD:refs/heads/mko-phase2` ถูกปฏิเสธโดยตัวตรวจสิทธิ์
ของ Claude Code (เหตุผลที่แจ้ง: `Production Deploy`) และกติกาของ Step 3 ข้อ Checkpoint 1 ระบุว่า
**"ก่อน push ตรวจ remote ไม่ drift; หาก push ไม่ผ่านให้ STOP ไม่เปลี่ยน deployment revision เงียบ ๆ"**
จึงหยุดตามคำสั่ง ไม่ข้ามไป packaging/build/cutover และไม่เปลี่ยนไปใช้ revision อื่นแทน

**Production ยังไม่ถูกเปลี่ยนแปลงเชิงบริการเลย** — ไม่ apply migration, ไม่ build อิมเมจ,
ไม่ recreate/restart บริการใด, ไม่แตะ Caddy, ไม่มี ingestion, ไม่มี embedding
mutation เดียวที่เกิดขึ้นคือการสร้าง docker tag สำหรับ rollback (ข้อ 16)

---

## 1. รายงาน Step 2 ที่ใช้เป็นฐาน · เวลา preflight · drift

### 1.1 ไฟล์รายงาน Step 2

สภาพแวดล้อมนี้เป็น Windows และ **ไม่มี path `/mnt/data/`** ตามที่ prompt อ้างถึง
จึงใช้สำเนาในโปรเจกต์ ซึ่งเป็นไฟล์เดียวกับที่ส่งมอบเมื่อจบ Step 2

```
docs/AUTOMATED_INGESTION_PHASE3D_STEP2_REPORT.md
  889 บรรทัด · 63,842 ไบต์
  sha256 9d1265d6dca3af7247fce16659bb4b479672db63b551ebd4c25052dca79ad9e5
```

### 1.2 Repository baseline (ตรวจ remote ref สด ไม่เชื่อ remote-tracking)

| รายการ | Expected | Actual | ผล |
|---|---|---|---|
| branch | `mko-phase2` | `mko-phase2` | ตรง |
| HEAD ตอนเริ่ม | `617110e97…` | `617110e975dccc94b5e67f77990e34a071ccf9a0` | ตรง |
| `refs/heads/mko-phase2` บน remote | `617110e97…` | `617110e975dccc94b5e67f77990e34a071ccf9a0` | ตรง |
| `refs/heads/main` บน remote | — | `b78b3f8bf895685874d9a52c66b45569072f0514` | ไม่แตะ |
| staged | 0 | 0 | ตรง |
| tracked modified | 0 | 0 | ตรง |
| untracked นอก `docs/` | 3 ไฟล์ deployment | 3 ไฟล์เดียวกัน | ตรง |

remote คือ `https://github.com/pattana-ketchot/Project-Chataipnru.git` (ไม่มี credential ใน URL)
ไม่มีการ `checkout`, `reset`, `clean` หรือ `stash` ใด ๆ

### 1.3 Production baseline — read-only (`BEGIN TRANSACTION READ ONLY`, `statement_timeout=15s`)

ตรวจชื่อ schema จริงก่อน query: พบ `mko` และ `public` ตามที่คาด

| รายการ | Expected (Step 2) | Actual (2026-09-29 07:25 ไทย) | drift |
|---|---|---|---|
| `courses` | 24 | 24 | ไม่มี |
| `course_documents` | 31 | 31 | ไม่มี |
| `course_chunks` | 9039 | 9039 | ไม่มี |
| embedding dimension | 1024 | 1024 | ไม่มี |
| users / active | 197 / 197 | 197 / 197 | ไม่มี |
| admin / active admin | 0 / 0 | 0 / 0 | ไม่มี |
| `mko.crawl_sources` | 12 | 12 | ไม่มี |
| `status='unchanged'` | 12 | 12 | ไม่มี |
| `needs_review` | 6 | 6 | ไม่มี |
| `staging_path IS NOT NULL` | 0 | 0 | ไม่มี |
| `mko.schema_migrations` | 001, 002, 003 | `001_mko_structured, 002_mko_review_publish, 003_crawl_sources` | ไม่มี |
| `mko.crawl_decisions` | ยังไม่มี | ไม่มี (0) | ไม่มี |
| `mko.v_crawl_queue` | ยังไม่มี | ไม่มี (0) | ไม่มี |
| mko tables / views | 19 / 7 | 19 / 7 | ไม่มี |
| public tables | 10 | 10 | ไม่มี |

### 1.4 เอกสาร — เทียบ manifest ทีละไฟล์ ไม่ใช่นับอย่างเดียว

เทียบ sha256 และขนาดของทุกบรรทัดใน `documents_manifest_20260928T060342Z.tsv`
กับไฟล์จริงใน `/home/ubuntu/course-advisor-system/documents`

```
manifest 32 รายการ -> hash ตรง 32 · ไม่ตรง 0 · ขาด 0 · ขนาดต่าง 0
ไฟล์บนดิสก์ที่ไม่อยู่ใน manifest: 0
.pdf บนดิสก์: 30
โฟลเดอร์ย่อย: curriculum, curriculum-brief, web
```

`staging/crawl` ว่าง (0 รายการ) ตามที่คาด

### 1.5 บริการและคอนเทนเนอร์ — ก่อนทำอะไร

| service | image | state | restarts | startedAt |
|---|---|---|---|---|
| backend | `sha256:d1d1ba713412…` | running (ไม่มี healthcheck) | 0 | 2026-09-23T23:53:41Z |
| frontend | `sha256:ce65aad64305…` | running (ไม่มี healthcheck) | 0 | 2026-09-04T17:27:43Z |
| caddy | `sha256:5f5c8640aae0…` | running | 0 | 2026-09-22T21:23:48Z |
| postgres | `sha256:ccc6e83d6e35…` | running (healthy) | 0 | 2026-08-18T14:17:25Z |
| ollama | `sha256:9d30908e4114…` | running (healthy) | 0 | 2026-08-18T14:17:25Z |
| webapi | `sha256:1163e36361d9…` | running (healthy) | 0 | 2026-09-22T21:21:35Z |

compose project = `course-advisor-system` · project working_dir = `/home/ubuntu/course-advisor-system`
network = `course-advisor-system_default` · backend cmd `uvicorn app.main:app --host 0.0.0.0 --port 8000`
backend workdir `/app/backend` user `appuser` · frontend cmd `node server.js` entrypoint `docker-entrypoint.sh`

ports ที่เปิดออกนอกเครื่องมีเฉพาะ caddy `80:80` และ `443:443`

**ยืนยันว่าไม่มี worker/crawler ทำงาน:** ไม่มีคอนเทนเนอร์ชื่อ/อิมเมจที่เกี่ยวกับ worker หรือ ingest
เลยแม้แต่ที่หยุดอยู่ และ `pgrep -af 'pipeline.crawl'` บน host ได้ 0 รายการ
(มีคอนเทนเนอร์ `db-viewer` รันอยู่ แต่อยู่นอก compose project นี้ และไม่ได้แตะในรอบนี้)

### 1.6 Drift: **ไม่พบ**

ทุกค่าตรงกับ Step 2 ทั้งข้อมูล ไฟล์ config และ schema

---

## 1.7 ข้อที่ต้องแก้จากรายงาน Step 2 และจาก prompt

รายการนี้แยกออกมาเพราะเป็นการแก้ข้อเท็จจริง ไม่ใช่ drift

1. **`pipeline/Dockerfile` มี 58 บรรทัด ไม่ใช่ 59**
   prompt และตาราง §15 ของรายงาน Step 2 ระบุ 59 บรรทัด ค่าจริงคือ 58
   (`wc -l` = 58, ไฟล์ปิดท้ายด้วย `\n`, และ `git show --stat` ของ commit ใหม่ยืนยัน
   `58 insertions` สำหรับไฟล์นี้ รวมสามไฟล์ 144 = 34+52+58)
   ที่มาของความผิด: ตอน Step 2 ผมอ่านจำนวนบรรทัดจากการแสดงผลของเครื่องมืออ่านไฟล์
   ซึ่งนับบรรทัดว่างท้ายไฟล์เป็นบรรทัดที่ 59

2. **ผมรายงานผิดกลางรอบนี้ว่าไฟล์เป็น CRLF — ที่จริงเป็น LF ทั้งหมด**
   คำสั่ง `grep -c $'\r'` ใน Git Bash ให้ผลลวงว่าทุกบรรทัดมี CR
   นับไบต์จริงแล้วได้ `CRLF=0` ทุกไฟล์ ทั้ง working tree, blob ที่ staged
   และไฟล์ที่ track อยู่แล้ว (`HEAD:docker-compose.prod.yml` 10,606 ไบต์ CRLF=0,
   `HEAD:db/migrations/004_crawl_decisions.sql` 11,949 ไบต์ CRLF=0)
   จึง **ไม่มีปัญหา line ending ที่ต้องจัดการในรอบนี้**

3. **การตรวจไฟล์ Phase 3A ในอิมเมจ backend ของ Step 2 ใช้ path ผิด**
   Step 2 ตรวจที่ `/app/app/services/...` แต่ workdir จริงของ backend คือ `/app/backend`
   ตรวจใหม่ด้วย path ที่ถูก (`/app/backend/app/services/...`) ได้ผลเดิมคือ **ไม่มีไฟล์**
   และยืนยันเพิ่มว่า `find /app -name "*crawl*" -o -name "*staging*"` ได้ **0 ไฟล์**
   ส่วน `app/services/document_store.py` และ `app/main.py` **มี** ซึ่งพิสูจน์ว่า path ถูกต้องแล้ว
   → ข้อสรุปของ Step 2 ถูก แต่หลักฐานเดิมใช้อ้างไม่ได้ ตอนนี้มีหลักฐานที่ถูกต้องแทน

4. **โดเมนตอบ HTTP 200 ให้ `/crawl-review` อยู่แล้วตั้งแต่ก่อน deploy**
   เพราะ Caddy ตั้ง `try_files {path} /index.html` ให้ SPA ที่ `/srv/web`
   จึงตอบ index.html ให้ทุก path ที่ไม่รู้จัก **ห้ามนับ 200 นี้เป็นหลักฐานว่า route มีจริง**
   ค่าที่มีความหมายคือทาง `:80` ซึ่งตอบ **404** ตอนนี้ และควรเป็น 200 หลัง deploy frontend

5. **พบใหม่: API ของ `/crawl-review` ใช้โดเมนได้โดยไม่ต้องแก้ Caddy**
   `Caddyfile` มีบล็อก `handle /api/*` ที่ทำ `uri strip_prefix /api` แล้วส่งไป `backend:8000`
   ดังนั้น `https://<โดเมน>/api/crawl-review/…` → `/crawl-review/…` บน backend ได้เลย
   (ตรวจแล้ว: `GET https://…/api/crawl-review/pending` ตอบ 404 ตอนนี้ ตรงกับที่ backend ยังไม่มี route
   ขณะที่ `GET https://…/api/health` ตอบ 200 พิสูจน์ว่าเส้นทางถึง backend จริง)
   ข้อจำกัด "เข้าได้เฉพาะทาง IP" ของ Step 2 เป็นจริงเฉพาะ **หน้าเว็บ** ไม่ใช่ **API**

6. **พบใหม่: อิมเมจ backend ที่รันอยู่ถือ tag `course-advisor-system-backend:latest`**
   ถ้า build ใหม่ด้วย tag เริ่มต้นของ compose จะทับ tag นี้ และอิมเมจเดิมจะกลายเป็น
   อิมเมจไม่มีชื่อซึ่งเสี่ยงถูก prune — เป็นเหตุที่ต้องสร้าง rollback tag ก่อน build
   และต้อง build ด้วย immutable tag แยก (แผนเดิมของ Checkpoint 3 ถูกอยู่แล้ว
   แต่เหตุผลหนักกว่าที่คาด)

---

## 2. Exact deployed revision

**ไม่มีการ deploy** ในรอบนี้

| ส่วน | revision ที่ให้บริการอยู่ | หมายเหตุ |
|---|---|---|
| backend | พิสูจน์ไม่ได้ | อิมเมจ `sha256:d1d1ba713412…` ไม่มี OCI revision label (U1) |
| frontend | พิสูจน์ไม่ได้ | อิมเมจ `sha256:ce65aad64305…` ไม่มี label และหายจาก image store |
| database schema | migration 001–003 | ยังไม่ apply 004 |

**Approved source revision ที่เตรียมไว้ (ยังไม่อนุมัติเพราะ push ไม่ผ่าน):**
`2fdc6f241fc1742047b572ee2ef354cd811f9401`

ยังไม่มี artifact hash ของ deployment package เพราะยังไม่ได้ทำ packaging (Checkpoint 1 ท่อนหลัง)

---

## 3. Commit ที่สร้างและผล push

### 3.1 Commit ที่สร้าง (local เท่านั้น)

```
commit  2fdc6f241fc1742047b572ee2ef354cd811f9401
parent  617110e975dccc94b5e67f77990e34a071ccf9a0
branch  mko-phase2
message chore: version the deployment files for the crawler review rollout
stat    3 files changed, 144 insertions(+)
          docker-compose.staging.yml | 34 +
          docker-compose.worker.yml  | 52 +
          pipeline/Dockerfile        | 58 +
```

ใช้ `git add -- <exact-paths>` เท่านั้น ไม่ใช้ `git add .` / `-A`
ตรวจ staged list ก่อน commit แล้ว: มี 3 ไฟล์พอดี ไม่มี docs, ไม่มีรายงาน, ไม่มี `.env`,
ไม่มี untracked อื่น (`docs/` 41 ไฟล์ยัง untracked อยู่ครบ ไม่ถูกดึงเข้า commit)

### 3.2 การ review ทั้งสามไฟล์ก่อน commit

ไม่พบ secret ในไฟล์ใดเลย — การอ้างค่าลับทำผ่าน `${...}` ซึ่งอ่านจาก `.env` ของโปรเจกต์

| ไฟล์ | ไบต์ | บรรทัด | sha256 (blob ที่ commit) |
|---|---|---|---|
| `docker-compose.staging.yml` | 2,977 | 34 | `fa85a75762379cb1491965b4801149713dee88b2c4e4ac3b6eda3af193f4c49f` |
| `docker-compose.worker.yml` | 4,932 | 52 | `a6a4dd87013ca42f1e462f7880dfb6543b4c7394761a6d5fa1261127a21f5143` |
| `pipeline/Dockerfile` | 4,395 | 58 | `ca48cd2da16c7fefcd72edc42fa943b728ad67ec627d425e00db3c91848971a1` |

blob ที่ commit **เหมือน working tree ทุกไบต์** ทั้งสามไฟล์ (ตรวจด้วยการเทียบไบต์ ไม่ใช่ `grep`)

เหตุผลที่ commit แต่ละไฟล์

- **`docker-compose.staging.yml` — จำเป็น** prompt กำหนดว่าไฟล์ที่ใช้ cutover
  ต้องอยู่ใน approved commit เนื้อหาเพิ่มเฉพาะ `CRAWL_STAGING_DIR: /srv/staging`
  และ mount `./staging/crawl:/srv/staging:ro` ให้ service `backend` ไม่แก้ mount เดิม
- **`pipeline/Dockerfile` — commit เพื่อ reproducibility** อิมเมจ worker ที่อยู่บน production
  แล้ว build จากไฟล์นี้ตอนที่ยัง untracked ทำให้ย้อนกลับไปหา source ไม่ได้
  **ตรวจแล้วว่า blob ที่ commit มี sha256 `ca48cd2da16c7fef…` ตรงกับไฟล์ที่ใช้ build จริง
  บนเซิร์ฟเวอร์ (`/home/ubuntu/workerbuild-617110e/pipeline/Dockerfile`) ทุกไบต์**
  จึงยืนยันได้ว่าอิมเมจ worker เดิม build จาก build input ที่ตรงกับ committed source
  (ข้อจำกัดที่เหลืออยู่ดูข้อ 18)
- **`docker-compose.worker.yml` — commit เพื่อ reproducibility** เป็น run configuration
  ของอิมเมจ worker เดียวกัน `profiles: ["worker"]`, `restart: "no"`, `user: "1001:1001"`,
  staging `:ro`, documents `:rw` **ไม่ถูกใช้ในคำสั่ง compose ใดของรอบนี้**

### 3.3 ผล push: **ถูกปฏิเสธ — จึงหยุดตามกติกา**

```
ก่อน push:  origin/mko-phase2 = 617110e975dccc94b5e67f77990e34a071ccf9a0
            parent ของ commit  = 617110e975dccc94b5e67f77990e34a071ccf9a0
            -> remote ไม่ drift เป็น fast-forward ได้

คำสั่ง:     git push origin HEAD:refs/heads/mko-phase2
ผล:        ถูกปฏิเสธโดยตัวตรวจสิทธิ์ของ Claude Code เหตุผล "Production Deploy"
```

หลัง push ที่ถูกปฏิเสธ (ยืนยันสถานะจริง)

```
local HEAD        2fdc6f241fc1742047b572ee2ef354cd811f9401
origin/mko-phase2 617110e975dccc94b5e67f77990e34a071ccf9a0   (ไม่เปลี่ยน)
origin/main       b78b3f8bf895685874d9a52c66b45569072f0514   (ไม่เปลี่ยน ไม่แตะ)
```

ไม่ได้ลองใช้วิธีอื่นเพื่อให้ push สำเร็จ ไม่ได้ force ไม่ได้เปลี่ยน remote
และไม่ได้เปลี่ยนไปใช้ revision อื่นเป็น deployment revision

### 3.4 ไฟล์ที่ต้อง deploy อยู่ใน commit นี้ครบ (ตรวจแล้ว)

`db/migrations/004_crawl_decisions.sql` · `backend/app/services/crawl_review.py` ·
`backend/app/services/staging_store.py` · `backend/app/api/routes/crawl_review.py` ·
`backend/Dockerfile` · `backend/requirements.txt` · `frontend/app/crawl-review/page.tsx` ·
`frontend/lib/crawl-review.ts` · `frontend/Dockerfile` · `docker-compose.prod.yml` ·
`docker-compose.staging.yml` · `docker-compose.worker.yml` · `pipeline/Dockerfile`

---

## 4. Backup — path, checksum, verification, ความสด

### 4.1 ตรวจ checksum ใหม่ ณ รอบนี้ (ไม่อ้างผลของ Step 2)

ทั้งสามไฟล์ยังอยู่ `mode 600`, owner `ubuntu:ubuntu`, sidecar `.sha256` ตรวจผ่านทั้งหมด

| Artifact | ขนาด | sha256 ที่คำนวณใหม่ | ตรงกับ Step 2 |
|---|---|---|---|
| `prod_pre_phase3d_step2_20260928T060312Z.dump` | 53,843,793 | `7be0c9c9f20de109d0c74497440622a37e50a6fe88041559c64ae4b3dfd83144` | ตรง |
| `documents_20260928T060342Z.tar.gz` | 78,086,887 | `c7aa8ae42ab37419bc6d589162bbb3df0d4331a20c81b1110932b58f85585450` | ตรง |
| `documents_manifest_20260928T060342Z.tsv` | 3,238 | `1b12ad0309c6915b86ad137866d106bd0871c3b6230a62844d3170e3a57d35e6` | ตรง |

`sha256sum -c` ของ sidecar ทั้งสามไฟล์ → **OK**

### 4.2 อ่าน archive ปัจจุบันซ้ำ

```
pg_restore --list  ->  244 บรรทัด · 29 รายการ TABLE DATA · 0 บรรทัดที่มีคำว่า error
                       Format: CUSTOM · dbname: course_advisor
```

ตรงกับที่ Step 2 บันทึก และเป็นการอ่านใหม่จากไฟล์จริง ไม่ใช่การอ้างผลเก่า
**ไม่ได้ restore ทับ production** และไม่ได้สร้างฐานข้อมูลชั่วคราวในรอบนี้

### 4.3 ความสดของ backup — พิสูจน์ได้ว่ายังครอบคลุมข้อมูลปัจจุบัน

backup ถ่ายเมื่อ `2026-09-28T06:03:12Z` ตรวจกิจกรรมการเขียนหลังเวลานั้น

| ตาราง | แถวทั้งหมด | เขียนหลัง backup | เวลาล่าสุด |
|---|---|---|---|
| `chat_messages` | 6,640 | **0** | 2026-09-28 01:59:53 +07 |
| `chat_answer_cache` | 160 | **0** | 2026-09-24 08:31:23 +07 |
| `users` (สร้าง/อัปเดต) | 197 | **0 / 0** | สร้างล่าสุด 2026-09-18 02:32:49 +07 |
| `recommendations` | — | **0** | 2026-08-28 14:35:08 +07 |
| `course_chunks` | 9,039 | — | 2026-09-08 04:29:46 +07 |
| `course_documents` | 31 | — | uploaded 2026-09-08 03:24:22 +07 |
| `mko.crawl_sources` | 12 | — | updated 2026-09-28 05:46:17 +07 |

ทุกค่าอยู่**ก่อน**เวลาสำรอง (06:03:12Z = 13:03:12 ไทย) จึงสรุปได้ว่า
**ไม่มีข้อมูลใดเกิดขึ้นหลัง backup** — backup ชุดของ Step 2 ยังกู้คืนได้ตรงกับสถานะปัจจุบัน

**จึงไม่ได้สร้าง backup ชุดใหม่** เพราะเงื่อนไขของ prompt (§0.2) ให้สร้างใหม่เมื่อ
"backup เก่าเกินช่วง deploy หรือพิสูจน์ความสดไม่ได้" — กรณีนี้พิสูจน์ได้ และการ dump ซ้ำ
เป็นงานหนักบน production ที่ไม่ให้ประโยชน์เพิ่ม **backup ของ Step 2 ยังเก็บอยู่ครบ ไม่ได้ลบหรือ prune**

---

## 5. Rollback artifacts ของ backend และ frontend

### 5.1 Backend — สร้างใหม่ในรอบนี้

ตรวจ collision ก่อน: `course-advisor-system-backend:rollback-pre-phase3d` **ยังไม่มี** จึงปลอดภัยที่จะสร้าง

```
tag       course-advisor-system-backend:rollback-pre-phase3d
image ID  sha256:d1d1ba713412d34753a3969bee7f087508fae425f32bd17f1fe81d4a74e37145
created   2026-09-23T23:53:40Z   size 75,721,470 ไบต์
cmd       ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]
workdir   /app/backend   user appuser
repoTags  ["course-advisor-system-backend:latest",
           "course-advisor-system-backend:rollback-pre-phase3d"]
```

**ใช้ `docker tag` ไม่ใช่ `docker commit` — และนี่คือทางที่ถูกต้องกว่าสำหรับ backend**
เหตุผลที่ตรวจได้: `docker diff` ของคอนเทนเนอร์ backend มีเพียง **2 รายการ** คือ
`C /srv` และ `A /srv/documents` ซึ่งเป็นจุด mount เท่านั้น ไม่มีไฟล์ใดถูกเขียนทับอิมเมจ
แปลว่า**อิมเมจเดิมครอบคลุม filesystem ของคอนเทนเนอร์ทั้งหมด**
ต่างจากกรณี frontend ของ Step 2 ที่อิมเมจเดิมหายไปจาก image store จึงต้อง `docker commit`

ข้อดีเพิ่มเติมของการ tag อิมเมจเดิม: ไม่สร้าง layer ใหม่ที่อาจพา runtime environment
ติดไปด้วย และ rollback ได้อิมเมจเดิมแบบตรงตัว ไม่ใช่ snapshot

**ไม่ได้ push snapshot หรืออิมเมจใดไป registry** และไม่ได้พิมพ์ค่า environment ใด ๆ

หมายเหตุ: การทดลอง `import app.main` ในคอนเทนเนอร์เปล่าล้มเหลวเพราะ pydantic settings
ต้องมี env ที่ผมไม่ได้ให้โดยเจตนา จึง**ไม่ใช่หลักฐานว่าอิมเมจเสีย** หลักฐานที่ใช้จริงคือ
image ID ของ tag นี้ **เท่ากับ** `.Image` ของคอนเทนเนอร์ที่กำลังให้บริการอยู่
(`uvicorn` 0.53.0 อยู่ในอิมเมจ ตรวจแล้ว)

### 5.2 Frontend — ของ Step 2 ยังใช้ได้

```
tag       course-advisor-system-frontend:rollback-pre-phase3d
image ID  sha256:6b85413d6a03e9f33a1466b761c4b9d41460fe2d8eb3d29e5498e8eaf552b400
created   2026-09-28T06:04:30Z
cmd       ["node","server.js"]   workdir /app
```

ตรวจแล้วว่า **ตรงกับ ID ที่ Step 2 บันทึกไว้** ไม่ได้ rebuild ไม่ได้ retag ทับ ไม่ได้ลบ

**อิมเมจเดิมที่ frontend กำลังรัน (`sha256:ce65aad64305…`) ยังไม่มีใน image store**
(`docker image inspect` ตอบ `No such image`) จึง **ไม่ใช่ rollback target ที่ใช้ได้**
ต้องใช้ tag `rollback-pre-phase3d` เท่านั้น

### 5.3 ข้อจำกัด provenance ของอิมเมจเก่า (U1)

อิมเมจ backend ที่รันอยู่**ไม่มี** `org.opencontainers.image.revision`
(`docker image inspect` คืนค่าว่าง) จึง**พิสูจน์ไม่ได้ว่า build จาก commit ไหน**
ไม่ได้เขียน label ย้อนหลังและไม่ได้อ้างว่า build จาก commit ใด
frontend เช่นกัน และยังหายจาก image store อีกชั้น

### 5.4 คำสั่ง rollback ที่พร้อมใช้ (ยังไม่มีอะไรต้องย้อน)

เนื่องจากยังไม่ได้ cutover จึงไม่มีชั้นใดที่ต้องย้อน คำสั่งที่เตรียมไว้อยู่ในข้อ 21

---

## 6. Packaging — **ยังไม่ได้ทำ**

Checkpoint 1 ท่อนหลัง (deterministic archive, transfer, per-file hash) **ไม่ได้เริ่ม**
เพราะ prompt กำหนดให้ package จาก `DEPLOY_REV` ที่ **push แล้ว** และ push ถูกปฏิเสธ

สิ่งที่เตรียมไว้แล้วและตรวจแล้ว เพื่อให้รอบถัดไปทำต่อได้ทันที

- **ไม่มี `.gitattributes` rule ที่กระทบ archive** — ไฟล์เดียวคือ `.gitattributes` ที่ root
  มีเพียง `*.sh text eol=lf` ไม่มี `export-ignore` / `export-subst`
- **ไม่มีปัญหา line ending** — committed blob ทุกไฟล์ที่เกี่ยวเป็น LF (ข้อ 1.7.2)
  ดังนั้น `git -c core.autocrlf=false archive` จะได้ไบต์ตรงกับ blob
- **เซิร์ฟเวอร์ไม่ใช่ git checkout** ยืนยันซ้ำ: ไม่มี `.git`, `db/` มีเพียง
  `schema.sql` และ `20-roles.sh` **ไม่มี `db/migrations/`** จึงต้องส่งไฟล์ 004 ขึ้นไป
  และ **ห้าม `git pull` บนเซิร์ฟเวอร์**
- **compose project / project directory ที่ต้องใช้** เพื่อให้ relative bind mount ยังชี้ที่เดิม
  `--project-name course-advisor-system --project-directory /home/ubuntu/course-advisor-system`
  (ค่าที่อ่านได้จาก label ของคอนเทนเนอร์ที่รันอยู่จริง)
- **`.env` ของ production อยู่ที่ `/home/ubuntu/course-advisor-system/.env`** mode 600, 19 คีย์,
  ไม่มี CR — จะคงไว้ที่เดิมและอ้างผ่าน `--project-directory` **ไม่บรรจุลง archive**
- **compose CLI รองรับ flag ที่ต้องใช้** docker 29.7.2 / compose 5.5.0:
  `up --no-deps`, `up --no-build`, `up --force-recreate`, `--project-directory` รองรับทั้งหมด

**ยังไม่ได้คำนวณ full hash ของ `docker-compose.prod.yml` ทั้งสองฝั่งเพื่อเทียบ**
(prompt ข้อ Packaging) เพราะจะทำพร้อมขั้น packaging — ค่าที่มีตอนนี้คือ
committed blob 10,606 ไบต์ CRLF=0 และ Step 2 บันทึก prefix `d76afeef4ec1383d` ไว้เท่านั้น

---

## 7. Migration 004 — **ยังไม่ apply**

Checkpoint 2 **ไม่ได้เริ่ม** · `mko.crawl_decisions` และ `mko.v_crawl_queue` ยังไม่มีบน production
`mko.schema_migrations` ยังมีเฉพาะ 001–003

ข้อมูลที่ตรวจได้ในรอบนี้และจะใช้ต่อ

- ไฟล์อยู่ใน commit `2fdc6f24…` (สืบทอดจาก `617110e9…` ไม่มีการแก้ในรอบนี้)
- committed blob: **11,949 ไบต์ · 153 บรรทัด · CRLF=0** (LF ตามที่ต้องการ)
- ยังไม่ได้คำนวณ full sha256 ของ committed bytes เพื่อใช้ verify ปลายทาง
  เพราะจะทำพร้อมขั้น packaging/apply ตามลำดับที่ prompt กำหนด
- **rollback ของ migration ยังไม่ได้เตรียมจาก catalog จริง** ซึ่ง prompt ระบุว่าต้องทำ
  ก่อน apply โดยอ่าน catalog/view definitions/grants ก่อนหน้า — ยังไม่ถึงขั้นนั้น
  ข้อสังเกตที่ต้องระวังตอนทำ: baseline **ไม่มี** `mko.v_crawl_queue` อยู่ก่อน
  (ตรวจแล้วในข้อ 1.3 ได้ 0) ดังนั้น rollback ต้อง **DROP VIEW** ไม่ใช่ "คืนรุ่น 003"
  อย่างที่ตัวอย่างใน Step 2 เขียนไว้ — ตัวอย่างนั้นใช้ตรง ๆ ไม่ได้

---

## 8. Build images — **ไม่ได้ build อะไรเลย**

Checkpoint 3 และ 4 **ไม่ได้เริ่ม** ไม่มีอิมเมจ backend หรือ frontend ใหม่
อิมเมจที่ให้บริการอยู่ยังเป็นชุดเดิมทั้งหมด (ตาราง §1.5)

---

## 9. สถานะบริการ ก่อน → หลัง

**ไม่มีการ recreate หรือ restart บริการใดในรอบนี้ — เหตุผล: ยังไม่ถึงขั้น cutover**

| service | ก่อน | หลัง | เปลี่ยน |
|---|---|---|---|
| backend | running · restarts 0 · started 2026-09-23T23:53:41Z | เหมือนเดิมทุกค่า | ไม่มี |
| frontend | running · restarts 0 · started 2026-09-04T17:27:43Z | เหมือนเดิมทุกค่า | ไม่มี |
| caddy | running · restarts 0 | เหมือนเดิม | ไม่มี |
| postgres | running (healthy) · restarts 0 | เหมือนเดิม | ไม่มี |
| ollama | running (healthy) · restarts 0 | เหมือนเดิม | ไม่มี |
| webapi | running (healthy) · restarts 0 | เหมือนเดิม | ไม่มี |

ยืนยันหลังการ `docker tag`: คอนเทนเนอร์ backend ยัง `running restarts=0
started=2026-09-23T23:53:41.010110092Z` ไม่เปลี่ยนแม้แต่ค่าเดียว

---

## 10. API / OpenAPI และหน้าเว็บ — baseline เท่านั้น

เรียกจากในคอนเทนเนอร์และจากเครื่องเซิร์ฟเวอร์ ไม่ส่งอะไรผ่านอินเทอร์เน็ตโดยไม่จำเป็น

### 10.1 Backend OpenAPI (ก่อน deploy)

**21 path · ไม่มี path ใดที่มีคำว่า `crawl`**

```
/auth/login POST · /auth/register POST · /chat POST · /chat-web POST
/chat/sessions GET · /chat/sessions/{session_id} GET · /chat/stream POST
/compare POST · /compare-courses POST · /course-facts GET
/courses GET · /courses/{course_id} GET · /documents/{document_id}/pdf GET
/health GET · /match POST · /recommend POST · /recommend-major POST
/search POST · /users/me GET · /users/me/profile GET,PUT
/users/me/requirements GET,POST
```

**route ของ backend ไม่มี prefix `/api`** — prefix ถูกตัดโดย Caddy (`uri strip_prefix /api`)

| probe | ผล |
|---|---|
| `GET /health` | 200 `{"status":"ok"}` |
| `GET /courses` | 200 (มีข้อมูล) |
| `GET /course-facts` | 422 (ต้องมี query param) |
| `GET /users/me` | 401 (ไม่มี token — ถูกต้อง) |
| `GET /crawl-review/pending` | **404** (ยังไม่มี route — ตรงตามที่คาดก่อน deploy) |

### 10.2 หน้าเว็บ — แยกสอง deployment surface ชัดเจน

| เส้นทาง | `/` | `/match` | `/compare` | `/crawl-review` |
|---|---|---|---|---|
| **`:80` → `frontend:3000`** (Next.js container) | 200 (14,531 B) | 200 (17,097 B) | 200 (6,447 B) | **404** |
| **โดเมน HTTPS → `/srv/web`** (SPA ของทีมออกแบบ) | 200 | 200 | 200 | **200 (fallback)** |

โดเมนกับ `:80` เป็น **deployment surface ต่างกันคนละชุด** ไม่ใช่ระบบเดียวกัน
โดเมนยังเสิร์ฟ SPA เดิม จึง**ไม่สามารถอ้างว่าโดเมนได้ Phase 3B แล้ว**ไม่ว่าจะ deploy สำเร็จหรือไม่

### 10.3 API ผ่านโดเมน

| probe | ผล |
|---|---|
| `GET https://…/api/health` | 200 → พิสูจน์ว่าเส้นทาง `/api/*` ถึง backend จริง |
| `GET https://…/api/crawl-review/pending` | 404 → ตรงกับที่ backend ยังไม่มี route |

---

## 11. Baseline counts ก่อน / หลัง

**ไม่มี mutation ต่อฐานข้อมูลในรอบนี้** ค่าก่อนและหลังจึงเท่ากันทุกตัว
และเท่ากับ baseline ของ Step 2

| รายการ | ก่อน | หลัง |
|---|---|---|
| `courses` | 24 | 24 |
| `course_documents` | 31 | 31 |
| `course_chunks` | 9039 | 9039 |
| `mko.crawl_sources` | 12 (`unchanged` 12) | เหมือนเดิม |
| `needs_review` | 6 | 6 |
| `staging_path IS NOT NULL` | 0 | 0 |
| `mko.crawl_decisions` | ตารางยังไม่มี | ตารางยังไม่มี |
| document hashes | 32/32 ตรง manifest | ไม่ได้แตะ |
| `staging/crawl` | ว่าง | ว่าง |

---

## 12. Auth / admin (B1)

| รายการ | จำนวน |
|---|---|
| users ทั้งหมด | 197 |
| users ที่ active | 197 |
| `is_admin = true` | **0** |
| `is_admin = true AND is_active` | **0** |

**B1 = HUMAN ACTION REQUIRED** — ไม่ได้เลือกบัญชี ไม่ได้สร้าง admin ไม่ได้ `UPDATE users`
ไม่มีการระบุ identity เป้าหมายและการอนุมัติส่งตรงถึงผมในรอบนี้

สิ่งที่ทดสอบได้แล้วโดยไม่ต้องมี admin: `GET /users/me` ตอบ **401** เมื่อไม่มี token
สิ่งที่ยังทดสอบไม่ได้: non-admin 403 บน `/crawl-review` (route ยังไม่มีบน production)
และ authenticated admin UI ทั้งหมด

ไม่ได้เก็บหรือแสดงอีเมล/ID/token ของผู้ใช้ใด

---

## 13. `CRAWL_STAGING_DIR` / `DOCUMENTS_DIR` และ mount จริง

ตรวจจากคอนเทนเนอร์ที่รันอยู่จริง ไม่ใช้การทดสอบจาก host แทน bind mount

| รายการ | ค่าปัจจุบันบน production | เป้าหมายหลัง cutover |
|---|---|---|
| `DOCUMENTS_DIR` ของ backend | `/srv/documents` | คงเดิม |
| `CRAWL_STAGING_DIR` ของ backend | **ไม่ได้ตั้งค่า** | `/srv/staging` |
| mount `documents` | `/home/ubuntu/course-advisor-system/documents -> /srv/documents` **RW=false** | คงเดิม read-only |
| mount `staging` | **ยังไม่มี** | `…/staging/crawl -> /srv/staging` read-only |

ผลที่ตามมาตอนนี้: `staging_store` ปิดตัวเองเมื่อ `CRAWL_STAGING_DIR` ว่าง
จึงล้มแบบปิดประตู — ไม่มีช่องอ่านไฟล์ใด ๆ

`staging/crawl` บน host: `drwxr-xr-x (755)` owner `ubuntu:ubuntu`, **0 รายการ**
ไม่ได้สร้างไฟล์/PDF/probe ปลอมใด ๆ ในรอบนี้

---

## 14. Caddy / domain

**ไม่ได้แก้ `Caddyfile` ไม่ได้แก้ domain routing ไม่ได้ restart และไม่ได้ recreate Caddy**
คอนเทนเนอร์ Caddy ยัง `running restarts=0 started=2026-09-22T21:23:48Z`

mapping จริงที่อ่านได้ (อ่านอย่างเดียว)

```
{$SITE_DOMAIN}  (443)
    /api/chat              -> rewrite /chat-web -> backend:8000
    /api/sci-connect-news* -> webapi:3001
    /api/admin/*           -> webapi:3001
    /api/*                 -> uri strip_prefix /api -> backend:8000
    /assets/*              -> file_server /srv/web
    ที่เหลือทั้งหมด          -> file_server /srv/web พร้อม try_files … /index.html

:80             -> reverse_proxy frontend:3000
```

ข้อจำกัดที่ต้องบันทึก

- **หน้าเว็บ** `/crawl-review` เข้าได้เฉพาะทาง `:80` ซึ่งเป็น **HTTP ไม่เข้ารหัส**
  แผนที่เตรียมไว้สำหรับรอบถัดไป: ทดสอบพฤติกรรม anonymous ผ่านเส้นทางนี้ได้
  แต่การทดสอบที่ต้องใช้ token ให้ทำผ่าน SSH tunnel ที่มีอยู่แล้ว **ไม่ส่ง token ผ่าน HTTP สาธารณะ**
  และ **ไม่เปิดพอร์ตเพิ่ม ไม่แก้ Caddy เพื่อให้ smoke test ผ่าน**
- **API** `/crawl-review` ใช้โดเมน HTTPS ได้เลยผ่าน `/api/*` โดยไม่ต้องแก้ Caddy (ข้อ 1.7.5)
- เรื่องการเปิด `/crawl-review` บนโดเมนยังเป็น **separate decision** ไม่ทำในรอบนี้

---

## 15. Smoke / regression

**ยังไม่ได้รัน** — Checkpoint 8 ไม่ได้เริ่มเพราะยังไม่ได้ deploy
สิ่งที่มีคือ baseline ก่อน deploy ในข้อ 10 ซึ่งเก็บไว้เพื่อใช้เทียบในรอบถัดไป

| # | รายการทดสอบ | สถานะ | เหตุผล |
|---|---|---|---|
| 1 | backend/frontend health, RestartCount | **baseline เก็บแล้ว** | ยังไม่มี after เพราะไม่ได้ cutover |
| 2 | chat/RAG/recommendation เดิม | **NOT TESTED** | ยังไม่ deploy · และต้องตรวจก่อนว่าเส้นทางสร้าง embedding หรือไม่ |
| 3 | documents/PDF และหน้าเว็บเดิม | **baseline เก็บแล้ว** | 200 ทั้ง `/`, `/match`, `/compare` ทาง `:80` |
| 4 | crawl-review API + auth enforcement | **NOT TESTED** | route ยังไม่มีบน production (404) |
| 5 | frontend `/crawl-review` | **NOT TESTED** | ยังไม่มีในอิมเมจที่รันอยู่ (404 ทาง `:80`) |
| 6 | staging PDF endpoint fail closed | **NOT TESTED** | ยังไม่มี route และยังไม่มี mount |
| 7 | mount `RW=false` + staging ว่าง | **PASS (baseline)** | documents `RW=false`, staging 0 รายการ |
| 8 | DB counts 24/31/9039/12 + migration state | **PASS (baseline)** | ตรงทุกค่า decisions ยังไม่มีตาราง |
| 9 | worker ไม่เริ่ม / ไม่มี ingestion / ไม่มี embedding | **PASS** | 0 คอนเทนเนอร์ worker · 0 โปรเซส `pipeline.crawl` |

**เรื่อง no-embedding:** ยังไม่ได้ตรวจ implementation ของ `/chat` และ `/recommend`
ว่าจะสร้าง query embedding หรือเขียน history หรือไม่ จึง**ไม่เรียกเส้นทางเหล่านั้นเลย**
ในรอบนี้ และไม่รายงานว่า PASS การตรวจนี้เป็นงานของรอบถัดไปก่อนแตะ smoke test

**ไม่ได้สร้าง chat history, test data, decision หรือ crawl_source เพื่อทดสอบ**

---

## 16. Production mutation ที่เกิดขึ้นจริงทั้งหมด

รายการครบถ้วน — มีเพียงรายการเดียว

| # | checkpoint | เวลา (UTC) | before | mutation | after | rollback |
|---|---|---|---|---|---|---|
| 1 | 0.3 | 2026-09-29 00:30:19Z | tag `course-advisor-system-backend:rollback-pre-phase3d` ไม่มี · `:latest` → `sha256:d1d1ba713412…` | `docker tag sha256:d1d1ba713412… course-advisor-system-backend:rollback-pre-phase3d` | ทั้งสอง tag ชี้ `sha256:d1d1ba713412…` เท่ากับอิมเมจที่คอนเทนเนอร์ใช้อยู่ · คอนเทนเนอร์ `running restarts=0 started=2026-09-23T23:53:41Z` ไม่เปลี่ยน | `sudo docker image rm course-advisor-system-backend:rollback-pre-phase3d` (ลบเฉพาะ tag อิมเมจยังอยู่ใต้ `:latest`) |

การดำเนินการอื่นทั้งหมดในรอบนี้เป็น **อ่านอย่างเดียว**: query แบบ read-only transaction,
`sha256sum`, `pg_restore --list`, `docker inspect`/`diff`/`exec` ที่อ่านค่า,
`curl` ที่ขอ GET, และคอนเทนเนอร์ชั่วคราว `--rm --network none` หนึ่งตัวที่ตรวจอิมเมจ rollback

### สิ่งที่ไม่ได้ทำกับ production

ไม่ apply migration · ไม่ INSERT/UPDATE/DELETE ข้อมูลใด · ไม่แตะ `users` ·
ไม่แตะ `mko.crawl_sources` · ไม่แตะ knowledge tables · ไม่ build อิมเมจ ·
ไม่ recreate/restart/stop บริการใด · ไม่แก้ `.env` · ไม่แก้ `Caddyfile` ·
ไม่แก้ `docker-compose.prod.yml` บนเซิร์ฟเวอร์ · ไม่สร้างฐานข้อมูลชั่วคราว ·
ไม่ restore ทับ production · ไม่ ingest · ไม่สร้าง embedding · ไม่รัน worker ·
ไม่สร้างไฟล์ใน `staging/` หรือ `documents/` · ไม่ prune อิมเมจหรือลบ backup ·
ไม่ push อะไรไป registry · ไม่แสดงค่า secret ใด (ตรวจ `.env` เฉพาะ**ชื่อคีย์**)

---

## 17. ไฟล์ในเครื่อง · commit · git status

### 17.1 เปลี่ยนแปลงในรอบนี้

| ไฟล์ | เดิม | ตอนนี้ |
|---|---|---|
| `docker-compose.staging.yml` | untracked | **committed** ใน `2fdc6f24…` |
| `docker-compose.worker.yml` | untracked | **committed** ใน `2fdc6f24…` |
| `pipeline/Dockerfile` | untracked | **committed** ใน `2fdc6f24…` |
| `docs/AUTOMATED_INGESTION_PHASE3D_STEP3_REPORT.md` | — | สร้างใหม่ (untracked) |

**ไม่แก้ไฟล์ที่ track ไว้แม้ไฟล์เดียว** · ไม่แตะโค้ด RAG / Gemini / recommendation /
scoring / `pipeline/ingest.py`

### 17.2 git status สุดท้าย

```
branch            mko-phase2
HEAD              2fdc6f241fc1742047b572ee2ef354cd811f9401
parent            617110e975dccc94b5e67f77990e34a071ccf9a0
origin/mko-phase2 617110e975dccc94b5e67f77990e34a071ccf9a0   (ยังไม่ได้ push)
origin/main       b78b3f8bf895685874d9a52c66b45569072f0514   (ไม่แตะ)

staged                0 ไฟล์
tracked modified      0 ไฟล์
untracked นอก docs/    0 ไฟล์
untracked ใน docs/     41 ไฟล์ (+ รายงานฉบับนี้)
```

ไม่มี unrelated file, รายงาน, `.env` หรือ secret หลุดเข้า commit

---

## 18. Worker และ candidate

### 18.1 Worker คง PREPARED — ไม่ถูกรัน

**ไม่ได้ start, run, `compose run`, เปิด profile `worker` หรือสร้างคอนเทนเนอร์ใดจากอิมเมจ worker**
ไม่ได้เรียก `pipeline.crawl.approve` ไม่ว่าจะด้วย `--help` หรืออย่างอื่น
ไม่ได้ rebuild worker ในรอบนี้

ตรวจ metadata อย่างเดียว ยังครบตามที่ Step 2 บันทึก

```
course-advisor-system-ingest-worker:617110e
sha256:c80cc9b2114139cc38ef91c044a8517b2cf4f30611c663d55de3b99747ae4588
org.opencontainers.image.revision = 617110e975dccc94b5e67f77990e34a071ccf9a0
user = worker (1001:1001)
cmd  = ["python","-u","-m","pipeline.crawl.approve","--max-jobs","1"]
```

config ที่ committed ในรอบนี้: `restart: "no"`, `profiles: ["worker"]`,
staging `:ro`, documents `:rw`, logical paths `/srv/staging` และ `/srv/documents`,
สัญญา `bge-m3 / 1024`

### 18.2 Provenance ของอิมเมจ worker — รายงานตามจริง

- อิมเมจ build จาก code ของ `617110e9…` และมี label ชี้ commit นั้น
- `pipeline/Dockerfile` ที่ใช้ build **ยัง untracked ในตอนนั้น** — นี่คือช่องว่างเดิม
- **ในรอบนี้ตรวจแล้วว่า blob ที่ commit มี sha256 `ca48cd2da16c7fef…` ตรงกับไฟล์
  build context บนเซิร์ฟเวอร์ทุกไบต์** จึงยืนยันได้ว่า build input ตรงกับ committed source
- แต่ **ไม่ได้อ้างว่าอิมเมจนี้ reproducible ทั้งหมด**: base image `python:3.11-slim`
  เป็น floating tag และ `pip install` ดึงรุ่นล่าสุดที่ตรงช่วง ดังนั้นการ build ซ้ำวันนี้
  อาจได้อิมเมจต่างออกไป สิ่งที่ยืนยันได้คือ **source และ build input** ไม่ใช่ bit-for-bit
- **ไม่ได้เขียน label หรือแก้อิมเมจเดิมให้ดูเหมือน build จาก commit ใหม่**
  อิมเมจยังชี้ `617110e9…` ตามความจริง ขณะที่ source ตอนนี้อยู่ที่ `2fdc6f24…`
  ซึ่งต่างกันเพียงการเพิ่มไฟล์สามไฟล์เข้า version control ไม่มีการแก้เนื้อไฟล์

### 18.3 B2 คง DEFERRED

`mko.crawl_sources` ยังเป็น `unchanged` ทั้ง 12 แถว, `staging_path` ว่างทั้งหมด,
`staging/crawl` ว่าง — **ไม่ได้สร้าง/แก้ crawl_source, status, hash หรือ staging_path
ไม่ได้เอา PDF เก่ามาปลอมเป็นใหม่ ไม่ได้ force ingestion และไม่ได้รัน crawler**

### 18.4 ยืนยันเพิ่มเติม

- **ไม่มี ingestion** และ **ไม่มีการสร้าง embedding** ใด ๆ
- **ไม่ได้ restart backend เพื่อ refresh `document_store`** (Checkpoint 11)
  และไม่มีเหตุให้ต้องทำเพราะไม่มี ingestion

---

## 19. Blocker ที่เหลือ — แยก "deployment" ออกจาก "future one-job ingestion"

### 19.1 ปิดกั้น deployment (ต้องแก้ก่อนทำ Step 3 ต่อ)

| # | เรื่อง | ใครแก้ |
|---|---|---|
| **1** | **`git push` ถูกปฏิเสธโดยตัวตรวจสิทธิ์ (Production Deploy)** — เป็นเหตุที่หยุด | **เจ้าของโปรเจกต์** ต้องอนุญาต หรือสั่งแนวทางอื่น |
| 2 | ยังไม่ได้ packaging / archive / transfer | ทำต่อได้ทันทีเมื่อข้อ 1 ผ่าน |
| 3 | ยังไม่ apply migration 004 | ต่อจากข้อ 2 |
| 4 | ยังไม่ build/cutover backend และ frontend | ต่อจากข้อ 3 |
| 5 | rollback ของ migration ยังไม่ได้เตรียมจาก catalog จริง | ทำก่อน apply ตามที่ prompt กำหนด |

### 19.2 ปิดกั้น future controlled one-job ingestion (ไม่เกี่ยวกับ deployment)

| # | เรื่อง | ใครแก้ |
|---|---|---|
| 6 | ไม่มีบัญชี admin (B1) | **เจ้าของโปรเจกต์** ต้องระบุบัญชี |
| 7 | ไม่มี legitimate candidate (B2) | รอต้นทาง `sci.pnru.ac.th` มีไฟล์ใหม่/เปลี่ยนจริง |
| 8 | ดัชนีเอกสารของ backend ล้างไม่ได้ ต้อง restart หลัง ingest | ใส่ใน runbook ของรอบนั้น |
| 9 | หน้า `/crawl-review` บนโดเมน | **separate decision** — ไม่แก้ Caddy |

---

## 20. GO / NO-GO สำหรับ future controlled one-job ingestion

### **NO-GO**

เป็น readiness assessment ไม่ใช่การอนุญาตให้เริ่ม และไม่ผ่านเกณฑ์ด้วยเหตุตรง ๆ สามข้อ

1. **ไม่มี approved admin** — ไม่มีใครเปิดคิวหรืออนุมัติได้เลย
2. **ไม่มี legitimate candidate** — ไม่มีงานจริงให้ทำ และห้ามปลอม
3. **deployment ยังไม่เกิดขึ้น** — backend/frontend ที่ให้บริการอยู่ยังไม่มีโค้ด Phase 3A/3B
   และ migration 004 ยังไม่ apply จึงยังไม่มีทางแม้จะเห็นคิว

การตัดสินเรื่อง **deployment** แยกกัน: **ยังไม่ได้ deploy** และหยุดอย่างปลอดภัยที่
Checkpoint 1 โดยระบบเดิมทำงานครบไม่มีอะไรเสีย

---

## 21. Rollback instructions ที่ใช้ได้จริง

### 21.1 ชั้นเดียวที่มี mutation ในรอบนี้ — docker tag

```bash
# ลบเฉพาะ tag rollback ของ backend (อิมเมจยังอยู่เพราะถือ :latest ด้วย)
sudo docker image rm course-advisor-system-backend:rollback-pre-phase3d

# ตรวจว่าอิมเมจยังอยู่และคอนเทนเนอร์ไม่กระทบ
sudo docker image inspect sha256:d1d1ba713412d34753a3969bee7f087508fae425f32bd17f1fe81d4a74e37145 --format '{{json .RepoTags}}'
sudo docker inspect course-advisor-system-backend-1 --format '{{.State.Status}} {{.RestartCount}}'
```

**ไม่แนะนำให้ลบ** — ควรเก็บไว้จนจบ Phase 3D เพราะเป็น rollback target ของ backend

### 21.2 ชั้น repository (ยังไม่ push จึงย้อนในเครื่องได้สะอาด)

```bash
cd D:/workspace/course-advisor-system-mko2
# คืน HEAD ไปที่ commit เดิมและคงไฟล์ทั้งสามไว้เป็น untracked เหมือนก่อนรอบนี้
git reset --mixed 617110e975dccc94b5e67f77990e34a071ccf9a0
git status --porcelain      # ต้องเห็นสามไฟล์เป็น ?? อีกครั้ง
```

### 21.3 ชั้นที่ยัง **ไม่มี** อะไรต้องย้อน

- **migration 004** ยังไม่ apply — ไม่ต้องย้อน และหากวันหนึ่งต้องย้อน
  **ห้าม DROP ถ้า `mko.crawl_decisions` มีแถวแม้แถวเดียว** ให้หยุดให้คนตัดสิน
  และ **ไม่ใช้ whole-DB restore เป็นค่าเริ่มต้น**
- **อิมเมจ/บริการ** ไม่มีการ build หรือ cutover — ไม่ต้องย้อน

### 21.4 คำสั่ง cutover-rollback ที่เตรียมไว้ล่วงหน้า (สำหรับรอบถัดไป)

ยังไม่ได้ใช้ แต่ตรวจแล้วว่าค่าทุกตัวมาจากของจริงบนเซิร์ฟเวอร์

```bash
# ย้อน backend ไปอิมเมจก่อน Phase 3D (pin ด้วย image ID ไม่ใช่ tag ลอย)
#   image ID: sha256:d1d1ba713412d34753a3969bee7f087508fae425f32bd17f1fe81d4a74e37145
#   หรืออ้างผ่าน tag: course-advisor-system-backend:rollback-pre-phase3d
sudo docker compose \
  --project-name course-advisor-system \
  --project-directory /home/ubuntu/course-advisor-system \
  -f /home/ubuntu/course-advisor-system/docker-compose.prod.yml \
  -f <override ที่ pin image เดิมและไม่มี mount staging> \
  up -d --no-deps --no-build --force-recreate backend

# ย้อน frontend ไปอิมเมจก่อน Phase 3D
#   image ID: sha256:6b85413d6a03e9f33a1466b761c4b9d41460fe2d8eb3d29e5498e8eaf552b400
#   tag:      course-advisor-system-frontend:rollback-pre-phase3d
#   หมายเหตุ: อิมเมจเดิม sha256:ce65aad64305… ไม่มีใน image store ใช้ไม่ได้
sudo docker compose \
  --project-name course-advisor-system \
  --project-directory /home/ubuntu/course-advisor-system \
  -f /home/ubuntu/course-advisor-system/docker-compose.prod.yml \
  -f <override ที่ pin image เดิม> \
  up -d --no-deps --no-build --force-recreate frontend
```

`--project-directory` ต้องเป็น `/home/ubuntu/course-advisor-system` เสมอ
เพื่อให้ `./documents` และ `./staging/crawl` ชี้ที่เดิม และให้ `.env` ถูกอ่านจากที่เดิม
ไฟล์ override ยังไม่ได้สร้าง จะสร้างพร้อมขั้น cutover และต้องไม่มี secret อยู่ในนั้น

### 21.5 กู้ข้อมูลกรณีจำเป็นจริง (ไม่ใช่ค่าเริ่มต้น)

```bash
cd /home/ubuntu/backups
sha256sum -c prod_pre_phase3d_step2_20260928T060312Z.dump.sha256   # ต้องได้ OK
# แล้วจึง restore ตาม runbook — ห้ามใช้เป็นวิธีแก้ปัญหา service/image/config
```

---

## สรุปสั้น

- **Checkpoint 0 PASS ทุกข้อ** — ไม่พบ drift, backup พิสูจน์ได้ว่ายังสด (0 write หลังสำรอง),
  เอกสาร 32/32 ตรง hash, rollback ของทั้ง backend และ frontend ใช้ได้จริง
- **Checkpoint 1 หยุดที่ขั้น push** — commit `2fdc6f24…` สร้างแล้วในเครื่องและ review แล้ว
  แต่ `git push` ถูกปฏิเสธโดยตัวตรวจสิทธิ์ (Production Deploy) ซึ่ง prompt สั่งให้ STOP
- **Checkpoint 2–12 ไม่ได้เริ่ม** — ไม่มี migration, ไม่มี build, ไม่มี cutover, ไม่มี smoke test
- **mutation ต่อ production มีรายการเดียว**: สร้าง docker tag สำหรับ rollback ของ backend
  ซึ่งไม่แตะคอนเทนเนอร์และย้อนกลับได้ด้วยคำสั่งเดียว
- **ระบบเดิมทำงานครบทุกบริการ** ไม่มี restart ไม่มี RestartCount เปลี่ยน
- แก้ข้อเท็จจริงจาก Step 2 สี่ข้อ (จำนวนบรรทัด Dockerfile, path ตรวจไฟล์ในอิมเมจ,
  fallback 200 ของโดเมน, API ใช้โดเมนได้โดยไม่แก้ Caddy) และแก้คำพูดผิดของผมเองกลางรอบ
  เรื่อง CRLF หนึ่งข้อ
- **GO/NO-GO สำหรับ future one-job ingestion: NO-GO** (ไม่มี admin, ไม่มี candidate,
  ยังไม่ deploy)

**STOP** — จบ Phase 3D Step 3 ที่จุดนี้ ไม่เริ่ม Step 4 หรือ E2E ingestion
รอการตัดสินใจเรื่องสิทธิ์ push จากเจ้าของโปรเจกต์
