# Phase 4 — ขั้นส่งไฟล์และสำรอง (พร้อมคัดลอก)

| รายการ | ค่า |
|---|---|
| วันที่ | 12 ตุลาคม 2569 |
| ขอบเขตของเอกสารนี้ | **ส่งไฟล์ + สำรอง เท่านั้น** |
| สถานะ | **ดำเนินการเสร็จถึง B5 แล้ว** เมื่อ 12 ต.ค. 2569 — ผลจริงอยู่ในข้อ 8 |
| **ยังไม่ทำในรอบนี้** | ไม่รัน migration · ไม่ `import --apply` · **ไม่เปลี่ยนคอนเทนเนอร์ production** · ไม่แตะ Supabase |
| ขั้นถัดไปหลังรอบนี้ | `PHASE4_DEPLOY_PROMPT_2569-10-12.md` ขั้น A เป็นต้นไป |

## ตัวเลือกที่เจ้าของเลือกแล้ว

| เรื่อง | ที่เลือก |
|---|---|
| `main.py` | **ฉบับ Phase 4-only** — ไม่รวม crawl review / MKO |
| งาน careers | **รวมในชุดนี้** (`--with-careers`) |
| `PUBLIC_BASE_URL` | ตั้งให้ตรงกับ `SITE_DOMAIN` ของระบบจริง |
| Supabase และระบบปัจจุบัน | **เก็บไว้ย้อนกลับ** |

---

## 1. ไฟล์ที่จะส่ง — ค่าจากการ build รอบนี้

> ตัวเลขและ checksum ทั้งหมดมาจากการ build เมื่อ 12 ต.ค. 2569 **ไม่ใช่ค่าของรอบก่อน**
> รอบก่อนเป็น **28 ไฟล์** เพราะ **ไม่รวม careers** — รอบนี้รวมแล้วจึงเป็น **29 ไฟล์** และ checksum เปลี่ยน

| ไฟล์ | จำนวนไฟล์ข้างใน | ขนาด (ไบต์) | sha256 |
|---|---|---|---|
| `phase4-source.tar.gz` | **29** | 60,912 | `b2e27de4aec1904ac0fd11f853d56b754dafbc32c8968184cc116da32fa03bbd` |
| `phase4-web.tgz` | **19** | 1,457,804 | `50970307f840bcb39574cef6389ef907d2049526c6f43fd6a1a1ec68c1f650bc` |

ส่งไปด้วยอีกสี่ไฟล์: `phase4-source.tar.gz.sha256` · `phase4-web.tgz.sha256` · `phase4-manifest.json` · `phase4-web-manifest.json`

### checksum นี้ build ซ้ำได้ค่าเดิม

สร้างชุดใหม่สองครั้งแล้วได้ **sha256 เท่ากันเป๊ะทั้งสองไฟล์** — จึงเทียบกับตารางนี้ได้จริง ไม่ใช่ดูผ่าน ๆ

ทำได้เพราะตั้ง `mtime=0` และไม่ฝังชื่อไฟล์ลง header ของ gzip · ปล่อยค่าตั้งต้นไว้ gzip
จะฝัง**เวลาที่สร้าง**ลงไป ทำให้ archive ที่มีเนื้อหาเหมือนกันเป๊ะได้ checksum ต่างกันทุกครั้ง
แล้วตัวเลขในเอกสารก็ใช้เทียบอะไรไม่ได้เลย

> **ถ้า build ใหม่แล้ว checksum ไม่ตรงตารางนี้ แปลว่าเนื้อหาเปลี่ยนจริง** — ไม่ใช่เรื่องเวลา
> ให้หาว่าไฟล์ไหนเปลี่ยนก่อนส่ง

### 1.1 ซอร์ส 29 ไฟล์

**backend — Phase 4 (19 ไฟล์)**

```
backend/app/main.py                        ← ตัด crawl_review ออกแล้ว
backend/app/api/deps.py
backend/app/api/routes/auth.py
backend/app/api/routes/extract.py
backend/app/api/routes/site.py
backend/app/api/routes/site_admin.py
backend/app/api/routes/uploads.py
backend/app/core/config.py
backend/app/core/security.py
backend/app/db/session.py
backend/app/jobs/__init__.py
backend/app/jobs/sync_sci_news.py
backend/app/models/user.py
backend/app/schemas/user.py
backend/app/services/__init__.py
backend/app/services/auth_service.py
backend/app/services/file_store.py
backend/app/services/mailer.py
backend/app/services/sci_news.py
```

**careers (1 ไฟล์ — เพิ่มในรอบนี้)**

```
backend/app/api/routes/web_compat.py       ← เพิ่ม GET /career-lists
```

**อื่น ๆ (9 ไฟล์)**

```
backend/requirements.txt                   ← เพิ่ม 3 แพ็กเกจ
db/migrations/007_web_auth.sql
docker-compose.prod.yml                    ← เพิ่ม env 8 ตัว + volume uploads
pipeline/__init__.py
pipeline/web/__init__.py
pipeline/web/import_from_supabase.py
pipeline/web/import_accounts.py
pipeline/web/migrate_storage.py
pipeline/web/programme_links.json
```

### 1.2 หน้าเว็บ 19 ไฟล์

```
index.html
assets/index-BYSigOEx.js      471,276
assets/index-BHkpgChU.css      48,509
assets/logo.png               198,620
assets/hero-building3.webp    232,042
assets/courses/1.png … 13.png  (13 ไฟล์)
assets/README.md
```

> ชื่อไฟล์ asset มี hash ของเนื้อหาอยู่ในชื่อ **ถ้า build ใหม่แล้วชื่อเปลี่ยน ต้องใช้ checksum ชุดใหม่**
> อย่าใช้ตัวเลขในเอกสารนี้กับ archive ที่ build รอบอื่น

