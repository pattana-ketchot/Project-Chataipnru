# ชุด deploy — หน้า "อาชีพหลังจบ" + แท็บข่าวสารของผู้ดูแล

| รายการ | ค่า |
|---|---|
| วันที่ | 11 ตุลาคม 2569 |
| สถานะ | **ยังไม่ลงมือ** — เอกสารนี้ไว้ตรวจทานและคัดลอกไปใช้ |
| ต่อจาก | `docs/PRE_DEMO_READINESS_2569-10-11.md` |
| คงไว้ | C1 และ C2 ที่ผ่านแล้ว · **C3 พักไว้ ไม่รวมในรอบนี้** |

> รอบนี้ **ไม่ deploy เอง** · ไม่เปลี่ยน production · ไม่แตะ secret / cron / policy

---

## 1. สิ่งที่จะ deploy

| ส่วน | อะไร | ต้อง build ใหม่ไหม |
|---|---|---|
| **A** backend (FastAPI) | เพิ่ม `GET /career-lists` — **เพิ่มล้วน 65 บรรทัด ไม่ลบบรรทัดใด** | **ต้อง** — ซอร์สถูก build เข้า image ไม่มี bind mount ของโค้ด |
| **B** หน้าเว็บ (Vite → Caddy) | หน้า "อาชีพหลังจบ" · แท็บข่าวสารของผู้ดูแล · ชื่อแท็บเบราว์เซอร์ | **ไม่ต้อง** — Caddy อ่านไฟล์จาก bind mount ตรงๆ |

### 1.1 ทำไมบอกได้ว่า A ต้อง build และ B ไม่ต้อง

จาก `docker-compose.prod.yml` ในรีโป

```yaml
  backend:
    build:
      context: .
      dockerfile: backend/Dockerfile
    volumes:
      - ./documents:/srv/documents:ro      # มีแต่เอกสาร ไม่มีซอร์ส
  caddy:
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - ./web:/srv/web:ro                  # หน้าเว็บมาจาก host
```

| ข้อสรุป | หลักฐาน |
|---|---|
| โค้ด backend อยู่ใน image | `build.context: .` และไม่มี volume ของซอร์ส |
| **`/srv/web` ไม่ใช่โฟลเดอร์ใน container** | เป็น bind mount ของ `./web` บน host |
| **เขียนใน container ไม่ได้** | mount เป็น `:ro` |
| **ต้องวางไฟล์บน host** | ที่ `./web` ของ project directory |
| ไม่ต้อง restart caddy | `file_server` อ่านไฟล์ทุกคำขอ · `Caddyfile` ตั้ง `no-cache` ให้ HTML และ `immutable` ให้ `/assets/*` ซึ่งเปลี่ยนชื่อไฟล์ทุก build |

### 1.2 ⚠ project directory — ต้องตรวจก่อน ห้ามคาดเดา

Compose แปลงพาธแบบ `./web` เทียบกับ **project directory** ซึ่งเมื่อสั่งด้วยหลาย `-f` จะเป็นโฟลเดอร์ของไฟล์ `-f` **ตัวแรก** → คาดว่าเป็น `/home/ubuntu/course-advisor-system` → `./web` = `/home/ubuntu/course-advisor-system/web`

**แต่ไฟล์ pin อีกสองไฟล์อยู่ใน `/home/ubuntu/release-2fdc6f2/` และอาจ override volume หรือ image ได้** และผมอ่านไฟล์เหล่านั้นไม่ได้จากเครื่องพัฒนา

→ **ขั้น P1 ในข้อ 3 คือการให้ compose บอกค่าจริงออกมาเอง ห้ามข้าม**

---

## 2. ไฟล์ต้นทาง → ปลายทาง

### 2.1 ส่วน A — backend

| # | ต้นทาง (เครื่องพัฒนา) | ปลายทาง (เซิร์ฟเวอร์) |
|---|---|---|
| 1 | `backend/app/api/routes/web_compat.py` | `<repo บนเซิร์ฟเวอร์>/backend/app/api/routes/web_compat.py` |

**ไฟล์เดียว** · ไฟล์อื่นในรีโปไม่ถูกแก้

`<repo บนเซิร์ฟเวอร์>` คาดว่าเป็น `/home/ubuntu/course-advisor-system` — **ยืนยันจากขั้น P1**

