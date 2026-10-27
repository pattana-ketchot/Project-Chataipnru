# C1 — วิเคราะห์ผลกระทบของ RLS Migration ต่อ SCI Advisor

> **READ-ONLY** — ไม่แก้โค้ด ไม่แก้ฐานข้อมูล ไม่รัน SQL ที่เปลี่ยนข้อมูลหรือสิทธิ์ ไม่ deploy ไม่ restart ไม่ push/merge

| รายการ | ค่า |
|---|---|
| วันที่ | 11 ตุลาคม 2569 |
| ขอบเขต | ผลกระทบของการเปลี่ยน `SELECT` RLS ของ **Supabase** `public.user_profiles` |
| ผลสรุป | **`PASS` — พร้อมขออนุมัติ migration** |

---

## ผลสรุปใน 30 วินาที

| # | ประเด็น | ผล |
|---|---|---|
| 1 | หน้าเว็บสาธารณะและการถาม AI | **ไม่กระทบเลย** — ไม่แตะ Supabase `user_profiles` ในทุกเส้นทาง |
| 2 | FastAPI backend | **ไม่กระทบเลย** — ไม่ได้ต่อ Supabase และตารางชื่อเดียวกันที่ใช้อยู่เป็น**คนละตาราง** |
| 3 | หน้าผู้ดูแล | **ไม่กระทบ** ถ้าฟังก์ชันทำงาน |
| 4 | M3 WebAPI | **ไม่กระทบ** — อ่านแถวตัวเอง |
| 5 | ความเสี่ยงหลักที่เหลือ | **RLS recursion** — ล้มแบบเห็นชัด ย้อนได้ทันที |

**ความเสี่ยงต่ำกว่าที่ประเมินไว้ตอนแรกมาก** เพราะบริบทใหม่สองข้อ — **เว็บฝั่งผู้ใช้ไม่มีระบบล็อกอิน** และ **ตารางมีแค่ 3 แถว**

---

## 1. ⚠ เรื่องที่ต้องแยกให้ชัดก่อนอ่านต่อ — มีตารางชื่อซ้ำกันสองตาราง

นี่คือจุดที่สับสนได้ง่ายที่สุดและอาจทำให้ประเมินผลกระทบผิดทั้งหมด

| | **Supabase** `public.user_profiles` | **PostgreSQL ของเรา** `public.user_profiles` |
|---|---|---|
| จำนวนแถว | **3** | **11** |
| คอลัมน์หลัก | `user_id`, `role`, `status`, `full_name`, `email` | `user_id`, `education_level`, `field_of_study`, `career_goal`, `skills`, `interests` |
| เก็บอะไร | **สิทธิ์และตัวตนของผู้ดูแล** | **ข้อมูลการศึกษาและความสนใจของผู้ใช้** |
| ใครใช้ | SPA ของทีมออกแบบ · M3 WebAPI | FastAPI backend |
| นิยามอยู่ที่ | Supabase (จัดการผ่าน Dashboard) | [`backend/app/models/user.py:28`](backend/app/models/user.py) |
| **C1 กระทบไหม** | **ใช่** | **ไม่เลย** |

> **คนละฐานข้อมูล คนละ schema คนละวัตถุประสงค์ บังเอิญชื่อซ้ำกัน**
> การแก้ RLS ของ Supabase **ไม่มีทางกระทบ** ตารางของ FastAPI เพราะอยู่คนละเซิร์ฟเวอร์ และ FastAPI ไม่ได้ต่อ Supabase เลย

### หลักฐาน

```
grep -rn "supabase" backend/ --include="*.py"   ->  ไม่พบเลย
```

[`backend/app/db/session.py:17`](backend/app/db/session.py) สร้าง engine จาก `DATABASE_URL` เดียว ซึ่งชี้ไปที่ PostgreSQL ของเรา

---

## 2. จุดที่เรียก Supabase `user_profiles` — ครบทุกที่

