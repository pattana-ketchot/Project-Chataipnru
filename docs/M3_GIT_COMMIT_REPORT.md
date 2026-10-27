# รายงานการ Commit งานจนถึง M3

| รายการ | ค่า |
|---|---|
| Worktree | `D:\workspace\course-advisor-system-mko2` |
| Branch | `mko-phase2` |
| HEAD ก่อนเริ่ม | `cf4fb16` feat: add webapi authorization foundation |
| HEAD หลังเสร็จ | `dba865b` |
| จำนวน commit ที่สร้าง | 4 |
| สถานะเทียบ remote | `mko-phase2` นำหน้า `origin/mko-phase2` อยู่ 6 commits (ของรอบนี้ 4 + ของเดิม 2) |
| `origin/mko-phase2` | ยังอยู่ที่ `dc5e860` — **ไม่ได้ push** |

**ขอบเขตที่ได้รับอนุมัติ:** Commit เท่านั้น · ห้าม Push / Merge / Deploy / Restart Production / แก้ production `.env` / เขียน Production Database / เขียน Supabase / แตะ Frontend Repository — **ปฏิบัติครบทุกข้อ**

---

## 1. Commit ที่สร้าง

### 1.1 `20fb2c2` — feat(db): add migration 006 for web identity mapping

8 ไฟล์ · +4,418 บรรทัด

| ไฟล์ | สถานะ | บรรทัด |
|---|---|---|
| `db/migrations/006_web_identity_mapping.sql` | ใหม่ | +148 |
| `db/20-roles.sh` | แก้ | +46 |
| `eval/web_identity_mapping_check.py` | ใหม่ | +525 |
| `docs/B1_ADVISOR_WEB_ROLE_DESIGN.md` | ใหม่ | +897 |
| `docs/B1_ADVISOR_WEB_PROVISION_RESULT.md` | ใหม่ | +1,083 |
| `docs/MIGRATION_006_IDENTITY_MAPPING_REVIEW.md` | ใหม่ | +802 |
| `docs/MIGRATION_006_PRODUCTION_PREAPPLY.md` | ใหม่ | +442 |
| `docs/MIGRATION_006_PRODUCTION_APPLY_RESULT.md` | ใหม่ | +475 |

เนื้อหา: เพิ่มคอลัมน์ `supabase_user_id UUID` (nullable ไม่มี default ไม่มี FK) ลง `public.users` พร้อม partial unique index `uq_users_supabase_user_id` และ GRANT ระดับคอลัมน์ให้ `advisor_web` · `20-roles.sh` เพิ่มการสร้าง role `advisor_web` แบบข้ามอย่างมีเสียงเมื่อไม่ได้ตั้ง `ADVISOR_WEB_PASSWORD` (ไม่ให้สิทธิ์ตารางในไฟล์นี้ตามหลัก role = infrastructure, grant = migration)

### 1.2 `b989221` — docs(auth): record S1 identity mapping design and production apply

5 ไฟล์ · +3,163 บรรทัด

| ไฟล์ | บรรทัด |
|---|---|
| `docs/AUTHORIZATION_USER_MAPPING_DESIGN.md` | +715 |
| `docs/B1_ACTIVE_USER_MAPPING_DESIGN.md` | +807 |
| `docs/B1_ACTIVE_USER_MAPPING_FINAL_DECISION.md` | +705 |
| `docs/B1_S1_IDENTITY_MAPPING_PREAPPLY.md` | +570 |
| `docs/B1_S1_IDENTITY_MAPPING_APPLY_RESULT.md` | +366 |

### 1.3 `59f9c3b` — fix(webapi): carry identity per request instead of shared closure state

3 ไฟล์ · +957 −59

| ไฟล์ | สถานะ | บรรทัด |
|---|---|---|
| `webapi/auth.mjs` | แก้ | +112 / −59 |
| `webapi/auth.test.mjs` | แก้ | +108 |
| `docs/B1_AUTHORIZATION_PHASE1_IMPLEMENTATION.md` | ใหม่ | +796 |

