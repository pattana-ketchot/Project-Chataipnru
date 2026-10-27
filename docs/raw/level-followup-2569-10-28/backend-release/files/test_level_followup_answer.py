"""
ตอบคำถามที่ระบบถามระดับกลับ แล้วต้องได้ **คำตอบปลายทาง** ที่ถูกต้อง

    docker exec -w /app/backend -e PYTHONPATH=/app/backend <c> python tests/test_level_followup_answer.py

ที่มา — ตรวจพบตอนตรวจรับ deploy 27 ต.ค. 2569
------------------------------------------
ด่านถามระดับทำงานถูก และเลือกเล่มถูกระดับแล้ว แต่คำตอบที่ผู้ใช้ได้คือ
"ไม่พบข้อมูลจำนวนหน่วยกิต" ทั้งที่ตัวเลขอยู่ในเล่มที่เลือกมาถูก

สาเหตุ: เมื่อผู้ใช้ตอบสั้น ๆ ว่า "ปริญญาโท" ขั้นเขียนคำถามใหม่ด้วยโมเดลคืน
"หลักสูตร<ชื่อ> ระดับปริญญาโท" — เก็บชื่อกับระดับไว้ แต่ **ทิ้งเรื่องที่ถาม**
เส้นทางตอบจากฐานข้อมูลจึงไม่ทำงาน และการค้นเอกสารค้นด้วยคำที่ไม่มีหัวข้อที่ถาม

แก้โดยให้ swap_follow_up ประกอบคำถามใหม่ด้วยโค้ด เมื่อข้อความของผู้ใช้พูดแค่ระดับปริญญา

สิ่งที่ทดสอบ
------------
1. คำถามที่ประกอบใหม่ เก็บทั้งชื่อหลักสูตรและหัวข้อเดิม — ทดสอบหลายหัวข้อ
   เพื่อยืนยันว่าไม่ได้แก้เฉพาะคำว่า "หน่วยกิต"
2. **คำตอบปลายทาง** ของคำถามหน่วยกิต ต้องมีตัวเลขของระดับที่ตอบ และไม่มีของอีกระดับ
   (เส้นทางนี้ตอบจากฐานข้อมูล ไม่เรียกโมเดล ผลจึงคงที่)
3. หัวข้ออื่น — ตรวจว่าเอกสารที่ดึงมาเป็นของระดับที่ตอบ และคำถามที่ตีความเก็บหัวข้อไว้
   (ถ้อยคำของคำตอบมาจากโมเดล จึงไม่ยืนยันถ้อยคำ)
4. ผู้ใช้เปลี่ยนเรื่อง ต้องไม่ถูกดึงกลับไปคำถามเดิม
"""
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import text as _sql

# ต้องนำเข้าโมเดลให้ครบก่อน ไม่งั้น SQLAlchemy ผูก foreign key ของ chat_sessions
# กับตาราง users ไม่ได้ (ชุดทดสอบนำเข้าเฉพาะโมดูลที่ใช้ จึงไม่ได้ลงทะเบียนให้เอง)
from app.db.session import SessionLocal
from app.models.chat import ChatSession  # noqa: F401
from app.models.course import Course  # noqa: F401
from app.models.user import User  # noqa: F401
from app.services.chat import PriorTurn, prepare_answer
from app.services.course_scope import ambiguous_degree_level
from app.services.follow_up import swap_follow_up

AGRI = "การจัดการเทคโนโลยีการเกษตรและบริหารทรัพยากรชุมชน"

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


def used_titles(res) -> str:
    names = set()
    for item in list(getattr(res, "retrieved", ()) or ()):
        t = getattr(item, "course_title", None)
        if isinstance(t, str) and t:
            names.add(t)
    for c in list(getattr(res, "citations", []) or []):
        t = getattr(c, "course_title", None)
        if isinstance(t, str) and t:
            names.add(t)
    return " ".join(sorted(names))


class _Turn:
    """ข้อความในประวัติ — รูปเดียวกับที่ swap_follow_up รับ"""

    def __init__(self, role: str, content: str) -> None:
        self.role = role
        self.content = content


# (ชื่อเคส, คำถามแรก, คำตอบของผู้ใช้, คำที่หัวข้อเดิมต้องยังอยู่, ชื่อปริญญาที่ต้องใช้, ที่ต้องไม่ใช้)
TOPICS = [
    ("หน่วยกิต -> ปริญญาโท", AGRI + " เรียนกี่หน่วยกิต", "ปริญญาโท",
     "หน่วยกิต", "วิทยาศาสตรมหาบัณฑิต", "ปรัชญาดุษฎีบัณฑิต"),
    ("หน่วยกิต -> ปริญญาเอก", AGRI + " เรียนกี่หน่วยกิต", "ปริญญาเอก",
     "หน่วยกิต", "ปรัชญาดุษฎีบัณฑิต", "วิทยาศาสตรมหาบัณฑิต"),
    ("รายวิชา -> ปริญญาโท", AGRI + " มีวิชาอะไรบ้าง", "ปริญญาโท",
     "วิชา", "วิทยาศาสตรมหาบัณฑิต", "ปรัชญาดุษฎีบัณฑิต"),
    ("คุณสมบัติ -> ปริญญาเอก", AGRI + " รับคนจบอะไร", "ปริญญาเอก",
     "รับคนจบ", "ปรัชญาดุษฎีบัณฑิต", "วิทยาศาสตรมหาบัณฑิต"),
]