### 2.1 M3 WebAPI (รีโปของเรา)

| ไฟล์ | บรรทัด | คำสั่ง | ขอบเขต | อ่านในนามใคร |
|---|---|---|---|---|
| [`webapi/auth.mjs`](webapi/auth.mjs) | **312** | `.from("user_profiles").select("role, status").eq("user_id", userId).single()` | **แถวตัวเอง** | ผู้เรียก (client ผูกกับ token ของผู้เรียก) |
| [`webapi/api/_lib/adminAuth.js`](webapi/api/_lib/adminAuth.js) | **31** | `.from('user_profiles').select('role, status').eq('user_id', user.id).single()` | **แถวตัวเอง** | ผู้เรียก |

โค้ดมีคอมเมนต์กำกับที่ [`adminAuth.js:5-7`](webapi/api/_lib/adminAuth.js) ว่า *"ใช้ supabase client ที่ scope ด้วย token ของผู้เรียกเอง (ไม่ใช่ shared key) เพื่อให้ RLS บังคับด้วยตัวตนจริงของผู้เรียกด้วย"*

### 2.2 SPA ของทีมออกแบบ (`/srv/web` → `/home/ubuntu/course-advisor-system/web`)

พบ **8 รูปแบบ ไม่มี `INSERT` และไม่มี `DELETE`**

| # | คำสั่ง | ขอบเขต | ใช้ที่ไหน | ต้องล็อกอินไหม |
|---|---|---|---|---|
| 1 | `.select("role, status").eq("user_id", <ตัวเอง>).single()` | ตัวเอง | ตรวจสิทธิ์ก่อนเข้าหน้าผู้ดูแล (2 จุด) | **ใช่** |
| 2 | `.select("full_name").eq("user_id", <ตัวเอง>).single()` | ตัวเอง | หน้าโปรไฟล์ผู้ดูแล | **ใช่** |
| 3 | `.update({ full_name }).eq("user_id", <ตัวเอง>)` | ตัวเอง | หน้าโปรไฟล์ผู้ดูแล | **ใช่** |
| 4 | `.select("user_id, full_name, email").in("user_id", [...])` | **คนอื่น** | แสดงชื่อผู้สร้าง/ผู้แก้ไขในรายการเนื้อหา | **ใช่** |
| 5 | `.select("id", { count:"exact", head:true })` | **ทั้งตาราง** | แดชบอร์ดผู้ดูแล | **ใช่** |
| 6 | `.select("id, user_id, role, status, full_name, email, created_at")` | **ทั้งตาราง** | หน้า `/admin/users` | **ใช่** |
| 7 | `.update({ role }).eq("user_id", <คนอื่น>)` | คนอื่น | `/admin/users` | **ใช่** |
| 8 | `.update({ status }).eq("user_id", <คนอื่น>)` | คนอื่น | `/admin/users` | **ใช่** |

### 2.3 FastAPI Backend

**ไม่มีจุดใดเลย** — ดูข้อ 1

---

## 3. แยกการใช้งาน Anonymous กับ Admin

### 3.1 ผู้ใช้ทั่วไป (ไม่ล็อกอิน) — เส้นทางทั้งหมด

| สิ่งที่ผู้ใช้ทำ | เส้นทาง | ปลายทาง | แตะ Supabase `user_profiles` ไหม |
|---|---|---|---|
| เปิดหน้าแรก | `/` | ไฟล์ static ที่ `/srv/web` | **ไม่** |
| ดูหลักสูตร | `/courses` | Supabase ตาราง `courses` | **ไม่** |
| เปรียบเทียบสาขา | `/api/compare-courses` | **FastAPI backend** | **ไม่** |
| ค้นหาสาขาที่เหมาะ | `/api/recommend-major` | **FastAPI backend** | **ไม่** |
| **ถาม AI** | `/api/chat` → rewrite `/chat-web` | **FastAPI backend** → PostgreSQL + Ollama | **ไม่** |
| อ่านข่าว | `/api/sci-connect-news` | webapi → Supabase ตาราง `external_news` | **ไม่** |

