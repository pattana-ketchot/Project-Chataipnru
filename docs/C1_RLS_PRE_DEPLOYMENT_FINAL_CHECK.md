# C1 — ตรวจแก้ครั้งสุดท้ายก่อนลงมือ

> **READ-ONLY** — ไม่ apply migration · ไม่ `GRANT`/`REVOKE` · ไม่แก้ policy จริง · ไม่สร้างบัญชี · ไม่เปลี่ยน `role`/`status` · ไม่ deploy · ไม่ restart · ไม่ push/merge

| รายการ | ค่า |
|---|---|
| วันที่ | 11 ตุลาคม 2569 |
| แก้ไขจาก | `C1_RLS_SECURITY_FINAL_DECISION.md` |
| สถานะ | **`GO` แบบมีเงื่อนไข** — เหลือ **เก็บค่าฐานก่อนแก้** 4 ข้อ |
| ปรับปรุง | 11 ต.ค. 2569 — ผลตรวจชื่อฟังก์ชัน · ขั้นตอนเก็บค่าฐาน · ลำดับตรวจหลัง migration |

---

## อ่านแบบเร็ว — สรุปภาษาง่าย ๆ

### รอบนี้ทำอะไร

ทบทวนงานของตัวเองอีกครั้ง แล้ว **พบว่าเขียนผิดไป 3 จุด** จึงแก้ให้ตรงกับความจริง

### ผิดตรงไหนบ้าง

**ผิดที่ 1 — เขียนขัดกันเอง**
บอกว่า "รอบนี้ไม่มีการให้หรือถอนสิทธิ์เลย" แต่ในคำสั่งจริงมีการให้สิทธิ์เรียกใช้ฟังก์ชันใหม่อยู่ 2 บรรทัด · ที่ถูกคือ **ไม่แตะสิทธิ์ของตาราง แต่มีการตั้งสิทธิ์ของฟังก์ชันใหม่ที่สร้างเอง**

**ผิดที่ 2 — มั่นใจเกินหลักฐาน**
เขียนว่าวิธีที่เลือก "ปลอดภัยแน่นอน" เพราะตัวกันที่มีอยู่ใช้วิธีเดียวกัน · ที่ถูกคือ **มีหลักฐานสนับสนุนหนักแน่น แต่บริบทการเรียกใช้ต่างกัน จึงยังต้องทดสอบจริง**

**ผิดที่ 3 — วิธีทดสอบใช้ไม่ได้**
เสนอให้ทดสอบสิทธิ์ด้วยการรันคำสั่งใน SQL Editor ของ Supabase · **ซึ่งใช้พิสูจน์ไม่ได้เลย** เพราะ SQL Editor รันด้วยสิทธิ์สูงที่ข้ามกฎความปลอดภัยทั้งหมด ไม่ว่ากฎจะเป็นอย่างไรก็จะเห็นข้อมูลครบเสมอ · ต้องทดสอบผ่านหน้าเว็บหรือ API จริงเท่านั้น

**และอีกเรื่องที่ประเมินหลวมไป**
เคยบอกว่าทดสอบด้วยบัญชีผู้ดูแลแทนบัญชีผู้แก้ไขได้ · **ที่ถูกคือแทนกันไม่ได้ครบ** ทดสอบผู้ดูแลพิสูจน์ได้แค่ว่าคำว่า `admin` ใช้ได้ ไม่ได้พิสูจน์คำว่า `editor`

### ยังไม่ได้แก้อะไรบน production

**ไม่มีการเปลี่ยนแปลงใด ๆ** เอกสารนี้เป็นการตรวจและแก้เอกสารเท่านั้น

### ความคืบหน้าล่าสุด

**ตรวจชื่อฟังก์ชันแล้ว — ไม่ซ้ำกับของเดิม** จึงหมดความเสี่ยงเรื่องเขียนทับ และหมดความเสี่ยงที่การย้อนกลับจะไปลบของเดิมทิ้ง

### แล้วยังเดินหน้าได้ไหม

**ได้** แต่ยังต้อง **เก็บค่าตั้งต้นก่อนแก้** ด้วยวิธีที่ถูกต้อง ไม่งั้นแก้เสร็จแล้วจะไม่มีอะไรให้เทียบว่าได้ผลจริงหรือไม่

และต้องยอมรับว่าเส้นทางของบัญชีผู้แก้ไขยังไม่ถูกพิสูจน์ (ซึ่งตอนนี้ไม่มีใครใช้อยู่แล้ว)

---

## 1. แก้คำอธิบาย `GRANT` / `REVOKE` ให้ตรงกับ SQL

### 1.1 ข้อความเดิมที่ผิด

เอกสารก่อนหน้าเขียนในตารางความพร้อมว่า

```
| มี GRANT / REVOKE ไหม | ไม่มีเลยในรอบนี้ |
```

**แต่ migration มีจริง 2 บรรทัด**

```sql
revoke all on function public.c1_is_approved_staff() from public, anon;
grant execute on function public.c1_is_approved_staff() to authenticated;
```

### 1.2 ข้อความที่ถูกต้อง

| ขอบเขต | มี `GRANT`/`REVOKE` ไหม | รายละเอียด |
|---|---|---|
| **สิทธิ์ของตาราง `user_profiles`** | **ไม่มีเลย** | ไม่แตะสิทธิ์ของ `anon`, `authenticated`, `service_role` · `TRUNCATE` ที่ค้างอยู่ก็ยังอยู่ (เป็นงานแยก) |
| **สิทธิ์ของฟังก์ชันใหม่ `c1_is_approved_staff()`** | **มี 2 คำสั่ง** | `revoke all ... from public, anon` แล้ว `grant execute ... to authenticated` |
| สิทธิ์ของฟังก์ชันเดิม | **ไม่แตะ** | `guard_user_profile_privileges()` · `handle_new_user()` |

