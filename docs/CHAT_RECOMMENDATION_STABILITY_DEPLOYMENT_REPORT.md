# Chat Recommendation Stability Fix — Controlled Production Deployment Report

วันที่ deploy: 2026-09-17T19:09:45Z (UTC) = 2026-09-18 02:09 เวลาไทย
ขอบเขต: backend only · ไม่มี migration / DB write · ไม่แตะ `.env` · ไม่แตะ frontend / postgres / ollama / caddy · ไม่ push
อ้างอิง: `docs/CHAT_RECOMMENDATION_STABILITY_FIX_REPORT.md`, `docs/CHAT_BROAD_RECOMMENDATION_RCA.md`

---

## 1. ก่อน deploy

**git scope** — diff เทียบ production เดิม (`6762333`) มีไฟล์เดียวใน `backend`: `backend/app/services/chat.py` (+38 / −63)
commit `fe6c57f497d362f1914d933c34c8798bfe0cef75` มี 5 ไฟล์
- `backend/app/services/chat.py`
- `eval/recommendation_reply_check.py` (เปลี่ยน expectation 2 ข้อ)
- `eval/recommendation_stability_check.py` (ใหม่ 12 tests)
- `docs/CHAT_RECOMMENDATION_STABILITY_FIX_REPORT.md`
- `docs/CHAT_BROAD_RECOMMENDATION_RCA.md`

ไฟล์ของรอบอื่น (รายงาน Find Major และ patch) ยังไม่ commit ตามที่ระบุให้ commit เฉพาะของรอบนี้

**secret scan** — ตรวจ 5 ไฟล์ด้วย pattern (API key / private key / DB URL ที่มีรหัสผ่าน / JWT) และเทียบกับค่าจริงของคีย์อ่อนไหวทั้ง 5 ตัวใน `.env` ของ server โดยไม่พิมพ์ค่า: **hits = 0**

**baseline (script หยุดทันทีถ้าไม่ตรง)**

| รายการ | ค่า |
|---|---|
| deployed commit | `6762333` |
| image | `sha256:3ae6bed7753568a6a961a5b0e20a7e8cc1136c09a406e1ec1781cf4dcf8f2223` |
| `STRUCTURED_ANSWERS` | `on` (.env และ container) |
| public health | 200 · restarts 0 · errors 0 |
| publication / live / decisions | `7999a1c2…` / 103 / 156 / 37 |
| publications / migration / courses / chunks | 4 / `002_mko_review_publish` / 24 / 9039 |
| `mko.shadow_answers` ก่อน deploy | 116 |
| drift ของไฟล์บน server | ตรงกับ `6762333` ทั้ง 63 ไฟล์ |

**release** — `git -c core.autocrlf=false archive fe6c57f backend llm` · SHA-256 `9f2001f02c9142c8eafa13ae60bf83224cbe57dc628e192256e2deebb19c6532` · 63 ไฟล์ · CR = 0 · manifest diff เทียบ `6762333` ต่างเพียงไฟล์เดียว: `backend/app/services/chat.py` `4f036291…` → `023bf307…`

**backup / rollback**
- `~/backups/env.before_chat_stability_20260917T190926Z` และ `docker-compose.prod.yml.before_chat_stability_20260917T190926Z` (สิทธิ์ 600, `sha256sum -c` OK ทั้งคู่)
- สำรอง `~/DEPLOYED_COMMIT.6762333`, `~/ROLLBACK.txt.6762333`
- tag image เดิมเป็น `course-advisor-system-backend:rollback-6762333` → `3ae6bed77535`
- ไม่ backup DB เพิ่ม เพราะ deploy นี้ไม่มี migration และไม่เขียน DB (backup ล่าสุด `prod_pre_find_major_fix_20260917T171410Z.dump` ยังใช้ได้)

## 2. Deploy

```
cp -a ~/release-fe6c57f/backend/. backend/ && cp -a ~/release-fe6c57f/llm/. llm/   # server files == fe6c57f (63)
docker compose -f docker-compose.prod.yml build backend
docker compose -f docker-compose.prod.yml up -d --no-deps backend                  # 19:09:45Z
```
`.env` SHA ไม่เปลี่ยน (`4d37472d…`) · container อื่นไม่ถูก recreate (caddy 8 days, frontend 13 days, postgres/ollama 4 weeks, db-viewer 3 days)

## 3. หลัง deploy ก่อนยิงคำถาม

