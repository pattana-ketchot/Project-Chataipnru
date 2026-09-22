# แผนรวมสองระบบ — LastProject (Frontend/Supabase) × course-advisor-system (FastAPI/RAG/Metadata)

วันที่ตรวจ: 2026-09-22 · **READ-ONLY** — ยังไม่แก้ไฟล์ ไม่ commit ไม่ push ไม่ deploy
ตรวจจาก `D:\workspace\LastProject` · `D:\workspace\course-advisor-system` (main `b78b3f8`) ·
`D:\workspace\course-advisor-system-mko2` (mko-phase2 `705b425`) · production บน Oracle Cloud

---

## 🔴 พบก่อนอื่น — โฟลเดอร์ `ProjectPnru` หายไปจากเครื่องแล้ว

ต้นชั่วโมงนี้ผมอ่านไฟล์จาก `D:\workspace\ProjectPnru\ProjectPnru` ได้ปกติ ตอนนี้ **ไม่มีโฟลเดอร์นั้นแล้ว**
ค้นทั้งไดรฟ์ `D:\` และ `C:\Users\User` หา `FindMajorResult.jsx` เจอเพียงไฟล์เดียวคือของ LastProject (11,299 ไบต์)
ส่วนไฟล์ของ ProjectPnru (15,480 ไบต์) **ไม่เหลืออยู่บนดิสก์** — และไฟล์ชุดนั้นคือ 47 ไฟล์ที่ยังไม่เคย commit

### ผลกระทบ และสิ่งที่ยังกู้ได้

| สิ่งที่หาย | ยังกู้ได้จาก | สถานะ |
|---|---|---|
| ซอร์สโค้ดหน้าเว็บที่ใช้ deploy อยู่ | — | **หายถาวร** |
| หน้าเว็บที่ผู้ใช้เห็นตอนนี้ | `~/course-advisor-system/web/assets/index-gw896RX9.js` บนเซิร์ฟเวอร์ (643,791 ไบต์) | ✅ **ยังอยู่ เว็บไม่ล่ม** |
| ส่วนอธิบายเปอร์เซ็นต์ | `docs/find-major-score-explanation.patch` (4,825 ไบต์) | ✅ **กู้ได้ครบ** |
| การเรียก `/api/course-facts` ในหน้ารายละเอียด | อ่านย้อนจาก bundle ที่ deploy แล้ว | ✅ **กู้ได้ (มีโค้ดอยู่ในรายงานนี้)** |

**ข่าวดี:** ผมทดสอบแล้วว่า patch ส่วนอธิบายเปอร์เซ็นต์ **apply เข้ากับ `FindMajorResult.jsx` ของ LastProject ได้สะอาด**
(`git apply --check` → exit 0) จึงไม่ต้อง merge ด้วยมือ

**ข่าวร้าย:** ถ้ามีการแก้อื่นใน ProjectPnru ที่ผมไม่รู้ จะรู้ได้ทางเดียวคือเทียบกับ bundle ที่ deploy แล้ว
ผมตรวจ bundle นั้นแล้วพบร่องรอยของสิ่งที่ LastProject ไม่มีอยู่ **2 อย่างเท่านั้น** (ข้อ 7)

---

## 1. ควรใช้โปรเจกต์ไหนเป็นฐาน

| ส่วน | ใช้เป็นฐาน | เหตุผล |
|---|---|---|
| **Frontend** | **`LastProject`** | commit ครบ working tree สะอาด มี Admin + Sci Connect + Supabase ครบ และตอนนี้เป็น**ซอร์สหน้าเว็บชุดเดียวที่ยังเหลืออยู่** |
| **Backend AI** | **`course-advisor-system-mko2` (`mko-phase2` = `705b425`)** | คือโค้ดที่รัน production อยู่จริง มี Structured Metadata + Source header + PDF endpoint ครบ |
| **ฐานข้อมูลหลักสูตร/ข่าว/แอดมิน** | **Supabase ของ LastProject** | หน้าเว็บผูกกับมันทั้งหมด 16 จุด และเป็นที่เดียวที่มีข้อมูลหลักสูตรสำหรับแสดงผล |
| **ฐานข้อมูล RAG/เอกสาร** | **PostgreSQL + pgvector ของเรา** | มี 9,039 chunks · 4,129 หน้า · 787 หลักฐาน · metadata ที่ publish แล้ว |

> `course-advisor-system` (branch `main`, `b78b3f8`) **ไม่ใช้เป็นฐาน** — ตามหลัง `mko-phase2` อยู่ 14 commits
> ใช้เป็นแหล่งอ้างอิงเอกสารเก่าเท่านั้น

---

## 2. ต้องย้าย/แก้ไฟล์อะไรบ้าง

ทั้งหมดอยู่ฝั่ง `LastProject` — **ไม่ต้องแก้ backend แม้แต่ไฟล์เดียว**

| # | ไฟล์ | ทำอะไร |
|---|---|---|
| 1 | `api/chat.js` | เปลี่ยนจาก "เรียก OpenRouter เอง" → **proxy ไป FastAPI** |
| 2 | `api/compare-courses.js` | เปลี่ยนเป็น proxy ไป FastAPI |
| 3 | `api/recommend-major.js` | เปลี่ยนเป็น proxy ไป FastAPI |
| 4 | `api/course-facts.js` | **สร้างใหม่** — proxy ไป FastAPI (endpoint นี้ LastProject ยังไม่มี) |
| 5 | `src/pages/FindMajorResult.jsx` | apply `find-major-score-explanation.patch` |
| 6 | `src/pages/CourseDetail.jsx` | เพิ่มการดึง `/api/course-facts?title=…` มาเติมช่องว่าง |
| 7 | `.env` / Vercel env | เพิ่ม `ADVISOR_API_BASE` |
| 8 | `api/_lib/rag.js`, `api/_lib/aiConfig.js` | **ไม่ต้องแตะ** — ยังใช้กับ admin ingest ต่อไป |

**ไม่ต้องลบไฟล์ใดทิ้ง** — เขียนทับเนื้อในของ 3 ไฟล์แรกเท่านั้น วิธีนี้ปลอดภัยกว่าการลบไฟล์แล้วใช้
`vercel.json` rewrite เพราะ **Vercel เลือกไฟล์ใน `api/` ก่อน rewrite เสมอ** ถ้าลบไม่หมดจะได้ผลลัพธ์ปนกันแบบหาสาเหตุยาก

---

## 3. API endpoint ของ FastAPI ที่เกี่ยวข้องจริง

เส้นทางที่หน้าเว็บใช้ (ผ่าน Caddy ที่ `https://stpnru-advisor.duckdns.org`)

