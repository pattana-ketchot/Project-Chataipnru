# Pre-Implement Report — ROUND 1: Central Storage + PDF Endpoint

วันที่: 2026-09-21 · **ยังไม่ implement** · ทำตาม `docs/ENGINEERING_STABILITY_RULES.md` ข้อ 12
อ่านแล้ว: `docs/ENGINEERING_STABILITY_RULES.md`, `docs/PDF_STORAGE_INSPECTION.md`
รอบนี้: READ-ONLY inspection + รายงาน · ไม่แก้ code · ไม่แตะ DB · ไม่ deploy · ไม่ commit

---

## 1. CURRENT STATE

| รายการ | สถานะจริง (ตรวจแล้ว) |
|---|---|
| Central Storage | **สร้างแล้วเมื่อ 2026-09-21** ที่ `~/course-advisor-system/documents/` — `curriculum/` 19 ไฟล์ 77.3 MB · `curriculum-brief/` 11 ไฟล์ 7.4 MB · `web/` 1 ไฟล์ · `MANIFEST.tsv` 31 แถว |
| SHA-256 | ตรงกับ `course_documents.file_sha256` **31/31** |
| ต้นฉบับ `samples/` | ยังครบ 31 ไฟล์ 84.7 MB (คัดลอก ไม่ได้ย้าย) |
| สิทธิ์ไฟล์ | โฟลเดอร์ 700 · ไฟล์ 600 · เจ้าของ `ubuntu` |
| `course_documents` | 31 แถว · มี `id`, `original_filename`, `file_sha256`, `storage_path`, `page_count` |
| `storage_path` | **ไม่มีโค้ดใดอ่าน** · ค่าปนกันสองรูปแบบ (backslash 18 / slash 13) |
| backend container | **ไม่มี `volumes:` เลยใน `docker-compose.prod.yml`** → ตอนนี้มองไม่เห็นโฟลเดอร์ `documents/` |
| Caddy | `handle /api/*` → `uri strip_prefix /api` → `reverse_proxy backend:8000` (เส้นทางใหม่ใช้ได้ทันทีโดยไม่ต้องแก้ Caddyfile) |
| หน้าเว็บจริง | อยู่คนละ repo (`FoMake/Univercity`, เพื่อนดูแล) build จาก working copy ในเครื่อง ดู `docs/FIND_MAJOR_SCORE_EXPLANATION_FRONTEND_HANDOFF.md` |
| ข้อมูลที่ผูก metadata กับเอกสาร | `mko.published_values.document_id` และ `mko.v_live_values.document_id` **มีอยู่แล้ว** → อนาคตทำลิงก์จากบรรทัด "ที่มา:" ได้โดยไม่ต้องแก้ตรรกะ metadata |

**สิทธิ์เผยแพร่เอกสาร: NOT CONFIRMED**
ค้นใน repository แล้วไม่พบหลักฐานใด ๆ ว่ามีการอนุญาตให้เผยแพร่ไฟล์ มคอ.2 แก่ผู้ใช้เว็บไซต์
- ไม่มีไฟล์ `LICENSE`
- ไม่มีข้อความเรื่องลิขสิทธิ์/การอนุญาตเผยแพร่ใน `docs/*.md` หรือ `README.md`
- `docs/IMPLEMENTATION_AND_EVALUATION.md` พูดถึงเฉพาะที่มาของข้อมูล (บางหลักสูตรมี มคอ.2 บางหลักสูตรมีแต่หน้าเว็บคณะ) ไม่ได้พูดถึงสิทธิ์ในการเผยแพร่ไฟล์ต่อ
- คำว่า "เผยแพร่" ที่พบในเอกสารทั้งหมดหมายถึงการ publish ชุดข้อมูล metadata ภายในระบบ ไม่ใช่การเปิดไฟล์ให้ดาวน์โหลด

