# Auth Architecture Audit — READ-ONLY

| | |
|---|---|
| วันที่ | 2026-09-29 (ไทย) · ตรวจจาก source และ config จริง ไม่สรุปจากรายงานเพียงอย่างเดียว |
| ขอบเขต | **READ-ONLY** — ไม่แก้ Supabase, ไม่แก้ PostgreSQL, ไม่สร้าง/แก้/ลบผู้ใช้, ไม่ promote admin, ไม่เปลี่ยนรหัสผ่าน, ไม่แก้ auth, ไม่แก้ Caddy, ไม่ deploy, ไม่ restart, ไม่ commit/push, ไม่รัน ingestion/worker/crawler, ไม่เปลี่ยน production config |
| Revision ที่อ่าน | `2fdc6f241fc1742047b572ee2ef354cd811f9401` (= อิมเมจที่ให้บริการอยู่จริง ยืนยันด้วย OCI label) |
| รายงานที่อ่านประกอบ | `AUTOMATED_INGESTION_PHASE3D_STEP3_RESUME_REPORT.md` (sha256 `2039ba5f…3348`) · `AUTOMATED_INGESTION_PHASE3D_STEP3_5_ADMIN_VERIFICATION_REPORT.md` |
| ข้อสรุปหลัก | **มีระบบผู้ใช้/สิทธิ์สองระบบแยกกันสมบูรณ์จริง** ไม่มีจุดเชื่อมใดเลยระหว่างกัน |

---

## สรุปผังระบบที่พบ

```
                        ┌──────────────── Caddy (พอร์ต 80 / 443) ────────────────┐
                        │                                                        │
  โดเมน HTTPS           │  /api/chat            → rewrite /chat-web → backend    │
  stpnru-advisor…       │  /api/sci-connect-news*→ webapi:3001                   │
                        │  /api/admin/*         → webapi:3001                    │
                        │  /api/*               → strip /api → backend:8000      │
                        │  ที่เหลือ              → file_server /srv/web (SPA)     │
                        │                                                        │
  http://<IP>:80        │  ทุกเส้นทาง            → frontend:3000 (Next.js)        │
                        └────────────────────────────────────────────────────────┘

ระบบ A — Supabase (ของทีมออกแบบ)              ระบบ B — FastAPI + PostgreSQL (ของเรา)
─────────────────────────────────              ──────────────────────────────────────
SPA ใน /srv/web                                Next.js ใน frontend/
  @supabase/supabase-js ในเบราว์เซอร์            POST /auth/login (bcrypt + HS256)
  signInWithPassword / signUp                    token → localStorage
  getSession / onAuthStateChange                   "course_advisor_token"
  resetPasswordForEmail                          Authorization: Bearer <FastAPI JWT>
       │                                              │
       │ Authorization: Bearer <Supabase JWT>         │
       ▼                                              ▼
webapi:3001 · api/_lib/adminAuth.js            backend:8000 · app/api/deps.py
  supabase.auth.getUser(token)                   decode_token() ด้วย JWT_SECRET ของเรา
  → Supabase user_profiles.role ∈ {admin,editor}  → public.users.is_admin
    และ status = 'approved'                       → require_admin()
       │                                              │
       ▼                                              ▼
Supabase: auth.users, user_profiles,           PostgreSQL: public.users,
  courses, news, knowledge_articles,             public.user_profiles (คนละความหมาย),
  rag_documents, ai_settings                     course_chunks (pgvector), mko.*
       │                                              │
คุม /api/admin/* (ข่าว + ingest ของทีมออกแบบ)    คุม /crawl-review/* (Phase 3A)
```

**ไม่มีเส้นใดลากข้ามระหว่างสองคอลัมน์** — นี่คือสาเหตุตรง ๆ ที่ `Tester@gmail.com`
ซึ่งอยู่ใน Supabase หาไม่เจอใน `public.users`

---

## 1. Frontend ปัจจุบัน Login / Register ผ่านระบบอะไร

**มีหน้าเว็บสองชุดที่คนละระบบกันโดยสมบูรณ์**

### 1.1 Next.js (`frontend/`) — เข้าทาง `http://<IP>:80` · เป็นที่อยู่ของ `/crawl-review`

ใช้ **auth ของ FastAPI เท่านั้น** ไม่มี Supabase แม้แต่บรรทัดเดียว

| หลักฐาน | ที่มา |
|---|---|
| `register` เรียก `POST /auth/register` | [frontend/lib/api.ts:90](frontend/lib/api.ts:90) |
| `login` เรียก `POST /auth/login` คืน `{access_token, refresh_token}` | [frontend/lib/api.ts:91](frontend/lib/api.ts:91) |
| ส่ง token เป็น `Authorization: Bearer` | [frontend/lib/api.ts:12](frontend/lib/api.ts:12) |
| เก็บ token ใน `localStorage["course_advisor_token"]` | [frontend/app/page.tsx:54](frontend/app/page.tsx:54) |
| หน้า `/crawl-review` ใช้ **คีย์เดียวกัน** | [frontend/app/crawl-review/page.tsx:34](frontend/app/crawl-review/page.tsx:34) `const TOKEN_KEY = "course_advisor_token"` และบรรทัด 90-91 เรียก `api.login(...)` |

ตรวจ dependency แล้ว `frontend/package.json` มี 7 dependency
(`next`, `react`, `react-dom`, `react-hook-form`, `@hookform/resolvers`, `zod`, `lucide-react`)
**ไม่มี `@supabase/supabase-js`** และ `git grep -il supabase -- frontend` ได้ **0 ไฟล์**

### 1.2 SPA ของทีมออกแบบ (`/srv/web`) — เข้าทางโดเมน HTTPS

ใช้ **Supabase Auth** ตรวจจากบันเดิลที่ build แล้วบนเซิร์ฟเวอร์ (40 ไฟล์ 8.5 MB, `.js` 4 ไฟล์)
พบครบทุกคำในทั้ง 4 ไฟล์ js

