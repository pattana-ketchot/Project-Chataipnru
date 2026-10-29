# แสดงชื่อรุ่นที่ใช้จริงในหน้าแนะนำสาขาและหน้าเปรียบเทียบ — diff + readiness

**29 ต.ค. 2569** · รอบนี้**เพิ่มการแสดงข้อมูลอย่างเดียว** ไม่มีปุ่มเลือกโมเดล
ไม่แตะวิธีให้คะแนนและไม่แตะการเลือกโมเดลเดิม · **ยังไม่ merge ยังไม่ deploy**

| | |
|---|---|
| backend | `course-advisor-system` · commit **`e0e0a2e`** + **`7c32fd4`** (รอบแก้จากการรีวิว ดูข้อ 7) |
| หน้าเว็บ | `LastProject` · commit **`488a543`** |
| ไฟล์ที่แตะ | `llm/connector.py` · `llm/gemini.py` · `app/services/llm_client.py` · `app/api/routes/web_compat.py` · `tests/test_result_model_label.py` (ใหม่) · `src/components/EngineNote.jsx` (ใหม่) · `src/pages/FindMajorResult.jsx` · `src/pages/CompareResult.jsx` |
| migration / ค่าตั้งค่าใหม่ | **ไม่มีทั้งคู่** |
| งานค้าง `AiSettings.jsx` | ไม่ถูกแตะ (ยืนยันหลัง commit: ยังขึ้น ` M` และ commit มีแค่ 3 ไฟล์) |

---

## 1. เส้นทางเดิมของสองหน้านี้ — ส่วนไหนเป็นกฎ/ฐานข้อมูล ส่วนไหนเป็น AI

ทั้งสองหน้าเรียก `POST /api/recommend-major` และ `POST /api/compare-courses`
(`app/api/routes/web_compat.py`)

### หน้า "ค้นหาสาขาที่เหมาะกับฉัน" (`recommend-major` → `program_match.match_programs`)

| ขั้น | ใครทำ |
|---|---|
| แปลงคำตอบแบบสอบถามเป็นข้อความ แล้วเป็นเวกเตอร์ | **โมเดล embedding ในเครื่อง** (`bge-m3` ผ่าน Ollama) — เปลี่ยนไม่ได้ ผูกกับเวกเตอร์ของเอกสารทั้งคลัง |
| ให้คะแนนทุกหลักสูตร | **คำนวณเอง** — cosine ของเนื้อหา ผสมกับ cosine ของชื่อหลักสูตร (ถ่วง `_TITLE_WEIGHT`) |
| คัดและจัดอันดับ | **กฎของระบบ** — ตัดหลักสูตรที่ปิดรับสมัคร (`is_offered`) ยุบเอกสารหลายฉบับของสาขาเดียวกัน ตัดที่ห่างจากอันดับหนึ่งเกินเกณฑ์ |
| แปลงคะแนนเป็นเปอร์เซ็นต์ | **สูตรของระบบ** (`_to_percent`) |
| **เขียนเหตุผลของแต่ละสาขา** | **โมเดลเขียนคำตอบ** (ค่าตั้งต้นคือ Gemini) — เรียกครั้งเดียวทั้งชุด แล้วผ่านด่านตรวจข้อความอ้างอิง (`_verified_rationales`) |
| ข้อความสรุปบนสุด | **ข้อความคงที่ของระบบ** เลือกตามระดับความมั่นใจของคะแนน ไม่ได้มาจากโมเดล |

**คะแนนไม่ได้มาจากโมเดลที่เขียนคำอธิบาย** และถ้าโมเดลเขียนไม่ได้ ผู้ใช้ยังได้อันดับครบ
พร้อมข้อความมาตรฐานแทนเหตุผล (`_generate_rationales` คืนค่าว่างเมื่อล้ม)

### หน้า "เปรียบเทียบสาขา" (`compare-courses` → `program_compare.compare_programs`)

| ขั้น | ใครทำ |
|---|---|
| จับคู่ชื่อสาขาที่ส่งมากับหลักสูตรในฐาน | **กฎ/ฐานข้อมูล** (`match_by_title`) |
| ค้นเนื้อหาที่เกี่ยวข้องของแต่ละหัวข้อเปรียบเทียบ | **โมเดล embedding ในเครื่อง** + ค้นด้วย pgvector |
| **เขียนตารางเปรียบเทียบและข้อความสรุป** | **โมเดลเขียนคำตอบ** |
| ช่อง "ข้อเสีย" | **ไม่มีโดยตั้งใจ** — เอกสาร มคอ.2 ไม่ได้เขียนข้อเสียของตัวเอง การให้โมเดลคิดเองคือการแต่งข้อมูล |
| บรรทัด verdict ท้ายผล | **ข้อความคงที่ของระบบ** |

หน้านี้**ไม่มีคะแนน** จึงไม่มีบรรทัด "คะแนนความเหมาะสม…"

### ไม่มีแคชในสองเส้นทางนี้

ตรวจแล้วทั้ง `program_match.py` และ `program_compare.py` ไม่มีการอ่าน/เขียนแคชใด ๆ
(แคชคำตอบที่มีอยู่ `chat_answer_cache` เป็นของหน้าแชทเท่านั้น) ทุกคำขอจึงเรียกโมเดลจริง
· ถึงอย่างนั้นโครงสร้างที่ส่งกลับก็ออกแบบให้รองรับกรณี "ไม่ได้เรียกโมเดล" อยู่แล้ว
ถ้าวันหนึ่งมีแคช ให้เก็บค่า `engine` ไปกับผลแล้วส่งค่าที่เก็บไว้คืนมา ไม่ใช่ค่าปัจจุบัน

---

## 2. สิ่งที่เพิ่ม

### backend — บันทึก "ตัวที่เขียนสำเร็จ" ไม่ใช่ "ตัวที่ถูกเลือก"

ของเดิมมี `answer_model_label()` ซึ่งบอก**ตัวที่ถูกสั่ง**ให้เขียน · ใช้ตรงนี้ไม่ได้ เพราะ
เส้นทาง Gemini มีโมเดลในเครื่องรับช่วงต่อเมื่อเจ้าหลักล้ม ค่าจะยังเป็น `gemini` ทั้งที่
ข้อความมาจากโมเดลในเครื่อง

จึงเพิ่ม `record_chat_model()` / `chat_model_used()` / `reset_chat_model()` ใน
`llm_client.py` เก็บใน `ContextVar` (กลไกเดียวกับเพดานเวลาของคำขอ ซึ่งแยกต่อคำขออยู่แล้ว)
แล้วบันทึกที่จุดที่ **ได้ผลลัพธ์จริง** สามจุด

* `_SplitConnector.chat()` สำเร็จ → `gemini` + รุ่นของเจ้าหลัก
* `_SplitConnector._call_fallback()` สำเร็จ → `ollama` + รุ่นในเครื่อง
* `_LocalPrimary.chat()` สำเร็จ → `ollama` + รุ่นในเครื่อง

ทั้งสอง endpoint `reset_chat_model()` ก่อนเริ่มงาน แล้วส่งช่องใหม่กลับไปกับผล

```json
"engine": {
  "explanation": {"provider": "gemini", "model": "gemini-3.5-flash-lite"},
  "scoring": "embedding_and_rules"
}
```

* `explanation` = `null` เมื่อ **ไม่ได้เรียกโมเดล** หรือ **เรียกแล้วข้อความไม่ได้ถูกใช้เลย**
  (ทุกใบเป็นข้อความมาตรฐานของระบบ เพราะโมเดลล่มหรือไม่ผ่านด่านตรวจข้อความอ้างอิง)
* `scoring` = `null` สำหรับหน้าเปรียบเทียบ เพราะหน้านั้นไม่มีคะแนน
* ส่งแค่ชื่อผู้ให้บริการกับชื่อรุ่น — **ไม่มีคีย์ ไม่มี endpoint ไม่มีข้อมูลการเชื่อมต่อ**
  (มีข้อทดสอบกำกับว่าช่องนี้มีแค่สองคีย์)

