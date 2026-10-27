# Migration 005 Final Review — Push Report

| | |
|---|---|
| วันที่ | 2026-10-02 |
| ขอบเขต | PUSH เท่านั้น |
| **push** | **`f72b418..dc5e860  mko-phase2 -> mko-phase2`** |
| **remote hash ที่ verify ได้** | **`dc5e86035c2b2c3faedd6f79487b308db3513d2b`** ✓ |
| ชนิดการ push | **fast-forward** · ไม่มี force · ไม่เขียนประวัติทับ |
| `main` | **ไม่ขยับ** — ยังอยู่ที่ `b78b3f8` |

```
Apply Migration 005   NONE        Production Write        NONE
Data Migration        NONE        Deploy / Restart        NONE
Merge main            NONE        Push main               NONE
```

---

## 1. ตรวจก่อน push — ครบทั้ง 4 ข้อที่สั่ง

| # | ข้อที่สั่งให้ยืนยัน | ผล |
|---|---|---|
| 1 | HEAD = `dc5e860` | **`dc5e86035c2b2c3faedd6f79487b308db3513d2b`** ✓ |
| 2 | branch = `mko-phase2` | **`mko-phase2`** ✓ |
| 3 | `origin/mko-phase2` ยังอยู่ที่ `f72b418` | **`f72b4189bc4c08f594cdd842b91c772bf5b253f5`** ✓ |
| 4 | ไม่ amend เพิ่ม | ไม่มีคำสั่ง `--amend` ในรอบนี้ ✓ |

### ข้อ 3 ตรวจจาก remote โดยตรง ไม่ใช่จาก ref ที่ cache ไว้

```
git ls-remote origin refs/heads/mko-phase2
f72b4189bc4c08f594cdd842b91c772bf5b253f5    refs/heads/mko-phase2
```

`git rev-parse origin/mko-phase2` อ่านจาก ref ในเครื่องซึ่งอัปเดตเฉพาะตอน fetch/push —
ถ้ามีใครดัน commit ขึ้น remote หลัง fetch ครั้งล่าสุด ค่านั้นจะล้าสมัยโดยไม่มีอะไรฟ้อง
จึงยิงถาม remote ตรง ๆ ด้วย `ls-remote` เพื่อให้เป็นหลักฐานที่เชื่อได้

ทั้งสองทางให้ค่าเดียวกัน → remote ยังไม่มีใครเปลี่ยน การ push เป็น fast-forward แท้

### สิ่งที่จะถูก push

```
git log --oneline origin/mko-phase2..HEAD
dc5e860  fix(db): finalize web schema migration from live verification
```

**commit เดียว** ไม่มี commit แฝง

### working tree ก่อน push

```
staged:    0
modified:  0
```

---

## 2. คำสั่งที่ใช้

```bash
git push origin mko-phase2:mko-phase2
```

**ใช้ refspec ชัดเจน `mko-phase2:mko-phase2`** ไม่ใช่ `git push` เปล่า —
`git push` เปล่าจะทำตามค่า `push.default` ของเครื่อง ซึ่งถ้าตั้งเป็น `matching`
จะดันทุก branch ที่ชื่อตรงกันทั้ง local และ remote ขึ้นไปพร้อมกัน
การระบุ refspec ทำให้ไม่มีทางแตะ branch อื่นได้เลย ไม่ว่า config จะเป็นอะไร

### ผล

```
To https://github.com/pattana-ketchot/Project-Chataipnru.git
   f72b418..dc5e860  mko-phase2 -> mko-phase2
```

`f72b418..dc5e860` (มีจุดสองจุด ไม่มีเครื่องหมาย `+`) คือสัญลักษณ์ของ **fast-forward**
ถ้าเป็นการเขียนทับจะขึ้นเป็น `+ f72b418...dc5e860 (forced update)`

---

## 3. Verify remote hash หลัง push

```
git ls-remote origin refs/heads/mko-phase2
dc5e86035c2b2c3faedd6f79487b308db3513d2b    refs/heads/mko-phase2
```

| | |
|---|---|
| remote | `dc5e86035c2b2c3faedd6f79487b308db3513d2b` |
| local HEAD | `dc5e86035c2b2c3faedd6f79487b308db3513d2b` |
| ผล | **MATCH** |

เทียบแบบ full 40 ตัวอักษร ไม่ใช่ short hash — short hash 7 ตัวชนกันได้ในทางทฤษฎี
และถ้าเทียบแค่นั้นจะไม่เห็นความต่างในกรณีที่แย่ที่สุด

---

