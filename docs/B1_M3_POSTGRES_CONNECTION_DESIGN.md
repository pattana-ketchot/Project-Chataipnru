# B1 M3 — `webapi` → PostgreSQL Connection Design & Verification

| | |
|---|---|
| วันที่ | 2026-10-03 |
| ขอบเขต | **DESIGN + READ-ONLY VERIFICATION ONLY** |
| **M3** | **`M3_DESIGN_READY`** |
| role ที่แนะนำ | **`advisor_api`** (ใช้ได้ · ดูข้อ 5) · พร้อม **ข้อเสนอให้แยก role ใหม่** เป็นทางเลือกที่ปลอดภัยกว่า (ข้อ 9.3) |
| secret ใหม่ที่ต้องสร้าง | **ไม่มี** — `ADVISOR_API_PASSWORD` มีอยู่ใน `.env` ของ production แล้ว |
| dependency ใหม่ | **ต้องเพิ่ม 1 ตัว** — `pg` (node-postgres) |
| compose network | **ไม่ต้องแก้** — `webapi` กับ `postgres` อยู่ network เดียวกันอยู่แล้ว (ยืนยันบน production) |

```
แก้ production env  NONE   สร้าง/เปลี่ยน password  NONE   ALTER/CREATE ROLE  NONE
GRANT / REVOKE      NONE   แก้ docker-compose      NONE   แก้ source code    NONE
Migration 006       NONE   Apply Migration 005     NONE   Data Migration     NONE
Production Write    NONE   Supabase Write          NONE   Deploy / Restart   NONE
Commit / Push       NONE   Merge                   NONE
```

**ไม่มีรหัสผ่าน ไม่มีค่าใน `.env` ไม่มี connection string จริง ไม่มีอีเมล ไม่มี uuid ในเอกสารนี้**
สิ่งที่รายงานคือ **ชื่อตัวแปร** และ **สิทธิ์** เท่านั้น

---

## 1. Current `webapi` DB connectivity

# **ไม่มีเลย**

`webapi` วันนี้ **ไม่เคยต่อ PostgreSQL** — ตรวจจากสามที่ตรงกันทั้งหมด

| ที่ตรวจ | ผล |
|---|---|
| `docker-compose.prod.yml` · service `webapi` environment | มีแค่ **`VITE_SUPABASE_URL`** · **`VITE_SUPABASE_ANON_KEY`** · **`GOOGLE_GENERATIVE_AI_API_KEY`** — **ไม่มี `DATABASE_URL`** |
| `webapi/package.json` dependencies | `@supabase/supabase-js` · `@ai-sdk/google` · `ai` · `mammoth` · `pdf-parse` · `zod` — **ไม่มี PostgreSQL driver** |
| `webapi/auth.mjs` · `server.mjs` | ไม่มี `import` ของ driver ใด · `createRuntimeDeps()` คุย Supabase ผ่าน REST เท่านั้น |

`@supabase/supabase-js` เป็น **REST client ไม่ใช่ PG driver** — ต่อ PostgreSQL ของเราด้วยตัวนี้ไม่ได้

### 1.1 ผลที่ตามมา

`resolveAuthorId()` ใน `webapi/auth.mjs` ต้อง query `public.users` เพื่อแปลง
Supabase uuid → `public.users.id` (Option C ที่เจ้าของอนุมัติ) → **ทำไม่ได้จนกว่าจะปลดล็อก M3**

**M3 เป็น prerequisite ของทุก write endpoint** ไม่ว่าจะเลือก design ไหน

---

## 2. Current Docker / network topology

ตรวจบน production จริง (`docker network ls` · `docker inspect` · `docker port`)

```
network: course-advisor-system_default   (bridge, project default, ไม่มีบล็อก networks: ใน compose)

  frontend-1   3000/tcp                                  ไม่ publish
  backend-1    8000/tcp                                  ไม่ publish
  webapi-1     3001/tcp                                  ไม่ publish
  postgres-1   5432/tcp                                  ไม่ publish      <- สำคัญ
  ollama-1     11434/tcp                                 ไม่ publish
  caddy-1      80/tcp=PUBLISHED  443/tcp=PUBLISHED       ทางเข้าเดียวจากภายนอก
  db-viewer    8080/tcp -> 127.0.0.1:18081               publish แต่ผูก localhost เท่านั้น
```

### 2.1 สามข้อที่ยืนยันแล้วและทำให้งานนี้ง่าย

| | |
|---|---|
| **`webapi` กับ `postgres` อยู่ network เดียวกันอยู่แล้ว** | ทั้งคู่อยู่ `course-advisor-system_default` → **ไม่ต้องแก้บล็อก networks** ของ compose เลย |
| **`postgres` ไม่ publish พอร์ตออกนอกเครื่อง** | `docker port course-advisor-system-postgres-1` คืนค่าว่าง → ฐานข้อมูลเข้าถึงได้เฉพาะจากใน network |
| **ไม่มีบล็อก `networks:` ใน compose** | ใช้ default network ของ project → DNS ของ compose แปลงชื่อ service ให้อัตโนมัติ |

### 2.2 hostname / port ที่ `webapi` ต้องใช้

```
host  postgres        <- ชื่อ service ใน compose  ไม่ใช่ localhost ไม่ใช่ 127.0.0.1
port  5432            <- พอร์ตภายใน container
db    course_advisor
```

**เหมือนกับที่ `backend` ใช้อยู่แล้วเป๊ะ** (`@postgres:5432/course_advisor`)

> ⚠ **ห้ามใช้ `localhost` หรือ `127.0.0.1`** — ภายใน container นั้นหมายถึงตัว container เอง
> ไม่ใช่ฐานข้อมูล

### 2.3 ข้อสังเกตด้านความปลอดภัยที่พบระหว่างทาง — ไม่เป็นปัญหา

