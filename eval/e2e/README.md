# Isolated E2E test harness — TEST DATA ONLY

ชุดนี้พิสูจน์ว่า pipeline นำเข้าเอกสารทำงานครบวงจร
**ในสภาพแวดล้อมที่แยกอิสระจาก production โดยสมบูรณ์**

```
Test PDF -> TEST CANDIDATE -> Admin Review -> Approve
         -> Worker -> extract -> chunk -> embed (bge-m3/1024) -> pgvector -> verify
```

---

## คำเตือนที่ต้องอ่านก่อนใช้

| คำ | ความหมาย |
|---|---|
| **PRODUCTION CANDIDATE** | PDF ที่ใหม่หรือเปลี่ยนจริงจาก `sci.pnru.ac.th` — สิ่งเดียวที่อนุญาตให้ ingest เข้าคลังจริง |
| **TEST CANDIDATE** | PDF จำลองที่มีอยู่เฉพาะในสภาพแวดล้อมนี้เท่านั้น |

**ห้ามนำมาปนกัน** และ **การที่ชุดนี้ผ่านไม่ใช่การอนุญาตให้รัน ingestion บน production**

---

## การแยกที่ชุดนี้รับประกัน

1. **compose project ของตัวเอง** — `sci-advisor-e2e` ไม่ใช่ `course-advisor-system`
2. **PostgreSQL ของตัวเอง** — ฐานข้อมูล `e2e_test` คนละอินสแตนซ์กับ production
3. **Ollama ของตัวเอง** — โมเดลอยู่ใน volume ของ project นี้
4. **เครือข่ายของตัวเอง** — ไม่ได้ผูกกับเครือข่ายของ production
5. **ไม่ publish พอร์ตใดออกสู่ host** — ตัวทดสอบรันใน `e2e-runner` จึงเรียกบริการอื่น
   ด้วยชื่อ service ได้โดยตรง
6. **volume ของตัวเองทั้งหมด** — ไม่มี bind mount ไปยังโฟลเดอร์ของ production
7. **ไม่ใช้ `.env` ของโปรเจกต์** — ค่าทุกตัวอยู่ในไฟล์ compose และเป็นค่าทดสอบล้วน
8. **ด่านสามชั้นในโค้ด** — ตรวจ DSN ก่อนต่อ → `SELECT current_database()` ต้องเป็น
   `e2e_test` → `course_chunks` ต้องไม่เกิน 1000 แถว (production มี 9039)

`sci.pnru.ac.th` ถูก alias ให้ชี้ `e2e-fakesite` **เฉพาะภายในเครือข่ายนี้**
ทำให้ crawler ตัวจริงผ่านด่าน `ALLOWED_HOSTS` ได้โดยไม่ต้องแก้ source แม้บรรทัดเดียว
และไม่มีคำขอใดออกไปถึงเว็บของคณะจริง

---

## วิธีรัน (จาก root ของ repo)

```bash
# 1) ยกฐานข้อมูลและ Ollama ขึ้นก่อน
docker compose -p sci-advisor-e2e -f eval/e2e/docker-compose.e2e.yml up -d e2e-postgres e2e-ollama

# 2) ดึงโมเดล embedding ลง Ollama ของ project ทดสอบ (ประมาณ 1.2 GB)
docker compose -p sci-advisor-e2e -f eval/e2e/docker-compose.e2e.yml exec e2e-ollama ollama pull bge-m3

# 3) ยกบริการที่เหลือ (build backend และ runner จาก Dockerfile ชุดเดียวกับ production)
docker compose -p sci-advisor-e2e -f eval/e2e/docker-compose.e2e.yml up -d

# 3.1) ตั้งเจ้าของ volume ให้เป็น uid 1001 ซึ่งเป็น uid ที่ worker รัน
#      Docker สร้าง volume ใหม่เป็นของ root แต่อิมเมจ worker ตั้ง USER worker (1001)
#      การตั้งเป็น 1001 ยังตรงกับ production ที่ documents/ และ staging/ เป็นของ uid 1001
docker run --rm --network none \
  -v sci-advisor-e2e_e2e_site:/a -v sci-advisor-e2e_e2e_staging:/b \
  -v sci-advisor-e2e_e2e_documents:/c -v sci-advisor-e2e_e2e_out:/d \
  busybox:latest sh -c 'chown 1001:1001 /a /b /c /d && chmod 755 /a /b /c /d'

# 4) สร้าง Test PDF ให้เว็บจำลองมีของเสิร์ฟ
docker compose -p sci-advisor-e2e -f eval/e2e/docker-compose.e2e.yml \
  exec e2e-runner python -m eval.e2e.make_test_pdf

# 5) รันชุดทดสอบทั้งหมด
docker compose -p sci-advisor-e2e -f eval/e2e/docker-compose.e2e.yml \
  exec e2e-runner python -m eval.e2e.run_e2e --report /out/e2e_report.json

# 6) เก็บกวาดให้หมด
docker compose -p sci-advisor-e2e -f eval/e2e/docker-compose.e2e.yml down -v --remove-orphans
```

