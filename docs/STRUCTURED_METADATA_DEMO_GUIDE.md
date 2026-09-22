# Structured Metadata — คู่มือสาธิตให้อาจารย์ดู

วันที่ตรวจ: 2026-09-21 · READ-ONLY เท่านั้น — ไม่แก้ code / DB / data / config · ไม่ migration ไม่ publish ไม่ deploy ไม่ commit
ตรวจจาก repository ที่ commit `f2450a0` (ตรงกับที่รันบน production) และฐานข้อมูล production ด้วย `BEGIN READ ONLY … ROLLBACK`
ทุกตัวเลขในเอกสารนี้มาจากการ query จริง ไม่ได้ประมาณ

---

## A. METADATA PIPELINE (วาดให้อาจารย์ดูได้)

```
เอกสาร มคอ.2 (PDF)
   │  pipeline/extract_pdf.py, pipeline/pages.py, pipeline/ocr.py
   ▼
ข้อความรายหน้า  →  mko.document_pages   (4,129 หน้า)
   │  บันทึก text_source ของแต่ละหน้า: text_layer 3,934 · text_layer+ocr 185 · plain_text 9 · ocr 1
   ▼
หั่นเป็นส่วน/หัวข้อ + ตรวจหน้าสารบัญ   pipeline/mko/doc.py, toc.py, normalize.py, templates.py
   ▼
สกัดค่าและรายการ   pipeline/mko/extract.py, fields.py
   ├─ ค่าเดี่ยว (scalar)  → mko.field_values
   └─ รายการ (list)      → mko.list_items
   │  ทุกค่าผูกกับข้อความต้นฉบับ + เลขหน้า → mko.evidence (787 ชิ้น) ผ่าน mko.field_value_evidence
   ▼
ตัดสินสถานะอัตโนมัติ   pipeline/mko/decide.py
   verified (เจอค่าตรงกันสองตำแหน่งในเล่ม) / needs_review / not_found
   ▼
คนตรวจ   pipeline/mko/review.py  →  mko.review_decisions  (verified 36 · rejected 1 · ผู้ตรวจ project-owner)
   ▼
เผยแพร่เป็นชุด   pipeline/mko/publish.py  →  mko.publications + published_values + published_list_items
   (4 ครั้ง · policy = verified_any · ชุดที่ใช้อยู่ 7999a1c2… เผยแพร่ 2026-09-17)
   ▼
view ของชุดล่าสุด   mko.v_live_values (103 ค่า) · mko.v_live_list_items (156 รายการ)
   ▼
แชทตอบผู้ใช้   backend/app/services/structured_shadow.py → curriculum_facts.py
```

จุดที่ควรเน้นกับอาจารย์: **ข้อมูลไม่ได้เข้าสู่การตอบจนกว่าจะผ่านการตรวจและถูก publish เป็นชุด** และทุกค่ามีหน้าเอกสารกำกับเสมอ

---

## B. IMPORTANT FILES (เส้นทางจริง)

| ขั้นตอน | ไฟล์ | ฟังก์ชันสำคัญ |
|---|---|---|
| อ่าน PDF เป็นข้อความรายหน้า | `pipeline/extract_pdf.py`, `pipeline/pages.py` | — |
| OCR เฉพาะหน้าที่ข้อความไม่ครบ | `pipeline/ocr.py` | — |
| ประกอบข้อความทั้งเล่ม + ตรวจสารบัญ | `pipeline/mko/doc.py`, `pipeline/mko/toc.py` | `DocText.from_pages()`, `DocText.span_has_ocr()`, `is_toc_page()` |
| จัดรูปข้อความไทย/ตัวเลข | `pipeline/mko/normalize.py` | `fold()` |
| รู้จักรูปแบบเล่ม (มคอ.2 คนละแบบ) | `pipeline/mko/templates.py` | — |
| สกัดค่าและรายการ | `pipeline/mko/extract.py`, `pipeline/mko/fields.py` | — |
| ตัดสินสถานะอัตโนมัติ | `pipeline/mko/decide.py` | `decide_scalar()` · กฎ `AUTO_TWO_LOCATIONS` |
| เขียนลงฐานข้อมูลพร้อมหลักฐาน | `pipeline/mko/run.py` | `store()`, `_insert_evidence()`, `upsert_curriculum()` |
| คิวให้คนตรวจ + บันทึกผลตรวจ | `pipeline/mko/review.py` | `export_queue()`, `apply_file()`, `reapply()`, `status_summary()` |
| เผยแพร่เป็นชุด / ย้อนชุด | `pipeline/mko/publish.py` | `collect()`, `publish()`, `rollback_latest()` |
| รายงานความครอบคลุม | `pipeline/mko/report.py` | — |
| **ฝั่งตอบคำถาม** — อ่านเจตนาและขอบเขต | `backend/app/services/structured_intent.py` | `detect()` · `_FIELD_PATTERNS` |
| ค้นข้อมูลที่ publish แล้วและเรียงเป็นคำตอบ | `backend/app/services/curriculum_facts.py` | `lookup()`, `_scalar_facts()`, `_list_facts()`, `_compose()` · `LIST_FIELDS` |
| ด่านตัดสินว่าจะตอบด้วย metadata หรือ RAG | `backend/app/services/structured_shadow.py` | `configured_mode()`, `servable_answer()`, `structured_reply()` · `USER_FACING_FIELDS` |
| เสียบคำตอบเข้าเส้นทางแชท | `backend/app/services/chat.py` | `_with_structured()` (บรรทัด 1006) เรียกจาก `answer_question()` และ `stream_answer()` |

