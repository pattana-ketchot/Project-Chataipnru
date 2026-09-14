"""
แยกหน้าสารบัญออกจากหน้าเนื้อหา

หน้าสารบัญเอ่ยทุกหัวข้อของเล่มพร้อมเลขหน้า เช่น "8. อาชีพที่สามารถประกอบได้หลังสำเร็จการศึกษา ....... 2"
ถ้าไม่ตัดทิ้ง ตัวแบ่งหัวข้อจะเข้าใจว่าหัวข้อทั้งเล่มอยู่ในหน้าเดียว (ปัญหาเดียวกับที่ backend เจอใน
services/program_match.py::_looks_like_table_of_contents)

looks_like_table_of_contents คือกฎเดียวกับของ backend ทุกประการ (มีชุดทดสอบเทียบผลกันใน
eval/mko_extraction_check.py) ไม่ได้ย้ายของ backend มาใช้ร่วมกันใน Phase 1 เพื่อไม่แตะโค้ดที่ production ใช้อยู่
"""
from __future__ import annotations

import re

from pipeline.mko.normalize import fold

_DOT_LEADER = re.compile(r"[.…]{5,}")


def looks_like_table_of_contents(content: str) -> bool:
    """กฎของ backend: จุดนำสายตาตั้งแต่ 3 ชุด หรือสัดส่วนตัวเลขตั้งแต่ 0.33"""
    tokens = content.split()
    if not tokens:
        return False
    numbers = sum(t.strip(".…").isdigit() for t in tokens)
    return len(_DOT_LEADER.findall(content)) >= 3 or numbers / len(tokens) >= 0.33


def is_toc_page(text: str) -> bool:
    """
    หน้านี้เป็นสารบัญหรือไม่ — ดูคำว่าสารบัญช่วงต้นหน้า หรือจุดนำสายตาหลายชุด

    ระดับหน้าไม่ใช้สัดส่วนตัวเลข เพราะหน้าตารางรายวิชามีรหัสวิชาและหน่วยกิตเป็นตัวเลขจำนวนมาก ถ้าใช้เกณฑ์นั้น
    หน้ารายวิชาจะถูกตัดทิ้งไปด้วย
    """
    head = fold(text[:400])
    if "สารบัญ" in head:
        return True
    return len(_DOT_LEADER.findall(text)) >= 5
