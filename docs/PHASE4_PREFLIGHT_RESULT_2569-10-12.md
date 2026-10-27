# Phase 4 — ผล preflight (อ่านอย่างเดียว)

| รายการ | ค่า |
|---|---|
| วันที่ | 12 ตุลาคม 2569 |
| เซิร์ฟเวอร์ | `ubuntu@161.118.237.37` · hostname **`stpnru`** · Linux 6.8.0-1054-oracle |
| ขอบเขต | **อ่านอย่างเดียว** — ไม่รัน migration · ไม่ `--apply` · ไม่แตะคอนเทนเนอร์ · ไม่แตะ Supabase |
| ผล | **ยังไม่พร้อม deploy** — มี 4 ข้อต้องตัดสินใจหรือแก้ก่อน (ข้อ 9) |

คำสั่งที่รันเป็นการอ่านทั้งหมด: `docker compose config` · `docker inspect` · `docker exec ... id` · `cat` · `stat` · `getent` · `psql` แบบ `select` จาก `information_schema`

---

## 1. backend build context และ image ที่ใช้จริง

| รายการ | ค่าจริงบนเซิร์ฟเวอร์ |
|---|---|
| project name | `course-advisor-system` ✅ |
| compose ที่โปรเจกต์ใช้จริง | **ตรงทั้งสี่ไฟล์** ตามที่แผนเขียนไว้ (ยืนยันด้วย `docker compose ls`) |
| `backend.build.context` | `/home/ubuntu/course-advisor-system` |
| `backend.build.dockerfile` | `backend/Dockerfile` |
| `backend.image` | **`course-advisor-system-backend:2fdc6f2`** — มี tag ชัดเจน |
| `webapi.image` | ไม่ระบุใน compose → compose ตั้งชื่อเอง เป็น `course-advisor-system-webapi` |

ไฟล์ compose ทั้งสี่ **มีอยู่จริงครบ**

```
/home/ubuntu/course-advisor-system/docker-compose.prod.yml
/home/ubuntu/course-advisor-system/docker-compose.staging.yml
/home/ubuntu/release-2fdc6f2/compose.pin-backend-2fdc6f2.yml
/home/ubuntu/release-2fdc6f2/compose.pin-frontend-2fdc6f2.yml
```

## 2. image ID ของคอนเทนเนอร์ปัจจุบัน

| รายการ | ค่า |
|---|---|
| container id | `fda31caa20c4` |
| `Config.Image` | `course-advisor-system-backend:2fdc6f2` |
| **image ID (`$OLD_ID`)** | **`sha256:4a45677ec010fc076e283b1e556bd4c1b0b25bc66786b32ec6f64a76ad0cca46`** |
| tag `2fdc6f2` ชี้ไป | **ID เดียวกันเป๊ะ** — tag ไม่ได้ถูกย้าย ใช้เป็นต้นทางย้อนกลับได้ |
| อายุ | `Up 12 days` |

สถานะคอนเทนเนอร์ทั้งหมด

| service | สถานะ |
|---|---|
| backend | Up 12 days |
| frontend | Up 12 days |
| webapi | Up 5 hours (healthy) |
| caddy | Up 2 weeks |
| postgres | Up 7 weeks (healthy) |
| ollama | Up 7 weeks (healthy) |

## 3. ตำแหน่ง frontend ที่ Caddy เสิร์ฟจริง

**มีสองทางเข้า และ Phase 4 เกี่ยวกับทางแรกเท่านั้น**

| ทางเข้า | เสิร์ฟอะไร | ที่มา |
|---|---|---|
| **`{$SITE_DOMAIN}`** (ทางที่ผู้ใช้เข้า) | ไฟล์นิ่งจาก **`/srv/web`** | bind mount `/home/ubuntu/course-advisor-system/web` → `/srv/web` **(ro)** |
| `:80` ด้วยเลข IP | `reverse_proxy frontend:3000` — หน้าเว็บเดิมของหลังบ้าน | คนละ service ไม่เกี่ยวกับงานนี้ |

