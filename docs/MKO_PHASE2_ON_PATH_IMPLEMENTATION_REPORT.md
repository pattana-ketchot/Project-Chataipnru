# MKO Phase 2 — User-Facing Structured ON Path: Implementation

**สถานะ: implement และทดสอบ offline แล้ว — ยังไม่ commit / push / deploy · production flag ยังเป็น `shadow`**

- `STRUCTURED_ANSWERS=on` มีความหมายจริงแล้ว: ตอบผู้ใช้ด้วยข้อมูลหลักสูตรเฉพาะ 4 field ใน allow-list ที่ระบุชื่อทีละตัว
- admission, no_data, route rag และทุกกรณีอื่นได้คำตอบ RAG เดิม · ข้อผิดพลาดของ structured ไม่ทำให้ตอบผู้ใช้ไม่ได้
- ไม่แก้ routing / lookup / ข้อความคำตอบ structured / RAG prompt · ไม่มี migration · ไม่แตะฐานข้อมูลหรือ publication
- tests: **319 / 0 fail** (เดิม 287 + ใหม่ 32) · ไม่มี production traffic · ไม่ใช้ Gemini · ไม่รัน behaviour_check

---

## 1. พฤติกรรมก่อนแก้ (commit 8d6d271)

| โหมด | พฤติกรรมจริง |
|---|---|
| off | ไม่ทำงาน structured · ผู้ใช้ได้ RAG |
| shadow | ผู้ใช้ได้ RAG · หลังตอบแล้ว thread แยกคำนวณ structured และบันทึก `mko.shadow_answers` |
| **on** | **ถูกบังคับกลับเป็น shadow** — `configured_mode("on")` คืน `SHADOW` พร้อมเตือน log "ยังไม่เปิดใน Phase 2" · ไม่มีโค้ดส่วนใดที่ใช้ `structured_answer` ตอบผู้ใช้ |
| ค่าอื่น | off + เตือน log |

---

## 2. Files changed

| ไฟล์ | การเปลี่ยน |
|---|---|
| `backend/app/services/structured_shadow.py` | +68 / −10 : docstring ของโหมด · `SERVED_STRUCTURED` / `SERVED_RAG` · **`USER_FACING_FIELDS`** ([:55](backend/app/services/structured_shadow.py:55)) · `configured_mode` รับ `on` จริง ([:87](backend/app/services/structured_shadow.py:87)) · **`servable_answer`** ([:170](backend/app/services/structured_shadow.py:170)) · **`structured_reply`** ([:186](backend/app/services/structured_shadow.py:186)) · `run_shadow` บันทึก served_source / configured_mode ([:207](backend/app/services/structured_shadow.py:207)) · `submit` ทำงานใน shadow และ on ([:303](backend/app/services/structured_shadow.py:303)) |
| `backend/app/services/chat.py` | +25 / −6 : `Prepared.served_source` ([:467](backend/app/services/chat.py:467)) · **`_with_structured`** ([:995](backend/app/services/chat.py:995)) · เรียกใน `answer_question` ([:1381](backend/app/services/chat.py:1381)) และ `stream_answer` ([:1434](backend/app/services/chat.py:1434)) · ส่ง `served_source` ให้ `shadow_submit` |
| `eval/structured_shadow_check.py` | +5 / −3 : **เปลี่ยน expectation** `test_on_is_held_at_shadow_in_phase2` → `test_on_is_a_real_mode` (on เป็นโหมดจริงตามที่อนุมัติ) และแก้ docstring หนึ่งบรรทัด — test อื่นทั้งหมดไม่เปลี่ยน |
| `eval/structured_on_path_check.py` | ใหม่ 32 tests |
| `docs/MKO_PHASE2_ON_PATH_IMPLEMENTATION_REPORT.md` | รายงานนี้ |

ไม่แก้: `structured_intent.py` (routing) · `curriculum_facts.py` (lookup และข้อความคำตอบ) · `course_scope.py` · prompt ของ RAG · comparator · schema / migration · pipeline

---

## 3. Serving decision (deterministic)