```
createClient · supabase.auth · signInWithPassword · signUp
getSession · onAuthStateChange · signOut · resetPasswordForEmail · auth/v1
```

โฮสต์ Supabase ที่บันเดิลชี้ไป: `https://hlln…<ปิดไว้>.supabase.co`

**สำหรับนักเรียนทั่วไป SPA นี้ไม่บังคับ login เลย** — ดูข้อ 4.3

---

## 2. Supabase Auth ถูกใช้อยู่จริงหรือไม่ และใช้ตรงไหน

**ใช้จริง** สองจุด

### 2.1 ในเบราว์เซอร์ของ SPA

เรียก Supabase Auth API ตรงจากเบราว์เซอร์ (`auth/v1`) ด้วย anon key
**ไม่ผ่านเซิร์ฟเวอร์ของเราเลย** — Caddy เสิร์ฟ SPA เป็นไฟล์สแตติกเท่านั้น

### 2.2 ใน `webapi` เพื่อคุม `/api/admin/*`

`webapi/api/_lib/adminAuth.js` (41 บรรทัด อยู่บนเซิร์ฟเวอร์ ไม่ถูก track ใน repo นี้)

```js
const ADMIN_ROLES = ['admin', 'editor'];
export async function requireAdminUser(request) {
  const url = process.env.VITE_SUPABASE_URL;
  const anonKey = process.env.VITE_SUPABASE_ANON_KEY;
  ...
  const token = authHeader.replace(/^Bearer\s+/i, '');
  const supabase = createClient(url, anonKey, { global: { headers: { Authorization: `Bearer ${token}` } } });
  const { data: { user }, error: userError } = await supabase.auth.getUser(token);
  if (userError || !user) → 401
  ... .from('user_profiles').select('role, status').eq('user_id', user.id) ...
  if (!ADMIN_ROLES.includes(profile?.role) || profile?.status !== 'approved') → 403
}
```

ข้อสังเกตเชิงสถาปัตยกรรม: `webapi` **ไม่ได้ตรวจลายเซ็น JWT เอง** แต่ส่ง token ไปถาม
Supabase Auth API (`getUser`) ทุกคำขอ จึงไม่ต้องถือ JWT secret ของ Supabase ไว้เลย

`webapi/server.mjs` รับผิดชอบ **5 เส้นทางเท่านั้น** และ **ไม่มีเส้นทาง login/register**

```
/api/sci-connect-news-detail   /api/sci-connect-news
/api/admin/extract-file        /api/admin/ingest        /api/admin/sync-sci-news
```

env ที่ `webapi` ใช้จริงมีเพียง `PORT`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`
(ตรวจชื่อคีย์ในคอนเทนเนอร์ที่รันอยู่: `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`,
`GOOGLE_GENERATIVE_AI_API_KEY` — ไม่แสดงค่า)

---

## 3. ตาราง `user_profiles` / `users` ที่เกี่ยวข้องทำหน้าที่อะไร

**มีตารางชื่อ `user_profiles` อยู่ทั้งสองฝั่ง แต่คนละฐานข้อมูลและคนละหน้าที่โดยสิ้นเชิง —
นี่เป็นจุดที่ทำให้เข้าใจผิดได้ง่ายที่สุดในระบบนี้**

### 3.1 ฝั่ง Supabase

| ตาราง | หน้าที่ (อ้างจากโค้ดที่เรียกใช้) |
|---|---|
| `auth.users` (ของ Supabase เอง) | แหล่งตัวตนของ SPA · `signInWithPassword` / `signUp` ทำงานที่นี่ · `user.id` คือ UUID ของ Supabase |
| **`user_profiles`** | **ตารางสิทธิ์** — คอลัมน์ `user_id`, `role`, `status` · `adminAuth.js` อ่าน `role` ต้องเป็น `admin` หรือ `editor` และ `status` ต้องเป็น `approved` · บันเดิลของ SPA อ้างตารางนี้มากถึง 36 ครั้ง และมีสตริง `pending` / `approved` → มี flow ขออนุมัติผู้ใช้ในตัว |
| `courses` | ข้อมูลหลักสูตรของ SPA (คนละชุดกับ `public.courses` ของเรา) — อ้าง 60 ครั้ง |
| `news`, `knowledge_articles` | เนื้อหาข่าว/บทความของ SPA |
| `rag_documents` | **RAG ของทีมออกแบบ** (คนละชุดกับ `course_chunks` + pgvector ของเรา) |
| `ai_settings` | ค่าตั้งโมเดลของ SPA |

### 3.2 ฝั่ง PostgreSQL ของเรา

| ตาราง | หน้าที่ |
|---|---|
| **`public.users`** | แหล่งตัวตนของ FastAPI · `id uuid` PK · `email citext` UNIQUE · `password_hash text` (bcrypt) · `is_active bool` · **`is_admin bool`** · `created_at`/`updated_at` |
| **`public.user_profiles`** | **ไม่ใช่ตารางสิทธิ์** — เป็นแบบสอบถามของนักเรียน: `education_level`, `field_of_study`, `current_role`, `career_goal`, `skills`, `interests`, `language_preference`, `metadata` · **ไม่มีคอลัมน์ `role` หรือ `status`** ([backend/app/models/user.py:27-39](backend/app/models/user.py:27)) |
| `public.user_requirements` | เงื่อนไขที่นักเรียนระบุ |

> **กับดัก:** `current_role` ใน `public.user_profiles` เป็น "อาชีพปัจจุบันของนักเรียน"
> ไม่ใช่ role เชิงสิทธิ์ · และ `role` ใน `public.chat_messages` คือ `user`/`assistant`
> ของข้อความแชท ตรวจแล้วว่าในฐานข้อมูลของเรา **มีคอลัมน์สิทธิ์เพียงตัวเดียวคือ
> `public.users.is_admin`**

---

## 4. FastAPI Login / Register ใช้ `public.users` อย่างไร

### 4.1 Register — `POST /auth/register` (เปิดสาธารณะ ไม่ต้อง auth)

[backend/app/api/routes/auth.py:32-45](backend/app/api/routes/auth.py:32)

```python
existing = db.query(User).filter(User.email == payload.email).first()
if existing: raise HTTPException(409, "email already registered")
user = User(email=payload.email, password_hash=hash_password(payload.password), full_name=payload.full_name)
db.add(user); db.commit(); db.refresh(user)
```

- ไม่มี dependency ของ auth และ **ไม่มี rate limiter** บนเส้นทางนี้ (ข้อสังเกตเดิมของระบบ
  ไม่ใช่สิ่งที่การตรวจครั้งนี้เสนอให้แก้)
- `is_admin` ไม่ถูกกำหนดในคำขอ จึงได้ค่า default ของคอลัมน์ = `false` เสมอ
  → **สมัครเองแล้วเป็น admin ไม่ได้**
- คืน `UserOut` ซึ่งมีเพียง `id`, `email`, `full_name`, `created_at`
  ([backend/app/schemas/user.py:13-18](backend/app/schemas/user.py:13))

### 4.2 Login — `POST /auth/login`

[backend/app/api/routes/auth.py:48-62](backend/app/api/routes/auth.py:48)

```python
user = db.query(User).filter(User.email == payload.email).first()
password_hash = user.password_hash if user else _DUMMY_PASSWORD_HASH   # กัน timing/enumeration
ok = verify_password(payload.password, password_hash)
if not user or not ok or not user.is_active: raise HTTPException(401, "invalid credentials")
return TokenPair(access_token=create_access_token(str(user.id)),
                 refresh_token=create_refresh_token(str(user.id)))
