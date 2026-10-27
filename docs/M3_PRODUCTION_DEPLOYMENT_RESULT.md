# M3 — ผลการ Deploy ขึ้น Production

**วันที่ 10 ตุลาคม 2569 เวลา 20:47–21:10 น.**

---

## ผลสรุป

# `DEPLOY_SUCCESS`

Smoke test **ผ่านครบ 11 ข้อ** · ไม่มี rollback · บริการอื่นไม่ถูกแตะแม้แต่ตัวเดียว

| รายการ | ค่า |
|---|---|
| Commit | `427ce19` บน `mko-phase2` |
| Image ใหม่ | `d2663f039a18` (483 MB) |
| Image เดิม / rollback | `1163e36361d9` (527 MB) — **ยังอยู่ครบ** |
| คอนเทนเนอร์ | `running` · `healthy` · **restarts = 0** |
| บริการที่เปลี่ยน | **`webapi` เท่านั้น** |

---

## 1. Phase 1 — ยืนยันก่อนเริ่ม

### 1.1 ต่อถูกเครื่อง

| จุดตรวจ | ค่า |
|---|---|
| hostname | `stpnru` |
| จำนวนผู้ใช้ใน `public.users` | **201** (เครื่องพัฒนาคือ 56) |

ตรวจข้อนี้เพราะเครื่องพัฒนามีคอนเทนเนอร์ชื่อ `course-advisor-system-postgres-1` เหมือนกันเป๊ะ คำสั่งที่ไม่ผ่าน ssh จะไปโดนเครื่องผิดโดยไม่มีอะไรเตือน

### 1.2 Commit และ source

```
HEAD        427ce19 · branch mko-phase2 · ไฟล์โค้ดที่แก้ยังไม่ commit 0
webapi/api/ 10 ไฟล์ · symlink 0
hash        2b67e0f4a9dc9fd9f47231d93eaff12903d962d0e8d430f3347dbe52cafa8fcd
```

### 1.3 Rollback image ก่อนเริ่ม

`:latest` · `:rollback-pre-m3` · คอนเทนเนอร์ที่รันอยู่ — **ชี้ `1163e36361d9` ตรงกันทั้งสามจุด**

### 1.4 แก้คำอธิบายสิทธิ์ `advisor_web` ใน Runbook

รอบตรวจก่อนหน้าพบว่า Runbook เขียนว่า `INSERT/UPDATE/DELETE` → "ไม่มีสิทธิ์" โดยไม่ระบุขอบเขต ซึ่งอ่านแล้วเข้าใจผิดได้ว่า role นี้เขียนอะไรไม่ได้เลย

ตรวจจริงทุกตารางแล้วพบว่า

| ตาราง | สิทธิ์ |
|---|---|
| `public.users` | **ไม่มีสิทธิ์ระดับตาราง** — มีเฉพาะ `SELECT` บน `id`, `is_active`, `supabase_user_id` |
| `web.ai_settings` | `SELECT`, `UPDATE` |
| `web.external_news` | `SELECT` |
| `web.knowledge_articles` | `INSERT`, `SELECT`, `UPDATE` |
| `web.news` | `INSERT`, `SELECT`, `UPDATE` |
| `web.site_courses` | `INSERT`, `SELECT`, `UPDATE` |

แก้ Runbook แล้วให้ระบุชัดว่า **เขียน `public.users` ไม่ได้ แต่เขียน `web` schema ได้** พร้อมหมายเหตุว่าสิทธิ์ชุดนี้มีอยู่ก่อน M3 และโค้ด M3 ไม่แตะ `web` schema เลย

---

## 2. Phase 2 — Backup

ทั้ง 4 อย่างสำเร็จ และ **ตรวจแล้วว่าใช้งานได้จริง ไม่ใช่แค่มีไฟล์อยู่**

| สิ่งที่สำรอง | ไฟล์ | การตรวจ |
|---|---|---|
| ฐานข้อมูล | `backups/course_advisor_20261010_204704.sql.gz` 52 MB | `gzip -t` **ผ่าน** |
| `.env` | `~/m3-backup-env-20261010T204704` | 19 คีย์ · สิทธิ์ `600` |
| compose | `~/m3-backup-compose-20261010T204704.yml` 11 KB | มี service `webapi` |
| `webapi/api/` | `~/m3-backup-webapi-api-20261010T204704.tar.gz` | แตกออกมาแล้ว **10 ไฟล์ · hash `2b67e0f4…fa8fcd` ตรงเป๊ะ** |

