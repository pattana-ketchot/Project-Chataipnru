# B1 — Active User Mapping · Final Design Decision

| | |
|---|---|
| วันที่ | 2026-10-03 (บันทึกการตัดสินใจของเจ้าของแล้ว) |
| ขอบเขต | **DESIGN / REVIEW / DOCUMENTATION ONLY** |
| **การตัดสินใจของเจ้าของ** | **ทางเลือก A** — ต่อจากนี้ใช้ **S1 บัญชีเดียว** เพิ่ม/แก้ Courses และ News · **ไม่ provision ผู้ใช้ให้ S2** |
| M1 · M2 · N1 | **RESOLVED ทั้งสามข้อ** |
| **S1** (`admin`/`approved`) | **`EXACT_MATCH`** — production match = **1** · แถวนั้นเป็น admin และ active |
| **S2** (`admin`/`approved` · ผู้เขียนเดิม) | **`NO_MATCH`** — production match = **0** |
| ambiguity | **เป็นไปไม่ได้** — ยืนยันทั้งสองฝั่ง |
| **M4** | **`M4_RESOLVED_DESIGN_READY`** ✅ (เดิม `M4_ACTIVE_USER_PROVISIONING_REQUIRED`) |
| **B1_ACTIVE_USER_MAPPING_REQUIRED** | **`true`** (ยังไม่ implement) |
| Design ที่เลือก | **Option C** — `public.users.supabase_user_id` |

```
Migration 006        NONE   ALTER public.users   NONE   CREATE mapping table  NONE
สร้าง/แก้ user        NONE   implement mapping    NONE   write endpoints       NONE
Apply Migration 005  NONE   Apply Migration 006  NONE   Data Migration        NONE
Production Write     NONE   Supabase Write       NONE   แก้ frontend          NONE
Deploy / Restart     NONE   Commit / Push        NONE   Merge main            NONE
```

**ไม่มีอีเมล ไม่มี UUID ไม่มี full SHA-256 ไม่มี token ไม่มีคีย์ในเอกสารนี้**
hash แสดงเป็น prefix 12 ตัวเท่านั้น · การตัดสินใช้ full hash **ภายใน SQL**

---

## 1. Verified facts

### 1.1 ฝั่ง Supabase — จาก `B1_SUPABASE_IDENTITY_VERIFICATION.md` (2026-10-03 · live MCP read-only)

| metric | ค่า |
|---|---:|
| `auth_users` | **3** |
| `users_with_email` | **3** |
| `distinct_normalized_email_hash` | **3** |
| `duplicate_normalized_email_hash` | **0** |
| `privileged_accounts` (`role IN ('admin','editor')` AND `status='approved'`) | **2** |

| label | role | status | hash prefix | ผู้เขียนเดิม |
|---|---|---|---|---|
| **S1** | `admin` | `approved` | `66067ef9e155` | ไม่ |
| **S2** | `admin` | `approved` | `716e6e356eae` | **ใช่** |

`courses` distinct `created_by` = 1 · `news` distinct `created_by` = 1 · `same_account` = **true**
→ **เนื้อหาทั้งหมดเขียนโดย S2 บัญชีเดียว** · ไม่มีแถวใดที่ `created_by` เป็น NULL ที่ต้นทาง

**ไม่พบ role `editor` เลย** แม้ policy ครึ่งระบบจะอ้างถึง

### 1.2 ฝั่ง production PostgreSQL — ตรวจเองในรอบนี้ แบบ `SELECT` อย่างเดียว

| metric | ค่า |
|---|---:|
| `users` ทั้งหมด | **198** |
| มีอีเมลครบ | **198** |
| `distinct_normalized_email_hash` | **198** |
| `duplicate_normalized_email_hash` | **0** |
| `is_admin = true` | **1** |
| `is_active = false` | **0** |
| คอลัมน์ external identity | **ไม่มี** |

### 1.3 ผลเทียบข้ามระบบ — **ใหม่ในรอบนี้**

| label | role / status | `postgres_match_count` | match เป็น admin? | match active? | classification |
|---|---|---:|---|---|---|
| **S1** | `admin` / `approved` | **1** | **ใช่** | **ใช่** | **`EXACT_MATCH`** |
| **S2** | `admin` / `approved` | **0** | — | — | **`NO_MATCH`** |

`self_test_pipeline` = **ผ่าน** — hash ของ `'  TeSt '` ตรงกับ SHA-256 ที่รู้ค่าของ `test`
→ **`match_count = 0` ของ S2 ไม่ใช่ผลลบลวงจาก pipeline**

#### คำสั่งที่ใช้ (รันแล้ว · READ-ONLY)

```sql
-- เทียบ full SHA-256 ภายใน SQL · คืนแต่จำนวนกับ boolean
-- ไม่ SELECT email ไม่ SELECT uuid ออกมาเลย
WITH h AS (
  SELECT id, is_admin, is_active,
         encode(digest(lower(btrim(email::text)),'sha256'),'hex') AS full_hash
  FROM public.users
)
SELECT 'S1' AS label, count(*) AS postgres_match_count,
       COALESCE(bool_or(is_admin),false)  AS any_match_is_admin,
       COALESCE(bool_or(is_active),false) AS any_match_is_active
FROM h WHERE full_hash = '<S1 full hash>'
UNION ALL
SELECT 'S2', count(*), COALESCE(bool_or(is_admin),false), COALESCE(bool_or(is_active),false)
FROM h WHERE full_hash = '<S2 full hash>';
```

full hash ของ S1/S2 อ่านจากไฟล์หลักฐานที่มีอยู่ (`B2_AUTHOR_IDENTITY_CROSSCHECK.md`)
**ไม่ได้คำนวณจากอีเมลของใคร** และ **ไม่นำค่าเต็มมาแสดงในเอกสารนี้**

### 1.4 ความไม่สมมาตรของ `digest()` ที่ต้องจำ

| ฐานข้อมูล | schema ของ `digest()` | วิธีเรียก |
|---|---|---|
| Supabase | **`extensions`** | `extensions.digest(...)` |
| production PostgreSQL | **`public`** | `digest(...)` |

query ที่เขียนไว้สำหรับฝั่งหนึ่ง **ต้องเปลี่ยน schema ก่อนรันอีกฝั่ง**
ไม่มีการ `CREATE EXTENSION` และไม่มีการเปลี่ยน `search_path` ทั้งสองฝั่ง

---

## 2. M1 / M2 / N1 final status

