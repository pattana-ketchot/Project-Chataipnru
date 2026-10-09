# M3 — WebAPI Missing Source Recovery

> **Production READ-ONLY** — ไม่แก้หรือลบไฟล์ production, ไม่ deploy, ไม่ restart, ไม่ build ทับ image, ไม่แก้ `.env`, ไม่เขียนฐานข้อมูล, ไม่เขียน Supabase, ไม่ commit/push/merge, ไม่แตะ frontend repository

## ผลสรุป

# `M3_SOURCE_RECOVERY_BLOCKED`

**การกู้คืนสำเร็จครบถ้วนทุกขั้นทางเทคนิค** ไฟล์ทั้ง 10 ถูกสำรองออกมาแล้ว ตรวจแล้วว่าตรงกับต้นฉบับทุกไบต์ ไม่มีความลับ เป็นโค้ดจริง โหลดได้ และ regression ผ่าน 82/82

**แต่บล็อกที่ขั้นนำเข้า Git** เพราะพบว่า `webapi/api/` **ถูกยกเว้นจากรีโปนี้โดยเจตนาตั้งแต่ต้น** พร้อมเอกสารกำกับ — ไม่ใช่ของที่หายไปโดยอุบัติเหตุ การ commit เข้ามาจะขัดกับข้อตกลงเรื่องความเป็นเจ้าของโค้ดที่บันทึกไว้แล้ว จึงต้องให้เจ้าของตัดสินใจก่อน

---

## ⚠️ ต้องแก้ข้อสรุปของ Preflight ก่อน

รายงาน `M3_PRODUCTION_ROLLOUT_PREFLIGHT.md` ข้อ 5 สรุปว่า `webapi/api/` **ไม่ได้ถูก gitignore** — **ข้อสรุปนั้นผิด**

สาเหตุ: ตอน preflight ผมรัน `git check-ignore -v webapi/api` ขณะที่**โฟลเดอร์ยังไม่มีอยู่จริง** กฎใน `.gitignore` คือ `webapi/api/` ซึ่งมี `/` ปิดท้าย จึงตรงกับ "ไดเรกทอรี" เท่านั้น เมื่อไม่มีไดเรกทอรีให้ตรวจ คำสั่งจึงไม่คืนอะไร และผมอ่านผลว่าง ๆ นั้นว่า "ไม่ถูก ignore"

พอคัดลอกไฟล์ลงมาจริงแล้วตรวจซ้ำ:

```
$ git check-ignore -v webapi/api/_lib/rag.js
.gitignore:49:webapi/api/	webapi/api/_lib/rag.js
```

**บทเรียน:** `git check-ignore` กับ path ที่ยังไม่มีอยู่ ให้คำตอบที่เชื่อไม่ได้เมื่อกฎเป็นแบบปิดท้ายด้วย `/` — ต้องตรวจกับไฟล์จริง

ข้อสรุปอื่น ๆ ของ preflight ยังถูกต้องทั้งหมด

---

## สิ่งที่ค้นพบ — เป็นการตัดสินใจที่มีเอกสาร ไม่ใช่ความผิดพลาด

### `.gitignore` บรรทัด 48–49

```gitignore
# โค้ดฝั่ง API ของหน้าเว็บที่ทีมออกแบบดูแล อยู่คนละรีโปและคนละเจ้าของ
# ตอน deploy ต้องคัดลอกมาวางเองก่อน build (ดู webapi/README.md)
webapi/api/
```

เข้ามาตั้งแต่ commit `589cff5` *"feat: เพิ่มบริการ webapi สำหรับข่าวและงานหลังบ้านของหน้าเว็บ"* คือตั้งแต่วันที่สร้างบริการนี้

### `webapi/README.md` — **อยู่ใน git อยู่แล้ว** และมีขั้นตอนครบ

README ที่ถูก track อยู่แล้วระบุไว้ชัดเจน:

