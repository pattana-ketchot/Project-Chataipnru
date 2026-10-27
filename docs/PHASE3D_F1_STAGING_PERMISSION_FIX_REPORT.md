# Phase 3D — F1 Staging PDF Permission Fix

| | |
|---|---|
| วันที่ | 2026-09-29 → 30 · ช่วงทำงาน **23:06–23:40 UTC** (ไทย 2026-09-30 ราว 06:06–06:40) |
| ขอบเขต | แก้ข้อบกพร่อง F1 เท่านั้น · เพิ่มชุดตรวจ · รัน regression · รัน isolated E2E |
| สถานที่รัน | เครื่อง Windows ของผู้พัฒนา · Docker Desktop 29.7.2 · compose project `sci-advisor-e2e` |
| Production | **READ-ONLY baseline verification เท่านั้น — ไม่ deploy ไม่ restart ไม่แตะข้อมูล** |
| ไฟล์ที่แก้ | `pipeline/crawl/http.py` (+40 −0) · `eval/crawl_download_check.py` (+182 −3) · `eval/e2e/run_e2e.py` (ไฟล์ทดสอบ untracked) |
| **F1 FIX** | **PASS** |
| **ISOLATED E2E** | **PASS** — 107/107 |
| **PRODUCTION SAFETY** | **PASS** — 15/15 ค่าตรง baseline |
| **F1 PRODUCTION DEPLOYMENT** | **GO** (ยังห้าม deploy จนเจ้าของสั่ง) |

> GO สำหรับ deployment ไม่ได้หมายถึงให้ deploy — ห้าม deploy จนกว่าเจ้าของโปรเจกต์
> จะอ่านรายงานนี้แล้วสั่ง

---

## 1. Root cause

```
pipeline/crawl/http.py:330   fd, name = tempfile.mkstemp(prefix=".part_", suffix=".pdf", dir=dest_dir)
                             └─ mkstemp สร้างไฟล์โหมด 0600 เสมอ โดยไม่สนใจ umask
                                (เจตนาของ stdlib: ไฟล์ชั่วคราวไม่ควรให้ใครอ่านระหว่างเขียน)

pipeline/crawl/sync.py:206   os.replace(dl.path, out)
                             └─ rename(2) ไม่แตะโหมดของ inode ไฟล์จึงยังเป็น 0600
                                ใต้ชื่อจริงใน staging เจ้าของคือ uid ที่รัน crawler (1001)

backend รันเป็น uid 1000 (appuser)
backend/app/services/staging_store.py:96   sha256_of(resolved)
                                           └─ PermissionError เป็นลูกของ OSError
:99-101                                    except OSError: return None
routes/crawl_review.py                     None -> 404

ผล: GET /crawl-review/{id}/pdf ตอบ 404 ทุกครั้ง แม้ไฟล์จะมีอยู่จริงและ sha256 ถูกต้อง
```

**ผลกระทบ**: ผู้ตรวจเปิด PDF ดูก่อนกดอนุมัติไม่ได้เลย ซึ่งเป็นขั้นตอนบังคับของกระบวนการ
Phase 3 ที่กำหนดให้คนต้องเห็นไฟล์ก่อนตัดสินใจ

**ทำไมไม่เคยถูกพบ**: `staging/crawl` บน production ว่างมาตลอด
(`crawl_sources.staging_path IS NOT NULL` = 0 แถว) ข้อบกพร่องนี้จึงไม่เคยถูกกระตุ้น

**worker ไม่กระทบ**: worker รันเป็น uid 1001 ซึ่งเป็นเจ้าของไฟล์ จึงอ่านได้ตามปกติ
ยืนยันจากการ ingest สำเร็จในรอบทดสอบก่อน

---

## 2. Source audit

ตรวจก่อนแก้ ไม่ได้สมมติว่า `chmod 644` คือคำตอบ

| ไฟล์ | สิ่งที่ตรวจ | ผล |
|---|---|---|
| `pipeline/crawl/http.py:330` | จุดที่สร้างไฟล์ | `tempfile.mkstemp()` — **จุดเดียวในทั้ง repo** |
| `pipeline/crawl/sync.py:206` | จุดที่ย้ายเข้าชื่อจริง | `os.replace()` — ไม่แตะโหมด |
| `pipeline/crawl/sync.py:209-210` | ทางที่ล้ม | `unlink(missing_ok=True)` — ไม่ทิ้งไฟล์ค้าง |
| `backend/app/services/staging_store.py:94-101` | ที่ที่พังเงียบ | `except OSError: return None` → 404 ข้อความเดียวกันทุกกรณี |
| `pipeline/crawl/approve.py:157` | worker อ่านไฟล์ | `resolve_staged()` → `shutil.copyfile` ไป scratch ส่วนตัว |
| `pipeline/crawl/approve.py:258-296` | worker เขียนคลังเอกสาร | `shutil.copyfile` ซึ่ง **เคารพ umask** ไม่ใช่ mkstemp |
| `backend/Dockerfile:29-30` | uid ของ backend | `useradd --uid 1000 appuser` · `USER appuser` |
| `pipeline/Dockerfile:54-55` | uid ของ worker | `groupadd --gid 1001 worker` · `USER worker` |
| `docker-compose.staging.yml:34` | mount ของ backend | `./staging/crawl:/srv/staging:**ro**` |
| `docker-compose.worker.yml:50` | mount ของ worker | `./staging/crawl:/srv/staging:**ro**` |
| `docker-compose.worker.yml:36` | uid ที่สั่งรัน | `user: "1001:1001"` |
| crawler | ผู้เขียน staging | ตัวเดียวที่ต้อง `:rw` — ไม่มี service ใน compose รันเองตามเจตนา (Phase 3 ให้คนสั่ง) |

### 2.1 จุดที่สร้างไฟล์ใน staging — มีจุดเดียว

```
grep -rn 'mkstemp|NamedTemporaryFile' pipeline/ backend/
  pipeline/crawl/http.py:330     <- จุดเดียว
```

ผู้เรียก `download()` มีสองราย และไม่มีรายใดพึ่งโหมดของไฟล์

| ผู้เรียก | ทำอะไรกับไฟล์ | ผลของการแก้ |
|---|---|---|
| `pipeline/crawl/sync.py:168` | `os.replace()` เข้า staging (Phase 2) | **ได้ประโยชน์โดยตรง** |
| `pipeline/crawl/run.py:99` | คำนวณ sha แล้ว `unlink()` ทันที (Phase 1 สำรวจ) | ไม่มีผล — ไฟล์ถูกลบทันที |

---

## 3. UID / GID / mount findings

วัดจาก production จริง (READ-ONLY) เมื่อ 2026-09-29T23:06:34Z

| รายการ | ค่าที่วัดได้ |
|---|---|
| `staging/` | `mode=755 owner=ubuntu(1001):ubuntu(1001)` |
| `staging/crawl/` | `mode=755 owner=ubuntu(1001):ubuntu(1001)` |
| `documents/` | `mode=755 owner=ubuntu(1001):ubuntu(1001)` |
| `/home/ubuntu` | **`mode=750 owner=ubuntu:ubuntu`** |
| backend container | `uid=1000(appuser) gid=1000(appuser) groups=1000(appuser)` |
| กลุ่ม `ubuntu` | `ubuntu:x:1001:` — **ไม่มีสมาชิกเพิ่ม** |
| ผู้ใช้บนโฮสต์ uid≥1000 | `opc uid=1000 gid=1000` · `ubuntu uid=1001 gid=1001` |
| umask ของ `ubuntu` บนโฮสต์ | **`0002`** |
| umask ในอิมเมจ worker | `0022` |
| umask ในอิมเมจ backend | `0022` |
| filesystem ของ staging | `ext4` บน `/dev/sda1` · `rw,relatime,discard,errors=remount-ro` |
| `setfacl` | **ไม่ได้ติดตั้ง** |

**ข้อสรุปสามข้อที่กำหนดทางเลือก**

1. **ไม่มีกลุ่มร่วม** ระหว่างเจ้าของไฟล์ (gid 1001) กับ backend (gid 1000 ไม่มีกลุ่มเสริม)
   → `0640` ใช้ไม่ได้โดยไม่แก้อิมเมจ backend