---

## ไฟล์ในชุดนี้

| ไฟล์ | หน้าที่ |
|---|---|
| `docker-compose.e2e.yml` | นิยามสภาพแวดล้อมทดสอบทั้งห้าบริการ · network alias · volume แยก |
| `fakesite/server.py` | เว็บจำลองของคณะ · เสิร์ฟ `programs.php`, `program_detail.php?id=1`, PDF · `robots.txt` ตอบ 404 |
| `make_test_pdf.py` | สร้าง `TEST_CS_CURRICULUM_E2E.pdf` ด้วย PyMuPDF · คำนวณ sha256 จากไฟล์จริง |
| `seed.py` | apply migrations 001–004 · seed `TEST101` และผู้ใช้ทดสอบสองบัญชี · ด่านความปลอดภัย |
| `run_e2e.py` | ชุดทดสอบหลัก · เรียกโค้ด production ตัวจริงทุกขั้น · เขียนรายงาน JSON |
| `README.md` | ไฟล์นี้ |

**ไม่มีไฟล์ใดในชุดนี้แก้ source ของ production** — `pipeline/`, `backend/`, `llm/`,
`db/` และ compose ของ production ไม่ถูกแตะแม้ไบต์เดียว

---

## เรื่องรหัสผ่าน

* รหัสผ่านของผู้ใช้ทดสอบถูก**สุ่มขึ้นในหน่วยความจำ**โดย `run_e2e.py` ทุกครั้งที่รัน
  ไม่เขียนลงไฟล์ ไม่พิมพ์ออกหน้าจอ ไม่ลงรายงาน
* ค่าลับของโครงสร้างพื้นฐานในไฟล์ compose (รหัส postgres, JWT secret) เป็น
  **ค่าทดสอบที่ใช้ครั้งเดียวแล้วหายไปพร้อม volume** ไม่ได้ใช้ที่อื่นและไม่เกี่ยวกับ production
* **ห้ามใช้อีเมลหรือรหัสผ่านจริงของเจ้าของโปรเจกต์กับชุดนี้**

---

## ข้อจำกัดที่ต้องรู้

| # | เรื่อง |
|---|---|
| 1 | **`ivfflat lists=100` กับข้อมูลน้อย** — ฐานทดสอบมี chunk ไม่กี่แถว list ส่วนใหญ่จึงว่าง และ `ivfflat.probes` เริ่มต้น = 1 อาจคืน 0 แถว · harness ตั้ง `SET LOCAL ivfflat.probes = 100` ในคำค้น **ไม่ได้แก้ schema หรือ index** ผลจึงพิสูจน์ว่า vector ถูกสร้าง มิติถูก เก็บได้ และค้นเจอ — **ไม่ได้พิสูจน์คุณภาพ ANN ที่ scale จริง** |
| 2 | **Test PDF ไม่เหมือน มคอ.2 จริง** — พิสูจน์กลไกของ pipeline ไม่ใช่คุณภาพการสกัดข้อมูลจากเอกสารจริง |
| 3 | **เว็บจำลองไม่เหมือนเว็บคณะจริง** — การทดสอบกับเว็บจริงอยู่ใน `CRAWLER_PRODUCTION_VERIFY_REPORT.md` |
| 4 | **`e2e-runner` mount repo ที่ `/repo` แบบอ่านอย่างเดียว** — อิมเมจ worker มีแต่ `pipeline/` และ `llm/` จึงต้อง mount เพิ่มเพื่อให้เข้าถึง `backend/`, `db/`, `eval/` · source ที่รันคือ working tree เดียวกับที่ตรวจไว้ |
| 5 | **`e2e-runner` mount staging เป็น rw** — ใน production ตัว crawler กับ worker เป็นคนละคอนเทนเนอร์ (crawler rw · worker ro) ที่นี่รวมเป็นตัวเดียว · ส่วน `e2e-backend` ยังเป็น **ro** เหมือน production ซึ่งเป็นจุดที่สำคัญต่อความปลอดภัย |

---

## STOP

ชุดนี้ไม่แตะ production เลย — แต่ **ห้ามตีความว่าผลผ่าน = อนุญาตให้รัน ingestion บน production**
