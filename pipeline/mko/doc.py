"""
ข้อความทั้งเล่มที่ต่อจากข้อความรายหน้า พร้อมตำแหน่งหน้าของทุกช่วง

ต่อหน้าด้วยขึ้นบรรทัดใหม่หนึ่งตัว (PAGE_JOIN) ซึ่งเป็นตัวเดียวกับที่ trigger mko.check_evidence_quote ใช้ต่อหน้า
ข้อความที่ตัดจากช่วงใดของเล่มนี้จึงผ่านการตรวจหลักฐานของฐานข้อมูลเสมอ ถ้าตัวคั่นสองฝั่งไม่ตรงกัน หลักฐานที่คร่อมหน้า
จะถูกฐานข้อมูลปฏิเสธทั้งที่ข้อความถูกต้อง
"""
from __future__ import annotations

import bisect
import re
from collections import Counter
from dataclasses import dataclass, field

from pipeline.mko.normalize import FoldedText, fold
from pipeline.mko.toc import is_toc_page

PAGE_JOIN = "\n"

# อักขระของเลขหน้าและคำประจำหน้า เมื่อตัดออกแล้วไม่เหลืออะไรแปลว่าบรรทัดนั้นไม่ใช่เนื้อหา
_NOISE_TOKENS = re.compile(r"[\d.|:~\-–()]|มคอ|หน้า")

# ข้อความที่ถูกฟอนต์เข้ารหัส า เป็น ำ (เช่น "กำร", "ภำษำ") มี ำ มากผิดสัดส่วนเมื่อเทียบกับ า
# ภาษาไทยปกติมี า มากกว่า ำ หลายเท่า ค่าที่ใช้ตัดสินดูเหตุผลใน suspect_encoding
_SUSPECT_MIN_COUNT = 2
_SUSPECT_RATIO = 0.5


def suspect_encoding(text: str, min_count: int = _SUSPECT_MIN_COUNT) -> bool:
    """
    ข้อความนี้มีร่องรอยฟอนต์เข้ารหัส า เป็น ำ หรือไม่

    ใช้สัดส่วน ำ ต่อ า แทนการไล่รายการคำที่เพี้ยน เพราะความเพี้ยนเกิดกับทุกคำที่มี า ไม่ใช่เฉพาะคำที่รู้จัก
    """
    sara_am = text.count("ำ")
    sara_aa = text.count("า")
    return sara_am >= min_count and sara_am > _SUSPECT_RATIO * sara_aa


@dataclass(frozen=True)
class Page:
    page_number: int
    text: str
    source: str
    is_toc: bool
    encoding_suspect: bool


