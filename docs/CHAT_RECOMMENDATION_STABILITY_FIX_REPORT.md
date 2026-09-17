# Chat Recommendation Stability Fix — Offline Implementation Report

วันที่: 2026-09-18 · Branch `mko-phase2` ต่อจาก `6762333`
ขอบเขต: OFFLINE IMPLEMENTATION ONLY — ไม่ยิง production, ไม่เรียก Gemini, ไม่แตะ DB, ไม่ deploy, ไม่ commit, ไม่ push, ไม่รัน behaviour_check
อ้างอิง: `docs/CHAT_BROAD_RECOMMENDATION_RCA.md`

---

## 1. Root cause ที่แก้

`_recommendation_reply` ตัดสาขาที่ขั้นเขียนเหตุผล (Gemini) ไม่ได้ให้ข้อความที่ใช้ได้ ออกจากคำตอบ

```python
supported = [m for m in matches if m.rationale.strip() and NO_EVIDENCE_MARKER not in m.rationale][:3]
```

รายชื่อสาขาที่ผู้ใช้เห็นจึงขึ้นกับการเรียกโมเดลซึ่งไม่นิ่ง ทั้งที่การจัดอันดับคำนวณจากเวกเตอร์และให้ผลเดิมทุกครั้ง
หลักฐานจาก log จริง (5 ครั้ง คำถามเดียวกัน `has_history=false`): ได้ผล 4 แบบ — ไม่มีสาขาเลย / CS / CS+IT / CS+Animation ทั้งที่อันดับที่คำนวณได้คือ CS .561, Animation .542, IT .528 ทุกรอบ

## 2. Files changed

| ไฟล์ | การเปลี่ยนแปลง |
|---|---|
| `backend/app/services/chat.py` | +38 / −63 : เอาตัวกรอง `supported` และสามสาขาข้อความ "ไม่มีสาขาที่แสดงได้" ออก · เพิ่ม `_rationale_line()` กับข้อความคงที่ `_RATIONALE_UNAVAILABLE`, `_RATIONALE_NO_EVIDENCE` · ทุกสาขาที่จัดอันดับมาได้บรรทัดคำอธิบายเสมอ |
| `eval/recommendation_reply_check.py` | +21 / −5 : **เปลี่ยน expectation 2 ข้อ** ให้ตรงกับสัญญาใหม่ (รายละเอียดข้อ 6) |
| `eval/recommendation_stability_check.py` | ใหม่ 12 tests (A–F) |
| `docs/CHAT_RECOMMENDATION_STABILITY_FIX_REPORT.md` | รายงานนี้ |

**ไม่เปลี่ยน:** สูตรคะแนน, `_RELEVANCE_MARGIN 0.04`, `limit=3`, embedding, retrieval, การจัดอันดับ, `_recommendation_intent`, RAG, Structured Answers, Find Major, frontend, DB/schema/data, โมเดล/คอนฟิก/พรอมต์ของ Gemini

## 3. สิ่งที่แก้ (logic)

```python
# เดิม: ตัดสาขาที่ไม่มีเหตุผลออกจากคำตอบ แล้วแตกเป็น 3 กรณีข้อความเมื่อไม่เหลือใครเลย
# ใหม่: รายชื่อ = ผลของ match_programs() เสมอ · เหตุผลที่ใช้ไม่ได้ถูกแทนด้วยข้อความคงที่
def _rationale_line(rationale: str) -> str:
    text = (rationale or "").strip()
    if not text:
        return _RATIONALE_UNAVAILABLE      # ขั้นเขียนเหตุผลล้ม — ยังไม่มีใครดูเอกสารสาขานี้
    if NO_EVIDENCE_MARKER in text:
        return _RATIONALE_NO_EVIDENCE      # โมเดลดูเอกสารแล้วและไม่พบความเชื่อมโยงตรงๆ
    return text
```

ข้อความคงที่ทั้งสอง
- `ตอนนี้ระบบยังเขียนคำอธิบายประกอบให้ไม่ได้ ถามรายละเอียดของสาขานี้ต่อได้เลยครับ`
- `เอกสารหลักสูตรของสาขานี้ไม่ได้ระบุไว้ตรงๆ ว่าเชื่อมโยงกับสิ่งที่คุณบอกอย่างไร สาขานี้มาจากความใกล้เคียงของเนื้อหาโดยรวม`

ทั้งคู่ไม่เพิ่มข้อเท็จจริงใหม่ (ไม่กล่าวถึงรายวิชา อาชีพ หน่วยกิต ค่าเทอม และไม่บอกว่า "เหมาะ" หรือ "ดีที่สุด") และให้ผลเดิมเสมอสำหรับอินพุตเดิม — มี test คุมทั้งสองข้อ

## 4. Behavior before / after

