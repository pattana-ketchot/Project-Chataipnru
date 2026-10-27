# C1 — ยืนยัน RLS จริงก่อนแก้ Production

> **READ-ONLY** — ไม่ apply migration · ไม่แก้ Supabase Auth หรือ RLS จริง · ไม่ deploy · ไม่ restart · ไม่ push/merge
> **ไม่อ่านและไม่ส่งข้อมูลผู้ใช้จริง** — คำสั่งทุกชุดในเอกสารนี้คืนเฉพาะโครงสร้างและกฎ ไม่คืนแถวข้อมูล

| รายการ | ค่า |
|---|---|
| วันที่ | 11 ตุลาคม 2569 |
| ต่อจาก | `C1_SUPABASE_RLS_SECURITY_PLAN.md` |
| สถานะ | **รอผลตรวจจากเจ้าของ** — ดูข้อ 9 |

---

## 1. สถานะและข้อจำกัด

ผู้ช่วย **ไม่มีสิทธิ์เข้าถึง Supabase โดยชอบ** และ **ไม่ใช้ช่องโหว่ R1 เพื่อดึงข้อมูล** ตามที่คำสั่งระบุ

จึงเตรียมคำสั่งตรวจแบบอ่านอย่างเดียวให้เจ้าของรันเอง แล้วนำผลมาปรับ migration ให้ตรงกับของจริง

**ยังไม่มีผลตรวจ → ยังสรุป GO ไม่ได้** ดูข้อ 9

### 1.1 หลักประกันว่าคำสั่งตรวจไม่ดึงข้อมูลส่วนบุคคล

| ชุด | อ่านจาก | คืนอะไร | มีข้อมูลผู้ใช้ไหม |
|---|---|---|---|
| A–B | `pg_policies`, `pg_class` | ชื่อ policy และนิพจน์เงื่อนไข | **ไม่มี** |
| C | `information_schema.role_table_grants` | ชื่อ role และชนิดสิทธิ์ | **ไม่มี** |
| D | `pg_proc` | นิยามฟังก์ชัน | **ไม่มี** |
| E–F | `pg_depend`, `pg_trigger` | ชื่อ object ที่เกี่ยวข้อง | **ไม่มี** |
| G | `information_schema.columns` | ชื่อคอลัมน์และชนิด | **ไม่มี** |
| H | `pg_policies` | ตารางอื่นที่มี policy แบบเปิด | **ไม่มี** |
| I | `count(*)` | ตัวเลขนับอย่างเดียว | **ไม่มี** |

**ไม่มีชุดใดใช้ `select *` หรือเลือกคอลัมน์ `email` / `full_name` เลย**

---

## 2. คำสั่งตรวจ — รันใน Supabase SQL Editor

> รันทีละชุด แล้วส่งผลกลับมาเป็นข้อความ **ไม่ต้องส่งภาพหน้าจอที่มีข้อมูลอื่นติดมา**

### ชุด A — Policy ทั้งหมดของ `user_profiles` ← สำคัญที่สุด

```sql
select
  policyname,
  cmd,
  permissive,
  roles::text  as applies_to_roles,
  coalesce(qual, '(ไม่มี USING)')            as using_expression,
  coalesce(with_check, '(ไม่มี WITH CHECK)') as with_check_expression
from pg_policies
where schemaname = 'public' and tablename = 'user_profiles'
order by cmd, policyname;
```

### ชุด B — RLS เปิดอยู่จริงไหม

```sql
select
  relname,
  relrowsecurity      as rls_enabled,
  relforcerowsecurity as rls_forced,
  (select count(*) from pg_policies
    where schemaname='public' and tablename='user_profiles') as policy_count
from pg_class
where oid = 'public.user_profiles'::regclass;
```

> **ถ้า `rls_enabled` เป็น false** → policy ทั้งหมดไม่มีผล ใครก็อ่านได้ทันที และสถานการณ์ร้ายแรงกว่าที่ประเมินไว้

### ชุด C — สิทธิ์ระดับตารางของแต่ละ role ← จุดที่คนมองข้ามบ่อย

```sql
select grantee, string_agg(distinct privilege_type, ', ' order by privilege_type) as privileges
from information_schema.role_table_grants
where table_schema='public' and table_name='user_profiles'
  and grantee in ('anon','authenticated','service_role','public')
group by grantee
order by grantee;
```

