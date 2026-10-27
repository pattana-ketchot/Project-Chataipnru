# C2 — ปิดช่องเรียก `sync-sci-news` โดยไม่ตรวจสิทธิ์

> **deploy บน production แล้วและยืนยันผลแล้ว** — บันทึกผลอยู่ใน `DEPLOY_PLAN.md` ข้อ 1 และ `TEST_STATUS.md` ข้อ 0
> เอกสารนี้อธิบาย **ที่มาและเหตุผลของการออกแบบ** · ไม่ได้แตะ C1 policies
> **ไม่อ่านและไม่แสดงค่า secret ใด ๆ**

| รายการ | ค่า |
|---|---|
| วันที่ | 11 ตุลาคม 2569 |
| ต่อจาก | `C1_POST_MIGRATION_SECURITY_REVIEW.md` ข้อ F1 |
| source ที่ใช้ | `D:/workspace/LastProject/supabase/functions/sync-sci-news/index.ts` |

---

## 1. ปัญหา — ยืนยันจาก source จริงแล้ว

อ่าน source ของ Edge Function แล้ว ยืนยันทุกข้อ

| บรรทัด | สิ่งที่พบ |
|---|---|
| `121-124` | `Deno.serve` ยกเว้น `OPTIONS` แล้ว **เข้าสู่การ sync ทันทีสำหรับทุก method ที่เหลือ** |
| `127` | **`fetch(SOURCE_URL)` เป็นคำสั่งแรก** — ยิงเว็บต้นทางก่อนตรวจอะไรทั้งสิ้น |
| `138-141` | สร้าง client ด้วย **`SUPABASE_SERVICE_ROLE_KEY`** — เขียน `external_news` โดยข้าม RLS |
| ทั้งไฟล์ | **ไม่มีการตรวจ `role` หรือ `status` แม้แต่บรรทัดเดียว** |

ประกอบกับ gateway ตั้ง `verify_jwt = true` ซึ่งตรวจเพียงว่า JWT ถูกต้อง **ไม่ตรวจ role** และ anon key เป็น JWT ที่ถูกต้องและอยู่ใน JavaScript ของหน้าเว็บตามธรรมชาติ

```
ใครก็ได้ -> POST /functions/v1/sync-sci-news  (Authorization: Bearer <anon key>)
         -> gateway: JWT ถูกต้อง ผ่าน
         -> ฟังก์ชัน: ไม่ตรวจอะไร -> ยิงเว็บต้นทาง -> เขียนฐานข้อมูลด้วย service role
```

### ⚠ สถานะการเทียบโค้ดที่ deploy อยู่เดิมกับ source นี้

เอกสารตรวจรอบก่อนบันทึกว่า Edge Function เป็น **version 1 · ยังไม่เคย redeploy** ส่วน source ที่ใช้ทำ patch นี้มาจากรีโปของทีมออกแบบในเครื่อง

| ประเด็น | สถานะ |
|---|---|
| มีบันทึกผลการเทียบก่อน deploy ไหม | **ไม่มี** |
| มีไฟล์สำรองของฉบับเดิมไหม | **ผู้ดำเนินการยืนยันว่าเก็บไว้ก่อน deploy แล้ว** · **ยังไม่ได้ตรวจไฟล์นั้น** |
| เทียบย้อนหลังได้ไหม | **ได้ถ้าไฟล์สำรองใช้ได้** — ต้องเปิดตรวจก่อน · ดู `DEPLOY_PLAN.md` ข้อ 3.1 ข |
| ทางสำรองอีกชั้น | สำเนาในรีโปทีมออกแบบซึ่งยังไม่ถูกแก้ |

---

## 2. สิ่งที่แก้

### 2.1 Edge Function — `edge-function/index.ts`

| # | การเปลี่ยนแปลง | แก้ปัญหาอะไร |
|---|---|---|
| 1 | **รับเฉพาะ `POST`** (และ `OPTIONS` สำหรับ CORS) | ฉบับเดิมรับ `GET` ด้วย ทำให้เรียกจากแถบที่อยู่ของเบราว์เซอร์ได้ |
| 2 | **ตรวจสิทธิ์ก่อนแตะเครือข่ายและฐานข้อมูล** | ฉบับเดิมยิงเว็บต้นทางก่อนเสมอ ผู้ไม่มีสิทธิ์ก่อภาระให้ต้นทางได้ |
| 3 | รองรับ **ผู้ดูแล** — ตรวจ `role ∈ {admin, editor}` และ `status = approved` | ปิดช่องที่ใครก็เรียกได้ |
| 4 | รองรับ **cron** — ตรวจ `x-cron-secret` เทียบกับ `SYNC_CRON_SECRET` | ให้งานตั้งเวลาทำงานต่อได้โดย**ไม่ใช้ anon key เป็นหลักฐานสิทธิ์** |
| 5 | เทียบ secret แบบ **เวลาคงที่** | กันการเดาทีละตัวอักษรจากเวลาที่ตอบกลับ |
| 6 | ส่ง secret มาแต่ยังไม่ตั้งค่า → **`503` ไม่ใช่ปล่อยผ่าน** | ตั้งค่าไม่ครบต้องล้ม ไม่ใช่เปิดโล่ง |
| 7 | แยก `handler` และ `runSync` ออกจาก `Deno.serve` | ทดสอบได้โดยไม่ต้องเปิดพอร์ต |
| 8 | ไม่ส่งรายละเอียด error ภายในกลับไปหาผู้เรียก | ฉบับเดิมคืน `String(err)` ซึ่งอาจมีรายละเอียดภายใน |

