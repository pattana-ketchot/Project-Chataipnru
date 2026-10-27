# Phase 3D Step 3.5 (RESUME) — Admin Promotion + Authorization Verification

| | |
|---|---|
| วันที่ | 2026-09-29 · ช่วงทำงาน **08:49:00Z – 08:53Z** (ไทย 15:49–15:53) |
| Decision ที่ยึด | **Architecture Option B** — Supabase Auth ยังเป็นระบบของ SPA/webapi · FastAPI + PostgreSQL เป็นระบบของ Next.js และ `/crawl-review` · ไม่รวม auth ไม่ทำ SSO ไม่ทำ identity mapping |
| บัญชีที่เจ้าของอนุมัติ | **`Tester@gmail.com`** เท่านั้น |
| ผลการ promote | **สำเร็จ · COMMIT · affected rows = 1 พอดี** |
| Production mutation | **1 รายการเดียว**: `public.users.is_admin` ของบัญชีนั้น `false → true` (+ `updated_at` ที่ trigger เปลี่ยนตาม schema) |
| Restart | **ไม่มี** — ทั้งหกบริการ container ID และ StartedAt เดิม |
| `mko.crawl_decisions` | **0 ทั้งก่อนและหลัง** |
| authenticated login/UI test | **เสร็จแล้ว — PASS** (เจ้าของทำเอง 2026-09-29 ราว 11:50–12:00Z) ดูข้อ 20 · ตอนเขียนรายงานส่วนแรกยังเป็น HUMAN ACTION REQUIRED |
| GO/NO-GO สำหรับ one-job ingestion | **ยัง NO-GO** — ไม่มี legitimate candidate |

เอกสารที่อ่านก่อนเริ่ม: `AUTH_ARCHITECTURE_AUDIT.md` ·
`PHASE3D_ADMIN_REGISTRATION_SAFETY_CHECK.md` ·
`AUTOMATED_INGESTION_PHASE3D_STEP3_5_ADMIN_VERIFICATION_REPORT.md` ·
`AUTOMATED_INGESTION_PHASE3D_STEP3_RESUME_REPORT.md`

---

## 1. สภาพบัญชีก่อน promote

ตรวจด้วย **citext equality ตรงตัว** (`email = 'Tester@gmail.com'`) ซึ่งเป็น semantics จริง
ของแอปเพราะคอลัมน์เป็น `citext` · **ไม่ได้อ่าน `password_hash`**

| รายการ | ค่าที่ต้องได้ | ค่าจริง | ผล |
|---|---|---|---|
| จำนวนบัญชีที่ตรง (นับก่อนกรอง active) | 1 พอดี | **1** | PASS |
| `email` ที่เก็บไว้ | — | `Tester@gmail.com` (ตัวพิมพ์ตรงตามที่เจ้าของกรอก) | — |
| `is_active` | `true` | **true** | PASS |
| `is_admin` | `false` | **false** | PASS |
| `created_at` | — | `2026-09-29 14:53:16.777237+07` (= 07:53:16Z) | — |
| `updated_at` (ก่อน) | — | `2026-09-29 14:53:16.777237+07` เท่ากับ `created_at` | — |

ตรวจความกำกวมอีกสองชั้น: `lower(email::text)` ตรงกัน **1** บัญชี ·
`email::text ILIKE 'tester@%'` (ทุกโดเมน) **1** บัญชี → ไม่มีบัญชีใกล้เคียงที่ทำให้สับสน

**ยืนยันว่าเป็นบัญชีที่เจ้าของสมัครในรอบนี้**: `created_at` = 07:53:16Z ซึ่งอยู่**หลัง**
การตรวจ registration safety check ที่ 04:50Z และมีบัญชีที่ถูกสร้างหลัง 04:50Z
**เพียง 1 บัญชี** — สอดคล้องกับที่เจ้าของแจ้งว่าได้ `HTTP 201`

บัญชี `Tester@gmail.com` ที่อยู่ใน **Supabase** เป็น identity store คนละตัว
**ไม่ได้แก้ ไม่ได้ลบ ไม่ได้ migrate** ตามข้อกำหนดของ Option B

---

## 2. Baseline counts ที่วัดจริง (ไม่ hard-code)

อ่านใน read-only transaction ที่ 08:49Z ก่อนแตะข้อมูล

| รายการ | ค่าที่วัดจริง | หมายเหตุ |
|---|---:|---|
| `users_total` | **198** | = 197 เดิม + 1 บัญชีที่เจ้าของสมัคร |
| `users_active` | **198** | |
| `users_admin` (ก่อน) | **0** | ค่านี้ถูกใช้เป็น `previous_admin_count` |
| บัญชีที่สร้างหลัง 04:50Z | 1 | = การสมัครของเจ้าของ |

**ไม่ได้ hard-code 197 หรือ 198** — ค่าที่ใส่ใน assertion ของ transaction มาจากการวัดครั้งนี้
ถ้าค่าจริงต่างจากนี้ transaction จะ `RAISE EXCEPTION` และ rollback เอง

### สภาพ production ก่อน promote

| service | container | image | status | restarts | StartedAt |
|---|---|---|---|---|---|
| backend | `fda31caa20c4` | `4a45677ec010` | running | 0 | 2026-09-29T01:06:17.872Z |
| frontend | `2886c1bf9183` | `591ab6d935bb` | running | 0 | 2026-09-29T01:07:21.190Z |
| caddy | `a2957d7b8fc3` | `5f5c8640aae0` | running | 0 | 2026-09-22T21:23:48.949Z |
| postgres | `e8c091a4fc60` | `ccc6e83d6e35` | running | 0 | 2026-08-18T14:17:25.705Z |
| ollama | `e6ac0350c722` | `9d30908e4114` | running | 0 | 2026-08-18T14:17:25.705Z |
| webapi | `6a73308d4f39` | `1163e36361d9` | running | 0 | 2026-09-22T21:21:35.624Z |