**`$WEB` = `/home/ubuntu/course-advisor-system/web`** · mount เป็น `ro` จึงต้องวางไฟล์ **บน host** ตามที่แผนเขียนไว้ ✅

## 4. volumes และ uid/gid (ไม่เดา — อ่านจากของจริง)

| mount | เป้าหมาย | โหมด | สถานะ |
|---|---|---|---|
| `/home/ubuntu/course-advisor-system/documents` | `/srv/documents` | **ro** | ✅ ตามที่ต้องการ |
| `/home/ubuntu/course-advisor-system/staging/crawl` | `/srv/staging` | ro | มาจาก `docker-compose.staging.yml` ไม่แตะ |
| — | `/srv/uploads` | — | ❌ **ยังไม่มี** |

### uid/gid ที่วัดได้จริง — **ไม่ใช่ 1000 อย่างที่แผนเดิมเขียน**

| ที่ | uid:gid | ชื่อ |
|---|---|---|
| **โปรเซสใน backend container** | **1000:1000** | `appuser` (`Config.User` = `appuser`) |
| **ผู้ใช้บน host** | **1001:1001** | `ubuntu` |
| host uid 1000 | 1000:1000 | **`opc`** — ผู้ใช้อื่นที่ติดมากับ image ของ Oracle |
| `/srv/documents` มองจากในคอนเทนเนอร์ | 1001:1001 · 755 | เป็นของ `ubuntu` ของ host · อ่านได้เพราะ 755 |

**ความหมายที่สำคัญ** — แผนเดิมเขียน `chown -R 1000:1000` ซึ่ง **ได้ผลถูกโดยบังเอิญ** (1000 ตรงกับ `appuser` ในคอนเทนเนอร์) แต่จะทำให้โฟลเดอร์กลายเป็นของ `opc` บน host และผู้ใช้ `ubuntu` **เขียนไม่ได้** ถ้า mode เป็น 755

ที่ถูกคือ **เจ้าของ = uid ของคอนเทนเนอร์ · กลุ่ม = gid ของ `ubuntu` · mode 775** เพื่อให้ทั้งสองฝั่งเขียนได้ และ **อ่านค่า uid จากคอนเทนเนอร์จริง ไม่พิมพ์เลขลงไป** (แก้ไว้ในแผนแล้ว)

## 5. Caddy routing ที่โหลดใช้งานจริง

ไฟล์ในคอนเทนเนอร์กับบน host **md5 ตรงกัน** (`0e6b6f1d…`) → ที่โหลดอยู่คือไฟล์บนดิสก์จริง

| ลำดับ | บล็อก | ไปที่ |
|---|---|---|
| 1 | `handle /api/chat` | `rewrite * /chat-web` → `backend:8000` |
| 2 | `handle /api/sci-connect-news*` | `webapi:3001` |
| 3 | `handle /api/admin/*` | `webapi:3001` |
| 4 | **`handle /api/*`** | **`uri strip_prefix /api` → `backend:8000`** |
| 5 | `handle /assets/*` | `/srv/web` + cache 1 ปี |
| 6 | `handle` (ที่เหลือ) | `/srv/web` + `try_files {path} /index.html` |

**ยืนยันว่า Caddyfile ไม่ต้องแก้** ✅ — เส้นทางใหม่ทุกเส้นตกที่บล็อก 4

| เส้นทางใหม่ | ไปถึง backend ไหม |
|---|---|
| `/api/site/*` · `/api/site-admin/*` · `/api/auth/*` · `/api/uploads/*` · `/api/extract-file` | ✅ ตกบล็อก 4 ทั้งหมด |

> ข้อควรรู้ที่ไม่กระทบตอนนี้ — `/api/admin/*` ถูกจับโดยบล็อก 3 ไปที่ `webapi` ก่อนถึงบล็อก 4
> เส้นทางใหม่ทั้งหมดของเราไม่ได้ขึ้นต้นด้วย `/api/admin/` จึงไม่ชนกัน
> (`/api/auth/admin/reset-link` ขึ้นต้นด้วย `/api/auth/` **ไม่ชน**)

