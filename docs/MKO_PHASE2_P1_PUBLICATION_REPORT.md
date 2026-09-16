# MKO Phase 2 — P1 Controlled Publication

**สรุป:** สร้าง publication ใหม่ด้วยนโยบายเดิม `verified_any` สำเร็จใน transaction เดียว
- ค่าที่เข้า live เพิ่มคือ 4 รายการที่ผ่าน human review รอบ P1 เท่านั้น
- ค่าเดิมจาก publication ก่อนหน้าอยู่ครบทุกค่า
- cs66_brief (rejected) และ Math 2564 careers (candidate) ไม่เข้า live
- **ผู้ใช้ยังได้คำตอบจากระบบเดิม** เพราะ `STRUCTURED_ANSWERS=shadow`
- ไม่ได้ deploy ไม่ได้แก้ code/extraction ไม่ได้เปลี่ยน policy ไม่ได้ commit/push

เวลาเป็น UTC

---

## 1. Publication

| รายการ | ค่า |
|---|---|
| previous publication id | `92e34932-2863-4604-a5f6-4611fc6e9b51` (2026-09-14 22:45:59Z, by `local-phase2`) |
| **new publication id** | **`9b382588-db00-4e80-9935-953fc4559ef7`** (2026-09-15 23:32:20Z) |
| policy | `verified_any` (เดิม ไม่เปลี่ยน) |
| published_by | `project-owner` — identifier เดียวกับที่อนุมัติให้ใช้ในรอบ human review (`mko.publications.published_by` เป็นข้อความอิสระ ไม่มีทะเบียนผู้ใช้ให้ต้องอ้างอิง) |
| parser_version | `mko-phase1-2026.09.15` (เท่าเดิม) |
| conflicts | ไม่มี |
| summary | courses 21 · values_by_field: total_credits 21, edition_year 20, revision_type 20, program_name_th 7, program_name_en 7, degree_abbr_th 7, degree_abbr_en 7, degree_level 7, degree_name_th 1, degree_name_en 1 · list_items_by_type: objective 35, career 18 · lists_by_type: objective 7, career 2 · values_reviewed_by: auto 97, human 1 |

**publication เดิมยังอยู่ในฐานข้อมูล** (ไม่ได้ลบ) — `v_live_*` ชี้ไปที่ publication ล่าสุดตาม design

---

## 2. Before / after live counts

| รายการ | ก่อน | หลัง |
|---|---|---|
| `mko.v_live_values` | 97 | **98** |
| `mko.v_live_list_items` | 31 | **53** |
| `mko.publications` | 1 | 2 |
| `mko.curricula` | published 20 / draft 4 | published 21 / draft 3 |
| live facts ที่ยืนยันโดยคน | 0 | **1 ค่า + 22 ข้อรายการ** |

---

## 3. ค่าที่เพิ่มเข้า live (ตรงกับที่อนุมัติทุกรายการ)

| หลักสูตร / ฉบับ | field | ค่า | source | หน้า | reviewed_by |
|---|---|---|---|---|---|
| คณิตศาสตร์ 2569 | total_credits | **124** | ma69.pdf | 1 | human:project-owner |
| วิทยาการคอมพิวเตอร์ 2566 | careers | 9 ข้อ | cs66.pdf | 3 | human:project-owner |
| วิทยาการคอมพิวเตอร์ 2566 | objectives | 4 ข้อ | cs66.pdf | 11 | human:project-owner |
| เทคโนโลยีสารสนเทศ 2566 | careers | 9 ข้อ | it66.pdf | 6 | human:project-owner |

**ตรวจก่อน COMMIT (publication preview จากการรัน `publish()` จริงบนข้อมูลชุดเดียวกัน):**
- ค่าที่เพิ่ม = 4 รายการข้างต้นเท่านั้น (values +1 แถว, list items +22 แถว)
- ไม่มีค่าใดของ publication เดิมหายไป
- conflicts ว่าง
- preview ตรงกับผลจริงทุกแถว (md5 ของ published_values `b8c656a0…` และ published_list_items `4da2d9d8…` ถูกตรวจใน transaction ก่อน COMMIT)

---

## 4. ตรวจหลัง publish

