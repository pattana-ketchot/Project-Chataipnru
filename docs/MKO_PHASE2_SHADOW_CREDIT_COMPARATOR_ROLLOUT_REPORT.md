# MKO Phase 2 — Shadow Credit Comparator: Controlled Shadow Deployment

**สรุป: deploy สำเร็จ shadow validation ผ่านทั้ง 3 ข้อ ไม่พบ regression จึงไม่ได้ rollback**
- ป.โท 2568 = 36 และ ป.เอก 2568 = 48 เปลี่ยนจาก `unclear` เป็น **`agree`** พร้อม `degree_levels` ถูกระดับ
- ปริญญาตรี (วิทยาการคอมพิวเตอร์ 130) ยัง `agree` ตามพฤติกรรมเดิม
- production คงไว้ที่ `STRUCTURED_ANSWERS=shadow` · ไม่ได้ publish ใหม่ · ไม่ได้ review เพิ่ม · ไม่มี migration · ไม่ได้ push branch · ไม่ได้เริ่ม Phase 3

เวลาเป็น UTC

---

## 1. ก่อน deploy

| ขั้น | ผล |
|---|---|
| git status / diff | production code ที่ต่างจาก `668f74c` มี **ไฟล์เดียว**: `backend/app/services/structured_shadow.py` (ตรวจทั้ง `git diff --name-only 668f74c 8d6d271 -- backend llm` และ manifest ของ archive: 63 ไฟล์ ต่าง 1 บรรทัด) |
| test suites | **287 tests / 0 fail** (16 ชุด ฐานข้อมูล local ไม่มี production traffic ไม่ใช้ Gemini ไม่รัน behaviour_check) |
| secret scan | pattern (Google API key / sk- / private key / DB URL มีรหัสผ่าน / JWT) = 0 · เทียบค่าจริง 5 ตัวจาก `.env` ของ server (`ADVISOR_API_PASSWORD`, `ADVISOR_INGEST_PASSWORD`, `GEMINI_API_KEY`, `JWT_SECRET`, `POSTGRES_PASSWORD`) แบบไม่พิมพ์ค่า = 0 |
| migration | **ไม่มี** — ไม่มี schema change, `docker-compose.prod.yml` hash เดิม `fc95afb8…` ก่อนและหลัง |
| STRUCTURED_ANSWERS | `.env` = shadow, ในคอนเทนเนอร์ = shadow (ก่อนและหลัง) |
| drift บน server | backend + llm 63 ไฟล์บน server **ตรงกับ `~/release-668f74c`** และไฟล์ในคอนเทนเนอร์เดิมตรงกับ `668f74c` |

### 1.1 Commit

| รายการ | ค่า |
|---|---|
| commit | `8d6d271` (`8d6d2716a1fd4bc14228df9c5b8b371e1a5fac72`) บน `mko-phase2` ต่อจาก `668f74c` |
| ข้อความ | fix(mko): compare graduate total credits in the shadow comparator |
| ไฟล์ | `backend/app/services/structured_shadow.py`, `eval/structured_shadow_check.py`, `docs/MKO_PHASE2_SHADOW_CREDIT_COMPARATOR_REPORT.md`, `docs/MKO_PHASE2_DEGREE_DISAMBIGUATION_ROLLOUT_REPORT.md` (รายงานรอบก่อนที่ค้าง commit) — ทุก blob LF (CR = 0) |
| ไฟล์ที่เข้า image | `structured_shadow.py` เท่านั้นที่เปลี่ยน (tests / docs ไม่อยู่ใน image) |

### 1.2 Backup (บน server, สิทธิ์ 600)

| รายการ | ค่า |
|---|---|
| database | `~/backups/prod_pre_shadow_credit_fix_20260916T172817Z.dump` — `pg_dump -Fc` ทั้งฐาน 53,662,355 bytes, `pg_restore -l` อ่านได้ 28 TABLE DATA |
| SHA-256 | `0da3ef1825e350e86ae4dfe8862bb500d8958709b00ec91b6eca96364e4431a6` (`sha256sum -c` OK) |
| config | `env.before_shadow_credit_fix_20260916T172817Z`, `docker-compose.prod.yml.before_shadow_credit_fix_20260916T172817Z` |
| บันทึกเดิม | `~/DEPLOYED_COMMIT.668f74c`, `~/ROLLBACK.txt.668f74c` |

