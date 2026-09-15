# MKO Phase 2 — รายงาน controlled rollout ขึ้น production (shadow)

วันที่ 15 ก.ย. 2569 (01:31–01:43 UTC) · commit `a4201cc` · `STRUCTURED_ANSWERS=shadow`

**สถานะ: rollout สำเร็จ** — คำตอบที่ผู้ใช้เห็นยังมาจากระบบเดิม และคำตอบจากฐานข้อมูลถูกบันทึกเฉพาะใน `mko.shadow_answers`
ไม่ได้ตั้ง `on`, ไม่ได้เริ่ม Phase 3, ไม่ได้ merge งานอื่น

---

## 1. Backup

| รายการ | ค่า |
|---|---|
| ไฟล์ | `/home/ubuntu/backups/prod_pre_mko_phase2_20260915T013154Z.dump` |
| รูปแบบ | `pg_dump -Fc` ทั้งฐาน `course_advisor` (ฐาน 187 MB → ไฟล์ 49,952,371 bytes, สิทธิ์ 600) |
| SHA-256 | `ad584f38cdc67f573df85cc3fd725bf0f17192cab0ad75d4a3846beb29972196` (เก็บคู่กันใน `.dump.sha256`) |
| ตรวจ | `pg_dump` exit 0; `pg_restore -l` exit 0 อ่านสารบัญได้ 74 รายการ มีข้อมูลครบ 10 ตาราง public |

สำเนาเพิ่มเติมก่อน deploy ใน `~/backups/`
- `env.before_mko_phase2` (สิทธิ์ 600)
- `DEPLOYED_COMMIT.b78b3f8`, `ROLLBACK.txt.b78b3f8`
- `~/release-b78b3f8/docker-compose.prod.yml.deployed`

## 2. Migration

| ไฟล์ | ผล |
|---|---|
| `001_mko_structured.sql` | exit 0 — CREATE SCHEMA/TABLE/INDEX/VIEW/FUNCTION/TRIGGER ใน `mko` เท่านั้น |
| `002_mko_review_publish.sql` | exit 0 — CREATE TABLE/INDEX/VIEW ใน `mko` + GRANT |

- `mko.schema_migrations`: `001_mko_structured`, `002_mko_review_publish`
- วัตถุใน `mko`: 18 ตาราง, 6 view, 30 index
- log ไม่มี ALTER/DROP ของตาราง public (DROP ตัวเดียวคือ `DROP TRIGGER IF EXISTS` บน `mko.evidence` ซึ่งยังไม่มีอยู่)

## 3. Snapshot ก่อน/หลัง

| รายการ | ก่อน migration | หลัง migration | หลังโหลดข้อมูล mko |
|---|---|---|---|
| schemas | public | mko, public | mko, public |
| ตาราง public | 10 ตาราง | เหมือนเดิม | เหมือนเดิม |
| fingerprint คอลัมน์ / constraint / index / trigger ของ public | `d033c5f6…` / `a5dffe2b…` / `1743d1e6…` / 3 | เหมือนเดิม | เหมือนเดิม |
| courses | 24 (rowhash `-14299909628347055902`) | เหมือนเดิม | เหมือนเดิม |
| course_documents | 31 (rowhash `33001670800999705810`) | เหมือนเดิม | เหมือนเดิม |
| course_chunks (รวม embedding) | 9039 (rowhash `-530925850819360065410`) | เหมือนเดิม | เหมือนเดิม |
| users | 192 | 192 | 192 |
| chat_sessions / chat_messages / chat_answer_cache | 2910 / 5626 / 113 | เหมือนเดิม | เหมือนเดิม |
| recommendations / user_profiles / user_requirements | 53 / 11 / 10 | เหมือนเดิม | เหมือนเดิม |

- rowhash คือ `sum(hashtextextended(row::text))` ของทุกแถว ใช้ตรวจว่าเนื้อหาไม่เปลี่ยน ไม่ใช่แค่จำนวน
- **SHA ของ `pg_dump --schema-only --schema=public` ต่างกัน — ตรวจแล้วไม่ใช่การเปลี่ยน schema**
  - pg_dump 16.15 ใส่ token `\restrict` แบบสุ่มทุกครั้ง (dump สองครั้งติดกันโดยไม่มีอะไรเปลี่ยนก็ต่างกัน 4 บรรทัด)
  - บล็อก `CREATE TABLE public.courses` และ GRANT ของมันย้ายตำแหน่ง เพราะมี view ของ mko อ้างถึง แต่ข้อความเหมือนเดิมทุกตัวอักษร
  - เมื่อตัดบรรทัด token และเรียงบล็อก ได้ 61 บล็อก hash `91de5541…` ตรงกันทั้งก่อน หลัง และ dump ควบคุมสองครั้ง
