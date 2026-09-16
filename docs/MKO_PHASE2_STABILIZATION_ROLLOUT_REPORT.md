# MKO Phase 2 Stabilization — Controlled Shadow Deployment

**สรุป: deploy สำเร็จ smoke test ผ่าน 7/7 ไม่พบ regression จึงไม่ได้ rollback**
- production คงไว้ที่ `STRUCTURED_ANSWERS=shadow`
- ไม่ได้เปิด `on` ไม่ได้เปลี่ยน routing ที่ผู้ใช้เห็นไปใช้ structured answer
- ไม่ได้เริ่ม Phase 3 ไม่ได้ push branch

เวลาในรายงานเป็น UTC (วันที่ 2026-09-15 UTC = คืน 15 ต่อเช้า 16 ก.ย. เวลาไทย)

## 1. ก่อน deploy

| ขั้น | ผล |
|---|---|
| git status / diff | worktree `mko-phase2` มีเฉพาะงาน stabilization + รายงาน 4 ฉบับ ไม่มีงานค่าเทอม (งานนั้นอยู่ใน repo หลัก ไม่ได้อยู่ใน worktree นี้) |
| test suite ครั้งสุดท้าย | 15 suites **249 tests OK, 0 fail** (local DB ที่ `course_chunks` ตรง production, ไม่รัน behaviour_check) |
| secret scan | pattern (Gemini/OpenAI key, private key, password/token, DB URL ที่มีรหัสผ่าน) = ไม่พบ; เทียบค่าจริง `GEMINI_API_KEY`, `JWT_SECRET`, รหัสผ่าน DB จาก `.env` production แบบไม่พิมพ์ค่า = ไม่พบในทุกไฟล์ที่ commit |
| commit | ดูข้อ 2 — blob ที่ commit เป็น LF ทั้งหมด (CR = 0) |
| ต้องใช้ schema ใหม่ไหม | **ไม่ต้อง** โค้ดใหม่อ่านเฉพาะ `course_chunks` และ `courses` ที่มีอยู่แล้ว จึงไม่ได้รัน migration และไม่ได้แก้ข้อมูลใน production DB |

## 2. Commit

| รายการ | ค่า |
|---|---|
| commit | `1493db2` (`1493db2e3d3d7090dd01c088a53b65c0046aec5e`) บน branch `mko-phase2` ต่อจาก `9368d16` |
| ข้อความ | fix(mko): keep follow-up programme and year, and decide comparison evidence in code (Phase 2 stabilization) |
| ไฟล์ (12) | `answer_cache.py`, `chat.py`, `comparison_evidence.py` (ใหม่), `follow_up.py` (ใหม่), `llm/prompts.py`, `eval/comparison_evidence_check.py` (ใหม่), `eval/follow_up_scope_check.py` (ใหม่), `eval/multi_program_scope_check.py`, รายงาน `MKO_PHASE2_SHADOW_EVAL.md`, `MKO_PHASE2_STABILIZATION_REPORT.md`, `MKO_PHASE2_MODEL_VALIDATION.md`, `MKO_PHASE2_GATE_DETERMINISM_REPORT.md` |
| ไฟล์ที่ deploy จริง (backend + llm) | ต่างจาก `a4201cc` **5 ไฟล์**: `answer_cache.py`, `chat.py`, `comparison_evidence.py`, `follow_up.py`, `llm/prompts.py` ; `docker-compose.prod.yml` ไม่เปลี่ยน |

## 3. Backup

| รายการ | ค่า |
|---|---|
| ไฟล์ | `~/backups/prod_pre_mko_stabilization_20260915T183952Z.dump` (สิทธิ์ 600) |
| รูปแบบ | `pg_dump -Fc` ทั้งฐาน (ฐาน 201 MB → ไฟล์ 53,606,554 bytes) |
| SHA-256 | `ae3621054b48ec926a4fe4b3f373244898367270abd4c4e472276f6537aa7e85` (เก็บคู่ใน `.dump.sha256`, `sha256sum -c` OK) |
| ตรวจ | `pg_dump` exit 0; `pg_restore -l` อ่านสารบัญได้ 231 รายการ มีข้อมูลตาราง public 10 ตาราง และ mko 18 ตาราง (รวม `shadow_answers`) |
| ขณะ backup | course_chunks 9039, chat_messages 5714, mko.shadow_answers 38 |

