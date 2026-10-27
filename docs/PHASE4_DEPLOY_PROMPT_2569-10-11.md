> # ⛔ ฉบับนี้เลิกใช้แล้ว
>
> ใช้ **[PHASE4_DEPLOY_PROMPT_2569-10-12.md](PHASE4_DEPLOY_PROMPT_2569-10-12.md)** แทน
>
> ฉบับ 12 ต.ค. เขียนขึ้นหลังอ่านเซิร์ฟเวอร์จริง (ดู [PHASE4_PREFLIGHT_RESULT_2569-10-12.md](PHASE4_PREFLIGHT_RESULT_2569-10-12.md))
> และแก้ข้อผิดของฉบับนี้ 6 จุด ที่สำคัญคือ
>
> | ข้อผิดในฉบับนี้ | ผลถ้ารันตามนี้ |
> |---|---|
> | ไม่มีขั้นส่งไฟล์ · เขียนแค่ "เจ้าของจะส่งมาให้" | ถ้าส่ง `main.py` ทั้งไฟล์ไป **backend ขึ้นไม่ได้เลย** เพราะ `import crawl_review` ซึ่งไม่มีบนเซิร์ฟเวอร์ |
> | `chown -R 1000:1000` | host uid 1000 คือ `opc` ไม่ใช่ `ubuntu` (1001) — ผู้ใช้ `ubuntu` จะเขียนโฟลเดอร์ไม่ได้ |
> | เลื่อนสิทธิ์ด้วย `lower('$E')` | ต่อสตริงเข้า SQL · และฉบับใหม่พบว่า `psql -v` **ไม่แทนค่าใน `-c`** ต้องอ่านจาก stdin |
> | บอกให้ "กดลืมรหัสผ่าน" ตอนไม่มี SMTP | ลิงก์ชี้ไปหน้า `/admin/reset-password` ที่ **ไม่มีอยู่** — token ไม่เคยถูกใช้ |
> | ตรวจ URL เฉพาะ `logo_url` | URL ที่ฝังใน `content` / `description` หลุดไป รูปในเนื้อหาจะหายตอนปิด Supabase |
> | อ้างว่า cron สองตัวกันซ้ำด้วย `detail_url` | **เหตุผลผิด** — เขียนคนละฐานข้อมูล และไม่ได้พิสูจน์ว่า cron เก่าเลิกใช้ |

# Prompt สำหรับผู้ช่วยที่ดูแลเซิร์ฟเวอร์ — Phase 4 (ฉบับแก้ไข)

> คัดลอกทุกอย่างตั้งแต่เส้นคั่นลงไป · รายละเอียดอยู่ใน `docs/PHASE4_BUILD_REPORT_2569-10-11.md`
>
> **ฉบับนี้แทนที่ฉบับก่อนทั้งหมด** — ฉบับก่อนมีข้อผิดสามจุด: ถอนกลับด้วย `TRUNCATE`
> (ลบข้อมูลที่เกิดหลัง deploy ทิ้ง) · ทดสอบการตัด Supabase ด้วย hosts entry ที่ครอบ
> subdomain ไม่ได้ · และอ้างว่า `is_admin` ไม่เคยถูกแตะ ซึ่งไม่จริง

---

## งาน

ย้ายระบบแนะแนวหลักสูตร (`stpnru-advisor.duckdns.org`) ให้ใช้ **PostgreSQL บนเซิร์ฟเวอร์เป็นฐานข้อมูลเดียว**

ลำดับ **ห้ามสลับ** — backend ก่อน → ข้อมูล/ไฟล์/บัญชีพร้อม → ตรวจ API → หน้าเว็บ

```
P1 ให้ compose บอกค่าจริง (อ่านอย่างเดียว)
P2 ตั้งตัวแปรจากค่าที่อ่านได้
P3 สำรองฐานข้อมูล · หน้าเว็บ · image
A  migration 007 (สิทธิ์ผู้ใช้)
B  deploy backend                 ← ก่อนข้อมูล เพราะ API ต้องพร้อมรับการตรวจ
C  นำข้อมูลเข้า + บัญชี + ไฟล์
D  ตรวจ API ให้ผ่านครบ            ← ด่านก่อนแตะหน้าเว็บ
E  deploy หน้าเว็บ
F  ตั้ง cron
V  ตรวจรับ
```

**E ต้องอยู่หลัง D เสมอ** — หน้าเว็บใหม่ไม่คุยกับ Supabase แล้ว ถ้า API ยังไม่พร้อม หน้าสาธารณะและหน้าผู้ดูแลจะว่างทั้งหมด

> **ทุกคำสั่งในเอกสารนี้รันบนเซิร์ฟเวอร์ (ssh เข้าไปแล้ว)** ไม่ใช่บนเครื่องของตัวเอง
> ชื่อคอนเทนเนอร์ชุดนี้ (`course-advisor-system-postgres-1` ฯลฯ) **ซ้ำกับชุดที่รันบนเครื่องพัฒนา**
> `docker exec` ที่เผลอรันบนเครื่องตัวเองจะไปโดนฐานข้อมูลของเครื่องนั้นเงียบ ๆ โดยไม่มีอะไรฟ้อง
>
> ยืนยันก่อนเริ่ม — ต้องได้ชื่อโฮสต์ของเซิร์ฟเวอร์ ไม่ใช่ชื่อเครื่องตัวเอง
>
> ```bash
> hostname && docker ps --format '{{.Names}}' | sort | head
> ```

