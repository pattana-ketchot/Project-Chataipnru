# M3 Production Rollout Preflight

> **READ-ONLY** — การตรวจรอบนี้ไม่แก้ production, ไม่ deploy, ไม่ restart, ไม่เขียนฐานข้อมูล, ไม่เขียน Supabase, ไม่ push/merge/commit และไม่แตะ frontend repository

## ผลสรุป (ปรับปรุง 10 ต.ค. 2569)

# `M3_ROLLOUT_PREFLIGHT_READY`

**ต้องทำ 2 ข้อนี้ก่อนกด deploy — ทั้งคู่ต้องให้เจ้าของสั่ง**

| # | สิ่งที่ต้องทำ | ทำไมสำคัญ |
|---|---|---|
| 1 | `docker tag course-advisor-system-webapi:latest course-advisor-system-webapi:rollback-pre-m3` **บนเครื่อง production** แล้วยืนยันด้วย `docker images \| grep webapi` | webapi มี tag `latest` ตัวเดียว ไม่มี rollback tag เหมือน backend/frontend · ถ้า build ทับโดยไม่ติด tag ก่อน จะไม่เหลืออะไรให้ย้อนกลับเลย |
| 2 | เตรียมบัญชี admin ที่สถานะ `approved` ไว้ทดสอบ smoke test ข้อ 6 | เป็นข้อเดียวที่พิสูจน์ว่า authorization foundation ที่จะขึ้น production ครั้งแรกไม่ล็อกผู้ดูแลออกจากระบบ |

ทั้งสองข้อเป็นการกระทำบน production จึงไม่ได้ทำในรอบตรวจนี้

### สิ่งที่เปลี่ยนจากฉบับแรก

ฉบับแรกสรุปว่า **BLOCKED** ด้วยเหตุผลว่า `webapi/api/` ไม่อยู่ใน version control และไม่มีสำเนาสำรองนอก production ตอนนี้แก้ครบแล้ว

| เดิม | ตอนนี้ |
|---|---|
| ไม่รู้ว่าทำไม `api/` ถึงไม่อยู่ใน git | **รู้แล้ว** — ถูก `.gitignore` โดยตั้งใจตั้งแต่ commit `589cff5` และ `webapi/README.md` ที่อยู่ใน git มีขั้นตอนครบ (ดูหมายเหตุแก้ไขในข้อ 5) |
| ไม่มีสำเนาสำรองนอก production | **มีแล้ว** — `webapi-api-backup-20261009T204112.tar.gz` ตรวจ SHA256 ครบ 10 ไฟล์และทดสอบกู้คืนแล้ว |
| ไม่เคยพิสูจน์ว่า build ผ่าน | **พิสูจน์แล้ว** — `docker build -t webapi-m3-localtest:dba865b` สำเร็จด้วย source จริงทั้ง 10 ไฟล์ · ไฟล์ใน image ครบ · import 7/7 · container บูตและตอบ `/healthz` ได้ |

รายละเอียดอยู่ใน `M3_WEBAPI_SOURCE_RECOVERY_RESULT.md` และ `M3_BUILD_VERIFICATION_RESULT.md`

ส่วนอื่นทั้งหมดผ่านตั้งแต่ฉบับแรก ไม่มีข้อมูลไม่ตรง ไม่พบ drift ระหว่าง production กับ repo

| สถานะที่แจ้งมา | ตรวจแล้ว |
|---|---|
| HEAD = `dba865b` | ตรง |
| Branch = `mko-phase2` | ตรง |
| ยังไม่ push | ตรง — `origin/mko-phase2` ยังอยู่ที่ `dc5e860` ตามหลัง 6 commits |
| ยังไม่แก้ production `.env` | ตรง — ไม่มีคีย์ `ADVISOR_WEB_PASSWORD` ใน `.env` |

---

## 1. Production WebAPI image และ Compose ปัจจุบัน

### 1.1 คอนเทนเนอร์ที่รันอยู่

| คอนเทนเนอร์ | Image | สถานะ |
|---|---|---|
| `course-advisor-system-webapi-1` | `course-advisor-system-webapi` (`:latest`) | Up 2 weeks (healthy) |
| `course-advisor-system-postgres-1` | `pgvector/pgvector:pg16` | Up 7 weeks (healthy) |
| `course-advisor-system-backend-1` | `course-advisor-system-backend:2fdc6f2` | Up 10 days |
| `course-advisor-system-frontend-1` | `course-advisor-system-frontend:2fdc6f2` | Up 10 days |
| `course-advisor-system-caddy-1` | `caddy:2-alpine` | Up 2 weeks |
| `course-advisor-system-ollama-1` | `ollama/ollama:latest` | Up 7 weeks (healthy) |
| `db-viewer` | `adminer:latest` | Up 3 weeks |