2. **`/home/ubuntu` เป็น 750** → บนโฮสต์มีเพียง `ubuntu` และ root ที่เข้าถึงโฟลเดอร์
   staging ได้เลย ไม่ว่าโหมดของไฟล์จะเป็นอะไร ผู้ใช้ `opc` (uid 1000) เข้าไม่ถึง
3. **umask ไม่น่าเชื่อถือ** — โฮสต์ใช้ `0002` ซึ่งให้ `0664` (group-writable)
   ส่วนคอนเทนเนอร์ใช้ `0022` ซึ่งให้ `0644` การพึ่ง umask จะได้โหมดต่างกันตามที่รัน

วัดจริง

```
umask 0022 -> open() ได้โหมด 0644
umask 0002 -> open() ได้โหมด 0664     <- โฮสต์ ubuntu เป็นค่านี้
umask 0077 -> open() ได้โหมด 0600
```

---

## 4. Fix options compared

| | ตัวเลือก | ปลอดภัย | เรียบง่าย | พาไปได้ | รองรับ worker | backend :ro | atomic | ความเสี่ยง rollback |
|---|---|---|---|---|---|---|---|---|
| A | `chmod` **หลัง** `os.replace()` ใน `sync.py` | เท่ากัน | ปานกลาง | ได้ | ได้ | ไม่กระทบ | **มีช่วงที่ไฟล์อยู่ใต้ชื่อจริงด้วยโหมดผิด** | ต่ำ |
| **B** | **`chmod` ไฟล์ชั่วคราวก่อนคืนให้ผู้เรียก ใน `http.py`** | **เท่ากัน** | **สูง** | **ได้** | **ได้** | **ไม่กระทบ** | **รักษาไว้ครบ** | **ต่ำสุด** |
| C | กลุ่มร่วม + `0640` | ดีกว่าเล็กน้อย | ต่ำ | จำกัด | ต้องแก้ | ไม่กระทบ | รักษาไว้ | **ต้อง rebuild + redeploy backend** |
| D | ปรับ uid/gid ของคอนเทนเนอร์ให้ตรงกัน | เท่ากัน | ต่ำ | จำกัด | ต้องแก้ | ไม่กระทบ | รักษาไว้ | **ต้อง rebuild backend + chown `/app` ใหม่** |
| E | ACL / แก้ระดับ compose | เท่ากัน | ต่ำสุด | **แย่** | ได้ | ไม่กระทบ | รักษาไว้ | **ต้องติดตั้ง `acl` บน production** |
| F | พึ่ง umask (เลิกใช้ `mkstemp`) | **แย่กว่า** | สูง | **ไม่แน่นอน** | ได้ | ไม่กระทบ | ต้องเขียนใหม่ | ต่ำ แต่ **ได้ 0664 บนโฮสต์** |

### 4.1 เหตุผลที่เลือก B

1. **จุดเดียวที่สร้างไฟล์** คือ `http.py:330` การแก้ที่นั้นคุมทุกผู้เรียกทั้งปัจจุบันและอนาคต
   โดยไม่ต้องหวังว่าผู้เรียกทุกรายจะจำได้ — หลักเดียวกับที่โมดูลนี้ใช้กับ `ALLOWED_HOSTS`
   ("บังคับที่ชั้นนี้เพราะเป็นชั้นเดียวที่ทุกโมดูลใน crawl/ ต้องผ่าน")
2. **ตั้งก่อน `os.replace()`** ทำให้ไฟล์ **ไม่เคยปรากฏใต้ชื่อจริงด้วยโหมดที่ผิด**
   ตัวเลือก A มีช่วงเวลานั้น
3. **ตั้งหลังไฟล์สมบูรณ์** ระหว่างเขียนยังเป็น `0600` ไฟล์ครึ่ง ๆ จึงไม่มีใครอ่านได้
4. `download()` ถูกทดสอบตรงอยู่แล้วใน `eval/crawl_download_check.py`
   การแก้ที่ชั้นนี้จึงได้ทั้งชุด download และชุด `process_link` คลุมพร้อมกัน

### 4.2 เหตุผลที่ `0644` ยอมรับได้ ไม่ใช่ `0640`

`0640` **พิสูจน์แล้วว่าใช้ไม่ได้** — ไม่มีกลุ่มร่วมจริงทั้งบน local และ production
(`getent group ubuntu` = `ubuntu:x:1001:` ไม่มีสมาชิก · backend `groups=1000(appuser)`)
จะให้ได้ต้องแก้อิมเมจ backend เพิ่มกลุ่ม 1001 แล้ว rebuild + redeploy
ซึ่งเกินขอบเขต "narrow fix" และเพิ่มความเสี่ยงมากกว่าที่ได้คืนมา

`0644` ยอมรับได้เพราะ

| เหตุผล | หลักฐาน |
|---|---|
| สิทธิ์อ่านของ other ถูกจำกัดด้วยโฟลเดอร์เหนือขึ้นไปอยู่แล้ว | `/home/ubuntu` เป็น `750` — บนโฮสต์มีแค่ `ubuntu` กับ root ที่เข้าถึงได้ |
| ในคอนเทนเนอร์ มีเพียง backend และ worker ที่ได้ mount นี้ และทั้งคู่ต้องอ่าน | `docker-compose.staging.yml:34` · `docker-compose.worker.yml:50` ทั้งสอง `:ro` |
| เนื้อไฟล์เป็น PDF สาธารณะจากเว็บคณะ | ใครก็ดาวน์โหลดเองได้จาก `sci.pnru.ac.th` |
| ไม่เปิดสิทธิ์ **เขียน** ให้ใครเพิ่ม | `0644` — group/other อ่านอย่างเดียว |
| ไม่มี execute bit · ไม่มี setuid/setgid/sticky | ยืนยันด้วยข้อตรวจ |
| ตรงกับข้อตกลงที่โครงการบันทึกไว้แล้ว | `pipeline/Dockerfile:49-51` "ไฟล์…จะเป็น mode 644 ซึ่ง backend (uid 1000) อ่านได้" |

**ไม่ใช้** `0777` · `0666` · world-writable ใด ๆ

### 4.3 ตัวเลือก F ถูกปฏิเสธเพราะวัดผลแล้วแย่กว่า

"เลิกใช้ `mkstemp` แล้วให้ umask จัดการ" ฟังดูเรียบง่ายที่สุด แต่ umask ของโฮสต์ `ubuntu`
คือ `0002` ซึ่งให้ **`0664` — group-writable** ผิดข้อกำหนดที่ว่าบุคคลที่ไม่เกี่ยวข้อง
ไม่ควรเขียนได้ และผลจะต่างกันตามที่รัน (คอนเทนเนอร์ `0022` โฮสต์ `0002`)
`os.chmod()` แบบระบุค่าชัดเจนให้ผลเดิมทุกที่
---

## 5. Selected fix + rationale

**ตัวเลือก B · `STAGED_FILE_MODE = 0o644` ตั้งด้วย `os.chmod()` ใน `download()`**
หลังไฟล์ครบและผ่านทุกด่าน ก่อนคืนไฟล์ให้ผู้เรียก

ลำดับเวลาที่ได้

```
mkstemp            -> 0600   ไฟล์เปล่า ยังไม่มีใครอ่านได้
เขียนทีละ 64 KB     -> 0600   ไฟล์ครึ่ง ๆ ยังไม่มีใครอ่านได้
ตรวจ %PDF-          -> 0600
ตรวจเพดานขนาด       -> 0600
ตรวจอ่านครบ          -> 0600
os.chmod(0o644)     -> 0644   ไฟล์สมบูรณ์แล้ว จึงเปิดสิทธิ์อ่าน   <-- จุดที่แก้
คืน Download(ok=True)
os.replace() ที่ sync.py -> 0644   rename ไม่แตะโหมด
```

ถ้า `chmod` ล้ม ถือว่าดาวน์โหลดล้ม (`fail(...)`) ไม่ใช่เตือนแล้วปล่อยผ่าน
เพราะไฟล์ที่ผู้ตรวจเปิดไม่ได้คือไฟล์ที่ใช้งานไม่ได้ และ `finally` เดิมจะลบไฟล์ชั่วคราวให้เอง
— พฤติกรรมนี้ตรงกับกติกาที่โมดูลเขียนไว้ว่า "ทุกทางออกต้องผ่านตัวแปรเดียวกัน"

