# B2 — Legacy Author Resolution + Migration 005 Readiness Review

| | |
|---|---|
| วันที่ | 2026-10-02 |
| ขอบเขต | **READ / REVIEW / DOCUMENTATION ONLY** |
| **B2 status** | **`RESOLVED_WITH_NULL_LEGACY_AUTHOR`** |
| Migration 005 | **รองรับอยู่แล้ว ไม่ต้องแก้** |
| ไฟล์ที่แก้ในรอบนี้ | **เอกสาร 1 ไฟล์** (`AUTHORIZATION_USER_MAPPING_DESIGN.md` §6.4) · **ไม่แตะ SQL หรือโค้ด** |

```
Production Write  NONE   INSERT/UPDATE/DELETE  NONE   DDL              NONE
Apply Migration   NONE   Data Migration        NONE   Create User      NONE
Supabase Write    NONE   Deploy / Restart      NONE   Docker recreate  NONE
Re-embed          NONE   Commit / Push         NONE   Merge main       NONE
```

**รอบนี้ไม่ได้รันอะไรเลย** — ไม่ได้สร้างคอนเทนเนอร์ทดสอบ ไม่ได้ลง migration ที่ใด
ไม่ได้ต่อ production ทั้งหมดเป็นการอ่านไฟล์ในรีโปและอ้างผลที่ยืนยันไว้แล้วในรอบก่อน

---

## 1. Owner decision

สำหรับข้อมูล legacy ที่จะย้ายจาก Supabase (`public.courses` · `public.news`)

```
Legacy created_by = NULL
Legacy updated_by = NULL
```

เมื่อ map ผู้เขียนเดิมฝั่ง Supabase ไปยัง `public.users` ฝั่ง production แบบ
deterministic ไม่ได้

**เหตุผลที่เจ้าของให้ไว้**

| | |
|---|---|
| 1 | Supabase `courses`/`news` historical author เป็น **account เดียวกัน** |
| 2 | แต่ historical author **ไม่ใช่** บัญชี Supabase ของเจ้าของโปรเจกต์ |
| 3 | hash ของอีเมล historical author **ไม่มี match** ใน production `public.users` |
| 4 | ห้ามสร้าง fake user |
| 5 | ห้ามเอา existing admin มาเป็น fallback |
| 6 | ห้ามเปลี่ยน historical `created_by` ใน Supabase |

**ข้อมูลใหม่หลัง cutover**: ให้ API กำหนด `created_by` / `updated_by` จาก
authenticated production user ตาม B1 authorization design

---

## 2. Evidence summary

ต้องแยกให้ชัดว่าอะไรเป็นหลักฐานที่ผมตรวจเอง และอะไรเป็นผลที่เจ้าของแจ้งมา

### 2.1 ผลที่เจ้าของแจ้ง — **OWNER-SUPPLIED · ผมไม่ได้ตรวจเอง**

| ข้อ | สถานะ |
|---|---|
| `courses`/`news` historical author เป็นบัญชีเดียวกัน | **OWNER-SUPPLIED** — session นี้ไม่มี Supabase MCP (ดู `B2_USER_MAPPING_VERIFICATION.md` ข้อ 1) · ผมรายงานไว้เองว่าข้อนี้ **ยังไม่เคยถูกตอบ** จากหลักฐานเดิม (ข้อ 2 ของไฟล์นั้น) · **เจ้าของตอบแล้ว: เป็นบัญชีเดียวกัน** |
| historical author ≠ บัญชีเจ้าของโปรเจกต์ | **OWNER-SUPPLIED** |
| email hash ไม่ match ใน `public.users` | **OWNER-SUPPLIED** — ตรงกับผลที่เป็นไปได้ "0 แถว" ที่ผมเตรียมทางเลือกไว้แล้ว |

ผมบันทึกสามข้อนี้ตามที่แจ้ง **ไม่ได้อ้างว่าตรวจเอง** และไม่มีข้อสรุปใดในเอกสารนี้
ที่พังถ้าสามข้อนี้ผิด — เพราะทางที่เลือก (NULL) ปลอดภัยทั้งกรณี 1 บัญชีและ 2 บัญชี

### 2.2 ผลที่ผมตรวจเอง — **VERIFIED**

