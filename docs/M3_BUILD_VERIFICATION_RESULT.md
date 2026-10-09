# M3 — ผลการตรวจสอบ Docker Build ด้วย Source จริง

> ตรวจในเครื่อง local เท่านั้น · **ไม่แตะ production** · ไม่ deploy · ไม่ restart · ไม่ push/merge

## ผลสรุป

# `M3_BUILD_VERIFIED`

Build ผ่าน · ไฟล์ใน image ครบและ hash ตรงกับ production · import 7/7 · container บูตและตอบ `/healthz` ได้ · regression 82/82

| รายการ | ค่า |
|---|---|
| วันที่ | 10 ตุลาคม 2569 |
| Image ที่สร้าง | `webapi-m3-localtest:dba865b` (id `a14d79bd88c7`) |
| Image ของ production | `course-advisor-system-webapi:latest` — **ไม่ถูกแตะ ไม่มีในเครื่อง local ด้วยซ้ำ** |
| Source ที่ใช้ | 10 ไฟล์จริงจาก production · hash `2b67e0f4…fa8fcd` |
| Stub | **ไม่มี** |

---

## 1. การแก้ปัญหาพื้นที่ไดรฟ์ C:

Docker Desktop เริ่มไม่ขึ้นเพราะไดรฟ์ C: เต็ม — ได้รับอนุมัติให้ล้าง **npm cache อย่างเดียว**

| | ก่อน | หลัง |
|---|---|---|
| C: ว่าง | **32.31 MB** | **6.33 GB** |
| npm cache | 6.90 GB (56,709 ไฟล์) | 0.65 GB (44,794 ไฟล์) |

คืนพื้นที่ได้ **6.30 GB** ด้วย `npm cache clean --force`

### ยืนยันว่าไม่ได้แตะสิ่งที่ห้าม

| สิ่งที่ห้ามลบ | สถานะ |
|---|---|
| Source code | ครบ — `webapi/api/` ยัง 10 ไฟล์ |
| `node_modules` ของโปรเจกต์ | ยังอยู่ |
| Docker images / containers / volumes | ไม่แตะ — `docker_data.vhdx` ยัง 21.86 GB เท่าเดิม |
| ไฟล์ส่วนตัว (Roblox, CapCut, Android ฯลฯ) | ไม่แตะ |

npm cache อยู่ที่ `C:\Users\User\AppData\Local\npm-cache` แยกจาก `node_modules` ของทุกโปรเจกต์โดยสิ้นเชิง และ npm สร้างใหม่เองเมื่อ install ครั้งถัดไป

### ยังต้อง restart Docker Desktop อีกชั้น

ล้าง cache แล้วแต่ engine ยังตอบ `Docker Desktop is unable to start` — log ชี้ว่า VM ไม่ตอบ `_ping` มา 34 นาที คือค้างตั้งแต่ตอนดิสก์เต็ม ไม่ฟื้นเอง

แก้ด้วยการปิดโปรเสส Docker Desktop ทั้งหมด (13 โปรเสส) → `wsl --shutdown` → เปิดใหม่ จากนั้น engine ขึ้นปกติ

> ตอนนั้นไม่มี container หรือ image ใดทำงานอยู่ในเครื่อง local การปิดจึงไม่ทำให้เสียอะไร

---

## 2. Docker Engine

```
$ docker version
Server 29.0.1 · linux/amd64
```

Image ที่มีในเครื่อง local ก่อน build — **ไม่มีชื่อ `course-advisor-system-*` เลย** จึงเป็นไปไม่ได้ที่จะ build ทับ production image

```
adminer:latest · busybox:latest · hello-world:latest · my-backend-app:latest
ollama/ollama:latest · pgvector/pgvector:pg16 · python:3.11-slim
```

---

## 3. Build

```bash
cd webapi
docker build -t webapi-m3-localtest:dba865b .
```

ตั้ง tag เป็น `webapi-m3-localtest` ซึ่งคนละชื่อกับ production (`course-advisor-system-webapi`) โดยตั้งใจ

### ผลแต่ละขั้น