---

## 2. ผลทดสอบ bundle — ทดสอบจากไฟล์ที่จะส่งจริง

### 2.1 ทำไมต้องทดสอบจาก bundle

`main.py` ในเครื่องพัฒนา `import crawl_review` แล้ว**ผ่าน** เพราะเครื่องนี้มีไฟล์นั้น
แต่เซิร์ฟเวอร์ไม่มี — การทดสอบจากไฟล์ในเครื่องจึง**พิสูจน์อะไรไม่ได้เลย**

`tools/verify_phase4_bundle.py` จึงประกอบ **ต้นไม้ไฟล์เหมือนเซิร์ฟเวอร์หลัง deploy** ขึ้นมาจริง

1. คัดลอกไฟล์ที่เซิร์ฟเวอร์มีอยู่แล้ว (76 ไฟล์ จากรายการที่อ่านมาตอน preflight)
2. ทับด้วยไฟล์จาก bundle (29 ไฟล์)
3. **ไม่ใส่** ไฟล์ที่เซิร์ฟเวอร์ไม่มีและ bundle ไม่ส่ง — `crawl_review.py` · `services/crawl_review.py` · `staging_store.py` · `schemas/crawl_review.py`

แล้วจึง `import app.main` จากต้นไม้นั้น และอ่านเส้นทางจาก `app.openapi()`

```bash
cd /d/workspace/course-advisor-system-mko2 && python -m tools.verify_phase4_bundle --server-files <รายการไฟล์ของเซิร์ฟเวอร์>
```

### 2.2 ผลที่ได้

```
ประกอบต้นไม้จำลองเซิร์ฟเวอร์: จากเซิร์ฟเวอร์ 76 ไฟล์ · ทับด้วย bundle 29 ไฟล์
ยืนยัน: ต้นไม้จำลองไม่มีไฟล์ของ crawl review เลย (เหมือนเซิร์ฟเวอร์)
import app.main สำเร็จ · FastAPI ลงทะเบียน 50 เส้นทาง

เส้นทางที่ต้องมี: ครบทั้ง 26 รายการ
เส้นทางที่ต้องไม่มี (crawl review): ไม่มีเลย ถูกต้อง

ผ่าน — backend จะขึ้นได้บนเซิร์ฟเวอร์ และมีเส้นทางที่ต้องใช้ครบ
```

**26 เส้นทางที่บังคับว่าต้องมี** — Phase 4 ทั้งชุด · `/career-lists` · และของเดิมที่ต้องไม่หาย (`/chat-web` `/compare-courses` `/recommend-major` `/health`)

> ระหว่างทำขั้นนี้พบว่าวิธีนับเส้นทางแบบเดิน `app.routes` **ใช้ไม่ได้กับ FastAPI รุ่นนี้**
> มันห่อ router ที่ include เข้ามาเป็น `_IncludedRouter` ซึ่งไม่มี `.path` ทำให้เห็นแค่ 5 เส้นทาง
> แล้วสรุปผิดว่า router ไม่ได้ลงทะเบียน · เปลี่ยนไปอ่านจาก `app.openapi()` ซึ่งเป็นสิ่งเดียวกับที่
> `/api/openapi.json` บนเซิร์ฟเวอร์คืนออกมา จึงเทียบกันได้ตรง

### 2.3 careers — ตรวจ dependency ครบแล้ว

**import:** `web_compat.py` ต้องใช้โมดูลเหล่านี้ · **ตรวจแล้วมีบนเซิร์ฟเวอร์ครบทุกตัว ไม่ต้องส่งเพิ่ม**

```
app.api.deps · app.db.session · app.services.chat · app.services.curriculum_facts
app.services.program_compare · app.services.program_match · app.services.program_names
app.services.web_compat · llm.connector · llm.prompts
```

**ฐานข้อมูล:** `/career-lists` อ่าน `mko.v_live_list_items` — **ไม่ใช่แค่ dependency ของโค้ด แต่ของฐานข้อมูลด้วย**

ตรวจบน production แล้ว (อ่านอย่างเดียว)

| รายการ | ค่าจริง |
|---|---|
| view `mko.v_live_list_items` | **มีอยู่แล้ว** |
| แถวทั้งหมด | 156 |
| `item_type = 'career'` | **69 รายการ · 11 หลักสูตร** |
| ค่าที่โค้ดใช้ค้น | `LIST_FIELDS["careers"]` = `'career'` — **ตรงกับข้อมูลจริง** |

**แปลว่า `/career-lists` จะคืนข้อมูล 11 หลักสูตรทันทีที่ deploy** ไม่ต้องรัน migration หรือ import อะไรเพิ่ม

> หน้า `/careers` จะแสดง **11 จาก 12 หลักสูตร** — หลักสูตรที่ยังไม่มีอาชีพที่ตรวจแล้วจะไม่ขึ้นเลย
> ซึ่งเป็นพฤติกรรมที่ออกแบบไว้ (แสดงเท่าที่มีจริง ไม่เติมของที่ยังไม่ได้ตรวจ)

### 2.4 ชุดทดสอบอื่นในรอบนี้

| ชุด | ผล |
|---|---|
| จำลอง 12 ชุด | **315 ผ่าน** |
| integration กับ PostgreSQL จริง | **65 ผ่าน** (26 + 39) |
| หน้าเว็บ `node --test` | **79 ผ่าน / 0 ล้ม** |
| webapi ของเดิม | **82 ผ่าน** |
| frontend ของเดิม `vitest` | **33 ผ่าน** |
| `npm run build` | ผ่าน · **ไม่มีคำว่า supabase ใน `dist/`** |

