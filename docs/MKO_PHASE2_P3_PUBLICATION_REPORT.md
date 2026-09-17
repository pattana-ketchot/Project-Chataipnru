# MKO Phase 2 — P3 Controlled Publication

**สรุป: publish สำเร็จ ตรงกับ preview ทุกจุด ไม่พบ regression จึงไม่ได้ rollback**
- publication ใหม่ **`7999a1c2-e2fd-4b19-98d1-b50b3212f8d9`** (verified_any) เป็น live แทน `d0311dd5-ba1d-44dc-8460-66542394cefa`
- live **100 → 103 values** และ **90 → 156 list_items** — เพิ่มเฉพาะ P3: edition_year +3, careers +14, admission +15, objectives +37
- ข้อมูล live เดิมจาก auto / P1 / P2 **อยู่ครบทุกแถวและไม่เปลี่ยน** · KEEP_REVIEW 5 หน่วย **ไม่เข้า live**
- coverage: ฉบับล่าสุด **66/80** · ทั้งคลัง **82/120**
- `STRUCTURED_ANSWERS=shadow` · ไม่มี review decision เพิ่ม (ยัง 37) · ไม่ได้ deploy / แก้ extraction / normalize / schema / routing / RAG / prompt · ไม่ได้ใช้ Gemini · ไม่ได้รัน behaviour_check · ไม่ได้ push

เวลาเป็น UTC · published_at = `2026-09-16 21:40:11.007116+00`

---

## 1. ก่อน publish

### 1.1 สถานะ production (read-only)

| ตรวจ | ต้องเป็น | ผล |
|---|---|---|
| commit / flag | 8d6d271 / shadow | ✔ `8d6d271` · `shadow` (.env และคอนเทนเนอร์) · restarts 0 |
| current publication | d0311dd5… | ✔ `d0311dd5-ba1d-44dc-8460-66542394cefa` (publications = 3) |
| review_decisions | 37 | ✔ 37 active 37 |
| P3 VERIFIED | 23 | ✔ 23 decision `decided_at = 2026-09-16 20:58:50.558794+00`, verified |
| human verified field_values | 36 | ✔ 36 |
| live values / list_items | 100 / 90 | ✔ 100 / 90 |
| KEEP_REVIEW 5 | candidate, ไม่มี decision | ✔ attm65 careers · ma64 careers · ph_web careers · bio2568 admission · ph_web total_credits — candidate ทั้งหมด decision 0 |
| state หลัง P3 apply | ไม่เปลี่ยน | ✔ field_values / list_items md5 = `5bbdbfb1…` / `e44351e4…` (เท่ากับหลัง apply) · extraction_runs 31 `22c5c2f1…` |
| fingerprint ของ live ปัจจุบัน | บันทึกไว้ | published_values 100 `9ad8862d…` · published_list_items 90 `9f4ecac0…` |

### 1.2 Backup / snapshot (`~/backups/`, สิทธิ์ 600)

| ไฟล์ | รายละเอียด | SHA-256 |
|---|---|---|
| `mko_pre_p3_publication_20260916T213958Z.dump` | `pg_dump -Fc --data-only` 7 ตาราง: publications, published_values, published_list_items, curricula, review_decisions, field_values, list_items · 86,719 bytes · `pg_restore -l` = 7 TABLE DATA · `sha256sum -c` OK | `819af825a6ee8d8e22f73291b737110064b0efac9e2892634cc346cbd015abf6` |
| `mko_pub3_before_20260916T213958Z_curricula.tsv` | 24 แถว (id, course_id, status, published_at, updated_at) — ตัวคั่น tab จริง 5 คอลัมน์ทุกแถว | `486d114cb8dc9d2fd84f5b5028f91c7c7c74c0cd98449320c79ebe86f41e542c` |
| `mko_pub3_before_20260916T213958Z_publications.tsv` | 3 publications พร้อมจำนวนแถว | `1558d60e72744eee22e2e2e921e4fd06d2a01aef0da4f72ef8545d2460d3f2b0` |
| `mko_pub3_before_20260916T213958Z_live.tsv` | `d0311dd5… 100 90` | `6f8bf7533783e71069463a0c557881bd5e5cb9ad6332eb0b5c26ed4061125e9f` |

