# B1 Authorization Phase 1 — Web API Authorization Foundation

| | |
|---|---|
| วันที่ | 2026-10-02 (แก้ไขรอบที่ 2 — C2) |
| ขอบเขต | authorization foundation ของ `webapi` · ยังไม่ย้ายข้อมูล ยังไม่ cutover หน้าเว็บ |
| ไฟล์ที่แก้/เพิ่ม | **6 ไฟล์ · ทั้งหมดอยู่ใน `webapi/` ของรีโปนี้** |
| **ผลทดสอบ** | **webapi 52/52 ผ่าน** · regression **562 ผ่าน · 0 ไม่ผ่าน** |
| **C2** | **`RESOLVED` — existing public behavior preserved** |
| **C3** | **`ACCEPTED_TEMPORARILY`** |
| **B1_ACTIVE_USER_MAPPING_REQUIRED** | **`true`** |
| **G3** | **`G3_API_ENFORCEMENT_PENDING_B1`** ต่อ — ยังไม่มี write endpoint |
| **สถานะ** | **`READY_FOR_REVIEW`** |

```
Commit / Push         NONE    Apply Migration 005    NONE    Data Migration    NONE
Supabase Write        NONE    แก้ RLS / policy        NONE    Deploy / Restart  NONE
Production Write      NONE    Re-embed               NONE    Merge main        NONE
แก้รีโปหน้าเว็บ        NONE    แก้ Migration 005       NONE
```

**ไม่ใช่ `READY_FOR_PRODUCTION`**

---

## 1. Existing auth flow discovered

ตรวจจากโค้ดจริงทั้งหมด ไม่ได้เดา

### 1.1 มี **สาม** ระบบ ไม่ใช่สอง

```
                         Caddy  (Caddyfile)
                               |
   /api/chat ───────────────► backend:8000  /chat-web     FastAPI + JWT ของตัวเอง
   /api/sci-connect-news* ──► webapi:3001                 Supabase anon key
   /api/admin/* ───────────► webapi:3001                  Supabase JWT + user_profiles
   /api/* ─────────────────► backend:8000                 FastAPI + JWT ของตัวเอง
   ที่เหลือ ────────────────► ไฟล์ static ของ SPA
                               |
   SPA ในเบราว์เซอร์ ────────────────────────► Supabase PostgREST ตรง ๆ (anon key)
                                                ← ทางหลักของข้อมูลเกือบทั้งหมด
```

### 1.2 `webapi` — ด่านที่มีอยู่จริง

`webapi/server.mjs` เป็นตัวครอบบาง ๆ แปลง Node request → `Request` มาตรฐาน
แล้วเรียก handler 5 ตัว · **ไฟล์ handler อยู่ในรีโปหน้าเว็บ** ถูกคัดลอกเข้าตอน build
(`webapi/Dockerfile:18  COPY api ./api`) — รีโปนี้มีแค่ `Dockerfile` `package.json`
`README.md` `server.mjs`

ตรรกะตรวจสิทธิ์ของเดิมอยู่ที่ `api/_lib/adminAuth.js::requireAdminUser` (รีโปหน้าเว็บ)

```js
const ADMIN_ROLES = ['admin', 'editor'];

const token = (request.headers.get('authorization')||'').replace(/^Bearer\s+/i,'');
if (!token) return 401;                                    // {error:'Missing Authorization token'}

const supabase = createClient(url, anonKey, {
  global: { headers: { Authorization: `Bearer ${token}` } },  // scope ด้วย token ผู้เรียก
});
const { data:{user}, error } = await supabase.auth.getUser(token);
if (error || !user) return 401;                             // {error:'Unauthorized'}

const { data: profile } = await supabase.from('user_profiles')
  .select('role, status').eq('user_id', user.id).single();

if (!ADMIN_ROLES.includes(profile?.role) || profile?.status !== 'approved') return 403;  // {error:'Forbidden'}
```

สี่คุณสมบัติที่ต้องรักษา

| | |
|---|---|
| 1 | **ถาม Supabase เอง** (`auth.getUser`) ไม่ถอด JWT ในเครื่อง → token ที่ถูกเพิกถอนใช้ไม่ได้ทันที |
| 2 | `role IN ('admin','editor')` |
| 3 | `status = 'approved'` — **เข้มกว่า RLS ส่วนใหญ่** มี policy เดียวในฐานที่ตรวจ `status` |
| 4 | client ถูก **scope ด้วย token ผู้เรียก** → RLS บังคับซ้ำด้วยตัวตนจริง |

**ไม่พบว่าใช้ service-role key ที่ใดเลย** — ใช้ anon key + token ของผู้เรียกเท่านั้น

### 1.3 คำศัพท์ `role` / `status` ที่ระบบใช้จริง — ไม่ได้ตั้งเอง

| | ค่า | ที่มา |
|---|---|---|
| `role` | `admin` · `editor` · `user` | `user` เป็นค่าที่ trigger `handle_new_user` ให้ · `src/lib/adminAuth.js: ADMIN_ROLES = ['admin','editor']` |
| `status` | `approved` · `pending` | `src/pages/Admin/UserManagement.jsx` สลับสองค่านี้ · `ProtectedAdminRoute.jsx:58` ตรวจ `'pending'` |
| เกณฑ์เข้าพื้นที่ผู้ดูแล | `canAccessAdminArea = ADMIN_ROLES.includes(role) && status === 'approved'` | `src/lib/adminAuth.js` |
| ของจริงใน production | admin/approved **2** · user/approved **1** · **ไม่พบ `editor` เลย** | Live Verification ข้อ 9 |

**ไม่ต้องเดาคำศัพท์** — ตรงกับที่คำสั่งระบุทุกข้อ ไม่มีการเปลี่ยน semantics

### 1.4 กรณีที่ต้องลอกให้ตรง: ไม่มีแถวใน `user_profiles`

`requireAdminUser` ใช้ `profile?.role` ซึ่งเป็น `undefined` แล้วตกเกณฑ์ทุกข้อ → **403**
ส่วน `src/lib/adminAuth.js` ฝั่งเบราว์เซอร์ใส่ค่าตั้งต้น `role: 'user'`, `status: 'approved'`

ด่านใหม่ลอก **ฝั่งเซิร์ฟเวอร์** คือ **ไม่ใส่ค่าตั้งต้นเลย** (`role = null`, `status = null`)
→ ทุกระดับที่ต้องมีสิทธิ์ปฏิเสธ · มีข้อตรวจคุ้มไว้

### 1.5 ข้อจำกัดที่กำหนดรูปของงานนี้

**`api/` ทั้งโฟลเดอร์เป็นของรีโปหน้าเว็บ และรอบนี้ห้ามแตะ** (Owner decision ข้อ 5)

→ ด่านกลางต้องอยู่ **ข้าง `server.mjs` ในรีโปนี้** แล้วบังคับ **ก่อน** ส่งคำขอเข้าฟังก์ชัน
ของหน้าเว็บ · **ไม่แทนที่** `requireAdminUser` ที่ handler เรียกอยู่ เป็นการเพิ่มชั้นนอก

---

## 2. Architecture after Phase 1