@dataclass
class DocText:
    filename: str
    pages: list[Page]
    text: str = field(init=False)
    starts: list[int] = field(init=False)
    folded: FoldedText = field(init=False)

    header_keys: set[str] = field(init=False)

    def __post_init__(self) -> None:
        starts, parts, pos = [], [], 0
        for page in self.pages:
            starts.append(pos)
            parts.append(page.text)
            pos += len(page.text) + len(PAGE_JOIN)
        self.starts = starts
        self.text = PAGE_JOIN.join(parts)
        self.folded = FoldedText.of(self.text)
        self.header_keys = self._running_headers()

    # ---- หัวกระดาษและเลขหน้า ----
    #
    # รายการที่ยาวถึงท้ายหน้าเคยได้หัวกระดาษของหน้าถัดไปติดมาด้วย เจอในคลังจริง: อาชีพข้อสุดท้ายของ cs61 กลายเป็น
    # "ผู้ประกอบการด้านคอมพิวเตอร์ มคอ.2 คณะวิทยาศาสตร์และเทคโนโลยี มหาวิทยาลัยราชภัฏพระนคร 3" เพราะหัวข้อถัดไป
    # (ข้อ 9) อยู่หลังหัวกระดาษของหน้าถัดไป ขั้นทำความสะอาดเดิมตัดได้เฉพาะบรรทัดที่ซ้ำเหมือนกันทุกตัวอักษร
    # แต่หัวกระดาษมีเลขหน้าต่างกันทุกหน้า
    def _running_headers(self) -> set[str]:
        """บรรทัดช่วงต้นหน้าที่ซ้ำกันอย่างน้อย 30% ของหน้าเมื่อตัดตัวเลขออก"""
        counts: Counter[str] = Counter()
        for page in self.pages:
            seen = set()
            for line in [ln for ln in page.text.split("\n") if ln.strip()][:3]:
                key = re.sub(r"\d", "", fold(line))
                if len(key) >= 6:
                    seen.add(key)
            counts.update(seen)
        threshold = max(3, int(len(self.pages) * 0.3))
        return {key for key, n in counts.items() if n >= threshold}

    def is_noise_line(self, line: str) -> bool:
        """บรรทัดว่าง เลขหน้า (เช่น "~ 1 ~", "มคอ.2 13") หรือหัวกระดาษที่ซ้ำหลายหน้า"""
        folded = fold(line)
        if not folded or not _NOISE_TOKENS.sub("", folded):
            return True
        return re.sub(r"\d", "", folded) in self.header_keys

    def content_start(self, index: int) -> int:
        """ตำแหน่งเริ่มเนื้อหาของหน้า หลังหัวกระดาษและเลขหน้าช่วงต้นหน้า"""
        pos = 0
        for line in self.pages[index].text.split("\n"):
            if not self.is_noise_line(line):
                return self.starts[index] + pos
            pos += len(line) + 1
        return self.page_end(index)

    def content_end(self, index: int) -> int:
        """ตำแหน่งจบเนื้อหาของหน้า ก่อนท้ายกระดาษและเลขหน้าช่วงท้ายหน้า"""
        text = self.pages[index].text
        end = len(text)
        for line in reversed(text.split("\n")):
            if not self.is_noise_line(line):
                break
            end -= len(line) + 1
        return self.starts[index] + max(0, end)

    def readable(self, start: int, end: int) -> str:
        """ข้อความของช่วงสำหรับแสดงผล โดยไม่เอาหัวกระดาษ/เลขหน้าตรงรอยต่อหน้า (หลักฐานยังเก็บช่วงเต็มตามต้นฉบับ)"""
        first = self.page_index(start)
        last = self.page_index(max(start, end - 1))
        parts = []
        for index in range(first, last + 1):
            s = start if index == first else max(start, self.content_start(index))
            e = end if index == last else min(end, self.content_end(index))
            if e > s:
                parts.append(self.text[s:e])
        return " ".join(" ".join(parts).split())

    @classmethod
    def from_records(cls, filename: str, records) -> "DocText":
        """สร้างจาก PageRecord ของ pipeline.pages หรือแถวที่มี page_number / text_clean / text_source"""
        pages = []
        for r in records:
            text = r.text_clean
            pages.append(Page(r.page_number, text, r.text_source, is_toc_page(text), suspect_encoding(text, min_count=5)))
        return cls(filename, pages)

    # ---- ตำแหน่ง ----
    def page_index(self, offset: int) -> int:
        return max(0, bisect.bisect_right(self.starts, offset) - 1)

    def page_at(self, offset: int) -> Page:
        return self.pages[self.page_index(offset)]

    def page_start(self, index: int) -> int:
        return self.starts[index]

    def page_end(self, index: int) -> int:
        return self.starts[index] + len(self.pages[index].text)

    def pages_of(self, start: int, end: int) -> list[Page]:
        first = self.page_index(start)
        last = self.page_index(max(start, end - 1))
        return self.pages[first:last + 1]

    # ---- ข้อความ ----
    def trimmed(self, start: int, end: int) -> tuple[int, int]:
        """ตัดช่องว่างและเครื่องหมาย : ที่หัวท้ายช่วงออก"""
        while start < end and (self.text[start].isspace() or self.text[start] in ":："):
            start += 1
        while end > start and (self.text[end - 1].isspace() or self.text[end - 1] in ":："):
            end -= 1
        return start, end

    def slice(self, start: int, end: int) -> str:
        return self.text[start:end]

    # ---- ค้นหา ----
    def find(self, pattern: str | re.Pattern, start: int = 0, end: int | None = None, skip_toc: bool = True):
        """
        ค้นรูปแบบในรูปที่ใช้ค้น (ดู normalize.fold) คืน (ต้นฉบับเริ่ม, ต้นฉบับจบ, match) ของตัวแรกที่ไม่อยู่ในหน้าสารบัญ
        """
        for hit in self.find_all(pattern, start, end, skip_toc):
            return hit
        return None

    def find_all(self, pattern: str | re.Pattern, start: int = 0, end: int | None = None, skip_toc: bool = True):
        rx = pattern if isinstance(pattern, re.Pattern) else re.compile(pattern)
        f_start = self.folded.folded_pos(start)
        f_end = len(self.folded.folded) if end is None else self.folded.folded_pos(end)
        for m in rx.finditer(self.folded.folded, f_start, f_end):
            s, e = self.folded.span(m.start(), m.end())
            if skip_toc and self.page_at(s).is_toc:
                continue
            yield s, e, m

    def span_has_ocr(self, start: int, end: int) -> bool:
        return any(p.source in ("ocr", "text_layer+ocr") for p in self.pages_of(start, end))

    def span_in_toc(self, start: int, end: int) -> bool:
        return any(p.is_toc for p in self.pages_of(start, end))
