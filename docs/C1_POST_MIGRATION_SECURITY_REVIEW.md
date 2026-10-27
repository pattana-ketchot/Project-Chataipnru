# ตรวจความปลอดภัยหลัง C1 Migration

> **READ-ONLY** — ไม่แก้ฐานข้อมูล โค้ด สิทธิ์ · ไม่ deploy/restart · **ไม่เรียก `ingest` หรือ `sync-sci-news` ที่เขียนข้อมูล** · ไม่รัน C1 migration ซ้ำ · ไม่เปิดเผย PII, key หรือ token

| รายการ | ค่า |
|---|---|
| วันที่ | 11 ตุลาคม 2569 |
| ขอบเขต | สิทธิ์ของ `ingest` · `sync-sci-news` · สิทธิ์ตารางและฟังก์ชันที่ยังให้ `anon`/`public` |
| สถานะ C1 | **ขึ้นแล้วและผ่านการตรวจ** — anon อ่าน `user_profiles` ได้ 0 แถว · หน้า admin ครบ 3 แถว · M3 ปกติ |

---

## สรุปข้อค้นพบเรียงตามความสำคัญ

| # | ข้อค้นพบ | ระดับ | ยืนยันจาก |
|---|---|---|---|
| **F1** | **Edge Function `sync-sci-news` ตรวจแค่ JWT ไม่ตรวจ role — เรียกตรงด้วย anon key ได้ ข้ามด่าน webapi ทั้งหมด** | **สูง** | **โค้ด + เอกสาร 2 แหล่ง** |
| **F2** | `rag_documents` และ `external_news` ยังอ่านได้โดย `anon` — R1 รูปแบบเดียวกันที่ C1 ไม่ได้แก้ | **กลาง** | เอกสาร · **ต้องทดสอบจริง** |
| **F3** | `TRUNCATE` ของ `anon`/`authenticated` บน `user_profiles` ยังค้างอยู่ | **กลาง** | ผลตรวจรอบก่อน |
| F4 | `ingest` มีสองชั้นป้องกัน — ปลอดภัยกว่า `sync-sci-news` อย่างมีนัย | **ดี** | โค้ด |
| F5 | ไม่มี service role key ที่ใดเลยใน webapi | **ดี** | โค้ด |

---

## 1. F1 — Edge Function เรียกตรงได้ ข้ามด่าน webapi

### 1.1 หลักฐาน

**แหล่งที่ 1 — คอมเมนต์ในโค้ดของเราเอง**

[`webapi/api/admin/sync-sci-news.js:1-5`](webapi/api/admin/sync-sci-news.js)

```js
// Lets an admin/editor force-run the sync-sci-news Edge Function from the
// admin dashboard's SCI Connect tab, instead of waiting for the 30-minute
// cron. The Edge Function itself only checks for a valid Supabase JWT (any
// anon-key request passes that), not a role, so the role check has to
// happen here before we call it — via the shared requireAdminUser() helper.
```

**แหล่งที่ 2 — ผลตรวจ Supabase ของจริงจากรอบก่อน**

[`docs/MIGRATION_005_FINAL_REVIEW.md:474`](docs/MIGRATION_005_FINAL_REVIEW.md)

```
| Edge Function | sync-sci-news · ACTIVE · version 1 · verify_jwt = true · ยังไม่เคย redeploy |
```

[`docs/SUPABASE_LIVE_VERIFICATION.md:1069`](docs/SUPABASE_LIVE_VERIFICATION.md) ยืนยันซ้ำว่า **ตัวที่เขียนข้อมูลจริงคือ Edge Function ตัวนี้**

### 1.2 ความหมายของ `verify_jwt = true`

| สิ่งที่ตรวจ | สิ่งที่**ไม่**ตรวจ |
|---|---|
| JWT ถูกต้องและลงนามโดยโปรเจกต์นี้ | **`role` ของผู้เรียก** |
| | **`status` ของผู้เรียก** |

**anon key คือ JWT ที่ถูกต้อง** — ลงนามโดยโปรเจกต์เดียวกัน และ**อยู่ใน JavaScript ของหน้าเว็บตามธรรมชาติ**

### 1.3 เส้นทางที่ถูกข้าม

