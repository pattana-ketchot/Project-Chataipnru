# M3 — ผลการตรวจและปรับปรุง Deployment Runbook

> ตรวจแบบ **READ-ONLY** และแก้เฉพาะเอกสาร · ไม่ deploy ไม่ restart ไม่แก้ `.env` ไม่แก้รหัสผ่านฐานข้อมูล ไม่เขียนฐานข้อมูลหรือ Supabase ไม่ push/merge

## ผลสรุป

# `M3_RUNBOOK_REVISED`

ตรวจพบข้อผิดพลาด **2 จุดที่จะทำให้ตีความผลผิด** และช่องโหว่การตรวจสอบ **1 จุดที่ร้ายแรง** แก้ครบแล้วทั้งหมด

| # | งาน | ผล |
|---|---|---|
| 1 | แก้คำสั่งเพิ่ม `ADVISOR_WEB_PASSWORD` เป็น if/else + ตรวจ hex 64 | **แก้แล้ว** |
| 2 | เพิ่มขั้นตอนตรวจการเชื่อมต่อ PostgreSQL ด้วย `advisor_web` | **เพิ่มแล้ว — ข้อ 4.0** |
| 3 | ตรวจว่า health check ทดสอบการเชื่อมต่อจริงหรือแค่ดู configuration | **ตรวจแล้ว — แค่ดู configuration** |
| 4 | Rollback บังคับ recreate เฉพาะ webapi + ยืนยัน image ID | **แก้แล้ว** |
| 5 | ตรวจพฤติกรรม `sci-connect-news-detail` และแก้ smoke test | **แก้แล้ว — เดิมคาดหวังผิด** |
| 6 | ตรวจว่า compose ใหม่ไม่กระทบบริการอื่น | **ตรวจแล้ว — ไม่กระทบ** |
| 7 | GO/NO-GO กรณี PostgreSQL authentication ไม่ผ่าน | **เพิ่มแล้ว 3 กรณี** |
| 8 | รายงาน | เอกสารฉบับนี้ |

Runbook เดิม 412 บรรทัด → **550 บรรทัด**

---

## 1. `ADVISOR_WEB_PASSWORD` — เปลี่ยนเป็น if/else และตรวจ hex จริง

### เดิม

```bash
[ ${#AWP} -eq 64 ] && grep -q '^ADVISOR_WEB_PASSWORD=' .env && echo 'มีอยู่แล้ว' || { [ ${#AWP} -eq 64 ] && printf ... >> .env; }
```

### ปัญหา

| ข้อ | รายละเอียด |
|---|---|
| ตรวจแค่ความยาว | `${#AWP} -eq 64` ผ่านได้ด้วยอะไรก็ได้ที่ยาว 64 — ตัวพิมพ์ใหญ่ ช่องว่าง อักขระพิเศษ หรือค่าที่ไม่ใช่ hex เลย |
| โซ่ `&&`/`\|\|` อ่านยาก | ต้องเขียนเงื่อนไข `${#AWP} -eq 64` **ซ้ำสองที่** ถ้าแก้ที่เดียวจะไม่ตรงกัน |
| ลำดับการตีความ | `A && B \|\| C` ถ้า `B` ล้มจะไป `C` ซึ่งไม่ใช่เจตนาเสมอไป |

### ใหม่

```bash
if [[ ! "$AWP" =~ ^[0-9a-f]{64}$ ]]; then
  echo 'ไม่ผ่าน: ต้องเป็นเลขฐานสิบหกตัวพิมพ์เล็ก 64 ตัวเท่านั้น — ไม่เขียนอะไรทั้งสิ้น'
elif grep -q '^ADVISOR_WEB_PASSWORD=' .env; then
  echo 'มีคีย์นี้อยู่แล้ว — ไม่เขียนทับ'
else
  printf 'ADVISOR_WEB_PASSWORD=%s\n' "$AWP" >> .env
  echo 'เพิ่มแล้ว'
fi
```

