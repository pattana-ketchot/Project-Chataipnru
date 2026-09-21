# Post-Implement Report — ส่ง source ของ Structured Metadata ถึงหน้าเว็บ (ทางเลือก A)

วันที่: 2026-09-21 · **OFFLINE IMPLEMENTATION + TEST เท่านั้น** · ไม่ deploy ไม่ commit ไม่ push ไม่แตะ production ไม่แตะ repo ของเพื่อน
อ้างอิง: `docs/FRONTEND_PDF_LINK_INSPECTION.md` (อนุมัติทางเลือก A) · `docs/ENGINEERING_STABILITY_RULES.md` · `docs/PDF_ENDPOINT_DEPLOYMENT_REPORT.md` (endpoint FROZEN)

---

## 1. EXACT FILES CHANGED

| ไฟล์ | +/− | การเปลี่ยนแปลง |
|---|---|---|
| `backend/app/services/curriculum_facts.py` | +12 / −4 | `Source` เพิ่มฟิลด์ `document_id` · SELECT ของ `_scalar_facts()` และ `_list_facts()` ดึง `document_id` เพิ่ม (คอลัมน์มีอยู่แล้วใน `v_live_values` / `v_live_list_items`) |
| `backend/app/services/structured_shadow.py` | +49 / −7 | เพิ่ม `ServedAnswer` (answer + document_id + page_start) · แยก `servable_result()` ออกจาก `servable_answer()` · เพิ่ม `_source_of()` · เพิ่ม `structured_answer()` · `structured_reply()` เดิมยังอยู่และคืนค่าเท่าเดิม |
| `backend/app/services/chat.py` | +14 / −5 | `Prepared` เพิ่มฟิลด์ `source` · `_with_structured()` ใช้ `structured_answer()` และเก็บ source · meta event เพิ่มคีย์ `"source"` |
| `backend/app/api/routes/web_compat.py` | +66 / −14 | เพิ่ม `_parse_event()` และ `_source_headers()` · `chat_web()` ดึง event แรก (meta) ก่อนสร้าง response เพื่อใส่ header |
| `eval/chat_source_header_check.py` | ใหม่ | 21 tests |

**ไฟล์ที่ไม่ถูกแตะ (ยืนยันแล้ว):** `backend/app/api/routes/documents.py` — SHA-256 ยังเป็น `4d95d4b1ea2f5e839c8db84483e73dc8cc8d8025ff18a0b950ce65e2b1ec4226` เท่ากับตอน deploy ROUND 1 และมี test ตรึงค่านี้ไว้
ไม่แตะ: routing ของ structured, ค่าหรือข้อความของ metadata, RAG, recommendation/scoring, prompts, model, DB/schema/data, Caddy, `docker-compose.prod.yml`, frontend repo ของเพื่อน

## 2. EXACT DIFF SUMMARY

**`curriculum_facts.py`** — เพิ่มข้อมูล ไม่เปลี่ยนการคำนวณหรือข้อความ
```python
class Source:
    file: str; page_start: int; page_end: int; quote: str | None = None
+   document_id: str | None = None      # ใช้เปิดไฟล์ผ่าน /documents/{id}/pdf เท่านั้น

- SELECT ... quote, reviewed_by, publication_id
+ SELECT ... quote, reviewed_by, publication_id, document_id
```

**`structured_shadow.py`** — แยกชั้นให้ได้ที่มาโดยไม่เปลี่ยนคำตอบ
```python
+ @dataclass(frozen=True)
+ class ServedAnswer: answer: str; document_id: str | None = None; page_start: int | None = None
+ def _source_of(result):            # บอกที่มาเฉพาะเมื่อคำตอบอ้างถึง "ฉบับเดียว"
+     if len(result.facts) != 1: return None, None
+ def servable_result(db, asked)     # ตรรกะเดิมของ servable_answer ทุกบรรทัด
  def servable_answer(db, asked)     # กลายเป็น wrapper คืน .answer (พฤติกรรมเดิม)
+ def structured_answer(...)         # คืน ServedAnswer
  def structured_reply(...)          # คืนข้อความอย่างเดียวเหมือนเดิม (ผู้เรียกเดิมไม่กระทบ)
```

**`chat.py`**
```python
  class Prepared: ...
+     source: dict | None = None

- answer = structured_reply(...)            → served = structured_answer(...)
+ source = {"document_id": ..., "page_start": ...} if served.document_id else None
  replace(p, ..., canned=served.answer, source=source)     # ข้อความเดิมไม่เปลี่ยน

  yield _sse("meta", {... "citations": [...],
+                     "source": p.source})   # คีย์ที่เพิ่มเข้ามา ผู้อ่านเดิมไม่รู้จักก็ไม่กระทบ
```

