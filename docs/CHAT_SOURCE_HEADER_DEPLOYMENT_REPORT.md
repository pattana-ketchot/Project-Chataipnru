# CHAT SOURCE HEADER — Production Deployment Report

- วันที่ deploy: 2026-09-21T02:15:04Z (เวลาไทย 2026-09-21 09:15)
- ขอบเขต: **BACKEND ONLY**
- คอมมิต: `6937a71` → `705b425`
- อ้างอิง: `docs/CHAT_SOURCE_HEADER_POST_IMPLEMENT_REPORT.md`, `docs/FRONTEND_PDF_LINK_INSPECTION.md` (ทางเลือก A),
  `docs/PDF_ENDPOINT_DEPLOYMENT_REPORT.md`, `docs/ENGINEERING_STABILITY_RULES.md`

---

## 1. สิ่งที่เปลี่ยนจริงบน production

`/chat-web` (ที่ Caddy map มาจาก `/api/chat` ของหน้าเว็บ) ส่ง header เพิ่ม 2 ตัวเมื่อคำตอบมาจาก
Structured Answer ที่อ้างเอกสารได้เล่มเดียวแน่นอน:

| header | ความหมาย | ส่งเมื่อ |
|---|---|---|
| `X-Source-Document` | `course_documents.id` ของ PDF ต้นฉบับ | มี `document_id` จริงเท่านั้น |
| `X-Source-Page` | เลขหน้าเริ่มต้นของหลักฐาน | มีเลขหน้าเป็นจำนวนเต็ม > 0 |

**เนื้อความคำตอบ (response body) ไม่เปลี่ยนแม้แต่ไบต์เดียว** — header เป็นข้อมูลเสริมล้วน

ไฟล์ที่เปลี่ยน 4 ไฟล์ (ตรงกับ manifest diff ที่ตรวจก่อน deploy):

```
backend/app/api/routes/web_compat.py
backend/app/services/chat.py
backend/app/services/curriculum_facts.py
backend/app/services/structured_shadow.py
```

**ไม่เปลี่ยน:** `.env` · `docker-compose.prod.yml` · Caddy · PDF endpoint · RAG · scoring · prompt/model · schema/ข้อมูล

---

## 2. Pre-deploy (ผ่านครบ)

| รายการ | ค่าที่ตรวจได้ |
|---|---|
| commit เดิมบน production | `6937a71` ✅ ตรงตามที่กำหนด |
| image เดิม | `sha256:1daf486b69d4…` |
| ไฟล์บนเซิร์ฟเวอร์ตรงกับ `6937a71` | ✅ ไม่มี drift |
| health / restarts / errors / 5xx | 200 / 0 / 0 / 0 |
| `.env` sha | `4d37472dc9a6…` |
| `docker-compose.prod.yml` sha | `d55a4cadebaf…` |
| counts ก่อน deploy | `7999a1c2…\|103\|156\|37\|4\|002_mko_review_publish\|31\|136` |
| release package | `release-705b425.tar.gz` sha `83e48edaecf4…`, 65 ไฟล์, CR=0 |
| manifest diff เทียบ `6937a71` | เปลี่ยนตรง 4 ไฟล์ตามข้อ 1 เท่านั้น |
| `routes/documents.py` (FROZEN) | sha `4d95d4b1ea2f…` **ไม่เปลี่ยน** |
| backup | `env.before_source_header_20260921T021009Z`, `docker-compose.prod.yml.before_source_header_20260921T021009Z` |
| rollback tag | `course-advisor-system-backend:rollback-6937a71` |

Baseline body ที่เก็บไว้ก่อน deploy (คำถามเดียวกับ smoke ข้อ 1): 304 ไบต์ ไม่มี `X-Source-*` ตามคาด

---

## 3. Deploy

- วิธี: `git -c core.autocrlf=false archive 705b425` → scp → สคริปต์ deploy แบบ detached + log → `docker compose up -d --no-deps backend`
- image ใหม่: `sha256:dbb3eba5fa6f036599366b93559996aceb7e2fc2c17541c59117902d6c5a134d`
- restarts หลัง deploy: 0
- ไฟล์ในคอนเทนเนอร์ == `705b425` (65 ไฟล์) ✅
- `routes/documents.py` ในคอนเทนเนอร์ sha `4d95d4b1ea2f…` ✅ ไม่เปลี่ยน
- `docs_indexed` = 30 · `STRUCTURED_ANSWERS` = `on` · `DOCUMENTS_DIR` = `/srv/documents`
- `.env` และ compose sha หลัง deploy เท่าเดิมทุกตัว ✅

