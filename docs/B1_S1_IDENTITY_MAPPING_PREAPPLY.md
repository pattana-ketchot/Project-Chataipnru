# B1 — S1 Identity Mapping · Production Pre-Apply

| | |
|---|---|
| ตรวจครั้งแรก | 2026-10-03 19:43:35 +07 |
| **ตรวจซ้ำล่าสุด** | **2026-10-03 20:17:36 +07** — ผลเหมือนเดิมทุกข้อ |
| **Classification** | **`S1_MAPPING_PREAPPLY_READY`** |
| ฝั่ง PostgreSQL | **ตรวจครบ 21 ข้อ ผ่านทั้งหมด สองครั้ง** — เป้าหมายชัดเจน **แถวเดียว** |
| ฝั่ง Supabase | **ยืนยันแล้ว** — **เจ้าของเป็นผู้รันและรายงานผล** ไม่ใช่ผมสังเกตเอง (ข้อ 1) |
| UUID ของ S1 | **เจ้าของถือไว้** — ส่งเข้าทาง `psql -v` ตอน apply · **ไม่อยู่ในเอกสารนี้** |
| คำสั่ง UPDATE | **ออกแบบและทดสอบแล้ว 3 เส้นทาง** · **ยังไม่รัน** |
| Rollback | **ออกแบบและทดสอบแล้ว 3 เส้นทาง** · **ยังไม่รัน** |

```
UPDATE public.users        NONE     INSERT/DELETE production   NONE
เติม supabase_user_id จริง  NONE     Supabase Write             NONE
ALTER / GRANT / REVOKE     NONE     แก้ production .env         NONE
แก้ webapi                 NONE     แก้ frontend                NONE
Deploy / Restart           NONE     Commit / Push / Merge      NONE
```

**ไม่มี email จริง ไม่มี Supabase UUID ไม่มี connection string ในเอกสารนี้**

---

## 1. สถานะของสิ่งที่เคยเป็นตัวขวาง — ปิดแล้วทั้งสองข้อ

ฉบับก่อนหน้าของเอกสารนี้จัดเป็น **`S1_MAPPING_BLOCKED`** ด้วยเหตุสองข้อ · ปิดแล้วทั้งคู่

### 1.1 ⚠ ยืนยันฝั่ง Supabase — **เจ้าของเป็นผู้รันและรายงานผล**

| | |
|---|---|
| ใครรัน | **เจ้าของ** ผ่าน **Supabase SQL Editor** |
| ผมสังเกตผลเองไหม | **ไม่** — ผมไม่มีช่องทางเข้าถึง Supabase ใน session นี้ |
| วันที่ | 2026-10-03 |

ผลที่เจ้าของรายงาน

| ฟิลด์ | ที่รายงาน | ที่ต้องเป็น | ผล |
|---|---|---|---|
| จำนวนแถวที่ได้ | **1** | 1 | ✅ |
| `role` | **`admin`** | admin | ✅ |
| `status` | **`approved`** | approved | ✅ |
| `email_hash_prefix` | **`66067ef9e155`** | `66067ef9e155` | ✅ |
| ได้ `supabase_user_id` แล้ว | **ใช่** — จาก query ที่กรองด้วย full hash ของ S1 | — | ✅ |

**ตรงครบทั้งสี่ข้อกับที่หลักฐานเดิมบันทึกไว้** → ไม่มีสัญญาณว่าตัวตนเปลี่ยน
จึงไม่เข้าเงื่อนไข `S1_IDENTITY_CHANGED`

> **ข้อสำคัญที่สุด**: เจ้าของอ่าน UUID มาจาก **query ที่กรองด้วย full hash ของ S1 เอง**
> ไม่ใช่คัดลอกจากหน้าจอ Dashboard → **ปิดความเสี่ยงข้อ 8.1** ที่ว่า "UUID ที่กรอกมา
> อาจเป็นของ account อื่น" เพราะ query รับประกันว่า UUID นั้นมาจาก account
> ที่ hash ตรงกับ S1 จริง

### 1.2 ⚠ ขอบเขตของคำว่า "ยืนยันแล้ว" — ต้องพูดให้ตรง

| ยืนยันโดย | สิ่งที่ยืนยัน |
|---|---|
| **ผมเอง · ตรวจซ้ำได้ตลอด** | ฝั่ง PostgreSQL ทั้ง 21 ข้อ · ท่อ hash สองฝั่งให้ผลเหมือนกัน |
| **เจ้าของรายงาน · ผมไม่ได้สังเกตเอง** | ฝั่ง Supabase ทั้งหมด — จำนวนแถว · `role` · `status` · prefix |

การจัดเป็น `S1_MAPPING_PREAPPLY_READY` **ตั้งอยู่บนรายงานของเจ้าของในส่วนของ Supabase**
ถ้าค่าใดที่รายงานมาคลาดเคลื่อน ข้อสรุปนี้จะคลาดตามไปด้วย · บันทึกไว้ให้ชัดว่าข้อไหน
ตรวจซ้ำได้และข้อไหนตรวจซ้ำไม่ได้ ไม่ใช่เพื่อโยนความรับผิด

