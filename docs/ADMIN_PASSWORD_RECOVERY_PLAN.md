# Admin Password Recovery — `Tester@gmail.com`

| | |
|---|---|
| ตรวจ (PHASE 1/2) | 2026-09-29 · **10:06–10:10Z** (ไทย 17:06–17:10) |
| ดำเนินการจริง (PHASE 3/4) | 2026-09-29 · **11:43:28Z** (ไทย 18:43:28) — **โดยเจ้าของโปรเจกต์** |
| ตรวจยืนยัน | 2026-09-29 · **11:44:35Z** |
| ผลลัพธ์ | **สำเร็จ · affected rows = 1 · invariants ไม่ขยับ · ไม่มี restart** |
| หลักการ | รหัสผ่าน plaintext **ไม่ผ่านผมเลย** ไม่เห็น ไม่รับ ไม่พิมพ์ ไม่ log ไม่เก็บ · **ไม่ได้อ่าน `password_hash` เดิม** |

> หมายเหตุเรื่องไฟล์: รายงานฉบับแรกถูกเขียนไว้ที่ path นี้เมื่อ 10:10Z และส่งมอบแล้ว
> แต่เมื่อกลับมาบันทึกผลลัพธ์พบว่า**ไฟล์หายไปจากโปรเจกต์** (ค้นทั้ง `D:/workspace` ไม่พบ)
> ผมไม่ทราบสาเหตุและไม่เดา · ไฟล์นี้จึงเป็นการเขียนขึ้นใหม่ โดยเนื้อหา PHASE 1/2
> เหมือนฉบับที่ส่งมอบ และเพิ่มข้อ 9 ที่เป็นผลลัพธ์จริง

บัญชี `Tester@gmail.com` ที่อยู่ใน **Supabase** เป็น identity store คนละตัว
**ไม่ได้แตะ ไม่ได้แก้ ไม่ได้ลบ** ตาม Architecture Option B

---

## 1. สภาพบัญชีก่อนดำเนินการ

ตรวจด้วย **citext equality ตรงตัว** (`email = 'Tester@gmail.com'`) · **ไม่ได้ SELECT `password_hash`**

| รายการ | ค่าที่ต้องได้ | ค่าจริง | ผล |
|---|---|---|---|
| จำนวนบัญชีที่ตรง | 1 พอดี | **1** | PASS |
| `is_active` | `true` | **true** | PASS |
| `is_admin` | `true` | **true** | PASS |
| จำนวน active admin ที่ตรงอีเมล | 1 | **1** | PASS |
| `created_at` | — | `2026-09-29 14:53:16.777237+07` | — |
| `updated_at` (ก่อน reset) | — | `2026-09-29 15:50:54.925933+07` (เวลาที่ promote) | — |

**เงื่อนไข PHASE 1 ผ่าน: เป็น 1 active admin พอดี**

### `public.users` schema จริง

```
id            :: uuid NOT NULL                (PRIMARY KEY users_pkey)
email         :: citext NOT NULL              (UNIQUE users_email_key)
password_hash :: text NOT NULL                <- คอลัมน์เดียวที่เปลี่ยน
full_name     :: text
is_active     :: boolean NOT NULL
is_admin      :: boolean NOT NULL
created_at    :: timestamptz NOT NULL
updated_at    :: timestamptz NOT NULL
trigger       : trg_users_updated_at  BEFORE UPDATE FOR EACH ROW -> set_updated_at()
```

### สิทธิ์ที่จำเป็น

| ข้อตรวจ | ผล |
|---|---|
| `advisor_api` UPDATE บน `public.users` | **true** |
| `advisor_api` UPDATE คอลัมน์ `password_hash` | **true** |
| `advisor_api` SELECT คอลัมน์ `password_hash` | true (แต่**ไม่ได้ใช้**) |

→ ทำได้ด้วยสิทธิ์ที่มีอยู่แล้ว **ไม่ต้องเพิ่ม grant ไม่ต้อง migration**

