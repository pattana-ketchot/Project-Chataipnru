# MKO Phase 2 — Degree-Level Disambiguation: Controlled Shadow Deployment

**สรุป: deploy สำเร็จ shadow validation ผ่านทุกข้อ ไม่พบ regression จึงไม่ได้ rollback**
- อาการเดิมหายแล้ว: ถามระบุ "วิทยาศาสตรมหาบัณฑิต" ได้เล่ม ป.โท และ "ปรัชญาดุษฎีบัณฑิต" ได้เล่ม ป.เอก
- คำถามที่ไม่ระบุระดับ → ไม่เดาให้ (route เป็น RAG `multiple_degree_levels`)
- production คงไว้ที่ `STRUCTURED_ANSWERS=shadow` · ไม่ได้ publish ใหม่ · ไม่ได้ review เพิ่ม · ไม่มี migration · ไม่ได้ push branch · ไม่ได้เริ่ม Phase 3

เวลาเป็น UTC

---

## 1. ก่อน deploy

| ขั้น | ผล |
|---|---|
| git status / diff | มีเฉพาะงาน degree disambiguation (3 ไฟล์ service) + tests (4 ไฟล์) + รายงาน Phase 2 (9 ฉบับ) ไม่มีงานอื่นปน |
| test suites | **275 tests / 0 fail** (16 ชุด รันกับฐานข้อมูล local ไม่มี production traffic ไม่ใช้ Gemini ไม่รัน behaviour_check) |
| secret scan | pattern (API key / private key / DB URL ที่มีรหัสผ่าน) = ไม่พบ · เทียบค่าจริงของ `GEMINI_API_KEY`, `JWT_SECRET`, `POSTGRES_PASSWORD` แบบไม่พิมพ์ค่า = ไม่พบในไฟล์ที่ commit |
| commit | `668f74c` — 16 ไฟล์ ทุก blob เป็น LF (CR = 0) |
| migration | **ไม่มี** — รอบนี้ไม่มี schema change (ตรวจว่า `docker-compose.prod.yml` ไม่เปลี่ยน และไม่มีไฟล์ใน `db/migrations` ถูกแก้) |
| STRUCTURED_ANSWERS | `.env` = shadow, ในคอนเทนเนอร์ = shadow (ก่อนและหลัง deploy) |
| ไฟล์บน server ก่อนคัดลอก | backend + llm 63 ไฟล์ **ตรงกับ `~/release-1493db2` ทุกไฟล์** (ไม่มีไฟล์แปลกปลอม) |

### 1.1 Commit

| รายการ | ค่า |
|---|---|
| commit | `668f74c` (`668f74ca60ef8eb5377c26bf8df78403cfd0d8fb`) บน branch `mko-phase2` ต่อจาก `1493db2` |
| ข้อความ | fix(mko): pick the curriculum by degree level when a programme has several of them |
| ไฟล์ที่ deploy จริง (backend + llm) | ต่างจาก `1493db2` **3 ไฟล์**: `course_scope.py`, `structured_intent.py`, `curriculum_facts.py` |
| ไฟล์อื่นใน commit | tests 4 ไฟล์ + รายงาน 9 ฉบับ (ไม่อยู่ใน image) |

### 1.2 Backup (บน server, สิทธิ์ 600)

| รายการ | ค่า |
|---|---|
| database | `~/backups/prod_pre_degree_fix_20260916T081701Z.dump` — `pg_dump -Fc` ทั้งฐาน 53,650,985 bytes, `pg_restore -l` อ่านได้ 28 TABLE DATA |
| SHA-256 | `8e50b9a15e7b5ee1e6c6d5bc8e1101dad7d9c42eb8890350ab334dbbc63bb153` (`sha256sum -c` OK) |
| config | `env.before_degree_fix_20260916T081701Z`, `docker-compose.prod.yml.before_degree_fix_20260916T081701Z` |
| บันทึกเดิม | `DEPLOYED_COMMIT.1493db2`, `ROLLBACK.txt.1493db2` |

