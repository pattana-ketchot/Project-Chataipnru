# M3 — WebAPI PostgreSQL Connection · Design & Pre-Apply

| | |
|---|---|
| วันที่ | 2026-10-05 |
| **Classification** | **`M3_DESIGN_READY`** |
| ตรวจ production | **READ-ONLY ทั้งหมด** — เส้นทางเครือข่าย · สิทธิ์ · ขีดจำกัด connection |
| พิสูจน์ resolver | **สวมบทเป็น `advisor_web` บน production จริง** · query คืน **1 แถวพอดี** |
| ⚠ พบระหว่างตรวจ | **image ของ `webapi` ที่รันอยู่เป็นของ 2026-09-22 — `cf4fb16` ยังไม่เคย deploy** (ข้อ 1.5) |
| แก้ production ในรอบนี้ | **ไม่มีแม้อย่างเดียว** |

```
แก้ production .env   NONE     restart webapi      NONE     deploy            NONE
Production write      NONE     Supabase Write      NONE     ALTER/GRANT/REVOKE NONE
แก้ frontend          NONE     Data Migration      NONE     commit/push/merge NONE
```

**ไม่มีรหัสผ่าน ไม่มี connection string ที่มีรหัสผ่าน ไม่มี Supabase UUID ในเอกสารนี้**

---

## 1. Current architecture

### 1.1 `webapi` คืออะไร

| | |
|---|---|
| ภาษา/รันไทม์ | **Node.js v22.23.2** (ยืนยันจากคอนเทนเนอร์จริง) · ESM (`"type": "module"`) |
| จุดเริ่ม | `node server.mjs` → `http.createServer` → `listen(3001, "0.0.0.0")` |
| หน้าที่ | **5 เส้นทางเท่านั้น** — ข่าว Sci Connect 2 · งานหลังบ้าน 3 |
| การเปิดพอร์ต | `expose: 3001` — **ไม่ publish ออกนอกเครื่อง** เข้าได้เฉพาะผ่าน Caddy |
| health | `GET /healthz` · Docker `HEALTHCHECK` เรียกทุก 30 วินาที |

```
/api/sci-connect-news-detail   PUBLIC
/api/sci-connect-news          PUBLIC
/api/admin/extract-file        EDITOR
/api/admin/ingest              EDITOR
/api/admin/sync-sci-news       EDITOR
```

### 1.2 ⚠ ตอนนี้ `webapi` มี PostgreSQL client หรือยัง — **ยังไม่มี**

`webapi/package.json` → `dependencies`

```
@supabase/supabase-js   @ai-sdk/google   ai   mammoth   pdf-parse   zod
```

**ไม่มี `pg` ไม่มี `postgres` ไม่มี ORM ใด** · README ของ `webapi` ระบุตรง ๆ ว่า
*"บริการนี้**ไม่ได้ต่อฐานข้อมูล PostgreSQL ของเราเลย**"*

→ M3 คือรอบที่เปลี่ยนข้อนั้น

### 1.3 เส้นทางเครือข่ายไป PostgreSQL — **ยืนยันจากของจริง ไม่ได้เดา**

ตรวจจากในคอนเทนเนอร์ `webapi` บน production

| ข้อตรวจ | ผล |
|---|---|
| network ของ `webapi` | `course-advisor-system_default` = `172.18.0.8` |
| network ของ `postgres` | `course-advisor-system_default` = `172.18.0.2` |
| **DNS: `postgres` แปลงเป็น** | **`172.18.0.2`** ✅ |
| **TCP ไป `postgres:5432`** | **ต่อได้** ✅ |

→ **hostname = `postgres` · port = `5432`** · อยู่ network เดียวกันจริงตามที่ระบุ

`docker-compose.prod.yml` **ไม่ publish พอร์ตของ postgres ออกนอกเครื่อง**
(ต่างจาก `docker-compose.yml` ของ dev ที่ผูก `127.0.0.1:5432:5432`)
→ เข้าถึงได้เฉพาะจากใน docker network เท่านั้น

### 1.4 ⚠ `webapi` ไม่มี `depends_on: postgres`

`docker-compose.prod.yml` — `backend` มี `depends_on: postgres: condition: service_healthy`
แต่ **`webapi` ไม่มี** เพราะวันนี้ยังไม่ได้ใช้ฐานข้อมูล

→ ต้องเพิ่มพร้อมกับ pool ไม่งั้น `webapi` อาจขึ้นก่อน postgres พร้อม

### 1.5 ⚠ พบระหว่างตรวจ — **image ที่รันอยู่เป็นของก่อนงาน authorization**

| หลักฐาน | ค่า |
|---|---|
| image created | **`2026-09-22T21:21:32Z`** |
| `/app` มี `auth.mjs` ไหม | **ไม่มี** |
| `/app/server.mjs` อ้างถึง `auth.mjs` | **0 ครั้ง** |
| `/healthz` ที่รันอยู่ตอบ | `{"status":"ok","routes":[…]}` — **ไม่มี `authConfigured` ไม่มี `level` รายเส้นทาง** |

→ **commit `cf4fb16` (`feat: add webapi authorization foundation`) ยังไม่เคยถูก deploy**
ซึ่งสอดคล้องกับที่ทุกรอบที่ผ่านมาห้าม deploy

#### production เปิดโล่งอยู่หรือไม่ — **ไม่**

ตรวจโค้ดที่รันอยู่จริงในคอนเทนเนอร์ · ทั้งสาม handler ของ `/api/admin/*` เรียก
`requireAdminUser` จาก `_lib/adminAuth.js` และคืนค่าทันทีถ้า `!auth.ok`

```
/app/api/admin/ingest.js        import { requireAdminUser } … if (!auth.ok) return auth.response;
/app/api/admin/extract-file.js  import { requireAdminUser } … if (!auth.ok) return auth.response;
/app/api/admin/sync-sci-news.js import { requireAdminUser } … if (!auth.ok) return auth.response;
```

→ วันนี้ production ป้องกันด้วย **การตรวจในตัว handler** · ด่านกลางจาก `cf4fb16`
เป็น **ชั้นป้องกันเพิ่ม** ที่ยังไม่ได้ขึ้น **ไม่ใช่ชั้นเดียวที่หายไป**

**ผลต่อ M3**: การ deploy ของ M3 จะพาเอา authorization foundation ขึ้นไปด้วยเป็นครั้งแรก
→ ไม่ใช่ deploy ที่ "เพิ่มแค่ pool" (ดูข้อ 8)

### 1.6 ⚠ `webapi/api/` ไม่ได้อยู่ในรีโปนี้ — ตั้งใจ

`.gitignore` บรรทัด 49 มี `webapi/api/` และ README อธิบายไว้ว่าเป็นโค้ดของทีมหน้าเว็บ
(คนละรีโปคนละเจ้าของ) · **ก่อน build ต้องคัดลอกมาวางที่ `webapi/api/` ก่อน**

→ ขั้น build ของ M3 ต้องทำขั้นนี้ด้วย ไม่งั้น image จะไม่มี handler เลย

### 1.7 ไม่มี `package-lock.json` ในรีโป แต่มีใน image

