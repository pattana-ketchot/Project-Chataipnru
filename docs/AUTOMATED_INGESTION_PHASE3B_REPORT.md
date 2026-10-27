# Phase 3B — Admin Review UI

| | |
|---|---|
| วันที่ | 28 กันยายน 2569 |
| ฐาน | `mko-phase2` ที่ `787f1437b78a4b2d9da506fe393a555ce6b2cd19` |
| อ้างอิง | [AUTOMATED_INGESTION_PHASE3A_REPORT.md](docs/AUTOMATED_INGESTION_PHASE3A_REPORT.md) · [AUTOMATED_INGESTION_PHASE3_DESIGN.md](docs/AUTOMATED_INGESTION_PHASE3_DESIGN.md) |
| สถานะ | **เขียนเสร็จ · เทสต์ 33/33 ผ่าน · build production ผ่าน · ยังไม่ commit / push** |
| ไม่ได้ทำ | `pipeline.ingest` · ingest-worker · chunking · embedding · เขียน `course_documents`/`course_chunks` · แตะ RAG/Gemini/Supabase/Caddy · scheduler · notification · analytics · deploy/migration/restart production · merge main |

**ไฟล์ที่แก้นอก `frontend/` ในรอบนี้: 0 ไฟล์** — ยืนยันจาก `git status`
Phase 3B ไม่ได้แตะ backend, pipeline, migration หรือ schema เลยแม้บรรทัดเดียว

---

## 1. Architecture ที่ตรวจพบ

### frontend

| เรื่อง | ที่พบ |
|---|---|
| framework | Next.js 15.5 App Router · React 19 · TypeScript · Tailwind |
| routing | `frontend/app/` — `/` (หน้าเดียวสลับด้วย state), `/match`, `/compare`, `/api/[...path]` |
| ตัวส่งต่อ API | `app/api/[...path]/route.ts` ส่ง `/api/*` ไป backend และ**ส่งต่อ header `authorization` ให้แล้ว** |
| API client | `lib/api.ts` — `apiFetch(path, init, token)` แนบ `Bearer` ให้เอง มี `ApiError` พร้อม `status` |
| คลาส UI | `globals.css` — `panel`, `field`, `label`, `btn-primary`, `btn-secondary` · สี `ink`/`cream`/`sage`/`lime`/`coral` |
| แถบเมนู | `components/site-nav.tsx` รับ `active`, `onNavigate`, `right` |
| เทสต์ | vitest + @testing-library/react + jsdom · 3 ไฟล์ 8 ข้อ (baseline ผ่านทั้งหมด) |

### authentication ที่มีอยู่จริง — มีสองแบบ และเลือกใช้แบบเดียว

| แบบ | ที่ไหน | ใช้ในหน้านี้ไหม |
|---|---|---|
| ล็อกอินจริง เก็บ token ใน `localStorage["course_advisor_token"]` แล้วเรียก `api.me()` | `app/page.tsx` | ✅ **ใช้แบบนี้** |
| สมัครบัญชีชั่วคราวให้อัตโนมัติด้วยอีเมลสุ่ม | `app/match/page.tsx`, `app/compare/page.tsx` | ❌ **ตั้งใจไม่ใช้** |

แบบที่สองเป็นทางลัดของหน้าทดสอบ (คอมเมนต์ในโค้ดบอกไว้ตรง ๆ) บัญชีที่สมัครเองมี
`is_admin = false` จึงใช้กับหน้านี้ไม่ได้อยู่แล้ว และการสมัครบัญชีอัตโนมัติในหน้า
ของผู้ดูแลเป็นแบบแผนที่ไม่ควรลอก

### ไม่มีอะไรขัดกับ Phase 3A report

ตรวจแล้วว่า endpoint ทั้ง 6 เส้นทาง รูปแบบ request/response รหัสสถานะ และการที่
`staging_path` ไม่อยู่ใน response — ตรงกับที่ Phase 3A รายงานไว้ทุกข้อ

**แต่พบเรื่องที่ Phase 3A ยังไม่ได้คิดถึง 2 ข้อ** ซึ่งกระทบการทำ UI โดยตรง (หัวข้อ 2 และ 4)

---

## 2. ⚠️ เรื่องที่ Phase 3A ยังไม่ได้คิดถึง — เปิด PDF ในแท็บใหม่ทำไม่ได้