### หน้าเว็บ — คอมโพเนนต์เดียวใช้ร่วมสองหน้า

`src/components/EngineNote.jsx` อ่านค่าจาก `engine` แล้วแสดงใต้ข้อความสรุปของผล
**ไม่มีชื่อรุ่นใดเขียนไว้ในหน้าเว็บเลย** มีแต่การแปลงรหัสผู้ให้บริการเป็นคำอ่าน
(`gemini` → `Gemini`, `ollama` → `โมเดลในเครื่อง`) และถ้าเจอรหัสที่ไม่รู้จักก็แสดงรหัสนั้นตรง ๆ

| หลังบ้านส่งมา | หน้าเว็บแสดง |
|---|---|
| `explanation` มีรุ่น | `คำอธิบายโดย Gemini · gemini-3.5-flash-lite` |
| `explanation` เป็น `null` | `ประมวลผลจากข้อมูลและเกณฑ์ของระบบ` |
| `explanation` มี แต่รุ่นเป็น `?` หรือว่าง | `คำอธิบายโดย Gemini · ไม่มีข้อมูลรุ่น` |
| `scoring = embedding_and_rules` | เพิ่มอีกบรรทัด: `คะแนนความเหมาะสมคำนวณจากความใกล้เคียงระหว่างคำตอบของคุณกับเนื้อหาในเอกสารหลักสูตร และเกณฑ์ของระบบ` |
| ไม่มีช่อง `engine` เลย (หลังบ้านรุ่นเก่า) | **ไม่แสดงอะไร** — ดีกว่าเดาแล้วบอกผิด |

---

## 3. diff — backend (`e0e0a2e`)

