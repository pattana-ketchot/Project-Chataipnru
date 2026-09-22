# ตรวจสถานะ git หลังรวมระบบ — สรุปไฟล์ ตรวจความลับ และข้อเสนอการ commit

2026-09-23 · **ยังไม่ commit ยังไม่ push** · รออนุมัติ

---

## 1. ผลตรวจความลับ — **ผ่าน ไม่พบสิ่งที่ไม่ควรอยู่ใน git**

สแกนไฟล์ที่จะถูก commit ทั้งหมด **37 ไฟล์** (หลังบ้าน 34 · หน้าเว็บ 3) ด้วยรูปแบบ 13 แบบ

| สิ่งที่ค้นหา | ผล |
|---|---|
| กุญแจแบบ JWT / Supabase (`eyJ…`) | ✅ ไม่พบ |
| Google API key (`AIza…`) | ✅ ไม่พบ |
| OpenAI / OpenRouter (`sk-…`) | ✅ ไม่พบ |
| AWS key · PRIVATE KEY block | ✅ ไม่พบ |
| `password=` / `passwd=` ที่มีค่าจริง | ✅ ไม่พบ |
| `postgresql://user:pass@host` | ✅ ไม่พบ |
| URL โปรเจกต์ Supabase ตัวจริง | ✅ ไม่พบ |
| ที่อยู่เซิร์ฟเวอร์ · เส้นทางกุญแจ ssh | ✅ ไม่พบในไฟล์ใหม่ |
| อีเมลส่วนบุคคล | ✅ ไม่พบ |

**จุดเดียวที่เครื่องมือจับได้** คือ `ANON_KEY: ${VITE_SUPABASE_ANON_KEY}` ใน
`docs/OPTION_A_PREDEPLOY_REPORT.md` — เป็น **ชื่อตัวแปร** ในตัวอย่างไฟล์ compose ไม่ใช่ค่าจริง ปลอดภัย

### ไฟล์ที่ git ติดตามอยู่ — ไม่มีของต้องห้าม

```
ค้นหา .env / backups/ / *.key / id_rsa / secret ในรายการไฟล์ที่ถูก track
ผลลัพธ์: พบเพียง .env.example และ frontend/.env.example  ← เป็นแม่แบบ ตั้งใจให้อยู่
```

ตรวจเนื้อในของทั้งสองไฟล์แล้ว **ทุกค่าเป็นค่าตัวอย่าง** (`change-me-…`, `your-anon-key`)
มีสองบรรทัดที่เครื่องมือเตือนเพราะยาวเกินเกณฑ์ แต่ตรวจแล้วไม่ใช่ความลับ —
`AI_BASE_URL=https://openrouter.ai/api/v1` (URL สาธารณะ) และ
`CORS_ALLOW_ORIGINS=["http://localhost:3000",…]` (ค่าตั้งต้น)

### ไฟล์สำรองถูกกันไว้แล้วโดยอัตโนมัติ

`docs/backups/supabase_courses_backup_20260923.json` และ `restore_course_detail_20260923.sql`
**ไม่ขึ้นใน git status** เพราะ `.gitignore` บรรทัดที่ 35 มีกฎ `backups/` อยู่แล้ว ✅

---

## 2. ไฟล์ที่เปลี่ยนทั้งหมดจากการรวมระบบครั้งนี้

### 2.1 หน้าเว็บ — `D:\workspace\LastProject` (branch `prep-step8`)

รีโป `FoMake/Univercity` — **เป็นรีโปของเพื่อน**

| ไฟล์ | เปลี่ยน | เนื้อหา |
|---|---|---|
| `src/pages/FindMajorResult.jsx` | +54 −1 | คอมโพเนนต์อธิบายที่มาของเปอร์เซ็นต์ความเหมาะสม (กดเปิด/ปิด) |
| `src/pages/CourseDetail.jsx` | +39 −2 | เรียก `/api/course-facts` มาเติมช่องที่ยังว่าง + ฟังก์ชัน `withFacts()` |
| `TECH_STACK.md` | ไฟล์ใหม่ ยังไม่ track | **เป็นไฟล์ของเพื่อน ไม่ใช่ของงานรอบนี้** |

### 2.2 หลังบ้าน — `D:\workspace\course-advisor-system-mko2` (branch `mko-phase2`)

รีโป `pattana-ketchot/Project-Chataipnru`

**ไม่มีไฟล์โค้ดที่ถูกแก้เลย** — โค้ด backend ทั้งหมด commit ไปแล้วที่ `705b425`
ที่เหลือเป็นเอกสาร **29 รายการ · 34 ไฟล์ · ประมาณ 640 KB** แบ่งได้ 3 กลุ่ม

