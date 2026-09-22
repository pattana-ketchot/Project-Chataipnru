# Chat Recommendation Clarification Gate — Controlled Production Deployment

วันที่ deploy: 2026-09-17T20:32:47Z (UTC) = 2026-09-18 03:32 เวลาไทย
อ้างอิง: `docs/CHAT_RECOMMENDATION_CLARIFICATION_FIX.md` · `docs/CHAT_RECOMMENDATION_CLARIFICATION_RCA.md` · `docs/CHAT_RECOMMENDATION_CLARIFICATION_VALIDATION.md`
ขอบเขต: backend only · ไม่แก้ implementation เพิ่มก่อน deploy · ไม่ push

---

## 1. Pre-deploy

| ตรวจ | ผล |
|---|---|
| branch / worktree | `mko-phase2` · `D:\workspace\course-advisor-system-mko2` |
| tracked diff ก่อน commit | `backend/app/services/chat.py` ไฟล์เดียว |
| production commit | `fe6c57f` ตรงกับรายงาน |
| production image | `sha256:0e15938743a94c16f923fb21e6151abe6ef55b3f8385a134aee27db92d304197` ตรงกับรายงาน |
| health / restarts / errors | 200 / 0 / 0 |
| `STRUCTURED_ANSWERS` | `on` |
| publication / live / decisions | `7999a1c2…` / 103 / 156 / 37 |
| drift ของไฟล์บน server | ตรงกับ `fe6c57f` ทั้ง 63 ไฟล์ |
| secret scan (3 ไฟล์) | ไม่พบ |

backup: `~/backups/env.before_clarification_20260917T203220Z` และ `docker-compose.prod.yml.before_clarification_20260917T203220Z` (สิทธิ์ 600, `sha256sum -c` OK) · สำรอง `~/DEPLOYED_COMMIT.fe6c57f`, `~/ROLLBACK.txt.fe6c57f` · tag rollback image `rollback-fe6c57f` → `0e15938743a9`

## 2. Commit

`f2450a026ab05fac2142e996089a47bbefaf56ec` — *fix: ask what the student likes before ranking programmes for them*

ไฟล์ใน commit (ตรงกับที่อนุญาต ไม่มีไฟล์อื่นปน)
- `backend/app/services/chat.py`
- `eval/recommendation_clarification_check.py`
- `docs/CHAT_RECOMMENDATION_CLARIFICATION_FIX.md`

ไฟล์ที่ **ไม่** ถูก stage: รายงาน RCA/validation ของรอบนี้, รายงาน deploy ของรอบก่อน, เอกสารและ patch ของ Find Major (ทั้งหมดยังเป็น untracked ตามเดิม) · ไม่มี working copy ของหน้าเว็บที่เพื่อนดูแลอยู่ในนี้เลย

## 3. Release package

`git -c core.autocrlf=false archive f2450a0 backend llm` → SHA-256 `8d54cc9e738ddfbbee92314032ea745781db414bc8e098378f5c6e290a6508e2` · 63 ไฟล์ · CR = 0
manifest diff เทียบ `fe6c57f`: ต่างไฟล์เดียว `backend/app/services/chat.py` `023bf307…` → `3de28007…`

## 4. Deploy

```
cp -a ~/release-f2450a0/backend/. backend/ && cp -a ~/release-f2450a0/llm/. llm/   # server files == f2450a0
docker compose -f docker-compose.prod.yml build backend
docker compose -f docker-compose.prod.yml up -d --no-deps backend                   # 20:32:47Z
```
`.env` SHA ไม่เปลี่ยน · container อื่นไม่ถูกแตะ (caddy Up 8 days, frontend Up 13 days, postgres/ollama Up 4 weeks, db-viewer Up 3 days)

## 5. Post-deploy (ก่อนยิงคำถาม)

