# MKO Phase 2 — Shadow Comparator: หน่วยกิตรวมระดับบัณฑิตศึกษา

สถานะ: **แก้และทดสอบ local/offline แล้ว — ยังไม่ commit / push / deploy รออนุมัติ**

| รายการ | ค่า |
|---|---|
| branch / HEAD | `mko-phase2` / `668f74c` (ตรงกับ production) |
| production | ไม่ถูกแตะในรอบนี้ — ไม่มี request, ไม่มี query เขียน, ไม่มี deploy |
| STRUCTURED_ANSWERS (production) | `shadow` (ไม่เปลี่ยน) |
| publication / live | `d0311dd5…` / values 100, list_items 90 (ไม่เปลี่ยน) |
| Gemini | ไม่ได้ใช้ |
| behaviour_check | ไม่ได้รัน |

---

## 1. Root cause

`backend/app/services/structured_shadow.py` → `compare()` ส่วน `total_credits` (ก่อนแก้):

```python
found = sorted({int(n) for n in _CREDIT_NUMBER.findall(reply.replace(",", ""))
                if int(n) >= _TOTAL_CREDIT_FLOOR})       # _TOTAL_CREDIT_FLOOR = 100
```

- `_TOTAL_CREDIT_FLOOR` ถูกใช้ **ที่เดียว** คือบรรทัดนี้ ไม่มีโมดูลอื่นอ้างถึง
- ตัวเลขทุกตัวที่ต่ำกว่า 100 ในคำตอบเดิมถูกทิ้งก่อนเทียบ
- ป.โท 2568 = 36 และ ป.เอก 2568 = 48 จึงถูกทิ้ง → `found_in_reply = []` → `_set_verdict` คืน `unclear`
- ค่า structured ถูกต้อง (36 / 48 จากเล่มที่ถูกระดับ) และคำตอบ RAG ก็มีเลข 36 / 48 จริง — ความผิดอยู่ที่ตัวเทียบอย่างเดียว
- ไม่ใช่ regression จาก deploy `668f74c` — เงื่อนไขนี้มีมาตั้งแต่ comparator ถูกเขียนขึ้น แต่ก่อน degree fix ระบบเลือกเล่มผิดระดับอยู่แล้ว จึงไม่เคยเห็นกรณีนี้ชัด

## 2. เหตุผลเดิมของ floor 100

คอมเมนต์เดิมในโค้ด: หน่วยกิตรวมตลอดหลักสูตรปริญญาตรีมากกว่า 100 เสมอ ตัวเลขที่น้อยกว่าในคำตอบคือหน่วยกิตรายหมวด

คำตอบ RAG เรื่องหน่วยกิตมักแจกแจงโครงสร้างหลักสูตรด้วย เช่น

> ไม่น้อยกว่า 130 หน่วยกิต หมวดวิชาศึกษาทั่วไป 30 หน่วยกิต หมวดวิชาเฉพาะ 94 หน่วยกิต หมวดวิชาเลือกเสรี 6 หน่วยกิต

ถ้าไม่มี floor ตัวเทียบจะได้ `found = {130, 30, 94, 6}` ≠ `{130}` → ตัดสิน `partial` ทั้งที่คำตอบถูก และคำตอบที่บอกยอดรวมผิดแต่มีเลขหมวดตรงกับยอดรวมบังเอิญอาจได้ผลผิดทาง floor จึงกัน **false match จากหน่วยกิตรายหมวด** (มี test เดิม `CompareChecks.test_total_credits` ยืนยันพฤติกรรมนี้)

สมมติฐานนี้ถูกสำหรับปริญญาตรีในคลังจริง (ตรวจข้อ 7) แต่ไม่ถูกสำหรับบัณฑิตศึกษา

## 3. Metadata ที่ comparator ได้รับ (ไม่ต้องเพิ่ม schema)

`compare(result: FactsResult, served_status, served_reply)` — `result.facts` เป็น `EditionFact` ที่มี

