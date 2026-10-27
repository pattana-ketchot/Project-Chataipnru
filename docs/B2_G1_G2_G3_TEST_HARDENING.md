# B2 — G1 / G2 / G3 Test Hardening

| | |
|---|---|
| วันที่ | 2026-10-02 |
| ขอบเขต | เพิ่มชุดตรวจอัตโนมัติคุ้มการตัดสินใจ `RESOLVED_WITH_NULL_LEGACY_AUTHOR` |
| ไฟล์ที่แก้ | **`eval/web_schema_check.py` ไฟล์เดียว** · `+255 −1` |
| **ผลทดสอบ** | **`web_schema_check` 103 ผ่าน · 0 ไม่ผ่าน · ค้าง 2** (จาก 76) |
| **G1** | **PASS** — 12 ข้อ |
| **G2** | **PASS** — 10 ข้อ (เชิงพฤติกรรมจริง) |
| **G3** | **`G3_API_ENFORCEMENT_PENDING_B1`** — 5 ผ่าน · 2 ค้าง |
| **สถานะ** | **`READY_FOR_REVIEW`** |

```
Migration 005 แก้         NONE        Production Write      NONE
Production code แก้        NONE        Apply Migration 005   NONE
Data Migration            NONE        Supabase Write        NONE
Deploy / Restart          NONE        Re-embed              NONE
Commit / Push             NONE        Merge main            NONE
```

**ไม่ใช่ `READY_FOR_PRODUCTION`**

---

## 1. Files inspected

| ไฟล์ | สิ่งที่ยืนยัน |
|---|---|
| `db/migrations/005_web_schema.sql` | คอลัมน์ผู้เขียน 4 ตัว nullable · FK → `public.users(id)` · `ON DELETE SET NULL` · ไม่มี `DEFAULT` · ตารางจริงคือ **`web.site_courses`** และ **`web.news`** |
| `eval/web_schema_check.py` | โครงสร้างชุดตรวจ · `Checks` มี `check` / `rejects` / `accepts` / `report` · **ไม่มี** ช่องทางรายงาน "ค้าง" |
| `docs/B2_LEGACY_AUTHOR_RESOLUTION.md` | สิ่งที่ต้องคุ้ม · G1/G2/G3 ที่ระบุไว้ในข้อ 9.2 |
| `docs/AUTHORIZATION_USER_MAPPING_DESIGN.md` | สัญญา §6.4 ข้อ 1 · 1a · 1b ที่ G3 ต้องตรวจ |
| `db/schema.sql` | `public.users` บังคับแค่ `email` (CITEXT UNIQUE) กับ `password_hash` → fixture ขั้นต่ำของ G2 |
| `backend/` · `webapi/` | **ค้นแล้วไม่พบโค้ดบริการใดอ้างถึง `web.site_courses` หรือ `web.news` เลย** → ยืนยันว่า G3 ค้างจริง ไม่ใช่ข้ออ้าง |

### 1.1 ยืนยันชื่อตารางก่อนเขียนอะไร

คำสั่งพูดถึง `courses.created_by` และ `news.created_by` ส่วน 005 **ไม่มีตารางชื่อ
`courses` หรือ `news` ตรง ๆ** ปลายทางคือ

```
public.courses (Supabase)  ->  web.site_courses
public.news    (Supabase)  ->  web.news
```

`public.courses` ที่มีอยู่ฝั่งเราเป็นข้อเท็จจริงของหลักสูตรจากเอกสาร มคอ. **คนละเรื่อง**
ชุดตรวจใหม่ชี้ไป `web.site_courses` และ `web.news` เท่านั้น

### 1.2 สิ่งที่พบว่าชุดตรวจเดิมคุ้มไว้แค่ไหน

| สิ่งที่คุ้มอยู่แล้ว | |
|---|---|
| `news.created_by` เป็น NULL ได้ | 1 ข้อ |
| `news.created_by` ที่ไม่มีอยู่จริงถูกปฏิเสธ | 1 ข้อ |
| `ON DELETE SET NULL` ทั้ง 8 FK | **อ่าน `confdeltype` จาก catalog — ไม่ใช่เชิงพฤติกรรม** |
| ลบ **หลักสูตร** แล้ว `site_courses.course_id` กลายเป็น NULL | มีอยู่แล้วเชิงพฤติกรรม (ใช้เป็นแม่แบบของ G2) |

