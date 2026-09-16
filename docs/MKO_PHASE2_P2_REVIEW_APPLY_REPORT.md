# MKO Phase 2 — Human Review Apply: P2

**สรุป:** บันทึก human review รอบ P2 บน production ครบตามที่อนุมัติ **9 decision (VERIFIED ทั้งหมด)** ใน transaction เดียว
- รายการที่ 6 (การแพทย์แผนไทยประยุกต์ 2565 — careers) **ไม่มี decision** และยังเป็น candidate ทั้ง field และรายการ 3 ข้อ
- Math 2564 careers จาก P1 ยังเป็น candidate เหมือนเดิม
- ไม่มีแถวอื่นเปลี่ยน ไม่มีค่า/ข้อความที่สกัดเปลี่ยน ไม่มีการเปลี่ยนข้ามฉบับหลักสูตร
- **ยังไม่ได้ publish** — publication ปัจจุบันยังเป็น `9b382588…` และ `v_live_*` ยังเป็น 98/53
- `STRUCTURED_ANSWERS=shadow` · ไม่ได้ deploy ไม่ได้แก้ extraction code ไม่ได้เปลี่ยน publish policy ไม่ได้ commit/push

เวลาเป็น UTC · decided_at ของรอบนี้ = `2026-09-16 07:34:58.671858+00`

---

## 1. Decision ที่บันทึก (9 แถว)

| # | หลักสูตร / ฉบับ | field | source / หน้า | ค่า | document_id | field_value_id | value_key |
|---|---|---|---|---|---|---|---|
| 1 | การจัดการเทคโนโลยีการเกษตรฯ (ป.โท) 2568 | careers | agri68_master.pdf หน้า 8 | 6 ข้อ | 51265845-29aa-4dbb-8566-b741fb0979b0 | e3a27fcd-d310-4886-8ab3-f0d8587c949c | items:f0e490039e9e42b2ecd9 |
| 2 | การจัดการเทคโนโลยีการเกษตรฯ (ป.เอก) 2568 | careers | agri68_phd.pdf หน้า 8 | 6 ข้อ | d1c84418-cd9d-4485-ac4a-edd0777d6946 | 3f254e9a-dffa-4b30-b961-b2805e1fe80c | items:a190fd49f823b28270ec |
| 3 | เทคโนโลยีผลิตภัณฑ์ชีวภาพฯ 2568 | careers | bio2568.pdf หน้า 9 | 5 ข้อ | 526d2910-ca54-4c2b-ad66-6be2bb007bf0 | 6685fb4d-f754-4f59-9f2b-fa71ebeb71e4 | items:8bc704c39bacea46e126 |
| 4 | วิทยาศาสตร์เครื่องสำอาง 2566 | careers | cos66.pdf หน้า 7–8 | 7 ข้อ | 53e1b3c2-9e83-42f1-942f-231595bb658a | 5f34df03-81fa-452a-896c-ac9ea45c0d84 | items:8ab5f0b8d91866ef5ec4 |
| 5 | เทคโนโลยีอาหารฯ 2566 | careers | food66.pdf หน้า 8 | 4 ข้อ | f87802b9-6da1-4920-bd75-c32f22aa0137 | 90aaf1a2-80cd-4c23-a97a-f11df6338d68 | items:17380df5022769df2b8b |
| 7 | การจัดการสิ่งแวดล้อมฯ 2565 | careers | en65.pdf หน้า 8 | 6 ข้อ | ec535a16-5bc5-41f5-9115-5ef6a4ef76de | bb9e96ae-ff94-486c-a105-5b2456636b8f | items:d08ede65f1a42f8a6fa7 |
| 8 | การจัดการเทคโนโลยีการเกษตรสมัยใหม่ 2564 | careers | atm.pdf หน้า 8 | 3 ข้อ | 68f72b12-b8ba-4db9-b2e1-8c57f0f768bc | 9eabb416-c7db-4a66-b29a-4b4914c4fac6 | items:cf7598bd0a6069820d8a |
| 9 | การประกอบอาหารฯ 2569 | total_credits | cook69.pdf หน้า 1 | **128** | 0ed72329-c1ef-4168-855c-6e10662a691e | 23498c34-03bc-4673-b28a-9c5db02ac831 | 128 |
| 10 | คอมพิวเตอร์แอนิเมชันฯ 2569 | total_credits | animation69.pdf หน้า 1 | **127** | 454cf2bd-aa31-4ccf-a10f-56146a3f8f2f | 04baf1bc-8d04-4e15-b053-356dbfa7dcdd | 127 |