### สิ่งที่ไม่ถูกแตะเลย

`SHA verification` · `%PDF-` verification · เพดาน 50 MB · redirect/robots/allowlist ·
`os.replace()` แบบ atomic · การลบไฟล์ค้างทุกเส้นทาง · state machine ของ crawler ·
ตรรกะการนำเข้า · auth · schema/ฐานข้อมูล · สถาปัตยกรรม production

---

## 6. Exact files changed

| ไฟล์ | สถานะ git | เปลี่ยน | หน้าที่ |
|---|---|---|---|
| `pipeline/crawl/http.py` | tracked · modified | **+40 −0** | ตัวแก้ |
| `eval/crawl_download_check.py` | tracked · modified | **+182 −3** | ชุดตรวจกัน F1 กลับมา |
| `eval/e2e/run_e2e.py` | untracked (ไฟล์ทดสอบเดิม) | แก้เกณฑ์รับของ F1 | ยืนยันผลจาก endpoint จริง |

**ไม่แตะ** `backend/` · `db/` · `llm/` · `docker-compose*.yml` · `Caddyfile` · `.env` ·
`pipeline/crawl/sync.py` · `pipeline/crawl/approve.py` · `pipeline/Dockerfile` ·
`backend/Dockerfile`

---

## 7. Exact diff summary

### `pipeline/crawl/http.py` — สองก้อน ไม่มีบรรทัดเดิมถูกแก้หรือลบ

**ก้อนที่ 1** — ค่าคงที่ (หลัง `_STREAM_CHUNK` บรรทัด 67)

```python
STAGED_FILE_MODE = 0o644
```

พร้อมคำอธิบาย 24 บรรทัดว่าทำไมต้องตั้งเอง ทำไม `0644` ไม่ใช่ `0640`
และอ้างอิง `pipeline/Dockerfile:49-51` ที่บันทึกข้อตกลงนี้ไว้ก่อนแล้ว

**ก้อนที่ 2** — การตั้งสิทธิ์ (ใน `download()` หลังด่าน "อ่านครบ" บรรทัด 375)

```python
try:
    os.chmod(tmp, STAGED_FILE_MODE)
except OSError as e:
    return fail(f"ตั้งสิทธิ์ไฟล์ที่โหลดมาไม่ได้: {type(e).__name__}",
                size=size, **meta)
```

`git diff --check`: ว่าง — ไม่มี whitespace เสีย
CRLF ในไฟล์: **0**

### `eval/crawl_download_check.py`

| ส่วน | เปลี่ยน |
|---|---|
| import | เพิ่ม `os`, `stat`, `STAGED_FILE_MODE` |
| ค่าคงที่ | `BACKEND_UID/GID = 1000` · `WORKER_UID/GID = 1001` อ้าง Dockerfile ทั้งสอง |
| `Checks.skip()` | ใหม่ — ข้อที่เครื่องนี้พิสูจน์ไม่ได้ต้องเห็นว่า **ข้าม** ไม่ใช่ถูกนับเป็นผ่าน |
| `Checks.report()` | รายงานจำนวนที่ข้ามด้วย |
| `read_as_uid()` | ใหม่ — `fork()` + `setgroups/setgid/setuid` แล้วเปิดไฟล์ในนาม uid นั้นจริง |
| `staged_permissions()` | ใหม่ — ชุด `[5]` 25 ข้อ |
| `[5] Phase 2 regression` → `[6]` | เลี่ยงหมายเลขหมวดซ้ำ (ผลจากการแทรกหมวดใหม่) |

---

## 8. Permission — ก่อนแก้

วัดในคอนเทนเนอร์ Linux ด้วยโค้ดเดิมทั้งเส้นทาง (ถอดเฉพาะ `os.chmod` ออก คงค่าคงที่ไว้
เพื่อให้ชุดตรวจ import ได้และวัดได้ว่าข้อตรวจจับข้อบกพร่องนี้จริง)

```
โหมดไฟล์ที่ download() ส่งมอบ            0600
โหมดหลัง os.replace()                    0600
อ่านในนาม uid 1000 (backend)             err:PermissionError
อ่านในนาม uid 1001 (worker)              err:PermissionError
โหมดไฟล์จาก process_link()               0600
อ่านไฟล์จาก process_link ในนาม uid 1000  err:PermissionError
```

ชุดตรวจใหม่ **ไม่ผ่าน 10 ข้อ** กับโค้ดที่ยังมีข้อบกพร่อง

```
ไม่ผ่าน F1: ไฟล์ที่ส่งมอบมีโหมดตามที่ประกาศไว้ — 0600 != 0644
ไม่ผ่าน F1: ไม่ใช่ 0600 อย่างที่ mkstemp ตั้งไว้ — 0600 — ข้อบกพร่อง F1 กลับมาแล้ว
ไม่ผ่าน F1: other อ่านได้ — 0600
ไม่ผ่าน F1: group อ่านได้ — 0600
ไม่ผ่าน F1: uid 1000 (backend) เปิดไฟล์ได้จริง — err:PermissionError
ไม่ผ่าน F1: uid 1000 (backend) อ่านได้ลายเซ็น %PDF- — err:PermissionError
ไม่ผ่าน F1: uid 1001 (worker) เปิดไฟล์ได้จริง — err:PermissionError
ไม่ผ่าน F1: uid 1001 (worker) อ่านได้ลายเซ็น %PDF- — err:PermissionError
ไม่ผ่าน F1: ไฟล์จาก process_link มีโหมดตามที่ประกาศไว้ — 0600 != 0644
ไม่ผ่าน F1: backend uid เปิดไฟล์จาก process_link ได้ — err:PermissionError
สรุป: ผ่าน 155 · ไม่ผ่าน 10 · ข้าม 0
```

ข้อนี้สำคัญกว่าการรายงานว่า "แก้แล้วผ่าน" เพราะพิสูจน์ว่าชุดตรวจ **จับข้อบกพร่องนี้ได้จริง**
ไม่ใช่ข้อตรวจที่ผ่านอยู่แล้วไม่ว่าโค้ดจะเป็นอะไร

**สิ่งที่ยังผ่านแม้ตอนที่มีข้อบกพร่อง** — sha256, ขนาด, ลายเซ็น, ไม่มีไฟล์ค้าง
ซึ่งเป็นเหตุผลว่าทำไมชุดทดสอบเดิม 140 ข้อจึงผ่านหมดทั้งที่ระบบใช้งานไม่ได้

---

## 9. Permission — หลังแก้

```
โหมดไฟล์ที่ download() ส่งมอบ            0644
โหมดหลัง os.replace()                    0644
โหมดไฟล์จาก process_link()               0644
other อ่านได้ / group อ่านได้              ใช่ / ใช่
other เขียนได้ / group เขียนได้            ไม่ / ไม่
execute bit / setuid / setgid / sticky    ไม่มีทั้งสี่
อ่านในนาม uid 1000 (backend)             อ่านได้ · ได้ b'%PDF-'
อ่านในนาม uid 1001 (worker)              อ่านได้ · ได้ b'%PDF-'
อ่านไฟล์จาก process_link ในนาม uid 1000  อ่านได้
sha256 / ขนาด / ลายเซ็น                   ไม่เปลี่ยนเลย
```

ทดสอบ `chmod` บนสองชนิดไฟล์ระบบที่เกี่ยวข้อง

| ที่เก็บ | `mkstemp` | หลัง `chmod` | ผล |
|---|---|---|---|
| Docker volume (ext4 — แบบเดียวกับ production) | `0600` | `0644` | **ทำงาน** |
| bind mount จาก Windows (เครื่องผู้พัฒนา) | `0600` | `0644` | **ทำงาน** |
---

## 10. Unit / regression tests

### 10.1 ชุดตรวจใหม่ที่เพิ่มเข้าไป — `[5]` ใน `eval/crawl_download_check.py` · 25 ข้อ