**ก่อนแก้** (คำถามเดียวกัน ไม่มี history — จาก log จริง)
| ครั้งที่ | สาขาที่ผู้ใช้เห็น |
|---|---|
| 15:50 | ไม่มีสาขาเลย ("ยังไม่พบสาขาที่เอกสารหลักสูตรระบุไว้ชัดพอ…") |
| 18:33:20 | วิทยาการคอมพิวเตอร์ |
| 18:33:40 | วิทยาการคอมพิวเตอร์ + เทคโนโลยีสารสนเทศ |
| 18:33:59 | วิทยาการคอมพิวเตอร์ + คอมพิวเตอร์แอนิเมชัน |
| 18:34:17 | วิทยาการคอมพิวเตอร์ + เทคโนโลยีสารสนเทศ |

**หลังแก้** — รายชื่อเท่ากันทุกครั้ง (วิทยาการคอมพิวเตอร์ → คอมพิวเตอร์แอนิเมชัน → เทคโนโลยีสารสนเทศ) เปลี่ยนเฉพาะข้อความใต้ชื่อ

ตัวอย่างจริงจากชุดทดสอบ (ไม่ได้เรียกโมเดล)

*กรณีเขียนเหตุผลได้ครบ*
```
จากความสนใจที่บอกมา สาขาในคณะที่เกี่ยวข้อง ได้แก่
1. วิทยาการคอมพิวเตอร์
   เน้นการพัฒนาซอฟต์แวร์
2. คอมพิวเตอร์แอนิเมชันและมัลติมีเดีย
   เน้นงานแอนิเมชันและมัลติมีเดีย
3. เทคโนโลยีสารสนเทศ
   เน้นระบบสารสนเทศ
```

*กรณีเดียวกันแต่ Animation ติด `[[ไม่มีข้อมูลรองรับ]]` และ IT เขียนไม่ได้*
```
จากความสนใจที่บอกมา สาขาในคณะที่เกี่ยวข้อง ได้แก่
1. วิทยาการคอมพิวเตอร์
   เน้นการพัฒนาซอฟต์แวร์
2. คอมพิวเตอร์แอนิเมชันและมัลติมีเดีย
   เอกสารหลักสูตรของสาขานี้ไม่ได้ระบุไว้ตรงๆ ว่าเชื่อมโยงกับสิ่งที่คุณบอกอย่างไร สาขานี้มาจากความใกล้เคียงของเนื้อหาโดยรวม
3. เทคโนโลยีสารสนเทศ
   ตอนนี้ระบบยังเขียนคำอธิบายประกอบให้ไม่ได้ ถามรายละเอียดของสาขานี้ต่อได้เลยครับ
```

รายชื่อและลำดับเท่ากันทั้งสองกรณี · เครื่องหมายภายใน `[[…]]` ไม่หลุดถึงผู้ใช้

## 5. Offline tests — `eval/recommendation_stability_check.py` (12 tests)

อ่านรายชื่อจากบรรทัดที่ขึ้นต้นด้วยเลขอันดับ แล้วเทียบกับอันดับที่ backend ส่งมา

| ข้อ | test | ผล |
|---|---|---|
| A | rationale ครบทุก candidate → รายชื่อเดิม | OK |
| B | rationale หาย 1 ราย (วนครบทั้ง 3 ตำแหน่ง) → รายชื่อเดิม | OK |
| C | rationale หายหลายราย (ว่างทั้งหมด / ว่าง 2 ราย) → รายชื่อเดิม | OK |
| D | rationale เป็น `NO_EVIDENCE_MARKER` (ทั้งหมด และแบบผสม) → รายชื่อเดิม | OK |
| E | ถ้อยคำต่างกันสองชุด → รายชื่อและลำดับเท่ากัน แต่ข้อความตอบต่างกันจริง | OK |
| F | สลับลำดับที่ backend ส่งมา → คำตอบสลับตาม · เหตุผลยาวกว่าไม่ดันอันดับขึ้น | OK |
| + | รอบตอบต่อยอด (refinement) ก็คงรายชื่อไว้เหมือนกัน | OK |
| + | เครื่องหมาย `[[…]]` ต้องไม่หลุดถึงผู้ใช้ | OK |
| + | แยกสองสาเหตุ (เขียนไม่ได้ / ไม่มีหลักฐาน) ออกจากกัน | OK |
| + | ข้อความแทนไม่กล่าวอ้างข้อเท็จจริงของหลักสูตร | OK |
| + | ข้อความแทนคงที่สำหรับอินพุตเดียวกัน และคำตอบซ้ำได้เหมือนเดิม | OK |
| + | ทุกสาขาในรายการมีบรรทัดคำอธิบายเสมอ | OK |

## 6. Expectation ที่เปลี่ยนใน test เดิม (ต้องรู้ตอน review)