```
SPA (เบราว์เซอร์)
  │ ล็อกอิน / ต่ออายุ token
  └──────────────────────────────► Supabase Auth          ← ยังไม่ตัด ตามที่สั่ง
  │
  │ Authorization: Bearer <supabase access token>
  └──► Caddy /api/* ──► webapi:3001
                          │
                          ├─ [ใหม่] server.mjs  ด่านกลาง
                          │    ตาราง ROUTES ประกาศระดับสิทธิ์ของทุกเส้นทาง
                          │    ไม่ประกาศ = บริการไม่ยอมเริ่มทำงาน (exit 1)
                          │    ปฏิเสธ 401/403 "ก่อน" เรียก handler
                          │
                          └─ [เดิม ไม่แตะ] api/*.js
                               ยังเรียก requireAdminUser ของตัวเอง
                               ยังใช้ client ที่ scope ด้วย token ผู้เรียก (RLS บังคับซ้ำ)
```

**แหล่งข้อมูลยังเป็น Supabase ทั้งหมด** — รอบนี้สร้างด่าน ยังไม่ย้ายข้อมูล

| คง | ย้ายภายหลัง |
|---|---|
| Supabase Auth · `user_profiles` (role/status) · Storage | `courses` · `news` · `knowledge_articles` · `ai_settings` · `external_news` → PostgreSQL `web` |

**ไม่ย้าย authentication ไป FastAPI JWT** ตามที่สั่ง — ไม่มีโค้ดใดในรอบนี้แตะ `backend/`

---

## 3. Files modified

| ไฟล์ | | |
|---|---:|---|
| `webapi/auth.mjs` | **+377 ใหม่** | ด่านตรวจตัวตนและสิทธิ์กลาง |
| `webapi/auth.test.mjs` | **+440 ใหม่** | 36 test — ตรรกะการตัดสินสิทธิ์ |
| `webapi/server.test.mjs` | **+269 ใหม่** | 9 test — ระดับ HTTP จริง |
| `webapi/server.mjs` | **+119 −13** | ตาราง ROUTES มีระดับสิทธิ์ · บังคับก่อน dispatch · `/healthz` ประกาศระดับ |
| `webapi/Dockerfile` | **+7 −2** | `COPY server.mjs auth.mjs ./` — **ถ้าลืม คอนเทนเนอร์พังตอนเริ่มทำงาน** |
| `webapi/package.json` | **+3** | `"test": "node --test *.test.mjs"` |

**รวม `+1215 −15`** · ไม่เพิ่ม dependency ใด (ใช้ `node:test` ที่มาพร้อม Node 22+)

### 3.1 ไฟล์ที่ **ไม่** ถูกแตะ

```
db/migrations/005_web_schema.sql    git diff ว่างเปล่า
backend/ · eval/ · pipeline/ · db/  git diff --name-only = 0 ไฟล์
Caddyfile · docker-compose.prod.yml ไม่แก้
รีโปหน้าเว็บ (LastProject)          ไม่แตะ — ไฟล์ที่มี diff อยู่ที่นั่นลงวันที่ 09-22 · 09-23 · 09:53
                                     ซึ่งมาก่อนงานรอบนี้ทั้งหมด
```

---

## 4. Central auth implementation

`webapi/auth.mjs` — ไม่มี I/O ตอนโหลดโมดูล ทุกอย่างรับ dependency เข้ามา

### 4.1 รูปร่างหลัก

```js
parseBearer(headerValue)            -> {kind:'none'} | {kind:'malformed'} | {kind:'token', token}
resolveAuthContext(request, deps)   -> {ok:true, context} | {ok:false, status, body}
authorize(context, level)           -> {ok:true} | {ok:false, status, body}
isPrivileged(context)               -> boolean  (เท่ากับระดับ EDITOR)
validateRouteTable(routes)          -> string[]  รายชื่อเส้นทางที่ไม่ประกาศระดับ
describeForLog(context)             -> string   ปลอดภัยพอจะเขียนลง log
```

`deps` = `{ verifyToken(token), readProfile(userId) }` → ทดสอบได้โดยไม่แตะ Supabase

### 4.2 auth context

```js
{ authenticated: boolean, userId: string|null, role: string|null, status: string|null }
```

เป็น `Object.freeze` → **แก้กลางทางไม่ได้** มีข้อตรวจยืนยันว่า assignment โยน `TypeError`

### 4.3 ตัดสินใจเชิงออกแบบ 6 ข้อ และเหตุผล

| # | ตัดสินใจ | เหตุผล |
|---|---|---|
| 1 | **ถาม Supabase ทุกคำขอ ไม่ถอด JWT ในเครื่อง** | ลอกพฤติกรรมเดิม → ถอนสิทธิ์มีผลทันที ไม่ต้องรอ token หมดอายุ · แลกกับ latency และการพึ่งพา Supabase (ดูความเสี่ยง R5) |
| 2 | **ไม่แคชผลตรวจสิทธิ์** | การลดสิทธิ์ผู้ใช้ต้องมีผลกับคำขอถัดไปเลย · SPA แคชฝั่งเบราว์เซอร์ไว้แล้วเพื่อ UX ซึ่งเป็นที่ที่เหมาะกว่า |
| 3 | **ไม่ใส่ค่าตั้งต้นให้ role/status เมื่อไม่มีแถวใน `user_profiles`** | ลอก `requireAdminUser` ฝั่งเซิร์ฟเวอร์ (ข้อ 1.4) · การใส่ `status:'approved'` ตั้งต้นแบบฝั่งเบราว์เซอร์จะหลวมกว่าของเดิม |
| 4 | **ข้อมูลยืนยันตัวตนที่ใช้ไม่ได้ → ลดระดับเป็น anonymous ที่ `resolveAuthContext` แล้วให้ `authorize()` ตัดสิน** | **แก้ตามการตัดสินใจ C2** · เส้นทางสาธารณะต้องไม่ใช้งานไม่ได้เพราะ header ที่ติดมา · ความปลอดภัยไม่ลดลงเพราะ context ที่ได้เป็น anonymous ทุกฟิลด์ และระดับที่ต้องมีสิทธิ์ยังได้ 401 เหมือนเดิม — ดูข้อ 15.1 |
| 5 | **อ่าน `user_profiles` ไม่ได้ → `role = null`** | ไม่รู้สิทธิ์ = ต้องไม่เดาว่ามีสิทธิ์ · ยังถือว่าล็อกอินแล้ว (ระดับ AUTHENTICATED ผ่าน) |
| 6 | **ไม่ใช้ service-role key** | สถาปัตยกรรมเดิมไม่ได้ต้องการ · anon key + token ผู้เรียก ทำให้ RLS ยังบังคับด้วยตัวตนจริง |

### 4.4 หนึ่งคำขอ = หนึ่ง Supabase client

`createRuntimeDeps()` สร้าง client ต่อ token เพราะ header `Authorization` ติดไปกับ
**client** ไม่ใช่กับ query — client ที่ใช้ร่วมกันข้ามคำขอจะทำให้ตัวตนรั่วข้ามผู้ใช้
และ `readProfile` ใช้ client ตัวเดียวกับ `verifyToken` เพื่อให้การอ่านโปรไฟล์ถูกบังคับ
ด้วย RLS ในนามผู้เรียกเอง

### 4.5 นำเข้า `@supabase/supabase-js` แบบ dynamic ภายในฟังก์ชัน

ไม่ใช่ที่หัวไฟล์ — เพื่อให้ชุดทดสอบนำเข้า `auth.mjs` ได้โดยไม่ต้องติดตั้งไลบรารี
(รีโปนี้ไม่มี `webapi/node_modules`) ชุดทดสอบส่ง `verifyToken`/`readProfile` ปลอมเข้ามา
จึง **ไม่เคยแตะ Supabase จริงแม้ครั้งเดียว**

---