### 1.3 ทำไมฟังก์ชันใหม่ต้องมีสองคำสั่งนี้

PostgreSQL ให้สิทธิ์ `EXECUTE` แก่ `PUBLIC` โดยอัตโนมัติเมื่อสร้างฟังก์ชัน **ถ้าไม่ `revoke` ก่อน `anon` จะเรียกฟังก์ชันนี้ได้**

ฟังก์ชันนี้เป็น `SECURITY DEFINER` ที่อ่าน `user_profiles` ได้โดยข้าม RLS ถ้าปล่อยให้ `anon` เรียกได้ จะกลายเป็นช่องทางใหม่ที่เราสร้างขึ้นเอง — แม้จะคืนแค่ `true`/`false` ก็ยังบอกได้ว่าผู้เรียกเป็นผู้ดูแลหรือไม่

> **ลำดับสำคัญ** — ต้อง `revoke` ก่อน `grant` เสมอ

---

## 2. ป้องกันการเขียนทับฟังก์ชันเดิม

### 2.1 ปัญหาของ `CREATE OR REPLACE`

เอกสารเดิมใช้ `create or replace function public.c1_is_approved_staff()` โดยให้เหตุผลว่าชื่อไม่ชนเพราะพบฟังก์ชันแค่ 2 ตัว

**เหตุผลนั้นอ่อนเกินไป** เพราะคำสั่งที่ใช้ค้นกรองด้วย `ilike '%user_profiles%'` และ `'%truncate%'` ถ้ามีฟังก์ชันชื่อเดียวกันที่ไม่เข้าเงื่อนไขทั้งสอง จะมองไม่เห็น

ถ้าเผลอ `replace` ทับฟังก์ชันที่มีคนใช้อยู่ → **พฤติกรรมเปลี่ยนเงียบ ๆ และ rollback ด้วย `drop function` จะทำลายของเดิมไปเลย**

### 2.2 ตรวจก่อน — รันก่อน migration

```sql
select n.nspname as schema, p.proname, pg_get_userbyid(p.proowner) as owner, p.prosecdef
from pg_proc p join pg_namespace n on n.oid = p.pronamespace
where p.proname = 'c1_is_approved_staff';
```

| ผล | ทำอะไร |
|---|---|
| **ไม่มีแถว** | **ปลอดภัย** — เดินหน้าด้วย `create function` ได้ |
| มีแถว | **หยุด** — เปลี่ยนชื่อฟังก์ชันใหม่ หรือตรวจว่าของเดิมคืออะไรก่อน |

### 2.3 ✅ ผลตรวจ (11 ต.ค. 2569) — ผ่านแล้ว

```sql
select n.nspname as schema, p.proname, pg_get_userbyid(p.proowner) as owner, p.prosecdef
from pg_proc p join pg_namespace n on n.oid = p.pronamespace
where p.proname = 'c1_is_approved_staff';
```

```
Success. No rows returned
```

**ยืนยันว่าไม่มีฟังก์ชันชื่อ `c1_is_approved_staff` ใน schema `public`**

| ผลที่ตามมา | |
|---|---|
| เงื่อนไขตรวจชื่อฟังก์ชันก่อน migration | **ผ่าน** |
| ความเสี่ยงเขียนทับของเดิม | **หมดไป** |
| ความเสี่ยงที่ rollback จะทำลายของเดิม (ข้อ 7.4) | **หมดไป** |
| ใช้ `create function` ต่อไหม | **ใช่ — คงไว้** เพราะถ้ามีใครสร้างชื่อนี้ระหว่างนี้ จะได้ล้มเสียงดังแทนที่จะทับเงียบ |

### 2.4 ใช้ `CREATE` ไม่ใช่ `CREATE OR REPLACE`

```sql
-- ล้มเสียงดังถ้ามีอยู่แล้ว ดีกว่าทับเงียบ ๆ
create function public.c1_is_approved_staff() ...
```

ถ้ามีอยู่แล้วจะได้ `ERROR: function ... already exists` และ transaction ถูกยกเลิกทั้งก้อน — **ล้มแบบปลอดภัย**

---

## 3. Function Ownership และสิทธิ์ `EXECUTE`

### 3.1 ทำไมเจ้าของสำคัญ

`SECURITY DEFINER` รันด้วยสิทธิ์ของ**เจ้าของฟังก์ชัน** การข้าม RLS จึงขึ้นกับว่าเจ้าของเป็นใคร

| เจ้าของเป็น | ผล |
|---|---|
| role เดียวกับเจ้าของตาราง (ปกติ `postgres`) | ข้าม RLS ได้ (เพราะ `rls_forced = false`) |
| role อื่น | ถูก RLS จับ → อาจเกิด recursion |

### 3.2 ตรวจหลังสร้าง — บังคับ

```sql
select
  p.proname,
  pg_get_userbyid(p.proowner)                  as function_owner,
  (select pg_get_userbyid(c.relowner)
     from pg_class c
    where c.oid = 'public.user_profiles'::regclass) as table_owner,
  p.prosecdef                                   as is_security_definer,
  p.proconfig::text                             as config_settings,
  p.proacl::text                                as access_privileges
from pg_proc p
where p.pronamespace = 'public'::regnamespace
  and p.proname = 'c1_is_approved_staff';
```

| สิ่งที่ต้องเห็น | ค่า |
|---|---|
| `function_owner` | **ควรเท่ากับ `table_owner`** |
| `is_security_definer` | `true` |
| `config_settings` | ต้องมี `search_path=pg_catalog, public` |
| `access_privileges` | ต้องมี `authenticated=X/...` และ **ต้องไม่มี** `=X/` ลอย ๆ (ซึ่งหมายถึง `PUBLIC`) และไม่มี `anon=X/` |

