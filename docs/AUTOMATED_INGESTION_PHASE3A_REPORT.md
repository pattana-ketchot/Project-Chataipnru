# Phase 3A — Database + Backend Approval Foundation

| | |
|---|---|
| วันที่ | 28 กันยายน 2569 |
| ฐาน | commit `a0655ef` บน `mko-phase2` |
| อ้างอิงแบบ | [AUTOMATED_INGESTION_PHASE3_DESIGN.md](docs/AUTOMATED_INGESTION_PHASE3_DESIGN.md) |
| สถานะ | **เขียนเสร็จ · ทดสอบ 84/84 ผ่าน · ยังไม่ commit / push / deploy** |
| ไม่ได้ทำ | Admin UI · ingest-worker · เรียก `pipeline.ingest` · embedding · แตะ RAG/Gemini/Supabase/Caddy · scheduler · deploy/migration/restart production · merge main |

สิ่งที่ได้ในรอบนี้คือ flow `crawl_sources → review queue → admin decision` ครบวง
**ยังไม่มี ingestion** การกดอนุมัติบันทึกเพียงว่าคนอนุญาตแล้ว ไม่ทำให้อะไรเข้าคลังความรู้

---

## 0. ตรวจ implementation ปัจจุบันก่อนแก้ — ผลการตรวจ

ตรวจแล้วว่า **แบบใน Phase 3 Design ไม่ขัดกับ source ปัจจุบัน** ทั้ง `require_admin`,
`get_current_user`, `get_db`, แบบแผนของ `document_store.py`, สิทธิ์ใน `20-roles.sh`
และ `Caddyfile` เป็นไปตามที่แบบอธิบายไว้ทุกข้อ

แต่**พบช่องว่างในตัวแบบเอง 1 ข้อ** ที่ต้องปิดเพื่อให้ข้อกำหนดข้อ 12 ทำได้จริง

> แบบระบุสิทธิ์ของ `advisor_api` ไว้เพียง `SELECT ON mko.v_crawl_queue`
> และระบุด้วยว่าวิวนั้น **ต้องไม่มี `staging_path`**
> ผลคือ backend อ่านที่อยู่ไฟล์ไม่ได้ จึงเปิด PDF ให้ผู้ดูแลดูไม่ได้เลย

ปิดช่องนี้ด้วย **column-level grant ที่แคบที่สุด** ไม่ใช่ให้สิทธิ์ทั้งตาราง

```sql
GRANT SELECT (id, file_sha256, staging_path, status) ON mko.crawl_sources TO advisor_api;
```

backend อ่านได้สี่คอลัมน์นี้เท่านั้น — `approved_by`, `last_error`, `http_etag`,
`review_reason` และคอลัมน์อื่นอ่านไม่ได้แม้เขียนโค้ดผิด (มีข้อทดสอบยืนยัน)
และยังเขียนตารางนี้ไม่ได้เลยตามแบบเดิม

นี่เป็นการเติมสิ่งที่แบบต้องมีอยู่แล้วเพื่อให้ข้อกำหนดที่สั่งมาทำได้ ไม่ใช่การเปลี่ยนทิศ
จึงดำเนินการต่อและบันทึกไว้ที่นี่ให้เห็นชัด

---

## 1. Schema — migration 004 (additive ล้วน)

[`db/migrations/004_crawl_decisions.sql`](db/migrations/004_crawl_decisions.sql) · 153 บรรทัด

**ไม่ `ALTER` ไม่ `DROP` อะไรเลย** ไม่แก้ `v_crawl_pending` ของ 003 ไม่แตะ `public`
ไม่แก้ CHECK ของ `crawl_sources.status` (ค่า `ingested`/`ignored` มีอยู่ในชุดเดิมแล้ว)

### `mko.crawl_decisions` — 15 คอลัมน์

| กลุ่ม | คอลัมน์ |
|---|---|
| ตัวระบุ | `id`, `crawl_source_id` → `mko.crawl_sources(id)` ON DELETE CASCADE |
| ผูกกับเนื้อไฟล์ | `file_sha256` **NOT NULL** + CHECK `^[0-9a-f]{64}$` |
| การตัดสิน | `decision` (`approve`/`ignore`), `decided_by`, `decided_at`, `note` |
| หลักสูตรที่คนยืนยัน | `course_code`, `course_title` |
| ผลการนำเข้า (Phase 3B เขียน) | `ingest_started_at`, `ingest_finished_at`, `ingest_error`, `document_id` |
| การถอน | `superseded_at`, `superseded_by` |

### เหตุผลของการแยกตาราง (ข้อกำหนดข้อ 3)

