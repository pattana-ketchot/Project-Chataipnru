# B2 — User Mapping Verification (SHA-256 deterministic email mapping)

| | |
|---|---|
| วันที่ | 2026-10-02 |
| ขอบเขต | **READ-ONLY VERIFICATION เท่านั้น** |
| **ผล** | **ฝั่ง PostgreSQL พร้อมแล้วและพิสูจน์ได้ · ฝั่ง Supabase ทำไม่ได้ในรอบนี้** |
| **B2** | **ยัง BLOCKED** — ดูข้อ 1 |

```
Production Write   NONE        Data Migration   NONE        Deploy / Restart   NONE
Apply Migration    NONE        แก้ Supabase     NONE        Commit / Push      NONE
Merge main         NONE        Re-embed         NONE
```

**ไม่มีอีเมลจริงของใครปรากฏในไฟล์นี้ ใน log หรือในคำสั่งที่รัน** — ค่าที่ดึงออกมาจาก
ฐานข้อมูลเป็น **จำนวน** และ **ค่า boolean** เท่านั้น ไม่มีแม้แต่ hash ของอีเมลจริง
(hash ที่ปรากฏในเอกสารนี้มีตัวเดียว คือของ `test@example.com` ซึ่งเป็นค่าอ้างอิงสาธารณะ
ใช้ทดสอบว่าฟังก์ชันคำนวณถูก)

---

## 1. ⚠ BLOCKER — ไม่มี Supabase MCP ใน session นี้

| ข้อตรวจ | ผล |
|---|---|
| `.mcp.json` ในรีโปนี้ | **ไม่มีไฟล์** |
| Supabase MCP tool ใน session | **ไม่มี** — ค้นด้วย ToolSearch แล้วไม่พบ tool ที่ยิง SQL ไปยัง Supabase ได้ |
| ที่ตั้งค่าไว้จริง | `D:\workspace\LastProject\.mcp.json` → server ชื่อ `supabase` · `type: http` |
| URL ที่ตั้งไว้ | `https://mcp.supabase.com/mcp?project_ref=<REDACTED>&read_only=true&features=…` |
| token ฝังไว้ไหม | **ไม่มี** → เป็น OAuth ต้องล็อกอินแบบ interactive |
| `supabase` CLI | **ไม่ได้ติดตั้งในเครื่อง** |

MCP ตัวนั้นถูกตั้งค่าไว้สำหรับ working directory `D:\workspace\LastProject`
session นี้ทำงานที่ `D:\workspace\course-advisor-system-mko2` จึงไม่ได้โหลดมาด้วย

**ข้อดีอย่างเดียวของสถานะนี้**: URL มี `read_only=true` ติดมาแล้ว เมื่อเปิด session
ที่โฟลเดอร์นั้น การตรวจจะเป็น read-only โดยโครงสร้าง ไม่ต้องพึ่งวินัย

### 1.1 ทางที่ไม่ใช้

| ทาง | ทำไมไม่ใช้ |
|---|---|
| ใช้ anon key จาก production env ยิง PostgREST | **ขัดคำสั่งเดิมของเจ้าของ** — *"ห้ามใช้ anon key เพื่อ bypass Member access"* · และ `auth.users` ไม่ได้เปิดผ่าน PostgREST อยู่แล้ว |
| เดาอีเมลจากบริบท | **ขัดคำสั่งรอบนี้และรอบก่อน** — *"ห้าม map จากชื่อหรือข้อมูลที่ไม่ unique · ห้ามเดา UUID"* · การใช้อีเมลที่พบที่อื่นมาสมมติว่าเป็นผู้เขียนคือการเดา ไม่ใช่หลักฐาน |
| หา service-role key | ไม่มีในมือ และเป็นการขอสิทธิ์สูงกว่าที่งานนี้ต้องใช้ |

---

## 2. ⚠ แก้ความเข้าใจผิดของรายงานก่อนหน้า

คำสั่งรอบนี้ถามว่า *"ตรวจว่า `news.created_by` เป็นบัญชีเดียวกันหรือไม่"*

รายงานก่อน ๆ — **รวมทั้ง `MIGRATION_005_FINAL_REVIEW.md` ที่ผมเขียนเอง** —
เขียนว่า *"เนื้อหาทั้งฐานเขียนโดยบัญชีเดียว"* ซึ่ง **หลักฐานไม่ได้บอกอย่างนั้น**

หลักฐานที่มีอยู่จริงคือ (Live Verification ข้อ 9)