## 4. สภาพ branch บน remote หลัง push

```
b78b3f8  refs/heads/main          <- ไม่ขยับ เท่าเดิมทั้งก่อนและหลัง push
dc5e860  refs/heads/mko-phase2    <- อัปเดตแล้ว
```

มี 2 branch บน remote เท่านั้น ไม่มี branch ใหม่เกิดขึ้น

### `main` ยืนยันสองรอบ

| จังหวะ | `refs/heads/main` |
|---|---|
| ก่อน push | `b78b3f8bf895685874d9a52c66b45569072f0514` |
| หลัง push | `b78b3f8bf895685874d9a52c66b45569072f0514` |

**ไม่มีการ push `main` และไม่มีการ merge เข้า `main`**

### local หลัง push

```
## mko-phase2...origin/mko-phase2
staged:    0
modified:  0
```

ไม่มีเลข `[ahead N]` หรือ `[behind N]` ต่อท้าย → local กับ remote ตรงกันพอดี

---

## 5. สิ่งที่ขึ้นไปบน remote

| ไฟล์ | |
|---|---|
| `db/migrations/005_web_schema.sql` | `+148 −18` — nullable `careers`/`detail` · `title` 3 คอลัมน์เป็น 500 · trigger 4 ตัว · GRANT EXECUTE |
| `eval/web_schema_check.py` | `+127` — ข้อตรวจความกว้างคอลัมน์ 16 ข้อ · trigger 8 ข้อ · nullable 2 ข้อ |
| `docs/MIGRATION_005_FINAL_REVIEW.md` | `+602` ใหม่ — Final Review รอบสอง · M1–M17 · import mapping · แผน cutover |
| `docs/SUPABASE_LIVE_VERIFICATION.md` | `+1173` ใหม่ — หลักฐานจาก production 32 คำสั่ง · **project ref ถูก redact เป็น `<SUPABASE_PROJECT_REF>`** |

รวม **4 ไฟล์ · +2032 −18**

### ไฟล์ที่ไม่ได้ขึ้นไป

| ไฟล์ | เหตุผล |
|---|---|
| `docs/MIGRATION_005_FINAL_COMMIT_REPORT.md` | untracked · ไม่อยู่ในขอบเขต 4 ไฟล์ที่อนุมัติให้ commit |
| `docs/MIGRATION_005_FINAL_PUSH_REPORT.md` (ไฟล์นี้) | untracked · สร้างหลัง push |
| `docs/MIGRATION_005_CORRECTIVE_PUSH_REPORT.md` | เอกสารค้างจากรอบก่อน ไม่ใช่รอบนี้ |
| untracked อีก **53** รายการใน `docs/` | ไม่เกี่ยวกับ Migration 005 Final Review |

---

## 6. เรื่องที่ต้องรู้ — project ref ถูก redact ไปแล้วและ push ขึ้น public repo แล้ว

รีโปนี้เป็น **public** (`https://api.github.com/repos/pattana-ketchot/Project-Chataipnru`
ตอบ `200` โดยไม่ต้อง auth) ก่อน commit จึงแทนค่า Supabase project ref จริง
ด้วย `<SUPABASE_PROJECT_REF>` ใน `SUPABASE_LIVE_VERIFICATION.md`

เหตุผล: ไฟล์นั้นอธิบายแบบจำลองสิทธิ์ของ production ไว้ครบ — RLS เป็นด่านเดียว ·
`user_profiles` อ่านได้โดยทุกคนขณะที่เก็บ `email`/`full_name` · `anon` เรียก
security-definer function ได้ 3 ตัว · bucket `course-assets` เป็น public ·
`auth_leaked_password_protection` ปิดอยู่

**ตอนนี้ push ไปแล้ว การแก้ด้วย `--amend` ไม่ใช่ทางเลือกอีกต่อไป**
ถ้าภายหลังตัดสินใจว่าต้องการค่า ref จริงในไฟล์ ทำได้ด้วย commit ใหม่ที่ใส่ค่ากลับเข้าไป
(ไม่ต้องเขียนประวัติทับ เพราะค่าที่ถูกปิดไว้ไม่ใช่ความลับที่รั่ว — เป็นการไม่ใส่ตั้งแต่ต้น)

ในทางกลับกัน **ถ้าตัดสินใจว่าค่า ref ไม่ควรอยู่ในรีโปนี้เลย ก็ไม่ต้องทำอะไรเพิ่ม** —
สถานะปัจจุบันคือสถานะที่ปลอดภัยอยู่แล้ว ค่าจริงยังหาได้จาก Supabase Dashboard
หรือ `.mcp.json` ของรีโปหน้าเว็บ และฉบับที่มี ref ครบยังอยู่ที่
`course-advisor-system/docs/SUPABASE_LIVE_VERIFICATION.md`

