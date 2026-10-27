# Phase 3D — F1 Deployment Decision Finalization

| | |
|---|---|
| วันที่ | 2026-09-30 · ตรวจเมื่อ **01:10–01:11 UTC** (ไทย ราว 08:10–08:11) |
| ขอบเขต | บันทึกการตัดสินใจ B1 · ตรวจยืนยันทั้งหมดแบบ **READ-ONLY** · เขียนรายงาน |
| เอกสารหลัก | `docs/PHASE3D_F1_PRODUCTION_DEPLOYMENT_REPORT.md` |
| **DEPLOY_REV** | `7af085b2e8138c5f7d10229af4a68b8e435c0a63` |
| **F1 FIX** | **PASS** |
| **F1 IMAGE READY ON PRODUCTION** | **PASS** |
| **B1 DEPLOYMENT STRATEGY** | **OPTION C — ACCEPTED** |
| **PRODUCTION DATA SAFETY** | **PASS** |
| **PRODUCTION SERVICE SAFETY** | **PASS** |
| **CRAWLER EXECUTED** | **NO** |
| **WORKER EXECUTED** | **NO** |
| **INGESTION EXECUTED** | **NO** |
| **PRODUCTION ONE-JOB INGESTION** | **ยัง NO-GO** |

> **คำที่ใช้บรรยายสถานะให้ถูกต้อง**
>
> อิมเมจ worker ของ F1 ถูก build ตรวจยืนยัน และพร้อมใช้งานอยู่บนเครื่อง production
> การรัน worker ยังคงต้องสั่งอย่างชัดแจ้งผ่าน Option C และ **ไม่มี worker service
> ที่ถูกติดตั้งหรือกำลังทำงาน**
>
> ไม่ใช่ "worker deployed and active"

รอบนี้ไม่มีการเปลี่ยนแปลงใดบน production เลย — เป็นการตรวจยืนยันและบันทึกเท่านั้น

---

## 1. Owner decision B1 = C

เจ้าของโปรเจกต์ตัดสินใจเลือก **Option C**

```
ไม่ติดตั้ง docker-compose.worker.yml ลงใน /home/ubuntu/course-advisor-system/

คงไฟล์
  /home/ubuntu/release-7af085b-worker/compose.worker-candidate-7af085b.yml
ไว้เป็น explicit worker execution configuration

เมื่ออนาคตเจ้าของอนุมัติให้รัน worker จริง จึงค่อยสั่งอย่างชัดแจ้งด้วย
  docker compose -f <approved compose files> ...
ตาม configuration ที่ตรวจแล้วใน release directory
```

**บันทึกแล้ว** — รอบนี้จึงไม่มีการ copy · ไม่มีการแก้ production compose ·
ไม่มี commit เพิ่ม · ไม่มี push เพิ่ม · ไม่มีการ build ใหม่

---

## 2. เหตุผลของ Option C

| เจตนา | Option C ให้ผลอย่างไร |
|---|---|
| worker execution ยังคง explicit | ต้องพิมพ์ `-f` ชี้ไฟล์ใน release directory เอง ไม่มีทางพลาดสั่งจากโฟลเดอร์ production |
| production directory ไม่มี worker compose | ยืนยันแล้วว่าไม่มี (ข้อ 8) |
| ไม่ลด safety property ของ Step 3 | Step 3 กัน `docker-compose.worker.yml` ออกจาก production โดยเจตนา "เพื่อให้ไม่มีทางรัน worker จาก release directory" — Option C รักษาคุณสมบัตินี้ไว้ทั้งหมด |
| ไม่ต้องสร้าง Git commit เพิ่ม | `docker-compose.worker.yml` ในโปรเจกต์ยังชี้ `:617110e` ตามเดิม ไม่ถูกแก้ |
| DEPLOY_REV ยังคงเดิม | `HEAD == origin/mko-phase2 == 7af085b2e813…` (ข้อ 19) |
| worker image ที่พร้อมใช้งานคือ `:7af085b` | ยืนยันแล้ว (ข้อ 4, 9, 10, 11) |
| rollback image `:617110e` ยังเก็บไว้ | ยืนยันแล้ว (ข้อ 5) |

