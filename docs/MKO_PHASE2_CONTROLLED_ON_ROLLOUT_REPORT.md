# MKO Phase 2 — Controlled ON Rollout (Step B)

วันที่: 2026-09-17 (UTC)
ขอบเขต: เปลี่ยน `STRUCTURED_ANSWERS=shadow` → `on` บน production เท่านั้น
ไม่แก้ code, ไม่ build/deploy image ใหม่, ไม่ commit, ไม่มีงาน DB/review/publish/migration, ไม่ push

## 1. Baseline ก่อนเปลี่ยน flag (ตรวจแล้ว ตรงทุกค่า)

| รายการ | ค่า |
|---|---|
| deployed commit (`~/DEPLOYED_COMMIT`) | `9879653` |
| backend image | `sha256:b046f9086076776c26da78b7989636ddc930e2a4bde8ddacb4a8341496859e83` |
| backend | running, restarts 0, started 2026-09-17T07:40:41Z |
| flag | `.env` line 20 `STRUCTURED_ANSWERS=shadow`, container env `shadow` |
| live publication | `7999a1c2-e2fd-4b19-98d1-b50b3212f8d9` |
| live values / list items | 103 / 156 |
| review_decisions | 37 |
| publications | 4 |
| mko.shadow_answers | 94 |
| migration ล่าสุด | `002_mko_review_publish` |
| health | public `/api/health` 200, internal `{"status":"ok"}` |
| error/traceback/exception ใน log backend | 0 |
| `.env` | 20 บรรทัด, SHA-256 `b8a692d14e0cdb5c2a81243355b820b8c5a6bc76aac8d3d6d5607acc65071753` |
| `docker-compose.prod.yml` | SHA-256 `fc95afb84355bb953880d9211ce9211677517351630aacc8bfef791683530d1f` |

## 2. Backup `.env`

- ไฟล์: `~/backups/env.before_on_rollout_20260917T092413Z`
- permissions `-rw-------` (600), owner ubuntu
- SHA-256 `b8a692d14e0cdb5c2a81243355b820b8c5a6bc76aac8d3d6d5607acc65071753` (ตรงกับ `.env` ก่อนเปลี่ยน)
- `.sha256` เก็บคู่กัน; `sha256sum -c` → `OK`

## 3. การเปลี่ยน flag และ restart

- diff `backup → current` มีเพียง:
  ```
  20c20
  < STRUCTURED_ANSWERS=shadow
  ---
  > STRUCTURED_ANSWERS=on
  ```
- `.env` ใหม่: 20 บรรทัด, SHA-256 `4d37472dc9a6055b2198c95fe58ab15008056586733a03c865a6b3763fe13d27`
- restart backend เท่านั้น เวลา 2026-09-17T09:24:13Z:
  `docker compose -f docker-compose.prod.yml up -d --no-deps --no-build backend`
  (ต้อง recreate เพราะ compose interpolate `${STRUCTURED_ANSWERS:-off}`; restart ธรรมดาจะไม่รับค่าใหม่)
- ผล: recreate → started 09:24:13.709Z, image เดิม `b046f908…`, restarts 0
- container อื่น (postgres, ollama, caddy, frontend, db-viewer) ไม่ถูกแตะ — uptime เดิม

## 4. ตรวจหลัง restart ก่อนยิง chat

| ตรวจ | ผล |
|---|---|
| container env `STRUCTURED_ANSWERS` | `on` |
| `configured_mode()` | `on` |
| `USER_FACING_FIELDS` == {careers, edition_year, objectives, total_credits} | True |
| `admission` อยู่ใน allow-list | False |
| public `/api/health` | 200 |
| internal `/health` | `{"status":"ok"}` |
| error/traceback/exception | 0 |
| publication / live / review_decisions / shadow_answers | `7999a1c2…` / 103 / 156 / 37 / 94 (ไม่เปลี่ยน) |

## 5. Controlled smoke (10 HTTP requests)

