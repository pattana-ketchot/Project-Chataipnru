# Prompt สำหรับผู้ที่ดูแลเซิร์ฟเวอร์ — Phase 4 (ฉบับหลัง preflight)

> **ฉบับนี้แทนที่ `PHASE4_DEPLOY_PROMPT_2569-10-11.md` ทั้งหมด**
> ค่าทุกค่าในนี้มาจากการอ่านเซิร์ฟเวอร์จริงเมื่อ 12 ต.ค. 2569 — ดู `PHASE4_PREFLIGHT_RESULT_2569-10-12.md`
>
> แก้จากฉบับก่อน 6 จุด: เพิ่มขั้นส่งของจริง · คำสั่งเลื่อนสิทธิ์ใช้ parameterized query ·
> การกู้บัญชีตอนไม่มี SMTP ใช้ได้จริงแล้ว · ตรวจ URL ทุกคอลัมน์ ไม่ใช่แค่ `logo_url` ·
> อธิบาย cron เก่า/ใหม่ให้ถูกและกำหนดจุดปิด · uid อ่านจากคอนเทนเนอร์ ไม่พิมพ์เลขลงไป

---

## งาน

ย้ายระบบแนะแนวหลักสูตร (`stpnru-advisor.duckdns.org`) ให้ใช้ **PostgreSQL บนเซิร์ฟเวอร์เป็นฐานข้อมูลเดียว**

```
S   ส่งของจากเครื่องพัฒนา            ← เจ้าของทำ
P1  ให้ compose บอกค่าจริง (อ่าน)
P2  ตั้งตัวแปรจากค่าที่อ่านได้
P3  สำรองฐานข้อมูล · หน้าเว็บ · image
A   migration 007 (สิทธิ์ผู้ใช้)
B   อัปเดต compose + deploy backend   ← ก่อนข้อมูล เพราะ API ต้องพร้อมรับการตรวจ
C   นำข้อมูล + บัญชี + ไฟล์เข้า
D   ตรวจ API ให้ผ่านครบ              ← ด่านก่อนแตะหน้าเว็บ
E   deploy หน้าเว็บ
F   ตั้ง cron ใหม่บนเซิร์ฟเวอร์
V   ตรวจรับ V1–V21
G   ปิด cron เก่าใน Supabase          ← หลัง V ผ่านครบเท่านั้น
```

**E ต้องอยู่หลัง D เสมอ** — หน้าเว็บใหม่ไม่คุยกับ Supabase แล้ว ถ้า API ยังไม่พร้อม หน้าสาธารณะและหน้าผู้ดูแลจะว่างทั้งหมด

> **ทุกคำสั่งที่ขึ้นต้นด้วย `docker` รันบนเซิร์ฟเวอร์ (ssh เข้าไปแล้ว)** ไม่ใช่บนเครื่องของตัวเอง
> ชื่อคอนเทนเนอร์ชุดนี้ **ซ้ำกับชุดที่รันบนเครื่องพัฒนา** · `docker exec` ที่เผลอรันบนเครื่องตัวเองจะไปโดนฐานข้อมูลของเครื่องนั้นเงียบ ๆ
>
> ```bash
> hostname && docker compose ls
> ```
>
> ต้องได้ `stpnru` และเห็นโปรเจกต์ `course-advisor-system` — ถ้าไม่ใช่ หยุด

## ข้อห้าม

| ห้าม | เหตุผล |
|---|---|
| **ลบหรือปิดโปรเจกต์ Supabase ก่อนขั้น G** | ต้องเก็บไว้จนตรวจรับครบ — เป็นทางถอยเดียวที่เหลือ |
| **`TRUNCATE` หรือ `DELETE` แบบเหมารวม** | ลบข้อมูลที่เกิดหลัง deploy ทิ้งด้วย — ใช้ backup/snapshot แทน |
| แตะ `public.courses` · `course_documents` · `course_chunks` · schema `mko` | ข้อมูลที่ AI ใช้ตอบ ไม่เกี่ยวกับงานนี้ |
| restart postgres · ollama · frontend · webapi · caddy | ใช้ `--no-deps` ทุกคำสั่ง `up` |
| **`chown 1000` แบบพิมพ์เลขลงไป** | host uid 1000 คือ `opc` ไม่ใช่ `ubuntu` (ซึ่งเป็น 1001) — ให้อ่านค่าจากคอนเทนเนอร์ (ขั้น P2) |

---

# ขั้น S — ส่งของจากเครื่องพัฒนา และสำรอง

**ขั้นนี้แยกไปอยู่ในเอกสารของตัวเองแล้ว** เพื่อไม่ให้ตัวเลขและ checksum สองที่ไม่ตรงกัน

### → [PHASE4_SHIP_AND_BACKUP_2569-10-12.md](PHASE4_SHIP_AND_BACKUP_2569-10-12.md)

เอกสารนั้นครอบคลุม

| ส่วน | เนื้อหา |
|---|---|
| S1–S7 | สร้างชุด · build หน้าเว็บ · ตรวจ checksum · ส่งขึ้นเซิร์ฟเวอร์ — **คำสั่ง PowerShell สำหรับ Windows** |
| T1–T5 | ตรวจของที่ถึงเซิร์ฟเวอร์ — **คำสั่ง bash บนเซิร์ฟเวอร์** แยกจากฝั่ง Windows ชัดเจน |
| B1–B5 | ตั้งตัวแปร · สำรองฐานข้อมูล/หน้าเว็บ/compose/main.py/web_compat.py · ติดป้าย image |
| ข้อ 7 | วิธีกรอก `SUPABASE_DB_URL` และ `SUPABASE_SERVICE_ROLE_KEY` แบบไม่ให้ค่าหลุด |

**B1–B5 ของเอกสารนั้นคือสิ่งเดียวกับขั้น P2 และ P3 ข้างล่าง** — ทำครบแล้วไม่ต้องทำซ้ำ
แต่ **ขั้น P1 ยังต้องรันในวันที่ deploy จริง** เพื่อยืนยันว่าค่าบนเซิร์ฟเวอร์ไม่เปลี่ยนไปจากวันที่เตรียมของ

ชุดที่เตรียมไว้ในรอบนี้ (12 ต.ค.) — **รวมงาน careers แล้ว**

| ไฟล์ | จำนวนไฟล์ | sha256 |
|---|---|---|
| `phase4-source.tar.gz` | **29** | `b2e27de4aec1904ac0fd11f853d56b754dafbc32c8968184cc116da32fa03bbd` |
| `phase4-web.tgz` | **19** | `50970307f840bcb39574cef6389ef907d2049526c6f43fd6a1a1ec68c1f650bc` |

