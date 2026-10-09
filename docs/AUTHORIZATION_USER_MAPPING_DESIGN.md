# B1 Authorization + B2 User Mapping — Design

| | |
|---|---|
| วันที่ | 2026-10-02 |
| ขอบเขต | **DESIGN / AUDIT เท่านั้น** — ไม่มีการแก้โค้ดในรอบนี้ |
| Source of truth | `docs/SUPABASE_LIVE_VERIFICATION.md` · `docs/MIGRATION_005_FINAL_REVIEW.md` · โค้ดจริงของ 3 บริการ |
| **B1** | **READY** — ออกแบบได้ครบจากหลักฐานจริง |
| **B2** | **BLOCKED** — ขาดหลักฐาน 1 ชิ้นเดียว ดูข้อ 5 |

```
Production Write   NONE        Data Migration      NONE        Deploy / Restart   NONE
Apply Migration    NONE        แก้ Supabase        NONE        Commit / Push      NONE
Merge main         NONE
```

**การเข้าถึง production ในรอบนี้**: `SELECT` อย่างเดียวบน `public.users` เพื่อนับจำนวนและ
ดูโครงสร้าง · **ไม่ได้ดึงอีเมลหรือชื่อออกมาแม้แถวเดียว** · ไม่มีคำสั่งเขียน

---

## 0. ข้อค้นพบที่เปลี่ยนรูปของงาน B1

> **คำถามที่สั่งให้ตรวจ**: *"ตรวจว่าปัจจุบัน FastAPI รับ/ตรวจ Supabase JWT อย่างไร
> และ role มาจากไหน"*
>
> **คำตอบจากโค้ดจริง: FastAPI ไม่เคยเห็น Supabase JWT เลย**

`grep -rni 'supabase|anon_key|service_role|auth.uid|jwks|RS256' backend/ --include='*.py'`
คืนผลเพียง **4 บรรทัดซึ่งเป็นคอมเมนต์ทั้งหมด** ไม่มีโค้ดที่ตรวจ Supabase token แม้บรรทัดเดียว

ระบบจริงมี **auth สองชุดที่แยกกันสมบูรณ์** และ **สามบริการ** ไม่ใช่สองอย่างที่คิดไว้

```
                         Caddy  (Caddyfile)
                               |
   /api/chat ───────────────► backend:8000   /chat-web      FastAPI + JWT ของเราเอง
   /api/sci-connect-news* ──► webapi:3001                   Supabase anon key
   /api/admin/* ───────────► webapi:3001                    Supabase JWT + user_profiles
   /api/* ─────────────────► backend:8000                   FastAPI + JWT ของเราเอง
   ที่เหลือ ────────────────► ไฟล์ static ของ SPA
                               |
   SPA ในเบราว์เซอร์ ─────────────────────────► Supabase PostgREST ตรง ๆ (anon key)
                                                 ← ทางนี้คือทางหลักของข้อมูลทั้งหมด
```

### 0.1 ทางที่ข้อมูลเดินจริงในวันนี้

นับการเรียกตาราง Supabase **ตรงจากเบราว์เซอร์** ใน `src/` ของ SPA

| ตาราง | select | insert | update | delete |
|---|---:|---:|---:|---:|
| `courses` | 6 | 1 | 1 | 1 |
| `knowledge_articles` | 4 | 1 | 1 | 1 |
| `news` | 3 | 1 | 1 | — |
| `user_profiles` | 2 | — | 3 | — |
| `ai_settings` | 2 | — | — | — |
| `rag_documents` | — | — | — | 3 |

`external_news` เป็นตารางเดียวที่อ่านผ่าน API (`/api/sci-connect-news`) ส่วน
`storage` ถูกเรียกตรงจาก `src/lib/courseStorage.js` และ `src/lib/knowledgeStorage.js`

**แปลว่า**: วันนี้ **ไม่มีชั้น API อยู่หน้าข้อมูลเลย** สำหรับเกือบทุกการทำงาน
เบราว์เซอร์คุย PostgREST ตรงด้วย anon key และ **RLS คือการควบคุมสิทธิ์ทั้งหมดที่มี**

### 0.2 ผลที่ตามมาต่องาน B1

งานนี้จึง **ไม่ใช่** "ย้ายการตรวจสิทธิ์จาก RLS ไปที่ API ที่มีอยู่แล้ว"
แต่คือ **"สร้างชั้น API ที่ยังไม่มี"** ขึ้นมาใหม่สำหรับทุกตารางที่ SPA แตะ
พร้อมกับแก้ SPA ให้เลิกคุยฐานข้อมูลตรง

| | จำนวน |
|---|---:|
| endpoint ใหม่ที่ต้องมี | **~20** (ตามข้อ 6) |
| ไฟล์ SPA ที่ต้องแก้ให้เลิกเรียก Supabase ตรง | **15 ไฟล์** |
| policy ที่ต้องแปลงเป็นเงื่อนไขในโค้ด | **24 บนตาราง + 8 บน storage** |

นี่คือเหตุผลที่ข้อ 3 เสนอให้ทำเป็น **สองเฟส** ไม่ใช่ทีเดียว

---

## 1. Current auth flow — ตรวจจากโค้ดจริง

### 1.1 ชุด A — FastAPI (`backend/`) · auth ของเราเอง

**ไม่เกี่ยวกับ Supabase เลย**

| | จากไฟล์ |
|---|---|
| ออก token | `core/security.py::create_access_token` — JWT **HS256** ลงนามด้วย `settings.jwt_secret` |
| claims | `sub` (user id) · `type: "access"` · `iat` · `exp` — **ไม่มี role ใน token** |
| อายุ | access **30 นาที** · refresh **14 วัน** (`core/config.py:28-29`) |
| ตรวจ token | `api/deps.py::get_current_user` → `decode_token` → ตรวจ `type == "access"` |
| **role มาจากไหน** | **อ่าน DB ทุกคำขอ** — `db.get(User, sub)` แล้วดู `user.is_admin` · `user.is_active` |
| ระดับสิทธิ์ | **2 ระดับ** — `is_admin` boolean เท่านั้น ไม่มี editor |
| gate ที่มีอยู่ | `require_admin` (`deps.py:50`) ใช้กับ `crawl_review` router ทั้ง router |
| รหัสผ่าน | bcrypt cost 12 + SHA-256 prehash (`security.py::_prehash`) |

**ข้อดีที่ควรรักษาไว้**: role ไม่ได้ฝังใน token แต่อ่านจาก DB ทุกครั้ง
→ ถอนสิทธิ์มีผลทันที ไม่ต้องรอ token หมดอายุ · เป็นรากฐานที่ดีสำหรับเพิ่ม role ใหม่

### 1.2 ชุด B — `webapi:3001` · Supabase JWT (ของจริงที่ต้องรักษา)

`webapi/server.mjs` เป็น **ตัวครอบบาง ๆ** ที่แปลง Node request → `Request` มาตรฐาน
แล้วเรียก handler 5 ตัว ซึ่ง **ไฟล์จริงอยู่ในรีโปหน้าเว็บ** (`webapi/Dockerfile:18  COPY api ./api`)
ในรีโปนี้มีแค่ `Dockerfile` · `package.json` · `README.md` · `server.mjs`

```
/api/sci-connect-news-detail    -> anon key  ไม่ต้องล็อกอิน
/api/sci-connect-news           -> anon key  ไม่ต้องล็อกอิน
/api/admin/extract-file         -> requireAdminUser
/api/admin/ingest               -> requireAdminUser
/api/admin/sync-sci-news        -> requireAdminUser
```

