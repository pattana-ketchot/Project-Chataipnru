# C1 — ทบทวนความปลอดภัยตามหลักฐานที่ตรวจจริง

> **READ-ONLY** — ไม่แก้ production · ไม่ apply SQL · ไม่ `REVOKE` · ไม่ deploy · ไม่ restart · ไม่ push/merge

| รายการ | ค่า |
|---|---|
| วันที่ | 11 ตุลาคม 2569 |
| แทนที่ | `C1_RLS_FINAL_MIGRATION_REVIEW.md` ในส่วนที่ประเมินไว้ก่อนได้หลักฐาน |
| สถานะ | **`NO-GO`** — เหลือหลักฐาน 2 ชิ้นที่ต้องเห็นก่อน |

---

## อ่านแบบเร็ว — สรุปเป็นภาษาง่าย ๆ

### ตรวจอะไรไปแล้ว

ดูกฎความปลอดภัยของตาราง `user_profiles` ใน Supabase ซึ่งเก็บ **อีเมลกับชื่อจริงของผู้ใช้ทุกคนรวมผู้ดูแล** และเป็นตารางที่ระบบใช้ตัดสินว่าใครเป็นผู้ดูแล

### พบอะไร

**เรื่องที่ 1 — ตารางนี้ใครก็อ่านได้ (ยืนยันแล้ว)**
กฎที่ชื่อ `Public profiles are viewable by everyone` เปิดให้อ่านได้ทุกคนแม้ไม่ล็อกอิน และกุญแจที่ใช้เปิดอยู่ใน JavaScript ของหน้าเว็บตามปกติ ใครเปิดดูก็เจอ

**เรื่องที่ 2 — `anon` และ `authenticated` มีสิทธิ์ `TRUNCATE` (ยืนยันแล้ว)**
`TRUNCATE` คือการล้างข้อมูลทั้งตารางในครั้งเดียว และ**กฎ RLS ไม่คุมคำสั่งนี้เลย** เป็นการให้สิทธิ์ที่เกินความจำเป็นมาก · ข่าวดีคือเท่าที่ประเมิน **ยังเรียกผ่านหน้าเว็บโดยตรงไม่ได้** เพราะ API ของ Supabase ไม่มีช่องทางสั่ง `TRUNCATE`

**เรื่องที่ 3 — เรื่องที่เคยกังวลที่สุด มีตัวกันอยู่แล้ว (แต่ยังไม่เห็นโค้ด)**
รอบก่อนกังวลว่าผู้ใช้ทั่วไปอาจแก้ข้อมูลตัวเองให้กลายเป็นผู้ดูแลได้ · **ตรวจแล้วพบว่ามีตัวกันชื่อ `guard_user_profile_privileges_trigger` ติดตั้งอยู่** ซึ่งน่าจะทำหน้าที่นี้พอดี · **แต่ยังไม่ได้เห็นโค้ดข้างใน จึงยังไม่ฟันธงว่ากันได้ครบ**

**เรื่องที่ 4 — ปัญหาที่เคยกลัวว่าจะทำให้ระบบล่ม หมดไปแล้ว**
ตรวจพบว่าค่า `forced = false` ซึ่งแปลว่าวิธีแก้ที่วางไว้ใช้ได้จริงและจะไม่ทำให้เกิดการวนซ้ำไม่รู้จบ

### ยังไม่ได้แก้อะไรเลย

**ไม่มีการเปลี่ยนแปลงใด ๆ บน production** ทั้ง Supabase ฐานข้อมูล และระบบที่รันอยู่ · เอกสารนี้เป็นการวิเคราะห์และเตรียมคำสั่งไว้เท่านั้น

### ต้องการอะไรต่อ

ขอดู **โค้ดข้างในของ `guard_user_profile_privileges()`** กับ **รายการสิทธิ์แบบละเอียด** แค่สองอย่าง แล้วจะสรุปได้ว่าเดินหน้าได้หรือไม่

---

## 1. หลักฐานที่ยืนยันแล้ว