### 2.2 ส่วน B — หน้าเว็บ

| # | ต้นทาง | ปลายทาง |
|---|---|---|
| 1 | `D:\workspace\LastProject\dist\` ทั้งโฟลเดอร์ (build แล้ว) | `<project dir>/web/` |

ไฟล์ที่เปลี่ยนในรีโป LastProject

| ไฟล์ | สถานะ |
|---|---|
| `index.html` | แก้ชื่อแท็บ + meta description |
| `src/pages/Careers.jsx` | ใช้ `/api/career-lists` · ไม่กลืน error · แสดงที่มาเอกสาร |
| `src/lib/careerMerge.js` | **ใหม่** |
| `src/pages/Admin/Dashboard.jsx` | แท็บข่าวสารใช้งานได้จริง |
| `src/lib/adminDeletable.js` | **ใหม่** |
| `test/careerMerge.test.mjs` · `test/adminDeletable.test.mjs` | **ใหม่** (ไม่ขึ้น production) |

> **ไม่แตะ `src/pages/ChatAdvisor.jsx`** ที่ยังมีการแก้ค้างอยู่ (C3) — ถ้า build จากรีโปตอนนี้ **ไฟล์นั้นจะติดไปด้วย** ดูข้อ 6.1

---

## 3. คำสั่ง — คัดลอกไปใช้ได้ทันที

> ทุกคำสั่ง compose ใช้ `-p course-advisor-system` และ `-f` ครบสี่ไฟล์ · **คำสั่งละหนึ่งบรรทัด** เพราะคำสั่งหลายบรรทัดผ่าน ssh เคยถูกตัดกลางคัน

### ขั้น P1 — ให้ compose บอกค่าจริง (อ่านอย่างเดียว ต้องทำก่อนทุกอย่าง)

```bash
docker compose -p course-advisor-system -f /home/ubuntu/course-advisor-system/docker-compose.prod.yml -f /home/ubuntu/course-advisor-system/docker-compose.staging.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-backend-2fdc6f2.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-frontend-2fdc6f2.yml config --format json > /tmp/effective.json
```

```bash
python3 -c "import json;d=json.load(open('/tmp/effective.json'));print('name:',d.get('name'));b=d['services']['backend'];print('backend.image:',b.get('image'));print('backend.build:',(b.get('build') or {}).get('context'));c=d['services']['caddy'];[print('caddy volume:',v.get('source'),'->',v.get('target'),'ro' if v.get('read_only') else 'rw') for v in c.get('volumes',[])]"
```

**ต้องจดสี่ค่านี้ก่อนไปต่อ**

| ค่า | ใช้ทำอะไร |
|---|---|
| `name` | ต้องเป็น `course-advisor-system` |
| `backend.image` | tag ที่ build จะเขียนทับ — **ต้องสำรองก่อน** |
| `backend.build` context | ที่ตั้งของรีโปบนเซิร์ฟเวอร์ = ที่วางไฟล์ของส่วน A |
| `caddy` volume ที่ target `/srv/web` | `source` คือโฟลเดอร์จริงบน host = ที่วางไฟล์ของส่วน B |

> **ถ้า `backend.build` ไม่มีค่า** แปลว่าไฟล์ pin เอา `build` ออกและใช้ image ที่ build ไว้ล่วงหน้า → **หยุด** แล้วรายงานกลับ วิธี deploy จะต่างไปโดยสิ้นเชิง

### ขั้น P2 — สิทธิ์และตำแหน่งของโฟลเดอร์หน้าเว็บ

```bash
ls -ld <source ของ /srv/web จากขั้น P1> && ls -l <source ของ /srv/web จากขั้น P1> | head -5 && df -h <source ของ /srv/web จากขั้น P1> | tail -1
```

```bash
docker compose -p course-advisor-system -f /home/ubuntu/course-advisor-system/docker-compose.prod.yml -f /home/ubuntu/course-advisor-system/docker-compose.staging.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-backend-2fdc6f2.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-frontend-2fdc6f2.yml exec caddy sh -c "touch /srv/web/.writetest 2>&1 || echo 'read-only ตามคาด'"
```

| ผล | แปลว่า |
|---|---|
| `read-only ตามคาด` | ถูกต้อง — ต้องวางไฟล์บน host |
| สร้างไฟล์ได้ | mount ไม่ได้เป็น `:ro` → **หยุด** แล้วรายงาน เพราะต่างจากที่รีโประบุ |

> ถ้าสร้างไฟล์ได้จริง ให้ลบทิ้งด้วย `exec caddy rm -f /srv/web/.writetest`

### ขั้น B0 — สำรองหน้าเว็บ **ก่อนแก้อะไร**

```bash
sudo cp -a <source ของ /srv/web จากขั้น P1> /home/ubuntu/web-backup-2569-10-11
```

```bash
ls -1 /home/ubuntu/web-backup-2569-10-11 | head && du -sh /home/ubuntu/web-backup-2569-10-11
```

ต้องเห็น `index.html` และโฟลเดอร์ `assets`

### ขั้น A0 — สำรอง image **จาก container ที่รันจริง**

```bash
docker inspect --format '{{.Image}}' $(docker compose -p course-advisor-system -f /home/ubuntu/course-advisor-system/docker-compose.prod.yml -f /home/ubuntu/course-advisor-system/docker-compose.staging.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-backend-2fdc6f2.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-frontend-2fdc6f2.yml ps -q backend)
```

```bash
docker tag <image ID ที่ได้จากคำสั่งบน> course-advisor-backend:pre-careers-2569-10-11
```

```bash
docker image inspect --format '{{.Id}}' course-advisor-backend:pre-careers-2569-10-11
```

**ID ที่ได้ต้องตรงกับ ID จากคำสั่งแรก** — ถ้าไม่ตรง หยุด

> ใช้ `docker inspect` ของ **container** ไม่ใช่ `docker images` เพราะ tag อาจชี้ไปคนละ image กับที่กำลังรันอยู่

### ขั้น A1 — วางไฟล์ backend

```bash
scp D:/workspace/course-advisor-system-mko2/backend/app/api/routes/web_compat.py ubuntu@<host>:/tmp/web_compat.py
```

```bash
sudo cp /tmp/web_compat.py <backend.build context จากขั้น P1>/backend/app/api/routes/web_compat.py && rm -f /tmp/web_compat.py
```

```bash
grep -c "career-lists" <backend.build context จากขั้น P1>/backend/app/api/routes/web_compat.py
```

ต้องได้ **`2`** (เส้นทางหนึ่งครั้ง + ตัวชี้ในคอมเมนต์หนึ่งครั้ง)

### ขั้น A2 — build

```bash
docker compose -p course-advisor-system -f /home/ubuntu/course-advisor-system/docker-compose.prod.yml -f /home/ubuntu/course-advisor-system/docker-compose.staging.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-backend-2fdc6f2.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-frontend-2fdc6f2.yml build backend
```

### ขั้น A3 — ตรวจไฟล์ **ในคอนเทนเนอร์** ก่อน up

```bash
docker compose -p course-advisor-system -f /home/ubuntu/course-advisor-system/docker-compose.prod.yml -f /home/ubuntu/course-advisor-system/docker-compose.staging.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-backend-2fdc6f2.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-frontend-2fdc6f2.yml run --rm --no-deps --entrypoint sh backend -c "grep -c career-lists /app/app/api/routes/web_compat.py"
```

ต้องได้ **`2`** · ถ้าได้ `0` แปลว่า build ไม่ได้ใช้ไฟล์ใหม่ → **หยุด** (ถ้าพาธ `/app` ไม่ถูก ให้หาด้วย `--entrypoint sh backend -c "find / -name web_compat.py -not -path '*/node_modules/*' 2>/dev/null"`)

### ขั้น A4 — เปลี่ยนเฉพาะ backend

```bash
docker compose -p course-advisor-system -f /home/ubuntu/course-advisor-system/docker-compose.prod.yml -f /home/ubuntu/course-advisor-system/docker-compose.staging.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-backend-2fdc6f2.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-frontend-2fdc6f2.yml up -d --no-deps --no-build --force-recreate backend
```

```bash
docker compose -p course-advisor-system -f /home/ubuntu/course-advisor-system/docker-compose.prod.yml -f /home/ubuntu/course-advisor-system/docker-compose.staging.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-backend-2fdc6f2.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-frontend-2fdc6f2.yml ps backend
```

| ธง | ทำอะไร |
|---|---|
| `--no-deps` | ไม่แตะ postgres · ollama · frontend · webapi · caddy |
| `--no-build` | ใช้ image ที่ build ในขั้น A2 ไม่ build ซ้ำ |
| `--force-recreate` | สร้างคอนเทนเนอร์ใหม่แม้ config ไม่เปลี่ยน |

```bash
docker inspect --format '{{.Image}}' $(docker compose -p course-advisor-system -f /home/ubuntu/course-advisor-system/docker-compose.prod.yml -f /home/ubuntu/course-advisor-system/docker-compose.staging.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-backend-2fdc6f2.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-frontend-2fdc6f2.yml ps -q backend)
```

**ID ต้องต่างจากขั้น A0** — ถ้าเหมือนเดิมแปลว่ายังรันโค้ดเก่า

### ขั้น B1 — build หน้าเว็บ (ทำบนเครื่องพัฒนา)

```bash
cd D:/workspace/LastProject && npm run build
```

### ขั้น B2 — วางไฟล์หน้าเว็บ

```bash
cd D:/workspace/LastProject && tar -czf dist.tgz -C dist . && scp dist.tgz ubuntu@<host>:/tmp/dist.tgz
```

```bash
sudo rm -rf /tmp/web-new && mkdir -p /tmp/web-new && tar -xzf /tmp/dist.tgz -C /tmp/web-new && ls -1 /tmp/web-new
```

ต้องเห็น `index.html` และ `assets`

```bash
sudo rsync -a --delete /tmp/web-new/ <source ของ /srv/web จากขั้น P1>/ && rm -rf /tmp/web-new /tmp/dist.tgz
```

> ใช้ `rsync --delete` เพื่อให้ไฟล์ asset ชื่อเก่าหายไป · ของสำรองอยู่ที่ `/home/ubuntu/web-backup-2569-10-11` แล้วจากขั้น B0

```bash
grep -o "<title>[^<]*</title>" <source ของ /srv/web จากขั้น P1>/index.html
```

ต้องได้ `ระบบแนะแนวหลักสูตร คณะวิทยาศาสตร์และเทคโนโลยี มหาวิทยาลัยราชภัฏพระนคร`

---

## 4. ตรวจหลัง deploy

> **ทุกข้อที่ยิง `/api/chat` ต้องเป็น `POST` พร้อม body จริง** — `GET` ไปที่เส้นทางนี้ไม่ใช่การทดสอบที่ถูก (รายงานรอบก่อนเขียน `GET` ไว้ผิด แก้แล้วในข้อนี้)

| # | ทดสอบ | คำสั่ง / วิธี | ต้องได้ |
|---|---|---|---|
| **V1** | เส้นทางใหม่มีจริง | `curl -s https://stpnru-advisor.duckdns.org/api/openapi.json \| grep -c career-lists` | ≥ `1` |
| **V2** | เส้นทางใหม่ตอบ | `curl -s https://stpnru-advisor.duckdns.org/api/career-lists` | `200` · มี `programmes` · **ทุกรายการมี `source.file`** |
| **V3** | จำนวนหลักสูตรที่ได้ | นับ `programmes` จาก V2 | **คาด 2** (วิทยาการคอมพิวเตอร์ 2566 · เทคโนโลยีสารสนเทศ 2566) — ได้ `0` ให้ดูข้อ 4.2 |
| **V4** | หน้า `/careers` | เปิดด้วยเบราว์เซอร์ | หลักสูตรที่มีรายการขึ้นก่อน · ที่ยังไม่มีขึ้นข้อความบอกตรงๆ · บรรทัด "N จาก M หลักสูตร" ตรงกับ V3 |
| **V5** | ลิงก์เอกสารในหน้านั้น | กดลิงก์ "ที่มา: cs66.pdf หน้า 3" | เปิด PDF ได้ **ไม่ใช่ 404** |
| **V6** | แชทพร้อมแหล่งอ้างอิง | ดูคำสั่งข้อ 4.1 | `200` · มี `X-Source-Document` `X-Source-Page: 3` `X-Source-Title` · คำตอบเป็นรายการอาชีพ |
| **V7** | แชทคำถามทั่วไป | ดูคำสั่งข้อ 4.1 | `200` · คำตอบจริงเรื่องค่าเทอม ไม่ใช่ข้อความ fallback |
| **V8** | แนะนำสาขา | ดูคำสั่งข้อ 4.1 | `200` · มี `primary.courseId` และ `primary.reason` |
| **V9** | เปรียบเทียบสาขา | ดูคำสั่งข้อ 4.1 | `200` · มี `summary` และ `courses` 2 รายการ |
| **V10** | SCI Connect | `curl -s -o /dev/null -w '%{http_code}' https://stpnru-advisor.duckdns.org/api/sci-connect-news` | `200` |
| **V11** | ด่านของผู้ดูแลยังทำงาน | `curl -s -o /dev/null -w '%{http_code}' -X POST https://stpnru-advisor.duckdns.org/api/admin/sync-sci-news` | `401` |
| **V12** | แท็บข่าวสารของผู้ดูแล | ล็อกอินเป็น admin → `/admin/dashboard?tab=news` | เห็นรายการข่าว (หรือ "ยังไม่มีข่าว") **ไม่ใช่หน้า "กำลังพัฒนา"** |

