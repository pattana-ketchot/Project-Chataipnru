# Phase 4 — ผลขั้น A และ B

| รายการ | ค่า |
|---|---|
| วันที่ | 12 ตุลาคม 2569 |
| ชุดสำรอง | `TAG=2569-10-12` |
| ขอบเขต | **ขั้น A (migration 007) และขั้น B (deploy backend) เท่านั้น** |
| **ยังไม่ทำ** | ขั้น C (ข้อมูล/บัญชี/ไฟล์) · ไม่แตะ frontend · ไม่ตั้ง cron · ไม่ปิด Supabase · ไม่กรอก secrets |
| สถานะรวม | **Phase 4 ยังไม่เสร็จ** — ข้อมูล บัญชี และไฟล์ยังอยู่ที่ Supabase |

---

## 0. ตรวจค่าก่อนเปลี่ยน — ตรงกับหลักฐานทุกตัว

| ตัวแปร | ค่า | เทียบ preflight |
|---|---|---|
| `CTX` | `/home/ubuntu/course-advisor-system` | ตรง |
| `WEB` | `/home/ubuntu/course-advisor-system/web` | ตรง |
| `IMG` | `course-advisor-system-backend:2fdc6f2` | ตรง |
| `OLD_ID` | `sha256:4a45677ec010fc076e283b1e556bd4c1b0b25bc66786b32ec6f64a76ad0cca46` | ตรง |
| `APP_UID` | `1000` | ตรง |
| `HOST_GID` | `1001` | ตรง |

ของสำรอง `sha256sum -c` **exit 0 ทุกไฟล์** · ชุดที่จะใช้ตรง manifest **29/29 และ 19/19**

---

## 1. ทดสอบ restore ก่อนแตะ production — **ผ่าน**

ทำตามที่สั่ง: restore ลงฐานทดสอบแยก ไม่ทับ production ไม่เปิดพอร์ตสาธารณะ

| รายการ | ค่า |
|---|---|
| ฐานทดสอบ | `phase4_restore_test` ในคลัสเตอร์เดิม · **ไม่เปิดพอร์ตใหม่** · ไม่แตะ `course_advisor` |
| `pg_restore` | **exit 0** · ใช้เวลา 4 วินาที |
| error / warning ใน stderr | **0 / 0** |
| ตารางที่เทียบ | **35 ตาราง** |
| แถวรวม | **26,927 เท่ากันทั้งสองฝั่ง** |
| ตารางที่จำนวนแถวต่างกัน | **0** |

เทียบโครงสร้างและข้อมูลด้วย — **เหมือนกันทุกบรรทัด**

| สิ่งที่เทียบ | ค่า |
|---|---|
| schema | `public` · `mko` · `web` |
| view | **8 ตัว** รวม `mko.v_live_list_items` |
| function | **204 ตัว** |
| extension | `vector 0.8.6` · `citext 1.6` · `pgcrypto 1.3` · `plpgsql 1.0` |
| `md5` ของ `public.users` (id+email+hash) | **ตรงกัน** |
| `md5` ของ `public.courses` | **ตรงกัน** |
| มิติของ embedding | **1024** ทั้งสองฝั่ง |
| careers ใน view | **69 รายการ · 11 หลักสูตร** ทั้งสองฝั่ง |

**ลบฐานทดสอบแล้ว** · เหลือ `course_advisor` ตามเดิม

> รอบก่อนพูดได้แค่ "อ่านโครงสร้าง archive ได้" · **รอบนี้ยืนยันได้ว่า restore แล้วข้อมูลครบและตรง**

---

## 2. ขั้น A — migration 007

### รอบที่ 1

```
NOTICE:  บันทึกสภาพเดิมไว้ 202 แถว
NOTICE:  แปลงผู้ใช้เดิม 202 แถว เป็น approved
CREATE TRIGGER
UPDATE 0
INSERT 0 1
COMMIT
psql exit=0
```

