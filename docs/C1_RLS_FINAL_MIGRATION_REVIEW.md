# C1 — ทบทวน Migration จากผล RLS จริง

> **READ-ONLY** — ไม่ apply migration · ไม่ `REVOKE` · ไม่แก้ Supabase Auth หรือ RLS จริง · ไม่ deploy · ไม่ restart · ไม่ push/merge · ไม่ดึงข้อมูลส่วนบุคคล

| รายการ | ค่า |
|---|---|
| วันที่ | 11 ตุลาคม 2569 |
| ต่อจาก | `C1_RLS_VERIFIED_MIGRATION_PLAN.md` |
| สถานะ | **`NO-GO` ชั่วคราว** — พบเรื่องที่ร้ายแรงกว่า R1 ต้องตัดสินใจขอบเขตใหม่ก่อน |

---

## ผลสรุปสั้น

การตรวจรอบนี้พบว่า **R1 ไม่ใช่ปัญหาที่ร้ายแรงที่สุดของตารางนี้**

| # | เรื่อง | ความรุนแรง | สถานะ |
|---|---|---|---|
| **F1** | **ผู้ใช้ทั่วไปอาจเลื่อนตัวเองเป็น `admin` ได้** | **วิกฤต** | **ต้องยืนยันด้วยชุด F และ C ก่อน** |
| **F2** | `anon` มีสิทธิ์เขียนระดับตาราง · ถ้ามี `TRUNCATE` ด้วย **RLS คุมไม่ได้เลย** | **สูง** | ต้องยืนยันรายการสิทธิ์ที่แน่ชัด |
| **R1** | `user_profiles` อ่านได้โดยทุกคนขณะเก็บอีเมลและชื่อจริง | สูง | **ยืนยันแล้ว** |
| **F3** | ถ้าแก้ `SELECT` policy โดยไม่ระวัง **จะเกิด recursion ทันที** | สูง | วิเคราะห์แล้ว มีทางแก้ |

**ไม่ควร apply migration ที่แก้แค่ `SELECT`** เพราะจะปิดช่องที่เบากว่าแล้วปล่อยช่องที่หนักกว่าไว้

---

## 1. วิเคราะห์ Recursion ของ UPDATE Policy เดิม

### 1.1 Policy ที่ยืนยันแล้ว

| ชื่อ | cmd | USING | WITH CHECK |
|---|---|---|---|
| `Public profiles are viewable by everyone` | SELECT | `true` · PERMISSIVE · roles `{public}` | — |
| `Approved admins can update any profile` | UPDATE | `EXISTS (SELECT 1 FROM user_profiles p WHERE p.user_id = auth.uid() AND p.role = 'admin' AND p.status = 'approved')` | **NULL** |
| `Users can update own profile` | UPDATE | `auth.uid() = user_id` | **NULL** |

### 1.2 ทำไมของเดิมยังไม่ recursion — คำตอบสำคัญกว่าที่คิด

Policy `Approved admins can update any profile` **อ้างถึง `user_profiles` ในตัวเอง** ซึ่งตามปกติคือสูตรของ recursion

ที่ยังไม่พังเพราะ — เมื่อ subquery `SELECT 1 FROM user_profiles p` ทำงาน PostgreSQL ต้องเอา **`SELECT` policy** มาใช้กับ subquery นั้น และ `SELECT` policy ปัจจุบันคือ `USING (true)` ซึ่ง**ไม่อ้างถึงตารางอีก** การประเมินจึงจบทันที

```
UPDATE policy -> subquery บน user_profiles -> ใช้ SELECT policy -> true -> จบ
```

> **`USING (true)` ซึ่งคือตัว R1 เอง คือสิ่งที่กันไม่ให้ UPDATE policy เกิด recursion อยู่ตอนนี้**

### 1.3 ผลที่ตามมา — การแก้ R1 จะทำให้ recursion โผล่ ถ้าทำผิดวิธี

ถ้าเปลี่ยน `SELECT` policy เป็นแบบที่อ้างถึงตารางเอง เช่น

