# C2 — บันทึก deploy และแผน rollback

| รายการ | ค่า |
|---|---|
| วันที่ | 11 ตุลาคม 2569 |
| สถานะ | **deploy บน production แล้ว · ยืนยันผลแล้ว** |
| ช่องที่ปิด | F1 — เรียก `sync-sci-news` ด้วย anon key โดยไม่ตรวจสิทธิ์ |
| เอกสารผลทดสอบ | `TEST_STATUS.md` |

> เอกสารนี้ **ไม่บันทึกค่าคีย์ ค่า secret หรือ URL ของ Vault** ใด ๆ
> รอบนี้ **ไม่เปลี่ยน production เพิ่ม** — เป็นการบันทึกผลที่เกิดขึ้นแล้วและเตรียมทางย้อน

---

## 1. ผลที่ยืนยันแล้วบน production

| # | สิ่งที่ทำ | ผลที่ยืนยัน |
|---|---|---|
| **P1** | deploy Edge Function ฉบับใหม่ | สำเร็จ · `verify_jwt` = **on** |
| **P2** | `POST` ด้วย anon key **ไม่มี** `x-cron-secret` | **`401` `{"error":"unauthorized"}`** |
| **P3** | job เดิม `sync-sci-news-every-30-min` | **ปิด** — ไม่ลบ |
| **P4** | job ใหม่ `sync-sci-news-every-30-min-v2` | **เปิด** · ทุก 30 นาที |
| **P5** | cron ยิงผ่าน scheduler | `request_id` **1765 · 1766 · 1767** → **`200` ทั้งสามรอบ** · ไม่ timeout · ไม่มี error |
| **P6** | deploy webapi ฉบับใหม่ | คอนเทนเนอร์ **healthy** |
| **P7** | `node --test` ด้วย `api/` ที่ใส่ patch แล้ว | **82 ผ่าน** |
| **P8** | admin กดปุ่ม Force Update ผ่านเว็บจริง | **สำเร็จ** |

### 1.1 ข้อชี้ขาดคือ P2

ช่อง F1 คือ "ใครก็ยิงได้ด้วย anon key" · **P2 ยืนยันบน production ว่าปิดแล้วจริง** จากการยิงของจริง ไม่ใช่จาก unit test

### 1.2 P5 ยืนยันมากกว่าที่ `job_run_details` บอกได้

`request_id` 1765–1767 มาจาก `net._http_response` ซึ่งเป็น **ผลตอบกลับ HTTP จริง** · ต่างจาก `cron.job_run_details` ที่ขึ้น `succeeded` แม้ปลายทางจะคืน `401` หรือ `500` (เหตุผลอยู่ใน `README.md` ข้อ 6.2)

สิ่งที่ P5 ยืนยันพร้อมกันสามอย่าง

| # | ยืนยันอะไร |
|---|---|
| 1 | job v2 ส่ง `x-cron-secret` ได้จริงผ่าน `pg_cron` |
| 2 | Edge Function ฉบับใหม่รับทางของ cron ได้ |
| 3 | `timeout_milliseconds` ที่ตั้งไว้เพียงพอกับ production จริง — 3 รอบไม่มี timeout |

> **`request_id` 1765–1767 เป็นลำดับของ production** · อย่าปนกับ `request_id` 8–10 ซึ่งเป็นของโปรเจกต์ทดสอบ

---

## 2. ปัญหาที่พบและแก้ระหว่าง deploy

| # | ปัญหา | ผลที่เกิด | แก้แล้วอย่างไร |
|---|---|---|---|
| **D1** | `project_url` ใน Vault เป็น **placeholder / ข้อความ Markdown** ไม่ใช่ URL | URL ที่ job ประกอบขึ้นไม่ใช่ที่อยู่จริงของฟังก์ชัน | แก้ค่าให้เป็น URL จริง |
| **D2** | `anon_key` ใน Vault **มีรูปแบบ JWT ไม่ถูกต้อง** | gateway ปฏิเสธที่ชั้นแรก คำขอไม่เคยถึงโค้ดฟังก์ชัน | แก้ค่าให้เป็น JWT ที่ถูกรูป |

