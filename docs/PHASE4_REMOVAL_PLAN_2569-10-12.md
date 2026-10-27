# Phase 4 — แผนถอด cron เก่า / webapi / Caddy routes / env

| รายการ | ค่า |
|---|---|
| วันที่เตรียมแผน | **12 ตุลาคม 2569 · เวลาไทย 08:00 (01:00 UTC)** |
| แก้ไขครั้งที่ 2 | 12 ตุลาคม 2569 เวลาไทย 08:00 — แก้ 7 ข้อตามที่สั่ง |
| เขตเวลาของเซิร์ฟเวอร์ | `Etc/UTC` — ทุกเวลาในแผนนี้เขียนเป็นเวลาไทยพร้อม UTC ในวงเล็บ |
| สถานะ | **เตรียมไว้เท่านั้น — ยังไม่ได้ลงมือขั้นใดทั้งสิ้น** |
| **ยังไม่ทำ** | **ไม่ปิด cron · ไม่หยุด webapi · ไม่เปลี่ยน Caddy · ไม่ลบ env · ไม่ลบโปรเจกต์ Supabase** |

---

## 0. สิ่งที่แก้จากฉบับแรก

| # | ที่แก้ | ฉบับแรกผิดอย่างไร |
|---|---|---|
| 1 | ชุดไฟล์ compose | ใช้ `-f docker-compose.yml -f docker-compose.prod.yml` ซึ่ง **ไม่ใช่ชุดที่ production ใช้** และพิสูจน์แล้วว่าทำให้ **postgres ถูกสร้างใหม่** |
| 2 | webapi ต่อกับอะไร | เขียนว่า "ไม่ได้ต่อ Supabase แล้ว" — **ผิด** อ่านโค้ดจริงแล้วพบว่าต่อ Supabase ทุกเส้นทาง |
| 3 | ขั้นเปิด access log | เสนอ bind mount ซึ่งต้อง **recreate caddy** เปลี่ยนมาใช้ stdout ที่ reload พอ และเพิ่มการกรองค่าลับ |
| 4 | ขั้นถอด webapi | สั่ง `up -d` ทั้งชุด · ไม่ได้ตรวจ `depends_on` ซึ่ง **caddy depends_on webapi** อยู่ |
| 5 | ผลการสำรอง | เรียก 47/52 ว่า "กู้ได้" ลอย ๆ · ไม่ได้ระบุว่า **ไม่มี GRANT และไม่มี role** ในไฟล์สำรอง |
| 6 | Edge Functions | บอกว่า "ต้องทำเอง" แต่ไม่ได้เตรียมเครื่องมือให้ · ตอนนี้เตรียมแล้วและทดสอบแล้ว |
| 7 | วันเวลา | ปน UTC กับเวลาไทยจนวันไม่ตรงกันระหว่างเอกสาร |

---

## 1. คำสั่ง compose ที่ถูกต้อง — ใช้ชุดนี้ทุกคำสั่งและทุกการย้อนกลับ

ชุดที่ production ใช้จริง อ่านจาก label ของคอนเทนเนอร์ที่กำลังรัน
(`com.docker.compose.project.config_files` ของ `backend`, `webapi`, `frontend`)

```bash
CF="-f /home/ubuntu/course-advisor-system/docker-compose.prod.yml \
-f /home/ubuntu/course-advisor-system/docker-compose.staging.yml \
-f /home/ubuntu/release-2fdc6f2/compose.pin-backend-2fdc6f2.yml \
-f /home/ubuntu/release-2fdc6f2/compose.pin-frontend-2fdc6f2.yml"
```

ทุกคำสั่งในแผนนี้ขึ้นต้นด้วย `docker compose -p course-advisor-system $CF …`

### หลักฐานว่าชุดนี้ถูก และชุดอื่นผิด

ทดสอบด้วย `up -d --no-build --dry-run` ซึ่งอ่านอย่างเดียว ไม่เปลี่ยนอะไร

| ชุดที่ใช้ | ผลที่ `--dry-run` บอก |
|---|---|
| **4 ไฟล์ตาม label** | `frontend` `webapi` `caddy` `postgres` `ollama` `backend` → **Running ทุกตัว** (ไม่มีอะไรเปลี่ยน) |
| `docker-compose.yml` + `prod.yml` | **`postgres` Recreated · `ollama` Recreated · `backend` Recreated · `frontend` Recreated** |

> **`docker-compose.yml` ห้ามใส่ในคำสั่งใด ๆ** — ไฟล์นั้นนิยาม `postgres` และ `ollama` ไว้ต่างจาก
> `docker-compose.prod.yml` การใส่เข้าไปทำให้ compose เห็น config ต่างจากที่คอนเทนเนอร์ถูกสร้างมา
> แล้วสั่งสร้างฐานข้อมูลใหม่ ซึ่งคือการหยุดบริการทั้งระบบโดยไม่ได้ตั้งใจ
>
> `deploy.sh` เดิมใช้ `-f docker-compose.prod.yml` อย่างเดียวกับ `--no-deps backend` ซึ่งใช้ได้
> เฉพาะกับ `backend` ตัวเดียว **ไม่ใช่ชุดอ้างอิงของทั้งระบบ** label ของคอนเทนเนอร์คือหลักฐานที่ถูก

### ตรวจชุด config ได้โดยไม่เปิดเผยค่าลับ

```bash
docker compose -p course-advisor-system $CF config --no-interpolate | grep -nE 'SUPABASE|PASSWORD|KEY'
```

`--no-interpolate` ไม่คลี่ค่าจาก `.env` ผลที่ได้เป็นชื่อตัวแปร เช่น `${VITE_SUPABASE_ANON_KEY}`
**ห้ามใช้ `docker compose config` เปล่า ๆ** เพราะจะพิมพ์รหัสผ่านฐานข้อมูลและคีย์ทุกตัวออกจอ

---

## 2. webapi ต่อกับอะไร — ตรวจจากโค้ดที่รันอยู่จริง

ฉบับแรกสรุปจาก startup log บรรทัดเดียว (`advisor_web@postgres:5432`) แล้วเขียนว่าไม่ได้ต่อ Supabase
**นั่นพิสูจน์แค่ว่ามีการต่อฐานข้อมูลหนึ่งเส้นทาง ไม่ได้พิสูจน์ว่าทุกเส้นทางต่อที่นั่น**

อ่านไฟล์ `.mjs`/`.js` ทั้ง 13 ไฟล์ในคอนเทนเนอร์ `course-advisor-system-webapi-1` แล้วได้ผลดังนี้

### ต่อ PostgreSQL ของเรา — ที่เดียว ที่ `db.mjs`