| ตรวจ | ผล |
|---|---|
| internal `/health` / public `/api/health` | `{"status":"ok"}` / 200 |
| backend | image `0e159387…`, running, **restarts 0** |
| errors / traceback / exception | 0 |
| `STRUCTURED_ANSWERS` | `on` / `on` · `.env` และ compose SHA ไม่เปลี่ยน |
| `configured_mode()` / allow-list | `on` / `['careers','edition_year','objectives','total_credits']` |
| container files vs `fe6c57f` | ตรงทั้ง 63 ไฟล์ |
| โค้ดที่รันจริง | `_rationale_line` มีอยู่ · ตัวกรอง `supported = [...]` หายไปแล้ว · fallback ทั้งสองแบบคืนข้อความถูกต้อง · เหตุผลปกติส่งผ่านไม่ถูกแก้ |
| publication / counts | `7999a1c2…` / 103 / 156 / 37 / 4 / migration เดิม |

## 4. Controlled validation — 3 requests (เต็มเพดาน)

`POST https://stpnru-advisor.duckdns.org/api/chat` คำถาม `"สาขาไหนเหมาะกับคนชอบทำงานกับคอมพิวเตอร์"` ไม่มี history เว้นระยะ ≥ 12 วินาที (ไม่ใช้เคส regression เพิ่ม เพราะ 3 ครั้งนี้ครอบคลุมทั้งกรณีเหตุผลครบและกรณี fallback แล้ว)

| # | เวลา (UTC) | HTTP | เวลา | รายชื่อสาขา (ตามลำดับ) | ข้อความใต้ชื่อ |
|---|---|---|---|---|---|
| 1 | 19:10:45 | 200 | 7.4 s | วิทยาการคอมพิวเตอร์ → คอมพิวเตอร์แอนิเมชันและมัลติมีเดีย → เทคโนโลยีสารสนเทศ | #1 เหตุผลจริง · #2 และ #3 ใช้ fallback "เอกสาร…ไม่ได้ระบุไว้ตรงๆ" |
| 2 | 19:11:05 | 200 | 3.2 s | **เหมือนกันทุกตัว ลำดับเดียวกัน** | ทั้ง 3 รายการเป็นเหตุผลจริง |
| 3 | 19:11:20 | 200 | 2.9 s | **เหมือนกันทุกตัว ลำดับเดียวกัน** | #1 เหตุผลจริง · #2 และ #3 ใช้ fallback |

- **รายชื่อและลำดับตรงกับการจัดอันดับของ backend ทั้ง 3 ครั้ง** (CS .561 → Animation .542 → IT .528)
- **Gemini ไม่ได้ทำให้ candidate หายแม้แต่ครั้งเดียว** — ครั้งที่ 1 และ 3 คือกรณีที่โค้ดเดิมจะตัด Animation และ IT ทิ้ง (เหลือ CS สาขาเดียว) แต่ตอนนี้ยังอยู่ครบพร้อม fallback
- **ไม่มี marker `[[…]]` หลุดถึงผู้ใช้** ทั้ง 3 ครั้ง
- ถ้อยคำของเหตุผลต่างกันในแต่ละครั้ง ซึ่งเป็นพฤติกรรมที่ยอมรับได้ตามที่ตกลงไว้
- log ยืนยัน: `POST /chat-web` 3 ครั้ง · เรียก Gemini 6 ครั้ง (ขั้นตรวจ intent + ขั้นเขียนเหตุผล อย่างละครั้งต่อคำถาม)

เทียบกับก่อนแก้ (log เดิมของคำถามเดียวกัน ไม่มี history): ได้ผล 4 แบบใน 5 ครั้ง — ไม่มีสาขาเลย / CS / CS+IT / CS+Animation

## 5. หลัง smoke

| ตรวจ | ผล |
|---|---|
| public health / internal | 200 / `{"status":"ok"}` |
| backend | image `0e159387…`, running, restarts 0 |
| errors / traceback / exception · HTTP 5xx | 0 · 0 |
| `STRUCTURED_ANSWERS` · `.env` SHA | `on` · `4d37472d…` ไม่เปลี่ยน |
| publication / live values / list items | `7999a1c2…` / 103 / 156 |
| review_decisions / publications / migration | 37 / 4 / `002_mko_review_publish` |
| `mko.shadow_answers` | 116 → 119 (+3 = log ของ 3 คำถามนี้ตามปกติ ไม่ใช่การเปลี่ยนข้อมูลหลักสูตร) |
| container อื่น | ไม่ถูกแตะ |