| field | ใช้ได้ไหม |
|---|---|
| `course_title` | ✅ ชื่อหลักสูตรเต็ม มีชื่อปริญญา เช่น `หลักสูตรวิทยาศาสตรมหาบัณฑิต สาขาวิชา… (พ.ศ. 2568)` |
| `edition_year` | ✅ |
| `value_int` | ✅ ค่า total_credits ที่คาดหวัง |
| `source` / `reviewed_by` | ✅ มี แต่ไม่จำเป็นสำหรับการแก้นี้ |

ระดับปริญญาอ่านได้จาก `course_title` ด้วย helper ที่ deploy แล้วใน `668f74c`: `course_scope.degree_of_title()` + `degree_level_of()` → `bachelor` / `master` / `doctoral` / `None`
ไม่มี import cycle (`course_scope` ไม่ import `structured_shadow`)

## 4. Solution

แก้เฉพาะ `structured_shadow.py` ส่วนตัวเทียบ:

```python
_GRADUATE_LEVELS = frozenset({"master", "doctoral"})
_TOTAL_CREDIT_CONTEXT = re.compile(
    r"(?:ตลอดหลักสูตร|หน่วยกิตรวม)[^0-9\n]{0,40}?(\d{1,3})\s*หน่วยกิต"
    r"|(\d{1,3})\s*หน่วยกิต(?:รวม)?ตลอดหลักสูตร"
)

def _fact_levels(result):            # ระดับปริญญาของทุกฉบับที่เทียบ (อ่านไม่ได้ = None)
def _total_credits_in_reply(reply, levels):
    found = {เลข >= _TOTAL_CREDIT_FLOOR}                       # กฎเดิม ทุกระดับ
    if levels and levels <= _GRADUATE_LEVELS:                 # ทุกฉบับเป็น ป.โท/ป.เอก เท่านั้น
        found |= {เลขที่อยู่ในบริบท "ยอดรวมตลอดหลักสูตร"}
```

กติกาการตัดสิน (`_set_verdict`) ไม่เปลี่ยน — `agree / partial / disagree / unclear` ความหมายเดิม
`detail` ที่บันทึกลง `mko.shadow_answers` เพิ่ม key `degree_levels` เพื่อให้คนอ่านซ้ำรู้ว่าใช้กฎชุดไหน (ข้อมูลประเมินผลเท่านั้น ไม่มีผลกับผู้ใช้ ไม่ต้องแก้ schema เพราะคอลัมน์เป็น JSON)

### เงื่อนไขทั้งสองต้องจริงพร้อมกัน

| เงื่อนไข | กันอะไร |
|---|---|
| **(1) ทุกฉบับที่เทียบเป็นบัณฑิตศึกษา** | ปริญญาตรีไม่ได้รับกฎใหม่เลย → protection เดิมคงอยู่ครบ; ชื่อที่อ่านระดับไม่ได้ (`None`) หรือชุดที่ปนระดับ ไม่ผ่าน `levels <= _GRADUATE_LEVELS` → ใช้กฎเดิมที่เข้มกว่า |
| **(2) เลขอยู่ในบริบทยอดรวม** (`ตลอดหลักสูตร` / `หน่วยกิตรวม` นำหน้า หรือ `…หน่วยกิตตลอดหลักสูตร` ตามหลัง) | หน่วยกิตรายหมวด (`หมวดวิชาบังคับ 24 หน่วยกิต`) และหน่วยกิตวิทยานิพนธ์ (`วิทยานิพนธ์ 12 หน่วยกิต`) ของบัณฑิตศึกษาเอง ไม่ถูกนับเป็นยอดรวม; `[^0-9\n]` ทำให้ข้ามตัวเลขอื่นไม่ได้ เช่น `ตลอดหลักสูตร 2 ปี … 12 หน่วยกิต` ไม่ match |

## 5. ทำไมไม่ลด floor แบบ global