เส้นทางจาก [`Caddyfile:20-45`](Caddyfile)

```
handle /api/chat              -> rewrite /chat-web -> backend:8000
handle /api/sci-connect-news* -> webapi:3001
handle /api/admin/*           -> webapi:3001
handle /api/*                 -> backend:8000
handle (ที่เหลือ)              -> file_server /srv/web
```

### 3.2 ⭐ หลักฐานสำคัญ — ผู้ไม่ล็อกอินไม่เคยไปถึง query เลย

ทั้งสองจุดที่อ่าน `role, status` ใน SPA **มีการตรวจก่อนเสมอ**

```js
// จุดที่ 1
const { data: { user } } = await D.auth.getUser();
if (!user) return { user: null, role: null, status: null };   // <- ออกก่อน
const { data } = await D.from("user_profiles").select("role, status")...

// จุดที่ 2
const { data: { user: u } } = await D.auth.getUser();
if (!u) { Sr = null; t("/admin/login"); return; }              // <- ออกก่อน
const { data: d } = await D.from("user_profiles").select("role, status")...
```

**ผู้ใช้ที่ไม่ล็อกอินจะถูกส่งกลับหรือคืนค่าว่างก่อนถึงบรรทัดที่ query เสมอ**

### 3.3 แล้วทำไม A1 baseline ถึงอ่านได้ 3 แถว

เพราะ **policy อนุญาต** ไม่ใช่เพราะแอปเรียกใช้

| | |
|---|---|
| แอปเรียกใช้ไหม | **ไม่** |
| ใครก็ตามที่มี anon key เรียกเองได้ไหม | **ได้** — `HTTP 206 · Content-Range */3` |
| anon key หาได้จากไหน | อยู่ใน JavaScript ของหน้าเว็บตามธรรมชาติ |

> **นี่คือสาระของ R1** — เป็น**ความสามารถที่เปิดทิ้งไว้** ไม่ใช่ความสามารถที่ระบบใช้งาน
> **การปิดจึงเป็นการถอดสิ่งที่ไม่มีใครใช้ ไม่ใช่การตัดฟีเจอร์**

### 3.4 ผู้ดูแล (ล็อกอินแล้ว)

| การใช้งาน | ต้องอ่านอะไร | หลัง migration |
|---|---|---|
| ตรวจสิทธิ์ตอนเข้าหน้า | แถวตัวเอง | `select_own` ครอบ |
| หน้าโปรไฟล์ | แถวตัวเอง | `select_own` ครอบ |
| แดชบอร์ด (นับผู้ใช้) | ทั้งตาราง | `select_staff` ครอบ |
| รายการเนื้อหา (ชื่อผู้เขียน) | คนอื่น | `select_staff` ครอบ |
| `/admin/users` | ทั้งตาราง | `select_staff` ครอบ |
| M3 `/api/admin/*` | แถวตัวเอง | `select_own` หรือ `select_staff` ครอบ |

---

## 4. ผลกระทบของการเปลี่ยน `SELECT` RLS

### 4.1 ก่อนและหลัง

| ผู้เรียก | ก่อน | หลัง | กระทบฟีเจอร์ไหน |
|---|---|---|---|
| **anon** | อ่านได้ **3 แถว** | **0 แถว** | **ไม่มีเลย** — แอปไม่เคยเรียก |
| ผู้ใช้ล็อกอินที่ไม่ใช่ staff | อ่านได้ 3 แถว | **1 แถว (ของตัวเอง)** | **ไม่มีใครอยู่ในกลุ่มนี้** — ไม่มีช่องทางล็อกอินสำหรับผู้ใช้ทั่วไป |
| `admin` ที่ `approved` | 3 แถว | **3 แถว (คงเดิม)** | **ไม่มี** |
| `editor` ที่ `approved` | 3 แถว | 3 แถว (คงเดิม) | **ไม่มีบัญชีประเภทนี้** |