```
เส้นทางที่ตั้งใจ (มีด่าน)
  ผู้ใช้ -> POST /api/admin/sync-sci-news -> Caddy -> webapi
        -> requireAdminUser() ตรวจ role + status  <- ด่าน
        -> เรียก Edge Function ด้วย anon key

เส้นทางที่ข้ามด่านได้
  ใครก็ได้ -> POST https://<project>.supabase.co/functions/v1/sync-sci-news
             Authorization: Bearer <anon key จาก bundle>
          -> Edge Function ตรวจแค่ว่า JWT ถูกต้อง -> ผ่าน -> เขียนข้อมูล
```

**ด่านที่ [`adminAuth.js:31-36`](webapi/api/_lib/adminAuth.js) ไม่ได้อยู่บนเส้นทางที่สอง**

### 1.4 ผลกระทบ — ประเมินตามความเป็นจริง

| ประเด็น | ประเมิน |
|---|---|
| ทำอะไรได้ | บังคับให้ sync ข่าวทำงานเมื่อไรก็ได้ ซ้ำกี่ครั้งก็ได้ |
| เขียนอะไร | `external_news` — ข่าวที่ดึงจากแหล่งต้นทาง |
| ขโมยข้อมูลได้ไหม | **ไม่ได้** — ฟังก์ชันนี้เขียนอย่างเดียว ไม่คืนข้อมูลผู้ใช้ |
| แก้ข้อมูลตามใจได้ไหม | **ไม่ได้** — เขียนเฉพาะสิ่งที่ดึงมาจากแหล่งต้นทาง ไม่รับ input จากผู้เรียก (`body: '{}'`) |
| ความเสียหายจริง | **การใช้ทรัพยากรเกินควร** — ยิงรัว ๆ ทำให้ดึงข่าวถี่เกินไป เสี่ยงโดนแหล่งต้นทางจำกัดอัตรา และเพิ่มภาระฐานข้อมูล |
| ตัวนี้ทำงานเองอยู่แล้วไหม | **ใช่** — `pg_cron` job `sync-sci-news-every-30-min` (`*/30 * * * *`) ตามที่บันทึกไว้ใน [`MIGRATION_005_FINAL_REVIEW.md:475`](docs/MIGRATION_005_FINAL_REVIEW.md) |

> **ไม่ใช่ช่องรั่วข้อมูล แต่เป็นช่องให้ใครก็ได้สั่งงานเขียนของระบบ** · ความรุนแรงอยู่ที่การใช้ทรัพยากรและการสูญเสียการควบคุมว่าใครสั่งงานได้ ไม่ใช่ความลับรั่ว

### 1.5 C1 แก้ข้อนี้ไหม

**ไม่** — C1 แก้ `SELECT` policy ของ `user_profiles` เท่านั้น ไม่เกี่ยวกับ Edge Function

### 1.6 สิ่งที่ยังต้องทดสอบจริง

**ยังไม่ได้ยืนยันด้วยการยิงจริง** เพราะการเรียกจะทำให้เกิดการเขียนข้อมูล ซึ่งขัดข้อห้ามรอบนี้

| สิ่งที่ยืนยันแล้วจากโค้ดและเอกสาร | สิ่งที่ยังต้องทดสอบ |
|---|---|
| `verify_jwt = true` | การเรียกตรงด้วย anon key สำเร็จจริงหรือไม่ |
| Edge Function ไม่ตรวจ role (คอมเมนต์ในโค้ดเรา) | Edge Function มีการตรวจ role ภายในที่เราไม่เห็นหรือเปล่า |

> **วิธีทดสอบที่ไม่เขียนข้อมูล** — ยิงด้วย **`OPTIONS`** หรือ **method ที่ฟังก์ชันไม่รองรับ** แล้วดูว่าได้ `401` (ปฏิเสธที่ชั้น JWT) หรือ `405`/`400` (ผ่าน JWT แล้วไปตกที่การตรวจ method)
> **ถ้าได้อย่างหลัง แปลว่า JWT ผ่านแล้วจริง** โดยไม่ต้องให้มันเขียนอะไร

---

## 2. F2 — ตารางอื่นที่ `anon` ยังอ่านได้

### 2.1 โค้ดที่อ่านด้วย anon key **โดยไม่มี token ของผู้ใช้**