### 1.3 Publication preview (reference run บน local แล้ว rollback)

`pipeline.mko.publish` รันกับ production ตรงๆ ไม่ได้ (`database_url()` ปฏิเสธ host ที่ไม่ใช่ local — ไม่ได้เลี่ยง) จึงใช้ reference run บน local (ข้อมูล mko เท่ากับ production ก่อน P1) ใน transaction เดียว:

1. เล่น decision P1 + P2 ซ้ำด้วย `review.apply_file` จริง → state md5 = production ตอนสร้าง d0311dd5 → รัน `publish.publish` จริง → **ได้ 100 values `9ad8862d…` / 90 items `9f4ecac0…` ตรงกับ d0311dd5 บน production ทุกไบต์**
2. เล่น decision P3 ซ้ำ → state md5 `5bbdbfb1…` / `e44351e4…` **ตรงกับ production ปัจจุบัน**
3. รัน `publish.publish(human_only=False)` จริง = **preview ของ P3 publication** แล้วเทียบกับข้อ 1
4. rollback และตรวจว่า local กลับเป็นเหมือนเดิม (publications 1, review_decisions 0)

| ผล preview | ที่คาด | ได้ |
|---|---|---|
| values | 103 | ✔ 103 (`78941c9f…`) |
| list_items | 156 | ✔ 156 (`857b1ec4…`) |
| แถวของ d0311dd5 ที่หาย / เปลี่ยน | 0 / 0 | ✔ 0 / 0 (values และ items) |
| values ที่เพิ่ม | edition_year +3 | ✔ edition_year 3 |
| list_items ที่เพิ่ม | career 14 · admission 15 · objective 37 = 66 | ✔ 14 · 15 · 37 = 66 |
| reviewed_by ของทุกแถวที่เพิ่ม | human | ✔ `human:project-owner` ทั้งหมด |
| สถานะของแถวต้นทางทุกแถวใน publication | verified | ✔ values 103 verified · items 156 verified — **ไม่มี candidate / rejected / needs_review** |
| KEEP_REVIEW 5 ใน publication | 0 | ✔ 0 แถวทุกหน่วย (และไม่มีแถวของ course+field นั้นเลย) |
| cross-edition (document ≠ course) | 0 | ✔ 0 / 0 |
| conflicts | ไม่มี | ✔ [] |
| en65 careers | เหมือน d0311dd5 | ✔ 6 ข้อ md5 และ reviewed_by เท่าเดิม |

**ผล: PREVIEW MATCHES EXPECTATION = True** → สร้าง SQL สำหรับ production

---

## 2. Publish (transaction เดียว)