## 6. ตัวแปร — มีครบไหม (ไม่แสดงค่า)

### มีแล้วบนเซิร์ฟเวอร์

`DATABASE_URL` · `JWT_SECRET` · `SITE_DOMAIN` · `POSTGRES_PASSWORD` · `ADVISOR_API_PASSWORD` · `ADVISOR_INGEST_PASSWORD` · `ADVISOR_WEB_PASSWORD` · `OLLAMA_BASE_URL` · `LLM_*` · `EMBED_*` · `GEMINI_*` · `CHAT_TOP_K` · `STRUCTURED_ANSWERS` · `DOCUMENTS_DIR` · `CRAWL_STAGING_DIR`

ตรวจว่ามีค่าจริง (วัดความยาวเท่านั้น ไม่พิมพ์ค่า): `SITE_DOMAIN` 26 · `POSTGRES_PASSWORD` 64 · `ADVISOR_API_PASSWORD` 64 · `ADVISOR_INGEST_PASSWORD` 64 · `JWT_SECRET` 64 — **ครบและไม่ว่าง**

### ยังไม่มี แต่ compose มีค่าตั้งต้นให้

| ตัวแปร | ค่าตั้งต้น | พอไหม |
|---|---|---|
| `UPLOADS_DIR` | `/srv/uploads` | ✅ พอ |
| `UPLOAD_MAX_BYTES` | `10485760` | ✅ พอ |
| `SMTP_HOST` · `SMTP_PORT` · `SMTP_USER` · `SMTP_PASSWORD` · `SMTP_FROM` | ว่าง | ส่งอีเมลไม่ได้ แต่ส่วนอื่นทำงาน — ดูข้อ 8 |
| **`PUBLIC_BASE_URL`** | **ว่าง** | ❌ **ต้องตั้ง** ไม่งั้นลิงก์รีเซ็ตรหัสเป็น `null` — ดูข้อ 8 |

### ไม่มีเลย — เจ้าของต้องเอามาจาก Supabase Dashboard

| ตัวแปร | หมายเหตุ |
|---|---|
| **`SUPABASE_DB_URL`** | ค้นทั้ง `.env` และ env ของทุกคอนเทนเนอร์แล้ว **ไม่มีที่ไหนเลย** |
| **`SUPABASE_SERVICE_ROLE_KEY`** | **ไม่มีที่ไหนเลย** |

บนเซิร์ฟเวอร์มีแต่ `VITE_SUPABASE_URL` และ `VITE_SUPABASE_ANON_KEY` ซึ่ง **ใช้ย้ายข้อมูลไม่ได้** (anon key อ่าน `auth.users` และ private bucket ไม่ได้)

## 7. ไฟล์และ dependencies ที่ต้องส่งจากเครื่องพัฒนา

**`/home/ubuntu/course-advisor-system` ไม่ใช่ git checkout** (ไม่มี `.git`) → ส่งเป็น archive ไม่ใช่ `git pull`

เทียบไฟล์ด้วย sha256 แบบปรับ CRLF→LF ก่อนเทียบ (ไม่งั้น CRLF ของ Windows จะดูเหมือนเปลี่ยนทุกไฟล์)

| กลุ่ม | จำนวน |
|---|---|
| มีบนเครื่องพัฒนาแต่ไม่มีบนเซิร์ฟเวอร์ | **50 ไฟล์** |
| เนื้อหาต่างกัน | **10 ไฟล์** |
| มีบนเซิร์ฟเวอร์แต่ไม่มีบนเครื่องพัฒนา | **0** — ไม่มีของที่จะหาย |

### แต่ 50 ไฟล์นั้น **ไม่ใช่ของ Phase 4 ทั้งหมด**

ในนั้นมีงานคนละก้อนที่ยังไม่ได้ deploy รวมอยู่ด้วย