**`api/_lib/adminAuth.js::requireAdminUser` — นี่คือรูปแบบที่ต้องรักษา**

```js
const ADMIN_ROLES = ['admin', 'editor'];

const token = (request.headers.get('authorization')||'').replace(/^Bearer\s+/i,'');
if (!token) return 401;

const supabase = createClient(url, anonKey, {
  global: { headers: { Authorization: `Bearer ${token}` } },   // ← scope ด้วย token ผู้เรียก
});

const { data:{user}, error } = await supabase.auth.getUser(token);   // ← ถาม Supabase
if (error || !user) return 401;

const { data: profile } = await supabase.from('user_profiles')
  .select('role, status').eq('user_id', user.id).single();

if (!ADMIN_ROLES.includes(profile?.role) || profile?.status !== 'approved') return 403;
```

สี่อย่างที่แบบนี้ทำได้และต้องไม่หายไป

1. **ตรวจ token กับ Supabase เอง** (`auth.getUser`) ไม่ใช่ถอด JWT ในเครื่อง →
   token ที่ถูกเพิกถอนใช้ไม่ได้ทันที
2. **`role IN ('admin','editor')`**
3. **`status = 'approved'`** — เข้มกว่า RLS ส่วนใหญ่ มี policy เดียวในฐานที่ตรวจ `status`
   (`Approved admins can update any profile`) ชั้น API เพิ่มด่านนี้ให้ทุก endpoint
4. **client ถูก scope ด้วย token ผู้เรียก** → RLS บังคับซ้ำด้วยตัวตนจริง เป็น defence in depth

### 1.3 ชุด C — SPA · ตรวจสิทธิ์ฝั่งเบราว์เซอร์

`src/hooks/useAdminAuth.js` ทำเหมือน `requireAdminUser` คือ `auth.getUser()` แล้วอ่าน
`user_profiles.role/status` · มี `canAccessAdminArea(role, status)` และ `requireAdmin`
สำหรับหน้าที่ต้องเป็น admin เท่านั้น · มี `onAuthStateChange` ล้างแคชเมื่อ `SIGNED_OUT`

**เป็นการตรวจเพื่อ UX ไม่ใช่การบังคับ** — ด่านจริงคือ RLS ใต้ PostgREST
(ซึ่งทีมเขียนไว้ตรงแล้ว คอมเมนต์ในไฟล์ยอมรับเองว่าเป็นการตรวจซ้ำระดับหน้า)

### 1.4 ⚠ กับดักชื่อซ้ำ — `public.user_profiles` สองตารางที่ไม่ใช่ตารางเดียวกัน

| | Supabase `public.user_profiles` | **ของเรา** `public.user_profiles` |
|---|---|---|
| หน้าที่ | **สิทธิ์** | **ความชอบของนักเรียน** |
| คอลัมน์ | `user_id` · `role` · `status` · `full_name` · `email` | `user_id` · `education_level` · `field_of_study` · `current_role` · `career_goal` · `skills` · `interests` · `language_preference` · `metadata` |
| แถว | 3 | — |

**ชื่อเดียวกัน ความหมายไม่เกี่ยวกันเลย** ห้ามเขียน migration หรือ query ที่สมมติว่า
สองตารางนี้คืออันเดียวกัน · คอลัมน์ `current_role` ของเราคือ *"ตำแหน่งงานปัจจุบันของนักเรียน"*
ไม่ใช่ role เชิงสิทธิ์

### 1.5 ข้อจำกัดเชิงโครงสร้าง — ทำไมใช้ RLS ซ้ำที่ปลายทางไม่ได้ง่าย ๆ

```
DATABASE_URL: postgresql+psycopg://advisor_api:***@postgres:5432/course_advisor
                                   ^^^^^^^^^^^  (docker-compose.prod.yml:63)
ตรวจบน production:  advisor_api  login=true  super=false
                    advisor_ingest login=true super=false
```

`backend/app/db/session.py` สร้าง engine **ตัวเดียว** จาก `DATABASE_URL` เดียว →
ทุกคำขอของทุกผู้ใช้ใช้ connection pool ของ role `advisor_api` ร่วมกัน

Supabase ทำ RLS ได้เพราะ PostgREST ตั้ง `request.jwt.claims` ต่อ transaction
ให้ `auth.uid()` อ่านได้ · ถ้าจะทำแบบเดียวกันที่ปลายทางต้องเรียก
`set_config('request.jwt.claims', ..., true)` ทุก transaction แล้วเขียน policy ใหม่ทั้งชุด
ซึ่งเป็นงานใหญ่และเพิ่มจุดพลาด (ลืม `set_config` ครั้งเดียว = policy ผ่านหมดหรือปฏิเสธหมด)

**005 เลือกทาง GRANT ต่อ role ของบริการ ซึ่งถูกต้องกับสถาปัตยกรรมนี้**
และหมายความว่า **การตรวจสิทธิ์ระดับผู้ใช้ต้องอยู่ในโค้ด API**

---

## 2. Supabase RLS behavior ที่ต้องรักษา

จาก Live Verification ข้อ 6 — RLS เปิดครบ 7 ตาราง · ไม่มีตารางใดตั้ง FORCE ROW SECURITY ·
**24 policy บนตาราง + 8 บน `storage.objects`** · ทุกตัว `PERMISSIVE` ผูกกับ role `{public}`
แยกสิทธิ์ด้วยเงื่อนไขใน `USING`/`WITH CHECK` ทั้งหมด

แม่แบบเดียวทั้งระบบ

```sql
EXISTS (SELECT 1 FROM user_profiles
        WHERE user_id = auth.uid() AND role IN ('admin','editor'))   -- insert / update
EXISTS (... AND role = 'admin')                                      -- delete
```

### 2.1 ตารางเทียบพฤติกรรมที่สั่งให้รักษา

| ที่สั่งให้รักษา | ของจริงจาก Live Verification | ตรงกันไหม |
|---|---|---|
| `courses` public read | `SELECT USING (true)` | ✓ |
| `external_news` public read | `SELECT USING (true)` | ✓ |
| `news` public อ่านได้เฉพาะ `status='published'` | `SELECT USING (status = 'published')` + policy แยกให้ admin/editor เห็นทั้งหมด (**5 policy**) | ✓ |
| `knowledge_articles` public ห้ามอ่าน ต้อง admin/editor | `SELECT` ต้อง `role IN (admin,editor)` | ✓ |
| การเขียนรักษาสิทธิ์ admin/editor | `INSERT`/`UPDATE` = admin+editor · `DELETE` = **admin เท่านั้น** | ✓ |

### 2.2 ตารางเต็ม 24 policy ที่ต้องแปลง

| ตาราง | SELECT | INSERT | UPDATE | DELETE |
|---|---|---|---|---|
| `courses` | ทุกคน | admin+editor | admin+editor | **admin** |
| `external_news` | ทุกคน | admin+editor | admin+editor | **admin** |
| `ai_settings` | ทุกคน | — | **admin** | — |
| `rag_documents` | ทุกคน | `ALL` policy: admin+editor | ↑ | ↑ |
| `news` | **`status='published'`** + admin/editor เห็นหมด | admin+editor | admin+editor | **admin** |
| `knowledge_articles` | **admin+editor** | admin+editor | admin+editor | **admin** |
| `user_profiles` | ทุกคน ⚠ | — | ตัวเอง (`auth.uid() = user_id`) · **admin ที่ `status='approved'`** แก้ของคนอื่นได้ | — |