- **เหตุผล** — "โฟลเดอร์ `api/` ไม่ได้อยู่ในรีโปนี้โดยตั้งใจ เพราะเป็นโค้ดของทีมที่ดูแลหน้าเว็บ (อยู่คนละรีโปและคนละเจ้าของ) จึงไม่นำมาเก็บซ้ำโดยไม่ได้ตกลงกัน"
- **ขั้นตอนคัดลอกก่อน build** พร้อมคำสั่ง `cp` ครบทุกบรรทัด
- **รายการ 10 ไฟล์ที่ต้องมีครบ** — ตรงกับที่กู้คืนมาได้ทุกไฟล์
- **ไฟล์ที่ห้ามคัดลอก** — `api/chat.js`, `api/compare-courses.js`, `api/recommend-major.js`
- **ตัวแปรสภาพแวดล้อม** ที่ต้องมี
- **ลำดับบล็อกใน Caddyfile** ที่ห้ามสลับ

**ดังนั้นขั้นตอน deploy ของ `api/` ไม่ได้หายไปจากรีโป** — มีบันทึกไว้ครบใน README ที่ commit ไปแล้ว สิ่งที่ขาดจริง ๆ มีอย่างเดียวคือ **สำเนาสำรองนอกเครื่อง production** ซึ่งรอบนี้ทำเสร็จแล้ว

---

## 1. รายการไฟล์ใน Production

| # | ไฟล์ | บรรทัด | ไบต์ |
|---|---|---|---|
| 1 | `api/_lib/adminAuth.js` | 41 | 1,850 |
| 2 | `api/_lib/aiConfig.js` | 36 | 1,150 |
| 3 | `api/_lib/fileExtract.js` | 34 | 1,096 |
| 4 | `api/_lib/ingest.js` | 71 | 2,177 |
| 5 | `api/_lib/rag.js` | 85 | 4,690 |
| 6 | `api/admin/extract-file.js` | 42 | 1,416 |
| 7 | `api/admin/ingest.js` | 29 | 1,029 |
| 8 | `api/admin/sync-sci-news.js` | 37 | 1,359 |
| 9 | `api/sci-connect-news-detail.js` | 53 | 1,949 |
| 10 | `api/sci-connect-news.js` | 50 | 1,832 |
| | **รวม** | **478** | **18,548** |

โครงสร้าง: ไฟล์ 10 · โฟลเดอร์ 3 · **symlink 0** · ขนาดรวมทั้งโฟลเดอร์ 30,836 ไบต์

ครบตรงกับรายการ 10 ไฟล์ที่ `webapi/README.md` ระบุไว้ ไม่ขาดไม่เกิน และ**ไม่มี** `chat.js` / `compare-courses.js` / `recommend-major.js` ที่ README ห้ามคัดลอก

---

## 2–3. การสำรองและการตรวจความครบถ้วน

คัดลอกด้วย `scp -r` จาก production ลงพื้นที่กักกันก่อน ไม่เขียนอะไรกลับขึ้นเซิร์ฟเวอร์

### SHA256 ทั้ง 10 ไฟล์

| ไฟล์ | SHA256 |
|---|---|
| `_lib/adminAuth.js` | `ac929f4867384c0e8e259123d73266f44b65f475676142a44771b0524a311696` |
| `_lib/aiConfig.js` | `40ef93d649073a0ea44c40a97ad608c5272cd80543f5b1373c6e9238a489b122` |
| `_lib/fileExtract.js` | `4b9eef03cb50d1549407557985b66d26b19770d96d74233408ad478af42139d7` |
| `_lib/ingest.js` | `58b22b91467e08abcdf3ca913b44a582fbc4397ef91cfefcf04dc38f7ce5e14d` |
| `_lib/rag.js` | `f2f69619d435e9666facbdd6ddc9d9040892730fd75a98cefd1fba82f400e621` |
| `admin/extract-file.js` | `6f8f95033392d57ba64f201f2898528300ad66b3908fa493a4b14955cc0a425e` |
| `admin/ingest.js` | `6495ba9b7262f8b2995a3af870626a453b05173adc9f7efcf626e143841f1378` |
| `admin/sync-sci-news.js` | `61b2c07eae62e653fd77100784dba30d4c8b9bbf65ec029872f77dfdde396f97` |
| `sci-connect-news-detail.js` | `3278fc40a88fab06c63f0b06758fcb6efe945484abd6b3abfc68bf5e2258eca3` |
| `sci-connect-news.js` | `b062c08bee69bf9506ad81271d36eaf16c719233651647840ec7494839235acd` |

**ตรงกันทุกไฟล์ระหว่าง production → พื้นที่กักกัน → `webapi/api/` ในรีโป → ไฟล์สำรอง → ผลกู้คืนจากไฟล์สำรอง**

