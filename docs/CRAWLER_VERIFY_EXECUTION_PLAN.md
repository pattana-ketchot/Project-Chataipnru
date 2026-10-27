# แผนรัน Production Crawler Check ของ commit `a0655ef`

| | |
|---|---|
| วันที่ | 28 กันยายน 2569 |
| checkpoint | `a0655ef` บน `mko-phase2` (ตรงกับ `origin/mko-phase2`) |
| สถานะ | **สำรวจแบบอ่านอย่างเดียวเสร็จ · เสนอแผน · ยังไม่ได้รันอะไร** |
| ข้อสรุป | **รันได้ด้วยของที่มีอยู่แล้วบนเซิร์ฟเวอร์ ไม่ต้อง pull / build / pip install / แก้ compose / restart** |

**ไม่มีค่า secret ใดถูกแสดง คัดลอก หรือส่งออกในรายงานนี้หรือในขั้นตอนที่เสนอ**

---

## ผลสำรวจ (อ่านอย่างเดียว)

### สิ่งที่มีอยู่แล้ว

| รายการ | สถานะ |
|---|---|
| อิมเมจ backend ที่ production ใช้อยู่ | `d1d1ba713412` (คอนเทนเนอร์ `course-advisor-system-backend-1` รันด้วยตัวนี้) |
| Python ในอิมเมจนั้น | 3.11.16 |
| `httpx` | **0.28.1 มีแล้ว** |
| `psycopg` | **3.3.6 มีแล้ว** |
| เครือข่าย compose | `course-advisor-system_default` (bridge) |
| DNS จากในเครือข่าย | `sci.pnru.ac.th → 202.29.26.144` · `postgres → 172.18.0.2` **ทั้งคู่แก้ชื่อได้** |
| `python:3.11-slim` | มีบนเครื่องแล้ว (ไม่ต้องใช้ แต่บันทึกไว้) |
| พื้นที่ดิสก์ | ว่าง 65 GB จาก 97 GB |
| `git`, `tar` บน host | มีทั้งคู่ |

### สิ่งที่ขาด

| รายการ | สถานะ |
|---|---|
| **โค้ด crawler บนเซิร์ฟเวอร์** | `/home/ubuntu/course-advisor-system/pipeline/` มีแค่ 8 ไฟล์ (`ingest.py`, `chunker.py`, `embed.py`, …) **ไม่มีโฟลเดอร์ `crawl/` เลย** — เป็นสแนปช็อตเก่าก่อน Phase 1/2 |
| `python3` บน host | มี แต่ **ไม่มี `httpx`** → รันบน host ไม่ได้ |
| `pymupdf` / `fitz` ในอิมเมจ backend | ไม่มี — **ไม่จำเป็น** เพราะ crawler ใช้แค่ `httpx` + `psycopg` + stdlib (`pymupdf` เป็นของ ingest ซึ่งรอบนี้ไม่ทำ) |
| git repo บนเซิร์ฟเวอร์ | `/home/ubuntu/course-advisor-system/` **ไม่ใช่ git repo** → `git checkout a0655ef` ที่นั่นทำไม่ได้ |
| โฟลเดอร์ staging บนเซิร์ฟเวอร์ | ไม่มี (รอบ Phase 2 รันจากเครื่องพัฒนา staging จึงอยู่ที่นั่น) |

### `.env` บนเซิร์ฟเวอร์ — ตรวจรูปแบบเท่านั้น ไม่เปิดดูค่า

| ตรวจ | ผล |
|---|---|
| มีไฟล์ | ใช่ · `/home/ubuntu/course-advisor-system/.env` |
| สิทธิ์ | `-rw-------` เจ้าของ `ubuntu:ubuntu` |
| จำนวนบรรทัด | 27 |
| คีย์ `ADVISOR_INGEST_PASSWORD` | มี (1 บรรทัด) |
| ค่าขึ้นต้นด้วยเครื่องหมายคำพูด | **ไม่** (0) |
| บรรทัดลงท้ายด้วย CR (CRLF) | **ไม่มี** (0) |
| บรรทัดที่มี `export` | ไม่มี (0) |
| ช่องว่างรอบ `=` | ไม่มี (0) |

