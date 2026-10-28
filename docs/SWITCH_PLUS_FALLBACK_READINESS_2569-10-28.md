# ชุดพร้อมอนุมัติ: สวิตช์เลือกโมเดล + patch ตัวสำรองในเครื่อง

28 ต.ค. 2569 · เป้าหมาย: พรีวันเสาร์ที่ 31 ต.ค. 2569
**ยังไม่ deploy · ยังไม่เปลี่ยนค่าใดของ production · ยังไม่ merge เข้า `mko-phase2`**

ข้อสรุปสั้น: **สวิตช์พร้อมปล่อยพร้อมคำเตือน โดยคง Gemini เป็นตัวที่ใช้งานจริง ·
Ollama ยังไม่พร้อมรับคำถามที่ต้องอ้างอิงเอกสาร** และรอบนี้ไม่ได้แก้อะไรเพื่อให้ดูผ่าน

ทดสอบบนเซิร์ฟเวอร์จริงแล้ว (คอนเทนเนอร์แยก ฐาน `course_advisor_test` ค่าเท่า production):
เลือก Gemini แล้วคำตอบมาจาก Gemini จริง **ผ่าน 9/9** · จำลอง Gemini ล่มแล้วตัวสำรอง
ในเครื่องได้ทำงานจริง **ผ่าน 5/5** (ดูหัวข้อ 8) · production ไม่ถูกแตะเลย

---

## 1. patch อยู่ที่ไหน และรวมกันอย่างไร

| งาน | เดิมอยู่ที่ | สภาพ |
|---|---|---|
| สวิตช์เลือกโมเดล | worktree `D:/workspace/course-advisor-system-mko2` (branch `mko-phase2`) | **ยังไม่ commit** — 6 ไฟล์แก้ + 4 path ใหม่ |
| ตัวสำรองในเครื่องมีเวลาใช้จริง | branch งานของรอบนี้ commit `605eb20` | commit แล้ว ฐานเป็น `b78b3f8` |

`b78b3f8` เป็นบรรพบุรุษของ `mko-phase2` (`4d7a5a5`) จึง fast-forward ฐานของ patch ขึ้นมาที่
`4d7a5a5` ก่อน แล้ว **รวมด้วย merge ไม่ใช่คัดทับ** เพราะทั้งสองงานแก้
`backend/app/services/llm_client.py` ไฟล์เดียวกัน

```
4d7a5a5  (= mko-phase2 = production)
 ├── 605eb20  fix: ตัวสำรองในเครื่องต้องมีเวลาใช้จริง        (ของรอบก่อน)
 ├── 8c76861  feat: สวิตช์เลือกโมเดล (ยกจาก worktree mko2 ตามสภาพ ไม่แก้เนื้อหา)
 └── bbc45eb  merge: รวมสองงาน   ← ชุดที่ขออนุมัติ
```

ชนกันจุดเดียวคือบล็อก `from llm.connector import ...` แก้โดยรวมรายการ import ของทั้งสองฝั่ง
ตรวจแล้วว่าโค้ดของทั้งสอง patch อยู่ครบในไฟล์ที่รวมเสร็จ (`reserve_budget` 2 จุด ·
`apply_budget` 3 จุด · `_LocalPrimary` / `_build` / `probe` ของสวิตช์ครบ)

**ของในworktree `mko2` ไม่ถูกแตะเลย** — อ่านอย่างเดียว ไฟล์ที่ยกมาคัดลอกออกมา

## 2. diff เทียบ production (`4d7a5a5`)

```
backend/app/api/routes/site_admin.py            124 +-     สวิตช์
backend/app/main.py                              14 +-     สวิตช์ (งานอุ่นโมเดล)
backend/app/schemas/chat.py                      10 +      สวิตช์ (answer_model)
backend/app/services/ai_settings.py             201 +      สวิตช์ (ไฟล์ใหม่)
backend/app/services/answer_cache.py             14 +-     สวิตช์ (ผูกแคชกับโมเดล)
backend/app/services/chat.py                     32 +-     สวิตช์ (ตรึง connector ต่อคำขอ)
backend/app/services/llm_client.py              381 +-     สวิตช์ + patch ตัวสำรอง
llm/connector.py                                 34 +      patch ตัวสำรอง (reserve_budget)
backend/tests/test_model_switch.py              465 +      สวิตช์ (ชุดใหม่)
backend/tests/test_local_fallback_gets_time.py  257 +      patch ตัวสำรอง (ชุดใหม่)
db/migrations/010_ai_settings_provider.sql       39 +      สวิตช์ (DDL ล้วน)
docs/MODEL_SWITCH_2569-10-28.md                 670 +      รายงานสวิตช์
docs/LOCAL_FALLBACK_FIX_2569-10-28.md           134 +      รายงาน patch ตัวสำรอง
                                     13 ไฟล์ · +2,324 / -51
```

**ไม่แตะ**: `llm/prompts.py` · `_grounding_verdict` / `_can_answer_from` · `services/vector_search.py` ·
`services/course_scope.py` · ฝั่ง embedding ทั้งหมด (ตรวจด้วย `git diff` แล้วว่าไม่มีบรรทัดใดเปลี่ยน)

---

## 3. ยืนยันสี่ข้อที่โจทย์กำหนด

ทดสอบผ่าน **API จริงด้วย HTTP** (uvicorn จากโค้ดที่รวมแล้ว) บนฐาน `course_advisor_test`
(สำเนาของฐาน local ที่ `course_chunks` = 7,301 แถว) · สคริปต์: `eval/model_switch_api_check.py`
คำถามที่ใช้เป็นคำถามที่ **ต้องเรียกโมเดล** และล้าง `chat_answer_cache` ก่อนทุกคำขอ

