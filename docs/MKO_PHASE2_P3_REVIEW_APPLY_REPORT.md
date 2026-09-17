# MKO Phase 2 — Human Review Apply: P3

**สรุป:** บันทึก human review รอบ P3 บน production ครบตามที่อนุมัติ **23 decision (VERIFIED ทั้งหมด)** ใน transaction เดียว
- **KEEP_REVIEW 5 หน่วยไม่มี decision** และยังเป็น candidate ทั้ง field และรายการทุกข้อ
- เปลี่ยนเฉพาะ `status / reviewed_by / reviewed_at / reason` ของ 23 `field_values` และ 66 `list_items` ที่อนุมัติ — **ไม่มีค่า/ข้อความที่สกัดเปลี่ยน** ไม่มีการเปลี่ยนข้ามหลักสูตรหรือข้ามฉบับ
- **ยังไม่ได้ publish** — publication ยังเป็น `d0311dd5-ba1d-44dc-8460-66542394cefa` และ `v_live_*` ยังเป็น **100 / 90**
- `STRUCTURED_ANSWERS=shadow` · ไม่ได้ deploy · ไม่ได้แก้ extraction / schema / routing / RAG / prompt · ไม่ได้ใช้ Gemini · ไม่มี chat traffic · ไม่ได้รัน behaviour_check · ไม่ได้ commit/push

เวลาเป็น UTC · `decided_at` / `reviewed_at` ของรอบนี้ = `2026-09-16 20:58:50.558794+00`

---

## 1. Decision ที่บันทึก (23 แถว)

`decision = verified` · `reviewer = project-owner` → `reviewed_by = human:project-owner` · `note` ระบุหน้าและจำนวนข้อที่ตรวจ (เช่น "P3: ตรงต้นฉบับหน้า 2-3 ครบ 11 ข้อ")

