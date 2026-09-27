# รายงานการ Deploy Phase 2 ขึ้น Production

28 กันยายน 2569 · branch `mko-phase2` · เริ่ม 01:55 น. เสร็จ 02:00 น. (รวมประมาณ 5 นาที)
ต่อจาก `AUTOMATED_INGESTION_PHASE2_REPORT.md`

> **สถานะ: สำเร็จทั้งหมด** ไม่มีข้อผิดพลาด ไม่มีการย้อนกลับ
> ข้อมูลเดิมไม่เปลี่ยนแปลงแม้แต่แถวเดียว

---

## สรุปผล

| ขั้นตอน | ผล |
|---|---|
| 1. ตรวจสถานะ production ก่อน | ✅ ตรงกับรายงาน Phase 2 ทุกตัว |
| 2. สำรองฐานข้อมูล | ✅ 52 MB · ตรวจไฟล์แล้วใช้ได้ |
| 3. ตรวจ migration ก่อนรัน | ✅ ไม่มีคำสั่งแก้ของเดิม |
| 4. รัน migration 003 | ✅ สำเร็จ exit=0 |
| 5. ตรวจหลัง migration | ✅ ผ่านครบ 6 ข้อ |
| 6. ทดสอบสิทธิ์ `advisor_ingest` | ✅ ผ่านครบ · DELETE ถูกปฏิเสธจริง |
| 7. รัน crawler 1 รอบ | ✅ ตรงกับที่คาดทุกข้อ |
| 8. smoke test Chat/RAG | ✅ ทำงานปกติ |

---

## 1. Backup

```
ไฟล์    backups/course_advisor_20260927_185506.sql.gz
ขนาด    53,643,927 ไบต์ (52 MB)
sha256  9d6cde9f720e484dd203056aad98e9f8...
```

**ตรวจความสมบูรณ์แล้ว** — `gzip -t` ผ่าน · มี `CREATE TABLE` 28 รายการ · มี `COPY` 28 บล็อก
ครบทุกตารางที่มีข้อมูล

ไฟล์สำรองชุดก่อนหน้า (18 สิงหาคม) ยังอยู่ ไม่ถูกลบ

---

## 2. Migration

### ตรวจก่อนรัน

| สิ่งที่ตรวจ | ผล |
|---|---|
| คำสั่ง `ALTER TABLE` บนตารางเดิม | **ไม่มี** |
| คำสั่ง `DROP TABLE` / `TRUNCATE` / `DELETE` | **ไม่มี** |
| ตารางใน `public` ที่ถูกอ้างถึง | `course_documents` (เป้าหมายคีย์นอก) และ `set_updated_at` (ฟังก์ชัน) เท่านั้น |
| sha256 ของไฟล์ต้นฉบับ | `dd2add2937c99c0c5742254e6a84f676c385e7568aa9f09f1287921fac8c3656` |
| sha256 ของไฟล์ที่ส่งขึ้นเซิร์ฟเวอร์ | **ตรงกัน** |

### ผลการรัน

```
BEGIN
CREATE TABLE
CREATE INDEX x 4
DROP TRIGGER      <- NOTICE: ไม่มีอยู่ ข้ามไป (ปกติสำหรับตารางที่เพิ่งสร้าง)
CREATE TRIGGER
CREATE VIEW
DO                <- บล็อกให้สิทธิ์
INSERT 0 1        <- บันทึกลง schema_migrations
COMMIT
exit=0
```

### ตรวจหลัง migration

| ข้อที่กำหนด | ผล |
|---|---|
| migration 003 ถูกบันทึก | ✅ `003_crawl_sources` · 2026-09-28 01:56:01 |
| `mko.crawl_sources` มีอยู่ | ✅ BASE TABLE · 29 คอลัมน์ · 6 ดัชนี · 1 trigger |
| `mko.v_crawl_pending` มีอยู่ | ✅ VIEW |
| `course_documents` จำนวนเดิม | ✅ **31 → 31** |
| `course_chunks` ไม่เปลี่ยน | ✅ **9,039 → 9,039** |
| `courses` ไม่เปลี่ยน | ✅ **24 → 24** |
| Production API / Chat | ✅ ทำงานปกติ |