| # | สิ่งที่ตรวจพบ | ผลต่อการประเมิน |
|---|---|---|
| 1 | `rls_enabled = true` · **`rls_forced = false`** | **ปลดล็อก** — `SECURITY DEFINER` ข้าม RLS ได้ ทางแก้ใช้ได้จริง |
| 2 | `SELECT` policy `Public profiles are viewable by everyone` · `USING (true)` · PERMISSIVE · `{public}` | **R1 ยืนยัน** |
| 3 | `anon` และ `authenticated` มี **`TRUNCATE`** และสิทธิ์อื่นระดับตาราง | **F2 ยืนยัน** |
| 4 | มี trigger **`guard_user_profile_privileges_trigger`** ก่อน `UPDATE` | **F1 เปลี่ยนสถานะ** — มีตัวกันอยู่ |
| 5 | มี function **`guard_user_profile_privileges()`** แบบ `SECURITY DEFINER` | ตัวกันของข้อ 4 |
| 6 | มี trigger **`on_auth_user_created`** และ function **`handle_new_user()`** | อธิบายว่าโปรไฟล์ถูกสร้างอย่างไร |
| 7 | `UPDATE` policy 2 ตัว ตามที่รายงานไว้เดิม | ไม่เปลี่ยน |

---

## 2. แยกความเสี่ยงที่ยืนยันแล้ว ออกจากที่ยังเป็นสมมติฐาน

### 2.1 ยืนยันแล้ว

| รหัส | เรื่อง | ความรุนแรง | หลักฐาน |
|---|---|---|---|
| **R1** | `user_profiles` อ่านได้โดยทุกคนรวม `anon` ขณะเก็บ `email` และ `full_name` | **สูง** | policy `USING (true)` roles `{public}` |
| **F2** | `anon` และ `authenticated` มี `TRUNCATE` ซึ่ง **RLS ไม่คุม** | **สูง** (ดูข้อ 4 เรื่องการเข้าถึงจริง) | grant ระดับตาราง |

### 2.2 เปลี่ยนสถานะ — เดิมประเมินว่าวิกฤต ตอนนี้ลดระดับ

| รหัส | เรื่อง | สถานะใหม่ |
|---|---|---|
| **F1** | ผู้ใช้ทั่วไปเลื่อนตัวเองเป็น `admin` | **น่าจะถูกกันไว้แล้ว — รอยืนยันโค้ด** |

**เหตุผลที่ลดระดับ** — พบ trigger `guard_user_profile_privileges_trigger` ทำงาน **ก่อน `UPDATE`** และชื่อฟังก์ชันตรงกับหน้าที่ที่ควรทำพอดี (`guard` + `user_profile` + `privileges`)

**เหตุผลที่ยังไม่ปิดเคส** — **ยังไม่เห็นโค้ดข้างในฟังก์ชัน** การสรุปจากชื่อฟังก์ชันคือการเดา ไม่ใช่การตรวจสอบ

### 2.3 หมดไปแล้ว

| รหัส | เรื่อง | เหตุผล |
|---|---|---|
| **F3** | แก้ `SELECT` policy แล้วจะเกิด recursion | **`rls_forced = false`** → `SECURITY DEFINER` ข้าม RLS ได้ → ไม่วนซ้ำ (วิเคราะห์เส้นทางในข้อ 5.2) |

---

## 3. F1 — สิ่งที่ต้องดูในโค้ดของ `guard_user_profile_privileges()`

### 3.1 คำสั่งขอโค้ด

```sql
select pg_get_functiondef(oid) as definition
from pg_proc
where pronamespace = 'public'::regnamespace
  and proname = 'guard_user_profile_privileges';

select tgname, tgtype, pg_get_triggerdef(oid) as definition
from pg_trigger
where tgrelid = 'public.user_profiles'::regclass and not tgisinternal;
```

> คืนเฉพาะนิยามฟังก์ชันและ trigger **ไม่มีข้อมูลผู้ใช้**

### 3.2 รายการตรวจ — ต้องผ่านทุกข้อจึงจะปิดเคส F1

