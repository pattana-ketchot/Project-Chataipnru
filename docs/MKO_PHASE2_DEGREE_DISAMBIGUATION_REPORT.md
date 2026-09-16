# MKO Phase 2 — Degree-Level Curriculum Disambiguation Stabilization

**สถานะ:** แก้โค้ดและทดสอบใน worktree `course-advisor-system-mko2` (branch `mko-phase2`, HEAD `1493db2`) — **ยังไม่ commit / push / deploy**
- production ยังรันโค้ดเดิม (image `23bd7aa4…`) จึงยังมีอาการเดิมจนกว่าจะได้รับอนุมัติให้ deploy
- ไม่ได้แตะ production DB · ไม่ได้ publish · ไม่ได้ review เพิ่ม · `STRUCTURED_ANSWERS` ยังเป็น shadow · ไม่ได้เริ่ม Phase 3
- ไม่มี schema migration · ไม่ได้แก้ extraction · ไม่ได้ยิง production หรือใช้ Gemini · ไม่ได้รัน behaviour_check
- ไม่มีชื่อสาขาหรือคำถามตัวอย่างถูก hard-code ในโค้ดที่แก้

---

## 1. Root cause

อาการ: ถาม "หลักสูตร**วิทยาศาสตรมหาบัณฑิต** สาขาวิชาการจัดการเทคโนโลยีการเกษตรและบริหารทรัพยากรชุมชน จบไปทำอาชีพอะไร" แล้ว structured ตอบรายการของ **ปริญญาเอก**

ไล่จากโค้ดจริง:

| ขั้น | โค้ด | สิ่งที่เกิดขึ้น |
|---|---|---|
| 1. จับคู่ชื่อหลักสูตร | [course_scope.py:65 `_distinctive_name`](backend/app/services/course_scope.py:65) | ตัดส่วนชื่อปริญญาทิ้ง เหลือแต่ชื่อสาขา — ทั้ง "หลักสูตรวิทยาศาสตรมหาบัณฑิต สาขาวิชา X" และ "หลักสูตรปรัชญาดุษฎีบัณฑิต สาขาวิชา X" กลายเป็น `X` เหมือนกัน จึงถูกรวมเป็นขอบเขตเดียว |
| 2. จำกัดขอบเขต | `_narrow_by_year` (เดิม) | มีตัวกรองเดียวคือ "ปี" ทั้งสองเล่มเป็น พ.ศ. 2568 จึงกรองไม่ออก |
| 3. ตัดสินเส้นทาง | [structured_intent.py `detect`](backend/app/services/structured_intent.py) | เห็นเป็น "หลักสูตรเดียว" (ชื่อสาขาเดียว) จึงส่งไป structured พร้อม course_ids สองตัว |
| 4. อ่านค่า | [curriculum_facts.py `lookup`](backend/app/services/curriculum_facts.py) | field แบบรายการเรียงตาม (ปีใหม่สุด, ชื่อหลักสูตร) แล้ว **หยิบตัวแรก** — "ปรัชญาดุษฎีบัณฑิต" มาก่อน "วิทยาศาสตรมหาบัณฑิต" ตามลำดับอักษรไทย จึงได้ ป.เอก |

**สรุปสาเหตุ:** ตัวตนของหลักสูตรในชั้น resolve/select ใช้แค่ *ชื่อสาขา + ปี* ไม่มี *ระดับ/ชื่อปริญญา* อยู่ในสมการ และเมื่อเหลือหลายเล่มก็เลือกเล่มแรกโดยไม่บอกผู้ใช้

**ข้อมูลที่มีให้ใช้อยู่แล้ว** (ไม่ต้องเพิ่ม schema):
- `public.courses.title` มีชื่อปริญญาอยู่ในชื่อเต็มทุกหลักสูตร
- `mko.field_values` / `v_live_values` มี `degree_level`, `degree_name_th`, `degree_abbr_th` (แต่ live ไม่ครบทุกหลักสูตร จึงไม่ใช้เป็นแหล่งหลัก)
- `mko.curricula.degree_level` ยังเป็น NULL ทุกแถว (ขั้น publish ไม่ได้เติม) จึงใช้ไม่ได้

---