| ข้อกำหนดของงานนี้ | ข้อตรวจที่พิสูจน์ | ผล |
|---|---|---|
| 1. ไฟล์ staged มี permission ที่เลือกไว้ | โหมดของไฟล์ที่ `download()` ส่งมอบ = `0644` · ไม่ใช่ `0600` · โหมดของไฟล์จาก `process_link()` = `0644` | ผ่าน |
| 2. backend-equivalent reader อ่านได้ | `fork()` + `setuid(1000)` แล้วเปิดไฟล์จริง ได้ `b'%PDF-'` — ทั้งไฟล์จาก `download()` และจาก `process_link()` | ผ่าน |
| 3. worker-equivalent reader อ่านได้ | `fork()` + `setuid(1001)` แล้วเปิดไฟล์จริง ได้ `b'%PDF-'` | ผ่าน |
| 4. ไม่ world-writable | `mode & 0o002 == 0` · เพิ่ม `mode & 0o020 == 0` (group) · ทั้งจาก `download()` และ `process_link()` | ผ่าน |
| 5. SHA ไม่เปลี่ยนเพราะการตั้งสิทธิ์ | sha ของไฟล์บนดิสก์ = ที่ crawler รายงาน = ที่เซิร์ฟเวอร์ส่ง · ขนาดไม่เปลี่ยน · sha คงเดิมหลัง `os.replace()` | ผ่าน |
| 6. ลายเซ็น PDF ยังถูก | ห้าไบต์แรกเป็น `%PDF-` | ผ่าน |
| 7. ดาวน์โหลดที่ล้มไม่ทิ้ง partial file | ดาวน์โหลดที่ถูกปฏิเสธ → ไม่มี `.part_*` ค้าง · `path is None` · staging ว่างเมื่อจบชุด | ผ่าน |
| เพิ่มเติม | ไม่มี execute bit · ไม่มี setuid/setgid/sticky · โหมดคงเดิมหลัง `os.replace()` | ผ่าน |

การพิสูจน์ข้อ 2 และ 3 ใช้ **การอ่านในนาม uid จริง** ไม่ใช่การดูบิตโหมดเพียงอย่างเดียว
เพราะบิตโหมดคือกลไก แต่สิ่งที่ต้องพิสูจน์คือผลลัพธ์ การอ่านจาก uid จริงตรวจบิตโหมด
เจ้าของไฟล์ และการ traverse โฟลเดอร์เหนือขึ้นไปพร้อมกันในข้อเดียว
(ต้องรันเป็น root จึงจะลดสิทธิ์ได้ — บนเครื่องที่ไม่ใช่ root ข้อนี้รายงานว่า **ข้าม**
ไม่ใช่ผ่าน และผลจริงมาจาก isolated E2E ที่ใช้ backend ตัวจริง)

### 10.2 ผลการรัน regression suites — จำนวนจริง

| ชุด | ที่รัน | ผ่าน | ไม่ผ่าน | ข้าม |
|---|---|---:|---:|---:|
| `eval/crawl_download_check.py` | Linux (root) ในคอนเทนเนอร์ | **165** | **0** | **0** |
| `eval/crawl_download_check.py` | Windows ของผู้พัฒนา | **140** | **0** | 1 (หมวด F1 — บิตโหมดไม่มีความหมายบน Windows) |
| `eval/crawl_state_check.py` | Linux + PostgreSQL 16.15 (`crawl_test`) | **32** | **0** | 0 |
| `eval/crawl_approval_check.py` | Linux + PostgreSQL 16.15 (`crawl_test`) | **84** | **0** | **0** |
| `eval/crawl_ingest_worker_check.py` | Linux + PostgreSQL 16.15 (`crawl_test`) | **187** | **0** | **0** |
| `eval/document_endpoint_check.py` | Linux (unittest) | **16** | **0** | 0 |
| **รวมบน Linux** | | **484** | **0** | **0** |

`84` และ `187` ตรงกับตัวเลขที่บันทึกไว้ใน `AUTOMATED_INGESTION_PHASE3A_REPORT.md`
และ `AUTOMATED_INGESTION_PHASE3C_REPORT.md` เป๊ะ — ไม่มี regression

ฐานข้อมูลที่ใช้คือ `crawl_test` ในคอนเทนเนอร์ PostgreSQL ของ project `sci-advisor-e2e`
สร้างจาก `db/schema.sql` + `db/20-roles.sh` (ส่วน GRANT) + migrations 001–004
ชุดเดียวกับ production · **ไม่ได้แตะฐานข้อมูล production เลย**
(ชุด `crawl_ingest_worker_check` มีด่านปฏิเสธเองถ้าชื่อฐานข้อมูลไม่อยู่ในรายการที่อนุญาต
`{crawl_test, ingest_worker_test}` หรือ DSN มีคำว่า `course_advisor`)

### 10.3 ทำไมชุดเดิมจับ F1 ไม่ได้ — และช่องนั้นถูกปิดแล้ว

| ชุด | ทำไมไม่จับได้ |
|---|---|
| `crawl_download_check` เดิม | ตรวจ "มีไฟล์ไหม เนื้อตรงไหม ไม่มี `.part_` ค้างไหม" — ไม่มีข้อใดแตะบิตโหมด |
| `crawl_approval_check` `[3] เปิดดู PDF` 17 ข้อ | ใช้ `TestClient` ในโปรเซสเดียวกับที่สร้างไฟล์ทดสอบ จึงเป็น uid เดียวกันและอ่านได้เสมอ — ข้ามคนละ uid ไม่เคยเกิดขึ้น |
| `crawl_ingest_worker_check` | worker เป็นเจ้าของไฟล์ (uid เดียวกัน) จึงอ่านได้ตลอด |
| ของจริงบน production | `staging/crawl` ว่างมาตลอด ไม่เคยมีไฟล์ให้กระตุ้นอาการ |

ชุด `[5]` ที่เพิ่มเข้าไปปิดช่องนี้ด้วยการ **ข้าม uid จริง** ซึ่งเป็นเงื่อนไขเดียวที่ทำให้
ข้อบกพร่องปรากฏ และมันจับได้จริง (พิสูจน์ในข้อ 8)
---

## 11. Isolated E2E result

| | |
|---|---|
| compose project | `sci-advisor-e2e` (แยกจาก production และจาก stack พัฒนาในเครื่องโดยสมบูรณ์) |
| เริ่ม / จบ | **2026-09-29T23:34:08.736Z → 23:34:24.214Z** (15.5 วินาที) |
| ผล | **107 / 107 PASS · 0 FAIL** · `overall = PASS` |
| ฐานข้อมูล | `e2e_test` (ด่านยืนยันแล้ว) · PostgreSQL 16.15 — รุ่นเดียวกับ production |
| `sci.pnru.ac.th` ในเครือข่ายนี้ | `172.19.0.4` = IP ของ `e2e-fakesite` พอดี |

### 11.1 Isolation — ยืนยันซ้ำในรอบนี้

| ข้อพิสูจน์ | ผล |
|---|---|
| พอร์ตที่ publish ออก host | **ไม่มีเลยสักบริการ** (`8000/tcp`, `5432/tcp`, `11434/tcp` เป็น EXPOSE ไม่ใช่ publish) |
| `sci.pnru.ac.th` | → `172.19.0.4` = `e2e-fakesite` |
| ชื่อบริการของ production จากคอนเทนเนอร์ทดสอบ | `postgres`, `backend`, `ollama`, `caddy`, `frontend`, `webapi` → **resolve ไม่ได้ทั้งหก** |
| ด่านฐานข้อมูล | `SELECT current_database()` = `e2e_test` · `course_chunks > 1000` → ปฏิเสธ |
| bge-m3 ใน test ollama | `790764642607` — **ID เดียวกับ production** |
| e2e-backend เรียก ollama | **0 ครั้ง** (`WARMUP_INTERVAL_MINUTES=0`) |
| คำขอที่เว็บจำลองรับตลอดการทดสอบ | **7 ครั้ง** — ไม่มีคำขอใดออกไปถึงเว็บคณะจริง |

```
2 GET /programs.php                      2 GET /TEST_CS_CURRICULUM_E2E.pdf
1 GET /program_detail.php?id=1           1 HEAD /TEST_CS_CURRICULUM_E2E.pdf
1 GET /robots.txt   (404 = ไม่มีข้อห้าม ตาม RFC 9309)
```

### 11.2 เส้นทางที่รันครบทั้งเส้น

```
Test PDF -> เว็บจำลอง -> crawler ตัวจริง -> staging -> Admin Review -> GET PDF
         -> approve -> worker -> ingest -> chunks -> bge-m3 1024 -> pgvector -> กันซ้ำ
```