ทั้งสองข้อ **แก้แล้ว** และ P5 คือหลักฐานว่าทางของ cron ใช้งานได้จริงหลังแก้

### 2.1 ทำไมขั้นตรวจก่อนลงมือไม่จับสองข้อนี้

`01_update_cron.sql` ขั้น 0.2 ตรวจเพียงว่า secret **มีอยู่และอ่านได้** (`usable`) **ไม่ได้ตรวจรูปร่างของค่า** จึงปล่อยทั้ง placeholder และ JWT ผิดรูปผ่านไปได้

ตรวจรูปร่างได้โดย**ไม่ต้องแสดงค่า** เช่น

| ค่า | ตรวจอะไรได้โดยไม่เปิดเผยค่า |
|---|---|
| `project_url` | ขึ้นต้นด้วย `https://` · ไม่มีช่องว่าง · ไม่มีวงเล็บเหลี่ยมหรือวงเล็บกลม ซึ่งเป็นร่องรอยของ Markdown |
| `anon_key` | ขึ้นต้นด้วย `eyJ` · แบ่งด้วยจุดได้ **3 ส่วน** |

> **ยังไม่แก้ `01_update_cron.sql`** เพราะไฟล์นั้นเป็น**บันทึกของสิ่งที่รันไปแล้วบน production** · ถ้าแก้จะไม่ตรงกับที่รันจริง
> ถ้าต้องการให้รอบหน้าปลอดภัยขึ้น ให้เพิ่มการตรวจรูปร่างเป็น **ไฟล์ใหม่แยก** — เป็นงานติดตาม ไม่ใช่งานรอบนี้

---

## 3. สิ่งที่สำรองไว้ — ทางย้อนที่มีจริง

| ส่วน | ของสำรอง | สถานะหลักฐาน |
|---|---|---|
| **C** webapi — image | **`course-advisor-system-webapi:c2-before-update`** — ผู้ดำเนินการยืนยันว่าสร้างไว้ **ก่อน build ใหม่** | **มี** · **ยังไม่ได้ตรวจไฟล์/ID** |
| **C** webapi — ไฟล์เดิม | `/home/ubuntu/c2-webapi-backup/` | **มี** |
| **B** cron — นิยาม job เดิม | **job เดิมถูกปิด ไม่ได้ลบ** นิยามยังอยู่ใน `cron.job` | **มี** |
| **A** Edge Function — โค้ดเดิม | ไฟล์ที่ผู้ดำเนินการเก็บไว้ก่อน deploy | **ยืนยันจากผู้ดำเนินการ · ยังไม่ได้ตรวจไฟล์สำรอง** |
| **A** Edge Function — สำเนาอีกชั้น | รีโปทีมออกแบบ `LastProject/supabase/functions/sync-sci-news/index.ts` ยังไม่ถูกแก้ (mtime 2026-09-04) | **มี** |

### 3.1 ⚠ สองข้อที่ต้องระวังเมื่อหยิบของสำรองมาใช้

#### ก. tag สำรองของ image — ต้องยืนยันว่ายังไม่ถูกเขียนทับ

> **tag สำรองที่ใช้จริงคือ `course-advisor-system-webapi:c2-before-update`** · ผู้ดำเนินการยืนยันว่า **สร้างไว้ก่อน build ใหม่**