**ทำไมสำคัญ** — RLS กรองได้ก็ต่อเมื่อ role นั้นมี `GRANT` ระดับตารางอยู่ก่อน ถ้า `anon` **ไม่มี** `SELECT` grant เลย ก็อ่านไม่ได้อยู่แล้วไม่ว่า policy จะเขียนว่าอะไร · กลับกันถ้ามี grant อยู่ การแก้ policy อย่างเดียวคือทางที่ถูก

### ชุด D — ฟังก์ชันช่วยที่มีอยู่แล้ว

```sql
select
  p.proname,
  p.prosecdef                        as is_security_definer,
  pg_get_userbyid(p.proowner)        as owner,
  p.proconfig::text                  as config_settings,
  pg_get_functiondef(p.oid)          as definition
from pg_proc p
where p.pronamespace = 'public'::regnamespace
  and (
    p.proname in ('is_approved_staff','is_admin','is_staff','current_user_role','get_user_role','check_admin')
    or pg_get_functiondef(p.oid) ilike '%user_profiles%'
  )
order by p.proname;
```

### ชุด E — อะไรบ้างที่พึ่งพา `user_profiles`

```sql
select distinct
  dependent_ns.nspname || '.' || dependent_view.relname as dependent_object,
  dependent_view.relkind                                 as kind
from pg_depend
join pg_rewrite      on pg_depend.objid       = pg_rewrite.oid
join pg_class  dependent_view on pg_rewrite.ev_class = dependent_view.oid
join pg_class  source_table   on pg_depend.refobjid  = source_table.oid
join pg_namespace dependent_ns on dependent_view.relnamespace = dependent_ns.oid
where source_table.oid = 'public.user_profiles'::regclass
  and dependent_view.oid <> source_table.oid
order by 1;
```

### ชุด F — Trigger ที่สร้างหรือแก้โปรไฟล์

```sql
select tgname, tgrelid::regclass::text as on_table, pg_get_triggerdef(oid) as definition
from pg_trigger
where not tgisinternal
  and (tgrelid = 'public.user_profiles'::regclass
       or pg_get_triggerdef(oid) ilike '%user_profiles%')
order by tgname;
```

> ตรวจเพราะ SPA **ไม่มี `INSERT`** เลย แปลว่าโปรไฟล์น่าจะถูกสร้างด้วย trigger ตอนสมัคร ถ้าเป็นจริง trigger มักเป็น `SECURITY DEFINER` จึงไม่ถูกกระทบจากการแก้ policy — แต่ต้องยืนยัน

### ชุด G — คอลัมน์ในตาราง

```sql
select column_name, data_type, is_nullable
from information_schema.columns
where table_schema='public' and table_name='user_profiles'
order by ordinal_position;
```

### ชุด H — ตารางอื่นมีช่องโหว่แบบเดียวกันอีกไหม

```sql
select tablename, policyname, cmd, roles::text as applies_to_roles
from pg_policies
where schemaname = 'public'
  and cmd in ('SELECT','ALL')
  and qual = 'true'
order by tablename, policyname;
```

> R1 อาจไม่ใช่ตารางเดียว ชุดนี้ตอบว่ามีที่อื่นอีกไหม **ไม่ดึงข้อมูลในตารางเหล่านั้น**

### ชุด I — ขนาดของผลกระทบ (ตัวเลขล้วน)

```sql
select
  count(*)                                                        as total_profiles,
  count(*) filter (where role = 'admin'  and status = 'approved') as admin_approved,
  count(*) filter (where role = 'editor' and status = 'approved') as editor_approved,
  count(*) filter (where status <> 'approved')                    as not_approved
from public.user_profiles;
```

---

## 3. วิธีส่งผลกลับมาอย่างปลอดภัย

| ชุด | ส่งอะไร |
|---|---|
| A | **ส่งทั้งตาราง** — เป็นชื่อ policy และนิพจน์ ไม่ใช่ข้อมูลผู้ใช้ |
| B, C, G, H, I | ส่งทั้งตาราง |
| D | ส่งทั้งหมด · ถ้า `definition` ยาวมากส่งเฉพาะ `proname`, `is_security_definer`, `owner`, `config_settings` ก่อนได้ |
| E, F | ส่งทั้งหมด |

