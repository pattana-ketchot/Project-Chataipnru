# Migration 005 — รายงานการลบข้อมูลส่วนบุคคล commit และ push

| | |
|---|---|
| วันที่ | 2026-10-01 · 13:3x UTC |
| ขอบเขตที่ได้รับอนุมัติ | แทนที่อีเมลจริงด้วย placeholder · ตรวจ diff · commit แยกอีกหนึ่ง commit · push `mko-phase2` |
| **commit ใหม่** | **`97686a18b794b517ffe36da73c1998e1c09a1d09`** |
| **push ไปที่** | **`origin/mko-phase2`** · `7af085b..97686a1` |
| **`main` ถูกแตะหรือไม่** | **ไม่** — `b78b3f8…` เท่าเดิม · merge เข้า main = 0 commit |
| **Production write / deploy / restart** | **NONE ทั้งสามอย่าง** |


> ## ⚠ มีข้อมูลในรายงานนี้ที่ภายหลังพบว่าผิด
>
> รายงานนี้บันทึกสิ่งที่เกิดขึ้น ณ เวลานั้นไว้ตามเดิมโดยเจตนา **ไม่แก้เนื้อใน**
> แต่ข้อเท็จจริงสี่เรื่องต่อไปนี้ผิด และได้แก้ในเอกสารอ้างอิงแล้ว
>
> | ที่รายงานไว้ | ความจริง |
> |---|---|
> | Supabase มี FK 0 · CHECK 0 · UNIQUE 1 | **FK 7 · CHECK 2 · UNIQUE 4** |
> | ต้นทางเป็น `TIMESTAMP` ไม่มีเขตเวลา · เสี่ยงคลาด 7 ชั่วโมง | เป็น `TIMESTAMP WITH TIME ZONE` อยู่แล้ว · **ไม่มีความเสี่ยงนี้** |
> | `rag_documents` เป็น `vector(768)` | คอลัมน์เป็น `vector` **ไม่ล็อกมิติ** · 768 เป็นค่าของแอป · มิติจริง **UNKNOWN** |
> | `external_news` ใช้ `slug` เป็นกุญแจ unique | ต้นทางใช้ **`detail_url` NOT NULL UNIQUE** · `slug` เป็น NULL ได้ |
>
> ดู [`SUPABASE_PRE_MIGRATION_AUDIT.md`](SUPABASE_PRE_MIGRATION_AUDIT.md) ข้อ 12
> และ [`MIGRATION_005_CORRECTIVE_REVIEW.md`](MIGRATION_005_CORRECTIVE_REVIEW.md)


---

## 1. commit hash ใหม่

```
97686a18b794b517ffe36da73c1998e1c09a1d09
docs: record the consolidation feasibility study
parent 67c6f99a8c11c90d89b625b447a5350b9663860d
```

ประวัติล่าสุดของ branch

```
97686a1  docs: record the consolidation feasibility study            ← commit นี้
67c6f99  feat(db): add a web schema for the website data that lives elsewhere
7af085b  test: add isolated crawler ingestion e2e harness
5d8f82b  fix: make staged crawler PDFs readable by the review backend
2fdc6f2  chore: version the deployment files for the crawler review rollout
```

---

## 2. ไฟล์ที่แก้ — 1 ไฟล์

```
docs/DATABASE_CONSOLIDATION_AUDIT.md     866 บรรทัด
```

### 2.1 สิ่งที่เปลี่ยน

แทนที่อีเมลจริงของเจ้าของโปรเจกต์ด้วย `<OWNER_EMAIL>` **2 จุด** คือบรรทัด **447**
และ **628** ซึ่งเป็นสองจุดเดียวที่อีเมลนั้นปรากฏในไฟล์

ทั้งสองจุดใช้อีเมลเป็นตัวอย่างของบัญชีที่ **มีอยู่ในระบบหนึ่งแต่ไม่มีในอีกระบบ**
ซึ่งเป็นประเด็นที่ไม่ขึ้นกับว่าอีเมลนั้นคืออะไร **ความหมายของทั้งสองประโยคจึงไม่เปลี่ยน**

### 2.2 วิธียืนยันว่าเปลี่ยนเฉพาะข้อมูลส่วนบุคคล

ไฟล์นี้ยัง untracked ก่อนแก้ `git diff` จึงเทียบกับ `HEAD` ไม่ได้
ใช้วิธีเก็บสำเนาก่อนแก้ไว้แล้วเทียบแทน

