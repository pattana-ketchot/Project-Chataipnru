# หน้าแนะนำสาขา/เปรียบเทียบหมุนรอ — สาเหตุ หลักฐาน และสิ่งที่แก้

**29 ต.ค. 2569** · ตรวจจาก log ของ production ช่วงเวลาเดียวกับที่ผู้ใช้เจอ
**ไม่ได้ยิงทดสอบซ้ำกับของจริง** · **ยังไม่ deploy**

---

## 1. สาเหตุ — แยกตามที่สั่ง

| ความเป็นไปได้ | ผล |
|---|---|
| รอ Gemini | **ใช่ บางส่วน** — Gemini ตอบ **503 ครบทั้งสี่รุ่น** ใน 12 วินาที แล้วถูกพักไว้รุ่นละ 60 วินาที |
| รอ embedding | **ไม่ใช่** — `ollama/api/embeddings` ตอบ 200 ทุกครั้ง ใช้เวลารวมไม่ถึง 2 วินาที |
| backend ผิดพลาด | **ไม่ใช่** — ไม่มี Traceback ไม่มี 5xx จากฝั่งเรา คำขอจบด้วย **200 OK** |
| frontend ไม่จบสถานะโหลด | **ใช่ ส่วนที่ผู้ใช้เห็น** — `fetch()` ไม่มีเพดานเวลา จึงรอจนกว่าคำขอจะจบเอง |
| เกี่ยวกับ release `model-label` | **ไม่เกี่ยว** — release นั้นแตะแค่การ "รายงานชื่อรุ่น" ไม่แตะการเลือกโมเดล การลองซ้ำ หรือเพดานเวลา · อาการนี้เกิดได้ตั้งแต่ก่อนหน้านั้น |

**ต้นเหตุที่แท้จริง**: สองเส้นทางนี้ **ไม่เคยตั้งเพดานเวลาของคำขอ** ต่างจาก `/chat-web`
ที่ตั้งไว้ตั้งแต่ต้น เมื่อ Gemini ล่มครบทุกรุ่น ระบบตกไปใช้โมเดลในเครื่อง (เซิร์ฟเวอร์
ไม่มีการ์ดจอ จึงช้ามาก) แล้ว `ollama /api/chat` ติด ReadTimeout **120 วินาที × 3 ครั้ง**
โดยไม่มีอะไรตัด — คำขอเดียวใช้เวลา **6 นาที 15 วินาที** และหน้าเว็บหมุนรอทั้งหมดนั้น

---

## 2. หลักฐานจาก log (คำขอล่าสุดของผู้ใช้)

```
09:29:01.300  POST /recommend-major เข้ามา (172.18.0.6:39098)
09:29:01.710  ollama /api/embeddings 200            ← embedding ปกติ
09:29:04.489  gemini-3.5-flash-lite  503 → พัก 60 วินาที
09:29:08.052  gemini-3.1-flash-lite  503 → พัก 60 วินาที
09:29:13.931  gemini-3.5-flash       503 → พัก 60 วินาที
09:29:16.411  gemini-3.6-flash       503 → พัก 60 วินาที
09:29:16.412  "เจ้าหลักตอบไม่ได้ … — ใช้โมเดลในเครื่องแทน"
09:31:16.470  ollama /api/chat attempt 1/3 failed: ReadTimeout
09:33:16.572  ollama /api/chat attempt 2/3 failed: ReadTimeout
09:35:16.612  ollama /api/chat attempt 3/3 failed: ReadTimeout
09:35:16.612  "เขียนเหตุผลไม่สำเร็จ (LLMConnectionError)"
09:35:16.615  POST /recommend-major → 200 OK        ← รวม 6 นาที 15 วินาที
```

คำขอ `/compare-courses` ที่เริ่ม 09:31:11 **สำเร็จใน 31 วินาที** เพราะตอนนั้น
`gemini-3.5-flash-lite` พ้นช่วงพัก 60 วินาทีแล้ว (`09:31:26-09:31:42` ตอบ 200 สี่ครั้ง)
— ยืนยันว่าไม่ใช่ปัญหาของโค้ดเส้นทางนี้ แต่เป็นจังหวะที่ผู้ให้บริการล่ม

---

## 3. สิ่งที่แก้ — สองจุด ตรงที่เป็นต้นเหตุ

### 3.1 backend: ตั้งเพดานเวลาให้สองเส้นทางนี้ (`2e49926`)

`backend/app/api/routes/web_compat.py` — ตัวงานเดิมไม่ถูกแตะเลย ย้ายไปเป็นฟังก์ชันภายใน
แล้วห่อด้วยตัวตั้งเพดานบาง ๆ

```python
RESULT_PAGE_BUDGET_S = 90.0

@router.post("/compare-courses", dependencies=[Depends(web_rate_limiter)])
def compare_courses_web(payload, db=Depends(get_db)) -> dict:
    budget = start_budget(RESULT_PAGE_BUDGET_S)
    try:
        return _compare_courses(payload, db)
    finally:
        reset_budget(budget)      # ล้างเสมอ ไม่งั้นเพดานค้างไปตัดงานถัดไป
```

