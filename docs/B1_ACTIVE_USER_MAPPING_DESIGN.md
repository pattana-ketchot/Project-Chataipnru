# B1 — Active User Mapping · Design + READ-ONLY Verification

| | |
|---|---|
| วันที่ | 2026-10-02 · **ปรับปรุง 2026-10-03** |
| ขอบเขต | **DESIGN + READ-ONLY VERIFICATION เท่านั้น** |
| **สถานะเอกสารนี้** | **ถูกแทนที่บางส่วนแล้ว** → ข้อสรุปที่ใช้จริงอยู่ใน **`B1_ACTIVE_USER_MAPPING_FINAL_DECISION.md`** |
| **ผลตรวจฝั่ง PostgreSQL** | **เสร็จครบ** — normalized email ไม่ซ้ำ 198/198 |
| **ผลตรวจฝั่ง Supabase** | ~~ทำไม่ได้~~ → **เสร็จแล้ว 2026-10-03** (`B1_SUPABASE_IDENTITY_VERIFICATION.md`) |
| **M1 · M2 · N1** | **RESOLVED ทั้งสามข้อ** |
| **S1** (`admin`/`approved`) | **`EXACT_MATCH`** — production match = **1** · admin · active |
| **S2** (`admin`/`approved` · ผู้เขียนเดิม) | **`NO_MATCH`** — production match = **0** |
| **Final classification** | ~~`MAPPING_REQUIRES_OWNER_DECISION`~~ → **`M4_RESOLVED_DESIGN_READY`** ✅ |
| **การตัดสินใจของเจ้าของ** | **ทางเลือก A** (2026-10-03) — ใช้ **S1 บัญชีเดียว** · ไม่ provision ให้ S2 |
| **B1_ACTIVE_USER_MAPPING_REQUIRED** | **`true`** (ยังไม่เปลี่ยน) |
| Design ที่แนะนำ | **Option C** (ดูข้อ 15 และเอกสาร Final Decision ข้อ 11) |

> ## ⬆ อ่านเอกสารนี้อย่างไร
>
> เอกสารนี้เขียนตอนที่ **ยังไม่มีผลตรวจฝั่ง Supabase** — การวิเคราะห์ design options
> (ข้อ 9–14) ยังใช้ได้ทั้งหมด แต่ **ส่วนที่บอกว่าข้อมูลยัง UNKNOWN ถูกปิดไปแล้ว**
> ดูสถานะล่าสุดในตารางข้างบน และข้อสรุปที่ใช้จริงใน
> **`docs/B1_ACTIVE_USER_MAPPING_FINAL_DECISION.md`**

```
INSERT/UPDATE/DELETE  NONE   CREATE/ALTER/DROP/DDL  NONE   Production Write  NONE
Supabase Write        NONE   Create User            NONE   Create Mapping    NONE
Apply Migration 005   NONE   Data Migration         NONE   write endpoints   NONE
แก้ frontend          NONE   Deploy / Restart       NONE   Commit / Push     NONE
Merge main            NONE   implement mapping      NONE
```

**ไม่มีอีเมล ไม่มี UUID ไม่มี token ไม่มีคีย์ ไม่มี hash เต็มของผู้ใช้จริงในเอกสารนี้**
hash เดียวที่ปรากฏคือของ `test@example.com` ซึ่งเป็นค่าอ้างอิงสาธารณะใช้ทดสอบฟังก์ชัน

---

## 1. Current identity architecture

**สองระบบตัวตนที่ไม่มีเส้นเชื่อมกันเลย**

```
Browser
  │ email + password
  └──► Supabase Auth ──► auth.users                    ← ตัวตนของผู้ดูแลหน้าเว็บ
                            │ (id = uuid ของ Supabase)
                            └──► public.user_profiles   ← role / status
                                   user_id → auth.users.id

Browser / eval
  │ email + password
  └──► FastAPI /auth/login ──► public.users             ← ตัวตนของระบบเรา
                                 (id = uuid ที่เราสร้างเอง)
                                 bcrypt password_hash
```

| | Supabase Auth | FastAPI |
|---|---|---|
| ที่เก็บตัวตน | `auth.users` | `public.users` |
| ที่เก็บสิทธิ์ | `public.user_profiles.role` + `.status` | `public.users.is_admin` (boolean) |
| ระดับสิทธิ์ | `admin` · `editor` · `user` × `approved` · `pending` | มี / ไม่มี (2 ระดับ) |
| ผู้ที่ใช้ | ผู้ดูแลหน้าเว็บ (3 บัญชี) | ผู้ใช้ของระบบเรา (198 บัญชี) |
| ใครตรวจ token | `webapi` ผ่าน `auth.getUser()` | `backend` ผ่าน JWT HS256 ของตัวเอง |

**`webapi` รู้จักแต่ตัวตนฝั่ง Supabase** — `auth.mjs` ไม่เคยแตะ `public.users` เลย
และนั่นคือช่องว่างที่งานนี้ต้องออกแบบวิธีข้าม

### 1.1 ⚠ สองตารางชื่อ `public.user_profiles` ที่ไม่ใช่ตารางเดียวกัน

| | Supabase | **ของเรา** |
|---|---|---|
| หน้าที่ | **สิทธิ์** | **ความชอบของนักเรียน** |
| คอลัมน์ | `user_id` · `role` · `status` · `full_name` · `email` | `user_id` · `education_level` · `field_of_study` · `current_role` · `career_goal` · `skills` · `interests` · `language_preference` · `metadata` |

`current_role` ของเราคือ *"ตำแหน่งงานปัจจุบันของนักเรียน"* **ไม่ใช่ role เชิงสิทธิ์**
ห้ามเขียน query หรือ migration ที่สมมติว่าสองตารางนี้คืออันเดียวกัน

---

## 2. Supabase identity schema summary

**ที่มา**: `docs/SUPABASE_LIVE_VERIFICATION.md` (ตรวจ production จริงผ่าน Supabase MCP
`read_only=true` · 32 คำสั่ง) — **ไม่ได้ตรวจซ้ำในรอบนี้** เพราะไม่มีสิทธิ์เข้าถึง

### 2.1 `auth.users` — 3 แถว

| metric | ค่า |
|---|---:|
| users ทั้งหมด | **3** |
| ยืนยันอีเมลแล้ว | **3** |
| ยังไม่ยืนยันอีเมล | 0 |
| ถูกแบน / soft deleted | 0 / 0 |
| เคยเข้าสู่ระบบ | 3 |
| SSO users | **0** |
| anonymous users | **0** |

**ทั้ง 3 บัญชีมีอีเมลและยืนยันแล้ว** ไม่มีบัญชีที่ล็อกอินด้วยเบอร์โทรหรือแบบไม่ระบุตัวตน
→ อีเมลใช้เป็นกุญแจได้สำหรับข้อมูลชุดนี้

### 2.2 `public.user_profiles` — 3 แถว

| คอลัมน์ | ชนิด | null? | default |
|---|---|---|---|
| `id` | uuid | NO | `gen_random_uuid()` |
| `user_id` | uuid | YES | — |
| `role` | varchar(50) | YES | `'user'` |
| `full_name` | varchar(255) | YES | — |
| `created_at` · `updated_at` | timestamptz | YES | `now()` |
| **`email`** | **text** | **YES** | — |
| `status` | varchar(20) | NO | `'approved'` |

