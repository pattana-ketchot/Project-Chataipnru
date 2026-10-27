# C1 — Final Pre-Migration Review

> **READ-ONLY** — ไม่แก้โค้ด ฐานข้อมูล production หรือ Supabase · ไม่รัน migration หรือ rollback · ไม่รัน SQL ที่เปลี่ยนสิทธิ์ · ไม่ deploy/restart/push/merge · **ไม่ทดสอบ API ที่สร้างหรือเปลี่ยนข้อมูลจริง**

| รายการ | ค่า |
|---|---|
| วันที่ | 11 ตุลาคม 2569 |
| อ้างอิง | `C1_RLS_IMPACT_ANALYSIS_SCI_ADVISOR.md` และเอกสาร C1 ก่อนหน้า |
| สถานะ | **`NO-GO` ชั่วคราว** — เหลือตรวจ **1 ข้อ** ที่ยังไม่มีหลักฐาน |

---

## สรุปสั้น

| | จำนวน | รายละเอียด |
|---|---|---|
| **ยืนยันแล้ว** | 9 ข้อ | ดูข้อ 1 |
| **ยังต้องตรวจ** | **1 ข้อ** | **เจ้าของฟังก์ชันข้าม RLS ได้หรือไม่** — ข้อ 2 |
| **แก้ SQL** | 2 จุด | `create or replace` → `create` · `drop policy if exists` → `drop policy` |
| **เปลี่ยนเป็น read-only** | 3 ข้อ | ข้อ 4 |
| **BLOCKED** | 4 ข้อ | ข้อ 4.4 |

---

## 1. สิ่งที่ยืนยันแล้ว

| # | เรื่อง | หลักฐาน |
|---|---|---|
| 1 | `SELECT` policy เดิมมีตัวเดียว `USING (true)` roles `{public}` | ผลตรวจ `pg_policies` |
| 2 | `UPDATE` policy 2 ตัว · `WITH CHECK = NULL` | CSV จาก SQL Editor |
| 3 | Trigger บนตาราง 2 ตัว + 1 ตัวบน `auth.users` | CSV |
| 4 | `guard_user_profile_privileges()` กัน `role` และ `status` ได้จริง | อ่านโค้ดเต็มแล้ว ครบ 6 เกณฑ์ |
| 5 | `handle_new_user()` ตั้ง `role='user'` | อ่านโค้ดเต็มแล้ว |
| 6 | `rls_enabled = true` · **`rls_forced = false`** | ผลตรวจ |
| 7 | ไม่มี view/rule ที่พึ่งพาตาราง · ฟังก์ชันใน `public` ที่อ้างตารางมีแค่ 2 ตัว | `No rows returned` |
| 8 | **ไม่มีฟังก์ชันชื่อ `c1_is_approved_staff`** | `No rows returned` |
| 9 | `proconfig = NULL` ทั้งสองฟังก์ชันเดิม (ไม่มี `search_path`) | ผลตรวจ |

### 1.1 Baseline ที่ใช้ตัดสิน

| ข้อ | บริบท | HTTP | `Content-Range` |
|---|---|---|---|
| **A1** | anonymous | **206** | **`*/3`** |
| **D1** | admin | **206** | **`*/3`** |
| U1 | user ทั่วไป | — | ⛔ ไม่มีช่องทางล็อกอิน |
| E1 | editor | — | ⛔ ไม่มีบัญชี |

ตาราง Supabase `user_profiles` มี **3 แถว**

---

## 2. ⚠ สิ่งที่ยังต้องตรวจ — เหลือข้อเดียว

### 2.1 เจ้าของฟังก์ชันใหม่จะข้าม RLS ได้หรือไม่

**ยังไม่มีหลักฐานโดยตรง** และนี่คือเงื่อนไขเดียวที่ยังขาด

`SECURITY DEFINER` รันด้วยสิทธิ์ของเจ้าของฟังก์ชัน จะข้าม RLS ได้ก็ต่อเมื่อเจ้าของคือ **เจ้าของตาราง** หรือมี `BYPASSRLS`