พื้นที่เซิร์ฟเวอร์เหลือ 62 GB

---

## 3. Phase 3 — ตั้งค่า Production

### 3.1 Role

`advisor_web` · `login=true` · `superuser=false` · `createdb=false`

### 3.2 `ADVISOR_WEB_PASSWORD`

เจ้าของป้อนเองบนเซิร์ฟเวอร์ด้วย `read -rsp` **ผู้ช่วยไม่เคยเห็นค่า**

ผลตรวจหลังเพิ่ม (อ่านรูปแบบเท่านั้น ไม่อ่านค่า)

| จุดตรวจ | ผล |
|---|---|
| จำนวนบรรทัดของคีย์ | **1** (ไม่ใช่ 0 และไม่ใช่ 2) |
| ความยาวค่า | **64** |
| ตรงรูปแบบ `^[0-9a-f]{64}$` | **ใช่** |
| สิทธิ์ไฟล์ | `600 ubuntu:ubuntu` ไม่เปลี่ยน |
| ขนาดไฟล์ | 1,867 → **1,953 ไบต์** (โต 86 ไบต์พอดี = ชื่อคีย์ 21 + ค่า 64 + ขึ้นบรรทัด 1) |
| จำนวนคีย์ทั้งหมด | 19 → **20** เพิ่มขึ้นหนึ่งพอดี |

**ไม่มีการเปลี่ยนรหัสผ่านของ role ในฐานข้อมูล** — ไม่มีคำสั่ง `ALTER ROLE` เกิดขึ้นเลยตลอดงาน

---

## 4. Phase 4 — ส่งไฟล์และ Build

### 4.1 การส่งไฟล์

สร้าง archive จาก `427ce19` ด้วย `git -c core.autocrlf=false archive` เพื่อกันกับดัก CRLF

| จุดตรวจ | ผล |
|---|---|
| hash ต้นทาง / ปลายทาง | `c43376e175010a4f622e9e78327d315e…` **ตรงกัน** |
| `webapi/api/` ใน archive | **0 ไฟล์** — ไม่อยู่ใน git จึงเขียนทับอะไรไม่ได้ตามนิยาม |
| วิธีวาง | `cp` ทีละไฟล์ **7 ครั้ง** ไม่ใช้ `rsync --delete` |
| `rm` ที่ใช้ | `rm -rf /tmp/m3-extract` ที่พักชั่วคราวเท่านั้น |

### 4.2 ไฟล์หลังคัดลอก — ขนาดตรงกับฝั่ง local ทุกตัว

| ไฟล์ | ขนาด | ก่อนหน้า |
|---|---|---|
| `server.mjs` | 15,815 | 4,151 (ของเก่า) |
| `auth.mjs` | 29,042 | **ไม่มี** |
| `db.mjs` | 14,403 | **ไม่มี** |
| `package-lock.json` | 31,378 | **ไม่มี** |
| `Dockerfile` | 3,117 | ของเก่า |
| `package.json` | 345 | ของเก่า |
| `docker-compose.prod.yml` | — | ไม่มีส่วน M3 |

compose หลังอัปเดต — `WEBAPI_DB_USER` 1 · `ADVISOR_WEB_PASSWORD` 1 · `depends_on … service_healthy` ครบ

### 4.3 `webapi/api/` หลังคัดลอก

```
10 ไฟล์ · symlink 0
hash 2b67e0f4a9dc9fd9f47231d93eaff12903d962d0e8d430f3347dbe52cafa8fcd
```

**ไม่เปลี่ยนแม้แต่ไบต์เดียว**

### 4.4 Build

ผ่านทุกขั้น รวมถึง `COPY api ./api` ที่จะล้มทันทีถ้าไม่มี source

หลัง build — `:latest` = `d2663f039a18` (ใหม่) · `:rollback-pre-m3` = `1163e36361d9` (เดิม) · **คอนเทนเนอร์ยังรันของเก่าอยู่ ผู้ใช้ยังไม่ถูกกระทบ**

### 4.5 ตรวจของใน image ก่อน `up`

| จุดตรวจ | ผล |
|---|---|
| ไฟล์ใน `/app` | `api` `auth.mjs` `db.mjs` `node_modules` `package-lock.json` `package.json` `server.mjs` — **ครบ** |
| `api/` | **10 ไฟล์** · hash `2b67e0f4…fa8fcd` **ตรงกับ source ทุกไบต์** |
| `*.test.mjs` | **ไม่มี** ถูกต้อง |
| `pg` | **8.23.1** ตรงกับ lock file |