```python
# structured_shadow.py
def servable_answer(db, asked) -> str | None:
    intent = detect(db, asked)                                   # routing เดิม
    if intent.route != STRUCTURED or intent.field not in USER_FACING_FIELDS:
        return None                                              # ไม่ lookup เลย
    result = lookup(db, intent)                                  # lookup เดิม
    if result.status != ANSWERED or not (result.answer or "").strip():
        return None
    return result.answer                                         # ข้อความเดียวกับ structured_answer ของ shadow

def structured_reply(*, question, interpreted) -> str | None:
    try:
        if configured_mode() != ON:
            return None                                          # off / shadow ไม่แตะฐานข้อมูล
        with SessionLocal() as db:                               # session ของตัวเอง ไม่ใช่ session ของคำขอ
            try:
                return servable_answer(db, interpreted or question)
            finally:
                db.rollback()
    except Exception:
        log warning; return None                                 # ผิดพลาด = RAG

# chat.py — answer_question และ stream_answer ใช้ตัวเดียวกัน
p = _with_structured(prepare_answer(...), message)
#   structured_reply(...) is None  -> p เดิมทุกประการ (RAG)
#   มีคำตอบ -> replace(p, canned=answer, status="answered", citations=[], messages=[],
#                      allow_fallback=False, cacheable=False, served_source="structured")
```

| เงื่อนไข | ผล |
|---|---|
| mode = on **และ** route = structured **และ** field ∈ USER_FACING_FIELDS **และ** status = answered **และ** answer ไม่ว่าง | **served_source = structured** · ส่ง `structured_answer` ให้ผู้ใช้ |
| กรณีอื่นทั้งหมด | **served_source = rag** · คำตอบ RAG เดิม |

- **คำถามที่ใช้ตัดสิน:** คำถามที่ตีความแล้ว (`p.interpreted`) ตัวเดียวกับโหมด shadow · ถ้าว่าง (คำตอบจากแคช/คำตอบสำเร็จรูปก่อนขั้นตีความ) ใช้ข้อความของผู้ใช้
- **เมื่อตอบด้วย structured:** ไม่เรียกโมเดลเขียนคำตอบ · meta ของสตรีมส่ง status `answered` และ citations ว่าง (ที่มาอยู่ในบรรทัด "ที่มา:" ของคำตอบ) · บันทึกบทสนทนาด้วยข้อความ structured (คำถามต่อเนื่องจึงเห็นคำตอบที่ผู้ใช้เห็นจริง)
- **ไม่เก็บคำตอบ structured ลงแคช** — แคชไม่รู้โหมด ถ้าเก็บ การย้อนกลับเป็น shadow จะยังตอบข้อความ structured จากแคช · ในทางกลับกัน คำถามที่มีคำตอบ RAG ในแคชอยู่แล้ว เมื่อเปิด on จะได้ structured ตามเงื่อนไข (การตัดสินทำหลังอ่านแคช)

---

## 4. Explicit field allow-list

```python
# structured_shadow.py:55
USER_FACING_FIELDS = frozenset({"total_credits", "edition_year", "careers", "objectives"})
```

- ระบุทีละชื่อ ไม่ใช่ "ทุก field ยกเว้น admission" — field ที่ routing รองรับเพิ่มในอนาคต **default = RAG** จนกว่าจะเพิ่มชื่อไว้ที่นี่ (ทดสอบด้วย field สมมติ `study_plan`, `tuition`, `program_name_th`, `None`)
- เป็น `frozenset` แก้ระหว่างทำงานไม่ได้
- วางไว้คู่กับนิยามโหมดใน `structured_shadow.py` เพราะเป็นที่เดียวที่ตัดสินว่าโหมดทำอะไร (ไม่ย้ายโมดูลเพื่อเลี่ยง refactor)

---

## 5. Admission

