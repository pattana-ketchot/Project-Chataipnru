# Phase 3C — Ingest Worker Only

## 1. ฐานที่ตรวจจริง และสรุปผล

| | |
|---|---|
| repository root | `D:/workspace/course-advisor-system-mko2` (git worktree) |
| branch | `mko-phase2` |
| HEAD ตอนเริ่ม | `0b86ef26976710dc3ad7aade86e55b183c821009` — **ตรงกับฐานที่กำหนด** |
| `origin/mko-phase2` | `0b86ef2` · ahead 0 / behind 0 |
| working tree ตอนเริ่ม | tracked ว่าง · untracked 38 รายการ ทั้งหมดอยู่ใน `docs/` (รายงานของเฟสก่อน) |
| ไฟล์ที่จะสร้างชนของเดิมไหม | ไม่ชน — `pipeline/crawl/approve.py`, `eval/crawl_ingest_worker_check.py` ยังไม่มี |
| `AGENTS.md` / `CLAUDE.md` | **ไม่มีในโปรเจค** (ค้นถึงระดับสองชั้นจาก root) |
| HEAD ตอนจบ | `0b86ef2` เท่าเดิม — **ไม่ commit ไม่ push** |

**สรุป: ทำสำเร็จ ไม่มีข้อใด blocked**

worker มีครบตามเกณฑ์ปิดงาน — ประตูอนุมัติ · การยึดงานที่ปลอดภัยใน transaction ·
การตรวจก่อนมีผลข้างเคียง · ใช้หลักสูตรที่มีอยู่แล้วเท่านั้น · เรียก `pipeline.ingest.run()`
ตัวเดิมโดยไม่แก้ · สัญญา embedding · หาเอกสารด้วย SHA · ปิดงานเฉพาะเมื่อสำเร็จ ·
ลองใหม่และกันซ้ำที่พิสูจน์ได้

**เทสต์ของ worker 187 ข้อ ผ่านทั้งหมด ไม่มีข้อข้าม** · regression 4 ชุด ผ่านทั้งหมด

---

## 2. ผลตรวจ source (พร้อมเลขบรรทัด)

### `pipeline/ingest.py`

| เรื่อง | ที่พบจริง |
|---|---|
| signature | `run(pdf_path: str, title: str, course_code: str \| None, provider: str \| None) -> None` — **บรรทัด 170** |
| return | ไม่มี `return <ค่า>` ที่ใดเลย · ออกก่อนกำหนดที่ 188 และ 211 → **คืน `None` เสมอ** |
| อ่าน env เมื่อไหร่ | `load_dotenv(..., override=False)` ตอน import **บรรทัด 46** (env จริงชนะ) · `INGEST_DATABASE_URL` **172** · `OLLAMA_BASE_URL` **178** · `EMBED_MODEL` **179** — ทั้งสามอ่าน **ตอนเรียก run() ไม่ใช่ตอน import** |
| ค่าเริ่มต้นของโมเดล | `nomic-embed-text` (บรรทัด 179) ซึ่งให้เวกเตอร์ 768 มิติ |
| **ไม่อ่าน `EMBED_DIM` เลย** | ค้นทั้งไฟล์ไม่พบ · `OllamaConnector.embed()` (`llm/connector.py:105-111`) ก็ไม่ตรวจความยาว |
| course lookup/creation | `get_or_create_course()` **104** — `SELECT id FROM courses WHERE code = %s` ที่ **107** ถ้าเจอคืนเลย (110) **ถ้าไม่เจอ INSERT สร้างใหม่ที่ 111-115** |
| SHA dedup | `already_ingested()` **80** · query ที่ **98**: `file_sha256 = %s AND extraction_status = 'done'` — **ไม่กรอง course_id** · เรียกที่ **186** ก่อน embed |
| dedup ชั้นสอง | `insert_document()` **118** · `ON CONFLICT (course_id, file_sha256) DO UPDATE ... WHERE extraction_status <> 'done'` **125-129** · คืน `None` ถ้าทำเสร็จแล้ว (140) → run() ออกที่ **211** |
| transaction | A: course + document(`processing`) **204-208** · B: chunks + `done` **215-217** · C: `failed` **221-222** · `psycopg.connect` เป็น context manager **198** จึง commit เมื่อออก |
| embedding | `embed_chunks(connector, chunks)` **196** — เกิด **ก่อน** เปิด connection ที่ 198 |
| `SystemExit` | `raise SystemExit(...)` **174** เมื่อไม่มี `INGEST_DATABASE_URL` |
| ผลข้างเคียงอื่น | อ่าน `OCR_TEXT_JSON` ผ่าน `apply_ocr()` **190** · `storage_path` ที่บันทึกคือ `str(pdf_path)` **207** · `original_filename` คือ `Path(pdf_path).name` **207** |

### `pipeline/extract_pdf.py` — ตัวตรวจ PDF ที่มีอยู่แล้ว

`MAX_PDF_BYTES = 50 MB` **22** · `PDF_MAGIC = b"%PDF-"` **23** · `InvalidPdfError` **26** ·
`_validate_file()` **43-57** ตรวจ: เป็นไฟล์จริง (44) · ขนาด `0 < n ≤ 50 MB` (47-49) ·
magic bytes (51-55) · `extract_pdf()` **60-73** อ่าน bytes ครั้งเดียวแล้ว hash bytes ชุดนั้น
(62) และ `fitz.open(stream=raw_bytes, ...)` (66) พร้อมปฏิเสธไฟล์ที่ใส่รหัส (67-68)

→ **ใช้ตัวนี้เป็นตัวตรวจของ worker ได้ตรง ๆ** เป็นโค้ดเส้นเดียวกับที่ `run()` จะเรียก
(`extract_document` ที่ `ingest.py:182`) ถ้าผ่านที่ worker ก็จะผ่านที่ run() · PyMuPDF
มีอยู่แล้วในเครื่อง (1.28.2) และใน `pipeline/requirements.txt` — **ไม่ได้ติดตั้งอะไรเพิ่ม**

### `db/` — schema และสิทธิ์

| เรื่อง | ที่พบจริง |
|---|---|
| มิติ embedding | `db/schema.sql:122` → `embedding VECTOR(1024) NOT NULL` |
| `mko.crawl_sources.document_id` | **มีจริง** — `003_crawl_sources.sql:77` `UUID REFERENCES public.course_documents(id) ON DELETE SET NULL` |
| `status` รับค่า `ingested` | `003:58-60` |
| `staging_path`, `file_sha256` | `003:71,73` |
| `advisor_ingest` บน `mko.crawl_sources` | `003:128` `SELECT, INSERT, UPDATE` — **ไม่มี DELETE** |
| `crawl_decisions` คอลัมน์ ingest | `004:59` `ingest_started_at` · `60` `ingest_finished_at` · `61` `ingest_error` · `62` `document_id` |
| CHECK ที่บังคับลำดับ | `004:73-74` `ingest_finished_at IS NULL OR ingest_started_at IS NOT NULL` · `004:76-77` `decision = 'approve' OR (ingest_started_at IS NULL AND document_id IS NULL)` |
| ดัชนีกันซ้ำ | `004:83-84` partial unique `(crawl_source_id, file_sha256) WHERE superseded_at IS NULL` |
| คิวของ worker | `004:87-89` partial index `WHERE superseded_at IS NULL AND decision='approve' AND ingest_finished_at IS NULL` |
| `advisor_ingest` บน `crawl_decisions` | `004:144` `SELECT, INSERT, UPDATE` |
| `advisor_ingest` บน public | `db/20-roles.sh:53` `SELECT, INSERT, UPDATE ON courses, course_documents` · `57` `+ DELETE ON course_chunks` |

