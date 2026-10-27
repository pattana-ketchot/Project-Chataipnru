# สถานะการทดสอบ C2

**ปรับปรุง 11 ตุลาคม 2569** · **C2 deploy บน production แล้วและยืนยันผลแล้ว**

> เอกสารนี้รายงาน **คำสั่งที่รันจริงและผลลัพธ์จริง** · ไม่มีการอ้างผลผ่านจากการตรวจแบบคงที่
>
> **ผลบน production อยู่ในข้อ 0** · แยกจากผลบนโปรเจกต์ทดสอบซึ่งอยู่ในข้อ 5 และ 6 โดยสิ้นเชิง
> **บันทึก deploy และแผน rollback อยู่ใน `DEPLOY_PLAN.md`**
> **ไม่บันทึกค่าคีย์ ค่า secret หรือ URL ของ Vault**

---

## สรุป

| ชุด | ผล |
|---|---|
| `deno check` (2 ไฟล์) | **exit 0 ทั้งคู่** |
| `deno test` — Edge Function | **`ok \| 14 passed \| 0 failed (53ms)`** |
| `node --test` — webapi patch | **`tests 12 \| pass 12 \| fail 0`** |
| `node --test` — ชุดเดิมของ webapi | **`tests 82 \| pass 82 \| fail 0`** (ยืนยันว่า patch ไม่ทำของเดิมพัง) |
| **Gateway G1–G8** บนโปรเจกต์ทดสอบ | **ผ่านครบ 8 ข้อ** — ดูข้อ 5 |
| **pg_net แบบเรียกครั้งเดียว** บนโปรเจกต์ทดสอบ | **ผ่าน** — ดูข้อ 6.2 ข้อ ข |
| **cron scheduler ด้วย timeout 30000 ms** บนโปรเจกต์ทดสอบ | **ผ่าน 3 รอบ** — ดูข้อ 6.2 ข้อ ค |
| **transaction rollback คืนสถานะ job** บนโปรเจกต์ทดสอบ | **ผ่าน** — ดูข้อ 6.6 |

### ผลบน production

| ชุด | ผล |
|---|---|
| **anon POST ไม่มี `x-cron-secret`** | **`401` `{"error":"unauthorized"}`** ← ข้อชี้ขาด · ดูข้อ 0 |
| **cron v2 ผ่าน scheduler** | **`200` 3 รอบ** (`request_id` 1765–1767) · ดูข้อ 0 |
| **admin กด Force Update ผ่านเว็บจริง** | **สำเร็จ** · ดูข้อ 0 |
| **`node --test` ด้วย `api/` ที่ใส่ patch แล้ว** | **82 ผ่าน** · ดูข้อ 0 |
| `rollback cron` บน production | **`NOT RUN`** — ดูข้อ 0.5 |
| บัญชี `editor` จริง | **`NOT RUN`** ทั้งสองโปรเจกต์ — ดูข้อ 0.5 |
| `verify_jwt = false` (V1–V6) | **`NOT RUN`** |
| สถานะ JWT signing keys (S1–S3) | **`NOT RUN`** |

## 0. ผลบน production — deploy แล้ว

> **ทุกบรรทัดในข้อนี้มาจาก production** · ผลบนโปรเจกต์ทดสอบอยู่ในข้อ 5 และ 6 **อย่าปนกัน**

### 0.1 สิ่งที่ยืนยันแล้ว

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

### 0.2 P2 คือข้อชี้ขาด

รายงาน F1 ระบุว่า "ใครก็ยิง `sync-sci-news` ได้ด้วย anon key" · **P2 ยืนยันบน production ว่าปิดแล้วจริง** จากการยิงของจริง ไม่ใช่จาก unit test และไม่ใช่จากโปรเจกต์ทดสอบ

### 0.3 P5 ยืนยันมากกว่าที่ `job_run_details` บอกได้

`request_id` 1765–1767 มาจาก `net._http_response` ซึ่งเป็น **ผลตอบกลับ HTTP จริง** · ต่างจาก `cron.job_run_details` ที่ขึ้น `succeeded` แม้ปลายทางจะคืน `401` หรือ `500` (เหตุผลอยู่ใน `README.md` ข้อ 6.2)

> **`request_id` 1765–1767 เป็นลำดับของ production** · `request_id` 8–10 เป็นของโปรเจกต์ทดสอบ · **เป็นคนละชุดกัน**

### 0.4 ปัญหาที่พบและแก้ระหว่าง deploy