## 2. กลุ่มที่ชื่อสาขา + ปี ซ้ำกันแต่คนละระดับปริญญา

สแกนจากฐานข้อมูล local (เท่ากับ production) ด้วยการอ่านระดับปริญญาจากชื่อหลักสูตรทุกเล่ม — ไม่ได้ระบุชื่อสาขาใดไว้ล่วงหน้า

| กลุ่ม (ชื่อสาขา + ปี) | ระดับปริญญาที่พบ | เอกสาร |
|---|---|---|
| การจัดการเทคโนโลยีการเกษตรและบริหารทรัพยากรชุมชน พ.ศ. 2568 | ปรัชญาดุษฎีบัณฑิต (doctoral), วิทยาศาสตรมหาบัณฑิต (master) | agri68_phd.pdf, agri68_master.pdf |

**พบ 1 กลุ่ม จาก 24 หลักสูตร** — ที่เหลือเป็นระดับปริญญาตรีทั้งหมด ชุดทดสอบสแกนกลุ่มเองทุกครั้ง ถ้าอนาคตมีกลุ่มใหม่จะถูกทดสอบอัตโนมัติ

---

## 3. Solution (generic)

**หลักการ:** ตัวตนของหลักสูตรคือ **programme + edition_year + degree identity** — ระดับปริญญาอ่านจาก metadata ของหลักสูตรเอง

### 3.1 อ่านระดับปริญญาจาก metadata (`course_scope.py`)

- `degree_of_title(title)` — ตัดชื่อปริญญาออกจากชื่อหลักสูตร (ส่วนหน้าคำว่า "สาขาวิชา" หรือทั้งชื่อถ้าไม่มี)
- `degree_level_of(text)` — แปลงเป็น `bachelor` / `master` / `doctoral` จาก
  - ชื่อปริญญา: `…ดุษฎีบัณฑิต`, `…มหาบัณฑิต`, `…บัณฑิต`
  - คำระดับ: `ปริญญาตรี/โท/เอก`, `ป.ตรี/ป.โท/ป.เอก`
  - อักษรย่อ: `X.บ.` / `X.ม.` / `X.ด.` (เช่น วท.บ., วท.ม., ปร.ด.)
  - เรียงจากเฉพาะเจาะจงไปกว้าง เพราะ "ดุษฎีบัณฑิต"/"มหาบัณฑิต" มีคำว่า "บัณฑิต" อยู่ด้วย
  - "บัณฑิต" ที่ไม่มีอักษรไทยนำหน้า (แปลว่าผู้จบการศึกษา) **ไม่นับ** เป็นการระบุระดับ และ "พ.ศ." ไม่ชนกับรูปอักษรย่อ
- `requested_degree_level(question)` — ระดับที่ผู้ใช้ระบุในคำถาม
- `degree_levels_of(ids, titles)` — ระดับทั้งหมดของหลักสูตรชุดหนึ่ง

### 3.2 จำกัดขอบเขตด้วยระดับปริญญา (`course_scope.py`)

`_narrow()` = กรองปีก่อน แล้วกรองระดับปริญญา ใช้ในทั้ง `resolve_scope` และ `resolve_scopes`
- ถ้าผู้ใช้ระบุระดับ → เหลือเฉพาะเล่มระดับนั้น (มีผลกับทั้งเส้นทาง RAG และ structured — RAG จะค้นเฉพาะเล่มที่ถูกด้วย)
- ถ้าระดับที่ระบุไม่ตรงเล่มใดเลย → คงรายการเดิม (กติกาเดียวกับการกรองปี ดีกว่าตัดจนไม่เหลืออะไร)

### 3.3 ไม่เดาเมื่อกำกวม (`structured_intent.py`)

ใน `detect()` ถ้าขอบเขตยังมีหลายระดับปริญญา **และผู้ใช้ไม่ได้ระบุระดับ** → ไม่ตอบจากฐานข้อมูล คืน `RAG` เหตุผล `multiple_degree_levels`
ตรงกับหลักการที่โมดูลนี้เขียนไว้ตั้งแต่ต้นว่า "ถ้าไม่แน่ใจให้พลาดไปทาง RAG" และบันทึกเหตุผลลง `mko.shadow_answers.route_reason` ให้ตรวจย้อนได้