| Blocker | สถานะ | หลักฐาน |
|---|---|---|
| **M1** — เทียบ hash ฝั่ง Supabase | ✅ **RESOLVED** | live MCP read-only · ได้ aggregate ครบ 4 ค่า · บัญชีที่มีสิทธิ์ทั้ง 2 พร้อม prefix · ผู้เขียนเดิม = **S2** จับคู่ด้วย full SHA-256 ภายใน SQL |
| **M2** — `digest()` อยู่ schema ไหน | ✅ **RESOLVED** | **`extensions`** · ยืนยันด้วยการที่ query รันผ่าน · ไม่ enable extension ไม่เปลี่ยน search_path |
| **N1** — การ normalize ของรอบ B2 | ✅ **RESOLVED** | ทั้งสองฝั่งใช้ `lower(btrim(email))` เหมือนกัน · บันทึกไว้ใน `B2_SUPABASE_AUTHOR_HASH.md` · **ความกังวลเรื่องผลบวกลวงตกไป** |

### 2.1 ทำไม N1 สำคัญกว่าที่ดู

รอบก่อนผมเตือนว่าถ้า B2 hash อีเมลดิบ ผล `NO_MATCH` อาจเป็นผลบวกลวง เพราะ
**ฝั่ง production มี 2 แถวที่เก็บอีเมลด้วยตัวพิมพ์ใหญ่** (ผลจาก `citext`) ซึ่งเป็นกลุ่ม
ที่จะพลาดได้พอดี

ตรวจแล้วทั้งสองฝั่งใช้ `lower(btrim(...))` และทั้งสองฝั่งผ่าน self-test กับค่าอ้างอิง
→ **`NO_MATCH` ของ S2 ยืนหยัด** และรอบนี้ผมรันซ้ำเองได้ผลเหมือนกัน

---

## 3. Legacy vs active identity — แยกให้ชัด

สองเรื่องนี้ถูกปนกันได้ง่ายและมีคำตอบต่างกัน

| | **LEGACY IDENTITY** | **ACTIVE WRITE IDENTITY** |
|---|---|---|
| คืออะไร | ผู้เขียนของแถวที่มีอยู่แล้วใน Supabase | ผู้ใช้ที่ล็อกอินแล้วเขียนข้อมูล**ใหม่**หลัง cutover |
| กี่แถว / กี่บัญชี | 15 แถว (12 courses + 3 news) · บัญชีเดียว = **S2** | บัญชีที่มีสิทธิ์ที่ยังใช้งานได้ = **S1 · S2** |
| ตัดสินแล้วหรือยัง | **ตัดสินแล้ว** — B2 `RESOLVED_WITH_NULL_LEGACY_AUTHOR` | **ยังไม่** — คือเรื่องของเอกสารนี้ |
| ค่าที่ใช้ | `created_by = NULL` · `updated_by = NULL` | **ต้องเป็น `public.users.id` จริง** |
| ความหมายของ NULL | *"ยังแมปผู้เขียนเดิมไม่ได้"* | **ห้ามใช้ NULL** — จะปนกับความหมายข้างซ้าย |
| ต้องการ mapping ไหม | **ไม่** | **ใช่** |

### 3.1 ข้อที่ต้องไม่สับสน

`S2` ปรากฏทั้งสองคอลัมน์ แต่ด้วยบทบาทต่างกัน

```
S2 ในฐานะ LEGACY author       -> ปิดแล้วด้วย NULL  ห้ามแมปใหม่
S2 ในฐานะ ACTIVE write identity -> ยังเป็น admin/approved ล็อกอินได้  แต่ไม่มีคู่ใน production
```

**การที่ S2 เป็น `NO_MATCH` ไม่ใช่เหตุผลให้ย้อนไปแก้การตัดสินใจเรื่อง legacy**
และไม่ใช่เหตุผลให้สร้างผู้ใช้ปลอม

---

## 4. Historical S2 handling — ปิดแล้ว ไม่แก้

B2 ตัดสินแล้วเป็น **`RESOLVED_WITH_NULL_LEGACY_AUTHOR`**

```
legacy courses 12 แถว + news 3 แถว
    created_by = NULL
    updated_by = NULL
```

### 4.1 สิ่งที่ยืนยันว่าไม่ได้ทำในรอบนี้

```
ไม่ได้พยายามแมป historical S2 ใหม่       ไม่ได้แมป S2 ไป admin คนอื่น
ไม่ได้แมป S2 ไป project owner (S1)       ไม่ได้สร้าง fake user
ไม่ได้สร้าง placeholder user             ไม่ได้ใช้ Supabase UUID เป็น PostgreSQL UUID
ไม่ได้เปลี่ยน historical created_by / updated_by ทั้งที่ Supabase และที่ปลายทาง
```

### 4.2 ความหมายของ NULL ที่ต้องรักษา

```
NULL ของแถว legacy = "legacy author identity not mapped"
                   ไม่ใช่ "ไม่มีผู้สร้างข้อมูล"
```

ตัวตนของ S2 **ยังอยู่ครบใน Supabase** (`created_by` ไม่ NULL 15/15 ที่ต้นทาง)
ไม่ได้ถูกลบหรือแก้ — NULL ที่ปลายทางคือการเก็บความไม่แน่นอนไว้อย่างซื่อสัตย์

---

## 5. S1 PostgreSQL mapping status

# `EXACT_MATCH`

| | |
|---|---|
| `postgres_match_count` | **1** |
| แถวที่ match เป็น `is_admin` | **ใช่** |
| แถวที่ match เป็น `is_active` | **ใช่** |
| ambiguity | **เป็นไปไม่ได้** — ฝั่ง Supabase 3 hash ไม่ซ้ำ · ฝั่ง production 198 hash ไม่ซ้ำ |
| วิธีตัดสิน | **full SHA-256 ภายใน SQL** ไม่ใช่ prefix |

### 5.1 ข้อสังเกตที่เพิ่มความมั่นใจ

production มี `is_admin = true` **เพียง 1 แถว** และแถวที่ S1 จับคู่ได้ **คือแถวนั้น**
→ สองหลักฐานที่ไม่เกี่ยวกันชี้ไปที่เดียว: hash ตรง และบทบาทตรง

