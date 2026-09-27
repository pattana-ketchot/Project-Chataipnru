"""
คลังเอกสารที่ระบบมีอยู่แล้ว และการจับคู่ PDF บนเว็บเข้ากับหลักสูตรในฐานข้อมูล

แหล่งข้อมูล
-----------
อ่านจากไฟล์ TSV ที่ส่งออกมาจากฐานข้อมูลแบบอ่านอย่างเดียว ไม่ต่อฐานข้อมูลโดยตรง
เพื่อให้เครื่องมือนี้รันที่ไหนก็ได้โดยไม่ต้องเปิดพอร์ต DB ออกนอกเซิร์ฟเวอร์
และเพื่อให้ชัดเจนว่า Phase 1 ไม่แตะฐานข้อมูล production เลย

รูปแบบ TSV (มีหัวตาราง):
    file_sha256  original_filename  page_count  course_code  course_title

การจับคู่ทำอย่างไร
------------------
ชื่อไฟล์ PDF บนเว็บเป็นค่าแฮช จับคู่จากชื่อไฟล์ไม่ได้ ตัวที่ใช้ได้คือหัวเรื่องของ
หน้าที่พบลิงก์ เทียบกับ courses.title ในฐานข้อมูล

ชื่อหลักสูตรสองฝั่งเขียนคนละแบบ เว็บเขียน "(ปริญญาเอก) การจัดการเทคโนโลยีการเกษตร…"
ฐานข้อมูลเขียน "หลักสูตรปรัชญาดุษฎีบัณฑิต สาขาวิชาการจัดการเทคโนโลยีการเกษตร…"
จึงตัดคำนำหน้าที่ไม่ใช่สาระออกก่อนเทียบ แล้ววัดด้วยสัดส่วนคำที่ซ้อนกัน

ตั้งใจให้ "ไม่รู้" มากกว่าจะ "เดา"
----------------------------------
ถ้าคะแนนไม่ถึงเกณฑ์จะรายงานว่าระบุหลักสูตรไม่ได้ ดีกว่าจับคู่ผิดแล้วคนอ่านรายงาน
เชื่อตามนั้น เพราะรายงานนี้จะถูกใช้ตัดสินใจว่าจะนำเอกสารเล่มไหนเข้าคลังความรู้
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

# ภาษาไทยไม่เว้นวรรคระหว่างคำ การแยกคำด้วยช่องว่างจึงใช้ไม่ได้
# ตัวอย่างที่พิสูจน์แล้ว — เทียบสองชื่อนี้ด้วยการแยกคำได้คะแนน 0.0 ทั้งที่เป็นหลักสูตรเดียวกัน
#   เว็บ:        "(ปริญญาเอก) การจัดการเทคโนโลยีการเกษตรและบริหารทรัพยากรชุมชน"
#   ฐานข้อมูล:  "หลักสูตรปรัชญาดุษฎีบัณฑิต สาขาวิชาการจัดการเทคโนโลยีการเกษตรและบริหารทรัพยากรชุมชน (พ.ศ. 2568)"
# เพราะ "การจัดการ…" กับ "สาขาวิชาการจัดการ…" เป็นคนละสตริง ไม่มีคำซ้อนกันเลย
#
# จึงเปลี่ยนมาตัดคำนำหน้าที่ไม่ใช่สาระออก แล้วเทียบที่ระดับตัวอักษรแทน
_YEAR = re.compile(r"\(?\s*(?:พ\.?ศ\.?)?\s*25\d\d\s*\)?")
_NOISE = re.compile(
    r"หลักสูตร|สาขาวิชา|สาขา|"
    r"วิทยาศาสตรมหาบัณฑิต|วิทยาศาสตรบัณฑิต|ศิลปศาสตรบัณฑิต|"
    r"ปรัชญาดุษฎีบัณฑิต|สาธารณสุขศาสตรบัณฑิต|"
    r"\(\s*ปริญญา(?:ตรี|โท|เอก)\s*\)"
)
_PUNCT = re.compile(r"[()\[\]{}·.,\-/\s]+")

# ระดับปริญญาต้องแยกให้ออก เพราะมีหลักสูตรชื่อเดียวกันทั้ง ป.โท และ ป.เอก
# ปี 2568 ถ้าตัดคำระบุระดับทิ้งหมด สองหลักสูตรนี้จะเหลือชื่อเหมือนกันเป๊ะ
_LEVEL_PATTERNS = [
    ("เอก", re.compile(r"ปริญญาเอก|ดุษฎีบัณฑิต")),
    ("โท", re.compile(r"ปริญญาโท|มหาบัณฑิต")),
]


def _degree_level(title: str) -> str:
    for level, pat in _LEVEL_PATTERNS:
        if pat.search(title):
            return level
    return "ตรี"


@dataclass
class KnownDocument:
    sha256: str
    filename: str
    page_count: int | None
    course_code: str
    course_title: str


@dataclass
class MatchResult:
    course_code: str | None
    course_title: str | None
    score: float
    confidence: str                      # "สูง" | "ปานกลาง" | "กำกวม" | "ระบุไม่ได้"
    # ชื่อหลักสูตรทุกตัวที่ได้คะแนนเท่ากัน — มากกว่าหนึ่งแปลว่าเลือกเองไม่ได้
    candidates: list[str] = field(default_factory=list)


def load_inventory(path: str | Path) -> list[KnownDocument]:
    rows: list[KnownDocument] = []
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            pc = (r.get("page_count") or "").strip()
            rows.append(KnownDocument(
                sha256=(r.get("file_sha256") or "").strip().lower(),
                filename=(r.get("original_filename") or "").strip(),
                page_count=int(pc) if pc.isdigit() else None,
                course_code=(r.get("course_code") or "").strip(),
                course_title=(r.get("course_title") or "").strip(),
            ))
    return rows


def _normalize(title: str) -> str:
    """เหลือแต่สาระของชื่อสาขา ตัดคำนำหน้า ปีที่ปรับปรุง เครื่องหมาย และช่องว่างออก"""
    s = _YEAR.sub("", title)
    s = _NOISE.sub("", s)
    return _PUNCT.sub("", s)


def _similarity(a: str, b: str) -> float:
    """
    เทียบที่ระดับตัวอักษร ไม่ใช่ระดับคำ

    ถ้าฝั่งหนึ่งเป็นสตริงย่อยของอีกฝั่งให้เต็ม 1.0 เพราะชื่อบนเว็บมักเป็นส่วนหนึ่ง
    ของชื่อเต็มในฐานข้อมูลอยู่แล้ว เช่น "คณิตศาสตร์" อยู่ใน "คณิตศาสตร์" ที่ตัด
    คำนำหน้าแล้ว นอกนั้นใช้สัดส่วนตัวอักษรที่ตรงกัน
    """
    if not a or not b:
        return 0.0
    if a in b or b in a:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def match_course(page_title: str, known: list[KnownDocument]) -> MatchResult:
    """
    หาหลักสูตรที่ใกล้ที่สุดกับหัวเรื่องของหน้าเว็บ

    เทียบสองชั้น — ระดับปริญญาต้องตรงกันก่อน แล้วค่อยวัดความคล้ายของชื่อสาขา
    ถ้าไม่บังคับระดับปริญญา หลักสูตรการจัดการเทคโนโลยีการเกษตรฯ ซึ่งมีทั้ง ป.โท
    และ ป.เอก ปี 2568 เหมือนกัน จะจับคู่สลับกันได้
    """
    web_norm = _normalize(page_title)
    web_level = _degree_level(page_title)
    if not web_norm:
        return MatchResult(None, None, 0.0, "ระบุไม่ได้")

    # รวมชื่อหลักสูตรที่ซ้ำกัน (คนละปีปรับปรุง) ให้เทียบทีละชื่อไม่ซ้ำ
    by_title: dict[str, KnownDocument] = {}
    for k in known:
        if k.course_title:
            by_title.setdefault(k.course_title, k)

    scored: list[tuple[float, KnownDocument]] = []
    for title, doc in by_title.items():
        if _degree_level(title) != web_level:
            continue
        scored.append((_similarity(web_norm, _normalize(title)), doc))

    if not scored:
        return MatchResult(None, None, 0.0, "ระบุไม่ได้")

    scored.sort(key=lambda x: -x[0])
    best_score = scored[0][0]
    if best_score < 0.55:
        return MatchResult(None, None, round(best_score, 2), "ระบุไม่ได้")

    # ชื่อหลักสูตรเดียวกันคนละปีปรับปรุงจะได้คะแนนเท่ากันเป๊ะ เลือกเองไม่ได้
    # ต้องบอกว่ากำกวม ไม่ใช่หยิบตัวแรกมาแล้วทำเป็นว่ามั่นใจ
    tied = [d for s, d in scored if abs(s - best_score) < 1e-9]
    best = tied[0]
    if len(tied) > 1:
        return MatchResult(
            best.course_code, best.course_title, round(best_score, 2), "กำกวม",
            candidates=[d.course_title for d in tied],
        )
    confidence = "สูง" if best_score >= 0.85 else "ปานกลาง"
    return MatchResult(best.course_code, best.course_title, round(best_score, 2), confidence,
                       candidates=[best.course_title])