| ไฟล์ | บรรทัด | ตาราง | ใช้ทำอะไร |
|---|---|---|---|
| [`webapi/api/sci-connect-news.js`](webapi/api/sci-connect-news.js) | 14, 28-29 | `external_news` | แสดงรายการข่าวสาธารณะ |
| [`webapi/api/sci-connect-news-detail.js`](webapi/api/sci-connect-news-detail.js) | 15, 29-30 | `external_news` | แสดงรายละเอียดข่าว |
| [`webapi/api/_lib/rag.js`](webapi/api/_lib/rag.js) | 17-20 | `rag_documents` | ค้นเอกสารสำหรับตอบคำถาม |
| [`webapi/api/_lib/aiConfig.js`](webapi/api/_lib/aiConfig.js) | 18-24 | `ai_settings` | อ่านชื่อโมเดลที่ใช้อยู่ |

ทั้งสี่สร้าง client ด้วย `VITE_SUPABASE_ANON_KEY` **ไม่มีการส่ง token ของผู้เรียก** จึงทำงานในสิทธิ์ `anon`

### 2.2 ผลที่ตามมา

**ตารางเหล่านี้ต้องเปิดให้ `anon` อ่านได้ ไม่งั้นหน้าเว็บสาธารณะจะพัง** — นี่เป็นการออกแบบ ไม่ใช่ความผิดพลาด

แต่ตามเอกสาร [`AUTHORIZATION_USER_MAPPING_DESIGN.md:220`](docs/AUTHORIZATION_USER_MAPPING_DESIGN.md) บันทึกว่า `rag_documents` เป็น **"ทุกคน"** สำหรับ `SELECT` ซึ่งหมายความว่า

| ตาราง | ความอ่อนไหวของเนื้อหา | ประเมิน |
|---|---|---|
| `external_news` | ข่าวสาธารณะ | **ยอมรับได้** — เป็นข้อมูลที่ตั้งใจเผยแพร่ |
| `ai_settings` | ชื่อโมเดลเท่านั้น (`select('model')`) | **ยอมรับได้** — ตรวจแล้วว่าไม่ได้อ่านคีย์หรือ prompt |
| `rag_documents` | **เนื้อหาเอกสารหลักสูตรที่ทำดัชนีแล้ว** | **ควรทบทวน** — ดูข้อ 2.3 |

### 2.3 `rag_documents` — จุดที่ควรทบทวน

| ประเด็น | ประเมิน |
|---|---|
| เนื้อหาเป็นความลับไหม | **ไม่** — เป็นเนื้อหาจากเอกสาร มคอ. ที่ตอบให้ผู้ใช้อยู่แล้ว |
| ต่างจากการถาม AI อย่างไร | การถาม AI ได้ทีละคำตอบ · **การอ่านตารางตรงได้ทั้งคลังในครั้งเดียว** (9,027 ชิ้นในฝั่ง PostgreSQL ของเรา) |
| ความเสี่ยง | การดูดเนื้อหาทั้งหมดออกไปได้ง่าย · ไม่ใช่ความลับรั่ว แต่เป็นการสูญเสียการควบคุม |
| C1 แก้ไหม | **ไม่** |

### 2.4 ⚠ ยังไม่ได้ทดสอบ — ต้องยืนยันจริง

ข้อมูลข้างบนมาจาก**เอกสารรอบก่อน** ยังไม่ได้ยืนยันกับ Supabase ปัจจุบัน

```sql
-- ตารางไหนยังมี policy ที่เปิดให้อ่านโดยไม่จำกัด
select tablename, policyname, cmd, permissive, roles::text, qual
from pg_policies
where schemaname = 'public'
  and cmd in ('SELECT','ALL')
  and (qual = 'true' or roles::text like '%public%' or roles::text like '%anon%')
order by tablename, policyname;
```

> คืนเฉพาะชื่อตารางและนิยาม policy **ไม่มีข้อมูลผู้ใช้**

---

## 3. F3 — `TRUNCATE` ที่ยังค้าง