| ข้อตรวจ | ผล |
|---|---|
| จำนวนบรรทัดก่อน → หลัง | **866 → 866** ไม่เปลี่ยน |
| บรรทัดที่เนื้อหาต่าง | **[447, 628]** เท่านั้น |
| **ทำให้จุดอีเมลเป็นกลางทั้งสองไฟล์แล้วเทียบ** | **เหมือนกันทุกไบต์** |
| จำนวนอักขระที่เปลี่ยน | 6 ตัว (= ผลต่างความยาวสตริง × 2 จุด) |
| `git diff --cached --check` | ว่าง |
| CRLF | **0** |

ข้อที่สามคือข้อที่พิสูจน์ได้แน่นอนที่สุด — แทนที่ทั้งอีเมลเดิมและ `<OWNER_EMAIL>`
ด้วยอักขระเดียวกันในทั้งสองไฟล์แล้วเทียบ ได้ผลว่า **เหมือนกันทุกไบต์**
แปลว่านอกจากจุดอีเมลแล้วไม่มีอะไรเปลี่ยนเลยแม้แต่ช่องว่างเดียว

### 2.3 ตรวจความปลอดภัยของไฟล์ก่อน commit

repo นี้เป็น **public** จึงตรวจซ้ำก่อนส่งขึ้น

| สิ่งที่ค้นหา | พบ |
|---|---:|
| อีเมลส่วนบุคคล (gmail / hotmail / outlook / yahoo) | **0** |
| bcrypt hash | **0** |
| JWT / API key (`eyJ…`, `AIza…`, `sb_…`) | **0** |
| DSN ที่มีรหัสผ่าน | **0** |

ตรวจทั้งในไฟล์บนดิสก์และใน **blob ที่ git เก็บจริง** (`git cat-file -p :<path>`)
ได้ผลตรงกัน: อีเมลส่วนบุคคล 0 · `<OWNER_EMAIL>` 2 จุด · CRLF 0 · 866 บรรทัด

---

## 3. branch / remote ที่ push

```
git push origin mko-phase2
  To https://github.com/pattana-ketchot/Project-Chataipnru.git
     7af085b..97686a1  mko-phase2 -> mko-phase2
```

| | ก่อน push | หลัง push |
|---|---|---|
| `origin/mko-phase2` | `7af085b2e813…` | **`97686a18b794…`** |
| local `HEAD` | `97686a18b794…` | `97686a18b794…` |
| ตรงกันหรือไม่ | — | **ตรง** |

**commit ที่ถูก push 2 รายการ**

```
97686a1  docs: record the consolidation feasibility study
67c6f99  feat(db): add a web schema for the website data that lives elsewhere
```

เป็น **fast-forward ปกติ** (ตรวจก่อน push แล้วว่า `origin/mko-phase2` เป็น ancestor
ของ `HEAD`) · ไม่ใช้ `--force` · ไม่ push tag (local tags = 0) · ไม่ใช้ `--all`

---

## 4. ยืนยันว่า `main` ไม่ถูกแตะ

```
origin/main ก่อน push  b78b3f8bf895685874d9a52c66b45569072f0514
origin/main หลัง push   b78b3f8bf895685874d9a52c66b45569072f0514      ← เท่าเดิม
```

| ข้อตรวจ | ผล |
|---|---|
| `origin/main` เปลี่ยนไหม | **ไม่เปลี่ยน** |
| merge เข้า `main` | **ไม่มี** — `origin/mko-phase2..origin/main` = **0 commit** |
| `mko-phase2` นำหน้า `main` | 30 commit (ยังไม่ merge) |

branch ทั้งหมดบน remote

```
b78b3f8bf895  refs/heads/main
97686a18b794  refs/heads/mko-phase2
```

---

## 5. Production write / deploy / restart = NONE

ยืนยันแบบอ่านอย่างเดียวเมื่อ **2026-10-01T13:39:04Z** หลัง push เสร็จ

```
schema ที่มี        : mko, public                       ← ยังไม่มี web
migration ที่ลงแล้ว  : 001, 002, 003, 004                ← ยังไม่มี 005
courses=24  documents=31  chunks=9039  users=198  decisions=0
```

คอนเทนเนอร์ — container ID และ StartedAt เหมือนเดิมทุกตัว