OCI revision label ของ backend และ frontend = `2fdc6f241fc1742047b572ee2ef354cd811f9401`
ทั้งคู่ · `Caddyfile` sha256 = `da2e26fd948d2a7143c85d1ee7dde204c774569d6f2e49130ea9bd059aec0f0d`
— **ตรงกับ baseline ล่าสุดทุกค่า ไม่มี drift**

### Implementation ยังเหมือนที่ audit ยืนยัน — อ่านจากอิมเมจที่ให้บริการอยู่จริง

| ข้อตรวจ | ผล |
|---|---|
| `get_current_user` ทำ `db.get(User, uuid.UUID(payload["sub"]))` ทุกคำขอ | พบ 1 จุด ✓ |
| `require_admin` ตรวจ `if not user.is_admin` | พบ 1 จุด ✓ |
| router `/crawl-review` ใส่ `dependencies=[Depends(require_admin)]` | พบ 1 จุด ✓ |
| `security.py` อ้าง `is_admin` (ต้องเป็น 0 = token ไม่มี role claim) | **0** ✓ |
| `UserOut` มีฟิลด์ `is_admin` (ต้องเป็น 0) | **0** ✓ |

`create_access_token` ในอิมเมจใส่เพียง `sub`, `type`, `iat`, `exp`
→ **สิทธิ์ไม่ได้อยู่ใน token** จึงไม่ต้อง restart และไม่ต้อง login ใหม่

### Invariants ก่อน promote

`crawl_decisions = 0` · `courses = 24` · `course_documents = 31` · `course_chunks = 9039` ·
`crawl_sources = 12` (unchanged 12, needs_review 6, staging_path ไม่ null 0) ·
`embedding_dim = 1024` · `v_crawl_queue = 6` ·
`migrations = 001,002,003,004_crawl_decisions` · `chat_messages = 6640` ·
`chat_answer_cache = 160` · `staging/crawl` **0 รายการ** ·
trigger บน `users` มีตัวเดียวคือ `trg_users_updated_at` · `email` เป็น `citext`

**PHASE 1 gate: PASS ทุกข้อ**

---

## 3. Guarded transaction ที่ใช้

เก็บไฟล์จริงไว้เป็นหลักฐานที่ `/home/ubuntu/promote_tester_admin_20260929.sql`
(100 บรรทัด · sha256 `eb91307d84abef3673b3d40a129bcfc24f8448d7bf53c16f18e7892283253d7c`)
รันด้วย `psql -v ON_ERROR_STOP=1 -f` ผ่านช่องทางเดิม ไม่มี credential ใน argument

```sql
BEGIN;
SET LOCAL lock_timeout = '3s';
SET LOCAL statement_timeout = '30s';

-- กันการเขียนของผู้ใช้อื่นระหว่างตรวจกับ UPDATE โดยไม่ล็อกตารางที่ไม่เกี่ยว (อ่านยังทำได้ปกติ)
LOCK TABLE public.users IN SHARE ROW EXCLUSIVE MODE;

DO $$
DECLARE
    n_all int; n_ok int;
    n_users int; n_active int; n_admin_before int; n_admin_after int;
    n_rows int; tgt uuid;
    v_active boolean; v_admin boolean;
BEGIN
    -- 1. cardinality และสภาพของเป้าหมาย (citext equality ตรงตัว)
    SELECT count(*) INTO n_all FROM public.users WHERE email = 'Tester@gmail.com';
    IF n_all <> 1 THEN RAISE EXCEPTION 'หยุด: พบ % บัญชีที่ตรงอีเมล ต้องได้ 1 พอดี', n_all; END IF;

    SELECT count(*) INTO n_ok FROM public.users
      WHERE email = 'Tester@gmail.com' AND is_active AND NOT is_admin;
    IF n_ok <> 1 THEN RAISE EXCEPTION 'หยุด: บัญชีเป้าหมายไม่ active หรือเป็น admin อยู่แล้ว'; END IF;

    -- 2. ตรึงแถวเป้าหมายไว้จนจบธุรกรรม
    SELECT id INTO tgt FROM public.users
      WHERE email = 'Tester@gmail.com' AND is_active AND NOT is_admin
      FOR UPDATE;
    IF tgt IS NULL THEN RAISE EXCEPTION 'หยุด: ตรึงแถวเป้าหมายไม่ได้'; END IF;

    -- 3. aggregate ก่อน ต้องเท่าค่าที่วัดจริงใน PHASE 1
    SELECT count(*), count(*) FILTER (WHERE is_active), count(*) FILTER (WHERE is_admin)
      INTO n_users, n_active, n_admin_before FROM public.users;
    IF (n_users, n_active, n_admin_before) <> (198, 198, 0) THEN
        RAISE EXCEPTION 'หยุด: aggregate ก่อนไม่ตรงค่าที่วัดไว้ 198/198/0 (ได้ %/%/%)',
            n_users, n_active, n_admin_before;
    END IF;
    RAISE NOTICE 'ก่อน UPDATE: users=% active=% admins=%', n_users, n_active, n_admin_before;

    -- 4. invariants ก่อน
    IF (SELECT count(*) FROM mko.crawl_decisions)   <> 0    THEN RAISE EXCEPTION 'หยุด: mko.crawl_decisions ไม่เป็น 0'; END IF;
    IF (SELECT count(*) FROM public.courses)         <> 24   THEN RAISE EXCEPTION 'หยุด: courses เปลี่ยน'; END IF;
    IF (SELECT count(*) FROM public.course_documents)<> 31   THEN RAISE EXCEPTION 'หยุด: course_documents เปลี่ยน'; END IF;
    IF (SELECT count(*) FROM public.course_chunks)   <> 9039 THEN RAISE EXCEPTION 'หยุด: course_chunks เปลี่ยน'; END IF;
    IF (SELECT count(*) FROM mko.crawl_sources)      <> 12   THEN RAISE EXCEPTION 'หยุด: crawl_sources เปลี่ยน'; END IF;

    -- 5. UPDATE คอลัมน์เดียว ของแถวเดียว
    UPDATE public.users
       SET is_admin = TRUE
     WHERE id = tgt
       AND email = 'Tester@gmail.com'
       AND is_active
       AND is_admin = FALSE;
    GET DIAGNOSTICS n_rows = ROW_COUNT;
    RAISE NOTICE 'affected rows = %', n_rows;
    IF n_rows <> 1 THEN RAISE EXCEPTION 'หยุด: affected rows = % ต้องเป็น 1 พอดี', n_rows; END IF;

    -- 6. ตรวจก่อน COMMIT
    SELECT is_active, is_admin INTO v_active, v_admin FROM public.users WHERE id = tgt;
    IF NOT v_active OR NOT v_admin THEN
        RAISE EXCEPTION 'หยุด: เป้าหมายไม่ได้อยู่ในสภาพ active+admin (active=% admin=%)', v_active, v_admin; END IF;

    SELECT count(*), count(*) FILTER (WHERE is_active), count(*) FILTER (WHERE is_admin)
      INTO n_users, n_active, n_admin_after FROM public.users;
    IF (n_users, n_active, n_admin_after) <> (198, 198, n_admin_before + 1) THEN
        RAISE EXCEPTION 'หยุด: หลัง UPDATE ต้องเป็น 198/198/% (ได้ %/%/%)',
            n_admin_before + 1, n_users, n_active, n_admin_after; END IF;
    RAISE NOTICE 'หลัง UPDATE: users=% active=% admins=%', n_users, n_active, n_admin_after;

    IF (SELECT count(*) FROM public.users WHERE email = 'Tester@gmail.com' AND is_active AND is_admin) <> 1 THEN
        RAISE EXCEPTION 'หยุด: ไม่ใช่ 1 บัญชีที่ active+admin สำหรับอีเมลนี้'; END IF;

    IF (SELECT count(*) FROM mko.crawl_decisions) <> 0 THEN
        RAISE EXCEPTION 'หยุด: crawl_decisions ไม่เป็น 0 หลัง UPDATE'; END IF;
    IF (SELECT count(*) FROM public.courses)          <> 24
       OR (SELECT count(*) FROM public.course_documents) <> 31
       OR (SELECT count(*) FROM public.course_chunks)    <> 9039
       OR (SELECT count(*) FROM mko.crawl_sources)       <> 12 THEN
        RAISE EXCEPTION 'หยุด: invariants ของหลักสูตร/crawler เปลี่ยนหลัง UPDATE'; END IF;

    RAISE NOTICE 'ผ่านทุกข้อตรวจ พร้อม COMMIT';
END $$;

COMMIT;
```