| | |
|---|---|
| ในรีโป | **ไม่มี** |
| ใน image ที่รันอยู่ (`/app/package-lock.json`) | **มี** — เกิดจาก `npm install` ตอน build |
| Dockerfile | `COPY package.json package-lock.json* ./` — glob จึงไม่ล้มเมื่อไม่มีไฟล์ |

→ ทุก build แก้ dependency ใหม่หมด · การเพิ่ม `pg` จึงควรทำพร้อมคิดเรื่อง lock file
(ดูข้อ 10 ความเสี่ยงข้อ 5)

### 1.8 Supabase auth flow ปัจจุบัน (ในโค้ดที่ commit แล้ว ยังไม่ deploy)

```
Authorization: Bearer <JWT>
  → parseBearer()
  → verifyToken()   = supabase.auth.getUser(token)   → { userId }
  → readProfile()   = SELECT role, status FROM user_profiles WHERE user_id = …
  → context { authenticated, userId, role, status }
  → authorize(context, level)
```

| หลักการที่ตั้งไว้แล้ว | |
|---|---|
| token พัง / ตรวจไม่ผ่าน / Supabase ล่ม | **ลดระดับเป็น anonymous** ไม่ปฏิเสธทันที · ให้ `authorize()` เป็นผู้ตัดสินจุดเดียว |
| อ่าน profile ไม่ได้ | ถือว่า **ไม่รู้สิทธิ์** → ไม่เดาว่ามีสิทธิ์ |
| log | บันทึกเฉพาะเส้นทางกับระดับ · **ไม่มี token ไม่มีอีเมล ไม่มี uuid** |

### 1.9 ⚠ ข้อบกพร่องที่พบในโค้ดเดิม — `createRuntimeDeps` ใช้ตัวแปรร่วมข้ามคำขอ

```js
export function createRuntimeDeps(config) {
  const verifier = createSupabaseVerifier(config);
  let lastIdentity = null;            // <-- ใช้ร่วมกันทุกคำขอ
  return {
    async verifyToken(token) { lastIdentity = await verifier.verifyToken(token); … },
    async readProfile(userId) { return verifier.readProfile(userId, lastIdentity); },
  };
}
```

คำขอสองรายการที่ทับเวลากัน: A เรียก `verifyToken` → B เรียก `verifyToken` (ทับ `lastIdentity`)
→ A เรียก `readProfile` ได้ client ของ B

| ผลที่เป็นไปได้ | ระดับ |
|---|---|
| A อ่าน profile ของตัวเองด้วย client ของ B → RLS คืนศูนย์แถว → **A ถูกปฏิเสธทั้งที่มีสิทธิ์** | **flaky auth** |
| ไต่สิทธิ์ขึ้นไปได้ไหม | **ไม่** — `userId` ส่งเข้ามาตรง ๆ และ RLS บังคับในนามผู้เรียก |

**ไม่ใช่ช่องโหว่ยกระดับสิทธิ์ แต่เป็นบั๊กจริงที่จะโผล่ตอนมีผู้ใช้พร้อมกัน**
และอยู่บนเส้นทางเดียวกับที่ M3 จะต่อยอด → **เสนอให้แก้พร้อมกัน** (ข้อ 2)

### 1.10 ไม่มี graceful shutdown

`server.mjs` จบที่ `server.listen(…)` · **ไม่มี `process.on("SIGTERM")` หรือ `SIGINT`**
วันนี้ไม่เป็นปัญหาเพราะไม่มี resource ที่ต้องปิด · **เมื่อมี pool แล้วจะเป็นปัญหา**

---

## 2. Files that would change

| ไฟล์ | สถานะ | การเปลี่ยน |
|---|---|---|
| `webapi/package.json` | แก้ | เพิ่ม `pg` ลง **`dependencies`** (ไม่ใช่ devDependencies — Dockerfile ใช้ `--omit=dev`) |
| **`webapi/db.mjs`** | **ใหม่** | pool · `resolveLocalUser()` · `closePool()` |
| `webapi/auth.mjs` | แก้ | `resolveAuthorId()` เปลี่ยนจาก "ปฏิเสธเสมอ" เป็นรับ local user ที่ resolver หามาได้ |
| `webapi/server.mjs` | แก้ | สร้าง pool · ส่งเข้า resolver · **เพิ่ม graceful shutdown** · `/healthz` รายงานสถานะ DB |
| **`webapi/Dockerfile`** | แก้ | **`COPY server.mjs auth.mjs db.mjs ./`** |
| `docker-compose.prod.yml` | แก้ | เพิ่ม env 5 ตัว + `depends_on: postgres: service_healthy` |
| `webapi/db.test.mjs` | ใหม่ | ชุดทดสอบ resolver แบบฉีด dependency |
| `webapi/auth.test.mjs` · `server.test.mjs` | แก้ | เพิ่มเคสของ `resolveAuthorId` ที่ทำงานได้แล้ว |
| `db/20-roles.sh` | **ไม่ต้องแก้** | แก้ไปแล้วรอบก่อน (`+46 −0` ยังไม่ commit) |

### 2.1 ⚠ กับดักที่ต้องไม่ลืม — `COPY` ใน Dockerfile

Dockerfile เขียนเตือนไว้เองแล้วสำหรับ `auth.mjs`

> *"`auth.mjs` ต้องมาด้วยเสมอ — `server.mjs` นำเข้ามันตั้งแต่บรรทัดแรก
> ถ้าลืมคัดลอก คอนเทนเนอร์จะพังตอนเริ่มทำงาน ไม่ใช่ตอนมีคนเรียก"*

`db.mjs` มีสมบัติเดียวกันทุกประการ → **ถ้าลืมเพิ่มในบรรทัด `COPY` คอนเทนเนอร์จะพังทันทีที่ขึ้น**
ชุดทดสอบข้อ 7-J ครอบข้อนี้ด้วยการตรวจตัว Dockerfile เอง

---

## 3. Env design

### 3.1 ตัวแปรที่เสนอ

| ตัวแปร | ความลับ? | ค่าที่เสนอ (production) | ที่มา |
|---|---|---|---|
| `ADVISOR_WEB_PASSWORD` | **ใช่** | — **ไม่อยู่ในเอกสารนี้** | เจ้าของกรอกเอง (ข้อ 6) |
| `WEBAPI_DB_HOST` | ไม่ | **`postgres`** | **ยืนยันจาก DNS ในคอนเทนเนอร์จริง** |
| `WEBAPI_DB_PORT` | ไม่ | **`5432`** | ยืนยันจาก TCP จริง |
| `WEBAPI_DB_NAME` | ไม่ | **`course_advisor`** | `current_database()` |
| `WEBAPI_DB_USER` | ไม่ | **`advisor_web`** | role ที่ provision แล้ว |

### 3.2 ทำไมแยกเป็น 5 ตัว ไม่ใช่ `DATABASE_URL` ตัวเดียว

| ทาง | ข้อดี | ข้อเสีย |
|---|---|---|
| `DATABASE_URL` เดียว | สั้น · เป็นที่คุ้นเคย | **รหัสผ่านอยู่ปนกับค่าที่ไม่ลับ** → หลุดง่ายตอน log/ดีบัก · และ **ต้อง percent-encode** อักขระพิเศษในรหัสผ่าน |
| **แยก 5 ตัว (เสนอ)** | **ค่าลับอยู่ตัวเดียว ชัดเจน** · ไม่ต้อง encode อะไร · log ค่าที่ไม่ลับได้โดยไม่เสี่ยง | ยาวกว่า |