| # | ต้องมี | ถ้าไม่มีจะเกิดอะไร |
|---|---|---|
| 1 | เทียบ `OLD.role` กับ `NEW.role` **และ** `OLD.status` กับ `NEW.status` | ถ้าเทียบแค่ `role` ผู้ใช้จะแก้ `status` ตัวเองเป็น `approved` ได้ |
| 2 | เมื่อค่าเปลี่ยนและผู้แก้**ไม่ใช่** admin ที่ approved → **คืนค่าเดิม** หรือ **`raise exception`** | ถ้าแค่เตือนแล้วปล่อยผ่าน ไม่มีผล |
| 3 | ทำงานกับ **ทุกเส้นทาง** ไม่ใช่เฉพาะที่มาจากหน้าเว็บ | trigger ระดับฐานข้อมูลครอบคลุมอยู่แล้วถ้าเขียนถูก |
| 4 | จัดการกรณี `auth.uid()` เป็น `NULL` | ถ้าเทียบ `NULL` ผิดวิธี เงื่อนไขอาจกลายเป็น `NULL` แล้วหลุด |
| 5 | เป็น `BEFORE UPDATE` **FOR EACH ROW** | ถ้าเป็น `STATEMENT` จะไม่เห็น `OLD`/`NEW` |
| 6 | มี `set search_path` | เป็น `SECURITY DEFINER` จึงเสี่ยงถูกสวม `search_path` |
| 7 | ไม่ยกเว้นให้ `service_role` แบบกว้างเกินไป | ถ้ายกเว้นทั้งหมด เส้นทางที่ใช้ service key จะข้ามการป้องกัน |

### 3.3 ข้อจำกัดที่ trigger นี้ครอบไม่ถึง

| ช่องทาง | trigger ก่อน `UPDATE` ครอบไหม |
|---|---|
| `UPDATE` ผ่าน PostgREST | **ครอบ** |
| `UPDATE` ผ่าน SQL ตรง | **ครอบ** |
| `INSERT` แถวใหม่ที่ตั้ง `role='admin'` มาเลย | **ไม่ครอบ** — เป็น trigger ของ `UPDATE` เท่านั้น · ต้องดูว่า `handle_new_user()` ตั้งค่าอะไรให้ และมี `INSERT` policy ไหม (ปัจจุบันไม่มี จึง `anon`/`authenticated` insert ตรงไม่ได้) |
| **`TRUNCATE`** | **ไม่ครอบ** — คนละชนิด trigger |

---

## 4. F2 — TRUNCATE ประเมินตามความเป็นจริง

### 4.1 ทำไมเป็นเรื่อง

`TRUNCATE` ลบทุกแถวในตารางในครั้งเดียว และ **PostgreSQL ไม่นำ RLS มาใช้กับคำสั่งนี้** นโยบายที่เขียนไว้ทั้งหมดจึงไม่มีผล

นอกจากนั้นยัง **ข้าม trigger ของ `UPDATE`/`DELETE`** ด้วย ตัวกัน `guard_user_profile_privileges` จึงไม่ช่วยอะไรในกรณีนี้

### 4.2 เข้าถึงได้จริงแค่ไหน — ประเมินตรงไปตรงมา

| ช่องทาง | สั่ง `TRUNCATE` ได้ไหม | เหตุผล |
|---|---|---|
| PostgREST ผ่าน anon key จากหน้าเว็บ | **ไม่ได้** | PostgREST รองรับแค่ `SELECT`/`INSERT`/`UPDATE`/`DELETE` และ `rpc` **ไม่มีช่องทางสั่ง `TRUNCATE`** |
| `POST /rpc/<ฟังก์ชัน>` | **ได้ ถ้ามีฟังก์ชันที่สั่ง `TRUNCATE` หรือรัน SQL แบบไดนามิก** | ต้องตรวจว่ามีฟังก์ชันแบบนั้นไหม — **ชุด D และ E ที่ยังขาด** |
| ต่อฐานข้อมูลตรงด้วย role `anon` | **ไม่ได้ในทางปฏิบัติ** | anon key เป็น JWT สำหรับ API ไม่ใช่รหัสผ่านฐานข้อมูล |
| ผ่านช่องโหว่อื่นในอนาคต เช่น SQL injection ในฟังก์ชัน `SECURITY INVOKER` | **ได้** | สิทธิ์นี้ทำให้ความเสียหายบานปลายจาก "อ่านข้อมูลได้" เป็น "ลบข้อมูลทิ้งทั้งตาราง" |

### 4.3 สรุปความรุนแรง