**ข้อเสนอ: ต้องได้คำยืนยันจากอาจารย์หรือคณะก่อนเปิดให้ผู้ใช้ทั่วไปเปิดไฟล์ได้** และควรตัดสินใจด้วยว่าจะเปิดทั้งฉบับเต็มหรือเฉพาะฉบับย่อ (`curriculum-brief/`) ข้อนี้เป็น STOP CONDITION ข้อแรก

---

## 2. CLASSIFICATION

| หัวข้อ | ผล |
|---|---|
| ประเภท | **E. FEATURE REQUEST** (ความสามารถใหม่ ไม่ใช่การแก้ bug) — ได้รับอนุมัติจากเจ้าของงานให้ทำเป็น ROUND 1 แยกจากงานอื่น |
| EVIDENCE | Central Storage มีอยู่จริงและ SHA ตรง 31/31 · backend ยังไม่มี mount · Caddy ส่ง `/api/*` เข้า backend อยู่แล้ว · `v_live_values.document_id` มีอยู่แล้ว |
| PROVES | ทำ endpoint ที่อ้างด้วย `document_id` ได้โดยไม่ต้องแตะ RAG, metadata, scoring, prompt |
| UNCERTAINTY | สิทธิ์เผยแพร่ (NOT CONFIRMED) · การรองรับ HTTP Range ของ `FileResponse` ใน Starlette เวอร์ชันที่ใช้ (ยังไม่ได้ตรวจ) · พฤติกรรมของ `#page=N` ขึ้นกับ PDF viewer ของเบราว์เซอร์ |
| BUG CLASS | ไม่ใช่ bug |
| TRAINING REQUIRED | NO |
| DATA CHANGE REQUIRED | NO (ไม่ UPDATE `storage_path`, ไม่สร้างตารางใหม่, ไม่ migration) |

---

## 3. PROPOSED ARCHITECTURE

หัวใจคือ **แยก "สัญญาของ API" ออกจาก "ที่เก็บไฟล์จริง"** เพื่อให้ ROUND 2 เปลี่ยนข้างในได้โดยหน้าเว็บไม่ต้องแก้

```
ผู้ใช้กด "เปิดเอกสารต้นฉบับ"
   │
   ▼
GET /api/documents/{document_id}/pdf#page=6        ← สัญญาที่จะไม่เปลี่ยนใน ROUND 2
   │  (Caddy: strip /api → backend:8000/documents/{id}/pdf)
   ▼
backend/app/api/routes/documents.py
   ├─ ตรวจว่า {document_id} เป็น UUID (FastAPI บังคับชนิดให้)
   ├─ อ่านแถวจาก course_documents → ไม่มีแถว = 404
   └─ เรียก DocumentStore.open(document)      ← จุดสลับ implementation
        │
        ├── ROUND 1: FilesystemDocumentStore
        │      หาไฟล์ใน DOCUMENTS_DIR จากดัชนีที่สร้างตอนเริ่มโปรเซส
        │      คีย์ของดัชนีคือ file_sha256 (ไม่ใช่ path จาก DB)
        │      ตรวจ sha256 ของไฟล์ก่อนส่ง → ไม่ตรง = 404 + log warning
        │
        └── ROUND 2 (ยังไม่ทำ): DatabaseDocumentStore
               SELECT content FROM document_files WHERE document_id = ...
               endpoint, URL, headers และหน้าเว็บไม่ต้องเปลี่ยนแม้แต่บรรทัดเดียว
```

**สิ่งที่ไม่แตะเลย:** `chat.py`, `program_match.py`, `structured_shadow.py`, `curriculum_facts.py`, `structured_intent.py`, `rag.py`, prompts, model, scoring, margin, limit, schema, publication

---

## 4. DOCUMENT_ID → FILE MAPPING