| ที่รู้แล้ว | ที่ยังไม่รู้ |
|---|---|
| `rls_forced = false` → เจ้าของตารางข้าม RLS ได้ | **ใครเป็นเจ้าของตาราง `user_profiles`** |
| `guard_user_profile_privileges()` ข้าม RLS ได้จริงทุกวันนี้ | **ใครเป็นเจ้าของฟังก์ชันนั้น** |
| ฟังก์ชันใหม่จะมีเจ้าของตามผู้ที่รัน `create` | **ผู้ที่รันใน SQL Editor คือ role ไหน** |

### 2.2 คำสั่งตรวจ — รันก่อน migration

```sql
select
  (select pg_get_userbyid(c.relowner)
     from pg_class c where c.oid = 'public.user_profiles'::regclass)        as table_owner,
  (select pg_get_userbyid(p.proowner)
     from pg_proc p
    where p.pronamespace = 'public'::regnamespace
      and p.proname = 'guard_user_profile_privileges')                      as working_function_owner,
  current_user                                                              as will_own_new_function,
  (select rolbypassrls from pg_roles where rolname = current_user)          as current_user_bypasses_rls;
```

> คืนเฉพาะชื่อ role และค่า boolean **ไม่มีข้อมูลผู้ใช้**

### 2.3 เกณฑ์ตัดสิน

| ผลที่ได้ | ความหมาย | ทำอะไร |
|---|---|---|
| `will_own_new_function` = `table_owner` | **ผ่าน** — ฟังก์ชันใหม่จะข้าม RLS ได้แน่นอน | **GO** |
| `will_own_new_function` = `working_function_owner` | **ผ่าน** — เป็น role เดียวกับที่ใช้ได้อยู่แล้ว | **GO** |
| `current_user_bypasses_rls` = `true` | **ผ่าน** — ข้าม RLS ได้ด้วยคุณสมบัติของ role เอง | **GO** |
| ไม่ตรงข้อใดเลย | **เสี่ยง recursion** | **หยุด** — ให้ผู้ที่เป็นเจ้าของตารางเป็นผู้รัน หรือพิจารณา `alter function ... owner to` (ต้องอนุมัติแยก) |

### 2.4 ถ้าไม่ตรวจแล้วผิดจะเกิดอะไร

| | |
|---|---|
| อาการ | `infinite recursion detected in policy for relation "user_profiles"` |
| ผล | **อ่านตารางไม่ได้เลย** → ล็อกอินหน้าผู้ดูแลไม่ได้ · M3 คืน 403 ทุกคำขอ |
| เห็นทันทีไหม | **เห็น** — เป็นข้อความผิดพลาด ไม่ใช่ความเงียบ |
| ย้อนได้ไหม | **ได้ทันที** · ไม่มีข้อมูลเสียหาย |
| ผู้ใช้ทั่วไปกระทบไหม | **ไม่** — การถาม AI ไม่แตะ Supabase |

> **ยังเป็นความเสี่ยงที่ควบคุมได้ แต่การตรวจล่วงหน้าใช้เวลาไม่ถึงนาที จึงควรตรวจ**

---

## 3. ตรวจ Migration และ Rollback SQL

### 3.1 ปัญหาที่พบในฉบับก่อน

SQL กระจายอยู่ใน **5 เอกสาร** และมี **2 จุดที่ไม่ปลอดภัย**

| # | ปัญหา | ผลถ้าปล่อยไว้ |
|---|---|---|
| **1** | ใช้ `create or replace function` | ถ้ามีฟังก์ชันชื่อนี้อยู่ (สร้างโดยใครก็ตามหลังจากที่เราตรวจ) จะ**ทับเงียบ ๆ** และ rollback ด้วย `drop function` จะทำลายของเดิม |
| **2** | ใช้ `drop policy if exists "Public profiles are viewable by everyone"` | **ถ้าชื่อไม่ตรง จะไม่ทำอะไรเลยและไม่มีข้อผิดพลาด** → policy เดิมยังอยู่ → **R1 ยังเปิด** ทั้งที่ transaction สำเร็จ |