| ก้อน | ไฟล์ | สถานะ |
|---|---|---|
| **Phase 4** (งานนี้) | 17 โมดูล + `007_web_auth.sql` + `pipeline/web/*` | พร้อม |
| **careers** (`web_compat.py`) | เส้นทางรายการอาชีพ | เตรียมไว้แล้ว **ยังไม่ deploy** — เจ้าของตัดสินใจว่าจะรวมไปไหม |
| **crawl review + MKO pipeline** | `crawl_review.py` · `staging_store.py` · `pipeline/mko/*` · `pipeline/crawl/*` · migration 001–006 | **ไม่ควรรวมในรอบนี้** |

**วงปิดของ Phase 4 ตรวจแล้ว: 17 โมดูล และ ไม่พึ่ง crawl/staging เลยแม้ไฟล์เดียว** → แยกส่งได้สะอาด

### dependencies

```diff
+ python-multipart>=0.0.9   # รับไฟล์อัปโหลด
+ pymupdf>=1.24             # แตกข้อความจาก PDF
+ python-docx>=1.1          # แตกข้อความจาก .docx
```

สถาปัตยกรรมเซิร์ฟเวอร์คือ **x86_64 / amd64** (ไม่ใช่ ARM ตามที่คอมเมนต์เก่าใน compose เขียนไว้) ทั้งสามแพ็กเกจมี wheel สำเร็จรูปสำหรับ amd64 — **ไม่ต้องคอมไพล์** · ดิสก์เหลือ **61 GB จาก 97 GB** พอสำหรับ build

### compose ที่ต้องอัปเดต

diff ระหว่างเซิร์ฟเวอร์กับเครื่องพัฒนา **ต่างกันเฉพาะส่วนที่ Phase 4 เพิ่ม ไม่มี drift อื่นเลย** — อัปเดตได้สะอาด

| ไฟล์ | ต้องเพิ่ม |
|---|---|
| `docker-compose.prod.yml` | env 8 ตัว (`UPLOADS_DIR` · `UPLOAD_MAX_BYTES` · `SMTP_*` 5 ตัว · `PUBLIC_BASE_URL`) + volume `./uploads:/srv/uploads` |
| อีกสามไฟล์ | **ไม่ต้องแก้** |

## 8. การกู้บัญชีเมื่อยังไม่มี SMTP — **ของเดิมใช้ไม่ได้จริง**

ตรวจแล้วพบว่าคำแนะนำเดิม ("ให้กดลืมรหัสผ่าน" / "ผู้ดูแลออกลิงก์ที่ `/api/auth/admin/reset-link`") **ขาดสองชิ้น**

| ปัญหา | หลักฐาน |
|---|---|
| `reset_url` เป็น **`null`** | โค้ดคืน `null` เมื่อ `PUBLIC_BASE_URL` ว่าง — ซึ่งบนเซิร์ฟเวอร์ว่างอยู่จริง |
| ลิงก์ชี้ไปหน้าที่ **ไม่มีอยู่** | `reset_url` ชี้ `/admin/reset-password` แต่ `src/App.jsx` **ไม่มีเส้นทางนี้** → SPA คืน `index.html` แล้ว token ไม่เคยถูกใช้ |

### แก้แล้วในรอบนี้

| สิ่งที่ทำ | ผล |
|---|---|
| สร้างหน้า `src/pages/Admin/ResetPassword.jsx` + ลงทะเบียนเส้นทาง `/admin/reset-password` | ลิงก์ใช้ได้จริง · ไม่มีด่านสิทธิ์โดยตั้งใจ เพราะคนที่ใช้คือคนที่เข้าระบบไม่ได้ |
| เพิ่ม `validateResetPasswordForm()` และ `readResetToken()` | ตรวจก่อนยิง · อ่าน token ได้แม้ผู้ใช้วางลิงก์มาทั้งอัน |
| เพิ่มชุดทดสอบ 14 ข้อ | **หน้าเว็บรวม 65 → 79 ข้อ ผ่านหมด** |
| ยืนยันในเบราว์เซอร์จริง | หน้าแสดงถูก · ลิงก์ไม่มี token ขึ้นเตือนทันที · รหัสไม่ตรง **ไม่ยิงคำขอเลย** · กรอกถูกยิง `POST /api/auth/password-reset/confirm` ถูกเส้นทาง |