---

## 5. Phase 5 — Deploy

```bash
docker compose -f docker-compose.prod.yml up -d --no-deps webapi
```

```
Container course-advisor-system-webapi-1 Recreate
Container course-advisor-system-webapi-1 Recreated
Container course-advisor-system-webapi-1 Starting
Container course-advisor-system-webapi-1 Started
```

หลังรอ health check — `status=running health=healthy restarts=0 image=d2663f039a18`

### 5.1 ตรวจการเชื่อมต่อ PostgreSQL จริง

รันในคอนเทนเนอร์ `webapi` เรียก resolver ด้วย UUID สังเคราะห์ที่เป็นศูนย์ทั้งหมด

```
ปลายทาง: advisor_web@postgres:5432/course_advisor
เหตุผลที่ได้: ACCOUNT_NOT_LINKED
status หลังเรียก: up
สรุป: ต่อฐานข้อมูลได้ และอ่าน public.users ได้ -> ผ่าน
```

**พิสูจน์พร้อมกันสามอย่าง** — รหัสผ่านที่ใส่ใน `.env` ถูกต้อง · network จากคอนเทนเนอร์ถึง `postgres` ใช้ได้ · สิทธิ์อ่าน `public.users` ทำงานจริง

ต่อผ่าน host `postgres` ไม่ใช่ `127.0.0.1` จึงถูกบังคับยืนยันรหัสผ่านจริง ไม่หลงไปเจอ `trust` ของ `pg_hba`

> ไฟล์ตรวจ `m3probe.mjs` ลบออกจากคอนเทนเนอร์เรียบร้อยแล้ว — `/app` กลับมามีเฉพาะไฟล์ที่ควรมี

---

## 6. Phase 6 — Smoke Test

| # | ทดสอบ | ต้องได้ | ได้จริง | ผล |
|---|---|---|---|---|
| 1 | คอนเทนเนอร์ | `healthy` | `Up (healthy)` restarts 0 | **ผ่าน** |
| 2 | `/healthz` | `status=ok` · `authConfigured=true` · `dbConfigured=true` · 5 เส้นทางมี level | ตรงทุกค่า | **ผ่าน** |
| 3 | เชื่อมต่อ PostgreSQL | `ACCOUNT_NOT_LINKED` + `up` | ตรง | **ผ่าน** |
| 4 | `GET /api/sci-connect-news` | 200 | **200** | **ผ่าน** |
| 5 | `news-detail` ไม่ส่ง slug | 400 | **400** | **ผ่าน** |
| 5 | `news-detail` slug ไม่มีจริง | 404 | **404** | **ผ่าน** |
| 5 | `news-detail` slug จริง | 200 | **200** | **ผ่าน** |
| 6 | `extract-file` ไม่มี token | 401 | **401** | **ผ่าน** |
| 7 | `ingest` ไม่มี token | 401 | **401** | **ผ่าน** |
| 8 | **`extract-file` พร้อม token ของ S1** | **200** | **200** | **ผ่าน** |
| 9 | `chat` ผ่าน FastAPI | ไม่ใช่ 404/502 | **422** (validation ของ FastAPI) | **ผ่าน** |
| 10 | log | ไม่มีรหัสผ่าน | **0 รูปแบบที่ตรงกับรหัสผ่าน/โทเคน** | **ผ่าน** |
| 11 | connection `advisor_web` | 0–5 | **0** | **ผ่าน** |

### 6.1 ข้อ 8 — ข้อที่สำคัญที่สุด

เป็นข้อเดียวที่พิสูจน์ว่า **authorization foundation ที่เพิ่งขึ้น production ไม่ล็อกผู้ดูแลออกจากระบบ**

ทดสอบด้วย `extract-file` ซึ่งตรวจโค้ดแล้วว่า**ไม่เขียนข้อมูลใด ๆ** — ไม่เรียก supabase เลย (0 ครั้ง) และ `_lib/fileExtract.js` ไม่มี side effect ภายนอก เป็นเส้นทางระดับ `EDITOR` เพียงเส้นเดียวจากสามเส้นที่ปลอดภัยพอจะทดสอบด้วย token จริง

**เจ้าของเป็นผู้ล็อกอินและยิงคำขอเอง** ผ่าน Console ของเบราว์เซอร์ที่มี token อยู่แล้ว **ผู้ช่วยไม่เคยเห็นและไม่เคยถือ token**