---

## C. DATABASE TABLES ที่ควรเปิดให้ดู

เปิดใน Adminer ที่ schema `mko` (เข้าผ่าน SSH tunnel ตามที่เคยตั้งไว้)

| ตาราง / view | เก็บอะไร | ตัวเลขจริง |
|---|---|---|
| `mko.document_pages` | ข้อความรายหน้าของเอกสารแต่ละเล่ม พร้อม `text_source` ว่าหน้านั้นได้ข้อความจาก text layer หรือ OCR | 4,129 หน้า |
| `mko.field_values` | ค่าเดี่ยวที่สกัดได้ พร้อม `status`, `reason`, `reviewed_by` | — |
| `mko.list_items` | รายการที่สกัดได้ (อาชีพ / วัตถุประสงค์ / คุณสมบัติผู้เข้าศึกษา) พร้อม `seq` และสถานะ | — |
| `mko.evidence` | ข้อความต้นฉบับ (`quote`) + ช่วงหน้า (`page_start`, `page_end`) + วิธีที่ได้มา (`method`) | 787 ชิ้น |
| `mko.field_value_evidence` | ตารางเชื่อม "ค่า ↔ หลักฐาน" (หนึ่งค่ามีหลายหลักฐานได้) | — |
| `mko.review_decisions` | ผลการตรวจของคน: `decision`, `reviewer`, `decided_at`, `superseded_at` | verified 36 · rejected 1 |
| `mko.publications` | ชุดที่เผยแพร่ พร้อม `published_by`, `policy`, `parser_version` | 4 ชุด |
| `mko.published_values` / `published_list_items` | ภาพนิ่งของข้อมูลในแต่ละชุด | — |
| **`mko.v_live_values`** | ค่าเดี่ยวของชุดที่ใช้อยู่จริง — คอลัมน์พร้อมใช้: `course_title`, `field_key`, `value_text`, `value_int`, `source_filename`, `page_start`, `quote`, `reviewed_by` | **103 ค่า** |
| **`mko.v_live_list_items`** | รายการของชุดที่ใช้อยู่จริง — `item_type`, `seq`, `text`, `source_filename`, `page_start` | **156 รายการ** |
| `mko.v_live_publication` | ชุดที่กำลังใช้ตอบ | `7999a1c2-e2fd-4b19-98d1-b50b3212f8d9` |

⚠️ **อย่าเปิด `mko.curricula` เป็นตัวอย่าง** — ตรวจแล้วพบว่า 24 แถวมี `program_name_th` เป็น NULL ทั้งหมด และ `total_credits` ในตารางนี้ก็เป็น NULL ทั้งหมด (ค่าจริงอยู่ที่ `field_values` / `v_live_values`) เปิดแล้วจะดูเหมือนระบบไม่มีข้อมูล

---

## D. SAFE DEMO QUERIES (อ่านอย่างเดียวทั้งหมด)

รันใน Adminer → SQL command หรือ psql · ทุก query เป็น `SELECT` ล้วน

**1. ชุดข้อมูลที่กำลังใช้ตอบ และภาพรวมจำนวน**
```sql
SELECT p.id, p.published_at, p.published_by, p.policy, p.parser_version,
       (SELECT count(*) FROM mko.v_live_values)     AS live_values,
       (SELECT count(*) FROM mko.v_live_list_items) AS live_list_items,
       (SELECT count(*) FROM mko.review_decisions WHERE superseded_at IS NULL) AS review_decisions
FROM mko.v_live_publication p;
```

