# Production Deployment Report — ROUND 1: PDF Endpoint

วันที่ deploy: 2026-09-21T00:54:15Z (UTC) = 2026-09-21 07:54 เวลาไทย
อ้างอิง: `docs/PDF_ENDPOINT_PRE_IMPLEMENT_REPORT.md` · `docs/PDF_ENDPOINT_POST_IMPLEMENT_REPORT.md` · `docs/ENGINEERING_STABILITY_RULES.md`
ขอบเขต: backend only + compose ของ backend · ไม่มี migration · ไม่เขียน DB · ไม่แตะ Caddy/postgres/ollama/frontend · ไม่ push

---

## 1. Commit / Image

| | ก่อน | หลัง |
|---|---|---|
| commit | `f2450a0` | **`6937a713cb701dbe32fa1f2e51d9742e93f9c4e7`** |
| backend image | `sha256:cbec7c94a8b4…` | **`sha256:1daf486b69d47fb4e5e431a468f6d7df6c23556ac82bef82f76375a2d1d32b76`** |
| compose SHA | `fc95afb8…` | `d55a4cad…` |
| `.env` SHA | `4d37472d…` | `4d37472d…` (**ไม่เปลี่ยน**) |
| rollback | — | image tag `rollback-f2450a0` · release `~/release-f2450a0` · compose backup |

**ไฟล์ใน commit (9):** `backend/app/services/document_store.py` (ใหม่), `backend/app/api/routes/documents.py` (ใหม่), `backend/app/core/config.py` (+6), `backend/app/main.py` (+2/−1), `docker-compose.prod.yml` (+6), `eval/document_endpoint_check.py` (ใหม่) และรายงาน 3 ฉบับ
**ไฟล์ที่ deploy จริง:** 4 ไฟล์ใน image (2 ใหม่ + 2 แก้) + compose · อีก 61 ไฟล์ตรงกับ `f2450a0` ทุกไบต์

## 2. Pre-deploy (ผ่านทุกข้อ)

| ตรวจ | ผล |
|---|---|
| diff รอบสุดท้าย | แก้เฉพาะ 3 ไฟล์ในขอบเขต + ไฟล์ใหม่ 3 · ไม่มีไฟล์นอกขอบเขต |
| production commit / image | `f2450a0` / `cbec7c94…` ตรงกับรายงาน |
| compose บนเซิร์ฟเวอร์ | SHA ตรงกับ repo ที่ `f2450a0` (ไม่มี drift) |
| health / restarts / errors | 200 / 0 / 0 |
| `STRUCTURED_ANSWERS` | `on` |
| counts | `7999a1c2…` / 103 / 156 / 37 / 4 / `002_mko_review_publish` / course_documents 31 |
| **`documents/` SHA-256** | **31/31 ตรงกับฐานข้อมูล** · 84.7 MB · pdf 30 ไฟล์ |
| `samples/` | ยังครบ 31 ไฟล์ |
| release package | 65 ไฟล์ · CR = 0 · `sha256sum -c` OK |
| backup | `.env` + compose (สิทธิ์ 600, `sha256sum -c` OK) · `DEPLOYED_COMMIT.f2450a0`, `ROLLBACK.txt.f2450a0` · tag `rollback-f2450a0` |

## 3. Deploy

```
cp -a ~/release-6937a71/backend/. backend/   (server files == 6937a71)
cp -a ~/release-6937a71/llm/. llm/
cp -a ~/release-6937a71/docker-compose.prod.yml docker-compose.prod.yml
docker compose -f docker-compose.prod.yml build backend
docker compose -f docker-compose.prod.yml up -d --no-deps backend      # 00:54:15Z
```

`.env` ไม่ถูกแตะ · container อื่นไม่ถูก recreate (caddy Up 12 days · frontend Up 2 weeks · postgres/ollama Up 4 weeks · db-viewer Up 6 days)

## 4. ปัญหาที่พบระหว่าง deploy และการแก้ (รายงานตามจริง)

**อาการ:** หลัง deploy ครั้งแรก container อ่านโฟลเดอร์ไม่ได้ — `ls: cannot open directory '/srv/documents': Permission denied` ดัชนีเอกสารจึงเป็น 0 ไฟล์ (endpoint ตอบ 404 ทุกกรณี = ฟีเจอร์ปิดอยู่โดยปริยาย · ระบบเดิมไม่กระทบ health 200 errors 0)

**สาเหตุ:** ผู้ใช้ `ubuntu` บน host เป็น **uid 1001** แต่โปรเซสใน container รันเป็น `appuser` **uid 1000** (ตั้งไว้ใน `backend/Dockerfile`) โฟลเดอร์ที่สร้างไว้เป็น 700/600 จึงถูกปฏิเสธ