| สิ่งที่ดีขึ้น | เหตุผล |
|---|---|
| ตรวจ **ชุดอักขระ** ไม่ใช่แค่ความยาว | `^[0-9a-f]{64}$` จับช่องว่างติดมา ตัวพิมพ์ใหญ่ และค่าที่ไม่ใช่ hex |
| **ไม่ส่งค่าผ่าน pipe และไม่เข้า argv** | ใช้ `[[ =~ ]]` ในตัว bash — ไม่มี subprocess จึงไม่โผล่ใน `ps` ต่างจากการ `echo "$AWP" \| grep` |
| แต่ละกรณีมีทางออกเดียว | อ่านแล้วรู้ทันทีว่าเกิดอะไรได้บ้าง 3 กรณี |
| เขียนเงื่อนไขครั้งเดียว | ไม่มีโอกาสแก้ไม่ครบ |

**ยืนยัน:** ไม่มีคำสั่ง `ALTER ROLE` อยู่ที่ใดในเอกสารทั้งสองฉบับ — ขั้นนี้เพียงบันทึกค่าที่ตั้งไว้แล้วตอน provision ลง `.env`

---

## 2 และ 3. ช่องโหว่ที่ร้ายแรงที่สุดที่พบ — `/healthz` พิสูจน์การเชื่อมต่อไม่ได้

### สิ่งที่ตรวจพบ

อ่าน `server.mjs:149-168` และ `db.mjs:145-200` แล้วยืนยันว่า **`/healthz` ไม่ยิง query ไปฐานข้อมูลเลย**

| ค่าที่คืนมา | ความหมายจริง |
|---|---|
| `status: "ok"` | HTTP server รับคำขอได้ · **จงใจไม่ให้ขึ้นกับฐานข้อมูล** |
| `dbConfigured: true` | **แค่มีค่า env ครบ** — ไม่ได้แปลว่ารหัสผ่านถูกหรือต่อติด |
| `db: "unknown"` | ยังไม่มีใครเรียก resolver ตั้งแต่คอนเทนเนอร์ขึ้น |

โค้ดอธิบายเหตุผลไว้เอง — Docker HEALTHCHECK มี timeout 5 วินาที ถ้า `/healthz` ไปรอฐานข้อมูลที่ค้าง คอนเทนเนอร์จะถูกตัดสินว่า unhealthy ทั้งที่เส้นทางสาธารณะสองเส้นทางยังทำงานได้และไม่ได้ใช้ฐานข้อมูล **เป็นการออกแบบที่ถูกต้อง ไม่ใช่ข้อบกพร่อง**

`db` เปลี่ยนเป็น `"up"`/`"down"` เฉพาะเมื่อมีการเรียก resolver จริง ซึ่งเกิดเฉพาะตอน**เขียนข้อมูล** (`authorFieldsFor` → `resolveAuthorId`)

### ทำไมเรื่องนี้ร้ายแรง

Runbook ฉบับแรกตั้งเงื่อนไขผ่านไว้ว่า `dbConfigured: true` และ `db` ไม่ใช่ `not-configured`

**ทั้งสองเงื่อนไขนั้นผ่านได้แม้รหัสผ่านจะผิด** เพราะ `dbConfigured` ดูแค่ว่ามีค่า env และ `db` จะเป็น `"unknown"` ซึ่งก็ไม่ใช่ `not-configured`

> deploy ด้วยรหัสผ่านผิดจะผ่าน smoke test **ทุกข้อ** โดยไม่มีอะไรฟ้อง แล้วไปพังตอนผู้ดูแลกดบันทึกข้อมูลจริงครั้งแรก ซึ่งตอนนั้นเราจะไม่รู้แล้วว่าพังเพราะอะไร

### สิ่งที่เพิ่ม — ข้อ 4.0 ตรวจการเชื่อมต่อจริง

รัน **ในคอนเทนเนอร์ webapi** เพื่อใช้ค่า env ชุดเดียวกับของจริง แล้วเรียก resolver ด้วย UUID ที่เป็นศูนย์ทั้งหมด

| ผลที่ได้ | แปลว่า |
|---|---|
| `ACCOUNT_NOT_LINKED` + `status: up` | **ผ่าน** — ต่อติด รหัสผ่านถูก มีสิทธิ์อ่าน `public.users` จริง |
| `IDENTITY_LOOKUP_FAILED` + `status: down` | **ไม่ผ่าน** — ต่อไม่ได้ รหัสผ่านผิด หรือไม่มีสิทธิ์ |

