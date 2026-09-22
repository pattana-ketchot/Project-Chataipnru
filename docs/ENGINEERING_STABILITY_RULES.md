# SCI Advisor — Engineering Stability Rules

กฎกลางสำหรับ AI Coding Agent (และคน) ทุกตัวที่แก้ไขระบบ SCI Advisor
ใช้กับงานที่ **แก้พฤติกรรมเดิมของระบบ** ทุกชนิด ไม่ว่าจะเป็น backend, retrieval, prompt, structured data หรือ frontend

> **ค่าเริ่มต้นของโปรเจกต์ตอนนี้คือ "ไม่แก้"** จนกว่าจะมีหลักฐานว่าจำเป็นต้องแก้
> เป้าหมายคือ **ROBUST ENOUGH TO USE AND DEMO** ไม่ใช่ PERFECT FOR EVERY POSSIBLE INPUT

---

## 1. Purpose

SCI Advisor อยู่ในช่วงที่ต้องการ **ความเสถียร** มากกว่าความสามารถใหม่ เอกสารนี้มีไว้กันปัญหาสี่อย่าง

1. **แก้บ่อยเกินไป** — คำตอบที่ "ไม่สวย" ไม่ได้แปลว่าเป็น bug เสมอ
2. **Patch-chase** — แก้ให้ประโยคตัวอย่างหนึ่งผ่าน แล้วประโยคข้างเคียงยังพังเหมือนเดิม
3. **Scope creep** — ถือโอกาสแก้หรือ refactor ส่วนอื่นระหว่างแก้ bug
4. **แก้ผิด layer** — ซ่อนอาการไว้ที่ prompt / routing / hardcode ทั้งที่ต้นเหตุอยู่ที่อื่น

ขอบเขต: ใช้กับทุกการเปลี่ยนแปลงพฤติกรรมเดิม · ไม่ใช้กับงานเอกสาร งานอ่านอย่างเดียว หรือ feature ใหม่ที่ได้รับอนุมัติแยก (แต่ feature ใหม่ต้องไม่ปนกับ bug fix — ข้อ 2)

### Project anchors (ข้อเท็จจริงที่กฎนี้อ้างถึง ตรวจจาก repository แบบอ่านอย่างเดียว)

| สิ่งที่อ้าง | ที่อยู่ / สถานะ |
|---|---|
| ชุดทดสอบ offline | `eval/*_check.py` (unittest) 20 ชุด รันด้วย `python -m eval.<name>` · ผ่านล่าสุด 365 tests / 0 fail (`docs/CHAT_RECOMMENDATION_CLARIFICATION_FIX.md`) |
| ชุดที่ยิง production | `eval/behaviour_check.py` — ค่าเริ่มต้นยิงเว็บจริง **ห้ามรวมในการรัน regression ปกติ** |
| CI | NOT FOUND (ไม่มี `.github/` หรือ config CI อื่น) — regression รันด้วยมือ |
| คลังคำย่อ/ชื่อเรียกสาขา (alias) กลาง | `backend/app/services/query_expansion.py` → `ALIASES` (ใช้ร่วมโดย `course_scope.py`, `follow_up.py`) |
| ชื่อสาขาที่เปลี่ยนตอนปรับปรุงหลักสูตร | `backend/app/services/web_compat.py` → `_ALIASES` |
| รายการสาขาที่เปิดรับ | `backend/app/data/programs_offered.json` (แก้ที่ไฟล์นี้ที่เดียว) |
| รุ่นของตรรกะในแคชคำตอบ | `backend/app/services/answer_cache.py` → `_LOGIC_VERSION` (ต้องเพิ่มเมื่อแก้ตรรกะการตอบ ตาม `docs/NEXT_STEPS.md`) |
| สถานะ production | `~/DEPLOYED_COMMIT` และ `~/ROLLBACK.txt` บนเซิร์ฟเวอร์ |
| Agent rules เดิม (`CLAUDE.md`, `AGENTS.md`) | NOT FOUND — เอกสารนี้เป็นกฎกลางฉบับแรก |

---

## 2. Bug Classification

**ก่อนเปิดงานแก้ใดๆ ต้องจัดประเภทก่อนเสมอ** และจัดได้มากกว่าหนึ่งประเภท แต่ทุกประเภทที่เลือกต้องมีหลักฐาน