| ไฟล์ | ใช้ทำอะไร |
|---|---|
| `db.mjs` | ต่อด้วย role `advisor_web` เพื่อแปลง `public.users.supabase_user_id` → `public.users.id` สำหรับคอลัมน์ `created_by` / `updated_by` เท่านั้น |

### ต่อ Supabase ผ่านเครือข่าย — ทุกเส้นทางที่ให้บริการ

| ไฟล์ | บรรทัด | ทำอะไรกับ Supabase |
|---|---|---|
| `api/_lib/adminAuth.js` | 29–39 | `createClient(url, anonKey)` → **`supabase.auth.getUser(token)`** แล้วอ่าน `user_profiles` |
| `api/sci-connect-news.js` | 5–29 | อ่านตาราง **`external_news` จาก Supabase** |
| `api/sci-connect-news-detail.js` | 9–30 | อ่าน **`external_news` จาก Supabase** |
| `api/_lib/rag.js` | 16–39 | เรียก RPC **`match_rag_documents` บน Supabase** |
| `api/_lib/ingest.js` | 35–62 | **`delete` และ `upsert` ตาราง `rag_documents` บน Supabase** |
| `api/_lib/aiConfig.js` | 18–24 | อ่าน **`ai_settings` จาก Supabase** |
| `api/admin/sync-sci-news.js` | 28 | เรียก **Edge Function `${url}/functions/v1/sync-sci-news`** |
| `auth.mjs` | 276–290 | `supabaseEnv()` + `createSupabaseVerifier()` → ตัวตรวจ token ที่คุยกับ Supabase |
| `server.mjs` | 91–95 | ถ้าไม่มีค่าตั้งค่า Supabase **เส้นทางที่ต้องมีสิทธิ์จะตอบ 500 ทุกครั้ง** |

### ข้อสรุปที่ถูกต้อง

**webapi คือองค์ประกอบสุดท้ายใน production ที่ยังเรียก Supabase ผ่านเครือข่ายจริง**

ผลที่ตามมาสองข้อที่ต้องรู้:

1. `https://stpnru-advisor.duckdns.org/api/sci-connect-news` **เปิดอยู่ต่อสาธารณะและตอบ 200 ด้วยข้อมูลจาก Supabase**
   ไม่ใช่ข้อมูลจากฐานของเรา — ใครยิงเข้ามาก็ยังทำให้เกิดการเรียก Supabase ได้
2. คำกล่าวในรายงานตรวจรับที่ว่า "เบราว์เซอร์ไม่มีคำขอไป supabase 0/88" **ถูกต้องแต่ครอบคลุมแค่ฝั่งเบราว์เซอร์**
   การเรียกจาก webapi เป็นการเรียกฝั่งเซิร์ฟเวอร์ ซึ่งไม่ปรากฏใน Network ของเบราว์เซอร์

การถอด webapi จึงไม่ใช่แค่ "ลบของซ้ำซ้อน" แต่เป็น **การตัดสายพึ่งพา Supabase เส้นสุดท้าย**

### ของที่มาแทนครบทั้ง 5 เส้นทาง

| เส้นทาง webapi | ของที่มาแทน (backend) | bundle ที่ deploy เรียกตัวไหน |
|---|---|---|
| `/api/sci-connect-news` | `/api/site/external-news` | **ตัวใหม่** |
| `/api/sci-connect-news-detail` | `/api/site/external-news/{slug}` | **ตัวใหม่** |
| `/api/admin/sync-sci-news` | `/api/site-admin/sync-news` | **ตัวใหม่** |
| `/api/admin/ingest` | `/api/site-admin/knowledge` (POST) | **ตัวใหม่** |
| `/api/admin/extract-file` | `/api/extract-file` (POST) | **ตัวใหม่** |

ค้นในไฟล์ที่ Caddy เสิร์ฟจริง (`/srv/web` 19 ไฟล์): `/api/admin` **0 ไฟล์** · `/api/sci-connect` **0 ไฟล์** · `supabase` **0 ไฟล์**
และพบ `/api/extract-file` `/api/uploads/` `/api/site-admin/knowledge` `/api/site-admin/sync-news` `/api/site/external-news` ครบทั้ง 5

---

## 3. สิ่งที่จะถอด — สถานะปัจจุบัน

### 3.1 cron เก่าที่ Supabase

| jobid | ชื่อ | ตาราง | active |
|---|---|---|---|
| 1 | `sync-sci-news-every-30-min` | ทุก 30 นาที | **false** — ปิดอยู่แล้ว |
| 2 | `sync-sci-news-every-30-min-v2` | ทุก 30 นาที | **true** — ตัวที่ยังทำงาน |

คำสั่งเรียก `net.http_post` ไป `/functions/v1/sync-sci-news` และอ่านคีย์จาก `vault` (ไม่ฝัง JWT ตรง ๆ)

### 3.2 cron ของเรา

`*/30 * * * * /bin/bash /home/ubuntu/phase4-sync-news.sh` — ผ่านการตรวจ 3 รอบติดตามเวลาจริง

### 3.3 Caddy routes

`/home/ubuntu/course-advisor-system/Caddyfile` บรรทัด **25–39** สองบล็อกที่ `reverse_proxy webapi:3001`

### 3.4 env

| ตัวแปร | อยู่ที่ | ใครใช้ |
|---|---|---|
| `VITE_SUPABASE_URL` | `.env` + `docker-compose.prod.yml:191–192` | **`webapi` เท่านั้น** |
| `VITE_SUPABASE_ANON_KEY` | เหมือนกัน | **`webapi` เท่านั้น** |

ตรวจด้วย `config --no-interpolate` แล้ว ไม่มีบริการอื่นอ้างถึง · `backend` ไม่มีตัวแปรที่ขึ้นต้นด้วย `SUPABASE` เลย

### 3.5 **`depends_on` ที่ต้องแก้พร้อมกัน**

`docker-compose.prod.yml` บรรทัด 168–173

```yaml
  caddy:
    image: caddy:2-alpine
    depends_on:
      - frontend
      - webapi        # ← บรรทัด 173 ต้องลบพร้อมกับการลบบริการ webapi
```

> ถ้าลบบริการ `webapi` แต่ไม่ลบบรรทัดนี้ `docker compose config` จะไม่ผ่านเลย
> และคำสั่งใดที่แตะ `caddy` จะล้มทั้งคำสั่ง — ต้องแก้สองที่ในการเปลี่ยนครั้งเดียว

### 3.6 สิ่งที่ไม่อยู่ในแผนนี้

