# M3 — WebAPI Source Recovery · ทางเลือก A · ความคืบหน้า

> **ยังทำไม่ครบ** — เหลือ 4 ข้อที่รอ Docker engine บูตเสร็จ · ยังไม่ได้ commit อะไรเลย

| รายการ | ค่า |
|---|---|
| มติเจ้าของ | ทางเลือก **A** — คง `webapi/api/` ใน `.gitignore` ใช้ไฟล์สำรองเป็นหลักประกัน |
| HEAD | `dba865b` (ไม่ขยับ) |
| Branch | `mko-phase2` · นำหน้า `origin/mko-phase2` 6 commits |
| Commit ในรอบนี้ | **ยังไม่มี** |
| เขียนถึง production | **ไม่มีเลย** |

---

## สถานะรายข้อ

| # | งาน | สถานะ |
|---|---|---|
| 1 | คง `webapi/api/` ใน `.gitignore` | **เสร็จ** |
| 2 | ไม่นำโค้ดทีม frontend เข้า backend repo | **เสร็จ** |
| 3 | ใช้ไฟล์สำรองที่ตรวจ SHA256 แล้ว | **เสร็จ** |
| 4 | อัปเดต `webapi/README.md` | **เสร็จ** |
| 5 | แก้รายงาน preflight ให้ตรงข้อเท็จจริง | **เสร็จ** |
| 6 | เปิด Docker Desktop แล้ว build image ทดสอบ | **ค้าง — engine กำลังบูต** |
| 7 | รัน regression tests | **เสร็จ — 82/82 ผ่าน** |
| 8 | ตรวจว่า build ผ่านและ import handler ครบ | **ค้าง — รอข้อ 6** |
| 9 | Commit README และรายงานที่เกี่ยวข้อง | **ค้าง — รอข้อ 8** |
| 10 | อัปเดตผล preflight และรายงานสิ่งที่ค้าง | **ค้าง — รอข้อ 8** |

---

## 1–2. คงข้อตกลงเดิมไว้

ไม่แตะ `.gitignore` เลย กฎ `webapi/api/` ที่บรรทัด 49 ยังอยู่ตามเดิม ตรวจยืนยันว่ายังทำงาน:

```
$ git check-ignore -v webapi/api/_lib/rag.js
.gitignore:49:webapi/api/	webapi/api/_lib/rag.js

$ git status --porcelain webapi/
 M webapi/README.md
```

git เห็นเฉพาะ `README.md` ที่แก้ — **ไฟล์ทั้ง 10 ใน `api/` ไม่เข้า git** ตามมติ

---

## 3. ไฟล์สำรองที่ใช้

| รายการ | ค่า |
|---|---|
| ไฟล์ | `D:/workspace/webapi-api-backup-20261009T204112.tar.gz` (6,242 ไบต์) |
| ที่มา | `/home/ubuntu/course-advisor-system/webapi/api/` |
| จำนวน | 10 ไฟล์ · 3 โฟลเดอร์ · **0 symlink** · 30,836 ไบต์ |
| SHA256 รวม | `2b67e0f4a9dc9fd9f47231d93eaff12903d962d0e8d430f3347dbe52cafa8fcd` |

ตรวจซ้ำก่อนเตรียม build — ได้ค่าเดียวกันเป๊ะ ไฟล์ที่วางอยู่ใน `webapi/api/` คือ source จริงจาก production ไม่ใช่ stub

---

## 4. `webapi/README.md` — เพิ่ม 4 หัวข้อ (97 → 163 บรรทัด)

| หัวข้อที่เพิ่ม | เนื้อหา |
|---|---|
| ถ้าไม่มีรีโปของทีมออกแบบ — ใช้ไฟล์สำรอง | ตาราง path / ที่มา / วันที่ / จำนวนไฟล์ / SHA256 รวม + คำสั่ง `tar -xzf` กู้คืน |
| ตรวจ SHA256 ก่อน build ทุกครั้ง | สามคำสั่ง — นับไฟล์ให้ได้ 10, symlink ให้ได้ 0, เทียบ hash รวม |
| ขั้นตอน build | บังคับตรวจ `api/` ก่อน และ build ด้วย tag ที่มีเวอร์ชัน ไม่ใช่ `latest` เปล่า |
| ติด rollback tag ก่อน build ทับ | `docker tag … :rollback-pre-<ชื่องาน>` แล้วยืนยันด้วย `docker images` |

