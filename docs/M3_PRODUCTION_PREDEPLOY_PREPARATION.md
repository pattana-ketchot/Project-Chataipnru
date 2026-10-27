# M3 — Production Pre-Deploy Preparation

> อนุญาตให้เปลี่ยนเฉพาะ **docker image tag สำหรับ rollback** เท่านั้น · ไม่ deploy · ไม่ restart · ไม่ build ทับ · ไม่แก้ `.env` · ไม่เขียนฐานข้อมูลหรือ Supabase · ไม่ push/merge

## ผลสรุป

# `M3_PREDEPLOY_PREPARATION_DONE` (มีเงื่อนไขค้าง 1 ข้อ)

| ข้อ | งาน | ผล |
|---|---|---|
| 1 | ตรวจ WebAPI image ปัจจุบัน | **เสร็จ** |
| 2 | สร้าง rollback tag | **เสร็จ** — `course-advisor-system-webapi:rollback-pre-m3` |
| 3 | ยืนยันว่า tag ชี้ image เดียวกัน | **เสร็จ** — ตรงกันทั้งสามจุด |
| 4 | ตรวจบัญชี admin สำหรับ smoke test | **เสร็จบางส่วน** — ฝั่ง PostgreSQL ยืนยันแล้ว **ฝั่ง Supabase ยืนยันเองไม่ได้** |
| 5 | ตรวจแผน smoke test | **เสร็จ** — มีแผนที่ทดสอบด่านสิทธิ์ได้ครบโดยไม่เขียนข้อมูลเลย |
| 6 | รายงาน | เอกสารฉบับนี้ |

---

## ⚠️ คำสั่งข้อ 2 ที่ได้รับมาเสียรูป

คำสั่งที่วางมาคือ

```
docker tag course-advisor-system-webapi course-advisor-system-webapi
```

ต้นทางกับปลายทางเป็นชื่อเดียวกันและไม่มี tag กำกับ — docker จะตีความเป็น `:latest` ทั้งคู่ คำสั่งนี้จึงเป็น **no-op** ไม่ได้สร้าง rollback tag อะไรเลย น่าจะเป็นเพราะชื่อ tag หลุดตอนคัดลอก

จึงใช้ชื่อที่ระบุไว้ตรงกันทั้งใน `M3_PRODUCTION_ROLLOUT_PREFLIGHT.md` และ `webapi/README.md` แทน

```bash
docker tag course-advisor-system-webapi:latest course-advisor-system-webapi:rollback-pre-m3
```

ชื่อนี้สอดคล้องกับแบบแผนที่ production ใช้อยู่กับบริการอื่น เช่น `course-advisor-system-backend:rollback-pre-phase3d`

---

## 1. WebAPI image ก่อนดำเนินการ

| รายการ | ค่า |
|---|---|
| Repository:Tag | `course-advisor-system-webapi:latest` |
| Image ID | `sha256:1163e36361d9e39749aa3d8e788629417e47e2d83265bd386af6c07949f52a12` |
| Created | `2026-09-22T21:21:26Z` |
| ขนาด | 527 MB |
| Tags ทั้งหมด | `[course-advisor-system-webapi:latest]` — **มี tag เดียว** |

คอนเทนเนอร์ที่ให้บริการอยู่

| รายการ | ค่า |
|---|---|
| ชื่อ | `course-advisor-system-webapi-1` |
| Image ที่ใช้ | `sha256:1163e363…f52a12` |
| สถานะ | `running` · `healthy` |
| เริ่มเมื่อ | `2026-09-22T21:21:35Z` |

ยืนยันว่า **คอนเทนเนอร์ที่รันอยู่ใช้ image ID เดียวกับที่ `:latest` ชี้** จึงเป็น image ที่ถูกต้องสำหรับติด rollback tag

---

## 2–3. Rollback tag

### คำสั่งที่รัน (คำสั่งเดียวที่เปลี่ยนสถานะ production ในรอบนี้)

```bash
docker tag course-advisor-system-webapi:latest course-advisor-system-webapi:rollback-pre-m3
```

### หลังติด tag

```
course-advisor-system-webapi:latest            1163e36361d9   2 weeks ago
course-advisor-system-webapi:rollback-pre-m3   1163e36361d9   2 weeks ago
```