ทั้งสี่ข้อท้ายสำคัญ เพราะ `docker run --env-file` แยกค่าแบบตรงตัว ไม่ถอดเครื่องหมายคำพูด
และไม่ตัด `\r` — ถ้ามีอย่างใดอย่างหนึ่ง รหัสผ่านที่ส่งเข้าไปจะผิดโดยไม่มีอะไรฟ้อง
**ไฟล์นี้ผ่านทั้งสี่ข้อ จึงใช้ `--env-file` ได้ปลอดภัย**

---

## ตอบคำถาม 6 ข้อ

### 1. crawler จะรันจาก environment/container ใด

คอนเทนเนอร์ **ชั่วคราว** ที่สร้างจากอิมเมจ backend ตัวเดียวกับที่ production ใช้อยู่
(`d1d1ba713412`) ด้วย `docker run --rm` บนเครือข่าย `course-advisor-system_default`

- **ไม่ใช่** การเข้าไปในคอนเทนเนอร์ backend ที่รันอยู่ และ**ไม่**คัดลอกโค้ดเข้าไปในนั้น
- คอนเทนเนอร์ที่รันอยู่ไม่ถูกแตะ ไม่ restart ไม่ recreate
- `--rm` ทำให้คอนเทนเนอร์ชั่วคราวหายไปเองเมื่อจบ
- โค้ด crawler เข้ามาทาง bind mount แบบอ่านจากโฟลเดอร์ใหม่ ไม่ได้ฝังในอิมเมจ
  → **นี่ไม่ใช่การ deploy** อิมเมจของ production ไม่เปลี่ยน

### 2. dependency ที่ต้องใช้มีอยู่แล้วหรือไม่ — **มีครบ**

`pipeline/crawl/` ต้องการเพียง

| โมดูล | ใช้ที่ | ในอิมเมจ |
|---|---|---|
| `httpx` | `http.py` | ✅ 0.28.1 |
| `psycopg` + `psycopg.rows` | `state.py` | ✅ 3.3.6 |
| `hashlib`, `tempfile`, `os`, `pathlib`, `re`, `difflib`, `urllib.robotparser`, `argparse`, `logging`, `json`, `dataclasses`, `datetime` | ทั้งโฟลเดอร์ | ✅ stdlib |

ไม่ต้องใช้ `pymupdf`, `pgvector`, `tqdm`, `sqlalchemy`, `fastapi` เลย

### 3. จำเป็นต้อง build / pull / install อะไรเพิ่มหรือไม่ — **ไม่ต้อง**

| รายการ | ต้องทำไหม |
|---|---|
| `docker pull` | ❌ อิมเมจอยู่บนเครื่องแล้ว |
| `docker build` | ❌ |
| `pip install` | ❌ |
| แก้ `docker-compose.prod.yml` | ❌ |
| เพิ่ม service / เพิ่ม volume ใน compose | ❌ |
| แก้ `Caddyfile` | ❌ |
| แก้ schema / รัน migration | ❌ |
| เปลี่ยน / สร้าง credential | ❌ |

**สิ่งเดียวที่ต้องเพิ่มบนเซิร์ฟเวอร์คือโฟลเดอร์ใหม่ที่เก็บโค้ด crawler**
เพราะ `pipeline/crawl/` ไม่มีอยู่บนเซิร์ฟเวอร์เลย ไม่มีทางรันโค้ดที่ไม่มีอยู่

```
/home/ubuntu/crawlrun-a0655ef/          ← โฟลเดอร์ใหม่ ไม่มีของเดิมอยู่ก่อน
    pipeline/...                        ← จาก git archive ของ commit a0655ef
    staging/                            ← crawler สร้างเองถ้ามีไฟล์ต้องเก็บ
    crawl_sources_before.sql            ← สแนปช็อตสำหรับ rollback
    run.log                             ← บันทึกการรัน
```

ไม่แตะ `/home/ubuntu/course-advisor-system/` เลยแม้แต่ไฟล์เดียว

### 4. จำเป็นต้อง restart service หรือไม่ — **ไม่ต้อง**