| ข้อ | ที่มา |
|---|---|
| ทั้ง 4 คอลัมน์ผู้เขียนใน 005 เป็น nullable | อ่าน `db/migrations/005_web_schema.sql` โดยตรง (ข้อ 3) |
| FK ทั้ง 8 เส้นตั้ง `ON DELETE SET NULL` | catalog-level ในการรันรอบก่อน (`confdeltype = 'n'` ทุกเส้น) |
| **ไม่มี `DEFAULT` บน `created_by`** ใน 005 | `grep -c 'created_by.*DEFAULT'` = **0** |
| `public.users.id` เป็น PK | `db/schema.sql` |
| `public.users` มี 198 แถว · `is_admin` = 1 | `SELECT` อ่านอย่างเดียวในรอบก่อน |
| `web` schema บน production ยังไม่มี | `SELECT count(*) FROM pg_namespace` = 0 ในรอบก่อน |
| 198 แถว → 198 hash ไม่ซ้ำ | รอบก่อน — ผลเทียบเป็นได้แค่ 0 หรือ 1 |
| **2 แถวเก็บอีเมลด้วยตัวพิมพ์ใหญ่** | รอบก่อน — ทำให้ `lower()` จำเป็นจริง |

ข้อสุดท้ายยังสำคัญกับการตัดสินใจนี้: ถ้าฝั่ง Supabase hash โดยไม่ `lower()`
ผลจะออกมาเป็น "0 แถว" **ทั้งที่อาจมี match อยู่จริง** → ก่อนปิดเคสถาวร ควรยืนยัน
ว่า query ที่เจ้าของรันใช้ `lower(trim(email))` ตามที่กำหนด (ดูข้อ 9 · N1)

---

## 3. Migration 005 nullable / FK verification

### 3.1 ผลตรวจทั้ง 4 คอลัมน์ที่สั่ง

> หมายเหตุชื่อตาราง: 005 ไม่มีตารางชื่อ `courses` หรือ `news` ตรง ๆ
> ปลายทางของ `public.courses` คือ **`web.site_courses`** และของ `public.news` คือ **`web.news`**
> `public.courses` ที่มีอยู่แล้วฝั่งเราเป็นข้อเท็จจริงของหลักสูตรจากเอกสาร มคอ. คนละเรื่องกัน

| # | ที่สั่งให้ตรวจ | คอลัมน์จริงใน 005 | nullable | FK | ON DELETE | ตรงเป้าหมาย |
|---|---|---|---|---|---|---|
| 1 | `courses.created_by` | `web.site_courses.created_by` (บรรทัด 136) | **ใช่** | `public.users(id)` | **SET NULL** | ✓ |
| 2 | `courses.updated_by` | `web.site_courses.updated_by` (บรรทัด 137) | **ใช่** | `public.users(id)` | **SET NULL** | ✓ |
| 3 | `news.created_by` | `web.news.created_by` (บรรทัด 207) | **ใช่** | `public.users(id)` | **SET NULL** | ✓ |
| 4 | `news.updated_by` | `web.news.updated_by` (บรรทัด 208) | **ใช่** | `public.users(id)` | **SET NULL** | ✓ |

### 3.2 นิยามจริงจากไฟล์

```sql
-- web.site_courses
created_by    UUID REFERENCES public.users(id) ON DELETE SET NULL,
updated_by    UUID REFERENCES public.users(id) ON DELETE SET NULL,

-- web.news
created_by    UUID REFERENCES public.users(id) ON DELETE SET NULL,
updated_by    UUID REFERENCES public.users(id) ON DELETE SET NULL,
```

ทั้งสี่บรรทัด **ไม่มี `NOT NULL`** และ **ไม่มี `DEFAULT`**

### 3.3 สามอย่างที่ตรงกับเป้าหมายพอดี

| เป้าหมายที่สั่ง | ของจริง |
|---|---|
| `created_by UUID NULL` | ✓ — ไม่มี `NOT NULL` |
| `updated_by UUID NULL` | ✓ |
| FK → `ON DELETE SET NULL` | ✓ — ทั้ง 8 FK ในทั้ง schema `web` ไม่ใช่แค่ 4 คอลัมน์นี้ |

**และข้อที่สำคัญกว่าที่สั่งมา: ไม่มี `DEFAULT`**

ต้นทาง Supabase ตั้ง `courses.created_by DEFAULT auth.uid()` — ถ้า 005 มี `DEFAULT`
ทำนองเดียวกัน การ `INSERT` ที่ละคอลัมน์นี้จะได้ค่า "ใครก็ตามที่กำลังรันคำสั่งนำเข้า"
ยัดเข้ามาเงียบ ๆ ซึ่งคือ **การยัดเจ้าของผิดคน** ที่เจ้าของสั่งห้ามโดยตรง

`grep -c 'created_by.*DEFAULT' db/migrations/005_web_schema.sql` = **0**
→ การละคอลัมน์ตอน INSERT ให้ผลเป็น **NULL** ไม่ใช่ค่าแทน

### 3.4 ที่ 005 เขียนกำกับไว้เองตั้งแต่ต้น