เทียบกับทางเลือกที่ไม่ได้เลือก

| ทาง | ผลที่เลี่ยงได้ด้วย Option C |
|---|---|
| A — commit ที่สามแก้บรรทัด `image:` | จะทำให้ `HEAD ≠ DEPLOY_REV` และเพิ่ม commit นอกรายการที่อนุมัติไว้ |
| B — ติดตั้งไฟล์ลงโฟลเดอร์ production | จะทำให้การ start worker เหลือคำสั่งเดียว ย้อนคุณสมบัติความปลอดภัยของ Step 3 |

**ผลข้างเคียงที่ต้องรู้ไว้**: reference สำหรับรัน worker ไม่อยู่ในโปรเจกต์ ผู้ที่จะรัน
ในอนาคตต้องรู้ path ของ release directory เอง จึงบันทึก path ไว้ในข้อ 6 ให้ชัด

---

## 3. DEPLOY_REV

```
7af085b2e8138c5f7d10229af4a68b8e435c0a63
short: 7af085b
```

| | |
|---|---|
| branch | `mko-phase2` |
| `HEAD` | `7af085b2e8138c5f7d10229af4a68b8e435c0a63` |
| `origin/mko-phase2` | `7af085b2e8138c5f7d10229af4a68b8e435c0a63` — ตรงกัน |
| `origin/main` | `b78b3f8bf895685874d9a52c66b45569072f0514` — ไม่แตะ |
| commit ที่ประกอบขึ้น | `5d8f82b` (F1 fix + regression) · `7af085b` (E2E harness 6 ไฟล์) |

ไม่มี commit เพิ่มหลัง DEPLOY_REV · staged 0 ไฟล์ · tracked modified 0 ไฟล์

---

## 4. Current worker image

```
course-advisor-system-ingest-worker:7af085b
  image ID   sha256:9d5c623b7e0a8a0f88873b170bfc697ac4edd039bdaaf6771c45322c3bbfb2a4
  short      9d5c623b7e0a
  ขนาด        330MB
  สร้างเมื่อ    2026-09-29 23:59:08 UTC
  OCI revision  7af085b2e8138c5f7d10229af4a68b8e435c0a63
```

อยู่บนเครื่อง production แล้ว **แต่ไม่มีคอนเทนเนอร์ใดถูกสร้างจากอิมเมจนี้**

---

## 5. Rollback worker image

```
course-advisor-system-ingest-worker:617110e
  image ID   sha256:c80cc9b2114139cc38ef91c044a8517b2cf4f30611c663d55de3b99747ae4588
  short      c80cc9b21141
  ขนาด        330MB
  สร้างเมื่อ    2026-09-28 06:15:45 UTC
  OCI revision  617110e975dccc94b5e67f77990e34a071ccf9a0
```

**ยังอยู่ครบ ไม่ถูกลบ ไม่ถูก relabel** และ `docker-compose.worker.yml` ในโปรเจกต์
ก็ยังชี้อิมเมจนี้อยู่ ดังนั้น **สถานะปัจจุบันคือสถานะ rollback อยู่แล้วโดยปริยาย** —
ถ้าไม่ทำอะไรต่อ ก็ไม่มีอะไรต้องถอน

---

## 6. Candidate compose path

```
/home/ubuntu/release-7af085b-worker/compose.worker-candidate-7af085b.yml
  4,932 ไบต์ · 52 บรรทัด · mode 644 · owner ubuntu:ubuntu · mtime 2026-09-30 00:01
  sha256  db97a3621f3fe9050b7ab6518a787ad23ae5bfa3b175bae7f213ee8ea89c873c
```

release directory ทั้งชุด (mode 750)

```
/home/ubuntu/release-7af085b-worker/
  build-worker-7af085b.log
  compose.worker-candidate-7af085b.yml      <- explicit worker execution configuration
  release-7af085b-worker.manifest.tsv
  release-7af085b-worker.tar
  src/
```