`B2_AUTHOR_IDENTITY_CROSSCHECK.md` ยังระบุว่า S1 คือบัญชีของเจ้าของโปรเจกต์
(`owner_hash_match_count` ใน `auth.users` = 1 · `owner_hash_is_courses_author` = **false**)
→ **S1 = เจ้าของโปรเจกต์ และไม่ใช่ผู้เขียนเดิม** ซึ่งสอดคล้องกันทั้งสามแหล่ง

### 5.2 หลักฐานนี้เพิ่งได้มาในรอบนี้

`B1_SUPABASE_IDENTITY_VERIFICATION.md` ให้ prefix ของ S1 แต่ **ไม่ได้ระบุ
`postgres_match_count` ของ S1** · `B2_PRODUCTION_FINAL_VERIFICATION.md` ตรวจแต่ S2 ·
`B2_AUTHOR_IDENTITY_CROSSCHECK.md` ตรวจ S1 แต่ **เทียบภายใน `auth.users` เท่านั้น
ไม่ได้เทียบกับ production**

→ ก่อนรอบนี้ **S1 ยังเป็น UNKNOWN** และรอบนี้ปิดด้วยการรัน query ฝั่ง production เอง
โดยใช้ full hash ที่มีอยู่ในไฟล์หลักฐานแล้ว **ไม่ได้คำนวณจากอีเมลของใคร**

## 6. S2 PostgreSQL mapping status

# `NO_MATCH`

| | |
|---|---|
| `postgres_match_count` | **0** |
| เป็นผลลบลวงไหม | **ไม่** — self-test ของ pipeline ผ่าน · normalization ตรงกันทั้งสองฝั่ง (N1) · collision เป็นศูนย์ทั้งสองฝั่ง |
| ยืนยันซ้ำได้ไหม | **ได้** — `B2_PRODUCTION_FINAL_VERIFICATION.md` ได้ 0 และรอบนี้ผมรันเองได้ 0 เหมือนกัน |
| เป็น ambiguity ไหม | **ไม่** — เป็น **การไม่มีอยู่ที่ชัดเจน** (definitive absence) |

### 6.1 ผลสองด้านของ S2

| บทบาท | ผล |
|---|---|
| **LEGACY author** | **ไม่กระทบ** — ปิดด้วย NULL แล้ว (ข้อ 4) |
| **ACTIVE write identity** | ⚠ **S2 ยังเป็น `admin`/`approved` ล็อกอินได้วันนี้** → ถ้า S2 พยายามเขียนข้อมูลใหม่หลัง cutover จะ **FAIL CLOSED** ทุกครั้ง |

**ข้อหลังเป็นแกนของการจัดชั้น M4** — ดูข้อ 14

---

## 7. Active privileged mapping status

ตอบคำถามทั้ง 6 ข้อที่ Phase 3 ถาม

| # | คำถาม | คำตอบ |
|---|---|---|
| 1 | S1 PostgreSQL match status | **`EXACT_MATCH`** (1) — admin · active |
| 2 | S2 PostgreSQL match status | **`NO_MATCH`** (0) |
| 3 | บัญชีที่ใช้เขียนหลัง cutover ได้แบบ deterministic | **S1 เท่านั้น** |
| 4 | บัญชีที่ `NO_MATCH` | **S2** |
| 5 | บัญชีที่ `UNKNOWN` | **ไม่มี** — ตรวจครบทั้ง 2 บัญชีที่มีสิทธิ์แล้ว |
| 6 | มี ambiguity ไหม | **ไม่มี** — และ **เป็นไปไม่ได้** ด้วย ดูข้อ 7.1 |

### 7.1 ทำไม ambiguity เป็นไปไม่ได้ ไม่ใช่แค่ "ยังไม่เจอ"

```
ฝั่ง Supabase   3 บัญชี   -> 3 normalized hash ไม่ซ้ำ   -> duplicate 0
ฝั่ง production 198 แถว  -> 198 normalized hash ไม่ซ้ำ -> duplicate 0

ดังนั้นสำหรับ hash หนึ่งค่า จำนวนแถวที่จับคู่ได้เป็นได้แค่ 0 หรือ 1
```

พิสูจน์จากข้อมูลจริงทั้งสองฝั่ง **ไม่ใช่อนุมานจาก UNIQUE constraint**
(ซึ่งกันซ้ำแบบไม่สนตัวพิมพ์ แต่ไม่ได้กันช่องว่างหัวท้าย — `btrim` เป็นตัวจัดการ)

### 7.2 บัญชีที่สาม (S3)

`user` / `approved` — **ไม่อยู่ในกลุ่มที่สนใจ** เพราะไม่ผ่านระดับ EDITOR จึงเขียนข้อมูลไม่ได้
ตั้งแต่ชั้น authorization อยู่แล้ว · **ไม่ได้ตรวจ** และไม่จำเป็นต้องตรวจ

---

## 8. Option A — Runtime normalized-email mapping

```
token -> auth.getUser() -> email -> lower(btrim(email))
      -> SELECT id FROM public.users WHERE email = <normalized>   ทุกคำขอที่เขียน
```

| มิติ | ประเมิน |
|---|---|
| **determinism** | **ดี ณ วันนี้** — S1 จับคู่ได้ 1 แถว · `citext` เทียบไม่สนตัวพิมพ์ให้เอง |
| **security** | **อ่อนที่สุด** — ใครควบคุมอีเมลฝั่ง Supabase ได้ จะกลายเป็นผู้ใช้ฝั่งเราคนนั้นทันทีโดยไม่ต้องรู้รหัสผ่านฝั่งเรา · **อีเมลกลายเป็นหนังสือเดินทางข้ามระบบ** |
| **performance** | เพิ่ม query ทุกคำขอที่เขียน · มี index บน `email` จึงเร็ว แต่เป็น round trip เพิ่ม |
| **email change** | **พังเงียบ ๆ** — เปลี่ยนอีเมลแล้วกลายเป็น `NO_MATCH` ทันที งานเขียนถูกปฏิเสธโดยไม่มีใครรู้สาเหตุ · และถ้ามีคนอื่นมาใช้อีเมลเดิมภายหลัง **จะได้ตัวตนของคนเก่าไป** |
| **account deletion** | แถวเก่าไม่กระทบ · บัญชีนั้นเขียนอะไรไม่ได้อีก |
| **PII exposure** | **แย่ที่สุด** — อีเมลจริงต้องเดินทางเข้า `webapi` **ทุกคำขอ** · `auth.mjs` ตั้งใจไม่เก็บอีเมลใน context เลย ทางนี้ทำลายหลักนั้น |
| **operational complexity** | **ต่ำสุด** — ไม่ต้องแก้ schema |
| **migration complexity** | **ต่ำสุด** — ไม่มี migration |
| **Path 3 compatibility** | **ปานกลาง** — ตัด Supabase Auth แล้วไม่มีอะไรเหลือเป็นร่องรอยว่าใครคือใคร |
| **long-term maintainability** | **แย่** — ตัดสินใหม่ทุกคำขอจากค่าที่เปลี่ยนได้ · ไม่มีบันทึกว่าจับคู่เมื่อไหร่อิงอะไร |

