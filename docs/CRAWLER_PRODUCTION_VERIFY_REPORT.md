# Production Crawler Verification ของ commit `a0655ef`

| | |
|---|---|
| วันที่ | 28 กันยายน 2569 |
| checkpoint | `a0655ef3bd7ddd4d71d6ede59f9cab8d6d027c87` บน `mko-phase2` |
| เวลารัน | 28 ก.ย. 2569 05:45:36 – 05:46:18 (+07) · 42 วินาที |
| แผนที่ใช้ | [CRAWLER_VERIFY_EXECUTION_PLAN.md](docs/CRAWLER_VERIFY_EXECUTION_PLAN.md) — ทำตามทุกขั้น ไม่ขยาย scope |
| **ผล** | ✅ **ผ่านทุกข้อที่กำหนด** |

**ไม่มีค่า secret ใดถูกแสดง อ่านออกมา หรือคัดลอกในกระบวนการนี้**

---

## 1. สรุปผลเทียบกับเกณฑ์

| เกณฑ์ | ต้องได้ | ที่ได้จริง | ผล |
|---|---|---|---|
| PDF links | 12 | **12** | ✅ |
| สถานะ | `unchanged=12` | **`unchanged=12`** | ✅ |
| `courses` | 24 | **24** | ✅ |
| `course_documents` | 31 | **31** | ✅ |
| `course_chunks` | 9,039 | **9,039** | ✅ |
| `mko.crawl_sources` | 12 | **12** | ✅ |
| `needs_review` | 6 | **6** | ✅ |
| `staging_path` ไม่ว่าง | 0 | **0** | ✅ |
| `error_count` รวม | 0 | **0** | ✅ |
| migration | เฉพาะ 001 / 002 / 003 | **001, 002, 003** | ✅ |
| `changed` / `downloaded` / `error` | ไม่มี | **ไม่มีสักแถว** | ✅ |
| ไฟล์ใน staging | ไม่มี | **ไม่มีโฟลเดอร์ staging เลย** | ✅ |
| ingestion / embedding / deletion | ไม่มี | **ไม่มี** | ✅ |
| production service ถูก restart | ไม่มี | **ไม่มี · restart=0 ทุกตัว** | ✅ |

---

## 2. ขั้นตอนที่ทำจริง

### ขั้น 0 · สแนปช็อตก่อนรัน

```
โฟลเดอร์ทำงาน  /home/ubuntu/crawlrun-a0655ef
สแนปช็อต       crawl_sources_before.sql  46 บรรทัด · 15,924 ไบต์
baseline รายแถว rows_before.txt           12 แถว
```

สแนปช็อตทำด้วย `pg_dump --data-only --table=mko.crawl_sources` เฉพาะตารางเดียว
ไม่มี credential อยู่ในไฟล์

### ขั้น 1 · วางโค้ดของ `a0655ef` — hash ตรงกับแผนทุกไฟล์

ส่งด้วย `git -c core.autocrlf=false archive a0655ef pipeline | ssh … tar -x`

| ไฟล์ | sha256 ที่แผนระบุ | ที่ได้บนเซิร์ฟเวอร์ | บรรทัด | ผล |
|---|---|---|---|---|
| `pipeline/crawl/http.py` | `6c61fed8430e7e1d` | `6c61fed8430e7e1d` | 362 | ✅ |
| `pipeline/crawl/sync.py` | `7b574f64933c8eee` | `7b574f64933c8eee` | 315 | ✅ |
| `pipeline/crawl/run.py` | `dd8b59c07c46ee82` | `dd8b59c07c46ee82` | 176 | ✅ |
| `pipeline/crawl/state.py` | — | `0e2fb0796a4704c2` | 176 | — |
| `pipeline/crawl/discover.py` | — | `022f2dcff61110a6` | 146 | — |
| `pipeline/crawl/inventory.py` | — | `c9b57930416c0d11` | 166 | — |

ไฟล์ `.py` ที่ส่งไป 30 ไฟล์ · **ไฟล์ที่มี CR: 0** (การบังคับ `core.autocrlf=false` ทำงาน)

### ขั้น 2 · รัน crawler หนึ่งรอบ

คอนเทนเนอร์ชั่วคราวจากอิมเมจ **ที่ production ใช้อยู่** `d1d1ba713412`

