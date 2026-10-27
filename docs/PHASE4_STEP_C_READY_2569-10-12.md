# Phase 4 — ขั้น C/D: เตรียมพร้อมแล้ว รอกรอก credentials

| รายการ | ค่า |
|---|---|
| วันที่ | 12 ตุลาคม 2569 |
| ชุดสำรอง | `TAG=2569-10-12` |
| ขั้นที่ผ่านแล้ว | **A** (migration 007) · **B** (deploy backend) — ดู [PHASE4_STEP_AB_RESULT_2569-10-12.md](PHASE4_STEP_AB_RESULT_2569-10-12.md) |
| สถานะตอนนี้ | **หยุดรอเจ้าของกรอกค่าเชื่อมต่อ Supabase ต้นทาง** |
| **ยังไม่ทำ** | import ใด ๆ · ไม่แตะ frontend · ไม่ตั้ง cron · ไม่ปิด Supabase |

---

## 1. ตรวจสถานะก่อนเริ่ม — ตรงกับรายงาน A/B ทุกข้อ

| ตรวจ | ผล |
|---|---|
| backend image ที่รันอยู่ | `sha256:f2fb28e75ee303bbd11808ca61c6d8ef10f8990dcadac931c3a69593f77cff35` **ตรงกับรายงาน** |
| ป้าย image เดิม | `course-advisor-backend:pre-phase4-2569-10-12` → `sha256:4a45677ec010…` **ยังย้อนกลับได้** |
| `db-backup-2569-10-12.dump` | `sha256sum -c` **OK** |
| 4 ไฟล์ `.before-phase4-2569-10-12` | `sha256sum -c` **OK ทุกไฟล์** |
| `.env` สำรอง | มี (โหมด 600) |
| `web-backup-2569-10-12/` | 40 ไฟล์ |
| `web.*` ทุกตาราง | **0 แถว** |
| `public.users` | **202 คน** |

## 2. snapshot ก่อน import — ย้อนเฉพาะรอบนี้ได้

แยกเป็นก้อนเล็กต่อเป้าหมาย ไม่ต้องย้อนทั้งฐานข้อมูลเวลาจะถอนแค่ผลของการ import

| ไฟล์ | คลุมอะไร | ขนาด | `pg_restore -l` |
|---|---|---|---|
| `preimport-2569-10-12.web.dump` | **schema `web` ทั้งก้อน** | 19,120 ไบต์ | exit 0 · 62 บรรทัด |
| `preimport-2569-10-12.users.dump` | `public.users` | 25,533 ไบต์ | exit 0 · 30 บรรทัด |
| `preimport-2569-10-12.user_backup.dump` | `public.migration_007_user_backup` | 7,711 ไบต์ | exit 0 · 20 บรรทัด |

checksum อยู่ที่ `/home/ubuntu/preimport-2569-10-12.sha256`

ตัวเลขและลายนิ้วมือ ณ ก่อน import

```
public.users|202        web.site_courses|0      web.news|0
web.external_news|0     web.knowledge_articles|0    web.ai_settings|0
ลายนิ้วมือสิทธิ์ผู้ใช้: 822956a93509675c74a69945663a8671
```

> **สิ่งที่ snapshot นี้พิสูจน์: อ่านโครงสร้าง archive ได้** · การ restore ของ dump ก้อนใหญ่
> ถูกทดสอบจริงแล้วในขั้นก่อน (35 ตาราง 26,927 แถว ตรงกันหมด) แต่ snapshot สามก้อนนี้
> **ยังไม่ได้ทดสอบ restore แยก**

## 3. ปัญหาสิทธิ์ฐานข้อมูลที่จะทำให้ import ล้ม — แก้แล้ว

### ที่พบ

`advisor_api` คือ role ที่ `DATABASE_URL` ของคอนเทนเนอร์ backend ใช้ (และสคริปต์ทั้งสามรันในคอนเทนเนอร์นั้น)

สิทธิ์เดิมบน `web.external_news` คือ **`SELECT` อย่างเดียว**

| ใครต้องเขียน `web.external_news` | ต้องการสิทธิ์ |
|---|---|
| `pipeline.web.import_from_supabase` | `INSERT` · `UPDATE` |
| `pipeline.web.migrate_storage` | `UPDATE` (แก้ `image_url`) |
| `app.jobs.sync_sci_news` (ขั้น F) | `INSERT` · **`DELETE`** (ตัดข่าวเก่าเกิน 15 รายการ) |