เหตุผลที่แยกแยะได้แม่น — `resolveLocalUser` ตั้ง `lastOutcome = "up"` **หลัง query สำเร็จ** และตั้ง `"down"` ใน `catch` ดังนั้นการได้ `ACCOUNT_NOT_LINKED` แปลว่า query วิ่งผ่านจริงแล้วคืน 0 แถว ไม่ใช่ล้มกลางทาง

### ความปลอดภัยของคำสั่งตรวจ

| ข้อกังวล | คำตอบ |
|---|---|
| แสดงรหัสผ่าน | **ไม่** — `describe()` คืนแค่ `user@host:port/database` และ `createDatabase` ตั้ง `config.password` เป็น `undefined` ไว้แล้ว |
| เปลี่ยนรหัสผ่าน | **ไม่** — อ่านจาก env ที่มีอยู่ ไม่มี `ALTER ROLE` |
| เขียนฐานข้อมูล | **ไม่** — `RESOLVER_SQL` เป็น `SELECT` ล้วน |
| ใช้ UUID ของคนจริง | **ไม่** — ใช้ `00000000-…-000000000000` ที่ไม่มีอยู่จริง จงใจให้คืน 0 แถว |
| หลงไปเจอ `trust` ของ `pg_hba` | **ไม่** — รันจากคอนเทนเนอร์ `webapi` ต่อผ่าน network ไปที่ host `postgres` ไม่ใช่ `127.0.0.1` จึงถูกบังคับยืนยันรหัสผ่านจริง (กับดักจากรอบ provision) |

---

## 4. Rollback — บังคับ recreate และยืนยัน image ID

### ปัญหาของฉบับเดิม

```bash
docker tag course-advisor-system-webapi:rollback-pre-m3 course-advisor-system-webapi:latest
docker compose ... up -d --no-deps webapi
```

| ปัญหา | ผลที่ตามมา |
|---|---|
| `docker tag` เปลี่ยนแค่**ชื่อ** | คอนเทนเนอร์ที่รันอยู่ยังผูกกับ **image ID ของรอบ M3** ไม่ได้เปลี่ยนตามชื่อ |
| compose อาจมองว่า "ไม่มีอะไรเปลี่ยน" | ถ้า config hash เหมือนเดิม `up -d` **อาจไม่ทำอะไรเลย** |
| ไม่มีการยืนยันผล | เข้าใจผิดว่าย้อนสำเร็จทั้งที่ยังรันของใหม่อยู่ — **อันตรายที่สุดในสถานการณ์ฉุกเฉิน** |

### ที่แก้แล้ว

```bash
EXPECT=$(docker image inspect course-advisor-system-webapi:rollback-pre-m3 --format '{{.Id}}')
docker tag course-advisor-system-webapi:rollback-pre-m3 course-advisor-system-webapi:latest
cp ~/m3-backup-compose-<TS>.yml docker-compose.prod.yml
docker compose -f docker-compose.prod.yml up -d --no-deps --force-recreate webapi

ACTUAL=$(docker inspect course-advisor-system-webapi-1 --format '{{.Image}}')
[ "$EXPECT" = "$ACTUAL" ] && echo "ย้อนกลับสำเร็จ" || echo "!! ยังไม่ใช่ image เดิม อย่าเพิ่งวางมือ"
```

| สิ่งที่เพิ่ม | ทำอะไร |
|---|---|
| `--force-recreate` | บังคับสร้างคอนเทนเนอร์ใหม่แม้ compose จะคิดว่าไม่มีอะไรเปลี่ยน |
| `--no-deps` (คงไว้) | ไม่ให้ไป restart `postgres` ที่ backend ใช้อยู่ |
| เทียบ `EXPECT` กับ `ACTUAL` | **ยืนยันด้วยหลักฐาน** ไม่ใช่สันนิษฐาน |
| คืน compose เดิม (คงไว้) | compose ใหม่บังคับว่าต้องมี `ADVISOR_WEB_PASSWORD` |

---

## 5. `sci-connect-news-detail` — smoke test เดิมคาดหวังผิด

