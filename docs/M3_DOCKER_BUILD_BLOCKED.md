# M3 Source Recovery Option A — Docker Build ติดขัด

> **STOP ตามคำสั่ง** — "ถ้า Docker Build หรือ Tests ไม่ผ่าน ให้ STOP และรายงานข้อผิดพลาดก่อน"
>
> Tests ผ่าน · **Docker Build เริ่มไม่ได้** เพราะปัญหาของเครื่อง ไม่ใช่ของโค้ด

| รายการ | ค่า |
|---|---|
| วันที่ | 10 ตุลาคม 2569 |
| HEAD | `dba865b` (ไม่ขยับ) |
| Commit ในรอบนี้ | **ยังไม่มี** |
| เขียนถึง production | **ไม่มีเลย** |
| สาเหตุที่หยุด | ไดรฟ์ C: เหลือพื้นที่ 33.72 MB — Docker Desktop เริ่มไม่ขึ้น |

---

## 1. ผลตรวจ Docker Engine

```
$ docker version --format 'Server {{.Server.Version}}'
Error response from daemon: Docker Desktop is unable to start
```

ไม่ใช่อาการ "กำลังบูต" แบบรอบก่อน (ซึ่งตอบ `500 Internal Server Error`) แต่เป็นการประกาศว่า **เริ่มไม่ได้**

| การตรวจ | ผล |
|---|---|
| โปรเสส `Docker Desktop` | ทำงานอยู่ 6 โปรเสส |
| โปรเสส `com.docker.backend` | ทำงานอยู่ 2 โปรเสส |
| Named pipe `dockerDesktopLinuxEngine` | มีอยู่ |
| `docker version` / `docker image ls` | **ล้มเหลว** |
| WSL distro `Ubuntu` | `Stopped` |
| WSL distro `docker-desktop` | `Stopped` |

โปรเสสขึ้นและ pipe มี แต่ VM ข้างในไม่ยอมสตาร์ท

---

## 2. สาเหตุ — ไดรฟ์ C: เต็ม

```
C: ว่าง 35,356,672 ไบต์ (33.72 MB) จากทั้งหมด 420.0 GB
```

Docker Desktop บน Windows ใช้ WSL2 ซึ่งต้อง mount และขยายไฟล์ VHDX ตอนเริ่มทำงาน เมื่อไม่มีพื้นที่เหลือ การสตาร์ท VM จึงล้ม และ distro ทั้งสองตัวค้างอยู่ที่ `Stopped`

### สัญญาณที่เคยเห็นแล้วแต่อ่านผิด

ตอนตรวจสถานะ Docker รอบก่อนหน้า คำสั่ง `wsl.exe -l -v` คืนข้อความ

```
out-lineoutput: There is not enough space on the disk.
```

ตอนนั้นประเมินว่าเป็นปัญหาการแสดงผลของ PowerShell แล้วข้ามไป — **ประเมินผิด นั่นคือสาเหตุจริง** ถ้าตามตั้งแต่ตอนนั้นจะเจอเร็วกว่านี้หนึ่งรอบ

### พื้นที่ที่ถูกใช้ไป

| โฟลเดอร์ใต้ `AppData\Local` | ขนาด |
|---|---|
| `Docker` | **21.99 GB** (ในนั้น `wsl\disk\docker_data.vhdx` 21.86 GB) |
| `Android` | 17.94 GB |
| `Programs` | 10.68 GB |
| `Roblox` | 8.57 GB |
| `Packages` | 7.68 GB |
| `NVIDIA` | 7.29 GB |
| `npm-cache` | 6.90 GB |
| `CapCut` | 6.65 GB |
| `Microsoft` | 5.35 GB |
| `Google` | 3.99 GB |

### สถานะไดรฟ์

| ไดรฟ์ | ใช้ไป | ว่าง |
|---|---|---|
| **C:** | 419.9 GB | **0.0 GB** |
| D: | 470.7 GB | **483.2 GB** |

ไดรฟ์ D: ว่างเหลือเฟือ แต่ Docker ตั้งค่าเก็บ disk image ไว้ที่ C:

---

## 3. ไม่ได้ลบหรือแก้อะไรให้