`frontend` (Next.js พอร์ต 3000 · Caddy ไม่ได้เสิร์ฟจากตัวนี้) · `postgres` · `ollama` · `backend` · `caddy` — **ไม่แตะ**

---

## ขั้น G0.8 — เปิด access log ของ Caddy (ทำก่อนทุกขั้น)

### ทำไมต้องมีขั้นนี้

| สิ่งที่ตรวจ | ผล |
|---|---|
| `Caddyfile` มี directive `log` | **0 บรรทัด** → Caddy ไม่ได้เขียน access log เลย |
| `webapi` เขียน log ต่อคำขอ | **ไม่เขียน** — ยิงเข้าไป 1 ครั้งได้ 200 แต่ log เพิ่ม 0 บรรทัด |

ตัวเลข "0 ครั้ง" ที่ได้จากแหล่งที่ไม่มีการบันทึก **ไม่ต่างจากไม่ได้ตรวจ**

### เลือกวิธีที่กระทบน้อยที่สุด

| ทางเลือก | ต้องทำอะไร | ผลกระทบ |
|---|---|---|
| bind mount ไฟล์ log | แก้ `docker-compose.prod.yml` เพิ่ม volume | **ต้อง recreate คอนเทนเนอร์ caddy** → เว็บสะดุด 1–3 วินาที และใบรับรองต้องโหลดใหม่ |
| **`output stdout`** | แก้ `Caddyfile` ไฟล์เดียว | **`caddy reload` พอ ไม่ต้อง recreate** · ไม่มีคำขอใดหลุด |

**เลือก `output stdout`** · log ไปอยู่ใน `docker logs course-advisor-system-caddy-1` ซึ่ง grep ได้ตามปกติ

### บล็อกที่จะเพิ่ม — ทดสอบแล้วว่าไม่บันทึกค่าลับ

เพิ่มไว้ **ในบล็อกของโดเมน ก่อน `handle` แรก**

```
	log {
		output stdout
		format filter {
			wrap json
			fields {
				request>headers delete
				resp_headers delete
				request>uri query {
					delete token
					delete access_token
					delete refresh_token
				}
			}
		}
	}
```

### ทดสอบไว้แล้วในคอนเทนเนอร์ caddy ชั่วคราว (`--network none` ไม่เปิดพอร์ต ไม่แตะ production)

| ข้อตรวจ | ผลที่ได้ |
|---|---|
| `caddy validate` | **Valid configuration** · exit 0 |
| ยิงคำขอที่มี `Authorization: Bearer SENTINEL_AUTH_VALUE` | **พบในบันทึก 0 ครั้ง** |
| ยิงคำขอที่มี `Cookie: session=SENTINEL_COOKIE_VALUE` | **พบในบันทึก 0 ครั้ง** |
| ยิง `/admin/reset-password?token=SENTINEL_QUERY_TOKEN&slug=ok` | **พบในบันทึก 0 ครั้ง** |
| บรรทัดที่บันทึกได้จริง | `"uri":"/admin/reset-password?slug=ok"` — **`token` ถูกตัด `slug` ยังอยู่** |

> ทำไมต้องกรอง `token` ใน query: หน้าตั้งรหัสใหม่ที่เราเพิ่มในเฟสนี้รับ token จาก URL
> (`/admin/reset-password?token=…`) ถ้าไม่กรอง token ที่ใช้ตั้งรหัสใหม่จะถูกบันทึกลง log ทั้งค่า
> `request>headers delete` ตัด `Authorization` และ `Cookie` ทั้งก้อน ไม่ต้องพึ่งค่าตั้งต้น
> `log_credentials` ของ Caddy ว่าจะเปลี่ยนหรือไม่ในอนาคต

### คำสั่ง

```bash
ssh ubuntu@161.118.237.37 'cd /home/ubuntu/course-advisor-system && cp -a Caddyfile Caddyfile.bak-before-g0.8 && chmod 600 Caddyfile.bak-before-g0.8 && sha256sum Caddyfile Caddyfile.bak-before-g0.8'
```

แก้ `Caddyfile` เพิ่มบล็อก `log` แล้ว

```bash
ssh ubuntu@161.118.237.37 'docker compose -p course-advisor-system exec caddy caddy validate --config /etc/caddy/Caddyfile && docker compose -p course-advisor-system exec caddy caddy reload --config /etc/caddy/Caddyfile'
```

**ไฟล์ที่เปลี่ยนในขั้นนี้: `Caddyfile` ไฟล์เดียว** — สำรองไว้แล้วหนึ่งชุดชื่อ `.bak-before-g0.8`

### ข้อตรวจ

| # | ตรวจอะไร | ต้องได้ |
|---|---|---|
| 1 | `caddy validate` ก่อน reload | exit **0** |
| 2 | คอนเทนเนอร์ **ไม่ถูกสร้างใหม่** | `docker inspect -f '{{.Id}}'` ของ caddy **ตรงกับก่อน reload** · `.State.StartedAt` ไม่เปลี่ยน |
| 3 | หน้าเว็บเปิดได้ | `curl -o /dev/null -w '%{http_code}'` หน้าแรก = **200** |
| 4 | API ทำงาน | `/api/site/external-news` = **200** และ JSON มีข่าว |
| 5 | **log เขียนจริง** | เปิดหน้าเว็บ 1 ครั้ง แล้ว `docker logs --since 1m` **มีบรรทัด `handled request` เพิ่ม** |
| 6 | **log จับเส้นทางเป้าหมายได้** | ยิง `/api/sci-connect-news` เอง 1 ครั้ง ต้อง **เห็นบรรทัดนั้นใน log** |
| 7 | **ไม่บันทึกค่าลับ** | ยิงคำขอที่มี `Authorization` + `Cookie` + `?token=` ของตัวเอง แล้ว `grep` ค่าเหล่านั้นใน log ต้องได้ **0** |
| 8 | ปริมาณ log ไม่โตเกินรับได้ | นับบรรทัดใน 15 นาที แล้วคูณ 96 → ต้อง **ต่ำกว่า 50 MB/วัน** |

> ข้อ 5–7 คือหัวใจ — **ถ้าไม่เห็น log เพิ่มจากคำขอที่เรายิงเอง ห้ามไปขั้นต่อไป**
> ข้อ 8 จำเป็นเพราะ log driver ของ caddy เป็น `json-file` **ที่ไม่ได้ตั้ง `max-size`**
> จึงโตได้ไม่จำกัด (ตอนนี้ 292 KB · ดิสก์เหลือ 60 GB) ถ้าเกินเกณฑ์ให้ย้อนกลับแล้วเปลี่ยนไปใช้
> bind mount + `logrotate` แทน โดยยอมรับว่าต้อง recreate caddy หนึ่งครั้ง
> ระหว่างทางถ้าต้องการคืนที่ว่างทันที: `sudo truncate -s 0 $(docker inspect --format '{{.LogPath}}' course-advisor-system-caddy-1)`