---

## 2. Hashing implementation ที่ตรวจจากอิมเมจที่ให้บริการอยู่จริง

อ่านจาก `/app/backend/app/core/security.py` ในคอนเทนเนอร์ `course-advisor-system-backend-1`
(อิมเมจ `sha256:4a45677ec010…` · OCI revision `2fdc6f241fc1742047b572ee2ef354cd811f9401`)

```python
BCRYPT_ROUNDS = 12

def _prehash(plain_password: str) -> bytes:
    digest = hashlib.sha256(plain_password.encode("utf-8")).digest()
    return base64.b64encode(digest)

def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(_prehash(plain_password), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("ascii")

def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(_prehash(plain_password), password_hash.encode("ascii"))
    except ValueError:
        return False
```

**อัลกอริทึมที่ใช้จริง**

```
hash = bcrypt( base64( sha256( utf8(password) ) ),  salt cost 12 )
```

เหตุที่มี pre-hash: bcrypt รับ input ได้ 72 ไบต์ · รหัสผ่านภาษาไทย 1 ตัวอักษร = 3 ไบต์
จะชนเพดานตั้งแต่ 24 ตัวอักษร · SHA-256 + base64 ให้ความยาวคงที่ 44 ไบต์
(รูปแบบเดียวกับ `bcrypt_sha256` ของ passlib)

### ตรวจว่าใช้งานได้จริง — คอนเทนเนอร์ทิ้งจากอิมเมจเดียวกับ production

`--rm --network none` ไม่ต่อฐานข้อมูล · ค่าทดสอบเป็นค่าสุ่มที่สร้าง**ในคอนเทนเนอร์เอง**
ด้วย `secrets.token_urlsafe(24)` ไม่ได้มาจากคำสั่งของผมและไม่ได้แสดงออกมา

| ข้อตรวจ | ผล |
|---|---|
| `hash_password` คืนรูปแบบ `$2b$12$…` ยาว 60 อักขระ | **True** |
| `verify_password(รหัสที่ถูก, hash)` | **True** |
| `verify_password(รหัสที่ผิด, hash)` | **False** |
| รหัสผ่านภาษาไทย 88 ตัวอักษร = 264 ไบต์ → verify | **True** |
| `getpass` พร้อมใช้ · Python | True · 3.11.16 |

### ไม่มี endpoint reset/forgot password อยู่แล้วจริง

| ข้อตรวจ | ผล |
|---|---|
| ค้นไฟล์ในอิมเมจ `reset.?password\|forgot.?password\|password.?reset\|recover` | **ไม่พบไฟล์ใด** |
| path ใน OpenAPI ที่มีคำว่า `password` / `reset` / `forgot` / `recover` | **ไม่มีเลย** |
| เส้นทางใต้ `/auth` | `['/auth/login', '/auth/register']` เท่านั้น |

→ **ไม่มีทางกู้รหัสผ่านผ่าน API** จึงต้องใช้วิธีในข้อ 4–5

---

## 3. Baseline ที่วัดจริง

| รายการ | ค่า |
|---|---:|
| `users_total` / `active` / `admins` | **198 / 198 / 1** |
| `mko.crawl_decisions` | 0 |
| `public.courses` | 24 |
| `public.course_documents` | 31 |
| `public.course_chunks` | 9039 |
| `mko.crawl_sources` | 12 (unchanged 12 · needs_review 6 · staging_path ไม่ null 0) |
| embedding dimension | 1024 |
| `mko.v_crawl_queue` | 6 |
| `chat_messages` / `chat_answer_cache` | 6640 / 160 |

---

## 4. วิธีที่เลือก และเหตุผล

### สคริปต์ที่เจ้าของรันเอง **ในคอนเทนเนอร์ backend ของ production**