```
-- ทำไม created_by / updated_by เป็น NULL ได้
-- ------------------------------------------
-- ของเดิมอ้างถึงผู้ใช้ในระบบ auth ของหน้าเว็บ ซึ่งเป็นคนละชุดกับ public.users
-- (ยืนยันแล้วว่าไม่มีเส้นเชื่อมกันเลย) ตอนนำข้อมูลเข้าจึงจะมีบางแถวที่หาเจ้าของ
-- ไม่เจอ ปล่อยให้เป็น NULL ได้ดีกว่าทิ้งแถวนั้นหรือยัดเจ้าของผิดคน
-- และ ON DELETE SET NULL เพราะการลบบัญชีผู้ใช้ไม่ควรลบข่าวที่เขาเคยเขียน
```

**การตัดสินใจของเจ้าของตรงกับเจตนาที่เขียนไว้ในไฟล์แล้ว** ไม่ใช่การดัดการออกแบบ
ให้เข้ากับผลที่เพิ่งพบ — ข้อ "ปล่อยให้เป็น NULL ได้ดีกว่าทิ้งแถวนั้นหรือยัดเจ้าของผิดคน"
คือเหตุผลเดียวกับที่เจ้าของให้มา

### 3.5 ที่ยืนยันแล้วในการรันรอบก่อน (ไม่ได้รันซ้ำรอบนี้)

```
ชุด eval/web_schema_check.py  76 ผ่าน · 0 ไม่ผ่าน   (PostgreSQL 16.15 ในคอนเทนเนอร์แยก)

ข้อที่เกี่ยวข้องโดยตรง:
  foreign key ครบ 8 เส้น
  ทุก FK ตั้ง ON DELETE SET NULL (ลบผู้ใช้แล้วเนื้อหาต้องไม่หาย)   <- confdeltype = 'n' ทุกเส้น
  news: created_by เป็น NULL ได้ (ผู้เขียนเดิมแมปไม่ได้)
  news: created_by ที่ไม่มีอยู่จริงถูกปฏิเสธ
```

ข้อ `confdeltype = 'n'` อ่านจาก `pg_constraint` ของ PostgreSQL จริง
จึงเป็นการยืนยันระดับ catalog ไม่ใช่การอ่าน DDL ในไฟล์

**ช่องว่างของชุดตรวจที่พบ — ดูข้อ 9 · G1 และ G2**

---

## 4. `courses` author field compatibility

ปลายทาง **`web.site_courses`**

| ต้นทาง `public.courses` | ปลายทาง `web.site_courses` | legacy import | หลัง cutover |
|---|---|---|---|
| `created_by` `uuid` → **`auth.users(id)`** DEFAULT `auth.uid()` · ไม่ NULL **12/12** | `created_by` `uuid` nullable → `public.users(id)` SET NULL · **ไม่มี DEFAULT** | **NULL ทั้ง 12 แถว** | id ของผู้ใช้ที่ยืนยันตัวตนแล้ว |
| `updated_by` `uuid` → **`user_profiles(user_id)`** ON DELETE SET NULL · ไม่ NULL **12/12** | `updated_by` `uuid` nullable → `public.users(id)` SET NULL | **NULL ทั้ง 12 แถว** | id ของผู้ใช้ที่ยืนยันตัวตนแล้ว |

**COMPATIBLE** — ไม่ต้องแก้ schema

ข้อสังเกตที่ควรบันทึก: ต้นทาง `created_by` กับ `updated_by` ชี้ **ตารางต่างกัน**
(`auth.users` กับ `user_profiles`) ปลายทางยุบเป็นตารางเดียว (`public.users`)
เมื่อทั้งคู่เป็น NULL ความต่างนี้ไม่มีผลในรอบนี้ แต่ต้องรู้ไว้ถ้าภายหลัง
มีการย้อนมาเติมค่า — ค่าที่เคยอยู่ในสองคอลัมน์นั้นมาจากคนละ domain ของ id

## 5. `news` author field compatibility

ปลายทาง **`web.news`**

| ต้นทาง `public.news` | ปลายทาง `web.news` | legacy import | หลัง cutover |
|---|---|---|---|
| `created_by` `uuid` → `auth.users(id)` DEFAULT `auth.uid()` · ไม่ NULL **3/3** | `created_by` `uuid` nullable → `public.users(id)` SET NULL · **ไม่มี DEFAULT** | **NULL ทั้ง 3 แถว** | id ของผู้ใช้ที่ยืนยันตัวตนแล้ว |
| `updated_by` `uuid` → `user_profiles(user_id)` ON DELETE SET NULL · ไม่ NULL **3/3** | `updated_by` `uuid` nullable → `public.users(id)` SET NULL | **NULL ทั้ง 3 แถว** | id ของผู้ใช้ที่ยืนยันตัวตนแล้ว |