### ย้อนกลับ

```bash
ssh ubuntu@161.118.237.37 'cd /home/ubuntu/course-advisor-system && cp -a Caddyfile.bak-before-g0.8 Caddyfile && docker compose -p course-advisor-system exec caddy caddy validate --config /etc/caddy/Caddyfile && docker compose -p course-advisor-system exec caddy caddy reload --config /etc/caddy/Caddyfile'
```

**ตรวจหลังย้อนกลับ:** `sha256sum Caddyfile` ตรงกับ `.bak-before-g0.8` · หน้าแรก 200 · `docker logs --since 1m` **ไม่มีบรรทัด `handled request` เพิ่ม**

---

## ขั้น G0.9 — เก็บสิ่งที่ยังขาดในไฟล์สำรอง (ทำตอนกรอก credentials รอบหน้า)

ไฟล์สำรองที่มีอยู่ **ไม่มี GRANT และไม่มี role** (ดูหัวข้อ 5) จึงต้องเก็บเพิ่มสองอย่าง
ทำพร้อมขั้น G1 เพราะต้องกรอก credentials ครั้งเดียวใช้ได้ทั้งสองขั้น

```bash
# 1) สิทธิ์ระดับตารางและ default privileges (ไม่ใส่ --no-privileges)
docker run --rm -e PGURL postgres:17 sh -c 'pg_dump "$PGURL" -Fc --no-owner' > supabase-with-acl-<วันที่>.dump

# 2) role และสิทธิ์ระดับคลัสเตอร์ (อาจถูกปฏิเสธผ่าน pooler — ถ้าไม่ได้ให้บันทึกตามจริง)
docker run --rm -e PGURL postgres:17 sh -c 'pg_dumpall -d "$PGURL" --globals-only --no-role-passwords' > supabase-globals-<วันที่>.sql
```

| ข้อตรวจ | ต้องได้ |
|---|---|
| ไฟล์ที่ 1 มี GRANT | `pg_restore -f - … | grep -c '^GRANT '` **มากกว่า 0** |
| ไฟล์ที่ 2 มี CREATE ROLE | `grep -c '^CREATE ROLE'` **มากกว่า 0** |
| ถ้าข้อใดทำไม่ได้ | **บันทึกตามจริงว่าทำไม่ได้** ห้ามข้ามเงียบ ๆ |

`--no-role-passwords` ใส่ไว้โดยตั้งใจ — ไม่ต้องการ hash รหัสผ่านระดับคลัสเตอร์ออกมาเพิ่ม

---

## ขั้น G0.10 — เก็บ Edge Functions และการตั้งค่า + สำรองนอกเซิร์ฟเวอร์

**เตรียมเครื่องมือไว้แล้วและทดสอบแล้ว** คุณเป็นคนรันเอง เพราะต้องกรอกค่าลับของบัญชีคุณ

### ก. เก็บโค้ด Edge Functions และการตั้งค่า

```bash
bash /home/ubuntu/phase4-capture-supabase-extras.sh
```

ต้องเตรียม **personal access token** จาก `https://supabase.com/dashboard/account/tokens` และ **project ref**

| คุณสมบัติของสคริปต์ | ตรวจแล้ว |
|---|---|
| กรอก token และ ref **แบบซ่อนค่า** ไม่ขึ้นจอ | ✓ |
| token **ไม่ส่งผ่าน argv** (ใช้ `curl -H @ไฟล์` โหมด 600 ที่ลบทันทีเมื่อจบ) | ✓ `-H "Authorization` ตรง ๆ = 0 ครั้ง |
| token **ไม่ถูกเขียนลงดิสก์ถาวร** | ✓ 0 ครั้ง |
| ปฏิเสธค่าผิดรูปแบบ **ก่อน** เรียก API | ✓ ทดสอบแล้ว ขึ้น "หยุด ไม่ได้เรียก API ใด" |
| `api.supabase.com` เข้าถึงได้จากเซิร์ฟเวอร์ | ✓ ตอบ HTTP 401 เมื่อไม่ส่ง token |
| แยกที่เก็บ: โค้ด (commit ได้) กับการตั้งค่า (ความลับ) | ✓ `edge-functions/` และ `settings/` |
| สแกนว่าโค้ดมีค่าลับฝังไว้ไหมก่อนบอกว่า commit ได้ | ✓ ค้น JWT / DSN / `sbp_` |
| ห้ามเขียนทับของเดิม | ✓ ออกถ้า `edge-functions/` ไม่ว่าง |

สิ่งที่สคริปต์ดึง: ข้อมูลโปรเจกต์ · รายการฟังก์ชันทั้งหมด · `meta.json` + `index.ts` ของทุกฟังก์ชัน ·
`config/auth` · `postgrest` · `storage/buckets` · `secrets` (ชื่อ Edge Function secrets) · `custom-hostname` · `network-restrictions`

| ข้อตรวจ | ต้องได้ |
|---|---|
| รายการฟังก์ชัน | HTTP **200** และ **มี `sync-sci-news` อยู่ในรายการ** |
| โค้ดของทุกฟังก์ชัน | HTTP 200 และไฟล์ **ใหญ่กว่า 10 ไบต์** ทุกตัว |
| จำนวนฟังก์ชันที่ได้ | **ตรงกับจำนวนในรายการ** — ถ้าขาด ต้องคัดลอกจาก dashboard เอง |
| การสแกนค่าลับ | ถ้า **0 ไฟล์** → นำ `edge-functions/` เข้า repo ที่ `supabase/functions/` ได้ |
| ถ้า endpoint ใดตอบ 4xx | **บันทึกตามจริง** แล้วเก็บค่านั้นจาก dashboard ด้วยมือ |

> `settings/` มีรหัส SMTP และคีย์ได้ · ทุกไฟล์โหมด 600 · **ห้าม commit โฟลเดอร์นี้**

### ข. สำรองอีกชุดนอกเซิร์ฟเวอร์ แบบเข้ารหัส

ตอนนี้ของสำรองมีอยู่ **ที่เดียว** ถ้าเซิร์ฟเวอร์เสียหายก็หายไปพร้อมกัน

```bash
bash /home/ubuntu/phase4-package-backup.sh
```

รวม `/home/ubuntu/supabase-g0` + `/home/ubuntu/supabase-storage-backup` (รวม ~12.6 MB)
เป็น `phase4-offsite-<เวลา>.tar.zst.gpg` พร้อม `MANIFEST.sha256` ข้างใน และไฟล์ `.sha256` ข้างนอก

