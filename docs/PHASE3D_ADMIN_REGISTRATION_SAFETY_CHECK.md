# Phase 3D — Admin Registration Safety Check (Option B)

**PHASE 1 (READ-ONLY) เสร็จ · PHASE 2 = รอเจ้าของโปรเจกต์สมัครบัญชีเอง · PHASE 3 ยังไม่เริ่ม**

| | |
|---|---|
| วันที่ตรวจ | 2026-09-29 · **04:46–04:50Z** (ไทย 11:46–11:50) |
| Decision ที่ยึด | **Architecture Option B** — Supabase Auth ยังเป็นระบบของ SPA/webapi ต่อไป · FastAPI + PostgreSQL เป็นระบบของ Next.js และ `/crawl-review` · ไม่รวม auth, ไม่ทำ SSO, ไม่ทำ identity mapping, ไม่แตะ Supabase, ไม่ย้ายข้อมูลข้ามฐาน |
| Revision ที่ตรวจ | `2fdc6f241fc1742047b572ee2ef354cd811f9401` (= อิมเมจที่ให้บริการอยู่ ยืนยันด้วย OCI label) |
| **Production mutations** | **0 (ศูนย์)** — ทุกการดำเนินการเป็นการอ่าน |
| **GO / NO-GO** | **GO สำหรับให้เจ้าของโปรเจกต์สมัครบัญชีเองผ่าน HTTPS** · **NO-GO สำหรับการ promote** (ยังไม่มีบัญชี) |

เอกสารที่อ่านก่อนเริ่ม: `docs/AUTH_ARCHITECTURE_AUDIT.md` ·
`docs/AUTOMATED_INGESTION_PHASE3D_STEP3_5_ADMIN_VERIFICATION_REPORT.md` ·
`docs/AUTOMATED_INGESTION_PHASE3D_STEP3_RESUME_REPORT.md`

---

## 1. เส้นทาง Register ผ่าน HTTPS ใช้งานได้หรือไม่

### **ได้ — พิสูจน์แล้วโดยไม่ส่ง POST แม้ครั้งเดียว**

```
GET https://stpnru-advisor.duckdns.org/api/auth/register

HTTP/2 405
allow: POST
content-type: application/json
server: uvicorn
{"detail":"Method Not Allowed"}
```

ทำไม 405 นี้เป็นข้อพิสูจน์ที่ใช้ได้

| หลักฐาน | ความหมาย |
|---|---|
| `405` ไม่ใช่ `404` | เส้นทาง `/auth/register` **มีอยู่จริง** บน FastAPI |
| `allow: POST` | รับเฉพาะ POST ตรงกับ `@router.post("/register")` |
| `server: uvicorn` | คำตอบมาจาก **FastAPI** ไม่ใช่ Caddy และไม่ใช่ SPA ที่ `/srv/web` |
| `GET /api/auth/<path ที่ไม่มีจริง>` → **404** | 405 ไม่ใช่คำตอบเหมารวม การจับคู่เส้นทางทำงานถูกต้อง |
| `GET /api/auth/login` → **405 + allow: POST** | เส้นทาง login ก็พร้อมใช้เช่นกัน |

**การตรวจใช้เพียง GET** ซึ่งบน route ที่รับแต่ POST ไม่มีทางสร้างข้อมูลใดได้

### TLS ของโดเมน — ตรวจปกติ ไม่ปิดการตรวจ

```
ssl_verify_result = 0  (ผ่าน)     scheme = HTTPS     HTTP/2
subject : CN = stpnru-advisor.duckdns.org
issuer  : C = US, O = Let's Encrypt, CN = YE1
valid   : 2026-09-04T17:00:27Z  ->  2026-12-03T17:00:26Z
```

ใบรับรองถูกต้องและยังไม่หมดอายุ → รหัสผ่านที่ส่งผ่านเส้นทางนี้ถูกเข้ารหัส

---

## 2. Routing ที่พิสูจน์จาก config และ source จริง

### 2.1 `Caddyfile` ที่ใช้อยู่ (ไม่แก้ ไม่ reload ไม่ restart)