1. **ใช้ `hash_password()` ตัวเดียวกับ production จริง** — `import` จาก `app.core.security`
   ในอิมเมจที่ให้บริการอยู่ ไม่ได้เขียนอัลกอริทึมใหม่ ไม่ได้ประกอบรูปแบบ bcrypt ด้วยมือ
   และ**ไม่ใช้เว็บ hash ภายนอก**
2. **รหัสผ่านอยู่ในหน่วยความจำของโปรเซสเดียว** — อ่านด้วย `getpass` → hash →
   เขียนลงฐานข้อมูล ในโปรเซสเดียว ไม่มีขั้นที่รหัสผ่านหรือ hash ต้องผ่านไฟล์ ผ่าน pipe
   ผ่านหน้าจอ หรือผ่านผม
3. **สิทธิ์พอแล้ว** — ไม่ต้องเพิ่ม grant ไม่ต้อง migration ไม่ต้อง deploy ไม่ต้อง restart
4. **ด่านครบ** — cardinality = 1, active, admin, `FOR UPDATE`, affected rows = 1,
   ตรวจ aggregate และ invariants ทั้งก่อนและหลัง UPDATE ในธุรกรรมเดียว

### ทำไม**ไม่**ใช้ทางอื่น

| ทางเลือก | เหตุที่ไม่ใช้ |
|---|---|
| `pgcrypto` `crypt(pw, gen_salt('bf', 12))` ใน SQL | pgcrypto **ติดตั้งอยู่จริง** จึงดูเหมือนทำได้ แต่ `crypt()` hash **รหัสผ่านดิบ** ขณะที่ `verify_password` เทียบกับ `base64(sha256(pw))` → **login จะไม่ผ่านและเจ้าของจะถูกล็อกออก** ทางนี้ผิด |
| เขียน bcrypt ด้วยมือ / เว็บ hash ออนไลน์ | ห้ามตามข้อกำหนด และเสี่ยงรหัสผ่านรั่วไปบุคคลที่สาม |
| สร้าง endpoint reset ใหม่ | ต้องแก้โค้ดและ deploy — ห้าม |
| สมัครบัญชีใหม่ | `email` เป็น unique · ห้ามสร้างบัญชีใหม่ · ต้อง promote ใหม่อีก |
| ให้เจ้าของส่งรหัสผ่านมาให้ผม hash | **ห้ามเด็ดขาด** |

### ตรวจแล้วว่ากลไกทำงานได้ (ทั้งหมดเป็นการอ่าน ไม่มี commit)

| ข้อตรวจ | ผล |
|---|---|
| ผู้ใช้ที่ `docker exec` ใช้ | `appuser` (1000:1000) |
| สิทธิ์ `/tmp` ในคอนเทนเนอร์ | `1777` |
| workdir | `/app/backend` |
| `/dev/tty` | **มี** → `getpass` ซ่อนการพิมพ์ได้เมื่อใช้ `-it` |
| `getpass` / `bcrypt` / `sqlalchemy` ในอิมเมจ | พร้อมทั้งสาม |
| `from app.db.session import SessionLocal` | เชื่อมต่อได้ เป็น role `advisor_api` |
| query ทุกตัวที่สคริปต์ใช้ | `n_all=1` · `n_active_admin=1` · aggregate `(198,198,1)` · invariants `(0,24,31,9039,12)` |

---

## 5. ขั้นตอนที่เจ้าของทำ (บันทึกไว้เพื่ออ้างอิง)

1. `ssh -i ~/.ssh/oci.key ubuntu@161.118.237.37`
2. ผมส่งสคริปต์เข้าคอนเทนเนอร์ให้ (ไฟล์มีแต่โค้ด ไม่มีรหัสผ่าน) — ดูเหตุผลในข้อ 9.1
3. `sudo docker exec -it course-advisor-system-backend-1 python /tmp/reset_admin_password.py`
   แล้วพิมพ์รหัสผ่านใหม่สองครั้ง (การพิมพ์ถูกซ่อน)