---

## 3. ชื่อตารางข่าวต้นทาง — ระบุให้ตรงก่อนนำเข้า

รายงานฉบับก่อนเขียนว่า Supabase ใช้ตาราง `sci_connect_news` ซึ่ง **ผิด** · แก้แล้ว

ตรวจจากโค้ดและ schema จริง — **ทั้งสองฝั่งใช้ชื่อตาราง `external_news` เหมือนกัน แต่คนละฐานข้อมูล**

| ที่ | ตารางเต็ม | หลักฐาน |
|---|---|---|
| **Supabase** (ต้นทาง) | **`public.external_news`** | `edge-function/index.ts:235,266,274,285` `.from('external_news')` · `webapi/api/sci-connect-news.js:28` · `import_from_supabase.py` `select … from public.external_news` |
| **ของเรา** (ปลายทาง) | **`web.external_news`** | `005_web_schema.sql` · `import_from_supabase.py` `insert into web.external_news` |

`sci_connect_news` **ไม่มีอยู่จริง** — ที่ทำให้สับสนคือ `SOURCE_NAME = 'sci_connect'` ใน Edge Function ซึ่งเป็น **ค่าในคอลัมน์ `source`** ไม่ใช่ชื่อตาราง

**ผลต่อการนำเข้า: ไม่ต้องแก้สคริปต์** — `import_from_supabase.py` อ่าน `public.external_news` อยู่แล้วถูกต้อง

> เวลาสั่งงานหรือรายงานต่อจากนี้ **ใส่ schema นำหน้าทุกครั้ง** (`public.external_news` หรือ `web.external_news`)
> เพราะชื่อเหมือนกันทั้งสองฝั่ง การเขียนลอย ๆ ว่า `external_news` ตีความได้สองทาง

---

## 4. ขั้นส่งไฟล์ — **บนเครื่องพัฒนา (PowerShell บน Windows)**

> ทุกคำสั่งในหัวข้อ 4 รันใน **PowerShell บนเครื่องพัฒนา** ไม่ใช่บนเซิร์ฟเวอร์

### S1 สร้างชุดซอร์ส (รวม careers)

```powershell
cd D:\workspace\course-advisor-system-mko2; python -m tools.make_phase4_bundle --with-careers
```

ต้องเห็น `29 ไฟล์` และ `careers: ใส่`

### S2 build หน้าเว็บ

```powershell
cd D:\workspace\LastProject; npm run build
```

### S3 ห่อหน้าเว็บ (ตรวจ supabase ให้เองก่อนห่อ)

```powershell
cd D:\workspace\course-advisor-system-mko2; python -m tools.make_web_bundle --dist D:\workspace\LastProject\dist
```

**ถ้า build ยังมีร่องรอย supabase สคริปต์จะไม่สร้าง archive เลย** — ดีกว่าสร้างแล้วไปเจอบนเซิร์ฟเวอร์

### S4 ดู checksum ที่จะใช้เทียบ

```powershell
Get-Content D:\workspace\course-advisor-system-mko2\dist-deploy\phase4-source.tar.gz.sha256, D:\workspace\course-advisor-system-mko2\dist-deploy\phase4-web.tgz.sha256
```

### S5 ตรวจว่า checksum ของไฟล์จริงตรงกับที่บันทึกไว้ (ก่อนส่ง)

คำสั่งนี้เทียบให้เอง แล้วบอก `OK` หรือ `ผิด!` ต่อไฟล์

```powershell
cd D:\workspace\course-advisor-system-mko2\dist-deploy; Get-ChildItem *.sha256 | ForEach-Object { $expected = (Get-Content $_.FullName).Split(' ')[0].ToLower(); $target = $_.Name -replace '\.sha256$',''; $actual = (Get-FileHash $target -Algorithm SHA256).Hash.ToLower(); if ($actual -eq $expected) { "OK    $target" } else { "ผิด!  $target`n  คาด $expected`n  ได้  $actual" } }
```

**ต้องได้ `OK` ทั้งสองไฟล์** — ขึ้น `ผิด!` อย่าส่ง

> **`Get-FileHash` คืนค่าเป็นตัวพิมพ์ใหญ่ แต่ไฟล์ `.sha256` เก็บเป็นตัวพิมพ์เล็ก**
> ถ้าเทียบด้วยตาจะดูเหมือนไม่ตรงทั้งที่ตรง — คำสั่งข้างบนแปลงเป็นพิมพ์เล็กก่อนเทียบ
> (บนเซิร์ฟเวอร์ `sha256sum -c` จัดการให้เองอยู่แล้ว จึงไม่มีปัญหานี้)

### S6 ส่งขึ้นเซิร์ฟเวอร์

```powershell
cd D:\workspace\course-advisor-system-mko2\dist-deploy; scp -i $HOME\.ssh\oci.key phase4-source.tar.gz phase4-source.tar.gz.sha256 phase4-manifest.json phase4-web.tgz phase4-web.tgz.sha256 phase4-web-manifest.json ubuntu@161.118.237.37:/home/ubuntu/
```

### S7 เข้าเซิร์ฟเวอร์

```powershell
ssh -i $HOME\.ssh\oci.key ubuntu@161.118.237.37
```

---

## 5. ขั้นตรวจ — **บนเซิร์ฟเวอร์ (bash)**

> ทุกคำสั่งตั้งแต่หัวข้อ 5 ลงไปรันบน **เซิร์ฟเวอร์** หลัง ssh เข้าไปแล้ว

### T1 ยืนยันว่าอยู่เครื่องถูก