มีเพดานแล้ว กลไกที่มีอยู่เดิมจะทำงานเอง — `http_timeout()` หดเวลาของทุกคำขอ HTTP
ให้ไม่เกินเวลาที่เหลือ และ `check_budget()` หยุดลองรุ่นถัดไปเมื่อหมดเวลา ·
`LLMBudgetExceeded` สืบทอดจาก `LLMConnectionError` ที่ endpoint ดักอยู่แล้ว ผู้ใช้จึงได้
**คำตอบที่จบ** แทนการรอ

> **แก้จากฉบับแรก** — ตรงนี้เคยเขียนว่า "ได้ 503 พร้อมข้อความบอกเหตุ" ซึ่งไม่ครบ ·
> วัดจริงแล้วทั้งสองเส้นทางจบไม่เหมือนกัน: `/compare-courses` และ `/recommend-major`
> ที่หมดเวลาตั้งแต่ขั้นจัดอันดับ เป็น **503** ส่วน `/recommend-major` ที่จัดอันดับเสร็จแล้ว
> หมดเวลาตอนเขียนคำอธิบาย เป็น **200 พร้อมอันดับครบและข้อความมาตรฐาน** ·
> ตารางและเหตุผลอยู่ในข้อ 7.2

เลือก 90 วินาทีเพราะคำขอที่สำเร็จปกติใช้ 9–35 วินาที (วัดวันเดียวกัน) เผื่อไว้อีกเท่าตัวกว่า
**ไม่แตะการเลือกโมเดล ไม่แตะจำนวนครั้งที่ลองซ้ำ ไม่เพิ่มค่าตั้งค่าใหม่**

### 3.2 หน้าเว็บ: เพดานเวลาฝั่งเบราว์เซอร์ + อ่านเหตุผลที่หลังบ้านส่งมา (`96777da`)

`src/lib/apiRequest.js` (ใหม่) ใช้ร่วมสองหน้า

* `AbortController` + เพดาน **100 วินาที** — ยาวกว่าเพดานของหลังบ้านเล็กน้อยโดยตั้งใจ
  เพื่อให้ข้อความของหลังบ้าน (ซึ่งอธิบายสาเหตุได้ดีกว่า) มาถึงผู้ใช้ก่อน ส่วนค่านี้เป็น
  ตาข่ายรองรับกรณีคำขอไปไม่ถึงหลังบ้าน
* อ่านเหตุผลจากช่อง **`detail`** ที่ FastAPI ส่งมา — ของเดิมอ่านแต่ `body.error`
  ข้อความไทยที่หลังบ้านเขียนไว้ให้ผู้ใช้อ่านจึงไม่เคยไปถึงผู้ใช้เลย ทุกความล้มเหลวกลายเป็น
  ข้อความกลาง ๆ อันเดียวกันหมด
* ทั้งสองหน้าออกจากสถานะโหลดใน `finally` เหมือนเดิม (ของเดิมก็มี แต่ไม่เคยได้ทำงาน
  เพราะคำขอไม่เคยจบ)

**คำตอบและตัวเลือกไม่หาย** — คำตอบแบบสอบถามอยู่ใน `sessionStorage` และสาขาที่เลือก
อยู่ใน query string ของหน้า ทั้งคู่ไม่ถูกล้างตอนคำขอล้ม ปุ่ม "ลองอีกครั้ง" จึงใช้ของเดิมได้ทันที

---

## 4. ผลทดสอบ

### 4.1 backend (ไม่ต่อฐาน ไม่เรียกโมเดล) — `test_result_page_budget.py` ผ่าน 4/4

| ข้อ | ยืนยันว่า |
|---|---|
| เพดานถูกตั้งไว้สมเหตุผล | อยู่ระหว่าง 60–120 วินาที |
| หน้าเปรียบเทียบ / หน้าแนะนำสาขา | **มีเพดานเวลาระหว่างทำงานจริง** (`budget_left_s()` ไม่เป็น None) |
| ล้างเพดานหลังจบเสมอ | ทั้งกรณีสำเร็จและกรณีงานล้ม — เพดานที่ค้างจะไปตัดงานถัดไปในบริบทเดียวกัน |

ชุดเดิมของงานแสดงชื่อรุ่น (`test_result_model_label`) ยังผ่าน 12/12

### 4.2 หน้าเว็บจริงในเบราว์เซอร์ (เสิร์ฟ dist ในเครื่อง ให้สอง endpoint ตอบตามที่กำหนด)

| กรณี | ผลที่เห็น |
|---|---|
| หลังบ้านตอบ **503 พร้อม `detail`** | หยุดหมุนทันที · ขึ้นข้อความของหลังบ้านตรงตัว ("ระบบใช้เวลาตอบนานเกินเพดานที่ตั้งไว้ จึงหยุดรอครับ…") · มีปุ่ม "ลองอีกครั้ง" · คำตอบแบบสอบถามยังอยู่ |
| หลังบ้าน **ค้างไม่ตอบเลย** | หมุนรอจนถึง **112 วินาที** แล้วหยุดเอง · ขึ้น "ระบบใช้เวลาตอบนานเกินปกติ จึงหยุดรอครับ — คำตอบของคุณยังถูกเก็บไว้ กดลองใหม่ได้เลย" · สาขาที่เลือกยังอยู่ใน URL · ปุ่ม "ให้ AI ช่วยวิเคราะห์" กลับมาให้กดใหม่ |