การลบไฟล์ย้อนกลับไม่ได้ และคำสั่งรอบนี้ไม่ได้อนุญาตให้ลบอะไร จึงหยุดรอการตัดสินใจ

### ทางเลือก เรียงจากเสี่ยงน้อยไปมาก

| # | ทางเลือก | คืนพื้นที่ | ความเสี่ยง |
|---|---|---|---|
| 1 | `npm cache clean --force` | ~6.9 GB | **ต่ำสุด** — แคชสร้างใหม่ได้เอง ไม่กระทบโปรเจกต์ |
| 2 | ย้าย disk image ของ Docker ไป D: | ~21.9 GB จาก C: | ต่ำ แต่ต้องทำผ่านหน้าจอ Docker Desktop เอง (Settings → Resources → Advanced → Disk image location) และใช้เวลาย้าย |
| 3 | ลบแคชของแอปที่ไม่ได้ใช้ (Roblox / CapCut / Android SDK) | สูงสุด ~33 GB | เป็นข้อมูลส่วนตัว **เจ้าของตัดสินใจเอง** |

ทางเลือก 1 สั่งได้ทันทีถ้าต้องการ · ทางเลือก 2 ต้องทำเองในหน้าจอ Docker Desktop · ทางเลือก 3 ไม่แตะโดยไม่ได้สั่ง

> ประเมินคร่าว ๆ ว่า build รอบนี้ต้องการพื้นที่ราว 1–2 GB (base image `node:22-alpine` ~180 MB + layer ของ `npm ci`) แต่ Docker Desktop ต้องสตาร์ทให้ได้ก่อน ซึ่งต้องการพื้นที่มากกว่านั้น

---

## 4. สถานะรายข้อตามคำสั่งรอบนี้

| # | งาน | ผล |
|---|---|---|
| 1 | ตรวจ Docker Engine | **ทำแล้ว — และนี่คือข้อที่ไม่ผ่าน** |
| 2 | Build image ด้วย tag แยก | ทำไม่ได้ |
| 3 | ตรวจว่า image มีไฟล์ครบ | รอข้อ 2 |
| 4 | ทดสอบ import handlers ใน image | รอข้อ 2 |
| 5 | รัน regression tests | **ผ่าน 82/82** |
| 6 | ตรวจ git diff และ secret scan | **เสร็จแล้ว** |
| 7 | Commit README และรายงาน | รอการตัดสินใจ (ดูข้อ 6 ด้านล่าง) |
| 8 | อัปเดต preflight classification | รอข้อ 2–4 |
| 9 | สรุป commit hash และสิ่งที่ค้าง | เอกสารฉบับนี้ |

---

## 5. สิ่งที่ยืนยันได้แล้วโดยไม่ต้อง build

### Source จริงครบ ไม่ใช่ stub

```
ไฟล์ใน api/ : 10
symlink     : 0
hash รวม    : 2b67e0f4a9dc9fd9f47231d93eaff12903d962d0e8d430f3347dbe52cafa8fcd
```

ตรงกับค่าที่สำรองมาจาก production ทุกไบต์

### Build context มีครบตามที่ Dockerfile ต้องใช้

| `COPY` | ไฟล์ที่มีจริง |
|---|---|
| `COPY package.json package-lock.json ./` | ครบ 2 |
| `COPY api ./api` | **ครบ 10** (ก่อนกู้คืนไม่มีเลย = build ล้มแน่นอน) |
| `COPY server.mjs auth.mjs db.mjs ./` | ครบ 3 |

### Node import ผ่านแล้ว

ทั้ง 5 handler โหลดได้และมี `export default.fetch` เป็น function ครบ — ทดสอบนอก container แล้ว เหลือยืนยันซ้ำใน image

### Regression tests

```
ℹ tests 82
ℹ pass 82
ℹ fail 0
```

---

## 6. ไฟล์ที่พร้อม commit แล้ว

```
 M webapi/README.md
?? docs/M3_PRODUCTION_ROLLOUT_PREFLIGHT.md
?? docs/M3_WEBAPI_SOURCE_RECOVERY_RESULT.md
```