### 4.1 คำสั่งของ V6–V9

```bash
printf '{"messages":[{"role":"user","content":"สาขาวิทยาการคอมพิวเตอร์ จบแล้วทำงานอะไรได้บ้าง"}]}' > /tmp/v6.json && curl -s -D - -X POST -H 'Content-Type: application/json' --data-binary @/tmp/v6.json https://stpnru-advisor.duckdns.org/api/chat -o /tmp/v6.txt | grep -iE '^HTTP|^x-source' && head -c 300 /tmp/v6.txt
```

```bash
printf '{"messages":[{"role":"user","content":"ค่าเทอมสาขาวิทยาการคอมพิวเตอร์เท่าไร"}]}' > /tmp/v7.json && curl -s -w '\nHTTP %{http_code}\n' -X POST -H 'Content-Type: application/json' --data-binary @/tmp/v7.json https://stpnru-advisor.duckdns.org/api/chat
```

```bash
printf '{"answers":{"interests":["คอมพิวเตอร์"],"skills":["การเขียนโปรแกรม"],"goal":"เป็นนักพัฒนาซอฟต์แวร์"},"courses":[{"id":"demo-1","title":"วิทยาการคอมพิวเตอร์"},{"id":"demo-2","title":"เทคโนโลยีสารสนเทศ"}]}' > /tmp/v8.json && curl -s -w '\nHTTP %{http_code}\n' -X POST -H 'Content-Type: application/json' --data-binary @/tmp/v8.json https://stpnru-advisor.duckdns.org/api/recommend-major | head -c 400
```