(ของเดิมในกรณีที่สอง หน้าจะหมุนต่อไปจนกว่าเบราว์เซอร์จะยอมแพ้เอง)

---

## 5. diff

### backend

```diff
diff --git a/backend/app/api/routes/web_compat.py b/backend/app/api/routes/web_compat.py
index b4d82d5..dc225e8 100644
--- a/backend/app/api/routes/web_compat.py
+++ b/backend/app/api/routes/web_compat.py
@@ -41,7 +41,8 @@ from app.services.program_names import program_about, program_facts
 from app.services.course_scope import degree_level_of, degree_of_title
 from app.services.web_compat import canonical_labels, label_of, match_by_title, normalise_title, shared_user
 
-from llm.connector import LLMConnectionError  # noqa: E402
+from llm.connector import (LLMConnectionError, reset_budget,  # noqa: E402
+                           start_budget)
 from llm.prompts import NO_EVIDENCE_MARKER  # noqa: E402
 
 router = APIRouter(tags=["web-compat"])
@@ -49,6 +50,21 @@ logger = logging.getLogger("course_advisor")
 
 BUSY = "ขออภัยครับ ระบบตอบไม่ได้ในขณะนี้ กรุณาลองใหม่อีกครั้ง"
 
+# เพดานเวลาของหน้าแนะนำสาขาและหน้าเปรียบเทียบ
+#
+# สองเส้นทางนี้ไม่เคยตั้งเพดานเวลาเลย ต่างจาก /chat-web ที่ตั้งมาตั้งแต่ต้น ผลคือเมื่อ
+# Gemini ตอบ 503 ครบทุกรุ่นแล้วตกไปใช้โมเดลในเครื่อง (ซึ่งช้ามากเพราะเซิร์ฟเวอร์ไม่มี
+# การ์ดจอ) คำขอหนึ่งใช้เวลาเท่ากับ ReadTimeout ของ Ollama คูณจำนวนครั้งที่ลองซ้ำ
+# วัดจาก production เมื่อ 29 ต.ค. 2569: คำขอ /recommend-major เวลา 09:29:01 ตอบกลับ
+# 09:35:16 — **6 นาที 15 วินาที** โดยหน้าเว็บหมุนรออยู่ทั้งหมดนั้น
+#
+# ตั้งเพดานแล้ว http_timeout() จะหดเวลาของทุกคำขอ HTTP ให้ไม่เกินเวลาที่เหลือ และ
+# check_budget() จะหยุดลองรุ่นถัดไปเมื่อหมดเวลา ผู้ใช้จึงได้ข้อความบอกเหตุแทนการรอ
+#
+# 90 วินาทีเพราะคำขอที่สำเร็จตามปกติใช้ 9-35 วินาที (วัดวันเดียวกัน: compare 31 วินาที
+# ตอนที่ Gemini ล่มไปรอบหนึ่งแล้วกลับมา) เผื่อไว้อีกเท่าตัวกว่า แต่ยังสั้นกว่าของเดิมหลายเท่า
+RESULT_PAGE_BUDGET_S = 90.0
+
 # แถวจากตารางเปรียบเทียบที่นำไปแสดงเป็นข้อดีของแต่ละสาขา เรียงตามที่นักเรียนอยากรู้ก่อน
 _PROS_ROWS = ["เรียนอะไรบ้าง", "ทักษะที่ได้รับ", "จบแล้วทำงานอะไร", "จำนวนหน่วยกิต", "ค่าเทอม"]
 _BEST_FOR_ROW = "คุณสมบัติผู้เข้าศึกษา"
@@ -503,6 +519,16 @@ def _row_value(rows, dimension: str, index: int) -> str | None:
 
 @router.post("/compare-courses", dependencies=[Depends(web_rate_limiter)])
 def compare_courses_web(payload: WebCompareRequest, db: Session = Depends(get_db)) -> dict:
+    """เปรียบเทียบสาขา — ห่อด้วยเพดานเวลาของคำขอ (ดู RESULT_PAGE_BUDGET_S)"""
+    budget = start_budget(RESULT_PAGE_BUDGET_S)
+    try:
+        return _compare_courses(payload, db)
+    finally:
+        # ล้างเสมอ ไม่ว่าจะสำเร็จหรือไม่ ไม่งั้นเพดานค้างไปถึงงานถัดไปในบริบทเดียวกัน
+        reset_budget(budget)
+
+
+def _compare_courses(payload: WebCompareRequest, db: Session) -> dict:
     """
     เปรียบเทียบสาขาในรูปแบบที่หน้าเว็บรออยู่
 
@@ -560,6 +586,15 @@ def compare_courses_web(payload: WebCompareRequest, db: Session = Depends(get_db
 
 @router.post("/recommend-major", dependencies=[Depends(web_rate_limiter)])
 def recommend_major_web(payload: WebRecommendRequest, db: Session = Depends(get_db)) -> dict:
+    """แนะนำสาขา — ห่อด้วยเพดานเวลาของคำขอ (ดู RESULT_PAGE_BUDGET_S)"""
+    budget = start_budget(RESULT_PAGE_BUDGET_S)
+    try:
+        return _recommend_major(payload, db)
+    finally:
+        reset_budget(budget)
+
+
+def _recommend_major(payload: WebRecommendRequest, db: Session) -> dict:
     """
     แนะนำสาขาในรูปแบบที่หน้าเว็บรออยู่
 
```