คุณสมบัติที่ยืนยันได้จากตัวสคริปต์

- `UPDATE` **คอลัมน์เดียว** (`is_admin`) ของ **แถวเดียว** โดยระบุด้วย primary key
  ที่ตรึงไว้ (`id = tgt`) ประกอบกับ **citext equality ตรงตัว** ของอีเมล
- **ไม่มี** `LIKE`, `ILIKE`, wildcard, substring, `LIMIT` หรือการอาศัย `LIMIT 1`
  เพื่อกลบกรณีหลายแถว — กรณีหลายแถวถูกจับด้วย `n_all <> 1` แล้ว `RAISE EXCEPTION`
- ใช้ `GET DIAGNOSTICS ROW_COUNT` ยืนยัน affected rows ภายใน transaction
- ทุกข้อตรวจที่ไม่ผ่านทำให้ `RAISE EXCEPTION` → ธุรกรรม rollback ทั้งชุด
- `RAISE NOTICE` พิมพ์เฉพาะตัวเลข **ไม่พิมพ์ UUID ของเป้าหมาย** และไม่พิมพ์ข้อมูลส่วนบุคคล

---

## 4. Affected rows และผลการ execute

รันเมื่อ **2026-09-29T08:50:54Z** (ไทย 15:50:54)

```
BEGIN
SET
SET
LOCK TABLE
NOTICE:  ก่อน UPDATE: users=198 active=198 admins=0
NOTICE:  affected rows = 1
NOTICE:  หลัง UPDATE: users=198 active=198 admins=1
NOTICE:  ผ่านทุกข้อตรวจ พร้อม COMMIT
DO
COMMIT
exit code: 0
```

**affected rows = 1 พอดี** · ทุก assertion ผ่าน · **COMMIT สำเร็จ** ไม่มี rollback

---

## 5. สภาพหลัง promote (read-only transaction แยกหลัง COMMIT)

| รายการ | ค่าที่ต้องได้ | ค่าจริง | ผล |
|---|---|---|---|
| จำนวนบัญชีที่ตรงอีเมล | 1 | **1** | PASS |
| `is_active` | `true` | **true** | PASS |
| **`is_admin`** | **`true`** | **true** | **PASS** |
| `created_at` | ไม่เปลี่ยน | `2026-09-29 14:53:16.777237+07` เท่าเดิม | PASS |
| `updated_at` | เปลี่ยนตาม trigger | `2026-09-29 15:50:54.925933+07` = เวลาที่ promote | ตามที่คาด |
| `users_total` | 198 (ไม่เปลี่ยน) | **198** | PASS |
| `users_active` | 198 (ไม่เปลี่ยน) | **198** | PASS |
| `users_admin` | 0 + 1 = 1 | **1** | PASS |

### หลักฐานว่าแตะแถวเดียวจริง

| ข้อตรวจ | ผลลัพธ์ |
|---|---:|
| จำนวน admin ที่ **ไม่ใช่** อีเมลเป้าหมาย | **0** |
| จำนวนบัญชีที่ `updated_at` เปลี่ยนใน 10 นาทีล่าสุด | **1** |

→ ไม่มีบัญชีอื่นถูกยกระดับ และไม่มีแถวอื่นถูกแก้เลย

---

## 6. Invariants ก่อน / หลัง

