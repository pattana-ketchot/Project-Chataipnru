# Phase 3D Step 3.5 — Admin Setup & Authenticated UI Verification

**NO INGESTION · ไม่เริ่ม Step 4**

| | |
|---|---|
| ผลรวม | **BLOCKED — ไม่ได้ promote เพราะไม่มีบัญชีที่ตรงกับอีเมลที่อนุมัติ** |
| เหตุที่หยุด | ค้นหา `Tester@gmail.com` ใน `public.users` ได้ **0 บัญชี** · §2 ของคำสั่งระบุว่า zero match ต้อง **STOP ไม่สร้างและไม่ promote** |
| Production mutation ในรอบนี้ | **ไม่มีเลย** — ทุกการดำเนินการเป็นการอ่าน |
| วันที่ | 2026-09-29 · ช่วงทำงาน **03:11:34Z – 03:14Z** (ไทย 10:11–10:14) |
| Repository | `D:/workspace/course-advisor-system-mko2` · branch `mko-phase2` |
| DEPLOY_REV | `2fdc6f241fc1742047b572ee2ef354cd811f9401` |
| Production | `ubuntu@161.118.237.37` · compose project `course-advisor-system` · db `course_advisor` |

---

## 1. รายงานต้นทาง · ช่วงเวลา · baseline เทียบ expected/observed

### 1.1 รายงานที่ใช้เป็นฐาน

สภาพแวดล้อมนี้เป็น Windows และ **ไม่มี path `/mnt/data/`** จึงใช้สำเนาในโปรเจกต์
ซึ่งเป็นไฟล์เดียวกับที่ส่งมอบเมื่อจบ Step 3 (resume) — **ไม่ได้ใช้รายงาน Step 3 ฉบับที่ไม่ใช่ resume**

```
docs/AUTOMATED_INGESTION_PHASE3D_STEP3_RESUME_REPORT.md
  950 บรรทัด · 70,905 ไบต์
  sha256 2039ba5f29cf389f1866f94662250ff767d06137dda05254d5f5cf3778243348
```

อ่านครบทั้งฉบับก่อนเริ่มงาน และถือค่าทุกค่าในนั้นเป็น **หลักฐานย้อนหลังที่ต้องตรวจซ้ำ**
ไม่ใช่ผลสังเกตสด

### 1.2 Repository — expected vs observed

| ข้อตรวจ | Expected | Observed | ผล |
|---|---|---|---|
| branch | `mko-phase2` | `mko-phase2` | PASS |
| local HEAD | `2fdc6f24…9401` | `2fdc6f241fc1742047b572ee2ef354cd811f9401` | PASS |
| live `refs/heads/mko-phase2` | DEPLOY_REV | `2fdc6f241fc1742047b572ee2ef354cd811f9401` | PASS |
| live `refs/heads/main` | `b78b3f8bf895685874d9a52c66b45569072f0514` | ตรงกัน ไม่เปลี่ยน | PASS |
| tracked modified / staged | 0 / 0 | 0 / 0 | PASS |
| untracked นอก `docs/` | 0 | 0 | PASS |
| untracked ใน `docs/` | 42 (ตามรายงาน) | **43** | อธิบายได้ |
| tag local / remote | 0 / 0 | 0 / 0 | PASS |

**คำอธิบายส่วนต่าง 42 → 43:** ตัวเลข 42 ในรายงาน Step 3 ถูกนับ **ก่อน** ที่ไฟล์รายงาน
`AUTOMATED_INGESTION_PHASE3D_STEP3_RESUME_REPORT.md` จะถูกเขียน ส่วนต่างหนึ่งไฟล์คือรายงานนั้นเอง
เป็นความต่างของไฟล์รายงานล้วน **ไม่มีความเปลี่ยนแปลงของโค้ด ref หรือ config**
ไม่ได้ reset / stash / clean / checkout / commit / push / merge / tag หรือซ่อม ref ใด

### 1.3 อิมเมจที่ deploy อยู่ — เทียบ image ID และ OCI label

| Component | Expected image ID | Observed | revision label | ผล |
|---|---|---|---|---|
| backend | `sha256:4a45677ec010fc076e283b1e556bd4c1b0b25bc66786b32ec6f64a76ad0cca46` | ตรงทุกตัวอักษร | `2fdc6f241fc1742047b572ee2ef354cd811f9401` | PASS |
| frontend | `sha256:591ab6d935bbbdf533ec3fc9e8a50b1378b59e9f849ab6d3303a91b638240eec` | ตรงทุกตัวอักษร | `2fdc6f241fc1742047b572ee2ef354cd811f9401` | PASS |

### 1.4 บริการทั้งหก — container ID / StartedAt / status / health / RestartCount

| Service | Container ID | Expected prefix | StartedAt | status / health | RestartCount |
|---|---|---|---|---|---:|
| backend | `fda31caa20c4` | `fda31caa20c4` | 2026-09-29T01:06:17.872Z | running / ไม่มี healthcheck | 0 |
| frontend | `2886c1bf9183` | `2886c1bf9183` | 2026-09-29T01:07:21.190Z | running / ไม่มี healthcheck | 0 |
| caddy | `a2957d7b8fc3` | `a2957d7b8fc3` | 2026-09-22T21:23:48.949Z | running / ไม่มี healthcheck | 0 |
| postgres | `e8c091a4fc60` | `e8c091a4fc60` | 2026-08-18T14:17:25.705Z | running / healthy | 0 |
| ollama | `e6ac0350c722` | `e6ac0350c722` | 2026-08-18T14:17:25.705Z | running / healthy | 0 |
| webapi | `6a73308d4f39` | `6a73308d4f39` | 2026-09-22T21:21:35.624Z | running / healthy | 0 |

**ไม่มีการแทนที่คอนเทนเนอร์และไม่มี restart** — เทียบทั้ง container ID และ StartedAt ไม่ใช่ดู
RestartCount อย่างเดียว ไม่พบ deployment drift

### 1.5 Migration และโครงสร้าง (ไม่ได้รัน migration ซ้ำ ไม่ได้แก้ grant)

| ข้อตรวจ | Expected | Observed | ผล |
|---|---|---|---|
| `mko.schema_migrations` | 001, 002, 003, 004 | `001_mko_structured,002_mko_review_publish,003_crawl_sources,004_crawl_decisions` | PASS |
| แถวของ `004_crawl_decisions` | 1 | 1 | PASS |
| `mko.crawl_decisions` คอลัมน์ | 15 | 15 | PASS |
| CHECK constraint | 7 | 7 | PASS |
| FOREIGN KEY | 2 | 2 | PASS |
| index | 4 | 4 | PASS |
| `mko.v_crawl_queue` คอลัมน์ | 19 | 19 | PASS |
| view มี `has_staged_file` | ต้องมี | 1 | PASS |
| view เปิด `staging_path` | **ต้องไม่มี** | 0 | PASS |

### 1.6 Aggregate ใน read-only transaction เดียว (`statement_timeout = 15s`)