| ข้อที่ต้องยืนยัน | ผล | หลักฐาน |
|---|---|---|
| เลือก Gemini/Ollama แล้วเรียกเจ้าที่เลือกจริง | **ผ่าน** (Ollama) · **ยืนยันได้แค่การตัดสิน** (Gemini) | เลือก ollama → `answer_model = ollama:qwen2.5:3b` และตัวนับขึ้น `local_primary_*` ไม่ขึ้น `gemini_ok` · เครื่องนี้ไม่มี `GEMINI_API_KEY` จึงตรวจฝั่ง Gemini ได้แค่ว่า "เลือกไว้แต่ไม่มีคีย์ → ไม่ยอมใช้ บอกเหตุผล และไม่มีคำขอไป Gemini เลย" |
| เปลี่ยนกลับได้โดยไม่ restart | **ผ่าน** | `PUT /site-admin/ai-settings` แล้ว `GET` คืน `effective` ใหม่ทันทีในกระบวนการเดิม · log: `ใช้โมเดลเขียนคำตอบ: ollama / qwen2.5:0.5b (ที่มา: db)` ของคำขอถัดไป โดยไม่ restart |
| คำขอที่กำลังตอบไม่ถูกสลับกลางทาง | **ผ่าน** | เริ่มคำขอตอนเลือก `qwen2.5:3b` · สลับเป็น `qwen2.5:0.5b` หลังจากนั้น 8 วินาที · คำขอนั้นคืน `answer_model = ollama:qwen2.5:3b` (ใช้เวลา 5.8s) |
| embedding และกฎตรวจหลักฐานเดิมไม่เปลี่ยน | **ผ่าน** | ทุกการตั้งค่า `GET` คืน `embedding = {"model": "bge-m3", "changeable": false}` · `llm/prompts.py` และด่าน `_grounding_verdict` ไม่มี diff เทียบ production |

### ผล API แบบเต็ม

| ชุด | การตั้งค่า | ผล | ไฟล์หลักฐาน |
|---|---|---|---|
| โหมด prod | `RAG_TIME_BUDGET_S=30` · `CHAT_TOP_K=25` | **ผ่าน 21 / 21** (รันสองรอบ ผ่านทั้งสองรอบ) | `evidence/api-checks-merged-prod.txt` |
| โหมดเพดานกว้าง | `RAG_TIME_BUDGET_S=120` · `CHAT_TOP_K=25` | **ผ่าน 28 / 29** | `evidence/api-checks-merged-k25-budget120.txt` |
| เพดานกว้าง พรอมต์เล็ก | `RAG_TIME_BUDGET_S=120` · `CHAT_TOP_K=4` | ผ่าน 25 / 29 — ที่ตกคือด่านตรวจหลักฐานของโมเดลในเครื่องตอบ "ตอบไม่ได้" ทุกคำถาม | `evidence/api-checks-merged-k4-budget120.txt` |

ข้อที่ตกข้อเดียว: *"คำขอถัดไปได้รุ่นใหม่โดยไม่ restart"* — คำขอนั้นได้รุ่นใหม่จริง
(log ยืนยัน) แต่ **ตายที่เพดานเวลา** เพราะด่านตรวจหลักฐานของ `qwen2.5:0.5b` ใช้ไป
`decide=119,818ms` จาก 120 วินาที · ชุดทดสอบอ่าน `answer_model` ซึ่งเป็น `null` เมื่อคำขอล้ม
จึงตก — **ไม่ใช่ความล้มเหลวของสวิตช์ แต่เป็นข้อจำกัดของตัววัดที่เขียนไว้** (บันทึกไว้ในสคริปต์แล้ว)

---

## 4. Ollama ยังไม่พร้อม — และไม่ได้แก้อะไรเพื่อให้ดูผ่าน

| สภาพแวดล้อม | ผล |
|---|---|
| เซิร์ฟเวอร์ production (ไม่มีการ์ดจอ · วัดในรอบสวิตช์ · `MODEL_SWITCH` ข้อ 6) | คำถามที่ต้องอ้างอิงเอกสาร **สำเร็จ 0 จาก 3** ที่เพดาน 30 วินาที · ที่เพดาน 300 วินาที ใช้ 233–249 วินาทีแล้วได้ `not_found` |
| เครื่องทดสอบรอบนี้ (**มีการ์ดจอ** RTX 5050) `CHAT_TOP_K=25` เพดาน 30 วินาที | รันสองรอบด้วยคำถามชุดเดียวกัน ได้ **1 จาก 3** และ **0 จาก 3** — ด่านตรวจหลักฐานตอบ `not_found` ทั้งที่หลักฐานมี และ **ตัดสินไม่เหมือนกันสองรอบ** |
| เครื่องเดียวกัน `CHAT_TOP_K=25` เพดาน 120 วินาที | คำถามเดียวกันเขียนจบใน 14.2 และ 5.8 วินาที · อีกคำถามกินเพดานจนหมด |
| เครื่องเดียวกัน `CHAT_TOP_K=8` / `=4` | ด่านตรวจหลักฐานตอบ "ตอบไม่ได้" ทุกครั้ง → ผู้ใช้ได้ข้อความ "ไม่พบข้อมูล" |
| `qwen2.5:0.5b` ที่ `CHAT_TOP_K=25` | ด่านตรวจหลักฐานใช้ 119.8 วินาที ชนเพดาน |

**เครื่องทดสอบรอบนี้มีการ์ดจอ เซิร์ฟเวอร์ไม่มี** ตัวเลขเวลาของรอบนี้จึง *ดีกว่า* ของจริง
ข้อสรุป "ไม่พร้อม" อ้างจากตัวเลขของเซิร์ฟเวอร์เป็นหลัก ส่วนรอบนี้เพิ่มหลักฐานอีกชั้นว่า
**ปัญหาไม่ใช่แค่ความเร็ว** — ด่านตรวจหลักฐานของโมเดลในเครื่อง **ตัดสินผิด** ที่ทุกค่า
`CHAT_TOP_K` ที่ลอง บนเครื่องที่เร็วกว่าเซิร์ฟเวอร์หลายเท่า