→ คอลัมน์ผู้เขียน **3 ใน 4 ตัวไม่มีข้อตรวจคุ้มเลย** และ `ON DELETE SET NULL`
กับ `users` ยังไม่เคยถูกพิสูจน์เชิงพฤติกรรม

---

## 2. Files modified

```
eval/web_schema_check.py    +255 −1
```

**ไฟล์เดียว** · ไม่แก้ `db/migrations/005_web_schema.sql` · ไม่แก้ `backend/` · ไม่แก้ `webapi/`
· ไม่แก้ `Caddyfile` · ไม่แก้ `docker-compose.prod.yml`

ยืนยันด้วย `git diff --name-only` → `eval/web_schema_check.py` รายการเดียว
และ `git diff -- db/migrations/005_web_schema.sql` → ว่างเปล่า

### 2.1 test helper ที่เพิ่ม — 2 ตัว

| helper | ทำอะไร | ทำไมต้องมี |
|---|---|---|
| `Checks.pending(name, why)` | บันทึกข้อที่ยังพิสูจน์ที่นี่ไม่ได้ **แยกจาก `passed` และ `failed`** · `report()` พิมพ์ `ค้าง N` เพิ่ม · **ไม่ทำให้ exit code เป็น 1** | ชุดนี้ตรวจ schema ของฐานข้อมูล ข้อที่ด่านจริงอยู่ชั้น API พิสูจน์ที่นี่ไม่ได้ · **การนับข้อเหล่านั้นว่าผ่านจะทำให้อ่านรายงานแล้วเข้าใจว่าฐานข้อมูลกันให้แล้ว ซึ่งไม่จริง** และเป็นความเข้าใจผิดที่อันตรายกว่าการไม่มีข้อตรวจเลย |
| `Checks.returns(conn, name, sql, params, ok)` | รัน SQL ที่ต้องคืนแถว ตรวจแถวนั้น · **error ของฐานข้อมูลนับเป็น "ไม่ผ่าน" ข้อเดียว** ไม่โยนออกไปทั้งกลุ่ม | ดูข้อ 11.2 — ค้นพบจากการทดสอบ mutation ว่าถ้าไม่มีตัวนี้ regression จะทำให้กลุ่มทั้งกลุ่มหยุดกลางคัน รายงานบอกแค่ "กลุ่มนี้พัง" |

---

## 3. G1 tests added — `G1_SCHEMA_NULLABILITY`

กลุ่ม `[6]` · ฟังก์ชัน `legacy_author_nullability()` · **12 ข้อ**

### 3.1 ระดับ catalog — 8 ข้อ

อ่านจาก `pg_attribute` ของ PostgreSQL จริง ครบทั้ง 4 คอลัมน์

```
4 ข้อ   attnotnull = false     คอลัมน์เป็น NULL ได้
4 ข้อ   atthasdef  = false     ไม่มี DEFAULT
```

**ข้อ `atthasdef` เป็นข้อที่คำสั่งไม่ได้สั่ง แต่สำคัญกับการตัดสินใจนี้โดยตรง** —
ต้นทาง Supabase ตั้ง `courses.created_by DEFAULT auth.uid()` ถ้าปลายทางมี `DEFAULT`
ทำนองเดียวกัน การ `INSERT` ที่ละคอลัมน์นี้จะได้ **"ใครก็ตามที่กำลังรันคำสั่งนำเข้า"**
ยัดเข้ามาเงียบ ๆ ซึ่งคือ **การยัดเจ้าของผิดคน** ที่การตัดสินใจนี้สั่งห้ามโดยตรง

### 3.2 เชิงพฤติกรรม — 4 ข้อ

```
2 ข้อ   ใส่ author เป็น NULL ตรง ๆ แล้วได้แถวจริง            (site_courses · news)
2 ข้อ   ละคอลัมน์ผู้เขียนไปเลย แล้วได้ NULL ทั้งคู่           (site_courses · news)
```