`db-viewer` (adminer) publish พอร์ต แต่ผูกไว้ที่ **`127.0.0.1:18081`** ไม่ใช่ `0.0.0.0`
→ เข้าถึงได้เฉพาะจากบนเครื่องหรือผ่าน SSH tunnel **ไม่ได้เปิดสู่อินเทอร์เน็ต**
ตรวจแล้วเพราะเป็นหน้าจอจัดการฐานข้อมูล ถ้าผูก `0.0.0.0` จะเป็นเรื่องใหญ่ — **ไม่ใช่**

---

## 3. Existing PostgreSQL roles

ตรวจ `pg_roles` บน production แบบอ่านอย่างเดียว

| role | login | superuser | createdb | member of | connection limit | expiry |
|---|---|---|---|---|---|---|
| `advisor_api` | ✅ | ❌ | ❌ | **ไม่เป็นสมาชิก role ใด** | `-1` (ไม่จำกัด) | ไม่มี |
| `advisor_ingest` | ✅ | ❌ | ❌ | **ไม่เป็นสมาชิก role ใด** | `-1` | ไม่มี |

### 3.1 `advisor_api` ทำอะไรได้บ้างวันนี้

```
USAGE ON SCHEMA public          true
CREATE ON SCHEMA public         false      <- ทำ DDL ไม่ได้  ดีแล้ว
DELETE ที่ใดบ้าง                 public.chat_answer_cache · public.user_requirements  เท่านั้น
                                ** ไม่มี DELETE บนตารางเนื้อหาใดเลย **
INSERT/UPDATE ที่ใดบ้าง          chat_answer_cache · chat_messages · chat_sessions
                                crawl_decisions · recommendations · shadow_answers
                                user_profiles · user_requirements · users
public.users                    INSERT · SELECT · UPDATE   (DELETE = false)
public.courses                  SELECT เท่านั้น
```

### 3.2 สิ่งที่สำคัญที่สุดสำหรับ M3

**`advisor_api` มี `SELECT` บน `public.users` อยู่แล้ว** → การ query ที่ Option C ต้องใช้

```sql
SELECT id FROM public.users WHERE supabase_user_id = $1
```

**ทำได้ทันทีโดยไม่ต้อง GRANT อะไรเพิ่ม** และสิทธิ์เป็น **ระดับตาราง ไม่มี grant ระดับคอลัมน์แยก**
→ คอลัมน์ `supabase_user_id` ที่ migration 006 จะเพิ่ม **ถูกครอบคลุมโดยอัตโนมัติ**

### 3.3 ภาระ connection ปัจจุบัน

```
max_connections       100
กำลังใช้อยู่            8     (advisor_api=1 · postgres=3 · ไม่ระบุชื่อ 4)
```

เหลือพื้นที่เหลือเฟือ — ดูการคำนวณ pool ในข้อ 8.3

---

## 4. Existing Migration 005 grants

จาก `db/migrations/005_web_schema.sql` (บรรทัด 339–353) ห่อด้วย `IF EXISTS (… pg_roles …)`
จึงไม่ล้มถ้า role ยังไม่มี

```sql
-- advisor_api
GRANT USAGE  ON SCHEMA web TO advisor_api;
GRANT SELECT ON ALL TABLES IN SCHEMA web TO advisor_api;
GRANT INSERT, UPDATE ON web.site_courses, web.news,
                        web.knowledge_articles, web.ai_settings TO advisor_api;
GRANT EXECUTE ON FUNCTION web.touch_updated_at() TO advisor_api;
GRANT SELECT ON web.external_news TO advisor_api;

-- advisor_ingest
GRANT USAGE  ON SCHEMA web TO advisor_ingest;
GRANT SELECT ON ALL TABLES IN SCHEMA web TO advisor_ingest;
GRANT INSERT, UPDATE ON web.external_news TO advisor_ingest;
GRANT EXECUTE ON FUNCTION web.touch_updated_at() TO advisor_ingest;
```

**ไม่มี `GRANT DELETE` ให้ใครเลย** — ตรงตามการตัดสินใจเดิมของเจ้าของ

### 4.1 GRANT รองรับ endpoint เป้าหมายไหม — ตารางเทียบ

| endpoint ที่ออกแบบไว้ | ระดับสิทธิ์ | SQL ที่ต้องทำ | 005 รองรับ |
|---|---|---|---|
| `GET /api/courses` | PUBLIC | `SELECT web.site_courses` | ✅ |
| `POST /api/courses` | EDITOR | `INSERT web.site_courses` | ✅ |
| `PATCH /api/courses/:id` | EDITOR | `UPDATE web.site_courses` + trigger | ✅ (มี `EXECUTE` ฟังก์ชัน trigger) |
| `DELETE /api/courses/:id` | ADMIN | `DELETE web.site_courses` | ❌ **ไม่มีสิทธิ์** — ตามที่ตัดสินใจไว้ |
| `GET /api/news` | PUBLIC_FILTERED | `SELECT web.news` | ✅ |
| `POST` / `PATCH /api/news` | EDITOR | `INSERT` / `UPDATE web.news` | ✅ |
| `DELETE /api/news/:id` | ADMIN | `DELETE web.news` | ❌ ตามที่ตัดสินใจไว้ |
| `GET` / `POST` / `PATCH /api/knowledge` | EDITOR | `SELECT`/`INSERT`/`UPDATE web.knowledge_articles` | ✅ |
| `DELETE /api/knowledge/:id` | ADMIN | `DELETE` | ❌ ตามที่ตัดสินใจไว้ |
| `GET /api/ai-settings` | PUBLIC | `SELECT web.ai_settings` | ✅ |
| `PATCH /api/ai-settings` | ADMIN | `UPDATE web.ai_settings` | ✅ |
| `GET /api/sci-connect-news*` | PUBLIC | `SELECT web.external_news` | ✅ |
| **resolve local identity** | ภายใน | **`SELECT public.users`** | ✅ **มีอยู่แล้ว ไม่ต้อง GRANT เพิ่ม** |

