# B1 — `advisor_web` Production Provisioning Result

| | |
|---|---|
| วันที่ | 2026-10-03 |
| **Classification** | **`ADVISOR_WEB_PROVISIONED_VERIFIED`** |
| ยืนยันเมื่อ | 2026-10-03 — ตรวจ **20 ข้อผ่านครบ** บน production (ข้อ 11.7) |
| ใครสร้าง role | **เจ้าของรันเอง** · ผมไม่ได้รัน `CREATE ROLE` แม้ครั้งเดียว |
| รหัสผ่าน | **ตั้งใหม่แล้วและพิสูจน์ด้วยการเข้าสู่ระบบจริง** (ข้อ 11.9–11.10) |
| ตรวจซ้ำหลังตั้งรหัสผ่านใหม่ | **20 ข้อผ่านครบ เหมือนเดิมทุกช่อง** (ข้อ 11.10) |
| Precheck | **ผ่านครบ 11 ข้อ** |
| `db/20-roles.sh` | **แก้แล้วและทดสอบ 3 เส้นทาง** — `+46 −0` |
| คำสั่งสำหรับ production | **ทดสอบจริงแล้ว 10 ข้อ บน PostgreSQL 16.15 เวอร์ชันเดียวกับ production** (ข้อ 10.2) |

```
GRANT / REVOKE       NONE   ALTER public.users   NONE   Migration 006        NONE
เติม supabase_user_id NONE   Data Migration       NONE   แก้ webapi           NONE
แก้ docker-compose    NONE   แก้ production .env   NONE   Supabase Write       NONE
Deploy / Restart     NONE   Commit / Push / Merge NONE   แก้ role เดิม         NONE
```

**ไม่มีรหัสผ่าน ไม่มี connection string ที่มีรหัสผ่านในเอกสารนี้**

---

## 1. Precheck

### 1.1 ฐานข้อมูล production — **ผ่านครบ 9 ข้อ** (READ-ONLY)

| # | ข้อตรวจ | ได้ | คาดหวัง | ผล |
|---|---|---|---|---|
| 1 | **`advisor_web` ยังไม่มี** | **0** | 0 | ✅ |
| 2 | ledger มี `005_web_schema` | **1** | 1 | ✅ |
| 3 | `web` schema มีอยู่ | **1** | 1 | ✅ |
| 4 | ตารางใน `web` | **5** | 5 | ✅ |
| 5 | execution user | **`postgres`** | postgres | ✅ |
| 5 | `rolcreaterole` ของ execution user | **true** | true | ✅ |
| 5 | เป็น superuser | **true** | true | ✅ |
| 8 | role ที่มีอยู่ | **`advisor_api, advisor_ingest`** | เท่าเดิม | ✅ |
| 8 | snapshot สิทธิ์ `advisor_api` บน `public.users` | **`INSERT, SELECT, UPDATE`** | เท่าเดิม | ✅ |

**ข้อ 1 สำคัญที่สุด** — ถ้า `advisor_web` มีอยู่แล้ว คำสั่งกำหนดให้ STOP และห้าม
`ALTER` รหัสผ่านหรือเปลี่ยน role เอง · **ไม่มีอยู่จริง** จึงไม่ติดเงื่อนไขนั้น

### 1.2 สภาพแวดล้อม production ที่ยืนยันแล้ว

| | |
|---|---|
| คอนเทนเนอร์ฐานข้อมูล | `course-advisor-system-postgres-1` (image `pgvector/pgvector:pg16`) |
| ฐานข้อมูล | `course_advisor` |
| เวอร์ชัน | PostgreSQL **16.15** |

ยืนยันด้วย `docker ps` และ `SELECT datname FROM pg_database` — **ไม่เดา**
สำคัญเพราะคำสั่งในข้อ 10 อ้างชื่อทั้งสองนี้ตรง ๆ

### 1.3 รูปแบบเดิมของ `db/20-roles.sh` (ข้อ 6)

```bash
set -euo pipefail

: "${ADVISOR_API_PASSWORD:?ต้องตั้งค่า ADVISOR_API_PASSWORD ใน .env ก่อน docker compose up}"
: "${ADVISOR_INGEST_PASSWORD:?ต้องตั้งค่า ADVISOR_INGEST_PASSWORD ใน .env ก่อน docker compose up}"

psql -v ON_ERROR_STOP=1 \
     -v api_password="$ADVISOR_API_PASSWORD" \
     -v ingest_password="$ADVISOR_INGEST_PASSWORD" \
     --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-'EOSQL'
    CREATE ROLE advisor_api LOGIN PASSWORD :'api_password';
    GRANT …
    CREATE ROLE advisor_ingest LOGIN PASSWORD :'ingest_password';
    GRANT …
EOSQL
```

| ลักษณะของรูปแบบเดิม | |
|---|---|
| รหัสผ่านมาจาก | env var → `psql -v` → `:'var'` ใน SQL · **ไม่เคย hardcode** |
| บังคับให้ต้องมี env var | **ใช่** — ใช้ `"${VAR:?ข้อความ}"` |
| idempotent ไหม | **ไม่** — `CREATE ROLE` ธรรมดา · ปลอดภัยเพราะ initdb รันครั้งเดียวตอน volume ว่าง |
| มี GRANT ในไฟล์นี้ไหม | **มี** สำหรับ `advisor_api`/`advisor_ingest` (ของเดิม) |

### 1.4 git (ข้อ 7)

```
branch   mko-phase2
HEAD     cf4fb16
staged   0
tracked ที่แก้  0   (ก่อนรอบนี้)
```

### 1.5 ยืนยันว่าจะไม่แก้ role เดิม (ข้อ 8)

เก็บ snapshot ของ `advisor_api` ไว้ก่อน (`INSERT, SELECT, UPDATE` บน `public.users`)
และตรวจซ้ำหลังแก้ `20-roles.sh` → **เท่าเดิมทุกข้อ** (ข้อ 6.4)

**ไม่มีคำสั่ง `ALTER ROLE` · `REVOKE` · `DROP ROLE` ใดในรอบนี้**

---

## 2. Production role creation result

# **สร้างแล้ว โดยเจ้าของ**

```
advisor_web บน production   =   1
role ที่มีอยู่                =   advisor_api, advisor_ingest, advisor_web
```

**ผมไม่ได้รัน `CREATE ROLE` แม้ครั้งเดียว** — เจ้าของรันบล็อกข้อ 10.1 เองบนเซิร์ฟเวอร์
ผมทำเฉพาะ precheck และ verification แบบ READ-ONLY

### 2.0 ทำไมผมส่งต่อให้เจ้าของรันเอง — ไม่ใช่ความล้มเหลว แต่เป็นข้อจำกัดของเครื่องมือ

คำสั่งของเจ้าของกำหนดว่า

> *"Password: Owner กรอกเองผ่าน secure hidden input"*
> *"ถ้าต้องรับค่าจาก terminal: ใช้ hidden input เช่น `read -s`"*

**ผมรับ hidden input ไม่ได้** — พิสูจน์แล้วโดยการรันจริง

```
read -rs -t 2 -p "test: " X
-> ได้ค่าว่าง  จำนวนอักขระ 0
```

stdin ของเครื่องมือที่ผมใช้เป็น `/dev/null` → `read` ได้ EOF ทันทีและคืนค่าว่าง

**ถ้าฝืนรันต่อจะได้สถานะที่พังเงียบ ๆ** — ทดสอบแล้วว่ารหัสผ่านว่างทำให้ PostgreSQL
ขึ้น `NOTICE: empty string is not a valid password, clearing password` แล้ว **สร้าง role
ที่ `rolpassword IS NULL`** คือมีอยู่แต่ยืนยันตัวตนไม่ได้เลย และต้องไป `ALTER ROLE`
แก้ภายหลัง ซึ่งเป็นสิ่งที่คำสั่งห้าม (ดูข้อ 8.2)

### 2.2 ทางอื่นที่พิจารณาแล้วและไม่ใช้

| ทาง | ทำไมไม่ใช้ |
|---|---|
| **ผมสุ่มรหัสผ่านเอง** | คำสั่งกำหนดว่าเจ้าของกรอกเอง และห้ามให้รหัสผ่านปรากฏในที่ที่ผมเห็น · การสุ่มเองหมายความว่าผมเห็นค่า |
| **อ่านจาก production `.env`** | **ตรวจแล้วว่ายังไม่มี `ADVISOR_WEB_PASSWORD` ในไฟล์นั้น** (ข้อ 7.3) และรอบนี้ **ห้ามแก้ production `.env`** |
| **ใช้ค่าเดียวกับ `ADVISOR_API_PASSWORD`** | ใช้รหัสผ่านซ้ำระหว่าง role ทำลายเหตุผลทั้งหมดของการแยก role |
| **สร้างด้วยรหัสผ่านชั่วคราวแล้วให้เจ้าของเปลี่ยนภายหลัง** | จะมีช่วงที่ role ใช้งานได้ด้วยรหัสผ่านที่ผมรู้ · และ `ALTER ROLE … PASSWORD` ภายหลังอยู่นอกขอบเขตรอบนี้ |

**จึงหยุดก่อนเขียน production** และเตรียมคำสั่งให้เจ้าของรันเอง (ข้อ 10)

---

## 3. Role attributes

**วัดจาก production จริง** เมื่อ 2026-10-03 (ข้อ 11.7)

| คุณสมบัติที่สั่ง | ค่าบน production | ผล |
|---|---|---|
| `rolcanlogin = true` | **true** | ✅ |
| `rolsuper = false` | **false** | ✅ |
| `rolcreatedb = false` | **false** | ✅ |
| `rolcreaterole = false` | **false** | ✅ |
| `rolreplication = false` | **false** | ✅ |
| `rolbypassrls = false` | **false** | ✅ |
| **มีรหัสผ่านตั้งไว้** | **true** | ✅ |
| **รหัสผ่านเก็บแบบ SCRAM-SHA-256** | **true** | ✅ |