`sha256 = da2e26fd948d2a7143c85d1ee7dde204c774569d6f2e49130ea9bd059aec0f0d`
`mtime = 2026-09-22 21:23:34` — **ค่าเดียวกับที่บันทึกไว้ใน Step 3 และ Step 3.5**

```caddy
{$SITE_DOMAIN} {
    handle /api/chat              { rewrite * /chat-web ; reverse_proxy backend:8000 }
    handle /api/sci-connect-news* { reverse_proxy webapi:3001 }
    handle /api/admin/*           { reverse_proxy webapi:3001 }
    handle /api/*                 { uri strip_prefix /api ; reverse_proxy backend:8000 }   ← ตัวนี้จับ /api/auth/register
    handle /assets/*              { root * /srv/web ; file_server }
    handle                        { root * /srv/web ; try_files {path} /index.html ; file_server }
}

:80 { reverse_proxy frontend:3000 }
```

ลำดับการจับคู่ของ Caddy: `/api/chat` → `/api/sci-connect-news*` → `/api/admin/*` → **`/api/*`**

`/api/auth/register` **ไม่ตรงกับสามตัวแรก** จึงตกที่ `handle /api/*` ซึ่งทำ
`uri strip_prefix /api` แล้วส่งไป `backend:8000` → FastAPI เห็นเป็น `/auth/register`

→ **ไม่ตกเข้า `webapi` (Supabase) และไม่ตกเข้า `file_server` ของ SPA**

### 2.2 เส้นทางที่สองที่พิสูจน์แล้วด้วย — ผ่าน Next.js proxy

`BACKEND_ORIGIN = http://backend:8000` (ค่าในคอนเทนเนอร์ frontend ที่รันอยู่)
และ [frontend/app/api/[...path]/route.ts](frontend/app/api/%5B...path%5D/route.ts) ส่งต่อ
`/api/*` ไป backend โดยยกเฉพาะ header `authorization`, `content-type`, `accept`

ทดสอบด้วย GET ผ่าน `:80` ได้ผลเดียวกัน

```
[:80 -> Next -> backend] /api/health                  -> 200  {"status":"ok"}
[:80 -> Next -> backend] /api/auth/register           -> 405  {"detail":"Method Not Allowed"}
[:80 -> Next -> backend] /api/auth/<ไม่มีจริง>          -> 404  {"detail":"Not Found"}
```

### 2.3 สัญญาของ endpoint (จาก source ที่ deploy)

[backend/app/api/routes/auth.py:32-45](backend/app/api/routes/auth.py:32) ·
[backend/app/schemas/user.py:7-10](backend/app/schemas/user.py:7)

```
POST /auth/register        (บนโดเมนคือ POST /api/auth/register)
body  { "email": <อีเมลที่ถูกรูปแบบ>, "password": <8-128 ตัวอักษร>, "full_name": <ไม่บังคับ> }
201   { "id", "email", "full_name", "created_at" }
409   { "detail": "email already registered" }   ← ถ้าอีเมลนี้มีอยู่แล้ว
422   ถ้ารูปแบบอีเมลผิดหรือรหัสผ่านสั้นกว่า 8 ตัวอักษร
```

ข้อเท็จจริงสำคัญที่ตรวจจาก source

- **`is_admin` กำหนดจากคำขอไม่ได้** — โค้ดสร้าง `User(email=..., password_hash=..., full_name=...)`
  เท่านั้น `is_admin` จึงได้ค่า default ของคอลัมน์ = `false` เสมอ
  → **สมัครเองแล้วเป็น admin ไม่ได้ ต้องมีขั้น promote แยกที่ต้องได้รับอนุมัติ**
- `/auth/register` **ไม่มี dependency ใด** ทั้ง auth และ rate limiter (สภาพเดิมของระบบ
  ไม่ใช่สิ่งที่รอบนี้เสนอให้แก้)
- รหัสผ่านถูก hash ด้วย bcrypt cost 12 โดย pre-hash SHA-256 + base64 ก่อน
  ([security.py:28-43](backend/app/core/security.py:28)) → รหัสผ่านภาษาไทยหรือยาวเกิน
  72 ไบต์ใช้ได้จริงไม่ถูกตัด