webapi image id `sha256:1163e363…` สร้างเมื่อ **2026-09-22T21:21:26Z** ขนาด 527 MB

### 1.2 Compose ที่ใช้จริง

- ไฟล์: `/home/ubuntu/course-advisor-system/docker-compose.prod.yml`
- working dir: `/home/ubuntu/course-advisor-system`
- **sha256 = `d76afeef4ec1383d28f595f600a3383c857f808a95842880c476ff955d0926c8`**

เทียบกับ repo:

| เวอร์ชัน | sha256 | ตรงกับ production |
|---|---|---|
| `HEAD~1` (ก่อนแก้ M3) | `d76afeef…0926c8` | **ตรงเป๊ะ** |
| `HEAD` (`dba865b`, มี M3) | `abc9b2fb…8d1562` | ต่าง (ตามที่ตั้งใจ) |

**ไม่มี configuration drift** — compose บนเซิร์ฟเวอร์คือไฟล์เดียวกับใน git ก่อนแก้ M3 ทุกไบต์ การ deploy จึงเป็น delta ที่สะอาด

### 1.3 Deploy tree บนเซิร์ฟเวอร์เป็นรุ่นก่อน Authorization

`/home/ubuntu/course-advisor-system/` **ไม่ใช่ git checkout** เป็นโฟลเดอร์ที่คัดลอกไฟล์เข้าไป เนื้อหาใน `webapi/` ลงวันที่ 22 ก.ย.

| ไฟล์ | บนเซิร์ฟเวอร์ | ใน repo (`dba865b`) |
|---|---|---|
| `Dockerfile` | มี (รุ่นเก่า) | แก้แล้ว — `npm ci`, copy `db.mjs` |
| `server.mjs` | มี 91 บรรทัด | 261 บรรทัด |
| `package.json` | มี ไม่มี `pg` | มี `pg ^8.23.1` |
| `api/` (10 ไฟล์) | **มี** | **ไม่มี** |
| `auth.mjs` | **ไม่มี** | มี |
| `db.mjs` | **ไม่มี** | มี |
| `package-lock.json` | **ไม่มี** | มี |

ยืนยันว่า `server.mjs` บน production ไม่มีการอ้างถึง `auth.mjs`, `db.mjs`, `requireAdminUser` หรือ `resolveAuthContext` เลยสักครั้ง

---

## 2. Dependencies, Healthcheck, Routes, ความพร้อมของ PostgreSQL

### 2.1 Dependencies

`package.json` ใน repo เพิ่ม `pg ^8.23.1` หนึ่งตัว และ `package-lock.json` ตรึงไว้ที่ 8.23.1 ตรงกับที่รันทดสอบในเครื่อง (`require('pg/package.json').version` = 8.23.1)

Dockerfile เปลี่ยนจาก `npm install` + `package-lock.json*` (glob) เป็น `npm ci` + `package-lock.json` (ไม่มี glob) — **ถ้า deploy ลืมคัดลอก `package-lock.json` ขึ้นไป build จะล้มทันที** ซึ่งเป็นพฤติกรรมที่ตั้งใจ (ล้มเสียงดังดีกว่าเงียบ ๆ ดึงรุ่นใหม่ที่ไม่เคยทดสอบ) แต่ต้องจำไว้ในขั้นตอน deploy เพราะเซิร์ฟเวอร์ยังไม่มีไฟล์นี้

### 2.2 Healthcheck

| จุด | สถานะ |
|---|---|
| `postgres` healthcheck ใน compose | **มี** — `pg_isready -U postgres -d course_advisor`, interval 10s, timeout 5s, retries 10 |
| สถานะจริงตอนนี้ | `healthy` |
| `webapi` HEALTHCHECK ใน Dockerfile | มี — เรียก `/healthz` ภายในคอนเทนเนอร์ ตัดสินจาก `r.ok` |

**`depends_on: postgres: condition: service_healthy` ที่เพิ่มใน compose ใหม่ใช้งานได้** เพราะ postgres มี healthcheck อยู่แล้วจริง ไม่ใช่สืบทอดจาก image

### 2.3 Routes

`/healthz` ของ webapi ตอนนี้คืน:

```json
{"status":"ok","routes":["/api/sci-connect-news-detail","/api/sci-connect-news","/api/admin/extract-file","/api/admin/ingest","/api/admin/sync-sci-news"]}
```

หลัง deploy จะเพิ่ม `authConfigured`, `dbConfigured`, `db` และเปลี่ยน `routes` จาก array ของ string เป็น array ของ `{route, level}` — **เป็นการเปลี่ยนสัญญา** แต่ความเสี่ยงต่ำเพราะ

- Docker HEALTHCHECK ตัดสินจาก `r.ok` เท่านั้น ไม่อ่านเนื้อหา
- Caddy **ไม่ได้ route `/healthz` ไปที่ webapi** เส้นทางนี้เข้าถึงได้เฉพาะภายใน Docker network