| # | หลักสูตร / ฉบับ (ระดับ) | field | source / หน้า | ค่า | document_id | field_value_id | value_key |
|---|---|---|---|---|---|---|---|
| 1 | คหกรรมศาสตร์ 2564 (ตรี) | careers | ds2564.pdf หน้า 2–3 | 11 ข้อ | 5cb797f1-5ea1-4cc7-a352-e35fce2ab38c | f546db95-fc19-4f34-a280-584234ec0f7b | items:aa8d9f3969fffbcd00c1 |
| 2 | เทคโนโลยีการจัดการสุขภาพ 2561 (ตรี) | careers | ht61.pdf หน้า 7 | 3 ข้อ | af9fad17-5d0c-400c-bd11-25459a418672 | 5808d98d-2a53-4b36-b77c-8fe9dbf2449b | items:299d13a54df7a73b7d03 |
| 3 | การจัดการสิ่งแวดล้อมฯ 2565 (ตรี) | admission | en65.pdf หน้า 18 | 1 ข้อ | ec535a16-5bc5-41f5-9115-5ef6a4ef76de | fe51649b-f9ed-4074-9269-1b4824ffd4b6 | items:abf4e08e3a90b1192a8c |
| 4 | การจัดการเทคโนโลยีการเกษตรสมัยใหม่ 2564 (ตรี) | admission | atm.pdf หน้า 16 | 1 ข้อ | 68f72b12-b8ba-4db9-b2e1-8c57f0f768bc | 1750082f-0fb2-486d-8084-5784de89c44e | items:f3cacac40d9b8b5dc5db |
| 5 | เกษตรฯ 2568 (ป.เอก) | admission | agri68_phd.pdf หน้า 91 | 2 ข้อ | d1c84418-cd9d-4485-ac4a-edd0777d6946 | 9c67203e-7054-4a6b-8847-0d09b450940d | items:4a7d2fee4d461555cdd6 |
| 6 | เกษตรฯ 2568 (ป.โท) | admission | agri68_master.pdf หน้า 85 | 3 ข้อ | 51265845-29aa-4dbb-8566-b741fb0979b0 | 8de2ac84-5ea9-4885-8149-76d1aec501de | items:1c25410d0fd12807dc4a |
| 7 | การแพทย์แผนไทยประยุกต์ 2565 (ตรี) | admission | attm65.pdf หน้า 19 | 1 ข้อ | 2c079b84-e333-44c2-a44a-b0896db03f16 | 5fe22166-e7c6-4e1a-b176-9e65f80569ce | items:7d4eae3bb8085cb0c07f |
| 8 | คหกรรมศาสตร์ 2564 (ตรี) | admission | ds2564.pdf หน้า 11 | 1 ข้อ | 5cb797f1-5ea1-4cc7-a352-e35fce2ab38c | 7c2fd24b-4732-40f2-ba4b-64d60d53b419 | items:b1dd86cbd2e773ba0d26 |
| 9 | วิทยาศาสตร์เครื่องสำอาง 2566 (ตรี) | admission | cos66.pdf หน้า 18 | 1 ข้อ | 53e1b3c2-9e83-42f1-942f-231595bb658a | 6e7c89be-7fce-4696-992a-5010d556fb4a | items:1a7c85b35c0a661904f5 |
| 10 | เทคโนโลยีการจัดการสุขภาพ 2561 (ตรี) | admission | ht61.pdf หน้า 16 | 1 ข้อ | af9fad17-5d0c-400c-bd11-25459a418672 | 51f60d83-49e8-47f0-982b-5a039ad94759 | items:fd41076fdb78ba129637 |
| 11 | เทคโนโลยีสารสนเทศ 2566 (ตรี) | admission | it66.pdf หน้า 16 | 3 ข้อ | 9403a438-bf26-47fa-9f70-9354e1451916 | 12a14002-a5f2-4028-8cd9-3517dd3fc003 | items:3949be9adf44555c8048 |
| 12 | เทคโนโลยีอาหารฯ 2566 (ตรี) | admission | food66.pdf หน้า 20 | 1 ข้อ | f87802b9-6da1-4920-bd75-c32f22aa0137 | 64bee368-8f7a-456c-8afc-aab91b36190d | items:b5fde7bd07301562a540 |
| 13 | การประกอบอาหารฯ 2569 (ตรี) | edition_year | cook69.pdf หน้า 1 | 2569 | 0ed72329-c1ef-4168-855c-6e10662a691e | 0e062637-399a-4de7-9b79-7c4dff2c4735 | 2569 |
| 14 | คณิตศาสตร์ 2569 (ตรี) | edition_year | ma69.pdf หน้า 1 | 2569 | fb2279ac-3139-449f-87dc-51c8e970bcd4 | 2fde90b1-842e-424d-9470-38199ca1e4dd | 2569 |
| 15 | คอมพิวเตอร์แอนิเมชันฯ 2569 (ตรี) | edition_year | animation69.pdf หน้า 1 | 2569 | 454cf2bd-aa31-4ccf-a10f-56146a3f8f2f | 41db36c5-721a-4140-9e0d-c264403f5aff | 2569 |
| 16 | การจัดการเทคโนโลยีการเกษตรสมัยใหม่ 2564 (ตรี) | objectives | atm.pdf หน้า 13–14 | 5 ข้อ | 68f72b12-b8ba-4db9-b2e1-8c57f0f768bc | 78a8520b-3538-4927-8583-6225bbb4e896 | items:69637887224ff2809034 |
| 17 | เกษตรฯ 2568 (ป.เอก) | objectives | agri68_phd.pdf หน้า 19 | 4 ข้อ | d1c84418-cd9d-4485-ac4a-edd0777d6946 | 4dbb0a00-5d92-4f40-a9df-23af6f458293 | items:c614ac9cf8cb42759d65 |
| 18 | เกษตรฯ 2568 (ป.โท) | objectives | agri68_master.pdf หน้า 19 | 5 ข้อ | 51265845-29aa-4dbb-8566-b741fb0979b0 | 035da432-35eb-43ad-9ee7-706296cf9d75 | items:dc6b67d5baf5ce580870 |
| 19 | การประกอบอาหารฯ 2569 (ตรี) | objectives | cook69.pdf หน้า 1 | 4 ข้อ | 0ed72329-c1ef-4168-855c-6e10662a691e | 6f1d64fe-811e-4766-bfbf-dae500a7b158 | items:cf4d346f111475ea14a0 |
| 20 | คณิตศาสตร์ 2569 (ตรี) | objectives | ma69.pdf หน้า 1 | 4 ข้อ | fb2279ac-3139-449f-87dc-51c8e970bcd4 | b527b913-6f52-4ba9-9f9a-bc590f119842 | items:6bfcc5f12242830df599 |
| 21 | คอมพิวเตอร์แอนิเมชันฯ 2569 (ตรี) | objectives | animation69.pdf หน้า 1 | 6 ข้อ | 454cf2bd-aa31-4ccf-a10f-56146a3f8f2f | 65f20f4f-7a1d-43ba-9b79-accf9c1dfcff | items:45f21b2b00708febf344 |
| 22 | คหกรรมศาสตร์ 2564 (ตรี) | objectives | ds2564.pdf หน้า 8–9 | 5 ข้อ | 5cb797f1-5ea1-4cc7-a352-e35fce2ab38c | 88a6dfea-52f3-4749-b745-98efc2e5191e | items:a8e1ab87f570a20e217f |
| 23 | เทคโนโลยีการจัดการสุขภาพ 2561 (ตรี) | objectives | ht61.pdf หน้า 13 | 4 ข้อ | af9fad17-5d0c-400c-bd11-25459a418672 | bdde865f-b6e2-44d7-9734-559a78fe0a62 | items:888523e37fd8678b2f5f |