backup เดิมของ Phase 2 (`prod_pre_mko_phase2_20260915T013154Z.dump`) ยังอยู่ ไม่ได้ลบ

## 4. Rollback point

| รายการ | ค่า |
|---|---|
| commit ก่อนหน้า | `a4201cc` |
| image ก่อนหน้า | `sha256:e3da1c0f1adb89f450e5e3fcff54c6179b86864a75332337239a4017542cd3ed` tag เป็น `course-advisor-system-backend:rollback-a4201cc` |
| โค้ดก่อนหน้า | `~/release-a4201cc` (backend + llm + `docker-compose.prod.yml.deployed`) ตรวจ hash แล้ว **62 ไฟล์ตรง `a4201cc`** |
| บันทึกเดิม | `~/backups/DEPLOYED_COMMIT.a4201cc`, `~/backups/ROLLBACK.txt.a4201cc`, `~/backups/env.before_mko_stabilization` (600) |
| ก่อนคัดลอก | backend + llm + compose บน server 62 ไฟล์ตรง `a4201cc` ทุกไฟล์ ไม่มีไฟล์แปลกปลอม |
| `~/ROLLBACK.txt` | เพิ่มขั้นตอนย้อนกลับของรอบนี้ไว้บนสุด |
| rollback เก่ากว่า | `rollback-b78b3f8`, `~/release-b78b3f8` ยังอยู่ครบ |

**ปิด shadow อย่างเดียว** (คงโค้ดใหม่)
```
cd ~/course-advisor-system
sed -i 's/^STRUCTURED_ANSWERS=.*/STRUCTURED_ANSWERS=off/' .env
docker compose -f docker-compose.prod.yml up -d --no-deps backend
```

**กลับ `a4201cc` ทั้งหมด**
```
cd ~/course-advisor-system
cp -a ~/release-a4201cc/backend/. backend/ && cp -a ~/release-a4201cc/llm/. llm/
rm -f backend/app/services/comparison_evidence.py backend/app/services/follow_up.py
cp -p ~/release-a4201cc/docker-compose.prod.yml.deployed docker-compose.prod.yml
docker tag course-advisor-system-backend:rollback-a4201cc course-advisor-system-backend:latest
docker compose -f docker-compose.prod.yml up -d --no-build --no-deps backend
# ตรวจ: docker inspect -f '{{.Image}}' course-advisor-system-backend-1 -> sha256:e3da1c0f1adb...
```
- แคช: `_LOGIC_VERSION` กลับเป็น "31" คำตอบที่แคชไว้ใต้ "33" จะไม่ถูกหยิบใช้เอง
- ฐานข้อมูล: รอบนี้ไม่ได้เปลี่ยน schema หรือข้อมูล จึงไม่ต้อง restore

## 5. Deploy

| รายการ | ค่า |
|---|---|
| archive | `git -c core.autocrlf=false archive 1493db2 backend llm` → `~/release-1493db2.tar.gz` SHA-256 `a700b8384afea531f99492174abeea016b619fd79a02bd50e12c426220d9ff71` (ตรงกันทั้ง local และ server), 63 ไฟล์ CR = 0 |
| ตรวจก่อน build | `.env` = shadow, compose hash ไม่เปลี่ยน, backup SHA ตรง, rollback tag มีอยู่ |
| หลังคัดลอก | backend + llm บน server 63 ไฟล์ตรง `1493db2` |
| build / up | `docker compose build backend` แล้ว `up -d --no-deps backend` (log: `~/backups/deploy_1493db2_20260915T185621Z.log`) |
| image ใหม่ | `sha256:23bd7aa465af5c08506dfa6a8b132840758b38ce93f84c52397c8bc902240647` |
| เริ่มทำงาน | 2026-09-15T18:56:22Z |
| ในคอนเทนเนอร์ | backend + llm 63 ไฟล์ตรง `1493db2`, `_LOGIC_VERSION = "33"`, `STRUCTURED_ANSWERS=shadow` |
| คอนเทนเนอร์อื่น | caddy, frontend, postgres, ollama, db-viewer ไม่ถูกแตะ (uptime เดิม) |
| `~/DEPLOYED_COMMIT` | commit=1493db2, image ใหม่, previous_commit=a4201cc, rollback tag, backup + SHA |