### 3.3 ถ้าเจ้าของไม่ตรงกับเจ้าของตาราง

| ทางเลือก | หมายเหตุ |
|---|---|
| สร้างใหม่ด้วยบัญชีที่ถูกต้อง | รันผ่าน Supabase SQL Editor ซึ่งปกติเป็น `postgres` |
| `alter function ... owner to <role>` | **เป็นการเปลี่ยนสิทธิ์ ต้องขออนุมัติแยก** |

---

## 4. ปรับข้อความเรื่อง RLS Recursion

### 4.1 ข้อความเดิมที่มั่นใจเกินหลักฐาน

> ~~"ฟังก์ชันที่เราจะสร้างใช้รูปแบบเดียวกันเป๊ะ จึงปลอดภัยแน่นอน"~~

### 4.2 ข้อความที่ถูกต้อง

> **มีหลักฐานสนับสนุนหนักแน่น แต่บริบทการเรียกใช้ต่างกัน จึงยังต้องพิสูจน์ด้วยการทดสอบ**

### 4.3 หลักฐานที่มี

| หลักฐาน | น้ำหนัก |
|---|---|
| `guard_user_profile_privileges()` เป็น `SECURITY DEFINER` ที่ `SELECT` จาก `public.user_profiles` และ**ทำงานอยู่ทุกวันนี้โดยไม่ recursion** | **สูง** — พิสูจน์ว่ากลไกข้าม RLS ใช้ได้จริงในฐานข้อมูลนี้ |
| `rls_forced = false` ยืนยันแล้ว | สูง |
| ไม่มี view หรือฟังก์ชันอื่นที่อ่านตารางนี้ | กลาง |

### 4.4 ทำไมยังไม่ใช่ "แน่นอน" — ความต่างของบริบท

| | `guard_user_profile_privileges()` | `c1_is_approved_staff()` |
|---|---|---|
| ถูกเรียกจาก | **Trigger** ของ `UPDATE` | **RLS policy ของ `SELECT`** บนตารางเดียวกัน |
| ตอนถูกเรียก ระบบกำลังทำอะไร | ประเมินแถวที่กำลังจะเขียน | **กำลังประเมิน policy เพื่อตัดสินว่าจะอ่านแถวได้ไหม** |
| ถ้าข้าม RLS ไม่สำเร็จ | query ภายในเห็นแถวน้อยลง | **เข้าสู่การประเมิน policy ซ้ำ → recursion** |

**ความต่างนี้มีจริงและสำคัญ** — trigger ทำงาน *หลัง* การตัดสินใจเรื่อง policy แล้ว ส่วนฟังก์ชันใหม่ทำงาน *ระหว่าง* การตัดสินใจนั้น

### 4.5 วิธีพิสูจน์

ทดสอบ **A1 และ U1** ทันทีหลัง apply (ดูข้อ 6)

| ผล | แปลว่า |
|---|---|
| ได้ตัวเลขปกติ | **ไม่มี recursion** ยืนยันแล้ว |
| ขึ้น `infinite recursion detected in policy` | **rollback ทันที** |

> ล้มแบบ**เห็นชัด** ไม่ใช่ความเงียบ · ล้มแบบ**ปิด** คืออ่านไม่ได้ ไม่ใช่อ่านได้หมด · และ**ย้อนได้ทันทีโดยไม่มีข้อมูลเสียหาย**

---

## 5. แยกผลทดสอบ Admin กับ Editor

### 5.1 ข้อความเดิมที่หลวมเกินไป

> ~~"การทดสอบ D1–D4 ด้วย `admin` ครอบคลุมโค้ดเส้นทางเดียวกันกับ E1–E4 แล้ว"~~

### 5.2 ทำไมแทนกันไม่ได้ครบ

policy ใช้นิพจน์ `role in ('admin','editor')`

| ทดสอบด้วย | พิสูจน์อะไร | **ไม่** พิสูจน์อะไร |
|---|---|---|
| `admin` | คำว่า `'admin'` ในรายการใช้ได้ · ฟังก์ชันคืน `true` ให้ผู้ดูแล · policy `select_staff` ทำงาน | **คำว่า `'editor'` ในรายการใช้ได้หรือไม่** |
| `editor` | คำว่า `'editor'` ใช้ได้ | — |

นอกจากนี้ **เส้นทางในหน้าเว็บอาจต่างกัน** — หน้าที่ `editor` เข้าได้กับที่ `admin` เข้าได้ไม่ใช่ชุดเดียวกันทั้งหมด การทดสอบด้วย `admin` จึงไม่ได้เดินผ่านโค้ดเดียวกันทุกบรรทัด

### 5.3 สถานะที่ถูกต้อง

| ชุดทดสอบ | สถานะ |
|---|---|
| **A** (anonymous) | ทำได้ |
| **U** (user ทั่วไป) | ทำได้ |
| **D** (admin) | ทำได้ |
| **M** (M3 WebAPI) | ทำได้ |
| **E** (editor) | **`BLOCKED — NO TEST ACCOUNT`** · **ไม่มีชุดใดทดแทนได้** |

### 5.4 ความเสี่ยงที่ยอมรับถ้าไม่ทดสอบ E

| ประเด็น | ประเมิน |
|---|---|
| มีผู้ใช้ที่กระทบวันนี้ไหม | **ไม่มี** — ยืนยันแล้วว่าไม่มีบัญชี `editor` ในระบบ |
| ความน่าจะเป็นที่ `'editor'` ใช้ไม่ได้ทั้งที่ `'admin'` ใช้ได้ | **ต่ำ** — เป็นรายการค่าคงที่ในนิพจน์เดียว แต่ **"ต่ำ" ไม่เท่ากับ "ศูนย์"** |
| ถ้าผิดจะรู้เมื่อไร | เมื่อสร้างบัญชี `editor` คนแรก |
| ย้อนกลับได้ไหม | ได้ทันที |