| กลุ่ม | ไฟล์ |
|---|---|
| **ก. บันทึกงานที่ค้างจากรอบก่อน** (9 ไฟล์) | `CHAT_RECOMMENDATION_CLARIFICATION_{RCA,VALIDATION,DEPLOY}.md` · `CHAT_RECOMMENDATION_STABILITY_DEPLOYMENT_REPORT.md` · `CHAT_SOURCE_HEADER_DEPLOYMENT_REPORT.md` · `FIND_MAJOR_SCORE_{EXPLANATION_DEPLOYMENT,EXPLANATION_FRONTEND_HANDOFF,ORDER_FIX_DEPLOYMENT}*.md` · `PDF_ENDPOINT_DEPLOYMENT_REPORT.md` · `find-major-score-explanation.patch` |
| **ข. เอกสารสำหรับเล่มรายงานและเครื่องมือวิจัย** (11 รายการ) | `APPENDIX_A_QUESTIONNAIRE.md` · `APPENDIX_B_IOC_FORM.md` · `HANDOFF_REPORT_DATABASE_SECTION.md` · `HANDOFF_SATISFACTION_QUESTIONNAIRE.md` · `REPORT_SECTION_DATABASE_DESIGN.md` · `REPORT_SECTIONS_CH3_CH4_RESEARCH.md` · `REPORT_RESTRUCTURE_TO_TEMPLATE.md` · `PRESENTATION_SCRIPT_METADATA_TO_SOURCE_LINK.md` · `STRUCTURED_METADATA_DEMO_GUIDE.md` · `ENGINEERING_STABILITY_RULES.md` · `satisfaction_analysis.xlsx` · `diagrams/` (6 ไฟล์) |
| **ค. บันทึกการรวมระบบรอบนี้** (7 ไฟล์) | `FRONTEND_TWO_VERSIONS_COMPARISON.md` · `MERGE_PLAN_LASTPROJECT_X_FASTAPI.md` · `OPTION_A_PREDEPLOY_REPORT.md` · `OPTION_A_STEP1_6_REPORT.md` · `OPTION_A_STEP8_READINESS.md` · `OPTION_A_STEP8_DEPLOYMENT_REPORT.md` · `SUPABASE_TESTDATA_CLEANUP.md` |

---

## 3. ⚠️ พบสองเรื่องที่ต้องตัดสินใจ — รีโปยังไม่ตรงกับ production

### 3.1 ไฟล์ตั้งค่าบนเซิร์ฟเวอร์ต่างจากในรีโปแล้ว

การรวมระบบรอบนี้แก้ `docker-compose.prod.yml` และ `Caddyfile` **บนเซิร์ฟเวอร์โดยตรง**
แต่ไฟล์ในรีโปยังเป็นของเดิม

| ไฟล์ | รีโป | เซิร์ฟเวอร์ |
|---|---|---|
| `docker-compose.prod.yml` | `3835f968…` — **ไม่มีบริการ webapi** | `d76afeef…` — มี |
| `Caddyfile` | `2922ff4b…` — **ไม่มีเส้นทาง webapi** | `da2e26fd…` — มี |

ถ้าไม่แก้ ใครก็ตามที่ deploy จากรีโปนี้จะได้ระบบที่ **ไม่มีข่าว Sci Connect และไม่มีหน้าแอดมิน**

### 3.2 โฟลเดอร์ `webapi/` มีเฉพาะบนเซิร์ฟเวอร์ ไม่มีในรีโป

ประกอบด้วย 13 ไฟล์ — `Dockerfile` · `server.mjs` · `package.json` (สามอย่างนี้ผมเขียนเอง)
และ `api/` อีก 10 ไฟล์ซึ่ง **เป็นโค้ดของเพื่อน คัดลอกมาโดยไม่แก้**

**ข้อเสนอ** เก็บเฉพาะสามไฟล์ที่เราเขียนเองเข้ารีโป แล้วใส่ `webapi/api/` ไว้ใน `.gitignore`
พร้อม `README.md` อธิบายว่าต้องคัดลอก `api/` จากรีโปของเพื่อนตอน deploy
เหตุผลคือโค้ดส่วนนั้นเป็นของอีกทีม ไม่ควรนำมาเก็บในรีโปเราโดยไม่ได้ตกลงกัน
— ถ้าคุณอยากเก็บทั้งหมดเพื่อให้ deploy ซ้ำได้จากรีโปเดียว บอกได้ ผมทำให้