**COMPATIBLE** — ไม่ต้องแก้ schema

**รวมแถวที่จะมี author เป็น NULL หลัง legacy import = 15** (12 courses + 3 news)
จำนวนนี้ไม่เปลี่ยนไม่ว่า historical author จะเป็น 1 หรือ 2 บัญชี

---

## 6. Legacy migration semantics

### 6.1 ความหมายของ NULL — ต้องไม่อ่านผิด

```
NULL ในคอลัมน์ created_by / updated_by ของแถว legacy หมายถึง

        "legacy author identity not mapped"
        ตัวตนของผู้เขียนเดิม ยังจับคู่กับผู้ใช้ในระบบปลายทางไม่ได้

ไม่ใช่

        "ไม่มีผู้สร้างข้อมูล"
```

ข้อเท็จจริงที่รองรับ: ต้นทางมี `created_by` และ `updated_by` **ครบทุกแถว**
(courses 12/12 · news 3/3 · ไม่ NULL เลย · ไม่มี FK กำพร้า)
→ **ผู้สร้างมีอยู่จริงและยังมีอยู่ใน Supabase** ข้อมูลเดิมไม่ได้ถูกลบหรือแก้

NULL ที่ปลายทางจึงเป็นการ **เก็บความไม่แน่นอนไว้อย่างซื่อสัตย์** ไม่ใช่การลบข้อมูล

### 6.2 สิ่งที่ต้อง preserve — ชัดเจนว่าอะไรเปลี่ยนและอะไรไม่

| กลุ่ม | ปฏิบัติ |
|---|---|
| **author fields** | `created_by` = NULL · `updated_by` = NULL — **เฉพาะ legacy `courses`/`news` เท่านั้น** |
| `id` | ปลายทางสร้างใหม่ (`gen_random_uuid()`) · uuid สองฝั่งไม่เกี่ยวกัน · ตาม mapping strategy ใน `MIGRATION_005_FINAL_REVIEW.md` ข้อ 6 |
| `site_courses.course_id` | ตั้งเฉพาะคู่ที่ `MATCHED` กับ `public.courses` · `AMBIGUOUS` / `UNMATCHED` = NULL |
| title / content / description / category | **คงค่าเดิมทุกตัวอักษร** |
| `status` | **คงค่าเดิม** — ค่าจริงทั้ง 3 แถวเป็น `published` ผ่าน CHECK ของ 005 |
| timestamps (`created_at` · `updated_at`) | **คงค่าเดิม** — เป็นไปได้เพราะ trigger เป็น `BEFORE UPDATE` อย่างเดียว (`tgtype = 19` ไม่มีบิต INSERT) |
| source fields | `logo` → `logo_url` · `date` → `published_on` · `image` → `image_url` — เปลี่ยนชื่อคอลัมน์ ไม่เปลี่ยนค่า |
| programme fields | `title` · `title_en` · `description` · `careers` · `detail` — คงค่าเดิม · **`detail` ที่เป็น NULL ต้องคง NULL ห้าม `COALESCE`** |
| `is_published` | คอลัมน์ใหม่ที่ไม่มีต้นทาง → ใช้ `DEFAULT TRUE` (ตรงกับที่ RLS ต้นทางเปิดอ่าน `courses` ไร้เงื่อนไข) |
| **ฝั่ง Supabase** | **อ่านอย่างเดียว ห้ามเขียนอะไรเลย** — ห้าม `UPDATE created_by` / `updated_by` |

### 6.3 ตารางที่ไม่อยู่ในขอบเขตการตัดสินใจนี้

การตั้ง NULL ใช้กับ **legacy `courses` และ `news` เท่านั้น** ไม่ขยายไปที่อื่น

| ตาราง | author fields | สถานะ |
|---|---|---|
| `web.knowledge_articles` | มี `created_by`/`updated_by` nullable เหมือนกัน | **ต้นทางมี 0 แถว** → ไม่มีอะไรจะนำเข้า ไม่ต้องตัดสินใจ |
| `web.ai_settings` | มี `updated_by` nullable | ต้นทาง 1 แถวที่ `updated_by` ไม่ NULL — **ยังไม่อยู่ในขอบเขตคำสั่งนี้** ดูข้อ 9 · N2 |
| `web.external_news` | **ไม่มีคอลัมน์ author เลย** | ไม่เกี่ยว |

---

## 7. Post-cutover author semantics

### 7.1 พฤติกรรมที่กำหนด