4. ลบสคริปต์ออกจากคอนเทนเนอร์
5. ทดสอบ login ด้วยตัวเองผ่าน HTTPS

### สคริปต์ที่ใช้ (ส่วนที่เป็นตรรกะ)

```python
import getpass
import sys

# Python ตั้ง sys.path[0] เป็นโฟลเดอร์ของไฟล์สคริปต์ (/tmp) ไม่ใช่ WORKDIR
if "/app/backend" not in sys.path:
    sys.path.insert(0, "/app/backend")

from sqlalchemy import text
from app.core.security import hash_password, verify_password
from app.db.session import SessionLocal

EMAIL = "Tester@gmail.com"
EXPECT_AGG = (198, 198, 1)              # users, active, admins
EXPECT_INV = (0, 24, 31, 9039, 12)      # decisions, courses, documents, chunks, sources

with SessionLocal() as s:
    # ด่านก่อนถามรหัสผ่าน (อ่านอย่างเดียว) -> cardinality = 1 และเป็น active admin
    ...
    s.rollback()          # ไม่ถือ transaction ค้างระหว่างที่คนพิมพ์

    pw  = getpass.getpass("รหัสผ่านใหม่ (8-128 ตัวอักษร): ")
    pw2 = getpass.getpass("พิมพ์อีกครั้งเพื่อยืนยัน:      ")
    # ตรวจว่าตรงกันและความยาว 8-128

    new_hash = hash_password(pw)
    if not verify_password(pw, new_hash):
        fail("ตรวจย้อน hash ในหน่วยความจำไม่ผ่าน — ไม่ได้เขียนอะไร")

    s.execute(text("SET LOCAL lock_timeout = '3s'"))
    s.execute(text("SET LOCAL statement_timeout = '30s'"))
    s.execute(text("LOCK TABLE public.users IN SHARE ROW EXCLUSIVE MODE"))
    # ตรวจ cardinality ซ้ำ -> SELECT id ... FOR UPDATE -> ตรวจ aggregate และ invariants

    res = s.execute(text("UPDATE public.users SET password_hash = :h "
                         "WHERE id = :id AND email = :e AND is_active AND is_admin"),
                    {"h": new_hash, "id": tgt, "e": EMAIL})
    if res.rowcount != 1:
        s.rollback(); fail(...)
    # ตรวจสภาพเป้าหมาย + aggregate + invariants อีกครั้งก่อน commit
    s.commit()
```

คุณสมบัติ: `UPDATE` **คอลัมน์เดียว ของแถวเดียว** ระบุด้วย primary key ที่ตรึงด้วย
`FOR UPDATE` ร่วมกับ citext equality ของอีเมล · ไม่มี `LIKE`/`ILIKE`/wildcard/substring/`LIMIT` ·
**ไม่อ่าน `password_hash` เดิม** · ไม่พิมพ์รหัสผ่านหรือ hash ออกมา

---

## 6–8. (สรุปรวมอยู่ในข้อ 9)

---

## 9. ผลลัพธ์จริง — PHASE 3/4 ดำเนินการโดยเจ้าของโปรเจกต์แล้ว

### 9.1 ปัญหาระหว่างทางและการแก้