### 1.3 UUID ของ S1 — ไม่ใช่ตัวขวางอีกต่อไป

| | |
|---|---|
| ใครถือค่า | **เจ้าของ** |
| อยู่ในเอกสารนี้ไหม | **ไม่** · และไม่ควรอยู่ |
| ส่งเข้าคำสั่งอย่างไร | ทาง `psql -v s1_uuid=…` ตอน apply — **ไม่ฝังในไฟล์ใด** (ข้อ 5.2) |

แบบเดียวกับที่ทำกับ `ADVISOR_WEB_PASSWORD` — ค่าที่ระบุตัวตนเดินทางจากเจ้าของ
เข้าคำสั่งโดยตรง ไม่ผ่านผมและไม่ผ่านไฟล์ที่ commit

### 1.4 ตรวจซ้ำฝั่ง production หลังได้ผลจาก Supabase

รันชุดเดิมอีกครั้งเมื่อ **20:17:36 +07** — **ผลเหมือนเดิมทุกข้อทั้ง 21 ข้อ**
198 แถว · mapping 0 · S1 ตรง 1 แถว · ยังเป็น NULL · index ยัง valid/ready/live

→ สถานะ `READY` เป็นคำกล่าวถึง **ตอนนี้** ไม่ใช่ผลค้างจากเมื่อ 34 นาทีก่อน

## 2. Evidence ที่ใช้ยืนยัน S1

### 2.1 ที่มาของตัวตน S1

| | |
|---|---|
| ที่มาของ hash | **เจ้าของเป็นผู้ให้** (owner-provided SHA-256) บันทึกใน `B2_AUTHOR_IDENTITY_CROSSCHECK.md` ข้อ 2 |
| hash prefix | **`66067ef9e155`** |
| วิธี hash | `sha256(lower(btrim(email)))` คำนวณ **ภายในฐานข้อมูลทั้งสองฝั่ง** |
| ฝั่ง Supabase | `extensions.digest(lower(btrim(email)),'sha256')` |
| ฝั่ง production | `public.digest(lower(btrim(email::text)),'sha256')` |
| ป้ายกำกับ S1/S2 | `row_number() OVER (ORDER BY full_hash)` — **เสถียร ไม่ขึ้นกับลำดับการ query** |

### 2.2 สิ่งที่หลักฐานเดิมบันทึกไว้เกี่ยวกับ S1

| ข้อมูล | หลักฐานเดิม (2026-10-02) | เจ้าของยืนยันซ้ำ (2026-10-03) | ผล |
|---|---|---|---|
| `role` | `admin` | **`admin`** | ✅ ตรง |
| `status` | `approved` | **`approved`** | ✅ ตรง |
| จำนวน account ที่ตรง hash ใน `auth.users` | **1** | **1** | ✅ ตรง |
| `email_hash_prefix` | `66067ef9e155` | **`66067ef9e155`** | ✅ ตรง |
| เป็นผู้เขียน courses/news เดิมไหม | **ไม่ใช่** (ผู้เขียนเดิมคือ S2) | ไม่ได้ตรวจซ้ำ | — |
| จำนวน account ทั้งหมดใน `auth.users` | 3 · hash ต่างกันทั้ง 3 | ไม่ได้ตรวจซ้ำ | — |

**สี่ข้อแรกยืนยันซ้ำแล้วและตรงกันทุกข้อ** — ที่มา: `B1_SUPABASE_IDENTITY_VERIFICATION.md`
และ `B2_AUTHOR_IDENTITY_CROSSCHECK.md` (ทั้งคู่เป็นไฟล์ที่ยังไม่ commit ใน checkout หลัก)

สองข้อท้ายไม่ได้ตรวจซ้ำและ**ไม่จำเป็นต้องตรวจ** สำหรับการ mapping รอบนี้ —
mapping ผูกตัวตน ไม่ได้เปลี่ยนผู้เขียนเดิมของข้อมูลใด

### 2.3 ⚠ การตรวจสอบความถูกต้องของท่อ hash — **ทำได้และผ่าน**

ข้อนี้สำคัญ เพราะถ้าท่อ normalize ของสองฝั่งต่างกัน การเทียบ hash จะไร้ความหมาย

```
hash('  TeSt ')  ฝั่ง production  =  9f86d081…0a08
sha256('test') ที่รู้กันทั่วไป      =  9f86d081…0a08
```

**ตรงกัน** → `lower(btrim(...))` ของฝั่ง production ให้ผลเหมือนกับฝั่ง Supabase
(เอกสารเดิมบันทึกว่าฝั่ง Supabase ผ่าน self-test เดียวกันนี้)