| หน้าเว็บเรียก | Caddy แปลงเป็น | FastAPI route | รับ | คืน |
|---|---|---|---|---|
| `POST /api/chat` | `/chat-web` | `web_compat.py:127` | `{messages:[{role,content}]}` | **text/plain stream** + header `X-Source-Document` / `X-Source-Page` |
| `POST /api/compare-courses` | `/compare-courses` | `web_compat.py:239` | `{courses:[{id,title}]}` (≥2) | `{summary, courses:[{courseId,bestFor,pros,cons}], verdict}` |
| `POST /api/recommend-major` | `/recommend-major` | `web_compat.py:290` | `{answers:{}, courses:[{id,title}]}` | `{primary:{courseId,matchScore,reason}, alternatives:[…≤2], summary, profileText}` |
| `GET /api/course-facts?title=…` | `/course-facts` | `web_compat.py:212` | query `title` | `{}` หรือ facts (หน่วยกิต ภาษา ค่าเทอม ชื่อปริญญา EN คำอธิบาย อาจารย์) |
| `GET /api/documents/{id}/pdf` | `/documents/{id}/pdf` | `documents.py:35` | UUID | PDF (`inline`, รองรับ Range) |

**Caddy แปลงเส้นทางแบบนี้** (`Caddyfile`)
```
handle /api/chat   { rewrite * /chat-web ; reverse_proxy backend:8000 }
handle /api/*      { uri strip_prefix /api ; reverse_proxy backend:8000 }
```

endpoint อื่นของ FastAPI (`/chat`, `/match`, `/compare`, `/recommend`, `/search`, `/auth/*`, `/users/*`)
ใช้บัญชีผู้ใช้และคนละสัญญา — **หน้าเว็บไม่ต้องเรียก**

---

## 4. `fetch()` ของ LastProject ตอนนี้วิ่งไปไหน

ทุกอันเป็น **path สัมพัทธ์** → ชี้ไปที่ Vercel Function ในโฟลเดอร์ `api/` ของตัวเอง