| test | เดิม | ใหม่ | เหตุผล |
|---|---|---|---|
| `test_ไม่มีหลักฐานทุกรายการจึงปฏิเสธได้` → `test_ไม่มีหลักฐานทุกรายการยังต้องคงรายชื่อที่จัดอันดับไว้` | ทุกรายการติด marker → ตอบ "ยังไม่พบสาขา" | แสดงสาขาที่จัดอันดับได้ พร้อมข้อความว่าเอกสารไม่ได้ระบุไว้ตรงๆ · ห้ามมี marker หลุด | ตามขอบเขตที่อนุมัติ: `NO_EVIDENCE_MARKER` ต้องไม่ทำให้ candidate หาย |
| `test_ตอบว่าไม่แน่ใจต้องไม่ขัดกับคำแนะนำรอบก่อน` | รอบต่อยอดที่ทุกรายการติด marker → ตอบประโยค "ยังหาสาขาที่ตรงกว่าเดิมไม่ได้" โดยไม่แสดงรายชื่อ | แสดงรายชื่อที่จัดอันดับได้ต่อ | เจตนาเดิมคือ "ห้ามขัดกับคำแนะนำรอบก่อน" ซึ่งการแสดงสาขาต่อก็ทำได้ และคงที่กว่า |

test อื่นของชุดเดิมผ่านหมดโดยไม่แก้ รวมถึงข้อที่ตรวจว่า "เหตุผลว่างทั้งหมดต้องคงอันดับไว้" และ "กรณีผสมต้องไม่บอกว่าไม่พบสาขา"

การที่สอง test นี้ fail ทันทีหลังแก้โค้ด (ก่อนปรับ expectation) เป็นหลักฐานว่าพฤติกรรมเดิมถูกเปลี่ยนจริงตามที่ตั้งใจ

## 7. Full regression

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
| recommendation_reply_check | 27 | OK |
| **recommendation_stability_check (ใหม่)** | **12** | **OK** |
| structured_on_path_check | 32 | OK |
| structured_routing_check | 22 | OK |
| structured_shadow_check | 30 | OK |
| tuition_followup_check | 14 | OK |
| **รวม** | **350** (เดิม 338 + ใหม่ 12) | **0 fail** |

## 8. สิ่งที่ยังไม่ได้แก้ (นอกขอบเขตรอบนี้)

- ความครบถ้วนของคำแนะนำกว้างยังจำกัดด้วย `_RELEVANCE_MARGIN 0.04` และ `limit=3` ตามที่ระบุห้ามแก้ — ระบบจึงยังอ้างไม่ได้ว่ารายชื่อคือ "ทุกสาขาที่เกี่ยวข้อง"
- ข้อความ `interest` ที่ LLM คัดมาก่อนจับคู่ยังผ่านโมเดล (ข้อ B ใน RCA) ยังไม่ได้ปิดช่องนี้ และยังไม่มี log เก็บค่านี้
- ยังไม่ commit และยังไม่ deploy

---

ROOT CAUSE FIXED: ใช่ — `_recommendation_reply` ไม่ตัดสาขาที่ Gemini เขียนเหตุผลไม่ได้/คืน `NO_EVIDENCE_MARKER` ออกจากคำตอบอีกต่อไป รายชื่อมาจาก `match_programs()` เท่านั้น

FILES CHANGED: `backend/app/services/chat.py` (+38/−63), `eval/recommendation_reply_check.py` (+21/−5, เปลี่ยน expectation 2 ข้อ), `eval/recommendation_stability_check.py` (ใหม่ 12 tests), `docs/CHAT_RECOMMENDATION_STABILITY_FIX_REPORT.md`

BEHAVIOR BEFORE: คำถามเดียวกัน ไม่มี history ได้รายชื่อสาขาต่างกัน 4 แบบใน 5 ครั้ง (ไม่มีสาขาเลย / CS / CS+IT / CS+Animation)

BEHAVIOR AFTER: รายชื่อและลำดับเท่ากับผลการจัดอันดับเสมอ (CS → Animation → IT) เปลี่ยนเฉพาะข้อความใต้ชื่อสาขา · สาขาที่เขียนเหตุผลไม่ได้ได้ข้อความคงที่ที่ไม่กล่าวอ้างเกินหลักฐาน

CANDIDATE SELECTION CHANGED: NO — ยังเป็น `program_match.match_programs(db, …, limit=3, relevant_only=True)` ตัวเดิม

SCORING CHANGED: NO

MARGIN/LIMIT CHANGED: NO (`_RELEVANCE_MARGIN 0.04`, `limit=3` เท่าเดิม)

GEMINI CAN REMOVE CANDIDATE: NO — เพิ่มสาขาก็ไม่ได้ ตัดออกก็ไม่ได้ เหลือเพียงเขียนข้อความอธิบาย

OFFLINE TESTS: 12 tests ใหม่ครอบคลุม A–F ครบ (+ refinement, marker ไม่หลุด, ข้อความแทนคงที่และไม่เพิ่มข้อเท็จจริง) ทั้งหมดผ่าน

FULL REGRESSION: 350 tests / 0 fail (ไม่รัน behaviour_check ตามข้อห้าม)

PRODUCTION TOUCHED: NO — ไม่มี request ไป production, ไม่เรียก Gemini, ไม่เขียน DB, ไม่ deploy, ไม่ commit, ไม่ push

READY FOR CONTROLLED DEPLOYMENT: YES (รออนุมัติ) — deploy backend only, ไม่มี migration, `STRUCTURED_ANSWERS` คงเป็น `on`, rollback ด้วย image tag ของ `6762333`