ยิงผ่าน `https://stpnru-advisor.duckdns.org/api/chat` ทีละ request ช่วง 09:26:16–09:27:33Z ไม่ใช้ behaviour_check ไม่ batch
เคส follow-up chain นับเป็น 2 requests จึง **ตัดเคส 1 (CS total credits)** ออกตามคำสั่ง

| # | คำถาม | คาด | HTTP | เวลา (s) | served_source | route / reason | field | structured_status | publication | ข้อเท็จจริงที่ใช้ | คำตอบที่ผู้ใช้เห็น |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2 | หลักสูตรวิทยาศาสตรมหาบัณฑิต สาขาวิชาการจัดการเทคโนโลยีการเกษตรและบริหารทรัพยากรชุมชน เรียนกี่หน่วยกิต | structured | 200 | 0.8 | structured | structured / single_programme_field | total_credits | answered | 7999a1c2 | ป.โท (พ.ศ. 2568) agri68_master.pdf p6 = 36 | "…มหาบัณฑิต … (พ.ศ. 2568) … 36 หน่วยกิต / ที่มา: agri68_master.pdf หน้า 6" |
| 3 | หลักสูตรปรัชญาดุษฎีบัณฑิต สาขาวิชาการจัดการเทคโนโลยีการเกษตรและบริหารทรัพยากรชุมชน เรียนกี่หน่วยกิต | structured | 200 | 0.2 | structured | structured / single_programme_field | total_credits | answered | 7999a1c2 | ป.เอก (พ.ศ. 2568) agri68_phd.pdf p6 = 48 | "…ปรัชญาดุษฎีบัณฑิต … 48 หน่วยกิต / ที่มา: agri68_phd.pdf หน้า 6" |
| 4 | หลักสูตรคณิตศาสตร์ปรับปรุงปีไหน | structured | 200 | 0.2 | structured | structured / single_programme_field | edition_year | answered | 7999a1c2 | ma69.pdf p1 = 2569; ma64.pdf p2 = 2564 | "คณิตศาสตร์ มีหลักสูตรฉบับ พ.ศ. 2569 และ พ.ศ. 2564 / ที่มา: ma69.pdf หน้า 1; ma64.pdf หน้า 2" |
| 5 | สาขาคหกรรมศาสตร์จบไปทำอาชีพอะไรได้บ้าง | structured | 200 | 0.1 | structured | structured / single_programme_field | careers | answered | 7999a1c2 | ศศ.บ. คหกรรมศาสตร์ (พ.ศ. 2564) ds2564.pdf = 11 items | รายการ 11 ข้อ "ที่มา: ds2564.pdf หน้า 2–3" |
| 6 | หลักสูตรคณิตศาสตร์ พ.ศ. 2569 มีวัตถุประสงค์อะไรบ้าง | structured | 200 | 0.1 | structured | structured / single_programme_field | objectives | answered | 7999a1c2 | ma69.pdf p1 = 4 items | รายการ 4 ข้อ "ที่มา: ma69.pdf หน้า 1" |
| 7 **CRITICAL** | หลักสูตรเทคโนโลยีสารสนเทศ พ.ศ. 2566 คุณสมบัติของผู้เข้าศึกษามีอะไรบ้าง | **rag** | 200 | 0.1 | **rag** | structured / single_programme_field | admission | answered (shadow เท่านั้น) | 7999a1c2 (log เท่านั้น) | it66.pdf p16 = 3 items (ไม่ถูก serve) | คำตอบ RAG แบบเดิม ("ผู้เข้าศึกษาใน…เทคโนโลยีสารสนเทศ … ต้องมีคุณสมบัติดังนี้: 1. สำเร็จการศึกษาระดับมัธยมศึกษาตอนปลาย…") ไม่มีบรรทัด "ที่มา:" แบบ structured |
| 8 | สาขาคอมพิวเตอร์แอนิเมชันและมัลติมีเดียจบไปทำอาชีพอะไรได้บ้าง | rag | 200 | 0.1 | rag | structured / single_programme_field | careers | no_data | – | – | คำตอบ RAG ("ผู้สำเร็จการศึกษา… สามารถประกอบอาชีพได้ดังนี้: - นักผลิตสื่อแอนิเมชัน…") |
| 9 | สาขาการจัดการเทคโนโลยีการเกษตรและบริหารทรัพยากรชุมชน เรียนกี่หน่วยกิต | rag | 200 | 3.0 | rag | rag / multiple_degree_levels | total_credits | not_applicable | – | – | คำตอบ RAG ระบุทั้ง ป.โท 36 และ ป.เอก 48 (เนื้อหาจาก RAG ไม่ใช่ structured เลือกระดับเอง) |
| 10a | หลักสูตรคณิตศาสตร์ พ.ศ. 2569 เรียนกี่หน่วยกิต | structured | 200 | 0.4 | structured | structured / single_programme_field | total_credits | answered | 7999a1c2 | ma69.pdf p1 = 124 | "…คณิตศาสตร์ (พ.ศ. 2569) … 124 หน่วยกิต / ที่มา: ma69.pdf หน้า 1" |
| 10b | แล้วฉบับ พ.ศ. 2564 ล่ะ (history = 10a) | structured | 200 | 2.5 | structured | structured / single_programme_field | total_credits | answered | 7999a1c2 | ma64.pdf p6 = 130 | "…คณิตศาสตร์ (พ.ศ. 2564) … 130 หน่วยกิต / ที่มา: ma64.pdf หน้า 6" |