แบบใน Phase 3 Design เขียนว่า *"เปิด PDF ในแท็บใหม่ ไม่ใช่ iframe"*

**แต่ `GET /crawl-review/{id}/pdf` ต้องมี header `Authorization: Bearer …`**
ซึ่ง `window.open()` และ `<iframe src>` ส่งไปไม่ได้ทั้งคู่ — ทั้งสองทางจะได้ 401

ทางแก้ที่เลือก: ดึงไฟล์ด้วย `fetch` ที่แนบ token แล้วทำเป็น `blob:` URL เปิดแทน

```ts
const res = await fetch(pdfPath(id), { headers: { Authorization: `Bearer ${token}` } });
const url = URL.createObjectURL(await res.blob());
window.open(url, "_blank");
window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
```

**ผลที่ยอมรับ**

- ไฟล์ถูกโหลดเข้าหน่วยความจำของเบราว์เซอร์ทั้งก้อน (เพดาน 50 MB จาก crawler)
- ตัวอ่าน PDF ขอเฉพาะช่วงไบต์ (`Range`) ไม่ได้ จึงต้องรอโหลดครบก่อนจะเห็นหน้าแรก
- ถ้าเบราว์เซอร์ปิดกั้นแท็บใหม่ หน้าเว็บแจ้งให้อนุญาตแล้วลองอีกครั้ง

รับได้เพราะเป็นเครื่องมือภายในของผู้ดูแล ไม่ใช่หน้าสาธารณะ
ทางเลือกที่ดีกว่า (URL ชั่วคราวที่เซ็นแล้ว) ต้องแก้ backend จึงอยู่นอกขอบเขตรอบนี้ —
บันทึกไว้ให้ Phase 3C

---

## 3. UI ที่สร้าง

`frontend/app/crawl-review/page.tsx` — 356 บรรทัด · เส้นทาง `/crawl-review`

**ไม่ได้เพิ่มลงในแถบเมนูสาธารณะ** (`components/site-nav.tsx` ไม่ถูกแก้) เพราะเป็น
เครื่องมือภายใน ไม่ควรมีลิงก์ชวนให้คนทั่วไปกดเข้าไปเจอหน้า "ไม่มีสิทธิ์"

### สิ่งที่แสดง

| ที่กำหนด | แสดงเป็นอะไร |
|---|---|
| จำนวนรายการรอตรวจ | แถบตัวนับ 4 ช่อง: รอตรวจทั้งหมด · ต้องให้คนดู · จับคู่ไม่ชัด · มีไฟล์ให้เปิดดู |
| source / page URL | `source_url` แบบเต็ม (`break-all`) + ลิงก์ "หน้าที่พบลิงก์นี้" ไปที่ `page_url` (`rel="noreferrer noopener"`) |
| course label ที่ crawler จับได้ | `course_label` + `course_code` ในวงเล็บ หรือ "ระบุไม่ได้" |
| match confidence | ป้ายสี — `high` = ตรงชัดเจน · `medium` = ค่อนข้างตรง · `ambiguous`/`unknown` = ต้องเลือกเอง (ป้ายสีเตือน) |
| review reason | `review_reason` เต็มบรรทัด |
| SHA / ข้อมูลไฟล์ | `file_sha256` 16 ตัวแรก + `…` · `previous_sha256` ถ้ามี · ขนาดไฟล์แปลงเป็น KB/MB · `last_checked_at` เป็นเวลาไทย |
| มี staged PDF หรือไม่ | ปุ่มเปลี่ยนเป็น "ไม่มีไฟล์" และถูกปิด + ข้อความอธิบายว่าอนุมัติไม่ได้ |
| ปุ่มเปิด PDF | "เปิดไฟล์" |
| สถานะ | ป้าย `status` (สีแดงถ้า `error`) และป้าย "ต้องให้คนดู" |

แสดงเฉพาะฟิลด์ที่ backend ส่งมา ไม่คำนวณสถานะเองในเบราว์เซอร์

### responsive

`max-w-5xl` + `px-5` · ตัวนับ `grid-cols-2 md:grid-cols-4` · รายละเอียด `md:grid-cols-2` ·
ปุ่มและป้าย `flex-wrap` ทุกแถว · URL ยาวใช้ `break-all` ไม่ล้นจอ · ใช้ได้ตั้งแต่ความกว้าง
ระดับมือถือขึ้นไปโดยไม่มีการเลื่อนแนวนอน