---

## 2. Deploy

| รายการ | ค่า |
|---|---|
| archive | `git -c core.autocrlf=false archive 8d6d271 backend llm` — SHA-256 `1c736670f6d6f0de0b34b139329cdd9d18c839136ce40bf706b1ab67ca42e4ff` (ตรงกันทั้ง local และ server), 63 ไฟล์, CR = 0 |
| หลังคัดลอก | backend + llm บน server 63 ไฟล์ **ตรงกับ `8d6d271`** |
| build / restart | `docker compose -f docker-compose.prod.yml build backend` แล้ว `up -d --no-deps backend` (log: `~/backups/deploy_8d6d271_20260916T174823Z.log`) — layer pip install ใช้ cache |
| **image ใหม่** | `sha256:5fb3ef402848c028ce81425d676ae4f24d1d7550e7f2f39c438935de3fd76161` |
| เริ่มทำงาน | 2026-09-16T17:48:25Z |
| ในคอนเทนเนอร์ | backend + llm 63 ไฟล์ตรงกับ `8d6d271` · import แล้วพบ `_total_credits_in_reply` และ `_GRADUATE_LEVELS = {doctoral, master}` · `STRUCTURED_ANSWERS=shadow` |
| คอนเทนเนอร์อื่น | postgres, frontend, caddy, ollama, db-viewer **ไม่ถูกแตะ** (uptime เดิม 4 สัปดาห์ / 12 วัน / 7 วัน / 2 วัน) |
| `~/DEPLOYED_COMMIT` / `~/ROLLBACK.txt` | อัปเดตแล้ว (commit, image, rollback tag, backup + SHA) |

**เหตุการณ์ระหว่างทาง (ไม่มีผลกับ production):** การส่งสคริปต์ deploy ครั้งแรกผ่าน stdin ของ ssh ได้ไฟล์ขนาด 0 byte สคริปต์จึงไม่ทำงานเลย ตรวจแล้วว่า backend ยังเป็น image `3fd6c400…` และไฟล์เดิม ไม่มีอะไรเปลี่ยน จากนั้นส่งสคริปต์ใหม่ด้วย `scp` ตรวจ SHA-256 ตรงกัน (`ade000c4…`) แล้วจึงรัน

---

## 3. Rollback (พร้อมใช้ ยังไม่ได้รัน)

| รายการ | ค่า |
|---|---|
| commit ก่อนหน้า | `668f74c` |
| image ก่อนหน้า | `sha256:3fd6c40018da65448364565693829c111e3e06fa633a24fa3d13e6baedfd0f96` tag `course-advisor-system-backend:rollback-668f74c` |
| โค้ดก่อนหน้า | `~/release-668f74c` (ตรวจแล้วว่าตรงกับไฟล์บน server ก่อน deploy ทุกไฟล์) |
| ฐานข้อมูล | ไม่ต้องย้อน — ไม่มี migration และ deploy ไม่ได้เขียนข้อมูล (backup ข้อ 1.2 มีไว้เผื่อ) |

```
cd ~/course-advisor-system
cp -a ~/release-668f74c/backend/. backend/ && cp -a ~/release-668f74c/llm/. llm/
docker tag course-advisor-system-backend:rollback-668f74c course-advisor-system-backend:latest
docker compose -f docker-compose.prod.yml up -d --no-build --no-deps backend
# ตรวจ: docker inspect -f '{{.Image}}' course-advisor-system-backend-1 -> sha256:3fd6c40018da...
```

ขั้นตอนเดียวกันอยู่บนสุดของ `~/ROLLBACK.txt`

---

## 4. Shadow validation (3 คำขอผ่าน `/api/chat`)

เวลา 18:12:47–18:13:07Z เว้นระยะ 8 วินาที · **3 คำขอ** (ไม่เกิน 4 ตามที่อนุมัติ) · ไม่ได้รัน behaviour_check

