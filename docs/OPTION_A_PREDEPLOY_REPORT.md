# ทางเลือก A — รายงานก่อน deploy (หยุดรออนุมัติ)

วันที่ 2026-09-23 · **ยังไม่มีการเปลี่ยนแปลงใด ๆ บนเซิร์ฟเวอร์** · ยังไม่ build ยังไม่ทับ `/srv/web`

---

## 1. สำรองข้อมูลเรียบร้อยแล้ว — อยู่ที่ไหน

```
/home/ubuntu/backups/optionA_20260922T211050Z/
```

เส้นทางนี้บันทึกไว้ที่ `~/LAST_OPTIONA_BACKUP` ด้วย (อ่านด้วย `cat ~/LAST_OPTIONA_BACKUP`)

| สิ่งที่สำรอง | รายละเอียด | ตรวจแล้ว |
|---|---|---|
| `web/` (หน้าเว็บที่ใช้งานจริง) | สำเนาทั้งโฟลเดอร์ **35 ไฟล์** | ✅ เทียบ sha256 ทีละไฟล์ **ตรงครบ 35/35** |
| `docker-compose.prod.yml` | sha `d55a4cadebaf…` | ✅ |
| `Caddyfile` | sha `2922ff4b3c2e…` | ✅ |
| `.env` | สำเนาพร้อมตั้งสิทธิ์ 600 | ✅ |
| `state.txt` | บันทึกสถานะคอนเทนเนอร์ · image · commit · health · ชื่อ bundle ที่ live | ✅ |
| `web.manifest` | รายการ sha256 ของทุกไฟล์ต้นฉบับ | ✅ 35 บรรทัด |

ขนาดรวม 7.0 MB · **ไม่มีการลบหรือย้ายไฟล์ต้นฉบับ** `~/course-advisor-system/web` ยังอยู่ครบทุกไฟล์

**สถานะระบบ ณ เวลาที่สำรอง**

```
backend image   sha256:dbb3eba5fa6f…  (commit 705b425)
bundle ที่ live  assets/index-gw896RX9.js
health          public = 200
คอนเทนเนอร์      backend · postgres · ollama · caddy · frontend · db-viewer  ทำงานปกติทั้งหมด
```

---

## 2. ตรวจแล้วว่า Node API ของเพื่อนเชื่อม Supabase ได้จริง

ทดสอบในเครื่อง โดย **ไม่แก้โค้ดของเพื่อนแม้แต่บรรทัดเดียว** — เขียนเพียงตัวครอบที่แปลงคำขอของ Node
ให้เป็น `Request` มาตรฐาน แล้วส่งเข้าฟังก์ชันเดิมซึ่งเขียนไว้เป็น `export default { fetch(Request) }`

| เส้นทาง | วิธีทดสอบ | ผล |
|---|---|---|
| `GET /api/sci-connect-news?limit=3` | เรียกจริง | **HTTP 200** · ได้ข่าวจริง 3 รายการ (2,197 ไบต์) |
| `GET /api/sci-connect-news-detail?slug=<ของจริง>` | ใช้ slug จากข่าวจริง | **HTTP 200** · ได้ `title · published_date · image_url · description · facebook_url` |
| `GET /api/sci-connect-news-detail?slug=<ไม่มีจริง>` | ทดสอบกรณีไม่พบ | **HTTP 404** พร้อมข้อความภาษาไทย ถูกต้อง |
| `POST /api/admin/extract-file` (ไม่มี token) | ทดสอบด่านสิทธิ์ | **HTTP 401** ถูกต้อง |
| `POST /api/admin/ingest` (ไม่มี token) | ทดสอบด่านสิทธิ์ | **HTTP 401** ถูกต้อง |
| `POST /api/admin/sync-sci-news` (ไม่มี token) | ทดสอบด่านสิทธิ์ | **HTTP 401** ถูกต้อง |
| `POST /api/chat` | ยิงเข้าบริการ Node | **HTTP 404** — บริการนี้ไม่รับ ปล่อยให้ FastAPI ตอบ ✅ |
| `GET /healthz` | ตรวจสุขภาพ | `{"status":"ok","routes":[… 5 เส้นทาง]}` |