| Invariant | Required | Observed | ผล |
|---|---:|---:|---|
| `public.courses` | 24 | 24 | PASS |
| `public.course_documents` | 31 | 31 | PASS |
| `public.course_chunks` | 9039 | 9039 | PASS |
| embedding dimension | 1024 | 1024 | PASS |
| `mko.crawl_sources` | 12 | 12 | PASS |
| status `unchanged` | 12 | 12 | PASS |
| `needs_review` | 6 | 6 | PASS |
| `staging_path` ไม่เป็น null | 0 | 0 | PASS |
| `mko.v_crawl_queue` แถว | 6 | 6 | PASS |
| `mko.crawl_decisions` | 0 | **0** | PASS |
| `public.users` / active | 197 / 197 | 197 / 197 | PASS |
| admins | 0 | **0** | PASS |
| `public.chat_messages` | 6640 | 6640 | PASS |
| `public.chat_answer_cache` | 160 | 160 | PASS |

### 1.7 Worker / crawler / staging / documents

- คอนเทนเนอร์ที่รัน: 6 บริการของโปรเจกต์ + `db-viewer` (อยู่นอก compose project นี้ ไม่ได้แตะ)
- คอนเทนเนอร์ชื่อ worker/ingest รวมที่หยุด: **0** · โปรเซสที่ชื่อมี `pipeline.crawl`: **0**
  → **worker คง PREPARED · candidate คง DEFERRED** ไม่ได้เปิด inspection container
  และไม่ได้โหลด worker compose overlay
- `staging/crawl`: **0 รายการ** · `CRAWL_STAGING_DIR=/srv/staging` · `DOCUMENTS_DIR=/srv/documents`
- mount ของ backend: `/srv/documents` **RW=false** และ `/srv/staging` **RW=false**
- เอกสารเทียบ `documents_manifest_20260928T060342Z.tsv`: **32/32 ตรง size และ hash ·
  ไม่ตรง 0 · ขาด 0 · เกิน 0 · `.pdf` 30 ไฟล์ · ไฟล์ทั้งหมดในดิสก์ 32**
  (32 ไฟล์บนดิสก์ **ไม่ใช่** 31 แถวใน `course_documents` — ส่วนต่างคือ `MANIFEST.tsv`
  และ `ph_web.txt` ซึ่งไม่ใช่ PDF และไม่ใช่ระเบียนเอกสาร)
- **ไม่ได้เขียนไฟล์ probe ใด**

**§1 baseline gate: PASS ทุกข้อ** — ไม่มี mismatch ที่ต้องอธิบายนอกจากจำนวนไฟล์รายงานในข้อ 1.2

---

## 2. อีเมลที่เจ้าของอนุมัติ และผลการตรวจตัวตน

**อีเมลที่อนุมัติ: `Tester@gmail.com`** (อีเมลเดียวที่ได้รับอนุมัติ ไม่มีสิทธิ์เลือกบัญชีแทน
ไม่มีสิทธิ์สร้างบัญชี)

ตรวจด้วย **bound literal** และ **semantics จริงของแอป** (คอลัมน์เป็น `citext` ดูข้อ 3)
ทั้งหมดอยู่ใน read-only transaction

| ข้อตรวจ | ผลลัพธ์ |
|---|---:|
| จำนวนบัญชีที่ตรง (นับก่อนกรอง active) | **0** |
| จำนวนบัญชีที่ตรง และ `is_active = true` | 0 |
| จำนวนบัญชีที่ตรง และ `is_admin = true` อยู่แล้ว | 0 |

ตรวจความกำกวมเพิ่มอีกสามทาง เพื่อไม่ให้พลาดกรณีตัวพิมพ์หรือช่องว่าง

| ข้อตรวจเพิ่ม | ผลลัพธ์ |
|---|---:|
| `lower(email::text) = lower('Tester@gmail.com')` | **0** |
| `btrim(email::text) = btrim('Tester@gmail.com')` | **0** |
| `email::text ILIKE 'tester@%'` (local part `tester` ทุกโดเมน) | **0** |

**สรุป: ไม่มีบัญชีนี้อยู่ในระบบเลย** ทั้งแบบตรงตัว แบบไม่สนตัวพิมพ์ และแบบตัดช่องว่าง

### ข้อมูลรวมยอดที่ช่วยเจ้าของโปรเจกต์ตรวจสอบ (ไม่เปิดเผยอีเมลรายบุคคล)

| รายการ | จำนวน |
|---|---:|
| ผู้ใช้ทั้งหมด | 197 |
| โดเมน `example.com` | 188 |
| โดเมน `gmail.com` | **6** |
| โดเมน `awdaw.com` / `stpnru.local` / `gggg.com` | 1 / 1 / 1 |
| บัญชีที่ local part ขึ้นต้นด้วย `test` (ทุกโดเมน) | **2** |
| บัญชีที่ local part เป็น `tester` (ทุกโดเมน) | **0** |

มีบัญชีโดเมน gmail.com อยู่ 6 บัญชี และมีบัญชีที่ local part ขึ้นต้นด้วย `test` อยู่ 2 บัญชี
**แต่ไม่มีบัญชีใดที่ local part เป็น `tester`** ผมจึง**ไม่เลือกบัญชีใดแทน** และไม่เปิดเผยอีเมลใด
เจ้าของโปรเจกต์ต้องระบุอีเมลที่ถูกต้องของบัญชีที่มีอยู่จริง หรือสมัครบัญชีนั้นเองผ่านขั้นตอนปกติ
ของแอป (ไม่ใช่งานของผมและไม่ได้รับอนุมัติในรอบนี้)

**ไม่ได้อ่านคอลัมน์ `password_hash` และไม่ได้ดึงอีเมลหรือ PII ของผู้ใช้ใดออกมา**

---

## 3. Schema · email semantics · กลไก admin/auth ที่เป็นตัวตัดสิน

### 3.1 `public.users` ตามที่ deploy อยู่จริง

```
id            :: uuid NOT NULL              (PRIMARY KEY users_pkey)
email         :: citext NOT NULL            (UNIQUE users_email_key)
password_hash :: text NOT NULL              (ไม่อ่าน)
full_name     :: text
is_active     :: boolean NOT NULL
is_admin      :: boolean NOT NULL
created_at    :: timestamptz NOT NULL
updated_at    :: timestamptz NOT NULL
```

constraint: `users_pkey PRIMARY KEY (id)` · `users_email_key UNIQUE (email)`
index: `CREATE UNIQUE INDEX users_email_key ON public.users USING btree (email)`
extension ที่ติดตั้ง: `citext`, `pgcrypto`, `plpgsql`, `vector`
rule: ไม่มี · row level security: `relrowsecurity=false relforcerowsecurity=false` · policy: ไม่มี
owner: `postgres` · grant: `advisor_api` มี SELECT, INSERT, UPDATE ระดับตาราง

**trigger เดียว:** `trg_users_updated_at BEFORE UPDATE ON public.users FOR EACH ROW
EXECUTE FUNCTION set_updated_at()` ซึ่งนิยามคือ

```sql
CREATE OR REPLACE FUNCTION public.set_updated_at() RETURNS trigger LANGUAGE plpgsql AS $$
    NEW.updated_at = now();
    RETURN NEW;
END; $$
```

ตรวจแล้วว่า trigger แตะเฉพาะ `updated_at` **ไม่แตะ profile, email, password, is_active
หรือข้อมูลอื่นที่ห้ามเปลี่ยน** จึงไม่เป็นเหตุให้ต้อง STOP หากมีการ UPDATE จริง
(แต่รอบนี้ไม่มีการ UPDATE เกิดขึ้นเลย)