---

# ขั้น P1 — ให้ compose บอกค่าจริง (อ่านอย่างเดียว ห้ามข้าม)

ค่าที่ควรได้อยู่ในตารางท้ายขั้นนี้แล้ว (จาก preflight 12 ต.ค.) — **ยังต้องรันซ้ำเพื่อยืนยันว่าไม่เปลี่ยน** ไม่ใช่ข้ามเพราะเอกสารบอกไว้

```bash
docker compose -p course-advisor-system -f /home/ubuntu/course-advisor-system/docker-compose.prod.yml -f /home/ubuntu/course-advisor-system/docker-compose.staging.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-backend-2fdc6f2.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-frontend-2fdc6f2.yml config --format json > /tmp/effective.json && echo "ขนาด $(stat -c%s /tmp/effective.json) ไบต์"
```

```bash
python3 -c "import json;d=json.load(open('/tmp/effective.json'));b=d['services']['backend'];print('name:',d.get('name'));print('backend.image:',b.get('image'));print('backend.build:',(b.get('build') or {}).get('context'));[print('backend volume:',v.get('source'),'->',v.get('target'),'ro' if v.get('read_only') else 'rw') for v in b.get('volumes',[])];[print('caddy volume:',v.get('source'),'->',v.get('target'),'ro' if v.get('read_only') else 'rw') for v in d['services']['caddy'].get('volumes',[])]"
```

**เทียบกับค่าที่ preflight อ่านได้**

| ตรวจอะไร | ค่าที่ควรได้ |
|---|---|
| `name` | `course-advisor-system` |
| `backend.image` | `course-advisor-system-backend:2fdc6f2` |
| `backend.build` | `/home/ubuntu/course-advisor-system` |
| volume `/srv/documents` | **`ro`** |
| volume `/srv/web` ของ caddy | `/home/ubuntu/course-advisor-system/web` · `ro` |
| volume `/srv/uploads` | **ยังไม่มี — ถูกต้อง** ขั้น B จะเพิ่ม |

**ต่างจากนี้ให้หยุดแล้วรายงาน** — มีคนแก้อะไรบนเซิร์ฟเวอร์หลังวันที่ preflight

Caddyfile **ไม่ต้องแก้** — preflight ยืนยันแล้วว่า `handle /api/*` → `uri strip_prefix /api` → `backend:8000` รับเส้นทางใหม่ทั้งหมด ตรวจซ้ำได้ด้วย

```bash
docker exec course-advisor-system-caddy-1 md5sum /etc/caddy/Caddyfile && md5sum /home/ubuntu/course-advisor-system/Caddyfile
```

ทั้งสองต้องเท่ากัน และควรเป็น `0e6b6f1d55f98d0116c62087ef00ce26`

# ขั้น P2 — ตั้งตัวแปรจากค่าจริง

เพื่อให้คำสั่งทุกข้อข้างล่าง **คัดลอกไปรันได้ตรง ๆ ไม่มีช่องให้กรอกเอง**

```bash
export COMPOSE="-p course-advisor-system -f /home/ubuntu/course-advisor-system/docker-compose.prod.yml -f /home/ubuntu/course-advisor-system/docker-compose.staging.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-backend-2fdc6f2.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-frontend-2fdc6f2.yml"
```

```bash
export CTX=$(python3 -c "import json;print(json.load(open('/tmp/effective.json'))['services']['backend']['build']['context'])") && export IMG=$(python3 -c "import json;d=json.load(open('/tmp/effective.json'));print(d['services']['backend'].get('image') or d['name']+'-backend')") && export WEB=$(python3 -c "import json;print([v['source'] for v in json.load(open('/tmp/effective.json'))['services']['caddy']['volumes'] if v['target']=='/srv/web'][0])") && export OLD_ID=$(docker inspect --format '{{.Image}}' $(docker compose $COMPOSE ps -q backend))
```

**uid ต้องอ่านจากคอนเทนเนอร์ ไม่พิมพ์เลขลงไป** — โปรเซสใน backend เป็น `appuser` ซึ่ง**ไม่ใช่** `ubuntu` ของ host

```bash
export APP_UID=$(docker compose $COMPOSE exec -T backend id -u) && export HOST_GID=$(id -g) && echo "APP_UID=$APP_UID (ผู้ใช้ในคอนเทนเนอร์) · HOST_GID=$HOST_GID (ubuntu บน host)"
```

```bash
echo "CTX=$CTX" && echo "IMG=$IMG" && echo "WEB=$WEB" && echo "OLD_ID=$OLD_ID" && test -n "$CTX" -a -n "$IMG" -a -n "$WEB" -a -n "$OLD_ID" -a -n "$APP_UID" -a -n "$HOST_GID" && test -d "$CTX" -a -d "$WEB" && docker image inspect "$IMG" > /dev/null && echo "ครบทุกค่า · โฟลเดอร์มีจริง · ชื่อ image ใช้ได้"
```

**ต้องเห็นบรรทัดสุดท้าย** · ค่าที่ preflight วัดได้คือ `APP_UID=1000` และ `HOST_GID=1001`

> **เปิด shell ใหม่ต้องรันขั้น P2 ทั้งขั้นซ้ำ** (รวมคำสั่งย่อ `run_pipeline` ในขั้น C) ตัวแปรและฟังก์ชันไม่ติดไปกับ session ใหม่
> `OLD_ID` ที่ preflight อ่านได้คือ `sha256:4a45677ec010fc076e283b1e556bd4c1b0b25bc66786b32ec6f64a76ad0cca46` — **จดไว้ในที่อื่นด้วย**

# ขั้น P3 — สำรอง (**ทำแล้วเมื่อ 12 ต.ค. 2569**)

ขั้นนี้คือ B2–B5 ของ [PHASE4_SHIP_AND_BACKUP_2569-10-12.md](PHASE4_SHIP_AND_BACKUP_2569-10-12.md) ซึ่ง **ดำเนินการเสร็จแล้ว**

ชื่อไฟล์จริงมี `TAG` ต่อท้ายเพื่อกันเขียนทับของสำรองชุดอื่น · ค่าที่ใช้อยู่คือ `TAG=2569-10-12`
ทุกค่าถูกบันทึกไว้ที่ `/home/ubuntu/.phase4-vars` (โหมด 600) อ่านกลับมาใช้ได้ด้วย

```bash
. /home/ubuntu/.phase4-vars && echo "TAG=$TAG · CTX=$CTX · WEB=$WEB · OLD_ID=$OLD_ID · APP_UID=$APP_UID · HOST_GID=$HOST_GID"
```

ของสำรองที่มีอยู่จริง