**2. Metadata แบบค่าเดี่ยว พร้อมหน้าเอกสารและข้อความต้นฉบับ (provenance)**
```sql
SELECT course_title, field_key,
       COALESCE(value_text, value_int::text) AS value,
       source_filename, page_start,
       left(replace(quote, chr(10), ' '), 80) AS quote_from_document,
       reviewed_by
FROM mko.v_live_values
WHERE field_key IN ('total_credits', 'edition_year')
ORDER BY course_title, field_key
LIMIT 15;
```

**3. Metadata แบบรายการ (อาชีพหลังจบ) ของสาขาหนึ่ง**
```sql
SELECT seq, text, source_filename, page_start
FROM mko.v_live_list_items
WHERE item_type = 'career'
  AND course_title LIKE '%คหกรรม%'
ORDER BY seq;
```

**4. หนึ่งค่ามีหลักฐานกี่ชิ้น และอยู่หน้าไหนบ้าง**
```sql
SELECT fv.field_key,
       COALESCE(fv.value_text, fv.value_int::text) AS value,
       fv.status, fv.reviewed_by,
       count(*) AS evidence_count,
       string_agg(DISTINCT e.page_start::text, ', ' ORDER BY e.page_start::text) AS pages
FROM mko.field_values fv
JOIN mko.field_value_evidence fve ON fve.field_value_id = fv.id
JOIN mko.evidence e ON e.id = fve.evidence_id
GROUP BY fv.id, fv.field_key, fv.value_text, fv.value_int, fv.status, fv.reviewed_by
ORDER BY evidence_count DESC
LIMIT 10;
```

**5. ข้อมูลที่ใช้ตอบจริงมีสาขาละกี่ field และผ่านการตรวจโดยใคร**
```sql
SELECT field_key,
       count(DISTINCT course_id) AS programmes,
       count(*) FILTER (WHERE reviewed_by LIKE 'human:%') AS reviewed_by_human,
       count(*) FILTER (WHERE reviewed_by LIKE 'auto:%')  AS verified_by_rule
FROM mko.v_live_values
GROUP BY field_key
ORDER BY programmes DESC;
```

**เสริม (ถ้าอาจารย์ถามเรื่อง OCR)**
```sql
SELECT text_source, count(*) AS pages
FROM mko.document_pages
GROUP BY text_source
ORDER BY pages DESC;
```

---

## E. METADATA ที่มีอยู่จริง (ยืนยันจากฐานข้อมูล ไม่ได้สมมติ)

**ค่าเดี่ยวใน `v_live_values` — 10 field_key รวม 103 ค่า**

| field_key | จำนวนหลักสูตร |
|---|---|
| `edition_year` | 23 |
| `total_credits` | 23 |
| `revision_type` | 20 |
| `degree_abbr_th` / `degree_abbr_en` / `degree_level` / `program_name_th` / `program_name_en` | อย่างละ 7 |
| `degree_name_th` / `degree_name_en` | อย่างละ 1 |

**รายการใน `v_live_list_items` — 3 item_type รวม 156 รายการ**

| item_type | รายการ | หลักสูตร |
|---|---|---|
| `objective` (วัตถุประสงค์) | 72 | 15 |
| `career` (อาชีพหลังจบ) | 69 | 11 |
| `admission` (คุณสมบัติผู้เข้าศึกษา) | 15 | 10 |

**ที่แชทนำไปตอบผู้ใช้จริงมีเพียง 4 อย่าง** ตาม `USER_FACING_FIELDS` ใน `structured_shadow.py:55`
`total_credits`, `edition_year`, `careers`, `objectives`

`admission` **มีข้อมูลในฐานข้อมูลแต่ถูกกันไว้ไม่ให้ตอบ** โดยเจตนา (เหตุผลใน `docs/MKO_PHASE2_FINAL_SHADOW_VALIDATION.md`: ข้อมูล structured มีเฉพาะส่วนในหมวด มคอ.2 ไม่ครบเกณฑ์อายุ/GPAX/ข้อบังคับมหาวิทยาลัย) ส่วน field อื่นเช่น `degree_level`, `revision_type` ใช้ภายในเพื่อแยกระดับปริญญาและฉบับ ไม่ได้ตอบตรงๆ

---

