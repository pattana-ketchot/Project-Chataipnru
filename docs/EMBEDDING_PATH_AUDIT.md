# เส้นทาง embedding ของระบบ — ตรวจจาก source จริง

| | |
|---|---|
| วันที่ตรวจ | 2026-10-01 |
| วิธีตรวจ | อ่าน source ใน repo · **READ-ONLY** ไม่แก้ไฟล์ ไม่รันอะไร ไม่แตะ production |
| ทำไมต้องมีเอกสารนี้ | ก่อนออกแบบการย้าย RAG ต้องรู้ก่อนว่า **ของจริงทำงานอย่างไร** ไม่ใช่สมมติเอาจากผัง |
| เอกสารประกอบ | [`TARGET_ARCHITECTURE.md`](TARGET_ARCHITECTURE.md) · [`DATABASE_CONSOLIDATION_AUDIT.md`](DATABASE_CONSOLIDATION_AUDIT.md) |

---

## ข้อสรุปสามข้อ

> **1. ไม่มี automatic failover ของ embedding**
> ต่อ Ollama ไม่ติด = ล้มและโยน error ไม่สลับไปโฮสต์อื่น
>
> **2. นี่เป็นการออกแบบที่ตั้งใจ ไม่ใช่ข้อบกพร่อง**
> ถ้ามี fallback ข้ามโฮสต์อัตโนมัติแล้วโฮสต์สำรองมีโมเดลคนละตัว เวกเตอร์จะปนกัน
> ในตารางเดียวโดยไม่มีอะไรฟ้อง ซึ่งพังเงียบและตามหายาก
> ระบบนี้เลือก **"ล้มดังกว่าปนเงียบ"**
>
> **3. `bge-m3` / `1024` มิติ เป็นค่าที่ล็อกไว้**
> ห้ามเปลี่ยนในแผนหรือการออกแบบใด ๆ โดยไม่ได้รับอนุมัติจากเจ้าของโปรเจกต์ก่อน

---

## 1. สภาพแวดล้อมที่มี Ollama

| สภาพแวดล้อม | ที่อยู่ | ตั้งค่าจาก | ใช้ทำอะไร |
|---|---|---|---|
| **Production** | Ollama บน OCI VM เดียวกับบริการอื่น · `http://ollama:11434` | `docker-compose.prod.yml:64` (backend) · `docker-compose.worker.yml:40` (worker) | สร้าง embedding ของจริงทั้งหมด |
| **Development** | Ollama บนเครื่องผู้พัฒนา | ตั้ง `OLLAMA_BASE_URL` เอง · ถ้าไม่ตั้งจะเป็น `http://127.0.0.1:11434` | ทดสอบ · เป็นทางเลือกสำรอง**ที่คนเลือกเอง** |
| **ชุดทดสอบแยก** | `e2e-ollama` ในคอมโพสของชุดทดสอบ | `eval/e2e/docker-compose.e2e.yml:83,115` | รัน E2E แบบแยกอิสระ |

**Ollama บนเครื่องผู้พัฒนาเป็นสภาพแวดล้อมคนละชุด ไม่ใช่ตัวสำรองของ production**
การจะใช้มันต้องเปลี่ยน `OLLAMA_BASE_URL` ด้วยมือ ระบบไม่สลับให้เอง

---

## 2. หลักฐานว่าไม่มี failover

### 2.1 `base_url` เป็นค่าเดียว ไม่ใช่รายการโฮสต์

`llm/connector.py:46-52`

```python
class OllamaConnector:
    base_url: str = "http://127.0.0.1:11434"     # str ไม่ใช่ list
    chat_model: str = "qwen2.5:7b"
    embed_model: str = "nomic-embed-text"
    timeout_s: int = 120
    max_retries: int = 2
```

`llm/connector.py:100`

```python
self._client = httpx.Client(base_url=self.base_url, timeout=self.timeout_s)
```