| รายการ | สถานะ |
|---|---|
| `anon` และ `authenticated` มี `TRUNCATE` บน `user_profiles` | **ยืนยันแล้วจากรอบก่อน** |
| RLS คุม `TRUNCATE` ไหม | **ไม่** — อยู่นอกการควบคุมของ RLS ทั้งหมด |
| trigger `guard_user_profile_privileges_trigger` กันไหม | **ไม่** — เป็น trigger ของ `UPDATE` |
| C1 แก้ไหม | **ไม่** |
| เรียกผ่าน PostgREST ตรงได้ไหม | **ไม่ได้** — PostgREST ไม่มี verb ที่แปลงเป็น `TRUNCATE` |

**ยังเป็นสิทธิ์เกินจำเป็นที่ขยายความเสียหายของช่องโหว่อื่น** · เสนอ `REVOKE` ในข้อ 6

### 3.1 ต้องตรวจเพิ่ม

```sql
-- สิทธิ์ที่ RLS คุมไม่ได้ ของทุกตารางใน public
select table_name, grantee, privilege_type
from information_schema.role_table_grants
where table_schema = 'public'
  and grantee in ('anon','authenticated')
  and privilege_type in ('TRUNCATE','REFERENCES','TRIGGER')
order by table_name, grantee, privilege_type;
```

---

## 4. F4 — `ingest` ปลอดภัยกว่าอย่างมีนัย

### 4.1 สองชั้นป้องกัน

| ชั้น | กลไก | หลักฐาน |
|---|---|---|
| **1** | `requireAdminUser()` ตรวจ `role` + `status` ที่ webapi | [`api/admin/ingest.js:12-13`](webapi/api/admin/ingest.js) |
| **2** | **RLS บังคับการเขียนในนามผู้เรียก** | [`api/admin/ingest.js:22`](webapi/api/admin/ingest.js) ส่ง `auth.supabase` ซึ่งเป็น client ที่ผูกกับ token ของผู้เรียก |

[`_lib/ingest.js:30`](webapi/api/_lib/ingest.js) มีคอมเมนต์กำกับว่า

```js
// `supabase` must be scoped to an authenticated admin/editor session — RLS enforces the write.
```

### 4.2 ทำไมต่างจาก `sync-sci-news`

| | `ingest` | `sync-sci-news` |
|---|---|---|
| ด่านที่ webapi | มี | มี |
| **ด่านที่ชั้นข้อมูล** | **มี — RLS ของ `rag_documents`** | **ไม่มี** — Edge Function ตรวจแค่ JWT |
| ถ้าข้ามด่าน webapi ได้ | **ยังเขียนไม่ได้** เพราะ RLS กัน | **เขียนได้** |

> **นี่คือความต่างที่สำคัญที่สุดของรายงานฉบับนี้** — `ingest` ออกแบบถูกต้องตามหลักป้องกันหลายชั้น ส่วน `sync-sci-news` พึ่งชั้นเดียว

### 4.3 ข้อควรรู้ — `ingest` ไม่รับ `sourceType` ตามใจ

[`api/admin/ingest.js:4,17`](webapi/api/admin/ingest.js) จำกัดไว้ 4 ค่า

```js
const SOURCE_TYPES = ['major', 'news', 'article', 'knowledge'];
if (!SOURCE_TYPES.includes(sourceType) || !sourceId || !title) -> 400
```

---

## 5. F5 — ไม่มี service role key ใน webapi

ค้นทั้งโฟลเดอร์แล้ว **ไม่พบ `service_role` หรือคีย์ที่ข้าม RLS เลยแม้แต่ที่เดียว**

| ไฟล์ที่สร้าง client | key ที่ใช้ | มี token ของผู้เรียกไหม |
|---|---|---|
| [`_lib/adminAuth.js:21`](webapi/api/_lib/adminAuth.js) | anon | **มี** |
| [`auth.mjs:290`](webapi/auth.mjs) | anon | **มี** |
| [`sci-connect-news.js:14`](webapi/api/sci-connect-news.js) | anon | ไม่มี (เส้นทางสาธารณะ) |
| [`sci-connect-news-detail.js:15`](webapi/api/sci-connect-news-detail.js) | anon | ไม่มี (เส้นทางสาธารณะ) |
| [`_lib/rag.js:20`](webapi/api/_lib/rag.js) | anon | ไม่มี |
| [`_lib/aiConfig.js:23`](webapi/api/_lib/aiConfig.js) | anon | ไม่มี |