| คุณสมบัติของสคริปต์ | ตรวจแล้ว |
|---|---|
| รหัสผ่านกรอกซ่อนค่า **สองครั้ง** · สั้นกว่า 12 ตัวอักษรไม่รับ | ✓ |
| ไม่ส่งรหัสผ่านผ่าน argv และ **ไม่เขียนลงไฟล์ชั่วคราว** (ใช้ pipe ทาง fd 3) | ✓ `--passphrase` ตรง ๆ = 0 ครั้ง |
| เข้ารหัส AES256 + SHA512 | ✓ |
| **ตรวจผลด้วยการถอดรหัสและอ่านสารบัญกลับ** ไม่ใช่แค่ดูว่าไฟล์ถูกสร้าง | ✓ ทดสอบด้วยข้อมูลจำลองแล้ว ได้ 4 รายการ |
| รหัสผิดต้องถอดไม่ได้ | ✓ ได้ 0 ไบต์ |
| ห้ามเขียนทับของเดิม | ✓ ออกถ้ามีไฟล์ชื่อเดียวกัน |

**ที่เก็บปลายทางต้องคุมสิทธิ์ได้** — เครื่องของคุณเองที่ตั้งรหัสเข้าเครื่อง หรือที่เก็บที่คุณเป็นคนเดียวที่เข้าถึงได้
**ห้ามใส่ใน repo · ห้ามอัปโหลดขึ้นที่แชร์ลิงก์ได้** เพราะข้างในมี hash รหัสผ่านของผู้ใช้ 3 บัญชี

ทำข้อ ก. ก่อน แล้วรันข้อ ข. เพื่อให้ก้อนที่เข้ารหัสมีโค้ด Edge Function รวมอยู่ด้วย

---

## ขั้น G1 — ปิด cron เก่าที่ Supabase

### เงื่อนไขก่อนทำ

| # | ต้องเป็นจริง | ตรวจอย่างไร |
|---|---|---|
| 1 | G0.8 ผ่านครบ 8 ข้อ | เห็น log เพิ่มจากคำขอที่ยิงเอง และไม่มีค่าลับใน log |
| 2 | G0.9 และ G0.10 ทำแล้ว | มีไฟล์ ACL/globals และมีโค้ด Edge Function ครบ |
| 3 | cron ของเรารัน 3 รอบติด exit 0 | `/home/ubuntu/phase4-sync-news.log` |
| 4 | ข่าวในฐานเราตรงกับต้นทาง | เทียบ slug + `synced_at` ตัวล่าสุด |

### คำสั่ง

```sql
select cron.alter_job(2, active := false);
```

ส่ง DSN ผ่าน env ไม่ผ่าน argv · ใช้ `psql -f -` รับ SQL ทาง stdin · ลบ credentials ด้วย
`phase4-clear-credentials.sh` ทันทีเมื่อจบ (รอบที่แล้วไฟล์ค้างอยู่ จึงต้องตรวจซ้ำทุกครั้ง)

### ข้อตรวจ

| # | ตรวจอะไร | ต้องได้ |
|---|---|---|
| 1 | สถานะ job | `select jobid, active from cron.job` → jobid 2 = **false** |
| 2 | **หยุดรันจริง** | `count(*)` ของ `cron.job_run_details` **ไม่เพิ่ม** หลังผ่านไป 35 นาที |
| 3 | ข่าวฝั่งเรายังอัปเดต | `synced_at` ล่าสุด **ใหม่กว่า** เวลาที่ปิด cron เก่า |
| 4 | หน้าเว็บยังแสดงข่าว | `/api/site/external-news` = 200 · จำนวนข่าว > 0 |
| 5 | ไฟล์ credentials ถูกลบ | `ls /home/ubuntu/.phase4-supabase` → **ไม่มีไฟล์** |

> ข้อ 2 คือหัวใจ — **`alter_job` สำเร็จไม่ได้แปลว่ามันหยุด** ต้องรอถึงรอบถัดไปแล้วดูว่าไม่มีแถวใหม่
> ข้อ 3 กันกรณีปิดของเก่าแล้วของใหม่ก็ไม่ทำงาน ทำให้ข่าวค้างโดยไม่มีใครรู้

### ย้อนกลับ

```sql
select cron.alter_job(2, active := true);
```

**ตรวจหลังย้อนกลับ:** `active = true` และหลังผ่านไป 35 นาที `cron.job_run_details` **มีแถวใหม่**

---

## ขั้น G2 — เฝ้าดู 72 ชั่วโมง

ไม่มีคำสั่งเปลี่ยนอะไร · **ห้ามข้าม** เพราะเป็นขั้นเดียวที่เก็บหลักฐานว่าไม่มีใครเรียกของเก่า

| # | ตรวจอะไร | ต้องได้ |
|---|---|---|
| 1 | คำขอไป `/api/sci-connect-news*` ใน access log | **0** |
| 2 | คำขอไป `/api/admin/*` ใน access log | **0** |
| 3 | คำขอไป `/api/site/external-news` | **มากกว่า 0** |
| 4 | cron ของเรารันครบ | **≥ 140 รอบ** ใน 72 ชม. · exit 0 ทุกรอบ |
| 5 | ข่าวยังตรงกับต้นทาง | เทียบ slug ล่าสุดกับหน้า Sci Connect จริง |
| 6 | ขนาด log | ยังต่ำกว่าเกณฑ์ที่วัดไว้ใน G0.8 ข้อ 8 |

> ข้อ 3 คือข้อกันหลอกตัวเอง: ถ้าข้อ 1–2 ได้ 0 แต่ข้อ 3 ก็ได้ 0 ด้วย แปลว่า **log ใช้ไม่ได้** ไม่ใช่ว่าไม่มีคนเรียก
> ถ้าข้อ 1 หรือ 2 ไม่ใช่ 0 ให้หยุด หาว่าใครเรียก ก่อนตัดสินใจอะไรต่อ

---

## ขั้น G3 — หยุด webapi (ยังไม่ลบ)

### คำสั่ง

```bash
ssh ubuntu@161.118.237.37 'cd /home/ubuntu/course-advisor-system && CF="-f /home/ubuntu/course-advisor-system/docker-compose.prod.yml -f /home/ubuntu/course-advisor-system/docker-compose.staging.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-backend-2fdc6f2.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-frontend-2fdc6f2.yml" && docker compose -p course-advisor-system $CF stop webapi'
```

`stop` เท่านั้น — ไม่ใช่ `down` ไม่ใช่ `rm` · คอนเทนเนอร์และ image ยังอยู่ กลับมาได้ในวินาที