| ไฟล์ | เรียก | ปลายทางตอนนี้ | หลัง merge |
|---|---|---|---|
| `src/pages/ChatAdvisor.jsx:52` | `/api/chat` | `api/chat.js` → OpenRouter `gpt-4o-mini` + Supabase RAG | **→ FastAPI** |
| `src/pages/CompareResult.jsx:68` | `/api/compare-courses` | `api/compare-courses.js` → OpenRouter | **→ FastAPI** |
| `src/pages/FindMajorResult.jsx:58` | `/api/recommend-major` | `api/recommend-major.js` → OpenRouter | **→ FastAPI** |
| `src/components/SciConnectNews.jsx:13` | `/api/sci-connect-news` | `api/sci-connect-news.js` → Supabase | **คงเดิม** |
| `src/pages/SciConnectAll.jsx:12` | `/api/sci-connect-news?limit=15` | เหมือนบน | **คงเดิม** |
| `src/pages/SciConnectDetail.jsx:13` | `/api/sci-connect-news-detail?slug=` | เหมือนบน | **คงเดิม** |
| `src/pages/Admin/Dashboard.jsx:111` | `/api/admin/sync-sci-news` | `api/admin/sync-sci-news.js` | **คงเดิม** |
| `src/lib/extractFile.js:12` | `/api/admin/extract-file` | `api/admin/extract-file.js` (mammoth/pdf-parse) | **คงเดิม** |
| `src/lib/ragIngest.js:11` | `/api/admin/ingest` | `api/admin/ingest.js` → embed + Supabase | **คงเดิม** |

**สรุป: แตะแค่ 3 จาก 9 จุด** ที่เหลือเป็นงานของ Supabase/แอดมินล้วน

---

## 5. Supabase ถูกใช้กับอะไร และต้องเก็บส่วนไหน

ใช้ใน **27 ไฟล์** เรียก 7 ตาราง

| ตาราง | ใช้ที่ | เก็บไว้ | เหตุผล |
|---|---|---|---|
| `courses` (16 จุด) | `AllCourses` · `CourseDetail` · `CompareCourses` · `CompareResult` · `FindMajorResult` · `Careers` · `CourseCarousel` · `HomeQuickLinks` · Admin | ✅ **ต้องเก็บ** | เป็นรายการสาขาที่หน้าเว็บแสดง และเป็นตัวที่ส่งเข้า `courses:[…]` ให้ FastAPI จับคู่ด้วยชื่อ |
| `user_profiles` (10) | ระบบแอดมิน (login/register/approve) | ✅ เก็บ | FastAPI ไม่มีระบบแอดมิน |
| `news` (5) · `external_news` (2) | Sci Connect | ✅ เก็บ | ฟีเจอร์ที่ต้องการรักษาไว้ |
| `ai_settings` (4) | `/admin/ai-settings` | ⚠️ เก็บแต่**เลิกมีผลกับแชท** | หลัง merge แชทใช้ Gemini ของเรา การเปลี่ยนโมเดลตรงนี้จะมีผลเฉพาะ admin ingest |
| `rag_documents` (7) · `knowledge_articles` (7) | `/admin/knowledge`, ingest | ⚠️ เก็บแต่**ไม่ถูกใช้ตอบแชทอีก** | คลังความรู้ของเพื่อน ถ้าลบจะทำให้หน้า Admin พัง |

**จุดสำคัญที่ทำให้สองระบบเข้ากันได้:** FastAPI จับคู่สาขาด้วย **ชื่อ** (`match_by_title`, `normalise_title`)
ไม่ใช่รหัส เพราะ "ฐานข้อมูลสองฝั่งใช้รหัสคนละชุดกัน" — ออกแบบรองรับกรณีนี้ไว้แล้วตั้งแต่แรก
`courseId` ที่ FastAPI คืนกลับมาคือ **id ของ Supabase ที่หน้าเว็บส่งไป** ไม่ใช่ id ฝั่งเรา

---

## 6. ถ้าให้ Frontend บน Vercel เรียก FastAPI

### วิธีที่ปลอดภัยที่สุด: **proxy ฝั่งเซิร์ฟเวอร์ ไม่เรียกตรงจากเบราว์เซอร์**

เบราว์เซอร์ยิง `/api/chat` ที่โดเมน Vercel เหมือนเดิม → Vercel Function ยิงต่อไป FastAPI
**ไม่เกิด CORS เลย** เพราะเบราว์เซอร์เห็นเป็น same-origin ตลอด และ **ไม่ต้องแก้ backend**