| # | ปัญหา | ผลที่เกิด | แก้แล้วอย่างไร |
|---|---|---|---|
| **D1** | `project_url` ใน Vault เป็น **placeholder / ข้อความ Markdown** ไม่ใช่ URL | URL ที่ job ประกอบขึ้นไม่ใช่ที่อยู่จริงของฟังก์ชัน | แก้ค่าให้เป็น URL จริง |
| **D2** | `anon_key` ใน Vault **มีรูปแบบ JWT ไม่ถูกต้อง** | gateway ปฏิเสธที่ชั้นแรก คำขอไม่เคยถึงโค้ดฟังก์ชัน | แก้ค่าให้เป็น JWT ที่ถูกรูป |

ทั้งสองข้อ **แก้แล้ว** · P5 คือหลักฐานว่าทางของ cron ใช้งานได้จริงหลังแก้

**ทำไมขั้นตรวจก่อนลงมือไม่จับสองข้อนี้** — `01_update_cron.sql` ขั้น 0.2 ตรวจเพียงว่า secret **มีอยู่และอ่านได้** ไม่ได้ตรวจ **รูปร่าง** ของค่า จึงปล่อยทั้ง placeholder และ JWT ผิดรูปผ่านไปได้ · รายละเอียดและข้อเสนอแก้อยู่ใน `DEPLOY_PLAN.md` ข้อ 2.1

### 0.5 ยังไม่ได้ทดสอบบน production

| # | ยังไม่ได้ทำ | เคยผ่านที่ไหน |
|---|---|---|
| **1** | **`02_rollback_cron.sql` บน production** | **ไม่เคย** — transaction rollback ผ่านบนโปรเจกต์ทดสอบ (ข้อ 6.6) แต่ไม่ใช่สคริปต์นี้ |
| 2 | `x-cron-secret` **ผิด** → `401` | โปรเจกต์ทดสอบ G5 |
| 3 | `GET` → `405` | โปรเจกต์ทดสอบ G4 |
| 4 | `role = user` → `403` | โปรเจกต์ทดสอบ G8 |
| 5 | **บัญชี `editor` จริง** | **ไม่เคยที่ไหนเลย** — มีแต่ unit test ที่จำลองคำตอบฐานข้อมูล |
| 6 | `verify_jwt = false` | ไม่เคย |
| 7 | สถานะ JWT signing keys | ไม่เคยบันทึก |
| 8 | มีระบบอื่นเรียก Edge Function นี้อยู่อีกไหม | ไม่เคยตรวจ — **ถ้ามีจะได้ `401` เงียบ ๆ** |
| 9 | **เปิดตรวจไฟล์สำรองโค้ด Edge Function เดิม** | **ผู้ดำเนินการยืนยันว่าเก็บไว้ก่อน deploy แล้ว · ยังไม่ได้ตรวจไฟล์** |
| 10 | เทียบ `pg_cron`/`pg_net` ของสองโปรเจกต์ | **✅ ทำแล้ว ตรงกัน** — `pg_cron` 1.6.4 · `pg_net` 0.20.4 |
| 11 | **ย้อน webapi จาก `course-advisor-system-webapi:c2-before-update`** | **ยังไม่ทดสอบ** · ขั้นตอนอยู่ใน `DEPLOY_PLAN.md` ข้อ 4.4.1 — **ยังไม่ได้ตรวจ image ID ของ tag นี้** |

> **ข้อ 5** โค้ดตรวจ `role in ('admin','editor')` · P8 ทดสอบด้วยบัญชี admin จึงยืนยันได้เฉพาะค่า `admin`

---

## 1. Runtime และ dependency

### 1.1 Deno

ติดตั้งแบบ portable จาก GitHub release ทางการของ `denoland` ลงในโฟลเดอร์ชั่วคราวของงานนี้ **ไม่ได้ติดตั้งลงระบบและไม่ได้แก้ `PATH`**

```
deno 2.9.7 (stable, release, x86_64-pc-windows-msvc)
v8 15.0.245.2-rusty
typescript 6.0.3
```

| รายการ | ค่า |
|---|---|
| แหล่ง | `https://github.com/denoland/deno/releases/latest/download/deno-x86_64-pc-windows-msvc.zip` |
| ขนาดที่ดาวน์โหลด | 42,630,221 ไบต์ (HTTP 200) |
| ที่อยู่ | โฟลเดอร์ scratchpad ของ session · โฟลเดอร์ว่างเปล่าเฉพาะของมันเอง |
| `DENO_DIR` | ตั้งไปที่ `scratchpad/deno-portable/cache` **ไม่เขียนลง `~/.deno`** |

### 1.2 Dependency ที่ resolve จริง

