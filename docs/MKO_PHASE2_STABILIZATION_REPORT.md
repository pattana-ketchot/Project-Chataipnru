# MKO Phase 2 Stabilization — รายงานการแก้ไข (local/offline)

วันที่ 15 ก.ย. 2569 · worktree `course-advisor-system-mko2` · branch `mko-phase2` (ฐาน `9368d16`) · **ยังไม่ commit / push / deploy**

ขอบเขตงานคือแก้ 3 ปัญหาจาก `docs/MKO_PHASE2_SHADOW_EVAL.md` ถือเป็น Phase 2 stabilization ไม่ใช่ Phase 3
- ไม่แตะ production database และไม่ deploy
- `STRUCTURED_ANSWERS` บน production ยังเป็น `shadow`
- ไม่มีชื่อหลักสูตร คำถาม หรือคำตอบผูกไว้ในโค้ดของระบบ

---

## 1. Root cause และสิ่งที่แก้

### 1.1 คำถามต่อเนื่องเปลี่ยนหลักสูตรผิด ("แล้วคณิตศาสตร์ล่ะ")

**Root cause** (ยืนยันด้วยโค้ดและการเล่นซ้ำ offline ด้วยคำถามที่เขียนใหม่ตามที่ production บันทึกไว้)
1. ข้อความมีชื่อหลักสูตร → `own_scope = True` → ระบบไม่หาหลักสูตรที่กำลังคุยจากประวัติ ขั้น condense จึงไม่รู้บริบท และข้อความเหลือแค่ชื่อ ไม่มีเรื่องที่ถาม
2. ชื่อหลักสูตรบางชื่อเป็นชื่อศาสตร์ที่มีรายวิชาชื่อเดียวกัน โมเดลจึงเขียนใหม่เป็น "สาขาวิทยาการคอมพิวเตอร์เรียนวิชาคณิตศาสตร์อะไรบ้าง"
3. เกณฑ์เลือก `gained_scope or alt_score > best_score` ใช้คะแนนค้นหาเทียบข้ามขอบเขตหลักสูตร (0.678 > 0.405) ทำให้คำถามที่เปลี่ยนหลักสูตรที่ผู้ใช้ระบุเองชนะ

**สิ่งที่แก้ (general)** — `backend/app/services/follow_up.py` (ใหม่)
- **`swap_follow_up`:** ถ้าตัดชื่อหลักสูตร คำย่อ ปี และคำลงท้าย (แล้ว ล่ะ ครับ …) ออกแล้วข้อความไม่เหลืออะไร ถือเป็นการเปลี่ยนตัวแปรของคำถามก่อนหน้า
  - ประกอบคำถามใหม่ด้วยโค้ดจาก **คำถามล่าสุดของผู้ใช้ที่มีเนื้อหาจริง**: คงเรื่องที่ถาม (field) และเปลี่ยนเฉพาะหลักสูตรหรือปี **ไม่เรียกโมเดล**
  - รองรับคำย่อ ตัวเลขไทย ค.ศ. และคำถามต่อเนื่องหลายทอด
  - ปีของหลักสูตรเดิมถูกตัดเมื่อเปลี่ยนหลักสูตร
  - ข้อความที่มีชื่อหลายหลักสูตร หรือคำถามก่อนหน้าที่เทียบหลายหลักสูตร → ไม่เดา ส่งให้ขั้นเดิม
- **`explicit_programmes`:** ชื่อหลักสูตรที่ตามหลัง "วิชา"/"รายวิชา" (ไม่ใช่ "สาขาวิชา") คือชื่อรายวิชา ไม่นับเป็นหลักสูตรที่ผู้ใช้ระบุ
- **`rewrite_keeps_explicit`:** คำถามที่โมเดลเขียนใหม่ต้องมีชุดหลักสูตรตรงกับที่ผู้ใช้ระบุ ถ้าไม่ตรงต้องทิ้ง **ไม่ว่าคะแนนค้นหาจะสูงกว่าเท่าไร**
- **`chat.prepare_answer`:**
  - ขั้น 0.85 ใช้ `swap_follow_up` ก่อนขั้นแทนคำอ้างอิง ถ้าคำถามที่ประกอบได้เป็นคำถามค่าเทอม ส่งไปตารางค่าเทอม
  - ขั้น condense ส่ง "หลักสูตรที่คุยก่อนหน้า" และ "หลักสูตรที่ผู้ใช้ระบุ" ให้โมเดลเฉพาะเมื่อผู้ใช้ระบุชื่อเอง แล้วตรวจผลด้วย `rewrite_keeps_explicit`

### 1.2 คำถามเปรียบเทียบหลายหลักสูตร (CS กับคอมพิวเตอร์แอนิเมชันฯ)

**Root cause** (ยืนยันด้วย retrieval จริงบนคลังชุดเดียวกับ production)
- คำค้นหลังตัดชื่อเหลือ "กับ ต่างกันอย่างไร" ชิ้นที่ค้นเจอจึงเป็นเศษ ที่ `top_k=25` CS และ IT มีชิ้น OCR อ่านไม่ออกฝั่งละ 8 ชิ้น
- หลักฐานที่ใช้เทียบได้จริงคือ `newest_core_chunks` ≤ 2 ชิ้นจากฉบับล่าสุดตามปีในชื่อเท่านั้น แอนิเมชันฯ 2569 เป็นเอกสารสรุปที่ **ไม่มีหัวข้ออาชีพ** (ตรวจทั้งเล่มแล้ว) ทั้งที่ฉบับ 2564 มี
- ด่านตรวจเอกสารใช้เกณฑ์เปรียบเทียบ แต่ `CHAT_SYSTEM_PROMPT` ของขั้นเขียนคำตอบไม่มีเกณฑ์นี้ ขั้นเขียนคำตอบจึงปฏิเสธเองได้หลังด่านตรวจผ่าน

**สิ่งที่แก้ (general)** — `backend/app/services/comparison_evidence.py` (ใหม่)
- **`programme_evidence`:** หลักฐาน **แยกต่อหลักสูตร แยกตามด้าน** คือ ปรัชญา วัตถุประสงค์ อาชีพหลังสำเร็จการศึกษา และโครงสร้างหลักสูตร (หัวข้อตามแบบ มคอ.2 ที่วัดจากคลังจริงว่าเป็นบรรทัดขึ้นต้นที่พบบ่อย)
  - แต่ละด้านใช้ **ฉบับล่าสุดที่มีหัวข้อนั้น** ถ้าฉบับล่าสุดไม่มีจึงใช้ฉบับก่อนหน้า ชิ้นเอกสารคงชื่อหลักสูตรพร้อมปีของฉบับที่มาจริง จึงไม่ปนปีโดยไม่ระบุ
  - ฉบับที่ปีเท่ากัน (เช่น ป.โท/ป.เอก ชื่อสาขาเดียวกัน) ใช้ทุกฉบับ ไม่เลือกเอง
  - ตัดสารบัญและชิ้นอ่านไม่ออก เกณฑ์ความหนาแน่นสัญลักษณ์ ≥ 0.05 วัดจากคลัง 9,039 ชิ้น: ตัด 38 ชิ้น ล้วนเป็น OCR ที่อ่านไม่ออกหรือตารางสัญลักษณ์ ส่วนคำอธิบายรายวิชาภาษาอังกฤษอยู่ราว 0.015
  - รวมชิ้นถัดไปของหัวข้อด้วย เพราะรายการใต้หัวข้อมักยาวเลยขอบชิ้น
