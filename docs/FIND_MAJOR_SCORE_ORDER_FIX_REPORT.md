# Find-Major Score Order-Dependence Fix — Offline Implementation Report

วันที่: 2026-09-18
Branch: `mko-phase2` (worktree `course-advisor-system-mko2`) ต่อจาก `6d3964d`
ขอบเขต: OFFLINE IMPLEMENTATION ONLY — ไม่ยิง production, ไม่เรียก Gemini, ไม่เขียน DB, ไม่ deploy, ไม่เปลี่ยน production config, ไม่รัน behaviour_check, ไม่ push

---

## 1. Root cause

หน้าเว็บ (`ProjectPnru/src/pages/FindMajor*.jsx`) เก็บคำตอบแบบเลือกได้หลายข้อเป็น array ตามลำดับที่ผู้ใช้กด (`[...prev, id]`)
และ `POST /recommend-major` (`backend/app/api/routes/web_compat.py`) แปลรหัสด้วย `labels_of()` ซึ่งคงลำดับนั้นไว้
จากนั้น `build_match_query()` ต่อเป็นข้อความด้วย `", ".join(...)` แล้วนำไปสร้าง embedding

```
same answer set + different click order
→ different query text → different embedding → different percentage (ทุกสาขาขยับพร้อมกัน)
```

## 2. Files changed

| ไฟล์ | การเปลี่ยนแปลง |
|---|---|
| `backend/app/services/web_compat.py` | +29: เพิ่ม `_LABEL_RANK` และ `canonical_labels(field, values)` |
| `backend/app/api/routes/web_compat.py` | +8 / −5: ข้อ subjects / interests / skills / goals เรียก `canonical_labels` แทน `labels_of` · import ปรับตาม |
| `eval/find_major_order_check.py` | ใหม่ 19 tests |
| `docs/FIND_MAJOR_SCORE_ORDER_FIX_REPORT.md` | รายงานนี้ |

ไม่เปลี่ยน: `program_match.py` (สูตร, น้ำหนัก 0.5/0.5, ช่วง 0.35–0.72, `build_match_query`, `build_profile_text`), embedding model, DB, ข้อมูลหลักสูตร, Gemini rationale prompt, RAG, Structured Answers / Phase 2, frontend

## 3. Canonicalization algorithm

`canonical_labels(field, values)`:

1. แปลแต่ละค่าด้วย `labels_of(field, values)` เหมือนเดิม (รหัส → ข้อความบนปุ่ม, ค่าที่ไม่รู้จักคืนค่าเดิม, `None`/`[]` → `[]`)
2. ตัดตัวซ้ำ **หลังแปล** ด้วย `dict.fromkeys` — รหัส `tech` กับข้อความ `เทคโนโลยีและคอมพิวเตอร์` นับเป็นข้อเดียว
3. เรียงด้วย key:
   - ค่าที่อยู่ใน `OPTION_LABELS[field]` → `(0, ลำดับใน OPTION_LABELS, "")`
   - ค่าที่ไม่รู้จัก / free text / ข้อที่ไม่มีตาราง (subjects) → `(1, 0, str(value))` ต่อท้าย เรียงตาม code point
4. ไม่มีค่าใดถูกทิ้ง นอกจากตัวซ้ำ

Multi-select fields ที่ครอบคลุม: `subjects`, `interests`, `skills`, `goals` (ตรวจจากหน้าเว็บจริง: 4 ข้อนี้เป็น array ทั้งหมด)
`track` และ `environment` เป็นตัวเลือกเดียว ใช้ `label_of` เหมือนเดิม · `gender` หน้าเว็บส่งมาแต่หลังบ้านไม่ได้ใช้

## 4. Before / after examples

สร้างจากโค้ดจริง (before = เส้นทางเดิมด้วย `labels_of`, after = `recommend_major_web` หลังแก้)