```diff
diff --git a/backend/app/api/routes/web_compat.py b/backend/app/api/routes/web_compat.py
index 61d2499..b4d82d5 100644
--- a/backend/app/api/routes/web_compat.py
+++ b/backend/app/api/routes/web_compat.py
@@ -33,7 +33,7 @@ from app.api.deps import web_rate_limiter
 from app.db.session import get_db
 from app.services.chat import PriorTurn, stream_answer
 from app.services import ai_settings
-from app.services.llm_client import connector_for
+from app.services.llm_client import chat_model_used, connector_for, reset_chat_model
 from app.services.curriculum_facts import LIST_FIELDS
 from app.services.program_compare import compare_programs
 from app.services.program_match import build_profile_text, confidence_of, match_programs
@@ -474,6 +474,20 @@ def career_lists_web(db: Session = Depends(get_db)) -> dict:
     return {"programmes": programmes}
 
 
+# ที่มาของสิ่งที่ผู้ใช้เห็นในผลชุดหนึ่ง — ส่งเป็นโครงสร้าง ไม่ใช่ประโยคสำเร็จรูป
+#
+# หน้าเว็บเลือกถ้อยคำเอง แต่ **ชื่อรุ่นต้องมาจากที่นี่เท่านั้น** ห้ามหน้าเว็บเขียนทับไว้เอง
+# เพราะผู้ดูแลเปลี่ยนรุ่นได้ตลอด และเส้นทาง Gemini มีโมเดลในเครื่องรับช่วงต่อได้
+#
+# explanation เป็น None เมื่อ "ไม่ได้เรียกโมเดล" หรือ "เรียกแล้วแต่ข้อความของมันไม่ได้ถูกใช้"
+# หน้าเว็บจะได้ไม่ติดป้ายชื่อรุ่นให้ผลที่ไม่ได้มาจากโมเดล
+SCORING_EMBEDDING_RULES = "embedding_and_rules"
+
+
+def _engine(explained: bool, scoring: str | None = None) -> dict:
+    return {"explanation": chat_model_used() if explained else None, "scoring": scoring}
+
+
 def _rank_key(title: str) -> tuple[str, str | None]:
     """คีย์เทียบชื่อสาขาที่แยกระดับปริญญาด้วย — ใช้จับคู่อันดับกลับไปที่การ์ดบนหน้าเว็บ"""
     return normalise_title(title), degree_level_of(degree_of_title(title))
@@ -496,6 +510,7 @@ def compare_courses_web(payload: WebCompareRequest, db: Session = Depends(get_db
     หลักสูตรตัวเองไว้ การให้โมเดลคิดข้อเสียขึ้นมาเองคือการแต่งข้อมูล ซึ่งเป็นสิ่งที่
     ระบบนี้ตั้งใจไม่ทำ หน้าเว็บตรวจความยาวก่อนแสดงอยู่แล้ว บล็อกนั้นจึงไม่ขึ้นเอง
     """
+    reset_chat_model()
     sent = [c.model_dump() for c in payload.courses]
     matched, unmatched = match_by_title(db, sent)
 
@@ -538,6 +553,8 @@ def compare_courses_web(payload: WebCompareRequest, db: Session = Depends(get_db
         "summary": (result.get("summary") or "") + note,
         "courses": courses,
         "verdict": "ข้อมูลทั้งหมดสรุปจากเอกสารหลักสูตร (มคอ.2) ของแต่ละสาขา ยกเว้นค่าเทอมที่มาจากประกาศของคณะ",
+        # หน้านี้ไม่มีคะแนน มีแต่ข้อความที่โมเดลสรุปจากเอกสาร จึงไม่ส่ง scoring
+        "engine": _engine(explained=True),
     }
 
 
@@ -548,6 +565,7 @@ def recommend_major_web(payload: WebRecommendRequest, db: Session = Depends(get_
 
     ชื่อช่องในแบบสอบถามของหน้าเว็บไม่ตรงกับของเรา (skills/goals/track) จึงแปลงก่อน
     """
+    reset_chat_model()
     a = payload.answers
     # แปลรหัสตัวเลือกเป็นข้อความไทยที่ผู้ใช้เห็นก่อนเสมอ — หน้าเว็บส่งรหัสอย่าง "tech"
     # หรือ "career-growth" มา ซึ่งแทบไม่มีความหมายให้เทียบกับเอกสารภาษาไทย
@@ -615,10 +633,18 @@ def recommend_major_web(payload: WebRecommendRequest, db: Session = Depends(get_
         "ผลนี้คำนวณจากความใกล้เคียงระหว่างคำตอบของคุณกับเนื้อหาจริงในเอกสารหลักสูตรของแต่ละสาขา"
     )
 
+    cards = [card(e) for e in ranked[:1 + _MAX_ALTERNATIVES]]
+    # ติดป้ายชื่อรุ่นเฉพาะเมื่อข้อความของโมเดลถูกใช้จริงอย่างน้อยหนึ่งใบ — โมเดลล่ม
+    # หรือเขียนมาแล้วไม่ผ่านด่านตรวจข้อความอ้างอิง ทุกใบจะเป็นข้อความมาตรฐานของระบบ
+    explained = any(c["reason"] not in (NO_REASON, NO_EVIDENCE_REASON) for c in cards)
+
     return {
-        "primary": card(ranked[0]),
-        "alternatives": [card(e) for e in ranked[1:1 + _MAX_ALTERNATIVES]],
+        "primary": cards[0],
+        "alternatives": cards[1:],
         "summary": summary,
         # เปิดไว้ให้ตรวจสอบได้ว่าระบบเข้าใจคำตอบของนักเรียนว่าอย่างไร
         "profileText": build_profile_text(answers),
+        # คะแนนไม่ได้มาจากโมเดลที่เขียนคำอธิบาย — มาจากความใกล้เคียงของเวกเตอร์กับ
+        # เกณฑ์ของระบบ (ตัดหลักสูตรที่ปิดรับ ยุบฉบับซ้ำ ถ่วงน้ำหนักชื่อหลักสูตร)
+        "engine": _engine(explained, scoring=SCORING_EMBEDDING_RULES),
     }
diff --git a/backend/app/services/llm_client.py b/backend/app/services/llm_client.py
index ab14d26..5098f54 100644
--- a/backend/app/services/llm_client.py
+++ b/backend/app/services/llm_client.py
@@ -23,6 +23,7 @@ import logging
 import sys
 import threading
 import time
+from contextvars import ContextVar
 from pathlib import Path
 
 # monorepo: <root>/backend/app/services/llm_client.py -> <root>/llm
@@ -110,7 +111,9 @@ class _SplitConnector:
         # ขั้นที่ห้ามใช้ตัวสำรองไม่ต้องกัน เพราะไม่มีใครมารับช่วงต่อ
         full = reserve_budget() if allow_fallback else None
         try:
-            return self._chatter.chat(*args, **kwargs)
+            out = self._chatter.chat(*args, **kwargs)
+            record_chat_model(self.provider_name, self._chatter.chat_model)
+            return out
         except LLMConnectionError as e:
             if not allow_fallback:
                 llm_usage.record("fallback_declined")
@@ -138,6 +141,8 @@ class _SplitConnector:
             llm_usage.record("fallback_local_failed")
             raise
         llm_usage.record("fallback_local_ok")
+        # ข้อความที่ผู้ใช้จะเห็นมาจากตัวสำรอง ไม่ใช่เจ้าหลักที่ถูกเลือกไว้
+        record_chat_model("ollama", getattr(self._fallback, "chat_model", ""))
         return out
 
     def chat_stream(self, *args, allow_fallback: bool = True, **kwargs):
@@ -226,6 +231,7 @@ class _LocalPrimary:
             llm_usage.record("local_primary_failed")
             raise
         llm_usage.record("local_primary_ok")
+        record_chat_model("ollama", getattr(self._local, "chat_model", ""))
         return out
 
     def chat_stream(self, *args, **kwargs):
@@ -386,6 +392,35 @@ def connector_for(choice: ai_settings.Choice):
     return built
 
 
+# รุ่นที่ "เขียนข้อความให้คำขอนี้จริง" — บันทึกตอนเรียกสำเร็จ ไม่ใช่ตอนเลือก
+#
+# ต่างจาก answer_model_label() ที่บอกตัวที่ถูก **สั่ง** ให้เขียน · ถ้าเจ้าหลักล้มแล้ว
+# โมเดลในเครื่องรับช่วงต่อ ค่าที่นี่จะเป็นโมเดลในเครื่อง เพราะข้อความที่ผู้ใช้เห็นมาจาก
+# ตัวนั้นจริง · ไม่ได้เรียกโมเดลเลย = None ซึ่งต้องไม่ถูกแปลงเป็นชื่อรุ่นค่าตั้งต้น
+#
+# เก็บใน ContextVar ไม่ใช่ตัวแปรโมดูล เพราะหลายคำขอทำงานพร้อมกัน — endpoint แบบ sync
+# ของ FastAPI รันใน threadpool ซึ่งคัดลอก context ให้ทีละคำขออยู่แล้ว (กลไกเดียวกับที่
+# เพดานเวลาของคำขอใช้อยู่) ค่าของคำขอหนึ่งจึงไม่รั่วไปอีกคำขอ
+_chat_model_used: ContextVar[tuple[str, str] | None] = ContextVar(
+    "chat_model_used", default=None)
+
+
+def record_chat_model(provider: str, model: str) -> None:
+    """บันทึกว่าใครเพิ่งเขียนข้อความสำเร็จให้คำขอนี้ — เรียกหลังได้ผลลัพธ์เท่านั้น"""
+    _chat_model_used.set((provider or "unknown", model or "?"))
+
+
+def reset_chat_model() -> None:
+    """ล้างค่าก่อนเริ่มงานของคำขอใหม่ ไม่งั้นค่าที่ค้างอยู่จะถูกรายงานว่าเป็นของคำขอนี้"""
+    _chat_model_used.set(None)
+
+
+def chat_model_used() -> dict | None:
+    """{'provider', 'model'} ของการเขียนข้อความครั้งล่าสุดในคำขอนี้ · None = ไม่ได้เรียกโมเดล"""
+    pair = _chat_model_used.get()
+    return None if pair is None else {"provider": pair[0], "model": pair[1]}
+
+
 def answer_model_label(connector) -> str:
     """
     ชื่อผู้ให้บริการและรุ่นที่ถูก "สั่งให้เขียน" คำตอบของคำขอนี้
diff --git a/backend/tests/test_result_model_label.py b/backend/tests/test_result_model_label.py
new file mode 100644
index 0000000..2cf75bf
--- /dev/null
+++ b/backend/tests/test_result_model_label.py
@@ -0,0 +1,133 @@
+"""
+ชื่อรุ่นที่หน้าผลลัพธ์แสดง ต้องเป็นตัวที่เขียนข้อความให้คำขอนั้นจริง
+
+    cd backend && python tests/test_result_model_label.py
+
+ไม่ต่อฐานข้อมูล ไม่เรียกโมเดลจริง — ใช้ของจับพฤติกรรมแทน connector ชั้นใน
+
+ทำไมต้องมีชุดนี้
+---------------
+หน้า "ค้นหาสาขาที่เหมาะกับฉัน" และ "เปรียบเทียบสาขา" จะติดป้ายว่าใครเขียนคำอธิบาย
+ให้ผู้ใช้เห็น · สามอย่างที่ผิดแล้วผู้ใช้จะถูกบอกข้อมูลเท็จโดยไม่มีใครรู้
+
+1. **ติดป้ายด้วยค่าตั้งต้นแทนตัวที่ทำงานจริง** — เส้นทาง Gemini มีโมเดลในเครื่อง
+   รับช่วงต่อเมื่อเจ้าหลักล้ม ถ้ารายงานตามค่าที่เลือกไว้ ผู้ใช้จะเห็นว่า Gemini เขียน
+   ทั้งที่ข้อความมาจากโมเดลในเครื่อง
+2. **ติดป้ายทั้งที่ไม่ได้เรียกโมเดลเลย** — ถ้าโมเดลล่ม ผลยังออกได้ด้วยข้อความมาตรฐาน
+   ของระบบ กรณีนั้นต้องไม่มีชื่อรุ่น
+3. **ค่าของคำขอหนึ่งรั่วไปอีกคำขอ** — หลายคำขอทำงานพร้อมกัน
+"""
+import os
+import sys
+import unittest
+from contextvars import copy_context
+from pathlib import Path
+
+sys.stdout.reconfigure(encoding="utf-8", errors="replace")
+sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
+sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
+
+os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://unused:unused@127.0.0.1:1/unused")
+os.environ.setdefault("JWT_SECRET", "ชุดทดสอบไม่ได้ออก token")
+os.environ.setdefault("GEMINI_API_KEY", "คีย์ปลอมสำหรับชุดทดสอบ")
+
+from llm.connector import LLMConnectionError  # noqa: E402
+
+from app.api.routes.web_compat import _engine  # noqa: E402
+from app.services import llm_client  # noqa: E402
+
+
+class _Fake:
+    """connector ชั้นในแบบปลอม — ตอบสำเร็จหรือล้มตามที่สั่ง"""
+
+    answer_token_cap = 512
+
+    def __init__(self, model: str, fail: bool = False) -> None:
+        self.chat_model = model
+        self._fail = fail
+        self.calls = 0
+
+    def chat(self, *_args, **_kwargs):
+        self.calls += 1
+        if self._fail:
+            raise LLMConnectionError("จำลองว่าเจ้าหลักล้ม")
+        return "ข้อความจาก " + self.chat_model
+
+    def embed(self, _text):
+        return [0.0]
+
+
+class ResultModelLabelTests(unittest.TestCase):
+    def setUp(self):
+        llm_client.reset_chat_model()
+
+    def test_ยังไม่ได้เรียกโมเดล_ต้องไม่มีชื่อรุ่น(self):
+        self.assertIsNone(llm_client.chat_model_used())
+
+    def test_เจ้าหลักเขียนสำเร็จ_รายงานเจ้าหลัก(self):
+        split = llm_client._SplitConnector(_Fake("bge-m3"), _Fake("gemini-3.5-flash"))
+        split.chat([])
+        self.assertEqual(llm_client.chat_model_used(),
+                         {"provider": "gemini", "model": "gemini-3.5-flash"})
+
+    def test_เจ้าหลักล้มแล้วตัวสำรองรับช่วง_ต้องรายงานตัวสำรอง(self):
+        """ข้อความที่ผู้ใช้เห็นมาจากโมเดลในเครื่อง การติดป้ายว่า Gemini คือการบอกผิด"""
+        local = _Fake("qwen2.5:3b")
+        split = llm_client._SplitConnector(local, _Fake("gemini-3.5-flash", fail=True))
+        out = split.chat([])
+        self.assertIn("qwen2.5:3b", out)
+        self.assertEqual(llm_client.chat_model_used(),
+                         {"provider": "ollama", "model": "qwen2.5:3b"})
+
+    def test_ทั้งเจ้าหลักและตัวสำรองล้ม_ต้องไม่มีชื่อรุ่น(self):
+        split = llm_client._SplitConnector(_Fake("qwen2.5:3b", fail=True),
+                                           _Fake("gemini-3.5-flash", fail=True))
+        with self.assertRaises(LLMConnectionError):
+            split.chat([])
+        self.assertIsNone(llm_client.chat_model_used())
+
+    def test_เลือกโมเดลในเครื่องเป็นตัวหลัก_รายงานตัวนั้น(self):
+        local = llm_client._LocalPrimary(_Fake("qwen2.5:3b"))
+        local.chat([])
+        self.assertEqual(llm_client.chat_model_used(),
+                         {"provider": "ollama", "model": "qwen2.5:3b"})
+
+    def test_ค่าของคำขอหนึ่งไม่รั่วไปอีกคำขอ(self):
+        """endpoint แบบ sync รันใน threadpool ซึ่งคัดลอก context ให้ทีละคำขอ"""
+        def one():
+            llm_client.reset_chat_model()
+            llm_client._SplitConnector(_Fake("bge-m3"), _Fake("gemini-3.5-flash")).chat([])
+            return llm_client.chat_model_used()
+
+        self.assertEqual(copy_context().run(one)["model"], "gemini-3.5-flash")
+        # คำขอนี้ไม่ได้เรียกโมเดลเอง จึงต้องไม่เห็นของคำขอก่อนหน้า
+        self.assertIsNone(llm_client.chat_model_used())
+
+    # ---------------- รูปร่างที่ส่งให้หน้าเว็บ ----------------
+
+    def test_ส่งชื่อรุ่นที่ทำงานจริงไปกับผล(self):
+        llm_client._SplitConnector(_Fake("bge-m3"), _Fake("gemini-3.5-flash-lite")).chat([])
+        engine = _engine(explained=True, scoring="embedding_and_rules")
+        self.assertEqual(engine["explanation"],
+                         {"provider": "gemini", "model": "gemini-3.5-flash-lite"})
+        self.assertEqual(engine["scoring"], "embedding_and_rules")
+
+    def test_ข้อความของโมเดลไม่ได้ถูกใช้_ต้องไม่ติดป้ายชื่อรุ่น(self):
+        """โมเดลเขียนมาแล้วไม่ผ่านด่านตรวจข้อความอ้างอิง ผู้ใช้เห็นข้อความมาตรฐานของระบบ"""
+        llm_client._SplitConnector(_Fake("bge-m3"), _Fake("gemini-3.5-flash")).chat([])
+        self.assertIsNone(_engine(explained=False)["explanation"])
+
+    def test_ไม่เรียกโมเดลเลย_ผลยังบอกวิธีให้คะแนนได้(self):
+        engine = _engine(explained=True, scoring="embedding_and_rules")
+        self.assertIsNone(engine["explanation"])
+        self.assertEqual(engine["scoring"], "embedding_and_rules")
+
+    def test_ไม่มีคีย์หรือข้อมูลการเชื่อมต่อหลุดไปกับผล(self):
+        llm_client._SplitConnector(_Fake("bge-m3"), _Fake("gemini-3.5-flash")).chat([])
+        engine = _engine(explained=True, scoring="embedding_and_rules")
+        self.assertEqual(set(engine), {"explanation", "scoring"})
+        self.assertEqual(set(engine["explanation"]), {"provider", "model"})
+
+
+if __name__ == "__main__":
+    unittest.main(verbosity=2)
```

