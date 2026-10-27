# M3 — Production Deployment Runbook

> **เอกสารนี้จัดทำแบบ READ-ONLY** — ยังไม่ได้ deploy ไม่ได้ restart ไม่ได้แก้ `.env` ไม่ได้เขียนฐานข้อมูล ไม่ได้ push/merge
> ทุกคำสั่งในเอกสารนี้คือสิ่งที่ **จะ** ทำเมื่อได้รับอนุมัติ ไม่ใช่สิ่งที่ทำไปแล้ว

| รายการ | ค่า |
|---|---|
| วันที่จัดทำ | 10 ตุลาคม 2569 |
| Commit ที่จะ deploy | `427ce19` บน branch `mko-phase2` |
| Image ปัจจุบันบน production | `course-advisor-system-webapi:latest` = `1163e36361d9` |
| Rollback tag | `course-advisor-system-webapi:rollback-pre-m3` = `1163e36361d9` **พร้อมแล้ว** |
| สถานะ | `M3_SUPABASE_READINESS_CONFIRMED` · S1 `ready = true` · build + tests ผ่าน |

---

## 1. สภาพ production ตอนนี้ (ตรวจแล้ว)

### 1.1 ไฟล์ใน `webapi/`

| ไฟล์ | บน production | ใน repo (`427ce19`) | ต้องทำ |
|---|---|---|---|
| `api/` | **10 ไฟล์** | ไม่อยู่ใน git (`.gitignore:49`) | **ห้ามแตะ ห้ามลบ** |
| `server.mjs` | 4,151 ไบต์ (เก่า) | 15,815 ไบต์ | **เขียนทับ** |
| `auth.mjs` | **ไม่มี** | 29,042 ไบต์ | **เพิ่มใหม่** |
| `db.mjs` | **ไม่มี** | 14,403 ไบต์ | **เพิ่มใหม่** |
| `package-lock.json` | **ไม่มี** | 31,378 ไบต์ | **เพิ่มใหม่ — `npm ci` บังคับต้องมี** |
| `package.json` | มี | 345 ไบต์ | เขียนทับ |
| `Dockerfile` | มี (เก่า) | 3,117 ไบต์ | **เขียนทับ** |
| `node_modules/` | — | ไม่อยู่ใน git | ห้ามแตะ |

> ถ้าลืม `package-lock.json` → `RUN npm ci` **ล้มทันทีตอน build** (ไม่เงียบ ออกแบบไว้แบบนั้น)
> ถ้าลืม `auth.mjs` หรือ `db.mjs` → คอนเทนเนอร์ **พังตอนเริ่มทำงาน** เพราะ `server.mjs` นำเข้าทั้งคู่ตั้งแต่บรรทัดแรก

### 1.2 `docker-compose.prod.yml` — ยังไม่มีส่วนของ M3 เลย

service `webapi` บน production ตอนนี้มีแค่

```yaml
  webapi:
    build:
      context: ./webapi
    restart: unless-stopped
    environment:
      VITE_SUPABASE_URL: ${VITE_SUPABASE_URL}
      VITE_SUPABASE_ANON_KEY: ${VITE_SUPABASE_ANON_KEY}
      GOOGLE_GENERATIVE_AI_API_KEY: ${GOOGLE_GENERATIVE_AI_API_KEY:-}
    expose:
      - "3001"
```

| คีย์ของ M3 | มีใน production |
|---|---|
| `WEBAPI_DB_HOST` / `WEBAPI_DB_PORT` / `WEBAPI_DB_NAME` / `WEBAPI_DB_USER` | **ไม่มี** |
| `ADVISOR_WEB_PASSWORD` | **ไม่มี** |
| `depends_on: postgres (service_healthy)` | **ไม่มี** |

**นี่คือกับดักที่อันตรายที่สุดของ deploy รอบนี้** — ถ้าคัดลอกแต่โค้ดแล้ว build ใหม่โดยลืม compose คอนเทนเนอร์จะ **ขึ้นได้ตามปกติและ `/healthz` ตอบ `status: ok`** แต่ `dbConfigured` เป็น `false` แปลว่าการแปลงตัวตนไม่ทำงานเลย โดยไม่มีอะไรฟ้อง

> ข้อดีที่ออกแบบไว้: compose ของใหม่ใช้ `${ADVISOR_WEB_PASSWORD:?ต้องตั้งค่าใน .env}` — ถ้า `.env` ยังไม่มีคีย์นี้ **`docker compose` จะปฏิเสธไม่ยอมขึ้นเลย** ไม่ใช่ขึ้นแล้วพังเงียบ จึงต้องทำขั้น `.env` ก่อนเสมอ

### 1.3 `.env` บน production

| คีย์ | สถานะ |
|---|---|
| `ADVISOR_API_PASSWORD` | มี |
| `ADVISOR_INGEST_PASSWORD` | มี |
| **`ADVISOR_WEB_PASSWORD`** | **ยังไม่มี** ← ต้องเพิ่ม |

ตรวจด้วยการนับชื่อคีย์เท่านั้น **ไม่ได้อ่านค่าใด ๆ**

### 1.4 Role `advisor_web` ในฐานข้อมูล — พร้อมแล้ว