- admission ไม่อยู่ใน allow-list → `servable_answer` คืน None **ก่อนเรียก lookup** (ไม่ดึงข้อมูล admission มาตอบเลย)
- ผลในโหมด on: admission ได้ RAG เสมอ แม้มีข้อมูล admission เผยแพร่อยู่ (production มี 10 หลักสูตร)
- routing ยังส่ง admission ไป structured ตามเดิม ใช้สำหรับบันทึกผลเทียบ (served_source = rag) ต่อได้
- เหตุผลบันทึกไว้ในคอมเมนต์ของ constant อ้างถึง `docs/MKO_PHASE2_FINAL_SHADOW_VALIDATION.md` ข้อ B

---

## 6. no_data / error fallback

| กรณี | ผล | ทดสอบ |
|---|---|---|
| structured no_data | RAG | test_08, test_no_data_and_missing_year_are_rag |
| answered แต่ข้อความว่าง | RAG | test_answered_without_text_is_rag |
| route = rag (บรรยาย/เปรียบเทียบ/แนะนำ/จัดอันดับ/หัวข้อที่ไม่รองรับ) | RAG | test_09, 19, 20, 21, unsupported_topic |
| multiple_degree_levels | RAG | test_11, test_multiple_degree_levels_is_rag |
| lookup โยน exception | RAG (log warning) | test_12 |
| เปิด session ฐานข้อมูลไม่ได้ | RAG | test_12 |
| อ่านค่า setting ไม่ได้ | RAG | test_12 |
| off / shadow | ไม่เปิด session ฐานข้อมูลเพื่อตอบผู้ใช้เลย | test_off_and_shadow_never_open_a_database_session_for_serving |

`structured_reply` ใช้ session แยก: query ที่ล้มใน session ของคำขอจะทำให้ transaction เสีย แล้วขั้นบันทึกบทสนทนาหลังจากนั้นพังตาม — แยก session จึงรักษาเส้นทาง RAG ไว้ได้

---

## 7. Logging

- **ไม่มี migration:** คอลัมน์ `mko.shadow_answers.mode` มี `CHECK (mode IN ('shadow','replay'))` จึงคงค่า `shadow` ในคอลัมน์นี้ และบันทึกข้อมูลการตอบใน `comparison_detail` (JSONB)
- ทำงานในโหมด **shadow และ on** (off ไม่บันทึก) · thread แยกหลังตอบเสร็จ คิวมีเพดานเหมือนเดิม

| ข้อมูล | ที่เก็บ |
|---|---|
| configured mode | `comparison_detail.configured_mode` = `shadow` / `on` |
| served source | `comparison_detail.served_source` = `structured` / `rag` |
| route / reason / field / status / publication / facts / structured_answer | คอลัมน์เดิม |
| คำตอบที่ผู้ใช้ได้รับจริง | `served_reply` (ข้อความ structured เมื่อ served_source = structured) |
| comparison | served_source = rag → เทียบเหมือนเดิม · served_source = structured → `not_compared` (ไม่มีคำตอบ RAG ให้เทียบ เพราะไม่ได้เรียกโมเดล) |

ตัวอย่าง query สำหรับเฝ้าดูหลังเปิด on:
```sql
SELECT comparison_detail->>'served_source', intent_field, count(*)
  FROM mko.shadow_answers WHERE comparison_detail->>'configured_mode' = 'on' GROUP BY 1, 2;
```

**ข้อเสนอ (ไม่ได้ทำ):** ถ้าต้องการให้คอลัมน์ `mode` เป็น `on` จริง ต้องมี migration ขยาย CHECK — ไม่จำเป็นสำหรับงานนี้

---

## 8. Tests before / after

### 8.1 ชุดใหม่ `eval/structured_on_path_check.py` (32 tests)