ไม่มี service ใดถูก restart, recreate, stop หรือ reload
`docker run` สร้างคอนเทนเนอร์ใหม่แยกจาก stack ที่รันอยู่ และลบตัวเองเมื่อจบ

### 5. วิธีส่ง credential ให้ process โดยไม่เปิดเผยค่า

ใช้ `--env-file` ชี้ไปที่ `.env` เดิมบนเซิร์ฟเวอร์ **Docker เป็นผู้อ่านไฟล์เอง**
ค่าไม่ผ่านมือผม ไม่ผ่านคำสั่งที่ผมพิมพ์ ไม่ผ่านผลลัพธ์ที่แสดง

```
--env-file /home/ubuntu/course-advisor-system/.env
```

แล้วให้ shell **ในคอนเทนเนอร์** ประกอบ URL เอง

```sh
CRAWL_DATABASE_URL="postgresql://advisor_ingest:$ADVISOR_INGEST_PASSWORD@postgres:5432/course_advisor"
```

`$ADVISOR_INGEST_PASSWORD` ถูกแทนค่าข้างในคอนเทนเนอร์ ไม่เคยปรากฏใน

- คำสั่งที่ส่งผ่าน ssh
- ประวัติ shell ของเซิร์ฟเวอร์ (ค่าไม่ได้อยู่ในบรรทัดคำสั่ง)
- `run.log` — ตรวจแล้วว่า `sync.py` ไม่ log URL หรือ DSN ที่จุดใด มันบันทึกเฉพาะ
  จำนวนเอกสาร ชื่อไฟล์ สถานะ และเวลา

**ไม่ใช้ `INGEST_DATABASE_URL` ที่อยู่ใน `.env` โดยตรง** เพราะค่านั้นชี้ไปที่
`127.0.0.1:5432` ซึ่งในคอนเทนเนอร์หมายถึงตัวคอนเทนเนอร์เอง ชื่อโฮสต์ที่ถูกต้องคือ `postgres`
จึงประกอบ URL ใหม่จาก `ADVISOR_INGEST_PASSWORD` โดยตรง

**เรื่องที่ต้องบอกให้ครบ**: `--env-file` ใส่ตัวแปรทั้ง 27 ตัวเข้าคอนเทนเนอร์ชั่วคราว
รวม `GEMINI_API_KEY` และรหัสผ่านอื่น ๆ ที่ crawler ไม่ได้ใช้
ยอมรับข้อนี้เพราะทางเลือกเดียวที่แคบกว่าคือทำสำเนา `.env` แบบกรองเฉพาะคีย์ที่ต้องใช้
ซึ่งเท่ากับ **คัดลอก secret ไปไว้ที่ใหม่** ที่ห้ามไว้ คอนเทนเนอร์นี้ไม่เปิดพอร์ตออกนอก
ไม่มี process อื่นในนั้น และถูกลบทิ้งด้วย `--rm`

### 6. วิธี rollback

| สิ่งที่เปลี่ยน | rollback |
|---|---|
| แถวใน `mko.crawl_sources` (`status`, `last_checked_at`, `error_count`, `http_etag`, `http_last_modified`, `content_length`, `review_reason`) | คืนจากสแนปช็อต `crawl_sources_before.sql` ที่เก็บก่อนรัน — ต้องใช้ superuser ผ่าน `docker exec` เพราะ `advisor_ingest` ไม่มีสิทธิ์ `DELETE` บนตารางนี้ |
| โฟลเดอร์ `/home/ubuntu/crawlrun-a0655ef/` | `rm -rf /home/ubuntu/crawlrun-a0655ef` |
| คอนเทนเนอร์ชั่วคราว | ไม่ต้องทำอะไร `--rm` ลบเอง |
| อิมเมจ / compose / service / schema / credential | **ไม่มีอะไรเปลี่ยน จึงไม่มีอะไรต้อง rollback** |

`sync.py` เขียนลง `mko.crawl_sources` **เท่านั้น** — `state.py` อ่าน `course_documents`
กับ `courses` แบบอ่านอย่างเดียว และไม่มีคำสั่ง `DELETE` สักจุดในโมดูล crawl ทั้งชุด
ตาราง `courses` / `course_documents` / `course_chunks` จึงไม่มีทางเปลี่ยนจากการรันนี้