## F. CHATBOT FLOW — เลือก Metadata หรือ RAG อย่างไร

```
คำถามผู้ใช้
   │
   ▼
prepare_answer()  (chat.py)  → ตีความคำถามต่อเนื่อง/อ้างอิงให้เป็นคำถามเต็ม
   │
   ▼
_with_structured()  (chat.py:1006)  → structured_reply()  (structured_shadow.py)
   │
   ├─ configured_mode() ต้องเป็น "on"  (ตอนนี้ production = on)
   │
   ▼
structured_intent.detect(คำถาม)
   ├─ route = RAG พร้อมเหตุผล เมื่อ: ไม่ระบุสาขา · ระบุหลายสาขา · หลายปี ·
   │          ระดับปริญญากำกวม (multiple_degree_levels) · เป็นคำถามเชิงเล่า/เปรียบเทียบ
   └─ route = STRUCTURED + field
        │
        ▼
   field ต้องอยู่ใน USER_FACING_FIELDS (4 ตัว) — ไม่อยู่ เช่น admission → RAG
        │
        ▼
   curriculum_facts.lookup()  อ่าน **เฉพาะ** mko.v_live_values / mko.v_live_list_items
        ├─ ไม่มีข้อมูลของสาขานั้น (no_data) → RAG
        └─ answered → _compose() ประกอบคำตอบ + บรรทัด "ที่มา: <ไฟล์> หน้า <n>"
        │
        ▼
   ตอบผู้ใช้ด้วย metadata (ไม่เรียกโมเดลเขียนคำตอบ ไม่เก็บลงแคชคำตอบ)
```

**สรุปกฎ:** ตอบด้วย metadata เมื่อครบสี่อย่างพร้อมกัน — โหมดเป็น `on` · เจตนาเป็น structured · field อยู่ใน allow-list · มีข้อมูลที่ publish แล้วของสาขานั้น · **กรณีอื่นทั้งหมดตกไปที่ RAG** ซึ่งเป็นเส้นทางเดิมที่ค้นจากเอกสาร

ทุกคำถามถูกบันทึกไว้ที่ `mko.shadow_answers` พร้อมข้อมูลว่าตอบด้วยทางไหน (`comparison_detail->>'served_source'`) เปิดให้อาจารย์ดูได้ว่าคำถามไหนใช้ metadata คำถามไหนใช้ RAG

---

## G. TEACHER DEMO SCRIPT (1–2 นาที)

> **ขั้นที่ 1 — เปิดเว็บจริง** `https://stpnru-advisor.duckdns.org` หน้าแชท
> พิมพ์: **"หลักสูตรคณิตศาสตร์ พ.ศ. 2569 เรียนกี่หน่วยกิต"**
>
> พูด: "คำตอบนี้ไม่ได้มาจากโมเดลภาษา แต่มาจากฐานข้อมูลที่เราสกัดจากเอกสาร มคอ.2 สังเกตบรรทัดสุดท้ายครับ ระบบบอกที่มาว่าเป็นไฟล์ไหน หน้าอะไร"
>
> **ขั้นที่ 2 — เปิดฐานข้อมูล** (Adminer → schema `mko` → SQL command) รัน **query ข้อ 2**
>
> พูด: "ค่าที่เห็นในคำตอบ อยู่ในตารางนี้ครับ แต่ละแถวเก็บค่า ชื่อไฟล์ เลขหน้า และข้อความต้นฉบับที่ตัดมาจากเอกสารจริง ทุกค่าสาวกลับไปหาหน้าในเล่มได้เสมอ"
>
> **ขั้นที่ 3 — แสดงว่าผ่านการตรวจ** รัน **query ข้อ 1** และชี้คอลัมน์ `reviewed_by` จากข้อ 2
>
> พูด: "ข้อมูลไม่ได้เข้าสู่การตอบทันทีที่สกัดได้ ต้องผ่านสองด่าน ด่านแรกคือกฎอัตโนมัติที่ยืนยันเมื่อเจอค่าตรงกันสองตำแหน่งในเล่ม ขึ้นเป็น `auto:` ด่านที่สองคือคนตรวจ ขึ้นเป็น `human:` แล้วจึงเผยแพร่เป็นชุด ตอนนี้ใช้ชุดที่เผยแพร่เมื่อวันที่ 17 กันยายน มี 103 ค่าและ 156 รายการ"
>
> **ขั้นที่ 4 — แสดงหลักฐานหลายชิ้นต่อหนึ่งค่า** รัน **query ข้อ 4**
>
> พูด: "หนึ่งค่ามีหลักฐานได้หลายชิ้น เช่นเจอเลขเดียวกันทั้งหน้า 1 หน้า 6 และหน้า 7 ระบบถึงจะยืนยันให้อัตโนมัติ ถ้าขัดกันจะถูกตีกลับให้คนตรวจ"
>
> **ขั้นที่ 5 — แสดงว่าระบบรู้ว่าเมื่อไรไม่ควรใช้ metadata** พิมพ์ในแชท: **"หลักสูตรเทคโนโลยีสารสนเทศ พ.ศ. 2566 คุณสมบัติของผู้เข้าศึกษามีอะไรบ้าง"**
>
> พูด: "คำถามนี้เรามีข้อมูลในฐานข้อมูลอยู่ 15 รายการ แต่เราตั้งใจไม่ให้ตอบจากฐานข้อมูล เพราะข้อมูลที่สกัดได้มีเฉพาะส่วนในเล่ม ยังไม่ครบเกณฑ์อายุกับ GPAX ระบบจึงถอยไปใช้การค้นเอกสารตามปกติ ซึ่งให้ข้อมูลครบกว่าในกรณีนี้"