### 3.4 ด่านกันการหยิบเล่มแรกเงียบๆ (`curriculum_facts.py`)

ใน `lookup()` ถ้า field เป็นรายการ (careers / objectives / admission) และชุด ids มีหลายระดับปริญญา → คืน `no_data` พร้อม note บอกว่ามีหลายระดับและให้ระบุระดับ แทนการหยิบเล่มแรก
- **ค่าเดี่ยว (total_credits / edition_year) ไม่ถูกบล็อก** เพราะแสดงทุกฉบับแยกบรรทัดพร้อมชื่อหลักสูตรเต็ม (ซึ่งมีชื่อปริญญาอยู่แล้ว) จึงเป็นการเปิดเผย ไม่ใช่การเลือกแทนผู้ใช้
- เป็นด่านสำรองสำหรับผู้เรียกใช้ `lookup` โดยตรง (เส้นทางปกติถูกกันตั้งแต่ `detect` แล้ว)

---

## 4. Files changed

| ไฟล์ | +/− | สาระ |
|---|---|---|
| `backend/app/services/course_scope.py` | +67 / −3 | helper อ่านระดับปริญญา + `_narrow` (ปี แล้วระดับ) ใช้ใน resolve_scope/resolve_scopes |
| `backend/app/services/structured_intent.py` | +14 / −1 | กำกวม (หลายระดับ + ไม่ได้ระบุ) → RAG `multiple_degree_levels` |
| `backend/app/services/curriculum_facts.py` | +8 / −0 | รายการที่ชุด ids มีหลายระดับ → no_data พร้อมเหตุผล |
| `eval/degree_disambiguation_check.py` | ใหม่ (25 tests) | ชุดทดสอบของรอบนี้ |
| `eval/structured_routing_check.py` | +19 / −1 | ทดสอบเดิมรับรู้กรณีหลายระดับ + เพิ่ม test ใหม่ 1 ข้อ |
| `eval/follow_up_scope_check.py` | +12 / −2 | คู่คำถามต่อเนื่องที่สาขาใหม่มีหลายระดับ คาดหวังพฤติกรรมใหม่ |
| `eval/curriculum_facts_check.py` | +6 / −2 | คำถาม end-to-end ใส่ชื่อปริญญาเมื่อสาขานั้นมีหลายระดับ |

---

## 5. Tests

### 5.1 ก่อน / หลัง

| | ก่อนแก้ | หลังแก้ |
|---|---|---|
| ชุดทดสอบ | 15 | **16** |
| จำนวน test | 249 | **275** |
| ผล | ผ่านทั้งหมด (แต่ผูกพฤติกรรมเดิมที่ผิดไว้) | **ผ่านทั้งหมด 0 fail** |

รันแบบ offline ทั้งหมดกับฐานข้อมูล local (ไม่มี production traffic, ไม่มี Gemini)

### 5.2 ชุดใหม่ `eval/degree_disambiguation_check.py` (25 tests)

| หัวข้อที่กำหนด | test ที่ครอบคลุม | ผล |
|---|---|---|
| 1. ป.โท programme/year ซ้ำ → เลือก ป.โท | `test_master_is_selected_by_degree_name`, `test_level_words_select_the_right_curriculum`, `test_total_credits_with_each_degree` | ✔ |
| 2. ป.เอก → เลือก ป.เอก | `test_doctoral_is_selected_by_degree_name`, เดียวกัน | ✔ |
| 3. ชื่อปริญญาเต็ม | `test_degree_name_is_taken_from_the_title`, `test_master/doctoral_is_selected_by_degree_name` | ✔ |
| 4. อักษรย่อ | `test_abbreviations_select_the_right_curriculum`, `test_degree_level_from_names_and_abbreviations` | ✔ |
| 5. ไม่ระบุระดับ → ไม่เลือกเอง | `test_without_a_degree_every_level_stays_in_scope`, `test_ambiguous_degree_is_not_guessed`, `test_list_field_reports_ambiguity_instead_of_choosing` | ✔ |
| 6. สาขาที่มี curriculum เดียว → เหมือนเดิม | `test_single_level_programme_is_unchanged`, `test_single_level_programme_still_goes_to_the_database`, `test_programmes_with_one_degree_level_still_reach_the_database` | ✔ |
| 7. total_credits | `test_total_credits_with_each_degree`, `test_scalar_field_still_lists_every_edition` | ✔ |
| 8. careers | `test_careers_with_each_degree`, lookup guard | ✔ |
| 9. objectives | `test_objectives_with_each_degree`, lookup guard | ✔ |
| ชุดข้อมูลจริง | `RealCatalogueChecks` — สแกนกลุ่มหลายระดับเองแล้วตรวจทุกกลุ่ม ทุกระดับ ทั้งแบบระบุและไม่ระบุ | ✔ |
| กันความเข้าใจผิด | `test_words_that_are_not_a_degree_request` ("บัณฑิตจบไปทำอาชีพอะไร", "พ.ศ. 2568") | ✔ |