### 4.2 ฟีเจอร์ที่ตรวจแล้วว่าไม่กระทบ

| ฟีเจอร์ | เหตุผล |
|---|---|
| **ถาม AI โดยไม่ล็อกอิน** | ไปที่ FastAPI ไม่แตะ Supabase เลย |
| ค้นหาสาขาที่เหมาะ · เปรียบเทียบหลักสูตร | FastAPI |
| ดูรายการหลักสูตร · ข่าว | Supabase ตารางอื่น ไม่ใช่ `user_profiles` |
| ล็อกอินผู้ดูแล | Supabase Auth ไม่อ่าน `user_profiles` ตอนล็อกอิน |
| หน้าผู้ดูแลทั้งหมด | `select_staff` ครอบ |
| M3 `/api/admin/*` | อ่านแถวตัวเอง |
| `UPDATE` role/status | **ไม่แตะ policy UPDATE เลย** |
| สมัครสมาชิก | `handle_new_user()` เป็น `SECURITY DEFINER` และไม่แตะ `SELECT` policy |

### 4.3 ข้อสังเกต — `select_own` แทบไม่มีผู้ใช้จริงวันนี้

ด้วยบริบทที่ **ไม่มีช่องทางล็อกอินสำหรับผู้ใช้ทั่วไป** และตารางมี 3 แถว

| | |
|---|---|
| ใครที่ `select_own` ครอบแต่ `select_staff` ไม่ครอบ | ผู้ที่ล็อกอินได้แต่ไม่ใช่ staff ที่ approved |
| มีกี่คน | **อย่างมาก 1 คน** (3 แถว ลบ admin ที่ approved 2 คน) |
| คนนั้นล็อกอินได้ไหม | ได้เฉพาะผ่าน `/admin/login` |

`select_own` จึงเป็นการป้องกันเชิงโครงสร้างที่ถูกต้อง แต่ **ไม่ใช่เส้นทางที่มีทราฟฟิกจริงวันนี้**

---

## 5. ความเสี่ยง SECURITY DEFINER และ RLS Recursion

### 5.1 กลไก

policy `select_staff` เรียกฟังก์ชัน `c1_is_approved_staff()` ซึ่งอ่าน `user_profiles` **ถ้าฟังก์ชันไม่ข้าม RLS จะวนกลับมาประเมิน policy เดิมไม่รู้จบ**

### 5.2 หลักฐานที่สนับสนุนว่าจะไม่เกิด

| หลักฐาน | น้ำหนัก |
|---|---|
| `rls_forced = false` (ยืนยันแล้ว) | สูง — เจ้าของตารางข้าม RLS ได้ |
| `guard_user_profile_privileges()` เป็น `SECURITY DEFINER` ที่ `SELECT` จากตารางนี้ และ**ทำงานอยู่ทุกวันนี้** | **สูงที่สุด** — พิสูจน์ว่ากลไกใช้ได้จริงในฐานข้อมูลนี้ |
| ไม่มี view หรือฟังก์ชันอื่นที่อ่านตารางนี้ | กลาง |
| ชื่อ `c1_is_approved_staff` ยังไม่มีอยู่ | ยืนยันแล้ว — ไม่ทับของเดิม |

### 5.3 ความต่างที่ยังทำให้ต้องทดสอบ

| | `guard_user_profile_privileges()` | `c1_is_approved_staff()` |
|---|---|---|
| ถูกเรียกจาก | **Trigger ของ `UPDATE`** | **RLS policy ของ `SELECT`** |
| จังหวะที่ทำงาน | **หลัง** ตัดสินใจเรื่อง policy แล้ว | **ระหว่าง** การตัดสินใจนั้น |
| ถ้าข้าม RLS ไม่สำเร็จ | เห็นแถวน้อยลง | **recursion** |