**วิธีใช้ในอนาคต** (ยังไม่ได้รัน และยังต้องขออนุมัติแยกก่อน)

```bash
docker compose \
  -f /home/ubuntu/course-advisor-system/docker-compose.prod.yml \
  -f /home/ubuntu/release-7af085b-worker/compose.worker-candidate-7af085b.yml \
  run --rm ingest-worker
```

---

## 7. Candidate compose verification

ดึงไฟล์จากเซิร์ฟเวอร์ลงมาเทียบกับ `docker-compose.worker.yml` ที่ DEPLOY_REV โดยตรง
ไม่ได้เทียบกับสำเนาที่ผมสร้างไว้เอง

| ข้อตรวจ | ผล |
|---|---|
| sha256 บนเซิร์ฟเวอร์ | `db97a3621f3fe9050b7ab6518a787ad23ae5bfa3b175bae7f213ee8ea89c873c` — ไม่เปลี่ยนตั้งแต่สร้าง |
| จำนวนบรรทัด | 52 ทั้งสองไฟล์ |
| **บรรทัดที่เนื้อหาต่าง** | **1 บรรทัด** |
| image reference | `course-advisor-system-ingest-worker:7af085b` |

```diff
@@ บรรทัด 30 @@
-    image: course-advisor-system-ingest-worker:617110e
+    image: course-advisor-system-ingest-worker:7af085b
```

**ทุกบรรทัดที่ไม่ใช่ `image:` เหมือนกันหมด 51 บรรทัด**

เทียบ field ที่ห้ามเปลี่ยนทีละรายการแบบ byte-for-byte

| field | จำนวนบรรทัดที่พบ | เหมือนกัน |
|---|---:|---|
| `command` | 0 (อิมเมจใช้ CMD ของตัวเอง ไม่ถูก override ในไฟล์นี้) | **ใช่** |
| `environment` | 1 | **ใช่** |
| `volumes` | 1 | **ใช่** |
| `user` | 1 | **ใช่** |
| `restart` | 2 | **ใช่** |
| `profiles` | 2 | **ใช่** |
| `INGEST_DATABASE_URL` | 1 | **ใช่** |
| `OLLAMA_BASE_URL` | 1 | **ใช่** |
| `EMBED_MODEL` | 1 | **ใช่** |
| `EMBED_DIM` | 1 | **ใช่** |
| `CRAWL_STAGING_DIR` | 1 | **ใช่** |
| `DOCUMENTS_DIR` | 1 | **ใช่** |
| `srv/staging` (mount) | 2 | **ใช่** |
| `srv/documents` (mount) | 2 | **ใช่** |

ไฟล์นี้ยังคงคุณสมบัติความปลอดภัยเดิมไว้ทั้งหมด: `profiles: ["worker"]` (ต้องระบุ
`--profile worker` หรือใช้ `run` จึงจะถูกสร้าง — `up -d` เฉย ๆ จะข้ามไป) ·
`restart: "no"` · `user: "1001:1001"` · `./staging/crawl:/srv/staging:ro`

---

## 8. Proof no worker compose in production directory

```
/home/ubuntu/course-advisor-system/
  -rw-rw-r-- 1 ubuntu ubuntu  1391 Sep  7 18:12 docker-compose.gpu.yml
  -rw-rw-r-- 1 ubuntu ubuntu 10606 Sep 22 21:20 docker-compose.prod.yml
  -rw-r--r-- 1 ubuntu ubuntu  2977 Sep 29 01:05 docker-compose.staging.yml
  -rw-rw-r-- 1 ubuntu ubuntu  3894 Sep  7 18:12 docker-compose.yml

  ไม่มี docker-compose.worker.yml
```

ค้นทั้งเครื่องอีกครั้งด้วย `find /home/ubuntu -maxdepth 3 -name "docker-compose.worker.yml"`:
**ไม่พบไฟล์ชื่อนี้ที่ใดเลย**

mtime ของไฟล์ทั้งสี่ไม่เปลี่ยนจากรอบก่อน — ไม่มีการแก้ production compose

