"""
Step 4: เรียก embedding model (ผ่าน Local LLM connector) สำหรับแต่ละ chunk

reuse `llm/connector.py` ตัวเดียวกับที่ backend ใช้ เพื่อไม่ให้ logic การเรียก
Ollama กระจัดกระจายหลายที่
"""
from __future__ import annotations

import logging

from llm.connector import OllamaConnector
from pipeline.chunker import Chunk

logger = logging.getLogger("pipeline.embed")


def embed_chunks(connector: OllamaConnector, chunks: list[Chunk], batch_log_every: int = 20) -> list[list[float]]:
    embeddings: list[list[float]] = []
    for i, chunk in enumerate(chunks, start=1):
        embeddings.append(connector.embed(chunk.content))
        if i % batch_log_every == 0:
            logger.info("embedded %d/%d chunks", i, len(chunks))
    return embeddings
