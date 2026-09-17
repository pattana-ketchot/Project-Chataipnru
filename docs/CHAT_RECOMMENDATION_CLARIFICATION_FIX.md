# Chat Recommendation Clarification Gate — Offline Implementation Report

วันที่: 2026-09-18 · Branch `mko-phase2` ต่อจาก `fe6c57f` (commit ที่รันบน production ตอนนี้)
ขอบเขต: OFFLINE ONLY — ไม่ deploy ไม่ยิง production ไม่เรียก Gemini ไม่ restart ไม่แตะ DB ไม่ commit ไม่ push
อ้างอิง: `docs/CHAT_RECOMMENDATION_CLARIFICATION_RCA.md`, `docs/CHAT_RECOMMENDATION_CLARIFICATION_VALIDATION.md`

---

## 1. Root cause ที่แก้

`_recommendation_intent` เมื่อโมเดลคืน `interest = ""` (ขอคำแนะนำจริง แต่ยังไม่ได้บอกความสนใจ) โค้ดเดิมแทนที่ด้วย **ข้อความทั้งประโยค** แล้วส่งเข้า `match_programs` ต่อ

```python
if not interest or re.sub(r"\s+", "", interest) not in re.sub(r"\s+", "", message):
    return message          # ← "เรียนไรดี" ถูกส่งไปจับคู่สาขา
```

ผลบน production: "เรียนไรดี" ได้สามสาขาที่ทุกบรรทัดใต้ชื่อเขียนเองว่าเอกสารไม่ได้ระบุความเชื่อมโยง (log 2026-09-17 19:57Z)

## 2. สิ่งที่แก้

**`backend/app/services/chat.py` ไฟล์เดียว** (+56 / −5)

1. **สถานะที่สาม `NO_PREFERENCE`** — แยก "ขอคำแนะนำแต่ยังไม่มีความสนใจ" ออกจาก `None` (ไม่ใช่การขอคำแนะนำ) และออกจากข้อความความสนใจ
   ```python
   interest = str(data.get("interest") or "").strip()
   if not interest:
       return NO_PREFERENCE
   if re.sub(r"\s+", "", interest) not in re.sub(r"\s+", "", message):
       return message      # โมเดลเรียบเรียงใหม่ → ใช้ข้อความเดิม (พฤติกรรมเดิม ไม่เปลี่ยน)
   ```
2. **ด่าน 0.71 ใน `prepare_answer`** — เมื่อได้ `NO_PREFERENCE` ตอบด้วยคำถามกลับคงที่ และ **ไม่เรียก `match_programs`**
3. **`_NO_PREFERENCE_REPLY`** — ข้อความคงที่ ขึ้นต้นด้วย `_FOLLOW_UP_LEAD` เดิม ถามสี่หัวข้อที่ระบบใช้จับคู่จริง และบอกว่าขอดูรายชื่อสาขาทั้งหมดก่อนก็ได้

```
เพื่อให้แนะนำได้ตรงขึ้น บอกผมเพิ่มได้ไหมครับว่าชอบวิชาอะไร สนใจด้านไหน ถนัดอะไร
หรืออยากทำงานแบบไหนในอนาคต แล้วผมจะช่วยดูให้ว่าสาขาไหนใกล้เคียงบ้าง
ถ้ายังไม่แน่ใจ จะขอดูรายชื่อสาขาทั้งหมดของคณะก่อนก็ได้ครับ
```

เพราะข้อความขึ้นต้นด้วย `_FOLLOW_UP_LEAD` เทิร์นถัดไปที่ผู้ใช้ตอบว่า "ชอบเขียนโปรแกรม" จึงถูกจับเป็นคำตอบต่อยอดด้วย `_refinement_of_recommendation` **เส้นทางเดิม** แล้วนำ "เรียนไรดี ชอบเขียนโปรแกรม" ไปจับคู่ — ไม่มีกลไกใหม่

**ไม่แตะ:** `program_match.py`, สูตรคะแนน, `_RELEVANCE_MARGIN 0.04`, `limit=3`, embeddings/retrieval, Gemini rationale, prompts, model, config, RAG, Structured Answers, Find Major, frontend, DB/schema/data

## 3. Offline tests — `eval/recommendation_clarification_check.py` (15 tests)

เรียก `prepare_answer` ตัวจริง โดยจำลองคำตอบของขั้นจำแนกเจตนาตามค่าที่วัดมาจาก production และดัก `match_programs` ไว้ดูว่าถูกเรียกหรือไม่ · ไม่เรียกโมเดลจริง ไม่ต่อฐานข้อมูล