- **`describe_evidence`:** สรุปจากชิ้นที่ส่งจริงว่าพบด้านใดของหลักสูตรใด ฉบับปีใด และด้านใดไม่พบ **ส่งให้ทั้งด่านตรวจเอกสารและขั้นเขียนคำตอบชุดเดียวกัน**
- **`chat._retrieve` (เฉพาะคำถามหลายหลักสูตร):** หลักฐานรายด้านมาก่อน แล้วเติมชิ้นที่ค้นเจอ (ตัดสารบัญและชิ้นอ่านไม่ออกแล้ว) จนเต็มงบของหลักสูตรนั้น แต่ไม่น้อยกว่าครึ่งงบ
- **`llm/prompts.py`:**
  - `GROUNDING_COMPARISON_SYSTEM_PROMPT` เพิ่มกรณี true: (ก) มีข้อเท็จจริงของทุกหลักสูตรเพียงบางด้าน (ข) คำถามเชิงปริมาณ/จัดอันดับที่มีข้อเท็จจริงของทุกหลักสูตรแต่ไม่พอจัดอันดับ ส่วนกรณี false เดิมยังอยู่ครบ
  - `CHAT_COMPARISON_RULES` (ใหม่) ต่อท้าย system prompt **เฉพาะคำถามหลายหลักสูตร** มีกฎดังนี้
    - วางข้อเท็จจริงเทียบกันได้ และห้ามตอบว่าไม่พบเพียงเพราะไม่มีเอกสารที่เปรียบเทียบไว้
    - เทียบเฉพาะด้านที่มีหลักฐานทุกฝั่ง และบอกด้านที่ขาด
    - ห้ามสร้างความแตกต่างที่เนื้อหาไม่ระบุ
    - ระบุปีเมื่อต่างฉบับ

### 1.3 คำถามเชิงปริมาณ ("สาขาไหนเรียนเขียนโปรแกรมมากกว่ากัน")

**Root cause:** retrieval ได้รายวิชาเขียนโปรแกรมของทั้งสองหลักสูตรแล้ว แต่ด่านตรวจตัดสินแบบผ่าน/ไม่ผ่านทั้งคำถาม คำถามต้องการการจัดอันดับที่หลักฐานไม่รองรับ จึงคืน not_found และข้อมูลที่ตอบได้หายหมด

**สิ่งที่แก้:**
- **ด่านตรวจ:** ด่านตรวจของคำถามหลายหลักสูตรยอมให้ผ่านเมื่อมีข้อเท็จจริงในเรื่องที่ถามของทุกหลักสูตร (ข้อ 1.2 ข)
- **ขั้นเขียนคำตอบ:** ต้องบอกก่อนว่ายังสรุป "มากกว่า" จากเอกสารไม่ได้ แล้วยกข้อเท็จจริงที่มีของแต่ละหลักสูตร (เช่น รายวิชาที่ปรากฏ พร้อมบอกว่าเป็นบางส่วน) และบอกเกณฑ์ที่ต้องกำหนด (จำนวนวิชา/หน่วยกิต/วิชาบังคับ-เลือก/ปีหลักสูตร) **ห้ามเดาหรือจัดอันดับเอง**
- **ถ้าไม่มีข้อเท็จจริงของหลักสูตรใดหลักสูตรหนึ่ง:** ด่านตรวจยังตอบ false และระบบคืน not_found ตามเดิม (มีเทสต์)
- **คำถามหลักสูตรเดียว:** ไม่ได้เปลี่ยนด่านตรวจของคำถามหลักสูตรเดียว (ดูข้อจำกัด 7.4)

### 1.4 แคชคำตอบ

- `_LOGIC_VERSION` เปลี่ยนจาก `31` เป็น `33` เพราะคำตอบของคำถามเปรียบเทียบที่ไม่มีประวัติถูกเก็บลงแคชได้ ถ้าไม่เปลี่ยน แคชจะตอบแบบเดิมก่อนโค้ดใหม่ทำงาน
- ข้าม `32` เพราะงานค่าเทอมที่ยังไม่ commit ใน repo หลักใช้เลขนั้นอยู่

## 2. ไฟล์ที่แก้

| ไฟล์ | ประเภท | สาระ |
|---|---|---|
| `backend/app/services/follow_up.py` | ใหม่ (154 บรรทัด) | swap_follow_up, explicit_programmes, rewrite_keeps_explicit |
| `backend/app/services/comparison_evidence.py` | ใหม่ (186 บรรทัด) | programme_evidence, describe_evidence, is_garbled |
| `backend/app/services/chat.py` | แก้ (+69/−20) | ขั้น 0.85, guard ของ condense, หลักฐานของ `_retrieve` หลายหลักสูตร, note ส่งด่านตรวจและขั้นเขียนคำตอบ, system prompt เฉพาะคำถามเปรียบเทียบ |
| `llm/prompts.py` | แก้ (+29) | เกณฑ์เปรียบเทียบของด่านตรวจ, `CHAT_COMPARISON_RULES` |
| `backend/app/services/answer_cache.py` | แก้ | `_LOGIC_VERSION` 31 → 33 |
| `eval/follow_up_scope_check.py` | ใหม่ (21 เทสต์) | กรณี A/B/C, ทุกคู่หลักสูตร (สมมติ + ฐานข้อมูลจริง), guard, prepare_answer |
| `eval/comparison_evidence_check.py` | ใหม่ (19 เทสต์) | ตัวเลือกหลักฐาน, ปีฉบับ, ความสอดคล้องของ prompt, prepare_answer, คลังจริง, retrieval จริง |
| `eval/multi_program_scope_check.py` | แก้เทสต์เดิม | ตัวปลอมเปลี่ยนจาก `program_match.newest_core_chunks` เป็น `chat.programme_evidence` และชิ้นปลอมมี `content` — **เกณฑ์ที่ตรวจไม่เปลี่ยน** (ยังตรวจการจัดกลุ่มตามหลักสูตร หลักฐานมาก่อน ไม่มีชิ้นซ้ำ และคะแนน) |

ไม่ได้แก้ไฟล์อื่น
- `program_match.newest_core_chunks` ยังอยู่ (มีเทสต์เดิมใช้) แต่ `chat` ไม่เรียกแล้ว
- ส่วนอื่นไม่ถูกแตะ: structured_intent / curriculum_facts / structured_shadow / config / compose

## 3. ผลทดสอบ local/offline

| ชุดทดสอบ | จำนวน | ผล |
|---|---:|---|
| mko_extraction_check | 45 | OK |
| tuition_followup_check | 14 | OK |
| multi_program_scope_check (แก้ตัวปลอม) | 12 | OK |
| program_core_check | 7 | OK |
| rationale_key_check | 4 | OK |
| conversation_context_check | 12 | OK |
| eval_runner_check | 4 | OK |
| gemini_quota_check | 6 | OK |
| recommend_intent_check | 12 | OK |
| recommendation_reply_check | 27 | OK |
| structured_routing_check | 21 | OK |
| structured_shadow_check (flag off/shadow) | 18 | OK |
| curriculum_facts_check | 16 | OK |
| **follow_up_scope_check (ใหม่)** | 21 | OK |
| **comparison_evidence_check (ใหม่)** | 19 | OK (รันทั้ง `CHAT_TOP_K` ค่าเริ่มต้นและ 25) |
| **รวม** | **238** | **ผ่านทั้งหมด ไม่มีเทสต์ที่ถูกข้าม** |