| กลุ่ม | tests | วิธีทดสอบ |
|---|---|---|
| **MODE** 1–6 | off → RAG · shadow → RAG + บันทึก · on + total_credits / edition_year / careers / objectives → structured (ทั้ง answer_question และ stream_answer) · on ใช้คำถามที่ตีความแล้ว | เรียก `answer_question` / `stream_answer` จริง แทนเฉพาะ prepare_answer, โมเดล, การเขียนฐานข้อมูลของคำขอ, detect/lookup · ตรวจว่าไม่เรียกโมเดล ไม่เก็บแคช บันทึกบทสนทนาด้วยข้อความ structured citations ว่าง |
| **ADMISSION** 7, 22 | on + admission answered → RAG และไม่เรียก lookup · admission ยังเป็น RAG แม้มีข้อมูลเผยแพร่ (detect จริงบน DB) · admission ไม่อยู่ใน allow-list | ทั้ง mock และ DB |
| **FALLBACK** 8–12 | no_data · answered ว่าง · route rag · field ไม่อยู่ใน allow-list (รวม field สมมติในอนาคต) · multiple_degree_levels · exception ที่ lookup / SessionLocal / setting | mock |
| **CONTEXT** 13–18 | ตรี CS 2566 = 130 · ป.โท = 36 (ไม่มีคำว่าดุษฎีบัณฑิต) · ป.เอก = 48 (ไม่มีคำว่ามหาบัณฑิต) · หลายฉบับ IT 130/127 และปี 2566/2561 · programme swap (ตอบ IT ไม่ใช่ CS) · year swap (127 ไม่ใช่ 130) · ข้อความต่อเนื่องที่ยังไม่ตีความ → RAG · objectives จาก DB · คำตอบที่ส่งผู้ใช้ = `structured_answer` ของ shadow ทุกตัวอักษร | detect / lookup จริงบน DB local (publication อัตโนมัติ) อ่านอย่างเดียว rollback |
| **SAFETY** 19–22 | เปรียบเทียบ 2 แบบ · แนะนำ 2 แบบ · จัดอันดับ/winner 3 แบบ → route rag และไม่มีคำตอบ structured · หัวข้อที่ไม่รองรับ (ค่าเทอม) | DB |
| **LOGGING** | แถว structured: comparison not_compared, detail = {served_source: structured, configured_mode: on}, mode คอลัมน์ = shadow · แถว RAG ในโหมด on ยังเทียบได้ (agree) · submit ทำงานในโหมด on | DB (commit=False rollback) |
| **ALLOW-LIST** | ค่าเท่ากับ 4 field พอดีและเป็น frozenset | — |

### 8.2 ผลก่อน / หลัง

| ชุด | กับโค้ดก่อนแก้ (8d6d271) | หลังแก้ |
|---|---|---|
| `structured_on_path_check` (ใหม่) | Ran 32 · **failures 8, errors 32** (นับรวม subtest) — on ถูกบังคับเป็น shadow จึงไม่ตอบ structured, และไม่มี `USER_FACING_FIELDS` / `servable_answer` / `structured_reply` / served_source · ผ่านเฉพาะ off → RAG | **Ran 32 · OK** |
| `structured_shadow_check` (แก้ expectation 1 ข้อ) | ชุดเดิมกับโค้ดเดิม OK 30 · ชุดที่แก้แล้วกับโค้ดเดิม fail 1 (`test_on_is_a_real_mode`) | **Ran 30 · OK** |

ข้อความ `RuntimeError: db down / no database / settings broken` ที่เห็นในผลรันคือ warning ที่ตั้งใจให้เกิดใน test_12 (fallback ลง log แล้วตอบ RAG)

---

## 9. Regression (offline ทั้งหมด)

DB local `127.0.0.1:55432` · `CHAT_TOP_K=25` · ไม่มี production traffic · ไม่ใช้ Gemini · ไม่รัน behaviour_check

| suite | tests | ผล |
|---|---|---|
| comparison_evidence_check | 30 | OK |
| conversation_context_check | 12 | OK |
| curriculum_facts_check | 16 | OK |
| degree_disambiguation_check | 25 | OK |
| eval_runner_check | 4 | OK |
| follow_up_scope_check | 21 | OK |
| gemini_quota_check | 6 | OK |
| mko_extraction_check | 45 | OK |
| multi_program_scope_check | 12 | OK |
| program_core_check | 7 | OK |
| rationale_key_check | 4 | OK |
| recommend_intent_check | 12 | OK |
| recommendation_reply_check | 27 | OK |
| structured_routing_check | 22 | OK |
| structured_shadow_check (รวม comparator) | 30 | OK |
| tuition_followup_check | 14 | OK |
| **structured_on_path_check** | **32** | **OK** |
| **รวม** | **319** (เดิม 287) | **0 fail** |