---

## 7. สรุปสถานะ Migration 005 ทั้งเส้น

```
97686a1  docs: record the consolidation feasibility study
   |
de42e38  fix(db): match the source schema's keys in the web schema
   |       แก้ external_news ให้ตรงกับต้นทาง (slug/detail_url/source)
   |
f72b418  docs: correct the Supabase facts and record where they came from
   |       แก้ข้อสรุปที่ผิดเรื่อง FK/CHECK/UNIQUE ของ Supabase
   |
dc5e860  fix(db): finalize web schema migration from live verification   <- อยู่บน remote แล้ว
         ปิดเคสจากหลักฐาน production จริง · CLOSED 9 · ACCEPTED 4 · BLOCKED 4
```

| | |
|---|---|
| migration 005 บน production database | **ยังไม่ apply** |
| schema `web` บน production | **ยังไม่มี** |
| ข้อมูลจาก Supabase | **ยังไม่ย้ายแม้แถวเดียว** |
| Supabase Auth / Storage / Edge Function / cron | **ยังไม่แตะ** |

สิ่งที่ `dc5e860` เปลี่ยนคือ **ไฟล์ในรีโปเท่านั้น** ไม่มีอะไรในระบบที่ทำงานอยู่เปลี่ยน

---

## 8. ขั้นถัดไป — รอการตัดสินใจ 5 เรื่อง

```
B1  Authorization ชั้น API  (M11 + M13)
    policy 24 ตัวบนตาราง + 8 ตัวบน storage ต้องกลายเป็นเงื่อนไขที่ API ตรวจ
    จุดที่พลาดไม่ได้:
      news                 คนทั่วไปเห็นเฉพาะ status = 'published'  (เป็นขอบเขตความปลอดภัย)
      knowledge_articles   คนทั่วไป "อ่านไม่ได้เลย" ต้องเป็น admin/editor
    ต้องตัดสินด้วยว่าจะรักษาการแยก admin/editor ไหม — ของจริงยังไม่มีใครถือ editor

B2  ผู้เขียนเนื้อหา  (M10)
    เนื้อหาทั้งฐานเขียนโดยบัญชีเดียว (distinct = 1) ตัดสินแค่ 1 ราย ไม่ใช่ 3
    ทางเลือก: จับคู่กับแถวใน public.users ด้วยมือ
              หรือยอมให้ created_by/updated_by เป็น NULL ทั้ง 15 แถว

B3  PDF กำพร้า 4 ไฟล์ 10.4 MiB  (M7)
    knowledge_articles มี 0 แถว แต่ bucket knowledge-files มี 4 ไฟล์
    ชื่อเป็น UUID ล้วน ไม่มีทางรู้ว่าแต่ละไฟล์คืออะไร (U8)
    ห้ามลบ — ตัดสินว่าเก็บที่เดิม / ย้าย / สร้างแถวให้ใหม่

B4  PII ใน courses.detail
    1 แถวที่มี detail (5 คีย์) มี faculty[].email  รีโปหน้าเว็บเป็น public

U3  ตัวดึงข่าวค้าง 10 วัน
    pg_cron */30 เปิดอยู่ แต่ max(synced_at) = 2026-09-22
    ควรตรวจ cron.job_run_details หรือ Edge Function logs ก่อนวางแผน cutover
    ถ้าตัวดึงข่าวพังอยู่ การย้ายจะพาปัญหาไปด้วย
```

เมื่อตัดสินแล้วจึงขออนุมัติแยกเป็นขั้น ๆ

```
1. apply 005 กับ production database
2. data migration ทีละตาราง   ai_settings (1) -> courses (12) -> news (3)
                              knowledge_articles ข้าม (0 แถว)
                              external_news ไว้ท้ายสุด เพราะมีผู้เขียนอัตโนมัติ
3. cutover sync-sci-news       ต้องปิดทั้ง pg_cron job และ Edge Function
4. re-embed 12 chunk ด้วย bge-m3
```

---

## STOP

```
PUSH:                 เสร็จแล้ว   mko-phase2 -> origin/mko-phase2   (dc5e860)
PUSH main:            NONE
APPLY MIGRATION 005:  NONE
DATA MIGRATION:       NONE
PRODUCTION WRITE:     NONE
DEPLOY / RESTART:     NONE
MERGE main:           NONE
```
