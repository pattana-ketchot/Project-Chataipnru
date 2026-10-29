"""
คัดว่า "ชิ้นเอกสารไหนรองรับคำตอบนี้จริง" ออกจาก "รายการที่การค้นหยิบมา"

ทำไมต้องแยกสองอย่างนี้
---------------------
การค้นด้วยเวกเตอร์คืนชิ้นที่ "ใกล้เคียงคำถาม" มา 20–25 ชิ้นต่อคำถาม ซึ่งไม่ใช่สิ่งเดียวกับ
ชิ้นที่ "ถูกใช้เขียนคำตอบ" · ตรวจเมื่อ 14 ต.ค. 2569 พบว่าคำถามคุณสมบัติผู้เข้าศึกษาของ
เทคโนโลยีสารสนเทศได้ citation อันดับหนึ่งเป็น it66.pdf หน้า 161 ซึ่งเป็นภาคผนวกข้อบังคับ
การรับเข้าของมหาวิทยาลัย (เรื่องประวัติอาชญากรรม) ขณะที่คำตอบจริงมาจากหน้า 16 §2.2
การหยิบ citation คะแนนสูงสุดมาแสดงเป็น "ที่มา" จึงพาผู้ใช้ไปหน้าที่ไม่ได้รองรับคำตอบ

วิธีที่ใช้
---------
เทียบ n-gram ระดับตัวอักษรระหว่างข้อความคำตอบกับเนื้อชิ้นเอกสาร แล้วเลือกชิ้นที่ "ครอบ
ข้อความคำตอบ" ได้มากที่สุดแบบไล่เก็บ (greedy set cover) จึงรองรับคำตอบที่สังเคราะห์จาก
หลายเอกสารได้เอง · เป็นการคำนวณด้วยโค้ด ไม่เรียกโมเดล ผลเดิมทุกครั้งสำหรับข้อความเดิม

ข้อความไทยในเอกสารชุดนี้แทรกช่องว่างกลางคำและเก็บวรรณยุกต์ไว้ใน Private Use Area
(ดู pipeline/mko/extract_list_items.py) จึงต้องตัดสองอย่างนั้นออกก่อนเทียบ ไม่งั้นข้อความ
เดียวกันจะเทียบไม่ตรงเพราะต่างกันแค่รูปอักขระ

ถ้าไม่มีชิ้นใดครอบคำตอบถึงเกณฑ์ **จะไม่เดาเลขหน้าให้** แต่คืนค่าว่างเพื่อให้ผู้เรียกบอก
ผู้ใช้ว่ายังชี้หน้าที่รองรับไม่ได้
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Protocol, Sequence

# ความยาว n-gram — วัดกับคำตอบจริงห้าข้อเมื่อ 14 ต.ค. 2569 กวาดค่า 5/6/7/10
#
# ยาว 10 ตัวอักษรจับรายการแบบตารางไม่ได้ เพราะเล่มมีรหัสวิชาคั่นกลาง — คำตอบ
# "มีแคลคูลัส 1, 2, 3 และ 4" จึงเทียบไม่ติดกับหน้าที่มีรายชื่อครบทั้งสี่วิชา (ma64.pdf หน้า 142)
# ยาว 6 จับหน้านั้นได้ และยังเลือกหน้า 16 (ไม่ใช่หน้า 161) ให้คำถามคุณสมบัติผู้เข้าศึกษา
# สั้นกว่า 5 เริ่มชนพยางค์ทั่วไป
GRAM = 6
# ชิ้นแรกต้องครอบคำตอบได้ไม่น้อยกว่านี้ ไม่ถึงเกณฑ์ถือว่ายังยืนยันที่มาไม่ได้
MIN_COVERAGE = 0.08
# ชิ้นถัดไปต้องเพิ่มความครอบคลุมได้ไม่น้อยกว่านี้ ไม่งั้นไม่ต้องเพิ่มที่มา
MIN_GAIN = 0.05
# พอครอบได้เท่านี้ก็หยุด ไม่ต้องไล่ให้ครบทุกชิ้น
ENOUGH = 0.90
MAX_SOURCES = 4
# ข้อความประจำเล่ม (ชื่อหลักสูตร ชื่อปริญญา หน่วยกิตรวม) โปล่อยู่หลายหน้า ถ้านับรวม
# ด้วย ชิ้นที่ไม่เกี่ยวกับสาระของคำตอบก็ได้ความครอบคลุมสูง — คำถามวิชาแคลคูลัสเคยเลือกหน้า
# ตารางเปรียบเทียบหลักสูตรเก่า-ใหม่มาเป็นที่มา เพราะชื่อหลักสูตรกับเลข 130 ซ้ำกับคำตอบ
# จึงนับเฉพาะ n-gram ที่โปล่ไม่เกินสัดส่วนนี้ของชิ้นที่ค้นได้
COMMON_SHARE = 0.4

_MARKS = re.compile(r"[ัิ-ฺ็-๎-\s]")
# บรรทัดที่มาที่ระบบเติมเอง ไม่ใช่เนื้อคำตอบ จึงไม่นับเป็นสิ่งที่ต้องหาหลักฐานรองรับ
_SOURCE_LINE = re.compile(r"^\s*(ที่มา|หมายเหตุ)\s*:.*$", re.MULTILINE)

# คำที่นำหน้าการไล่รายการในคำตอบ และตัวคั่นระหว่างรายการ
#
# ใช้กับ "คำตอบที่ไล่ชื่อสิ่งต่าง ๆ" เท่านั้น (ดู list_items) — คำตอบความเรียงยังเดินเส้นทาง
# เทียบกรามตามเดิมทุกประการ
_LIST_MARKER = re.compile(r"(?:ได้แก่|เช่น|ดังนี้|ประกอบด้วย|มีดังนี้)\s*[:：]?\s*")
_LIST_SPLIT = re.compile(r"\s*(?:,|·|•|;|และ|กับ|หรือ)\s*")
_PAREN = re.compile(r"\([^)]*\)")
# วงเล็บที่ข้างในไม่มีอักษรไทยเลย = ชื่อ/คำแปลภาษาอังกฤษที่คำตอบใส่กำกับไว้
_PAREN_LATIN = re.compile(r"\(([^()฀-๿]{3,})\)")
# คำที่ขึ้น "ประโยคขยาย" ต่อท้ายรายการสุดท้าย เช่น "… และแคลคูลัส 4 ซึ่งจัดอยู่ในกลุ่มวิชาแกน
# และหมวดวิชาเฉพาะ" — ข้อความหลังคำเหล่านี้ไม่ใช่สมาชิกของรายการ จึงตัดที่จุดนี้แล้วหยุดเก็บ
# (วัดจากคำตอบจริงของข้อ r1-05 เมื่อ 15 ต.ค. 2569 ซึ่งได้รายการเกินมาสองชิ้น)
_CLAUSE = re.compile(r"\s*(?:ซึ่ง|โดย|ทั้งนี้|อยู่ใน|จัดอยู่|ตามที่|เพื่อ)")
# คำลงท้ายสุภาพที่คำตอบติดมาท้ายรายการสุดท้าย ("…และแคลคูลัส 4 (4093408) ครับ")
_PARTICLE = re.compile(r"(?:\s*(?:ครับ|ค่ะ|คะ|นะ|ด้วย|เลย|แล้ว|นี้))+$")
# บรรทัดที่เป็นหัวข้อย่อย — คำตอบแบบไล่รายการมักขึ้นบรรทัดใหม่ทีละข้อ
_BULLET = re.compile(r"^(?:[-*•·]|\d{1,2}[.)])\s+(.+)$")
# ความยาวของสิ่งที่ยอมรับว่าเป็น "ชื่อรายการ" — สั้นหรือยาวกว่านี้มักเป็นประโยค ไม่ใช่รายการ
_ITEM_MIN, _ITEM_MAX = 2, 60
# ต้องมีรายการตั้งแต่สองชิ้นขึ้นไปจึงถือว่าคำตอบ "ไล่รายการ"
MIN_ITEMS = 2


class Chunk(Protocol):
    """รูปร่างที่ต้องการจากผลการค้น (SearchResultChunk ใช้ได้ตรงๆ)"""

    chunk_id: object
    course_id: object
    course_title: str
    page_number: int | None
    content: str
    score: float


@dataclass(frozen=True)
class Support:
    chunk_id: object
    course_id: object
    course_title: str
    page_number: int | None
    # สัดส่วนของข้อความคำตอบที่ชิ้นนี้ครอบได้ (ไม่ใช่คะแนนการค้น และไม่ใช่ความมั่นใจว่าคำตอบถูก)
    coverage: float


def normalise(text: str) -> str:
    return _MARKS.sub("", text or "")


def _grams(text: str, n: int = GRAM) -> set[str]:
    flat = normalise(text)
    if len(flat) < n:
        return {flat} if flat else set()
    return {flat[i:i + n] for i in range(len(flat) - n + 1)}


# อักขระคั่นที่ใช้แทน "กรอบของคำตอบ" ก่อนตัดกราม — ไม่ปรากฏในข้อความเอกสาร
_MASK = "\x00"
# ถ้อยคำกรอบของคำตอบเอง: คำเกริ่นรายการ คำเชื่อม และคำลงท้ายสุภาพ
#
# คำเหล่านี้เป็นวิธีเรียบเรียงของคำตอบ ไม่ใช่สาระที่ต้องหาหลักฐานรองรับ · เป็นชุดปิด
# จึงตัดได้แม้สั้นกว่าหนึ่งกราม ต่างจากกรอบอื่น (คำถาม ชื่อหลักสูตร) ที่ตัดเฉพาะเมื่อยาวพอ
_FRAME_WORDS = ("ได้แก่", "ประกอบด้วย", "มีดังนี้", "ดังนี้", "ต่อไปนี้", "เช่น",
                "แบ่งออกเป็น", "แบ่งเป็น", "ครับ", "ค่ะ", "คะ")


def _masked_grams(text: str, frames: Sequence[str], n: int = GRAM) -> set[str]:
    """
    กรามของข้อความ โดยไม่นับส่วนที่เป็นกรอบ และไม่นับกรามที่คาบรอยต่อของกรอบ

    ทำไมต้องแทนที่ในข้อความ ไม่ใช่ลบชุดกราม
    ---------------------------------------
    เดิมตัดกรอบด้วยการลบ "ชุดกรามของกรอบ" ออกจากชุดกรามของคำตอบ ซึ่งลบกรามที่คาบ
    **รอยต่อ** ระหว่างกรอบกับข้อความถัดไปไม่ได้ · กรามที่คาบปลายชื่อหลักสูตรกับวงเล็บ
    ที่ตามมาจึงรอด และหน้าภาคผนวกที่ทวนชื่อหลักสูตรก็ยังได้คะแนนพอจะถูกเลือกเป็นที่มา
    วัดจริงเมื่อ 15 ต.ค. 2569: คำตอบโครงสร้างหลักสูตรเทคโนโลยีสารสนเทศเลือก it66.pdf
    หน้า 137 (หน้าผลสำรวจความเห็นอาจารย์ ไม่มีเรื่องโครงสร้างเลย) ด้วย coverage 0.119
    จากกรามของคำว่า "สาขาวิชาเทคโนโลยีสารสนเทศ(" และ "รประกอบด้วย"

    วิธีนี้ทำเครื่องหมายตำแหน่งที่เป็นกรอบในข้อความก่อน แล้วตัดกรามทีละช่วงที่เหลือ
    กรามจึงไม่ข้ามจุดที่ตัดกรอบออก และไม่เกิดกรามปลอมจากการเอาสองข้างของกรอบมาต่อกัน

    ทำไมต้องเทียบกรอบ "ระดับกราม" ไม่ใช่สตริงเดียว
    ---------------------------------------------
    คำตอบเขียนชื่อหลักสูตรโดยแทรกชื่อภาษาอังกฤษไว้ในวงเล็บ ("…สาขาวิชาเทคโนโลยีสารสนเทศ
    (Bachelor of Science Program in Information Technology) พ.ศ. 2566") ขณะที่ชื่อใน
    คลังเขียน "(พ.ศ. 2566)" ติดท้าย · สตริงทั้งชื่อจึงไม่ตรงกันเลยแม้เป็นชื่อเดียวกัน
    การตัดจึงต้องทำทีละกรามของกรอบ แล้วลบ "ช่วงตำแหน่ง" ที่กรามนั้นกินไป
    """
    flat = normalise(text)
    if len(flat) < n:
        return _grams(text, n)
    frame_grams: set[str] = set()
    for frame in frames:
        frame_grams |= _grams(frame, n)
    keep = [True] * len(flat)
    for i in range(len(flat) - n + 1):
        if flat[i:i + n] in frame_grams:
            for j in range(i, i + n):
                keep[j] = False
    # ถ้อยคำกรอบชุดปิด: ตัดตามตำแหน่งที่ปรากฏ แม้สั้นกว่าหนึ่งกราม
    for word in _FRAME_WORDS:
        if not (w := normalise(word)):
            continue
        start = flat.find(w)
        while start >= 0:
            for j in range(start, start + len(w)):
                keep[j] = False
            start = flat.find(w, start + 1)
    out: set[str] = set()
    seg: list[str] = []
    for ch, ok in zip(flat + _MASK, keep + [False]):
        if ok:
            seg.append(ch)
            continue
        # ช่วงที่สั้นกว่าหนึ่งกรามเทียบกับชิ้นเอกสารไม่ได้อยู่แล้ว (ชุดของชิ้นมีแต่กรามยาว n)
        # ถ้านับไว้จะเป็นตัวหารที่ไม่มีใครครอบได้ ทำให้ความครอบคลุมต่ำลงโดยไม่มีความหมาย
        if len(seg) >= n:
            s = "".join(seg)
            out |= {s[i:i + n] for i in range(len(s) - n + 1)}
        seg = []
    return out


def answer_body(reply: str) -> str:
    """ตัดบรรทัดที่มา/หมายเหตุที่ระบบเติมออก เหลือเฉพาะเนื้อคำตอบ"""
    return _SOURCE_LINE.sub("", reply or "").strip()


def list_items(reply: str) -> tuple[str, ...]:
    """
    รายการที่คำตอบ "ไล่ชื่อ" ออกมา — คืน () ถ้าคำตอบไม่ได้ไล่รายการ

    ทำไมต้องรู้ว่าคำตอบไล่รายการ
    ---------------------------
    คำตอบแบบรายการมีหน่วยความถูกต้องเป็น "รายชื่อ" ไม่ใช่ถ้อยคำรวม · วัดเมื่อ 15 ต.ค. 2569
    (ข้อ r1-05 บน production) คำตอบ "มีแคลคูลัส 1-4" ได้ที่มาเป็น ma64.pdf หน้า 139 ซึ่งเป็น
    ตารางเปรียบเทียบที่ไม่มีคำว่าแคลคูลัสเลย เพราะหน้านั้นทวนชื่อหลักสูตรภาษาไทย-อังกฤษ
    ซึ่งกินสัดส่วนกรามของคำตอบมากกว่าชื่อวิชาทั้งสี่ (วัดได้ coverage 0.292 ต่อ 0.0796)
    ส่วนหน้าที่มีรายชื่อครบทั้งสี่วิชา (หน้า 142) แพ้เพราะชื่อวิชาซ้ำกันหลายหน้า ตัวกรอง
    กรามที่โปล่จึงตัดมันออกไปอีก

    การเลือกที่มาของคำตอบแบบรายการจึงวัดจาก "รายการใดมีอยู่ในหน้าไหน" ตรง ๆ แทนความคล้าย
    ของข้อความรวม · คำตอบความเรียงไม่เข้าเงื่อนไขนี้ และยังเดินเส้นทางเทียบกรามตามเดิม

    ตัดข้อความในวงเล็บออกจากชื่อรายการ เพราะคำตอบมักใส่ชื่อภาษาอังกฤษกำกับไว้ ขณะที่ตาราง
    ในเอกสารมีเฉพาะชื่อไทยกับรหัสวิชา
    """
    return _split_items(answer_body(reply))[0]


def _split_items(body: str) -> tuple[tuple[str, ...], str]:
    """(รายการที่ไล่ชื่อ, ข้อความส่วนที่ไม่ใช่รายการ) — ส่วนที่ไม่ใช่รายการใช้หาที่มาของความเรียง"""
    out: list[str] = []
    used: set[int] = set()

    # วงเล็บที่เหลือค้างต้องตัดออกด้วย ไม่ใช่เฉพาะคู่ที่ปิดครบ
    #
    # คำตอบใส่รายการย่อยไว้ในวงเล็บ ("(ประกอบด้วยกลุ่มวิชาแกน 15 หน่วยกิต, … หรือ
    # สหกิจศึกษา ไม่น้อยกว่า 7 หน่วยกิต)") แล้วชิ้นสุดท้ายติดวงเล็บปิดมาด้วย ซึ่งไม่มีใน
    # เอกสาร จึงหาไม่พบและถูกรายงานว่ายืนยันไม่ได้ ทั้งที่ it66.pdf หน้า 19 เขียนข้อความ
    # นั้นไว้ตรงตัว (วัดจากคำตอบ detailed เมื่อ 29 ต.ค. 2569)
    _EDGE = " .·:–-()[]"

    def clean(part: str) -> str:
        part = _PAREN.sub("", part).strip(_EDGE)
        return _PARTICLE.sub("", part).strip(_EDGE)

    lines = body.split("\n")
    # แบบที่ 1: ไล่รายการในบรรทัดเดียวหลังคำนำ ("… ได้แก่ ก, ข และ ค")
    for lineno, line in enumerate(lines):
        found = _LIST_MARKER.search(line)
        if found is None:
            continue
        parts: list[str] = []
        for part in _LIST_SPLIT.split(line[found.end():]):
            part = clean(part)
            clause = _CLAUSE.search(part)
            if clause is not None:
                part = clean(part[:clause.start()])
                if _ITEM_MIN <= len(part) <= _ITEM_MAX:
                    parts.append(part)
                break   # ข้อความหลังประโยคขยายไม่ใช่สมาชิกของรายการอีก
            if _ITEM_MIN <= len(part) <= _ITEM_MAX:
                parts.append(part)
        if len(parts) >= MIN_ITEMS:
            out.extend(parts)
            used.add(lineno)

    # แบบที่ 2: ไล่รายการเป็นบรรทัดหัวข้อย่อย ("- 4091403 แคลคูลัส 1 (Calculus 1)")
    bullets: list[str] = []
    bullet_lines: set[int] = set()
    for lineno, line in enumerate(lines):
        hit = _BULLET.match(line.strip())
        if hit is None:
            continue
        item = clean(hit.group(1))
        if _ITEM_MIN <= len(item) <= _ITEM_MAX:
            bullets.append(item)
            bullet_lines.add(lineno)
    if len(bullets) >= MIN_ITEMS:
        out.extend(bullets)
        used |= bullet_lines
    rest = "\n".join(line for i, line in enumerate(lines) if i not in used)
    return tuple(dict.fromkeys(out)), rest


# รหัสวิชา/รหัสอ้างอิงในรายการ — ตัวระบุที่เจาะจงที่สุดที่คำตอบให้มา
_ITEM_CODE = re.compile(r"\d{5,}")


def item_in_flat(item: str, flat: str) -> bool:
    """
    รายการนี้ปรากฏในข้อความของหน้านี้หรือไม่ (flat = ข้อความที่ผ่าน normalise แล้ว)

    ใช้กฎเดียวกันทั้งตอน "เลือกหน้าที่เป็นที่มา" และตอน "ตรวจข้ออ้างรายการ" เพื่อให้สองชั้น
    ไม่ขัดกันเอง · เดิมตอนเลือกใช้การเทียบตรงตัว ตอนตรวจใช้กฎที่ยืดหยุ่นกว่า ผลคือคำตอบที่
    เขียนรายการว่า "แคลคูลัส 1 (Calculus 1) รหัสวิชา 4091403" หาหน้าที่มาไม่ได้เลย แล้วระบบ
    ขึ้นข้อความว่าจับคู่หน้าที่รองรับไม่ได้ ทั้งที่หน้า 142 ของ ma64.pdf มีวิชานั้นอยู่
    (วัดจากการรันในอิมเมจของ release รอบ 17 เมื่อ 15 ต.ค. 2569)

    ลำดับการตรวจ
      1. ข้อความของรายการทั้งชิ้นปรากฏในหน้า
      2. ถ้ารายการมีรหัส (ตัวเลข 5 หลักขึ้นไป) ให้ยึดรหัสเป็นเกณฑ์ — รหัสผิดถือว่าไม่รองรับ
      3. ไม่มีรหัส: ยอมรับเมื่อ **ทุกชื่อยาว** ในชิ้นนั้นปรากฏในหน้า (กรณีชื่อสองชื่อเขียนติดกัน)
         โดยไม่ลดเหลือการตรวจคำเดียว เพื่อให้ "แคลคูลัส 4" ที่เลขผิดยังถูกจับได้
    """
    whole = normalise(item)
    if whole and whole in flat:
        return True
    codes = _ITEM_CODE.findall(item)
    if codes:
        return all(code in flat for code in codes)
    parts = [n for part in re.split(r"\s+", item) if len(n := normalise(part)) >= 6]
    return len(parts) >= 2 and all(part in flat for part in parts)


def _supporting_by_items(items: Sequence[str], chunks: Sequence[Chunk]) -> tuple[Support, ...]:
    """เลือกชิ้นที่ครอบ "รายการ" ได้มากที่สุดแบบไล่เก็บ — ชิ้นที่ไม่มีรายการใดเลยไม่ถูกเลือก"""
    flats = [(c, normalise(c.content)) for c in chunks]
    left = set(items)
    picked: list[Support] = []
    while left and len(picked) < MAX_SOURCES:
        best, best_hits = None, set()
        for c, flat in flats:
            if any(p.chunk_id == c.chunk_id for p in picked):
                continue
            hits = {item for item in left if item_in_flat(item, flat)}
            # เสมอกันให้ชิ้นที่คะแนนการค้นสูงกว่าเป็นตัวแทนของรายการชุดเดียวกัน
            if len(hits) > len(best_hits) or (
                    hits and len(hits) == len(best_hits) and best is not None
                    and c.score > best.score):
                best, best_hits = c, hits
        if best is None or not best_hits:
            break
        left -= best_hits
        picked.append(Support(
            chunk_id=best.chunk_id,
            course_id=best.course_id,
            course_title=best.course_title,
            page_number=best.page_number,
            # สัดส่วนของ "รายการ" ที่ชิ้นนี้ครอบได้ (ไม่ใช่คะแนนการค้น)
            coverage=round(len(best_hits) / len(items), 4),
        ))
    return tuple(picked)


def supporting(reply: str, chunks: Sequence[Chunk], question: str = "",
               items: Sequence[str] = ()) -> tuple[Support, ...]:
    """
    คืนชิ้นที่รองรับคำตอบ เรียงตามลำดับที่เลือกได้ · คืน () เมื่อไม่มีชิ้นใดถึงเกณฑ์

    ไม่เลือกตามคะแนนการค้นโดยเจตนา — เลือกจากข้อความที่รองรับคำตอบจริง

    ตัด "กรอบของคำตอบ" ออกก่อนวัด: ข้อความจากคำถามเอง และชื่อหลักสูตรที่คำตอบ
    ยกขึ้นนำ ไม่ใช่หลักฐานของข้ออ้าง · วัดกับคำตอบจริงเมื่อ 14 ต.ค. 2569 พบว่าคำตอบ
    "หลักสูตรคณิตศาสตร์ 2564 มีแคลคูลัส 1-4" มีชื่อหลักสูตรไทย-อังกริษเป็น 56% ของ
    คำตอบ หน้าผนวกท้ายเล่มที่ทวนชื่อหลักสูตรจึงเอาชนะหน้าที่มีรายชื่อแคลคูลัสครบสี่วิชา
    """
    body = answer_body(reply)
    want = _grams(body)
    if not want or not chunks:
        return ()
    # คำตอบที่ไล่รายการ: เลือกจากรายการตรง ๆ ก่อน (ดูเหตุผลใน list_items) แล้วจึงเติมหน้าที่
    # เส้นทางกรามเลือกได้ เพราะคำตอบหนึ่งมีทั้งส่วนที่เป็นรายการและส่วนที่เป็นความเรียง
    # (คำตอบเปรียบเทียบสองหลักสูตรมีรายการของฝั่งหนึ่ง และความเรียงของอีกฝั่ง)
    by_items: tuple[Support, ...] = ()
    measured = body
    if len(items) >= MIN_ITEMS:
        by_items = _supporting_by_items(items, chunks)
        # ส่วนที่เป็นรายการมีหน้ารองรับจากขั้นบนแล้ว · เส้นทางกรามจึงวัดเฉพาะ "ส่วนที่ไม่ใช่
        # รายการ" เพื่อไม่ให้เติมหน้าที่ซ้ำซ้อนกับรายการ แต่ยังได้หน้าของส่วนที่เป็นความเรียง
        # (คำตอบเปรียบเทียบที่ฝั่งหนึ่งเป็นรายการ อีกฝั่งเป็นความเรียง ต้องได้ที่มาทั้งสองฝั่ง)
        if by_items:
            measured = _split_items(body)[1] or body
    # กรอบที่ไม่ใช่สาระ: คำถามเอง ชื่อหลักสูตรทุกชื่อที่ปรากฏในผลการค้น และชื่อภาษาอังกฤษ
    # ในวงเล็บที่คำตอบใส่กำกับไว้ · ตัดออกจากข้อความก่อนตัดกราม เพื่อไม่ให้กรามที่คาบ
    # รอยต่อของกรอบรอดมาเป็นคะแนนของหน้าที่ทวนแต่ชื่อเล่ม (ดู _masked_grams)
    # ข้อความไทยของสาระยังอยู่ในชุดที่ใช้วัด จึงไม่เสียความสามารถในการจับหลักฐาน
    frames = [question, *(c.course_title or "" for c in chunks),
              *_PAREN_LATIN.findall(body)]
    want = _masked_grams(measured, frames)
    if not want:
        # ตัดกรอบแล้วไม่มีสาระเหลือให้หาหลักฐาน — เช่นประโยคนำที่มีแต่ชื่อหลักสูตรกับคำเกริ่น
        # ("หลักสูตร… พ.ศ. 2566 มีโครงสร้างหลักสูตรประกอบด้วย 3 หมวดวิชาหลัก ดังนี้ครับ:")
        # ส่วนที่เป็นรายการมีหน้ารองรับจากขั้นบนแล้ว และถ้าไม่มีรายการก็ไม่มีข้ออ้างให้ยืนยัน
        # จึงไม่เดาหน้าให้ · เดิมมีทางถอยไปใช้กรามที่ยังมีกรอบอยู่ ซึ่งพาหน้าที่ทวนแต่ชื่อเล่ม
        # กลับเข้ามาเป็นที่มา (it66.pdf หน้า 137 เมื่อ 15 ต.ค. 2569)
        return tuple(by_items)
    pools = [(c, _grams(c.content)) for c in chunks]
    # ตัดข้อความประจำเล่มออกก่อนวัด เหลือเฉพาะส่วนที่เป็นสาระของคำตอบนี้
    df = Counter()
    for _, pool in pools:
        df.update(want & pool)
    cap = max(1, int(len(pools) * COMMON_SHARE))
    distinctive = {g for g in want if df[g] <= cap}
    if distinctive:
        want = distinctive
    # เริ่มจากหน้าที่รายการเลือกไว้ แล้วให้เส้นทางกรามเติมได้เฉพาะหน้าที่เพิ่มความครอบคลุม
    # เกินกว่าที่หน้าเหล่านั้นครอบอยู่แล้ว — คำตอบที่เป็นรายการล้วนจึงไม่ได้หน้าซ้ำซ้อนมาเพิ่ม
    # ส่วนคำตอบที่มีทั้งรายการและความเรียง (เช่นเปรียบเทียบสองหลักสูตร) ยังได้หน้าของอีกฝั่ง
    picked: list[Support] = list(by_items)
    covered: set[str] = set()
    for c, pool in ([(c, _grams(c.content)) for c in chunks] if by_items else []):
        if any(p.chunk_id == c.chunk_id for p in picked):
            covered |= want & pool
    while len(picked) < MAX_SOURCES:
        best, best_gain, best_hits = None, 0.0, set()
        for c, pool in pools:
            if any(p.chunk_id == c.chunk_id for p in picked):
                continue
            hits = (want & pool) - covered
            gain = len(hits) / len(want)
            if gain > best_gain:
                best, best_gain, best_hits = c, gain, hits
        if best is None:
            break
        floor = MIN_COVERAGE if not picked else MIN_GAIN
        if best_gain < floor:
            break
        covered |= best_hits
        picked.append(Support(
            chunk_id=best.chunk_id,
            course_id=best.course_id,
            course_title=best.course_title,
            page_number=best.page_number,
            coverage=round(best_gain, 4),
        ))
        if len(covered) / len(want) >= ENOUGH:
            break
    return tuple(picked)


def quote_is_supported(quote: str, evidence: str, *, min_chars: int = 12) -> bool:
    """
    ข้อความที่ยกมาต้องปรากฏในหลักฐานของหลักสูตรนั้นจริง

    ใช้กับขั้นเขียนเหตุผลของคำแนะนำ: อนุญาตให้สรุปความได้ แต่ส่วนที่ยกมาอ้างต้องตรวจได้
    และต้องมาจากหลักฐานของหลักสูตรนั้นเอง ไม่ใช่ของหลักสูตรอื่น
    """
    q = normalise(quote)
    if len(q) < min_chars:
        return False
    return q in normalise(evidence)