```sql
(SELECT count(DISTINCT created_by) FROM public.courses) AS courses_distinct_created_by,  -- = 1
(SELECT count(DISTINCT updated_by) FROM public.courses) AS courses_distinct_updated_by,  -- = 1
(SELECT count(DISTINCT created_by) FROM public.news)    AS news_distinct_created_by      -- = 1
```

สามค่านี้บอกว่า **แต่ละตารางมีผู้เขียนคนเดียว** — ไม่ได้บอกว่า **เป็นคนเดียวกันข้ามตาราง**
ไม่มี query ใดที่เทียบค่าของ `courses.created_by` กับ `news.created_by`

และ `auth.users` มี **3 บัญชี** กับ `user_profiles` มี **admin 2 คน** → เป็นไปได้จริงที่
สองตารางถูกเขียนโดยคนละคน

→ **คำถามข้อนี้ยังไม่เคยถูกตอบ** และตอบในรอบนี้ไม่ได้เพราะข้อ 1
ผลที่ตามมา: จำนวนบัญชีที่ต้อง map คือ **1 หรือ 2 ยังไม่ทราบ** ไม่ใช่ 1 อย่างที่เคยเขียน

---

## 3. ฝั่ง PostgreSQL — ตรวจแล้ว พร้อม

`SELECT` อย่างเดียวบน production ผ่าน `docker exec … psql` · ไม่มีคำสั่งเขียน

| สิ่งที่ตรวจ | ผล | ความหมาย |
|---|---|---|
| `pgcrypto` ติดตั้งที่ schema | **`public`** | `digest()` เรียกได้โดยไม่ต้องระบุ schema |
| `digest()` คำนวณถูกไหม | **ถูก** — `lower(btrim('  Test@Example.COM  '))` ให้ `973dfe46…13b` ซึ่งเท่ากับ SHA-256 ของ `test@example.com` ที่เป็นค่าอ้างอิงสาธารณะ | พิสูจน์กับค่าภายนอก ไม่ใช่แค่ consistent กับตัวเอง |
| ชนิดของ `public.users.email` | **`citext`** | เทียบแบบไม่สนตัวพิมพ์อยู่แล้วในฐาน แต่ **`digest()` สนตัวพิมพ์** จึงต้อง `lower()` ก่อนเสมอ |
| จำนวนแถว | **198** | |
| จำนวน hash ที่ไม่ซ้ำ (หลัง normalize) | **198** | **ผลการเทียบจึงเป็นได้แค่ 0 หรือ 1 เท่านั้น ไม่มีทางเป็น >1** — พิสูจน์แล้ว ไม่ใช่สมมติจาก UNIQUE constraint |
| แถวที่ค่าเปลี่ยนหลัง normalize | **2** | |
| แถวที่มีช่องว่างหัวท้าย | **0** | `trim` ไม่เปลี่ยนอะไรในข้อมูลชุดนี้ |
| แถวที่มีตัวพิมพ์ใหญ่ | **2** | **`lower()` เปลี่ยนผล 2 แถว** |

### 3.1 ข้อที่สำคัญต่อการใช้งานจริง

**มี 2 แถวที่เก็บอีเมลด้วยตัวพิมพ์ใหญ่** เพราะ `citext` ทำให้ฐานเทียบแบบไม่สนตัวพิมพ์
คนกรอกจึงใส่ตัวพิมพ์ใหญ่ได้โดยไม่มีอะไรฟ้อง

→ **ถ้าฝั่ง Supabase hash อีเมลดิบโดยไม่ `lower()` สองแถวนี้จะจับคู่ไม่เจอตลอดไป**
และผลจะออกมาเป็น "0 แถว" ซึ่งอ่านผิดเป็น "ไม่มีบัญชีนี้ในระบบเรา"

การ normalize แบบ `lower(trim(email))` ที่เจ้าของกำหนดมาจึง **ไม่ใช่รายละเอียดเสริม
แต่เป็นเงื่อนไขที่ทำให้ผลถูก** — และตอนนี้มีหลักฐานแล้วว่ามันกระทบ 2 แถวจริง

---

## 4. คำสั่งที่พร้อมรัน — ทั้งสองฝั่งใช้การ normalize เดียวกัน

### ขั้นที่ 1 — ฝั่ง Supabase (ยังรันไม่ได้ · ต้องทำใน session ที่ `D:\workspace\LastProject`)