| # | อาการ | สาเหตุ | การแก้ |
|---|---|---|---|
| 1 | เชลล์ค้างที่เครื่องหมาย `>` หลังพิมพ์ `<<'PY'` | heredoc รอบรรทัดปิด `PY` — การวางสคริปต์ยาวหลายบรรทัดใน terminal ของ Windows ไม่เสถียร | เลิกให้เจ้าของวางเอง · ผมส่งไฟล์เข้าคอนเทนเนอร์ผ่าน `ssh \| docker exec -i sh -c "cat > …"` แล้วตรวจ sha256 ตรงกันทั้งสองฝั่ง |
| 2 | `ModuleNotFoundError: No module named 'app'` | Python ตั้ง `sys.path[0]` เป็นโฟลเดอร์ของ**ไฟล์สคริปต์** (`/tmp`) ไม่ใช่ WORKDIR (`/app/backend`) — กับดักเดียวกับที่เคยเจอตอนทดสอบด่าน staging และผมควรกันไว้ตั้งแต่แรก | เพิ่ม `sys.path.insert(0, "/app/backend")` ที่หัวสคริปต์ แล้ว**พิสูจน์ด้วยการรันสคริปต์ตัวจริง** โดยดัก `getpass` ให้หยุดก่อนถามรหัสผ่าน → import ผ่านและด่านตรวจก่อนถามรหัสผ่านผ่าน |

สคริปต์ฉบับที่ใช้จริง: 7,997 ไบต์ · 126 บรรทัด ·
sha256 `c3b1c02547d2951c79dbe7d560c3cd5b1b3189774d647ffd6960518b512c76eb`
(ตรงกันทั้งต้นทางและในคอนเทนเนอร์ · ตรวจไวยากรณ์ด้วย `compile()` โดยไม่เขียน `.pyc`)

### 9.2 ผลที่เจ้าของเห็นบนหน้าจอ

```
สำเร็จ: ตั้งรหัสผ่านใหม่ให้ 1 บัญชี
  affected rows = 1
  users/active/admins = (198, 198, 1) (ไม่เปลี่ยน)
  decisions/courses/documents/chunks/sources = (0, 24, 31, 9039, 12) (ไม่เปลี่ยน)
  ไม่ได้แสดงรหัสผ่านหรือ hash ใด และไม่ได้อ่าน hash เดิม
```

### 9.3 การตรวจยืนยันของผม (read-only · ไม่ SELECT `password_hash`)

| ข้อตรวจ | ค่าที่ต้องได้ | ค่าจริง | ผล |
|---|---|---|---|
| จำนวนบัญชีที่ตรงอีเมล | 1 | **1** | PASS |
| `is_active` | `true` | **true** | PASS |
| `is_admin` | `true` | **true** | PASS |
| `created_at` | ไม่เปลี่ยน | `2026-09-29 14:53:16.777237+07` เท่าเดิม | PASS |
| `updated_at` | เปลี่ยนเป็นเวลาที่ reset | `2026-09-29 18:43:28.888899+07` (เดิม 15:50:54 ของการ promote) | ตามที่คาด — ผลของ trigger |
| `users` / `active` / `admins` | 198 / 198 / 1 | **198 / 198 / 1** | PASS |
| admin ที่ไม่ใช่อีเมลเป้าหมาย | 0 | **0** | PASS |
| บัญชีอื่นที่ `updated_at` ขยับใน 15 นาที | 0 | **0** | PASS |
| `mko.crawl_decisions` | 0 | **0** | PASS |
| `courses` / `course_documents` / `course_chunks` / `crawl_sources` | 24 / 31 / 9039 / 12 | ตรงทุกตัว | PASS |
| sources `unchanged` / `needs_review` / `staging_path` ไม่ null | 12 / 6 / 0 | ตรงทุกตัว | PASS |
| embedding dimension | 1024 | 1024 | PASS |
| `mko.v_crawl_queue` | 6 | 6 | PASS |
| `chat_messages` / `chat_answer_cache` | 6640 / 160 | 6640 / 160 | PASS |

**บริการทั้งหกไม่ถูก restart** — container ID และ StartedAt เท่าเดิมทุกตัว

```
backend   fda31caa20c4  restarts=0  started=2026-09-29T01:06:17.872Z
frontend  2886c1bf9183  restarts=0  started=2026-09-29T01:07:21.190Z
caddy     a2957d7b8fc3  restarts=0  started=2026-09-22T21:23:48.949Z
postgres  e8c091a4fc60  restarts=0  started=2026-08-18T14:17:25.705Z
ollama    e6ac0350c722  restarts=0  started=2026-08-18T14:17:25.705Z
webapi    6a73308d4f39  restarts=0  started=2026-09-22T21:21:35.624Z
```