### 8.1 ข้อที่หลักฐานใหม่เพิ่งเผย — A ซ่อนปัญหาของ S2

ภายใต้ Option A บัญชี S2 จะ `NO_MATCH` **ทุกคำขอตลอดไป** โดยไม่มีที่ใดในระบบบันทึกว่า
"มีบัญชีที่มีสิทธิ์ที่ยังไม่ได้จับคู่" → ผู้ดูแลจะเห็นแค่ "บันทึกไม่สำเร็จ" ซ้ำ ๆ

ภายใต้ B/C การไม่ได้จับคู่เป็น **สภาพของข้อมูลที่ query ได้** → ตรวจได้ว่าใครยังไม่ถูกจับคู่

## 9. Option B — Explicit identity mapping table

```
identity_mappings (auth_provider, external_user_id, local_user_id, created_at)
  UNIQUE (auth_provider, external_user_id)
  UNIQUE (auth_provider, local_user_id)
```

| มิติ | ประเมิน |
|---|---|
| **determinism** | **ดีที่สุด** — จับคู่ด้วย uuid ที่บันทึกไว้ ไม่คำนวณใหม่ |
| **security** | **ดี** — จับคู่ครั้งเดียวอย่างตั้งใจแล้วตรึงไว้ |
| **performance** | query ด้วย uuid ที่มี index · ต้อง join หนึ่งชั้น |
| **email change** | **ไม่กระทบเลย** |
| **account deletion** | แถวค้างชี้ external id ที่ไม่มีแล้ว · ต้องมีนโยบายเก็บกวาด |
| **PII exposure** | **ดีที่สุด** — เก็บแต่ uuid สองตัว ไม่มีอีเมลเลย |
| **operational complexity** | **สูงสุด** — ตารางใหม่ + ความสัมพันธ์ใหม่ + ขั้นตอนสร้างแถว |
| **migration complexity** | ต้องสร้างตารางใหม่ |
| **Path 3 compatibility** | **ดีที่สุด** — รองรับผู้ให้บริการ auth หลายราย และเก็บประวัติการจับคู่ |
| **long-term maintainability** | ดี แต่มีของให้ดูแลเพิ่ม |

## 10. Option C — External identity column

```
public.users.supabase_user_id UUID        -- partial unique index WHERE NOT NULL
runtime:  supabase uuid -> supabase_user_id -> public.users.id
```

| มิติ | ประเมิน |
|---|---|
| **determinism** | **ดีที่สุด** เท่า B — uuid ที่บันทึกไว้ |
| **security** | **ดี** เท่า B · `UNIQUE` กันไม่ให้สอง Supabase account ชี้ผู้ใช้เดียวกัน |
| **performance** | **ดีที่สุด** — query เดียวบนตารางเดียว ไม่ต้อง join |
| **email change** | **ไม่กระทบเลย** |
| **account deletion** | ตั้งคอลัมน์เป็น NULL จบ · **ง่ายกว่า B** ไม่มีแถวค้าง |
| **PII exposure** | **ดี** — เก็บแต่ uuid |
| **operational complexity** | **ต่ำกว่า B** — ไม่มีตารางใหม่ |
| **migration complexity** | `ADD COLUMN` + partial unique index — **เบากว่า B** |
| **Path 3 compatibility** | **ปานกลาง** — ผูกกับผู้ให้บริการรายเดียว · ถ้าวันหนึ่งมีหลายราย ต้องย้ายไปเป็นตารางแบบ B |
| **long-term maintainability** | **ดี** — คอลัมน์เดียว ความหมายชัด · ข้อเสียคือ 196/198 แถวจะเป็น NULL |

---

## 11. Recommended Phase 1 design

# **Option C**

```
Supabase authenticated user
        ↓  auth.getUser(token)  ->  supabase uuid  (+ role/status จาก user_profiles)
webapi  (ด่าน B1 foundation ที่ทำแล้ว)
        ↓  SELECT id FROM public.users WHERE supabase_user_id = <supabase uuid>
resolve local identity
        ↓  ต้องได้ 1 แถวพอดี  ไม่ได้ -> FAIL CLOSED
public.users.id
        ↓
web.site_courses.created_by / updated_by
web.news.created_by / updated_by
```

### 11.1 ทำไม C เหมาะกว่า A

| | |
|---|---|
| **อีเมลเป็นค่าที่เปลี่ยนได้และนำกลับมาใช้ได้** | ผูกตัวตนไว้กับมันตลอดกาลไม่มั่นคง · ถ้ามีคนอื่นมาใช้อีเมลเดิมภายหลัง จะได้ตัวตนของคนเก่าไป (ข้อ 8) |
| **A บังคับให้อีเมลเข้ามาใน `webapi` ทุกคำขอ** | ทำลายหลักที่ `auth.mjs` ตั้งไว้ว่า context ไม่เก็บอีเมล และ `describeForLog()` มีข้อตรวจคุ้มว่าไม่มีอีเมลใน log |
| **A ไม่มีร่องรอยว่าจับคู่เมื่อไหร่อิงอะไร** | ตรวจย้อนหลังไม่ได้ |
| ⬅ **หลักฐานใหม่: S2 เป็น `NO_MATCH`** | ภายใต้ A การไม่ได้จับคู่เป็นสิ่งที่ **มองไม่เห็น** · ภายใต้ C เป็น **สภาพของข้อมูลที่ query ได้** ว่าบัญชีไหนยังไม่ถูกจับคู่ (ข้อ 8.1) |

### 11.2 ทำไม C เหมาะกว่า B

