# B1 — S1 Identity Mapping · Production Apply Result

| | |
|---|---|
| **Classification** | **`S1_MAPPING_APPLIED_VERIFIED`** |
| backup | **2026-10-03 20:28:26 +07** · validate ผ่านครบ 3 ข้อ |
| final precheck | **2026-10-03 20:28:45 +07** · ผ่านครบ 21 ข้อ |
| **apply สำเร็จ** | **`COMMIT`** · `NOTICE: ผูก supabase_user_id ให้ 1 แถวเรียบร้อย` |
| ใครรันคำสั่ง UPDATE | **เจ้าของ** — ผมรับ interactive input ไม่ได้ (ข้อ 3.1) |
| post-apply verification | **2026-10-04 00:06:59 +07** · **26 ข้อ ผ่านครบ** |
| แถวที่ถูกแก้ | **1 แถวพอดี** — local id prefix **`4ad26503`** |
| S1 Supabase UUID | **[REDACTED]** — ไม่อยู่ในเอกสารนี้ |

```
UPDATE user อื่น          NONE     เปลี่ยน email/name/admin/active  NONE
INSERT / DELETE          NONE     Supabase Write                  NONE
ALTER / GRANT / REVOKE   NONE     แก้ production .env              NONE
แก้ webapi               NONE     แก้ frontend                     NONE
Data Migration อื่น       NONE     Deploy / Restart                NONE
Commit / Push / Merge    NONE
```

**ไม่มี Supabase UUID เต็ม ไม่มี email ไม่มีรหัสผ่าน ไม่มี connection string ในเอกสารนี้**

---

## 1. Backup result และ validation

| | |
|---|---|
| คำสั่ง | `pg_dump -U postgres -d course_advisor -Fc` ผ่าน `docker exec` |
| ไฟล์ | `/home/ubuntu/backup-before-s1-mapping-20261003-132826.dump` |
| เวลาในชื่อไฟล์ | `13:28:26` **UTC** = `20:28:26 +07` |
| exit code | **0** |

### 1.1 ตรวจครบ 3 ข้อที่สั่ง

| # | ข้อตรวจ | ผล |
|---|---|---|
| 1 | **ขนาด > 0** | ✅ **53,871,053 ไบต์** (≈ 51.4 MiB) |
| 2 | รูปแบบ custom | ✅ `PostgreSQL custom database dump - v1.15-0` |
| 3 | **`pg_restore -l` อ่านได้** | ✅ **exit 0** |

### 1.2 เนื้อในของ backup

```
Archive created at 2026-10-03 13:28:26 UTC
    dbname: course_advisor
    TOC Entries: 303
```

รายการที่ไม่ใช่คอมเมนต์ **298 รายการ** · ตารางสำคัญครบ

| ตาราง | พบ |
|---|---|
| `public.users` | ✅ |
| `public.courses` | ✅ |
| `web.news` | ✅ |
| `mko.schema_migrations` | ✅ |

> TOC เพิ่มจาก 298 เป็น 303 เทียบกับ backup ก่อน migration 006 ซึ่งสอดคล้องกับ
> คอลัมน์ · index · และสิทธิ์ที่ 006 เพิ่มเข้ามา

---

## 2. Final read-only precheck (20:28:45 +07)

รันใต้ `PGOPTIONS='-c default_transaction_read_only=on'` · **ผ่านครบ 21 ข้อ**

ครบทั้ง 8 ข้อที่สั่ง

| ข้อที่สั่ง | ได้ | ผล |
|---|---|---|
| `public.users` = 198 | **198** | ✅ |
| `mapped_total` = 0 | **0** | ✅ |
| **S1 hash match = exactly 1** | **1** | ✅ |
| target `is_admin` = true | **true** | ✅ |
| target `is_active` = true | **true** | ✅ |
| target `supabase_user_id IS NULL` | **true** | ✅ |
| index valid / ready / live | **true ทั้งสาม** | ✅ |
| ledger มี 006 exactly 1 | **1** | ✅ |

ตรวจเพิ่มอีก 13 ข้อ ผ่านทั้งหมด — ที่สำคัญคือ

| ข้อตรวจเพิ่ม | ได้ |
|---|---|
| **self-test ของท่อ hash** | `hash('  TeSt ')` = sha256 ของ `test` ✅ |
| hash อีเมลที่ไม่ซ้ำกัน | **198** จาก 198 แถว |
| admin ทั้งตาราง | **1** และเป็นแถวเป้าหมายนั้นเอง |
| S2 ฝั่ง PostgreSQL | **0** — ไม่มีคู่ ตามมติที่ไม่ provision |

