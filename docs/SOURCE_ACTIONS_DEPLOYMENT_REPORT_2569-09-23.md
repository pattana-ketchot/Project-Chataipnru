# Deployment Report — Source Headers + AnswerActions + Responsive

- **วันที่:** 23 กันยายน 2569
- **ผล:** Phase 1 และ Phase 2 **ผ่านทั้งหมด ไม่มี rollback**
- **สถานะ:** deploy แล้ว · **ยังไม่ commit และยังไม่ push ทั้งสอง repo** ตามที่สั่ง

---

## 1. Pre-deploy

| รายการ | ค่า |
|---|---|
| image เดิม | `dbb3eba5fa6f` (สร้าง 21 ก.ย. 2569) |
| restarts ก่อน deploy | 0 |
| `web_compat.py` — local HEAD (589cff5) | `56ee1da26b1ea430…` |
| `web_compat.py` — บนเครื่องเซิร์ฟเวอร์ | `56ee1da26b1ea430…` |
| `web_compat.py` — ในคอนเทนเนอร์ | `56ee1da26b1ea430…` |
| **สรุป drift** | **ไม่มี** — production ตรงกับ HEAD ทุกไบต์ |
| `.env` / compose / Caddyfile sha | `ddd6c441c303171f` / `d76afeef4ec1383d` / `da2e26fd948d2a71` |
| counts ก่อน deploy | `courses=24 · course_documents=31 · course_chunks=9039 · v_live_values=103 · v_live_list_items=156` |
| health | 200 |

### Backup

```
~/backups/source_headers_20260923T045009Z/
  env.backup · docker-compose.prod.yml · Caddyfile
  web_compat.py.before · manifest.before (67 ไฟล์)
  web.before/ (38 ไฟล์) · web.manifest.before
```

- rollback image tag: **`course-advisor-system-backend:rollback-589cff5`** → `dbb3eba5fa6f`
- บันทึกตำแหน่ง backup ไว้ที่ `~/LAST_SOURCE_HEADER_BACKUP`

### Baseline ก่อน deploy (เก็บไว้เทียบ body)

| คำถาม | bytes | sha | header |
|---|---|---|---|
| "เรียนวิทยาการคอมพิวเตอร์จบแล้วทำงานอะไรได้บ้าง" | 1363 | `a756a5a649d089e2` | Document + Page |
| "สวัสดีครับ" | 485 | `0f8706c4bf2ebc71` | ไม่มี |

---

## 2. Phase 1 — Backend

### วิธี deploy

1. สร้าง release package จาก working tree ด้วยรายชื่อไฟล์ของ git (`git ls-files backend llm`)
   บังคับ LF — แปลง CRLF **8,838 จุด** เป็น LF
2. package: 65 ไฟล์ · 158,744 bytes · sha `1dccd782ed521397…`
   → อัปโหลดแล้วตรวจ sha ตรงทั้ง sha และขนาด
3. แตกไฟล์แล้วเทียบ manifest — **เปลี่ยนไฟล์เดียว**
   `web_compat.py` `56ee1da2…` → `0baf8b69…` ที่เหลือ 66 ไฟล์เหมือนเดิมทุกไบต์
4. `docker compose build backend` → `up -d --no-deps backend` (รันแบบ detached + log)
   **ไม่ได้ scp ทับ source แล้ว restart เฉย ๆ — build image ใหม่จริง**

### ผลหลัง deploy

| รายการ | ค่า |
|---|---|
| image ใหม่ | **`638bc49d5aee`** (เดิม `dbb3eba5fa6f`) |
| `web_compat.py` ในคอนเทนเนอร์ | `0baf8b694e2e82c9…` ✅ ตรงกับที่ตั้งใจ |
| `X-Source-Title` อยู่ในคอนเทนเนอร์ | ✅ |
| restarts | 0 |
| `.env` / compose / Caddyfile sha | **ไม่เปลี่ยน** ทั้งสามค่า |
| counts หลัง deploy | `24 · 31 · 9039 · 103 · 156` — **เท่าเดิมทุกตัว** |
| error/traceback ใน log | 0 |
| ทุกบริการ | backend · caddy · frontend · ollama · postgres · webapi = running |

### Smoke test บน production จริง

**คำถามที่มี source และ resolve สาขาได้**

```
POST https://stpnru-advisor.duckdns.org/api/chat
X-Source-Document : 7e06cd12-87ee-49ab-9687-c5dc51114474
X-Source-Page     : 3
X-Source-Title    : Y3M2Ni5wZGY=                 -> cs66.pdf
X-Source-Programme: 4Lir4Lil4Lix4LiB…            -> หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาการคอมพิวเตอร์ (พ.ศ. 2566)
body: 1363 bytes  sha a756a5a649d089e2
```

- **body เหมือน baseline ทุกไบต์** (1363 / `a756a5a6…` เท่ากันเป๊ะ) → streaming และเนื้อความไม่เสีย
- base64 ถอดกลับเป็นภาษาไทยได้ครบ และ**ตรงกับชื่อในฐานข้อมูลทุกตัวอักษร**
- resolve ต่อได้เป็น courseId `20c3ca9c-…` + PNRU `id=10`