> **ต้องทดสอบ E1–E5 ทันทีที่มีบัญชี `editor` คนแรก** — บันทึกเป็นงานค้างที่ผูกกับเหตุการณ์ ไม่ใช่กับวันที่

---

## 6. วิธีทดสอบ RLS ที่ถูกต้อง — แก้ข้อผิดพลาดสำคัญ

### 6.1 ข้อผิดพลาดเดิม

เอกสารก่อนหน้าเสนอให้รันคำสั่งนี้ใน **Supabase SQL Editor** เพื่อวัดจำนวนแถวที่แต่ละบทบาทเห็น

```sql
select count(*) as rows_visible from public.user_profiles;
```

**วิธีนี้พิสูจน์อะไรไม่ได้เลย**

| เหตุผล | รายละเอียด |
|---|---|
| SQL Editor รันด้วย role สิทธิ์สูง | ปกติคือ `postgres` ซึ่งเป็นเจ้าของตาราง |
| เจ้าของตารางข้าม RLS เมื่อ `rls_forced = false` | **ซึ่งยืนยันแล้วว่าเป็น `false`** |
| ผลที่ได้ | **เห็นทุกแถวเสมอ ไม่ว่า policy จะเป็นอย่างไร** |
| `auth.uid()` ใน SQL Editor | เป็น `NULL` เพราะไม่มี JWT ของผู้ใช้ |

> ถ้าใช้วิธีนี้ จะได้ตัวเลขเท่าเดิมทั้งก่อนและหลังแก้ แล้วสรุปผิดว่า "การแก้ไม่ได้ผล" หรือแย่กว่านั้นคือสรุปว่า "ยังอ่านได้อยู่ ต้อง rollback" ทั้งที่ระบบทำงานถูกต้อง

### 6.2 SQL Editor ใช้ทำอะไรได้

| ใช้ได้ | ใช้ไม่ได้ |
|---|---|
| ดู policy ที่มี (`pg_policies`) | **พิสูจน์ว่า anon อ่านได้หรือไม่** |
| ดูสิทธิ์และเจ้าของฟังก์ชัน | **พิสูจน์ว่าผู้ใช้ทั่วไปเห็นกี่แถว** |
| ดู trigger และนิยามฟังก์ชัน | **วัดผลของ RLS ใด ๆ** |
| รัน migration | |

### 6.3 วิธีที่ถูกต้อง — ผ่าน PostgREST ด้วยบริบทจริง

**ที่มาของ anon key** — Supabase Dashboard → Settings → API → `anon public` **ไม่ต้องไปดึงจาก JavaScript ของหน้าเว็บ**

#### ทดสอบในฐานะ `anon`

```bash
read -rsp 'ANON_KEY: ' ANON && echo
read -rp  'PROJECT_REF: ' REF

curl -s -D - -o /dev/null \
  -H "apikey: $ANON" \
  -H "Authorization: Bearer $ANON" \
  -H "Prefer: count=exact" \
  "https://$REF.supabase.co/rest/v1/user_profiles?select=user_id&limit=0" \
  | grep -i '^content-range'
```

| ส่วนประกอบ | ทำไมใช้แบบนี้ |
|---|---|
| `limit=0` | **ไม่ดึงข้อมูลแถวกลับมาเลย** |
| `Prefer: count=exact` | จำนวนมาในส่วนหัว `Content-Range` |
| `select=user_id` | ถึงจะหลุดมาก็ไม่ใช่ `email` หรือ `full_name` |
| `read -rsp` | คีย์ไม่ขึ้นบนจอ |

**ผลที่ต้องได้**

| เวลา | `Content-Range` |
|---|---|
| ก่อนแก้ | `*/<จำนวนผู้ใช้ทั้งหมด>` |
| **หลังแก้** | **`*/0`** |

#### ทดสอบในฐานะผู้ใช้ที่ล็อกอิน

ใช้ access token ของบัญชีนั้นแทนในส่วน `Authorization` โดย `apikey` ยังเป็น anon key

```bash
read -rsp 'ACCESS_TOKEN: ' TK && echo

curl -s -D - -o /dev/null \
  -H "apikey: $ANON" \
  -H "Authorization: Bearer $TK" \
  -H "Prefer: count=exact" \
  "https://$REF.supabase.co/rest/v1/user_profiles?select=user_id&limit=0" \
  | grep -i '^content-range'

unset TK
```

#### ทางเลือกที่ง่ายกว่า — ผ่าน Console ของเบราว์เซอร์

เปิดหน้าเว็บด้วยบัญชีที่ต้องการทดสอบ (หรือหน้าต่างส่วนตัวสำหรับ `anon`) แล้วที่แท็บ Console

```js
const r = await fetch('/rest/v1/user_profiles?select=user_id&limit=0', {
  headers: { Prefer: 'count=exact' }
});
console.log('count =', r.headers.get('content-range'));
```

> ใช้ได้ถ้าโดเมนมี proxy ไปที่ Supabase · ถ้าไม่มีให้ใช้วิธี `curl` ข้างบน

### 6.4 ตารางผลที่ต้องได้ — ฉบับแก้แล้ว

| # | บริบท | วิธีวัด | ก่อนแก้ | หลังแก้ |
|---|---|---|---|---|
| **A1** | `anon` | PostgREST + anon key | จำนวนผู้ใช้ทั้งหมด | **`0`** |
| **U1** | user ทั่วไป | PostgREST + token ของเขา | ทั้งหมด | **`1`** |
| **D1** | admin | PostgREST + token ของ admin | ทั้งหมด | **ทั้งหมด (คงเดิม)** |
| **E1** | editor | — | — | ⛔ `BLOCKED` |
| **M2** | M3 | `/healthz` | — | `dbConfigured=true` |