> รหัสผ่านที่ใช้จริงเป็น **hex 64 ตัว** (`openssl rand -hex 32`) ซึ่งเลือกไว้ตั้งแต่รอบ
> provision เพื่อเลี่ยงปัญหา percent-encoding พอดี · แต่การแยกตัวแปรยังดีกว่าอยู่ดี
> เพราะทำให้ "อะไรคือความลับ" อ่านออกจาก compose ได้ทันที

### 3.3 กฎการตั้งค่า

| กฎ | วิธีทำ |
|---|---|
| **ห้าม hardcode รหัสผ่าน** | `db.mjs` อ่านจาก `process.env.ADVISOR_WEB_PASSWORD` เท่านั้น |
| ไม่มีค่าเริ่มต้นให้รหัสผ่าน | ไม่มี `?? "…"` — ไม่มีรหัสผ่านก็คือตั้งค่าไม่ครบ |
| ค่าที่ไม่ลับมีค่าเริ่มต้นได้ | `host ?? "postgres"` · `port ?? 5432` ฯลฯ |
| **ห้าม log ค่ารหัสผ่าน** | log ได้แค่ `host:port/db user=…` · **ไม่มีรหัสผ่าน** |
| ตั้งค่าไม่ครบ = ไม่สร้าง pool | `/healthz` รายงาน `dbConfigured: false` · เส้นทางที่ต้องใช้ DB ตอบ 503 |

### 3.4 compose ที่ต้องเพิ่ม (ยังไม่แก้)

```yaml
  webapi:
    depends_on:
      postgres:
        condition: service_healthy      # ยังไม่มีวันนี้ (ข้อ 1.4)
    environment:
      VITE_SUPABASE_URL: ${VITE_SUPABASE_URL}
      VITE_SUPABASE_ANON_KEY: ${VITE_SUPABASE_ANON_KEY}
      GOOGLE_GENERATIVE_AI_API_KEY: ${GOOGLE_GENERATIVE_AI_API_KEY:-}
      # ---- เพิ่มใหม่ ----
      WEBAPI_DB_HOST: postgres
      WEBAPI_DB_PORT: "5432"
      WEBAPI_DB_NAME: course_advisor
      WEBAPI_DB_USER: advisor_web
      ADVISOR_WEB_PASSWORD: ${ADVISOR_WEB_PASSWORD:?ต้องตั้งค่าใน .env}
```

> ใช้ `:?` แบบบังคับได้ที่นี่ **ต่างจาก `db/20-roles.sh`** ที่ต้องเป็นทางเลือก
> เพราะไฟล์นั้นถูก mount โดย compose ทั้งสามชุดรวม e2e · ส่วน service `webapi`
> มีอยู่ใน `docker-compose.prod.yml` ไฟล์เดียว จึงบังคับได้โดยไม่กระทบ dev/e2e

---

## 4. Connection design

### 4.1 ไลบรารีที่เสนอ — **`pg` (node-postgres)**

| เกณฑ์ | `pg` | `postgres` (porsager) | ORM (Prisma/Knex) |
|---|---|---|---|
| ต้อง build native ไหม | **ไม่** (`pg-native` เป็นของเสริมที่ไม่ใช้) | ไม่ | Prisma ต้องมี engine binary |
| เหมาะกับ `node:22-alpine` | **ใช่** | ใช่ | **เพิ่มความซับซ้อนมาก** |
| parameterized query | **ใช่ `$1`** | ใช่ | ใช่ |
| ขนาดและความคุ้นเคย | **มาตรฐานโดยพฤตินัย** | เล็กกว่า แต่คนรู้จักน้อยกว่า | เกินจำเป็นสำหรับ **query เดียว** |

**เลือก `pg`** — งานทั้งหมดของ M3 คือ query เดียวที่อ่าน 3 คอลัมน์ ORM ไม่คุ้ม

### 4.2 pool ควรสร้างตรงไหน

**สร้างครั้งเดียวตอน module load ใน `webapi/db.mjs` แล้วฉีดเข้า resolver**
— รูปแบบเดียวกับ `authDeps` ที่ `server.mjs` ทำอยู่แล้ว

| ทางเลือก | ตัดสิน |
|---|---|
| สร้าง pool ใหม่ทุกคำขอ | **ไม่** — เสียเวลา handshake ทุกครั้ง และ connection รั่ว |
| **pool เดียวระดับ module** | **เลือก** — `pg.Pool` ออกแบบมาให้ใช้แบบนี้ · ปลอดภัยกับ concurrency (ต่างจากข้อ 1.9) |
| singleton ซ่อนใน resolver | ไม่ — ทดสอบยาก · ฉีด dependency ไม่ได้ |

### 4.3 ขนาดและเวลา — อิงตัวเลขจริงของ production

ตรวจแล้ว

| ค่า | production |
|---|---|
| `max_connections` | **100** |
| `superuser_reserved_connections` | **3** → ใช้ได้จริง **97** |
| connection ที่ใช้อยู่ตอนนี้ | **8** (ของ `course_advisor` = 3 · `advisor_api` = 1) |
| `statement_timeout` ค่าตั้งต้น | **0 = ไม่จำกัด** |
| `idle_in_transaction_session_timeout` | **0 = ไม่จำกัด** |

ค่าที่เสนอ

```js
new Pool({
  host, port, database, user, password,
  max: 5,                          // 5 จาก 97 — เหลือที่ให้ backend/ingest มาก
  min: 0,                          // ไม่จองไว้ตอนไม่มีทราฟฟิก
  connectionTimeoutMillis: 5_000,  // ต่อไม่ได้ใน 5 วิ = ยอมแพ้ ไม่ค้าง
  idleTimeoutMillis: 30_000,       // คืน connection ที่ว่างนานกลับไป
  statement_timeout: 5_000,        // query ค้างต้องตาย ไม่ใช่ถือ connection ไว้
  query_timeout: 5_000,
  idle_in_transaction_session_timeout: 10_000,
  application_name: "webapi",      // ให้เห็นใน pg_stat_activity ว่าใครต่อมา
})
```

| ค่า | เหตุผล |
|---|---|
| **`max: 5`** | `webapi` รับแค่ 5 เส้นทาง อยู่หลัง Caddy ทราฟฟิกต่ำ · และ resolver ใช้ connection แค่ชั่วขณะต่อคำขอ |
| **`statement_timeout`** | ค่าตั้งต้นของเซิร์ฟเวอร์เป็น 0 → ถ้าไม่ตั้งเอง query ที่ค้างจะถือ connection ไว้ตลอดกาล |
| **`application_name`** | ทำให้สืบได้ว่า connection ไหนเป็นของ `webapi` ตอนดู `pg_stat_activity` |
| **ไม่ใช้ `postgres` superuser** | ใช้ `advisor_web` เท่านั้น — ตรวจบังคับในชุดทดสอบ |
| **ไม่ใช้ `advisor_api`** | คนละสิทธิ์คนละหน้าที่ · `advisor_api` อ่าน `public.users` ได้ทั้งตารางรวม `email` |