| รายการ | ค่า |
|---|---|
| SQL | `~/backups/mko_p3_publish_20260916T213958Z.sql` · 62 บรรทัด · SHA-256 `7cf85955a5f8db6f125be65530cbd330458e299e5e4ca03812ca7974b7cf2b58` (ตรงกัน local / server) |
| ทำตาม | `publish.publish()` ([publish.py:128-163](pipeline/mko/publish.py:128)): แถว publications → published_values (103 คีย์ run+field จาก preview, `status = 'verified'`) → published_list_items (36 รายการ run+item_type) → curricula ของ 23 หลักสูตร |
| ด่านก่อนเขียน | publication ปัจจุบัน = d0311dd5 และมี 3 · review_decisions 37 · P3 verified 23 · human verified field_values 36 · state md5 และ extraction_runs เท่า pre-check · fingerprint ของ d0311dd5 (100 / 90) · KEEP_REVIEW 5 candidate และไม่มี decision |
| ด่านหลังเขียน | publication ใหม่เป็น live และมี 4 · published_values / items = md5 ของ preview · live **103 / 156** · แถวของ d0311dd5 ไม่ถูกแตะ · **ทุกแถวของ d0311dd5 มีแถวเหมือนกันใน publication ใหม่** (values 100/100, items 90/90) · KEEP_REVIEW ไม่อยู่ใน live · cs66_brief ไม่อยู่ใน live · cross-edition 0 |
| log | `~/backups/mko_p3_publish_20260916T213958Z.log` SHA-256 `3aea65d09301ca0e98f313fee6319b3676656a4dc17b9aaaa31d0f165dd34039` |
| **ผล** | `BEGIN` · `DO` (guard ผ่าน) · `SELECT 1` · `INSERT 0 1` · `INSERT 0 103` · `INSERT 0 156` · `UPDATE 23` · `DO` (post ผ่าน) · **`COMMIT`** · psql exit 0 |
| publication ใหม่ | **`7999a1c2-e2fd-4b19-98d1-b50b3212f8d9`** · project-owner · verified_any · parser `mko-phase1-2026.09.15` |
| summary | courses 23 · values_by_field: edition_year 23, total_credits 23, revision_type 20, program_name_th/en 7, degree_level 7, degree_abbr_th/en 7, degree_name_th/en 1 · list_items_by_type: objective 72, career 69, admission 15 · lists_by_type: objective 15, career 11, admission 10 · values_reviewed_by: auto 97, human 6 · conflicts [] |

---

## 3. Rollback (เตรียมไว้ ยังไม่ได้รัน)

**ทางที่ 1:** `~/backups/mko_p3_publication_rollback_20260916T213958Z.sql` (SHA-256 `0523c59434b9e69350f65253937c01b53631f3b06cc191fa1abb1f09cceb0f6c`, 37 บรรทัด, สิทธิ์ 600)
- `DELETE` publication `7999a1c2…` (published rows cascade) → `d0311dd5…` กลับเป็น live (100 / 90)
- คืน `published_at` / `updated_at` ของ curricula 23 แถวจาก before snapshot (status ไม่เปลี่ยนในรอบนี้ — published 23 / draft 1 ทั้งก่อนและหลัง)
- ตรวจก่อน COMMIT: live = d0311dd5, publications 3, live 100/90, curricula published 23, **review_decisions ยัง 37** (rollback publication ไม่แตะผล review)

```
docker exec -i course-advisor-system-postgres-1 psql -U postgres -d course_advisor -X \
  < ~/backups/mko_p3_publication_rollback_20260916T213958Z.sql
```

**ทางที่ 2:** backup `mko_pre_p3_publication_20260916T213958Z.dump` (ข้อ 1.2)

**after snapshot:** `mko_pub3_after_20260916T213958Z_curricula.tsv` `d9e7f4fb…` · `_publications.tsv` `7385abfe…` · `_live.tsv` `92f23811…`

---

## 4. ผลหลัง publish

### 4.1 Live counts

| รายการ | ก่อน | หลัง |
|---|---|---|
| live publication | d0311dd5-ba1d-44dc-8460-66542394cefa | **7999a1c2-e2fd-4b19-98d1-b50b3212f8d9** |
| publications | 3 | 4 (d0311dd5 ยังอยู่ครบ 100 / 90 สำหรับ rollback) |
| `v_live_values` | 100 | **103** |
| `v_live_list_items` | 90 | **156** |
| review_decisions | 37 | 37 (ไม่เปลี่ยน) |
| curricula | published 23 / draft 1 | published 23 / draft 1 |

### 4.2 P3 additions (exact)

**values +3 (edition_year, human:project-owner):**