ข่าวจริงที่ดึงได้ — "นโยบายผู้บริหารคณะวิทยาศาสตร์และเทคโนโลยี ปีการศึกษา 2569" (15 ก.ย. 2569),
"SCI Connect ฉบับที่ 28" (13 ก.ย. 2569), "ขอแสดงความยินดีกับผู้ได้รับตำแหน่ง…" (11 ก.ย. 2569)

ไลบรารีที่ต้องใช้โหลดได้ครบ: `@supabase/supabase-js` · `mammoth` · `pdf-parse` · `@ai-sdk/google` · `ai` · `zod`

### ⚠️ พบปัญหา 1 อย่างที่ต้องตัดสินใจ

`api/admin/ingest.js` ต้องใช้คีย์ **`GOOGLE_GENERATIVE_AI_API_KEY`** สำหรับสร้างเวกเตอร์ของคลังความรู้
ตรวจไฟล์ `.env` ของ LastProject แล้วพบว่าช่องนี้ **ว่างเปล่า** (เช่นเดียวกับ `AI_API_KEY`, `AI_MODEL`, `AI_BASE_URL`)
แปลว่าคีย์จริงเก็บอยู่ในค่าตั้งของ Vercel ไม่ได้อยู่ในไฟล์นี้

| เส้นทาง | ใช้งานได้ไหมถ้าไม่มีคีย์ |
|---|---|
| `/api/sci-connect-news` · `-detail` | ✅ ได้ ใช้แค่ค่า Supabase |
| `/api/admin/sync-sci-news` | ✅ ได้ ใช้แค่ค่า Supabase |
| `/api/admin/extract-file` | ✅ ได้ ใช้แค่ `mammoth` กับ `pdf-parse` ไม่ต้องใช้คีย์ |
| **`/api/admin/ingest`** | ❌ **ไม่ได้** ต้องขอคีย์จากเพื่อน (ดูในหน้าตั้งค่าของ Vercel) |

**ทางเลือก** ขอคีย์จากเพื่อนมาใส่ หรือ deploy ไปก่อนโดยเส้นทางนี้จะตอบข้อผิดพลาดจนกว่าจะใส่คีย์
(ส่วนอื่นไม่กระทบ) — ต้องการให้ทำแบบไหนบอกได้

---

## 3. เส้นทางไหนไป Node เส้นทางไหนอยู่ที่ FastAPI

### ไป Node (บริการใหม่ `webapi`) — 5 เส้นทางเท่านั้น

```
GET   /api/sci-connect-news
GET   /api/sci-connect-news-detail
POST  /api/admin/extract-file
POST  /api/admin/ingest
POST  /api/admin/sync-sci-news
```

### อยู่ที่ FastAPI เหมือนเดิมทุกประการ — ไม่แตะ

```
POST  /api/chat              →  /chat-web      แชท RAG + Structured Metadata + header ที่มา
POST  /api/compare-courses   →  /compare-courses
POST  /api/recommend-major   →  /recommend-major
GET   /api/course-facts      →  /course-facts
GET   /api/documents/{id}/pdf →  /documents/{id}/pdf    เปิดเอกสารต้นฉบับ
GET   /api/health            →  /health
        และ /api/* อื่น ๆ ทั้งหมด
```

**ยืนยันตามที่สั่ง** — RAG · Structured Metadata · Source/PDF · PostgreSQL/pgvector · Gemini · Ollama
**ไม่มีการเปลี่ยนแปลงใด ๆ** ทั้งโค้ด ทั้งเส้นทาง ทั้งฐานข้อมูล บริการ Node ใหม่ไม่แตะฐานข้อมูลของเราเลย
มันคุยกับ Supabase อย่างเดียว

> ทดสอบยืนยันแล้วว่าบริการ Node ตอบ **404** เมื่อถูกยิงด้วย `/api/chat`
> จึงเป็นไปไม่ได้ที่มันจะไปแย่งตอบแทน FastAPI แม้ตั้ง Caddy ผิด

---

## 4. ไฟล์ที่แก้ไปแล้ว ณ ตอนนี้

### บนเซิร์ฟเวอร์