| role / status | จำนวน | `user_id` NULL |
|---|---:|---:|
| `admin` / `approved` | **2** | 0 |
| `user` / `approved` | **1** | 0 |

**ไม่พบ `editor` เลย** แม้ policy ครึ่งระบบจะอ้างถึง role นี้

### 2.3 ความเชื่อมโยง

```
profile ที่จับคู่ auth.users ได้      3 / 3
profile กำพร้า                       0
auth user ที่ไม่มี profile            0
```

### 2.4 ⚠ anomaly ที่กระทบการออกแบบ

`user_profiles_user_id_fkey` ชี้ **`user_profiles(user_id)` กลับตัวเอง** ไม่ได้ชี้
`auth.users(id)` → เป็น constraint ที่ผ่านได้เสมอโดยไม่ตรวจอะไร
ตอนนี้ยังไม่เกิดผลเสีย (จับคู่ครบ 3/3) **แต่หมายความว่าฐานข้อมูลไม่ได้บังคับว่า
`user_profiles.user_id` ต้องเป็น auth user ที่มีอยู่จริง** — การออกแบบ mapping
จึงต้องไม่พึ่งพา FK นั้นเป็นหลักประกัน

### 2.5 คอลัมน์ที่ใช้เป็นกุญแจได้ — ฝั่ง Supabase

| ตัวเลือก | ใช้ได้ไหม | เหตุผล |
|---|---|---|
| `auth.users.id` (uuid) | **ไม่ได้ข้ามระบบ** | สร้างแยกกันคนละฐาน ไม่มีความสัมพันธ์กับ `public.users.id` |
| `auth.users.email` | **ได้** | ทั้ง 3 บัญชีมีและยืนยันแล้ว · Supabase บังคับ unique ที่ชั้น auth |
| `user_profiles.email` | **สำรอง** | nullable และเป็นสำเนา — ถ้าไม่ตรงกับ `auth.users.email` จะเกิดสองความจริง |
| `user_profiles.full_name` | **ไม่ได้** | ไม่ unique |
| username | **ไม่มีคอลัมน์นี้** | — |
| external identity | **ไม่มี** | ไม่มีคอลัมน์ที่เก็บ id ของระบบอื่น |

**ต้องใช้ `auth.users.email` เป็นแหล่งความจริง ไม่ใช่ `user_profiles.email`**
เพราะตัวแรกเป็นของระบบ auth ที่ผู้ใช้ล็อกอินด้วยจริง

---

## 3. PostgreSQL identity schema summary

**ตรวจเองในรอบนี้ แบบ `SELECT` อย่างเดียว** — ไม่ดึงอีเมลหรือ UUID ออกมาแม้แถวเดียว

### 3.1 `public.users` — โครงสร้างจริงจาก catalog

```
id, email, password_hash, full_name, is_active, is_admin, created_at, updated_at
```

| | |
|---|---|
| `email` ชนิด | **`citext`** → เทียบแบบไม่สนตัวพิมพ์ในฐานอยู่แล้ว |
| unique index | **2** (PK บน `id` + UNIQUE บน `email`) |
| **คอลัมน์ external identity** | **ไม่มีเลย** — ยืนยันด้วย query บน `pg_attribute` ที่ค้น `supabase\|external\|provider\|oauth\|sub$` |

### 3.2 ตัวเลขจริง

| metric | ค่า |
|---|---:|
| `users` ทั้งหมด | **198** |
| มีอีเมล (ไม่ NULL ไม่ว่าง) | **198** |
| **distinct normalized email hash** | **198** |
| **duplicate normalized hash** | **0** |
| แถวที่ค่าเปลี่ยนหลัง normalize | **2** |
| `is_admin = true` | **1** |
| `is_active = false` | **0** |
| `web` schema | **ยังไม่มี** (ยืนยันซ้ำว่า 005 ยังไม่ apply) |

### 3.3 ข้อสรุปสำคัญจากฝั่งนี้

**normalized email ไม่ซ้ำเลย 198/198** → การเทียบข้ามระบบจากฝั่งนี้
**ให้ผลได้แค่ 0 หรือ 1 เท่านั้น ไม่มีทางเป็น AMBIGUOUS**

พิสูจน์แล้วจากข้อมูลจริง ไม่ใช่อนุมานจาก UNIQUE constraint — เพราะ `citext` UNIQUE
กันซ้ำแบบไม่สนตัวพิมพ์อยู่แล้ว แต่ไม่ได้กันช่องว่างหัวท้าย ซึ่ง `btrim` จัดการ

### 3.4 ⚠ การ normalize จำเป็นจริง — กระทบ 2 แถว

มี **2 แถวที่เก็บอีเมลด้วยตัวพิมพ์ใหญ่** เพราะ `citext` ทำให้ฐานเทียบไม่สนตัวพิมพ์
คนกรอกจึงใส่ตัวพิมพ์ใหญ่ได้โดยไม่มีอะไรฟ้อง **แต่ `digest()` สนตัวพิมพ์**

→ **ถ้าฝั่ง Supabase hash อีเมลดิบโดยไม่ `lower()` สองแถวนี้จะจับคู่ไม่เจอตลอดไป**
และผลจะออกมาเป็น `NO_MATCH` ซึ่งอ่านผิดเป็น *"ไม่มีบัญชีนี้ในระบบเรา"*

ทั้งสองฝั่ง **ต้องใช้ `lower(btrim(email))` เหมือนกันเป๊ะ**

---

## 4. Privacy-safe verification methodology

### 4.1 หลักที่ใช้

```
อีเมลจริงไม่เคยออกจากฐานข้อมูลที่มันอยู่
แต่ละฝั่งคำนวณ SHA-256 ภายในฐานตัวเอง  แล้วเทียบกันแค่ hash
ไม่ SELECT อีเมลออกมา hash ที่ฝั่ง client
```

### 4.2 ฝั่ง PostgreSQL — ยืนยันแล้ว

| | |
|---|---|
| `pgcrypto` | ติดตั้งอยู่ · **schema `public`** → เรียก `digest()` ได้โดยไม่ต้องระบุ schema |
| ทดสอบความถูกต้อง | `encode(digest(lower(btrim('  Test@Example.COM  ')),'sha256'),'hex')` = `973dfe46…13b` ซึ่งเท่ากับ SHA-256 ของ `test@example.com` ที่เป็นค่าอ้างอิงสาธารณะ → **ผ่าน** |
| **ไม่ enable extension** | ใช้ของที่ติดตั้งอยู่แล้ว |
| **ไม่เปลี่ยน `search_path`** | `pgcrypto` อยู่ใน `public` ซึ่งอยู่ใน path ปกติแล้ว |

พิสูจน์กับค่าอ้างอิงภายนอก **ไม่ใช่แค่ consistent กับตัวเอง** — ถ้าทดสอบด้วยการ hash
ค่าเดียวกันสองครั้งแล้วเทียบกัน ก็จะผ่านแม้ฟังก์ชันคำนวณผิด

### 4.3 ชุดคำสั่งที่ใช้ (ฝั่งเรา · รันแล้ว)