| ประเภท | ลักษณะ | การตัดสินใจเริ่มต้น |
|---|---|---|
| **A. REAL BUG** | error / exception · ตรรกะผิด · ข้อเท็จจริงที่ไม่มีหลักฐานรองรับ (hallucination) · routing ผิด · flow หลักพัง · ผลลัพธ์ไม่นิ่งทั้งที่อินพุตเหมือนเดิม | ทำ RCA แล้วพิจารณาแก้ |
| **B. UX GAP** | ถ้อยคำไม่สวย · ตอบซ้ำ · ยาวไป/สั้นไป · edge case เล็กน้อย | **ค่าเริ่มต้น = บันทึกเป็นข้อจำกัดแล้วยอมรับ** · แก้เฉพาะเมื่อกระทบ flow หลัก, เกิดบ่อย, หรือขวางการสาธิต (demo-blocking) |
| **C. DATA QUALITY** | ข้อมูลต้นทางผิด/ขาด/อ่านผิด (OCR, การสกัด, metadata, การ review) | แก้ที่ **source data / ingestion / metadata / review pipeline เท่านั้น** (ข้อ 6) |
| **D. ACCEPTED LIMITATION** | ข้อจำกัดที่ตัดสินใจรับไว้แล้วและบันทึกแล้ว | บันทึก → **FREEZE** |
| **E. FEATURE REQUEST** | ความสามารถใหม่ที่ระบบไม่เคยสัญญาว่าจะทำ | ลง backlog · **ห้ามรวมกับ bug fix** |

ตัวอย่างการจัดประเภทจริงในโปรเจกต์นี้
- รายชื่อสาขาในแชทเปลี่ยนไปตามผลของขั้นเขียนเหตุผล ทั้งที่อันดับคงที่ → **REAL BUG** (`docs/CHAT_BROAD_RECOMMENDATION_RCA.md`, แก้ใน `fe6c57f`)
- "เรียนไรดี" ได้สามสาขาที่อธิบายไม่ได้ → **UX GAP** ที่แสดงผลที่ไม่มีหลักฐาน จึงแก้ (`docs/CHAT_RECOMMENDATION_CLARIFICATION_RCA.md`, `f2450a0`)
- ตัวอักษร "น้ า" เพี้ยนในรายการอาชีพ en65 → **DATA QUALITY** ที่รับไว้เป็นข้อจำกัด ไม่แก้ด้วย prompt (`docs/MKO_PHASE2_P3_REVIEW_APPLY_REPORT.md`)
- คุณสมบัติผู้เข้าศึกษา (admission) ยังตอบด้วย RAG เพราะข้อมูล structured ไม่ครบ → **ACCEPTED LIMITATION** ที่ถูกกันไว้ด้วย allow-list (`docs/MKO_PHASE2_FINAL_SHADOW_VALIDATION.md`)

---

## 3. Evidence / RCA Rules

**ห้ามประกาศ root cause จากการเดา** ทุกข้อสรุปต้องชี้ไปที่หลักฐานได้

หลักฐานที่ยอมรับ
- log ที่มีอยู่แล้ว (เช่น `mko.shadow_answers`, log ของ backend container)
- เส้นทางในโค้ด (ระบุไฟล์ + ฟังก์ชัน + บรรทัด)
- การทำซ้ำแบบ deterministic
- test ที่มีอยู่ หรือ test ใหม่ที่ fail ก่อนแก้
- retrieval trace, ผลดิบของโมเดล (raw model output)
- การอ่านฐานข้อมูลแบบ read-only (`BEGIN READ ONLY … ROLLBACK`)
- รายงานเดิมใน `docs/`

กติกา
1. ทุกหลักฐานต้องบอก 3 อย่าง: **หลักฐานคืออะไร · พิสูจน์อะไร · ยังไม่แน่ใจอะไร**
2. ถ้าหลักฐานไม่พอ ให้ตอบ **UNKNOWN / NEEDS CONTROLLED TEST** ห้ามเติมช่องว่างด้วยการคาดเดา
3. การสังเกตเพิ่มเติมให้ทำแบบ local/offline ก่อน · การยิง production ทำได้เฉพาะเมื่อได้รับอนุมัติ พร้อมเพดานจำนวน request ที่ระบุชัด
4. instrumentation ชั่วคราวทำได้เฉพาะ local/offline และ **ต้องลบก่อนจบงาน**
5. **ห้ามสร้าง observability infrastructure ใหม่เอง** (ตาราง log ใหม่, service ใหม่, dashboard ใหม่) โดยไม่ได้รับอนุมัติแยก
6. หลักฐานที่ขัดกับสมมติฐาน ต้องรายงาน ห้ามตัดทิ้ง