### 2.3 Storage 8 policy

| bucket | public | SELECT | INSERT / UPDATE / DELETE |
|---|---|---|---|
| `course-assets` | **true** | ทุกคน | admin+editor |
| `knowledge-files` | false | **admin+editor** | admin+editor |

ไม่มี policy บน `storage.buckets` → สร้าง/ลบ bucket ได้เฉพาะ service role

### 2.4 สามจุดที่ต้องระวังเป็นพิเศษ

**ก. `news.status` ไม่ใช่ธงแสดงผล มันคือขอบเขตความปลอดภัย**

RLS ใช้ `USING (status = 'published')` ตรง ๆ → วันนี้ **ฐานข้อมูลเป็นคนกรอง**
ถ้าย้ายแล้วลืมกรองที่ API ข่าวที่ยังไม่เผยแพร่จะหลุดออกสาธารณะ
นี่คือการ**เปลี่ยนที่ตั้งของขอบเขตความปลอดภัย** ไม่ใช่การย้ายโค้ด

**ข. `knowledge_articles` วันนี้คนทั่วไปอ่านไม่ได้เลย**

005 ให้ `advisor_api` `SELECT` ได้ทั้งตาราง → ถ้าเขียน endpoint อ่านโดยไม่ใส่ด่าน
เนื้อหาคลังความรู้ทั้งหมดจะเปิดสาธารณะทันที **นี่คือข้อที่รายงานรอบก่อนเขียนผิด**
(เคยเขียนว่าอ่านได้สาธารณะ) และเป็นข้อที่ผิดแล้วกลายเป็นข้อมูลรั่ว

**ค. `user_profiles` ของ Supabase อ่านได้โดยทุกคนขณะที่เก็บ `email` + `full_name`**

`qual = true` — ใครมี anon key ก็อ่านอีเมลผู้ดูแลทั้ง 3 คนได้วันนี้
**ไม่ใช่สิ่งที่ควร "รักษา"** ถือเป็นข้อบกพร่องที่มีอยู่ ไม่ใช่ข้อกำหนด
→ ดูความเสี่ยง R1 ในข้อ 7

---

## 3. Proposed API authorization architecture

### 3.1 หลักที่ใช้ตัดสิน

```
1. เปลี่ยนให้น้อยที่สุด       ยังไม่ตัด Supabase Auth ในเฟสนี้
2. ไม่มีช่วงที่ไม่มีด่าน       ทุกช่วงของการย้ายต้องมีด่านอย่างน้อยหนึ่งชั้นตลอดเวลา
3. ปฏิเสธเป็นค่าตั้งต้น        endpoint ใหม่ต้องถูกคลุมโดย default ไม่ใช่ต้องจำใส่
4. ด่านเดียวต่อหนึ่งความจริง   role อ่านจากที่เดียว ไม่ทำสำเนา
```

### 3.2 ทางเลือกที่พิจารณา

| | วิธี | ประเมิน |
|---|---|---|
| **A** | ขยาย `webapi:3001` ให้คุย PostgreSQL ปลายทางแทน Supabase | **เลือกสำหรับเฟส 1** — ตรวจสิทธิ์เดิมอยู่ที่นี่แล้วครบ · SPA แก้น้อยสุด · ไม่ต้องยกชั้น auth ไป FastAPI |
| B | ย้ายทุกอย่างไป FastAPI พร้อมรับ Supabase JWT | งานใหญ่กว่า · ต้องเพิ่ม role editor ใน FastAPI และรับ token สองชนิดพร้อมกัน → ซับซ้อนตอนย้าย |
| C | ทำ RLS ที่ปลายทางด้วย `set_config('request.jwt.claims')` | ปฏิเสธ — ต้องเขียน policy ใหม่ทั้ง 32 ตัว · ลืม `set_config` ครั้งเดียวคือพลาดทั้งระบบ · ขัดกับ GRANT ที่ 005 เลือกไว้ |
| D | ให้ SPA คุย PostgreSQL ตรงเหมือนที่คุย Supabase | **ปฏิเสธเด็ดขาด** — ไม่มี RLS ที่ปลายทาง = เปิดฐานข้อมูลให้เบราว์เซอร์ |

### 3.3 เฟส 1 — ขยาย `webapi` เป็นชั้นบังคับสิทธิ์ (เลือกทางนี้)

```
SPA (เบราว์เซอร์)
  |  ล็อกอิน / ต่ออายุ token
  └──────────────────────────────► Supabase Auth      ← ยังไม่ตัด ตามที่สั่ง
  |
  |  Authorization: Bearer <supabase access token>
  └──► Caddy /api/* ──► webapi:3001
                          |
                          ├── ตรวจ token กับ Supabase  (auth.getUser — เหมือนเดิม)
                          ├── อ่าน role/status จาก Supabase user_profiles  (เหมือนเดิม)
                          └── อ่าน/เขียนข้อมูล ──► PostgreSQL  schema web
                                                    (role advisor_api ตาม GRANT ของ 005)
```

**เปลี่ยนอะไรน้อยที่สุด**

| | |
|---|---|
| ตรรกะตรวจสิทธิ์ | **ไม่เปลี่ยน** — `requireAdminUser` ใช้ต่อได้ทั้งก้อน |
| ที่ล็อกอิน | **ไม่เปลี่ยน** — Supabase Auth |
| `user_profiles` ที่เก็บ role | **ไม่เปลี่ยน** — ยังอยู่ที่ Supabase (คือเหตุผลที่ยังไม่ตัด Auth ได้) |
| ที่เก็บข้อมูลเนื้อหา | **เปลี่ยน** — `supabase.from(x)` → query `web.x` |
| SPA | **เปลี่ยน** — 15 ไฟล์ที่เรียก Supabase ตรง เปลี่ยนเป็น `fetch('/api/...')` |

### 3.4 สิ่งที่ต้องเพิ่มใน `requireAdminUser` — แยกสองระดับ

วันนี้ `requireAdminUser` คืน ok/403 แบบเดียว แต่ RLS แยก **DELETE = admin เท่านั้น**
ออกจาก **INSERT/UPDATE = admin+editor** ถ้าใช้ตัวเดิมทั้งหมด **editor จะลบข้อมูลได้
ซึ่งวันนี้ลบไม่ได้** → เป็นการยกระดับสิทธิ์โดยไม่ตั้งใจ

เสนอให้แยกเป็นสองฟังก์ชันที่ใช้ตัวเดิมเป็นแกน

```js
requireEditor(request)   // role IN ('admin','editor') AND status='approved'   -> insert/update
requireAdmin(request)    // role = 'admin'            AND status='approved'   -> delete + ai_settings
requireAnyone(request)   // ไม่ต้องมี token แต่ต้องรู้ว่า "ไม่มีตัวตน" เพื่อกรอง news.status
```

ข้อสาม สำคัญกับ `news`: endpoint อ่านข่าวต้อง **รู้ว่าผู้เรียกเป็นใครถ้ามี token**
เพื่อตัดสินว่าจะคืนเฉพาะ `published` หรือทั้งหมด — แปลว่าต้อง *ลอง* ตรวจ token
แต่ไม่ปฏิเสธถ้าไม่มี

### 3.5 กฎ "ปฏิเสธเป็นค่าตั้งต้น"