## 6. Production health

| ตรวจ | ผล |
|---|---|
| backend `/health` ในคอนเทนเนอร์ | `{"status":"ok"}` ภายใน ~2 วินาทีหลังเริ่ม |
| `https://stpnru-advisor.duckdns.org/api/health` | 200 `{"status":"ok"}` |
| หน้าเว็บ `/` | 200 |
| restart count | **0** |
| log backend ตั้งแต่เริ่ม | error / warning / traceback / exception = **0** ; POST chat 10 ครั้ง = 200 OK ทั้งหมด |
| public tables | courses 24, course_chunks 9039, course_documents 31 **ไม่เปลี่ยน**; chat_messages +20 (= 10 คำขอ × 2 ข้อความ) |

## 7. Smoke test (หน้า production ผ่าน `/api/chat`)

**คำขอทั้งหมด 10 ครั้ง** (7 cases, 3 cases มีคำถามต่อเนื่อง) เวลา 18:57:14–18:58:53Z เว้นระยะ 8 วินาที
คำถามต่อเนื่องส่งประวัติแบบเดียวกับหน้าเว็บ ไม่ได้รัน behaviour_check หรือชุดทดสอบอื่นกับ production
ตัวเลขในคำตอบตรวจกับ `course_chunks` (สำเนาเดียวกับ production) แล้วถูกต้องทุกตัว

| # | คำถาม | HTTP / เวลา | คำตอบที่ผู้ใช้เห็น (ย่อ) | ผล |
|---|---|---|---|---|
| 1a | สาขาวิทยาการคอมพิวเตอร์เรียนกี่หน่วยกิต | 200 / 2.7s | ไม่น้อยกว่า 130 หน่วยกิต | PASS |
| 1b | → แล้วคณิตศาสตร์ล่ะ | 200 / 3.4s | คณิตศาสตร์ 130 (พ.ศ. 2564) และ 124 (พ.ศ. 2569) — ตีความเป็น "สาขาคณิตศาสตร์เรียนกี่หน่วยกิต" | **PASS** คง intent หน่วยกิตรวม เปลี่ยนเป็นคณิตศาสตร์ |
| 2a | หลักสูตรเทคโนโลยีสารสนเทศเรียนกี่หน่วยกิต | 200 / 2.8s | 130 (พ.ศ. 2566), 127 (พ.ศ. 2561) | PASS |
| 2b | → แล้ววิทยาการคอมพิวเตอร์ล่ะ | 200 / 3.4s | 130 ทั้ง พ.ศ. 2566 และ 2561 — ตีความเป็น "หลักสูตรวิทยาการคอมพิวเตอร์เรียนกี่หน่วยกิต" | **PASS** |
| 3a | หลักสูตรคณิตศาสตร์ พ.ศ. 2569 เรียนกี่หน่วยกิต | 200 / 2.9s | 124 หน่วยกิต (พ.ศ. 2569) | PASS |
| 3b | → แล้ว พ.ศ. 2564 ล่ะ | 200 / 3.5s | 130 หน่วยกิต (พ.ศ. 2564) — ตีความเป็น "หลักสูตรคณิตศาสตร์ พ.ศ. 2564 เรียนกี่หน่วยกิต" | **PASS** คงหลักสูตรและ intent เปลี่ยนเฉพาะปี |
| 4 | วิทยาการคอมพิวเตอร์กับเทคโนโลยีสารสนเทศต่างกันอย่างไร | 200 / 2.6s | เทียบปรัชญาของทั้งสองหลักสูตร พ.ศ. 2566 | PASS |
| 5 | วิทยาการคอมพิวเตอร์กับคอมพิวเตอร์แอนิเมชันและมัลติมีเดียต่างกันอย่างไร | 200 / 3.1s | CS (พ.ศ. 2566) 130 หน่วยกิต + ปรัชญา / Animation (พ.ศ. 2569) 127 หน่วยกิต + ปรัชญา | PASS ระบุปีครบ |
| 6 | วิทยาการคอมพิวเตอร์กับเทคโนโลยีสารสนเทศ สาขาไหนเรียนเขียนโปรแกรมมากกว่ากัน | 200 / 2.9s | "ยังสรุปจากเอกสารที่มีไม่ได้ว่าหลักสูตรใดเน้นการเขียนโปรแกรมมากกว่ากัน" + CS 2566 กลุ่มซอฟต์แวร์ 24 หน่วยกิต / IT 2566 15 หน่วยกิต + เกณฑ์ (หน่วยกิตกลุ่มวิชา, จำนวนรายวิชา, ปีหลักสูตร) | **PASS** ไม่ฟันธง แสดงข้อเท็จจริงทั้งสอง บอกเกณฑ์ |
| 7 | ทีมลิเวอร์พูลเป็นยังไงบ้าง | 200 / 1.8s | ปฏิเสธ ตอบได้เฉพาะเรื่องหลักสูตร | PASS (out_of_scope) |