| ผลลัพธ์ | ค่า |
|---|---|
| `admin` / `approved` / `bcrypt_sha256` | **1 คน** |
| `user` / `approved` / `bcrypt_sha256` | **201 คน** |
| ค่าขัดกัน (`is_admin` ไม่ตรงกับ `role='admin'`) | **0** |
| บันทึกสภาพเดิม | **202 แถว** |
| ยังไม่อนุมัติ | **0** |
| รูปแบบ hash | `bcrypt_sha256` + `$2b$` **ทั้ง 202 แถว** |
| ตารางใหม่ | `auth_sessions` · `auth_tokens` · `migration_007_user_backup` |
| trigger | `trg_sync_user_admin_flag` **1 ตัว** |
| `mko.schema_migrations` | `007_web_auth` · `2026-10-12 01:47:29+07` |

`UPDATE 0` ในขั้น reconciliation ถูกต้อง — ไม่มีแถวที่ `is_admin` ขัดกับ `role` หลังแปลง

### รอบที่ 2 — พิสูจน์ว่ารันซ้ำไม่เปลี่ยนสิทธิ์

เพิ่มบัญชีทดสอบที่ `status='pending'` ก่อนรันซ้ำ เพื่อจับบั๊กที่รุ่นแรกของ migration เคยมี

```
NOTICE:  007 เคยรันแล้ว — ข้ามขั้นแปลงผู้ใช้เดิม ไม่แตะสิทธิ์ของใคร
UPDATE 0
```

| ตรวจ | ผล |
|---|---|
| ลายนิ้วมือสิทธิ์ก่อน/หลัง | `9068c22d50c133d0ec0bc375685d9db4` **เท่ากันเป๊ะ** |
| บัญชีทดสอบ | **ยังเป็น `pending`** — ไม่ถูกอนุมัติให้ |
| บันทึกสภาพเดิม | **ยัง 202** ไม่กลายเป็น 203 |

**ลบบัญชีทดสอบแล้ว** · กลับเป็น 202 ผู้ใช้

### trigger — ทดสอบบน production จริง (บนบัญชีทดสอบ ไม่แตะผู้ใช้จริง)

| ทำอะไร | `role` | `is_admin` | ถูกต้องไหม |
|---|---|---|---|
| เริ่มต้น | `user` | `f` | — |
| เขียน `is_admin=true` อย่างเดียว | `user` | **`f`** | **ไม่มีผล ถูกต้อง** |
| เขียน `role='admin'` | `admin` | **`t`** | ตามกันถูกต้อง |
| เขียนขัดกันในคำสั่งเดียว (`role='user'`, `is_admin=true`) | `user` | **`f`** | **`role` ชนะ ถูกต้อง** |
| เขียน `role='superuser'` | — | — | **ถูก CHECK ปฏิเสธ** |

---

## 3. ขั้น B — deploy backend

### ไฟล์และ compose

| ตรวจ | ผล |
|---|---|
| วางซอร์ส | **29/29 ไฟล์ · checksum ตรง · ผิด 0 · ขาด 0** |
| `compose` diff | เพิ่มเฉพาะ env 8 ตัว + volume `./uploads:/srv/uploads` |
| `main.py` diff | เพิ่มเฉพาะ router Phase 4 สี่ตัว · **`crawl_review` = 0 ครั้ง** |
| `web_compat.py` diff | **เพิ่ม 66 บรรทัด ไม่ลบโค้ดเดิมเลย** · มีแค่ `GET /career-lists` |
| `requirements.txt` diff | เพิ่ม 3 แพ็กเกจ |

### `PUBLIC_BASE_URL`

สำรอง `.env` ไว้ที่ `/home/ubuntu/env.before-phase4-2569-10-12` (โหมด 600) ก่อนแก้

| ตรวจ | ผล |
|---|---|
| จำนวน key ใน `.env` | 20 → **21** (เพิ่มหนึ่งบรรทัด) |
| ค่าตรงกับ `https://` ต่อด้วย `SITE_DOMAIN` | **ใช่** |
| ค่าที่ backend เห็น | **ตั้งแล้ว ยาว 34 ตัวอักษร** (ไม่แสดงค่า) |