| รายการ | ค่า |
|---|---|
| มี role | **ใช่** · `login = true` · `superuser = false` · `createdb = false` |
| สิทธิ์บน `public.users` | `SELECT` บน **`id`, `is_active`, `supabase_user_id` เท่านั้น** |
| อ่าน `email` ได้ไหม | **ไม่ได้** — ไม่มี grant |
| สิทธิ์เขียน `public.users` (`INSERT`/`UPDATE`/`DELETE`) | **ไม่มี** — ไม่มีสิทธิ์ระดับตารางเลย มีเฉพาะ `SELECT` ระดับคอลัมน์ |

**นี่คือสิ่งที่ M3 ใช้** — `db.mjs` รันเฉพาะ `RESOLVER_SQL` ซึ่งเป็น `SELECT` บน `public.users` เท่านั้น **การ deploy รอบนี้จึงไม่ต้องเขียนฐานข้อมูลเลยแม้แต่คำสั่งเดียว**

#### ⚠ ขอบเขตที่ต้องเข้าใจให้ตรง — role นี้เขียน `web` schema ได้

`advisor_web` ไม่ใช่ role อ่านอย่างเดียว เป็น role ที่เว็บไซต์ใช้กับข้อมูลของตัวเองด้วย จึงมีสิทธิ์เขียนใน schema `web`

| ตาราง | สิทธิ์ |
|---|---|
| `public.users` | **ไม่มีสิทธิ์ระดับตาราง** (มีเฉพาะ `SELECT` 3 คอลัมน์) |
| `web.ai_settings` | `SELECT`, `UPDATE` |
| `web.external_news` | `SELECT` |
| `web.knowledge_articles` | **`INSERT`, `SELECT`, `UPDATE`** |
| `web.news` | **`INSERT`, `SELECT`, `UPDATE`** |
| `web.site_courses` | **`INSERT`, `SELECT`, `UPDATE`** |

| ประเด็น | คำตอบ |
|---|---|
| M3 ทำให้แย่ลงไหม | **ไม่** — สิทธิ์ชุดนี้มีอยู่ก่อนแล้วจากงาน `web` schema ต้นเดือน ต.ค. ไม่ได้เกิดจาก M3 |
| โค้ด M3 แตะ `web` schema ไหม | **ไม่** — ไม่มีการอ้างถึง schema นี้ใน `db.mjs` เลย |
| ข้อห้ามของ M3 ยังบังคับได้ไหม | **ได้** — "สร้างผู้ใช้ใหม่อัตโนมัติไม่ได้" และ "fallback ด้วย email ไม่ได้" ถูกบังคับด้วยสิทธิ์บน `public.users` ซึ่งยังแน่นอยู่ |
| ควรทำอะไรต่อ | พิจารณาภายหลังว่าควรแยก role อ่านอย่างเดียวสำหรับ M3 โดยเฉพาะหรือไม่ — **ไม่ใช่งานของรอบนี้** |

> เขียนไว้เพื่อให้คนที่อ่านตอน deploy ไม่เข้าใจผิดว่า ถ้าโค้ดพลาดแล้วจะเขียนอะไรไม่ได้เลย

---

### 1.5 compose ใหม่กระทบบริการอื่นหรือไม่ — ตรวจแล้ว ไม่กระทบ

เทียบ `docker-compose.prod.yml` ของ production กับของ repo ทั้งไฟล์ (ตัดคอมเมนต์และบรรทัดว่าง และลบ `\r` ออกก่อนเพราะของบนเซิร์ฟเวอร์เป็น CRLF)

**ความต่างทั้งหมดมีเพียง 2 จุด และอยู่ใน service `webapi` ทั้งคู่**

```
+     depends_on:
+       postgres:
+         condition: service_healthy
+       WEBAPI_DB_HOST: postgres
+       WEBAPI_DB_PORT: "5432"
+       WEBAPI_DB_NAME: course_advisor
+       WEBAPI_DB_USER: advisor_web
+       ADVISOR_WEB_PASSWORD: ${ADVISOR_WEB_PASSWORD:?ต้องตั้งค่าใน .env}
```

| รายการ | ผล |
|---|---|
| รายชื่อ service | **เหมือนกันทุกตัว** — `postgres` `ollama` `backend` `frontend` `webapi` `caddy` |
| volume | **เหมือนกัน** — `caddy_data` `caddy_config` `pgdata` `ollama_models` |
| `postgres` / `ollama` / `backend` / `frontend` / `caddy` | **ไม่มีการเปลี่ยนแปลงแม้แต่บรรทัดเดียว** |
| คอนเทนเนอร์ `db-viewer` | ไม่ได้อยู่ใน compose นี้ จึงไม่ถูกกระทบ |

#### ข้อควรระวังที่เกิดจาก `depends_on`

การเพิ่ม `depends_on: postgres (condition: service_healthy)` เปลี่ยนกราฟการพึ่งพา ถ้าสั่ง `up -d` **โดยไม่ใส่ `--no-deps`** compose อาจไปแตะ `postgres` ซึ่ง backend ใช้งานอยู่

> **ทุกคำสั่ง `up` ในเอกสารนี้จึงใส่ `--no-deps` เสมอ** ทั้งตอน deploy และตอน rollback

ตรวจแล้วว่าเงื่อนไขนี้ใช้ได้จริง — `postgres` ของ production **มี healthcheck อยู่แล้ว** (`pg_isready -U postgres -d course_advisor` ทุก 10 วินาที) และสถานะปัจจุบันเป็น `healthy` (ขึ้นมา 7 สัปดาห์) ถ้าไม่มี healthcheck เงื่อนไข `service_healthy` จะทำให้ compose ปฏิเสธไม่ยอมขึ้น