---

## 4. Controlled smoke (3 requests ตามที่อนุมัติ)

### 4.1 คำถาม Structured — "หลักสูตรคณิตศาสตร์ พ.ศ. 2569 เรียนกี่หน่วยกิต"

`POST https://stpnru-advisor.duckdns.org/api/chat` → HTTP 200, 304 ไบต์

```
X-Source-Document: fb2279ac-3139-449f-87dc-51c8e970bcd4
X-Source-Page: 1
```

body ที่ได้:

```
หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาคณิตศาสตร์ (พ.ศ. 2569) มีจำนวนหน่วยกิตรวมตลอดหลักสูตร 124 หน่วยกิต
ที่มา: ma69.pdf หน้า 1
```

| เกณฑ์ | ผล |
|---|---|
| response body เหมือนเดิม | ✅ เนื้อความตรงกับ baseline ทุกตัวอักษร (304 ไบต์เท่ากัน) |
| `X-Source-Document` มีค่า | ✅ `fb2279ac-3139-449f-87dc-51c8e970bcd4` |
| `X-Source-Page` = 1 | ✅ |
| `document_id` ตรงกับ `ma69.pdf` | ✅ (ยืนยันในข้อ 4.2) |

> **บันทึกความต่างที่ต้องพูดให้ตรง:** sha ของ *ไฟล์* baseline กับ *ไฟล์* ที่เพิ่งเก็บไม่ตรงกัน
> (`95d350a5…` vs `cca3c89e…`) เพราะไฟล์ baseline ถูกเขียนลงดิสก์ฝั่ง Windows แล้วตัวขึ้นบรรทัด
> กลายเป็น CRLF (305 ไบต์) ส่วนไบต์ที่ออกจากเซิร์ฟเวอร์เป็น LF (304 ไบต์)
> ตรวจซ้ำแล้ว: response จริงไม่มีไบต์ `\r` เลย และเมื่อเทียบแบบปรับตัวขึ้นบรรทัดให้เป็นแบบเดียวกัน
> สองก้อนนี้ **เท่ากันทุกไบต์** ความต่างจึงอยู่ที่วิธีเก็บไฟล์บนเครื่องพัฒนา ไม่ใช่ที่คำตอบ

### 4.2 เปิด PDF จาก header ที่ได้ (ไม่แก้ endpoint)

URL ที่ประกอบจาก header:
`https://stpnru-advisor.duckdns.org/api/documents/fb2279ac-3139-449f-87dc-51c8e970bcd4/pdf#page=1`

```
HTTP 200
Content-Type: application/pdf
Content-Disposition: inline; filename="ma69.pdf"
Content-Length: 677183
Accept-Ranges: bytes
```

- sha256 ของไฟล์ที่ได้ = `755613494128a0fa40e67608980195d0a9b0639ea5a53ed1a9c0481824d1e756` ✅ ตรงกับ `ma69.pdf` ที่บันทึกไว้
- ไฟล์ขึ้นต้นด้วย `%PDF-1.5` ✅
- `filename="ma69.pdf"` ยืนยันว่า `document_id` จาก header ชี้ไปที่เอกสารเดียวกับบรรทัด "ที่มา: ma69.pdf" ✅
- `Accept-Ranges: bytes` ⇒ ตัวอ่าน PDF ของเบราว์เซอร์กระโดดไป `#page=1` ได้ ✅
- **ไม่มีการแก้ PDF endpoint** — sha ของ `routes/documents.py` เท่าเดิมทั้งใน release และในคอนเทนเนอร์ ✅

### 4.3 คำถาม non-Structured — "คุณสมบัติผู้สมัครเข้าศึกษาสาขาคณิตศาสตร์ มีอะไรบ้าง"

`POST /api/chat` → HTTP 200, 875 ไบต์ ตอบผ่าน RAG ตามเดิม (คำถามเรื่องการรับเข้าไม่ใช้ Structured โดยเจตนา)

- header `X-Source-*`: **ไม่มีเลย** (นับได้ 0) ✅
- รูปแบบคำตอบเป็นรายการคุณสมบัติตามปกติ พฤติกรรมเดิมทุกอย่าง ✅

