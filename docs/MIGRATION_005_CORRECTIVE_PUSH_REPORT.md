# Migration 005 Corrective Review — รายงาน commit และ push

| | |
|---|---|
| วันที่ | 2026-10-01 |
| ขอบเขตที่ได้รับอนุมัติ | ตรวจ diff รอบสุดท้าย · ตรวจ secret/PII · commit แยก code/docs · push `mko-phase2` |
| **commit ใหม่** | **2 รายการ** — `de42e38` และ `f72b4189` |
| **push ไปที่** | **`origin/mko-phase2`** · `97686a1..f72b418` |
| **ผลทดสอบ** | **536 / 536 ผ่าน · 0 ไม่ผ่าน** |
| **`main` ถูกแตะหรือไม่** | **ไม่** — `b78b3f8…` เท่าเดิม · merge เข้า main = 0 commit |
| **Production write / deploy / restart** | **NONE ทั้งสามอย่าง** |
| เอกสารต้นเรื่อง | [`MIGRATION_005_CORRECTIVE_REVIEW.md`](MIGRATION_005_CORRECTIVE_REVIEW.md) |

---

## 1. commit hash ใหม่

```
f72b4189bc4c08f594cdd842b91c772bf5b253f5   docs: correct the Supabase facts and record where they came from
de42e38df59f910af0f02c0ab5051502dac6fd4e   fix(db): match the source schema's keys in the web schema
parent                                      97686a18b794b517ffe36da73c1998e1c09a1d09
```

ประวัติล่าสุดของ branch

```
f72b418  docs: correct the Supabase facts and record where they came from   ← commit 2
de42e38  fix(db): match the source schema's keys in the web schema          ← commit 1
97686a1  docs: record the consolidation feasibility study
67c6f99  feat(db): add a web schema for the website data that lives elsewhere
7af085b  test: add isolated crawler ingestion e2e harness
```

แยกสอง commit ตามที่อนุญาต — **แก้ code/schema** กับ **แก้เอกสาร** คนละก้อน
เพื่อให้ย้อนดูหรือถอนทีละส่วนได้

---

## 2. ไฟล์ในแต่ละ commit

### 2.1 `de42e38` — code / schema correction · 2 ไฟล์ · **+88 −31**

```
db/migrations/005_web_schema.sql   | 73 ++++++++++++++++++++++++---------
eval/web_schema_check.py           | 46 +++++++++++++++++++------
2 files changed, 88 insertions(+), 31 deletions(-)
```

สิ่งที่แก้

| จุด | ก่อน | หลัง |
|---|---|---|
| `external_news.detail_url` | `TEXT` nullable | **`TEXT NOT NULL UNIQUE`** |
| `external_news.slug` | `NOT NULL UNIQUE` | **nullable + partial unique** |
| `external_news.source` | nullable | **`NOT NULL`** |
| คอมเมนต์เรื่อง constraint ต้นทาง | "FK 0 · CHECK 0 · UNIQUE 1" | **"FK 7 · CHECK 2 · UNIQUE 4"** + หมายเหตุว่าตัวเลขเดิมผิด |
| คอมเมนต์เรื่องเวลา | "ต้นทางเป็น TIMESTAMP ไม่มีเขตเวลา · เสี่ยงคลาด 7 ชั่วโมง" | **"ต้นทางเป็น TIMESTAMP WITH TIME ZONE · ไม่ต้องตีความเขตเวลา"** |
| `news.status` | CHECK 3 ค่า ไม่มีหมายเหตุ | **CHECK เดิม + ทำเครื่องหมาย PENDING DECISION** ระบุชัดว่า `archived` ยังไม่มีหลักฐาน |
| ข้อตรวจใน test | 47 ข้อ | **52 ข้อ** (+5 เรื่อง `external_news`) |

### 2.2 `f72b4189` — documentation · 8 ไฟล์ · **+1,516 −31**

**แก้ข้อเท็จจริง**

```
docs/MIGRATION_005_WEB_SCHEMA_REVIEW.md   +33 −22
docs/TARGET_ARCHITECTURE.md                +6  −6
docs/DATABASE_CONSOLIDATION_AUDIT.md       +8  −1
docs/EMBEDDING_PATH_AUDIT.md               +1  −1
```

**เอกสารใหม่**

```
docs/SUPABASE_PRE_MIGRATION_AUDIT.md      608 บรรทัด   ที่มาของการแก้รอบนี้
docs/MIGRATION_005_CORRECTIVE_REVIEW.md   377 บรรทัด   รายละเอียดการแก้
```

**ใส่แบนเนอร์แจ้งข้อผิดพลาด — ไม่แก้เนื้อใน**

```
docs/MIGRATION_005_COMMIT_REPORT.md
docs/MIGRATION_005_PUSH_REPORT.md
```