**`web_compat.py`**
```python
+ def _parse_event(event) -> (kind, data)     # ย้ายตรรกะแกะ SSE เดิมออกมาเป็นฟังก์ชัน
+ def _source_headers(source) -> dict         # ส่ง header เฉพาะเมื่อมี document_id จริง

  def chat_web(...):
+     try: stream = stream_answer(...); kind, parsed = _parse_event(next(stream, ""))
+          if kind == "meta" and parsed: source_headers = _source_headers(parsed.get("source"))
+     except LLMConnectionError / Exception: prelude = <ข้อความเดิม>   # ยังตอบ 200 เป็นข้อความ
      return StreamingResponse(text_only(), media_type="text/plain; charset=utf-8",
-                              headers={"Cache-Control": ..., "X-Accel-Buffering": ...})
+                              headers={..., **source_headers})
```

## 3. TESTS ADDED — `eval/chat_source_header_check.py` (21 tests, ผ่านหมด)

| กลุ่ม | ครอบคลุม |
|---|---|
| **Header** (8) | คำตอบที่มีที่มา → ได้ `X-Source-Document` + `X-Source-Page` ครบ · `document_id` ตรงกับเอกสารจริง · เลขหน้าตรง · ประกอบ URL ได้ตรงรูปแบบ `/api/documents/{id}/pdf#page=N` · ไม่มีที่มา → ไม่มี header · ที่มาไม่ครบ 6 แบบ (None, "", ไม่มีคีย์, {}, ไม่ใช่ dict) → ไม่ส่ง header ปลอม · มีเอกสารแต่ไม่มีหน้า → ส่งเฉพาะ document · เลขหน้าที่ไม่ใช่จำนวนเต็มบวก (0, −1, "1", None, 1.5) → ตัดทิ้ง |
| **Body unchanged** (5) | เนื้อความเท่ากับเดิมทุกตัวอักษร · หลาย token ต่อกันเหมือนเดิม · ยังเป็น `text/plain` + header เดิมครบ · **มี/ไม่มี source เนื้อความเท่ากัน** · event ที่ไม่รู้จัก (`citations`) ไม่หลุดไปให้ผู้ใช้ |
| **Error flow** (2) | โมเดลล่มตั้งแต่ต้น → ยัง 200 พร้อมข้อความเดิม และไม่มี header · `event: error` กลางสตรีม → ต่อท้ายข้อความเหมือนเดิม |
| **Source plumbing** (5) | ที่มาเดินทางจากฐานข้อมูลถึง `Prepared` · ไม่มี `document_id` → `source` เป็น None · คำตอบที่ไม่ใช่ structured → ไม่มี source · **ที่มาบอกได้เมื่ออ้างถึงฉบับเดียว** (หลายฉบับ → ไม่บอก) · ที่มาไม่เปลี่ยนข้อความคำตอบ |
| **Frozen** (1) | SHA-256 ของ `routes/documents.py` ต้องเท่ากับตอน deploy ROUND 1 |

## 4. FULL REGRESSION — 402 / 0 fail

| Suite | Tests | | Suite | Tests |
|---|---|---|---|---|
| **chat_source_header_check (ใหม่)** | **21** | | program_core_check | 7 |
| comparison_evidence_check | 30 | | rationale_key_check | 4 |
| conversation_context_check | 12 | | recommend_intent_check | 12 |
| curriculum_facts_check | 16 | | recommendation_clarification_check | 15 |
| degree_disambiguation_check | 25 | | recommendation_reply_check | 27 |
| document_endpoint_check | 16 | | recommendation_stability_check | 12 |
| eval_runner_check | 4 | | structured_on_path_check | 32 |
| find_major_order_check | 19 | | structured_routing_check | 22 |
| follow_up_scope_check | 21 | | structured_shadow_check | 30 |
| gemini_quota_check | 6 | | tuition_followup_check | 14 |
| mko_extraction_check | 45 | | multi_program_scope_check | 12 |
| | | | **รวม** | **402** |

**ชุดเดิม 381 ผ่านครบโดยไม่ต้องแก้ expectation ใดเลย** (381 + 21 = 402) · `structured_on_path_check` (32) และ `structured_shadow_check` (30) ที่เรียก `servable_answer` / `structured_reply` ผ่านเหมือนเดิม เพราะทั้งสองฟังก์ชันคงสัญญาเดิมไว้