`pipeline/crawl/state.py::upsert()` ตั้ง `status` และ `needs_review` ทับ**ทุกรอบ
ที่ crawl โดยไม่มีเงื่อนไข** ถ้าเก็บผลอนุมัติไว้ในคอลัมน์ของ `crawl_sources`

- แถวที่คนกด "ไม่เกี่ยวข้อง" จะกลับเข้าคิวในรอบถัดไป
- แถวที่นำเข้าแล้วแต่จับคู่หลักสูตรกำกวมจะติดค้างในคิวตลอดไป

อยู่คนละตารางแล้ว crawler เขียนทับไม่ได้ และ backend ไม่ต้องมีสิทธิ์เขียน `crawl_sources` เลย

### ผูกกับ `crawl_source_id + file_sha256` (ข้อกำหนดข้อ 4)

หลักเดียวกับ `mko.review_decisions` ใน migration 002 — คนอนุมัติ "เนื้อไฟล์นี้"
ไม่ใช่ "URL นี้ตลอดไป" ถ้าคณะอัปโหลดไฟล์ใหม่ทับ URL เดิม `sha` เปลี่ยน
การอนุมัติเดิมจึงไม่ครอบของใหม่และแถวกลับเข้าคิวให้คนดูอีกครั้ง (มีข้อทดสอบยืนยัน)

### CHECK constraint 7 ข้อ

| constraint | บังคับอะไร |
|---|---|
| `file_sha256 ~ '^[0-9a-f]{64}$'` | ลายนิ้วมือต้องถูกรูปแบบ |
| `decision IN ('approve','ignore')` | ไม่มีคำตัดสินนอกสองแบบ |
| `length(btrim(decided_by)) > 0` | ต้องรู้ว่าใครตัดสิน |
| `crawl_decisions_approve_has_course` | **approve ต้องระบุหลักสูตร** ส่วน ignore ไม่ต้อง |
| `crawl_decisions_supersede_complete` | ถอนแล้วต้องรู้ว่าใครถอน |
| `crawl_decisions_finished_after_started` | จบการนำเข้าได้เฉพาะที่เริ่มแล้ว |
| `crawl_decisions_only_approve_ingests` | ignore ห้ามมีผลการนำเข้า |

### ป้องกันการตัดสินใจซ้ำที่ระดับฐานข้อมูล (ข้อกำหนดข้อ 6)

```sql
CREATE UNIQUE INDEX uq_crawl_decisions_active
    ON mko.crawl_decisions (crawl_source_id, file_sha256) WHERE superseded_at IS NULL;
```

เป็น **partial unique index** ทำให้หนึ่งไฟล์มีการตัดสินใจที่ยังใช้อยู่ได้ครั้งเดียว
แต่ยังตัดสินใหม่ได้หลังถอน ทดสอบสองแบบ (ดูหัวข้อ 5)

### `mko.v_crawl_queue` (ข้อกำหนดข้อ 2)

ต่างจาก `v_crawl_pending` ของ 003 สองเรื่อง

1. กรองแถวที่มีการตัดสินใจที่ยังใช้อยู่ออกด้วย `NOT EXISTS` — คนกดแล้วหายจากคิว
   และไม่กลับมาแม้ crawler รอบถัดไปตั้ง `needs_review` ใหม่
2. **ไม่มี `staging_path`** มีแต่ `has_staged_file` เป็นค่าจริง/เท็จ

### สิทธิ์ที่ 004 ให้

| role | `mko.crawl_sources` | `mko.crawl_decisions` | `mko.v_crawl_queue` |
|---|---|---|---|
| `advisor_api` (backend) | `SELECT` เฉพาะ 4 คอลัมน์ · **เขียนไม่ได้** | `SELECT`, `INSERT` · `UPDATE` เฉพาะ `superseded_at`, `superseded_by` | `SELECT` |
| `advisor_ingest` (crawler + worker 3B) | `SELECT/INSERT/UPDATE` (จาก 003) | `SELECT/INSERT/UPDATE` | `SELECT` |
| ทั้งคู่ | **ไม่มี `DELETE` เลย** | **ไม่มี `DELETE` เลย** | |

---

## 2. Backend API

[`backend/app/api/routes/crawl_review.py`](backend/app/api/routes/crawl_review.py) · 153 บรรทัด

| Method | Path | ทำอะไร | ตอบ |
|---|---|---|---|
| `GET` | `/crawl-review/pending` | คิวรอตรวจ + ตัวนับสรุป | 200 |
| `GET` | `/crawl-review/{id}` | รายละเอียดแถวเดียว | 200 / 404 |
| `GET` | `/crawl-review/{id}/pdf` | เปิดไฟล์ในคิวแบบ inline | 200 / 404 |
| `POST` | `/crawl-review/{id}/approve` | บันทึก approve | 201 / 409 / 422 / 404 |
| `POST` | `/crawl-review/{id}/ignore` | บันทึก ignore | 201 / 409 / 422 / 404 |
| `POST` | `/crawl-review/{id}/undo` | ถอนการตัดสินใจ | 200 / 409 / 404 |