การจัดเส้นทางของ Caddy (อ่านจาก `Caddyfile` จริง):

| เส้นทาง | ปลายทาง |
|---|---|
| `/api/chat` | `backend:8000` |
| `/api/sci-connect-news*` | `webapi:3001` |
| `/api/admin/*` | `webapi:3001` |
| `/api/*` (ที่เหลือ) | `backend:8000` |
| อื่น ๆ | `frontend:3000` |

### 2.4 ความพร้อมของ PostgreSQL

- สถานะ `healthy` ต่อเนื่อง 7 สัปดาห์
- ดิสก์เหลือ **62 GB จาก 97 GB** (ใช้ไป 37%) เพียงพอสำหรับ build
- Docker: images 11.17 GB · build cache 7.199 GB (เรียกคืนได้ 5.386 GB ถ้าต้องการพื้นที่)

---

## 3. Migration 005 / 006 และ S1 Mapping

ตรวจจาก catalog ของ production โดยตรง (SELECT อย่างเดียว)

| สิ่งที่ตรวจ | ผล |
|---|---|
| คอลัมน์ `public.users.supabase_user_id` | มี · `uuid` · nullable · **ไม่มี default** |
| index `uq_users_supabase_user_id` | มี |
| นิยาม index | `CREATE UNIQUE INDEX … USING btree (supabase_user_id) WHERE (supabase_user_id IS NOT NULL)` — partial unique ตามที่ออกแบบ |
| schema `web` | มี |
| ตารางใน schema `web` | 5 ตาราง |
| role `advisor_web` | มี |

S1 Mapping:

| รายการ | จำนวน |
|---|---|
| `public.users` ทั้งหมด | 201 |
| ผูก `supabase_user_id` แล้ว | **1** |
| ผูกแล้วและ `is_active` | **1** |

ตรงกับที่บันทึกไว้ตอน apply — ผูกไว้หนึ่งบัญชีและบัญชีนั้นยังใช้งานอยู่ ไม่มีแถวที่ผูกแล้วแต่ถูกปิด ไม่มีการผูกเกินมา

> ไม่ได้แสดงค่า UUID หรืออีเมลของผู้ใช้ในรายงานนี้ตามข้อกำหนด

---

## 4. สิทธิ์ของ advisor_web และการเชื่อมต่อ

ตรวจจาก catalog โดยไม่ใช้รหัสผ่านและไม่เปิดเผยรหัสผ่าน

### 4.1 คุณสมบัติของ role

| คุณสมบัติ | ค่า |
|---|---|
| `rolcanlogin` | `t` |
| `rolsuper` | `f` |
| `rolcreatedb` | `f` |
| `rolcreaterole` | `f` |
| `rolbypassrls` | `f` |

### 4.2 สิทธิ์บน `public.users` — จุดสำคัญที่สุด

| การตรวจ | ผล | ที่ต้องการ |
|---|---|---|
| คอลัมน์ที่ SELECT ได้ | `id`, `is_active`, `supabase_user_id` (3 คอลัมน์) | ถูกต้อง |
| `has_column_privilege(… 'email', 'SELECT')` | **`f`** | อ่าน email ไม่ได้ |
| `has_table_privilege(… 'SELECT')` | **`f`** | `SELECT *` ต้องล้มด้วย `42501` |
| INSERT / UPDATE / DELETE บน `public.users` | **ไม่มีเลย** | ถูกต้อง |

### 4.3 สิทธิ์บน schema `web`

| ตาราง | สิทธิ์ |
|---|---|
| `web.external_news` | SELECT |
| `web.ai_settings` | SELECT, UPDATE |
| `web.knowledge_articles` | SELECT, INSERT, UPDATE |
| `web.news` | SELECT, INSERT, UPDATE |
| `web.site_courses` | SELECT, INSERT, UPDATE |

**ไม่มี DELETE บนตารางใดเลย** · สิทธิ์ทั้งหมดเป็นระดับคอลัมน์ 125 รายการ สอดคล้องกับ 12 รายการระดับตาราง

### 4.4 การเชื่อมต่อ

| การตรวจ | ผล |
|---|---|
| `has_database_privilege('advisor_web','course_advisor','CONNECT')` | `t` |
| `has_schema_privilege('advisor_web','public','USAGE')` | `t` |

**ไม่ได้ทดสอบ login จริง** เพราะต้องใช้รหัสผ่านซึ่งยังไม่มีใน `.env` และการทดสอบนั้นต้องทำตอน deploy ไม่ใช่ตอน preflight

---

## 5. `webapi/api/` — ข้อที่ทำให้ BLOCKED

### 5.1 สิ่งที่พบ