**สรุป: 005 รองรับทุก endpoint ยกเว้น `DELETE` 3 เส้นทาง ซึ่งเป็นการตัดสินใจไม่ใช่ข้อบกพร่อง**

### 4.2 ⚠ `DELETE` ยังไม่เพิ่ม — ต้องจัดการให้ไม่พังเงียบ

ตามการตัดสินใจเดิม **ยังไม่เพิ่ม `DELETE` privilege ในรอบนี้**
ถ้าสร้าง endpoint `DELETE` ขึ้นมา `advisor_api` จะได้ error ระดับฐานข้อมูล
(`permission denied for table`) ซึ่งเป็นข้อความภายในที่ไม่ควรหลุดออกไป

**ข้อเสนอ: ยังไม่สร้าง endpoint `DELETE` ในเฟสนี้** · ถ้าสร้างต้องคืน **501**
พร้อมข้อความชัด ไม่ใช่ปล่อยให้ error ของฐานข้อมูลไปถึงผู้ใช้

---

## 5. Recommended `webapi` DB role

# **`advisor_api` — ใช้ได้**

### 5.1 ทำไมใช้ได้

| เกณฑ์ | ผล |
|---|---|
| `SELECT public.users` สำหรับ resolve identity | ✅ **มีอยู่แล้ว** |
| `SELECT`/`INSERT`/`UPDATE` บน `web.*` ตามที่ endpoint ต้องการ | ✅ 005 ให้ไว้แล้ว |
| `EXECUTE web.touch_updated_at()` | ✅ |
| ทำ DDL ได้ไหม | ❌ `CREATE ON SCHEMA public` = `false` — **ดีแล้ว** |
| เป็น superuser ไหม | ❌ |
| เป็นสมาชิก role อื่นไหม | ❌ **ไม่สืบทอดสิทธิ์จากใคร** |
| `DELETE` บนตารางเนื้อหา | ❌ ตรงตามการตัดสินใจ |
| ต้อง GRANT เพิ่มไหม | **ไม่ต้องเลย** |
| ต้องสร้าง secret ใหม่ไหม | **ไม่ต้อง** — `ADVISOR_API_PASSWORD` มีอยู่ใน `.env` แล้ว |

### 5.2 ทางเลือกที่พิจารณาแล้วไม่เลือก

| role | ทำไมไม่เลือก |
|---|---|
| `postgres` (superuser) | **ปฏิเสธเด็ดขาด** — ให้ superuser แก่บริการที่รับคำขอจากอินเทอร์เน็ต |
| `advisor_ingest` | สิทธิ์ผิดด้าน — เขียนได้แต่ `web.external_news` และ **ไม่มีสิทธิ์แตะ `public.users`** จึง resolve identity ไม่ได้ |
| สร้าง role ใหม่ `advisor_web` | **เป็นทางที่ปลอดภัยกว่า** แต่ต้อง `CREATE ROLE` + `GRANT` + secret ใหม่ ซึ่งรอบนี้ห้าม → เสนอเป็นทางเลือกในข้อ 9.3 |

### 5.3 ข้อแลกเปลี่ยนที่ยอมรับอย่างรู้ตัว

ใช้ `advisor_api` ร่วมกับ `backend` หมายถึง **สองบริการใช้ตัวตนฐานข้อมูลเดียวกัน**
→ แยกไม่ออกใน `pg_stat_activity` ว่า connection ไหนมาจากบริการไหน

ลดได้ด้วยการตั้ง `application_name` ต่างกัน (ข้อ 6.3) ซึ่งไม่ต้องเปลี่ยน role

---

## 6. `DATABASE_URL` / env design

### 6.1 รูปแบบที่เสนอ — ลอกของ `backend` ให้ตรง

`docker-compose.prod.yml` service `webapi` เพิ่ม **หนึ่งบรรทัด** (ยังไม่ทำ)

```yaml
  webapi:
    environment:
      VITE_SUPABASE_URL: ${VITE_SUPABASE_URL}
      VITE_SUPABASE_ANON_KEY: ${VITE_SUPABASE_ANON_KEY}
      GOOGLE_GENERATIVE_AI_API_KEY: ${GOOGLE_GENERATIVE_AI_API_KEY:-}
      # เพิ่มบรรทัดนี้ — รูปแบบเดียวกับ backend แต่ไม่มี +psycopg
      DATABASE_URL: postgresql://advisor_api:${ADVISOR_API_PASSWORD}@postgres:5432/course_advisor?application_name=webapi
    depends_on:
      postgres:
        condition: service_healthy      # เพิ่ม — ของเดิมไม่มี depends_on
```

### 6.2 ⚠ ต่างจาก `backend` หนึ่งจุด — scheme

| | scheme | เหตุผล |
|---|---|---|
| `backend` (SQLAlchemy) | `postgresql+psycopg://` | `+psycopg` เป็นรูปแบบของ SQLAlchemy ที่ระบุ driver |
| **`webapi` (node-postgres)** | **`postgresql://`** | `pg` **ไม่รู้จัก `+psycopg`** จะ parse ไม่ผ่าน |

**คัดลอกค่าของ `backend` มาตรง ๆ ไม่ได้** — เป็นกับดักที่หาสาเหตุยากถ้าพลาด

### 6.3 `application_name=webapi`

ทำให้ `pg_stat_activity` แยกได้ว่า connection ไหนมาจาก `webapi` ไหนมาจาก `backend`
ทั้งที่ใช้ role เดียวกัน — **ไม่ต้องเปลี่ยน role และไม่มีต้นทุน**
ตอนนี้ 4 connection แสดงเป็น "ไม่ระบุชื่อ" ซึ่งตามรอยไม่ได้

