# MKO Phase 2 — Human Review Apply: P1

**สรุป:** บันทึก human review บน production ครบตามที่อนุมัติ 5 decision (VERIFIED 4, REJECTED 1) ใน transaction เดียว
- Math 2564 careers ไม่มี decision และยังเป็น candidate
- ไม่มีแถวอื่นเปลี่ยน ไม่มีการเปลี่ยนข้ามฉบับหลักสูตร
- **ยังไม่ได้ publish** — live publication, shadow และคำตอบผู้ใช้ไม่เปลี่ยน
- ไม่ได้ deploy ไม่ได้แก้ code/extraction ไม่ได้ commit/push

เวลาเป็น UTC · decided_at = `2026-09-15 21:10:40.205747+00`

---

## 1. Decision ที่บันทึก

| # | หลักสูตร / ฉบับ | course_id | field | source / หน้า | document_id | value_key | decision |
|---|---|---|---|---|---|---|---|
| 1 | เทคโนโลยีสารสนเทศ 2566 | 2fa6627f-e2fa-4956-b9d0-d0c82ad3dcaf | careers | it66.pdf หน้า 6 | 9403a438-bf26-47fa-9f70-9354e1451916 | items:f5306dd1816043ccb46b | **verified** |
| 3 | วิทยาการคอมพิวเตอร์ 2566 | 02bb0f00-a6af-448b-8772-b064d399f770 | careers | cs66.pdf หน้า 3 | 7e06cd12-87ee-49ab-9687-c5dc51114474 | items:a67be7cada1ac88f818e | **verified** |
| 4 | คณิตศาสตร์ 2569 | 163c0edc-a4e2-4ff2-ae96-b21160348ec1 | total_credits | ma69.pdf หน้า 1 | fb2279ac-3139-449f-87dc-51c8e970bcd4 | 124 | **verified** |
| 5 | วิทยาการคอมพิวเตอร์ 2566 | 02bb0f00-a6af-448b-8772-b064d399f770 | objectives | cs66.pdf หน้า 11 | 7e06cd12-87ee-49ab-9687-c5dc51114474 | items:452f6545956df64f10fa | **verified** |
| 6 | วิทยาการคอมพิวเตอร์ 2566 | 02bb0f00-a6af-448b-8772-b064d399f770 | objectives | cs66_brief.pdf หน้า 1 | 50a085cb-e258-4c85-9433-51fcfc177606 | items:ac4b17facc36c9b21d9d | **rejected** |
| 2 | คณิตศาสตร์ 2564 | 589bc11f-0b3c-4ad7-a545-6fe25685ea40 | careers | ma64.pdf หน้า 7 | 35708c6c-baa6-4e86-9312-f4c0f23911d7 | (items:4d0225576ea686807cf8) | **KEEP_REVIEW — ไม่บันทึก decision** |

`note` ของแต่ละ decision:
- **1:** "P1: ตรงต้นฉบับหน้า 6 ครบ 9 ข้อ (ต้นฉบับพิมพ์เลขข้อ 8.7, 8.9, 8.9)"
- **3:** "P1: ตรงต้นฉบับหน้า 3 ครบ 9 ข้อ"
- **4:** "P1: หน้า 1 จำนวนหน่วยกิตรวมตลอดหลักสูตรไม่น้อยกว่า 124 หน่วยกิต"
- **5:** "P1: มคอ.2 หัวข้อ 1.3 หน้า 11 เป็น source authoritative"
- **6:** "P1: ใบสรุปข้อ 2 ไม่ครบประโยคเมื่อเทียบกับ มคอ.2 (cs66.pdf หน้า 11)"

### reviewed_by

- ระบบ review ไม่มีรายชื่อผู้ตรวจที่ต้องมีอยู่ก่อน
  - `review_decisions.reviewer` เป็นข้อความที่ต้องไม่ว่างเท่านั้น
  - reapply บันทึก `reviewed_by = "human:" + reviewer` ([review.py:141](pipeline/mko/review.py:141))