ใช้ `RETURNING` อ่านค่าที่ฐานข้อมูลเก็บจริงกลับมาตรวจ — **ไม่ใช่แค่ "ไม่ error"**
`accepts()` ที่มีอยู่พิสูจน์แค่ว่าคำสั่งไม่ล้ม ไม่ได้พิสูจน์ว่าได้แถวที่ค่าถูก

ข้อ "ละคอลัมน์ไปเลย" คือ **รูปแบบที่การนำเข้า legacy จะใช้จริง** ซึ่งต่างจากการส่ง
`NULL` มาตรง ๆ และเป็นจุดที่ `DEFAULT` จะออกฤทธิ์ถ้ามี

## 4. G1 result — **PASS 12 / 12**

```
ผ่าน   G1 site_courses.created_by เป็น NULL ได้
ผ่าน   G1 site_courses.updated_by เป็น NULL ได้
ผ่าน   G1 news.created_by เป็น NULL ได้
ผ่าน   G1 news.updated_by เป็น NULL ได้
ผ่าน   G1 site_courses.created_by ไม่มี DEFAULT (ละคอลัมน์แล้วต้องได้ NULL ไม่ใช่ค่าแทน)
ผ่าน   G1 site_courses.updated_by ไม่มี DEFAULT (ละคอลัมน์แล้วต้องได้ NULL ไม่ใช่ค่าแทน)
ผ่าน   G1 news.created_by ไม่มี DEFAULT (ละคอลัมน์แล้วต้องได้ NULL ไม่ใช่ค่าแทน)
ผ่าน   G1 news.updated_by ไม่มี DEFAULT (ละคอลัมน์แล้วต้องได้ NULL ไม่ใช่ค่าแทน)
ผ่าน   G1 site_courses: ใส่ author เป็น NULL ตรง ๆ แล้วได้แถวจริง
ผ่าน   G1 site_courses: ละคอลัมน์ผู้เขียนแล้วได้ NULL ทั้งคู่
ผ่าน   G1 news: ใส่ author เป็น NULL ตรง ๆ แล้วได้แถวจริง
ผ่าน   G1 news: ละคอลัมน์ผู้เขียนแล้วได้ NULL ทั้งคู่
```

---

## 5. G2 behavioral tests added — `G2_FK_DELETE_BEHAVIOR`

กลุ่ม `[7]` · ฟังก์ชัน `author_fk_delete_behaviour()` · **10 ข้อ**

### 5.1 flow ตามที่สั่ง

```
1. สร้าง test user ใน public.users  ->  email 'webchk-g2@test.invalid'  (commit ก่อน)
2. สร้าง test content row ใน web.site_courses / web.news
3. ตั้ง created_by = updated_by = test user
4. ตรวจก่อนลบว่าตั้งได้จริง                     <- ข้อกันการผ่านแบบว่างเปล่า
5. DELETE test user
6. ตรวจว่าผู้ใช้ถูกลบจริง
7. ตรวจว่าแถวเนื้อหายังอยู่
8. ตรวจว่า created_by IS NULL
9. ตรวจว่า updated_by IS NULL
10. rollback + ลบ fixture + commit
```

### 5.2 สองข้อที่เพิ่มเองเพราะถ้าไม่มีจะผ่านแบบว่างเปล่า

| ข้อ | ป้องกันอะไร |
|---|---|
| **"ก่อนลบ author ถูกตั้งเป็นผู้ใช้จริงทั้งสองคอลัมน์"** | ถ้า `INSERT` ไม่ได้ตั้ง author ตั้งแต่ต้น (เช่นเพราะพิมพ์ชื่อคอลัมน์ผิด) ข้อ 7–9 จะผ่าน**โดยไม่ได้พิสูจน์อะไรเลย** — `created_by` เป็น NULL อยู่แล้วตั้งแต่แรก |
| **"ผู้ใช้ถูกลบจริง (ไม่ใช่ลบไม่สำเร็จแล้วผ่านไปเฉย ๆ)"** | ถ้า `DELETE` แก้ 0 แถว (เช่นเพราะ id ผิด) ข้อที่เหลือก็ผ่านโดยไม่ได้ทดสอบพฤติกรรม `ON DELETE` เลย |

### 5.3 fixture ขั้นต่ำ · ความปลอดภัย