| ขั้น | ค่าที่วัดได้ |
|---|---|
| Test PDF | `240b73e1f0037eb7237ae73adec362a29b2c4c44485fba662ed968f66a229bae` · 7,571 ไบต์ · 1 หน้า |
| crawl | `source_id 172dee82-9eb1-424a-87ef-118c7016cb99` · `status downloaded` → สุดท้าย `ingested` |
| staging_path | `/srv/staging/240b73e1f003_TEST_CS_CURRICULUM_E2E.pdf` |
| match_confidence | `unknown` (ฐานทดสอบไม่มีเอกสารให้จับคู่ จึงตั้งธง `needs_review` ตามที่ควร) |
| auth | anonymous `/pending`,`/{id}`,`/{id}/pdf` → **401·401·401** · non-admin `/pending` → **403** · admin → **200** |
| `GET /{id}` | 200 · **19 คีย์ ไม่มี `staging_path`** |
| approve | sha ผิด → **409** · รหัสหลักสูตรไม่มี → **422** · สำเร็จ → **201** · ซ้ำ → **409** |
| worker | `document_id bc735d72-8777-41dd-bd2f-6d3e2b20784d` · 2 chunks · 9.0 วินาที · exit 0 |
| publish | `/srv/documents/240b73e1f003_TEST_CS_CURRICULUM_E2E.pdf` · sha ตรง |
| pgvector | คืน 2 แถว · `top_distance 0.2966856108828996` · อันดับ 1 จากเอกสารทดสอบ มี `TEST101` |
| กันซ้ำ | รัน worker ซ้ำ → exit 0 · documents/chunks/decisions/ไฟล์ **ไม่เพิ่มเลย** · `ingest_finished_at` ไม่ถูกเขียนทับ |
| e2e_test สุดท้าย | courses 1 · documents 1 · chunks 2 · users 2 (1 admin) · crawl_sources 1 `ingested` · decisions 1 · queue 0 · `vector_dims` 1024 |

### 11.3 สถานะที่ e2e-backend ตอบทั้งหมด — 22 คำขอ

```
9 x 200   3 x 201   3 x 401   1 x 403   3 x 404   2 x 409   1 x 422
```

**404 ทั้งสามครั้งมาจากข้อทดสอบ fail-closed ที่ตั้งใจทำ** (ไฟล์หาย · sha ไม่ตรง · ไม่ใช่ PDF)
ไม่มี 404 จากเรื่องสิทธิ์อีกแล้ว — เทียบกับรอบก่อนที่มี 9 ครั้ง

---

## 12. GET staged PDF — ผลโดยไม่มี workaround

**นี่คือเกณฑ์รับหลักของงานนี้**

หลัง crawler สร้างไฟล์ใน staging เสร็จ **ไม่มี `chmod` / `chown` / `copy` / `setfacl` /
workaround ใดเลย** (ยืนยันด้วยการค้นทั้งโฟลเดอร์ `eval/e2e/` — พบคำว่า `chmod`
เพียงในบรรทัดคอมเมนต์ที่ห้ามใช้มันเท่านั้น) แล้วเรียก endpoint ทันที

```
โหมดไฟล์ staged ที่ crawler สร้าง      คาด 0o644   จริง 0o644   PASS
ไฟล์ staged ไม่ world-writable          คาด 0       จริง 0       PASS
ไฟล์ staged ไม่ group-writable          คาด 0       จริง 0       PASS
ไฟล์ staged ไม่มี execute bit           คาด 0       จริง 0       PASS
ไฟล์ staged ไม่มี setuid/setgid/sticky  คาด 0       จริง 0       PASS
uid ของไฟล์ staged                      คาด 1001    จริง 1001    PASS

[เกณฑ์รับ F1] เปิด PDF ได้ทันทีโดยไม่แตะสิทธิ์   คาด 200   จริง 200   PASS
content-type ของ PDF                    คาด application/pdf   จริง application/pdf   PASS
เนื้อไฟล์ขึ้นต้น %PDF-                   คาด True    จริง True    PASS
ขนาด PDF ที่ส่งออกตรงกับไฟล์ใน staging   คาด 7571    จริง 7571    PASS
โหมดไฟล์คงเดิมหลัง backend อ่าน          คาด 0o644   จริง 0o644   PASS
```

**หลักฐานเชิงลบที่สำคัญกว่าสถานะ 200** — log ของ `staging_store` ในรอบนี้

```
อ่านไฟล์ในคิวไม่ได้ (crawl_source_id=…)     ปรากฏ 0 ครั้ง
```

ข้อความนี้คือบรรทัดที่ `staging_store.py:100` เขียนเมื่อจับ `OSError` จาก `sha256_of()`
ซึ่งเป็นต้นทางของ 404 ในรอบก่อน การที่ไม่ปรากฏเลยยืนยันว่าเส้นทางสิทธิ์ไม่ล้มอีก

คำเตือนที่ปรากฏใน log มีเพียงสามข้อ และทั้งสามเป็นข้อทดสอบ fail-closed ที่ตั้งใจทำ

```
WARNING ไม่พบไฟล์ในคิวที่ฐานข้อมูลอ้างถึง        <- ทดสอบไฟล์หาย
WARNING ลายนิ้วมือไฟล์ในคิวไม่ตรงกับฐานข้อมูล    <- ทดสอบ sha ไม่ตรง
WARNING ไฟล์ในคิวไม่ใช่ PDF                     <- ทดสอบไฟล์ไม่ใช่ PDF
INFO    อนุมัติไฟล์ในคิว crawl_source_id=… course_code=TEST101
```

---

## 13. SHA verification

sha256 เดียวกันตลอดเจ็ดจุด ไม่เปลี่ยนเพราะการตั้งสิทธิ์

```
240b73e1f0037eb7237ae73adec362a29b2c4c44485fba662ed968f66a229bae
```

| จุด | ตรง |
|---|---|
| ไฟล์ที่ `make_test_pdf.py` สร้าง | ✓ |
| ที่ crawler คำนวณจากสายข้อมูล | ✓ |
| ไฟล์ใน staging บนดิสก์ | ✓ |
| `mko.crawl_sources.file_sha256` | ✓ |
| ที่ `GET /crawl-review/{id}/pdf` ส่งออก | ✓ |
| `mko.crawl_decisions.file_sha256` | ✓ |
| `course_documents.file_sha256` + ไฟล์ที่ publish | ✓ |

ขนาดไฟล์ 7,571 ไบต์ เท่ากันทุกจุด

---

## 14. Worker result

```
worker ใช้เวลา 9.0 วินาที · exit=0

ยึดงาน decision=8bdaab87-b7ef-43de-af84-1d48982fab05 source=http://sci.pnru.ac.th/TEST_CS_CURRICULUM_E2E.pdf
POST http://e2e-ollama:11434/api/embeddings  200      <- probe ของ check_embedding_contract
extracting /tmp/ingest_worker_vt09bw05/240b73e1f003_TEST_CS_CURRICULUM_E2E.pdf
produced 2 chunks from 1 pages
POST http://e2e-ollama:11434/api/embeddings  200      <- chunk 1
POST http://e2e-ollama:11434/api/embeddings  200      <- chunk 2
ingest complete: course_id=57a4a25b-… document_id=bc735d72-… chunks=2
งานสำเร็จ decision=8bdaab87-… · ingested
---- สรุป ---- สำเร็จ 1 · ล้มเหลว 0
```

| assertion | ผล |
|---|---|
| exit code 0 | **0** |
| `ingest_started_at` / `ingest_finished_at` / `document_id` ถูกเติม | **ครบทั้งสาม** |
| `ingest_error` เป็น null | **null** |
| `course_documents` = 1 · `extraction_status` = `done` · `page_count` ≥ 1 | **ครบ** |
| เอกสารผูกกับ `TEST101` | **ใช่** |
| `crawl_sources.status` สุดท้าย | **`ingested`** |

**worker ไม่ได้รับผลกระทบจากการแก้** — อ่านไฟล์ `0644` ได้เหมือนที่เคยอ่าน `0600` ได้
(เป็นเจ้าของไฟล์อยู่แล้ว) และ `shutil.copyfile` ไป scratch ส่วนตัวเหมือนเดิม