```sql
-- READ-ONLY · คืนแต่จำนวน ไม่มีอีเมล ไม่มี uuid ไม่มี hash ของผู้ใช้จริง
SELECT count(*)                                                          AS users_total,
       count(*) FILTER (WHERE email IS NOT NULL AND btrim(email::text) <> '') AS with_email,
       count(DISTINCT encode(digest(lower(btrim(email::text)),'sha256'),'hex'))  AS distinct_hash,
       count(*) - count(DISTINCT encode(digest(lower(btrim(email::text)),'sha256'),'hex'))
                                                                          AS duplicate_hash
FROM public.users;
```

### 4.4 ~~⚠ ฝั่ง Supabase — STOP~~ → **ปิดแล้ว 2026-10-03**

> **ปิดแล้ว** — เจ้าของเปิด session ที่มี Supabase MCP แล้วรันให้ ผลอยู่ใน
> `B1_SUPABASE_IDENTITY_VERIFICATION.md` (live MCP · `read_only=true` · `SELECT` 3 คำสั่ง)
>
> | | |
> |---|---|
> | `auth_users` | **3** · มีอีเมลครบ **3** |
> | `distinct_normalized_email_hash` | **3** · duplicate **0** |
> | `digest()` อยู่ schema | **`extensions`** → ต้องเรียก `extensions.digest(...)` |
> | บัญชีที่มีสิทธิ์ | **2** — S1 และ S2 ทั้งคู่ `admin`/`approved` |
> | ผู้เขียนเดิม | **S2** · `same_account` = true · ตัดสินด้วย full SHA-256 ภายใน SQL |
>
> ข้อความเดิมด้านล่างเก็บไว้เป็นบันทึกว่าตอนนั้นติดอะไร

#### บันทึกเดิม (2026-10-02)

คำสั่งระบุ *"ถ้า digest unavailable: STOP สำหรับ database นั้น ห้าม SELECT raw email
ออกมา hash local"*

**สถานะจริงคือหนักกว่านั้น — เข้าถึงฐานข้อมูลไม่ได้เลย**

| ข้อตรวจ | ผล |
|---|---|
| `.mcp.json` ในรีโปนี้ | **ไม่มีไฟล์** |
| Supabase MCP tool ใน session | **ไม่มี** |
| `supabase` CLI | **ไม่ได้ติดตั้งในเครื่อง** |
| ที่ตั้งค่าไว้จริง | `D:\workspace\LastProject\.mcp.json` → server `supabase` · `type: http` · URL มี `read_only=true` · **ไม่มี token ฝังไว้** (OAuth ต้องล็อกอินแบบ interactive) |

**ไม่ได้หาทางอ้อม** — ใช้ anon key ยิง PostgREST ขัดคำสั่งเดิมของเจ้าของ
(*"ห้ามใช้ anon key เพื่อ bypass Member access"*) และ `auth.users` ไม่ได้เปิดผ่าน
PostgREST อยู่แล้ว · **ไม่ SELECT อีเมลออกมา hash เองที่ client** ตามที่สั่ง

#### `digest()` ฝั่ง Supabase มีไหม — **มีหลักฐานแต่ยังไม่ยืนยัน**

`SUPABASE_LIVE_VERIFICATION.md` บรรทัด 181 บันทึกผล `list_extensions` ว่า
**`pgcrypto 1.3` ติดตั้งอยู่** แต่ไฟล์นั้น **ไม่ได้ระบุ schema ของ pgcrypto**
(ระบุไว้แต่ `vector` ว่าอยู่ใน `public`)

→ โดยค่าตั้งต้นของ Supabase `pgcrypto` อยู่ใน schema `extensions` ซึ่งทำให้ต้องเรียก
`extensions.digest(...)` **แต่ข้อนี้ยังไม่ได้ยืนยันด้วยการรัน** จึงถือเป็น UNVERIFIED

---

## 5. Aggregate counts

| | Supabase | PostgreSQL |
|---|---|---|
| auth user count | **3** | **198** |
| users with email | **3** | **198** |
| distinct normalized email hash | **3** ✅ | **198** |
| duplicate normalized hash | **0** ✅ | **0** |

**ยืนยันครบทั้งสองฝั่งแล้ว** (ฝั่ง Supabase ปิดเมื่อ 2026-10-03)
→ **collision เป็นศูนย์ทั้งสองทิศทาง** จำนวนที่จับคู่ได้ต่อหนึ่ง hash เป็นได้แค่ **0 หรือ 1**
**ambiguity เป็นไปไม่ได้** ไม่ใช่แค่ "ยังไม่เจอ"

## 6. Cross-system match results

| metric | ค่า |
|---|---|
| `matched_hash_count` (เฉพาะบัญชีที่มีสิทธิ์) | **1** — S1 เท่านั้น |
| Supabase-only (บัญชีที่มีสิทธิ์ที่ไม่มีคู่) | **1** — **S2** |
| PostgreSQL-only | 197 (ไม่เกี่ยวกับ Supabase) |

**ตรวจเสร็จแล้ว** — ดู `B1_ACTIVE_USER_MAPPING_FINAL_DECISION.md` ข้อ 1.3

### 6.1 หลักฐานชิ้นเดียวที่มีอยู่ — เจ้าของแจ้งไว้ในรอบ B2

> *"historical author email hash ไม่มี match ใน production `public.users`"*

| | |
|---|---|
| ชั้นของหลักฐาน | **OWNER-SUPPLIED** — ผมไม่ได้ตรวจเอง |
| บอกอะไร | **มี Supabase account อย่างน้อย 1 บัญชีที่ `NO_MATCH`** |
| บัญชีนั้นเป็นบัญชีที่มีสิทธิ์ไหม | **น่าจะใช่แต่ยังไม่ยืนยัน** — บัญชีนั้นสร้างเนื้อหาใน `courses`/`news` ซึ่ง RLS ยอมให้เขียนเฉพาะ `role IN ('admin','editor')` จึงเป็นบัญชีที่มีสิทธิ์ ณ เวลาที่เขียน · แต่ role ของบัญชีนั้น **ตอนนี้** อาจเปลี่ยนไปแล้ว |
| ไม่รู้อะไร | อีก 2 บัญชีจับคู่ได้หรือไม่ |

**ข้อนี้มีน้ำหนักต่อการจัดชั้นสุดท้าย** — ดูข้อ 20

### 6.2 ⚠ ข้อควรระวังเรื่องวิธี hash ของหลักฐานข้อ 6.1

ยังไม่ยืนยันว่า query ที่เจ้าของรันใช้ `lower(btrim(email))` ตามที่กำหนด
ถ้าใช้อีเมลดิบ ผล `NO_MATCH` อาจเป็นผลบวกลวง — **ฝั่งเรามี 2 แถวที่เก็บด้วย
ตัวพิมพ์ใหญ่** (ข้อ 3.4) ซึ่งเป็นกลุ่มที่พลาดได้พอดี

ควรยืนยันข้อนี้ก่อนตัดสินใจถาวร (ดูข้อ 19 · N1)

## 7. Privileged account match results

บัญชีที่สนใจ: `role IN ('admin','editor')` AND `status = 'approved'` → **2 บัญชี**
(จาก Live Verification: admin/approved 2 · user/approved 1 · ไม่มี editor)