ตรวจด้วย hash รวมของค่า hash ทั้ง 10 เรียงต่อกัน ได้ `2b67e0f4a9dc9fd9f47231d93eaff12903d962d0e8d430f3347dbe52cafa8fcd` เท่ากันทั้งบน production และในรีโป local

> หมายเหตุ: ถ้าคำนวณ hash รวมจาก **output ดิบ** ของ `sha256sum` ค่าจะไม่ตรงกันระหว่าง Windows กับ Linux เพราะ `sha256sum` บน Windows ใส่ `*` นำหน้าชื่อไฟล์ (binary mode) แต่ Linux ใส่ช่องว่างสองตัว — เป็นความต่างของรูปแบบข้อความ ไม่ใช่ของเนื้อไฟล์ การเทียบข้างบนจึงตัดชื่อไฟล์ออกแล้วเทียบเฉพาะค่า hash

เนื่องจาก hash ตรง แปลว่า **ไม่มีการแปลง CRLF ระหว่างทาง** ไฟล์ยังเป็น LF เหมือนบน production

### ไฟล์สำรองถาวร

```
D:/workspace/webapi-api-backup-20261009T204112.tar.gz   (6,242 ไบต์)
```

วางไว้**นอกรีโป** โดยตั้งใจ เพื่อไม่ให้ปนกับไฟล์ที่ถูก gitignore และทดสอบกู้คืนแล้วว่าได้ไฟล์ครบ 10 ตัว hash ตรงทุกไฟล์

---

## 4. การสแกนความลับและข้อมูลส่วนบุคคล

| สิ่งที่สแกน | ผล |
|---|---|
| JWT (`eyJ…`), `sk-…`, `AIza…`, `ghp_…`, `xox[baprs]-`, PRIVATE KEY | **ไม่พบ** |
| ค่าคงที่ที่ดูเหมือนความลับ (`password`/`secret`/`token`/`api_key` = string literal) | **ไม่พบ** |
| Connection string ที่มีรหัสผ่านฝัง | **ไม่พบ** |
| อีเมล / เบอร์โทร / เลขบัตรประชาชน 13 หลัก | **ไม่พบ** |
| URL ที่ hardcode | **ไม่พบ** |
| ไฟล์ `.env*`, `*.pem`, `*.key`, `*secret*`, `*credential*` | **ไม่พบ** |

ความลับทั้งหมดมาจาก environment variable อย่างเดียว ไม่มีค่าฝังในโค้ด:

| ตัวแปร | ไฟล์ที่อ่าน |
|---|---|
| `VITE_SUPABASE_URL` | `sci-connect-news.js`, `sci-connect-news-detail.js`, `_lib/adminAuth.js`, `_lib/aiConfig.js`, `_lib/rag.js` |
| `VITE_SUPABASE_ANON_KEY` | ไฟล์เดียวกันทั้ง 5 |

ทั้งสองตัวมีอยู่ใน production `.env` แล้ว และ anon key เป็นคีย์สาธารณะโดยการออกแบบของ Supabase (ความปลอดภัยมาจาก RLS ไม่ใช่จากการซ่อนคีย์)

> `GOOGLE_GENERATIVE_AI_API_KEY` ที่ compose ส่งเข้า webapi **ไม่ถูกอ่านตรง ๆ ใน `api/`** — `_lib/rag.js` ใช้ `@ai-sdk/google` ซึ่งอ่าน env นี้เองภายในไลบรารี

---

## 5. ตรวจว่าเป็น production handler จริง ไม่ใช่ stub

| หลักฐาน | ผล |
|---|---|
| ขนาดรวม | 478 บรรทัด / 18.5 KB — ไม่ใช่ไฟล์เปล่า |
| สัญญาของ handler ทั้ง 5 | `export default { async fetch(request) }` ครบทุกไฟล์ |
| ตรรกะจริง | `_lib/adminAuth.js` ตรวจ `ADMIN_ROLES = ['admin','editor']` + `status === 'approved'` เต็มรูปแบบ |
| ค่าคงที่ที่สมเหตุสมผล | `fileExtract.js` จำกัด 15 MB, นามสกุล `pdf/docx/txt/md` · `ingest.js` chunk 800 overlap 100 · `rag.js` โมเดล `gemini-embedding-001` มิติ 768 · `aiConfig.js` cache TTL 30 วินาที |
| ไม่มี TODO/FIXME/stub marker | ตรวจแล้วไม่พบ |