### ข้อตรวจ

| # | ตรวจอะไร | ต้องได้ |
|---|---|---|
| 1 | webapi หยุด | `compose ps` → `webapi` **Exited** |
| 2 | **บริการอื่นไม่ถูกแตะ** | container id ของ `backend` `caddy` `postgres` `ollama` `frontend` **เท่าเดิมทุกตัว** |
| 3 | หน้าเว็บทุกหน้าใช้งานได้ | เปิดจริง: หน้าแรก · Sci Connect · รายการข่าวทั้งหมด · รายละเอียดข่าว · `/careers` |
| 4 | เส้นทางที่ frontend ใช้ | `/api/site/external-news` · `/api/site/external-news/{slug}` · `/api/site/courses` = **200** |
| 5 | **อัปโหลดคลังความรู้ยังทำงาน** | เข้าระบบผู้ดูแล อัปโหลด PDF ทดสอบ 1 ไฟล์ **สำเร็จ** แล้วลบทิ้ง |
| 6 | ซิงก์ข่าวจากหน้าผู้ดูแล | กดปุ่ม → `/api/site-admin/sync-news` = **200** |
| 7 | ถามคำถามในหน้าเว็บ | `/api/chat` ตอบคำถามจริงได้ |
| 8 | เส้นทางเก่าตอบอย่างไร | `/api/sci-connect-news` = **502** (ต้องเกิด เพราะ route ยังชี้ไป webapi ที่หยุดแล้ว) |

> ข้อ 5 ต้องทำมือจริง ไม่ดูจาก log — เพราะ `/api/admin/extract-file` และ `/api/admin/ingest` เคยเป็นของ webapi
> ข้อ 8 ไม่ใช่ความผิดพลาด เป็นผลที่ต้องเกิด และจะหายไปในขั้น G4

### ย้อนกลับ

```bash
ssh ubuntu@161.118.237.37 'cd /home/ubuntu/course-advisor-system && CF="…ชุด 4 ไฟล์…" && docker compose -p course-advisor-system $CF start webapi'
```

**ตรวจหลังย้อนกลับ:** `webapi` **Up (healthy)** · `/api/sci-connect-news` = **200**

---

## ขั้น G4 — ลบ Caddy routes ของ webapi

ทำหลัง G3 ผ่านครบ และเว้นอย่างน้อย 24 ชม.

### คำสั่ง

```bash
ssh ubuntu@161.118.237.37 'cd /home/ubuntu/course-advisor-system && cp -a Caddyfile Caddyfile.bak-before-g4 && chmod 600 Caddyfile.bak-before-g4 && sha256sum Caddyfile.bak-before-g4'
```

ลบบรรทัด 25–39 (คอมเมนต์ + สองบล็อก `handle`) · **เก็บคอมเมนต์บรรทัด 30–32** ย้ายไปไว้เหนือ `handle /api/*`
**เก็บบล็อก `log` ที่เพิ่มใน G0.8 ไว้** จนจบ G5

### ข้อตรวจ

| # | ตรวจอะไร | ต้องได้ |
|---|---|---|
| 1 | ไวยากรณ์ก่อน reload | `caddy validate` exit **0** |
| 2 | ลำดับบล็อกถูก | `/api/chat` ยังอยู่ **ก่อน** `/api/*` · `/assets/*` และ catch-all ยังอยู่ท้าย |
| 3 | reload ไม่ recreate | container id และ `StartedAt` ของ caddy **ไม่เปลี่ยน** |
| 4 | ทุกหน้าใช้งานได้ | เหมือน G3 ข้อ 3–7 |
| 5 | เส้นทางเก่าเปลี่ยนจาก 502 เป็น 404 | `/api/sci-connect-news` = **404 จาก backend** ไม่ใช่ 502 |
| 6 | ไม่มีเส้นทางตกผิดที่ | `/api/site-admin/users` ยังได้ **403** เมื่อไม่มีสิทธิ์ ไม่ใช่ 404 |

> ข้อ 5 บอกว่า route ถูกลบจริงและคำขอตกไปที่ `handle /api/*` ตามที่ออกแบบ
> ข้อ 6 กันความผิดพลาดที่พบบ่อยที่สุดของ Caddy — ลำดับบล็อกผิดแล้วคำขอถูกบล็อกอื่นกลืน

### ย้อนกลับ

```bash
ssh ubuntu@161.118.237.37 'cd /home/ubuntu/course-advisor-system && cp -a Caddyfile.bak-before-g4 Caddyfile && docker compose -p course-advisor-system exec caddy caddy validate --config /etc/caddy/Caddyfile && docker compose -p course-advisor-system exec caddy caddy reload --config /etc/caddy/Caddyfile'
```

**ตรวจหลังย้อนกลับ:** `sha256sum` ตรงกับ `.bak-before-g4` · `/api/sci-connect-news` กลับเป็น 200 (ถ้า webapi เปิด) หรือ 502 (ถ้ายังหยุด)

---

## ขั้น G5 — ลบบริการ webapi และ env ออกจาก compose

`/home/ubuntu/course-advisor-system` **ไม่ได้อยู่ใต้ git** → การย้อนกลับพึ่งสำเนาไฟล์เท่านั้น

### ไฟล์ที่ต้องแก้ — **สามไฟล์ ไม่ใช่สองไฟล์**

| ไฟล์ | แก้อะไร |
|---|---|
| `docker-compose.prod.yml` | ลบบล็อก `webapi:` (บรรทัด 130–162) **และ** ลบ `- webapi` ใน `depends_on` ของ `caddy` (บรรทัด 173) |
| `.env` | ลบ `VITE_SUPABASE_URL=` และ `VITE_SUPABASE_ANON_KEY=` |

### คำสั่งสำรองก่อนแก้

```bash
ssh ubuntu@161.118.237.37 'cd /home/ubuntu/course-advisor-system && cp -a docker-compose.prod.yml docker-compose.prod.yml.bak-before-g5 && cp -a .env .env.bak-before-g5 && chmod 600 .env.bak-before-g5 docker-compose.prod.yml.bak-before-g5 && sha256sum docker-compose.prod.yml.bak-before-g5 .env.bak-before-g5'
```

### ข้อตรวจก่อนลงมือจริง