---

## 2. Deploy

| รายการ | ค่า |
|---|---|
| archive | `git -c core.autocrlf=false archive 668f74c backend llm` — SHA-256 `d63110d681b1e8eb8581e4f913af9c9c24f857b8200818c54e2d4741e3b433d2` (ตรงกันทั้ง local และ server), 63 ไฟล์, CR = 0 |
| ตรวจก่อน build | `.env` = shadow · compose hash ไม่เปลี่ยน · rollback tag พร้อม |
| หลังคัดลอก | backend + llm บน server 63 ไฟล์ **ตรงกับ `668f74c`** |
| build / restart | `docker compose build backend` แล้ว `up -d --no-deps backend` (log: `~/backups/deploy_668f74c_20260916T081756Z.log`) |
| **image ใหม่** | `sha256:3fd6c40018da65448364565693829c111e3e06fa633a24fa3d13e6baedfd0f96` |
| เริ่มทำงาน | 2026-09-16T08:18:08Z |
| ในคอนเทนเนอร์ | backend + llm 63 ไฟล์ตรงกับ `668f74c` · `STRUCTURED_ANSWERS=shadow` |
| คอนเทนเนอร์อื่น | postgres, frontend, caddy, ollama, db-viewer **ไม่ถูกแตะ** (uptime เดิม) |
| `~/DEPLOYED_COMMIT` / `~/ROLLBACK.txt` | อัปเดตแล้ว (commit, image, rollback tag, backup + SHA) |

---

## 3. Rollback (พร้อมใช้ ยังไม่ได้รัน)

| รายการ | ค่า |
|---|---|
| commit ก่อนหน้า | `1493db2` |
| image ก่อนหน้า | `sha256:23bd7aa465af5c08506dfa6a8b132840758b38ce93f84c52397c8bc902240647` tag `course-advisor-system-backend:rollback-1493db2` |
| โค้ดก่อนหน้า | `~/release-1493db2` (ตรวจแล้วว่าตรงกับไฟล์บน server ก่อน deploy ทุกไฟล์) |
| ฐานข้อมูล | ไม่ต้องย้อน — รอบนี้ไม่มี migration และไม่ได้เขียนข้อมูล (backup ข้อ 1.2 มีไว้เผื่อ) |

```
cd ~/course-advisor-system
cp -a ~/release-1493db2/backend/. backend/ && cp -a ~/release-1493db2/llm/. llm/
docker tag course-advisor-system-backend:rollback-1493db2 course-advisor-system-backend:latest
docker compose -f docker-compose.prod.yml up -d --no-build --no-deps backend
# ตรวจ: docker inspect -f '{{.Image}}' course-advisor-system-backend-1 -> sha256:23bd7aa465af...
```

ขั้นตอนเต็มอยู่บนสุดของ `~/ROLLBACK.txt` แล้ว

---

## 4. Shadow validation (9 คำขอผ่าน `/api/chat`)

เวลา 08:18:51–08:20:20Z เว้นระยะ 8 วินาที · ไม่ได้รัน behaviour_check และไม่มี batch test
**คำตอบที่ผู้ใช้เห็นยังมาจากระบบเดิมทุกข้อ** (`STRUCTURED_ANSWERS=shadow`) — ตารางนี้คือสิ่งที่ structured เลือกใน `mko.shadow_answers`