## 4. diff — หน้าเว็บ (`488a543`)

```diff
diff --git a/src/components/EngineNote.jsx b/src/components/EngineNote.jsx
new file mode 100644
index 0000000..6979197
--- /dev/null
+++ b/src/components/EngineNote.jsx
@@ -0,0 +1,47 @@
+// บอกผู้ใช้ว่าอะไรในผลชุดนี้มาจากโมเดล และอะไรมาจากเกณฑ์ของระบบ
+//
+// **ชื่อรุ่นมาจากหลังบ้านเท่านั้น** ที่นี่ไม่เขียนชื่อรุ่นใดไว้เลย เพราะผู้ดูแลเปลี่ยนรุ่นได้
+// ตลอด และเส้นทาง Gemini มีโมเดลในเครื่องรับช่วงต่อเมื่อเจ้าหลักล้ม — ค่าที่หลังบ้านส่งมา
+// คือตัวที่เขียนข้อความให้คำขอนั้นจริง ไม่ใช่ค่าที่ตั้งไว้
+//
+// engine ไม่มีมาเลย (หลังบ้านรุ่นเก่า) = ไม่แสดงอะไร ดีกว่าเดาแล้วบอกผิด
+
+const PROVIDER_LABEL = { gemini: 'Gemini', ollama: 'โมเดลในเครื่อง' }
+
+const SCORING_TEXT = {
+  embedding_and_rules:
+    'คะแนนความเหมาะสมคำนวณจากความใกล้เคียงระหว่างคำตอบของคุณกับเนื้อหาในเอกสารหลักสูตร และเกณฑ์ของระบบ'
+}
+
+export const engineLines = (engine) => {
+  if (!engine) return []
+  const lines = []
+  const used = engine.explanation
+
+  if (used) {
+    const provider = PROVIDER_LABEL[used.provider] || used.provider || 'ผู้ให้บริการที่ไม่ทราบชื่อ'
+    // รุ่นที่หลังบ้านบอกว่าไม่รู้ ("?" หรือว่าง) ต้องไม่ถูกเติมด้วยค่าตั้งต้นของหน้าเว็บ
+    const model = used.model && used.model !== '?' ? used.model : 'ไม่มีข้อมูลรุ่น'
+    lines.push(`คำอธิบายโดย ${provider} · ${model}`)
+  } else {
+    lines.push('ประมวลผลจากข้อมูลและเกณฑ์ของระบบ')
+  }
+
+  if (engine.scoring && SCORING_TEXT[engine.scoring]) lines.push(SCORING_TEXT[engine.scoring])
+  return lines
+}
+
+const EngineNote = ({ engine, className = '' }) => {
+  const lines = engineLines(engine)
+  if (lines.length === 0) return null
+
+  return (
+    <p className={`text-xs text-gray-500 leading-relaxed ${className}`}>
+      {lines.map((line, index) => (
+        <span key={index} className="block">{line}</span>
+      ))}
+    </p>
+  )
+}
+
+export default EngineNote
diff --git a/src/pages/CompareResult.jsx b/src/pages/CompareResult.jsx
index 4e052a0..5752c46 100644
--- a/src/pages/CompareResult.jsx
+++ b/src/pages/CompareResult.jsx
@@ -3,6 +3,7 @@ import { useNavigate, useSearchParams } from 'react-router-dom'
 import { Plus, Trash2, X, Check, GraduationCap, Sparkles, Loader2, AlertTriangle } from 'lucide-react'
 import { fetchSiteCoursesByIds } from '../lib/siteCourses'
 import { levelOf } from '../lib/courseLevels'
+import EngineNote from '../components/EngineNote'
 
 const CompareResult = () => {
   const navigate = useNavigate()
@@ -207,6 +208,8 @@ const CompareResult = () => {
                 {aiResult.summary && (
                   <p className="text-sm lg:text-base text-gray-700 leading-relaxed">{aiResult.summary}</p>
                 )}
+                {/* ใครเขียนข้อความเปรียบเทียบชุดนี้ — ค่ามาจากหลังบ้าน ไม่ใช่ค่าที่ตั้งไว้ที่นี่ */}
+                <EngineNote engine={aiResult.engine} className="-mt-2" />
 
                 {Array.isArray(aiResult.courses) && aiResult.courses.length > 0 && (
                   <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
diff --git a/src/pages/FindMajorResult.jsx b/src/pages/FindMajorResult.jsx
index 01edd34..4e2b2ac 100644
--- a/src/pages/FindMajorResult.jsx
+++ b/src/pages/FindMajorResult.jsx
@@ -4,6 +4,7 @@ import { Sparkles, Loader2, RotateCcw, ArrowRight, AlertTriangle, Info, ChevronD
 import { fetchSiteCourses } from '../lib/siteCourses'
 import { forUndergraduateAdvice } from '../lib/courseLevels'
 import { getFindMajorAnswers, clearFindMajorAnswers } from '../lib/findMajorAnswers'
+import EngineNote from '../components/EngineNote'
 
 const steps = [
   { id: 1, title: 'ข้อมูลพื้นฐาน', status: 'completed' },
@@ -266,6 +267,8 @@ const FindMajorResult = () => {
                     <h3 className="font-semibold text-gray-800">สรุปจาก AI</h3>
                   </div>
                   <p className="text-sm lg:text-base text-gray-700 leading-relaxed">{result.summary}</p>
+                  {/* ใครเขียนคำอธิบาย และคะแนนมาจากไหน — ค่าทั้งหมดมาจากหลังบ้าน */}
+                  <EngineNote engine={result.engine} className="mt-2" />
                   <ScoreExplanation />
                 </div>
 
```