| | |
|---|---|
| วันนี้มีผู้ให้บริการ auth **รายเดียว** | ตารางที่รองรับหลายรายยังไม่มีใครใช้ |
| บัญชีที่มีสิทธิ์มี **2 บัญชี** และจะจับคู่จริง **1** | ตารางแยกพร้อม FK สองทางเกินความจำเป็น |
| **ลบบัญชีง่ายกว่า** | ตั้งคอลัมน์เป็น NULL จบ · ไม่มีแถวค้างต้องเก็บกวาด |
| ย้ายทีหลังได้ | ถ้าวันหนึ่งมีหลายผู้ให้บริการ ย้ายจากคอลัมน์ไปเป็นตารางแบบ B ได้ และตอนนั้นจะมีเหตุผลรองรับจริง |

### 11.3 ไม่ overfit กับผู้ใช้ 3 คน

```
ไม่มี  if email == ...        ไม่มี  if uuid == ...
ไม่มี  hardcoded mapping      ไม่มี  static mapping ใน source code
```

กลไกเป็นคอลัมน์ `UNIQUE` + query เดียว — **รองรับผู้ใช้เพิ่มเท่าไหร่ก็ได้**
การจับคู่แต่ละรายเป็นข้อมูล ไม่ใช่โค้ด

### 11.4 อีเมลใช้แค่ครั้งเดียว ไม่ใช้ตอน runtime

email hash ใช้เพื่อ **หา** คู่ที่ถูกต้องในขั้นเติมค่าครั้งแรกเท่านั้น (ซึ่งรอบนี้ทำแล้ว
สำหรับ S1) · หลังจากนั้น runtime ใช้ uuid ที่บันทึกไว้ → ได้ความแน่นอนของ C
โดยไม่ต้องให้อีเมลเดินทางเข้าชั้น API เลย

---

## 12. Author write contract

**ออกแบบไว้ ยังไม่ implement**

### 12.1 CREATE

```
1. verify Supabase token                     auth.getUser()        [ทำแล้วใน B1 foundation]
2. authorize role/status                     EDITOR ขึ้นไป          [ทำแล้วใน B1 foundation]
3. resolve local PostgreSQL user             supabase_user_id -> public.users.id
4. ต้อง match exactly 1                      0 หรือ >1 -> FAIL CLOSED
5. created_by = local user.id
6. updated_by = local user.id
```

### 12.2 UPDATE

```
1. verify / authorize                        [ทำแล้วใน B1 foundation]
2. resolve local PostgreSQL user             ไม่สำเร็จ -> FAIL CLOSED
3. created_by  ***ไม่อยู่ใน SET clause เลย***
4. updated_by = local user.id
```

### 12.3 ทำไม `created_by` ต้องไม่อยู่ใน `SET` ของ UPDATE เลย

ไม่ใช่แค่ *"ตั้งค่าให้เท่าเดิม"* แต่ **ไม่ใส่คอลัมน์ลงไปด้วยซ้ำ**

แถว legacy มี `created_by = NULL` ซึ่งหมายความว่า *"ยังแมปผู้เขียนเดิมไม่ได้"*
ถ้า UPDATE เขียนค่าลงไป ความหมายจะกลายเป็น *"คนที่เพิ่งมาแก้เป็นคนสร้าง"* ซึ่งไม่จริง
— เป็นการยัดเจ้าของผิดคนแบบเดียวกับที่ห้ามตอน migration เพียงแต่เกิดภายหลัง

และการไม่ใส่คอลัมน์เลย **ปลอดภัยกว่าการใส่แล้วตั้งค่าเท่าเดิม** เพราะอย่างหลัง
ยังมีช่องพลาดถ้าโค้ดสร้าง SET clause แบบ dynamic

### 12.4 ห้ามเชื่อค่าจาก request

```
created_by จาก request body   ->  ตัดออกทิ้ง
updated_by จาก request body   ->  ตัดออกทิ้ง
```

`stripAuthorFields()` ใน `webapi/auth.mjs` **ทำงานแล้วและมีข้อตรวจคุ้ม**
จำเป็นจริงเพราะวันนี้หน้าเว็บส่ง `updated_by: user?.id` มาเองที่ `KnowledgeForm.jsx:138`
ซึ่ง RLS ต้นทางไม่ได้กัน

### 12.5 รูปร่างที่มีอยู่ในโค้ดแล้ว

```js
stripAuthorFields(payload)   // ทำงานแล้ว
resolveAuthorId()            // ปฏิเสธเสมอ พร้อมรหัส B1_ACTIVE_USER_MAPPING_REQUIRED
authorFieldsFor(mode, ctx)   // create: ทั้งสองคอลัมน์ · update: แค่ updated_by
                             // ตอนนี้คืน ok:false ทุกครั้ง
```

**เหลือแต่ให้ `resolveAuthorId()` ทำงานได้เมื่อมีคอลัมน์** — ไม่ต้องแก้โครงอื่น

---

## 13. Fail-closed behavior

### 13.1 เมื่อ resolve ไม่ได้

```
ปฏิเสธคำขอ  ไม่เขียนข้อมูลใด ๆ แม้บางส่วน
```

**ห้ามทำทั้งห้าอย่างนี้**

```
created_by = NULL สำหรับข้อมูลใหม่   ปนกับความหมายของแถว legacy
fallback ไป admin                     ยัดเจ้าของผิดคน
fallback ไปผู้ใช้คนแรก                ยัดเจ้าของผิดคน
ใช้ Supabase uuid ตรง ๆ               FK ปฏิเสธ หรือชี้ผิดคน
เชื่อ created_by / updated_by จาก request
```

### 13.2 HTTP behavior ที่เสนอ

| สถานการณ์ | รหัส | body |
|---|---|---|
| ไม่มี token / token ใช้ไม่ได้ | **401** | `{"error":"Unauthorized"}` — เหมือน B1 foundation |
| ล็อกอินแล้วแต่สิทธิ์ไม่พอ | **403** | `{"error":"Forbidden"}` — เหมือน B1 foundation |
| **ล็อกอินแล้ว สิทธิ์พอ แต่บัญชียังไม่ถูกจับคู่** | **409 Conflict** | `{"error":"Account is not linked"}` |

**ทำไม 409** — ผู้เรียกไม่ได้ทำอะไรผิด และส่งคำขอใหม่ก็ไม่หาย เป็นสถานะที่ต้องให้
ผู้ดูแลจัดการ · ไม่ใช่ **403** (สื่อว่าสิทธิ์ไม่พอ ซึ่งผิด) · ไม่ใช่ **500**
(สื่อว่าระบบพัง ซึ่งผิดและทำให้ไม่มีใครไปแก้ต้นเหตุ) · ไม่ใช่ **422**
(สื่อว่าข้อมูลที่ส่งมาผิด ซึ่งผิด)