ตารางที่อ้าง `users` ด้วย FK: `chat_sessions`, `course_documents`, `recommendations`,
`user_profiles`, `user_requirements` — การเปลี่ยน `is_admin` ไม่กระทบ FK ใด

### 3.2 Email semantics — **แก้ข้อสรุปที่ผมเคยพูดผิดกลางงาน**

ORM ประกาศ `email: Mapped[str] = mapped_column(String, unique=True, nullable=False)`
ที่ [backend/app/models/user.py:15](backend/app/models/user.py:15) ซึ่ง**ทำให้เข้าใจผิดได้ว่าเป็น
การเทียบแบบสนตัวพิมพ์** แต่คอลัมน์จริงในฐานข้อมูลเป็น **`citext`**

พิสูจน์ในฐานข้อมูลโดยไม่แตะข้อมูล

```
'Tester@gmail.com'::citext = 'TESTER@GMAIL.COM'::citext  ->  true
'Tester@gmail.com'::text   = 'TESTER@GMAIL.COM'::text    ->  false
```

ดังนั้น semantics จริงของแอปคือ **เทียบไม่สนตัวพิมพ์ที่ระดับฐานข้อมูลผ่าน citext**
ไม่ใช่เพราะโค้ดทำ lowercase หรือใช้ `ILIKE` (โค้ดไม่ได้ทำทั้งสองอย่าง)
และเพราะ unique index อยู่บนคอลัมน์ citext **จึงมีได้มากสุดหนึ่งแถวต่อหนึ่งอีเมล
แบบไม่สนตัวพิมพ์** การตรวจในข้อ 2 จึงใช้ `email = 'Tester@gmail.com'` ตรงตาม semantics นี้
ไม่ได้เพิ่ม lowercasing, `ILIKE` หรือ trimming ที่แอปไม่ได้ทำ

ผมเคยสรุปกลางงานว่าการเทียบเป็น "แบบตรงตัว สนตัวพิมพ์" จากการอ่าน ORM เพียงอย่างเดียว —
**ข้อสรุปนั้นผิด** และแก้ไว้ที่นี่ ผลของการค้นหาไม่เปลี่ยน (0 บัญชีทั้งสองแบบ)

### 3.3 `is_admin` เป็นธงสิทธิ์ที่ crawl-review ใช้จริง

| หลักฐาน | ที่มา |
|---|---|
| router ของ `/crawl-review` บังคับ admin ที่ระดับ router ทุกเส้นทาง | [backend/app/api/routes/crawl_review.py:50-53](backend/app/api/routes/crawl_review.py:50) — `APIRouter(prefix="/crawl-review", dependencies=[Depends(require_admin)])` |
| `require_admin` อ่าน `user.is_admin` ตรง ๆ | [backend/app/api/deps.py:50-53](backend/app/api/deps.py:50) — `if not user.is_admin: raise HTTPException(403, "admin only")` |
| ผู้ใช้ปัจจุบันถูก **โหลดใหม่จากฐานข้อมูลทุกคำขอ** | [backend/app/api/deps.py:44](backend/app/api/deps.py:44) — `user = db.get(User, uuid.UUID(payload["sub"]))` |
| token มีเพียง `sub` และ `type` ไม่มี role claim | [backend/app/api/deps.py:35-42](backend/app/api/deps.py:35) — ตรวจ `payload.get("type") != "access"` เท่านั้น |
| login เทียบอีเมลกับตาราง `users` และต้อง `is_active` | [backend/app/api/routes/auth.py:50-57](backend/app/api/routes/auth.py:50) |

ตรวจแล้วว่า **ไม่มี role store อื่นในฐานข้อมูลนี้**: ตารางที่ชื่อเกี่ยวกับ user/role/auth
มีเพียง `public.users`, `public.user_profiles`, `public.user_requirements` ·
คอลัมน์ที่ชื่อเหมือนเก็บสิทธิ์มี `public.users.is_admin` เป็นตัวเดียวที่เป็นสิทธิ์จริง
(`public.chat_messages.role` คือบทบาทของข้อความ user/assistant และ
`public.user_profiles.current_role` คือข้อมูลอาชีพของผู้ใช้ ไม่ใช่สิทธิ์)
คอลัมน์ที่ชื่อเกี่ยวกับอีเมลมีเพียง `public.users.email`

→ **`public.users.is_admin` เป็นตัวตัดสินเพียงตัวเดียว** และไม่มี semantics ที่ขัดกัน
ไม่ได้แก้ role table, Supabase, trigger หรือโค้ดแอปใด

### 3.4 `/users/me` — ไม่มีฟิลด์ `is_admin`

[backend/app/schemas/user.py:13-18](backend/app/schemas/user.py:13) กำหนด `UserOut` เป็น
`id`, `email`, `full_name`, `created_at` เท่านั้น
และ [backend/app/api/routes/users.py:18-20](backend/app/api/routes/users.py:18) คืน `UserOut`

→ **`/users/me` ไม่สามารถใช้ยืนยันสถานะ admin ได้** จะไม่อ้างว่ามีฟิลด์นี้
หลักฐานเรื่อง authorization ต้องมาจากการที่ admin-only route ตอบสำเร็จ

### 3.5 login ไม่มี side effect ที่เขียนข้อมูล

[auth.py:48-62](backend/app/api/routes/auth.py:48) ทำเพียง SELECT, verify hash
(เทียบ dummy hash เสมอเมื่อไม่พบผู้ใช้ เพื่อลด timing signal) แล้วออก token
**ไม่มี `db.add` / `db.commit`** ในเส้นทาง login (`db.refresh` ที่บรรทัด 44 อยู่ในเส้นทาง register)

---

## 4. การเปลี่ยนข้อมูล — **ไม่ได้ดำเนินการ**

**สถานะ: BLOCKED ที่ §2 gate** — ไม่ได้เปิด transaction ไม่ได้ lock ตาราง
ไม่ได้รัน UPDATE และไม่ได้ COMMIT อะไรเลย

เหตุผล: §2 ของคำสั่งกำหนดให้ต้องพบ **หนึ่งบัญชีพอดี** ที่ `is_active = true` และ
`is_admin = false` · กรณี **zero match** สั่งให้ **STOP โดยไม่สร้างและไม่ promote อะไร**
ผลตรวจได้ 0 บัญชี จึงหยุดตามคำสั่ง

- affected rows: **ไม่มี (ไม่ได้รัน UPDATE)**
- transaction outcome: **ไม่มี transaction**
- ไม่ได้สร้าง helper function/table หรือ artifact ใดในฐานข้อมูล
- ไม่ได้สร้างบัญชี ไม่ได้เลือกบัญชีแทน ไม่ได้ promote บัญชีที่สอง

SQL ที่ **เตรียมไว้** สำหรับใช้เมื่อเจ้าของโปรเจกต์ระบุอีเมลของบัญชีที่มีอยู่จริง
อยู่ในข้อ 17 (โครงสร้างเดียวกับ rollback แต่กลับทิศ) — ยังไม่ถูกรัน

---

## 5. Aggregate ก่อน / หลัง และสถานะของเป้าหมาย