---

## 4. ⚠️ Course selection — endpoint ที่ต้องใช้มีอยู่แล้ว ไม่ได้เพิ่มใหม่

Phase 3A บันทึกไว้เป็นข้อจำกัดว่า `match_candidates` เป็น**ชื่อ**หลักสูตร ไม่ใช่ `course_code`
ส่วน `POST /approve` ต้องการ `course_code`

**ตรวจแล้วพบว่ามี endpoint ที่ใช้ได้อยู่แล้ว** จึง reuse ตามที่สั่ง — **ไม่ได้เพิ่ม endpoint ใด**

```
GET /courses   →  lib/api.ts :: api.courses()  →  Course[] { id, code, title, … }
```

เส้นทางนี้อ่านอย่างเดียว (`routes/courses.py` มีแต่ `GET`) และหน้าแรกใช้อยู่แล้วในมุม
"สำรวจหลักสูตร"

### ขั้นตอนที่ผู้ดูแลทำ

```
ambiguous / unknown / ไม่มี course_code
        ↓
ปุ่มอนุมัติถูกปิด + ข้อความ "ต้องเลือกหลักสูตรก่อนจึงจะกดอนุมัติได้"
        ↓
<select> รายการหลักสูตรที่มีอยู่จริงใน PostgreSQL (value = course_code)
ข้อความประกอบ: "ระบบเดาได้หลายชื่อ: … — เลือกให้ตรงกับที่เปิดดูในไฟล์"
        ↓
เลือกแล้วปุ่มอนุมัติจึงเปิด
```

- `match_candidates` แสดงเป็น**ข้อมูลประกอบให้คนอ่าน** ไม่ใช่ตัวเลือกที่กดอนุมัติได้เอง
  ไม่มีการ fuzzy map ชื่อ → รหัสแล้วอนุมัติให้อัตโนมัติที่ใดเลย
- หลักสูตรที่ `code` เป็น `null` ถูกคัดออกจากรายการ เพราะอนุมัติด้วยรหัสว่างไม่ได้
- ไม่มีที่ใดในหน้านี้เรียก `POST/PUT/DELETE /courses` — มีข้อทดสอบยืนยัน

---

## 5. Authentication / Authorization

### backend เป็นผู้ตัดสิน หน้าเว็บไม่ตัดสินเลย

ตรวจพบว่า **`UserOut` ของ `/users/me` ไม่มีฟิลด์ `is_admin`** จึงเลือกไม่เพิ่มเข้าไป
เพราะการให้หน้าเว็บตัดสินเองว่าใครเป็นผู้ดูแลไม่มีประโยชน์ด้านความปลอดภัยเลย —
คนที่แก้ค่าในเบราว์เซอร์ก็ยังยิง API ไม่ผ่านอยู่ดี

หน้านี้จึง**ยิงคำขอไปแล้วแปลคำตอบ**

| คำตอบจาก backend | หน้าเว็บทำอะไร |
|---|---|
| `200` | แสดงคิว |
| `401` | ลบ token ออกจาก `localStorage` แล้วกลับไปหน้าเข้าสู่ระบบ |
| `403` | แสดงหน้า "ไม่มีสิทธิ์เข้าถึง" พร้อมปุ่มเข้าสู่ระบบด้วยบัญชีอื่น · ไม่มีปุ่มตัดสินใจโผล่มาเลย |

ผลพลอยได้: ไม่ต้องแก้ backend แม้แต่บรรทัดเดียวเพื่อทำ authorization ของหน้านี้

### `decided_by`

ไม่มีฟิลด์นี้ใน `lib/crawl-review.ts` และไม่มีที่ใดในหน้าส่งค่านี้ออกไป
backend ใช้อีเมลจาก JWT เหมือน Phase 3A มีข้อทดสอบตรวจ body ของทุกคำขอว่าไม่มีคีย์
`decided_by`, `staging_path` หรือ `path`

---

## 6. Approve / Ignore / Undo flow

ทั้งสามการกระทำมี**ขั้นยืนยันในหน้าเดียวกัน** ไม่ใช้ `window.confirm`
(ทั้งเพราะ UX ดีกว่า และเพราะ jsdom ไม่รองรับจึงทดสอบไม่ได้)

