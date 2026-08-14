"""
Step 2: Data Cleaning ก่อนนำเข้าสู่ Database

งานหลัก:
  - แปลงอักขระไทยใน Private Use Area กลับเป็น Thai Unicode มาตรฐาน (ดู _PUA_MAP)
  - ประกอบสระ ำ ที่ถูกแยกเป็น "ช่องว่าง + า" กลับคืน
  - ลบ header/footer ที่ซ้ำทุกหน้า (เช่น "Confidential - Company X - Page N")
  - normalize whitespace/line-break, ลบ hyphenation ที่ตัดคำข้ามบรรทัด
  - ลบอักขระควบคุม/null byte ที่อาจติดมาจาก PDF ที่สร้างไม่สมบูรณ์
  - ลบ header/footer ซ้ำเป็น heuristic ที่ดีพอสำหรับ PDF หลักสูตรทั่วไป
    (บรรทัดที่ปรากฏซ้ำใน >60% ของหน้าทั้งหมด มักเป็น header/footer ไม่ใช่เนื้อหา)

SECURITY:
  - เนื้อหาที่ clean แล้วยังคง "ข้อมูลที่ไม่น่าเชื่อถือ" อยู่ (มาจากไฟล์ user
    อัปโหลด) — ห้าม eval/exec เนื้อหานี้ และตอน insert DB ต้องผ่าน parameterized
    query เท่านั้น (ดู ingest.py)
"""
from __future__ import annotations

import logging
import re
import unicodedata
from collections import Counter

from pipeline.extract_pdf import ExtractedDocument, ExtractedPage

logger = logging.getLogger("pipeline.clean")

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_MULTI_SPACE_RE = re.compile(r"[ \t]+")
_MULTI_BLANK_LINE_RE = re.compile(r"\n{3,}")
_HYPHEN_LINEBREAK_RE = re.compile(r"(\w)-\n(\w)")  # "informa-\ntion" -> "information"

# ---------------------------------------------------------------------------
# แก้ปัญหาฟอนต์ไทยใน PDF ที่แม็ปวรรณยุกต์/สระไปยัง Private Use Area (U+F700-F71F)
#
# ที่มา: ฟอนต์ไทยตระกูล Angsana/Cordia (และ PDF ที่สร้างจาก Word รุ่นเก่า) ใช้
# glyph คนละตัวสำหรับวรรณยุกต์ตัวเดียวกัน ขึ้นกับว่าวางบนพยัญชนะที่มีหางสูง
# (ป ฝ ฟ) หรือมีสระบนอยู่ก่อนแล้วหรือไม่ — รูปแปรพวกนี้ไม่มีที่อยู่ใน Thai
# Unicode block จึงถูกยัดไว้ใน PUA เวลาดึงข้อความออกมาจึงได้ codepoint ที่
# ค้นหาหรือเทียบคำไม่ได้เลย
#
# ผลกระทบถ้าไม่แก้: "คอมพิวเตอร" ไม่มีวันแมตช์คำค้น "คอมพิวเตอร์" และ
# embedding ที่ได้ก็เพี้ยนทั้งก้อน — ในคลังเอกสารชุดนี้พบ 4 ไฟล์จาก 18 ที่ได้รับ
# ผลกระทบแทบทุกบรรทัด (animation64, cs61, fs61, it66)
#
# ตารางนี้สอบทานจากบริบทจริงในเอกสาร เช่น 'ไดจัด' = "ได้จัด" -> F70B = ้
# ---------------------------------------------------------------------------
_PUA_MAP = {
    # F701-F709: วางเยื้องซ้าย ใช้กับพยัญชนะที่มีหางสูง (ป ฝ ฟ ฬ)
    "": "ิ",  # ิ   'เปดสอน'    -> เปิดสอน
    "": "ี",  # ี   'ปรับปรุงป' -> ปรับปรุงปี
    "": "ึ",  # ึ   'ฝกงาน'     -> ฝึกงาน
    "": "ื",  # ื   'ฝน'        -> ฝืน
    "": "่",  # ่   'ฝาย'       -> ฝ่าย
    "": "้",  # ้   'เปาหมาย'   -> เป้าหมาย
    "": "๊",  # ๊   (ตามลำดับของบล็อก ไม่พบในคลังนี้)
    "": "๋",  # ๋   'กระปอง'    -> กระป๋อง
    "": "์",  # ์   'ศิลป'      -> ศิลป์
    # F70A-F70E: ลดระดับลง ใช้เมื่อไม่มีสระบนอยู่ก่อน
    "": "่",  # ่   'กลาว'      -> กล่าว
    "": "้",  # ้   'ไดจัด'     -> ได้จัด
    "": "๊",  # ๊   'เฟสบุก'    -> เฟสบุ๊ก
    "": "๋",  # ๋   (ตามลำดับของบล็อก ไม่พบในคลังนี้)
    "": "์",  # ์   'คอมพิวเตอร' -> คอมพิวเตอร์
    # F70F: ญ ที่ตัดเชิงออก ใช้เมื่อมีสระล่างตามมา
    "": "ญ",  # ญ   'กตัญู'     -> กตัญญู
    # F710-F717: รูปแปรที่ใช้คู่กับสระ ั
    "": "ั",  # ั   'ฟง'        -> ฟัง
    "": "็",  # ็   (ตามลำดับของบล็อก ไม่พบในคลังนี้)
    "": "็",  # ็   'จำเปน'     -> จำเป็น
    "": "่",  # ่   'ฝง'  -> ฝั่ง
    "": "้",  # ้   'ปน'  -> ปั้น
    "": "๊",  # ๊   (ตามลำดับของบล็อก ไม่พบในคลังนี้)
    "": "๋",  # ๋   (ตามลำดับของบล็อก ไม่พบในคลังนี้)
    "": "์",  # ์   (ตามลำดับของบล็อก ไม่พบในคลังนี้)
}
_PUA_TRANS = str.maketrans(_PUA_MAP)
_PUA_RANGE_RE = re.compile(r"[-]")