### หน้าเว็บ

```diff
diff --git a/src/pages/CompareResult.jsx b/src/pages/CompareResult.jsx
index 5752c46..8766858 100644
--- a/src/pages/CompareResult.jsx
+++ b/src/pages/CompareResult.jsx
@@ -4,6 +4,10 @@ import { Plus, Trash2, X, Check, GraduationCap, Sparkles, Loader2, AlertTriangle
 import { fetchSiteCoursesByIds } from '../lib/siteCourses'
 import { levelOf } from '../lib/courseLevels'
 import EngineNote from '../components/EngineNote'
+import { postJsonWithTimeout } from '../lib/apiRequest'
+
+// เหตุผลเดียวกับหน้าแนะนำสาขา — ยาวกว่าเพดานของหลังบ้านเล็กน้อย
+const REQUEST_TIMEOUT_MS = 100000
 
 const CompareResult = () => {
   const navigate = useNavigate()
@@ -63,20 +67,12 @@ const CompareResult = () => {
         careers: c.careers
       }))
 
-      const response = await fetch('/api/compare-courses', {
-        method: 'POST',
-        headers: { 'Content-Type': 'application/json' },
-        body: JSON.stringify({ courses: payload })
-      })
-
-      if (!response.ok) {
-        const body = await response.json().catch(() => ({}))
-        throw new Error(body.error || 'AI request failed')
-      }
-
-      setAiResult(await response.json())
-    } catch {
-      setAiError('ระบบ AI ไม่สามารถวิเคราะห์การเปรียบเทียบได้ในขณะนี้ กรุณาลองใหม่อีกครั้ง')
+      setAiResult(await postJsonWithTimeout(
+        '/api/compare-courses', { courses: payload }, REQUEST_TIMEOUT_MS
+      ))
+    } catch (err) {
+      // สาขาที่เลือกอยู่ใน query string ของหน้า การล้มของคำขอจึงไม่ทำให้ตัวเลือกหาย
+      setAiError(err.message || 'ระบบ AI ไม่สามารถวิเคราะห์การเปรียบเทียบได้ในขณะนี้ กรุณาลองใหม่อีกครั้ง')
     } finally {
       setAiLoading(false)
     }
diff --git a/src/pages/FindMajorResult.jsx b/src/pages/FindMajorResult.jsx
index 4e2b2ac..b2489f7 100644
--- a/src/pages/FindMajorResult.jsx
+++ b/src/pages/FindMajorResult.jsx
@@ -5,6 +5,11 @@ import { fetchSiteCourses } from '../lib/siteCourses'
 import { forUndergraduateAdvice } from '../lib/courseLevels'
 import { getFindMajorAnswers, clearFindMajorAnswers } from '../lib/findMajorAnswers'
 import EngineNote from '../components/EngineNote'
+import { postJsonWithTimeout } from '../lib/apiRequest'
+
+// ยาวกว่าเพดานของหลังบ้าน (90 วินาที) เล็กน้อย เพื่อให้ข้อความบอกเหตุของหลังบ้าน
+// มาถึงผู้ใช้ก่อน ส่วนค่านี้เป็นตาข่ายรองรับกรณีคำขอค้างระหว่างทาง
+const REQUEST_TIMEOUT_MS = 100000
 
 const steps = [
   { id: 1, title: 'ข้อมูลพื้นฐาน', status: 'completed' },
@@ -109,20 +114,15 @@ const FindMajorResult = () => {
     setResult(null)
 
     try {
-      const response = await fetch('/api/recommend-major', {
-        method: 'POST',
-        headers: { 'Content-Type': 'application/json' },
-        body: JSON.stringify({ answers: savedAnswers, courses: coursesData })
-      })
-
-      if (!response.ok) {
-        const body = await response.json().catch(() => ({}))
-        throw new Error(body.error || 'AI request failed')
-      }
-
-      setResult(await response.json())
+      setResult(await postJsonWithTimeout(
+        '/api/recommend-major',
+        { answers: savedAnswers, courses: coursesData },
+        REQUEST_TIMEOUT_MS
+      ))
     } catch (err) {
-      setError('ขออภัยครับ ระบบ AI ไม่สามารถวิเคราะห์ผลลัพธ์ได้ในขณะนี้ กรุณาลองใหม่อีกครั้ง')
+      // บอกเหตุที่หลังบ้านให้มา ถ้ามี — มันอธิบายได้ตรงกว่าข้อความกลาง ๆ ของหน้านี้
+      // คำตอบแบบสอบถามยังอยู่ใน sessionStorage ปุ่ม "ลองใหม่" จึงใช้ของเดิมได้ทันที
+      setError(err.message || 'ขออภัยครับ ระบบ AI ไม่สามารถวิเคราะห์ผลลัพธ์ได้ในขณะนี้ กรุณาลองใหม่อีกครั้ง')
     } finally {
       setLoading(false)
     }
```