`webapi/server.mjs` ลงทะเบียน route จากตาราง `ROUTES` ตรง ๆ ไม่มีด่านกลาง
ถ้าเพิ่ม route ใหม่แล้วลืมเรียก `requireAdminUser` ใน handler นั้น → **เปิดโล่งเงียบ ๆ**

เสนอให้ `ROUTES` ประกาศระดับสิทธิ์ไปด้วย และ `server.mjs` เป็นคนบังคับ
ก่อนจะเรียก handler

```js
const ROUTES = [
  ["/api/sci-connect-news",        "./api/sci-connect-news.js",        PUBLIC],
  ["/api/news",                    "./api/news.js",                    PUBLIC_FILTERED],
  ["/api/knowledge",               "./api/knowledge.js",               EDITOR],
  ["/api/admin/ai-settings",       "./api/admin/ai-settings.js",        ADMIN],
  // route ที่ไม่ประกาศระดับ -> server ปฏิเสธตอน start ไม่ใช่ตอนมีคนเรียก
];
```

เป็นรูปแบบเดียวกับที่ `crawl_review.py` ทำไว้แล้วใน FastAPI และเขียนเหตุผลกำกับไว้ว่า

> *"require_admin คลุมทั้ง router ไม่ใช่ทีละเส้นทาง — เส้นทางที่เพิ่มในอนาคตจะถูกคลุมด้วย
> โดยไม่ต้องจำ ถ้าใส่ทีละเส้นทางแล้วลืมหนึ่งที่ คิวงานภายในจะหลุดออกไปให้ใครก็อ่านได้"*

**ใช้บทเรียนเดิมที่ทีมเขียนไว้แล้ว ไม่ต้องเรียนซ้ำ**

### 3.6 เฟส 2 — เมื่อตัดสินใจตัด Supabase Auth (ยังไม่ทำ)

```
เพิ่ม role ใน FastAPI       users.is_admin (boolean) -> users.role (admin|editor|user) + status
ย้าย identity              Supabase Auth -> FastAPI auth ที่มีอยู่
รวม webapi เข้า FastAPI     หรือคงไว้แต่ให้ตรวจ JWT ของเรา
```

**ห้ามทำพร้อมเฟส 1** — ถ้าย้ายทั้งที่เก็บข้อมูลและที่เก็บตัวตนในคราวเดียว
เวลาเกิดปัญหาจะแยกไม่ออกว่ามาจากฝั่งไหน และการถอนกลับต้องถอนสองอย่างพร้อมกัน

---

## 4. Role mapping

### 4.1 สามระบบ role ที่มีอยู่จริง

| ระบบ | ที่เก็บ | ค่าที่เป็นไปได้ | ค่าที่มีอยู่จริง |
|---|---|---|---|
| Supabase | `public.user_profiles.role` + `.status` | `admin` · `editor` · `user` (DEFAULT `'user'`) × `status` (DEFAULT `'approved'`) | **admin/approved 2 · user/approved 1** · **ไม่พบ editor เลย** |
| FastAPI | `public.users.is_admin` | boolean | **is_admin=true 1 คน** จาก 198 |
| DB role | `pg_roles` | `advisor_api` · `advisor_ingest` | ทั้งคู่ `login=true super=false` |

### 4.2 เฟส 1 — ไม่ต้อง map role

เพราะ role ยังอ่านจาก Supabase `user_profiles` ที่เดิม **ไม่มีการทำสำเนา ไม่มีการแปลง**
→ ไม่มีความเสี่ยง "ที่บอกสิทธิ์สองแห่งไม่ตรงกัน"

### 4.3 เฟส 2 — ตารางแปลงที่เสนอ (ยังไม่ทำ)

| Supabase `role` / `status` | FastAPI ที่เสนอ | หมายเหตุ |
|---|---|---|
| `admin` / `approved` | `role='admin'` · `status='approved'` | |
| `editor` / `approved` | `role='editor'` | **ยังไม่มีใครถือ** — ดูข้อ 4.4 |
| `user` / `approved` | `role='user'` | ผู้ใช้ทั่วไป |
| อะไรก็ตาม / ไม่ใช่ `approved` | ปฏิเสธการเขียนทั้งหมด | |

**ห้ามแปลง `is_admin` boolean ไปเป็น role ตรง ๆ** — `is_admin=false` ไม่ได้บอกว่าเป็น
`user` หรือ `editor` ข้อมูลระดับกลางไม่มีอยู่ในของเรา การแปลงจึงมีทิศทางเดียว
(Supabase → ของเรา) ไม่ใช่สองทาง

### 4.4 คำถามที่ต้องให้เจ้าของตัดสิน

> **จะรักษาการแยก `admin` กับ `editor` ไหม ทั้งที่ของจริงยังไม่มีใครถือ `editor`?**

| ทางเลือก | ผล |
|---|---|
| **รักษาไว้** | ต้องมี `requireEditor` + `requireAdmin` แยกกัน · 12 policy ที่ต่างกันระหว่างสองระดับยังคงความหมาย · งานเพิ่มเล็ก (ฟังก์ชันเดียว) |
| ยุบเป็นระดับเดียว | โค้ดง่ายกว่า **แต่ editor จะลบข้อมูลได้ซึ่งวันนี้ลบไม่ได้** = ยกระดับสิทธิ์ · และถ้าภายหลังอยากแยกกลับ ต้องรู้ว่าใครควรเป็นอะไรซึ่งข้อมูลจะหายไปแล้ว |

**ข้อเสนอ: รักษาไว้** งานเพิ่มคือฟังก์ชันเดียว แต่การยุบแล้วแยกกลับทำไม่ได้
และ policy 12 ตัวที่แยก DELETE ออกมาเป็นเจตนาที่ชัดเจนของคนออกแบบเดิม

---

## 5. User mapping strategy — **BLOCKED**

### 5.1 ของจริงสองฝั่ง

**ฝั่ง Supabase** (Live Verification ข้อ 9 · M10)

```
auth.users              3 คน · ยืนยันอีเมลครบ 3 · เคยเข้าสู่ระบบครบ 3 · ไม่มี SSO · ไม่มี anonymous
user_profiles           3 แถว · จับคู่ auth.users ได้ 3/3 · กำพร้า 0
ผู้เขียนเนื้อหา           distinct(created_by) = 1 · distinct(updated_by) = 1  ทั้ง courses และ news
                        ไม่ NULL ทุกแถว (courses 12/12 · news 3/3) · ไม่มี FK กำพร้า
courses.created_by      DEFAULT auth.uid()  ->  auth.users(id)
courses.updated_by      ->  user_profiles(user_id)
```

→ **เนื้อหาทั้งฐานเขียนโดยบัญชีเดียว** ต้อง map แค่ **1 ราย** ไม่ใช่ 3

**ฝั่งเรา** — `SELECT` อย่างเดียวบน production วันนี้ ไม่ได้ดึงอีเมลออกมา

```
users_total                198
is_admin = true              1      (โดเมน gmail.com · มี full_name)
is_active = true           198
distinct email             198      email CITEXT NOT NULL UNIQUE  -> เทียบไม่สนตัวพิมพ์อยู่แล้ว
email ว่าง/NULL              0
full_name IS NULL          177
โดเมน                      example.com 188 · gmail.com 7 · awdaw.com 1 · stpnru.local 1 · gggg.com 1
created_at                 2026-08-14 .. 2026-09-29
web schema                 ไม่มี          <- ยืนยันซ้ำว่า 005 ยังไม่ apply
```