### uploads — uid/gid จากของจริง ไม่ใช่เลขที่เดา

| รายการ | ค่า |
|---|---|
| เจ้าของโฟลเดอร์บน host | **`1000:1001`** = `opc:ubuntu` |
| โหมด | **775** |
| ที่คอนเทนเนอร์เห็น | `drwxrwxr-x appuser 1001` |
| uid ที่โปรเซสรัน | **1000 (`appuser`)** |
| เขียน `/srv/uploads` | **เขียนได้** |
| เขียน `/srv/documents` | **เขียนไม่ได้ (ro)** ถูกต้อง |

เจ้าของเป็น uid ของคอนเทนเนอร์ · กลุ่มเป็น gid ของ `ubuntu` บน host · **เขียนได้ทั้งสองฝั่ง**

### build และ image

| รายการ | ค่า |
|---|---|
| `docker compose build backend` | **exit 0** · 18 วินาที |
| แพ็กเกจใหม่ | `python-multipart 0.0.32` · `pymupdf 1.28.2` · `python-docx 1.2.0` |
| ตรวจก่อน `up` (คอนเทนเนอร์ชั่วคราว) | `import app.main` **สำเร็จ · 50 เส้นทาง** · `crawl_review` 0 ครั้ง |
| ไฟล์ใน image | มี `site.py` `site_admin.py` `uploads.py` `extract.py` `sync_sci_news.py` `web_compat.py` · **ไม่มี `crawl_review.py`** |

> **ข้อควรรู้: `build` เขียนทับ tag `2fdc6f2`** — tag นั้นชี้ image ใหม่แล้ว
> image เดิมเหลือทางเดียวคือป้าย `course-advisor-backend:pre-phase4-2569-10-12`
> ตรวจแล้วว่าป้ายนั้นยังชี้ `sha256:4a45677ec010…` **ย้อนกลับได้**
>
> พบอีกข้อระหว่างทำ: พาธของโค้ดใน image คือ **`/app/backend/app/`** ไม่ใช่ `/app/app/`
> (Dockerfile ตั้ง `WORKDIR /app/backend`) — แก้ในเอกสารแล้วทั้งสองฉบับ

### image ID

| รายการ | ค่า |
|---|---|
| **image เดิม** | `sha256:4a45677ec010fc076e283b1e556bd4c1b0b25bc66786b32ec6f64a76ad0cca46` |
| **image ใหม่** | `sha256:f2fb28e75ee303bbd11808ca61c6d8ef10f8990dcadac931c3a69593f77cff35` |
| คอนเทนเนอร์ใหม่ | `940e0b5bc8fb` (เดิม `fda31caa20c4`) |

### เปลี่ยนแค่ backend

| service | สถานะหลัง deploy |
|---|---|
| **backend** | **Up 3 minutes** ← ตัวเดียวที่เปลี่ยน |
| caddy | Up 2 weeks |
| frontend | Up 12 days |
| ollama | Up 7 weeks (healthy) |
| postgres | Up 7 weeks (healthy) |
| webapi | Up 6 hours (healthy) |

log ตอนเริ่ม: `embedding dim = 1024 ตรงกับ bge-m3` · `Application startup complete` · **ไม่มี error**

---

## 4. ผลตรวจ HTTP

### health และเส้นทาง

| ตรวจ | ผล |
|---|---|
| `GET /api/health` | **200** `{"status":"ok"}` |
| เส้นทางทั้งหมดใน openapi | **50** |
| เส้นทางใหม่ (`/site*` `/auth*` `/uploads*` `/extract-file`) | **30** |
| `/career-lists` | **มี** |
| `/crawl-review*` | **ไม่มี** ถูกต้อง |

### เส้นทางสาธารณะใหม่

| เส้นทาง | HTTP |
|---|---|
| `GET /api/site/courses` | **200** |
| `GET /api/site/news` | **200** |
| `GET /api/site/external-news` | **200** |