---

## 6. ที่ยังไม่ได้ทำ / ข้อควรรู้

* **ยังไม่ deploy** ตามที่สั่ง · production ยังเป็น `model-label-2569-10-29` และ bundle เดิม
* **ไม่ได้ยิงทดสอบซ้ำกับของจริง** — หลักฐานทั้งหมดมาจาก log ของคำขอที่ผู้ใช้ทำเอง
  ส่วนการทดสอบการแสดงผลทำในเครื่องด้วยของจำลอง
* เพดาน 90/100 วินาทีเป็นค่าที่ตั้งจากตัวเลขที่วัดได้วันนี้ ถ้าภายหลังพบว่าคำขอปกติ
  ใช้เวลานานกว่านี้ (เช่นเพิ่มจำนวนสาขาที่เปรียบเทียบ) ต้องขยับทั้งสองค่าให้สัมพันธ์กัน
* **ไม่ได้แก้ที่ต้นตออีกชั้นหนึ่ง** คือการที่ Gemini ล่มแล้วตกไปใช้โมเดลในเครื่องซึ่ง
  ตอบไม่ทันบนเซิร์ฟเวอร์ที่ไม่มีการ์ดจอ — ถ้าต้องการให้ผู้ใช้ไม่ต้องรอ 90 วินาทีในกรณีนั้น
  ทางเลือกคือ **ไม่ใช้โมเดลในเครื่องเป็นตัวสำรองของสองหน้านี้** แล้วตอบทันทีว่า
  ผู้ให้บริการขัดข้อง (คะแนนและอันดับยังแสดงได้ ขาดแค่คำอธิบาย) · เป็นการเปลี่ยน
  นโยบายตัวสำรอง จึงไม่ทำในรอบนี้โดยไม่ได้สั่ง
* หน้าแชทไม่ได้แตะ — เส้นทางนั้นมีเพดานเวลาของตัวเองอยู่แล้ว

---

## 7. รอบตรวจเพิ่ม (29 ต.ค. 2569) — แยกปิดสองอาการ

### 7.1 อาการ "ชื่อโมเดลไม่แสดง" ที่หน้าเปรียบเทียบ

ตรวจของจริงที่ปล่อยอยู่ ไม่ใช่เดาจากภาพ

| ตรวจอะไร | ผล |
|---|---|
| bundle ที่ production เสิร์ฟ | `assets/index-BndauWSW.js` (488,410 ไบต์) |
| สตริงของคอมโพเนนต์อยู่ในไฟล์นั้นไหม | `คำอธิบายโดย` 1 · `ประมวลผลจากข้อมูลและเกณฑ์ของระบบ` 1 · `ไม่มีข้อมูลรุ่น` 1 · `คะแนนความเหมาะสมคำนวณ` 1 · `engine` 5 — **อยู่ครบ** |
| ตัวคอมโพเนนต์ในไฟล์ที่เสิร์ฟจริง | แกะออกมาได้ตรงตามต้นฉบับ (`ev={gemini:"Gemini",ollama:"โมเดลในเครื่อง"}` · `n.model&&n.model!=="?"?n.model:"ไม่มีข้อมูลรุ่น"`) |
| จุดที่เรียกใช้ | **สองจุด** — หน้าแนะนำสาขา `Of,{engine:a.engine,...}` · หน้าเปรียบเทียบ `Of,{engine:u.engine,...}` อยู่ในบล็อก `!h&&u` (= `!aiLoading && aiResult`) |
| header ของ `index.html` | `Cache-Control: no-cache` · `Last-Modified: 29 Oct 2026 09:00:45 GMT` — เบราว์เซอร์ตรวจกับเซิร์ฟเวอร์ทุกครั้ง โอกาสค้างที่ bundle เก่าจึงต่ำ |

**ไม่พบข้อบกพร่องในการไหลของค่าจาก state ถึง EngineNote** — ตามรอยในไฟล์ที่เสิร์ฟจริง
ค่าถูกส่งจาก `aiResult.engine` เข้าคอมโพเนนต์โดยตรง

เงื่อนไขที่ทำให้ "ไม่มีบรรทัดนี้เลย" บนหน้าเปรียบเทียบ มีอยู่สองอย่าง ทดสอบยืนยันแล้ว

```
ก่อนกดปุ่ม "ให้ AI ช่วยวิเคราะห์"  ->  บรรทัดชื่อรุ่น: []  (ยังไม่มีผลของ AI จึงไม่มีอะไรให้ติดป้าย)
หลังกดปุ่มแล้วได้ผล               ->  "คำอธิบายโดย Gemini · gemini-3.5-flash-lite"
```

หน้าเปรียบเทียบแสดง **ตารางเปรียบเทียบจากฐานข้อมูลได้โดยไม่ต้องเรียก AI** ส่วนบล็อก
"เปรียบเทียบด้วย AI" จะมีก็ต่อเมื่อกดปุ่มแล้วได้ผลสำเร็จ · อีกอย่างคือคำขอที่ค้าง
(อาการที่ 2) ซึ่งไม่เคยได้ผลมาแสดง — กรณีนั้นแก้ด้วยเพดานเวลาในข้อ 3 แล้ว