**ไม่มีเลย** — มีเพียงการ *สร้าง* โฟลเดอร์สำรองใหม่ และไฟล์ `~/LAST_OPTIONA_BACKUP`
ไม่มีการแก้ ลบ ย้าย หรือ restart อะไรทั้งสิ้น

### ในเครื่องพัฒนา

| ไฟล์ | สถานะ |
|---|---|
| `scratchpad/webapi/server.mjs` | **สร้างใหม่** — ตัวครอบ 100 บรรทัด |
| `scratchpad/webapi/Dockerfile` | **สร้างใหม่** |
| `scratchpad/webapi/package.json` | **สร้างใหม่** — เฉพาะไลบรารีที่ 5 เส้นทางต้องใช้ |
| `scratchpad/webapi/api/` | **สำเนา** จาก `LastProject/api` ไม่ได้แก้ |
| `D:\workspace\LastProject\_probe_supabase.mjs` | **สร้างใหม่ชั่วคราว** เพื่อทดสอบ — **ลบทิ้งได้ บอกมาแล้วผมลบให้** |
| `docs/OPTION_A_PREDEPLOY_REPORT.md` | ไฟล์รายงานนี้ |

**ไม่ได้แตะไฟล์เดิมของเพื่อนแม้แต่ไฟล์เดียว**

---

## 5. สิ่งที่จะ deploy ถ้าอนุมัติ

### 5.1 เพิ่มบริการใหม่ 1 ตัวใน `docker-compose.prod.yml`

```yaml
  # บริการเสริมสำหรับฟังก์ชันของหน้าเว็บที่ต้องรันฝั่งเซิร์ฟเวอร์
  # รับผิดชอบเฉพาะข่าว Sci Connect และงานหลังบ้าน ไม่เกี่ยวกับการตอบคำถามของระบบ
  webapi:
    build:
      context: ./webapi
    restart: unless-stopped
    environment:
      VITE_SUPABASE_URL: ${VITE_SUPABASE_URL}
      VITE_SUPABASE_ANON_KEY: ${VITE_SUPABASE_ANON_KEY}
      GOOGLE_GENERATIVE_AI_API_KEY: ${GOOGLE_GENERATIVE_AI_API_KEY:-}
    expose:
      - "3001"
```

**ไม่เปิดพอร์ตออกนอกเครื่อง** เข้าถึงได้เฉพาะผ่าน Caddy เหมือนที่ `backend` ทำอยู่

### 5.2 เพิ่ม 2 บล็อกใน `Caddyfile` — วางไว้ **ก่อน** `handle /api/*` เดิม

```caddy
	# ข่าว Sci Connect และงานหลังบ้าน — สองกลุ่มนี้เป็นของบริการ webapi
	# ต้องวางก่อน handle /api/* เพราะ Caddy เลือกบล็อกแรกที่ตรงเส้นทาง
	handle /api/sci-connect-news* {
		reverse_proxy webapi:3001
	}
	handle /api/admin/* {
		reverse_proxy webapi:3001
	}
```

**บล็อกเดิมทั้งหมดไม่ถูกแก้** — `handle /api/chat`, `handle /api/*`, `handle /assets/*`, `handle` ท้ายสุด คงเดิมทุกบรรทัด

### 5.3 เพิ่ม 3 บรรทัดใน `.env` บนเซิร์ฟเวอร์

```
VITE_SUPABASE_URL=...
VITE_SUPABASE_ANON_KEY=...
GOOGLE_GENERATIVE_AI_API_KEY=      # ว่างไว้ได้ ถ้ายังไม่ได้คีย์จากเพื่อน
```

ค่าที่เหลือใน `.env` ไม่ถูกแก้

### 5.4 อัปโหลดโฟลเดอร์ใหม่ `~/course-advisor-system/webapi/`

ประกอบด้วย `Dockerfile` · `server.mjs` · `package.json` · `api/` (โค้ดของเพื่อน 10 ไฟล์)

### 5.5 build หน้าเว็บของเพื่อนแล้ววางที่ `/srv/web` ← **ขั้นนี้ต้องรออนุมัติรอบสอง**

---

## 6. ลำดับการ deploy ที่ย้อนกลับได้ทุกขั้น

