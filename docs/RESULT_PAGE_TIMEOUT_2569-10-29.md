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
**503 พร้อมข้อความบอกเหตุ** แทนการรอ

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
