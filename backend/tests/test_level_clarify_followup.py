"""
ถามกำกวม -> ระบบถามระดับ -> ผู้ใช้ตอบระดับ -> ต้องตอบจากเล่มที่ถูกระดับ

    docker exec -w /app/backend -e PYTHONPATH=/app/backend <c> python tests/test_level_clarify_followup.py

ที่มา — ตรวจพบ 2569-10-27
------------------------
คลังนี้มีสาขาที่ชื่อและปีเดียวกันแต่คนละระดับปริญญา เดิมเมื่อผู้ใช้ถามโดยไม่บอกระดับ
ระบบตรวจเจอความกำกวม (structured_intent คืนเหตุผล multiple_degree_levels) แล้ว
**ตกไปเส้นทางเอกสารโดยไม่บอกผู้ใช้** ซึ่งค้นจากทั้งสองเล่ม คำตอบจึงอาจเอาตัวเลข
ของสองระดับมาปนกัน (โท 36 หน่วยกิต / เอก 48 หน่วยกิต) หรือหยิบเล่มเดียวมาตอบ
โดยไม่บอกว่าระดับไหน

เพิ่มด่าน ambiguous_degree_level + ด่าน 0.7155 ใน chat.py ให้ถามกลับแทน

สิ่งที่ทดสอบ
------------
1. เทิร์นแรกที่ไม่ระบุระดับ -> ถามระดับกลับ และยังไม่ตอบตัวเลขของเล่มใด
2. เทิร์นถัดมาผู้ใช้ตอบระดับ -> ต่อบริบทได้ ไม่ถามซ้ำ
3. เอกสารที่ดึงมาใช้ต้องเป็นของระดับที่ตอบเท่านั้น ไม่มีอีกระดับปน

วัดที่เอกสารที่ถูกดึงมา (retrieved/citations) ซึ่งเป็นผลของขั้นที่ไม่มีโมเดลเกี่ยว
ผลจึงคงที่ · ถ้อยคำของคำตอบสุดท้ายเป็นของโมเดล ไม่ได้วัดในไฟล์นี้

เลียนแบบสิ่งที่หน้าเว็บทำจริง คือส่งบทสนทนาทั้งก้อนมาทุกครั้งผ่าน prior
"""
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import text as _sql

from app.db.session import SessionLocal
# ต้องนำเข้าโมเดลให้ครบก่อน ไม่งั้น SQLAlchemy ผูก foreign key ของ chat_sessions
# กับตาราง users ไม่ได้ (ชุดทดสอบนำเข้าเฉพาะโมดูลที่ใช้ จึงไม่ได้ลงทะเบียนให้เอง)
from app.models.chat import ChatSession  # noqa: F401
from app.models.course import Course  # noqa: F401
from app.models.user import User  # noqa: F401
from app.services.chat import PriorTurn, prepare_answer
from app.services.course_scope import ambiguous_degree_level

AGRI = "การจัดการเทคโนโลยีการเกษตรและบริหารทรัพยากรชุมชน"

# (คำตอบของผู้ใช้, ชื่อปริญญาที่ต้องพบในเล่มที่ใช้, ชื่อปริญญาที่ต้องไม่พบ)
REPLIES = [
    ("ปริญญาโท", "วิทยาศาสตรมหาบัณฑิต", "ปรัชญาดุษฎีบัณฑิต"),
    ("ปริญญาเอก", "ปรัชญาดุษฎีบัณฑิต", "วิทยาศาสตรมหาบัณฑิต"),
    ("เอาปริญญาโทครับ", "วิทยาศาสตรมหาบัณฑิต", "ปรัชญาดุษฎีบัณฑิต"),
]

CHECKS = 0
FAILURES: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    if ok:
        print(f"  [ผ่าน] {label}" + (f" — {detail}" if detail else ""))
    else:
        FAILURES.append(f"{label} — {detail}")
        print(f"  [ตก]  {label} — {detail}")


def answer_text(res) -> str:
    return (getattr(res, "canned", None) or "") or ""