- คอลัมน์ `public.users.email` เป็น **`citext`** (ยืนยันจากฐานข้อมูลในรอบนี้)
  → `Tester@gmail.com` และ `tester@gmail.com` ถือเป็นบัญชีเดียวกัน และ
  `UNIQUE INDEX users_email_key` กันการสมัครซ้ำต่างตัวพิมพ์ให้แล้ว

---

## 3. มีวิธีให้เจ้าของ register โดยไม่ต้องส่งรหัสผ่านผ่าน HTTP `:80` หรือไม่

### **มี สองวิธีที่เข้ารหัสทั้งเส้นทาง**

ก่อนอื่นต้องรู้ข้อจำกัดนี้: **หน้าสมัครของ Next.js ถูกเสิร์ฟที่บล็อก `:80` เท่านั้น
ซึ่งเป็น HTTP ไม่เข้ารหัส** ส่วนโดเมน HTTPS เสิร์ฟ SPA ของทีมออกแบบจาก `/srv/web`
(ยืนยัน: หน้าโดเมนมี 762 ไบต์ ไม่มีคำว่า `course_advisor_token` เลย ขณะที่หน้า `:80`
มี 14,530 ไบต์และอ้าง `_next`) — SPA นั้นสมัครผ่าน **Supabase** ซึ่งเป็นคนละ identity store
จึงใช้แทนกันไม่ได้

จึงเหลือสองทางที่ปลอดภัย

---

### วิธี 1 (แนะนำ) — SSH tunnel แล้วใช้หน้าสมัครจริงของ Next.js

ข้อดี: มีช่องกรอกรหัสผ่านจริง (`type="password"`) · แอปประกอบ JSON ให้เอง
จึงไม่มีปัญหาอักขระพิเศษในรหัสผ่าน · รหัสผ่านไม่เข้าประวัติคำสั่งหรือ console ใด ·
ทั้งเส้นทางถูกเข้ารหัสด้วย SSH · และเมื่อสมัครเสร็จแอปจะ **login ให้ทันที**
([frontend/app/page.tsx:68](frontend/app/page.tsx:68) เรียก `api.register` ต่อด้วย
`api.login` และ `api.me` ในฟอร์มเดียว)

**ขั้นตอนที่เจ้าของทำเอง**

1. เปิด terminal บนเครื่องของตัวเอง แล้วเปิด tunnel (ผูกกับ loopback ของเครื่องตัวเองเท่านั้น)

```bash
ssh -i ~/.ssh/oci.key -N -L 127.0.0.1:8080:127.0.0.1:80 ubuntu@161.118.237.37
```

2. เปิดเบราว์เซอร์ไปที่

```
http://127.0.0.1:8080/
```

3. กดปุ่ม **"ยังไม่มีบัญชี? สมัครสมาชิก"**
4. กรอก **ชื่อ** (ไม่บังคับ) · **อีเมล** = `Tester@gmail.com` · **รหัสผ่าน** ที่เจ้าของตั้งเอง
   อย่างน้อย 8 ตัวอักษร (ฟอร์มบังคับ `minLength={8}` อยู่แล้ว)
5. กด **สมัครสมาชิก** — ถ้าสำเร็จหน้าเว็บจะพาเข้าสู่ระบบและไปหน้าแบบสอบถามต่อ
6. ปิด tunnel (กด `Ctrl+C` ใน terminal ข้อ 1)
7. แจ้งผมว่า **"register สำเร็จแล้ว"** พร้อมยืนยันอีเมลที่ใช้ — **ไม่ต้องส่งรหัสผ่านมา**

> รหัสผ่านวิ่งผ่าน `127.0.0.1:8080` บนเครื่องเจ้าของ → อุโมงค์ SSH ที่เข้ารหัส →
> `127.0.0.1:80` บนเซิร์ฟเวอร์ → เครือข่ายภายในของ Docker เท่านั้น
> **ไม่มีช่วงใดวิ่งผ่านอินเทอร์เน็ตแบบไม่เข้ารหัส**