> **ไม่ใช่ช่องโหว่ที่กดใช้ได้ทันทีจากหน้าเว็บ** แต่เป็น **การให้สิทธิ์เกินจำเป็นอย่างชัดเจน** ที่ขยายความเสียหายของช่องโหว่อื่นทุกตัว

ควรถอดออก แต่ **การ `REVOKE` อยู่นอกขอบเขตที่อนุมัติรอบนี้** จึงเสนอไว้เพื่อขออนุมัติแยก

### 4.4 แนวทาง REVOKE ที่เสนอ (ยังไม่รัน)

```sql
-- ถอดสิทธิ์ที่ RLS คุมไม่ได้ออกจาก anon และ authenticated
-- ⚠ ต้องดูผลชุดสิทธิ์แบบละเอียดก่อน เพื่อไม่ถอดสิ่งที่ระบบใช้อยู่

revoke truncate on table public.user_profiles from anon, authenticated;
revoke trigger  on table public.user_profiles from anon, authenticated;
revoke references on table public.user_profiles from anon, authenticated;
```

| ข้อควรระวัง | เหตุผล |
|---|---|
| **อย่าใช้ `revoke all`** | จะถอด `SELECT`/`UPDATE` ที่ระบบใช้งานจริงไปด้วย ทำให้หน้าเว็บและ M3 พัง |
| ถอดทีละสิทธิ์ที่ระบุชื่อ | ควบคุมผลได้ |
| ตรวจก่อนว่ามีอะไรบ้างจริง ๆ | ดูข้อ 6 |

---

## 5. ผลต่อการออกแบบ Migration

### 5.1 สิ่งที่เปลี่ยนจากฉบับก่อน

| ประเด็น | ฉบับก่อน | ฉบับนี้ |
|---|---|---|
| ความเสี่ยง recursion | เป็น blocker | **หมดไป** — `rls_forced = false` |
| F1 | ประเมินว่าวิกฤต | **น่าจะถูกกันแล้ว** รอยืนยันโค้ด |
| ขอบเขตที่แนะนำ | เสนอรวม F1 ในคราวเดียว | **แยกได้** — ถ้า guard ทำงานจริง แก้ `SELECT` อย่างเดียวก็สมเหตุสมผล |
| TRUNCATE | ยังไม่ยืนยัน | **ยืนยันแล้ว** ต้องขออนุมัติ `REVOKE` แยก |

### 5.2 เส้นทางการประเมินหลังเปลี่ยน — ยืนยันว่าไม่วนซ้ำ

```
UPDATE policy "Approved admins can update any profile"
  └─ subquery: SELECT 1 FROM user_profiles WHERE user_id = auth.uid() ...
       └─ ใช้ SELECT policy
            ├─ c1_select_own   : auth.uid() = user_id          -> ไม่อ้างตาราง จบ
            └─ c1_select_staff : c1_is_approved_staff()
                 └─ SECURITY DEFINER + rls_forced=false        -> ข้าม RLS จบ
```

**ไม่มีเส้นทางใดวนกลับ** และ subquery ของ UPDATE policy อ่าน**แถวของผู้เรียกเอง** ซึ่ง `c1_select_own` ครอบอยู่แล้ว จึงยังทำงานได้

### 5.3 trigger `on_auth_user_created` ไม่ถูกกระทบ

`handle_new_user()` ทำ `INSERT` ตอนสมัครสมาชิก ซึ่งทำงานได้ทุกวันนี้ทั้งที่**ไม่มี `INSERT` policy** แปลว่าเป็น `SECURITY DEFINER` ที่ข้าม RLS อยู่แล้ว

**รอบนี้แก้เฉพาะ `SELECT` policy จึงไม่กระทบการสมัครสมาชิก**

> ยังควรดูโค้ด `handle_new_user()` ว่าตั้ง `role`/`status` เริ่มต้นเป็นอะไร ถ้าตั้งเป็น `admin`/`approved` จะเป็นปัญหาคนละเรื่อง — ขอมาพร้อมกับข้อ 3.1

---

## 6. ผลตรวจที่ยังขาด — เหลือ 2 ชิ้นสำคัญ