## 5. Authorization levels

```
PUBLIC            ไม่ต้องมี token
PUBLIC_FILTERED   ไม่ต้องมี token แต่ถ้ามีและมีสิทธิ์จะเห็นมากขึ้น (ไว้ใช้กับ news)
AUTHENTICATED     token ใช้ได้
EDITOR            token ใช้ได้ AND status = 'approved' AND role IN ('admin','editor')
ADMIN             token ใช้ได้ AND status = 'approved' AND role = 'admin'
```

| กฎที่สั่ง | ยืนยันด้วยข้อตรวจ |
|---|---|
| admin ต้องผ่านระดับ editor ได้ | ข้อ 6 — `admin` อยู่ในชุด role ของ EDITOR โดยเจตนา |
| editor ห้ามผ่าน admin | ข้อ 5 — 403 |
| user ห้ามผ่าน editor/admin | ข้อ 3 · 3b — 403 |
| status ที่ไม่ใช่ `approved` ห้ามทำงานที่ต้องมีสิทธิ์ | ข้อ 8 · 8c |

### 5.1 `PUBLIC_FILTERED` ประกาศไว้แล้วแต่ยังไม่มีเส้นทางใดใช้

เตรียมไว้สำหรับ `GET /api/news` ซึ่งต้องกรอง `status='published'` ให้คนทั่วไป
`isPrivileged(context)` คือตัวช่วยที่ endpoint นั้นจะใช้ตัดสินว่าควรกรองไหม
**ยังไม่สร้าง endpoint ในรอบนี้**

---

## 6. Role / status rules

### 6.1 ไม่เปลี่ยน semantics ของระบบเดิม

| | ของเดิม (`requireAdminUser`) | ด่านใหม่ |
|---|---|---|
| role ที่ยอม | `['admin','editor']` | EDITOR = เหมือนกัน · เพิ่ม ADMIN = `['admin']` แยกออกมา |
| status | `=== 'approved'` | **เหมือนกันเป๊ะ** รวมถึงไม่ยอม `'APPROVED'` หรือ `' approved'` |
| ไม่มีโปรไฟล์ | 403 | **403 เหมือนกัน** |

### 6.2 ปฏิเสธเป็นค่าตั้งต้นในทุกจุดที่ตัดสินใจ

| จุด | ค่าที่ไม่รู้จัก |
|---|---|
| ระดับสิทธิ์ที่ route ประกาศ | ไม่อยู่ใน `LEVELS` → **403** และตอนเริ่มบริการ → **exit 1** |
| `status` | ไม่ใช่ `'approved'` → 403 (รวม `pending` · `rejected` · `inactive` · ค่าว่าง · `null`) |
| `role` | ไม่อยู่ในชุดของระดับนั้น → 403 |
| `deps` ไม่ครบ | **500** ไม่ใช่ปล่อยผ่าน |
| ค่าตั้งค่า Supabase ไม่ครบ | เส้นทางที่ต้องมีสิทธิ์ → **500** ทุกครั้ง |

### 6.3 ⚠ `editor` ยังไม่มีใครถือในของจริง

Live Verification พบ admin 2 · user 1 · **ไม่มี `editor`** → เส้นทาง EDITOR วันนี้
มีแต่ admin ที่ผ่านได้ · การแยกสองระดับยังเป็นของที่ออกแบบไว้แต่ยังไม่มีใครใช้
**รักษาไว้ตาม Owner decision ข้อ 2** เพราะยุบแล้วแยกกลับทำไม่ได้

---

## 7. Route protection changes

### 7.1 ตาราง `ROUTES` ประกาศระดับสิทธิ์

```js
const ROUTES = [
  ["/api/sci-connect-news-detail", "./api/sci-connect-news-detail.js", PUBLIC],
  ["/api/sci-connect-news",        "./api/sci-connect-news.js",        PUBLIC],
  ["/api/admin/extract-file",      "./api/admin/extract-file.js",      EDITOR],
  ["/api/admin/ingest",            "./api/admin/ingest.js",            EDITOR],
  ["/api/admin/sync-sci-news",     "./api/admin/sync-sci-news.js",     EDITOR],
];
```

**ระดับที่ตั้งตรงกับพฤติกรรมที่มีอยู่จริงวันนี้ ไม่เข้มขึ้นและไม่หลวมลง** —
ข่าว Sci Connect หน้าเว็บเรียกโดยไม่ล็อกอินอยู่แล้ว · `/api/admin/*` ของเดิมเรียก
`requireAdminUser` ซึ่งยอม admin+editor ที่ `approved` = ตรงกับ EDITOR

### 7.2 ปฏิเสธตอนเริ่มทำงาน ไม่ใช่ตอนมีคนเรียก

```js
const undeclared = validateRouteTable(ROUTES);
if (undeclared.length > 0) { console.error(...); process.exit(1); }
```

ของเดิมพึ่งพาว่าคนเขียนฟังก์ชันใหม่จะจำได้ว่าต้องเรียก `requireAdminUser`
**ลืมที่เดียวคือเส้นทางนั้นเปิดโล่งเงียบ ๆ** — รูปแบบเดียวกับที่ FastAPI ฝั่งเราเลือกใช้
`require_admin` คลุมทั้ง router แทนการใส่ทีละเส้นทาง (`routes/crawl_review.py:48`)

มีข้อตรวจระดับ HTTP ยืนยันว่าเส้นทางที่ไม่ประกาศระดับทำให้บริการ **exit 1** จริง

### 7.3 `/healthz` ประกาศระดับสิทธิ์ออกมาด้วย

```json
{"status":"ok","authConfigured":true,
 "routes":[{"route":"/api/admin/ingest","level":"EDITOR"}, ...]}
```

ตรวจจากภายนอกได้ว่าเส้นทางไหนถูกคุ้มระดับใด โดยไม่ต้องอ่านโค้ด — เป็นสัญญาที่เปิดเผยได้
ไม่ใช่ความลับ

### 7.4 ไม่สร้าง endpoint ใหม่เพียงเพื่อให้ matrix ครบ

ตามที่สั่ง — `GET/POST/PATCH/DELETE` ของ `courses` · `news` · `knowledge_articles` ·
`ai_settings` **ยังไม่มีในรอบนี้** foundation พร้อมรับเมื่อถึงเวลา

`ai_settings` คงพฤติกรรมเดิมไว้ก่อนตาม Owner decision ข้อ 4 — ยังไม่เปลี่ยน PUBLIC → EDITOR

---

## 8. 401 / 403 / 404 behaviour

### 8.1 ตารางพฤติกรรมจริง — วัดจากโค้ดที่รันอยู่

```
                      PUBLIC    PUBLIC_FILTERED  AUTHENTICATED  EDITOR  ADMIN   ได้สิทธิ์?
ไม่มี header           200       200              401            401     401     ไม่
header พัง (Basic)     200       200              401            401     401     ไม่
Bearer เปล่า           200       200              401            401     401     ไม่
token ใช้ไม่ได้        200       200              401            401     401     ไม่
token ของ admin        200       200              200            200     200     ใช่
```

**ทุกแถวที่ข้อมูลยืนยันตัวตนใช้ไม่ได้ ให้ "ไม่ได้สิทธิ์" ทั้งหมด** — ลดระดับเป็น
anonymous ได้เท่านั้น ไม่มีทางไต่ขึ้นไป

### 8.2 รายละเอียดต่อสถานการณ์