```

- รหัสผ่าน: bcrypt cost 12 โดย **pre-hash ด้วย SHA-256 + base64** ก่อน เพื่อให้รหัสผ่าน
  ภาษาไทยที่ยาวเกิน 72 ไบต์ใช้ได้จริง ([backend/app/core/security.py:28-43](backend/app/core/security.py:28))
- login **ไม่เขียนข้อมูลใด** (ไม่มี `db.add` / `db.commit` ในเส้นทางนี้)
- **การเทียบอีเมลไม่สนตัวพิมพ์** เพราะคอลัมน์จริงเป็น `citext` ไม่ใช่ `String`
  อย่างที่ ORM ประกาศไว้ที่ [backend/app/models/user.py:15](backend/app/models/user.py:15)
  พิสูจน์ในฐานข้อมูล: `'Tester@gmail.com'::citext = 'TESTER@GMAIL.COM'::citext` → `true`
  ขณะที่เทียบแบบ `text` → `false` · และมี `UNIQUE INDEX users_email_key ON public.users (email)`
  บนคอลัมน์ citext จึงมีได้มากสุดหนึ่งแถวต่อหนึ่งอีเมลแบบไม่สนตัวพิมพ์

### 4.3 เส้นทางของ SPA บน FastAPI — ไม่มี auth เลย และใช้ "บัญชีกลาง"

[backend/app/services/web_compat.py:13-47](backend/app/services/web_compat.py:13) อธิบายไว้ตรง ๆ ว่า

> "หน้าเว็บนี้ไม่มีระบบเข้าสู่ระบบสำหรับนักเรียน ทุกคนที่เปิดเว็บใช้งานได้เลย
> แต่ตารางบทสนทนาผูกกับผู้ใช้เสมอ … จึงใช้บัญชีกลางหนึ่งบัญชีแทน"

```python
SHARED_USER_EMAIL = "public-web@stpnru.local"
def shared_user(db): ...สร้างอัตโนมัติครั้งแรก รหัสผ่านสุ่มที่ไม่มีใครรู้และไม่เก็บไว้...
```

endpoint ที่ SPA ใช้ (`/chat-web`, `/course-facts`, `/compare-courses`, `/recommend-major`)
มีเพียง `Depends(web_rate_limiter)` **ไม่มี `get_current_user` และไม่มี `require_admin`**
([backend/app/api/routes/web_compat.py:167, 252, 279, 330](backend/app/api/routes/web_compat.py:167))

→ สอดคล้องกับผลนับผู้ใช้ใน Step 3.5: โดเมน `stpnru.local` มี **1 บัญชี** ซึ่งคือบัญชีกลางนี้
ส่วน `example.com` 188 บัญชีเป็นข้อมูลทดสอบ/ผู้ใช้ของ Next.js app

---

## 5. JWT ของ Supabase กับ JWT ของ FastAPI เป็นคนละระบบหรือไม่

**คนละระบบโดยสมบูรณ์ ไม่มีทางใช้แทนกันได้ในสภาพปัจจุบัน**

| ประเด็น | FastAPI | Supabase |
|---|---|---|
| ผู้ออก token | `create_access_token()` ของเรา | Supabase Auth (`auth/v1`) |
| อัลกอริทึม | `HS256` ([config.py:27](backend/app/core/config.py:27)) | ตามการตั้งค่าของโปรเจกต์ Supabase — legacy shared HS256 หรือ asymmetric key ที่มี JWKS · **ยังไม่ได้ยืนยัน** เพราะห้ามแตะ Supabase |
| กุญแจ | `JWT_SECRET` ใน `.env` ของเรา | secret/keypair ของโปรเจกต์ Supabase ซึ่งเราไม่มี |
| claim | `sub` (UUID ของ `public.users`), `type` (`access`/`refresh`), `iat`, `exp` | `sub` (UUID ของ `auth.users`), `aud: authenticated`, `iss: https://<ref>.supabase.co/auth/v1`, `role`, `email`, `exp`, `app_metadata`, `user_metadata` |
| อายุ | access 30 นาที · refresh 14 วัน | ตามการตั้งค่าของ Supabase |
| ผู้ตรวจ | `decode_token()` ตรวจลายเซ็นในเครื่อง ([security.py:78-80](backend/app/core/security.py:78)) | `supabase.auth.getUser(token)` ถาม Supabase ผ่านเครือข่าย |
| ตรวจ `iss` / `aud` | **ไม่ตรวจ** — `jwt.decode(token, secret, algorithms=["HS256"])` เท่านั้น | Supabase ตรวจเอง |