| รายการ | ก่อน | หลัง | ผล |
|---|---:|---:|---|
| `mko.crawl_decisions` | **0** | **0** | คงเป็น 0 |
| `public.courses` | 24 | **24** | คงเดิม |
| `public.course_documents` | 31 | **31** | คงเดิม |
| `public.course_chunks` | 9039 | **9039** | คงเดิม |
| `mko.crawl_sources` | 12 | **12** | คงเดิม |
| status `unchanged` / `needs_review` / `staging_path` ไม่ null | 12 / 6 / 0 | 12 / 6 / 0 | คงเดิม |
| embedding dimension | 1024 | **1024** | คงเดิม |
| `mko.v_crawl_queue` | 6 | **6** | คงเดิม |
| `mko.schema_migrations` | 001–004 | 001–004 | คงเดิม |
| `public.chat_messages` | 6640 | **6640** | คงเดิม |
| `public.chat_answer_cache` | 160 | **160** | คงเดิม |
| `staging/crawl` | 0 รายการ | **0 รายการ** | คงเดิม |

---

## 7. Production mutation ทั้งหมด

| # | เวลา (UTC) | ชั้น | before | after | affected | rollback |
|---|---|---|---|---|---|---|
| 1 | 2026-09-29 08:50:54 | `public.users` แถวเดียว | `is_admin = false` · `updated_at = 2026-09-29 14:53:16.777237+07` | `is_admin = true` · `updated_at = 2026-09-29 15:50:54.925933+07` | **1 แถว · 1 คอลัมน์** (+ `updated_at` จาก trigger `trg_users_updated_at` ตาม schema) | ข้อ 14 |

**ไม่มี mutation อื่นเลย** · การดำเนินการอื่นทั้งหมดในรอบนี้เป็นการอ่าน:
`docker inspect`, `docker exec` ที่รัน `psql` ใน `BEGIN TRANSACTION READ ONLY`,
`docker logs`, `sha256sum`, `ls`, และ `curl` แบบ GET ที่ไม่ส่ง credential

### ไฟล์ที่เพิ่มบนเซิร์ฟเวอร์

`/home/ubuntu/promote_tester_admin_20260929.sql` — สคริปต์ที่รันจริง เก็บไว้เป็นหลักฐาน
(ไม่มีค่าลับในไฟล์นี้) ลบได้ด้วย `rm` ถ้าไม่ต้องการเก็บ

---

## 8. สภาพบริการและคอนเทนเนอร์ ก่อน / หลัง

| service | container ก่อน → หลัง | image | restarts ก่อน → หลัง | StartedAt |
|---|---|---|---|---|
| backend | `fda31caa20c4` → `fda31caa20c4` | `4a45677ec010` ไม่เปลี่ยน | 0 → **0** | 2026-09-29T01:06:17.872Z ไม่เปลี่ยน |
| frontend | `2886c1bf9183` → `2886c1bf9183` | `591ab6d935bb` ไม่เปลี่ยน | 0 → **0** | 2026-09-29T01:07:21.190Z ไม่เปลี่ยน |
| caddy | `a2957d7b8fc3` → `a2957d7b8fc3` | ไม่เปลี่ยน | 0 → **0** | 2026-09-22T21:23:48.949Z ไม่เปลี่ยน |
| postgres | `e8c091a4fc60` → `e8c091a4fc60` | ไม่เปลี่ยน | 0 → **0** | 2026-08-18T14:17:25.705Z ไม่เปลี่ยน |
| ollama | `e6ac0350c722` → `e6ac0350c722` | ไม่เปลี่ยน | 0 → **0** | 2026-08-18T14:17:25.705Z ไม่เปลี่ยน |
| webapi | `6a73308d4f39` → `6a73308d4f39` | ไม่เปลี่ยน | 0 → **0** | 2026-09-22T21:21:35.624Z ไม่เปลี่ยน |

## 9. Restart

**ไม่ได้ restart อะไรเลย** — ไม่ restart backend, frontend, Caddy, PostgreSQL, Ollama, webapi

หลักฐานสองชั้น: (ก) container ID และ StartedAt ของทั้งหกบริการเท่าเดิมทุกค่า
(RestartCount = 0 อย่างเดียวไม่พอ เพราะการแทนที่คอนเทนเนอร์ก็ทำให้ตัวนับเริ่มใหม่)
(ข) จากโค้ดในอิมเมจที่รันอยู่ `get_current_user` โหลดแถวผู้ใช้จากฐานข้อมูล**ทุกคำขอ**
และ token ไม่บรรจุ role claim → สิทธิ์ใหม่มีผลทันทีโดยไม่ต้อง restart
และไม่ต้องให้เจ้าของ login ใหม่ด้วยซ้ำ (token เดิมที่ได้ตอนสมัครยังใช้ได้)

---

## 10. Authenticated verification

### **HUMAN ACTION REQUIRED**

ผมไม่มี credential ของ `Tester@gmail.com` และ**ไม่ได้พยายาม login แทนเจ้าของ**

**ไม่ได้ขอรหัสผ่าน · ไม่ได้อ่าน `password_hash` · ไม่ได้รีเซ็ตรหัสผ่าน ·
ไม่ได้สร้าง token ปลอม · ไม่ได้สร้าง session แทนเจ้าของ · ไม่ได้ bypass authentication**

### สิ่งที่ยืนยันได้จาก server-side โดยไม่ต้องใช้ credential — **PASS**

| ข้อตรวจ | ผล |
|---|---|
| บัญชี active | **true** (จากฐานข้อมูล) |
| บัญชีเป็น admin | **true** (จากฐานข้อมูล) |
| `require_admin` อ่าน `public.users.is_admin` ทุกคำขอ | ยืนยันจากโค้ดในอิมเมจที่ให้บริการอยู่ |
| ไม่ต้อง restart | ยืนยันจากโค้ด + สภาพคอนเทนเนอร์ |
| anonymous ถูกปฏิเสธบนทั้งสาม GET | **401 `missing bearer token`** ทั้งสามเส้นทาง ผ่าน HTTPS |
| token ที่ไม่ถูกต้องถูกปฏิเสธ | `Authorization: Bearer not-a-jwt` → **401 `invalid token`** (ส่งสตริงที่ไม่ใช่ JWT ไม่ได้สร้าง token ที่ลงนามได้) |

### หลักฐานจาก log ว่ายังไม่มีการเข้าถึงแบบ authenticated

```
คำขอ /crawl-review ใน log ของ backend ทั้งหมด : 11 ครั้ง
   เป็น 401 : 11        เป็น 403 : 0        เป็น 200 : 0
```