| ข้อ | ผล |
|---|---|
| publication ใหม่เป็น current | ✔ `v_live_publication` = `9b382588…` |
| v_live เพิ่มเฉพาะที่คาด | ✔ values ใหม่ 1 แถว (คณิตศาสตร์ 2569), list items ใหม่ 22 แถว (CS 2566 career 9 + objective 4, IT 2566 career 9) |
| ค่าเดิมยังอยู่ | ✔ ค่าจาก publication เดิมที่หายไปจาก live = **0 แถว** (values 0, list items 0) |
| ไม่มี candidate / needs_review / rejected หลุดเข้า | ✔ แถว live ทุกแถว (98 values + 53 items) ผูกกับแถวต้นทางสถานะ `verified` ทั้งหมด |
| cs66_brief.pdf | ✔ 0 แถวใน live |
| Math 2564 careers | ✔ 0 แถวใน live (ยัง candidate) |
| CS 2566 objectives | ✔ มาจาก `cs66.pdf` ไฟล์เดียว 4 ข้อ |
| ไม่มี cross-edition mixing | ✔ แถว live ที่ course ไม่ตรงกับเจ้าของเอกสาร = 0 ทั้งสองตาราง |
| curricula | ✔ เปลี่ยนสถานะเฉพาะคณิตศาสตร์ 2569 (draft → published) |

**หมายเหตุเรื่อง curricula:** ขั้น publish ตาม design อัปเดต `status/published_at/updated_at` ของทุกหลักสูตรที่มีค่าใน publication (21 แถว)
- เปลี่ยน **สถานะ** จริงแถวเดียว (คณิตศาสตร์ 2569)
- อีก 20 แถวเป็นการรีเฟรช timestamp ของหลักสูตรที่ published อยู่แล้ว
- คอลัมน์นี้ backend ไม่ได้ใช้ตอบคำถาม (อ่านเฉพาะ `v_live_*`)

### 4.1 ตรวจ structured service โดยตรง (อ่านอย่างเดียว ในคอนเทนเนอร์ backend)

| ข้อ | คำถาม | ผล |
|---|---|---|
| 1 | คณิตศาสตร์ พ.ศ. 2569 กี่หน่วยกิต | answered **124** · ที่มา ma69.pdf หน้า 1 · reviewed_by human:project-owner |
| 2 | วิทยาการคอมพิวเตอร์ อาชีพ | answered 9 ข้อ · ที่มา cs66.pdf หน้า 3 · แจ้งว่า ฉบับ 2561 ยังไม่มีข้อมูลที่ผ่านการตรวจ |
| 3 | เทคโนโลยีสารสนเทศ อาชีพ | answered 9 ข้อ · ที่มา it66.pdf หน้า 6 · แจ้งว่า ฉบับ 2561 ยังไม่มีข้อมูล |
| 4 | วิทยาการคอมพิวเตอร์ วัตถุประสงค์ | answered 4 ข้อ · ที่มา **cs66.pdf หน้า 11** เท่านั้น (ไม่มีข้อความจากใบสรุป) |
| 5 | คณิตศาสตร์ อาชีพ (ไม่ระบุปี) | **no_data** "ยังไม่มีข้อมูลที่เผยแพร่" |
| 6 | คณิตศาสตร์ พ.ศ. 2564 อาชีพ | **no_data** — ยืนยันว่า Math 2564 careers ไม่ได้ถูกใช้เป็นค่าที่เผยแพร่ |

ทุกข้อที่ answered อ้าง `publication_id = 9b382588…`

---

## 5. Shadow validation (5 คำขอผ่าน `/api/chat`)

ส่งจริง 5 ครั้ง เว้นระยะ 8 วินาที เวลา 23:42:23–23:43:38Z · ไม่ได้รัน behaviour_check และไม่มี batch test