```sql
-- ห้ามทำ
create policy ... for select using (
  exists (select 1 from user_profiles where user_id = auth.uid() and role in ('admin','editor'))
);
```

จะเกิด

```
UPDATE policy -> subquery -> SELECT policy -> subquery -> SELECT policy -> ... ไม่จบ
```

อาการคือ `infinite recursion detected in policy for relation "user_profiles"` และ **ทุกการอ่านและเขียนตารางนี้พังพร้อมกัน** รวมถึงล็อกอินหน้าผู้ดูแลและ M3

### 1.4 เงื่อนไขที่ทำให้ทางแก้ใช้ได้จริง — ต้องยืนยันเพิ่ม

ทางแก้คือใช้ฟังก์ชัน `SECURITY DEFINER` ซึ่งรันด้วยสิทธิ์เจ้าของจึงข้าม RLS **แต่ข้ามได้ก็ต่อเมื่อ**

```sql
select relforcerowsecurity from pg_class where oid = 'public.user_profiles'::regclass;
```

| ค่า | ผล |
|---|---|
| **false** | เจ้าของตารางข้าม RLS ได้ → ฟังก์ชันทำงานถูกต้อง **ไม่ recursion** |
| **true** | **บังคับ RLS กับเจ้าของด้วย** → ฟังก์ชันจะถูก RLS จับ → **recursion กลับมา** ต้องออกแบบใหม่ทั้งหมด |

**ยังไม่ได้รับค่านี้** — ผลที่ส่งมาระบุแค่ `enabled=true` · เป็น blocker ข้อหนึ่ง

---

## 2. ⚠ F1 — ช่องโหว่ที่ร้ายแรงกว่า R1

### 2.1 ความหมายของ `WITH CHECK: NULL`

PostgreSQL กำหนดว่า **ถ้า UPDATE policy ไม่มี `WITH CHECK` จะนำ `USING` มาใช้เป็น `WITH CHECK` แทน**

ดังนั้น policy `Users can update own profile` มีผลจริงเป็น

```
USING      : auth.uid() = user_id     -- เลือกแถวที่แก้ได้
WITH CHECK : auth.uid() = user_id     -- แถวหลังแก้ต้องยังเป็นของตัวเอง
```

### 2.2 ปัญหา

เงื่อนไขนี้ควบคุมแค่ว่า **แถวยังเป็นของตัวเอง** แต่ **ไม่ได้ควบคุมว่าแก้คอลัมน์ไหนได้บ้าง** — RLS ไม่มีกลไกจำกัดระดับคอลัมน์

ผู้ใช้ที่ล็อกอินแล้วจึงสามารถยิงคำขอไปที่ PostgREST โดยตรง (ไม่ต้องผ่านหน้าเว็บ) เพื่อแก้แถวของตัวเองให้เป็น

```
role   = 'admin'
status = 'approved'
```

แถวหลังแก้ยังเป็นของตัวเอง → `WITH CHECK` ผ่าน → **เลื่อนตัวเองเป็นผู้ดูแลสำเร็จ**

### 2.3 ผลกระทบถ้าเป็นจริง

| ระบบ | ผล |
|---|---|
| หน้าผู้ดูแลของเว็บ | เข้าได้ทั้งหมด |
| **M3 WebAPI `/api/admin/*`** | **ผ่านด่าน** เพราะ `requireAdminUser` อ่าน `role`/`status` จากตารางนี้โดยตรง |
| `/api/admin/ingest` | เขียนทับ `rag_documents` ได้ |
| `/api/admin/sync-sci-news` | สั่ง Edge Function ได้ |

**ด่านตรวจสิทธิ์ของ M3 ที่เพิ่ง deploy ไปเชื่อค่าในตารางนี้ทั้งหมด** ถ้าผู้ใช้แก้ค่าเองได้ ด่านก็ไม่มีความหมาย

### 2.4 สิ่งที่อาจกันไว้อยู่แล้ว — ต้องยืนยันก่อนสรุป