---

## 2. เงื่อนไข GO / NO-GO

### 2.1 ต้องครบทุกข้อก่อนเริ่ม (GO)

| # | เงื่อนไข | สถานะตอนนี้ |
|---|---|---|
| 1 | S1 `ready = true` ใน Supabase | **ผ่าน** |
| 2 | Rollback tag `:rollback-pre-m3` ชี้ image เดิม | **ผ่าน** — `1163e36361d9` |
| 3 | Build ผ่าน + import 7/7 + `/healthz` ตอบ | **ผ่าน** (ทดสอบในเครื่อง) |
| 4 | Regression 82/82 | **ผ่าน** |
| 5 | Role `advisor_web` + สิทธิ์ถูกต้อง | **ผ่าน** |
| 6 | มีรหัสผ่าน `advisor_web` (hex 64) อยู่กับเจ้าของ | **ต้องยืนยัน** |
| 7 | สำรองฐานข้อมูลเสร็จ | **ต้องทำตามข้อ 3.1** |
| 8 | สำรอง `docker-compose.prod.yml` และ `.env` เดิม | **ต้องทำตามข้อ 3.1** |

### 2.2 หยุดทันที (NO-GO) ถ้าเจอข้อใดข้อหนึ่ง

| อาการ | ทำอะไร |
|---|---|
| จำนวนไฟล์ใน `webapi/api/` ไม่ใช่ **10** | **หยุด** กู้จากไฟล์สำรองก่อน |
| `docker compose build` ล้ม | **หยุด** ไม่ต้อง `up` |
| image ใหม่ไม่มี `auth.mjs` / `db.mjs` / `api/` ครบ | **หยุด** ไม่ต้อง `up` |
| `/healthz` → `dbConfigured: false` | **หยุดและ rollback** — compose หรือ `.env` ไม่ครบ |
| **ตรวจการเชื่อมต่อ (ข้อ 4.0) ได้ `password authentication failed`** | **rollback ทันที** — รหัสผ่านใน `.env` ไม่ตรงกับของ role `advisor_web` · **ห้ามแก้รหัสผ่านใน PostgreSQL เพื่อให้ผ่าน** ต้องหาค่าที่ถูกมาใส่ `.env` แทน |
| **ตรวจการเชื่อมต่อได้ `permission denied` (`42501`)** | **rollback** — grant ของ role เปลี่ยนไปจากที่ตรวจไว้ ต้องตรวจสิทธิ์ก่อนลองใหม่ |
| **ตรวจการเชื่อมต่อได้ timeout หรือ `ECONNREFUSED`** | **rollback** — `depends_on` หรือ network ไม่ถูกต้อง |
| `/healthz` → `status` ไม่ใช่ `ok` | **rollback ทันที** |
| เส้นทางข่าว 2 เส้นทางไม่ตอบ 200 | **rollback ทันที** |
| `extract-file` พร้อม token ได้ **403** | **rollback ทันที** — ด่านใหม่ล็อกผู้ดูแลออก |
| `ingest` **ไม่มี token** ได้อย่างอื่นที่ไม่ใช่ 401 | **rollback ทันที** — ด่านไม่ทำงาน มีความเสี่ยงเขียนข้อมูล |
| เห็นรหัสผ่านโผล่ใน log | **rollback** และตรวจ `db.mjs` |

---

## 3. ขั้นตอน Deploy

> ทุกคำสั่งรันบน **production** ผ่าน `ssh -i ~/.ssh/oci.key ubuntu@161.118.237.37` แล้ว `cd ~/course-advisor-system`
>
> ⚠ เครื่องของเจ้าของมีคอนเทนเนอร์ชื่อ `course-advisor-system-postgres-1` เหมือนกันเป๊ะ
> **ยืนยันว่าอยู่บนเซิร์ฟเวอร์ก่อนเสมอ** — นับ `public.users` ต้องได้ **201** (เครื่องตัวเองได้ 56)

### 3.1 สำรองก่อน (บังคับ)

```bash
cd ~/course-advisor-system
TS=$(date +%Y%m%dT%H%M%S)
bash scripts/backup_db.sh
cp docker-compose.prod.yml ~/m3-backup-compose-$TS.yml
cp .env ~/m3-backup-env-$TS
chmod 600 ~/m3-backup-env-$TS
tar -czf ~/m3-backup-webapi-api-$TS.tar.gz -C webapi api
tar -tzf ~/m3-backup-webapi-api-$TS.tar.gz | grep -c 'js$'
echo "สำรองไว้ที่ ~/m3-backup-*-$TS"
```

บรรทัดนับไฟล์ต้องได้ **10** · `backup_db.sh` มีอยู่แล้วในรีโป ไม่ต้องเขียนใหม่

### 3.2 เพิ่ม `ADVISOR_WEB_PASSWORD` ลง `.env`

ใช้ขั้นตอนเดิมจาก `M3_WEBAPI_POSTGRES_CONNECTION_DESIGN.md` ข้อ 8.3 **ไม่ประดิษฐ์ใหม่**

**ขั้น A — รับค่าโดยไม่แสดงบนจอและไม่เข้า history**

```bash
read -rsp 'ADVISOR_WEB_PASSWORD: ' AWP && echo; echo "ความยาว = ${#AWP}  (ต้องเป็น 64)"
```

**ขั้น B — ได้ 64 แล้วค่อยวางก้อนนี้**