| # | คำถาม | route / reason | หลักสูตรที่ structured เลือก | source | ผล |
|---|---|---|---|---|---|
| 1 | ระบุ "วิทยาศาสตรมหาบัณฑิต" + ชื่อสาขา — อาชีพ | structured / single_programme_field | **ป.โท 2568** | agri68_master.pdf **6 ข้อ** | ✔ ไม่เลือก ป.เอก |
| 2 | ระบุ "ปรัชญาดุษฎีบัณฑิต" + ชื่อสาขา — อาชีพ | structured / single_programme_field | **ป.เอก 2568** | agri68_phd.pdf **6 ข้อ** | ✔ |
| 3 | ใช้คำว่า "ป.โท" แทนชื่อปริญญาเต็ม | structured / single_programme_field | **ป.โท 2568** | agri68_master.pdf 6 ข้อ | ✔ |
| 4 | ใช้คำว่า "ป.เอก" | structured / single_programme_field | **ป.เอก 2568** | agri68_phd.pdf 6 ข้อ | ✔ |
| 5 | ชื่อสาขาเดียวกัน **ไม่ระบุระดับ** | **rag / `multiple_degree_levels`** | — (ไม่เลือกเล่มใดเลย) | — | ✔ ไม่ arbitrary select |
| 6 | หน่วยกิต ป.โท | structured / single_programme_field | ป.โท 2568 | agri68_master.pdf · **36** | ✔ (comparison = unclear ดูข้อ 4.1) |
| 7 | หน่วยกิต ป.เอก | structured / single_programme_field | ป.เอก 2568 | agri68_phd.pdf · **48** | ✔ (comparison = unclear ดูข้อ 4.1) |
| 8 | สาขาปริญญาตรีปกติ (วิทยาศาสตร์เครื่องสำอาง) | structured / single_programme_field | วิทยาศาสตร์เครื่องสำอาง 2566 | cos66.pdf 7 ข้อ · comparison **agree** | ✔ พฤติกรรมเดิมไม่เปลี่ยน |
| 9 | out-of-scope | rag / no_supported_field | — | — | ✔ พฤติกรรมเดิม |

- **สรุป route:** structured 7 · rag 2 (`multiple_degree_levels` 1, `no_supported_field` 1)
- **comparison:** agree 5 · unclear 2 (ข้อ 6–7) · not_compared 2 (ข้อ 5, 9)
- **publication_id ของทุกแถวที่ answered:** `d0311dd5-ba1d-44dc-8460-66542394cefa` (ตัวเดิม)
- **latency:** 1–7 ms
- **ข้อ 5 คำตอบที่ผู้ใช้เห็น** มาจาก RAG และเล่าทั้งสองระดับแยกหัวข้อให้เอง ซึ่งเป็นพฤติกรรมที่ยอมรับได้ระหว่าง shadow

### 4.1 ข้อสังเกต: comparison "unclear" ของหน่วยกิต ป.โท/ป.เอก (ไม่ใช่ regression)

- ค่าที่ structured ให้ **ถูกต้อง**: ป.โท 36 หน่วยกิต (agri68_master.pdf), ป.เอก 48 หน่วยกิต (agri68_phd.pdf) และคำตอบที่ผู้ใช้เห็นก็ระบุ 36 / 48 เช่นกัน
- ตัวเทียบผลของ shadow มีเพดานล่าง `_TOTAL_CREDIT_FLOOR = 100` ([structured_shadow.py:48-49](backend/app/services/structured_shadow.py:48)) ตั้งไว้ตั้งแต่ a4201cc โดยสมมติว่า "หน่วยกิตรวมของปริญญาตรีมากกว่า 100 เสมอ ตัวเลขที่น้อยกว่าคือหน่วยกิตรายหมวด"
- หลักสูตรปริญญาโท/เอกมียอดรวมต่ำกว่าเพดานนี้ ตัวเทียบจึงอ่านว่า "ไม่พบตัวเลขในคำตอบ" แล้วสรุปเป็น unclear
- **เป็นข้อจำกัดเดิมของตัวเทียบ ไม่ได้เกิดจากการแก้รอบนี้** และเพิ่งมาเห็นเพราะตอนนี้หลักสูตรบัณฑิตศึกษาถูกเลือกได้ถูกเล่มแล้ว
- ไม่ได้แก้ในรอบนี้เพราะอยู่นอกขอบเขต (ห้าม unrelated refactor) — เสนอให้พิจารณาในรอบถัดไป