### 4.4 Graceful shutdown

วันนี้ **ไม่มีเลย** (ข้อ 1.10) · เสนอ

```js
let closing = false;
async function shutdown(signal) {
  if (closing) return;              // SIGTERM ซ้ำไม่ทำงานซ้อน
  closing = true;
  console.log(`[webapi] ได้รับ ${signal} — ปิดอย่างเรียบร้อย`);
  server.close(async () => {        // หยุดรับคำขอใหม่ รอคำขอที่ค้างอยู่ให้จบ
    await closePool();              // แล้วค่อยคืน connection ให้ PostgreSQL
    process.exit(0);
  });
  setTimeout(() => process.exit(1), 10_000).unref();   // ไม่ยอมค้างเกิน 10 วินาที
}
process.on("SIGTERM", () => shutdown("SIGTERM"));
process.on("SIGINT",  () => shutdown("SIGINT"));
```

| กลไก | เหตุผล |
|---|---|
| `server.close()` ก่อน `pool.end()` | ปิด pool ก่อนจะทำให้คำขอที่กำลังทำงานอยู่พัง |
| ตัวกัน 10 วินาที | Docker ส่ง `SIGKILL` หลัง `stop_grace_period` (ตั้งต้น 10 วิ) อยู่แล้ว — ออกเองก่อนดีกว่าถูกฆ่า |
| กัน signal ซ้ำ | `docker compose down` อาจส่งซ้ำ |

### 4.5 `/healthz` — เพิ่มสถานะ DB แบบไม่ทำให้ container ตาย

```json
{
  "status": "ok",
  "authConfigured": true,
  "dbConfigured": true,
  "db": "up",
  "routes": [ … ]
}
```

⚠ **`status` ต้องไม่กลายเป็น `error` เพราะ DB ล่ม** — Docker `HEALTHCHECK` ตัดสินจาก
exit code ของคำสั่งนี้ · ถ้าทำให้ `/healthz` ล้มเมื่อ DB ล่ม คอนเทนเนอร์จะถูกมองว่า
unhealthy ทั้งที่ **สองเส้นทางสาธารณะยังทำงานได้ปกติ** (ไม่ได้ใช้ DB เลย)

→ รายงาน `db` เป็นข้อมูลประกอบ · ให้ `status` สะท้อนเฉพาะว่า HTTP server ยังรับคำขอได้

---

## 5. Identity resolver design

### 5.1 ลำดับการทำงาน

```
Authorization: Bearer <JWT>
      │
      ├─ supabase.auth.getUser(token)      -> supabaseUserId        (มีแล้ว)
      │
      ├─ user_profiles.role/status         -> role, status          (มีแล้ว)
      │
      └─ PostgreSQL  (ใหม่ใน M3)
             SELECT id, is_active, supabase_user_id
             FROM public.users
             WHERE supabase_user_id = $1
                                              -> localUserId
```

### 5.2 Query — parameterized เท่านั้น

```js
const SQL = `
  SELECT id, is_active, supabase_user_id
  FROM public.users
  WHERE supabase_user_id = $1
`;
const { rows } = await pool.query(SQL, [supabaseUserId]);
```

| ข้อกำหนด | วิธี |
|---|---|
| **parameterized** | `$1` · **ห้ามต่อสตริงเข้า SQL เด็ดขาด** |
| ค่าที่ส่งเข้าไป | **`supabaseUserId` ที่ได้จาก `auth.getUser()` เท่านั้น** ไม่ใช่จาก body หรือ query string |
| ชนิด | คอลัมน์เป็น `uuid` → PostgreSQL cast เอง · ค่าที่ไม่ใช่ uuid จะได้ error ไม่ใช่ผลลัพธ์ปลอม |

### 5.3 เงื่อนไขการยอมรับ — **fail closed ทุกทาง**

| กรณี | ผลลัพธ์ | เหตุผล |
|---|---|---|
| **แถว = 1 และ `is_active = true`** | ✅ คืน `localUserId` | ทางเดียวที่ผ่าน |
| **แถว = 0** | ❌ `ACCOUNT_NOT_LINKED` | ผู้ใช้ Supabase คนนี้ยังไม่ถูกจับคู่ |
| **แถว > 1** | ❌ `MAPPING_AMBIGUOUS` | ไม่ควรเกิด (มี partial unique index) แต่ **ต้องไม่เดาว่าเอาแถวไหน** |
| **`is_active = false`** | ❌ `ACCOUNT_INACTIVE` | บัญชีถูกปิดฝั่งเรา |
| **query ล้ม / DB ล่ม** | ❌ `IDENTITY_LOOKUP_FAILED` | ไม่รู้ = ไม่ปล่อยผ่าน |
| **ไม่ได้ตั้งค่า DB** | ❌ `DATABASE_NOT_CONFIGURED` | ตั้งค่าไม่ครบ = เขียนไม่ได้ |

### 5.4 ⚠ สิ่งที่ห้ามทำ — เขียนเป็นข้อตรวจในชุดทดสอบ

| ห้าม | ทำไม |
|---|---|
| **fallback ด้วย email** | อีเมลตรงกันไม่ได้แปลว่าเป็นคนเดียวกัน · และ `advisor_web` **อ่าน `email` ไม่ได้อยู่แล้ว** (บังคับด้วยสิทธิ์ ไม่ใช่แค่ด้วยวินัย) |
| **fallback เป็น admin** | ยัดเจ้าของผิดคน — ข้อห้ามเดียวกับตอน migration |
| **ใช้ Supabase UUID เป็น local author id ตรง ๆ** | เป็น uuid คนละชุด จะชี้ไปผู้ใช้ที่ไม่มีอยู่ หรือชี้ผิดคน |
| **สร้างผู้ใช้ใหม่อัตโนมัติ** | `advisor_web` **ไม่มีสิทธิ์ INSERT** อยู่แล้ว |
| **เชื่อ `created_by`/`updated_by` จาก body** | `stripAuthorFields()` ตัดทิ้งอยู่แล้ว |

> **ข้อสังเกตสำคัญ**: ข้อห้ามสามข้อแรกไม่ได้พึ่งแค่โค้ด — **สิทธิ์ของ `advisor_web`
> บังคับไว้อีกชั้น** · ต่อให้มีใครเขียนโค้ด fallback ด้วย email ในอนาคต query นั้น
> จะถูกฐานข้อมูลปฏิเสธด้วย `permission denied` (พิสูจน์แล้วข้อ 6.2)

### 5.5 Error behavior ที่เสนอ

| reason | HTTP | ข้อความถึงผู้เรียก | log |
|---|---|---|---|
| `ACCOUNT_NOT_LINKED` | **403** | `บัญชีนี้ยังไม่ได้เชื่อมกับผู้ใช้ในระบบ` | เส้นทาง + reason · **ไม่มี uuid** |
| `ACCOUNT_INACTIVE` | **403** | `บัญชีนี้ถูกปิดการใช้งาน` | เส้นทาง + reason |
| `MAPPING_AMBIGUOUS` | **500** | `internal error` | **`console.error` — ต้องมีคนมาดู** |
| `IDENTITY_LOOKUP_FAILED` | **503** | `ระบบฐานข้อมูลไม่พร้อมใช้งานชั่วคราว` | `console.error` |
| `DATABASE_NOT_CONFIGURED` | **500** | `internal error` | `console.error` ตอนเริ่มทำงานด้วย |