```
กดปุ่ม → แผงยืนยันเปิดขึ้นในการ์ดเดิม → กด "ยืนยัน" จึงส่งคำขอ
                                       → กด "ยกเลิก" ไม่ส่งอะไรเลย
```

| การกระทำ | ส่งอะไร | ข้อความเมื่อสำเร็จ |
|---|---|---|
| Approve | `{ file_sha256, course_code }` | "อนุมัติแล้ว — ผูกกับ *ชื่อหลักสูตร* · **ยังไม่นำเข้าคลังความรู้จนกว่าจะรันตัวนำเข้า**" |
| Ignore | `{ file_sha256, reason }` | "บันทึกว่าไม่เกี่ยวข้องแล้ว รายการออกจากคิว" |
| Undo | `{ file_sha256 }` | "ถอนการตัดสินใจแล้ว รายการกลับเข้าคิว" |

แผงยืนยันของ Approve บอกชื่อหลักสูตรที่จะผูก และย้ำว่ายังไม่มีอะไรเข้าคลังความรู้
แผงยืนยันของ Ignore มีช่องกรอกเหตุผล

**โหลดคิวใหม่ทุกครั้งหลังตัดสินใจ** ไม่ลบแถวออกจากหน้าจอเอง เพื่อให้สิ่งที่เห็นเป็น
สถานะจริงจากเซิร์ฟเวอร์ ไม่ใช่สิ่งที่หน้าเว็บเดาว่าน่าจะเป็น

### optimistic locking

`file_sha256` ที่แสดงบนหน้าจอถูกส่งกลับไปทุกคำขอที่ตัดสินใจ
เมื่อ backend ตอบ **409**

- **ไม่ส่งซ้ำอัตโนมัติ** (มีข้อทดสอบนับจำนวนคำขอยืนยันว่าเรียกครั้งเดียว)
- แสดงข้อความของ backend + "โหลดคิวใหม่ให้แล้ว **กรุณาเปิดไฟล์ตรวจอีกครั้งก่อนตัดสินใจ**"
- โหลดคิวใหม่ให้ทันทีเพื่อให้ผู้ดูแลเห็น `sha` ใหม่

ครอบทั้ง 409 จาก sha ล้าสมัยและ 409 จาก "มีการตัดสินใจอยู่แล้ว" ด้วยเส้นทางเดียวกัน

---

## 7. Error handling / UX ที่ทำครบ

| สถานะ | ที่ทำ |
|---|---|
| Loading | `role="status"` "กำลังตรวจสอบสิทธิ์…" / "กำลังโหลดคิว…" + ไอคอนหมุนบนปุ่มโหลดใหม่ |
| Empty queue | "ไม่มีรายการรอตรวจ — ระบบตรวจเว็บคณะแล้วไม่พบเอกสารใหม่หรือเอกสารที่เปลี่ยนแปลง" |
| API error | `role="alert"` แสดง `detail` จาก backend |
| Unauthorized (401) | ลบ token แล้วกลับไปหน้าเข้าสู่ระบบ |
| Forbidden (403) | หน้าเต็มบอกว่าไม่มีสิทธิ์ + ปุ่มเปลี่ยนบัญชี |
| Approve confirmation | แผงยืนยันบอกหลักสูตรที่จะผูก |
| Ignore confirmation | แผงยืนยัน + ช่องเหตุผล |
| Success feedback | แถบสีเขียว `role="status"` พร้อมไอคอน |
| stale file (409) | แถบสีเหลืองเตือน + โหลดคิวใหม่ + ห้าม retry |
| PDF unavailable | "เปิดไฟล์ไม่ได้ — ไฟล์อาจไม่อยู่ในที่เก็บแล้ว เนื้อไฟล์ไม่ตรงกับที่บันทึกไว้ หรือไม่ใช่ PDF" |
| แท็บใหม่ถูกปิดกั้น | แถบเตือนให้อนุญาตแล้วลองอีกครั้ง |
| 429 | "ส่งคำขอบ่อยเกินไป กรุณารอสักครู่" |
| responsive | ดูหัวข้อ 3 |