| หลักสูตร | ค่า | source |
|---|---|---|
| หลักสูตรศิลปศาสตรบัณฑิต สาขาวิชาการประกอบอาหารและการบริการอาหาร (พ.ศ. 2569) | 2569 | cook69.pdf หน้า 1 |
| หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาคณิตศาสตร์ (พ.ศ. 2569) | 2569 | ma69.pdf หน้า 1 |
| หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาคอมพิวเตอร์แอนิเมชันและมัลติมีเดีย (พ.ศ. 2569) | 2569 | animation69.pdf หน้า 1 |

**list_items +66 (human:project-owner):**

| หลักสูตร (ระดับ) | career | admission | objective | source |
|---|---|---|---|---|
| คหกรรมศาสตร์ 2564 (ศศ.บ.) | 11 | 1 | 5 | ds2564.pdf |
| เทคโนโลยีการจัดการสุขภาพ 2561 (วท.บ.) | 3 | 1 | 4 | ht61.pdf |
| การจัดการสิ่งแวดล้อมและทรัพยากรธรรมชาติ 2565 | — | 1 | — | en65.pdf |
| การจัดการเทคโนโลยีการเกษตรสมัยใหม่ 2564 | — | 1 | 5 | atm.pdf |
| การจัดการเทคโนโลยีการเกษตรฯ 2568 **(วิทยาศาสตรมหาบัณฑิต)** | — | 3 | 5 | agri68_master.pdf |
| การจัดการเทคโนโลยีการเกษตรฯ 2568 **(ปรัชญาดุษฎีบัณฑิต)** | — | 2 | 4 | agri68_phd.pdf |
| การแพทย์แผนไทยประยุกต์ 2565 | — | 1 | — | attm65.pdf |
| วิทยาศาสตร์เครื่องสำอาง 2566 | — | 1 | — | cos66.pdf |
| เทคโนโลยีสารสนเทศ 2566 | — | 3 | — | it66.pdf |
| เทคโนโลยีอาหารและความเป็นผู้ประกอบการสมัยใหม่ 2566 | — | 1 | — | food66.pdf |
| การประกอบอาหารและการบริการอาหาร 2569 | — | — | 4 | cook69.pdf |
| คณิตศาสตร์ 2569 | — | — | 4 | ma69.pdf |
| คอมพิวเตอร์แอนิเมชันและมัลติมีเดีย 2569 | — | — | 6 | animation69.pdf |
| **รวม** | **14** | **15** | **37** | **66** |

### 4.3 การคงข้อมูล live เดิม (auto / P1 / P2)

- **ไม่มีแถวหายหรือเปลี่ยน:** ทุก (course, field) ของ d0311dd5 100 แถว และทุก (course, item_type, seq) 90 แถว มีแถวเดียวกันใน 7999a1c2 (ค่า ข้อความ เอกสาร หน้า reviewed_by เท่าเดิม) — ตรวจทั้งใน preview และในด่าน post-check ของ transaction
- ที่มาของ values ใน live ใหม่: auto 97 + human 6 (P1: Math 2569 total_credits · P2: cook69 / animation69 total_credits · P3: edition_year 3)
- list ใน live ใหม่: careers 11 รายการ (P1: IT/CS 2566 · P2: 7 ฉบับ · P3: ds2564, ht61) · objectives 15 รายการ (auto 6 · P1: CS 2566 · P3: 8) · admission 10 รายการ (P3)
- **en65 careers (known issue "น้ า")** — 6 ข้อใน live ใหม่ md5 / reviewed_by เท่ากับใน d0311dd5 ทุกข้อ publication นี้ไม่ได้เปลี่ยนข้อมูลส่วนนี้

### 4.4 KEEP_REVIEW — ไม่เข้า live

| หน่วย | ใน live ใหม่ |
|---|---|
| การแพทย์แผนไทยประยุกต์ 2565 careers | 0 แถว (attm65 ใน live มีเฉพาะ objectives 6 ข้อของ auto และ admission 1 ข้อของ P3) |
| คณิตศาสตร์ 2564 careers | 0 แถว |
| สาธารณสุขศาสตร์ careers | 0 แถว |
| เทคโนโลยีผลิตภัณฑ์ชีวภาพฯ 2568 admission | 0 แถว (bio2568 careers ของ P2 และ objectives ของ auto ยังอยู่) |
| สาธารณสุขศาสตร์ total_credits | 0 แถว (ph_web.txt ไม่มีแถวใดใน live) |