> ข้อ `has_password` อ่านเฉพาะ predicate `rolpassword IS NOT NULL` และ
> `rolpassword LIKE 'SCRAM-SHA-256$%'` — **ไม่ดึงตัว hash ออกมา** ตามที่สั่ง

### 3.1 เรื่อง `rolinherit = true`

ค่านี้เป็นค่าตั้งต้นของ PostgreSQL และ **เหมือนกับ `advisor_api`/`advisor_ingest`**
(ตรวจแล้วทั้งคู่เป็น `true`)

`rolinherit` มีผล **เฉพาะเมื่อ role เป็นสมาชิกของ role อื่น** · `advisor_web`
**ไม่เป็นสมาชิกของใครเลย** (ข้อ 4) → ไม่สืบทอดสิทธิ์จากที่ใด ค่านี้จึงไม่มีผลจริง

ตั้ง `NOINHERIT` ก็ได้แต่จะต่างจาก role เดิมสองตัวโดยไม่มีเหตุผลรองรับ · **ไม่ตั้ง**

### 3.2 คำสั่งที่ใช้สร้าง

```sql
CREATE ROLE advisor_web LOGIN PASSWORD :'web_password'
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
```

ระบุทั้ง 5 ข้อชัดเจนแม้เป็นค่าตั้งต้น — เพื่อไม่ให้ความถูกต้องขึ้นกับค่าตั้งต้น
ที่อาจเปลี่ยนในเวอร์ชันอนาคต

---

## 4. Role membership

**วัดจาก production จริง**

| ข้อตรวจ | ค่าบน production | ผล |
|---|---|---|
| `advisor_web` เป็นสมาชิกของ role ใด | **ไม่เป็นสมาชิกใครเลย** (0 แถว) | ✅ |
| เป็นสมาชิก `advisor_api` ไหม | **ไม่** | ✅ |
| เป็นสมาชิก `advisor_ingest` ไหม | **ไม่** | ✅ |
| เป็นสมาชิก `postgres` ไหม | **ไม่** | ✅ |

```sql
SELECT g.rolname FROM pg_auth_members m
JOIN pg_roles r ON r.oid = m.member
JOIN pg_roles g ON g.oid = m.roleid
WHERE r.rolname = 'advisor_web';
-- ได้ 0 แถว
```

สคริปต์ **ไม่มีคำสั่ง `GRANT <role> TO advisor_web` ใด ๆ** → ไม่มีทางสืบทอดสิทธิ์
จาก role ที่มีสิทธิ์สูง

---

## 5. Current privileges before Migration 006

**ต้องยังไม่มีสิทธิ์อะไรเลย** — **วัดจาก production จริง**

| ข้อตรวจ | ค่าบน production | คาดหวัง | ผล |
|---|---|---|---|
| `information_schema.table_privileges` | **0** | 0 | ✅ |
| `information_schema.role_table_grants` | **0** | 0 | ✅ |
| `information_schema.routine_privileges` | **0** | 0 | ✅ |
| จำนวน membership | **0** | 0 | ✅ |
| `SELECT public.users` | **false** | false | ✅ |
| `UPDATE public.users` | **false** | false | ✅ |
| `SELECT web.news` | **false** | false | ✅ |
| `CREATE ON SCHEMA public` | **false** | false | ✅ |

### 5.1 พิสูจน์เชิงพฤติกรรม ไม่ใช่แค่อ่าน catalog

เข้าสู่ระบบเป็น `advisor_web` จริงแล้วลองอ่านตาราง

```
psql -U advisor_web -c "SELECT count(*) FROM public.t"
-> ERROR:  permission denied for table t
```

**ต่อฐานข้อมูลได้แต่อ่านตารางไม่ได้** คือสถานะที่ต้องการก่อน migration 006

### 5.2 สิ่งที่ `advisor_web` **ได้ฟรี** จาก `PUBLIC` — ไม่ใช่สิทธิ์ที่ไม่คาดคิด

| สิทธิ์ | ที่มา | วัดได้ | อันตรายไหม |
|---|---|---|---|
| `CONNECT` บน database | **`PUBLIC` มีอยู่แล้ว** (ค่าตั้งต้นของ PostgreSQL) | `t` | **ไม่** — ต่อได้แต่อ่านตารางใดไม่ได้เลย (ข้อ 5.1) |
| `USAGE ON SCHEMA public` | **`PUBLIC` มีอยู่แล้ว** | `t` | **ไม่** — เห็น schema แต่ไม่มีสิทธิ์บนตารางใด |
| `CREATE ON SCHEMA public` | **`PUBLIC` ไม่มี** | `f` | — ทำ DDL ไม่ได้ |

**บันทึกไว้ล่วงหน้าแล้วใน `B1_ADVISOR_WEB_ROLE_DESIGN.md` ข้อ 1.4** จึงไม่ใช่
"privilege โดยไม่คาดคิด" ที่คำสั่งให้ STOP · และไม่มีการ `REVOKE` อะไร
(การ REVOKE จาก `PUBLIC` จะกระทบ role อื่นทั้งหมด — อยู่นอกขอบเขต)

### 5.3 ยังไม่ให้สิทธิ์ตารางตามที่สั่ง

> *"รอบนี้ CREATE ROLE เท่านั้น · ยังไม่ GRANT web/public table privileges
> เพราะ GRANT จะอยู่ Migration 006"*

สคริปต์ที่แก้ **ไม่มีคำสั่ง `GRANT` ใดสำหรับ `advisor_web`** — ตรวจได้จาก diff (ข้อ 6.3)

---

## 6. `db/20-roles.sh` change

`+46 −0` · **ไม่แก้บรรทัดเดิมแม้บรรทัดเดียว** — เพิ่มบล็อกใหม่ต่อท้าย

### 6.1 ⚠ ตั้งใจให้ตัวแปรเป็น "ทางเลือก" ไม่ใช่ "บังคับ" — ต่างจากรูปแบบเดิม

รูปแบบเดิมใช้ `: "${ADVISOR_API_PASSWORD:?…}"` ซึ่ง **ล้มทันทีถ้าไม่ได้ตั้งค่า**
ถ้าทำแบบเดียวกันกับ `ADVISOR_WEB_PASSWORD` จะพัง **ทั้งสามสภาพแวดล้อม**

| compose | mount `20-roles.sh` | ส่ง `ADVISOR_WEB_PASSWORD` | ผลถ้าใช้ `:?` |
|---|---|---|---|
| `docker-compose.yml` (dev) | ✅ | **ไม่** | **ฐานข้อมูลไม่ขึ้น** |
| `docker-compose.prod.yml` | ✅ | **ไม่** | **ฐานข้อมูลไม่ขึ้น** |
| **`eval/e2e/docker-compose.e2e.yml`** | ✅ | **ไม่** (ตั้งแค่ api + ingest เป็นค่า throwaway) | **ชุดทดสอบ e2e ใช้ไม่ได้** |

และรอบนี้ **ห้ามแก้ docker-compose** → ตัวแปรต้องเป็นทางเลือก

```bash
if [ -n "${ADVISOR_WEB_PASSWORD:-}" ]; then
    …สร้าง role…
else
    echo "20-roles.sh: ไม่พบ ADVISOR_WEB_PASSWORD จึงข้ามการสร้าง advisor_web" >&2
    echo "20-roles.sh: webapi จะต่อฐานข้อมูลไม่ได้จนกว่าจะตั้งตัวแปรนี้แล้วสร้าง role" >&2
fi
```

**ข้ามอย่างมีเสียง ไม่ใช่ข้ามเงียบ ๆ** — เขียนลง stderr สองบรรทัดที่บอกทั้งสาเหตุและผล
เพื่อให้คนที่เจอ "role does not exist" ภายหลังตามรอยกลับมาถึงจุดนี้ได้

> เมื่อ compose ทั้งสามไฟล์ส่งตัวแปรนี้มาแล้ว (รอบแยกที่ได้รับอนุมัติ)
> จะเปลี่ยนเป็น `:?` แบบบังคับก็ได้

### 6.2 ⚠ ไม่ใช้ `DO` block เพราะ psql ไม่แทนค่าตัวแปรข้างใน dollar-quote

กับดักที่หลีกเลี่ยงไว้: psql **ไม่** ทำ variable interpolation ภายใน dollar-quoted string
→ `:'web_password'` ที่อยู่ใน `DO` block จะถูกส่งไปเป็นข้อความดิบ ไม่ใช่ค่ารหัสผ่าน

ใช้ psql meta-command แทน ซึ่งเก็บ `:'web_password'` ไว้ในคำสั่ง SQL ธรรมดา

```
SELECT NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'advisor_web')
    AS need_web_role \gset

\if :need_web_role
    CREATE ROLE advisor_web LOGIN PASSWORD :'web_password'
        NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
\else
    \echo 'advisor_web มีอยู่แล้ว — ไม่สร้างซ้ำและไม่เปลี่ยนรหัสผ่าน'
\endif
```

**idempotent** — รันซ้ำแล้วข้าม **และไม่เปลี่ยนรหัสผ่านของ role ที่มีอยู่**
(ข้อหลังสำคัญ: `ALTER ROLE … PASSWORD` จะเปลี่ยนค่าเงียบ ๆ ซึ่งคำสั่งห้าม)

> ใน `20-roles.sh` เลือก **ข้ามเงียบ** เพราะ initdb ต้องไม่ล้ม
> แต่คำสั่งสำหรับ production ในข้อ 10 เลือก **ล้มเสียงดัง** เพราะเจ้าของสั่งให้หยุด
> ถ้า role มีอยู่แล้ว — สองที่ต้องการพฤติกรรมต่างกันโดยเจตนา

### 6.3 ไม่มี `GRANT` สำหรับ `advisor_web`

```
ค้น "GRANT" ในบล็อกที่เพิ่ม  ->  ไม่พบแม้รายการเดียว
```