| label | role | status | hash prefix | postgres_match_count | classification |
|---|---|---|---|---|---|
| **S1** | `admin` | `approved` | `66067ef9e155` | **1** | **`EXACT_MATCH`** · match เป็น admin + active |
| **S2** | `admin` | `approved` | `716e6e356eae` | **0** | **`NO_MATCH`** · เป็นผู้เขียนเดิม |
| S3 | `user` | `approved` | — | ไม่ได้ตรวจ | ไม่อยู่ในกลุ่มที่สนใจ (ไม่ผ่านระดับ EDITOR) |

**ตรวจเสร็จแล้ว** · ตัดสินด้วย **full SHA-256 ภายใน SQL** ไม่ใช่ prefix
`self_test_pipeline` ผ่าน → `0` ของ S2 ไม่ใช่ผลลบลวง

> **ไม่ output** อีเมล · UUID · ชื่อ ของบัญชีใด ๆ · label `S1`–`S3` เป็นชื่อสมมติที่
> **ยังไม่ผูกกับบัญชีจริง** เพราะยังไม่ได้ดึงข้อมูลมาเลย

### 7.1 ชุดคำสั่งที่พร้อมรัน — ฝั่ง Supabase

```sql
-- READ-ONLY · คืน hash prefix ไม่คืนอีเมล ไม่คืน uuid
-- ถ้า digest อยู่ใน schema extensions ให้ใช้ extensions.digest(...)
SELECT
  row_number() OVER (ORDER BY p.role, p.created_at)        AS label_seq,
  p.role,
  p.status,
  left(encode(digest(lower(btrim(u.email)), 'sha256'), 'hex'), 12) AS email_hash_prefix
FROM auth.users u
JOIN public.user_profiles p ON p.user_id = u.id
WHERE u.email IS NOT NULL
ORDER BY p.role, p.created_at;
```

```sql
-- นับรวมเพื่อเทียบกับข้อ 5
SELECT count(*)                                              AS auth_users,
       count(u.email)                                        AS with_email,
       count(DISTINCT encode(digest(lower(btrim(u.email)),'sha256'),'hex')) AS distinct_hash
FROM auth.users u;
```

### 7.2 ชุดคำสั่งที่พร้อมรัน — ฝั่งเรา (รับ hash prefix เข้ามาเทียบ)

```sql
-- READ-ONLY · คืนแต่จำนวนกับ is_admin ไม่คืนอีเมล ไม่คืน uuid
SELECT count(*) AS postgres_match_count,
       bool_or(is_admin) AS any_match_is_admin
FROM public.users
WHERE left(encode(digest(lower(btrim(email::text)),'sha256'),'hex'), 12)
      = '<email_hash_prefix>';
```

⚠ **prefix 12 ตัวมีโอกาสชนกันได้** ตอนตัดสินใจจริงต้องเทียบ hash เต็ม 64 ตัว
prefix ใช้เพื่อ **รายงาน** ไม่ใช่เพื่อ **ตัดสิน**

---

## 8. Identity uniqueness analysis

| | Supabase | PostgreSQL |
|---|---|---|
| อีเมล unique ไหม | **ใช่** — Supabase บังคับที่ชั้น auth | **ใช่** — `citext NOT NULL UNIQUE` |
| normalize แล้วยังไม่ซ้ำไหม | **ยังไม่ยืนยัน** | **ยืนยันแล้ว 198/198** |
| uuid ใช้ข้ามระบบได้ไหม | **ไม่ได้** — ไม่มีความสัมพันธ์กัน | **ไม่ได้** |
| ชื่อ unique ไหม | **ไม่** | **ไม่** · และ 177/198 เป็น NULL |
| มี external identity column | **ไม่มี** | **ไม่มี** |

### 8.1 ผลต่อความเป็น deterministic

```
ฝั่งเรา normalized hash ไม่ซ้ำ 198/198
   -> จำนวนที่จับคู่ได้ต่อหนึ่ง Supabase account เป็นได้แค่ 0 หรือ 1
   -> AMBIGUOUS (>1) เป็นไปไม่ได้จากฝั่งเรา

ที่เหลือจึงเป็นแค่สองกรณี
   EXACT_MATCH (1)   mapping เป็น deterministic
   NO_MATCH (0)      ต้องให้เจ้าของตัดสิน
```

**นี่เป็นผลที่ดี** — ตัดความเป็นไปได้ที่แย่ที่สุด (`MAPPING_BLOCKED_BY_IDENTITY_AMBIGUITY`)
ออกไปได้ด้วยหลักฐาน ไม่ใช่ด้วยการสมมติ

---

## 9. Option A — Runtime normalized-email mapping

```
Supabase token -> auth.getUser() -> email -> lower(btrim(email))
               -> SELECT id FROM public.users WHERE email = <normalized>   (ทุกคำขอที่เขียน)
```

| มิติ | ประเมิน |
|---|---|
| **determinism** | **ดี** ถ้าอีเมลตรงกัน · `citext` ทำให้เทียบไม่สนตัวพิมพ์ให้เอง |
| **security** | **อ่อนที่สุดในสามทาง** — ใครที่ควบคุมอีเมลในระบบ Supabase ได้ จะกลายเป็นผู้ใช้ฝั่งเราคนนั้นทันทีโดยไม่ต้องรู้รหัสผ่านฝั่งเรา · **อีเมลกลายเป็นหนังสือเดินทางข้ามระบบ** |
| **PII exposure** | **แย่** — อีเมลจริงต้องเดินทางจาก Supabase เข้า `webapi` **ทุกคำขอ** และมีโอกาสหลุดเข้า log ได้ตลอด (`auth.mjs` ตั้งใจไม่เก็บอีเมลไว้ใน context เลย — ทางนี้ทำลายหลักนั้น) |
| **performance** | `auth.getUser()` + query `public.users` ทุกคำขอที่เขียน · index บน `email` มีอยู่แล้วจึงเร็ว แต่เพิ่มอีกหนึ่ง round trip |
| **operational complexity** | **ต่ำสุด** — ไม่ต้องแก้ schema ไม่ต้องมีตารางใหม่ |
| **migration complexity** | **ต่ำสุด** — ไม่มี migration |
| **ถ้าอีเมลเปลี่ยน** | **พังเงียบ ๆ** — ผู้ใช้เดิมกลายเป็น `NO_MATCH` ทันที งานเขียนทั้งหมดถูกปฏิเสธโดยไม่มีใครรู้ว่าเพราะอะไร |
| **ถ้าบัญชี Supabase ถูกลบ** | ไม่กระทบแถวเก่า (`created_by` ยังชี้ `public.users` ที่ยังอยู่) · บัญชีนั้นเขียนอะไรไม่ได้อีก |
| **Path 3 compatibility** | **ปานกลาง** — เมื่อตัด Supabase Auth แล้วไม่มีอะไรเหลือเป็นร่องรอยว่าใครคือใคร |

**ข้อเสียที่หนักที่สุด**: ไม่มีบันทึกว่าการจับคู่เกิดขึ้นเมื่อไหร่และอิงอะไร
ทุกคำขอตัดสินใหม่จากค่าที่เปลี่ยนได้

## 10. Option B — Explicit identity mapping table

```
identity_mappings
  auth_provider     เช่น 'supabase'
  external_user_id  auth.users.id ของ Supabase
  local_user_id     public.users.id
  created_at
  (UNIQUE (auth_provider, external_user_id) · UNIQUE (auth_provider, local_user_id))
```

