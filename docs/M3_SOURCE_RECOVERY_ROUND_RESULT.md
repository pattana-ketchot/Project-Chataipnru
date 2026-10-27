# M3 Source Recovery Option A — ผลการดำเนินงานรอบปิด

> สรุปรอบที่ทำต่อจากจุดที่ค้าง · **ไม่แตะ production** · ไม่ push · ไม่ merge · ไม่ deploy

## ผลสรุป

# `M3_SOURCE_RECOVERY_READY`
# Preflight: `M3_ROLLOUT_PREFLIGHT_BLOCKED` → `M3_ROLLOUT_PREFLIGHT_READY`

| รายการ | ค่า |
|---|---|
| วันที่ | 10 ตุลาคม 2569 |
| Commit ที่สร้าง | **`427ce190325267d6418692d905e2c8837e03c306`** |
| ข้อความ | `docs(webapi): document api/ source recovery and verify M3 build` |
| ไฟล์ | 4 ไฟล์ · +1,148 บรรทัด |
| HEAD ก่อน | `dba865b` |
| HEAD หลัง | `427ce19` |
| Branch | `mko-phase2` · นำหน้า `origin/mko-phase2` **7 commits** |

---

## สถานะรายข้อตามคำสั่ง

| # | งาน | ผล |
|---|---|---|
| 1 | ตรวจ Docker Engine อีกครั้ง | ผ่าน (หลังแก้ดิสก์และ restart) |
| 2 | Build image ด้วย source จริง tag แยก | **ผ่าน** — `webapi-m3-localtest:dba865b` |
| 3 | ตรวจว่า image มีไฟล์ครบ | **ผ่าน** — `server.mjs`, `auth.mjs`, `db.mjs`, `api/` 10 ไฟล์ |
| 4 | ทดสอบ import handlers ใน image | **ผ่าน 7/7** |
| 5 | รัน regression tests ซ้ำ | **ผ่าน 82/82** |
| 6 | ตรวจ git diff และ secret scan | **ผ่าน** — ไม่พบความลับ |
| 7 | Commit README และรายงาน | **เสร็จ** — `427ce19` |
| 8 | อัปเดต preflight classification | **เสร็จ** — เป็น `READY` พร้อมเงื่อนไข 2 ข้อ |
| 9 | สรุป commit hash และสิ่งที่ค้าง | เอกสารฉบับนี้ |

> **หมายเหตุลำดับ:** สลับข้อ 7 กับ 8 โดยตั้งใจ — อัปเดต classification ก่อนแล้วค่อย commit ทีเดียว ถ้าทำตามลำดับเดิมจะต้อง commit รายงานแล้วแก้ทับทันที ทำให้ commit แรกบรรยายสถานะที่ไม่จริง

---

## ไฟล์ใน commit `427ce19`

| ไฟล์ | สถานะ | เนื้อหา |
|---|---|---|
| `webapi/README.md` | แก้ (+64) | ที่มาของ source · ไฟล์สำรองพร้อม SHA256 · ขั้นตอน restore · การตรวจก่อน build · ขั้นตอน build ที่บังคับติด rollback tag |
| `docs/M3_WEBAPI_SOURCE_RECOVERY_RESULT.md` | ใหม่ | รายงานการกู้คืน 12 ขั้น |
| `docs/M3_BUILD_VERIFICATION_RESULT.md` | ใหม่ | รายงานผล build และการแก้ปัญหาดิสก์ |
| `docs/M3_PRODUCTION_ROLLOUT_PREFLIGHT.md` | ใหม่ | preflight ฉบับแก้แล้ว classification ใหม่ |

### ที่ไม่ได้ commit โดยตั้งใจ