แยกตาม field: careers 2 · admission 10 · edition_year 3 · objectives 8

---

## 2. KEEP_REVIEW 5 หน่วย — ยืนยันว่าไม่ถูกแตะ

| หลักสูตร / ฉบับ | field | field_value_id | สถานะหลัง apply | รายการ | decision |
|---|---|---|---|---|---|
| การแพทย์แผนไทยประยุกต์ 2565 (ตรี) | careers | 03a24a62-7c19-4a72-83a5-d54a84e4b9a5 | candidate · reviewed_by ว่าง | 3 ข้อ candidate | 0 แถว |
| คณิตศาสตร์ 2564 (ตรี) | careers | 7f879dd7-790e-4554-9636-0b53ae333374 | candidate · reviewed_by ว่าง | 5 ข้อ candidate | 0 แถว |
| สาธารณสุขศาสตร์ ไม่ระบุปี (ตรี) | careers | 6cc7aaba-8f04-4fc2-8639-c3c0932f4988 | candidate · reviewed_by ว่าง | 7 ข้อ candidate | 0 แถว |
| เทคโนโลยีผลิตภัณฑ์ชีวภาพฯ 2568 (ตรี) | admission | 632efcb5-4220-4bea-837a-e47a49825e3f | candidate · reviewed_by ว่าง | 2 ข้อ candidate | 0 แถว |
| สาธารณสุขศาสตร์ ไม่ระบุปี (ตรี) | total_credits | 87c0f7bc-052f-47c3-812d-949becf6f574 | candidate · reviewed_by ว่าง | — | 0 แถว |

ตรวจสามชั้น:
1. **ด่าน post-check ใน transaction** — `RAISE EXCEPTION` ถ้า field ใดไม่ใช่ candidate / มี reviewed_by / มี decision / รายการใดไม่ใช่ candidate
2. **diff snapshot รายแถว** — แถว field_value และทุกข้อของรายการของ 5 หน่วย **เหมือน before ทุกคอลัมน์**
3. **query read-only หลัง COMMIT** — status candidate, reviewed_by ว่าง, `review_decisions` ของ (เอกสาร, field) = 0 ทั้ง 5 หน่วย

---

## 3. ก่อนเขียน

### 3.1 สถานะ production (read-only pre-check)

| ตรวจ | ค่าที่ต้องเป็น | ผล |
|---|---|---|
| deployed commit | 8d6d271 | ✔ `8d6d271` (image `5fb3ef40…`, restarts 0) |
| STRUCTURED_ANSWERS | shadow | ✔ `.env` และในคอนเทนเนอร์ = `shadow` |
| publication | d0311dd5… | ✔ `d0311dd5-ba1d-44dc-8460-66542394cefa` (verified_any, publications = 3) |
| review_decisions | 14 | ✔ 14 (active 14) |
| live values / list_items | 100 / 90 | ✔ 100 / 90 |
| extraction run ใหม่ | ไม่มี | ✔ `extraction_runs` 31 แถว fingerprint `22c5c2f1…` เท่าก่อน P1 · `evidence` 787 `9325bbcb…` · `document_pages` 4129 `976a1cc9…` เท่าเดิม |