**บัญชีที่น่าจะเป็นคนจริง = 9** (ไม่นับ 188 `example.com` ที่เป็นข้อมูลทดสอบ
และ 1 `stpnru.local` ซึ่งคือบัญชีกลางของหน้าเว็บ `public-web@stpnru.local`
สร้างอัตโนมัติโดย `services/web_compat.py::shared_user`)

### 5.2 ทำไม BLOCKED — ขาดหลักฐานชิ้นเดียว

ที่จับคู่ได้ต้องเป็นค่าที่ **unique ทั้งสองฝั่ง** ซึ่งมีอยู่อย่างเดียวคือ **อีเมล**

| ตัวเลือกกุญแจ | ใช้ได้ไหม |
|---|---|
| **UUID** | **ไม่ได้** — `auth.users.id` กับ `public.users.id` ถูก generate แยกกันคนละฐาน ไม่มีความสัมพันธ์ · **ห้ามเดา UUID ตามที่สั่ง** |
| **ชื่อ (`full_name`)** | **ไม่ได้** — ไม่ unique · และ 177/198 เป็น NULL · **ห้าม map จากชื่อตามที่สั่ง** |
| `created_at` | **ไม่ได้** — ไม่ unique และคนละฐานคนละเวลา |
| `is_admin` ↔ `role='admin'` | **ไม่ได้** — ฝั่งเรา admin 1 คน ฝั่งนั้น admin 2 คน จำนวนไม่เท่า และไม่ใช่กุญแจ |
| **อีเมล** | **ได้** — unique ทั้งสองฝั่ง · ฝั่งเราเป็น `CITEXT` จึงเทียบแบบไม่สนตัวพิมพ์ให้เอง |

**แต่ไม่มีอีเมลของบัญชีผู้เขียนฝั่ง Supabase อยู่ในหลักฐานใดเลย**

`SUPABASE_LIVE_VERIFICATION.md` ระบุไว้ชัดในหัวข้อท้ายเอกสารว่า
*"ไม่มีรายการอีเมล … ไม่มีเนื้อหา `user_profiles.email` และ `full_name`
สิ่งที่รายงานคือ **จำนวน** และ **โครงสร้าง** เท่านั้น"* ซึ่งเป็นไปตามที่สั่งไว้ตอนนั้น

→ **B2 = BLOCKED** ขาดค่าเดียว: อีเมลของบัญชีที่เป็น `created_by`/`updated_by` ของเนื้อหา

### 5.3 วิธี manual mapping ที่ปลอดภัย — เสนอ 2 ทาง

#### ทาง A (แนะนำ) — เทียบด้วย hash ไม่ต้องขนอีเมลข้ามระบบ

ไม่ต้องให้ใครคัดลอกอีเมลไปวางที่ไหน และไม่ต้องมีอีเมลโผล่ในรายงานหรือใน log

**ขั้นที่ 1** — เจ้าของรันบน Supabase (อ่านอย่างเดียว) คืนค่าเป็น hash ไม่ใช่อีเมล

```sql
SELECT encode(digest(lower(btrim(u.email)), 'sha256'), 'hex') AS email_sha256
FROM auth.users u
WHERE u.id = (SELECT created_by FROM public.courses LIMIT 1);
```

**ขั้นที่ 2** — เทียบกับฝั่งเราด้วย hash เดียวกัน (`pgcrypto` ยืนยันแล้วว่ามีอยู่)

```sql
SELECT id, is_admin, (full_name IS NOT NULL) AS has_name
FROM public.users
WHERE encode(digest(lower(btrim(email::text)), 'sha256'), 'hex') = '<hash จากขั้นที่ 1>';
```

| ผลที่ได้ | แปลว่า |
|---|---|
| **1 แถว** | **mapping เป็น deterministic** → ใช้ `id` นั้นเป็น `created_by`/`updated_by` ได้ · B2 ปลดล็อก |
| **0 แถว** | บัญชีผู้เขียนฝั่ง Supabase **ไม่มีคู่ในฝั่งเรา** → ตัดสินตามข้อ 5.4 · **ห้ามสร้าง user ใหม่ตามที่สั่ง** |
| >1 แถว | เป็นไปไม่ได้ — `email` เป็น UNIQUE (ถ้าเกิดขึ้นคือฐานข้อมูลผิดปกติ ต้องหยุดตรวจก่อน) |

**ทำไมดีกว่าการส่งอีเมลมาตรง ๆ**: ค่าที่ขนข้ามระบบเป็น digest ทางเดียว ไม่ปรากฏใน
รายงานที่ commit ลงรีโป public และไม่อยู่ใน shell history ที่อ่านย้อนได้
(ยังเดาถอยหลังได้ถ้ารู้อีเมลอยู่แล้ว แต่ไม่ได้เปิดเผยอะไรใหม่)

#### ทาง B — เจ้าของชี้แถวเองโดยไม่ต้องบอกอีเมลใคร

เจ้าของรันบน production ฝั่งเรา ดูรายการ 9 บัญชีที่น่าจะเป็นคนจริงด้วยตาตัวเอง
แล้วบอกกลับมาเป็น **`id` (UUID) ของแถวที่เลือก** — ไม่ต้องบอกอีเมล

```sql
SELECT id, is_admin, created_at::date
FROM public.users
WHERE split_part(email::text,'@',2) NOT IN ('example.com','stpnru.local')
ORDER BY created_at;
```

ใช้เมื่อทาง A คืน 0 แถวแต่เจ้าของยืนยันว่ารู้ว่าเป็นบัญชีไหน
(เช่น ใช้อีเมลคนละตัวในสองระบบ ซึ่ง hash จับไม่ได้)

### 5.4 ถ้าหาคู่ไม่ได้ — ทางที่เหลือ

| ทาง | ผล | ประเมิน |
|---|---|---|
| **1. ให้ `created_by`/`updated_by` เป็น NULL ทั้ง 15 แถว** | เสียข้อมูลผู้เขียน · **ไม่ขัด 005** ซึ่งตั้งทั้งคู่เป็น nullable `ON DELETE SET NULL` อยู่แล้ว · นำเข้าได้ทันที | **ยอมรับได้** ถ้าเจ้าของรับว่าไม่ต้องรู้ผู้เขียนของ 15 แถวนี้ · ข้อมูลเดิมยังอยู่ใน Supabase ไม่ได้ถูกลบ |
| 2. สร้าง user ใหม่ให้ตรงกับบัญชีฝั่ง Supabase | **ห้ามตามที่สั่ง** — และจะได้บัญชีที่ไม่มีใครใช้เข้าระบบได้ | ปฏิเสธ |
| 3. เก็บ UUID เดิมของ Supabase ไว้ในคอลัมน์ใหม่ | เก็บความจริงไว้ครบโดยไม่ต้อง map · **แต่ 005 ไม่มีคอลัมน์นี้** ต้องมี migration 006 และต้องขออนุมัติแยก | **ควรพิจารณา** ถ้าเจ้าของอยากรักษาข้อมูลผู้เขียนไว้แต่ map ไม่ได้ |

**ข้อเสนอ**: ทำทาง A ก่อน ได้ 1 แถวก็จบ · ถ้าได้ 0 แถวให้เลือกระหว่างทาง 1 (ง่ายสุด)
กับทาง 3 (รักษาข้อมูล) — **รอบนี้ไม่ตัดสินให้ เพราะเป็นการแลกข้อมูลกับความซับซ้อน
ซึ่งเป็นการตัดสินใจของเจ้าของ**

---

## 6. Endpoint-by-endpoint authorization matrix