| มิติ | ประเมิน |
|---|---|
| **determinism** | **ดีที่สุด** — จับคู่ด้วย uuid ที่ **บันทึกไว้แล้ว** ไม่ใช่คำนวณใหม่ทุกครั้ง |
| **security** | **ดี** — การจับคู่เกิดขึ้นครั้งเดียวอย่างตั้งใจ แล้วถูกตรึงไว้ · อีเมลเปลี่ยนภายหลังไม่ทำให้ตัวตนย้าย |
| **PII exposure** | **ดีที่สุด** — ตารางเก็บแต่ uuid สองตัว **ไม่มีอีเมลเลย** · อีเมลใช้แค่ตอนสร้างแถวครั้งแรก |
| **performance** | query เดียวด้วย uuid ที่มี index · เร็วกว่า Option A |
| **operational complexity** | **สูงสุด** — ต้องมีขั้นตอน/หน้าจอสำหรับสร้างแถว และต้องมีคนตัดสินว่าจับคู่ใครกับใคร |
| **migration complexity** | ต้องมี migration 006 สร้างตาราง |
| **ถ้าอีเมลเปลี่ยน** | **ไม่กระทบเลย** — ข้อดีที่ชัดที่สุด |
| **ถ้าบัญชี Supabase ถูกลบ** | แถว mapping ค้างอยู่ชี้ไป external id ที่ไม่มีแล้ว · ต้องมีนโยบายเก็บกวาด (หรือเก็บไว้เป็นประวัติโดยเจตนา) |
| **Path 3 compatibility** | **ดีที่สุด** — เป็นตารางที่รองรับผู้ให้บริการ auth หลายรายและเก็บประวัติการจับคู่ไว้ |

**ข้อเสีย**: ซับซ้อนเกินความจำเป็นสำหรับ **2 บัญชีที่มีสิทธิ์** ในวันนี้ และมีตาราง
ที่ต้องดูแลเพิ่ม

## 11. Option C — External identity column

```
ALTER TABLE public.users ADD COLUMN supabase_user_id UUID UNIQUE;   -- ยังไม่ทำ
```

| มิติ | ประเมิน |
|---|---|
| **determinism** | **ดีที่สุด** เท่า Option B — จับคู่ด้วย uuid ที่บันทึกไว้ |
| **security** | **ดี** เท่า Option B · `UNIQUE` กันไม่ให้สอง Supabase account ชี้ผู้ใช้เดียวกัน |
| **PII exposure** | **ดี** — เก็บแต่ uuid ไม่เก็บอีเมล |
| **performance** | **ดีที่สุด** — query เดียวบนตารางเดียว ไม่ต้อง join |
| **operational complexity** | **ต่ำกว่า B** — ไม่มีตารางใหม่ ไม่มีความสัมพันธ์ใหม่ |
| **migration complexity** | ต้องมี migration 006 (`ADD COLUMN` + index) — เบากว่าการสร้างตาราง |
| **ถ้าอีเมลเปลี่ยน** | **ไม่กระทบเลย** |
| **ถ้าบัญชี Supabase ถูกลบ** | ค่าค้างอยู่ในคอลัมน์ · ตั้งเป็น NULL ได้โดยไม่กระทบอะไรอื่น **ง่ายกว่า B** |
| **Path 3 compatibility** | **ปานกลาง** — ผูกกับผู้ให้บริการรายเดียว ถ้าวันหนึ่งมีหลายราย ต้องย้ายไปเป็นตารางแบบ B |

**ข้อเสีย**: สมมติว่าจะมีผู้ให้บริการ auth รายเดียวตลอดไป · และเติมคอลัมน์ให้ผู้ใช้
198 คนที่ส่วนใหญ่ไม่เกี่ยวกับ Supabase เลย (ค่าจะเป็น NULL 196 แถว)

---

## 12. Security analysis

### 12.1 เทียบความเสี่ยงหลักของสามทาง

| ความเสี่ยง | A | B | C |
|---|---|---|---|
| ควบคุมอีเมลฝั่ง Supabase แล้วสวมรอยเป็นผู้ใช้ฝั่งเรา | **เสี่ยง ทุกคำขอ** | เสี่ยงแค่ตอนสร้าง mapping | เสี่ยงแค่ตอนตั้งค่าคอลัมน์ |
| อีเมลหลุดเข้า log | **เสี่ยง** | ต่ำ | ต่ำ |
| สองตัวตนชี้ผู้ใช้เดียวกัน | ไม่เกิด (อีเมล unique) | กันด้วย UNIQUE | กันด้วย UNIQUE |
| การจับคู่เปลี่ยนโดยไม่มีใครรู้ | **เกิดได้** | ไม่เกิด | ไม่เกิด |
| ตรวจย้อนหลังได้ว่าจับคู่เมื่อไหร่ | **ไม่ได้** | ได้ (`created_at`) | ได้บางส่วน |

### 12.2 เรื่องที่ทั้งสามทางต้องทำเหมือนกัน

```
ห้ามใช้ Supabase uuid เป็น created_by โดยตรง       FK จะปฏิเสธ หรือชี้ผิดคน
ห้ามเชื่อ created_by / updated_by จาก request body  stripAuthorFields ทำแล้ว
ห้าม fallback ไป admin หรือผู้ใช้คนแรก              ยัดเจ้าของผิดคน
ห้าม NULL สำหรับข้อมูลใหม่                          ปนกับความหมายของแถว legacy
```

### 12.3 สิ่งที่ `auth.mjs` ทำไว้แล้วและต้องไม่ถอย

`auth.mjs` **ตั้งใจไม่เก็บอีเมลไว้ใน auth context เลย** — context มีแค่
`{ authenticated, userId, role, status }` และ `describeForLog()` มีข้อตรวจคุ้มว่า
**ไม่มี uuid ไม่มีอีเมล ไม่มี token** ในบรรทัด log

Option A ต้องดึงอีเมลเข้ามาใน context → **ทำลายหลักนั้น**
Option B/C ไม่ต้อง → รักษาไว้ได้

---

## 13. Email-change analysis

สถานการณ์: ผู้ดูแลเปลี่ยนอีเมลใน Supabase หลังจากเริ่มใช้ระบบไปแล้ว

| | Option A | Option B / C |
|---|---|---|
| ทันทีหลังเปลี่ยน | `NO_MATCH` → เขียนข้อมูลไม่ได้ | ไม่กระทบ ยังจับคู่ได้ |
| อาการที่ผู้ใช้เห็น | "บันทึกไม่สำเร็จ" ทุกครั้งโดยไม่มีคำอธิบาย | ไม่มีอาการ |
| แก้ได้อย่างไร | ต้องไปแก้อีเมลฝั่งเราให้ตรง — **ซึ่งเป็นการแก้ข้อมูลผู้ใช้เพื่อให้ระบบทำงาน** ไม่ใช่ทางที่ดี | ไม่ต้องทำอะไร |
| ความเสี่ยงที่ซ่อนอยู่ | ถ้ามีคนอื่นมาใช้อีเมลเดิมในภายหลัง **จะได้ตัวตนของคนเก่าไป** | ไม่เกิด |