| กลุ่ม | ครอบคลุม | ผล |
|---|---|---|
| **NO PREFERENCE** | "เรียนไรดี", "เรียนอะไรดี", "แนะนำสาขาหน่อย", "ไม่รู้จะเรียนอะไร", "มีสาขาไหนน่าเรียน", "ช่วยเลือกสาขาให้หน่อย" → ได้คำถามกลับ และ **`match_programs` ไม่ถูกเรียกเลย** | OK |
| | คำถามกลับถามครบสี่หัวข้อ + บอกเรื่องรายชื่อสาขา · ขึ้นต้นด้วย `_FOLLOW_UP_LEAD` · ไม่เก็บลงแคช · ไม่ส่งข้อความทั้งประโยคไปจับคู่อีก | OK |
| | สถานะแยกจาก "ไม่ใช่การขอคำแนะนำ" (`NO_PREFERENCE` ≠ `None`) | OK |
| **WITH PREFERENCE** | "ชอบคอม เรียนอะไรดี", "ชอบเขียนโปรแกรมควรเรียนสาขาไหน", "ชอบคณิตศาสตร์และวิเคราะห์ข้อมูล เรียนอะไรดี", "อยากทำงานด้านอาหารควรเรียนอะไร" → `match_programs` ถูกเรียก 1 ครั้ง ด้วย `{"extra": <ความสนใจ>}` และได้คำแนะนำเหมือนเดิม | OK |
| | ค่าที่ส่งให้การจัดอันดับไม่เปลี่ยน (`limit=3`, `relevant_only=True`, `profile_text=None`) | OK |
| | interest ที่โมเดลเรียบเรียงใหม่ ยังใช้ข้อความเดิมเหมือนเดิม (ไม่ถูก gate) | OK |
| **FOLLOW-UP** | "เรียนไรดี" → คำถามกลับ → ผู้ใช้ตอบ "ชอบเขียนโปรแกรม" → เข้าเส้นทางคำตอบต่อยอด จับคู่ด้วย "เรียนไรดี ชอบเขียนโปรแกรม" และได้คำแนะนำจริง | OK |
| **NON-RECOMMENDATION** | รายชื่อสาขา / ค่าเทอม / คำถามข้อเท็จจริงของสาขา ไม่โดน gate (และคำถามข้อเท็จจริงไม่เรียกโมเดลเลย) | OK |
| **ไม่มีรายการคำ** | ตรวจ source ของ `_recommendation_intent` + `prepare_answer` แบบตัด docstring/คอมเมนต์ออกด้วย `ast` แล้วยืนยันว่าไม่มีประโยคตัวอย่างใดอยู่ในโค้ดที่ทำงานจริง | OK |

## 4. Full regression

รันทุก suite ใน `eval/*_check.py` ยกเว้น `behaviour_check` (ยิง production)

| Suite | Tests | ผล |
|---|---|---|
| comparison_evidence_check | 30 | OK |
| conversation_context_check | 12 | OK |
| curriculum_facts_check | 16 | OK |
| degree_disambiguation_check | 25 | OK |
| eval_runner_check | 4 | OK |
| find_major_order_check | 19 | OK |
| follow_up_scope_check | 21 | OK |
| gemini_quota_check | 6 | OK |
| mko_extraction_check | 45 | OK |
| multi_program_scope_check | 12 | OK |
| program_core_check | 7 | OK |
| rationale_key_check | 4 | OK |
| recommend_intent_check | 12 | OK |
| **recommendation_clarification_check (ใหม่)** | **15** | **OK** |
| recommendation_reply_check | 27 | OK |
| recommendation_stability_check | 12 | OK |
| structured_on_path_check | 32 | OK |
| structured_routing_check | 22 | OK |
| structured_shadow_check | 30 | OK |
| tuition_followup_check | 14 | OK |
| **รวม** | **365** (เดิม 350 + ใหม่ 15) | **0 fail** |

ชุดเดิมทั้ง 350 ผ่านโดย **ไม่ต้องแก้ expectation ใดเลย** ต่างจากรอบก่อนหน้า — ยืนยันว่าเส้นทางที่มีความสนใจไม่ถูกกระทบ

หมายเหตุการรัน: รอบแรก `comparison_evidence_check` รายงาน 25 tests (skipped 1) เพราะฐานข้อมูล local ตอบไม่ทันชั่วขณะ รันซ้ำได้ 30/30 OK ทั้งสองครั้งไม่มี fail

## 5. ข้อจำกัดที่ยังอยู่ (บันทึกไว้ในเทสต์ด้วย)