### 5.3 Regression (ชุดเดิมทั้งหมด)

| ชุด | tests | ผล | หมายเหตุ |
|---|---|---|---|
| structured_routing_check | 22 | OK | ข้อ 10 — เพิ่ม 1 test และปรับ 1 test (ดู 5.4) |
| follow_up_scope_check | 21 | OK | ข้อ 11 — ปรับ 1 test (ดู 5.4) |
| comparison_evidence_check | 30 | OK | ข้อ 12 |
| multi_program_scope_check | 12 | OK | ข้อ 12 |
| structured_shadow_check | 18 | OK | ข้อ 13 (off / shadow) |
| conversation_context_check | 12 | OK | ข้อ 14 (out-of-scope / บทสนทนา) |
| recommendation_reply_check | 27 | OK | ข้อ 14 |
| curriculum_facts_check | 16 | OK | ปรับ 1 test (ดู 5.4) |
| mko_extraction_check | 45 | OK | |
| recommend_intent_check | 12 | OK | |
| tuition_followup_check | 14 | OK | |
| program_core_check / rationale_key_check / eval_runner_check / gemini_quota_check | 7 / 4 / 4 / 6 | OK | |
| degree_disambiguation_check | 25 | OK | ชุดใหม่ |
| **รวม** | **275** | **0 fail** | |

### 5.4 ⚠️ ทดสอบเดิมที่เปลี่ยนความคาดหวัง (3 ข้อ)

ทั้งสามข้อเคยผูกพฤติกรรมเดิมไว้ว่า "ชื่อสาขาอย่างเดียวต้องตอบจากฐานข้อมูลเสมอ" ซึ่งเป็นพฤติกรรมที่รอบนี้ตั้งใจแก้ ทั้งหมดปรับให้ **อ่านจากข้อมูลว่าสาขานั้นมีหลายระดับหรือไม่** ไม่ได้ใส่ชื่อสาขาไว้ในเทสต์

| ไฟล์ / test | เดิมคาดหวัง | ใหม่คาดหวัง |
|---|---|---|
| `structured_routing_check.test_every_programme_routes_to_itself` | ทุกสาขา → STRUCTURED | สาขาที่มีหลายระดับ → RAG `multiple_degree_levels` ที่เหลือเหมือนเดิม |
| `follow_up_scope_check.test_every_ordered_pair_keeps_field_and_changes_programme` | ทุกคู่ → STRUCTURED + สาขาใหม่ | ถ้าสาขาใหม่มีหลายระดับ → RAG (ยังตรวจว่าคำถามที่เขียนใหม่เปลี่ยนไปถามสาขาใหม่จริง) |
| `curriculum_facts_check.test_questions_end_to_end` | คำถาม "หลักสูตร{ชื่อสาขา} พ.ศ. {ปี}" | ถ้าสาขานั้นมีหลายระดับ ใส่ชื่อปริญญาในคำถามด้วย (พฤติกรรมที่ถูกของผู้ใช้) |

---

## 6. พฤติกรรมเมื่อกำกวม (ตามที่ออกแบบ)