**คำถามที่มี source แต่ไม่มี mapping**

```
X-Source-Document : 5cb797f1-5ea1-4cc7-a352-e35fce2ab38c
X-Source-Page     : 1
X-Source-Title    : ds2564.pdf
X-Source-Programme: หลักสูตรศิลปศาสตรบัณฑิต สาขาวิชาคหกรรมศาสตร์ (พ.ศ. 2564)
```

ชื่อนี้ไม่อยู่ใน `programmeLinks.js` → หน้าเว็บจะไม่ขึ้นปุ่มสาขา **ถูกต้องตามที่ออกแบบ**

**คำถามทั่วไป** — `สวัสดีครับ` → 485 bytes `0f8706c4bf2ebc71` **เท่า baseline** · header 0 ตัว

### PDF endpoint

| document | ผล |
|---|---|
| `7e06cd12-…` | 200 · `application/pdf` · `inline; filename="cs66.pdf"` · `accept-ranges: bytes` |
| `5cb797f1-…` | 200 · `application/pdf` · `inline; filename="ds2564.pdf"` · `accept-ranges: bytes` |

`accept-ranges` ทำให้ `#page=N` กระโดดหน้าได้

### API regression

| endpoint | ผล |
|---|---|
| `POST /api/compare-courses` | **200** · 8.1s · 5,074 bytes |
| `POST /api/recommend-major` | **200** · 16.5s · 1,498 bytes |
| `GET /api/course-facts` | **200** · 1,217 bytes |
| `GET /api/sci-connect-news` | **200** · 2,197 bytes |

> `/api/recommend-major` ใช้ 16.5 วินาที ขณะที่ตอนทดสอบในเครื่องได้ 3.5 วินาที
> เป็นความแกว่งของเวลาตอบจากโมเดล ไม่ใช่ error — ได้ 200 และข้อมูลครบ
> แต่บันทึกไว้เพราะเป็นตัวเลขที่ต่างจากผล local อย่างชัดเจน

**Phase 1 ผ่านครบ ไม่ต้อง rollback → ไปต่อ Phase 2**

---

## 3. Phase 2 — Frontend

### วิธี deploy

- `/srv/web` เป็น bind mount แบบอ่านอย่างเดียวจาก `~/course-advisor-system/web`
  จึง deploy ด้วยการวางไฟล์ที่โฮสต์ ไม่ต้องแตะคอนเทนเนอร์ Caddy
- สำรอง `web/` เดิม 38 ไฟล์ + manifest ไว้ก่อน
- package dist: 19 ไฟล์ · 1,514,106 bytes · sha `b6d60c1422bd1d7d…` (CRLF 0 จุด)
  อัปโหลดแล้ว sha ตรง
- **overlay ไม่ลบของเดิม** → 38 → 40 ไฟล์

| เปลี่ยน | ไฟล์ |
|---|---|
| แทนที่ | `web/index.html` |
| เพิ่ม | `web/assets/index-Bs9VOUpB.js`, `web/assets/index-Bm7bH-b4.css` |
| **คงไว้** | bundle เดิม `index-CCD6GRgQ.js` ยังอยู่ → rollback = คืน `index.html` ไฟล์เดียว |

### ผลบน production

| รายการ | ค่า |
|---|---|
| bundle ที่เสิร์ฟจริง | `index-Bs9VOUpB.js` (683,363 bytes) + `index-Bm7bH-b4.css` (48,270 bytes) |
| assets | 200 ทั้งคู่ |
| SPA routes | `/` `/chat` `/courses` `/compare` `/sci-connect` `/admin/login` = 200 ทั้งหมด |

### Flow แชทจริงบน production (390px)

| ปุ่ม | href | target/rel | ขนาด |
|---|---|---|---|
| 📄 ดูเอกสารหลักสูตร · cs66.pdf · หน้า 3 | `/api/documents/7e06cd12-…/pdf#page=3` | `_blank` / `noopener noreferrer` | 222×54 |
| 🎓 ดูรายละเอียดสาขา · วิทยาการคอมพิวเตอร์ | `/courses/20c3ca9c-…` | ไม่เปิดแท็บใหม่ (ถูกต้อง) | 222×54 |
| 🌐 เว็บไซต์สาขา PNRU | `https://sci.pnru.ac.th/program_detail.php?id=10` | `_blank` / `noopener noreferrer` | 222×44 |
| 🏫 เว็บไซต์คณะ | `https://sci.pnru.ac.th` | `_blank` / `noopener noreferrer` | 222×44 |

ทุกปุ่ม ≥44px · ไม่มีปุ่มที่ไม่มีข้อมูลจริง · `hscroll = 0`

### Responsive บน production