| | |
|---|---|
| fixture | `users (email, password_hash)` เท่านั้น — 2 คอลัมน์ที่ `db/schema.sql` บังคับ |
| อีเมลที่ใช้ | `webchk-g2@test.invalid` — โดเมน `.invalid` สงวนไว้ไม่มีอยู่จริง (RFC 2606) |
| `password_hash` | ข้อความที่ระบุชัดว่าไม่ใช่ hash จริง ไม่มีรหัสผ่านจริงอยู่ในชุดตรวจ |
| ไม่แตะผู้ใช้จริง | ลบด้วย `WHERE email = 'webchk-g2@test.invalid'` เท่านั้น ไม่เคยลบด้วยเงื่อนไขกว้าง |
| ด่านกันฐานจริง | `guard()` เดิม — ชื่อฐานต้องอยู่ใน `{web_test, crawl_test, e2e_test}` และ URL ห้ามมีคำว่า `course_advisor` |
| cleanup | ตามแม่แบบเดิมของ `partial_unique()` — `finally: rollback` → ลบ fixture → `commit` |

## 6. G2 result — **PASS 10 / 10**

```
ผ่าน   G2 site_courses: ก่อนลบ author ถูกตั้งเป็นผู้ใช้จริงทั้งสองคอลัมน์
ผ่าน   G2 site_courses: ผู้ใช้ถูกลบจริง (ไม่ใช่ลบไม่สำเร็จแล้วผ่านไปเฉย ๆ)
ผ่าน   G2 site_courses: ลบผู้ใช้แล้วแถวเนื้อหายังอยู่
ผ่าน   G2 site_courses: created_by กลายเป็น NULL
ผ่าน   G2 site_courses: updated_by กลายเป็น NULL
ผ่าน   G2 news: ก่อนลบ author ถูกตั้งเป็นผู้ใช้จริงทั้งสองคอลัมน์
ผ่าน   G2 news: ผู้ใช้ถูกลบจริง (ไม่ใช่ลบไม่สำเร็จแล้วผ่านไปเฉย ๆ)
ผ่าน   G2 news: ลบผู้ใช้แล้วแถวเนื้อหายังอยู่
ผ่าน   G2 news: created_by กลายเป็น NULL
ผ่าน   G2 news: updated_by กลายเป็น NULL
```

**พิสูจน์แล้วเชิงพฤติกรรม**

```
ลบผู้ใช้  ->  เนื้อหายังอยู่  ->  author FK กลายเป็น NULL
```

ไม่ใช่การอ่าน `pg_constraint` อีกแล้ว

---

## 7. G3 enforcement layer

### 7.1 ด่านอยู่ที่ชั้นไหน — แยกให้ชัดก่อนเขียนอะไร

| ชั้น | บังคับ `created_by` immutability ไหม | หลักฐาน |
|---|---|---|
| **Migration 005 / schema** | **ไม่** และ **ไม่ควร** | ไม่มี trigger หรือ rule ใดบน `web.site_courses` / `web.news` นอกจาก `trg_*_updated_at` · การบังคับ authorization ไม่ใช่หน้าที่ของ schema |
| **ชั้น API** | **ใช่ — แต่ยังไม่มีโค้ด** | `grep -rn 'web.site_courses\|web.news' backend/ webapi/` → **ไม่พบเลย** · `courses.py` ไม่มี endpoint เขียน |
| **เอกสารสัญญา** | เป็นที่บันทึกข้อตกลง | `AUTHORIZATION_USER_MAPPING_DESIGN.md` §6.4 ข้อ 1 · 1a · 1b |

**ไม่สร้าง trigger ใน 005 และไม่สร้าง API เพียงเพื่อให้ข้อตรวจผ่าน** ตามที่สั่ง

### 7.2 G3 จึงตรวจสามอย่างที่ตรวจได้จริง