ข้อความผิดพลาดใช้ `detail` ที่ backend ส่งมา ซึ่ง Phase 3A ออกแบบให้ไม่มีที่อยู่ไฟล์อยู่แล้ว

---

## 8. Security

| ที่ต้องตรวจ | ผล | พิสูจน์ด้วย |
|---|---|---|
| ไม่มี `staging_path` leak | ✅ ไม่มีในชนิดข้อมูล ไม่มีในหน้าจอ | ข้อทดสอบตรวจ `container.innerHTML` ว่าไม่มี `staging_path`, `staging/`, `/srv/`, `/tmp/`, `C:\`, `.part_` |
| ไม่มี secret ใน frontend bundle | ✅ | ไม่มี `NEXT_PUBLIC_*` ใหม่ · ไม่มีค่าคงที่ที่เป็นความลับ · token มาจากการล็อกอินของผู้ใช้เท่านั้น |
| ไม่มี DB credentials | ✅ | หน้าเว็บไม่รู้จักฐานข้อมูลเลย คุยผ่าน HTTP เท่านั้น |
| ไม่มี production password | ✅ | ไม่มีค่าใดฝังไว้ |
| frontend bypass `require_admin` ไม่ได้ | ✅ | หน้าเว็บไม่ได้ตัดสินสิทธิ์เลย (หัวข้อ 5) ทุกเส้นทางผ่าน `require_admin` ที่ backend |
| URL/path จากผู้ใช้ไม่ถูกเปิดเป็นไฟล์ในเครื่อง | ✅ | เรียก PDF ด้วย `id` เท่านั้น ไม่มีที่ใดประกอบ path — ข้อทดสอบยืนยันว่า URL ที่ยิงคือ `/crawl-review/{id}/pdf` เป๊ะ |
| API error ไม่ leak path | ✅ | ตรวจข้อความ 404 ของทุกเคสว่าไม่มีที่อยู่ไฟล์ |
| ลิงก์ออกนอกเว็บ | ✅ | `page_url` ใช้ `rel="noreferrer noopener"` |
| `blob:` URL | ✅ | `revokeObjectURL` หลัง 60 วินาที ไม่ค้างในหน่วยความจำ |

---

## 9. Tests

### ใหม่: `frontend/test/crawl-review.test.tsx` — **25 ข้อ ผ่านทั้งหมด**

จำลองเฉพาะ `fetch` ระดับเครือข่าย ส่วนคอมโพเนนต์ สถานะ และ `lib/api.ts` เป็นของจริง
เก็บทุกคำขอไว้ตรวจ body และ header ที่ส่งออก ซึ่งดูจากหน้าจออย่างเดียวไม่ได้

| หมวด | ข้อ |
|---|---|
| สิทธิ์เข้าถึง | 5 |
| คิวและสถานะหน้าจอ | 5 |
| เปิดไฟล์ PDF | 3 |
| เลือกหลักสูตรและอนุมัติ | 6 |
| ไม่เกี่ยวข้องและถอนการตัดสินใจ | 2 |
| ความปลอดภัย | 4 |

### รายการที่สั่งให้ครอบ — ครอบครบ

| ที่สั่ง | ข้อทดสอบ |
|---|---|
| admin เปิด queue ได้ | `เข้าสู่ระบบสำเร็จแล้วเห็นคิว` · `ส่ง token ไปกับทุกคำขอของคิว` |
| non-admin เข้าไม่ได้ | `ผู้ใช้ที่ไม่ใช่ผู้ดูแล: backend ตอบ 403 แล้วหน้าเว็บบอกว่าไม่มีสิทธิ์` (+ ยืนยันว่าไม่มีปุ่มอนุมัติ) |
| unauthenticated เข้าไม่ได้ | `ยังไม่เข้าสู่ระบบ: ไม่เรียกคิวเลย` · `token หมดอายุ: ลบ token แล้วกลับไปหน้าเข้าสู่ระบบ` |
| empty queue | `คิวว่าง: บอกว่าไม่มีรายการรอตรวจ` |
| loading / error | `กำลังโหลด: แสดงสถานะให้เห็น` · `API พัง: แสดงข้อความผิดพลาด ไม่ใช่หน้าว่าง` |
| PDF open | `เปิดได้: ดึงไฟล์พร้อม token แล้วเปิดเป็น blob` |
| PDF unavailable | `เปิดไม่ได้ (404)` · `ไม่มีไฟล์ในคิว: ปุ่มถูกปิด` |
| existing course selection | `รายการกำกวม: …` ตรวจว่าตัวเลือกมาจาก `/courses` และตัวที่ไม่มีรหัสถูกคัดออก |
| ambiguous ต้องเลือก course | `กดอนุมัติไม่ได้จนกว่าจะเลือกหลักสูตร` |
| approve success | `อนุมัติสำเร็จ: ต้องยืนยันก่อน ส่ง sha กับรหัสหลักสูตร แล้วโหลดคิวใหม่` |
| ignore success | `บันทึกว่าไม่เกี่ยวข้อง: ต้องยืนยันและส่งเหตุผล` |
| duplicate decision | `ตัดสินใจซ้ำ (409)` |
| stale SHA 409 | `ไฟล์เปลี่ยนไปแล้ว (409): เตือน ไม่ส่งซ้ำอัตโนมัติ และโหลดคิวใหม่` |
| refresh หลัง decision | ตรวจในข้อ approve (นับจำนวนครั้งที่เรียก `/pending` = 2) และ `โหลดคิวใหม่: ยิงคำขอไปใหม่` |
| ไม่มี `staging_path` ใน UI/API | `ไม่มี staging_path หรือที่อยู่ไฟล์บนเซิร์ฟเวอร์ปรากฏในหน้าจอ` · `ไม่ส่ง staging_path, decided_by หรือ path ใด ๆ ออกไปกับคำขอ` |
| ไม่มี automatic course creation | `ไม่มีคำขอสร้างหลักสูตรใหม่เลย` |

เพิ่มนอกรายการ: `ยกเลิกการยืนยัน: ไม่ส่งคำขอ` · `หลักสูตรที่ไม่มีในระบบ (422)` ·
`ถอนการตัดสินใจ: ส่ง sha ปัจจุบัน` · `ไม่ประกอบที่อยู่ไฟล์เอง`

### Regression

| ชุด | ผล |
|---|---|
| `frontend` ทั้งหมด (`programs`, `api`, `app.integration` + ชุดใหม่) | **33/33 ผ่าน** (baseline เดิม 8 ข้อยังผ่านครบ) |
| `npx tsc --noEmit` | ผ่าน ไม่มีข้อผิดพลาด |
| `npx next build` | ผ่าน · `/crawl-review` ขึ้นเป็น route ขนาด 6.98 kB · lint + type check ในตัว build ผ่าน |
| `eval/crawl_download_check.py` | **140/140 ผ่าน** |
| `eval/tuition_followup_check.py` | **14/14 OK** |
| `eval/recommendation_clarification_check.py` | **15/15 OK** |
| เส้นทาง Phase 3A ใน OpenAPI | 6 เส้นทาง `/crawl-review` ครบ · 27 เส้นทางรวม |

### ⚠️ ที่ไม่ได้รันซ้ำ

`eval/crawl_approval_check.py` (84 ข้อ) และ `eval/crawl_state_check.py` (32 ข้อ)
ต้องมี PostgreSQL ที่ลง migration 003+004 ซึ่งฐานข้อมูลทดสอบถูกลบไปหลัง Phase 3A แล้ว

**เหตุที่ไม่สร้างใหม่เพื่อรันซ้ำ**: Phase 3B ไม่ได้แก้ไฟล์ใดนอก `frontend/` เลย —
ยืนยันจาก `git status` ว่าไฟล์ที่แก้นอก `frontend/` = 0 ไฟล์ พฤติกรรมของ backend
ที่สองชุดนั้นตรวจจึงเปลี่ยนไม่ได้ และการสร้างฐานข้อมูลทดสอบต้องไปแตะ instance เดียวกับ
production ซึ่งไม่คุ้มกับผลที่รู้อยู่แล้ว

ถ้าต้องการยืนยันด้วยตา ให้รันซ้ำตามขั้นตอนใน
[AUTOMATED_INGESTION_PHASE3A_REPORT.md](docs/AUTOMATED_INGESTION_PHASE3A_REPORT.md) หัวข้อ 5

---

## 10. ไฟล์ที่เพิ่ม / แก้

### เพิ่มใหม่ 3 ไฟล์ — ทั้งหมดอยู่ใน `frontend/`

```
frontend/lib/crawl-review.ts            106 บรรทัด   ชนิดข้อมูล + ตัวเรียก API + ตัวช่วยแสดงผล
frontend/app/crawl-review/page.tsx      356 บรรทัด   หน้าคิวตรวจ
frontend/test/crawl-review.test.tsx     438 บรรทัด   เทสต์ 25 ข้อ
```

### แก้ของเดิม: **ไม่มี**

```
git status --porcelain --untracked-files=no   →  ว่าง
ไฟล์ที่แก้นอก frontend/                        →  0
```

ไม่แก้ `lib/api.ts` · ไม่แก้ `components/site-nav.tsx` · ไม่แก้ `app/page.tsx` ·
ไม่แก้ `backend/` · ไม่แก้ `pipeline/` · ไม่แก้ `db/` · ไม่แก้ `package.json`

ผลพลอยได้จากการ build (`frontend/.next`, `frontend/node_modules`, `frontend/.vitest-cache`)
ตรวจแล้วว่าถูก `gitignore` ครบทั้งสามรายการ

> หมายเหตุ: ระหว่างตรวจ ผมแก้ `.claude/launch.json` ชั่วคราวเพื่อลองเปิด dev server
> ของ worktree นี้ (ดูหัวข้อ 11) และ **คืนค่าเดิมแล้ว** — `git diff` ของไฟล์นั้นว่าง

---

## 11. Known limitations

| ข้อจำกัด | ผล | ทางแก้ |
|---|---|---|
| **เปิด PDF ต้องโหลดไฟล์ทั้งก้อนเข้าหน่วยความจำ** (หัวข้อ 2) | ไฟล์หลายสิบเมกะไบต์ต้องรอโหลดครบก่อนเห็นหน้าแรก · ไม่มี `Range` | 3C — เพิ่ม endpoint ที่ออก URL ชั่วคราวที่เซ็นแล้ว |
| **ตรวจด้วยเบราว์เซอร์จริงไม่ได้ในรอบนี้** | `.claude/launch.json` ใช้ `npm run dev --prefix frontend` แต่ `npm --prefix` **ไม่เปลี่ยน cwd ของสคริปต์** `next dev` จึงอ่าน app จาก checkout หลักเสมอ ไม่ใช่ worktree นี้ (`/crawl-review` ตอบ 404) | ตรวจด้วย `npx next build` (ผ่าน) และเทสต์ 25 ข้อที่ render คอมโพเนนต์จริงแทน · ถ้าอยากดูด้วยตา: `cd frontend && npm run dev` แล้วเปิด `/crawl-review` |
| **หลักสูตรที่ `code` เป็น `null` เลือกไม่ได้** | อนุมัติเอกสารเข้าหลักสูตรนั้นไม่ได้ | 3C — ตั้งรหัสให้หลักสูตรนั้น หรือให้ approve รับ `course_id` ได้ |
| **`GET /courses` จำกัด 50 รายการต่อคำขอ** และไม่มีการค้นหา | ตอนนี้มี 24 หลักสูตรจึงพอ แต่ถ้าเกิน 50 รายการจะไม่ครบ | 3C — ใส่ `limit`/`offset` หรือช่องค้นหา |
| **`GET /courses` ไม่ต้องยืนยันตัวตน** (พฤติกรรมเดิมของระบบ ไม่ได้เกิดจากรอบนี้) | รายชื่อหลักสูตรเป็นข้อมูลสาธารณะอยู่แล้ว (หน้าแรกแสดงอยู่) | ไม่ต้องแก้ |
| **ไม่มีหน้าดูรายการที่ตัดสินใจไปแล้ว** | ถอนได้เฉพาะรายการที่ยังอยู่ในคิว ถ้าอนุมัติแล้วแถวหายจากคิวจะกดถอนจาก UI ไม่ได้ | 3C — ต้องมี endpoint ดูประวัติก่อน (เป็นข้อจำกัดที่ Phase 3A บันทึกไว้แล้ว) |
| **ปุ่ม "ถอนการตัดสินใจล่าสุด" มีประโยชน์จำกัด** | ใช้ได้เฉพาะเมื่อแถวยังอยู่ในคิวแต่มีการตัดสินใจที่ถูก supersede ไปแล้ว หรือเมื่อ backend ตอบ 409 ว่ามีการตัดสินใจอยู่ ซึ่งผู้ใช้จะกดถอนต่อได้ | ข้างบน |
| **แถวที่ `file_sha256` เป็น `null`** | ปุ่มทั้งสามถูกปิด (ตัดสินใจไม่ได้ตาม Phase 3A) | 3C ตามที่ Phase 3A บันทึก |
| **ไม่ได้เพิ่มลิงก์ในแถบเมนู** | ต้องพิมพ์ `/crawl-review` เอง | เจตนา — เป็นเครื่องมือภายใน |
| **ยังไม่ได้ deploy** | migration 004 ยังไม่ลง production · ยังไม่มีบัญชี admin · `CRAWL_STAGING_DIR` ยังไม่ได้ตั้ง จึงเปิด PDF บน production ไม่ได้ | รออนุมัติ deploy |

---

## 12. สิ่งที่ Phase 3C ต้องทำ

| # | งาน | หมายเหตุ |
|---|---|---|
| 1 | **ingest-worker** `pipeline/crawl/approve.py` | หา decision ที่ `approve` และยังไม่นำเข้า ด้วย `FOR UPDATE SKIP LOCKED` · ตรวจไฟล์ซ้ำ (root · sha256 · `%PDF-` · `fitz.open()`) · เรียก `pipeline.ingest.run()` ตัวเดิมไม่แก้ |
| 2 | อัปเดตสถานะหลังนำเข้า | `crawl_sources.status='ingested'` + `document_id` ด้วย role `advisor_ingest` · `crawl_decisions.ingest_*` |
| 3 | หา `document_id` หลัง `run()` | `run()` คืน `None` ต้อง `SELECT` ด้วย `file_sha256` |
| 4 | `EMBED_MODEL` / `EMBED_DIM` | ค่าเริ่มต้นของ `ingest.py` เป็น `nomic-embed-text` (768) แต่ production ใช้ `bge-m3` (1024) ต้องตรวจก่อน embed |
| 5 | คัดลอกไฟล์เข้า `documents/` หลังนำเข้าสำเร็จ + restart backend | ไม่งั้น `/documents/{id}/pdf` เปิดไม่ได้ (`document_store` ทำดัชนีครั้งเดียวต่อโปรเซส) |
| 6 | `ingest-worker` container ใน compose (`profiles: ["ingest"]`) | รันครั้งเดียวแล้วจบ ไม่ใช่บริการรันค้าง |
| 7 | endpoint ดูประวัติการตัดสินใจ | ปลดล็อกการถอนหลังแถวหลุดจากคิว และให้ UI แสดงสิ่งที่ตัดสินไปแล้ว |
| 8 | URL ชั่วคราวที่เซ็นแล้วสำหรับ PDF | แก้ข้อจำกัดเรื่องโหลดไฟล์ทั้งก้อน (หัวข้อ 2) |
| 9 | ค้นหา/แบ่งหน้าใน `GET /courses` | รองรับกรณีหลักสูตรเกิน 50 รายการ |
| 10 | deploy: migration 004 · ตั้งบัญชี admin · ย้าย staging ขึ้นเซิร์ฟเวอร์ + mount `:ro` · ตั้ง `CRAWL_STAGING_DIR` | ต้องขออนุมัติแยกทุกข้อ |

---

## 13. git diff และสถานะ repository

```
HEAD                787f143  feat: add crawler review and approval foundation
branch              mko-phase2  (ตรงกับ origin/mko-phase2 · ahead 0 / behind 0)
main                b78b3f8  ไม่ถูกแตะ

git status --porcelain --untracked-files=no      →  ว่าง (ไม่มีไฟล์ tracked ถูกแก้)
git diff                                         →  ว่าง

ไฟล์ใหม่ที่ยังไม่ commit
  ?? frontend/app/crawl-review/       (page.tsx)
  ?? frontend/lib/crawl-review.ts
  ?? frontend/test/crawl-review.test.tsx
```

production ไม่ถูกแตะ: ไม่มี migration 004 · ไม่ deploy · ไม่ restart · ไม่แก้ฐานข้อมูล ·
ไม่สร้างบัญชี admin · ไม่มี ingestion · ไม่มี embedding

**หยุดรอ review · ยังไม่ commit / push / deploy และยังไม่เริ่ม Phase 3C**