สองฉบับนี้เป็นบันทึกว่าเกิดอะไรขึ้น ณ เวลานั้น การแก้เนื้อในเงียบ ๆ จะทำลายคุณค่า
ของการเป็นบันทึก จึงใส่ตารางแจ้งข้อผิดพลาดสี่ข้อไว้หัวไฟล์แทน

---

## 3. การตรวจก่อน commit

### 3.1 ตรวจ secret / PII — repo นี้เป็น **public**

ตรวจ **10 ไฟล์ × 9 รูปแบบ**

| รูปแบบที่ค้น | พบ |
|---|---:|
| อีเมลส่วนบุคคล (gmail / hotmail / outlook / yahoo / live / icloud) | **0** |
| JWT (`eyJ…`) | **0** |
| Google API key (`AIza…`) | **0** |
| Supabase key / `service_role` | **0** |
| DSN ที่มีรหัสผ่าน | **0** |
| bcrypt hash | **0** |
| โฮสต์ของ Supabase project | **0** |
| private key | **0** |
| ssh key | **0** |
| **รวม** | **0** |

### 3.2 ตรวจ git

```
git add  ระบุ path ทุกไฟล์   ← ไม่ใช้ git add .
git diff --cached --check     ว่าง ทั้งสองครั้ง
CRLF ในทุกไฟล์                0
```

---

## 4. Test result — **536 / 536 ผ่าน · 0 ไม่ผ่าน**

| ชุด | ก่อนแก้ | **หลังแก้** |
|---|---:|---:|
| `eval/web_schema_check.py` | 47 | **52** |
| `eval/crawl_download_check.py` | 165 | 165 |
| `eval/crawl_ingest_worker_check.py` | 187 | 187 |
| `eval/crawl_approval_check.py` | 84 | 84 |
| `eval/crawl_state_check.py` | 32 | 32 |
| `eval/document_endpoint_check.py` | 16 | 16 |
| **รวม** | 531 | **536** |

```
migration 001 → 005 จากฐานทดสอบใหม่   ผ่านครบทุกตัว
ลง 005 ซ้ำ (idempotency)              ไม่ error
constraint ที่ได้                      ตาราง 5 · FK 8 · CHECK 3 · UNIQUE 8
```

**ข้อตรวจใหม่ที่สำคัญที่สุด**

```
external_news: หลายแถวที่ slug เป็น NULL อยู่ร่วมกันได้
```

ข้อนี้ **schema เดิมจะไม่ผ่าน** — เป็นการพิสูจน์ว่าความเสี่ยง "นำเข้าล้มทั้งก้อน
เพราะมีแถวที่ slug เป็น NULL" ถูกปิดแล้วจริง

สภาพแวดล้อม: PostgreSQL 16.15 ในคอนเทนเนอร์แยก · ฐาน `web_test` / `crawl_test` ·
ด่านกันสองชั้น · ทำความสะอาดแล้ว containers 0 · volumes 0 · images 0

---

## 5. branch / remote ที่ push

```
git push origin mko-phase2
  To https://github.com/pattana-ketchot/Project-Chataipnru.git
     97686a1..f72b418  mko-phase2 -> mko-phase2
```

| | ก่อน push | หลัง push |
|---|---|---|
| `origin/mko-phase2` | `97686a18b794…` | **`f72b4189bc4c…`** |
| local `HEAD` | `f72b4189bc4c…` | `f72b4189bc4c…` |
| ตรงกันหรือไม่ | — | **ตรง** |

เป็น **fast-forward ปกติ** (ตรวจก่อน push ว่า `origin/mko-phase2` เป็น ancestor ของ
`HEAD`) · ไม่ใช้ `--force` · ไม่ push tag (local tags = 0) · ไม่ใช้ `--all`

### 5.1 ยืนยันบน GitHub จริง

ไฟล์ของงานนี้อยู่บน `origin/mko-phase2` **ครบทั้ง 10 ไฟล์** และดึงเนื้อไฟล์จริงมาตรวจแล้ว

```sql
-- db/migrations/005_web_schema.sql บน origin/mko-phase2
slug            VARCHAR(255),
detail_url      TEXT         NOT NULL UNIQUE,
source          VARCHAR(100) NOT NULL,
```

---

## 6. `origin/main` ก่อน / หลัง

```
ก่อน  b78b3f8bf895685874d9a52c66b45569072f0514
หลัง   b78b3f8bf895685874d9a52c66b45569072f0514      ← เท่าเดิม
```

| ข้อตรวจ | ผล |
|---|---|
| `origin/main` เปลี่ยนไหม | **ไม่เปลี่ยน** |
| merge เข้า `main` | **ไม่มี** — `origin/mko-phase2..origin/main` = **0 commit** |
| `mko-phase2` นำหน้า `main` | 32 commit (ยังไม่ merge) |

---

## 7. Production write / deploy / restart

