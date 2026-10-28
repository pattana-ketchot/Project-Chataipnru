# Runbook: deploy ชุดสวิตช์เลือกโมเดล + patch กันเวลาให้ตัวสำรอง

ชุดที่จะ deploy คือ PR #2 (`feature/model-switch-fallback-budget`)
**ยังไม่ merge · ยังไม่ deploy · ยังไม่เปลี่ยนค่าใดของ production จนกว่าจะอนุมัติ**

เอกสารนี้เป็นลำดับปฏิบัติพร้อมด่านหยุดและทางย้อน · รายละเอียดของงานอยู่ใน
`SWITCH_PLUS_FALLBACK_READINESS_2569-10-28.md` · ที่มาของตัวเลขอยู่ใน
`MODEL_SWITCH_2569-10-28.md` และ `LOCAL_FALLBACK_FIX_2569-10-28.md`

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

**สองโฟลเดอร์ชื่อคล้ายกันมาก อย่าสลับ**

* `/home/ubuntu/switch-release-2569-10-28/` — **ที่วางชุดที่อัปขึ้นไป** (คนทำเป็นคนสร้าง)
* `/home/ubuntu/release-switch-2569-10-28/` — **บริบท build + ที่เก็บ compose pin**
  (`deploy_backend.sh` สร้างเองด้วย `mkdir -p` แล้วคัดลอก `backend-release/` ลงไป)
  `rollback_backend.sh` อ่านไฟล์ rollback จากโฟลเดอร์นี้ **ห้ามลบทิ้งหลัง deploy**

**ยังตรวจไม่ได้จากที่นี่ (ต้องอ่านฐาน production)** — สองข้อนี้ `deploy_db.sh` ตรวจเองอยู่แล้ว
และหยุดให้ถ้าไม่ผ่าน จึงไม่ใช่ความเสี่ยงที่ลอยอยู่:

1. คอลัมน์ `provider` ยังไม่มีบนฐาน production (ถ้ามีแล้วแปลว่าเคยลง migration ไปแล้ว)
2. role `advisor_api` อ่านคอลัมน์ใหม่ได้ — สคริปต์ตรวจหลัง migration และ die ถ้าอ่านไม่ได้

**ข้อแนะนำ**: สำรองฐานเต็มก่อนเริ่ม ไฟล์ล่าสุดใน `backups/` คือ 16 ต.ค. (ห่าง 12 วัน)
แม้ migration นี้จะเป็น DDL ล้วนบนตารางเดียวและ `deploy_db.sh` สำรองตารางนั้นให้อีกชั้น
(`web.ai_settings_backup_switch`)

---

## 2. ลำดับ deploy — ฐาน → backend → หน้าเว็บ

ทำตามลำดับนี้เท่านั้น เหตุผลอยู่ใน `MODEL_SWITCH` ข้อ 7
(โค้ดใหม่อ่านคอลัมน์ `provider` · หน้าเว็บรุ่นใหม่เรียก `/ai-settings/check` ที่โค้ดเก่าไม่มี)

```bash
# อัปชุดขึ้นเซิร์ฟเวอร์ (ทำจากเครื่องพัฒนา · -c core.autocrlf=false กัน CRLF)
git -c core.autocrlf=false archive --format=tar.gz -o /tmp/switch.tar.gz <commit ของ PR #2>
scp -i <ไฟล์กุญแจ> /tmp/switch.tar.gz ubuntu@<IP>:~/

# บนเซิร์ฟเวอร์
mkdir -p ~/switch-release-2569-10-28 && tar xzf ~/switch.tar.gz -C ~/switch-release-2569-10-28
cd ~/switch-release-2569-10-28/docs/raw/model-switch-2569-10-28
( cd backend-release && sha256sum -c SHA256SUMS )     # ต้องผ่าน 11/11 ก่อนไปต่อ

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

## 5. ตรวจหลัง deploy (อ่านอย่างเดียว ไม่ต้องยิงคำถามใส่เว็บจริง)

1. `docker inspect course-advisor-system-backend-1 --format '{{.Config.Image}}'`
   → ต้องเป็น `course-advisor-system-backend:switch-2569-10-28`
2. health ของ backend ต้องเป็น 200
3. หน้าผู้ดูแล → ช่องตั้งค่า AI ต้องแสดง `ที่ใช้จริง = gemini` · ที่มา `env` ·
   `embedding = bge-m3 (เปลี่ยนไม่ได้)` · และ **ไม่มีค่าคีย์โผล่ในคำตอบของเส้นทางนั้น**
4. ตัวนับของวันนั้น: `gemini_ok` ยังเพิ่มตามปกติ และ `local_primary_*` ไม่ขึ้น
   (ถ้าขึ้นแปลว่ามีคนสลับไป Ollama แล้ว)

```sql
select event, n from public.llm_usage_daily where day = current_date order by event;
```

5. คำถามชุดแรกหลัง deploy จะช้ากว่าปกติ เพราะตัวระบุรุ่นของแคชรวมชื่อโมเดลเข้าไปด้วย
   แคชเดิมจึงกลายเป็นของรุ่นเก่าทั้งหมดครั้งเดียว — **คาดไว้แล้ว ไม่ใช่อาการผิดปกติ**

---

## 6. สิ่งที่แก้ในชุดระหว่างเตรียมรอบนี้

ตรวจชุดเทียบกับ PR #2 แล้วพบว่า `deploy_backend.sh` **ยังไม่ได้ใส่ชุดทดสอบของ patch
ตัวสำรองเข้าไปในลูปที่รันในอิมเมจใหม่** (ลูปมี 7 ไฟล์ ทั้งที่เอกสารระบุว่า 8) และ
`test_local_fallback_gets_time.py` **ไม่พิมพ์คำว่า `ผ่านทั้งหมด`** ซึ่งเป็นคำที่
`deploy_backend.sh` ใช้ grep ตัดสินว่าชุดไหนผ่าน — ถ้าปล่อยไว้ ด่านขั้นที่ 5 จะ
**ล้มทั้งที่ชุดทดสอบผ่าน** แก้แล้วทั้งสองจุด และสร้าง `SHA256SUMS` ใหม่ (ผ่าน 11/11)