ข้อ 2 อันตรายกว่า เพราะ **migration จะรายงานว่าสำเร็จ** ทั้งที่ช่องโหว่ยังอยู่ · จับได้เฉพาะเมื่อตรวจหลัง commit

### 3.2 ✅ Migration ฉบับแก้แล้ว — ใช้ฉบับนี้เท่านั้น

```sql
-- =====================================================================
-- C1 — จำกัดการอ่าน Supabase public.user_profiles  (แก้ความเสี่ยง R1)
-- ฉบับรวม ใช้แทนฉบับในเอกสารก่อนหน้าทั้งหมด
--
-- ต้องผ่านก่อนรัน:
--   1) ตรวจเจ้าของฟังก์ชันตามข้อ 2.2 แล้วผ่านเกณฑ์ข้อ 2.3
--   2) เปิด rollback (ข้อ 3.3) ค้างไว้ในหน้าต่างอื่น พร้อมกด
--
-- ไม่แตะ: UPDATE policy 2 ตัว · trigger 3 ตัว · สิทธิ์ระดับตาราง
-- =====================================================================

begin;

-- 1) ฟังก์ชันตรวจสิทธิ์
--    ใช้ create ไม่ใช่ create or replace -> ถ้าชื่อซ้ำจะล้มทั้ง transaction
create function public.c1_is_approved_staff()
returns boolean
language sql
stable
security definer
set search_path = pg_catalog, public
as $$
  select exists (
    select 1
    from public.user_profiles
    where user_id = auth.uid()
      and role in ('admin', 'editor')
      and status = 'approved'
  );
$$;

-- 2) ปิดไม่ให้ anon และ PUBLIC เรียกฟังก์ชันนี้
--    PostgreSQL ให้ EXECUTE แก่ PUBLIC อัตโนมัติ ต้อง revoke ก่อน grant เสมอ
revoke all on function public.c1_is_approved_staff() from public, anon;
grant execute on function public.c1_is_approved_staff() to authenticated;

-- 3) ถอด policy เดิมที่เปิดให้ทุกคนอ่าน
--    ไม่ใช้ if exists -> ถ้าชื่อไม่ตรงจะล้มทั้ง transaction แทนที่จะเงียบ
drop policy "Public profiles are viewable by everyone" on public.user_profiles;

-- 4) อ่านแถวของตัวเอง
create policy c1_user_profiles_select_own
  on public.user_profiles
  for select
  to authenticated
  using (auth.uid() = user_id);

-- 5) ผู้ดูแลและผู้แก้ไขที่อนุมัติแล้ว อ่านได้ทุกแถว
create policy c1_user_profiles_select_staff
  on public.user_profiles
  for select
  to authenticated
  using (public.c1_is_approved_staff());

commit;
```

#### ตรวจความถูกต้องทีละจุด

| จุด | ตรวจแล้ว |
|---|---|
| ลำดับ — สร้างฟังก์ชันก่อน policy ที่เรียกใช้ | **ถูกต้อง** |
| ลำดับ — `revoke` ก่อน `grant` | **ถูกต้อง** |
| อยู่ใน transaction เดียว | **ใช่** — ไม่มีช่วงที่ policy หายไประหว่างทาง |
| `auth.uid()` ระบุ schema | **ใช่** — แม้ `search_path` ไม่มี `auth` ก็เรียกได้ |
| `public.user_profiles` ระบุ schema | **ใช่** |
| คืนค่าเป็น `boolean` เท่านั้น | **ใช่** — ไม่เป็นช่องดึงข้อมูล |
| `stable` ไม่ใช่ `volatile` | **ใช่** |
| ไม่แตะ `UPDATE` policy / trigger / สิทธิ์ตาราง | **ใช่** |
| ล้มเสียงดังทุกกรณีที่ผิดคาด | **ใช่** — ทั้งชื่อฟังก์ชันซ้ำและชื่อ policy ไม่ตรง |

