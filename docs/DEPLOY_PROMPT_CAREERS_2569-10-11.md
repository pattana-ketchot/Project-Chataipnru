# Prompt สำหรับส่งให้ผู้ช่วยที่ดูแลเซิร์ฟเวอร์

> คัดลอกทุกอย่างตั้งแต่เส้นคั่นด้านล่างลงไป · ไฟล์อ้างอิงฉบับเต็มคือ `docs/CAREERS_DEPLOY_2569-10-11.md`

---

## งาน

Deploy สองอย่างขึ้น production ของระบบแนะแนวหลักสูตร คณะวิทยาศาสตร์และเทคโนโลยี ม.ราชภัฏพระนคร (`stpnru-advisor.duckdns.org`)

| ส่วน | อะไร |
|---|---|
| **A** backend FastAPI | เพิ่มเส้นทางใหม่ `GET /career-lists` — **เพิ่มล้วน 65 บรรทัดในไฟล์เดียว ไม่ลบบรรทัดใด ไม่แก้เส้นทางเดิม** |
| **B** หน้าเว็บ (ไฟล์ static ที่ Caddy เสิร์ฟ) | หน้า "อาชีพหลังจบ" ใช้งานได้ · แท็บข่าวสารของผู้ดูแลใช้งานได้ · แก้ชื่อแท็บเบราว์เซอร์ |

สองส่วนนี้ไม่ขึ้นแก่กัน ย้อนแยกกันได้ · ถ้า deploy แค่ A หน้าเว็บไม่กระทบ · ถ้า deploy แค่ B หน้า "อาชีพหลังจบ" จะแสดงหลักสูตรครบแต่ยังไม่มีรายการอาชีพ (ไม่ล้ม)

## ข้อห้ามเด็ดขาด

| ห้าม | เหตุผล |
|---|---|
| แตะ Supabase — policy ของ `user_profiles`, Auth, RLS | งาน C1 ที่ผ่านการตรวจแล้ว |
| แตะ Edge Function `sync-sci-news`, cron job, Vault secret, `SYNC_CRON_SECRET` | งาน C2 ที่ผ่านการตรวจแล้ว |
| แตะไฟล์ใน `webapi/` หรือ build webapi ใหม่ | ไม่เกี่ยวกับงานรอบนี้ |
| restart postgres, ollama, frontend, webapi, caddy | ใช้ `--no-deps` ทุกคำสั่ง `up` |
| รัน SQL ที่เขียนข้อมูล | ทุกคำสั่ง SQL ในงานนี้เป็น `select` เท่านั้น |
| เปลี่ยนค่าใน `.env` | ไม่จำเป็นสำหรับงานนี้ |
| เดาตำแหน่งโฟลเดอร์หรือชื่อ image | ให้ `docker compose config` บอกค่าจริง — ขั้น P1 |

## ขั้นที่ 1 — ให้ compose บอกค่าจริงก่อน (อ่านอย่างเดียว ห้ามข้าม)

ต้องใช้ `-p course-advisor-system` และ `-f` ครบสี่ไฟล์ในทุกคำสั่ง compose · **คำสั่งละหนึ่งบรรทัด** เพราะคำสั่งหลายบรรทัดผ่าน ssh เคยถูกตัดกลางคัน

```bash
docker compose -p course-advisor-system -f /home/ubuntu/course-advisor-system/docker-compose.prod.yml -f /home/ubuntu/course-advisor-system/docker-compose.staging.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-backend-2fdc6f2.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-frontend-2fdc6f2.yml config --format json > /tmp/effective.json
```

```bash
python3 -c "import json;d=json.load(open('/tmp/effective.json'));print('name:',d.get('name'));b=d['services']['backend'];print('backend.image:',b.get('image'));print('backend.build:',(b.get('build') or {}).get('context'));[print('caddy volume:',v.get('source'),'->',v.get('target'),'ro' if v.get('read_only') else 'rw') for v in d['services']['caddy'].get('volumes',[])]"
```

**รายงานค่าทั้งสี่กลับมาก่อนทำขั้นต่อไป**

1. `name` — ต้องเป็น `course-advisor-system`
2. `backend.image` — tag ที่การ build จะเขียนทับ
3. `backend.build` context — ที่ตั้งรีโปบนเซิร์ฟเวอร์ (คาดว่า `/home/ubuntu/course-advisor-system`)
4. `source` ของ volume ที่ target เป็น `/srv/web` — โฟลเดอร์จริงบน host (คาดว่า `/home/ubuntu/course-advisor-system/web`) และต้องเป็น `ro`

**ถ้า `backend.build` ว่าง → หยุดทันทีแล้วรายงาน** เพราะแปลว่าไฟล์ pin เอา build ออกและใช้ image สำเร็จ วิธี deploy จะต่างไปทั้งหมด