เป็นโค้ดที่ใช้งานจริงบน production ขณะนี้ และเป็นตัวที่ตอบ HTTP 200 / 401 ที่ยิงทดสอบไว้ใน preflight

---

## 6. Dependency และ import path ทำงานกับ M3 `server.mjs` ได้

### ไลบรารีภายนอกที่ `api/` ต้องใช้

| แพ็กเกจ | ใน `package.json` | ติดตั้งจริง | ตรึงใน lock |
|---|---|---|---|
| `@supabase/supabase-js` | `^2.112.3` | 2.117.0 | ใช่ |
| `pdf-parse` | `^2.4.5` | 2.4.5 | 2.4.5 |
| `mammoth` | `^1.12.2` | 1.12.3 | ใช่ |
| `@ai-sdk/google` | `^4.0.51` | 4.0.77 | ใช่ |
| `ai` | `^7.0.79` | 7.0.111 | ใช่ |

ครบทั้ง 5 ตัว ไม่ต้องเพิ่ม dependency ใด ๆ — `pg` ที่ M3 เพิ่มเข้ามาเป็นของ `db.mjs` ไม่เกี่ยวกับ `api/`

### import ภายใน

```
admin/extract-file.js   -> ../_lib/fileExtract.js, ../_lib/adminAuth.js
admin/ingest.js         -> ../_lib/ingest.js,      ../_lib/adminAuth.js
admin/sync-sci-news.js  -> ../_lib/adminAuth.js
_lib/ingest.js          -> ./rag.js
```

ทุกเส้นทางอยู่ในโฟลเดอร์ `api/` ที่กู้คืนมา ไม่มี import ที่ชี้ออกนอกโฟลเดอร์

### ผลทดสอบ import จริง

โหลดทั้ง 5 เส้นทางตามที่ `server.mjs` ประกาศในตารางเส้นทาง:

```
ผ่าน  ./api/sci-connect-news-detail.js  export default.fetch = function
ผ่าน  ./api/sci-connect-news.js         export default.fetch = function
ผ่าน  ./api/admin/extract-file.js       export default.fetch = function
ผ่าน  ./api/admin/ingest.js             export default.fetch = function
ผ่าน  ./api/admin/sync-sci-news.js      export default.fetch = function

โหลดครบ 5/5
```

ตรวจแล้วว่าไม่มี side effect ตอน import — top-level ของทุกไฟล์มีแค่ `import` กับการประกาศค่าคงที่ การอ่าน `process.env` อยู่ในฟังก์ชันทั้งหมด

---

## 7. การเรียกใช้ Supabase

| ไฟล์ | Auth | Database (Supabase) | Edge Function | Storage |
|---|---|---|---|---|
| `_lib/adminAuth.js` | `.auth.getUser` | `user_profiles` | — | — |
| `_lib/aiConfig.js` | — | `ai_settings` | — | — |
| `_lib/ingest.js` | — | `rag_documents` | — | — |
| `sci-connect-news.js` | — | `external_news` | — | — |
| `sci-connect-news-detail.js` | — | `external_news` | — | — |
| `admin/sync-sci-news.js` | — | — | `functions/v1/sync-sci-news` | — |
| `_lib/rag.js` | — | — | — | — |
| `_lib/fileExtract.js` | — | — | — | — |
| `admin/extract-file.js` | — | — | — | — |
| `admin/ingest.js` | — | — | — | — |

**ไม่มีการใช้ Supabase Storage เลย**

### จุดสำคัญ — `api/` ไม่แตะ PostgreSQL ของเรา

ตรวจแล้วไม่พบ `require('pg')`, `from 'pg'`, การ import `db.mjs` หรือ `auth.mjs`, คำว่า `advisor_web` หรือ `WEBAPI_DB*` ในโฟลเดอร์ `api/` เลยแม้แต่ที่เดียว

ตรงกับที่ `webapi/README.md` เขียนไว้ว่า *"บริการนี้ไม่ได้ต่อฐานข้อมูล PostgreSQL ของเราเลย มันคุยกับ Supabase ของทีมออกแบบอย่างเดียว"*

**ผลต่อ M3:** การเพิ่ม `db.mjs` ไม่กระทบพฤติกรรมของ 5 เส้นทางนี้เลย ทั้งสองส่วนแยกขาดจากกัน — `api/` ใช้ Supabase, `db.mjs` ใช้ PostgreSQL และยังไม่มี endpoint ไหนเรียก `db.mjs` จริง