| service | container ID | StartedAt | restarts |
|---|---|---|---:|
| backend | `fda31caa20c4` | 2026-09-29T01:06:17.872Z | 0 |
| frontend | `2886c1bf9183` | 2026-09-29T01:07:21.190Z | 0 |
| caddy | `a2957d7b8fc3` | 2026-09-22T21:23:48.949Z | 0 |
| postgres | `e8c091a4fc60` | 2026-08-18T14:17:25.705Z | 0 |
| ollama | `e6ac0350c722` | 2026-08-18T14:17:25.705Z | 0 |
| webapi | `6a73308d4f39` | 2026-09-22T21:21:35.624Z | 0 |

| รายการที่ยังไม่ได้รับอนุญาต | สถานะ |
|---|---|
| apply migration 005 กับ production | **ไม่ได้ทำ** |
| data migration จาก Supabase | **ไม่ได้ทำ** |
| production database write | **ไม่ได้ทำ** |
| deploy / restart | **ไม่ได้ทำ** |
| auth / storage migration | **ไม่ได้ทำ** |
| RAG / embedding migration | **ไม่ได้ทำ** |
| re-embedding | **ไม่ได้ทำ** |
| เปลี่ยน Ollama configuration | **ไม่ได้ทำ** |
| merge เข้า `main` | **ไม่ได้ทำ** |
| เริ่ม phase ถัดไปเอง | **ไม่ได้ทำ** |

---

## 6. สถานะปัจจุบันของงานทั้งชุด

### 6.1 อยู่บน `origin/mko-phase2` แล้ว

| ไฟล์ | commit |
|---|---|
| `db/migrations/005_web_schema.sql` | `67c6f99` |
| `eval/web_schema_check.py` | `67c6f99` |
| `docs/MIGRATION_005_WEB_SCHEMA_REVIEW.md` | `67c6f99` |
| `docs/TARGET_ARCHITECTURE.md` | `67c6f99` |
| `docs/EMBEDDING_PATH_AUDIT.md` | `67c6f99` |
| `docs/DATABASE_CONSOLIDATION_AUDIT.md` | `97686a1` |

ลิงก์ข้ามเอกสารที่เคยเปิดไม่ได้บน GitHub (เพราะไฟล์ยังไม่ commit) **ใช้งานได้แล้ว**

### 6.2 ยังไม่ commit

`docs/MIGRATION_005_COMMIT_REPORT.md` และรายงานฉบับนี้ยัง untracked
เพราะยังไม่อยู่ในรายการที่ได้รับอนุญาตให้ commit

---

## สรุปการเปลี่ยนแปลงในรอบนี้

```
FILES CHANGED:                    1  (docs/DATABASE_CONSOLIDATION_AUDIT.md)
LINES CHANGED:                    2  (บรรทัด 447, 628 — เฉพาะอีเมล)
COMMITS:                          1  (97686a18b794b517ffe36da73c1998e1c09a1d09)
PUSHED TO:                        origin/mko-phase2  (7af085b..97686a1 fast-forward)

MAIN BRANCH:                      UNTOUCHED  (b78b3f8… เท่าเดิม)
MIGRATION APPLIED TO PRODUCTION:  NONE
PRODUCTION WRITES:                NONE
DATA MIGRATED:                    NONE
DEPLOYMENTS:                      NONE
SERVICE RESTARTS:                 NONE
OLLAMA / RAG / EMBEDDING CHANGES: NONE
AUTH / STORAGE CHANGES:           NONE
```

---

## STOP

**ไม่เริ่ม phase ถัดไปเอง** — รอคำสั่งอนุมัติรอบใหม่

สิ่งที่ยังต้องการก่อนเริ่ม Data Migration อยู่ใน
[`MIGRATION_005_COMMIT_REPORT.md`](MIGRATION_005_COMMIT_REPORT.md) ข้อ 5 และ 6
สรุปสั้น ๆ: สิทธิ์เข้า Supabase ในฐานะ member · ค่า `news.status` ที่ใช้จริง ·
เขตเวลาของ `TIMESTAMP` เดิม · วิธีแมปผู้ใช้สองชุด · ที่อยู่ใหม่ของไฟล์แนบ ·
จำนวนแถวจริง — และ unknown ที่ใหญ่ที่สุดคือ **source ของ SPA ขอใช้ได้หรือไม่**
