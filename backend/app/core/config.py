"""
ตั้งค่าระบบทั้งหมดผ่าน environment variables (ไม่ hardcode secret ในโค้ด)
SECURITY: ห้าม commit ไฟล์ .env จริงเข้า repo — ใช้ .env.example เป็นแม่แบบ
"""
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# <root>/backend/app/core/config.py -> <root>/.env
# ต้องเป็น absolute path: ถ้าใช้ ".env" เฉยๆ pydantic-settings จะอ่านจาก working
# directory ตอนรัน ซึ่งปกติคือ backend/ (ตามคำสั่ง uvicorn ใน README) แล้วหาไฟล์
# ไม่เจอ เพราะ .env อยู่ที่ root ของ repo — backend จะ crash ตั้งแต่ import
_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")

    # --- Database ---
    database_url: str = Field(..., alias="DATABASE_URL")
    # ตัวอย่าง: postgresql+psycopg://advisor_api:xxxx@localhost:5432/course_advisor

    # --- Auth ---
    jwt_secret: str = Field(..., alias="JWT_SECRET")          # openssl rand -hex 32
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14

    # --- ผู้ให้บริการโมเดลสำหรับ "เขียนคำตอบ" ---
    # "ollama" = โมเดลในเครื่อง (ค่าเริ่มต้น ไม่ส่งข้อมูลออกนอกเครื่อง)
    # "gemini" = เรียก API ของ Google (เร็วกว่ามากบนเครื่องที่ไม่มีการ์ดจอ)
    #
    # ส่วน embedding ใช้ bge-m3 ในเครื่องเสมอไม่ว่าตั้งค่านี้เป็นอะไร
    # เพราะเวกเตอร์ในฐานข้อมูลผูกกับโมเดลและขนาดมิติของมัน (ดู services/llm_client.py)
    llm_provider: str = Field("ollama", alias="LLM_PROVIDER")
    gemini_api_key: str = Field("", alias="GEMINI_API_KEY")
    gemini_model: str = Field("gemini-3.5-flash-lite", alias="GEMINI_MODEL")

    # --- Local LLM (Ollama) ---
    ollama_base_url: str = Field("http://127.0.0.1:11434", alias="OLLAMA_BASE_URL")
    llm_model: str = Field("qwen2.5:3b", alias="LLM_MODEL")
    embed_model: str = Field("nomic-embed-text", alias="EMBED_MODEL")
    embed_dim: int = Field(768, alias="EMBED_DIM")
    llm_request_timeout_s: int = 120

    # ยิงคำขอเล็กๆ ไปที่ Ollama ทุกกี่นาทีเพื่อไม่ให้โมเดลถูกถอดออกจาก VRAM
    # ต้องน้อยกว่า OLLAMA_KEEP_ALIVE ใน docker-compose.yml (ตั้งไว้ 30 นาที)
    # ตั้ง 0 เพื่อปิด แล้วคืน VRAM ให้งานอื่นแทน
    warmup_interval_minutes: int = Field(20, alias="WARMUP_INTERVAL_MINUTES")

    # --- PDF ingest ---
    max_pdf_size_mb: int = 50
    pdf_storage_dir: str = Field("./storage/pdfs", alias="PDF_STORAGE_DIR")

    # --- CORS ---
    cors_allow_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    # --- Rate limiting (applied in middleware, see api/deps.py) ---
    rate_limit_per_minute: int = 30

    # --- คำตอบจากข้อมูลหลักสูตรที่มีโครงสร้าง (มคอ. Phase 2) ---
    # off    = ไม่ทำอะไรเลย (ค่าตั้งต้น)
    # shadow = คำนวณคำตอบจากฐานข้อมูลเทียบกับคำตอบเดิมแล้วบันทึกลง mko.shadow_answers ไม่เปลี่ยนคำตอบที่ผู้ใช้เห็น
    # on     = ยังไม่เปิดใน Phase 2 ระบบทำงานเป็น shadow (ดู services/structured_shadow.py)
    # เก็บเป็นข้อความแทน Literal เพื่อให้ค่าที่พิมพ์ผิดกลายเป็น off แทนที่จะทำให้ backend เปิดไม่ขึ้น
    structured_answers: str = Field("off", alias="STRUCTURED_ANSWERS")

    # --- เอกสารต้นฉบับที่เปิดให้ผู้ใช้ดู (ดู services/document_store.py) ---
    # โฟลเดอร์ที่เก็บไฟล์ มคอ.2 บนเซิร์ฟเวอร์ mount แบบอ่านอย่างเดียว
    # ค่าว่าง (ค่าตั้งต้น) = ปิดฟีเจอร์ เส้นทาง /documents/{id}/pdf จะตอบว่าไม่พบเสมอ
    # ใช้เป็นสวิตช์ปิดได้ทันทีโดยไม่ต้อง deploy โค้ดใหม่
    documents_dir: str = Field("", alias="DOCUMENTS_DIR")

    # --- ไฟล์ที่ crawler โหลดมารออนุมัติ (ดู services/staging_store.py) ---
    # โฟลเดอร์ staging ของ pipeline/crawl/sync.py mount แบบอ่านอย่างเดียว
    # ค่าว่าง (ค่าตั้งต้น) = ปิดการเปิดดูไฟล์ในคิว เส้นทาง /crawl-review/{id}/pdf จะ
    # ตอบว่าไม่พบเสมอ ส่วนคิวและการอนุมัติยังทำงานได้ — สวิตช์เดียวกับ documents_dir
    crawl_staging_dir: str = Field("", alias="CRAWL_STAGING_DIR")


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
