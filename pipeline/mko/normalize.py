"""
ทำข้อความให้เทียบหัวข้อได้ โดยยังชี้กลับไปยังตำแหน่งในข้อความต้นฉบับได้เสมอ

ทำไมต้องมี
---------
หัวข้อเดียวกันถูกดึงออกมาจาก PDF หลายรูป เจอในคลังจริง:
    "ระบบการจัดการศึกษา"  กับ  "ระบบกำรจัดกำรศึกษำ"   (ma64, bio2568 — ฟอนต์เข้ารหัส า เป็น ำ)
    "จำนวนหน่วยกิต"      กับ  "จ ำนวนหน่วยกิต"        (สระอำแตกเป็นช่องว่าง + ำ)
    "หมวดที่ ๓"          กับ  "หมวดที่ 3"
การค้นแบบตรงตัวจึงพลาดหัวข้อจริง ส่วนการแก้ข้อความต้นฉบับให้ "ถูก" เสี่ยงทำให้ค่าที่เก็บเพี้ยนแบบเงียบๆ

ที่นี่จึงไม่แก้ข้อความต้นฉบับเลย แต่สร้างข้อความอีกชุดไว้ค้นเท่านั้น โดยทำแบบเดียวกันทั้งกับข้อความและกับรูปแบบที่ค้น
(ตัดช่องว่าง, ำ → า, เลขไทย → เลขอารบิก) และเก็บตารางตำแหน่งไว้แปลงผลการค้นกลับเป็นช่วงของข้อความต้นฉบับ
ค่าที่นำไปเก็บและข้อความที่ยกมาเป็นหลักฐานจึงตัดจากข้อความต้นฉบับเสมอ
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

_THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")
_ZERO_WIDTH = {"​", "‌", "‍", "﻿"}


def _fold_char(ch: str) -> str:
    """อักขระหนึ่งตัวในรูปที่ใช้ค้น คืนสตริงว่างถ้าต้องตัดทิ้ง"""
    if ch.isspace() or ch in _ZERO_WIDTH:
        return ""
    if ch == "ำ":
        return "า"
    return ch.translate(_THAI_DIGITS)


def fold(text: str) -> str:
    """รูปที่ใช้ค้นของข้อความ ใช้กับรูปแบบที่จะค้นด้วย"""
    return "".join(_fold_char(ch) for ch in unicodedata.normalize("NFC", text))


@dataclass(frozen=True)
class FoldedText:
    """ข้อความในรูปที่ใช้ค้น พร้อมตำแหน่งในข้อความต้นฉบับของอักขระแต่ละตัว"""

    original: str
    folded: str
    index: tuple[int, ...]

    @classmethod
    def of(cls, original: str) -> "FoldedText":
        chars: list[str] = []
        index: list[int] = []
        for i, ch in enumerate(original):
            folded = _fold_char(ch)
            chars.append(folded)
            index.extend([i] * len(folded))
        return cls(original, "".join(chars), tuple(index))

    def span(self, start: int, end: int) -> tuple[int, int]:
        """แปลงช่วงในข้อความที่ใช้ค้นเป็นช่วงในข้อความต้นฉบับ"""
        if start >= end:
            pos = self.index[start] if start < len(self.index) else len(self.original)
            return pos, pos
        return self.index[start], self.index[end - 1] + 1

    def search(self, pattern: str | re.Pattern, pos: int = 0, endpos: int | None = None):
        """ค้นรูปแบบ (เขียนในรูปที่ใช้ค้นแล้ว) คืน match หรือ None ตำแหน่งใน match เป็นของข้อความที่ใช้ค้น"""
        rx = pattern if isinstance(pattern, re.Pattern) else re.compile(pattern)
        return rx.search(self.folded, pos, len(self.folded) if endpos is None else endpos)

    def folded_pos(self, original_pos: int) -> int:
        """ตำแหน่งแรกในข้อความที่ใช้ค้นที่มาจากตำแหน่งต้นฉบับนี้หรือหลังจากนั้น"""
        lo, hi = 0, len(self.index)
        while lo < hi:
            mid = (lo + hi) // 2
            if self.index[mid] < original_pos:
                lo = mid + 1
            else:
                hi = mid
        return lo


def squash(text: str) -> str:
    """ยุบช่องว่างและบรรทัดว่างให้อ่านง่าย ใช้กับค่าที่แสดงผล ไม่ใช้กับข้อความที่ยกมาเป็นหลักฐาน"""
    return re.sub(r"\s+", " ", text).strip()