| # | คำถาม | route / reason | structured (publication `d0311dd5…`) | source | comparison | comparison_detail |
|---|---|---|---|---|---|---|
| 1 | หลักสูตรวิทยาศาสตรมหาบัณฑิต สาขาวิชา… เรียนกี่หน่วยกิต | structured / single_programme_field | ป.โท 2568 = **36** | agri68_master.pdf p.6 | **agree** | `{"expected": [36], "found_in_reply": [36], "degree_levels": ["master"]}` |
| 2 | หลักสูตรปรัชญาดุษฎีบัณฑิต สาขาวิชา… เรียนกี่หน่วยกิต | structured / single_programme_field | ป.เอก 2568 = **48** | agri68_phd.pdf p.6 | **agree** | `{"expected": [48], "found_in_reply": [48], "degree_levels": ["doctoral"]}` |
| 3 | หลักสูตรวิทยาการคอมพิวเตอร์ เรียนกี่หน่วยกิต | structured / single_programme_field | 2566 = **130**, 2561 = **130** | cs66.pdf p.2, cs61.pdf p.6 | **agree** | `{"expected": [130], "found_in_reply": [130], "degree_levels": ["bachelor"]}` |

- **ทุกแถว** `mode = shadow`, `structured_status = answered`, `served_status = answered`, `publication_id = d0311dd5-ba1d-44dc-8460-66542394cefa`, latency 4–8 ms
- **เทียบกับรอบก่อน deploy** (คำถามเดียวกันใน validation ของ `668f74c`): ข้อ 1–2 เดิม `unclear` → ตอนนี้ `agree`
- **ข้อ 3 (bachelor regression):** เส้นทางปริญญาตรียังใช้กฎเดิม (เลข ≥ 100) ได้ `agree` ตามเดิม และสองฉบับที่ค่าเท่ากันถูกรวมเป็น expected `[130]` เหมือนเดิม
- `comparison` ของทุกแถวหลัง deploy: agree 3 / อื่นๆ 0

### 4.1 คำตอบที่ผู้ใช้เห็นยังมาจากระบบเดิม

| # | เวลาตอบ | คำตอบที่ผู้ใช้เห็น (ย่อ) |
|---|---|---|
| 1 | 0.5 s | "…มีจำนวนหน่วยกิตรวมตลอดหลักสูตรไม่น้อยกว่า 36 หน่วยกิต" |
| 2 | 0.1 s | "…ทั้งแผน 1 (แผน 1.1) และแผน 2 (แผน 2.1) มีจำนวนหน่วยกิตรวมตลอดหลักสูตรไม่น้อยกว่า 48 หน่วยกิต" |
| 3 | 2.7 s | "…กำหนดจำนวนหน่วยกิตรวมตลอดหลักสูตรไม่น้อยกว่า 130 หน่วยกิต" |

- เป็นคำตอบรูปแบบ RAG เดิม ไม่มีรูปแบบคำตอบ structured (`ที่มา:`) ในคำตอบที่ผู้ใช้ได้รับเลย (0/3)
- ข้อ 1–2 ตอบเร็วเพราะมาจาก answer cache ของคำถามเดียวกันรอบก่อน — ข้อความเดียวกับที่ผู้ใช้เคยเห็น โหมด shadow ยังบันทึกผลสำหรับคำตอบจากแคชตามปกติ (`shadow_submit` ถูกเรียกหลังได้คำตอบทุกทาง)

### 4.2 Negative control (ไม่ยิง production)

ข้อ 4 ตรวจจาก local test แทน เพราะการยิง production ไม่จำเป็น — `GraduateCreditCompareChecks` ในชุด 287 tests ก่อน deploy

| กรณี | ผล |
|---|---|
| ปริญญาตรี 130 แต่คำตอบมีแค่ "หมวดวิชาศึกษาทั่วไป 30 / หมวดวิชาเฉพาะ 24 หน่วยกิต" | unclear (ไม่ agree) |
| ป.โท 36 แต่คำตอบมีแค่ "หมวดวิชาบังคับ 24 / หมวดวิชาเลือก 6 หน่วยกิต" | unclear |
| ป.โท 36 "ตลอดหลักสูตร 2 ปี มีวิทยานิพนธ์ 12 หน่วยกิต" | unclear |
| ป.เอก 48 แต่คำตอบบอกยอดรวม 36 | disagree |
| ป.โท 36 คำตอบมี 12 / 6 / 18 + ยอดรวม 36 | agree, found = [36] |