ทั้ง 11 ครั้งคือการตรวจแบบ anonymous ของผมข้ามรอบ → **ไม่มีการเข้าถึงด้วย token ใดเลย**
สอดคล้องกับที่ผมไม่ได้ login

### non-admin 403 — **NOT TESTED**

ไม่มี session ของผู้ใช้ non-admin ที่เข้าถึงได้อย่างปลอดภัย และ**ไม่สร้างบัญชีหรือ session
ขึ้นเพื่อทดสอบ** (ตอนนี้บัญชีที่ไม่ใช่ admin มี 197 บัญชี แต่ผมไม่มี credential ของใคร)

### ขั้นตอนที่เจ้าของทำเองได้อย่างปลอดภัย (เจ้าของกรอกรหัสผ่านเอง)

**วิธี 1 (แนะนำ) — SSH tunnel แล้วใช้หน้า `/crawl-review` จริง**

มีช่องกรอกรหัสผ่านจริง ทั้งเส้นทางเข้ารหัสด้วย SSH และเมื่อ login สำเร็จหน้าเว็บจะ
เรียก `GET /crawl-review/pending` ให้เองแล้วแสดงคิว

```bash
ssh -i ~/.ssh/oci.key -N -L 127.0.0.1:8080:127.0.0.1:80 ubuntu@161.118.237.37
```

แล้วเปิด `http://127.0.0.1:8080/crawl-review` → กรอกอีเมล `Tester@gmail.com`
และรหัสผ่านของตัวเอง → ควรเห็น **คิว 6 รายการ**

**ห้ามกดปุ่ม "อนุมัติ" / "ไม่เกี่ยวข้อง" / "ถอนการตัดสินใจล่าสุด" และห้ามยืนยันในกล่อง dialog**
— การกดจะสร้างแถวใน `mko.crawl_decisions` ซึ่งยังไม่ได้รับอนุมัติ

**วิธี 2 — ผ่าน console บนโดเมน HTTPS (GET เท่านั้น)**

เปิด `https://stpnru-advisor.duckdns.org/` → DevTools → Console → วาง

```js
await (async () => {
  const password = prompt("รหัสผ่านของ Tester@gmail.com");
  const lr = await fetch("/api/auth/login", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: "Tester@gmail.com", password }),
  });
  if (!lr.ok) return console.log("login ไม่ผ่าน:", lr.status, await lr.text());
  const { access_token: t } = await lr.json();
  const H = { Authorization: "Bearer " + t };

  const p = await fetch("/api/crawl-review/pending", { headers: H });
  const page = await p.json();
  console.log("pending ->", p.status, "จำนวนรายการ:", page.items?.length, "counts:", page.counts);

  const id = page.items?.[0]?.id;
  if (id) {
    const d = await fetch("/api/crawl-review/" + id, { headers: H });
    console.log("detail ->", d.status);
    const f = await fetch("/api/crawl-review/" + id + "/pdf", { headers: H });
    console.log("pdf ->", f.status, "(คาดว่า 404 เพราะ staging ว่าง = fail closed ตามที่ควร)");
  }
})();
```

แล้วแจ้งผลเป็นตัวเลข status และจำนวนรายการกลับมา — **ไม่ต้องส่งรหัสผ่านหรือ token มาให้ผม**

---

## 11. Crawl-review GET verification

### **HUMAN ACTION REQUIRED — ยังไม่ได้ทำ**

PHASE 5 ระบุว่าทำได้เฉพาะเมื่อมี authenticated admin token ที่ได้จากการ login ปกติ
โดยเจ้าของอย่างปลอดภัย ซึ่งยังไม่มี จึงยังไม่ได้เรียกสามเส้นทางนั้นด้วย token ใด

ค่าที่คาดไว้เมื่อเจ้าของทดสอบ (อ้างจากฐานข้อมูลที่ตรวจแล้ว)

| endpoint | คาดว่า | เหตุผล |
|---|---|---|
| `GET /api/crawl-review/pending` | **200** และคืน **6 รายการ** | `mko.v_crawl_queue` มี 6 แถว (แหล่งที่ `needs_review = true` และยังไม่มีการตัดสินใจ) |
| `GET /api/crawl-review/{id}` | **200** อ่านรายละเอียดได้ | แถวมีอยู่จริงในคิว |
| `GET /api/crawl-review/{id}/pdf` | **404** | `staging/crawl` ว่างและ `staging_path` เป็น null ทั้ง 12 แถว → `staging_store` ล้มแบบปิดประตู **นี่คือพฤติกรรมที่ถูกต้อง ไม่ใช่ข้อผิดพลาด** และไม่ใช่การพิสูจน์ว่าแสดง PDF ของ candidate ได้ |

การตรวจแบบ isolated ของด่าน fail-closed ผ่าน **9/9** แล้วในรายงาน Step 3 (resume)
ครอบคลุมกรณีไฟล์ไม่มี, path หลุด root, traversal `..`, sha ไม่ตรง, ไม่ใช่ PDF และ env ว่าง

---

## 12. `mko.crawl_decisions`

| จุดเวลา | ค่า |
|---|---:|
| ก่อน promote (08:49Z) | **0** |
| ภายใน transaction ก่อน COMMIT | **0** (assertion ผ่าน) |
| หลัง COMMIT (08:51Z) | **0** |
| หลังตรวจ anonymous guard (08:53Z) | **0** |

**ยังเป็น 0 ทุกจุดเวลา** — ไม่มี decision ใดถูกสร้าง

---

## 13. สิ่งที่ไม่ได้ทำ

- **ไม่ได้ POST approve / ignore / undo** แม้ครั้งเดียว และไม่ได้ทดสอบ route ที่เปลี่ยนสภาพ
  แม้จะคาดว่าถูกปฏิเสธ
- ไม่ได้ ingestion · ไม่ได้รัน worker · ไม่ได้รัน crawler · ไม่ได้สร้าง embedding ของเอกสาร ·
  ไม่ได้สร้าง candidate ปลอม · ไม่ได้แก้ `mko.crawl_sources` หรือ status/hash/staging path
