# MKO Phase 2 — P2 Controlled Publication

**สรุป:** สร้าง publication ใหม่ด้วยนโยบายเดิม `verified_any` สำเร็จใน transaction เดียว
- เข้า live เพิ่มเฉพาะข้อมูล P2 ที่เพิ่งผ่าน human review: careers 7 ฉบับ 37 ข้อ และ total_credits 2 ค่า
- ค่าเดิมทั้งหมด (auto + P1) อยู่ครบ ไม่มีค่าใดหายไป
- ATTM 2565 careers, Math 2564 careers และ cs66_brief ที่ rejected **ไม่เข้า** live
- **ผู้ใช้ยังได้คำตอบจากระบบเดิม** เพราะ `STRUCTURED_ANSWERS=shadow`
- ไม่ได้ deploy ไม่ได้แก้ extraction/code ไม่ได้เปลี่ยน policy ไม่ได้ review เพิ่ม ไม่ได้ commit/push

เวลาเป็น UTC

---

## 1. Publication

| รายการ | ค่า |
|---|---|
| previous publication id | `9b382588-db00-4e80-9935-953fc4559ef7` (2026-09-15 23:32:20Z, P1) |
| **new publication id** | **`d0311dd5-ba1d-44dc-8460-66542394cefa`** (2026-09-16 07:47:49Z) |
| policy | `verified_any` (เดิม ไม่เปลี่ยน) |
| published_by / parser_version | `project-owner` / `mko-phase1-2026.09.15` |
| conflicts | ไม่มี |
| summary | courses 23 · total_credits 23, edition_year 20, revision_type 20, program_name_th/en 7, degree_abbr_th/en 7, degree_level 7, degree_name_th/en 1 · list_items: career 55 (9 รายการ), objective 35 (7 รายการ) · values_reviewed_by: auto 97, human 3 |

publication เดิมทั้งสองชุด (`92e34932…`, `9b382588…`) ยังอยู่ในฐานข้อมูล ไม่ได้ลบ — `v_live_*` ชี้ไปที่ชุดล่าสุดตาม design

---

## 2. Before / after

| รายการ | ก่อน | หลัง |
|---|---|---|
| `mko.v_live_values` | 98 | **100** |
| `mko.v_live_list_items` | 53 | **90** |
| — careers | 18 ข้อ (2 ฉบับ) | **55 ข้อ (9 ฉบับ)** |
| — objectives | 35 ข้อ (7 ฉบับ) | 35 ข้อ (7 ฉบับ) |
| `mko.publications` | 2 | 3 |
| `mko.curricula` | published 21 / draft 3 | **published 23 / draft 1** |
| live facts ที่ยืนยันโดยคน | 1 ค่า + 22 ข้อ | **3 ค่า + 59 ข้อ** |

---

## 3. ค่าที่เพิ่มเข้า live (ตรงกับที่อนุมัติทุกรายการ)

**careers 7 ฉบับ / 37 ข้อ** — ทุกข้อ `reviewed_by = human:project-owner`

| หลักสูตร / ฉบับ | source | หน้า | จำนวน |
|---|---|---|---|
| การจัดการเทคโนโลยีการเกษตรและบริหารทรัพยากรชุมชน (ป.โท) 2568 | agri68_master.pdf | 8 | 6 |
| การจัดการเทคโนโลยีการเกษตรและบริหารทรัพยากรชุมชน (ป.เอก) 2568 | agri68_phd.pdf | 8 | 6 |
| เทคโนโลยีผลิตภัณฑ์ชีวภาพกับการประกอบธุรกิจ 2568 | bio2568.pdf | 9 | 5 |
| วิทยาศาสตร์เครื่องสำอาง 2566 | cos66.pdf | 7–8 | 7 |
| เทคโนโลยีอาหารและความเป็นผู้ประกอบการสมัยใหม่ 2566 | food66.pdf | 8 | 4 |
| การจัดการสิ่งแวดล้อมและทรัพยากรธรรมชาติ 2565 | en65.pdf | 8 | 6 |
| การจัดการเทคโนโลยีการเกษตรสมัยใหม่ 2564 | atm.pdf | 8 | 3 |

**total_credits 2 ค่า**

| หลักสูตร / ฉบับ | ค่า | source |
|---|---|---|
| การประกอบอาหารและการบริการอาหาร 2569 | **128** | cook69.pdf หน้า 1 |
| คอมพิวเตอร์แอนิเมชันและมัลติมีเดีย 2569 | **127** | animation69.pdf หน้า 1 |