| แพ็กเกจ | เวอร์ชันที่ได้ |
|---|---|
| `@supabase/supabase-js` | **2.117.3** (จาก `esm.sh/@supabase/supabase-js@2`) |
| `@supabase/auth-js` | 2.117.3 |
| `@supabase/postgrest-js` | 2.117.3 |
| `@supabase/functions-js` | 2.117.3 |
| `@supabase/realtime-js` | 2.117.3 |
| `@supabase/storage-js` | 2.117.3 |
| `deno.land/std/assert` | **0.224.0** (ตรึงไว้ในไฟล์เทสต์) |

> **ข้อควรระวัง** — `supabase-js@2` เป็น specifier แบบลอย เวอร์ชันที่ได้อาจเปลี่ยนในอนาคต · ถ้าต้องการผลที่ทำซ้ำได้แน่นอน ควรตรึงเป็น `@2.117.3`

---

## 2. คำสั่งที่รันและผลจริง

### 2.1 `deno check` — รอบแรก **ล้ม 3 ข้อ**

```bash
deno check edge-function/index.ts
```

```
Check edge-function/index.ts
TS2345 [ERROR]: Argument of type 'string | null' is not assignable to parameter of type 'string'.
  const newItems = parsed.filter((item) => !existingUrls.has(item.detail_url))
    at .../edge-function/index.ts:238:62

TS2345 [ERROR]: Argument of type '{ title: string; ... }[]' is not assignable to parameter of type 'never[]'.
      .insert(rows, { count: 'exact' })
    at .../edge-function/index.ts:263:15

TS2345 [ERROR]: Argument of type 'SupabaseClient<any, "public", "public", any, any>' is not assignable to
  parameter of type 'SupabaseClient<unknown, { PostgrestVersion: string; }, never, never, ...>'.
    const result = await runSync(supabase)
    at .../edge-function/index.ts:338:34

Found 3 errors.
error: Type checking failed.
```

**สาเหตุ — มาจากการแก้ของผมเอง ไม่ใช่ของเดิม**

ตอนแยก `runSync` ออกมาเป็นฟังก์ชัน ผมใส่ชนิดของพารามิเตอร์เป็น `ReturnType<typeof createClient>` ซึ่งไม่ตรงกับชนิดที่ `createClient(url, key)` คืนจริง และการแยกออกมาทำให้ TypeScript ตรวจขอบเขตที่เดิมไม่เคยถูกตรวจ

> **ไฟล์ต้นฉบับของทีมออกแบบไม่เคยถูก `deno check`** — ถ้ารันกับของเดิมก็จะเจอข้อ 1 เหมือนกัน

### 2.2 การแก้ 4 จุด

| # | แก้อะไร | เหตุผล |
|---|---|---|
| 1 | `import { createClient, type SupabaseClient }` | ใช้ชนิดจริงแทนการเดาจาก `ReturnType` |
| 2 | เปลี่ยน `.filter((item) => item.detail_url)` เป็น **type guard** `(item): item is typeof item & { detail_url: string }` | ให้ TypeScript รู้ว่าหลังกรองแล้ว `detail_url` ไม่เป็น `null` |
| 3 | `runSync(supabase: SupabaseClient<any, any, any>)` | โปรเจกต์นี้ไม่มี generated types ของ schema |
| 4 | `extractSlug(item.detail_url)` เอา `!` ออก | ไม่ต้องใช้แล้วเพราะมี type guard |

**ไม่มีการเปลี่ยนพฤติกรรมตอนรัน** — ทั้งสี่เป็นเรื่องชนิดข้อมูลล้วน ๆ

### 2.3 `deno check` — รอบสอง **ผ่าน**

```bash
deno check edge-function/index.ts            # exit 0
deno check tests/sync-sci-news.auth.test.ts  # exit 0
```

### 2.4 `deno test` — รอบแรก **10 ผ่าน 4 ล้ม**

```bash
deno test --allow-env --allow-net=esm.sh,deno.land tests/sync-sci-news.auth.test.ts
```

```
FAILED | 10 passed | 4 failed (56ms)
```

| ข้อที่ล้ม | อาการ | สาเหตุจริง |
|---|---|---|
| `cron secret ผิด -> 401` | โยนที่ `new Request` | **ใส่ค่าภาษาไทย `'ผิด'` เป็น header value** — HTTP header ต้องเป็น ASCII |
| `ส่ง cron secret มาแต่ยังไม่ตั้งค่า -> 503` | โยนที่ `new Request` | ใส่ `'อะไรก็ได้'` เป็น header value |
| `admin + approved -> sync ทำงาน` | ได้ `403` แทน `200` | **ตัวจำลองคืน array ให้ `.single()`** |
| `editor + approved -> sync ทำงาน` | ได้ `403` แทน `200` | เหตุผลเดียวกัน |