### 3.2 ตรวจ key / ความเป็นปัจจุบันของทั้ง 28 หน่วย

- **CLI `pipeline.mko.review` รันกับ production ตรงๆ ไม่ได้** เพราะ `database_url()` ปฏิเสธ host ที่ไม่ใช่ local โดยตั้งใจ ([run.py:49-54](pipeline/mko/run.py:49)) — ไม่ได้เลี่ยงด่านนี้ (เหมือน P1/P2)
- **Reference run บน local DB** (ข้อมูล mko เท่ากับ production ก่อน P1) ใน transaction เดียวแล้ว rollback:
  1. เล่น decision ของ P1 (5) และ P2 (9) ซ้ำด้วย `review.apply_file` จริง
  2. state md5 ได้ `183cf602…` / `0241e85a…` และ content md5 `dfb1fd1d…` / `3579089b…` **ตรงกับ production ทุกค่า** — แปลว่าค่า ข้อความ สถานะ และ run ของทุกแถวเหมือน production
  3. `current_values` + `review_key` ของทั้ง 28 หน่วย **ตรงกับ preview ทุกหน่วย** (document_id, run_id, field_value_id, value_key) · status candidate · reviewed_by ว่าง · decision เดิม 0 แถวทุกหน่วย
  4. `apply_file` จริงกับ CSV 23 แถว → `recorded 23, stale 0, stale_rows 0, applied 37` (37 = decision ที่ active ทั้งหมดหลังรอบนี้)
  5. เก็บผลเป็นค่าที่ production ต้องได้ → rollback → ตรวจ fingerprint local กลับเป็นเหมือนเดิม
- **ไม่มีหน่วยใด stale หรือ mismatch**

### 3.3 Backup / snapshot (บน server `~/backups/`, สิทธิ์ 600)

| ไฟล์ | รายละเอียด | SHA-256 |
|---|---|---|
| `mko_pre_p3_review_20260916T205813Z.dump` | `pg_dump -Fc --data-only` 7 ตาราง: review_decisions, field_values, list_items, curricula, publications, published_values, published_list_items · 79,426 bytes · `pg_restore -l` = 7 TABLE DATA · `sha256sum -c` OK | `70760e32f7bda9c35eb5e30be54de5717c0663c2c4fefe29958e7d1bc98f1187` |
| `mko_p3_before_20260916T205813Z_field_values.tsv` | 403 แถว (id, run, field, status, value_int, md5(value_text), reviewed_by, reviewed_at, reason) | `fcd3f65878a81feacdd19ac4715f73f1463b7e12a3ba2a5f648058e3bd38ebbe` |
| `mko_p3_before_20260916T205813Z_list_items.tsv` | 294 แถว (id, run, item_type, seq, status, md5(text), reviewed_by, reviewed_at, reason) | `c072fb9a6379ca927468f107b38544bd85b6bbb189d7fedea3dbecd0408381d5` |
| `mko_p3_before_20260916T205813Z_other.tsv` | review_decisions / curricula / publications / จำนวน published / live | `fef929d0fb73e844d03b9b703eeeeef2a128725fc1d63c6c747da92826a4c5c0` |

**หมายเหตุ snapshot:** ตัวคั่นคอลัมน์ในไฟล์ TSV เป็นข้อความ `$'\t'` แทนอักขระ tab (การ quote ในสคริปต์ snapshot ส่งข้อความนี้ให้ `psql -F`) — ข้อมูลครบทุกคอลัมน์ ตัวคั่นมีจำนวนเท่ากันทุกแถว (field_values / list_items 8 ต่อแถว) และไม่มี tab จริงในไฟล์ จึงอ่านได้ไม่กำกวม สคริปต์ diff และ rollback อ่านด้วยตัวคั่นนี้ · dump (`pg_dump -Fc`) ไม่ได้รับผลกระทบ

---

## 4. Transaction