### 13.3 ต้องเห็นได้ว่าเกิดขึ้น — ไม่ใช่เงียบ

**หลักฐานใหม่ทำให้ข้อนี้เป็นเรื่องจริง ไม่ใช่สมมติ** — S2 เป็น `admin`/`approved`
ที่ล็อกอินได้วันนี้ และจะชน 409 ทุกครั้งที่พยายามเขียน

ถ้าเงียบ ผู้ดูแลจะเจอแต่ "บันทึกไม่สำเร็จ" โดยไม่มีใครรู้สาเหตุ

```
log         "บัญชีนี้ยังไม่ได้จับคู่ — role=admin status=approved"
            ไม่มี uuid ไม่มีอีเมล  ตามหลักของ describeForLog()
มองเห็นได้  ควรมีทางให้นับได้ว่ามีบัญชีที่มีสิทธิ์กี่บัญชีที่ยังไม่ถูกจับคู่
            (ภายใต้ Option C query ได้ตรง ๆ จากคอลัมน์)
```

---

## 14. M4 final classification

# `M4_RESOLVED_DESIGN_READY`

> **ปรับปรุง 2026-10-03 หลังเจ้าของตัดสินใจ**
>
> เดิมจัดเป็น `M4_ACTIVE_USER_PROVISIONING_REQUIRED` เพราะ **S2** เป็น `admin`/`approved`
> ที่ล็อกอินได้แต่ `match_count = 0` และยังไม่รู้ว่า S2 ต้องเขียนข้อมูลต่อหรือไม่
>
> **เจ้าของเลือกทางเลือก A**: ต่อจากนี้ใช้ **S1 บัญชีเดียว** ในการเพิ่ม/แก้ Courses และ News
> → **ไม่ต้อง provision ผู้ใช้ PostgreSQL ให้ S2**
>
> เงื่อนไขที่ค้างข้อเดียวจึงถูกตอบแล้ว และตามเกณฑ์ที่กำหนดไว้ สถานะพลิกเป็น
> **`M4_RESOLVED_DESIGN_READY`** โดย **ไม่ต้องแก้อะไรในโค้ดหรือ schema**

### 14.0 สิ่งที่การตัดสินใจนี้ยืนยัน

| | |
|---|---|
| บัญชีที่ใช้เขียนข้อมูลใหม่ | **S1 เท่านั้น** — `EXACT_MATCH` (1) · admin · active |
| S2 | **ไม่ provision** · ถ้าพยายามเขียนผ่าน API ใหม่จะได้ **409** ซึ่งเป็น **พฤติกรรมที่ถูกต้อง ไม่ใช่ข้อบกพร่อง** |
| legacy 15 แถว | `created_by` / `updated_by` = **NULL** — **ไม่เปลี่ยน** ตาม B2 |
| ถอนกลับได้ไหม | **ได้** — ถ้าวันหนึ่ง S2 ต้องเขียนจริง ใช้ทางเดียวกับ S1 คือผูก `supabase_user_id` กับผู้ใช้ production ที่**มีอยู่แล้ว** · การตัดสินใจนี้ไม่ปิดประตูนั้น |
| ไม่ได้ทำอะไร | ไม่สร้างผู้ใช้ · ไม่ fallback · ไม่ใช้ NULL สำหรับข้อมูลใหม่ · ไม่แก้ legacy |

### 14.0.1 ⚠ สิ่งที่การตัดสินใจนี้ **ไม่** ได้ทำ — ยังเป็นเรื่องค้าง

**ทางเลือก A ไม่ได้ลดอำนาจของ S2 บน Supabase เลย**

A ปิดเฉพาะทางเขียนผ่าน API ใหม่ · S2 ยังเป็น `admin`/`approved` จึงยังทำสิ่งเหล่านี้ได้
**จนกว่า SPA จะเลิกคุย Supabase ตรง** ซึ่งเป็นปลายทางของ B1 ทั้งหมด ไม่ใช่รอบนี้

```
DELETE courses · news · knowledge_articles · external_news   (policy role = admin)
INSERT / UPDATE ทุกตารางเนื้อหา
อ่าน knowledge_articles ที่คนทั่วไปอ่านไม่ได้
UPDATE user_profiles ของคนอื่น  ->  เลื่อน/ลดสิทธิ์ใครก็ได้
```

ถ้าเจตนาคือ *"ต่อจากนี้มีแต่ S1 ที่จัดการเนื้อหา"* การแสดงเจตนานั้นให้ถูกที่คือ
**เปลี่ยน `role` หรือ `status` ของ S2 ใน Supabase** (เป็น `user` หรือ `pending`)
ไม่ใช่การพึ่ง 409 ของ API ใหม่

→ เป็น **Supabase write** ซึ่งรอบนี้ห้าม · **ต้องเป็นรอบแยกที่เจ้าของอนุมัติ**
บันทึกเป็นข้อ **S2-PRIV** ในข้อ 16

### 14.1 เทียบกับเกณฑ์ทั้งสี่ (บันทึกเดิม ก่อนการตัดสินใจ)

| เกณฑ์ | ตรงไหม | เหตุผล |
|---|---|---|
| `M4_ACTIVE_USER_VERIFICATION_REQUIRED` — S1 ยังไม่ได้ verify | **ไม่** | **S1 verify แล้วในรอบนี้** → `EXACT_MATCH` (1) |
| `M4_BLOCKED_IDENTITY_AMBIGUITY` — มี duplicate / multiple matches | **ไม่** | collision เป็นศูนย์ทั้งสองฝั่ง → match เป็นได้แค่ 0 หรือ 1 **เป็นไปไม่ได้ที่จะกำกวม** |
| `M4_ACTIVE_USER_PROVISIONING_REQUIRED` — active privileged account **ที่จำเป็นต้องใช้** ถูก verify แล้วว่าไม่มี PostgreSQL counterpart | ~~ใช่~~ → **ไม่** | S2 `match_count = 0` จริง **แต่เจ้าของยืนยันว่า S2 ไม่จำเป็นต้องใช้เขียนข้อมูลอีก** → เงื่อนไข "จำเป็นต้องใช้" ไม่เป็นจริง |
| **`M4_RESOLVED_DESIGN_READY`** — design + active identity พร้อม deterministic | ~~ยังไม่~~ → **ใช่** | **S1 เป็น identity ที่ใช้เขียนจริง และ deterministic แล้ว** · S2 ไม่อยู่ในเส้นทางการเขียนอีก |