**ถ้า volume ของ `/srv/web` ไม่ใช่ `ro` หรือไม่มี → หยุดแล้วรายงาน** เพราะต่างจากที่ไฟล์ compose ในรีโประบุ

## ขั้นที่ 2 — สำรองก่อนแก้อะไรทั้งสิ้น

**2.1 สำรองหน้าเว็บ** (แทน `<WEB>` ด้วย source ที่ได้จากขั้น 1 ข้อ 4)

```bash
sudo cp -a <WEB> /home/ubuntu/web-backup-2569-10-11 && ls -1 /home/ubuntu/web-backup-2569-10-11 | head && du -sh /home/ubuntu/web-backup-2569-10-11
```

ต้องเห็น `index.html` และโฟลเดอร์ `assets`

**2.2 สำรอง image ของ backend จาก container ที่รันอยู่จริง** (ไม่ใช่จาก `docker images` เพราะ tag อาจชี้คนละ image กับที่รัน)

```bash
docker inspect --format '{{.Image}}' $(docker compose -p course-advisor-system -f /home/ubuntu/course-advisor-system/docker-compose.prod.yml -f /home/ubuntu/course-advisor-system/docker-compose.staging.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-backend-2fdc6f2.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-frontend-2fdc6f2.yml ps -q backend)
```

**จด image ID นี้ไว้** แล้วติด tag สำรอง (แทน `<OLD_ID>`)

```bash
docker tag <OLD_ID> course-advisor-backend:pre-careers-2569-10-11 && docker image inspect --format '{{.Id}}' course-advisor-backend:pre-careers-2569-10-11
```

ID ที่ได้ต้องตรงกับ `<OLD_ID>` — ไม่ตรงให้หยุด

## ขั้นที่ 3 — ส่วน A: backend

เจ้าของจะส่งไฟล์ `web_compat.py` มาให้ หนึ่งไฟล์ · วางที่ `<CTX>/backend/app/api/routes/web_compat.py` โดย `<CTX>` คือ build context จากขั้น 1 ข้อ 3

```bash
sudo cp /tmp/web_compat.py <CTX>/backend/app/api/routes/web_compat.py && grep -c "career-lists" <CTX>/backend/app/api/routes/web_compat.py
```

ต้องได้ **`2`**

```bash
docker compose -p course-advisor-system -f /home/ubuntu/course-advisor-system/docker-compose.prod.yml -f /home/ubuntu/course-advisor-system/docker-compose.staging.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-backend-2fdc6f2.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-frontend-2fdc6f2.yml build backend
```

**ตรวจไฟล์ในคอนเทนเนอร์ก่อน up** — scp แล้ว build แล้วไม่พอ ต้องเห็นว่าไฟล์ใหม่อยู่ใน image จริง

```bash
docker compose -p course-advisor-system -f /home/ubuntu/course-advisor-system/docker-compose.prod.yml -f /home/ubuntu/course-advisor-system/docker-compose.staging.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-backend-2fdc6f2.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-frontend-2fdc6f2.yml run --rm --no-deps --entrypoint sh backend -c "grep -c career-lists /app/app/api/routes/web_compat.py"
```

ต้องได้ **`2`** · ได้ `0` ให้หยุด · ถ้าพาธ `/app` ไม่ถูกให้หาด้วย `--entrypoint sh backend -c "find / -name web_compat.py -not -path '*/node_modules/*' 2>/dev/null"`

```bash
docker compose -p course-advisor-system -f /home/ubuntu/course-advisor-system/docker-compose.prod.yml -f /home/ubuntu/course-advisor-system/docker-compose.staging.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-backend-2fdc6f2.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-frontend-2fdc6f2.yml up -d --no-deps --no-build --force-recreate backend
```

```bash
docker inspect --format '{{.Image}}' $(docker compose -p course-advisor-system -f /home/ubuntu/course-advisor-system/docker-compose.prod.yml -f /home/ubuntu/course-advisor-system/docker-compose.staging.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-backend-2fdc6f2.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-frontend-2fdc6f2.yml ps -q backend)
```

**ID ต้องต่างจาก `<OLD_ID>`** — เหมือนเดิมแปลว่ายังรันโค้ดเก่า

## ขั้นที่ 4 — ส่วน B: หน้าเว็บ

เจ้าของจะส่ง `dist.tgz` มาให้ · **ต้องวางบน host ไม่ใช่ใน container** เพราะ `/srv/web` mount เป็น `:ro`

```bash
sudo rm -rf /tmp/web-new && mkdir -p /tmp/web-new && tar -xzf /tmp/dist.tgz -C /tmp/web-new && ls -1 /tmp/web-new
```