- ไม่ได้รัน RAG/chat test (ยืนยันด้วย log: คำขอ `/chat` = **0 ครั้ง** และ
  `chat_messages`/`chat_answer_cache` คงที่ 6640/160)
- ไม่ได้แก้ Supabase · ไม่ได้แก้ Supabase user/profile · ไม่ได้ migrate Supabase user ·
  ไม่ได้รวม auth · ไม่ได้ทำ SSO · ไม่ได้ทำ identity mapping · ไม่ได้แก้สถาปัตยกรรม JWT
- ไม่ได้แก้ Caddy (sha256 เดิม `da2e26fd…`) · ไม่ได้ deploy · ไม่ได้ migration ·
  ไม่ได้ commit/push · ไม่ได้ merge main
- ไม่ได้ restart บริการใด · ไม่ได้เปลี่ยน production config · ไม่ได้เปิดพอร์ตหรือ listener ใด
- ไม่ได้แก้ `courses` / `course_documents` / `course_chunks` / RAG / pgvector
- ไม่ได้แตะบัญชีอื่น · ไม่ได้เปลี่ยนรหัสผ่าน, อีเมล, `is_active`, profile หรือ role ของใคร
- ไม่ได้อ่าน `password_hash` · ไม่ได้ขอรหัสผ่าน · ไม่ได้แสดงค่าลับใด ·
  ไม่ได้พิมพ์ UUID ของบัญชีเป้าหมายลงรายงาน

### กิจกรรม embedding ที่สังเกตได้ — บันทึกแยกตามความจริง

```
เรียก ollama /api/embeddings ตั้งแต่ cutover : 24 ครั้ง
คำขอ /chat ที่เข้าถึง backend               : 0 ครั้ง
backend uptime ณ เวลาตรวจ                   : 465 นาที
คาดจาก warmup: 1 (ตอนเริ่ม) + floor(465/20) = 1 + 23 = 24 ครั้ง  -> ตรงพอดี
```

ทั้งหมดมาจาก `_keep_models_warm()` ที่ [backend/app/main.py:68](backend/app/main.py:68)
ซึ่ง embed สตริง `"warmup"` ทุก 20 นาที เป็นพฤติกรรมเดิมของบริการ
**ผมไม่ได้กระตุ้น warmup และไม่ได้ปิดหรือแก้ค่า config ของมัน**
ไม่ใช่ document ingestion — ยืนยันด้วย `course_chunks = 9039` ที่ไม่ขยับ
**ไม่อ้างว่า "ไม่มี embedding เกิดขึ้นเลย"**

---

## 14. Rollback — ลดสิทธิ์ `is_admin: true → false` ของบัญชีเดียวกัน

**ยังไม่ได้รัน และห้ามรันเพื่อทดสอบ** ใช้เฉพาะเมื่อจำเป็นต้องถอนสิทธิ์จริง
**ไม่ใช่การลดสิทธิ์เป็นชุด ไม่ลบผู้ใช้ ไม่รีเซ็ตรหัสผ่าน ไม่ restore ฐานข้อมูล
ไม่ย้อน migration และไม่ rollback บริการ**

```sql
BEGIN;
SET LOCAL lock_timeout = '3s';
SET LOCAL statement_timeout = '30s';
LOCK TABLE public.users IN SHARE ROW EXCLUSIVE MODE;

DO $$
DECLARE
    n_all int; n_ok int; n_users int; n_active int; n_admin_before int; n_admin_after int;
    n_rows int; tgt uuid; v_active boolean; v_admin boolean;
BEGIN
    SELECT count(*) INTO n_all FROM public.users WHERE email = 'Tester@gmail.com';
    IF n_all <> 1 THEN RAISE EXCEPTION 'หยุด: พบ % บัญชีที่ตรงอีเมล ต้องได้ 1 พอดี', n_all; END IF;

    SELECT count(*) INTO n_ok FROM public.users
      WHERE email = 'Tester@gmail.com' AND is_active AND is_admin;
    IF n_ok <> 1 THEN RAISE EXCEPTION 'หยุด: บัญชีนั้นไม่ได้เป็น admin ที่ active อยู่'; END IF;

    SELECT id INTO tgt FROM public.users
      WHERE email = 'Tester@gmail.com' AND is_active AND is_admin FOR UPDATE;
    IF tgt IS NULL THEN RAISE EXCEPTION 'หยุด: ตรึงแถวเป้าหมายไม่ได้'; END IF;

    -- ค่า aggregate ต้องวัดจริงก่อนใช้ ถ้ามีผู้ใช้สมัครเพิ่มให้เปลี่ยน 198 เป็นค่าที่วัดได้
    SELECT count(*), count(*) FILTER (WHERE is_active), count(*) FILTER (WHERE is_admin)
      INTO n_users, n_active, n_admin_before FROM public.users;
    IF (n_users, n_active, n_admin_before) <> (198, 198, 1) THEN
        RAISE EXCEPTION 'หยุด: ก่อนถอนสิทธิ์ต้องเป็น 198/198/1 (ได้ %/%/%)',
            n_users, n_active, n_admin_before; END IF;

    IF (SELECT count(*) FROM mko.crawl_decisions) <> 0 THEN
        RAISE EXCEPTION 'หยุด: mko.crawl_decisions ไม่เป็น 0 — ต้องให้คนตรวจก่อน'; END IF;
    IF (SELECT count(*) FROM public.courses)          <> 24
       OR (SELECT count(*) FROM public.course_documents) <> 31
       OR (SELECT count(*) FROM public.course_chunks)    <> 9039
       OR (SELECT count(*) FROM mko.crawl_sources)       <> 12 THEN
        RAISE EXCEPTION 'หยุด: invariants ของหลักสูตร/crawler เปลี่ยน'; END IF;

    UPDATE public.users
       SET is_admin = FALSE
     WHERE id = tgt AND email = 'Tester@gmail.com' AND is_active AND is_admin = TRUE;
    GET DIAGNOSTICS n_rows = ROW_COUNT;
    RAISE NOTICE 'affected rows = %', n_rows;
    IF n_rows <> 1 THEN RAISE EXCEPTION 'หยุด: affected rows = % ต้องเป็น 1 พอดี', n_rows; END IF;

    SELECT is_active, is_admin INTO v_active, v_admin FROM public.users WHERE id = tgt;
    IF NOT v_active OR v_admin THEN
        RAISE EXCEPTION 'หยุด: เป้าหมายต้อง active และไม่ใช่ admin (active=% admin=%)', v_active, v_admin; END IF;

    SELECT count(*), count(*) FILTER (WHERE is_active), count(*) FILTER (WHERE is_admin)
      INTO n_users, n_active, n_admin_after FROM public.users;
    IF (n_users, n_active, n_admin_after) <> (198, 198, n_admin_before - 1) THEN
        RAISE EXCEPTION 'หยุด: หลังถอนสิทธิ์ต้องเป็น 198/198/% (ได้ %/%/%)',
            n_admin_before - 1, n_users, n_active, n_admin_after; END IF;
    RAISE NOTICE 'หลังถอนสิทธิ์: users=% active=% admins=%', n_users, n_active, n_admin_after;
END $$;

COMMIT;
```