**กรณี 1 — วิชาที่ชอบ กดตามลำดับ** `subjects=["คณิตศาสตร์","คอมพิวเตอร์"], interests=["tech"], skills=["creative"], goals=["career-growth"]`
```
before: ชอบวิชา คณิตศาสตร์, คอมพิวเตอร์ สนใจด้าน เทคโนโลยีและคอมพิวเตอร์ ถนัด ชอบเขียนโค้ด พัฒนาโปรแกรม เป้าหมายอาชีพคือ ทำงานในบริษัทขนาดใหญ่
after:  ชอบวิชา คณิตศาสตร์, คอมพิวเตอร์ สนใจด้าน เทคโนโลยีและคอมพิวเตอร์ ถนัด ชอบเขียนโค้ด พัฒนาโปรแกรม เป้าหมายอาชีพคือ ทำงานในบริษัทขนาดใหญ่
```

**กรณี 1b — ชุดเดียวกัน กดสลับวิชา** `subjects=["คอมพิวเตอร์","คณิตศาสตร์"]`
```
before: ชอบวิชา คอมพิวเตอร์, คณิตศาสตร์ สนใจด้าน เทคโนโลยีและคอมพิวเตอร์ ถนัด ชอบเขียนโค้ด พัฒนาโปรแกรม เป้าหมายอาชีพคือ ทำงานในบริษัทขนาดใหญ่
after:  ชอบวิชา คณิตศาสตร์, คอมพิวเตอร์ สนใจด้าน เทคโนโลยีและคอมพิวเตอร์ ถนัด ชอบเขียนโค้ด พัฒนาโปรแกรม เป้าหมายอาชีพคือ ทำงานในบริษัทขนาดใหญ่
```
หลังแก้ 1 และ 1b ได้ข้อความเดียวกันทุกตัวอักษร

**กรณี 2 — interests / skills / goals กดสลับทั้งหมด** `subjects=["คอมพิวเตอร์"], interests=["industry","tech"], skills=["creative","math"], goals=["high-income","career-growth"]`
```
before: ชอบวิชา คอมพิวเตอร์ สนใจด้าน การออกแบบและสื่อสร้างสรรค์, เทคโนโลยีและคอมพิวเตอร์ ถนัด ชอบเขียนโค้ด พัฒนาโปรแกรม, ชอบวิเคราะห์ แยกแยะ และหาสาเหตุของปัญหา เป้าหมายอาชีพคือ เป็นเจ้าของธุรกิจ, ทำงานในบริษัทขนาดใหญ่
after:  ชอบวิชา คอมพิวเตอร์ สนใจด้าน เทคโนโลยีและคอมพิวเตอร์, การออกแบบและสื่อสร้างสรรค์ ถนัด ชอบวิเคราะห์ แยกแยะ และหาสาเหตุของปัญหา, ชอบเขียนโค้ด พัฒนาโปรแกรม เป้าหมายอาชีพคือ ทำงานในบริษัทขนาดใหญ่, เป็นเจ้าของธุรกิจ
```

**กรณี 3 — มีตัวซ้ำและค่าที่ไม่รู้จัก** `interests=["tech","new-option","tech"]`
```
before: … สนใจด้าน เทคโนโลยีและคอมพิวเตอร์, new-option, เทคโนโลยีและคอมพิวเตอร์ …
after:  … สนใจด้าน เทคโนโลยีและคอมพิวเตอร์, new-option …
```

## 5. Tests — `eval/find_major_order_check.py` (19 tests)

ตรวจทั้งฟังก์ชัน `canonical_labels` และเส้นทาง `recommend_major_web` จริง โดยดัก `match_programs` เพื่อเก็บคำตอบที่ส่งเข้าการจัดอันดับ แล้วสร้างข้อความด้วย `build_match_query` ตัวจริง (ไม่เรียก DB, embedding หรือ Gemini)