ผลที่ตามมาโดยตรงจากโค้ด: ถ้าส่ง Supabase JWT ไปที่ `/crawl-review/*`
`jwt.decode` จะตรวจลายเซ็นไม่ผ่านและโยน `InvalidTokenError` → `get_current_user`
ตอบ **401 `invalid token`** ([deps.py:38-39](backend/app/api/deps.py:38))
แม้จะข้ามด่านลายเซ็นได้ ค่า `sub` ก็เป็น UUID ของ Supabase ซึ่ง `db.get(User, sub)`
หาไม่เจอใน `public.users` → 401 `user not found or inactive`

> **ข้อควรระวังด้านความปลอดภัยที่พบ:** `decode_token` **ไม่ตรวจ `iss` และ `aud`**
> ถ้าวันหนึ่งมีใครเพิ่ม Supabase legacy HS256 secret เข้าไปเป็นกุญแจที่ยอมรับ
> โดยไม่เพิ่มการตรวจ `iss`/`aud` จะเกิดช่อง **token confusion** ข้ามบริการทันที
> เรื่องนี้ต้องแก้พร้อมกันถ้าเลือกทางเลือก A

---

## 6. Frontend ส่ง token แบบไหนให้ FastAPI

**Bearer token ใน HTTP header เท่านั้น — ไม่มี cookie ไม่มี session ฝั่งเซิร์ฟเวอร์**

```
Authorization: Bearer <FastAPI access token>     (frontend/lib/api.ts:12)
```

เส้นทางของคำขอมีสองทางและ **ทั้งสองทางไปถึง FastAPI ตัวเดียวกัน**

| ทางเข้า | ขั้นตอน |
|---|---|
| `http://<IP>:80` (Next.js) | เบราว์เซอร์ → `/api/...` → route handler ของ Next ([frontend/app/api/[...path]/route.ts](frontend/app/api/%5B...path%5D/route.ts)) ส่งต่อไป `BACKEND_ORIGIN=http://backend:8000` โดยส่งเฉพาะ header `authorization`, `content-type`, `accept` |
| โดเมน HTTPS | เบราว์เซอร์ → Caddy `handle /api/*` → `uri strip_prefix /api` → `backend:8000` |

Next proxy **ไม่ส่ง cookie ต่อ** (ยกเฉพาะ 3 header ข้างบน) ดังนั้นไม่มี CSRF surface
จาก cookie และไม่มีทางที่ session ของ Supabase (ซึ่งเก็บใน storage ของเบราว์เซอร์
บนโดเมนนั้น) จะไหลไปถึง FastAPI เองโดยอัตโนมัติ

---

## 7. `/crawl-review` ตรวจ token และ admin จากที่ไหน

| ชั้น | กลไก | ที่มา |
|---|---|---|
| router | `APIRouter(prefix="/crawl-review", dependencies=[Depends(require_admin)])` — บังคับทุกเส้นทาง | [backend/app/api/routes/crawl_review.py:50-53](backend/app/api/routes/crawl_review.py:50) |
| token | `decode_token()` ด้วย `JWT_SECRET` ของเรา · ต้องมี `type == "access"` | [backend/app/api/deps.py:35-42](backend/app/api/deps.py:35) |
| ตัวตน | `user = db.get(User, uuid.UUID(payload["sub"]))` — **อ่านแถวจาก `public.users` ใหม่ทุกคำขอ** · ต้อง `is_active` | [backend/app/api/deps.py:44-46](backend/app/api/deps.py:44) |
| สิทธิ์ | `if not user.is_admin: raise HTTPException(403, "admin only")` | [backend/app/api/deps.py:50-53](backend/app/api/deps.py:50) |
| ผู้บันทึกการตัดสินใจ | `decided_by=str(admin.email)` — มาจากฝั่งเซิร์ฟเวอร์ ไม่รับจาก request body | `crawl_review.py` |
| ชั้นฐานข้อมูล | `advisor_api` มีเพียง SELECT/INSERT บน `mko.crawl_decisions` และ UPDATE เฉพาะ `superseded_at`, `superseded_by` · ไม่มี DELETE | migration `004_crawl_decisions.sql` |

**ผลตรวจจริงบน production:** ทั้งสาม GET ของ `/api/crawl-review/*` ตอบ
**401 `{"detail":"missing bearer token"}`** เมื่อไม่ส่ง token — route มีจริงและบังคับ auth

**ข้อสำคัญ:** token ไม่บรรจุ role ใด ๆ สิทธิ์อ่านจากแถวผู้ใช้ทุกคำขอ →
**เปลี่ยน `is_admin` แล้วมีผลทันทีโดยไม่ต้อง restart และไม่ต้อง login ใหม่**

---

## 8. ตอนนี้มี User / Auth ซ้ำกันสองระบบจริงหรือไม่

**จริง และซ้ำแบบขนานกันสมบูรณ์ ไม่มีจุดเชื่อม**