สามทางที่จะทำให้ดูผ่าน และเหตุผลที่ไม่ทำ (เพิ่มเติมจาก `MODEL_SWITCH` ข้อ 6.7):

| ทาง | ไม่ทำเพราะ |
|---|---|
| ขยาย `RAG_TIME_BUDGET_S` | เพดานมีที่มาของตัวเอง (คำขอหนึ่งเคยใช้ 408 วินาที) · และที่ 120–300 วินาทีก็ยังไม่พอ |
| ใส่ `num_predict` ให้ด่านตรวจหลักฐาน | **วัดแล้วไม่ช่วย** — เวลา 88–91% หมดไปกับการ *อ่าน* พรอมต์ ไม่ใช่การเขียน ผลลัพธ์จริงยาว 46–174 โทเคน ไม่เคยชนเพดาน (`done_reason='stop'` ทุกรอบ) · ตัวเลขทั้งหมดใน `LOCAL_FALLBACK_FIX` ข้อ 2 |
| ลด `CHAT_TOP_K` | รอบนี้วัดที่ 8 และ 4 แล้ว **แย่กว่า** ไม่ใช่ดีกว่า — ด่านตรวจตอบ "ไม่ได้" ทุกครั้ง |

**ข้อเสนอ: ปล่อยสวิตช์พร้อมคำเตือน** — หลัง deploy ค่าที่ใช้จริงยังเป็น Gemini จาก env
(`provider` เป็น NULL) การเลือก Ollama เป็นการกระทำของผู้ดูแลที่หน้าเว็บ ซึ่งมีคำเตือนและ
ปุ่มตรวจสองขั้นที่ไม่ขึ้นเขียวถ้าขั้นที่วัดงานเท่าของจริงไม่ผ่านอยู่แล้ว (`MODEL_SWITCH` ข้อ 6.6)

---

## 5. ผลทดสอบของโค้ดที่รวมแล้ว

### 5.1 ชุดที่ผ่านทั้งหมด — 167 จุด

| ไฟล์ | จุดตรวจ |
|---|---|
| `test_model_switch.py` | 51 / 51 |
| `test_local_fallback_gets_time.py` | 12 / 12 |
| `test_request_budget.py` | 41 / 41 |
| `test_llm_usage_counter.py` | 43 / 43 |
| `test_gemini_overload_fallback.py` | 20 / 20 |

### 5.2 สามชุดที่ตกบางจุด — **ตกเท่ากับ production ทุกจุด**

รันบนฐาน `course_advisor_test` ของเครื่องนี้ ซึ่ง **ไม่มีข้อมูล `mko` ที่เผยแพร่แล้ว**
(migration 009 ลงไม่ได้เพราะไม่มี `mko.published_subjects`) คำถามที่ควรตอบจากฐานหลักสูตร
จึงตกไปใช้เส้นทาง RAG แล้วใช้โมเดลในเครื่องตัดสิน ซึ่งตอบ "ไม่พบข้อมูล"

เทียบแบบ A/B กับ worktree ที่ checkout `4d7a5a5` (production) บนฐานและสภาพแวดล้อมเดียวกัน:

| ไฟล์ | โค้ดที่รวมแล้ว | production (`4d7a5a5`) |
|---|---|---|
| `test_sse_format.py` | ตก 3 / 26 | **ตก 3 / 26 — ชื่อข้อเดียวกันทุกข้อ** |
| `test_chatweb_stream_budget.py` | ตก 3 / 20 | **ตก 3 / 20 — ชื่อข้อเดียวกันทุกข้อ** |
| `test_model_outage_n1.py` | ตก 6 / 16 | **ตก 6 / 16** |

→ **ไม่ใช่ regression ของสองงานนี้** เป็นข้อจำกัดของฐานทดสอบในเครื่อง
(รอบสวิตช์รันสามชุดนี้ในคอนเทนเนอร์บนฐานที่มีข้อมูลครบ แล้วผ่าน 26/26 · 20/20 · 16/16)

การรันครั้งแรกของ `test_chatweb_stream_budget` ได้ตก 5 จุด และ `test_sse_format` ได้
ข้อความต่างออกไป — รันซ้ำบนเครื่องที่ว่างแล้วได้ตกเท่ากับ production ทั้งสองชุด
**ความต่างนั้นคือความผันผวนของคำตอบจากโมเดลในเครื่อง ไม่ใช่ผลของโค้ด**

### 5.3 `eval/multi_program_scope_check.py` — ตก 1 / 12 (มีอยู่ก่อนแล้ว)

ข้อที่ตกคือ `test_แต่ละหลักสูตรรวมทุกฉบับ_และเลือกปีได้` ซึ่งคาดว่าหลักสูตรชื่อเดียวกันต่างปี
จะอยู่ใน scope เดียวกัน · เป็นผลของ commit production `4d7a5a5` เอง
("แยกหลักสูตรที่ชื่อสาขาเหมือนกันแต่คนละระดับปริญญา") ที่แก้ `services/course_scope.py`
ซึ่ง **ทั้งสอง patch ไม่ได้แตะไฟล์นั้นเลย** — ชุดทดสอบนี้ล้าสมัยกับกฎใหม่ เป็นงานแยก

---

## 6. ชุดสำหรับ deploy — สิ่งที่ต้องเปลี่ยนเพราะมีสอง patch

ชุดเดิมที่ `docs/raw/model-switch-2569-10-28/` **มีแต่งานสวิตช์** ถ้า deploy ตามนั้น
patch ตัวสำรองในเครื่องจะไม่ขึ้นไปด้วย · รอบนี้จึงปรับชุดให้ครอบทั้งสองงาน:

| ไฟล์ในชุด | เปลี่ยนอะไร |
|---|---|
| `backend-release/files/llm_client.py` | เปลี่ยนเป็นฉบับที่รวม patch แล้ว |
| `backend-release/files/connector.py` | **ใหม่** → ซ้อนที่ `/app/llm/connector.py` |
| `backend-release/files/test_local_fallback_gets_time.py` | **ใหม่** → ชุดทดสอบของ patch |
| `backend-release/Dockerfile` | เพิ่ม `COPY` สองบรรทัด (รวมเป็น 11 ไฟล์ซ้อน) |
| `backend-release/SHA256SUMS` | สร้างใหม่ ครอบ 11 ไฟล์ · `sha256sum -c` ผ่านทั้ง 11 |
| `deploy_backend.sh` | `check_in_image` / `check_in_container` ของสองไฟล์ใหม่ · เพิ่ม `test_local_fallback_gets_time` เข้าลูปชุดทดสอบในอิมเมจ (รวม 8 ไฟล์) |
| `.gitattributes` | `docs/raw/** text eol=lf` — ดูย่อหน้าถัดไป |

**กับดักที่เจอจริงรอบนี้**: ชุดถูก commit แล้ว checkout บน Windows ซึ่ง `core.autocrlf=true`
ไฟล์ทั้งหมดกลายเป็น CRLF แล้วด่าน `sha256sum -c SHA256SUMS` ของ `deploy_backend.sh`
**ล้มทั้ง 9 ไฟล์** ด้วยข้อความ `No such file or directory` (ตัว `SHA256SUMS` เองก็เป็น CRLF
จนชื่อไฟล์มี `\r` ติดมา) · แก้ด้วยกฎใน `.gitattributes` และทำให้ไฟล์ในชุดกลับเป็น LF แล้ว

**ยังต้องทำบนเซิร์ฟเวอร์**: อิมเมจฐาน `course-advisor-system-backend:followup-2569-10-28`
ไม่มีในเครื่องนี้ จึง **build อิมเมจซ้อนที่นี่ไม่ได้** ต้อง build บนเซิร์ฟเวอร์ตามสคริปต์
(ยังใช้ชื่อ tag เดิม `switch-2569-10-28` โดยเจตนา เพราะ `rollback_db.sh` จับคู่ชื่อนั้นไว้ ·
ตัวที่แยกว่าโค้ดในอิมเมจถูกหรือไม่คือด่าน hash ของ 11 ไฟล์ ไม่ใช่ชื่อ tag)

### แผน deploy (ตาม `MODEL_SWITCH` ข้อ 7 ไม่เปลี่ยนลำดับ)

| ขั้น | สคริปต์ | แตะอะไร | ย้อนด้วย |
|---|---|---|---|
| 1 | `./deploy_db.sh` | `web.ai_settings` เพิ่มคอลัมน์ `provider` (DDL ล้วน) | `./rollback_db.sh` |
| 2 | `./deploy_backend.sh` | อิมเมจ backend เท่านั้น (`--no-deps`) · ตรวจ hash 11 ไฟล์ · รันชุดทดสอบ 8 ไฟล์ในอิมเมจใหม่ก่อนสลับ | `./rollback_backend.sh` |
| 3 | `./deploy_web.sh` | ไฟล์ static ของหน้าเว็บ | `./rollback_web.sh --run <โฟลเดอร์ผล>` |

**rollback ย้อน backend พอ ไม่ต้องย้อนฐาน** คอลัมน์ `provider` เป็นคอลัมน์ที่โค้ดเก่าไม่รู้จัก
อยู่เฉย ๆ ได้ · ย้อนแล้วพฤติกรรมกลับเป็นของ production เดิมทั้งสองงาน (ตัวสำรองกลับไป
ถูกเพดานเวลาปฏิเสธเหมือนเดิม ซึ่งเป็นสภาพก่อนรอบนี้ ไม่ใช่สภาพที่แย่ลง)

**ผลข้างเคียงที่คาดไว้** — แคชคำตอบทั้งหมดกลายเป็นของรุ่นเก่าครั้งเดียวตอน deploy
เพราะตัวระบุรุ่นของแคชรวมชื่อโมเดลเข้าไปด้วย คำถามชุดแรกหลัง deploy จะช้ากว่าปกติ

---

## 7. สิ่งที่ยังยืนยันไม่ได้

1. ~~ไม่ได้ทดสอบกับ Gemini จริง~~ **ยืนยันบนเซิร์ฟเวอร์แล้ว** (หัวข้อ 8 · ผ่าน 9/9)
2. ~~patch ตัวสำรองยังไม่ได้ทดสอบ end-to-end~~ **ยืนยันบนเซิร์ฟเวอร์แล้วด้วยการจำลอง
   Gemini ติดต่อไม่ได้** (หัวข้อ 8 · ผ่าน 5/5 · `fallback_local_ok` ขยับจริง)
   ส่วนที่ยังไม่ได้ทำคือจำลองด้วย **429 ของจริง** — การจำลองที่ใช้คือปลายทางติดต่อไม่ได้
   ซึ่งกินเพดานเวลาแบบเดียวกัน แต่ไม่ได้เดินเส้นทาง "ไล่โมเดลสำรองของ Gemini แล้วนอนรอ
   ให้พ้นช่วงพัก" ครบทุกขั้นเหมือนโควตาหมดจริง
3. **ยังไม่ได้ทดสอบบนฐานและคอนเทนเนอร์ของ production** ผลบนเซิร์ฟเวอร์ทั้งหมดมาจาก
   คอนเทนเนอร์แยกที่ชี้ฐาน `course_advisor_test` · ไม่ได้ยิงคำถามใส่เว็บจริง
   และไม่ได้ restart หรือเปลี่ยนอิมเมจของ production
4. **ฐานทดสอบในเครื่องไม่ครบ** ไม่มีข้อมูล `mko` ที่เผยแพร่แล้ว (migration 009 ลงไม่ได้)
   และ migration 006 ลงได้แต่เฉพาะ DDL (ไม่มี role `advisor_web` จึงไม่ได้ให้สิทธิ์)
   สามชุดใน 5.2 จึงตกเท่า ๆ กับ production ไม่ใช่ผ่าน
