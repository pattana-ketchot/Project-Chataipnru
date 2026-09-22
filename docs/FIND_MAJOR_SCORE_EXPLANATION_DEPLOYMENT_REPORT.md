# Find-Major Score Explanation — Frontend Deployment Report (Step A)

วันที่ deploy: 2026-09-17T18:03:29Z (UTC) = 2026-09-18 01:03 เวลาไทย
ขอบเขต: frontend static เท่านั้น (`~/course-advisor-system/web/`) · ไม่แตะ backend / postgres / ollama / caddy · ไม่ restart คอนเทนเนอร์ใด · ไม่มี DB write · ไม่มี API หรือ Gemini request · ไม่ commit · ไม่ push

---

## 1. ยืนยัน source-of-truth ก่อน deploy

| หลักฐาน | ผล |
|---|---|
| ไฟล์ต้นทางที่เปลี่ยนหลัง build ครั้งก่อน (2026-09-09 06:12 +07) | มีไฟล์เดียวคือ `src/pages/FindMajorResult.jsx` (แก้ 2026-09-18 00:45) ตรวจทั้ง tree ยกเว้น `node_modules`, `dist`, `.git` |
| **Reference build** จาก working copy เดิม (สลับ `FindMajorResult.jsx` เป็นสำเนาก่อนแก้ผ่าน vite plugin ใน memory ไม่แตะไฟล์ใน repo) | JS ที่ได้ SHA-256 `ea2c9ed9426dd5cc4c1c8729ee9f9c5bf39fae6a28da1753e5848ad835a7ca1a` **ตรงกับ bundle ที่รันบน production ทุกไบต์** |
| production `web/` ก่อน deploy | ตรงกับ `ProjectPnru/dist/` ทุกไฟล์ (ตรวจ SHA-256 ทั้งชุด) |

สรุป: working copy `D:\workspace\ProjectPnru\ProjectPnru` reproduce production ได้ทุกไบต์ จึงยืนยันว่าเป็น source ที่ใช้ build production frontend จริง

## 2. ตรวจว่ามีงานของคนอื่นติดขึ้นไปหรือไม่ — ไม่มี

**JS (เทียบ build แบบไม่ minify: reference vs ใหม่)** — ต่างกันทั้งหมด 47 บรรทัดเพิ่ม 1 บรรทัดแก้ ไม่มีบรรทัดถูกลบนอกจากบรรทัดที่ถูกแทน
- `const ScoreExplanation = () => {...}` ทั้ง component
- บรรทัดเดียวที่เพิ่มการ render: `jsx(ScoreExplanation, {})` ต่อท้าย `{result.summary}`
- ไม่มีการเปลี่ยนโค้ดของหน้าอื่น ไม่มี feature อื่นติดมา
- ไอคอน `Info` / `ChevronDown` มีอยู่ใน bundle เดิมแล้ว จึงไม่มีโค้ดไอคอนใหม่

**CSS** — เพิ่ม 5 rule ไม่มี rule ใดถูกลบหรือแก้ ทั้ง 5 มาจาก class ของ component ใหม่
`.rotate-180`, `.rounded-md`, `.pt-3`, `.focus-visible\:ring-2:focus-visible`, `.focus-visible\:ring-pnru\/40:focus-visible`

**ขนาดไฟล์** — JS 641,570 → 643,791 bytes (+2,221) · CSS 38,325 → 39,026 bytes (+701)

## 3. Backup ก่อน deploy

| รายการ | ค่า |
|---|---|
| ไฟล์ | `~/backups/web.before_score_explanation_20260917T182049Z.tar.gz` (5,870,310 bytes, 33 ไฟล์) |
| SHA-256 | `3371f1ce7dd9f6d64f0bf6fd2b61d14e0e017be97f0bb56a13d956ae4b408093` (`sha256sum -c` → OK) |
| manifest รายไฟล์ | `~/backups/web.before_score_explanation_20260917T182049Z.manifest` |

## 4. Deploy

```
cp -a /tmp/web_new/assets/. web/assets/     # หลังตรวจ sha256 ของ tarball ที่อัปโหลด
cp -a /tmp/web_new/index.html web/index.html
```
- ไม่ลบไฟล์ asset เดิม (`index-_o0WDEib.js`, `index-Dw228rEr.css`) เพื่อให้ผู้ใช้ที่ยังค้างหน้าเก่าโหลดต่อได้ ตอนนี้ `web/assets/` จึงมี bundle 4 ไฟล์
- `index.html` ชี้ไปที่ `assets/index-gw896RX9.js` และ `assets/index-BRkWBF7z.css`
- ไม่ต้อง restart caddy เพราะ mount เป็น `ro` และอ่านไฟล์จากดิสก์ทุกครั้ง · `index.html` ส่ง `Cache-Control: no-cache` อยู่แล้ว
- คอนเทนเนอร์ทั้งหมดมี uptime เดิม: backend (Up about an hour, จาก deploy backend รอบก่อน), caddy (8 days), frontend (13 days), postgres/ollama (4 weeks)