---

### วิธี 2 (ไม่ต้องใช้ SSH) — เรียก API ผ่าน HTTPS จาก console ของเบราว์เซอร์

ข้อดี: ไม่ต้องมีคีย์ SSH · `JSON.stringify` จัดการอักขระพิเศษให้ถูกต้อง ·
`prompt()` ทำให้รหัสผ่านไม่เข้าประวัติของ console

**ขั้นตอนที่เจ้าของทำเอง**

1. เปิดเบราว์เซอร์ไปที่ `https://stpnru-advisor.duckdns.org/`
   (ต้องเป็นหน้านี้ เพื่อให้คำขอเป็น same-origin — ดูหมายเหตุ CORS ข้างล่าง)
2. เปิด DevTools → แท็บ Console
3. วางสคริปต์นี้แล้วกด Enter จากนั้นพิมพ์รหัสผ่านในกล่องที่เด้งขึ้น

```js
await (async () => {
  const email = "Tester@gmail.com";
  const full_name = "Owner";
  const password = prompt("ตั้งรหัสผ่าน (อย่างน้อย 8 ตัวอักษร)");
  if (!password || password.length < 8) return console.log("ยกเลิก: รหัสผ่านสั้นเกินไป");
  const r = await fetch("/api/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, full_name }),
  });
  console.log("HTTP", r.status, r.status === 201 ? "สมัครสำเร็จ" : await r.text());
})();
```

4. ถ้าได้ `HTTP 201 สมัครสำเร็จ` ให้ปิด DevTools แล้วแจ้งผม
   - `HTTP 409` = อีเมลนี้มีอยู่แล้วในระบบเรา (แจ้งผมได้เลย ไปขั้น promote ต่อ)
   - `HTTP 422` = รูปแบบอีเมลผิดหรือรหัสผ่านสั้นกว่า 8 ตัวอักษร

> **หมายเหตุ CORS:** `CORS_ALLOW_ORIGINS` ของ backend ตั้งเป็น `["http://localhost:3000"]`
> แต่เรียกจากหน้าโดเมนเดียวกันเป็น **same-origin** จึงไม่เข้าเงื่อนไข CORS เลย
> ถ้าเรียกจาก origin อื่นจะถูกเบราว์เซอร์บล็อก

---

### วิธี 3 (สำหรับคนถนัด terminal) — `curl` ผ่าน HTTPS

```bash
read -rsp 'ตั้งรหัสผ่าน (อย่างน้อย 8 ตัวอักษร): ' PW; echo
printf '{"email":"Tester@gmail.com","password":"%s","full_name":"Owner"}' "$PW" \
  | curl -sS -X POST https://stpnru-advisor.duckdns.org/api/auth/register \
      -H 'Content-Type: application/json' --data-binary @- \
      -w '\nHTTP %{http_code}\n'
unset PW
```

`read -rs` ไม่แสดงรหัสผ่านและไม่เก็บลงประวัติ · `printf` เป็น builtin ของ shell
รหัสผ่านจึงไม่ปรากฏใน `ps`

> **ข้อควรระวังของวิธีนี้:** ถ้ารหัสผ่านมีอักขระ `"` หรือ `\` JSON จะเสียรูป
> ให้เลี่ยงสองตัวนี้ หรือใช้วิธี 1 / วิธี 2 ที่ประกอบ JSON ให้ถูกต้องอัตโนมัติ

---

### ห้ามทำ

**อย่าเปิด `http://161.118.237.37/` ตรง ๆ แล้วกรอกรหัสผ่าน** — เส้นทางนั้นเป็น HTTP
ไม่เข้ารหัส รหัสผ่านจะวิ่งผ่านอินเทอร์เน็ตเป็นข้อความธรรมดา
ถ้าต้องการใช้หน้าเว็บนั้นให้ใช้วิธี 1 (ผ่าน SSH tunnel) เท่านั้น

---

## 4. สิ่งที่ผมไม่ได้ทำในรอบนี้