ChatHookChecks เดิม (off กับ shadow ให้คำตอบและลำดับเหตุการณ์เหมือนกันทุกตัวอักษร, shadow พังไม่เปลี่ยนคำตอบ, submit หลังตัวอักษรสุดท้าย) ผ่านทั้งหมดโดยไม่แก้

---

## 10. Git diff summary

```
$ git status --short
 M backend/app/services/chat.py
 M backend/app/services/structured_shadow.py
 M eval/structured_shadow_check.py
?? eval/structured_on_path_check.py
?? docs/MKO_PHASE2_ON_PATH_IMPLEMENTATION_REPORT.md
?? docs/MKO_PHASE2_FINAL_SHADOW_VALIDATION.md          (รายงานรอบก่อน ยังไม่ commit)
?? docs/MKO_PHASE2_P3_PUBLICATION_REPORT.md            (รายงานรอบก่อน)
?? docs/MKO_PHASE2_P3_REVIEW_APPLY_REPORT.md           (รายงานรอบก่อน)
?? docs/MKO_PHASE2_P3_REVIEW_PREVIEW.md                (รายงานรอบก่อน)
?? docs/MKO_PHASE2_SHADOW_CREDIT_COMPARATOR_ROLLOUT_REPORT.md (รายงานรอบก่อน)

$ git diff --stat
 backend/app/services/chat.py              | 31 +++++++++---
 backend/app/services/structured_shadow.py | 78 +++++++++++++++++++++++++++----
 eval/structured_shadow_check.py           |  8 ++--
 3 files changed, 98 insertions(+), 19 deletions(-)
```

secret scan บน diff และไฟล์ test ใหม่: ไม่พบ API key / private key / DB URL ที่มีรหัสผ่าน · ยังไม่ commit

---

## 11. Production untouched

ตรวจแบบ read-only หลังทำงานเสร็จ:

| รายการ | ค่า |
|---|---|
| deployed commit | `8d6d271` (image `5fb3ef40…`, started 2026-09-16T17:48:25Z, restarts 0) — ไม่ได้ deploy |
| STRUCTURED_ANSWERS | `shadow` (.env และคอนเทนเนอร์) — ไม่ได้เปลี่ยน |
| publication | `7999a1c2-e2fd-4b19-98d1-b50b3212f8d9` · publications 4 |
| live values / list_items | 103 / 156 |
| review_decisions | 37 |
| schema migration ล่าสุด | `002_mko_review_publish` — ไม่มี migration ใหม่ |

งานนี้ไม่ต้องเปลี่ยนข้อมูล ไม่ต้อง publish และไม่ขึ้นกับ publication ใด (อ่าน `v_live_*` เหมือนโหมด shadow)

---

## 12. Remaining limitations