ทั้งสามคืนรายการว่าง เพราะ `web.*` ยังไม่มีข้อมูล — **ถูกต้องตามสถานะ** (ขั้น C ยังไม่ทำ)

### careers (งานที่รวมในรอบนี้)

| ตรวจ | ผล |
|---|---|
| `GET /api/career-lists` | **200** |
| หลักสูตร | **11** |
| อาชีพรวม | **69** |
| รายการที่ไม่มีแหล่งอ้างอิง | **0** |

ตรงกับที่นับไว้ตอน preflight เป๊ะ · ทุกรายการมีชื่อไฟล์และเลขหน้าของเอกสารต้นทาง

### เส้นทางเดิมที่หน้าเว็บปัจจุบันยังใช้

| เส้นทาง | HTTP | เวลา | หมายเหตุ |
|---|---|---|---|
| `POST /api/chat` | **200** | 1.46s | `x-source-document` · **`x-source-page: 3`** · `x-source-title: cs66.pdf` · คำตอบ 1,363 ไบต์ |
| `POST /api/recommend-major` | **200** | 6.57s | `primary.courseId` · `matchScore 52` · `alternatives 1` · มี `summary` |
| `POST /api/compare-courses` | **200** | 6.17s | มี `summary` เปรียบเทียบสองหลักสูตรจริง |
| `GET /api/courses` | **200** | — | ของเดิม |
| `GET /api/sci-connect-news` | **200** | — | ยังไปที่ `webapi` ตามเดิม |
| `GET /api/documents/<id>/pdf` | **200** | — | เปิดเอกสารต้นทางได้ |

> **สองรอบแรกที่ยิง `recommend-major` และ `compare-courses` ได้ 422 และ 500 — เป็นเพราะ body ที่ผมส่งผิด ไม่ใช่ระบบพัง**
> `recommend-major` ต้องมี `courses[].id` และ `answers` ต้องใช้คีย์ `favorite_subjects` / `interests` / `aptitudes`
> พอส่ง body ถูกตามสัญญาใน openapi ได้ **200 ทั้งคู่**
>
> หมายเหตุที่ควรรู้แต่ไม่ใช่ของรอบนี้: `recommend-major` แปลง `ValueError` เป็น **500** แทน 400/422
> เมื่อ `answers` ไม่มีข้อมูลที่ใช้จัดอันดับ · **เป็นพฤติกรรมเดิม** เพราะ diff ของ `web_compat.py`
> มีแต่การเพิ่ม `/career-lists` ไม่ได้แก้ฟังก์ชันนี้เลย

### การตรวจสิทธิ์ — ไม่มี token ต้องเข้าไม่ได้

| เส้นทาง | HTTP |
|---|---|
| `GET /api/site-admin/courses` | **401** |
| `GET /api/site-admin/news` | **401** |
| `GET /api/site-admin/knowledge` | **401** |
| `GET /api/site-admin/users` | **401** |
| `GET /api/site-admin/ai-settings` | **401** |
| `POST /api/site-admin/sync-news` | **401** |
| `DELETE /api/site-admin/courses/<uuid>` | **401** |
| `GET /api/auth/me` | **401** |
| `GET /api/uploads/knowledge/aa/x.pdf` | **401** |
| `POST /api/uploads/logo` | **401** |

| ทดสอบ auth | ผล |
|---|---|
| เข้าสู่ระบบด้วยอีเมลที่ไม่มีจริง | **401** `อีเมลหรือรหัสผ่านไม่ถูกต้อง` — ข้อความไม่บอกว่าอีเมลมีในระบบหรือไม่ |
| `refresh` ด้วย token ปลอม | **401** `เซสชันหมดอายุหรือถูกเพิกถอนแล้ว` |
| `auth_sessions` / `auth_tokens` | **0 / 0** — ยังไม่มีใครเข้าสู่ระบบผ่านระบบใหม่ |