---

## 5. readiness — ผลทดสอบ

### 5.1 ชุดทดสอบใหม่ `test_result_model_label.py` (10 ข้อ) — ผ่าน 10/10

ไม่ต่อฐานข้อมูล ไม่เรียกโมเดลจริง · รันทั้งในเครื่องและในอิมเมจบนเซิร์ฟเวอร์

| ข้อ | ยืนยันว่า |
|---|---|
| ยังไม่ได้เรียกโมเดล | ไม่มีชื่อรุ่น |
| เจ้าหลักเขียนสำเร็จ | รายงาน `gemini` + รุ่นของเจ้าหลัก |
| **เจ้าหลักล้มแล้วตัวสำรองรับช่วง** | รายงาน `ollama` + รุ่นในเครื่อง ไม่ใช่ `gemini` |
| ทั้งเจ้าหลักและตัวสำรองล้ม | ไม่มีชื่อรุ่น |
| เลือกโมเดลในเครื่องเป็นตัวหลัก | รายงานตัวนั้น |
| **ค่าของคำขอหนึ่งไม่รั่วไปอีกคำขอ** | คำขอที่ไม่ได้เรียกโมเดลไม่เห็นค่าของคำขอก่อนหน้า |
| ข้อความของโมเดลไม่ได้ถูกใช้ | ไม่ติดป้ายชื่อรุ่น |
| ไม่เรียกโมเดลเลย | ยังบอกวิธีให้คะแนนได้ |
| ช่องที่ส่งออก | มีแค่ `explanation` กับ `scoring` และข้างในมีแค่ `provider`/`model` — ไม่มีคีย์หรือข้อมูลการเชื่อมต่อ |

> ระหว่างทางพบว่าสคริปต์ช่วยรันเทสต์ในกล่องเครื่องมือของผมไม่ได้เรียก `setUp()`
> ทำให้สี่ข้อแรกตกแบบหลอก ๆ · แก้ที่สคริปต์ ไม่ได้แก้เกณฑ์ของเทสต์

### 5.2 ยิงจริงผ่าน API บนฐานทดสอบ — ทั้งสองหน้า

คอนเทนเนอร์แยกจากอิมเมจที่ซ้อนไฟล์ของงานนี้ทับอิมเมจที่ production ใช้อยู่
(`image-upload-2569-10-29`) · ฐาน `course_advisor_test` · ไม่แตะ production

```
POST /compare-courses   HTTP 200 · 7 วินาที
  ช่องที่ได้ : courses · engine · summary · verdict
  engine    : {"explanation": {"provider": "gemini", "model": "gemini-3.5-flash-lite"}, "scoring": null}

POST /recommend-major   HTTP 200 · 8 วินาที
  ช่องที่ได้ : alternatives · engine · primary · profileText · summary
  engine    : {"explanation": {"provider": "gemini", "model": "gemini-3.5-flash-lite"}, "scoring": "embedding_and_rules"}
  อันดับ 1  : 50% · "หลักสูตรด้านวิทยาการคอมพิวเตอร์สอดคล้องกับความสนใจด้านคอมพิว…"
```

ชื่อรุ่นที่ได้คือรุ่นที่เซิร์ฟเวอร์นั้นใช้อยู่จริง ไม่ใช่ค่าที่หน้าเว็บเดา

### 5.3 หน้าเว็บจริงในเบราว์เซอร์ — ครบทุกกรณีที่หลังบ้านส่งมาได้

เสิร์ฟ `dist` ในเครื่องแล้วให้สองเส้นทางนี้ตอบด้วยข้อมูลที่กำหนดเอง (กรณีโมเดลล่มหรือ
ไม่รู้ชื่อรุ่นสร้างกับของจริงยาก) ส่วนเส้นทางอื่นต่อกับ backend จริง

| กรณี | หน้า "ค้นหาสาขาที่เหมาะกับฉัน" แสดง |
|---|---|
| `explanation` มีรุ่น | `คำอธิบายโดย Gemini · gemini-3.5-flash-lite` + บรรทัดคะแนน |
| `explanation` = `null` | `ประมวลผลจากข้อมูลและเกณฑ์ของระบบ` + บรรทัดคะแนน |
| รุ่นเป็น `?` | `คำอธิบายโดย Gemini · ไม่มีข้อมูลรุ่น` + บรรทัดคะแนน |
| ไม่มีช่อง `engine` | ไม่มีบรรทัดใดเลย (ผลลัพธ์ยังแสดงครบ) |

หน้า "เปรียบเทียบสาขา" (กรณีปกติ · `scoring: null` เหมือนของจริง)

```
เปรียบเทียบด้วย AI | … | ข้อความเปรียบเทียบ… | คำอธิบายโดย Gemini · gemini-3.5-flash-lite
```

แสดงบรรทัดเดียว ไม่มีบรรทัดคะแนน — ถูกต้อง เพราะหน้านี้ไม่มีคะแนน

### 5.4 ไม่กระทบของเดิม

`test_public_model_choice` (30 ข้อ) และ `test_upload_image` (11 ข้อ) ยังผ่าน exit 0
· ไม่ได้รันชุดใหญ่อื่นซ้ำตามที่สั่ง

---

## 6. ข้อควรรู้ / ที่ยังไม่ได้ทำ

* **ยังไม่ merge ยังไม่ deploy** · production ยังเป็น `image-upload-2569-10-29` และ
  bundle เดิม — ตรวจแล้วหลังทดสอบเสร็จ (health 200)