| การตัดสิน | เหตุผล |
|---|---|
| **403 ไม่ใช่ 401** สำหรับ not-linked | ผู้เรียก **ยืนยันตัวตนสำเร็จแล้ว** · ปัญหาคือสิทธิ์/การเชื่อมบัญชี · 401 จะชวนให้ไป login ใหม่ซึ่งไม่ช่วยอะไร |
| **503 ไม่ใช่ 500** สำหรับ DB ล่ม | บอกว่า "ลองใหม่ได้" ซึ่งเป็นความจริง |
| **ไม่บอกว่า uuid ไหนไม่เจอ** | ไม่ยืนยันการมีอยู่ของบัญชีให้คนนอก |

### 5.6 ผลต่อ `resolveAuthorId()` ใน `auth.mjs`

วันนี้ฟังก์ชันนี้ **ปฏิเสธเสมอ** พร้อมคอมเมนต์ว่า

> *"ห้ามแก้ฟังก์ชันนี้ให้คืนค่าอะไรจนกว่าจะมีการออกแบบ mapping ที่ได้รับอนุมัติ"*

**เงื่อนไขนั้นครบแล้ว** — `S1_MAPPING_APPLIED_VERIFIED` · M3 คือรอบที่ปลดล็อก
โครงของ `authorFieldsFor()` รองรับไว้อยู่แล้ว (เรียก `resolveAuthorId(context)` และ
ส่งต่อ `{ ok: false }` ตามเดิมถ้าไม่ผ่าน) → **แก้จุดเดียว ไม่ต้องรื้อ**

### 5.7 ขอบเขตที่ต้องพูดให้ชัด — M3 **ยังไม่ทำให้มีใครเขียนข้อมูลได้**

ทั้ง 5 เส้นทางที่ `webapi` รับผิดชอบวันนี้ **ไม่มีเส้นทางใดเขียน `web.site_courses`
หรือ `web.news`** · `authorFieldsFor()` จึงยังไม่มีผู้เรียก

→ M3 ทำให้ **เครื่องมือพร้อม** · การสร้าง endpoint เขียนข้อมูลจริงเป็นรอบแยก
(ตรงกับ `G3_API_ENFORCEMENT_PENDING_B1` ที่ค้างอยู่ใน `web_schema_check.py`)

---

## 6. Privilege compatibility — **ตรวจบน production จริงแล้ว**

READ-ONLY ภายใต้ `default_transaction_read_only=on`

### 6.1 catalog — 10 ข้อ ผ่านครบ

| ข้อตรวจ | ได้ | คาดหวัง |
|---|---|---|
| `has_column_privilege` `id` | **true** | true |
| `has_column_privilege` `is_active` | **true** | true |
| `has_column_privilege` `supabase_user_id` | **true** | true |
| `has_column_privilege` `email` | **false** | false |
| `has_column_privilege` `password_hash` | **false** | false |
| `has_table_privilege` SELECT | **false** | false |
| `has_table_privilege` UPDATE / INSERT / DELETE | **false ทั้งสาม** | false |
| `has_any_column_privilege` UPDATE | **false** | false |

### 6.2 ⚠ พิสูจน์เชิงพฤติกรรม — สวมบทเป็น `advisor_web` บน production

| คำสั่งที่ยิงจริง | ผล |
|---|---|
| **`SELECT id, is_active, supabase_user_id FROM public.users`** | ✅ **ทำได้** |
| **query ของ resolver (`WHERE supabase_user_id = …`)** | ✅ **คืน 1 แถวพอดี** |
| สามคอลัมน์มีค่าครบ | ✅ |
| แถวที่เจอ `is_active` | ✅ **true** |
| **UUID ที่ไม่มีในระบบ** | ✅ **0 แถว** (fail closed ได้จริง) |
| จำนวน mapping ทั้งหมด | ✅ **1** → ไม่มีทางได้ > 1 แถว |
| `SELECT email` | ✅ **`permission denied for table users`** |
| `SELECT password_hash` | ✅ **ปฏิเสธ** |
| `SELECT full_name` | ✅ **ปฏิเสธ** |
| `SELECT is_admin` | ✅ **ปฏิเสธ** |
| **`SELECT *`** | ✅ **ปฏิเสธ** |

### 6.3 ข้อที่ยังพิสูจน์เชิงพฤติกรรมบน production ไม่ได้ — พูดให้ตรง

`UPDATE` และ `DELETE` ถูกปฏิเสธด้วยข้อความ **`cannot execute UPDATE in a read-only transaction`**
ซึ่งมาจาก `default_transaction_read_only` **ไม่ใช่จากสิทธิ์**

→ **ข้อตรวจนั้นผ่านด้วยเหตุผลที่ผิด** · บน production จึงยืนยันได้จาก **catalog เท่านั้น**
(`has_table_privilege UPDATE` = false)

หลักฐานเชิงพฤติกรรมของ `UPDATE`/`DELETE` มาจาก **คอนเทนเนอร์ทดสอบรอบ migration 006**
ซึ่งยิง `UPDATE public.users … WHERE false` ในฐานะ `advisor_web` แล้วได้ `42501`
(ชุดทดสอบ 99 ข้อ · `eval/web_identity_mapping_check.py`)

การพิสูจน์บน production ต้องรันนอก read-only transaction ซึ่ง **อยู่นอกขอบเขตรอบนี้**

---

## 6.4 ⚠ `public.users` โตจาก 198 เป็น 201 ระหว่างรอบนี้ — ไม่ใช่ความเสียหาย

ตรวจพบตอนยืนยันสถานะท้ายรอบ

| ข้อมูล | ค่า |
|---|---|
| จำนวนแถวตอนนี้ | **201** (เดิม 198 ตอนรอบ S1 mapping) |
| สร้างใน 3 วันล่าสุด | **3 แถว** |
| แถวใหม่สุดสร้างเมื่อ | **2026-10-04 06:06 +07** |
| **mapping ที่ผูกไว้** | **1** — ไม่เปลี่ยน |
| **admin** | **1** — ไม่เปลี่ยน |
| hash อีเมลที่ไม่ซ้ำกัน | **201** จาก 201 — ยังไม่มีการชน |

เป็นการสมัครใช้งานตามปกติของระบบที่เปิดใช้จริง · ไม่มีความเกี่ยวข้องกับงานชุดนี้
(รอบ S1 mapping แตะแค่ 1 แถว 1 คอลัมน์ และผู้ใช้ใหม่สร้างหลังจากนั้น)

### ผลที่ต้องรู้ — ข้อตรวจที่ตรึงเลข 198 ไว้จะไม่ผ่านอีกต่อไป