ต้องเห็น `index.html` และ `assets`

```bash
sudo rsync -a --delete /tmp/web-new/ <WEB>/ && rm -rf /tmp/web-new /tmp/dist.tgz
```

```bash
grep -o "<title>[^<]*</title>" <WEB>/index.html
```

ต้องได้ `ระบบแนะแนวหลักสูตร คณะวิทยาศาสตร์และเทคโนโลยี มหาวิทยาลัยราชภัฏพระนคร`

**ไม่ต้อง restart caddy** — เป็น bind mount อ่านไฟล์ตรงๆ

## ขั้นที่ 5 — ตรวจหลัง deploy แล้วรายงานผลทุกข้อ

```bash
curl -s https://stpnru-advisor.duckdns.org/api/openapi.json | grep -c career-lists
```
→ ต้อง ≥ `1`

```bash
curl -s -w '\nHTTP %{http_code}\n' https://stpnru-advisor.duckdns.org/api/career-lists | head -c 600
```
→ `200` · มี `programmes` · **ทุกรายการมี `source.file`** · **รายงานจำนวนหลักสูตรที่ได้** (คาด 2)

```bash
printf '{"messages":[{"role":"user","content":"สาขาวิทยาการคอมพิวเตอร์ จบแล้วทำงานอะไรได้บ้าง"}]}' > /tmp/v6.json && curl -s -D - -X POST -H 'Content-Type: application/json' --data-binary @/tmp/v6.json https://stpnru-advisor.duckdns.org/api/chat -o /tmp/v6.txt | grep -iE '^HTTP|^x-source' && head -c 300 /tmp/v6.txt
```
→ `200` · มี `X-Source-Document`, `X-Source-Page: 3`, `X-Source-Title` · คำตอบเป็นรายการอาชีพ
**เส้นทางนี้เป็น `POST` เท่านั้น — `GET` ไม่ใช่การทดสอบที่ถูก**

```bash
printf '{"messages":[{"role":"user","content":"ค่าเทอมสาขาวิทยาการคอมพิวเตอร์เท่าไร"}]}' > /tmp/v7.json && curl -s -w '\nHTTP %{http_code}\n' -X POST -H 'Content-Type: application/json' --data-binary @/tmp/v7.json https://stpnru-advisor.duckdns.org/api/chat
```
→ `200` · ต้องเป็นคำตอบเรื่องค่าเทอมจริง **ไม่ใช่** "ขออภัยครับ ระบบตอบไม่ได้ในขณะนี้"

```bash
printf '{"answers":{"interests":["คอมพิวเตอร์"],"skills":["การเขียนโปรแกรม"],"goal":"เป็นนักพัฒนาซอฟต์แวร์"},"courses":[{"id":"demo-1","title":"วิทยาการคอมพิวเตอร์"},{"id":"demo-2","title":"เทคโนโลยีสารสนเทศ"}]}' > /tmp/v8.json && curl -s -w '\nHTTP %{http_code}\n' -X POST -H 'Content-Type: application/json' --data-binary @/tmp/v8.json https://stpnru-advisor.duckdns.org/api/recommend-major | head -c 400
```
→ `200` · มี `primary.courseId` และ `primary.reason` (ใช้เวลาหลายสิบวินาที)

```bash
printf '{"courses":[{"id":"demo-1","title":"วิทยาการคอมพิวเตอร์"},{"id":"demo-2","title":"เทคโนโลยีสารสนเทศ"}]}' > /tmp/v9.json && curl -s -w '\nHTTP %{http_code}\n' -X POST -H 'Content-Type: application/json' --data-binary @/tmp/v9.json https://stpnru-advisor.duckdns.org/api/compare-courses | head -c 400
```
→ `200` · มี `summary` และ `courses` 2 รายการ

```bash
curl -s -o /dev/null -w 'sci-connect %{http_code}\n' https://stpnru-advisor.duckdns.org/api/sci-connect-news && curl -s -o /dev/null -w 'admin sync ไม่มี token %{http_code}\n' -X POST https://stpnru-advisor.duckdns.org/api/admin/sync-sci-news
```
→ `200` และ `401` ตามลำดับ · **`401` คือข้อยืนยันว่า C2 ยังทำงาน**

```bash
rm -f /tmp/v6.json /tmp/v6.txt /tmp/v7.json /tmp/v8.json /tmp/v9.json /tmp/effective.json
```

## ขั้นที่ 6 — ถ้า `/api/career-lists` คืน `programmes` ว่าง

เรื่องข้อมูล ไม่ใช่โค้ด · ตรวจด้วย SQL อ่านอย่างเดียว