**NONE ทั้งสามอย่าง** — ยืนยันแบบอ่านอย่างเดียวหลัง push เสร็จ

```
schema ที่มีบน production   : mko, public                   ← ยังไม่มี web
migration ที่ลงแล้ว          : 001, 002, 003, 004            ← ยังไม่มี 005
คอนเทนเนอร์ที่ทำงาน          : 7 ตัว ไม่มีการ restart
```

| รายการที่ยังไม่ได้รับอนุญาต | สถานะ |
|---|---|
| apply migration 005 กับ production | **ไม่ได้ทำ** |
| data migration จาก Supabase | **ไม่ได้ทำ** |
| production DB write | **ไม่ได้ทำ** |
| Supabase write | **ไม่ได้ทำ** |
| auth / RLS / storage migration | **ไม่ได้ทำ** |
| RAG migration / re-embedding | **ไม่ได้ทำ** |
| เปลี่ยน Ollama configuration | **ไม่ได้ทำ** |
| deploy / restart | **ไม่ได้ทำ** |
| merge `main` | **ไม่ได้ทำ** |
| เริ่ม phase ถัดไปเอง | **ไม่ได้ทำ** |

---

## 8. working tree ที่เหลือ

```
staged            0
tracked modified  0
```

ไฟล์ของงานนี้ **commit ครบทั้ง 10 ไฟล์** ไม่มีค้าง

```
untracked  53 รายการ — เป็นเอกสารเก่าที่ไม่เกี่ยวกับงานนี้
  สไลด์ (SLIDE_*.png/svg/py) · ER diagram (ER_DIAGRAM_*) · docs/database/
  รายงาน Phase 3 เก่า · AUTH_ARCHITECTURE_AUDIT.md · PHASE3D_* ฯลฯ
```

> เอกสารชุดนี้ยังไม่เคย commit และอยู่นอกขอบเขตที่ได้รับอนุมัติในรอบใด ๆ
> ความเสี่ยงที่เคยบันทึกไว้ยังอยู่: ไฟล์เหล่านี้มีอยู่บนดิสก์เครื่องเดียว
> และเคยมีไฟล์หนึ่งหายไปเองมาแล้ว

---

## 9. `news.status` — Pending Decision ยังมีผล

**ห้ามนำเข้าข้อมูลตาราง `news`** จนกว่าจะ

1. ได้สิทธิ์ member ของโปรเจกต์ Supabase
2. รัน `SELECT DISTINCT status FROM public.news`
3. ปรับรายการค่าใน CHECK ให้ตรงกับของจริง

**ห้ามถือว่า `archived` เป็นค่าที่ใช้งานจริงจนกว่าจะมีหลักฐาน** — บันทึกไว้แล้วทั้งใน
คอมเมนต์ของ `db/migrations/005_web_schema.sql` และใน
[`MIGRATION_005_CORRECTIVE_REVIEW.md`](MIGRATION_005_CORRECTIVE_REVIEW.md) ข้อ 3.2

---

## สรุปการเปลี่ยนแปลงในรอบนี้

```
COMMITS:                          2   (de42e38 · f72b4189)
FILES COMMITTED:                 10   (2 code/schema · 8 documentation)
PUSHED TO:                        origin/mko-phase2   (97686a1..f72b418 fast-forward)
TESTS:                            536 ผ่าน · 0 ไม่ผ่าน

MAIN BRANCH:                      UNTOUCHED  (b78b3f8… เท่าเดิม)
MIGRATION APPLIED TO PRODUCTION:  NONE
PRODUCTION WRITES:                NONE
SUPABASE WRITES:                  NONE
DATA MIGRATED:                    NONE
DEPLOYMENTS / RESTARTS:           NONE
AUTH / RLS / STORAGE CHANGES:     NONE
RAG / EMBEDDING / OLLAMA CHANGES: NONE
SECRETS หรือ PII ที่ขึ้น repo:      NONE  (ตรวจ 10 ไฟล์ × 9 รูปแบบ พบ 0)
```

---

## STOP

**ไม่เริ่ม Phase ถัดไปเอง** — รอคำสั่งอนุมัติรอบใหม่

สิ่งที่ต้องมีก่อนเริ่ม Data Migration อยู่ใน
[`SUPABASE_PRE_MIGRATION_AUDIT.md`](SUPABASE_PRE_MIGRATION_AUDIT.md) ข้อ 13
และ [`MIGRATION_005_CORRECTIVE_REVIEW.md`](MIGRATION_005_CORRECTIVE_REVIEW.md) ข้อ 6

สรุปสั้น: **สิทธิ์ member ของ Supabase project** คือสิ่งเดียวที่ปลดล็อกทุกอย่างที่เหลือ
และคำสั่งแรกที่ต้องรันเมื่อได้มาคือ `SELECT DISTINCT status FROM public.news`