---

## แผนที่เสนอ — คำสั่งตรงตัว

### ขั้น 0 · สแนปช็อตก่อนรัน (สำหรับ rollback และเทียบผล)

```bash
ssh -i ~/.ssh/oci.key ubuntu@161.118.237.37 \
  'mkdir -p /home/ubuntu/crawlrun-a0655ef && \
   sudo docker exec course-advisor-system-postgres-1 \
     pg_dump -U postgres -d course_advisor --data-only --table=mko.crawl_sources \
   > /home/ubuntu/crawlrun-a0655ef/crawl_sources_before.sql'
```

ไฟล์นี้มีแต่สถานะการ crawl ไม่มี credential

### ขั้น 1 · วางโค้ดของ `a0655ef` ลงโฟลเดอร์ใหม่

```bash
git -c core.autocrlf=false archive a0655ef pipeline \
  | ssh -i ~/.ssh/oci.key ubuntu@161.118.237.37 \
      'tar -x -C /home/ubuntu/crawlrun-a0655ef'
```

`-c core.autocrlf=false` **จำเป็น** เพราะเครื่องนี้เป็น Windows ถ้าไม่ใส่ ไฟล์ `.py`
จะออกมาเป็น CRLF ซึ่งเคยทำให้เทียบ sha256 ไม่ตรงและ shebang เพี้ยนมาแล้ว

จากนั้นตรวจว่าโค้ดที่ไปถึงตรงกับ commit จริง

| ไฟล์ | sha256 (16 ตัวแรก) ที่ต้องได้ | บรรทัด |
|---|---|---|
| `pipeline/crawl/http.py` | `6c61fed8430e7e1d` | 362 |
| `pipeline/crawl/sync.py` | `7b574f64933c8eee` | 315 |
| `pipeline/crawl/run.py` | `dd8b59c07c46ee82` | 176 |

### ขั้น 2 · รัน crawler หนึ่งรอบ

```bash
ssh -i ~/.ssh/oci.key ubuntu@161.118.237.37 \
 'cd /home/ubuntu/crawlrun-a0655ef && \
  nohup sudo docker run --rm \
    --network course-advisor-system_default \
    --env-file /home/ubuntu/course-advisor-system/.env \
    -v /home/ubuntu/crawlrun-a0655ef:/work \
    -w /work \
    d1d1ba713412 \
    sh -c "CRAWL_DATABASE_URL=\"postgresql://advisor_ingest:\$ADVISOR_INGEST_PASSWORD@postgres:5432/course_advisor\" \
           exec python -u -m pipeline.crawl.sync --staging /work/staging" \
    > /home/ubuntu/crawlrun-a0655ef/run.log 2>&1 &'
```

- `nohup … > run.log 2>&1 &` ตามบทเรียนเดิม — งานบนเซิร์ฟเวอร์ต้องเขียน log ลงไฟล์
  ไม่ pipe ผ่าน ssh เพราะสายหลุดแล้วงานตายและไม่เหลือหลักฐาน
- `python -u` ให้ log ออกทันที ไม่ค้างใน buffer
- `\$ADVISOR_INGEST_PASSWORD` มี backslash เพื่อให้ shell ของ **เซิร์ฟเวอร์** ไม่แทนค่า
  ปล่อยให้ shell ใน **คอนเทนเนอร์** แทนค่าเอง — ค่าจึงไม่เข้าประวัติคำสั่งของเซิร์ฟเวอร์
- ค่าเริ่มต้นของ `--delay` คือ 1.5 วินาที และ `--max-pages` คือ 80 ตามเดิมของ Phase 2
- คาดว่าใช้เวลาไม่เกิน 1–2 นาที (ส่วนใหญ่เป็น HEAD เพราะ ETag ไม่เปลี่ยน)

### ขั้น 3 · ตรวจผล (อ่านอย่างเดียว)