### 6.4 ห้าม hardcode password — การันตีด้วยกลไกที่มีอยู่แล้ว

```
compose ใช้ ${ADVISOR_API_PASSWORD}   -> อ่านจาก .env ตอน docker compose up
ไม่มีรหัสผ่านใน repo                   -> .env ถูก gitignore (.gitignore:17) และ git ls-files = 0
ไม่มีรหัสผ่านใน image                  -> Dockerfile ไม่ COPY .env และไม่มี ARG/ENV ของ secret
โค้ดอ่านจาก process.env เท่านั้น        -> เหมือนที่ auth.mjs ทำกับ VITE_SUPABASE_*
```

### 6.5 ถ้า `DATABASE_URL` ไม่ถูกตั้ง — ต้อง fail closed

ตามรูปแบบที่ `auth.mjs` ใช้อยู่แล้วกับ `supabaseEnv()`

```
ไม่มี DATABASE_URL  ->  endpoint ที่ต้อง resolve identity ตอบ 500 ทุกครั้ง
                        /healthz รายงาน dbConfigured: false
                        ** ห้าม fallback ไปค่าใด ๆ และห้ามข้ามการ resolve **
```

`/healthz` วันนี้รายงาน `authConfigured` อยู่แล้ว → เพิ่ม `dbConfigured` เป็นรูปแบบเดียวกัน

---

## 7. Secret-management design

### 7.1 สภาพที่เป็นอยู่ — ตรวจแล้ว

| | |
|---|---|
| ที่เก็บ | `/home/ubuntu/course-advisor-system/.env` บน production |
| สิทธิ์ไฟล์ | **`600 ubuntu:ubuntu`** — อ่านได้เฉพาะเจ้าของ |
| gitignore | ✅ `.gitignore:17` · `git ls-files .env` = **0** |
| มีแม่แบบไหม | ✅ `.env.example` อยู่ใน repo |
| คีย์ที่มีอยู่แล้ว (ชื่อเท่านั้น) | `POSTGRES_PASSWORD` · **`ADVISOR_API_PASSWORD`** · `ADVISOR_INGEST_PASSWORD` · `JWT_SECRET` · `DATABASE_URL` · `INGEST_DATABASE_URL` · `VITE_SUPABASE_URL` · `VITE_SUPABASE_ANON_KEY` · `GOOGLE_GENERATIVE_AI_API_KEY` · อื่น ๆ |

### 7.2 ข้อสรุป — **ไม่ต้องสร้าง secret ใหม่เลย**

**`ADVISOR_API_PASSWORD` มีอยู่ใน `.env` ของ production แล้ว** เพราะ `backend` ใช้อยู่
→ compose interpolate ให้ `webapi` ได้ทันที

| | |
|---|---|
| ต้องสร้างรหัสผ่านใหม่ไหม | **ไม่** |
| ต้องแก้ `.env` บน production ไหม | **ไม่** (ถ้าใช้ `advisor_api`) |
| ต้องแก้ `.env.example` ไหม | **ไม่จำเป็น** — ไม่มีคีย์ใหม่ · แต่ถ้าแยก role ใหม่ ต้องเพิ่ม `ADVISOR_WEB_PASSWORD` |
| รหัสผ่านโผล่ใน log ไหม | **ต้องไม่** — ดูข้อ 7.3 |

### 7.3 กฎที่ต้องรักษาตอน implement

```
ห้าม console.log ค่า DATABASE_URL หรือส่วนใดของมัน  (มี password อยู่ในนั้น)
ห้ามส่ง error ของ driver ดิบ ๆ ออกไปใน response      (ข้อความอาจมี host/user)
log บอกได้แค่ "ต่อฐานข้อมูลไม่ได้"                    ไม่บอก host ไม่บอก user ไม่บอก password
/healthz รายงานแค่ dbConfigured: true/false         ไม่รายงานค่าใด
```

เป็นหลักเดียวกับที่ `auth.mjs` ใช้อยู่แล้ว (`describeForLog()` ไม่มี token ไม่มีอีเมล ไม่มี uuid)

---

## 8. Node driver + pool design

### 8.1 ต้องเพิ่ม dependency — **ใช่ 1 ตัว**

```
pg   (node-postgres)
```

| เกณฑ์ | `pg` |
|---|---|
| มี connection pool ในตัว | ✅ `pg.Pool` |
| รองรับ parameterized query | ✅ `$1`, `$2` — **จำเป็นเพื่อกัน SQL injection** |
| เป็นมาตรฐานของระบบนิเวศ Node | ✅ |
| ต้องมี build tool ไหม | ❌ pure JS → ติดตั้งใน `node:22-alpine` ได้ไม่ต้องเพิ่มอะไร |

**ทางเลือกที่ไม่เลือก**: `postgres` (porsager) ใช้งานได้แต่ไม่ใช่ตัวที่คนในระบบนิเวศคุ้นที่สุด ·
**ไม่ใช้ ORM** เพราะ query มีไม่กี่ตัวและตรงไปตรงมา ORM จะเพิ่มของให้ดูแลโดยไม่ได้ประโยชน์

> `Dockerfile` มี `RUN npm install --omit=dev` อยู่แล้ว → `pg` ต้องอยู่ใน `dependencies`
> **ไม่ใช่ `devDependencies`** ไม่งั้นจะไม่ถูกติดตั้งใน image

### 8.2 pool ควรอยู่ตรงไหน

```
webapi/db.mjs  (ไฟล์ใหม่)        สร้าง pool ตัวเดียวระดับโมดูล  export query()
webapi/auth.mjs                 import query() ไปใช้ใน resolveAuthorId()
webapi/server.mjs               เรียก db.close() ตอนปิดบริการ
```