| การกระทำ | `created_by` | `updated_by` |
|---|---|---|
| **CREATE** | id ของผู้ใช้ที่ยืนยันตัวตนแล้ว | id ของผู้ใช้ที่ยืนยันตัวตนแล้ว |
| **UPDATE** | **ห้ามแตะเลย** — คงค่าเดิมไว้ไม่ว่าจะเป็นค่าใดหรือเป็น NULL | id ของผู้ใช้ที่ยืนยันตัวตนแล้ว |
| **ที่มาของค่า** | token เท่านั้น | token เท่านั้น |
| ค่าจาก request body | **ไม่เชื่อ ทิ้งทันที** | **ไม่เชื่อ ทิ้งทันที** |

### 7.2 ทำไม UPDATE ต้องไม่แตะ `created_by` — สำคัญเป็นพิเศษกับการตัดสินใจนี้

ถ้า UPDATE ตั้ง `created_by` จาก token (แม้จะเป็น token จริง ไม่ใช่ค่าปลอมจาก body)
แถว legacy ที่ `created_by` เป็น NULL จะถูกเขียนเป็น id ของ **คนแรกที่บังเอิญมาแก้ไข**

ความหมายของ NULL จะเปลี่ยนจาก

```
"ยังแมปผู้เขียนเดิมไม่ได้"      ->      "คนที่เพิ่งมาแก้ไข เป็นคนสร้าง"
```

ซึ่ง **ไม่จริง** และเป็นการ "ยัดเจ้าของผิดคน" แบบเดียวกับที่เจ้าของสั่งห้ามไว้
เพียงแต่เกิดภายหลังผ่านการใช้งานปกติ ไม่ใช่ตอน migration

→ **ข้อนี้เพิ่งถูกเขียนให้ชัดใน `AUTHORIZATION_USER_MAPPING_DESIGN.md` §6.4 ข้อ 1b**
(ดูข้อ 8.2) เดิมเอกสารเขียนแค่ "ตั้ง `updated_by` จาก token" ซึ่งสื่อเป็นนัยว่า
ไม่แตะ `created_by` แต่ไม่ได้ห้ามไว้ตรง ๆ

### 7.3 แยกแถว legacy กับแถวใหม่ออกจากกันได้ไหม

**ไม่มีอะไรในข้อมูลบอกว่าแถวไหนเป็น legacy** — schema ไม่มีคอลัมน์ที่ระบุ

หลัง cutover API จะตั้ง author ให้ทุกแถวใหม่เสมอ ดังนั้น `created_by IS NULL`
จะหมายถึงอย่างใดอย่างหนึ่ง

```
(ก) แถว legacy 15 แถวที่นำเข้าตอน cutover        <- ตั้งใจ
(ข) ข้อบกพร่องของ API ที่ลืมตั้ง author            <- ไม่ตั้งใจ
```

แยกได้ด้วย `created_at` เทียบกับเวลา cutover **แต่เปราะ** เพราะ `created_at`
ของแถว legacy เป็นเวลาเดิมจากต้นทาง (ปี 2026-08-25 สำหรับ news)
ซึ่งอาจซ้อนกับช่วงเวลาอื่นได้ และถ้ามีการย้ายข้อมูลซ้ำภายหลังจะยิ่งแยกยาก

**ไม่เป็น blocker** — การตัดสินใจของเจ้าของทำงานได้กับ schema ปัจจุบัน
แต่เป็นข้อจำกัดที่ควรรู้ ดูทางเลือกในข้อ 9 · N3

---

## 8. B1 authorization compatibility

### 8.1 ตรวจเทียบกับที่ Phase 3 สั่ง

| Phase 3 สั่ง | B1 design เดิม | ผล |
|---|---|---|
| CREATE: `created_by` = authenticated user id | §6.2 `POST /api/courses` → *"ตั้ง `created_by` จาก token ห้ามรับจาก body"* | **ตรง** |
| CREATE: `updated_by` = authenticated user id | ไม่ได้ระบุชัด | **เพิ่มให้ชัดแล้ว** — §6.4 ข้อ 1a |
| UPDATE: `created_by` ต้องไม่เปลี่ยนจาก client input | §6.2 `PATCH` → *"ตั้ง `updated_by` จาก token"* (สื่อเป็นนัยว่าไม่แตะ `created_by` แต่ไม่ได้ห้ามตรง ๆ) | **เพิ่มให้ชัดแล้ว** — §6.4 ข้อ 1b · **ห้ามแตะ `created_by` เลยแม้จะตั้งจาก token** ซึ่งเข้มกว่าที่สั่ง |
| UPDATE: `updated_by` = authenticated user id | §6.2 ระบุไว้แล้ว | **ตรง** |
| ห้าม trust `created_by`/`updated_by` จาก body | §6.4 ข้อ 1 + ความเสี่ยง **R7** (ระดับสูง) — วันนี้ SPA ส่ง `updated_by: user?.id` มาเอง (`KnowledgeForm.jsx:138`) | **ตรง** |
| DELETE: คงตาม B1 เดิม ห้ามขยายสิทธิ์ | §6.2 `DELETE` = **ADMIN เท่านั้น** ตาม RLS ต้นทาง | **ตรง ไม่ขยาย** |