---

## 3. การรับ S1 UUID (STEP 3)

### 3.1 ⚠ ผมรับ interactive input ไม่ได้ — เจ้าของเป็นผู้รัน

คำสั่งกำหนดให้ *"รับ S1 UUID จาก Owner แบบ interactive"*

พิสูจน์ซ้ำในรอบนี้

```
read -rs -t 2 -p "test: " X   ->   ได้ค่าว่าง  0 อักขระ
```

stdin ของเครื่องมือผมเป็น `/dev/null` → **ขั้นที่ 3 และ 4 เจ้าของรันเองบนเซิร์ฟเวอร์**
ผมเตรียมคำสั่งที่ทดสอบแล้วให้ และรับผิดชอบขั้น backup · precheck · post-verify

เหมือนกับรอบ `ADVISOR_WEB_PASSWORD` — ค่าที่ระบุตัวตนเดินทางจากเจ้าของเข้าคำสั่งโดยตรง
**ไม่ผ่านผม ไม่ผ่านไฟล์ที่ commit ไม่ผ่าน chat**

### 3.2 การตรวจ UUID ทั้งสามข้อ — ทำในฝั่งฐานข้อมูล

ไม่พึ่ง shell เพราะถ้า shell ตรวจแล้วปล่อยผ่าน จะไม่มีอะไรกันอีกชั้น

| # | ข้อตรวจที่สั่ง | ทำที่ไหน |
|---|---|---|
| 1 | **ความยาว = 36** | `IF length(v) <> 36 THEN RAISE EXCEPTION` ใน `DO` block |
| 2 | **รูปแบบ UUID ถูกต้อง** | regex `^[0-9a-fA-F]{8}-…-[0-9a-fA-F]{12}$` |
| 3 | **cast เป็น uuid ได้** | `PERFORM v::uuid` ก่อนแตะตาราง |

ทั้งสามอยู่**ใน transaction** → ล้มข้อไหนก็ถอนกลับทั้งหมด
และข้อความ error **ไม่แสดงค่า UUID** (`'UUID ผิดรูปแบบ (ไม่แสดงค่าเพื่อความปลอดภัย)'`)

เสริมด้วยด่านฝั่ง shell ก่อนหน้า — `read -rsp` แล้วพิมพ์เฉพาะความยาว

### 3.3 ⚠ ด่านทำงานจริง — จับความผิดพลาดได้ 2 ครั้งก่อนถึง production

| ครั้ง | เกิดอะไร | ด่านที่จับ | เสียหายไหม |
|---|---|---|---|
| 1 | **วาง hash (64 ตัว) แทน UUID (36 ตัว)** | ขั้นตรวจความยาวฝั่ง shell → `ความยาว = 64 (ต้องเป็น 36)` | **ไม่** — ยังไม่ได้แตะฐานข้อมูล |
| 2 | วาง SQL ของ Supabase ลงใน **bash ของเซิร์ฟเวอร์** แทน Supabase SQL Editor | bash เอง → `command not found` ทั้งชุด | **ไม่** — ไม่มีคำสั่งใดไปถึงฐานข้อมูลใด |

ยืนยันหลังทั้งสองครั้ง: `public.users` = **198** · `mapped_total` = **0**

ครั้งที่ 1 คือเหตุผลที่ขั้นตรวจความยาวมีอยู่ · ถ้าไม่มี ค่า 64 ตัวจะไปตกที่ด่าน
ในฐานข้อมูลแทน ซึ่งก็กันได้เหมือนกัน แต่รู้ช้ากว่าหนึ่งขั้น

ครั้งที่ 2 สะท้อนความสับสนที่เข้าใจได้ — ระบบนี้มีฐานข้อมูลสองตัวที่ไม่เกี่ยวกัน
(Supabase บนคลาวด์ ↔ PostgreSQL บนเซิร์ฟเวอร์ OCI) และ `auth.users` อยู่ที่ตัวแรกเท่านั้น

---

## 4. Exact apply result (STEP 4)

### 4.1 คำสั่งที่รัน

```bash
[ ${#S1UUID} -eq 36 ] && docker exec -i -e PGOPTIONS='-c lock_timeout=10s' \
  course-advisor-system-postgres-1 \
  psql -U postgres -d course_advisor -v ON_ERROR_STOP=1 \
       -v s1_uuid="$S1UUID" -v local_id='<target id>' -v s1_hash='<S1 hash>' <<'SQL'
…
SQL
unset S1UUID
```