```bash
printf '{"courses":[{"id":"demo-1","title":"วิทยาการคอมพิวเตอร์"},{"id":"demo-2","title":"เทคโนโลยีสารสนเทศ"}]}' > /tmp/v9.json && curl -s -w '\nHTTP %{http_code}\n' -X POST -H 'Content-Type: application/json' --data-binary @/tmp/v9.json https://stpnru-advisor.duckdns.org/api/compare-courses | head -c 400
```

```bash
rm -f /tmp/v6.json /tmp/v6.txt /tmp/v7.json /tmp/v8.json /tmp/v9.json
```

> `id` ของ V8/V9 เป็นค่าสมมุติได้ เพราะหลังบ้านจับคู่ด้วย **ชื่อ** ไม่ใช่รหัส · ทั้งสองเส้นทางนี้เรียกโมเดลภาษา ใช้เวลาหลายสิบวินาที

### 4.2 ถ้า V3 ได้ `0`

ตรวจว่ามีรายการอาชีพที่เผยแพร่แล้วจริงไหม (อ่านอย่างเดียว)

```sql
select count(*) as items, count(distinct course_id) as programmes
from mko.v_live_list_items where item_type = 'career';
```

| ผล | แปลว่า |
|---|---|
| `programmes` ≥ 1 แต่ V2 ว่าง | เส้นทางผิดพลาด — ดู log ของ backend |
| `programmes` = 0 | **ยังไม่มีการเผยแพร่รายการอาชีพ** — เรื่องข้อมูล ไม่ใช่โค้ด ดู `docs/CAREERS_REVIEW_WORKSHEET_2569-10-11.md` |