ตรวจหลังรัน (read-only transaction แยก)

```sql
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout = 10000;
SELECT count(*) FROM public.users WHERE email = 'Tester@gmail.com' AND is_active AND NOT is_admin;  -- ต้องได้ 1
SELECT count(*) FILTER (WHERE is_admin) FROM public.users;                                          -- ต้องได้ 0
SELECT count(*) FROM mko.crawl_decisions;                                                           -- ต้องได้ 0
COMMIT;
```

**ไม่ต้อง restart หลัง rollback** ด้วยเหตุผลเดียวกับข้อ 9
**ไม่ต้องใช้ UUID ของบัญชีในคำสั่ง** — ระบุด้วยอีเมลที่อนุมัติร่วมกับเงื่อนไขสภาพ
และบังคับ cardinality = 1 ซึ่งรับประกันได้เพราะ `email` เป็น `citext` ที่มี unique index
รายงานนี้จึงไม่มี internal ID ใดที่ต้อง redact

---

## 15. GO / NO-GO สำหรับขั้นถัดไป

| เรื่อง | คำตัดสิน | เหตุผล |
|---|---|---|
| **admin promotion** | **เสร็จแล้ว — PASS** | affected rows = 1 · 198/198/1 · invariants ครบ · ไม่มี restart |
| **authenticated login + crawl-review GET test** | **HUMAN ACTION REQUIRED** | ผมไม่มี credential · ขั้นตอนที่ปลอดภัยอยู่ในข้อ 10 · เจ้าของกรอกรหัสผ่านเอง |
| **non-admin 403 test** | **NOT TESTED** | ไม่มี session non-admin ที่ปลอดภัย · ไม่สร้างบัญชีเพื่อทดสอบ |
| **future controlled one-job ingestion** | **NO-GO** | ดูข้างล่าง |
| **Step 4 / E2E ingestion** | **ไม่เริ่ม** | ไม่ได้รับอนุมัติ |

### ทำไม one-job ingestion ยัง NO-GO

**การเป็น admin สำเร็จไม่ได้แปลว่าอนุญาตให้รัน ingestion** — สองเรื่องนี้แยกกัน

Blocker ที่ยังเหลือคือ **ไม่มี legitimate candidate**

```
mko.crawl_sources           : 12 แถว · สถานะ unchanged ทั้ง 12
staging_path ไม่เป็น null     : 0 แถว
staging/crawl               : 0 รายการ
mko.crawl_decisions         : 0
```

**คำเตือนที่ต้องย้ำ: 6 รายการในคิว (`v_crawl_queue`) ไม่ใช่ 6 candidate ที่นำเข้าได้**
แถวเหล่านั้นถูกตั้งธง `needs_review` เพราะการจับคู่หลักสูตรยังไม่ชัด **ไม่ใช่เพราะมีไฟล์ใหม่**
ทั้ง 6 แถวมีสถานะ `unchanged` และไม่มีไฟล์ใน staging จึงยังไม่มีอะไรให้ worker ทำ

candidate ที่ถูกต้องต้องเป็นไฟล์ใหม่หรือไฟล์ที่เปลี่ยนจริงจากต้นทาง `sci.pnru.ac.th`
พร้อม staged PDF และ hash ที่ตรวจได้ — **ห้ามสร้าง ห้ามปลอม และห้ามรัน crawler เพื่อให้เกิด**

### สิ่งที่พร้อมแล้วและไม่ใช่เหตุปิดกั้นอีกต่อไป

migration 004 · backend Phase 3A · frontend Phase 3B · staging mount read-only ·
anonymous guard 401 ทั้งสาม route · หน้า Next.js เป็น route จริง ·
**บัญชี admin หนึ่งบัญชี** · worker image และ config พร้อม (คง PREPARED ไม่ถูกรัน) ·
backup และ rollback ครบทุกชั้น

### ขั้นถัดไปที่เจ้าของทำได้ทันที

ทำตามข้อ 10 วิธี 1 หรือวิธี 2 เพื่อ login และเรียกสาม GET แล้วแจ้งผลเป็นตัวเลขกลับมา
**ห้ามกด approve / ignore / undo** · ถ้าผลตรงตามที่คาด (pending 200 + 6 รายการ,
detail 200, pdf 404) ก็ถือว่า Phase 3D Step 3.5 เสร็จสมบูรณ์
โดยที่ `mko.crawl_decisions` ต้องยังเป็น 0

---

---

## 20. Authenticated verification — เสร็จแล้ว (เจ้าของโปรเจกต์ทำเอง)

**อัปเดต 2026-09-29 ราว 12:00Z (ไทย 19:00)** · ข้อ 10 และ 11 ข้างบนเขียนไว้ตอนที่ยัง
ทดสอบไม่ได้ ส่วนนี้คือผลจริงที่เกิดขึ้นหลังจากนั้น

### 20.1 ลำดับเหตุการณ์