ขั้นตอนบังคับ

```
OBSERVE → EVIDENCE → ROOT CAUSE → CLASSIFY → GENERAL RULE
        → OWNING LAYER → MINIMAL FIX → TEST → VALIDATE → FREEZE
```

---

## 4. Root-Cause Ownership

1. **แก้ที่ layer ที่เป็นเจ้าของ root cause** (ข้อมูล → ingestion → structured data → retrieval → routing → validation → prompt → presentation)
2. จากนั้นเลือก **การเปลี่ยนแปลงที่เล็กที่สุดที่แก้ bug class ได้ครบ**
3. **ห้ามเลือก workaround ที่เล็กกว่า ถ้ามันแค่ซ่อน root cause** — เล็กที่สุดไม่ได้แปลว่าถูกที่สุด
4. ถ้าจำเป็นต้องใช้ workaround จริง ต้องระบุเป็น **KNOWN DEVIATION** พร้อมเหตุผลและเงื่อนไขที่จะกลับไปแก้ที่ต้นเหตุ
5. การแก้ต้องไม่แตะ component ที่ไม่เกี่ยวข้อง ถ้าจำเป็นต้องแตะ → STOP (ข้อ 13)

ตัวอย่างที่ถูกต้อง: สัญญาณ "ไม่มีความสนใจ" มีอยู่แล้วในผลของขั้นจำแนกเจตนา (`interest = ""`) จึงแก้ที่ `_recommendation_intent` จุดเดียว แทนการแก้ prompt, การตั้งเกณฑ์คะแนน หรือการเพิ่มรายการคำ (`f2450a0`)

---

## 5. No Patch-Chase

### ห้ามทำ

```
เจอคำถามหนึ่งตอบผิด → เพิ่ม if สำหรับคำนั้น → test ผ่าน → จบ
```

- exact-string patch
- hardcode คำตอบเพื่อให้ test ผ่าน
- blacklist / whitelist ตามประโยคที่ fail
- prompt patch ที่ใส่ประโยคตัวอย่างที่ fail ลงไปตรงๆ
- refactor ระบบอื่นโดยไม่มีหลักฐานว่าเกี่ยวกับ root cause
- แก้ expectation ของ test เดิมเพื่อให้ผ่าน โดยไม่อธิบายว่าพฤติกรรมเดิมผิดอย่างไร

### General rule over example

fix ต้องแก้ **ประเภทของปัญหา** ไม่ใช่เฉพาะประโยคตัวอย่าง

```python
# BAD
if message == "เรียนไรดี":
    ask_clarification()

# GOOD
# recommendation intent + no meaningful preference -> clarification
if interest is NO_PREFERENCE:
    return clarification_reply()
```

หลักฐานในโปรเจกต์ว่ารายการคำไม่ได้ผล: `_recommendation_intent` (`backend/app/services/chat.py`) บันทึกว่ารายการคำเดิม ("เหมาะกับ" "แนะนำสาขา" "เรียนอะไรดี") ไม่จับข้อความเล่าความสนใจที่นักเรียนพิมพ์จริงเลยสักแบบจาก 5 แบบ · และ `eval/recommend_intent_check.py` มี test กันไม่ให้รายการคำกลับมา

### เมื่อมีการเปลี่ยน expectation ของ test เดิม

ทำได้เฉพาะเมื่อพฤติกรรมเดิมคือสิ่งที่ถูกแก้ และต้อง
- อธิบายใน docstring ของ test ว่าเดิมคาดหวังอะไร ใหม่คาดหวังอะไร และเพราะอะไร
- ระบุในรายงานว่ามี expectation เปลี่ยนกี่ข้อ ข้อไหน

---

## 6. Data Quality Rules

1. ปัญหาข้อมูลแก้ที่ **source data / ingestion / metadata / review pipeline** เท่านั้น
2. **ห้ามใช้ prompt, routing, หรือ hardcode เพื่อซ่อนข้อมูลเสีย** — การซ่อนทำให้ข้อมูลเสียยังอยู่ในระบบและย้อนกลับมาในเส้นทางอื่น
3. ข้อมูลที่ยังไม่ผ่านการตรวจ (unverified) **ห้ามแสดงเป็นข้อเท็จจริงที่ยืนยันแล้ว**
4. ถ้าแก้ข้อมูลไม่ได้ทันที ให้ **fail-safe** (ไม่แสดงค่านั้น หรือกลับไปใช้เส้นทางที่มีหลักฐาน) และบันทึกเป็น data issue
5. การแก้ข้อมูลบน production ต้องได้รับอนุมัติ ทำใน transaction เดียวที่มีการ backup และตรวจก่อน/หลัง
6. เส้นทาง structured data ใช้กระบวนการ review → publish ที่มีอยู่ (`pipeline/mko/review.py`, `pipeline/mko/publish.py`) ไม่แก้ค่าใน table ตรงๆ

