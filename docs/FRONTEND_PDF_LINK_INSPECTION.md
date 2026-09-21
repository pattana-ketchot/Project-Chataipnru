# Frontend PDF Link — Read-only Inspection

วันที่: 2026-09-21 · **READ-ONLY** — ไม่แก้ไฟล์ใด ไม่แตะ repo ของเพื่อน ไม่แก้ backend ไม่ deploy ไม่ commit
อ่านแล้ว: `ENGINEERING_STABILITY_RULES.md`, `PDF_ENDPOINT_PRE_IMPLEMENT_REPORT.md`, `PDF_ENDPOINT_POST_IMPLEMENT_REPORT.md`, `PDF_ENDPOINT_DEPLOYMENT_REPORT.md`

> **ข้อสรุปสั้น: หน้าเว็บสร้างลิงก์ไม่ได้ในตอนนี้** เพราะคำตอบที่ส่งถึงหน้าเว็บเป็น "ข้อความล้วน" ไม่มี `document_id` และไม่มี `page_start` แม้แต่ฟิลด์เดียว → **STOP ตามเงื่อนไขที่กำหนด**

---

## 1. CURRENT FRONTEND FLOW

```
ผู้ใช้พิมพ์คำถาม  (ProjectPnru/src/pages/ChatAdvisor.jsx)
   │  POST /api/chat  {messages:[{role, content}]}
   ▼
Caddy: /api/chat → rewrite → backend /chat-web   (web_compat.py:91)
   ▼
stream_answer() สร้างเหตุการณ์ SSE: token / citations / done
   ▼
chat-web แกะ **เฉพาะ event "token"** แล้ว yield ข้อความดิบ
   StreamingResponse(media_type="text/plain; charset=utf-8")   ← web_compat.py:153-156
   ▼
ChatAdvisor.jsx อ่านสตรีมเป็นตัวอักษร ต่อเข้าตัวแปร content (บรรทัด 62-76)
   ▼
แสดงผลบรรทัดเดียว: <div className="text-sm whitespace-pre-wrap">{msg.content}</div>   (บรรทัด 206)
```

**"ที่มา: ma69.pdf หน้า 1" ที่ผู้ใช้เห็น เป็นส่วนหนึ่งของข้อความคำตอบ** ไม่ใช่ข้อมูลโครงสร้าง — ประกอบขึ้นใน `curriculum_facts._compose()` ด้วย `Source.label()` แล้วต่อท้ายคำตอบเป็นสตริง

## 2. CURRENT CHAT API RESPONSE

| เส้นทาง | ใครเรียก | รูปแบบคำตอบ | มี `document_id` | มี `page` |
|---|---|---|---|---|
| `POST /chat-web` | **หน้าเว็บจริง** (ผ่าน `/api/chat`) | `text/plain` สตรีมตัวอักษรล้วน | ไม่มี | ไม่มี |
| `POST /chat` (SSE) | ชุดประเมิน / หน้าทดสอบ | event `token`, `citations`, `done` | ไม่มี | `page_number` (เฉพาะ citations ของ RAG) |
| `POST /chat` (JSON, `ChatReply`) | API เดิม | `citations: [ChatCitation]` | **ไม่มี** | `page_number` |

**สำคัญ:** คำตอบที่มาจาก Structured Metadata ตั้งค่า `citations=[]` เสมอ (`chat.py:1018` ใน `_with_structured`) เพราะที่มาถูกใส่ไว้ในเนื้อข้อความแล้ว ดังนั้นแม้หน้าเว็บจะเปลี่ยนไปเรียก `/chat` แบบ JSON ก็ยังไม่ได้ `document_id` หรือหน้าของค่านั้นอยู่ดี

## 3. AVAILABLE FIELDS

ที่หน้าเว็บมีอยู่ตอนนี้: **เฉพาะข้อความคำตอบ (string)** เท่านั้น

ที่ backend มีอยู่แล้วแต่ยังไม่ส่งออก

| ชั้น | ฟิลด์ | หมายเหตุ |
|---|---|---|
| `mko.v_live_values` / `v_live_list_items` | **`document_id`**, `source_filename`, `page_start`, `page_end`, `quote` | มีครบในฐานข้อมูล ใช้ได้ทันที |
| `curriculum_facts._scalar_facts()` (บรรทัด 104-112) | SELECT ดึง `source_filename, page_start, page_end, quote` — **ไม่ได้ดึง `document_id`** | เพิ่มในคำสั่ง SELECT ได้ |
| `Source` dataclass | `file`, `page_start`, `page_end`, `quote` | **ไม่มี `document_id`** |
| `EditionFact` | `course_id`, `course_title`, `edition_year`, `source`, `reviewed_by` | มี `course_id` ไม่ใช่ `document_id` |
| `ChatCitation` (RAG) | `chunk_id`, `course_id`, `course_title`, `page_number`, `score` | **ไม่มี `document_id`** (ตาราง `course_chunks` มีคอลัมน์ `document_id` อยู่แล้ว) |

## 4. MISSING FIELDS