ชื่อคอนเทนเนอร์ชุดนี้ซ้ำกับชุดบนเครื่องพัฒนา · `docker` ที่เผลอรันผิดเครื่องจะโดนของเครื่องนั้นเงียบ ๆ

```bash
hostname && docker compose ls
```

ต้องได้ `stpnru` และเห็นโปรเจกต์ `course-advisor-system` **ถ้าไม่ใช่ หยุด**

### T2 ตรวจว่าของถึงครบและไม่เพี้ยน

```bash
cd /home/ubuntu && sha256sum -c phase4-source.tar.gz.sha256 && sha256sum -c phase4-web.tgz.sha256
```

**ต้องได้ `OK` ทั้งสองบรรทัด**

```bash
cd /home/ubuntu && echo "ซอร์ส: $(tar -tzf phase4-source.tar.gz | grep -vc '/$') ไฟล์ (ต้องได้ 29)" && echo "หน้าเว็บ: $(tar -tzf phase4-web.tgz | grep -vc '/$') ไฟล์ (ต้องได้ 19)"
```

### T3 ตรวจเนื้อในชุดซอร์ส

```bash
cd /home/ubuntu && tar -tzf phase4-source.tar.gz | sort
```

**ต้องเห็น `backend/app/api/routes/web_compat.py`** (งาน careers) และ **ต้องไม่เห็นไฟล์ใดที่มีคำว่า `crawl_review`**

```bash
cd /home/ubuntu && tar -xzOf phase4-source.tar.gz backend/app/main.py | grep -c crawl_review || echo "0 — main.py ไม่อ้าง crawl_review ถูกต้อง"
```

```bash
cd /home/ubuntu && tar -xzOf phase4-source.tar.gz backend/app/api/routes/web_compat.py | grep -c "career-lists"
```

ต้องได้อย่างน้อย `1`

### T4 แตกชุดไว้ **ยังไม่วางทับ**

```bash
cd /home/ubuntu && rm -rf phase4-src && mkdir -p phase4-src && tar -xzf phase4-source.tar.gz -C phase4-src && find phase4-src -type f | wc -l
```

ต้องได้ `29`

```bash
cd /home/ubuntu && rm -rf phase4-web && mkdir -p phase4-web && tar -xzf phase4-web.tgz -C phase4-web && ls -1 phase4-web && (grep -rl supabase phase4-web/ && echo "พบร่องรอย — อย่าใช้ชุดนี้") || echo "สะอาด"
```

ต้องได้ `สะอาด`

### T5 เทียบชุดใหม่กับของที่รันอยู่ (ยังไม่เปลี่ยนอะไร)

```bash
diff -u /home/ubuntu/course-advisor-system/docker-compose.prod.yml /home/ubuntu/phase4-src/docker-compose.prod.yml
```

**ต้องต่างกันเฉพาะ env 8 ตัว (`UPLOADS_DIR` · `UPLOAD_MAX_BYTES` · `SMTP_*` 5 ตัว · `PUBLIC_BASE_URL`) และ volume `./uploads:/srv/uploads`**

```bash
diff -u /home/ubuntu/course-advisor-system/backend/app/main.py /home/ubuntu/phase4-src/backend/app/main.py
```

ต้องเห็นการเพิ่ม router ของ Phase 4 (`site` · `site_admin` · `uploads` · `extract`) · **ไม่มีคำว่า `crawl_review`**

```bash
diff -u /home/ubuntu/course-advisor-system/backend/app/api/routes/web_compat.py /home/ubuntu/phase4-src/backend/app/api/routes/web_compat.py | head -40
```

ต้องเห็นการเพิ่ม `GET /career-lists` เท่านั้น

---

## 6. ขั้นสำรอง — บนเซิร์ฟเวอร์

**ของสำรองคือทางถอยเดียว — ขาดข้อใดข้อหนึ่งให้หยุด**

### B1 ตั้งตัวแปร

```bash
export COMPOSE="-p course-advisor-system -f /home/ubuntu/course-advisor-system/docker-compose.prod.yml -f /home/ubuntu/course-advisor-system/docker-compose.staging.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-backend-2fdc6f2.yml -f /home/ubuntu/release-2fdc6f2/compose.pin-frontend-2fdc6f2.yml"
```

```bash
docker compose $COMPOSE config --format json > /tmp/effective.json && export CTX=$(python3 -c "import json;print(json.load(open('/tmp/effective.json'))['services']['backend']['build']['context'])") && export IMG=$(python3 -c "import json;d=json.load(open('/tmp/effective.json'));print(d['services']['backend'].get('image') or d['name']+'-backend')") && export WEB=$(python3 -c "import json;print([v['source'] for v in json.load(open('/tmp/effective.json'))['services']['caddy']['volumes'] if v['target']=='/srv/web'][0])") && export OLD_ID=$(docker inspect --format '{{.Image}}' $(docker compose $COMPOSE ps -q backend)) && export APP_UID=$(docker compose $COMPOSE exec -T backend id -u) && export HOST_GID=$(id -g)
```

```bash
echo "CTX=$CTX"; echo "IMG=$IMG"; echo "WEB=$WEB"; echo "OLD_ID=$OLD_ID"; echo "APP_UID=$APP_UID"; echo "HOST_GID=$HOST_GID"; test -n "$CTX" -a -n "$IMG" -a -n "$WEB" -a -n "$OLD_ID" -a -n "$APP_UID" -a -n "$HOST_GID" && test -d "$CTX" -a -d "$WEB" && echo "ครบทุกค่า"
```

ค่าที่ preflight อ่านได้เมื่อ 12 ต.ค.