> **ทั้งสี่เป็นข้อบกพร่องของชุดทดสอบ ไม่ใช่ของโค้ดที่ทดสอบ** — แต่ก็มีประโยชน์ เพราะเปิดเผยว่าตัวจำลองของผมไม่ตรงกับ PostgREST จริง

### 2.5 การแก้ชุดทดสอบ 2 จุด

| # | แก้อะไร | เหตุผล |
|---|---|---|
| 1 | เปลี่ยนค่า header เป็น ASCII (`'wrong-secret-value'`, `'any-value'`) | HTTP header value ต้องเป็น ASCII |
| 2 | ตัวจำลอง `user_profiles` คืน **object เดี่ยว** เมื่อพบแถว และคืน **`406` พร้อม `PGRST116`** เมื่อไม่พบ | `.single()` ตั้ง `Accept: application/vnd.pgrst.object+json` · PostgREST จริงคืน object ไม่ใช่ array และคืน 406 เมื่อไม่มีแถว |

> **ข้อ 2 ทำให้ตัวจำลองตรงกับของจริงมากขึ้น** ซึ่งลดความเสี่ยงที่เทสต์จะผ่านทั้งที่ของจริงไม่ทำงาน

### 2.6 `deno test` — รอบสอง **ผ่านครบ**

```
running 14 tests from ./tests/sync-sci-news.auth.test.ts
OPTIONS ผ่านได้โดยไม่ต้องมีสิทธิ์ และไม่แตะเว็บต้นทาง ... ok (7ms)
GET ถูกปฏิเสธด้วย 405 — ฉบับเดิมรับ GET แล้ว sync เลย ... ok (438µs)
cron secret ถูกต้อง -> sync ทำงาน ... ok (8ms)
cron secret ผิด -> 401 และไม่ยิงเว็บต้นทาง ... ok (425µs)
ส่ง cron secret มาแต่ฟังก์ชันยังไม่ตั้งค่า -> 503 ไม่ใช่ปล่อยผ่าน ... ok (313µs)
‼ anon key เป็น bearer -> 401 (นี่คือช่องที่ปิด) ... ok (1ms)
ไม่ส่งอะไรมาเลย -> 401 ... ok (282µs)
token ใช้ได้แต่ role = user -> 403 ... ok (1ms)
admin แต่ status ยังไม่ approved -> 403 ... ok (1ms)
ไม่มีแถวใน user_profiles -> 403 (ไม่เดาว่ามีสิทธิ์) ... ok (1ms)
admin + approved -> sync ทำงาน ... ok (1ms)
editor + approved -> sync ทำงาน ... ok (1ms)
ข่าวที่มีอยู่แล้วไม่ถูกเพิ่มซ้ำ ... ok (1ms)
เว็บต้นทางล้ม -> 502 และไม่แตะฐานข้อมูล ... ok (664µs)

ok | 14 passed | 0 failed (39ms)
```

---

## 3. ยืนยันว่าตรรกะเดิมยังไม่ถูกแก้

เทียบแต่ละฟังก์ชันกับต้นฉบับ **หลังการแก้ type ทั้งสี่จุดแล้ว**

| ฟังก์ชัน | ผล |
|---|---|
| `decodeEntities` · `cleanText` · `parseNewsCards` | **เหมือนเดิมทุกไบต์** |
| `parseThaiDate` · `extractSlug` | **เหมือนเดิมทุกไบต์** |
| `parseDetailPage` · `fetchDetail` | **เหมือนเดิมทุกไบต์** |

การแก้ทั้งสี่จุดอยู่ใน `runSync` และบรรทัด `import` เท่านั้น **ไม่แตะฟังก์ชันแปลง HTML เลย**

---

## 4. ชุดทดสอบ webapi — `node --test` **12 ผ่าน 0 ล้ม**

### 4.1 คำสั่ง

```bash
node --test tests/webapi-sync-sci-news.test.mjs
```

รันในโฟลเดอร์ชั่วคราวที่จัดโครงให้ `../_lib/adminAuth.js` resolve ได้ และมี junction ไปยัง `webapi/node_modules` เพื่อให้ `@supabase/supabase-js` (2.117.0) resolve ได้ **ไม่ได้แก้โฟลเดอร์ `webapi/` จริง**

### 4.2 ผล