**ข้อสุดท้ายเป็นข้อที่ตัดสิน Option A ออกจากการเป็นทางเลือกหลัก** — การผูกตัวตน
ไว้กับค่าที่ผู้ใช้เปลี่ยนเองได้ และที่คนอื่นอาจมาใช้ต่อ เป็นรากฐานที่ไม่มั่นคง

---

## 14. Path 3 compatibility

Path 3 = ตัด Supabase Auth แล้วใช้ตัวตนฝั่ง PostgreSQL ชุดเดียว

| | Option A | Option B | Option C |
|---|---|---|---|
| ตอนตัด Supabase Auth | ไม่มีอะไรต้องย้าย **แต่ก็ไม่มีอะไรเหลือเป็นร่องรอย** | ตารางกลายเป็นประวัติว่าใครเคยเป็นใคร — **มีค่า** | คอลัมน์กลายเป็นร่องรอยเดียวกัน |
| ต้องย้ายผู้ใช้ 3 คนไปฝั่งเราไหม | ใช่ ทุกทาง | ใช่ | ใช่ |
| รู้ว่าใครคือใครตอนย้าย | **ต้องเทียบอีเมลใหม่อีกครั้ง** | **รู้อยู่แล้วจากตาราง** | **รู้อยู่แล้วจากคอลัมน์** |
| รองรับผู้ให้บริการ auth หลายราย | ไม่ | **ใช่** | ไม่ (ต้องย้ายเป็นตาราง) |
| เก็บคอลัมน์/ตารางไว้หลังตัดได้ไหม | — | ได้ เป็นประวัติ | ได้ แต่ชื่อคอลัมน์จะล้าสมัย |

---

## 15. Recommended Phase 1 design

# **Option C เป็นหลัก + ขั้นเติมค่าแบบ B ครั้งเดียว**

```
migration 006 (ยังไม่ทำ)
    ALTER TABLE public.users ADD COLUMN supabase_user_id UUID;
    CREATE UNIQUE INDEX ... ON public.users (supabase_user_id) WHERE supabase_user_id IS NOT NULL;

ขั้นเติมค่าครั้งเดียว (ยังไม่ทำ · ต้องขออนุมัติแยก)
    เทียบ email hash ตามข้อ 7.1/7.2  ->  ได้คู่ที่ EXACT_MATCH
    เจ้าของยืนยันทีละคู่               ->  UPDATE supabase_user_id ของแถวนั้น
    คู่ที่ NO_MATCH                    ->  ไม่เติม  บัญชีนั้นเขียนข้อมูลไม่ได้

runtime (ยังไม่ทำ)
    auth.getUser(token) -> supabase uuid
    SELECT id FROM public.users WHERE supabase_user_id = <supabase uuid>
    ไม่เจอ -> FAIL CLOSED
```

### 15.1 ทำไมเลือก C ไม่ใช่ A

| | |
|---|---|
| อีเมลเป็นค่าที่เปลี่ยนได้และนำกลับมาใช้ได้ | ผูกตัวตนไว้กับมันตลอดกาลไม่มั่นคง (ข้อ 13) |
| A บังคับให้อีเมลเดินทางเข้า `webapi` ทุกคำขอ | ทำลายหลักที่ `auth.mjs` ตั้งไว้ว่า context ไม่เก็บอีเมล (ข้อ 12.3) |
| A ไม่มีร่องรอยว่าจับคู่เมื่อไหร่อิงอะไร | ตรวจย้อนหลังไม่ได้ |

### 15.2 ทำไมเลือก C ไม่ใช่ B

| | |
|---|---|
| วันนี้มีผู้ให้บริการ auth **รายเดียว** | ตารางที่รองรับหลายรายเป็นความซับซ้อนที่ยังไม่มีใครใช้ |
| บัญชีที่มีสิทธิ์มี **2 บัญชี** | ตารางแยกพร้อม FK สองทางเกินความจำเป็น |
| คำสั่ง *"ห้าม overfit to 3 users"* ยังถูกเคารพ | คอลัมน์ `UNIQUE` รองรับผู้ใช้เพิ่มเท่าไหร่ก็ได้ · **ไม่มี hardcode uuid หรืออีเมลในโค้ด** |
| ถ้าวันหนึ่งมีหลายผู้ให้บริการ | ย้ายจากคอลัมน์ไปเป็นตารางแบบ B ได้ และตอนนั้นจะมีเหตุผลรองรับจริง |

### 15.3 อีเมลใช้แค่ครั้งเดียว ไม่ใช้ตอน runtime

**จุดสำคัญของข้อเสนอนี้** — email hash ใช้เพื่อ **หา** คู่ที่ถูกต้องครั้งแรกเท่านั้น
หลังจากนั้นระบบใช้ uuid ที่บันทึกไว้ → ได้ความแน่นอนของ B/C โดยไม่เสียความง่าย
ของการใช้อีเมลเป็นตัวช่วยค้นหา

### 15.4 ⚠ ไม่ใช่ข้อสรุปสุดท้าย

ข้อเสนอนี้อิงหลักฐานที่ยังไม่ครบ — **ยังไม่รู้ว่าบัญชีที่มีสิทธิ์ทั้ง 2 จับคู่ได้หรือไม่**
ถ้าทั้งสองเป็น `NO_MATCH` ขั้นเติมค่าจะไม่มีอะไรให้เติม และต้องตัดสินใจเรื่องอื่นก่อน
(ดูข้อ 19)

---

## 16. Author write contract

**ออกแบบไว้ ยังไม่ implement**

### 16.1 CREATE

```
1. ตรวจสิทธิ์ตาม B1 foundation (EDITOR ขึ้นไป)
2. resolveLocalUserId(context)  ->  public.users.id
      ไม่สำเร็จ -> FAIL CLOSED  ไม่เขียนอะไรเลย
3. stripAuthorFields(body)      ->  ตัด created_by / updated_by ที่ผู้เรียกส่งมา
4. created_by = local user id
   updated_by = local user id
```

### 16.2 UPDATE

```
1. ตรวจสิทธิ์ตาม B1 foundation
2. resolveLocalUserId(context)  ->  ไม่สำเร็จ -> FAIL CLOSED
3. stripAuthorFields(body)
4. updated_by = local user id
   created_by  ***ไม่แตะเลย***  ไม่อยู่ใน SET clause ด้วยซ้ำ
```

### 16.3 ทำไม `created_by` ต้องไม่อยู่ใน `SET` ของ UPDATE เลย

แถว legacy มี `created_by = NULL` ซึ่งหมายความว่า *"ยังแมปผู้เขียนเดิมไม่ได้"*
ถ้า UPDATE เขียนค่าลงไป ความหมายจะกลายเป็น *"คนที่เพิ่งมาแก้เป็นคนสร้าง"* ซึ่งไม่จริง

**การไม่ใส่คอลัมน์ใน `SET` เลย ปลอดภัยกว่าการใส่แล้วตั้งค่าให้เท่าเดิม** เพราะอย่างหลัง
ยังมีช่องให้พลาดได้ถ้าโค้ดสร้าง SET clause แบบ dynamic

### 16.4 สิ่งที่มีอยู่แล้วใน `webapi/auth.mjs`