| ของสำรอง | พาธ |
|---|---|
| ฐานข้อมูล | `/home/ubuntu/db-backup-2569-10-12.dump` (53,876,818 ไบต์) |
| สารบัญของ archive | `/home/ubuntu/db-backup-2569-10-12.toc` (313 บรรทัด) |
| checksum ของ dump | `/home/ubuntu/db-backup-2569-10-12.dump.sha256` |
| หน้าเว็บ | `/home/ubuntu/web-backup-2569-10-12/` (40 ไฟล์) |
| compose เดิม | `/home/ubuntu/docker-compose.prod.yml.before-phase4-2569-10-12` |
| `main.py` เดิม | `/home/ubuntu/main.py.before-phase4-2569-10-12` |
| `web_compat.py` เดิม | `/home/ubuntu/web_compat.py.before-phase4-2569-10-12` |
| `requirements.txt` เดิม | `/home/ubuntu/requirements.txt.before-phase4-2569-10-12` |
| checksum ของทั้งสี่ไฟล์ | `/home/ubuntu/before-phase4-2569-10-12.sha256` |
| image เดิม | ป้าย `course-advisor-backend:pre-phase4-2569-10-12` → `sha256:4a45677ec010…` |

> **สิ่งที่การสำรองนี้พิสูจน์แล้ว: อ่านโครงสร้าง archive ได้ (`pg_restore -l` คืน exit 0)**
> **ยังไม่ได้ทดสอบ restore** — ไม่ได้กู้ลงฐานข้อมูลเปล่าแล้วเทียบจำนวนแถว
> ห้ามรายงานว่า "กู้คืนได้" จากหลักฐานชุดนี้

# ขั้น A — migration สิทธิ์ผู้ใช้

```bash
cd /home/ubuntu && mkdir -p phase4-src && tar -xzf phase4-source.tar.gz -C phase4-src && ls phase4-src/db/migrations/
```

อ่านไฟล์ทั้งไฟล์ก่อนรัน

```bash
less /home/ubuntu/phase4-src/db/migrations/007_web_auth.sql
```

```bash
docker exec -i course-advisor-system-postgres-1 psql -U postgres -d course_advisor -v ON_ERROR_STOP=1 -f - < /home/ubuntu/phase4-src/db/migrations/007_web_auth.sql
```

```bash
docker exec -i course-advisor-system-postgres-1 psql -U postgres -d course_advisor -c "select role, status, count(*) from public.users group by role, status order by role;"
```

**ผู้ใช้เดิมทั้งหมดต้องเป็น `status='approved'`** — มีใครเป็น `pending` ให้หยุดแล้วรายงาน

ค่าที่ควรได้ ตามที่ preflight นับไว้: **`admin`/`approved` = 1 คน · `user`/`approved` = 201 คน · รวม 202**
ต่างไปมากให้หยุด (มีคนสมัครเพิ่มระหว่างนี้ได้บ้าง แต่ไม่ควรต่างเป็นสิบ)

```bash
docker exec -i course-advisor-system-postgres-1 psql -U postgres -d course_advisor -c "select password_scheme, substring(password_hash from 1 for 4) as รูปแบบ, count(*) from public.users group by 1,2 order by 3 desc;"
```

**ควรได้ `bcrypt_sha256` + `\$2b\$` ทั้ง 202 แถว** — preflight ตรวจแล้วว่าไม่มีแถว `$2a$` (ซึ่งเป็นของ Supabase) จึงไม่มีแถวใดถูกทำเครื่องหมายผิด
ถ้าเจอ `$2a$` ปนมา **หยุดแล้วรายงาน** เพราะแถวนั้นจะเข้าสู่ระบบไม่ได้จนแก้ `password_scheme` เป็น `bcrypt`

```bash
docker exec -i course-advisor-system-postgres-1 psql -U postgres -d course_advisor -c "select count(*) as บันทึกสภาพเดิม from public.migration_007_user_backup; select count(*) as ค่าขัดกัน from public.users where is_admin is distinct from (role='admin');"
```

**`ค่าขัดกัน` ต้องเป็น `0`** และ `บันทึกสภาพเดิม` ต้องเท่ากับจำนวนผู้ใช้เดิม

**ทดสอบว่ารันซ้ำไม่เปลี่ยนสิทธิ์** — ฉบับก่อนของ migration อนุมัติบัญชีที่รออนุมัติทุกครั้งที่รันซ้ำ

```bash
docker exec -i course-advisor-system-postgres-1 psql -U postgres -d course_advisor -At -c "select md5(string_agg(id::text || role || status, ',' order by id)) from public.users;" > /tmp/perm-before.txt && cat /tmp/perm-before.txt
```

```bash
docker exec -i course-advisor-system-postgres-1 psql -U postgres -d course_advisor -v ON_ERROR_STOP=1 -f - < /home/ubuntu/phase4-src/db/migrations/007_web_auth.sql > /dev/null && docker exec -i course-advisor-system-postgres-1 psql -U postgres -d course_advisor -At -c "select md5(string_agg(id::text || role || status, ',' order by id)) from public.users;" > /tmp/perm-after.txt && diff /tmp/perm-before.txt /tmp/perm-after.txt && echo "รันซ้ำไม่เปลี่ยนสิทธิ์ของใคร"
```

**ต้องเห็นบรรทัดยืนยัน** — ถ้า `diff` ฟ้อง ให้ถอนกลับทันที (ดูท้ายเอกสาร)

# ขั้น B — อัปเดต compose แล้ว deploy backend

## B1 วางซอร์สและ compose ใหม่

```bash
cd /home/ubuntu/phase4-src && tar -cf - . | (cd "$CTX" && tar -xvf -)
```

```bash
diff -u "/home/ubuntu/docker-compose.prod.yml.before-phase4-$TAG" "$CTX/docker-compose.prod.yml"
```

**ต้องต่างกันเฉพาะ env 8 ตัว (`UPLOADS_DIR` · `UPLOAD_MAX_BYTES` · `SMTP_*` 5 ตัว · `PUBLIC_BASE_URL`) และ volume `./uploads:/srv/uploads`** — มีอย่างอื่นให้หยุด

```bash
diff -u "/home/ubuntu/main.py.before-phase4-$TAG" "$CTX/backend/app/main.py"
```

ต้องเห็นเฉพาะการเพิ่ม router ของ Phase 4 (`site` · `site_admin` · `uploads` · `extract`) · **ต้องไม่มีคำว่า `crawl_review`**

```bash
diff -u "/home/ubuntu/web_compat.py.before-phase4-$TAG" "$CTX/backend/app/api/routes/web_compat.py" | head -40
```

