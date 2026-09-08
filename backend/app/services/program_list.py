"""
ตอบคำถาม "คณะเปิดสอนสาขาอะไรบ้าง" จากรายการหลักสูตรในฐานข้อมูลโดยตรง

ทำไมต้องแยกออกมาไม่ให้ไปทางค้นเอกสาร
------------------------------------
คำตอบของคำถามนี้ไม่ได้อยู่ในเอกสารเล่มใดเล่มหนึ่ง เพราะ มคอ.2 แต่ละเล่มพูดถึงหลักสูตร
ของตัวเองเท่านั้น ไม่มีเล่มไหนแจกแจงว่าคณะมีหลักสูตรอะไรบ้าง การค้นด้วยความใกล้เคียง
จึงได้เนื้อหาของสาขาใดสาขาหนึ่งมา แล้วด่านตรวจก็ตัดสินว่าตอบไม่ได้ ผู้ใช้จึงได้คำตอบว่า
"ไม่พบข้อมูล" กับคำถามที่พื้นฐานที่สุดของทั้งระบบ

รายการหลักสูตรเป็นสิ่งที่ระบบรู้แน่นอนอยู่แล้ว เพราะเป็นข้อมูลของตัวเอง การตอบจาก
ฐานข้อมูลตรงๆ จึงถูกต้องเสมอ ไม่ต้องเรียกโมเดล และไม่มีทางแต่งข้อมูล

จุดบอดของชุดประเมิน
------------------
ชุดประเมิน 113 คำถามไม่มีคำถามแนวนี้เลยสักข้อ ระบบจึงได้ 112/113 ทั้งที่ตอบคำถามที่
นักเรียนถามเป็นคำถามแรกไม่ได้ — เป็นตัวอย่างว่าคะแนนสูงบอกได้แค่ว่าทำข้อสอบที่มีได้ดี
ไม่ได้บอกว่าข้อสอบครอบคลุมสิ่งที่ผู้ใช้ถามจริง
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.course_scope import _distinctive_name
from app.services.program_names import english_name

_LIST_WORDS = (
    "มีสาขาอะไรบ้าง", "มีหลักสูตรอะไรบ้าง", "เปิดสอนอะไรบ้าง", "เปิดสอนสาขาอะไร",
    "สาขาอะไรบ้าง", "หลักสูตรอะไรบ้าง", "มีสาขาไหนบ้าง", "มีหลักสูตรไหนบ้าง",
    "สาขาทั้งหมด", "หลักสูตรทั้งหมด", "กี่สาขา", "กี่หลักสูตร",
    "รายชื่อสาขา", "รายชื่อหลักสูตร", "สาขาที่เปิดสอน", "หลักสูตรที่เปิดสอน",
    "what programs", "what programmes", "what majors", "which majors",
    "list of programs", "list of majors",
)

# ชื่อปริญญาที่บอกว่าเป็นหลักสูตรระดับบัณฑิตศึกษา ใช้ตัวเดียวกับที่ระบบจับคู่สาขาใช้
_GRADUATE = ("มหาบัณฑิต", "ดุษฎีบัณฑิต")


def asks_for_program_list(text_in: str) -> bool:
    lowered = text_in.lower()
    return any(w in text_in or w in lowered for w in _LIST_WORDS)


def _degree_level(title: str) -> str:
    """ระดับปริญญาที่อ่านจากชื่อหลักสูตร"""
    if "ดุษฎีบัณฑิต" in title:
        return "ปริญญาเอก"
    if "มหาบัณฑิต" in title:
        return "ปริญญาโท"
    return "ปริญญาตรี"


def _newest_editions(rows) -> list[str]:
    """
    เหลือหลักสูตรละหนึ่งรายการ โดยเก็บฉบับปีล่าสุดไว้

    คลังเก็บหลักสูตรเดียวกันไว้หลายปีการศึกษา (เช่น วิทยาการคอมพิวเตอร์ 2561 และ 2566)
    ซึ่งจำเป็นตอนตอบคำถามเจาะจงปี แต่การแจกแจงรายชื่อให้นักเรียนต้องเหลือชื่อละครั้ง
    ไม่งั้นจะดูเหมือนคณะเปิดสาขาซ้ำกันสองรอบ

    รวมระดับปริญญาไว้ในกุญแจด้วย เพราะปริญญาโทกับปริญญาเอกของสาขาเดียวกันใช้ชื่อ
    สาขาวิชาเดียวกัน ถ้ายุบด้วยชื่อสาขาอย่างเดียวจะเหลือรายการเดียวแล้วรายงานว่าคณะมี
    หลักสูตรบัณฑิตศึกษา 1 หลักสูตร ทั้งที่มีสอง
    """
    best: dict[tuple[str, str], str] = {}
    for title in rows:
        key = (_degree_level(title), _distinctive_name(title))
        best[key] = max(best.get(key, ""), title)
    return [best[k] for k in sorted(best, key=lambda k: (k[0], k[1]))]


def program_list_answer(db: Session, thai: bool = True) -> str:
    titles = [r.title for r in db.execute(text("SELECT title FROM courses WHERE is_active")).all()]
    undergrad = _newest_editions([t for t in titles if not any(g in t for g in _GRADUATE)])
    graduate = _newest_editions([t for t in titles if any(g in t for g in _GRADUATE)])
    if not undergrad:
        return ""

    def line(title: str) -> str:
        name = _distinctive_name(title)
        en = english_name(title)
        return f"- {name} ({en})" if en else f"- {name}"

    if thai:
        parts = [
            f"คณะวิทยาศาสตร์และเทคโนโลยี มหาวิทยาลัยราชภัฏพระนคร มีหลักสูตรระดับปริญญาตรี "
            f"{len(undergrad)} สาขา ที่มีเอกสารอยู่ในระบบดังนี้",
            "",
            *[line(t) for t in undergrad],
        ]
        if graduate:
            parts += [
                "",
                f"และมีหลักสูตรระดับบัณฑิตศึกษาอีก {len(graduate)} หลักสูตร",
                # บอกระดับปริญญากำกับไว้ เพราะชื่อสาขาของทั้งสองระดับเหมือนกันทุกตัวอักษร
                *[f"- {_distinctive_name(t)} ({_degree_level(t)})" for t in graduate],
            ]
        parts += [
            "",
            "ถามรายละเอียดของสาขาไหนต่อได้เลยครับ เช่น เรียนกี่หน่วยกิต เรียนอะไรบ้าง "
            "หรือจบแล้วทำงานอะไรได้",
        ]
    else:
        parts = [
            f"The Faculty of Science and Technology, Phranakhon Rajabhat University offers "
            f"{len(undergrad)} bachelor's programmes held in this system:",
            "",
            *[line(t) for t in undergrad],
        ]
        if graduate:
            parts += [
                "",
                f"It also offers {len(graduate)} postgraduate programmes:",
                *[f"- {_distinctive_name(t)} ({_degree_level(t)})" for t in graduate],
            ]
        parts += ["", "Ask about any of them — credits, what you study, or careers after graduation."]

    return "\n".join(parts)