> **สรุป: มีหลักฐานหนักแน่น แต่ไม่ใช่การพิสูจน์** — ต้องทดสอบ

### 5.4 มาตรการในฟังก์ชันใหม่

| มาตรการ | ป้องกันอะไร |
|---|---|
| `security definer` | ข้าม RLS → ไม่ recursion |
| `set search_path = pg_catalog, public` | กันการสวม `search_path` · **ดีกว่าฟังก์ชันเดิมทั้งสองที่ `proconfig = NULL`** |
| `stable` | ลดการเรียกซ้ำต่อแถว |
| คืน `boolean` เท่านั้น | ไม่กลายเป็นช่องทางดึงข้อมูล |
| `revoke all ... from public, anon` แล้ว `grant execute ... to authenticated` | `anon` เรียกไม่ได้ |
| ชื่อขึ้นต้น `c1_` + ใช้ `create` ไม่ใช่ `create or replace` | ไม่ทับของเดิม · ล้มเสียงดังถ้าชื่อซ้ำ |

### 5.5 ลักษณะการล้มถ้าเกิดปัญหา

| คำถาม | คำตอบ |
|---|---|
| เห็นทันทีไหม | **เห็น** — `infinite recursion detected in policy` |
| ล้มแบบเปิดสิทธิ์ไหม | **ไม่** — อ่านไม่ได้เลย ไม่ใช่อ่านได้หมด |
| ย้อนได้ไหม | **ได้ทันที** |
| ข้อมูลเสียหายไหม | **ไม่** — ไม่มีคำสั่งใดแตะข้อมูล |

---

## 6. แผนทดสอบหลัง Migration

### 6.1 ขั้นที่ 1 — ตรวจโครงสร้าง (SQL Editor ใช้ได้)

```sql
-- 1.1 ต้องไม่เหลือ policy ที่เปิดให้อ่าน
select policyname, cmd, permissive, roles::text, qual
from pg_policies
where schemaname='public' and tablename='user_profiles' and cmd in ('SELECT','ALL');
-- ต้องไม่มีแถวใดที่ qual = 'true'

-- 1.2 ของเดิมต้องครบ
select policyname from pg_policies
where schemaname='public' and tablename='user_profiles' and cmd='UPDATE';   -- ต้องได้ 2

select tgname from pg_trigger
where tgrelid='public.user_profiles'::regclass and not tgisinternal;        -- ต้องได้ 2

-- 1.3 ฟังก์ชันใหม่ถูกต้อง
select proname, pg_get_userbyid(proowner) as owner, prosecdef, proconfig::text, proacl::text
from pg_proc where pronamespace='public'::regnamespace and proname='c1_is_approved_staff';
-- owner ต้องเท่ากับเจ้าของตาราง · prosecdef = true
-- proconfig ต้องมี search_path · proacl ต้องไม่มี anon และไม่มี PUBLIC
```

### 6.2 ขั้นที่ 2 — วัด RLS จริง (ต้องผ่าน PostgREST เท่านั้น)

> **ห้ามใช้ SQL Editor วัดขั้นนี้** — รันด้วย role สิทธิ์สูงที่ข้าม RLS จะเห็น 3 แถวเสมอ

| ข้อ | บริบท | ค่าฐาน | หลังแก้ต้องได้ |
|---|---|---|---|
| **A1** | anon | `HTTP 206` · `*/3` | **`HTTP 200` · `*/0`** |
| **D1** | admin | `HTTP 206` · `*/3` | **`*/3` คงเดิม** |
| U1 | user ทั่วไป | — | ⛔ **ไม่มีช่องทางล็อกอิน — ทดสอบไม่ได้** |
| E1 | editor | — | ⛔ **ไม่มีบัญชี — ทดสอบไม่ได้** |