* หน้าแชทไม่ได้แตะในรอบนี้ · การบันทึกรุ่นทำเฉพาะเส้นทาง `chat()` ยังไม่ได้ทำกับ
  `chat_stream()` ที่หน้าแชทใช้ — หน้าแชทมีวิธีบอกรุ่นของตัวเองอยู่แล้ว (ช่อง
  `corpus_version` ของแคชและ log) ถ้าต้องการให้หน้าแชทโชว์ด้วยค่อยทำรอบหน้า
* รอบนี้ไม่มีปุ่มเลือกโมเดลในสองหน้านี้ตามที่สั่ง
* ถ้าวันหนึ่งเพิ่มแคชให้สองเส้นทางนี้ ต้องเก็บ `engine` ลงแคชด้วยและคืนค่าที่เก็บไว้
  ไม่ใช่ค่าปัจจุบัน (เขียนเหตุผลไว้ในข้อ 1 แล้ว)
* ลบคอนเทนเนอร์ อิมเมจ และไฟล์ที่ใช้ตรวจบนเซิร์ฟเวอร์ทิ้งหมดแล้ว

---

## 7. รอบแก้จากการรีวิว: Gemini ตอบด้วยรุ่นสำรองของตัวเองได้

**ข้อที่รีวิวจับได้ถูกต้อง** — ป้ายอ่านจาก `self._chatter.chat_model` ซึ่งเป็น**รุ่นที่ตั้งไว้**
แต่ `GeminiConnector.chat()` วนลองตาม `_models_to_try()` และตอบด้วยรุ่นสำรองของตัวเองได้
เมื่อรุ่นหลักชนเพดานต่อนาที (429 ของ Google เป็นแบบต่อโมเดล) หรือฝั่งผู้ให้บริการล่ม (5xx)

```python
# llm/gemini.py — ของเดิมที่มีอยู่แล้ว ไม่ได้แก้ในรอบนี้
for model in self._models_to_try():          # [รุ่นหลัก, รุ่นสำรอง 1, รุ่นสำรอง 2, …]
    text = self._chat_one_model(model, payload)
    self._note("gemini_ok" if model == self.chat_model else f"gemini_backup:{model}")
```

คำขอที่ `gemini-3.6-flash` เขียนให้ จึงเคยถูกติดป้ายว่า `gemini-3.5-flash-lite`

### สิ่งที่แก้ (commit `7c32fd4`)

* **บันทึกในตัวเชื่อมต่อเอง ณ จุดที่คืนข้อความสำเร็จ** — `note_answered_model(model)`
  ใน `GeminiConnector.chat()` และใน `OllamaConnector.chat()` · ผู้เรียกไม่ต้องเดาอีกต่อไป
* **เก็บใน `ContextVar` ของ `llm/connector.py` ไม่ใช่แอตทริบิวต์ของตัวเชื่อมต่อ** ตามที่
  รีวิวกำชับ — ตัวเชื่อมต่อถูกแคชไว้ใช้ร่วมกันทุกคำขอ (`_connectors` ใน `llm_client`)
  การเขียนทับบนวัตถุเดียวกันจะทำให้คำขอที่ทำงานพร้อมกันอ่านค่าของกันและกัน
* ชั้นบนอ่าน `answered_model()` ก่อน แล้วค่อยถอยไปใช้ค่าที่ตั้งไว้ถ้าไม่มี
* `reset_chat_model()` ล้างทั้งสองค่าให้ในครั้งเดียว ผู้เรียกจึงไม่ลืมล้างอันใดอันหนึ่ง
* **ไม่เปลี่ยนนโยบายเลือกโมเดล** — ไม่มีบรรทัดใดใน `_models_to_try()` หรือลำดับการลอง
  ถูกแก้ · รอบนี้เพิ่มแต่การ "รายงานว่าตัวไหนตอบ"

### เทสต์ที่เพิ่ม (รวมเป็น 12 ข้อ · ผ่าน 12/12)

ใช้ `GeminiConnector` ตัวจริง แล้วแทนเฉพาะการยิง HTTP ด้วยของจำลอง ไม่ยิงโมเดลจริง

| ข้อ | ยืนยันว่า |
|---|---|
| `รุ่นหลักของ_gemini_ชนโควตา_ต้องรายงานรุ่นสำรองที่ตอบจริง` | ลองตามลำดับ `[gemini-3.5-flash-lite, gemini-3.6-flash]` · ข้อความมาจากรุ่นสำรอง · ป้ายเป็น **`gemini-3.6-flash`** ไม่ใช่รุ่นที่ตั้งไว้ |
| `ค่าของคำขอที่ใช้รุ่นสำรองไม่รั่วไปคำขออื่นที่ใช้ตัวเชื่อมต่อเดียวกัน` | ใช้ `_SplitConnector` **ตัวเดียวกัน** สองคำขอ · คำขอที่ไม่ได้เรียกโมเดลได้ `None` ไม่ใช่รุ่นของคำขอก่อนหน้า |

### ชุดเดิมที่แตะเส้นทางเดียวกัน — ยังผ่าน

เป็นชุดที่จำลองทั้งหมด ไม่ยิงโมเดลจริง และไม่ใช่ชุดใหญ่

```
test_gemini_overload_fallback   9 ชุด · 20 จุดตรวจ · ผ่านทั้งหมด
test_local_fallback_gets_time   12 ข้อ · ตก 0
test_request_budget             13 ชุด · 41 จุดตรวจ · ผ่านทั้งหมด
```

### diff ของรอบแก้