ยืนยันจาก OpenAPI ของแอปจริงว่าลงทะเบียนครบ 6 เส้นทาง และเส้นทางเดิมทั้ง 27 เส้นทาง
ยังอยู่ครบ (`/chat-web`, `/documents/{id}/pdf`, `/courses`, `/auth/login` ตรวจทีละตัว)

### ทำไม prefix ไม่ใช่ `/admin`

`Caddyfile:37` ส่ง `/api/admin/*` **ทั้ง prefix** ไปที่บริการ `webapi` ซึ่งเป็นโค้ดของ
ทีมออกแบบและคุยกับ Supabase ถ้าตั้งเส้นทางใต้ `/api/admin` คำขอจะไม่มาถึง FastAPI เลย
`/crawl-review` ตกลง `handle /api/*` เดิม → **ไม่ต้องแก้ Caddyfile**

### `require_admin` (ข้อกำหนดข้อ 9)

ใส่ที่ระดับ `APIRouter` ไม่ใช่ทีละเส้นทาง เส้นทางที่เพิ่มในอนาคตจึงถูกคลุมโดยไม่ต้องจำ
**นี่เป็นผู้ใช้รายแรกของ `require_admin`** ซึ่งเขียนไว้ใน `deps.py:50` มานานแล้วแต่ยังไม่มี
route ไหนเรียกใช้

### `decided_by` (ข้อกำหนดข้อ 10)

มาจาก `admin.email` ของ `User` ที่ `require_admin` คืนมา ซึ่งได้มาจากการถอด JWT แล้ว
query `users` ฝั่งเซิร์ฟเวอร์ **ไม่มี field `decided_by` ใน pydantic schema เลย**
ส่งมาใน body ก็ถูก `extra` ของ pydantic ทิ้ง (มีข้อทดสอบยิง `decided_by` ปลอมมาแล้ว
ยืนยันว่าแถวที่บันทึกยังเป็นอีเมลของเจ้าของ token)

### ไม่ expose `staging_path` (ข้อกำหนดข้อ 11)

`v_crawl_queue` ไม่มีคอลัมน์นั้น และ pydantic schema ก็ไม่มี field นั้น
ข้อทดสอบตรวจ response ทั้งก้อนว่าไม่มีสตริง `staging_path`, `/tmp`, path ของ staging จริง,
`last_error`, `http_etag` — ทั้งใน `/pending`, `/{id}` และใน 404 ของ `/pdf` ทุกเคส

### PDF endpoint (ข้อกำหนดข้อ 12)

[`backend/app/services/staging_store.py`](backend/app/services/staging_store.py) · 125 บรรทัด
คัดกติกาจาก `document_store.py` มาทั้งชุด ผู้ใช้ส่งมาได้เพียง UUID

```
1. อ่าน staging_path จากฐานข้อมูล (ไม่ใช่จาก request)
2. Path(...).resolve() แล้วต้อง is_relative_to(CRAWL_STAGING_DIR)   ← กัน ../ และ symlink
3. ต้องเป็นไฟล์จริง
4. sha256_of(ไฟล์) ต้องตรงกับ file_sha256 ในฐานข้อมูล
5. ห้าไบต์แรกต้องเป็น b"%PDF-"
ผิดข้อใด → None → route ตอบ 404 ข้อความเดียวกันทุกกรณี
```

`CRAWL_STAGING_DIR` ค่าว่าง = ปิดการเปิดดูไฟล์ (คิวและการอนุมัติยังทำงาน) —
สวิตช์เดียวกับ `DOCUMENTS_DIR`

### Course mapping — Phase 3 v1 ไม่สร้างหลักสูตรใหม่

| กรณี | ผล |
|---|---|
| `course_code` มีอยู่ใน `public.courses` | อนุมัติได้ · เก็บ `course_title` **จากฐานข้อมูล** ไม่ใช่จาก client |
| `course_code` ไม่มีในระบบ | **422** พร้อมข้อความบอกว่าต้องเลือกจากที่มีอยู่ |
| ไม่ส่ง `course_code` มาเลย | **422** จาก pydantic (เป็น required field) |
| `match_confidence` เป็น `ambiguous`/`unknown` | เหมือนกัน — ต้องส่ง `course_code` ทุกกรณีจึงอนุมัติได้ |