---

## 5. Publication / live counts (ต้องไม่เปลี่ยน)

| รายการ | ก่อน | หลัง |
|---|---|---|
| publication ที่มีผล | `d0311dd5-ba1d-44dc-8460-66542394cefa` | **เท่าเดิม** |
| `mko.v_live_values` | 100 | **100** |
| `mko.v_live_list_items` | 90 | **90** |
| `mko.publications` | 3 | 3 |
| `mko.review_decisions` | 14 | 14 |
| `public.courses` | 24 | 24 |
| `mko.shadow_answers` | 70 | 73 (+3 จาก validation รอบนี้) |

---

## 6. Production health

| ตรวจ | ผล |
|---|---|
| backend `/health` ในคอนเทนเนอร์ | `{"status":"ok"}` |
| `https://stpnru-advisor.duckdns.org/api/health` | 200 (หลัง deploy และหลัง validation) |
| restart count | **0** |
| log backend ตั้งแต่เริ่มคอนเทนเนอร์ | error / traceback / exception = **0** · คำเตือนเกี่ยวกับ shadow = 0 |
| `STRUCTURED_ANSWERS` | `shadow` ทั้งใน `.env` และในคอนเทนเนอร์ |
| คอนเทนเนอร์อื่น | ไม่ถูกแตะ |

---

## 7. ข้อจำกัดที่เหลือ

1. **คำตอบบัณฑิตศึกษาที่ไม่มีคำบอกบริบทยอดรวม** (เช่น "เรียน 36 หน่วยกิต" หรือ "ทั้งหมด 36 หน่วยกิต") ยังได้ `unclear` — ตั้งใจให้พลาดทางระมัดระวัง คำตอบจริงทั้งสองรายการใช้ "หน่วยกิตรวมตลอดหลักสูตร"
2. **ยอดรวมปริญญาตรีที่ผิดแต่ต่ำกว่า 100** ยังได้ `unclear` แทน `disagree` (พฤติกรรมเดิม)
3. **ระดับปริญญาอ่านจากชื่อหลักสูตรใน `courses.title`** เพราะ `mko.curricula.degree_level` ยังว่าง — ชื่อที่อ่านไม่ได้จะใช้กฎเดิม (ปัจจุบัน 20/20 ค่า live อ่านได้)
4. **ป.โท/ป.เอก หลายแผนที่ยอดรวมต่างกัน** ข้อมูลปัจจุบันมีหนึ่งค่าต่อเล่ม ถ้าอนาคตมีหลายค่า ผลจะขึ้นกับการ extract
5. **แถว shadow เก่า** (สอง `unclear` ของรอบ `668f74c`) ไม่ถูกคำนวณใหม่ — ถ้าจะสรุปสถิติ comparison ต้องแยกช่วงก่อน/หลัง 2026-09-16T17:48:25Z
6. ตัวเทียบยังเป็นกฎข้อความแบบง่าย ใช้ดูแนวโน้ม ไม่ใช่ตัวตัดสินความถูกต้อง
7. **ค้างจากรอบก่อน:** อ่านระดับปริญญาจากคำอังกฤษยังไม่ได้ · สาขาหลายระดับที่ไม่ระบุระดับตกไป RAG · careers การแพทย์แผนไทยประยุกต์ 2565 และคณิตศาสตร์ 2564 ยัง candidate · admission ยังไม่มีใน live

---

## 8. สิ่งที่ยังไม่ได้ทำ

- `STRUCTURED_ANSWERS=on` / Phase 3
- publish ใหม่ / review เพิ่ม / เปลี่ยน publish policy
- schema migration / extraction / routing / RAG / prompt changes
- behaviour_check / large production tests
- push branch — commit `8d6d271` อยู่ใน worktree เท่านั้น
- รายงานฉบับนี้ยังไม่ commit