1. **ขั้นเตรียมคำตอบของ RAG ยังทำงานก่อนตัดสิน** — การค้นเอกสารและด่านตรวจของ RAG (รวมการเรียก LLM ในด่าน scope/grounding และการเขียนคำถามต่อเนื่องใหม่) ยังเกิดขึ้นทุกคำขอ เพราะต้องได้คำถามที่ตีความแล้วก่อน · เมื่อตอบด้วย structured จะข้ามเฉพาะการเรียกโมเดลเขียนคำตอบ — latency และโควตาโมเดลลดลงเพียงบางส่วน (ตั้งใจไม่ย้ายการตัดสินไปก่อนเพื่อไม่เปลี่ยน routing / flow)
2. **structured มาก่อนคำตอบสำเร็จรูปของ RAG** — ถ้าคำถามเข้าเงื่อนไขครบ ผู้ใช้ได้ structured แม้ขั้น RAG จะตัดสินว่า not_found / out_of_scope (ตามกฎที่อนุมัติ: ตัดสินจาก route / status / field เท่านั้น)
3. **คอลัมน์ `mode` ยังเป็น `shadow`** ในโหมด on — ต้องอ่าน `comparison_detail.configured_mode`
4. **แถวที่ตอบด้วย structured ไม่มีผลเทียบ** (`not_compared`) เพราะไม่มีคำตอบ RAG ให้เทียบ — การเฝ้าดูคุณภาพหลังเปิด on ต้องใช้การตรวจคำตอบโดยตรง
5. **known limitations ที่ยอมรับแล้ว:** careers en65 glyph "น้ า" · ช่องว่างจากการตัดบรรทัดใน objectives · ชื่อหลักสูตรเดิมที่ถูกแทน (fs61 / en60) ได้ค่าของฉบับเก่าพร้อมปีกำกับ · admission ตอบด้วย RAG
6. **ชุด CONTEXT ใช้ DB local** ซึ่งมีเฉพาะ publication อัตโนมัติ (ไม่มี careers / admission live) — careers และ admission ทดสอบด้วยผล lookup ที่ควบคุมได้ ส่วนข้อมูลจริงของ production ตรวจแล้วใน Final Shadow Validation
7. การตั้งค่า `on` อ่านจาก settings ตอนเริ่ม (ต้อง restart backend เพื่อเปลี่ยนโหมด เหมือนเดิม)

---

## 13. Proposed controlled deployment plan (ยังไม่ทำ — รออนุมัติแยกทีละขั้น)

**ขั้น A — deploy โค้ดโดย flag ยังเป็น shadow**
1. ตรวจ git diff / status · รัน 17 suites (คาด 319 / 0 fail) · secret scan · commit เฉพาะ 2 ไฟล์ service + 2 ไฟล์ test + รายงาน
2. backup DB + config · บันทึก commit / image / rollback tag (`rollback-8d6d271`)
3. deploy backend only (ไม่แตะ postgres / frontend / caddy / ollama / ไม่มี migration) · `STRUCTURED_ANSWERS=shadow`
4. ตรวจ health / restarts / errors · shadow smoke ≤ 4 คำขอ — ต้องได้ RAG เหมือนเดิม และแถว shadow มี `served_source = rag`, `configured_mode = shadow`

**ขั้น B — เปลี่ยน flag เป็น on (อนุมัติแยก)**
1. backup `.env` · ตั้ง `STRUCTURED_ANSWERS=on` · restart backend เท่านั้น
2. smoke ≤ 10 คำขอ:
   - total_credits ตรี (CS) · ป.โท (36) · ป.เอก (48) → ผู้ใช้เห็นคำตอบ structured พร้อม "ที่มา:"
   - edition_year หลายฉบับ (คณิตศาสตร์ 2569/2564) · careers (คหกรรมศาสตร์) · objectives (คณิตศาสตร์ 2569)
   - admission (IT 2566) → **ต้องเป็น RAG**
   - no_data control (แอนิเมชัน careers) → RAG
   - ชื่อสาขาหลายระดับไม่ระบุระดับ → RAG
   - follow-up year swap
3. ตรวจ `mko.shadow_answers`: served_source ตรงกับที่คาดทุกแถว · ไม่มี admission ที่ served_source = structured · ไม่มี error / traceback · restarts 0
4. **rollback ของขั้น B:** ตั้งกลับ `STRUCTURED_ANSWERS=shadow` แล้ว restart (ไม่มีคำตอบ structured ค้างในแคช) · **rollback ของขั้น A:** image `rollback-8d6d271`
5. เฝ้าดู 24–48 ชั่วโมง · เกณฑ์ย้อนกลับ: ตอบผิดหลักสูตร / ฉบับ / ระดับ, admission หลุดไป structured, error ใหม่

---

## สิ่งที่ยังไม่ได้ทำ

- deploy / เปลี่ยน production flag / commit / push
- DB write / review / publish / P4 / extraction / normalize / schema migration
- routing redesign / RAG prompt / admission extractor / comparator
- แก้ known limitations (en65 glyph, objectives whitespace, ชื่อหลักสูตรเดิม)