เนื้อหา: ถอด `let lastIdentity` ที่ใช้ร่วมกันทุกคำขอใน `createRuntimeDeps` ออก — คำขอสองรายการที่ทับเวลากันเคยทับ identity ของกันเอง ทำให้ผู้ใช้ที่มีสิทธิ์ถูกปฏิเสธแบบสุ่ม · เปลี่ยนเป็นส่ง identity ไปกับค่าที่คืนจาก `verifyToken` แล้ว `resolveAuthContext` ส่งต่อให้ `readProfile` เอง · `resolveAuthorId` และ `authorFieldsFor` กลายเป็น async และรับ resolver เข้ามา

### 1.4 `dba865b` — feat(webapi): connect to PostgreSQL for Supabase identity resolution (M3)

11 ไฟล์ · +3,856 −5

| ไฟล์ | สถานะ | บรรทัด |
|---|---|---|
| `webapi/db.mjs` | ใหม่ | +254 |
| `webapi/db.test.mjs` | ใหม่ | +364 |
| `webapi/package-lock.json` | ใหม่ | +867 |
| `webapi/server.mjs` | แก้ | +61 |
| `webapi/server.test.mjs` | แก้ | +38 |
| `webapi/package.json` | แก้ | +1 (`pg ^8.23.1`) |
| `webapi/Dockerfile` | แก้ | +11 / −5 |
| `docker-compose.prod.yml` | แก้ | +21 |
| `docs/B1_M3_POSTGRES_CONNECTION_DESIGN.md` | ใหม่ | +626 |
| `docs/M3_WEBAPI_POSTGRES_CONNECTION_DESIGN.md` | ใหม่ | +817 |
| `docs/M3_WEBAPI_POSTGRES_IMPLEMENTATION_RESULT.md` | ใหม่ | +801 |

เนื้อหา: pool + identity resolver ที่อ่าน `public.users` ได้แค่ 3 คอลัมน์ในนาม `advisor_web` · `/healthz` รายงาน `dbConfigured` และ `db` โดยไม่ล้มเมื่อฐานข้อมูลล่ม · ปิดอย่างเรียบร้อยด้วย SIGTERM/SIGINT พร้อม hard stop 10 วินาที · Dockerfile เปลี่ยนเป็น `npm ci` กับ lock file ที่ไม่ใช่ glob และคัดลอก `db.mjs` เข้า image · compose เพิ่ม `depends_on: service_healthy` และ env 5 ตัวโดยแยกค่าลับออกจากค่าที่ไม่ลับ

ทุก commit มี trailer `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>` ครบ

---

## 2. ผลการตรวจตามเงื่อนไข

| # | เงื่อนไข | ผล |
|---|---|---|
| 1 | ตรวจ `git status` และ `git diff` ก่อน | ผ่าน — ตรวจครบ 8 modified + คัดจาก 80 untracked |
| 2 | แยก commit ตามขอบเขตงาน | ผ่าน — 4 ชุดตามที่กำหนด |
| 3 | `git add` ระบุไฟล์เท่านั้น | ผ่าน — ไม่ใช้ `git add .` เลย |
| 4 | ไม่มี password / token / UUID ผู้ใช้ / production `.env` | ผ่าน — ดูข้อ 2.1 |
| 5 | ไม่มี stub หรือไฟล์ทดสอบชั่วคราว | ผ่าน — ดูข้อ 2.2 |
| 6 | รัน tests ซ้ำก่อน commit | ผ่าน — ดูข้อ 2.3 |
| 7 | Commit เฉพาะไฟล์ที่ตรวจแล้ว | ผ่าน — เหลือ 61 untracked ที่ไม่แตะ |
| 8 | รายงาน commit hashes และ `git status` | เอกสารฉบับนี้ |

### 2.1 การสแกนความลับ

สแกนด้วย regex ครอบคลุม `password=`, `secret=`, `api_key=`, JWT (`eyJ…`), connection string ที่มีรหัสผ่านฝัง, `sk-…`, `AIza…`, private key header และ UUID เต็มรูปแบบ