| ข้อ | คำถาม | HTTP / เวลา | structured (shadow) | comparison | คำตอบที่ผู้ใช้เห็น |
|---|---|---|---|---|---|
| A | หลักสูตรคณิตศาสตร์ พ.ศ. 2569 เรียนกี่หน่วยกิต | 200 / 0.4s | **answered 124** · ma69.pdf · human:project-owner | **agree** (expected [124], พบ [124]) | ไม่น้อยกว่า 124 หน่วยกิต (จากระบบเดิม) |
| B | สาขาวิทยาการคอมพิวเตอร์จบไปทำอาชีพอะไรได้บ้าง | 200 / 10.4s | **answered 9 ข้อ** · cs66.pdf | **agree** (covered 9/9) | รายการอาชีพ 9 ข้อ ตรงกับที่เผยแพร่ |
| C | สาขาเทคโนโลยีสารสนเทศจบไปทำอาชีพอะไรได้บ้าง | 200 / 14.9s | **answered 9 ข้อ** · it66.pdf | **agree** (covered 9/9) | รายการอาชีพ 9 ข้อ |
| D | หลักสูตรวิทยาการคอมพิวเตอร์มีวัตถุประสงค์อะไร | 200 / 17.1s | **answered 4 ข้อ** · cs66.pdf | **partial** (covered 2/4, coverage 0.79 / 0.42 / 0.65 / 0.37) | ระบบเดิมสรุปวัตถุประสงค์เป็นย่อหน้าเดียว ไม่ได้ไล่ทั้ง 4 ข้อ |
| E | หลักสูตรคณิตศาสตร์จบไปทำอาชีพอะไรได้บ้าง | 200 / 12.0s | **no_data** | not_compared | ระบบเดิมตอบรายการอาชีพจากเอกสาร (RAG) ตามปกติ |

- **บันทึกครบ:** `mko.shadow_answers` เพิ่ม 5 แถว (48 → 53) ไม่มีแถวอื่นแทรกในช่วงเวลานั้น
- **publication ที่อ้างอิง:** แถวที่ answered ทั้ง 4 อ้าง `9b382588…` (แถว no_data ไม่มี publication)
- **latency:** 3–5 ms
- **ข้อ D ได้ partial ไม่ใช่ความผิดของข้อมูล** — โครงสร้าง 4 ข้อจาก cs66.pdf ถูกต้อง แต่คำตอบที่ผู้ใช้เห็น (RAG) เป็นการสรุปความ ตัววัด coverage จึงนับได้ 2 ใน 4 ข้อ เป็นตัวอย่างว่าเมื่อเปิด `on` ในอนาคต คำตอบจะเปลี่ยนรูปแบบไปเป็นรายการตามเอกสาร
- **ข้อ E ตรงตาม design** — Math careers ยังไม่ผ่านการตรวจ/เผยแพร่ structured จึงเป็น no_data และปล่อยให้ระบบเดิมตอบ
- **ผู้ใช้ยังไม่เห็นผลจาก structured** — ทุกคำตอบมาจากระบบเดิม (`STRUCTURED_ANSWERS=shadow`)

---

## 6. Production health

| ตรวจ | ผล |
|---|---|
| backend | `STRUCTURED_ANSWERS=shadow`, restarts 0, image `23bd7aa4…` (ไม่ได้ deploy) |
| `/health` ในคอนเทนเนอร์ | `{"status":"ok"}` |
| log backend (30 นาทีล่าสุด) | error / traceback = 0 |
| ตาราง public | courses 24, course_chunks 9039 — ไม่เปลี่ยน; chat_messages +10 (5 คำขอ × 2 ข้อความ) |
| ข้อมูลที่สกัด | evidence / extraction_runs / document_pages fingerprint เท่าเดิม; `field_values` / `list_items` ไม่ถูกแตะในรอบนี้ |

---

## 7. Rollback

**ทางที่ 1 — ย้อน publication นี้:** `~/backups/mko_p1_publication_rollback_20260915T233220Z.sql`
(SHA-256 `29006d9db9aed6e78041a8eba09ab62045108b3480d3b18b9eef20953871ed83`, สิทธิ์ 600, **ยังไม่ได้รัน**)
- `DELETE FROM mko.publications WHERE id = '9b382588…'` — `published_values` / `published_list_items` ถูกลบตาม cascade และ `v_live_*` กลับไปใช้ `92e34932…` เอง
- คืน `mko.curricula` 21 แถว (status / published_at / updated_at) จาก snapshot ก่อน publish — คณิตศาสตร์ 2569 กลับเป็น draft
- ตรวจใน transaction ก่อน COMMIT: live publication = `92e34932…`, publications = 1, live counts = 97/31, curricula published = 20