```bash
cd ~/course-advisor-system
if [[ ! "$AWP" =~ ^[0-9a-f]{64}$ ]]; then
  echo 'ไม่ผ่าน: ต้องเป็นเลขฐานสิบหกตัวพิมพ์เล็ก 64 ตัวเท่านั้น — ไม่เขียนอะไรทั้งสิ้น'
elif grep -q '^ADVISOR_WEB_PASSWORD=' .env; then
  echo 'มีคีย์นี้อยู่แล้ว — ไม่เขียนทับ'
else
  printf 'ADVISOR_WEB_PASSWORD=%s
' "$AWP" >> .env
  echo 'เพิ่มแล้ว'
fi
unset AWP
grep -c '^ADVISOR_WEB_PASSWORD=' .env
ls -l .env
```

`grep -c` ต้องได้ **1** เท่านั้น · `.env` ต้องยังเป็น `600 ubuntu:ubuntu`

| กลไกป้องกัน | ทำอะไร |
|---|---|
| `read -rsp` | ไม่แสดงค่า ไม่เข้า history |
| **`[[ =~ ^[0-9a-f]{64}$ ]]`** | ตรวจทั้ง**ความยาวและชุดอักขระ** — จับกรณีวางซ้ำ วางขาด มีช่องว่างติดมา มีตัวพิมพ์ใหญ่ หรือเผลอวางค่าที่ไม่ใช่ hex · เทียบในตัว bash เอง **ไม่ส่งผ่าน pipe และไม่เข้า argv** จึงไม่โผล่ใน `ps` |
| **`if / elif / else`** | แทนโซ่ `&&`/`||` เดิมที่อ่านยากและมีโอกาสตีความลำดับผิด — ตอนนี้แต่ละกรณีมีทางออกทางเดียวชัดเจน |
| ตรวจว่ามีอยู่แล้วก่อนเขียน | ไม่เขียนทับของเดิมโดยไม่ตั้งใจ |
| `>>` ไม่ใช่ `>` | ไม่ทับทั้งไฟล์ |
| `grep -c` ปิดท้าย | ต้องได้ 1 ไม่ใช่ 0 (ไม่ได้เพิ่ม) และไม่ใช่ 2 (เพิ่มซ้ำ) |

**ห้าม `cat .env` · ห้ามอ่านค่าเดิมออกมาดู · ห้ามใส่ค่าเป็น argument ของคำสั่ง**

> **ไม่เปลี่ยนรหัสผ่านของ role ในฐานข้อมูล** — ขั้นนี้เพียงบันทึกค่าที่ตั้งไว้แล้วตอน provision ลง `.env` เท่านั้น ไม่มีคำสั่ง `ALTER ROLE` อยู่ที่ใดในเอกสารนี้

### 3.3 ส่งไฟล์ขึ้น production

**รันจากเครื่องของเจ้าของ** ไม่ใช่บนเซิร์ฟเวอร์

```bash
cd /d/workspace/course-advisor-system-mko2
git -c core.autocrlf=false archive --format=tar.gz -o /tmp/m3-427ce19.tar.gz 427ce19
scp -i ~/.ssh/oci.key /tmp/m3-427ce19.tar.gz ubuntu@161.118.237.37:~/
```

> **กับดัก CRLF** — บนเครื่องนี้ `core.autocrlf` เป็น `true` และ `git archive` ใช้ค่านั้นด้วย
> ถ้าไม่ใส่ `-c core.autocrlf=false` จะได้ไฟล์ CRLF ทั้งชุด เคยทำให้ตัวตรวจ diff รายงานผิด 49 จาก 59 ไฟล์มาแล้ว

**แตกลงที่พักก่อน แล้วคัดลอกทีละไฟล์ — ไม่แตะ `api/`**

```bash
cd ~/course-advisor-system
mkdir -p /tmp/m3-extract && tar -xzf ~/m3-427ce19.tar.gz -C /tmp/m3-extract
cp /tmp/m3-extract/webapi/server.mjs        webapi/server.mjs
cp /tmp/m3-extract/webapi/auth.mjs          webapi/auth.mjs
cp /tmp/m3-extract/webapi/db.mjs            webapi/db.mjs
cp /tmp/m3-extract/webapi/package.json      webapi/package.json
cp /tmp/m3-extract/webapi/package-lock.json webapi/package-lock.json
cp /tmp/m3-extract/webapi/Dockerfile        webapi/Dockerfile
cp /tmp/m3-extract/docker-compose.prod.yml  docker-compose.prod.yml
rm -rf /tmp/m3-extract
```

> **ทำไมคัดลอกทีละไฟล์** — `rsync --delete` หรือการแตก tar ทับทั้งโฟลเดอร์มีโอกาสลบ `webapi/api/` ซึ่ง **ไม่อยู่ใน git จึงไม่อยู่ใน archive** การ `cp` ทีละไฟล์ลบอะไรไม่ได้เลยตามนิยาม

### 3.4 ยืนยันก่อน build

```bash
cd ~/course-advisor-system/webapi
find api -type f | wc -l
find api -type l | wc -l
ls -l server.mjs auth.mjs db.mjs package-lock.json Dockerfile
```

ไฟล์ต้องได้ **10** · symlink ต้องได้ **0** · ขนาดต้องตรงตามนี้

| ไฟล์ | ขนาดที่ต้องได้ |
|---|---|
| `server.mjs` | 15,815 |
| `auth.mjs` | 29,042 |
| `db.mjs` | 14,403 |
| `package-lock.json` | 31,378 |
| `Dockerfile` | 3,117 |