| รายการ | ก่อน | หลัง | เปลี่ยน |
|---|---:|---:|---|
| ผู้ใช้ทั้งหมด | 197 | 197 | ไม่เปลี่ยน |
| ผู้ใช้ที่ active | 197 | 197 | ไม่เปลี่ยน |
| admin | **0** | **0** | **ไม่เปลี่ยน** |

สถานะของบัญชีเป้าหมาย: **ไม่มีบัญชีเป้าหมาย** (0 match) จึงไม่มี boolean ใดให้รายงาน
ไม่มี internal ID ใดถูกเก็บหรือใช้ เพราะไม่มีแถวที่ตรง

---

## 6. การตัดสินใจเรื่อง restart

**ไม่จำเป็นต้อง restart และไม่ได้ restart**

หลักฐานจากโค้ดที่ deploy: [deps.py:44](backend/app/api/deps.py:44) ทำ
`db.get(User, uuid.UUID(payload["sub"]))` ทุกคำขอ และ JWT บรรจุเพียง `sub` กับ `type`
ไม่มี role claim และไม่มีชั้น cache ของสิทธิ์ → การเปลี่ยน `is_admin` ในฐานข้อมูล
**มีผลกับคำขอถัดไปทันที** โดยไม่ต้องรีสตาร์ตและไม่ต้อง login ใหม่ด้วยซ้ำ
(token เดิมยังใช้ได้เพราะสิทธิ์อ่านจากแถวผู้ใช้ ไม่ได้อ่านจาก token)

ไม่ได้ restart เพื่อ refresh `document_store` · ไม่ได้ restart เพื่อหา credential ·
ไม่ได้ restart เพื่อแก้ routing ของ UI · ไม่ได้ restart เพื่อให้ข้อตรวจที่ล้มเหลวผ่าน
ยืนยันด้วย container ID และ StartedAt ของทั้งหกบริการที่ไม่เปลี่ยน (ข้อ 12)

---

## 7. วิธีการยืนยันตัวตน (ไม่มี credential)

**HUMAN ACTION REQUIRED** ด้วยเหตุสองชั้นที่แยกกัน

1. **ไม่มีบัญชีที่อนุมัติอยู่ในระบบ** — ต้องแก้ก่อนเรื่องอื่น
2. **ไม่มี credential ของบัญชีใดที่ผมเข้าถึงได้อย่างปลอดภัย** — ไม่มีกลไก
   environment/credential store ที่เก็บรหัสผ่านของบัญชีผู้ใช้ไว้ให้ผมใช้

ไม่ได้ขอรหัสผ่าน · ไม่ได้อ่านหรือแสดง `password_hash` · ไม่ได้รีเซ็ตรหัสผ่าน ·
ไม่ได้สร้างบัญชี · ไม่ได้สร้างหรือเซ็น token · ไม่ได้ปลอม session · ไม่ได้ inject identity ·
ไม่ได้ข้าม login · ไม่ได้ลอง login ซ้ำ ๆ · ไม่ได้ใช้ flow กู้บัญชี
ไม่มี credential ใดปรากฏใน tool call, shell history, log หรือรายงานฉบับนี้

เจ้าของโปรเจกต์ใช้ credential ของตนเองผ่านขั้นตอนปกติของแอปได้เอง —
**ไม่ต้องส่งรหัสผ่านมาให้ผม**

---

## 8. ผลการยืนยันผ่าน API

### 8.1 Anonymous guard — **PASS** (ทำได้โดยไม่ต้องมี credential)

เรียกผ่าน origin HTTPS จริงที่อ่านจาก config ที่ deploy (`SITE_DOMAIN` ใน `.env`
สะท้อนที่ Caddy ใช้) · ตรวจ TLS ตามปกติ · ไม่ส่ง credential หรือ token ใด

| endpoint | HTTP | body | ผล |
|---|---:|---|---|
| `GET /api/crawl-review/pending` | **401** | `{"detail":"missing bearer token"}` | PASS |
| `GET /api/crawl-review/{uuid}` | **401** | `{"detail":"missing bearer token"}` | PASS |
| `GET /api/crawl-review/{uuid}/pdf` | **401** | `{"detail":"missing bearer token"}` | PASS |

ทั้งสามตอบ 401 ไม่ใช่ 404 → route มีจริงและบังคับ auth · **ไม่มีการเปิดเผยเนื้อคิว
รายการเอกสาร หรือ path ของไฟล์ใด ๆ ในคำตอบ**

### 8.2 `/users/me` — **NOT TESTED**

ต้องมี token จากการ login ปกติซึ่งทำไม่ได้ (ข้อ 7)
และแม้เรียกได้ก็ยืนยัน admin ไม่ได้เพราะ `UserOut` ไม่มีฟิลด์ `is_admin` (ข้อ 3.4)

### 8.3 Admin-only route ด้วยตัวตนที่ผ่านการยืนยัน — **HUMAN ACTION REQUIRED**

`GET /api/crawl-review/pending` ที่ควรคืน 6 รายการในคิว ยังทดสอบไม่ได้
ค่าที่คาดไว้อ้างจาก `mko.v_crawl_queue` = **6 แถว** ซึ่งยืนยันแล้วในชั้นฐานข้อมูล (ข้อ 1.6)

### 8.4 non-admin 403 — **NOT TESTED**

ไม่มี session ของผู้ใช้ non-admin ที่เข้าถึงได้อย่างปลอดภัย และ**ไม่สร้างบัญชีหรือ session ขึ้นเพื่อทดสอบ**

---

## 9. หน้า Next.js `/crawl-review`

### 9.1 ตรวจแบบ anonymous ผ่าน loopback ของเซิร์ฟเวอร์ — **PASS**

ก่อนเปิดหน้า ตรวจ effect ในโค้ดแล้วพบว่า `useEffect` เรียก `load(token)` ซึ่ง
**ไม่ยิง API เลยเมื่อไม่มี token** และปุ่ม approve/ignore/undo อยู่หลังกล่องยืนยัน
จึงเปิดหน้าได้โดยไม่เกิดการเปลี่ยนสภาพ

| ข้อตรวจ | ผล |
|---|---|
| `http://127.0.0.1/crawl-review` (loopback บนเซิร์ฟเวอร์) | **HTTP 200 · 7,356 ไบต์** |
| chunk เฉพาะ route ที่หน้าอ้าง | `/_next/static/chunks/app/crawl-review/page-a6096f0244f418a5.js` |
| sha256 ของหน้าเทียบหน้าแรก | `71b6a743…` ≠ `2e42d468…` → **route จริง ไม่ใช่ fallback** |

**ไม่ได้เปิด listener สาธารณะใหม่ ไม่ได้ส่ง credential ผ่าน HTTP** และไม่ได้สร้าง tunnel
ในรอบนี้เพราะการตรวจแบบ anonymous ทำได้จาก loopback ของเซิร์ฟเวอร์โดยตรง
(ไม่มีอะไรต้องปิดหลังทำเสร็จ)

### 9.2 คิวและรายละเอียดแบบ authenticated — **HUMAN ACTION REQUIRED**

ยังไม่ได้เห็นคิวที่ render จริง, ยังไม่ได้เรียก `GET /crawl-review/{id}`,
ยังไม่ได้ตรวจว่า action control ปรากฏตามสภาพของรายการ
ทั้งหมดต้องมี admin ที่ login ได้