**ไม่ต้องส่ง** — อีเมล ชื่อจริง `user_id` หรือเนื้อหาในตาราง · ไม่มีชุดใดคืนค่าพวกนี้อยู่แล้ว

---

## 4. ตีความผล — ตารางตัดสิน

### 4.1 จากชุด A — `SELECT` policy

| สิ่งที่เห็น | ความหมาย | ทำอะไรต่อ |
|---|---|---|
| มี `SELECT` policy เดียว `permissive` `qual = true` | **ยืนยัน R1** ตามที่เอกสารบันทึก | ใช้ migration ข้อ 6 ได้ |
| มี `SELECT` policy **หลายตัว** และอย่างน้อยหนึ่งตัวเป็น `true` | **R1 ยังเปิด** — policy แบบ permissive รวมกันด้วย **OR** ตัวเดียวที่เปิดก็พอให้อ่านได้ | **ต้องถอดทุกตัวที่เปิด** ไม่ใช่แค่ตัวเดียว |
| `cmd = ALL` และ `qual = true` | เปิดทั้ง SELECT/INSERT/UPDATE/DELETE | **หยุด** — ขอบเขตใหญ่กว่าที่วางแผนไว้มาก ต้องออกแบบใหม่ |
| มี policy `restrictive` อยู่ด้วย | เงื่อนไขรวมกันด้วย **AND** | ต้องอ่านประกอบก่อนสรุป |
| `SELECT` policy ไม่ใช่ `true` | **R1 อาจถูกแก้ไปแล้ว** | **หยุด** — แผนนี้ใช้ไม่ได้ ตรวจใหม่ทั้งหมด |

> **จุดที่พลาดง่ายที่สุด** — policy แบบ permissive หลายตัวรวมกันด้วย OR ถ้าถอดไปตัวเดียวแล้วเหลืออีกตัวที่ `true` ช่องโหว่ยังเปิดอยู่ทั้งที่คิดว่าแก้แล้ว

### 4.2 จากชุด C — grant ระดับตาราง

| `anon` มีสิทธิ์ | ความหมาย |
|---|---|
| `SELECT` | ตามที่คาด — RLS คือด่านเดียว **แก้ policy คือทางที่ถูก** |
| ไม่มีเลย | anon อ่านไม่ได้อยู่แล้ว **R1 อาจไม่ร้ายอย่างที่ประเมิน** ต้องทบทวนความรุนแรงใหม่ |
| มี `INSERT`/`UPDATE`/`DELETE` ด้วย | **ร้ายแรงกว่าที่ประเมิน** ต้องขยายขอบเขตการแก้ |

### 4.3 จากชุด A และ D — ความเสี่ยง recursion

| สิ่งที่เห็นใน `UPDATE` policy | ความหมาย | ผล |
|---|---|---|
| อ้าง `user_profiles` ตรง ๆ ใน `EXISTS (...)` | ของเดิมเสี่ยง recursion อยู่แล้วแต่ยังไม่แสดงอาการ | **ต้องระวังมาก** — การเพิ่ม `SELECT` policy อาจกระตุ้นให้ recursion โผล่ · พิจารณาเปลี่ยน `UPDATE` ให้ใช้ฟังก์ชันเดียวกันในคราวเดียว |
| เรียกฟังก์ชัน เช่น `is_admin()` | ปลอดภัยถ้าฟังก์ชันเป็น `SECURITY DEFINER` | **ใช้ฟังก์ชันเดิมแทนการสร้างใหม่** |
| ใช้ claim จาก JWT เช่น `auth.jwt() ->> 'role'` | ไม่แตะตาราง ไม่มี recursion | ปลอดภัย · พิจารณาใช้วิธีเดียวกันกับ `SELECT` |

---

## 5. ความเสี่ยงของ `SECURITY DEFINER` — ต้องตรวจทุกข้อ

ฟังก์ชันแบบนี้รันด้วยสิทธิ์ของ**เจ้าของฟังก์ชัน** ไม่ใช่ผู้เรียก จึงข้าม RLS ได้ ซึ่งเป็นทั้งข้อดีและความเสี่ยง