**pool ตัวเดียวต่อโปรเซส ไม่ใช่ต่อคำขอ** — สร้าง pool ต่อคำขอคือการเปิดปิด TCP ทุกครั้ง
ซึ่งเป็นเหตุผลที่ pool มีอยู่

โครงสร้างนี้ลอกรูปแบบที่ `auth.mjs` ใช้อยู่แล้ว: ไม่มี I/O ตอนโหลดโมดูล · รับ dependency
เข้ามาได้เพื่อให้ทดสอบได้โดยไม่ต้องมีฐานข้อมูลจริง

### 8.3 ขนาด pool ที่เสนอ

```
max                4       เล็กพอ และพอสำหรับ 3 เส้นทาง /api/admin/* ที่มีผู้ดูแลใช้
idleTimeoutMillis  30000
connectionTimeoutMillis  5000      ไม่รอนานจนคำขอค้าง
```

**งบ connection ที่ตรวจแล้ว**

```
max_connections            100
ใช้อยู่ตอนนี้                 8
backend (SQLAlchemy)       pool_size 10 + max_overflow 20  ->  สูงสุด 30
webapi ที่เสนอ               4
รวมที่แย่ที่สุด                ~42  <  100          เหลือพื้นที่พอ
```

`max = 4` ไม่ใช่ตัวเลขที่เดา — เส้นทางที่ต้องใช้ฐานข้อมูลคือ 3 เส้นทางของผู้ดูแล
ซึ่งไม่ใช่เส้นทางที่นักเรียนใช้ · ถ้าวันหนึ่งย้าย endpoint อ่านสาธารณะมาที่นี่ด้วย
**ต้องทบทวนตัวเลขนี้ใหม่** ไม่ใช่ปล่อยไว้

### 8.4 startup / shutdown lifecycle

```
startup   ไม่ต่อฐานข้อมูลตอน import  (lazy)  -> บริการขึ้นได้แม้ฐานข้อมูลยังไม่พร้อม
          แต่ compose ตั้ง depends_on: postgres condition: service_healthy อยู่แล้ว
          -> ลำดับถูกตั้งแต่ต้น ไม่ต้องพึ่ง retry loop ในโค้ด

readiness /healthz รายงาน dbConfigured: true/false  (ไม่ยิง query จริงทุกครั้งที่เรียก
          เพราะ healthcheck ของ Docker เรียกทุก 30 วินาที จะกลายเป็นภาระ)

shutdown  รับ SIGTERM / SIGINT -> server.close() -> pool.end() -> process.exit(0)
          สำคัญ: ปัจจุบัน server.mjs ไม่มีตัวจัดการสัญญาณเลย
          ถ้าไม่เพิ่ม connection จะถูกตัดกลางคันตอน deploy ทุกครั้ง
```

> **ข้อสังเกตที่พบระหว่างตรวจ**: `server.mjs` วันนี้ไม่มี graceful shutdown
> ซึ่งวันนี้ยังไม่เป็นปัญหาเพราะไม่มี connection ค้าง แต่เมื่อมี pool แล้ว **จำเป็น**

---

## 9. Least-privilege analysis

### 9.1 `advisor_api` เพียงพอไหม — **เพียงพอ และไม่ต้อง GRANT เพิ่ม**

| สิ่งที่ต้องทำ | สิทธิ์ที่มี | ต้องเพิ่ม |
|---|---|---|
| resolve identity (`SELECT public.users`) | ✅ SELECT | ไม่ |
| อ่าน `web.*` | ✅ SELECT ทุกตาราง | ไม่ |
| เขียน 4 ตารางเนื้อหา | ✅ INSERT, UPDATE | ไม่ |
| เรียก trigger function | ✅ EXECUTE | ไม่ |
| เขียน `web.external_news` | ❌ มีแต่ SELECT | **ไม่ควรเพิ่ม** — เป็นของ `advisor_ingest` โดยเจตนา |
| DDL | ❌ | **ไม่ควรเพิ่ม** |
| DELETE ตารางเนื้อหา | ❌ | **ไม่เพิ่มตามการตัดสินใจ** |

### 9.2 ⚠ พบจุดที่กว้างเกินจำเป็น — `UPDATE` บน `public.users`

ตรวจแล้วบน production

```
advisor_api  ->  public.users   INSERT · SELECT · UPDATE     (DELETE = false)
สิทธิ์เป็นระดับตาราง ไม่มี grant ระดับคอลัมน์แยก
```

**ผลที่ตามมาเมื่อ migration 006 เพิ่มคอลัมน์ `supabase_user_id`**

คอลัมน์นั้นจะถูกครอบคลุมโดย `UPDATE` ระดับตารางอัตโนมัติ → **บริการที่ *อ่าน* การจับคู่
ตัวตน ก็ *เขียน* การจับคู่นั้นได้ด้วย**

| ทำไมสำคัญ | |
|---|---|
| `supabase_user_id` **คือสิ่งที่ตัดสินว่าใครเป็นใคร** | ถ้ามีข้อบกพร่องหรือช่องโหว่ใน `webapi` การเขียนทับคอลัมน์นี้คือการผูกบัญชี Supabase เข้ากับผู้ใช้ production คนอื่น = **ยกระดับสิทธิ์** |
| `webapi` รับคำขอจากอินเทอร์เน็ต | พื้นที่โจมตีใหญ่กว่า script ที่รันครั้งเดียว |
| ขั้นเติมค่าควรทำโดยใคร | **เจ้าของ/migrator ครั้งเดียว ไม่ใช่ `webapi`** |

**ไม่ใช่ช่องโหว่วันนี้** (คอลัมน์ยังไม่มี และยังไม่มีโค้ดที่เขียนมัน) แต่ต้องตัดสินใจ
**ก่อน** สร้าง migration 006 ไม่ใช่หลัง