**ลำดับการกู้บัญชีที่ใช้ได้จริง** (เรียงตามที่ควรใช้)

1. **ปกติไม่ต้องกู้เลย** — `import_accounts.py` ย้ายรหัสผ่านเดิมมาด้วย ทุกคนเข้าได้ด้วยรหัสเดิมทันที
2. ถ้าไม่มี admin เข้าได้ → เลื่อนสิทธิ์บัญชีที่ย้ายมาแล้วหนึ่งคนด้วย SQL (parameterized — ข้อ 9.2) แล้วคนนั้นเข้าด้วย **รหัสเดิมของตัวเอง**
3. ถ้าลืมรหัสจริง → admin เรียก `/api/auth/admin/reset-link` แล้วส่งลิงก์ให้ทางช่องทางอื่น · **ต้องตั้ง `PUBLIC_BASE_URL` ก่อน** ไม่งั้นได้แต่ token เปล่า

## 9. สิ่งที่ต้องตัดสินใจหรือแก้ก่อน deploy

| # | เรื่อง | ต้องทำอะไร |
|---|---|---|
| **1** | `main.py` ของผม `import crawl_review` ซึ่ง **ไม่มีบนเซิร์ฟเวอร์** | ถ้าส่ง `main.py` ไปตรง ๆ **backend จะขึ้นไม่ได้เลย** → ต้องเลือก: (ก) ส่ง `main.py` ฉบับ Phase 4-only **(แนะนำ)** หรือ (ข) รวมงาน crawl review ไปด้วย ซึ่งเพิ่มของที่ยังไม่ได้ตรวจรับเข้า production |
| **2** | `PUBLIC_BASE_URL` ว่าง | ตั้งเป็น `https://` + ค่า `SITE_DOMAIN` ก่อน deploy |
| **3** | `SUPABASE_DB_URL` · `SUPABASE_SERVICE_ROLE_KEY` ไม่มีบนเซิร์ฟเวอร์ | เจ้าของเอามาจาก Dashboard ตอนขั้น C |
| **4** | งาน careers จะรวมไปในรอบนี้ไหม | เจ้าของตัดสินใจ — ถ้ารวม ต้องส่ง `web_compat.py` ด้วย |

**ไม่มีอะไรที่ preflight เปลี่ยนบนเซิร์ฟเวอร์** — ทุกคำสั่งเป็นการอ่าน

## 10. สิ่งที่ยังไม่ได้ตรวจ และตรวจไม่ได้ในรอบนี้

| รายการ | เพราะอะไร | ปิดเมื่อไหร่ |
|---|---|---|
| จำนวนแถวและไฟล์ที่จะย้ายมาจาก Supabase | ไม่มี `SUPABASE_DB_URL` / service key | ขั้น C `--dry-run` |
| **URL ของ Supabase ที่ฝังใน `content` / `description`** | ข้อมูลยังไม่ได้นำเข้า `web.*` | ขั้น C3 (ดูข้อ 11) |
| `web.*` มีข้อมูลหรือยัง | ตารางยังว่าง (migration 005 สร้างโครงไว้แล้ว) | ขั้น C1 |
| `uploads` เขียนได้จริงจากในคอนเทนเนอร์ | ยังไม่มีทั้ง volume และโฟลเดอร์ | ขั้น B |

## 10.1 สภาพตาราง `public.users` บน production (ข้อมูลใหม่ที่เพิ่งรู้)

| รายการ | ค่าจริง |
|---|---|
| จำนวนผู้ใช้ | **202 คน** |
| `is_admin = true` | **1 คน** |
| `is_admin = false` | 201 คน |
| มี `supabase_user_id` | **1 แถว** |
| คอลัมน์ที่มีอยู่ | `id` `email` `password_hash` `full_name` `is_active` `is_admin` `created_at` `updated_at` `supabase_user_id` |
| คอลัมน์ที่ยังไม่มี | `role` · `status` · `password_scheme` · `failed_login_count` · `locked_until` — **migration 007 จะเพิ่ม ถูกต้องตามแผน** |