---

## 5. Post-smoke verification

| รายการ | ผล |
|---|---|
| `/api/health` สาธารณะ | 200 ✅ |
| health ภายในคอนเทนเนอร์ | `{"status":"ok"}` ✅ |
| image | `sha256:dbb3eba5fa6f…` · status `running` ✅ |
| restarts | 0 ✅ |
| traceback / error / exception ใน log | 0 ✅ |
| 5xx ใน log | 0 ✅ |
| `STRUCTURED_ANSWERS` | `on` ✅ |
| `routes/documents.py` (FROZEN) | `4d95d4b1ea2f…` ไม่เปลี่ยน ✅ |
| counts หลัง smoke | `7999a1c2…\|103\|156\|37\|4\|002_mko_review_publish\|31\|139` |
| คอนเทนเนอร์อื่น (caddy / frontend / postgres / ollama / db-viewer) | ไม่ถูกแตะ ✅ |

**เรื่อง DB write:** ตัวเลขที่เป็น metadata ทั้งหมดเท่าเดิม —
publication `7999a1c2…` · live values 103 · live list items 156 · review decisions 37 · publications 4 ·
migration ล่าสุด `002_mko_review_publish` · course_documents 31

ที่ขยับคือ `mko.shadow_answers` 136 → 139 (+3) ซึ่งตรงกับจำนวนคำถามที่ยิงในรอบนี้พอดี
(1 ครั้งตอนเก็บ baseline ก่อน deploy + 2 ครั้งใน smoke) — เป็นการบันทึกของระบบ shadow ที่มีอยู่ก่อนแล้ว
**ไม่ได้เกิดจากฟีเจอร์นี้** ฟีเจอร์ source header อ่านอย่างเดียว ไม่เขียนฐานข้อมูล และรอบนี้ไม่มี migration

---

## 6. ขอบเขตที่ยังไม่ทำ (ตามที่สั่ง)

- **ยังไม่แก้ frontend** — `ChatAdvisor.jsx` ของเพื่อนยังไม่ถูกแตะ ปุ่ม "เปิดเอกสารต้นฉบับ" ยังไม่ปรากฏให้ผู้ใช้
  backend พร้อมรองรับแล้ว หน้าเว็บอ่าน header สองตัวนี้ไปประกอบ URL ได้ทันทีเมื่อถึงรอบนั้น
- **ROUND 2 (`document_files` / BYTEA)** ยังไม่ทำ

## 7. ข้อจำกัดที่ต้องรู้ (ไม่ใช่บั๊ก)

- คำตอบที่รวมหลายรุ่นหลักสูตรไว้ในข้อความเดียวจะ **ไม่ส่ง** header เลย เพราะมีเอกสารต้นทางมากกว่าหนึ่งเล่ม
  การเลือกส่งเล่มใดเล่มหนึ่งคือการเดาให้ผู้ใช้ — ออกแบบให้เงียบไว้ดีกว่าพาไปผิดเล่ม
- คำตอบที่มาจาก RAG (รวมเรื่องการรับเข้า) ไม่มี header เพราะไม่มี `document_id` เดี่ยวที่ยืนยันได้
- smoke รอบนี้เป็นการวัดครั้งเดียวต่อกรณี ไม่ใช่การรับประกันอัตราความสำเร็จ

---

## สรุป

```
CHAT SOURCE HEADER DEPLOYMENT: PASS
RESPONSE BODY UNCHANGED:       YES
PDF ENDPOINT UNCHANGED:        YES (documents.py sha 4d95d4b1ea2f…)
NON-STRUCTURED UNAFFECTED:     YES (ไม่มี X-Source-*)
DB WRITES FROM THIS FEATURE:   NONE
FEATURE STATUS:                FROZEN
```

**FREEZE — chat source header**
ห้ามปรับ behavior ของ `X-Source-Document` / `X-Source-Page` ต่อ (รวมถึงการ "ปรับให้ส่งบ่อยขึ้น"
ในเคสหลายรุ่นหลักสูตรหรือเคส RAG) จนกว่าจะมีรอบงานใหม่ที่อนุมัติแยกต่างหาก

Rollback: `~/ROLLBACK.txt` บรรทัดบนสุด (705b425 → 6937a71, image tag `rollback-6937a71`)
สถานะที่บันทึกไว้: `~/DEPLOYED_COMMIT`