## ข้อห้าม

| ห้าม | เหตุผล |
|---|---|
| **ลบหรือปิดโปรเจกต์ Supabase** | ต้องเก็บไว้จนตรวจรับครบ — เป็นทางถอยเดียวที่เหลือ |
| **`TRUNCATE` หรือ `DELETE` แบบเหมารวม** | ลบข้อมูลที่เกิดหลัง deploy ทิ้งด้วย — ใช้ backup/snapshot แทน |
| แตะ `public.courses` · `course_documents` · `course_chunks` · schema `mko` | ข้อมูลที่ AI ใช้ตอบ ไม่เกี่ยวกับงานนี้ |
| restart postgres · ollama · frontend · webapi · caddy | ใช้ `--no-deps` ทุกคำสั่ง `up` |
| เดาตำแหน่งโฟลเดอร์ ชื่อ image หรือสิทธิ์ไฟล์ | ให้ `docker compose config` บอก — ขั้น P1 |

---

## ขั้น P1 — ให้ compose บอกค่าจริง (อ่านอย่างเดียว ห้ามข้าม)

ทุกคำสั่ง compose ใช้ `-p course-advisor-system` และ `-f` ครบสี่ไฟล์ · **คำสั่งละหนึ่งบรรทัด**

```bash
docker compose -p course-advisor-system -f /home/ubuntu/course-advisor-system/docker-compose.prod.yml -f /home/ubuntu/course-advisor-system/docker-compose.staging.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-backend-2fdc6f2.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-frontend-2fdc6f2.yml config --format json > /tmp/effective.json
```

```bash
python3 -c "import json;d=json.load(open('/tmp/effective.json'));b=d['services']['backend'];print('name:',d.get('name'));print('backend.image:',b.get('image'));print('backend.build:',(b.get('build') or {}).get('context'));[print('backend volume:',v.get('source'),'->',v.get('target'),'ro' if v.get('read_only') else 'rw') for v in b.get('volumes',[])];[print('caddy volume:',v.get('source'),'->',v.get('target'),'ro' if v.get('read_only') else 'rw') for v in d['services']['caddy'].get('volumes',[])]"
```

**รายงานกลับก่อนทำต่อ** — `name` · `backend.image` · `backend.build` context · volume ของ backend · `source` ของ `/srv/web`

| ตรวจอะไร | ต้องได้ |
|---|---|
| `name` | `course-advisor-system` |
| `backend.build` | มีค่า — **ว่าง = หยุดแล้วรายงาน** วิธี deploy จะต่างไปทั้งหมด |
| volume `/srv/documents` | **`ro`** |
| volume `/srv/uploads` | **`rw`** — ถ้าไม่มี แปลว่า compose ยังไม่ได้อัปเดต หยุดแล้วรายงาน |
| volume `/srv/web` | `ro` (Caddy อ่านอย่างเดียว ต้องวางไฟล์บน host) |

**ตรวจ Caddy ว่าเส้นทางใหม่ไปลง backend จริง** (อ่านอย่างเดียว)

```bash
grep -n "handle" /home/ubuntu/course-advisor-system/Caddyfile
```

ลำดับที่ควรเห็นคือ `/api/chat` → `/api/sci-connect-news*` → `/api/admin/*` → `/api/*` → `/assets/*`

เส้นทางใหม่ทั้งหมด (`/api/site/…` `/api/site-admin/…` `/api/auth/…` `/api/uploads/…` `/api/extract-file`) ตกลงที่ `handle /api/*` ซึ่งส่งเข้า backend โดยตัด `/api` ออก — **ไม่ต้องแก้ Caddyfile**

## ขั้น P2 — ตั้งตัวแปรจากค่าจริง

เพื่อให้คำสั่งทุกข้อข้างล่าง **คัดลอกไปรันได้ตรง ๆ ไม่มีช่องให้กรอกเอง** ให้ตั้งตัวแปรสี่ตัวจากของจริงก่อน

```bash
export COMPOSE="-p course-advisor-system -f /home/ubuntu/course-advisor-system/docker-compose.prod.yml -f /home/ubuntu/course-advisor-system/docker-compose.staging.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-backend-2fdc6f2.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-frontend-2fdc6f2.yml"
```

```bash
export CTX=$(python3 -c "import json;print(json.load(open('/tmp/effective.json'))['services']['backend']['build']['context'])") && export IMG=$(python3 -c "import json;d=json.load(open('/tmp/effective.json'));print(d['services']['backend'].get('image') or d['name']+'-backend')") && export WEB=$(python3 -c "import json;print([v['source'] for v in json.load(open('/tmp/effective.json'))['services']['caddy']['volumes'] if v['target']=='/srv/web'][0])") && export OLD_ID=$(docker inspect --format '{{.Image}}' $(docker compose $COMPOSE ps -q backend))
```