| รายการ | ค่า |
|---|---|
| SQL | `~/backups/mko_p3_review_apply_20260916T205813Z.sql` · 272 บรรทัด · SHA-256 `cd3c6def61ab5a2712a6c96c0dcf4022c6094d1cc96cd28c004f4202a6abd770` (ตรงกันทั้ง local และ server) |
| ทำตาม | `apply_file` ([review.py:185-202](pipeline/mko/review.py:185)): supersede + INSERT decision → `reapply` ([review.py:126-158](pipeline/mko/review.py:126)): อัปเดต status / reviewed_by / reviewed_at / reason ของ field_value และทุกข้อของรายการ |
| ด่านก่อนเขียน (`DO $guard$`) | review_decisions = 14 · state md5 ของ field_values / list_items = ค่า pre-check · extraction_runs ไม่เปลี่ยน · publication = d0311dd5 และ live 100/90 · ต่อหน่วย (28 หน่วย): SHA ของเอกสาร, run ล่าสุด, field_value (id/run/field/candidate/value_int/md5 value_text/reviewed_by ว่าง), md5 + จำนวนข้อของรายการ, ไม่มี decision เดิม |
| ด่านหลังเขียน (`DO $post$`) | จำนวน decision / field_values / list_items ที่ human ตรวจ = reference · KEEP_REVIEW 5 หน่วยยัง candidate และไม่มี decision · state md5 = reference (`5bbdbfb1…` / `e44351e4…`) · **content md5 ของ field_values และ list_items = ก่อนเขียน** · publication และ live 100/90 ไม่เปลี่ยน |
| log | `~/backups/mko_p3_review_apply_20260916T205813Z.log` SHA-256 `e25e5d37a813dcc4a8b8be942d0664d17f832b7e92bfcdd3f381c3aac9d37a2e` |
| **ผล** | `BEGIN` · `DO` (guard ผ่าน) · `UPDATE 0` ×23 (supersede — ไม่มี decision เดิม) · `INSERT 0 1` ×23 · `UPDATE 1` ×23 (field_values) · `UPDATE` รายการ 20 ชุด: 11 ×1, 6 ×1, 5 ×3, 4 ×4, 3 ×3, 2 ×1, 1 ×7 = 66 ข้อ · `DO` (post-check ผ่าน) · **`COMMIT`** · psql exit 0 |

---

## 5. ตรวจหลัง Apply

### 5.1 จำนวน ก่อน → หลัง

| รายการ | ก่อน | หลัง | ต่าง |
|---|---|---|---|
| review_decisions | 14 | **37** (active 37) | **+23** |
| field_values verified (human) | 13 | **36** | **+23** |
| field_values rejected (human) | 1 | 1 | 0 |
| field_values candidate | 175 | 152 | −23 |
| field_values verified (auto) / not_found | 167 / 47 | 167 / 47 | 0 |
| list_items verified (human) | 59 | **125** | **+66** (career 14, admission 15, objective 37) |
| list_items candidate | 169 | 103 | −66 |
| list_items verified (auto) / rejected (human) | 62 / 4 | 62 / 4 | 0 |
| publication | d0311dd5… (3 publications) | **d0311dd5…** (3) | ไม่เปลี่ยน |
| `v_live_values` / `v_live_list_items` | 100 / 90 | **100 / 90** | ไม่เปลี่ยน |
| published_values / published_list_items | 295 / 174 | 295 / 174 | ไม่เปลี่ยน |
| curricula | published 23 / draft 1 | published 23 / draft 1 | ไม่เปลี่ยน |

### 5.2 Diff snapshot รายแถว (before vs after)