**#6 การแพทย์แผนไทยประยุกต์ 2565 — careers: ไม่บันทึก decision ตามที่สั่ง**
- `field_values` `03a24a62-7c19-4a72-83a5-d54a84e4b9a5` ยังเป็น **candidate** `reviewed_by` ว่าง
- รายการอาชีพ 3 ข้อ (run `fb5c3fc4…`) ยังเป็น **candidate** ทั้งหมด
- `review_decisions` ของเอกสาร `attm65.pdf` = **0 แถว**

`reviewer = project-owner` → `reviewed_by = human:project-owner` ทุกแถว
`note` ของแต่ละ decision บันทึกหน้าและจำนวนข้อที่ตรวจ เช่น "P2: ตรงต้นฉบับหน้า 7-8 ครบ 7 ข้อ"

---

## 2. ก่อนเขียน

### 2.1 ตรวจ id / key และความเป็นปัจจุบัน

| ตรวจ | ผล |
|---|---|
| document_id / run_id / field_value_id / value_key ของทั้ง 10 หน่วย | **ตรงกับ preview ทุกหน่วย** (รวมหน่วยที่ 6 ที่ไม่บันทึก) |
| สถานะก่อนเขียน | candidate ทั้ง 10 หน่วย `reviewed_by` ว่าง |
| extraction run ใหม่ | **ไม่มี** — `mko.extraction_runs` ยังเป็น 31 แถว fingerprint `22c5c2f1…` เท่าเดิม |
| stale | ไม่มี — `field_values` snapshot ก่อนรอบนี้มี SHA-256 `34e529f5…` **ตรงกับ snapshot หลังรอบ P1 ทุกไบต์** |
| review decision เดิมของ 9 หน่วย | **ไม่มี** (0 แถวต่อเอกสาร/field) |
| publication / live ก่อนเขียน | `9b382588…`, live 98/53, publications 2 |

### 2.2 Backup / snapshot (บน server, สิทธิ์ 600)

| ไฟล์ | รายละเอียด | SHA-256 |
|---|---|---|
| `mko_pre_p2_review_20260916T073226Z.dump` | `pg_dump -Fc --data-only` 7 ตาราง: review_decisions, field_values, list_items, curricula, publications, published_values, published_list_items (71,899 bytes, `pg_restore -l` = 7 TABLE DATA, `sha256sum -c` OK) | `c27c07713905bce762bcf53cfd207461b9692b59b7254b818ce05d3290082aad` |
| `mko_p2_before_20260916T073226Z_field_values.tsv` | 403 แถวก่อนเขียน | `34e529f5be6cc2b20ad6a1e86e28daab65ebc1eec804e9e8899f47a70f3fbd98` |
| `mko_p2_before_20260916T073226Z_list_items.tsv` | 294 แถว | `f718871f66af40b0e116dee79767ffe31bf46c564f89fc4f427acce0069cc138` |
| `mko_p2_before_20260916T073226Z_other.tsv` | review_decisions / curricula / publications / จำนวน published | `2636340acaa0a4c2ff117ae903b94e95c3d648704483f293ce5679ed99ea21f8` |

### 2.3 Reference / dry-run ก่อน COMMIT

- **CLI `pipeline.mko.review` รันกับ production ตรงๆ ไม่ได้** เพราะ `database_url()` ปฏิเสธ host ที่ไม่ใช่ local โดยตั้งใจ ([run.py:49-54](pipeline/mko/run.py:49)) — และไม่ได้เลี่ยงด่านนี้
- แทนที่ด้วย reference run บน local DB (ข้อมูล mko เหมือน production) ใน transaction เดียวแล้ว rollback:
  1. เล่น decision ของ P1 ซ้ำด้วย `apply_file` จริง → state md5 ได้ `357745…` / `58f674…` **ตรงกับ production ปัจจุบัน**
  2. ตรวจ key ของทั้ง 10 หน่วยกับ preview → ตรงทุกหน่วย
  3. รัน `apply_file` จริงของ P2 ด้วย CSV 9 แถว → `recorded 9, stale 0`
  4. เก็บผลเป็นค่าที่ production ต้องได้ แล้ว rollback (ตรวจ fingerprint local ว่ากลับเหมือนเดิม)
