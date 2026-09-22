# Find-Major Score Explanation — Frontend Handoff (Step B)

ถึงเจ้าของ repo หน้าเว็บ (`FoMake/Univercity`)
สถานะ: UI นี้อยู่บน production แล้ว (deploy เฉพาะไฟล์ static ดู `FIND_MAJOR_SCORE_EXPLANATION_DEPLOYMENT_REPORT.md`) แต่ **ยังไม่ได้ commit ที่ไหน** จึงต้องนำกลับเข้า source ที่ track ไว้

---

## 1. ทำไมต้องเพิ่มคำอธิบาย

หน้า "ผลลัพธ์" แสดง "65% เหมาะสม" ซึ่งอ่านได้ง่ายว่าเป็นความน่าจะเป็นที่จะเหมาะหรือจะเรียนสำเร็จ แต่ความจริงคือ

- คะแนนคือ **ระดับความใกล้เคียงของข้อความ** ระหว่างคำตอบแบบสอบถามกับเนื้อหาในเอกสารหลักสูตร (มคอ.2) และชื่อสาขา
- ข้อที่นำมาคำนวณมีเพียง วิชาที่ชอบ ความสนใจ ความถนัด และเป้าหมายอาชีพ (สายการเรียนกับสภาพแวดล้อมการทำงานใช้เฉพาะตอนเขียนคำอธิบาย)
- **AI ไม่ได้เป็นผู้ให้คะแนน** ทำหน้าที่เขียนข้อความเหตุผลเท่านั้น
- แต่ละสาขาคิดคะแนนแยกกัน ผลรวมจึงไม่จำเป็นต้องเป็น 100%

ถ้อยคำในกล่องนี้ตรวจกับโค้ดหลังบ้านแล้ว (`backend/app/services/program_match.py`, `backend/app/api/routes/web_compat.py` ของระบบ course-advisor)

## 2. production เปลี่ยนอะไร

- เพิ่มปุ่มเล็ก ๆ "เปอร์เซ็นต์คำนวณอย่างไร?" ใต้ข้อความในกล่อง "สรุปจาก AI" กดเพื่อเปิด/ปิดคำอธิบาย
- ไม่แก้การ์ดผลลัพธ์ ไม่แก้ `matchScore` ไม่แก้ payload ที่ส่งไป `/api/recommend-major` ไม่แก้หน้าอื่น
- build ที่ deploy: JS `index-gw896RX9.js`, CSS `index-BRkWBF7z.css` ต่างจากของเดิมเฉพาะ component นี้ (JS +47 บรรทัดก่อน minify, CSS +5 rule)

## 3. Source file

`src/pages/FindMajorResult.jsx`

- ตัวที่ track อยู่: `FoMake/Univercity` branch `main` commit `0f0dfe7`
- ตัวที่ production ใช้ build จริงตอนนี้: working copy ในเครื่อง `D:\workspace\ProjectPnru\ProjectPnru\src\pages\FindMajorResult.jsx` ซึ่ง **untracked**
- สองไฟล์นี้ต่างกันแค่ comment 2 บรรทัด (เรื่องคอลัมน์ `category` ของ Supabase) โค้ดเหมือนกันทุกบรรทัด patch จึง apply ได้กับทั้งสองฝั่ง

## 4. Patch ที่ต้อง apply

ไฟล์: `docs/find-major-score-explanation.patch` (SHA-256 `dec8f7d611e5edb96ef611545bba6b7cfc86e89a5588804305f763417c3a2acb`) สร้างจากไฟล์ที่ track ไว้ที่ `0f0dfe7`

```bash
git checkout -b feat/find-major-score-explanation
git apply --3way docs/find-major-score-explanation.patch   # หรือ patch -p1 < ...
```

patch มีเฉพาะ 3 อย่าง ไม่มีอย่างอื่นปนเลย

1. เพิ่ม `Info` และ `ChevronDown` ใน import ของ `lucide-react` (1 บรรทัด)
2. เพิ่ม component `ScoreExplanation` (ก่อน `const FindMajorResult`)
3. เพิ่ม `<ScoreExplanation />` ต่อท้าย `<p>{result.summary}</p>` ในกล่อง "สรุปจาก AI" (1 บรรทัด)

ไม่มี `launch.json`, ไม่มี config ชั่วคราว, ไม่มีงานค้างของคนอื่นใน working copy, ไม่แตะ `api/`, `vite.config.js`, `package.json` หรือหน้าอื่น

เนื้อหา component (ย่อ)