5. **ไม่ได้วัดคุณภาพคำตัดสินของด่านตรวจหลักฐานซ้ำหลายรอบ** รอบนี้ไม่ได้แก้ด่านนั้น
   ตัวเลข `not_found` ของโมเดลในเครื่องมาจากการรันครั้งละหนึ่งรอบ จึงใช้เป็นสัญญาณว่า
   "ไม่พร้อม" ได้ แต่ยังไม่ใช่การวัดคุณภาพที่สรุปเป็นอัตราได้
6. **ค่า `RAG_FALLBACK_RESERVE_S` = 10 วินาที วัดบนเซิร์ฟเวอร์แล้วหนึ่งสถานการณ์**
   ทำให้ 1–2 ขั้นจาก 3 ขั้นทำจบได้ (หัวข้อ 8) ขั้นที่ยังไม่จบคือด่านตรวจหลักฐานที่
   พรอมต์ใหญ่ ซึ่งเป็นผลที่ตั้งใจ — ให้ตัวสำรองได้ลองจริงและทำให้ตัวนับเลิกโกหก
   ไม่ใช่ทำให้ด่านตรวจหลักฐานสำเร็จบนโมเดลในเครื่อง · **ยังไม่ได้หาค่าที่เหมาะที่สุด**
   (วัดคำถามเดียวสองรอบ ไม่ใช่หลายรูปแบบคำถาม)

## 8. สองข้อที่เหลือ — **รันบนเซิร์ฟเวอร์แล้ว ผ่านทั้งคู่**

รันเมื่อ 28 ต.ค. 2569 บนเซิร์ฟเวอร์ `stpnru` (`ubuntu@161.118.237.37`)
**ในคอนเทนเนอร์แยกสองตัว ฐาน `course_advisor_test` ค่าเท่า production**
(`CHAT_TOP_K=25` · ไม่ตั้ง `RAG_TIME_BUDGET_S` จึงเป็นค่าตั้งต้น 30 วินาที ·
backend ของ production ไม่ได้จำกัด cpu/memory ไว้เลย — ตรวจจาก `docker inspect`
ได้ `NanoCpus=0 Memory=0` — คอนเทนเนอร์ตรวจจึงไม่จำกัดเหมือนกัน)

| ของที่ส่งไปตรวจ | ที่มา | ด่านตรวจ |
|---|---|---|
| ชุดซ้อนอิมเมจ 11 ไฟล์ | **release `213d65e`** (ไม่เปลี่ยนเลยใน `92b7346` และ commit ถัดมา — `git diff 213d65e..HEAD -- docs/raw/` ว่าง) | `sha256sum -c SHA256SUMS` **ผ่าน 11/11 บนเซิร์ฟเวอร์** · เทียบ hash ของไฟล์ในอิมเมจที่ build แล้วอีกชั้น **ตรงทั้ง 11 ไฟล์** |
| สคริปต์ตรวจ `eval/model_switch_api_check.py` | **รุ่นหลังสุดของ branch นี้** (แก้การรอรอบเขียนตัวนับและคำถามของโหมด outage ระหว่างรันจริง) — ยืนยันตัวไฟล์ด้วย sha256 ข้างขวา ไม่ใช่ด้วยเลข commit | `sha256 = 5f3ba3fd782aa8b409e8605ab2bdfb5998a8fd2664089e624f92671842d47f2a` ตรงกันทั้งบนเครื่องพัฒนาและในคอนเทนเนอร์ |

อิมเมจที่ build ใช้ **tag ของตัวเอง** `switch-check-2569-10-28` ไม่ใช่ tag ของ release
และลบทิ้งหลังตรวจเสร็จ · **production ไม่ถูกแตะ**: backend ยังเป็น
`followup-2569-10-28` และ `StartedAt` ยังเป็น 27 ต.ค. 21:32 UTC (ไม่ได้ restart)

### ผลที่ได้

**`--mode gemini` — ผ่าน 9 / 9** (`evidence/api-checks-server-gemini.txt`)

```
· HTTP 200 · 2.5s · status=answered · answer_model=gemini:gemini-3.5-flash-lite
[ผ่าน] ที่ใช้จริงเป็น gemini — source=db · honoured=True
[ผ่าน] คำตอบมาจาก gemini · [ผ่าน] ตัวนับฝั่ง gemini ขยับ — gemini_ok 85 -> 87
[ผ่าน] ไม่ได้ไปเรียกโมเดลในเครื่องเป็นตัวหลัก · [ผ่าน] ไม่ได้ใช้ตัวสำรองเลย
[ผ่าน] embedding ยังเป็น bge-m3
```

→ **เลือก Gemini แล้วคำตอบมาจาก Gemini จริง** ที่ค่าของ production ใช้เวลา 2.5 วินาที
(`gemini_ok` ขยับ 2 ครั้งต่อหนึ่งคำขอ: ด่านตรวจหลักฐานกับขั้นเขียนคำตอบ)

**`--mode outage` — ผ่าน 5 / 5** (`evidence/api-checks-server-outage.txt`)

จำลองโดยคอนเทนเนอร์ตัวที่สองตั้ง `--add-host generativelanguage.googleapis.com:198.51.100.1`
(ช่วงเอกสาร TEST-NET-2 ที่ไม่มีเส้นทางไปถึง) **ไม่แก้โค้ดเพื่อการทดสอบ**

```
· HTTP 503 · 30.1s                        (ชนเพดานเวลาของ production พอดี)
[ผ่าน] ปลายทางของ Gemini ถูกจำลองให้ติดต่อไม่ได้
[ผ่าน] ไม่มีคำตอบใดมาจาก Gemini — gemini_ok +0
[ผ่าน] ตกมาที่ตัวสำรองในเครื่องจริง — fallback_local_attempt +3
[ผ่าน] ตัวสำรองได้ทำงานจบอย่างน้อยหนึ่งขั้น (ผลของ patch)
       รอบแรก  ok +1 · failed +2 · declined +1
       รอบสอง  ok +2 · failed +1 · declined +1
```

