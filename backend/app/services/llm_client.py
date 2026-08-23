"""
เลือกและสร้าง connector ที่ backend ใช้ (item 4 ของ requirement)

ระบบนี้ใช้โมเดลสองตัวคนละหน้าที่ และเลือกผู้ให้บริการแยกกันได้:

    embedding (แปลงข้อความเป็นเวกเตอร์)   ใช้ bge-m3 ในเครื่องเสมอ
    การเขียนคำตอบ                        เลือกได้ระหว่างโมเดลในเครื่องกับ Gemini

ทำไม embedding ถึงเปลี่ยนไม่ได้: เวกเตอร์ของเอกสารทั้ง 7,301 ชิ้นในฐานข้อมูลถูกสร้าง
ด้วย bge-m3 ขนาด 1024 มิติ และคอลัมน์ในฐานข้อมูลก็ประกาศขนาดนี้ไว้ตายตัว การเปลี่ยน
โมเดล embedding แปลว่าต้องคำนวณใหม่ทั้งคลังและแก้โครงสร้างตาราง ซึ่งไม่เกี่ยวกับ
ปัญหาความเร็วเลย เพราะการค้นเอกสารใช้เวลาไม่ถึง 3 วินาที

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
from llm.gemini import GeminiConnector  # noqa: E402
from app.core.config import get_settings  # noqa: E402

settings = get_settings()

_connector = None


class _SplitConnector:
    """
    ใช้ผู้ให้บริการคนละเจ้าสำหรับ embedding กับการเขียนคำตอบ

    มีเพื่อให้โค้ดที่เรียกใช้ไม่ต้องรู้เรื่องนี้เลย ทุกที่ยังเรียก connector.embed()
    และ connector.chat() บนวัตถุเดียวเหมือนเดิม การสลับผู้ให้บริการจึงไม่กระทบ
    services/chat.py หรือ services/rag.py แม้แต่บรรทัดเดียว
    """

    def __init__(self, embedder: OllamaConnector, chatter: GeminiConnector) -> None:
        self._embedder = embedder
        self._chatter = chatter

    # --- ฝั่ง embedding: โมเดลในเครื่อง ---
    def embed(self, text):
        return self._embedder.embed(text)

    def embed_batch(self, texts):
        return self._embedder.embed_batch(texts)

    # --- ฝั่งเขียนคำตอบ: ผู้ให้บริการที่เลือกไว้ ---
    def chat(self, *args, **kwargs):
        return self._chatter.chat(*args, **kwargs)

    def chat_stream(self, *args, **kwargs):
        return self._chatter.chat_stream(*args, **kwargs)

    @property
    def chat_model(self) -> str:
        return self._chatter.chat_model


def _build_ollama() -> OllamaConnector:
    return OllamaConnector(
        base_url=settings.ollama_base_url,
        chat_model=settings.llm_model,
        embed_model=settings.embed_model,
        timeout_s=settings.llm_request_timeout_s,
    )


def get_llm_connector():
    """Singleton connector — reuse the underlying httpx client/connection pool."""
    global _connector
    if _connector is None:
        ollama = _build_ollama()
        if settings.llm_provider == "gemini":
            _connector = _SplitConnector(
                embedder=ollama,
                chatter=GeminiConnector(
                    api_key=settings.gemini_api_key,
                    chat_model=settings.gemini_model,
                    timeout_s=settings.llm_request_timeout_s,
                ),
            )
        else:
            _connector = ollama
    return _connector