ต้องเห็นเฉพาะการเพิ่ม `GET /career-lists` (งาน careers ที่เลือกรวมในรอบนี้)

## B2 ตั้ง `PUBLIC_BASE_URL`

ถ้าไม่ตั้ง ลิงก์รีเซ็ตรหัสผ่านจะออกมาเป็น `null` — ดูขั้น C2

```bash
grep -q '^PUBLIC_BASE_URL=' "$CTX/.env" || printf 'PUBLIC_BASE_URL=https://%s\n' "$(grep -E '^SITE_DOMAIN=' "$CTX/.env" | cut -d= -f2-)" >> "$CTX/.env"; grep -c '^PUBLIC_BASE_URL=' "$CTX/.env"
```

```bash
grep -E '^PUBLIC_BASE_URL=' "$CTX/.env" | sed 's/=.*/= ตั้งแล้ว/'
```

## B3 โฟลเดอร์ไฟล์อัปโหลด — ใช้ uid ที่อ่านมา

เจ้าของเป็น uid ของผู้ใช้ในคอนเทนเนอร์ · กลุ่มเป็น gid ของ `ubuntu` · mode `775` เพื่อให้ **ทั้งสองฝั่งเขียนได้**

```bash
sudo mkdir -p "$CTX/uploads" && sudo chown -R "$APP_UID:$HOST_GID" "$CTX/uploads" && sudo chmod 775 "$CTX/uploads" && stat -c "%u:%g %a %n" "$CTX/uploads"
```

## B4 build และตรวจก่อน up

```bash
docker compose $COMPOSE build backend
```

```bash
docker compose $COMPOSE run --rm --no-deps --entrypoint sh backend -c "ls /app/backend/app/api/routes/ /app/backend/app/jobs/ | tr '\n' ' '; echo; python -c 'import app.main; print(\"main.py นำเข้าได้\")'"
```

ต้องเห็น `site_admin.py` `uploads.py` `extract.py` `sync_sci_news.py` และบรรทัด **`main.py นำเข้าได้`**

> ขั้นนี้คือด่านที่จับได้ว่า `main.py` อ้างโมดูลที่ไม่มี **ก่อน** คอนเทนเนอร์เดิมถูกแทนที่

## B5 up แล้วตรวจ

```bash
docker compose $COMPOSE up -d --no-deps --no-build --force-recreate backend
```

```bash
docker inspect --format '{{.Image}}' $(docker compose $COMPOSE ps -q backend)
```

**ID ต้องต่างจาก `$OLD_ID`**

```bash
docker compose $COMPOSE exec -T backend sh -c 'touch /srv/uploads/.writetest && rm /srv/uploads/.writetest && echo เขียนได้ || echo เขียนไม่ได้'
```

ต้องได้ `เขียนได้` — ถ้าไม่ แก้สิทธิ์แล้วตรวจซ้ำ **ก่อนไปต่อ**

```bash
curl -s https://stpnru-advisor.duckdns.org/api/openapi.json | python3 -c "import sys,json;p=json.load(sys.stdin)['paths'];print(len(p),'เส้นทาง · ใหม่:',[k for k in sorted(p) if k.startswith(('/site','/auth','/uploads'))][:8])"
```

# ขั้น C — นำข้อมูล บัญชี และไฟล์เข้า

## สคริปต์ทั้งสามรัน **ในคอนเทนเนอร์** ไม่ใช่บน host

| ค่า | ในคอนเทนเนอร์ | บน host |
|---|---|---|
| `DATABASE_URL` | `@postgres:5432` — **ถูก** | ชื่อ `postgres` ไม่มีใน DNS ของ host และ **postgres ไม่ได้เปิดพอร์ตออกมา** (preflight ยืนยัน) จึงต่อไม่ได้เลย |
| `UPLOADS_DIR` | `/srv/uploads` — **ถูก** ผูกกับ `$CTX/uploads` | เป็นพาธในคอนเทนเนอร์ · รันบน host ไฟล์จะไปกองที่ `/srv/uploads` ของ host ที่ไม่มีใครอ่าน แล้ว **รูปทุกใบ 404 หลังแก้ URL** |

ค่าของ Supabase **ไม่มีอยู่บนเซิร์ฟเวอร์เลย** (preflight ตรวจแล้ว มีแต่ `VITE_SUPABASE_ANON_KEY` ซึ่งอ่าน `auth.users` และ bucket แบบ private ไม่ได้) เจ้าของต้องเอามาจาก Dashboard

| ตัวแปร | ที่มา |
|---|---|
| `SUPABASE_DB_URL` | Project Settings → Database → Connection string |
| `SUPABASE_URL` · `SUPABASE_SERVICE_ROLE_KEY` | Project Settings → API |

```bash
read -rsp 'SUPABASE_DB_URL: ' SUPABASE_DB_URL && echo && read -rp 'SUPABASE_URL: ' SUPABASE_URL && read -rsp 'SUPABASE_SERVICE_ROLE_KEY: ' SUPABASE_SERVICE_ROLE_KEY && echo && export SUPABASE_DB_URL SUPABASE_URL SUPABASE_SERVICE_ROLE_KEY && echo "ตั้งครบสามค่า (ความยาว ${#SUPABASE_DB_URL}/${#SUPABASE_URL}/${#SUPABASE_SERVICE_ROLE_KEY})"
```

```bash
run_pipeline() { docker compose $COMPOSE run --rm --no-deps -w /app -v "$CTX/pipeline:/app/pipeline:ro" -e SUPABASE_DB_URL -e SUPABASE_URL -e SUPABASE_SERVICE_ROLE_KEY backend python -u -m "$@"; }
```

## C1 ข้อมูลหน้าเว็บ

```bash
run_pipeline pipeline.web.import_from_supabase --dry-run
```

**อ่านผลให้ครบแล้วรายงานกลับก่อนรันจริง** — จำนวนแถวแต่ละตาราง · จับคู่หลักสูตรได้กี่รายการจาก 12

**ถ้าฟ้องว่าต่อฐานข้อมูลไม่ได้ อย่าแก้ด้วยการย้ายไปรันบน host** — รายงานข้อความที่ได้

```bash
run_pipeline pipeline.web.import_from_supabase --apply
```

```bash
docker exec -i course-advisor-system-postgres-1 psql -U postgres -d course_advisor -c "select 'site_courses' t, count(*) from web.site_courses union all select 'news', count(*) from web.news union all select 'external_news', count(*) from web.external_news union all select 'knowledge', count(*) from web.knowledge_articles union all select 'ai_settings', count(*) from web.ai_settings;"
```

**`site_courses` ต้องได้ 12**