```bash
echo "CTX=$CTX" && echo "IMG=$IMG" && echo "WEB=$WEB" && echo "OLD_ID=$OLD_ID" && test -n "$CTX" -a -n "$IMG" -a -n "$WEB" -a -n "$OLD_ID" && test -d "$CTX" && test -d "$WEB" && docker image inspect "$IMG" > /dev/null && echo "ครบทั้งสี่ค่า · โฟลเดอร์มีจริง · ชื่อ image ใช้ได้"
```

**ต้องเห็นบรรทัด `ครบทั้งสี่ค่า · โฟลเดอร์มีจริง · ชื่อ image ใช้ได้`** — ถ้าไม่เห็น หยุดแล้วรายงานว่าค่าใดว่างหรือหาไม่เจอ

`IMG` คือชื่อ image ที่ compose ใช้ — ถ้า compose ไม่ได้ระบุ `image` ไว้ จะเป็นชื่อที่ compose ตั้งเอง (`<project>-backend`) ซึ่งคำสั่งข้างบนยืนยันแล้วว่ามีจริง

> **เปิด shell ใหม่ต้องรันสามคำสั่งนี้ซ้ำ** (และคำสั่งย่อ `run_pipeline` ในขั้น C ด้วย) ตัวแปรและฟังก์ชันไม่ติดไปกับ session ใหม่
> `OLD_ID` คือ image ของ backend ตัวปัจจุบัน ใช้เทียบและใช้ย้อนกลับ — **จดไว้ในที่อื่นด้วย**

## ขั้น P3 — สำรองก่อนแตะอะไรทั้งสิ้น

**ของสำรองคือทางถอยเดียว — ขาดข้อใดข้อหนึ่งให้หยุด**

```bash
docker exec -i course-advisor-system-postgres-1 pg_dump -U postgres -Fc course_advisor > /home/ubuntu/db-backup-2569-10-11.dump && ls -lh /home/ubuntu/db-backup-2569-10-11.dump
```

```bash
docker exec -i course-advisor-system-postgres-1 pg_restore -l /home/ubuntu/db-backup-2569-10-11.dump | head -5
```

อ่านรายการได้ = ไฟล์สำรองใช้ได้จริง ไม่ใช่แค่มีไฟล์

```bash
sudo cp -a $WEB /home/ubuntu/web-backup-2569-10-11 && ls -1 /home/ubuntu/web-backup-2569-10-11 | head
```

ติดป้ายให้ image ตัวปัจจุบัน เพื่อให้ย้อนกลับได้แม้ `latest` ถูกเขียนทับไปแล้ว

```bash
docker tag $OLD_ID course-advisor-backend:pre-phase4-2569-10-11 && test "$(docker image inspect --format '{{.Id}}' course-advisor-backend:pre-phase4-2569-10-11)" = "$OLD_ID" && echo "ป้ายสำรองชี้ image ตัวเดียวกับที่รันอยู่"
```

**ต้องเห็นบรรทัดยืนยัน** — ถ้าไม่เห็น แปลว่าป้ายชี้ไปคนละ image อย่าไปต่อ เพราะจะย้อนกลับไม่ได้

## ขั้น A — migration สิทธิ์ผู้ใช้

เจ้าของจะส่ง `007_web_auth.sql` มาให้ · อ่านทั้งไฟล์ก่อนรัน

```bash
docker exec -i course-advisor-system-postgres-1 psql -U postgres -d course_advisor -v ON_ERROR_STOP=1 -f - < /tmp/007_web_auth.sql
```

```bash
docker exec -i course-advisor-system-postgres-1 psql -U postgres -d course_advisor -c "select role, status, count(*) from public.users group by role, status order by role;"
```

**ผู้ใช้เดิมทั้งหมดต้องเป็น `status='approved'`** — มีใครเป็น `pending` ให้หยุดแล้วรายงาน

```bash
docker exec -i course-advisor-system-postgres-1 psql -U postgres -d course_advisor -c "select count(*) as บันทึกสภาพเดิม from public.migration_007_user_backup; select count(*) as ค่าขัดกัน from public.users where is_admin is distinct from (role='admin');"
```

**`ค่าขัดกัน` ต้องเป็น `0`** และ `บันทึกสภาพเดิม` ต้องเท่ากับจำนวนผู้ใช้เดิม

**ทดสอบว่ารันซ้ำไม่เปลี่ยนสิทธิ์** — ขั้นนี้สำคัญเพราะฉบับก่อนของ migration อนุมัติบัญชีที่รออนุมัติทุกครั้งที่รันซ้ำ

```bash
docker exec -i course-advisor-system-postgres-1 psql -U postgres -d course_advisor -c "select md5(string_agg(id::text || role || status, ',' order by id)) as ลายนิ้วมือก่อน from public.users;"
```

```bash
docker exec -i course-advisor-system-postgres-1 psql -U postgres -d course_advisor -v ON_ERROR_STOP=1 -f - < /tmp/007_web_auth.sql > /dev/null && docker exec -i course-advisor-system-postgres-1 psql -U postgres -d course_advisor -c "select md5(string_agg(id::text || role || status, ',' order by id)) as ลายนิ้วมือหลัง from public.users;"
```

