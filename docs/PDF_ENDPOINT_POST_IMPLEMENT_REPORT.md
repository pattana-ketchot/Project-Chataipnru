# Post-Implement Report — ROUND 1: Central Storage + PDF Endpoint (OFFLINE)

วันที่: 2026-09-21 · **OFFLINE IMPLEMENTATION + TEST เท่านั้น** · ไม่ deploy ไม่ commit ไม่ push ไม่แตะ production
อ้างอิง: `docs/PDF_ENDPOINT_PRE_IMPLEMENT_REPORT.md` (อนุมัติแล้ว) · `docs/ENGINEERING_STABILITY_RULES.md`

---

## 1. สิ่งที่ทำ

| ไฟล์ | สถานะ | การเปลี่ยนแปลง |
|---|---|---|
| `backend/app/services/document_store.py` | **ใหม่** | `DocumentStore` (Protocol) · `StoredDocument` · `FilesystemDocumentStore` (ดัชนี sha256 → path, ตรวจขอบเขตโฟลเดอร์, ตรวจลายนิ้วมือ) · `get_document_store()` จุดสลับ implementation ของ ROUND 2 |
| `backend/app/api/routes/documents.py` | **ใหม่** | `GET /documents/{document_id}/pdf` — อ่านแถวจาก `course_documents` แล้วส่งต่อให้ store · 404 ข้อความเดียวกับทุกกรณีที่เปิดไม่ได้ |
| `backend/app/core/config.py` | +6 / −0 | เพิ่ม setting `documents_dir` (alias `DOCUMENTS_DIR`) ค่าเริ่มต้นว่าง = ปิดฟีเจอร์ |
| `backend/app/main.py` | +2 / −1 | import + `include_router(documents.router)` |
| `docker-compose.prod.yml` | +6 / −0 | เพิ่ม `DOCUMENTS_DIR: ${DOCUMENTS_DIR:-}` และ `volumes: - ./documents:/srv/documents:ro` **เฉพาะ service `backend`** |
| `eval/document_endpoint_check.py` | **ใหม่** | 16 tests |

**ไม่แตะ:** RAG, Structured Metadata, recommendation, scoring, prompts, model, Caddyfile, schema/ข้อมูลใด ๆ, `storage_path`, `samples/`, frontend repo ของเพื่อน
ตรวจแล้วว่า service อื่นใน compose (postgres / ollama / frontend / caddy) มี `volumes` เท่าเดิมทุกตัว

## 2. Diff ของไฟล์เดิม (3 ไฟล์)

```diff
backend/app/core/config.py   +6  −0     เพิ่ม documents_dir: str = Field("", alias="DOCUMENTS_DIR")
backend/app/main.py          +2  −1     import documents + include_router(documents.router)
docker-compose.prod.yml      +6  −0     DOCUMENTS_DIR + volumes ./documents:/srv/documents:ro (backend เท่านั้น)
```

ไฟล์ใหม่ 3 ไฟล์: `document_store.py` (≈150 บรรทัดรวมคำอธิบาย) · `routes/documents.py` (≈60) · `eval/document_endpoint_check.py` (≈230)

## 3. Architecture ที่ได้ (ตรงตามที่อนุมัติ)

```
GET /api/documents/{document_id}/pdf#page=N
  → Caddy strip /api → backend
  → route: ตรวจ UUID (FastAPI) → SELECT original_filename, file_sha256 FROM course_documents
  → get_document_store().open(document_id, filename, sha256)
       FilesystemDocumentStore: ดัชนี sha256→path จาก DOCUMENTS_DIR (เฉพาะ *.pdf)
       ตรวจ 1: path อยู่ใต้ DOCUMENTS_DIR จริง (resolve + is_relative_to)
       ตรวจ 2: sha256 ของไฟล์ตรงกับที่ฐานข้อมูลบันทึก
  → FileResponse(media_type=application/pdf, content_disposition_type=inline, filename=<ชื่อจาก DB>)
```

route ไม่รู้จักดิสก์เลย — มี test ตรวจ source ว่าไม่มี `Path(`, `os.`, `DOCUMENTS_DIR`, `rglob`, `read_bytes`, `settings`, `FilesystemDocumentStore`

## 4. ผลการทดสอบ — `eval/document_endpoint_check.py` (16 tests, ผ่านหมด)