```sql
select count(*) as items, count(distinct course_id) as programmes
from mko.v_live_list_items where item_type = 'career';
```

- `programmes` = 0 → ยังไม่มีการเผยแพร่รายการอาชีพ **ไม่ต้องแก้อะไรบนเซิร์ฟเวอร์** รายงานกลับให้เจ้าของ
- `programmes` ≥ 1 แต่ API ว่าง → ดู log ของ backend แล้วรายงาน

## Rollback

ย้อนส่วนใดก่อนก็ได้เพราะไม่ขึ้นแก่กัน · ถ้าย้อนทั้งคู่ ให้ย้อน **B แล้ว A**

**ย้อน B** — หน้าเว็บ

```bash
sudo rsync -a --delete /home/ubuntu/web-backup-2569-10-11/ <WEB>/ && grep -o "<title>[^<]*</title>" <WEB>/index.html
```
ต้องกลับเป็น `มหาวิทยาลัย - หน้าแรก`

**ย้อน A** — backend · ต้นทางคือ tag สำรอง `course-advisor-backend:pre-careers-2569-10-11` **ห้ามใช้ชื่อ image โดยไม่ระบุ tag** เพราะชื่อนั้นชี้ไป image ใหม่แล้ว (แทน `<BACKEND_IMAGE>` ด้วยค่าจากขั้น 1 ข้อ 2)

```bash
docker tag course-advisor-backend:pre-careers-2569-10-11 <BACKEND_IMAGE>
```

```bash
docker compose -p course-advisor-system -f /home/ubuntu/course-advisor-system/docker-compose.prod.yml -f /home/ubuntu/course-advisor-system/docker-compose.staging.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-backend-2fdc6f2.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-frontend-2fdc6f2.yml up -d --no-deps --no-build --force-recreate backend
```

```bash
docker inspect --format '{{.Image}}' $(docker compose -p course-advisor-system -f /home/ubuntu/course-advisor-system/docker-compose.prod.yml -f /home/ubuntu/course-advisor-system/docker-compose.staging.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-backend-2fdc6f2.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-frontend-2fdc6f2.yml ps -q backend) && curl -s https://stpnru-advisor.duckdns.org/api/openapi.json | grep -c career-lists
```

ID ต้องเท่ากับ `<OLD_ID>` และ `grep -c` ต้องได้ `0` = ย้อนสำเร็จ · ถ้า ID ไม่เท่า **ยังไม่ได้ย้อน** อย่าสรุปจากข้อความว่าคำสั่งสำเร็จ

## สิ่งที่ผ่านการทดสอบแล้ว และสิ่งที่ยังไม่ได้ทดสอบ

**ผ่านแล้วบนเครื่องพัฒนา** — ชุดทดสอบของเส้นทางใหม่ 17 ข้อ · ตรรกะหน้าเว็บ 23 ข้อ · ชุดเดิมของ backend 44 ข้อ · ชุดเดิมของ webapi 82 ข้อ · ชุดเดิมของ frontend 33 ข้อ · build ของหน้าเว็บผ่าน

**ยังไม่ได้ทดสอบเลย — ต้องกดด้วยมือหลัง deploy**

| # | รายการ |
|---|---|
| 1 | เรียก `/career-lists` กับฐานข้อมูลจริง (ชุดทดสอบใช้ฐานข้อมูลปลอม) |
| 2 | เห็นหน้า `/careers` ด้วยตา และกดลิงก์เอกสารในนั้น |
| 3 | **แท็บข่าวสารของผู้ดูแล — ยังไม่เคยกดปุ่มใดเลย** ต้องล็อกอินแล้วทดสอบ เพิ่มข่าว / แก้ไข / ลบ / กล่องยืนยันการลบ / ช่องค้นหา ทีละปุ่ม |
| 4 | จำนวนหลักสูตรที่จะขึ้นจริงใน `/careers` |

**การที่หน้าเปิดได้ไม่ได้แปลว่าทดสอบทุกปุ่มครบแล้ว** — ข้อ 3 ต้องกดจริงทุกปุ่ม ถ้าปุ่มใดใช้ไม่ได้ให้รายงานพร้อมข้อความ error จาก console ของเบราว์เซอร์

## สิ่งที่ต้องรายงานกลับ

1. ค่าสี่ค่าจากขั้นที่ 1
2. `<OLD_ID>` และ image ID ใหม่หลัง deploy
3. ผลทุกข้อของขั้นที่ 5 พร้อม HTTP code จริง
4. จำนวนหลักสูตรที่ `/api/career-lists` คืนมา
5. ผลการกดปุ่มในแท็บข่าวสาร ทีละปุ่ม
6. ถ้าหยุดกลางทาง — หยุดที่ขั้นไหนและเพราะอะไร