| ลำดับ | สิ่งที่ขอ | ใช้ตัดสินอะไร |
|---|---|---|
| **1** | **โค้ดของ `guard_user_profile_privileges()` และ `handle_new_user()`** | ปิดเคส F1 · ดูค่าเริ่มต้นของโปรไฟล์ใหม่ |
| **2** | **รายการสิทธิ์แบบละเอียด** | ยืนยันขอบเขต F2 และเขียน `REVOKE` ให้ถูก |

```sql
-- ชิ้นที่ 1
select proname, prosecdef, proconfig::text, pg_get_functiondef(oid) as definition
from pg_proc
where pronamespace = 'public'::regnamespace
  and proname in ('guard_user_profile_privileges','handle_new_user');

select tgname, pg_get_triggerdef(oid) as definition
from pg_trigger
where not tgisinternal
  and tgrelid in ('public.user_profiles'::regclass);

-- ชิ้นที่ 2
select grantee, privilege_type, is_grantable
from information_schema.role_table_grants
where table_schema='public' and table_name='user_profiles'
  and grantee in ('anon','authenticated','public','service_role')
order by grantee, privilege_type;

select grantee, column_name, privilege_type
from information_schema.column_privileges
where table_schema='public' and table_name='user_profiles'
  and grantee in ('anon','authenticated')
order by grantee, column_name;
```

### 6.1 ที่ยังขาดแต่ไม่บล็อก

ชุด **E** (object ที่พึ่งพาตาราง) · **G** (รายชื่อคอลัมน์) · **H** (ตารางอื่นที่เปิดแบบเดียวกัน) · **I** (จำนวนนับ)

| ชุด | ทำไมควรมี |
|---|---|
| E | view ที่อ่านตารางนี้อาจกลายเป็นช่องอ่านอ้อมหลังปิด policy · และบอกว่ามีฟังก์ชันที่สั่ง `TRUNCATE` ไหม (ข้อ 4.2) |
| G | ยืนยันว่ามี PII อะไรบ้างนอกจาก `email` และ `full_name` |
| H | **R1 อาจไม่ใช่ตารางเดียว** |
| I | ยืนยันว่ามีบัญชี `editor` ไว้ทดสอบไหม |

---

## 7. Migration และ Rollback ฉบับปรับตามระบบจริง

### 7.1 Migration — แก้เฉพาะ `SELECT`

```sql
-- C1 — จำกัดการอ่าน public.user_profiles (แก้ R1)
--
-- ยืนยันแล้ว: rls_enabled = true · rls_forced = false -> SECURITY DEFINER ข้าม RLS ได้
-- ไม่แตะ: UPDATE policy 2 ตัว · trigger guard_user_profile_privileges_trigger
--         · trigger on_auth_user_created · function handle_new_user()

begin;

-- 1) ฟังก์ชันตรวจสิทธิ์ ตั้งชื่อขึ้นต้น c1_ เพื่อไม่ทับของเดิม
create or replace function public.c1_is_approved_staff()
returns boolean
language sql
stable
security definer
set search_path = pg_catalog, public
as $$
  select exists (
    select 1 from public.user_profiles
    where user_id = auth.uid()
      and role in ('admin','editor')
      and status = 'approved'
  );
$$;

revoke all on function public.c1_is_approved_staff() from public, anon;
grant execute on function public.c1_is_approved_staff() to authenticated;

-- 2) ถอด policy เดิมที่เปิดให้ทุกคนอ่าน (ยืนยันแล้วว่ามีตัวเดียว)
drop policy if exists "Public profiles are viewable by everyone" on public.user_profiles;

-- 3) อ่านแถวของตัวเอง
create policy c1_user_profiles_select_own
  on public.user_profiles for select
  to authenticated
  using (auth.uid() = user_id);

-- 4) ผู้ดูแลและผู้แก้ไขที่อนุมัติแล้ว อ่านได้ทุกแถว
create policy c1_user_profiles_select_staff
  on public.user_profiles for select
  to authenticated
  using (public.c1_is_approved_staff());

commit;
```

### 7.2 Rollback — คืนนิยามเดิมแบบคำต่อคำ

```sql
begin;

drop policy if exists c1_user_profiles_select_own   on public.user_profiles;
drop policy if exists c1_user_profiles_select_staff on public.user_profiles;

create policy "Public profiles are viewable by everyone"
  on public.user_profiles
  as permissive
  for select
  to public
  using (true);

drop function if exists public.c1_is_approved_staff();

commit;
```