`email` ของ production เป็นชนิด `citext` · การ cast เป็น `text` ก่อน hash
ทำให้ได้ไบต์ชุดเดียวกับฝั่ง Supabase ที่เป็น `varchar`

---

## 3. Local target resolution — ฝั่ง PostgreSQL ผ่านครบ

รันใต้ `PGOPTIONS='-c default_transaction_read_only=on'` · SQL เป็น `SELECT` ล้วน
**ไม่มีการ SELECT email ออกมา** — hash คำนวณในฐานข้อมูลแล้วเทียบในฐานข้อมูล

| # | ข้อตรวจ | ได้ | คาดหวัง | ผล |
|---|---|---|---|---|
| P01 | **self-test ของท่อ hash** | `9f86d081…0a08` | sha256 ของ `test` | ✅ |
| P02 | จำนวนแถว `public.users` | **198** | 198 | ✅ |
| P03 | `supabase_user_id` ที่ไม่ใช่ NULL | **0** | 0 | ✅ |
| P04 | **hash อีเมลที่ไม่ซ้ำกัน** | **198** | 198 | ✅ **ไม่มีอีเมลซ้ำหลัง normalize** |
| P05 | **แถวที่ตรง hash ของ S1** | **1** | **1** | ✅ **แถวเดียวพอดี** |
| P06 | แถวนั้น `is_admin` | **true** | true | ✅ |
| P07 | แถวนั้น `is_active` | **true** | true | ✅ |
| P08 | แถวนั้น `supabase_user_id IS NULL` | **true** | true | ✅ |
| P09 | id ของแถวนั้น (prefix) | **`4ad26503`** | บันทึกเป็นหลักฐาน | — |
| P10 | จำนวน admin ทั้งตาราง | **1** | 1 | ✅ |
| P11 | **แถวของ S1 คือ admin คนนั้น** | **true** | true | ✅ |

### 3.1 P04 สำคัญกว่าที่เห็น

**198 แถว → 198 hash ที่ไม่ซ้ำกัน** แปลว่าไม่มีอีเมลสองอันที่ normalize แล้วชนกัน
ถ้ามีการชน การจับคู่ด้วย hash จะได้มากกว่า 1 แถวและต้อง BLOCK ทันที

### 3.2 P12 — S2 ไม่มีคู่ฝั่ง PostgreSQL

```
แถวที่ตรง hash ของ S2 (716e6e356eae…)  =  0
```

สอดคล้องกับการตัดสินใจเดิมของเจ้าของว่า **ไม่ provision ผู้ใช้ให้ S2**
และยืนยันว่า S2 ไม่ได้แอบมีคู่อยู่แล้วโดยไม่มีใครรู้

### 3.3 เงื่อนไข BLOCK ทั้งสี่ข้อ — ไม่มีข้อใดเกิดขึ้นฝั่ง PostgreSQL

| เงื่อนไข BLOCK ที่สั่งไว้ | สถานะจริง |
|---|---|
| 0 matches | **ไม่** — ได้ 1 |
| > 1 matches | **ไม่** — ได้ 1 |
| identity evidence เปลี่ยน | **ไม่พบว่าเปลี่ยน** — hash เดิมยังจับคู่ได้เหมือนเดิม |
| S1 ไม่ active / ไม่ authorized | **ฝั่ง PostgreSQL ยัง active และเป็น admin** · **ฝั่ง Supabase ยืนยันไม่ได้** ← นี่คือข้อที่ block |

---

## 4. Collision checks

| # | ข้อตรวจ | ได้ | ผล |
|---|---|---|---|
| 1 | **UUID ของ S1 ถูกใช้ไปแล้วหรือยัง** | ทั้งตารางมี `supabase_user_id` ที่ไม่ใช่ NULL = **0 แถว** → **ไม่มีใครถืออยู่ ไม่ว่า UUID ใด** | ✅ |
| 2 | แถวเป้าหมายยังเป็น NULL | **true** | ✅ |
| 3 | มี local user อื่น claim UUID ของ S1 ไหม | **ไม่มี** — ครอบคลุมด้วยข้อ 1 | ✅ |
| 4 | partial unique index มีอยู่ | **1** | ✅ |
| 5 | **index `indisvalid`** | **true** | ✅ |
| 6 | **index `indisready`** | **true** | ✅ |
| 7 | **index `indislive`** | **true** | ✅ |
| 8 | เป็น unique **และ** partial | **true** | ✅ |
| 9 | ชนิดคอลัมน์ | **`uuid`** | ✅ |
| 10 | ledger มี `006_web_identity_mapping` | **1** | ✅ |

### 4.1 ทำไมตรวจ `indisvalid` / `indisready` / `indislive` ครบสามตัว

index ที่สร้างไม่สำเร็จบางกรณียัง**ปรากฏใน catalog** แต่ **ไม่บังคับความ unique**
ถ้าตรวจแค่ "มีอยู่" แล้วเขียนค่าซ้ำเข้าไป ฐานข้อมูลจะยอมรับโดยไม่เตือน