| Viewport | หน้า | ผล |
|---|---|---|
| 360 | Compare Result | ไม่มีตาราง เป็นการ์ดเรียงลง · hscroll 0 · breaks 0 · ช่องกรอก <16px = 0 · ตัวอักษร <12px = 0 |
| 360 | Chat | ปุ่ม 4 อัน 1 คอลัมน์ ≥44px |
| 390 | Chat | ปุ่ม 222×44–54 · hscroll 0 |
| 430 | Course Detail | แท็บซ่อน 55px + **มีเงาบอก 1 จุด** · hscroll 0 |
| 768 | Compare Result | ตาราง 703px ในกล่อง 703px → **cutOff 0** |
| 820 | Compare Result / Find Major | hscroll 0 · ตารางไม่โดนตัด |
| 1024 | Courses | hscroll 0 |
| 1280 | Home | เมนูเต็ม ไม่มี hamburger · hscroll 0 |

> ที่ 1024 ช่อง select ของหน้า Courses ยังเป็น 14px — **ถูกต้องตามที่ออกแบบ**
> กฎบังคับ 16px ตั้งไว้เฉพาะต่ำกว่า 640px เพราะอาการ iOS ซูมเองเกิดบนมือถือเท่านั้น
> ที่ 360px หน้าเดียวกันวัดได้ช่องกรอกต่ำกว่า 16px = 0

---

## 4. Git status — ยังไม่ commit ตามที่สั่ง

### `course-advisor-system-mko2` (branch `mko-phase2`)

```
commit ที่ production ใช้เป็นฐาน : 589cff5
 M backend/app/api/routes/web_compat.py   (+44 −1)   <-- deploy แล้ว
 M eval/chat_source_header_check.py       (+87 −5)   <-- ไม่ได้ deploy (เป็นเทสต์)
```

### `LastProject` (branch `prep-step8`)

```
 M  22 ไฟล์ (responsive + ChatAdvisor)
 ?? src/components/AnswerActions.jsx
 ?? src/data/programmeLinks.js
 ?? TECH_STACK.md  (ไม่เกี่ยวกับงานนี้)
```

**production รันโค้ดที่ยังไม่ถูก commit อยู่ตอนนี้** — ตั้งใจตามคำสั่ง แต่ต้องรู้ไว้ว่า
ถ้ายังไม่ commit แล้วมีคน deploy ทับจาก `589cff5` การแก้นี้จะหายไป

---

## 5. Rollback status — **ไม่ได้ใช้** แต่พร้อมใช้

| ส่วน | วิธีย้อนกลับ | เวลาที่ใช้ |
|---|---|---|
| Backend | `docker tag course-advisor-system-backend:rollback-589cff5 course-advisor-system-backend:latest` แล้ว `up -d --no-deps backend` | ~30 วินาที |
| Backend source | `cp ~/backups/source_headers_20260923T045009Z/web_compat.py.before backend/app/api/routes/web_compat.py` | ทันที |
| Frontend | `cp ~/backups/source_headers_20260923T045009Z/web.before/index.html web/index.html` (bundle เดิมยังอยู่) | ทันที |
| Config | `.env` / compose / Caddyfile **ไม่ได้แก้เลย** แต่มีสำเนาไว้แล้ว | — |

---

## 6. ต่างจากผล local หรือไม่

ตรวจทุกข้อที่ทดสอบในเครื่องแล้วเทียบกับ production — **ตรงกันทั้งหมด ยกเว้นเรื่องเดียว**

| ข้อ | local | production | ตรงกันไหม |
|---|---|---|---|
| header ครบ 4 ตัวเมื่อมี source | ✅ | ✅ | ตรง |
| base64 ถอดเป็นไทยได้ | ✅ | ✅ | ตรง |
| ไม่มี mapping → ไม่ขึ้นปุ่มสาขา | ✅ | ✅ | ตรง |
| ไม่มี source → ไม่มีกล่อง | ✅ | ✅ | ตรง |
| body ไม่เปลี่ยน | ✅ (unit test) | ✅ (sha เท่า baseline) | ตรง |
| PDF เปิดได้ | ✅ | ✅ | ตรง |
| ปุ่มไปถูกปลายทาง | ✅ | ✅ | ตรง |
| responsive ทุก viewport | ✅ | ✅ | ตรง |
| **เวลาตอบของ `/api/recommend-major`** | **3.5s** | **16.5s** | **ต่าง** |

เรื่องเดียวที่ต่างคือเวลาตอบของ `recommend-major` ซึ่งเป็นความแกว่งของโมเดล
ไม่ใช่ error (ได้ 200 และข้อมูลครบ) **ไม่ได้แก้อะไรเพิ่มเอง** รายงานไว้ให้ตรวจ

---

## 7. สรุป

- Phase 1 ผ่าน → Phase 2 ผ่าน → **ไม่มี rollback**
- ทั้งสอง phase ไม่แตะ PostgreSQL schema/data, Supabase, Caddy routing, RAG, Gemini, scoring
  (ยืนยันด้วย counts เท่าเดิมทุกตัว และ config sha ไม่เปลี่ยน)
- **หยุดก่อน commit/push ตามที่สั่ง** รอการอนุมัติ