- **SQL บน production** ทำตาม `apply_file` ([review.py:185-202](pipeline/mko/review.py:185)) และ `reapply` ([review.py:126-158](pipeline/mko/review.py:126)) พร้อมด่านตรวจก่อน/หลังเขียนใน transaction เดียวกัน — ถ้าไม่ตรง reference จะ `RAISE EXCEPTION` และไม่ COMMIT
- SQL: `~/backups/mko_p2_review_apply_20260916T073226Z.sql` SHA-256 `2d0340312f19367a59803a22d68995943b5ec530636f1cd5b2b292c080bc5ed0`
- **ผลการรัน:** BEGIN · DO (guard) · UPDATE 0 ×9 (supersede — ไม่มี decision เดิม) · INSERT 0 1 ×9 · UPDATE 1 ×9 (field_values) · UPDATE 6/6/5/7/4/6/3 (list_items 7 รายการ) · DO (post-check) · COMMIT — exit 0

---

## 3. ตรวจหลัง Apply

| ข้อที่ต้องตรวจ | ผล |
|---|---|
| review_decisions เพิ่ม 9 แถว | ✔ 5 → **14** แถว (P1 5 แถว decided_at 2026-09-15 21:10:40Z ยังอยู่ครบ + P2 9 แถว decided_at 2026-09-16 07:34:58Z) active ทั้งหมด |
| verified(human) เพิ่ม 9 field_values | ✔ 4 → **13** (rejected human ยังเป็น 1) |
| careers list_items ที่เปลี่ยนมี 37 ข้อเท่านั้น | ✔ เปลี่ยน 37 แถวใน 7 รายการ: agri ป.โท 6, agri ป.เอก 6, bio2568 5, cos66 7, food66 4, en65 6, atm 3 — ทุกข้อของแต่ละรายการเปลี่ยนครบ และทุกแถวเป็น `item_type = career` |
| total_credits 128 / 127 verified ถูก edition | ✔ cook69.pdf → การประกอบอาหารฯ **2569** = 128 · animation69.pdf → คอมพิวเตอร์แอนิเมชันฯ **2569** = 127 (Math 2569 = 124 จาก P1 ยังอยู่) |
| ATTM 2565 careers ยัง candidate และไม่มี decision | ✔ field candidate, รายการ 3 ข้อ candidate, decision 0 แถว |
| Math 2564 careers ยัง candidate | ✔ field candidate, รายการ 5 ข้อ candidate, decision 0 แถว |
| ไม่มี field อื่นเปลี่ยน | ✔ `field_values` เปลี่ยน **9 แถว** ตรงกับ 9 หน่วยที่อนุมัติ · `list_items` เปลี่ยน **37 แถว** ตรงกับ 7 รายการที่อนุมัติ |
| ไม่มี extracted value/text เปลี่ยน | ✔ คอลัมน์ที่เปลี่ยนมีเพียง status, reviewed_by, reviewed_at, reason · `value_int` และ md5 ของ `value_text` / `text` เท่าเดิมทุกแถว |
| ไม่มี cross-edition mixing | ✔ ทุกแถวที่เปลี่ยนอยู่ในเอกสารของหลักสูตรฉบับตัวเอง |
| ป.โท / ป.เอก เกษตรฯ 2568 แยกกัน | ✔ คนละ course, คนละเอกสาร, คนละ field_value (`e3a27fcd…` / `3f254e9a…`) และรายการ 6 ข้อของแต่ละฉบับแยกกัน |
| publication ปัจจุบัน | ✔ ยังเป็น `9b382588-db00-4e80-9935-953fc4559ef7` (publications = 2) |
| `v_live_*` ไม่เปลี่ยน | ✔ 98 / 53 · curricula published 21 / draft 3 · published_values / published_list_items ไม่เปลี่ยน |
| STRUCTURED_ANSWERS | ✔ `shadow` (restarts 0, `/health` = ok) |

**สถานะรวมก่อน → หลัง**

| ตาราง | ก่อน | หลัง |
|---|---|---|
| field_values | candidate 184, verified(auto) 167, verified(human) 4, rejected(human) 1, not_found 47 | candidate **175**, verified(auto) 167, **verified(human) 13**, rejected(human) 1, not_found 47 |
| list_items | candidate 206, verified(auto) 62, verified(human) 22, rejected(human) 4 | candidate **169**, verified(auto) 62, **verified(human) 59**, rejected(human) 4 |
| review_decisions | 5 | **14** |

