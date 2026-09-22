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