### 8.2 เอกสารที่แก้ในรอบนี้ — ไฟล์เดียว บรรทัดเดียวเพิ่มสองข้อ

`docs/AUTHORIZATION_USER_MAPPING_DESIGN.md` §6.4 เพิ่มกฎ **1a** และ **1b**

```
1a. CREATE  ตั้งทั้ง created_by และ updated_by = id ของผู้เรียกที่ยืนยันตัวตนแล้ว
1b. UPDATE  ตั้ง updated_by เท่านั้น  ห้ามแตะ created_by เลยแม้แต่จะตั้งจาก token
```

พร้อมเหตุผลว่าทำไมสำคัญกับแถว legacy ที่ `created_by` เป็น NULL

**ไม่ได้แก้ SQL ไม่ได้แก้โค้ด** — เป็นการอัปเดต documentation ตามที่คำสั่งอนุญาต

### 8.3 ผลที่ตามมาจาก Owner decision ข้อ 2 — DELETE ยังใช้ไม่ได้

เจ้าของตัดสินแล้วว่า **ยังไม่เพิ่ม DELETE privilege ใน PostgreSQL รอบนี้**
และ 005 **ไม่ให้ `DELETE` แก่ role ใดเลย**

| | |
|---|---|
| ผล | endpoint `DELETE` ที่ออกแบบไว้ 4 เส้นทาง **ยังทำงานไม่ได้** แม้ตรวจสิทธิ์ ADMIN ผ่าน |
| อาการที่จะเกิด | `advisor_api` จะได้ error ระดับฐานข้อมูล (`permission denied for table`) ไม่ใช่ 403 ที่สื่อความหมาย |
| ปุ่มลบในหน้าผู้ดูแลที่กระทบ | 5 ที่ (`courses` · `knowledge_articles` · `rag_documents` ×3) |
| **ข้อเสนอ** | **ยังไม่สร้าง endpoint `DELETE` ในเฟส 1** แล้วให้ปุ่มลบเรียก Supabase ตามเดิมจนกว่าจะตัดสินเรื่องสิทธิ์ · ถ้าสร้าง ต้องคืน **501** พร้อมข้อความชัด ไม่ใช่ปล่อยให้ error ของฐานข้อมูลหลุดออกไป |
| **ห้าม** | เพิ่ม `GRANT DELETE` เอง — เป็นการขยายสิทธิ์ที่เจ้าของสั่งห้ามในรอบนี้ |

ยังเป็นความเสี่ยง **R4** ใน design doc ตามเดิม ไม่ได้ลดระดับลง

---

## 9. Remaining blockers

### 9.1 Blocker ที่เหลือจริงก่อน Data Migration

| # | Blocker | ระดับ | สถานะ |
|---|---|---|---|
| ~~B2~~ | ~~จับคู่ผู้เขียน~~ | — | **ปิดแล้วด้วยการตัดสินใจของเจ้าของ** (ข้อ 10) |
| **B1** | Authorization ชั้น API ยังไม่ได้เขียน | **สูงสุด** | design พร้อม (`AUTHORIZATION_USER_MAPPING_DESIGN.md`) · **ยังไม่ลงมือ** · ครึ่งหนึ่งของงานอยู่ในรีโปหน้าเว็บที่ยังไม่ได้รับอนุมัติให้เขียน |
| **B3** | PDF กำพร้า 4 ไฟล์ 10.4 MiB | กลาง | ยังต้องตัดสิน · **ห้ามลบ** |
| **B4** | PII ใน `courses.detail` (`faculty[].email`) · รีโปหน้าเว็บเป็น public | กลาง | ยังต้องตัดสิน |
| **U3** | ตัวดึงข่าวค้าง 10 วัน (`max(synced_at)` = 2026-09-22 ขณะที่ cron `*/30` เปิดอยู่) | กลาง | ควรตรวจก่อนวางแผน cutover ของ `external_news` |

**B2 ไม่ใช่ blocker อีกต่อไป** และ **ไม่ต้องแก้ Migration 005**

### 9.2 ช่องว่างของชุดตรวจ — ต้องแก้ในรอบถัดไป ไม่ใช่รอบนี้

ตามคำสั่ง *"ถ้าพบว่าต้องแก้ code/schema/migration: STOP และรายงานสิ่งที่ต้องแก้ก่อน"*