### สิ่งที่ตรวจพบ

อ่าน `api/sci-connect-news-detail.js` แล้วพบพฤติกรรมจริง

| กรณี | ผลจริง |
|---|---|
| ไม่ส่ง `slug` | **400** `missing slug` |
| `slug` ไม่มีในฐานข้อมูล | **404** `ไม่พบข่าวนี้` (ใช้ `.maybeSingle()`) |
| `slug` มีจริง | **200** |
| ฝั่ง Supabase ผิดพลาด | 502 |

### ปัญหา

Runbook ฉบับแรกเขียนว่า

```bash
curl ... 'https://.../api/sci-connect-news-detail?slug=test'   # คาดหวัง 200
```

`slug=test` เป็นค่าสมมติที่แทบแน่นอนว่าไม่มีในฐานข้อมูล → **จะได้ 404 เสมอ** แล้วถูกตีความว่า deploy พัง ทั้งที่ระบบทำงานถูกต้องทุกอย่าง

เอกสารต้นทางก็ระบุไว้เองว่า slug ที่เก่าจนถูกตัดออกไปแล้วจะคืน not-found

### ที่แก้แล้ว

```bash
# ไม่ส่ง slug -> ต้องได้ 400
curl ... 'https://.../api/sci-connect-news-detail'

# slug ไม่มีจริง -> ต้องได้ 404
curl ... 'https://.../api/sci-connect-news-detail?slug=ไม่มีสลักนี้จริง'

# slug จริง: ดึงจากรายการข่าวก่อน แล้วค่อยยิง -> ต้องได้ 200
SLUG=$(curl -s https://.../api/sci-connect-news | sed -n 's/.*"slug":"\([^"]*\)".*/\1/p' | head -1)
[ -n "$SLUG" ] && curl ... "https://.../api/sci-connect-news-detail?slug=$SLUG"
```

ดีกว่าเดิมสามทาง — ทดสอบ **ทั้งสามเส้นทางของ endpoint** ไม่ใช่แค่ทางเดียว · ใช้ slug จริงจึงเป็นการทดสอบแบบต่อเนื่องถึง Supabase จริง · และถ้าไม่มีข่าวในระบบเลยก็จะพิมพ์บอก ไม่ใช่เงียบแล้วล้มเหลวให้ตีความผิด

---

## 6. compose ใหม่ไม่กระทบบริการอื่น — ตรวจแล้ว

เทียบทั้งไฟล์ (ตัดคอมเมนต์และบรรทัดว่าง · ลบ `\r` ก่อนเพราะของบนเซิร์ฟเวอร์เป็น CRLF)

**ความต่างทั้งหมดอยู่ใน service `webapi` เท่านั้น** — เพิ่ม `depends_on` และเพิ่ม env 5 ตัว

| รายการ | ผล |
|---|---|
| รายชื่อ service | เหมือนกันทุกตัว |
| volume | เหมือนกันทุกตัว |
| `postgres` `ollama` `backend` `frontend` `caddy` | **ไม่เปลี่ยนแม้แต่บรรทัดเดียว** |
| `db-viewer` | ไม่ได้อยู่ใน compose นี้ ไม่ถูกกระทบ |

### ความเสี่ยงที่เกิดจาก `depends_on` และการจัดการ

การเพิ่ม `depends_on: postgres (condition: service_healthy)` เปลี่ยนกราฟการพึ่งพา ถ้าสั่ง `up -d` โดยไม่ใส่ `--no-deps` compose อาจไปแตะ `postgres` ที่ backend ใช้อยู่

**ทุกคำสั่ง `up` ในเอกสารจึงใส่ `--no-deps` เสมอ** ทั้งตอน deploy และตอน rollback

ตรวจแล้วว่าเงื่อนไขนี้ใช้ได้จริง — `postgres` บน production **มี healthcheck อยู่แล้ว** (`pg_isready -U postgres -d course_advisor` ทุก 10 วินาที) และสถานะปัจจุบัน `healthy` ขึ้นมา 7 สัปดาห์ · ถ้าไม่มี healthcheck เงื่อนไข `service_healthy` จะทำให้ compose ปฏิเสธไม่ยอมขึ้นเลย