# สระ ำ ที่ถูกแยกออกเป็นสองส่วนตอน extract: "ค าน า" -> "คำนำ"
# ปลอดภัยเพราะภาษาไทยไม่มีคำที่ขึ้นต้นด้วยสระ า — เจอ "พยัญชนะ + ช่องว่าง + า"
# เมื่อไหร่ แปลว่าเป็นซากของ ำ ที่แตกออกมาเสมอ
# ในคลังนี้พบ 13,292 ครั้ง กระจายใน 12 จาก 18 ไฟล์
_BROKEN_SARA_AM_RE = re.compile(r"([ก-ฮ]) (า)")

# ำ อีกรูปหนึ่ง: บาง PDF เข้ารหัสเป็น นิคหิต (U+0E4D) + สระอา (U+0E32) ซึ่ง
# มองด้วยตาเหมือน ำ ทุกประการแต่คนละ codepoint จึงเทียบคำกันไม่ติด
# ในคลังนี้ทำให้ "เครื่องสำอาง" ของ cos66 กับ cosmetic61 (หลักสูตรเดียวกัน
# คนละปี) กลายเป็นคนละคำ ทั้งที่ควรค้นเจอด้วยคำค้นเดียวกัน
_NIKHAHIT_SARA_AA_RE = re.compile("ํา")


def _fix_thai_pua(text: str) -> str:
    """แปลง PUA กลับเป็น Thai Unicode และเตือนถ้าเจอ codepoint ที่ยังไม่รู้จัก"""
    unknown = set(_PUA_RANGE_RE.findall(text)) - set(_PUA_MAP)
    if unknown:
        # ไม่เดาค่าเอง เพราะเดาผิดจะทำให้ข้อความเพี้ยนแบบเงียบๆ ซึ่งตรวจยากกว่า
        # การปล่อยให้อักขระแปลกปลอมหลงเหลืออยู่แล้วเห็นได้ชัดตอนตรวจข้อมูล
        logger.warning(
            "พบอักขระ PUA ที่ยังไม่มีในตารางแปลง: %s",
            ", ".join(f"U+{ord(c):04X}" for c in sorted(unknown)),
        )
    return text.translate(_PUA_TRANS)


def _fix_broken_sara_am(text: str) -> str:
    text = _NIKHAHIT_SARA_AA_RE.sub("ำ", text)
    return _BROKEN_SARA_AM_RE.sub(r"\1ำ", text)


def _strip_control_chars(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    return _CONTROL_CHARS_RE.sub("", text)


def _normalize_whitespace(text: str) -> str:
    text = _HYPHEN_LINEBREAK_RE.sub(r"\1\2", text)
    text = _MULTI_SPACE_RE.sub(" ", text)
    text = _MULTI_BLANK_LINE_RE.sub("\n\n", text)
    return text.strip()


def _detect_repeated_lines(pages: list[ExtractedPage], min_ratio: float = 0.6) -> set[str]:
    """หาบรรทัดที่ซ้ำในหลายหน้า (มักคือ header/footer) เพื่อตัดทิ้ง"""
    if len(pages) < 3:
        return set()  # เอกสารสั้นเกินไปจะ false-positive ง่าย ข้ามการตัด header/footer
    line_counts: Counter[str] = Counter()
    for page in pages:
        lines = {line.strip() for line in page.text.splitlines() if line.strip()}
        line_counts.update(lines)
    threshold = max(2, int(len(pages) * min_ratio))
    return {line for line, count in line_counts.items() if count >= threshold and len(line) < 120}


def clean_document(doc: ExtractedDocument) -> ExtractedDocument:
    # ซ่อมอักขระให้ถูกต้องก่อนตรวจ header/footer ซ้ำ ไม่งั้นบรรทัดเดียวกันที่
    # ฟอนต์ต่างกันจะถูกนับเป็นคนละบรรทัดจนตัดไม่ออก
    repaired = [
        ExtractedPage(page_number=p.page_number, text=_fix_broken_sara_am(_fix_thai_pua(p.text)))
        for p in doc.pages
    ]
    repeated = _detect_repeated_lines(repaired)

    cleaned_pages: list[ExtractedPage] = []
    for page in repaired:
        text = _strip_control_chars(page.text)
        if repeated:
            lines = [ln for ln in text.splitlines() if ln.strip() not in repeated]
            text = "\n".join(lines)
        text = _normalize_whitespace(text)
        cleaned_pages.append(ExtractedPage(page_number=page.page_number, text=text))

    return ExtractedDocument(file_sha256=doc.file_sha256, page_count=doc.page_count, pages=cleaned_pages)