**การแก้:** ปรับสิทธิ์ของโฟลเดอร์ `documents/` เป็น 755 (ไดเรกทอรี) และ 644 (ไฟล์ PDF) ให้ตรงกับ `web/` ที่ caddy ใช้อยู่แล้วบนเครื่องเดียวกัน · `MANIFEST.tsv` คงไว้ที่ 600 เพราะ container ไม่ต้องใช้ · **mount ยังเป็น read-only** (ยืนยันด้วย `touch` → `Read-only file system`) · restart backend เพื่อสร้างดัชนีใหม่ → **indexed = 30 ไฟล์**

**ขอบเขต:** เป็นการปรับสิทธิ์ของโฟลเดอร์ที่สร้างใน ROUND 1 เพื่อให้ mount ที่อนุมัติไว้ใช้งานได้จริง ไม่ได้แตะ code, DB, `.env`, service อื่น หรือไฟล์ใน `samples/` · ย้อนกลับได้ด้วย `chmod 700/600`
**ผลข้างเคียงที่ต้องรู้:** ไฟล์อ่านได้โดยผู้ใช้อื่นบนเซิร์ฟเวอร์ (world-readable) เท่ากับไฟล์ใน `web/` ซึ่งเป็นเอกสารที่ตั้งใจเปิดให้ผู้ใช้เว็บดูอยู่แล้ว

## 5. Post-deploy (ก่อน smoke)

| ตรวจ | ผล |
|---|---|
| internal / public health | `{"status":"ok"}` / 200 |
| backend | image `1daf486b…` · restarts 0 · running |
| errors / traceback / exception | 0 |
| `STRUCTURED_ANSWERS` | `on` (`.env` และ container) · `.env` SHA ไม่เปลี่ยน |
| `DOCUMENTS_DIR` ใน container | `/srv/documents` |
| mount | read-only ยืนยันแล้ว · container เห็น 30 PDF |
| ดัชนีในโปรเซส | `enabled=True indexed=30` |
| counts | `7999a1c2…` / 103 / 156 / 37 / 4 / migration เดิม / course_documents 31 |

## 6. Smoke test — 4 requests (ครบทุกข้อที่กำหนด ไม่เรียก Gemini)

| # | คำขอ | ผลที่ได้ |
|---|---|---|
| 1 | `GET /api/documents/35708c6c…/pdf` (**curriculum/ma64.pdf**) | **200** · 1,801,912 bytes · `Content-Type: application/pdf` · `Content-Disposition: inline; filename="ma64.pdf"` · `Accept-Ranges: bytes` · **SHA-256 ของไฟล์ที่ได้ = `4d0f18fc…` ตรงกับ `course_documents.file_sha256`** · ขึ้นต้นด้วย `%PDF-1.6` |
| 2 | `GET /api/documents/fb2279ac…/pdf` พร้อม `Range: bytes=0-7` (**curriculum-brief/ma69.pdf**) | **206 Partial Content** · `Content-Range: bytes 0-7/677183` · 8 ไบต์แรกคือ `%PDF-1.5` · หัวข้อมูล inline ถูกต้อง |
| 3 | UUID ที่ไม่มีในฐานข้อมูล | **404** · `{"detail":"ไม่พบเอกสารที่ขอ"}` — ไม่บอก path หรือสิ่งที่มีในระบบ |
| 4 | ค่าที่ไม่ใช่ UUID (`not-a-uuid`) | **422** · FastAPI ปฏิเสธที่ชั้น validation ก่อนถึงฐานข้อมูล |

log ฝั่งเซิร์ฟเวอร์: `GET /documents/... 200` · `206 Partial Content` · `404` · `422` — ตรงกันทั้ง 4 รายการ
**Gemini calls = 0** ตลอดรอบ deploy และ smoke

## 7. Post-smoke

| ตรวจ | ผล |
|---|---|
| public / internal health | 200 / `{"status":"ok"}` |
| backend | image `1daf486b…` · restarts 0 · running |
| errors / traceback / exception · HTTP 5xx | 0 · 0 |
| `STRUCTURED_ANSWERS` · `.env` SHA | `on` · `4d37472d…` ไม่เปลี่ยน |
| publication / live values / list items | `7999a1c2…` / **103** / **156** |
| review_decisions / publications / migration | **37** / 4 / `002_mko_review_publish` |
| course_documents / shadow_answers | 31 / 136 (ไม่เปลี่ยนจากก่อน deploy — endpoint นี้ไม่เขียน DB) |
| `samples/` | ยังครบ 31 ไฟล์ |
| container อื่น | ไม่ถูกแตะ |

บันทึกบนเซิร์ฟเวอร์: `~/DEPLOYED_COMMIT` → `commit=6937a71` · `~/ROLLBACK.txt` เพิ่มขั้นตอนของรอบนี้ไว้บนสุด (รวมวิธีปิดฟีเจอร์โดยไม่ย้อนโค้ด)