client ตัวเดียวผูกกับ URL เดียวตั้งแต่สร้าง เปลี่ยนระหว่างทางไม่ได้

### 2.2 การลองใหม่เกิดกับโฮสต์เดิมเท่านั้น

`llm/connector.py:191-204`

```python
def _post_with_retry(self, path, payload):
    last_exc = None
    for attempt in range(1, self.max_retries + 2):        # รวม 3 ครั้ง
        try:
            resp = self._client.post(path, json=payload)  # ← client เดิม URL เดิม
            resp.raise_for_status()
            return resp.json()
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            last_exc = e
            logger.warning("ollama %s attempt %d/%d failed: %s", ...)
        except httpx.HTTPStatusError as e:
            # 4xx/5xx จาก Ollama เอง (เช่น model ไม่ถูก pull ไว้) — ไม่ retry ซ้ำ
            raise LLMConnectionError(...) from e
    raise LLMConnectionError(f"could not reach local LLM at {self.base_url}{path}") from last_exc
```

| กรณี | พฤติกรรม |
|---|---|
| ต่อไม่ติด / timeout | ลองซ้ำ **ที่โฮสต์เดิม** รวม 3 ครั้ง แล้ว **โยน `LLMConnectionError`** |
| Ollama ตอบ 4xx/5xx (เช่นไม่ได้ pull โมเดล) | **ล้มทันที ไม่ลองซ้ำเลย** |
| หมดครั้งที่ลอง | ข้อความระบุ URL เดียว — ไม่มีโฮสต์ที่สองให้ไปต่อ |

### 2.3 fallback ที่มีอยู่คุมเฉพาะการเขียนคำตอบ

`backend/app/services/llm_client.py:71-126`

```python
def __init__(self, embedder: OllamaConnector, chatter: GeminiConnector):
    self._embedder = embedder
    self._chatter  = chatter
    self._fallback = embedder          # ตัวเดียวกับที่ใช้ embed

# --- ฝั่ง embedding: โมเดลในเครื่อง ---
def embed(self, text):
    return self._embedder.embed(text)          # ตรงไป ไม่มี try/except ไม่มีสำรอง

def embed_batch(self, texts):
    return self._embedder.embed_batch(texts)

# --- ฝั่งเขียนคำตอบ: ใช้เจ้าหลักก่อน ล้มแล้วค่อยตกมาที่โมเดลในเครื่อง ---
def chat(self, *args, allow_fallback=True, **kwargs):
    try:
        return self._chatter.chat(*args, **kwargs)      # Gemini
    except ...:
        return self._fallback.chat(...)                 # ← fallback อยู่ตรงนี้เท่านั้น
```

**`embed()` ไม่มี `try` ไม่มี `except` ไม่มีทางสำรอง** — ล้มคือล้ม
ส่วน `chat()` และ `chat_stream()` มี fallback จาก Gemini มาที่โมเดลในเครื่อง
ซึ่งเป็นคนละเรื่องกับ embedding โดยสิ้นเชิง

### 2.4 Gemini ไม่มี `embed()` โดยเจตนา

`llm/gemini.py:14-19` เขียนเหตุผลไว้ในไฟล์เอง

> ขอบเขต — รับผิดชอบเฉพาะการ "เขียนคำตอบ" เท่านั้น **ไม่มี embed() โดยตั้งใจ**
> เพราะเวกเตอร์ของเอกสารทั้ง 7,301 ชิ้นในฐานข้อมูลถูกสร้างด้วย bge-m3 ขนาด 1024 มิติ
> การเปลี่ยนโมเดล embedding แปลว่าต้องคำนวณใหม่ทั้งหมดและแก้ชนิดคอลัมน์ในฐานข้อมูล

**embedding จึงไม่มีทางหลุดไปหา Gemini ได้เลย** แม้โดยอุบัติเหตุ
(ตัวเลข 7,301 ในคอมเมนต์เป็นค่าตอนเขียนไฟล์นั้น ปัจจุบันคือ **9,039** chunk)