**สองค่าต้องเท่ากันเป๊ะ** — ไม่เท่ากันแปลว่าการรันซ้ำเปลี่ยนสิทธิ์ ให้ถอนกลับทันที (ดูท้ายเอกสาร)

## ขั้น B — deploy backend

เจ้าของจะส่งซอร์สมาให้ · วางทับใน `$CTX`

```bash
grep -c "site_admin" $CTX/backend/app/main.py && grep -c "python-multipart" $CTX/backend/requirements.txt
```

ทั้งสองต้องได้อย่างน้อย `1`

```bash
sudo mkdir -p $CTX/uploads && sudo chown -R 1000:1000 $CTX/uploads && sudo chmod 755 $CTX/uploads && ls -ld $CTX/uploads
```

```bash
docker compose $COMPOSE build backend
```

**ตรวจไฟล์ในคอนเทนเนอร์ก่อน up**

```bash
docker compose $COMPOSE run --rm --no-deps --entrypoint sh backend -c "ls /app/backend/app/api/routes/ /app/backend/app/jobs/ | tr '\n' ' '"
```

ต้องเห็น `site_admin.py` `uploads.py` `extract.py` `sync_sci_news.py`

```bash
docker compose $COMPOSE up -d --no-deps --no-build --force-recreate backend
```

```bash
docker inspect --format '{{.Image}}' $(docker compose $COMPOSE ps -q backend)
```

**ID ต้องต่างจาก `$OLD_ID`**

**ตรวจว่าโฟลเดอร์ไฟล์เขียนได้จริงจากในคอนเทนเนอร์**

```bash
docker compose $COMPOSE exec -T backend sh -c "touch /srv/uploads/.writetest && rm /srv/uploads/.writetest && echo เขียนได้ || echo เขียนไม่ได้"
```

ต้องได้ `เขียนได้` — ถ้าไม่ ให้แก้สิทธิ์โฟลเดอร์แล้วตรวจซ้ำ **ก่อนไปต่อ**

```bash
curl -s https://stpnru-advisor.duckdns.org/api/openapi.json | python3 -c "import sys,json;p=json.load(sys.stdin)['paths'];print(len(p),'เส้นทาง · ใหม่:',[k for k in sorted(p) if k.startswith(('/site','/auth','/uploads'))][:8])"
```

## ขั้น C — นำข้อมูล บัญชี และไฟล์เข้า

### สคริปต์ทั้งสามต้องรัน **ในคอนเทนเนอร์** ไม่ใช่บน host

สำคัญ เพราะค่าที่ระบบตั้งไว้ใช้ได้เฉพาะจากในคอนเทนเนอร์

| ค่า | ในคอนเทนเนอร์ | บน host |
|---|---|---|
| `DATABASE_URL` | `@postgres:5432` — **ถูก** | ชื่อ `postgres` ไม่มีใน DNS ของ host และ **postgres ไม่ได้เปิดพอร์ตออกมา** จึงต่อไม่ได้เลย |
| `UPLOADS_DIR` | `/srv/uploads` — **ถูก** ผูกกับ `$CTX/uploads` บน host | `/srv/uploads` บน host **ไม่ใช่โฟลเดอร์ที่ผูกเข้าคอนเทนเนอร์** ไฟล์จะไปกองที่ไม่มีใครอ่าน แล้วรูปทั้งหมดจะ 404 หลังแก้ URL |

`pipeline/` ไม่ได้อยู่ใน image จึงผูกเข้าไปตอนรันแบบอ่านอย่างเดียว · `-w /app` เพราะ image ตั้ง workdir ไว้ที่ `/app/backend`

ตั้งสองค่านี้ในเชลล์ก่อน — **ส่งเข้าคอนเทนเนอร์ด้วย `-e ชื่อ` เฉย ๆ ค่าจึงไม่ปรากฏในคำสั่งและไม่ติดใน history**

| ตัวแปร | ที่มา |
|---|---|
| `SUPABASE_DB_URL` | Dashboard → Project Settings → Database → Connection string |
| `SUPABASE_URL` · `SUPABASE_SERVICE_ROLE_KEY` | Dashboard → Project Settings → API |

```bash
read -rsp 'SUPABASE_DB_URL: ' SUPABASE_DB_URL && echo && read -rp 'SUPABASE_URL: ' SUPABASE_URL && echo && read -rsp 'SUPABASE_SERVICE_ROLE_KEY: ' SUPABASE_SERVICE_ROLE_KEY && echo && export SUPABASE_DB_URL SUPABASE_URL SUPABASE_SERVICE_ROLE_KEY && echo "ตั้งครบสามค่า (ความยาว ${#SUPABASE_DB_URL}/${#SUPABASE_URL}/${#SUPABASE_SERVICE_ROLE_KEY})"
```

ตั้งคำสั่งย่อสำหรับรันสคริปต์ เพื่อให้สามขั้นข้างล่างสั้นและไม่พิมพ์ผิด

```bash
run_pipeline() { docker compose $COMPOSE run --rm --no-deps -w /app -v "$CTX/pipeline:/app/pipeline:ro" -e SUPABASE_DB_URL -e SUPABASE_URL -e SUPABASE_SERVICE_ROLE_KEY backend python -u -m "$@"; }
```