ทั้งสามเป็น `true` → **ข้อห้ามซ้ำบังคับใช้จริงแล้ว**

### 4.2 ข้อจำกัดที่ต้องพูดให้ตรง

ข้อ 1 และ 3 พิสูจน์ว่า **ยังไม่มีแถวใดในตารางถือค่า `supabase_user_id` ใดเลย**
ซึ่งครอบคลุมกรณี "UUID ของ S1 ถูก claim ไปแล้ว" อย่างสมบูรณ์ **โดยไม่ต้องรู้ค่า UUID**

แต่ถ้าในอนาคตมีการเติม mapping ให้คนอื่นก่อน ต้องตรวจซ้ำด้วยค่า UUID จริง
ซึ่งตอนนั้นจะมีค่าให้ตรวจแล้ว

---

## 5. Exact planned mutation

**ออกแบบและทดสอบแล้ว · ยังไม่รันบน production**

### 5.1 เป้าหมายเชิงตรรกะ

```sql
UPDATE public.users
SET supabase_user_id = <S1_SUPABASE_UUID>
WHERE id = <VERIFIED_LOCAL_USER_ID>
  AND supabase_user_id IS NULL;
```

### 5.2 คำสั่งจริงที่เสนอ — เพิ่มด่านกันพลาดสามชั้น

ค่าทั้งสามส่งเข้าทาง `psql -v` **ไม่มีค่าใดฝังอยู่ในไฟล์**

```sql
BEGIN;

-- ปิดการแสดงผลบรรทัดนี้ เพื่อไม่ให้ UUID และ hash ถูกพิมพ์ออกหน้าจอ
\o /dev/null
SELECT set_config('mapping.s1_uuid',  :'s1_uuid',  true),
       set_config('mapping.local_id', :'local_id', true),
       set_config('mapping.s1_hash',  :'s1_hash',  true);
\o

DO $$
DECLARE
    n integer;
BEGIN
    UPDATE public.users
       SET supabase_user_id = current_setting('mapping.s1_uuid')::uuid
     WHERE id = current_setting('mapping.local_id')::uuid
       AND encode(public.digest(lower(btrim(email::text)), 'sha256'), 'hex')
           = current_setting('mapping.s1_hash')
       AND supabase_user_id IS NULL;

    GET DIAGNOSTICS n = ROW_COUNT;

    IF n <> 1 THEN
        RAISE EXCEPTION 'แก้ไข % แถว แต่ต้องเป็น 1 แถวพอดี — ยกเลิกทั้งหมด', n
            USING HINT = 'ตรวจว่า local_id ถูกต้อง · hash ตรง · และแถวนั้นยังเป็น NULL อยู่';
    END IF;

    RAISE NOTICE 'ผูก supabase_user_id ให้ 1 แถวเรียบร้อย';
END;
$$;

COMMIT;
```

### 5.3 เหตุผลของแต่ละกลไก

| กลไก | ป้องกันอะไร |
|---|---|
| **`id = :local_id`** | เจาะจงแถวเดียว |
| **เงื่อนไข hash** | **ถ้า `local_id` ถูกคัดลอกผิด เงื่อนไขนี้จะไม่ผ่าน → 0 แถว → ยกเลิก** · เป็นด่านที่จับความผิดพลาดจากการคัดลอก |
| **`supabase_user_id IS NULL`** | ไม่ทับค่าที่มีอยู่แล้วของใคร |
| **`GET DIAGNOSTICS` + `RAISE EXCEPTION`** | **บังคับว่าต้องโดน 1 แถวพอดี** · 0 หรือ > 1 → ถอนกลับทั้ง transaction |
| **`set_config(..., true)`** | ค่าเป็น transaction-local หายไปเองเมื่อจบ · **และหลบกับดักที่ psql ไม่แทนค่า `:'var'` ภายใน `$$ … $$`** |
| **`\o /dev/null`** | ไม่ให้ UUID และ hash ถูกพิมพ์ออกหน้าจอ |
| `BEGIN`/`COMMIT` | ล้มที่ใดก็ถอนกลับหมด |

### 5.4 ทดสอบแล้ว 3 เส้นทาง — คอนเทนเนอร์ทิ้ง PostgreSQL 16.15

จำลองตารางที่มีโครงเดียวกัน พร้อม partial unique index เดียวกัน