→ **นี่คือหลักฐานตรงของ patch** ก่อนแก้ ตัวนับของ production เป็น
`attempt = 10 · failed = 10 · ok = 0` คือไม่มีไบต์ใดถึง Ollama เลย
หลังแก้ บนเครื่องเดียวกันที่ไม่มีการ์ดจอและเพดานเวลาเท่าเดิม **มีขั้นที่ทำจบจริง 1–2 ขั้น
จาก 3 ขั้น** ส่วนที่ยัง `failed` คือด่านตรวจหลักฐานที่พรอมต์ใหญ่เกินเวลาที่กันไว้
และ `declined +1` คือขั้นเขียนคำตอบที่ปฏิเสธโมเดลสำรองโดยเจตนา — ผู้ใช้จึงยังได้ 503
ตามที่ออกแบบไว้ ไม่ใช่คำตอบที่ตรวจกับเอกสารไม่ได้

**ความผันผวนระหว่างสองรอบ (ok 1 เทียบกับ 2)** มาจากความเร็วของโมเดลในเครื่องบน CPU
ไม่ใช่จากโค้ด · ข้อที่ยืนยันคือ `ok > 0` ซึ่งเป็นจริงทั้งสองรอบ และเป็นสิ่งที่
**เป็นไปไม่ได้ก่อนมี patch** เพราะตัวสำรองถูกปฏิเสธก่อนยิงคำขอแรกทุกครั้ง

### กับดักของตัววัดที่เจอระหว่างรัน (แก้แล้ว)

1. **ตัวนับยังไม่ถูกเขียนลงฐาน** — `llm_usage` บวกในหน่วยความจำแล้วเขียนทุก 30 วินาที
   อ่านฐานทันทีหลังคำขอจบจึงได้ `gemini_ok 83 -> 83` ทั้งที่คำตอบมาจาก Gemini
2. **อ่านกลางรอบการเขียน** — เห็น `attempt +1` โดย `ok` และ `failed` เป็น `+0` ทั้งคู่
   ซึ่งเป็นไปไม่ได้ในโค้ด (`_call_fallback` บันทึกอย่างใดอย่างหนึ่งเสมอ) · แก้โดย
   **รอให้ครบรอบเขียนเสมอ ไม่คืนค่าทันทีที่เห็นตัวเลขขยับ**
3. **คำถามที่เอ่ยชื่อหลักสูตรข้ามตัวคัดกรองขอบเขต** ทำให้โมเดลถูกเรียกครั้งแรกที่ด่าน
   ตรวจหลักฐานซึ่งพรอมต์ใหญ่ ตัวสำรองจึงไม่มีขั้นใดทำจบได้เลยและแยกไม่ออกว่า
   "ถูกปฏิเสธ" หรือ "ได้เวลาแต่ช้าเกิน" · โหมด outage จึงใช้คำถามที่ไม่เอ่ยชื่อหลักสูตร

สิทธิ์ฐานข้อมูล: ผู้ใช้ของแอปไม่มีสิทธิ์ `truncate`/`delete` บน `chat_answer_cache`
และ `web.ai_settings` จึงต้องส่ง `SWITCH_CHECK_DSN` ของผู้ใช้ `postgres` **ของฐานทดสอบ**
ให้สคริปต์ (ด่านในสคริปต์ปฏิเสธ DSN ที่ชื่อฐานไม่ลงท้าย `_test`)

### เก็บของหลังตรวจ

ลบคอนเทนเนอร์สองตัว ลบอิมเมจ `switch-check-2569-10-28` ลบไฟล์ชุดบนเซิร์ฟเวอร์
คืนแถว `web.ai_settings` ของฐานทดสอบเป็น `provider=NULL · model=gemini-3.1-flash-lite`
(ค่าเดิมก่อนตรวจ) และลบผู้ใช้ `switch-check@test.local` ที่สร้างไว้ชั่วคราว

### ขั้นตอนที่ใช้ (รันซ้ำได้)

ชุดที่ใช้คือ release `213d65e` + สคริปต์ตรวจรุ่นหลังสุดของ branch นี้ · `eval/model_switch_api_check.py`
มีด่านกันไว้สองชั้น: ปฏิเสธถ้าชื่อฐาน (หรือชื่อฐานใน `SWITCH_CHECK_DSN`) ไม่ลงท้าย `_test`
และปฏิเสธถ้า `--api` ไม่ใช่ localhost

**ค่าคีย์ไม่ถูกแสดงที่ใดเลย** — ส่งผ่าน `--env-file` ของ docker เท่านั้น สคริปต์อ่านแค่
`has_gemini_key` ที่เป็น true/false และตรวจแล้วว่าคำตอบของเส้นทางตั้งค่าไม่มีคำว่า
`api_key` หรือค่าที่ขึ้นต้นด้วย `AIza` ปนออกมา (ข้อตรวจในหัวข้อ 1 ของสคริปต์)