---

## 7. Alias / Synonym Rules

alias ที่เป็น **ข้อเท็จจริง** ทำได้ เช่น "วิทคอม" → "วิทยาการคอมพิวเตอร์", "IT" → "เทคโนโลยีสารสนเทศ"

แต่ต้อง
- อยู่ใน **คลังกลางที่มีอยู่แล้ว** (`query_expansion.ALIASES` สำหรับชื่อเรียก/คำย่อ, `web_compat._ALIASES` สำหรับชื่อเดิมก่อนปรับปรุงหลักสูตร) ไม่สร้างคลังใหม่ซ้อน
- ใช้ซ้ำได้ทุกเส้นทาง ไม่ผูกกับ endpoint เดียว
- ทดสอบได้ มี test ครอบ
- มีหลักฐานว่าเป็น alias จริง (เอกสารของคณะ, ประกาศ, หรือการใช้งานที่พบซ้ำ) ไม่ใช่แค่ประโยคที่ fail หนึ่งครั้ง

**ห้าม** ฝัง alias เป็น patch เฉพาะอินพุตที่ fail · ห้ามใช้ alias เพื่อ "แปล" ความหมายที่ไม่ใช่ชื่อเรียกเดียวกันจริง

---

## 8. Fail-Safe Rules

เมื่อข้อมูลไม่พอ

| เลือก | มากกว่า |
|---|---|
| ถามเพิ่ม | เดา |
| บอกว่าไม่มีหลักฐาน | แต่งคำตอบ |
| บอกที่มาและระดับความมั่นใจ | แสดงข้อมูลที่ยังไม่ยืนยันเป็นข้อเท็จจริง |
| fail-safe + บันทึก data issue | ซ่อนข้อมูลเสียด้วย prompt |

ระบบควรแยกได้ว่าเมื่อไร
- **ตอบได้** (มีหลักฐานโดยตรง)
- **ต้องค้นเอกสาร** (retrieve)
- **ต้องถามเพิ่ม** (ข้อมูลของผู้ใช้ไม่พอ)
- **ไม่มีหลักฐาน** (ตอบตรงๆ ว่าไม่พบ)

**ระบบไม่จำเป็นต้องตอบทุกคำถามให้ได้** และ **ไม่ต้องรองรับทุกประโยคที่มนุษย์พิมพ์ได้**

---

## 9. Training Policy

1. **ห้ามเสนอ training / fine-tuning เป็นทางแก้เริ่มต้น** ของ bug
2. ก่อนตอบ `TRAINING REQUIRED: YES` ต้องมีหลักฐานว่าปัญหา **ไม่เหมาะ** จะแก้ด้วยวิธีต่อไปนี้ทุกข้อ
   - validation
   - routing
   - retrieval
   - Structured Data
   - data quality
   - deterministic logic
   - entity / alias mapping
3. การเปลี่ยน prompt หรือ model ถือเป็นการเปลี่ยนพฤติกรรมทั้งระบบ ต้องมีหลักฐานและชุดวัด ไม่ใช่ทางแก้เฉพาะกรณี

---

## 10. Testing / Regression

### Inventory ก่อนเสมอ
ก่อนสร้าง test ใหม่ ให้ดู `eval/*_check.py` ที่มีอยู่ก่อน **ใช้ harness เดิมให้มากที่สุด** (เช่น `FakeConnector`, `FakeDb`, การแทน `app.services.program_match` ใน `sys.modules`, `mock.patch.object(chat, ...)`) · ห้ามสร้าง test framework ใหม่

### Test matrix ขั้นต่ำเมื่อแก้ bug