| ขั้น | วิธี | เหตุผล |
|---|---|---|
| 1 | client ส่งมาเฉพาะ `document_id` (UUID) | ไม่รับ path จาก client เลย |
| 2 | `SELECT id, original_filename, file_sha256, page_count FROM course_documents WHERE id = :id` | ยืนยันว่ามีเอกสารนี้จริง |
| 3 | หาไฟล์จาก **ดัชนี sha256 → path** ที่สร้างครั้งเดียวตอนโปรเซสเริ่ม โดยสแกน `DOCUMENTS_DIR` | ใช้กติกาเดียวกับ `pipeline/mko/run.py::local_files()` ที่ใช้อยู่แล้ว · ไม่ต้องพึ่ง `storage_path` ที่ยังไม่ถูกต้อง |
| 4 | ตรวจ `sha256(ไฟล์) == file_sha256` ก่อนส่งออก | กันไฟล์ถูกสลับ/เสีย และพิสูจน์ได้ว่าไฟล์ที่ผู้ใช้เห็นคือไฟล์เดียวกับที่สกัด |
| 5 | ส่งด้วยชื่อไฟล์จาก DB (`original_filename`) | ชื่อไม่ได้มาจาก client |

**ไม่ใช้ `storage_path`** — เพราะค่าในคอลัมน์นั้นยังชี้ไปยังเครื่องที่นำเข้า (ข้อจำกัดที่บันทึกไว้ใน `docs/IMPLEMENTATION_AND_EVALUATION.md:728`) การอัปเดตคอลัมน์นี้เป็นงานแยกและไม่จำเป็นต่อ ROUND 1

---

## 5. FILES / COMPONENTS TO CHANGE

| ไฟล์ | การเปลี่ยนแปลง | หมายเหตุ |
|---|---|---|
| `backend/app/services/document_store.py` | **ใหม่** — `DocumentStore` (โปรโตคอล) + `FilesystemDocumentStore` + ดัชนี sha→path + การตรวจ sha | จุดที่ ROUND 2 จะเพิ่ม `DatabaseDocumentStore` |
| `backend/app/api/routes/documents.py` | **ใหม่** — `GET /documents/{document_id}/pdf` | ใช้ `web_rate_limiter` ตัวเดิม |
| `backend/app/main.py` | +1 บรรทัด `app.include_router(documents.router)` | — |
| `backend/app/core/config.py` | +1 setting `DOCUMENTS_DIR` (ค่าเริ่มต้นว่าง = ปิดฟีเจอร์) | ถ้าไม่ตั้งค่า endpoint ตอบ 404 เสมอ |
| `docker-compose.prod.yml` | + `volumes: - ./documents:/srv/documents:ro` และ `DOCUMENTS_DIR: /srv/documents` ใน backend | **เป็นการเปลี่ยน production config → ต้องอนุมัติแยกตอน deploy** |
| `eval/document_endpoint_check.py` | **ใหม่** — offline tests | — |
| `Caddyfile` | ไม่ต้องแก้ | `handle /api/*` ครอบคลุมอยู่แล้ว |
| ฐานข้อมูล | ไม่แก้ | ไม่มี migration ไม่มี UPDATE |
| หน้าเว็บจริง | **แยก repo** → ส่งเป็น patch ให้เพื่อน เหมือนรอบ `find-major-score-explanation.patch` | ปุ่ม "เปิดเอกสารต้นฉบับ" เป็นงานของเจ้าของหน้าเว็บ |
| `frontend/` (หน้าทดสอบของเรา) | ตัวเลือก: เพิ่มลิงก์ในหน้า `/match` เพื่อสาธิต | ถ้าต้องการ ขออนุมัติเพิ่ม |

**ประมาณการ:** backend 3 ไฟล์ใหม่/แก้ 2 ไฟล์เดิม ~120 บรรทัด · ไม่มีการแก้ไฟล์ที่เกี่ยวกับการตอบคำถาม

---

## 6. SECURITY

