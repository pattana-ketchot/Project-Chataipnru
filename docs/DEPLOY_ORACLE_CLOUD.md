# คู่มือนำระบบขึ้น Oracle Cloud

สำหรับ Oracle Cloud Infrastructure แพ็กเกจ **Always Free** ซึ่งให้เครื่อง ARM Ampere
สูงสุด 4 คอร์ RAM 24GB และดิสก์ 200GB โดยไม่มีค่าใช้จ่าย

> **เข้าใจก่อนเริ่ม: แพ็กเกจฟรีไม่มีการ์ดจอ** โมเดลจะทำงานบน CPU ซึ่งช้ากว่าเครื่องที่มี
> การ์ดจอมาก คาดว่าคำตอบใช้เวลาหลายสิบวินาทีต่อคำถาม เหมาะกับการเปิดให้กรรมการหรือ
> ผู้สนใจเข้าดูได้ตลอดเวลา ส่วนการสาธิตสดควรใช้เครื่องที่มีการ์ดจอ

---

## ขั้นที่ 1 — สร้างเครื่องบน Oracle Cloud

ส่วนนี้ต้องทำเองผ่านหน้าเว็บ เพราะต้องยืนยันตัวตนและผูกบัตรเครดิต
(Oracle เรียกเก็บประมาณ 1 ดอลลาร์เพื่อยืนยันแล้วคืนให้)

**ตั้งค่าเครื่อง**

| หัวข้อ | ค่าที่ใช้ |
|---|---|
| Shape | `VM.Standard.A1.Flex` (ARM Ampere) |
| OCPU / RAM | 4 คอร์ / 24GB (เพดานของแพ็กเกจฟรี) |
| Image | Ubuntu 22.04 หรือใหม่กว่า |
| Boot volume | 100–200GB |
| SSH key | สร้างใหม่แล้ว**เก็บไฟล์กุญแจส่วนตัวไว้ให้ดี** ถ้าหายจะเข้าเครื่องไม่ได้อีก |

> **หาเครื่องว่างยาก** ARM ในแพ็กเกจฟรีมักขึ้น "Out of capacity" ต้องลองซ้ำหลายครั้ง
> หรือเปลี่ยน availability domain **อย่ารอทำใกล้วันสอบ**

**เปิดพอร์ตฝั่งคลาวด์**

ไปที่ VCN → Security List ของ subnet ที่เครื่องอยู่ แล้วเพิ่ม Ingress Rule

| ช่อง | ค่า |
|---|---|
| Source CIDR | `0.0.0.0/0` |
| IP Protocol | TCP |
| Destination Port Range | `80` |

---

## ขั้นที่ 2 — ติดตั้งระบบ

เข้าเครื่องด้วย SSH แล้วรัน

```bash
sudo apt update && sudo apt install -y git
```

```bash
git clone https://github.com/popoza11874/Project-Chataipnru.git && cd Project-Chataipnru
```

```bash
bash scripts/setup_server.sh
```

สคริปต์จะติดตั้ง Docker, เปิดพอร์ตใน iptables, สร้าง `.env` พร้อมรหัสผ่านสุ่ม,
build ทุกส่วน แล้วดึงโมเดล

**ครั้งแรกจะให้ออกจากระบบแล้วเข้าใหม่** หลังติดตั้ง Docker เสร็จ เพราะต้องให้สิทธิ์
ผู้ใช้ปัจจุบันสั่ง docker ได้ จากนั้นรันสคริปต์ซ้ำอีกครั้ง

รวมเวลาทั้งหมดประมาณ **20–40 นาที** ส่วนใหญ่หมดไปกับการ build และดึงโมเดล 6GB

---

## ขั้นที่ 3 — นำข้อมูลขึ้นเซิร์ฟเวอร์

ระบบที่เพิ่งติดตั้งมีฐานข้อมูลว่าง ต้องนำข้อมูลหลักสูตรขึ้นไป

> **ห้ามใช้วิธี ingest ใหม่บนเซิร์ฟเวอร์** การสร้างเวกเตอร์ให้ 7,301 ส่วนข้อความ
> บนเครื่องที่ไม่มีการ์ดจอใช้เวลาหลายชั่วโมง ขณะที่การกู้จากไฟล์สำรองใช้เวลาไม่กี่นาที
> เพราะไฟล์สำรองมีเวกเตอร์ที่คำนวณไว้แล้ว

**บนเครื่องพัฒนา** สร้างไฟล์สำรองก่อน