| ชุด | ต้องพิสูจน์ |
|---|---|
| **A. original failing case** | กรณีที่รายงานมาผ่านแล้ว |
| **B. semantic equivalents** | ประโยคอื่นที่มีความหมายเดียวกันก็ผ่าน (พิสูจน์ general rule) |
| **C. valid opposite cases** | กรณีที่ **ไม่ควร** ถูกแก้ ยังทำงานเหมือนเดิม |
| **D. neighboring unrelated behavior** | เส้นทางข้างเคียงไม่ถูกกระทบ |
| **E. existing regression** | ชุดเดิมทั้งหมดผ่าน |

- test ต้องพิสูจน์ general rule ไม่ใช่แค่ทำให้กรณีเดิมผ่าน
- ควรยืนยันว่า test ใหม่ **fail กับโค้ดก่อนแก้** (เช่น จำลองพฤติกรรมเดิม) เพื่อพิสูจน์ว่า test จับ bug ได้จริง
- test แบบ offline ต้องไม่เรียกโมเดลจริง ไม่ยิง production และไม่เขียนฐานข้อมูล

### การรัน regression
- รันทุกชุดใน `eval/*_check.py` **ยกเว้น `behaviour_check`**
- รายงานผลเป็นตารางรายชุด พร้อมยอดรวม และบอกถ้ามี skip หรือตัวเลขไม่ตรงกับรอบก่อน
- ถ้าผลครั้งเดียวผิดปกติ (เช่น skip จากฐานข้อมูล local ช้า) ให้รันซ้ำและรายงานทั้งสองครั้ง ห้ามรายงานเฉพาะครั้งที่สวย

### Production validation
- ใช้จำนวน request **น้อยที่สุด** ที่พิสูจน์ acceptance criteria ได้ และต้องมีเพดานที่อนุมัติไว้
- ห้าม batch / stress / broad test · ห้ามรัน `behaviour_check` โดยไม่ได้รับอนุมัติแยก
- ถ้าพบปัญหาคนละเรื่องระหว่าง validate → บันทึกเป็น OBSERVATION ห้ามแก้ทันที

---

## 11. Freeze Policy

เมื่อครบทุกข้อต่อไปนี้ feature นั้นเป็น **FROZEN**
- root cause ถูกแก้
- test ที่จำเป็นผ่าน
- regression ผ่าน
- validation ที่กำหนดผ่าน

**หลัง freeze ห้าม**
- optimize
- refactor
- "ปรับให้ดีขึ้นอีกนิด"

**เปิดใหม่ได้เฉพาะเมื่อมีหลักฐานของ**
- bug class ใหม่ (ไม่ใช่ตัวอย่างใหม่ของ bug class เดิมที่รับเป็นข้อจำกัดไว้แล้ว)
- requirement ใหม่ที่ได้รับอนุมัติ
- demo blocker
- ปัญหาด้าน security หรือ data integrity

**Known limitations ไม่ใช่คำสั่งให้แก้** — เป็นบันทึกว่าตัดสินใจรับไว้แล้ว

### สถานะ freeze ปัจจุบัน

| Feature | Commit | สถานะ | Known limitations ที่รับไว้ |
|---|---|---|---|
| Chat Recommendation Clarification | `f2450a0` | **FROZEN** (`docs/CHAT_RECOMMENDATION_CLARIFICATION_DEPLOY.md`) | ตอบ "ไม่รู้" ต่อจากคำถามกลับยังไปทางจับคู่ · margin 0.04 และ limit 3 · gate พึ่งสัญญาณ `interest` ที่วัดมา 3 สำนวน · ข้อความถามกลับเป็นภาษาไทยอย่างเดียว |
| Chat Recommendation Stability (รายชื่อสาขาไม่หายตาม Gemini) | `fe6c57f` | Production PASS (`docs/CHAT_RECOMMENDATION_STABILITY_DEPLOYMENT_REPORT.md`) · สถานะ freeze อย่างเป็นทางการ: NOT FOUND ในรายงาน | ความครบถ้วนจำกัดด้วย margin/limit · `interest` ยังผ่านโมเดล |

ห้าม reopen feature ที่ FROZEN เพียงเพราะพบถ้อยคำหรือ UX ที่ไม่สมบูรณ์ ที่ไม่ใช่ bug class ใหม่

---

## 12. Pre-Implement Report Template

**ก่อนแก้พฤติกรรมเดิมทุกครั้ง** Agent ต้องส่งรายงานนี้ก่อน และรอการอนุมัติ