`PUBLIC` = ไม่ต้องมี token · `PUBLIC_FILTERED` = ไม่ต้องมี token แต่ถ้ามีจะเห็นมากขึ้น ·
`EDITOR` = `role IN (admin,editor)` + `status='approved'` · `ADMIN` = `role='admin'` + `status='approved'`

### 6.1 เส้นทางที่มีอยู่แล้ว — ไม่เปลี่ยน

| เส้นทาง | บริการ | วันนี้ | หลังย้าย |
|---|---|---|---|
| `POST /api/chat` → `/chat-web` | FastAPI | PUBLIC + `web_rate_limiter` (IP) | **เหมือนเดิม** |
| `POST /compare-courses` | FastAPI | PUBLIC + `web_rate_limiter` | **เหมือนเดิม** |
| `POST /recommend-major` | FastAPI | PUBLIC + `web_rate_limiter` | **เหมือนเดิม** |
| `GET /course-facts` | FastAPI | PUBLIC | **เหมือนเดิม** |
| `/api/crawl-review/*` | FastAPI | `require_admin` (JWT ของเรา) ทั้ง router | **เหมือนเดิม** — เป็นงานภายในไม่เกี่ยวหน้าเว็บ |
| `POST /api/admin/extract-file` | webapi | EDITOR | **เหมือนเดิม** |
| `POST /api/admin/ingest` | webapi | EDITOR | **เหมือนเดิม** |
| `POST /api/admin/sync-sci-news` | webapi | EDITOR | **เหมือนเดิม** |

### 6.2 เส้นทางที่ต้องสร้างใหม่ — แทนการที่ SPA คุย Supabase ตรง

| เส้นทางที่เสนอ | ระดับ | แทนอะไรใน SPA | ด่านที่ต้องมี |
|---|---|---|---|
| `GET /api/courses` | PUBLIC | `from('courses').select()` ×6 | — |
| `GET /api/courses/:id` | PUBLIC | `CourseDetail.jsx` | — |
| `POST /api/courses` | **EDITOR** | `CourseForm.jsx` insert | ตั้ง `created_by` จาก token ห้ามรับจาก body |
| `PATCH /api/courses/:id` | **EDITOR** | `CourseForm.jsx` update | ตั้ง `updated_by` จาก token |
| `DELETE /api/courses/:id` | **ADMIN** | `AllCourses.jsx` delete | ⚠ **admin เท่านั้น** 005 ไม่ให้ DELETE แก่ใคร → ดู R4 |
| `GET /api/news` | **PUBLIC_FILTERED** | `from('news').select()` ×3 | ⚠ **ไม่มี token → `WHERE status='published'` บังคับ** |
| `GET /api/news/:id` | **PUBLIC_FILTERED** | `NewsForm.jsx` | ⚠ เงื่อนไขเดียวกัน ไม่ใช่แค่ที่ list |
| `POST /api/news` | **EDITOR** | `NewsForm.jsx` insert | ตรวจ `status` อยู่ในค่าที่ CHECK ยอม |
| `PATCH /api/news/:id` | **EDITOR** | `NewsForm.jsx` update | |
| `DELETE /api/news/:id` | **ADMIN** | — | |
| `GET /api/knowledge` | **EDITOR** | `KnowledgeBase.jsx` · `AdminLayout.jsx` · `Dashboard.jsx` | ⚠ **ห้าม PUBLIC** วันนี้คนทั่วไปอ่านไม่ได้เลย |
| `GET /api/knowledge/:id` | **EDITOR** | `KnowledgeForm.jsx` | ⚠ เงื่อนไขเดียวกัน |
| `POST /api/knowledge` | **EDITOR** | `KnowledgeForm.jsx` insert | |
| `PATCH /api/knowledge/:id` | **EDITOR** | `KnowledgeForm.jsx` update | |
| `DELETE /api/knowledge/:id` | **ADMIN** | `KnowledgeBase.jsx` delete | |
| `GET /api/ai-settings` | PUBLIC | `AiSettings.jsx` · `Dashboard.jsx` select ×2 | RLS ต้นทางเปิดสาธารณะ — **แต่ดู R2** |
| `PATCH /api/ai-settings` | **ADMIN** | `AiSettings.jsx` update | ⚠ **admin เท่านั้น ไม่ใช่ editor** |
| `GET /api/sci-connect-news` | PUBLIC | มีอยู่แล้ว | เปลี่ยนที่อ่านเป็น `web.external_news` |
| `GET /api/sci-connect-news-detail` | PUBLIC | มีอยู่แล้ว | เปลี่ยนที่อ่าน |
| `GET /api/me` | ต้องมี token | `useAdminAuth` อ่าน `user_profiles` | คืนเฉพาะ role/status ของผู้เรียกเอง |

### 6.3 ที่ยังไม่ย้ายในเฟสนี้

| | เหตุผล |
|---|---|
| `user_profiles` (3 แถว) · `auth.users` | **ยังไม่ตัด Supabase Auth** ตามที่สั่ง · role ยังอ่านจากที่เดิม |
| `rag_documents` (12 แถว · 768 มิติ) | ต้อง re-embed ด้วย `bge-m3` ก่อน ยังไม่อนุญาต |
| `storage` 2 bucket · 8 policy | **ยังไม่ตัด Supabase Storage** ตามที่สั่ง |
| `storage.objects` ผ่าน `courseStorage.js` / `knowledgeStorage.js` | ⚠ **ยังคุย Supabase ตรงต่อไป** — `knowledgeStorage.js` ใช้ `createSignedUrl(path, 3600)` ซึ่งเป็นด่านที่ต้องรักษา |

### 6.4 กฎที่ใช้กับทุก endpoint ที่เขียนข้อมูล

```
1. created_by / updated_by มาจาก token ของผู้เรียกเท่านั้น  ห้ามรับจาก request body
   (วันนี้ SPA ส่ง updated_by: user?.id มาเอง — ย้ายแล้วต้องไม่เชื่อค่านั้น)
1a. CREATE  ตั้งทั้ง created_by และ updated_by = id ของผู้เรียกที่ยืนยันตัวตนแล้ว
1b. UPDATE  ตั้ง updated_by เท่านั้น  ห้ามแตะ created_by เลยแม้แต่จะตั้งจาก token
   (created_by เป็นข้อเท็จจริงที่เกิดครั้งเดียว การเขียนทับตอนแก้ไขจะลบประวัติ
    ผู้สร้างทิ้งทุกครั้งที่มีคนแก้ และถ้า created_by เดิมเป็น NULL เพราะเป็นแถว
    legacy ที่แมปผู้เขียนไม่ได้ การตั้งค่าใหม่จะเปลี่ยนความหมายของ NULL นั้น
    จาก "ยังแมปไม่ได้" ไปเป็น "คนที่เพิ่งมาแก้เป็นคนสร้าง" ซึ่งไม่จริง
    ดู docs/B2_LEGACY_AUTHOR_RESOLUTION.md)
2. id ของแถวที่จะแก้มาจาก path ไม่ใช่ body
3. ไม่คืน error ที่บอกว่าแถวมีอยู่จริงไหม เมื่อผู้เรียกไม่มีสิทธิ์อ่านแถวนั้น
   (404 กับ 403 ต้องเลือกให้สม่ำเสมอ ไม่งั้นกลายเป็นช่องนับจำนวนข้อมูล)
4. endpoint ที่คืนรายการต้องมีเพดานจำนวน ไม่คืนทั้งตาราง
```

---

## 7. Security risks