`webapi/Dockerfile` มีบรรทัด `COPY api ./api` และ `server.mjs` โหลด 5 โมดูลจากโฟลเดอร์นี้:

```
./api/sci-connect-news-detail.js
./api/sci-connect-news.js
./api/admin/extract-file.js
./api/admin/ingest.js
./api/admin/sync-sci-news.js
```

แต่:

| การตรวจ | ผล |
|---|---|
| `webapi/api/` ใน worktree `mko-phase2` | **ไม่มี** |
| `webapi/api/` ใน worktree `mko-phase1` | **ไม่มี** |
| `git ls-files webapi/api` | **0 ไฟล์** |
| `git log --all -- webapi/api` | **ไม่มีประวัติเลย** |
| ถูก `.gitignore` ไหม | **ใช่ — `.gitignore:49` `webapi/api/`** (ดูหมายเหตุแก้ไขด้านล่าง) |
| มี `.dockerignore` ไหม | **ไม่มี** |

> ### ⚠️ แก้ไขหลังการตรวจรอบถัดไป (10 ต.ค. 2569)
>
> ตอนทำ preflight รอบแรก บรรทัดนี้เคยเขียนว่า "ไม่ถูก `.gitignore`" ซึ่ง **ผิด**
>
> สาเหตุ: รัน `git check-ignore -v webapi/api` ขณะที่โฟลเดอร์ยังไม่มีอยู่จริง กฎใน
> `.gitignore` คือ `webapi/api/` ซึ่งปิดท้ายด้วย `/` จึงตรงกับไดเรกทอรีเท่านั้น
> เมื่อไม่มีไดเรกทอรีให้ตรวจ คำสั่งจึงไม่คืนอะไร และผลว่างนั้นถูกอ่านว่า "ไม่ถูก ignore"
>
> เมื่อกู้ไฟล์ลงมาจริงแล้วตรวจซ้ำได้ผลว่า `.gitignore:49:webapi/api/`
>
> **ข้อเท็จจริงคือโฟลเดอร์นี้ถูกยกเว้นโดยตั้งใจตั้งแต่ commit `589cff5`** พร้อมคอมเมนต์
> ว่าเป็นโค้ดของทีมที่ดูแลหน้าเว็บซึ่งอยู่คนละรีโปและคนละเจ้าของ และ `webapi/README.md`
> ที่อยู่ใน git อยู่แล้วก็มีขั้นตอนคัดลอกก่อน build ครบถ้วน
>
> รายละเอียดเต็มอยู่ใน `M3_WEBAPI_SOURCE_RECOVERY_RESULT.md`
| บนเครื่อง production | **มี 10 ไฟล์** |

ไฟล์ที่มีอยู่บน production เท่านั้น:

```
webapi/api/_lib/adminAuth.js
webapi/api/_lib/aiConfig.js
webapi/api/_lib/fileExtract.js
webapi/api/_lib/ingest.js
webapi/api/_lib/rag.js
webapi/api/admin/extract-file.js
webapi/api/admin/ingest.js
webapi/api/admin/sync-sci-news.js
webapi/api/sci-connect-news-detail.js
webapi/api/sci-connect-news-detail.js
webapi/api/sci-connect-news.js
```

### 5.2 ทำไมถึงบล็อก

1. **Build จาก repo ล้วน ๆ ทำไม่ได้** — `COPY api ./api` จะล้มด้วย build error เพราะไม่มีโฟลเดอร์ใน build context
2. **ไม่มีสำเนาที่ไหนเลยนอกจากเครื่อง production เครื่องเดียว** ไม่อยู่ใน git ไม่อยู่ใน release tarball ที่ตรวจดู ถ้าไฟล์หายคือกู้ไม่ได้ และ 5 เส้นทางของ webapi จะ build ใหม่ไม่ได้ตลอดไป
3. **วิธี deploy ที่แทนที่ทั้งโฟลเดอร์จะทำลายไฟล์ถาวร** เช่น `rm -rf webapi && scp -r` หรือ `git archive` แล้วแตกทับ

ข้อนี้ไม่ได้เกิดจากงาน M3 — มีมาก่อนแล้ว แต่ **ข้อ 5 ของ preflight ถามตรง ๆ ว่าของจริงจะนำมาใช้ตอน build ได้ครบไหม คำตอบคือไม่ได้** จึงต้องจัดให้เรียบร้อยก่อน