| ไฟล์ | ข้อที่ตรึงไว้ |
|---|---|
| `s1_preapply.sql` (scratchpad) | `P02_users_rows` คาดหวัง `198` |
| `post006.sql` (scratchpad) | `Q01_users_rows` · `Q08_users_rows` คาดหวัง `198` |
| เอกสาร 006 และ S1 | บันทึก 198 ไว้เป็นค่า ณ เวลานั้น |

**เอกสารเดิมไม่ผิด** — มันบันทึกค่า ณ เวลาที่ตรวจ ซึ่งถูกต้องตอนนั้น
แต่ **ถ้ารันสคริปต์เดิมซ้ำวันนี้จะเห็น `198~201` แล้วอาจเข้าใจผิดว่าเสียหาย**

→ ข้อตรวจที่ควรใช้ต่อไปคือสิ่งที่**ไม่ขึ้นกับจำนวนผู้ใช้ทั้งหมด**

```
mapping ที่ไม่ใช่ NULL              = 1
hash ของ S1 จับคู่ได้               = 1 แถว
แถวที่ผูกไว้ยังเป็นแถวเดิม            id prefix 4ad26503
hash อีเมลที่ไม่ซ้ำกัน               = จำนวนแถวทั้งหมด (ไม่มีการชน)
```

สามข้อแรกเป็นสิ่งที่ resolver พึ่งพาจริง · จำนวนแถวทั้งหมด**ไม่เกี่ยวกับความถูกต้องของ
resolver เลย** เพราะ query กรองด้วย `supabase_user_id` ไม่ใช่ด้วยจำนวน

---

## 7. Test plan

### 7.1 ชุดทดสอบใหม่ `webapi/db.test.mjs` — ไม่ต้องมี DB จริง

ใช้การฉีด dependency แบบเดียวกับ `auth.test.mjs` ที่มีอยู่แล้ว (52 เทสต์ผ่าน)

| # | เคส | วิธี | ต้องได้ |
|---|---|---|---|
| **C** | S1 UUID คืน local user หนึ่งคน | pool ปลอมคืน 1 แถว `is_active: true` | `{ ok: true, localUserId }` |
| **D** | UUID ที่ไม่รู้จัก | pool ปลอมคืน 0 แถว | `ACCOUNT_NOT_LINKED` · **ไม่คืน id** |
| **E** | ผู้ใช้ถูกปิด | คืน 1 แถว `is_active: false` | `ACCOUNT_INACTIVE` |
| — | คืน 2 แถว | pool ปลอมคืน 2 แถว | `MAPPING_AMBIGUOUS` · **ไม่เลือกแถวแรก** |
| — | pool โยน error | pool ปลอม throw | `IDENTITY_LOOKUP_FAILED` · ไม่รั่ว stack ออกไปหาผู้เรียก |
| **F** | **input แบบ SQL injection** | ส่ง `"' OR '1'='1"` และ `"' OR 1=1 --"` | **ค่าถูกส่งเป็น parameter เสมอ** — ตรวจว่า `pool.query` ถูกเรียกด้วย `(SQL, [value])` และ **SQL ที่ส่งไม่เปลี่ยนรูป** |
| — | ไม่มี fallback email | ตรวจว่า SQL **ไม่มีคำว่า `email`** เลย | regex บนสตริง query |
| **I** | ปิด pool สะอาด | เรียก `closePool()` สองครั้ง | เรียก `pool.end()` **ครั้งเดียว** · ไม่โยน error |

### 7.2 ชุดทดสอบที่ต้องมีฐานข้อมูลจริง — คอนเทนเนอร์ทิ้ง

ต่อยอดจากฮาร์เนสของ `eval/web_identity_mapping_check.py` (schema → 001–006 → role)

| # | เคส | ต้องได้ |
|---|---|---|
| **A** | ต่อด้วย `advisor_web` + รหัสผ่านถูก | ต่อได้ · `SELECT 1` ผ่าน |
| **B** | **รหัสผ่านผิด** | **ถูกปฏิเสธ** `password authentication failed` · ⚠ **ต้องต่อผ่าน IP ของคอนเทนเนอร์ ไม่ใช่ `127.0.0.1`** เพราะ `pg_hba` ของ image ตั้ง `trust` ให้ loopback (บทเรียนจากรอบ provision) |
| **G** | `advisor_web` อ่าน `email` | **`42501`** |
| **H** | `advisor_web` สั่ง `UPDATE public.users` | **`42501`** |
| — | ใช้ `postgres` หรือ `advisor_api` แทน | ชุดทดสอบ **ต้องล้ม** ถ้าโค้ดเผลอใช้ user อื่น |

### 7.3 ไม่ถดถอย

| # | เคส | วิธี |
|---|---|---|
| **J** | เทสต์ Supabase auth เดิมไม่พัง | `cd webapi && npm test` ต้องยังผ่าน **52/52** |
| — | `/healthz` ยังตอบ 200 เมื่อ **ไม่ได้ตั้งค่า DB** | เส้นทางสาธารณะต้องไม่พังเพราะ DB |
| — | เส้นทาง `PUBLIC` ยังทำงานเมื่อ **DB ล่ม** | ไม่เรียก resolver เลย |
| — | **Dockerfile `COPY` มี `db.mjs`** | อ่านไฟล์ Dockerfile แล้ว assert — กันกับดักข้อ 2.1 |
| — | `pg` อยู่ใน `dependencies` ไม่ใช่ `devDependencies` | อ่าน `package.json` แล้ว assert |

### 7.4 ยังไม่ทำในรอบ implementation

**ไม่ยิง production write** · การทดสอบที่ต้องเขียนข้อมูลใช้คอนเทนเนอร์ทิ้งเท่านั้น

---

## 8. Rollout plan

### 8.1 ⚠ deploy นี้ไม่ใช่ "เพิ่มแค่ pool"

image ที่รันอยู่เป็นของ **2026-09-22** · การ deploy M3 จะพาขึ้นไปพร้อมกัน

| สิ่งที่จะขึ้นไปด้วย | ผลที่ต้องเฝ้าดู |
|---|---|
| **authorization foundation (`cf4fb16`)** | ด่านกลางเริ่มบังคับ — เส้นทาง `/api/admin/*` จะถูกตรวจ **สองชั้น** (ด่านกลาง + `requireAdminUser` เดิม) |
| `validateRouteTable` + `process.exit(1)` | ถ้าตาราง ROUTES ไม่ครบ **คอนเทนเนอร์จะไม่ขึ้นเลย** |
| `/healthz` รูปแบบใหม่ | มี `authConfigured` · `routes[].level` เพิ่มมา |
| pool + resolver ของ M3 | ของใหม่จริง ๆ ของรอบนี้ |

→ **ต้องถือว่าเป็น deploy ที่มีความเสี่ยงระดับ "เปลี่ยนพฤติกรรมการตรวจสิทธิ์"
ไม่ใช่ระดับ "เพิ่มไลบรารี"**

### 8.2 ลำดับที่เสนอ