| # | ความเสี่ยง | ระดับ | เหตุ | ทางลด |
|---|---|---|---|---|
| **R1** | **`user_profiles` ของ Supabase อ่านได้โดยทุกคนวันนี้** ขณะที่เก็บ `email` + `full_name` (`qual = true`) | **สูง** | ใครมี anon key ก็ดึงอีเมลผู้ดูแลทั้ง 3 คนได้ · anon key อยู่ใน bundle ของ SPA ตามธรรมชาติ | **เป็นข้อบกพร่องที่มีอยู่ ไม่ใช่สิ่งที่ต้องรักษา** · เมื่อย้ายแล้ว `/api/me` ต้องคืนเฉพาะของผู้เรียกเอง **ห้ามทำ endpoint ที่คืนรายการผู้ใช้ทั้งหมดแบบสาธารณะ** · แก้ที่ Supabase ตอนนี้ก็ได้แต่ต้องขออนุมัติแยก |
| **R2** | **`ai_settings` อ่านได้สาธารณะ** และเก็บชื่อโมเดล (`gemini-3.1-flash-lite`) | กลาง | เปิดเผยรายละเอียดภายในโดยไม่จำเป็น แม้ไม่ใช่ความลับ | ตอนย้ายเสนอให้เป็น EDITOR ไม่ใช่ PUBLIC · **เป็นการเข้มขึ้นจากเดิม ต้องให้เจ้าของอนุมัติ** เพราะอาจมีหน้าที่ใช้ค่านี้โดยไม่ล็อกอิน |
| **R3** | **ลืมกรอง `news.status` ที่ API** | **สูง** | วันนี้ฐานข้อมูลกรองให้ ย้ายแล้วไม่มีใครกรองถ้าลืม → ข่าวที่ยังไม่เผยแพร่หลุด · ไม่มีอะไรฟ้อง | เขียน endpoint อ่านข่าวให้ **บังคับ `status='published'` เป็นค่าตั้งต้น** แล้วค่อยปลดเมื่อพิสูจน์ได้ว่าผู้เรียกเป็น editor — ไม่ใช่ตรงกันข้าม · **ต้องมี test ที่ยิงโดยไม่มี token แล้วยืนยันว่าไม่เห็น draft** |
| **R4** | **005 ไม่ให้ DELETE แก่ใครเลย แต่ RLS ต้นทางให้ admin ลบได้** | กลาง | SPA มีปุ่มลบ 5 ที่ (`courses` · `knowledge_articles` · `rag_documents` ×3) · ย้ายแล้วปุ่มจะพังเงียบ ๆ ด้วย error ระดับ DB ไม่ใช่ 403 ที่สื่อความหมาย | **เป็นการเปลี่ยนที่ 005 ตั้งใจ** ตามหลัก 002/004 · ต้องตัดสินว่า (ก) ยอมให้ปุ่มลบหายไป หรือ (ข) ให้ `advisor_api` DELETE ได้ใน migration ถัดไป · **ห้ามปล่อยให้พังเงียบ** |
| **R5** | **`webapi` ไม่มีด่านกลาง** ลืมเรียก `requireAdminUser` ใน handler ใหม่ = เปิดโล่ง | **สูง** | `server.mjs` ลงทะเบียน route จากตารางตรง ๆ โดยไม่บังคับอะไร | ข้อ 3.5 — ให้ `ROUTES` ประกาศระดับสิทธิ์ และ **server ปฏิเสธตอน start ถ้า route ไม่ประกาศ** |
| **R6** | **`editor` ได้สิทธิ์ลบโดยไม่ตั้งใจ** ถ้าใช้ `requireAdminUser` ตัวเดียวคลุมทุกอย่าง | กลาง | ตัวที่มีอยู่ยอม `['admin','editor']` แต่ RLS ให้ DELETE เฉพาะ admin | ข้อ 3.4 — แยก `requireEditor` กับ `requireAdmin` |
| **R7** | **เชื่อ `created_by`/`updated_by` จาก request body** | **สูง** | วันนี้ SPA ส่ง `updated_by: user?.id` มาเอง (`KnowledgeForm.jsx:138`) ซึ่งวันนี้ RLS ไม่ได้กัน · ย้ายแล้วถ้า API เชื่อค่านั้น ใครก็อ้างเป็นคนอื่นได้ | ข้อ 6.4 กฎ 1 — **ตั้งจาก token เท่านั้น** |
| **R8** | **ช่วงเปลี่ยนผ่านมีสองที่เก็บข้อมูล** | กลาง | ถ้า SPA บางหน้ายังอ่าน Supabase ขณะที่บางหน้าอ่าน `web` ผู้ใช้จะเห็นข้อมูลไม่ตรงกัน | ย้ายทีละตารางให้จบทั้งอ่านและเขียนพร้อมกัน **ห้ามย้ายครึ่งตาราง** · ตารางที่ง่ายสุดคือ `knowledge_articles` (0 แถว) |
| **R9** | **`auth.getUser()` เรียก Supabase ทุกคำขอ** | ต่ำ | Supabase ล่ม = หน้าผู้ดูแลใช้ไม่ได้แม้ข้อมูลอยู่ที่เราแล้ว | ยอมรับในเฟส 1 (แลกกับการถอนสิทธิ์ที่มีผลทันที) · หายไปเองในเฟส 2 · **ห้ามแก้ด้วยการถอด JWT ในเครื่องแทน** เพราะจะเสียคุณสมบัติข้อ 1 ของ 1.2 |
| **R10** | **`public-web@stpnru.local` เป็นบัญชีที่มีอยู่จริงใน `users`** | ต่ำ | `shared_user()` สร้างให้อัตโนมัติ · รหัสผ่านสุ่มที่ไม่มีใครรู้ (`web_compat.py:53`) | ตรวจแล้วว่ามีอยู่ 1 แถว · **ห้ามใช้บัญชีนี้เป็นคู่ของ mapping ในข้อ 5** เพราะไม่ใช่คน |

---

## 8. Code changes ที่จะต้องทำในรอบถัดไป

**ยังไม่แก้อะไรในรอบนี้** — รายการนี้คือสิ่งที่ขออนุมัติทำต่อ

### 8.1 เรียงตามลำดับที่ปลอดภัย

```
ขั้น 1  โครงสร้างด่าน  (ไม่เปลี่ยนพฤติกรรม)
        webapi/server.mjs          ให้ ROUTES ประกาศระดับสิทธิ์ · ปฏิเสธตอน start ถ้าไม่ประกาศ
        api/_lib/adminAuth.js      แยก requireEditor / requireAdmin / optionalUser
        test                       ยิงทุก route โดยไม่มี token · ด้วย token user · editor · admin

ขั้น 2  ตารางที่ง่ายสุดก่อน — knowledge_articles (0 แถว ไม่มีอะไรจะเสีย)
        api/knowledge.js (ใหม่)    GET/POST/PATCH ระดับ EDITOR · DELETE ระดับ ADMIN
        SPA 4 ไฟล์                 KnowledgeBase · KnowledgeForm · AdminLayout · Dashboard
        test                       ยิงโดยไม่มี token ต้องได้ 401 ไม่ใช่รายการบทความ

ขั้น 3  news (3 แถว · มีกับดัก status)
        api/news.js (ใหม่)         GET บังคับ status='published' เป็นค่าตั้งต้น
        SPA 2 ไฟล์
        test                       ไม่มี token แล้วต้องไม่เห็น draft — ทั้งที่ list และที่ :id

ขั้น 4  courses (12 แถว · มี logo ใน storage)
        api/courses.js (ใหม่)      storage ยังคุย Supabase ตรงต่อไป
        SPA 6 ไฟล์

ขั้น 5  ai_settings (1 แถว) + /api/me
ขั้น 6  external_news — ท้ายสุด เพราะมีผู้เขียนอัตโนมัติ (ดูแผน cutover ใน Final Review 7.2)
```