**ทางที่ 2 — backup:** `~/backups/mko_pre_p1_publication_20260915T230540Z.dump`
(`pg_dump -Fc --data-only` 7 ตาราง: publications, published_values, published_list_items, curricula, review_decisions, field_values, list_items · SHA-256 `982be564793ebbcc21e5a142a70e858c3301bb3a3fb237dfec0e43ae79697a06` · ตรวจ `sha256sum -c` แล้ว)

**ไฟล์อื่นของรอบนี้ (สิทธิ์ 600):** `mko_p1_publication_20260915T230540Z.sql/.log`, `mko_pub_before_20260915T230540Z_*`, `mko_pub_after_20260915T233220Z_*`

การย้อนกลับไม่กระทบคำตอบผู้ใช้ เพราะ `STRUCTURED_ANSWERS` ยังเป็น shadow

---

## 8. วิธีทำงานในรอบนี้ (เพื่อให้ตรวจซ้ำได้)

- **ก่อน publish:** ยืนยัน review_decisions 5 แถว (verified 4 / rejected 1), human verified 4 / rejected 1, Math 2564 careers ยัง candidate, publication ปัจจุบันยังเป็น `92e34932…`, `STRUCTURED_ANSWERS=shadow`
- **ไม่มี decision ใด stale:** ส่งออก `field_values` / `list_items` ใหม่แล้วเทียบกับ snapshot หลัง review apply — ไฟล์ตรงกันทุกไบต์
- **CLI `pipeline.mko.publish` รันกับ production ตรงๆ ไม่ได้** เพราะ `database_url()` ปฏิเสธ host ที่ไม่ใช่ local โดยตั้งใจ ([run.py:49-54](pipeline/mko/run.py:49)) และไม่ได้เลี่ยงด่านนี้ด้วย tunnel
- **แทนที่ด้วย:** รัน `publish.publish()` ของจริงบน local DB (ข้อมูล mko เหมือน production ทุก fingerprint) ใน transaction แล้ว rollback → ใช้ผลนั้นเป็น preview และเป็นตัวกำหนดว่า SQL บน production ต้องเขียนแถวใด
- **SQL บน production** คัดลอกแถวจากข้อมูลของ production เอง (`INSERT … SELECT` จาก `field_values` / `list_items` ที่สถานะ verified ตาม key ที่ `collect()` เลือก) ใน transaction เดียว พร้อมด่านตรวจก่อนและหลังเขียน — ถ้าไม่ตรง preview จะ `RAISE EXCEPTION` และไม่ COMMIT
- **ผลการรัน:** BEGIN · DO (guard) · INSERT 1 publication · INSERT 98 values · INSERT 53 list items · UPDATE 21 curricula · DO (post-check) · COMMIT

---

## 9. สิ่งที่ยังไม่ได้ทำ

- `STRUCTURED_ANSWERS=on` — ยังเป็น shadow
- Phase 3
- เปลี่ยน publish policy เป็น `verified_human_only`
- review P2 / P3 / P4 และ Math 2564 careers (ยัง candidate)
- แก้ extraction code หรือค่า/ข้อความที่สกัด
- deploy code ใหม่
- commit / push — รายงานนี้และรายงานก่อนหน้ายังไม่ commit

**ข้อมูลฝั่ง local:** ไม่เปลี่ยน — reference run ถูก rollback แล้ว local ยังไม่มีทั้ง review decisions และ publication ใหม่ (ต่างจาก production)

**สิ่งที่ควรพิจารณาต่อ (ยังไม่เสนอให้ทำ):**
- careers / objectives ของฉบับ 2561 และฉบับอื่นยังไม่มีข้อมูลที่ผ่านการตรวจ คำตอบ structured จึงมีบรรทัด "ยังไม่มีข้อมูลที่ผ่านการตรวจของ …" กำกับอยู่
- คำถามอาชีพของคณิตศาสตร์ยังได้ no_data จนกว่าจะตัดสิน Math 2564 careers (P1 ข้อ 2 ที่ KEEP_REVIEW)