> **ห้ามใช้ SQL Editor วัดข้อ A1, U1, D1, E1** — ดูเหตุผลข้อ 6.1

---

### 6.5 ขั้นตอนเก็บค่าฐาน A1 · U1 · D1 — ทำก่อน apply

#### สิ่งที่ต้องมีก่อน

| # | ต้องมี | ได้จากไหน | มีแล้วหรือยัง |
|---|---|---|---|
| 1 | `PROJECT_REF` | Supabase Dashboard → Settings → API → Project URL | ต้องเตรียม |
| 2 | `ANON_KEY` | Dashboard → Settings → API → **`anon` `public`** | ต้องเตรียม |
| 3 | access token ของ **admin** | ล็อกอิน `/admin/login` แล้วดึงจาก Console | ต้องเตรียม |
| 4 | access token ของ **ผู้ใช้ทั่วไป** | ต้องมีบัญชี `role='user'` | **ต้องตรวจก่อนว่ามีไหม** |

> **ห้ามดึง anon key จาก JavaScript ของหน้าเว็บ** — ใช้จาก Dashboard ซึ่งเป็นแหล่งที่ถูกต้อง

#### ตรวจก่อนว่ามีบัญชีให้ทดสอบครบไหม

```sql
-- คืนเฉพาะ role, status และจำนวนนับ ไม่มีข้อมูลผู้ใช้
select role, status, count(*) as total
from public.user_profiles
group by role, status
order by role, status;
```

| ถ้าเห็น | แปลว่า |
|---|---|
| มีแถว `user` อย่างน้อย 1 | **ทดสอบ U1 ได้** (ต้องรู้ว่าล็อกอินบัญชีนั้นได้) |
| ไม่มีแถว `user` เลย | **U1 ถูกบล็อกเหมือน E1** — บันทึกไว้ อย่าข้ามเงียบ ๆ |
| มีแถว `admin` + `approved` | ทดสอบ D1 ได้ |

#### วิธีดึง access token โดยไม่ให้โผล่บนจอ

ที่ Console ของเบราว์เซอร์ขณะล็อกอินด้วยบัญชีที่ต้องการ

```js
copy(JSON.parse(Object.entries(localStorage).find(([k])=>k.startsWith('sb-')&&k.endsWith('-auth-token'))[1]).access_token)
```

จะขึ้น `undefined` ซึ่งปกติ — คลิปบอร์ดได้ token แล้ว

#### สคริปต์เก็บค่าฐาน

```bash
read -rp  'PROJECT_REF: ' REF
read -rsp 'ANON_KEY: '    ANON && echo

probe() {
  # $1 = ชื่อข้อ  $2 = token ที่ใช้ใน Authorization
  local out status range
  out=$(curl -s -D - -o /tmp/c1body.txt \
        -H "apikey: $ANON" \
        -H "Authorization: Bearer $2" \
        -H "Prefer: count=exact" \
        "https://$REF.supabase.co/rest/v1/user_profiles?select=user_id&limit=0")
  status=$(printf '%s' "$out" | head -1 | awk '{print $2}')
  range=$(printf '%s' "$out" | grep -i '^content-range' | tr -d '\r' | awk '{print $2}')
  printf '%-4s HTTP=%-4s Content-Range=%-12s body_bytes=%s\n' \
         "$1" "${status:-?}" "${range:-ไม่มี}" "$(wc -c < /tmp/c1body.txt)"
}

probe A1 "$ANON"          # anonymous
read -rsp 'USER_TOKEN: '  TKU && echo; probe U1 "$TKU"; unset TKU
read -rsp 'ADMIN_TOKEN: ' TKA && echo; probe D1 "$TKA"; unset TKA

rm -f /tmp/c1body.txt; unset ANON
```

| กลไกป้องกัน | ทำอะไร |
|---|---|
| `limit=0` | **ไม่ดึงข้อมูลแถวกลับมาเลย** |
| `Prefer: count=exact` | จำนวนมาในส่วนหัว ไม่ใช่ในเนื้อ |
| `select=user_id` | ถึงหลุดมาก็ไม่ใช่ `email` หรือ `full_name` |
| `read -rsp` | คีย์และ token ไม่ขึ้นบนจอ ไม่เข้า history |
| รายงาน `body_bytes` แทนเนื้อ | ยืนยันว่าไม่มีข้อมูลกลับมาโดยไม่ต้องแสดงเนื้อ |
| `unset` + `rm` | ไม่ทิ้งค่าไว้ |

#### ตารางบันทึกค่าฐาน

| ข้อ | บริบท | HTTP | `Content-Range` | `body_bytes` |
|---|---|---|---|---|
| A1 | anon | ______ | ______ | ______ |
| U1 | user | ______ | ______ | ______ |
| D1 | admin | ______ | ______ | ______ |

**ก่อนแก้ ทั้งสามข้อควรได้ `HTTP 200` และตัวเลขหลัง `/` ใน `Content-Range` เท่ากันทั้งหมด** เพราะ policy ปัจจุบันเปิดให้ทุกคนอ่าน

### 6.6 อ่านผลให้ถูก — จุดที่เข้าใจผิดได้ง่าย

