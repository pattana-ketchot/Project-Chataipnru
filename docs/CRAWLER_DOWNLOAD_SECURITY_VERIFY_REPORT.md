# Crawler Download Security Hardening — ผลการตรวจสอบ

| | |
|---|---|
| วันที่ | 28 กันยายน 2569 |
| commit | `a0655ef3bd7ddd4d71d6ede59f9cab8d6d027c87` (`a0655ef`) |
| branch | `mko-phase2` — push แล้ว ตรงกับ `origin/mko-phase2` |
| อ้างอิง | [CRAWLER_DOWNLOAD_SECURITY_REPORT.md](docs/CRAWLER_DOWNLOAD_SECURITY_REPORT.md) |
| สถานะ | **เทสต์ครบ · commit แล้ว · push แล้ว · production crawler check ยังทำไม่ได้ — ติดรหัสผ่าน** |

---

## สรุปเป็นข้อ

| # | งาน | ผล |
|---|---|---|
| 1 | รัน `eval/crawl_state_check.py` กับฐานข้อมูลทดสอบที่มี migration 003 | ✅ **32/32 ผ่าน** |
| 2 | ห้ามรันกับ `course_advisor` | ✅ รันกับ `crawl_test` เท่านั้น |
| 3 | Phase 2 database-backed regression ผ่านครบ รวม 4e–4h | ✅ ผ่านครบ |
| 4 | ถ้า fail ให้หยุด | ไม่มีข้อใด fail |
| 5 | ตรวจ `git diff` / `git status` — เฉพาะ 5 ไฟล์ | ✅ 5 ไฟล์พอดี |
| 6 | commit แบบ path-specific ไม่ใช้ `git add .` | ✅ |
| 7 | push `mko-phase2` → `origin/mko-phase2` ไม่ merge main | ✅ |
| 8 | ยืนยัน HEAD ตรงกัน · ahead 0 / behind 0 · ไม่มี tracked ค้าง | ✅ |
| 9 | **รัน production crawler 1 รอบ** | ❌ **ทำไม่ได้ — รหัสผ่าน `advisor_ingest` ในเครื่องนี้ใช้กับ production ไม่ได้** |
| 10 | ยืนยันตัวเลข production ไม่เปลี่ยน | ✅ อ่านแบบอ่านอย่างเดียว — ตรงกับ baseline ทุกตัว |

---

## 1. `eval/crawl_state_check.py` — 32/32 ผ่าน

### วิธีเตรียมฐานข้อมูลทดสอบ

เครื่องพัฒนาไม่มีทั้ง PostgreSQL และ Docker จึงใช้วิธีเดียวกับที่ทดสอบ migration 003
ตอน Phase 2 คือสร้างฐานข้อมูล **แยกคนละฐาน** ในคอนเทนเนอร์ของเซิร์ฟเวอร์ แล้วลบทิ้ง

```
1. CREATE ROLE crawl_test_runner  (รหัสผ่านสุ่มใหม่ ใช้ครั้งเดียว)
2. CREATE DATABASE crawl_test OWNER crawl_test_runner
3. โหลด bootstrap_test.sql (โครงขั้นต่ำที่ 003 ต้องพึ่ง) + db/migrations/003_crawl_sources.sql
4. เปิดอุโมงค์ SSH 127.0.0.1:55432 -> 172.18.0.2:5432
5. รันชุดทดสอบ
6. DROP DATABASE crawl_test · DROP ROLE crawl_test_runner · ปิดอุโมงค์
```

ตรวจว่าของครบก่อนรัน

```
migration              001_mko_structured, 002_mko_review_publish, 003_crawl_sources
ตาราง mko              3
วิว mko                1   (v_crawl_pending)
crawl_sources คอลัมน์   29
ดัชนี crawl_sources     6
PostgreSQL             16.15
```

### ด่านกันรันใส่ production

ชุดทดสอบมีด่านของตัวเองที่ปฏิเสธถ้า `"course_advisor"` อยู่ใน URL
([crawl_state_check.py](eval/crawl_state_check.py) ใน `main()`) และหัวรายงานที่พิมพ์ออกมา
ยืนยันปลายทางจริง