> **ตรรกะการดึงข่าว การแปลง HTML การ dedup และการตัดแถวเก่า ไม่ถูกแก้แม้แต่บรรทัดเดียว**

### 2.2 webapi — `webapi/sync-sci-news.js`

เปลี่ยนจากส่ง **anon key** เป็นส่ง **access token ของผู้ใช้ที่ผ่านด่านแล้ว**

```diff
- Authorization: `Bearer ${auth.anonKey}`,
+ Authorization: `Bearer ${auth.token}`,
    apikey: auth.anonKey,
```

`apikey` ยังเป็น anon key เพราะ gateway ใช้ระบุโปรเจกต์ **ไม่ใช่หลักฐานสิทธิ์**

### 2.3 webapi — `webapi/adminAuth.js`

เพิ่ม `token` เข้าไปในค่าที่คืนเมื่อผ่านด่าน **เป็นการเพิ่มฟิลด์อย่างเดียว** ผู้เรียกเดิม (`extract-file`, `ingest`) ไม่ต้องแก้และพฤติกรรมไม่เปลี่ยน

### 2.4 cron — `scripts/01_update_cron.sql`

สร้าง job ใหม่ที่ส่ง `x-cron-secret` อ่านค่าจาก Vault **ปิด job เดิมแทนการลบ** เพื่อให้ย้อนได้

---

## 3. การตั้งค่า gateway JWT — รองรับสองทางอย่างไร

### 3.1 ตัวเลือกที่พิจารณา

| ทาง | `verify_jwt` | ด่านที่มี | ประเมิน |
|---|---|---|---|
| **ก — ที่เลือก** | **คงไว้ `true`** | gateway + โค้ดในฟังก์ชัน | **สองชั้น** · ไม่ต้องแก้ config ของ gateway เลย |
| ข | `false` + `withSupabase({ auth: ['user', 'secret:...'] })` | โค้ดในฟังก์ชันอย่างเดียว | ตามแนวทางทางการล่าสุด แต่**เหลือด่านเดียว** และต้องเพิ่ม dependency ใหม่ |

### 3.2 ทำไมเลือกทาง ก

เอกสารทางการระบุว่าเมื่อ `verify_jwt` เปิด (ค่าตั้งต้น) แพลตฟอร์มจะตรวจ `Authorization` ก่อนโค้ดทำงาน ถ้า header หายไป ผิดรูป หรือลงนามด้วยคีย์อื่น จะคืน `401` โดยที่โค้ดไม่เคยถูกเรียก

| ข้อดีของการคงไว้ | |
|---|---|
| 1 | **ไม่ต้องแก้ config ของ gateway เลย** — ลดจำนวนสิ่งที่เปลี่ยนในรอบเดียว |
| 2 | คำขอที่ไม่มี JWT ที่ถูกต้องถูกตัดทิ้งก่อนถึงโค้ด |
| 3 | ถ้าโค้ดตรวจสิทธิ์ในฟังก์ชันพลาด **ยังมี gateway เป็นชั้นรอง** |
| 4 | cron ยังส่ง anon key ใน `Authorization` ได้เหมือนเดิมเพื่อผ่านชั้นแรก **แต่สิทธิ์จริงมาจาก `x-cron-secret`** |

เอกสารทางการเสนอให้ปิด `verify_jwt` เมื่อรับผู้เรียกแบบ secret เพราะ cron ส่ง secret มาที่ header `apikey` ไม่ใช่ user JWT · **แต่การออกแบบนี้ให้ cron ส่งทั้งสองอย่าง** จึงผ่านทั้งสองชั้นได้โดยไม่ต้องปิด

> **ถ้าภายหลังต้องการย้ายไปทาง ข** เอกสารทางการมีรูปแบบ `auth: ['user', 'secret:automations']` ที่ wrapper จะลองทีละโหมดแล้วตั้ง `ctx.authMode` ให้ · ใช้ `ctx.supabase` สำหรับอ่านในนามผู้ใช้ และ `ctx.supabaseAdmin` สำหรับงานที่ต้องข้าม RLS

### 3.3 เอกสารอ้างอิง