### `backend/app/services/crawl_review.py` — ⚠️ ช่องที่ต้องปิดด้วย locking

`undo()` **212** ตรวจที่ **225**: `if current["ingest_finished_at"] is not None or current["document_id"] is not None`
และ UPDATE ที่ **231** มีเงื่อนไข `superseded_at IS NULL AND ingest_finished_at IS NULL`

> **ไม่มีที่ใดตรวจ `ingest_started_at`** — แปลว่าถ้า worker ยึดงานแล้ว commit ทิ้งไว้
> คนกดถอนได้กลางทาง เอกสารจะเข้าคลังไปแล้วโดยที่การอนุมัติถูกถอน
>
> ปิดด้วยการถือ row lock ตลอดงาน (หัวข้อ 4) **ไม่ได้แก้ backend** ตามข้อห้าม

### อื่น ๆ

| เรื่อง | ที่พบจริง |
|---|---|
| ด่านตรวจมิติที่มีอยู่ | `backend/app/main.py:22-44` · query ที่ **32-34**: `SELECT atttypmod FROM pg_attribute WHERE attrelid='course_chunks'::regclass AND attname='embedding'` → **ใช้ query เดียวกันใน worker** |
| `document_store` | `backend/app/services/document_store.py:94-98` — สแกน `rglob("*.pdf")` ใต้ `DOCUMENTS_DIR` ทำ index `sha256 → path` ด้วย `setdefault` · สร้าง index ครั้งเดียวต่อโปรเซส (**105-108**) · `open()` ตรวจ `is_relative_to(root)` (123) และ sha ซ้ำ (127) → **ชื่อไฟล์ไม่สำคัญต่อการค้น** |
| `staging_store` | `backend/app/services/staging_store.py` — ใช้ร่วมไม่ได้เพราะ import `app.core.config` ที่ต้องมี `DATABASE_URL`/`JWT_SECRET` · worker จึงทำด่านของตัวเองตามกติกาเดียวกัน |
| `CRAWL_STAGING_DIR` | `backend/app/core/config.py:76` — worker อ่านชื่อตัวแปรเดียวกันเพื่อให้ชี้ที่เดียวกัน |
| compose | **ไม่มี service หรือ Dockerfile ของ pipeline เลย** (`docker-compose*.yml` มีแค่ postgres/ollama/backend/frontend/webapi/caddy · Dockerfile มีแค่ backend/frontend/webapi) |

### ข้อขัดแย้งกับ design/reports

| รายงานเดิมบอก | source บอก |
|---|---|
| `run()` คืน `None` | ✅ ตรง |
| แยก human decision ออกจาก crawler state · ผูก `crawl_source_id + file_sha256` · active = `superseded_at IS NULL` · partial unique index | ✅ ตรงทั้งหมด |
| `bge-m3` / 1024 | ✅ `docker-compose.prod.yml:74-75` และ `schema.sql:122` — แต่ **`ingest.py` ไม่ได้บังคับเลย** ค่าเริ่มต้นคือ 768 มิติ |
| `document_store` ทำ index ตอนเริ่มโปรเซส | ✅ ตรง |
| Phase 3A รายงานว่าจะเพิ่ม `ingest-worker` container | **ไม่ทำ** — ไม่มี pipeline image ให้ต่อยอด และ CLI เดิมพอสำหรับ local/test ตามข้อ §9 ของคำสั่ง |

---

## 3. สิ่งที่สร้าง และคำสั่งรัน

### ไฟล์

```
pipeline/crawl/approve.py            535 บรรทัด   worker
eval/crawl_ingest_worker_check.py    833 บรรทัด   เทสต์ 187 ข้อ
```

### คำสั่งรันแบบครั้งเดียวจบ (ตรวจแล้วว่าใช้ได้จริง)

```bash
INGEST_DATABASE_URL='postgresql://advisor_ingest:<PASSWORD>@<HOST>:<PORT>/<DB>' \
EMBED_MODEL=bge-m3 \
EMBED_DIM=1024 \
OLLAMA_BASE_URL='http://<OLLAMA_HOST>:11434' \
CRAWL_STAGING_DIR='/path/to/staging/crawl' \
DOCUMENTS_DIR='/path/to/documents' \
python -m pipeline.crawl.approve --max-jobs 1
```

`--database-url` ใช้แทน `INGEST_DATABASE_URL` ได้ · `--max-jobs` ค่าเริ่มต้น 1 ·
ออกด้วยรหัส 1 ถ้ามีงานล้มเหลว 0 ถ้าไม่มี

**ไม่มี daemon ไม่มี watch ไม่มี polling ไม่มี sleep** — ยึดงานไม่เกินที่กำหนด
หมดงานที่ยึดได้ก็ `break` ออกทันที (`work()` บรรทัด 400-431)

### ไม่แก้ compose

ตรวจแล้วว่า**ไม่มี image หรือ service ของ pipeline อยู่เลย** การเพิ่ม `ingest-worker`
ต้องสร้าง Dockerfile ใหม่ + แก้ compose ซึ่งเกินความจำเป็นสำหรับ local/test
CLI เดิมพอ — เหมือน `pipeline.crawl.sync` ของ Phase 2 ที่ไม่มีคอนเทนเนอร์ของตัวเองและ
รันจริงบน production ได้ด้วยการ `docker run --rm` จาก backend image ที่มีอยู่
(ดู `docs/CRAWLER_PRODUCTION_VERIFY_REPORT.md`) **จึงไม่แตะ `docker-compose*.yml`**

---

## 4. Transaction / concurrency

### เงื่อนไขที่ยึดได้ (`CLAIM_SQL` บรรทัด 317-337)

```sql
WHERE d.superseded_at      IS NULL
  AND d.decision           =  'approve'
  AND d.ingest_finished_at IS NULL
  AND d.id <> ALL(%(skip)s::uuid[])
ORDER BY d.decided_at, d.id
  FOR UPDATE OF d SKIP LOCKED
LIMIT 1
```

- `FOR UPDATE **OF d**` ล็อกเฉพาะแถว `crawl_decisions` **ไม่ล็อก `crawl_sources`**
  เพื่อไม่ขวาง crawler ที่ upsert แถวต้นทางทุกรอบ