- ถ้าลด floor เป็น เช่น 30: คำตอบปริญญาตรี `130 หน่วยกิต หมวดศึกษาทั่วไป 30 หน่วยกิต` → found `{130, 30}` → `partial` แทน `agree` (test เดิมพัง) และคำตอบที่มีแค่เลขหมวดจะถูกตัดสินเป็น `disagree` แทน `unclear`
- ถ้าลดเป็น 24: ป.โท ที่มี `หมวดวิชาบังคับ 24 หน่วยกิต` + ยอดรวม 36 → `partial` แทน `agree`
- ไม่มีค่า floor เดียวที่แยก "ยอดรวมบัณฑิตศึกษา" (36–48) ออกจาก "หน่วยกิตรายหมวดปริญญาตรี" (6–94) ได้ เพราะช่วงซ้อนกัน

## 6. ทำไมไม่ใช้ "มีเลข expected อยู่ในคำตอบ" อย่างเดียว

พิจารณาแล้วไม่เลือกเป็นกฎหลัก เพราะ

- ถ้า anchor ที่ expected value ตัวเทียบจะมองไม่เห็นยอดรวมที่ **ผิด** — ป.เอก expected 48 แต่คำตอบบอก `รวมตลอดหลักสูตร 36 หน่วยกิต` จะได้ `unclear` แทน `disagree` (สัญญาณที่ shadow ต้องการจับที่สุด)
- เลข expected อาจปรากฏในความหมายอื่นโดยบังเอิญ เช่นหน่วยกิตหมวดที่เท่ากับยอดรวมของอีกระดับ → false `agree`
- กฎบริบทให้ทั้ง agree ที่ถูก และ disagree ที่ถูก (test 6) โดยไม่ขึ้นกับค่าที่คาดหวัง

## 7. ตรวจสมมติฐานกับคลังข้อมูลจริง (local, ข้อมูล mko เหมือน production)

`mko.v_live_values` field `total_credits` ทั้งหมด 20 ค่า:

| ระดับ (อ่านจาก course_title) | จำนวน | ค่าที่พบ | ต่ำกว่า 100 |
|---|---|---|---|
| bachelor | 18 | 124, 127, 130, 135, 138, 147, 149 | ไม่มี |
| master | 1 | 36 | 36 |
| doctoral | 1 | 48 | 48 |
| อ่านระดับไม่ได้ | 0 | — | — |

- ทุกชื่อหลักสูตรอ่านระดับได้ รวมชื่อที่ไม่ขึ้นต้นด้วย "วิทยาศาสตร" (`ศิลปศาสตรบัณฑิต`, `การแพทย์แผนไทยประยุกต์บัณฑิต`)
- floor 100 ยังถูกสำหรับปริญญาตรีทุกค่า; ค่าที่ต่ำกว่า floor มีเฉพาะบัณฑิตศึกษา → กฎที่แยกตามระดับตรงกับข้อมูลจริง

## 8. Files changed

| ไฟล์ | การเปลี่ยน |
|---|---|
| `backend/app/services/structured_shadow.py` | +38 / −2 : import helper ระดับปริญญา, ค่าคงที่ `_GRADUATE_LEVELS` / `_TOTAL_CREDIT_CONTEXT`, `_fact_levels()`, `_total_credits_in_reply()`, ใช้ใน `compare()` + `degree_levels` ใน detail |
| `eval/structured_shadow_check.py` | +122 / −3 : `facts()` รับ `titles=` (ค่าเริ่มต้นเหมือนเดิม), ชื่อหลักสูตรสมมุติ 4 ชื่อ, คลาส `GraduateCreditCompareChecks` 12 tests |
| `docs/MKO_PHASE2_SHADOW_CREDIT_COMPARATOR_REPORT.md` | รายงานนี้ (ใหม่) |

ไม่แก้: routing (`structured_intent.py`), lookup (`curriculum_facts.py`), `course_scope.py`, RAG, prompt, extraction, schema, chat flow
test เดิมทุกข้อไม่ถูกแก้ expectation — `facts()` ที่ไม่ส่ง `titles` ให้ชื่อ `ฉบับ n` เหมือนเดิม