### 6.2 log ตอนบูต

```
[webapi] พร้อมให้บริการ /api/sci-connect-news-detail (PUBLIC)
[webapi] พร้อมให้บริการ /api/sci-connect-news (PUBLIC)
[webapi] พร้อมให้บริการ /api/admin/extract-file (EDITOR)
[webapi] พร้อมให้บริการ /api/admin/ingest (EDITOR)
[webapi] พร้อมให้บริการ /api/admin/sync-sci-news (EDITOR)
[webapi] ตั้งค่าฐานข้อมูลแล้ว: advisor_web@postgres:5432/course_advisor
[webapi] ฟังที่พอร์ต 3001 · 5 เส้นทาง
[webapi] ปฏิเสธ /api/admin/extract-file (EDITOR) — ผู้เรียก: anonymous
[webapi] ปฏิเสธ /api/admin/ingest (EDITOR) — ผู้เรียก: anonymous
```

สองบรรทัดท้ายคือผลของข้อ 6 และ 7 — **ด่านปฏิเสธก่อนถึง handler จึงไม่มีการเขียนข้อมูลเกิดขึ้น**

บรรทัดตั้งค่าฐานข้อมูลแสดงแค่ `user@host:port/database` **ไม่มีรหัสผ่าน** ตามที่ออกแบบ

ระบบบันทึกเฉพาะคำขอที่**ถูกปฏิเสธ** ไม่บันทึกคำขอที่ผ่าน จึงไม่มีบรรทัดของข้อ 8 ซึ่งถูกต้อง

### 6.3 เส้นทางที่ไม่ได้ทดสอบด้วย token โดยเจตนา

| เส้นทาง | เหตุผล |
|---|---|
| `POST /api/admin/ingest` | `delete` + `upsert` + `delete` บน `rag_documents` ของจริง |
| `POST /api/admin/sync-sci-news` | สั่ง Edge Function เขียน `external_news` ของจริง |

ทดสอบเฉพาะแบบไม่มี token (ข้อ 7) ซึ่งพิสูจน์ว่าด่านกัดก่อน handler

---

## 7. สถานะบริการอื่น — ไม่ถูกแตะเลย

| บริการ | ก่อน deploy | หลัง deploy |
|---|---|---|
| **webapi** | Up 2 weeks | **Up (healthy) — เปลี่ยนตัวเดียว** |
| frontend | Up 11 days | **Up 11 days** |
| backend | Up 11 days | **Up 11 days** |
| postgres | Up 7 weeks (healthy) | **Up 7 weeks (healthy)** |
| caddy | Up 2 weeks | **Up 2 weeks** |
| ollama | Up 7 weeks (healthy) | **Up 7 weeks (healthy)** |
| db-viewer | Up 3 weeks | **Up 3 weeks** |

`--no-deps` ทำงานตามที่ตั้งใจ — ไม่มีบริการใดถูก restart นอกจาก `webapi`

---

## 7.1 Phase 7 — ผลการเฝ้าระวัง 10 นาที

เก็บตัวอย่างทุก 1 นาที ตั้งแต่ 21:23:30 ถึง 21:32:48

```
21:23:30 | healthy | restarts=0 | news=200
21:24:32 | healthy | restarts=0 | news=200
21:25:33 | healthy | restarts=0 | news=200
21:26:35 | healthy | restarts=0 | news=200
21:27:38 | healthy | restarts=0 | news=200
21:28:39 | healthy | restarts=0 | news=200
21:29:41 | healthy | restarts=0 | news=200
21:30:43 | healthy | restarts=0 | news=200
21:31:46 | healthy | restarts=0 | news=200
21:32:48 | healthy | restarts=0 | news=200
```

**10 ตัวอย่าง `healthy` ทั้งหมด · `restarts=0` ตลอด · เส้นทางสาธารณะตอบ 200 ทุกครั้ง**

สถานะหลังครบช่วงเฝ้าระวัง — `Up 31 minutes (healthy)` · `restarts=0` · `image=d2663f039a18`

### 7.2 สิ่งที่สังเกตได้จาก log

ไทม์ไลน์ทั้งหมดตั้งแต่คอนเทนเนอร์ใหม่เริ่มทำงาน