| # | ความเสี่ยง | ทำไมอันตราย | การป้องกันใน migration |
|---|---|---|---|
| 1 | **`search_path` ถูกสวม** | ผู้เรียกสร้าง schema ของตัวเองที่มีตารางชื่อ `user_profiles` แล้วทำให้ฟังก์ชันไปอ่านของปลอม | `set search_path = public` ติดกับฟังก์ชัน **บังคับต้องมี** |
| 2 | **ใครเรียกก็ได้** | `anon` เรียกฟังก์ชันเพื่อตรวจสถานะคนอื่นได้ | `revoke all ... from public, anon` แล้ว `grant execute ... to authenticated` |
| 3 | **เจ้าของฟังก์ชันมีสิทธิ์สูงเกิน** | ถ้าเจ้าของเป็น superuser ฟังก์ชันจะทำได้ทุกอย่าง | ตรวจ `owner` จากชุด D · ควรเป็นเจ้าของ schema ปกติ |
| 4 | **คืนค่ามากกว่าที่ควร** | ถ้าฟังก์ชันคืนข้อมูลแทนที่จะคืน boolean จะกลายเป็นช่องทางดึงข้อมูลใหม่ | ฟังก์ชันคืน **`boolean` เท่านั้น** |
| 5 | **ไปทับฟังก์ชันเดิมที่มีคนใช้อยู่** | `create or replace` อาจเปลี่ยนพฤติกรรมของ policy อื่น | ชุด D และ E บอกว่ามีของเดิมไหมและใครใช้ · **ถ้ามีชื่อซ้ำ ห้าม replace** ให้ตั้งชื่อใหม่ |
| 6 | เป็น `volatile` ทำให้ช้า | ถูกเรียกทุกแถว | ประกาศ `stable` |

---

## 6. Migration และ Rollback — ฉบับที่ต้องปรับตามผลตรวจ

> **ยังรันไม่ได้** — มีช่องว่างที่ต้องเติมจากชุด A และ D

### 6.1 สิ่งที่ต้องเติมก่อนใช้

| ช่องว่าง | เติมจาก |
|---|---|
| `<ชื่อ policy เดิมทุกตัวที่เปิดให้อ่าน>` | ชุด A |
| `<ชื่อฟังก์ชัน>` — ใช้ของเดิมหรือสร้างใหม่ | ชุด D |
| ต้องแก้ `UPDATE` policy ด้วยไหม | ชุด A ข้อ 4.3 |

### 6.2 Migration

```sql
-- C1 — จำกัดการอ่าน public.user_profiles
-- แก้ความเสี่ยง R1 · แก้เฉพาะ SELECT · ไม่แตะ INSERT / UPDATE / DELETE
--
-- ก่อนรัน: เติมชื่อ policy เดิมจากชุด A ให้ครบทุกตัวที่เปิดให้อ่าน

begin;

-- 0) กันพลาด — ยืนยันว่า RLS เปิดอยู่
alter table public.user_profiles enable row level security;

-- 1) ฟังก์ชันตรวจสิทธิ์ที่ข้าม RLS เพื่อไม่ให้ policy เรียกตัวเองซ้อน
--    ถ้าชุด D พบฟังก์ชันเดิมที่ใช้ได้ ให้ข้ามขั้นนี้แล้วใช้ของเดิมในข้อ 4
create or replace function public.c1_is_approved_staff()
returns boolean
language sql
stable
security definer
set search_path = public          -- กันการสวม search_path
as $$
  select exists (
    select 1
    from public.user_profiles
    where user_id = auth.uid()
      and role in ('admin', 'editor')
      and status = 'approved'
  );
$$;

revoke all on function public.c1_is_approved_staff() from public, anon;
grant execute on function public.c1_is_approved_staff() to authenticated;

-- 2) ถอด policy เดิมที่เปิดให้อ่าน — ต้องครบทุกตัว
drop policy if exists "<ชื่อ policy เดิม 1>" on public.user_profiles;
-- drop policy if exists "<ชื่อ policy เดิม 2>" on public.user_profiles;

-- 3) อ่านแถวของตัวเอง
create policy c1_user_profiles_select_own
  on public.user_profiles
  for select
  to authenticated
  using (auth.uid() = user_id);

-- 4) ผู้ดูแลและผู้แก้ไขที่อนุมัติแล้ว อ่านได้ทุกแถว
create policy c1_user_profiles_select_staff
  on public.user_profiles
  for select
  to authenticated
  using (public.c1_is_approved_staff());

commit;
```