| # | ข้อตรวจ | เหตุผล |
|---|---|---|
| 1 | ฐานข้อมูล **ไม่มี** trigger ที่ตั้งใจกัน `created_by` (มีแต่ตัวดูแล `updated_at`) | ถ้าวันหนึ่งมีใครเพิ่ม trigger เข้ามา ต้องรู้ตัว ไม่ใช่มีพฤติกรรมใหม่โผล่มาเงียบ ๆ |
| 2 | ฐานข้อมูล **ยอมให้** `UPDATE` เปลี่ยน `created_by` จาก NULL เป็นค่าอื่นได้ | **บันทึกสภาพที่เป็นจริง** เพื่อไม่ให้ใครอ่าน G1/G2 แล้วเข้าใจผิดว่าฐานข้อมูลกันเรื่องนี้ให้แล้ว · เป็น characterization test ไม่ใช่ข้อที่บอกว่า "ดี" |
| 3 | สัญญาในเอกสารยังอยู่ครบ 3 ข้อ | ถ้าใครลบกฎทิ้ง ต้องมีอะไรฟ้อง — ทดสอบแล้วว่าจับได้ (ดู mutation [F] ในข้อ 11.3) |

### 7.3 สองข้อที่รายงานเป็น "ค้าง" ไม่ใช่ "ผ่าน"

```
ค้าง   G3 API บังคับ created_by immutability — G3_API_ENFORCEMENT_PENDING_B1
       ยังไม่มี endpoint POST/PATCH ของ web.site_courses / web.news
       จึงยังไม่มีอะไรให้ทดสอบ ต้องรอ B1 เฟส 1

ค้าง   G3 PATCH ที่ส่ง created_by ปลอมมาใน body ต้องไม่มีผล — G3_API_ENFORCEMENT_PENDING_B1
       ต้องเขียนพร้อม endpoint ในรอบ B1 ห้ามสร้าง API เพียงเพื่อให้ข้อนี้ผ่าน
```

**ไม่ถูกนับว่าผ่าน** และ **ไม่ทำให้ชุดตรวจ fail** — `report()` คืน `not self.failed`
ส่วน `pendings` พิมพ์แยกและนับแยก

## 8. G3 result — **`G3_API_ENFORCEMENT_PENDING_B1`**

```
ผ่าน   G3 ฐานข้อมูลไม่มี trigger ที่ตั้งใจกัน created_by (มีแต่ตัวดูแล updated_at)
ผ่าน   G3 ฐานข้อมูลยอมให้ UPDATE เปลี่ยน created_by จาก NULL เป็นค่าอื่นได้
       (จึงต้องกันที่ API ไม่ใช่ที่ schema)
ผ่าน   G3 เอกสารระบุว่า CREATE ตั้งทั้ง created_by และ updated_by จากผู้เรียก
ผ่าน   G3 เอกสารระบุว่า UPDATE ห้ามแตะ created_by
ผ่าน   G3 เอกสารระบุว่าห้ามเชื่อ created_by/updated_by จาก request body

ค้าง   G3 API บังคับ created_by immutability             — G3_API_ENFORCEMENT_PENDING_B1
ค้าง   G3 PATCH ที่ส่ง created_by ปลอมมาใน body ต้องไม่มีผล  — G3_API_ENFORCEMENT_PENDING_B1
```

**5 ผ่าน · 2 ค้าง · 0 ไม่ผ่าน** — ถือเป็น PENDING ไม่ใช่ความล้มเหลวของ Migration 005

### 8.1 สัญญาที่เอกสารตรวจแล้วว่ายังอยู่

```
CREATE   created_by = authenticated user     updated_by = authenticated user
UPDATE   created_by unchanged                updated_by = authenticated user
body     created_by / updated_by must not be trusted
```

---

## 9. Full test counts

| ชุด | ก่อน | **หลัง** | ค้าง / ข้าม |
|---|---:|---:|---|
| `eval/web_schema_check.py` | 76 | **103** (+27) | **ค้าง 2** |
| `eval/crawl_download_check.py` | 140 | 140 | ข้าม 1 (Linux-only) |
| `eval/crawl_ingest_worker_check.py` | 187 | 187 | — |
| `eval/crawl_approval_check.py` | 84 | 84 | — |
| `eval/crawl_state_check.py` | 32 | 32 | — |
| `eval/document_endpoint_check.py` | 16 | 16 | — |
| **รวม** | 535 | **562** | **ค้าง 2 · ข้าม 1** |

```
passed   562
failed     0
pending    2    (G3_API_ENFORCEMENT_PENDING_B1)
skipped    1    (crawl_download_check กลุ่ม F1 — ต้องรันบน Linux)
```