```bash
cd ~/course-advisor-system
grep -c 'WEBAPI_DB_USER' docker-compose.prod.yml
grep -c 'ADVISOR_WEB_PASSWORD' docker-compose.prod.yml
```

ทั้งสองบรรทัดต้องได้ **1**

### 3.5 Build

```bash
cd ~/course-advisor-system
docker compose -f docker-compose.prod.yml build webapi
```

**ถ้าล้ม → หยุด ไม่ต้อง `up`** ของเดิมยังทำงานอยู่ ไม่มีอะไรเสียหาย

### 3.6 ยืนยันของใน image ก่อน `up`

```bash
IMG=$(docker images -q course-advisor-system-webapi:latest)
docker run --rm --entrypoint sh "$IMG" -c 'ls /app; echo ---; find /app/api -type f | wc -l; ls /app/*.test.mjs 2>/dev/null || echo "ไม่มีไฟล์ทดสอบ ถูกต้อง"'
docker run --rm --entrypoint node "$IMG" -e "console.log(require('pg/package.json').version)"
```

| ต้องเห็น | ค่า |
|---|---|
| `server.mjs` `auth.mjs` `db.mjs` | ครบทั้งสาม |
| ไฟล์ใน `/app/api` | **10** |
| `*.test.mjs` | **ต้องไม่มี** |
| รุ่นของ `pg` | **8.23.1** |

**ถ้าข้อใดไม่ตรง → หยุด ไม่ต้อง `up`** ขั้นนี้คือกับดักที่ Dockerfile เตือนไว้เอง และเป็นบทเรียน "deploy ต้อง build image ใหม่" — คัดลอกไฟล์แล้ว restart เฉย ๆ จะรันโค้ดเก่า

### 3.7 ขึ้นบริการ (แตะเฉพาะ webapi)

```bash
cd ~/course-advisor-system
docker compose -f docker-compose.prod.yml up -d --no-deps webapi
docker compose -f docker-compose.prod.yml ps webapi
```

`--no-deps` เพื่อไม่ให้ไป restart `postgres` ที่ให้บริการ backend อยู่

รอจนสถานะเป็น `healthy` — start-period 10 วินาที + retries 3 ที่ interval 30 วินาที

---

## 4. Smoke Test

> **ข้อ 7 เป็นข้อเดียวที่ใช้ token และเลือก endpoint ที่ตรวจแล้วว่าไม่เขียนข้อมูลใด ๆ**

| # | ทดสอบ | ต้องได้ | เขียนข้อมูล |
|---|---|---|---|
| 1 | สถานะคอนเทนเนอร์ | `healthy` | ไม่ |
| 2 | `/healthz` ในคอนเทนเนอร์ | `status=ok` · `authConfigured=true` · **`dbConfigured=true`** · `routes` 5 รายการมี `level` · **`db` เป็น `"unknown"` ถือว่าปกติ** ดูข้อ 4.0 | ไม่ |
| **2.5** | **ตรวจการเชื่อมต่อ PostgreSQL จริง (ข้อ 4.0)** | **ต่อได้ · อ่าน `public.users` ได้ · 0 แถว** | ไม่ |
| 3 | `GET /api/sci-connect-news` | HTTP **200** | ไม่ |
| 4 | `GET /api/sci-connect-news-detail` | **ไม่ส่ง slug → 400** · **slug ที่ไม่มีจริง → 404** · **slug จริงจากข้อ 3 → 200** | ไม่ |
| 5 | `POST /api/admin/extract-file` **ไม่มี token** | HTTP **401** | ไม่ |
| 6 | `POST /api/admin/ingest` **ไม่มี token** | HTTP **401** | ไม่ — ด่านกัดก่อน handler |
| 7 | `POST /api/admin/extract-file` **พร้อม token ของ admin** | HTTP **200** | **ไม่** |
| 8 | `GET /api/chat` | ยังไปที่ FastAPI ตามเดิม | ไม่ |
| 9 | log ของ webapi | มีบรรทัดตั้งค่าฐานข้อมูล · **ไม่มีรหัสผ่าน** | ไม่ |
| 10 | จำนวน connection ของ `advisor_web` | **0 ถึง 5** — `0` ถือว่าปกติเมื่อยังไม่มีทราฟฟิกที่เขียนข้อมูล เพราะ pool ตั้ง `min: 0` ไว้โดยตั้งใจ ("ไม่จอง connection ไว้ตอนไม่มีทราฟฟิก") และ resolver ถูกเรียกเฉพาะตอนเขียนข้อมูล · **เกินกว่า 5 คือผิดปกติ** | ไม่ |

### 4.0 ตรวจการเชื่อมต่อ PostgreSQL จริง (ต้องทำ ห้ามข้าม)

#### ทำไมต้องมีขั้นนี้ — `/healthz` พิสูจน์การเชื่อมต่อไม่ได้

ตรวจโค้ดแล้วยืนยันว่า `/healthz` **ไม่ได้ทดสอบการเชื่อมต่อฐานข้อมูลเลย** เป็นการออกแบบที่ตั้งใจ ไม่ใช่ข้อบกพร่อง