### 7.3 ตรวจทันทีหลัง commit

```sql
-- 1) ต้องไม่เหลือ policy ที่เปิดให้อ่าน
select policyname, cmd, permissive, roles::text, qual
from pg_policies
where schemaname='public' and tablename='user_profiles' and cmd in ('SELECT','ALL');
-- ต้องไม่มีแถวใดที่ qual = 'true'

-- 2) ต้องไม่ recursion
select count(*) from public.user_profiles where user_id = auth.uid();

-- 3) ของเดิมต้องอยู่ครบ
select policyname from pg_policies
where schemaname='public' and tablename='user_profiles' and cmd='UPDATE';
-- ต้องได้ 2 แถวชื่อเดิม

select tgname from pg_trigger
where tgrelid='public.user_profiles'::regclass and not tgisinternal;
-- ต้องยังมี guard_user_profile_privileges_trigger
```

---

## 8. ความเข้ากันได้ — ไม่เปลี่ยนจากฉบับก่อน

| ระบบ | ผลหลังแก้ `SELECT` |
|---|---|
| Login · สมัครสมาชิก | **ไม่กระทบ** — `handle_new_user()` เป็น `SECURITY DEFINER` และรอบนี้ไม่แตะ `INSERT` |
| หน้าสาธารณะทั้งหมด | **ไม่กระทบ** — ไม่อ่านตารางนี้เลย |
| ตรวจสิทธิ์เข้าหน้าผู้ดูแล · หน้าโปรไฟล์ | **ไม่กระทบ** — อ่านแถวตัวเอง |
| แดชบอร์ด · รายการเนื้อหา (ชื่อผู้เขียน) | **ไม่กระทบ** ถ้ารวม `editor` ← **จุดที่พังง่ายที่สุด** |
| `/admin/users` อ่านและแก้ | **ไม่กระทบ** — UPDATE policy เดิมยังทำงาน (ข้อ 5.2) |
| **M3 WebAPI** | **ไม่กระทบ** — `auth.mjs` และ `adminAuth.js` อ่าน `role, status` ของตัวเองในนามผู้เรียก · ตรวจซ้ำแล้วว่า**ไม่มีการเขียนและไม่มี `TRUNCATE`** ในโค้ด M3 เลย |

ถ้าอ่านโปรไฟล์ไม่ได้ M3 **ล้มแบบปลอดภัย** — `readProfile` คืน `null` → `role: null` → ปฏิเสธ ยืนยันด้วย `webapi/auth.test.mjs:368`

---

## 9. GO / NO-GO

### 9.1 สถานะ

# `NO-GO` — เหลือหลักฐาน 2 ชิ้น

ใกล้พร้อมมากแล้ว ความเสี่ยงที่เคยเป็น blocker หนักที่สุด (recursion) **หมดไปแล้ว**

### 9.2 เงื่อนไข GO

| # | เงื่อนไข | สถานะ |
|---|---|---|
| 1 | รู้ชื่อและนิยาม `SELECT` policy เดิม | **ผ่าน** |
| 2 | รู้ว่ามี `SELECT` policy ที่เปิดกี่ตัว | **ผ่าน** — 1 ตัว |
| 3 | รู้ `UPDATE` policy เดิมครบ | **ผ่าน** — 2 ตัว |
| 4 | ประเมิน recursion | **ผ่าน** — `rls_forced = false` |
| 5 | รู้ว่ามี trigger อะไรบ้างบนตาราง | **ผ่าน** — 2 ตัว |
| 6 | **ยืนยันว่า `guard_user_profile_privileges()` กัน `role` และ `status` ได้จริง** | **ยังไม่มีโค้ด** |
| 7 | **รู้รายการสิทธิ์แบบละเอียดของ `anon`/`authenticated`** | **ยังไม่มี** |
| 8 | ผลชุด E, G, H, I | **ยังไม่มี** (ไม่บล็อกการแก้ `SELECT`) |
| 9 | มีบัญชี `editor` ที่ `approved` ไว้ทดสอบ | **ยังไม่ยืนยัน** |
| 10 | ตัดสินใจว่าจะรวม `REVOKE TRUNCATE` ในคราวเดียวหรือแยก | **ต้องตัดสินใจ** |