- จึงบันทึก `reviewer = project-owner` → `reviewed_by = human:project-owner` ตรงตามที่อนุมัติ ไม่ได้เดาหรือเปลี่ยนชื่อ

---

## 2. วิธีบันทึก และเหตุผลที่ไม่ได้รัน CLI `pipeline.mko.review apply` กับ production ตรงๆ

**เหตุผล:**
- `pipeline.mko.review` เชื่อมฐานข้อมูลผ่าน `database_url()` ซึ่ง **ปฏิเสธ host ที่ไม่ใช่เครื่อง local โดยตั้งใจ** ([run.py:49-54](pipeline/mko/run.py:49): "Phase 1 เขียนได้เฉพาะฐานข้อมูลบนเครื่องนี้")
- การทำ SSH tunnel ให้ production ดูเป็น 127.0.0.1 คือการเลี่ยงด่านนี้ จึงไม่ทำ
- ไม่ได้แก้ code ของด่านนี้ด้วย

**สิ่งที่ทำแทน:** ใช้ `psql` ใน transaction เดียว (ช่องทางเดียวกับการเขียน production ที่อนุมัติมาก่อน) และให้ผลตรงกับเครื่องมือจริงดังนี้
1. **Reference run ของเครื่องมือจริงบน local DB**
   - ตรวจก่อนว่า fingerprint ของ mko บน local **ตรงกับ production ทุกตาราง** (field_values, list_items, evidence, extraction_runs, document_pages, review_decisions)
   - รัน `review.apply_file()` จริงด้วย CSV 5 แถวเดียวกัน ใน transaction แล้ว **rollback**
   - ผล: recorded 5, stale 0, applied 5 — local ไม่เปลี่ยนหลัง rollback (ตรวจ fingerprint ซ้ำ)
2. **SQL ที่ใช้บน production สร้างจาก reference run นั้น**
   - คำสั่งตรงกับ `apply_file` ([review.py:185-202](pipeline/mko/review.py:185)) และ `reapply` ([review.py:126-158](pipeline/mko/review.py:126))
   - `shown_value`, `value_key`, `reason` เป็นค่าเดียวกับที่เครื่องมือสร้าง และ `reviewed_at = decided_at`
3. **ด่านตรวจใน transaction ก่อนเขียน** — ถ้าไม่ผ่านจะ `RAISE EXCEPTION` และไม่มีการ COMMIT
   - `mko.review_decisions` ต้องว่าง
   - ทั้ง 6 หน่วย (รวม Math 2564):
     - file_sha256 ของเอกสาร
     - latest run id
     - field_value id / run / field / status / value
     - `reviewed_by IS NULL`
     - md5 ของรายการ `seq:text` และจำนวนข้อ
4. **ด่านตรวจใน transaction หลังเขียน:**
   - review_decisions = 5
   - field_values ที่เป็น human = 5
   - list_items ที่เป็น human = 26
   - Math 2564 careers ยังเป็น candidate และไม่มี decision

---

## 3. ก่อนเขียน

### 3.1 ตรวจความเป็นปัจจุบัน (stale check)

| หน่วย | latest run | field_value | สถานะก่อน | value_key ตรง preview |
|---|---|---|---|---|
| it66.pdf careers | 09b1e5c9-6518-4d82-88f5-1e0d6f5c688d | abce04a9-2db2-4a90-bcd6-d5006d047968 | needs_review | ✔ |
| cs66.pdf careers | 1530ea96-3ebd-4583-8d58-0907459dd39e | e2fa4e0a-b040-43f1-9c74-54372f98f316 | candidate | ✔ |
| ma69.pdf total_credits | c29b9f1a-4d90-472a-b79d-46a067afab92 | 29407dad-917a-498b-9049-7ac6b357a10e | candidate | ✔ |
| cs66.pdf objectives | 1530ea96-3ebd-4583-8d58-0907459dd39e | 2f89492a-b362-44d7-aaeb-069f57107a2a | needs_review | ✔ |
| cs66_brief.pdf objectives | 57062a5e-f2dd-4707-a5f3-a1efce838fb7 | 5e8ffecb-80b9-40e8-91fc-0d2f74274b9b | needs_review | ✔ |
| ma64.pdf careers (ไม่บันทึก) | 92ddef7b-7c92-4bc1-aae3-5a6471ae0a5f | 7f879dd7-790e-4554-9636-0b53ae333374 | candidate | ✔ |