> **ข้อนี้จึงปิดด้วยหลักฐานว่าโค้ดที่ปล่อยไปถูกต้อง** ไม่ได้ปิดด้วยการอ้างรายงาน timeout
> ถ้าหลังจากนี้ยังเจอหน้าที่กดปุ่มแล้วได้ผลแต่ไม่มีบรรทัดชื่อรุ่น รบกวนส่ง URL กับเวลา
> ที่กดมา ผมจะตาม response ของคำขอนั้นใน log ให้ตรงตัว

### 7.2 อาการ timeout — พฤติกรรมจริงไม่ใช่ 503 เสมอ

รายงานฉบับแรกเขียนว่า "ผู้ใช้จึงได้ 503 พร้อมข้อความบอกเหตุ" **ซึ่งไม่ครบ**
จำลองเพดานเวลาหมดในแต่ละขั้น (ไม่เรียกโมเดลจริง) แล้ววัดสถานะและข้อความที่ออกมาจริง

| เส้นทาง | หมดเวลาตอนไหน | สถานะ | สิ่งที่ผู้ใช้ได้ |
|---|---|---|---|
| `/compare-courses` | ระหว่างให้โมเดลเขียนตารางเปรียบเทียบ | **503** | ข้อความที่เขียนไว้ให้ผู้ใช้อ่าน (`user_text`) |
| `/recommend-major` | ระหว่างจัดอันดับ (ขั้นที่ใช้ embedding) | **503** | ข้อความเดียวกัน — ไม่มีอันดับให้แสดง |
| `/recommend-major` | ระหว่างเขียนคำอธิบาย | **200** | **อันดับและคะแนนครบ** + ข้อความมาตรฐานแทนเหตุผล + `engine.explanation = null` (จึงไม่ติดป้ายชื่อรุ่น) |

เหตุผลที่ถูกต้องแล้ว: อันดับกับคะแนนคำนวณเสร็จก่อนเรียกโมเดลและไม่ได้พึ่งโมเดลเลย
การคืน 503 ทิ้งผลที่คำนวณเสร็จแล้วจะแย่กว่า

**พบเพิ่มระหว่างตรวจ**: สองเส้นทางนี้ส่ง `str(e)` เป็น `detail` ขณะที่เส้นทางแชทส่ง
`user_text` มาตั้งแต่ต้น (พร้อมคอมเมนต์อธิบายว่า `str(exc)` มีรายละเอียดวินิจฉัยต่อท้าย
และอาจพาเนื้อหาจากปลายทางออกมา) · ของเดิมไม่มีใครเห็นเพราะหน้าเว็บอ่านช่องที่หลังบ้าน
ไม่ได้ส่ง พอหน้าเว็บเริ่มแสดง `detail` ข้อความภายใน (รวมชื่อขั้นที่กำลังทำ) จะไปถึงผู้ใช้ทันที
— แก้ให้ส่ง `user_text` เหมือนเส้นทางแชท (commit `3608029`)

### 7.3 ผลทดสอบของรอบนี้ (ของจำลองล้วน ไม่ยิงโมเดลจริง)

```
test_result_page_timeout_behaviour   3 ข้อ · ผ่าน    (สถานะและข้อความของทั้งสองเส้นทาง)
test_result_page_budget              4 ข้อ · ผ่าน
test_result_model_label             12 ข้อ · ผ่าน
```

หน้าเว็บจริงในเบราว์เซอร์ (เสิร์ฟ dist ที่ build จากโค้ดชุดนี้)

| กรณี | ผลที่เห็น |
|---|---|
| เปรียบเทียบ ก่อนกดปุ่ม AI | ไม่มีบรรทัดชื่อรุ่น (ตามที่ออกแบบ) |
| เปรียบเทียบ หลังกดปุ่มแล้วได้ผล | `คำอธิบายโดย Gemini · gemini-3.5-flash-lite` |
| แนะนำสาขา กรณี 200 ที่ไม่ได้ใช้ข้อความของโมเดล | `ประมวลผลจากข้อมูลและเกณฑ์ของระบบ` + บรรทัดคะแนน · **อันดับยังแสดงครบ** · ไม่หมุนค้าง |
| หลังบ้านตอบ 503 พร้อม detail | หยุดหมุน · ขึ้นข้อความของหลังบ้านตรงตัว · มีปุ่มลองใหม่ |
| หลังบ้านค้างไม่ตอบ | หยุดเองที่ 112 วินาที · ขึ้นข้อความหมดเวลา · คำตอบและสาขาที่เลือกยังอยู่ |

---

## 8. diff ของรอบตรวจเพิ่ม

### `src/lib/apiRequest.js` (ไฟล์ใหม่ ที่ยังไม่มีในรายงานฉบับแรก)