**ไม่เรียก `get_or_create_course()` ไม่มีที่ใดในโค้ดนี้ INSERT ลง `courses`**
และ role `advisor_api` ก็ไม่มีสิทธิ์ INSERT อยู่แล้ว — ห้ามสองชั้น

### Optimistic locking ด้วย `file_sha256` (ข้อกำหนดข้อ 7)

client ต้องส่ง `file_sha256` ที่เห็นบนหน้าจอมาด้วยทุกคำขอที่ตัดสินใจ
ถ้าไม่ตรงกับค่าปัจจุบันในฐานข้อมูล → **409** "ไฟล์เปลี่ยนไปแล้วหลังจากที่คุณเปิดดู"
กันกรณี crawler โหลดไฟล์ใหม่ทับระหว่างที่คนกำลังพลิกดูอยู่ แล้วคนไปกดอนุมัติไฟล์ที่ตัวเอง
ไม่ได้เห็น

### รหัสสถานะที่ตั้งใจให้เป็นแบบนี้

| สถานการณ์ | รหัส | เหตุผล |
|---|---|---|
| ไม่มี token / token ปลอม / บัญชีถูกปิด | 401 | |
| `is_admin = false` | 403 | |
| ไม่มีแถวนี้ หรือมีแต่ไม่อยู่ในคิวและไม่มีการตัดสินใจ | 404 | |
| **มีการตัดสินใจที่ยังใช้อยู่แล้ว** | **409** | ดู "ปัญหาที่พบและแก้" ข้อ 1 |
| `file_sha256` ล้าสมัย | 409 | |
| ไม่มีไฟล์รออนุมัติ / ยังไม่มี `sha` | 409 | |
| `course_code` ไม่มีในระบบ | 422 | |
| body ผิดรูปแบบ (`sha` ไม่ใช่ 64 hex, ไม่ใส่ `reason`) | 422 | |
| ถอนหลังนำเข้าแล้ว | 409 | การถอนไม่ย้อนคลังความรู้ จึงต้องไม่ยอมให้เข้าใจผิด |

---

## 3. Permissions

### ข้อกำหนด vs ที่ทำได้จริง

| ต้องได้ | ผล | พิสูจน์ด้วย |
|---|---|---|
| อ่าน review queue | ✅ | `role: อ่านคิวได้` |
| เพิ่ม decision | ✅ | `approve`/`ignore` คืน 201 |
| supersede/undo | ✅ | `undo` คืน 200 |
| **ห้ามเขียน `course_documents`** | ✅ ถูกปฏิเสธที่ฐานข้อมูล | `role: เขียน course_documents ไม่ได้` |
| **ห้ามเขียน `course_chunks`** | ✅ | `role: เขียน course_chunks ไม่ได้` |
| **ห้ามทำ ingestion** | ✅ ไม่มีโค้ดเรียก และไม่มีสิทธิ์เขียนคลัง | ทั้งสองข้อข้างบน |
| ห้ามเพิ่ม `courses` | ✅ | `role: เพิ่ม courses ไม่ได้` |
| ห้ามเขียน `crawl_sources` | ✅ | `role: เขียน mko.crawl_sources ไม่ได้` |
| ห้ามแก้เนื้อการตัดสินใจเดิม | ✅ column-level UPDATE | `role: แก้เนื้อการตัดสินใจไม่ได้` |
| ห้ามแตะผลการนำเข้า | ✅ | `role: แก้ผลการนำเข้าไม่ได้` |
| ห้ามลบการตัดสินใจ | ✅ | `role: ลบการตัดสินใจไม่ได้` |
| ห้ามอ่านคอลัมน์ที่ไม่ได้ให้สิทธิ์ | ✅ | `role: อ่านคอลัมน์ที่ไม่ได้ให้สิทธิ์ไม่ได้` (`SELECT last_error` ถูกปฏิเสธ) |

ทั้ง 9 ข้อทดสอบด้วยการ**ต่อฐานข้อมูลด้วย role นั้นจริงแล้วยิงคำสั่งที่ควรถูกปฏิเสธ**
และยืนยันว่าถูกปฏิเสธด้วย `InsufficientPrivilege` ไม่ใช่ด้วยเหตุอื่น

> **หมายเหตุเรื่องความสมจริงของการทดสอบ**: ฐานข้อมูลทดสอบใช้ role ชื่อ `crawl_test_api`
> ที่ให้สิทธิ์ลอกมาจาก `db/20-roles.sh` และ `004_crawl_decisions.sql` **ทีละบรรทัด**
> ไม่ได้ใช้ `advisor_api` ตัวจริงเพราะไม่มีรหัสผ่านของมัน และเลือกไม่ใช้วิธี
> `GRANT advisor_api TO ...` เพราะการเป็นสมาชิกของ role มีผลข้ามฐานข้อมูล
> จะทำให้มี role ที่อ่าน `course_advisor` ได้ในช่วงที่ทดสอบ ซึ่งไม่คุ้มความเสี่ยง