| # | ตรวจอะไร | ต้องได้ |
|---|---|---|
| 1 | config อ่านได้ **โดยไม่โชว์ค่าลับ** | `config --no-interpolate` exit **0** · ไม่มี warning เรื่องตัวแปรที่ไม่ได้ตั้ง |
| 2 | ไม่มีใครอ้างตัวแปรที่ลบ | `config --no-interpolate | grep -c SUPABASE` = **0** |
| 3 | ไม่มีใคร `depends_on` webapi | `config --no-interpolate | grep -A3 depends_on | grep -c webapi` = **0** |
| 4 | `webapi` หายจากรายการบริการ | `config --services` **ไม่มี** `webapi` |
| 5 | **`--dry-run` ต้องไม่แตะบริการอื่น** | `up -d --no-build --dry-run` → บริการอื่น **Running** ทุกตัว · **ไม่มีคำว่า Recreate** |

> ข้อ 5 คือข้อที่กันอุบัติเหตุร้ายแรงที่สุด · **ห้ามสั่ง `up -d` ทั้งชุดเพื่อ "ให้ compose จัดการเอง"**
> ถ้า `--dry-run` แสดง `Recreate` ของบริการใด ให้ถือว่าผิดแผนและหยุดทันที

### ลงมือ (เฉพาะบริการที่จำเป็น)

```bash
# 1) หยุดและลบคอนเทนเนอร์ webapi ตัวเดียว
docker compose -p course-advisor-system $CF rm -s -f webapi

# 2) ไม่ต้องสั่ง up ใด ๆ — caddy ที่กำลังรันไม่ได้อ่าน depends_on ใหม่
#    การแก้ depends_on มีผลครั้งถัดไปที่ caddy ถูกสร้างใหม่เท่านั้น
```

| # | ตรวจหลังลงมือ | ต้องได้ |
|---|---|---|
| 6 | คอนเทนเนอร์ webapi หายไป | `docker ps -a --filter name=webapi` = **0 รายการ** |
| 7 | **บริการอื่น id เดิมทุกตัว** | เทียบ container id ก่อน/หลัง **ตรงกันหมด** |
| 8 | เว็บและ API ทำงาน | เหมือน G3 ข้อ 3–7 |
| 9 | ไม่มีคอนเทนเนอร์ค้าง | `docker ps -a --filter label=com.docker.compose.project=course-advisor-system` = **5 รายการ** |

### ย้อนกลับ

```bash
ssh ubuntu@161.118.237.37 'cd /home/ubuntu/course-advisor-system && cp -a docker-compose.prod.yml.bak-before-g5 docker-compose.prod.yml && cp -a .env.bak-before-g5 .env && chmod 600 .env && CF="…ชุด 4 ไฟล์…" && docker compose -p course-advisor-system $CF up -d --no-build --no-deps webapi'
```

`--no-deps` สำคัญ — ไม่ให้ compose ไปแตะ `postgres` ที่ `webapi` ประกาศ `depends_on` ไว้

**ตรวจหลังย้อนกลับ:** `webapi` **Up (healthy)** · `config --services` มี `webapi` · `sha256sum` สองไฟล์ตรงกับ `.bak` · container id ของบริการอื่น**ไม่เปลี่ยน**

> **ลำดับย้อนกลับคือย้อนจากขั้นหลังไปขั้นก่อน: G5 → G4 → G3 → G1**
> ถ้าย้อน G5 แต่ไม่ย้อน G4 webapi จะกลับมาแต่ไม่มีใครเรียกถึง

---

## ขั้น G6 — ตัดสินใจเรื่องไฟล์ที่เก็บไว้

| ไฟล์ | ที่อยู่ | ข้อเสนอ |
|---|---|---|
| ไฟล์สำรองฐาน Supabase 448 KB | `/home/ubuntu/supabase-g0/` | **เก็บถาวร** · มี hash รหัสผ่าน ต้องคงโหมด 600 |
| ไฟล์ ACL/globals จาก G0.9 | `/home/ubuntu/supabase-g0/` | **เก็บถาวร** |
| โค้ด Edge Function จาก G0.10 | `/home/ubuntu/supabase-g0/edge-functions/` | **commit เข้า repo** ที่ `supabase/functions/` ถ้าสแกนแล้วไม่มีค่าลับ |
| การตั้งค่าจาก G0.10 | `/home/ubuntu/supabase-g0/settings/` | **เก็บถาวร โหมด 600 ห้าม commit** |
| ก้อนเข้ารหัสนอกเซิร์ฟเวอร์ | `/home/ubuntu/phase4-offsite/` + สำเนาที่คุณเก็บ | **เก็บทั้งสองที่** |
| ไฟล์ Storage 5 ไฟล์ | `/home/ubuntu/supabase-storage-backup/` | **เก็บถาวร** |
| โค้ด webapi | `/home/ubuntu/course-advisor-system/webapi/` | เก็บไว้ ไม่กินที่ |
| image `course-advisor-system-webapi` | docker | ลบได้หลัง G5 ผ่าน 1 สัปดาห์ |
| `.env.bak-before-g5` | เซิร์ฟเวอร์ | **มี anon key อยู่ข้างใน** · โหมด 600 หรือลบเมื่อแน่ใจ |

---

## ขั้น G7 — ลบโปรเจกต์ Supabase · **ยังเสนอไม่ได้**

| # | เงื่อนไข | สถานะ |
|---|---|---|
| 1 | สำรองฐานข้อมูลและทดสอบ restore แล้ว | **ผ่าน** (47/52 ตาราง · ดูข้อยกเว้นในหัวข้อ 5) |
| 2 | สำรองไฟล์ Storage ครบ | **ผ่าน** |
| 3 | **เก็บ GRANT และ role** | **ยังไม่ทำ** → ขั้น G0.9 |
| 4 | **เก็บโค้ด Edge Function ทุกตัว** | **ยังไม่ทำ** → ขั้น G0.10 ก. |
| 5 | **รู้ว่ามี Edge Function ทั้งหมดกี่ตัว** | **ยังไม่รู้** → G0.10 ก. ตอบข้อนี้ได้ |
| 6 | เก็บการตั้งค่าที่ `pg_dump` ไม่ครอบคลุม | **ยังไม่ทำ** → ขั้น G0.10 ก. |
| 7 | **สำรองอีกชุดนอกเซิร์ฟเวอร์** | **ยังไม่ทำ** → ขั้น G0.10 ข. |
| 8 | G1–G5 ผ่านครบและระบบเดินเองได้ ≥ 2 สัปดาห์ | **ยังไม่เริ่ม** |

> **ข้อเสนอที่ปลอดภัยกว่าการลบ:** Supabase มี **Pause project** ซึ่งหยุดทุกอย่างแต่ไม่ลบข้อมูล
> ถ้าเป้าหมายคือ "ไม่ให้มีอะไรวิ่งอยู่ที่ Supabase อีก" การ pause ให้ผลเท่ากัน แต่ย้อนกลับได้
> และยังเข้าไปเก็บของที่ลืมได้ · **ลบจริงค่อยทำเมื่อครบข้อ 3–8**