| ประเด็น | สถานะ |
|---|---|
| ชื่อเต็มของต้นทาง | **`course-advisor-system-webapi:c2-before-update`** |
| image ที่ compose ใช้อยู่ | **`course-advisor-system-webapi:latest`** — ฉบับใหม่ที่ build ตอน deploy |
| สร้าง tag สำรองเมื่อไร | **ก่อน build ใหม่** — ยืนยันจากผู้ดำเนินการ |
| ตรวจแล้วหรือยังว่า tag นี้ชี้ไปที่ฉบับก่อน deploy จริง | **ยังไม่ได้ตรวจ** |
| ตรวจอย่างไร | เทียบ **image ID ของ `:c2-before-update`** กับ **ID ของ `:latest`** — ข้อ 4.4.1 ขั้น 3 |
| ถ้าสอง ID เท่ากันแปลว่าอะไร | **tag สำรองชี้ไปที่ฉบับใหม่แล้ว ใช้ย้อนไม่ได้** → คืนไฟล์จาก `/home/ubuntu/c2-webapi-backup/` แล้ว build |

> **สองชื่อนี้ต่างกันแค่ tag** — `:c2-before-update` คือของสำรอง · `:latest` คือฉบับที่ใช้งานอยู่
> อ้างชื่อโดยไม่ระบุ tag หมายถึง `:latest` คือฉบับใหม่ **ไม่ใช่ของสำรอง**

> **ขั้น 3 ของข้อ 4.4.1 เป็นด่านบังคับ ไม่ใช่ขั้นตรวจเสริม** — ถ้า tag ถูกเขียนทับ คำสั่งย้อนจะขึ้นสำเร็จแต่ได้โค้ดใหม่กลับมา

#### ข. ไฟล์สำรองของ Edge Function **ยังไม่ได้ตรวจ**

> **ผู้ดำเนินการยืนยันว่าเก็บโค้ด Edge Function เดิมไว้ก่อน deploy แล้ว** · **แต่ยังไม่ได้ตรวจไฟล์สำรองนั้น**

| ประเด็น | สถานะ |
|---|---|
| มีของสำรองไหม | **ยืนยันจากผู้ดำเนินการ** |
| ตรวจแล้วหรือยัง | **ยังไม่ได้ตรวจ** — ไม่ได้เปิดไฟล์ ไม่ได้เทียบกับอะไร |
| ย้อนได้แน่นอนไหม | **ยังสรุปไม่ได้** จนกว่าจะเปิดไฟล์ดู |
| มีทางสำรองอีกชั้นไหม | **มี** — สำเนาในรีโปทีมออกแบบซึ่งยังไม่ถูกแก้ |
| ควรทำอะไรก่อนถึงเวลาต้องย้อนจริง | เปิดไฟล์สำรองดูว่าเป็นโค้ด Edge Function ฉบับเดิมจริง แล้วเทียบกับสำเนาในรีโป |

> **เอกสารนี้ไม่อ้างว่าไม่ได้สำรอง และไม่อ้างว่าย้อนกลับได้แน่นอน** — บันทึกตามหลักฐานที่มีเท่านั้น

---

## 4. Rollback — สามส่วนแยกกัน

### 4.1 สภาพปัจจุบันที่ใช้เป็นจุดตั้งต้น

| ส่วน | ตอนนี้เป็นฉบับไหน |
|---|---|
| **A** Edge Function | **ใหม่** — POST เท่านั้น · ตรวจสิทธิ์ก่อนแตะเครือข่าย |
| **B** cron | **v2** — ส่ง `x-cron-secret` · job เดิมปิดไว้ |
| **C** webapi | **ใหม่** — ส่ง user token |

### 4.2 ย้อนแค่ส่วนเดียวจะได้อะไร

ฉบับเดิมของ Edge Function **รับ JWT ที่ถูกต้องทุกใบและไม่สนใจ header ที่ไม่รู้จัก** จึงอธิบายผลได้ตรง ๆ

| ย้อนแค่ส่วนไหน | ระบบทำงานต่อไหม | ความปลอดภัย |
|---|---|---|
| **A เท่านั้น** | **ทำงานปกติทุกทาง** — ฉบับเดิมรับทั้ง user token และ anon key | **‼ ช่องโหว่ F1 เปิดกลับทันที** |
| **B เท่านั้น** | **ข่าวหยุดอัปเดต** — job เดิมส่ง anon key ล้วน ฉบับใหม่คืน `401` | ยังปิดอยู่ |
| **C เท่านั้น** | **ปุ่ม Force Update ของ admin ใช้ไม่ได้** — webapi เดิมส่ง anon key · cron ไม่กระทบ | ยังปิดอยู่ |