### 3.3 `.env.example` ขาดตัวแปรที่ compose อ้างถึง 6 ตัว

| ตัวแปร | เพิ่มจากรอบนี้ไหม |
|---|---|
| `VITE_SUPABASE_URL` · `VITE_SUPABASE_ANON_KEY` · `GOOGLE_GENERATIVE_AI_API_KEY` | **ใช่ มาจากการรวมระบบ** |
| `SITE_DOMAIN` · `DOCUMENTS_DIR` · `CHAT_TOP_K` | ไม่ใช่ ขาดอยู่ก่อนแล้ว |

---

## 4. ข้อเสนอการ commit

### รีโปที่ 1 — หลังบ้าน `Project-Chataipnru` branch `mko-phase2`

**commit 1** เอกสารงานที่ค้างจากรอบก่อน
```
docs: บันทึกผลการแก้ไขและการนำขึ้นใช้งานที่ค้างจากรอบก่อนหน้า

รวมรายงาน RCA การแก้ปัญหาคำแนะนำสาขา การแก้คะแนนที่ขึ้นกับลำดับการเลือก
เส้นทางเปิดเอกสารต้นฉบับ และ header บอกที่มาของคำตอบ
```
ไฟล์: กลุ่ม ก. 9 ไฟล์

**commit 2** เอกสารสำหรับเล่มรายงานและเครื่องมือวิจัย
```
docs: เอกสารประกอบเล่มรายงานและเครื่องมือประเมินผล

หัวข้อการออกแบบฐานข้อมูลจากโครงสร้างจริง ระเบียบวิธีวิจัย แบบประเมินความพึงพอใจ
แบบตรวจ IOC ไฟล์คำนวณสถิติ ภาพประกอบ และกติกาการแก้ปัญหาของโครงการ
```
ไฟล์: กลุ่ม ข. 11 รายการ (16 ไฟล์)

**commit 3** บันทึกการรวมระบบ
```
docs: บันทึกการรวมหน้าเว็บของทีมออกแบบเข้ากับระบบหลังบ้าน

ครอบคลุมการสำรวจสองเวอร์ชัน แผนการรวม รายงานก่อน deploy ระหว่าง deploy
และผลหลังนำขึ้นใช้งาน พร้อมรายการที่ยังค้าง
```
ไฟล์: กลุ่ม ค. 7 ไฟล์

**commit 4** ทำให้ไฟล์ตั้งค่าในรีโปตรงกับ production *(ต้องทำ ไม่งั้นรีโปไม่ตรงกับของจริง)*
```
feat: เพิ่มบริการ webapi สำหรับข่าวและงานหลังบ้านของหน้าเว็บ

เพิ่มบริการ Node ที่รับผิดชอบเฉพาะ /api/sci-connect-news* และ /api/admin/*
โดยคุยกับ Supabase เท่านั้น ไม่แตะฐานข้อมูลหรือเส้นทางของ FastAPI

/api/chat /api/compare-courses /api/recommend-major /api/course-facts
และ /api/documents ยังเป็นของ backend เหมือนเดิมทุกประการ
```
ไฟล์: `docker-compose.prod.yml` · `Caddyfile` · `webapi/{Dockerfile,server.mjs,package.json,README.md}` · `.gitignore` · `.env.example`

### รีโปที่ 2 — หน้าเว็บ `FoMake/Univercity` branch `prep-step8`

**commit 1**
```
feat: อธิบายที่มาของเปอร์เซ็นต์ความเหมาะสมในหน้าผลลัพธ์

ผู้ใช้เห็น "59% เหมาะสม" แล้วเข้าใจว่าเป็นโอกาสที่จะเรียนสำเร็จ ซึ่งไม่ใช่
เพิ่มส่วนอธิบายแบบกดเปิดว่าเป็นความใกล้เคียงกับเนื้อหาในเอกสารหลักสูตร
```
ไฟล์: `src/pages/FindMajorResult.jsx`

**commit 2**
```
feat: เติมข้อมูลหลักสูตรจากเอกสาร มคอ.2 ในหน้ารายละเอียด

ช่องหน่วยกิต ภาษาที่ใช้ ค่าเทอม และคำอธิบายสาขาถูกสกัดจากเอกสารไว้แล้วฝั่งหลังบ้าน
หน้านี้จึงเรียก /api/course-facts มาเติมเฉพาะช่องที่ยังไม่มีคนกรอก
ค่าที่ผู้ดูแลระบบกรอกเองมาก่อนเสมอ และถ้าเรียกไม่สำเร็จก็แสดงเท่าที่มีตามเดิม
```
ไฟล์: `src/pages/CourseDetail.jsx`