| ไฟล์ | เหตุผล |
|---|---|
| `webapi/api/` (10 ไฟล์) | **มติทางเลือก A** — `.gitignore:49` ยังครอบอยู่ · ยืนยันหลัง commit แล้วว่า `git ls-files webapi/api` = **0 ไฟล์** |
| `docs/M3_GIT_COMMIT_REPORT.md` | รายงานสถานะ git ของรอบก่อน ถ้า commit เนื้อหาจะไม่ตรงกับที่บรรยายทันที |
| `docs/M3_DOCKER_BUILD_BLOCKED.md` | รายงานสถานะชั่วคราวที่ถูกแทนที่ด้วย `M3_BUILD_VERIFICATION_RESULT.md` แล้ว |
| `docs/M3_SOURCE_RECOVERY_OPTION_A_PROGRESS.md` | รายงานความคืบหน้าระหว่างทาง ถูกแทนที่ด้วยฉบับนี้ |
| อีก 60 ไฟล์ | นอกขอบเขต เป็นงานรอบก่อนที่ยืนยันเนื้อหาไม่ได้ |

---

## การแก้ปัญหาพื้นที่ดิสก์

ได้รับอนุมัติให้ล้าง **npm cache อย่างเดียว**

| | ก่อน | หลัง | ผล |
|---|---|---|---|
| C: ว่าง | 32.31 MB | **6.33 GB** | +6.30 GB |
| npm cache | 6.90 GB (56,709 ไฟล์) | 0.65 GB (44,794 ไฟล์) | −6.25 GB |

### ยืนยันว่าไม่ได้แตะสิ่งที่ห้าม

| ห้ามลบ | สถานะ |
|---|---|
| Source code | ครบ — `webapi/api/` ยัง 10 ไฟล์ hash เดิม |
| `node_modules` | ยังอยู่ |
| Docker images / containers / volumes | ไม่แตะ — `docker_data.vhdx` ยัง 21.86 GB |
| ไฟล์ส่วนตัว | ไม่แตะ |

### ต้อง restart Docker Desktop อีกชั้น

ล้าง cache แล้ว engine ยังตอบ `Docker Desktop is unable to start` — log ชี้ว่า VM ไม่ตอบ `_ping` มา **34 นาที** คือค้างตั้งแต่ตอนดิสก์เต็มและไม่ฟื้นเอง

แก้ด้วยการปิดโปรเสส Docker Desktop ทั้ง 13 ตัว → `wsl --shutdown` → เปิดใหม่ จากนั้น engine ขึ้นปกติ (`Server 29.0.1 · linux/amd64`) ตอนนั้นไม่มี container หรือ image ใดทำงานในเครื่อง local การปิดจึงไม่ทำให้เสียอะไร

---

## ผลการตรวจ build โดยย่อ

| การตรวจ | ผล |
|---|---|
| `docker build -t webapi-m3-localtest:dba865b` | ผ่าน รวมขั้น `COPY api ./api` |
| ชนชื่อ production ไหม | ไม่ — เครื่อง local ไม่มี image ชื่อ `course-advisor-system-*` เลย |
| ไฟล์ใน `/app` | `server.mjs` · `auth.mjs` · `db.mjs` · `api/` · `node_modules` ครบ |
| `api/` ใน image | 10 ไฟล์ · hash `2b67e0f4…fa8fcd` **ตรงกับ production ทุกไบต์** |
| `*.test.mjs` ใน image | ไม่มี (ตามเจตนา) |
| `pg` ใน image | 8.23.1 ตรงกับ lock file |
| import ใน image | 7/7 |
| รัน container | `/healthz` ตอบ `status: ok` · `authConfigured: true` · ระดับสิทธิ์ครบ · ไม่ล้มเมื่อไม่มีฐานข้อมูล |
| log ตอนบูต | ไม่มีรหัสผ่านหรือคีย์ |
| regression | 82/82 |

รายละเอียดเต็มอยู่ใน `M3_BUILD_VERIFICATION_RESULT.md`

---

## Secret scan ก่อน commit

| สิ่งที่สแกน | ผล |
|---|---|
| JWT (`eyJ…`) / `sk-` / `AIza` / private key | ไม่พบ |
| connection string ที่มีรหัสผ่าน | ไม่พบ |
| `password=` ที่เป็นค่าจริง | ไม่พบ |
| UUID เต็ม | ไม่พบ |
| อีเมล | ไม่พบ |
| `webapi/api/` ใน staged | **ไม่มี** |