| ตัวแปร | ค่าที่ควรได้ |
|---|---|
| `CTX` | `/home/ubuntu/course-advisor-system` |
| `IMG` | `course-advisor-system-backend:2fdc6f2` |
| `WEB` | `/home/ubuntu/course-advisor-system/web` |
| `OLD_ID` | `sha256:4a45677ec010fc076e283b1e556bd4c1b0b25bc66786b32ec6f64a76ad0cca46` |
| `APP_UID` | `1000` |
| `HOST_GID` | `1001` |

**ต่างไปให้หยุดแล้วรายงาน**

### B2 สำรองฐานข้อมูล

```bash
docker exec -i course-advisor-system-postgres-1 pg_dump -U postgres -Fc course_advisor > /home/ubuntu/db-backup-$TAG.dump && ls -lh /home/ubuntu/db-backup-$TAG.dump
```

ตรวจว่า archive อ่านได้ · **ไฟล์ dump อยู่บน host ไม่ได้อยู่ในคอนเทนเนอร์** จึงต้องป้อนทาง stdin

```bash
docker exec -i course-advisor-system-postgres-1 pg_restore -l < /home/ubuntu/db-backup-$TAG.dump > /home/ubuntu/db-backup-$TAG.toc; echo "exit=$?"
```

**`exit=0` เท่านั้นถือว่าผ่าน** — คำสั่งเดิมเขียนพาธไว้หลัง `-l` ซึ่งเป็นพาธ**ในคอนเทนเนอร์** ที่ไม่มีไฟล์นั้น
และการต่อ `| head -5` ทำให้ exit code ที่เห็นเป็นของ `head` ไม่ใช่ของ `pg_restore` จึงไม่รู้เลยว่าอ่านสำเร็จหรือไม่

```bash
wc -l < /home/ubuntu/db-backup-$TAG.toc && head -5 /home/ubuntu/db-backup-$TAG.toc && grep -c "TABLE DATA" /home/ubuntu/db-backup-$TAG.toc
```

เก็บไฟล์ `.toc` ไว้เป็นหลักฐานว่าอ่านอะไรได้บ้าง

> **สิ่งที่ขั้นนี้พิสูจน์: อ่านโครงสร้าง archive ได้ แต่ยังไม่ได้ทดสอบ restore**
>
> `pg_restore -l` อ่านแค่สารบัญของไฟล์ · **ไม่ได้ยืนยันว่าข้อมูลข้างในกู้คืนได้จริง**
> การยืนยันแบบนั้นต้อง restore ลงฐานข้อมูลเปล่าแล้วเทียบจำนวนแถว ซึ่ง **ไม่ได้ทำในรอบนี้**
> ห้ามรายงานว่า "สำรองใช้ได้จริง" หรือ "กู้คืนได้" จากผลของขั้นนี้

### B3 สำรองหน้าเว็บ · compose · main.py · web_compat.py

```bash
sudo cp -a "$WEB" /home/ubuntu/web-backup-$TAG && ls -1 /home/ubuntu/web-backup-$TAG | head
```

```bash
cp -a "$CTX/docker-compose.prod.yml" /home/ubuntu/docker-compose.prod.yml.before-phase4-$TAG && cp -a "$CTX/backend/app/main.py" /home/ubuntu/main.py.before-phase4-$TAG && cp -a "$CTX/backend/app/api/routes/web_compat.py" /home/ubuntu/web_compat.py.before-phase4-$TAG && cp -a "$CTX/backend/requirements.txt" /home/ubuntu/requirements.txt.before-phase4-$TAG && ls -l /home/ubuntu/*.before-phase4
```

**ต้องเห็น 4 ไฟล์** — `web_compat.py` อยู่ในรายการเพราะรอบนี้รวม careers ไปด้วย ต้องย้อนได้แยก

### B4 ติดป้ายให้ image ตัวปัจจุบัน

```bash
docker tag "$OLD_ID" course-advisor-backend:pre-phase4-$TAG && test "$(docker image inspect --format '{{.Id}}' course-advisor-backend:pre-phase4-$TAG)" = "$OLD_ID" && echo "ป้ายสำรองชี้ image ตัวเดียวกับที่รันอยู่"
```

**ต้องเห็นบรรทัดยืนยัน** — ถ้าไม่เห็น อย่าไปต่อ เพราะจะย้อนกลับไม่ได้

### B5 ตรวจของสำรองครบ

```bash
ls -lh /home/ubuntu/db-backup-$TAG.dump /home/ubuntu/*.before-phase4-$TAG && ls -d /home/ubuntu/web-backup-$TAG && docker image inspect --format 'image สำรอง: {{.Id}}' course-advisor-backend:pre-phase4-$TAG
```

**ครบ 6 อย่าง: dump · 4 ไฟล์ `.before-phase4` · โฟลเดอร์หน้าเว็บ · ป้าย image**

---

## 7. วิธีกรอกค่าลับโดยไม่ให้ค่าหลุด

**ค่าสองตัวนี้ไม่มีอยู่บนเซิร์ฟเวอร์เลย** (preflight ตรวจแล้ว มีแต่ `VITE_SUPABASE_ANON_KEY` ซึ่งอ่าน `auth.users` และ bucket แบบ private ไม่ได้)

| ตัวแปร | เอามาจาก |
|---|---|
| `SUPABASE_DB_URL` | Dashboard → Project Settings → Database → Connection string |
| `SUPABASE_SERVICE_ROLE_KEY` | Dashboard → Project Settings → API → `service_role` |

### กฎที่ต้องทำตาม

