# webapi — บริการเสริมของหน้าเว็บ

บริการเล็กๆ ที่รับผิดชอบ **5 เส้นทางเท่านั้น** คือข่าว Sci Connect และงานหลังบ้านของหน้าเว็บ
ซึ่งเป็นงานที่ต้องรันฝั่งเซิร์ฟเวอร์แต่ไม่เกี่ยวกับการตอบคำถามของระบบ

```
GET   /api/sci-connect-news
GET   /api/sci-connect-news-detail
POST  /api/admin/extract-file
POST  /api/admin/ingest
POST  /api/admin/sync-sci-news
```

เส้นทางอื่นทั้งหมดยังเป็นของ `backend` (FastAPI) เหมือนเดิม โดยเฉพาะ
`/api/chat` · `/api/compare-courses` · `/api/recommend-major` · `/api/course-facts` ·
`/api/documents/{id}/pdf` — บริการนี้**ไม่ได้ต่อฐานข้อมูล PostgreSQL ของเราเลย**
มันคุยกับ Supabase ของทีมออกแบบอย่างเดียว

---

## ⚠️ ต้องนำโค้ดจากรีโปของทีมออกแบบมาใส่ก่อน build

**โฟลเดอร์ `api/` ไม่ได้อยู่ในรีโปนี้โดยตั้งใจ** เพราะเป็นโค้ดของทีมที่ดูแลหน้าเว็บ
(อยู่คนละรีโปและคนละเจ้าของ) จึงไม่นำมาเก็บซ้ำโดยไม่ได้ตกลงกัน — ดู `.gitignore` บรรทัด `webapi/api/`

**ก่อน build ต้องคัดลอก `api/` จากรีโปของหน้าเว็บมาวางที่ `webapi/api/` ก่อน**

```bash
# จากรีโปของทีมออกแบบ (เช่น LastProject)
cp -r <repo-หน้าเว็บ>/api/_lib                       webapi/api/_lib
cp -r <repo-หน้าเว็บ>/api/admin                      webapi/api/admin
cp    <repo-หน้าเว็บ>/api/sci-connect-news.js        webapi/api/
cp    <repo-หน้าเว็บ>/api/sci-connect-news-detail.js webapi/api/
```

**ห้ามคัดลอก** `api/chat.js` · `api/compare-courses.js` · `api/recommend-major.js`
สามไฟล์นั้นเป็นระบบตอบคำถามของอีกฝั่ง ซึ่ง FastAPI ของเราทำหน้าที่แทนแล้ว
ถ้าคัดลอกมาด้วยจะไม่มีผลทันที (ตัวครอบไม่ได้โหลด) แต่เป็นโค้ดซ้ำซ้อนที่ชวนสับสน

ไฟล์ที่ต้องมีครบ 10 ไฟล์

```
webapi/api/_lib/adminAuth.js      webapi/api/admin/extract-file.js
webapi/api/_lib/aiConfig.js       webapi/api/admin/ingest.js
webapi/api/_lib/fileExtract.js    webapi/api/admin/sync-sci-news.js
webapi/api/_lib/ingest.js         webapi/api/sci-connect-news.js
webapi/api/_lib/rag.js            webapi/api/sci-connect-news-detail.js
```

### ถ้าไม่มีรีโปของทีมออกแบบอยู่ในมือ — ใช้ไฟล์สำรอง

เนื่องจาก `api/` ไม่ได้อยู่ใน git ของเรา ถ้าเครื่องที่ build ไม่มีรีโปของทีมออกแบบ
จะ build ไม่ได้เลย จึงเก็บสำเนาสำรองของชุดที่รันอยู่บน production ไว้

| รายการ | ค่า |
|---|---|
| ไฟล์สำรอง | `D:/workspace/webapi-api-backup-20261009T204112.tar.gz` |
| ที่มา | `/home/ubuntu/course-advisor-system/webapi/api/` บนเครื่อง production |
| วันที่สำรอง | 9 ตุลาคม 2569 |
| จำนวนไฟล์ | 10 ไฟล์ · 3 โฟลเดอร์ · 0 symlink · 30,836 ไบต์ |
| SHA256 รวม | `2b67e0f4a9dc9fd9f47231d93eaff12903d962d0e8d430f3347dbe52cafa8fcd` |

**สำเนานี้เป็นของสำรองเพื่อกู้คืน ไม่ใช่แหล่งต้นทาง** แหล่งต้นทางยังเป็นรีโปของทีมออกแบบ
ถ้าทีมนั้นแก้โค้ด สำเนานี้จะเก่าทันที — ให้ใช้วิธี `cp` ข้างบนเป็นหลักเสมอ
และใช้ไฟล์สำรองเฉพาะตอนที่เข้าถึงรีโปต้นทางไม่ได้

```bash
# กู้คืนลงที่เดิม
tar -xzf webapi-api-backup-20261009T204112.tar.gz -C webapi/
```