ชื่อหลักสูตรใน test เป็นชื่อสมมุติ `สาขาวิชาทดสอบ` ใช้แค่รูปแบบชื่อปริญญา ไม่มีชื่อสาขาจริงและไม่มีเลข 36/48 ในโค้ด service

## 9. Tests before / after

### ชุดทดสอบ comparator (รันชุด test ใหม่กับ comparator ตัวเดิมจาก `HEAD` โดยโหลดซอร์สเดิมแทนในหน่วยความจำ ไม่สลับไฟล์)

| # | test | ความต้องการ | BEFORE (HEAD) | AFTER |
|---|---|---|---|---|
| 1 | bachelor 124/127/128/130 agree | agree | ✅ pass | ✅ pass |
| 2 | bachelor 130 vs มีแต่ 24/30 | ไม่ agree (unclear) | ✅ pass | ✅ pass |
| 3 | master 36 agree (3 รูปประโยค รวมเลขไทย ๓๖) | agree | ❌ unclear | ✅ pass |
| 4 | doctoral 48 (และ 54) agree | agree | ❌ unclear | ✅ pass |
| 5 | master 36 vs มีแต่ 24 / วิทยานิพนธ์ 12 / ไม่มีเลข | ไม่ agree (unclear) | ✅ pass | ✅ pass |
| 6 | doctoral 48 vs ตอบ 36 และ master 36 vs ตอบ 48 | disagree | ❌ unclear | ✅ pass |
| 7 | หลายตัวเลข (12, 6, 18) + ยอดรวม 36 | agree, found=[36] | ❌ unclear | ✅ pass |
| 8 | multi-edition 124/130 (agree, partial) + ป.โท 2 ฉบับ | ไม่เปลี่ยน | ❌ เฉพาะบรรทัด ป.โท; บรรทัด 124/130 ผ่านทั้งก่อนและหลัง | ✅ pass |
| 9 | careers / objectives / admission / edition_year บนชื่อทุกระดับ | ไม่เปลี่ยน | ✅ pass | ✅ pass |
| 10 | served_no_answer / not_compared | ไม่เปลี่ยน | ✅ pass | ✅ pass |
| + | ชื่ออ่านระดับไม่ได้ / ชุดปนระดับ ใช้กฎเดิม | unclear / found=[130] | ✅ pass | ✅ pass |
| + | detail มี `degree_levels` | — | ❌ (ยังไม่มี key) | ✅ pass |
| เดิม | `CompareChecks` 4 tests | ไม่เปลี่ยน | ✅ pass | ✅ pass |

BEFORE: 16 run / 8 fail — ทุกข้อที่ fail เป็นเส้นทางบัณฑิตศึกษา (หรือ key ใหม่) ข้อที่เป็นปริญญาตรี, false-positive protection และ field อื่น ผ่านทั้งก่อนและหลัง → พฤติกรรมปริญญาตรีไม่เปลี่ยน
AFTER: 16 run / 0 fail

### Offline replay ด้วยคำตอบจริงจาก Controlled Shadow Validation รอบก่อน

ใช้คำตอบที่บันทึกไว้แล้วจากรอบ `668f74c` (ไม่ยิง production ซ้ำ) → `detect` + `lookup` บนฐาน local → `compare` ทั้งตัวเดิมและตัวใหม่ → `run_shadow(commit=False)` แล้ว rollback

| case | เล่มที่ structured เลือก | BEFORE | AFTER |
|---|---|---|---|
| 6-credits-master | วิทยาศาสตรมหาบัณฑิต … (พ.ศ. 2568) | `unclear` expected [36] found [] | **`agree`** expected [36] found [36] levels [master] |
| 7-credits-phd | ปรัชญาดุษฎีบัณฑิต … (พ.ศ. 2568) | `unclear` expected [48] found [] | **`agree`** expected [48] found [48] levels [doctoral] |