### 4.5 ตรวจเฉพาะ

| ตรวจ | ผล |
|---|---|
| ป.โท / ป.เอก เกษตรฯ แยกกัน | ✔ agri68_master.pdf → วิทยาศาสตรมหาบัณฑิต: career 6, objective 5, admission 3 · agri68_phd.pdf → ปรัชญาดุษฎีบัณฑิต: career 6, objective 4, admission 2 · คนละ course |
| edition_year 2569 ถูกหลักสูตร | ✔ cook69 / ma69 / animation69 → หลักสูตร (พ.ศ. 2569) ของตัวเอง หน้า 1 |
| admission ถูก programme / year / degree | ✔ 10 รายการ source ตรงกับหลักสูตรของตัวเอง (หน้า 85, 91, 16, 19, 18, 11, 18, 20, 16, 16) |
| cross-edition / cross-programme | ✔ live values และ list_items ที่ document ไม่ใช่ของ course เดียวกัน = 0 / 0 |
| rejected cs66_brief | ✔ ไม่อยู่ใน live |

### 4.6 Coverage (นับจาก production หลัง publish ด้วยสคริปต์ชุดเดียวกับ preview)

| ขอบเขต | total_credits | edition_year | careers | objectives | admission | รวม |
|---|---|---|---|---|---|---|
| ทั้งคลัง (24 ฉบับ) | 23 | 23 | 11 | 15 | 10 | **82/120** (เดิม 59) |
| ฉบับล่าสุด (16 ฉบับ, ตัดฉบับที่ถูกแทน fs61/en60) | 15 | 15 | 11 | 15 | 10 | **66/80** (เดิม 43) |

---

## 5. Shadow validation (8 คำขอผ่าน `/api/chat`)

### 5.1 ตรวจ structured service ก่อนยิง (read-only ในคอนเทนเนอร์ ไม่มี traffic)

ทั้ง 8 คำถามได้ route / หลักสูตร / publication ตามคาด (ตาราง 5.2) — ใช้ยืนยันว่าคำถามที่จะยิงจะเข้าหน่วยที่ต้องการ

### 5.2 ผลจาก `mko.shadow_answers` (21:43:55–21:45:21Z เว้นระยะ 8 วินาที)

| # | คำถาม | route / field | structured | publication_id | source | comparison |
|---|---|---|---|---|---|---|
| 1 | สาขาคหกรรมศาสตร์จบไปทำอาชีพอะไรได้บ้าง | structured / careers | answered — คหกรรมศาสตร์ 2564, 11 ข้อ | 7999a1c2… | ds2564.pdf หน้า 2–3 | **agree** (covered 11/11) |
| 2 | สาขาเทคโนโลยีการจัดการสุขภาพจบไปทำอาชีพอะไรได้บ้าง | structured / careers | answered — 2561, 3 ข้อ | 7999a1c2… | ht61.pdf หน้า 7 | **agree** (3/3) |
| 3 | หลักสูตรเทคโนโลยีสารสนเทศ พ.ศ. 2566 คุณสมบัติของผู้เข้าศึกษามีอะไรบ้าง | structured / admission | answered — IT 2566, 3 ข้อ | 7999a1c2… | it66.pdf หน้า 16 | **agree** (3/3) |
| 4 | หลักสูตรการแพทย์แผนไทยประยุกต์ พ.ศ. 2565 คุณสมบัติของผู้เข้าศึกษามีอะไรบ้าง | structured / admission | answered — 2565, 1 ข้อ | 7999a1c2… | attm65.pdf หน้า 19 | **unclear** (coverage 0.47) |
| 5 | หลักสูตรวิทยาศาสตรมหาบัณฑิต สาขาวิชาการจัดการเทคโนโลยีการเกษตรฯ คุณสมบัติของผู้เข้าศึกษามีอะไรบ้าง | structured / admission | answered — **ป.โท** 2568, 3 ข้อ | 7999a1c2… | agri68_master.pdf หน้า 85 | **partial** (1/3) |
| 6 | หลักสูตรปรัชญาดุษฎีบัณฑิต สาขาวิชาการจัดการเทคโนโลยีการเกษตรฯ คุณสมบัติของผู้เข้าศึกษามีอะไรบ้าง | structured / admission | answered — **ป.เอก** 2568, 2 ข้อ | 7999a1c2… | agri68_phd.pdf หน้า 91 | **unclear** (0.39 / 0.36) |
| 7 | หลักสูตรคณิตศาสตร์ พ.ศ. 2569 มีวัตถุประสงค์อะไรบ้าง | structured / objectives | answered — 2569, 4 ข้อ | 7999a1c2… | ma69.pdf หน้า 1 | **agree** (4/4) |
| 8 | สาขาเทคโนโลยีผลิตภัณฑ์ชีวภาพกับการประกอบธุรกิจ คุณสมบัติของผู้เข้าศึกษามีอะไรบ้าง (**KEEP_REVIEW control**) | structured / admission | **no_data** "ยังไม่มีข้อมูลที่เผยแพร่" | — | — | **not_compared** |