```
ฐานข้อมูลทดสอบ: 127.0.0.1:55432/crawl_test
เชื่อมต่อได้: db=crawl_test user=crawl_test_runner
```

### ผลทั้ง 32 ข้อ

```
--- รอบที่ 1 ---
  ผ่าน  1.  PDF เดิม (sha ตรงกับคลัง) ได้สถานะ unchanged
  ผ่าน  1b. ผูก document_id กับเอกสารในคลังให้ด้วย
  ผ่าน  1c. ไม่เก็บไฟล์ลง staging
  ผ่าน  2.  PDF ใหม่ ได้สถานะ downloaded
  ผ่าน  2b. เก็บไฟล์ลง staging จริง
  ผ่าน  2c. ตั้งธงรอคนตรวจ
  ผ่าน  2d. ยังไม่ผูกกับเอกสารในคลัง (ยังไม่ได้นำเข้า)
  ผ่าน  2e. ยังไม่มีข้อมูลการอนุมัติ
  ผ่าน  4.  HTTP 500 ได้สถานะ error
  ผ่าน  4b. นับจำนวนครั้งที่ผิดพลาด
  ผ่าน  4c. ลิงก์อื่นในรอบเดียวกันยังทำงานต่อได้
  ผ่าน  4e. ลิงก์นอกเว็บคณะได้สถานะ error              ← ใหม่
  ผ่าน  4f. ไม่เก็บไฟล์ของลิงก์นอกเว็บคณะ                ← ใหม่
  ผ่าน  4g. ไม่ยิงคำขอไปหาโฮสต์นอกขอบเขตเลย             ← ใหม่
  ผ่าน  4h. บันทึกเหตุผลว่าโฮสต์ไม่อนุญาต                ← ใหม่
  ผ่าน  5.  ชื่อหลักสูตรกำกวม ถูกทำเครื่องหมาย ambiguous
  ผ่าน  5b. เก็บตัวเลือกทั้งหมดไว้ ไม่เลือกเอง
  ผ่าน  5c. ตั้งธงรอคนตรวจ
  ผ่าน  5d. หลักสูตรที่ไม่มีในคลัง ไม่ถูกเดาให้ผิด

--- รอบที่ 2 (เนื้อหาของ willchange.pdf เปลี่ยน) ---
  ผ่าน  3.  URL เดิมแต่เนื้อหาเปลี่ยน ได้สถานะ changed
  ผ่าน  3b. เก็บ sha ของเดิมไว้เทียบได้
  ผ่าน  3c. sha ใหม่ถูกบันทึก
  ผ่าน  3d. เก็บไฟล์ใหม่ลง staging
  ผ่าน  1d. รอบสอง ETag เท่าเดิม ยังเป็น unchanged
  ผ่าน  4d. เมื่อกลับมาดึงได้ ตัวนับข้อผิดพลาดถูกรีเซ็ต
  ผ่าน  6.  เอกสารในคลังยังอยู่ครบหลัง crawl สองรอบ
  ผ่าน  6b. เอกสารที่ไม่พบบนเว็บไม่ถูกลบ
  ผ่าน  7.  วิว v_crawl_pending แสดงเฉพาะงานที่ต้องตัดสินใจ

--- ข้อบังคับของฐานข้อมูล ---
  ผ่าน  CHECK กันสถานะที่ไม่รู้จัก
  ผ่าน  CHECK กัน sha256 ที่ผิดรูปแบบ
  ผ่าน  CHECK บังคับว่าอนุมัติแล้วต้องมีชื่อผู้อนุมัติ
  ผ่าน  UNIQUE กัน source_url ซ้ำ

สรุป: ผ่าน 32 · ไม่ผ่าน 0
```

