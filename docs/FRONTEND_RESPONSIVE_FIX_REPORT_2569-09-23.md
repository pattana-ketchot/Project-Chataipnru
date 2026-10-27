# รายงานผลการแก้ Responsive — SCI Advisor Frontend

- **วันที่:** 23 กันยายน 2569
- **Branch:** `prep-step8` (LastProject) — **ยังไม่ commit ยังไม่ push ยังไม่ deploy**
- **อ้างอิง audit:** `FRONTEND_RESPONSIVE_AUDIT_2569-09-23.md`
- **Build:** `npm run build` ผ่าน ไม่มี error — `dist/assets/index-*.js` 644 kB (gzip 173 kB)
- **ขอบเขตที่แก้:** UI/UX และ responsive เท่านั้น
  ไม่แตะ FastAPI, RAG, Gemini, PostgreSQL, Supabase schema, API contract,
  scoring/recommendation logic, permission หรือ production config

---

## 1. ไฟล์ที่แก้ (22 ไฟล์ · +351 −149 บรรทัด)

| ไฟล์ | แก้เรื่อง | ข้อ |
|---|---|---|
| `src/index.css` | บังคับช่องกรอก ≥16px บนมือถือ, ล็อกสกรอลล์ตอนเปิดเมนู, ความสูงกล่องแชทแบบ `dvh`, scrollbar ของแถบแท็บ, ยกปุ่มแชทลอยพ้น home indicator | C3, M1, M4, M5, M7 |
| `src/pages/CompareResult.jsx` | ต่ำกว่า `md` เปลี่ยนตารางเป็นการ์ดเรียงลงมา, ปุ่มลบ 44×44, ลดความกว้างคอลัมน์, ปุ่ม action ≥44px | C1, C2, M8 |
| `src/pages/ChatAdvisor.jsx` | ใช้ `.chat-shell`, ลด padding บนมือถือ, ช่องพิมพ์ 16px/44px, ปุ่มส่ง 44×44, ซ่อนปุ่มเปล่าบนมือถือ, แก้ empty state ที่ถูกตัดหัว | M1, M2, M3 |
| `src/pages/CourseDetail.jsx` | แถบแท็บมีเงาบอกว่าเลื่อนได้ + scrollbar บาง | M4 |
| `src/components/Header.jsx` | ล็อก background scroll ตอนเปิดเมนู, hamburger 40→44 | M5, m3 |
| `src/pages/Admin/NewsForm.jsx` | `grid-cols-2` → `grid-cols-1 sm:grid-cols-2` | M6 |
| `src/components/Footer.jsx` | เผื่อที่ล่างให้ปุ่มแชทลอย, ลิงก์ footer 18→40px | M7, m2 |
| `src/components/ChatButton.jsx` | ระยะขอบบนมือถือ + safe-area | M7 |
| `src/pages/CompareCourses.jsx` | ปุ่มเลือก 32→44 (วงกลมยังเท่าเดิม), ลิงก์ ≥44px | m2 |
| `src/components/CourseCard.jsx`, `SciConnectCard.jsx`, `CourseCarousel.jsx`, `Hero.jsx` | ลิงก์/ปุ่ม/ลูกศรสไลด์ ≥44px | m1, m2 |
| `src/pages/AllCourses.jsx`, `FindMajor.jsx`, `FindMajorResult.jsx`, `SciConnectAll.jsx`, `SciConnectDetail.jsx` | ลิงก์/ปุ่มตัวเลือก ≥44px | m2, m4 |
| `src/pages/Admin/Login.jsx`, `components/admin/auth/{AdminAuthCard,AdminAuthInput,PasswordInput}.jsx` | ปุ่มดูรหัสผ่าน 36→44, checkbox row 44px, ลด padding การ์ด, ตัวอักษร 11→12px | m6, C3 |

---

## 2. ผลการทดสอบทุก viewport