ซ้อมก่อนว่าเข้าถึงได้ทั้งสองฝั่ง — ฐานข้อมูลของเราและ Supabase ต้นทาง

```bash
run_pipeline pipeline.web.import_from_supabase --dry-run
```

**ถ้าขั้นนี้ฟ้องว่าต่อฐานข้อมูลไม่ได้ อย่าแก้ด้วยการย้ายไปรันบน host** — ให้รายงานข้อความที่ได้

### C1 ข้อมูลหน้าเว็บ

ผล `--dry-run` ของคำสั่งข้างบนคือขั้นนี้แล้ว

**อ่านผลให้ครบแล้วรายงานกลับก่อนรันจริง** — จำนวนแถวแต่ละตาราง · จับคู่หลักสูตรได้กี่รายการจาก 12

```bash
run_pipeline pipeline.web.import_from_supabase --apply
```

```bash
docker exec -i course-advisor-system-postgres-1 psql -U postgres -d course_advisor -c "select 'site_courses' t, count(*) from web.site_courses union all select 'news', count(*) from web.news union all select 'external_news', count(*) from web.external_news union all select 'knowledge', count(*) from web.knowledge_articles union all select 'ai_settings', count(*) from web.ai_settings;"
```

**`site_courses` ต้องได้ 12**

### C2 บัญชีผู้ใช้ — ไม่ต้องให้ใครตั้งรหัสใหม่

```bash
run_pipeline pipeline.web.import_accounts --dry-run
```

รายงานบอกจำนวนและการแบ่งตามสิทธิ์เท่านั้น ไม่มีอีเมลหรือ hash

```bash
run_pipeline pipeline.web.import_accounts --apply
```

```bash
docker exec -i course-advisor-system-postgres-1 psql -U postgres -d course_advisor -c "select role, status, password_scheme, count(*) from public.users group by 1,2,3 order by 1,2;"
```

บัญชีที่ย้ายมาจะเป็น `password_scheme = bcrypt` และ **ใช้รหัสผ่านเดิมได้ทันที** ระบบจะอัปเกรดรูปแบบเองตอนเข้าสู่ระบบครั้งแรก

> **ถ้าไม่มีบัญชี admin เลยหลังย้าย** ให้เลื่อนสิทธิ์หนึ่งคนด้วยคำสั่งนี้ (ไม่มีรหัสผ่านในคำสั่ง จึงไม่ติดใน history)
>
> ```bash
> read -rp 'อีเมลของผู้ที่จะเป็น admin: ' E && docker exec -i course-advisor-system-postgres-1 psql -U postgres -d course_advisor -c "update public.users set role='admin', status='approved' where lower(email)=lower('$E') returning email, role, status;" && unset E
> ```
>
> จากนั้นให้เจ้าของบัญชีกด "ลืมรหัสผ่าน" หรือให้ผู้ดูแลออกลิงก์ที่ `/api/auth/admin/reset-link`

### C3 ไฟล์

```bash
run_pipeline pipeline.web.migrate_storage --dry-run
```

```bash
run_pipeline pipeline.web.migrate_storage --apply
```

**สคริปต์จะไม่แก้ URL ในฐานข้อมูลเลยถ้าดาวน์โหลดพลาดแม้ไฟล์เดียว** — ถ้าพลาด แก้สาเหตุแล้วรัน `--apply --retry-failed`

```bash
cat $CTX/uploads/storage_migration_manifest.json | python3 -c "import sys,json;d=json.load(sys.stdin);print('ทั้งหมด',len(d),'· สำเร็จ',sum(1 for x in d if x['status']=='ok'),'· ล้ม',sum(1 for x in d if x['status']!='ok'))"
```

```bash
docker exec -i course-advisor-system-postgres-1 psql -U postgres -d course_advisor -c "select count(*) as ยังชี้ไป_supabase from web.site_courses where logo_url like '%supabase%';"
```

ต้องได้ `0`

## ขั้น D — ตรวจ API ให้ผ่านครบ **ก่อนแตะหน้าเว็บ**

```bash
curl -s -w '\nHTTP %{http_code}\n' https://stpnru-advisor.duckdns.org/api/site/courses | python3 -c "import sys;t=sys.stdin.read();import json;d=json.loads(t.rsplit('HTTP',1)[0]);print('หลักสูตร',len(d['courses']),'· มีที่ยังชี้ไป supabase:',sum(1 for c in d['courses'] if c.get('logo_url') and 'supabase' in c['logo_url']))"
```

**ต้องได้ 12 หลักสูตร และ 0 ที่ยังชี้ไป supabase** — ไม่ครบ **ห้ามไปขั้น E**

```bash
curl -s -o /dev/null -w 'news %{http_code}\n' https://stpnru-advisor.duckdns.org/api/site/news && curl -s -o /dev/null -w 'external-news %{http_code}\n' https://stpnru-advisor.duckdns.org/api/site/external-news && curl -s -o /dev/null -w 'admin ไม่มี token %{http_code}\n' https://stpnru-advisor.duckdns.org/api/site-admin/courses
```

สองอันแรก `200` · อันท้าย **`403` หรือ `401`**

## ขั้น E — deploy หน้าเว็บ