---

## 4. ไฟล์ที่เพิ่ม / แก้

### เพิ่มใหม่ 6 ไฟล์

```
db/migrations/004_crawl_decisions.sql           153 บรรทัด
backend/app/schemas/crawl_review.py              92
backend/app/services/staging_store.py           125
backend/app/services/crawl_review.py            242
backend/app/api/routes/crawl_review.py          153
eval/crawl_approval_check.py                    535
```

### แก้ของเดิม 2 ไฟล์ · +10 −1 บรรทัด

```diff
backend/app/core/config.py   (+6 −0)
+    # --- ไฟล์ที่ crawler โหลดมารออนุมัติ (ดู services/staging_store.py) ---
+    crawl_staging_dir: str = Field("", alias="CRAWL_STAGING_DIR")

backend/app/main.py          (+4 −1)
-from app.api.routes import auth, chat, compare, courses, documents, match, recommend, search, users, web_compat
+from app.api.routes import (auth, chat, compare, courses, crawl_review, documents, match,
+                            recommend, search, users, web_compat)
+app.include_router(crawl_review.router)
```

### ที่ **ไม่** แก้

`pipeline/` ทั้งโฟลเดอร์ (รวม `crawl/state.py` และ `ingest.py`) · `db/migrations/001–003` ·
`db/schema.sql` · `db/20-roles.sh` · `Caddyfile` · `docker-compose*` · `webapi/` ·
`frontend/` · `deps.py` · `document_store.py` · RAG / Gemini / embedding

---

## 5. Tests — 84/84 ผ่าน

[`eval/crawl_approval_check.py`](eval/crawl_approval_check.py) · 535 บรรทัด

```bash
python eval/crawl_approval_check.py \
  --database-url postgresql://<owner>@HOST:PORT/crawl_test \
  --api-url      postgresql://<api-role>@HOST:PORT/crawl_test
```

รันกับ PostgreSQL 16.15 จริงที่ลง bootstrap + migration 003 + 004 บนฐานข้อมูล
**`crawl_test` แยกคนละฐาน** (มีด่านปฏิเสธถ้า URL มีคำว่า `course_advisor`)
API ทดสอบผ่าน `TestClient` ที่ `include_router` **ตัวจริง** — auth, `require_admin`, JWT
และ session ฐานข้อมูลเป็นของจริงทั้งหมด ไม่ได้ import `app.main` ทั้งก้อนเพราะ lifespan
จะเปิดงาน warmup ที่ยิงหา Ollama

| หมวด | ข้อ | ผล |
|---|---|---|
| [1] การยืนยันตัวตนและสิทธิ์ | 6 | ผ่าน |
| [2] คิวรอตรวจ | 13 | ผ่าน |
| [3] เปิดดู PDF | 17 | ผ่าน |
| [4] อนุมัติ | 18 | ผ่าน |
| [5] ไม่เกี่ยวข้อง (ignore) | 6 | ผ่าน |
| [6] ถอนการตัดสินใจ | 6 | ผ่าน |
| [7] ข้อบังคับของฐานข้อมูล | 9 | ผ่าน |
| [8] สิทธิ์ของ role ที่ backend ใช้ | 9 | ผ่าน |
| **รวม** | **84** | **ผ่านทั้งหมด · ข้าม 0** |

### รายการที่สั่งให้ครอบ — ครอบครบทุกข้อ