### การยืนยัน

| จุดที่เทียบ | Image ID |
|---|---|
| `:latest` | `sha256:1163e36361d9e39749aa3d8e788629417e47e2d83265bd386af6c07949f52a12` |
| `:rollback-pre-m3` | `sha256:1163e36361d9e39749aa3d8e788629417e47e2d83265bd386af6c07949f52a12` |
| คอนเทนเนอร์ที่รันอยู่ | `sha256:1163e36361d9e39749aa3d8e788629417e47e2d83265bd386af6c07949f52a12` |

**ตรงกันทั้งสามจุด** — rollback tag ใช้ย้อนกลับได้จริง

`RepoTags` ของ image ตอนนี้: `[course-advisor-system-webapi:latest course-advisor-system-webapi:rollback-pre-m3]`

### ผลข้างเคียง

| รายการ | ผล |
|---|---|
| คอนเทนเนอร์ | `Up 2 weeks (healthy)` — **ไม่ถูก restart ไม่ถูกกระทบ** |
| จำนวน image | เท่าเดิม — `docker tag` เพิ่มเฉพาะชื่อ ไม่ได้สร้าง image ใหม่ ไม่กินพื้นที่เพิ่ม |
| เนื้อ image | ไม่เปลี่ยน |

### วิธีย้อนกลับเมื่อจำเป็น

```bash
docker tag course-advisor-system-webapi:rollback-pre-m3 course-advisor-system-webapi:latest
docker compose -f docker-compose.prod.yml up -d webapi
```

---

## 4. บัญชี Admin สำหรับ Smoke Test

### สิ่งที่ยืนยันได้ — ฝั่ง PostgreSQL (read-only)

| การนับ | จำนวน |
|---|---|
| `public.users` ทั้งหมด | 201 |
| `is_admin = true` | **1** |
| `is_admin` และ `is_active` | **1** |
| ผูก `supabase_user_id` แล้ว | **1** |
| ผูกแล้ว + `is_active` | **1** |
| ผูกแล้ว + `is_active` + `is_admin` | **1** |

มีบัญชีเดียวที่ผ่านทุกเงื่อนไขฝั่ง PostgreSQL และเป็นบัญชีเดียวกับที่ผูกไว้ตอน S1 Mapping

> ไม่แสดง UUID อีเมล หรือชื่อผู้ใช้ตามข้อกำหนด — ใช้การนับเท่านั้น

### สิ่งที่ยืนยันเองไม่ได้ — ฝั่ง Supabase

ด่านตรวจสิทธิ์ของ webapi **ไม่ได้อ่าน `is_admin` จาก PostgreSQL** แต่อ่าน `role` และ `status` จากตาราง `user_profiles` ของ **Supabase**

```js
// api/_lib/adminAuth.js
const ADMIN_ROLES = ['admin', 'editor'];
… .from('user_profiles').select('role, status')
if (!ADMIN_ROLES.includes(profile?.role) || profile?.status !== 'approved') → 403
```

`auth.mjs` ของด่านกลางก็ใช้แหล่งเดียวกัน

**ตรวจฝั่ง Supabase ไม่ได้ในรอบนี้** เพราะ

1. ต้องใช้คีย์จาก production `.env` ซึ่งรอบนี้อ่านได้แค่ชื่อคีย์ ไม่ใช่ค่า
2. anon key ทำงานภายใต้ RLS จึงต้องมี token ของผู้ใช้จริงอยู่ดี
3. การไปเอาคีย์มาใช้เกินขอบเขต "read-only query" ที่อนุมัติ

### สถานะตามบันทึกเดิม

ในรอบ **S1 Identity Mapping** เจ้าของเคยยืนยันผลตรวจ Supabase ด้วยตนเองไว้แล้วว่าพบ **1 แถว · `role = admin` · `status = approved`** และนั่นคือบัญชีที่นำมาผูกเป็น S1

### สิ่งที่ต้องทำก่อน smoke test

**ขอให้เจ้าของยืนยันอีกครั้งว่าบัญชีนั้นยังเป็น `role = admin` และ `status = approved` อยู่** เพราะทั้งสองค่าแก้ได้จากหน้า `/admin/users` ระหว่างนี้ และถ้าเปลี่ยนไป smoke test ข้อสำคัญจะให้ผลลวง