**เป็นการออกแบบที่ดี** — ไม่มีคีย์ที่ข้าม RLS อยู่ในบริการนี้เลย ถ้า webapi ถูกเจาะ ผู้โจมตีก็ได้แค่สิทธิ์ระดับ `anon`

---

## 6. แยกสิ่งที่ยืนยันแล้ว ออกจากสิ่งที่ต้องทดสอบ

### ✅ ยืนยันจากโค้ดและเอกสารแล้ว

| # | ข้อสรุป | หลักฐาน |
|---|---|---|
| 1 | `sync-sci-news.js` เรียก Edge Function ด้วย **anon key** | `sync-sci-news.js:18-22` |
| 2 | Edge Function ตั้ง `verify_jwt = true` และ**ไม่ตรวจ role** | `MIGRATION_005_FINAL_REVIEW.md:474` + คอมเมนต์ `sync-sci-news.js:3-5` |
| 3 | มี `pg_cron` เรียกฟังก์ชันนี้ทุก 30 นาทีอยู่แล้ว | `MIGRATION_005_FINAL_REVIEW.md:475` |
| 4 | `ingest` ส่ง client ที่ผูกกับ token ผู้เรียก → RLS บังคับการเขียน | `ingest.js:22` + `_lib/ingest.js:30` |
| 5 | `ingest` จำกัด `sourceType` ไว้ 4 ค่า | `ingest.js:4,17` |
| 6 | ทั้งสอง endpoint ผ่าน `requireAdminUser()` ก่อนเสมอ | `ingest.js:12` · `sync-sci-news.js:14` |
| 7 | ระดับสิทธิ์ของทั้งสองเป็น `EDITOR` ในตารางเส้นทาง | `server.mjs:52-53` |
| 8 | **ไม่มี service role key ใน webapi เลย** | ค้นทั้งโฟลเดอร์ |
| 9 | 4 ไฟล์อ่าน Supabase ด้วย anon key โดยไม่มี token ผู้ใช้ | ตารางข้อ 2.1 |

### ⏳ ต้องทดสอบจริงก่อนสรุป

| # | สิ่งที่ต้องยืนยัน | วิธีที่ไม่เขียนข้อมูล |
|---|---|---|
| **1** | **Edge Function รับ anon key จริงหรือไม่** | ยิงด้วย `OPTIONS` หรือ method ที่ไม่รองรับ แล้วดูว่าได้ `401` หรือ `405`/`400` |
| **2** | ตารางใดยัง `SELECT` ได้โดย `anon` | SQL ข้อ 2.4 |
| **3** | `TRUNCATE` ยังค้างที่ตารางไหนบ้าง | SQL ข้อ 3.1 |
| 4 | `rag_documents` อ่านได้ทั้งคลังโดย anon จริงไหม | PostgREST + `limit=0` + `Prefer: count=exact` → ดู `Content-Range` |
| 5 | Edge Function มีการตรวจ role ภายในที่เราไม่เห็นหรือไม่ | ดูโค้ด Edge Function ใน Supabase Dashboard |

---

## 7. ขั้นถัดไปที่จำเป็น

### 7.1 เรียงตามความสำคัญ

| ลำดับ | สิ่งที่ต้องทำ | ทำไม |
|---|---|---|
| **1** | **ยืนยัน F1 ด้วยการทดสอบที่ไม่เขียนข้อมูล** (ข้อ 6 ข้อ 1) | เป็นข้อค้นพบที่รุนแรงที่สุด ต้องรู้ว่าจริงไหมก่อนวางแผนแก้ |
| **2** | รัน SQL ข้อ 2.4 และ 3.1 | รู้ขอบเขตที่แท้จริงของ F2 และ F3 |
| 3 | อ่านโค้ด Edge Function ใน Dashboard | ยืนยันว่าไม่มีการตรวจ role ภายใน |
| 4 | ตัดสินใจเรื่องการแก้ F1 | ดูข้อ 7.2 |
| 5 | ขออนุมัติ `REVOKE TRUNCATE` แยก | F3 |
| 6 | ทบทวนว่า `rag_documents` ควรเปิดให้ anon อ่านทั้งคลังไหม | F2 |

### 7.2 รายการแก้ที่เสนอให้ตรวจทานก่อนลงมือ