| ที่สั่ง | ข้อทดสอบ |
|---|---|
| unauthenticated | `ไม่ส่ง token: 401` · `token ปลอม: 401` |
| non-admin | `ผู้ใช้ทั่วไป (is_admin=false): 403` · `ผู้ใช้ทั่วไปกดอนุมัติ: 403` · `ผู้ใช้ทั่วไปเปิด PDF: 403` |
| admin | `ผู้ดูแล: 200` |
| pending queue | `คิวมีครบ 9 รายการ` · ตัวนับ `with_staged_file` / `ambiguous` · `ส่งตัวเลือกหลักสูตรของรายการกำกวมมาให้` |
| approve | `หลักสูตรที่มีอยู่จริง: 201` + ตรวจ `decision`, `decided_by`, `course_title`, `document_id` |
| ignore | `ignore รายการที่ไม่มีไฟล์: 201` · `ignore ไม่ต้องมีหลักสูตร` · `ignore แล้วหายจากคิว` |
| undo ก่อน ingest | `ถอนก่อนนำเข้า: 200` · `ถอนแล้วกลับเข้าคิว` · `ถอนแล้วอนุมัติใหม่ได้: 201` · `ถอนหลังนำเข้าแล้ว: 409` |
| duplicate approval | `อนุมัติซ้ำ: 409` · `ignore ซ้ำ: 409` · `ถอนซ้ำ: 404` |
| stale SHA → 409 | `sha ล้าสมัย: 409` (และ `sha ผิดรูปแบบ: 422`) |
| ambiguous ไม่เลือก course → reject | `รายการกำกวมไม่เลือกหลักสูตร: 422` · `ไม่ส่ง course_code: 422` |
| existing course → approve | `หลักสูตรที่มีอยู่จริง: 201` |
| nonexistent course → reject | `หลักสูตรที่ไม่มีในระบบ: 422` |
| path traversal | `path traversal (..): 404` + ไม่รั่วที่อยู่ไฟล์ |
| symlink escape | `junction ของโฟลเดอร์ ชี้ออกนอก staging: 404` + `ไม่ส่งเนื้อไฟล์ข้างนอกออกไป` |
| staging file missing | `ไฟล์หายจาก staging: 404` |
| SHA mismatch | `sha256 ไม่ตรง: 404` |
| non-PDF | `ไม่ใช่ PDF: 404` |
| API ไม่ leak `staging_path` | ตรวจ 5 สตริงใน `/pending`, `/{id}` และใน 404 ของ `/pdf` ทุกเคส |
| backend role ไม่มีสิทธิ์เขียน knowledge tables | หมวด [8] ทั้ง 9 ข้อ |

> **เรื่อง symlink บน Windows**: `os.symlink` ต้องมีสิทธิ์พิเศษบนเครื่องนี้จึงสร้างไม่ได้
> เทสต์จึงถอยไปใช้ **junction ของโฟลเดอร์** (`mklink /J`) ซึ่งสร้างได้โดยไม่ต้องมีสิทธิ์
> และ `Path.resolve()` คลายมันเหมือนกัน จึงพิสูจน์เรื่องเดียวกันคือ "ทางที่ชี้ออกนอก
> โฟลเดอร์ต้องถูกปฏิเสธ" ผลคือข้อนี้ **ไม่ถูกข้าม**

### ข้อบังคับของฐานข้อมูลที่ทดสอบจริง

CHECK ทั้ง 6 ข้อ (คำตัดสินที่ไม่รู้จัก · sha ผิดรูปแบบ · approve ไม่มีหลักสูตร ·
ถอนไม่ระบุคนถอน · ignore มีผลนำเข้า · ไม่มีชื่อผู้ตัดสิน) และ partial unique index 2 แบบ

| แบบ | พิสูจน์อะไร |
|---|---|
| A | แถวแรก commit แล้ว แถวที่สองได้ `UniqueViolation` ทันที |
| B | แถวแรกยังไม่ commit แถวที่สอง (ตั้ง `lock_timeout`) **ต้องไม่ผ่าน** — รอหรือชน constraint |

แบบ B จำเป็นเพราะเป็นสถานการณ์ "สองคนกดพร้อมกัน" จริง และต้องตั้ง `lock_timeout`
ไม่งั้นการทดสอบจะค้าง (ดู "ปัญหาที่พบและแก้" ข้อ 3)

### Regression — ไม่มีอะไรถอยหลัง

| ชุด | ผล |
|---|---|
| `eval/crawl_state_check.py` (Phase 2, ฐานข้อมูลเดียวกันที่มี 004 อยู่แล้ว) | **32/32 ผ่าน** |
| `eval/crawl_download_check.py` | **140/140 ผ่าน** |
| `eval/tuition_followup_check.py` | **14/14 OK** |
| `eval/recommendation_clarification_check.py` | **15/15 OK** |
| OpenAPI ของแอปจริง | 6 เส้นทางใหม่ครบ · 27 เส้นทางรวม · เส้นทางเดิมอยู่ครบ |

**รวมทั้งหมด 285 ข้อ ผ่านทั้งหมด**

### เก็บของหลังทดสอบ

`DROP DATABASE crawl_test` · `DROP ROLE crawl_test_owner, crawl_test_api` · ปิดอุโมงค์ SSH

ยืนยันว่า production ไม่ถูกแตะ

```
ฐานข้อมูล:        postgres, course_advisor
role ที่ login ได้: advisor_api, advisor_ingest, postgres
migration:        001, 002, 003 เท่านั้น — ไม่มี 004
mko:              19 ตาราง / 7 วิว (เท่าเดิม)
crawl_decisions:  ไม่มีใน production
v_crawl_queue:    ไม่มีใน production
คลังความรู้:       courses 24 / course_documents 31 / course_chunks 9,039
```