```bash
bash scripts/backup_db.sh
```

**ส่งไฟล์ขึ้นเซิร์ฟเวอร์** (แทน `<ไฟล์>` และ `<IP>` ด้วยของจริง)

```bash
scp -i <ไฟล์กุญแจ> backups/<ไฟล์>.sql.gz ubuntu@<IP>:~/Project-Chataipnru/backups/
```

**บนเซิร์ฟเวอร์** กู้ข้อมูล

```bash
gunzip -c backups/<ไฟล์>.sql.gz | docker compose -f docker-compose.prod.yml exec -T postgres psql -U postgres -d course_advisor
```

**ตรวจว่าข้อมูลครบ**

```bash
docker compose -f docker-compose.prod.yml exec -T postgres psql -U postgres -d course_advisor -c "SELECT (SELECT count(*) FROM courses) AS courses, (SELECT count(*) FROM course_chunks) AS chunks;"
```

ต้องได้ **18 หลักสูตร และ 7,301 ส่วนข้อความ**

**สร้างดัชนีค้นหาใหม่** เพราะดัชนีถูกสร้างตอนตารางยังว่าง

```bash
docker compose -f docker-compose.prod.yml exec -T postgres psql -U postgres -d course_advisor -c "REINDEX INDEX idx_course_chunks_embedding; ANALYZE course_chunks;"
```

---

## ขั้นที่ 4 — ทดสอบ

เปิดเว็บที่ `http://<IP ของเครื่อง>` แล้วสมัครสมาชิกและลองถามคำถาม

**คำถามแรกจะช้ามาก** เพราะต้องโหลดโมเดลเข้าหน่วยความจำก่อน หลังจากนั้นระบบจะยิง
คำขอเล็กๆ ทุก 20 นาทีเพื่อไม่ให้โมเดลถูกถอดออก

ตรวจจากฝั่งเซิร์ฟเวอร์ว่าตอบได้จริง

```bash
curl -s http://localhost/api/health
```

---

## ถ้าเข้าเว็บไม่ได้

ไล่ตรวจตามลำดับ เพราะ Oracle ปิดพอร์ตไว้ **สองชั้น** และคนมักลืมชั้นใดชั้นหนึ่ง

| ตรวจอะไร | คำสั่ง / ที่ดู |
|---|---|
| ระบบทำงานอยู่ไหม | `docker compose -f docker-compose.prod.yml ps` |
| เว็บตอบจากในเครื่องไหม | `curl -I http://localhost` |
| iptables เปิดพอร์ต 80 ไหม | `sudo iptables -L INPUT -n --line-numbers \| head` |
| Security List เปิดไหม | หน้าเว็บ Oracle → VCN → Security List |

ถ้า `curl` จากในเครื่องได้แต่จากข้างนอกไม่ได้ แปลว่าติดที่ firewall ชั้นใดชั้นหนึ่ง

---

## การดูแลหลังติดตั้ง

**ดู log**

```bash
docker compose -f docker-compose.prod.yml logs -f backend
```

**อัปเดตโค้ดใหม่**

```bash
git pull && docker compose -f docker-compose.prod.yml up -d --build
```

**สำรองข้อมูลจากเซิร์ฟเวอร์**

```bash
BACKUP_DIR=backups docker compose -f docker-compose.prod.yml exec -T postgres pg_dump -U postgres -d course_advisor --clean --if-exists | gzip > backups/oci_$(date +%Y%m%d).sql.gz
```

---

## ข้อควรรู้

**ถ้าคำตอบช้าเกินรับได้** ลองเปลี่ยนเป็นโมเดลเล็กลงโดยแก้ `LLM_MODEL` ใน `.env`
เป็น `qwen2.5:3b` แล้วดึงโมเดลใหม่และรีสตาร์ท backend
**ต้องรันชุดประเมิน 109 คำถามใหม่ทั้งหมด** เพื่อดูว่าคุณภาพคำตอบตกลงหรือไม่

**เครื่องในแพ็กเกจฟรีอาจถูกเรียกคืน** ถ้าไม่ได้ใช้งานเลยเป็นเวลานาน Oracle มีนโยบาย
เรียกคืนทรัพยากรที่ไม่ได้ใช้ ควรเข้าใช้งานเป็นระยะ

**สำรองข้อมูลเก็บไว้นอกเครื่องด้วยเสมอ** อย่าเก็บไฟล์สำรองไว้บนเครื่องเดียวกับฐานข้อมูล