```sql
-- READ-ONLY · คืนค่าเป็น hash ไม่ใช่อีเมล · ไม่มีข้อมูลระบุตัวบุคคลออกมา
WITH authors AS (
  SELECT DISTINCT 'courses' AS src, created_by AS uid FROM public.courses WHERE created_by IS NOT NULL
  UNION
  SELECT DISTINCT 'news',           created_by        FROM public.news    WHERE created_by IS NOT NULL
)
SELECT
  a.src,
  a.uid                                                              AS supabase_auth_uid,
  encode(digest(lower(btrim(u.email)), 'sha256'), 'hex')             AS email_sha256
FROM authors a
JOIN auth.users u ON u.id = a.uid
ORDER BY a.src;
```

พร้อมคำถามที่คำสั่งรอบนี้ถามถึงโดยตรง

```sql
-- courses กับ news เป็นบัญชีเดียวกันไหม — ตอบเป็น boolean ไม่ต้องเปิดเผย uid ก็ได้
SELECT
  (SELECT count(DISTINCT created_by) FROM public.courses)                      AS courses_authors,
  (SELECT count(DISTINCT created_by) FROM public.news)                         AS news_authors,
  ((SELECT DISTINCT created_by FROM public.courses)
   = (SELECT DISTINCT created_by FROM public.news))                            AS same_account;
```

### ขั้นที่ 2 — ฝั่ง PostgreSQL (พร้อมรันทันทีที่ได้ hash)

```sql
-- READ-ONLY · ไม่ SELECT email ออกมาเลย · คืนเฉพาะ id กับ is_admin ตามที่สั่ง
SELECT id, is_admin
FROM public.users
WHERE encode(digest(lower(btrim(email::text)), 'sha256'), 'hex')
      = '<email_sha256 จากขั้นที่ 1>';
```

| จำนวนแถวที่ได้ | แปลว่า | ทำอะไรต่อ |
|---:|---|---|
| **1** | mapping เป็น deterministic | ใช้ `id` นั้นเป็น `created_by`/`updated_by` · **B2 = READY** |
| **0** | บัญชีผู้เขียนฝั่ง Supabase ไม่มีคู่ในฝั่งเรา | ไปที่ `AUTHORIZATION_USER_MAPPING_DESIGN.md` ข้อ 5.4 — **ห้ามสร้าง user ใหม่** |
| **>1** | **เป็นไปไม่ได้** — พิสูจน์แล้วว่า 198 แถวให้ 198 hash ไม่ซ้ำ | ถ้าเกิดขึ้นคือฐานข้อมูลเปลี่ยนไปจากที่ตรวจ ต้องหยุดและตรวจใหม่ |

### 4.1 ทำไมแยกเป็นสองขั้นแล้วขนแค่ hash

```
อีเมลจริงไม่เคยออกจากฐานข้อมูลที่มันอยู่
hash เป็นฟังก์ชันทางเดียว  ไม่ต้องมีใครคัดลอกอีเมลไปวางที่ไหน
ค่าที่ขนข้ามระบบไม่ลงเอกสารที่ commit ลงรีโป public และไม่อยู่ใน shell history
```

ข้อจำกัดที่ยอมรับอย่างรู้ตัว: **hash ของอีเมลไม่ใช่ความลับที่แข็ง** — ใครรู้อีเมลอยู่แล้ว
ก็ยืนยันได้ว่าตรงกัน แต่มันไม่ **เปิดเผย** อีเมลที่ยังไม่มีใครรู้ ซึ่งเป็นสิ่งที่ต้องการที่นี่

---

## 5. รายงานตามรายการที่สั่ง

| ที่สั่งให้รายงาน | ผล |
|---|---|
| Supabase author IDs เหมือนกันระหว่าง `courses` / `news` หรือไม่ | **UNKNOWN** — เข้าถึง Supabase ไม่ได้ (ข้อ 1) · และหลักฐานเดิมไม่เคยตอบข้อนี้ (ข้อ 2) |
| email hash match count = 0 / 1 / >1 | **UNKNOWN** — ยังไม่มี hash จากฝั่งต้นทางให้เทียบ |
| ถ้า match = 1 → target `public.users.id` | **ยังรายงานไม่ได้** |
| target `is_admin` | **ยังรายงานไม่ได้** |
| **B2** | **ยัง BLOCKED** |

### 5.1 สิ่งที่รายงานได้แล้วและเป็นของจริง

| | |
|---|---|
| ฝั่งปลายทางพร้อม | `pgcrypto` อยู่ที่ `public` · `digest()` คำนวณถูกเทียบกับค่าอ้างอิงภายนอก |
| ผลการเทียบจะกำกวมไหม | **ไม่** — 198 แถว → 198 hash ไม่ซ้ำ จึงเป็นได้แค่ 0 หรือ 1 |
| การ normalize จำเป็นจริงไหม | **จริง** — กระทบ 2 แถวที่เก็บด้วยตัวพิมพ์ใหญ่ |
| จำนวนบัญชีที่ต้อง map | **1 หรือ 2 ยังไม่ทราบ** (ข้อ 2) ไม่ใช่ 1 อย่างที่เคยเขียน |
| `web` schema บน production | **ยังไม่มี** — ยืนยันซ้ำ `SELECT count(*) FROM pg_namespace WHERE nspname='web'` = 0 |