**สภาพแวดล้อมทดสอบ**
- ฐานข้อมูล local มี `course_chunks` คัดลอกแบบอ่านอย่างเดียวจาก production (`pg_dump --data-only -t course_chunks`) ตรวจแล้ว rowhash ตรงกับ production ทุกแถว (9,039 แถว)
- embedding ใช้ `bge-m3` ของ Ollama ในเครื่อง ไม่มีการเรียกโมเดลภาษา
- ไม่ได้รัน `behaviour_check` และไม่ได้ยิง production

**ครอบคลุมข้อที่ขอ**
1. **Regression เดิมทั้งหมด:** 13 ชุด 198 ข้อ ผ่าน
2. **Follow-up:** A, B, C, คำถามต่อเนื่องหลายทอด, คำย่อ, เปลี่ยน field อื่น, หลักสูตร+ปีพร้อมกัน, ข้อความที่ต้องไม่ถูกประกอบใหม่ 6 แบบ, **ทุกคู่ลำดับของหลักสูตรจริงในฐานข้อมูล** (17×16 = 272 คู่) และเส้นทางใน prepare_answer
3. **Comparison หลายคู่:**
   - CS vs IT และ CS vs คอมพิวเตอร์แอนิเมชันฯ (retrieval จริง)
   - **3 คู่ที่ไม่ได้ใช้ออกแบบ** เลือกจากฐานข้อมูลอัตโนมัติด้วยการตัดหลักสูตรที่อยู่ในคำถามออกแบบ
   - **ทุกคู่ของ 17 หลักสูตร (136 คู่) มีอย่างน้อยหนึ่งด้านที่มีหลักฐานทั้งสองฝั่ง**
   - ทุกหลักสูตร: แต่ละด้านมาจากฉบับล่าสุดที่มีหัวข้อนั้นจริง
4. **เชิงปริมาณแบบหลักฐานไม่พอ:**
   - เนื้อหามีรายวิชาเขียนโปรแกรมของทั้งสองหลักสูตร
   - prompt ของด่านตรวจและขั้นเขียนคำตอบมีเกณฑ์ตรงกัน (ห้ามจัดอันดับ บอกเกณฑ์ที่ต้องกำหนด)
   - ด่านตรวจที่ตอบ false ยังได้ not_found
5. **Out-of-scope:** "ทีมลิเวอร์พูลเป็นยังไงบ้าง" ยังได้ `out_of_scope` ทั้งกับตัวปลอมและ retrieval จริง (คะแนน 0.4863 < 0.50) และไม่ถึงด่านตรวจ
6. **`STRUCTURED_ANSWERS=off`:** structured_shadow_check 18 ข้อผ่าน และคำถามหลักสูตรเดียวได้ system prompt และ user prompt **เหมือนเดิมทุกตัวอักษร** (เทสต์เทียบตรง)

## 4. Before / after ของ regression cases (offline, `CHAT_TOP_K=25` เท่า production)

**วิธีวัด**
- before = โค้ด `9368d16` (backend เดียวกับ production `a4201cc`) · after = working tree
- ฐานข้อมูลและ embedding เดียวกัน
- ขั้นที่ใช้โมเดลถูกแทนด้วยตัวปลอม ขั้น condense คืนคำถามที่ production บันทึกไว้จริงของแต่ละกรณี จึงเล่นซ้ำสิ่งที่เกิดบนเว็บได้ตรง

### Follow-up

| กรณี | before (interpreted → intent) | after (interpreted → intent) |
|---|---|---|
| A IT กี่หน่วยกิต → "แล้ววิทยาการคอมพิวเตอร์ล่ะ" | "หลักสูตรวิทยาการคอมพิวเตอร์เรียนกี่หน่วยกิต" → total_credits/CS (เรียกโมเดล) | เหมือนเดิม **ไม่เรียกโมเดล** |
| **B** CS กี่หน่วยกิต → "แล้วคณิตศาสตร์ล่ะ" | **"สาขาวิทยาการคอมพิวเตอร์เรียนวิชาคณิตศาสตร์อะไรบ้าง" → rag, ค้นเฉพาะเอกสาร CS** | **"สาขาคณิตศาสตร์เรียนกี่หน่วยกิต" → total_credits/คณิตศาสตร์, เอกสารคณิตศาสตร์ 2564/2569** |
| C คณิตศาสตร์ 2569 กี่หน่วยกิต → "แล้ว พ.ศ. 2564 ล่ะ" | "หลักสูตรคณิตศาสตร์ พ.ศ. 2564 เรียนกี่หน่วยกิต" → total_credits/คณิตศาสตร์/2564 (เรียกโมเดล) | เหมือนเดิม **ไม่เรียกโมเดล** |

### Comparison (หลักฐานที่ส่งให้ด่านตรวจและขั้นเขียนคำตอบ)

| คำถาม | before | after |
|---|---|---|
| CS vs IT | 30 ชิ้น · OCR อ่านไม่ออกฝั่งละ 8 · ด้าน: ปรัชญา/วัตถุประสงค์/อาชีพ · ขั้นเขียนคำตอบไม่มีกฎเปรียบเทียบ | 20 ชิ้น · อ่านไม่ออก 0 · สารบัญ 0 · ด้าน: ปรัชญา/วัตถุประสงค์/อาชีพ/โครงสร้าง (2566 ทั้งสองฝั่ง) · มีกฎและสรุปหลักฐาน |
| **CS vs คอมพิวเตอร์แอนิเมชันฯ** | แอนิเมชันฯ: **ไม่มีอาชีพ** (มีแค่ปรัชญา/วัตถุประสงค์ 2569) · CS อ่านไม่ออก 8 | แอนิเมชันฯ: ปรัชญา/วัตถุประสงค์/โครงสร้าง **2569** + **อาชีพ 2564 (ระบุปีกำกับ)** · CS ครบ 4 ด้าน 2566 · อ่านไม่ออก 0 |
| คู่ 1 (เลือกอัตโนมัติ) | ฝั่งละ 3–4 ด้าน · สารบัญ 1 | ฝั่งละ 4 ด้าน · สารบัญ 0 |
| คู่ 2 (เลือกอัตโนมัติ) | ฝั่งละ 3–4 ด้าน · สารบัญ 1 | ฝั่งละ 4 ด้าน · สารบัญ 0 |
| คู่ 3 (เลือกอัตโนมัติ มี ป.โท+ป.เอก ปีเดียวกัน) | 2 ด้าน · สารบัญ 2 | 4 ด้าน · แยกป.โท/ป.เอก ในสรุป · 33 ชิ้น |
| เชิงปริมาณ CS vs IT (เขียนโปรแกรม) | ฝั่งละ 15 ชิ้น (มีคำว่าโปรแกรม 13) · สารบัญ IT 5 | ฝั่งละ 13 ชิ้น (มีคำว่าโปรแกรม 8) · สารบัญ 0 · มีกฎห้ามจัดอันดับ |
| Out-of-scope | out_of_scope | out_of_scope |