### 14.2 บันทึกว่าทำไมเดิมไม่จัดเป็น `DESIGN_READY`

ก่อนการตัดสินใจ S2 เป็นบัญชีที่เขียนเนื้อหาทั้ง **100%** ของระบบมาตลอด
(courses 12/12 · news 3/3) และยังเป็น `admin`/`approved` ที่ล็อกอินได้
การจัดเป็น `DESIGN_READY` ตอนนั้นจะกลบข้อเท็จจริงว่า **บัญชีที่เคยทำงานทั้งหมด
จะเขียนอะไรไม่ได้เลยหลัง cutover** ซึ่งเป็นผลที่เจ้าของควรรู้**ก่อน** ไม่ใช่หลัง

**เจ้าของรู้แล้วและเลือกแล้ว** จึงไม่ใช่การกลบข้อเท็จจริงอีก

### 14.3 ✅ คำถามที่ค้าง — ตอบแล้ว

> **S2 ยังต้องเขียนข้อมูลใหม่หลัง cutover หรือไม่**

**คำตอบ: ไม่ต้อง** — เจ้าของยืนยันว่าต่อจากนี้ใช้ **S1 บัญชีเดียว** ในการเพิ่ม/แก้
Courses และ News

| | |
|---|---|
| ต้อง provision ให้ S2 ไหม | **ไม่** |
| ต้องแก้ migration / schema เพิ่มไหม | **ไม่** — การตัดสินใจนี้ไม่ต้องแก้อะไรเลย |
| S2 จะเจออะไรถ้าพยายามเขียน | **409 `Account is not linked`** — **พฤติกรรมที่ถูกต้อง** |
| ย้อนกลับได้ไหม | **ได้** — ผูก `supabase_user_id` กับผู้ใช้ที่มีอยู่แล้ว เหมือนที่ S1 ทำ |

### 14.4 ทางที่ไม่ขัดข้อห้าม — เก็บไว้เผื่อวันหนึ่งคำตอบเปลี่ยนเป็น "ต้อง"

| ทาง | ขัดข้อห้ามไหม |
|---|---|
| เจ้าของเปลี่ยนอีเมลของ S2 ฝั่ง Supabase ให้ตรงกับบัญชีที่มีอยู่แล้วฝั่ง production | **ไม่ขัด** — ไม่สร้างผู้ใช้ใหม่ · แต่เป็นการแก้ Supabase ซึ่งรอบนี้ห้าม จึงต้องเป็นรอบแยก |
| เจ้าของชี้ `public.users.id` ที่ต้องการให้ S2 ผูกด้วย **ด้วยตัวเอง** แล้วตั้ง `supabase_user_id` | **ไม่ขัด** — ชี้แถวที่มีอยู่ ไม่ใช่สร้างแถว · ต้องเป็นการตัดสินใจของเจ้าของว่า S2 คือใครในระบบเรา |
| เจ้าของสร้างบัญชีใหม่ฝั่ง production ให้ S2 เอง | **ผมไม่ทำ** — เป็นการ provision ซึ่งต้องเป็นคนตัดสินใจและลงมือเอง |
| ~~ให้ระบบสร้างผู้ใช้อัตโนมัติเมื่อ resolve ไม่เจอ~~ | **ขัดโดยตรง** — ห้ามสร้าง user |
| ~~ให้ S2 ใช้ `created_by = NULL`~~ | **ขัดโดยตรง** — ห้าม NULL สำหรับข้อมูลใหม่ |
| ~~ให้ S2 fallback ไปเป็น S1~~ | **ขัดโดยตรง** — ยัดเจ้าของผิดคน |

---

## 15. B1_ACTIVE_USER_MAPPING_REQUIRED

# `true`

**ไม่เปลี่ยนเป็น `false`** ตามที่คำสั่งระบุ — design พร้อมไม่เท่ากับ implement แล้ว

สภาพจริงในโค้ดวันนี้

```
public.users.supabase_user_id   ยังไม่มีคอลัมน์นี้  (ยืนยันจาก pg_attribute)
resolveAuthorId()               ยังปฏิเสธเสมอ
authorFieldsFor()               ยังคืน ok:false ทุกครั้ง
write endpoint                  ยังไม่มีแม้เส้นทางเดียว
webapi -> PostgreSQL            ยังต่อไม่ได้  ไม่มี DATABASE_URL
```

จะเปลี่ยนเป็น `false` ได้เมื่อครบทั้งห้าข้อ และผ่านการทดสอบแล้ว

---

## 16. Remaining blocker

| # | Blocker | ระดับ | สถานะ |
|---|---|---|---|
| ~~**M4**~~ | ~~S2 ยังต้องเขียนข้อมูลหลัง cutover หรือไม่~~ | — | ✅ **ปิดแล้ว 2026-10-03** — เจ้าของเลือก **A**: ใช้ S1 บัญชีเดียว · ไม่ provision ให้ S2 |
| **S2-PRIV** | **S2 ยังมีสิทธิ์ `admin` เต็มบน Supabase** รวม DELETE และการแก้ `user_profiles` ของคนอื่น | **กลาง** | ⬅ **ข้อใหม่จากการตัดสินใจ** · ทางเลือก A ปิดเฉพาะทางเขียนผ่าน API ใหม่ ไม่ได้ลดสิทธิ์บน Supabase · ถ้าต้องการให้ตรงกับเจตนา ต้องเปลี่ยน `role`/`status` ของ S2 ซึ่งเป็น **Supabase write** → **รอบแยกที่เจ้าของอนุมัติ** · ดูข้อ 14.0.1 |
| **M3** | **`webapi` ยังต่อ PostgreSQL ไม่ได้** | **สูง** | `docker-compose.prod.yml` ให้แต่ `VITE_SUPABASE_URL` + anon key · **ไม่มี `DATABASE_URL`** · ต้องตัดสินใจเรื่อง role (`advisor_api` ตาม GRANT ของ 005) และการจัดการรหัสผ่านใน env |
| **R1** | `createSupabaseVerifier` ยังไม่เคยคุยกับ Supabase จริง | **สูง** | ค้างจากรอบ B1 foundation · ถ้ารูปแบบที่ `auth.getUser` คืนมาไม่ตรง ด่านจะปฏิเสธทุกคน (**fail closed** — ผู้ดูแลเข้าไม่ได้ ไม่ใช่คนนอกเข้าได้) |
| **R6** | ครึ่งหนึ่งของงาน B1 อยู่ในรีโปหน้าเว็บที่ยังไม่อนุมัติให้แก้ | **สูง** | ค้างจากรอบ B1 foundation |