### 3.3 ✅ Rollback ฉบับแก้แล้ว

```sql
-- =====================================================================
-- C1 Rollback — คืนสภาพเดิมทั้งหมด
-- ⚠ การ rollback = เปิดช่องโหว่ R1 กลับมา ใช้เป็นมาตรการชั่วคราวเท่านั้น
-- =====================================================================

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

-- ลบเฉพาะฟังก์ชันที่รอบนี้สร้าง · ACL ของมันหายไปพร้อมกันอัตโนมัติ
drop function if exists public.c1_is_approved_staff();

commit;
```

| จุด | ตรวจแล้ว |
|---|---|
| ใช้ `if exists` ที่นี่เหมาะสมไหม | **ใช่** — ตรงข้ามกับ migration เพราะ rollback ต้องทำงานได้แม้ migration ล้มกลางคัน |
| คืน policy เดิมครบทุกคุณสมบัติ | **ใช่** — `as permissive` · `for select` · `to public` · `using (true)` |
| ต้องคืน `UPDATE` policy หรือ trigger ไหม | **ไม่ต้อง** — ไม่ได้แตะ |
| ต้องคืนสิทธิ์ของฟังก์ชันไหม | **ไม่ต้อง** — `drop function` ลบ ACL ไปด้วย |
| ทำลายของเดิมได้ไหม | **ไม่** — ยืนยันแล้วว่าไม่มีฟังก์ชันชื่อนี้อยู่ก่อน |
| ข้อมูลเสียหายไหม | **ไม่** — ไม่มีคำสั่งใดแตะข้อมูลในตาราง |

### 3.4 ตรวจทันทีหลัง commit

```sql
-- 1) ต้องไม่เหลือ policy ที่เปิดให้อ่าน
select policyname, cmd, permissive, roles::text, qual
from pg_policies
where schemaname='public' and tablename='user_profiles' and cmd in ('SELECT','ALL');
-- ต้องเห็นเฉพาะ c1_user_profiles_select_own และ c1_user_profiles_select_staff
-- ต้องไม่มีแถวใดที่ qual = 'true'

-- 2) ของเดิมต้องครบ
select policyname from pg_policies
where schemaname='public' and tablename='user_profiles' and cmd='UPDATE';   -- ต้องได้ 2

select tgname from pg_trigger
where tgrelid='public.user_profiles'::regclass and not tgisinternal;        -- ต้องได้ 2

-- 3) ฟังก์ชันใหม่ถูกต้อง
select proname, pg_get_userbyid(proowner) as owner, prosecdef, proconfig::text, proacl::text
from pg_proc where pronamespace='public'::regnamespace and proname='c1_is_approved_staff';
-- owner ต้องตรงตามเกณฑ์ข้อ 2.3 · prosecdef = true
-- proconfig ต้องมี search_path · proacl ต้องไม่มี anon และไม่มี PUBLIC

-- 4) ต้องไม่ recursion
select count(*) from public.user_profiles where user_id = auth.uid();
```

---

## 4. แผนทดสอบ — ปรับเป็น Read-only และระบุ BLOCKED

### 4.1 หลักการที่ใช้ปรับ

> **การ migration นี้แก้เฉพาะ `SELECT` policy** จึงไม่จำเป็นต้องทดสอบการเขียนข้อมูลเพื่อยืนยันว่าใช้ได้
> `UPDATE` policy และ trigger **ไม่ถูกแตะเลย** การทดสอบการแก้ `role`/`status`/`full_name` จึงไม่ได้พิสูจน์อะไรเกี่ยวกับการเปลี่ยนแปลงครั้งนี้

### 4.2 ทดสอบที่เป็น Read-only ล้วน

