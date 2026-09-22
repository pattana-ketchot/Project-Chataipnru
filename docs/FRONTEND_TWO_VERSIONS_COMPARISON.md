# เปรียบเทียบหน้าเว็บสองเวอร์ชัน — ของที่ deploy อยู่ vs ของเพื่อนที่ได้มาล่าสุด

วันที่ตรวจ: 2026-09-22 · **READ-ONLY** — ไม่แก้ไฟล์ใดทั้งสองฝั่ง ไม่ commit ไม่ push ไม่ deploy
ตรวจจาก `D:\workspace\LastProject` (ของเพื่อน) และ `D:\workspace\ProjectPnru\ProjectPnru` (ตัวที่ live อยู่)

> **สรุปบรรทัดเดียว:** ไฟล์ที่เพื่อนส่งมาไม่ใช่แค่หน้าเว็บ แต่เป็น **ระบบ SCI Advisor อีกตัวที่สมบูรณ์ในตัวเอง** มี backend, ฐานข้อมูล และโมเดล AI เป็นของตัวเอง ไม่เรียกระบบของเราเลย

---

## 1. สองระบบนี้ต่างกันตรงไหน

| | ของเรา (live ที่ `stpnru-advisor.duckdns.org`) | ของเพื่อน (`LastProject`) |
|---|---|---|
| Backend | FastAPI บน Oracle Cloud | **Vercel Serverless Functions** (`api/`) |
| ฐานข้อมูล | PostgreSQL + pgvector (เครื่องเรา) | **Supabase** |
| โมเดลตอบคำถาม | Gemini `3.5-flash-lite` + สำรองอีก 3 ตัว | **OpenRouter → `openai/gpt-4o-mini`** |
| โมเดลฝังเวกเตอร์ | Ollama `bge-m3` (1024 มิติ) | ใช้บริการฝั่ง Supabase/AI SDK |
| คลังความรู้ | 4,129 หน้าจาก มคอ.2 · 787 หลักฐานรายหน้า | ตาราง `rag_documents` / `knowledge_articles` |
| Structured Metadata | **มี** — 103 ค่า · 156 รายการ · ผ่านการตรวจและ publish เป็นชุด | **ไม่มี** |
| บอกที่มาของคำตอบ | **มี** — "ที่มา: ma69.pdf หน้า 1" | **ไม่มี** |
| เปิด PDF ต้นฉบับ | **มี** — `/api/documents/{id}/pdf` | **ไม่มี** |
| ระบบ Admin | ไม่มี | **มี** — จัดการหลักสูตร/ข่าว/ผู้ใช้/ตั้งค่า AI |
| ข่าว Sci Connect | ไม่มี | **มี** (+ Supabase Edge Function ซิงค์ข่าว) |
| เปลี่ยนโมเดล AI จากหน้าเว็บ | ไม่ได้ | **ได้** (ตาราง `ai_settings`) |
| deploy ที่ | Oracle Cloud + Caddy | **Vercel** |

ฝั่งเพื่อนมี endpoint ของตัวเองครบ: `api/chat.js` · `api/compare-courses.js` · `api/recommend-major.js`
พร้อมไลบรารีร่วม `api/_lib/` (`rag.js`, `ingest.js`, `aiConfig.js`, `adminAuth.js`, `fileExtract.js`)

---

## 2. เป็น repo เดียวกัน แต่แยกทางกันแล้ว

ทั้งสองโฟลเดอร์มาจาก `github.com/FoMake/Univercity` เหมือนกัน แต่เดินคนละเส้นทาง

```
f9f897c  Initial commit
   │
eef5f71  Add vercel.json SPA rewrite
   ├──────────────────────────────┐
   │                              │
   │  ProjectPnru                 │  LastProject (ของเพื่อน)
   │  = eef5f71 + 47 ไฟล์         │  e143ad2  First
   │    ที่ยังไม่ commit           │  0f0dfe7  Update SciAdvisor
   │  ★ ตัวนี้คือของที่ live      │  (working tree สะอาด)
```

| | ProjectPnru | LastProject |
|---|---|---|
| commit ล่าสุด | `eef5f71` | `0f0dfe7` (ล้ำหน้า 2 commits) |
| ไฟล์ที่ยังไม่ commit | **47 ไฟล์** (แก้ 25 · ลบ 12 · ใหม่ 10) | 1 |
| ขนาดความต่างจากจุดแยก | — | **102 ไฟล์ · +8,068 / −4,316 บรรทัด** |
| เป็นตัวที่ deploy อยู่จริง | **ใช่** | ไม่ |

**สองฝั่งนี้ยังไม่เคยรวมกัน**

---

## 3. งานของเราไม่มีอยู่ในชุดที่เพื่อนส่งมา

