# MKO Phase 2 — Controlled Deployment Step A: ON-Path Code, Flag Remains SHADOW

**สรุป: deploy สำเร็จ ผ่านทุกข้อ ไม่ได้ rollback**
- production รันโค้ด ON-path (commit `9879653`) แล้ว แต่ **`STRUCTURED_ANSWERS=shadow`** ทั้ง `.env` และในคอนเทนเนอร์
- ผู้ใช้ยังได้คำตอบ RAG ทุกคำขอ · ไม่มีคำตอบ structured ถูกส่งให้ผู้ใช้ · structured ยังคำนวณและบันทึกผลเหมือนเดิม
- บันทึก shadow ใหม่มี `configured_mode = shadow` และ `served_source = rag` ครบทุกแถว
- publication / live counts / review_decisions ไม่เปลี่ยน · ไม่มี migration · health ok · restarts 0 · error 0
- **ไม่ได้เปิด on · ไม่ได้ทำ Step B · ไม่ได้ push**

เวลาเป็น UTC

---

## 1. ก่อน deploy

| ขั้น | ผล |
|---|---|
| git status / diff | production code ที่เปลี่ยนจาก `8d6d271` มีเฉพาะ `backend/app/services/chat.py` และ `backend/app/services/structured_shadow.py` · tests 2 ไฟล์ · รายงาน Phase 2 · ไม่มี source อื่น |
| regression offline | **319 tests / 0 fail** (17 suites, DB local, ไม่มี production traffic, ไม่ใช้ Gemini, ไม่รัน behaviour_check) |
| secret scan | 10 ไฟล์ที่ commit: pattern (API key / sk- / private key / DB URL มีรหัสผ่าน / JWT) = 0 · เทียบค่าจริง 5 ตัวของ `.env` บน server (ไม่พิมพ์ค่า) = 0 · ไม่มีอีเมลในรายงาน |
| migration | ไม่มี — `mko.schema_migrations` ล่าสุดยังเป็น `002_mko_review_publish` · compose hash `fc95afb8…` ไม่เปลี่ยน |
| drift บน server | backend + llm 63 ไฟล์บน server ตรงกับ `~/release-8d6d271` · ไฟล์ในคอนเทนเนอร์เดิมตรงกับ `8d6d271` |

### 1.1 Commit

| รายการ | ค่า |
|---|---|
| commit | **`9879653`** (`9879653acffe88857d1cd62fd08c66c92dc92b14`) บน `mko-phase2` ต่อจาก `8d6d271` · ไม่ได้ push |
| ข้อความ | feat(mko): serve structured answers when STRUCTURED_ANSWERS=on |
| diff stat | 10 files changed, 2113 insertions(+), 19 deletions(-) · ทุก blob LF (CR = 0) |

| ไฟล์ที่ commit | บรรทัด |
|---|---|
| `backend/app/services/chat.py` | +25 / −6 |
| `backend/app/services/structured_shadow.py` | +68 / −10 |
| `eval/structured_shadow_check.py` | +5 / −3 |
| `eval/structured_on_path_check.py` | +385 (ใหม่) |
| `docs/MKO_PHASE2_ON_PATH_IMPLEMENTATION_REPORT.md` | +279 |
| `docs/MKO_PHASE2_FINAL_SHADOW_VALIDATION.md` | +204 |
| `docs/MKO_PHASE2_P3_PUBLICATION_REPORT.md` | +245 |
| `docs/MKO_PHASE2_P3_REVIEW_APPLY_REPORT.md` | +218 |
| `docs/MKO_PHASE2_P3_REVIEW_PREVIEW.md` | +517 |
| `docs/MKO_PHASE2_SHADOW_CREDIT_COMPARATOR_ROLLOUT_REPORT.md` | +167 |

ไฟล์ที่เข้า image ต่างจาก `8d6d271` เพียง 2 ไฟล์ (ตรวจด้วย manifest ของ archive 63 ไฟล์)

### 1.2 Backup (server, สิทธิ์ 600)

| ไฟล์ | รายละเอียด | SHA-256 |
|---|---|---|
| `~/backups/prod_pre_on_path_20260917T073953Z.dump` | `pg_dump -Fc` ทั้งฐาน 53,708,565 bytes · `pg_restore -l` = 28 TABLE DATA · `sha256sum -c` OK | `baef04b99a70949fbca011afcdfba8a7efef8fdfba20d68457a6a3ebaf76a8c2` |
| `~/backups/env.before_on_path_20260917T073953Z` | สำเนา `.env` | `b8a692d14e0cdb5c2a81243355b820b8c5a6bc76aac8d3d6d5607acc65071753` |
| `~/backups/docker-compose.prod.yml.before_on_path_20260917T073953Z` | สำเนา compose | `fc95afb84355bb953880d9211ce9211677517351630aacc8bfef791683530d1f` |
| `~/DEPLOYED_COMMIT.8d6d271`, `~/ROLLBACK.txt.8d6d271` | บันทึกเดิม | — |

### 1.3 Images