> **`HTTP 200` + `*/0` คือผลที่ถูกต้องสำหรับ A1** ไม่ใช่ `403` · RLS ที่ปฏิเสธทุกแถวให้ `200` พร้อมผลว่าง
> รหัสเปลี่ยนจาก `206` เป็น `200` เพราะไม่มีเนื้อหาบางส่วนให้ส่งแล้ว

### 6.3 ขั้นที่ 3 — ทดสอบการใช้งานจริงของผู้ใช้ทั่วไป (ไม่ล็อกอิน)

**ใช้หน้าต่างส่วนตัวหรือเบราว์เซอร์ที่ไม่ได้ล็อกอิน**

| # | ทดสอบ | ต้องได้ |
|---|---|---|
| P1 | เปิดหน้าแรก | แสดงปกติ |
| P2 | `/courses` แสดงรายการหลักสูตร | **12 หลักสูตร** เหมือนเดิม |
| P3 | **ถาม AI ที่หน้า `/chat`** เช่น *"หลักสูตรคณิตศาสตร์เรียนกี่หน่วยกิต"* | **ได้คำตอบพร้อมแหล่งอ้างอิง** |
| P4 | `/find-major` ทำแบบสอบถามจนจบ | ได้ผลแนะนำ |
| P5 | `/compare` เปรียบเทียบสองหลักสูตร | ได้ตารางเปรียบเทียบ |
| P6 | `/sci-connect` ดูข่าว | แสดงข่าวปกติ |

> **P3 สำคัญที่สุดสำหรับผู้ใช้ทั่วไป** เพราะเป็นฟีเจอร์หลักของระบบ · ตรวจแล้วว่าไม่แตะ Supabase `user_profiles` เลย จึง**ไม่ควรกระทบ** แต่ต้องยืนยันด้วยตา

### 6.4 ขั้นที่ 4 — ทดสอบหน้าผู้ดูแล

| # | ทดสอบ | ต้องได้ |
|---|---|---|
| D2 | ล็อกอิน `/admin/login` | เข้าได้ |
| D3 | `/admin/dashboard` | ตัวเลขครบ · จำนวนผู้ใช้ = **3** |
| D4 | `/admin/users` | เห็นครบ **3 แถว** |
| D5 | หน้าโปรไฟล์ แสดงและแก้ `full_name` ตัวเอง | สำเร็จ |
| D6 | รายการเนื้อหาแสดงชื่อผู้สร้าง/ผู้แก้ไข | เห็นเหมือนเดิม |
| D7 | แก้ `status` ของแถวอื่นใน `/admin/users` | สำเร็จ |

### 6.5 ขั้นที่ 5 — ทดสอบ M3 WebAPI

| # | ทดสอบ | ต้องได้ |
|---|---|---|
| M1 | `/healthz` | `status=ok` · `authConfigured=true` · `dbConfigured=true` |
| M2 | คอนเทนเนอร์ | `healthy` · restarts ไม่เพิ่ม |
| M3 | `GET /api/sci-connect-news` | **200** |
| M4 | `POST /api/admin/ingest` **ไม่มี token** | **401** |
| M5 | **`POST /api/admin/extract-file` พร้อม token ของ admin** | **200** |
| M6 | log ของ webapi | ไม่มี `auth failed` ที่ไม่ได้ตั้งใจ |

> **M5 คือข้อชี้ขาด** — ถ้าได้ 403 แปลว่า `readProfile` อ่านแถวตัวเองไม่ได้ ต้อง rollback ทันที

### 6.6 ขั้นที่ 6 — เฝ้าดู

เฝ้า log และสถานะคอนเทนเนอร์ของ webapi อย่างน้อย 10 นาที

---

## 7. สรุป PASS / RISK / BLOCKED

### 7.1 รายข้อ