---

## 5. แผน Smoke Test ที่ไม่เขียนข้อมูล

### จำแนกเส้นทางตามการเขียนข้อมูล

| เส้นทาง | ระดับ | เขียนข้อมูลไหม | หลักฐาน |
|---|---|---|---|
| `GET /api/sci-connect-news` | PUBLIC | **ไม่** | `.from('external_news').select(…)` อย่างเดียว |
| `GET /api/sci-connect-news-detail` | PUBLIC | **ไม่** | `.from('external_news').select(…)` อย่างเดียว |
| `POST /api/admin/extract-file` | EDITOR | **ไม่** | อ่านไฟล์จาก form แล้วแปลงในหน่วยความจำ คืนข้อความ · `fileExtract.js` ไม่มี `fetch`, `.from(`, storage หรือการเขียนไฟล์เลย |
| `POST /api/admin/ingest` | EDITOR | **เขียน** | `rag_documents` — `.delete()` + `.upsert()` + `.delete()` |
| `POST /api/admin/sync-sci-news` | EDITOR | **เขียน** | `POST` ไปยัง Supabase Edge Function `functions/v1/sync-sci-news` |

### แผนที่เสนอ — ครบทั้งเส้นทางอนุญาตและปฏิเสธ โดยไม่เขียนอะไรเลย

| # | การทดสอบ | ผลที่ต้องได้ | เขียนข้อมูลไหม |
|---|---|---|---|
| 1 | `docker ps` ดู webapi | `healthy` ภายใน start-period 10s + 3 retries | ไม่ |
| 2 | `/healthz` **ในคอนเทนเนอร์** | `status=ok` · `authConfigured=true` · `dbConfigured=true` · `db` ไม่ใช่ `not-configured` · `routes` เป็น `{route, level}` 5 รายการ | ไม่ |
| 3 | `GET /api/sci-connect-news` ผ่านเว็บจริง | HTTP 200 และมีเนื้อหาข่าว | ไม่ |
| 4 | `GET /api/sci-connect-news-detail` ผ่านเว็บจริง | HTTP 200 | ไม่ |
| 5 | `POST /api/admin/extract-file` **ไม่มี token** | HTTP 401 (ไม่ใช่ 500) — ด่านปฏิเสธก่อนถึง handler | ไม่ |
| 6 | `POST /api/admin/ingest` **ไม่มี token** | HTTP 401 — **สำคัญ** เพราะพิสูจน์ว่าด่านกัดก่อนที่ handler จะได้เขียน `rag_documents` | ไม่ |
| 7 | **`POST /api/admin/extract-file` พร้อม token ของ admin ที่ approved** + แนบไฟล์ `.txt` เล็ก ๆ | HTTP 200 และได้ข้อความกลับมา — **ไม่ใช่ 401/403** | **ไม่** |
| 8 | `GET /api/chat` | ยังไปที่ backend ตามปกติ ไม่กระทบ | ไม่ |
| 9 | log ของ webapi | มีบรรทัด `ตั้งค่าฐานข้อมูลแล้ว:` และ **ไม่มีรหัสผ่านโผล่** | ไม่ |
| 10 | `SELECT count(*) FROM pg_stat_activity WHERE usename='advisor_web'` | มากกว่า 0 และไม่เกิน 5 (ค่า `max` ของ pool) | ไม่ |

### ทำไมแผนนี้ครอบคลุมทั้งที่ไม่เขียนข้อมูล

**ข้อ 7 คือข้อที่สำคัญที่สุด** — เป็นข้อเดียวที่พิสูจน์ว่า authorization foundation ซึ่งจะขึ้น production ครั้งแรก **ไม่ล็อกผู้ดูแลออกจากระบบ** และ `extract-file` เป็นเส้นทางระดับ EDITOR เพียงเส้นทางเดียวจากสามเส้นทางที่ไม่เขียนข้อมูลเลย จึงใช้ทดสอบเส้นทางอนุญาตได้อย่างปลอดภัย