> ตั้งชื่อฟังก์ชันขึ้นต้นด้วย `c1_` โดยตั้งใจ เพื่อ**ไม่ไปทับของเดิม**ตามความเสี่ยงข้อ 5.5

### 6.3 ตรวจทันทีหลัง commit — ก่อนประกาศว่าสำเร็จ

```sql
-- ต้องเหลือเฉพาะ policy ของเราและต้องไม่มี qual = true หลงเหลือ
select policyname, cmd, permissive, roles::text, qual
from pg_policies
where schemaname='public' and tablename='user_profiles' and cmd in ('SELECT','ALL')
order by policyname;
```

**ต้องไม่มีแถวใดที่ `qual` เป็น `true`** ถ้ายังมีแปลว่าถอดไม่ครบ ช่องโหว่ยังเปิด

```sql
-- ต้องไม่เกิด recursion
select count(*) from public.user_profiles where user_id = auth.uid();
```

ถ้าขึ้น `infinite recursion detected in policy for relation "user_profiles"` → **rollback ทันที**

### 6.4 Rollback

```sql
-- ⚠ การ rollback = เปิดช่องโหว่ R1 กลับมา ใช้เป็นมาตรการชั่วคราวเท่านั้น

begin;

drop policy if exists c1_user_profiles_select_own   on public.user_profiles;
drop policy if exists c1_user_profiles_select_staff on public.user_profiles;

-- คืน policy เดิม — ใช้ชื่อและเงื่อนไขที่บันทึกจากชุด A แบบคำต่อคำ
create policy "<ชื่อ policy เดิม 1>"
  on public.user_profiles
  for select
  using (true);

-- ลบเฉพาะฟังก์ชันที่รอบนี้สร้าง ไม่แตะของเดิม
drop function if exists public.c1_is_approved_staff();

commit;
```

> **ต้องบันทึกผลชุด A ไว้ก่อน apply** ถ้าไม่รู้ชื่อและเงื่อนไขเดิมแบบคำต่อคำ จะคืนสภาพไม่ได้

---

## 7. แผนทดสอบ

### 7.1 anonymous

| # | ทดสอบ | ต้องได้ |
|---|---|---|
| A1 | อ่าน `user_profiles` ด้วย anon key (นับแถว ไม่ดึงข้อมูล) | **0 แถว** |
| A2 | หน้าแรก / หลักสูตร / เปรียบเทียบ / ค้นหาสาขา / แชท | ใช้ได้เหมือนเดิม |
| A3 | `GET /api/sci-connect-news` | **200** |
| A4 | `POST /api/admin/extract-file` ไม่มี token | **401** |

### 7.2 ผู้ใช้ทั่วไป

| # | ทดสอบ | ต้องได้ |
|---|---|---|
| U1 | อ่าน `role, status` ของตัวเอง | **1 แถว** |
| U2 | อ่าน/แก้ `full_name` ของตัวเอง | **ได้** |
| U3 | นับแถวทั้งตาราง | **1** (เห็นเฉพาะของตัวเอง) |
| U4 | เปิดหน้าผู้ดูแล | ถูกปฏิเสธเหมือนเดิม |

### 7.3 `editor` ที่ `approved`

| # | ทดสอบ | ต้องได้ |
|---|---|---|
| E1 | อ่าน `role, status` ของตัวเอง | ได้ |
| E2 | **รายการเนื้อหาแสดงชื่อผู้สร้าง/ผู้แก้ไข** | **เห็นเหมือนเดิม** ← พังง่ายที่สุดถ้าลืมรวม editor |
| E3 | แดชบอร์ดแสดงจำนวนผู้ใช้ | แสดงได้ |
| E4 | `POST /api/admin/extract-file` พร้อม token | **200** |
| E5 | แก้ `role` ของคนอื่น | ถูกปฏิเสธ (policy `UPDATE` เดิม) |

### 7.4 `admin` ที่ `approved`