| มิติ | ระบบ A (Supabase) | ระบบ B (FastAPI/PostgreSQL) |
|---|---|---|
| แหล่งตัวตน | `auth.users` ของ Supabase | `public.users` |
| สมัคร | `supabase.auth.signUp` ในเบราว์เซอร์ | `POST /auth/register` |
| เข้าสู่ระบบ | `supabase.auth.signInWithPassword` | `POST /auth/login` |
| รีเซ็ตรหัสผ่าน | `resetPasswordForEmail` ของ Supabase | **ไม่มีในระบบเรา** |
| เก็บ session | storage ของ supabase-js | `localStorage["course_advisor_token"]` |
| รูปแบบสิทธิ์ | `user_profiles.role ∈ {admin, editor}` **และ** `status = 'approved'` (สามสถานะ มี flow อนุมัติ) | `users.is_admin` (บูลีนเดียว ไม่มี flow อนุมัติ) |
| ผู้บังคับสิทธิ์ | `webapi/api/_lib/adminAuth.js` | `backend/app/api/deps.py::require_admin` |
| คุ้มครองอะไร | `/api/admin/extract-file`, `/api/admin/ingest`, `/api/admin/sync-sci-news` | `/crawl-review/*` (Phase 3A) |
| คลังความรู้ที่เกี่ยวข้อง | Supabase `rag_documents`, `courses`, `news`, `knowledge_articles` | `public.course_chunks` (pgvector 1024 มิติ), `public.courses`, `mko.*` |

**จุดที่ "ไม่ซ้ำ" และต้องเข้าใจให้ตรง:** ฝั่ง **นักเรียนที่ใช้โดเมน** ไม่มีบัญชีเลย
ทุกคนใช้งานแบบไม่ล็อกอินและประวัติแชทกองอยู่ที่บัญชีกลาง `public-web@stpnru.local`
ดังนั้นสิ่งที่ซ้ำกันจริงคือ **ระบบผู้ใช้ฝั่งทีมงาน/หลังบ้าน** ไม่ใช่ฐานผู้ใช้ของนักเรียน

---

## 9. `Tester@gmail.com` ใน Supabase เชื่อมกับ FastAPI ได้อย่างไร

ตรวจแล้วใน Step 3.5: `public.users` **ไม่มีบัญชีนี้เลย** (0 แถว ทั้งแบบ citext ตรงตัว,
`lower()`, `btrim()` และ `email ILIKE 'tester@%'` ทุกโดเมน)
ส่วนการมีอยู่ใน Supabase **ยืนยันไม่ได้ในการตรวจครั้งนี้** เพราะห้ามแตะ Supabase —
ถือตามที่เจ้าของโปรเจกต์แจ้ง

วันนี้ **เชื่อมกันไม่ได้เลย** โดยไม่ทำอย่างใดอย่างหนึ่งต่อไปนี้ (เรียงจากงานน้อยไปมาก)

| วิธี | สิ่งที่ต้องทำ | ต้องแก้โค้ด | ต้อง migration |
|---|---|---|---|
| **9.1 สร้างบัญชีชื่อเดียวกันในระบบเรา** | เจ้าของสมัคร `Tester@gmail.com` เองผ่านหน้า Next.js (`/auth/register`) ตั้งรหัสผ่านของตัวเอง แล้วเราค่อย promote `is_admin` ตามขั้นตอนที่ตรวจแล้วใน Step 3.5 §17.1 | **ไม่ต้อง** | **ไม่ต้อง** |
| 9.2 ให้ FastAPI ยอมรับ Supabase token | = ทางเลือก A ข้างล่าง | ต้อง | อาจต้อง (ถ้าทำ auto-provision) |
| 9.3 ผูกตัวตนสองฝั่งเข้าหากัน | = ทางเลือก C ข้างล่าง | ต้อง | ต้อง |

ข้อ 9.1 ให้ผลว่า **อีเมลเดียวกัน แต่เป็นสองบัญชีคนละระบบและคนละรหัสผ่าน**
ซึ่งใช้งานได้ทันทีและไม่เสี่ยงอะไร แต่ยังไม่ใช่ single sign-on

---

## 10. ทางเลือกสถาปัตยกรรม — เปรียบเทียบครบสามทาง

### ก่อนเปรียบเทียบ: ต้องตอบคำถามเดียวนี้ให้ชัดก่อน

ข้อกำหนด *"ให้ `/crawl-review` ใช้ account เดียวกับที่ผู้ใช้ login หน้าเว็บ"*
ตีความได้สองแบบ และคำตอบต่างกันสิ้นเชิง

| การตีความ | สถานะวันนี้ | สิ่งที่ต้องทำ |
|---|---|---|
| **(ก) "หน้าเว็บ" = Next.js app ที่ `:80`** ซึ่งเป็นที่อยู่ของ `/crawl-review` เอง | **เป็นบัญชีเดียวกันอยู่แล้ว** — ใช้ `localStorage["course_advisor_token"]` คีย์เดียวกันและ `api.login` ตัวเดียวกัน | แค่ให้มีบัญชีในระบบเราแล้ว promote — **ไม่ต้องแก้อะไรเลย** |
| **(ข) "หน้าเว็บ" = SPA บนโดเมน** ที่ใช้ Supabase | **คนละบัญชีคนละระบบ** | ต้องทำ A หรือ C |

ผมไม่เดาว่าเจ้าของหมายถึงแบบไหน จึงเสนอทั้งสองเส้นทางและระบุคำแนะนำของแต่ละแบบ

---

### ทางเลือก A — Supabase Auth เป็น source of truth และ FastAPI verify Supabase token

**สิ่งที่ต้องแก้**

1. `backend/app/core/security.py` — เพิ่มตัวตรวจ Supabase JWT แยกจาก `decode_token`
   ต้องรู้ก่อนว่าโปรเจกต์ Supabase ใช้ legacy shared HS256 secret หรือ asymmetric key
   - ถ้า HS256 legacy: เก็บ secret เพิ่มใน `.env` และ **บังคับตรวจ `iss` และ `aud`**
   - ถ้า asymmetric: ต้องดึงและแคช JWKS จาก `https://<ref>.supabase.co/auth/v1/.well-known/jwks.json`
     เพิ่ม dependency (เช่น `PyJWKClient`) จัดการ key rotation, timeout, และ fallback
     เมื่อ Supabase ล่ม