| ข้อบังคับ | มีครบ |
|---|---|
| ใช้ transaction | ✅ `BEGIN` … `COMMIT` |
| `-v ON_ERROR_STOP=1` | ✅ |
| `lock_timeout = 10s` | ✅ |
| **ค่าไม่ฝังในไฟล์** | ✅ ส่งทาง `-v` ทั้งสามค่า |
| **ไม่ echo UUID** | ✅ `\o /dev/null` ครอบ `set_config` |

### 4.2 เงื่อนไขของ `UPDATE` — สามชั้นตามที่สั่ง

```sql
UPDATE public.users
   SET supabase_user_id = current_setting('mapping.s1_uuid')::uuid
 WHERE id = current_setting('mapping.local_id')::uuid
   AND encode(public.digest(lower(btrim(email::text)), 'sha256'), 'hex')
       = current_setting('mapping.s1_hash')
   AND supabase_user_id IS NULL;

GET DIAGNOSTICS n = ROW_COUNT;
IF n <> 1 THEN RAISE EXCEPTION '…'; END IF;
```

| เงื่อนไข | ป้องกันอะไร |
|---|---|
| `id = verified local user id` | เจาะจงแถวเดียว |
| **`email hash = verified S1 full hash`** | ถ้า `local_id` ถูกคัดลอกผิด เงื่อนไขนี้ไม่ผ่าน → 0 แถว → ยกเลิก |
| `supabase_user_id IS NULL` | ไม่ทับค่าของใคร |
| **`ROW_COUNT = 1` บังคับ** | ไม่ใช่ 1 เมื่อไหร่ → `RAISE EXCEPTION` → `ROLLBACK` |

### 4.3 ผลลัพธ์ที่ได้

```
BEGIN
DO
NOTICE:  ผูก supabase_user_id ให้ 1 แถวเรียบร้อย
COMMIT
```

| สิ่งที่ต้องไม่เกิด | เกิดไหม |
|---|---|
| `ERROR` | **ไม่** |
| `ROLLBACK` | **ไม่** |
| `lock timeout` | **ไม่** |
| `ROW_COUNT <> 1` | **ไม่** — `NOTICE` ยืนยันว่าได้ 1 แถว |
| retry อัตโนมัติ | **ไม่มี** — รันครั้งเดียว |

**transaction result: `COMMIT`**

---

## 5. Post-apply verification (STEP 5 · 2026-10-04 00:06:59 +07)

รันใต้ `PGOPTIONS='-c default_transaction_read_only=on'` · SQL เป็น `SELECT` ล้วน
**ไม่ SELECT email · ไม่แสดง UUID เต็ม**

### 5.1 ข้อที่สั่งให้ตรวจ — ผ่านครบ

| ข้อที่สั่ง | ได้ | คาดหวัง | ผล |
|---|---|---|---|
| `public.users` = 198 | **198** | 198 | ✅ |
| **`mapped_total` = 1** | **1** | 1 | ✅ |
| **S1 UUID match = exactly 1** | **1** (distinct non-null) | 1 | ✅ |
| **mapped local id = verified target** | **true** | true | ✅ |
| target `is_admin` = true | **true** | true | ✅ |
| target `is_active` = true | **true** | true | ✅ |
| `advisor_web` column SELECT | **`id, is_active, supabase_user_id`** | เท่ากัน | ✅ |
| **`advisor_web` ไม่มี table-level SELECT** | **false** | false | ✅ |
| ไม่มีข้อมูลอื่นเปลี่ยน | ดูข้อ 5.2 | — | ✅ |

### 5.2 "ไม่มีข้อมูลอื่นเปลี่ยน" — พิสูจน์ด้วยอะไร

| ข้อตรวจ | ได้ | ความหมาย |
|---|---|---|
| **แถวอื่นที่มี mapping** | **0** | ไม่มีใครถูกผูกเกินมา |
| **hash อีเมลของแถวเป้าหมาย** | **ยังตรงกับ S1 hash** | **อีเมลไม่ถูกแก้** |
| จำนวน admin ทั้งตาราง | **1** | `is_admin` ไม่ถูกเปลี่ยนให้ใคร |
| จำนวนแถวที่ `is_active` | **198** | `is_active` ไม่ถูกปิดของใคร (snapshot) |
| **hash อีเมลที่ไม่ซ้ำกัน** | **198** | ไม่มีแถวใดถูกเพิ่ม ลบ หรือแก้อีเมล |
| ledger | **6** | ไม่มี migration แทรก |
| index `uq_users_supabase_user_id` | **valid + ready + live** | ยังบังคับความ unique อยู่ |