| ข้อกำหนด | วิธีทำ |
|---|---|
| ห้ามรับ absolute path จาก client | รับเฉพาะ `document_id: UUID` — FastAPI ปฏิเสธค่าที่ไม่ใช่ UUID ด้วย 422 ก่อนถึงโค้ดเรา |
| ป้องกัน path traversal | ไม่มีการต่อ string เป็น path จาก input เลย · path มาจากดัชนีที่สแกนไว้ล่วงหน้า · ก่อนส่งไฟล์ ตรวจ `resolved_path.is_relative_to(DOCUMENTS_DIR.resolve())` อีกชั้น |
| ตรวจว่า document_id มีจริง | query `course_documents` ไม่เจอ = 404 (ข้อความกลาง ๆ ไม่บอกว่าเพราะอะไร) |
| ห้าม expose filesystem path | ข้อความ error ไม่มี path · log ภายในเท่านั้น |
| ห้าม directory listing | ไม่มี endpoint ที่คืนรายการไฟล์ · mount แบบ `:ro` |
| Content-Type | `application/pdf` (หรือ `text/plain` สำหรับ `ph_web.txt` ซึ่งไม่ใช่ PDF — endpoint นี้จะปฏิเสธเอกสารที่ไม่ใช่ PDF ด้วย 404) |
| การแสดงในเบราว์เซอร์ | `Content-Disposition: inline; filename="<original_filename>"` เพื่อให้ viewer เปิดในแท็บ และ `#page=N` ทำงาน |
| อัตราการเรียก | ใช้ `web_rate_limiter` ตัวเดียวกับ endpoint สาธารณะอื่น |
| การเข้าถึง | เว็บเปิดสาธารณะอยู่แล้ว (ไม่มี login) → **ไฟล์จะเปิดสาธารณะด้วย** ต้องได้คำยืนยันสิทธิ์ก่อน (ข้อ 1) |
| ขนาดไฟล์ | ใหญ่สุดในชุดคือหลาย MB · ถ้า Starlette ที่ใช้ไม่รองรับ HTTP Range เบราว์เซอร์จะโหลดทั้งไฟล์ก่อนแสดง — **ยังไม่ได้ตรวจเวอร์ชัน → NOT CONFIRMED** จะตรวจในขั้น implement และบันทึกเป็นข้อจำกัดถ้าไม่รองรับ |

---

## 7. TEST PLAN (offline ทั้งหมด ไม่เรียกโมเดล ไม่ยิง production)

| ชุด | กรณี |
|---|---|
| **A. กรณีหลัก** | `document_id` ที่มีจริง → 200 · `Content-Type: application/pdf` · `Content-Disposition: inline` · ไบต์ที่ส่งออกมี sha256 ตรงกับ `file_sha256` |
| **B. เทียบเท่าเชิงความหมาย** | ทดสอบกับเอกสารหลายรายการ ทั้งใน `curriculum/` และ `curriculum-brief/` |
| **C. กรณีตรงข้ามที่ต้องไม่ผ่าน** | UUID ที่ไม่มีในฐานข้อมูล → 404 · ค่าที่ไม่ใช่ UUID → 422 · เอกสารที่ไม่ใช่ PDF (`ph_web.txt`) → 404 · `DOCUMENTS_DIR` ไม่ได้ตั้งค่า → 404 · ไฟล์หายจากดิสก์ → 404 · sha ไม่ตรง → 404 + log |
| **D. ความปลอดภัย** | สตริง traversal (`..%2f`, `../`, path ยาว, null byte) ต้องไม่หลุดถึงชั้นไฟล์ (ตกที่ 422 ตั้งแต่ชั้น validation) · ข้อความ error ต้องไม่มี path ของเซิร์ฟเวอร์ |
| **E. ROUND 2 compatibility** | ใส่ `DocumentStore` ปลอมที่คืนไบต์จากหน่วยความจำ แล้วยืนยันว่า endpoint คืนผลเหมือนกันทุกประการ → พิสูจน์ว่าเปลี่ยนที่เก็บได้โดยไม่แตะ route |
| **F. ไม่กระทบของเดิม** | รัน `eval/*_check.py` ทั้งหมด (ยกเว้น `behaviour_check`) ต้องได้ 365 tests / 0 fail เท่าเดิม |