จากการอ่าน source: ปุ่ม `ถอนการตัดสินใจล่าสุด` แสดงตามเงื่อนไขของรายการ
(รายการที่ยังไม่มีการตัดสินใจไม่จำเป็นต้องมีปุ่มนี้) — บันทึกเป็นข้อสังเกตจาก source
แยกจากการสังเกตหน้าจอจริงซึ่งยังไม่มี

### 9.3 PDF preview ของรายการในคิว — **ไม่มีให้แสดง (ไม่ใช่ PASS และไม่ใช่ FAIL)**

baseline: `staging/crawl` ว่าง และ `staging_path` เป็น null ทั้ง 12 แถว
`staging_store` จึงคืน `None` ทุกกรณีและ route ตอบ **404 แบบปิดประตู** ตามที่โค้ดกำหนด
นี่พิสูจน์ว่า "ไม่มีไฟล์แล้วปฏิเสธอย่างปลอดภัย" **ไม่ใช่การพิสูจน์ว่าแสดง PDF ของ candidate ได้**
บันทึกเป็น **staged preview unavailable** · **ไม่ได้สร้าง ไม่ได้ดึง และไม่ได้ stage candidate ใด
เพื่อทำให้ preview ทำงาน**

(ผลการทดสอบด่าน fail-closed 9/9 แบบ isolated อยู่ในรายงาน Step 3 ไม่ได้ทำซ้ำในรอบนี้)

### 9.4 ข้อควรระวังเรื่อง routing สาธารณะ

โดเมน HTTPS `/crawl-review` ตอบ **HTTP 200** แต่เป็น **SPA fallback จาก `/srv/web`**
ของทีมออกแบบ (`try_files {path} /index.html`) **ไม่ใช่หน้า Next.js ที่ deploy**
HTTP 200 บนโดเมนจึง **ไม่ใช่ PASS ของ Phase 3B UI** — เรื่องการเปิดหน้านี้บนโดเมน
ยังเป็น **การตัดสินใจแยก** ไม่ได้แก้ Caddy, DNS, frontend config, proxy หรือ public routing

---

## 10. ตัวเลขฝั่งฐานข้อมูล ก่อน / หลัง

| รายการ | ก่อน | หลัง | ผล |
|---|---:|---:|---|
| `mko.crawl_decisions` | **0** | **0** | **คงเป็น 0** |
| `courses` | 24 | 24 | คงเดิม |
| `course_documents` | 31 | 31 | คงเดิม |
| `course_chunks` | 9039 | 9039 | คงเดิม |
| embedding dimension | 1024 | 1024 | คงเดิม |
| `mko.crawl_sources` | 12 | 12 | คงเดิม |
| status `unchanged` / `needs_review` / `staging_path` ไม่ null | 12 / 6 / 0 | 12 / 6 / 0 | คงเดิม |
| `mko.v_crawl_queue` | 6 | 6 | คงเดิม |
| `chat_messages` / `chat_answer_cache` | 6640 / 160 | 6640 / 160 | คงเดิม |
| `users` / active / admins | 197 / 197 / 0 | 197 / 197 / 0 | คงเดิม |
| `mko.schema_migrations` | 001–004 | 001–004 | คงเดิม |

**ไม่มี POST approve / ignore / undo ถูกเรียกแม้ครั้งเดียว** และไม่ได้ทดสอบ route ที่เปลี่ยนสภาพ
แม้จะคาดว่าถูกปฏิเสธ

---

## 11. Staging / documents / mount / worker

| รายการ | ก่อน | หลัง |
|---|---|---|
| `staging/crawl` | 0 รายการ | **0 รายการ** |
| เอกสารเทียบ manifest เดิม | 32/32 ตรง | **32/32 ตรง** (ไม่ตรง 0 ขาด 0 เกิน 0) |
| `.pdf` ในดิสก์ | 30 | 30 |
| mount `/srv/staging` | RW=false | **RW=false** |
| mount `/srv/documents` | RW=false | **RW=false** |
| worker / crawler | ไม่ทำงาน | **ไม่ทำงาน** (คอนเทนเนอร์ 0 · โปรเซส 0) |

ไม่ได้เขียนไฟล์ probe · ไม่ได้แตะเนื้อหาใน `staging/` หรือ `documents/`

---

## 12. Container / image / StartedAt / RestartCount ก่อน–หลัง

| Service | Container ID ก่อน → หลัง | Image ก่อน → หลัง | StartedAt | RestartCount |
|---|---|---|---|---:|
| backend | `fda31caa20c4` → `fda31caa20c4` | `4a45677ec010` → เดิม | 2026-09-29T01:06:17.872Z ไม่เปลี่ยน | 0 |
| frontend | `2886c1bf9183` → `2886c1bf9183` | `591ab6d935bb` → เดิม | 2026-09-29T01:07:21.190Z ไม่เปลี่ยน | 0 |
| caddy | `a2957d7b8fc3` → `a2957d7b8fc3` | `5f5c8640aae0` → เดิม | 2026-09-22T21:23:48.949Z ไม่เปลี่ยน | 0 |
| postgres | `e8c091a4fc60` → `e8c091a4fc60` | `ccc6e83d6e35` → เดิม | 2026-08-18T14:17:25.705Z ไม่เปลี่ยน | 0 |
| ollama | `e6ac0350c722` → `e6ac0350c722` | `9d30908e4114` → เดิม | 2026-08-18T14:17:25.705Z ไม่เปลี่ยน | 0 |
| webapi | `6a73308d4f39` → `6a73308d4f39` | `1163e36361d9` → เดิม | 2026-09-22T21:21:35.624Z ไม่เปลี่ยน | 0 |

**ไม่มีการแทนที่คอนเทนเนอร์ในรอบนี้** — ต่างจาก Step 3 ที่ backend/frontend ถูกแทนที่
โดยเจตนา (RestartCount 0 ตอนนั้นไม่ได้หมายถึง "ไม่มีการ restart") รอบนี้ทั้ง container ID
และ StartedAt เท่าเดิมทุกบริการ จึงยืนยันได้ว่าไม่มี restart และไม่มี recreate

---

## 13. Production mutation ledger

### **ไม่มี mutation ใด ๆ ในรอบนี้**

ทุกการดำเนินการเป็นการอ่าน: `git` แบบอ่าน, `git ls-remote`, `docker inspect`, `docker logs`,
`docker exec` ที่รัน `psql` ใน `BEGIN TRANSACTION READ ONLY` พร้อม `statement_timeout`,
`printenv` ของสองคีย์ที่ไม่ใช่ความลับ, `ls`, `find`, `sha256sum -c`, และ `curl` แบบ GET
ที่ไม่ส่ง credential

ยืนยันว่า **ไม่ได้ทำ** สิ่งต่อไปนี้: ไม่ promote/สร้าง/แก้บัญชีใด · ไม่แตะ password, email,
`is_active`, profile, ผู้ใช้อื่น, role store อื่น หรือ Supabase · ไม่สร้าง session/token ·
ไม่ POST approve/ignore/undo · ไม่แตะ `crawl_sources`/status/hash/staging path ·
ไม่แตะเนื้อหา staging/documents หรือข้อมูลหลักสูตร · ไม่เรียก chat/RAG/recommend/search/
match/compare · ไม่ start/run/rebuild worker หรือ crawler · ไม่เปิด worker profile ·
ไม่เรียก `pipeline.ingest` หรือ `pipeline.crawl.approve` (รวมทั้ง `--help`) ·
ไม่สร้าง embedding ของเอกสาร · ไม่สร้าง candidate ปลอม · ไม่ restart บริการใด ·
ไม่แก้ Caddy/DNS/public routing · ไม่แก้โค้ดหรือ config · ไม่รัน migration หรือแก้ grant ·
ไม่ deploy · ไม่ commit/push/merge หรือแก้ ref ใด · ไม่ restore ฐานข้อมูล