| ต้องใช้ | มีไหม | ขาดที่ไหน |
|---|---|---|
| `document_id` | **ไม่มีตลอดเส้นทาง** | ตั้งแต่ SQL ใน `curriculum_facts` → `Source` → คำตอบ → `/chat-web` |
| `page_start` | มีในฐานข้อมูลและใน `Source` แต่ **ไม่ถูกส่งออกเป็นข้อมูล** | หลุดไปตอนแปลงเป็นข้อความใน `_compose()` และตอน `/chat-web` ตัดเหลือ text |
| ช่องทางส่งข้อมูลโครงสร้างถึงหน้าเว็บ | **ไม่มี** | `/chat-web` เป็น `text/plain` ตามสัญญาเดิมกับหน้าเว็บ |

## 5. COMPONENT TO CHANGE (ถ้าได้รับอนุมัติภายหลัง)

| ส่วน | ไฟล์ | บทบาท |
|---|---|---|
| หน้าแชท (เจ้าของการแสดงคำตอบ) | `ProjectPnru/src/pages/ChatAdvisor.jsx` — บรรทัด 62-76 (รับสตรีม) และ 206 (render) | เป็น component เดียวที่แสดงคำตอบ ยังไม่มีแนวคิดเรื่อง citation เลย |
| หน้าแบบสอบถาม (มี source แยกอยู่แล้ว) | `ProjectPnru/src/pages/FindMajorResult.jsx` | ได้ JSON จาก `/api/recommend-major` แต่คำตอบมีเพียง `courseId`, `matchScore`, `reason` — ไม่มีเอกสาร |
| ฝั่ง backend (ถ้าต้องเพิ่มฟิลด์) | `backend/app/services/curriculum_facts.py`, `backend/app/api/routes/web_compat.py` | **ยังห้ามแตะ รอการอนุมัติแยก** |

## 6. MINIMAL CHANGE ที่จำเป็น (ข้อเสนอ ยังไม่ทำ)

เนื่องจากหน้าเว็บไม่มีข้อมูลเลย จึงต้องเปิดช่องส่งข้อมูลก่อน — เสนอ 3 ทางเลือก เรียงจากกระทบน้อยไปมาก

**ทางเลือก A — ส่ง source เป็น header ของ `/chat-web`** (เล็กที่สุด ไม่เปลี่ยนสัญญาเดิม)
- เพิ่ม header เช่น `X-Source-Document: <document_id>` และ `X-Source-Page: <page_start>` ในคำตอบของ `/chat-web`
- ข้อความยังเป็น `text/plain` เหมือนเดิม หน้าเว็บที่ไม่อ่าน header ก็ทำงานได้เท่าเดิมทุกประการ
- ข้อจำกัด: header ต้องพร้อมก่อนเริ่มสตรีม ซึ่งทำได้เพราะคำตอบ structured เป็นข้อความสำเร็จรูป (ไม่ได้สตรีมจากโมเดล) แต่ต้องเปลี่ยนลำดับภายในเล็กน้อย → ต้องประเมินอีกครั้งก่อนลงมือ
- backend change: **YES** (เล็ก)

**ทางเลือก B — ต่อท้ายสตรีมด้วยบรรทัดข้อมูลที่หน้าเว็บแกะได้**
- เช่นส่งบรรทัดสุดท้ายเป็น JSON บรรทัดเดียวที่หน้าเว็บตัดออกก่อนแสดง
- ข้อเสีย: ถ้าหน้าเว็บรุ่นเก่ายังไม่ได้อัปเดต ผู้ใช้จะเห็น JSON ปนในคำตอบ — **ไม่แนะนำ**

**ทางเลือก C — ให้หน้าเว็บเรียก endpoint ใหม่เพื่อขอ source ของคำตอบล่าสุด**
- เช่น `GET /api/answer-source?...` แยกจากสตรีม
- ข้อเสีย: เพิ่ม endpoint ใหม่และต้องผูกกับคำถาม/คำตอบ ซึ่งซับซ้อนกว่าที่จำเป็น

**ข้อเสนอของผม: ทางเลือก A** และเมื่อเปิดช่องแล้ว ฝั่งหน้าเว็บค่อยเพิ่มปุ่มตาม UX ที่กำหนด

ฝั่ง backend ที่ต้องเพิ่ม (ถ้าอนุมัติ A)
1. `curriculum_facts._scalar_facts()` / `_list_facts()` — เพิ่ม `document_id` ใน SELECT (คอลัมน์มีอยู่แล้วใน view)
2. `Source` — เพิ่มฟิลด์ `document_id`
3. `web_compat.chat_web()` — แนบ header เมื่อคำตอบมาจาก structured
4. ไม่แตะ endpoint PDF ที่ FROZEN · ไม่แตะ RAG · ไม่แตะตรรกะ metadata (เพิ่มการส่งข้อมูลออกเท่านั้น ไม่เปลี่ยนคำตอบที่ผู้ใช้เห็น)

## 7. EXAMPLE RESULT (เป้าหมายหลังทำครบ)