---

## 6. ต้องทำอะไรเพื่อปลดล็อก

```
1. เปิด session ของ Claude Code ที่โฟลเดอร์  D:\workspace\LastProject
2. อนุมัติ MCP server ชื่อ "supabase"  (URL มี read_only=true ติดมาแล้ว)
3. ล็อกอิน OAuth ด้วยบัญชีเจ้าของโปรเจกต์
4. รัน SQL สองก้อนในข้อ 4 ขั้นที่ 1
5. วาง "email_sha256" (และ same_account) กลับมาที่ session นี้
     -> ไม่ต้องวางอีเมล  ไม่ต้องวาง uid ถ้าไม่อยากเปิดเผย
6. ผมรันข้อ 4 ขั้นที่ 2 แล้วรายงาน id + is_admin
```

ถ้าได้ `same_account = false` ขั้นที่ 2 ต้องรันสองครั้ง — ครั้งละ hash
และ mapping จะมี 2 รายการ ไม่ใช่ 1

### 6.1 ทางเลือกถ้าไม่ต้องการเปิด session ใหม่

ตามที่ออกแบบไว้ใน `AUTHORIZATION_USER_MAPPING_DESIGN.md` ข้อ 5.4 ทาง 1:
**ยอมให้ `created_by` / `updated_by` เป็น NULL ทั้ง 15 แถว**

| | |
|---|---|
| ขัดกับ 005 ไหม | **ไม่** — ทั้งสองคอลัมน์เป็น nullable `ON DELETE SET NULL` อยู่แล้ว |
| เสียอะไร | ข้อมูลว่าใครเขียนเนื้อหา 15 แถวนั้น |
| กู้คืนได้ไหม | **ได้** — ข้อมูลเดิมยังอยู่ใน Supabase ไม่ได้ถูกลบ · ย้อนมาเติมภายหลังได้เมื่อมี mapping |
| ปลดล็อก data migration ได้ทันทีไหม | **ได้** |

**ไม่ตัดสินให้ในรอบนี้** — เป็นการแลกข้อมูลกับความเร็ว ซึ่งเป็นการตัดสินใจของเจ้าของ

---

## 7. บันทึกการเข้าถึงข้อมูลในรอบนี้

| ระบบ | การเข้าถึง | คำสั่ง |
|---|---|---|
| PostgreSQL (production) | **อ่านอย่างเดียว** | `SELECT` ล้วน 2 ชุด — นับจำนวน · ตรวจชนิดคอลัมน์ · ทดสอบ `digest()` ด้วยค่าตัวอย่าง |
| Supabase | **ไม่ได้เข้าถึงเลย** | — |
| ข้อมูลที่ดึงออกมา | จำนวนเต็ม · ชื่อชนิดข้อมูล · ชื่อ schema · boolean | **ไม่มีอีเมล ไม่มีชื่อ ไม่มี id ของผู้ใช้ ไม่มี hash ของอีเมลจริง** |
| คำสั่งเขียน | **ไม่มีแม้คำสั่งเดียว** | |

---

## STOP

**B2 ยัง BLOCKED** — ขาดค่าเดียวคือ hash จากฝั่ง Supabase (ข้อ 4 ขั้นที่ 1)

ฝั่งปลายทางพร้อมแล้วและพิสูจน์ได้ · เมื่อได้ hash มา เหลือ query เดียว

สองเรื่องที่ต้องตัดสิน

1. **เปิด session ที่ `D:\workspace\LastProject` เพื่อรัน SQL ขั้นที่ 1 ไหม** (ข้อ 6)
   หรือจะยอมให้ `created_by` เป็น NULL ทั้ง 15 แถวแล้วเดินหน้าต่อ (ข้อ 6.1)
2. **ข้อ 2** — คำถาม "courses กับ news เป็นบัญชีเดียวกันไหม" ยังไม่เคยถูกตอบ
   query ที่ตอบได้อยู่ในข้อ 4 แล้ว

```
Production Write   NONE        Data Migration   NONE        Deploy / Restart   NONE
Apply Migration    NONE        แก้ Supabase     NONE        Commit / Push      NONE
Merge main         NONE        Re-embed         NONE
```
