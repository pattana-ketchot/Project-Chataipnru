"""
ตั้งค่าระบบทั้งหมดผ่าน environment variables (ไม่ hardcode secret ในโค้ด)
SECURITY: ห้าม commit ไฟล์ .env จริงเข้า repo — ใช้ .env.example เป็นแม่แบบ
"""
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Database ---
    database_url: str = Field(..., alias="DATABASE_URL")
    # ตัวอย่าง: postgresql+psycopg://advisor_api:xxxx@localhost:5432/course_advisor

    # --- Auth ---
    jwt_secret: str = Field(..., alias="JWT_SECRET")          # openssl rand -hex 32
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14

    # --- Local LLM (Ollama) ---
    ollama_base_url: str = Field("http://127.0.0.1:11434", alias="OLLAMA_BASE_URL")
    llm_model: str = Field("qwen2.5:7b", alias="LLM_MODEL")
    embed_model: str = Field("nomic-embed-text", alias="EMBED_MODEL")
    embed_dim: int = Field(768, alias="EMBED_DIM")
    llm_request_timeout_s: int = 120

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