| สถานการณ์ | รหัส | body |
|---|---|---|
| ไม่มี header → เส้นทางสาธารณะ | **200** | ผลลัพธ์จริง |
| **header ผิดรูปแบบ → เส้นทางสาธารณะ** | **200** | **ผลลัพธ์จริง (ในฐานะ anonymous)** ⬅ C2 |
| **token ใช้ไม่ได้ / ตัวตรวจล้ม → เส้นทางสาธารณะ** | **200** | **ผลลัพธ์จริง (ในฐานะ anonymous)** ⬅ C2 |
| ไม่มี header → เส้นทางที่ต้องมีสิทธิ์ | **401** | `{"error":"Unauthorized"}` |
| header ผิดรูปแบบ → เส้นทางที่ต้องมีสิทธิ์ | **401** | `{"error":"Unauthorized"}` |
| token ใช้ไม่ได้ / หมดอายุ / ตัวตรวจล้ม → เส้นทางที่ต้องมีสิทธิ์ | **401** | `{"error":"Unauthorized"}` |
| ล็อกอินแล้วแต่สิทธิ์ไม่พอ | **403** | `{"error":"Forbidden"}` |
| เส้นทางที่บริการนี้ไม่รับผิดชอบ | **404** | `{"error":"not found"}` |
| ตั้งค่า Supabase ไม่ครบ (เส้นทางที่ต้องมีสิทธิ์) | **500** | `{"error":"Authorization is not configured"}` |

### 8.3 ไม่แยก 401 สามแบบโดยเจตนา

"ไม่ได้ส่ง token" · "token เพี้ยน" · "token หมดอายุ" ตอบเหมือนกันหมด
การแยกให้ชัดคือการบอกผู้โจมตีว่าเดาไปถึงขั้นไหนแล้ว

### 8.4 404 มาก่อนตรวจสิทธิ์

เส้นทางที่บริการนี้ไม่รับผิดชอบไม่ใช่ความลับ — Caddy เป็นผู้ตัดสินว่าคำขอไหนมาถึงที่นี่อยู่แล้ว

---

## 9. Security controls

| | |
|---|---|
| ไม่ hardcode คีย์/token/รหัสผ่าน | ค่าตั้งค่าอ่านจาก env เท่านั้น · สแกน diff แล้วไม่พบ JWT / `sk-` / bcrypt hash / private key / base64 ยาว / `service_role` |
| ไม่พิมพ์ `.env` | `console.error` ตอนตั้งค่าไม่ครบบอกแค่ว่า "ไม่พบค่าตั้งค่า" ไม่พิมพ์ชื่อหรือค่าใด |
| **ไม่ log Authorization header หรือ token** | สแกนแล้วไม่มี `console.*` ใดที่มีคำว่า authorization/token/Bearer |
| log ของการปฏิเสธมีเฉพาะ | `describeForLog()` → `anonymous` หรือ `authenticated role=admin status=approved` · **ไม่มี uuid ไม่มีอีเมล ไม่มี token** · มีข้อตรวจยืนยัน |
| ไม่ส่งคำตอบดิบจาก Supabase ออกไป | body ตอบกลับมีคีย์ `error` เดียว · มีข้อตรวจว่าไม่มีคำว่า token/Bearer/supabase/jwt/uuid/sql |
| ไม่ใช้ service-role key | ใช้ anon key + token ผู้เรียก เหมือนของเดิม |
| ไม่แก้ RLS / policy | ไม่มีคำสั่ง SQL ใดในรอบนี้ |
| ไม่เชื่อค่าจาก request | ด่านอ่านจาก header เท่านั้น · ไม่เคยอ่าน body · context เป็น `Object.freeze` |

### 9.1 ค่าสมมติในชุดทดสอบ

`not-a-real-token` · `not-a-real-anon-key-for-tests-only` · `http://supabase.test.invalid`
— โดเมน `.invalid` และ `.test` สงวนไว้ตาม RFC 2606 ไม่มีอยู่จริง
**ไม่มี token หรือคีย์ของโปรเจกต์จริงในชุดทดสอบ**

---

## 10. created_by / updated_by status

**ยังเขียนลงฐานข้อมูลไม่ได้ และนั่นเป็นข้อสรุปที่ตั้งใจ ไม่ใช่งานที่ลืมทำ**

### 10.1 สิ่งที่ทำได้แล้ว

```js
stripAuthorFields(payload)   -> ตัด created_by / updated_by ออกจากสิ่งที่ผู้เรียกส่งมา
                                คืน object ใหม่ ไม่แก้ของเดิม  (มีข้อตรวจ)
resolveAuthorId(context)     -> ปฏิเสธเสมอ พร้อมรหัส B1_ACTIVE_USER_MAPPING_REQUIRED
authorFieldsFor(mode, ctx)   -> create: ตั้งทั้งสองคอลัมน์ · update: ตั้งแต่ updated_by
                                ตอนนี้คืน ok:false ทุกครั้ง  (มีข้อตรวจ)
```

`stripAuthorFields` จำเป็นจริง — วันนี้หน้าเว็บส่ง `updated_by: user?.id` มาเองที่
`KnowledgeForm.jsx:138` ซึ่ง RLS ต้นทางไม่ได้กัน ถ้าชั้น API เชื่อค่านั้น ใครก็อ้างเป็นคนอื่นได้

### 10.2 UPDATE ห้ามแตะ `created_by` เลย

เข้มกว่าที่สั่ง — ไม่ใช่แค่ "ห้ามเปลี่ยนจาก client input" แต่ **ห้ามแตะเลยแม้จะตั้งจาก token**

เพราะแถว legacy มี `created_by` เป็น NULL ซึ่งหมายความว่า *"ยังแมปผู้เขียนเดิมไม่ได้"*
ถ้า UPDATE เขียนค่าลงไป ความหมายจะกลายเป็น *"คนที่เพิ่งมาแก้เป็นคนสร้าง"* ซึ่งไม่จริง
— เป็นการยัดเจ้าของผิดคนแบบเดียวกับที่ห้ามไว้ตอน migration เพียงแต่เกิดภายหลัง
ผ่านการใช้งานปกติ

### 10.3 ไม่ปน legacy NULL กับข้อมูลใหม่

| | `created_by` |
|---|---|
| แถว legacy 15 แถว (12 courses + 3 news) | **NULL** = "ยังแมปผู้เขียนเดิมไม่ได้" |
| ข้อมูลใหม่หลัง cutover | **ต้องมาจากตัวตนที่ยืนยันแล้ว** — ถ้าทำไม่ได้ ต้องปฏิเสธการเขียน ไม่ใช่เขียน NULL |

`authorFieldsFor` คืน `ok:false` → endpoint ที่เรียกมันต้องปฏิเสธคำขอ
**ไม่ใช่เขียน NULL แล้วเดินหน้า** ซึ่งจะทำให้แถวใหม่แยกจากแถว legacy ไม่ออก

---

## 11. B1_ACTIVE_USER_MAPPING_REQUIRED

# `true`

| | |
|---|---|
| ปัญหา | `auth.users.id` (Supabase) กับ `public.users.id` (PostgreSQL) เป็น uuid ที่สร้างแยกกันคนละฐาน **ไม่มีเส้นเชื่อมกันเลย** |
| ถ้าเอาค่าหนึ่งไปใส่อีกที่ | ชี้ไปผู้ใช้ที่ไม่มีอยู่ (FK ปฏิเสธ) หรือแย่กว่านั้นคือชี้ไปผู้ใช้คนอื่น |
| ทางที่จับคู่ได้ | **มีแต่อีเมล** — และยังไม่มีการออกแบบที่ปลอดภัยสำหรับผู้ใช้ที่ยังใช้งานอยู่ |
| ของ legacy ปิดไปแล้วไหม | ปิดแล้วด้วย NULL (`RESOLVED_WITH_NULL_LEGACY_AUTHOR`) **แต่ใช้กับแถวเก่า 15 แถวเท่านั้น ไม่ใช่กับข้อมูลใหม่** |