| # | ทดสอบ | วิธี | ต้องได้ |
|---|---|---|---|
| **A1** | anon อ่าน `user_profiles` | PostgREST + anon key · `limit=0` · `Prefer: count=exact` | **`HTTP 200` · `*/0`** (จาก `206 */3`) |
| **D1** | admin อ่าน `user_profiles` | PostgREST + token ของ admin | **`*/3` คงเดิม** |
| **P1** | หน้าแรก | เปิดดู (ไม่ล็อกอิน) | แสดงปกติ |
| **P2** | `/courses` | เปิดดู | **12 หลักสูตร** เหมือนเดิม |
| **P3** | `/sci-connect` | เปิดดู | แสดงข่าวปกติ |
| **P4** | `GET /api/sci-connect-news` | `curl` | **200** |
| **P5** | `GET /api/sci-connect-news-detail?slug=<ของจริง>` | `curl` | **200** |
| **D2** | ล็อกอิน `/admin/login` | เปิดดู | เข้าได้ |
| **D3** | `/admin/dashboard` | เปิดดู | จำนวนผู้ใช้ = **3** |
| **D4** | `/admin/users` | เปิดดู | เห็น **3 แถว** |
| **D5** | รายการเนื้อหาแสดงชื่อผู้สร้าง/ผู้แก้ไข | เปิดดู | เห็นเหมือนเดิม |
| **D6** | หน้าโปรไฟล์ **แสดง** `full_name` ตัวเอง | เปิดดู **ไม่กดบันทึก** | แสดงได้ |
| **M1** | `/healthz` | `GET` | `status=ok` · `authConfigured=true` · `dbConfigured=true` |
| **M2** | คอนเทนเนอร์ webapi | `docker ps` | `healthy` · restarts ไม่เพิ่ม |
| **M3** | `POST /api/admin/ingest` **ไม่มี token** | `curl` | **401** — ด่านปฏิเสธก่อนถึง handler **จึงไม่มีการเขียน** |
| **M4** | log ของ webapi | `docker logs` | ไม่มี `auth failed` ที่ไม่ได้ตั้งใจ |

> **D2–D6 ครอบคลุมเส้นทางอ่านทั้งหมดของผู้ดูแล** — D3 D4 D5 พิสูจน์ `select_staff` · D2 และ D6 พิสูจน์ว่าอ่านแถวตัวเองได้

> **M3 เป็น POST แต่ไม่เขียนข้อมูล** เพราะด่านปฏิเสธก่อนถึง handler · เคยทดสอบบน production แล้วได้ 401 จึงมีค่าอ้างอิงเดิม

### 4.3 เปลี่ยนจากแผนเดิม — 3 ข้อ

| เดิม | เปลี่ยนเป็น | เหตุผล |
|---|---|---|
| `POST /api/admin/extract-file` **พร้อม token** | **ต้องขออนุมัติแยก** ดูข้อ 4.4 | เป็น POST แม้จะไม่เขียนข้อมูล |
| แก้ `full_name` ของตัวเอง | **D6 — เปิดดูอย่างเดียว ไม่กดบันทึก** | การแก้เป็นการเขียนข้อมูล |
| แก้ `role` / `status` ของคนอื่น | **BLOCKED** | เขียนข้อมูล · และไม่ได้พิสูจน์อะไรเกี่ยวกับ migration นี้ |

### 4.4 รายการ BLOCKED

| # | ทดสอบ | เหตุผล | ผลต่อการตัดสินใจ |
|---|---|---|---|
| **B1** | `POST /api/admin/extract-file` พร้อม token ของ admin | เป็น POST · **ตรวจโค้ดแล้วว่าไม่เขียนข้อมูลใด ๆ** (`extract-file.js` เรียก supabase 0 ครั้ง · `fileExtract.js` ไม่มี side effect) แต่ขัดกับข้อห้ามรอบนี้ | **ครอบแทนได้บางส่วน** ด้วย D2 (ล็อกอินเข้าหน้าผู้ดูแลได้ = อ่าน `role, status` ตัวเองสำเร็จ) |
| **B2** | แก้ `role` / `status` ของคนอื่น | เขียนข้อมูลจริง | **ไม่จำเป็น** — ไม่แตะ `UPDATE` policy |
| **B3** | แก้ `full_name` ของตัวเอง | เขียนข้อมูลจริง | **ไม่จำเป็น** — เหตุผลเดียวกัน |
| **B4** | ทดสอบบัญชี `editor` และ `user` ทั่วไป | **ไม่มีบัญชี** และ **ไม่มีช่องทางล็อกอินสำหรับผู้ใช้ทั่วไป** | **ไม่มีผู้ใช้ที่กระทบ** |