| สิ่งที่เห็น | ความหมาย | ถูกต้องไหมหลังแก้ |
|---|---|---|
| `HTTP 200` + `Content-Range: */0` | **RLS ปฏิเสธทุกแถว** — ไม่มีข้อมูลกลับมา | **นี่คือผลที่ต้องการสำหรับ A1** |
| `HTTP 200` + `Content-Range: */<N>` | อ่านได้ `N` แถว | ถูกสำหรับ U1 (`N=1`) และ D1 (`N` เท่าค่าฐาน) |
| `HTTP 401` | ไม่มี `apikey` หรือ token ไม่ถูกต้อง | **ไม่ใช่ผลของ RLS** — แก้คำสั่งก่อนสรุป |
| `HTTP 403` + `permission denied for table` | **ไม่มี `GRANT` ระดับตาราง** | ไม่ควรเกิด เพราะรอบนี้ไม่แตะสิทธิ์ตาราง |
| `HTTP 500` + `infinite recursion detected in policy` | **recursion** | **rollback ทันที** |

> **จุดที่พลาดง่ายที่สุด** — `HTTP 200` ไม่ได้แปลว่า "ยังอ่านได้อยู่" ต้องดู `Content-Range` ด้วย · RLS ที่ปฏิเสธทุกแถวให้ `200` พร้อมผลลัพธ์ว่าง **ไม่ใช่ `403`**

---

## 7. Rollback — ตรวจว่าคืนสภาพได้ครบ

### 7.1 สิ่งที่ต้องคืน

| รายการ | migration ทำอะไร | rollback ต้องทำอะไร |
|---|---|---|
| `SELECT` policy เดิม | `drop policy "Public profiles are viewable by everyone"` | **สร้างคืนให้เหมือนเดิมทุกคำ** |
| policy ใหม่ 2 ตัว | `create policy c1_...` | `drop policy` ทั้งสอง |
| ฟังก์ชันใหม่ | `create function c1_is_approved_staff()` | `drop function` |
| **สิทธิ์ของฟังก์ชันใหม่** | `revoke all ... from public, anon` แล้ว `grant execute ... to authenticated` | **หายไปพร้อมฟังก์ชันอัตโนมัติ** — `drop function` ลบ ACL ไปด้วย |
| สิทธิ์ของตาราง | **ไม่แตะ** | **ไม่ต้องคืน** |
| `UPDATE` policy · trigger · ฟังก์ชันเดิม | **ไม่แตะ** | **ไม่ต้องคืน** |

### 7.2 Rollback ฉบับแก้แล้ว

```sql
-- คืนสภาพเดิมทั้งหมดของรอบ C1
-- ⚠ การ rollback = เปิดช่องโหว่ R1 กลับมา ใช้ชั่วคราวเท่านั้น

begin;

drop policy if exists c1_user_profiles_select_own   on public.user_profiles;
drop policy if exists c1_user_profiles_select_staff on public.user_profiles;

-- คืน policy เดิมแบบคำต่อคำจากผลตรวจจริง
create policy "Public profiles are viewable by everyone"
  on public.user_profiles
  as permissive
  for select
  to public
  using (true);

-- ลบฟังก์ชันที่รอบนี้สร้าง — ACL ของมันหายไปด้วยโดยอัตโนมัติ
drop function if exists public.c1_is_approved_staff();

commit;
```

### 7.3 ตรวจหลัง rollback

```sql
-- 1) policy เดิมกลับมาและเป็น permissive to public
select policyname, permissive, roles::text, qual
from pg_policies
where schemaname='public' and tablename='user_profiles' and cmd='SELECT';
-- ต้องได้ 1 แถว · roles = {public} · qual = true

-- 2) ฟังก์ชันของรอบนี้ถูกลบแล้ว
select count(*) from pg_proc
where pronamespace='public'::regnamespace and proname='c1_is_approved_staff';
-- ต้องได้ 0

-- 3) ของเดิมยังครบ
select policyname from pg_policies
where schemaname='public' and tablename='user_profiles' and cmd='UPDATE';
-- ต้องได้ 2 แถว

select tgname from pg_trigger
where tgrelid='public.user_profiles'::regclass and not tgisinternal order by tgname;
-- ต้องได้ guard_user_profile_privileges_trigger และ update_user_profiles_updated_at
```

จากนั้นยืนยันด้วย **A1 ผ่าน PostgREST** ว่ากลับมาอ่านได้ตามเดิม

### 7.4 กรณีที่ rollback ทำลายของเดิมได้

**ถ้าใช้ `create or replace` แล้วฟังก์ชันชื่อนั้นมีอยู่ก่อน** → `drop function` ตอน rollback จะลบของเดิมทิ้ง

**ป้องกันด้วยข้อ 2** — ตรวจก่อนและใช้ `create` ไม่ใช่ `create or replace`

---

### 7.5 ลำดับการตรวจหลัง Migration — ทำตามลำดับนี้

> ขั้นที่ 1–2 รันใน **SQL Editor** ได้ เพราะเป็นการดู metadata ไม่ใช่การวัด RLS
> ขั้นที่ 3 เป็นต้นไป **ต้องผ่าน PostgREST เท่านั้น**

### ขั้นที่ 1 — ตรวจฟังก์ชันที่เพิ่งสร้าง

```sql
select
  p.proname,
  pg_get_userbyid(p.proowner)                       as function_owner,
  (select pg_get_userbyid(c.relowner)
     from pg_class c where c.oid='public.user_profiles'::regclass) as table_owner,
  p.prosecdef                                       as is_security_definer,
  p.provolatile                                     as volatility,
  p.proconfig::text                                 as config_settings,
  p.proacl::text                                    as access_privileges
from pg_proc p
where p.pronamespace='public'::regnamespace and p.proname='c1_is_approved_staff';
```