สิ่งที่ regex จับได้ ตรวจรายตัวแล้วปลอดภัยทั้งหมด:

| ที่พบ | ไฟล์ | เหตุผลที่ปลอดภัย |
|---|---|---|
| `CREATE ROLE … PASSWORD :'web_password'` | `db/20-roles.sh` | ตัวแปร psql ไม่ใช่ค่า |
| `${ADVISOR_WEB_PASSWORD}` | `docker-compose.prod.yml`, เอกสาร | variable reference |
| `postgresql://postgres:x@127.0.0.1:55406/web_test` | `MIGRATION_006_IDENTITY_MAPPING_REVIEW.md` | คอนเทนเนอร์ทิ้งที่ลบไปแล้ว |
| `read -rsp 'ADVISOR_WEB_PASSWORD: '` | `M3_*` | คำสั่งที่ **ถาม** รหัสผ่าน ไม่มีค่าฝัง |
| `"ไม่ใช่รหัสผ่านจริง"` | `webapi/db.test.mjs` | ค่าทดสอบที่ชื่อบอกตัวเอง |
| `11111111-2222-3333-4444-555555555555` | `webapi/db.test.mjs` | UUID สังเคราะห์ |
| `public-web@stpnru.local` | `AUTHORIZATION_USER_MAPPING_DESIGN.md` | บัญชีระบบที่ `web_compat.py::shared_user` สร้างเอง โดเมน `.local` |
| `test@example.com` | เอกสาร | โดเมนสงวนตาม RFC 2606 |

**ไม่พบ** production `.env`, JWT, API key, private key หรือ UUID ของผู้ใช้จริงในไฟล์ที่ commit

### 2.2 Stub และไฟล์ชั่วคราว

- `webapi/node_modules/` ถูก `.gitignore` ครอบอยู่ (`.gitignore:2`) ไม่เข้า staged
- `webapi/node_modules/pg` เป็นแพ็กเกจจริงรุ่น 8.23.1 ไม่ใช่ stub ที่สร้างไว้ตอนทดสอบ harness
- `git status` ไม่มีไฟล์ `.tmp` `.bak` `__pycache__` หรือชื่อที่มีคำว่า stub/scratch

### 2.3 การทดสอบ

| ชุด | ผล |
|---|---|
| `node --test` ใน `webapi/` ก่อน commit | **82/82 ผ่าน** |
| `node --test auth.test.mjs` ตอน `59f9c3b` (ยังไม่มี `db.mjs`) | **46/46 ผ่าน** |
| `node --test` ใน `webapi/` หลัง commit ครบ 4 ชุด | **82/82 ผ่าน** |
| `python -m py_compile eval/web_identity_mapping_check.py` | ผ่าน |
| `bash -n db/20-roles.sh` | ผ่าน |

ตรวจแยกว่า `auth.test.mjs` ผ่านได้ด้วยตัวเองตอน `59f9c3b` เพื่อให้แต่ละ commit เขียวในตัวมันเอง ไม่ใช่เขียวเฉพาะตอนครบชุด

### 2.4 ยืนยัน migration ตรงกับที่ apply จริง

```
sha256(db/migrations/006_web_identity_mapping.sql)
  = fb22346bf651312a9025c0553fcb8f2637751633cfd1ae2b6f302e4bdc203376
```

ตรงกับค่าที่บันทึกไว้ตอน apply ขึ้น production และตรงกับที่อ้างใน `MIGRATION_006_PRODUCTION_APPLY_RESULT.md` — ไฟล์ที่ commit คือไฟล์เดียวกับที่รันจริง

---

## 3. การแก้ไขระหว่างทาง