## C2 บัญชีผู้ใช้ — ไม่ต้องให้ใครตั้งรหัสใหม่

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

บัญชีที่ย้ายมาเป็น `password_scheme = bcrypt` และ **ใช้รหัสผ่านเดิมได้ทันที** ระบบอัปเกรดรูปแบบเองตอนเข้าสู่ระบบครั้งแรก

### ถ้าไม่มีบัญชี admin เข้าได้เลย — เลื่อนสิทธิ์หนึ่งคน

**ใช้ parameterized query** · อีเมลถูกส่งเป็น**ค่า** ไม่ใช่ต่อสตริงเข้า SQL

เขียน SQL ลงไฟล์ก่อน — **จำเป็น เพราะ `psql` ไม่แทนค่าตัวแปรใน `-c`** มันแทนให้เฉพาะเมื่ออ่านจากไฟล์หรือ stdin

```bash
cat > /tmp/promote-admin.sql <<'SQL'
update public.users
   set role = 'admin', status = 'approved'
 where lower(email) = lower(:'email')
returning email, role, status;
SQL
echo "เขียนไฟล์แล้ว"
```

ดูก่อนว่าอีเมลนั้นมีอยู่จริงกี่แถว (อ่านอย่างเดียว)

```bash
cat > /tmp/check-admin.sql <<'SQL'
select id, email, role, status from public.users where lower(email) = lower(:'email');
SQL
read -rp 'อีเมลของผู้ที่จะเป็น admin: ' E && docker exec -i course-advisor-system-postgres-1 psql -U postgres -d course_advisor -v ON_ERROR_STOP=1 -v email="$E" -f - < /tmp/check-admin.sql
```

**ต้องได้ 1 แถวพอดี** — ได้ 0 แปลว่าไม่มีอีเมลนั้น (ตรวจตัวสะกด หรือบัญชียังไม่ถูกย้าย) · ได้มากกว่า 1 ให้หยุดแล้วรายงาน

แล้วจึงเลื่อนสิทธิ์ (ใช้ค่า `$E` เดิมจากคำสั่งข้างบน)

```bash
docker exec -i course-advisor-system-postgres-1 psql -U postgres -d course_advisor -v ON_ERROR_STOP=1 -v email="$E" -f - < /tmp/promote-admin.sql && unset E && rm -f /tmp/promote-admin.sql /tmp/check-admin.sql
```

**ต้องได้ `UPDATE 1`**

> `:'email'` คือการแทนค่าแบบใส่ quote ของ `psql` เอง · อักขระพิเศษ (`'` `"` `;` `--`) ถูก escape ให้
> ทดสอบแล้วบนเซิร์ฟเวอร์จริงด้วยค่า `x' or 1=1 --` และ `a"b@c.d` — ได้ **0 แถว** ไม่ใช่ 202 แถว (จำนวนผู้ใช้ทั้งหมด)
> ฉบับก่อนเขียน `lower('$E')` ซึ่งเป็นการต่อสตริงเข้า SQL ตรง ๆ

### ถ้ามีคนลืมรหัสผ่านจริง และยังไม่ได้ตั้ง SMTP

ลำดับที่ใช้ได้จริง **ตรวจแล้วทั้งสามขั้น**

1. ปกติ **ไม่ต้องกู้เลย** — รหัสผ่านเดิมย้ายมาด้วย
2. ไม่มี admin เข้าได้ → เลื่อนสิทธิ์ตามคำสั่งข้างบน แล้วคนนั้นเข้าด้วย**รหัสเดิมของตัวเอง**
3. ลืมรหัสจริง → admin เรียก `/api/auth/admin/reset-link` ได้ `reset_url` แล้วส่งให้เจ้าของบัญชีทางช่องทางอื่น

**ข้อ 3 ต้องมีสองอย่างครบ** ไม่งั้นใช้ไม่ได้

| ต้องมี | สถานะ |
|---|---|
| `PUBLIC_BASE_URL` ตั้งแล้ว | ขั้น B2 · ถ้าว่าง `reset_url` จะเป็น `null` ได้แต่ token เปล่า |
| หน้า `/admin/reset-password` ในหน้าเว็บ | **เพิ่มใหม่ในรอบนี้** — ก่อนหน้านี้ไม่มี ลิงก์จึงตายมาตลอด |

ตรวจว่าหน้านั้นมาถึงจริงหลังขั้น E

```bash
curl -s -o /dev/null -w 'reset-password %{http_code}\n' https://stpnru-advisor.duckdns.org/admin/reset-password
```

## C3 ไฟล์

```bash
run_pipeline pipeline.web.migrate_storage --dry-run
```

```bash
run_pipeline pipeline.web.migrate_storage --apply
```

**สคริปต์จะไม่แก้ URL ในฐานข้อมูลเลยถ้าดาวน์โหลดพลาดแม้ไฟล์เดียว** — ถ้าพลาด แก้สาเหตุแล้วรัน `--apply --retry-failed`

```bash
python3 -c "import json;d=json.load(open('$CTX/uploads/storage_migration_manifest.json'));print('ทั้งหมด',len(d),'· สำเร็จ',sum(1 for x in d if x['status']=='ok'),'· ล้ม',sum(1 for x in d if x['status']!='ok'))"
```

### ตรวจ **ทุกคอลัมน์** ไม่ใช่แค่ `logo_url`

`migrate_storage.py` แก้ให้สี่ช่อง: `site_courses.logo_url` · `news.image_url` · `external_news.image_url` · `knowledge_articles.file_path`

แต่ schema `web` มีคอลัมน์ข้อความ **22 คอลัมน์** · ช่องเนื้อหายาว (`knowledge_articles.content` · `*.description`) **อาจมี URL ของ Supabase ฝังอยู่ และสคริปต์ไม่แตะ**

คำสั่งนี้สแกนทุกคอลัมน์ข้อความใน schema `web` โดยสร้าง query จาก `information_schema` เอง จึงไม่ตกหล่นแม้มีคอลัมน์เพิ่มในอนาคต

เขียนตัวสร้าง query ลงไฟล์ก่อน (เลี่ยงปัญหา quote ซ้อนใน shell)

```bash
cat > /tmp/gen_scan.sql <<'SQL'
select string_agg(
         format('select %L as tbl, %L as col, count(*) as n from %I.%I where %I like ''%%supabase%%''',
                table_name, column_name, table_schema, table_name, column_name),
         ' union all ')
  from information_schema.columns
 where table_schema = 'web'
   and data_type in ('text','character varying');
SQL
docker exec -i course-advisor-system-postgres-1 psql -U postgres -d course_advisor -At -f - < /tmp/gen_scan.sql > /tmp/scan.sql && echo "สร้าง query ขนาด $(stat -c%s /tmp/scan.sql) ไบต์"
```