```js
stripAuthorFields(payload)   // ทำงานแล้ว มีข้อตรวจคุ้ม
resolveAuthorId()            // ปฏิเสธเสมอ พร้อมรหัส B1_ACTIVE_USER_MAPPING_REQUIRED
authorFieldsFor(mode, ctx)   // create: ทั้งสองคอลัมน์ · update: แค่ updated_by
                             // ตอนนี้คืน ok:false ทุกครั้ง
```

**รูปร่างของ contract อยู่ในโค้ดแล้ว** เหลือแต่ให้ `resolveAuthorId` ทำงานได้
เมื่อมี mapping — **ไม่ต้องแก้โครงอื่น**

---

## 17. Fail-closed behavior

### 17.1 เมื่อหา local user ไม่ได้

```
ปฏิเสธคำขอ  ไม่เขียนข้อมูลใด ๆ แม้บางส่วน
```

**ห้ามทำทั้งสี่อย่างนี้**

```
created_by = NULL สำหรับข้อมูลใหม่    ปนกับความหมายของแถว legacy
fallback ไป admin                      ยัดเจ้าของผิดคน
fallback ไปผู้ใช้คนแรก                 ยัดเจ้าของผิดคน
ใช้ Supabase uuid โดยตรง               FK ปฏิเสธ หรือชี้ผิดคน
```

### 17.2 HTTP behavior ที่เสนอ

| สถานการณ์ | รหัสที่เสนอ | เหตุผล |
|---|---|---|
| ไม่มี token / token ใช้ไม่ได้ | **401** | เหมือน B1 foundation ไม่เปลี่ยน |
| ล็อกอินแล้วแต่สิทธิ์ไม่พอ | **403** | เหมือน B1 foundation |
| **ล็อกอินแล้ว สิทธิ์พอ แต่หา local user ไม่ได้** | **409 Conflict** | ผู้เรียกไม่ได้ทำอะไรผิด และแก้ด้วยการส่งคำขอใหม่ไม่ได้ · ไม่ใช่ 403 เพราะสิทธิ์ไม่ใช่ปัญหา · ไม่ใช่ 500 เพราะระบบไม่ได้พัง — เป็นสถานะที่ต้องให้ผู้ดูแลจัดการ |
| body | `{"error":"Account is not linked"}` | ไม่บอกอีเมล ไม่บอก uuid ไม่บอกวิธีจับคู่ |
| log | `บัญชีนี้ยังไม่ได้จับคู่ — role=admin status=approved` | **ไม่มี uuid ไม่มีอีเมล** ตามหลักของ `describeForLog()` |

**ทางเลือกที่พิจารณาแล้วไม่เลือก**: `403` (สื่อว่าสิทธิ์ไม่พอ ซึ่งผิด) ·
`500` (สื่อว่าระบบพัง ซึ่งผิดและทำให้ไม่มีใครไปแก้ต้นเหตุ) ·
`422` (สื่อว่าข้อมูลที่ส่งมาผิด ซึ่งผิด)

### 17.3 ต้องเห็นได้ว่าเกิดขึ้น

ถ้า fail closed แล้วเงียบ ผู้ดูแลจะเจอแต่ "บันทึกไม่สำเร็จ" โดยไม่มีใครรู้สาเหตุ
→ ควรมีทางให้เห็นว่ามีบัญชีที่ยังไม่ได้จับคู่ (เช่น นับใน `/healthz` หรือ log ที่ชัด)
**ยังไม่ออกแบบรายละเอียดในรอบนี้** แต่บันทึกไว้ว่าเป็นส่วนที่ขาดไม่ได้

---

## 18. Required code / schema changes — DESIGN ONLY

**ยังไม่ทำอะไรเลยในรอบนี้**

| # | สิ่งที่ต้องทำ | ที่ไหน | ขออนุมัติแยก |
|---|---|---|---|
| 1 | `ALTER TABLE public.users ADD COLUMN supabase_user_id UUID` + partial unique index | **migration 006 ใหม่** — **ไม่ใช่แก้ 005** | ✓ |
| 2 | ข้อตรวจของคอลัมน์ใหม่ (nullable · unique เฉพาะที่ไม่ NULL · ไม่กระทบ 198 แถวเดิม) | `eval/` | ✓ |
| 3 | `resolveAuthorId()` ให้ query `supabase_user_id` แทนการปฏิเสธเสมอ | `webapi/auth.mjs` | ✓ |
| 4 | `webapi` ต้องต่อ PostgreSQL ได้ (ตอนนี้ยังไม่มี `DATABASE_URL`) | `docker-compose.prod.yml` + `webapi/` | ✓ |
| 5 | ขั้นเติมค่า `supabase_user_id` ครั้งเดียว โดยเจ้าของยืนยันทีละคู่ | สคริปต์แยก | ✓ |
| 6 | พฤติกรรม 409 + log ที่เห็นได้ | `webapi/` | ✓ |

### 18.1 ข้อ 4 เป็นงานที่ยังไม่มีใครพูดถึง

`webapi` วันนี้ **ไม่เคยต่อ PostgreSQL เลย** — `docker-compose.prod.yml` ให้แต่
`VITE_SUPABASE_URL` และ `VITE_SUPABASE_ANON_KEY` ไม่มี `DATABASE_URL`

→ ไม่ว่าจะเลือก design ไหน **ต้องเพิ่มการเชื่อมต่อฐานข้อมูลให้ `webapi` ก่อน**
ซึ่งเป็นงานที่ต้องตัดสินใจเรื่อง role ที่ใช้ (`advisor_api` ตาม GRANT ของ 005) และ
การจัดการรหัสผ่านใน env

**ไม่ได้ทำในรอบนี้** และไม่ได้อยู่ในรายการที่คำสั่งคาดไว้ จึงรายงานเพิ่ม

---

## 19. Remaining blockers

| # | Blocker | ระดับ | สถานะ |
|---|---|---|---|
| ~~**M1**~~ | ~~ผลเทียบ hash ฝั่ง Supabase~~ | — | ✅ **RESOLVED** 2026-10-03 — `B1_SUPABASE_IDENTITY_VERIFICATION.md` |
| ~~**M2**~~ | ~~`digest()` ฝั่ง Supabase อยู่ schema ไหน~~ | — | ✅ **RESOLVED** — **`extensions`** · ไม่ enable extension ไม่เปลี่ยน search_path |
| ~~**N1**~~ | ~~hash ของรอบ B2 ใช้ `lower(btrim(email))` ไหม~~ | — | ✅ **RESOLVED** — ใช้เหมือนกันทั้งสองฝั่ง · **`NO_MATCH` ของ S2 ยืนหยัด** |
| **M3** | **`webapi` ยังต่อ PostgreSQL ไม่ได้** | สูง | ต้องเพิ่ม `DATABASE_URL` และตัดสินใจเรื่อง role · ดูข้อ 18.1 |
| ~~**M4**~~ | ~~S2 ยังต้องเขียนข้อมูลใหม่หลัง cutover หรือไม่~~ | — | ✅ **ปิดแล้ว 2026-10-03** — เจ้าของเลือก **A**: ใช้ S1 บัญชีเดียว ไม่ provision ให้ S2 → `M4_RESOLVED_DESIGN_READY` |
| **S2-PRIV** | **S2 ยังมีสิทธิ์ `admin` เต็มบน Supabase** | **กลาง** | ข้อใหม่จากการตัดสินใจ — ทางเลือก A ไม่ได้ลดสิทธิ์บน Supabase · ดู Final Decision ข้อ 14.0.1 |
| **R1** | `createSupabaseVerifier` ยังไม่เคยคุยกับ Supabase จริง | สูง | ค้างจากรอบ B1 foundation |
| **R6** | ครึ่งหนึ่งของงาน B1 อยู่ในรีโปหน้าเว็บที่ยังไม่อนุมัติให้แก้ | สูง | ค้างจากรอบ B1 foundation |