### 9.4 Production mutation ที่เกิดขึ้นจริง

| # | เวลา (UTC) | ชั้น | before → after | affected | ผู้ดำเนินการ |
|---|---|---|---|---|---|
| 1 | 2026-09-29 11:43:28 | `public.users.password_hash` ของ `Tester@gmail.com` | ค่าเดิม → ค่าใหม่ (ไม่ได้อ่านและไม่ได้แสดงทั้งสองค่า) | **1 แถว · 1 คอลัมน์** (+ `updated_at` จาก trigger ตาม schema) | **เจ้าของโปรเจกต์** |
| 2 | 11:34 → 11:44 | ไฟล์ `/tmp/reset_admin_password.py` ในคอนเทนเนอร์ backend | สร้าง → **ลบแล้ว** | ไฟล์โค้ดล้วน ไม่มีค่าลับ | ผม (สร้างและเก็บกวาด) |

**ไม่มีการเปลี่ยน** `email`, `is_active`, `is_admin`, `id`, `full_name`, `created_at`,
บัญชีอื่น, role อื่น, Supabase, schema, grant, config หรือบริการใด

### 9.5 สิ่งที่ผมไม่ได้ทำ

- **ไม่ได้อ่านหรือแสดง `password_hash`** ทั้งค่าเดิมและค่าใหม่
- **ไม่ได้พยายาม crack รหัสผ่านเดิม** และไม่ได้ทดลองเดา
- **ไม่ได้ขอ ไม่ได้รับ ไม่ได้เห็น ไม่ได้พิมพ์ ไม่ได้ log และไม่ได้เก็บ plaintext password**
- **ไม่ได้เลือกรหัสผ่านแทนเจ้าของ** — เจ้าของคิดและพิมพ์เอง
- ไม่ได้สร้างผู้ใช้ใหม่ · ไม่ได้ลดสิทธิ์ admin · ไม่ได้แตะบัญชีอื่น
- ไม่ได้แตะ Supabase · ไม่ได้แก้ Auth architecture · ไม่ได้ทำ SSO · ไม่ได้ทำ identity mapping
- ไม่ได้ migration · ไม่ได้ deploy · ไม่ได้ restart · ไม่ได้แก้ Caddy
- ไม่ได้รัน crawler/worker/ingestion · ไม่ได้ approve/ignore/undo · ไม่ได้สร้าง candidate ·
  ไม่ได้แตะ RAG/pgvector
- ไม่ได้ commit/push · ไม่ได้ merge main
- ไม่ได้ใช้เว็บ hash ภายนอก ไม่ได้คิดอัลกอริทึมเอง ไม่ได้ประกอบรูปแบบ bcrypt ด้วยมือ

### 9.6 ขั้นถัดไปของเจ้าของ

ทดสอบ login ด้วยรหัสผ่านใหม่ผ่าน HTTPS แล้วจึงทดสอบ `/crawl-review`
ตามขั้นตอนในรายงาน `PHASE3D_STEP3_5_ADMIN_PROMOTION_REPORT.md` ข้อ 10
โดย **ห้ามกด approve / ignore / undo**

**GO/NO-GO สำหรับ future controlled one-job ingestion: ยัง NO-GO**
เพราะยังไม่มี legitimate candidate (12 แหล่ง `unchanged` · `staging_path` null ทั้งหมด ·
staging ว่าง) — การมีรหัสผ่านใหม่และสิทธิ์ admin **ไม่ได้แปลว่าอนุญาตให้รัน ingestion**

---

## STOP

**Password recovery เสร็จสมบูรณ์** — เจ้าของโปรเจกต์เป็นผู้กำหนดรหัสผ่านใหม่เอง

STOP