รวมใช้เวลาประมาณ 2 นาที ใช้คำถามในแชท 2 ข้อ และ SQL 3 ข้อ

**เตรียมก่อนเข้าสาธิต:** เปิด SSH tunnel ของ Adminer ไว้ล่วงหน้า · ล็อกอินค้างไว้ · เปิดแท็บแชทไว้แยก · อย่าเปิดหน้า login ที่มีรหัสผ่านค้างบนจอ

---

## H. LIMITATIONS — สิ่งที่ยังไม่ควรเคลมว่ารองรับ

1. **ตอบด้วย metadata ได้เพียง 4 field** (`total_credits`, `edition_year`, `careers`, `objectives`) คำถามอื่นทั้งหมดใช้ RAG
2. **คุณสมบัติผู้เข้าศึกษา (admission) ไม่ได้ตอบจากฐานข้อมูล** แม้จะมี 15 รายการอยู่ในชุดที่เผยแพร่แล้ว
3. **ความครอบคลุมยังไม่เต็ม** — `edition_year` และ `total_credits` มี 23 หลักสูตร แต่ `careers` มี 11 และ `objectives` มี 15 หลักสูตร สาขาที่ไม่มีข้อมูลจะถอยไปใช้ RAG
4. **ตาราง `mko.curricula` ยังไม่ได้เติมค่า** — `program_name_th` และ `total_credits` เป็น NULL ทั้ง 24 แถว ค่าจริงอยู่ที่ `field_values` / `v_live_values` อย่าใช้ตารางนี้สาธิต
5. **ค่าส่วนใหญ่ยืนยันด้วยกฎอัตโนมัติ** (`auto:two_locations_agree`) ไม่ใช่คนตรวจทุกค่า จำนวนที่คนตรวจคือ 36 รายการใน `review_decisions`
6. **คำถามที่กำกวมไม่ถูกตอบด้วย metadata** เช่น ไม่ระบุสาขา ระบุหลายสาขา หลายปี หรือไม่ระบุระดับปริญญา — ออกแบบให้ถอยไป RAG โดยตั้งใจ
7. **ยังมีข้อมูลที่รู้ว่าเพี้ยนและรับไว้เป็นข้อจำกัด** เช่นตัวอักษร "น้ า" ในรายการอาชีพของสาขาหนึ่ง (บันทึกใน `docs/MKO_PHASE2_P3_REVIEW_APPLY_REPORT.md`)
8. **ตัวเลขความถูกต้องรวมของการสกัด** — NOT FOUND ในรายงานที่มีอยู่ (มีรายงานความครอบคลุมและผลตรวจรายฟิลด์ แต่ไม่มีตัวเลข accuracy รวมตัวเดียว) อย่าเคลมตัวเลขนี้ถ้าอาจารย์ถาม ให้ชี้ไปที่ `docs/MKO_PHASE2_STRUCTURED_COVERAGE_REPORT.md` แทน

---

RULE COMPLIANCE: อ่าน `docs/ENGINEERING_STABILITY_RULES.md` ก่อนทำงาน · งานนี้เป็น read-only demo preparation
CODE CHANGED: NO · DB WRITE: NO · MIGRATION: NO · PUBLISH: NO · DEPLOY: NO · COMMIT/PUSH: NO