| # | ทดสอบ | ต้องได้ |
|---|---|---|
| D1 | `/admin/users` เห็นรายชื่อครบ | เห็นครบ |
| D2 | แก้ `role` / `status` ของคนอื่น | ได้ |
| D3 | แดชบอร์ดครบทุกตัวเลข | ครบ |
| D4 | `POST /api/admin/extract-file` พร้อม token | **200** |

### 7.5 M3 WebAPI — ชุดที่ต้องผ่านหลังแก้ RLS

| # | ทดสอบ | ต้องได้ | เขียนข้อมูล |
|---|---|---|---|
| M1 | คอนเทนเนอร์ | `healthy` · restarts ไม่เพิ่ม | ไม่ |
| M2 | `/healthz` | `status=ok` · `authConfigured=true` · `dbConfigured=true` | ไม่ |
| M3 | ตรวจการเชื่อมต่อ PostgreSQL (วิธีเดิมในคู่มือ deploy ข้อ 4.0) | `ACCOUNT_NOT_LINKED` + `up` | ไม่ |
| M4 | `GET /api/sci-connect-news` | **200** | ไม่ |
| M5 | `POST /api/admin/ingest` **ไม่มี token** | **401** | ไม่ |
| M6 | **`POST /api/admin/extract-file` พร้อม token ของ admin** | **200** | ไม่ |
| M7 | log ของ webapi | ไม่มี `auth failed` ที่ไม่ได้ตั้งใจ · ไม่มีรหัสผ่าน | ไม่ |

> **M6 คือข้อชี้ขาด** — ถ้าได้ **403** แปลว่าการแก้ RLS ทำให้ `readProfile` อ่านแถวตัวเองไม่ได้ ซึ่งคือการล็อกผู้ดูแลออกจากระบบ ต้อง rollback ทันที

### 7.6 ทำไม M3 ไม่ควรพัง

ตรวจจากโค้ดแล้ว ทั้ง `auth.mjs:312` และ `adminAuth.js:31` อ่าน **แถวของตัวเอง** (`.eq('user_id', user.id)`) ด้วย client ที่ผูกกับ token ของผู้เรียก จึงเข้าเงื่อนไข policy `select_own`

และถ้าอ่านไม่ได้จริง ๆ ระบบ**ไม่เดาว่ามีสิทธิ์** — ชุดทดสอบ `webapi/auth.test.mjs:368` ยืนยันว่าเมื่อ `readProfile` ล้มเหลว จะได้ `role: null` แล้วด่านปฏิเสธ **ล้มแบบปลอดภัย ไม่ใช่ล้มแบบเปิดสิทธิ์**

---

## 8. ลำดับที่แนะนำตอน apply

```
1. รันชุด A–I เก็บผลไว้ทั้งหมด            (ยังไม่แก้อะไร)
2. เติมช่องว่างใน migration ตามผลจริง
3. ทบทวนเงื่อนไข GO ข้อ 9.1 อีกครั้ง
4. เลือกเวลาที่คนใช้งานน้อย
5. รัน migration ข้อ 6.2
6. รันชุดตรวจข้อ 6.3 ทันที               <- ต้องไม่มี qual = true และต้องไม่ recursion
7. ทดสอบ A1-A4 แล้ว M1-M7                <- ถ้าข้อใดไม่ผ่าน rollback ทันที
8. ทดสอบ U, E, D
9. เฝ้าดู log ของ webapi 10 นาที
```

**จุดที่ยังถอยได้โดยไม่กระทบใคร** คือขั้น 1–4 · **เริ่มกระทบที่ขั้น 5**

---

## 9. GO / NO-GO

### 9.1 เงื่อนไข GO

| # | เงื่อนไข | สถานะ |
|---|---|---|
| 1 | มีผลชุด A ครบ รู้ชื่อและเงื่อนไข policy ทุกตัว | **ยังไม่มี** |
| 2 | ยืนยันว่ามี `SELECT` policy ที่ `qual = true` จริง และรู้ว่ามีกี่ตัว | **ยังไม่ยืนยัน** |
| 3 | มีผลชุด C รู้ว่า `anon` มี grant อะไร | **ยังไม่มี** |
| 4 | มีผลชุด D รู้ว่ามีฟังก์ชันเดิมชื่อซ้ำไหม | **ยังไม่มี** |
| 5 | ประเมินความเสี่ยง recursion ของ `UPDATE` policy แล้ว | **ยังไม่ได้** |
| 6 | มีผลชุด F รู้ว่า trigger สร้างโปรไฟล์ทำงานอย่างไร | **ยังไม่มี** |
| 7 | เตรียมบัญชีทดสอบครบ 4 แบบ | **ต้องเตรียม** |
| 8 | บันทึก rollback SQL ที่เติมค่าจริงแล้ว | **ทำไม่ได้จนกว่าจะมีผลชุด A** |