**ค่าจาก publication เดิมที่ต้องคงอยู่ — คงอยู่ครบ**
- ค่าจาก publication `9b382588…` ที่หายไปจาก live = **0 values / 0 list items**
- รวมถึงของ P1: คณิตศาสตร์ 2569 = 124, careers CS 2566 (9), careers IT 2566 (9), objectives CS 2566 (4)
- และค่าที่ยืนยันอัตโนมัติเดิม 97 ค่า + objectives 31 ข้อ

**Preview ก่อน COMMIT** (จากการรัน `publish()` จริงบนข้อมูลชุดเดียวกัน) ตรงกับผลจริงทุกแถว — md5 ของ published_values (`9ad8862d…`) และ published_list_items (`9f4ecac0…`) ถูกตรวจใน transaction ก่อน COMMIT พร้อมด่านตรวจว่า publication เดิมไม่เปลี่ยน

---

## 4. Leakage / integrity checks

| ข้อ | ผล |
|---|---|
| publication ใหม่เป็น current | ✔ `v_live_publication` = `d0311dd5…` |
| ไม่มี candidate / needs_review / rejected เข้า live | ✔ แถว live ทั้ง **100 values + 90 items** ผูกกับแถวต้นทางสถานะ `verified` ทั้งหมด |
| ATTM 2565 careers | ✔ 0 แถวใน live (ยัง candidate) |
| Math 2564 careers | ✔ 0 แถวใน live (ยัง candidate) |
| cs66_brief (rejected) | ✔ 0 แถวทั้ง values และ list items |
| objectives ของ ATTM 2565 ที่ verified อัตโนมัติ | ✔ ยัง live 6 ข้อ (ไม่ถูกลบโดยไม่ตั้งใจ) |
| cross-edition mixing | ✔ 0 แถวทั้งสองตาราง (course ของแถว = course ของเอกสารเสมอ) |
| ป.โท / ป.เอก เกษตรฯ 2568 | ✔ แยกกัน: ป.เอก 6 ข้อจาก agri68_phd.pdf, ป.โท 6 ข้อจาก agri68_master.pdf |
| curricula | ✔ เปลี่ยนสถานะ 2 ฉบับ (การประกอบอาหารฯ 2569, คอมพิวเตอร์แอนิเมชันฯ 2569) draft → published · อีก 21 แถวเป็นการรีเฟรช timestamp ตามขั้น publish เดิม |

---

## 5. ตรวจ structured service โดยตรง (อ่านอย่างเดียว ในคอนเทนเนอร์ backend)

| ข้อ | คำถาม | ผล |
|---|---|---|
| A | การประกอบอาหารฯ พ.ศ. 2569 กี่หน่วยกิต | answered **128** · cook69.pdf หน้า 1 · human:project-owner |
| B | คอมพิวเตอร์แอนิเมชันฯ พ.ศ. 2569 กี่หน่วยกิต | answered **127** · animation69.pdf หน้า 1 (กรองปีจาก 2 ฉบับได้ถูกฉบับ) |
| C | วิทยาศาสตร์เครื่องสำอาง อาชีพ | answered **7 ข้อ** · cos66.pdf หน้า 7–8 · แจ้งว่าฉบับ 2561 ยังไม่มีข้อมูลที่ผ่านการตรวจ |
| D | เทคโนโลยีผลิตภัณฑ์ชีวภาพฯ อาชีพ | answered **5 ข้อ** · bio2568.pdf หน้า 9 |
| E | การจัดการสิ่งแวดล้อมฯ อาชีพ | answered **6 ข้อ** · en65.pdf หน้า 8 |
| F | การจัดการเทคโนโลยีการเกษตรสมัยใหม่ อาชีพ | answered **3 ข้อ** · atm.pdf หน้า 8 |
| G | การแพทย์แผนไทยประยุกต์ อาชีพ | **no_data** "ยังไม่มีข้อมูลที่เผยแพร่" — ไม่แสดง 3 ข้อที่ยัง candidate |
| H | คณิตศาสตร์ อาชีพ | **no_data** |

ทุกข้อที่ answered อ้าง `publication_id = d0311dd5…`

### 5.1 ข้อสังเกตสำคัญ: ป.โท / ป.เอก เกษตรฯ 2568 (ต้องแก้ก่อนเปิด `on`)

ตรวจเพิ่มด้วยคำถามที่ระบุระดับปริญญาชัดเจน:

| คำถาม | structured ตอบ |
|---|---|
| "หลักสูตร**วิทยาศาสตรมหาบัณฑิต** สาขาวิชาการจัดการเทคโนโลยีการเกษตรฯ จบไปทำอาชีพอะไร" | รายการของ **ป.เอก** (agri68_phd.pdf) 6 ข้อ พร้อมบรรทัด "มีข้อมูลของ หลักสูตรวิทยาศาสตรมหาบัณฑิต… ด้วย ระบุปีของหลักสูตรเพื่อดูฉบับนั้น" |
| "หลักสูตร**ปรัชญาดุษฎีบัณฑิต** …" | รายการของ ป.เอก (ถูกต้อง) |
| ไม่ระบุระดับ | รายการของ ป.เอก + บรรทัดแจ้งว่ามีฉบับ ป.โท ด้วย |

- **ไม่ใช่การรวมข้อมูลข้ามฉบับ** — คำตอบอ้างเอกสารเดียว 6 ข้อ และกำกับชื่อหลักสูตรเต็ม (ป.เอก) ไว้ชัดเจน
- **แต่เป็นการเลือกฉบับผิดเมื่อผู้ใช้ระบุระดับปริญญา** เพราะ
  - `resolve_scopes` จับคู่ด้วย "ชื่อสาขา" เท่านั้น ทั้งสองระดับใช้ชื่อสาขาเดียวกัน
  - ตัวกรองที่มีคือ "ปี" ซึ่งทั้งคู่เป็น 2568 จึงแยกไม่ได้
  - `curriculum_facts.lookup` เลือกฉบับแรกตามลำดับ (ปีใหม่สุด แล้วเรียงตามชื่อ) ซึ่งคือ ป.เอก
- ภายใต้ shadow ยังไม่กระทบผู้ใช้ แต่ต้องแก้ก่อนพิจารณา `STRUCTURED_ANSWERS=on` (การแก้อยู่นอกขอบเขตรอบนี้)

---

## 6. Shadow validation (8 คำขอผ่าน `/api/chat`)

ส่งจริง 8 ครั้ง เว้นระยะ 8 วินาที เวลา 07:48:50–07:50:12Z · ไม่ได้รัน behaviour_check และไม่มี batch test

| ข้อ | HTTP / เวลา | structured (shadow) | comparison | หมายเหตุ |
|---|---|---|---|---|
| A | 200 / 3.1s | answered 128 · cook69.pdf | **agree** (expected [128] พบ [128]) | |
| B | 200 / 3.0s | answered 127 · animation69.pdf | **agree** | |
| C | 200 / 3.2s | answered 7 ข้อ · cos66.pdf | **agree** (covered 7/7) | |
| D | 200 / 3.8s | answered 5 ข้อ · bio2568.pdf | **agree** (covered 5/5) | |
| E | 200 / 4.5s | answered 6 ข้อ · en65.pdf | **agree** (covered 6/6) | |
| F | 200 / 4.2s | answered 3 ข้อ · atm.pdf | **agree** (covered 3/3) | |
| G | 200 / 4.4s | **no_data** | not_compared | ระบบเดิมตอบจากเอกสาร (RAG) ตามปกติ |
| H | 200 / 0.2s | **no_data** | not_compared | คำตอบผู้ใช้มาจากแคชของรอบ P1 (คำถามเดิม) — shadow ยังบันทึกปกติ |

- **บันทึกครบ:** `mko.shadow_answers` เพิ่ม 8 แถว (53 → 61)
- **publication ที่อ้างอิง:** 6 แถวที่ answered อ้าง `d0311dd5…` ทั้งหมด (แถว no_data ไม่มี publication)
- **latency:** 3–5 ms
- **คำตอบที่ผู้ใช้เห็นยังมาจากระบบเดิมทุกข้อ** — `STRUCTURED_ANSWERS=shadow`
- `chat_messages` +16 (8 คำขอ × 2 ข้อความ)

---

## 7. Production health

| ตรวจ | ผล |
|---|---|
| backend | `STRUCTURED_ANSWERS=shadow`, restarts 0, image เดิม (ไม่ได้ deploy) |
| `/health` | `{"status":"ok"}` |
| log backend (20 นาทีล่าสุด) | error / traceback = 0 |
| ตาราง public | courses 24, course_chunks 9039 ไม่เปลี่ยน |
| ข้อมูลที่สกัด | `field_values` / `list_items` ไม่ถูกแตะในรอบนี้ (publication อ่านอย่างเดียว) |

---

## 8. Rollback