- **ทุกแถว** `mode = shadow`, `served_status = answered`, HTTP 200, latency ของ shadow 3–5 ms
- **structured ถูกทุกข้อ:** เลือกหลักสูตร ปี ระดับปริญญา และเอกสารถูก · ป.โท / ป.เอก แยกกัน · KEEP_REVIEW control ได้ no_data ตามที่ต้องเป็น
- **สรุป comparison:** agree 4 · partial 1 · unclear 2 · not_compared 1
- **คำตอบที่ผู้ใช้เห็นยังมาจากระบบเดิม (RAG):** ไม่มีรูปแบบคำตอบ structured (`ที่มา:`) ใน served_reply ของทั้ง 8 แถว

### 5.3 ข้อสังเกตจาก comparison ของ admission (ไม่ใช่ regression ของ publication)

- **#4, #5, #6 ไม่ใช่ agree เพราะคำตอบ RAG ต่างจากข้อความ มคอ.2 ที่ structured เก็บ** ไม่ใช่เพราะ structured ผิด:
  - #5 / #6 (ป.โท / ป.เอก): RAG สรุปย่อคุณสมบัติแต่ละแผนแทนการยกข้อความยาว ตัวเทียบ 4-gram จึงนับว่าครอบคลุมต่ำ (ตามที่ preview คาดไว้สำหรับ admission ที่เป็นย่อหน้ายาว)
  - #4 (แพทย์แผนไทย 2565): คำตอบ RAG มีเงื่อนไขอายุไม่เกิน 25 ปี และ GPAX 5 ภาคการศึกษา ซึ่ง **ไม่อยู่ใน มคอ.2 หน้า 19** (มีเพียงสายวิทย์-คณิต ผลการเรียนเฉลี่ย ≥ 2.50 และตามประกาศมหาวิทยาลัย)
- #3 และ #8 คำตอบ RAG ก็มีข้อที่ไม่อยู่ในรายการ structured ของหน้าหลักฐาน (#3 เพิ่มข้อ "ฟัง พูด อ่าน เขียนภาษาไทย" และสะกด "สาชา" · #8 เพิ่มข้อเกี่ยวกับโทษจำคุก/ความประพฤติ/โรค) — #3 ยังได้ agree เพราะครอบคลุมทั้ง 3 ข้อของ มคอ.2
- **ยังไม่ได้ตรวจ** ว่าข้อความเพิ่มเหล่านี้มาจากเอกสารอื่นในคลัง (เช่น ประกาศรับสมัคร) หรือเป็นข้อความที่โมเดลแต่งขึ้น — เป็นหลักฐานว่า admission เป็น field ที่ต้องดูผล shadow อย่างใกล้ชิดก่อนพิจารณา on