```js
// api/chat.js — แทนที่เนื้อในเดิมทั้งหมด
const BASE = process.env.ADVISOR_API_BASE;   // https://stpnru-advisor.duckdns.org

export default {
  async fetch(request) {
    if (request.method !== 'POST') return new Response('Method Not Allowed', { status: 405 });
    const upstream = await fetch(`${BASE}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: await request.text(),
    });
    // ส่ง stream กลับตรงๆ พร้อมยกหัวข้อมูลที่หน้าเว็บอาจใช้ต่อ
    const headers = new Headers({ 'Content-Type': 'text/plain; charset=utf-8', 'Cache-Control': 'no-cache' });
    for (const h of ['X-Source-Document', 'X-Source-Page', 'X-RAG-Sources']) {
      const v = upstream.headers.get(h);
      if (v) headers.set(h, v);
    }
    return new Response(upstream.body, { status: upstream.status, headers });
  },
};
```

`compare-courses.js` / `recommend-major.js` ทำแบบเดียวกันแต่คืน JSON
`course-facts.js` เป็น GET ส่งต่อ query `title`

### ถ้ายืนยันจะเรียกตรงจากเบราว์เซอร์ (ไม่แนะนำ)

ต้องแก้ **2 ที่**
1. `.env` บนเซิร์ฟเวอร์: `CORS_ALLOW_ORIGINS` — ตอนนี้เป็น `["http://localhost:3000"]` เท่านั้น
   ต้องเพิ่มโดเมน Vercel แล้ว restart backend → **เป็นการแตะ production ซึ่งเลี่ยงได้**
2. หน้าเว็บ: เปลี่ยน 3 จุด `fetch()` ให้เติม base URL จาก `import.meta.env.VITE_ADVISOR_API`

### ข้อจำกัดที่ต้องรู้ไม่ว่าจะเลือกทางไหน

**ตัวจำกัดคำขอจะกลายเป็นก้อนเดียว** — `web_rate_limiter` จำกัด **20 คำขอ/นาที และ 200/ชั่วโมง ต่อ IP**
และอ่าน IP จากรายการท้ายสุดของ `X-Forwarded-For` ซึ่ง Caddy เติมเอง (ปลอมไม่ได้โดยตั้งใจ)
เมื่อ proxy ผ่าน Vercel ทุกคนจะนับรวมเป็น IP เดียว — เดโมไม่มีปัญหา แต่ถ้าเปิดใช้จริงหลายคนพร้อมกันจะชน
แก้ภายหลังได้ด้วยการปรับ `_IP_LIMITS` ใน `backend/app/api/deps.py:98` (นับเป็นการแก้ backend แยกรอบ)

**Vercel Hobby จำกัดเวลา function ~10 วินาที** — คำถาม RAG วัดจริงได้ 3.9 วินาที ผ่านสบาย
แต่ถ้า Gemini ช้าผิดปกติจะถูกตัด ควรตั้ง `maxDuration` ให้สูงสุดเท่าที่แพ็กเกจอนุญาต

---

## 7. Source / PDF / Structured Metadata — ต้องย้ายอะไรกลับเข้า LastProject

ตรวจจาก bundle ที่ deploy อยู่จริงแล้ว พบว่า ProjectPnru มีเกิน LastProject อยู่ **2 อย่าง**

### 7.1 ส่วนอธิบายการคำนวณเปอร์เซ็นต์ (มี patch พร้อมแล้ว)

```
docs/find-major-score-explanation.patch  →  src/pages/FindMajorResult.jsx
```
เพิ่มคอมโพเนนต์ `ScoreExplanation` (กดเปิด/ปิด) + import `Info`, `ChevronDown`
**ทดสอบแล้วว่า apply สะอาด** — ไม่ต้องแก้มือ

### 7.2 การเติมข้อมูลหลักสูตรจาก `/api/course-facts` ในหน้ารายละเอียด

โค้ดที่ถอดจาก bundle ที่ deploy อยู่ — ต้องใส่กลับเข้า `src/pages/CourseDetail.jsx`
(หลังโหลด `courses` จาก Supabase สำเร็จ)

```js
const [facts, setFacts] = useState({})
// …หลังจาก setCourse(data) สำเร็จ:
try {
  const r = await fetch(`/api/course-facts?title=${encodeURIComponent(data.title)}`)
  if (r.ok) setFacts(await r.json())
} catch { /* ไม่มีก็แสดงค่าจาก Supabase ตามเดิม */ }
```
แล้วเวลาแสดงผลให้ใช้ `facts.<key> ?? course.<key>` เพื่อให้ค่าจากเอกสาร มคอ.2 ทับค่าที่ว่างใน Supabase
(`program_facts()` คืน หน่วยกิต · ภาษาที่ใช้ · ค่าเทอม · รูปแบบการเรียน · ชื่อปริญญา EN,
`program_about()` คืน คำอธิบายสาขา · รายชื่ออาจารย์)

### 7.3 ยังไม่มีทั้งสองฝั่ง — ทำเพิ่มได้ถ้าต้องการ

| ฟีเจอร์ | สถานะ |
|---|---|
| ปุ่ม "เปิดเอกสารต้นฉบับ" จาก `X-Source-Document` | backend พร้อมแล้ว (deploy 21 ก.ย.) **แต่ยังไม่มีหน้าเว็บฝั่งไหนอ่าน** |
| ชิป "อ้างอิงจาก:" จาก `X-RAG-Sources` | **หน้าเว็บของเพื่อนรองรับอยู่แล้ว** (`ChatAdvisor.jsx:71`) แต่ FastAPI ยังไม่ส่ง header นี้ |

> ข้อสังเกต: เพื่อนคิดวิธีเดียวกับเราพอดี — ใส่ที่มาไว้ใน response header เพราะ body เป็น text stream
> ถ้าวันหลังให้ FastAPI ส่ง `X-RAG-Sources` เป็น base64 ของ `[{title, source_type, source_id}]`
> UI แสดงแหล่งอ้างอิงจะติดทันทีโดยไม่ต้องแก้หน้าเว็บ

---

## 8. `FindMajorResult.jsx` สองเวอร์ชันต่างกันตรงไหน

| | ProjectPnru (หายแล้ว) | LastProject |
|---|---|---|
| ขนาด | 15,480 ไบต์ | 11,299 ไบต์ |
| ส่วนอธิบายเปอร์เซ็นต์ | ✅ มี | ❌ ไม่มี |
| โครงสร้างอื่น | เหมือนกัน | เหมือนกัน |

**ความต่างทั้งหมดคือ patch ไฟล์เดียว** — ยืนยันด้วย `git apply --check` กับสำเนาของ LastProject แล้วได้ exit 0
แปลว่า ProjectPnru = LastProject + patch นี้ **ไม่มีฟีเจอร์อื่นซ่อนอยู่**

**วิธีรวมโดยไม่ทำฟีเจอร์หาย**
1. `git apply --check docs/find-major-score-explanation.patch` ก่อน (ไม่เขียนไฟล์)
2. apply จริง
3. เทียบข้อความในไฟล์ผลลัพธ์กับ bundle ที่ deploy อยู่ — ต้องเจอคำว่า "เปอร์เซ็นต์คำนวณอย่างไร?" ทั้งสองที่
4. `npm run build` แล้ว grep bundle ใหม่ว่ามีข้อความนั้น

---

## 9. Environment variables ที่ต้องตั้ง

### บน Vercel

| ตัวแปร | ค่า | ใช้ตอน | มีอยู่แล้วไหม |
|---|---|---|---|
| `VITE_SUPABASE_URL` | URL โปรเจกต์ Supabase | build + runtime | ✅ มี |
| `VITE_SUPABASE_ANON_KEY` | anon key | build + runtime | ✅ มี |
| **`ADVISOR_API_BASE`** | `https://stpnru-advisor.duckdns.org` | server เท่านั้น (proxy) | ❌ **ต้องเพิ่ม** |
| `AI_BASE_URL` · `AI_API_KEY` · `AI_MODEL` | OpenRouter | **admin ingest เท่านั้น** (แชทไม่ใช้แล้ว) | ✅ มี |
| `GOOGLE_GENERATIVE_AI_API_KEY` | Google AI | `@ai-sdk/google` ใช้ทำ embedding ของคลังความรู้ฝั่งแอดมิน | ✅ มี |