| ช่อง | ต้องได้ | ถ้าไม่ตรง |
|---|---|---|
| `function_owner` | **เท่ากับ `table_owner`** | ดูข้อ 3.3 — อาจเกิด recursion |
| `is_security_definer` | `true` | ฟังก์ชันไม่ข้าม RLS → recursion |
| `volatility` | `s` (stable) | ไม่ร้ายแรง แต่ช้ากว่าที่ควร |
| `config_settings` | มี `search_path=pg_catalog, public` | **หยุด** — เสี่ยงถูกสวม search_path |
| `access_privileges` | มี `authenticated=X/` · **ไม่มี** `anon=X/` · **ไม่มี** `=X/` ที่ขึ้นต้นด้วยเครื่องหมายเท่ากับลอย ๆ | **หยุด** — `anon` หรือ `PUBLIC` เรียกฟังก์ชันได้ |

> `proacl` ที่ขึ้นต้นด้วย `=X/` หมายถึงให้สิทธิ์แก่ `PUBLIC` ซึ่ง**ต้องไม่มี**หลังจาก `revoke all ... from public, anon`

### ขั้นที่ 2 — ตรวจ policy และของเดิมที่ต้องไม่หาย

```sql
-- 2.1 ต้องไม่เหลือ policy ที่เปิดให้อ่าน
select policyname, cmd, permissive, roles::text, qual
from pg_policies
where schemaname='public' and tablename='user_profiles' and cmd in ('SELECT','ALL');
-- ต้องเห็นเฉพาะ c1_user_profiles_select_own และ c1_user_profiles_select_staff
-- ต้องไม่มีแถวใดที่ qual = 'true'

-- 2.2 UPDATE policy เดิมต้องครบ 2 ตัว
select policyname from pg_policies
where schemaname='public' and tablename='user_profiles' and cmd='UPDATE';

-- 2.3 trigger ต้องครบ 2 ตัว
select tgname from pg_trigger
where tgrelid='public.user_profiles'::regclass and not tgisinternal order by tgname;

-- 2.4 ฟังก์ชันเดิมต้องยังอยู่
select proname from pg_proc
where pronamespace='public'::regnamespace
  and proname in ('guard_user_profile_privileges','handle_new_user');
```

### ขั้นที่ 3 — วัด RLS จริงผ่าน PostgREST

รัน `probe` ตามข้อ 6.5 อีกครั้งด้วย token ชุดเดิม แล้วเทียบกับค่าฐาน

| ข้อ | ค่าฐาน | หลังแก้ต้องได้ |
|---|---|---|
| **A1** | `*/<ทั้งหมด>` | **`*/0`** |
| **U1** | `*/<ทั้งหมด>` | **`*/1`** |
| **D1** | `*/<ทั้งหมด>` | **`*/<ทั้งหมด>` เท่าค่าฐาน** |

### ขั้นที่ 4 — ตรวจระบบที่ใช้งานจริง

| # | ทดสอบ | ต้องได้ |
|---|---|---|
| 1 | ล็อกอิน `/admin/login` ด้วยบัญชี admin | เข้าได้ |
| 2 | `/admin/users` แสดงรายชื่อ | จำนวนแถวเท่าค่าฐาน |
| 3 | รายการเนื้อหาแสดงชื่อผู้สร้าง/ผู้แก้ไข | เห็นเหมือนเดิม |
| 4 | หน้าสาธารณะ (แรก · หลักสูตร · เปรียบเทียบ · แชท) | ใช้ได้เหมือนเดิม |
| 5 | M3 `/healthz` | `status=ok` · `authConfigured=true` · `dbConfigured=true` |
| 6 | M3 `POST /api/admin/extract-file` พร้อม token ของ admin | **200** |
| 7 | M3 `POST /api/admin/ingest` ไม่มี token | **401** |

### ขั้นที่ 5 — เฝ้าดู

เฝ้า log ของ webapi และสถานะคอนเทนเนอร์อย่างน้อย 10 นาที · ดูว่ามี `auth failed` ที่ไม่ได้ตั้งใจเพิ่มขึ้นไหม

---

## 8. GO / NO-GO ฉบับแก้แล้ว

### 8.1 สถานะ

# `GO` แบบมีเงื่อนไข

ปรับลงจาก `GO` ในเอกสารก่อนหน้า เพราะพบข้อผิดพลาดของตัวเอง 3 จุดที่กระทบวิธีทำงานจริง

### 8.2 ต้องทำก่อน apply

| # | สิ่งที่ต้องทำ | สถานะ |
|---|---|---|
| ~~1~~ | ~~ตรวจว่า `c1_is_approved_staff` ยังไม่มีอยู่~~ | **เสร็จแล้ว** — ไม่มี (ข้อ 2.3) |
| ~~2~~ | ~~เปลี่ยนเป็น `create function`~~ | **ตัดสินใจแล้ว** — คงไว้ |
| **1** | เตรียม `PROJECT_REF` · `ANON_KEY` จาก Dashboard | **ยังไม่ทำ** |
| **2** | ตรวจว่ามีบัญชี `role='user'` ไว้ทดสอบ U1 ไหม (ข้อ 6.5) | **ยังไม่ทำ** |
| **3** | เตรียม access token ของ admin และของ user | **ยังไม่ทำ** |
| **4** | **เก็บค่าฐาน A1 · U1 · D1 ผ่าน PostgREST** | **ยังไม่ทำ** — ไม่มีค่าฐานก็เทียบผลไม่ได้ |

### 8.3 เงื่อนไขทั้งหมด