```bash
docker exec -i course-advisor-system-postgres-1 psql -U postgres -d course_advisor -f - < /tmp/scan.sql
```

**ทุกแถวต้องเป็น `0`** · จะได้ 22 แถว (จำนวนคอลัมน์ข้อความใน schema `web` ตอนนี้)

ดูเฉพาะแถวที่ไม่เป็นศูนย์

```bash
docker exec -i course-advisor-system-postgres-1 psql -U postgres -d course_advisor -At -F' | ' -f - < /tmp/scan.sql | awk -F' \\| ' '$3 != 0' | sed 's/^/เหลือ: /' || true
```

**ไม่มีผลลัพธ์ = ผ่าน**

ถ้ายังเหลือ ให้ดูว่าอยู่คอลัมน์ไหน

| คอลัมน์ที่เหลือ | แปลว่า |
|---|---|
| `logo_url` · `image_url` · `file_path` | สคริปต์ทำไม่ครบ → รัน `--apply --retry-failed` แล้วตรวจซ้ำ |
| **`content` หรือ `description`** | **URL ฝังในเนื้อหา สคริปต์ไม่แตะ** → **หยุด แล้วรายงานจำนวนและชื่อคอลัมน์** อย่าแก้เอง ถ้าปิด Supabase ทั้งที่ยังเหลือ รูปในเนื้อหาจะหาย |

# ขั้น D — ตรวจ API ให้ผ่านครบ **ก่อนแตะหน้าเว็บ**

```bash
curl -s https://stpnru-advisor.duckdns.org/api/site/courses | python3 -c "import sys,json;d=json.load(sys.stdin);print('หลักสูตร',len(d['courses']),'· ยังชี้ไป supabase:',sum(1 for c in d['courses'] if c.get('logo_url') and 'supabase' in c['logo_url']))"
```

**ต้องได้ 12 หลักสูตร และ 0 ที่ยังชี้ไป supabase** — ไม่ครบ **ห้ามไปขั้น E**

```bash
curl -s -o /dev/null -w 'news %{http_code}\n' https://stpnru-advisor.duckdns.org/api/site/news && curl -s -o /dev/null -w 'external-news %{http_code}\n' https://stpnru-advisor.duckdns.org/api/site/external-news && curl -s -o /dev/null -w 'admin ไม่มี token %{http_code}\n' https://stpnru-advisor.duckdns.org/api/site-admin/courses
```

สองอันแรก `200` · อันท้าย **`403` หรือ `401`**

# ขั้น E — deploy หน้าเว็บ

**วางบน host ไม่ใช่ใน container** — `/srv/web` ของ Caddy เป็น `ro`

> **ต้องใส่ `--checksum`** · ชุดหน้าเว็บถูกสร้างด้วย mtime คงที่เพื่อให้ build ซ้ำได้ checksum เดิม
> `rsync -a` เปรียบเทียบด้วยขนาดกับ mtime จึง **ข้ามไฟล์ที่ขนาดเท่ากัน** อย่าง `index.html`
> ผลคือ `index.html` เก่ายังอ้างไฟล์ JS ที่ `--delete` ลบไปแล้ว → **ทั้งเว็บล่ม**
> เจอจริงตอน deploy รอบที่สอง · `--checksum` เทียบเนื้อหาจึงไม่พลาด

```bash
sudo rm -rf /tmp/web-new && mkdir -p /tmp/web-new && tar -xzf /home/ubuntu/phase4-web.tgz -C /tmp/web-new && ls -1 /tmp/web-new
```

```bash
(grep -rl supabase /tmp/web-new/assets/ && echo "พบร่องรอย — อย่าวางทับ") || echo "สะอาด วางทับได้"
```

**ต้องได้ `สะอาด วางทับได้`**

```bash
sudo rsync -a --delete --checksum /tmp/web-new/ "$WEB"/ && rm -rf /tmp/web-new
```

# ขั้น F — ตั้ง cron ใหม่บนเซิร์ฟเวอร์

```bash
docker compose $COMPOSE exec -T backend python -m app.jobs.sync_sci_news --dry-run
```

```bash
docker compose $COMPOSE exec -T backend python -m app.jobs.sync_sci_news
```

```bash
( crontab -l 2>/dev/null; echo "*/30 * * * * docker compose -p course-advisor-system -f /home/ubuntu/course-advisor-system/docker-compose.prod.yml -f /home/ubuntu/course-advisor-system/docker-compose.staging.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-backend-2fdc6f2.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-frontend-2fdc6f2.yml exec -T backend python -u -m app.jobs.sync_sci_news >> /home/ubuntu/sync-sci-news.log 2>&1" ) | crontab - && crontab -l | tail -2
```

**ยังไม่ปิด cron เก่า** — เหตุผลอยู่ในขั้น G

---

# ขั้น V — ตรวจรับ (รายงานผลทุกข้อ)

| # | ทดสอบ | ต้องได้ |
|---|---|---|
| V1 | `/api/site/courses` | `200` · **12 หลักสูตร** |
| V2 | เปิดลิงก์เดิม `/courses/<รหัสหลักสูตรเดิม>` | เปิดได้เหมือนเดิม |
| V3 | เปิด `/` `/courses` `/compare` `/find-major` `/sci-connect` `/careers` | แสดงครบ ไม่มี error ใน console |
| V4 | เข้าสู่ระบบด้วย **รหัสผ่านเดิม** ของบัญชีที่ย้ายมา | `200` |
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
| **V18** | **ลิงก์รีเซ็ตรหัสผ่านครบวงจร** | admin ออกลิงก์ → เปิดลิงก์ได้ → ตั้งรหัสใหม่ → เข้าสู่ระบบด้วยรหัสใหม่ได้ · token เดิมใช้ซ้ำ **ไม่ได้** |
| **V19** | **`/api/career-lists`** (งาน careers ที่รวมในรอบนี้) | `200` · **11 หลักสูตร** · ทุกรายการมี `source.file` และเลขหน้า |
| **V20** | หน้า `/careers` ในเบราว์เซอร์ | แสดง 11 หลักสูตร · หลักสูตรที่ยังไม่มีอาชีพที่ตรวจแล้ว **ไม่ขึ้นเลย** (ไม่ใช่ขึ้นแบบว่าง) |
| **V21** | **ตัด Supabase แล้วทำ V1–V20 ซ้ำ** | **ผ่านเหมือนเดิมทุกข้อ** |

## คำสั่งของ V19