- เรียงด้วย `(decided_at, id)` — แน่นอน ไม่ขึ้นกับ plan
- `skip` คือรายการงานที่รอบนี้แตะแล้ว กันหยิบซ้ำในโปรเซสเดียวจนวนไม่จบ
- **ยึดทีละงาน** ไม่ยึดหลายงานใน transaction เดียว ไม่งั้นงานที่เหลือจะถูกล็อกค้างไว้
  ทั้งที่ worker ตัวอื่นว่างอยู่

### เจ้าของงานคือ row lock ไม่ใช่คอลัมน์

ถือ transaction ที่ล็อกแถว decision ไว้ **ตั้งแต่ยึดงานจนปิดงาน** และ `ingest_started_at`
ถูกตั้งใน transaction เดียวกัน (ยังไม่ปรากฏต่อผู้อื่นจนกว่าจะ commit)

| คำถาม | คำตอบที่พิสูจน์แล้ว |
|---|---|
| worker อีกตัวยึดงานเดียวกันได้ไหม | **ไม่ได้** — `SKIP LOCKED` ข้ามแถวที่ถูกล็อก ทดสอบด้วยสาม connection จริง: สองตัวได้คนละงาน ตัวที่สามได้ `None` |
| คำสั่งถอนของ backend แทรกกลางทางได้ไหม | **ไม่ได้** — `UPDATE mko.crawl_decisions SET superseded_at ...` รอที่แถวเดียวกัน ทดสอบด้วย role ของ backend ที่ตั้ง `lock_timeout='800ms'` แล้วได้ `LockNotAvailable` จริง · พอ worker commit เสร็จ คำสั่งถอนจะเห็น `ingest_finished_at` แล้วถูกปฏิเสธด้วยเงื่อนไขของ `crawl_review.py:231` เอง |
| ถือ lock แล้วทำให้ ingest รอตัวเองไหม | **ไม่** — `run()` เปิด connection ของตัวเอง (`ingest.py:96, 198`) และแตะแค่ `courses`, `course_documents`, `course_chunks` ไม่แตะ `mko.*` เลย |
| rollback ของ worker ย้อน knowledge writes ได้ไหม | **ไม่ได้** — `run()` commit บน connection ของมันเอง การ rollback ของ worker ย้อนได้แค่แถวใน `mko.*` ที่ worker เขียน ผลคือมีกรณี "เอกสารเข้าคลังแล้วแต่งานยังไม่ปิด" ซึ่งกู้ได้ (ดูล่าง) |

**ราคาที่ยอมจ่ายและบันทึกไว้**: คำขอถอนที่เข้ามาระหว่าง worker ทำงานจะค้างรอจนงานจบ
(backend ไม่ได้ตั้ง `lock_timeout` เอง) และ transaction เปิดค้างนานเท่าเวลา embedding
ดูข้อจำกัดหัวข้อ 12

### SHA ของต้นทางเปลี่ยนระหว่างงาน

`finalize()` (บรรทัด 356-381) อัปเดตต้นทางแบบมีเงื่อนไขและตรวจจำนวนแถวที่โดน

```sql
UPDATE mko.crawl_sources SET status='ingested', document_id=%(doc)s
 WHERE id = %(sid)s AND file_sha256 = %(sha)s      -- sha ที่อนุมัติไว้
```

`rowcount == 1` → ตั้ง `ingested` ตามปกติ · `rowcount == 0` (crawler เปลี่ยนไฟล์แล้ว) →
**ไม่ตั้ง `ingested` ให้ไฟล์ใหม่ด้วยการอนุมัติเก่า** แต่ยังปิด decision พร้อมเขียน
`ingest_error = 'source_sha_changed_after_ingest'` เพื่อให้คนมาดู — งานที่ทำไปแล้วถูกต้อง
และต้องไม่ถูกทำซ้ำ ทดสอบแล้ว

### SHA เดียวกันข้ามต้นทาง

- **หลักสูตรเดียวกัน**: unique `(course_id, file_sha256)` ของ `course_documents` +
  `ON CONFLICT` ที่ `ingest.py:125` ทำให้ตัวที่สองไม่สร้างเอกสารใหม่ และ `already_ingested()`
  ที่ **186** ทำให้ไม่ embed ซ้ำ ทดสอบแล้ว: สองต้นทาง sha เดียวกัน → สำเร็จทั้งคู่ ·
  เอกสารฉบับเดียว · คำนวณเวกเตอร์ครั้งเดียว · ทั้งสอง decision ผูกเอกสารฉบับเดียวกัน
- **สองงานพร้อมกันจริง**: ตัวที่สองจะบล็อกที่ unique index ตอน INSERT จนตัวแรก commit
  แล้วเข้าทาง `DO UPDATE ... WHERE extraction_status <> 'done'` → ได้ `None` → ออกที่ 211
- **คนละหลักสูตร**: `already_ingested()` ไม่กรอง course_id จึงคืน `True` และ run() ออกก่อน
  โดยไม่สร้างอะไรให้หลักสูตรที่อนุมัติ worker จึงหาเอกสารไม่เจอ → error
  `document_course_conflict` ให้คนตัดสิน (ทดสอบแล้ว) **ไม่ผูกข้ามหลักสูตรเงียบ ๆ**

### crash และการกู้

| ตายตอนไหน | ผล | รอบถัดไป |
|---|---|---|
| หลังยึดงาน ก่อน run() | transaction ถูกยกเลิก `ingest_started_at` ไม่เคยถูกบันทึก | งานกลับเป็นงานว่างทันที **ไม่มี claim ค้าง ไม่ต้องมีคอลัมน์ lease** |
| หลัง run() commit ก่อน `finalize` | เอกสาร + chunk อยู่ในคลังแล้ว · decision ยังไม่ปิด | ยึดงานเดิมได้ → `already_ingested()` คืน `True` → run() ออกก่อนโดยไม่ embed ซ้ำ → หาเอกสารด้วย sha+course → ปิดงาน **ทดสอบแล้วว่าไม่เพิ่มเอกสาร ไม่เพิ่ม chunk ไม่ embed ซ้ำ** |
| เขียน `ingest_error` ไม่ได้เพราะ DB ล่ม | `record_error()` คืน `False` → worker โยนต่อ → โปรเซสออกด้วยรหัสไม่เป็นศูนย์ พร้อม log ที่ไม่มีข้อมูลอ่อนไหว | ดูข้อจำกัดหัวข้อ 12 |

**ไม่มีการ reset `ingest_started_at` ของใครทั้งนั้น** และไม่มี retry วนในตัว — รอบใหม่
ต้องมีคนสั่งรันใหม่

`lock_timeout = '5s'` ตั้งต่อ connection (บรรทัด 411-413) กันการรอค้างที่ไม่คาดคิด

---

## 5. Validation และความปลอดภัย

ลำดับใน`process()` (บรรทัด 385-...) เรียงจากถูกไปแพง และทุกด่านอยู่ **ก่อน** ผลข้างเคียง

```
staging_root() → resolve_staged() → snapshot → validate_pdf(snapshot)
   → lock_existing_course() → check_embedding_contract() → run() → ...
```