migration 005 ให้สิทธิ์ตารางนี้ไว้กับ `advisor_ingest` เพราะตอนนั้นออกแบบให้ตัวนำเข้าภายนอกเป็นคนเขียน
Phase 4 ย้ายงานมาอยู่ใน backend เอง · และ **`advisor_ingest` ก็ไม่มี `DELETE`** อยู่แล้ว จึงต้องให้สิทธิ์ใหม่ไม่ว่าจะใช้ role ไหน

### ที่ทำ — เท่าที่โค้ดใช้จริง

```sql
grant insert, update, delete on web.external_news to advisor_api;
```

| ขอบเขต | ค่า |
|---|---|
| ตาราง | **1 ตาราง** (`web.external_news`) |
| สิทธิ์ | **3 สิทธิ์** ตรงกับที่โค้ดเรียกใช้ |
| role | **1 role** |
| ไม่ทำ | ไม่ให้สิทธิ์ระดับ schema · ไม่ `ALTER DEFAULT PRIVILEGES` · **ไม่รัน import ด้วย superuser** |

ยืนยันว่าไม่เกินขอบเขต — อีกสี่ตารางยังไม่มี `DELETE`

| ตาราง | `advisor_api` มี DELETE |
|---|---|
| `ai_settings` | `f` |
| **`external_news`** | **`t`** |
| `knowledge_articles` | `f` |
| `news` | `f` |
| `site_courses` | `f` |

`web.external_news.id` เป็น `uuid default gen_random_uuid()` และ schema `web` **ไม่มี sequence** จึงไม่ต้องให้สิทธิ์ sequence เพิ่ม

### ถอนคืน

```bash
docker exec -i course-advisor-system-postgres-1 psql -U postgres -d course_advisor -c "revoke insert, update, delete on web.external_news from advisor_api;"
```

> ถ้าถอนสิทธิ์นี้ **cron ดึงข่าวในขั้น F จะใช้งานไม่ได้** — ถอนเฉพาะกรณีย้อน Phase 4 ทั้งหมด

---

## 4. สิ่งที่รออยู่ — เจ้าของกรอกค่าเชื่อมต่อ

ค่าสองตัวนี้ **ไม่มีอยู่บนเซิร์ฟเวอร์เลย** (บนเครื่องมีแต่ `VITE_SUPABASE_ANON_KEY` ซึ่งอ่าน `auth.users` และ bucket แบบ private ไม่ได้)

เปิดแท็บเทอร์มินัลรออยู่แล้ว กำลังรอที่บรรทัด `SUPABASE_DB_URL (ไม่แสดงค่า):`

ถ้าแท็บปิดไปแล้ว เปิดใหม่ด้วยคำสั่งนี้

```bash
ssh -i ~/.ssh/oci.key -t ubuntu@161.118.237.37 "bash /home/ubuntu/phase4-enter-credentials.sh"
```

| ค่า | เอามาจาก |
|---|---|
| `SUPABASE_DB_URL` | Project Settings → Database → Connection string (URI) |
| `SUPABASE_URL` | Project Settings → API → Project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Project Settings → API → `service_role` |

### ค่าไม่หลุดเพราะ

| กลไก | ผล |
|---|---|
| `read -rsp` | ไม่แสดงตัวอักษรบนจอ |
| ค่าไม่อยู่ในบรรทัดคำสั่ง | ไม่ติด `~/.bash_history` และ `ps` ของผู้ใช้อื่นมองไม่เห็น |
| `unset HISTFILE` ต้นสคริปต์ | เชลล์นั้นไม่บันทึกประวัติ |
| เก็บที่ `/home/ubuntu/.phase4-supabase` | `umask 077` + `chmod 600` — เจ้าของอ่านได้คนเดียว |
| รายงานผล | พิมพ์แค่ **ความยาว** และ **ตัวอักษรนำหน้า** (`postgresql:` / `eyJ`) |
| เสร็จขั้น C | ลบด้วย `bash /home/ubuntu/phase4-clear-credentials.sh` (ใช้ `shred -u`) |

สคริปต์จะทดสอบเชื่อมต่อให้ด้วยสองทาง โดยกรองค่าออกจากข้อความผลลัพธ์

1. `psql "$SUPABASE_DB_URL" -c "select count(*) from auth.users"` — ต้นทางของบัญชี
2. `curl` REST `/external_news` ด้วย service key — ต้องได้ **HTTP 200**

---

## 5. แผนขั้น C เมื่อกรอกค่าแล้ว — ทำทีละชุด หยุดรายงานทุกชุด