```bash
# 1) บนเครื่องพัฒนา — ทำชุดจาก commit โดยไม่ให้ CRLF ติดไป (ดูกับดักในหัวข้อ 6)
# branch นี้มีชุด release 213d65e อยู่ครบโดยไม่เปลี่ยนแม้ไบต์เดียว (ตรวจด้วย SHA256SUMS)
# และมีสคริปต์ตรวจรุ่นหลังสุด จึงส่งไฟล์เดียว
git -c core.autocrlf=false archive --format=tar.gz -o /tmp/switch.tar.gz <branch ของงานนี้>
scp -i <ไฟล์กุญแจ> /tmp/switch.tar.gz ubuntu@<IP>:~/

# 2) บนเซิร์ฟเวอร์ — แตกชุดและตรวจด่าน hash ก่อน build
mkdir -p ~/switch && tar xzf ~/switch.tar.gz -C ~/switch
cd ~/switch/docs/raw/model-switch-2569-10-28/backend-release
sha256sum -c SHA256SUMS                       # ต้องผ่านครบ 11 ไฟล์

# 3) build อิมเมจ "สำหรับตรวจ" ด้วย tag ของตัวเอง ไม่ใช่ tag ของ release
docker build -t course-advisor-system-backend:switch-check-2569-10-28 .

# 4) อ่านค่าทรัพยากรของ production มาใช้ให้เท่ากัน
docker inspect course-advisor-system-backend-1 \
  --format 'cpus={{.HostConfig.NanoCpus}} memory={{.HostConfig.Memory}}'

# 5) คอนเทนเนอร์ตรวจ — ไม่ publish port · ไม่ตั้ง RAG_TIME_BUDGET_S (ค่าตั้งต้น 30 = production)
docker run -d --name switch-check --network course-advisor-system_default \
  --env-file ~/course-advisor-system/.env \
  -e DATABASE_URL='postgresql+psycopg://postgres:<รหัส>@postgres:5432/course_advisor_test' \
  -e CHAT_TOP_K=25 \
  --cpus <เท่า production> --memory <เท่า production> \
  course-advisor-system-backend:switch-check-2569-10-28

# 6) ข้อที่ 7 — สวิตช์ Gemini จริง
docker cp ~/switch/eval/model_switch_api_check.py switch-check:/app/eval_check.py
docker exec -w /app -e PYTHONPATH=/app/backend \
  -e SWITCH_CHECK_DSN='postgresql://postgres:<รหัส>@postgres:5432/course_advisor_test' \
  switch-check python eval_check.py --api http://127.0.0.1:8000 --mode gemini

# 7) ข้อที่ 8 — Gemini ล้มแบบจำลอง ต้องเป็นคอนเทนเนอร์อีกตัว
#    198.51.100.1 คือที่อยู่ช่วงเอกสาร (TEST-NET-2) ที่ไม่มีเส้นทางไปถึง
#    คำขอของ Gemini จึงค้างจนชน timeout ที่เพดานเวลาบีบไว้ = รูปร่างเดียวกับของจริง
docker run -d --name switch-check-outage --network course-advisor-system_default \
  --add-host generativelanguage.googleapis.com:198.51.100.1 \
  --env-file ~/course-advisor-system/.env \
  -e DATABASE_URL='postgresql+psycopg://postgres:<รหัส>@postgres:5432/course_advisor_test' \
  -e CHAT_TOP_K=25 \
  --cpus <เท่า production> --memory <เท่า production> \
  course-advisor-system-backend:switch-check-2569-10-28
docker cp ~/switch/eval/model_switch_api_check.py switch-check-outage:/app/eval_check.py
docker exec -w /app -e PYTHONPATH=/app/backend \
  -e SWITCH_CHECK_DSN='postgresql://postgres:<รหัส>@postgres:5432/course_advisor_test' \
  switch-check-outage python eval_check.py --api http://127.0.0.1:8000 --mode outage

# 8) เก็บของ
docker rm -f switch-check switch-check-outage
docker rmi course-advisor-system-backend:switch-check-2569-10-28
```

ต้องมีผู้ใช้ที่เป็นผู้ดูแลบนฐานทดสอบชื่อ `switch-check@test.local` (สคริปต์ใช้ออก token เอง
จาก `JWT_SECRET` ของคอนเทนเนอร์ ไม่ต้องรู้รหัสผ่าน) ถ้ายังไม่มี:

```sql
insert into users (email, password_hash, full_name, is_active, is_admin, role, status)
values ('switch-check@test.local', 'ไม่ใช้รหัสผ่านในชุดนี้', 'ผู้ตรวจสวิตช์',
        true, true, 'admin', 'approved')
on conflict (email) do nothing;
```

**อ่านผลอย่างไร**

| โหมด | ผ่าน = |
|---|---|
| `--mode gemini` | `answer_model` ขึ้นต้นด้วย `gemini:` · `gemini_ok` ขยับ · `local_primary_*` และ `fallback_*` **ไม่ขยับเลย** |
| `--mode outage` | `gemini_ok` ไม่ขยับ · `fallback_local_attempt` ขยับ · **`fallback_local_ok` ขยับ** ← ข้อนี้คือผลของ patch · ถ้า `ok` เป็น 0 และ `failed` เท่ากับ `attempt` แปลว่ายังถูกเพดานเวลาปฏิเสธก่อนยิงคำขอแรก คือ patch ไม่ได้ผล |

คาดไว้ล่วงหน้าว่าโหมด `outage` คำขอนั้นจะยังจบด้วย HTTP 503 และผู้ใช้ไม่ได้คำตอบ
เพราะขั้นเขียนคำตอบที่ต้องอ้างอิงเอกสาร **ปฏิเสธโมเดลสำรองโดยเจตนา** (`fallback_declined`)
สิ่งที่ patch เปลี่ยนคือขั้นช่วยต่าง ๆ ได้ใช้โมเดลในเครื่องจริง และตัวนับเลิกรายงานเท็จ
— ไม่ใช่ทำให้ผู้ใช้ได้คำตอบตอน Gemini ล่ม (เรื่องนั้นเป็นการตัดสินใจเชิงนโยบาย ยังไม่ทำ)

## 9. ปิดงาน — deploy ขึ้น production แล้ว (28 ต.ค. 2569)

**ขึ้นใช้งานครบทั้งสามชั้น: ฐาน · backend · หน้าเว็บ**