ข้อสังเกตที่สืบเนื่องจาก preflight ข้อ 6.3: `_lib/adminAuth.js` เรียก `.auth.getUser` + อ่าน `user_profiles` เองหนึ่งรอบ เมื่อด่านกลางของ `auth.mjs` ทำเหมือนกันอีกรอบ จึงเป็นสองรอบต่อคำขอตามที่รายงานไว้ — ยืนยันจากโค้ดจริงแล้ว

---

## 8. การนำเข้า local repository

คัดลอกเข้า `webapi/api/` แล้ว ตรวจ hash ซ้ำในตำแหน่งใหม่ — ตรงทั้ง 10 ไฟล์

**git ไม่เห็นไฟล์เหล่านี้** เพราะถูก `.gitignore` ครอบไว้:

```
$ git status --porcelain webapi/
(ว่าง)

$ git status --porcelain --ignored webapi/
!! webapi/api/
!! webapi/node_modules/
```

สถานะนี้ **ถูกต้องตามที่ README ออกแบบไว้** — ไฟล์ต้องอยู่ในเครื่องเพื่อให้ build ได้ แต่ไม่เข้า git

---

## 9. ทดสอบ Node imports และ Docker build

| การทดสอบ | ผล |
|---|---|
| Node imports ทั้ง 5 handler | **ผ่าน 5/5** |
| ไลบรารีครบ | **ผ่าน 5/5** |
| Docker build | **ยังไม่ได้ทำ — Docker Desktop ไม่ได้เปิด** |

```
failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine
```

### สิ่งที่ตรวจแทนได้โดยไม่ต้อง build

| `COPY` ใน Dockerfile | มีครบใน build context ไหม |
|---|---|
| `COPY package.json package-lock.json ./` | ครบ 2 ไฟล์ |
| `COPY api ./api` | ครบ 10 ไฟล์ (ก่อนหน้านี้ไม่มีเลย = build ล้มแน่) |
| `COPY server.mjs auth.mjs db.mjs ./` | ครบ 3 ไฟล์ |

`*.test.mjs` ทั้ง 3 ไฟล์ไม่ถูกคัดลอกเข้า image ตามเจตนา

> ยังไม่มี `.dockerignore` — `node_modules/` ในเครื่องจะถูกส่งเข้า build context ทำให้ build ช้าโดยไม่จำเป็น แม้ `npm ci` จะเขียนทับในภายหลังก็ตาม ไม่ใช่ปัญหาด้านความถูกต้องแต่ควรเพิ่มไว้

**ต้องรัน `docker build` จริงก่อนประกาศว่า build ได้** — ขอ Docker Desktop แล้วจะทำให้ โดยใช้ tag ทดสอบแยก ไม่ทับ image ของ production

---

## 10. Regression tests

```
ℹ tests 82
ℹ pass 82
ℹ fail 0
```

**82/82 ผ่าน** เท่ากับก่อนนำ `api/` เข้ามา — การกู้คืนไม่กระทบชุดทดสอบเดิม

---

## 11. ยืนยันว่าไม่มี `.env` หรือความลับถูกคัดลอกมา

| การตรวจ | ผล |
|---|---|
| ไฟล์ `.env*`, `*.pem`, `*.key`, `*.p12` ใน `webapi/api/` | **0 ไฟล์** |
| จำนวนไฟล์ทั้งหมดใน `webapi/api/` | **10** (ตรงกับที่สำรองมา ไม่มีของแถม) |
| สิ่งที่ git เห็นเพิ่มใน `webapi/` | **ไม่มี** |

ไม่ได้คัดลอก `.env` ของ production ลงมาเลย และไม่ได้อ่านค่าในนั้นด้วย — ที่อ่านตอน preflight คือ**ชื่อคีย์เท่านั้น**

---

## สิ่งที่ต้องให้เจ้าของตัดสินใจ

ตัวเลือกสำหรับ `webapi/api/` โดยเรียงจากที่สอดคล้องกับข้อตกลงเดิมมากที่สุด:

| # | ทางเลือก | ข้อดี | ข้อเสีย |
|---|---|---|---|
| **A** | **คงสถานะ gitignore ไว้** ใช้ไฟล์สำรอง `.tar.gz` เป็นหลักประกัน และระบุใน README ว่าสำเนาสำรองอยู่ที่ไหน | เคารพความเป็นเจ้าของโค้ด ไม่ต้องคุยกับทีมออกแบบ ปลดบล็อก rollout ได้ทันที | ยังไม่มี version control ของไฟล์ชุดนี้ ถ้าทีมออกแบบแก้แล้วเราไม่รู้ |
| B | ขออนุญาตทีมออกแบบแล้วนำเข้า git | ได้ประวัติการเปลี่ยนแปลง build ซ้ำได้จากรีโปเดียว | ต้องรอการอนุมัติจากคนนอก และโค้ดซ้ำสองที่ |
| C | ใช้ git submodule ชี้ไปรีโปของทีมออกแบบ | ได้ทั้งความเป็นเจ้าของและการตรึงเวอร์ชัน | ต้องเข้าถึงรีโปนั้นได้ และเพิ่มความซับซ้อนให้ขั้นตอน deploy |

**คำแนะนำ: ทางเลือก A** เพราะปัญหาที่แท้จริงที่ preflight เจอคือ *"ไม่มีสำเนาสำรองนอกเครื่อง production"* ไม่ใช่ *"ไม่ได้อยู่ใน git"* — เมื่อมีไฟล์สำรองแล้วความเสี่ยงที่ไฟล์หายถาวรก็หมดไป โดยไม่ต้องละเมิดข้อตกลงที่ทีมตั้งไว้ตั้งแต่ commit แรกของบริการนี้

ถ้าเลือก A สิ่งที่ควรทำเพิ่มคือเติมหนึ่งย่อหน้าใน `webapi/README.md` ว่าสำเนาสำรองล่าสุดอยู่ที่ไหนและลงวันที่ใด — **อันนั้นเป็นการแก้ไฟล์ที่ต้อง commit จึงต้องขออนุมัติแยก**

---

## ผลต่อ Preflight

| ข้อใน preflight | สถานะใหม่ |
|---|---|
| ข้อสรุปว่า "ไม่ได้ถูก gitignore" | **ผิด — แก้แล้วในเอกสารนี้** |
| "ไม่มีสำเนาสำรองนอก production" | **แก้แล้ว** — `webapi-api-backup-20261009T204112.tar.gz` |
| "build จากรีโปล้วน ๆ ล้ม" | ยังจริง และ**เป็นพฤติกรรมที่ตั้งใจ** ตาม README ต้องคัดลอก `api/` มาก่อน build เสมอ |
| "วิธี deploy ที่แทนที่ทั้งโฟลเดอร์จะทำลายไฟล์" | ยังจริง และสำคัญกว่าเดิม เพราะตอนนี้ยืนยันแล้วว่าไฟล์ไม่ได้อยู่ใน git |
| เงื่อนไขปลดบล็อกข้อ 1 (สำรองไฟล์) | **เสร็จแล้ว** |
| เงื่อนไขปลดบล็อกข้อ 2 (ตัดสินใจเรื่องที่มา) | **รอเจ้าของเลือก A / B / C** |
| เงื่อนไขข้อ 3, 4, 5 | ยังค้างเหมือนเดิม |

---

## สถานะ Git

```
HEAD      dba865b  feat(webapi): connect to PostgreSQL for Supabase identity resolution (M3)
Branch    mko-phase2  (ahead of origin/mko-phase2 by 6)
Modified  0
Untracked 64   (เพิ่มเอกสารฉบับนี้ ส่วน webapi/api/ ถูก ignore จึงไม่นับ)
```

**ไม่มีการ commit, push หรือ merge** ตามข้อกำหนด

---

## ขั้นตอนถัดไปที่รออนุมัติ

1. รัน `docker build` จริงด้วย tag ทดสอบ (ต้องเปิด Docker Desktop) — ไม่ทับ image production
2. เลือกทางเลือก A / B / C สำหรับ `webapi/api/`
3. ถ้าเลือก A: แก้ `webapi/README.md` เพิ่มตำแหน่งไฟล์สำรอง แล้ว commit
4. Commit เอกสาร `M3_WEBAPI_SOURCE_RECOVERY_RESULT.md` และแก้ข้อ 5 ของ `M3_PRODUCTION_ROLLOUT_PREFLIGHT.md`