ข้อ 4e–4h เป็นข้อใหม่ที่เพิ่มในงานรอบนี้ — ปิดช่องที่ `discover.crawl()` เก็บลิงก์ `.pdf`
ข้ามโฮสต์มาด้วย และตอนนี้พิสูจน์กับฐานข้อมูลจริงแล้ว ไม่ใช่แค่กับ StubStore

### ลบของทดสอบแล้ว ตรวจซ้ำ

```
ฐานข้อมูลที่เหลือ:  postgres, course_advisor
role ที่เหลือ:      advisor_api, advisor_ingest, postgres
```

`crawl_test` และ `crawl_test_runner` หายไปทั้งคู่ · อุโมงค์ SSH ปิดแล้ว (พอร์ต 55432 ไม่เปิด)

> **บันทึกไว้ให้ครบ**: การสร้างและลบฐานข้อมูล/role นี้เกิดบน *instance* เดียวกับ production
> แต่เป็นฐานข้อมูลคนละฐาน ไม่มีคำสั่งใดแตะ `course_advisor` และผลตรวจในหัวข้อ 4
> ยืนยันว่าตัวเลขทุกตัวเท่าเดิม

---

## 2. เทสต์ที่รันในเครื่อง (ไม่ต้องมีฐานข้อมูล)

`eval/crawl_download_check.py` — **140 ข้อ ผ่านทั้งหมด** (รายละเอียดใน
[CRAWLER_DOWNLOAD_SECURITY_REPORT.md](docs/CRAWLER_DOWNLOAD_SECURITY_REPORT.md) หัวข้อ 5)

รวมสองชุด: **172 ข้อ ผ่านทั้งหมด**

---

## 3. commit และ push

### ก่อน commit

```
git status --porcelain --untracked-files=no
   M eval/crawl_state_check.py
   M pipeline/crawl/http.py
   M pipeline/crawl/run.py
   M pipeline/crawl/sync.py

git diff --numstat
  54    1   eval/crawl_state_check.py
  235   2   pipeline/crawl/http.py
  31   12   pipeline/crawl/run.py
  70   37   pipeline/crawl/sync.py
```

สแกน secret ใน 942 บรรทัดที่จะ commit: `password` · `secret` · `PASSWORD` ·
`postgres://` · `postgresql://` · `ADVISOR_` · `@161.` · `ssh -i` · `.key` = **0 ทุกรายการ**

### commit

```
hash    a0655ef3bd7ddd4d71d6ede59f9cab8d6d027c87
branch  mko-phase2
parents 1  (ไม่ใช่ merge)
msg     fix: harden crawler PDF downloads
ไฟล์    5 files changed, 1031 insertions(+), 52 deletions(-)
```

ใช้ `git add` ระบุพาธทีละไฟล์ทั้ง 5 ไฟล์ **ไม่ได้ใช้ `git add .`**

```
eval/crawl_download_check.py     (ไฟล์ใหม่)
eval/crawl_state_check.py
pipeline/crawl/http.py
pipeline/crawl/run.py
pipeline/crawl/sync.py
```

### push

```
To https://github.com/pattana-ketchot/Project-Chataipnru.git
   2cdab40..a0655ef  mko-phase2 -> mko-phase2
```

### ยืนยันหลัง push

```
local  HEAD        a0655ef3bd7ddd4d71d6ede59f9cab8d6d027c87
origin/mko-phase2  a0655ef3bd7ddd4d71d6ede59f9cab8d6d027c87   ตรงกัน
ahead 0 / behind 0
local main b78b3f8 · origin/main b78b3f8                      ไม่ถูกแตะ ไม่มี merge
tracked changes ค้าง: ไม่มี
```

ไฟล์ที่ยัง untracked โดยเจตนา: `docs/CRAWLER_DOWNLOAD_SECURITY_REPORT.md` และรายงานฉบับนี้
(คำสั่งระบุให้ commit เฉพาะ 5 ไฟล์ตามรายงาน ซึ่งไม่รวมตัวรายงานเอง)

---

## 4. Production — ตัวเลขตรงกับ baseline ทุกตัว