| กลุ่ม | Tests |
|---|---|
| **A** Subjects | `["คณิตศาสตร์","คอมพิวเตอร์"]` กับ `["คอมพิวเตอร์","คณิตศาสตร์"]` ได้ query เดียวกันทุกตัวอักษร · ทุก permutation ของ 4 วิชาได้ query เดียว |
| **B** interests / skills / goals | ทุก permutation ของ 4 ตัวเลือกแรกในแต่ละข้อได้ query เดียว (3 tests) · สลับทุกข้อพร้อมกันได้ query เดียว · `build_profile_text` ก็คงที่ · เรียงตามลำดับใน `OPTION_LABELS` |
| **C** Duplicates | ตัวซ้ำไม่เปลี่ยน query · รหัสกับข้อความไทยของตัวเลือกเดียวกันนับเป็นข้อเดียว · ส่งข้อความไทยแทนรหัสได้ผลเท่ารหัส |
| **D** Unknown / free text | ทุก permutation ของค่าที่ไม่รู้จักปนกับที่รู้จักได้ผลเดียว · ที่รู้จักมาก่อน ที่ไม่รู้จักต่อท้าย · ไม่มีคำตอบหาย · subjects (ไม่มีตาราง) เรียงตามตัวอักษร · `None`/`[]` → `[]` |
| **E** Canonical input เดิม | query ของคำตอบที่เรียงมาตรฐานอยู่แล้ว = ข้อความ literal ที่กำหนด · เท่ากับผลของเส้นทางเดิม (`labels_of`) ทุกตัวอักษร · track / environment ยังแปลเหมือนเดิม |

**ยืนยันว่า tests จับ bug ได้จริง:** จำลองเส้นทางก่อนแก้ (แทน `routes.canonical_labels` ด้วย `labels_of`) → **8 / 19 fail** ได้แก่ A ทั้ง 2, B ระดับ endpoint ทั้ง 5, C ตัวซ้ำ 1 · หลังแก้ **19 / 19 OK**

## 6. Regression result

รันทุก suite ใน `eval/*_check.py` ยกเว้น `behaviour_check` (ยิง production) ด้วย `PYTHONPATH=<worktree>`, `JWT_SECRET=local-test-only`, `PYTHONIOENCODING=utf-8`, `CHAT_TOP_K=25`, DB local

| Suite | Tests | ผล |
|---|---|---|
| comparison_evidence_check | 30 | OK |
| conversation_context_check | 12 | OK |
| curriculum_facts_check | 16 | OK |
| degree_disambiguation_check | 25 | OK |
| eval_runner_check | 4 | OK |
| **find_major_order_check (ใหม่)** | **19** | **OK** |
| follow_up_scope_check | 21 | OK |
| gemini_quota_check | 6 | OK |
| mko_extraction_check | 45 | OK |
| multi_program_scope_check | 12 | OK |
| program_core_check | 7 | OK |
| rationale_key_check | 4 | OK |
| recommend_intent_check | 12 | OK |
| recommendation_reply_check | 27 | OK |
| structured_on_path_check | 32 | OK |
| structured_routing_check | 22 | OK |
| structured_shadow_check | 30 | OK |
| tuition_followup_check | 14 | OK |
| **รวม** | **338** (เดิม 319 + ใหม่ 19) | **0 fail** |

หมายเหตุ: `eval/match_query_check.py` ไม่ได้อยู่ใน branch นี้ (เป็นไฟล์ untracked ใน checkout หลัก `course-advisor-system`) เมื่อรันกับ backend ของ branch นี้ได้ 2/3 — test `test_request_wrapper_does_not_change_interest_vector` fail เพราะคาดพฤติกรรม `build_profile_text` ของ `program_match.py` เวอร์ชันที่ยังไม่ commit ใน checkout หลัก ไม่เกี่ยวกับการแก้รอบนี้ (`program_match.py` ไม่เปลี่ยนเทียบ HEAD) จึงไม่นับใน regression

## 7. Git diff (backend)