ตามหลัก **role = infrastructure · grant = migration** ที่ไฟล์นี้กับ 005 ตั้งไว้แล้ว
GRANT ของ `advisor_web` อยู่ใน migration 006

### 6.4 `advisor_api` / `advisor_ingest` ไม่ถูกแตะ

| | |
|---|---|
| บรรทัดเดิมถูกแก้ไหม | **ไม่** — diff เป็น `+46 −0` |
| สิทธิ์เปลี่ยนไหม | **ไม่** — ทดสอบแล้วได้ `INSERT,SELECT,UPDATE` บน `users` เท่าเดิม |
| ลำดับการสร้างเปลี่ยนไหม | **ไม่** — บล็อกใหม่อยู่ต่อท้ายหลังบล็อกเดิมทั้งหมด |

### 6.5 ทดสอบแล้ว 3 เส้นทาง — คอนเทนเนอร์ทิ้ง ไม่แตะ production

| เส้นทาง | สถานการณ์ | ผล |
|---|---|---|
| **A** | **ไม่ตั้ง** `ADVISOR_WEB_PASSWORD` (เลียนแบบ e2e/dev วันนี้) | ✅ **ฐานข้อมูลขึ้นได้ปกติ** · ข้อความข้ามปรากฏครบ 2 บรรทัด · role ที่ได้ = `advisor_api, advisor_ingest` |
| **B** | **ตั้ง** `ADVISOR_WEB_PASSWORD` | ✅ ได้ `advisor_api, advisor_ingest, advisor_web` · คุณสมบัติถูกทั้ง 6 ข้อ · **ไม่มีสิทธิ์ตารางเลย** · ไม่เป็นสมาชิกใคร · **`advisor_api` เท่าเดิม** |
| **C** | **รันบล็อกซ้ำ** บนฐานที่มี role แล้ว | ✅ ข้ามอย่างถูกต้อง · จำนวน role ยังเป็น **1** |

> เส้นทาง B ครั้งแรกรายงาน FAIL — เป็นเพราะ `pg_isready` ของผมไปชนจังหวะที่ initdb
> ปิดเซิร์ฟเวอร์ชั่วคราวแล้วเริ่มใหม่ **ไม่ใช่สคริปต์ผิด** (log แสดง `CREATE ROLE` สำเร็จ)
> แก้การรอให้คอย `PostgreSQL init process complete` แล้วผ่าน

```
คอนเทนเนอร์ทดสอบที่เหลือ  0
```

---

## 7. Secret handling

### 7.1 สิ่งที่ยืนยันได้

| ข้อกำหนด | สถานะ |
|---|---|
| ไม่ถามหรือแสดงรหัสผ่านใน chat | ✅ **ไม่มีการถาม ไม่มีการแสดง** |
| ไม่มีรหัสผ่านใน report | ✅ |
| ไม่มีรหัสผ่านใน log | ✅ |
| ไม่ hardcode รหัสผ่านใน source/repo | ✅ `20-roles.sh` อ่านจาก `$ADVISOR_WEB_PASSWORD` เท่านั้น |
| ไม่ commit รหัสผ่าน | ✅ ไม่มี commit ในรอบนี้ · และ `.env` ถูก gitignore (`.gitignore:17`) |
| รหัสผ่านที่ใช้ทดสอบ | ค่าทิ้งในคอนเทนเนอร์ที่ลบแล้ว · **ไม่ใช่รหัสผ่านของระบบใด** |

### 7.2 ข้อจำกัดที่พิสูจน์แล้ว

```
read -rs -t 2 -p "test: " X    ->   ได้ค่าว่าง  0 อักขระ
```

stdin ของเครื่องมือเป็น `/dev/null` → **ผมรับ hidden input ไม่ได้** จึงไม่สามารถ
ทำขั้น `CREATE ROLE` ที่ต้องการรหัสผ่านจากเจ้าของได้

### 7.3 `ADVISOR_WEB_PASSWORD` ยังไม่มีใน production `.env`

ตรวจ **ชื่อคีย์เท่านั้น ไม่อ่านค่า**

```
grep -oE '^ADVISOR_[A-Z_]*PASSWORD' .env
  ADVISOR_API_PASSWORD
  ADVISOR_INGEST_PASSWORD
  ---
  ยังไม่มี ADVISOR_WEB_PASSWORD
```

`.env` บน production อยู่ที่ mode **`600 ubuntu:ubuntu`** (ตรวจไว้ในรอบก่อน)

### 7.4 เรื่อง shell history — พูดให้ตรง

**คำสั่ง `read -rsp …` จะถูกบันทึกลง history ตามปกติ** — ไม่มี shell ใดยกเว้นให้
สิ่งที่ **ไม่** ถูกบันทึกคือ **ค่าที่พิมพ์** เพราะมันไม่ได้อยู่ในบรรทัดคำสั่งเลย

นี่คือเหตุผลทั้งหมดที่ใช้ `read -s` แทนการใส่รหัสผ่านลงในคำสั่งโดยตรง

---

## 8. Unexpected findings

### 8.1 ⚠ ถ้าเพิ่ม `ADVISOR_WEB_PASSWORD` แบบบังคับ จะทำให้ชุดทดสอบ e2e ใช้ไม่ได้

ไม่ได้อยู่ในคำสั่งแต่พบและต้องรายงาน

`eval/e2e/docker-compose.e2e.yml` บรรทัด 28–29 ตั้งไว้แค่

```yaml
ADVISOR_API_PASSWORD: e2e-throwaway-api
ADVISOR_INGEST_PASSWORD: e2e-throwaway-ingest
```

และบรรทัด 34 mount `20-roles.sh` เข้า initdb → ถ้าไฟล์บังคับตัวแปรที่สาม
**ฐานข้อมูลของ e2e จะไม่ขึ้น และชุดทดสอบ isolated E2E ทั้งชุดจะใช้ไม่ได้**

เป็นเหตุผลที่เลือกให้ตัวแปรเป็นทางเลือก (ข้อ 6.1)

### 8.2 ⚠ รหัสผ่านว่างไม่ error — แต่สร้าง role ที่ล็อกอินไม่ได้

ทดสอบตรง ๆ แล้ว

```
CREATE ROLE … LOGIN PASSWORD :'web_password'      (ค่าว่าง)
-> NOTICE:  empty string is not a valid password, clearing password
-> CREATE ROLE                                     (สำเร็จ!)
-> rolpassword IS NULL = t
```

**ไม่ใช่ช่องโหว่** (role นั้นยืนยันตัวตนไม่ได้) แต่เป็น **สถานะพังแบบเงียบ** ซึ่งต้องไป
`ALTER ROLE … PASSWORD` แก้ภายหลัง — สิ่งที่คำสั่งรอบนี้ห้าม

→ คำสั่งในข้อ 10.1 จึงมีด่าน `[ -n "$AWP" ]` **ก่อน** แตะฐานข้อมูล
และขั้นตรวจข้อ 10.3 มีข้อ `rolpassword IS NOT NULL`

### 8.3 ไม่พบ privilege ที่ไม่คาดคิด

คำสั่งให้ STOP ถ้าพบ privilege โดยไม่คาดคิด · **ไม่พบ** —
สิทธิ์ที่ `advisor_web` ได้คือ `CONNECT` และ `USAGE ON SCHEMA public` จาก `PUBLIC`
ซึ่งบันทึกไว้ล่วงหน้าแล้วในเอกสารออกแบบ และพิสูจน์แล้วว่าอ่านตารางไม่ได้ (ข้อ 5.1)

**ไม่มีการ `REVOKE` อะไร** ตามที่สั่ง

### 8.4 บันทึกความผิดพลาดของผมในรอบนี้

| # | เกิดอะไร | กระทบไหม | แก้แล้วอย่างไร |
|---|---|---|---|
| 1 | การทดสอบเส้นทาง B ครั้งแรกรายงาน FAIL เพราะ `pg_isready` ชนจังหวะ initdb restart | **ไม่** — บั๊กของการทดสอบ ไม่ใช่ของสคริปต์ | รอ `PostgreSQL init process complete` แล้วผ่าน |
| 2 | **ฉบับร่างแรกของคำสั่งในข้อ 10 ใช้ไม่ได้** — ส่งรหัสผ่านทาง pipe เข้า `ssh … 'bash -s'` พร้อมกับใช้ heredoc ส่งสคริปต์ · heredoc **ทับ** stdin ที่ pipe มา รหัสผ่านไปไม่ถึงปลายทางเลย และ `read` จะไปกินบรรทัดถัดไปของสคริปต์เอง | **ไม่** — ยังไม่มีใครรัน | ทดสอบจนเห็นอาการจริง แล้วเปลี่ยนไปใช้รูปแบบที่รันบนเซิร์ฟเวอร์ (ข้อ 10.1) และ **ทดสอบคำสั่งใหม่จริง 10 ข้อ** (ข้อ 10.2) |
| 3 | การทดสอบ login ครั้งแรกบอกว่า "รหัสผ่านถูกต้อง" ทั้งที่ใส่รหัสผิดก็ผ่าน — เพราะ `pg_hba.conf` ของ image เป็น `trust` | **ไม่** | บังคับ `scram-sha-256` แล้วทดสอบใหม่ · เพิ่มเคสรหัสผ่านผิดและรหัสผ่านที่ถูกตัดท้าย เพื่อพิสูจน์ว่าข้อตรวจล้มได้จริง |

> ข้อ 2 และ 3 เป็นอาการเดียวกัน: **ข้อตรวจที่ผ่านเพราะมันตรวจไม่จริง**
> ทั้งสองถูกจับได้ด้วยการรันของจริง ไม่ใช่ด้วยการอ่านโค้ด

---

## 9. Final classification

# `ADVISOR_WEB_PROVISIONED_VERIFIED`

### 9.1 ยืนยันจากอะไร