เขียนกำกับไว้ชัดว่า **ไฟล์สำรองเป็นของกู้คืน ไม่ใช่แหล่งต้นทาง** — แหล่งต้นทางยังเป็นรีโปของทีมออกแบบ ถ้าทีมนั้นแก้โค้ด สำเนานี้จะเก่าทันที ให้ใช้วิธี `cp` เป็นหลักเสมอ

### กับดักที่บันทึกไว้ใน README ด้วย

ค่า hash รวมต้องคำนวณจาก **ค่า hash ของแต่ละไฟล์** ไม่ใช่จาก output ดิบของ `sha256sum`

เหตุผล: บน Windows คำสั่งนั้นใส่ `*` นำหน้าชื่อไฟล์ (binary mode) แต่บน Linux ใส่ช่องว่างสองตัว ถ้าเอา output ดิบไป hash ต่อ ค่าจะไม่ตรงกันข้ามระบบปฏิบัติการทั้งที่เนื้อไฟล์เหมือนกันทุกไบต์ — ผมเจอเองตอนเทียบ production กับ local รอบแรก

---

## 5. แก้รายงาน preflight

แทรกหมายเหตุแก้ไข 2 จุดใน `M3_PRODUCTION_ROLLOUT_PREFLIGHT.md`

**จุดที่ 1 — ตารางข้อ 5.1** เคยเขียนว่า `webapi/api/` ไม่ถูก gitignore ซึ่งผิด แก้เป็น **ใช่ `.gitignore:49`** พร้อมอธิบายว่าทำไมถึงตรวจพลาด: รัน `git check-ignore` ขณะโฟลเดอร์ยังไม่มีอยู่ กฎปิดท้ายด้วย `/` จึงตรงกับไดเรกทอรีเท่านั้น ไม่มีไดเรกทอรีก็ไม่คืนอะไร แล้วผมอ่านผลว่างว่า "ไม่ถูก ignore"

**จุดที่ 2 — ข้อ 5.2** เหตุผลที่บล็อก ข้อ 1 กับ 3 ยังจริงแต่ต้องอ่านใหม่ว่าข้อ 1 เป็นพฤติกรรมที่ตั้งใจไม่ใช่ข้อบกพร่อง · ข้อ 2 แก้แล้วด้วยไฟล์สำรอง · บันทึกมติทางเลือก A ไว้

---

## 7. Regression tests

```
ℹ tests 82
ℹ pass 82
ℹ fail 0
```

รันหลังนำ source จริงเข้ามาแล้ว ได้เท่าเดิมทุกข้อ การกู้คืนไม่กระทบชุดทดสอบ

---

## 6. Docker — สิ่งที่พบและสิ่งที่ทำ

**Docker Desktop ไม่ได้เปิดอยู่จริงตอนเริ่มงาน** ตรวจแล้วไม่มีโปรเสส ไม่มี `com.docker.service` ไม่มี named pipe เลย

ข้อ 6 สั่งให้เปิด จึงเปิดให้ — ตัวติดตั้งอยู่ที่ `C:\Users\User\AppData\Local\Programs\DockerDesktop\Docker Desktop.exe` ไม่ใช่ใน `Program Files` ตามปกติ (Docker Desktop 4.86.0 ติดตั้งแบบ per-user)

สถานะล่าสุด: โปรเสสขึ้นครบ · named pipe พร้อม · แต่ engine ยังตอบ `500 Internal Server Error` เพราะ Linux VM กำลังบูต ตั้งตัวรอแบบมีเงื่อนไขไว้แล้ว จะทำข้อ 6 ต่อทันทีที่ `docker image ls` สำเร็จ

### สิ่งที่ตรวจแทนได้แล้วโดยไม่ต้อง build

| `COPY` ใน Dockerfile | มีครบใน build context |
|---|---|
| `COPY package.json package-lock.json ./` | ครบ 2 |
| `COPY api ./api` | **ครบ 10** (ก่อนกู้คืนไม่มีเลย = build ล้มแน่) |
| `COPY server.mjs auth.mjs db.mjs ./` | ครบ 3 |