| ห้าม | เพราะ |
|---|---|
| พิมพ์ค่าลงแชต | จะอยู่ในประวัติการสนทนาถาวร |
| ใส่ค่าในบรรทัดคำสั่ง (`export KEY=eyJ...`) | ติดใน `~/.bash_history` และ `ps` ของผู้ใช้อื่นเห็นได้ |
| เขียนลงไฟล์ `.env` | ไม่จำเป็น — ใช้แค่ตอนรันสคริปต์ย้าย แล้วทิ้ง |
| `echo $SUPABASE_SERVICE_ROLE_KEY` | พิมพ์ค่าออกจอและอาจติด log |

### วิธีที่ใช้

`read -rs` อ่านจากแป้นพิมพ์โดย **ไม่แสดงตัวอักษร** และ **ไม่ลงประวัติคำสั่ง** เพราะค่าไม่ได้อยู่ในบรรทัดคำสั่ง

ปิดการบันทึกประวัติของ shell นี้ก่อน เผื่อเผลอพิมพ์อะไรติดไป

```bash
unset HISTFILE && export HISTSIZE=0 && echo "shell นี้ไม่บันทึกประวัติแล้ว"
```

```bash
read -rsp 'SUPABASE_DB_URL: ' SUPABASE_DB_URL && echo && read -rp 'SUPABASE_URL (ไม่ลับ): ' SUPABASE_URL && read -rsp 'SUPABASE_SERVICE_ROLE_KEY: ' SUPABASE_SERVICE_ROLE_KEY && echo && export SUPABASE_DB_URL SUPABASE_URL SUPABASE_SERVICE_ROLE_KEY && echo "ตั้งครบสามค่า"
```

ตรวจว่าตั้งแล้วจริงโดย **ไม่แสดงค่า** — ดูแค่ความยาวและสามตัวอักษรแรกของรูปแบบ

```bash
printf 'SUPABASE_DB_URL: ยาว %d · ขึ้นต้น %s\n' "${#SUPABASE_DB_URL}" "${SUPABASE_DB_URL:0:11}" && printf 'SUPABASE_SERVICE_ROLE_KEY: ยาว %d · ขึ้นต้น %s\n' "${#SUPABASE_SERVICE_ROLE_KEY}" "${SUPABASE_SERVICE_ROLE_KEY:0:3}" && printf 'SUPABASE_URL: %s\n' "$SUPABASE_URL"
```

| ควรได้ | หมายเหตุ |
|---|---|
| `SUPABASE_DB_URL` ขึ้นต้น `postgresql:` | 11 ตัวอักษรแรกไม่ใช่ความลับ |
| `SUPABASE_SERVICE_ROLE_KEY` ขึ้นต้น `eyJ` | เป็น JWT · 3 ตัวแรกบอกแค่รูปแบบ |
| ความยาวทั้งคู่ไม่เป็น `0` | ถ้าเป็น 0 คือกรอกไม่ติด ให้กรอกใหม่ |

ส่งเข้าคอนเทนเนอร์ด้วย **`-e ชื่อ` เปล่า ๆ ไม่ใส่ `=ค่า`** — ค่ามาจาก env ของ shell จึงไม่ปรากฏในคำสั่ง

```bash
run_pipeline() { docker compose $COMPOSE run --rm --no-deps -w /app -v "$CTX/pipeline:/app/pipeline:ro" -e SUPABASE_DB_URL -e SUPABASE_URL -e SUPABASE_SERVICE_ROLE_KEY backend python -u -m "$@"; }
```

ลบค่าออกเมื่อใช้เสร็จ

```bash
unset SUPABASE_DB_URL SUPABASE_SERVICE_ROLE_KEY SUPABASE_URL && echo "ลบค่าออกจาก shell แล้ว"
```

> **ถ้าต้องปิด terminal กลางทาง** ค่าจะหายไปด้วย ต้องกรอกใหม่ — ตั้งใจให้เป็นอย่างนั้น
> ค่าเหล่านี้ไม่ควรค้างอยู่บนเซิร์ฟเวอร์หลังย้ายเสร็จ

---

## 8. ผลการดำเนินการจริง — 12 ตุลาคม 2569

ทำครบถึง **B5** แล้ว · **ยังไม่มีอะไรที่ production ใช้งานอยู่ถูกเปลี่ยน**

### ชื่อไฟล์ใช้ `TAG` ต่อท้าย เพื่อไม่เขียนทับของสำรองชุดอื่น

บน `/home/ubuntu` มีของสำรองจากงานก่อน ๆ อยู่แล้ว (`backup-before-006-*`, `backup-before-s1-mapping-*`,
`m3-backup-*`, `c2-webapi-backup/`, `web-dist.tar.gz`) · ขั้น B1 จึงเลือก `TAG` ที่ยังไม่มีใครใช้
และ**ทุกขั้นตรวจว่าปลายทางยังไม่มีไฟล์ก่อนเขียน** ถ้ามีจะหยุดทันที

ค่าที่ได้รอบนี้คือ **`TAG=2569-10-12`** (ไม่ชนกับของเดิม จึงไม่ต้องเติม `-r2`)

ค่าทั้งหมดบันทึกไว้ที่ **`/home/ubuntu/.phase4-vars`** (โหมด 600) ให้ทุกขั้นอ่านค่าชุดเดียวกัน

```bash
. /home/ubuntu/.phase4-vars && echo "TAG=$TAG · CTX=$CTX · WEB=$WEB"
```

### ค่าจาก B1 — ตรงกับ preflight ทุกตัว