### 4.5 ช่องว่างที่เหลือจากการทำให้เป็น read-only

| ช่องว่าง | ความสำคัญ | ครอบแทนด้วย |
|---|---|---|
| เส้นทาง M3 `requireAdminUser` ไม่ถูกยิงด้วย token จริง | **กลาง** | D2 — ถ้าล็อกอินเข้าหน้าผู้ดูแลได้ แปลว่าการอ่าน `role, status` ของตัวเองผ่าน RLS สำเร็จ ซึ่งเป็นเงื่อนไขเดียวกับที่ M3 ต้องการ |
| | | **แต่ใช้ client คนละตัว** — SPA อ่านจากเบราว์เซอร์ · M3 อ่านจากเซิร์ฟเวอร์ด้วย token ที่ส่งมา |

> **ถ้าต้องการปิดช่องว่างนี้ ขออนุมัติทดสอบ B1 แยก** — เป็นคำขอเดียว ไม่เขียนข้อมูล และเคยทดสอบบน production มาแล้วตอน deploy M3 โดยได้ 200

---

## 5. ยืนยันว่าผู้ใช้ทั่วไปใช้ AI โดยไม่ล็อกอิน

### 5.1 หลักฐานจากโค้ดและเส้นทาง

| หลักฐาน | ที่มา |
|---|---|
| `/api/chat` ถูก rewrite เป็น `/chat-web` แล้วส่งไป `backend:8000` | [`Caddyfile:20-22`](Caddyfile) |
| FastAPI **ไม่ได้ต่อ Supabase เลย** | `grep -rn "supabase" backend/ --include="*.py"` → ไม่พบ |
| endpoint ที่ SPA ใช้ไม่มี `get_current_user` และไม่มี `require_admin` | `backend/app/api/routes/web_compat.py` (บันทึกไว้ใน `AUTH_ARCHITECTURE_AUDIT.md`) |
| หน้า `/chat` ไม่เรียก Supabase `user_profiles` | สำรวจ SPA ครบ 8 รูปแบบ ทั้งหมดอยู่หลังการตรวจล็อกอิน |

### 5.2 หลักฐานจากการสังเกตจริง

| หลักฐาน | รายละเอียด |
|---|---|
| เบราว์เซอร์ที่ใช้ตรวจ **ไม่มี auth token เลย** | `Object.keys(localStorage).filter(k=>k.startsWith('sb-'))` → **0 รายการ** |
| ถาม AI สำเร็จในสถานะไม่ล็อกอิน | รอบก่อนหน้าถาม *"หลักสูตรคณิตศาสตร์เรียนกี่หน่วยกิต"* แล้วได้คำตอบพร้อมแหล่งอ้างอิง `ma69.pdf หน้า 1` · ขณะนั้นเบราว์เซอร์ไม่มี token เช่นกัน |

> **ไม่ทดสอบซ้ำในรอบนี้** เพราะการถาม AI สร้างแถวใน `chat_sessions` และ `chat_messages` ของ PostgreSQL จริง ซึ่งขัดกับข้อห้าม

### 5.3 ข้อสรุป

**ผู้ใช้ทั่วไปใช้ AI ได้โดยไม่ล็อกอิน และเส้นทางนั้นไม่แตะ Supabase `user_profiles` เลย** → **การแก้ RLS ไม่กระทบฟีเจอร์หลักของผู้ใช้**

---

## 6. GO / NO-GO