### 4.3 ลำดับเมื่อต้องย้อนทั้งหมด

เลือกตามเป้าหมาย เพราะสองลำดับแลกกันคนละอย่าง

| เป้าหมาย | ลำดับ | ช่วงที่ใช้งานไม่ได้ | ช่องโหว่ |
|---|---|---|---|
| **ให้ระบบทำงานต่อโดยไม่สะดุด** | **A → C → B** | **ไม่มีเลย** | เปิดกลับทันทีที่ย้อน A |
| **คงการปิดช่องโหว่ให้นานที่สุด** | **C → A → B** | ปุ่ม admin ใช้ไม่ได้ช่วงระหว่าง C กับ A | ปิดอยู่จนถึงขั้น A |

> **ก่อน deploy เอกสารนี้เสนอ C → A → B** · หลัง deploy แล้ว **A → C → B ไม่มีช่วงใช้งานไม่ได้เลย** เพราะฉบับเดิมของ Edge Function รับทุกอย่างที่ฉบับใหม่รับ
> **ห้ามย้อน B ก่อน A ในทุกกรณี** — job เดิมส่ง anon key ล้วนไปหาฟังก์ชันฉบับใหม่ จะได้ `401` ทุกรอบ

### 4.4 คำสั่งย้อนแต่ละส่วน

| ส่วน | วิธี |
|---|---|
| **A** Edge Function | deploy ไฟล์สำรองที่ผู้ดำเนินการเก็บไว้ · **เปิดไฟล์ตรวจก่อน** (ข้อ 3.1 ข) · ถ้าไฟล์นั้นใช้ไม่ได้ ใช้สำเนาในรีโปทีมออกแบบแทน |
| **B** cron | `scripts/02_rollback_cron.sql` — **ใช้ได้เพราะ job เดิมถูกปิด ไม่ได้ลบ** |
| **C** webapi | ดูข้อ 4.4.1 — ต้นทางคือ **`course-advisor-system-webapi:c2-before-update`** |

#### 4.4.1 ย้อน webapi

> ทุกคำสั่ง compose ต้องมี **`-p course-advisor-system`** และ **`-f` ทั้งสี่ไฟล์**
> **คำสั่งละหนึ่งบรรทัด** — คำสั่งหลายบรรทัดผ่าน ssh เคยถูกตัดกลางคัน

| # | ไฟล์ compose ที่ต้องส่งทุกครั้ง |
|---|---|
| 1 | `/home/ubuntu/course-advisor-system/docker-compose.prod.yml` |
| 2 | `/home/ubuntu/course-advisor-system/docker-compose.staging.yml` |
| 3 | `/home/ubuntu/release-2fdc6f2/compose.pin-backend-2fdc6f2.yml` |
| 4 | `/home/ubuntu/release-2fdc6f2/compose.pin-frontend-2fdc6f2.yml` |

**ขั้น 1 — ดู image ที่ webapi ใช้อยู่ตอนนี้ (ฉบับใหม่)**

```bash
docker compose -p course-advisor-system -f /home/ubuntu/course-advisor-system/docker-compose.prod.yml -f /home/ubuntu/course-advisor-system/docker-compose.staging.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-backend-2fdc6f2.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-frontend-2fdc6f2.yml images webapi
```

บันทึกไว้สองค่าจากผลลัพธ์ — **`REPOSITORY:TAG`** และ **`IMAGE ID`**

> คาดว่าได้ `course-advisor-system-webapi:latest` · **ถ้าได้ tag อื่น** (เช่น tag ที่ pin ไว้ในไฟล์ release) ให้ขั้น 4 ชี้ไปที่ tag นั้นแทน `:latest` · ขั้น 6 จะจับได้เองถ้าชี้ผิดตัว