**ยังไม่ยืนยันว่าเป็นช่องโหว่จริง** เพราะอาจมีกลไกอื่นกันไว้

| กลไกที่อาจมี | ตรวจด้วย | ถ้ามี |
|---|---|---|
| Trigger `BEFORE UPDATE` ที่คืนค่า `role`/`status` เดิมถ้าผู้แก้ไม่ใช่ admin | **ชุด F** | ปลอดภัย — เป็นวิธีที่ถูกต้อง |
| `GRANT UPDATE (full_name)` แบบระบุคอลัมน์ แทน `GRANT UPDATE` ทั้งตาราง | **ชุด C แบบละเอียด** | ปลอดภัย |
| ไม่มีทั้งสองอย่าง | — | **เป็นช่องโหว่จริง ระดับวิกฤต** |

### 2.5 คำสั่งตรวจ — รันเพิ่ม

```sql
-- F1-a : trigger บนตาราง
select tgname, pg_get_triggerdef(oid) as definition
from pg_trigger
where tgrelid = 'public.user_profiles'::regclass and not tgisinternal;

-- F1-b : สิทธิ์ระดับคอลัมน์ (ถ้ามีแถว = จำกัดคอลัมน์ไว้แล้ว)
select grantee, column_name, privilege_type
from information_schema.column_privileges
where table_schema='public' and table_name='user_profiles'
  and grantee in ('anon','authenticated')
order by grantee, column_name;

-- F1-c : สิทธิ์ระดับตารางแบบละเอียด
select grantee, privilege_type, is_grantable
from information_schema.role_table_grants
where table_schema='public' and table_name='user_profiles'
  and grantee in ('anon','authenticated','public','service_role')
order by grantee, privilege_type;
```

> **ห้ามทดลองเลื่อนสิทธิ์จริงเพื่อพิสูจน์** — ดูจากกฎและ trigger เท่านั้น การทดลองคือการเขียน production database

---

## 3. F2 — สิทธิ์ที่ RLS คุมไม่ได้

ผลตรวจระบุว่า **`anon` มี `SELECT` และสิทธิ์เขียนระดับตาราง**

### 3.1 คำสั่งไหน RLS คุมได้บ้าง

| คำสั่ง | RLS คุม | สถานะสำหรับ `anon` |
|---|---|---|
| `SELECT` | **ใช่** | policy `true` → **อ่านได้ทุกแถว** (คือ R1) |
| `INSERT` | **ใช่** | ไม่มี INSERT policy → **ถูกปฏิเสธ** |
| `UPDATE` | **ใช่** | `auth.uid()` เป็น `NULL` สำหรับ anon → เงื่อนไขไม่เป็นจริง → **ถูกปฏิเสธ** |
| `DELETE` | **ใช่** | ไม่มี DELETE policy → **ถูกปฏิเสธ** |
| **`TRUNCATE`** | **ไม่** | **ถ้า `anon` มีสิทธิ์นี้ จะลบข้อมูลทั้งตารางได้ RLS ไม่ขวางเลย** |
| `REFERENCES` | **ไม่** | ความเสี่ยงต่ำ |
| `TRIGGER` | **ไม่** | ถ้ามี = สร้าง trigger รันโค้ดได้ **ความเสี่ยงสูง** |

### 3.2 ข้อสรุป

RLS ยังกัน `INSERT`/`UPDATE`/`DELETE` ของ anon ได้อยู่ แม้จะมี grant **แต่ `TRUNCATE` และ `TRIGGER` อยู่นอกการควบคุมของ RLS โดยสิ้นเชิง**

**ต้องดูผล F1-c ว่ารายการสิทธิ์ของ `anon` มีอะไรบ้างแน่ ๆ** ถ้ามี `TRUNCATE` ต้องถอดออก ซึ่งเป็นการ `REVOKE` ที่คำสั่งรอบนี้ห้ามไว้ จึงต้องขออนุมัติแยก

---

## 4. ออกแบบ Policy ที่ไม่เกิด Recursion