---

## 5. ผลการสำรองตามจริง — ข้อยกเว้นทั้งหมด

**`pg_restore` คืน exit code 1 และกู้ได้ 47 จาก 52 ตาราง — นี่ไม่ใช่ "restore ครบ"**
ที่ถูกต้องคือ: **47 ตารางที่กู้ได้ มีจำนวนแถวตรงกับต้นทางทุกตาราง และ 5 ตารางที่เหลือกู้ไม่ได้ในสภาพแวดล้อมทดสอบ**

### ก. อยู่ในไฟล์สำรอง แต่กู้ไม่ได้เพราะขาด extension

| ตาราง | แถว | ต้องมีอะไรจึงกู้ได้ |
|---|---|---|
| `cron.job` | 2 | `pg_cron` |
| `cron.job_run_details` | 1,793 | `pg_cron` |
| `vault.secrets` | 3 | `supabase_vault` — **และถอดรหัสไม่ได้อยู่ดี** |
| `public.rag_documents` | 12 | `vector` — **ทดสอบแล้วว่ากู้ได้ครบ 12 แถว** |

### ข. ไม่อยู่ในไฟล์สำรองเลย

| สิ่งที่ขาด | จำนวน | เพราะอะไร |
|---|---|---|
| `net._http_response` | 12 แถว | ตารางภายในของ extension `pg_net` — `pg_dump` ไม่เก็บ |
| `net.http_request_queue` | 0 แถว | เหมือนกัน |
| **`GRANT` / `REVOKE` ทั้งหมด** | **0 บรรทัดในไฟล์** | ใช้ `--no-privileges` ตอน dump → **สิทธิ์ของ `anon` / `authenticated` / `service_role` ไม่ถูกเก็บ** |
| **`CREATE ROLE`** | **0 บรรทัด** | `pg_dump` ไม่เคยเก็บ role — ต้องใช้ `pg_dumpall --globals-only` |
| `ALTER DEFAULT PRIVILEGES` | 0 บรรทัด | ผลพลอยของ `--no-privileges` |
| ค่าใน `vault.secrets` | 3 ค่า | ciphertext อยู่ในไฟล์ แต่กุญแจอยู่ในระบบ Supabase → **ลบโปรเจกต์แล้วถอดไม่ได้อีก** |

**ของที่ยังเก็บได้ครบ:** `ALTER … OWNER TO` **135 บรรทัด** (เจ้าของ object ถูกบันทึกไว้) · `POLICY` 33 · `TRIGGER` 14

> ผลที่ตามมาจริง: ถ้าวันหนึ่งต้อง restore กลับขึ้น Supabase ใหม่ **จะต้องสร้าง role และให้ GRANT เองทั้งหมด**
> ไม่งั้น PostgREST จะเข้าถึงตารางไม่ได้ทั้งที่ข้อมูลอยู่ครบ — ขั้น G0.9 มีไว้อุดช่องนี้

### ค. `pg_dump` ไม่ครอบคลุมเลย

| # | สิ่งที่ขาด | สถานะ |
|---|---|---|
| 1 | โค้ด Edge Function `sync-sci-news` | **ไม่มีทั้งในไฟล์สำรองและใน repo** → G0.10 ก. |
| 2 | จำนวน Edge Functions ที่มีจริง | **ยังไม่รู้** → G0.10 ก. |
| 3 | การตั้งค่า Auth (SMTP, OAuth, JWT secret, redirect URL, เทมเพลตอีเมล) | → G0.10 ก. |
| 4 | API keys ของโปรเจกต์ | ตั้งใจไม่เก็บ — ฝั่งเราไม่ใช้แล้ว |
| 5 | Storage bucket policy ระดับ API | → G0.10 ก. |
| 6 | **เนื้อไฟล์ใน Storage** | **สำรองแล้ว** 5 ไฟล์ + manifest + checksum |
| 7 | log / analytics | ไม่เก็บ — ไม่จำเป็น |
| 8 | custom domain / network restrictions | → G0.10 ก. |

---

## 6. สรุปลำดับและสถานะ

| ขั้น | ทำอะไร | ย้อนกลับ | ใครทำ | สถานะ |
|---|---|---|---|---|
| **G0.8** | เปิด access log (stdout + กรองค่าลับ) | คัดลอก `Caddyfile` กลับ + reload | ผม | **ยังไม่ทำ** |
| **G0.9** | เก็บ GRANT และ role เพิ่ม | ไม่ต้องย้อน (เพิ่มไฟล์สำรอง) | ผม (ตอนคุณกรอก credentials) | **ยังไม่ทำ** |
| **G0.10 ก** | เก็บ Edge Functions + การตั้งค่า | ไม่ต้องย้อน | **คุณรันเอง** (สคริปต์พร้อม) | **ยังไม่ทำ** |
| **G0.10 ข** | สำรองนอกเซิร์ฟเวอร์แบบเข้ารหัส | ไม่ต้องย้อน | **คุณรันเอง** (สคริปต์พร้อม) | **ยังไม่ทำ** |
| **G1** | ปิด cron job 2 | `active := true` | ผม | **ยังไม่ทำ** |
| **G2** | เฝ้าดู 72 ชม. | — | ผม | **ยังไม่ทำ** |
| **G3** | `stop webapi` | `start webapi` | ผม | **ยังไม่ทำ** |
| **G4** | ลบ Caddy routes 2 บล็อก | คัดลอกไฟล์กลับ + reload | ผม | **ยังไม่ทำ** |
| **G5** | ลบ webapi + `depends_on` + env | คัดลอก 2 ไฟล์กลับ + `up --no-deps webapi` | ผม | **ยังไม่ทำ** |
| **G6** | ตัดสินใจเรื่องไฟล์สำรอง | — | คุณ | **ยังไม่ทำ** |
| **G7** | ลบ (หรือ pause) โปรเจกต์ Supabase | **ลบแล้วย้อนไม่ได้** | คุณ | **เสนอไม่ได้ ยังขาดข้อ 3–8** |

**สภาพระบบตอนนี้ ยังเหมือนก่อนเริ่มทุกอย่าง:**
cron job 2 ยัง `active=true` · `webapi` ยัง **Up (healthy)** · `Caddyfile` ยังมี `reverse_proxy webapi:3001` **2 บล็อก** ·
`.env` ยังมี `VITE_SUPABASE_*` · โปรเจกต์ Supabase ยังอยู่ครบ · หน้าแรกตอบ **200** · `/api/site/external-news` ตอบ **200**