---

## 8. PRODUCTION DEPLOY PLAN (ขออนุมัติแยกอีกครั้งก่อนทำ)

1. **Pre-deploy** — ยืนยัน baseline: commit `f2450a0`, image `cbec7c94…`, health 200, `STRUCTURED_ANSWERS=on`, publication `7999a1c2…` 103/156/37 · ยืนยันว่า `documents/` ยังครบ 31 ไฟล์ SHA ตรง
2. **Backup** — `.env`, `docker-compose.prod.yml` (สิทธิ์ 600 + SHA) · tag image ปัจจุบันเป็น `rollback-f2450a0`
3. **แก้ compose** — เพิ่ม `volumes` และ `DOCUMENTS_DIR` ให้ backend เท่านั้น (**เป็น config change ที่ต้องอนุมัติ**)
4. **Deploy backend only** — `docker compose up -d --no-deps backend` · ไม่แตะ postgres/ollama/caddy/frontend · ไม่มี migration
5. **Post-deploy ก่อน traffic** — health 200 · restarts 0 · errors 0 · ยืนยันว่า container เห็น `/srv/documents` และดัชนีสร้างได้ 30 PDF · `STRUCTURED_ANSWERS` ยัง `on` · counts ไม่เปลี่ยน
6. **Smoke ≤ 4 requests** — เปิดเอกสาร 1 ไฟล์จาก `curriculum/` (200 + sha ตรง) · 1 ไฟล์จาก `curriculum-brief/` · UUID ปลอม (404) · ค่าที่ไม่ใช่ UUID (422) — ทั้งหมดเป็น request แบบ static ไม่เรียก Gemini
7. **Post-smoke** — health, errors, restarts, counts, `.env` SHA ไม่เปลี่ยน
8. บันทึก `~/DEPLOYED_COMMIT`, `~/ROLLBACK.txt` แล้วเขียนรายงาน deployment

---

## 9. ROLLBACK PLAN

| ระดับ | วิธี |
|---|---|
| ปิดฟีเจอร์ทันทีโดยไม่ deploy | ลบ `DOCUMENTS_DIR` ออกจาก compose แล้ว recreate backend → endpoint ตอบ 404 ทุกกรณี (ออกแบบให้ "ไม่ตั้งค่า = ปิด") |
| ย้อน code | `docker tag course-advisor-system-backend:rollback-f2450a0 …:latest` + คืนไฟล์จาก `~/release-f2450a0` + recreate backend only |
| ฐานข้อมูล | ไม่ต้องทำอะไร เพราะรอบนี้ไม่แตะ DB เลย |
| ไฟล์ | ไม่ต้องทำอะไร `documents/` เป็นสำเนา ต้นฉบับใน `samples/` ยังอยู่ครบ |

---

## 10. ROUND 2 COMPATIBILITY

| สิ่งที่ต้องไม่เปลี่ยนใน ROUND 2 | การออกแบบที่รองรับ |
|---|---|
| URL | `GET /api/documents/{document_id}/pdf` คงเดิม |
| พารามิเตอร์ | `document_id` (UUID) คงเดิม ไม่มีพารามิเตอร์เรื่องที่เก็บไฟล์ |
| headers | `Content-Type`, `Content-Disposition`, สถานะ 200/404/422 คงเดิม |
| หน้าเว็บ | ไม่ต้องแก้แม้แต่บรรทัดเดียว |
| จุดที่เปลี่ยน | เพิ่มคลาสใหม่ใน `document_store.py` แล้วเลือกจาก settings เท่านั้น |