ทุกแถวใน `mko.shadow_answers` ของ smoke มี `comparison_detail.configured_mode = on` ครบ 10/10
10b: `has_history = true`, `interpreted_question = "หลักสูตรคณิตศาสตร์ พ.ศ. 2564 เรียนกี่หน่วยกิต"`
แถวที่ serve structured ทั้งหมดมี `served_reply == structured_answer` และ `comparison = not_compared` (ตามการออกแบบ)
หมายเหตุ: เคส 7 และ 8 ตอบเร็ว (0.1 s) เพราะเป็นคำตอบ RAG ที่มีอยู่แล้วใน `chat_answer_cache` — เป็นเส้นทาง RAG ปกติ ไม่ใช่ structured

## 6. จำนวน structured vs RAG (แถวทั้งหมดตั้งแต่ ON 09:24:13Z)

| served_source | จำนวน |
|---|---|
| structured | 7 (เคส 2, 3, 4, 5, 6, 10a, 10b) |
| rag | 3 (เคส 7, 8, 9) |
| รวม | 10 (ทั้งหมดเป็น smoke; ไม่มี traffic อื่นในช่วงนี้) |

## 7. Safeguards (query READ ONLY … ROLLBACK, ช่วงตั้งแต่ ON)

| ตรวจ | ผล |
|---|---|
| admission ที่ served_source = structured | **0** |
| field นอก allow-list ที่ served_source = structured | **0** |
| served structured ขณะ route ≠ structured หรือ status ≠ answered (no_data / multiple_degree_levels) | **0** |
| structured rows ที่ publication ≠ `7999a1c2-e2fd-4b19-98d1-b50b3212f8d9` | **0** |
| structured rows ที่ served_reply ≠ structured_answer | 0 |
| facts ที่ course_id ไม่อยู่ใน course_ids ของคำถาม (cross-programme) | 0 |
| structured answer ถูกเขียนลง `chat_answer_cache` | 0 |