```
หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาคณิตศาสตร์ (พ.ศ. 2569)
มีจำนวนหน่วยกิตรวมตลอดหลักสูตร 124 หน่วยกิต

ที่มา: ma69.pdf หน้า 1
[เปิดเอกสารต้นฉบับ ↗]
   → https://stpnru-advisor.duckdns.org/api/documents/fb2279ac-3139-449f-87dc-51c8e970bcd4/pdf#page=1
```

กติกา UI ที่เสนอ: เปิดแท็บใหม่ (`target="_blank" rel="noopener"`) · ใช้ `document_id` เป็นตัวระบุเสมอ · มี `page_start` จึงต่อ `#page=N` ไม่มีก็เปิดหน้าแรก · **ไม่มี `document_id` ต้องไม่แสดงปุ่ม** (ห้ามสร้างลิงก์ปลอม) · ไม่ทำ PDF viewer เอง

ยืนยันแล้วว่า URL รูปแบบนี้ใช้งานได้จริงบน production (`docs/PDF_ENDPOINT_DEPLOYMENT_REPORT.md` — 200 + SHA ตรง, 206 สำหรับ Range)

## 8. RISK

| ความเสี่ยง | ระดับ | หมายเหตุ |
|---|---|---|
| แตะ `/chat-web` ซึ่งเป็นเส้นทางที่ผู้ใช้จริงใช้ทุกคำถาม | **กลาง** | ต้องมี test ว่าเนื้อความคำตอบไม่เปลี่ยนแม้แต่ตัวอักษรเดียว |
| หน้าเว็บอยู่คนละ repo และมีงานค้างของเพื่อน 47 รายการ | กลาง | ต้องส่งเป็น patch ห้าม commit ให้ |
| header หลุดข้อมูลที่ไม่ควรเปิด | ต่ำ | ส่งเฉพาะ `document_id` (UUID) กับเลขหน้า ซึ่งเปิดสาธารณะอยู่แล้วผ่าน endpoint PDF |
| ผู้ใช้กดเปิดเอกสารเต็มเล่มบนมือถือ | ต่ำ | endpoint รองรับ Range แล้ว ตัวอ่าน PDF โหลดเฉพาะส่วนที่ใช้ |
| คำตอบจาก RAG ไม่มี `document_id` | ต่ำ | ปุ่มจะไม่ขึ้นสำหรับคำตอบกลุ่มนั้น ซึ่งถูกต้องตามกติกา |

---

CURRENT FRONTEND FLOW: `ChatAdvisor.jsx` → `POST /api/chat` → `/chat-web` → รับสตรีม `text/plain` → แสดงเป็นข้อความล้วนบรรทัดเดียว ไม่มี component ที่แสดง citation เลย

CURRENT CHAT API RESPONSE: `text/plain` สตรีมตัวอักษร · `/chat-web` แกะเฉพาะ event `token` แล้วทิ้ง event `citations`

AVAILABLE FIELDS (ที่หน้าเว็บ): ข้อความคำตอบอย่างเดียว · "ที่มา: ma69.pdf หน้า 1" เป็นส่วนหนึ่งของข้อความ ไม่ใช่ข้อมูลโครงสร้าง

MISSING FIELDS: **`document_id`** (ไม่มีตลอดเส้นทาง ตั้งแต่ SQL ของ `curriculum_facts` จนถึงหน้าเว็บ) และ **`page_start`** (มีในฐานข้อมูล แต่ถูกแปลงเป็นข้อความและไม่ถูกส่งออกเป็นฟิลด์)

COMPONENT TO CHANGE: `ProjectPnru/src/pages/ChatAdvisor.jsx` (บรรทัด 62-76 รับสตรีม, บรรทัด 206 render) — และฝั่ง backend `curriculum_facts.py` + `web_compat.py` ถ้าอนุมัติให้เปิดช่องส่งข้อมูล

MINIMAL CHANGE: เพิ่ม `document_id` ใน SELECT ของ `curriculum_facts` → เพิ่มฟิลด์ใน `Source` → แนบ `X-Source-Document` / `X-Source-Page` เป็น header ของ `/chat-web` → หน้าเว็บอ่าน header แล้วแสดงปุ่ม (ทางเลือก A ในข้อ 6)

EXAMPLE RESULT: ปุ่ม "เปิดเอกสารต้นฉบับ ↗" ใต้บรรทัด "ที่มา:" ลิงก์ไป `/api/documents/{document_id}/pdf#page={page_start}` เปิดแท็บใหม่

RISK: กลาง — ต้องแตะ `/chat-web` ที่ผู้ใช้จริงใช้ทุกคำถาม ต้องมี test ยืนยันว่าเนื้อความคำตอบไม่เปลี่ยน · หน้าเว็บต้องส่งเป็น patch ให้เจ้าของ repo

**BACKEND CHANGE REQUIRED: YES** — หน้าเว็บสร้างลิงก์จากข้อมูลที่มีอยู่ตอนนี้ไม่ได้เลย

**READY TO IMPLEMENT: NO** — STOP ตามเงื่อนไขที่กำหนด รออนุมัติการเปิดช่องส่ง `document_id` + `page_start` (และเลือกทางเลือก A/B/C) ก่อนเริ่มทำอะไรทั้งฝั่ง backend และฝั่งหน้าเว็บ