**ข้อ 6 ทดสอบเส้นทางปฏิเสธบน endpoint ที่เขียนข้อมูล** โดยไม่เสี่ยง เพราะด่านตรวจทำงาน **ก่อน** handler ถ้าได้ 401 แปลว่า handler ไม่เคยถูกเรียก จึงไม่มีการเขียน `rag_documents` เกิดขึ้น — และถ้าได้อย่างอื่นที่ไม่ใช่ 401 นั่นคือสัญญาณว่าต้อง rollback ทันที

**ข้อ 5 กับ 6 เคยทดสอบแล้วบน production ปัจจุบัน** ได้ 401 ทั้งคู่ จึงมีค่าอ้างอิงก่อน deploy ไว้เทียบ

### เส้นทางที่ห้ามเรียกใน smoke test

| เส้นทาง | เหตุผล |
|---|---|
| `POST /api/admin/ingest` **พร้อม token** | จะลบและเขียนทับ `rag_documents` ของจริง |
| `POST /api/admin/sync-sci-news` **พร้อม token** | จะสั่ง Edge Function ไปดึงข่าวและเขียน `external_news` ของจริง |

ทั้งสองเส้นทางทดสอบได้เฉพาะแบบ **ไม่มี token** เพื่อดูว่าด่านปฏิเสธ (ข้อ 6)

---

## 6. สถานะ ณ ตอนปิดงาน

### Production

```
image : course-advisor-system-webapi:latest            1163e36361d9
        course-advisor-system-webapi:rollback-pre-m3   1163e36361d9   ← เพิ่มใหม่
container : course-advisor-system-webapi-1  Up 2 weeks (healthy)
webapi/api/ : 10 ไฟล์ (ไม่แตะ)
.env : ไม่มี ADVISOR_WEB_PASSWORD (ไม่แตะ)
```

### Local

```
HEAD      427ce19  docs(webapi): document api/ source recovery and verify M3 build
Branch    mko-phase2  (ahead of origin/mko-phase2 by 7)
Modified  0
```

### ยืนยันขอบเขต

| ข้อห้าม | สถานะ |
|---|---|
| Deploy / Restart / Build ทับ production image | **ไม่มี** |
| แก้ production `.env` | **ไม่มี** |
| เขียน production database | **ไม่มี** — ใช้ `SELECT count(*)` อย่างเดียว |
| เขียน Supabase | **ไม่มี** — ไม่ได้เชื่อมต่อ Supabase เลย |
| Push / Merge | **ไม่มี** |
| แก้ frontend repository | **ไม่มี** |
| เปิดเผย token / password / UUID / ข้อมูลส่วนบุคคล | **ไม่มี** — รายงานนี้มีแต่ตัวเลขนับ |
| เปลี่ยนแปลง production | **มีอย่างเดียว** — เพิ่ม image tag `rollback-pre-m3` ตามที่อนุมัติ |

---

## สิ่งที่ยังค้างก่อน Deploy

| # | งาน | ใครทำ |
|---|---|---|
| **1** | **ยืนยันว่าบัญชี admin ยังเป็น `role = admin` และ `status = approved` ใน Supabase** | เจ้าของ — ตรวจเองไม่ได้ด้วยสิทธิ์ที่มี |
| 2 | สร้าง `ADVISOR_WEB_PASSWORD` และใส่ production `.env` | ขั้น deploy |
| 3 | คัดลอก `package-lock.json` ขึ้นเซิร์ฟเวอร์ | ขั้น deploy — ยังไม่มีไฟล์นี้ และ `npm ci` บังคับต้องมี **ถ้าลืม build จะล้ม** |
| 4 | ยืนยันว่าขั้นตอน deploy ไม่ลบ `webapi/api/` ทิ้ง | ขั้น deploy — มีขั้นตอนใน `webapi/README.md` แล้ว |
| 5 | สำรองฐานข้อมูลก่อน deploy | แนะนำ (M3 ไม่แตะข้อมูล) |

### ระยะยาว

- เปลี่ยน UUID ใน `webapi/auth.test.mjs:480` เป็นค่าสังเคราะห์
- เขียน `docs/DEPLOY_WEB.md` หรือลบการอ้างอิงใน `docker-compose.prod.yml:169`
- เพิ่ม `.dockerignore`
- ถอด `requireAdminUser` ออกจาก handler เมื่อมั่นใจด่านกลางแล้ว — ตอนนี้ `/api/admin/*` จะเรียก Supabase สองรอบต่อคำขอ