| # | สถานการณ์ | ผล |
|---|---|---|
| T1 | ค่าถูกต้องทั้งสาม | ✅ **`NOTICE: ผูก … 1 แถวเรียบร้อย` · `COMMIT` · exit 0** |
| T2 | **รันซ้ำ** (แถวนั้นไม่เป็น NULL แล้ว) | ✅ **`ERROR: แก้ไข 0 แถว …` · exit 3 · ไม่เปลี่ยนอะไร** |
| T3 | **`local_id` ผิด** (hash ไม่ตรง) | ✅ **`ERROR: แก้ไข 0 แถว …` · exit 3 · ไม่เปลี่ยนอะไร** |
| — | ตรวจว่าค่าไม่ถูกพิมพ์ออกมา | ✅ ผลลัพธ์มีแค่ `BEGIN` · `DO` · `NOTICE` · `COMMIT` |
| — | GUC หายหลัง transaction จบ | ✅ `current_setting(..., true) IS NULL` = true |

> ฉบับร่างแรกพิมพ์ค่าทั้งสามออกหน้าจอ เพราะ `SELECT set_config(...)` คืนค่าที่ตั้ง
> เห็นตอนทดสอบจึงเพิ่ม `\o /dev/null` ครอบไว้ **ถ้าไม่ได้ทดสอบจะไม่เห็นข้อนี้**

---

## 6. Affected-row guard และ post-apply verification

### 6.1 Postcondition ที่ต้องเป็นจริงทั้งหมด

| # | เงื่อนไข | ค่าที่ต้องได้ |
|---|---|---|
| 1 | **affected rows** | **เท่ากับ 1 พอดี** — บังคับในตัวคำสั่งแล้ว ถ้าไม่ใช่จะถอนกลับเอง |
| 2 | แถวที่ `supabase_user_id` = UUID ของ S1 | **1** |
| 3 | `id` ของแถวนั้น | ตรงกับ target (prefix `4ad26503`) |
| 4 | จำนวนแถว `public.users` | **198 เท่าเดิม** |
| 5 | จำนวน mapping ที่ไม่ใช่ NULL | **จาก 0 → 1** |

### 6.2 ชุดตรวจหลัง UPDATE (READ-ONLY)

```sql
SELECT 'Q1_users_rows'       AS chk, count(*)::text FROM public.users
UNION ALL
SELECT 'Q2_mapped_total',    count(*)::text FROM public.users WHERE supabase_user_id IS NOT NULL
UNION ALL
SELECT 'Q3_s1_uuid_rows',    count(*)::text FROM public.users
       WHERE supabase_user_id = current_setting('mapping.s1_uuid')::uuid
UNION ALL
SELECT 'Q4_target_is_mapped', (supabase_user_id IS NOT NULL)::text FROM public.users
       WHERE id = current_setting('mapping.local_id')::uuid
UNION ALL
SELECT 'Q5_target_is_admin_active', (is_admin AND is_active)::text FROM public.users
       WHERE id = current_setting('mapping.local_id')::uuid;
```

| chk | ต้องได้ |
|---|---|
| Q1 | `198` |
| Q2 | `1` |
| Q3 | `1` |
| Q4 | `true` |
| Q5 | `true` |

ตรวจเพิ่ม: `advisor_web` ยังอ่าน `supabase_user_id` ได้ (`has_column_privilege` = true)
และยัง**ไม่มี** SELECT ระดับตารางบน `public.users`

---

## 7. Rollback plan

**ออกแบบและทดสอบแล้ว · ยังไม่รัน**

```sql
BEGIN;

\o /dev/null
SELECT set_config('mapping.s1_uuid',  :'s1_uuid',  true),
       set_config('mapping.local_id', :'local_id', true);
\o

DO $$
DECLARE
    n integer;
BEGIN
    UPDATE public.users
       SET supabase_user_id = NULL
     WHERE id = current_setting('mapping.local_id')::uuid
       AND supabase_user_id = current_setting('mapping.s1_uuid')::uuid;

    GET DIAGNOSTICS n = ROW_COUNT;

    IF n <> 1 THEN
        RAISE EXCEPTION 'ถอน % แถว แต่ต้องเป็น 1 แถวพอดี — ยกเลิกทั้งหมด', n
            USING HINT = 'แถวนั้นอาจถูกผูกกับ UUID อื่น หรือถูกถอนไปแล้ว';
    END IF;

    RAISE NOTICE 'ถอน mapping ของ 1 แถวเรียบร้อย';
END;
$$;

COMMIT;
```

### 7.1 ⚠ ด่านกันลบ mapping ของคนอื่น

เงื่อนไขบังคับ **ทั้งสองอย่างพร้อมกัน**

```
id = local_id                        และ
supabase_user_id = s1_uuid           <- ค่าปัจจุบันต้องเป็นของ S1 เท่านั้น
```

| สถานการณ์ | ผล |
|---|---|
| `local_id` ผิด | ไม่โดนแถวใด → **ยกเลิก** |
| แถวนั้นถูกผูกกับ UUID อื่นไปแล้ว | ไม่โดน → **ยกเลิก** |
| แถวนั้นเป็น NULL อยู่แล้ว | ไม่โดน → **ยกเลิก** |

**ลบ mapping ของคนอื่นโดยผิดพลาดไม่ได้เลย**