> ### ⚠️ แก้ไขหลังการตรวจรอบถัดไป (10 ต.ค. 2569)
>
> ข้อ 1 และ 3 ยังจริง แต่ต้องอ่านใหม่ว่า **ข้อ 1 เป็นพฤติกรรมที่ตั้งใจ ไม่ใช่ข้อบกพร่อง** —
> `webapi/README.md` ระบุไว้ตั้งแต่ต้นว่าต้องคัดลอก `api/` จากรีโปของทีมออกแบบมาก่อน build เสมอ
>
> **ข้อ 2 แก้แล้ว** — สำรองออกมาเป็น `webapi-api-backup-20261009T204112.tar.gz`
> ตรวจ SHA256 ครบทั้ง 10 ไฟล์ และทดสอบกู้คืนแล้ว
>
> เจ้าของเลือก **ทางเลือก A** คือคงสถานะ gitignore ไว้ตามข้อตกลงเดิม ไม่นำโค้ดของทีม
> frontend เข้ารีโปนี้ และใช้ไฟล์สำรองเป็นหลักประกันแทน

### 5.3 ไม่พบ temporary stub

ตรวจแล้วว่าไฟล์บน production เป็นโค้ดจริงไม่ใช่ stub — `_lib/adminAuth.js` มีตรรกะตรวจสิทธิ์เต็ม และ handler ทั้ง 3 ตัวเรียกใช้จริง (ดูข้อ 6)

### 5.4 เงื่อนไขที่ต้องทำให้ครบก่อนปลดบล็อก

1. สำรอง `webapi/api/` ออกจากเครื่อง production มาเก็บไว้ที่อื่นก่อน (ยังไม่ต้องตัดสินใจเรื่อง git)
2. ตัดสินใจว่าจะนำเข้า version control หรือกำหนดแหล่งที่มาภายนอกให้ชัดเจนเป็นเอกสาร
3. เลือกวิธี deploy ที่ **คัดลอกเฉพาะไฟล์ที่เปลี่ยน** ลงใน `webapi/` เดิม ไม่ลบโฟลเดอร์ทิ้ง

---

## 6. ผลกระทบจาก Authorization Foundation ที่จะขึ้น Production ครั้งแรก

การ deploy M3 จะพา commit `cf4fb16` (authorization foundation) ขึ้นไปด้วยเป็นครั้งแรก เพราะ image ปัจจุบันสร้างตั้งแต่ 22 ก.ย. ซึ่งเก่ากว่า

### 6.1 วันนี้ production ปิดอยู่แล้ว ไม่ได้เปิดโล่ง

| เส้นทาง | ป้องกันโดย | ผลจริงที่ยิงทดสอบ |
|---|---|---|
| `/api/admin/extract-file` | `requireAdminUser` ใน handler | — |
| `/api/admin/ingest` | `requireAdminUser` ใน handler | `POST` ไม่มี token → **HTTP 401** |
| `/api/admin/sync-sci-news` | `requireAdminUser` ใน handler | — |
| `/api/sci-connect-news` | ไม่ต้องมีสิทธิ์ (สาธารณะโดยเจตนา) | `GET` → **HTTP 200** |
| `/api/sci-connect-news-detail` | ไม่ต้องมีสิทธิ์ | — |

### 6.2 ด่านใหม่ใช้เกณฑ์เดียวกับของเดิมเป๊ะ

| | `_lib/adminAuth.js` (ของเดิม) | `auth.mjs` ระดับ EDITOR (ของใหม่) |
|---|---|---|
| role ที่ยอม | `['admin', 'editor']` | `['admin', 'editor']` |
| status ที่ยอม | `approved` เท่านั้น | `approved` เท่านั้น |
| ไม่มี token | 401 | 401 |
| role/status ไม่ผ่าน | 403 | 403 |

**เกณฑ์ตรงกันทุกข้อ จึงไม่มีผู้ใช้ที่เคยเข้าได้แล้วถูกล็อกออก** ด่านใหม่ทำงานก่อน handler แล้ว handler ยังตรวจซ้ำอีกชั้น เป็นการป้องกันสองชั้นที่เข้มเท่าเดิมหรือเข้มกว่า ไม่หลวมลง

### 6.3 ผลข้างเคียงที่ต้องรู้

**คำขอ `/api/admin/*` จะเรียก Supabase สองรอบต่อหนึ่งคำขอ** — ด่านกลางเรียก `auth.getUser()` + อ่าน profile หนึ่งรอบ แล้ว `requireAdminUser` ใน handler เรียกอีกรอบ เพราะ handler เป็นโค้ดที่คัดลอกมาทั้งอย่างโดยไม่แก้

ผลกระทบ: latency ของเส้นทางผู้ดูแลเพิ่มขึ้นประมาณหนึ่งเท่าของเวลาที่เรียก Supabase และใช้โควตา Supabase เพิ่มขึ้น เส้นทางสาธารณะไม่ได้รับผลกระทบเพราะระดับ `PUBLIC` ไม่เรียกตัวตนเลย

ยังไม่ใช่ปัญหาที่ต้องแก้ก่อน deploy เพราะเส้นทางผู้ดูแลมีปริมาณน้อยและไม่ใช่เส้นทางที่ผู้ใช้ทั่วไปเรียก แต่ควรบันทึกไว้และถอด `requireAdminUser` ออกจาก handler เมื่อมั่นใจว่าด่านกลางทำงานถูกต้องแล้ว