| เวลา | เหตุการณ์ |
|---|---|
| 21:01:17 | คอนเทนเนอร์ใหม่เริ่มทำงาน · ประกาศ 5 เส้นทางพร้อมระดับสิทธิ์ · ตั้งค่าฐานข้อมูลสำเร็จ |
| 21:02:30 | ปฏิเสธ `extract-file` และ `ingest` — ผู้เรียก `anonymous` (**คือ smoke test ข้อ 6 และ 7**) |
| 21:27:37 | ปฏิเสธ `extract-file` — `anonymous (auth failed)` |

รายการ 21:27:37 เป็นคำขอที่**แนบ token มาแต่ตรวจไม่ผ่าน** ต่างจากสองรายการก่อนหน้าที่ไม่มี token เลย เกิดจากการทดลองยิงด้วย token ที่คัดลอกมาไม่สมบูรณ์ในเทอร์มินัล (ดูปัญหาข้อ 4)

**เป็นพฤติกรรมที่ถูกต้อง** — ด่านปฏิเสธ token ที่ใช้ไม่ได้ และปฏิเสธ**ก่อน**ถึง handler จึงไม่มีการเขียนข้อมูลเกิดขึ้น

> smoke test ข้อ 8 ที่สำเร็จ (HTTP 200) **ไม่ปรากฏใน log** เพราะระบบบันทึกเฉพาะคำขอที่ถูกปฏิเสธ ไม่บันทึกคำขอที่ผ่าน ซึ่งเป็นพฤติกรรมที่ออกแบบไว้

การนับบรรทัดที่ตรงกับคำว่า `error|failed` ได้ **1** มาจากคำว่า `auth failed` ในบรรทัดภาษาไทยนั้นเอง **ไม่ใช่ข้อผิดพลาดของระบบ** · ไม่มี exception ไม่มี `ECONNREFUSED` ไม่มีรหัสผ่านหรือโทเคนหลุดใน log (สแกนได้ 0)

---

## 8. ปัญหาที่พบและการแก้

| # | ปัญหา | สาเหตุ | การแก้ |
|---|---|---|---|
| 1 | Runbook ระบุสิทธิ์ `advisor_web` ไม่ครบขอบเขต | ตรวจรอบก่อนกรองเฉพาะตาราง `users` | ตรวจทุกตารางแล้วแก้เอกสาร ระบุว่าเขียน `web` schema ได้ |
| 2 | เกณฑ์ข้อ 11 เขียนว่า connection ต้อง `> 0` | ขัดกับ `min: 0` ของ pool ที่ตั้งใจไม่จอง connection ตอนไม่มีทราฟฟิก | แก้เกณฑ์เป็น `0–5` พร้อมเหตุผล |
| 3 | คำสั่งที่ส่งให้เจ้าของรันเองโดนตัดด้วย bracketed paste | เทอร์มินัลแทรก `^[[200~` หน้าคำสั่ง | ปิดด้วย `bind 'set enable-bracketed-paste off'` ครั้งเดียวทั้ง session |
| 4 | คัดลอก access token ได้ความยาวไม่คงที่ (34 / 955 / 1912 / 50) | 34 = ชื่อ key · 1912 = JSON ทั้งก้อน · การวางสตริงยาวในเทอร์มินัลไม่เสถียร | เปลี่ยนไปทดสอบจาก Console ของเบราว์เซอร์แทน ไม่ต้องย้าย token ออกจากเบราว์เซอร์เลย |
| 5 | ไฟล์ตรวจ `m3probe.mjs` ลบไม่ออก | คอนเทนเนอร์รันด้วยสิทธิ์ `node` แต่ `/app` เป็นของ root | ลบด้วย `docker exec -u root` และยืนยันว่า `/app` สะอาดแล้ว |
| 6 | `heredoc` ผ่าน ssh ถูกตัดกลางคัน | คำสั่งยาวหลายบรรทัดไม่ถูกส่งครบ | แยกเป็นคำสั่งสั้น ๆ และตรวจผลทุกขั้นแทนการเชื่อเอาต์พุต |

### ข้อสังเกตด้านความปลอดภัยระหว่างทำงาน

ระหว่างพยายามคัดลอก token มีชิ้นส่วนของ token ปรากฏบนหน้าจอเทอร์มินัลหนึ่งครั้ง (จากการวางตอนที่ `read` ยังไม่ทำงาน) เป็นเพียงบางส่วน และ token ของ Supabase หมดอายุในราวหนึ่งชั่วโมง