+27 = G1 **12** + G2 **10** + G3 **5**

**ข้าม 1** คือกลุ่ม `[5] สิทธิ์ของไฟล์ใน staging` ของ `crawl_download_check` ซึ่งข้าม
เพราะรันบน Windows (`os.name='nt'` บิตโหมดไม่มีความหมาย) — บน Linux กลุ่มนั้นให้อีก
**25 ข้อ** รวมเป็น **587** ตัวเลขนี้เทียบกับรอบก่อนตรง ๆ ไม่ได้ ต้องเทียบในแพลตฟอร์มเดียวกัน

### 9.1 สภาพแวดล้อม

```
PostgreSQL 16.15 (pgvector/pgvector:pg16) ในคอนเทนเนอร์ทิ้ง  127.0.0.1:55439
db/schema.sql                        OK
001 -> 005 จากฐานใหม่                  OK ทุกไฟล์
005 ลงซ้ำ (idempotency)                OK
role advisor_api / advisor_ingest    LOGIN + GRANT ตาม db/20-roles.sh
trigger ที่ได้                         4 ตัว tgtype = 19 ทุกตัว
ความกว้าง title                       news/external_news/knowledge_articles = 500 · site_courses = 255

ทำความสะอาดแล้ว   containers 0 · volumes 0
ไม่แตะ production ไม่แตะ Supabase
```

## 10. Regression result

**ไม่มี regression** — ทุกชุดเดิมได้ตัวเลขเท่าเดิมทุกตัว

```
crawl_download_check        140 ผ่าน · 0 ไม่ผ่าน · ข้าม 1      เท่าเดิม
crawl_ingest_worker_check   187 ผ่าน · 0 ไม่ผ่าน               เท่าเดิม
crawl_approval_check         84 ผ่าน · 0 ไม่ผ่าน               เท่าเดิม
crawl_state_check            32 ผ่าน · 0 ไม่ผ่าน               เท่าเดิม
document_endpoint_check       16 tests OK                     เท่าเดิม
web_schema_check             76 -> 103 ผ่าน · 0 ไม่ผ่าน         ข้อเดิมผ่านครบ ไม่มีข้อใดเปลี่ยนเป็นไม่ผ่าน
```

migration 001 → 005 จากฐานใหม่ยังผ่านครบ · ลง 005 ซ้ำยังไม่ error

---

## 11. Diff summary

```
eval/web_schema_check.py    +255 −1     (ไฟล์เดียว)
```

### 11.1 สิ่งที่เพิ่ม

| ส่วน | บรรทัด |
|---|---|
| `Checks.pending()` | helper รายงานข้อค้างแยกจากผ่าน/ไม่ผ่าน |
| `Checks.returns()` | helper รัน SQL ที่ต้องคืนแถว · error นับเป็นไม่ผ่านข้อเดียว |
| `Checks.report()` | พิมพ์ `ค้าง N` และรายละเอียดข้อค้าง · **return value ไม่เปลี่ยน** (`not self.failed`) |
| `AUTHOR_COLUMNS` | รายการ 4 คอลัมน์ที่ต้องคุ้ม |
| `legacy_author_nullability()` | กลุ่ม `[6]` G1 · 12 ข้อ |
| `author_fk_delete_behaviour()` | กลุ่ม `[7]` G2 · 10 ข้อ |
| `author_immutability_contract()` | กลุ่ม `[8]` G3 · 5 ข้อ + 2 ค้าง |
| `G3_PENDING_TAG` · `_DESIGN_DOC` | ค่าคงที่ของ G3 |
| `main()` | เรียกสามกลุ่มใหม่ต่อท้าย `privileges()` |

**ไม่ลบหรือแก้ข้อตรวจเดิมแม้ข้อเดียว** — `−1` คือบรรทัดเดียวใน `report()` ที่ถูกแทน

### 11.2 ⚠ บั๊กในโค้ดทดสอบของผมเองที่พบและแก้แล้ว 2 จุด

พบจากการทดสอบ mutation ไม่ใช่จากการอ่านโค้ด

