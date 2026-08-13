"""
Thin in-process wrapper around the standalone connector in `llm/connector.py`
(item 4 ของ requirement) เพื่อให้ backend เรียกใช้ได้โดยไม่ต้อง duplicate logic.

ในระบบจริงแนะนำ package `llm/` แยกเป็น pip package ภายใน (monorepo) แล้ว
`pip install -e ../llm` แทนการ append sys.path — ที่นี่ใช้ sys.path เพื่อความง่าย
ของ scaffold เท่านั้น
"""
import sys
from pathlib import Path

# monorepo: <root>/backend/app/services/llm_client.py -> <root>/llm
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from llm.connector import OllamaConnector  # noqa: E402
from app.core.config import get_settings

settings = get_settings()

_connector: OllamaConnector | None = None


def get_llm_connector() -> OllamaConnector:
    """Singleton connector — reuse the underlying httpx client/connection pool."""
    global _connector
    if _connector is None:
        _connector = OllamaConnector(
            base_url=settings.ollama_base_url,
            chat_model=settings.llm_model,
            embed_model=settings.embed_model,
            timeout_s=settings.llm_request_timeout_s,
        )
    return _connector