def used_titles(res) -> list[str]:
    """ชื่อหลักสูตรของชิ้นข้อมูลที่ขั้นนี้ดึงมาใช้ — หลักฐานว่าใช้เล่มไหน"""
    names = set()
    for item in list(getattr(res, "retrieved", ()) or ()):
        t = getattr(item, "course_title", None)
        if isinstance(t, str) and t:
            names.add(t)
    for c in list(getattr(res, "citations", []) or []):
        t = getattr(c, "course_title", None)
        if isinstance(t, str) and t:
            names.add(t)
    return sorted(names)


def main() -> int:
    with SessionLocal() as db:
        if ambiguous_degree_level(db, AGRI + " เรียนกี่หน่วยกิต") is None:
            print("** ข้ามการทดสอบ: คลังนี้ไม่มีสาขาที่เปิดหลายระดับปริญญา **")
            return 0

        uid = db.execute(_sql("select id from public.users limit 1")).scalar()
        if uid is None:
            print("** ข้ามการทดสอบ: ไม่มีผู้ใช้ในฐานข้อมูล **")
            return 0

        q1 = AGRI + " เรียนกี่หน่วยกิต"
        print("1. เทิร์นแรก — ถามโดยไม่ระบุระดับ")
        r1 = prepare_answer(db, uid, None, q1)
        a1 = answer_text(r1)
        check("ถามระดับกลับ", "ระบุระดับที่ต้องการ" in a1, a1[:70])
        check("ยังไม่ตอบตัวเลขหน่วยกิตของเล่มใด", "36" not in a1 and "48" not in a1)
        check("เอ่ยทั้งสองระดับให้ผู้ใช้เลือก",
              "ปริญญาโท" in a1 and "ปริญญาเอก" in a1)

        for reply, want_degree, other_degree in REPLIES:
            print()
            print("2. เทิร์นถัดมา — ผู้ใช้ตอบว่า %r" % reply)
            prior = [PriorTurn(role="user", content=q1),
                     PriorTurn(role="assistant", content=a1)]
            r2 = prepare_answer(db, uid, None, reply, prior)
            a2 = answer_text(r2)
            titles = used_titles(r2)
            joined = " ".join(titles)

            check("ไม่ถามระดับซ้ำ", "ระบุระดับที่ต้องการ" not in a2, a2[:70])
            check("ต่อบริบทจากเทิร์นก่อนได้", bool(getattr(r2, "has_history", False)))
            check("คำถามที่ตีความมีทั้งชื่อสาขาและระดับ",
                  AGRI in (getattr(r2, "interpreted", "") or "")
                  and "ระดับ" in (getattr(r2, "interpreted", "") or ""),
                  getattr(r2, "interpreted", "") or "(ไม่มี)")
            # ยืนยัน "ผล" ไม่ใช่ "เส้นทาง" — คำถามบางข้อตอบจากฐานข้อมูลโดยตรง
            # จึงไม่มีชิ้นเอกสารให้นับ หลักฐานว่าใช้เล่มระดับไหนอยู่ในข้อความคำตอบแทน
            # (เดิมบังคับว่าต้องมีชิ้นเอกสาร ซึ่งทำให้ตกทันทีที่คำตอบมาจากฐานข้อมูล)
            evidence = (a2 + " " + joined).strip()
            check("มีหลักฐานว่าใช้เล่มไหน", bool(evidence), evidence[:60] or "(ไม่มี)")
            check("อ้างถึงเล่มของระดับที่ตอบ (%s)" % want_degree,
                  want_degree in evidence, evidence[:120] or "(ไม่มี)")
            check("ไม่อ้างถึงเล่มของอีกระดับ (%s)" % other_degree,
                  other_degree not in evidence, evidence[:120] or "(ไม่มี)")

    print()
    print("=" * 70)
    if FAILURES:
        print("ตก %d จาก %d ข้อ" % (len(FAILURES), CHECKS))
        for f in FAILURES:
            print("   - %s" % f)
        return 1
    print("ผ่านทั้ง %d ข้อ" % CHECKS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