| กลุ่ม | test | ผล |
|---|---|---|
| **การส่งไฟล์** | เอกสารที่มีจริง → 200 และไบต์ที่ได้ sha ตรงกับไฟล์ต้นฉบับ | OK |
| | headers: `content-type: application/pdf`, `content-disposition: inline; filename="ma64.pdf"` | OK |
| | เอกสารที่ต้นฉบับอยู่ใน `curriculum-brief/` ก็เปิดได้ | OK |
| | **HTTP Range**: `accept-ranges: bytes` · `Range: bytes=0-7` → 206 + `content-range` ถูกต้อง | OK |
| **ไม่พบ (404)** | UUID ที่ไม่มีในฐานข้อมูล · มีแถวแต่ไม่มีไฟล์ · ไฟล์ `.txt` · `DOCUMENTS_DIR` ว่าง · โฟลเดอร์ไม่มีอยู่จริง · ลายนิ้วมือไม่ตรงหลังไฟล์ถูกแก้ | OK (6 เคส) |
| **ความปลอดภัย** | `../../etc/passwd`, `..%2f..%2f…`, `ma64.pdf`, `/srv/documents/…`, `abc`, `1234`, `%00`, UUID ผิดรูปแบบ → 404/422 · ไม่มี `%PDF` ในคำตอบ · **ไม่มีการ query ฐานข้อมูลเลย** | OK |
| | ข้อความตอบกลับไม่มี path ของเซิร์ฟเวอร์ (`/srv/`, ชื่อโฟลเดอร์, temp path) | OK |
| | ดัชนีที่ชี้ออกนอกโฟลเดอร์ถูกปฏิเสธ (จำลอง symlink/ตั้งค่าผิด) | OK |
| | ดัชนีเก็บเฉพาะ `.pdf` | OK |
| **ROUND 2** | สลับ store เป็นตัวจำลอง `DatabaseDocumentStore` → เส้นทาง พารามิเตอร์ headers และเนื้อไฟล์เหมือนเดิมทุกประการ · store ได้รับ `(document_id, filename, sha256)` ครบ | OK |
| | route ไม่อ้างถึงดิสก์ใน source | OK |

## 5. HTTP Range — CONFIRMED รองรับ

| ที่ | Starlette | FastAPI | `FileResponse` รองรับ Range |
|---|---|---|---|
| เครื่องพัฒนา | 1.3.1 | 0.141.1 | **ใช่** |
| image ของ production ปัจจุบัน | 1.6.0 | 0.141.1 | **ใช่** |

ทดสอบจริงในชุดทดสอบ: ขอ `bytes=0-7` ได้ 206 พร้อม `content-range: bytes 0-7/<size>` และได้ไบต์ตรงช่วง
ผลคือตัวอ่าน PDF ของเบราว์เซอร์ขอเฉพาะช่วงที่ต้องใช้ได้ ลิงก์ `#page=N` จึงเปิดหน้าที่อ้างถึงโดยไม่ต้องรอทั้งเล่ม (ตัว `#page=N` เป็นเรื่องของเบราว์เซอร์ ฝั่งเซิร์ฟเวอร์ไม่ต้องทำอะไร)

## 6. Full regression — 381 / 0 fail

| Suite | Tests | | Suite | Tests |
|---|---|---|---|---|
| comparison_evidence_check | 30 | | recommend_intent_check | 12 |
| conversation_context_check | 12 | | recommendation_clarification_check | 15 |
| curriculum_facts_check | 16 | | recommendation_reply_check | 27 |
| degree_disambiguation_check | 25 | | recommendation_stability_check | 12 |
| **document_endpoint_check (ใหม่)** | **16** | | structured_on_path_check | 32 |
| eval_runner_check | 4 | | structured_routing_check | 22 |
| find_major_order_check | 19 | | structured_shadow_check | 30 |
| follow_up_scope_check | 21 | | tuition_followup_check | 14 |
| gemini_quota_check | 6 | | multi_program_scope_check | 12 |
| mko_extraction_check | 45 | | program_core_check | 7 |
| rationale_key_check | 4 | | **รวม** | **381** |

**ชุดเดิม 365 ผ่านครบโดยไม่ต้องแก้ expectation ใดเลย** (365 + 16 ใหม่ = 381)

**เหตุการณ์ระหว่างรัน (รายงานตามจริง):** รอบแรก `curriculum_facts_check` และ `degree_disambiguation_check` ขึ้น error เพราะ **Docker Desktop บนเครื่องพัฒนาไม่ได้เปิดอยู่** ฐานข้อมูลทดสอบที่พอร์ต 55432 จึงต่อไม่ได้ (`ConnectionRefusedError`) ผมเปิด Docker Desktop และสตาร์ตคอนเทนเนอร์ `mko-local-pg` แล้วรันใหม่ทั้งชุด ได้ 381/381 — เป็นปัญหาของเครื่องพัฒนา ไม่เกี่ยวกับโค้ดที่แก้ และไม่ได้แตะ production

## 7. ROUND 2 Compatibility — ยังเป็นไปตาม design

| ข้อตกลง | สถานะ |
|---|---|
| URL `GET /api/documents/{document_id}/pdf` | ไม่เปลี่ยนใน ROUND 2 |
| พารามิเตอร์ = `document_id` เท่านั้น | ไม่มีพารามิเตอร์ที่ผูกกับที่เก็บไฟล์ |
| headers และรหัสสถานะ | กำหนดที่ route ไม่ได้มาจาก store |
| จุดที่ต้องแก้ใน ROUND 2 | เพิ่มคลาสใหม่ใน `document_store.py` และเลือกใน `get_document_store()` — **จุดเดียว** |
| หน้าเว็บ | ไม่ต้องแก้ |
| การพิสูจน์ | test `Round2CompatibilityChecks` สลับ store เป็นตัวจำลองแล้วผลลัพธ์เหมือนเดิมทุกประการ |