```diff
diff --git a/backend/app/services/llm_client.py b/backend/app/services/llm_client.py
index 5098f54..6efbd36 100644
--- a/backend/app/services/llm_client.py
+++ b/backend/app/services/llm_client.py
@@ -33,7 +33,8 @@ if str(_REPO_ROOT) not in sys.path:
 
 from llm.connector import (_DEFAULT_BUDGET_S, ChatMessage,  # noqa: E402
                            LLMConnectionError, OllamaConnector,
-                           apply_budget, reserve_budget, reset_budget, start_budget)
+                           answered_model, apply_budget, reserve_budget,
+                           reset_answered_model, reset_budget, start_budget)
 from llm.gemini import GeminiConnector  # noqa: E402
 from llm.prompts import (GROUNDING_CHECK_SYSTEM_PROMPT,  # noqa: E402
                          build_grounding_check_prompt)
@@ -112,7 +113,10 @@ class _SplitConnector:
         full = reserve_budget() if allow_fallback else None
         try:
             out = self._chatter.chat(*args, **kwargs)
-            record_chat_model(self.provider_name, self._chatter.chat_model)
+            # ตัวที่ตอบสำเร็จจริง ไม่ใช่ chat_model ที่ตั้งไว้ — Gemini วนลองรุ่นสำรองของ
+            # ตัวเองได้เมื่อรุ่นหลักชนโควตา (ดู gemini._models_to_try)
+            record_chat_model(self.provider_name,
+                              answered_model() or self._chatter.chat_model)
             return out
         except LLMConnectionError as e:
             if not allow_fallback:
@@ -142,7 +146,8 @@ class _SplitConnector:
             raise
         llm_usage.record("fallback_local_ok")
         # ข้อความที่ผู้ใช้จะเห็นมาจากตัวสำรอง ไม่ใช่เจ้าหลักที่ถูกเลือกไว้
-        record_chat_model("ollama", getattr(self._fallback, "chat_model", ""))
+        record_chat_model("ollama",
+                          answered_model() or getattr(self._fallback, "chat_model", ""))
         return out
 
     def chat_stream(self, *args, allow_fallback: bool = True, **kwargs):
@@ -231,7 +236,8 @@ class _LocalPrimary:
             llm_usage.record("local_primary_failed")
             raise
         llm_usage.record("local_primary_ok")
-        record_chat_model("ollama", getattr(self._local, "chat_model", ""))
+        record_chat_model("ollama",
+                          answered_model() or getattr(self._local, "chat_model", ""))
         return out
 
     def chat_stream(self, *args, **kwargs):
@@ -413,6 +419,7 @@ def record_chat_model(provider: str, model: str) -> None:
 def reset_chat_model() -> None:
     """ล้างค่าก่อนเริ่มงานของคำขอใหม่ ไม่งั้นค่าที่ค้างอยู่จะถูกรายงานว่าเป็นของคำขอนี้"""
     _chat_model_used.set(None)
+    reset_answered_model()
 
 
 def chat_model_used() -> dict | None:
diff --git a/llm/connector.py b/llm/connector.py
index 31fb47c..a8c19f4 100644
--- a/llm/connector.py
+++ b/llm/connector.py
@@ -160,6 +160,34 @@ def budget_left_s() -> float | None:
     return None if end is None else end - time.monotonic()
 
 
+# รุ่นที่ "ตอบสำเร็จ" ให้คำขอนี้ — ตัวเชื่อมต่อบันทึกเอง ผู้เรียกจึงไม่ต้องเดา
+#
+# ที่นี่เป็นที่เดียวที่รู้ความจริง: GeminiConnector วนลองหลายรุ่นเมื่อรุ่นหลักชนโควตา
+# หรือฝั่งผู้ให้บริการล่ม (ดู _models_to_try) รุ่นที่ตอบสำเร็จจึงไม่ใช่ chat_model ที่ตั้งไว้เสมอ
+#
+# **ต้องเป็น ContextVar ไม่ใช่แอตทริบิวต์ของตัวเชื่อมต่อ** เพราะตัวเชื่อมต่อถูกแคชไว้ใช้ร่วมกัน
+# ทุกคำขอ การเขียนทับบนวัตถุเดียวกันจะทำให้คำขอที่ทำงานพร้อมกันอ่านค่าของกันและกัน
+_answered_model: contextvars.ContextVar[str | None] = contextvars.ContextVar(
+    "llm_answered_model", default=None
+)
+
+
+def note_answered_model(model: str) -> None:
+    """ตัวเชื่อมต่อเรียกเมื่อได้ข้อความกลับมาสำเร็จ — ห้ามเรียกตอนเริ่มลอง"""
+    if model:
+        _answered_model.set(model)
+
+
+def answered_model() -> str | None:
+    """รุ่นที่ตอบสำเร็จล่าสุดในคำขอนี้ · None = ยังไม่มีการตอบสำเร็จ"""
+    return _answered_model.get()
+
+
+def reset_answered_model() -> None:
+    """ล้างก่อนเริ่มคำขอใหม่ ไม่งั้นค่าที่ค้างอยู่จะถูกอ่านว่าเป็นของคำขอนี้"""
+    _answered_model.set(None)
+
+
 def check_budget(doing: str) -> None:
     """โยน LLMBudgetExceeded ถ้าหมดเวลาแล้ว · เรียกก่อนเริ่มงานที่กินเวลาทุกครั้ง"""
     left = budget_left_s()
@@ -330,6 +358,9 @@ class OllamaConnector:
         content = message.get("content")
         if content is None:
             raise LLMConnectionError(f"chat response missing content: {data!r}"[:200])
+        # บันทึกไว้ด้วย ไม่ใช่เพราะที่นี่มีหลายรุ่นให้เลือก (มีรุ่นเดียว) แต่เพื่อให้ค่าที่
+        # ผู้เรียกอ่านเป็นของการตอบ "ครั้งล่าสุด" จริง ๆ เมื่อคำขอหนึ่งเรียกข้ามผู้ให้บริการ
+        note_answered_model(self.chat_model)
         return content
 
     def chat_stream(
diff --git a/llm/gemini.py b/llm/gemini.py
index 78b69ed..b4cb51f 100644
--- a/llm/gemini.py
+++ b/llm/gemini.py
@@ -43,7 +43,7 @@ import httpx
 
 from llm.connector import (ChatMessage, LLMBudgetExceeded, LLMConnectionError,
                            budget_left_s, check_budget, http_timeout,
-                           post_json_bounded)
+                           note_answered_model, post_json_bounded)
 
 logger = logging.getLogger("llm.gemini")
 
@@ -365,6 +365,9 @@ class GeminiConnector:
                 if model != self.chat_model:
                     logger.info("ตอบด้วยโมเดลสำรอง %s", model)
                 self._note("gemini_ok" if model == self.chat_model else f"gemini_backup:{model}")
+                # ตัวที่ตอบสำเร็จจริง ซึ่งไม่ใช่ chat_model ที่ตั้งไว้เสมอ — ผู้เรียกที่จะ
+                # บอกผู้ใช้ว่า "รุ่นไหนเขียนคำตอบนี้" ต้องใช้ค่านี้ ไม่ใช่ค่าที่ตั้งไว้
+                note_answered_model(model)
                 return text
             except _QuotaExhausted as e:
                 self._note(f"gemini_{e.kind}:{model}")
diff --git a/backend/tests/test_result_model_label.py b/backend/tests/test_result_model_label.py
index 2cf75bf..4fa6311 100644
--- a/backend/tests/test_result_model_label.py
+++ b/backend/tests/test_result_model_label.py
@@ -31,7 +31,8 @@ os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://unused:unused@127.0.
 os.environ.setdefault("JWT_SECRET", "ชุดทดสอบไม่ได้ออก token")
 os.environ.setdefault("GEMINI_API_KEY", "คีย์ปลอมสำหรับชุดทดสอบ")
 
-from llm.connector import LLMConnectionError  # noqa: E402
+from llm.connector import ChatMessage, LLMConnectionError  # noqa: E402
+from llm.gemini import GeminiConnector, _QuotaExhausted  # noqa: E402
 
 from app.api.routes.web_compat import _engine  # noqa: E402
 from app.services import llm_client  # noqa: E402
@@ -103,6 +104,65 @@ class ResultModelLabelTests(unittest.TestCase):
         # คำขอนี้ไม่ได้เรียกโมเดลเอง จึงต้องไม่เห็นของคำขอก่อนหน้า
         self.assertIsNone(llm_client.chat_model_used())
 
+    # ---------------- Gemini วนลองรุ่นของตัวเอง ----------------
+
+    def _gemini_that_falls_back(self):
+        """
+        GeminiConnector จริง แต่แทนการยิง HTTP ด้วยของจำลอง
+
+        รุ่นหลักชนโควตา (429 ของ Google เป็นแบบต่อโมเดล) รุ่นสำรองตอบสำเร็จ
+        """
+        # คีย์ต้องเป็น ASCII เพราะมันถูกใส่ลงส่วนหัวของ HTTP ตอนสร้างตัวเชื่อมต่อ
+        conn = GeminiConnector(api_key="not-a-real-key", chat_model="gemini-3.5-flash-lite",
+                               fallback_models=("gemini-3.6-flash",))
+        tried: list[str] = []
+
+        def fake_call(model, _payload):
+            tried.append(model)
+            if model == conn.chat_model:
+                raise _QuotaExhausted(model, 1.0)
+            return "ข้อความจากรุ่นสำรอง " + model
+
+        conn._chat_one_model = fake_call
+        return conn, tried
+
+    def test_รุ่นหลักของ_gemini_ชนโควตา_ต้องรายงานรุ่นสำรองที่ตอบจริง(self):
+        """
+        ค่าที่ตั้งไว้คือ gemini-3.5-flash-lite แต่ตัวที่เขียนคำตอบคือ gemini-3.6-flash
+
+        ถ้ารายงานตามค่าที่ตั้งไว้ ผู้ใช้จะเห็นชื่อรุ่นที่ไม่ได้เขียนข้อความนั้นเลย
+        """
+        gemini, tried = self._gemini_that_falls_back()
+        split = llm_client._SplitConnector(_Fake("bge-m3"), gemini)
+        out = split.chat([ChatMessage(role="user", content="ทดสอบ")])
+
+        self.assertEqual(tried, ["gemini-3.5-flash-lite", "gemini-3.6-flash"])
+        self.assertIn("gemini-3.6-flash", out)
+        self.assertEqual(llm_client.chat_model_used(),
+                         {"provider": "gemini", "model": "gemini-3.6-flash"})
+
+    def test_ค่าของคำขอที่ใช้รุ่นสำรองไม่รั่วไปคำขออื่นที่ใช้ตัวเชื่อมต่อเดียวกัน(self):
+        """
+        ตัวเชื่อมต่อถูกแคชไว้ใช้ร่วมทุกคำขอ — ถ้าเก็บรุ่นที่ตอบไว้บนวัตถุนั้น
+        คำขอที่ทำงานพร้อมกันจะอ่านค่าของกันและกัน
+        """
+        gemini, _ = self._gemini_that_falls_back()
+        split = llm_client._SplitConnector(_Fake("bge-m3"), gemini)
+
+        def request_with_backup():
+            llm_client.reset_chat_model()
+            split.chat([ChatMessage(role="user", content="คำขอที่ใช้รุ่นสำรอง")])
+            return llm_client.chat_model_used()
+
+        def request_without_model():
+            llm_client.reset_chat_model()
+            return llm_client.chat_model_used()
+
+        self.assertEqual(copy_context().run(request_with_backup)["model"], "gemini-3.6-flash")
+        # คำขอนี้ใช้ตัวเชื่อมต่อตัวเดียวกันแต่ไม่ได้เรียกโมเดล ต้องไม่เห็นรุ่นของคำขอก่อนหน้า
+        self.assertIsNone(copy_context().run(request_without_model))
+        self.assertIsNone(llm_client.chat_model_used())
+
     # ---------------- รูปร่างที่ส่งให้หน้าเว็บ ----------------
 
     def test_ส่งชื่อรุ่นที่ทำงานจริงไปกับผล(self):
```