**STOP เฉพาะส่วน author-write implementation** ตามที่สั่ง · authorization foundation
ทำต่อได้และทำเสร็จแล้ว

### 11.1 สิ่งที่ยืนยันว่าไม่ได้ทำ

```
ไม่ได้สร้าง mapping เอง            ไม่ได้ map ด้วยชื่อ
ไม่ได้ map ด้วย uuid ข้ามระบบ      ไม่ได้สร้างผู้ใช้ใหม่
ไม่ได้ fallback ไป admin           ไม่ได้เชื่อ author id จาก client
```

`resolveAuthorId()` มีคอมเมนต์กำกับว่า **ห้ามแก้ให้คืนค่าอะไรจนกว่าจะมีการออกแบบ
mapping ที่ได้รับอนุมัติ** และมีข้อตรวจยืนยันว่ามันไม่คืน `id` ออกมาเลย

---

## 12. G3 status

# `G3_API_ENFORCEMENT_PENDING_B1`

**ยังค้างต่อ** — รอบนี้ **ไม่ได้สร้าง** write endpoint ของ `web.site_courses` / `web.news`
จึงยังไม่มีอะไรให้ทดสอบ · **ไม่สร้าง endpoint ปลอมเพื่อให้ test ผ่าน** ตามที่สั่ง

```
ค้าง   G3 API บังคับ created_by immutability             — G3_API_ENFORCEMENT_PENDING_B1
ค้าง   G3 PATCH ที่ส่ง created_by ปลอมมาใน body ต้องไม่มีผล  — G3_API_ENFORCEMENT_PENDING_B1
```

### 12.1 แต่รอบนี้ปิดส่วนที่ปิดได้แล้ว

| ที่ G3 ต้องการ | สถานะหลังรอบนี้ |
|---|---|
| client ส่ง `created_by` มาแล้วต้องไม่มีผล | **มีกลไกแล้ว** — `stripAuthorFields` + ข้อตรวจ (auth.test ข้อ 9b) |
| client ส่ง `role=admin` มาแล้วต้องไม่ได้สิทธิ์สูงขึ้น | **ปิดแล้ว** — ข้อตรวจระดับตรรกะ (ข้อ 9) + ระดับ HTTP จริง |
| UPDATE ห้ามเปลี่ยน `created_by` | **มีสัญญาในโค้ดแล้ว** (`authorFieldsFor('update')` ไม่มี `created_by`) · **ยังไม่มี endpoint ให้ทดสอบ end-to-end** |

สองข้อที่ค้างจะปิดได้เมื่อมี endpoint จริง ซึ่งต้องรอการจับคู่ผู้ใช้ (ข้อ 11)

---

## 13. Test results

### 13.1 `webapi` — **52 / 52 ผ่าน · 0 ไม่ผ่าน**

```
cd webapi && npm test        (node --test *.test.mjs)

auth.test.mjs      42 test    ตรรกะการตัดสินสิทธิ์  ไม่แตะ Supabase จริง
server.test.mjs    10 test    ระดับ HTTP จริง  บูต server.mjs กับ handler ปลอม
```

(รอบแรก 45 ข้อ · รอบแก้ C2 เพิ่ม 7 ข้อ — ดูข้อ 13.5)

**10 ข้อที่กำหนดไว้ ครบทุกข้อ**

| # | ข้อที่สั่ง | ผล |
|---|---|---|
| 1 | ไม่มี token → protected = 401 | **ผ่าน** (ทั้ง AUTHENTICATED · EDITOR · ADMIN) |
| 2 | token ใช้ไม่ได้ → 401 | **ผ่าน** |
| 3 | user ธรรมดา → editor route = 403 | **ผ่าน** |
| 4 | editor + approved → editor route ผ่าน | **ผ่าน** |
| 5 | editor → admin route = 403 | **ผ่าน** |
| 6 | admin + approved → editor route ผ่าน | **ผ่าน** |
| 7 | admin + approved → admin route ผ่าน | **ผ่าน** |
| 8 | role มีสิทธิ์แต่ status ≠ approved → 403 | **ผ่าน** (admin/pending · editor/pending · และค่าอื่น 7 แบบ) |
| 9 | body ส่ง `role=admin` ไม่ทำให้สิทธิ์สูงขึ้น | **ผ่าน** ทั้งระดับตรรกะและระดับ HTTP |
| 10 | header ผิดรูปแบบ → 401 | **ผ่าน** (7 รูปแบบ · เฉพาะระดับที่ต้องมีสิทธิ์ ดูข้อ 13.5) |

**ข้อที่เพิ่มเองเพราะสำคัญ**

```
ไม่มีแถวใน user_profiles = ไม่มีสิทธิ์ (ไม่เดาค่าตั้งต้น)
ตัวตรวจ token ล้ม (Supabase ล่ม) → 401 ไม่ใช่ปล่อยผ่านเป็น anonymous
อ่าน user_profiles ไม่ได้ → ไม่เดาว่ามีสิทธิ์
ไม่ส่ง deps มา → 500 ไม่ใช่ปล่อยผ่าน
ระดับสิทธิ์ที่ไม่รู้จัก → ปฏิเสธ ไม่ใช่ปล่อยผ่าน
describeForLog ไม่มี uuid / อีเมล / token
body ตอบกลับไม่มีรายละเอียดภายใน
validateRouteTable จับเส้นทางที่ไม่ประกาศระดับ (10 กรณี)
```

### 13.2 ข้อตรวจที่สำคัญที่สุดในชุด HTTP

```
✔ เส้นทาง EDITOR ไม่มี token ได้ 401 และ handler ไม่ถูกเรียกเลย
✔ เส้นทาง EDITOR ที่มี token ซึ่งตรวจไม่ผ่าน ได้ 401 และ handler ไม่ถูกเรียก
✔ ค่าใน body ที่อ้างว่าเป็น admin ไม่ทำให้ผ่าน
✔ เส้นทางที่ไม่ประกาศระดับสิทธิ์ ทำให้บริการไม่ยอมเริ่มทำงาน   (exit 1)
```

handler ปลอมบันทึกการถูกเรียกลงไฟล์ → ชุดทดสอบยืนยันได้ว่า **ด่านกันก่อนถึงฟังก์ชัน
ไม่ใช่กันทีหลัง** · ด่านที่ถูกต้องแต่ไม่ถูกเรียกใช้ก็ไม่กันอะไร

### 13.3 ⚠ บั๊กในโค้ดทดสอบของผมเองที่พบและแก้แล้ว 2 จุด

| # | อาการ | สาเหตุ |
|---|---|---|
| 1 | 3 ข้อตก `TypeError: Cannot convert argument to a ByteString` | ค่าของ header HTTP ต้องเป็น latin-1 — ผมใส่ภาษาไทยเป็น token สมมติ · เปลี่ยนเป็น ASCII และใส่คอมเมนต์กำกับไม่ให้ใครเผลอใส่กลับ |
| 2 | ชุดทดสอบตกด้วย `EBUSY: rmdir` ทั้งที่ข้อตรวจผ่านหมด | Windows ล็อก cwd ของโปรเซสที่ยังอยู่ · แก้ให้รอลูกออกก่อนลบ และความล้มเหลวของการเก็บกวาดไม่ถูกรายงานเป็นข้อตรวจที่ไม่ผ่าน |