```
✔ requireAdminUser คืน token ของผู้เรียกกลับมาด้วย (74.1ms)
✔ requireAdminUser ไม่คืน token เมื่อไม่ผ่านด่าน (1.9ms)
✔ ‼ ส่ง Authorization เป็น token ของผู้ใช้ ไม่ใช่ anon key (2.2ms)
✔ apikey ยังเป็น anon key เหมือนเดิม (2.0ms)
✔ ส่ง method POST และ body ว่างไปยัง Edge Function (1.7ms)
✔ GET -> 405 และไม่เรียก Edge Function (0.3ms)
✔ ไม่มี token -> 401 และไม่เรียก Edge Function (0.2ms)
✔ role = user -> 403 และไม่เรียก Edge Function (1.0ms)
✔ status ไม่ approved -> 403 (1.2ms)
✔ ไม่มีแถวใน user_profiles -> 403 (2.0ms)
✔ Edge Function คืน 401 -> webapi คืน 502 และไม่รั่ว token ลง log (2.8ms)
✔ ผลลัพธ์ที่ส่งกลับผู้เรียกไม่มี token หรือ anon key (1.6ms)

tests 12 | pass 12 | fail 0
```

### 4.3 ข้อที่สำคัญที่สุด

| ข้อ | พิสูจน์อะไร |
|---|---|
| `ส่ง Authorization เป็น token ของผู้ใช้ ไม่ใช่ anon key` | **หัวใจของ patch ฝั่ง webapi** — ตรวจ header ที่ส่งไป Edge Function จริง ไม่ใช่แค่ว่าโค้ดคืน 200 |
| `apikey ยังเป็น anon key เหมือนเดิม` | gateway ยังระบุโปรเจกต์ได้ |
| `Edge Function คืน 401 -> 502 และไม่รั่ว token ลง log` | ดัก `console.error` แล้วยืนยันว่าไม่มี token หรือ anon key อยู่ในข้อความ |
| ทุกเส้นทางปฏิเสธ | ยืนยันว่า **ไม่เรียก Edge Function เลย** เมื่อด่านไม่ผ่าน |

### 4.4 ชุดทดสอบเดิมของ webapi ยังผ่าน

```
cd webapi && node --test
tests 82 | pass 82 | fail 0
```

ยืนยันว่าการเพิ่มฟิลด์ `token` ใน `requireAdminUser` **ไม่กระทบผู้เรียกเดิม** (`extract-file`, `ingest`)

---

## 5. ผลทดสอบ Gateway บนโปรเจกต์ทดสอบ — **ผ่านครบ 8 ข้อ**

| ขั้น | ส่งอะไร | ต้องได้ | ได้จริง | ผ่าน |
|---|---|---|---|---|
| G1 | ไม่มี credential | `401` | **`401`** | ✅ |
| G2 | bearer มั่ว | `401` | **`401`** | ✅ |
| **G3** | **anon key เป็น bearer** | **`401`** | **`401`** | ✅ |
| G4 | `GET` | `405` | **`405`** | ✅ |
| G5 | cron secret ผิด | `401` | **`401`** | ✅ |
| G6 | cron secret ถูก | `200` | **`200`** | ✅ |
| G7 | admin token | `200` | **`200`** | ✅ |
| G8 | user token | `403` | **`403`** | ✅ |

> **G3 คือข้อชี้ขาด** — ก่อนแก้ได้ `200` และ sync ทำงาน · หลังแก้ได้ `401`
> **ช่องที่รายงาน F1 ระบุไว้ถูกปิดแล้วจริง ยืนยันจากการยิงของจริง ไม่ใช่จาก unit test**

---

## 6. ผลทดสอบ cron — ต้องแยกสองเรื่องให้ชัด

### 6.1 ⚠ สองผลนี้คนละเรื่องกัน อย่าปนกัน

| | ผ่าน scheduler | เรียกด้วยมือครั้งเดียว |
|---|---|---|
| ใครเป็นผู้เรียก | `pg_cron` ตามตาราง | คนรันคำสั่ง SQL เอง |
| ยืนยันอะไรได้ | **ทั้งเส้นทางตั้งแต่ scheduler ถึงปลายทาง** | **เฉพาะว่า `net.http_post` ด้วยค่านั้นทำงานได้** |

### 6.2 ✅ ผลการทดสอบ patch — ทั้งหมดอยู่บน **โปรเจกต์ทดสอบ `c1-migration-test`**

> ข้อนี้คือผล **ก่อน** deploy ซึ่งใช้ตัดสินใจว่าจะ deploy ไหม · **ผลบน production อยู่ในข้อ 0** อย่าปนกัน