**ขั้น 2 — ดู image ID ของ tag สำรอง**

```bash
docker image inspect --format '{{.Id}}' course-advisor-system-webapi:c2-before-update
```

**ขั้น 3 — ด่านบังคับ: เทียบ ID จากขั้น 1 กับขั้น 2**

| ผล | แปลว่า | ทำอะไร |
|---|---|---|
| **ต่างกัน** | `:c2-before-update` เป็นฉบับก่อน deploy จริง | **ไปขั้น 4** |
| **เท่ากัน** | **`:c2-before-update` ชี้ไปที่ฉบับใหม่ — ใช้ย้อนไม่ได้** | **หยุด** → คืนไฟล์จาก `/home/ubuntu/c2-webapi-backup/` แล้ว build ใหม่ |

**ขั้น 4 — ชี้ `:latest` กลับไปหาฉบับสำรอง**

```bash
docker tag course-advisor-system-webapi:c2-before-update course-advisor-system-webapi:latest
```

**ขั้น 5 — สร้างคอนเทนเนอร์ใหม่เฉพาะ webapi**

```bash
docker compose -p course-advisor-system -f /home/ubuntu/course-advisor-system/docker-compose.prod.yml -f /home/ubuntu/course-advisor-system/docker-compose.staging.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-backend-2fdc6f2.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-frontend-2fdc6f2.yml up -d --no-deps --no-build --force-recreate webapi
```

| ธง | ทำอะไร |
|---|---|
| `--no-deps` | **ไม่แตะบริการอื่น** — postgres, FastAPI, frontend, Caddy ไม่ถูก restart |
| `--no-build` | **บังคับใช้ image ที่มีอยู่ ไม่ build ใหม่** — ถ้า build ใหม่จะได้โค้ดใหม่กลับมา |
| `--force-recreate` | สร้างคอนเทนเนอร์ใหม่แม้ config ไม่เปลี่ยน |

**ขั้น 6 — ยืนยันว่าย้อนจริง**

```bash
docker compose -p course-advisor-system -f /home/ubuntu/course-advisor-system/docker-compose.prod.yml -f /home/ubuntu/course-advisor-system/docker-compose.staging.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-backend-2fdc6f2.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-frontend-2fdc6f2.yml images webapi
```

| ผล | แปลว่า |
|---|---|
| `IMAGE ID` **เท่ากับค่าจากขั้น 2** | **ย้อนสำเร็จ** |
| `IMAGE ID` **ยังเท่าค่าจากขั้น 1** | **ยังไม่ได้ย้อน** — อย่าสรุปจากข้อความว่าคำสั่งสำเร็จ |

**ขั้น 7 — ตรวจสุขภาพ**

```bash
docker compose -p course-advisor-system -f /home/ubuntu/course-advisor-system/docker-compose.prod.yml -f /home/ubuntu/course-advisor-system/docker-compose.staging.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-backend-2fdc6f2.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-frontend-2fdc6f2.yml ps webapi
```

ต้องได้ `healthy`

> **ทางเลือกเมื่อขั้น 3 สั่งให้หยุด** — คืนไฟล์จาก `/home/ubuntu/c2-webapi-backup/` แล้ว build ใหม่
> ช้ากว่าแต่ไม่พึ่ง tag · **ขั้นนั้นต้องเอา `--no-build` ออก** และยังต้องเทียบ image ID ตามขั้น 6 เหมือนกัน

### 4.5 คำสั่งฉุกเฉิน — ถ้าข่าวหยุดอัปเดต

ใช้เมื่อสงสัยว่าไม่มี job ไหนเปิดอยู่

```sql
select jobid, jobname, active
from cron.job
where jobname like '%sync-sci-news%'
order by jobname;
```