| # | ประเด็น | ผล | เหตุผล |
|---|---|---|---|
| 1 | หน้าเว็บสาธารณะ | **PASS** | ไม่แตะ `user_profiles` ในทุกเส้นทาง |
| 2 | **ถาม AI โดยไม่ล็อกอิน** | **PASS** | `/api/chat` → FastAPI → PostgreSQL + Ollama · **ไม่เกี่ยวกับ Supabase เลย** |
| 3 | FastAPI backend | **PASS** | ไม่ได้ต่อ Supabase · ตารางชื่อซ้ำเป็นคนละตาราง |
| 4 | หน้าผู้ดูแล | **PASS** | `select_staff` ครอบทุกการใช้งาน |
| 5 | M3 WebAPI | **PASS** | อ่านแถวตัวเองในนามผู้เรียก |
| 6 | `UPDATE` role/status | **PASS** | ไม่แตะ policy `UPDATE` และ trigger |
| 7 | สมัครสมาชิก | **PASS** | `handle_new_user()` เป็น `SECURITY DEFINER` |
| 8 | **RLS recursion** | **RISK** | หลักฐานหนักแน่นแต่ยังไม่พิสูจน์ · ล้มแบบเห็นชัดและย้อนได้ |
| 9 | ทดสอบ `editor` | **BLOCKED** | ไม่มีบัญชี · **ไม่มีผู้ใช้ที่กระทบ** |
| 10 | ทดสอบ `user` ทั่วไป | **BLOCKED** | **ไม่มีช่องทางล็อกอินในเว็บ** · ไม่มีผู้ใช้ที่กระทบ |
| 11 | `TRUNCATE` ของ `anon` | **RISK** | เรียกผ่าน PostgREST ตรงไม่ได้ · **เป็นงานแยกที่ต้องอนุมัติต่างหาก** |

### 7.2 ทำไม BLOCKED สองข้อไม่ขวางการ apply

| ข้อ | เหตุผล |
|---|---|
| `editor` | ยืนยันแล้วว่า **ไม่มีบัญชีประเภทนี้เลย** — ไม่มีใครพัง · เส้นทางในฟังก์ชันหลับอยู่ |
| `user` ทั่วไป | **เว็บไม่มีช่องทางล็อกอินสำหรับผู้ใช้ทั่วไป** — ไม่มีใครเข้ามาในสถานะนี้ได้ · ผู้ใช้ทั่วไปใช้ AI โดยไม่ล็อกอิน ซึ่งไม่แตะตารางนี้ |

> ทั้งสองเป็น **"ทดสอบไม่ได้เพราะไม่มีผู้ใช้"** ไม่ใช่ **"ทดสอบไม่ได้เพราะเข้าถึงไม่ได้"** — ความเสี่ยงจึงต่ำ

### 7.3 ผลรวม

# `PASS` — พร้อมขออนุมัติ migration

| เหตุผล | |
|---|---|
| 1 | **ฟีเจอร์หลักของผู้ใช้ทั่วไป (ถาม AI) ไม่เกี่ยวกับ Supabase เลย** — พิสูจน์จากเส้นทาง Caddy และจากการที่ FastAPI ไม่ต่อ Supabase |
| 2 | **แอปไม่เคยให้ผู้ไม่ล็อกอินอ่านตารางนี้** — มี `if (!user) return` กั้นทั้งสองจุด |
| 3 | **การปิดจึงถอดความสามารถที่ไม่มีใครใช้** ไม่ใช่ตัดฟีเจอร์ |
| 4 | ผู้ดูแลยังอ่านได้ครบผ่าน `select_staff` |
| 5 | ไม่แตะ `UPDATE` policy · trigger · สิทธิ์ของตาราง |
| 6 | ความเสี่ยงเดียวที่เหลือล้มแบบเห็นชัดและย้อนได้ทันทีโดยไม่มีข้อมูลเสียหาย |

### 7.4 ข้อเสนอแนะก่อนขออนุมัติ