⚠️ `ADVISOR_API_BASE` **ห้ามขึ้นต้นด้วย `VITE_`** ไม่งั้นจะถูกฝังลงไฟล์ JS ที่ผู้ใช้โหลดได้

### บนเซิร์ฟเวอร์ Oracle (`~/course-advisor-system/.env`)

**ไม่ต้องแก้อะไรเลยถ้าใช้วิธี proxy** — `CORS_ALLOW_ORIGINS` ปัจจุบันคือ `["http://localhost:3000"]`
จะต้องแก้ก็ต่อเมื่อเลือกวิธีเรียกตรงจากเบราว์เซอร์

---

## 10. จุดที่สองระบบไม่ตรงกัน

ตรวจทีละฟิลด์แล้ว — **สัญญาหลักตรงกันทั้งหมด** เหลือความต่างเล็กน้อย 5 ข้อ

| # | จุด | ฝั่งเพื่อน | ฝั่งเรา | ผลกระทบ |
|---|---|---|---|---|
| 1 | ชื่อ endpoint | `/api/chat`, `/api/compare-courses`, `/api/recommend-major` | `/chat-web`, `/compare-courses`, `/recommend-major` | Caddy แปลงให้แล้ว — **ไม่ต้องแก้** |
| 2 | `recommend-major` response | `{primary, alternatives, summary}` | เหมือนกัน + `profileText` | ฟิลด์เกิน หน้าเว็บไม่อ่าน — **ไม่กระทบ** |
| 3 | `compare-courses` → `cons` | LLM คิดให้ 0–3 ข้อ | **คืน `[]` เสมอโดยตั้งใจ** (มคอ.2 ไม่เขียนข้อเสียตัวเอง) | หน้าเว็บมี `length > 0` ครอบไว้ → ไม่พัง แต่**หัวข้อ "ข้อควรพิจารณา" จะหายไป** |
| 4 | header ที่มาของคำตอบ | `X-RAG-Sources` (base64 JSON) | `X-Source-Document` / `X-Source-Page` | คนละชื่อ — ชิป "อ้างอิงจาก:" จะไม่ขึ้น (มี try/catch ครอบ ไม่ error) |
| 5 | จำนวนสาขาที่เปรียบเทียบ | ไม่จำกัดชัดเจน | `min_length=2` และเฉพาะสาขาที่มีเอกสาร | สาขาที่ Supabase มีแต่เราไม่มีเอกสาร จะถูกตัดออกพร้อมข้อความบอกใน `summary` |
| 6 | `recommend-major` เมื่อจับคู่ไม่ได้เลย | คืน JSON ปกติ | **HTTP 422** | `FindMajorResult.jsx` จับ `!response.ok` แล้วโยน error → **ต้องดูว่าข้อความ error อ่านรู้เรื่องไหม** |