### 6.4 ยังเขียน created_by / updated_by ไม่ได้

`G3_API_ENFORCEMENT_PENDING_B1` ยังเปิดอยู่ — ยังไม่มี write endpoint ที่เรียก `authorFieldsFor` การ deploy รอบนี้จึงไม่เปลี่ยนพฤติกรรมการเขียนข้อมูลใด ๆ

---

## 7. Backup, Image Tag, Rollback และ Smoke Tests

### 7.1 Backup

มีแบบแผนที่ทำมาแล้วจริง สำรองก่อนทุกการเปลี่ยนแปลงที่เสี่ยง:

| ไฟล์ | ขนาด | เมื่อ |
|---|---|---|
| `backup-before-006-20261003-102047.dump` | 52 MB | 3 ต.ค. 10:20 |
| `backup-before-s1-mapping-20261003-132826.dump` | 52 MB | 3 ต.ค. 13:28 |

และมีชุดเก่าใน `/home/ubuntu/backups/` อีกหลายไฟล์

**ไม่มี cron หรือ systemd timer ที่สำรองอัตโนมัติ** — ทุกครั้งเป็นการสั่งเอง เป็นสภาพเดิมไม่ใช่ปัญหาที่ M3 สร้างขึ้น แต่หมายความว่าต้องสั่งสำรองเองก่อน deploy

> **M3 ไม่แตะข้อมูล** ไม่มี migration ใหม่ ไม่มี UPDATE/INSERT การสำรองฐานข้อมูลรอบนี้จึงเป็นการกันไว้ ไม่ใช่สิ่งที่จำเป็นตามเนื้องาน · สิ่งที่ **ต้อง** สำรองจริง ๆ คือ `webapi/api/` ตามข้อ 5

### 7.2 Image Tag — มีช่องโหว่

| บริการ | tag ที่มี |
|---|---|
| backend | `:2fdc6f2`, `:latest`, `:rollback-pre-phase3d`, `:rollback-17abce0`, `:rollback-589cff5`, `:rollback-6937a71`, `:rollback-f2450a0`, `:rollback-fe6c57f`, `:rollback-6762333` |
| frontend | `:2fdc6f2`, `:rollback-pre-phase3d` |
| **webapi** | **`:latest` อย่างเดียว** |

webapi ไม่มี tag ตาม commit และไม่มี rollback tag เลย **ถ้า build ทับตอนนี้ image ที่ทำงานได้อยู่จะหายไปทันทีและไม่มีอะไรให้ย้อนกลับ**

ต้อง tag image ปัจจุบันไว้ก่อน build เช่น

```bash
docker tag course-advisor-system-webapi:latest course-advisor-system-webapi:rollback-pre-m3
```

ยืนยันว่า tag ติดแล้วด้วย `docker images | grep webapi` ก่อนจะ build อะไรทั้งสิ้น

### 7.3 Rollback

เส้นทางย้อนกลับที่ใช้ได้จริงหลังทำข้อ 7.2 แล้ว:

1. `docker tag course-advisor-system-webapi:rollback-pre-m3 course-advisor-system-webapi:latest`
2. คืน `docker-compose.prod.yml` เป็นเวอร์ชัน sha256 `d76afeef…0926c8`
3. `docker compose -f docker-compose.prod.yml up -d webapi`
4. ลบ `ADVISOR_WEB_PASSWORD` ออกจาก `.env` (ไม่จำเป็นต่อการย้อนกลับ แต่ควรทำให้สถานะสะอาด)

**ไม่ต้องย้อน migration** เพราะ 006 เป็น additive ล้วน และ `server.mjs` รุ่นเก่าไม่รู้จักคอลัมน์ `supabase_user_id` อยู่แล้ว

**ไม่ต้องย้อน role `advisor_web`** เพราะรุ่นเก่าไม่ได้ใช้

### 7.4 Smoke Tests ที่ควรรันหลัง deploy

| # | การทดสอบ | ผลที่ต้องได้ |
|---|---|---|
| 1 | `docker ps` ดู webapi | `healthy` ภายใน start-period 10s + 3 retries |
| 2 | `/healthz` ในคอนเทนเนอร์ | `status=ok`, `authConfigured=true`, `dbConfigured=true`, `db` ไม่ใช่ `not-configured` |
| 3 | `GET /api/sci-connect-news` ผ่านเว็บจริง | HTTP 200 และมีเนื้อหาข่าว |
| 4 | `GET /api/sci-connect-news-detail` ผ่านเว็บจริง | HTTP 200 |
| 5 | `POST /api/admin/ingest` ไม่มี token | HTTP 401 (เท่าเดิม ไม่ใช่ 500) |
| 6 | `POST /api/admin/ingest` ด้วย token ของบัญชี admin ที่ approved | ไม่ใช่ 401/403 — ยืนยันว่าด่านใหม่ไม่ล็อกคนที่เคยเข้าได้ |
| 7 | `GET /api/chat` | ยังไปที่ backend ปกติ ไม่กระทบ |
| 8 | log ของ webapi | มีบรรทัด `ตั้งค่าฐานข้อมูลแล้ว:` และ **ไม่มีรหัสผ่านโผล่** |
| 9 | ฝั่ง PostgreSQL | `SELECT count(*) FROM pg_stat_activity WHERE usename='advisor_web'` มากกว่า 0 และไม่เกิน `max` ของ pool (5) |