### 4.1 ฟังก์ชันตรวจสิทธิ์ — least privilege

```sql
create or replace function public.c1_is_approved_staff()
returns boolean
language sql
stable                              -- ไม่ใช่ volatile ลดการเรียกซ้ำต่อแถว
security definer                    -- ข้าม RLS จึงไม่เกิด recursion
set search_path = pg_catalog, public  -- กันการสวม search_path
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
```

| มาตรการ | เหตุผล |
|---|---|
| คืน **`boolean` เท่านั้น** | ไม่กลายเป็นช่องทางดึงข้อมูลใหม่ |
| `set search_path = pg_catalog, public` | ผู้เรียกสร้าง schema ปลอมมาหลอกไม่ได้ · ใส่ `pg_catalog` นำหน้าเพื่อกันการสวมฟังก์ชันในตัว |
| `revoke ... from public, anon` | `anon` เรียกไม่ได้ |
| `stable` | ผลคงที่ในคำสั่งเดียวกัน ลดภาระ |
| ชื่อขึ้นต้น `c1_` | **ไม่ไปทับฟังก์ชันเดิม** ตามความเสี่ยงที่ระบุไว้รอบก่อน |
| **ไม่** ใช้ `admin` อย่างเดียว | รวม `editor` เพราะรายการเนื้อหาต้องแสดงชื่อผู้เขียน |

### 4.2 SELECT Policy ใหม่

```sql
drop policy if exists "Public profiles are viewable by everyone" on public.user_profiles;

create policy c1_user_profiles_select_own
  on public.user_profiles for select
  to authenticated
  using (auth.uid() = user_id);

create policy c1_user_profiles_select_staff
  on public.user_profiles for select
  to authenticated
  using (public.c1_is_approved_staff());
```

### 4.3 ตรวจว่า UPDATE Policy เดิมยังทำงานได้ไหมหลังเปลี่ยน

Policy `Approved admins can update any profile` มี subquery

```sql
EXISTS (SELECT 1 FROM user_profiles p WHERE p.user_id = auth.uid() AND p.role='admin' AND p.status='approved')
```

subquery นี้อ่าน **แถวของผู้เรียกเอง** → เข้าเงื่อนไข `c1_user_profiles_select_own` → **ยังทำงานได้**

เส้นทางการประเมินหลังเปลี่ยน

```
UPDATE policy -> subquery -> SELECT policy
                               |- select_own  : auth.uid() = user_id       -> ไม่อ้างตาราง จบ
                               `- select_staff: c1_is_approved_staff()     -> SECURITY DEFINER ข้าม RLS จบ