- **หลัง deploy และ smoke test:** chat_sessions 2923 และ chat_messages 5652 เพิ่มขึ้น 13 session / 26 ข้อความ เท่ากับคำขอ smoke 13 ครั้งพอดี ส่วน chat_answer_cache 114 เพิ่ม 1 แถวจาก smoke รอบแรก ตารางอื่นไม่เปลี่ยน

## 4. ข้อมูล mko ที่โหลด

- **mapping:** `course_documents` (id, course_id, file_sha256, ชื่อไฟล์, จำนวนหน้า) และ `courses` (id, title, is_active) ของ local กับ production เหมือนกันทั้ง 31 + 24 แถว (ไฟล์เปรียบเทียบ sha256 `ad8aedc1…` เท่ากัน) ไม่มีเอกสารที่อ้างถึงแต่ไม่มีในฐาน
- **ไฟล์ข้อมูล:** `pg_dump --data-only --schema=mko` จาก local ไม่รวม `shadow_answers` (ผลเล่นซ้ำ 125 แถว) และ `schema_migrations`; sha256 `386a8703…` ตรวจซ้ำบน server ก่อนโหลด
- **โหลด:** `psql --single-transaction -v ON_ERROR_STOP=1` exit 0 (COPY 16 ตาราง, trigger ตรวจข้อความหลักฐานทำงานทุกแถว)
- **ตรวจหลังโหลด:** จำนวนแถวและ rowhash ของทั้ง 16 ตาราง mko บน production **ตรงกับ local ทุกตาราง**
  - document_pages 4129, evidence 787, field_values 403, list_items 294, …
- **publication ที่มีผล:** `92e34932-2863-4604-a5f6-4611fc6e9b51`, `verified_any`, parser `mko-phase1-2026.09.15` — ชุดเดียวกับที่ผ่านเทสต์ local และมีเพียงชุดเดียว
  - v_live_values 97 / v_live_list_items 31
  - สถานะรอบล่าสุด: candidate 186 / verified 167 / not_found 47 / needs_review 3
- **ที่มาและสิทธิ์:** published values ทั้ง 97 ค่าชี้ไปยังเอกสารที่ชื่อไฟล์ตรงกับ `course_documents`; `advisor_api` อ่าน `v_live_values` ได้ 97 แถว

## 5. Deploy

| รายการ | ค่า |
|---|---|
| commit | `a4201cc` (`a4201ccdb497f203b6871e8842883224e7a09581`) |
| image ใหม่ | `sha256:e3da1c0f1adb89f450e5e3fcff54c6179b86864a75332337239a4017542cd3ed` |
| เริ่มทำงาน | 2026-09-15T01:39:58Z, restarts 0 |
| image เดิม (rollback) | `course-advisor-system-backend:rollback-b78b3f8` = `sha256:bda50df1…` |
| `STRUCTURED_ANSWERS` | `.env` = `shadow`, ในคอนเทนเนอร์ = `shadow`, `configured_mode()` = `shadow` |

- **ก่อนคัดลอก:** backend + llm บน server 58 ไฟล์ตรงกับ `b78b3f8` และ compose ตรง (ไม่นับ CR) ไม่มีไฟล์แปลกปลอม
- **ในคอนเทนเนอร์:** backend + llm 61 ไฟล์ตรงกับ `a4201cc` ทุกไฟล์ ความต่างจาก `b78b3f8` มีเฉพาะไฟล์ Phase 2 (config, chat, curriculum_facts, structured_intent, structured_shadow) และ compose 2 บรรทัด ไม่มีงานค่าเทอมที่ค้างอยู่ใน repo หลัก
- **คอนเทนเนอร์อื่น:** recreate เฉพาะ backend (`--no-deps`); caddy, frontend, postgres, ollama ไม่ถูกแตะ
- **บันทึก deploy:** `~/DEPLOYED_COMMIT` อัปเดตแล้ว; `~/ROLLBACK.txt` เพิ่มขั้นตอนย้อนกลับของรอบนี้ไว้บนสุด

**พบระหว่างทาง:** archive ชุดแรกที่สร้างบน Windows มี CRLF (`core.autocrlf=true`) ตรวจพบจาก hash ก่อนใช้งาน จึงลบทิ้งและสร้างใหม่ด้วย `git -c core.autocrlf=false archive` ไฟล์ที่ deploy จริงเป็น LF ตรงกับ git

## 6. หลัง deploy

| ตรวจ | ผล |
|---|---|
| backend `/health` | `{"status":"ok"}` (พร้อมใน ~2 วินาที) |
| `/api/health`, หน้าเว็บ | 200, 200 |
| log backend ตั้งแต่เริ่ม | error/warning/traceback = **0** |
| shadow worker | ทำงาน: บันทึก 7 แถว latency 1–8 ms ไม่มี error |
| public tables | ไม่เปลี่ยน ยกเว้นแถวแชทจาก smoke test ตามจำนวนคำขอ |

