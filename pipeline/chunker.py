"""
Step 3: แบ่งข้อความที่ clean แล้วเป็น chunk สำหรับทำ embedding

แบ่งตาม "จำนวนตัวอักษร" ไม่ใช่ "จำนวนคำ"
---------------------------------------
เวอร์ชันแรกใช้ text.split() นับคำแบบเว้นวรรค ซึ่งใช้กับภาษาไทยไม่ได้เพราะ
ภาษาไทยไม่เขียนเว้นวรรคระหว่างคำ ผลที่วัดได้จากคลังเอกสารจริง:

  - chunk ที่บันทึกว่า "115 token" มีขนาดจริง 3,316 ตัวอักษร
  - ขนาด chunk แกว่งตั้งแต่ 22 ถึง 3,780 ตัวอักษร ทั้งที่ตั้งค่าไว้ 220 คำเท่ากันหมด
  - chunk ที่ยาวเกินไปทำให้ embedding model ตอบ 500
    "the input length exceeds the context length" (3 ไฟล์จาก 18 นำเข้าไม่ได้เลย)

การนับตัวอักษรให้ผลที่คาดเดาได้กับทุกภาษา และคุมไม่ให้เกิน context ของ
embedding model ได้จริง

ทางเลือกที่ดีกว่าในอนาคต: ใช้ตัวตัดคำภาษาไทย (เช่น pythainlp) แล้วแบ่งตามขอบเขต
คำจริง จะได้ chunk ที่ไม่ตัดกลางคำ — แลกกับ dependency ที่หนักขึ้นและเวลาประมวลผล
ที่นานขึ้น
"""
from __future__ import annotations

from dataclasses import dataclass

from pipeline.extract_pdf import ExtractedDocument

# nomic-embed-text มี context 2,048 token — ภาษาไทยกินโทเคนเปลืองกว่าอังกฤษมาก
# (ราว 1 โทเคนต่อ 1-2 ตัวอักษร) ตั้งไว้ 1,000 ตัวอักษรเพื่อให้ต่อให้เป็นกรณี
# แย่ที่สุด (1 โทเคน/ตัวอักษร) ก็ยังไม่ถึงครึ่งของ context
CHUNK_SIZE_CHARS = 1000
CHUNK_OVERLAP_CHARS = 150

# ระยะที่ยอมถอยหลังเพื่อหาช่องว่างตัดให้พอดีคำ ถ้าไม่เจอในระยะนี้จะตัดตรงๆ
# (ข้อความไทยล้วนอาจไม่มีช่องว่างเลยตลอดทั้งย่อหน้า)
_BREAK_SEARCH_WINDOW = 120


@dataclass
class Chunk:
    chunk_index: int
    page_number: int
    content: str
    token_count: int  # ประมาณการ ดู _estimate_tokens


def _estimate_tokens(text: str) -> int:
    """
    ประมาณจำนวนโทเคนแบบหยาบ: อักษรไทยราว 2 ตัวอักษร/โทเคน ส่วนที่เหลือ
    (อังกฤษ/ตัวเลข) ราว 4 ตัวอักษร/โทเคน — ใช้เพื่อเก็บสถิติและตรวจสอบเท่านั้น
    ไม่ใช่ค่าจาก tokenizer จริงของโมเดล
    """
    thai = sum(1 for c in text if "฀" <= c <= "๿")
    other = len(text) - thai
    return round(thai / 2 + other / 4)


def _split_page_text(text: str) -> list[str]:
    """แบ่งข้อความหนึ่งหน้าเป็นหน้าต่างตัวอักษรที่ซ้อนทับกัน"""
    text = text.strip()
    if not text:
        return []

    pieces: list[str] = []
    start = 0
    step = CHUNK_SIZE_CHARS - CHUNK_OVERLAP_CHARS
    while start < len(text):
        end = min(start + CHUNK_SIZE_CHARS, len(text))

        # ถ้ายังไม่ถึงท้ายข้อความ ลองถอยมาตัดที่ช่องว่างเพื่อไม่ให้คำขาดกลาง
        if end < len(text):
            window = text.rfind(" ", end - _BREAK_SEARCH_WINDOW, end)
            if window > start:
                end = window

        piece = text[start:end].strip()
        if piece:
            pieces.append(piece)

        if end >= len(text):
            break
        start = max(end - CHUNK_OVERLAP_CHARS, start + step)

    return pieces


def chunk_document(doc: ExtractedDocument, min_chars: int = 20) -> list[Chunk]:
    chunks: list[Chunk] = []
    idx = 0
    for page in doc.pages:
        for piece in _split_page_text(page.text):
            if len(piece) < min_chars:
                continue  # ทิ้ง chunk ที่สั้นเกินไป (มักเป็นเศษหน้าเปล่า/เลขหน้า)
            chunks.append(
                Chunk(
                    chunk_index=idx,
                    page_number=page.page_number,
                    content=piece,
                    token_count=_estimate_tokens(piece),
                )
            )
            idx += 1
    return chunks