`StoredDocument` ตอนนี้ถือ `path` ซึ่ง ROUND 2 จะต้องเขียนไบต์จากฐานข้อมูลลงไฟล์ชั่วคราวหรือเปลี่ยนเป็น `Response(content=...)` — **ต้องแก้ route 1 บรรทัด** ถ้าเลือกทางหลัง บันทึกไว้เป็นรายละเอียดที่ต้องตัดสินใจใน ROUND 2 (สัญญาภายนอกยังไม่เปลี่ยน)

## 8. เรื่องที่ต้องตัดสินใจก่อน deploy

1. **เอกสาร 11 รายการมีต้นฉบับอยู่ใน `curriculum-brief/` เท่านั้น** ได้แก่ `ma69.pdf`, `agri68_master.pdf`, `agri68_phd.pdf`, `animation69.pdf`, `attm65_brief.pdf`, `en65_brief.pdf`, `bio2568_brief.pdf`, `it66_brief.pdf`, `food66_brief.pdf`, `cs66_brief.pdf`, `cos66_brief.pdf`
   - implementation ปัจจุบัน **เปิดได้ทั้งสองโฟลเดอร์** เพราะแต่ละ `document_id` ผูกกับไฟล์ที่ใช้สกัดข้อมูลจริงของเอกสารนั้น
   - ถ้ายึดตามข้อความอนุมัติ ("เปิดฉบับเต็มใน `curriculum/`" · brief "ไม่ใช้เป็นเอกสารหลัก") แบบเคร่งครัด จะทำให้ 11 เอกสารนี้เปิดไม่ได้เลย รวมถึง `ma69.pdf` ที่ใช้ในสคริปต์สาธิต
   - ถ้าต้องการจำกัดเฉพาะ `curriculum/` แก้ได้ที่ `_build_index()` บรรทัดเดียว — **รอคำยืนยันจากคุณ** ผมเลือกทางที่ไม่ทำให้เอกสารหายไปจากผู้ใช้ และรายงานให้ทราบแทนการเดา
2. `ph_web.txt` ไม่เปิดผ่านเส้นทางนี้ (ดัชนีรับเฉพาะ `.pdf`) ตรงตามที่สั่ง
3. หน้าเว็บจริงยังไม่มีปุ่ม "เปิดเอกสารต้นฉบับ" — เป็น repo ของเพื่อน ต้องส่งเป็น patch เหมือนรอบก่อน (ยังไม่ได้ทำ)

## 9. สิ่งที่ยังไม่ได้ทำ (ตามขอบเขต)

- ไม่ deploy · ไม่ commit · ไม่ push
- ไม่แตะ production (ไม่ได้ทดสอบบนเซิร์ฟเวอร์จริง) — การตรวจว่า container เห็น `/srv/documents` จะทำในขั้น deploy
- ไม่สร้าง `document_files` · ไม่มี BYTEA · ไม่มี migration
- ไม่ UPDATE `storage_path` · ไม่ลบ `samples/`

---

ROOT CAUSE / GOAL: ผู้ใช้เปิดเอกสาร มคอ.2 ต้นฉบับจากเว็บได้ โดยอ้างด้วย `document_id` และไม่เปิดช่องให้เข้าถึงไฟล์อื่นในเครื่อง

FILES CHANGED: 3 ไฟล์เดิม (`config.py` +6, `main.py` +2/−1, `docker-compose.prod.yml` +6) · 3 ไฟล์ใหม่ (`document_store.py`, `routes/documents.py`, `eval/document_endpoint_check.py`)

HTTP RANGE: **CONFIRMED** — Starlette 1.3.1 (dev) และ 1.6.0 (production image) รองรับ · ทดสอบจริงได้ 206 + `content-range` ถูกต้อง

SECURITY TESTS: ผ่านทั้งหมด — client ส่งได้เฉพาะ UUID · ไม่มีการประกอบ path จาก input · traversal ทุกแบบไม่ถึงชั้นฐานข้อมูล · ไฟล์นอกโฟลเดอร์ถูกปฏิเสธ · ลายนิ้วมือไม่ตรงไม่ส่งไฟล์ · ข้อความ error ไม่มี path ของเซิร์ฟเวอร์ · `.txt` ไม่ถูกเปิด · ไม่มี directory listing

NEW TESTS: 16 / 16 OK

FULL REGRESSION: **381 / 0 fail** (เดิม 365 + ใหม่ 16) · ชุดเดิมไม่ต้องแก้ expectation ใด

ROUND 2 COMPATIBILITY: ยังเป็นไปตาม design — มี test พิสูจน์ว่าสลับที่เก็บได้โดย route, headers และหน้าเว็บไม่เปลี่ยน (ข้อสังเกตเรื่อง `StoredDocument.path` อยู่ในข้อ 7)

PRODUCTION TOUCHED: NO · DB WRITE: NO · MIGRATION: NO · DEPLOY: NO · COMMIT/PUSH: NO

รอการตัดสินใจข้อ 8.1 (เปิดเฉพาะ `curriculum/` หรือเปิดทั้งสองโฟลเดอร์) ก่อนขออนุมัติ deploy