ทดสอบด้วยการวัดค่าจาก DOM จริง (ไม่ได้ดูด้วยสายตาอย่างเดียว) ที่
**360 / 390 / 430 / 768 / 820 / 1024 / 1280**
หน้า: Home, Courses, Course Detail, Find Major, Find Major Result, Compare,
Compare Result, Chat, Sci Connect, News Detail, Careers, Admin Login

| ข้อตรวจ | ผล |
|---|---|
| เลื่อนซ้าย-ขวาโดยไม่จำเป็น (`scrollWidth − clientWidth`) | **0 ทุกหน้า ทุก viewport** |
| อิลิเมนต์ทะลุขอบจอ | **ไม่พบเลย** |
| ช่องกรอกที่ตัวอักษร <16px บนมือถือ | **0** (เดิม 19 ช่อง) |
| ตัวอักษร <12px | **0** (เดิมมี 1 จุดที่หน้า Admin Login) |
| ตารางกว้างเกินจอ | **ไม่มี** |
| รูปกว้างเกินจอ / โหลดไม่ขึ้น | **ไม่มี** |
| console error | **ไม่มี** (หลังแก้ข้อผิดพลาดในข้อ 4) |

### ค่าที่เปลี่ยนชัดเจน

| จุด | ก่อน | หลัง |
|---|---|---|
| ตาราง Compare @360 | ตาราง 760px คอลัมน์หัวข้อกิน 200px เหลือให้สาขา 160px | ไม่มีตาราง เป็นการ์ดเรียงลงมา เต็มความกว้าง |
| ตาราง Compare @768 | 760px ในกล่อง 753px → **ขอบขวาโดนตัด 7px** | 703px ในกล่อง 703px → **cutOff 0** |
| ปุ่มลบสาขา | 20×20 | 44×44 |
| ช่องพิมพ์แชท @360 | 198×42 @14px | **256×46 @16px** |
| ปุ่มส่งข้อความ | 32×32 | 44×44 |
| hamburger | 40×40 | 44×44 |
| ลิงก์ footer | 18px | 40px |
| แท็บ Course Detail @430 | ซ่อน 61px ไม่มีอะไรบอก | ซ่อน 61px + **มีเงาบอกที่ขอบ** + scrollbar บาง |

---

## 3. Functional regression — ผ่านทั้งหมด

| API | ผล |
|---|---|
| `POST /api/chat` | **200** ตอบเป็นข้อความจริง |
| `POST /api/recommend-major` | **200** 2.9s คืน `primary.courseId` + `matchScore` |
| `POST /api/compare-courses` | **200** 7.1s คืน `summary` + `courses[]` |
| `GET /api/course-facts` | **200** 1,217 bytes |
| `GET /api/sci-connect-news` | **200** 2,197 bytes (ผ่าน Node webapi) |
| `GET /api/documents/{id}/pdf` | **200** `cs66.pdf` 922,878 bytes |

> ระหว่างทดสอบเจอ 422 สองครั้ง — เกิดจากผมส่ง payload ผิดรูปเอง
> (`/api/chat` ต้องใช้ `messages` ไม่ใช่ `message`; `/api/recommend-major` ต้องมี `courses` ด้วย)
> ไม่ใช่ regression ของระบบ

---

## 4. ข้อผิดพลาดที่เกิดระหว่างทำ และการแก้

**หน้า Course Detail ขาวทั้งหน้า** — ผมวาง React hook (`useRef`/`useState`/`useCallback`/`useEffect`)
ของแถบแท็บไว้ **ใต้** `if (loading) return` ทำให้จำนวน hook ไม่เท่ากันในแต่ละรอบ render
เกิด React error #310 หน้าเลยว่างเปล่า

แย่กว่านั้นคือ **ตอนแรกผมอ่านผลตรวจผิด** — สคริปต์รายงาน `smallN: 0, breaks: []`
ซึ่งผมสรุปว่า "ไม่มีปัญหา" ทั้งที่ความจริงคือหน้าว่างจึงไม่มีอะไรให้วัด
เพิ่งจับได้ตอนถ่าย screenshot แล้วเห็นหน้าขาว

