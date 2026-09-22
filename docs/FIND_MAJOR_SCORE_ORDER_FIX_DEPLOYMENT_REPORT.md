# Find-Major Score Order Fix — Controlled Production Deployment Report

วันที่ deploy: 2026-09-17T17:14:39Z (UTC) = 2026-09-18 00:14 เวลาไทย
ขอบเขต: backend only · ไม่มี migration / DB write · ไม่แตะ `.env` (`STRUCTURED_ANSWERS=on` คงเดิม) · ไม่แตะ frontend / postgres / caddy / ollama · ไม่ push

---

## 1. Deployed commit / image

| รายการ | ก่อน | หลัง |
|---|---|---|
| commit | `9879653` | **`6762333`** (`fix: give the same find-major answers the same score whatever order they were picked in`) |
| backend image | `sha256:b046f9086076776c26da78b7989636ddc930e2a4bde8ddacb4a8341496859e83` | **`sha256:3ae6bed7753568a6a961a5b0e20a7e8cc1136c09a406e1ec1781cf4dcf8f2223`** |
| rollback tag | — | `course-advisor-system-backend:rollback-9879653` → `b046f9086076` |
| backend started | 2026-09-17T09:24:13Z | 2026-09-17T17:14:39Z, restarts 0 |

## 2. Pre-deploy

**Baseline (ตรวจแล้วตรงทุกค่า — script หยุดทันทีถ้าค่าใดไม่ตรง)**

| รายการ | ค่า |
|---|---|
| `~/DEPLOYED_COMMIT` | `commit=9879653` |
| `.env` / container | `STRUCTURED_ANSWERS=on` / `on` |
| image | `b046f908…` |
| public health | 200 |
| backend | running, restarts 0, errors 0 |
| publication | `7999a1c2-e2fd-4b19-98d1-b50b3212f8d9` |
| live values / list items | 103 / 156 |
| review_decisions / publications | 37 / 4 |
| migration | `002_mko_review_publish` |
| courses / course_chunks | 24 / 9039 |
| mko.shadow_answers | 111 (เพิ่มจาก 104 หลัง Step B ด้วย traffic จริงของผู้ใช้ — ไม่ใช่ baseline ที่ล็อก) |

**Git / secret scan**
- HEAD `6762333acf52a082f1d45839ae8ab0fc16f94d58`, git status สะอาด
- `git diff --name-only 9879653 6762333 -- backend llm` = 2 ไฟล์: `backend/app/api/routes/web_compat.py`, `backend/app/services/web_compat.py`
- secret scan 4 ไฟล์ของ commit (เทียบ pattern + ค่าจริงของ key ที่อ่อนไหวใน `.env` ของ server โดยไม่พิมพ์ค่า): **hits = 0**

**Release package**
- `git -c core.autocrlf=false archive 6762333 backend llm` → `release-6762333.tar.gz` SHA-256 `289c16007cb17651d3b0b8835b20c06346ec8a65b8fdcda52e5148715896bec4`
- 63 ไฟล์, ไฟล์ที่มี CR = 0
- manifest diff เทียบ release `9879653` ต่างเพียง 2 ไฟล์:
  - `backend/app/api/routes/web_compat.py` `69bd87e8…` → `5568b81b…`
  - `backend/app/services/web_compat.py` `ff9e42d8…` → `f73e33a6…`
- บน server: `sha256sum -c` OK · release แตกแล้วตรง manifest · ไฟล์ของ server ก่อน deploy ตรง `9879653` (ไม่มี drift)

**Backups (TS `20260917T171410Z`)**

| ไฟล์ | SHA-256 | สิทธิ์ |
|---|---|---|
| `~/backups/env.before_find_major_fix_20260917T171410Z` | `4d37472dc9a6055b2198c95fe58ab15008056586733a03c865a6b3763fe13d27` | 600 |
| `~/backups/docker-compose.prod.yml.before_find_major_fix_20260917T171410Z` | `fc95afb84355bb953880d9211ce9211677517351630aacc8bfef791683530d1f` | 600 |
| `~/backups/prod_pre_find_major_fix_20260917T171410Z.dump` (pg_dump อ่านอย่างเดียว, 53,719,275 bytes) | `5b334dd4cf60453c6c75cdee9ccbd9d3c14b812022b3900d80b29ca4d4459dc4` | 600 |

`find_major_fix_config_20260917T171410Z.sha256` + `sha256sum -c` → OK ทั้งคู่ · สำรอง `~/DEPLOYED_COMMIT.9879653`, `~/ROLLBACK.txt.9879653`

## 3. Deploy (backend only)

```
cp -a ~/release-6762333/backend/. backend/ && cp -a ~/release-6762333/llm/. llm/
# server files == 6762333 (63)
docker compose -f docker-compose.prod.yml build backend        # เฉพาะชั้น COPY backend/llm ที่เปลี่ยน, requirements cached
docker compose -f docker-compose.prod.yml up -d --no-deps backend
# up done 2026-09-17T17:14:39Z · .env unchanged (4d37472d…)
```