| ชั้น | สถานะ |
|---|---|
| ฐาน | migration 010 ลงแล้ว · คอลัมน์ `provider` เพิ่ม · แถวเดิมไม่เปลี่ยน · `provider = NULL` |
| backend | อิมเมจ `course-advisor-system-backend:switch-2569-10-28` · `sha256:daa1a8fd689ddfbac712da40e62b159e595f035fc15e8fc082967628b152ecae` · ชุดทดสอบ 8/8 ผ่านในอิมเมจใหม่ก่อนสลับ · hash 11 ไฟล์ในอิมเมจ + 9 ไฟล์ในคอนเทนเนอร์ตรง |
| หน้าเว็บ | `assets/index-CEaz2vMx.js` + `index-r-tAGaTO.css` · 18 ไฟล์ผ่าน hash ทั้งตอนวางและตอนดึงผ่านเว็บจริง · สลับ `index.html` เป็นขั้นสุดท้าย |

**หน้าผู้ดูแลตรวจด้วยภาพจริงแล้ว** — สวิตช์แสดงครบ และระบบยังใช้ Gemini จาก env ถูกต้อง
สอดคล้องกับที่ API รายงาน: `effective = {provider: gemini, model: gemini-3.5-flash-lite,
source: env, honoured: false}` · `embedding = {model: bge-m3, changeable: false}` ·
คำตอบของเส้นทางนี้ไม่มีค่าคีย์ปนออกมา

**Gemini ยังเป็นตัวหลัก** — แถวในฐานยัง `provider = NULL` การ deploy ไม่ได้เปลี่ยนผู้ให้บริการ
การสลับไป Ollama ต้องเป็นการกดเองที่หน้าผู้ดูแลเท่านั้น

**ผลตรวจรับหลัง deploy**

```
HTTP 200 · 27.2s · status=answered · answer_model=gemini:gemini-3.5-flash-lite · citations=25
timing: total=27140ms prepare=18408ms write_answer=8702ms | decide=18198ms | outcome=ok
คำขอซ้ำทันที: total=17ms | cache_hit=6ms · answer_model=null   <- หลักฐานว่ารอบแรกไม่ได้มาจากแคช
ตัวนับ (หลังรอรอบเขียน 35 วินาที): gemini_ok=17 · fallback_local_attempt=1 ·
fallback_local_failed=1 · fallback_declined=1 · ไม่มี local_primary_* เลย
```

### ข้อจำกัดที่ยังอยู่หลัง deploy

1. **Ollama ยังไม่พร้อมตอบงานเอกสารภายในเพดาน 30 วินาที** — ตัวเลขทั้งหมดในข้อ 4
   ยังใช้ได้ตามเดิม ไม่ควรสลับไปใช้จนกว่าจะมีรอบวัดใหม่ที่ผ่าน
2. **เมื่อ Gemini ล่ม ยังไม่รับประกันว่าผู้ใช้จะได้คำตอบสำรอง** — patch ทำให้ตัวสำรอง
   *ได้ทำงานจริง* (ยืนยันบน production: ตอนคำขอแรกล้ม log ขึ้น `ollama /api/chat attempt
   1/3, 2/3, 3/3` คือมีคำขอออกไปจริง ซึ่งก่อนแก้เป็นไปไม่ได้) แต่ขั้นที่พรอมต์ใหญ่ยัง
   ทำไม่ทันเวลาที่กันไว้ และขั้นเขียนคำตอบที่ต้องอ้างอิงเอกสารยัง **ปฏิเสธโมเดลสำรอง
   โดยเจตนา** คำขอจึงจบด้วย 503 ได้เหมือนเดิม
3. วันที่ deploy Gemini เองตอบช้าผิดปกติ (ยิงตรงด้วยพรอมต์ 3 คำได้ 6.19s และ 38.54s
   ทั้งที่ปกติราว 2 วินาที) คำขอแรกหลัง deploy จึงชนเพดาน 30 วินาที — ไม่ได้เกิดจาก
   ชุดนี้ เพราะ `llm/gemini.py` ไม่ได้อยู่ใน 11 ไฟล์ที่ซ้อน และวัดได้โดยไม่ผ่านโค้ดเราเลย

### สิ่งที่แก้ระหว่าง deploy

* `deploy_web.sh` เดิน `assets` ด้วย glob ชั้นเดียว ตายที่โฟลเดอร์ย่อย `assets/courses/`
  แก้เป็น `find -type f` และยังตรวจ hash ราย**ไฟล์**ครบทุกไฟล์ (commit `7781a82`)
* `deploy_backend.sh` ตรวจ health เร็วเกินไปจนได้ `HTTP 000` ทั้งที่ backend ขึ้นปกติ
  (ตรวจซ้ำทันทีได้ 200) — **ยังไม่ได้แก้** ควรให้ลองซ้ำสัก 30 วินาทีก่อนสรุปว่าล้ม
* ชุด `web-release/assets` ไม่ได้อยู่ใน git (`.gitignore:57`) ต้องส่งขึ้นเซิร์ฟเวอร์แยก
  โดยมี `SHA256SUMS` ที่อยู่ใน git เป็นตัวตรวจ — ยืนยันแล้ว 19/19 ทั้งสองฝั่ง

### ทางย้อนที่ยังใช้ได้

```bash
cd /home/ubuntu/switch-release-2569-10-28
./rollback_web.sh --run /home/ubuntu/switch-release-2569-10-28/web-run-20261028-134529
./rollback_backend.sh        # กลับไป followup-2569-10-28 (sha256:2c25ad32170cae73…)
# คอลัมน์ provider เก็บไว้ได้ ไม่ต้องย้อนฐาน
```

---

## 10. ของที่สร้างไว้บนเครื่องนี้ (ลบได้)

* ฐาน `course_advisor_test` บนคอนเทนเนอร์ `course-advisor-system-postgres-1` (**ของ local ไม่ใช่ production**)
* โมเดล `qwen2.5:0.5b` ที่ `ollama pull` มาเพื่อทดสอบการสลับรุ่น (`ollama rm qwen2.5:0.5b`)
* ผู้ใช้ `switch-check@test.local` บนฐานทดสอบ (ไม่มีรหัสผ่านที่ใช้ได้)