> **ยังไม่ได้ทดสอบเข้าสู่ระบบด้วยบัญชีจริง** เพราะต้องใช้รหัสผ่านของเจ้าของบัญชี ซึ่งผมไม่มีและไม่ควรขอ
> ข้อนี้ปิดได้ที่ V4/V5 โดยเจ้าของบัญชีเอง

---

## 5. ขอบเขตที่รักษาไว้

| ตรวจ | ผล |
|---|---|
| frontend | `diff -r` กับของสำรอง **เหมือนกันทุกไฟล์ 40/40** · `phase4-web` 19 ไฟล์ยังรออยู่ **ไม่วางทับ** |
| `web.*` ทุกตาราง | **0 แถวทั้งหมด** — ไม่ได้รัน `import --apply` |
| ไฟล์ใน `uploads` | **0 ไฟล์** |
| ผู้ใช้ | **202** เท่าเดิม |
| cron ใหม่ | **ยังไม่ตั้ง** (0 บรรทัดใน crontab) |
| Supabase · cron เก่า | **ไม่แตะ** · `webapi` ยังได้รับค่า Supabase ไว้ย้อนกลับ (2 ตัวแปร) |
| secrets ของ Supabase | **ยังไม่ได้กรอก** |
| ของสำรอง | `sha256sum -c` **OK ทุกไฟล์** · ป้าย image ยังชี้ image เดิม |

---

## 6. ทางถอยกลับ ณ ตอนนี้

```bash
. /home/ubuntu/.phase4-vars
docker tag course-advisor-backend:pre-phase4-$TAG "$IMG"
cp -a "/home/ubuntu/docker-compose.prod.yml.before-phase4-$TAG" "$CTX/docker-compose.prod.yml"
cp -a "/home/ubuntu/main.py.before-phase4-$TAG"                 "$CTX/backend/app/main.py"
cp -a "/home/ubuntu/web_compat.py.before-phase4-$TAG"           "$CTX/backend/app/api/routes/web_compat.py"
cp -a "/home/ubuntu/requirements.txt.before-phase4-$TAG"        "$CTX/backend/requirements.txt"
cp -a "/home/ubuntu/env.before-phase4-$TAG"                     "$CTX/.env"
```

แล้ว `up -d --no-deps --no-build --force-recreate backend` และเทียบ image ID ให้เท่ากับ `$OLD_ID`

ส่วน migration ถอนด้วยบล็อก "ถอนกลับ" ท้าย `007_web_auth.sql` ซึ่งคืน `is_admin` จาก `public.migration_007_user_backup` (202 แถว) · **ต้อง `DROP TRIGGER` ก่อนคืนค่า**

---

## 7. ขั้นถัดไป — **Phase 4 ยังไม่เสร็จ**

| # | เหลืออะไร |
|---|---|
| 1 | **ขั้น C** — นำข้อมูล 5 ตาราง · บัญชีจาก Supabase · ไฟล์จาก Storage (ต้องกรอก `SUPABASE_DB_URL` และ `SUPABASE_SERVICE_ROLE_KEY`) |
| 2 | **ขั้น D** — ตรวจ API ให้ผ่านครบก่อนแตะหน้าเว็บ |
| 3 | **ขั้น E** — วางหน้าเว็บใหม่ (`phase4-web` 19 ไฟล์ที่รออยู่) |
| 4 | **ขั้น F** — ตั้ง cron ดึงข่าวบนเซิร์ฟเวอร์ |
| 5 | **ขั้น V** — ตรวจรับ V1–V21 รวมการเข้าสู่ระบบด้วยบัญชีจริง |
| 6 | **ขั้น G** — ปิด cron เก่าใน Supabase หลังตรวจรับผ่าน |

**ตอนนี้หน้าเว็บที่ผู้ใช้เห็นยังเป็นชุดเดิมที่เรียก Supabase อยู่** — backend ใหม่พร้อมรับงานแล้วแต่ยังไม่มีข้อมูลใน `web.*`