ผ่านการตรวจครบแล้ว:

| การตรวจ | ผล |
|---|---|
| JWT / `sk-` / `AIza` / private key | ไม่พบ |
| connection string ที่มีรหัสผ่าน | ไม่พบ |
| `password=` ที่เป็นค่าจริง | ไม่พบ |
| อีเมล | ไม่พบ |
| UUID เต็ม | ไม่พบ (ปิดค่าที่เคยมีในรายงาน preflight แล้ว) |
| `webapi/api/` จะเข้า git ไหม | **ไม่** — `.gitignore:49` ยังครอบอยู่ |

### ข้อเสนอ

**สาม ไฟล์นี้ไม่ได้ขึ้นกับผล `docker build` เลย** เป็นเอกสารและ README ล้วน ๆ จึง commit แยกออกมาก่อนได้โดยไม่ต้องรอเรื่องดิสก์ แล้วค่อยยืนยัน build กับอัปเดต preflight classification ในรอบถัดไป

ถ้าต้องการให้รอ build ก่อนตาม STRICT เดิมก็ได้เช่นกัน — แจ้งมาได้

---

## 7. สิ่งที่ยังค้างทั้งหมด

### ค้างเพราะดิสก์เต็ม

- `docker build` ด้วย source จริง (ใช้ tag แยก ไม่ทับ production)
- ตรวจไฟล์ใน image และ import handlers ใน container
- อัปเดต preflight classification จาก `BLOCKED` เป็นสถานะใหม่

### ค้างรออนุมัติแยก (จาก preflight)

| # | งาน | หมายเหตุ |
|---|---|---|
| 1 | `docker tag course-advisor-system-webapi:latest …:rollback-pre-m3` | เป็นการเขียนสถานะ docker **บน production** คำสั่งปัจจุบันยังไม่อนุญาต · webapi มีแค่ tag `latest` ตัวเดียว ถ้า build ทับโดยไม่ติด tag ก่อน จะไม่มีอะไรให้ย้อนกลับ |
| 2 | เตรียมบัญชี admin ที่ `approved` | ข้อเดียวที่พิสูจน์ว่า authorization foundation ไม่ล็อกผู้ดูแลออก |
| 3 | สร้าง `ADVISOR_WEB_PASSWORD` ใส่ production `.env` | ขั้น deploy |
| 4 | คัดลอก `package-lock.json` ขึ้นเซิร์ฟเวอร์ | เซิร์ฟเวอร์ยังไม่มีไฟล์นี้ และ Dockerfile ใหม่ใช้ `npm ci` ซึ่งบังคับต้องมี |
| 5 | ยืนยันว่าสคริปต์ deploy จริงไม่ลบ `webapi/api/` ทิ้ง | README มีขั้นตอนแล้ว เหลือตรวจตัวสคริปต์ |

### ค้างระยะยาว

- เปลี่ยน UUID ใน `webapi/auth.test.mjs:480` เป็นค่าสังเคราะห์ (แก้ไฟล์ไม่ลบค่าออกจากประวัติ git)
- เขียน `docs/DEPLOY_WEB.md` หรือลบการอ้างอิงใน `docker-compose.prod.yml:169`
- เพิ่ม `.dockerignore` — ตอนนี้ `node_modules/` ในเครื่องถูกส่งเข้า build context ทั้งก้อน
- ถอด `requireAdminUser` ออกจาก handler เมื่อมั่นใจด่านกลางแล้ว (ตอนนี้ `/api/admin/*` เรียก Supabase สองรอบต่อคำขอ)

---

## 8. ยืนยันว่าไม่มีอะไรเสียหาย

| รายการ | สถานะ |
|---|---|
| HEAD | `dba865b` ไม่ขยับ |
| Commit / Push / Merge | **ไม่มี** |
| Deploy / Restart production | **ไม่มี** |
| แก้ production `.env` | **ไม่มี** |
| เขียน production database / Supabase | **ไม่มี** |
| ลบหรือเขียนทับไฟล์บน production | **ไม่มี** |
| `webapi/api/` เข้า git | **ไม่** |
| ลบไฟล์บนเครื่อง local | **ไม่มี** |