---

## 9. STAGED_FILE_MODE verification

ตรวจด้วย safe entrypoint · **ไม่ใช้ default worker CMD**

```bash
sudo docker run --rm --network none --entrypoint python \
  course-advisor-system-ingest-worker:7af085b -c "..."
```

ยืนยันก่อนรันว่า `Config.Entrypoint` เป็น `null` จึงมั่นใจได้ว่าการส่ง args
จะแทนที่ CMD ทั้งชุด

```
CMD ที่ถูกแทนที่และไม่ถูกใช้ = ["python","-u","-m","pipeline.crawl.approve","--max-jobs","1"]
```

ผลที่วัดได้

```
STAGED_FILE_MODE                                  = 0o644
chmod อยู่หลังด่านอ่านครบ และก่อน Download(ok=True)  = True
```

`--network none` · ไม่ส่ง env ของฐานข้อมูลหรือ Ollama · ไม่ mount volume ใด ·
`--rm` — ไม่มีทางแตะข้อมูลใด และไม่เหลือคอนเทนเนอร์ค้าง

---

## 10. OCI revision verification

| อิมเมจ | `org.opencontainers.image.revision` | ตรงกับ |
|---|---|---|
| `:7af085b` | `7af085b2e8138c5f7d10229af4a68b8e435c0a63` | **= DEPLOY_REV** |
| `:617110e` | `617110e975dccc94b5e67f77990e34a071ccf9a0` | revision เดิม ไม่ถูกแตะ |

---

## 11. UID/GID verification

```
uid:gid = 1001:1001
groups  = [1001]
```

สถาปัตยกรรมเดิมทั้งหมด `groups = [1001]` ยังยืนยันเหตุผลที่เลือกโหมด `0644` ไม่ใช่
`0640` — ไม่มีกลุ่มร่วมกับ backend ซึ่งเป็น gid 1000

---

## 12. Production data invariants

วัดจริงเมื่อ **2026-09-30T01:11:12Z** (READ-ONLY) — ไม่ได้ใช้ค่าจากรายงานเก่า

| รายการ | ค่าที่คาด | **ค่าที่วัดได้** | ตรง |
|---|---|---|---|
| crawl_decisions | 0 | **0** | ✓ |
| course_documents | 31 | **31** | ✓ |
| course_chunks | 9039 | **9039** | ✓ |
| crawl_sources | 12 | **12** · unchanged 12 · needs_review 6 · staging_path ไม่ null **0** | ✓ |
| staging files | 0 | **0** | ✓ |
| documents PDF | 30 | **30** | ✓ |
| courses code `TEST%` | 0 | **0** | ✓ |
| courses | — | **24** | เท่าเดิม |
| users / active / admins | — | **198 / 198 / 1** | เท่าเดิม |
| v_crawl_queue | — | **6** | เท่าเดิม |
| chat_messages | — | **6640** | เท่าเดิม |
| chat_answer_cache | — | **160** | เท่าเดิม |
| embedding dimension | — | **1024** | เท่าเดิม |

**ตรงทุกค่าที่คาดไว้ และทุกค่าอื่นเท่าเดิมกับ baseline ของรอบ deployment**

โฟลเดอร์สำคัญไม่เปลี่ยน

```
/home/ubuntu/course-advisor-system/staging/crawl   mode=755 owner=ubuntu:ubuntu
/home/ubuntu/course-advisor-system/documents        mode=755 owner=ubuntu:ubuntu
```

---

## 13. Production service / process invariants

| service | container ID | image | StartedAt | restarts | status |
|---|---|---|---|---:|---|
| backend | `fda31caa20c4` | `4a45677ec010` | 2026-09-29T01:06:17.872Z | 0 | running |
| frontend | `2886c1bf9183` | `591ab6d935bb` | 2026-09-29T01:07:21.190Z | 0 | running |
| caddy | `a2957d7b8fc3` | `5f5c8640aae0` | 2026-09-22T21:23:48.949Z | 0 | running |
| postgres | `e8c091a4fc60` | `ccc6e83d6e35` | 2026-08-18T14:17:25.705Z | 0 | running |
| ollama | `e6ac0350c722` | `9d30908e4114` | 2026-08-18T14:17:25.705Z | 0 | running |
| webapi | `6a73308d4f39` | `1163e36361d9` | 2026-09-22T21:21:35.624Z | 0 | running |
| `db-viewer` | `da282643e533` | — | 2026-09-14T06:03:42.823Z | 0 | running |