```diff
--- a/backend/app/api/routes/web_compat.py
+++ b/backend/app/api/routes/web_compat.py
@@ -32,7 +32,7 @@
-from app.services.web_compat import label_of, labels_of, match_by_title, normalise_title, shared_user
+from app.services.web_compat import canonical_labels, label_of, match_by_title, normalise_title, shared_user
@@ -246,13 +246,16 @@ def recommend_major_web(...)
     # (ดูเหตุผลและตารางใน services/web_compat.py)
+    #
+    # ข้อที่เลือกได้หลายข้อต้องผ่าน canonical_labels เพื่อให้คำตอบชุดเดียวกันได้คะแนนเดียวกัน
+    # ไม่ว่าผู้ใช้จะกดเลือกลำดับไหน
     answers = {
         "study_track": label_of("track", a["track"]) if a.get("track") else None,
         # ข้อวิชาที่ชอบส่งเป็นชื่อวิชาภาษาไทยอยู่แล้ว label_of จึงคืนค่าเดิมไป
-        "favorite_subjects": labels_of("subjects", a.get("subjects")),
-        "interests": labels_of("interests", a.get("interests")),
-        "aptitudes": labels_of("skills", a.get("skills")),
-        "career_goal": labels_of("goals", a.get("goals")),
+        "favorite_subjects": canonical_labels("subjects", a.get("subjects")),
+        "interests": canonical_labels("interests", a.get("interests")),
+        "aptitudes": canonical_labels("skills", a.get("skills")),
+        "career_goal": canonical_labels("goals", a.get("goals")),
         "work_environment": [label_of("environment", a["environment"])] if a.get("environment") else [],
     }

--- a/backend/app/services/web_compat.py
+++ b/backend/app/services/web_compat.py
@@ -145,6 +145,35 @@ def labels_of(field: str, values) -> list[str]:
     return [label_of(field, v) for v in (values or [])]
 
+# ลำดับมาตรฐานของตัวเลือกแต่ละข้อ = ลำดับที่เขียนไว้ใน OPTION_LABELS
+_LABEL_RANK: dict[str, dict[str, int]] = {
+    field: {label: rank for rank, label in enumerate(table.values())}
+    for field, table in OPTION_LABELS.items()
+}
+
+def canonical_labels(field: str, values) -> list[str]:
+    """ (docstring อธิบายเหตุผลและลำดับที่ใช้) """
+    rank = _LABEL_RANK.get(field, {})
+    unique = dict.fromkeys(labels_of(field, values))
+    return sorted(unique, key=lambda v: (0, rank[v], "") if v in rank else (1, 0, str(v)))
```

## 8. ผลกระทบหลัง deploy

- **เปลี่ยนหนึ่งครั้ง:** ผู้ใช้ที่เคยกดเลือกในลำดับที่ไม่ตรงกับลำดับมาตรฐาน จะได้ query ใหม่ (แบบ canonical) → เปอร์เซ็นต์และอาจรวมถึงอันดับขยับ **หนึ่งครั้ง** หลัง deploy
- **ไม่เปลี่ยน:** ผู้ใช้ที่กดตามลำดับมาตรฐานอยู่แล้ว (และไม่มีตัวซ้ำ) ได้ query เดิมทุกตัวอักษร จึงได้คะแนนเดิม (test E)
- **หลังจากนั้น:** คำตอบชุดเดียวกันได้ query เดียวกันเสมอ ไม่ว่ากดลำดับไหน → คะแนนคงที่ (ตราบที่เอกสารหลักสูตร, embedding model และสูตรไม่เปลี่ยน)
- ข้อความ `profileText` และข้อความที่ส่งให้ Gemini เขียนเหตุผลก็เรียงแบบ canonical ด้วย เพราะสร้างจาก answers ชุดเดียวกัน — prompt และโค้ดของ rationale ไม่ได้แก้ มีแค่ลำดับคำในโปรไฟล์ที่คงที่ขึ้น

## 9. Risks