### 9.3 ทางลดที่เสนอ — เลือกหนึ่ง (ทั้งสองทางยังไม่ทำในรอบนี้)

| ทาง | วิธี | ประเมิน |
|---|---|---|
| **A. จำกัดระดับคอลัมน์** | ใน migration 006: `REVOKE UPDATE ON public.users FROM advisor_api;` แล้ว `GRANT UPDATE (คอลัมน์ที่ backend ต้องแก้จริง) ON public.users TO advisor_api;` | แม่นที่สุด **แต่ต้องรู้ว่า `backend` แก้คอลัมน์ไหนจริง** ถ้าระบุไม่ครบ backend จะพังตอนแก้โปรไฟล์ผู้ใช้ → **ต้องตรวจโค้ด backend ก่อน** |
| **B. แยก role ใหม่ `advisor_web`** | `SELECT` บน `public.users` · `SELECT/INSERT/UPDATE` บน `web.*` · **ไม่มี UPDATE บน `public.users`** | สะอาดที่สุดในแง่ขอบเขต · แยกใน `pg_stat_activity` ได้จริง · **แต่ต้อง `CREATE ROLE` + secret ใหม่ + แก้ `.env` บน production** |

**ข้อเสนอ: ทาง B** — ขอบเขตชัดกว่าและไม่เสี่ยงทำ `backend` พัง
แต่ต้นทุนสูงกว่า (secret ใหม่ + แก้ `.env`)

**ถ้าเจ้าของเลือกเดินเร็วก่อน**: ใช้ `advisor_api` ได้ทันทีโดยไม่ต้องทำอะไรเพิ่ม
แล้วบันทึกข้อ 9.2 เป็นหนี้ที่ต้องชำระก่อน migration 006 — **ซึ่งผมแนะนำว่าอย่าเลื่อน
ไปหลัง 006** เพราะการ REVOKE ทีหลังยากกว่าการตั้งให้ถูกตั้งแต่ต้น

### 9.4 สิ่งที่ `advisor_api` ทำไม่ได้ และดีแล้วที่ทำไม่ได้

```
CREATE/ALTER/DROP ใน schema public        false
DELETE บนตารางเนื้อหาใด ๆ                  ไม่มี
เขียน web.external_news                   ไม่มี  (เป็นของ advisor_ingest)
เป็นสมาชิก role อื่น                       ไม่เป็น -> ไม่สืบทอดสิทธิ์
PUBLIC role มีสิทธิ์บน public.users         ไม่มี
default privileges ใน schema public       0 รายการ -> ตารางใหม่ไม่ได้สิทธิ์อัตโนมัติ
```

ข้อสุดท้ายสำคัญ: **ไม่มี default privileges** → ตารางที่สร้างใหม่ในอนาคตจะไม่ให้สิทธิ์
แก่ `advisor_api` โดยอัตโนมัติ ต้อง `GRANT` อย่างตั้งใจทุกครั้ง ซึ่งเป็นพฤติกรรมที่ต้องการ

---

## 10. Required code / config changes — **DESIGN ONLY**

**ยังไม่ทำอะไรเลยในรอบนี้**

| # | ไฟล์ | การแก้ | ขนาด |
|---|---|---|---|
| 1 | `webapi/package.json` | เพิ่ม `pg` ใน **`dependencies`** | 1 บรรทัด |
| 2 | `webapi/db.mjs` | **ไฟล์ใหม่** — pool ตัวเดียว · `query()` ที่บังคับ parameterized · `close()` | ~60 บรรทัด |
| 3 | `webapi/auth.mjs` | `resolveAuthorId()` query `supabase_user_id` แทนการปฏิเสธเสมอ | ~15 บรรทัด |
| 4 | `webapi/server.mjs` | เพิ่ม `dbConfigured` ใน `/healthz` · graceful shutdown (SIGTERM/SIGINT → `pool.end()`) | ~20 บรรทัด |
| 5 | `webapi/Dockerfile` | `COPY server.mjs auth.mjs db.mjs ./` | 1 บรรทัด |
| 6 | `docker-compose.prod.yml` | `webapi` เพิ่ม `DATABASE_URL` + `depends_on: postgres service_healthy` | 4 บรรทัด |
| 7 | `webapi/*.test.mjs` | ข้อตรวจ: ไม่มี `DATABASE_URL` → fail closed · `query()` ปฏิเสธการต่อสตริง SQL · `resolveAuthorId` คืน 0/1/>1 ถูก · pool ปิดตอน shutdown | ชุดใหม่ |

### 10.1 ลำดับที่เสนอ

```
1. ตัดสินใจเรื่อง role (ข้อ 9.3)            <- ก่อนอื่น เพราะกำหนดว่า .env ต้องแก้ไหม
2. migration 006 (ADD COLUMN) + ข้อตรวจ      <- ขออนุมัติแยก
3. ขั้นเติมค่า supabase_user_id ของ S1       <- เจ้าของยืนยัน · ไม่ใช่ webapi ทำ
4. db.mjs + pg + compose + Dockerfile       <- M3 implementation
5. resolveAuthorId() ใช้งานจริง + ข้อตรวจ
6. write endpoint ทีละตาราง
```

**ข้อ 1 ต้องมาก่อน 2** — ถ้าเลือกทาง A ของข้อ 9.3 การ REVOKE/GRANT ต้องอยู่ใน 006

---

## 11. Risks / blockers