# ข้อความที่เป็นการเปลี่ยนเรื่อง ต้องไม่ถูกประกอบกลับเป็นคำถามเดิม
TOPIC_CHANGES = [
    "คณะนี้มีกี่หลักสูตร",
    "ปริญญาโท ค่าเทอมเท่าไร",
    "อยากเรียนสายคอมต้องเรียนอะไร",
]

# คำตอบปลายทางที่ยืนยันได้แน่นอน เพราะมาจากฐานข้อมูล ไม่ผ่านโมเดล
CREDITS = {"ปริญญาโท": ("36", "48"), "ปริญญาเอก": ("48", "36")}


def main() -> int:
    with SessionLocal() as db:
        if ambiguous_degree_level(db, AGRI + " เรียนกี่หน่วยกิต") is None:
            print("** ข้ามการทดสอบ: คลังนี้ไม่มีสาขาที่เปิดหลายระดับปริญญา **")
            return 0
        uid = db.execute(_sql("select id from public.users limit 1")).scalar()
        if uid is None:
            print("** ข้ามการทดสอบ: ไม่มีผู้ใช้ในฐานข้อมูล **")
            return 0

        print("1. คำถามที่ประกอบใหม่ เก็บทั้งชื่อหลักสูตรและหัวข้อเดิม")
        for label, q1, reply, topic, _want, _other in TOPICS:
            ask = answer_text(prepare_answer(db, uid, None, q1))
            history = [_Turn("user", q1), _Turn("assistant", ask)]
            rebuilt = swap_follow_up(db, history, reply, AGRI)
            ok = rebuilt is not None and AGRI in rebuilt and topic in rebuilt and reply in rebuilt
            check(label, ok, rebuilt or "(ไม่ประกอบ)")

        print()
        print("2. คำตอบปลายทางของคำถามหน่วยกิต (ตอบจากฐานข้อมูล ไม่เรียกโมเดล)")
        for label, q1, reply, _topic, want_degree, other_degree in TOPICS[:2]:
            ask = answer_text(prepare_answer(db, uid, None, q1))
            prior = [PriorTurn(role="user", content=q1),
                     PriorTurn(role="assistant", content=ask)]
            res = prepare_answer(db, uid, None, reply, prior)
            got = answer_text(res)
            want_n, other_n = CREDITS[reply]
            check(f"{label} — ตอบเป็นข้อความสำเร็จรูปจากฐานข้อมูล", bool(got), got[:60])
            check(f"{label} — มีตัวเลข {want_n} หน่วยกิต", want_n in got, got[:150])
            check(f"{label} — ไม่มีตัวเลข {other_n} ของอีกระดับ", other_n not in got, got[:150])
            check(f"{label} — อ้างชื่อปริญญาถูกระดับ", want_degree in got, got[:100])
            check(f"{label} — ไม่อ้างอีกระดับ", other_degree not in got, got[:100])
            check(f"{label} — ไม่ถามระดับซ้ำ", "ระบุระดับที่ต้องการ" not in got)

        print()
        print("3. หัวข้ออื่น — เอกสารที่ดึงมาต้องเป็นของระดับที่ตอบ")
        for label, q1, reply, topic, want_degree, other_degree in TOPICS[2:]:
            ask = answer_text(prepare_answer(db, uid, None, q1))
            prior = [PriorTurn(role="user", content=q1),
                     PriorTurn(role="assistant", content=ask)]
            res = prepare_answer(db, uid, None, reply, prior)
            interpreted = getattr(res, "interpreted", "") or ""
            # หัวข้อบางอย่างตอบจากฐานข้อมูลโดยตรง จึงไม่มีชิ้นเอกสารให้นับ
            # หลักฐานว่าใช้เล่มระดับไหนจึงอยู่ในข้อความคำตอบแทน — ดูทั้งสองทาง
            evidence = (answer_text(res) + " " + used_titles(res)).strip()
            check(f"{label} — คำถามที่ตีความเก็บหัวข้อเดิมไว้", topic in interpreted, interpreted)
            check(f"{label} — อ้างถึงเล่ม {want_degree}", want_degree in evidence, evidence[:120] or "(ไม่มี)")
            check(f"{label} — ไม่อ้างถึง {other_degree}", other_degree not in evidence, evidence[:120] or "(ไม่มี)")

        print()
        print("4. ผู้ใช้เปลี่ยนเรื่อง ต้องไม่ถูกดึงกลับไปคำถามเดิม")
        q1 = AGRI + " เรียนกี่หน่วยกิต"
        ask = answer_text(prepare_answer(db, uid, None, q1))
        history = [_Turn("user", q1), _Turn("assistant", ask)]
        for msg in TOPIC_CHANGES:
            rebuilt = swap_follow_up(db, history, msg, AGRI)
            check(f"ไม่ประกอบคำถามเดิมกลับมา: {msg!r}", rebuilt is None, rebuilt or "")

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