### 6.1 สถานะ

# `NO-GO` ชั่วคราว

**ไม่ใช่เพราะพบปัญหา** แต่เพราะเหลือการตรวจ 1 ข้อที่ใช้เวลาไม่ถึงนาที และถ้าข้ามไปแล้วผิดจะทำให้ระบบผู้ดูแลใช้ไม่ได้ชั่วคราว

### 6.2 เงื่อนไขที่ต้องครบ

| # | เงื่อนไข | สถานะ |
|---|---|---|
| 1 | รู้ `SELECT` policy เดิมครบ | **ผ่าน** |
| 2 | รู้ `UPDATE` policy และ trigger ครบ | **ผ่าน** |
| 3 | ยืนยันตัวกัน `role`/`status` ทำงาน | **ผ่าน** |
| 4 | `rls_forced = false` | **ผ่าน** |
| 5 | ไม่มี view/ฟังก์ชันอ่านอ้อม | **ผ่านในขอบเขตที่ตรวจ** |
| 6 | ชื่อฟังก์ชันใหม่ไม่ซ้ำ | **ผ่าน** |
| 7 | มี baseline A1 และ D1 | **ผ่าน** — `206 */3` ทั้งคู่ |
| 8 | ยืนยันผู้ใช้ทั่วไปไม่ล็อกอินและไม่แตะตารางนี้ | **ผ่าน** |
| 9 | Migration และ Rollback ถูกต้องปลอดภัย | **ผ่านหลังแก้ 2 จุด** — ข้อ 3.2 และ 3.3 |
| **10** | **เจ้าของฟังก์ชันใหม่ข้าม RLS ได้** | **ยังไม่มีหลักฐาน** ← **เหลือข้อเดียว** |

**ผ่าน 9 จาก 10**

### 6.3 สิ่งที่ต้องทำก่อนขออนุมัติ

| # | สิ่งที่ต้องทำ | เวลาที่ใช้ |
|---|---|---|
| **1** | **รันคำสั่งตรวจเจ้าของตามข้อ 2.2** แล้วเทียบเกณฑ์ข้อ 2.3 | ไม่ถึงนาที |
| 2 | ใช้ migration และ rollback ฉบับข้อ 3.2 และ 3.3 **เท่านั้น** ทิ้งฉบับในเอกสารก่อนหน้า | — |
| 3 | เตรียม `PROJECT_REF` และ `ANON_KEY` จาก Dashboard ไว้วัด A1 | สั้น |
| 4 | เตรียม token ของ admin ไว้วัด D1 | สั้น |
| 5 | เปิด rollback ค้างไว้ในหน้าต่างอื่นก่อนกด migration | — |
| 6 | ตัดสินใจว่าจะขออนุมัติทดสอบ **B1** แยกหรือไม่ (ข้อ 4.5) | — |

### 6.4 NO-GO ระหว่าง apply

| อาการ | ทำอะไร |
|---|---|
| `function ... already exists` | **หยุด** — มีคนสร้างชื่อนี้ระหว่างนี้ |
| `policy ... does not exist` ตอน `drop policy` | **หยุด** — ชื่อ policy เปลี่ยนไป ตรวจใหม่ |
| `infinite recursion detected in policy` | **rollback ทันที** |
| ข้อ 3.4 ข้อ 1 ยังเจอ `qual = 'true'` | **หยุด** — ถอดไม่ครบ |
| ข้อ 3.4 ข้อ 2 ได้ไม่ครบ | **หยุด** — เผลอลบของเดิม |
| **A1 หลังแก้ไม่ได้ `*/0`** | **หยุด** — ช่องโหว่ยังเปิด |
| **D1 หลังแก้ลดจาก `*/3`** | **rollback** — ฟังก์ชันไม่ทำงาน |
| ล็อกอิน `/admin/login` ไม่ได้ | **rollback ทันที** |
| M3 `/healthz` ไม่ตอบ หรือ `dbConfigured=false` | **rollback** |