| ตรวจ | ผล |
|---|---|
| internal `/health` / public | `{"status":"ok"}` / 200 |
| backend | image `cbec7c94…`, running, restarts 0 |
| errors / traceback / exception | 0 |
| `STRUCTURED_ANSWERS` | `on` / `on` · `.env` และ compose SHA ไม่เปลี่ยน |
| container files vs `f2450a0` | ตรงทั้ง 63 ไฟล์ |
| โค้ดที่รันจริง | มี `NO_PREFERENCE` · gate อยู่ใน `prepare_answer` · ข้อความ clarification ขึ้นต้นด้วย `_FOLLOW_UP_LEAD` |
| publication / counts | `7999a1c2…` / 103 / 156 / 37 / 4 / migration เดิม |

## 6. Controlled production validation — 3 requests

`POST https://stpnru-advisor.duckdns.org/api/chat` ไม่มีบทสนทนาก่อนหน้า เว้นระยะ ≥ 12 วินาที

**TEST A — "เรียนไรดี"** · HTTP 200 · 1.6 s · **ไม่มีรายชื่อสาขาเลย**
```
เพื่อให้แนะนำได้ตรงขึ้น บอกผมเพิ่มได้ไหมครับว่าชอบวิชาอะไร สนใจด้านไหน ถนัดอะไร
หรืออยากทำงานแบบไหนในอนาคต แล้วผมจะช่วยดูให้ว่าสาขาไหนใกล้เคียงบ้าง
ถ้ายังไม่แน่ใจ จะขอดูรายชื่อสาขาทั้งหมดของคณะก่อนก็ได้ครับ
```

**TEST B — "แนะนำสาขาหน่อย"** · HTTP 200 · 0.9 s · **ไม่มีรายชื่อสาขาเลย** · ข้อความเดียวกับ A ทุกตัวอักษร

**TEST C — "ชอบเขียนโปรแกรมควรเรียนสาขาไหน"** · HTTP 200 · 6.9 s · ได้คำแนะนำตามเส้นทางเดิม
1. วิทยาการคอมพิวเตอร์ — เหตุผลอ้างกลุ่มเทคโนโลยีและวิธีการทางซอฟต์แวร์
2. เทคโนโลยีสารสนเทศ — เหตุผลอ้างทักษะการเขียนโปรแกรมและการพัฒนาโปรแกรมประยุกต์
พร้อมบรรทัดที่มาและคำถามต่อยอดเหมือนเดิม

**หลักฐานว่าไม่ได้จัดอันดับในเคส A/B** — log ของ backend: `POST /chat-web` 3 ครั้ง, เรียก Gemini **4 ครั้ง** (A = 1 ครั้งสำหรับขั้นจำแนกเจตนา, B = 1 ครั้ง, C = 2 ครั้ง คือจำแนกเจตนา + เขียนเหตุผล) ถ้า A/B ยังเข้าการจัดอันดับจะต้องเป็น 6 ครั้ง · เวลาตอบของ A/B (1.6 s และ 0.9 s) เทียบกับ C (6.9 s) สอดคล้องกัน

## 7. หลัง validation

| ตรวจ | ผล |
|---|---|
| public / internal health | 200 / `{"status":"ok"}` |
| backend | image `cbec7c94…`, running, restarts 0 |
| errors / traceback / exception · HTTP 5xx | 0 · 0 |
| `STRUCTURED_ANSWERS` · `.env` SHA | `on` · `4d37472d…` ไม่เปลี่ยน |
| publication / live values / list items | `7999a1c2…` / 103 / 156 |
| review_decisions / publications / migration | 37 / 4 / `002_mko_review_publish` |
| `mko.shadow_answers` | 124 → 127 (+3 = log ของคำถามทดสอบ ไม่ใช่การเปลี่ยนข้อมูลหลักสูตร) |
| container อื่น | ไม่ถูกแตะ |

บันทึกบน server: `~/DEPLOYED_COMMIT` → `commit=f2450a0` · `~/ROLLBACK.txt` เพิ่มขั้นตอนของรอบนี้ไว้บนสุด

## 8. Rollback (ไม่ได้ใช้)