Node import ทั้ง 5 handler ผ่านแล้วตั้งแต่รอบก่อน — `export default.fetch = function` ครบทุกตัว

---

## 9. เตรียมไว้แล้ว — ตรวจก่อน commit

ไฟล์ที่จะ commit เมื่อข้อ 8 ผ่าน:

```
 M webapi/README.md
?? docs/M3_PRODUCTION_ROLLOUT_PREFLIGHT.md
?? docs/M3_WEBAPI_SOURCE_RECOVERY_RESULT.md
```

### ผลสแกนความลับ

| สิ่งที่สแกน | ผล |
|---|---|
| JWT / `sk-` / `AIza` / private key | ไม่พบ |
| connection string ที่มีรหัสผ่าน | ไม่พบ |
| `password=` ที่เป็นค่าจริง | ไม่พบ |
| อีเมล | ไม่พบ |
| UUID เต็ม | **พบ 1 จุด → ปิดค่าแล้ว** |

**จุดที่แก้:** `M3_PRODUCTION_ROLLOUT_PREFLIGHT.md` ข้อ 8.1 แสดงค่า UUID ที่ลบตรงกลางไว้ออกมาเต็ม ๆ ในเนื้อรายงาน ซึ่งขัดกับกฎ "ห้ามแสดง UUID เต็มในรายงานถ้าไม่จำเป็น" ที่ตั้งไว้ตั้งแต่รอบ S1 — เปลี่ยนเป็นอธิบายลักษณะของค่าและชี้ตำแหน่งไฟล์แทน สแกนซ้ำแล้วทั้งสามไฟล์ไม่มี UUID เหลือ

> `docs/M3_GIT_COMMIT_REPORT.md` **ไม่รวมใน commit นี้** เพราะเป็นรายงานสถานะ git ของรอบก่อน ถ้า commit ตัวมันเองเนื้อหาจะไม่ตรงกับสิ่งที่มันบรรยายทันที

---

## สิ่งที่ยังค้าง

### ค้างในงานรอบนี้

| # | งาน | ติดอะไร |
|---|---|---|
| 6 | `docker build` ด้วย source จริง ใช้ tag ทดสอบแยก | รอ Linux VM บูตเสร็จ |
| 8 | ยืนยันผล build และ import handler ใน image | รอข้อ 6 |
| 9 | Commit 3 ไฟล์ | รอข้อ 8 |
| 10 | อัปเดตผล preflight เป็นสถานะใหม่ | รอข้อ 8 |

### ค้างจาก preflight — ต้องขออนุมัติแยก

| # | งาน | หมายเหตุ |
|---|---|---|
| 1 | `docker tag course-advisor-system-webapi:latest …:rollback-pre-m3` บน production | **เป็นการเขียนสถานะ docker บน production** คำสั่งรอบนี้ยังไม่อนุญาต |
| 2 | เตรียมบัญชี admin ที่ `approved` ไว้ทดสอบ smoke test | ข้อเดียวที่พิสูจน์ว่า authorization foundation ไม่ล็อกผู้ดูแลออก |
| 3 | สร้าง `ADVISOR_WEB_PASSWORD` ใส่ production `.env` | ขั้น deploy |
| 4 | คัดลอก `package-lock.json` ขึ้นเซิร์ฟเวอร์ | เซิร์ฟเวอร์ยังไม่มี และ `npm ci` ต้องใช้ |
| 5 | กำหนดวิธี deploy ที่ไม่ลบ `webapi/api/` ทิ้ง | README มีขั้นตอนแล้ว เหลือยืนยันว่าสคริปต์ deploy จริงทำตาม |

### ค้างระยะยาว

- เปลี่ยน UUID ใน `webapi/auth.test.mjs:480` เป็นค่าสังเคราะห์ (แก้ไฟล์ไม่ลบค่าออกจากประวัติ git)
- เขียน `docs/DEPLOY_WEB.md` หรือลบการอ้างอิงใน `docker-compose.prod.yml:169`
- เพิ่ม `.dockerignore` เพื่อไม่ให้ `node_modules/` เข้า build context
- ถอด `requireAdminUser` ออกจาก handler เมื่อมั่นใจด่านกลางแล้ว (ตอนนี้เรียก Supabase สองรอบต่อคำขอ)