## 10. Bachelor / master / doctoral results (สรุป)

| ระดับ | ยอดรวมถูก | เลขหมวด/วิทยานิพนธ์อย่างเดียว | ยอดรวมผิด |
|---|---|---|---|
| bachelor | agree (ไม่เปลี่ยน) | unclear (ไม่เปลี่ยน) | disagree เมื่อเลข ≥ 100 (ไม่เปลี่ยน) |
| master | **agree** (เดิม unclear) | unclear | **disagree** (เดิม unclear) |
| doctoral | **agree** (เดิม unclear) | unclear | **disagree** (เดิม unclear) |

## 11. False-positive protection

| สถานการณ์ | ผล |
|---|---|
| ปริญญาตรี มีแต่เลขหมวด 24 / 30 | unclear — กฎใหม่ไม่ทำงานกับปริญญาตรี |
| ปริญญาตรี เขียน `หน่วยกิตรวมตลอดหลักสูตรของหมวดนี้ 24 หน่วยกิต` | unclear — บริบทไม่ถูกใช้กับปริญญาตรีเลย |
| ป.โท มีแต่ `หมวดวิชาบังคับ 24 หน่วยกิต` | unclear — ไม่มีบริบทยอดรวม |
| ป.โท `ตลอดหลักสูตร 2 ปี มีวิทยานิพนธ์ 12 หน่วยกิต` | unclear — `[^0-9]` ข้ามเลข 2 ไม่ได้ |
| ป.โท มีเลข 12/6/18 + ยอดรวม 36 | found = [36] เท่านั้น |
| ชื่อหลักสูตรอ่านระดับไม่ได้ | กฎเดิม |
| ชุดที่ปน ป.โท กับ ป.ตรี | กฎเดิม — found = [130] ไม่รับ 36 |

## 12. Regression results

รันทั้ง 16 suites แบบ offline (local Postgres `127.0.0.1:55432`, `CHAT_TOP_K=25`, ไม่มี Gemini, ไม่มี behaviour_check)

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
| structured_shadow_check | **30** (เดิม 18) | OK |
| tuition_followup_check | 14 | OK |
| **รวม** | **287** (เดิม 275 + ใหม่ 12) | **0 fail** |

หมายเหตุสภาพแวดล้อม: ถ้ารันโดยไม่ตั้ง `DATABASE_URL`/`JWT_SECRET` บาง suite error ตอน import settings และถ้า console เป็น cp1252 สอง suite (`degree_disambiguation_check`, `eval_runner_check`) error ตอน `print` ภาษาไทย — ทั้งสองเป็นเรื่อง env ไม่เกี่ยวกับการแก้นี้ ผลข้างบนรันด้วย env ครบและ `PYTHONIOENCODING=utf-8`

แยกหัวข้อที่ขอให้ตรวจ

| หัวข้อ | ผล |
|---|---|
| structured shadow | 30/30 |
| structured routing | 22/22 — ไม่ได้แก้ routing |
| curriculum facts | 16/16 — ไม่ได้แก้ lookup |
| degree disambiguation | 25/25 |
| follow-up | 21/21 (+ conversation_context 12/12) |
| comparison | 30/30 |
| out-of-scope | ครอบคลุมใน `test_10` (served_no_answer สำหรับ out_of_scope) และ suite routing/recommend |
| ปริญญาตรี 124/127/128/130 | agree ทุกค่า (test 1) |
| ป.โท 36 / ป.เอก 48 | agree (test 3, 4, replay) |
| multi-edition | ไม่เปลี่ยน (test 8) |
| เลขหมวดไม่ถูกนับเป็นยอดรวม | test 2, 5, 7 |

## 13. Remaining limitations