## 5. ตัวอย่าง headers จริง (จากชุดทดสอบ)

คำถาม: `หลักสูตรคณิตศาสตร์ พ.ศ. 2569 เรียนกี่หน่วยกิต`

```
HTTP/1.1 200 OK
Content-Type: text/plain; charset=utf-8
Cache-Control: no-cache
X-Accel-Buffering: no
X-Source-Document: fb2279ac-3139-449f-87dc-51c8e970bcd4
X-Source-Page: 1

หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาคณิตศาสตร์ (พ.ศ. 2569) มีจำนวนหน่วยกิตรวมตลอดหลักสูตร 124 หน่วยกิต
ที่มา: ma69.pdf หน้า 1
```

หน้าเว็บประกอบ URL ได้เป็น
`/api/documents/fb2279ac-3139-449f-87dc-51c8e970bcd4/pdf#page=1` — ตรงกับ endpoint ที่ deploy แล้วใน ROUND 1 (`document_id` นี้คือ `ma69.pdf` จริงตามที่ query มาในรอบ deploy ก่อน)

คำตอบจาก RAG หรือคำถามที่ตอบหลายฉบับ: **ไม่มี** `X-Source-*` เลย body เหมือนเดิมทุกประการ

## 6. ยืนยัน RESPONSE BODY UNCHANGED

- `text/plain; charset=utf-8` เหมือนเดิม · `Cache-Control: no-cache` และ `X-Accel-Buffering: no` เหมือนเดิม
- ตรรกะแกะ SSE ย้ายไปเป็นฟังก์ชันแต่เงื่อนไขเดิมทุกข้อ: ส่งออกเฉพาะ `event: token` ที่มี `t` และต่อท้าย `"\n\n" + detail` เมื่อเจอ `event: error`
- การดึง event แรกไม่ทำให้เสียตัวอักษร เพราะ `stream_answer` ส่ง `meta` ก่อน `token` เสมอ
- test เทียบตรง ๆ ว่า body ของ "มี source" กับ "ไม่มี source" เท่ากันทุกตัวอักษร

## 7. ยืนยัน NON-STRUCTURED FLOW UNCHANGED

| กรณี | พฤติกรรม |
|---|---|
| คำตอบจาก RAG | `source` เป็น None → ไม่มี header · ข้อความเดิม |
| คำถามที่ไม่ใช่ structured (รายชื่อสาขา, ค่าเทอม, แนะนำสาขา, small talk) | ไม่ผ่าน `_with_structured` หรือ `structured_answer` คืน None → ไม่มี header |
| โหมด `STRUCTURED_ANSWERS` ไม่ใช่ `on` | `structured_answer()` คืน None ตั้งแต่บรรทัดแรก เหมือน `structured_reply()` เดิม |
| โมเดลล่ม / stream error | ยังตอบ 200 พร้อมข้อความเดิม (test คุมไว้) |
| `/chat` (SSE) และ `/chat` (JSON) | event/schema เดิมครบ · meta มีคีย์ `source` เพิ่มมาเฉย ๆ · `ChatReply` **ไม่เปลี่ยน** |

## 8. FRONTEND PATCH PLAN (ยังไม่ทำ — repo ของเพื่อน)

ไฟล์เดียว: `ProjectPnru/src/pages/ChatAdvisor.jsx`

1. **อ่าน header ตอนรับ response** (ราวบรรทัด 58-62)
   ```js
   const documentId = response.headers.get('X-Source-Document')
   const sourcePage = response.headers.get('X-Source-Page')
   ```
2. **เก็บไว้กับข้อความของผู้ช่วย** — ตอนนี้เก็บเป็น `{role, content, timestamp}` เพิ่มเป็น `{..., documentId, sourcePage}` (บรรทัด 72-76)
3. **แสดงปุ่มใต้ข้อความ** (บรรทัด 206) เฉพาะเมื่อมี `documentId`
   ```jsx
   {msg.documentId && (
     <a href={`/api/documents/${msg.documentId}/pdf${msg.sourcePage ? `#page=${msg.sourcePage}` : ''}`}
        target="_blank" rel="noopener noreferrer"
        className="mt-2 inline-flex items-center gap-1 text-sm font-medium text-pnru hover:underline">
       เปิดเอกสารต้นฉบับ <ArrowUpRight className="w-4 h-4" aria-hidden="true" />
     </a>
   )}
   ```