---

## 5. Rollback

### 5.1 ย้อนแค่ส่วนเดียวได้อะไร

| ย้อนแค่ | ผล |
|---|---|
| **A** backend | หน้าเว็บเรียก `/career-lists` ได้ `404` → `res.ok` เป็น false → **แสดงหลักสูตรครบโดยไม่มีรายการอาชีพ ไม่ล้ม** · แท็บข่าวสารไม่กระทบ (ใช้ Supabase ไม่ใช่ backend) |
| **B** หน้าเว็บ | กลับไปหน้าเดิมทุกอย่าง · เส้นทาง `/career-lists` ยังอยู่แต่ไม่มีใครเรียก **ไม่มีผลเสีย** |

**ย้อนส่วนใดก่อนก็ได้** เพราะสองส่วนไม่ขึ้นแก่กัน · ถ้าย้อนทั้งคู่ ให้ย้อน **B แล้ว A**

### 5.2 ย้อนส่วน B — หน้าเว็บ

```bash
sudo rsync -a --delete /home/ubuntu/web-backup-2569-10-11/ <source ของ /srv/web จากขั้น P1>/
```

```bash
grep -o "<title>[^<]*</title>" <source ของ /srv/web จากขั้น P1>/index.html
```

ต้องกลับไปเป็น `มหาวิทยาลัย - หน้าแรก` = ย้อนสำเร็จ