| กรณี | ผลลัพธ์ |
|---|---|
| ระบุระดับ (ชื่อปริญญา / ป.โท-เอก-ตรี / อักษรย่อ) | เลือกเฉพาะเล่มระดับนั้น แล้วตอบจากฐานข้อมูลตามปกติ |
| ไม่ระบุระดับ และสาขานั้นมีหลายระดับ | `detect` → RAG เหตุผล `multiple_degree_levels` (ผู้ใช้ยังได้คำตอบจากเอกสารตามเส้นทางเดิม) |
| เรียก `lookup` ตรงๆ ด้วย ids หลายระดับ (field รายการ) | `no_data` + note "ชื่อสาขานี้มีหลายระดับปริญญา (…) ระบุระดับปริญญาที่ต้องการ" |
| ค่าเดี่ยว (หน่วยกิต/ปี) ที่ ids มีหลายระดับ | ตอบตามเดิม แยกบรรทัดตามฉบับ พร้อมชื่อหลักสูตรเต็มที่มีชื่อปริญญากำกับ |
| ระดับที่ระบุไม่มีในสาขานั้น | คงขอบเขตเดิม (ไม่ตัดจนว่าง) |

**ผลต่อ shadow เมื่อ deploy:** คำถามที่กำกวมจะบันทึกเป็น `route = rag`, `route_reason = multiple_degree_levels` แทนที่จะเป็น structured ที่ตอบผิดเล่ม

---

## 7. ข้อจำกัดที่เหลือ

1. **อ่านระดับจากข้อความ (lexical)** — รองรับคำไทยและอักษรย่อไทย ยังไม่รองรับคำอังกฤษ เช่น "master degree" หรือ "M.Sc."
2. **ถ้าไม่ระบุระดับ สาขาที่มีหลายระดับจะไม่ถูกตอบจาก structured เลย** (ตกไป RAG) — เป็นทางเลือกที่ปลอดภัยแต่แลกกับ coverage ถ้าต้องการให้ตอบพร้อมบอกว่ามีสองระดับ ต้องออกแบบรูปแบบคำตอบเพิ่มในรอบถัดไป
3. **ยังอาศัยชื่อหลักสูตรใน `public.courses.title`** ถ้าอนาคตมีหลักสูตรที่ชื่อไม่มีชื่อปริญญา จะอ่านระดับไม่ได้และกลับไปมีโอกาสกำกวมเงียบ — ทางแก้ระยะยาวคือเติม `mko.curricula.degree_level`/`program_id` ตอน publish (ไม่อยู่ในขอบเขตรอบนี้ และเป็น schema ที่มีอยู่แล้ว ไม่ต้อง migrate)
4. **ตอนนี้มีกลุ่มเดียวในคลัง** การทดสอบกับข้อมูลจริงจึงครอบคลุมเพียงกลุ่มนั้น (ชุดทดสอบสแกนอัตโนมัติ ถ้ามีกลุ่มใหม่จะถูกตรวจทันที) ส่วนกรณีสามระดับทดสอบด้วยหลักสูตรสมมติ
5. **ยังไม่ได้ทดสอบบน production** — ต้องขออนุมัติ deploy ก่อน และควรตรวจซ้ำด้วย shadow validation ชุดเล็กหลัง deploy
6. เรื่องที่ค้างจากรอบก่อนยังเหมือนเดิม: ATTM 2565 careers / Math 2564 careers ยัง candidate, หน่วย P2 ที่เลื่อน 6 หน่วย, admission ยังไม่มีใน live

---

## 8. git status / diff

```
 M backend/app/services/course_scope.py        (+67/-3)
 M backend/app/services/curriculum_facts.py    (+8/-0)
 M backend/app/services/structured_intent.py   (+14/-1)
 M eval/curriculum_facts_check.py              (+6/-2)
 M eval/follow_up_scope_check.py               (+12/-2)
 M eval/structured_routing_check.py            (+19/-1)
?? eval/degree_disambiguation_check.py         (ใหม่)
?? docs/… รายงาน 9 ฉบับของ Phase 2 (รวมฉบับนี้) ยังไม่ commit
```

branch `mko-phase2` · HEAD ยังเป็น `1493db2` (ไม่มี commit ใหม่)

**ยังไม่ได้ทำ:** commit / push / deploy / publish / review เพิ่ม / เปลี่ยน `STRUCTURED_ANSWERS` / Phase 3