ข้อ 6 สำคัญที่สุดเพราะเป็นข้อเดียวที่พิสูจน์ว่า authorization foundation ไม่ทำให้ผู้ดูแลเข้าระบบไม่ได้ — **ต้องเตรียมบัญชีทดสอบไว้ล่วงหน้า**

ข้อ 5 ต้องแยกให้ออกว่า 401 ที่ได้มาจากด่านตรวจ ไม่ใช่ 500 ที่แปลว่าคอนเทนเนอร์พัง

---

## 8. ความเสี่ยงจาก UUID ใน test fixture และ `docs/DEPLOY_WEB.md`

### 8.1 UUID ใน test fixture

`webapi/auth.test.mjs:480` ใช้ค่า uuid ค่าหนึ่งเป็น `userId` ในชุดทดสอบ ซึ่ง **หัว 8 ตัวและท้าย 12 ตัวตรงกับ path ไฟล์จริงบน Supabase Storage** ที่บันทึกใน `docs/SUPABASE_LIVE_VERIFICATION.md:554` — ตรงกลางถูกแทนด้วยศูนย์ไว้แล้ว เหลือ hex จริง 20 จาก 32 ตัว

> ไม่แสดงค่าในรายงานนี้ตามกฎ "ห้ามแสดง UUID เต็มถ้าไม่จำเป็น" — ดูค่าได้ที่ตำแหน่งไฟล์ที่อ้างไว้

**ผลกระทบต่อ rollout: ไม่มี**

| เหตุผล | รายละเอียด |
|---|---|
| ไม่เข้า image | Dockerfile คัดลอกเฉพาะ `server.mjs auth.mjs db.mjs` — `*.test.mjs` ไม่ถูกคัดลอกโดยเจตนา |
| ไม่ใช่ของใหม่ | อยู่ใน HEAD ตั้งแต่ commit ก่อนหน้า ไม่ได้อยู่ใน diff ของ M3 |
| ไฟล์ที่มีค่าต้นทางก็ถูก track แล้ว | `docs/SUPABASE_LIVE_VERIFICATION.md` commit ไปก่อนแล้ว |

เป็นเรื่องสุขอนามัยของ repo ไม่ใช่ความเสี่ยงของการ deploy · แก้ทีหลังได้ แต่ต้องเข้าใจว่าการแก้ไฟล์ไม่ลบค่าออกจากประวัติ git

### 8.2 `docs/DEPLOY_WEB.md` ที่ไม่มีอยู่

`docker-compose.prod.yml:169` อ้างถึงไฟล์นี้ในคอมเมนต์ แต่ไม่มีในรีโป

**ผลกระทบต่อ rollout: ไม่มี** เป็นคอมเมนต์ YAML ไม่กระทบการทำงาน และเป็นบรรทัดเดิมที่ M3 ไม่ได้แตะ

แต่มีผลทางอ้อมที่ควรรู้ — บรรทัดนั้นเขียนว่า frontend "ต้อง build แล้วคัดลอกขึ้นมาเอง (ดู `docs/DEPLOY_WEB.md`)" ซึ่งเป็นเอกสารขั้นตอน deploy ที่หายไป **ประกอบกับข้อ 5 แล้วเห็นรูปแบบเดียวกัน คือขั้นตอน deploy ของฝั่งเว็บพึ่งพาความรู้ที่ไม่ได้อยู่ในรีโป**

---

## 9. สรุปสิ่งที่ต้องทำก่อนปลดบล็อก