```jsx
const ScoreExplanation = () => {
  const [open, setOpen] = useState(false)
  const panelId = 'score-explanation-panel'
  return (
    <div className="mt-3 border-t border-gray-100 pt-3">
      <button type="button" onClick={() => setOpen((v) => !v)}
        aria-expanded={open} aria-controls={panelId}
        className="inline-flex items-center gap-1.5 rounded-md text-sm font-medium text-pnru hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-pnru/40">
        <Info className="w-4 h-4 shrink-0" aria-hidden="true" />
        เปอร์เซ็นต์คำนวณอย่างไร?
        <ChevronDown className={`w-4 h-4 shrink-0 transition-transform ${open ? 'rotate-180' : ''}`} aria-hidden="true" />
      </button>
      <div id={panelId} role="region" aria-label="เปอร์เซ็นต์คำนวณอย่างไร" hidden={!open}
        className="mt-3 rounded-lg bg-[#E8F5F1] p-4 text-sm text-gray-700 leading-relaxed space-y-2">
        {/* ข้อความอธิบาย + หมายเหตุ */}
      </div>
    </div>
  )
}
```

## 5. วิธี validate หลัง apply

1. `npm run build` ต้องผ่าน (ปัจจุบันมีคำเตือน chunk > 500 kB อยู่แล้วเป็นปกติ)
2. เทียบ bundle กับของเดิม: JS ต้องต่างเฉพาะ `ScoreExplanation` และบรรทัด render · CSS ต้องเพิ่มแค่ `.rotate-180`, `.rounded-md`, `.pt-3`, `.focus-visible:ring-2`, `.focus-visible:ring-pnru/40`
3. เปิดหน้า `/find-major/result` แล้วตรวจ
   - ปุ่มอยู่ใต้ข้อความในกล่อง "สรุปจาก AI"
   - กดแล้วเปิด/ปิดได้ `aria-expanded` เปลี่ยนตาม และ panel ใช้ `hidden`
   - Tab ไปที่ปุ่มได้ มีขอบโฟกัสสีเขียว กด Enter หรือ Space ทำงาน (เป็น `<button>` ปกติ)
   - ที่ความกว้าง 375px ไม่มี scroll แนวนอน
   - การ์ดผลลัพธ์และเปอร์เซ็นต์แสดงเหมือนเดิม console ไม่มี error
4. ไม่ต้องแก้หลังบ้าน ข้อความไม่ได้ผูกกับ API ใด

## 6. คำเตือนสำคัญ

**ตอนนี้ production frontend ไม่ได้ build จาก GitHub** แต่ build จาก working copy ในเครื่องซึ่งมีงานที่ยังไม่ commit จำนวนมาก (47 รายการ รวมไฟล์ untracked อย่าง `api/`, `src/lib/`, `src/pages/FindMajorResult.jsx`) ยืนยันได้จาก

- ไฟล์ใน `web/` บนเซิร์ฟเวอร์ตรงกับ `dist/` ในเครื่องทุกไบต์
- build ซ้ำจาก working copy (โดยใช้ไฟล์ก่อนแก้) ได้ JS SHA-256 ตรงกับ bundle บน production ทุกไบต์
- ข้อความที่มีเฉพาะใน working copy อยู่ใน bundle production ครบ ส่วนข้อความที่มีเฉพาะบน GitHub เช่น `X-RAG-Sources` ไม่อยู่ใน bundle

ผลที่ตามมา
- ถ้ามีใคร build จาก `main` บน GitHub แล้ว deploy จะได้เว็บคนละตัวกับที่ใช้อยู่ เช่น `api/recommend-major.js` บน GitHub ยังเรียกโมเดลผ่าน OpenRouter เอง ไม่ได้เรียกหลังบ้านของระบบนี้
- ถ้าเครื่องที่ถือ working copy เสียหาย จะสร้าง production ขึ้นใหม่ไม่ได้
- `docs/NEXT_STEPS.md` เคยบันทึกเรื่องเดียวกันไว้แล้วสำหรับ `src/pages/ChatAdvisor.jsx`

**ข้อเสนอ:** นำ working copy ทั้งชุด (ไม่ใช่เฉพาะ patch นี้) กลับเข้า repo ที่ track ไว้ แล้วให้ build production มาจาก commit เสมอ งานนี้ใหญ่กว่า UI รอบนี้และเป็นของเจ้าของ repo จึงยังไม่ได้ทำให้

---

สรุปสิ่งที่ต้องทำต่อ: apply patch → commit → push ไปที่ `FoMake/Univercity` แล้วแจ้งกลับ เพื่อให้ source ที่ track ตรงกับสิ่งที่รันอยู่จริง