---

## 6. Production health

| ตรวจ | ผล |
|---|---|
| STRUCTURED_ANSWERS | ✔ `shadow` (.env และคอนเทนเนอร์) |
| backend | ✔ image `5fb3ef40…` (8d6d271) · **restarts 0** · ไม่ได้ restart (started 2026-09-16T17:48:25Z) |
| `/health` ในคอนเทนเนอร์ / public `/api/health` | ✔ `{"status":"ok"}` / 200 |
| log backend ตั้งแต่เริ่มคอนเทนเนอร์ | ✔ error / traceback / exception = **0** · คำเตือน shadow = 0 |
| คอนเทนเนอร์อื่น | ✔ ไม่ถูกแตะ (postgres 4 weeks, ollama 4 weeks, frontend 12 days, caddy 7 days) |
| shadow_answers | 73 → 81 (+8 จาก validation) |

---

## 7. ข้อจำกัดที่เหลือ

1. **admission ใน shadow ยังให้สัญญาณเทียบน้อย** — ตัวเทียบ 4-gram ให้ unclear/partial เมื่อ RAG สรุปย่อย่อหน้ายาว และคำตอบ RAG ของ admission มีเงื่อนไขที่ไม่อยู่ใน มคอ.2 (ข้อ 5.3) ต้องตรวจเพิ่มใน Final Shadow Validation
2. **admission คือเกณฑ์ใน มคอ.2** ของปีที่หลักสูตรอนุมัติ ไม่ใช่ประกาศรับสมัครปีปัจจุบัน — รูปแบบคำตอบต้องบอกที่มาถ้าจะเปิด on
3. **known issue:** careers en65 "น้ า" ยังอยู่ใน live (ไม่ได้แก้ตามที่สั่ง)
4. **KEEP_REVIEW 5 หน่วย** ยังไม่มีข้อมูล structured → คำถามเหล่านี้ได้ no_data → RAG
5. **ฉบับที่ถูกแทน** (fs61 → food66, en60 → en65) ยังไม่ถูกเชื่อมเป็นสายเดียวกัน — คำถามชื่อเดิมได้ total_credits / edition_year ของฉบับเก่า
6. **ช่องว่างที่ review แก้ไม่ได้:** careers/admission ของใบสรุป 2569 สามฉบับ, admission CS 2566, สาธารณสุขศาสตร์ (หน้าเว็บ)
7. **นโยบาย `verified_any`:** live ยังมี 97 values และ objectives 6 รายการที่ยืนยันด้วยกฎอัตโนมัติ
8. **ค้างจากรอบก่อน:** ระดับปริญญาอ่านจากคำไทยเท่านั้น · สาขาหลายระดับที่ไม่ระบุระดับตกไป RAG · ตัวเทียบหน่วยกิตบัณฑิตศึกษาต้องมีคำบอกบริบทยอดรวม

---

## 8. สิ่งที่ยังไม่ได้ทำ

- `STRUCTURED_ANSWERS=on` / Phase 3 ของระบบ / P4
- review decision เพิ่ม / แก้ KEEP_REVIEW / แก้ known issue en65
- extraction / normalize / schema / routing / RAG / prompt / deploy
- behaviour_check / batch test
- commit / push — รายงานนี้และรายงาน P3 preview / apply / comparator rollout ยังไม่ commit

**ไฟล์ของรอบนี้บน server (`~/backups/`, สิทธิ์ 600):** `mko_pre_p3_publication_20260916T213958Z.dump(.sha256)`, `mko_pub3_before_*`, `mko_pub3_after_*`, `mko_p3_publish_20260916T213958Z.sql/.log`, `mko_p3_publication_rollback_20260916T213958Z.sql`, `mko_pub3_snapshot.sh`