`git add` ระบุชื่อไฟล์ทั้ง 4 ตัว ไม่ใช้ `git add .`

---

## สิ่งที่ยังค้าง

### ต้องทำก่อนกด deploy — ต้องให้เจ้าของสั่ง

| # | งาน | ทำไมสำคัญ |
|---|---|---|
| **1** | `docker tag course-advisor-system-webapi:latest course-advisor-system-webapi:rollback-pre-m3` **บน production** แล้วยืนยันด้วย `docker images \| grep webapi` | webapi มี tag `latest` ตัวเดียว ต่างจาก backend/frontend ที่มี rollback tag หลายตัว · ถ้า build ทับโดยไม่ติด tag ก่อน **จะไม่เหลืออะไรให้ย้อนกลับ** |
| **2** | เตรียมบัญชี admin สถานะ `approved` ไว้ทดสอบ smoke test ข้อ 6 | ข้อเดียวที่พิสูจน์ว่า authorization foundation ที่จะขึ้น production ครั้งแรกไม่ล็อกผู้ดูแลออก |

ทั้งสองข้อเป็นการกระทำบน production จึงไม่ได้ทำในรอบนี้

### ขั้น deploy

| # | งาน | หมายเหตุ |
|---|---|---|
| 3 | สร้าง `ADVISOR_WEB_PASSWORD` ใส่ production `.env` | ยังไม่มีคีย์นี้ใน `.env` |
| 4 | คัดลอก `package-lock.json` ขึ้นเซิร์ฟเวอร์ | เซิร์ฟเวอร์ยังไม่มี และ Dockerfile ใหม่ใช้ `npm ci` ซึ่งบังคับต้องมี **ถ้าลืม build จะล้ม** |
| 5 | ยืนยันว่าสคริปต์ deploy จริงไม่ลบ `webapi/api/` ทิ้ง | README มีขั้นตอนแล้ว เหลือตรวจตัวสคริปต์ |
| 6 | สำรองฐานข้อมูลก่อน deploy | แนะนำ (M3 ไม่แตะข้อมูล) |

### ระยะยาว

- เปลี่ยน UUID ใน `webapi/auth.test.mjs:480` เป็นค่าสังเคราะห์ (แก้ไฟล์ไม่ลบค่าออกจากประวัติ git)
- เขียน `docs/DEPLOY_WEB.md` หรือลบการอ้างอิงใน `docker-compose.prod.yml:169`
- เพิ่ม `.dockerignore` — `node_modules/` ถูกส่งเข้า build context ทั้งก้อน
- ถอด `requireAdminUser` ออกจาก handler เมื่อมั่นใจด่านกลาง (ตอนนี้ `/api/admin/*` เรียก Supabase สองรอบต่อคำขอ)
- พิจารณาย้าย Docker disk image ไป D: — C: เหลือ 6.33 GB และ `docker_data.vhdx` กิน 21.86 GB

---

## ยืนยันขอบเขต

| ข้อห้าม | สถานะ |
|---|---|
| แตะ production | **ไม่มี** — ssh เข้าครั้งเดียวตอนท้ายเพื่ออ่านสถานะยืนยัน ไม่ได้เขียนอะไร |
| Deploy / Restart production | **ไม่มี** |
| แก้ production `.env` | **ไม่มี** |
| เขียน production database / Supabase | **ไม่มี** |
| Push / Merge | **ไม่มี** |
| Build ทับ production image | **ไม่มี** |
| ลบ source / node_modules / images / containers / volumes / ไฟล์ส่วนตัว | **ไม่มี** — ลบเฉพาะ npm cache ตามที่อนุมัติ |
| นำ `webapi/api/` เข้า git | **ไม่** |

### สถานะ production ตอนปิดงาน

```
ไฟล์ใน webapi/api/ : 10
คอนเทนเนอร์        : course-advisor-system-webapi-1  Up 2 weeks (healthy)
image              : course-advisor-system-webapi:latest
```

เหมือนเดิมทุกอย่าง
