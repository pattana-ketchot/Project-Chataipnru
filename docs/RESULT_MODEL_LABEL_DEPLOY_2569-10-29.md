# ปิดงาน: แสดงชื่อรุ่นที่ใช้จริงในหน้าแนะนำสาขาและหน้าเปรียบเทียบ — merge + deploy แล้ว

**29 ต.ค. 2569** · เซิร์ฟเวอร์ `161.118.237.37` · `https://stpnru-advisor.duckdns.org`
· แผนที่ใช้คือข้อ 8 ของ [RESULT_MODEL_LABEL_2569-10-29.md](RESULT_MODEL_LABEL_2569-10-29.md)

| | |
|---|---|
| สถานะ | **ปล่อยแล้วทั้ง backend และหน้าเว็บ · ตรวจรับผ่านครบทุกข้อบนเว็บจริง** |
| ลำดับ | backend ก่อน แล้วหน้าเว็บ ตามแผน |
| rollback | พร้อมทั้งสองส่วน (ข้อ 6) |

---

## 1. commit

### backend — fast-forward `fb6cd7d..b9c5eb5` → `origin/mko-phase2`

| commit | |
|---|---|
| **`e0e0a2e`** | ส่งชื่อรุ่นที่เขียนข้อความจริงกลับไปกับผลของสองหน้านี้ (ตามที่สั่งให้รวม) |
| `e2f3180` | เอกสาร readiness |
| **`7c32fd4`** | แก้ตามรีวิว — บันทึกรุ่นที่ตอบสำเร็จในตัวเชื่อมต่อ Gemini เอง (ตามที่สั่งให้รวม) |
| `b9c5eb5` | เอกสารฉบับแก้ + แผน deploy |

ไฟล์ที่เปลี่ยนเทียบกับที่ deploy อยู่ก่อนหน้า: `llm/connector.py` · `llm/gemini.py` ·
`backend/app/services/llm_client.py` · `backend/app/api/routes/web_compat.py` ·
`backend/tests/test_result_model_label.py` และเอกสาร — **ไม่มีงานอื่นปน**

### หน้าเว็บ — `488a543` ใน `LastProject`

`src/components/EngineNote.jsx` (ใหม่) · `src/pages/FindMajorResult.jsx` ·
`src/pages/CompareResult.jsx` — สามไฟล์ ไม่มีอย่างอื่น

### สำรองก่อนปล่อย (push ขึ้น GitHub ยังไม่ได้)

`D:\workspace\lastproject-backup-2569-10-29.bundle` · 6,935,108 ไบต์ ·
`git bundle verify` = complete history · **ทดสอบ clone กลับมาจริง** ได้ head `488a543`
และ `EngineNote.jsx` sha256 ตรงกับต้นฉบับ

---

## 2. image

```
course-advisor-system-backend:model-label-2569-10-29
sha256:cc7d65e50d0704336600f65cd433639b4e8a459bd59a375eb73031aaf4cad096
```

ซ้อนบน `image-upload-2569-10-29` ทับ 5 ไฟล์ · **สองไฟล์แรกอยู่คนละพาธกับรอบก่อน ๆ**

```
4557b45b7fb9e14ff700e163bb0532ac49e26a7a9105a2040362813f6ca8c019  /app/llm/connector.py
0f1d8c7a2a406777a5fb4dd787320b19a561fc8a6942564dbdd07b634c060c0d  /app/llm/gemini.py
81b12fec9968216cbbe33183f89619af7f585b5a89f7ba95475337b3cb81ec07  /app/backend/app/services/llm_client.py
e0af726262eadf49174537fe4c6b0fe459976a5f069e13c334bc01ea7fd86f32  /app/backend/app/api/routes/web_compat.py
a73b3b11f5f17ee9c450ccd08f73022ad44198d15a7d188c623cbe6382b9b820  /app/backend/tests/test_result_model_label.py
```

| ด่าน | ผล |
|---|---|
| `sha256sum -c` ในอิมเมจก่อนสลับ | **OK ทั้ง 5 ไฟล์** (เทียบกับ blob ของ commit) |
| `sha256sum -c` ในคอนเทนเนอร์ที่รันจริงหลังสลับ | **OK ทั้ง 5 ไฟล์** |
| ชุดทดสอบในอิมเมจ (ฐาน `course_advisor_test`) | `test_result_model_label` **12 ข้อ OK** · `test_gemini_overload_fallback` 20 จุด · `test_local_fallback_gets_time` 12 ข้อ — exit 0 ทั้งสาม |
| dry-run ของ compose | แตะเฉพาะ `backend-1` |
| `StartedAt` | `2026-10-29T08:58:47Z` · `/api/health` 200 |