## 5. ตรวจหลัง deploy

**ที่เสิร์ฟจริง (static GET ไม่ใช่ API)**
- `GET /` → 200, `index.html` ชี้ bundle ใหม่
- `GET /assets/index-gw896RX9.js` → 200, SHA-256 `839328b8b4103d207873b2a906ed090ae870be816f588610427fea0b2296226b` ตรงกับไฟล์ที่ build ในเครื่อง
- `GET /find-major/result` → 200 (SPA fallback ทำงาน)
- ข้อความ `score-explanation-panel` พบใน bundle ที่เสิร์ฟจริง

**ในเบราว์เซอร์ (หน้า production)**

| ตรวจ | ผล |
|---|---|
| หน้า Result render | ปกติ ทั้งแถบขั้นตอน, หัวข้อ, กล่องสรุป, การ์ดผลลัพธ์ |
| ปุ่ม "เปอร์เซ็นต์คำนวณอย่างไร?" | แสดงใต้ข้อความในกล่อง "สรุปจาก AI" |
| เปิด/ปิด | กดครั้งแรก `aria-expanded` false → true และ panel แสดงข้อความครบ · กดซ้ำกลับเป็น false และ `hidden` |
| desktop (1024 กว้าง) | ปกติ ไม่มี scroll แนวนอน |
| mobile (375×812) | ปกติ ไม่มี scroll แนวนอน ข้อความขึ้นบรรทัดใหม่ถูกต้อง |
| การ์ดผลลัพธ์และ layout เดิม | ครบ ทั้งหัวข้อ "สาขาที่แนะนำสำหรับคุณ" และ "สาขาทางเลือกอื่นๆ" แสดงเปอร์เซ็นต์ 3 ใบตามปกติ |
| console | ไม่มี log หรือ error ใด ๆ |

**จำนวน request ที่ใช้ตรวจ**
- **API ของระบบเรา: 0 ครั้ง · Gemini: 0 ครั้ง** — หน้า Result ต้องเรียก `POST /api/recommend-major` จึงจะมีผลลัพธ์ให้ดู จึงแทนด้วยการ mock `window.fetch` เฉพาะ URL นั้นในเบราว์เซอร์ (นับได้ 1 ครั้งที่ถูกดักไว้ ไม่ออกจากเครื่อง) แล้วเข้าหน้าด้วย `history.pushState`
- request อื่นเป็นของหน้าเว็บตามปกติ: โหลด `index.html`, bundle และ Supabase อ่านรายชื่อสาขา (ฐานข้อมูลของทีมหน้าเว็บ ไม่ใช่ของระบบเรา)
- ตัวเลข 58/55/53 ที่เห็นในภาพเป็นข้อมูล mock สำหรับตรวจการแสดงผลเท่านั้น ไม่ใช่คะแนนจริง

## 6. Rollback (ยังไม่ได้ใช้)

```bash
cd ~/course-advisor-system
tar -xzf ~/backups/web.before_score_explanation_20260917T182049Z.tar.gz -C /tmp/webrestore_x --strip-components=0
cp -a /tmp/webrestore_x/web/index.html web/index.html     # index.html จะชี้กลับไป index-_o0WDEib.js ซึ่งยังอยู่ในเครื่อง
# ไม่ต้อง restart คอนเทนเนอร์ใด ๆ
```
ไฟล์ bundle เดิมยังอยู่ใน `web/assets/` ครบ การ rollback จึงเป็นการคืน `index.html` ไฟล์เดียว

## 7. สิ่งที่ยังค้าง

- production frontend ยัง build จาก working copy ที่ไม่ได้ commit ที่ไหน — รายละเอียดและ patch สำหรับเจ้าของ repo อยู่ใน `docs/FIND_MAJOR_SCORE_EXPLANATION_FRONTEND_HANDOFF.md`
- รายงานนี้และไฟล์ patch ยังไม่ commit

---

FIND-MAJOR SCORE EXPLANATION FRONTEND DEPLOYMENT: PASS