```
1. เจ้าของเพิ่ม ADVISOR_WEB_PASSWORD ลง production .env   (ข้อ 8.3)
2. commit โค้ด M3 + ของค้างทั้งหมด                        (ต้องขออนุมัติ)
3. คัดลอก webapi/api/ จากรีโปหน้าเว็บมาวาง                 (ข้อ 1.6)
4. build image ใหม่                                       docker compose build webapi
5. ยืนยันว่า image ใหม่มี db.mjs และ auth.mjs จริง          docker run --rm … ls /app
6. docker compose up -d webapi                            (ไม่แตะ service อื่น)
7. ตรวจ /healthz  -> authConfigured:true · dbConfigured:true · db:"up"
8. ตรวจ pg_stat_activity -> เห็น application_name = webapi
9. ยิงเส้นทาง PUBLIC 2 เส้นทาง -> ต้องตอบ 200 เหมือนเดิม
10. เฝ้าดู log 10 นาที
```

> ขั้นที่ 5 สำคัญเพราะเป็นกับดักที่ Dockerfile เตือนไว้เอง (ข้อ 2.1)
> และบทเรียน **"deploy ต้อง build image ใหม่"** — `scp` แล้ว restart จะรันโค้ดเก่า

### 8.3 ขั้นเพิ่ม `ADVISOR_WEB_PASSWORD` ลง production `.env`

**ยังไม่ทำ** · ออกแบบตามแบบเดียวกับ S1 UUID — **เจ้าของรันเองบนเซิร์ฟเวอร์**

**ขั้น A — วางบรรทัดนี้บรรทัดเดียว**

```bash
read -rsp 'ADVISOR_WEB_PASSWORD: ' AWP && echo; echo "ความยาว = ${#AWP}  (ต้องเป็น 64)"
```

**ขั้น B — ได้ 64 แล้ววางก้อนนี้**

```bash
cd ~/course-advisor-system
[ ${#AWP} -eq 64 ] && grep -q '^ADVISOR_WEB_PASSWORD=' .env \
  && echo 'มีอยู่แล้ว — ไม่เขียนทับ' \
  || { [ ${#AWP} -eq 64 ] && printf 'ADVISOR_WEB_PASSWORD=%s\n' "$AWP" >> .env && echo 'เพิ่มแล้ว'; }
unset AWP
grep -c '^ADVISOR_WEB_PASSWORD=' .env     # ต้องได้ 1
ls -l .env                                 # ต้องยังเป็น 600 ubuntu:ubuntu
```

| กลไกป้องกัน | ทำอะไร |
|---|---|
| `read -rsp` | ไม่แสดงค่า · ไม่เข้า history |
| ตรวจความยาว 64 | รหัสผ่านเป็น hex 64 ตัว — จับกรณีวางซ้ำหรือวางขาด |
| **ตรวจว่ามีอยู่แล้วก่อนเขียน** | **ไม่เขียนทับของเดิมโดยไม่ตั้งใจ** |
| `>>` ไม่ใช่ `>` | ไม่ทับทั้งไฟล์ |
| `grep -c` ท้ายสุด | ต้องได้ **1** — ไม่ใช่ 0 (ไม่ได้เพิ่ม) และไม่ใช่ 2 (เพิ่มซ้ำ) |

**ห้ามอ่านค่าเดิมออกมาดู · ห้าม `cat .env`**

### 8.4 ตรวจหลัง deploy

| ข้อตรวจ | ต้องได้ |
|---|---|
| `/healthz` → `authConfigured` | `true` |
| `/healthz` → `dbConfigured` · `db` | `true` · `"up"` |
| `/healthz` → `routes[].level` | ครบ 5 เส้นทางพร้อมระดับ |
| `pg_stat_activity` | เห็น `application_name = webapi` · usename = **`advisor_web`** |
| จำนวน connection ของ `advisor_web` | **ไม่เกิน 5** |
| เส้นทาง `PUBLIC` 2 เส้นทาง | **200 เหมือนเดิม** |
| log | ไม่มี token ไม่มีอีเมล ไม่มี uuid ไม่มีรหัสผ่าน |

---

## 9. Rollback plan

### 9.1 ถอนกลับที่ระดับ image — ทางหลัก

```bash
docker compose -f docker-compose.prod.yml up -d --no-deps webapi   # ด้วย image เดิม
```

| | |
|---|---|
| ต้องทำอะไรกับฐานข้อมูลไหม | **ไม่** — M3 **ไม่แก้ schema ไม่แก้ข้อมูล ไม่แก้สิทธิ์** |
| ต้องถอน migration ไหม | **ไม่** — 005/006 ยังอยู่ และไม่มีใครใช้ก็ไม่เป็นไร |
| ต้องลบ `ADVISOR_WEB_PASSWORD` ไหม | **ไม่จำเป็น** — ตัวแปรที่ไม่มีคนอ่านไม่ทำอะไร |
| ข้อมูลเสียหายไหม | **ไม่มีทาง** — `advisor_web` ไม่มีสิทธิ์เขียน `public.users` เลย |

**ต้องเก็บ image เดิมไว้ก่อน build ใหม่** — `docker tag` ของเดิมเป็น `webapi:before-m3`

### 9.2 ถอนกลับบางส่วน — ปิดการใช้ DB โดยไม่ rollback image

ลบ `ADVISOR_WEB_PASSWORD` ออกจาก `.env` แล้ว restart → `dbConfigured: false`
→ เส้นทาง `PUBLIC` ยังทำงาน · เส้นทางที่ต้องใช้ resolver ตอบ 500/503

**ใช้ได้เฉพาะถ้า compose ไม่ได้ตั้ง `:?` บังคับ** — ถ้าตั้งไว้ service จะไม่ขึ้น
→ **ตัดสิน: ตั้ง `:?` บังคับ** เพราะสถานะ "ขึ้นแต่ใช้ DB ไม่ได้" ตรวจยากกว่า
"ไม่ขึ้นเลยพร้อมข้อความชัดเจน" · การถอนกลับให้ใช้ทางข้อ 9.1 แทน

### 9.3 ความเสี่ยงของการถอนกลับเอง

| ความเสี่ยง | ระดับ |
|---|---|
| กลับไป image เก่า = **ด่าน authorization กลางหายไปอีกครั้ง** | **ต่ำ** — handler ยังตรวจเองอยู่ (ข้อ 1.5) |
| ไม่ได้เก็บ image เดิมไว้ | **สูงถ้าลืม** → ขั้นที่ต้องทำก่อน build คือ `docker tag` |

---

## 10. Risks