บันทึกบน server: `~/DEPLOYED_COMMIT` → `commit=fe6c57f` · `~/ROLLBACK.txt` เพิ่มขั้นตอนของรอบนี้ไว้บนสุด · log: `~/predeploy.sh` output, `~/deploy_chat_stability.log`

## 6. Rollback

ไม่พบ regression จึงไม่ได้ใช้ · ขั้นตอนที่เตรียมไว้
```bash
cd ~/course-advisor-system
cp -a ~/release-6762333/backend/. backend/ && cp -a ~/release-6762333/llm/. llm/
docker tag course-advisor-system-backend:rollback-6762333 course-advisor-system-backend:latest
docker compose -f docker-compose.prod.yml up -d --no-build --no-deps backend
# check: image -> sha256:3ae6bed77535… · STRUCTURED_ANSWERS ยัง on · health 200
```

## 7. ข้อจำกัดที่ยังอยู่

- ความครบถ้วนของคำแนะนำกว้างยังจำกัดด้วย margin 0.04 และ limit 3 (ไม่ได้แก้ตามขอบเขต) ระบบจึงยังอ้างไม่ได้ว่าเป็น "ทุกสาขาที่เกี่ยวข้อง"
- ข้อความ `interest` ที่ LLM คัดมาก่อนจับคู่ยังผ่านโมเดล (ข้อ B ใน RCA) และยังไม่มี log เก็บค่านี้
- ครั้งที่ 1 และ 3 แสดงว่าขั้นเขียนเหตุผลยังตัดสินว่า "ไม่มีข้อมูลรองรับ" อยู่บ่อย ซึ่งตอนนี้กระทบแค่ถ้อยคำ ไม่กระทบรายชื่อ
- รายงานนี้ยังไม่ commit

---

DEPLOYED COMMIT: `fe6c57f497d362f1914d933c34c8798bfe0cef75`

BACKEND IMAGE: `sha256:0e15938743a94c16f923fb21e6151abe6ef55b3f8385a134aee27db92d304197`

ROLLBACK TARGET: commit `6762333` · image tag `course-advisor-system-backend:rollback-6762333` (`3ae6bed77535`) · release `~/release-6762333`

STRUCTURED_ANSWERS: `on` (ไม่ถูกแตะ · `.env` SHA `4d37472d…` เท่าเดิมทั้งก่อนและหลัง)

HEALTH: public 200 · internal `{"status":"ok"}` ทั้งก่อนและหลัง smoke

RESTARTS/ERRORS: restarts 0 · errors/traceback/exception 0 · HTTP 5xx 0

PRODUCTION REQUESTS USED: 3 / 3 (chat) · ไม่ใช้เคสเพิ่ม · ไม่รัน behaviour_check · ไม่ batch

CANDIDATES REQUEST 1: วิทยาการคอมพิวเตอร์ → คอมพิวเตอร์แอนิเมชันและมัลติมีเดีย → เทคโนโลยีสารสนเทศ

CANDIDATES REQUEST 2: วิทยาการคอมพิวเตอร์ → คอมพิวเตอร์แอนิเมชันและมัลติมีเดีย → เทคโนโลยีสารสนเทศ

CANDIDATES REQUEST 3: วิทยาการคอมพิวเตอร์ → คอมพิวเตอร์แอนิเมชันและมัลติมีเดีย → เทคโนโลยีสารสนเทศ

CANDIDATE ORDER STABLE: YES — เหมือนกันทั้งชื่อและลำดับทั้ง 3 ครั้ง และตรงกับอันดับของ backend

GEMINI REMOVED CANDIDATE: NO — ครั้งที่ 1 และ 3 เป็นกรณีที่โค้ดเดิมจะตัดสาขาออก แต่ยังอยู่ครบ

FALLBACK/MARKER ISSUE: ไม่มี — fallback แสดงถูกกรณี และไม่มี `[[…]]` หลุดถึงผู้ใช้

DB/PUBLICATION CHANGED: NO — publication / 103 / 156 / 37 / 4 / migration เท่าเดิม · `shadow_answers` +3 คือ log ของคำถามทดสอบตามปกติ

ROLLBACK NEEDED: NO

FINAL RESULT: PASS