ข้อ "hash อีเมลของแถวเป้าหมายยังตรง" เป็นข้อที่แข็งที่สุด — ถ้า `UPDATE` ไปโดนคอลัมน์
อื่นหรือโดนแถวอื่น hash จะเปลี่ยนทันที

### 5.3 ค่าที่เก็บได้จริง — ตรวจโดยไม่เปิดเผยค่า

| ข้อตรวจ | ได้ |
|---|---|
| ความยาวของค่าที่เก็บ | **36** |
| ไม่ใช่ nil UUID (`00000000-…`) | **true** |
| ชนิดคอลัมน์ | `uuid` (บังคับโดย schema อยู่แล้ว) |

### 5.4 สิทธิ์ของ `advisor_web` — ไม่ถดถอย

| ข้อตรวจ | ได้ | ผล |
|---|---|---|
| คอลัมน์ที่อ่านได้บน `public.users` | **`id, is_active, supabase_user_id`** | ✅ |
| ชนิดสิทธิ์ระดับคอลัมน์บน `users` | **`SELECT`** เท่านั้น | ✅ |
| **อ่าน `supabase_user_id` ได้** | **true** | ✅ ใช้ mapping ได้จริง |
| **อ่าน `email` ได้** | **false** | ✅ |
| SELECT / INSERT / UPDATE / DELETE ระดับตาราง | **false ทั้งสี่** | ✅ |
| `advisor_api` บน `public.users` | **`INSERT,SELECT,UPDATE`** | ✅ เท่า baseline |

---

## 6. Row counts

| ตาราง | ก่อน apply | หลัง apply | ผล |
|---|---|---|---|
| `public.users` | **198** | **198** | ✅ ไม่เปลี่ยน |
| `public.users` ที่ `supabase_user_id` ไม่ใช่ NULL | **0** | **1** | ✅ เพิ่มขึ้นหนึ่งตามที่ตั้งใจ |
| `public.users` ที่ `is_admin` | 1 | **1** | ✅ |
| `public.users` ที่ `is_active` | — | **198** | snapshot |
| `mko.schema_migrations` | 6 | **6** | ✅ |

**แถวที่ถูกแก้ในรอบนี้ = 1 แถว · คอลัมน์ที่ถูกแก้ = 1 คอลัมน์**

---

## 7. Unexpected findings

### 7.1 ไม่พบสิ่งผิดปกติหลัง apply

ไม่มีแถวอื่นเปลี่ยน ไม่มีสิทธิ์เปลี่ยน ไม่มี object ใดถูกสร้างหรือลบ

### 7.2 สิ่งที่พบระหว่างทางและควรบันทึก

| # | เรื่อง | ระดับ |
|---|---|---|
| 1 | **วาง hash แทน UUID** (64 ตัว) | ด่านจับได้ที่ขั้น shell · **ไม่กระทบฐานข้อมูล** |
| 2 | **วาง SQL ของ Supabase ลงใน bash ของเซิร์ฟเวอร์** | bash ปฏิเสธเอง · **ไม่กระทบฐานข้อมูล** · สะท้อนว่าควรระบุให้ชัดทุกครั้งว่าคำสั่งไหนรันที่ระบบใด |
| 3 | นาฬิกา OS ของเซิร์ฟเวอร์เป็น **UTC** ส่วน session ของ PostgreSQL เป็น **+07** | ชื่อไฟล์ backup จึงดูย้อนหลัง 7 ชั่วโมง · ไม่ใช่ความผิดพลาด |

---

## 8. Remaining blockers

### 8.1 สิ่งที่ยังขาดก่อน `webapi` ใช้งานได้จริง

| # | เรื่อง | จำเป็นสำหรับ |
|---|---|---|
| 1 | **`ADVISOR_WEB_PASSWORD` ยังไม่อยู่ใน production `.env`** | **M3** — `webapi` ต่อฐานข้อมูล |
| 2 | compose ทั้ง 3 ไฟล์ยังไม่ส่ง `ADVISOR_WEB_PASSWORD` | dev / e2e |
| 3 | `G3_API_ENFORCEMENT_PENDING_B1` | ต้องทำพร้อม endpoint จริง |

### 8.2 เรื่องที่ยังเปิดอยู่