### กิจกรรม embedding ที่สังเกตได้ — บันทึกแยกและอธิบายครบ

```
จำนวนครั้งที่ backend เรียก ollama /api/embeddings ตั้งแต่ cutover (01:06:17Z): 7
จำนวนคำขอ /chat ที่เข้าถึง backend:                                          0
```

ทั้ง 7 ครั้งมาจาก `_keep_models_warm()` ที่ [backend/app/main.py:68](backend/app/main.py:68)
ซึ่งเรียก `connector.embed("warmup")` ทุก 20 นาที (ค่า `WARMUP_INTERVAL_MINUTES` เริ่มต้น 20)

ตรวจความสอดคล้องด้วยเลขจริง: backend ทำงานมา **127 นาที** (01:06:17Z → ~03:13Z)
→ 1 ครั้งตอนเริ่ม + `floor(127/20) = 6` ครั้งตามรอบ = **7 ครั้งพอดี** ตรงกับที่นับได้

- รายงาน Step 3 บันทึกไว้ **1 ครั้ง** (ตอน cutover) — นั่นเป็นกิจกรรมของ Step 3
  ส่วนอีก 6 ครั้งเกิดขึ้นเองตามรอบระหว่าง Step 3 จบถึง Step 3.5 นี้
- **ผมไม่ได้กระตุ้น warmup และไม่ได้ปิดหรือแก้ค่า config ของมัน**
- นี่ **ไม่ใช่ document ingestion** — embed สตริง `"warmup"` แล้วทิ้ง ไม่เขียนแถวใด
  ยืนยันด้วย `course_chunks = 9039` และ `chat_messages = 6640` ที่ไม่ขยับ
- **ไม่อ้างว่า "ไม่มี embedding เกิดขึ้นเลย"**

ข้อจำกัดของการสังเกต: log ของ uvicorn ไม่ประทับเวลาต่อบรรทัด จึงยืนยันเวลาแต่ละครั้ง
ไม่ได้ ใช้การนับรวมเทียบกับ uptime และคาบของ warmup แทน ซึ่งตรงกันพอดี

---

## 14. รายการ BLOCKED / HUMAN ACTION REQUIRED / NOT TESTED

| # | รายการ | สถานะ | เหตุผล |
|---|---|---|---|
| 1 | promote `Tester@gmail.com` เป็น admin | **BLOCKED** | ไม่มีบัญชีที่ตรงเลย (0 match ทุกวิธีตรวจ) · §2 สั่งให้ STOP ไม่สร้างและไม่ promote |
| 2 | login ปกติด้วยบัญชี admin | **HUMAN ACTION REQUIRED** | ไม่มีบัญชี และไม่มี credential ที่เข้าถึงได้อย่างปลอดภัย |
| 3 | `GET /users/me` | **NOT TESTED** | ต้องมี token · และยืนยัน admin ไม่ได้เพราะ `UserOut` ไม่มี `is_admin` |
| 4 | `GET /crawl-review/pending` แบบ authenticated (คาด 6 รายการ) | **HUMAN ACTION REQUIRED** | ต้องมี admin |
| 5 | `GET /crawl-review/{id}` รายละเอียดแบบอ่าน | **HUMAN ACTION REQUIRED** | ต้องมี admin |
| 6 | non-admin 403 | **NOT TESTED** | ไม่มี session non-admin ที่ปลอดภัย · ไม่สร้างบัญชีเพื่อทดสอบ |
| 7 | คิวที่ render จริง + action control | **HUMAN ACTION REQUIRED** | ต้องมี admin |
| 8 | PDF preview ของรายการในคิว | **ไม่มีให้แสดง** | staging ว่างและ `staging_path` null ทั้งหมด → 404 ปิดประตูตามที่โค้ดกำหนด · ไม่ใช่ PASS |
| 9 | เปิดหน้า `/crawl-review` บนโดเมน HTTPS | **การตัดสินใจแยก** | โดเมนเสิร์ฟ SPA จาก `/srv/web` · ไม่แก้ Caddy |

**ไม่พบสภาพที่ไม่คาดคิดอื่นใด** นอกจากจำนวน 0 match ในข้อ 1 และส่วนต่างของไฟล์รายงานในข้อ 1.2

---

## 15. Blocker เรื่อง legitimate candidate

`mko.crawl_sources` ทั้ง **12 แถวเป็นสถานะ `unchanged`** · `staging_path` เป็น null ทั้ง 12 ·
`staging/crawl` ว่าง → **ไม่มี PDF ใหม่หรือที่เปลี่ยนจริงที่ stage ไว้เลย**

**คำเตือนที่ต้องย้ำ: 6 รายการในคิว (`needs_review = true`) ไม่ใช่ 6 candidate ที่นำเข้าได้**
แถวเหล่านั้นถูกตั้งธง `needs_review` เพราะการจับคู่หลักสูตรยังไม่ชัด ไม่ใช่เพราะมีไฟล์ใหม่
ทั้ง 6 แถวมีสถานะ `unchanged` และไม่มีไฟล์ใน staging จึงยังไม่มีอะไรให้ worker ทำ

candidate ที่ถูกต้องต้องเป็นไฟล์ใหม่หรือไฟล์ที่เปลี่ยนจริงจากต้นทาง `sci.pnru.ac.th`
พร้อม staged PDF และ hash ที่ตรวจได้ — **ไม่ได้สร้าง ไม่ได้ปลอม และไม่ได้รัน crawler**
เพื่อทำให้เกิด candidate

---

## 16. GO / NO-GO สำหรับ future controlled one-job ingestion

### **NO-GO**

เป็น readiness assessment เท่านั้น **ไม่ใช่การอนุญาตให้เริ่ม ingestion**
และไม่ได้ตั้งเวลาการทำงานต่อเนื่องใด

เหตุผลที่ปิดกั้น พร้อมหลักฐาน

| # | เหตุ | หลักฐาน |
|---|---|---|
| 1 | **ยังไม่มีบัญชี admin** | `admins = 0` และบัญชีที่อนุมัติไม่มีอยู่ (0 match) |
| 2 | **ไม่มี legitimate candidate** | 12 แหล่ง `unchanged` · `staging_path` null ทั้งหมด · staging ว่าง |
| 3 | การยืนยัน authenticated UI/API ยังไม่เสร็จ | ข้อ 14 รายการ 2–7 |

สิ่งที่ **พร้อมแล้ว** และไม่ใช่เหตุปิดกั้น: migration 004 ครบถ้วนถูกต้อง ·
backend Phase 3A และ frontend Phase 3B ให้บริการอยู่จาก DEPLOY_REV ·
mount staging/documents read-only ทั้งคู่ · anonymous guard ตอบ 401 ทั้งสาม route ·
หน้า Next.js เป็น route จริง · worker image และ config พร้อม · backup และ rollback ครบ