**ครบ 0 จาก 8** — ทุกข้อขึ้นกับผลตรวจที่ยังไม่ได้รัน

### 9.2 NO-GO — หยุดทันทีถ้าเจอ

| อาการ | ทำอะไร |
|---|---|
| ชุด B บอกว่า `rls_enabled = false` | **หยุด** — สถานการณ์ต่างจากที่ประเมิน ต้องออกแบบใหม่ |
| ชุด A พบ `cmd = ALL` ที่ `qual = true` | **หยุด** — ขอบเขตใหญ่กว่าแผนนี้ |
| ชุด A พบ `SELECT` policy ที่ไม่ใช่ `true` | **หยุด** — R1 อาจถูกแก้ไปแล้ว ตรวจใหม่ |
| ชุด D พบฟังก์ชันชื่อซ้ำที่มีคนใช้อยู่ | **หยุด** — ห้าม `create or replace` ทับ |
| หลัง apply แล้วชุด 6.3 ยังเจอ `qual = true` | **หยุด** — ถอดไม่ครบ ช่องโหว่ยังเปิด |
| `infinite recursion detected in policy` | **rollback ทันที** |
| M6 ได้ 403 | **rollback ทันที** — ล็อกผู้ดูแลออก |
| หน้าสาธารณะพัง | **rollback** |

### 9.3 Blocker ที่เหลือ

| # | Blocker | ใครแก้ |
|---|---|---|
| **1** | **ยังไม่มีผลตรวจชุด A–I** — ผู้ช่วยเข้าถึง Supabase ไม่ได้ และไม่ใช้ช่องโหว่เพื่อตรวจ | **เจ้าของ** — รันข้อ 2 |
| 2 | ยังไม่ตัดสินใจว่าทดสอบบน production เลยหรือหาที่ทดสอบก่อน | เจ้าของ |
| 3 | ยังไม่มีบัญชีทดสอบ `editor` ที่ `approved` (เท่าที่ทราบมี admin 2 บัญชี) | เจ้าของ |

> ข้อ 3 สำคัญกว่าที่คิด — **E2 เป็นกรณีที่พังง่ายที่สุด** และทดสอบได้ก็ต่อเมื่อมีบัญชี editor จริง ถ้าไม่มี ต้องยอมรับว่าเสี่ยงที่จะพบปัญหาหลัง apply

---

## 10. ยืนยันขอบเขต

| ข้อห้าม | สถานะ |
|---|---|
| Apply migration | **ไม่ได้ทำ** — SQL ในเอกสารยังมีช่องว่างที่เติมไม่ได้จนกว่าจะมีผลตรวจ |
| แก้ Supabase Auth หรือ RLS จริง | **ไม่ได้ทำ** — ไม่ได้เชื่อมต่อ Supabase เลย |
| อ่านหรือส่งข้อมูลผู้ใช้จริง | **ไม่ได้ทำ** — ทุกชุดคืนเฉพาะโครงสร้างและกฎ |
| ใช้ช่องโหว่เพื่อตรวจ | **ไม่ได้ทำ** |
| Deploy / Restart / Push / Merge | **ไม่ได้ทำ** |
| เปิดเผยข้อมูลส่วนบุคคลหรือ token | **ไม่มีในเอกสารนี้** |

### สถานะระบบตอนปิดการตรวจ

```
Local  HEAD 427ce19 · mko-phase2 · ไฟล์โค้ดที่แก้ 0
Prod   webapi d2663f039a18 · running · healthy · restarts=0
       rollback image 1163e36361d9 ยังอยู่
       บริการอื่นไม่ถูกแตะ
```

**สถานะ: รอผลตรวจจากเจ้าของ แล้วจึงขออนุมัติแก้ production แยกต่างหาก**