```

**ไม่มีเส้นทางใดวนกลับ** — โดยมีเงื่อนไขว่า `relforcerowsecurity = false` ตามข้อ 1.4

### 4.4 UPDATE Policy — ข้อเสนอแก้ F1

> **เกินขอบเขตที่อนุมัติรอบนี้** เสนอไว้เพื่อประกอบการตัดสินใจ ยังไม่ใส่ใน migration

ทางเลือกในการปิดช่องเลื่อนสิทธิ์

| ทาง | วิธี | ข้อดี | ข้อเสีย |
|---|---|---|---|
| **ก** | Trigger `BEFORE UPDATE` คืนค่า `role`/`status` เดิมถ้าผู้แก้ไม่ใช่ admin ที่ approved | ครอบคลุมทุกเส้นทาง รวม PostgREST ตรง · ไม่ต้องแก้หน้าเว็บ | ต้องเขียน trigger ใหม่ |
| **ข** | `REVOKE UPDATE` ทั้งตาราง แล้ว `GRANT UPDATE (full_name)` ให้ `authenticated` · ส่วน admin ใช้ RPC | ชัดเจนที่สุด บังคับด้วยสิทธิ์ | หน้า `/admin/users` ที่แก้ `role`/`status` จะพัง ต้องแก้หน้าเว็บ |
| **ค** | เพิ่ม `WITH CHECK` ที่เทียบค่าเดิม | — | **ทำไม่ได้** `WITH CHECK` เห็นเฉพาะแถวใหม่ ไม่เห็นค่าเดิม |

**แนะนำทาง ก** เพราะไม่ต้องแตะรีโปของทีมออกแบบ

---

## 5. ความเข้ากันได้

| ระบบ | ใช้อะไร | หลังแก้ `SELECT` | หมายเหตุ |
|---|---|---|---|
| **Login** | Supabase Auth ไม่อ่าน `user_profiles` | **ไม่กระทบ** | |
| **หน้าสาธารณะ** | ไม่อ่านตารางนี้เลย | **ไม่กระทบ** | ยืนยันจากไฟล์ที่ deploy จริง |
| **ตรวจสิทธิ์เข้าหน้าผู้ดูแล** | `role, status` ของตัวเอง | **ไม่กระทบ** | `select_own` ครอบ |
| **หน้าโปรไฟล์** | `full_name` ของตัวเอง อ่าน/แก้ | **ไม่กระทบ** | |
| **แดชบอร์ด** | นับทั้งตาราง | **ไม่กระทบ** | `select_staff` ครอบ |
| **รายการเนื้อหา (ชื่อผู้เขียน)** | `user_id, full_name, email` ของคนอื่น | **ไม่กระทบ** ถ้ารวม `editor` | **จุดที่พังง่ายที่สุด** |
| **`/admin/users`** | อ่านทุกแถว + แก้ `role`/`status` | **ไม่กระทบ** | UPDATE policy เดิมยังทำงาน (ข้อ 4.3) |
| **M3 `auth.mjs`** | `role, status` ของตัวเอง ในนามผู้เรียก | **ไม่กระทบ** | |
| **M3 `adminAuth.js`** | `role, status` ของตัวเอง ในนามผู้เรียก | **ไม่กระทบ** | |

### 5.1 M3 ล้มแบบปลอดภัย

ถ้าอ่านโปรไฟล์ไม่ได้ `readProfile` คืน `null` → `role: null` → ด่านปฏิเสธ **ไม่เดาว่ามีสิทธิ์** ยืนยันด้วยชุดทดสอบ `webapi/auth.test.mjs:368`

---

## 6. Migration และ Rollback

### 6.1 Migration — เฉพาะส่วน `SELECT`

```sql
-- C1 — จำกัดการอ่าน public.user_profiles (แก้ R1)
-- แก้เฉพาะ SELECT · ไม่แตะ UPDATE policy เดิมทั้งสองตัว
--
-- ⚠ ต้องยืนยัน relforcerowsecurity = false ก่อน ไม่งั้นจะเกิด recursion

begin;

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

drop policy if exists "Public profiles are viewable by everyone" on public.user_profiles;

create policy c1_user_profiles_select_own
  on public.user_profiles for select
  to authenticated
  using (auth.uid() = user_id);

create policy c1_user_profiles_select_staff
  on public.user_profiles for select
  to authenticated
  using (public.c1_is_approved_staff());

commit;
```

### 6.2 Rollback — รักษาชื่อและนิยามเดิมไว้ครบ

```sql
-- คืนสภาพเดิมแบบคำต่อคำจากผลตรวจจริง
-- ⚠ การ rollback = เปิด R1 กลับมา ใช้ชั่วคราวเท่านั้น

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

**UPDATE policy ทั้งสองตัวไม่ถูกแตะ จึงไม่ต้องสร้างคืน** — บันทึกนิยามเดิมไว้เผื่อจำเป็น

```sql
-- สำเนานิยามเดิมของ UPDATE policy (ไม่ได้แก้ในรอบนี้)
-- "Approved admins can update any profile"
--   FOR UPDATE USING (EXISTS (SELECT 1 FROM user_profiles p
--     WHERE p.user_id = auth.uid() AND p.role = 'admin' AND p.status = 'approved'))
-- "Users can update own profile"
--   FOR UPDATE USING (auth.uid() = user_id)
```

### 6.3 ตรวจทันทีหลัง commit