**สรุปหลักฐานที่ส่งจริงของ CS vs คอมพิวเตอร์แอนิเมชันฯ (after)**
```
[สรุปจากระบบ: หัวข้อที่พบในเนื้อหาด้านล่าง แยกตามหลักสูตรและปีของฉบับ]
- คอมพิวเตอร์แอนิเมชันและมัลติมีเดีย: ปรัชญา (พ.ศ. 2569); วัตถุประสงค์ (พ.ศ. 2569); อาชีพหลังสำเร็จการศึกษา (พ.ศ. 2564); โครงสร้างหลักสูตร (พ.ศ. 2569)
- วิทยาการคอมพิวเตอร์: ปรัชญา (พ.ศ. 2566); วัตถุประสงค์ (พ.ศ. 2566); อาชีพหลังสำเร็จการศึกษา (พ.ศ. 2566); โครงสร้างหลักสูตร (พ.ศ. 2566)
```

**สิ่งที่ยังไม่ได้วัด:** **ถ้อยคำคำตอบจริงของโมเดล** (Gemini) หลังแก้
- ในเครื่องไม่มีคีย์ของโมเดลที่ใช้บน production และผลจากโมเดลอื่นใช้แทนไม่ได้
- ตารางข้างบนยืนยันได้ถึงระดับ "คำถามที่ตีความ หลักฐาน และคำสั่งที่โมเดลได้รับ" ไม่ใช่ระดับ "โมเดลตอบตามคำสั่งแล้ว"

## 5. Behavior เดิมที่เปลี่ยน

**ตั้งใจเปลี่ยน**
1. **คำถามต่อเนื่องที่เหลือแค่ชื่อหลักสูตรหรือปี:** ได้คำถามจากโค้ดแทนโมเดล (ลดการเรียกโมเดลหนึ่งครั้ง) เรื่องที่ถามมาจากคำถามล่าสุดของผู้ใช้ที่มีเนื้อหา
2. **ผู้ใช้ระบุหลักสูตรเองในคำถามต่อเนื่องที่มีเนื้อหาอื่น:** prompt ของ condense มีสองบรรทัดเพิ่ม และคำถามที่เขียนใหม่ที่เปลี่ยนหลักสูตรถูกทิ้ง (ใช้ข้อความดิบแทน)
3. **คำถามหลายหลักสูตร**
   - หลักฐานเปลี่ยนเป็นรายด้านต่อหลักสูตรพร้อมปี และตัดสารบัญกับชิ้นอ่านไม่ออก จำนวนชิ้นรวมลดลงในคู่ส่วนใหญ่ (30 → 20–26) แต่เพิ่มในหลักสูตรที่มีหลายระดับปริญญาปีเดียวกัน (29 → 33)
   - ด่านตรวจผ่อนให้ผ่านในสองกรณีที่ระบุ จึงคาดว่า not_found ของคำถามเปรียบเทียบจะลดลง
   - ขั้นเขียนคำตอบได้กฎเปรียบเทียบและสรุปหลักฐาน คำตอบอาจยาวกว่าสามประโยค
4. **แคชคำตอบทั้งหมดหมดอายุ** ครั้งเดียวหลัง deploy (เปลี่ยนรุ่นตรรกะ) คำถามแรกของแต่ละข้อความจะเรียกโมเดลใหม่

**ตรวจแล้วว่าไม่เปลี่ยน**
- คำถามหลักสูตรเดียว: system prompt, user prompt, เกณฑ์ด่านตรวจ, retrieval (มีเทสต์เทียบตรง)
- คำถามนอกขอบเขต, ค่าเทอม, คำทักทาย, รายชื่อหลักสูตร, การแนะนำสาขา, "สาขานี้"/"หลักสูตรนี้" (ชุดทดสอบเดิมผ่าน)
- `STRUCTURED_ANSWERS` และ shadow hook (ไม่ได้แก้ แต่ shadow ได้ interpreted_question ที่ถูกขึ้น เช่น กรณี B กลายเป็น structured/total_credits)

## 6. สิ่งที่ไม่ได้ทำ

- ไม่ commit / push / deploy
- ไม่แก้ production database และไม่เปลี่ยน `STRUCTURED_ANSWERS`
- ไม่เริ่ม Phase 3

## 7. Known limitations ที่ยังเหลือ

1. **ยังไม่ได้วัดกับโมเดลจริง:** ผลของกฎใหม่ต่อถ้อยคำคำตอบของ Gemini ยังไม่ได้วัด (ข้อ 4) โดยเฉพาะ
   - ขั้นเขียนคำตอบเปรียบเทียบจริงหรือไม่
   - ไม่จัดอันดับในคำถามเชิงปริมาณหรือไม่
   - ระบุปีเมื่อต่างฉบับหรือไม่
   - ด่านตรวจที่ผ่อนลงปล่อยกรณีที่ไม่ควรผ่านหรือไม่

   ต้องวัดซ้ำหลายรอบกับโมเดลจริงก่อน deploy เพราะเป็นการตัดสินของโมเดล ต้องได้รับอนุมัติวิธีวัดก่อน
2. **ขอบเขตของ swap_follow_up:**
   - ใช้เฉพาะข้อความที่ไม่เหลือเนื้อหาอื่น
   - คำถามก่อนหน้าที่ไม่มีชื่อหลักสูตร (เช่น คำขอคำแนะนำ) จะได้ชื่อหลักสูตรต่อท้ายในวงเล็บ ซึ่งอาจอ่านไม่เป็นธรรมชาติ
   - คำลงท้ายที่ไม่อยู่ในรายการทำให้ไม่เข้าเงื่อนไข และไหลไปขั้น condense ตามเดิม
3. **การแยกชื่อรายวิชาใช้แค่คำว่า "วิชา" ที่นำหน้า:** ประโยคอย่าง "แล้วคณิตศาสตร์ในหลักสูตรวิทยาการคอมพิวเตอร์ล่ะ" จะนับเป็นสองหลักสูตร
   - `_compares_programmes`/`resolve_scopes` ยังนับชื่อรายวิชาเป็นหลักสูตร เช่น คำถามรายวิชาที่มีชื่อศาสตร์ อาจถูกนับเป็นคำถามหลายหลักสูตร — ไม่ได้แก้เพราะอยู่นอกขอบเขตรอบนี้
4. **ด่านตรวจของคำถามหลักสูตรเดียวยังตัดสินแบบผ่าน/ไม่ผ่านทั้งคำถาม:** คำถามหลายส่วนที่ตอบได้บางส่วนยังได้ not_found ได้ ไม่ได้แก้เพราะเสี่ยงต่อ grounding ของคำถามส่วนใหญ่ และต้องวัดกับโมเดลจริง
5. **ชิ้นที่ค้นเจอของคำถามเปรียบเทียบลดลงเหลืออย่างน้อยครึ่งงบ:** ในคำถามเชิงปริมาณ ชิ้นที่มีคำว่าโปรแกรมลดจาก 13 เป็น 8 ต่อฝั่ง ยังพอยกตัวอย่าง แต่ไม่ครบรายวิชา ซึ่งตรงกับกฎที่ให้บอกว่าเป็นบางส่วน
6. **เกณฑ์หัวข้อผูกกับรูปแบบ มคอ.2:** เอกสารรูปแบบอื่น (หน้าเว็บ) มีหัวข้อไม่ครบ ตัวอย่างเช่นสาธารณสุขศาสตร์มีเฉพาะปรัชญาและอาชีพ สรุปหลักฐานจะบอกว่า "ไม่พบในเนื้อหาที่ค้นได้"
7. **หลักสูตรที่มีหลายระดับปริญญาปีเดียวกัน:** ได้หลักฐานทุกระดับ จำนวนชิ้นมากขึ้น (ตัวอย่าง 33 ชิ้น) และคำตอบต้องแยกระดับเอง
8. **เลขรุ่นแคช:** ตั้งเป็น 33 ถ้ารวมงานค่าเทอม (32) เข้ามาภายหลัง ต้องตั้งเลขใหม่ที่ไม่ซ้ำ