| สิ่งที่เห็น | ทำอะไร |
|---|---|
| v2 เปิด · เดิมปิด | **ถูกต้องแล้ว** — ไม่ต้องทำอะไร |
| ปิดทั้งคู่ | เปิดตัวที่ตรงกับฉบับของ Edge Function ที่ deploy อยู่ |
| **เปิดทั้งคู่** | **‼ ยิงซ้ำสองเท่า** — ปิดตัวเดิมทันที |

```sql
-- เปิด v2 กลับ (ใช้เมื่อ Edge Function ยังเป็นฉบับใหม่)
select cron.alter_job(
  job_id := (select jobid from cron.job where jobname = 'sync-sci-news-every-30-min-v2'),
  active := true
);
```

### 4.6 สิ่งที่ไม่ต้องย้อน

| รายการ | เหตุผล |
|---|---|
| secret ที่ตั้งไว้ | ถ้าไม่มีใครใช้ก็ไม่มีผล · เก็บไว้ลองใหม่ได้ |
| ค่า Vault ที่แก้ไปตามข้อ D1 และ D2 | **ค่าเดิมผิดอยู่แล้ว** การย้อนกลับไปหาค่าที่ผิดไม่มีประโยชน์ |
| ตาราง `c2_sync_runs` | ไม่มี secret · `anon`/`authenticated` เข้าไม่ถึง · เป็นหลักฐานสืบย้อน |
| ข้อมูลใน `external_news` | ไม่ถูกแตะโดยการย้อน |

---

## 5. สิ่งที่ยังไม่ได้ทดสอบ

| # | ยังไม่ได้ทำ | บล็อกอะไรไหม |
|---|---|---|
| **1** | **rollback cron บน production จริง** (`02_rollback_cron.sql`) | ไม่บล็อกการใช้งาน · **แต่คือทางย้อนที่ยังไม่เคยลอง** |
| 2 | `x-cron-secret` **ผิด** → `401` บน production | ผ่านบนโปรเจกต์ทดสอบ (G5) |
| 3 | `GET` → `405` บน production | ผ่านบนโปรเจกต์ทดสอบ (G4) |
| 4 | `role = user` → `403` บน production | ผ่านบนโปรเจกต์ทดสอบ (G8) |
| 5 | **บัญชี `editor` จริง** | **ไม่เคยทดสอบที่ไหนเลย** — มีแต่ unit test |
| 6 | `verify_jwt = false` | ยังไม่ทดสอบ · ไม่กระทบวันนี้ |
| 7 | สถานะ JWT signing keys | ยังไม่บันทึก · กำหนดว่าการออกแบบนี้อยู่ได้นานแค่ไหน (`README.md` ข้อ 7) |
| 8 | มีระบบอื่นเรียก Edge Function นี้อยู่อีกไหม | **ถ้ามีจะได้ `401` เงียบ ๆ** — ควรดู Edge Function logs |
| 9 | **เปิดตรวจไฟล์สำรองโค้ด Edge Function เดิม** | ผู้ดำเนินการยืนยันว่ามี · **ยังไม่ได้ตรวจ** — ดูข้อ 3.1 ข |

> **เวอร์ชัน `pg_cron` และ `pg_net` เทียบแล้วและตรงกัน** จึงย้ายออกจากรายการนี้ไปอยู่ในข้อ 6

### 5.1 ข้อ 1 สำคัญที่สุดในรายการนี้

**transaction rollback ผ่านบนโปรเจกต์ทดสอบแล้ว** — ยืนยันว่าเมื่อล้มกลาง transaction สถานะ `active` ของ job กลับมาเหมือนเดิม

แต่ **ยังไม่เคยรัน `02_rollback_cron.sql` บน production** จึงยังไม่ยืนยันว่า

| # | ยังไม่ยืนยัน |
|---|---|
| 1 | สคริปต์หา job ทั้งสองตัวบน production ได้ถูกต้อง |
| 2 | การสลับ เปิดเดิม/ปิด v2 ทำได้ครบในหนึ่ง transaction |
| 3 | job เดิมที่ถูกปิดไว้นาน กลับมาทำงานได้จริงเมื่อเปิด |