2. `backend/app/api/deps.py` — `get_current_user` ต้องแยกสองเส้นทาง: token ของเรา
   กับ token ของ Supabase แล้ว map `sub` ของ Supabase → แถวใน `public.users`
3. กลไก **provisioning** — เมื่อผู้ใช้ Supabase เข้ามาครั้งแรกจะยังไม่มีแถวใน `public.users`
   ต้องตัดสินใจว่าจะสร้างอัตโนมัติ (เพิ่มความเสี่ยง: ใครสมัคร Supabase ได้ก็ได้แถวในระบบเรา)
   หรือปฏิเสธจนกว่าจะมีคน provision ให้
4. ตัดสินใจเรื่อง **สิทธิ์** — จะยึด `users.is_admin` ของเราต่อ หรือย้ายไปอ่าน
   Supabase `user_profiles.role/status` (ซึ่ง backend ของเรายังไม่มีทางอ่าน Supabase เลย
   ต้องเพิ่ม client + คีย์ใหม่เข้ามาใน backend ที่เปิดสู่อินเทอร์เน็ต)
5. `frontend/` — เปลี่ยนหน้า `/crawl-review` ให้ login ด้วย Supabase แทน `api.login`
   เพิ่ม `@supabase/supabase-js` และตั้ง `NEXT_PUBLIC_SUPABASE_*` ตอน build

**ไฟล์/ตารางที่กระทบ**
`backend/app/core/security.py`, `backend/app/core/config.py`, `backend/app/api/deps.py`,
`backend/requirements.txt`, `frontend/lib/api.ts`, `frontend/app/crawl-review/page.tsx`,
`frontend/package.json`, `docker-compose.prod.yml`, `.env` ของ production ·
ตาราง `public.users` (ถ้าเพิ่มคอลัมน์ผูก Supabase id) · Supabase `user_profiles` (ถ้าย้ายสิทธิ์ไปที่นั่น)

**migration** — ต้อง ถ้าเก็บ Supabase user id (เช่น `users.supabase_user_id uuid UNIQUE`)
หรือถ้าต้องผ่อนเงื่อนไข `password_hash NOT NULL` สำหรับบัญชีที่ไม่มีรหัสผ่านของเราเอง
(ปัจจุบันคอลัมน์นี้ `NOT NULL`)

**ผลด้านความปลอดภัย**

- ข้อดี: source of truth เดียว · ได้ password reset, email verification, MFA ของ Supabase มาใช้ฟรี
- ข้อเสีย/ความเสี่ยง:
  - **สูงสุดคือ token confusion** — ปัจจุบัน `decode_token` ไม่ตรวจ `iss`/`aud` ถ้าเพิ่ม
    กุญแจที่สองเข้าไปโดยไม่เพิ่มการตรวจเหล่านี้ จะรับ token ที่ออกให้บริการอื่นมาใช้ได้
  - backend ที่เปิดสู่อินเทอร์เน็ตต้องถือคีย์ Supabase เพิ่ม → ขยาย secret surface
  - ถ้า auto-provision: ใครสมัคร Supabase ได้ ก็ได้แถวใน `public.users` ของเราทันที
  - เพิ่ม dependency ภายนอกในเส้นทาง auth — Supabase ล่ม/JWKS ดึงไม่ได้ = ล็อกอินหลังบ้านล่ม
  - ทีมออกแบบเป็นผู้คุมโปรเจกต์ Supabase → **การเปลี่ยนค่าฝั่งนั้นกระทบสิทธิ์ของระบบเรา**

**ความเข้ากันได้** — ต้อง build backend และ frontend ใหม่ทั้งคู่ และ recreate ทั้งสอง
`/chat-web` และเส้นทางของ SPA ไม่กระทบเพราะไม่มี auth อยู่แล้ว
บัญชีเดิม 197 บัญชีใน `public.users` จะ login ด้วยรหัสผ่านเดิมไม่ได้อีก
ถ้าเลิกรับ token ของเรา — ต้องคงสองเส้นทางไว้หรือย้ายบัญชีทั้งหมด

**ความเสี่ยงต่อ production: สูง** — แตะเส้นทาง auth ของระบบที่ให้บริการอยู่
ต้อง deploy สองบริการ และมีโอกาสล็อกผู้ใช้เดิมออกถ้าออกแบบผิด

---

### ทางเลือก B — PostgreSQL / FastAPI Auth เป็น source of truth

**สิ่งที่ต้องแก้: ไม่มีเลย**

`/crawl-review` ใช้ `public.users.is_admin` อยู่แล้ว และหน้า `/crawl-review`
ใช้ `api.login` + `localStorage["course_advisor_token"]` ตัวเดียวกับหน้าแรกของ Next.js อยู่แล้ว
สิ่งที่ขาดคือ **มีบัญชีอยู่จริงในระบบเรา** เท่านั้น

ขั้นตอนที่ต้องทำ (เป็นงานของคน ไม่ใช่การแก้ระบบ)

1. เจ้าของโปรเจกต์สมัคร `Tester@gmail.com` (หรืออีเมลที่ต้องการ) ผ่านหน้า Next.js
   ที่ `http://<IP>:80` → เรียก `POST /auth/register` ตั้งรหัสผ่านของตัวเอง
   **ไม่ต้องส่งรหัสผ่านให้ใคร**
2. เจ้าของแจ้งอีเมลนั้นและอนุมัติให้ promote
3. รัน transaction ที่มีด่านครบตาม Step 3.5 §17.1 (lock, cardinality = 1,
   assert 197/197/0 → 197/197/1, `decisions = 0`, invariants หลักสูตรไม่ขยับ)