| # | อาการ | สาเหตุ | แก้อย่างไร |
|---|---|---|---|
| 1 | เมื่อจำลองว่ามีคนตั้ง `NOT NULL` ให้คอลัมน์ผู้เขียน **กลุ่มทั้งกลุ่มหยุดกลางคัน** ด้วย `NotNullViolation` แทนที่จะบอกว่าข้อไหนไม่ผ่าน | รุ่นแรกใช้ `cursor` ตรง ๆ โดยไม่ดัก `psycopg.Error` | เพิ่ม `Checks.returns()` และให้ G2 ดัก error ต่อตาราง · ตอนเกิด regression จริงรายงานบอก "สามข้อนี้ไม่ผ่านเพราะอะไร" ไม่ใช่ "กลุ่มนี้พัง" |
| 2 | ข้อ G3 **ไม่ผ่านทั้งที่ schema ถูก** | รุ่นแรกใช้ CTE ที่เขียนข้อมูล (`WITH ins AS (INSERT ...) UPDATE ... WHERE id = (SELECT id FROM ins)`) — PostgreSQL ไม่ให้ `UPDATE` เห็นแถวที่ CTE เพิ่ง `INSERT` ในคำสั่งเดียวกัน `UPDATE` จึงแก้ 0 แถว | แยกเป็นสองคำสั่งแล้วห่อ error เอง |

บั๊กที่ 2 เป็นข้อตรวจที่ **ไม่ผ่านโดยที่ระบบไม่ได้ผิด** ซึ่งถ้าปล่อยไว้จะกลายเป็น
ข้อที่คนรุ่นหลังปิดทิ้งเพราะคิดว่ามันเสีย

### 11.3 ⚠ ทดสอบว่าข้อตรวจมีฟันจริง — mutation testing

ข้อตรวจที่ไม่มีทางไม่ผ่านไม่ได้คุ้มอะไร ทดสอบโดย **ทำลายดีไซน์ในคอนเทนเนอร์ทิ้ง**
แล้วดูว่าจับได้ไหม — **ไม่แก้ `005` แม้บรรทัดเดียว** ใช้ `ALTER` ในฐานทดสอบแล้วคืนค่า

| # | สิ่งที่ทำลาย | G1/G2/G3 ผ่าน | **ไม่ผ่าน** |
|---|---|---:|---:|
| **A** | **ไม่ดัดแปลง (ของจริง)** | **27** | **0** |
| B | `web.news.created_by` → `SET NOT NULL` | 19 | **8** |
| C | `web.site_courses.created_by` → `SET DEFAULT '…001'::uuid` | 25 | **2** |
| D | FK `news.created_by` → ไม่มี `ON DELETE` (NO ACTION) | 23 | **4** |
| E | FK `site_courses.updated_by` → `ON DELETE CASCADE` | 24 | **3** |
| F | ลบกฎ 1b ออกจากเอกสารออกแบบ | 26 | **1** |
| **G** | **คืนเอกสารกลับ** | **27** | **0** |

ทั้ง 5 การทำลายถูกจับได้ · และคืนสภาพแล้วกลับเป็น 0 ทุกครั้ง
**เอกสารออกแบบถูกคืนครบ** (715 บรรทัด · กฎ 1b อยู่ครบ) และยืนยันแล้วหลังทดสอบ

กรณี **E** สำคัญเป็นพิเศษ: `ON DELETE CASCADE` จะทำให้ **ลบผู้ใช้แล้วเนื้อหาหายไปด้วย**
ซึ่งเป็นผลตรงข้ามกับที่ต้องการ และเป็นสิ่งที่การอ่าน `confdeltype` เพียงอย่างเดียว
ก็จับได้อยู่แล้ว — แต่ G2 จับได้ด้วยและบอกชัดว่า **แถวเนื้อหาหายไป** ไม่ใช่แค่
"ค่า `confdeltype` ไม่ตรง"

---

## 12. Remaining blockers