**ผลต่อขั้น A** — migration 007 จะตั้ง 202 แถวเป็น `status='approved'` · 1 คนเป็น `role='admin'` · 201 คนเป็น `role='user'`
**มี admin อยู่แล้วหนึ่งคน** จึงไม่ต้องใช้คำสั่งเลื่อนสิทธิ์ตอน bootstrap เว้นแต่คนนั้นเข้าไม่ได้

### รูปแบบ hash ของรหัสผ่านที่มีอยู่ — ตรวจแล้วว่า default ของ migration ถูก

| รูปแบบ | ความยาว | จำนวน |
|---|---|---|
| `$2b$` | 60 | **202 (ทั้งหมด)** |

`$2b$` คือสิ่งที่ `bcrypt.gensalt()` ของเราสร้าง (= `bcrypt_sha256`) ส่วน GoTrue ของ Supabase สร้าง **`$2a$`**
**ไม่มีแถวใดเป็น `$2a$` เลย** → `password_scheme` ที่ migration 007 ตั้งค่าตั้งต้นเป็น `bcrypt_sha256` **ถูกต้องสำหรับทั้ง 202 แถว**

บัญชีที่ `import_accounts.py` จะเพิ่มเข้ามาใหม่จาก Supabase จะถูกทำเครื่องหมายเป็น `bcrypt` แยกต่างหาก — ไม่ทับของเดิม

> **ถ้าหลัง deploy มีใครเข้าไม่ได้ทั้งที่ยืนยันว่ารหัสถูก** ให้ลองเปลี่ยนรูปแบบของแถวนั้นเป็น `bcrypt` แล้วลองใหม่
> (แถวเดียว ไม่กระทบคนอื่น) ถ้าเข้าได้ แปลว่าแถวนั้นเป็น hash จาก Supabase ที่หลุดมาเป็น `$2b$`
> ตรวจแล้วว่า**ไม่มี**แถวแบบนั้น แต่เก็บวิธีไว้เพราะต้นทุนการลองต่ำ

## 11. ช่องที่อาจยังพึ่ง Supabase — **ไม่ใช่แค่ `logo_url`**

อ่าน `information_schema` ของ schema `web` แล้วได้ **22 คอลัมน์ที่เป็นข้อความ** · ในนั้น

| คอลัมน์ | `migrate_storage.py` จัดการไหม |
|---|---|
| `site_courses.logo_url` | ✅ |
| `news.image_url` | ✅ |
| `external_news.image_url` | ✅ |
| `knowledge_articles.file_path` | ✅ |
| **`knowledge_articles.content`** | ❌ **ไม่จัดการ** — เป็นเนื้อหายาว อาจมี URL ฝังอยู่ |
| **`site_courses.description`** · **`news.description`** · **`external_news.description`** | ❌ **ไม่จัดการ** |
| `external_news.detail_url` · `facebook_url` | ไม่เกี่ยว — ชี้เว็บต้นทางของคณะ ไม่ใช่ Supabase |

**แผนเดิมตรวจแค่ `logo_url` จึงไม่พอ** — ถ้ามี URL ฝังใน `content` หรือ `description` รูปในเนื้อหาจะหายตอนปิด Supabase โดยที่ขั้นตรวจไม่ฟ้องอะไรเลย

แก้ไว้ในแผนแล้ว: ขั้น C3 สแกน **ทุกคอลัมน์ข้อความใน schema `web`** และ **หยุดรายงานถ้าเจอในช่องที่สคริปต์ไม่จัดการ**

## 12. cron เก่ากับ cron ใหม่ — **เขียนคนละฐานข้อมูล**

ตรวจโค้ดแล้วยืนยันได้ว่าสองเส้นทางนี้ไม่เกี่ยวกันเลย