### 5.3 ย้อนส่วน A — backend

```bash
docker tag course-advisor-backend:pre-careers-2569-10-11 <backend.image จากขั้น P1>
```

```bash
docker compose -p course-advisor-system -f /home/ubuntu/course-advisor-system/docker-compose.prod.yml -f /home/ubuntu/course-advisor-system/docker-compose.staging.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-backend-2fdc6f2.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-frontend-2fdc6f2.yml up -d --no-deps --no-build --force-recreate backend
```

```bash
docker inspect --format '{{.Image}}' $(docker compose -p course-advisor-system -f /home/ubuntu/course-advisor-system/docker-compose.prod.yml -f /home/ubuntu/course-advisor-system/docker-compose.staging.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-backend-2fdc6f2.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-frontend-2fdc6f2.yml ps -q backend)
```

**ID ต้องเท่ากับ ID ที่จดไว้ในขั้น A0** · ถ้าไม่เท่า **ยังไม่ได้ย้อน** อย่าสรุปจากข้อความว่าคำสั่งสำเร็จ

```bash
curl -s https://stpnru-advisor.duckdns.org/api/openapi.json | grep -c career-lists
```

ต้องได้ `0` = ย้อนสำเร็จ

### 5.4 tag สำรองที่ใช้ในรอบนี้

| tag | คืออะไร |
|---|---|
| `course-advisor-backend:pre-careers-2569-10-11` | image ของ backend **ที่รันอยู่ก่อน deploy** จับจาก container จริงในขั้น A0 |
| `/home/ubuntu/web-backup-2569-10-11/` | สำเนาโฟลเดอร์หน้าเว็บก่อนเปลี่ยน |

> **ห้ามใช้ชื่อ image โดยไม่ระบุ tag เป็นต้นทาง** เพราะ `<backend.image>` จะชี้ไปที่ image ใหม่หลัง build แล้ว

---

## 6. ข้อควรระวัง

### 6.1 ⚠ C3 ติดไปกับ build ของหน้าเว็บ

`src/pages/ChatAdvisor.jsx` มีการแก้ค้างอยู่ในรีโป LastProject (ข้อความบอกสถานะระหว่างรอคำตอบ) **ซึ่งคือ C3 ที่สั่งให้พักไว้**

`npm run build` ใช้ไฟล์ในรีโปทั้งหมด → **ถ้า build ตอนนี้ C3 จะขึ้น production ไปด้วย**