**container ID และ StartedAt ตรงกับค่าที่บันทึกไว้ตอน pre-deploy และ post-deploy ทุกตัว**
ไม่มีบริการใดถูก restart หรือ recreate · `db-viewer` (adminer สร้าง 2026-09-14) เป็นของ
เจ้าของเครื่องที่มีอยู่ก่อนงานนี้ ใส่ไว้เพื่อความครบถ้วน ไม่ได้แตะ

คอนเทนเนอร์ที่มีคำว่า `worker` หรือ `ingest`: **0**

---

## 14. Proof crawler not run

```
โปรเซสที่ตรงกับ 'pipeline.crawl'  : 0
โปรเซสที่ตรงกับ 'crawl.sync'      : 0
```

โปรเซส python ที่ไม่ใช่ของ OS บนโฮสต์ มีเพียงตัวเดียว

```
3126055  opc  1-00:04:55  /usr/local/bin/python3.11 /usr/local/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

คือ backend ซึ่งรันมา **1 วัน 4 นาที** สอดคล้องกับ `StartedAt = 2026-09-29T01:06:17Z`
เป็นโปรเซสเดิมที่ไม่เคยถูก restart

หลักฐานเพิ่มเติมว่าไม่มีการ crawl: `crawl_sources` ทั้ง 12 แถวยังเป็น `unchanged` ·
`staging_path` null ทั้งหมด · staging ว่าง — ถ้ามีการ crawl แม้รอบเดียว ค่าเหล่านี้ต้องเปลี่ยน

### 14.1 วิธีวัดที่ใช้ และเหตุที่ต้องใช้วิธีนี้

`pgrep -f` เทียบกับ **command line เต็ม** จึงจับคำสั่ง ssh ของผู้ตรวจเองได้ถ้าคำค้น
ปรากฏในบรรทัดคำสั่งนั้น (รอบ deployment เคยให้ค่า 2 จากสาเหตุนี้ และได้แก้ไว้แล้ว)

รอบนี้เขียนสคริปต์เป็นไฟล์บนเซิร์ฟเวอร์ก่อน แล้วประกอบคำค้นด้วย `printf` ในสคริปต์
คำค้นจึงไม่ปรากฏใน command line ของ ssh เลย และตัดทั้ง `$$` และ `$PPID` ออกอีกชั้น

---

## 15. Proof worker not run

```
คอนเทนเนอร์ที่มีคำว่า worker หรือ ingest : 0
โปรเซสที่ตรงกับ 'crawl.approve'          : 0
```

ไม่มี `docker compose up worker` · ไม่มี `--profile worker up` · ไม่มีการ `docker run`
อิมเมจด้วย CMD เดิม — การตรวจอิมเมจทุกครั้งใช้ `--entrypoint python --network none --rm`

`compose.worker-candidate-7af085b.yml` ที่วางไว้ในระบบไฟล์ **ไม่ทำให้เกิด service ใด**
เพราะเป็นเพียงไฟล์ที่ต้องถูกอ้างด้วย `-f` อย่างชัดแจ้ง และ service ในไฟล์นั้นยังอยู่
หลัง `profiles: ["worker"]` อีกชั้น

---

## 16. Proof ingestion not run

```
โปรเซสที่ตรงกับ 'pipeline.ingest' : 0
```

หลักฐานจากข้อมูลซึ่งหนักกว่าการนับโปรเซส — ถ้ามี ingestion เกิดขึ้นแม้งานเดียว
ค่าเหล่านี้ต้องเปลี่ยน

| ตัวชี้ | ค่า |
|---|---:|
| `mko.crawl_decisions` | **0** |
| `course_documents` | **31** |
| `course_chunks` | **9039** |
| `documents` PDF | **30** |
| `staging` files | **0** |
| `crawl_sources` ที่ไม่ใช่ `unchanged` | **0** |
| `courses` code `TEST%` | **0** |

ไม่เปลี่ยนแม้ค่าเดียว

---

## 17. S1 = deferred

`publish_document()` ที่ `pipeline/crawl/approve.py:296` ใช้ `shutil.copyfile` ซึ่ง
**เคารพ umask** ไฟล์ในคลังเอกสารจึงเป็น `0644` เพราะอิมเมจ worker มี umask `0022`
ถ้ามีใครรัน worker บนโฮสต์ในนามผู้ใช้ `ubuntu` (umask `0002`) ไฟล์ที่ publish
จะกลายเป็น `0664` — group-writable

**การตัดสินใจ: DEFER — ไม่แก้รอบนี้ เก็บเป็น known observation เท่านั้น**

เหตุผลที่ยอมรับได้ในสถาปัตยกรรมปัจจุบัน

| เหตุผล | หลักฐานที่วัดได้รอบนี้ |
|---|---|
| คอนเทนเนอร์ worker รันเป็น uid/gid 1001:1001 | ตรวจแล้วในอิมเมจ `:7af085b` → `1001:1001` |
| umask ในอิมเมจเป็น `0022` | ตรวจแล้วในรอบ deployment → `0o22` |
| สถาปัตยกรรมปัจจุบันไม่ได้รัน worker บนโฮสต์ `ubuntu` โดยตรง | `compose.worker-candidate-7af085b.yml:36` บังคับ `user: "1001:1001"` และไม่มีโปรเซส worker บนโฮสต์เลย |

**ไม่ขยาย scope** — ถ้าวันหนึ่งมีการเปลี่ยนวิธีรัน worker ให้ไม่ผ่านคอนเทนเนอร์
ต้องกลับมาทบทวนข้อนี้ก่อน

---

## 18. Remaining blocker for real ingestion

**ยังไม่มี PRODUCTION CANDIDATE** — นี่คือสิ่งเดียวที่ค้างอยู่

| หลักฐาน | ค่า |
|---|---|
| `crawl_sources` ทั้งหมด | 12 แถว |
| สถานะ `unchanged` | **12 แถว — ทุกแถว** |
| `staging_path` ไม่ null | **0 แถว** |
| ไฟล์ใน `staging/crawl` | **0 ไฟล์** |
| `v_crawl_queue` | 6 แถว |

**6 แถวในคิวไม่ใช่ ingestion candidate** — ถูกตั้งธง `needs_review` เพราะจับคู่หลักสูตร
ไม่ชัด (`match_confidence` กำกวมหรือไม่รู้จัก) ไม่ใช่เพราะมีไฟล์ใหม่หรือไฟล์ที่เปลี่ยน
ห้ามใช้ 6 แถวนี้เพื่อบังคับทดสอบ ingestion

สิ่งที่ต้องเกิดก่อนจึงจะพิจารณา one-job ingestion ได้

1. มี PDF ใหม่หรือ PDF ที่เนื้อหาเปลี่ยนจริงบน `sci.pnru.ac.th`
2. รัน crawler ด้วยอิมเมจที่มีตัวแก้ F1 (ต้องขออนุมัติแยก)
3. ผู้ตรวจเปิด PDF ดูผ่าน `GET /crawl-review/{id}/pdf` ได้จริง แล้วจึงกดอนุมัติ
4. รัน worker หนึ่งงาน (ต้องขออนุมัติแยกอีกครั้ง)

ทุกขั้นเป็นการตัดสินใจแยก การที่อิมเมจพร้อมอยู่บนเครื่องไม่ใช่การอนุมัติข้อใดข้อหนึ่ง

---

## 19. Final state

### 19.1 Local (เครื่องผู้พัฒนา)

```
branch            mko-phase2
HEAD              7af085b2e8138c5f7d10229af4a68b8e435c0a63   = DEPLOY_REV
origin/mko-phase2 7af085b2e8138c5f7d10229af4a68b8e435c0a63
origin/main       b78b3f8bf895685874d9a52c66b45569072f0514   ไม่แตะ