| # | ความเสี่ยง | ระดับ | ทางลด |
|---|---|---|---|
| **D1** | **`UPDATE` บน `public.users` กว้างเกินจำเป็น** — บริการที่อ่านการจับคู่ตัวตนเขียนมันได้ด้วย | **สูง** | ข้อ 9.3 — ตัดสินใจ **ก่อน** migration 006 |
| **D2** | **ใช้ scheme ผิด** — คัดลอก `postgresql+psycopg://` จาก `backend` มาใช้กับ `pg` | **กลาง** | ข้อ 6.2 · `pg` parse ไม่ผ่านและ error อาจกำกวม · ควรมีข้อตรวจว่า URL ไม่มี `+` |
| **D3** | **ไม่มี graceful shutdown ใน `server.mjs` วันนี้** | **กลาง** | ข้อ 8.4 · เมื่อมี pool แล้วจำเป็น ไม่งั้น connection ถูกตัดกลางคันทุกครั้งที่ deploy |
| **D4** | **รหัสผ่านหลุดเข้า log** ผ่าน error ของ driver | **กลาง** | ข้อ 7.3 · ห้าม log `DATABASE_URL` ห้ามส่ง error ดิบออกไป |
| **D5** | **pool ใหญ่เกิน** ถ้าย้าย endpoint สาธารณะมาที่นี่ด้วย | ต่ำ | `max = 4` พอสำหรับ 3 เส้นทางผู้ดูแล · **ต้องทบทวนเมื่อขอบเขตเปลี่ยน** |
| **D6** | **SQL injection** ถ้าต่อสตริง query เอง | **สูงถ้าพลาด** | บังคับ parameterized (`$1`) ใน `db.mjs` และมีข้อตรวจ · ไม่ใช่แค่วินัย |
| **D7** | **ใช้ role ร่วมกับ `backend`** แยกไม่ออกใน `pg_stat_activity` | ต่ำ | `application_name=webapi` (ข้อ 6.3) หรือแยก role (9.3 ทาง B) |
| **R1** | `createSupabaseVerifier` ยังไม่เคยคุยกับ Supabase จริง | **สูง** | ค้างจากรอบ B1 foundation — **ไม่เกี่ยวกับ M3** |
| **R6** | ครึ่งหนึ่งของงาน B1 อยู่ในรีโปหน้าเว็บที่ยังไม่อนุมัติให้แก้ | **สูง** | ค้างจากรอบ B1 foundation |

### 11.1 ไม่มี blocker ที่ทำให้ M3 เดินต่อไม่ได้

D1 เป็นการตัดสินใจไม่ใช่สิ่งกีดขวาง · D2–D7 เป็นรายละเอียดการ implement ที่รู้ล่วงหน้าแล้ว
· R1 และ R6 ไม่เกี่ยวกับการเชื่อมต่อฐานข้อมูล

---

## 12. M3 classification

# `M3_DESIGN_READY`

### 12.1 ทุกคำถามที่สั่งให้ตอบ — ตอบครบ

| คำถาม | คำตอบ |
|---|---|
| `webapi` ควรใช้ role ไหน | **`advisor_api`** (ข้อ 5) · พร้อมข้อเสนอให้แยก `advisor_web` ถ้าต้องการแคบกว่า (9.3) |
| `advisor_api` ใช้ได้หรือไม่ | **ใช้ได้ ไม่ต้อง GRANT เพิ่มเลย** — มี `SELECT public.users` อยู่แล้ว |
| `DATABASE_URL` inject อย่างไร | compose interpolate `${ADVISOR_API_PASSWORD}` จาก `.env` → `postgresql://…@postgres:5432/course_advisor?application_name=webapi` (6.1) · **scheme ไม่มี `+psycopg`** (6.2) |
| ห้าม hardcode password | ✅ `.env` gitignored · ไม่อยู่ใน image · โค้ดอ่านจาก `process.env` (6.4) |
| hostname / port | **`postgres:5432`** · ฐาน `course_advisor` · **ห้ามใช้ localhost** (2.2) |
| ต้องเพิ่ม dependency ไหม | **ใช่ 1 ตัว — `pg`** ใน `dependencies` ไม่ใช่ `devDependencies` (8.1) |
| pool อยู่ตรงไหน | `webapi/db.mjs` **ตัวเดียวระดับโมดูล** ไม่ใช่ต่อคำขอ (8.2) · `max = 4` (8.3) |
| startup / shutdown | lazy connect · `depends_on` มี `service_healthy` อยู่แล้ว · **ต้องเพิ่ม graceful shutdown** (8.4) |
| secret จัดการอย่างไรโดยไม่ commit | **ไม่ต้องสร้าง secret ใหม่** — `ADVISOR_API_PASSWORD` มีอยู่แล้ว · `.env` mode `600` gitignored (7) |
| least privilege เพียงพอไหม | **เพียงพอสำหรับทุก endpoint** แต่ **พบจุดกว้างเกิน**: `UPDATE public.users` (9.2) |
| 005 GRANT รองรับ endpoint ไหม | **รองรับทุกอย่างยกเว้น `DELETE` 3 เส้นทาง** (4.1) |
| `DELETE` ยังไม่เพิ่มใช่ไหม | **ใช่ ไม่เพิ่ม** ตามการตัดสินใจเดิม · ข้อเสนอ: ยังไม่สร้าง endpoint `DELETE` หรือคืน **501** (4.2) |

### 12.2 ทำไมไม่ใช่ `M3_VERIFICATION_REQUIRED`

ตรวจครบทั้ง 8 รายการที่สั่ง: compose · Dockerfile · package.json · server.mjs · auth.mjs ·
GRANT ของ 005 · วิธีที่ `backend` ต่อ · network topology จริงบน production
**ไม่มีข้อใดเหลือที่เป็น "ยังไม่รู้"**

### 12.3 ทำไมไม่ใช่ `M3_BLOCKED`