```
docker run --rm --name crawlrun-a0655ef
  --network course-advisor-system_default
  --env-file /home/ubuntu/course-advisor-system/.env
  -v /home/ubuntu/crawlrun-a0655ef:/work  -w /work
  d1d1ba713412
  sh -c 'CRAWL_DATABASE_URL="postgresql://advisor_ingest:$ADVISOR_INGEST_PASSWORD@postgres:5432/course_advisor" \
         exec python -u -m pipeline.crawl.sync --staging /work/staging'
```

- ไม่ `pull` · ไม่ `build` · ไม่ `pip install` · ไม่แก้ compose · ไม่ restart อะไร
- `$ADVISOR_INGEST_PASSWORD` แทนค่าใน shell ของคอนเทนเนอร์ ค่าไม่ปรากฏในคำสั่งที่ส่งผ่าน ssh
  ไม่ปรากฏในประวัติ shell ของเซิร์ฟเวอร์ และไม่ปรากฏใน `run.log`
- รันแบบ detach เขียน log ลงไฟล์ตามบทเรียนเดิม ไม่ pipe ผ่าน ssh

---

## 3. ผลการรัน — `run.log`

```
คลังที่ระบบมี: 31 เอกสาร
GET https://sci.pnru.ac.th/robots.txt "HTTP/1.1 404 Not Found"
robots.txt ของ https://sci.pnru.ac.th: ไม่มี (http 404) ถือว่าอนุญาต
...
เดินเว็บ 16 หน้า พบลิงก์ PDF ไม่ซ้ำ 12

---- สรุป ----
  unchanged   12
  รอคนตรวจ   6
  คำขอ HTTP  29 · ใช้เวลา 42 วินาที
  ไฟล์รออนุมัติอยู่ที่ /work/staging
Phase 2 ไม่นำเข้าคลังความรู้ — ต้องให้คนอนุมัติก่อน
```

### ตรวจ log แบบเจาะจง

| ตรวจ | จำนวนบรรทัด |
|---|---|
| `ERROR` | **0** |
| `WARNING` | **0** |
| `Traceback` | **0** |
| `error` | **0** |
| `downloaded` | **0** |
| `changed` | 1 — เป็นสับสตริงของ `unchanged` ในบรรทัดสรุป ตรวจแล้วไม่มีแถวใดเป็น `changed` |
| `ไม่ใช่ PDF` · `เพดาน` · `redirect` · `โฮสต์ไม่อนุญาต` | **0 ทุกคำ** |
| `[n/12]` (ลิงก์ที่ตรวจ) | **12** |

### คำขอ HTTP ทั้ง 29 คำขอ

| ชนิด | จำนวน |
|---|---|
| `GET` หน้าเว็บ + `robots.txt` | 17 |
| `HEAD` ไฟล์ `.pdf` | **12** |
| **`GET` ไฟล์ `.pdf`** | **0** |

`GET` ของไฟล์ PDF เป็นศูนย์ เพราะ ETag และขนาดไฟล์เท่าเดิมทั้ง 12 ไฟล์
ตัวดึงจึงข้ามการโหลดตามตรรกะเดิมของ Phase 2 — ประหยัดทั้งเวลาและแบนด์วิดท์ของเว็บคณะ

### ไม่มี secret หลุดใน log

`ADVISOR_INGEST_PASSWORD` · `advisor_ingest` · `postgresql://` · `GEMINI` · `JWT` · `password`
= **0 ทุกคำ**

---

## 4. ฐานข้อมูล — ก่อน / หลัง

### ตัวเลขรวม

| รายการ | ก่อน | หลัง | ผล |
|---|---|---|---|
| `courses` | 24 | **24** | เท่าเดิม |
| `course_documents` | 31 | **31** | เท่าเดิม |
| `course_chunks` | 9,039 | **9,039** | เท่าเดิม |
| `mko.crawl_sources` | 12 | **12** | เท่าเดิม |
| `needs_review` | 6 | **6** | เท่าเดิม |
| `staging_path` ไม่ว่าง | 0 | **0** | เท่าเดิม |
| `error_count` รวม | 0 | **0** | เท่าเดิม |
| `document_id` ไม่ว่าง | 12 | **12** | เท่าเดิม |
| สถานะ | `unchanged=12` | **`unchanged=12`** | เท่าเดิม |
| migration | 001, 002, 003 | **001, 002, 003** | เท่าเดิม |

### เทียบระดับแถว — 12 แถว 12 คอลัมน์