> `TECH_STACK.md` **ไม่ commit** เพราะเป็นไฟล์ของเพื่อน ไม่เกี่ยวกับงานรอบนี้ ปล่อยไว้ให้เจ้าของจัดการ

---

## 5. ข้อเสนอเรื่อง branch ที่ควร push

| รีโป | branch | push ไปไหน | หมายเหตุ |
|---|---|---|---|
| `Project-Chataipnru` | `mko-phase2` | `origin/mko-phase2` (branch ใหม่) | **ยังไม่เคย push เลย — ตอนนี้ค้างอยู่ 15 commit บนเครื่องเดียว** |
| `FoMake/Univercity` | `prep-step8` | `origin/prep-step8` (branch ใหม่) | **เป็นรีโปของเพื่อน** ต้องมีสิทธิ์ push · อย่า push เข้า `main` ตรงๆ ให้เพื่อนรีวิวก่อน |

### ⚠️ เรื่องที่ต้องเน้น

`mko-phase2` มี **15 commit ที่ยังไม่ได้ push** รวมทั้งโค้ดทั้งหมดที่รันบน production อยู่ตอนนี้
(`origin/main` อยู่ที่ `b78b3f8` ตามหลัง 14–15 commit) — **ถ้าโน้ตบุ๊กมีปัญหา งานหายทั้งหมด**

แนะนำให้ push `mko-phase2` ขึ้นเป็น branch ใหม่ก่อนเป็นอันดับแรก
ยังไม่ต้อง merge เข้า `main` ก็ได้ แค่ให้มีสำเนาอยู่นอกเครื่อง

---

## 6. คำสั่งที่จะใช้ (ยังไม่รัน รออนุมัติ)

```bash
# ── หลังบ้าน ──
cd D:/workspace/course-advisor-system-mko2
git add docs/CHAT_* docs/FIND_MAJOR_* docs/PDF_ENDPOINT_DEPLOYMENT_REPORT.md docs/find-major-score-explanation.patch
git commit -m "docs: บันทึกผลการแก้ไขและการนำขึ้นใช้งานที่ค้างจากรอบก่อนหน้า"

git add docs/APPENDIX_* docs/HANDOFF_* docs/REPORT_* docs/PRESENTATION_SCRIPT_* \
        docs/STRUCTURED_METADATA_DEMO_GUIDE.md docs/ENGINEERING_STABILITY_RULES.md \
        docs/satisfaction_analysis.xlsx docs/diagrams/
git commit -m "docs: เอกสารประกอบเล่มรายงานและเครื่องมือประเมินผล"

git add docs/FRONTEND_TWO_VERSIONS_COMPARISON.md docs/MERGE_PLAN_* docs/OPTION_A_* docs/SUPABASE_TESTDATA_CLEANUP.md
git commit -m "docs: บันทึกการรวมหน้าเว็บของทีมออกแบบเข้ากับระบบหลังบ้าน"

# commit 4 ต้องดึงไฟล์ตั้งค่าจากเซิร์ฟเวอร์ลงมาก่อน แล้วสร้างโฟลเดอร์ webapi/
# (ผมจะทำให้ตามขั้นตอนถ้าอนุมัติ)

git push -u origin mko-phase2

# ── หน้าเว็บ ──
cd D:/workspace/LastProject
git add src/pages/FindMajorResult.jsx && git commit -m "feat: อธิบายที่มาของเปอร์เซ็นต์ความเหมาะสมในหน้าผลลัพธ์"
git add src/pages/CourseDetail.jsx     && git commit -m "feat: เติมข้อมูลหลักสูตรจากเอกสาร มคอ.2 ในหน้ารายละเอียด"
git push -u origin prep-step8
```

---

## 7. รออนุมัติ 4 ข้อ

1. **commit ตามที่เสนอไหม** (หลังบ้าน 4 commit · หน้าเว็บ 2 commit)
2. **`webapi/api/` จะเก็บเข้ารีโปด้วยไหม** — หรือเก็บเฉพาะตัวครอบของเราแล้วใส่ gitignore
3. **push `mko-phase2` ขึ้น GitHub ได้ไหม** — อันนี้เร่งที่สุด งานค้างบนเครื่องเดียว 15 commit
4. **push `prep-step8` เข้ารีโปของเพื่อนได้ไหม** — มีสิทธิ์ push หรือต้องรอคุยกับเพื่อนก่อน