ROUND 2 จะเพิ่ม `document_files(document_id, content bytea, byte_size, sha256, mime_type, created_at)` + migration + สคริปต์นำเข้า + การตรวจ sha — **ไม่อยู่ในรอบนี้และจะไม่ถูกแตะ**

---

## 11. INVARIANTS (ต้องไม่เปลี่ยน)

- ตรรกะ RAG, Structured Metadata, recommendation, scoring, `_RELEVANCE_MARGIN 0.04`, `limit=3`, prompts, model, config ของโมเดล
- schema ของฐานข้อมูลและข้อมูลทั้งหมด · publication `7999a1c2…` · 103/156/37
- `STRUCTURED_ANSWERS=on`
- ไฟล์ใน `samples/` (ห้ามลบ)
- ชุดทดสอบเดิม 365 tests ต้องผ่านเท่าเดิม

---

## 12. RISK

| ความเสี่ยง | ระดับ | การลด |
|---|---|---|
| เปิดเอกสารภายในของคณะสู่สาธารณะโดยไม่ได้รับอนุญาต | **สูง** | ต้องได้คำยืนยันก่อน (STOP condition) · ทางเลือก: เปิดเฉพาะ `curriculum-brief/` |
| ไฟล์ใหญ่ทำให้ผู้ใช้มือถือโหลดช้า | กลาง | เปิดฉบับย่อก่อน · ตรวจการรองรับ Range |
| compose เปลี่ยน = risk ของ deploy | ต่ำ | แก้เฉพาะ backend service · rollback ด้วยการถอด mount |
| ดัชนี sha ถูกสร้างตอน start ทำให้ไฟล์ใหม่ยังไม่เห็นจนกว่าจะ restart | ต่ำ | ยอมรับได้ (ไฟล์เปลี่ยนน้อยมาก) · บันทึกเป็นข้อจำกัด |
| สับสนว่าไฟล์ไหนคือฉบับเต็ม/ย่อ | ต่ำ | `MANIFEST.tsv` ระบุไว้ชัด |

---

## 13. STOP CONDITION

หยุดทันทีและรายงาน ถ้า
1. **ยังไม่ได้คำยืนยันสิทธิ์เผยแพร่เอกสาร** (ปัจจุบัน NOT CONFIRMED) — ข้อนี้ต้องเคลียร์ก่อนเริ่ม implement
2. ต้องแก้ไฟล์ที่เกี่ยวกับ RAG / metadata / recommendation เพื่อให้ฟีเจอร์ทำงาน
3. ต้องแก้ schema หรือเขียนฐานข้อมูล
4. ต้องเปลี่ยน Caddyfile หรือ config ของ service อื่นนอกจาก backend
5. ชุดทดสอบเดิมไม่ผ่าน 365/365
6. ต้องเปิด endpoint ที่รับ path หรือชื่อไฟล์จาก client เพื่อให้ `#page=N` ทำงาน
7. พบว่าต้องทำ `document_files` หรือ BYTEA เพื่อให้ ROUND 1 เสร็จ

---

## 14. READY TO IMPLEMENT

**READY TO IMPLEMENT: NO — รอเคลียร์ 2 ข้อ**

1. **คำยืนยันสิทธิ์เผยแพร่เอกสาร** (NOT CONFIRMED ในตอนนี้) และขอบเขตว่าจะเปิดฉบับเต็มหรือเฉพาะฉบับย่อ
2. **อนุมัติการแก้ `docker-compose.prod.yml`** เพื่อ mount `documents/` เข้า backend แบบอ่านอย่างเดียว (เป็น production config change)

เมื่อได้สองข้อนี้ ผมจะ implement แบบ offline ก่อน พร้อม tests แล้วส่งรายงานให้อนุมัติก่อน deploy ตามขั้นตอนเดิม

---

CODE CHANGED: NO · DB WRITE: NO · MIGRATION: NO · FILES MOVED/DELETED: NO · DEPLOY: NO · COMMIT/PUSH: NO