---

## 3. bundle หน้าเว็บ

build จาก worktree แยกที่ `488a543` (`D:\workspace\lastproject-rel-488a543`) ·
`git status` ว่าง — **งานค้าง `AiSettings.jsx` ไม่มีทางปนไปด้วย**

| | |
|---|---|
| ด่าน hash ก่อนอัปโหลด | `sha256sum -c` ผ่าน **19 / 19** |
| ไฟล์ที่วางใหม่ | `assets/index-BndauWSW.js` (`9f01f28b…`) · `assets/index-C5Md9iPm.css` (`9072f932…`) |
| ตรวจก่อนสลับ | ดึงทั้งสองไฟล์ผ่าน HTTPS มาเทียบ hash **ตรงทั้งคู่** |
| สลับ `index.html` ขั้นสุดท้าย | hash ที่คาด = ที่ได้ = `6692c8ba…` |
| หน้าแรกชี้ | `index-BndauWSW.js` · `index-C5Md9iPm.css` |
| bundle เดิมที่เก็บไว้ให้ rollback | `index-CByV8S-P.js` · `index-D9B7alIK.css` |

---

## 4. ผลตรวจรับบนเว็บจริง

### 4.1 ผ่าน API

```
POST /api/recommend-major   HTTP 200 · 9 วินาที
  engine = {"explanation": {"provider": "gemini", "model": "gemini-3.5-flash-lite"},
            "scoring": "embedding_and_rules"}

POST /api/compare-courses   HTTP 200 · 9 วินาที
  engine = {"explanation": {"provider": "gemini", "model": "gemini-3.5-flash-lite"},
            "scoring": null}
```

### 4.2 บนหน้าเว็บจริง (อ่านค่าจาก DOM ไม่ใช่จากภาพ)

| หน้า | bundle ที่โหลด | บรรทัดที่ขึ้น |
|---|---|---|
| ค้นหาสาขาที่เหมาะกับฉัน | `index-BndauWSW.js` | `คำอธิบายโดย Gemini · gemini-3.5-flash-lite` **และ** `คะแนนความเหมาะสมคำนวณจากความใกล้เคียงระหว่างคำตอบของคุณกับเนื้อหาในเอกสารหลักสูตร และเกณฑ์ของระบบ` |
| เปรียบเทียบสาขา | เดียวกัน | `คำอธิบายโดย Gemini · gemini-3.5-flash-lite` บรรทัดเดียว (หน้านี้ไม่มีคะแนน) |

**ชื่อรุ่นบนหน้าตรงกับที่หลังบ้านส่งมาจริง** — ยิง `/api/recommend-major` ซ้ำจากหน้านั้น
ด้วยคำตอบชุดเดียวกัน แล้วเทียบ: `engine.explanation.model = gemini-3.5-flash-lite`
ตรงกับข้อความบนหน้า (ตรวจด้วยการเทียบสตริง ไม่ใช่ดูด้วยตา)

### 4.3 กรณีที่ไม่ได้ใช้ข้อความของ AI — ต้องไม่ติดป้ายชื่อรุ่น

ทำได้จริงบน production โดยไม่ต้องจำลอง: ส่งคำตอบที่คณะไม่มีสาขารองรับ (สายกฎหมาย)
ทุกใบจึงได้ข้อความมาตรฐานของระบบแทนเหตุผลของโมเดล

```
POST /api/recommend-major (คำตอบสายกฎหมาย)   HTTP 200
  engine = {"explanation": null, "scoring": "embedding_and_rules"}
  เหตุผลอันดับ 1 = "เอกสารหลักสูตรของสาขานี้ไม่ได้ระบุข้อมูลที่เชื่อมโยงกับสิ่งที่คุณเลือกไว้โดยตรง"

หน้าเว็บจริงด้วยคำตอบชุดเดียวกัน แสดง:
  "ประมวลผลจากข้อมูลและเกณฑ์ของระบบ"
  "คะแนนความเหมาะสมคำนวณจากความใกล้เคียง…และเกณฑ์ของระบบ"
```