| # | ความเสี่ยง | ระดับ | สิ่งที่รองรับ |
|---|---|---|---|
| 1 | **ลืมใส่ `db.mjs` ใน `COPY` ของ Dockerfile** | **สูงถ้าลืม** | คอนเทนเนอร์พังตอนขึ้นทันที (เห็นเร็ว) · เทสต์อ่าน Dockerfile assert ไว้ (7.3) |
| 2 | **deploy นี้พา authorization ขึ้นไปด้วย** | **กลาง** | ขั้น 8.4 ตรวจเส้นทาง PUBLIC และ `/healthz` · handler เดิมยังตรวจเองอยู่ |
| 3 | `webapi` ขึ้นก่อน postgres พร้อม | **ต่ำ** | เพิ่ม `depends_on: service_healthy` · และ pool จะ retry เองตอนมีคำขอ |
| 4 | connection รั่วจนเต็ม | **ต่ำ** | `max: 5` จาก 97 · `idleTimeoutMillis` · `statement_timeout` · graceful shutdown |
| 5 | **ไม่มี `package-lock.json` → build ได้ `pg` คนละรุ่นกับที่ทดสอบ** | **กลาง** | เสนอให้ commit lock file พร้อมรอบ implementation |
| 6 | **บั๊ก `lastIdentity` ใช้ร่วมข้ามคำขอ (ข้อ 1.9)** | **กลาง** | ยังไม่ถูกแก้ · **เสนอให้แก้ในรอบเดียวกัน** เพราะอยู่บนเส้นทางเดียวกัน |
| 7 | `/healthz` ล้มเพราะ DB ล่ม แล้ว container ถูกมองว่า unhealthy | **ต่ำ** | ออกแบบให้ `status` ไม่ขึ้นกับ DB (ข้อ 4.5) |
| 8 | รหัสผ่านหลุดลง log | **ต่ำ** | ไม่ log ค่า · `log_statement = none` บน production · แยกตัวแปรไม่ปนใน URL |
| 9 | `webapi/api/` ไม่ถูกคัดลอกก่อน build | **กลาง** | ขั้นที่ 3 ของ rollout · และขั้นที่ 5 ตรวจ image ก่อน up |

---

## 11. Final classification

# `M3_DESIGN_READY`

| เกณฑ์ | ผล |
|---|---|
| ตรวจ architecture จริงก่อนออกแบบ ไม่ได้เดา | ✅ hostname · port · network · node version · env — จากคอนเทนเนอร์จริง |
| ตอบได้ว่ามี PG client หรือยัง | ✅ **ยังไม่มี** · เลือก `pg` พร้อมเหตุผลเทียบทางเลือก |
| ออกแบบ env โดยไม่ hardcode รหัสผ่าน | ✅ แยกค่าลับออกจากค่าไม่ลับ |
| ออกแบบ pool พร้อมตัวเลขอิงของจริง | ✅ `max_connections` 100 · ใช้อยู่ 8 → `max: 5` |
| graceful shutdown | ✅ ออกแบบแล้ว (วันนี้ยังไม่มีเลย) |
| identity resolver fail closed ทุกทาง | ✅ 6 กรณี · ห้าม fallback 5 ข้อ |
| **privilege compatibility** | ✅ **พิสูจน์บน production จริง** — resolver คืน 1 แถว · `email` ถูกปฏิเสธ |
| test plan ครบ A–J | ✅ แยกเป็นไม่ต้องมี DB / ต้องมี DB / ไม่ถดถอย |
| rollout · rollback · risks | ✅ |

### 11.1 ทำไมไม่ใช่ `M3_BLOCKED`

ไม่มีสิ่งใดขวางการ **ออกแบบ** · สิ่งที่ยังขาดคือ `ADVISOR_WEB_PASSWORD` ใน production `.env`
ซึ่งเป็น **ขั้นแรกของ rollout** ที่ออกแบบไว้แล้วในข้อ 8.3 ไม่ใช่ตัวขวางการออกแบบ

---

## 12. Exact next step

```
1. Owner อ่านและอนุมัติแบบนี้
     - ยืนยันว่าเอา pg ไม่ใช่ตัวอื่น
     - ยืนยันว่าเอาแบบแยก 5 ตัวแปร ไม่ใช่ DATABASE_URL เดียว
     - ตัดสินว่าจะแก้บั๊ก lastIdentity (ข้อ 1.9) ในรอบเดียวกันไหม

2. อนุมัติรอบ implementation
     - เขียน db.mjs · แก้ auth.mjs/server.mjs/Dockerfile/package.json
     - เขียนชุดทดสอบตามข้อ 7
     - ทดสอบในคอนเทนเนอร์ทิ้ง  ยังไม่แตะ production

3. อนุมัติรอบ .env  (ข้อ 8.3 — เจ้าของรันเอง)

4. อนุมัติรอบ deploy  (ข้อ 8.2 — เป็น deploy ที่พา authorization ขึ้นด้วย)

5. รอบแยก: endpoint ที่เขียนข้อมูลจริง + ปิด G3_API_ENFORCEMENT_PENDING_B1
```

### 12.1 ของค้างที่ยังไม่ commit — รวมทุกอย่างที่ผ่านมา

```
db/20-roles.sh                              +46 −0   (รอบ provision)
db/migrations/006_web_identity_mapping.sql  ใหม่      applied บน production แล้ว
eval/web_identity_mapping_check.py          ใหม่      99 ข้อผ่าน
docs/  (6 ฉบับ)                              ใหม่
```

**HEAD ยังเป็น `cf4fb16`** — ยังไม่มี commit ใดตั้งแต่เริ่มงานชุดนี้

---

## บันทึกการเข้าถึงข้อมูลในรอบนี้

| ระบบ | การเข้าถึง |
|---|---|
| production PostgreSQL | **`SELECT` อย่างเดียว** · `SET ROLE advisor_web` เพื่อทดสอบ query ของ resolver · ทั้งหมดใต้ `default_transaction_read_only=on` |
| production containers | **อ่านอย่างเดียว** — `docker inspect` · `ls` · `grep` ในไฟล์ของ image · `/healthz` · DNS/TCP probe |
| production `.env` | **ไม่ได้อ่านในรอบนี้** |
| Supabase | **ไม่ได้เข้าถึงเลย** |
| ไฟล์ในรีโป | **อ่านอย่างเดียว** · สร้างเอกสารนี้ไฟล์เดียว |
| git | ไม่ commit ไม่ push |

---

## STOP

# `M3_DESIGN_READY`

```
hostname / port       postgres:5432   ยืนยันด้วย DNS และ TCP จากในคอนเทนเนอร์ webapi
PG client             ยังไม่มี -> เสนอ pg (node-postgres)
pool                  max 5 จาก 97 ที่ใช้ได้ · timeout ครบ · application_name=webapi
graceful shutdown     วันนี้ไม่มีเลย -> ออกแบบแล้ว
resolver              parameterized · 1 แถวเท่านั้น · fail closed 6 กรณี · ห้าม fallback 5 ข้อ
privilege             พิสูจน์บน production แล้ว — อ่าน 3 คอลัมน์ได้ · email ถูกปฏิเสธ
```

**ไม่แก้ production · ไม่ deploy · ไม่ restart · ไม่ commit**

⚠ สองเรื่องที่พบระหว่างตรวจและควรตัดสินใจพร้อมกัน

1. **image ของ `webapi` ที่รันอยู่เป็นของ 2026-09-22** — `cf4fb16` ยังไม่เคย deploy
   → การ deploy M3 จะพา authorization foundation ขึ้นไปด้วยเป็นครั้งแรก
   (production ไม่ได้เปิดโล่ง — handler ตรวจเองอยู่ แต่ต้องรู้ว่าจะมีสองชั้น)
2. **บั๊ก `lastIdentity` ใช้ตัวแปรร่วมข้ามคำขอใน `createRuntimeDeps`** (ข้อ 1.9)
   → ทำให้ auth แกว่งเมื่อมีผู้ใช้พร้อมกัน · ไม่ใช่ช่องโหว่ยกระดับสิทธิ์
   → เสนอให้แก้ในรอบ implementation เดียวกัน