เทียบทุกคอลัมน์ (`source_url`, `status`, `needs_review`, `error_count`, `file_sha256`,
`http_etag`, `content_length`, `staging_path`, `document_id`, `course_code`,
`match_confidence`) **ยกเว้น `last_checked_at`**

```
เหมือนกันทุกแถวทุกคอลัมน์ (12 แถว)
```

`last_checked_at` เปลี่ยนทั้ง 12 แถวตามที่ควรเป็น — นี่คือสิ่งเดียวที่การรันนี้แก้

```
ก่อน  2026-09-28 01:58:03 … 01:58:32 (+07)   ← รอบ Phase 2
หลัง  2026-09-28 05:45:36 … 05:46:02 (+07)   ← รอบนี้
```

### 12 ลิงก์ที่เฝ้าดู — สถานะหลังรัน

| # | สถานะ | ต้องตรวจ | `error_count` | `last_error` | `course_code` | ความมั่นใจ |
|---|---|---|---|---|---|---|
| 1 | unchanged | – | 0 | – | agri68_phd | high |
| 2 | unchanged | ✓ | 0 | – | cs66 | ambiguous |
| 3 | unchanged | ✓ | 0 | – | animation69 | ambiguous |
| 4 | unchanged | – | 0 | – | cook69 | high |
| 5 | unchanged | ✓ | 0 | – | ma69 | ambiguous |
| 6 | unchanged | – | 0 | – | en65 | high |
| 7 | unchanged | – | 0 | – | agri68_master | high |
| 8 | unchanged | ✓ | 0 | – | attm65 | ambiguous |
| 9 | unchanged | – | 0 | – | food66 | high |
| 10 | unchanged | – | 0 | – | bio2568 | high |
| 11 | unchanged | ✓ | 0 | – | cos66 | ambiguous |
| 12 | unchanged | ✓ | 0 | – | it66 | ambiguous |

6 แถวที่ `needs_review` เป็นชุดเดิมทั้งหมด (สาขาที่มี มคอ.2 สองฉบับจึงแยกจากชื่อไม่ได้)
ไม่มีแถวใดถูกตั้งธงเพิ่มหรือปลดธง

---

## 5. staging

```
/home/ubuntu/crawlrun-a0655ef/staging : ไม่มีโฟลเดอร์
```

crawler **ไม่ได้สร้างโฟลเดอร์ staging เลย** เพราะไม่มีไฟล์ใดต้องเก็บ ซึ่งสอดคล้องกับ
โค้ดใหม่ที่ `dest_dir.mkdir()` เกิดขึ้นเฉพาะตอนจะสร้างไฟล์ชั่วคราว คือหลังผ่านลายเซ็น
`%PDF-` แล้วเท่านั้น — ไม่มี `.part_*` ค้าง และไม่มีไฟล์ใดถูกเขียน

---

## 6. ยืนยันว่าไม่มี production service ถูก restart

| service | `RestartCount` | เริ่มทำงานเมื่อ | ก่อนรอบนี้ไหม |
|---|---|---|---|
| backend | **0** | 2026-09-23 23:53:41 | ใช่ (4 วันก่อน) |
| frontend | **0** | 2026-09-04 17:27:43 | ใช่ |
| webapi | **0** | 2026-09-22 21:21:35 | ใช่ |
| caddy | **0** | 2026-09-22 21:23:48 | ใช่ |
| postgres | **0** | 2026-08-18 14:17:25 | ใช่ |
| ollama | **0** | 2026-08-18 14:17:25 | ใช่ |

ทุกตัว `RestartCount = 0` และเวลาเริ่มทำงานอยู่ก่อนการรันรอบนี้ทั้งหมด
อิมเมจที่ backend ใช้ยังเป็น `sha256:d1d1ba713412` ตัวเดิม — **ไม่ใช่การ deploy**

---

## 7. Cleanup

| รายการ | ผล |
|---|---|
| คอนเทนเนอร์ชั่วคราว | **0 ตัว** — `--rm` ลบเองเมื่อจบ |
| โฟลเดอร์ `/home/ubuntu/crawlrun-a0655ef/` (408 KB · 37 ไฟล์) | **ลบแล้ว** |
| โฟลเดอร์ `crawlrun*` อื่น | ไม่มี |
| `/home/ubuntu/course-advisor-system/pipeline/crawl` | **ยังไม่มี** — โฟลเดอร์ deploy เดิมไม่ถูกแตะ (ยังเป็น 8 ไฟล์ `.py` เท่าเดิม) |
| `.env` บนเซิร์ฟเวอร์ | mtime ยังเป็น 2026-09-22 21:20:18 · ขนาด 1,867 ไบต์ — **ไม่ถูกแก้** |
| อิมเมจ | ไม่มีอิมเมจใหม่ ไม่มี pull ไม่มี build |