ไม่ต้องสร้าง secret ใหม่ · ไม่ต้อง GRANT เพิ่ม · ไม่ต้องแก้ network · ไม่ต้องแก้ `.env`
→ ปลดล็อกได้ด้วยการแก้ **6 ไฟล์ในรีโปนี้** ซึ่งไม่มีไฟล์ใดอยู่ในรีโปหน้าเว็บ

### 12.4 ข้อเดียวที่ต้องตัดสินก่อนลงมือ

**D1 / ข้อ 9.3** — จะใช้ `advisor_api` ตามที่เป็น หรือแยก role ใหม่
**ไม่บล็อก M3** (ทั้งสองทางใช้งานได้) แต่ **ควรตัดสินก่อน migration 006**
เพราะถ้าเลือกทาง A การ REVOKE/GRANT ต้องอยู่ใน 006 นั้น

---

## 13. Exact next implementation step

```
1. ตัดสินใจเรื่อง role (ข้อ 9.3)
     ใช้ advisor_api ตามที่เป็น          -> ไม่ต้องแก้ .env  เริ่มข้อ 2 ได้ทันที
     แยก role advisor_web                -> ต้อง CREATE ROLE + GRANT + secret ใหม่ + แก้ .env
                                            = รอบแยกที่เจ้าของอนุมัติ

2. ขออนุมัติ implement M3  (6 ไฟล์ตามข้อ 10)
     webapi/package.json      เพิ่ม pg
     webapi/db.mjs            ใหม่ — pool + query() ที่บังคับ parameterized + close()
     webapi/auth.mjs          resolveAuthorId() ใช้ฐานข้อมูลจริง
     webapi/server.mjs        dbConfigured ใน /healthz + graceful shutdown
     webapi/Dockerfile        COPY db.mjs
     docker-compose.prod.yml  DATABASE_URL + depends_on

3. ขออนุมัติ migration 006 แยก  (ADD COLUMN supabase_user_id + partial unique index)
     ** ห้ามแก้ 005 **
     ถ้าเลือกทาง A ของข้อ 9.3 การ REVOKE/GRANT อยู่ใน 006 นี้

4. ขั้นเติมค่า supabase_user_id ของ S1  — เจ้าของยืนยัน · ไม่ใช่ webapi ทำ

5. ขออนุมัติเขียนรีโปหน้าเว็บ (R6) แล้วจึงสร้าง write endpoint ทีละตาราง
```

### 13.1 สิ่งที่ยังไม่ทำและจะไม่ทำจนได้รับอนุมัติ

```
ไม่แก้ source code แม้บรรทัดเดียว        ไม่แก้ docker-compose
ไม่สร้าง migration 006                  ไม่แก้ .env บน production
ไม่สร้าง/เปลี่ยนรหัสผ่าน                 ไม่ CREATE/ALTER ROLE  ไม่ GRANT/REVOKE
ไม่ deploy ไม่ restart                   ไม่ commit ไม่ push
```

---

## บันทึกการเข้าถึงข้อมูลในรอบนี้

| ระบบ | การเข้าถึง | รายละเอียด |
|---|---|---|
| source / config ในรีโป | **อ่านอย่างเดียว** | `docker-compose.prod.yml` · `webapi/*` · `db/migrations/005` · `db/schema.sql` · `.gitignore` |
| production PostgreSQL | **`SELECT` อย่างเดียว** | `pg_roles` · `information_schema.table_privileges` / `column_privileges` · `has_*_privilege()` · `pg_stat_activity` · `current_setting()` |
| production Docker | **อ่านอย่างเดียว** | `docker network ls` · `docker inspect` · `docker port` — ไม่มีคำสั่งที่เปลี่ยนสถานะ |
| production filesystem | **อ่าน metadata อย่างเดียว** | `stat` ของ `.env` (สิทธิ์/เจ้าของ) · `grep -oE '^[A-Z_]+'` เพื่อเอา **ชื่อคีย์เท่านั้น** |
| ข้อมูลที่ดึงออกมา | ชื่อ role · ชื่อสิทธิ์ · ชื่อตัวแปร · จำนวน · boolean | **ไม่มีรหัสผ่าน ไม่มีค่าใน `.env` ไม่มี connection string จริง ไม่มีอีเมล ไม่มี uuid** |
| คำสั่งเขียน / DDL | **ไม่มีแม้คำสั่งเดียว** | |

---

## STOP

**`M3_DESIGN_READY`** — ปลดล็อกได้ด้วยการแก้ 6 ไฟล์ในรีโปนี้ · ไม่ต้องสร้าง secret ใหม่
· ไม่ต้อง GRANT เพิ่ม · ไม่ต้องแก้ network

เรื่องที่รอการตัดสินใจ

1. **D1 / ข้อ 9.3** — ใช้ `advisor_api` ตามที่เป็น หรือแยก role `advisor_web`
   (ควรตัดสินก่อน migration 006 เพราะกำหนดว่า REVOKE/GRANT ต้องอยู่ใน 006 ไหม)
2. **อนุมัติ implement M3** 6 ไฟล์ตามข้อ 10 หรือไม่
3. **อนุมัติ migration 006** แยก (`ADD COLUMN supabase_user_id`)
4. **`DELETE` endpoint** — ยังไม่สร้าง หรือสร้างแล้วคืน 501 (ข้อ 4.2)
5. **R1** — ยืนยัน `createSupabaseVerifier` กับ Supabase จริงเมื่อใด
6. **R6** — อนุมัติเขียนรีโปหน้าเว็บ

```
แก้ production env  NONE   สร้าง/เปลี่ยน password  NONE   ALTER/CREATE ROLE  NONE
GRANT / REVOKE      NONE   แก้ docker-compose      NONE   แก้ source code    NONE
Migration 006       NONE   Apply Migration 005     NONE   Data Migration     NONE
Production Write    NONE   Supabase Write          NONE   Deploy / Restart   NONE
Commit / Push       NONE   Merge                   NONE
```