โหมดของไฟล์ที่ worker publish เข้าคลังเอกสาร — วัดจริงในคอนเทนเนอร์

```
/srv/staging/240b73e1f003_TEST_CS_CURRICULUM_E2E.pdf    -rw-r--r-- 1 worker worker   <- 0644 จากตัวแก้
/srv/documents/240b73e1f003_TEST_CS_CURRICULUM_E2E.pdf  -rw-r--r-- 1 worker worker   <- 0644 จาก umask 0022
```

---

## 15. pgvector result

```
query  = "E2E-MARKER-TEST101-PIPELINE-VERIFICATION"  (embed ด้วย bge-m3 ของ test ollama)
มิติ    = 1024
SQL    = ORDER BY embedding <=> :query    (cosine · ตัวดำเนินการเดียวกับ vector_search.py)
probes = SET LOCAL ivfflat.probes = 100
```

| assertion | ผล |
|---|---|
| มิติของ query embedding | **1024** |
| การค้นคืนผลลัพธ์ | **2 แถว** |
| อันดับ 1 มาจากเอกสารทดสอบ | **ใช่** (`bc735d72-…` · `chunk_index=1`) |
| ระยะห่างของอันดับ 1 | **0.2966856108828996** |
| เนื้อหาของอันดับ 1 มี `TEST101` | **ใช่** |
| ผลลัพธ์รวมมี marker | **ใช่** |
| `vector_dims` ของทุก chunk | **1024** (แถวที่ไม่ใช่ 1024 = 0) |
| chunk ที่ `embedding IS NULL` | **0** |

---

## 16. Duplicate protection

รัน worker ซ้ำหลังงานเสร็จ

| assertion | คาด | จริง |
|---|---|---|
| exit code | 0 | **0** |
| `ingest_finished_at` ไม่ถูกเขียนทับ | เท่าเดิม | **`2026-09-29 23:34:22.611812+00`** |
| `course_documents` | 1 | **1** |
| `course_chunks` | 2 | **2** |
| `crawl_decisions` | 1 | **1** |
| ไฟล์ใน `DOCUMENTS_DIR` | 1 | **1** |

### 16.1 เส้นทางความล้มเหลวที่ทดสอบซ้ำในรอบนี้

| สถานการณ์ | คาด | จริง |
|---|---:|---:|
| ไฟล์ staged หาย → `GET /{id}/pdf` | 404 | **404** |
| sha ไม่ตรง → `GET /{id}/pdf` | 404 | **404** |
| ไฟล์ไม่ใช่ PDF แต่ sha ตรง → `GET /{id}/pdf` | 404 | **404** |
| **คืนสภาพแล้วเปิดได้เหมือนเดิม** | 200 | **200** |
| `resolve_staged()` กับ path นอก root | `JobError` | **`path_outside_staging_root`** |
| `EMBED_MODEL` ผิด | worker ล้ม | **`embed_model_mismatch`** |
| `EMBED_DIM = 768` | worker ล้ม | **`embed_dim_mismatch`** |
| หลังล้มจากสัญญา งานยังยึดใหม่ได้ | `ingest_finished_at` ว่าง | **ว่าง · รันครั้งถัดไปสำเร็จ** |

ข้อ "คืนสภาพแล้วเปิดได้เหมือนเดิม → 200" สำคัญเป็นพิเศษ เพราะทำให้ 404 ทั้งสามข้อข้างบน
แยกออกจาก "endpoint พังเฉย ๆ" ได้ — ซึ่งเป็นข้อที่ทำให้พบ F1 ตั้งแต่รอบก่อน

---

## 17. Production baseline before / after

**ก่อน 2026-09-29T23:06:34Z** · **หลัง 2026-09-29T23:36:04Z**

| รายการ | ก่อน | หลัง | ต่าง |
|---|---|---|---|
| users / active / admins | 198/198/1 | 198/198/1 | **ไม่มี** |
| courses | 24 | 24 | **ไม่มี** |
| course_documents | 31 | 31 | **ไม่มี** |
| course_chunks | 9039 | 9039 | **ไม่มี** |
| crawl_sources (+ สถานะย่อย) | 12 · unchanged 12 · needs_review 6 · staging_notnull 0 | เหมือนเดิมทุกค่า | **ไม่มี** |
| crawl_decisions | 0 | 0 | **ไม่มี** |
| v_crawl_queue | 6 | 6 | **ไม่มี** |
| chat_messages | 6640 | 6640 | **ไม่มี** |
| chat_answer_cache | 160 | 160 | **ไม่มี** |
| embedding dimension | 1024 | 1024 | **ไม่มี** |
| **courses code `TEST%`** | **0** | **0** | **ไม่มี** |
| staging files | 0 | 0 | **ไม่มี** |
| documents PDF | 30 | 30 | **ไม่มี** |
| `staging/crawl` โหมด/เจ้าของ | `755 ubuntu:ubuntu` | `755 ubuntu:ubuntu` | **ไม่มี** |
| `documents` โหมด/เจ้าของ | `755 ubuntu:ubuntu` | `755 ubuntu:ubuntu` | **ไม่มี** |

**ต่างกัน 0 รายการจาก 15 รายการที่ตรวจ**

> หมายเหตุการวัด: รอบนี้นับ PDF ในคลังเอกสารด้วย `find -type f -name '*.pdf'` (ได้ 30)
> ไม่ใช่ glob ชั้นบนสุดซึ่งได้ 0 เพราะไฟล์อยู่ในโฟลเดอร์ย่อย
> `curriculum/`, `curriculum-brief/`, `web/` — ตัวเลข 30 ตรงกับรายงานรอบก่อน

---

## 18. Production container before / after

| service | container ID | image | StartedAt | restarts | เปลี่ยน |
|---|---|---|---|---:|---|
| backend | `fda31caa20c4` | `4a45677ec010` | 2026-09-29T01:06:17.872Z | 0 | **ไม่** |
| frontend | `2886c1bf9183` | `591ab6d935bb` | 2026-09-29T01:07:21.190Z | 0 | **ไม่** |
| caddy | `a2957d7b8fc3` | `5f5c8640aae0` | 2026-09-22T21:23:48.949Z | 0 | **ไม่** |
| postgres | `e8c091a4fc60` | `ccc6e83d6e35` | 2026-08-18T14:17:25.705Z | 0 | **ไม่** |
| ollama | `e6ac0350c722` | `9d30908e4114` | 2026-08-18T14:17:25.705Z | 0 | **ไม่** |
| webapi | `6a73308d4f39` | `1163e36361d9` | 2026-09-22T21:21:35.624Z | 0 | **ไม่** |
| `db-viewer` | `da282643e533` | `f742dcf1b6ca` | 2026-09-14T06:03:42.823Z | 0 | **ไม่** |

ทั้งเจ็ดตัว `running` · **container ID และ StartedAt ไม่เปลี่ยนแม้ตัวเดียว**
เทียบทั้งสองค่าไม่ใช่ดู `RestartCount` อย่างเดียว เพราะการ recreate จะรีเซ็ต `RestartCount` เป็น 0 ด้วย

`db-viewer` (adminer) สร้างเมื่อ **2026-09-14** ไม่อยู่ใน compose project ของโปรเจกต์
เป็นของเจ้าของเครื่องที่มีอยู่ก่อนงานรอบนี้ · ใส่ไว้ในตารางเพื่อความครบถ้วน ไม่ได้แตะ

บนเซิร์ฟเวอร์ production: คอนเทนเนอร์/volume/image ที่มีคำว่า `e2e` = **0 / 0 / 0**

---

## 19. Cleanup proof

```
docker compose -p sci-advisor-e2e -f eval/e2e/docker-compose.e2e.yml down -v --remove-orphans
docker rmi sci-advisor-e2e-e2e-backend:latest sci-advisor-e2e-e2e-runner:latest
```

ลบแล้ว: คอนเทนเนอร์ 5 ตัว · volume 6 ตัว (`e2e_pgdata` `e2e_ollama` `e2e_site`
`e2e_staging` `e2e_documents` `e2e_out`) · network 1 วง · อิมเมจที่ build 2 ตัว
(`sha256:074b029f39b5…` และ `sha256:228c463c6d73…`)