> **ยังไม่แก้อะไร** — เสนอเพื่อให้ตรวจทานและอนุมัติแยก

#### ทางเลือกสำหรับ F1

| ทาง | วิธี | ข้อดี | ข้อเสีย |
|---|---|---|---|
| **ก** | เพิ่มการตรวจ role **ในโค้ด Edge Function** | ปิดช่องที่ต้นเหตุ · ครอบทุกเส้นทาง | ต้องแก้และ redeploy Edge Function · เป็นของนอกรีโปนี้ |
| **ข** | ตั้ง `verify_jwt = false` แล้วให้ฟังก์ชันตรวจ secret header ที่รู้กันเฉพาะ webapi | ควบคุมได้ว่าใครเรียกได้ | ต้องจัดการ secret เพิ่ม · ถ้าหลุดก็เหมือนเดิม |
| **ค** | ปิดการเรียกจากภายนอกทั้งหมด ให้เหลือแต่ `pg_cron` | ง่ายที่สุด | **เสียฟีเจอร์ปุ่มบังคับ sync ในหน้า admin** |
| **ง** | ยอมรับความเสี่ยง + ตั้ง rate limit | ไม่ต้องแก้อะไรมาก | ช่องยังเปิด |

**ความเห็น** — **ทาง ก ถูกต้องที่สุด** เพราะปิดที่ต้นเหตุและไม่เสียฟีเจอร์ · ถ้าแก้ Edge Function ไม่สะดวก **ทาง ง พร้อมบันทึกความเสี่ยงไว้** ก็ยอมรับได้ในระยะสั้น เพราะผลกระทบคือการใช้ทรัพยากร ไม่ใช่ข้อมูลรั่ว

#### สำหรับ F3

```sql
-- ⚠ ยังไม่รัน ต้องอนุมัติแยก และต้องดูผล SQL ข้อ 3.1 ก่อน
revoke truncate on table public.user_profiles from anon, authenticated;
```

**ห้ามใช้ `revoke all`** — จะถอด `SELECT`/`UPDATE` ที่ระบบใช้จริงไปด้วย

#### สำหรับ F2

ยังไม่เสนอคำสั่งแก้ เพราะ **ต้องรู้ผล SQL ข้อ 2.4 ก่อน** ว่าตารางใดเปิดอยู่บ้างและแต่ละตารางจำเป็นต้องเปิดหรือไม่

---

## 8. สิ่งที่ C1 แก้ไปแล้วและยังดีอยู่

| รายการ | สถานะ |
|---|---|
| `anon` อ่าน `user_profiles` | **0 แถว** — ปิดแล้ว |
| หน้า admin อ่านได้ครบ | **3 แถว** |
| M3 `/healthz` | `200` · `status=ok` · `authConfigured=true` · `dbConfigured=true` |
| M3 `extract-file` ด้วย admin | **200** และข้อความตรงกัน |
| RLS 4 กรณี + rollback บนโปรเจกต์ทดสอบ | **ผ่าน** |

> **C1 บรรลุเป้าหมายของมันครบถ้วน** · ข้อค้นพบในรายงานนี้เป็นเรื่องที่อยู่นอกขอบเขต C1 ตั้งแต่ต้น ไม่ใช่ผลข้างเคียงของ C1

---

## 9. ยืนยันขอบเขต

| ข้อห้าม | สถานะ |
|---|---|
| แก้ฐานข้อมูล โค้ด หรือสิทธิ์ | **ไม่ได้ทำ** |
| Deploy / Restart | **ไม่ได้ทำ** |
| **เรียก `ingest` หรือ `sync-sci-news`** | **ไม่ได้ทำ** — วิเคราะห์จากโค้ดและเอกสารเท่านั้น |
| รัน C1 migration ซ้ำ | **ไม่ได้ทำ** |
| เปิดเผย PII / key / token | **ไม่มีในเอกสารนี้** |

```
Local  HEAD 427ce19 · mko-phase2 · ไฟล์โค้ดที่แก้ 0
Prod   webapi d2663f039a18 · running · healthy
```

**สถานะ: รายงานตรวจอย่างเดียว — F1 ต้องยืนยันด้วยการทดสอบก่อนวางแผนแก้**