**ยอดรวม** — ตาราง 28 → **29** · วิว 6 → **7** เพิ่มอย่างละหนึ่งตามที่ตั้งใจ

---

## 3. ทดสอบสิทธิ์ด้วย role `advisor_ingest` จริง

ทดสอบด้วย `SET ROLE advisor_ingest` ภายใน transaction แล้ว `ROLLBACK` จึงไม่ทิ้งข้อมูลไว้

| การกระทำ | คาดหวัง | ผลจริง |
|---|---|---|
| `SELECT` บน `mko.crawl_sources` | ได้ | ✅ ได้ |
| `INSERT` | ได้ | ✅ `INSERT 0 1` |
| `UPDATE` | ได้ | ✅ `UPDATE 1` · trigger ตั้ง `updated_at` ให้อัตโนมัติ |
| **`DELETE`** | **ถูกปฏิเสธ** | ✅ `ERROR: permission denied for table crawl_sources` |
| `SELECT` บน `mko.v_crawl_pending` | ได้ | ✅ ได้ |
| สิทธิ์ DELETE บน `course_documents` | ไม่มี | ✅ `false` |
| สิทธิ์ DELETE บน `crawl_sources` | ไม่มี | ✅ `false` |

**แถวทดสอบหลงเหลือ: 0** (rollback เรียบร้อย)

---

## 4. ผลการรัน Crawler

รันด้วย role `advisor_ingest` จริง ผ่านอุโมงค์ SSH หนึ่งรอบ

```
เดินเว็บ      16 หน้า
พบลิงก์ PDF   12 รายการ (ไม่ซ้ำ)
unchanged     12
รอคนตรวจ       6
คำขอ HTTP     41 · หน่วง 1.5 วินาทีต่อคำขอ
ใช้เวลา       62 วินาที
```

### เทียบกับที่คาดไว้

| ที่คาดไว้ | ผลจริง |
|---|---|
| ไม่ควรมี PDF ใหม่ถูกนำเข้า | ✅ `status = ingested` มี **0** แถว · เอกสารเพิ่มวันนี้ **0** |
| ไม่ควรมีการสร้าง Embedding | ✅ ไม่มีการเรียก Ollama เลย (Phase 2 ไม่มีโค้ดส่วนนั้น) |
| ไม่ควรมี `course_chunks` ใหม่ | ✅ chunk ที่สร้างวันนี้ **0** · ยอดรวมยัง **9,039** |
| ไม่ควรมีเอกสารเก่าถูกลบ | ✅ `course_documents` ยัง **31** · role ไม่มีสิทธิ์ DELETE ด้วยซ้ำ |
| บันทึกสถานะลง `mko.crawl_sources` | ✅ **12 แถว** |

### สถานะที่บันทึก

| status | needs_review | จำนวน |
|---|---|---|
| `unchanged` | false | 6 |
| `unchanged` | **true** | 6 |

| match_confidence | จำนวน |
|---|---|
| `high` | 6 |
| `ambiguous` | 6 |

**ไฟล์ที่เก็บลง staging: 0** — ถูกต้อง เพราะไม่มีไฟล์ใหม่และไม่มีไฟล์ที่เปลี่ยน

### ตัวอย่างแถวที่บันทึก

```
file                                  status     conf       review linked  bytes
33691df6b880b3d5d500c94740c2ee95.pdf  unchanged  ambiguous  t      t       515,217
460afd3bc569750f0327ac9bd09dc6ce.pdf  unchanged  ambiguous  t      t       657,259
5b30100f0b217d5427657ca432b26dba.pdf  unchanged  ambiguous  t      t       677,183
```

`linked = t` หมายถึงผูกกับเอกสารในคลังแล้วด้วย sha256