ข้อ 3, 4, 6 คือสามจุดที่ต้องตาดูตอนทดสอบ — ไม่ใช่บั๊ก แต่เป็นพฤติกรรมที่เปลี่ยนไป

---

## 11. ขั้นตอน merge ที่ทดสอบและย้อนกลับได้ทุกขั้น

### หลักการความปลอดภัย

> **ไม่แตะเซิร์ฟเวอร์ Oracle เลยตลอดแผนนี้**
> `stpnru-advisor.duckdns.org` ยังทำงานเหมือนเดิมทุกวินาที เป็นตัวสำรองสำหรับพรีเสมอ
> งาน merge ทั้งหมดลงบน **Vercel preview URL** ซึ่งเป็นพื้นที่ใหม่ ไม่ทับของเดิม

### ขั้นตอน

| ขั้น | ทำอะไร | ทดสอบว่าผ่านเมื่อ | ย้อนกลับด้วย |
|---|---|---|---|
| **0** | `git checkout -b merge-fastapi` ใน LastProject + สำรองทั้งโฟลเดอร์เป็น zip | มี branch ใหม่ · zip เปิดได้ | `git checkout main` |
| **1** | กู้ฟีเจอร์ frontend: apply patch (7.1) + เพิ่ม course-facts ใน CourseDetail (7.2) | `npm run build` ผ่าน · grep bundle เจอ "เปอร์เซ็นต์คำนวณอย่างไร?" | `git checkout -- src/` |
| **2** | เปลี่ยน `api/chat.js` เป็น proxy + เพิ่ม `api/course-facts.js` | `npm run dev` → ถามในแชท ได้คำตอบพร้อมบรรทัด "ที่มา:" | `git checkout -- api/chat.js` |
| **3** | เปลี่ยน `api/recommend-major.js` เป็น proxy | ทำแบบสอบถามครบ 4 ขั้น → เห็น primary + alternatives + เปอร์เซ็นต์ | `git checkout -- api/recommend-major.js` |
| **4** | เปลี่ยน `api/compare-courses.js` เป็น proxy | เลือก 2 สาขา → เห็นตาราง (ยอมรับว่า cons ว่าง) | `git checkout -- api/compare-courses.js` |
| **5** | ตรวจว่าของเพื่อนไม่พัง | Sci Connect โหลดข่าวได้ · `/admin` login ได้ · ingest ทำงาน | — |
| **6** | ตั้ง env บน Vercel แล้ว deploy เป็น **preview** (ไม่ใช่ production) | preview URL ใช้งานครบทุกหน้า | ไม่ต้องทำอะไร preview ไม่กระทบใคร |
| **7** | ซ้อมเดโมเต็มชุดบน preview URL | ผ่านทุกข้อใน `PRE_PRESENTATION_TEST_CHECKLIST.md` | ใช้ duckdns พรีแทน |
| **8** | *(หลังพอใจแล้วเท่านั้น)* promote เป็น production ของ Vercel | — | Vercel "Instant Rollback" กลับรุ่นก่อนได้ทันที |