**diff before/after รายแถว:** `field_values` 403 แถว เปลี่ยน 9 (candidate → verified ทุกแถว) · `list_items` 294 แถว เปลี่ยน 37 · ตาราง curricula / publications / published_* ไม่มีแถวเปลี่ยนหรือหายไป มีเพียง review_decisions เพิ่ม 9 แถว · `reviewed_at` ของทุกแถวที่เปลี่ยน = `2026-09-16 07:34:58.671858+00`

---

## 4. Rollback (เตรียมไว้ ยังไม่ได้รัน)

**ทางที่ 1 — ย้อนเฉพาะรอบ P2:** `~/backups/mko_p2_review_rollback_20260916T073458Z.sql`
(SHA-256 `deab6593ae2c28d8bda98ec881a2ed805b98628074f3312a6a8af0b1f38e1bee`, 67 บรรทัด, สิทธิ์ 600)
- คืน 9 `field_values` และ 37 `list_items` เป็นค่าก่อนเขียน (จาก before snapshot)
- ลบ 9 review_decisions ของรอบ P2
- ตรวจใน transaction ก่อน COMMIT ว่าเหลือ decision 5 แถวของ P1, field_values human 5, list_items human 26 และ publication ยังเป็น `9b382588…`
- **ไม่แตะ** decision ของ P1 และไม่แตะ publication

**ทางที่ 2 — backup:** `~/backups/mko_pre_p2_review_20260916T073226Z.dump` (ข้อ 2.2)

การย้อนกลับไม่กระทบคำตอบผู้ใช้ เพราะยังไม่ได้ publish และ `STRUCTURED_ANSWERS` ยังเป็น shadow

---

## 5. ผลที่จะเกิดถ้า publish ในอนาคต (ยังไม่ได้รับอนุมัติ)

ค่าที่จะเข้า live เพิ่มจากรอบนี้ ถ้า publish ด้วยนโยบายเดิม `verified_any`:
- careers เพิ่ม **7 ฉบับ** (เกษตรฯ ป.โท 2568, เกษตรฯ ป.เอก 2568, เทคโนโลยีผลิตภัณฑ์ชีวภาพฯ 2568, วิทยาศาสตร์เครื่องสำอาง 2566, เทคโนโลยีอาหารฯ 2566, การจัดการสิ่งแวดล้อมฯ 2565, เกษตรสมัยใหม่ 2564) รวม 37 ข้อ — จากปัจจุบัน live 2 ฉบับ (CS 2566, IT 2566) เป็น 9 ฉบับ
- total_credits เพิ่ม 2 ค่า (การประกอบอาหารฯ 2569 = 128, คอมพิวเตอร์แอนิเมชันฯ 2569 = 127) และ `mko.curricula` ของสองฉบับนี้จะเปลี่ยนจาก draft เป็น published (เหลือ draft 1 คือสาธารณสุขศาสตร์)
- คำถามอาชีพของ 7 สาขาที่ shadow เคยตอบ no_data จะมีข้อมูล structured ให้เทียบ
- **ยังไม่เข้า live:** careers ของการแพทย์แผนไทยประยุกต์ 2565 และคณิตศาสตร์ 2564 (ทั้งคู่ยัง candidate ตามที่อนุมัติ)

---

## 6. สิ่งที่ยังไม่ได้ทำ (ตามที่ยังไม่อนุมัติ)

- publish / เปลี่ยน publish policy
- deploy / แก้ extraction code
- `STRUCTURED_ANSWERS=on` / Phase 3
- review P3 / P4 และ 6 หน่วย P2 ที่เลื่อนไว้ (คหกรรมศาสตร์ 2564, วิทย์อาหาร 2561, เทคโนโลยีสุขภาพ 2561, วิทย์สิ่งแวดล้อม 2560, สาธารณสุขศาสตร์ careers + total_credits)
- decision ของ ATTM 2565 careers และ Math 2564 careers
- commit / push — รายงานนี้และรายงานก่อนหน้ายังไม่ commit

**ข้อมูลฝั่ง local:** ไม่เปลี่ยน — reference run ถูก rollback และตรวจ fingerprint แล้ว local จึงยังไม่มีทั้ง review decisions และ publication ใหม่ (ต่างจาก production)

**ไฟล์ของรอบนี้บน server (สิทธิ์ 600):** `mko_pre_p2_review_*.dump(.sha256)`, `mko_p2_before_*`, `mko_p2_after_20260916T073458Z_*`, `mko_p2_review_apply_*.sql/.log`, `mko_p2_review_rollback_*.sql`