---

## 8. แผน deploy / rollback (ยังไม่รัน รอการอนุมัติ)

**backend ก่อน หน้าเว็บทีหลัง** — หน้าเว็บใหม่ที่เจอ backend เก่าจะไม่เห็นช่อง `engine`
แล้วไม่แสดงบรรทัดนั้นเลย (ไม่พัง แต่ฟีเจอร์หายเงียบ ๆ) ส่วน backend ใหม่ที่เจอหน้าเว็บเก่า
ก็แค่ส่งช่องที่ไม่มีใครอ่าน

### 8.1 ค่าที่ต้องคงไว้

| | |
|---|---|
| การเลือกโมเดล / ลำดับรุ่นสำรองของ Gemini | **ไม่แตะ** — รอบนี้เพิ่มแต่การรายงาน |
| `GEMINI_FALLBACK_MODELS` และ env อื่นของโมเดล | **ไม่แตะ ไม่ต้องเพิ่มค่าใหม่** |
| `UPLOADS_DIR` · bind mount · ฐานข้อมูล | ไม่เกี่ยวกับรอบนี้ ไม่แตะ |
| `src/pages/Admin/AiSettings.jsx` | งานค้างที่ยังไม่ commit — ต้องรอดทั้งก่อนและหลัง |

### 8.2 backend

1. merge `feature/public-model-choice` เข้า `mko-phase2` แบบ fast-forward
2. สร้างอิมเมจซ้อนจากตัวที่รันอยู่ **ไม่ build จาก working tree ทั้งก้อน**
   `FROM course-advisor-system-backend:image-upload-2569-10-29` ทับ 4 ไฟล์

   | ไฟล์ในโปรเจกต์ | พาธในอิมเมจ |
   |---|---|
   | `llm/connector.py` | `/app/llm/connector.py` |
   | `llm/gemini.py` | `/app/llm/gemini.py` |
   | `backend/app/services/llm_client.py` | `/app/backend/app/services/llm_client.py` |
   | `backend/app/api/routes/web_compat.py` | `/app/backend/app/api/routes/web_compat.py` |

   พร้อมชุดทดสอบ `backend/tests/test_result_model_label.py` → `/app/backend/tests/`
   · tag `model-label-2569-10-29`

   > **สองไฟล์ใน `llm/` อยู่คนละพาธกับรอบก่อน ๆ** (`/app/llm/` ไม่ใช่ `/app/backend/app/`)
   > — รอบ switch 28 ต.ค. เคยซ้อน `connector.py` ที่พาธนี้มาแล้ว ให้ยึดตามนั้น
3. ตรวจ SHA256 ของทั้ง 5 ไฟล์ในอิมเมจให้ตรงกับ blob ของ commit ก่อนสลับ
4. รันในอิมเมจใหม่ (ฐาน `course_advisor_test`) ต้องผ่าน
   `python tests/test_result_model_label.py` (12 ข้อ · exit 0)
   และชุดที่แตะเส้นทางเดียวกัน `test_gemini_overload_fallback` · `test_local_fallback_gets_time`
5. dry-run ของ compose ต้องไม่แตะบริการอื่น แล้ว `up -d --no-build --no-deps backend`
6. ตรวจรับหลังสลับ — `/api/health` = 200 · หน้าแชทยังตอบได้ตามปกติ · ยิง
   `POST /api/recommend-major` และ `POST /api/compare-courses` หนึ่งครั้ง ต้องได้ช่อง
   `engine` พร้อมชื่อรุ่นที่ไม่ว่าง

### 8.3 หน้าเว็บ

ชุดนี้ยังไม่ได้ build (หน้าเว็บของรอบนี้ยังไม่มีชุด release) — เมื่ออนุมัติแล้วทำตามนี้

1. `git worktree add --detach D:/workspace/lastproject-rel-<sha> <sha>` แล้ว `npm run build`
   **ห้าม build จาก checkout หลัก** เพราะมีงานค้าง `AiSettings.jsx` อยู่
2. `sha256sum -c` ให้ผ่านครบ 19 ไฟล์ก่อนอัปโหลด
3. `deploy_web.sh` — วาง assets ตรวจ hash ผ่านเว็บจริง **แล้วค่อยสลับ `index.html`**
4. ตรวจรับ: เปิดหน้า "ค้นหาสาขาที่เหมาะกับฉัน" ให้ครบขั้นตอนจนเห็นผล ต้องมีบรรทัด
   `คำอธิบายโดย …` และบรรทัดคะแนน · หน้า "เปรียบเทียบสาขา" กด "ให้ AI ช่วยวิเคราะห์"
   ต้องมีบรรทัด `คำอธิบายโดย …` บรรทัดเดียว (หน้านี้ไม่มีคะแนน)

### 8.4 rollback

| ส่วน | วิธีย้อน |
|---|---|
| backend | สลับ tag กลับเป็น `image-upload-2569-10-29` แล้ว `up -d --no-build --no-deps backend` · ไม่มีอะไรต้องย้อนในฐานข้อมูล และไม่มีค่าตั้งค่าที่ต้องคืน |
| หน้าเว็บ | `rollback_web.sh --run <โฟลเดอร์ web-run ของรอบนั้น>` — ย้อน `index.html` ให้ชี้ bundle เดิม |
| ย้อนเฉพาะหน้าเว็บ | ได้ — บรรทัดที่เพิ่มหายไป ผลลัพธ์อื่นเหมือนเดิมทุกอย่าง |
| ย้อนเฉพาะ backend | ได้ — หน้าเว็บไม่เห็นช่อง `engine` แล้วไม่แสดงบรรทัดนั้น (กรณีนี้ทดสอบแล้วในข้อ 5.3) |

**ความเสี่ยงของรอบนี้ต่ำ**: ไม่มี migration ไม่มีค่าตั้งค่าใหม่ ไม่เปลี่ยนการเลือกโมเดล
และทุกเส้นทางที่แตะมีชุดทดสอบที่จำลองการล้มของโมเดลกำกับอยู่