### 13.5 ชุดทดสอบของ C2 — 7 ข้อที่เพิ่มในรอบแก้

| ข้อที่สั่ง | ผล |
|---|---|
| 1. PUBLIC + malformed → allowed | **ผ่าน** |
| 2. PUBLIC + invalid token → allowed as anonymous | **ผ่าน** |
| 3. PUBLIC_FILTERED + malformed → allowed as anonymous | **ผ่าน** พร้อมยืนยัน `role`/`status`/`userId` เป็น `null` และ `isPrivileged = false` |
| 4. PUBLIC_FILTERED + invalid token → allowed as anonymous | **ผ่าน** เงื่อนไขเดียวกัน |
| 5. EDITOR + malformed → 401 | **ผ่าน** |
| 6. EDITOR + invalid → 401 | **ผ่าน** |
| 7. ADMIN + malformed → 401 | **ผ่าน** |
| 8. AUTHENTICATED + malformed → 401 | **ผ่าน** |

ข้อที่เพิ่มเองเพราะเป็นหัวใจของความปลอดภัยในการเปลี่ยนนี้

```
C2 ข้อมูลยืนยันตัวตนที่ใช้ไม่ได้ เพิ่ม role หรือ status ให้ตัวเองไม่ได้
   -> เทียบ context ทุกฟิลด์กับ anonymous และยืนยันว่า freeze แก้ไม่ได้ (5 รูปแบบ)
C2 ANONYMOUS_AUTH_FAILED ให้สิทธิ์เท่ากับ ANONYMOUS เป๊ะ
   -> วนทุกระดับใน LEVELS เทียบผลทีละระดับ  ธง authFailed ต้องไม่มีผลต่อการตัดสินสิทธิ์
C2 ตัวตรวจ token ล้ม — สาธารณะยังใช้ได้ · ที่ต้องมีสิทธิ์ยังได้ 401
C2 PUBLIC ไม่ต้องหาตัวตนเลย แต่ระดับอื่นต้องหา
C2 (HTTP จริง) เส้นทางสาธารณะ + header พัง/token ใช้ไม่ได้ ได้ 200 และ handler ถูกเรียก
```

ข้อสุดท้ายเป็นข้อที่พิสูจน์ C2 จริง — ยิง HTTP เข้าเซิร์ฟเวอร์ที่รันอยู่ด้วย header
4 แบบ แล้วยืนยันว่า **handler ถูกเรียกทุกครั้ง** ไม่ใช่แค่ได้รหัส 200

### 13.6 ข้อตรวจที่ต้องปรับให้ตรงกับการตัดสินใจใหม่ 2 ข้อ

| ข้อเดิม | เปลี่ยนเป็น |
|---|---|
| *"token ที่ใช้ไม่ได้ ได้ 401 แม้เส้นทางนั้นเปิดสาธารณะ"* | **ลบ** — ขัดกับ C2 โดยตรง · แทนด้วยชุด C2 ทั้งชุด |
| *"ตัวตรวจ token ล้ม ต้องได้ 401 ไม่ใช่ปล่อยผ่านเป็น anonymous"* | **ปรับ** เป็น *"ตัวตรวจ token ล้ม ต้องไม่กลายเป็นผู้ใช้ที่มีสิทธิ์"* — การปฏิเสธย้ายจาก `resolveAuthContext` ไป `authorize()` แต่สิ่งที่ต้องไม่เปลี่ยนคือ "ล้มแล้วต้องไม่ได้สิทธิ์" ซึ่งยังคุ้มอยู่ |

**บันทึกไว้ให้ชัดว่าเกณฑ์เปลี่ยน** — ไม่ใช่ว่าข้อตรวจเดิมผิด แต่ความต้องการเปลี่ยน

### 13.4 ข้อจำกัดของชุดทดสอบที่ต้องรู้

| | |
|---|---|
| ไม่ได้ทดสอบกับ Supabase จริง | โดยเจตนา — `verifyToken`/`readProfile` เป็นตัวปลอม · **ยังไม่มีการยืนยันว่า `auth.getUser` ของจริงคืนรูปแบบที่ `createSupabaseVerifier` คาดไว้** ต้องยืนยันตอน deploy (ดู R1) |
| ไม่ได้ทดสอบ handler จริงของหน้าเว็บ | `api/` ไม่มีในรีโปนี้ · ชุด HTTP ใช้ handler ปลอม |
| ชุด HTTP ใช้พอร์ต 56421 / 56422 | ถ้าพอร์ตถูกใช้อยู่ ชุดจะล้มด้วย timeout ที่อ่านเข้าใจได้ |

## 14. Regression results

**ไม่มี regression** — ทุกชุดได้ตัวเลขเท่าเดิมทุกตัว

| ชุด | ผล |
|---|---|
| `eval/web_schema_check.py` | **103 ผ่าน · 0 ไม่ผ่าน · ค้าง 2** เท่าเดิม — **G1/G2 ไม่พัง** |
| `eval/crawl_download_check.py` | 140 ผ่าน · 0 ไม่ผ่าน · ข้าม 1 |
| `eval/crawl_ingest_worker_check.py` | 187 ผ่าน · 0 ไม่ผ่าน |
| `eval/crawl_approval_check.py` | 84 ผ่าน · 0 ไม่ผ่าน |
| `eval/crawl_state_check.py` | 32 ผ่าน · 0 ไม่ผ่าน |
| `eval/document_endpoint_check.py` | 16 tests OK |
| **รวม** | **562 ผ่าน · 0 ไม่ผ่าน · ค้าง 2 · ข้าม 1** |

migration 001 → 005 จากฐานใหม่ยังผ่านครบ · ลง 005 ซ้ำยังไม่ error ·
ทำความสะอาดแล้ว containers 0 · volumes 0

**รวมทั้งหมดในรอบนี้: 562 + 45 = 607 ผ่าน · 0 ไม่ผ่าน**

---

## 15. Behavior changed · Compatibility risks

### 15.1 พฤติกรรมที่เปลี่ยนจริง 3 ข้อ

| # | เปลี่ยนอะไร | กระทบใคร | ประเมิน |
|---|---|---|---|
| **C1** | เส้นทาง `/api/admin/*` **ไม่มี token** เดิมตอบ `{"error":"Missing Authorization token"}` ตอนนี้ตอบ `{"error":"Unauthorized"}` · **รหัสยังเป็น 401 เหมือนเดิม** | SPA อ่าน `data.error` ไปแสดง (`Dashboard.jsx:116`) แล้วมี fallback ภาษาไทย | ข้อความที่ผู้ใช้เห็นเปลี่ยนในกรณีขอบนี้เท่านั้น · **ตั้งใจ** เพื่อไม่บอกว่าเดาไปถึงขั้นไหน |
| **C2** | ~~header ผิดรูปแบบบนเส้นทางสาธารณะตอบ 401~~ → **เปลี่ยนกลับแล้ว** เส้นทางสาธารณะยังทำงานในฐานะ anonymous | **ไม่มีใครกระทบ** — พฤติกรรมเดิมถูกรักษาไว้ | **`RESOLVED`** ดูข้อ 15.4 |
| **C3** | `/api/admin/*` ตรวจ token **สองครั้ง** ต่อคำขอ (ด่านใหม่ + `requireAdminUser` ของ handler) | เพิ่ม latency และจำนวนคำขอไป Supabase เป็น ~2 เท่าสำหรับ 3 เส้นทางนี้ | **`ACCEPTED_TEMPORARILY`** ดูข้อ 15.5 |