```diff
diff --git a/src/lib/apiRequest.js b/src/lib/apiRequest.js
new file mode 100644
index 0000000..89ee081
--- /dev/null
+++ b/src/lib/apiRequest.js
@@ -0,0 +1,50 @@
+// ยิง POST ไปที่ API ของระบบ พร้อมเพดานเวลาของฝั่งเบราว์เซอร์
+//
+// ทำไมต้องมีเพดานตรงนี้ด้วย ทั้งที่หลังบ้านมีของตัวเองแล้ว
+// ------------------------------------------------------
+// fetch() ไม่มี timeout ในตัว ถ้าคำขอค้าง หน้าจอจะหมุนรอไปเรื่อย ๆ โดยไม่มีอะไรหยุดให้
+// วัดจาก production เมื่อ 29 ต.ค. 2569: คำขอ /recommend-major หนึ่งครั้งใช้เวลา
+// 6 นาที 15 วินาที (Gemini ตอบ 503 ครบทุกรุ่น แล้วตกไปใช้โมเดลในเครื่องที่ช้ามาก)
+// หน้าเว็บหมุนรอทั้งหมดนั้นโดยไม่บอกอะไรผู้ใช้เลย
+//
+// เพดานนี้ตั้งให้ "ยาวกว่า" เพดานของหลังบ้านเล็กน้อยโดยตั้งใจ เพื่อให้ข้อความบอกเหตุ
+// ที่หลังบ้านเขียนไว้ (ซึ่งอธิบายสาเหตุได้ดีกว่า) มาถึงผู้ใช้ก่อน ส่วนเพดานฝั่งนี้เป็น
+// ตาข่ายรองรับกรณีที่คำขอไปไม่ถึงหลังบ้านหรือค้างระหว่างทาง
+
+export const TIMEOUT_MESSAGE =
+  'ระบบใช้เวลาตอบนานเกินปกติ จึงหยุดรอครับ — คำตอบของคุณยังถูกเก็บไว้ กดลองใหม่ได้เลย'
+
+export class RequestTimeoutError extends Error {
+  constructor() {
+    super(TIMEOUT_MESSAGE)
+    this.name = 'RequestTimeoutError'
+  }
+}
+
+export const postJsonWithTimeout = async (url, body, timeoutMs) => {
+  const controller = new AbortController()
+  const timer = setTimeout(() => controller.abort(), timeoutMs)
+
+  try {
+    const response = await fetch(url, {
+      method: 'POST',
+      headers: { 'Content-Type': 'application/json' },
+      body: JSON.stringify(body),
+      signal: controller.signal
+    })
+
+    if (!response.ok) {
+      const payload = await response.json().catch(() => ({}))
+      // FastAPI ส่งเหตุผลมาในช่อง detail ซึ่งเป็นข้อความไทยที่เขียนไว้ให้ผู้ใช้อ่าน
+      // ของเดิมอ่านแต่ช่อง error ข้อความจริงจึงไม่เคยไปถึงผู้ใช้เลย
+      throw new Error(payload.detail || payload.error || `คำขอไม่สำเร็จ (HTTP ${response.status})`)
+    }
+
+    return await response.json()
+  } catch (err) {
+    if (err.name === 'AbortError') throw new RequestTimeoutError()
+    throw err
+  } finally {
+    clearTimeout(timer)
+  }
+}
```

### backend: ส่งข้อความที่เขียนไว้ให้ผู้ใช้อ่าน (`3608029`)

```diff
diff --git a/backend/app/api/routes/web_compat.py b/backend/app/api/routes/web_compat.py
index dc225e8..72d26c1 100644
--- a/backend/app/api/routes/web_compat.py
+++ b/backend/app/api/routes/web_compat.py
@@ -500,6 +500,11 @@ def career_lists_web(db: Session = Depends(get_db)) -> dict:
 SCORING_EMBEDDING_RULES = "embedding_and_rules"
 
 
+def _user_message(exc: Exception) -> str:
+    """ข้อความที่ส่งให้ผู้ใช้อ่านเมื่อเรียกโมเดลไม่สำเร็จ — ไม่ใช่ข้อความวินิจฉัยภายใน"""
+    return (getattr(exc, "user_text", None) or "").strip() or BUSY
+
+
 def _engine(explained: bool, scoring: str | None = None) -> dict:
     return {"explanation": chat_model_used() if explained else None, "scoring": scoring}
 
@@ -553,7 +558,11 @@ def _compare_courses(payload: WebCompareRequest, db: Session) -> dict:
     try:
         result = compare_programs(db, [c.id for _, c in matched])
     except LLMConnectionError as e:
-        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e) or BUSY) from e
+        # ส่งข้อความที่เขียนไว้ให้ผู้ใช้อ่าน ไม่ใช่ str(exc) ซึ่งมีรายละเอียดวินิจฉัย
+        # ต่อท้ายและอาจพาเนื้อหาจากปลายทางออกมา (ดู LLMConnectionError.user_text)
+        # — เส้นทางแชทใช้แบบนี้อยู่แล้ว ตรงนี้เพิ่งมามีผลเพราะหน้าเว็บเริ่มแสดง detail
+        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
+                            _user_message(e)) from e
 
     rows = [r if isinstance(r, dict) else r.model_dump() for r in result["rows"]]
     courses = []
@@ -621,7 +630,8 @@ def _recommend_major(payload: WebRecommendRequest, db: Session) -> dict:
     try:
         matches = match_programs(db, answers, limit=_MATCH_LIMIT)
     except LLMConnectionError as e:
-        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e) or BUSY) from e
+        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
+                            _user_message(e)) from e
 
     matched, _ = match_by_title(db, [c.model_dump() for c in payload.courses])
     # เทียบกลับด้วยชื่อ ไม่ใช่รหัสของหลักสูตร เพราะการจัดอันดับมองเอกสารทุกฉบับรวม
```