เจ้าของลืมรหัสผ่านที่เพิ่งตั้ง จึงทำ password recovery ก่อน (ดู
`ADMIN_PASSWORD_RECOVERY_PLAN.md`) โดยเจ้าของเป็นผู้กำหนดรหัสใหม่เอง
ผมไม่เห็นและไม่รับรหัสผ่าน แล้วจึงทดสอบ authenticated ต่อ

### 20.2 Login — PASS

```
POST /auth/login  ->  401 Unauthorized   (พิมพ์รหัสไม่ตรงครั้งแรก)
POST /auth/login  ->  401 Unauthorized
POST /auth/login  ->  200 OK             <- สำเร็จ
```

เรียกผ่าน HTTPS ที่ `https://stpnru-advisor.duckdns.org/api/auth/login`
เจ้าของกรอกรหัสผ่านเองผ่าน `prompt()` · **ไม่มีรหัสผ่านหรือ token ส่งมาให้ผม**

ยืนยันว่า login ไม่ได้เขียนอะไร: `users` 198/198/1 เท่าเดิม ·
`updated_at` ของบัญชียังเป็น `2026-09-29 18:43:28.888899+07` (เวลาที่ reset) ·
`chat_messages`/`chat_answer_cache` = 6640/160 ไม่ขยับ

### 20.3 Crawl-review GET — PASS ทั้งสามเส้นทาง

| endpoint | คาด | ผลจริง | ผล |
|---|---|---|---|
| `GET /api/crawl-review/pending` | 200 · 6 รายการ | **200** · `items.length = 6` · `counts = {total: 6, needs_review: 6, ambiguous: 6, with_staged_file: 0}` | **PASS** |
| `GET /api/crawl-review/{id}` | 200 | **200** | **PASS** |
| `GET /api/crawl-review/{id}/pdf` | 404 (fail closed) | **404 Not Found** | **PASS — พฤติกรรมที่ถูกต้อง** |

`with_staged_file: 0` จากคำตอบของ API ตรงกับฐานข้อมูลที่ `staging_path` เป็น null ทั้ง 12 แถว
และ `staging/crawl` ว่าง → 404 ของ endpoint PDF คือการปฏิเสธอย่างปลอดภัยเมื่อไม่มีไฟล์
**ไม่ใช่ข้อผิดพลาด และไม่ใช่การพิสูจน์ว่าแสดง PDF ของ candidate ได้**

### 20.4 หลักฐานจาก log ของ backend

```
คำขอ /crawl-review ทั้งหมด : 14 ครั้ง
   200 = 2      (pending + detail ด้วย token ของ admin)
   404 = 1      (pdf — fail closed)
   401 = 11     (การตรวจแบบ anonymous ของผมข้ามรอบ)
   403 = 0
POST /crawl-review/{id}/(approve|ignore|undo) : 0 ครั้ง
```

จำนวน 200 ที่เพิ่มจาก 0 เป็น 2 คือหลักฐานว่า **`require_admin` ผ่านจริงด้วยบัญชีนี้**
และยืนยันซ้ำว่าการ promote มีผลโดยไม่ต้อง restart

### 20.5 Invariants หลังการทดสอบ — ไม่ขยับ

| รายการ | ค่า |
|---|---:|
| `mko.crawl_decisions` | **0** |
| `users` / `active` / `admins` | 198 / 198 / 1 |
| `updated_at` ของบัญชีเป้าหมาย | `2026-09-29 18:43:28.888899+07` (ไม่เปลี่ยนจากตอน reset) |
| `crawl_sources` | 12 · unchanged 12 · needs_review 6 · staging_path ไม่ null 0 |
| `mko.v_crawl_queue` | 6 |
| `courses` / `course_documents` / `course_chunks` | 24 / 31 / 9039 |
| `chat_messages` / `chat_answer_cache` | 6640 / 160 |
| `staging/crawl` | 0 รายการ |

บริการทั้งหก container ID และ StartedAt เท่าเดิม · **ไม่มี restart ตลอดทั้งกระบวนการ**

### 20.6 รายการที่ยังไม่ได้ทดสอบ

| รายการ | สถานะ | เหตุผล |
|---|---|---|
| non-admin 403 | **NOT TESTED** | ไม่มี session ของผู้ใช้ non-admin ที่เข้าถึงได้อย่างปลอดภัย และไม่สร้างบัญชี/session ขึ้นเพื่อทดสอบ |
| หน้า `/crawl-review` ที่ render จริงใน UI | **NOT TESTED** | ทดสอบผ่าน API โดยตรงแทน ซึ่งครอบคลุมสัญญาเดียวกับที่หน้าเว็บเรียก |
| หน้า `/crawl-review` บนโดเมน HTTPS | **การตัดสินใจแยก** | โดเมนเสิร์ฟ SPA จาก `/srv/web` · ไม่แก้ Caddy |

### 20.7 สรุปสถานะ Phase 3D Step 3.5

**เสร็จสมบูรณ์** — migration 004 · backend Phase 3A · frontend Phase 3B ·
staging mount read-only · บัญชี admin หนึ่งบัญชีที่ login ได้จริง ·
API ของ `/crawl-review` ตอบถูกต้องทั้ง authenticated และ anonymous ·
`mko.crawl_decisions` ยังเป็น **0**

**GO/NO-GO สำหรับ future controlled one-job ingestion: ยัง NO-GO**
blocker ที่เหลือมีข้อเดียวคือ **ไม่มี legitimate candidate** — `crawl_sources`
ทั้ง 12 แถวเป็น `unchanged` · `staging_path` null ทั้งหมด · staging ว่าง ·
และคำตอบของ API เองก็ยืนยันด้วย `with_staged_file: 0`

ย้ำอีกครั้ง: **6 รายการในคิวไม่ใช่ 6 candidate ที่นำเข้าได้** — ถูกตั้งธง `needs_review`
เพราะการจับคู่หลักสูตรยังไม่ชัด (`ambiguous: 6`) ไม่ใช่เพราะมีไฟล์ใหม่

---

## STOP

ห้ามเริ่ม Step 4 · ห้าม ingestion · ห้าม worker

STOP