```bash
cd ~/course-advisor-system
cp -a ~/release-fe6c57f/backend/. backend/ && cp -a ~/release-fe6c57f/llm/. llm/
docker tag course-advisor-system-backend:rollback-fe6c57f course-advisor-system-backend:latest
docker compose -f docker-compose.prod.yml up -d --no-build --no-deps backend
# check: image -> sha256:0e15938743a9… · STRUCTURED_ANSWERS ยัง on · health 200
```

---

PREVIOUS PRODUCTION COMMIT: `fe6c57f`

NEW COMMIT: `f2450a026ab05fac2142e996089a47bbefaf56ec`

PREVIOUS BACKEND IMAGE: `sha256:0e15938743a94c16f923fb21e6151abe6ef55b3f8385a134aee27db92d304197`

NEW BACKEND IMAGE: `sha256:cbec7c94a8b46b5f50f7a23bdee05ff96137dbfc4066329915ddc71c1224917d`

FILES DEPLOYED: `backend/app/services/chat.py` ไฟล์เดียว (อีก 61 ไฟล์ใน image ตรงกับ `fe6c57f` ทุกไบต์) · ไฟล์ test และรายงานอยู่ใน commit แต่ไม่ได้ถูก deploy เพราะไม่อยู่ใน `backend`/`llm`

FRONTEND TOUCHED: NO

DB TOUCHED: NO

MIGRATION RUN: NO

CONFIG/PROMPT/MODEL TOUCHED: NO (`.env`, compose, prompts, model, config ไม่เปลี่ยน — ตรวจด้วย SHA)

STRUCTURED_ANSWERS: `on` ทั้งก่อนและหลัง

HEALTH: public 200 · internal `{"status":"ok"}` ทั้งก่อนและหลัง validation

RESTART COUNT: 0

ERROR CHECK: errors/traceback/exception = 0 · HTTP 5xx = 0

PRODUCTION REQUEST COUNT: 3 (chat) · Gemini 4 ครั้ง · ไม่รัน behaviour_check ไม่ batch ไม่ stress test

TEST A: PASS — "เรียนไรดี" ได้คำถามกลับ ไม่มีรายชื่อสาขา ไม่มีอันดับที่ไม่มีหลักฐาน

TEST B: PASS — "แนะนำสาขาหน่อย" ได้คำถามกลับเดียวกันทุกตัวอักษร ไม่มีรายชื่อสาขา

TEST C: PASS — "ชอบเขียนโปรแกรมควรเรียนสาขาไหน" เข้าเส้นทางแนะนำเดิม ได้วิทยาการคอมพิวเตอร์และเทคโนโลยีสารสนเทศ พร้อมเหตุผลจากเอกสาร ไม่ถูก gate ผิดพลาด

ACCEPTANCE RESULT: PASS

ROLLBACK REQUIRED: NO

KNOWN LIMITATIONS (คงตามรายงานเดิม ไม่แก้ในรอบนี้):
- ตอบว่า "ไม่รู้" ต่อจากคำถามกลับ ยังเข้าเส้นทางคำตอบต่อยอดและจับคู่ด้วยข้อความรวม — นอกขอบเขต มี test ตรึงพฤติกรรมไว้
- ความครบถ้วนของคำแนะนำกว้างยังจำกัดด้วย `_RELEVANCE_MARGIN 0.04` และ `limit=3`
- gate พึ่งสัญญาณ `interest` ที่วัดมา 3 สำนวน ความพลาดที่เป็นไปได้คือถามกลับเกินจำเป็น ซึ่งกู้คืนได้ในเทิร์นถัดไป
- ข้อความคำถามกลับเป็นภาษาไทยอย่างเดียว

FEATURE FROZEN: YES — ไม่ optimize หรือ refactor เส้นทางแนะนำสาขาต่อ ข้อจำกัดข้างต้นให้พิจารณาเป็นงานแยกภายใต้ Engineering Stability Rules

PRODUCTION STATUS: healthy · commit `f2450a0` · image `cbec7c94…` · `STRUCTURED_ANSWERS=on` · publication `7999a1c2…` 103/156 · review_decisions 37 · ไม่มี migration และไม่มีการเปลี่ยนข้อมูล

CHAT_RECOMMENDATION_CLARIFICATION: PRODUCTION PASS