| รายการ | ค่า |
|---|---|
| image ก่อนหน้า | `sha256:5fb3ef402848c028ce81425d676ae4f24d1d7550e7f2f39c438935de3fd76161` (8d6d271) |
| rollback tag | **`course-advisor-system-backend:rollback-8d6d271`** → `5fb3ef402848` |
| image ใหม่ | **`sha256:b046f9086076776c26da78b7989636ddc930e2a4bde8ddacb4a8341496859e83`** (9879653) |

---

## 2. Deploy

| รายการ | ค่า |
|---|---|
| archive | `git -c core.autocrlf=false archive 9879653 backend llm` · SHA-256 `a7678df337f486764095e2565f67ed8f58b92e84a64b3ed6f7a35dec5eec9344` (ตรง local / server) · 63 ไฟล์ · CR = 0 |
| สคริปต์ | ส่งด้วย `scp` · SHA-256 `825cfca2…` ตรงกันทั้งสองฝั่ง · ด่านแรกตรวจว่า `.env` เป็น `STRUCTURED_ANSWERS=shadow` ไม่เช่นนั้นหยุด |
| scope | **backend only** — `docker compose build backend` + `up -d --no-deps backend` · ไม่แตะ postgres / frontend / caddy / ollama / db-viewer |
| log | `~/backups/deploy_9879653_20260917T074040Z.log` |
| หลังคัดลอก | backend + llm บน server 63 ไฟล์ตรงกับ `9879653` |
| เริ่มทำงาน | 2026-09-17T07:40:41Z |
| ในคอนเทนเนอร์ | 63 ไฟล์ตรงกับ `9879653` · `configured_mode() = shadow` · `USER_FACING_FIELDS = [careers, edition_year, objectives, total_credits]` · `structured_reply(...)` คืน **None** ในโหมด shadow |
| `~/DEPLOYED_COMMIT` / `~/ROLLBACK.txt` | อัปเดตแล้ว (commit, image, rollback tag, backup + SHA) |

---

## 3. Flag / publication / counts ก่อน-หลัง

| รายการ | ก่อน | หลัง |
|---|---|---|
| deployed commit | 8d6d271 | **9879653** |
| `STRUCTURED_ANSWERS` (.env) | shadow | **shadow** |
| `STRUCTURED_ANSWERS` (คอนเทนเนอร์) | shadow | **shadow** |
| live publication | 7999a1c2-e2fd-4b19-98d1-b50b3212f8d9 | **7999a1c2-e2fd-4b19-98d1-b50b3212f8d9** |
| live values / list_items | 103 / 156 | **103 / 156** |
| review_decisions | 37 | **37** |
| publications | 4 | 4 |
| schema migration ล่าสุด | 002_mko_review_publish | 002_mko_review_publish |
| shadow_answers | 90 | 94 (+4 จาก smoke) |

---

## 4. Health / restarts / errors

| ตรวจ | ผล |
|---|---|
| `/health` ในคอนเทนเนอร์ | `{"status":"ok"}` |
| `https://stpnru-advisor.duckdns.org/api/health` | **200** (หลัง deploy และหลัง smoke) |
| คอนเทนเนอร์ backend | running · **restarts 0** |
| log ตั้งแต่เริ่มคอนเทนเนอร์ | error / traceback / exception = **0** · คำเตือนของ structured / shadow = 0 |
| คอนเทนเนอร์อื่น | ไม่ถูกแตะ (postgres / ollama 4 weeks healthy, frontend 12 days, caddy 8 days, db-viewer 3 days) |

---

## 5. Shadow smoke (4 คำขอผ่าน `/api/chat`, 07:42:29–07:42:54Z)

| # | คำถาม | คำตอบที่ผู้ใช้เห็น | route / field | structured (คำนวณใน shadow) | publication | comparison | configured_mode | served_source | ผล |
|---|---|---|---|---|---|---|---|---|---|
| 1 | หลักสูตรวิทยาการคอมพิวเตอร์ เรียนกี่หน่วยกิต | RAG: "…ไม่น้อยกว่า 130 หน่วยกิต" | structured / total_credits | answered · CS 2566 (cs66.pdf ห.2) + 2561 (cs61.pdf ห.6) | 7999a1c2… | agree | **shadow** | **rag** | ✔ |
| 2 | หลักสูตรคณิตศาสตร์ปรับปรุงปีไหน | RAG: "…มีการปรับปรุงในปี พ.ศ. 2564" | structured / edition_year | answered · 2569 (ma69.pdf ห.1) + 2564 (ma64.pdf ห.2) | 7999a1c2… | partial (RAG ขาดฉบับ 2569 เหมือนก่อน deploy) | **shadow** | **rag** | ✔ |
| 3 | หลักสูตรเทคโนโลยีสารสนเทศ พ.ศ. 2566 คุณสมบัติของผู้เข้าศึกษามีอะไรบ้าง | RAG: รายการ 5 ข้อ (เหมือนก่อน deploy) | structured / admission | answered · IT 2566 (it66.pdf ห.16) | 7999a1c2… | agree | **shadow** | **rag** | ✔ admission ไม่เปลี่ยน |
| 4 | สาขาคหกรรมศาสตร์จบไปทำอาชีพอะไรได้บ้าง (control ของ field ใน allow-list) | RAG: รายการ 11 ข้อ | structured / careers | answered · คหกรรมศาสตร์ 2564 (ds2564.pdf ห.2) | 7999a1c2… | agree | **shadow** | **rag** | ✔ |