**ขั้น 1–5 ทำบนเครื่องล้วน ไม่ยิงเน็ตออกนอกนอกจากเรียก FastAPI ซึ่งเป็นแค่การอ่าน**
**ขั้น 6 เป็นครั้งแรกที่มีอะไรขึ้นอินเทอร์เน็ต และเป็น URL ใหม่ที่ไม่มีใครใช้อยู่**

### สิ่งที่ทำเป็นอันดับแรกสุด ก่อนขั้น 0

**commit + push `LastProject` ขึ้น GitHub ทันที** — ตอนนี้มันคือซอร์สหน้าเว็บชุดเดียวที่เหลืออยู่บนโลก
และ `ProjectPnru` เพิ่งหายไปต่อหน้าต่อตาเมื่อชั่วโมงที่แล้ว

---

## 12. จุดที่เสี่ยงทำ production พัง — และทำไมแผนนี้ไม่พัง

| ความเสี่ยง | เกิดได้ไหมกับแผนนี้ | เหตุผล |
|---|---|---|
| หน้าเว็บ duckdns พัง | **ไม่** | ไม่แตะ `/srv/web` และไม่ build ทับ |
| backend FastAPI พัง | **ไม่** | ไม่แก้โค้ด ไม่ restart ไม่แตะ `.env` |
| ฐานข้อมูล/เอกสารเสียหาย | **ไม่** | ทุกการเรียกเป็น read-only ของ API สาธารณะ |
| PDF endpoint พัง | **ไม่** | FROZEN ไม่แตะ |
| Supabase เสียหาย | **ไม่** | ไม่แก้ schema ไม่ลบตาราง |
| **โควตา Gemini หมดเพราะทดสอบเยอะ** | ⚠️ **เป็นไปได้** | ทดสอบขั้น 2–4 ใช้ Gemini จริง — จำกัดไม่เกิน 10–15 คำถาม และ**อย่าทดสอบในวันพรี** |
| **ชนตัวจำกัด 20 คำขอ/นาที** | ⚠️ **เป็นไปได้** | ถ้ากดทดสอบรัวๆ จะได้ 429 ให้เว้นจังหวะ |
| ทำไฟล์หน้าเว็บหายซ้ำรอย ProjectPnru | ⚠️ **นี่คือความเสี่ยงที่แท้จริง** | ป้องกันด้วยการ push ขึ้น GitHub ก่อนเริ่ม และทำงานบน branch แยก |

**ความเสี่ยงที่รับไม่ได้มีข้อเดียว: ทำซอร์สหายอีกครั้ง** ซึ่งแก้ได้ด้วยการ push ก่อนลงมือ

---

## สถาปัตยกรรมสุดท้าย