1. **คำตอบบัณฑิตศึกษาที่ไม่มีคำบอกบริบทยอดรวม** เช่น `หลักสูตรนี้เรียน 36 หน่วยกิต` จะยังได้ `unclear` — เลือกให้พลาดทางระมัดระวัง (ไม่รู้ = unclear) แทนการเดา คำตอบจริงสองรายการที่เห็นใน production ใช้ `รวมตลอดหลักสูตร` ทั้งคู่
2. **รูปประโยคบริบทมีจำกัด** — รับ `ตลอดหลักสูตร`, `หน่วยกิตรวม`, `…หน่วยกิตตลอดหลักสูตร` ในระยะ 40 ตัวอักษร ถ้า LLM ใช้ถ้อยคำอื่น (เช่น `ทั้งหมด 36 หน่วยกิต`) จะได้ `unclear`
3. **ยอดรวมปริญญาตรีที่ผิดแต่ต่ำกว่า 100** ยังได้ `unclear` แทน `disagree` — เป็นพฤติกรรมเดิม ไม่ได้แก้ในรอบนี้
4. **ป.โท/ป.เอก ที่มีหลายแผน** (แผน ก1/ก2/ข ที่ยอดรวมต่างกัน) ข้อมูลปัจจุบันมีหนึ่งค่าต่อเล่ม ถ้าคำตอบบอกยอดรวมหลายแผนจะได้ `partial` — ขึ้นกับการ extract ไม่ใช่ตัวเทียบ
5. **ระดับปริญญาขึ้นกับชื่อหลักสูตรใน `courses.title`** — ชื่อที่อ่านไม่ได้จะใช้กฎเดิม (ปัจจุบัน 20/20 อ่านได้)
6. ตัวเทียบยังเป็นกฎข้อความแบบง่ายตามที่ docstring ระบุ ใช้ดูแนวโน้ม ไม่ใช่ตัวตัดสินความถูกต้อง
7. แถว `mko.shadow_answers` เดิมใน production (สอง `unclear` ของรอบ validation) ไม่ถูกคำนวณใหม่ — จะเห็นผลใหม่เฉพาะแถวที่เกิดหลัง deploy

## 14. Git diff / status

```
$ git log --oneline -1
668f74c fix(mko): pick the curriculum by degree level when a programme has several of them

$ git status --short
 M backend/app/services/structured_shadow.py
 M eval/structured_shadow_check.py
?? docs/MKO_PHASE2_DEGREE_DISAMBIGUATION_ROLLOUT_REPORT.md
?? docs/MKO_PHASE2_SHADOW_CREDIT_COMPARATOR_REPORT.md

$ git diff --stat
 backend/app/services/structured_shadow.py |  38 +++++++++-
 eval/structured_shadow_check.py           | 122 +++++++++++++++++++++++++++++-
 2 files changed, 155 insertions(+), 5 deletions(-)
```

- secret scan บน diff: ไม่พบ key / token / password (มีเพียง `JWT_SECRET=local-test-only` ที่มีอยู่เดิมใน test)
- ไม่มีการเปลี่ยน line ending ใน blob (คำเตือน LF→CRLF เป็นของ working copy บน Windows ตามปกติ)
- `docs/MKO_PHASE2_DEGREE_DISAMBIGUATION_ROLLOUT_REPORT.md` เป็นรายงานรอบก่อนที่ยังไม่ commit ไม่เกี่ยวกับการแก้นี้

## 15. ยังไม่ทำ (ตามขอบเขต)

- ไม่ commit / push / deploy
- ไม่เปิด `STRUCTURED_ANSWERS=on`, ไม่เริ่ม Phase 3
- ไม่ review / publish เพิ่ม, ไม่แก้ extraction / schema / routing / RAG / prompt
- ไม่ยิง production traffic, ไม่รัน behaviour_check

หากอนุมัติ deploy แบบ controlled shadow: backend-only, ไม่มี migration, และตรวจด้วยคำถามหน่วยกิต ป.โท / ป.เอก / ปริญญาตรีหนึ่งหลักสูตร ให้ `comparison` เป็น `agree` พร้อม `degree_levels` ในแถว shadow