staged            0 ไฟล์
tracked modified  0 ไฟล์
working tree      สะอาด (นอกจาก docs/ ที่ไม่ commit)

git log -3
  7af085b test: add isolated crawler ingestion e2e harness
  5d8f82b fix: make staged crawler PDFs readable by the review backend
  2fdc6f2 chore: version the deployment files for the crawler review rollout
```

ไม่มี resource ของสภาพแวดล้อมทดสอบค้าง: containers 0 · volumes 0 · images 0

### 19.2 Production host

```
อิมเมจ worker
  course-advisor-system-ingest-worker:7af085b   9d5c623b7e0a   rev 7af085b2e813…   <- พร้อมใช้งาน
  course-advisor-system-ingest-worker:617110e   c80cc9b21141   rev 617110e975dc…   <- rollback

คอนเทนเนอร์ที่ทำงาน (7)
  backend · frontend · caddy · postgres · ollama · webapi · db-viewer
  ไม่มี worker · ไม่มี ingest · restarts = 0 ทุกตัว

/home/ubuntu/course-advisor-system/
  docker-compose.gpu.yml · docker-compose.prod.yml
  docker-compose.staging.yml · docker-compose.yml
  ไม่มี docker-compose.worker.yml                      <- Option C
  staging/crawl : 0 ไฟล์ · mode 755 ubuntu:ubuntu