---

## 5. Publication / live counts (ต้องไม่เปลี่ยน)

| รายการ | ก่อน | หลัง |
|---|---|---|
| publication ที่มีผล | `d0311dd5-ba1d-44dc-8460-66542394cefa` | **เท่าเดิม** |
| `mko.v_live_values` | 100 | **100** |
| `mko.v_live_list_items` | 90 | **90** |
| `mko.publications` | 3 | 3 |
| `mko.review_decisions` | 14 | 14 |
| `public.courses` / `course_chunks` | 24 / 9039 | 24 / 9039 |
| `mko.shadow_answers` | 61 | 70 (+9 จาก validation รอบนี้) |
| `chat_messages` | — | +18 (9 คำขอ × 2 ข้อความ) |

---

## 6. Production health

| ตรวจ | ผล |
|---|---|
| backend `/health` ในคอนเทนเนอร์ | `{"status":"ok"}` ภายใน ~2 วินาทีหลังเริ่ม |
| `https://stpnru-advisor.duckdns.org/api/health` | 200 |
| restart count | **0** |
| log backend | error / traceback / exception = **0** (ตั้งแต่เริ่มคอนเทนเนอร์ และช่วง 15 นาทีล่าสุด) |
| `STRUCTURED_ANSWERS` | `shadow` ทั้งใน `.env` และในคอนเทนเนอร์ |
| คอนเทนเนอร์อื่น | ไม่ถูกแตะ |

---

## 7. ข้อจำกัดที่เหลือ

1. **ตัวเทียบผล shadow ของหน่วยกิตยังใช้เพดาน 100** — หลักสูตร ป.โท/ป.เอก จะได้ unclear เสมอ (ข้อ 4.1) ควรแก้ให้ตัวเทียบรู้ระดับปริญญาในรอบถัดไป
2. **อ่านระดับปริญญาจากข้อความไทย** — ยังไม่รองรับคำอังกฤษ เช่น "master degree" / "M.Sc."
3. **ถ้าไม่ระบุระดับ สาขาที่มีหลายระดับจะไม่ได้คำตอบจาก structured เลย** (ตกไป RAG ตามที่ออกแบบ) ถ้าต้องการให้ตอบพร้อมบอกว่ามีสองระดับ ต้องออกแบบรูปแบบคำตอบเพิ่ม
4. **อาศัยชื่อปริญญาในชื่อหลักสูตร** เพราะ `mko.curricula.degree_level` ยังเป็น NULL ทุกแถว — การเติมคอลัมน์นี้ตอน publish เป็นงานรอบถัดไป (ไม่ต้อง migrate schema)
5. **คลังมีกลุ่มหลายระดับเพียงกลุ่มเดียว** (การจัดการเทคโนโลยีการเกษตรฯ 2568) การทดสอบกับข้อมูลจริงจึงครอบคลุมเท่าที่มี ชุดทดสอบสแกนกลุ่มเองทุกครั้ง
6. **ค้างจากรอบก่อน:** careers ของการแพทย์แผนไทยประยุกต์ 2565 และคณิตศาสตร์ 2564 ยัง candidate · หน่วย P2 ที่เลื่อน 6 หน่วย · admission ยังไม่มีใน live · สาธารณสุขศาสตร์ยังเป็น draft

---

## 8. สิ่งที่ยังไม่ได้ทำ

- `STRUCTURED_ANSWERS=on` / Phase 3
- publish ใหม่ / review เพิ่ม / เปลี่ยน publish policy
- schema migration (รอบนี้ไม่มี schema change)
- extraction changes / unrelated refactor
- push branch — commit `668f74c` อยู่ใน worktree เท่านั้น
- รายงานฉบับนี้ยังไม่ commit