### 16.1 ที่ปิดแล้วในรอบนี้

```
M4  S2 ต้องเขียนข้อมูลต่อหรือไม่        RESOLVED  ->  ไม่ต้อง (เจ้าของเลือก A)   <- ใหม่
M1  เทียบ hash ฝั่ง Supabase          RESOLVED
M2  digest() อยู่ schema extensions    RESOLVED
N1  normalization ตรงกันทั้งสองฝั่ง     RESOLVED  ->  NO_MATCH ของ S2 ยืนหยัด
S1  PostgreSQL match status           EXACT_MATCH (1) · admin · active   <- ใหม่
S2  PostgreSQL match status           NO_MATCH (0) · ยืนยันซ้ำได้         <- ยืนยันเอง
ambiguity                             เป็นไปไม่ได้ทั้งสองทิศทาง
design                                เลือก Option C พร้อมเหตุผลเทียบ A/B
author write contract                 ครบ · รูปร่างอยู่ในโค้ดแล้ว
fail-closed                           เสนอ 409 พร้อมเหตุผลที่ไม่เลือก 403/500/422
```

**ไม่มีข้อใดเหลือที่เป็น "ต้องตรวจเพิ่ม"** — ที่เหลือเป็นการตัดสินใจและการลงมือ

---

## 17. Exact next step

```
1. ✅ เจ้าของตอบข้อ 14.3 แล้ว  S2 ไม่ต้องเขียนข้อมูลอีก -> M4_RESOLVED_DESIGN_READY

2. อนุมัติ Option C          ถ้าอนุมัติแล้วจึงขออนุมัติ migration 006 แยกอีกรอบ
                             ** ห้ามสร้าง 006 ในรอบนี้ และห้ามแก้ 005 **

3. ปลดล็อก M3                ให้ webapi ต่อ PostgreSQL ได้
                             ตัดสินใจ role + วิธีจัดการรหัสผ่านใน env
                             *** เป็นงานที่ต้องทำก่อน implement mapping ไม่ว่าจะเลือก design ไหน ***

4. ปลดล็อก R1                ยืนยัน createSupabaseVerifier กับ Supabase จริง

5. ขออนุมัติเขียนรีโปหน้าเว็บ  บล็อกงาน B1 ที่เหลือทั้งหมด

6. จึงเริ่ม implement         migration 006 -> ข้อตรวจ -> resolveAuthorId()
                             -> ขั้นเติมค่า supabase_user_id ของ S1 (เจ้าของยืนยัน)
                             -> write endpoint ทีละตาราง
```

### 17.1 ไม่มี READ-ONLY verification ค้างอยู่

คำสั่งระบุว่า *"ถ้า S1 ยังต้องตรวจเพิ่ม ให้เขียน exact READ-ONLY verification ที่ต้องทำต่อ"*

**S1 ตรวจเสร็จแล้วในรอบนี้** — รัน query ฝั่ง production เองด้วย full hash ที่มีอยู่
ในไฟล์หลักฐานแล้ว ได้ `postgres_match_count = 1` · **ไม่มี verification ค้าง**

ถ้าต้องการตรวจซ้ำเพื่อยืนยัน ใช้ query ในข้อ 1.3 ได้ตรง ๆ — เป็น `SELECT` ล้วน
คืนแต่จำนวนกับ boolean ไม่คืนอีเมลหรือ uuid

---

## บันทึกการเข้าถึงข้อมูลในรอบนี้

| ระบบ | การเข้าถึง | รายละเอียด |
|---|---|---|
| production PostgreSQL | **อ่านอย่างเดียว** | `SELECT` 1 ชุด — เทียบ full hash ภายใน SQL · คืน `count(*)` กับ `bool_or()` · พร้อม self-test ของ pipeline |
| Supabase | **ไม่ได้เข้าถึงเลย** | ใช้ผลจาก `B1_SUPABASE_IDENTITY_VERIFICATION.md` ที่ตรวจไว้แล้ว |
| full hash ของ S1 / S2 | อ่านจาก `B2_AUTHOR_IDENTITY_CROSSCHECK.md` | **ไม่ได้คำนวณจากอีเมลของใคร** และ **ไม่นำค่าเต็มมาแสดงในเอกสารนี้** |
| ข้อมูลที่ดึงออกมา | จำนวนเต็ม · boolean | **ไม่มีอีเมล ไม่มี uuid ไม่มีชื่อ ไม่มี full hash** |
| คำสั่งเขียน / DDL | **ไม่มีแม้คำสั่งเดียว** | |

---

## STOP

**`M4_RESOLVED_DESIGN_READY`** · **`B1_ACTIVE_USER_MAPPING_REQUIRED = true`**

ปิดแล้ว: **M4** — เจ้าของเลือก **A** (ใช้ S1 บัญชีเดียว · ไม่ provision ให้ S2)

เรื่องที่รอการตัดสินใจ

1. **อนุมัติ Option C** หรือไม่ (ถ้าอนุมัติ จึงขออนุมัติ migration 006 แยก)
2. **M3** — ให้ `webapi` ต่อ PostgreSQL ด้วย role ไหน จัดการรหัสผ่านอย่างไร
   *(ต้องทำก่อน implement ไม่ว่าจะเลือก design ไหน)*
3. **S2-PRIV** — จะลดสิทธิ์ `admin` ของ S2 บน Supabase ไหม (รอบแยก · เป็น Supabase write)
4. **R1** — ยืนยัน `createSupabaseVerifier` กับ Supabase จริงเมื่อใด
5. **อนุมัติเขียนรีโปหน้าเว็บ** — บล็อกงาน B1 ที่เหลือทั้งหมด
6. **HTTP 409** สำหรับกรณีจับคู่ไม่ได้ เหมาะไหม

```
Migration 006        NONE   ALTER public.users   NONE   CREATE mapping table  NONE
สร้าง/แก้ user        NONE   implement mapping    NONE   write endpoints       NONE
Apply Migration 005  NONE   Apply Migration 006  NONE   Data Migration        NONE
Production Write     NONE   Supabase Write       NONE   แก้ frontend          NONE
Deploy / Restart     NONE   Commit / Push        NONE   Merge main            NONE
```