## 8. git status / diff

```
$ git status --short
 M backend/app/services/answer_cache.py
 M backend/app/services/chat.py
 M eval/multi_program_scope_check.py
 M llm/prompts.py
?? backend/app/services/comparison_evidence.py
?? backend/app/services/follow_up.py
?? docs/MKO_PHASE2_SHADOW_EVAL.md
?? docs/MKO_PHASE2_STABILIZATION_REPORT.md
?? eval/comparison_evidence_check.py
?? eval/follow_up_scope_check.py

$ git diff --stat
 backend/app/services/answer_cache.py |  4 +-
 backend/app/services/chat.py         | 89 ++++++++++++++++++++++++++++--------
 eval/multi_program_scope_check.py    | 10 ++--
 llm/prompts.py                       | 29 ++++++++++++
 4 files changed, 107 insertions(+), 25 deletions(-)
```

- secret scan ของไฟล์ที่แก้และไฟล์ใหม่: ไม่พบ key/รหัสผ่าน/IP ของเซิร์ฟเวอร์
- diff ของไฟล์ที่มีอยู่เดิมอยู่ในภาคผนวก ไฟล์ใหม่ดูได้ที่ path ในข้อ 2

---

## ภาคผนวก — `git diff` ของไฟล์เดิม

```diff
diff --git a/backend/app/services/answer_cache.py b/backend/app/services/answer_cache.py
index 9a84eff..61ba0f8 100644
--- a/backend/app/services/answer_cache.py
+++ b/backend/app/services/answer_cache.py
@@ -68,7 +68,9 @@ def question_key(question: str) -> str | None:
 # หมดอายุ เจอจริงตอนเพิ่มด่านถามกลับเมื่อคำถามไม่ระบุสาขา: แก้เสร็จ deploy แล้วทดสอบ
 # กลับได้คำตอบผิดแบบเดิมทุกประการ เพราะแคชตอบก่อนที่โค้ดใหม่จะได้ทำงาน ซึ่งอ่านผลแล้ว
 # ดูเหมือนการแก้ไม่ได้ผล ทั้งที่โค้ดถูกแล้ว
-_LOGIC_VERSION = "31"
+# 33: Phase 2 stabilization — คำถามต่อเนื่องที่เปลี่ยนหลักสูตร/ปี และหลักฐานกับกฎของคำถามหลายหลักสูตร
+#     (ข้าม 32 เพราะงานค่าเทอมที่ยังไม่ได้รวม branch ใช้เลขนั้นอยู่ ถ้าใช้เลขซ้ำ แคชของอีกตรรกะจะถูกหยิบมาตอบ)
+_LOGIC_VERSION = "33"
 
 
 def corpus_version(db: Session, top_k: int) -> str:
diff --git a/backend/app/services/chat.py b/backend/app/services/chat.py
index 6dc6ed7..d8a5cb9 100644
--- a/backend/app/services/chat.py
+++ b/backend/app/services/chat.py
@@ -27,6 +27,8 @@ from app.db.session import SessionLocal
 from app.models.chat import ChatMessage, ChatSession
 from app.schemas.chat import ChatReply, ChatCitation
 from app.services.chat_history import user_first
+from app.services.comparison_evidence import describe_evidence, is_garbled, programme_evidence
+from app.services.follow_up import explicit_programmes, rewrite_keeps_explicit, swap_follow_up
 from app.services.course_scope import (
     _distinctive_name,
     programmes_named,
@@ -46,6 +48,7 @@ from app.services.vector_search import search_similar_chunks
 
 from llm.connector import ChatMessage as LLMMessage, LLMConnectionError  # noqa: E402  (sys.path ตั้งโดย llm_client)
 from llm.prompts import (  # noqa: E402
+    CHAT_COMPARISON_RULES,
     CHAT_SYSTEM_PROMPT,
     CONDENSE_SYSTEM_PROMPT,
     GROUNDING_CHECK_SYSTEM_PROMPT,
@@ -167,7 +170,9 @@ def _load_history(db: Session, session_id: uuid.UUID) -> list[ChatMessage]:
     return list(reversed(rows))  # เรียงเก่า -> ใหม่ ก่อนส่งเข้า prompt
 
 
-def _format_history_for_condense(history: list[ChatMessage], programme: str | None = None) -> str:
+def _format_history_for_condense(
+    history: list[ChatMessage], programme: str | None = None, explicit: list[str] | None = None
+) -> str:
     """
     ส่งเฉพาะคำถามของผู้ใช้เข้า prompt เขียนคำถามใหม่ ไม่ส่งคำตอบของผู้ช่วย
 
@@ -184,10 +189,20 @@ def _format_history_for_condense(history: list[ChatMessage], programme: str | No
     lines = "\n".join(f"- {q}" for q in users) if users else "(ไม่มี)"
     if programme:
         lines = f"(หลักสูตรที่กำลังคุยกันล่าสุด: {programme})\n{lines}"
+    if explicit:
+        # คำถามล่าสุดเอ่ยชื่อหลักสูตรเอง บางชื่อเป็นชื่อศาสตร์ที่มีรายวิชาชื่อเดียวกัน โมเดลเคยอ่านเป็นรายวิชาของหลักสูตร
+        # ก่อนหน้า (ดู services/follow_up.py) จึงบอกให้ชัดว่าคำนั้นคือหลักสูตรที่ถาม ผลที่ยังเปลี่ยนหลักสูตรถูกทิ้งอีกชั้น
+        lines = (
+            f"{lines}\n(คำถามล่าสุดระบุชื่อหลักสูตรเอง: {', '.join(explicit)} — คำนี้คือชื่อหลักสูตร ไม่ใช่ชื่อรายวิชา "
+            "คำถามที่เขียนใหม่ต้องถามถึงหลักสูตรนี้ ถ้าคำถามล่าสุดอ้างถึงเรื่องที่ถามก่อนหน้า ให้คงเรื่องนั้นไว้แล้วเปลี่ยนเฉพาะหลักสูตร)"
+        )
     return lines
 
 
-def _condense(connector, history: list[ChatMessage], message: str, programme: str | None = None) -> str:
+def _condense(
+    connector, history: list[ChatMessage], message: str, programme: str | None = None,
+    explicit: list[str] | None = None,
+) -> str:
     """เขียนคำถามใหม่ให้สมบูรณ์ คืนคำถามเดิมถ้าทำไม่สำเร็จ"""
     try:
         raw = connector.chat(
@@ -195,7 +210,7 @@ def _condense(connector, history: list[ChatMessage], message: str, programme: st
                 LLMMessage(role="system", content=CONDENSE_SYSTEM_PROMPT),
                 LLMMessage(
                     role="user",
-                    content=build_condense_prompt(_format_history_for_condense(history, programme), message),
+                    content=build_condense_prompt(_format_history_for_condense(history, programme, explicit), message),
                 ),
             ],
             temperature=0.0,
@@ -229,6 +244,11 @@ def _format_chunks(chunks) -> str:
     return "\n\n".join(parts)
 
 
+def _with_note(note: str, content_block: str) -> str:
+    """ต่อสรุปหลักฐานของคำถามหลายหลักสูตรไว้หน้าเนื้อหา ให้ด่านตรวจเอกสารและขั้นเขียนคำตอบเห็นสรุปเดียวกัน"""
+    return f"{note}\n\n{content_block}" if note else content_block
+
+
 def _retrieve(db: Session, connector, question: str):
     """
     ค้นเนื้อหาที่เกี่ยวข้อง โดยจำกัดขอบเขตไว้ที่หลักสูตรเดียวถ้าระบุได้จากคำถาม
@@ -243,22 +263,30 @@ def _retrieve(db: Session, connector, question: str):
 
     คำถามที่เอ่ยถึงหลายหลักสูตร (เช่น เปรียบเทียบสองสาขา) ค้นแยกทีละหลักสูตรโดยแบ่งจำนวนชิ้นเท่าๆ กัน
     ถ้าค้นรวมกันในครั้งเดียว หลักสูตรแรกที่เจอกินที่ทั้งหมด (เคยได้ 25 ต่อ 0 ชิ้น) อีกหลักสูตรไม่มีหลักฐาน
-    เหลือให้เทียบ (ดู course_scope.resolve_scopes) และวางแก่นของแต่ละหลักสูตร (อาชีพ วัตถุประสงค์) ไว้ก่อน
-    ชิ้นที่ค้นเจอของหลักสูตรนั้น เพราะคำค้นหลังตัดชื่อแทบไม่มีเรื่องให้ค้น ชิ้นที่ได้จึงไม่มีข้อเท็จจริงที่ใช้เทียบ
-    (ดู program_match.newest_core_chunks) จัดเป็นกลุ่มตามหลักสูตรเพื่อให้โมเดลแยกได้ว่าข้อเท็จจริงเป็นของใคร
+    เหลือให้เทียบ (ดู course_scope.resolve_scopes) และวางหลักฐานรายด้านของแต่ละหลักสูตร (ปรัชญา วัตถุประสงค์ อาชีพ
+    โครงสร้างหลักสูตร พร้อมปีของฉบับที่มา) ไว้ก่อนชิ้นที่ค้นเจอของหลักสูตรนั้น เพราะคำค้นหลังตัดชื่อแทบไม่มีเรื่องให้ค้น
+    ชิ้นที่ได้จึงไม่มีข้อเท็จจริงที่ใช้เทียบ (ดู comparison_evidence.programme_evidence) จัดเป็นกลุ่มตามหลักสูตรเพื่อให้
+    โมเดลแยกได้ว่าข้อเท็จจริงเป็นของใคร ชิ้นที่เป็นสารบัญหรืออ่านไม่ออกถูกตัดทิ้ง
     """
     scopes = resolve_scopes(db, question)
     if len(scopes) >= 2:
-        from app.services.program_match import newest_core_chunks
+        from app.services.program_match import _looks_like_table_of_contents
 
         vector = connector.embed(scopes[0].search_text)
         per_programme = -(-TOP_K_CHUNKS // len(scopes))
         chunks = []
         for scope in scopes:
-            found = search_similar_chunks(db, vector, top_k=per_programme, course_ids=scope.course_ids)
-            core = newest_core_chunks(db, scope.course_ids, score=found[0].score if found else 0.0)
-            core_ids = {c.chunk_id for c in core}
-            chunks += core + [c for c in found if c.chunk_id not in core_ids]
+            found = [
+                c for c in search_similar_chunks(db, vector, top_k=per_programme, course_ids=scope.course_ids)
+                if not is_garbled(c.content) and not _looks_like_table_of_contents(c.content)
+            ]
+            evidence = programme_evidence(db, scope.course_ids, score=found[0].score if found else 0.0)
+            evidence_ids = {c.chunk_id for c in evidence}
+            found = [c for c in found if c.chunk_id not in evidence_ids]
+            # หลักฐานรายด้านมาก่อน ชิ้นที่ค้นเจอเติมจนเต็มงบของหลักสูตรนั้น แต่ไม่น้อยกว่าครึ่งงบ เพราะชิ้นที่ค้นเจอคือหลักฐาน
+            # ของเรื่องที่ถามเจาะจง เช่น รายวิชาที่เกี่ยวข้อง ซึ่งหัวข้อตามแบบ มคอ.2 ไม่ครอบคลุม
+            keep = max(per_programme - len(evidence), per_programme // 2)
+            chunks += evidence + found[:keep]
         return chunks
     scope = resolve_scope(db, question)
     if scope is None:
@@ -330,7 +358,7 @@ def _program_names(db: Session) -> list[str]:
     return _PROGRAM_NAMES
 
 
-def _can_answer_from(connector, chunks, question: str, comparison: bool = False) -> bool:
+def _can_answer_from(connector, chunks, question: str, comparison: bool = False, note: str = "") -> bool:
     """
     เนื้อหาที่ค้นเจอมีข้อเท็จจริงตอบคำถามนี้ได้จริงไหม
 
@@ -338,10 +366,12 @@ def _can_answer_from(connector, chunks, question: str, comparison: bool = False)
     เพราะไม่มีเอกสารเล่มไหนเขียนเปรียบเทียบกับหลักสูตรอื่นไว้ (ตัวเลขที่วัดอยู่ใน prompts.GROUNDING_COMPARISON_
     SYSTEM_PROMPT) คำถามหลักสูตรเดียวยังใช้เกณฑ์เดิมทุกประการ
     """
-    return _grounding_verdict(connector, chunks, question, comparison)[0]
+    return _grounding_verdict(connector, chunks, question, comparison, note)[0]
 
 
-def _grounding_verdict(connector, chunks, question: str, comparison: bool = False) -> tuple[bool, str]:
+def _grounding_verdict(
+    connector, chunks, question: str, comparison: bool = False, note: str = ""
+) -> tuple[bool, str]:
     """
     ผลตัดสินของด่านตรวจเอกสารพร้อมเหตุผลที่โมเดลให้ คืน (ตอบได้ไหม, เหตุผล)
 
@@ -362,7 +392,7 @@ def _grounding_verdict(connector, chunks, question: str, comparison: bool = Fals
                     role="system",
                     content=GROUNDING_COMPARISON_SYSTEM_PROMPT if comparison else GROUNDING_CHECK_SYSTEM_PROMPT,
                 ),
-                LLMMessage(role="user", content=build_grounding_check_prompt(_format_chunks(chunks), question)),
+                LLMMessage(role="user", content=build_grounding_check_prompt(_with_note(note, _format_chunks(chunks)), question)),
             ],
             temperature=0.0,
             json_mode=True,
@@ -1151,7 +1181,15 @@ def prepare_answer(
     own_scope = resolve_scope(db, message) is not None
     context_programme = _context_programme(db, history) if history and not own_scope else None
     query = message
-    if not own_scope and _REFERENCE.search(message):
+    # --- 0.85 คำถามต่อเนื่องที่เปลี่ยนแค่หลักสูตรหรือปี ("แล้ว X ล่ะ") -> ประกอบคำถามใหม่จากคำถามก่อนหน้าด้วยโค้ด ---
+    # เรื่องที่ถามคงเดิม เปลี่ยนเฉพาะสิ่งที่ผู้ใช้ระบุใหม่ ไม่ให้โมเดลเดาว่าชื่อที่ผู้ใช้พิมพ์คือหลักสูตรหรือรายวิชา
+    # (ดู services/follow_up.py) ไม่ใช่กรณีนี้ก็ไปขั้นแทนคำอ้างอิงและขั้นเขียนคำถามใหม่ตามเดิม
+    swapped = swap_follow_up(db, history, message, context_programme) if history else None
+    if swapped:
+        if is_tuition_question(swapped):
+            return _tuition_reply(session.id, swapped)
+        query = swapped
+    elif not own_scope and _REFERENCE.search(message):
         if context_programme:
             query = _resolve_reference(message, context_programme)
         elif ask := _ask_which_program(db, written_in_thai(message)):
@@ -1191,7 +1229,14 @@ def prepare_answer(
     # มีตัวเลือกมากกว่าจึงได้คะแนนสูงกว่าเกือบเสมอ แม้จะเป็นเนื้อหาของสาขาอื่น — อาการเดียวกับ
     # ที่ทำให้ "สาขานี้" ได้คำตอบของเทคโนโลยีสารสนเทศ
     if history and query == message:
-        rewritten = _condense(connector, history, message, context_programme)
+        # ผู้ใช้เอ่ยชื่อหลักสูตรเอง: บอกขั้นเขียนคำถามใหม่ทั้งหลักสูตรที่คุยก่อนหน้าและหลักสูตรที่ระบุ แล้วทิ้งผลที่เปลี่ยนชุด
+        # หลักสูตรที่ผู้ใช้ระบุ ไม่ว่าคะแนนค้นหาจะสูงกว่าเท่าไร เพราะคะแนนต่างขอบเขตเทียบกันไม่ได้
+        # (docs/MKO_PHASE2_SHADOW_EVAL.md ข้อ 4)
+        explicit = explicit_programmes(db, message)
+        previous = context_programme or (_context_programme(db, history) if explicit else None)
+        rewritten = _condense(connector, history, message, previous, explicit=explicit)
+        if rewritten != message and not rewrite_keeps_explicit(db, message, rewritten):
+            rewritten = message
         if rewritten != message:
             # ถามต่อเรื่องค่าเทอมโดยไม่มีคำว่าค่าเทอม เช่น "ค่าเทอมเท่าไหร่" แล้วต่อด้วย "ของ comsci"
             # ขั้นค่าเทอม (0.5) ตรวจแค่ข้อความดิบจึงไม่เห็น เดิมข้อความนี้ไปค้นเอกสาร มคอ.2 ซึ่งไม่มีค่าเทอม
@@ -1227,6 +1272,9 @@ def prepare_answer(
     # ซึ่งต้องตอบคนละแบบ — เจอจริงกับหลักสูตรสาธารณสุขศาสตร์ที่คลังมีแต่ข้อมูลจากหน้าเว็บ
     # ไม่มีรายวิชา ผู้ใช้ถามถึงวิชาบังคับแล้วถูกตอบว่าถามนอกเรื่อง
     names_program = _names_a_program(db, interpreted) or _names_a_program(db, search_query)
+    # คำถามที่เอ่ยถึงหลายหลักสูตรใช้เกณฑ์เดียวกันทั้งด่านตรวจเอกสารและขั้นเขียนคำตอบ พร้อมสรุปหลักฐานรายด้านชุดเดียวกัน
+    comparison = _compares_programmes(db, interpreted)
+    evidence_note = describe_evidence(chunks) if comparison else ""
     if best_score < OFF_TOPIC_THRESHOLD and not names_program:
         # ต่ำขนาดนี้คือไม่มีอะไรในคลังใกล้เคียงเลย ตัดจบโดยไม่ต้องเสียเวลาเรียก LLM
         reply_text, status = out_of_scope, "out_of_scope"
@@ -1239,7 +1287,7 @@ def prepare_answer(
         and not _is_about_scope(connector, interpreted)
     ):
         reply_text, status = out_of_scope, "out_of_scope"
-    elif not _can_answer_from(connector, chunks, interpreted, comparison=_compares_programmes(db, interpreted)):
+    elif not _can_answer_from(connector, chunks, interpreted, comparison=comparison, note=evidence_note):
         reply_text, status = not_found, "not_found"
     else:
         status = "answered"
@@ -1247,12 +1295,13 @@ def prepare_answer(
     messages: list[LLMMessage] = []
     if status == "answered":
         reply_text = None
-        messages = [LLMMessage(role="system", content=CHAT_SYSTEM_PROMPT)]
+        system_prompt = f"{CHAT_SYSTEM_PROMPT}\n\n{CHAT_COMPARISON_RULES}" if comparison else CHAT_SYSTEM_PROMPT
+        messages = [LLMMessage(role="system", content=system_prompt)]
         for m in history:
             messages.append(LLMMessage(role=m.role, content=m.content))
         messages.append(
             # คำถามที่ตีความแล้วตัวเดียวกับที่ด่านตรวจใช้ ("สาขานี้" ถูกแทนด้วยชื่อสาขาแล้ว หรือคำถามที่เขียนใหม่)
-            LLMMessage(role="user", content=build_chat_prompt(_format_chunks(chunks), interpreted))
+            LLMMessage(role="user", content=build_chat_prompt(_with_note(evidence_note, _format_chunks(chunks)), interpreted))
         )
         citations = [
             ChatCitation(
diff --git a/eval/multi_program_scope_check.py b/eval/multi_program_scope_check.py
index 4192963..70d02ff 100644
--- a/eval/multi_program_scope_check.py
+++ b/eval/multi_program_scope_check.py
@@ -88,13 +88,15 @@ class ScopesChecks(unittest.TestCase):
 
 
 def chunk(owner, score, tag):
-    return SimpleNamespace(chunk_id=f"{owner.id}-{tag}", course_id=owner.id, course_title=owner.title, score=score)
+    return SimpleNamespace(chunk_id=f"{owner.id}-{tag}", course_id=owner.id, course_title=owner.title, score=score,
+                           content="เนื้อหาทดสอบ")
 
 
 class RetrieveChecks(unittest.TestCase):
+    # หลักฐานรายด้านของคำถามหลายหลักสูตรมาจาก comparison_evidence.programme_evidence (เดิม program_match.newest_core_chunks)
     def setUp(self):
         self.search_calls, self.core_calls = [], []
-        self._saved = (chat.search_similar_chunks, program_match.newest_core_chunks)
+        self._saved = (chat.search_similar_chunks, chat.programme_evidence)
 
         def fake_search(db, vector, top_k=8, course_ids=None):
             self.search_calls.append((top_k, course_ids))
@@ -109,11 +111,11 @@ class RetrieveChecks(unittest.TestCase):
             return [chunk(owner, score, "core-0"), chunk(owner, score, "core-1")]
 
         chat.search_similar_chunks = fake_search
-        program_match.newest_core_chunks = fake_core
+        chat.programme_evidence = fake_core
         self.connector = SimpleNamespace(embed=lambda text: [0.0])
 
     def tearDown(self):
-        chat.search_similar_chunks, program_match.newest_core_chunks = self._saved
+        chat.search_similar_chunks, chat.programme_evidence = self._saved
 
     def test_สองหลักสูตรได้แก่นของหลักสูตรนำหน้าชิ้นที่ค้นเจอของแต่ละหลักสูตร(self):
         chunks = chat._retrieve(FakeDb(), self.connector, "คณิตศาสตร์กับวิทยาศาสตร์เครื่องสำอางต่างกันอย่างไร")
diff --git a/llm/prompts.py b/llm/prompts.py
index eeada12..760c050 100644
--- a/llm/prompts.py
+++ b/llm/prompts.py
@@ -331,6 +331,11 @@ GROUNDING_COMPARISON_SYSTEM_PROMPT = """\
   ถือเป็นการตอบจากเนื้อหา ไม่ใช่การอนุมาน แม้เอกสารจะไม่ได้เขียนประโยคเปรียบเทียบไว้เอง
 - คำถามมีหลายส่วน และเนื้อหาตอบส่วนที่เป็นข้อเท็จจริงได้ ส่วนที่ขอให้เลือกหรือขอความเห็น
   ผู้ตอบจะใช้ข้อเท็จจริงเหล่านั้นประกอบ และบอกเองว่าส่วนไหนเอกสารไม่ได้ระบุ
+- เนื้อหามีข้อเท็จจริงของทุกหลักสูตรเพียงบางด้าน (เช่น มีวัตถุประสงค์ของทุกหลักสูตร แต่อาชีพมีของหลักสูตรเดียว)
+  ผู้ตอบจะเทียบเฉพาะด้านที่มีข้อเท็จจริงของทุกหลักสูตร และบอกว่าด้านใดเอกสารไม่ได้ระบุ
+- คำถามขอให้ตัดสินเชิงปริมาณหรือจัดอันดับระหว่างหลักสูตร (เช่น มากกว่า น้อยกว่า ที่สุด) และเนื้อหามีข้อเท็จจริง
+  ในเรื่องที่ถามของทุกหลักสูตร (เช่น รายวิชาที่เกี่ยวข้อง) แม้ไม่พอจะตัดสินอันดับได้ เพราะผู้ตอบจะยกข้อเท็จจริง
+  ของแต่ละหลักสูตรและบอกตรงๆ ว่ายังจัดอันดับจากเอกสารไม่ได้ ไม่ใช่ตัดสินแทน
 
 ถือว่าตอบไม่ได้ (false) เมื่อ:
 - ต้องใช้ความรู้นอกเหนือจากเนื้อหาที่ให้มา
@@ -343,6 +348,30 @@ GROUNDING_COMPARISON_SYSTEM_PROMPT = """\
 {"reason": "<หนึ่งถึงสองประโยค: ข้อเท็จจริงในเนื้อหาที่ใช้ตอบได้และมาจากหลักสูตรใด หรือขาดข้อมูลอะไร>", "can_answer": true หรือ false}
 """
 
+# ===========================================================================
+# กฎเพิ่มเติมของขั้นเขียนคำตอบสำหรับคำถามที่เอ่ยถึงหลายหลักสูตร — ต่อท้าย CHAT_SYSTEM_PROMPT เฉพาะคำถามแบบนี้
+#
+# เดิมขั้นเขียนคำตอบไม่มีเกณฑ์ของคำถามเปรียบเทียบเลย ด่านตรวจเอกสารให้ผ่านตาม GROUNDING_COMPARISON_SYSTEM_PROMPT แล้ว
+# แต่ขั้นเขียนคำตอบยังปฏิเสธเองว่า "ไม่พบข้อมูลเปรียบเทียบความแตกต่างระหว่างหลักสูตร" (docs/MKO_PHASE2_SHADOW_EVAL.md
+# ข้อ 5) กฎชุดนี้ใช้เกณฑ์เดียวกับด่านตรวจ คำถามหลักสูตรเดียวไม่ได้รับกฎนี้ พฤติกรรมของคำถามแบบนั้นจึงไม่เปลี่ยน
+# ===========================================================================
+CHAT_COMPARISON_RULES = """\
+กฎเพิ่มเติมสำหรับคำถามที่เอ่ยถึงหลายหลักสูตร (ใช้เกณฑ์เดียวกับผู้ตรวจเอกสาร):
+- หัวข้อของเนื้อหาแต่ละชิ้นบอกว่าเป็นของหลักสูตรใดและฉบับปีใด ส่วน "สรุปจากระบบ" ต้นเนื้อหาบอกว่าพบหัวข้อด้านใด
+  ของหลักสูตรใด ให้วางข้อเท็จจริงของแต่ละหลักสูตรเทียบกันได้ แม้เอกสารไม่ได้เขียนประโยคเปรียบเทียบไว้เอง
+  ห้ามตอบว่าไม่พบข้อมูลเพียงเพราะไม่มีเอกสารที่เปรียบเทียบหลักสูตรไว้
+- เทียบเฉพาะด้านที่เนื้อหามีข้อเท็จจริงของทุกหลักสูตร เช่น ปรัชญา วัตถุประสงค์ อาชีพ โครงสร้างหรือกลุ่มวิชา
+  ด้านที่มีข้อเท็จจริงเพียงบางหลักสูตร ให้บอกสั้นๆ ว่าเนื้อหาที่มีไม่ระบุด้านนั้นของหลักสูตรใด
+- ความแตกต่างหรือความเหมือนที่บอก ต้องมาจากข้อความในเนื้อหาของแต่ละหลักสูตรโดยตรง ห้ามสรุปความแตกต่าง
+  ที่เนื้อหาไม่ได้ระบุ และห้ามใช้ความรู้ทั่วไปเกี่ยวกับสาขาเหล่านั้น
+- ถ้าข้อเท็จจริงมาจากคนละฉบับปีกัน ทั้งภายในหลักสูตรเดียวหรือระหว่างหลักสูตร ให้ระบุปีของฉบับกำกับไว้
+- คำถามที่ขอให้ตัดสินเชิงปริมาณหรือจัดอันดับ (มากกว่า น้อยกว่า ที่สุด): ตัดสินได้เฉพาะเมื่อเนื้อหามีตัวเลขหรือรายการ
+  ที่ครบและเทียบกันได้ตรงๆ ถ้าไม่ถึงขั้นนั้น ให้บอกตรงๆ ก่อนว่ายังสรุปจากเอกสารที่มีไม่ได้ แล้วยกข้อเท็จจริงที่มี
+  ของแต่ละหลักสูตร (เช่น รายวิชาที่ปรากฏในเนื้อหา พร้อมบอกว่าเป็นเพียงบางส่วน) และบอกสั้นๆ ว่าการตัดสินต้องกำหนด
+  เกณฑ์ก่อน เช่น จำนวนวิชา หน่วยกิต วิชาบังคับหรือวิชาเลือก และปีของหลักสูตร ห้ามเดาหรือจัดอันดับเอง
+- จัดคำตอบเป็นหัวข้อย่อยตามด้านหรือตามหลักสูตร ความยาวเกินสามประโยคได้ แต่แต่ละหลักสูตรในแต่ละด้านไม่เกินสองประโยค
+"""
+
 # prompt สำหรับเขียนคำถามใหม่ให้สมบูรณ์ก่อนนำไปค้นหา (query condensation)
 #
 # จำเป็นเพราะคำถามต่อเนื่องมักอ้างถึงสิ่งที่พูดไปแล้ว เช่น "แล้วค่าเทอมล่ะ"
```