| ขั้น | ผล |
|---|---|
| `[1/6] FROM node:22-alpine` | ผ่าน |
| `[2/6] WORKDIR /app` | CACHED |
| `[3/6] COPY package.json package-lock.json ./` | CACHED |
| `[4/6] RUN npm ci --omit=dev` | CACHED |
| `[5/6] COPY api ./api` | **ผ่าน** ← ขั้นที่เคยล้มแน่นอนถ้าไม่มี source |
| `[6/6] COPY server.mjs auth.mjs db.mjs ./` | ผ่าน |
| exporting | ผ่าน — manifest `sha256:a14d79bd…b7ef4a` |

---

## 4. ตรวจของใน image

### ไฟล์ที่ root ของ `/app`

```
api/                  (โฟลเดอร์)
auth.mjs              29,042 ไบต์
db.mjs                14,403 ไบต์
server.mjs            15,815 ไบต์
package.json             345 ไบต์
package-lock.json     31,378 ไบต์
node_modules/         (จาก npm ci)
```

ครบทั้ง `server.mjs`, `auth.mjs`, `db.mjs` ตามที่ Dockerfile ระบุ

### `api/` ใน image

ครบ **10 ไฟล์** ตรงรายการเดียวกับ production ทุกไฟล์

```
/app/api/_lib/adminAuth.js      /app/api/admin/extract-file.js
/app/api/_lib/aiConfig.js       /app/api/admin/ingest.js
/app/api/_lib/fileExtract.js    /app/api/admin/sync-sci-news.js
/app/api/_lib/ingest.js         /app/api/sci-connect-news.js
/app/api/_lib/rag.js            /app/api/sci-connect-news-detail.js
```

### hash ภายใน image

```
2b67e0f4a9dc9fd9f47231d93eaff12903d962d0e8d430f3347dbe52cafa8fcd
```

**ตรงกับ source บน production ทุกไบต์** — ยืนยันว่าสิ่งที่อยู่ใน image คือโค้ดจริง ไม่ใช่ stub และไม่ถูกดัดแปลงระหว่างทาง

### สิ่งที่ต้องไม่อยู่ใน image

| รายการ | ผล |
|---|---|
| `*.test.mjs` | **ไม่มี** ถูกต้องตามเจตนา |
| `pg` | มี รุ่น **8.23.1** ตรงกับที่ตรึงใน lock file |

---

## 5. ทดสอบ import ภายใน image

```
ผ่าน   ./api/sci-connect-news-detail.js
ผ่าน   ./api/sci-connect-news.js
ผ่าน   ./api/admin/extract-file.js
ผ่าน   ./api/admin/ingest.js
ผ่าน   ./api/admin/sync-sci-news.js
ผ่าน   ./auth.mjs
ผ่าน   ./db.mjs

โหลดครบ 7/7
```

ทุก handler มี `export default.fetch` เป็น function ตามสัญญาที่ `server.mjs` คาดหวัง

---

## 6. ทดสอบรัน container จริง

รัน container จาก image ที่ build แล้วเรียก `/healthz` ภายใน

```json
{
  "status": "ok",
  "authConfigured": true,
  "dbConfigured": false,
  "db": "not-configured",
  "routes": [
    { "route": "/api/sci-connect-news-detail", "level": "PUBLIC" },
    { "route": "/api/sci-connect-news",        "level": "PUBLIC" },
    { "route": "/api/admin/extract-file",      "level": "EDITOR" },
    { "route": "/api/admin/ingest",            "level": "EDITOR" },
    { "route": "/api/admin/sync-sci-news",     "level": "EDITOR" }
  ]
}
```

### สิ่งที่ผลนี้พิสูจน์

| ข้อ | หลักฐาน |
|---|---|
| บริการเริ่มทำงานได้จริง ไม่ใช่แค่ build ผ่าน | `status: "ok"` |
| ด่านตรวจสิทธิ์ทำงาน | `authConfigured: true` และทุกเส้นทางมี `level` กำกับ |
| ระดับสิทธิ์ถูกต้อง | ข่าว 2 เส้นทาง = `PUBLIC` · งานหลังบ้าน 3 เส้นทาง = `EDITOR` |
| **ไม่ล้มเมื่อไม่มีฐานข้อมูล** | `dbConfigured: false`, `db: "not-configured"` แต่ `status` ยัง `ok` — ตรงตามที่ออกแบบไว้ว่า Docker HEALTHCHECK ต้องไม่ขึ้นกับฐานข้อมูล |