- [Securing Edge Functions](https://supabase.com/docs/guides/functions/auth)
- [Function Configuration](https://supabase.com/docs/guides/functions/function-configuration)
- [Authorization headers](https://supabase.com/docs/guides/functions/auth-headers)
- [Deploy to Production](https://supabase.com/docs/guides/functions/deploy)

---

## 4. ชุดทดสอบ

> **สถานะการทดสอบ — ดูผลจริงทั้งหมดใน `TEST_STATUS.md`**
>
> | ชุด | ผล |
> |---|---|
> | `deno test` — Edge Function | **14 ผ่าน 0 ล้ม** |
> | `node --test` — webapi patch | **12 ผ่าน 0 ล้ม** |
> | `node --test` — ชุดเดิมของ webapi | **82 ผ่าน 0 ล้ม** |
> | **Gateway G1–G8** บนโปรเจกต์ทดสอบ | **ผ่านครบ 8 ข้อ** |
> | **cron scheduler ด้วย `timeout_milliseconds = 30000`** | **ผ่าน 3 รอบ** — โปรเจกต์ทดสอบ |
> | **transaction rollback ของ cron** | **ผ่าน** — โปรเจกต์ทดสอบ |
> | **anon POST ไม่มี `x-cron-secret` → `401`** | **ผ่านบน production** ← ข้อชี้ขาด |
> | **cron v2 ผ่าน scheduler** | **`200` 3 รอบบน production** |
> | **admin กด Force Update ผ่านเว็บจริง** | **ผ่านบน production** |
> | `02_rollback_cron.sql` บน production | **`NOT RUN`** |
> | บัญชี `editor` จริง | **`NOT RUN`** ทั้งสองโปรเจกต์ |

`tests/sync-sci-news.auth.test.ts` — **14 ข้อ** รันด้วย

```bash
deno test --allow-env --allow-net=esm.sh tests/sync-sci-news.auth.test.ts
```

### วิธีจำลอง

ดัก `globalThis.fetch` ชั้นเดียวแล้วแยกเส้นทางตาม URL ซึ่งครอบทั้งเว็บข่าวต้นทางและทุกคำขอที่ `supabase-js` ยิงออก (auth และ REST) **จึงทดสอบ client จริงโดยไม่ต้องแก้โค้ด production และไม่ต้องต่อเน็ต**

### สิ่งที่ครอบ

| กลุ่ม | ข้อ |
|---|---|
| method | `OPTIONS` ผ่าน · **`GET` ได้ 405** |
| cron | secret ถูก → ทำงาน · secret ผิด → 401 · ยังไม่ตั้งค่า → **503 ไม่ใช่ปล่อยผ่าน** |
| ผู้ใช้ | **anon key เป็น bearer → 401** · ไม่ส่งอะไร → 401 · `role=user` → 403 · `status=pending` → 403 · ไม่มีแถว → 403 · admin → ทำงาน · editor → ทำงาน |
| ตรรกะเดิม | ข่าวซ้ำไม่เพิ่ม และไม่ลบอะไร · เว็บต้นทางล้ม → 502 และไม่แตะฐานข้อมูล |

### ข้อทดสอบที่สำคัญที่สุด

ทุกกรณีที่สิทธิ์ไม่ผ่าน **ยืนยันว่า `upstreamCalls() === 0`** — คือไม่ยิงเว็บต้นทางเลย ซึ่งเป็นจุดที่ฉบับเดิมพลาด

---

## 5. ขั้นตอน deploy

> **deploy ไปแล้ว** · ข้อนี้คือแผนที่ใช้จริง เก็บไว้เป็นบันทึก
> **ผลที่เกิดขึ้นจริงและแผน rollback ปัจจุบันอยู่ใน `DEPLOY_PLAN.md`** · ถ้าสองที่ไม่ตรงกัน ให้ยึด `DEPLOY_PLAN.md`
>
> ทุกขั้นต้องขออนุมัติแยกก่อนลงมือ · **ลำดับสำคัญ** เพราะช่วงระหว่างขั้นมีผลต่อการทำงานของ cron

### ก่อนลงมือ — บันทึกสิ่งที่ต้องใช้ย้อนกลับ

| # | สิ่งที่ต้องบันทึก | วิธี |
|---|---|---|
| 1 | โค้ด Edge Function ฉบับที่ deploy อยู่ | คัดลอกจาก Dashboard → Edge Functions → `sync-sci-news` เก็บเป็นไฟล์ |
| 2 | นิยาม cron job เดิม | `select command from cron.job where jobname='sync-sci-news-every-30-min'` **เก็บไว้ในที่ปลอดภัย ไม่วางในแชตหรือเอกสาร เพราะมีคีย์อยู่ข้างใน** |
| 3 | ยืนยันว่าโค้ดที่ deploy ตรงกับไฟล์ฉบับเดิมในรีโป | เทียบด้วยตา |

### ลำดับที่เสนอ

```
1. สร้าง secret                                   openssl rand -hex 32
2. ตั้ง Edge Function secret  SYNC_CRON_SECRET     Dashboard -> Edge Functions -> Secrets
3. สร้าง Vault secret         sync_cron_secret     scripts/01_update_cron.sql ขั้น 1
   (ค่าเดียวกับข้อ 2)
4. deploy Edge Function ฉบับใหม่                   supabase functions deploy sync-sci-news
   ‼ ตั้งแต่จุดนี้ cron เดิมจะได้ 401 จนกว่าจะทำขั้น 5
5. เปลี่ยน cron                                    scripts/01_update_cron.sql ขั้น 2-3
6. deploy webapi ฉบับใหม่                          build + up -d --no-deps webapi
7. ตรวจตามข้อ 6
```

### ⚠ ช่วงที่ cron จะล้มชั่วคราว

ระหว่างขั้น 4 ถึง 5 **cron เดิมจะได้ `401`** เพราะฉบับใหม่ไม่รับ anon key เป็นหลักฐานสิทธิ์แล้ว

| ประเด็น | ประเมิน |
|---|---|
| กระทบผู้ใช้ไหม | **ไม่** — แค่ข่าวไม่อัปเดตในรอบนั้น ข้อมูลเดิมยังแสดงปกติ |
| นานแค่ไหน | ขึ้นกับว่าทำขั้น 5 เร็วแค่ไหน · ถ้าทำติดกันจะไม่ข้ามรอบเลย |
| ลดได้ไหม | ทำขั้น 4 และ 5 ติดกันทันที · หรือเริ่มงานทันทีหลัง cron เพิ่งรันจบ |

### ⚠ ลำดับของ webapi

ขั้น 6 ต้องทำ **หลัง** ขั้น 4 เพราะ webapi ฉบับใหม่ส่ง user token ซึ่งฉบับเดิมของ Edge Function ไม่รู้จัก (จะยังผ่าน แต่ไม่มีประโยชน์) · ส่วน webapi ฉบับเดิมที่ส่ง anon key จะได้ `401` จากฉบับใหม่

**แปลว่าระหว่างขั้น 4 ถึง 6 ปุ่มบังคับ sync ในหน้า admin จะใช้ไม่ได้ชั่วคราว** — ไม่กระทบผู้ใช้ทั่วไป

---

## 6. การตรวจหลัง deploy

### 6.1 ตรวจที่ทำได้ทันที (read-only)

| # | ทดสอบ | ต้องได้ | เขียนข้อมูลไหม |
|---|---|---|---|
| 1 | `OPTIONS` ไปที่ Edge Function | `200` | ไม่ |
| 2 | `GET` ไปที่ Edge Function | **`405`** | ไม่ |
| 3 | `POST` ด้วย **anon key** เป็น bearer | **`401`** ← ข้อชี้ขาด | ไม่ |
| 4 | `POST` ด้วย `x-cron-secret` ผิด | **`401`** | ไม่ |
| 5 | `POST` ไม่มีอะไรเลย | `401` | ไม่ |
| 6 | `/api/sci-connect-news` | `200` และข่าวแสดงปกติ | ไม่ |

### 6.2 ⚠ `cron.job_run_details` บอกอะไรได้จริง

> **`status = succeeded` ยืนยันเพียงว่าคำสั่ง SQL ของ job ทำงานจบโดยไม่ error
> ไม่ได้ยืนยันว่า HTTP ไปถึง Edge Function และ sync สำเร็จ**

เหตุผล — `net.http_post` ของ `pg_net` เป็นแบบ **คิว** คืน `request_id` ทันทีแล้วจบคำสั่ง SQL · การยิง HTTP จริงเกิดภายหลังโดย background worker

ดังนั้นกรณีเหล่านี้ `job_run_details` จะขึ้น `succeeded` ทั้งหมด

| สิ่งที่เกิดขึ้นจริง | `job_run_details` |
|---|---|
| Edge Function คืน `200` | `succeeded` |
| **Edge Function คืน `401` เพราะ secret ผิด** | **`succeeded`** |
| **Edge Function คืน `500`** | **`succeeded`** |
| **ต่อปลายทางไม่ได้เลย** | **`succeeded`** |

**ต้องดูผลตอบกลับจาก `pg_net` ถึงจะรู้ว่าสำเร็จจริง**

### 6.3 ผูก `request_id` กับผลตอบกลับของ `pg_net`

#### ขั้น ก — ตรวจ schema และเวอร์ชันจริงก่อน

ชื่อและโครงสร้างตารางของ `pg_net` ต่างกันตามเวอร์ชัน **อย่าเดา**

```sql
-- เวอร์ชันที่ติดตั้งอยู่
select extname, extversion from pg_extension where extname = 'pg_net';

-- ตารางที่มีจริงใน schema net
select table_name
from information_schema.tables
where table_schema = 'net'
order by table_name;

-- คอลัมน์ของตารางผลตอบกลับ (ชื่อที่พบบ่อยคือ _http_response)
select table_name, column_name, data_type
from information_schema.columns
where table_schema = 'net'
order by table_name, ordinal_position;
```

> ถ้าไม่พบตารางผลตอบกลับ แปลว่าเวอร์ชันนี้เก็บผลต่างออกไป — **หยุดแล้วอ่านเอกสารของเวอร์ชันนั้นก่อน** อย่าเขียน query เดาเอง

#### ขั้น ข — ให้ job บันทึก `request_id` ไว้ใช้ผูก

job ปัจจุบันเรียก `net.http_post` แล้วทิ้งค่าที่คืนมา จึงไม่มีอะไรให้ผูกย้อนหลัง

**ทางเลือกที่ไม่ต้องแก้ job** — ผูกด้วยช่วงเวลาแทน โดยอาศัยว่า job รันทุก 30 นาที

```sql
-- แทนชื่อตารางด้วยชื่อที่พบจากขั้น ก
-- ‼ ไม่ดึงคอลัมน์ headers เพราะมี secret อยู่ข้างใน
select
  id                 as request_id,
  status_code,
  created,
  left(coalesce(content, ''), 200) as body_preview
from net._http_response
where created > now() - interval '2 hours'
order by created desc
limit 10;
```

| `status_code` | แปลว่า |
|---|---|
| **`200`** | **sync สำเร็จจริง** |
| `401` | secret ไม่ตรง หรือ gateway ปฏิเสธ — **ดู README ข้อ 7** |
| `403` | ผ่าน gateway แล้วแต่ด่านในฟังก์ชันปฏิเสธ |
| `405` | ส่ง method ผิด |
| `502` | เว็บข่าวต้นทางล้ม (ฟังก์ชันทำงานถูกต้อง) |
| `500` | ฟังก์ชันพัง |
| ไม่มีแถวเลย | คำขอยังไม่ถูกส่ง หรือ worker ของ `pg_net` ไม่ทำงาน |

> **ห้าม `select *`** จากตารางนี้ เพราะคอลัมน์ `headers` ของทั้งคำขอและผลตอบกลับอาจมี `apikey`, `Authorization` และ `x-cron-secret` อยู่

#### ขั้น ค — ถ้าต้องการผูกแบบแม่นยำ (ไม่ใช่ตามช่วงเวลา)

ต้องแก้ job ให้เก็บ `request_id` ลงตารางของเราเอง ซึ่ง **เป็นการเพิ่มตารางใหม่ ต้องขออนุมัติแยก**

```sql
-- แนวคิด ยังไม่เสนอให้รัน
-- create table ops.sync_sci_news_runs (
--   request_id bigint primary key,
--   queued_at  timestamptz not null default now()
-- );
--
-- แล้วใน job เปลี่ยนจาก  select net.http_post(...)
-- เป็น                   insert into ops.sync_sci_news_runs(request_id)
--                        select net.http_post(...);
```

### 6.4 ตรวจที่เขียนข้อมูลจริง — ทำหลังข้อ 6.1 ผ่านแล้ว

| # | ทดสอบ | ต้องได้ |
|---|---|---|
| 7 | รอ cron รอบถัดไป แล้วดู **`status_code` จาก `pg_net`** (ไม่ใช่แค่ `job_run_details`) | **`200`** |
| 8 | กดปุ่มบังคับ sync ในหน้า admin ด้วยบัญชี admin | สำเร็จ |
| 9 | `/api/sci-connect-news` ยังแสดงข่าวปกติ | `200` |

---

## 7. ⚠ ข้อจำกัดในอนาคต — JWT signing keys และ API keys ชุดใหม่

**เรื่องนี้ไม่กระทบวันนี้ แต่กำหนดว่าการออกแบบนี้จะอยู่ได้นานแค่ไหน**

### 7.1 สิ่งที่เอกสารทางการระบุ

| ประเด็น | ผลต่อ patch นี้ |
|---|---|
| `verify_jwt` ปัจจุบันรับทั้ง JWT แบบ HS256 เดิม **และ** JWT ที่ลงนามด้วย asymmetric signing keys | **วันนี้ใช้ได้ทั้งสองแบบ** |
| เอกสารเตือนว่าถ้าใช้ Edge Function ที่เปิด `verify_jwt` อยู่ แล้วทำ **rotation** ของ signing key **อาจทำให้แอปพัง** และแนะนำให้ปิดการตั้งค่านี้ | **ถ้าวันหนึ่งย้ายไป signing keys แล้ว rotate ต้องปิด `verify_jwt`** |
| เมื่อ **revoke** legacy secret แล้ว `anon` และ `service_role` **จะถูกปฏิเสธ** | **cron ที่ส่ง anon key ใน `Authorization` จะได้ `401`** |
| API keys ชุดใหม่ (publishable/secret) **ไม่ใช่ JWT** — ถ้าส่งใน `Authorization: Bearer` แพลตฟอร์มจะพยายาม parse เป็น JWT แล้วปฏิเสธด้วย `Invalid JWT` · ต้องส่งที่ `apikey` เท่านั้น | **การส่ง anon key ใน `Authorization` ของ cron จะใช้ไม่ได้** |

### 7.2 ความหมายสำหรับการออกแบบนี้

> **ด่านความปลอดภัยของฟังก์ชันไม่ได้พึ่ง `verify_jwt` เลย** — การตรวจ `x-cron-secret` และการตรวจ `role`/`status` อยู่ในโค้ดของฟังก์ชันทั้งหมด

ดังนั้น **เปลี่ยน `verify_jwt` เป็น `false` ภายหลังได้โดยไม่ต้องแก้โค้ดฟังก์ชัน** · สิ่งที่ต้องแก้ตอนนั้นคือ cron เท่านั้น (เอา `Authorization` ออก เหลือ `apikey` และ `x-cron-secret`)

### 7.3 สัญญาณที่บอกว่าถึงเวลาต้องเปลี่ยน

| สัญญาณ | ทำอะไร |
|---|---|
| เริ่มใช้ JWT signing keys และจะ rotate | ปิด `verify_jwt` **ก่อน** rotate · แก้ cron ให้เอา `Authorization` ออก |
| จะ revoke legacy JWT secret | เหมือนข้างบน · **บังคับ** ไม่ใช่ทางเลือก |
| ย้ายไป publishable/secret API keys | เหมือนข้างบน |
| `pg_net` ขึ้น `401` ทั้งที่ secret ถูก | **ตรวจว่ามีการ rotate หรือ revoke ไปหรือยัง** |

### 7.4 ทางเลือกถ้าต้องการให้ทนอนาคตตั้งแต่ตอนนี้

| ทาง | ทำอะไร | ข้อแลก |
|---|---|---|
| ก (ที่เลือก) | คง `verify_jwt = true` · cron ส่งทั้ง `Authorization` และ `x-cron-secret` | สองชั้นวันนี้ · ต้องแก้เมื่อ rotate |
| ข | ปิด `verify_jwt` ตั้งแต่ต้น · cron ส่งเฉพาะ `apikey` + `x-cron-secret` | ทนอนาคต · **เหลือด่านเดียวคือโค้ดฟังก์ชัน** |
| ค | ใช้ `withSupabase({ auth: ['user', 'secret:...'] })` ตามแนวทางทางการล่าสุด | ตามมาตรฐาน · ต้องปิด `verify_jwt` และเพิ่ม dependency ใหม่ |

**ยังเสนอทาง ก** เพราะรอบนี้ต้องการเปลี่ยนให้น้อยที่สุดและได้สองชั้นทันที · **แต่ต้องบันทึกข้อ 7.3 ไว้เป็นงานติดตาม**

### 7.5 หมายเหตุเรื่องการตรวจ token ในฟังก์ชัน

โค้ดใช้ `auth.getUser(token)` ซึ่งเรียกไปที่ Auth server ทุกครั้ง · เอกสารล่าสุดแนะนำ `getClaims()` ที่ตรวจในเครื่องได้เมื่อโปรเจกต์ใช้ asymmetric key

**ยังไม่เปลี่ยนในรอบนี้** เพราะ `getUser()` ทำงานได้ทั้งสองแบบและเป็นรูปแบบเดียวกับที่ `webapi/api/_lib/adminAuth.js` ใช้อยู่ · บันทึกไว้เป็นการปรับปรุงภายหลัง

### 7.6 เอกสารอ้างอิง

- [JWT Signing Keys](https://supabase.com/docs/guides/auth/signing-keys)
- [Migrating to publishable and secret API keys](https://supabase.com/docs/guides/getting-started/migrating-to-new-api-keys)
- [Securing Edge Functions](https://supabase.com/docs/guides/functions/auth)
- [Function Configuration](https://supabase.com/docs/guides/functions/function-configuration)
- [Authorization headers](https://supabase.com/docs/guides/functions/auth-headers)

---

## 8. Rollback — สามส่วนแยกกัน

> **แผนเต็มอยู่ใน `DEPLOY_PLAN.md`** — ข้อนี้เป็นสรุป

### 8.1 สามส่วนที่ย้อนแยกกันได้

| ส่วน | ย้อนด้วย | ย้อนแยกได้ไหม |
|---|---|---|
| **A** Edge Function | deploy ไฟล์สำรองที่ผู้ดำเนินการเก็บไว้ · **เปิดไฟล์ตรวจก่อน** | ได้ |
| **B** cron | `scripts/02_rollback_cron.sql` | ได้ |
| **C** webapi | `docker tag course-advisor-system-webapi:c2-before-update course-advisor-system-webapi:latest` แล้ว `up -d --no-deps --no-build --force-recreate webapi` | ได้ |

> **ขั้นตอนเต็มของส่วน C อยู่ใน `DEPLOY_PLAN.md` ข้อ 4.4.1**
> ต้นทางคือ **`course-advisor-system-webapi:c2-before-update`** · ปลายทางคือ **`:latest`** ซึ่งเป็นฉบับที่ใช้งานอยู่
> ทุกคำสั่ง compose ต้องส่ง **`-p course-advisor-system`** และ **`-f` ทั้งสี่ไฟล์** (prod · staging · pin-backend · pin-frontend)
> **ขั้น 3 เทียบ image ID เป็นด่านบังคับ** — ถ้า `:c2-before-update` ชี้ไปที่ฉบับใหม่ คำสั่งย้อนจะขึ้นสำเร็จแต่ได้โค้ดใหม่กลับมา

### 8.2 ลำดับเมื่อต้องย้อนหลายส่วน

```
1. C  webapi          ย้อนก่อน  (กลับไปส่ง anon key)
2. A  Edge Function   ย้อนถัดมา (กลับไปรับ anon key)
3. B  cron            ย้อนท้ายสุด   scripts/02_rollback_cron.sql
```

> **ห้ามย้อน A โดยไม่ย้อน B** — จะได้ job ที่ส่ง `x-cron-secret` ไปหาฟังก์ชันที่ไม่รู้จัก header นั้น
> ฟังก์ชันเดิมจะ **ไม่ล้ม** แต่ก็ **ไม่มีด่านเหลืออยู่** คือกลับไปมีช่องโหว่เดิมโดยที่ทุกอย่างดูปกติ

### 8.3 การทดสอบ rollback ก็แยกสามส่วน

| ส่วน | ทดสอบที่ไหน | ใช้ไฟล์ไหน |
|---|---|---|
| **B** cron | **โปรเจกต์ทดสอบ** | `scripts/03_test_rollback_on_test_project.sql` |
| **A** Edge Function | **โปรเจกต์ทดสอบ** — deploy ฉบับเดิมทับแล้วยิง anon key ต้องได้ `200` กลับมา | — |
| **C** webapi | เครื่องพัฒนา — วิธีเดียวกับ M3 ซึ่งเคยใช้จริงแล้ว | คู่มือ M3 |

> **`02_rollback_cron.sql` รันบนโปรเจกต์ทดสอบไม่ได้** เพราะหา job `sync-sci-news-every-30-min` ไม่เจอแล้วจะล้มทันที
> **นั่นคือพฤติกรรมที่ถูกต้อง** และตอนนี้ไฟล์จะขึ้นข้อความชี้ให้ไปใช้ `03_test_rollback_on_test_project.sql` แทน

### 8.4 ถ้า `01_update_cron.sql` ล้มกลางคัน

ต้องยืนยันว่า transaction ย้อนสถานะ job ให้จริง

```sql
select jobid, jobname, active
from cron.job
where jobname like '%sync-sci-news%'
order by jobname;
```

| สิ่งที่เห็น | แปลว่า |
|---|---|
| job เดิม `active = true` · ไม่มี job ใหม่ | ย้อนครบ — แก้สาเหตุแล้วลองใหม่ |
| job เดิม `active = false` · ไม่มี job ใหม่ | **‼ ย้อนไม่ครบ — ข่าวหยุดอัปเดต** ต้องเปิดกลับทันที (`DEPLOY_PLAN.md` ข้อ 4.5) |
| เปิดทั้งสอง job | **‼ ยิงซ้ำสองเท่า** ต้องปิดตัวใดตัวหนึ่งทันที |

**คุณสมบัตินี้ผ่านบนโปรเจกต์ทดสอบแล้ว** (`TEST_STATUS.md` ข้อ 6.6) · **แต่ยังไม่เคยรัน `02_rollback_cron.sql` บน production** — ดู `DEPLOY_PLAN.md` ข้อ 5.1

### 8.5 สิ่งที่ไม่ต้องย้อน

| รายการ | เหตุผล |
|---|---|
| secret ที่สร้างไว้ | ถ้าไม่มีใครใช้ก็ไม่มีผล · เก็บไว้ลองใหม่ได้ |
| ตาราง `c2_sync_runs` | ไม่มี secret · `anon`/`authenticated` เข้าไม่ถึง · ช่วยสืบย้อนได้ |
| ข้อมูลใน `external_news` | ไม่ถูกแตะโดยการย้อน |

---

## 9. รายการตรวจทานก่อนอนุมัติ

| # | สิ่งที่ต้องตรวจ | ทำแล้ว |
|---|---|---|
| 1 | โค้ดที่ deploy อยู่ตรงกับไฟล์ฉบับเดิมในรีโปจริงไหม | ☐ |
| 2 | ตรรกะการดึงข่าวในฉบับใหม่ไม่ถูกแก้จากเดิม | ☐ |
| 3 | ชื่อ env ของ Edge Function ตรงกับที่ Supabase ให้ (`SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`) | ☐ |
| 4 | `SYNC_CRON_SECRET` และ Vault `sync_cron_secret` เป็นค่าเดียวกัน | ☐ |
| 5 | รันชุดทดสอบผ่านครบ 14 ข้อ | ☐ |
| 6 | บันทึกนิยาม cron เดิมไว้แล้ว (ในที่ปลอดภัย) | ☐ |
| 7 | บันทึกโค้ด Edge Function เดิมไว้แล้ว | ☐ |
| 8 | เข้าใจช่วงที่ cron จะล้มชั่วคราวระหว่างขั้น 4-5 | ☐ |
| 9 | ยืนยันว่า `vault.decrypted_secrets` มีครบ 3 ชื่อ | ☐ |

### ข้อที่เคยบล็อกการ deploy — สถานะหลัง deploy

| # | สิ่งที่ต้องทำ | ผล |
|---|---|---|
| B1 | ทดสอบว่า **transaction rollback คืนสถานะ job** ได้จริง | **✅ ผ่านบนโปรเจกต์ทดสอบ** — `TEST_STATUS.md` ข้อ 6.6 |
| B2 | ยืนยันว่า Edge Function ที่ deploy บน production ตรงกับ source ในเครื่อง | **ยังเทียบไม่ได้** — ไม่มีบันทึกผลการเทียบก่อน deploy · มีไฟล์สำรองตามที่ผู้ดำเนินการยืนยัน แต่ **ยังไม่ได้ตรวจ** |
| B3 | เทียบเวอร์ชัน `pg_cron` และ `pg_net` ของสองโปรเจกต์ | **✅ ทำแล้ว ตรงกันทั้งคู่** — `pg_cron` **1.6.4** · `pg_net` **0.20.4** |
| B4 | บันทึกนิยาม job เดิมและโค้ด Edge Function เดิม | **job เดิมถูกปิดไม่ได้ลบ จึงยังมีนิยามอยู่** · โค้ด Edge Function เดิม **ผู้ดำเนินการยืนยันว่าเก็บไว้แล้ว แต่ยังไม่ได้ตรวจไฟล์** |

> **รายการที่ยังไม่ได้ทดสอบอยู่ใน `DEPLOY_PLAN.md` ข้อ 5**

---

## 10. คำถามเปิด — สถานะหลัง deploy

| # | คำถาม | สถานะ |
|---|---|---|
| 1 | โค้ดที่ deploy อยู่เดิมตรงกับ source ในเครื่องไหม | **ยังเปิดอยู่** — ต้องเปิดตรวจไฟล์สำรองก่อนจึงเทียบได้ |
| 2 | `pg_cron` ส่ง header เพิ่มได้จริงในสภาพแวดล้อมนี้ไหม | **ตอบแล้ว** — P5 ยืนยันว่าได้ |
| 3 | มีใครหรือระบบอื่นเรียก Edge Function นี้อยู่อีกไหม | **ยังเปิดอยู่** — ถ้ามีจะได้ `401` เงียบ ๆ ควรดู Edge Function logs |
| 4 | ชื่อ Vault secret `project_url` และ `anon_key` ตรงกับที่ใช้จริงไหม | **ตอบแล้ว** — ชื่อถูก แต่ **ค่าผิดทั้งสองตัว** (D1, D2) ดู `DEPLOY_PLAN.md` ข้อ 2 |
| 5 | เวอร์ชัน `pg_cron`/`pg_net` ของสองโปรเจกต์ตรงกันไหม | **ตอบแล้ว** — ตรงกัน `1.6.4` และ `0.20.4` |

> **ข้อ 1 และ 3 ยังเปิดอยู่** — ข้อ 1 ต้องเปิดตรวจไฟล์สำรองก่อน · ข้อ 3 ต้องดู Edge Function logs

---

## 11. ไฟล์ในโฟลเดอร์นี้

```
README.md                                     เอกสารนี้
DEPLOY_PLAN.md                                แผน deploy/rollback + ขั้นที่ยังขาดก่อน production
TEST_STATUS.md                                สถานะการทดสอบ — อะไรรันแล้ว อะไรยังไม่รัน
GATEWAY_TEST_PLAN.md                          แผนทดสอบ gateway บนโปรเจกต์ c1-migration-test
edge-function/index.ts                        Edge Function ฉบับเสนอแก้
webapi/adminAuth.js                           เพิ่ม token ในค่าที่คืน
webapi/sync-sci-news.js                       ส่ง user token แทน anon key
tests/sync-sci-news.auth.test.ts              ชุดทดสอบ Edge Function 14 ข้อ (Deno)
tests/webapi-sync-sci-news.test.mjs           ชุดทดสอบ webapi 12 ข้อ (Node)
scripts/01_update_cron.sql                    เปลี่ยน cron บน production (ไม่เปิดเผย secret)
scripts/02_rollback_cron.sql                  ย้อน cron บน production
scripts/03_test_rollback_on_test_project.sql  ทดสอบ rollback บนโปรเจกต์ทดสอบ (ห้ามรันบน production)
```

### ไฟล์ SQL สามไฟล์ใช้ต่างที่กัน

| ไฟล์ | รันที่ไหน | มีการ์ดกันรันผิดที่ไหม |
|---|---|---|
| `01_update_cron.sql` | **production เท่านั้น** | มี — ล้มถ้าไม่พบ job เดิม และชี้ไปไฟล์ 03 |
| `02_rollback_cron.sql` | **production เท่านั้น** | มี — ล้มถ้าไม่พบ job เดิม และชี้ไปไฟล์ 03 |
| `03_test_rollback_on_test_project.sql` | **โปรเจกต์ทดสอบเท่านั้น** | มี — ล้มทันทีถ้าพบ job ของ production |

### ไฟล์เหล่านี้ถูกนำไปใช้จริงแล้ว

| ไฟล์ในโฟลเดอร์นี้ | ปลายทาง | สถานะ |
|---|---|---|
| `edge-function/index.ts` | Edge Function `sync-sci-news` บน production | **deploy แล้ว** (P1) |
| `webapi/adminAuth.js` | `webapi/api/_lib/adminAuth.js` | **ใช้แล้ว** (P6) |
| `webapi/sync-sci-news.js` | `webapi/api/admin/sync-sci-news.js` | **ใช้แล้ว** (P6) |
| `scripts/01_update_cron.sql` | cron บน production | **รันแล้ว** (P3, P4) |

> สำเนาในโฟลเดอร์นี้เป็น **บันทึกของสิ่งที่นำไปใช้** · ของสำรองสำหรับย้อนกลับอยู่ใน `DEPLOY_PLAN.md` ข้อ 3
> **`edge-function/index.ts` อยู่คนละรีโป** — การแก้ครั้งต่อไปต้องประสานกับทีมออกแบบ