| # | ช่องว่าง | ทำไมสำคัญ |
|---|---|---|
| **G1** | ชุดตรวจมีข้อ `news.created_by` เป็น NULL ได้ **แต่ไม่มี** ข้อสำหรับ `site_courses.created_by` · `site_courses.updated_by` · `news.updated_by` | การตัดสินใจนี้ทำให้ NULL เป็น **สภาพปกติของ 15 แถว** คอลัมน์ที่ไม่มีข้อตรวจคุ้มอยู่ 3 ใน 4 คอลัมน์ ถ้าใครเพิ่ม `NOT NULL` ในอนาคตจะไม่มีอะไรฟ้อง |
| **G2** | `ON DELETE SET NULL` ตรวจที่ระดับ catalog (`confdeltype = 'n'`) **แต่ไม่ได้พิสูจน์เชิงพฤติกรรม** — ยังไม่มีข้อที่ลบผู้ใช้จริงแล้วยืนยันว่า author กลายเป็น NULL และ **แถวเนื้อหายังอยู่** | เป็นด่านที่กันไม่ให้การลบบัญชีลบเนื้อหาทิ้ง · การอ่านประกาศไม่เท่ากับการพิสูจน์ผล — บทเรียนเดิมของโปรเจกต์นี้ |
| **G3** | ยังไม่มีข้อตรวจว่า **UPDATE ไม่แตะ `created_by`** | เป็นกฎใหม่ (§6.4 ข้อ 1b) ที่ยังไม่มีอะไรบังคับ · ถ้าพลาด ความหมายของ NULL จะเปลี่ยนเงียบ ๆ ตามข้อ 7.2 |

**ไม่ได้แก้ในรอบนี้** — ทั้งสามข้อเป็นการเพิ่มข้อตรวจใน `eval/web_schema_check.py`
ซึ่งเป็นโค้ด ขออนุมัติทำในรอบถัดไป

### 9.3 ข้อที่ควรยืนยันแต่ไม่บล็อก

| # | | |
|---|---|---|
| **N1** | query ที่เจ้าของรันฝั่ง Supabase ใช้ `lower(trim(email))` ใช่ไหม | ฝั่งเรามี **2 แถวที่เก็บอีเมลด้วยตัวพิมพ์ใหญ่** (เพราะ `citext`) ถ้าฝั่งนั้น hash อีเมลดิบ ผลจะเป็น "0 แถว" **ทั้งที่อาจมี match จริง** · ไม่บล็อกเพราะทางที่เลือก (NULL) ปลอดภัยทั้งสองกรณี แต่ควรรู้ว่าปิดเคสด้วยหลักฐานที่ถูกหรือไม่ |
| **N2** | `ai_settings.updated_by` จะทำอย่างไร | ต้นทาง 1 แถวที่ `updated_by` **ไม่ NULL** · คำสั่งรอบนี้ครอบคลุมแค่ `courses`/`news` · ถ้าใช้หลักเดียวกันก็เป็น NULL แต่ **ยังไม่ได้รับคำสั่งให้ตัดสิน** |
| **N3** | จะแยกแถว legacy ออกจากแถวใหม่ไหม | ข้อ 7.3 — วันนี้แยกไม่ได้จากข้อมูล · ทางเลือก: (ก) ยอมรับ (ข) เพิ่มคอลัมน์ marker ใน migration 006 (ค) เก็บ uuid เดิมของ Supabase ไว้ · **ทั้งหมดต้องขออนุมัติแยกและเป็น migration ใหม่ ไม่ใช่การแก้ 005** |

---

## 10. Final B2 status

# `RESOLVED_WITH_NULL_LEGACY_AUTHOR`

> **Historical Supabase author could not be deterministically mapped to an existing
> production PostgreSQL user. The project owner explicitly chose to preserve this
> uncertainty by storing legacy `created_by`/`updated_by` as NULL rather than
> fabricating or substituting an identity.**

### 10.1 เงื่อนไขที่ทำให้สถานะนี้ใช้ได้ — ครบทั้งสองข้อ

| เงื่อนไขที่คำสั่งกำหนด | ผล |
|---|---|
| Migration 005 รองรับ nullable author FK อยู่แล้ว | **ใช่** — ทั้ง 4 คอลัมน์ nullable · FK → `public.users(id)` · `ON DELETE SET NULL` · **ไม่มี DEFAULT** (ข้อ 3) |
| ไม่มี blocker อื่นที่เกี่ยวกับเรื่องนี้ | **ใช่** — blocker ที่เหลือ (B1 · B3 · B4 · U3) ไม่เกี่ยวกับ author mapping · **ไม่ต้องแก้ schema** |

→ **ไม่ใช่ `BLOCKED_SCHEMA_CHANGE_REQUIRED`**