แก้ 1 จุดก่อน commit: `webapi/auth.mjs` มีคอมเมนต์ค้างเก่าเหนือ `authorFieldsFor` ว่า *"ตอนนี้คืน ok: false ทุกครั้งเพราะ resolveAuthorId ยังทำงานไม่ได้"* ซึ่งขัดกับพฤติกรรมใหม่ตั้งแต่ M3 เปลี่ยนเป็นอธิบายว่าต้องส่ง resolver มาด้วย ไม่งั้นจะปฏิเสธด้วย `ACTIVE_USER_MAPPING_REQUIRED` — คอมเมนต์ที่โกหกเรื่องพฤติกรรมถือเป็นข้อบกพร่อง จึงแก้ก่อนแทนที่จะ commit ทับไป

---

## 4. เรื่องที่ต้องรายงาน (มีอยู่ก่อนแล้ว ไม่ได้บล็อกการ commit)

### 4.1 UUID ที่น่าจะมาจาก production อยู่ใน test fixture

`webapi/auth.test.mjs:480` ใช้ค่า `3fe27ab3-0000-0000-0000-ba0118c3eceb` เป็น `userId` ในเทสต์ "describeForLog ไม่มี token อีเมล หรือ uuid ของผู้ใช้"

หัวกับท้ายของค่านี้ตรงกับ path ไฟล์จริงบน Supabase Storage ที่บันทึกไว้ใน `docs/SUPABASE_LIVE_VERIFICATION.md:554` (`course-assets/faculty/3fe27ab3-...-ba0118c3eceb.png`) คือเป็น UUID จริงที่ลบเฉพาะตรงกลาง เหลือ hex จริง 20 จาก 32 ตัว

**สถานะ:** อยู่ใน HEAD ตั้งแต่ commit ก่อนหน้า ไม่ได้อยู่ใน diff รอบนี้ และ `docs/SUPABASE_LIVE_VERIFICATION.md` ถูก track ไปแล้วเช่นกัน ประวัติ git จึงมีค่านี้อยู่แล้ว

**ข้อเสนอ:** เปลี่ยนเป็นค่าสังเคราะห์ในรอบแก้ถัดไป แต่ต้องเข้าใจว่าการแก้ไฟล์ไม่ลบค่าออกจากประวัติ

### 4.2 เอกสารอ้างถึงไฟล์ที่ไม่มีอยู่

`docker-compose.prod.yml:169` อ้าง `docs/DEPLOY_WEB.md` ซึ่งไม่มีในรีโป เป็นบรรทัดเดิมที่ไม่ได้อยู่ใน diff รอบนี้

---

## 5. สถานะหลังทำ

```
On branch mko-phase2
Your branch is ahead of 'origin/mko-phase2' by 6 commits.

Modified:  0
Untracked: 61
```

ไฟล์ untracked ที่เหลือไม่ได้แตะเลย เพราะอยู่นอกขอบเขต M3 และเป็นงานจากรอบก่อนที่ยืนยันเนื้อหาไม่ได้:

| กลุ่ม | จำนวน |
|---|---|
| `docs/SLIDE_*` | 14 |
| `docs/AUTOMATED_INGESTION_*` | 9 |
| `docs/PHASE3D_*` | 7 |
| `docs/ER_DIAGRAM_*` | 6 |
| `docs/MIGRATION_005_*` | 5 |
| `docs/CRAWLER_*` | 4 |
| `docs/CHAT_*` | 3 |
| `docs/B2_*` | 3 |
| `docs/FRONTEND_*` | 2 |
| อื่น ๆ (รวม `docs/database/`) | 8 |

---

## 6. งานที่ยังค้าง (ต้องรออนุมัติแยก)

1. Push `mko-phase2` ขึ้น remote
2. เพิ่ม `ADVISOR_WEB_PASSWORD` ลง production `.env`
3. Deploy M3 (ต้อง build image ใหม่ — image ของ webapi บน production ยังเก่ากว่า `cf4fb16` การ deploy รอบนี้จะพา authorization foundation ขึ้นไปเป็นครั้งแรกด้วย)
4. สร้าง write endpoints เพื่อปิด `G3_API_ENFORCEMENT_PENDING_B1`
5. ตัดสินใจเรื่อง UUID ในข้อ 4.1