ทุกคำสั่งรัน **ในคอนเทนเนอร์** ผ่าน `run_pipeline` (เหตุผล: `DATABASE_URL` ชี้ `@postgres:5432` ซึ่ง host แปลชื่อไม่ได้ และ `UPLOADS_DIR=/srv/uploads` เป็นพาธในคอนเทนเนอร์)

```bash
. /home/ubuntu/.phase4-vars
set -a; . /home/ubuntu/.phase4-supabase; set +a
run_pipeline() { docker compose $COMPOSE run --rm --no-deps -w /app -v "$CTX/pipeline:/app/pipeline:ro" -e SUPABASE_DB_URL -e SUPABASE_URL -e SUPABASE_SERVICE_ROLE_KEY backend python -u -m "$@"; }
```

### C1 ข้อมูล 5 ตาราง

| ขั้น | ตรวจอะไรก่อนไปต่อ |
|---|---|
| `--dry-run` | จำนวนแถวต้นทางแต่ละตาราง · **จับคู่หลักสูตรได้กี่รายการจาก 12** · รายการที่จับคู่ไม่ได้ · ข้อผิดพลาด |
| หยุดรายงาน | ถ้าจับคู่ได้ไม่ครบ 12 ต้องรู้ว่าขาดตัวไหนก่อนตัดสินใจ |
| `--apply` | — |
| ตรวจหลัง | `site_courses` ต้องได้ **12** · เทียบจำนวนทุกตารางกับที่ dry-run บอก |

### C2 บัญชี

| ขั้น | ตรวจอะไร |
|---|---|
| `--dry-run` | จำนวนบัญชีต้นทาง · **จับคู่กับ 202 คนเดิมได้กี่คน** · ความขัดแย้ง email ซ้ำ / ID ไม่ตรง · การแบ่ง role/status |
| หลักประกันในสคริปต์ | `on conflict (email) do update` **ไม่เขียน `password_hash` และไม่เขียน `role` ทับแถวที่มีอยู่** · ข้ามบัญชี OAuth ที่ไม่มีรหัสผ่าน |
| `--apply` | — |
| ตรวจหลัง | `role` × `status` × `password_scheme` แยกจำนวน · บัญชีใหม่ต้องเป็น `bcrypt` · 202 คนเดิมต้องยัง `bcrypt_sha256` · **ไม่แสดง hash ใด ๆ** |
| เทียบ | ลายนิ้วมือสิทธิ์เดิม `822956a9…` ต้องเปลี่ยนเฉพาะจากแถวที่เพิ่มใหม่ |

### C3 ไฟล์

| ขั้น | ตรวจอะไร |
|---|---|
| `--dry-run` | จำนวนไฟล์ที่ถูกอ้างถึงและยังอยู่ที่ Supabase แยกตามตาราง/คอลัมน์ |
| `--apply` | **สคริปต์ไม่แก้ URL เลยถ้าดาวน์โหลดพลาดแม้ไฟล์เดียว** |
| manifest | `storage_migration_manifest.json` — ทั้งหมด / สำเร็จ / ล้ม · ตรวจ sha256 จากไฟล์บนดิสก์จริง |
| **สแกนทุกช่อง** | สร้าง query จาก `information_schema` ครอบ **ทุกคอลัมน์ข้อความใน schema `web` (22 คอลัมน์)** ไม่ใช่แค่ `logo_url` |

ถ้าสแกนแล้วยังเหลือ

| เหลือที่คอลัมน์ | แปลว่า | ทำอะไร |
|---|---|---|
| `logo_url` · `image_url` · `file_path` | สคริปต์ทำไม่ครบ | `--apply --retry-failed` แล้วสแกนซ้ำ |
| **`content` · `description`** | **URL ฝังในเนื้อหา สคริปต์ไม่แตะ** | **หยุด · รายงานคอลัมน์และจำนวน · ห้ามสลับ frontend** |

## 6. แผนขั้น D