| ตรวจ | ผล |
|---|---|
| field_values ที่เปลี่ยน | **23 แถว = id ของ 23 หน่วยที่อนุมัติพอดี** · candidate/ว่าง → verified/human:project-owner ทุกแถว |
| คอลัมน์ที่เปลี่ยนใน field_values | เฉพาะ `status, reviewed_by, reviewed_at, reason` |
| list_items ที่เปลี่ยน | **66 แถวใน 20 รายการ = 20 รายการที่อนุมัติพอดี** (careers 2 + admission 10 + objectives 8) · ทุกข้อของแต่ละรายการเปลี่ยนครบ |
| คอลัมน์ที่เปลี่ยนใน list_items | เฉพาะ `status, reviewed_by, reviewed_at, reason` |
| **extracted content** | `value_int`, md5(`value_text`) ของทั้ง 403 แถว และ `seq`, md5(`text`) ของทั้ง 294 แถว **เหมือนเดิมทุกแถว** · content md5 หลัง COMMIT เท่ากับก่อนเขียน (ตรวจในด่าน post-check ด้วย) |
| ตารางอื่น | ไม่มีแถวหายหรือเปลี่ยน · เพิ่มเฉพาะ review_decisions 23 แถว ที่ (document, field, value_key) ตรงกับ 23 หน่วย · verified · project-owner · active |
| `reviewed_at` / `decided_at` | ค่าเดียว `2026-09-16 20:58:50.558794+00` |

### 5.3 ตรวจเป็นพิเศษ (query read-only หลัง COMMIT: decision → เอกสาร → course → curriculum)

| ตรวจ | ผล |
|---|---|
| admission ที่ VERIFIED ตรง programme / year / degree | ✔ 10 decision ผูกกับเอกสารของหลักสูตรตัวเอง เช่น attm65.pdf → การแพทย์แผนไทยประยุกต์บัณฑิต **พ.ศ. 2565**, it66.pdf → เทคโนโลยีสารสนเทศ **2566** (3 ข้อ), ds2564.pdf → **ศิลปศาสตรบัณฑิต** คหกรรมศาสตร์ **2564** · จำนวนข้อ verified = จำนวนข้อของรายการทุกหน่วย |
| **ป.โท / ป.เอก เกษตรฯ 2568 แยกกัน** | ✔ agri68_master.pdf → **วิทยาศาสตรมหาบัณฑิต** (admission 3 ข้อ, objectives 5 ข้อ) · agri68_phd.pdf → **ปรัชญาดุษฎีบัณฑิต** (admission 2 ข้อ, objectives 4 ข้อ) · คนละ course / เอกสาร / field_value / run |
| **edition_year 2569 ทั้ง 3 ฉบับถูก edition** | ✔ cook69.pdf → การประกอบอาหารฯ **(พ.ศ. 2569)** = 2569 · ma69.pdf → คณิตศาสตร์ **(พ.ศ. 2569)** = 2569 · animation69.pdf → คอมพิวเตอร์แอนิเมชันฯ **(พ.ศ. 2569)** = 2569 — ไม่แตะฉบับ 2564 ของคณิตศาสตร์และแอนิเมชัน |
| **objectives 8 หน่วยถูกฉบับ** | ✔ atm 2564 (5) · ป.เอก 2568 (4) · ป.โท 2568 (5) · cook69 2569 (4) · ma69 2569 (4) · animation69 2569 (6) · ds2564 2564 (5) · ht61 2561 (4) |
| **careers คหกรรมศาสตร์ / เทคโนโลยีการจัดการสุขภาพถูกฉบับ** | ✔ ds2564.pdf → คหกรรมศาสตร์ **2564** 11 ข้อ · ht61.pdf → เทคโนโลยีการจัดการสุขภาพ **2561** 3 ข้อ |
| cross-programme / cross-edition | ✔ `list_items` ที่ document ≠ document ของ run = **0** · `field_values` ที่ document ≠ run หรือ curriculum ≠ course ของเอกสาร = **0** · ทุก decision `curriculum.course_id = course ของเอกสาร` |
| ฉบับที่ถูกแทน (fs61, en60) | ✔ ไม่มี decision และไม่มีแถวเปลี่ยน |

### 5.4 Production health

| ตรวจ | ผล |
|---|---|
| STRUCTURED_ANSWERS | ✔ `shadow` (`.env` และคอนเทนเนอร์) |
| backend | ✔ commit 8d6d271 · restarts 0 · ไม่ได้ restart (started 2026-09-16T17:48:25Z) |
| `https://stpnru-advisor.duckdns.org/api/health` | ✔ 200 |

---

## 6. Known issue (บันทึกไว้ ไม่ได้แก้)