4. `/crawl-review` ใช้ได้ทันที **ไม่ต้อง restart** (สิทธิ์อ่านจาก DB ทุกคำขอ)

**ไฟล์/ตารางที่กระทบ** — ไม่มีไฟล์ใดถูกแก้ · แตะ `public.users` เพียงแถวเดียวหนึ่งคอลัมน์
(`is_admin` และ `updated_at` ที่ trigger `trg_users_updated_at` เปลี่ยนให้เอง)

**migration** — **ไม่ต้อง**

**ผลด้านความปลอดภัย**

- ข้อดี: ไม่ขยาย secret surface · ไม่เพิ่ม dependency ภายนอกในเส้นทาง auth ·
  `require_admin` เป็นด่านเดียวที่ตรวจง่ายและ audit ง่าย · ชั้นฐานข้อมูลบังคับซ้ำอีกชั้น
  (`advisor_api` ไม่มี DELETE และแก้ได้แค่สองคอลัมน์ของการถอน)
- ข้อจำกัดที่ต้องยอมรับ: ระบบเรา **ไม่มี password reset และไม่มี email verification**
  ถ้าลืมรหัสผ่านต้องให้คนที่เข้าถึงฐานข้อมูลจัดการ · `POST /auth/register` เปิดสาธารณะ
  และไม่มี rate limiter (สภาพเดิมของระบบ) · ยังมีสองระบบผู้ใช้อยู่ในภาพรวม
- หน้า `/crawl-review` เข้าได้เฉพาะทาง `:80` ซึ่งเป็น **HTTP ไม่เข้ารหัส**
  → ถ้าใช้งานจริงเป็นประจำ **ควรเข้าผ่าน SSH tunnel** ไม่ควรส่งรหัสผ่านผ่าน HTTP สาธารณะ
  (เรื่องนี้เป็นความเสี่ยงที่มีอยู่แล้วและควรจัดการแยก ไม่ใช่การแก้ Caddy ในรอบนี้)

**ความเข้ากันได้** — สมบูรณ์ ไม่กระทบ RAG, pgvector, `course_chunks`, `mko.*`,
SPA, webapi, Supabase หรือบัญชีเดิม 197 บัญชี

**ความเสี่ยงต่อ production: ต่ำสุด** — เปลี่ยนค่าบูลีนหนึ่งค่าในหนึ่งแถว ย้อนกลับได้
ด้วย transaction ที่มีด่านครบ (Step 3.5 §17.2)

---

### ทางเลือก C — Identity mapping ระหว่าง Supabase กับ PostgreSQL

ยังให้แต่ละระบบ login ด้วยกลไกของตัวเอง แต่ผูกว่า "คนเดียวกัน" ด้วยตารางกลาง

**สิ่งที่ต้องแก้**

1. migration ใหม่ (`005_identity_map`) — เช่น
   `mko.identity_links(supabase_user_id uuid PK, user_id uuid REFERENCES public.users(id), linked_at, linked_by)`
   หรือเพิ่มคอลัมน์ `public.users.supabase_user_id uuid UNIQUE`
2. กลไก linking — ต้องมีใครยืนยันว่า Supabase user คนนั้นคือเจ้าของบัญชีเรา
   (ผูกด้วยอีเมลอย่างเดียว **ไม่ปลอดภัย** ถ้าฝั่งใดฝั่งหนึ่งไม่ยืนยันอีเมล)
3. `/crawl-review` ยังอ่าน `users.is_admin` ต่อได้ แต่ต้องตัดสินใจว่า
   ยอมรับ Supabase token ด้วยไหม — ถ้าใช่ ก็ต้องทำงานตรวจ token เท่ากับทางเลือก A
4. งานดูแลต่อเนื่อง: บัญชีถูกลบฝั่งหนึ่ง สถานะ `status` เปลี่ยนจาก `approved`
   เป็นอื่น หรือ role เปลี่ยน — ต้องมีนโยบายว่าฝั่งเราตามด้วยไหมและตามอย่างไร

**ไฟล์/ตารางที่กระทบ** — `db/migrations/005_*.sql` ใหม่ · `public.users` หรือ schema `mko` ·
`backend/app/api/deps.py` · โค้ด/สคริปต์ linking ใหม่ · อาจกระทบ `frontend/`

**migration** — **ต้อง**

**ผลด้านความปลอดภัย**

- ข้อดี: ไม่ต้องย้ายบัญชี · ยังคงด่าน `is_admin` ของเราเป็นตัวตัดสินสิทธิ์สุดท้าย
- ข้อเสีย: **ซับซ้อนที่สุด** และมีจุดพลาดมากที่สุด · การผูกด้วยอีเมลเปิดช่อง
  account takeover ถ้าฝั่งใดไม่ยืนยันอีเมล · มีสองแหล่งความจริงที่ต้อง sync
  ซึ่งจะ desync แน่นอนเมื่อเวลาผ่านไป · ถ้ายอมรับ Supabase token ก็ได้ความเสี่ยง
  ของทางเลือก A มาเพิ่มด้วย

**ความเข้ากันได้** — เข้ากันได้กับทุกอย่างที่มีอยู่ (เป็นการเพิ่มล้วน) แต่ต้อง deploy
migration + backend

**ความเสี่ยงต่อ production: กลาง** — migration เป็น additive จึงย้อนง่าย
แต่ผิวสัมผัสโค้ดและภาระการดูแลระยะยาวสูง

---

## คำแนะนำ

**ระยะสั้น — เลือกทางเลือก B และทำตามข้อ 9.1**

เหตุผลที่ตรงกับสภาพระบบจริง

1. `/crawl-review` เป็นหน้าหลังบ้านที่อยู่ใน Next.js app และ **ใช้บัญชีเดียวกับ login
   ของ Next.js อยู่แล้ววันนี้** (คีย์ `localStorage` เดียวกัน, `api.login` ตัวเดียวกัน)
   ถ้าเจ้าของหมายถึงการตีความ (ก) **ระบบก็ตรงตามข้อกำหนดแล้วโดยไม่ต้องแก้อะไร**