**ชื่อหลักสูตรกำกวมแต่ลายนิ้วมือชี้ขาดได้** ระบบจึงผูกถูกตัวพร้อมตั้งธงให้คนตรวจไว้ด้วย
ไม่ได้เลือกเองเงียบ ๆ ตรงตามที่ออกแบบไว้

---

## 5. จำนวนข้อมูล ก่อน / หลัง

| ตาราง | ก่อน deploy | หลัง migration | หลังรัน crawler |
|---|---|---|---|
| `courses` | 24 | 24 | **24** |
| `course_documents` | 31 | 31 | **31** |
| `course_chunks` | 9,039 | 9,039 | **9,039** |
| `mko.crawl_sources` | (ไม่มีตาราง) | 0 | **12** |
| ตารางทั้งหมด | 28 | 29 | 29 |
| วิวทั้งหมด | 6 | 7 | 7 |

**ข้อมูลเดิมไม่เปลี่ยนแปลงแม้แต่แถวเดียว** สิ่งเดียวที่เพิ่มคือ 12 แถวในตารางใหม่

---

## 6. Production Smoke Test

ทดสอบสองรอบ — หลัง migration และหลังรัน crawler

| รายการ | หลัง migration | หลัง crawler |
|---|---|---|
| `/api/health` | ✅ 200 | ✅ 200 |
| หน้าเว็บหลัก | ✅ 200 · 0.13 วินาที | — |
| Chat + header อ้างอิง | ✅ 200 · 1.77 วินาที · มี `X-Source-*` ครบ | ✅ 200 · 1.99 วินาที · มีครบ |
| เปรียบเทียบสองหลักสูตร | — | ✅ 200 · 0.15 วินาที |
| แนะนำสาขาจากความสนใจ | — | ✅ 200 · 3.06 วินาที |
| PDF endpoint | ✅ 200 · 922,878 ไบต์ | — |

**ตัวอย่างคำตอบ** — "อาชีพที่สามารถประกอบได้หลังสำเร็จการศึกษา ตามหลักสูตรวิทยาศาสตรบัณฑิต
สาขาวิชาวิทยาการคอมพิวเตอร์ (พ.ศ. 2566)…" พร้อม `X-Source-Title: cs66.pdf` และ `X-Source-Page: 3`

---

## 7. Error และ Warning ที่พบ

| รายการ | ผล |
|---|---|
| error หรือ traceback ใน log backend 30 นาที | **0** |
| จำนวน restart ของ backend | **0** |
| บริการที่รันอยู่ | ครบ 6 ตัว — backend · caddy · frontend · ollama · postgres · webapi |

**Warning เดียวที่เจอ** และไม่ใช่ปัญหา

```
NOTICE: trigger "trg_crawl_sources_updated_at" for relation "mko.crawl_sources"
        does not exist, skipping
```

มาจาก `DROP TRIGGER IF EXISTS` ที่เขียนไว้ให้ migration รันซ้ำได้
ตารางเพิ่งถูกสร้างจึงยังไม่มี trigger เป็นพฤติกรรมที่ตั้งใจ

---

## 8. ข้อมูล Deploy

| รายการ | ค่า |
|---|---|
| branch | `mko-phase2` |
| commit ล่าสุด | `17abce0` |
| ไฟล์ที่ deploy | `db/migrations/003_crawl_sources.sql` เท่านั้น |
| sha256 ของ migration | `dd2add2937c99c0c5742254e6a84f676c385e7568aa9f09f1287921fac8c3656` |
| วิธี deploy | ส่งไฟล์ขึ้นเซิร์ฟเวอร์ ตรวจ sha แล้วรันด้วย `psql -v ON_ERROR_STOP=1` |
| container ที่ restart | **ไม่มี** |
| image ที่ build ใหม่ | **ไม่มี** |
| cron / systemd timer | **ไม่ได้ตั้ง** ตามข้อห้าม |
| ingest container | **ไม่ได้สร้าง** ตามข้อห้าม |
| Supabase | **ไม่แตะ** |
| commit ลง git | **ยังไม่ commit** รอการอนุมัติ |