Container อื่นไม่ถูก recreate: caddy (Up 8 days), frontend (Up 13 days), postgres (Up 4 weeks, healthy), ollama (Up 4 weeks, healthy), db-viewer (Up 3 days)

## 4. Files deployed

| ไฟล์ | การเปลี่ยนแปลง |
|---|---|
| `backend/app/services/web_compat.py` | เพิ่ม `_LABEL_RANK` + `canonical_labels()` |
| `backend/app/api/routes/web_compat.py` | subjects / interests / skills / goals ใช้ `canonical_labels` |

ไฟล์อื่นอีก 61 ไฟล์ใน image ตรงกับ `9879653` ทุกไบต์ (ตรวจด้วย manifest ในคอนเทนเนอร์)

## 5. Post-deploy ก่อนยิง test

| ตรวจ | ผล |
|---|---|
| internal `/health` | `{"status":"ok"}` |
| public `/api/health` | 200 |
| backend | running, restarts 0 (ไม่มี healthcheck กำหนดใน compose → `no-healthcheck`) |
| errors / traceback / exception | 0 |
| `STRUCTURED_ANSWERS` (.env / container) | `on` / `on` · `.env` SHA ไม่เปลี่ยน · compose SHA ไม่เปลี่ยน |
| `configured_mode()` / allow-list | `on` / `['careers','edition_year','objectives','total_credits']` |
| container files vs `6762333` | ตรงทั้ง 63 ไฟล์ |
| `canonical_labels` ในคอนเทนเนอร์ | มี · route ใช้ฟังก์ชันเดียวกัน · `["คอมพิวเตอร์","คณิตศาสตร์"]` → `["คณิตศาสตร์","คอมพิวเตอร์"]` · `["health","tech","tech"]` → `["เทคโนโลยีและคอมพิวเตอร์","คณิตศาสตร์และการวิเคราะห์"]` |
| ค่าคงที่ของสูตร | `_PCT_FLOOR 0.35`, `_PCT_CEILING 0.72`, `_TITLE_WEIGHT 0.5`, `CHUNKS_PER_COURSE 5` (ไม่เปลี่ยน) |
| publication / counts | `7999a1c2…` / 103 / 156 / 37 / 4 / shadow 111 / `002_mko_review_publish` / courses 24 / chunks 9039 |

## 6. Controlled production test — 4 requests

`POST https://stpnru-advisor.duckdns.org/api/recommend-major` เว้นระยะ ≥ 10 วินาที · `courses` = 12 สาขาปริญญาตรีที่คณะเปิดรับ (`c01`–`c12`) · Gemini ถูกเรียก **4 ครั้งพอดี** (log: `generateContent 200` × 4) ใช้เขียนเหตุผลเท่านั้น

ชุดคำตอบร่วม
- Pair A: `track=sci-math, interests=["tech","health"], skills=["creative","math"], goals=["career-growth"], environment=office`
- Pair B: `track=sci-math, subjects=["คอมพิวเตอร์","ศิลปะ"], environment=remote`

| # | เวลา (UTC) | ความต่างของ input | HTTP | เวลา | primary | alternatives |
|---|---|---|---|---|---|---|
| A1 | 17:15:36 | `subjects=["คณิตศาสตร์","คอมพิวเตอร์"]` | 200 | 7.7 s | เทคโนโลยีสารสนเทศ **53** | วิทยาการคอมพิวเตอร์ **53**, คณิตศาสตร์ **51** |
| A2 | 17:15:53 | `subjects=["คอมพิวเตอร์","คณิตศาสตร์"]` | 200 | 2.9 s | เทคโนโลยีสารสนเทศ **53** | วิทยาการคอมพิวเตอร์ **53**, คณิตศาสตร์ **51** |
| B1 | 17:16:06 | `interests=["tech","industry"], skills=["math","creative"], goals=["career-growth","high-income"]` | 200 | 2.9 s | วิทยาการคอมพิวเตอร์ **58** | เทคโนโลยีสารสนเทศ **55**, คอมพิวเตอร์แอนิเมชันและมัลติมีเดีย **53** |
| B2 | 17:16:19 | `interests=["industry","tech"], skills=["creative","math"], goals=["high-income","career-growth"]` | 200 | 2.9 s | วิทยาการคอมพิวเตอร์ **58** | เทคโนโลยีสารสนเทศ **55**, คอมพิวเตอร์แอนิเมชันและมัลติมีเดีย **53** |

**profileText ที่ได้**
- A1 = A2: `เรียนสายวิทย์-คณิต ชอบวิชา คณิตศาสตร์, คอมพิวเตอร์ สนใจด้าน เทคโนโลยีและคอมพิวเตอร์, คณิตศาสตร์และการวิเคราะห์ ถนัด ชอบวิเคราะห์ แยกแยะ และหาสาเหตุของปัญหา, ชอบเขียนโค้ด พัฒนาโปรแกรม เป้าหมายอาชีพคือ ทำงานในบริษัทขนาดใหญ่ อยากทำงานแบบ ทำงานในออฟฟิศ`
- B1 = B2: `เรียนสายวิทย์-คณิต ชอบวิชา คอมพิวเตอร์, ศิลปะ สนใจด้าน เทคโนโลยีและคอมพิวเตอร์, การออกแบบและสื่อสร้างสรรค์ ถนัด ชอบวิเคราะห์ แยกแยะ และหาสาเหตุของปัญหา, ชอบเขียนโค้ด พัฒนาโปรแกรม เป้าหมายอาชีพคือ ทำงานในบริษัทขนาดใหญ่, เป็นเจ้าของธุรกิจ อยากทำงานแบบ ทำงานภาคสนาม`