**careers การจัดการสิ่งแวดล้อมฯ 2565 (en65.pdf, P2) — glyph "น้ า"**
- ข้อ 1 และ 2 ของรายการที่ verified ใน P2 มีข้อความ "มลพิษน้ า" ส่วนต้นฉบับพิมพ์ "มลพิษน้ำ" (text layer แยกสระอำ)
- ตรวจหลัง apply: ทั้งสองข้อยังเป็น `verified / human:project-owner` และยังมีข้อความนี้ — **รอบนี้ไม่ได้แก้** extraction / normalize / decision เดิม ตามที่สั่ง
- ปัจจุบันรายการนี้อยู่ใน live แล้ว (publication d0311dd5) ต้องตัดสินแยกในรอบต่อไป (ดูตัวเลือกใน [MKO_PHASE2_P3_REVIEW_PREVIEW.md](docs/MKO_PHASE2_P3_REVIEW_PREVIEW.md) ข้อ 5.2)

---

## 7. Rollback (เตรียมไว้ ยังไม่ได้รัน)

**ทางที่ 1 — ย้อนเฉพาะรอบ P3:** `~/backups/mko_p3_review_rollback_20260916T205813Z.sql`
(SHA-256 `e237a966caed5a35e3584a0992eb9cb9c5aa4b0cb60287f89a0e77fcab9353e8`, 124 บรรทัด, สิทธิ์ 600)
- คืน 23 `field_values` และ 66 `list_items` เป็นค่าก่อนเขียน (status candidate, reviewed_by / reviewed_at / reason ว่าง — จาก before snapshot)
- ลบ 23 review_decisions ของรอบ P3 ด้วย id
- ตรวจใน transaction ก่อน COMMIT: decision เหลือ 14 (P1+P2), field_values human verified 13, list_items human verified 59, publication ยังเป็น d0311dd5
- **ไม่แตะ** decision ของ P1/P2 และไม่แตะ publication

```
docker exec -i course-advisor-system-postgres-1 psql -U postgres -d course_advisor -X \
  < ~/backups/mko_p3_review_rollback_20260916T205813Z.sql
```

**ทางที่ 2 — backup:** `~/backups/mko_pre_p3_review_20260916T205813Z.dump` (ข้อ 3.3) — restore data-only ของ 7 ตาราง mko

การย้อนกลับไม่กระทบคำตอบผู้ใช้ เพราะยังไม่ได้ publish และ `STRUCTURED_ANSWERS` ยังเป็น shadow

---

## 8. ผลที่จะเกิดถ้า publish ในอนาคต (ยังไม่ได้รับอนุมัติ)

ถ้า publish ด้วยนโยบายเดิม `verified_any` (คาดการณ์จาก preview ข้อ 12.3):
- live values 100 → **103** (edition_year 2569 สามฉบับ)
- live list_items 90 → **156** (careers +14, admission +15, objectives +37)
- coverage ฉบับล่าสุด 43/80 → **66/80** · ทั้งคลัง 59/120 → **82/120**
- **ไม่เข้า live:** KEEP_REVIEW 5 หน่วย (ยัง candidate)
- ตัวเลขจริงต้องยืนยันด้วย publication preview ก่อน COMMIT ในรอบ publish

---

## 9. สิ่งที่ยังไม่ได้ทำ (ตามที่ยังไม่อนุมัติ)

- publish / เปลี่ยน publish policy
- deploy / `STRUCTURED_ANSWERS=on` / Phase 3 ของระบบ / P4
- แก้ extraction / normalize / schema / routing / RAG / prompt
- แก้ known issue en65 careers
- decision ของ KEEP_REVIEW 5 หน่วย
- commit / push — รายงานนี้ รายงาน preview P3 และ rollout report ของ comparator ยังไม่ commit

**ข้อมูลฝั่ง local:** ไม่เปลี่ยน — reference run ถูก rollback และตรวจ fingerprint แล้ว

**ไฟล์ของรอบนี้บน server (`~/backups/`, สิทธิ์ 600):** `mko_pre_p3_review_20260916T205813Z.dump(.sha256)`, `mko_p3_before_20260916T205813Z_*`, `mko_p3_after_20260916T205813Z_*`, `mko_p3_review_apply_20260916T205813Z.sql/.log`, `mko_p3_review_rollback_20260916T205813Z.sql`, `mko_p3_snapshot.sh`