เจ้าของจะส่ง `dist.tgz` มาให้ · **วางบน host ไม่ใช่ใน container**

```bash
sudo rm -rf /tmp/web-new && mkdir -p /tmp/web-new && tar -xzf /tmp/dist.tgz -C /tmp/web-new && ls -1 /tmp/web-new
```

```bash
grep -rl "supabase" /tmp/web-new/assets/ | head
```

**ต้องไม่มีผลลัพธ์** — ถ้ามีแปลว่า build ผิดชุด **อย่าวางทับ**

```bash
sudo rsync -a --delete /tmp/web-new/ $WEB/ && rm -rf /tmp/web-new /tmp/dist.tgz
```

## ขั้น F — ตั้ง cron ดึงข่าว

```bash
docker compose $COMPOSE exec -T backend python -m app.jobs.sync_sci_news --dry-run
```

```bash
docker compose $COMPOSE exec -T backend python -m app.jobs.sync_sci_news
```

```bash
( crontab -l 2>/dev/null; echo "*/30 * * * * docker compose $COMPOSE exec -T backend python -u -m app.jobs.sync_sci_news >> /home/ubuntu/sync-sci-news.log 2>&1" ) | crontab - && crontab -l | tail -2
```

> **ยังไม่ปิด cron เดิมของ Supabase** — ปล่อยคู่กันไปก่อนได้ เพราะกันซ้ำด้วย `detail_url` · ปิดตัวเดิมเมื่อตรวจรับครบ

---

## ขั้น V — ตรวจรับ (รายงานผลทุกข้อ)

| # | ทดสอบ | ต้องได้ |
|---|---|---|
| V1 | `/api/site/courses` | `200` · **12 หลักสูตร** |
| V2 | เปิดลิงก์เดิม `/courses/<id>` | เปิดได้เหมือนเดิม |
| V3 | เปิด `/` `/courses` `/compare` `/find-major` `/sci-connect` `/careers` | แสดงครบ ไม่มี error ใน console |
| V4 | เข้าสู่ระบบด้วย **รหัสผ่านเดิม** ของบัญชีที่ย้ายมา | `200` — ถ้าไม่ได้ แปลว่าการย้ายบัญชีมีปัญหา |
| V5 | ดู `password_scheme` ของบัญชีนั้นหลังเข้าสู่ระบบ | เปลี่ยนเป็น `bcrypt_sha256` เอง |
| V6 | ใส่รหัสผิด 6 ครั้งติด | ครั้งที่ 6 ได้ **`429`** พร้อม `Retry-After` |
| V7 | เข้า `/admin/dashboard` ด้วยบัญชี **user** | ไม่มีสิทธิ์ |
| V8 | เข้าด้วยบัญชี **editor** | เข้าได้ · ไม่เห็นเมนูผู้ใช้งาน · ไม่มีปุ่มลบ |
| V9 | `DELETE /api/site-admin/courses/<id>` ด้วย token ของ editor | **`403`** และแถวยังอยู่ |
| V10 | admin เพิ่ม/แก้/ลบ หลักสูตร · ข่าว · คลังความรู้ | สำเร็จทุกอย่าง |
| V11 | อัปโหลดโลโก้แล้วเปิด URL ที่ได้ | เปิดได้ |
| V12 | อัปโหลด `.exe` ที่เปลี่ยนนามสกุลเป็น `.png` | **`400`** |
| V13 | เปิดไฟล์คลังความรู้โดยไม่ล็อกอิน | **`401`** |
| V14 | ถอนอนุมัติบัญชีหนึ่ง แล้วให้บัญชีนั้นใช้ token เดิม | **ใช้ไม่ได้ทันที** |
| V15 | `POST /api/chat` คำถามอาชีพ CS | `200` · มี `X-Source-Document` · `X-Source-Page: 3` |
| V16 | `POST /api/recommend-major` และ `/api/compare-courses` | `200` ทั้งคู่ |
| V17 | กดปุ่มดึงข่าวทันทีในหน้าผู้ดูแล | สำเร็จ · จำนวนข่าว **ไม่ลดลง** |
| V18 | **ตัด Supabase แล้วทำ V1–V17 ซ้ำ** (ดูข้อ V18) | **ผ่านเหมือนเดิมทุกข้อ** |

### คำสั่งของ V15–V16

```bash
printf '{"messages":[{"role":"user","content":"สาขาวิทยาการคอมพิวเตอร์ จบแล้วทำงานอะไรได้บ้าง"}]}' > /tmp/v15.json && curl -s -D - -X POST -H 'Content-Type: application/json' --data-binary @/tmp/v15.json https://stpnru-advisor.duckdns.org/api/chat -o /tmp/v15.txt | grep -iE '^HTTP|^x-source' && head -c 200 /tmp/v15.txt && rm -f /tmp/v15.*
```

### V18 — พิสูจน์ว่าระบบอยู่ได้โดยไม่มี Supabase

**ห้ามลบโปรเจกต์** · ใช้สามชั้นนี้แทน hosts entry ซึ่งครอบ subdomain ไม่ได้และคืนค่าไม่แน่นอน

**ชั้นที่ 1 — เบราว์เซอร์ (หลักฐานที่ตรงที่สุด)**