| ด่าน | ทำอะไร |
|---|---|
| root | `CRAWL_STAGING_DIR` ว่างหรือไม่ใช่โฟลเดอร์ → `staging_dir_unset`/`staging_dir_invalid` **ไม่ถอยไป cwd ไม่รับ path จาก CLI** |
| containment | `Path(...).resolve()` แล้ว `is_relative_to(root)` — **ไม่เทียบสตริงนำหน้า** ปฏิเสธ `../`, absolute นอก root, symlink/junction escape และโฟลเดอร์ข้างเคียงที่ชื่อขึ้นต้นเหมือนกัน |
| ชนิดไฟล์ | ต้อง `exists()` และ `is_file()` — โฟลเดอร์และไฟล์พิเศษถูกปฏิเสธ |
| PDF | `extract_pdf()` เดิม: ขนาด `0 < n ≤ 50 MB` · magic `%PDF-` · `fitz.open()` สำเร็จ · ไม่ใส่รหัส · `page_count > 0` |
| SHA | ต้องตรงทั้ง `crawl_decisions.file_sha256` **และ** `crawl_sources.file_sha256` ปัจจุบัน แยกเป็นสองข้อความผิดพลาด **ไม่มีที่ใดแก้ SHA ใน decision หรืออนุมัติใหม่เอง** |
| TOCTOU | **ทำสำเนาก่อนแล้วตรวจสำเนานั้น** แล้วส่งสำเนาให้ `run()` bytes ที่ผ่านการตรวจกับ bytes ที่ ingest จึงเป็นไฟล์เดียวกันในโฟลเดอร์ของ worker ที่ไม่มีใครเขียนได้ · คงชื่อไฟล์เดิมไว้เพราะ `run()` ใช้เป็น `original_filename` · ลบเฉพาะไฟล์ที่ worker สร้าง (`TemporaryDirectory`) |
| หลักสูตร | ต้องมีอยู่จริง + ตรึงด้วย `FOR SHARE` (ดูหัวข้อ 6) |
| สิทธิ์ | ใช้ `advisor_ingest` ตามสิทธิ์เดิม ไม่ยกระดับ ไม่เพิ่มสิทธิ์ให้ backend |
| ไม่ดาวน์โหลด | ไม่มี `httpx`, ไม่มี URL fetch, ไม่แตะ crawler ในไฟล์นี้เลย |

### ข้อความผิดพลาดที่ปลอดภัย

เก็บเป็นรหัสสั้น + รายละเอียดที่ปลอดภัย ตัดที่ 300 ตัวอักษร (`_ERROR_MAX`)
**ใช้ชนิดของ exception ไม่ใช่ข้อความ** เพราะ `InvalidPdfError` ใส่ที่อยู่ไฟล์ไว้ในข้อความ
(`extract_pdf.py:45`) — เทสต์ยืนยันว่า `ingest_error` ไม่มี staging path, documents path,
`/tmp`, `C:\`, `postgresql://`, ส่วน user:password ของ DSN หรือ `Traceback`

รหัสที่ใช้: `staging_dir_unset` · `staging_dir_invalid` · `staged_path_missing` ·
`path_outside_staging_root` · `staged_file_missing` · `staged_not_regular_file` ·
`snapshot_failed` · `pdf_invalid` · `pdf_unreadable` · `pdf_no_pages` ·
`sha_mismatch_decision` · `sha_mismatch_source` · `course_not_found` ·
`embed_model_mismatch` · `embed_dim_mismatch` · `embed_probe_failed` ·
`embed_probe_mismatch` · `ingest_systemexit` · `ingest_failed` · `document_not_found` ·
`document_not_done` · `document_ambiguous` · `document_course_conflict` ·
`publish_failed` · `publish_name_collision` · `publish_outside_root` ·
`documents_dir_unset` · `documents_dir_invalid` · `claim_lost` · `finalize_lost` ·
`source_sha_changed_after_ingest`

---

## 6. หลักสูตรที่มีอยู่แล้วเท่านั้น

`lock_existing_course()` (บรรทัด 245-265)

```sql
SELECT id::text, title FROM courses WHERE code = %s FOR SHARE
```

- ใช้ `course_code` ที่ **คนยืนยันใน decision** ไม่ใช่ `crawl_sources.course_code` ที่
  crawler เดาไว้ ไม่มี fuzzy matching ที่ใดในไฟล์นี้
- ไม่พบ → `course_not_found` **ก่อน** เรียก run() → ไม่มีอะไรเขียนลงคลัง ไม่มีหลักสูตรใหม่
- **ไม่มีที่ใดเรียก `get_or_create_course()` และไม่มี `INSERT INTO courses` เลย**
  (ค้นทั้งไฟล์) และ role `advisor_ingest` มี INSERT บน courses ได้ตามสิทธิ์เดิม
  จึงต้องกันที่ตรรกะ — ซึ่งทำด้วย `FOR SHARE`

### พิสูจน์ว่า run() เข้าทาง "ใช้ของเดิม" แน่นอน

`get_or_create_course()` สร้างหลักสูตรใหม่ถ้าหา `code` ไม่เจอ (`ingest.py:111-115`)
ถ้าใครลบหลักสูตรระหว่างที่เราตรวจเสร็จกับตอน run() ค้นหา หลักสูตรจะถูกสร้างขึ้นใหม่เงียบ ๆ

`FOR SHARE` ตรึงแถวไว้ในตัว transaction ของ worker ตลอดงาน คำสั่ง `DELETE FROM courses`
จะรอจนงานจบ ส่วน `SELECT` ธรรมดาของ `run()` ไม่ถูกบล็อก จึงเห็นแถวเดิมและเข้าทาง
`return row[0]` ที่บรรทัด 110 เสมอ — **ทดสอบแล้วว่า DELETE ถูกบล็อกจริง**
(`lock_timeout='800ms'` → `LockNotAvailable`) และ `FOR SHARE` ใช้ได้ด้วยสิทธิ์
`UPDATE ON courses` ที่ `advisor_ingest` มีอยู่แล้ว (`20-roles.sh:53`) — **ไม่เพิ่มสิทธิ์**

---

## 7. สัญญาของ embedding

`check_embedding_contract()` (บรรทัด 118-158) ตรวจสามชั้น **ก่อน** เรียก run()

| ชั้น | ตรวจอะไร | ล้มเหลวเป็น |
|---|---|---|
| 1 | `EMBED_MODEL == "bge-m3"` (ค่าที่ `run()` จะอ่านจริงที่ `ingest.py:179`) | `embed_model_mismatch` |
| 2 | `EMBED_DIM == 1024` และ `atttypmod` ของ `course_chunks.embedding == 1024` — **query เดียวกับด่านของ backend** (`main.py:32-34`) | `embed_dim_mismatch` |
| 3 | เรียก `OllamaConnector(...).embed()` หนึ่งครั้งแล้วนับความยาวเวกเตอร์จริง | `embed_probe_mismatch` / `embed_probe_failed` |