---

## 6. ปัญหาที่พบระหว่างทำและแก้ไปแล้ว

ทั้งสามข้อนี้เจอจากการรันเทสต์ ไม่ได้เจอจากการอ่านโค้ด

### 1. อนุมัติซ้ำได้ 404 แทน 409

`approve()` เรียก `get_pending()` ก่อน ซึ่งอ่านจาก `v_crawl_queue` — หลังอนุมัติครั้งแรก
แถวหลุดจากคิวแล้ว จึงได้ 404 "ไม่พบรายการ" ซึ่งทำให้เข้าใจว่าข้อมูลหายไป
ทั้งที่แบบระบุว่าต้องเป็น 409

**แก้** เพิ่ม `_for_decision()` ที่เมื่อไม่พบในคิวจะแยกแยะต่อว่าเป็นเพราะ
ไม่มีแถวนี้ (404) หรือมีการตัดสินใจที่ยังใช้อยู่ (409) ไม่รั่วข้อมูลเพิ่มเพราะทุกเส้นทาง
ผ่าน `require_admin` มาแล้ว

### 2. `rate_limiter` ทำให้ผู้ดูแลโดน 429 กลางงาน

เดิมใส่ `rate_limiter` คลุมทั้ง router ตามที่แบบเสนอ แต่เพดานคือ 30 คำขอต่อนาทีต่อบัญชี
ซึ่ง**ไม่พอสำหรับการอ่าน** — เปิดหน้าคิวหนึ่งครั้งแล้วไล่เปิด PDF ดูทีละเล่มใช้เกิน
สามสิบคำขอได้ง่าย ๆ เทสต์โดน 429 จริงในหมวด [6] ซึ่งเป็นสัญญาณว่าหน้าเว็บจริงก็จะโดน

**แก้** ย้ายตัวจำกัดไปคลุมเฉพาะสามเส้นทางที่ตัดสินใจ (POST) เพราะคนตรวจกดไม่กี่ครั้งต่อรอบ
เส้นทางที่อ่านยังกัน abuse ด้วย `require_admin` อยู่แล้ว ผู้ใช้ทั่วไปเข้าไม่ถึงเลย

### 3. เทสต์ concurrency ของตัวเองค้าง

เทสต์ partial unique index เดิมสั่ง INSERT จากสอง connection โดยยังไม่ commit ตัวแรก
ตัวที่สองจึงรอ lock ไปตลอด — **นั่นคือพฤติกรรมที่ถูกต้องของฐานข้อมูล** แต่ทำให้เทสต์แขวน

**แก้** แยกเป็นสองแบบ A/B ตามที่อธิบายในหัวข้อ 5 และตั้ง `lock_timeout` ในแบบ B

### บั๊กของเทสต์เองอีก 3 ข้อ (ไม่ใช่ปัญหาของโค้ด)

จำนวนรายการกำกวมที่คาดไว้ผิด (3 → 2) · นับสิทธิ์ DELETE ของทุก role รวม role
ที่เตรียมข้อมูลในเทสต์ซึ่งเป็นเจ้าของฐานข้อมูลทดสอบ · ส่ง header ที่ไม่ใช่ ASCII

---

## 7. Known limitations