### ตรวจ SHA256 ก่อน build ทุกครั้ง

ไม่ว่าจะคัดลอกจากรีโปต้นทางหรือกู้จากไฟล์สำรอง ให้ตรวจก่อน build เสมอ

```bash
cd webapi

# 1) ต้องได้ครบ 10 ไฟล์
find api -type f | wc -l

# 2) ต้องไม่มี symlink
find api -type l | wc -l            # ต้องได้ 0

# 3) hash รวม — เทียบกับค่าในตารางข้างบน
find api -type f -print0 | sort -z | xargs -0 sha256sum \
  | awk '{print $1}' | sha256sum
```

> ค่า hash รวมคำนวณจาก **ค่า hash ของแต่ละไฟล์เรียงตามชื่อ** ไม่ใช่จาก output ดิบของ
> `sha256sum` เพราะบน Windows คำสั่งนั้นใส่ `*` นำหน้าชื่อไฟล์แต่บน Linux ใส่ช่องว่าง
> ทำให้เทียบข้ามระบบปฏิบัติการไม่ได้ถ้าไม่ตัดชื่อไฟล์ออกก่อน
>
> ถ้า hash ไม่ตรง **ไม่ได้แปลว่าผิดเสมอไป** — อาจเป็นเพราะทีมออกแบบแก้โค้ดจริง
> ให้ตรวจว่าต่างตรงไหนก่อนตัดสินใจ อย่าเพิ่ง build ทับ

### ขั้นตอน build

```bash
# ยืนยันว่ามี api/ ครบแล้วค่อย build (ถ้าไม่มี COPY api ./api จะล้ม)
cd webapi && find api -type f | wc -l        # ต้องได้ 10

# build ด้วย tag ที่ระบุเวอร์ชัน ไม่ใช่ latest เปล่า ๆ
docker build -t course-advisor-system-webapi:$(git rev-parse --short HEAD) .
```

**ก่อน build ทับของที่ใช้งานอยู่ ให้ติด tag สำรองไว้ก่อนเสมอ** ไม่งั้นจะไม่มีอะไรให้ย้อนกลับ

```bash
docker tag course-advisor-system-webapi:latest course-advisor-system-webapi:rollback-pre-<ชื่องาน>
docker images | grep webapi          # ยืนยันว่า tag ติดแล้วจริง
```

---

## ตัวครอบทำอะไร

ฟังก์ชันในโฟลเดอร์ `api/` เขียนตามสัญญาแบบเว็บมาตรฐาน คือ

```js
export default { async fetch(request) { /* … */ return Response.json(...) } }
```

ซึ่งเดิมรันบนแพลตฟอร์มไร้เซิร์ฟเวอร์ `server.mjs` ทำหน้าที่แปลงคำขอของ Node
ให้เป็น `Request` มาตรฐานแล้วส่งเข้าฟังก์ชันเดิม **โดยไม่แก้ตัวฟังก์ชันแม้แต่บรรทัดเดียว**
ของเจ้าของเดิมยังเป็นของเจ้าของเดิมทุกอย่าง

เส้นทางที่ไม่อยู่ในรายการ 5 เส้นทางจะได้ `404` เสมอ จึงเป็นไปไม่ได้ที่บริการนี้
จะไปแย่งตอบแทน FastAPI แม้ตั้งค่า Caddy ผิด

---

## ตัวแปรสภาพแวดล้อมที่ต้องมี

| ตัวแปร | จำเป็นไหม | ใช้กับ |
|---|---|---|
| `VITE_SUPABASE_URL` | ✅ | ทุกเส้นทาง |
| `VITE_SUPABASE_ANON_KEY` | ✅ | ทุกเส้นทาง |
| `GOOGLE_GENERATIVE_AI_API_KEY` | ไม่บังคับ | เฉพาะ `/api/admin/ingest` (สร้างเวกเตอร์ของคลังความรู้) |

ถ้าไม่ตั้ง `GOOGLE_GENERATIVE_AI_API_KEY` เส้นทาง `/api/admin/ingest` จะใช้งานไม่ได้
ส่วนอีก 4 เส้นทางทำงานปกติ

---

## ตรวจสุขภาพ

```bash
curl http://webapi:3001/healthz
# {"status":"ok","routes":["/api/sci-connect-news", … ]}
```

---

## เส้นทางใน Caddy

สองบล็อกนี้ต้องอยู่ **ก่อน** `handle /api/*` ใน `Caddyfile` เสมอ
เพราะ Caddy เลือกบล็อกแรกที่ตรงกับเส้นทาง ถ้าวางทีหลังคำขอจะถูกส่งไป backend แล้วได้ 404

```caddy
handle /api/sci-connect-news* { reverse_proxy webapi:3001 }
handle /api/admin/*           { reverse_proxy webapi:3001 }
```