ไม่มีหน่วยใด stale และการสกัดไม่เปลี่ยน (31 runs เดิม, fingerprint เดิม)

### 3.2 Backup / snapshot (บน server, สิทธิ์ 600)

| ไฟล์ | รายละเอียด | SHA-256 |
|---|---|---|
| `~/backups/mko_pre_p1_review_20260915T210607Z.dump` | `pg_dump -Fc --data-only` ของ mko: review_decisions, field_values, list_items, field_value_evidence, evidence, extraction_runs, curricula, publications, published_values, published_list_items (122,015 bytes; `pg_restore -l` อ่านได้ 10 TABLE DATA) | `c77efa98f6499cdf954a3d260edba8f03dd4fb1cb3d078c2399b55a4f1d0d13c` |
| `~/backups/mko_p1_before_20260915T210607Z_field_values.tsv` | สถานะรายแถวทั้ง 403 แถวก่อนเขียน | `f61643b7fb7f06f25a04a4e0ab6a0e2ceb10250028e4b10ca86f1d64a0ab2f7b` |
| `~/backups/mko_p1_before_20260915T210607Z_list_items.tsv` | สถานะรายแถวทั้ง 294 แถว | `3f36a7f7230e326cc2dbd84922644572405ede3429abbfc61df992f2be6b4248` |
| `~/backups/mko_p1_before_20260915T210607Z_other.tsv` | curricula / review_decisions / publications / จำนวน published | `b09cc5714f63abb5ba99e65f537d6f2947a9a84ff251786781240bf34466a7ca` |

**Fingerprint ก่อนเขียน** (production = local):

| ตาราง | แถว | md5 |
|---|---|---|
| field_values | 403 | 3bc1518c… |
| list_items | 294 | 9f5973e0… |
| evidence | 787 | 9325bbcb… |
| extraction_runs | 31 | 22c5c2f1… |
| document_pages | 4129 | 976a1cc9… |
| review_decisions | 0 | — |

---

## 4. การเขียน

| รายการ | ค่า |
|---|---|
| SQL | `~/backups/mko_p1_review_apply_20260915T210607Z.sql` — SHA-256 `bf72c8a0f24f4d8b8f44ecbdabb6a73abdfc219db5e6e684b1570fbc9363ad5f` (ตรงกันทั้ง local และ server ก่อนรัน) |
| คำสั่ง | `psql -v ON_ERROR_STOP=1` หนึ่ง transaction |
| ผล (`…apply_…log`) | BEGIN · DO (guard) · UPDATE 0 ×5 (supersede — ไม่มี decision เดิม) · INSERT 0 1 ×5 · UPDATE 1 ×5 (field_values) · UPDATE 9 ×2 · UPDATE 4 ×2 (list_items) · DO (post-check) · COMMIT — exit 0 |

---

## 5. ตรวจหลังเขียน

### 5.1 review_decisions เพิ่มตรงตามอนุมัติ

5 แถวใหม่ (ก่อนหน้า 0):
- **สถานะ:** active ทั้งหมด, `reviewer = project-owner`, `document_sha256` ตรงกับไฟล์
- **decision:** verified 4 (it66 careers, cs66 careers, ma69 total_credits, cs66 objectives), rejected 1 (cs66_brief objectives)
- **Math 2564:** ไม่มี decision ใดของ `ma64.pdf`

### 5.2 VERIFIED / REJECTED ถูก reapply ถูก field / document