ชั้น 3 จำเป็นเพราะชั้น 1 พิสูจน์แค่ว่า "ตั้งค่าไว้ถูก" ไม่ได้พิสูจน์ว่าโมเดลที่ตอบกลับมา
ให้เวกเตอร์ขนาดนั้นจริง (`OllamaConnector.embed()` ไม่ตรวจความยาว และ `ingest.py`
ไม่อ่าน `EMBED_DIM` เลย)

**ไม่มี fallback ไปโมเดลอื่น ไม่ตัด/เติมเวกเตอร์ ไม่แก้ vector schema ไม่ re-embed ของเก่า**
ผิดสัญญา = error ก่อนเริ่ม ingest

### สิ่งที่ยังไม่ได้ตรวจด้วยโมเดลจริง

เทสต์แทน `pipeline.ingest.embed_chunks` และ `OllamaConnector` ของ worker ด้วยตัวปลอมที่
คืนเวกเตอร์ 1024 มิติ **ไม่ได้ติดต่อบริการ embedding ใด ๆ และไม่ดาวน์โหลดโมเดล**
จึงยังไม่ได้ยืนยันว่า `bge-m3` ตัวจริงบน production คืน 1024 มิติ — ชั้น 3 จะเป็นตัวตรวจ
ตอนรันจริง นี่ไม่ใช่การยืนยันแบบ end-to-end กับโมเดลจริง

---

## 8. State transitions

| เหตุการณ์ | `ingest_started_at` | `ingest_finished_at` | `ingest_error` | `crawl_decisions.document_id` | `crawl_sources` |
|---|---|---|---|---|---|
| ไม่มีการอนุมัติ / `ignore` / ถูกถอน / ปิดไปแล้ว | ไม่แตะ | ไม่แตะ | ไม่แตะ | ไม่แตะ | ไม่แตะ · ไม่ ingest ไม่ embed |
| ยึดงานสำเร็จ (ยังไม่ commit) | ตั้งใน transaction ที่ถือ lock | NULL | ล้างเป็น NULL | NULL | ไม่แตะ |
| validation / หลักสูตร / สัญญา embedding ไม่ผ่าน | ตั้ง (transaction แยก) | **NULL** | รหัสสั้นที่ปลอดภัย | NULL | ไม่แตะ · **ไม่เป็น ingested** |
| `run()` โยน exception หรือ `SystemExit` (รวม code 0) | ตั้ง | **NULL** | `ingest_failed:` / `ingest_systemexit:` | NULL | ไม่แตะ |
| run() จบ แต่หาเอกสารที่ `done` ไม่ได้ / ยังไม่ done / คนละหลักสูตร / กำกวม | ตั้ง | **NULL** | `document_*` | NULL | ไม่แตะ |
| วางไฟล์ในที่เก็บไม่สำเร็จ | ตั้ง | **NULL** | `publish_*` / `documents_dir_*` | NULL | ไม่แตะ |
| สำเร็จครบ และ source SHA ยังตรง | ตั้ง | **ตั้ง** | **ล้างเป็น NULL** | ตั้ง | `status='ingested'` + `document_id` |
| สำเร็จ แต่ crawler เปลี่ยน source SHA ไปแล้ว | ตั้ง | **ตั้ง** | `source_sha_changed_after_ingest` | ตั้ง | **ไม่แตะ** (conditional update โดน 0 แถว) |
| เรียกซ้ำหลังสำเร็จ | ไม่ยึดซ้ำ (เงื่อนไข `ingest_finished_at IS NULL` คัดออก) | — | — | — | ไม่เปลี่ยน · ไม่ embed ซ้ำ ไม่เพิ่มเอกสาร/chunk |
| crash หลัง knowledge commit ก่อน finalize | ยกเลิกไปกับ transaction | NULL | จากรอบนั้น | NULL | ไม่แตะ · รอบถัดไปกู้เองแบบ idempotent |

**เกณฑ์สำเร็จคือ `ingest_finished_at`** งานที่ล้มเหลวจึงยังมีทางลองใหม่เสมอ
เพราะเงื่อนไขการยึดงานไม่ได้ดู `ingest_started_at` หรือ `ingest_error`

`ingest_error` ถูกล้างตอนยึดงานทุกครั้ง (บรรทัด 345-348) แล้วเขียนใหม่ต่อรอบ —
**ไม่ลบและไม่แก้ `decision`, `decided_by`, `decided_at`, `course_code` ที่เป็นประวัติการอนุมัติ**

---

## 9. ที่เก็บเอกสาร

`publish_document()` (บรรทัด 268-306)

- จำเป็น เพราะ `document_store` หาไฟล์จากการสแกน `DOCUMENTS_DIR` ไม่ได้ใช้
  `course_documents.storage_path` (ซึ่ง `run()` บันทึกเป็นที่อยู่สำเนาชั่วคราว)
  ถ้าไม่วางไฟล์ `/documents/{id}/pdf` จะเปิดไม่ได้
- ทำ **หลัง** ingestion สำเร็จเท่านั้น · **ไม่ย้ายและไม่ลบไฟล์ต้นทางใน staging**
- ชื่อไฟล์: ใช้ชื่อเดิมของไฟล์ใน staging (การค้นใช้ sha ชื่อจึงไม่กระทบ index
  แต่ช่วยให้คนเปิดโฟลเดอร์แล้วรู้ว่าไฟล์ไหนคืออะไร)
- **มีไฟล์เนื้อเดียวกันอยู่แล้ว → ใช้ของเดิม ไม่เขียนเพิ่ม** (ทดสอบแล้ว)
- **ชื่อซ้ำแต่เนื้อต่าง → ไม่เขียนทับ** เปลี่ยนไปใช้ `<sha12>_<ชื่อ>` · ถ้ายังซ้ำ → `publish_name_collision`
- วางแบบ atomic: เขียนลง `.publish_*` ในโฟลเดอร์เดียวกันแล้ว `os.replace()` ตัวที่ไปสแกน
  จึงไม่เคยเจอไฟล์ครึ่ง ๆ · ตรวจ containment ซ้ำหลังวาง
- `DOCUMENTS_DIR` ว่างหรือไม่ใช่โฟลเดอร์ → `documents_dir_unset`/`documents_dir_invalid`
  **fail closed ไม่ปิดงาน ไม่ตั้ง ingested** ทดสอบแล้วว่าลองใหม่แล้วสำเร็จ **โดยไม่ embed ซ้ำ**

### ฐานข้อมูลกับไฟล์ไม่ใช่ transaction เดียวกัน

ช่องว่างที่เหลืออยู่: วางไฟล์สำเร็จแล้วแต่ `COMMIT` ของ worker ล้ม → มีไฟล์ส่วนเกินใน
`DOCUMENTS_DIR` ที่ยังไม่มี decision ชี้ถึง ไม่เป็นอันตราย (การค้นใช้ sha และ
`document_store.open()` ตรวจ sha ซ้ำอยู่แล้ว) และรอบถัดไปจะใช้ไฟล์เดิมซ้ำ
ทดสอบด้วยการทำให้ `DOCUMENTS_DIR` ใช้ไม่ได้แล้วลองใหม่

### ข้อจำกัดที่บันทึกไว้ — index ตอนเริ่มโปรเซส