---

## 3. ด่านที่กันโมเดลผิดไม่ให้เข้าฐานข้อมูล

ต่อให้มีใครชี้ `OLLAMA_BASE_URL` ไปที่ Ollama ตัวอื่นที่มีโมเดลคนละตัว
worker จะปฏิเสธงานก่อนแตะข้อมูล

`pipeline/crawl/approve.py:75-76`

```python
REQUIRED_EMBED_MODEL = "bge-m3"
REQUIRED_EMBED_DIM   = 1024
```

`pipeline/crawl/approve.py:112-133` — `check_embedding_contract()` ตรวจสามชั้น

| ชั้น | ตรวจอะไร | ข้อผิดพลาดที่โยน |
|---|---|---|
| 1 | `EMBED_MODEL` จาก env ตรงกับ `bge-m3` ไหม | `embed_model_mismatch` |
| 2 | `EMBED_DIM` จาก env ตรงกับ `1024` ไหม | `embed_dim_mismatch` |
| 3 | **ยิง embed จริงหนึ่งครั้ง** แล้ววัดความยาวเวกเตอร์ที่ได้ | ไม่ตรง = ล้ม |

ชั้นที่ 3 สำคัญที่สุด เพราะ env ตั้งถูกแต่โมเดลที่ปลายทางเป็นคนละตัวก็ยังจับได้

> **ข้อสังเกตที่บันทึกไว้แล้ว (F2)** — ด่านนี้ทำงาน **หลัง** `claim()` ไม่ใช่ก่อน
> worker ที่ตั้งค่าผิดจะยึดงานก่อนแล้วจึงล้ม แต่ `ingest_finished_at` ยังว่าง
> งานจึงยังถูกยึดใหม่ได้ และการรันครั้งถัดไปที่ตั้งค่าถูกก็สำเร็จ (พิสูจน์แล้วใน E2E)
> รายละเอียดใน `PHASE3D_ISOLATED_E2E_TEST_EXECUTION_REPORT.md`

---

## 4. ค่าที่ล็อกไว้ ห้ามเปลี่ยนโดยไม่ได้รับอนุมัติ

```
โมเดล embedding   bge-m3
มิติ               1024
ตัวดำเนินการค้นหา    <=>  (cosine distance)
index              ivfflat (embedding vector_cosine_ops) WITH (lists = 100)
คอลัมน์             public.course_chunks.embedding  vector(1024) NOT NULL
ข้อมูลที่มีอยู่       9,039 chunk · 174 MB
```

**การเปลี่ยนค่าใดค่าหนึ่งข้างบนต้องได้รับอนุมัติจากเจ้าของโปรเจกต์ก่อนเสมอ**
ไม่ว่าจะด้วยเหตุผลใด รวมถึงการ "ปรับให้เข้ากับของที่จะย้ายมา"

ที่มาของแต่ละค่า

| ค่า | ยืนยันจาก |
|---|---|
| `bge-m3` · `1024` | `pipeline/crawl/approve.py:75-76` + probe จริงตอนรัน |
| `<=>` cosine | `backend/app/services/vector_search.py:24,27` (`cosine_distance`) |
| `ivfflat` · `lists = 100` | `pg_get_indexdef()` บน production |
| `vector(1024) NOT NULL` · 9,039 แถว | `pg_attribute` + นับแถวจริงบน production |

---

## 5. ผลต่อการออกแบบการย้าย RAG

### 5.1 ข้อเท็จจริงที่แผนต้องยอมรับ