แก้โดยย้าย hook ทั้งหมดขึ้นไปเหนือ early return ทุกอัน ตอนนี้หน้าแสดงผลปกติ
และเงาบอกการเลื่อนของแท็บทำงาน (วัดได้ `hiddenPx: 61`, `fadeCues: 1`)

**บทเรียน:** ค่าที่ "สะอาดผิดปกติ" ต้องยืนยันด้วยภาพก่อน ไม่งั้นหน้าเสียจะดูเหมือนหน้าผ่าน

---

## 5. สิ่งที่ตัดสินใจไม่ทำ และเหตุผล

1. **ซ่อนปุ่มแนบไฟล์/อัดเสียงบนมือถือ** (`sm:hidden` → แสดงที่ ≥640px)
   ทั้งสองปุ่มเป็น `disabled` รอฟีเจอร์ ยังกดไม่ได้จริง
   ถ้าแสดงทั้งคู่ที่ขนาดนิ้ว 44px ช่องพิมพ์บนจอ 360px จะเหลือแค่ ~162px ซึ่งแคบกว่าเดิม
   **ถ้าไม่เห็นด้วย บอกได้ ย้อนกลับได้ด้วยการลบ `hidden sm:flex` สองที่**

2. **ลิงก์ footer หยุดที่ 40px ไม่ดันถึง 44px**
   ถ้าดันถึง 44 ความสูง footer บนมือถือจะเพิ่มอีก ~150px ต่อคอลัมน์ ซึ่งเปลี่ยนสัดส่วนดีไซน์

3. **เมนูเต็มยังโผล่ที่ 1280px (`xl`) เหมือนเดิม** — คอมเมนต์ในโค้ดระบุว่าตั้งใจ
   เพราะเมนูไทย 8 รายการวางไม่ลงถ้าแคบกว่านี้ ไม่ใช่ข้อบกพร่อง

4. **ตัว checkbox "จดจำฉัน" ยังเป็น 16×16** — เป็น native checkbox
   แต่ `<label>` ที่ครอบสูง 44px แล้ว พื้นที่กดจริงจึงได้ขนาดนิ้ว

---

## 6. สิ่งที่ยังยืนยันไม่ได้

1. **หน้า Admin ด้านใน** — `/admin/dashboard` เด้งกลับ `/admin/login`
   ผมไม่มีบัญชีผู้ดูแลและไม่กรอกรหัสผ่านแทนคุณ
   สิ่งที่แก้ไปแล้ว (C3 ทั้ง 17 ช่อง, M6 ฟอร์มข่าว) มาจากการอ่านซอร์สและแก้ที่ซอร์ส
   **ยังไม่ได้วัดจากหน้าจอจริง** — ถ้าต้องการให้ยืนยัน รบกวนล็อกอินค้างไว้แล้วบอกผม

2. **พฤติกรรม `100vh` / คีย์บอร์ดบนเครื่องจริง** — ตัวจำลอง viewport สร้างเงื่อนไขนี้ไม่ได้
   ผมเปลี่ยนไปใช้ `dvh` แล้ว (มี `100vh` เป็นทางถอย) แต่พิสูจน์ได้เฉพาะบนมือถือจริง

3. **แถว "อาชีพที่สามารถทำได้" ว่างในหน้า Compare** — เป็นเพราะ `careers` ใน Supabase
   ของสองสาขานั้นเป็น array ว่าง ไม่ใช่ปัญหา layout และเป็นแบบนี้มาก่อนแก้

---

## 7. สถานะ Git

```
branch: prep-step8
22 ไฟล์ modified (+351 −149), ยังไม่ commit
?? TECH_STACK.md (ไม่เกี่ยวกับงานนี้)
dist/ ถูก gitignore ไว้ ไม่เข้า commit
```

**ยังไม่ deploy production และยังไม่ push ไป repo ของเพื่อน ตามที่สั่งไว้**