เปิดเว็บด้วยเบราว์เซอร์ → เปิด DevTools → Network → ล้างรายการ → เดินครบ V3, V8, V10, V11
แล้วกรองด้วยคำว่า `supabase`

**ต้องไม่มีคำขอใดเลย** — นี่คือหลักฐานที่พิสูจน์ฝั่งหน้าเว็บได้จริง ต่างจากการบล็อกชื่อโฮสต์

**ชั้นที่ 2 — backend และงานตั้งเวลา ไม่เคยได้รับค่า**

```bash
docker compose $COMPOSE exec -T backend sh -c "env | grep -ci supabase || echo 0"
```

**ต้องได้ `0`** — ไม่มีค่าก็เรียกไม่ได้แม้อยากเรียก

แล้วดูทุกบรรทัดที่เอ่ยถึง Supabase ในโค้ดที่อยู่ใน image จริง

```bash
docker compose $COMPOSE exec -T backend sh -c "grep -rni supabase /app/backend/app --include='*.py'; echo '--- จำนวนบรรทัดทั้งหมด:'; grep -rni supabase /app/backend/app --include='*.py' | wc -l"
```

**ตอนส่งมอบมี 27 บรรทัด และมีเพียง 1 บรรทัดเท่านั้นที่เป็นโค้ดจริง**

```
app/models/user.py:31:    supabase_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
```

บรรทัดนี้คือ **ชื่อคอลัมน์ของเราเอง** จาก migration 006 ไว้แปลงตัวตนตอนย้าย ไม่ได้เรียก Supabase · อีก 26 บรรทัดเป็นคำอธิบายที่เล่าว่าอะไรมาแทนอะไร ซึ่งควรมีไว้

**ห้ามมีบรรทัดอื่นที่เป็น `import` · การเรียกเมท็อด · URL · หรือการอ่านค่า `SUPABASE_*`** — ถ้าเจอ ให้คัดลอกบรรทัดนั้นมารายงาน อย่าไปต่อ

> จำนวนอาจต่างจาก 27 ได้ถ้าเจ้าของแก้คำอธิบายเพิ่ม · **ที่ต้องตรงคือ "ไม่มีบรรทัดโค้ดอื่นนอกจากบรรทัดข้างบน"** ไม่ใช่ตัวเลข

> ตัวตรวจอัตโนมัติ `eval/no_supabase_check.py` ตัดคอมเมนต์และ docstring ออกด้วย `tokenize` ก่อนค้น
> และผ่านครบ 13 ข้อแล้วก่อนส่งมา คำสั่งข้างบนเป็นการยืนยันซ้ำว่า **image ที่ build จริงก็สะอาดเหมือนกัน**

**ชั้นที่ 3 — บล็อกที่ปลายทางจริง (ถ้าต้องการพิสูจน์ระดับเครือข่าย)**

ถ้าจะบล็อกจริง ต้องบล็อก **โดเมนของโปรเจกต์เอง** ไม่ใช่ `supabase.co` เฉย ๆ
หา ref ของโปรเจกต์จาก `SUPABASE_URL` แล้วใส่ทั้งชื่อเต็ม

```bash
sudo iptables -I DOCKER-USER 1 -m string --string "<ref>.supabase.co" --algo bm -j REJECT -m comment --comment "phase4-v18-test"
```

ทำ V1–V17 ซ้ำ แล้ว **คืนค่าด้วยการลบกฎที่มี comment กำกับ** — แน่นอนกว่าการจำลำดับ

```bash
sudo iptables -D DOCKER-USER $(sudo iptables -L DOCKER-USER --line-numbers -n | grep phase4-v18-test | awk '{print $1}') && sudo iptables -L DOCKER-USER -n | grep -c phase4-v18-test
```

ค่าสุดท้ายต้องเป็น `0` = คืนค่าครบ

> ชั้นที่ 3 เป็นทางเลือก · ชั้น 1 กับ 2 พิสูจน์ได้ครบอยู่แล้วและไม่ต้องแตะไฟร์วอลล์

---

## Rollback — ใช้ของสำรอง **ไม่ใช่ `TRUNCATE`**

> ฉบับก่อนเสนอ `truncate web.*` ซึ่ง **ลบข้อมูลที่ผู้ดูแลสร้างหลัง deploy ทิ้งไปด้วย**
> ถ้าย้อนหลังใช้งานไปแล้วหนึ่งวัน ข่าวและหลักสูตรที่เพิ่มในวันนั้นจะหายถาวร

ย้อนทีละส่วน · ถ้าย้อนทั้งหมด ลำดับคือ **E → B → C → A**