### 8.2 ไฟล์ที่จะถูกแตะ

| รีโป | ไฟล์ | การแก้ |
|---|---|---|
| นี้ | `webapi/server.mjs` | ด่านกลาง + ตาราง ROUTES มีระดับสิทธิ์ |
| นี้ | `webapi/Dockerfile` | อาจต้องเพิ่ม env ของ PostgreSQL |
| นี้ | `docker-compose.prod.yml` | `webapi` ต้องมี `DATABASE_URL` (role `advisor_api`) |
| นี้ | `Caddyfile` | เพิ่มเส้นทางใหม่ใต้ `webapi` — ⚠ **`/api/*` ตัวสุดท้ายส่งไป FastAPI** ลำดับบล็อกจึงสำคัญ |
| นี้ | `eval/` | ชุดตรวจ authorization ใหม่ |
| **หน้าเว็บ** | `api/_lib/adminAuth.js` · `api/{news,knowledge,courses,ai-settings}.js` | handler ใหม่ |
| **หน้าเว็บ** | `src/` **15 ไฟล์** | เลิกเรียก Supabase ตรง |

> ⚠ **งานครึ่งหนึ่งอยู่ในรีโปหน้าเว็บ** (`FoMake/Univercity`) ซึ่งเป็นรีโปของทีมอื่น
> ต้องตกลงเรื่องสิทธิ์เขียนและลำดับการ deploy ก่อนเริ่มขั้น 2
> **นี่คือข้อจำกัดด้านการเข้าถึง ไม่ใช่ด้านเทคนิค** และเป็นเรื่องเดิมที่เคยระบุไว้ว่า
> เป็นอุปสรรคจริงของการส่งมอบ

### 8.3 ที่ต้องมีก่อนย้ายข้อมูลจริง

```
ชุดตรวจที่ยิงทุก endpoint ใหม่ด้วยตัวตน 4 แบบ  ไม่มี token / user / editor / admin
   และยืนยัน "ผลลัพธ์" ไม่ใช่ "เส้นทาง" — ต้องดูว่าข้อมูลที่คืนมาคืออะไร
   ไม่ใช่แค่ว่าได้ status code เท่าไหร่
ข้อตรวจเฉพาะสำหรับ R3   ไม่มี token แล้วไม่เห็น draft
ข้อตรวจเฉพาะสำหรับ R7   ส่ง created_by ปลอมใน body แล้วต้องไม่มีผล
```

---

## 9. B1 / B2 — READY หรือ BLOCKED

### B1 Authorization — **READY**

| ที่ต้องรู้ | สถานะ |
|---|---|
| FastAPI รับ Supabase JWT อย่างไร | **ตอบแล้ว — ไม่รับเลย** มี auth ของตัวเองแยกสมบูรณ์ (ข้อ 1.1) |
| role มาจากไหน | **ตอบแล้ว** — FastAPI: `users.is_admin` อ่าน DB ทุกคำขอ · webapi/SPA: Supabase `user_profiles.role/status` (ข้อ 1.1–1.3) |
| policy ที่เปิดอยู่จริง | **ครบ 24 + 8** จาก Live Verification (ข้อ 2.2–2.3) |
| ค่า `role`/`status` ที่ใช้จริง | **ครบ** — admin 2 · user 1 · ไม่มี editor · ไม่มี status อื่นนอกจาก `approved` |
| สถาปัตยกรรมที่เสนอ | **ครบ** — เฟส 1 ขยาย `webapi` (ข้อ 3.3) |
| matrix ต่อ endpoint | **ครบ ~20 เส้นทาง** (ข้อ 6) |

**ลงมือได้เมื่อได้รับอนุมัติ** เหลือคำถามให้เจ้าของตัดสิน **1 ข้อที่ไม่บล็อกการเริ่ม**:
จะรักษาการแยก admin/editor ไหม (ข้อ 4.4 — **ข้อเสนอ: รักษาไว้**)

และ **1 ข้อจำกัดที่ไม่ใช่เรื่องเทคนิค**: ครึ่งหนึ่งของงานอยู่ในรีโปหน้าเว็บ (ข้อ 8.2)

### B2 User Mapping — **BLOCKED**

| | |
|---|---|
| ขาดอะไร | **อีเมลของบัญชีผู้เขียนฝั่ง Supabase** — ค่าเดียว |
| ทำไมยังไม่มี | Live Verification ตั้งใจไม่ดึงอีเมลตามที่สั่งไว้ตอนนั้น |
| ทำไมเดาไม่ได้ | กุญแจที่ unique ทั้งสองฝั่งมีแต่อีเมล · UUID generate แยกกันคนละฐาน · ชื่อ 177/198 เป็น NULL และไม่ unique |
| ขนาดปัญหา | **1 ราย** — เนื้อหาทั้งฐานเขียนโดยบัญชีเดียว (distinct = 1) |
| ปลดล็อกอย่างไร | **ข้อ 5.3 ทาง A** — รัน query เดียวบน Supabase คืนค่าเป็น sha256 ของอีเมล แล้วเทียบ · ไม่ต้องขนอีเมลข้ามระบบ · `pgcrypto` ยืนยันแล้วว่ามีทั้งสองฝั่ง |
| ถ้าปลดไม่ได้ | ข้อ 5.4 — ยอมให้เป็น NULL ทั้ง 15 แถว (005 รองรับอยู่แล้ว) หรือเพิ่มคอลัมน์เก็บ UUID เดิมใน migration 006 |

**B2 ไม่บล็อก B1** — เฟส 1 ของ B1 ไม่ต้องย้ายข้อมูล จึงไม่ต้องใช้ mapping
B2 บล็อกเฉพาะ **data migration ของ `courses` และ `news`**

---

## STOP

**รออนุมัติก่อนลงมือ**

เรื่องที่ต้องตัดสิน

1. **อนุมัติสถาปัตยกรรมเฟส 1** (ขยาย `webapi` ให้คุย PostgreSQL · ยังไม่ตัด Supabase Auth) หรือไม่
2. **รักษาการแยก admin/editor ไหม** (ข้อ 4.4 — ข้อเสนอ: รักษาไว้)
3. **B2** — รัน query sha256 ตามข้อ 5.3 ทาง A ไหม หรือเลือกยอมให้ `created_by` เป็น NULL เลย
4. **R4** — ปุ่มลบ 5 ที่ในหน้าผู้ดูแล: ยอมให้หายไป หรือให้ `advisor_api` DELETE ได้ใน migration ถัดไป
5. **R2** — `ai_settings` จะเข้มขึ้นจาก PUBLIC เป็น EDITOR ไหม (เป็นการเปลี่ยนพฤติกรรมเดิม)
6. **สิทธิ์เขียนรีโปหน้าเว็บ** — งานครึ่งหนึ่งอยู่ที่นั่น ต้องตกลงก่อนเริ่มขั้น 2

```
Production Write   NONE        Data Migration      NONE        Deploy / Restart   NONE
Apply Migration    NONE        แก้ Supabase        NONE        Commit / Push      NONE
Merge main         NONE        Re-embed            NONE
```