| ตัวแปร | ค่าที่ได้ | ตรงกับ preflight |
|---|---|---|
| `CTX` | `/home/ubuntu/course-advisor-system` | ตรง |
| `IMG` | `course-advisor-system-backend:2fdc6f2` | ตรง |
| `WEB` | `/home/ubuntu/course-advisor-system/web` | ตรง |
| `OLD_ID` | `sha256:4a45677ec010fc076e283b1e556bd4c1b0b25bc66786b32ec6f64a76ad0cca46` | ตรง |
| `APP_UID` | `1000` | ตรง |
| `HOST_GID` | `1001` | ตรง |

### ผล T2–T5

| ขั้น | ผล |
|---|---|
| T1 | `hostname` = `stpnru` · `docker compose ls` เห็น `course-advisor-system` ใช้ compose ครบสี่ไฟล์ |
| T2 | `sha256sum -c` **exit 0 ทั้งสองไฟล์** · ซอร์ส **29 ไฟล์** · หน้าเว็บ **19 ไฟล์** |
| T3 | มี `web_compat.py` ในชุด · `main.py` อ้าง `crawl_review` **0 ครั้ง** · `web_compat.py` มี `career-lists` **1 ครั้ง** · `main.py` ลงทะเบียน **14 router ไม่มี crawl_review** |
| T4 | แตกได้ 29 / 19 ไฟล์ · **ตรวจ manifest ทีละไฟล์: ตรงกัน 29/29 และ 19/19 · ผิด 0 · ขาด 0 · เกิน 0** · หน้าเว็บ **สะอาด** ไม่มีคำว่า supabase |
| T5 | compose ต่างเฉพาะ env 8 ตัว + volume `uploads` · `main.py` ต่างเฉพาะ router ของ Phase 4 · `web_compat.py` เพิ่ม **66 บรรทัด ไม่ลบโค้ดเดิมเลย** มีแค่ `GET /career-lists` · `requirements.txt` เพิ่ม 3 แพ็กเกจ |

### ผล B2 — สำรองฐานข้อมูล

| รายการ | ค่า |
|---|---|
| ไฟล์ | `/home/ubuntu/db-backup-2569-10-12.dump` |
| ขนาด | **53,876,818 ไบต์** |
| `pg_dump` | **exit 0** |
| `pg_restore -l` (ป้อนทาง stdin) | **exit 0** |
| สารบัญ | **313 บรรทัด** · `TABLE DATA` **35 รายการ** · เก็บไว้ที่ `db-backup-2569-10-12.toc` |
| schema ใน archive | `mko` · `web` (นอกจาก `public`) |
| เวลาที่ archive ถูกสร้าง | `2026-10-11 18:29:19 UTC` |
| sha256 | `e373cfb76593a00260c6e7a87c617f83f886cb05b6636cd116e1507ae3e0b201` |

> **อ่านโครงสร้าง archive ได้ แต่ยังไม่ได้ทดสอบ restore**
>
> `pg_restore -l` อ่านแค่สารบัญ · **ไม่ได้ยืนยันว่าข้อมูลกู้คืนได้จริง**
> การยืนยันแบบนั้นต้อง restore ลงฐานข้อมูลเปล่าแล้วเทียบจำนวนแถว ซึ่งยังไม่ได้ทำ

### ผล B3 — หน้าเว็บและไฟล์เดิม

| ของสำรอง | ผล |
|---|---|
| `/home/ubuntu/web-backup-2569-10-12/` | **40 ไฟล์** เท่ากับของจริง · `diff -r` กับของจริง **exit 0 (เหมือนกันทุกไฟล์)** |
| `docker-compose.prod.yml.before-phase4-2569-10-12` | 12,615 ไบต์ · `cmp` กับต้นฉบับ **ตรง** |
| `main.py.before-phase4-2569-10-12` | 6,955 ไบต์ · **ตรง** |
| `web_compat.py.before-phase4-2569-10-12` | 28,007 ไบต์ · **ตรง** |
| `requirements.txt.before-phase4-2569-10-12` | 393 ไบต์ · **ตรง** |
| checksum ทั้งสี่ไฟล์ | `/home/ubuntu/before-phase4-2569-10-12.sha256` |

### ผล B4 — image จากคอนเทนเนอร์ที่รันจริง

ไม่ได้ติดป้ายจากชื่อ tag ที่เขียนใน compose แต่จาก `docker inspect` ของ**คอนเทนเนอร์ที่รันอยู่จริง**
แล้วเทียบกับค่าที่บันทึกไว้ตอน B1 ก่อนติดป้าย — ถ้าไม่ตรงจะหยุด

| รายการ | ค่า |
|---|---|
| คอนเทนเนอร์ | `fda31caa20c4` |
| image ของคอนเทนเนอร์ | `sha256:4a45677ec010…` |
| เทียบกับ `OLD_ID` ของ B1 | **ตรงกัน** |
| ป้ายที่ติด | `course-advisor-backend:pre-phase4-2569-10-12` |
| ป้ายชี้ไป | `sha256:4a45677ec010…` — **ตรงกับที่รันอยู่** |

### ผล B5 — ของสำรองครบ

ครบทั้ง **10 รายการ** (dump · toc · checksum ของ dump · 4 ไฟล์ `.before-phase4-TAG` · checksum ของสี่ไฟล์ · โฟลเดอร์หน้าเว็บ · ป้าย image)

### ยืนยันว่า production ยังไม่ถูกแตะ