| ค่าใน `/healthz` | ความหมายจริง | พิสูจน์อะไรได้ |
|---|---|---|
| `status: "ok"` | HTTP server ยังรับคำขอได้ | **ไม่เกี่ยวกับฐานข้อมูลเลย** — จงใจให้ไม่ขึ้นกับฐานข้อมูล เพราะ Docker HEALTHCHECK ตัดสินจากเส้นทางนี้ |
| `dbConfigured: true` | **มีค่า env ครบ** | พิสูจน์แค่ว่า "ตั้งค่าแล้ว" · **ไม่ได้แปลว่ารหัสผ่านถูก หรือต่อติด** |
| `db: "unknown"` | ยังไม่มีใครใช้ resolver เลยตั้งแต่คอนเทนเนอร์ขึ้น | **ค่านี้เป็นเรื่องปกติทันทีหลัง deploy ไม่ใช่ความผิดปกติ** |

เหตุผลที่โค้ดเลือกแบบนี้ระบุไว้ใน `db.mjs` — HEALTHCHECK มี timeout 5 วินาที ถ้า `/healthz` ไปรอฐานข้อมูลที่ค้างอยู่ คอนเทนเนอร์จะถูกตัดสินว่า unhealthy ทั้งที่เส้นทางสาธารณะสองเส้นทางยังทำงานได้และไม่ได้ใช้ฐานข้อมูลเลย

`db` จะเปลี่ยนเป็น `"up"` หรือ `"down"` **ก็ต่อเมื่อมีการเรียก resolver จริง** ซึ่งเกิดเฉพาะตอนเขียนข้อมูล (`authorFieldsFor` → `resolveAuthorId`)

> **ผลที่ตามมาถ้าไม่มีขั้นนี้:** deploy ด้วยรหัสผ่านผิดจะผ่าน smoke test ทุกข้อโดยไม่มีอะไรฟ้อง แล้วไปพังตอนผู้ดูแลกดบันทึกข้อมูลจริงครั้งแรก

#### คำสั่งตรวจ

รัน **ในคอนเทนเนอร์ webapi** เพื่อให้ใช้ค่า env ชุดเดียวกับของจริง

```bash
cd ~/course-advisor-system
docker compose -f docker-compose.prod.yml exec -T webapi node --input-type=module -e '
import { createDatabase, ACCOUNT_NOT_LINKED, IDENTITY_LOOKUP_FAILED } from "./db.mjs";
const db = createDatabase();
if (!db) { console.log("ผล: ไม่ได้ตั้งค่า (dbConfigured=false)"); process.exit(1); }
console.log("ปลายทาง:", db.describe());
const r = await db.resolver.resolveLocalUser("00000000-0000-0000-0000-000000000000");
console.log("เหตุผลที่ได้:", r.reason);
console.log("status หลังเรียก:", db.status());
if (r.reason === ACCOUNT_NOT_LINKED && db.status() === "up") console.log("สรุป: ต่อฐานข้อมูลได้ และอ่าน public.users ได้ -> ผ่าน");
else console.log("สรุป: ไม่ผ่าน");
await db.close();
'
```

#### ผลที่ต้องได้

```
ปลายทาง: advisor_web@postgres:5432/course_advisor
เหตุผลที่ได้: ACCOUNT_NOT_LINKED
status หลังเรียก: up
สรุป: ต่อฐานข้อมูลได้ และอ่าน public.users ได้ -> ผ่าน
```

| ผลที่ได้ | แปลว่า | ทำอะไรต่อ |
|---|---|---|
| `ACCOUNT_NOT_LINKED` + `status: up` | **ผ่าน** — ต่อติด รหัสผ่านถูก และมีสิทธิ์อ่าน `public.users` จริง (คืน 0 แถวเพราะ UUID ศูนย์ทั้งหมดไม่มีอยู่จริง) | ไปข้อ 4.1 ต่อ |
| `IDENTITY_LOOKUP_FAILED` + `status: down` | **ไม่ผ่าน** — ต่อไม่ได้ หรือรหัสผ่านผิด หรือไม่มีสิทธิ์ | ดู log แล้ว **rollback** |
| `ไม่ได้ตั้งค่า` | compose หรือ `.env` ไม่ครบ | **rollback** |

#### ทำไมคำสั่งนี้ปลอดภัย

| ข้อกังวล | คำตอบ |
|---|---|
| แสดงรหัสผ่านไหม | **ไม่** — `describe()` คืนแค่ `user@host:port/database` (`config.password` ถูกตั้งเป็น `undefined` ตั้งแต่ `createDatabase`) และไม่มีจุดใดพิมพ์ค่ารหัสผ่าน |
| เปลี่ยนรหัสผ่านไหม | **ไม่** — ไม่มี `ALTER ROLE` อ่านค่าจาก env ที่มีอยู่แล้วเท่านั้น |
| เขียนฐานข้อมูลไหม | **ไม่** — `RESOLVER_SQL` เป็น `SELECT id, is_active, supabase_user_id FROM public.users WHERE supabase_user_id = $1` ล้วน ๆ |
| ใช้ UUID ของคนจริงไหม | **ไม่** — ใช้ `00000000-0000-0000-0000-000000000000` ซึ่งไม่มีอยู่จริง จงใจให้คืน 0 แถว |
| หลงไปเจอ `trust` ของ `pg_hba` ไหม | **ไม่** — รันจากคอนเทนเนอร์ `webapi` ต่อผ่าน network ไปที่ host `postgres` **ไม่ใช่ `127.0.0.1`** จึงถูกบังคับให้ยืนยันรหัสผ่านจริง (กับดักจากรอบ provision) |