| # | เรื่อง |
|---|---|
| 1 | **`advisor_web` พึ่ง `CONNECT` และ `USAGE ON SCHEMA public` ที่ได้จาก `PUBLIC`** — เจ้าของตัดสินใจไม่ใส่ใน 006 · ยังเป็นความเสี่ยงถ้ามีการ `REVOKE … FROM PUBLIC` ภายหลัง |
| 2 | **S2 ยังไม่มีคู่ฝั่ง PostgreSQL** (0) — ตามมติทางเลือก A · ถ้าวันหนึ่ง S2 ต้องเขียน ใช้วิธีเดียวกับรอบนี้ได้ |
| 3 | **ยังไม่ commit อะไรเลย** — `db/20-roles.sh` · ไฟล์ของ migration 006 · เอกสารทั้งชุด |

---

## 9. Final classification

# `S1_MAPPING_APPLIED_VERIFIED`

| เกณฑ์ | ผล |
|---|---|
| backup สำเร็จและ validate ผ่านครบ 3 ข้อ | ✅ |
| final precheck ผ่านครบ 8 ข้อที่สั่ง (+13 ข้อเพิ่ม) | ✅ |
| UUID ผ่านการตรวจความยาว · รูปแบบ · cast | ✅ ทั้งสามในฝั่งฐานข้อมูล |
| `UPDATE` โดน **1 แถวพอดี** · `COMMIT` | ✅ |
| post-apply verification | ✅ **26 ข้อ ผ่านครบ** |
| ข้อมูลอื่นไม่เปลี่ยน | ✅ พิสูจน์ด้วย 7 ข้อตรวจ (ข้อ 5.2) |
| สิทธิ์ `advisor_web` / `advisor_api` ไม่ถดถอย | ✅ |
| ไม่มีคำสั่งเขียนนอกขอบเขต | ✅ **แก้ 1 แถว 1 คอลัมน์เท่านั้น** |

---

## บันทึกการเข้าถึงข้อมูลในรอบนี้

| ระบบ | การเข้าถึง |
|---|---|
| production PostgreSQL | `pg_dump` (อ่าน) · **`UPDATE` 1 แถว 1 คอลัมน์ รันโดยเจ้าของ** · `SELECT` สำหรับ precheck 21 ข้อ และ post-verify 26 ข้อ |
| คำสั่งเขียนที่รัน | **`UPDATE public.users SET supabase_user_id` เท่านั้น** — ไม่มี INSERT · DELETE · DDL · GRANT · REVOKE |
| **email ของผู้ใช้** | **ไม่เคย SELECT ออกมา** — hash คำนวณและเทียบในฐานข้อมูลทั้งหมด |
| **S1 Supabase UUID** | **ไม่เคยผ่านผม** — เจ้าของกรอกเองด้วย `read -rsp` บนเซิร์ฟเวอร์ |
| Supabase | **ไม่ได้เข้าถึงเลย** — เจ้าของเป็นผู้รัน query ยืนยันตัวตนเอง |
| git | ไม่ commit ไม่ push |

---

## STOP

# `S1_MAPPING_APPLIED_VERIFIED`

```
public.users          198 แถวเท่าเดิม
mapped_total          0 -> 1     (แถวเดียว · local id prefix 4ad26503)
แถวเป้าหมาย            is_admin = true · is_active = true · hash อีเมลไม่เปลี่ยน
แถวอื่น                ไม่มีแถวใดถูกแก้ · ไม่มีใครถูกผูกเกินมา
advisor_web           อ่าน id · is_active · supabase_user_id ได้ · email ยังอ่านไม่ได้
                      ไม่มี SELECT ระดับตาราง · ไม่มี INSERT/UPDATE/DELETE
advisor_api           INSERT,SELECT,UPDATE เท่าเดิม
backup                /home/ubuntu/backup-before-s1-mapping-20261003-132826.dump
```

**ไม่เริ่มขั้น M3 เอง — รอ Owner อนุมัติ**

เรื่องที่รอการตัดสินใจ

1. **อนุมัติ commit** — ยังไม่ commit อะไรเลยตั้งแต่ `cf4fb16` · ค้างอยู่ `db/20-roles.sh`
   (`+46 −0`) · migration 006 + ชุดทดสอบ · เอกสาร 5 ฉบับของรอบ 006 และ S1
2. **รอบ M3** — เพิ่ม `ADVISOR_WEB_PASSWORD` ลง production `.env` แล้วให้ `webapi`
   ต่อฐานข้อมูลด้วย `advisor_web`
3. **รอบแยก** — เพิ่มตัวแปรลง compose 3 ไฟล์ + `.env.example` เพื่อให้ dev/e2e ใช้ได้