```text
CLASSIFICATION:          REAL BUG / UX GAP / DATA QUALITY / ACCEPTED LIMITATION / FEATURE REQUEST

EVIDENCE:
- Evidence:              <log / ไฟล์:บรรทัด / test / raw output / query แบบ read-only>
- Proves:                <หลักฐานนี้พิสูจน์อะไร>
- Uncertainty:           <อะไรที่ยังไม่แน่ใจ และต้องใช้อะไรยืนยัน>

ROOT CAUSE:              <กลไกที่ทำให้เกิด ไม่ใช่อาการ>

BUG CLASS:               <ประเภทของปัญหา ในรูปทั่วไป ไม่ใช่ประโยคตัวอย่าง>

GENERAL RULE:            <กฎที่ fix จะบังคับใช้กับทั้ง bug class>

OWNING LAYER:            <data / ingestion / structured / retrieval / routing / validation / prompt / presentation>

INVARIANTS:              <สิ่งที่ต้องไม่เปลี่ยน เช่น scoring, margin, limit, prompt, model, config, DB, feature ที่ freeze>

MINIMAL CHANGE:          <ไฟล์ + ฟังก์ชัน + สิ่งที่จะเปลี่ยน>

TEST MATRIX:             <A original / B semantic equivalents / C valid opposite / D neighboring / E regression>

TRAINING REQUIRED:       YES / NO   (YES ต้องมีหลักฐานตามข้อ 9)

DATA CHANGE REQUIRED:    YES / NO

RISK:                    <ผลกระทบที่เป็นไปได้ และกรณีแย่ที่สุด>

KNOWN DEVIATION:         <workaround ที่ยอมรับ และเหตุผล / NONE>

REVERT PLAN:             <วิธีย้อนกลับ: commit / image tag / ขั้นตอน>

STOP CONDITION:          <เงื่อนไขที่จะหยุดทันทีระหว่างทำ>

READY TO IMPLEMENT:      YES / NO
```

**ถ้า `READY TO IMPLEMENT: NO` → STOP ห้ามแก้เองต่อ**

---

## 13. Stop Conditions

**STOP และรายงานทันที** เมื่อ
- หลักฐานไม่พอจะระบุ root cause
- ต้องแตะ component ที่ไม่เกี่ยวข้องกับ root cause
- ต้องเปลี่ยน architecture
- ต้องเปลี่ยน scoring โดยไม่มี evaluation รองรับ
- ต้องเปลี่ยน prompt หรือ model โดยไม่มีหลักฐาน
- ต้อง migrate หรือเขียนฐานข้อมูล production โดยไม่ได้รับอนุมัติ
- พบ bug ใหม่ **คนละประเภท** ระหว่างทำงาน (บันทึกเป็น OBSERVATION แล้วแยกงาน)
- ต้องแก้ feature ที่ FROZEN โดยไม่มีหลักฐานใหม่
- production baseline ไม่ตรงกับที่รายงานไว้ก่อน deploy
- health check หลัง deploy ผิดปกติ → **ROLLBACK แล้ว STOP** · ห้าม patch production สด

**ห้ามรวมหลาย bug เป็น fix เดียว** — หนึ่ง bug class ต่อหนึ่งงาน ต่อหนึ่ง commit

---

## 14. Meta-Rule

1. **Engineering Stability Rules ฉบับนี้ถูก FREEZE หลังได้รับอนุมัติ**
2. การแก้กฎในอนาคตต้องมี
   - **evidence** — กรณีจริงที่กฎปัจจุบันทำให้ผลเสีย
   - **reason** — ทำไมกฎเดิมไม่พอ
   - **impact** — กระทบงานใดบ้าง
   - **minimal change** — แก้ข้อเดียวที่จำเป็น ไม่เขียนใหม่ทั้งฉบับ
3. **ห้ามผ่อนกฎเพียงเพราะอยากให้ task ผ่านเร็วขึ้น**
4. ถ้าคำสั่งในงานใดขัดกับกฎนี้ ให้รายงานความขัดแย้งก่อนลงมือ ห้ามเลือกเองเงียบๆ
5. ข้อเท็จจริงใน "Project anchors" (ข้อ 1) และตาราง "สถานะ freeze ปัจจุบัน" (ข้อ 11) เป็นข้อมูลอ้างอิง ปรับให้ตรงกับความจริงได้ โดยไม่ถือเป็นการแก้กฎ

---

RULE STATUS: CANONICAL
APPLICATION CODE CHANGED: NO
TESTS CHANGED: NO
PRODUCTION TOUCHED: NO
NEW INFRASTRUCTURE ADDED: NO