| # | ตรวจ | เกณฑ์ |
|---|---|---|
| D1 | `GET /api/site/courses` | **12 หลักสูตร** · ไม่มี URL ที่ยังชี้ supabase |
| D2 | `GET /api/site/courses/{id}` ด้วย **ID เดิมจาก Supabase** | `200` — ลิงก์เก่าต้องยังเปิดได้ |
| D3 | `GET /api/site/news` · `/api/site/external-news` | `200` · เห็นเฉพาะที่เผยแพร่ |
| D4 | **ร่างไม่หลุดสาธารณะ** | นับแถวที่ `status<>'published'` / `is_published=false` ในฐานข้อมูล เทียบกับที่ API คืน — ต้องไม่ปรากฏ |
| D5 | `GET /api/career-lists` | `200` · **11 หลักสูตร · 69 อาชีพ · มีเอกสารอ้างอิงครบ** |
| D6 | เปิดไฟล์รูปที่ย้ายมา | `200` |
| D7 | **ไฟล์ private** (`knowledge`) ไม่มี token | **`401`** |
| D8 | `POST /api/chat` | `200` + `X-Source-Document` + `X-Source-Page` |
| D9 | `POST /api/recommend-major` · `/api/compare-courses` | `200` ทั้งคู่ — ใช้ body ที่ถูกตามสัญญา (`courses[].id` และ `answers` คีย์ `favorite_subjects`/`interests`/`aptitudes`) |
| D10 | เส้นทางผู้ดูแลไม่มี token | **`401`** ทุกเส้นทาง |

### การทดสอบเข้าสู่ระบบ — เจ้าของทำเอง

**ไม่ขอรหัสผ่านในแชต** และผมไม่ตั้งรหัสให้ใคร

ขั้นตอนที่เจ้าของทำเองหลังขั้น C

1. เปิด `https://stpnru-advisor.duckdns.org/admin/login` แล้วเข้าสู่ระบบด้วย **รหัสผ่านเดิมของตัวเอง**
2. บอกผมว่าเข้าได้หรือไม่ (ไม่ต้องบอกรหัส)
3. ผมตรวจจากฝั่งฐานข้อมูลว่า `password_scheme` ของบัญชีนั้นเปลี่ยนเป็น `bcrypt_sha256` เองหรือไม่ และมีแถวใน `auth_sessions` เพิ่มขึ้นไหม

> หน้า `/admin/login` ที่ใช้ตอนนี้ยังเป็น **หน้าเว็บชุดเดิม** ซึ่งเรียก Supabase
> การทดสอบเข้าสู่ระบบผ่าน **API ใหม่** จะสมบูรณ์หลังขั้น E · ก่อนหน้านั้นทดสอบได้ด้วย
> `POST /api/auth/login` ตรง ซึ่งเจ้าของยิงเองได้โดยไม่ต้องบอกรหัสให้ผม

---

## 7. ขอบเขตของรอบนี้

| ทำ | ไม่ทำ |
|---|---|
| ขั้น C (ข้อมูล · บัญชี · ไฟล์) | ไม่แตะ frontend — `phase4-web` 19 ไฟล์ยังรออยู่ |
| ขั้น D (ตรวจ API) | ไม่ตั้ง cron ใหม่ |
| | ไม่ปิด cron เก่าหรือโปรเจกต์ Supabase |
| | ไม่รัน A/B ซ้ำ |

**หยุดก่อนขั้น E** แล้วรายงานจำนวนก่อน/หลัง ผลตรวจจริง และสิ่งที่ยังค้าง

---

## 8. ไฟล์ที่เกี่ยวข้องบนเซิร์ฟเวอร์

```
/home/ubuntu/.phase4-vars                      ค่าที่ทุกขั้นใช้ร่วมกัน (600)
/home/ubuntu/.phase4-supabase                  ค่าเชื่อมต่อต้นทาง (600) — ลบเมื่อเสร็จขั้น C
/home/ubuntu/phase4-enter-credentials.sh       กรอกค่าแบบซ่อน (700)
/home/ubuntu/phase4-clear-credentials.sh       ลบค่าทิ้ง (700)
/home/ubuntu/preimport-2569-10-12.*.dump       snapshot ก่อน import
/home/ubuntu/preimport-2569-10-12.sha256       checksum ของ snapshot
/home/ubuntu/db-backup-2569-10-12.dump         สำรองฐานข้อมูลทั้งก้อน (ขั้น P3)
/home/ubuntu/*.before-phase4-2569-10-12        สำรองไฟล์เดิม 5 ไฟล์ (รวม .env)
/home/ubuntu/web-backup-2569-10-12/            สำรองหน้าเว็บ 40 ไฟล์
/home/ubuntu/phase4-src/                       ซอร์สที่วางไปแล้ว (29 ไฟล์)
/home/ubuntu/phase4-web/                       หน้าเว็บที่รอขั้น E (19 ไฟล์)
ป้าย image course-advisor-backend:pre-phase4-2569-10-12
```