---

## 7. GO / NO-GO สำหรับ PostgreSQL authentication

เพิ่ม 3 กรณีเข้าตาราง NO-GO

| อาการ | ทำอะไร |
|---|---|
| ข้อ 4.0 ได้ `password authentication failed` | **rollback ทันที** — รหัสผ่านใน `.env` ไม่ตรงกับของ role · **ห้ามแก้รหัสผ่านใน PostgreSQL เพื่อให้ผ่าน** ต้องหาค่าที่ถูกมาใส่ `.env` แทน |
| ข้อ 4.0 ได้ `permission denied` (`42501`) | **rollback** — grant ของ role เปลี่ยนไปจากที่ตรวจไว้ |
| ข้อ 4.0 ได้ timeout หรือ `ECONNREFUSED` | **rollback** — `depends_on` หรือ network ไม่ถูกต้อง |

ข้อแรกสำคัญเป็นพิเศษ — ทางลัดที่ดูง่ายที่สุดตอนเจอปัญหาคือ `ALTER ROLE advisor_web PASSWORD ...` ให้ตรงกับที่พิมพ์ไป **ซึ่งเป็นการเขียน production database และห้ามเด็ดขาด** ทางที่ถูกคือหาค่าที่ตั้งไว้ตอน provision มาใส่ `.env`

---

## 8. สรุปสิ่งที่เปลี่ยนใน Runbook

| หัวข้อ | เดิม | ใหม่ |
|---|---|---|
| 1.5 | ไม่มี | **เพิ่ม** — ผลเทียบ compose ทั้งไฟล์ + ข้อควรระวัง `depends_on` |
| 2.2 NO-GO | 9 อาการ | **12 อาการ** (+3 กรณี authentication) |
| 3.2 รหัสผ่าน | โซ่ `&&`/`\|\|` ตรวจความยาว | **if/elif/else + ตรวจ hex 64** |
| 4.0 | ไม่มี | **เพิ่ม** — ตรวจการเชื่อมต่อจริง พร้อมคำอธิบายว่าทำไม `/healthz` ไม่พอ |
| 4 ตารางทดสอบ | 10 ข้อ | **11 ข้อ** (+ข้อ 2.5 ตรวจการเชื่อมต่อ) |
| 4 ข้อ 2 | `db` ไม่ใช่ `not-configured` | **`db: "unknown"` ถือว่าปกติ** |
| 4 ข้อ 4 | คาดหวัง 200 จาก slug สมมติ | **400 / 404 / 200 ครบสามกรณี ใช้ slug จริง** |
| 5.1 Rollback | `up -d --no-deps` | **`--force-recreate` + ยืนยัน image ID** |

**412 → 550 บรรทัด**

---

## 9. ยืนยันขอบเขต

| ข้อห้าม | สถานะ |
|---|---|
| Deploy / Restart production | **ไม่ได้ทำ** |
| แก้ production `.env` หรือรหัสผ่านฐานข้อมูล | **ไม่ได้ทำ** — อ่านเฉพาะชื่อคีย์ · ไม่มี `ALTER ROLE` ที่ใดในเอกสาร |
| เขียน production database / Supabase | **ไม่ได้ทำ** — ใช้ `SELECT` อย่างเดียว |
| Push / Merge | **ไม่ได้ทำ** |
| แก้ frontend repository | **ไม่ได้ทำ** |
| แสดง password / token / UUID / ข้อมูลส่วนบุคคล | **ไม่มี** — UUID เดียวในเอกสารคือ `00000000-…-000000000000` ซึ่งเป็นค่าทดสอบที่ไม่มีอยู่จริง |

### สถานะตอนปิดงาน

```
Local HEAD        427ce19 · mko-phase2 · ahead of origin 7 · ไม่ได้ commit ในรอบนี้
Production webapi course-advisor-system-webapi:latest + :rollback-pre-m3 (1163e36361d9)
คอนเทนเนอร์        Up (healthy) — ไม่ถูกแตะ
webapi/api/       10 ไฟล์ — ไม่ถูกแตะ
```

**รออนุมัติ deploy แยกต่างหาก**