| # | Blocker | ระดับ | สถานะ |
|---|---|---|---|
| **B1** | Authorization ชั้น API ยังไม่ได้เขียน | **สูงสุด** | design พร้อม · **ครึ่งหนึ่งของงานอยู่ในรีโปหน้าเว็บ `FoMake/Univercity` ซึ่งยังไม่ได้รับอนุมัติให้เขียน** (Owner decision ข้อ 5) · G3 ค้างอยู่กับข้อนี้ |
| **B3** | PDF กำพร้า 4 ไฟล์ 10.4 MiB | กลาง | ยังต้องตัดสิน · **ห้ามลบ** |
| **B4** | PII ใน `courses.detail` (`faculty[].email`) · รีโปหน้าเว็บเป็น public | กลาง | ยังต้องตัดสิน |
| **U3** | ตัวดึงข่าวค้าง 10 วัน (`max(synced_at)` = 2026-09-22 ขณะที่ cron `*/30` เปิดอยู่) | กลาง | ควรตรวจก่อนวางแผน cutover ของ `external_news` |
| **N2** | `ai_settings.updated_by` จะใช้หลัก NULL เดียวกันไหม | ต่ำ | ต้นทาง 1 แถวที่ไม่ NULL · ยังไม่ได้รับคำสั่งให้ตัดสิน |
| **N3** | แยกแถว legacy จากแถวใหม่ไม่ได้จากข้อมูล | ต่ำ | ไม่เป็น blocker · ถ้าจะแก้ต้องเป็น migration 006 ไม่ใช่แก้ 005 |

### 12.1 ที่ปิดแล้วในรอบนี้

```
G1   ช่องว่าง nullability ของ 3 คอลัมน์ที่ไม่มีข้อตรวจ    ->  ปิดแล้ว 12 ข้อ
G2   ON DELETE SET NULL ที่ยังไม่พิสูจน์เชิงพฤติกรรม       ->  ปิดแล้ว 10 ข้อ
G3   created_by immutability                            ->  ตรวจเท่าที่ตรวจได้ 5 ข้อ
                                                             ส่วนที่เหลือค้างรอ B1 อย่างชัดเจน
```

### 12.2 เรื่องที่ไม่พบว่าต้องแก้

**ไม่พบจุดใดที่ต้องแก้ `Migration 005` หรือ production code** — schema รองรับการตัดสินใจ
อยู่แล้วครบทุกข้อ และไม่มีอะไรใน 005 ที่ขัดกับ `RESOLVED_WITH_NULL_LEGACY_AUTHOR`

---

## 13. Final classification

# `READY_FOR_REVIEW`

| | |
|---|---|
| ไฟล์ที่แก้ | **1** — `eval/web_schema_check.py` `+255 −1` |
| Migration 005 | **ไม่ถูกแตะ** (`git diff` ว่างเปล่า) |
| production code | **ไม่ถูกแตะ** |
| ผลทดสอบ | **562 ผ่าน · 0 ไม่ผ่าน · ค้าง 2 · ข้าม 1** |
| G1 | **PASS** 12/12 |
| G2 | **PASS** 10/10 (เชิงพฤติกรรม) |
| G3 | **`G3_API_ENFORCEMENT_PENDING_B1`** — 5 ผ่าน 2 ค้าง 0 ไม่ผ่าน |
| mutation testing | 5 การทำลายถูกจับได้ · คืนสภาพแล้วกลับเป็น 0 |
| commit / push | **ยังไม่ทำ** รอ review diff และผลทดสอบก่อน |

**ไม่ใช่ `READY_FOR_PRODUCTION`** · **ยังไม่ apply Migration 005** · **ยังไม่ทำ data migration**

---

## STOP

**รอ review diff และผลทดสอบก่อน commit**

เรื่องที่รออนุมัติ

1. **อนุมัติ commit** `eval/web_schema_check.py` (`+255 −1`) หรือไม่
2. **N2** — `ai_settings.updated_by` ใช้หลัก NULL เดียวกันไหม
3. **เริ่ม B1 เฟส 1** — ต้องได้รับอนุมัติเขียนรีโปหน้าเว็บก่อน · G3 สองข้อที่ค้าง
   จะปิดได้ในรอบนั้น
4. **B3** (PDF กำพร้า) และ **B4** (PII ใน `detail`)
5. **U3** — ตรวจ `cron.job_run_details` ก่อนวางแผน cutover

```
Migration 005 แก้         NONE        Production Write      NONE
Production code แก้        NONE        Apply Migration 005   NONE
Data Migration            NONE        Supabase Write        NONE
Deploy / Restart          NONE        Re-embed              NONE
Commit / Push             NONE        Merge main            NONE
```