| # | ข้อเท็จจริง | ผลต่อแผน |
|---|---|---|
| 1 | ของที่จะย้ายมาเป็น `vector` **ที่ไม่ล็อกมิติใน schema** · แอปตั้ง `EMBEDDING_DIMENSIONS = 768` · **มิติจริงของข้อมูลยัง UNKNOWN** | **ย้ายค่าเวกเตอร์ตรง ๆ ไม่ได้** ต้อง embed เนื้อหาใหม่ทั้งหมดด้วย bge-m3 ไม่ว่ามิติเดิมจะเป็นเท่าใด |
| 2 | ไม่มี failover ของ embedding | ขั้นตอน re-embed ที่ยาวต้องทนต่อการล้มกลางคัน — ต้องทำเป็นงานที่รันซ้ำได้ ไม่ใช่งานเดียวยาว ๆ |
| 3 | 4xx/5xx จาก Ollama ไม่ลองซ้ำ | ถ้าโมเดลไม่ได้ pull ไว้ งานจะล้มทันทีตั้งแต่ชิ้นแรก — ต้องตรวจว่าโมเดลพร้อมก่อนเริ่ม |
| 4 | `check_embedding_contract()` บังคับ `bge-m3`/`1024` | เครื่องมือ re-embed ต้องผ่านด่านนี้ด้วย ห้ามหาทางข้าม |
| 5 | index เป็น `ivfflat` ที่สร้างจากข้อมูลเดิม | เพิ่มข้อมูลจำนวนมากแล้วควรพิจารณาสร้าง index ใหม่ ไม่ใช่เพราะพัง แต่เพราะการกระจายเปลี่ยน |

### 5.2 สิ่งที่ห้ามทำในแผน

- ห้ามเสนอให้เปลี่ยนโมเดลหรือมิติเพื่อให้ "ย้ายง่ายขึ้น"
- ห้ามเสนอให้เก็บเวกเตอร์สองมิติในระบบเดียวกัน
- ห้ามเสนอให้ปิด `check_embedding_contract()` ชั่วคราวระหว่างย้าย
- ห้ามถือว่า Ollama บนเครื่องผู้พัฒนาเป็นตัวสำรองอัตโนมัติของ production

### 5.3 สิ่งที่ต้องวัดก่อนและหลัง

การ re-embed **เปลี่ยนคำตอบของระบบ** โดยไม่มีอะไรพังให้เห็น ต่างจากขั้นตอนอื่น
ที่ผิดแล้วเห็นทันที จึงต้องวัดคุณภาพการค้นก่อนและหลัง และ**รันหลายรอบ**
เพราะคะแนนประเมินของโปรเจกต์นี้มีความผันผวนในตัวอยู่แล้ว รันครั้งเดียวสรุปไม่ได้

---

## 6. สิ่งที่เอกสารนี้ยังไม่ได้ยืนยัน

| # | ยังไม่รู้ | ทำไมสำคัญ |
|---|---|---|
| 1 | พฤติกรรมเมื่อ Ollama ล่ม **กลางการ ingest** งานจริง | ทดสอบใน E2E แล้วเฉพาะกรณีตั้งค่าโมเดลผิด ยังไม่ได้ทดสอบกรณีล่มกลางคัน (บันทึกไว้เป็นข้อจำกัดใน E2E report แล้ว) |
| 2 | เวลาที่ใช้ re-embed จริงของข้อมูลที่จะย้ายมา | ยังไม่รู้ว่าฝั่งที่จะย้ายมามีกี่แถว (U3 ใน consolidation audit) |
| 3 | คุณภาพการค้นหลังเปลี่ยนโมเดลของเนื้อหาที่ย้ายมา | ต้องวัดจริง เดาไม่ได้ |

---

## สรุปการเปลี่ยนแปลงในรอบนี้

```
CHANGES TO SOURCE:   NONE      (อ่าน source อย่างเดียว)
PRODUCTION WRITES:   NONE
CONFIG CHANGES:      NONE
SERVICE RESTARTS:    NONE
COMMITS / PUSHES:    NONE
```

เอกสารนี้เป็นการบันทึกสิ่งที่ตรวจพบ ไม่ได้เสนอให้เปลี่ยนอะไร