| ความเสี่ยง | ระดับ | หมายเหตุ |
|---|---|---|
| คะแนนของบางเคสขยับหนึ่งครั้งหลัง deploy | ต่ำ | คาดไว้แล้ว อธิบายในข้อ 8 |
| ลำดับมาตรฐานผูกกับลำดับใน `OPTION_LABELS` ถ้าแก้ลำดับตารางในอนาคต คะแนนจะขยับหนึ่งครั้งอีก | ต่ำ | บันทึกไว้ใน docstring |
| ค่าที่ไม่รู้จักเรียงตาม Unicode code point ซึ่งไม่ใช่ลำดับพจนานุกรมไทย | ต่ำ | ต้องการแค่ deterministic ไม่ใช่ลำดับสวย |
| `POST /match` (หน้าทดลองบน IP และตัวกลาง Vercel `ProjectPnru/api/recommend-major.js`) ยังไม่ canonicalize | กลาง (นอกขอบเขต) | หน้าเว็บจริงบนโดเมนใช้ `/recommend-major` ซึ่งแก้แล้ว · ถ้าต้องการให้ `/match` คงที่ด้วยต้องอนุมัติแยก |
| ความคลาดเคลื่อนระดับ float ของ embedding | ต่ำมาก | ผลที่บันทึกไว้เดิม 26/26 ตรงกัน |

## 10. Proposed controlled deployment (ยังไม่ทำ — รออนุมัติ)

1. **Pre-deploy (read-only):** ยืนยัน production = commit `9879653`, image `b046f908…`, `STRUCTURED_ANSWERS=on`, health 200, publication `7999a1c2…` 103/156, review_decisions 37
2. **Package:** `git -c core.autocrlf=false archive <fix-commit> backend llm` · manifest diff เทียบ release เดิม ต้องต่างเฉพาะ 2 ไฟล์ `web_compat.py` · CR = 0 · scp แล้วตรวจ SHA
3. **Backup / rollback:** tag image ปัจจุบันเป็น `rollback-9879653` · backup `.env` + compose · ไม่ต้อง backup DB (ไม่มีการเขียน DB / migration) แต่ทำได้ตามมาตรฐานเดิม
4. **Deploy backend only:** build image ใหม่ · `docker compose -f docker-compose.prod.yml up -d --no-deps backend` · ไม่แตะ `.env` (`STRUCTURED_ANSWERS` คง `on`), postgres, frontend, caddy, ollama
5. **Post-deploy ก่อน traffic:** health 200, restarts 0, errors 0, env / publication / counts ไม่เปลี่ยน, ในคอนเทนเนอร์มี `canonical_labels` และ `canonical_labels("subjects", ["คอมพิวเตอร์","คณิตศาสตร์"]) == ["คณิตศาสตร์","คอมพิวเตอร์"]`
6. **Controlled smoke ≤ 4 requests** ไปที่ `POST /api/recommend-major` (แต่ละ request เรียก Gemini เขียนเหตุผล 1 ครั้ง — ต้องได้รับอนุมัติ):
   - คู่ที่ 1: คำตอบชุดเดียวกัน subjects สลับลำดับ → `primary/alternatives` และ `matchScore` ต้องเท่ากันทุกตัว
   - คู่ที่ 2: คำตอบชุดเดียวกัน interests/skills/goals สลับลำดับ → `matchScore` ต้องเท่ากันทุกตัว, `profileText` เท่ากัน
7. **Chat / Structured regression:** ไม่มี request เพิ่ม — Phase 2 code ไม่ถูกแตะ ตรวจเพียง `configured_mode()=on` และ counts ไม่เปลี่ยน
8. **Rollback criteria:** health ผิดปกติ, error ใหม่, คู่ smoke ได้ `matchScore` ต่างกัน, HTTP ≠ 200 → `docker tag rollback-9879653` กลับ + recreate backend only แล้ว STOP
9. บันทึก `~/DEPLOYED_COMMIT`, `~/ROLLBACK.txt` และรายงาน deployment แยก

---

**FIND-MAJOR ORDER FIX (OFFLINE): PASS** — 338 tests / 0 fail · commit เฉพาะ fix + tests + report · ไม่ deploy · ไม่ push · รออนุมัติ