### 7.2 ทดสอบแล้ว 3 เส้นทาง

| # | สถานการณ์ | ผล |
|---|---|---|
| R1 | **UUID ผิด** | ✅ `ERROR: ถอน 0 แถว …` · **mapping เดิมยังอยู่ครบ** |
| R2 | **`local_id` ผิด** | ✅ `ERROR: ถอน 0 แถว …` · **mapping เดิมยังอยู่ครบ** |
| R3 | ค่าถูกต้อง | ✅ `NOTICE: ถอน … 1 แถวเรียบร้อย` · `COMMIT` · กลับเป็น **0 mapping** |

### 7.3 ขอบเขตของการถอนกลับ

| | |
|---|---|
| ถอนอะไร | **เฉพาะค่า `supabase_user_id` ของแถวเดียวนี้** |
| ไม่แตะอะไร | คอลัมน์อื่นของแถวนั้น · แถวอื่น · คอลัมน์ `supabase_user_id` เอง · index · สิทธิ์ |
| ต้อง backup ก่อนไหม | **ควร** — แม้จะกลับได้ด้วยคำสั่งเดียว แต่เป็น production write |

---

## 8. Risks

| # | ความเสี่ยง | ระดับ | สิ่งที่รองรับไว้ |
|---|---|---|---|
| 1 | **ผูก UUID ผิดคน** | **สูงถ้าไม่มีด่าน** | เงื่อนไข hash จับความผิดพลาดจากการคัดลอก `local_id` · `ROW_COUNT` ต้องเป็น 1 |
| 2 | **UUID ที่เจ้าของกรอกมาเป็นของ account อื่น** | **ปิดแล้ว** | เจ้าของอ่าน UUID จาก query ที่กรองด้วย full hash ของ S1 เอง ไม่ใช่จากหน้าจอ Dashboard — ดูข้อ 8.1 |
| 2b | **คัดลอก UUID ผิดตัวอักษรตอนส่งเข้าคำสั่ง** | **เหลืออยู่** | ด่านตรวจ "แถวไหน" ไม่ได้ตรวจ "ค่าอะไร" → เพิ่มขั้นตรวจความยาว 36 อักขระก่อนรัน (ข้อ 10.2) |
| 3 | ทับ mapping ที่มีอยู่ | **ไม่มี** | `supabase_user_id IS NULL` + ตอนนี้ทั้งตารางเป็น NULL หมด |
| 4 | เขียนหลายแถว | **ไม่มี** | `WHERE id =` + `ROW_COUNT = 1` |
| 5 | ล้มกลางคันเหลือสถานะครึ่ง ๆ | **ไม่มี** | อยู่ใน transaction เดียว ทดสอบเส้นทางล้มแล้วถอนกลับครบ |
| 6 | UUID ปรากฏใน log | **ต่ำ** | `log_statement = none` บน production (ตรวจไว้ตอน 006) · `\o /dev/null` กันหน้าจอ |
| 7 | UUID ปรากฏใน `pg_stat_activity` ชั่วขณะ | **ต่ำ** | เป็น identifier ไม่ใช่ความลับ · และ session จบเร็ว |

### 8.1 ความเสี่ยงข้อ 2 — **ปิดแล้ว**

ด่านทั้งหมดในข้อ 5 พิสูจน์ว่า**แถวปลายทางถูกต้อง** แต่ไม่มีด่านใดพิสูจน์ว่า
**UUID ที่กรอกเข้ามาเป็นของ S1 จริง** เพราะฝั่ง PostgreSQL ไม่มีทางรู้

**ปิดช่องนี้ด้วยวิธีที่ได้ผล** — เจ้าของอ่าน UUID มาจาก **query ที่กรองด้วย full hash
ของ S1 เอง** ไม่ใช่คัดลอกจากหน้าจอ Dashboard ด้วยตา (ข้อ 1.1)

| | |
|---|---|
| ถ้าคัดลอกจาก Dashboard | ไม่มีอะไรรับประกันว่าแถวที่มองคือ S1 |
| **ที่ทำจริง** | **query คืนเฉพาะ account ที่ hash ตรงกับ S1 · ได้ 1 แถว · UUID จึงเป็นของ account นั้นแน่นอน** |

ความเสี่ยงที่เหลือ: ถ้าคัดลอก UUID จากผลลัพธ์ผิดตัวอักษร → `UPDATE` จะเขียนค่าผิดลงไป
โดยที่ด่านทั้งสามไม่จับ **เพราะด่านตรวจ "แถวไหน" ไม่ได้ตรวจ "ค่าอะไร"**
→ ชุดตรวจหลัง apply ข้อ 6.2 มี `Q3` ที่นับแถวที่ `supabase_user_id` ตรงกับค่าที่ส่งเข้าไป
ซึ่งจับได้เฉพาะกรณีค่าไม่ตรงกับที่ตั้งใจ **ไม่ใช่กรณีคัดลอกผิดตั้งแต่ต้นทาง**