| ตรวจอะไร | ผล |
|---|---|
| คอนเทนเนอร์ทั้ง 6 | ยังเป็นชุดเดิม · backend `Up 12 days` · ไม่มีตัวใด restart |
| image ของ backend | ยัง `sha256:4a45677ec010…` **เท่ากับก่อนเริ่มงาน** |
| ซอร์สใน `$CTX` | ทั้ง 4 ไฟล์ **ไม่เปลี่ยน** (`cmp` กับของสำรองตรงหมด) |
| volume `/srv/uploads` | **ยังไม่มี** — ถูกต้อง ขั้น B ของ deploy prompt จะเพิ่ม |
| คอลัมน์ `role`/`status`/`password_scheme` ใน `public.users` | **ยังไม่มีเลย (0 คอลัมน์)** → migration 007 **ยังไม่ได้รัน** |
| `public.auth_sessions` · `public.migration_007_user_backup` | **ยังไม่มี** → 007 ยังไม่ได้รัน |
| จำนวนผู้ใช้ | **202 คน** เท่าเดิม |
| `web.site_courses` | **0 แถว** → ยังไม่ได้ import |
| Supabase · cron เก่า | **ไม่แตะเลย** |
| secrets | **ยังไม่ได้กรอก** — ขั้นนี้ไม่ใช้ |

### สิ่งที่เพิ่มขึ้นบนเซิร์ฟเวอร์ในรอบนี้ (ไม่มีผลกับระบบ)

```
/home/ubuntu/phase4-source.tar.gz          ชุดซอร์ส
/home/ubuntu/phase4-web.tgz                ชุดหน้าเว็บ
/home/ubuntu/phase4-*.sha256               checksum
/home/ubuntu/phase4-*manifest.json         manifest
/home/ubuntu/phase4-src/                   ซอร์สที่แตกไว้รอ — ยังไม่วางทับ
/home/ubuntu/phase4-web/                   หน้าเว็บที่แตกไว้รอ — ยังไม่วางทับ
/home/ubuntu/db-backup-2569-10-12.*        ของสำรองฐานข้อมูล
/home/ubuntu/web-backup-2569-10-12/        ของสำรองหน้าเว็บ
/home/ubuntu/*.before-phase4-2569-10-12    ของสำรองไฟล์เดิม
/home/ubuntu/before-phase4-2569-10-12.sha256
/home/ubuntu/.phase4-vars                  ค่าที่ทุกขั้นใช้ร่วมกัน (โหมด 600)
/home/ubuntu/check_manifest.py             สคริปต์ตรวจ manifest
ป้าย image course-advisor-backend:pre-phase4-2569-10-12
```

---

## 9. จุดหยุดของรอบนี้


ทำถึง **ขั้น B5** แล้วหยุด · **ยังไม่ได้เปลี่ยนอะไรที่ production ใช้งานอยู่**

| สิ่งที่เปลี่ยนบนเซิร์ฟเวอร์ในรอบนี้ | เปลี่ยนอะไร |
|---|---|
| `/home/ubuntu/phase4-source.tar.gz` ฯลฯ | ไฟล์ใหม่ที่ส่งขึ้นไป **ไม่มีผลกับระบบ** |
| `/home/ubuntu/phase4-src/` · `phase4-web/` | ชุดที่แตกไว้รอ **ยังไม่วางทับ** |
| `/home/ubuntu/db-backup-2569-10-12.dump` ฯลฯ | ของสำรอง |
| ป้าย image `pre-phase4-2569-10-12` | ป้ายเพิ่ม **ไม่เปลี่ยน image ที่รันอยู่** |

| สิ่งที่ **ยังไม่ทำ** |
|---|
| ไม่วางซอร์สทับ `$CTX` |
| ไม่รัน migration 007 |
| ไม่รัน `import --apply` ใด ๆ |
| ไม่ `docker compose build` หรือ `up` |
| ไม่แตะหน้าเว็บที่ `$WEB` |
| ไม่แตะ Supabase หรือ cron เก่า |

### รายงานกลับก่อนไปต่อ — **ครบแล้วทุกข้อ ดูข้อ 8**

| # | รายการ | ผล |
|---|---|---|
| 1 | T2 `sha256sum -c` และจำนวนไฟล์ | exit 0 ทั้งคู่ · 29 / 19 |
| 2 | T3 มี `web_compat.py` · `main.py` ไม่มี `crawl_review` | ผ่าน |
| 3 | T4 แตกได้ครบ · manifest ตรงทีละไฟล์ · หน้าเว็บสะอาด | ผ่าน |
| 4 | T5 `diff` ทั้งสี่ไฟล์ ต่างเฉพาะที่คาดไว้ | ผ่าน |
| 5 | ค่าจาก B1 ทั้งหกตัว | ตรงกับ preflight ทุกตัว |
| 6 | B5 ของสำรองครบ | ครบ 10 รายการ |

**ขั้นถัดไป: ขั้น A ของ [PHASE4_DEPLOY_PROMPT_2569-10-12.md](PHASE4_DEPLOY_PROMPT_2569-10-12.md)**
(ขั้น P1 ยังต้องรันซ้ำในวันที่ deploy เพื่อยืนยันว่าค่าไม่เปลี่ยน · ขั้น P2/P3 ทำแล้วในรอบนี้)

### สิ่งที่ยังค้างและต้องตัดสินใจก่อนขั้น A

| # | เรื่อง |
|---|---|
| 1 | `PUBLIC_BASE_URL` ยังไม่ได้ตั้ง — ขั้น B2 ของ deploy prompt จะตั้งให้ตรงกับ `SITE_DOMAIN` |
| 2 | `SUPABASE_DB_URL` · `SUPABASE_SERVICE_ROLE_KEY` **ยังไม่ได้กรอก** (ขั้น C จึงจะใช้) |
| 3 | การ restore ของสำรองยังไม่ได้ทดสอบ — ถ้าต้องการความมั่นใจกว่านี้ ต้อง restore ลงฐานข้อมูลเปล่าแยกแล้วเทียบจำนวนแถว |