1. อ่าน `run.log` — ดูสรุปท้ายรอบ: จำนวนแต่ละสถานะ · จำนวนรอคนตรวจ · จำนวนคำขอ HTTP
2. `ls -la /home/ubuntu/crawlrun-a0655ef/staging/` — **คาดว่าว่าง** ถ้ามีไฟล์แปลว่ามี
   เอกสารเปลี่ยนจริง ซึ่งต้องหยุดและรายงาน ไม่ใช่แก้เอง
3. อ่านตัวเลขจากฐานข้อมูลเทียบ baseline

| รายการ | ต้องได้ |
|---|---|
| `courses` | 24 |
| `course_documents` | 31 |
| `course_chunks` | 9,039 |
| `mko.crawl_sources` | 12 แถว |
| สถานะ | `unchanged=12` |
| `needs_review` | 6 |
| `staging_path` ไม่ว่าง | 0 |
| `document_id` ไม่ว่าง | เท่าเดิม |
| `error_count` รวม | 0 |
| migration | ยังเป็น 001/002/003 เท่าเดิม |

**ถ้าข้อใดไม่ตรง → หยุดทันที รายงาน ไม่แก้ production ต่อเอง**

### ขั้น 4 · เก็บของ

```bash
# ลบโฟลเดอร์ทำงานเมื่อเก็บ run.log ไว้เป็นหลักฐานแล้ว
rm -rf /home/ubuntu/crawlrun-a0655ef
```

---

## ความเสี่ยงที่ต้องรู้ก่อนอนุมัติ

| ความเสี่ยง | ขนาด | การรับมือ |
|---|---|---|
| มีเอกสารบนเว็บคณะเปลี่ยนจริงตั้งแต่ 28 ก.ย. 01:59 | ต่ำ (ผ่านมาไม่กี่ชั่วโมง) | จะได้สถานะ `changed`/`downloaded` และมีไฟล์ใน staging — **เป็นพฤติกรรมที่ถูกต้อง** แต่ผลจะต่างจาก baseline ผมจะหยุดและรายงาน ไม่ลบไฟล์ ไม่แก้สถานะ |
| เว็บคณะล่มหรือช้าตอนรัน | ต่ำ | บางแถวจะเป็น `error` + `error_count` เพิ่ม รอบถัดไปจะกลับมาเอง rollback ได้จากสแนปช็อต |
| `--env-file` ใส่ตัวแปรเกินความจำเป็น | ต่ำ | คอนเทนเนอร์ชั่วคราว ไม่เปิดพอร์ต ลบด้วย `--rm` (เหตุผลที่ไม่ทำสำเนากรองอยู่ในข้อ 5) |
| ยิงคำขอไปเว็บคณะราว 14–26 ครั้ง | ต่ำ | หน่วง 1.5 วินาทีต่อคำขอตามเดิม User-Agent ระบุตัวตน เคารพ robots.txt |
| อิมเมจ `d1d1ba713412` ไม่มี tag จึงอาจถูก prune | ต่ำ | ตรวจแล้วว่ามีอยู่และคอนเทนเนอร์ที่รันอยู่ใช้มัน จึงถูก prune ไม่ได้ขณะที่ยังรัน |

---

## สรุปสิ่งที่จะเปลี่ยนบน production ถ้าอนุมัติ

| | |
|---|---|
| **เปลี่ยน** | แถวใน `mko.crawl_sources` (`last_checked_at` และฟิลด์สถานะ) — นี่คือตัว check เอง |
| **เปลี่ยน** | เพิ่มโฟลเดอร์ `/home/ubuntu/crawlrun-a0655ef/` แล้วลบทีหลัง |
| **เปลี่ยน** | สร้างคอนเทนเนอร์ชั่วคราวหนึ่งตัว ลบตัวเองเมื่อจบ |
| **ไม่เปลี่ยน** | อิมเมจ · compose · Caddy · service ที่รันอยู่ · schema · migration · credential · Supabase · `courses` / `course_documents` / `course_chunks` · โฟลเดอร์ deploy เดิม |

**ยังไม่ได้รันอะไร รอการอนุมัติรอบถัดไป · ยังไม่เริ่ม Phase 3**