### ไฟล์ใน repo ที่ยังไม่ commit

```
?? db/migrations/003_crawl_sources.sql      <- deploy ไปแล้วแต่ยังไม่ commit
?? pipeline/crawl/                          (http, discover, inventory, report, run, state, sync)
?? eval/crawl_state_check.py
?? docs/AUTOMATED_INGESTION_*.md
?? docs/CRAWL_PDF_DISCOVERY_REPORT.md
 M backend/app/services/answer_cache.py     <- ของค้างจากงานก่อนหน้า ไม่เกี่ยวกับ Phase 2
 M backend/app/services/query_expansion.py  <- ของค้างจากงานก่อนหน้า ไม่เกี่ยวกับ Phase 2
```

> ⚠️ **ควรรีบ commit `003_crawl_sources.sql`**
> ตอนนี้ production มี schema ที่ repo ยังไม่มีบันทึกไว้ ถ้ามีคนตั้งฐานข้อมูลใหม่จาก repo
> จะได้โครงสร้างที่ไม่ตรงกับ production

---

## 9. วิธีย้อนกลับ

ยังไม่ได้ใช้ แต่พร้อมใช้ทันที

```sql
BEGIN;
DROP VIEW  IF EXISTS mko.v_crawl_pending;
DROP TABLE IF EXISTS mko.crawl_sources;
DELETE FROM mko.schema_migrations WHERE version = '003_crawl_sources';
COMMIT;
```

ใช้เวลาไม่ถึงวินาที ไม่ต้อง restart service
ปลอดภัยเพราะไม่มีตารางอื่นอ้างอิงเข้ามา และไม่มีโค้ดใน `backend/` อ่านตารางนี้

**ถ้าต้องกู้ทั้งฐานข้อมูล**

```bash
gunzip -c backups/course_advisor_20260927_185506.sql.gz | docker compose -f docker-compose.prod.yml exec -T postgres psql -U postgres -d course_advisor
```

ไฟล์สำรองสร้างด้วย `--clean --if-exists` อยู่แล้ว ลบของเดิมก่อนกู้ให้อัตโนมัติ

---

## 10. สิ่งที่ยังไม่ได้ทำ

| รายการ | สถานะ |
|---|---|
| Phase 3 (นำเอกสารเข้าคลังความรู้) | **ยังไม่เริ่ม รอการอนุมัติ** |
| ช่องทางให้ผู้ดูแลกดอนุมัติ | ยังไม่มี ตอนนี้ต้องแก้ในฐานข้อมูลเอง |
| ตั้งเวลาทำงานอัตโนมัติ | ไม่ได้ตั้ง ตามข้อห้าม |
| container สำหรับ ingest | ไม่ได้สร้าง ตามข้อห้าม |
| การแจ้งเตือนเมื่อพบของใหม่ | ยังไม่ได้ออกแบบ |
| commit โค้ดลง git | รอการอนุมัติ |
| crawl เว็บของแต่ละสาขา | ครอบคลุมเฉพาะ `sci.pnru.ac.th` |

---

## 11. คำสั่งสำหรับดูคิวงาน

```sql
SELECT substring(source_url from 47) AS file, status, match_confidence,
       needs_review, review_reason, last_checked_at
FROM mko.v_crawl_pending;
```

ตอนนี้จะได้ 6 แถวที่ชื่อหลักสูตรกำกวม ซึ่งทั้งหมดผูกเอกสารถูกตัวแล้วด้วย sha256
จึงเป็นแค่การรอให้คนยืนยันว่าจับคู่ถูก ไม่ใช่ปัญหาที่ต้องรีบแก้

**รัน crawler รอบถัดไปด้วยมือ**

```bash
CRAWL_DATABASE_URL=<INGEST_DATABASE_URL> python -m pipeline.crawl.sync --staging staging/crawl
```