### 4.1 คำสั่ง

```bash
docker compose -f docker-compose.prod.yml ps webapi
docker compose -f docker-compose.prod.yml exec -T webapi node -e "fetch('http://127.0.0.1:3001/healthz').then(r=>r.text()).then(console.log)"
curl -s -o /dev/null -w 'news %{http_code}\n' https://stpnru-advisor.duckdns.org/api/sci-connect-news
curl -s -o /dev/null -w 'detail(ไม่ส่ง slug ต้องได้ 400) %{http_code}
' 'https://stpnru-advisor.duckdns.org/api/sci-connect-news-detail'
curl -s -o /dev/null -w 'detail(slug ไม่มีจริง ต้องได้ 404) %{http_code}
' 'https://stpnru-advisor.duckdns.org/api/sci-connect-news-detail?slug=ไม่มีสลักนี้จริง'
# slug จริง: ดึงจากรายการข่าวก่อน แล้วค่อยยิง detail — ต้องได้ 200
SLUG=$(curl -s https://stpnru-advisor.duckdns.org/api/sci-connect-news | sed -n 's/.*"slug":"\([^"]*\)".*//p' | head -1)
echo "slug ที่ได้: ${SLUG:-(ไม่มีข่าวในระบบ)}"
[ -n "$SLUG" ] && curl -s -o /dev/null -w 'detail(slug จริง ต้องได้ 200) %{http_code}
' "https://stpnru-advisor.duckdns.org/api/sci-connect-news-detail?slug=$SLUG"
curl -s -o /dev/null -w 'extract-file(no token) %{http_code}\n' -X POST https://stpnru-advisor.duckdns.org/api/admin/extract-file
curl -s -o /dev/null -w 'ingest(no token) %{http_code}\n' -X POST https://stpnru-advisor.duckdns.org/api/admin/ingest
docker compose -f docker-compose.prod.yml logs --tail=30 webapi
docker exec -i course-advisor-system-postgres-1 psql -U postgres -d course_advisor -At -c "select count(*) from pg_stat_activity where usename='advisor_web'"
```

**ข้อ 7 — ข้อสำคัญที่สุด**

```bash
read -rsp 'ACCESS_TOKEN: ' TK && echo
printf 'ทดสอบ smoke test M3\n' > /tmp/smoke.txt
curl -s -o /dev/null -w 'extract-file(admin) %{http_code}\n' -H "Authorization: Bearer $TK" -F 'file=@/tmp/smoke.txt' https://stpnru-advisor.duckdns.org/api/admin/extract-file
unset TK; rm -f /tmp/smoke.txt
```

ต้องได้ **200** ถ้าได้ 401 หรือ 403 แปลว่าด่านใหม่ล็อกผู้ดูแลออก → rollback ทันที

### 4.2 ทำไมข้อ 7 ปลอดภัย

ตรวจ `api/admin/extract-file.js` ทั้งไฟล์แล้ว — รับไฟล์จาก form, แปลงเป็นข้อความในหน่วยความจำ, คืนผล **ไม่มี `fetch` ไม่มี `.from(` ไม่มี storage ไม่มีการเขียนไฟล์** และ `_lib/fileExtract.js` ก็ไม่มี side effect ภายนอกเลย

เป็น endpoint ระดับ `EDITOR` **เพียงเส้นทางเดียวจากสามเส้นทาง** ที่ไม่เขียนข้อมูล จึงใช้ทดสอบเส้นทางอนุญาตได้โดยไม่เสี่ยง

### 4.3 ห้ามเรียกเด็ดขาดใน smoke test

| เส้นทาง | เหตุผล |
|---|---|
| `POST /api/admin/ingest` **พร้อม token** | `.delete()` + `.upsert()` + `.delete()` บน `rag_documents` ของจริง |
| `POST /api/admin/sync-sci-news` **พร้อม token** | สั่ง Supabase Edge Function ไปดึงข่าวและเขียน `external_news` ของจริง |

ทดสอบได้เฉพาะแบบ **ไม่มี token** (ข้อ 6) เพื่อดูว่าด่านปฏิเสธ — ถ้าได้ 401 แปลว่า handler ไม่เคยถูกเรียก จึงไม่มีการเขียนเกิดขึ้น

---

## 5. Rollback

### 5.1 ย้อนเร็ว

```bash
cd ~/course-advisor-system
EXPECT=$(docker image inspect course-advisor-system-webapi:rollback-pre-m3 --format '{{.Id}}')
docker tag course-advisor-system-webapi:rollback-pre-m3 course-advisor-system-webapi:latest
cp ~/m3-backup-compose-<TS>.yml docker-compose.prod.yml
docker compose -f docker-compose.prod.yml up -d --no-deps --force-recreate webapi
docker compose -f docker-compose.prod.yml ps webapi
```

> **ต้องคืน compose เดิมด้วย ไม่ใช่แค่ image** เพราะ compose ของใหม่บังคับว่าต้องมี `ADVISOR_WEB_PASSWORD` และตั้ง `depends_on` ที่ของเก่าไม่มี

**ยืนยัน image ID หลังย้อนกลับ — บังคับ**

```bash
ACTUAL=$(docker inspect course-advisor-system-webapi-1 --format '{{.Image}}')
echo "คาดหวัง: $EXPECT"
echo "ได้จริง : $ACTUAL"
[ "$EXPECT" = "$ACTUAL" ] && echo "ย้อนกลับสำเร็จ — คอนเทนเนอร์ใช้ image เดิมแล้ว" || echo "!! ยังไม่ใช่ image เดิม อย่าเพิ่งวางมือ"
```