2. ฝั่งโดเมน **ไม่มีฐานผู้ใช้ของนักเรียนให้รวม** เพราะ SPA ไม่บังคับ login
   และใช้บัญชีกลางหนึ่งบัญชี — ดังนั้น "ผู้ใช้ซ้ำสองระบบ" จริง ๆ คือทีมงานหลังบ้านไม่กี่คน
3. สิทธิ์ที่ Supabase คุม (`role ∈ {admin, editor}`, `status = 'approved'`) มีไว้สำหรับ
   ข่าวและ RAG ของทีมออกแบบ ซึ่งเป็นงานคนละเรื่องกับการอนุมัติ มคอ. เข้าคลังของเรา
   การรวมสองเรื่องนี้เข้าด้วยกันทำให้ทีมออกแบบกลายเป็นผู้ควบคุมสิทธิ์ ingestion ของเราโดยปริยาย
4. ต้นทุนและความเสี่ยงต่ำสุด ไม่แตะ RAG/pgvector/หลักสูตร ไม่ต้อง migration ไม่ต้อง deploy

**ระยะยาว — พิจารณา A เป็นเป้าหมาย เฉพาะเมื่อเจ้าของตัดสินว่าทีมงานต้องมี single sign-on จริง**
และควรทำเป็นเฟสของตัวเองพร้อม audit แยก โดยมีเงื่อนไขบังคับสามข้อ

- ยืนยันก่อนว่าโปรเจกต์ Supabase ใช้ HS256 legacy หรือ asymmetric JWKS
- **เพิ่มการตรวจ `iss` และ `aud` ให้ `decode_token` ก่อน** จะรับกุญแจที่สองใด ๆ
- ตัดสินให้ชัดว่า provisioning เป็นแบบอัตโนมัติหรือต้องมีคนอนุมัติ (แนะนำแบบมีคนอนุมัติ)

**ไม่แนะนำทางเลือก C** เว้นแต่จำเป็นต้องให้ทั้งสองระบบ login ต่อไปพร้อมกันอย่างถาวร —
ได้ความซับซ้อนและภาระ sync มาโดยไม่ได้ source of truth ที่ชัดเจนขึ้นจริง

---

## สิ่งที่ยืนยันไม่ได้ในการตรวจครั้งนี้ (ตามข้อห้าม READ-ONLY)

| รายการ | เหตุผล |
|---|---|
| `Tester@gmail.com` มีอยู่ใน Supabase จริงหรือไม่ และมี `role`/`status` อะไร | ห้ามแตะ Supabase — ถือตามที่เจ้าของแจ้ง |
| Supabase ใช้ JWT แบบ HS256 legacy หรือ asymmetric JWKS | ต้องอ่าน config/endpoint ของโปรเจกต์ Supabase · กระทบเฉพาะการประเมินงานของทางเลือก A |
| source code ของ SPA | อยู่คนละ repo ไม่ได้ track ที่นี่ — ตรวจได้เฉพาะบันเดิลที่ build แล้วบนเซิร์ฟเวอร์ (40 ไฟล์ 8.5 MB) |
| source code ของ `webapi/api/*` | ไม่ได้ track ใน repo นี้ — ตรวจจากไฟล์บนเซิร์ฟเวอร์ (10 ไฟล์) ซึ่งเป็นของจริงที่รันอยู่ |
| ค่า `VITE_SUPABASE_URL` / anon key / `JWT_SECRET` | เป็นค่าลับ — ตรวจเฉพาะชื่อคีย์และปิดค่าไว้ |

---

## ยืนยันว่าไม่ได้ทำอะไรกับระบบ

การตรวจครั้งนี้เป็นการอ่านทั้งหมด: `git show` / `git grep` / `git ls-tree` บน revision,
`docker inspect`, `docker exec` ที่รัน `psql` ใน `BEGIN TRANSACTION READ ONLY` พร้อม
`statement_timeout`, `grep` / `find` / `wc` บนไฟล์บนเซิร์ฟเวอร์, และการอ่านชื่อ env key
ในคอนเทนเนอร์

**ไม่ได้แก้ Supabase · ไม่ได้แก้ PostgreSQL · ไม่ได้ CREATE/UPDATE/DELETE ผู้ใช้ ·
ไม่ได้ promote admin · ไม่ได้เปลี่ยนรหัสผ่าน · ไม่ได้แก้ auth · ไม่ได้แก้ Caddy ·
ไม่ได้ deploy · ไม่ได้ restart บริการใด · ไม่ได้ commit/push · ไม่ได้รัน ingestion ·
ไม่ได้รัน worker/crawler · ไม่ได้เปลี่ยน production config · ไม่ได้แสดงค่าลับใด**

ไฟล์เดียวที่สร้างคือรายงานฉบับนี้ (uncommitted ตามแนวปฏิบัติของ `docs/`)

---

## STOP

**ไม่ implement วิธีที่เสนอจนกว่าจะได้รับอนุมัติ** — ขั้นถัดไปที่ต้องให้เจ้าของโปรเจกต์ตัดสินคือ

1. `"หน้าเว็บ"` ในข้อกำหนดหมายถึง Next.js ที่ `:80` (การตีความ ก) หรือ SPA บนโดเมน (ข)
2. ถ้าเป็น (ก) หรือรับทางเลือก B: แจ้งอีเมลของบัญชีที่มีอยู่จริงในระบบเรา
   หรือสมัครบัญชีเองผ่านหน้า Next.js แล้วอนุมัติให้ promote
3. ถ้าต้องการทางเลือก A หรือ C: อนุมัติให้เปิดเฟสใหม่พร้อม audit ของเฟสนั้นเอง

STOP