ประเด็นที่ยังค้างและต้องแยกจากกัน: **การยืนยันแบบ authenticated** (ต้องมี admin)
และ **การตัดสินใจเรื่อง routing ของหน้าเว็บบนโดเมนสาธารณะ** (ต้องให้คนตัดสิน ไม่ใช่แก้ Caddy)

---

## 17. คำสั่งที่เตรียมไว้ — promote และ rollback แบบมีด่าน (ยังไม่รัน)

ทั้งสองชุดสร้างจาก schema ที่ตรวจจริงในข้อ 3: ตาราง `public.users`, คอลัมน์ `email citext`
(unique), `is_active boolean`, `is_admin boolean`, PK `id uuid`, trigger
`trg_users_updated_at` ที่แตะเฉพาะ `updated_at`

`<APPROVED_EMAIL>` ต้องเป็นอีเมลของ**บัญชีที่มีอยู่จริง** ที่เจ้าของโปรเจกต์ระบุและอนุมัติ
ค่าที่อนุมัติมาในรอบนี้คือ `Tester@gmail.com` ซึ่ง**ไม่มีในระบบ** จึงยังใช้ไม่ได้

### 17.1 Promotion (ใช้เมื่อเจ้าของระบุอีเมลของบัญชีที่มีอยู่จริง)

```sql
BEGIN;
SET LOCAL lock_timeout = '3s';
SET LOCAL statement_timeout = '15s';

-- กันการเปลี่ยนแปลงของผู้ใช้อื่นระหว่างตรวจกับ UPDATE โดยไม่ล็อกตารางที่ไม่เกี่ยว
LOCK TABLE public.users IN SHARE ROW EXCLUSIVE MODE;

DO $$
DECLARE n_all int; n_ok int; n_users int; n_active int; n_admin int; n_dec bigint;
BEGIN
    -- ใช้ semantics จริงของแอป: email เป็น citext จึงเทียบไม่สนตัวพิมพ์เอง
    SELECT count(*) INTO n_all  FROM public.users WHERE email = '<APPROVED_EMAIL>';
    SELECT count(*) INTO n_ok   FROM public.users
      WHERE email = '<APPROVED_EMAIL>' AND is_active AND NOT is_admin;
    IF n_all <> 1 THEN RAISE EXCEPTION 'หยุด: พบ % บัญชีที่ตรงอีเมล ต้องได้ 1 พอดี', n_all; END IF;
    IF n_ok  <> 1 THEN RAISE EXCEPTION 'หยุด: บัญชีนั้นไม่ active หรือเป็น admin อยู่แล้ว'; END IF;

    SELECT count(*), count(*) FILTER (WHERE is_active), count(*) FILTER (WHERE is_admin)
      INTO n_users, n_active, n_admin FROM public.users;
    IF (n_users, n_active, n_admin) <> (197, 197, 0)
      THEN RAISE EXCEPTION 'หยุด: aggregate ผู้ใช้ไม่ใช่ 197/197/0 (ได้ %/%/%)', n_users, n_active, n_admin; END IF;

    SELECT count(*) INTO n_dec FROM mko.crawl_decisions;
    IF n_dec <> 0 THEN RAISE EXCEPTION 'หยุด: mko.crawl_decisions มี % แถว', n_dec; END IF;
END $$;

-- ตรึงแถวเป้าหมายไว้จนจบธุรกรรม
SELECT id FROM public.users
 WHERE email = '<APPROVED_EMAIL>' AND is_active AND NOT is_admin
 FOR UPDATE;

UPDATE public.users
   SET is_admin = TRUE
 WHERE email = '<APPROVED_EMAIL>' AND is_active AND is_admin = FALSE;
-- ห้ามใส่ LIMIT 1 และห้ามใช้ substring ของอีเมล

DO $$
DECLARE n_users int; n_active int; n_admin int; tgt_ok int;
BEGIN
    -- ROW_COUNT ของ UPDATE ข้างบนต้องเป็น 1
    IF (SELECT count(*) FROM public.users
         WHERE email = '<APPROVED_EMAIL>' AND is_active AND is_admin) <> 1
      THEN RAISE EXCEPTION 'หยุด: เป้าหมายไม่ได้อยู่ในสภาพ active+admin หลัง UPDATE'; END IF;

    SELECT count(*), count(*) FILTER (WHERE is_active), count(*) FILTER (WHERE is_admin)
      INTO n_users, n_active, n_admin FROM public.users;
    IF (n_users, n_active, n_admin) <> (197, 197, 1)
      THEN RAISE EXCEPTION 'หยุด: หลัง UPDATE ต้องเป็น 197/197/1 (ได้ %/%/%)', n_users, n_active, n_admin; END IF;

    IF (SELECT count(*) FROM mko.crawl_decisions) <> 0
      THEN RAISE EXCEPTION 'หยุด: crawl_decisions ไม่เป็น 0'; END IF;
    IF (SELECT count(*) FROM public.courses) <> 24
      OR (SELECT count(*) FROM public.course_documents) <> 31
      OR (SELECT count(*) FROM public.course_chunks) <> 9039
      OR (SELECT count(*) FROM mko.crawl_sources) <> 12
      THEN RAISE EXCEPTION 'หยุด: invariants ของหลักสูตร/crawler เปลี่ยน'; END IF;
END $$;

COMMIT;
```

รันด้วย `psql -v ON_ERROR_STOP=1` ผ่านช่องทางเดิมที่ไม่ใส่ credential ลง argument
และหลัง COMMIT ต้องตรวจสภาพใน read-only transaction แยกอีกครั้ง
**หมายเหตุ:** trigger `trg_users_updated_at` จะเปลี่ยน `updated_at` ของแถวนั้นด้วย
ซึ่งเป็นพฤติกรรมที่ตั้งใจของ schema ไม่ใช่การแก้ข้อมูลที่ห้าม

### 17.2 Rollback — ลด `is_admin: true → false` ของบัญชีเดียวกันเท่านั้น

**ยังไม่ได้รัน และห้ามรันเพื่อทดสอบ** ใช้เมื่อจำเป็นต้องถอนสิทธิ์จริงเท่านั้น
ไม่ใช่การลดสิทธิ์เป็นชุด ไม่ลบผู้ใช้ ไม่รีเซ็ตรหัสผ่าน ไม่ restore ไม่ย้อน migration
และไม่ rollback บริการ