ข้อ 3 เดาไม่ได้ — ต้องเปิดจริงจึงรู้ และนั่นหมายถึงต้องย้อน A ด้วย (ดูข้อ 4.3)

### 5.2 ข้อ 5 — ทำไมแยก editor ออกจาก admin

โค้ดตรวจ `role in ('admin','editor')` · การทดสอบด้วยบัญชี admin **ยืนยันได้เฉพาะค่า `admin`** · ทาง `editor` ผ่านเฉพาะใน unit test ซึ่งจำลองคำตอบของฐานข้อมูล ไม่ได้ยิงของจริง

---

## 6. หลักฐาน — แยก production กับ test ให้ชัด

| หลักฐาน | โปรเจกต์ทดสอบ | **production** |
|---|---|---|
| ไม่มี credential → `401` | ✅ G1 | — |
| bearer มั่ว → `401` | ✅ G2 | — |
| **anon key เป็น bearer → `401`** | ✅ G3 | **✅ P2** |
| `GET` → `405` | ✅ G4 | — |
| cron secret ผิด → `401` | ✅ G5 | — |
| cron secret ถูก → `200` | ✅ G6 | **✅ P5** — ผ่าน scheduler 3 รอบ |
| admin → `200` | ✅ G7 | **✅ P8** — ผ่านปุ่มในเว็บจริง |
| `role = user` → `403` | ✅ G8 | — |
| **`role = editor` → `200`** | ❌ unit test เท่านั้น | ❌ |
| cron ผ่าน scheduler | ✅ `request_id` 8 · 9 · 10 | **✅ `request_id` 1765 · 1766 · 1767** |
| transaction rollback คืนสถานะ job | **✅ ผ่าน** | ❌ **ยังไม่ทดสอบ** |
| `02_rollback_cron.sql` | ❌ รันที่นั่นไม่ได้โดยการออกแบบ | ❌ **ยังไม่ทดสอบ** |
| **เวอร์ชัน `pg_cron`** | **✅ 1.6.4** | **✅ 1.6.4** |
| **เวอร์ชัน `pg_net`** | **✅ 0.20.4** | **✅ 0.20.4** |

> **สอง extension ตรงกันทั้งเวอร์ชัน** — ทำให้ผลการทดสอบ cron บนโปรเจกต์ทดสอบ **โอนมาอธิบาย production ได้หนักแน่นขึ้น**
> แต่ยังไม่แทนผลจริงบน production ซึ่งคือ P5

### 6.1 หลักฐานฝั่งโค้ด — เครื่องพัฒนา

| ชุด | ผล |
|---|---|
| `deno check` | ผ่าน |
| `deno test` — Edge Function | **14 ผ่าน** |
| `node --test` — webapi patch | **12 ผ่าน** |
| `node --test` — ชุดเดิมของ webapi | **82 ผ่าน** |
| `node --test` — **ด้วย `api/` ที่ใส่ patch แล้ว (P7)** | **82 ผ่าน** |

---

## 7. ขอบเขตของรอบนี้

| รายการ | สถานะ |
|---|---|
| เปลี่ยน production เพิ่ม | **ไม่ได้ทำ** |
| เรียก sync บน production | **ไม่ได้ทำ** |
| แก้ C1 policies | **ไม่ได้ทำ** |
| แก้ `01_update_cron.sql` หรือ `02_rollback_cron.sql` | **ไม่ได้ทำ** — เก็บไว้เป็นบันทึกของสิ่งที่รันจริง |
| บันทึกค่าคีย์ ค่า secret หรือ URL ของ Vault | **ไม่มีในเอกสารนี้** |
| อ้างผลที่ยังไม่ได้ทดสอบ | **ไม่มี** — ดูข้อ 5 และ 6 |
