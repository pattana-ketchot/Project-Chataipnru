"""
Step 3: แบ่งข้อความที่ clean แล้วเป็น chunk สำหรับทำ embedding

ใช้ sliding-window แบบนับคำ (word-based) เป็น proxy ของ token count เพื่อไม่ต้อง
พึ่ง tokenizer เฉพาะโมเดล — คร่าวๆ 1 คำอังกฤษ/ไทย ≈ 1-2 token ปรับ CHUNK_SIZE_WORDS
ให้เข้ากับ context window ของ embedding model ที่ใช้จริงได้
"""
from __future__ import annotations

from dataclasses import dataclass

from pipeline.extract_pdf import ExtractedDocument

CHUNK_SIZE_WORDS = 220
CHUNK_OVERLAP_WORDS = 40


@dataclass
class Chunk:
    chunk_index: int
    page_number: int
    content: str
    token_count: int  # approx (word count)


def _split_page_text(text: str) -> list[str]:
    words = text.split()
    if not words:
        return []
    step = CHUNK_SIZE_WORDS - CHUNK_OVERLAP_WORDS
    return [" ".join(words[i : i + CHUNK_SIZE_WORDS]) for i in range(0, len(words), step)]


def chunk_document(doc: ExtractedDocument, min_chars: int = 20) -> list[Chunk]:
    chunks: list[Chunk] = []
    idx = 0
    for page in doc.pages:
        for piece in _split_page_text(page.text):
            if len(piece) < min_chars:
                continue  # ทิ้ง chunk ที่สั้นเกินไป (มักเป็นเศษหน้าเปล่า/ตัวเลขหน้า)
            chunks.append(
                Chunk(
                    chunk_index=idx,
                    page_number=page.page_number,
                    content=piece,
                    token_count=len(piece.split()),
                )
            )
            idx += 1
    return chunks