| งานที่ทำไว้ | อยู่ใน ProjectPnru (live) | อยู่ใน LastProject |
|---|---|---|
| ส่วนขยาย "เปอร์เซ็นต์คำนวณอย่างไร?" ในหน้าผลลัพธ์ | ✅ | ❌ |
| อ่าน header `X-Source-Document` / `X-Source-Page` | ❌ (ยังไม่ได้ทำทั้งสองฝั่ง) | ❌ |
| `FindMajorResult.jsx` | 15,480 ไบต์ (18 ก.ย.) | 11,299 ไบต์ (4 ก.ย.) |
| จำนวนไฟล์ `.jsx` ใน `src/` | 48 | 43 |

⚠️ **ถ้า copy `LastProject` ทับ `ProjectPnru` งานฝั่งเราหายทันที** และหน้าเว็บที่ live อยู่จะเปลี่ยนตามด้วย

---

## 4. จุดที่ต้องเข้าใจให้ชัด — `/api/chat` เป็น path สัมพัทธ์

`src/pages/ChatAdvisor.jsx:52`

```js
const response = await fetch('/api/chat', { ... })
```

**โค้ดชุดเดียวกัน แต่สมองคนละตัว ขึ้นกับว่า host ที่ไหน**

```
host บน Vercel            →  api/chat.js ของเพื่อน  →  OpenRouter / gpt-4o-mini
host บนเซิร์ฟเวอร์เรา      →  Caddy แปลงเป็น /chat-web  →  FastAPI ของเรา
```

นี่คือเหตุผลที่หน้าเว็บหน้าตาเหมือนกัน แต่คำตอบที่ได้คนละระบบ

---

## 5. หน้าเว็บที่มีในแต่ละฝั่ง

เหมือนกันทั้งหมด 13 หน้า: `Home` · `AllCourses` · `CourseDetail` · `Careers` · `ChatAdvisor` ·
`CompareCourses` · `CompareResult` · `FindMajor` · `FindMajorStep2-4` · `FindMajorResult` · `Admin/`

**เพิ่มเฉพาะฝั่งเพื่อน:** `SciConnectAll.jsx` · `SciConnectDetail.jsx` (ข่าว Sci Connect)

---

## 6. สิ่งที่ต้องตัดสินใจก่อนพรี

**คำถามเดียว: จะพรีจาก URL ไหน**

| พรีจาก | อาจารย์จะเห็น |
|---|---|
| `stpnru-advisor.duckdns.org` | ระบบของเรา — ตอบพร้อมบอกไฟล์และเลขหน้า เปิด PDF ต้นฉบับได้ สาวกลับเอกสารได้ทุกค่า |
| URL Vercel ของเพื่อน | gpt-4o-mini + Supabase — **งาน MKO / Structured Metadata / หลักฐาน / PDF ไม่ปรากฏเลย** แต่ได้ระบบ Admin และข่าวมาแทน |

สคริปต์นำเสนอที่เตรียมไว้ (`PRESENTATION_SCRIPT_METADATA_TO_SOURCE_LINK.md`,
`STRUCTURED_METADATA_DEMO_GUIDE.md`) **อิงระบบของเราทั้งหมด** ใช้กับเวอร์ชันของเพื่อนไม่ได้

### คำแนะนำ

1. **อย่าเพิ่งรวมโค้ดสองฝั่ง** — เหลือ 2 วัน การ merge 102 ไฟล์เข้ากับ 47 ไฟล์ที่ยังไม่ commit เสี่ยงเกินไป
2. **ตกลงกับทีมให้ชัดว่าใครพรีจาก URL ไหน** ก่อนวันพรี ไม่ใช่หน้างาน
3. **อย่า copy ทับกันเด็ดขาด** จนกว่าจะพรีเสร็จ
4. **commit + push ฝั่ง ProjectPnru** ให้เรียบร้อย — ตอนนี้ของที่ live อยู่บนโน้ตบุ๊กเครื่องเดียว ไม่มีสำเนาที่อื่น
5. ค่อยคุยเรื่องรวมสองระบบหลังพรีเสร็จ

---

## 7. หมายเหตุ

- `.env` เคยถูก commit ไว้ใน `f9f897c` และยังอยู่ใน git history (ลบออกภายหลังที่ `e143ad2`)
  ตรวจแล้วมีเพียง `VITE_SUPABASE_URL` และ `VITE_SUPABASE_ANON_KEY` ซึ่งเป็นคีย์ฝั่ง client
  ที่ออกแบบมาให้เปิดเผยได้อยู่แล้ว และ `supabase_schema.sql` เปิด Row Level Security ครบ
  **7 ตาราง 32 policy** → ไม่ถือเป็นช่องโหว่ · คีย์ AI (`AI_API_KEY`, `GOOGLE_GENERATIVE_AI_API_KEY`)
  ไม่เคยเข้า git history
- เวอร์ชันของเพื่อนใช้ `mammoth` (Word) และ `pdf-parse` (PDF) นำเข้าเอกสารเข้าคลังความรู้จากหน้า Admin
  ต่างจากของเราที่ใช้ pipeline แยกพร้อม OCR และบันทึกหลักฐานรายหน้า

---

READ-ONLY: ไม่แก้ไฟล์ · ไม่ commit · ไม่ push · ไม่ deploy · ไม่แตะ repo ของเพื่อน