### 15.2 พฤติกรรมที่ **ไม่** เปลี่ยน

```
ผู้เรียกที่มีสิทธิ์ถูกต้อง        ได้ผลลัพธ์เหมือนเดิมทุกอย่าง
เส้นทางข่าว Sci Connect         ยังเปิดสาธารณะ ยังไม่ต้องล็อกอิน
เกณฑ์ role/status                เหมือนเดิมเป๊ะ
RLS / policy ของ Supabase       ไม่แตะ
client ที่ scope ด้วย token      handler ยังสร้างเองเหมือนเดิม RLS ยังบังคับด้วยตัวตนจริง
FastAPI / backend                ไม่แตะเลย
```

### 15.4 C2 = `RESOLVED` — รักษาพฤติกรรมเดิมของเส้นทางสาธารณะไว้

**ที่แก้**

```
resolveAuthContext()   header พัง / token ใช้ไม่ได้ / ตัวตรวจล้ม
                       -> คืน { ok: true, context: ANONYMOUS_AUTH_FAILED }   แทน 401
authorize()            เป็นจุดเดียวที่ตัดสินว่าระดับนั้นยอมรับ anonymous ไหม
needsAuthContext()     PUBLIC ข้ามการหาตัวตนไปเลย
```

**ทำไมแก้ที่ `resolveAuthContext` ไม่ใช่ที่ `authorize`**

ตอนแกะ header ยังไม่รู้ว่า route ต้องการระดับใด การตัดสินใจปฏิเสธจึงไม่ควรอยู่ที่นั่น
ย้ายมาให้ `authorize()` ซึ่งเป็นจุดเดียวที่รู้ระดับ ทำให้มีจุดตัดสินใจเดียว

**`ANONYMOUS_AUTH_FAILED` ปลอดภัยเพราะอะไร**

| | |
|---|---|
| ทุกฟิลด์ที่ใช้ตัดสินสิทธิ์ | `authenticated: false` · `userId: null` · `role: null` · `status: null` — **เท่ากับ anonymous เป๊ะ** |
| ต่างจาก `ANONYMOUS` แค่ | ธง `authFailed: true` ซึ่ง **ใช้เฉพาะในการเขียน log** |
| มีข้อตรวจยืนยันว่าธงไม่มีผล | วนทุกระดับใน `LEVELS` เทียบผลกับ `ANONYMOUS` ทีละระดับ ต้องเท่ากันทุกข้อ |
| `Object.freeze` | แก้ค่าเพื่อไต่สิทธิ์ไม่ได้ — มีข้อตรวจว่า assignment โยน `TypeError` |

**ผลพลอยได้ที่สำคัญ: `PUBLIC` ไม่เรียก Supabase เลย**

`needsAuthContext(PUBLIC) === false` → เส้นทางข่าว Sci Connect **ไม่ต้องรอผลตรวจ
token จาก Supabase** แม้ผู้เรียกจะส่ง header มา → **Supabase ล่มแล้วเนื้อหาสาธารณะ
ยังเร็วเหมือนเดิม** ไม่ใช่แค่ "ยังใช้ได้"

`PUBLIC_FILTERED` ยังต้องหาตัวตน เพราะต้องรู้ว่าจะกรองข้อมูลให้คนทั่วไปไหม —
ถ้าหาไม่ได้ก็เป็น anonymous ซึ่งได้ข้อมูลที่กรองแล้ว ปลอดภัยโดยค่าตั้งต้น

### 15.5 C3 = `ACCEPTED_TEMPORARILY` — defence in depth ชั่วคราว

```
คำขอหนึ่งครั้งไปที่ /api/admin/*

  1. ด่านนอก (server.mjs + auth.mjs)    auth.getUser + อ่าน user_profiles
  2. ฟังก์ชันของหน้าเว็บ (api/_lib/adminAuth.js)   auth.getUser + อ่าน user_profiles  ซ้ำ
```

| | |
|---|---|
| สาเหตุ | `api/` เป็นของรีโปหน้าเว็บ ซึ่ง Owner decision ข้อ 3 ยังไม่อนุมัติให้แก้ |
| ราคาที่จ่าย | จำนวนคำขอไป Supabase **~2 เท่า** และ latency เพิ่มขึ้นตามนั้น สำหรับ **3 เส้นทาง** |
| ใครรับผล | **ผู้ดูแลระบบเท่านั้น** (`/api/admin/*`) · เส้นทางที่นักเรียนใช้ไม่กระทบเลย |
| ประโยชน์ที่ได้ระหว่างนี้ | ถ้าด่านชั้นใดชั้นหนึ่งมีข้อบกพร่อง อีกชั้นยังกันอยู่ · และ handler ยังสร้าง client ที่ scope ด้วย token ผู้เรียก ทำให้ RLS บังคับซ้ำเป็นชั้นที่สาม |
| เลิกเมื่อไหร่ | เมื่อได้รับอนุมัติแก้รีโปหน้าเว็บ แล้วให้ handler ใช้ context ที่ด่านนอกส่งให้ แทนการตรวจเอง |
| **ห้ามทำในรอบนี้** | **ห้ามลบ `requireAdminUser` ออกจาก handler** — เป็นการแก้รีโปหน้าเว็บ |

### 15.3 ความเสี่ยง

| # | ความเสี่ยง | ระดับ | ทางลด |
|---|---|---|---|
| **R1** | **`createSupabaseVerifier` ยังไม่เคยคุยกับ Supabase จริง** — รูปแบบที่ `auth.getUser` คืนมาถูกลอกจาก `adminAuth.js` แต่ยังไม่ได้ยืนยันด้วยการรัน | **สูง** | ต้องทดสอบในสภาพแวดล้อมที่มี Supabase จริงก่อน deploy · ถ้ารูปแบบไม่ตรง ด่านจะปฏิเสธทุกคนซึ่ง **fail closed** (ผู้ดูแลเข้าไม่ได้ ไม่ใช่คนนอกเข้าได้) |
| **R2** | **ลืมคัดลอก `auth.mjs` เข้า image** | **สูง** | แก้ `Dockerfile` แล้ว (`COPY server.mjs auth.mjs ./`) · ถ้าลืม คอนเทนเนอร์พังตอนเริ่มทำงาน ไม่ใช่ตอนมีคนเรียก → เห็นทันที |
| **R3** | ค่าตั้งค่า Supabase ไม่ครบใน production | กลาง | เส้นทางที่ต้องมีสิทธิ์ตอบ 500 ทุกครั้ง (fail closed) · `/healthz` รายงาน `authConfigured: false` ให้เห็นก่อน |
| **R4** | **ไม่มีแคช + ถาม Supabase ทุกคำขอ** | กลาง | ยอมรับในเฟส 1 เพื่อให้การถอนสิทธิ์มีผลทันที · ปัจจุบันกระทบแค่ 3 เส้นทางที่ผู้ดูแลใช้ ไม่ใช่เส้นทางที่นักเรียนใช้ |
| **R5** | Supabase ล่ม = หน้าผู้ดูแลใช้ไม่ได้ | ต่ำ | เป็นอย่างนี้อยู่แล้วก่อนรอบนี้ (ทั้ง SPA และ handler พึ่ง Supabase) · ด่านใหม่ไม่ได้เพิ่มการพึ่งพาใหม่ · **หลังแก้ C2 เนื้อหาสาธารณะไม่พึ่ง Supabase auth เลย** (`needsAuthContext(PUBLIC) = false`) |
| **R6** | **ครึ่งหนึ่งของงาน B1 ยังอยู่ในรีโปหน้าเว็บ** | **สูง** | Owner decision ข้อ 5 ห้ามแตะจนได้รับอนุมัติแยก · endpoint ใหม่ทั้งหมดต้องเขียนที่นั่น |