**ตัวเลขที่ตรวจกับเอกสาร:**
- วิทยาการคอมพิวเตอร์: 2566 130 (หน้า 2), 2561 130
- เทคโนโลยีสารสนเทศ: 2566 130 (หน้า 5), 2561 127 (หน้า 6)
- คณิตศาสตร์: 2564 130 (หน้า 6), 2569 124 (หน้า 1)
- คอมพิวเตอร์แอนิเมชันและมัลติมีเดีย: 2569 127 (หน้า 1)
- ข้อ 6: 24 / 15 หน่วยกิต ตรวจแล้วในรอบ model validation (CS 2566 หน้า 40, IT 2566 หน้า 1)

## 8. Shadow status

- `.env` = `shadow`, ในคอนเทนเนอร์ = `shadow`
- `mko.shadow_answers` บันทึกได้: +10 แถว (38 → 48) ตรงกับคำขอ smoke 10 ครั้ง ไม่มีแถวอื่นในช่วงเวลานั้น
  - latency 1–6 ms
  - คำตอบที่ผู้ใช้เห็นยังมาจาก RAG ทุกข้อ (`served_status` ตามระบบเดิม) — shadow ไม่ได้เปลี่ยนคำตอบ
- คำถามต่อเนื่องบันทึก `has_history = true` และ `interpreted_question` เป็นคำถามที่เปลี่ยนหลักสูตร/ปีแล้ว (ยืนยันว่า Step 0.85 ทำงานบน production)

| คำถาม | route | structured | เทียบกับคำตอบผู้ใช้ |
|---|---|---|---|
| 1a CS กี่หน่วยกิต | structured | answered 130 (2566, 2561) | agree |
| 1b → คณิตศาสตร์ | structured | answered 130 (2564) + "ยังไม่มีข้อมูลที่ผ่านการตรวจของ พ.ศ. 2569" | **partial** (expected [130], ผู้ใช้ได้ [124, 130]) |
| 2a IT กี่หน่วยกิต | structured | answered 130 (2566), 127 (2561) | agree |
| 2b → CS | structured | answered 130 | agree |
| 3a คณิตศาสตร์ 2569 | structured | no_data | not_compared |
| 3b → 2564 | structured | answered 130 (2564) | agree |
| 4, 5, 6 เปรียบเทียบ | rag (`no_supported_field`) | not_applicable | not_compared |
| 7 out-of-scope | rag (`no_supported_field`) | not_applicable | not_compared |