`summary` ทั้ง 4 ครั้งเป็นข้อความ "คะแนนของหลายสาขาใกล้เคียงกันมาก…" (confidence low) เหมือนกันในแต่ละคู่

### Pair A equality — PASS
- HTTP 200 ทั้งคู่
- primary เหมือนกัน (`c11` 53)
- alternatives เหมือนกัน (`c06` 53, `c04` 51) รวมลำดับของสองสาขาที่ได้ 53 เท่ากัน
- matchScore ทุกสาขาเหมือนกัน · profileText เหมือนกันทุกตัวอักษร

### Pair B equality — PASS
- HTTP 200 ทั้งคู่
- primary เหมือนกัน (`c06` 58) · alternatives เหมือนกัน (`c11` 55, `c05` 53)
- matchScore ทุกสาขาเหมือนกัน · profileText canonical เหมือนกันทุกตัวอักษร

หมายเหตุ: ข้อความ `reason` ต่างกันในแต่ละ request เพราะ Gemini เขียนใหม่ทุกครั้ง — ไม่เกี่ยวกับคะแนนและอยู่นอกขอบเขตของการแก้ (ส่วน `c05` ทั้งสองครั้งได้ข้อความ "เอกสารหลักสูตรของสาขานี้ไม่ได้ระบุข้อมูลที่เชื่อมโยง…" เหมือนกัน)

## 7. Production state หลัง smoke

| ตรวจ | ผล |
|---|---|
| public health / internal | 200 / `{"status":"ok"}` |
| backend | image `3ae6bed7…`, running, restarts 0 |
| errors / traceback / exception | 0 · WARNING 0 · HTTP 5xx 0 |
| `/recommend-major` ใน log | 4 × `200 OK` |
| `STRUCTURED_ANSWERS` (.env / container) | `on` / `on` · `.env` SHA `4d37472d…` ไม่เปลี่ยน · compose SHA `fc95afb8…` ไม่เปลี่ยน |
| publication / live values / list items | `7999a1c2…` / 103 / 156 |
| review_decisions / publications / migration | 37 / 4 / `002_mko_review_publish` |
| shadow_answers / courses / course_chunks | 111 / 24 / 9039 (ไม่เปลี่ยน — `/recommend-major` ไม่เขียน DB) |
| container อื่น | ไม่ถูกแตะ |

บันทึกบน server: `~/DEPLOYED_COMMIT` → `commit=6762333` (พร้อม image, rollback tag, backups) · `~/ROLLBACK.txt` เพิ่มขั้นตอน rollback ของรอบนี้ไว้บนสุด · log: `~/predeploy_find_major_fix.log`, `~/deploy_find_major_fix.log`

## 8. Rollback status

**ไม่ต้อง rollback** — ไม่พบเกณฑ์ใดเลย (matchScore ต่างในคู่เดียวกัน, HTTP ≠ 200, backend error ใหม่, health ผิดปกติ, Structured config เปลี่ยน) → คง deployment ไว้

ขั้นตอน rollback ที่เตรียมไว้ (ยังไม่ได้ใช้):
```bash
cd ~/course-advisor-system
cp -a ~/release-9879653/backend/. backend/ && cp -a ~/release-9879653/llm/. llm/
docker tag course-advisor-system-backend:rollback-9879653 course-advisor-system-backend:latest
docker compose -f docker-compose.prod.yml up -d --no-build --no-deps backend
# check: image -> sha256:b046f9086076… · STRUCTURED_ANSWERS ยัง on (.env ไม่ถูกแตะ) · health 200
```

## 9. ข้อจำกัดที่ยังอยู่

- `POST /match` (หน้าทดลองบน IP และตัวกลาง Vercel ใน `ProjectPnru/api/recommend-major.js`) ยังไม่ canonicalize — นอกขอบเขตที่อนุมัติ
- เปอร์เซ็นต์ของผู้ใช้ที่เคยกดเลือกไม่ตรงลำดับมาตรฐานขยับหนึ่งครั้งหลัง deploy นี้ (คาดไว้แล้ว) หลังจากนี้คำตอบชุดเดียวกันได้คะแนนเดียวกัน
- A1/A2 มีสองสาขาได้ 53 เท่ากัน ลำดับของทั้งคู่คงที่ในการทดสอบนี้ แต่ตัวเลขที่เท่ากันแปลว่าอันดับของสองสาขานี้ไม่ควรตีความว่าต่างกัน (ระบบแสดงคำเตือน confidence low อยู่แล้ว)
- รายงานนี้ยังไม่ commit

---

FIND-MAJOR ORDER FIX PRODUCTION: PASS