**ข้อเสนอ: ให้ส่ง UUID เข้าคำสั่งด้วยการคัดลอกทั้งค่า (ไม่พิมพ์เอง) และตรวจความยาว
36 อักขระก่อนรัน** — เพิ่มไว้ในขั้นตอน apply ข้อ 10

---

## 9. Remaining blockers

### 9.1 ตัวขวางของการ mapping — **ไม่เหลือแล้ว**

| # | สิ่งที่เคยขาด | สถานะ |
|---|---|---|
| 1 | ยืนยัน S1 ฝั่ง Supabase (`role` · `status` · จำนวนแถว) | ✅ **เจ้าของยืนยันแล้ว** (ข้อ 1.1) |
| 2 | ค่า UUID ของ S1 | ✅ **เจ้าของถือไว้** · ส่งเข้าทาง `psql -v` ตอน apply |

### 9.2 เรื่องค้างที่ **ไม่เกี่ยวกับ** การ mapping รอบนี้

| # | เรื่อง | กระทบ mapping ไหม |
|---|---|---|
| 1 | `ADVISOR_WEB_PASSWORD` ยังไม่อยู่ใน production `.env` | **ไม่** — จำเป็นสำหรับ M3 (`webapi` ต่อฐาน) คนละขั้น |
| 2 | compose 3 ไฟล์ยังไม่ส่ง `ADVISOR_WEB_PASSWORD` | **ไม่** — กระทบ dev/e2e |
| 3 | `G3_API_ENFORCEMENT_PENDING_B1` | **ไม่** — ต้องทำพร้อม endpoint |
| 4 | **ยังไม่ commit อะไรเลย** — `db/20-roles.sh` · ไฟล์ของ 006 · เอกสารชุดนี้ | **ไม่** |
| 5 | Supabase project ref ปรากฏในไฟล์ที่ยังไม่ commit 2 ไฟล์ของ checkout หลัก | **ไม่** — แจ้งไว้เป็นข้อสังเกต |

---

## 10. Exact next step

### 10.1 query ฝั่ง Supabase — **ทำไปแล้ว**

เจ้าของรันผ่าน Supabase SQL Editor และรายงานผลกลับมาครบ (ข้อ 1.1)
เก็บ query ไว้เป็นหลักฐานว่าตัวตนถูกยืนยันด้วยวิธีใด

```sql
SELECT u.id                              AS supabase_user_id,
       p.role,
       p.status,
       left(encode(extensions.digest(lower(btrim(u.email)), 'sha256'), 'hex'), 12)
                                         AS email_hash_prefix
FROM auth.users u
LEFT JOIN public.user_profiles p ON p.user_id = u.id
WHERE encode(extensions.digest(lower(btrim(u.email)), 'sha256'), 'hex')
      = '<S1 full hash — อยู่ใน B2_AUTHOR_IDENTITY_CROSSCHECK.md ข้อ 2>';
```

ได้ **1 แถว** · `role = admin` · `status = approved` · prefix `66067ef9e155` ✅

### 10.2 ขั้น Apply ที่เสนอ — **ยังไม่รัน รออนุมัติ**

**ขั้นที่ 1 — สำรองก่อน**

```bash
ssh -i ~/.ssh/oci.key ubuntu@161.118.237.37   'docker exec -i course-advisor-system-postgres-1 pg_dump -U postgres -d course_advisor -Fc'   > backup-before-s1-mapping-$(date +%Y%m%d-%H%M%S).dump
```

**ขั้นที่ 2 — ตรวจซ้ำแบบ READ-ONLY ทันทีก่อนเขียน**

ต้องได้เหมือนข้อ 3 ทุกข้อ โดยเฉพาะ `P05 = 1` · `P08 = true` · `P03 = 0`

**ขั้นที่ 3 — รับ UUID แบบไม่พิมพ์เอง แล้วตรวจความยาวก่อน**

⚠ **วางบรรทัดนี้บรรทัดเดียว** แล้ววาง UUID ที่คัดลอกมาทั้งค่า

```bash
read -rsp 'S1 supabase_user_id: ' S1UUID && echo; echo "ความยาว = ${#S1UUID}  (ต้องเป็น 36)"
```

ได้ **36** จึงไปต่อ · ได้อย่างอื่นแปลว่าวางไม่ครบหรือวางซ้ำ → ทำใหม่
**นี่คือด่านเดียวที่จับกรณีคัดลอก UUID ผิด** (ความเสี่ยงข้อ 2b)

**ขั้นที่ 4 — รันคำสั่ง mapping** (เนื้อคำสั่งอยู่ในข้อ 5.2)