ฐานข้อมูล `crawl_test` ที่ใช้รัน regression อยู่ใน volume `e2e_pgdata` จึงถูกลบไปพร้อมกัน

| ตรวจหลัง cleanup | ผล |
|---|---:|
| images `sci-advisor-e2e*` | **0** |
| containers `sci-advisor-e2e` | **0** |
| volumes `sci-advisor-e2e` | **0** |
| networks `sci-advisor-e2e` | **0** |

คอนเทนเนอร์ที่เหลือบนเครื่องผู้พัฒนาเป็นของเจ้าของเครื่องทั้งหมด **มีอยู่ก่อนงานรอบนี้**
และไม่ถูกแตะ: `mko-local-pg` (2026-09-15) · `course-advisor-system-ollama-1` (2026-08-18) ·
`optimistic_khayyam` (2026-08-17) · `course-advisor-system-postgres-1` (2026-08-14)

ลบไฟล์ `__pycache__` ที่เกิดจากการ `py_compile` ในรอบนี้ออกด้วย (อยู่ใน `.gitignore` อยู่แล้ว)

**ไม่ได้ลบอิมเมจหรือ backup ของ production** — ทั้งหมดอยู่บนเซิร์ฟเวอร์ ไม่ใช่เครื่องนี้

---

## 20. Git status

```
branch            mko-phase2
HEAD              2fdc6f241fc1742047b572ee2ef354cd811f9401   (ไม่เปลี่ยน)
origin/mko-phase2 2fdc6f241fc1742047b572ee2ef354cd811f9401   (ไม่เปลี่ยน)
origin/main       b78b3f8bf895685874d9a52c66b45569072f0514   (ไม่แตะ)

staged            0 ไฟล์
```

```
git diff --name-only
  eval/crawl_download_check.py
  pipeline/crawl/http.py

git diff --stat
  eval/crawl_download_check.py | 185 +++++++++++++++++++++++++++++++++++++++-
  pipeline/crawl/http.py       |  40 ++++++++++
  2 files changed, 222 insertions(+), 3 deletions(-)

git status --porcelain
   M eval/crawl_download_check.py
   M pipeline/crawl/http.py
  ?? eval/e2e/            <- ไฟล์ทดสอบ 6 ไฟล์ · 84K (ชุดเดิมจากรอบก่อน)
```

`git diff --check`: ว่าง · CRLF ใน `http.py` / `crawl_download_check.py` / `run_e2e.py` = **0 / 0 / 0**

**ไม่ commit · ไม่ push · ไม่ merge main · ไม่ stage** ตามข้อกำหนด
---

## 21. Risks / limitations

### 21.1 ความเสี่ยงของตัวแก้เอง

| # | ความเสี่ยง | ประเมิน |
|---|---|---|
| 1 | `os.chmod` ล้มบนไฟล์ระบบที่ไม่รองรับ → ดาวน์โหลดถูกนับว่าล้ม | ทดสอบแล้วทำงานทั้งบน ext4 (แบบ production) และ bind mount จาก Windows · ผู้เรียกเป็นเจ้าของไฟล์ที่เพิ่งสร้างเองเสมอ กรณีล้มจึงแทบไม่มีทางเกิด · ถ้าเกิดจะเห็นชัดในสถานะ `error` ของแถวนั้นพร้อมเหตุผล ไม่พังเงียบ |
| 2 | เปิดสิทธิ์อ่านให้ group/other เพิ่มขึ้นจากเดิม | จำกัดด้วย `/home/ubuntu` ที่เป็น `750` อยู่แล้ว · ในคอนเทนเนอร์มีเพียง backend/worker ที่ได้ mount และทั้งคู่ `:ro` · เนื้อไฟล์เป็น PDF สาธารณะ |
| 3 | ไฟล์ครึ่ง ๆ ถูกอ่านระหว่างเขียน | ไม่เกิด — โหมดยังเป็น `0600` ตลอดช่วงที่เขียน ตั้ง `0644` หลังผ่านทุกด่านแล้วเท่านั้น |
| 4 | ไฟล์ปรากฏใต้ชื่อจริงด้วยโหมดผิด | ไม่เกิด — ตั้งโหมดก่อน `os.replace()` และ rename ไม่แตะโหมด |
| 5 | rollback | ถอนได้ด้วยการย้อน commit เดียว ไม่มี migration ไม่มีการเปลี่ยน schema ไม่มีการเปลี่ยนข้อมูล · ไฟล์ที่ถูกสร้างไว้แล้วด้วยโหมด `0644` ไม่เป็นปัญหาหลังถอน (worker ยังอ่านได้) |

### 21.2 สิ่งที่การทดสอบรอบนี้ยังไม่พิสูจน์

| # | เรื่อง |
|---|---|
| 1 | **ยังไม่ทดสอบกับ PDF จริงจากเว็บคณะ** — ยังไม่มี PRODUCTION CANDIDATE ให้ทดสอบ (staging ว่าง · `crawl_sources` ทั้ง 12 แถวเป็น `unchanged`) |
| 2 | **ยังไม่ทดสอบบน production** ตามข้อห้ามของรอบนี้ — ทั้งหมดรันในสภาพแวดล้อมแยกบนเครื่องผู้พัฒนา |
| 3 | **ไฟล์ที่มีอยู่ก่อนการแก้จะยังเป็น `0600`** — ตัวแก้มีผลกับไฟล์ที่ crawler โหลด **หลัง** deploy เท่านั้น ปัจจุบัน staging ว่าง (0 ไฟล์) จึงไม่มีไฟล์เก่าค้าง แต่ถ้ามีการรัน crawler ก่อน deploy ตัวแก้ ไฟล์ชุดนั้นจะต้องถูก `chmod` เองครั้งเดียว |
| 4 | **คุณภาพ ANN ที่ scale จริง** — ฐานทดสอบมี chunk น้อย ต้องตั้ง `ivfflat.probes = 100` เพื่อชดเชย (ไม่ได้แก้ schema หรือ index) |
| 5 | **bge-m3 คนละ instance กับ production** — ID ของโมเดลตรงกัน แต่ไม่ได้พิสูจน์ว่าค่า vector เท่ากัน bit-for-bit |
| 6 | **ไม่ได้ทดสอบ `SKIP LOCKED` แบบขนาน** และเส้นทางล้มเหลวที่ต้องจับจังหวะ (ollama ล่มกลางคัน · worker ถูกฆ่า) |

### 21.3 ข้อสังเกตข้างเคียงที่พบระหว่าง audit — ไม่ได้แก้ในรอบนี้

| # | เรื่อง | เหตุผลที่ไม่แก้ |
|---|---|---|
| S1 | `publish_document()` ใช้ `shutil.copyfile` ซึ่ง **เคารพ umask** ไฟล์ในคลังเอกสารจึงเป็น `0644` เพราะอิมเมจ worker มี umask `0022` เท่านั้น ถ้าวันหนึ่งมีใครรัน worker บนโฮสต์ในนาม `ubuntu` (umask `0002`) ไฟล์ที่ publish จะเป็น **`0664` — group-writable** | เป็นเส้นทางอื่น ไม่ใช่ F1 · ปัจจุบันไม่เกิดเพราะ `docker-compose.worker.yml:36` บังคับ `user: "1001:1001"` ในคอนเทนเนอร์เสมอ · แก้ควรทำเป็นงานแยกที่ขออนุมัติ |
| S2 | `F2` จากรอบก่อน — `check_embedding_contract()` ทำงาน **หลัง** `claim()` | เป็นข้อสังเกตเชิงพฤติกรรม ไม่ใช่ข้อบกพร่อง งานยังยึดใหม่ได้เพราะ `ingest_finished_at` ยังว่าง · อยู่นอกขอบเขต "แก้เฉพาะ F1" |
| S3 | `eval/e2e/run_e2e.py` เดิมเก็บด้วย CRLF (ไฟล์ทดสอบ untracked) การแก้รอบนี้ทำให้กลายเป็น LF ทั้งไฟล์ | ตรงกับไฟล์อื่นทั้ง repo ที่เป็น LF ทั้งหมด · เป็นไฟล์ทดสอบที่ยังไม่ commit |

---

## 22. Recommendation for production deployment

### 22.1 สิ่งที่ต้องทำเมื่อได้รับอนุมัติ