- **ไม่ได้ส่ง `POST /auth/register`** แม้ครั้งเดียว — ตรวจด้วย `GET` เท่านั้น
- **ไม่ได้ทดลองสมัครด้วยข้อมูลปลอม** และไม่ได้สร้างผู้ใช้ใด
- **ไม่ได้ promote admin** และไม่ได้แก้ `is_admin` ของใคร
- **ไม่ได้ขอรหัสผ่านจากเจ้าของ · ไม่ได้ตั้งรหัสผ่านแทน · ไม่ได้ print/log/เก็บรหัสผ่านใด**
- **ไม่ได้อ่านคอลัมน์ `password_hash`**
- **ไม่ได้แก้ฐานข้อมูล** — query ทั้งหมดอยู่ใน `BEGIN TRANSACTION READ ONLY`
  พร้อม `statement_timeout`
- ไม่ได้แก้ Supabase · ไม่ได้รวม Supabase กับ PostgreSQL · ไม่ได้ทำ SSO ·
  ไม่ได้เพิ่มการรองรับ Supabase JWT · ไม่ได้ทำ identity mapping · ไม่ได้แก้สถาปัตยกรรม JWT
- ไม่ได้แก้ Caddy (hash เดิม `da2e26fd…` mtime เดิม) · ไม่ได้ deploy · ไม่ได้ restart ·
  ไม่ได้ทำ migration · ไม่ได้ commit/push · ไม่ได้รัน ingestion/worker/crawler ·
  ไม่ได้สร้าง candidate ปลอม · ไม่ได้แตะ RAG/pgvector ·
  ไม่ได้แก้ production เพื่อทำให้การตรวจผ่าน
- ไม่ได้เปิด tunnel หรือ listener ใด และไม่ได้เปิดพอร์ตเพิ่ม
- ไม่ได้แสดงค่าลับใด (ตรวจ `.env` เฉพาะชื่อคีย์ · ปิดค่า Supabase URL ไว้)

---

## 5. สภาพฐานข้อมูลปัจจุบัน (ก่อนเจ้าของสมัคร)

อ่านใน read-only transaction เวลา 04:47Z และยืนยันซ้ำเวลา 04:50Z ได้ค่าเดียวกัน

| รายการ | ค่า |
|---|---:|
| `public.users` ทั้งหมด | **197** |
| `is_active = true` | **197** |
| **`is_admin = true`** | **0** |
| ชนิดคอลัมน์ `email` | `citext` |
| `mko.crawl_decisions` | 0 |
| `public.courses` | 24 |
| `public.course_documents` | 31 |
| `public.course_chunks` | 9039 |
| `mko.crawl_sources` | 12 |
| `public.chat_messages` | 6640 |

---

## 6. `Tester@gmail.com` ใน PostgreSQL

### **ยังไม่มี — 0 บัญชี**

| วิธีตรวจ | ผล |
|---|---:|
| `email = 'Tester@gmail.com'` (semantics จริงของแอป, citext) | **0** |
| `lower(email::text) = lower('Tester@gmail.com')` | **0** |
| `email::text ILIKE 'tester@%'` (local part `tester` ทุกโดเมน) | **0** |

บัญชี `Tester@gmail.com` ที่มีอยู่ **ใน Supabase** เป็น identity store คนละตัว
**ไม่ได้แก้ ไม่ได้ลบ และไม่ได้ migrate บัญชีนั้น** ตามข้อกำหนดของ Option B

---

## 7. Production mutations

### **0 (ศูนย์)**

ยืนยันหลังตรวจเสร็จ

```
users = 197  active = 197  admins = 0        (เท่ากับก่อนเริ่ม)
Tester@gmail.com = 0                          (เท่ากับก่อนเริ่ม)

backend   container=fda31caa20c4  restarts=0  started=2026-09-29T01:06:17.872Z
frontend  container=2886c1bf9183  restarts=0  started=2026-09-29T01:07:21.190Z
caddy     container=a2957d7b8fc3  restarts=0  started=2026-09-22T21:23:48.949Z
postgres  container=e8c091a4fc60  restarts=0  started=2026-08-18T14:17:25.705Z
ollama    container=e6ac0350c722  restarts=0  started=2026-08-18T14:17:25.705Z
webapi    container=6a73308d4f39  restarts=0  started=2026-09-22T21:21:35.624Z
```