## 7. Smoke test ผ่าน `/api/chat`

**จำนวนคำขอทั้งหมด 13 ครั้ง**
- ก่อน deploy 6 ครั้ง (01:39 UTC)
- หลัง deploy 6 ครั้ง (01:41 UTC)
- ถามซ้ำข้อ 6 อีก 1 ครั้งเพื่อวัดความแปรปรวนของโมเดล
- ไม่ได้รัน behaviour_check หรือชุดทดสอบอื่นกับ production

| # | คำถาม | HTTP ก่อน→หลัง | คำตอบที่ผู้ใช้เห็น |
|---|---|---|---|
| 1 | หลักสูตรวิทยาการคอมพิวเตอร์ต้องเรียนกี่หน่วยกิต | 200→200 | **เหมือนเดิมทุกตัวอักษร** |
| 2 | หลักสูตรการแพทย์แผนไทยประยุกต์ พ.ศ. 2560 ต้องเรียนทั้งหมดกี่หน่วยกิต | 200→200 | **เหมือนเดิมทุกตัวอักษร** |
| 3 | หลักสูตรเทคโนโลยีสารสนเทศมีวัตถุประสงค์อะไร | 200→200 | **เหมือนเดิมทุกตัวอักษร** |
| 4 | จบสาขาคณิตศาสตร์สามารถประกอบอาชีพอะไรได้บ้าง | 200→200 | **เหมือนเดิมทุกตัวอักษร** |
| 5 | วิทยาการคอมพิวเตอร์กับเทคโนโลยีสารสนเทศต่างกันอย่างไร | 200→200 | **เหมือนเดิมทุกตัวอักษร** |
| 6 | (ต่อจากข้อ 1) แล้วหลักสูตรคณิตศาสตร์ล่ะ | 200→200 | ถ้อยคำต่าง ตัวเลขเหมือนเดิม (124 และ 130) |

- **ข้อ 1–5:** หลัง deploy ตอบใน 0.0–0.5 วินาทีจากแคชคำตอบ แคชผูกกับรุ่นตรรกะที่ Phase 2 ไม่ได้เปลี่ยน จึงเป็นคำตอบเดียวกับที่ผู้ใช้ได้รับ
- **ข้อ 6** เป็นคำถามต่อเนื่อง ไม่ใช้แคช โมเดลเขียนใหม่ทุกครั้ง
  - ก่อน: "…ในเอกสารหลักสูตรมีระบุจำนวนหน่วยกิตรวมตลอดหลักสูตรไว้ 2 แบบ คือ ไม่น้อยกว่า 124 หน่วยกิต และไม่น้อยกว่า 130 หน่วยกิต ขึ้นอยู่กับปีพุทธศักราชของหลักสูตร"
  - หลัง: "…ต้องเรียนจำนวนหน่วยกิตรวมตลอดหลักสูตรไม่น้อยกว่า 124 ถึง 130 หน่วยกิต ขึ้นอยู่กับปีพุทธศักราชของหลักสูตร"
  - ถามซ้ำหลัง deploy: "…ไม่น้อยกว่า 124 ถึง 130 หน่วยกิต ขึ้นอยู่กับแผนปีพุทธศักราชของหลักสูตร" — ต่างจากรอบหลัง deploy เองด้วย
  - สรุป: เป็นความแปรปรวนของโมเดล ไม่ใช่ผลของ deploy เพราะ hook shadow ทำงานหลังได้คำตอบแล้ว (ยืนยันด้วยเทสต์ local ว่าคำตอบเหมือนกันทุกตัวอักษรไม่ว่าเปิดหรือปิด shadow) เนื้อหาตัวเลขไม่เปลี่ยน

## 8. ตัวอย่างคำตอบผู้ใช้ vs คำตอบ shadow

**จำนวนแถวใน `mko.shadow_answers` = 7**
- ตรงกับคำขอหลัง deploy 6 + ถามซ้ำ 1 และก่อน deploy = 0
- route structured 6 / RAG 1; ตอบได้ 5 / no_data 1
- ผลเทียบ: agree 5, not_compared 2