**ก. scheduler เดิมของ production (timeout 5000 ms) — สภาพก่อน deploy**

| รายการ | ค่า |
|---|---|
| โปรเจกต์ | **production** |
| ผ่าน scheduler | ใช่ |
| `timeout_milliseconds` | **5000** (ค่าเดิม) |
| ผลที่เคยได้ | HTTP 200 |

> นี่คือสภาพของ production **ก่อน** deploy C2 **ไม่ใช่ผลการทดสอบ patch**
> **ตอนนี้ job นี้ถูกปิดแล้ว** และ job v2 ทำงานแทน — ดูข้อ 0.1 P3 และ P4

**ข. เรียก `net.http_post` ด้วยมือครั้งเดียว (timeout 30000 ms)**

| รายการ | ค่า |
|---|---|
| โปรเจกต์ | **ทดสอบ** |
| ผ่าน scheduler | **ไม่** — เรียกด้วยมือ |
| `request_id` | 7 |
| `status_code` | 200 · `timed_out` = false · `error_msg` = null |

**ค. ⭐ ผ่าน scheduler จริง (timeout 30000 ms + บันทึก `request_id`)**

| รายการ | ค่า |
|---|---|
| โปรเจกต์ | **ทดสอบ `c1-migration-test`** |
| job | `c2-sync-sci-news-test` |
| ผ่าน scheduler | **ใช่** |
| `timeout_milliseconds` | **30000** |
| จำนวนรอบที่สำเร็จ | **3 รอบ** |

| `request_id` | `status_code` | `timed_out` | `error_msg` |
|---|---|---|---|
| **8** | **200** | false | null |
| **9** | **200** | false | null |
| **10** | **200** | false | null |

**สิ่งที่ผลนี้ยืนยัน**

| # | ยืนยันอะไร |
|---|---|
| 1 | `timeout_milliseconds = 30000` ใช้ได้ผ่าน `pg_cron` scheduler จริง |
| 2 | การ `insert into c2_sync_runs(request_id) select net.http_post(...)` ทำงานได้ |
| 3 | การ join `c2_sync_runs` กับ `net._http_response` ด้วย `request_id` ได้ผลถูกต้อง |
| 4 | Edge Function ฉบับใหม่รับคำขอจาก cron ที่ส่ง `x-cron-secret` ได้ |
| 5 | ทำซ้ำได้ ไม่ใช่ฟลุก — 3 รอบติดต่อกัน |

**ง. สถานะ job ทดสอบตอนนี้**

| รายการ | ค่า |
|---|---|
| ชื่อ | `c2-sync-sci-news-test` |
| `active` | **false** — ปิดแล้ว ไม่ยิงเว็บต้นทางอีก |

### 6.3 ขอบเขตของผลข้อ ค — และสิ่งที่ production ยืนยันเพิ่มภายหลัง

ตอนเขียนข้อ ค ยังไม่มีผลจาก production เลย · ตอนนี้ **มีแล้ว (ข้อ 0.1 P5)** จึงเทียบได้

| ประเด็นที่เคยต่างกัน | สถานะตอนนี้ |
|---|---|
| ชื่อ job | production ใช้ `sync-sci-news-every-30-min-v2` · ทดสอบใช้ `c2-sync-sci-news-test` |
| job เดิมที่ต้องปิด | production **มีและปิดสำเร็จแล้ว** (P3) · ทดสอบไม่มี |
| ปริมาณข่าวในตาราง | ต่างกัน — **แต่ production จบใน 30000 ms ได้จริง 3 รอบ** (P5) |
| เวอร์ชัน `pg_net` และ `pg_cron` | **✅ เทียบแล้ว ตรงกันทั้งคู่** — `pg_cron` **1.6.4** · `pg_net` **0.20.4** ทั้งสองโปรเจกต์ |
| ภาระของเว็บต้นทาง | job ทดสอบปิดแล้ว (ข้อ ง) จึงเหลือ production ยิงเพียงทางเดียว |

> **ผลข้อ ค ยังเป็นผลของโปรเจกต์ทดสอบ** · สิ่งที่ยืนยัน production คือ P5 ไม่ใช่ข้อ ค
>
> **แต่เวอร์ชัน extension ตรงกันทั้งคู่** ทำให้ข้อแตกต่างที่เคยน่ากังวลที่สุดหมดไป — ผลข้อ ค จึง **โอนมาอธิบาย production ได้หนักแน่นขึ้น** ไม่ใช่แค่ผลคนละที่กัน