`document_store` สร้าง index ครั้งเดียวต่อโปรเซส (`document_store.py:105-108`)
ไฟล์ที่เพิ่มหลัง backend เริ่มทำงานจะยังไม่ปรากฏจนกว่าจะมีขั้นตอน refresh/restart
ที่ได้รับอนุมัติในอนาคต

> **Phase 3C ไม่ได้แก้ `document_store` ไม่ได้ restart backend และไม่ได้ deploy อะไร**

---

## 10. ไฟล์ที่เพิ่ม / แก้

### เพิ่ม 2 ไฟล์

| ไฟล์ | บรรทัด | เหตุผล |
|---|---|---|
| `pipeline/crawl/approve.py` | 535 | worker — อยู่ใน `pipeline/crawl/` ตามที่คำสั่งระบุ และอยู่ข้าง ๆ `sync.py` ที่ผลิตแถวที่มันอ่าน |
| `eval/crawl_ingest_worker_check.py` | 833 | เทสต์ — ตามแบบแผนของ `eval/crawl_*_check.py` เดิม |

### แก้ของเดิม: **ไม่มีเลย**

```
git status --short --untracked-files=no   →  ว่าง
git diff -- pipeline/ingest.py           →  ว่าง
```

**ยืนยัน `pipeline/ingest.py` ไม่ถูกแก้** — sha256 ของไฟล์ในดิสก์ (หลัง normalize LF)
เท่ากับของใน HEAD: `90a03872cc88a053dc9f1b29…`

ตรวจทีละพาธแล้วว่าไม่ถูกแก้: `db/` · `backend/` · `frontend/` · `docker-compose.yml` ·
`docker-compose.prod.yml` · `Caddyfile` · `pipeline/ingest.py` · `pipeline/crawl/sync.py` ·
`pipeline/crawl/state.py` · `pipeline/crawl/http.py`

`git diff --check` ของไฟล์ใหม่: ว่าง (ไม่มี whitespace เสีย)

---

## 11. Tests

### `eval/crawl_ingest_worker_check.py` — **187 ข้อ ผ่านทั้งหมด · ไม่ผ่าน 0 · ข้าม 0**

```bash
python eval/crawl_ingest_worker_check.py \
  --database-url postgresql://<owner>:<PASSWORD>@127.0.0.1:<PORT>/crawl_test \
  --ingest-url   postgresql://<ingest-role>:<PASSWORD>@127.0.0.1:<PORT>/crawl_test \
  --api-url      postgresql://<api-role>:<PASSWORD>@127.0.0.1:<PORT>/crawl_test
```

| หมวด | ข้อ |
|---|---|
| [1] ทางปกติ — อนุมัติแล้ว ไฟล์ถูก หลักสูตรมีอยู่ | 15 |
| [1b] เรียกซ้ำหลังสำเร็จ | 4 |
| [2] งานที่ต้องไม่ถูกนำเข้า (ไม่อนุมัติ / ignore / ถูกถอน / ปิดแล้ว) | 20 |
| [3] ซ้ำ — sha เดิม ข้ามต้นทาง และข้ามหลักสูตร | 10 |
| [4] ยึดงานพร้อมกันสองตัว + คำสั่งถอนถูกบล็อก | 6 |
| [5] แข่งกับการถอนและกับ crawler | 5 |
| [6] ความปลอดภัยของที่อยู่ไฟล์ | 32 |
| [7] ลายนิ้วมือและรูปแบบไฟล์ | 20 |
| [8] หลักสูตรต้องมีอยู่จริง + ตรึงแถว | 9 |
| [9] สัญญาของ embedding | 16 |
| [10] `run()` ล้มเหลวแบบต่าง ๆ | 18 |
| [11] `run()` ไม่พัง แต่หลักฐานไม่ครบ | 8 |
| [12] ลองใหม่หลังล้มเหลว และกู้หลังล้มกลางทาง | 11 |
| [13] ที่เก็บเอกสาร | 7 |
| [14] สิทธิ์ของ role | 7 |
| **รวม** | **187** |

### ฐานข้อมูลทดสอบและด่านกัน

- ฐานข้อมูล **`crawl_test` แยกคนละฐาน** สร้างใหม่สำหรับรอบนี้ · role แยกสามตัว
  (`crawl_test_owner` เตรียมข้อมูล · `crawl_test_ingest` = สิทธิ์เท่า `advisor_ingest` ·
  `crawl_test_api` = สิทธิ์เท่า `advisor_api`) สิทธิ์ลอกจาก `db/20-roles.sh` และ
  `003`/`004` ทีละบรรทัด
- staging และ documents เป็นโฟลเดอร์ชั่วคราวใหม่ ไม่ใช่ของ production
- **ด่านสองชั้นก่อนแตะข้อมูลใด**: ชื่อฐานข้อมูลใน URL ต้องอยู่ใน allowlist
  (`crawl_test`, `ingest_worker_test`) และห้ามมีคำว่า `course_advisor` · แล้วถาม
  `current_database()` จากเซิร์ฟเวอร์จริงเทียบซ้ำ
- **ไม่มีการถอยไปใช้ `DATABASE_URL` หรือ `INGEST_DATABASE_URL` ของเครื่อง** เพราะสอง
  ค่านั้นชี้ production ได้ สคริปต์บังคับให้ระบุ URL มาเองทั้งสองตัว
- ใช้ `bootstrap` + `003` + `004` เดิม **ไม่แก้ schema ของ production และไม่ให้สิทธิ์
  ข้ามฐานข้อมูลแก่ใคร** (ไม่ใช้ `GRANT advisor_api TO ...` ที่มีผลข้ามฐาน)
- **ลบฐานข้อมูลและ role ทั้งสามทิ้งหลังเสร็จ** ยืนยันแล้ว: ฐานข้อมูลเหลือ
  `postgres, course_advisor` · role ที่ login ได้เหลือ `advisor_api, advisor_ingest, postgres`

### แยก mock กับของจริง

| ของจริง | ของปลอม |
|---|---|
| การยึดงานด้วย `FOR UPDATE SKIP LOCKED` · การบล็อกคำสั่งถอน · `FOR SHARE` บน courses · CHECK constraints · partial unique index · `ON CONFLICT` ของ `course_documents` · สิทธิ์ของ role · `rowcount` · transaction boundary ของ `run()` ตัวจริง · `extract_pdf` + `fitz` ตัวจริง · `clean`/`chunk` ตัวจริง · การวางไฟล์บนไฟล์ซิสเทมจริง | **เฉพาะการคำนวณเวกเตอร์**: `pipeline.ingest.embed_chunks` และ `OllamaConnector` ที่ worker ใช้ probe |

ไม่ติดต่อบริการ embedding ใด ๆ ไม่ดาวน์โหลดโมเดล **นี่คือ unit/integration test
ไม่ใช่การยืนยัน end-to-end บน production**

### ⚠️ บั๊กที่เทสต์จับได้ในโค้ดของรอบนี้เอง

รอบแรกได้ 184/187 — สามข้อที่ไม่ผ่านคือหมวด "ไฟล์ถูกสลับหลังตรวจ"