| ส่วน | วิธี |
|---|---|
| **E** หน้าเว็บ | `sudo rsync -a --delete /home/ubuntu/web-backup-2569-10-11/ $WEB/` |
| **B** backend | `docker tag course-advisor-backend:pre-phase4-2569-10-11 $IMG` แล้ว `up -d --no-deps --no-build --force-recreate backend` · **เทียบ image ID ต้องเท่ากับ `$OLD_ID`** |
| **C** ข้อมูล | **ไม่ต้องย้อน** — `web.*` เป็นตารางใหม่ที่ไม่มีใครอ่านเมื่อหน้าเว็บย้อนแล้ว · ปล่อยไว้เพื่อไม่ให้ข้อมูลที่เกิดหลัง deploy หาย |
| **C** ไฟล์ | ไฟล์ที่ย้ายมาอยู่บนเซิร์ฟเวอร์ **ไม่ต้องลบ** · URL ที่แก้ไปแล้วย้อนได้จาก manifest (ดูข้างล่าง) |
| **A** migration | รันบล็อก "ถอนกลับ" ท้ายไฟล์ `007_web_auth.sql` ซึ่ง **คืน `is_admin` จาก `public.migration_007_user_backup`** |
| ทั้งก้อน | `pg_restore` จาก `/home/ubuntu/db-backup-2569-10-11.dump` — **ทางสุดท้าย เพราะย้อนทุกอย่างรวมข้อมูลที่เกิดหลัง deploy** |

### ย้อน URL ของไฟล์จาก manifest

รันในคอนเทนเนอร์เหมือนขั้น C — manifest อยู่ที่ `/srv/uploads` และ `DATABASE_URL` ถูกต้องเฉพาะจากในนั้น

```bash
docker compose $COMPOSE run --rm --no-deps -T backend python -c "
import json, os, psycopg
rows = json.load(open('/srv/uploads/storage_migration_manifest.json'))
dsn = os.environ['DATABASE_URL'].replace('postgresql+psycopg://','postgresql://')
with psycopg.connect(dsn) as c:
    n = 0
    for r in rows:
        if r['status'] != 'ok': continue
        new = r['new_path'] if r['column']=='file_path' else '/api/uploads/' + r['new_path']
        n += c.execute(f\"update {r['table']} set {r['column']} = %s where {r['column']} = %s\", (r['original'], new)).rowcount or 0
    c.commit()
print('คืน URL จาก manifest แล้ว', n, 'แถว')
"
```

**ไฟล์บนเซิร์ฟเวอร์ไม่ถูกลบ** — ถ้าจะย้ายกลับมาใหม่ก็ยังอยู่ครบ

### ⚠ `is_admin` ถูกเปลี่ยนจริง

ฉบับก่อนเขียนว่า "`is_admin` ไม่เคยถูกแตะ" ซึ่ง **ไม่จริง** — ทั้ง trigger และขั้นแปลงผู้ใช้เดิมเปลี่ยนค่านี้

การถอนกลับจึงต้องคืนค่าจาก `public.migration_007_user_backup` และ **ต้อง `DROP TRIGGER` ก่อน** ไม่งั้น trigger เขียนทับทันที — ลำดับที่ถูกต้องอยู่ท้ายไฟล์ migration

```bash
docker exec -i course-advisor-system-postgres-1 psql -U postgres -d course_advisor -c "select count(*) as ยังไม่ตรง from public.users u join public.migration_007_user_backup b on b.user_id=u.id where u.is_admin is distinct from b.is_admin;"
```

หลังถอนกลับต้องได้ `0`

---

## สิ่งที่ทดสอบแล้ว และสิ่งที่ยังไม่ได้ทดสอบ

| ระดับ | จำนวน | สถานะ |
|---|---|---|
| **จำลอง** (ฐานข้อมูลปลอม) | **315 ข้อ** | ผ่าน |
| **integration กับ PostgreSQL จริง** (ฐานทดสอบแยก) | **65 ข้อ** | ผ่าน |
| หน้าเว็บ (`node --test`) | **65 ข้อ** | ผ่าน |
| webapi ของเดิม | **82 ข้อ** | ผ่าน |
| **production** | — | **ยังไม่มีเลย** |

ชุด integration ยืนยันกับ PostgreSQL จริงแล้วว่า: migration รันซ้ำไม่เปลี่ยนสิทธิ์ · trigger ทำงาน · เข้าสู่ระบบ/ล็อกบัญชี/เพิกถอนเซสชัน · บัญชีที่ย้ายมาใช้รหัสเดิมได้และอัปเกรดเอง · CRUD · อัปโหลด/ดาวน์โหลด · ดึงข่าวซ้ำไม่เพิ่มซ้ำและไม่ลบของเดิมตอนต้นทางล่ม

**ยังไม่เคยทำบน production เลย** — ทุกขั้นในเอกสารนี้เป็นครั้งแรก **หยุดและรายงานทันทีถ้าเจออะไรไม่ตรงกับที่เขียนไว้** อย่าแก้ด้วยการเดา

## สิ่งที่ต้องรายงานกลับ

1. ค่าจากขั้น P1 ทั้งหมด (รวม volume และสิทธิ์)
2. `$OLD_ID` และ image ID ใหม่
3. ลายนิ้วมือสิทธิ์ก่อน/หลังการรัน migration ซ้ำ (ขั้น A)
4. ผล `--dry-run` ของทั้งสามสคริปต์ **ก่อน** รันจริง
5. จำนวนแถวแต่ละตาราง · จำนวนบัญชีแยกตามสิทธิ์ · จำนวนไฟล์จาก manifest
6. ผล V1–V18 ทุกข้อพร้อม HTTP code จริง
7. ถ้าหยุดกลางทาง — หยุดที่ขั้นไหนและเพราะอะไร