ตรวจบน production จริง **20 ข้อ ผ่านครบ** เมื่อ 2026-10-03 (ข้อ 11.7)
รันแบบ READ-ONLY ภายใต้ `default_transaction_read_only=on`

| กลุ่ม | ผล |
|---|---|
| role มีอยู่ | ✅ 1 |
| คุณสมบัติทั้ง 6 ข้อ | ✅ `login=t` · อื่น ๆ `f` ทั้งหมด |
| มีรหัสผ่าน และเป็น SCRAM-SHA-256 | ✅ (อ่านเฉพาะ predicate ไม่ดึง hash) |
| membership | ✅ 0 |
| สิทธิ์ตาราง · routine · role_table_grants | ✅ 0 ทั้งสามแหล่ง |
| `SELECT`/`UPDATE public.users` · `SELECT web.news` · `CREATE public` | ✅ false ทั้งหมด |
| `advisor_api` บน `public.users` | ✅ `INSERT,SELECT,UPDATE` **เท่าเดิมกับ precheck** |

### 9.2 ขอบเขตของคำว่า verified

| ยืนยันแล้ว | **ยังไม่ได้ยืนยัน** |
|---|---|
| role มีอยู่ · คุณสมบัติถูก · ไม่มีสิทธิ์เกิน · ของเดิมไม่ถูกแตะ | **ค่ารหัสผ่านที่เจ้าของเก็บไว้ ตรงกับที่ฐานข้อมูลเก็บหรือไม่** |

ยืนยันได้แค่ว่า **มี** รหัสผ่านตั้งไว้ ไม่ใช่ว่า**ค่าไหน** — ผมตรวจค่านั้นไม่ได้
เพราะห้ามรับรหัสผ่าน · เจ้าของต้องทดสอบเองด้วยคำสั่งในข้อ 11.8

### 9.3 สิ่งที่ทำเสร็จแล้ว

```
Precheck                    ผ่านครบ 11 ข้อ
CREATE ROLE บน production    เจ้าของรันเอง  (ผมไม่ได้รัน)
Verification 20 ข้อ          ผ่านครบ  READ-ONLY
db/20-roles.sh              แก้แล้ว +46 −0 · ทดสอบ 3 เส้นทางผ่าน
                            -> dev/test/e2e ใหม่จะได้ advisor_web อัตโนมัติเมื่อตั้งตัวแปร
                               และไม่พังถ้าไม่ตั้ง
```

---

## 10. Exact next step

### 10.1 คำสั่งที่เจ้าของรันเอง

**ขั้นที่ 1 — ssh เข้าเซิร์ฟเวอร์**

```bash
ssh -i ~/.ssh/oci.key ubuntu@161.118.237.37
```

**ขั้นที่ 2 — วางบล็อกนี้ทั้งก้อน ในหน้าต่างเดียวกันนั้น**

```bash
AWP=$(openssl rand -hex 32); echo "ความยาวรหัสผ่าน = ${#AWP}  (ต้องเป็น 64)"
[[ "$AWP" =~ ^[0-9a-f]{64}$ ]] && docker exec -i -e PGWEBPW="$AWP" course-advisor-system-postgres-1 \
  psql -U postgres -d course_advisor -v ON_ERROR_STOP=1 <<'SQL'
\set web_password `printf '%s' "$PGWEBPW"`
CREATE ROLE advisor_web LOGIN PASSWORD :'web_password'
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
SQL
printf '=== คัดลอกรหัสผ่านนี้เก็บทันที ===\n%s\n==============================\n' "$AWP"
```

สำเร็จจะเห็น

```
ความยาวรหัสผ่าน = 64  (ต้องเป็น 64)
CREATE ROLE
=== คัดลอกรหัสผ่านนี้เก็บทันที ===
<รหัสผ่าน 64 ตัว>
==============================
```

**ขั้นที่ 3 — คัดลอกเก็บแล้วล้างหน้าจอ**

```bash
unset AWP; clear
```

> ⚠ **อย่าปิดหน้าต่างก่อนคัดลอกเก็บ** — ถ้าปิดไปแล้วจะไม่มีใครรู้รหัสผ่านของ role นี้
> และต้อง `ALTER ROLE` ตั้งใหม่ ซึ่งต้องขออนุมัติรอบใหม่
> ต้องใช้ซ้ำตอนเติม `.env` ในรอบ M3

### ⚠ ทำไมเป็นบล็อกเดียว ไม่แยกขั้น

ฉบับก่อนหน้าแยกเป็นหลายขั้น แล้ว**ล้มจริงสองครั้งด้วยเหตุต่างกัน** (ข้อ 11.5)

| ปัญหาที่เจอจริง | บล็อกเดียวแก้ได้อย่างไร |
|---|---|
| คัดลอกวางรหัสผ่านซ้ำสองรอบ → ได้ 128 ตัว | **ไม่มีการคัดลอกวางเลย** — `openssl` ใส่ลงตัวแปรเอง |
| ตั้ง `AWP` ใน ssh session หนึ่ง แล้วไปรันคำสั่งสร้างในอีก session → ตัวแปรหาย คำสั่งถูกข้ามแบบเงียบ | **ทุกอย่างอยู่ในบล็อกเดียว** ตัวแปรไม่ต้องข้าม session |
| `read` กินบรรทัดถัดไปของบล็อกเป็นรหัสผ่าน | **ไม่มี `read`** — วางทั้งก้อนได้ปลอดภัย |
| ด่าน `[ -n "$AWP" ]` ไม่ผ่านแล้วเงียบ ไม่รู้ว่าเกิดอะไร | **พิมพ์ความยาวออกมาก่อนเสมอ** เห็นทันทีว่าได้ค่าหรือไม่ |