สรุป shadow รอบนี้:
- **route:** structured 6 / rag 4
- **structured answered:** 5 / no_data 1
- **เทียบ:** agree 4 / partial 1 / not_compared 5

**partial ของข้อ 1b ไม่ใช่ความผิดของคำตอบผู้ใช้:**
- คำตอบผู้ใช้ (124 สำหรับ 2569, 130 สำหรับ 2564) ตรงเอกสารทั้งคู่
- ข้อมูล structured ยังไม่มีค่าที่ผ่านการตรวจของคณิตศาสตร์ พ.ศ. 2569 จึงคาดไว้แค่ [130]
- no_data ของข้อ 3a มาจากสาเหตุเดียวกัน

## 9. สิ่งที่ยืนยันว่าไม่ได้ทำ

- `STRUCTURED_ANSWERS=on`
- Phase 3
- เปลี่ยน routing ที่ผู้ใช้เห็นไปใช้ structured answer
- migration / แก้ข้อมูลใน production DB
- แก้ feature อื่น / รวมงานค่าเทอม
- push branch
- behaviour_check หรือยิงทดสอบจำนวนมาก
- แก้สดบน production

## 10. Known limitations

1. **ข้อมูล structured ยังไม่ครบ**
   - เช่น คณิตศาสตร์ พ.ศ. 2569 ยังไม่มีค่าหน่วยกิตที่ผ่านการตรวจ ทำให้ shadow ได้ no_data / partial
   - ต้องเติมก่อนพิจารณา `on`
2. **คำถามเปรียบเทียบหลายหลักสูตรใน shadow ยัง route เป็น RAG** (`no_supported_field`) จึงยังไม่มีผลเทียบสำหรับคำถามแบบข้อ 4–6
3. **ด่านตรวจของคำถามเปรียบเทียบ**
   - ตัดสินด้วยโค้ดเฉพาะเมื่อพบเรื่องที่ถามในเนื้อหาของทุกหลักสูตร
   - กรณีที่ตัดสินไม่ได้ (คำพ้องความหมาย, เรื่องที่ถามสั้นเกิน) ยังใช้ LLM gate ซึ่งอาจไม่นิ่ง
4. **การไม่จัดอันดับเมื่อหลักฐานไม่พอยังอาศัยกฎของขั้นเขียนคำตอบ** ซึ่งเป็นโมเดล ไม่ได้รับประกันด้วยโค้ด บน production ข้อ 6 ทำตามถูกต้อง 1/1 และ local 6/6
5. **ความลึกของคำตอบเปรียบเทียบต่างกันแต่ละครั้ง** เช่น ข้อ 4 รอบนี้เทียบเฉพาะปรัชญา ขณะที่รอบ validation เทียบโครงสร้างด้วย และโมเดลอาจสะกดคำผิด (พบใน validation 2 จุด)
6. **ตัวกรองสารบัญเดิม** อาจตัดตารางรายวิชาที่มีตัวเลขหนาแน่นออกจากหลักฐาน
7. **แคช:** `_LOGIC_VERSION = "33"` คำถามเดิมที่เคยแคชไว้ใต้ "31" จะถูกคำนวณใหม่ครั้งแรก ทำให้ครั้งแรกช้ากว่าเดิมเล็กน้อยและใช้โควตาโมเดลเพิ่ม
8. **ผล smoke test เป็นตัวอย่างเดียวต่อข้อ** ส่วนที่เป็นโมเดลควรดูจาก shadow / การใช้งานจริงต่อไป

## 11. ไฟล์ที่เหลืออยู่

**บน server (ยังไม่ลบ):**
- `~/release-1493db2` และ `~/release-1493db2.tar.gz` — โค้ดที่ deploy อยู่
- `/tmp/release_a4201cc.manifest`, `/tmp/r1493db2.manifest`, `/tmp/server_after_copy.manifest`, `/tmp/container.manifest`

**ใน repo:** รายงานนี้ (`docs/MKO_PHASE2_STABILIZATION_ROLLOUT_REPORT.md` ใน worktree `mko-phase2`) **ยังไม่ commit**