| ทางเลือก | ทำอะไร | ข้อแลก |
|---|---|---|
| **ก** | คง C3 ไว้ใน build นี้ด้วย | ได้ของสามอย่างในรอบเดียว · แต่ขัดกับที่สั่งให้พัก C3 |
| **ข (แนะนำ)** | **commit งานรอบนี้ แล้ว build จาก working tree ที่เอา ChatAdvisor.jsx กลับเป็นฉบับเดิม** | ตรงตามที่สั่ง · ต้องจัดการ git หนึ่งขั้น |

คำสั่งของทาง ข — ทำบนเครื่องพัฒนา **หลังจาก commit หรือสำรองไฟล์ C3 ไว้แล้ว**

```bash
cd D:/workspace/LastProject && git diff src/pages/ChatAdvisor.jsx > /tmp/c3-chatadvisor.patch && git checkout -- src/pages/ChatAdvisor.jsx && npm run build
```

เอา C3 กลับมาภายหลังด้วย

```bash
cd D:/workspace/LastProject && git apply /tmp/c3-chatadvisor.patch
```

> **ต้องตัดสินใจข้อนี้ก่อนขั้น B1** · ถ้าเลือกทาง ก ให้บันทึกไว้ว่า C3 ขึ้น production แล้ว ไม่ใช่ยังพักอยู่

### 6.2 สิ่งที่ไม่ถูกแตะเลยในรอบนี้

| รายการ | ยืนยัน |
|---|---|
| C1 — policy ของ `user_profiles` | ไม่มีคำสั่ง SQL ที่เขียนข้อมูลในเอกสารนี้ |
| C2 — Edge Function · cron · secret | ไม่มีคำสั่งที่แตะ |
| `webapi/api/` | ไม่มีไฟล์ใดถูกแก้ |
| ฐานข้อมูล | คำสั่ง SQL ทุกข้อในเอกสารนี้เป็น `select` |
| postgres · ollama · frontend · webapi · caddy | `--no-deps` ทุกคำสั่ง `up` |

---

## 7. สิ่งที่ผ่านจริงแล้ว และสิ่งที่ยังไม่ทดสอบ

### 7.1 ผ่านจริง — บนเครื่องพัฒนา

| ชุด | ผล |
|---|---|
| `python -m eval.career_lists_check` | **17 ผ่าน** |
| `python -m eval.chat_source_header_check` | **28 ผ่าน** |
| `python -m eval.document_endpoint_check` | **16 ผ่าน** |
| `node --test` ของ webapi | **82 ผ่าน** |
| `npx vitest run` ของ frontend | **33 ผ่าน** |
| `node --test test/careerMerge.test.mjs test/adminDeletable.test.mjs` | **23 ผ่าน** |
| `npm run build` ของ LastProject | **ผ่าน** |

### 7.2 ยังไม่ทดสอบ

| # | ยังไม่ได้ทำ | เหตุ |
|---|---|---|
| 1 | เรียก `/career-lists` กับฐานข้อมูลจริง | Docker บนเครื่องพัฒนาปิดอยู่ · ชุดทดสอบใช้ db ปลอม |
| 2 | **เห็นหน้า `/careers` ที่แก้แล้วด้วยตา** | ต้องมี backend + ฐานข้อมูลจริง |
| 3 | **แท็บข่าวสารของผู้ดูแล — ยังไม่เคยกดปุ่มใดเลย** | ต้องล็อกอิน ไม่มีบัญชีสำหรับทดสอบ |
| 4 | ปุ่มแก้ไข / ลบข่าว และกล่องยืนยันการลบ | เหมือนข้อ 3 |
| 5 | จำนวนหลักสูตรที่จะขึ้นจริงใน `/careers` | คาด 2 ตามรายงานการเผยแพร่ ต้องยืนยันด้วย V3 |
| 6 | `python -m eval.curriculum_facts_check` | ชุดนี้ต่อ PostgreSQL จริงที่พอร์ต 55432 ซึ่งไม่ได้เปิด — **ไม่ใช่ผลล้ม แต่ยังไม่ได้ยืนยัน** |

> **"หน้าเปิดได้" ไม่ได้แปลว่าทดสอบทุกปุ่มครบแล้ว** — ข้อ 3 และ 4 คือส่วนที่ต้องกดด้วยมือจริงหลัง deploy (V12 เป็นแค่การเห็นรายการ ยังไม่ได้ทดสอบเพิ่ม/แก้/ลบ)