| # | สิ่งที่ควรทำ | ความสำคัญ |
|---|---|---|
| 1 | **บันทึกค่าฐานไว้แล้ว** — A1 `206 */3` · D1 `206 */3` | เสร็จแล้ว |
| 2 | เตรียม token ของ admin ไว้ทดสอบ M5 | **จำเป็น** |
| 3 | เลือกเวลาที่คนใช้งานน้อย | แนะนำ |
| 4 | เตรียม rollback SQL ไว้ในหน้าต่างเดียวกัน พร้อมวาง | **จำเป็น** — ถ้า recursion ต้องย้อนทันที |
| 5 | ทดสอบ **P3 (ถาม AI โดยไม่ล็อกอิน)** ทันทีหลัง apply | **จำเป็น** — เป็นฟีเจอร์หลัก |
| 6 | บันทึกว่า E1 และ U1 ทดสอบไม่ได้ พร้อมเหตุผล | **จำเป็น** — อย่าข้ามเงียบ ๆ |
| 7 | ทดสอบ E1–E5 ทันทีที่มีบัญชี `editor` คนแรกในอนาคต | ผูกกับเหตุการณ์ |
| 8 | ขออนุมัติ `REVOKE TRUNCATE` แยกต่างหาก | งานถัดไป |

---

## 8. ไฟล์และตำแหน่งที่เกี่ยวข้อง

| ไฟล์ | บรรทัด | เกี่ยวอย่างไร |
|---|---|---|
| [`webapi/auth.mjs`](webapi/auth.mjs) | 312 | อ่าน `role, status` ของตัวเองในนามผู้เรียก |
| [`webapi/auth.mjs`](webapi/auth.mjs) | 127 | คอมเมนต์อธิบายสัญญาของ `readProfile` |
| [`webapi/api/_lib/adminAuth.js`](webapi/api/_lib/adminAuth.js) | 5–7 | คอมเมนต์ว่าใช้ token ของผู้เรียก ไม่ใช่ shared key |
| [`webapi/api/_lib/adminAuth.js`](webapi/api/_lib/adminAuth.js) | 31–35 | อ่าน `role, status` และตัดสิน 403 |
| [`webapi/auth.test.mjs`](webapi/auth.test.mjs) | 368 | ชุดทดสอบ *"อ่าน user_profiles ไม่ได้ ต้องไม่เดาว่ามีสิทธิ์"* |
| [`backend/app/models/user.py`](backend/app/models/user.py) | 28 | **ตารางชื่อซ้ำของ PostgreSQL เรา ไม่ใช่ของ Supabase** |
| [`backend/app/db/session.py`](backend/app/db/session.py) | 17 | ยืนยันว่า backend ต่อฐานข้อมูลเดียว |
| [`Caddyfile`](Caddyfile) | 20–45 | เส้นทางของทุกคำขอ |
| `/home/ubuntu/course-advisor-system/web/assets/*.js` | — | SPA ของทีมออกแบบ (อยู่นอกรีโปนี้) |

---

## 9. ยืนยันขอบเขต

| ข้อห้าม | สถานะ |
|---|---|
| แก้โค้ดหรือฐานข้อมูล | **ไม่ได้ทำ** |
| รัน SQL ที่เปลี่ยนข้อมูลหรือสิทธิ์ | **ไม่ได้ทำ** — อ่านอย่างเดียว |
| Deploy / Restart / Push / Merge | **ไม่ได้ทำ** |
| แก้ production หรือ Supabase | **ไม่ได้ทำ** — ไม่ได้เชื่อมต่อ Supabase เลย |
| เปิดเผยข้อมูลส่วนบุคคล | **ไม่มีในเอกสารนี้** |

```
Local  HEAD 427ce19 · mko-phase2 · ไฟล์โค้ดที่แก้ 0
Prod   webapi d2663f039a18 · running · healthy · บริการอื่นไม่ถูกแตะ
```

**สถานะ: `PASS` — พร้อมขออนุมัติ apply migration**