```bash
curl -s https://stpnru-advisor.duckdns.org/api/career-lists | python3 -c "import sys,json;d=json.load(sys.stdin)['programmes'];print('หลักสูตร',len(d),'· อาชีพรวม',sum(len(p['careers']) for p in d),'· ไม่มีแหล่งอ้างอิง:',sum(1 for p in d if not p.get('source',{}).get('file')))"
```

**ต้องได้ `หลักสูตร 11` · `อาชีพรวม 69` · `ไม่มีแหล่งอ้างอิง: 0`**

ค่าเหล่านี้มาจากการนับ `mko.v_live_list_items` บน production ตอน preflight — **ข้อมูลอยู่บนเซิร์ฟเวอร์แล้ว ไม่ต้อง migration หรือ import อะไรเพิ่ม**

## คำสั่งของ V15

```bash
printf '{"messages":[{"role":"user","content":"สาขาวิทยาการคอมพิวเตอร์ จบแล้วทำงานอะไรได้บ้าง"}]}' > /tmp/v15.json && curl -s -D - -X POST -H 'Content-Type: application/json' --data-binary @/tmp/v15.json https://stpnru-advisor.duckdns.org/api/chat -o /tmp/v15.txt | grep -iE '^HTTP|^x-source' && head -c 200 /tmp/v15.txt && rm -f /tmp/v15.*
```

## V21 — พิสูจน์ว่าระบบอยู่ได้โดยไม่มี Supabase

**ห้ามลบโปรเจกต์** · ใช้สามชั้นนี้แทน hosts entry ซึ่งครอบ subdomain ไม่ได้และคืนค่าไม่แน่นอน

**ชั้นที่ 1 — เบราว์เซอร์ (หลักฐานที่ตรงที่สุด)**

เปิดเว็บ → DevTools → Network → ล้างรายการ → เดินครบ V3, V8, V10, V11, V20 แล้วกรองด้วยคำว่า `supabase`

**ต้องไม่มีคำขอใดเลย**

**ชั้นที่ 2 — backend ไม่เคยได้รับค่า**

```bash
docker compose $COMPOSE exec -T backend sh -c 'env | grep -ci supabase || echo 0'
```

**ต้องได้ `0`** — ไม่มีค่าก็เรียกไม่ได้แม้อยากเรียก

```bash
docker compose $COMPOSE exec -T backend sh -c "grep -rni supabase /app/backend/app --include='*.py'; echo '--- จำนวนบรรทัด:'; grep -rni supabase /app/backend/app --include='*.py' | wc -l"
```

**ตอนส่งมอบมี 27 บรรทัด และมีเพียง 1 บรรทัดที่เป็นโค้ดจริง**

```
app/models/user.py:31:    supabase_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
```

บรรทัดนี้คือ **ชื่อคอลัมน์ของเราเอง** จาก migration 006 ไว้แปลงตัวตนตอนย้าย · อีก 26 บรรทัดเป็นคำอธิบาย

**ห้ามมีบรรทัดอื่นที่เป็น `import` · การเรียกเมท็อด · URL · หรือการอ่านค่า `SUPABASE_*`** — เจอให้คัดลอกมารายงาน

**ชั้นที่ 3 — บล็อกที่ปลายทางจริง (ทางเลือก)**

ต้องบล็อก **โดเมนของโปรเจกต์เอง** ไม่ใช่ `supabase.co` เฉย ๆ — หา ref จาก `SUPABASE_URL`

```bash
sudo iptables -I DOCKER-USER 1 -m string --string "<ref>.supabase.co" --algo bm -j REJECT -m comment --comment "phase4-v21-test"
```

คืนค่าด้วยการลบกฎที่มี comment กำกับ — แน่นอนกว่าการจำลำดับ

```bash
sudo iptables -D DOCKER-USER $(sudo iptables -L DOCKER-USER --line-numbers -n | grep phase4-v21-test | awk '{print $1}') && sudo iptables -L DOCKER-USER -n | grep -c phase4-v21-test
```

ค่าสุดท้ายต้องเป็น `0` = คืนค่าครบ

---

# ขั้น G — ปิด cron เก่าใน Supabase (**หลัง V ผ่านครบเท่านั้น**)

## cron สองตัวนี้เขียนคนละฐานข้อมูล

| | cron เก่า (ยังทำงานอยู่) | cron ใหม่ (ขั้น F) |
|---|---|---|
| ตัวสั่ง | `pg_cron` **ใน Supabase** · job **`sync-sci-news-every-30-min-v2`** | `crontab` ของ `ubuntu` **บนเซิร์ฟเวอร์** |
| ตัวทำงาน | Edge Function `sync-sci-news` | `python -m app.jobs.sync_sci_news` ในคอนเทนเนอร์ backend |
| **เขียนลงที่** | **ตารางของ Supabase** | **`web.external_news` ของเราเอง** |
| ใครอ่าน | `webapi` → Supabase ด้วย anon key | `backend` → `/api/site/external-news` |

**การกันซ้ำด้วย `detail_url` เป็น unique constraint ใน `web.external_news` ของเราเท่านั้น**
มันมองไม่เห็นและไม่แตะแถวใน Supabase เลย

**ฉบับก่อนเขียนว่า "ปล่อยคู่กันไปก่อนได้ เพราะกันซ้ำด้วย `detail_url`" ซึ่งเป็นเหตุผลผิด**
เหตุผลที่ถูกคือ *สองตัวเขียนลงคนละตารางในคนละฐานข้อมูล จึงชนกันไม่ได้ตั้งแต่ต้น*

และ **ไม่ได้พิสูจน์เลยว่า cron เก่าเลิกใช้แล้ว** — มันยังยิงทุก 30 นาที ยังกินโควตา Supabase และยังเพิ่มภาระให้เว็บต้นทางของคณะอีกทางหนึ่ง

## เงื่อนไขที่ต้องครบก่อนปิด

| # | เงื่อนไข |
|---|---|
| 1 | V1–V21 ผ่านครบ |
| 2 | cron ใหม่ทำงานสำเร็จ **อย่างน้อย 3 รอบติด** — ตรวจจาก `/home/ubuntu/sync-sci-news.log` |
| 3 | `/api/site/external-news` คืนข่าวที่ใหม่กว่าหรือเท่ากับที่หน้าเว็บเดิมแสดง |
| 4 | เจ้าของอนุมัติให้ปิด |

ตรวจเงื่อนไข 2

```bash
grep -c "" /home/ubuntu/sync-sci-news.log && tail -20 /home/ubuntu/sync-sci-news.log
```

## คำสั่งปิด (รันใน SQL editor ของ Supabase)