### 6.4 สถานะล่าสุดของรายการที่เคยค้าง

| # | รายการ | สถานะตอนนี้ |
|---|---|---|
| 1 | **`02_rollback_cron.sql` ทำงานได้ไหม** | **ยังไม่ทดสอบ** · บนโปรเจกต์ทดสอบรันตรง ๆ ไม่ได้ (ข้อ 6.5) · บน production ยังไม่เคยรัน |
| 2 | transaction rollback คืนสถานะ job ได้จริงไหม | **✅ ผ่านบนโปรเจกต์ทดสอบ** — ดูข้อ 6.6 |
| 3 | `01_update_cron.sql` ทั้งไฟล์ (รวมส่วนปิด job เดิม) | **✅ รันบน production สำเร็จแล้ว** — P3 และ P4 · พบปัญหา D1 และ D2 ระหว่างทาง (ข้อ 0.4) |
| 4 | รันเกิน 3 รอบติดต่อกัน | **ยังไม่ทดสอบ** · production เดินต่อเองทุก 30 นาที — ดูได้จาก `c2_sync_runs` |
| 5 | พฤติกรรมเมื่อเว็บต้นทางช้าจนเกิน 30000 ms | **ยังไม่เคยเกิด** ทั้งสองโปรเจกต์ |

### 6.5 ⚠ ทำไมทดสอบ `02_rollback_cron.sql` บนโปรเจกต์ทดสอบตรง ๆ ไม่ได้

สคริปต์นั้นเริ่มด้วย

```sql
select jobid into v_old_id from cron.job where jobname = 'sync-sci-news-every-30-min';
if v_old_id is null then raise exception ...
```

**โปรเจกต์ทดสอบไม่มี job ชื่อนั้น** จึงล้มที่บรรทัดแรกเสมอ

| ประเด็น | ประเมิน |
|---|---|
| เป็นข้อบกพร่องไหม | **ไม่** — เป็นพฤติกรรมที่ถูกต้อง · ล้มเสียงดังดีกว่าทำงานผิดเป้า |
| แปลว่าอะไร | **ต้องมีสคริปต์ทดสอบแยกสำหรับโปรเจกต์ทดสอบ** |
| แก้อย่างไร | เพิ่ม `03_test_rollback_on_test_project.sql` ซึ่งใช้ชื่อ job ของโปรเจกต์ทดสอบ |
| ป้องกันการรันผิดที่ | เพิ่มข้อความใน 01 และ 02 ว่า **ถ้าพบ `c2-sync-sci-news-test` แปลว่าน่าจะอยู่บนโปรเจกต์ทดสอบ ให้ใช้ไฟล์ 03 แทน** |

### 6.6 ✅ transaction rollback คืนสถานะ job — **ผ่านบนโปรเจกต์ทดสอบ**

| รายการ | ค่า |
|---|---|
| โปรเจกต์ | **ทดสอบ `c1-migration-test`** |
| สคริปต์ | `03_test_rollback_on_test_project.sql` ขั้น 1 |
| วิธี | เปลี่ยน `active` แล้ว **จงใจ `raise exception`** ในบล็อกย่อย จากนั้นตรวจค่าที่เหลืออยู่ |
| ผล | **สถานะ `active` กลับมาเท่าค่าตั้งต้น** |

**สิ่งที่ผลนี้ยืนยัน** — ถ้า `01_update_cron.sql` ล้มกลางคัน สถานะ job จะไม่ค้างครึ่ง ๆ คือไม่เกิดกรณี "ปิด job เดิมแล้วแต่ยังไม่มี job ใหม่"

**สิ่งที่ผลนี้ยืนยันไม่ได้**

| # | ยืนยันไม่ได้ |
|---|---|
| 1 | `02_rollback_cron.sql` ทำงานถูกต้องบน production — **ยังไม่เคยรัน** |
| 2 | job เดิมของ production ที่ถูกปิดไว้ กลับมาทำงานได้จริงเมื่อเปิด — **ต้องเปิดจริงจึงรู้** |

> ข้อ 2 เป็นข้อที่เดาไม่ได้ และการทดสอบต้องย้อน Edge Function ด้วย เพราะ job เดิมส่ง anon key ล้วน — เหตุผลอยู่ใน `DEPLOY_PLAN.md` ข้อ 4.3

---

## 7. สิ่งที่ `deno test` ยังยืนยันไม่ได้