**ผ่าน 5 จาก 10** (เดิม 4 จาก 10)

### 9.3 ทางเลือกของขอบเขต

| ทาง | ทำอะไร | เหมาะเมื่อ |
|---|---|---|
| **ก** | แก้ `SELECT` อย่างเดียวก่อน | **ยืนยันแล้วว่า guard ทำงาน** · ปิด R1 ได้เร็วโดยไม่แตะอย่างอื่น |
| ข | แก้ `SELECT` + `REVOKE TRUNCATE` ในคราวเดียว | ต้องการลดสิทธิ์เกินจำเป็นไปพร้อมกัน · ต้องมีรายการสิทธิ์ละเอียดก่อน |
| ค | รอจนตรวจครบทุกชุดแล้วทำทีเดียว | ไม่เร่ง อยากเห็นภาพรวมก่อน |

**แนะนำทาง ก** ถ้าโค้ด guard ผ่านรายการตรวจข้อ 3.2 — เพราะ R1 เป็นสิ่งที่เปิดอยู่จริงและปิดได้โดยไม่กระทบใคร ส่วน `TRUNCATE` เรียกจากหน้าเว็บตรงไม่ได้ จึงรอได้

### 9.4 NO-GO ระหว่าง apply

| อาการ | ทำอะไร |
|---|---|
| `infinite recursion detected in policy` | **rollback ทันที** |
| ข้อ 7.3 ข้อ 1 ยังเจอ `qual = 'true'` | **หยุด** — ถอดไม่ครบ |
| ข้อ 7.3 ข้อ 3 ได้ไม่ครบ 2 แถว หรือ trigger หาย | **หยุด** — เผลอลบของเดิม |
| ล็อกอินหน้าผู้ดูแลไม่ได้ | **rollback ทันที** |
| M3 `extract-file` พร้อม token ของ admin ได้ 403 | **rollback ทันที** |
| ชื่อผู้เขียนหายจากรายการเนื้อหาของ `editor` | **rollback** — ลืมรวม editor |

---

## 10. สิ่งที่ขอให้ทำต่อ

| ลำดับ | งาน | ใคร |
|---|---|---|
| **1** | ส่งโค้ด `guard_user_profile_privileges()` และ `handle_new_user()` (ข้อ 6) | **เจ้าของ** |
| **2** | ส่งรายการสิทธิ์ระดับตารางและระดับคอลัมน์แบบละเอียด | **เจ้าของ** |
| 3 | เลือกขอบเขตตามข้อ 9.3 | เจ้าของ |
| 4 | รันชุด E, G, H, I ที่ยังขาด | เจ้าของ |
| 5 | เตรียมบัญชี `editor` ที่ `approved` | เจ้าของ |
| 6 | พิจารณาอนุมัติ `REVOKE TRUNCATE` แยก | เจ้าของ |

---

## 11. ยืนยันขอบเขต

| ข้อห้าม | สถานะ |
|---|---|
| แก้ production | **ไม่ได้ทำ** |
| Apply SQL | **ไม่ได้ทำ** — SQL ในเอกสารยังไม่ถูกรันที่ใด |
| `REVOKE` | **ไม่ได้ทำ** — เสนอไว้เพื่อขออนุมัติเท่านั้น |
| แก้ Supabase Auth หรือ RLS จริง | **ไม่ได้ทำ** — ไม่ได้เชื่อมต่อ Supabase เลย |
| ทดลองเลื่อนสิทธิ์เพื่อพิสูจน์ F1 | **ไม่ได้ทำ** |
| Deploy / Restart / Push / Merge | **ไม่ได้ทำ** |
| เปิดเผยข้อมูลส่วนบุคคลหรือ token | **ไม่มีในเอกสารนี้** |

```
Local  HEAD 427ce19 · mko-phase2 · ไฟล์โค้ดที่แก้ 0
Prod   webapi d2663f039a18 · running · healthy · restarts=0 · บริการอื่นไม่ถูกแตะ
```

**สถานะ: `NO-GO` — รอโค้ด guard และรายการสิทธิ์ แล้วจึงขออนุมัติแก้ production แยกต่างหาก**