**ทางที่ 1 — ย้อน publication นี้:** `~/backups/mko_p2_publication_rollback_20260916T074749Z.sql`
(SHA-256 `1d385b9a20a94966876addbe4787201949276ed312b95d25cd6de189f12cf706`, สิทธิ์ 600, **ยังไม่ได้รัน**)
- `DELETE FROM mko.publications WHERE id = 'd0311dd5…'` — published rows ถูกลบตาม cascade และ `v_live_*` กลับไปใช้ `9b382588…` (98/53)
- คืน `mko.curricula` 23 แถว โดยสองฉบับปี 2569 กลับเป็น draft
- ตรวจใน transaction ก่อน COMMIT: live = `9b382588…`, publications = 2, live counts 98/53, curricula published 21

**ทางที่ 2 — backup:** `~/backups/mko_pre_p2_publication_20260916T074342Z.dump`
(`pg_dump -Fc --data-only` 7 ตาราง · SHA-256 `21a0176fc5128c213a654ce59173fdae30ffabb8749ca88ab576e832bd6d6842` · `sha256sum -c` OK)

การย้อนกลับไม่กระทบคำตอบผู้ใช้ เพราะยังเป็น shadow

---

## 9. ที่ยังเป็น no_data และข้อจำกัดที่เหลือ

**ยัง no_data (ตามที่ตั้งใจ):**
- careers ของ **การแพทย์แผนไทยประยุกต์ 2565** — KEEP_REVIEW เพราะย่อหน้าเงื่อนไข "ต้องได้รับใบอนุญาตประกอบวิชาชีพ" ไม่ได้อยู่ในรายการที่สกัด
- careers ของ **คณิตศาสตร์ 2564** — KEEP_REVIEW จาก P1 (ช่องว่างจากการตัดบรรทัดในข้อ 8.5)
- careers ของอีก 4 ฉบับที่เลื่อนจาก P2 (คหกรรมศาสตร์ 2564, วิทย์อาหาร 2561, เทคโนโลยีสุขภาพ 2561, วิทย์สิ่งแวดล้อม 2560) และของสาธารณสุขศาสตร์
- careers ของฉบับเก่าที่ยังไม่ได้ตรวจ เช่น CS 2561, IT 2561, เครื่องสำอาง 2561 — คำตอบ structured จะมีบรรทัด "ยังไม่มีข้อมูลที่ผ่านการตรวจของ …" กำกับ
- **admission ทั้ง 24 ฉบับ** และ objectives อีก 17 ฉบับ ยังไม่มีใน live

**ข้อจำกัดที่ต้องจัดการก่อนพิจารณา `STRUCTURED_ANSWERS=on`:**
1. **ป.โท / ป.เอก ชื่อสาขาเดียวกันปีเดียวกัน** — เลือกฉบับผิดเมื่อผู้ใช้ระบุระดับปริญญา (ข้อ 5.1)
2. **สาธารณสุขศาสตร์** ยังเป็น draft ฉบับเดียวที่เหลือ และเอกสารเป็นหน้าเว็บที่ไม่มีปี จึงกรองด้วยปีไม่ได้
3. **นโยบาย publish** ยังเป็น `verified_any` — live 100 ค่ายังมาจากกฎอัตโนมัติ 97 ค่า ถ้าจะใช้ `verified_human_only` ต้องตรวจค่าที่เหลือด้วยคน
4. **รายการถอยไปใช้ฉบับเก่า** เมื่อฉบับใหม่ไม่มีข้อมูล ยังเป็นพฤติกรรมที่ต้องตัดสินใจ (เช่น คณิตศาสตร์ 2569 ไม่มีหัวข้ออาชีพในเอกสาร)
5. **หลักฐาน shadow ยังน้อย** — 61 แถว ส่วนใหญ่เป็นการทดสอบของทีม ยังไม่มีข้อมูลการใช้งานจริงหลังข้อมูลชุดใหม่เข้า live

---

## 10. สิ่งที่ยังไม่ได้ทำ

- `STRUCTURED_ANSWERS=on` / Phase 3
- deploy / แก้ extraction code / เปลี่ยน publish policy
- review เพิ่ม (P3/P4, 6 หน่วย P2 ที่เลื่อน, ATTM 2565, Math 2564)
- commit / push — รายงานนี้และรายงานก่อนหน้ายังไม่ commit

**ข้อมูลฝั่ง local:** ไม่เปลี่ยน — reference run ถูก rollback แล้ว local จึงยังไม่มี review decisions และ publication ใหม่ (ต่างจาก production)