| | cron เก่า (ตอนนี้) | cron ใหม่ (Phase 4) |
|---|---|---|
| ตัวสั่ง | `pg_cron` **ใน Supabase** · job `sync-sci-news-every-30-min-v2` | `crontab` ของ `ubuntu` **บนเซิร์ฟเวอร์** |
| ตัวทำงาน | Edge Function `sync-sci-news` | `python -m app.jobs.sync_sci_news` ในคอนเทนเนอร์ backend |
| **เขียนลงที่** | **`public.external_news` ของ Supabase** | **ตาราง `web.external_news` ของเราเอง** |
| ใครอ่าน | `webapi` → Supabase ด้วย anon key (`api/sci-connect-news.js`) | `backend` → `/api/site/external-news` |

### ⚠ ชื่อตารางเหมือนกันทั้งสองฝั่ง — คนละฐานข้อมูล

ฉบับแรกของรายงานนี้เขียนว่า Supabase ใช้ตาราง `sci_connect_news` ซึ่ง **ผิด**
ชื่อนั้นไม่มีอยู่จริง · `sci_connect` เป็นเพียง**ค่าในคอลัมน์ `source`** ที่ Edge Function เขียนลงไป (`SOURCE_NAME = 'sci_connect'`)

ของจริงตรวจจากโค้ดและ schema แล้ว **ทั้งสองฝั่งใช้ชื่อตาราง `external_news` เหมือนกัน**

| ที่ | ตารางเต็ม | หลักฐาน |
|---|---|---|
| Supabase (ต้นทางที่จะย้ายมา) | **`public.external_news`** | `edge-function/index.ts` `.from('external_news')` · `webapi/api/sci-connect-news.js:28` `.from('external_news')` · `import_from_supabase.py` `select … from public.external_news` |
| ของเราเอง (ปลายทาง) | **`web.external_news`** | `005_web_schema.sql` · `import_from_supabase.py` `insert into web.external_news` |

**ชื่อเหมือนกันแต่คนละฐานข้อมูล จึงสับสนง่ายเป็นพิเศษ** — เวลาสั่งงานหรือรายงานต้องใส่ schema นำหน้าทุกครั้ง

**การกันซ้ำด้วย `detail_url` เป็น unique constraint ใน `web.external_news` ของเราเท่านั้น** — มันไม่เห็นและไม่แตะแถวใน `public.external_news` ของ Supabase เลย

**ที่แผนเดิมเขียนว่า "ปล่อยคู่กันไปก่อนได้ เพราะกันซ้ำด้วย `detail_url`" คือเหตุผลผิด** เหตุผลที่ถูกคือ *สองตัวเขียนลงคนละตารางในคนละฐานข้อมูล จึงชนกันไม่ได้ตั้งแต่ต้น* และ **ไม่ได้พิสูจน์เลยว่า cron เก่าเลิกใช้แล้ว** — มันยังยิงทุก 30 นาทีต่อไป ยังกินโควตา Supabase และยังสร้างภาระให้เว็บต้นทางของคณะอีกทางหนึ่ง

จุดปิดและวิธีเปิดคืน กำหนดไว้ในแผนแล้ว (ขั้น G)

---

## 13. ค่าที่ขั้น P2 จะได้ (ยืนยันล่วงหน้าแล้ว)

| ตัวแปร | ค่าที่จะได้ |
|---|---|
| `CTX` | `/home/ubuntu/course-advisor-system` |
| `IMG` | `course-advisor-system-backend:2fdc6f2` |
| `WEB` | `/home/ubuntu/course-advisor-system/web` |
| `OLD_ID` | `sha256:4a45677ec010fc076e283b1e556bd4c1b0b25bc66786b32ec6f64a76ad0cca46` |
| `APP_UID` | `1000` (จาก `appuser` ในคอนเทนเนอร์) |
| `HOST_GID` | `1001` (จาก `ubuntu` บน host) |

ขั้น P1/P2 ยัง **ต้องรันซ้ำตอน deploy จริง** เพื่อยืนยันว่าค่าไม่เปลี่ยนไปจากวันนี้ — ไม่ใช่ข้ามเพราะเอกสารนี้บอกไว้แล้ว