```bash
ssh -i ~/.ssh/oci.key ubuntu@161.118.237.37   "docker exec -i -e PGOPTIONS='-c lock_timeout=10s' course-advisor-system-postgres-1    psql -U postgres -d course_advisor -v ON_ERROR_STOP=1         -v s1_uuid='$S1UUID' -v local_id='<local_id>' -v s1_hash='<s1_hash>'"   < s1_map.sql
unset S1UUID
```

สำเร็จจะเห็น `NOTICE: ผูก supabase_user_id ให้ 1 แถวเรียบร้อย` แล้ว `COMMIT`

> ค่าทั้งสามเดินทางทาง `-v` **ไม่มีค่าใดฝังในไฟล์** · `local_id` และ `s1_hash`
> ผมส่งให้ได้ตอนขออนุมัติ เพราะไม่ใช่ความลับ (hash อยู่ในเอกสารหลักฐานอยู่แล้ว)

**ขั้นที่ 5 — ตรวจหลัง apply** ตามข้อ 6.2 (`Q1`–`Q5`)

### 10.3 ค่าที่พร้อมแล้วสำหรับขั้น Apply

| ค่า | สถานะ |
|---|---|
| `local_id` | ✅ **ยืนยันแล้ว** — prefix `4ad26503` · ดึงซ้ำได้ด้วย query hash เดิม |
| `s1_hash` | ✅ **มีแล้ว** — `B2_AUTHOR_IDENTITY_CROSSCHECK.md` ข้อ 2 |
| `s1_uuid` | ✅ **เจ้าของถือไว้** — ส่งเข้าทาง `-v` ตอน apply |
| คำสั่ง mapping + rollback | ✅ เขียนและทดสอบแล้วอย่างละ 3 เส้นทาง |
| backup | ⬜ ทำตอน apply |

---

## บันทึกการเข้าถึงข้อมูลในรอบนี้

| ระบบ | การเข้าถึง |
|---|---|
| production PostgreSQL | **`SELECT` อย่างเดียว** 21 ข้อ · รันใต้ `default_transaction_read_only=on` · **ไม่มี UPDATE/INSERT/DELETE/DDL** |
| **email ของผู้ใช้** | **ไม่เคย SELECT ออกมา** — hash คำนวณและเทียบภายในฐานข้อมูลทั้งหมด |
| production `.env` | **อ่านชื่อคีย์เท่านั้น** ไม่อ่านค่า |
| Supabase | **ไม่ได้เข้าถึงเลย** — ไม่มีช่องทางใน session นี้ |
| คอนเทนเนอร์ทดสอบ | สร้างและลบ · ทดสอบคำสั่ง UPDATE 3 เส้นทาง + rollback 3 เส้นทาง · เหลือ 0 |
| ไฟล์ในรีโป | สร้างเอกสารนี้ไฟล์เดียว |
| git | ไม่ commit ไม่ push |

---

## STOP

# `S1_MAPPING_PREAPPLY_READY`

```
ฝั่ง PostgreSQL     ตรวจครบ 21 ข้อ ผ่านทั้งหมด สองครั้ง (19:43 และ 20:17 +07)
                    เป้าหมายชัดเจนแถวเดียว (prefix 4ad26503) · admin · active
                    supabase_user_id ยังเป็น NULL · 198 แถว · 198 hash ไม่ซ้ำ
                    ยังไม่มีใครถือ mapping ใดเลย · index valid · ready · live

ฝั่ง Supabase        เจ้าของยืนยันแล้ว — 1 แถว · admin · approved · prefix ตรง
                    (ผมไม่ได้สังเกตเอง — บันทึกไว้ในข้อ 1.2)

UUID ของ S1         เจ้าของถือไว้ · ส่งเข้าทาง psql -v ตอน apply · ไม่อยู่ในเอกสารนี้

คำสั่ง UPDATE        ออกแบบ + ทดสอบ 3 เส้นทางแล้ว · ยังไม่รัน
Rollback            ออกแบบ + ทดสอบ 3 เส้นทางแล้ว · ยังไม่รัน
```

**ไม่ UPDATE production · ไม่เติม supabase_user_id · ไม่แตะ .env / webapi / frontend
· ไม่ deploy · ไม่ commit ไม่ push**

เรื่องที่รอการตัดสินใจ

1. **อนุมัติรอบ Apply** — ขั้นตอน 5 ขั้นพร้อมแล้วในข้อ 10.2 (backup → ตรวจซ้ำ →
   รับ UUID + ตรวจความยาว 36 → รัน → ตรวจหลัง apply)
2. **ความเสี่ยงที่เหลืออยู่ข้อเดียว**: คัดลอก UUID ผิดตัวอักษร — ด่านที่รองรับคือ
   ขั้นตรวจความยาวในขั้นที่ 3 · ด่านในตัวคำสั่งตรวจได้แค่ "เขียนแถวไหน" ไม่ได้ตรวจ "ค่าอะไร"
3. **อนุมัติ commit** — ยังไม่ commit อะไรเลยตั้งแต่ `cf4fb16`