| เอกสาร | field | status หลังเขียน | reviewed_by | list_items |
|---|---|---|---|---|
| it66.pdf | careers | verified | human:project-owner | career 9 ข้อ verified |
| cs66.pdf | careers | verified | human:project-owner | career 9 ข้อ verified |
| ma69.pdf | total_credits | verified (124) | human:project-owner | — |
| cs66.pdf | objectives | verified | human:project-owner | objective 4 ข้อ verified |
| cs66_brief.pdf | objectives | rejected | human:project-owner | objective 4 ข้อ rejected |
| **ma64.pdf** | **careers** | **candidate** (reviewed_by ว่าง) | — | **career 5 ข้อ candidate** |

- **reason:** "ตรวจโดย project-owner: <note>"
- **reviewed_at:** = decided_at ทุกแถว
- **ผลเทียบกับ reference run ของเครื่องมือจริง:** status / reviewed_by / reason ของ field_values ทั้ง 6 หน่วย และ list_items ทุกประเภทของ run ที่เกี่ยวข้อง **ตรงกันทั้งหมด**

### 5.3 ไม่มี field อื่นเปลี่ยน (diff before/after รายแถว)

| ตาราง | แถว | แถวที่เปลี่ยน | ตรงกับที่อนุมัติ | คอลัมน์ที่เปลี่ยน |
|---|---|---|---|---|
| mko.field_values | 403 | **5** | id ตรงกับ 5 field_value ที่อนุมัติ | เฉพาะ status, reviewed_by, reviewed_at, reason |
| mko.list_items | 294 | **26** | เฉพาะ 4 รายการที่อนุมัติ (it66 career 9, cs66 career 9, cs66 objective 4, cs66_brief objective 4) ครบทุกข้อของแต่ละรายการ | เฉพาะ status, reviewed_by, reviewed_at, reason |
| mko.review_decisions | 0 → 5 | +5 | ✔ | — |
| mko.curricula / publications / published_values / published_list_items | — | 0 | — | — |

**ไม่มีการแก้ค่าที่สกัด:**
- `value_int`, md5 ของ `value_text` และ md5 ของ `text` ของทุกแถวไม่เปลี่ยน
- fingerprint ของ evidence (787), extraction_runs (31), document_pages (4129) เท่าเดิม

**จำนวนตามสถานะ:**

| ตาราง | ก่อน | หลัง |
|---|---|---|
| field_values | candidate 186, needs_review 3, verified(auto) 167, not_found 47 | candidate 184, needs_review 0, verified(auto) 167, **verified(human) 4**, **rejected(human) 1**, not_found 47 |
| list_items | candidate 215, needs_review 17, verified(auto) 62 | candidate 206, needs_review 0, verified(auto) 62, **verified(human) 22**, **rejected(human) 4** |

### 5.4 ไม่มี cross-edition change

แถวที่มี `reviewed_by = human:*` อยู่ใน 3 ฉบับหลักสูตรเท่านั้น ตรงกับ decision ของฉบับนั้น:
- วิทยาการคอมพิวเตอร์ **2566**: careers verified, objectives verified (cs66.pdf) / rejected (cs66_brief.pdf)
- เทคโนโลยีสารสนเทศ **2566**: careers verified
- คณิตศาสตร์ **2569**: total_credits verified

ฉบับอื่นของสาขาเดียวกันไม่เปลี่ยน:
- วิทยาการคอมพิวเตอร์ 2561
- เทคโนโลยีสารสนเทศ 2561
- คณิตศาสตร์ 2564 — careers / objectives / admission ยังเป็น candidate ทั้งหมด

### 5.5 Live / shadow / ผู้ใช้

| ตรวจ | ผล |
|---|---|
| live publication | `92e34932-2863-4604-a5f6-4611fc6e9b51` (1 publication — ไม่มีใหม่) |
| `mko.v_live_values` / `v_live_list_items` | 97 / 31 — เท่าเดิม |
| curricula | published 20 / draft 4 — เท่าเดิม |
| backend | `STRUCTURED_ANSWERS=shadow`, restarts 0 |
| คำตอบผู้ใช้ | ไม่เปลี่ยน — backend อ่านเฉพาะ live publication |