```sql
-- 1) ต้องไม่เหลือ policy ที่เปิดให้อ่าน
select policyname, cmd, permissive, roles::text, qual
from pg_policies
where schemaname='public' and tablename='user_profiles' and cmd in ('SELECT','ALL');
-- ต้องไม่มีแถวใดที่ qual = 'true'

-- 2) ต้องไม่ recursion
select count(*) from public.user_profiles where user_id = auth.uid();

-- 3) UPDATE policy เดิมยังอยู่ครบ
select policyname from pg_policies
where schemaname='public' and tablename='user_profiles' and cmd='UPDATE';
-- ต้องได้ 2 แถวชื่อเดิม
```

---

## 7. ผลตรวจที่ยังขาด

| ชุด | ตรวจอะไร | ทำไมต้องมีก่อน GO |
|---|---|---|
| **B (ส่วนที่ขาด)** | `relforcerowsecurity` | **ถ้า true ทางแก้ทั้งหมดใช้ไม่ได้** เกิด recursion |
| **F** | trigger บนตาราง | ตัดสินว่า **F1 เป็นช่องโหว่จริงหรือมีอะไรกันไว้** |
| **C (ละเอียด)** | สิทธิ์ระดับคอลัมน์ และรายการสิทธิ์ของ `anon` แบบครบ | ตัดสิน F1 และ F2 · ดูว่ามี `TRUNCATE` ไหม |
| **E** | object ที่พึ่งพาตาราง (view ฯลฯ) | view ที่อ่านตารางนี้อาจกลายเป็นช่องอ่านอ้อม |
| **G** | รายชื่อคอลัมน์ | ยืนยันว่า `email`/`full_name` อยู่ในตารางนี้จริง และมี PII อื่นอีกไหม |
| **H** | ตารางอื่นที่มี `qual = true` | R1 อาจไม่ใช่ตารางเดียว |
| **I** | จำนวนนับ | ประเมินขนาดผลกระทบ · ยืนยันว่ามี `editor` ไว้ทดสอบ E2 ไหม |

ชุด E, G, H, I อยู่ใน `C1_RLS_VERIFIED_MIGRATION_PLAN.md` ข้อ 2 แล้ว · ชุด F1-a/b/c อยู่ในข้อ 2.5 ของเอกสารนี้

---

## 8. GO / NO-GO

### 8.1 สถานะ

# `NO-GO`

ไม่ใช่เพราะแผนผิด แต่เพราะ **ผลตรวจเปิดเผยปัญหาที่ใหญ่กว่าขอบเขตที่อนุมัติไว้**

### 8.2 เงื่อนไข GO

| # | เงื่อนไข | สถานะ |
|---|---|---|
| 1 | รู้ชื่อและนิยาม `SELECT` policy เดิม | **ผ่าน** — `Public profiles are viewable by everyone` · `USING (true)` |
| 2 | รู้ว่า `SELECT` policy ที่เปิดมีกี่ตัว | **ผ่าน** — 1 ตัว |
| 3 | รู้ `UPDATE` policy เดิมครบ | **ผ่าน** — 2 ตัว บันทึกนิยามไว้แล้ว |
| 4 | ประเมิน recursion แล้ว | **ผ่าน** — ข้อ 1 และ 4.3 |
| 5 | **ยืนยัน `relforcerowsecurity = false`** | **ยังไม่มี** |
| 6 | **ตัดสินว่า F1 เป็นช่องโหว่จริงไหม (ชุด F และ C)** | **ยังไม่มี** |
| 7 | **รู้ว่า `anon` มี `TRUNCATE` ไหม** | **ยังไม่มี** |
| 8 | ผลชุด E, G, H, I | **ยังไม่มี** |
| 9 | มีบัญชี `editor` ไว้ทดสอบ E2 | **ยังไม่ยืนยัน** |
| 10 | ตัดสินใจขอบเขต — แก้แค่ `SELECT` หรือแก้ F1 ด้วย | **ต้องตัดสินใจ** |

**ผ่าน 4 จาก 10**