- **คำตอบต่อยอดที่ยังไม่มีความสนใจ** เช่น ตอบว่า "ไม่รู้" ต่อจากคำถามกลับ ยังเข้าเส้นทาง `_refinement_of_recommendation` ซึ่งตัดสินก่อนขั้นจำแนกเจตนา และจับคู่ด้วยข้อความรวม "เรียนไรดี ไม่รู้" — **นอกขอบเขตรอบนี้** มี test ตรึงพฤติกรรมนี้ไว้ให้เห็นชัด ถ้าจะแก้ต้องเป็นรอบแยก
- ความครบถ้วนของคำแนะนำกว้างยังจำกัดด้วย margin 0.04 และ limit 3 (ไม่ได้แก้ตามขอบเขต)
- gate พึ่งสัญญาณ `interest` จากโมเดล ซึ่งวัดมาแล้ว 3 สำนวน ถ้าโมเดลพลาดกับสำนวนอื่น ผลที่แย่ที่สุดคือถามกลับทั้งที่ผู้ใช้บอกความสนใจมาแล้ว ซึ่งกู้คืนได้ในเทิร์นถัดไป
- ข้อความคำถามกลับเป็นภาษาไทยอย่างเดียว เหมือนข้อความอื่นในเส้นทางแนะนำสาขา

---

ROOT CAUSE FIXED: ใช่ — `interest` ว่างไม่ถูกแทนด้วยข้อความทั้งประโยคอีกต่อไป แต่กลายเป็นสถานะ `NO_PREFERENCE` ที่นำไปสู่การถามกลับ

FILES CHANGED: `backend/app/services/chat.py` (+56 / −5) · `eval/recommendation_clarification_check.py` (ใหม่ 15 tests) · `docs/CHAT_RECOMMENDATION_CLARIFICATION_FIX.md` (รายงานนี้) — ไม่มีไฟล์อื่น ไม่ต้องแก้ architecture / prompt / scoring

IMPLEMENTATION: สถานะที่สาม `NO_PREFERENCE` จาก `_recommendation_intent` → ด่าน 0.71 ใน `prepare_answer` ตอบ `_NO_PREFERENCE_REPLY` ซึ่งขึ้นต้นด้วย `_FOLLOW_UP_LEAD` เดิม เพื่อให้คำตอบของผู้ใช้ในเทิร์นถัดไปไหลเข้า `_refinement_of_recommendation` ตามเส้นทางเดิม

SPECIAL-CASE STRINGS USED: NO — มี test ตรวจ source (ตัด docstring/คอมเมนต์ด้วย `ast`) ว่าไม่มีประโยคตัวอย่างอยู่ในโค้ดที่ทำงานจริง

SCORE THRESHOLD USED: NO

NO-PREFERENCE TESTS: 6 ข้อความตามที่กำหนด ผ่านทั้งหมด — ได้คำถามกลับ และ `match_programs` ไม่ถูกเรียก

WITH-PREFERENCE TESTS: 4 ข้อความตามที่กำหนด ผ่านทั้งหมด — `match_programs` ถูกเรียกด้วยความสนใจที่คัดมา และค่า `limit` / `relevant_only` / `profile_text` เท่าเดิม

FOLLOW-UP TEST: ผ่าน — "เรียนไรดี" → คำถามกลับ → "ชอบเขียนโปรแกรม" → จับคู่ด้วย "เรียนไรดี ชอบเขียนโปรแกรม" และได้คำแนะนำจริง

NON-RECOMMENDATION REGRESSION: ผ่าน — รายชื่อสาขา, ค่าเทอม, คำถามข้อเท็จจริงของสาขา ไม่ถูก gate แตะ

MATCH_PROGRAMS SKIPPED WHEN NO PREFERENCE: YES — ยืนยันด้วย spy ในทุกเคสของกลุ่ม NO PREFERENCE

FULL TEST RESULT: 365 tests / 0 fail (เดิม 350 + ใหม่ 15) · ไม่ต้องแก้ expectation ของชุดเดิมเลย

PRODUCTION TOUCHED: NO

READY FOR CONTROLLED DEPLOY: YES (รออนุมัติ) — backend only, ไม่มี migration, `STRUCTURED_ANSWERS` คงเป็น `on`, rollback ไปที่ image ของ `fe6c57f`

REMAINING RISKS: คำตอบต่อยอดที่ยังไม่มีความสนใจ ("ไม่รู้") ยังไปทางจับคู่เหมือนเดิม (นอกขอบเขต มี test ตรึงไว้) · gate พึ่งสัญญาณ `interest` ที่วัดมา 3 สำนวน ความพลาดที่เป็นไปได้คือถามกลับเกินจำเป็น ซึ่งกู้คืนได้ในเทิร์นถัดไป · margin/limit ยังเท่าเดิม ระบบจึงยังอ้างความครบถ้วนไม่ได้