```sql
BEGIN;
SET LOCAL lock_timeout = '3s';
SET LOCAL statement_timeout = '15s';
LOCK TABLE public.users IN SHARE ROW EXCLUSIVE MODE;

DO $$
DECLARE n_all int; n_ok int; n_users int; n_active int; n_admin int;
BEGIN
    SELECT count(*) INTO n_all FROM public.users WHERE email = '<APPROVED_EMAIL>';
    SELECT count(*) INTO n_ok  FROM public.users
      WHERE email = '<APPROVED_EMAIL>' AND is_active AND is_admin;
    IF n_all <> 1 THEN RAISE EXCEPTION 'หยุด: พบ % บัญชีที่ตรงอีเมล ต้องได้ 1 พอดี', n_all; END IF;
    IF n_ok  <> 1 THEN RAISE EXCEPTION 'หยุด: บัญชีนั้นไม่ได้เป็น admin ที่ active อยู่'; END IF;

    SELECT count(*), count(*) FILTER (WHERE is_active), count(*) FILTER (WHERE is_admin)
      INTO n_users, n_active, n_admin FROM public.users;
    IF (n_users, n_active, n_admin) <> (197, 197, 1)
      THEN RAISE EXCEPTION 'หยุด: ก่อนถอนสิทธิ์ต้องเป็น 197/197/1 (ได้ %/%/%)', n_users, n_active, n_admin; END IF;
END $$;

SELECT id FROM public.users
 WHERE email = '<APPROVED_EMAIL>' AND is_active AND is_admin
 FOR UPDATE;

UPDATE public.users
   SET is_admin = FALSE
 WHERE email = '<APPROVED_EMAIL>' AND is_active AND is_admin = TRUE;

DO $$
DECLARE n_users int; n_active int; n_admin int;
BEGIN
    IF (SELECT count(*) FROM public.users
         WHERE email = '<APPROVED_EMAIL>' AND is_active AND NOT is_admin) <> 1
      THEN RAISE EXCEPTION 'หยุด: เป้าหมายไม่ได้อยู่ในสภาพ active และไม่ใช่ admin'; END IF;
    SELECT count(*), count(*) FILTER (WHERE is_active), count(*) FILTER (WHERE is_admin)
      INTO n_users, n_active, n_admin FROM public.users;
    IF (n_users, n_active, n_admin) <> (197, 197, 0)
      THEN RAISE EXCEPTION 'หยุด: หลังถอนสิทธิ์ต้องเป็น 197/197/0 (ได้ %/%/%)', n_users, n_active, n_admin; END IF;
    IF (SELECT count(*) FROM mko.crawl_decisions) <> 0
      THEN RAISE EXCEPTION 'หยุด: crawl_decisions ไม่เป็น 0'; END IF;
END $$;

COMMIT;
```

**การยืนยันเป้าหมายให้ตรงกันโดยไม่เผย ID:** ทั้งสองชุดระบุเป้าหมายด้วยอีเมลที่อนุมัติ
ร่วมกับเงื่อนไข `is_active` และสถานะ `is_admin` ที่คาดไว้ และบังคับ cardinality = 1
ด้วย `RAISE EXCEPTION` เพราะ `email` เป็น `citext` ที่มี unique index จึงรับประกันว่า
อีเมลหนึ่งค่าชี้ได้เพียงแถวเดียว **ไม่ต้องใช้ internal ID ใดในคำสั่ง** และรายงานนี้
จึงไม่มี ID ใดให้ redact · หากผู้ปฏิบัติต้องการยืนยันเป็นรายแถวก่อนรัน ให้ SELECT
`is_active, is_admin` ของอีเมลนั้นใน read-only transaction ก่อน **ไม่ต้องใช้ query
แบบกว้างที่ดึงผู้ใช้อื่น**

---

## 18. git status ปิดท้าย และไฟล์ที่เปลี่ยน

```
branch            mko-phase2
HEAD              2fdc6f241fc1742047b572ee2ef354cd811f9401
origin/mko-phase2 2fdc6f241fc1742047b572ee2ef354cd811f9401   = DEPLOY_REV ไม่เปลี่ยน
origin/main       b78b3f8bf895685874d9a52c66b45569072f0514   ไม่เปลี่ยน
staged                0 ไฟล์
tracked modified      0 ไฟล์
untracked นอก docs/    0 ไฟล์
untracked ใน docs/     43 ไฟล์ (รวมรายงานฉบับนี้ = 43 + 1 หลังเขียนเสร็จ)
tag local / remote    0 / 0
```

ไฟล์เดียวที่สร้างในรอบนี้คือรายงานฉบับนี้
`docs/AUTOMATED_INGESTION_PHASE3D_STEP3_5_ADMIN_VERIFICATION_REPORT.md` (uncommitted
ตามแนวปฏิบัติของ `docs/` ในโปรเจกต์นี้)

**ไม่มีการแก้โค้ดหรือ config · ไม่มี commit · ไม่มี push · ไม่มี merge · ไม่มีการแก้ ref ใด**

---

## สรุปสั้น

- **§1 baseline gate PASS ทุกข้อ** — บริการทั้งหกไม่เปลี่ยน (เทียบทั้ง container ID และ
  StartedAt), image ID และ OCI label ตรง DEPLOY_REV, migration 004 ครบ,
  invariants 24/31/9039/12 · decisions 0 · users 197/197/0 · เอกสาร 32/32 · staging ว่าง
- **§2 หยุดที่นี่: `Tester@gmail.com` ไม่มีอยู่ในระบบ (0 บัญชี)** ตรวจแล้วสี่ทาง
  (citext ตรงตัว, `lower()`, `btrim()`, `tester@` ทุกโดเมน) ได้ 0 ทั้งหมด
  จึง **BLOCKED ไม่ promote ไม่สร้างบัญชี และไม่เลือกบัญชีแทน**
- **ไม่มี production mutation ในรอบนี้เลย** ทุกอย่างเป็นการอ่าน
- แก้ข้อเท็จจริงสำคัญ: `users.email` เป็น **`citext`** ไม่ใช่ `String` ตามที่ ORM ประกาศ
  การเทียบอีเมลของแอปจึง**ไม่สนตัวพิมพ์**โดยกลไกของฐานข้อมูล — ผมเคยสรุปผิดว่าเป็น
  case-sensitive จากการอ่าน model อย่างเดียว
- `/users/me` **ไม่มีฟิลด์ `is_admin`** จึงใช้ยืนยันสิทธิ์ไม่ได้ · `require_admin` อ่าน
  `is_admin` จากแถวผู้ใช้ที่โหลดใหม่ทุกคำขอ → **ไม่ต้อง restart** และไม่ได้ restart
- anonymous guard **PASS**: ทั้งสาม GET ตอบ 401 ไม่รั่วข้อมูล · หน้า Next.js
  `/crawl-review` เป็น route จริง (chunk เฉพาะ route, hash ต่างจากหน้าแรก)
- **authenticated API/UI/PDF = HUMAN ACTION REQUIRED** ทั้งหมด
- warmup embedding สังเกตได้ **7 ครั้ง** อธิบายครบด้วย uptime 127 นาที ÷ 20 + 1 = 7
  ไม่ใช่ ingestion ไม่ได้กระตุ้น และไม่ได้แก้ค่า config
- **GO/NO-GO สำหรับ one-job ingestion: NO-GO** (ไม่มี admin, ไม่มี candidate)
  และย้ำว่า **6 รายการในคิวไม่ใช่ 6 candidate ที่นำเข้าได้**

### สิ่งที่เจ้าของโปรเจกต์ต้องทำต่อ

ระบุ**อีเมลที่ถูกต้องของบัญชีที่มีอยู่จริง** (มีบัญชีโดเมน gmail.com อยู่ 6 บัญชี และบัญชี
ที่ local part ขึ้นต้นด้วย `test` อยู่ 2 บัญชี แต่ไม่มี `tester@` เลย) หรือสมัครบัญชีนั้นเอง
ผ่านขั้นตอนปกติของแอป แล้วอนุมัติอีกครั้ง — คำสั่ง promotion ที่มีด่านครบพร้อมใช้ในข้อ 17.1
**ไม่ต้องส่งรหัสผ่านมาให้ผม**

**STOP**