| ทำไมต้อง `--force-recreate` | เหตุผล |
|---|---|
| `docker tag` เปลี่ยนแค่ชื่อ | คอนเทนเนอร์ที่รันอยู่ยังผูกกับ **image ID เดิมของรอบ M3** ไม่ได้เปลี่ยนตามชื่อ |
| compose อาจมองว่า "ไม่มีอะไรเปลี่ยน" | ถ้า compose ไฟล์และ config hash เหมือนเดิม `up -d` เฉย ๆ **อาจไม่ทำอะไรเลย** แล้วเข้าใจผิดว่าย้อนสำเร็จ |
| `--no-deps` ยังต้องมี | ไม่ให้ไป restart `postgres` ที่ backend ใช้อยู่ |

### 5.2 ตรวจหลัง rollback

```bash
curl -s -o /dev/null -w 'news %{http_code}\n' https://stpnru-advisor.duckdns.org/api/sci-connect-news
docker compose -f docker-compose.prod.yml logs --tail=20 webapi
```

ต้องได้ **200** กลับมาเหมือนเดิม

### 5.3 สิ่งที่ไม่ต้องย้อน

| รายการ | เหตุผล |
|---|---|
| ฐานข้อมูล | **deploy รอบนี้ไม่เขียนฐานข้อมูลเลย** ไม่มีอะไรให้ย้อน |
| Supabase | ไม่ได้แตะ |
| `webapi/api/` | ไม่ได้แตะ เพราะคัดลอกทีละไฟล์ ไม่ได้ลบอะไร |
| `ADVISOR_WEB_PASSWORD` ใน `.env` | ทิ้งไว้ได้ ไม่มีผลเมื่อ compose เป็นของเก่า |

### 5.4 ถ้า `webapi/api/` หายไปจริง ๆ

```bash
cd ~/course-advisor-system/webapi
tar -xzf ~/m3-backup-webapi-api-<TS>.tar.gz
find api -type f | wc -l
```

ต้องได้ **10** · หรือใช้ไฟล์สำรองที่เก็บนอกเครื่อง ขั้นตอนอยู่ใน `webapi/README.md`

---

## 6. ลำดับทั้งหมดโดยย่อ

```
1. สำรอง (db + compose + .env + api/)        ข้อ 3.1
2. เพิ่ม ADVISOR_WEB_PASSWORD ลง .env        ข้อ 3.2   <- ต้องก่อน up เสมอ
3. ส่งไฟล์ขึ้น (git archive + cp ทีละไฟล์)    ข้อ 3.3
4. ยืนยัน api/ = 10 และขนาดไฟล์ถูกต้อง        ข้อ 3.4
5. docker compose build webapi               ข้อ 3.5
6. ยืนยันของใน image ก่อน up                 ข้อ 3.6   <- กับดักที่ Dockerfile เตือนเอง
7. docker compose up -d --no-deps webapi     ข้อ 3.7
8. Smoke test 10 ข้อ                          ข้อ 4
9. เฝ้าดู log 10 นาที
```

**หยุดได้โดยไม่กระทบอะไรเลย:** ขั้นที่ 1–6 ทั้งหมด เพราะของเดิมยังทำงานอยู่
**เริ่มกระทบผู้ใช้:** ขั้นที่ 7 เป็นต้นไป

---

## 7. สิ่งที่ยังค้างหลัง deploy

| # | งาน | ระดับ |
|---|---|---|
| 1 | เปลี่ยน UUID ใน `webapi/auth.test.mjs:480` เป็นค่าสังเคราะห์ | ภายหลัง |
| 2 | เขียน `docs/DEPLOY_WEB.md` หรือลบการอ้างอิงใน `docker-compose.prod.yml:169` | ภายหลัง |
| 3 | เพิ่ม `.dockerignore` — `node_modules/` ถูกส่งเข้า build context ทั้งก้อน | ภายหลัง |
| 4 | ถอด `requireAdminUser` ออกจาก handler เมื่อมั่นใจด่านกลาง (ตอนนี้ `/api/admin/*` เรียก Supabase สองรอบต่อคำขอ) | ภายหลัง |
| 5 | **แก้ R1** — `user_profiles` ของ Supabase อ่านได้โดยทุกคนขณะที่เก็บ `email` + `full_name` · M3 ไม่ได้แก้ข้อนี้ | **ควรขออนุมัติแยก** |
| 6 | พิจารณาย้าย Docker disk image ไป D: บนเครื่องพัฒนา | ภายหลัง |

---

## 8. ยืนยันขอบเขตของเอกสารนี้

| ข้อห้าม | สถานะ |
|---|---|
| Deploy หรือ Restart production | **ไม่ได้ทำ** |
| แก้ production `.env` | **ไม่ได้ทำ** — อ่านเฉพาะชื่อคีย์ |
| เขียน production database / Supabase | **ไม่ได้ทำ** — ใช้ `SELECT` อย่างเดียว |
| Push / Merge | **ไม่ได้ทำ** |
| แก้ frontend repository | **ไม่ได้ทำ** |
| แสดง password / token / UUID / ข้อมูลส่วนบุคคล | **ไม่มีในเอกสารนี้** |

**สถานะ: รออนุมัติ deploy แยกต่างหาก**