**แนะนำให้ออกจากระบบแล้วล็อกอินใหม่** เพื่อเปลี่ยน token ชุดนั้น

---

## 9. สิ่งที่ยังค้างหลัง Deploy

### ควรทำเร็ว ๆ นี้

| # | งาน | หมายเหตุ |
|---|---|---|
| 1 | **แก้ R1** — `web.user_profiles` ของ Supabase ใครก็อ่านได้ ขณะเก็บอีเมลและชื่อผู้ดูแล | **M3 ไม่ได้แก้ข้อนี้** ต้องขออนุมัติแยก |
| 2 | ออกจากระบบแล้วล็อกอินใหม่เพื่อเปลี่ยน token | ดูข้อ 8 |
| 3 | commit เอกสารที่ค้าง | ตอนนี้ `docs/` มีไฟล์ยังไม่ commit และ branch นำหน้า remote 7 commits |

### ระยะถัดไป

| # | งาน |
|---|---|
| 4 | พิจารณาแยก role อ่านอย่างเดียวสำหรับ M3 แทนการใช้ `advisor_web` ที่เขียน `web` schema ได้ |
| 5 | ถอด `requireAdminUser` ออกจาก handler เมื่อมั่นใจด่านกลาง — ตอนนี้ `/api/admin/*` เรียก Supabase สองรอบต่อคำขอ |
| 6 | เปลี่ยน UUID ใน `webapi/auth.test.mjs:480` เป็นค่าสังเคราะห์ |
| 7 | เขียน `docs/DEPLOY_WEB.md` หรือลบการอ้างอิงใน `docker-compose.prod.yml:169` |
| 8 | เพิ่ม `webapi/.dockerignore` — `node_modules/` ถูกส่งเข้า build context ทั้งก้อน |
| 9 | ไดรฟ์ C: ของเครื่องพัฒนาเหลือ 6.5 GB (99%) — พิจารณาย้าย Docker disk image ไป D: |

### ไฟล์สำรองที่ควรเก็บไว้จนกว่าจะมั่นใจ

```
~/m3-backup-env-20261010T204704
~/m3-backup-compose-20261010T204704.yml
~/m3-backup-webapi-api-20261010T204704.tar.gz
~/course-advisor-system/backups/course_advisor_20261010_204704.sql.gz
~/m3-427ce19.tar.gz
```

วิธี rollback ถ้าจำเป็นภายหลังอยู่ใน `M3_PRODUCTION_DEPLOYMENT_RUNBOOK.md` หัวข้อ 6

---

## 10. ยืนยันขอบเขต

| ข้อห้าม | สถานะ |
|---|---|
| แก้หรือลบข้อมูล production database | **ไม่มี** — ใช้ `SELECT` อย่างเดียวตลอดงาน |
| เปลี่ยนรหัสผ่าน PostgreSQL role | **ไม่มี** — ไม่มี `ALTER ROLE` เกิดขึ้นเลย |
| แก้ Supabase Auth / RLS / `user_profiles` | **ไม่มี** — ไม่ได้เชื่อมต่อ Supabase เลย |
| ลบหรือเขียนทับ `webapi/api/` | **ไม่มี** — hash ก่อนและหลังตรงกันทุกไบต์ · ยัง 10 ไฟล์ |
| Restart postgres / FastAPI / frontend / caddy | **ไม่มี** — ทุกตัวแสดงเวลาทำงานต่อเนื่องเท่าเดิม |
| Push / Merge | **ไม่มี** — HEAD ยัง `427ce19` |
| แก้ frontend repository | **ไม่มี** |
| Deploy ระบบอื่นนอกจาก webapi | **ไม่มี** — ใช้ `--no-deps` |

### ยืนยันว่าไม่มีข้อมูลลับในรายงานนี้

| สิ่งที่สแกน | ผล |
|---|---|
| รหัสผ่าน | **ไม่มี** — รายงานค่าเฉพาะความยาวและรูปแบบ |
| Access token | **ไม่มี** — รายงานเฉพาะรหัส HTTP |
| UUID | **ไม่มี** — UUID เดียวที่กล่าวถึงคือค่าศูนย์ทั้งหมดซึ่งเป็นค่าสังเคราะห์ |
| อีเมลหรือข้อมูลส่วนบุคคล | **ไม่มี** |
| Image ID | ย่อ 12 หลักตามปกติของ docker ไม่ใช่ข้อมูลลับ |

---

# สถานะสุดท้าย: `DEPLOY_SUCCESS`