```sql
select cron.alter_job(
  job_id := (select jobid from cron.job where jobname = 'sync-sci-news-every-30-min-v2'),
  active := false
);
```

```sql
select jobid, jobname, active, schedule
  from cron.job
 where jobname like '%sync-sci-news%'
 order by jobname;
```

**`sync-sci-news-every-30-min-v2` ต้องเป็น `active = false`** · job เดิม `sync-sci-news-every-30-min` ปิดอยู่แล้วตั้งแต่งาน C2

## วิธีเปิดคืน

**ปิดด้วย `alter_job` ไม่ใช่ `unschedule`** — นิยาม job ยังอยู่ครบรวมทั้ง header และ secret จึงเปิดคืนได้ด้วยคำสั่งเดียว

```sql
select cron.alter_job(
  job_id := (select jobid from cron.job where jobname = 'sync-sci-news-every-30-min-v2'),
  active := true
);
```

> **ห้ามใช้ `cron.unschedule`** — จะลบนิยาม job ทิ้ง แล้วต้องสร้างใหม่พร้อมใส่ secret อีกครั้ง
> ซึ่งเป็นขั้นที่งาน C2 ใช้เวลาแก้นานที่สุด (ค่าใน Vault เคยผิดรูปแบบ)

ถ้าต้องกลับไปใช้เส้นทางเดิมทั้งเส้น ให้เปิด job คืน **และ** ย้อนขั้น E (หน้าเว็บ) ตามตาราง Rollback — เพราะหน้าเว็บใหม่ไม่เรียก `webapi` แล้ว

---

# Rollback — ใช้ของสำรอง **ไม่ใช่ `TRUNCATE`**

> ฉบับก่อนเสนอ `truncate web.*` ซึ่ง **ลบข้อมูลที่ผู้ดูแลสร้างหลัง deploy ทิ้งไปด้วย**

ย้อนทีละส่วน · ถ้าย้อนทั้งหมด ลำดับคือ **E → B → C → A**

| ส่วน | วิธี |
|---|---|
| **E** หน้าเว็บ | `sudo rsync -a --delete --checksum /home/ubuntu/web-backup-2569-10-12/ "$WEB"/` |
| **B** backend | `docker tag course-advisor-backend:pre-phase4-2569-10-12 "$IMG"` · คืน compose · `main.py` · `web_compat.py` · `requirements.txt` จาก `/home/ubuntu/*.before-phase4-$TAG` · แล้ว `up -d --no-deps --no-build --force-recreate backend` · **เทียบ image ID ต้องเท่ากับ `$OLD_ID`** |
| **C** ข้อมูล | **ไม่ต้องย้อน** — `web.*` เป็นตารางใหม่ที่ไม่มีใครอ่านเมื่อหน้าเว็บย้อนแล้ว · ปล่อยไว้เพื่อไม่ให้ข้อมูลที่เกิดหลัง deploy หาย |
| **C** ไฟล์ | ไฟล์ที่ย้ายมา **ไม่ต้องลบ** · URL ย้อนได้จาก manifest (ข้างล่าง) |
| **A** migration | รันบล็อก "ถอนกลับ" ท้ายไฟล์ `007_web_auth.sql` ซึ่ง **คืน `is_admin` จาก `public.migration_007_user_backup`** |
| ทั้งก้อน | `pg_restore` จาก `/home/ubuntu/db-backup-2569-10-12.dump` — **ทางสุดท้าย เพราะย้อนข้อมูลที่เกิดหลัง deploy ด้วย** |

## ย้อน URL ของไฟล์จาก manifest

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

## ⚠ `is_admin` ถูกเปลี่ยนจริง

ฉบับแรกเขียนว่า "`is_admin` ไม่เคยถูกแตะ" ซึ่ง **ไม่จริง** — ทั้ง trigger และขั้นแปลงผู้ใช้เดิมเปลี่ยนค่านี้

ต้อง `DROP TRIGGER` ก่อนคืนค่า ไม่งั้น trigger เขียนทับทันที — ลำดับที่ถูกอยู่ท้ายไฟล์ migration

```bash
docker exec -i course-advisor-system-postgres-1 psql -U postgres -d course_advisor -c "select count(*) as ยังไม่ตรง from public.users u join public.migration_007_user_backup b on b.user_id=u.id where u.is_admin is distinct from b.is_admin;"
```

หลังถอนกลับต้องได้ `0`

---

# สิ่งที่ทดสอบแล้ว และสิ่งที่ยังไม่ได้ทดสอบ

| ระดับ | จำนวน | สถานะ |
|---|---|---|
| **จำลอง** (ฐานข้อมูลปลอม) | **315 ข้อ** | ผ่าน |
| **integration กับ PostgreSQL จริง** (ฐานทดสอบแยก) | **65 ข้อ** | ผ่าน |
| หน้าเว็บ (`node --test`) | **79 ข้อ** | ผ่าน |
| webapi ของเดิม | **82 ข้อ** | ผ่าน |
| frontend ของเดิม (`vitest`) | **33 ข้อ** | ผ่าน |
| **preflight บนเซิร์ฟเวอร์จริง** | — | **อ่านครบแล้ว** ดู `PHASE4_PREFLIGHT_RESULT_2569-10-12.md` |
| **production (เขียน)** | — | **ยังไม่มีเลย** |

**ยังไม่เคยเขียนอะไรลง production เลย** — ทุกขั้นที่เขียนในเอกสารนี้เป็นครั้งแรก **หยุดและรายงานทันทีถ้าเจออะไรไม่ตรงกับที่เขียนไว้** อย่าแก้ด้วยการเดา

# สิ่งที่ต้องรายงานกลับ

1. ผล S4 — `sha256sum -c` และจำนวนไฟล์
2. ค่าจากขั้น P1 ทั้งหมด และว่าตรงกับตารางเทียบไหม
3. `APP_UID` · `HOST_GID` · `OLD_ID` และ image ID ใหม่
4. `diff` ของ compose และ `main.py` ในขั้น B1
5. ลายนิ้วมือสิทธิ์ก่อน/หลังรัน migration ซ้ำ (ขั้น A)
6. ผล `--dry-run` ของทั้งสามสคริปต์ **ก่อน** รันจริง
7. จำนวนแถวแต่ละตาราง · บัญชีแยกตามสิทธิ์ · ไฟล์จาก manifest
8. **ผลสแกนทุกคอลัมน์ในขั้น C3** — ถ้าเหลือ ให้บอกชื่อคอลัมน์และจำนวน
9. ผล V1–V21 ทุกข้อพร้อม HTTP code จริง
10. ถ้าหยุดกลางทาง — หยุดที่ขั้นไหนและเพราะอะไร