เดิมเขียนลำดับเป็น *ตรวจไฟล์ใน staging → คัดลอกเป็นสำเนา* ซึ่ง **เพียงตรวจจับ**
การสลับไฟล์ ไม่ได้ป้องกัน (สำเนาได้ bytes ชุดใหม่ แล้วด่านเทียบ sha จับได้ → งานล้มเหลว
ทั้งที่ควรสำเร็จด้วยเนื้อที่อนุมัติไว้)

แก้เป็น *คัดลอกก่อน → ตรวจสำเนานั้น → ส่งสำเนาให้ `run()`* ทำให้ bytes ที่ผ่านการตรวจ
กับ bytes ที่ ingest เป็นไฟล์เดียวกันที่ไม่มีใครเขียนได้ หลังแก้ได้ 187/187

---

## 12. Regression

| ชุด | ผล | หมายเหตุ |
|---|---|---|
| `eval/crawl_approval_check.py` (Phase 3A) | **84 ผ่าน · 0 ไม่ผ่าน · 0 ข้าม** | บนฐานข้อมูลทดสอบเดียวกันที่มี 003+004 |
| `eval/crawl_state_check.py` (crawler state) | **32 ผ่าน · 0 ไม่ผ่าน** | ฐานข้อมูลทดสอบเดียวกัน |
| `eval/crawl_download_check.py` (crawler download/security) | **140 ผ่าน · 0 ไม่ผ่าน** | ไม่ต้องมีฐานข้อมูล |
| `eval/tuition_followup_check.py` | **14 ผ่าน (OK)** | |
| `eval/recommendation_clarification_check.py` | **15 ผ่าน (OK)** | |
| static/import | `py_compile` ผ่าน · `import` ผ่านทั้ง `pipeline.crawl.approve`, `pipeline.crawl.sync`, `pipeline.crawl.run`, `pipeline.ingest`, `pipeline.ingest_batch` | |

**รวมทั้งหมด 187 + 285 = 472 ข้อ ผ่านทั้งหมด**

### ที่ไม่ได้รัน และเหตุผล

| ชุด | สถานะ | เหตุผล |
|---|---|---|
| `eval/behaviour_check.py` | **ไม่รัน** | ค่าเริ่มต้นยิงไปที่ production |
| `eval/comparison_evidence_check.py`, `follow_up_scope_check.py`, `structured_on_path_check.py`, `structured_shadow_check.py` | **blocked** | ต้องมีทั้งฐานข้อมูลที่มีข้อมูลจริงและ Ollama เครื่องนี้ไม่มี Ollama · ไม่เกี่ยวกับ Phase 3C ซึ่งไม่แตะ RAG |
| เทสต์ frontend (`npx vitest run`) | **ไม่รัน** | Phase 3C ไม่แก้ไฟล์ใน `frontend/` แม้แต่ไฟล์เดียว |

> ตัวเลข 84/32/140 ที่ตรงกับรายงานเก่าคือ**ผลที่รันจริงในรอบนี้** บนฐานข้อมูลทดสอบที่
> สร้างใหม่ ไม่ได้คัดลอกมาจากรายงานก่อน

---

## 13. Known limitations

| # | ข้อจำกัด | ผล | เงื่อนไขที่ต้อง review |
|---|---|---|---|
| 1 | **คำสั่งถอนค้างรอระหว่าง worker ทำงาน** — backend ไม่ได้ตั้ง `lock_timeout` เอง | ผู้ดูแลกด "ถอน" ตอน worker กำลัง embed แล้วคำขอจะค้างจนงานจบ (อาจเป็นชั่วโมงบน CPU) | เสนอให้ตั้ง `lock_timeout` ในเซสชันของ backend เพื่อให้ได้คำตอบชัดแทนการค้าง — **เป็นการแก้ backend จึงไม่ทำในรอบนี้** |
| 2 | **transaction เปิดค้างนานเท่าเวลา embedding** | ถือ connection หนึ่งตัวและกัน VACUUM cleanup ระหว่างนั้น | ถ้าคลังโตขึ้นมากหรือรันบ่อย ต้องทบทวนว่าจะเปลี่ยนไปใช้ ownership แบบอื่นหรือไม่ |
| 3 | **`run()` commit บน connection ของตัวเอง** | rollback ของ worker ย้อน knowledge writes ไม่ได้ จึงมีสถานะ "เอกสารเข้าคลังแล้วแต่งานไม่ปิด" | กู้เองได้ในรอบถัดไปแบบ idempotent (ทดสอบแล้ว) แต่ถ้าไม่มีใครรัน worker อีก แถวนั้นจะค้าง |
| 4 | **ฐานข้อมูลกับไฟล์ไม่ใช่ transaction เดียวกัน** | วางไฟล์สำเร็จแต่ commit ล้ม → มีไฟล์ส่วนเกินใน `DOCUMENTS_DIR` | ไม่เป็นอันตราย (ค้นด้วย sha) แต่ควรมีขั้นตอนเก็บกวาดในอนาคต |
| 5 | **เขียน `ingest_error` ไม่ได้ถ้า DB ล่ม** | `record_error()` คืน `False` → worker โยนต่อ → ออกด้วยรหัสไม่เป็นศูนย์ พร้อม log ที่ไม่มีข้อมูลอ่อนไหว · **รายงานไม่อ้างว่าบันทึกสำเร็จ** | ต้องดู log ของรอบนั้นเอง ไม่มีร่องรอยในฐานข้อมูล |
| 6 | **`document_store` ทำ index ครั้งเดียวต่อโปรเซส** | เอกสารใหม่จะยังเปิดผ่าน `/documents/{id}/pdf` ไม่ได้จนกว่า backend จะเริ่มโปรเซสใหม่ | **Phase 3C ไม่แก้ `document_store` ไม่ restart ไม่ deploy** |
| 7 | **`source_sha_changed_after_ingest`** | decision ปิดแล้วแต่ต้นทางไม่เป็น `ingested` และไฟล์ใหม่กลับเข้าคิว | เป็นกรณีที่ต้องให้คนดู ไม่ใช่ความล้มเหลว |
| 8 | **`document_course_conflict`** เกิดจาก `already_ingested()` ไม่กรอง `course_id` (`ingest.py:98`) | ไฟล์เนื้อเดียวกันนำเข้าสองหลักสูตรไม่ได้ | ต้องให้คนตัดสิน · การแก้ต้องแก้ `ingest.py` ซึ่งห้ามในรอบนี้ |
| 9 | **แถวที่ `file_sha256 IS NULL`** ไม่มีการอนุมัติได้ตั้งแต่ Phase 3A | worker จึงไม่เห็นงานเหล่านั้นเลย | ข้อจำกัดที่ Phase 3A บันทึกไว้แล้ว |
| 10 | **ยังไม่ทดสอบกับโมเดลจริง** | ชั้นที่ 3 ของสัญญา embedding จะทำงานตอนรันจริงเท่านั้น | ต้องยืนยันตอน integration ใน Phase 3D |
| 11 | **`crawl_sources` ไม่ถูกล็อก** โดยตั้งใจ (เพื่อไม่ขวาง crawler) | ใช้ conditional update + `rowcount` แทน ซึ่งครอบกรณี SHA เปลี่ยนได้ แต่ไม่กันกรณีอื่นที่ยังไม่เกิด | ทบทวนถ้าเพิ่มผู้เขียน `crawl_sources` รายใหม่ |