**ไม่มีชื่อรุ่นใดถูกติดป้ายในกรณีนี้** ตรงตามที่สั่ง · และคำอธิบายของ AI ถูกแยกออกจาก
คะแนนของระบบเป็นคนละบรรทัดเสมอ

---

## 5. ค่าที่ต้องคงไว้ — ตรวจหลัง deploy แล้วเหมือนเดิมทุกค่า

| | ค่าที่อ่านได้ |
|---|---|
| `LLM_PROVIDER` / `GEMINI_MODEL` | `gemini` / `gemini-3.5-flash-lite` (ไม่แตะ) |
| `GEMINI_FALLBACK_MODELS` | ไม่ได้ตั้งค่า = ใช้ลำดับเดิมในโค้ด (ไม่แตะ) |
| `PUBLIC_LOCAL_CHOICE` | ไม่ได้ตั้งค่า = ปิด (ไม่แตะ) |
| แถว `web.ai_settings` | `1 · provider NULL · gemini-3.1-flash-lite · updated_at 2026-08-25` (ไม่แตะ) |
| การเลือกโมเดล / ลำดับรุ่นสำรอง | **ไม่มีบรรทัดใดเปลี่ยน** — รอบนี้เพิ่มแต่การรายงาน |
| migration / ค่าตั้งค่าใหม่ | ไม่มีทั้งคู่ |

---

## 6. rollback

**backend**

```bash
cd ~/course-advisor-system && docker compose \
  $(docker inspect -f '{{index .Config.Labels "com.docker.compose.project.config_files"}}' \
    course-advisor-system-backend-1 | tr ',' '\n' | grep -v model-label | sed 's#^#-f #' | tr '\n' ' ') \
  -f ~/release-model-label-2569-10-29/compose.rollback-backend-image-upload.yml \
  up -d --no-build --no-deps backend
```

**หน้าเว็บ**

```bash
cd ~/release-model-label-2569-10-29 && ./rollback_web.sh --run \
  ~/release-model-label-2569-10-29/web-run-20261029-090044
```

ย้อนฝั่งเดียวได้ทั้งคู่ · กรณี "backend เก่า + หน้าเว็บใหม่" หน้าเว็บจะไม่เห็นช่อง `engine`
แล้วไม่แสดงบรรทัดนั้น (ทดสอบไว้แล้วก่อน deploy) · กรณี "backend ใหม่ + หน้าเว็บเก่า"
หลังบ้านก็แค่ส่งช่องที่ไม่มีใครอ่าน

---

## 7. ของที่เก็บไว้บนเซิร์ฟเวอร์

`~/release-model-label-2569-10-29/` — `Dockerfile` · `SHA256SUMS` (พาธจริงในอิมเมจ) ·
`compose.pin-backend-model-label.yml` · `compose.rollback-backend-image-upload.yml` ·
`compose-args-used.txt` · `deploy_web.sh` · `rollback_web.sh` · `web-release/` ·
`web-run-20261029-090044/`

อิมเมจเดิม `image-upload-2569-10-29` ยังอยู่ครบสำหรับ rollback · ลบ tar ที่อัปโหลดและ
ไฟล์ชั่วคราวใน `/tmp` แล้ว

---

## 8. ที่ยังไม่ได้ทำ

* หน้าแชทไม่ได้แตะ — การบันทึกรุ่นทำกับเส้นทาง `chat()` ยังไม่รวม `chat_stream()`
  ที่หน้าแชทใช้ (หน้านั้นมีหลักฐานของตัวเองจาก log และ `corpus_version` ของแคชอยู่แล้ว)
* สองหน้านี้ยังไม่มีปุ่มเลือกโมเดล — รอบนี้เพิ่มการแสดงข้อมูลอย่างเดียวตามที่สั่ง
* commit หน้าเว็บยัง push ขึ้น GitHub ไม่ได้ (`FoMake/Univercity` · บัญชีในเครื่องไม่มีสิทธิ์)
  มี git bundle สำรองไว้แล้ว และยังไม่มีสำเนานอกเครื่อง
* ขั้นตรวจรับการอัปโหลดรูปฝั่งผู้ดูแลของ release ก่อนหน้า — **ตรวจผ่านแล้ว** (29 ต.ค. 2569)
