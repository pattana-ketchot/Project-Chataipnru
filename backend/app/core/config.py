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
    gemini_model: str = Field("gemini-2.5-flash", alias="GEMINI_MODEL")

    # --- Local LLM (Ollama) ---
    ollama_base_url: str = Field("http://127.0.0.1:11434", alias="OLLAMA_BASE_URL")
    llm_model: str = Field("qwen2.5:7b", alias="LLM_MODEL")
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


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