---

## 14. Production prerequisites ที่ยังไม่ได้ทำ

ทั้งหมดยังไม่ได้ทำ และ**ไม่ได้ต่อเข้า production เพื่อสำรวจเพิ่มในรอบนี้** — ข้อมูลข้างล่าง
มาจากการอ่าน source และการตรวจแบบอ่านอย่างเดียวที่บันทึกไว้ในรายงานก่อนหน้า

| # | สิ่งที่ต้องมี | สถานะที่ยืนยันจาก source/รายงานก่อน |
|---|---|---|
| 1 | **migration 004 บน production** | ยังไม่ลง — production มี `001, 002, 003` เท่านั้น |
| 2 | role/สิทธิ์ | `advisor_ingest` มีสิทธิ์ครบตาม `20-roles.sh` + `003` แล้ว · สิทธิ์บน `crawl_decisions` มาพร้อม `004` |
| 3 | `CRAWL_STAGING_DIR` + โฟลเดอร์ staging บนเซิร์ฟเวอร์ | ยังไม่มี — Phase 2 รัน crawler จากเครื่องอื่น staging จึงยังไม่อยู่บนเซิร์ฟเวอร์ |
| 4 | `DOCUMENTS_DIR` ที่ **เขียนได้** สำหรับ worker | `docker-compose.prod.yml:86` mount `./documents` เข้า backend เป็น `:ro` — worker ต้องได้สิทธิ์เขียนโฟลเดอร์นี้ด้วยเส้นทางอื่น |
| 5 | `EMBED_MODEL=bge-m3` / `EMBED_DIM=1024` ในสภาพแวดล้อมของ worker | `docker-compose.prod.yml:74-75` ตั้งค่านี้ให้ backend อยู่แล้ว · worker ต้องได้ค่าเดียวกัน |
| 6 | บัญชีผู้ดูแลที่มีอยู่จริง | ยังไม่มี — ต้อง `UPDATE users SET is_admin = true` หนึ่งบัญชี **ยังไม่ทำ** |
| 7 | การ deploy โค้ดของ Phase 3A/3B/3C | ยังไม่ deploy — production image ยังเป็นตัวเดิม |
| 8 | ขั้นตอน refresh/restart ของ `document_store` | ยังไม่มี · index ตอนเริ่มโปรเซส |
| 9 | วิธีรัน worker บนเซิร์ฟเวอร์ | ไม่มี pipeline image — ใช้แนวเดียวกับที่ Phase 2 verify ทำ (`docker run --rm` จาก backend image ที่มีอยู่ + mount โค้ด) ซึ่งต้องขออนุมัติแยก |

---

## 15. Phase 3D — งานที่เหลือ

| # | งาน |
|---|---|
| 1 | รัน migration 004 บน production (ขออนุมัติแยก) |
| 2 | ตั้งบัญชีผู้ดูแลหนึ่งบัญชี (ขออนุมัติแยก) |
| 3 | ย้าย staging ขึ้นเซิร์ฟเวอร์ · mount `:ro` เข้า backend · ตั้ง `CRAWL_STAGING_DIR` |
| 4 | จัดทางให้ worker เขียน `DOCUMENTS_DIR` ได้ และตัดสินว่าจะ mount แบบไหน |
| 5 | deploy โค้ด Phase 3A/3B/3C แล้วยืนยัน `/crawl-review` และการเปิด PDF บน production |
| 6 | รัน worker จริงหนึ่งงานแบบควบคุม แล้วยืนยันสัญญา embedding ด้วย `bge-m3` ตัวจริง |
| 7 | ขั้นตอน refresh/restart ของ `document_store` เพื่อให้เอกสารใหม่เปิดดูได้ |
| 8 | ทบทวนข้อจำกัดข้อ 1 และ 2 (คำสั่งถอนค้าง · transaction ยาว) แล้วตัดสินว่าจะแก้ไหม |

**ไม่เอา feature ที่ห้ามไว้มาทำ**: ไม่มี history endpoint · ไม่มี signed PDF URL ·
ไม่มี course pagination/search · ไม่เปลี่ยน approval API · ไม่มี scheduler · ไม่มี
notification/analytics · ไม่มี permanent worker

---

## 16. Git และการยืนยัน

```
HEAD ตอนเริ่ม   0b86ef26976710dc3ad7aade86e55b183c821009
HEAD ตอนจบ     0b86ef26976710dc3ad7aade86e55b183c821009   (เท่าเดิม)
branch         mko-phase2 · origin/mko-phase2 0b86ef2 · ahead 0 / behind 0
main           b78b3f8 · origin/main b78b3f8              (ไม่ถูกแตะ)

git status --short --untracked-files=no     →  ว่าง
git diff -- pipeline/ingest.py              →  ว่าง
git diff --check -- pipeline/crawl/approve.py eval/crawl_ingest_worker_check.py  →  ว่าง

ไฟล์ใหม่ของรอบนี้ (ไม่ปรากฏใน tracked diff เพราะยังไม่ stage)
  ?? pipeline/crawl/approve.py
  ?? eval/crawl_ingest_worker_check.py

untracked ที่มีอยู่ก่อนรอบนี้ (ไม่ได้แตะ)
  38 รายการใน docs/ — รายงานของเฟสก่อน + รายงานฉบับนี้
```

### ยืนยันตามข้อเท็จจริง

- **ไม่ commit · ไม่ push · ไม่ stage · ไม่ใช้ `git add`** — `git status` ยังเป็น untracked
- **ไม่ merge `main`** — `main` ยังเป็น `b78b3f8` ทั้ง local และ origin
- **ไม่ deploy · ไม่ restart/recreate service ใด · ไม่แก้ config/credential ของ production**
- **ไม่รัน migration บน production** — production มี `001, 002, 003` เท่านั้น `crawl_decisions` ยังไม่มี
- **ไม่เขียนข้อมูลลงฐานข้อมูล production และไม่ใช้ฐานข้อมูล production ทดสอบ** แม้แต่การเตรียม fixture
  — ทุกอย่างอยู่บน `crawl_test` ที่สร้างใหม่และลบทิ้งแล้ว
- **คลังความรู้ของ production เท่าเดิม**: `courses 24 / course_documents 31 / course_chunks 9,039`
- **ไม่สร้างบัญชีผู้ดูแล** · **ไม่ ingest และไม่ embed บน production**
- **ไม่แก้ `pipeline/ingest.py`** — sha256 เท่ากับ HEAD ทุกไบต์
- **ไม่แก้ migration หรือ schema** เพื่อหลบปัญหาใด
- **ไม่เริ่ม Phase 3D**

**หยุดรอ review**