| # | สิ่งที่ต้องทำ | ความจำเป็น | สถานะ (10 ต.ค. 2569) |
|---|---|---|---|
| 1 | สำรอง `webapi/api/` (10 ไฟล์) ออกจาก production มาเก็บนอกเครื่อง | **บังคับ** | **เสร็จ** — `webapi-api-backup-20261009T204112.tar.gz` ตรวจ SHA256 และทดสอบกู้คืนแล้ว |
| 2 | ตัดสินใจและบันทึกว่า `webapi/api/` จะอยู่ใน version control หรือมาจากแหล่งใด | **บังคับ** | **เสร็จ** — เจ้าของเลือกทางเลือก A · บันทึกที่มา ขั้นตอน restore การตรวจ SHA256 และขั้นตอน build ไว้ใน `webapi/README.md` แล้ว |
| 3 | `docker tag course-advisor-system-webapi:latest …:rollback-pre-m3` และยืนยันว่าติดแล้ว | **บังคับ** | **ยังไม่ทำ** — เป็นการเขียนสถานะ docker บน production ต้องให้เจ้าของสั่ง |
| 4 | กำหนดวิธี deploy ที่คัดลอกเฉพาะไฟล์ที่เปลี่ยน ไม่ลบ `webapi/` ทิ้ง | **บังคับ** | **เสร็จบางส่วน** — ขั้นตอนอยู่ใน `webapi/README.md` แล้ว เหลือยืนยันว่าสคริปต์ deploy จริงทำตาม |
| 5 | เตรียมบัญชี admin ที่ `approved` ไว้ทดสอบ smoke test ข้อ 6 | **บังคับ** | **ยังไม่ทำ** — ต้องให้เจ้าของเตรียม |
| 6 | สร้าง `ADVISOR_WEB_PASSWORD` และใส่ `.env` production | บังคับ (ขั้น deploy) | ยังไม่ทำ |
| 7 | เตรียมคัดลอก `package-lock.json` ขึ้นเซิร์ฟเวอร์ (ยังไม่มี และ `npm ci` ต้องใช้) | บังคับ (ขั้น deploy) | ยังไม่ทำ |
| 8 | สำรองฐานข้อมูลก่อน deploy | แนะนำ (M3 ไม่แตะข้อมูล) | ยังไม่ทำ |
| 9 | เปลี่ยน UUID ใน test fixture เป็นค่าสังเคราะห์ | ภายหลัง | ยังไม่ทำ |
| 10 | เขียน `docs/DEPLOY_WEB.md` หรือลบการอ้างอิงออก | ภายหลัง | ยังไม่ทำ |
| 11 | เพิ่ม `.dockerignore` — `node_modules/` ถูกส่งเข้า build context ทั้งก้อน | ภายหลัง | ยังไม่ทำ |

### เพิ่มเติม — พิสูจน์แล้วว่า build ผ่าน

สิ่งที่ฉบับแรกยังพิสูจน์ไม่ได้ ตอนนี้ทำแล้วในเครื่อง local (ไม่แตะ production):

| การตรวจ | ผล |
|---|---|
| `docker build -t webapi-m3-localtest:dba865b` | **ผ่าน** — รวมถึงขั้น `COPY api ./api` ที่เคยจะล้มแน่นอน |
| ไฟล์ใน image | `server.mjs`, `auth.mjs`, `db.mjs` ครบ · `api/` ครบ 10 ไฟล์ · ไม่มี `*.test.mjs` |
| hash ของ `api/` ใน image | `2b67e0f4…fa8fcd` ตรงกับ production ทุกไบต์ |
| import ใน image | **7/7** |
| รัน container จริง | `/healthz` ตอบ `status: ok`, `authConfigured: true`, ระดับสิทธิ์ครบทุกเส้นทาง และไม่ล้มเมื่อไม่มีฐานข้อมูล |
| regression | 82/82 |

ดู `M3_BUILD_VERIFICATION_RESULT.md`

---

## ภาคผนวก — คำสั่งที่ใช้ตรวจ (READ-ONLY ทั้งหมด)

```bash
# โครงสร้างและ image
docker ps --format "{{.Names}}\t{{.Image}}\t{{.Status}}"
docker image inspect course-advisor-system-webapi --format '{{.Id}} | created={{.Created}}'
docker inspect course-advisor-system-webapi-1 \
  --format '{{index .Config.Labels "com.docker.compose.project.config_files"}}'

# ฐานข้อมูล — SELECT เท่านั้น
psql -c "SELECT count(*) FROM public.users WHERE supabase_user_id IS NOT NULL"
psql -c "SELECT indexdef FROM pg_indexes WHERE indexname='uq_users_supabase_user_id'"
psql -c "SELECT column_name, privilege_type FROM information_schema.column_privileges
         WHERE grantee='advisor_web'"
psql -c "SELECT has_column_privilege('advisor_web','public.users','email','SELECT')"

# เส้นทางจริง
curl -s -o /dev/null -w '%{http_code}' https://stpnru-advisor.duckdns.org/api/sci-connect-news
curl -s -o /dev/null -w '%{http_code}' -X POST https://stpnru-advisor.duckdns.org/api/admin/ingest
```

ไม่มีคำสั่งใดที่เขียน production, ไม่มี `docker build`, ไม่มี `docker compose up`, ไม่มีการแก้ `.env` และไม่มีการเขียนฐานข้อมูลหรือ Supabase