---

## 16. Remaining B1 work

```
ก. ได้รับอนุมัติเขียนรีโปหน้าเว็บ (Owner decision ข้อ 5)          <- บล็อกทุกข้อข้างล่าง
ข. ยืนยัน createSupabaseVerifier กับ Supabase จริง (R1)
ค. ออกแบบการจับคู่ผู้ใช้ที่ยังใช้งานอยู่ (B1_ACTIVE_USER_MAPPING_REQUIRED)
                                                             <- บล็อกทุก endpoint ที่เขียนข้อมูล
ง. สร้าง endpoint ทีละตาราง — ลำดับที่เสนอ
     knowledge_articles (0 แถว ไม่มีอะไรจะเสีย)
     news               (3 แถว · กับดัก status)
     courses            (12 แถว · logo อยู่ใน storage)
     ai_settings        (1 แถว)
     external_news      (ท้ายสุด มีผู้เขียนอัตโนมัติ)
จ. แก้ SPA 15 ไฟล์ให้เลิกเรียก Supabase ตรง
ฉ. ปิด G3 สองข้อที่ค้าง เมื่อมี write endpoint จริง
ช. ตัดสิน ai_settings PUBLIC -> EDITOR (Owner decision ยังบอกว่าคงพฤติกรรมเดิมไว้ก่อน)
ซ. ตัดสินเรื่อง DELETE — 005 ไม่ให้ DELETE แก่ใคร และยังไม่เพิ่มสิทธิ์รอบนี้
   -> endpoint DELETE ยังสร้างไม่ได้
ฌ. เลิก C3 (ตรวจซ้ำ) เมื่อได้รับอนุมัติแก้รีโปหน้าเว็บ
```

### 16.1 สิ่งที่ foundation รอบนี้ทำให้ง่ายขึ้นแล้ว

```
เพิ่มเส้นทางใหม่ = เพิ่มหนึ่งแถวในตาราง ROUTES พร้อมระดับสิทธิ์
ลืมประกาศระดับ = บริการไม่ขึ้น ไม่ใช่เปิดโล่งเงียบ ๆ
ไม่ต้องจำว่าต้องเรียก requireAdminUser ในทุก handler ใหม่
```

---

## 17. Diff summary

```
webapi/auth.mjs          +429  ใหม่   ด่านตรวจตัวตนและสิทธิ์กลาง
webapi/auth.test.mjs     +560  ใหม่   42 test
webapi/server.test.mjs   +285  ใหม่   10 test
webapi/server.mjs        +122 −13     ตาราง ROUTES มีระดับ · บังคับก่อน dispatch · healthz
webapi/Dockerfile          +7  −2     COPY auth.mjs · ไม่เอา *.test.mjs เข้า image
webapi/package.json        +3         script test
--------------------------------------------------------------------
รวม                     +1406 −15     6 ไฟล์ · ทั้งหมดใน webapi/ ของรีโปนี้
```

### 17.2 สิ่งที่รอบแก้ C2 เปลี่ยน — `+191` จากรอบแรก

```
auth.mjs         + ANONYMOUS_AUTH_FAILED · needsAuthContext()
                   resolveAuthContext: ลดระดับแทนปฏิเสธ 3 จุด
                   describeForLog: แยก "anonymous" จาก "anonymous (auth failed)"
server.mjs       + ข้าม resolveAuthContext เมื่อระดับเป็น PUBLIC
auth.test.mjs    + 6 ข้อตรวจของ C2 · ลบ 1 ข้อที่ขัด · ปรับ 1 ข้อ
server.test.mjs  + 1 ข้อตรวจระดับ HTTP ของ C2
```

**ไม่มีการแก้นอก `webapi/`** — ไม่แตะ 005 · ไม่แตะ `backend/` · ไม่แตะรีโปหน้าเว็บ
· ไม่สร้าง write endpoint

### 17.1 ที่ไม่ถูกแตะ — ยืนยันด้วยคำสั่ง

```
git diff --name-only -- db/ backend/ eval/ pipeline/    ->  0 ไฟล์
git diff -- db/migrations/005_web_schema.sql            ->  ว่างเปล่า
รีโปหน้าเว็บ                                             ->  ไฟล์ที่มี diff อยู่ที่นั่น
                                                            ลงวันที่ 09-22 · 09-23 · วันนี้ 09:53
                                                            ทั้งหมดมาก่อนงานรอบนี้ (เริ่ม ~19:00)
CRLF ทุกไฟล์ที่แก้/เพิ่ม                                   ->  0
ไม่เพิ่ม dependency                                      ->  ใช้ node:test ที่มาพร้อม Node
```

---

## 18. Final classification

# `READY_FOR_REVIEW`

| | |
|---|---|
| ไฟล์ | 6 · `+1406 −15` · ทั้งหมดใน `webapi/` |
| Migration 005 | **ไม่ถูกแตะ** |
| รีโปหน้าเว็บ | **ไม่ถูกแตะ** |
| backend / FastAPI | **ไม่ถูกแตะ** |
| ทดสอบ | **614 ผ่าน · 0 ไม่ผ่าน** (webapi 52 + regression 562) · ค้าง 2 · ข้าม 1 |
| **C2** | **`RESOLVED` — existing public behavior preserved** |
| **C3** | **`ACCEPTED_TEMPORARILY`** |
| B1_ACTIVE_USER_MAPPING_REQUIRED | **`true`** |
| G3 | **`G3_API_ENFORCEMENT_PENDING_B1`** |
| commit / push | **ยังไม่ทำ** |

**ไม่ใช่ `READY_FOR_PRODUCTION`** — ยังไม่ได้ยืนยันกับ Supabase จริง (R1) และยังไม่มี
endpoint ที่ย้ายข้อมูล

---

## STOP

**รอ review ก่อน commit**

เรื่องที่รออนุมัติ

1. **อนุมัติ commit 6 ไฟล์ใน `webapi/`** หรือไม่
2. **R1** — ยืนยัน `createSupabaseVerifier` กับ Supabase จริงเมื่อใด
   (ยังเป็นความเสี่ยงระดับสูงที่เหลืออยู่ข้อเดียวในโค้ด)
3. **อนุมัติเขียนรีโปหน้าเว็บ** — บล็อกงาน B1 ที่เหลือทั้งหมด รวมถึงการเลิก C3
4. **การจับคู่ผู้ใช้ที่ยังใช้งานอยู่** — บล็อกทุก endpoint ที่เขียนข้อมูล

ปิดแล้วในรอบนี้: **C2 `RESOLVED`** · **C3 `ACCEPTED_TEMPORARILY`**

```
Commit / Push         NONE    Apply Migration 005    NONE    Data Migration    NONE
Supabase Write        NONE    แก้ RLS / policy        NONE    Deploy / Restart  NONE
Production Write      NONE    Re-embed               NONE    Merge main        NONE
แก้รีโปหน้าเว็บ        NONE    แก้ Migration 005       NONE
```