## 8. Rollback (ไม่ได้ใช้)

```bash
# ปิดฟีเจอร์อย่างเดียว (ไม่ย้อนโค้ด)
echo 'DOCUMENTS_DIR=' >> ~/course-advisor-system/.env   # หรือแก้บรรทัดเดิม
docker compose -f docker-compose.prod.yml up -d --no-deps backend

# ย้อนโค้ดทั้งรอบ
cp -a ~/release-f2450a0/backend/. backend/ && cp -a ~/release-f2450a0/llm/. llm/
cp -p ~/backups/docker-compose.prod.yml.before_pdf_endpoint_20260921T005344Z docker-compose.prod.yml
docker tag course-advisor-system-backend:rollback-f2450a0 course-advisor-system-backend:latest
docker compose -f docker-compose.prod.yml up -d --no-build --no-deps backend
```
ฐานข้อมูลไม่ต้องย้อน (ไม่มี migration ไม่มีการเขียน) · ไฟล์ไม่ต้องย้อน (`documents/` เป็นสำเนา ต้นฉบับอยู่ครบ)

## 9. ข้อจำกัดที่ยังอยู่

- ยังไม่มีปุ่ม "เปิดเอกสารต้นฉบับ" บนหน้าเว็บจริง — เป็น repo ของเพื่อน ต้องส่งเป็น patch (ยังไม่ได้ทำ)
- ดัชนีเอกสารสร้างครั้งเดียวตอนโปรเซสเริ่ม ไฟล์ที่เพิ่มใหม่ต้อง restart backend จึงจะเห็น
- `storage_path` ในฐานข้อมูลยังไม่ถูกอัปเดต (ตามที่สั่ง) — ระบบไม่ได้ใช้คอลัมน์นี้
- ยังไม่ได้ทำ ROUND 2 (`document_files` / BYTEA)
- เอกสารเปิดสาธารณะโดยไม่ต้องล็อกอิน ตามสิทธิ์ที่ได้รับยืนยันมา

---

DEPLOYED COMMIT: `6937a713cb701dbe32fa1f2e51d9742e93f9c4e7` (ก่อนหน้า `f2450a0`)

BACKEND IMAGE: `sha256:1daf486b69d47fb4e5e431a468f6d7df6c23556ac82bef82f76375a2d1d32b76` (ก่อนหน้า `cbec7c94a8b4…`)

FILES DEPLOYED: `document_store.py`, `routes/documents.py` (ใหม่) · `config.py`, `main.py` (แก้) · `docker-compose.prod.yml` (DOCUMENTS_DIR + mount read-only ของ backend เท่านั้น)

SCOPE CHECK: ไม่มีการเปลี่ยนแปลงนอกขอบเขต — ไม่แตะ RAG / Structured Metadata / recommendation / scoring / prompt / model / DB / schema / `storage_path` / Caddy / `samples/` / frontend repo ของเพื่อน

DOCUMENTS SHA-256: 31/31 ตรงกับฐานข้อมูล ทั้งก่อนและหลัง deploy

STRUCTURED_ANSWERS: `on` ตลอด · `.env` SHA ไม่เปลี่ยน

HEALTH: 200 / `{"status":"ok"}` ทุกจุดตรวจ

RESTARTS / ERRORS: 0 / 0 (5xx = 0)

METADATA COUNTS: `7999a1c2…` · 103 / 156 / 37 / 4 · migration `002_mko_review_publish` — ไม่เปลี่ยน

SMOKE: 4 / 4 requests — curriculum 200 + sha ตรง · curriculum-brief 206 + `content-range` ถูกต้อง · UUID ไม่มีจริง 404 · invalid UUID 422 · Gemini calls 0

HTTP RANGE: **CONFIRMED บน production** (206 Partial Content, `Content-Range: bytes 0-7/677183`)

ISSUE DURING DEPLOY: สิทธิ์โฟลเดอร์ (host uid 1001 vs container uid 1000) แก้ด้วย `chmod 755/644` ให้เท่ากับ `web/` · mount ยังเป็น read-only · รายละเอียดในข้อ 4

ROLLBACK REQUIRED: NO

PRODUCTION STATUS: healthy · commit `6937a71` · `STRUCTURED_ANSWERS=on` · publication `7999a1c2…` 103/156 · review_decisions 37 · ไม่มี migration และไม่มีการเปลี่ยนข้อมูล

**FEATURE STATUS: FROZEN** — backend PDF endpoint ถูกแช่แข็งตามกฎข้อ 11 ของ `ENGINEERING_STABILITY_RULES.md` ห้ามปรับต่อจนกว่าจะมีหลักฐานของ bug class ใหม่ requirement ใหม่ demo blocker หรือปัญหาด้าน security/data integrity