อ่านแบบอ่านอย่างเดียวผ่าน `docker exec psql` **ไม่มีคำสั่งเขียนใดถูกรัน**

| รายการ | baseline ที่คาด | ที่อ่านได้ | ผล |
|---|---|---|---|
| `courses` | 24 | **24** | ✅ |
| `course_documents` | 31 | **31** | ✅ |
| `course_chunks` | 9,039 | **9,039** | ✅ |
| `mko.crawl_sources` | 12 | **12** | ✅ |
| `needs_review` | 6 | **6** | ✅ |
| `staging_path` ไม่ว่าง | 0 | **0** | ✅ |
| สถานะ | `unchanged=12` | **`unchanged=12`** | ✅ |
| `last_checked_at` ล่าสุด | 28 ก.ย. 2569 01:59:01 (รอบ Phase 2) | **เท่าเดิม** | ✅ |

migration ที่ลงไว้ — ไม่มีอะไรเพิ่ม

```
001_mko_structured      2026-09-15 08:34:52+07
002_mko_review_publish  2026-09-15 08:34:52+07
003_crawl_sources       2026-09-28 01:56:01+07
```

**ไม่มี ingestion · ไม่มี embedding · ไม่มี PDF ใหม่เข้าคลัง · ไม่มีการลบข้อมูล**
ยืนยันจากตัวเลขสามตัวหลัก (24 / 31 / 9,039) ที่เท่าเดิมทุกตัว

### 12 ลิงก์ที่เฝ้าดู — ทุกลิงก์อยู่บนโฮสต์ที่อนุญาต

```
โฮสต์ที่ตรงกับ https://sci.pnru.ac.th/ :  12 / 12
```

| โฮสต์ | สถานะ | ต้องตรวจ | course_code | ความมั่นใจ |
|---|---|---|---|---|
| sci.pnru.ac.th | unchanged | – | agri68_phd | high |
| sci.pnru.ac.th | unchanged | ✓ | cs66 | ambiguous |
| sci.pnru.ac.th | unchanged | ✓ | animation69 | ambiguous |
| sci.pnru.ac.th | unchanged | – | cook69 | high |
| sci.pnru.ac.th | unchanged | ✓ | ma69 | ambiguous |
| sci.pnru.ac.th | unchanged | – | en65 | high |
| sci.pnru.ac.th | unchanged | – | agri68_master | high |
| sci.pnru.ac.th | unchanged | ✓ | attm65 | ambiguous |
| sci.pnru.ac.th | unchanged | – | food66 | high |
| sci.pnru.ac.th | unchanged | – | bio2568 | high |
| sci.pnru.ac.th | unchanged | ✓ | cos66 | ambiguous |
| sci.pnru.ac.th | unchanged | ✓ | it66 | ambiguous |

**สิ่งที่ข้อมูลนี้บอกได้**: ด่านโฮสต์/scheme/พอร์ตที่เพิ่มใหม่จะไม่ปฏิเสธลิงก์ใดใน 12 ลิงก์นี้
เพราะทั้งหมดเป็น `https://sci.pnru.ac.th/` ซึ่งอยู่ในรายการที่อนุญาต

**สิ่งที่ข้อมูลนี้บอกไม่ได้**: ยังไม่ได้พิสูจน์ว่าไฟล์ทั้ง 12 ผ่านด่านขนาดและด่านลายเซ็น
`%PDF-` จริง (แม้จะเคยดาวน์โหลดสำเร็จมาแล้วในรอบ Phase 2 ซึ่งบอกว่าเป็นไฟล์จริง
และเป็น มคอ.2 หลายเมกะไบต์ ไม่ใกล้เพดาน 50 MB) — ต้องรัน crawler จริงจึงจะยืนยันได้

---

## 5. ❌ สิ่งที่ยังทำไม่ได้ — production crawler check

**อาการ**: รหัสผ่านของ `advisor_ingest` ใน `D:\workspace\course-advisor-system\.env`
ใช้ยืนยันตัวตนกับ production ไม่ผ่าน