---

## 6. ถ้าจะ publish ในอนาคต (ยังไม่ได้ทำ ต้องได้รับอนุมัติแยก)

`pipeline.mko.publish` นำเฉพาะค่า verified ของรอบสกัดล่าสุด (รายการต้อง verified ทุกข้อ) ค่าที่จะเข้าใหม่จากรอบนี้คือ:
- careers ของเทคโนโลยีสารสนเทศ 2566 (9 ข้อ)
- careers ของวิทยาการคอมพิวเตอร์ 2566 (9 ข้อ)
- total_credits ของคณิตศาสตร์ 2569 = 124 — ฉบับนี้ `mko.curricula` จะเปลี่ยนจาก draft เป็น published ตามขั้น publish
- objectives ของวิทยาการคอมพิวเตอร์ 2566 จาก `cs66.pdf` (4 ข้อ)
  - `cs66_brief.pdf` เป็น rejected จึงไม่ถูกนำไปเทียบ ไม่เกิด conflict
  - objectives ของฉบับ 2566 นี้ยังไม่ live (ตอนสกัด brief กับฉบับเต็มไม่ตรงกัน)

ข้อควรพิจารณาก่อนอนุมัติ publish:
- **นโยบาย `verified_any` (ปัจจุบัน):** publication ใหม่ = ค่า auto ที่ live เดิม + 4 field ข้างต้น
- **นโยบาย `verified_human_only`:** มีเฉพาะ 4 field นี้ ค่า auto 46 ค่าที่ live อยู่จะไม่อยู่ใน publication ใหม่
- **Math 2564 careers ยังไม่ publish** (KEEP_REVIEW) — คำถามอาชีพของคณิตศาสตร์ยังได้ no_data จาก shadow

---

## 7. Rollback (เตรียมไว้ ยังไม่ได้รัน)

**ทางที่ 1 — SQL ย้อนเฉพาะรอบนี้:** `~/backups/mko_p1_review_rollback_20260915T211040Z.sql` (SHA-256 `120e068eb0ad808b6da87df2e66ccaa30b31131adb07daca018e1711274b5bea`, 47 บรรทัด, สิทธิ์ 600)
- คืน status / reviewed_by / reviewed_at / reason ของ 5 field_values และ 26 list_items เป็นค่าก่อนเขียน (สร้างจาก before snapshot)
- ลบ 5 review_decisions ของ project-owner
- ตรวจใน transaction ว่าไม่เหลือแถว human ก่อน COMMIT

**ทางที่ 2 — backup:** `~/backups/mko_pre_p1_review_20260915T210607Z.dump` (ข้อ 3.2)

การย้อนกลับไม่กระทบ live publication เพราะยังไม่ได้ publish

---

## 8. สิ่งที่ยังไม่ได้ทำ (ตามที่ยังไม่อนุมัติ)

- publish / เปลี่ยน publish policy
- deploy / แก้ extraction code
- `STRUCTURED_ANSWERS=on` / Phase 3
- review P2 / P3 / P4
- บันทึก decision ของ Math 2564 careers
- commit / push

**ข้อมูลฝั่ง local:**
- local DB ไม่เปลี่ยน — reference run ถูก rollback และตรวจ fingerprint แล้ว
- local จึงยังไม่มี review decisions ของรอบนี้ (ต่างจาก production 5 decision)

**ไฟล์ที่เกี่ยวข้องบน server (ไม่ได้ลบ):**
- `mko_pre_p1_review_*.dump(.sha256)`
- `mko_p1_before_*`, `mko_p1_after_20260915T211040Z_*` (+ `.sha256`)
- `mko_p1_review_apply_*.sql/.log`, `mko_p1_review_rollback_*.sql`

รายงานนี้ยังไม่ commit