| คำถาม | ผู้ใช้เห็น (ระบบเดิม) | shadow (ฐานข้อมูล) | เทียบ |
|---|---|---|---|
| วิทยาการคอมพิวเตอร์กี่หน่วยกิต | "…ไม่น้อยกว่า 130 หน่วยกิต" | "(พ.ศ. 2566) และ (พ.ศ. 2561) มีจำนวนหน่วยกิตรวมตลอดหลักสูตร 130 หน่วยกิต — ที่มา: cs66.pdf หน้า 2; cs61.pdf หน้า 6" | agree |
| การแพทย์แผนไทยประยุกต์ พ.ศ. 2560 | "…149 หน่วยกิต" | "(พ.ศ. 2560) … 149 หน่วยกิต — ที่มา: attm.pdf หน้า 6" | agree |
| เทคโนโลยีสารสนเทศ วัตถุประสงค์ | รายการ 5 ข้อ | 5 ข้อตาม (พ.ศ. 2566) + "ยังไม่มีข้อมูลที่ผ่านการตรวจของ (พ.ศ. 2561)" — ที่มา: it66.pdf หน้า 13 | agree (ครอบคลุม 0.98–1.0) |
| คณิตศาสตร์ อาชีพ | รายการอาชีพจาก RAG | no_data — "ยังไม่มีข้อมูลที่เผยแพร่" | not_compared |
| วิทยาการคอมพิวเตอร์กับเทคโนโลยีสารสนเทศต่างกันอย่างไร | คำตอบเปรียบเทียบจาก RAG | route RAG (`no_supported_field`) ไม่คำนวณ | not_compared |
| แล้วหลักสูตรคณิตศาสตร์ล่ะ (ตีความเป็น "หลักสูตรคณิตศาสตร์ต้องเรียนกี่หน่วยกิต") | "…124 … 130 หน่วยกิต…" | "(พ.ศ. 2564) 130 หน่วยกิต + ยังไม่มีข้อมูลที่ผ่านการตรวจของ (พ.ศ. 2569) — ที่มา: ma64.pdf หน้า 6" | agree (expected [130], พบ [124, 130]) |

- แถวสุดท้ายยืนยันว่าคำถามต่อเนื่องใช้คำถามที่ตีความแล้ว (`has_history = true`)
- **ข้อควรระวังในการอ่านผล:** แถวสุดท้ายได้ `agree` ทั้งที่คำตอบผู้ใช้มีทั้ง 124 และ 130 เพราะรอบนี้ตัวเลขทั้งสองอยู่ในประโยคเดียวกัน ("124 ถึง 130 หน่วยกิต") และกฎนับเฉพาะเลขที่ตามด้วย "หน่วยกิต" ทันที ในการเล่นซ้ำ local ประโยคลักษณะคล้ายกันได้ `partial` จึงต้องอ่านคู่คำตอบประกอบเสมอ

## 9. Errors / warnings

- **backend:** error/warning/traceback ตั้งแต่เริ่มคอนเทนเนอร์ = 0, restarts = 0
- **migration / โหลดข้อมูล:** ไม่มี error มี NOTICE เดียวจาก `DROP TRIGGER IF EXISTS` (ปกติ)
- **ทุกข้อที่ต้องตรวจ:** ไม่พบคำตอบผู้ใช้เปลี่ยนผิดคาด จึงไม่ได้ปิด shadow หรือ rollback

## 10. ความพร้อมในการย้อนกลับ

**ปิด shadow อย่างเดียว** (ไม่กี่วินาที)
```
cd ~/course-advisor-system
sed -i 's/^STRUCTURED_ANSWERS=.*/STRUCTURED_ANSWERS=off/' .env
docker compose -f docker-compose.prod.yml up -d --no-deps backend
```

**กลับ `b78b3f8` ทั้งหมด:** ขั้นตอนเต็มอยู่ใน `~/ROLLBACK.txt`
- ใช้โค้ดจาก `~/release-b78b3f8` (ตรวจแล้ว 58 ไฟล์ตรง `b78b3f8`)
- ลบไฟล์ใหม่ 3 ไฟล์
- ใช้ compose เดิมจาก `~/release-b78b3f8/docker-compose.prod.yml.deployed`
- tag image `rollback-b78b3f8` (`bda50df1…`) เป็น `latest` แล้ว `up -d --no-build --no-deps backend`

**ฐานข้อมูล:** schema `mko` เป็นส่วนเพิ่มที่ `b78b3f8` ไม่ได้อ่าน ปล่อยไว้ได้ backup เต็มอยู่ที่ข้อ 1

## 11. สิ่งที่ยังไม่ได้ทำ (ตามที่ยังไม่อนุมัติ)

- `STRUCTURED_ANSWERS=on`
- Phase 3
- การเปลี่ยนคำตอบที่ผู้ใช้เห็น
- merge งานอื่น
- push branch

**ไฟล์รายงานนี้** (`docs/MKO_PHASE2_ROLLOUT_REPORT.md` ใน worktree `mko-phase2`) ยังไม่ commit

**ไฟล์ชั่วคราวบน server ที่ยังอยู่:** `/tmp/*manifest*.sha256`, `/tmp/mko_snapshot.sql`, `/tmp/deploy_a4201cc.sh`, `/tmp/verify_a4201cc.sh`, `/tmp/ctl1.sql`, `/tmp/ctl2.sql`, `~/release-a4201cc-lf(.tar.gz)` — ยังไม่ลบ