### 19.1 ที่ปิดได้แล้วในรอบนี้

```
ฝั่ง PostgreSQL ยืนยันครบ        198 แถว · normalized hash ไม่ซ้ำ 198 · duplicate 0
                                 digest() ใช้ได้ ทดสอบกับค่าอ้างอิงภายนอกผ่าน
                                 ไม่มีคอลัมน์ external identity (ยืนยันจาก catalog)
AMBIGUOUS เป็นไปไม่ได้จากฝั่งเรา  ตัดกรณีที่แย่ที่สุดออกได้ด้วยหลักฐาน
Design options เทียบครบ 3 ทาง     9 มิติต่อทาง พร้อมข้อเสนอและเหตุผล
Author write contract             ออกแบบครบ · รูปร่างอยู่ในโค้ดแล้ว
Fail-closed behavior              เสนอ 409 พร้อมเหตุผลที่ไม่เลือก 403/500/422
```

---

## 20. Final classification

# ~~`MAPPING_REQUIRES_OWNER_DECISION`~~ → **`M4_RESOLVED_DESIGN_READY`** ✅

> **ปรับปรุง 2026-10-03** — ดูเหตุผลเต็มใน
> `B1_ACTIVE_USER_MAPPING_FINAL_DECISION.md` ข้อ 14

### 20.1 เงื่อนไขทั้งสามข้อ — ตรวจครบแล้ว

| เงื่อนไข | สถานะ |
|---|---|
| normalized email unique ทั้งสองฝั่ง | ✅ **ครบ** — Supabase 3/3 · production 198/198 · duplicate 0 ทั้งคู่ |
| privileged users มี exact match | ⚠ **S1 ใช่ (1) · S2 ไม่ (0)** |
| ไม่มี ambiguity | ✅ **ยืนยันทั้งสองฝั่ง** — และ **เป็นไปไม่ได้** ที่จะกำกวม |

ข้อกลางคือเหตุที่ยังไม่เป็น `DESIGN_READY` — **S2 คือบัญชีที่เขียนเนื้อหา 100%
ของระบบมาตลอด และยังล็อกอินได้** ถ้าจัดเป็นพร้อมจะกลบข้อเท็จจริงนั้น

### 20.2 ทำไมไม่ใช่ `MAPPING_BLOCKED_BY_IDENTITY_AMBIGUITY`

**ไม่มี ambiguity** — ฝั่งเรา normalized hash ไม่ซ้ำเลย 198/198 ทำให้
`postgres_match_count > 1` เป็นไปไม่ได้ **พิสูจน์จากข้อมูลจริง**

### 20.3 ทำไมเป็น `M4_ACTIVE_USER_PROVISIONING_REQUIRED`

**S2 ถูก verify แล้วว่าไม่มี PostgreSQL counterpart** และยังเป็น `admin`/`approved`
ที่ล็อกอินได้วันนี้ → ถ้าพยายามเขียนข้อมูลใหม่หลัง cutover จะ FAIL CLOSED ทุกครั้ง

สิ่งที่พลิกสถานะนี้คือการตัดสินใจของเจ้าของข้อเดียว: **S2 ยังต้องเขียนข้อมูลหรือไม่**
ถ้าไม่ต้อง → `M4_RESOLVED_DESIGN_READY` ทันทีโดยไม่ต้องทำอะไรเพิ่ม

ทางเลือกที่ไม่ขัดข้อห้าม (ถ้าคำตอบคือ "ต้อง") อยู่ใน Final Decision ข้อ 14.4

### 20.4 `B1_ACTIVE_USER_MAPPING_REQUIRED` = **`true`**

**ไม่เปลี่ยนเป็น `false`** ตามหมายเหตุที่คำสั่งระบุไว้ — design ไม่เท่ากับ implementation
และในกรณีนี้ design เองก็ยังไม่สมบูรณ์เพราะหลักฐานไม่ครบ

`resolveAuthorId()` ยังปฏิเสธเสมอ · `authorFieldsFor()` ยังคืน `ok: false` ทุกครั้ง ·
**ยังไม่มี write endpoint ใดในระบบ**

---

## บันทึกการเข้าถึงข้อมูลในรอบนี้

| ระบบ | การเข้าถึง | คำสั่ง |
|---|---|---|
| PostgreSQL (production) | **อ่านอย่างเดียว** | `SELECT` ล้วน 1 ชุด — นับจำนวน · นับ hash ที่ไม่ซ้ำ · อ่าน catalog · ทดสอบ `digest()` ด้วยค่าตัวอย่าง |
| Supabase | **ไม่ได้เข้าถึงเลยในรอบ 2026-10-02** | ปิดในรอบ 2026-10-03 ด้วย live MCP read-only — ดู `B1_SUPABASE_IDENTITY_VERIFICATION.md` |
| ข้อมูลที่ดึงออกมา | จำนวนเต็ม · ชื่อชนิดข้อมูล · ชื่อ schema · ชื่อคอลัมน์ · boolean | **ไม่มีอีเมล ไม่มี uuid ไม่มีชื่อ ไม่มี hash ของผู้ใช้จริง** |
| คำสั่งเขียน / DDL | **ไม่มีแม้คำสั่งเดียว** | |

---

## STOP

**`M4_RESOLVED_DESIGN_READY`** · **`B1_ACTIVE_USER_MAPPING_REQUIRED = true`**

> **เอกสารนี้ถูกแทนที่บางส่วนแล้ว** — ข้อสรุปและรายการที่รอการตัดสินใจล่าสุดอยู่ใน
> **`docs/B1_ACTIVE_USER_MAPPING_FINAL_DECISION.md`**

ปิดแล้ว: ~~M1~~ · ~~M2~~ · ~~N1~~ · ~~S1 UNKNOWN~~

เหลือ

1. ~~**M4**~~ — ✅ ปิดแล้ว เจ้าของเลือก **A**
2. **อนุมัติ Option C** หรือไม่
3. **M3** — ให้ `webapi` ต่อ PostgreSQL ด้วย role ไหน และจัดการรหัสผ่านอย่างไร
4. **R1** — ยืนยัน `createSupabaseVerifier` กับ Supabase จริงเมื่อใด
5. **อนุมัติเขียนรีโปหน้าเว็บ**
6. **HTTP 409** สำหรับกรณีจับคู่ไม่ได้ เหมาะไหม

```
INSERT/UPDATE/DELETE  NONE   CREATE/ALTER/DROP/DDL  NONE   Production Write  NONE
Supabase Write        NONE   Create User            NONE   Create Mapping    NONE
Apply Migration 005   NONE   Data Migration         NONE   write endpoints   NONE
แก้ frontend          NONE   Deploy / Restart       NONE   Commit / Push     NONE
Merge main            NONE   implement mapping      NONE
```