container ID และ StartedAt ของทั้งหกบริการไม่เปลี่ยน → ไม่มี restart และไม่มี recreate

---

## 8. GO / NO-GO

| เรื่อง | คำตัดสิน | เหตุผล |
|---|---|---|
| **ให้เจ้าของสมัครบัญชีเองผ่าน HTTPS** | **GO** | เส้นทาง `POST /api/auth/register` ถึง FastAPI จริง (405 + `allow: POST` + `server: uvicorn`) · TLS ถูกต้อง (`verify_result=0`) · `is_admin` กำหนดจากคำขอไม่ได้ · มีสองวิธีที่เข้ารหัสทั้งเส้นทาง |
| **promote บัญชีเป็น admin** | **NO-GO ตอนนี้** | ยังไม่มีบัญชี `Tester@gmail.com` ใน `public.users` (0 แถว) — ต้องรอเจ้าของสมัครและยืนยันก่อน |
| **authenticated verification ของ Step 3.5** | **NO-GO ตอนนี้** | ต้องมี admin ก่อน |
| **แก้ Caddy / deploy / migration เพื่อเปิดหน้าสมัครบน HTTPS** | **ไม่จำเป็นและไม่ทำ** | เรียก API ผ่าน HTTPS ได้อยู่แล้ว ไม่ต้องแตะ routing ใด |

---

## 9. หลังเจ้าของสมัครสำเร็จ — ขั้นตอนถัดไป (PHASE 3 · ยังไม่รันในรอบนี้)

เริ่มได้เมื่อเจ้าของแจ้งว่า **"register สำเร็จแล้ว"** และยืนยันอีเมลที่ใช้

### 9.1 ตรวจก่อน promote

1. ตรวจ `public.users` ด้วย semantics จริง (`email = 'Tester@gmail.com'` บนคอลัมน์ `citext`)
   ต้องพบ **1 บัญชีพอดี** — นับก่อนกรอง active เพื่อจับความกำกวม
2. ต้อง `is_active = true`
3. ต้อง `is_admin = false`
4. ตรวจ baseline/invariants เดิม: `crawl_decisions = 0` · `courses = 24` ·
   `course_documents = 31` · `course_chunks = 9039` · `crawl_sources = 12` ·
   embedding dimension `1024` · `staging/crawl` ว่าง · mount ทั้งสอง `RW=false`
5. **ต้องอ่านจำนวนผู้ใช้จริงใหม่ ห้าม hard-code 197** — หลังเจ้าของสมัคร 1 บัญชี
   ค่าที่คาดคือ `users = 198`, `active = 198`, `admins = 0` แต่ต้อง**วัดจริง**
   แล้วนำค่าที่วัดได้ไปใส่ใน assertion ของ transaction
   (ถ้ามีผู้ใช้อื่นสมัครเข้ามาระหว่างนั้น ตัวเลขจะต่างไปอีก)

### 9.2 promote ด้วย guarded transaction

ใช้โครงจาก `AUTOMATED_INGESTION_PHASE3D_STEP3_5_ADMIN_VERIFICATION_REPORT.md §17.1`
โดย **ปรับตัวเลข aggregate ให้เป็นค่าที่วัดได้จริงในข้อ 9.1** ไม่ใช่ 197/197/0 ที่ hard-code ไว้

ด่านที่ต้องมีครบ

- `SET LOCAL lock_timeout` / `statement_timeout` และ `LOCK TABLE public.users IN SHARE ROW EXCLUSIVE MODE`
- ตรวจ cardinality = 1, `is_active`, `is_admin = false` **ภายใน** transaction
- ตรวจ aggregate ผู้ใช้ก่อน (ค่าที่วัดจริง เช่น `198/198/0`)
- `SELECT ... FOR UPDATE` ตรึงแถวเป้าหมาย
- `UPDATE public.users SET is_admin = TRUE WHERE email = '...' AND is_active AND is_admin = FALSE`
  — **เปลี่ยนคอลัมน์เดียว ไม่ใส่ `LIMIT 1` ไม่ใช้ substring ของอีเมล**