4. **กติกา:** ไม่มี `documentId` → ไม่แสดงปุ่ม (ห้ามสร้างลิงก์ปลอม) · ไม่มีหน้า → เปิดหน้าแรก · ไม่ทำ PDF viewer เอง · ไม่แตะโค้ดส่วนอื่นของหน้า

ส่งเป็น patch ให้เจ้าของ repo เหมือนรอบ `find-major-score-explanation.patch` — **ต้องมี backend deploy ก่อน** ไม่งั้นปุ่มจะไม่ขึ้น (header ยังไม่มี) ซึ่งเป็น fail-safe ที่ถูกต้อง

## 9. RISK / ROLLBACK

| ความเสี่ยง | ระดับ | การลด |
|---|---|---|
| แตะ `/chat-web` ที่ผู้ใช้จริงใช้ทุกคำถาม | กลาง | 21 tests คุมเนื้อความและเส้นทาง error · smoke ตอน deploy ต้องเทียบข้อความกับคำตอบเดิม |
| ดึง event แรกก่อนสร้าง response เปลี่ยนจังหวะการเกิด error | กลาง | ครอบด้วย try/except ที่คืนข้อความแบบเดิมและสถานะ 200 · มี test 2 ข้อ |
| header หลุดข้อมูลที่ไม่ควรเปิด | ต่ำ | ส่งเฉพาะ UUID กับเลขหน้า ซึ่งเปิดผ่าน endpoint PDF อยู่แล้ว |
| คำตอบหลายฉบับชี้เอกสารผิดเล่ม | ต่ำ | กติกา "ฉบับเดียวเท่านั้น" มี test คุม |
| เปลี่ยนรูปคืนค่าของ `structured_*` | ต่ำ | `servable_answer` / `structured_reply` คงสัญญาเดิม ชุดทดสอบเดิม 62 ข้อของสองไฟล์นั้นผ่านโดยไม่แก้ |

**Rollback:** ย้อน 4 ไฟล์กลับ commit `6937a71` แล้ว deploy backend เหมือนรอบก่อน · ไม่มี migration ไม่มีการเขียน DB ไม่มี config เปลี่ยน (ไม่แตะ compose/.env) · ถ้าต้องการปิดเฉพาะ header โดยไม่ย้อนโค้ด ยังไม่มีสวิตช์ — ถ้าต้องการให้มี บอกได้ จะเพิ่มในรอบ implement ถัดไป (ยังไม่ทำเพราะไม่อยู่ในขอบเขตที่อนุมัติ)

---

EXACT FILES CHANGED: `curriculum_facts.py` (+12/−4) · `structured_shadow.py` (+49/−7) · `chat.py` (+14/−5) · `web_compat.py` (+66/−14) · `eval/chat_source_header_check.py` (ใหม่)

TESTS ADDED: 21 (header 8 · body unchanged 5 · error flow 2 · source plumbing 5 · frozen endpoint 1)

FULL REGRESSION: **402 / 0 fail** (เดิม 381 + ใหม่ 21) · ไม่ต้องแก้ expectation ของชุดเดิมเลย

ตัวอย่าง HEADERS จริง: `X-Source-Document: fb2279ac-3139-449f-87dc-51c8e970bcd4` · `X-Source-Page: 1` → URL `/api/documents/fb2279ac-3139-449f-87dc-51c8e970bcd4/pdf#page=1`

RESPONSE BODY UNCHANGED: ยืนยันด้วย test ที่เทียบ body ของกรณีมี/ไม่มี source ว่าเท่ากันทุกตัวอักษร และ `text/plain` + header เดิมครบ

NON-STRUCTURED FLOW UNCHANGED: RAG, คำถามอื่น, โหมดไม่ใช่ `on`, และเส้นทาง error ไม่มี header และข้อความเดิม

PDF ENDPOINT (FROZEN): ไม่ถูกแก้ — SHA-256 `4d95d4b1ea2f…` เท่าเดิม และมี test ตรึงไว้

API CONTRACT: เปลี่ยนเฉพาะ header (และคีย์ `source` ใน meta event ของ `/chat` ซึ่งเป็นการเพิ่มฟิลด์) ไม่มีการเปลี่ยนรูปแบบ body หรือ schema ใด

PRODUCTION TOUCHED: NO · DB WRITE: NO · MIGRATION: NO · CONFIG CHANGED: NO · DEPLOY: NO · COMMIT/PUSH: NO

**READY TO DEPLOY: YES** (รออนุมัติ) — deploy backend only ไม่มี migration ไม่ต้องแก้ `.env`/compose · rollback กลับ `6937a71` ได้ทันที