/home/ubuntu/release-7af085b-worker/   (mode 750)
  compose.worker-candidate-7af085b.yml               <- explicit worker execution config
  release-7af085b-worker.tar · manifest.tsv · src/ · build-worker-7af085b.log
```

ไม่ได้ลบ release directory หรือ backup ของรอบก่อนใด ๆ

---

## 20. Final verdict

### **F1 FIX: PASS**

ตัวแก้อยู่ใน `pipeline/crawl/http.py` ที่ commit `5d8f82b` · `STAGED_FILE_MODE = 0o644`
ตั้งด้วย `os.chmod()` หลังไฟล์ครบและผ่านทุกด่าน ก่อนคืนให้ผู้เรียก ·
ยืนยันในอิมเมจที่รันจริงว่า `chmod` อยู่หลังด่านอ่านครบและก่อน `Download(ok=True)` ·
regression 484/484 ผ่าน · isolated E2E 107/107 ผ่าน พร้อมเกณฑ์รับ
`GET /crawl-review/{id}/pdf` → 200 ทันทีโดยไม่มี workaround

### **F1 IMAGE READY ON PRODUCTION: PASS**

อิมเมจ worker ของ F1 ถูก build ตรวจยืนยัน และพร้อมใช้งานอยู่บนเครื่อง production
`:7af085b` · ID `9d5c623b7e0a` · OCI revision = DEPLOY_REV ·
`STAGED_FILE_MODE = 0o644` · uid/gid `1001:1001` · CMD/User/WorkDir เดิม

การรัน worker ยังคงต้องสั่งอย่างชัดแจ้งผ่าน Option C และ
**ไม่มี worker service ที่ถูกติดตั้งหรือกำลังทำงาน**

### **B1 DEPLOYMENT STRATEGY: OPTION C — ACCEPTED**

บันทึกแล้ว · ไม่ติดตั้ง `docker-compose.worker.yml` ลงโฟลเดอร์ production
(ยืนยันว่าไม่มีไฟล์ชื่อนี้ที่ใดบนเครื่องเลย) · `compose.worker-candidate-7af085b.yml`
คงอยู่ใน release directory · ต่างจาก compose ที่ DEPLOY_REV เพียง **1 บรรทัด**
คือ image reference · ทุก field ที่ห้ามเปลี่ยนเหมือนกันแบบ byte-for-byte ·
ไม่มี commit เพิ่ม · DEPLOY_REV ไม่เปลี่ยน · rollback image ยังอยู่

### **PRODUCTION DATA SAFETY: PASS**

วัดจริงเมื่อ 2026-09-30T01:11:12Z: 7/7 ค่าที่คาดไว้ตรงทุกค่า และ 13 รายการที่ตรวจ
เท่าเดิมกับ baseline ทั้งหมด · `crawl_decisions` = 0 · `courses code TEST%` = 0 ·
staging = 0 ไฟล์ · โหมด/เจ้าของของโฟลเดอร์ไม่เปลี่ยน · ไม่มี DB mutation ·
ไม่มี migration · รอบนี้แตะ production แบบ **อ่านอย่างเดียว**

### **PRODUCTION SERVICE SAFETY: PASS**

คอนเทนเนอร์ทั้งเจ็ด container ID และ StartedAt ตรงกับที่บันทึกไว้ตอน pre-deploy
และ post-deploy · restarts = 0 ทุกตัว · ไม่มีบริการใดถูก restart หรือ recreate ·
ไม่ได้แตะ Supabase · auth · Caddy · production compose

### **CRAWLER EXECUTED: NO**

### **WORKER EXECUTED: NO**

### **INGESTION EXECUTED: NO**

โปรเซสที่ตรงกับ `pipeline.crawl` / `crawl.sync` / `crawl.approve` / `pipeline.ingest`
= **0 ทั้งสี่แบบ** (วัดด้วยวิธีที่คำค้นไม่ปรากฏใน command line ของผู้ตรวจ) ·
คอนเทนเนอร์ worker/ingest = 0 · โปรเซส python ที่ไม่ใช่ของ OS มีเพียง uvicorn
ของ backend ที่รันมา 1 วัน 4 นาที · และข้อมูลทุกตัวชี้ไม่เปลี่ยนแม้ค่าเดียว

### **PRODUCTION ONE-JOB INGESTION: ยัง NO-GO**

จนกว่าจะมี legitimate new/changed PDF จาก `sci.pnru.ac.th` — ปัจจุบัน
`crawl_sources` ทั้ง 12 แถวเป็น `unchanged` · `staging_path` null ทั้งหมด ·
staging ว่าง · 6 แถวในคิวไม่ใช่ candidate (ดูข้อ 18)

---

## สิ่งที่ไม่ได้ทำในรอบนี้

ไม่ได้ copy candidate compose เข้าโฟลเดอร์ production · ไม่ได้แก้ production compose ·
ไม่ได้ commit เพิ่ม · ไม่ได้ push เพิ่ม · ไม่ได้ build อิมเมจใหม่ · ไม่ได้ restart service ใด ·
ไม่ได้รัน crawler · ไม่ได้รัน worker · ไม่ได้ ingestion · ไม่ได้สร้าง embedding ·
ไม่ได้ POST approve/ignore/undo · ไม่ได้เปลี่ยนข้อมูลในฐานข้อมูลแม้แถวเดียว ·
ไม่ได้ทำ migration · ไม่ได้แก้ Supabase · ไม่ได้แก้ Caddy · ไม่ได้แก้ auth ·
ไม่ได้ merge main · ไม่ได้ลบอิมเมจสำหรับ rollback · ไม่ได้แก้ S1

---

## STOP

การแก้ F1 จบครบวงจรแล้วในระดับที่อนุมัติไว้ — โค้ดแก้แล้ว มีชุดตรวจกันไม่ให้กลับมา
commit และ push แล้ว อิมเมจ build ตรวจยืนยันและพร้อมอยู่บนเครื่อง production
และกลยุทธ์การ deploy คือ Option C ซึ่งทำให้การรัน worker ยังต้องสั่งอย่างชัดแจ้ง

**รอ legitimate new/changed PDF จากเว็บคณะ**

ห้ามดำเนินการ pipeline ต่อ · ห้ามรัน crawler · ห้ามรัน worker · ห้าม ingestion
จนกว่าจะได้รับอนุมัติแยกสำหรับแต่ละขั้น

STOP