- ยืนยัน affected rows = **1 พอดี** · ถ้า 0 หรือ >1 ให้ `ROLLBACK` และหยุด
- ก่อน `COMMIT` ตรวจ aggregate หลัง (เช่น `198/198/1`), `crawl_decisions = 0`,
  และ invariants หลักสูตร/crawler ไม่เปลี่ยน
- หลัง `COMMIT` ตรวจสภาพใน read-only transaction แยกอีกครั้ง

หมายเหตุ: trigger `trg_users_updated_at` จะเปลี่ยน `updated_at` ของแถวนั้นด้วย
ซึ่งเป็นพฤติกรรมที่ตั้งใจของ schema (ฟังก์ชัน `set_updated_at()` แตะเฉพาะ `updated_at`)

### 9.3 ไม่ต้อง restart

[backend/app/api/deps.py:44](backend/app/api/deps.py:44) ทำ `db.get(User, uuid.UUID(payload["sub"]))`
ทุกคำขอ และ token บรรจุเพียง `sub` กับ `type` ไม่มี role claim
→ สิทธิ์มีผลทันที **ไม่ต้อง restart และไม่ต้อง login ใหม่**
(ก่อน promote ต้องยืนยันว่า implementation ยังเหมือนที่ audit ตรวจไว้)

### 9.4 authenticated verification ที่ทำได้หลังจากนั้น

ทั้งหมดต้องผ่านช่องทางที่เข้ารหัส (HTTPS สำหรับ API · SSH tunnel สำหรับหน้าเว็บ)

- login ปกติ (เจ้าของใช้รหัสผ่านของตัวเอง — ไม่ส่งมาให้ผม)
- `GET /api/crawl-review/pending` — คาดว่าคืน 6 รายการตาม `mko.v_crawl_queue`
- `GET /api/crawl-review/{id}` — อ่านรายละเอียดอย่างเดียว
- `GET /api/crawl-review/{id}/pdf` — คาดว่า **404 แบบปิดประตู** เพราะ staging ว่าง
  และ `staging_path` เป็น null ทั้ง 12 แถว → พิสูจน์การปฏิเสธอย่างปลอดภัย
  **ไม่ใช่การพิสูจน์ว่าแสดง PDF ของ candidate ได้**
- หน้า `/crawl-review` ที่ render จริงพร้อม action control ตามสภาพของรายการ
- ตรวจ anonymous ยังได้ 401 และ `mko.crawl_decisions` ยังเป็น 0

### 9.5 ห้ามเด็ดขาดในรอบนั้น

**ห้าม POST approve / ignore / undo** (แม้เพื่อทดสอบว่าถูกปฏิเสธ) ·
ห้าม ingestion · ห้ามรัน worker/crawler · ห้ามสร้าง candidate ปลอม ·
ห้ามแก้ `crawl_sources` · `mko.crawl_decisions` **ต้องยังเป็น 0**

---

## PHASE 2 — รอเจ้าของโปรเจกต์

`Tester@gmail.com` **ยังไม่มีใน PostgreSQL `public.users`**

ตามข้อกำหนด: **STOP** — เจ้าของโปรเจกต์ต้องสร้างบัญชีเองผ่านช่องทาง HTTPS
ที่ตรวจแล้วในข้อ 3 เท่านั้น (**วิธี 1** ผ่าน SSH tunnel หรือ **วิธี 2** ผ่าน console
บนโดเมน HTTPS — เลือกอย่างใดอย่างหนึ่ง)

**ผมไม่ promote และไม่สร้างบัญชีให้** · เริ่ม Phase 3 ได้ในรอบใหม่
เฉพาะเมื่อเจ้าของแจ้งว่า register สำเร็จแล้วเท่านั้น

---

## STOP

ห้ามสร้างบัญชี · ห้าม promote admin · ห้ามเริ่ม Step 4

STOP