| # | เงื่อนไข | สถานะ |
|---|---|---|
| 1 | รู้ชื่อและนิยาม `SELECT` policy เดิม | **ผ่าน** |
| 2 | รู้ว่ามี `SELECT` policy ที่เปิดกี่ตัว | **ผ่าน** — 1 ตัว |
| 3 | รู้ `UPDATE` policy เดิมครบ | **ผ่าน** |
| 4 | ประเมินความเสี่ยง recursion | **ผ่านบางส่วน** — มีหลักฐานหนักแน่น **แต่ต้องทดสอบยืนยัน** (ข้อ 4) |
| 5 | รู้ trigger ทั้งหมด | **ผ่าน** |
| 6 | ยืนยันว่าตัวกัน `role`/`status` ทำงาน | **ผ่าน** |
| 7 | รู้ค่าเริ่มต้นของโปรไฟล์ใหม่ | **ผ่าน** |
| 8 | ไม่มี view หรือฟังก์ชันที่อ่านอ้อม | **ผ่านในขอบเขตที่ตรวจ** |
| 9 | บัญชี `editor` ไว้ทดสอบ | **`BLOCKED`** — ไม่มีบัญชี · **ไม่บล็อกการ apply แต่ทดแทนด้วย admin ไม่ได้** |
| 10 | รายการสิทธิ์ละเอียดของตาราง | ยังไม่มี · ไม่บล็อกรอบนี้ |
| 11 | ฟังก์ชันใหม่ไม่ชนของเดิม | **ผ่าน** — ตรวจแล้ว `No rows returned` (ข้อ 2.3) |
| 12 | **มีวิธีทดสอบ RLS ที่ถูกต้อง** | **ผ่านแล้วหลังแก้** — ข้อ 6 |
| 13 | Rollback คืนสภาพได้ครบ | **ผ่าน** — ข้อ 7 |

### 8.4 NO-GO

| อาการ | ทำอะไร |
|---|---|
| ข้อ 2.2 พบว่ามีฟังก์ชันชื่อนี้อยู่แล้ว | **หยุด** — เปลี่ยนชื่อก่อน |
| `infinite recursion detected in policy` | **rollback ทันที** |
| **A1 หลังแก้ไม่ได้ `0`** (วัดผ่าน PostgREST) | **หยุด** — ถอด policy ไม่ครบ |
| U1 หลังแก้ไม่ได้ `1` | ตรวจ policy `select_own` |
| D1 หลังแก้ลดลงจากค่าฐาน | **rollback** — ฟังก์ชันไม่ทำงาน |
| M3 `extract-file` พร้อม token ของ admin ได้ 403 | **rollback ทันที** |
| ล็อกอินหน้าผู้ดูแลไม่ได้ | **rollback ทันที** |
| ตรวจเจ้าของฟังก์ชันแล้วไม่ตรงกับเจ้าของตาราง | **หยุด** — ดูข้อ 3.3 |

### 8.5 ความเสี่ยงที่ยอมรับ

| # | ความเสี่ยง | ทำไมยอมรับได้ |
|---|---|---|
| 1 | เส้นทาง `editor` ไม่ถูกทดสอบ | ไม่มีบัญชี `editor` ในระบบ · ไม่มีใครกระทบวันนี้ · ย้อนได้ |
| 2 | recursion ยังไม่พิสูจน์ด้วยการทดสอบ | ล้มแบบเห็นชัดและย้อนได้ทันที · ไม่มีข้อมูลเสียหาย |
| 3 | `TRUNCATE` ยังค้างอยู่ | เรียกผ่าน PostgREST ตรงไม่ได้ · เป็นงานแยกที่ต้องอนุมัติ |
| 4 | ฟังก์ชันเดิม 2 ตัวไม่มี `SET search_path` | การอ้างอิงภายในระบุ schema ไว้แล้ว · เป็นงานเสริมความแข็งแกร่งภายหลัง |

---

## 9. สรุปสิ่งที่แก้ในรอบนี้

| # | เรื่อง | เดิม | แก้เป็น |
|---|---|---|---|
| 1 | `GRANT`/`REVOKE` | "ไม่มีเลยในรอบนี้" | **ไม่แตะสิทธิ์ตาราง · มี 2 คำสั่งสำหรับฟังก์ชันใหม่** |
| 2 | สร้างฟังก์ชัน | `create or replace` | **ตรวจก่อน + ใช้ `create`** |
| 3 | Ownership | กล่าวถึงลอย ๆ | **มีคำสั่งตรวจและเกณฑ์ชัดเจน** |
| 4 | Recursion | "ปลอดภัยแน่นอน" | **"มีหลักฐานสนับสนุน แต่ต้องทดสอบ"** พร้อมอธิบายความต่างของบริบท |
| 5 | Admin แทน Editor | "ครอบคลุมเส้นทางเดียวกัน" | **"แทนกันไม่ได้ครบ"** |
| 6 | วิธีทดสอบ | SQL Editor | **PostgREST ด้วยบริบท `anon`/`authenticated` จริง** |
| 7 | Rollback | ครบอยู่แล้ว | **เพิ่มคำสั่งตรวจหลัง rollback และกรณีที่ทำลายของเดิม** |
| 8 | GO/NO-GO | `GO` | **`GO` แบบมีเงื่อนไข** พร้อม 4 ข้อที่ต้องทำก่อน |

---

## 10. ยืนยันขอบเขต

| ข้อห้าม | สถานะ |
|---|---|
| Apply migration | **ไม่ได้ทำ** |
| `GRANT` / `REVOKE` / แก้ policy จริง | **ไม่ได้ทำ** |
| สร้างบัญชี หรือเปลี่ยน `role`/`status` | **ไม่ได้ทำ** |
| Deploy / Restart / Push / Merge | **ไม่ได้ทำ** |
| เปิดเผย PII หรือ secrets | **ไม่มีในเอกสารนี้** — คำสั่งทดสอบใช้ `read -rsp` และ `limit=0` เพื่อไม่ให้ค่าและข้อมูลโผล่ |

```
Local  HEAD 427ce19 · mko-phase2 · ไฟล์โค้ดที่แก้ 0
Prod   webapi d2663f039a18 · running · healthy · บริการอื่นไม่ถูกแตะ
```

**สถานะ: `GO` แบบมีเงื่อนไข — ทำข้อ 8.2 ให้ครบ 4 ข้อ แล้วรออนุมัติ apply**