### หลักฐานที่เก็บไว้ก่อนลบ

`run.log` (66 บรรทัด) · `counts_before.txt` · `counts_after.txt` ·
`rows_before.txt` (12 แถว) · `rows_after.txt` (12 แถว) — ดึงมาเก็บไว้นอกเซิร์ฟเวอร์
และสรุปไว้ในรายงานฉบับนี้ครบแล้ว

สแนปช็อต `crawl_sources_before.sql` ถูกลบไปพร้อมโฟลเดอร์ เพราะการรันผ่านทุกข้อ
จึงไม่มีอะไรต้อง rollback (ถ้าจำเป็นภายหลัง สร้างใหม่ได้จาก `pg_dump` ตัวเดิม)

---

## 8. ⚠️ ข้อจำกัดของการตรวจรอบนี้ — ต้องรู้ไว้

**ด่านที่ถูกใช้งานจริง**

| ด่านใหม่ | ถูกเรียกไหม | หลักฐาน |
|---|---|---|
| `url_rejection()` ตรวจ scheme / โฮสต์ / พอร์ต ก่อนยิงคำขอ | ✅ 12 ครั้ง | ทั้ง 12 ลิงก์เป็น `https://sci.pnru.ac.th/` ผ่านด่านและเดินต่อได้ปกติ |
| `head()` ตรวจโฮสต์ปลายทางหลัง redirect | ✅ 12 ครั้ง | HEAD 12 คำขอ ไม่มีลิงก์ใดถูกปฏิเสธ |
| `get()` ตรวจโฮสต์ปลายทางหลัง redirect | ✅ 17 ครั้ง | GET หน้าเว็บและ robots.txt |

**ด่านที่ยังไม่ถูกใช้งานในรอบนี้**

`download()` ทั้งฟังก์ชัน — เพดานขนาดแบบทยอยอ่าน · ลายเซ็น `%PDF-` ·
การตรวจ redirect ตอน GET ไฟล์ · การเขียนไฟล์ `.part_*` แล้ว `os.replace()`

เพราะ ETag และขนาดของทั้ง 12 ไฟล์เท่าเดิม ตัวดึงจึงข้ามการโหลดทั้งหมด
(`GET` ไฟล์ `.pdf` = 0) ซึ่ง **เป็นพฤติกรรมที่ถูกต้องและเป็นผลดี** แต่หมายความว่า
เส้นทางดาวน์โหลดจริงบน production ยังไม่ได้พิสูจน์ในรอบนี้

สิ่งที่พิสูจน์เส้นทางนั้นไปแล้วคือ `eval/crawl_download_check.py` **140 ข้อ**
กับเว็บเซิร์ฟเวอร์จริงในเครื่อง และ `eval/crawl_state_check.py` **32 ข้อ**
กับ PostgreSQL จริงที่ลง migration 003 — รวม 172 ข้อ ผ่านทั้งหมด

เส้นทางดาวน์โหลดจะถูกใช้งานจริงบน production เมื่อคณะอัปโหลดเอกสารฉบับใหม่
หรือเมื่อรันด้วยตัวเลือกที่บังคับให้โหลด ซึ่งรอบนี้ไม่ได้ทำเพราะอยู่นอก scope ที่อนุมัติ

---

## 9. สถานะปัจจุบัน

| | |
|---|---|
| `mko-phase2` | `a0655ef` ตรงกับ `origin/mko-phase2` · ahead 0 / behind 0 |
| `main` | `b78b3f8` ไม่ถูกแตะ ไม่มี merge |
| production image | `d1d1ba713412` เดิม — **โค้ด hardening ยังไม่ได้ deploy** |
| ฐานข้อมูล | ไม่มีการแก้ schema ไม่มี migration ใหม่ ข้อมูลคลังความรู้เท่าเดิมทุกตัว |
| Phase 3 | **ยังไม่เริ่ม** ทั้ง Admin UI/API และ ingest-worker |

**หยุดตามคำสั่ง รอการตรวจรายงานฉบับนี้**