### log ตอนบูต

```
[webapi] พร้อมให้บริการ /api/sci-connect-news-detail (PUBLIC)
[webapi] พร้อมให้บริการ /api/sci-connect-news (PUBLIC)
[webapi] พร้อมให้บริการ /api/admin/extract-file (EDITOR)
[webapi] พร้อมให้บริการ /api/admin/ingest (EDITOR)
[webapi] พร้อมให้บริการ /api/admin/sync-sci-news (EDITOR)
[webapi] ไม่พบค่าตั้งค่าฐานข้อมูล — แปลงตัวตนผู้เขียนไม่ได้ (เส้นทางสาธารณะยังทำงานปกติ)
[webapi] ฟังที่พอร์ต 3001 · 5 เส้นทาง
```

**ไม่มีรหัสผ่านหรือคีย์โผล่ใน log** — ค่าที่ใช้ทดสอบเป็นค่าสมมติสำหรับ container ในเครื่องเท่านั้น (`https://local-test.invalid`) ไม่ใช่ค่าจริงของ production

ลบ container ทดสอบทิ้งหลังตรวจเสร็จ

---

## 7. Regression Tests

```
ℹ tests 82
ℹ pass 82
ℹ fail 0
```

---

## 8. สิ่งที่ยังค้าง

### ต้องทำก่อน deploy — ต้องให้เจ้าของสั่ง

| # | งาน | หมายเหตุ |
|---|---|---|
| 1 | `docker tag course-advisor-system-webapi:latest …:rollback-pre-m3` บน production | เป็นการเขียนสถานะ docker บนเครื่องจริง · webapi มี tag `latest` ตัวเดียว ไม่มีอะไรให้ย้อนกลับถ้าไม่ติดก่อน |
| 2 | เตรียมบัญชี admin สถานะ `approved` | ข้อเดียวที่พิสูจน์ว่า authorization foundation ไม่ล็อกผู้ดูแลออก |
| 3 | สร้าง `ADVISOR_WEB_PASSWORD` ใส่ production `.env` | ขั้น deploy |
| 4 | คัดลอก `package-lock.json` ขึ้นเซิร์ฟเวอร์ | เซิร์ฟเวอร์ยังไม่มี และ `npm ci` บังคับต้องมี ถ้าลืม build จะล้ม |
| 5 | ยืนยันว่าสคริปต์ deploy จริงไม่ลบ `webapi/api/` ทิ้ง | README มีขั้นตอนแล้ว เหลือตรวจตัวสคริปต์ |

### ระยะยาว

- เปลี่ยน UUID ใน `webapi/auth.test.mjs:480` เป็นค่าสังเคราะห์
- เขียน `docs/DEPLOY_WEB.md` หรือลบการอ้างอิงใน `docker-compose.prod.yml:169`
- เพิ่ม `.dockerignore` — ตอนนี้ `node_modules/` ถูกส่งเข้า build context ทั้งก้อน
- ถอด `requireAdminUser` ออกจาก handler เมื่อมั่นใจด่านกลาง (ตอนนี้ `/api/admin/*` เรียก Supabase สองรอบต่อคำขอ)
- พิจารณาย้าย Docker disk image ไป D: — C: ยังเหลือแค่ 6.33 GB และ `docker_data.vhdx` กินอยู่ 21.86 GB

---

## 9. ยืนยันขอบเขต

| ข้อห้าม | สถานะ |
|---|---|
| แตะ production | **ไม่มี** — รอบนี้ไม่ได้ ssh เข้าเครื่อง production เลย |
| Deploy / Restart production | **ไม่มี** |
| แก้ production `.env` | **ไม่มี** |
| เขียน production database / Supabase | **ไม่มี** |
| Push / Merge | **ไม่มี** |
| Build ทับ production image | **ไม่มี** — ใช้ tag `webapi-m3-localtest` คนละชื่อ และเครื่อง local ไม่มี image ของ production อยู่เลย |
| ลบ source / node_modules / images / containers / volumes / ไฟล์ส่วนตัว | **ไม่มี** — ลบเฉพาะ npm cache ตามที่อนุมัติ |
| นำ `webapi/api/` เข้า git | **ไม่** — `.gitignore:49` ยังครอบอยู่ |