### 8.3 ทำไมไม่ควรแก้แค่ `SELECT` แล้วจบ

| ถ้าแก้แค่ `SELECT` | ผล |
|---|---|
| R1 ปิด | อีเมลไม่หลุดสู่สาธารณะแล้ว |
| **F1 ยังเปิด (ถ้าเป็นจริง)** | **ผู้ใช้ที่ล็อกอินยังเลื่อนตัวเองเป็น admin ได้** |
| ความเสี่ยงรวม | **อาจแย่ลงในแง่การรับรู้** — จะเข้าใจว่า "แก้ความปลอดภัยของตารางนี้แล้ว" ทั้งที่ช่องที่หนักกว่ายังอยู่ |

### 8.4 NO-GO ระหว่าง apply

| อาการ | ทำอะไร |
|---|---|
| `infinite recursion detected in policy` | **rollback ทันที** |
| ข้อ 6.3 ข้อ 1 ยังเจอ `qual = 'true'` | **หยุด** — ถอดไม่ครบ |
| ข้อ 6.3 ข้อ 3 ได้ไม่ครบ 2 แถว | **หยุด** — เผลอลบ UPDATE policy |
| ล็อกอินหน้าผู้ดูแลไม่ได้ | **rollback ทันที** |
| M3 `extract-file` พร้อม token ของ admin ได้ 403 | **rollback ทันที** |
| ชื่อผู้เขียนหายจากรายการเนื้อหาของ editor | **rollback** — ลืมรวม editor |

---

## 9. สิ่งที่เสนอให้ทำต่อ

| ลำดับ | งาน | ใคร |
|---|---|---|
| **1** | รันชุด **F1-a, F1-b, F1-c** และ `relforcerowsecurity` | **เจ้าของ** — ตัดสินว่า F1 เป็นช่องโหว่จริงไหม |
| 2 | รันชุด E, G, H, I ที่ยังขาด | เจ้าของ |
| 3 | ตัดสินใจขอบเขต — แก้ `SELECT` อย่างเดียว หรือรวม F1 ในคราวเดียว | เจ้าของ |
| 4 | ถ้า F1 จริง — อนุมัติให้ออกแบบ trigger ตามทาง ก ข้อ 4.4 | เจ้าของ |
| 5 | ถ้า `anon` มี `TRUNCATE` — อนุมัติ `REVOKE` แยก | เจ้าของ |
| 6 | เตรียมบัญชี `editor` ที่ `approved` ไว้ทดสอบ | เจ้าของ |

> **ข้อ 1 เร่งที่สุด** ถ้าไม่มี trigger และไม่มีสิทธิ์ระดับคอลัมน์กันไว้ F1 คือช่องโหว่ระดับวิกฤตที่เปิดอยู่ขณะนี้ และ M3 ที่เพิ่ง deploy ไปก็พึ่งค่าในตารางนี้โดยตรง

---

## 10. ยืนยันขอบเขต

| ข้อห้าม | สถานะ |
|---|---|
| Apply migration หรือ `REVOKE` | **ไม่ได้ทำ** |
| แก้ Supabase Auth หรือ RLS จริง | **ไม่ได้ทำ** — ไม่ได้เชื่อมต่อ Supabase เลย |
| ดึงข้อมูลส่วนบุคคล | **ไม่ได้ทำ** — วิเคราะห์จากกฎที่เจ้าของส่งมาและจากโค้ดเท่านั้น |
| ทดลองเลื่อนสิทธิ์เพื่อพิสูจน์ F1 | **ไม่ได้ทำ** — เป็นการเขียน production database |
| Deploy / Restart / Push / Merge | **ไม่ได้ทำ** |

```
Local  HEAD 427ce19 · mko-phase2 · ไฟล์โค้ดที่แก้ 0
Prod   webapi d2663f039a18 · running · healthy · restarts=0 · บริการอื่นไม่ถูกแตะ
```

**สถานะ: `NO-GO` — รอผลชุด F1 และการตัดสินใจขอบเขต ก่อนขออนุมัติแก้ production**