- **Admission safeguard:** ผ่าน — IT 2566 admission ถูก detect เป็น structured/answered แต่ allow-list กันไว้ ผู้ใช้ได้ RAG (served_source = rag); structured answer ถูก log เพื่อเปรียบเทียบเท่านั้น
- **No-data safeguard:** ผ่าน — Animation careers `no_data` → RAG
- **Degree:** ผ่าน — ระบุ ป.โท ได้ 36 (agri68_master), ระบุ ป.เอก ได้ 48 (agri68_phd), ไม่ระบุระดับ → `multiple_degree_levels` → RAG ไม่มีการเลือกระดับแทนผู้ใช้
- **Year/edition:** ผ่าน — edition_year แสดงทั้ง 2569 และ 2564; objectives ระบุ 2569 ใช้ ma69.pdf
- **Follow-up:** ผ่าน — 2569 = 124 (ma69), เปลี่ยนเป็น 2564 = 130 (ma64) ไม่ข้ามฉบับ
- ไม่มีคำตอบข้าม programme / edition / degree

## 8. สถานะหลัง smoke

| รายการ | ก่อน | หลัง |
|---|---|---|
| live publication | 7999a1c2… | 7999a1c2… |
| live values / list items | 103 / 156 | 103 / 156 |
| review_decisions | 37 | 37 |
| publications | 4 | 4 |
| migration | 002_mko_review_publish | 002_mko_review_publish |
| mko.shadow_answers | 94 | 104 (+10 = log ของ smoke 10 requests ตามปกติ) |
| backend image | b046f908… | b046f908… |
| backend restarts | 0 | 0 (หลัง recreate) |
| public health | 200 | 200 |
| internal health | ok | ok |
| error/traceback/exception ใน log (ตั้งแต่ start) | 0 | 0 |
| warning fallback ของ structured/shadow | – | 0 |
| HTTP 5xx ใน log | – | 0 |
| `.env` line 20 / container env | shadow | `on` / `on` |

## 9. Rollback

Rollback criteria ที่ตรวจ: programme/edition/degree ผิด, admission หรือ no_data หรือ field นอก allow-list ถูก serve structured, HTTP/backend error ใหม่, health ผิดปกติ — **ไม่พบข้อใด → ไม่ต้อง rollback**

ขั้นตอน rollback (พร้อมใช้, ยังไม่ได้ใช้):
```bash
cd ~/course-advisor-system
cp -p ~/backups/env.before_on_rollout_20260917T092413Z .env   # หรือ sed line 20 กลับเป็น shadow
sha256sum .env   # ต้องได้ b8a692d14e0c…
docker compose -f docker-compose.prod.yml up -d --no-deps --no-build backend
docker exec course-advisor-system-backend-1 printenv STRUCTURED_ANSWERS   # shadow
# verify configured_mode() = shadow, /api/health = 200 แล้ว STOP
```
rollback ระดับ code (ถ้าจำเป็นในอนาคต ต้องได้รับอนุมัติแยก): image tag `rollback-8d6d271`

**Final production mode: `STRUCTURED_ANSWERS=on`**

## 10. ข้อจำกัดที่ยอมรับ (ยังคงอยู่)

- admission ยังตอบด้วย RAG (structured แสดงเฉพาะหมวด มคอ.2 ไม่ครบเกณฑ์อายุ/GPAX/ข้อบังคับมหาวิทยาลัย)
- glyph "น้ า" ใน en65 careers (P2 live) — ยอมรับ ไม่แก้รอบนี้
- whitespace ภายในรายการ objectives (เช่น "ประยุกต์ใช้ ได้", "มี ความมุ่งมั่น") — ยอมรับ
- ชื่อหลักสูตรเก่าที่ superseded — ยอมรับ
- programme ที่ยังไม่มีข้อมูล live (no_data) และคำถามที่ไม่ระบุระดับปริญญาไปทาง RAG ตามเดิม
- ขั้นเตรียม RAG ยังทำงานก่อนตัดสิน structured (ยังไม่ optimize ตามคำสั่ง)
- smoke ไม่ได้ครอบคลุมเคส 1 (CS total credits) เพราะเพดาน 10 requests
- รายงาน Step A และรายงานนี้ยังไม่ commit

## ผลสรุป

PHASE 2 CONTROLLED ON ROLLOUT: PASS