| ข้อจำกัด | ผล | จะแก้เมื่อไหร่ |
|---|---|---|
| **แถวที่ `file_sha256 IS NULL` ตัดสินใจไม่ได้เลย** — `crawl_decisions.file_sha256` เป็น NOT NULL ตามข้อกำหนดข้อ 4 แถว `status='error'` ที่โหลดไฟล์ไม่สำเร็จเลยจึงค้างในคิวจนกว่าจะ crawl ได้ไฟล์ | แถว error ที่ดึงไม่ได้ถาวรจะอยู่ในคิวเรื่อย ๆ | 3B — ทางเลือกคือ unique index บน `coalesce(file_sha256,'-')` เพื่อให้ `ignore` ได้ |
| **ไม่มีเส้นทางดูรายการที่ตัดสินใจแล้ว** — `GET /{id}` ตอบ 404 หลังตัดสินใจ | ดูประวัติจาก API ไม่ได้ ต้อง query ฐานข้อมูล | 3B/UI |
| **undo ไม่ย้อนคลังความรู้** — ถอนหลัง ingest ถูกปฏิเสธ (409) การเอาเอกสารออกต้องใช้ superuser | การอนุมัติเป็นการตัดสินใจที่ย้อนยาก จึงต้องให้คนเปิด PDF ดูก่อนเสมอ | เป็นข้อจำกัดที่ยอมรับ ไม่ใช่บั๊ก |
| **`rate_limiter` นับแยกต่อโปรเซส** (ตามที่ `deps.py` เขียนไว้) | ถ้ามีหลาย worker เพดานจริงจะสูงกว่าที่ตั้ง | เมื่อย้ายไป Redis-backed limiter |
| **`match_candidates` เป็นชื่อหลักสูตร ไม่ใช่ `course_code`** | UI ต้องแปลงชื่อเป็นรหัสเองก่อนส่ง approve | 3B — เพิ่มเส้นทางค้นหาหลักสูตร หรือให้ crawler เก็บรหัสด้วย |
| **ยังไม่มี UI** | ทดลองได้ผ่าน HTTP client เท่านั้น | 3B |
| **004 ยังไม่ได้ลง production** | ฟีเจอร์ยังใช้จริงไม่ได้ | รออนุมัติ deploy |
| **ยังไม่มีบัญชี admin ใน production** | ต้อง `UPDATE users SET is_admin = true` หนึ่งบัญชี ซึ่งเป็นการแก้ข้อมูล production ต้องขออนุมัติแยก | ก่อน deploy |
| **`staging` ยังไม่ได้ย้ายขึ้นเซิร์ฟเวอร์** | `CRAWL_STAGING_DIR` ยังตั้งไม่ได้ เปิดดู PDF จากหน้าเว็บยังไม่ได้ | ตอน deploy (ต้อง mount `:ro` เข้า backend) |

---

## 8. Phase 3B — สิ่งที่จะทำต่อ

| # | งาน | หมายเหตุ |
|---|---|---|
| 1 | `pipeline/crawl/approve.py` — ingest-worker | หา decision ที่ `approve` และ `ingest_finished_at IS NULL` ด้วย `FOR UPDATE SKIP LOCKED` · ตรวจไฟล์ซ้ำ (root · sha256 · `%PDF-` · `fitz.open()`) · เรียก `pipeline.ingest.run()` **ตัวเดิม ไม่แก้** |
| 2 | อัปเดตสถานะหลังนำเข้า | `crawl_sources.status='ingested'` + `document_id` (ด้วย role `advisor_ingest`) และ `crawl_decisions.ingest_*` |
| 3 | หา `document_id` หลัง `run()` | `run()` คืน `None` ต้อง `SELECT id FROM course_documents WHERE file_sha256 = %s AND extraction_status='done'` |
| 4 | จัดการ `EMBED_MODEL` / `EMBED_DIM` | ค่าเริ่มต้นของ `ingest.py` คือ `nomic-embed-text` (768) แต่ production ใช้ `bge-m3` (1024) ต้องตรวจก่อนเริ่ม embed ไม่งั้นเสียเวลาเป็นชั่วโมงฟรี |
| 5 | คัดลอกไฟล์เข้า `documents/` หลังนำเข้าสำเร็จ | ไม่งั้น `/documents/{id}/pdf` เปิดไม่ได้ · และต้อง restart backend เพราะ `document_store` ทำดัชนีครั้งเดียวต่อโปรเซส |
| 6 | `ingest-worker` container ใน compose (`profiles: ["ingest"]`) | ตามที่เสนอไว้ในแบบ — รันครั้งเดียวแล้วจบ ไม่ใช่บริการรันค้าง |
| 7 | Admin UI `frontend/app/crawl-review/` | บังคับเลือกหลักสูตรเมื่อ `ambiguous`/`unknown` · เปิด PDF ในแท็บใหม่ |
| 8 | เส้นทางค้นหาหลักสูตรสำหรับ UI | แก้ข้อจำกัดเรื่อง `match_candidates` เป็นชื่อไม่ใช่รหัส |
| 9 | เทสต์ของ worker | ไฟล์หาย · sha ไม่ตรง · ไม่ใช่ PDF · `run()` พัง · รันซ้ำ · สองตัวพร้อมกัน |

---

## 9. สถานะปัจจุบัน

| | |
|---|---|
| ไฟล์ | เพิ่ม 6 · แก้ 2 (+10 −1) · **ยังไม่ commit** |
| `mko-phase2` | ยังเป็น `a0655ef` ตรงกับ `origin/mko-phase2` |
| `main` | `b78b3f8` ไม่ถูกแตะ |
| production | ไม่มี migration ใหม่ ไม่ deploy ไม่ restart คลังความรู้เท่าเดิม |
| ingestion | **ไม่มีเลย** ไม่มีโค้ดใดเรียก `pipeline.ingest` ในรอบนี้ |

**หยุดรอการตรวจรายงานนี้ ก่อน commit / push / deploy**