### 10.2 ไม่เรียกว่า mapping success

| | |
|---|---|
| สิ่งที่เกิดขึ้น | **เลือกเก็บความไม่แน่นอนไว้อย่างซื่อสัตย์** |
| สิ่งที่ไม่ได้เกิดขึ้น | การจับคู่ผู้ใช้สำเร็จ |
| ตัวตนผู้เขียนเดิมหายไปไหม | **ไม่หาย** — ยังอยู่ครบใน Supabase (`created_by` ไม่ NULL 15/15) ไม่ได้ถูกลบหรือแก้ |
| ย้อนกลับมาเติมได้ไหม | **ได้** — ถ้าภายหลังมีหลักฐานที่จับคู่ได้ ก็ `UPDATE` ค่าเข้าไปได้ เพราะคอลัมน์เป็น nullable ไม่ได้ถูกบังคับให้ว่างตลอดไป |

### 10.3 สิ่งที่ยืนยันว่าไม่ได้ทำ

```
ไม่ได้ map ไปบัญชีเจ้าของโปรเจกต์โดยเดา        ไม่ได้ map ไป admin ที่มีอยู่
ไม่ได้สร้าง placeholder / fake user            ไม่ได้ UPDATE created_by ใน Supabase
ไม่ได้ UPDATE updated_by ใน Supabase           ไม่ได้แก้ Migration 005
```

---

## 11. Recommended next step

```
1. ปิดช่องว่างของชุดตรวจ G1 · G2 · G3   (ขออนุมัติแก้ eval/web_schema_check.py)
   ทำก่อน data migration เพราะเป็นด่านที่กันการตัดสินใจนี้ให้คงอยู่
   G2 สำคัญที่สุด — พิสูจน์ว่าลบผู้ใช้แล้วเนื้อหาไม่หาย ไม่ใช่แค่อ่านประกาศ

2. ยืนยัน N1   query ฝั่ง Supabase ใช้ lower(trim(email)) ใช่ไหม
   ถ้าไม่ใช่ ให้รันซ้ำก่อนปิดเคสถาวร (ไม่กระทบการตัดสินใจ แต่กระทบความถูกของหลักฐาน)

3. ตัดสิน N2   ai_settings.updated_by จะใช้หลักเดียวกันไหม

4. เริ่ม B1 เฟส 1   ต้องได้รับอนุมัติเขียนรีโปหน้าเว็บก่อน (Owner decision ข้อ 5)
   ลำดับที่เสนอไว้: โครงสร้างด่าน -> knowledge_articles (0 แถว) -> news -> courses

5. ตัดสิน B3 (PDF กำพร้า) และ B4 (PII ใน detail)

6. ตรวจ U3 ก่อนวางแผน cutover ของ external_news

7. ขออนุมัติแยกสำหรับ apply Migration 005 บน production
8. ขออนุมัติแยกสำหรับ data migration ทีละตาราง
```

**ลำดับ 1 ควรมาก่อน 7 และ 8** — ถ้า apply migration แล้วย้ายข้อมูลโดยที่ยังไม่มี
ข้อตรวจคุ้ม G1/G2/G3 การตัดสินใจเรื่อง NULL นี้จะไม่มีอะไรรักษาไว้
และข้อผิดพลาดจะไปปรากฏในข้อมูลจริงแทนที่จะปรากฏในชุดทดสอบ

---

## STOP

**B2 = `RESOLVED_WITH_NULL_LEGACY_AUTHOR` · Migration 005 ไม่ต้องแก้**

```
Production Write  NONE   INSERT/UPDATE/DELETE  NONE   DDL              NONE
Apply Migration   NONE   Data Migration        NONE   Create User      NONE
Supabase Write    NONE   Deploy / Restart      NONE   Docker recreate  NONE
Re-embed          NONE   Commit / Push         NONE   Merge main       NONE
```

**แม้ B2 ปิดแล้ว ยังไม่ apply Migration 005 และยังไม่ทำ data migration — รออนุมัติรอบใหม่**

เรื่องที่รออนุมัติ

1. **แก้ `eval/web_schema_check.py`** เพิ่มข้อตรวจ G1 · G2 · G3 (ข้อ 9.2)
2. **N1** — ยืนยันว่า query ฝั่ง Supabase ใช้ `lower(trim(email))`
3. **N2** — `ai_settings.updated_by` ใช้หลักเดียวกันไหม
4. **N3** — จะแยกแถว legacy ออกจากแถวใหม่ไหม (ต้องเป็น migration 006 ไม่ใช่แก้ 005)
5. **DELETE endpoint** — ยังไม่สร้างในเฟส 1 หรือสร้างแล้วคืน 501 (ข้อ 8.3)