| ขั้น | ทำอะไร | ย้อนกลับด้วย | เว็บ live กระทบไหม |
|:---:|---|---|---|
| **1** | อัปโหลดโฟลเดอร์ `webapi/` ขึ้นเซิร์ฟเวอร์ | `rm -rf ~/course-advisor-system/webapi` | **ไม่กระทบ** |
| **2** | เพิ่ม 3 บรรทัดใน `.env` | คืนไฟล์จากโฟลเดอร์สำรอง | **ไม่กระทบ** |
| **3** | เพิ่มบริการ `webapi` ใน compose แล้ว `up -d webapi` (บริการเดียว) | `docker compose stop webapi && docker compose rm -f webapi` + คืน compose | **ไม่กระทบ** — Caddy ยังไม่รู้จักบริการนี้ |
| **4** | ทดสอบจากในเครือข่าย compose ว่า `webapi:3001/healthz` ตอบ | — | **ไม่กระทบ** |
| **5** | เพิ่ม 2 บล็อกใน `Caddyfile` แล้ว `docker compose restart caddy` | คืน Caddyfile จากสำรอง + restart caddy (~3 วินาที) | **กระทบชั่วขณะ** — caddy รีสตาร์ต |
| **6** | ทดสอบ `/api/sci-connect-news` ได้ข่าวจริง และ `/api/chat` ยังตอบจาก FastAPI | — | ไม่กระทบ |
| **7** | **หยุด รายงาน รออนุมัติ** | — | — |
| **8** | build หน้าเว็บของเพื่อน แล้ววางทับ `/srv/web` | `rm -rf web && cp -a <สำรอง>/web web` (~5 วินาที) | **เปลี่ยนหน้าเว็บจริง** |
| **9** | ทดสอบเส้นทางเดโมทั้งหมด | — | — |

**จุดที่เสี่ยงที่สุดคือขั้นที่ 8 เท่านั้น** และมีสำเนาครบ 35 ไฟล์รออยู่แล้ว

---

## 7. สิ่งที่ยังไม่ได้ตรวจ และต้องตรวจก่อนขั้นที่ 8

1. **หน้าเว็บของเพื่อน build ผ่านไหมในเครื่องนี้** (`npm run build` ใน LastProject) — ยังไม่ได้ลอง
2. **หน้าเว็บที่ build แล้วเรียก `/api/chat` แล้วได้คำตอบจาก FastAPI จริงไหม** — ต้องทดสอบก่อนวางทับ
3. **ฟีเจอร์ที่คุณเพิ่มเองในหน้าเว็บ** (ส่วนอธิบายเปอร์เซ็นต์ · การเรียก `/api/course-facts`) — ต้องย้ายเข้า
   LastProject ก่อน build ไม่งั้นของที่ live อยู่ตอนนี้จะหายไป (มี patch พร้อมแล้ว ทดสอบว่า apply สะอาด)
4. **โควตา Gemini** — การทดสอบเส้นทางแชทใช้โควตาจริง ควรจำกัดจำนวนครั้ง

---

## 8. สรุปสถานะ

```
สำรองข้อมูล              : เสร็จ ตรวจแล้วตรงทุกไบต์ 35/35 ไฟล์
ตรวจ Node + Supabase     : เสร็จ 5 เส้นทางทำงานได้ (ยกเว้น ingest ที่ขาดคีย์)
แยกเส้นทาง Node / FastAPI : ชัดเจน ยืนยันด้วยการทดสอบแล้ว
แก้ไขบนเซิร์ฟเวอร์        : ยังไม่มี
build ทับ /srv/web       : ยังไม่ทำ — หยุดรออนุมัติตามที่สั่ง
```

**รอการตัดสินใจจากคุณ 3 ข้อ**

1. อนุมัติให้ทำขั้นที่ 1–6 (เพิ่มบริการ Node + เส้นทาง Caddy) ได้เลยไหม — ขั้นเหล่านี้ไม่กระทบเว็บที่ใช้งานอยู่
2. เรื่องคีย์ `GOOGLE_GENERATIVE_AI_API_KEY` — จะขอจากเพื่อน หรือปล่อยให้ `/api/admin/ingest` ใช้ไม่ได้ไปก่อน
3. ไฟล์ทดสอบ `LastProject/_probe_supabase.mjs` ให้ลบทิ้งเลยไหม