### 6.5 ความเสี่ยงที่ยอมรับ

| # | ความเสี่ยง | ทำไมยอมรับได้ |
|---|---|---|
| 1 | เส้นทาง M3 ไม่ถูกยิงด้วย token จริง (B1) | D2 ครอบบางส่วน · เคยผ่านมาแล้วตอน deploy M3 |
| 2 | `editor` และ `user` ทั่วไปทดสอบไม่ได้ | **ไม่มีบัญชีและไม่มีช่องทางล็อกอิน** — ไม่มีผู้ใช้ที่กระทบ |
| 3 | `TRUNCATE` ของ `anon` ยังอยู่ | เรียกผ่าน PostgREST ตรงไม่ได้ · เป็นงานแยก |
| 4 | ฟังก์ชันเดิม 2 ตัวไม่มี `search_path` | การอ้างอิงภายในระบุ schema แล้ว |

---

## 7. แยกสิ่งที่ยืนยันแล้วกับที่ยังต้องตรวจ

### ✅ ยืนยันแล้ว

1. `SELECT` policy เดิมมีตัวเดียวและเป็น `USING (true)`
2. `UPDATE` policy 2 ตัวและ trigger 3 ตัว รู้ชื่อและนิยามครบ
3. ตัวกัน `role`/`status` ทำงานจริง อ่านโค้ดเต็มแล้ว
4. `rls_forced = false`
5. ไม่มี view หรือฟังก์ชันอ่านอ้อมในขอบเขตที่ตรวจ
6. ไม่มีฟังก์ชันชื่อ `c1_is_approved_staff` อยู่ก่อน
7. Baseline A1 `206 */3` · D1 `206 */3` · ตารางมี 3 แถว
8. ผู้ใช้ทั่วไปใช้ AI โดยไม่ล็อกอิน และเส้นทางนั้นไม่แตะ Supabase
9. FastAPI ใช้ตารางชื่อซ้ำแต่**คนละฐานข้อมูล** จึงไม่กระทบ
10. Migration และ Rollback ถูกต้องหลังแก้ 2 จุด

### ⏳ ยังต้องตรวจ

1. **เจ้าของฟังก์ชันใหม่จะข้าม RLS ของ `public.user_profiles` ได้หรือไม่** — คำสั่งอยู่ในข้อ 2.2

### ⛔ BLOCKED (ยอมรับความเสี่ยง)

1. `POST /api/admin/extract-file` พร้อม token — ต้องขออนุมัติแยก
2. การแก้ `role` / `status` / `full_name` — เขียนข้อมูล และไม่จำเป็นต่อ migration นี้
3. บัญชี `editor` — ไม่มีบัญชี
4. บัญชี `user` ทั่วไป — ไม่มีช่องทางล็อกอิน

---

## 8. ยืนยันขอบเขต

| ข้อห้าม | สถานะ |
|---|---|
| แก้โค้ด ฐานข้อมูล production หรือ Supabase | **ไม่ได้ทำ** |
| รัน migration · rollback · SQL ที่เปลี่ยนสิทธิ์ | **ไม่ได้ทำ** |
| Deploy / Restart / Push / Merge | **ไม่ได้ทำ** |
| ทดสอบ API ที่สร้างหรือเปลี่ยนข้อมูลจริง | **ไม่ได้ทำ** — ไม่ได้ถาม AI ซ้ำ ไม่ได้ยิง endpoint ใด ๆ ในรอบนี้ |
| เปิดเผยข้อมูลส่วนบุคคล | **ไม่มีในเอกสารนี้** |

```
Local  HEAD 427ce19 · mko-phase2 · ไฟล์โค้ดที่แก้ 0
Prod   webapi d2663f039a18 · running · healthy · บริการอื่นไม่ถูกแตะ
```

**สถานะ: `NO-GO` ชั่วคราว — รันคำสั่งข้อ 2.2 แล้วถ้าผ่านเกณฑ์ข้อ 2.3 จะเป็น `GO` ทันที**