การ deploy ตัวแก้นี้ **ต้อง rebuild อิมเมจ** ไม่ใช่ copy ไฟล์แล้ว restart
เพราะ `pipeline/crawl/http.py` อยู่ใน layer `COPY pipeline/ pipeline/` ของอิมเมจ worker

```
1. commit + push (เมื่อได้รับอนุมัติ)
2. build อิมเมจ worker ใหม่ผูกกับ revision:
     docker build -f pipeline/Dockerfile --build-arg GIT_REVISION=<commit> \
       -t course-advisor-system-ingest-worker:<tag> .
3. แก้ image tag ใน docker-compose.worker.yml ให้ชี้อิมเมจใหม่
4. ยืนยันในคอนเทนเนอร์ว่าโค้ดใหม่เข้าไปจริง ไม่ใช่เชื่อว่า build แล้วต้องเข้า:
     docker run --rm --entrypoint python <image> -c \
       "from pipeline.crawl.http import STAGED_FILE_MODE; print(oct(STAGED_FILE_MODE))"
     ต้องได้ 0o644
5. รัน crawler ด้วยอิมเมจใหม่ (ต้องขออนุมัติแยก — ยังไม่ใช่รอบนี้)
6. ตรวจว่าไฟล์ใน staging เป็น 0644 แล้วเปิดผ่าน /crawl-review/{id}/pdf ได้ 200
```

**backend ไม่ต้อง rebuild และไม่ต้อง restart** — ตัวแก้ไม่แตะโค้ด backend เลย

### 22.2 สิ่งที่ยังไม่ควรทำแม้ deploy ตัวแก้แล้ว

การ deploy ตัวแก้ **ไม่ใช่** การอนุมัติให้รัน crawler หรือ ingestion บน production
ทั้งสองอย่างเป็นการตัดสินใจแยกที่ต้องขออนุมัติเอง

### 22.3 ถ้ามีไฟล์เก่าใน staging ตอน deploy

ตอนนี้ไม่มี (staging = 0 ไฟล์) ถ้าวันที่ deploy มีไฟล์ค้างอยู่ ไฟล์ชุดนั้นจะยังเป็น `0600`
เพราะตัวแก้มีผลกับไฟล์ที่โหลดใหม่เท่านั้น ต้อง `chmod 644` ไฟล์ชุดนั้นครั้งเดียว
หรือให้ crawler โหลดใหม่ — แต่นั่นเป็นคำสั่งที่ต้องขออนุมัติแยก
---

## 23. คำตัดสิน

### **F1 FIX: PASS**

| หลักฐาน | ผล |
|---|---|
| ต้นเหตุระบุได้ชัดและตรวจกับ source แล้ว | `tempfile.mkstemp()` โหมด `0600` + `os.replace()` ไม่แตะโหมด → backend คนละ uid |
| ตัวแก้อยู่ที่จุดเดียวที่สร้างไฟล์ | `pipeline/crawl/http.py` · +40 −0 · ไม่มีบรรทัดเดิมถูกแก้ |
| ชุดตรวจ **จับข้อบกพร่องได้จริง** | รันกับโค้ดที่ยังมีบั๊ก → **ไม่ผ่าน 10 ข้อ** รวม `PermissionError` จาก uid 1000 และ 1001 |
| ชุดตรวจผ่านหลังแก้ | 25 ข้อในหมวด F1 · **ผ่านทั้งหมด** |
| พิสูจน์ข้าม uid จริง | `fork()` + `setuid(1000)` และ `setuid(1001)` เปิดไฟล์ได้ ได้ `b'%PDF-'` |
| **เกณฑ์รับใน E2E** | `GET /crawl-review/{id}/pdf` → **200 ทันทีโดยไม่มี chmod/chown/copy/workaround ใด** |
| ความปลอดภัย | `0644` · ไม่ world-writable · ไม่ group-writable · ไม่มี execute bit · ไม่มี setuid/setgid/sticky |
| ไม่กระทบสิ่งอื่น | SHA · `%PDF-` · เพดาน 50 MB · redirect/robots/allowlist · atomic replace · การลบไฟล์ค้าง — ครบเหมือนเดิม |
| regression | **484 / 484 ผ่าน · 0 ไม่ผ่าน** บน Linux (`84` และ `187` ตรงกับ Phase 3A/3C เป๊ะ) |

### **ISOLATED E2E: PASS**

**107 / 107 ผ่าน · 0 ไม่ผ่าน** · `overall = PASS` · 15.5 วินาที

เส้นทางครบวงจรทำงานจริงตั้งแต่ Test PDF ถึง pgvector และการกันซ้ำ
พร้อมหลักฐานเชิงลบว่า `staging_store` ไม่เคยบ่นว่าอ่านไฟล์ไม่ได้อีกเลย (0 ครั้ง)

### **PRODUCTION SAFETY: PASS**

15 / 15 ค่าของ production ตรง baseline เป๊ะ · `courses code TEST%` = 0 ·
โหมด/เจ้าของของ `staging/crawl` และ `documents` ไม่เปลี่ยน ·
คอนเทนเนอร์ทั้งเจ็ด container ID และ StartedAt ไม่เปลี่ยน · restarts = 0 ทุกตัว ·
ไม่มี resource ของ e2e บนเซิร์ฟเวอร์เลย · Production access ในรอบนี้เป็น **READ-ONLY ล้วน**

### **F1 PRODUCTION DEPLOYMENT: GO**

ตัวแก้พร้อม deploy ทางเทคนิค เพราะ

1. แก้ไฟล์เดียว 40 บรรทัด ไม่มีบรรทัดเดิมถูกแก้หรือลบ
2. ไม่มี migration ไม่แตะ schema ไม่แตะข้อมูล ไม่แตะ auth ไม่แตะ Caddy
3. **backend ไม่ต้อง rebuild และไม่ต้อง restart** — ตัวแก้อยู่ฝั่ง pipeline เท่านั้น
4. rollback = ย้อน commit เดียว · ไฟล์ `0644` ที่สร้างไว้แล้วไม่เป็นปัญหาหลังถอน
5. regression 484 ข้อผ่านหมด และ E2E ครบวงจรผ่าน 107 ข้อ
6. มีชุดตรวจที่พิสูจน์แล้วว่าจับข้อบกพร่องนี้ได้ กันไม่ให้กลับมาเงียบ ๆ

> **GO ไม่ได้หมายถึงให้ deploy** — ห้าม deploy จนกว่าเจ้าของโปรเจกต์จะอ่านรายงานนี้แล้วสั่ง
> และการ deploy ตัวแก้ **ไม่ใช่** การอนุมัติให้รัน crawler หรือ ingestion บน production
> ทั้งสองอย่างเป็นการตัดสินใจแยกที่ต้องขออนุมัติเอง

---

## สิ่งที่ไม่ได้ทำ

ไม่ได้ deploy · ไม่ได้ restart หรือ recreate บริการใดบน production ·
ไม่ได้รัน crawler/worker/ingestion บน production · ไม่ได้ POST approve/ignore/undo ·
ไม่ได้สร้าง embedding บน production · ไม่ได้ทำ migration บน production ·
ไม่ได้ INSERT/UPDATE/DELETE ข้อมูลใดบน production · ไม่ได้แตะ staging ของ production ·
ไม่ได้แก้ Supabase · ไม่ได้แก้ auth · ไม่ได้แก้ Caddy · ไม่ได้ refactor สิ่งที่ไม่เกี่ยวข้อง ·
ไม่ได้ commit · ไม่ได้ push · ไม่ได้ merge main · ไม่ได้ stage ไฟล์ใด

---

## STOP

รอ **OWNER REVIEW**

สามเรื่องที่ต้องให้เจ้าของโปรเจกต์ตัดสิน

1. **อนุมัติ commit + deploy ตัวแก้ F1 หรือไม่** (ขั้นตอนอยู่ในข้อ 22)
2. **ไฟล์ทดสอบ 6 ไฟล์ใน `eval/e2e/`** — จะ commit เก็บไว้หรือไม่
3. **ข้อสังเกต S1** (ไฟล์ที่ publish พึ่ง umask ของคอนเทนเนอร์) — จะทำเป็นงานแยกหรือปล่อยไว้

STOP
