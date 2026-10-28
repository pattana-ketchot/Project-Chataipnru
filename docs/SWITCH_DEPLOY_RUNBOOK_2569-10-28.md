# Runbook: deploy ชุดสวิตช์เลือกโมเดล + patch กันเวลาให้ตัวสำรอง

ชุดที่จะ deploy คือ PR #2 (`feature/model-switch-fallback-budget`)
**ยังไม่ merge · ยังไม่ deploy · ยังไม่เปลี่ยนค่าใดของ production จนกว่าจะอนุมัติ**

เอกสารนี้เป็นลำดับปฏิบัติพร้อมด่านหยุดและทางย้อน · รายละเอียดของงานอยู่ใน
`SWITCH_PLUS_FALLBACK_READINESS_2569-10-28.md` · ที่มาของตัวเลขอยู่ใน
`MODEL_SWITCH_2569-10-28.md` และ `LOCAL_FALLBACK_FIX_2569-10-28.md`

## ชุดปล่อยคือ commit ไหน

| | ค่า |
|---|---|
| branch | `feature/model-switch-fallback-budget` (head ของ PR #2) |
| **commit สุดท้ายที่แตะของที่ deploy จริง** | **`e1ef9e8`** — `fix(release): run the fallback test in the deploy gate, and add the deploy runbook` |
| commit หลังจากนั้น | **เอกสารล้วน** ไม่แตะโค้ด สคริปต์ หรือชุดซ้อนอิมเมจ จึงไม่เปลี่ยนสิ่งที่ deploy |
| ตัวระบุเนื้อหาที่แท้จริง | `backend-release/SHA256SUMS` — 11 ไฟล์ที่ซ้อนทับอิมเมจ · ด่านทุกด่านตรวจจากไฟล์นี้ ไม่ได้ตรวจจากเลข commit |

**ก่อนเริ่ม** ให้จดเลข commit ที่ใช้ทำ archive จริงลงใน log ของรอบ deploy:

```bash
git rev-parse feature/model-switch-fallback-budget        # ต้องตรงกับ head ของ PR #2
git log --oneline -1 feature/model-switch-fallback-budget
```

ถ้าเลขที่ได้ไม่ตรงกับ head ของ PR #2 บน GitHub แปลว่ามีคนเพิ่ม commit หลังรีวิว
— **หยุด** แล้วทบทวน diff ใหม่ก่อน ไม่ใช่ deploy ต่อ

---

## 0. หลังจาก deploy แล้วระบบจะใช้โมเดลอะไร

**Gemini เหมือนเดิมทุกประการ** — migration 010 เพิ่มคอลัมน์ `provider` โดยปล่อยเป็น
`NULL` และโค้ดถือว่าค่าที่บันทึกใช้ได้ก็ต่อเมื่อ `provider` ไม่ใช่ NULL
(`services/ai_settings.py`) แถวเดิมที่มี `model` แต่ไม่มี `provider` จึงยังตกไปใช้
ค่าจาก env (`LLM_PROVIDER=gemini` · `GEMINI_MODEL=gemini-3.5-flash-lite`) เหมือนก่อน deploy

**การเลือก Ollama เป็นการกระทำของผู้ดูแลที่หน้าเว็บ ไม่ใช่ผลข้างเคียงของการ deploy**
และหน้านั้นแสดงข้อจำกัดไว้แล้ว: แยก "ค่าที่บันทึก" ออกจาก "ค่าที่ใช้จริง" พร้อมเหตุผล
เมื่อสองค่าไม่ตรงกัน · ปุ่มตรวจแยกสองขั้นและผลรวมไม่ขึ้นเขียวถ้าขั้นที่วัดงานขนาด
เท่าของจริงไม่ผ่าน · มีข้อความกำกับว่าเป็นการวัดด้วยเนื้อหาตัวอย่าง คำถามจริงอาจช้ากว่า

**Ollama ยังไม่พร้อมรับคำถามที่ต้องอ้างอิงเอกสารภายในเพดาน 30 วินาที** (ตัวเลขใน
`MODEL_SWITCH` ข้อ 6 และ `SWITCH_PLUS_FALLBACK_READINESS` ข้อ 4) — ไม่ควรสลับไปใช้
จนกว่าจะมีรอบวัดใหม่ที่ผ่าน

---

## 1. สิ่งที่ตรวจแล้วบนเซิร์ฟเวอร์ (28 ต.ค. 2569 · อ่านอย่างเดียว)

| รายการ | ผล |
|---|---|
| ไฟล์ compose ทั้ง 13 ไฟล์ที่ `compose-args.txt` อ้าง | **ครบ** |
| อิมเมจฐาน `course-advisor-system-backend:followup-2569-10-28` | **มี** (450MB) |
| คอนเทนเนอร์ backend ที่รันอยู่ | อิมเมจเดียวกัน · ขึ้นตั้งแต่ 27 ต.ค. 21:32 UTC |
| เนื้อที่ดิสก์ | ว่าง 57G จาก 97G (ใช้ไป 42%) |
| `/home/ubuntu/release-switch-2569-10-28` | ยังไม่มี — `deploy_backend.sh` สร้างเอง |
| `sha256sum -c SHA256SUMS` ของชุดซ้อนที่ PR head | **ผ่าน 11/11** |

### พาธทั้งหมดที่สคริปต์ใช้จริง

**สองโฟลเดอร์แรกชื่อคล้ายกันมาก สลับเมื่อไหร่ rollback จะหาไฟล์ไม่เจอ**

| พาธ | ใคร/อะไรใช้ | ใครสร้าง |
|---|---|---|
| `/home/ubuntu/switch-release-2569-10-28/` | **ที่วางชุดและที่รันสคริปต์** — หัวสคริปต์ทุกตัวเขียนว่า `cd /home/ubuntu/switch-release-2569-10-28 && ./xxx.sh` · สคริปต์อ้างตัวเองด้วย `$HERE` และเก็บผลลัพธ์ไว้ที่นี่ (`db-run-*`, `backend-run-*`, `web-run-*`, `db-rollback-*`) | **คนทำสร้างเอง** ตอนแตกชุด |
| `/home/ubuntu/release-switch-2569-10-28/` | **บริบท build + ที่เก็บ compose pin** · `deploy_backend.sh` ใช้เป็น `$REL`: `mkdir -p` แล้วคัดลอก `backend-release/` ลงไป แล้ว `docker build` จากโฟลเดอร์นี้ · `rollback_backend.sh` อ่าน `$REL/compose.rollback-backend-followup.yml` | `deploy_backend.sh` สร้างเอง · **ห้ามลบหลัง deploy** |
| `/home/ubuntu/course-advisor-system/` | โปรเจกต์ของ production (`$PROJ`) — อ่าน `.env` และ compose หลัก | มีอยู่แล้ว |
| `/home/ubuntu/course-advisor-system/web/` | รากไฟล์ static ที่ `deploy_web.sh` วางของ (`$WEB`) | มีอยู่แล้ว |
| `/home/ubuntu/course-advisor-system/backups/` | ที่เก็บไฟล์สำรองฐาน (ขั้นที่ 0) | มีอยู่แล้ว |
| `/home/ubuntu/release-*/compose.pin-*.yml` (13 ไฟล์) | `compose-args.txt` อ้างถึงทั้งหมด ตรวจแล้วว่าครบ | มีอยู่แล้ว |

**ย้อนหน้าเว็บต้องใช้โฟลเดอร์ผลของรอบนั้น** — `deploy_web.sh` พิมพ์บรรทัด
`ย้อนกลับด้วย : ./rollback_web.sh --run /home/ubuntu/switch-release-2569-10-28/web-run-<เวลา>`
ตอนจบ · **จดบรรทัดนั้นไว้** ไม่งั้นย้อนหน้าเว็บไม่ได้

**ยังตรวจไม่ได้จากที่นี่ (ต้องอ่านฐาน production)** — สองข้อนี้ `deploy_db.sh` ตรวจเองอยู่แล้ว
และหยุดให้ถ้าไม่ผ่าน จึงไม่ใช่ความเสี่ยงที่ลอยอยู่:

1. คอลัมน์ `provider` ยังไม่มีบนฐาน production (ถ้ามีแล้วแปลว่าเคยลง migration ไปแล้ว)
2. role `advisor_api` อ่านคอลัมน์ใหม่ได้ — สคริปต์ตรวจหลัง migration และ die ถ้าอ่านไม่ได้

**ไฟล์สำรองล่าสุดใน `backups/` คือ 16 ต.ค. (ห่าง 12 วัน)** — ขั้นที่ 0 ข้างล่างจึงเป็น
**ขั้นบังคับ** ไม่ใช่ข้อแนะนำ · `deploy_db.sh` สำรองเฉพาะตาราง `web.ai_settings`
(`web.ai_settings_backup_switch`) ซึ่งไม่ช่วยอะไรถ้าเกิดเรื่องนอกตารางนั้น

---

## 2. ลำดับ deploy — ฐาน → backend → หน้าเว็บ

ทำตามลำดับนี้เท่านั้น เหตุผลอยู่ใน `MODEL_SWITCH` ข้อ 7
(โค้ดใหม่อ่านคอลัมน์ `provider` · หน้าเว็บรุ่นใหม่เรียก `/ai-settings/check` ที่โค้ดเก่าไม่มี)

### ขั้น 0 — สำรองฐานเต็มและตรวจไฟล์สำรอง (**บังคับ ห้ามข้าม**)

```bash
cd /home/ubuntu/course-advisor-system
./scripts/backup_db.sh                      # pg_dump ฐาน course_advisor -> backups/*.sql.gz
BK=$(ls -t backups/course_advisor_*.sql.gz | head -1); echo "$BK"

# ตรวจไฟล์สำรอง — ห้ามไปต่อถ้าข้อใดไม่ผ่าน
gzip -t "$BK"                               # ไฟล์ไม่เสีย (ไม่มี output = ผ่าน)
ls -lh "$BK"                                # ต้องไม่ใช่ขนาดไม่กี่ KB
zcat "$BK" | head -5                        # ต้องขึ้นหัว PostgreSQL database dump
zcat "$BK" | grep -c "CREATE TABLE"         # ต้องได้เลขสองหลักขึ้นไป
zcat "$BK" | grep -c "COPY public.course_chunks"   # ต้องได้ 1
sha256sum "$BK" | tee -a ~/switch-release-2569-10-28/backup-sha256.txt
```

จด path กับ sha256 ของไฟล์สำรองไว้ใน log ของรอบ deploy · ถ้าขั้นใดข้างบนไม่ผ่าน
**หยุด** แล้วแก้เรื่องสำรองก่อน อย่าเริ่มขั้นที่ 1

### อัปชุดขึ้นเซิร์ฟเวอร์

```bash
# จากเครื่องพัฒนา · -c core.autocrlf=false กัน CRLF ทำให้ด่าน sha256sum ล้มทุกไฟล์
git -c core.autocrlf=false archive --format=tar.gz -o /tmp/switch.tar.gz <commit ของชุดปล่อย>
scp -i <ไฟล์กุญแจ> /tmp/switch.tar.gz ubuntu@<IP>:~/

# บนเซิร์ฟเวอร์ — ต้องให้สคริปต์ไปอยู่ที่ /home/ubuntu/switch-release-2569-10-28/ ตรง ๆ
# (ไม่ใช่ลึกลงไปใน docs/raw/... ไม่งั้นโฟลเดอร์ผล db-run-*/web-run-* จะไปโผล่คนละที่
#  กับที่หัวสคริปต์และคำสั่ง rollback เขียนไว้)
rm -rf ~/switch-unpack && mkdir -p ~/switch-unpack && tar xzf ~/switch.tar.gz -C ~/switch-unpack
mkdir -p ~/switch-release-2569-10-28
cp -r ~/switch-unpack/docs/raw/model-switch-2569-10-28/. ~/switch-release-2569-10-28/
chmod +x ~/switch-release-2569-10-28/*.sh

cd /home/ubuntu/switch-release-2569-10-28
ls                                          # ต้องเห็น deploy_*.sh rollback_*.sh backend-release/ web-release/ sql/ compose-args.txt
( cd backend-release && sha256sum -c SHA256SUMS )   # ต้องผ่าน 11/11 ก่อนไปต่อ

./deploy_db.sh        # ขั้น 1
./deploy_backend.sh   # ขั้น 2
./deploy_web.sh       # ขั้น 3
```

### ขั้น 1 — `./deploy_db.sh`

เพิ่มคอลัมน์ `provider` ให้ `web.ai_settings` (DDL ล้วน ไม่แก้ข้อมูลแถวใด)

ด่านที่สคริปต์หยุดเอง: ปฏิเสธถ้า `DATABASE_URL` ไม่ได้ชี้ฐาน production · ข้ามให้ถ้า
คอลัมน์มีอยู่แล้ว · สำรองตารางเป็น `web.ai_settings_backup_switch` ก่อนแก้ · รัน migration
ในทรานแซกชันเดียว · เทียบลายนิ้วมือของแถวก่อน/หลัง ถ้าข้อมูลเปลี่ยนถือว่าล้ม ·
ตรวจว่า `advisor_api` อ่านคอลัมน์ใหม่ได้ · ต้องพิมพ์ `YES` ยืนยันก่อนลงมือ

### ขั้น 2 — `./deploy_backend.sh`

build อิมเมจใหม่โดย **ซ้อน 11 ไฟล์ทับอิมเมจที่ production ใช้อยู่** ไม่ได้ build จากซอร์สทั้งก้อน

ด่านที่สคริปต์หยุดเอง:

1. ตรวจว่า migration ขั้น 1 ลงแล้ว
2. `sha256sum -c SHA256SUMS` ของ 11 ไฟล์
3. อิมเมจฐานต้องเป็นตัวที่คอนเทนเนอร์รันอยู่จริง
4. เทียบ hash ของ **11 ไฟล์ในอิมเมจใหม่** กับชุด
5. รันชุดทดสอบ **8 ไฟล์ในอิมเมจใหม่** บนฐาน `course_advisor_test` — ต้องขึ้น `ผ่านทั้งหมด` ทุกไฟล์
   (`test_model_switch` · `test_local_fallback_gets_time` · `test_llm_usage_counter` ·
   `test_gemini_overload_fallback` · `test_model_outage_n1` · `test_sse_format` ·
   `test_chatweb_stream_budget` · `test_request_budget`)
6. `compose --dry-run` ต้องไม่แตะ postgres / ollama / caddy / frontend / webapi
7. ต้องพิมพ์ `YES` ก่อน restart backend ของ production
8. หลังสลับ: ตรวจว่าคอนเทนเนอร์ใช้อิมเมจใหม่จริง · เทียบ hash ของ 9 ไฟล์ในคอนเทนเนอร์ที่รันอยู่ ·
   **หยุดเมื่อ health ไม่ใช่ 200**

### ขั้น 3 — `./deploy_web.sh`

วางไฟล์ static ของหน้าเว็บ · ตรวจ bundle เดิมที่ rollback ต้องใช้ · วาง assets ให้ครบและ
ตรวจด้วย hash ของไฟล์ที่เว็บเสิร์ฟจริง แล้วค่อยสลับ `index.html` เป็นขั้นสุดท้าย

---

## 3. เกณฑ์ยกเลิกระหว่างทาง

หยุดทันทีและอย่าไปขั้นถัดไป เมื่อ:

* ขั้นที่ 0 ไม่ผ่าน — ไฟล์สำรองเสีย ขนาดผิดปกติ หรือไม่มีตาราง `course_chunks`
* `sha256sum -c` ไม่ผ่านแม้ไฟล์เดียว → ชุดบนเซิร์ฟเวอร์ไม่ตรงกับที่ตรวจ (มักเป็น CRLF ตอนย้ายไฟล์)
* ชุดทดสอบในอิมเมจใหม่ไม่ขึ้น `ผ่านทั้งหมด` แม้ไฟล์เดียว
* `--dry-run` บอกว่าจะแตะบริการอื่นนอกจาก backend
* health ไม่ใช่ 200 หลังสลับอิมเมจ
* ข้อมูลในแถว `web.ai_settings` เปลี่ยนหลัง migration

---

## 4. ทางย้อน

| ย้อนอะไร | คำสั่ง | ผล |
|---|---|---|
| หน้าเว็บ | `./rollback_web.sh --run <โฟลเดอร์ผลของ deploy_web>` | กลับไป bundle เดิม |
| backend | `./rollback_backend.sh` | ตรึงกลับอิมเมจ `followup-2569-10-28` |
| ฐาน | `./rollback_db.sh` | ตัดคอลัมน์ `provider` ทิ้ง |

**ย้อน backend พอ ไม่ต้องย้อนฐาน** — คอลัมน์ `provider` เป็นคอลัมน์ที่โค้ดเก่าไม่รู้จัก
อยู่เฉย ๆ ได้ · ข้อมูลใน `model` / `updated_by` / `updated_at` ไม่ถูกแตะทั้งตอน deploy และตอนย้อน

ย้อนแล้วพฤติกรรมกลับเป็นของ production เดิมทั้งสองงาน — รวมถึงตัวสำรองในเครื่องที่กลับไป
ถูกเพดานเวลาปฏิเสธเหมือนเดิม ซึ่งเป็นสภาพก่อนรอบนี้ ไม่ใช่สภาพที่แย่ลง

`rollback_backend.sh` ต้องมีไฟล์ `compose.rollback-backend-followup.yml` ใน
`/home/ubuntu/release-switch-2569-10-28` ซึ่ง `deploy_backend.sh` คัดลอกไปให้แล้ว
**ห้ามลบโฟลเดอร์นั้นหลัง deploy**

---

## 5. ตรวจหลัง deploy

### 5.1 ตรวจแบบอ่านอย่างเดียว

1. `docker inspect course-advisor-system-backend-1 --format '{{.Config.Image}}'`
   → ต้องเป็น `course-advisor-system-backend:switch-2569-10-28`
2. health ของ backend ต้องเป็น 200
3. หน้าผู้ดูแล → ช่องตั้งค่า AI ต้องแสดง `ที่ใช้จริง = gemini` · ที่มา `env` ·
   `embedding = bge-m3 (เปลี่ยนไม่ได้)` · และ **ไม่มีค่าคีย์โผล่ในคำตอบของเส้นทางนั้น**

### 5.2 ยิงหนึ่งคำถามที่เรียก Gemini จริง (**บังคับ**)

ข้อ 5.1 บอกได้แค่ว่าอิมเมจสลับแล้วและหน้าตั้งค่าอ่านค่าถูก **บอกไม่ได้ว่าระบบยังตอบ
คำถามได้จริง** จึงต้องยิงหนึ่งคำถามที่ต้องอ้างอิงเอกสาร (ไม่ใช่คำถามที่ฐานหลักสูตร
ตอบได้เอง ซึ่งจะได้ `answer_model = null` แล้วดูเหมือนผ่านทั้งที่ไม่เคยแตะโมเดลเลย)

ยิงจากในคอนเทนเนอร์ backend ไปที่ตัวเอง ไม่ผ่านเว็บสาธารณะ:

```bash
docker exec -e PYTHONPATH=/app/backend -w /app/backend \n  course-advisor-system-backend-1 python - <<'EOF'
import httpx
from sqlalchemy import text
from app.core.security import create_access_token
from app.db.session import SessionLocal

with SessionLocal() as db:
    uid = db.execute(text(
        "select id from users where role in ('admin','editor') "
        "and status = 'approved' and is_active order by created_at limit 1")).scalar()

tok = create_access_token(str(uid))
r = httpx.post("http://127.0.0.1:8000/chat",
               headers={"Authorization": f"Bearer {tok}"},
               json={"message": "หลักสูตรวิทยาการคอมพิวเตอร์เรียนเกี่ยวกับอะไร"},
               timeout=60)
d = r.json()
print("HTTP", r.status_code)
print("status       =", d.get("status"))
print("answer_model =", d.get("answer_model"))
print("citations    =", len(d.get("citations") or []))
print("reply[:200]  =", (d.get("reply") or "")[:200])
EOF
```

**เกณฑ์ผ่าน ต้องครบทุกข้อ**

| ตรวจ | ต้องได้ |
|---|---|
| HTTP | `200` |
| `status` | `answered` |
| `answer_model` | ขึ้นต้นด้วย **`gemini:`** เช่น `gemini:gemini-3.5-flash-lite` · ถ้าเป็น `null` แปลว่าไม่ได้เรียกโมเดล (ตอบจากฐานหรือจากแคช) ให้เปลี่ยนคำถามแล้วยิงใหม่ · ถ้าขึ้นต้นด้วย `ollama:` แปลว่าสวิตช์ไม่ได้อยู่ที่ Gemini **ให้ย้อน** |
| `citations` | มากกว่า 0 |
| `reply` | คำตอบที่อ่านรู้เรื่องและอ้างเอกสาร **ไม่ใช่** ข้อความบริการขัดข้อง หรือ "ไม่พบข้อมูลนี้ในเอกสารหลักสูตร" |

**ผลข้างเคียงของการยิงคำถามนี้ ยอมรับได้และคาดไว้แล้ว**: สร้างบทสนทนาหนึ่งรายการใน
`chat_sessions` / `chat_messages` ของ production · อาจเขียนแคชคำตอบหนึ่งแถว ·
ตัวนับ `gemini_ok` เพิ่มราวสองครั้ง (ด่านตรวจหลักฐาน + ขั้นเขียนคำตอบ)

### 5.3 ตัวนับ

```sql
select event, n from public.llm_usage_daily where day = current_date order by event;
```

* `gemini_ok` ต้องเพิ่มขึ้นหลังข้อ 5.2
* `local_primary_*` **ต้องไม่ขึ้น** (ถ้าขึ้นแปลว่ามีคนสลับไป Ollama แล้ว)
* `fallback_local_*` ขึ้นได้ถ้า Gemini สะดุดชั่วคราว — ดูคู่กัน ถ้า `ok` ขยับแปลว่า
  patch ทำงาน ถ้า `failed` เท่ากับ `attempt` ตลอดแปลว่ายังถูกเพดานเวลาปฏิเสธ

### 5.4 เรื่องที่คาดไว้แล้ว

คำถามชุดแรกหลัง deploy จะช้ากว่าปกติ เพราะตัวระบุรุ่นของแคชรวมชื่อโมเดลเข้าไปด้วย
แคชเดิมจึงกลายเป็นของรุ่นเก่าทั้งหมดครั้งเดียว — **ไม่ใช่อาการผิดปกติ**

---

## 6. สิ่งที่แก้ในชุดระหว่างเตรียมรอบนี้

ตรวจชุดเทียบกับ PR #2 แล้วพบว่า `deploy_backend.sh` **ยังไม่ได้ใส่ชุดทดสอบของ patch
ตัวสำรองเข้าไปในลูปที่รันในอิมเมจใหม่** (ลูปมี 7 ไฟล์ ทั้งที่เอกสารระบุว่า 8) และ
`test_local_fallback_gets_time.py` **ไม่พิมพ์คำว่า `ผ่านทั้งหมด`** ซึ่งเป็นคำที่
`deploy_backend.sh` ใช้ grep ตัดสินว่าชุดไหนผ่าน — ถ้าปล่อยไว้ ด่านขั้นที่ 5 จะ
**ล้มทั้งที่ชุดทดสอบผ่าน** แก้แล้วทั้งสองจุด และสร้าง `SHA256SUMS` ใหม่ (ผ่าน 11/11)