- **ผู้ใช้ไม่ได้รับคำตอบ structured เลย:** `served_reply` ไม่มีบรรทัด "ที่มา:" และไม่เท่ากับ `structured_answer` ทั้ง 4 แถว · แถวตั้งแต่ deploy: served_source = structured **0**, configured_mode = on **0**
- **structured shadow computation ทำงานเหมือนเดิม:** route / field / หลักสูตร / ฉบับ / publication / comparison ตรงกับผลของคำถามเดียวกันก่อน deploy (CS agree, คณิตศาสตร์ partial, IT admission agree, คหกรรมศาสตร์ agree) · latency 4–8 ms
- **RAG ไม่ regression:** คำตอบทั้ง 4 ข้อเหมือนคำตอบ RAG ก่อน deploy (มาจาก answer cache ของรุ่นตรรกะเดียวกัน ตอบใน 0.1–0.7 วินาที) — แสดงว่าเส้นทางแคช + shadow ในโหมด shadow ส่งคำตอบ RAG ตามเดิม
- ไม่ได้รัน behaviour_check · ไม่มี batch test

---

## 6. Rollback (พร้อมใช้ ยังไม่ได้รัน)

| รายการ | ค่า |
|---|---|
| commit ก่อนหน้า | `8d6d271` |
| image ก่อนหน้า | `sha256:5fb3ef40…` tag `course-advisor-system-backend:rollback-8d6d271` |
| โค้ดก่อนหน้า | `~/release-8d6d271` (ตรวจแล้วว่าตรงกับไฟล์บน server ก่อน deploy ทุกไฟล์) |
| ฐานข้อมูล | ไม่ต้องย้อน — ไม่มี migration และ deploy ไม่ได้เขียนข้อมูล (backup ข้อ 1.2 มีไว้เผื่อ) |
| flag | ไม่ต้องเปลี่ยน — เป็น shadow ตลอด |

```
cd ~/course-advisor-system
cp -a ~/release-8d6d271/backend/. backend/ && cp -a ~/release-8d6d271/llm/. llm/
docker tag course-advisor-system-backend:rollback-8d6d271 course-advisor-system-backend:latest
docker compose -f docker-compose.prod.yml up -d --no-build --no-deps backend
# ตรวจ: docker inspect -f '{{.Image}}' course-advisor-system-backend-1 -> sha256:5fb3ef402848...
```

ขั้นตอนเดียวกันอยู่บนสุดของ `~/ROLLBACK.txt`

---

## 7. Limitations

1. **Step A ยืนยันเฉพาะโหมด shadow บน production** — เส้นทาง on ทดสอบแล้วแบบ offline (32 tests) แต่ยังไม่เคยทำงานบน production จนกว่าจะอนุมัติ Step B
2. **smoke ทั้ง 4 ข้อได้คำตอบจาก answer cache** — ยืนยันเส้นทางแคช + shadow ได้ แต่ไม่ได้เรียกโมเดลเขียนคำตอบใหม่ (ตั้งใจใช้คำถามเดิมเพื่อเทียบก่อน/หลังได้ตรง) · เส้นทางไม่ใช้แคชของ RAG ไม่ได้ถูกแก้ในรอบนี้และผ่าน regression offline
3. คอลัมน์ `mode` ของ `mko.shadow_answers` ยังเป็น `shadow` เสมอ — ต้องอ่านโหมดจริงจาก `comparison_detail.configured_mode`
4. known limitations ที่ยอมรับแล้วยังอยู่: careers en65 glyph "น้ า" · ช่องว่างใน objectives · ชื่อหลักสูตรเดิมที่ถูกแทน · admission ตอบด้วย RAG · ขั้นเตรียมคำตอบของ RAG ยังทำงานก่อนการตัดสินในโหมด on

---

## 8. สิ่งที่ยังไม่ได้ทำ

- `STRUCTURED_ANSWERS=on` / Step B
- Phase 3 เพิ่มเติม / P4 / review / publish
- extraction / normalize / schema / routing / RAG prompt / admission
- push branch — commit `9879653` อยู่ใน worktree เท่านั้น
- รายงานฉบับนี้ยังไม่ commit

**ไฟล์ของรอบนี้บน server:** `~/release-9879653(.tar.gz)`, `~/r9879653.manifest`, `~/deploy_9879653.sh`, `~/postdeploy_9879653.sh`, `~/backups/prod_pre_on_path_20260917T073953Z.dump(.sha256)`, `~/backups/env.before_on_path_*`, `~/backups/docker-compose.prod.yml.before_on_path_*`, `~/backups/deploy_9879653_20260917T074040Z.log`