```
psycopg.OperationalError: connection failed: connection to server at "127.0.0.1",
port 55432 failed: FATAL:  password authentication failed for user "advisor_ingest"
```

**ตรวจต่อแล้วพบว่า** ค่าในไฟล์ไม่ใช่ค่าตัวอย่างจาก `.env.example` (เป็นค่าจริงค่าหนึ่ง)
และรหัสผ่านใน `INGEST_DATABASE_URL` ตรงกับ `ADVISOR_INGEST_PASSWORD` ในไฟล์เดียวกัน
แปลว่าไฟล์นี้สอดคล้องกันเอง แต่เป็นของ PostgreSQL คนละตัวกับ production
(หรือรหัสผ่านบนเซิร์ฟเวอร์ถูกเปลี่ยนหลังจากนั้น)

รหัสผ่านจริงอยู่ใน `.env` บนเซิร์ฟเวอร์ที่ docker compose ใช้ ซึ่งผมไม่ได้อ่านและจะไม่อ่าน
โดยไม่ได้รับอนุญาต

**หยุดตามคำสั่ง ไม่แก้ production ต่อเอง** ไม่มีคำสั่งเขียนใดถูกรันบน `course_advisor`

### ทางเลือกสำหรับรอบถัดไป

| # | วิธี | ข้อดี | ข้อเสีย |
|---|---|---|---|
| 1 | เจ้าของโปรเจครัน `pipeline.crawl.sync` เองบนเครื่องที่มี `.env` ถูกต้อง แล้วส่งผลมาให้ | ตรงกับ flow Phase 2 · ไม่มีใครเห็นรหัสผ่านเพิ่ม | ต้องลงมือเอง |
| 2 | ให้รหัสผ่าน `ADVISOR_INGEST_PASSWORD` ของ production มา | ผมรันได้ทันทีด้วย flow เดิม | รหัสผ่านเข้ามาอยู่ในบทสนทนานี้ |
| 3 | อนุญาตให้ผมอ่าน `.env` บนเซิร์ฟเวอร์ | ไม่ต้องพิมพ์เอง | เท่ากับข้อ 2 ในผล |
| 4 | รัน crawler ในคอนเทนเนอร์ชั่วคราวบนเซิร์ฟเวอร์ โดย `--env-file .env` ให้ Docker ใส่ค่าเอง | **ไม่มีใครเห็นรหัสผ่านเลย** | ต้องดึงอิมเมจ `python:3.11-slim` และ `pip install httpx psycopg` บนเซิร์ฟเวอร์ ซึ่งเป็นการเพิ่มของบน production ที่ยังไม่ได้อนุมัติ |

**แนะนำข้อ 1 หรือ 4** ข้อ 4 สะอาดที่สุดในแง่ความปลอดภัยแต่ต้องอนุมัติการเพิ่มอิมเมจก่อน

คำสั่งสำหรับข้อ 1 (รันจากรากของ repo บน branch `mko-phase2` ที่ `a0655ef`)

```bash
CRAWL_DATABASE_URL="$INGEST_DATABASE_URL" python -m pipeline.crawl.sync --staging staging/crawl
```

สิ่งที่ต้องดูในผล: 12 ลิงก์ · ควรได้ `unchanged` ทั้ง 12 · ไม่มีรายการใดกลายเป็น `error` ·
`ไฟล์รออนุมัติ` ต้องเป็น 0 · และตรวจซ้ำว่า `courses` / `course_documents` / `course_chunks`
ยังเป็น 24 / 31 / 9,039

---

## 6. สถานะถัดไป

- ✅ commit `a0655ef` อยู่บน `origin/mko-phase2` แล้ว
- ⛔ **ยังไม่ deploy** — โค้ดใหม่ยังไม่ได้เข้า production image และ crawler ยังไม่ได้รันบน production
- ⛔ **ยังไม่เริ่ม Phase 3** (Admin UI/API และ ingest-worker) ตามคำสั่ง
- ⏳ รอการตัดสินใจเรื่องวิธีรัน production crawler check (หัวข้อ 5)
