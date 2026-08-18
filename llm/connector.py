"""
Local LLM Connector — item 4 ของ requirement

เชื่อมต่อกับ Qwen / Llama ที่รันผ่าน Ollama (http://localhost:11434) แบบ
framework-agnostic (ไม่ผูกกับ FastAPI) ใช้ได้ทั้งจาก backend, pipeline,
notebook หรือ batch job อื่นๆ

ทำไมเลือก Ollama:
  - รองรับทั้ง /api/chat (LLM) และ /api/embeddings (embedding model) ในตัวเดียว
  - โมเดล gguf ของ Qwen2.5 / Llama3.x โหลดผ่าน `ollama pull` ได้ตรงๆ
  - ถ้าอยากเปลี่ยนไปใช้ vLLM/llama.cpp server ในอนาคต แก้แค่คลาสนี้ที่เดียว
    (ทุกที่ที่เรียกใช้งานผ่าน interface เดียวกันอยู่แล้ว)

SECURITY:
  - Local LLM endpoint ควร bind 127.0.0.1 หรืออยู่ใน internal network เท่านั้น
    (ดู docker-compose.yml) — ไม่ควร expose ตรงสู่ internet เพราะไม่มี auth
    ในตัว Ollama เอง
  - timeout ทุก request กันกรณีโมเดลค้าง/เครื่อง local โหลดหนักจน backend hang
  - ไม่ log เนื้อหา prompt/response แบบเต็มที่ INFO level เพราะอาจมี PII จาก
    user profile ปนอยู่ (log แค่ length/metadata พอ)
"""
from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger("llm.connector")


class LLMConnectionError(RuntimeError):
    """โมเดล local ต่อไม่ได้ / timeout / ตอบผิดรูปแบบ"""


@dataclass
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class OllamaConnector:
    base_url: str = "http://127.0.0.1:11434"
    chat_model: str = "qwen2.5:7b"
    embed_model: str = "nomic-embed-text"
    timeout_s: int = 120
    max_retries: int = 2
    _client: httpx.Client = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._client = httpx.Client(base_url=self.base_url, timeout=self.timeout_s)

    # ------------------------------------------------------------------
    # Embeddings
    # ------------------------------------------------------------------
    def embed(self, text: str) -> list[float]:
        payload = {"model": self.embed_model, "prompt": text}
        data = self._post_with_retry("/api/embeddings", payload)
        embedding = data.get("embedding")
        if not embedding:
            raise LLMConnectionError(f"embedding response missing 'embedding' field: {data!r}"[:200])
        return embedding

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        # Ollama /api/embeddings รับทีละข้อความ — วน loop ฝั่ง client
        # (ถ้าต้องการ throughput สูงกว่านี้ ค่อยสลับไปใช้ sentence-transformers
        # ที่รองรับ true batch บน GPU local แทน)
        return [self.embed(t) for t in texts]

    # ------------------------------------------------------------------
    # Chat / generation
    # ------------------------------------------------------------------
    def chat(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.2,
        json_mode: bool = False,
    ) -> str:
        payload: dict[str, Any] = {
            "model": self.chat_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": {"temperature": temperature},
        }
        if json_mode:
            payload["format"] = "json"  # Ollama บังคับ valid JSON output

        data = self._post_with_retry("/api/chat", payload)
        message = data.get("message", {})
        content = message.get("content")
        if content is None:
            raise LLMConnectionError(f"chat response missing content: {data!r}"[:200])
        return content

    def chat_stream(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.2,
    ) -> Iterator[str]:
        """
        เหมือน chat() แต่ทยอยคืนข้อความทีละส่วนระหว่างที่โมเดลกำลังเขียน

        มีไว้เพื่อลด "เวลารอที่รู้สึกได้" ไม่ใช่เวลารวม — เซิร์ฟเวอร์ที่รันด้วย CPU
        เขียนได้ราว 8 โทเคน/วินาที คำตอบยาว 250 โทเคนจึงใช้เวลาราว 30 วินาที
        ถ้ารอจนจบค่อยส่ง ผู้ใช้จะเห็นแต่หน้าจอว่างตลอด 30 วินาทีนั้น

        ไม่มีการลองใหม่เหมือน _post_with_retry เพราะเมื่อส่งข้อความบางส่วนออกไปแล้ว
        การเริ่มใหม่จะทำให้ผู้ใช้เห็นคำตอบซ้ำสองรอบ ความล้มเหลวกลางคันจึงต้องโยน
        ออกไปให้ผู้เรียกตัดสินใจแทน
        """
        payload: dict[str, Any] = {
            "model": self.chat_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
            "options": {"temperature": temperature},
        }
        try:
            with self._client.stream("POST", "/api/chat", json=payload) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    if chunk := data.get("message", {}).get("content"):
                        yield chunk
                    if data.get("done"):
                        return
        except (httpx.HTTPError, json.JSONDecodeError) as e:
            raise LLMConnectionError(f"chat_stream failed: {type(e).__name__}: {e}"[:200]) from e

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    def _post_with_retry(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 2):
            try:
                resp = self._client.post(path, json=payload)
                resp.raise_for_status()
                return resp.json()
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_exc = e
                logger.warning("ollama %s attempt %d/%d failed: %s", path, attempt, self.max_retries + 1, type(e).__name__)
            except httpx.HTTPStatusError as e:
                # 4xx/5xx จาก Ollama เอง (เช่น model ไม่ถูก pull ไว้) — ไม่ retry ซ้ำ ให้ fail ทันที
                raise LLMConnectionError(f"ollama returned {e.response.status_code}: {e.response.text[:300]}") from e
        raise LLMConnectionError(f"could not reach local LLM at {self.base_url}{path}") from last_exc

    def close(self) -> None:
        self._client.close()