**`-hex` ไม่ใช่ `-base64`** — base64 มี `+` `/` `=` ที่ต้อง percent-encode เมื่อประกอบ
`DATABASE_URL` ในรอบ M3 โดยเฉพาะ `/` ที่ทำให้ตัวแยก URL อ่านผิดตำแหน่ง ·
hex มีแค่ `0-9 a-f` วางลง `.env` และ URL ได้ตรง ๆ
(ทั้งสองแบบใช้กับ `CREATE ROLE` ได้ — ทดสอบแล้วทั้งคู่ ข้อ 10.2 #1)

**ห้ามใช้ค่าเดียวกับ `ADVISOR_API_PASSWORD`**

### ถ้าต้องการกำหนดรหัสผ่านเอง ไม่ให้ `openssl` สุ่ม

ใช้ `read` แทนบรรทัดแรก · ⚠ **วางบรรทัดนี้บรรทัดเดียว** แล้วพิมพ์รหัสผ่าน
จากนั้นจึงวางส่วนที่เหลือของขั้นที่ 2 **ในหน้าต่างเดียวกัน**

```bash
read -rsp 'ADVISOR_WEB_PASSWORD: ' AWP && echo; echo "ความยาว = ${#AWP}"
```

ถ้าวางพร้อมบล็อกข้างล่าง `read` จะกินบรรทัดถัดไปเป็นรหัสผ่านแทน แล้วได้ role
ที่มีรหัสผ่านเป็นข้อความคำสั่ง ซึ่งเป็นค่าที่เดาได้ — เป็นอาการเดียวกับข้อ 8.4 #2


| กลไกป้องกัน | ทำอะไร |
|---|---|
| `AWP=$(openssl rand -hex 32)` | ค่าไม่ขึ้นหน้าจอตอนสร้าง · **ไม่มีการคัดลอกวาง** จึงไม่มีทางวางซ้ำหรือวางขาด |
| `echo "ความยาว = ${#AWP}"` | **เห็นทันทีว่าได้ค่าหรือไม่** — บอกแค่ความยาว ไม่แสดงค่า |
| `[[ "$AWP" =~ ^[0-9a-f]{64}$ ]]` | **ไม่แตะฐานข้อมูลถ้ารหัสผ่านผิดรูปแบบ** — กันสถานะพังเงียบในข้อ 8.2 |
| heredoc ที่ใส่ quote ให้ตัวคั่น | shell ไม่แตะเนื้อข้างใน · `$PGWEBPW` และ backtick ถูกส่งให้ psql ตีความเอง |
| `\set` + backtick | psql อ่านค่าจาก **env ของตัวเอง** ที่ `docker exec -e` ส่งมา |
| `:'web_password'` | psql ใส่ quote ให้เป็น SQL literal ที่ถูกต้อง — **ทดสอบแล้วกับรหัสผ่านที่มี `'` `"` `\` `$` `+` `/` `=`** |
| `ON_ERROR_STOP=1` + `CREATE ROLE` ธรรมดา | **ถ้า role มีอยู่แล้วจะ ERROR และหยุด** ตามที่เจ้าของสั่ง — ไม่แอบ `ALTER` รหัสผ่าน |
| `printf` ท้ายบล็อก | แสดงรหัสผ่านครั้งเดียวเพื่อคัดลอกเก็บ — **ต้องเก็บก่อนปิดหน้าต่าง** |
| `unset AWP; clear` | ล้างค่าออกจาก shell และล้างหน้าจอ |

#### ⚠ ทำไมไม่ใช่แบบ pipe ผ่าน ssh จากเครื่องตัวเอง

ฉบับร่างแรกของผมเป็นแบบนั้นและ **ใช้ไม่ได้** — การ pipe รหัสผ่านเข้า `ssh … 'bash -s'`
พร้อมกับส่งสคริปต์ทาง heredoc ทำให้ heredoc **ทับ** stdin ที่ pipe มา
รหัสผ่านไปไม่ถึงปลายทาง แล้ว `read` ก็ไปกินบรรทัดถัดไปของสคริปต์เอง · ทดสอบยืนยันแล้ว

```
printf 'THE_SECRET\n' | bash -s <<'EOS'   ->  ไม่มีผลลัพธ์เลย (read กินบรรทัด echo)
printf 'THE_SECRET\n' | bash -c '…'        ->  ได้ THE_SECRET   ถูกต้อง
```

แบบ `bash -c` ใช้ได้ แต่ต้องซ้อน quote สามชั้น (shell เครื่องตัวเอง → ssh → psql)
บนคำสั่งที่สร้าง role ของ production · **เลือกแบบที่อ่านแล้วตรวจทานได้ด้วยตาแทน**

#### ⚠ ข้อเปิดเผยที่เหลืออยู่ — ต้องรู้ไว้

`docker exec -i -e PGWEBPW="$AWP"` ทำให้ค่าปรากฏใน **argv ของกระบวนการ `docker`
บนเซิร์ฟเวอร์** ชั่วขณะ → ใครที่รัน `ps` บนเซิร์ฟเวอร์พร้อมกันพอดีจะเห็นได้

| | |
|---|---|
| เป็นระดับความเสี่ยงใหม่ไหม | **ไม่** — `db/20-roles.sh` ที่ใช้อยู่ก็ส่งรหัสผ่านทาง `psql -v` ซึ่งเป็น argv เช่นกัน |
| ลดได้ไหม | ได้ ด้วยการเขียน SQL ลงไฟล์ชั่วคราว `umask 077` แล้ว `shred` ทิ้ง — **แต่เพิ่มความซับซ้อนให้ขั้นตอนที่เกี่ยวกับความปลอดภัย ซึ่งเป็นความเสี่ยงอีกแบบ** |
| เซิร์ฟเวอร์นี้มีผู้ใช้หลายคนไหม | ไม่ — เครื่องเดี่ยวที่เจ้าของเข้าถึงคนเดียว |

**ตัดสินใจ: ใช้รูปแบบที่เรียบง่ายและตรวจทานได้** และบันทึกข้อเปิดเผยนี้ไว้ตรง ๆ
แทนที่จะอ้างว่าปลอดภัยสมบูรณ์

### 10.2 คำสั่งในข้อ 10.1 ทดสอบจริงแล้ว ไม่ใช่เขียนลอย ๆ

รันกับคอนเทนเนอร์ทิ้ง `pgvector/pgvector:pg16` → **PostgreSQL 16.15 เวอร์ชันเดียวกับ production**
และ **บังคับ `scram-sha-256` ใน `pg_hba.conf`** เพื่อให้การทดสอบรหัสผ่านมีความหมายจริง

| # | ข้อตรวจ | ผล |
|---|---|---|
| 1 | สร้าง role ด้วยรหัสผ่านที่มี `'` `"` `\` `$` `+` `/` `=` | ✅ `CREATE ROLE` · exit 0 |
| 2 | คุณสมบัติทั้ง 6 ข้อ | ✅ `t f f f f f` |
| 3 | login ด้วยรหัสผ่านที่ตั้งไว้ | ✅ `login_ok advisor_web` |
| 4 | **login ด้วยรหัสผ่านผิด** | ✅ **ถูกปฏิเสธ** `password authentication failed` |
| 4b | **login ด้วยรหัสผ่านที่ตัดอักขระท้ายออก 1 ตัว** | ✅ **ถูกปฏิเสธ** |
| 5 | สิทธิ์ตาราง · membership | ✅ `0` · `0` |
| 5b | `advisor_web` อ่านตาราง | ✅ `permission denied for table t` |
| 6 | **รันซ้ำด้วยรหัสผ่านอื่น** | ✅ `ERROR: role "advisor_web" already exists` · **exit 3** |
| 7 | รหัสผ่านเดิมหลังรันซ้ำ | ✅ ยังใช้ได้ — **ไม่ถูกเปลี่ยน** |
| 8 | จำนวน role | ✅ ยังเป็น `1` |

**ข้อ 4 และ 4b คือหัวใจ** — ถ้าไม่มีสองข้อนี้ ข้อ 3 จะผ่านแม้รหัสผ่านไปถึงแบบถูกตัด
และตอนแรกมันก็ผ่านแบบนั้นจริง เพราะ `pg_hba` ของ image เป็น `trust` (ข้อ 8.4 #3)

**ข้อ 6–7 คือหลักประกันตามคำสั่งของเจ้าของ** ว่าถ้า role มีอยู่แล้วจะหยุด
และ **ไม่เปลี่ยนรหัสผ่านเดิม**

```
คอนเทนเนอร์ทดสอบที่เหลือ  0
```

### 10.3 ขั้นตรวจหลังสร้าง — ผมรันให้ได้ทันที (`SELECT` ล้วน)

```sql
SELECT rolname, rolcanlogin, rolsuper, rolcreatedb, rolcreaterole,
       rolreplication, rolbypassrls
FROM pg_roles WHERE rolname = 'advisor_web';
-- คาดหวัง: login=t · อื่น ๆ = f ทั้งหมด

SELECT rolpassword IS NOT NULL AS has_password
FROM pg_authid WHERE rolname = 'advisor_web';
-- คาดหวัง: t    (กันกรณีรหัสผ่านว่างในข้อ 8.2)

SELECT count(*) AS memberships FROM pg_auth_members m
JOIN pg_roles r ON r.oid = m.member WHERE r.rolname = 'advisor_web';
-- คาดหวัง: 0

SELECT count(*) AS table_privs FROM information_schema.table_privileges
WHERE grantee = 'advisor_web';
-- คาดหวัง: 0  (ก่อน migration 006)

SELECT has_table_privilege('advisor_web','public.users','SELECT')  AS sel_users,
       has_table_privilege('advisor_web','public.users','UPDATE')  AS upd_users,
       has_table_privilege('advisor_web','web.news','SELECT')      AS sel_news,
       has_schema_privilege('advisor_web','public','CREATE')       AS create_public;
-- คาดหวัง: false ทุกคอลัมน์

SELECT string_agg(DISTINCT privilege_type, ',' ORDER BY privilege_type) AS api_on_users
FROM information_schema.table_privileges
WHERE grantee = 'advisor_api' AND table_schema='public' AND table_name='users';
-- คาดหวัง: INSERT,SELECT,UPDATE   (ยืนยันว่า advisor_api ไม่ถูกแตะ)
```

### 10.4 ลำดับถัดไป

```
1. เจ้าของสร้างรหัสผ่าน   openssl rand -hex 32     (ดูทางเลือกสำหรับ PowerShell ข้อ 10.1)
     ** ห้ามใช้ค่าเดียวกับ ADVISOR_API_PASSWORD **
     ** เก็บไว้ ต้องใช้ซ้ำในขั้นที่ 4 **

2. เจ้าของรันบล็อกข้อ 10.1 บนเซิร์ฟเวอร์เพื่อ CREATE ROLE

3. แจ้งผม -> ผมรันขั้นตรวจข้อ 10.3 และอัปเดตรายงานนี้
     ถ้าผ่านครบ -> ADVISOR_WEB_PROVISIONED_VERIFIED

4. เจ้าของเพิ่ม ADVISOR_WEB_PASSWORD ลง production .env
     จำเป็นสำหรับ M3 (DATABASE_URL ของ webapi)  -> รอบแยก

5. ขออนุมัติเพิ่มตัวแปรลง compose ทั้ง 3 ไฟล์ + .env.example
     เพื่อให้ dev/e2e ได้ advisor_web ด้วย  -> รอบแยก (รอบนี้ห้ามแก้ compose)

6. ขออนุมัติ migration 006  (ADD COLUMN + GRANT ให้ advisor_web)
     ** ห้ามเริ่มเอง — รอเจ้าของอนุมัติ **

7. ขออนุมัติ commit db/20-roles.sh + เอกสารของรอบนี้
```

---

## 11. บันทึกการตรวจตามข้อ 10.3

เจ้าของแจ้งว่าสร้าง `advisor_web` บน production แล้ว และสั่งให้ตรวจแบบ READ-ONLY

### 11.1 ครั้งที่ 1 (13:54 +07) — **ตรวจไม่ผ่าน เพราะ role ยังไม่มีอยู่**

```
ERROR:  role "advisor_web" does not exist
```

ยืนยันซ้ำด้วยคำถามที่ไม่ต้องอาศัยว่า role มีอยู่

| ข้อตรวจ | ผลที่ได้ |
|---|---|
| `advisor_web` | **0** |
| role ที่ชื่อมีคำว่า `advisor` | `advisor_api, advisor_ingest` |
| role ที่ชื่อมีคำว่า `web` | **(ไม่มี)** — ตัดกรณีพิมพ์ชื่อผิด |
| role ที่ล็อกอินได้ทั้งหมด | `advisor_api, advisor_ingest, postgres` |
| คอนเทนเนอร์ฐานข้อมูลบนเซิร์ฟเวอร์ | **มีตัวเดียว** `course-advisor-system-postgres-1` · ขึ้นมา 6 สัปดาห์ |
| PostgreSQL บน host โดยตรง | **ไม่มี** (ไม่มี `psql` · service `inactive`) |

→ **ไม่ใช่กรณี "สร้างถูกแต่ตรวจผิดที่"** — เซิร์ฟเวอร์นี้มีฐานข้อมูลเดียว และไม่มี role นั้น

### 11.2 ไม่ได้แก้อะไรทั้งสิ้น

การตรวจรันผ่าน `PGOPTIONS='-c default_transaction_read_only=on'` และไฟล์ SQL
เป็น `SELECT … UNION ALL …` ล้วน (19 `UNION ALL SELECT` + 1 `ORDER BY`)
**ไม่มี `CREATE` / `ALTER` / `GRANT` / `REVOKE` / `INSERT` / `UPDATE` / `DELETE`**

### 11.3 ผลพลอยได้ที่ตรวจเจอ — เป็นข่าวดี

| ค่า | ผล | แปลว่า |
|---|---|---|
| `log_statement` | `none` | **ตัวคำสั่งไม่ถูกบันทึกลง log** |
| `log_min_duration_statement` | `-1` | ไม่บันทึกตามเวลาที่ใช้ |
| `logging_collector` | `off` | — |
| `password_encryption` | `scram-sha-256` | รหัสผ่านถูกเก็บเป็น SCRAM ไม่ใช่ md5 |

→ **`CREATE ROLE … PASSWORD '…'` จะไม่ทิ้งรหัสผ่านไว้ใน log ของ PostgreSQL**
(ถ้า `log_statement` เป็น `ddl` หรือ `all` รหัสผ่านจะถูกเขียนลง log เป็นข้อความธรรมดา
— ตรวจแล้วว่าไม่ใช่)

### 11.4 ความพยายามสร้าง role ที่ล้ม 2 ครั้ง — สาเหตุคนละเรื่อง

ทั้งสองครั้ง **ด่านกันทำงานถูกต้อง ไม่มีอะไรถูกเขียนลงฐานข้อมูล** · ครั้งที่ 3 สำเร็จ

| ครั้ง | อาการที่เห็น | สาเหตุจริง | ใครผิด |
|---|---|---|---|
| 1 | `printf '%s' "$AWP" \| wc -c` ได้ **128** แทนที่จะเป็น 64 | **คัดลอกวางรหัสผ่านซ้ำสองรอบ** (64 × 2) — terminal วางทั้งตอนคลิกขวาและตอน `Ctrl+Shift+V` | ขั้นตอนของผมบังคับให้ต้องคัดลอกวาง ทั้งที่ไม่จำเป็น |
| 2 | วางบล็อกสร้าง role แล้ว **ไม่มีผลลัพธ์ใด ๆ เลย** ไม่มีทั้ง `CREATE ROLE` และ error | ssh session **ใหม่** (เห็นได้จาก `Last login:` ที่หัวจอ) → ตัวแปร `AWP` ของ session ก่อนหายไป → `[ -n "$AWP" ]` เป็นเท็จ → ทั้งคำสั่งถูกข้าม | ผมแยกเป็นหลายขั้นโดยสมมติเองว่าทุกขั้นอยู่ใน session เดียวกัน และตัดบรรทัด `\|\| echo` ที่แจ้งเตือนออกตอนส่งในแชต จึงเงียบสนิท |

### 11.5 แก้ที่ต้นเหตุ — รวมเป็นบล็อกเดียว

ไม่ใช่แค่บอกให้ระวัง แต่เอาโอกาสพลาดออกจากขั้นตอน

| โอกาสพลาด | เอาออกอย่างไร |
|---|---|
| คัดลอกวางผิด | **ไม่มีการคัดลอกวาง** — `AWP=$(openssl rand -hex 32)` |
| ตัวแปรข้าม session ไม่ได้ | **ทุกอย่างอยู่ในบล็อกเดียว** |
| `read` กินบรรทัดถัดไป | **ไม่มี `read`** ในเส้นทางหลัก |
| ด่านไม่ผ่านแล้วเงียบ | **พิมพ์ความยาวออกมาก่อนเสมอ** |

ปรับข้อ 10.1 แล้ว — เหลือ 3 ขั้น และขั้นที่สร้าง role วางได้ทั้งก้อนครั้งเดียว
**เจ้าของรันฉบับนี้แล้วสำเร็จในครั้งเดียว**

สิ่งที่ยังไม่ได้แก้: บล็อกพิมพ์รหัสผ่านออกมาแม้ `CREATE ROLE` จะล้มเหลว (ข้อ 11.8)

### 11.6 Classification หลังการตรวจครั้งที่ 1

ยังเป็น `ADVISOR_WEB_PROVISION_ABORTED` ในขณะนั้น เพราะ role ยังไม่มีอยู่จริง
**เปลี่ยนเป็น `ADVISOR_WEB_PROVISIONED_VERIFIED` หลังการตรวจครั้งที่ 2** (ข้อ 11.7)

**ไม่ได้สร้าง role ให้เอง** ตามที่สั่งห้าม `CREATE ROLE`

### 11.7 ครั้งที่ 2 — **ผ่านครบ 20 ข้อ**

เจ้าของสร้าง role สำเร็จแล้ว · ตรวจแบบ READ-ONLY ภายใต้
`PGOPTIONS='-c default_transaction_read_only=on'` · ไฟล์ SQL เป็น `SELECT` ล้วน

| # | ข้อตรวจ | ได้ | คาดหวัง | ผล |
|---|---|---|---|---|
| 01 | role มีอยู่ | `1` | 1 | ✅ |
| 02 | `rolcanlogin` | `true` | true | ✅ |
| 03 | `rolsuper` | `false` | false | ✅ |
| 04 | `rolcreatedb` | `false` | false | ✅ |
| 05 | `rolcreaterole` | `false` | false | ✅ |
| 06 | `rolreplication` | `false` | false | ✅ |
| 07 | `rolbypassrls` | `false` | false | ✅ |
| 08 | **มีรหัสผ่าน** (`rolpassword IS NOT NULL`) | `true` | true | ✅ |
| 09 | **เก็บแบบ SCRAM-SHA-256** | `true` | true | ✅ |
| 10 | membership | `0` | 0 | ✅ |
| 11 | `table_privileges` | `0` | 0 | ✅ |
| 12 | `SELECT public.users` | `false` | false | ✅ |
| 13 | `UPDATE public.users` | `false` | false | ✅ |
| 14 | `SELECT web.news` | `false` | false | ✅ |
| 15 | `CREATE ON SCHEMA public` | `false` | false | ✅ |
| 16 | **`advisor_api` บน `public.users`** | `INSERT,SELECT,UPDATE` | เท่า precheck | ✅ |
| 17 | รายชื่อ role ทั้งหมด | `advisor_api, advisor_ingest, advisor_web` | ครบ 3 | ✅ |
| 18 | `advisor_ingest` บน `public.users` | `(ไม่มี)` | — บันทึกไว้เป็น snapshot | — |
| 19 | `role_table_grants` | `0` | 0 | ✅ |
| 20 | `routine_privileges` | `0` | 0 | ✅ |

> ข้อ 18 เป็น **snapshot เพื่อบันทึก ไม่ใช่ข้อตรวจผ่าน/ไม่ผ่าน** —
> precheck รอบแรกเก็บไว้เฉพาะ `advisor_api` จึงไม่มีค่าเดิมของ `advisor_ingest`
> ให้เทียบ · บันทึกค่าปัจจุบันไว้ให้รอบหน้าเทียบได้

ข้อ 08 และ 09 อ่านจาก `pg_authid` เฉพาะ **predicate** `IS NOT NULL` และ
`LIKE 'SCRAM-SHA-256$%'` — **ไม่ดึงตัว hash ออกมา** ตามที่สั่ง

### 11.8 ⚠ เรื่องค้าง — ต้องยืนยันว่ารหัสผ่านที่เก็บไว้ถูกตัวจริง

**การรันครั้งที่สำเร็จกับครั้งที่ ERROR แสดงรหัสผ่านคนละค่ากัน**

บล็อกข้อ 10.1 สุ่มรหัสผ่านใหม่ทุกครั้งที่รัน แล้วพิมพ์ออกมาท้ายบล็อก **ไม่ว่า
`CREATE ROLE` จะสำเร็จหรือไม่** · รอบที่ขึ้น `ERROR: role "advisor_web" already exists`
ก็ยังพิมพ์รหัสผ่านออกมา — **แต่ค่านั้นไม่ได้ถูกบันทึกลงฐานข้อมูล**

| รอบ | ผลลัพธ์ | รหัสผ่านที่พิมพ์ออกมา |
|---|---|---|
| ที่ขึ้น `CREATE ROLE` | สร้างสำเร็จ | **นี่คือค่าจริงที่ฐานข้อมูลเก็บ** |
| ที่ขึ้น `ERROR: … already exists` | ไม่ได้สร้าง | **ไม่ใช่ค่าจริง — ถ้าเก็บค่านี้ไว้จะต่อฐานข้อมูลไม่ได้** |

เป็นข้อบกพร่องของบล็อกที่ผมเขียน — ควรให้พิมพ์เฉพาะเมื่อ `CREATE ROLE` สำเร็จ

#### วิธีทดสอบว่าเก็บถูกตัว

⚠ **ต้องต่อผ่าน IP ของคอนเทนเนอร์ ไม่ใช่ `127.0.0.1`**

`pg_hba.conf` ของ production ตรวจแล้วเป็น

```
line 119   host  127.0.0.1   trust            <- ไม่ตรวจรหัสผ่านเลย
line 128   host  all         scram-sha-256    <- ตรวจจริง
```

ทดสอบผ่าน `127.0.0.1` จะ **ผ่านเสมอแม้ใส่รหัสผ่านผิด** — พิสูจน์แล้วด้วยรหัสผ่านมั่ว
ซึ่งผ่านทาง `127.0.0.1` แต่ถูกปฏิเสธทาง `172.18.0.2`

```bash
read -rsp 'รหัสผ่านที่เก็บไว้: ' PW && echo
IP=$(docker exec -i course-advisor-system-postgres-1 hostname -i)
docker exec -i -e PGPASSWORD="$PW" course-advisor-system-postgres-1   psql -U advisor_web -h "$IP" -d course_advisor -tAc "SELECT 'ok ' || current_user"
unset PW
```

| ผลลัพธ์ | แปลว่า |
|---|---|
| `ok advisor_web` | **เก็บถูกตัว** — ใช้ค่านี้ใน `.env` รอบ M3 ได้ |
| `password authentication failed` | เก็บผิดตัว — role มีรหัสผ่านที่ไม่มีใครรู้ ต้อง `ALTER ROLE` ตั้งใหม่ **ซึ่งต้องขออนุมัติรอบใหม่** |

#### ผลจริง: **`password authentication failed`** (2026-10-03)

รหัสผ่านที่เจ้าของเก็บไว้ **ไม่ตรง** กับที่ฐานข้อมูลเก็บ — ตรงกับที่คาดไว้ว่า
ค่าที่เก็บมาจากรอบที่ขึ้น `ERROR: … already exists` ไม่ใช่รอบที่สร้างสำเร็จ

⚠ **ก่อนสรุป ต้องแยกสองสาเหตุนี้ออกจากกันก่อน** — บล็อกทดสอบถูกวางรวดเดียว
ซึ่งมีโอกาสที่ `read` จะรับค่าผิดเหมือนที่เคยเกิดมาแล้ว (ข้อ 11.4)

```bash
read -rsp 'รหัสผ่านที่เก็บไว้: ' PW && echo; echo "ความยาว = ${#PW}  (ต้องเป็น 64)"
```

**วางบรรทัดนี้บรรทัดเดียว** แล้วค่อยวางส่วนทดสอบที่เหลือ

| ความยาว | แปลว่า |
|---|---|
| ไม่ใช่ 64 | `read` รับค่าผิด — **ยังไม่สรุปว่ารหัสผ่านผิด** ให้ทดสอบใหม่ |
| 64 แล้วยังล้ม | **รหัสผ่านผิดจริง** — role มีรหัสผ่านที่ไม่มีใครรู้ |

#### ถ้ารหัสผ่านผิดจริง — ทางออกที่เสนอ

**ยังไม่ทำ รอเจ้าของอนุมัติ** เพราะรอบนี้สั่งห้าม `ALTER ROLE`

| ทาง | ผลกระทบ |
|---|---|
| **A. `ALTER ROLE advisor_web PASSWORD '…'`** (แนะนำ) | เปลี่ยนเฉพาะรหัสผ่าน · คุณสมบัติและสิทธิ์ไม่ถูกแตะ · role นี้ยัง **ไม่มีสิทธิ์ใด ๆ และไม่มีใครใช้งาน** (ตรวจแล้วข้อ 11.7) จึงไม่มีอะไรพังตามมา |
| **B. `DROP ROLE` แล้วสร้างใหม่** | ได้ผลเท่ากันแต่เสี่ยงกว่าโดยไม่จำเป็น · `DROP` จะล้มถ้ามี object ที่ผูกอยู่ |
| **C. หาค่าจาก scrollback ของรอบที่ขึ้น `CREATE ROLE`** | ไม่ต้องเขียนฐานข้อมูลเลย — **ลองทางนี้ก่อน** ถ้าหน้าต่างเดิมยังเปิดอยู่ |

#### ผลจริง: เจ้าของแจ้งว่า **จำรหัสผ่านไม่ได้** → ทาง C ใช้ไม่ได้ → เลือกทาง A

### 11.9 คำสั่ง `ALTER ROLE` ตั้งรหัสผ่านใหม่ — ทดสอบแล้ว 6 ข้อ

**ต้องการการอนุมัติจากเจ้าของ** เพราะเป็น production write และรอบนี้สั่งห้าม `ALTER ROLE`
เจ้าของเป็นผู้รันเอง ผมไม่รันให้

```bash
AWP=$(openssl rand -hex 32); echo "ความยาวรหัสผ่าน = ${#AWP}  (ต้องเป็น 64)"
[[ "$AWP" =~ ^[0-9a-f]{64}$ ]] && docker exec -i -e PGWEBPW="$AWP" course-advisor-system-postgres-1   psql -U postgres -d course_advisor -v ON_ERROR_STOP=1 <<'SQL'
\set web_password `printf '%s' "$PGWEBPW"`
ALTER ROLE advisor_web PASSWORD :'web_password';
SQL
RC=$?
IP=$(docker exec -i course-advisor-system-postgres-1 hostname -i)
docker exec -i -e PGPASSWORD="$AWP" course-advisor-system-postgres-1   psql -U advisor_web -h "$IP" -d course_advisor -tAc "SELECT 'login_ok ' || current_user"
LOGIN=$?
[ $RC -eq 0 ] && [ $LOGIN -eq 0 ] && printf '=== คัดลอกเก็บทันที ===
%s
=====================
' "$AWP" || echo "ไม่สำเร็จ — ไม่แสดงรหัสผ่าน (alter=$RC login=$LOGIN)"
unset AWP
```

#### แก้ข้อบกพร่องของบล็อกเดิมสองอย่าง

| บล็อกเดิม (ข้อ 10.1) | บล็อกนี้ |
|---|---|
| พิมพ์รหัสผ่านออกมา **แม้คำสั่งล้มเหลว** — ต้นเหตุที่เก็บผิดตัว | **พิมพ์เฉพาะเมื่อสำเร็จจริง** ทั้ง `ALTER` และ login |
| ไม่ได้ยืนยันว่ารหัสผ่านใช้ได้จริง | **เข้าสู่ระบบจริงผ่าน IP ของคอนเทนเนอร์** (เส้นทาง `scram-sha-256` เดียวกับที่ `webapi` จะใช้) ก่อนจึงแสดงค่า |

#### ผลทดสอบในคอนเทนเนอร์ทิ้ง PostgreSQL 16.15

จำลองสถานการณ์เดียวกัน — มี `advisor_web` ที่ไม่มีใครรู้รหัสผ่าน และบังคับ `scram-sha-256`

| # | ข้อตรวจ | ผล |
|---|---|---|
| 1 | `ALTER ROLE` สำเร็จ แล้ว login ผ่าน | ✅ `ALTER ROLE` · `login_ok advisor_web` |
| 2 | **คุณสมบัติ role ไม่เปลี่ยน** | ✅ ก่อน `1~true~false×5` → หลัง `1~true~false×5` |
| 3 | สิทธิ์และ membership ไม่เปลี่ยน | ✅ `0` · `0` · ยังเป็น SCRAM |
| 4 | **รหัสผ่านเดิมใช้ไม่ได้แล้ว** | ✅ `password authentication failed` |
| 5 | **`ALTER` ล้มเหลว → ไม่พิมพ์รหัสผ่าน** | ✅ `ไม่สำเร็จ (alter=3 login=2)` |
| 6 | **`ALTER` ผ่านแต่ login ไม่ผ่าน → ไม่พิมพ์รหัสผ่าน** | ✅ `ไม่สำเร็จ (alter=0 login=2)` |

> ข้อ 5 ครั้งแรกรายงานว่า "พิมพ์รหัสผ่าน" ทั้งที่ควรเงียบ — เพราะผมต่อ `| head -2`
> ในการทดสอบ ทำให้ `$?` กลายเป็นสถานะของ `head` ไม่ใช่ของ `psql` ·
> **เป็นบั๊กของการทดสอบ ไม่ใช่ของบล็อก** · รันใหม่โดยไม่มี pipe แล้วผ่าน
> (อาการเดียวกับข้อ 8.4 #3 — ข้อตรวจที่ผ่านเพราะมันตรวจไม่จริง)

#### หลังรันเสร็จ

1. **คัดลอกรหัสผ่านเก็บทันที** ก่อนปิดหน้าต่าง
2. บอกผม → ผมรันชุดตรวจ 20 ข้ออีกครั้งเพื่อยืนยันว่าคุณสมบัติและสิทธิ์ยังเหมือนเดิม
3. `unset AWP; clear`

**ไม่กระทบสิ่งที่ตรวจผ่านไปแล้ว** — `advisor_web` ยังไม่มีสิทธิ์ใด ๆ และยังไม่มีบริการใดใช้งาน
(ข้อ 11.7) การเปลี่ยนรหัสผ่านตอนนี้จึงไม่ทำให้อะไรพัง

### 11.10 ครั้งที่ 3 — ตรวจซ้ำหลังตั้งรหัสผ่านใหม่ · **ผ่านครบ 20 ข้อ เหมือนเดิมทุกช่อง**

เจ้าของรันบล็อกข้อ 11.9 เองและได้รหัสผ่านออกมา ซึ่งแปลว่า **ทั้ง `ALTER ROLE`
และการเข้าสู่ระบบจริงสำเร็จทั้งคู่** — บล็อกจะไม่แสดงค่าถ้าข้อใดข้อหนึ่งล้ม

ตรวจซ้ำแบบ READ-ONLY ด้วยไฟล์ SQL เดิม ภายใต้ `default_transaction_read_only=on`

| กลุ่ม | ก่อน `ALTER` | หลัง `ALTER` | ผล |
|---|---|---|---|
| role มีอยู่ | `1` | `1` | ✅ ไม่เปลี่ยน |
| คุณสมบัติ 6 ข้อ | `login=t` · อื่น ๆ `f` | **เหมือนเดิม** | ✅ ไม่เปลี่ยน |
| มีรหัสผ่าน · SCRAM | `true` · `true` | `true` · `true` | ✅ |
| membership | `0` | `0` | ✅ |
| สิทธิ์ตาราง · routine · role_table_grants | `0` ทั้งสาม | `0` ทั้งสาม | ✅ |
| `SELECT`/`UPDATE public.users` · `SELECT web.news` · `CREATE public` | `false` | `false` | ✅ |
| `advisor_api` บน `public.users` | `INSERT,SELECT,UPDATE` | **เท่าเดิม** | ✅ |
| รายชื่อ role | 3 ตัว | 3 ตัว | ✅ |

**`ALTER ROLE … PASSWORD` เปลี่ยนเฉพาะรหัสผ่านจริง** — ไม่มีช่องใดในชุดตรวจ 20 ข้อ
เปลี่ยนค่า ตรงกับที่ทดสอบไว้ล่วงหน้าในข้อ 11.9

### 11.12 ครั้งที่ 4 — ตรวจตามคำสั่ง 15 ข้อ · **ผ่านครบ** (2026-10-03 16:40 +07)

รันแบบ READ-ONLY ภายใต้ `default_transaction_read_only=on` · SQL เป็น `SELECT` ล้วน

| # | ข้อตรวจตามคำสั่ง | ได้ | คาดหวัง | ผล |
|---|---|---|---|---|
| 1 | role มีอยู่ exactly 1 | `1` | 1 | ✅ |
| 2 | `rolcanlogin` | `true` | true | ✅ |
| 3 | `rolsuper` | `false` | false | ✅ |
| 4 | `rolcreatedb` | `false` | false | ✅ |
| 5 | `rolcreaterole` | `false` | false | ✅ |
| 6 | `rolreplication` | `false` | false | ✅ |
| 7 | `rolbypassrls` | `false` | false | ✅ |
| 8 | `has_password` | `true` | true | ✅ |
| 9 | membership | `0` | 0 | ✅ |
| 10 | table privileges ก่อน Migration 006 | `0` | 0 | ✅ |
| 11 | `SELECT public.users` | `false` | false | ✅ |
| 12 | `UPDATE public.users` | `false` | false | ✅ |
| 13 | `SELECT web.news` | `false` | false | ✅ |
| 14 | `CREATE ON SCHEMA public` | `false` | false | ✅ |
| 15 | `advisor_api` privileges | `INSERT,SELECT,UPDATE` | เท่าเดิม | ✅ |

ข้อ 8 อ่านเฉพาะ predicate `rolpassword IS NOT NULL` (และ `LIKE 'SCRAM-SHA-256$%'`)
— **ไม่อ่านและไม่แสดง hash** ตามที่สั่ง

ตรวจเพิ่มอีก 5 ข้อนอกเหนือจากที่สั่ง ผ่านทั้งหมด: `role_table_grants` = 0 ·
`routine_privileges` = 0 · รายชื่อ role ครบ 3 ตัว · รหัสผ่านเก็บแบบ SCRAM-SHA-256 ·
snapshot `advisor_ingest` บน `public.users`

### 11.13 เรื่องเวลาที่สร้าง role — **PostgreSQL ไม่เก็บข้อมูลนี้**

คำสั่งระบุว่า *"ห้ามเดาหาก PostgreSQL ไม่มีข้อมูล creation timestamp"*

> **PostgreSQL ไม่มีคอลัมน์เวลาที่สร้าง role ในทุกตาราง catalog**
> `pg_roles` และ `pg_authid` ไม่มีฟิลด์ใดบันทึกเวลาที่ `CREATE ROLE` เกิดขึ้น
> **จึงไม่รายงานเวลาที่สร้าง และไม่ประมาณการใด ๆ**

ทางอ้อมที่ลองแล้วและ**ใช้ไม่ได้บนเครื่องนี้**

| ทาง | ผล |
|---|---|
| `pg_xact_commit_timestamp(xmin)` ของแถวใน `pg_authid` | **`track_commit_timestamp = off`** → ไม่มีข้อมูลเวลา commit ให้แปลง |
| log ของ PostgreSQL | **`log_statement = none`** · `logging_collector = off` (ข้อ 11.3) → ไม่มีร่องรอยคำสั่ง |

สิ่งที่ catalog **บอกได้จริง** และบันทึกไว้เป็นหลักฐาน

| ข้อมูล | ค่า | ความหมาย |
|---|---|---|
| `oid` ของ `advisor_web` | **80822** | — |
| `oid` ของ `advisor_api` | `17024` | |
| `oid` ของ `advisor_ingest` | `17025` | |
| `oid` ของ `postgres` | `10` | |
| `xmin` ของแถวใน `pg_authid` | `10388` | xid ของการแก้ไข **ครั้งล่าสุด** (คือ `ALTER ROLE`) ไม่ใช่ตอนสร้าง · แปลงเป็นเวลาไม่ได้เพราะ commit timestamp ปิดอยู่ |

`advisor_web` มี oid สูงกว่าอีกสองตัวมาก ซึ่ง**สอดคล้องกับการถูกสร้างทีหลัง**

> ⚠ **เป็นหลักฐานเชิงลำดับ ไม่ใช่เวลา** — ตัวนับ oid วนกลับมาใช้ซ้ำได้เมื่อครบรอบ
> จึงใช้ยืนยันลำดับอย่างหนักแน่นไม่ได้ และไม่ใช่ timestamp
> **ข้อเท็จจริงที่ยืนยันได้คือสถานะปัจจุบัน ไม่ใช่เวลาที่เกิด**

### 11.14 สถานะอื่นของ role เท่าที่ catalog รองรับ

| ข้อมูล | `advisor_web` | `advisor_api` | `advisor_ingest` | หมายเหตุ |
|---|---|---|---|---|
| `rolconnlimit` | `-1` | `-1` | `-1` | **เหมือนกันทั้งสามตัว** — ไม่จำกัดจำนวน connection (ค่าตั้งต้น) |
| `rolvaliduntil` | ไม่มีวันหมดอายุ | ไม่มี | ไม่มี | **เหมือนกันทั้งสามตัว** |
| `rolinherit` | `t` | `t` | `t` | **เหมือนกันทั้งสามตัว** (ข้อ 3.1) |
| `rolconfig` | ไม่มี per-role setting | — | — | ไม่มีการตั้งค่าเฉพาะ role |
| จำนวน object ที่เป็นเจ้าของ | `0` | — | — | ไม่ได้เป็นเจ้าของตารางหรือ object ใด |
| `pg_default_acl` | `0` | — | — | ไม่มี default privilege ที่ตั้งไว้ |
| session ที่เชื่อมต่ออยู่ | `0` | — | — | ยังไม่มีบริการใดใช้งาน |

**ไม่พบ attribute หรือ privilege ใดผิดจากที่คาด** จึงไม่มีอะไรต้องรายงานเพื่อ STOP

> `rolconnlimit = -1` เหมือนกับ role เดิมทั้งสองตัว จึงไม่ใช่ความผิดปกติ ·
> ถ้าต้องการจำกัดจำนวน connection ของ `webapi` เป็นเรื่องของรอบ M3 ไม่ใช่รอบนี้

### 11.11 สรุปสถานะสุดท้าย

```
advisor_web            มีอยู่บน production · คุณสมบัติถูกครบ 6 ข้อ
ตรวจแล้ว 4 ครั้ง         ครั้งที่ 1 role ยังไม่มี · ครั้งที่ 2–4 ผ่านครบทุกข้อ
รหัสผ่าน                ตั้งแล้ว · เก็บแบบ SCRAM-SHA-256 · เจ้าของถือค่าไว้
                       พิสูจน์ด้วยการเข้าสู่ระบบจริงผ่านเส้นทาง scram-sha-256
                       ซึ่งเป็นเส้นทางเดียวกับที่ webapi จะใช้
สิทธิ์                   ไม่มีเลย — ตามที่ต้องการก่อน Migration 006
advisor_api            ไม่ถูกแตะ
ผมเขียน production      ไม่มีแม้คำสั่งเดียว  (CREATE ROLE และ ALTER ROLE เจ้าของรันเอง)
```

หมายเหตุ: `webapi` จะต่อผ่าน docker network ไม่ใช่ `127.0.0.1` จึงเจอกฎ
`scram-sha-256` เหมือนการทดสอบนี้ — **รหัสผ่านต้องถูกต้องจริง**



---

## บันทึกการเข้าถึงข้อมูลในรอบนี้

| ระบบ | การเข้าถึง | รายละเอียด |
|---|---|---|
| production PostgreSQL | **`SELECT` อย่างเดียว** | precheck 9 ข้อ · ชื่อคอนเทนเนอร์และฐานข้อมูล · ยืนยันสถานะหลังจบ · **ไม่มี `CREATE` / `ALTER` / `GRANT` / `REVOKE` / `DROP`** |
| production filesystem | **อ่านชื่อคีย์ใน `.env` เท่านั้น** | `grep -oE '^ADVISOR_[A-Z_]*PASSWORD'` — **ไม่อ่านค่า** |
| คอนเทนเนอร์ทดสอบ | สร้างและลบ | ทดสอบ `20-roles.sh` 3 เส้นทาง + คำสั่งข้อ 10.1 อีก 10 ข้อ · ลบแล้วเหลือ 0 |
| ไฟล์ในรีโป | **แก้ 1 ไฟล์** | `db/20-roles.sh` `+46 −0` |
| Supabase | **ไม่ได้เข้าถึงเลย** | — |
| git | ไม่ commit ไม่ push | HEAD = `cf4fb16` · staged 0 |

---

## STOP

# `ADVISOR_WEB_PROVISIONED_VERIFIED`

`advisor_web` มีอยู่บน production · คุณสมบัติถูกครบ · **ยังไม่มีสิทธิ์ใด ๆ**
ตามที่ต้องการก่อน Migration 006 · `advisor_api` ไม่ถูกแตะ

**ไม่เริ่ม Migration 006 เอง — รอเจ้าของอนุมัติรอบถัดไป**

```
GRANT / REVOKE       NONE   ALTER public.users   NONE   Migration 006        NONE
เติม supabase_user_id NONE   Data Migration       NONE   แก้ webapi           NONE
แก้ docker-compose    NONE   แก้ production .env   NONE   Supabase Write       NONE
Deploy / Restart     NONE   Commit / Push / Merge NONE   แก้ role เดิม         NONE
```

เรื่องที่รอการตัดสินใจ

1. ⚠ **ทดสอบว่ารหัสผ่านที่คุณเก็บไว้ใช้ได้จริง** (ข้อ 11.8) — สำคัญที่สุด
   เพราะการรันครั้งที่สำเร็จกับครั้งที่ ERROR แสดงรหัสผ่านคนละค่ากัน
2. **อนุมัติ commit `db/20-roles.sh`** (`+46 −0`) และเอกสารรอบนี้ หรือไม่
3. **รอบแยก**: เพิ่ม `ADVISOR_WEB_PASSWORD` ลง production `.env` · compose 3 ไฟล์ ·
   `.env.example` — จำเป็นสำหรับ M3 และเพื่อให้ e2e ได้ role นี้ด้วย
4. **รอบแยก**: Migration 006 (`ADD COLUMN` + `GRANT` ให้ `advisor_web`)