```
                          ผู้ใช้ (เบราว์เซอร์)
                                  │
                    ┌─────────────┴─────────────┐
                    │   Frontend (LastProject)   │
                    │   React + Vite บน Vercel    │
                    └─────────────┬─────────────┘
                                  │
        ┌─────────────────────────┼──────────────────────────┐
        │                         │                          │
        ▼                         ▼                          ▼
┌───────────────┐   ┌──────────────────────────┐   ┌──────────────────┐
│ Supabase      │   │ Vercel Functions (proxy)  │   │ Vercel Functions │
│ (เรียกตรงจาก  │   │ /api/chat                 │   │ /api/sci-connect │
│  เบราว์เซอร์) │   │ /api/compare-courses      │   │ /api/admin/*     │
│               │   │ /api/recommend-major      │   │                  │
│ • courses     │   │ /api/course-facts         │   │ ingest · extract │
│ • news        │   └────────────┬─────────────┘   └────────┬─────────┘
│ • user_profiles│               │ HTTPS                     │
│ • ai_settings │                ▼                           ▼
│ • rag_documents│   ┌────────────────────────┐      ┌──────────────┐
│ • knowledge    │   │ Caddy (Oracle Cloud)    │      │ Supabase     │
└───────────────┘    │ /api/chat → /chat-web   │      │ + Google     │
                     │ /api/*    → strip /api  │      │   embedding  │
                     └───────────┬────────────┘      └──────────────┘
                                 ▼
                     ┌────────────────────────┐
                     │ FastAPI (backend)       │
                     │ web_compat.py           │
                     ├────────────────────────┤
                     │ • Structured Metadata   │──► PostgreSQL + pgvector
                     │ • RAG (9,039 chunks)    │    mko.v_live_values (103)
                     │ • Gemini 3.5-flash-lite │    mko.v_live_list_items (156)
                     │   + สำรอง 3 ตัว          │    course_chunks · evidence (787)
                     │ • Ollama bge-m3         │
                     │ • /documents/{id}/pdf   │──► /srv/documents (PDF 30 เล่ม)
                     └────────────────────────┘
```

### request แต่ละประเภทวิ่งไปไหน

| ผู้ใช้ทำอะไร | วิ่งผ่าน | ประมวลผลที่ | ข้อมูลจาก |
|---|---|---|---|
| เปิดหน้ารายการสาขา / รายละเอียด | Supabase โดยตรง | Supabase | ตาราง `courses` |
| เปิดหน้ารายละเอียด (ช่องหน่วยกิต/ค่าเทอม/อาจารย์) | Vercel proxy → Caddy | **FastAPI** `/course-facts` | ไฟล์ที่สรุปจาก มคอ.2 + ประกาศค่าเทอม |
| **ถามแชท (ข้อเท็จจริง เช่น หน่วยกิต)** | Vercel proxy → Caddy | **FastAPI** Structured Metadata | `mko.v_live_values` — **ไม่เรียกโมเดลเลย** |
| **ถามแชท (ปลายเปิด)** | Vercel proxy → Caddy | **FastAPI** RAG + Gemini | `course_chunks` (9,039) + Ollama `bge-m3` |
| **แนะนำสาขา** | Vercel proxy → Caddy | **FastAPI** `match_programs` + Gemini | เวกเตอร์เอกสาร + ชื่อสาขา · รับ `courses` จาก Supabase |
| **เปรียบเทียบสาขา** | Vercel proxy → Caddy | **FastAPI** `compare_programs` + Gemini | เอกสาร มคอ.2 ทั้งสองเล่ม |
| เปิด PDF ต้นฉบับ | Caddy โดยตรง | **FastAPI** `/documents/{id}/pdf` | `/srv/documents` (30 เล่ม) |
| ข่าว Sci Connect | Vercel Function | Vercel + Supabase | `news` / `external_news` |
| หน้าแอดมิน (login, จัดการ, ingest) | Supabase + Vercel Function | Supabase + Google embedding | `user_profiles` · `rag_documents` · `knowledge_articles` |

**สรุปการแบ่งงาน:** Supabase ดูแล *รายการสาขา ข่าว ผู้ใช้ และหลังบ้าน* · FastAPI ดูแล *ทุกอย่างที่เป็นคำตอบจากเอกสารหลักสูตร*

---

## สิ่งที่รออนุมัติ

1. ยืนยันว่าใช้ **วิธี proxy** (ไม่แก้ CORS ไม่แตะ backend) — หรือจะเลือกวิธีเรียกตรง
2. ยืนยันว่า **deploy ลง Vercel preview ก่อน** ไม่ promote จนกว่าจะซ้อมผ่าน
3. อนุมัติให้ **commit + push `LastProject` ขึ้น GitHub ก่อนเริ่ม** (สำคัญที่สุด)
4. ยืนยันว่ารับได้ที่ **หัวข้อ "ข้อควรพิจารณา" (cons) จะหายไป** จากหน้าเปรียบเทียบ

---

READ-ONLY: ไม่แก้ไฟล์ · ไม่ commit · ไม่ push · ไม่ deploy · ไม่แตะ production