| # | สิ่งที่ยืนยันไม่ได้ | ต้องใช้อะไรแทน |
|---|---|---|
| 1 | พฤติกรรมของ **gateway** ก่อนโค้ดทำงาน | `GATEWAY_TEST_PLAN.md` ข้อ 4 |
| 2 | `verify_jwt` รับ JWT ที่ลงนามด้วย **signing key แบบใหม่** ไหม | `GATEWAY_TEST_PLAN.md` ข้อ 6 |
| 3 | `pg_cron` ส่ง header เพิ่มได้จริงไหม | `GATEWAY_TEST_PLAN.md` ข้อ 5 |
| 4 | Edge Function ที่ deploy จริงตรงกับ source นี้ไหม | **ยังเทียบไม่ได้** — ผู้ดำเนินการยืนยันว่าเก็บโค้ดเดิมไว้ก่อน deploy แล้ว แต่ **ยังไม่ได้ตรวจไฟล์สำรอง** ดู `DEPLOY_PLAN.md` ข้อ 3.1 ข |
| 5 | รูปแบบ URL ที่ `supabase-js` ยิงจริงตรงกับตัวจำลองไหม | ทดสอบบนโปรเจกต์แยก |

> **ข้อ 5 เบาลงแล้วหลังแก้ข้อ 2.5** แต่ยังแทนการทดสอบของจริงไม่ได้ — ชุดทดสอบเรียก `handler()` โดยตรง **ข้าม gateway ทั้งหมด**

---

## 8. วิธีรันซ้ำ

```bash
# ตั้งที่อยู่ของ deno portable และ cache
DENO="<scratchpad>/deno-portable/deno.exe"
export DENO_DIR="<scratchpad>/deno-portable/cache"

cd docs/patches/C2_sync_sci_news_auth

"$DENO" check edge-function/index.ts
"$DENO" check tests/sync-sci-news.auth.test.ts
"$DENO" test --allow-env --allow-net=esm.sh,deno.land tests/sync-sci-news.auth.test.ts
```

### ชุด webapi (Node)

ต้องรันในโฟลเดอร์ที่จัดโครงให้ import resolve ได้

```
<work>/
  package.json            {"type":"module"}
  node_modules            junction -> webapi/node_modules
  api/_lib/adminAuth.js   คัดลอกจาก patch
  api/admin/sync-sci-news.js
  tests/webapi-sync-sci-news.test.mjs
```

```bash
node --test tests/webapi-sync-sci-news.test.mjs
```

สร้าง junction บน Windows

```powershell
New-Item -ItemType Junction -Path "<work>
ode_modules" -Target "<repo>\webapi
ode_modules"
```

### ชุดเดิมของ webapi

```bash
cd webapi && node --test
```

| สิทธิ์ | ใช้ทำอะไร |
|---|---|
| `--allow-env` | ตั้งและอ่าน `Deno.env` ในชุดทดสอบ |
| `--allow-net=esm.sh,deno.land` | ดาวน์โหลด dependency ครั้งแรกเท่านั้น · ระหว่างทดสอบ `fetch` ถูกดักไว้ทั้งหมด **ไม่มีคำขอออกเน็ตจริง** |

> ไม่ได้ให้สิทธิ์ `--allow-read` หรือ `--allow-write` · ชุดทดสอบไม่แตะไฟล์ใด ๆ

---

## 9. สถานะการลงมือ

### 9.1 ทำแล้วบน production

| รายการ | สถานะ |
|---|---|
| Deploy Edge Function | **ทำแล้ว** — P1 |
| ตั้ง secrets | **ทำแล้ว** — ยืนยันจาก P5 |
| เปลี่ยน cron | **ทำแล้ว** — P3 และ P4 |
| Deploy webapi | **ทำแล้ว** — P6 |
| เรียก sync จริงบน production | **เกิดขึ้นแล้ว** — ผ่าน cron (P5) และผ่านปุ่ม admin (P8) |

### 9.2 ไม่ได้ทำ

| รายการ | สถานะ |
|---|---|
| เปลี่ยน production เพิ่มในรอบอัปเดตเอกสารนี้ | **ไม่ได้ทำ** |
| แก้ C1 policies | **ไม่ได้ทำ** |
| ติดตั้ง Deno ลงระบบหรือแก้ `PATH` | **ไม่ได้ทำ** — ใช้แบบ portable ในโฟลเดอร์ชั่วคราว |
| แก้ `01_update_cron.sql` หรือ `02_rollback_cron.sql` | **ไม่ได้ทำ** — เก็บไว้เป็นบันทึกของสิ่งที่รันจริง |
| บันทึกค่าคีย์ ค่า secret หรือ URL ของ Vault | **ไม่มีในเอกสารนี้** |