---

## 9. แผน deploy / rollback (ยังไม่รัน)

ของรอบนี้มีสาม commit — `2e49926` (เพดานเวลา) · `3608029` (ข้อความที่ส่งให้ผู้ใช้ +
ชุดทดสอบพฤติกรรม) ฝั่ง backend และ `96777da` ฝั่งหน้าเว็บ

### 9.1 ค่าที่ต้องคงไว้

| | |
|---|---|
| นโยบายตัวสำรอง (Gemini → โมเดลในเครื่อง) | **ไม่แตะ** ตามที่สั่ง |
| ลำดับรุ่นสำรองของ Gemini / จำนวนครั้งที่ลองซ้ำของ Ollama | ไม่แตะ |
| ค่าตั้งค่าใหม่ / migration | **ไม่มีทั้งคู่** (เพดานเป็นค่าคงที่ในโค้ด) |
| `src/pages/Admin/AiSettings.jsx` | งานค้างที่ยังไม่ commit — ต้องรอดทั้งก่อนและหลัง |

### 9.2 backend (ปล่อยก่อน)

1. merge `feature/public-model-choice` เข้า `mko-phase2` แบบ fast-forward
2. อิมเมจซ้อนจาก `course-advisor-system-backend:model-label-2569-10-29` ทับ **1 ไฟล์**
   `backend/app/api/routes/web_compat.py` → `/app/backend/app/api/routes/web_compat.py`
   พร้อมชุดทดสอบใหม่สองไฟล์ → `/app/backend/tests/`
   · tag `page-timeout-2569-10-29`
3. ตรวจ SHA256 ของทุกไฟล์ในอิมเมจให้ตรงกับ blob ของ commit ก่อนสลับ
4. รันในอิมเมจใหม่ (ฐาน `course_advisor_test`) ต้องผ่าน
   `test_result_page_timeout_behaviour` (3) · `test_result_page_budget` (4) ·
   `test_result_model_label` (12)
5. dry-run ของ compose ต้องไม่แตะบริการอื่น แล้ว `up -d --no-build --no-deps backend`
6. ตรวจรับ: `/api/health` 200 · ยิง `/api/recommend-major` และ `/api/compare-courses`
   อย่างละครั้ง ต้องได้ 200 ในเวลาปกติ (ไม่เกิน 90 วินาที) และยังมีช่อง `engine` ครบ

### 9.3 หน้าเว็บ (ตามหลัง)

build จาก worktree แยกที่ `96777da` — `git status` ต้องว่าง · `sha256sum -c` 19/19 ·
`deploy_web.sh` วาง assets ตรวจ hash ผ่านเว็บจริงแล้วค่อยสลับ `index.html` ·
สำรอง `git bundle` ก่อนปล่อยเหมือนทุกรอบ (ยัง push GitHub ไม่ได้)

ตรวจรับหน้าเว็บ: หน้าแนะนำสาขาและหน้าเปรียบเทียบยังได้ผลตามปกติ · บรรทัดชื่อรุ่นยังขึ้น ·
ลองกดขณะที่ผู้ให้บริการปกติ ต้องไม่เห็นข้อความหมดเวลา

### 9.4 rollback

| ส่วน | วิธีย้อน |
|---|---|
| backend | สลับ tag กลับเป็น `model-label-2569-10-29` แล้ว `up -d --no-build --no-deps backend` — กลับไปเป็น "ไม่มีเพดานเวลา" แบบเดิม ไม่มีอะไรต้องย้อนในฐานข้อมูล |
| หน้าเว็บ | `rollback_web.sh --run <โฟลเดอร์ web-run ของรอบนั้น>` |
| ย้อนฝั่งเดียว | ได้ทั้งคู่ — หน้าเว็บเก่า + backend ใหม่ ยังทำงานได้ (หน้าเว็บเก่าไม่มีเพดานฝั่งเบราว์เซอร์ แต่หลังบ้านตัดให้ที่ 90 วินาทีแล้ว) · หน้าเว็บใหม่ + backend เก่า ก็ได้ (เพดานฝั่งเบราว์เซอร์ 100 วินาทีทำงานแทน) |

### 9.5 ความเสี่ยงที่ควรรู้ก่อนกด

* คำขอที่ "ปกติแต่ช้ากว่า 90 วินาที" จะถูกตัด — จากตัวเลขที่วัดได้ (9–35 วินาที)
  ยังห่างมาก แต่ถ้าวันหนึ่งเปรียบเทียบพร้อมกันหลายสาขาจนเกิน ต้องขยับทั้งสองค่า
* ผู้ใช้จะเริ่มเห็นข้อความบอกเหตุจากหลังบ้านโดยตรง (เช่น "ระบบใช้เวลาตอบนานเกินเพดาน
  ที่ตั้งไว้…") ซึ่งเป็นข้อความที่เขียนไว้ให้ผู้ใช้อ่านอยู่แล้ว ไม่ใช่ข้อความวินิจฉัย
