"""
ยืนยันการแก้ 5 ข้อที่พบจากการตรวจทางตอบเร็ว (14 ต.ค. 2569)

    cd backend && python tests/test_audit_fixes_round2.py

1. ข้อมูลที่เผยแพร่และตรวจแล้วต้องมาก่อนแคช
2. คำถามหลายหัวข้อต้องตอบครบจากฐาน และระบุชัดเมื่อขาดบางหัวข้อ
3. คำถามต่อเนื่องต้องจำหลักสูตร ปี และระดับปริญญา โดยไม่เรียกโมเดล
4. ปีฉบับที่ไม่มีต้องบอกว่า "ยังไม่พบในข้อมูลของระบบ" พร้อมปีที่มี
5. timing log ต้องครอบคำขอที่ล้มระหว่างเตรียมคำตอบ

ยิงผ่าน /chat-web ด้วย TestClient (ปั๊ม generator แบบเดียวกับ uvicorn) โดยปิดแคช
เป็นค่าตั้งต้น และทำให้โมเดลใช้ไม่ได้ เพื่อให้ทุกคำตอบที่ผ่านต้องมาจากข้อมูลจริง
"""
import logging
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from llm.connector import LLMConnectionError  # noqa: E402

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


class DeadModel:
    answer_token_cap = 2048

    def __init__(self) -> None:
        self.calls: list[str] = []

    def _die(self, what: str):
        self.calls.append(what)
        raise LLMConnectionError("จำลองว่าโมเดลใช้ไม่ได้")

    def chat(self, *a, **k):
        return self._die("chat")

    def chat_stream(self, *a, **k):
        return self._die("chat_stream")

    def embed(self, *a, **k):
        return self._die("embed")


class Timing(logging.Handler):
    def __init__(self):
        super().__init__()
        self.lines: list[str] = []

    def emit(self, record):
        try:
            self.lines.append(record.getMessage())
        except Exception:
            pass


LOG = Timing()
logging.getLogger("course_advisor").addHandler(LOG)

from fastapi.testclient import TestClient  # noqa: E402

from app.services import chat as C  # noqa: E402
from app.services import llm_client  # noqa: E402
from app.main import app  # noqa: E402

# แคชปิดเป็นค่าตั้งต้น · ข้อ 1 จะสลับมาใช้แคชปลอมเฉพาะช่วงที่ทดสอบ
CACHE_HIT: dict | None = None
CACHE_ASKED: list[str] = []


def _cache_lookup(db, question, version):
    CACHE_ASKED.append(question)
    return CACHE_HIT


C.cache_lookup = _cache_lookup
C.cache_store = lambda *a, **k: None
DEAD = DeadModel()
llm_client._connector = DEAD

CLIENT = TestClient(app)
SENT: list[float] = []


def ask(message, prior=None):
    while True:  # ด่านจำกัดอัตรายอม 20 คำขอ/นาที/IP
        SENT[:] = [t for t in SENT if time.monotonic() - t < 60.0]
        if len(SENT) < 17:
            break
        time.sleep(60.0 - (time.monotonic() - SENT[0]) + 0.3)
    SENT.append(time.monotonic())
    before = len(DEAD.calls)
    LOG.lines.clear()
    msgs = list(prior or []) + [{"role": "user", "content": message}]
    t0 = time.perf_counter()
    r = CLIENT.post("/chat-web", json={"messages": msgs})
    return r.text.strip(), DEAD.calls[before:], time.perf_counter() - t0


def timing_line():
    return next((ln for ln in LOG.lines if "timing /chat-web" in ln), "")


def _db_state(course_title: str) -> tuple[int, int]:
    """(จำนวนแถวหน่วยกิต, จำนวนแถวอาชีพ) ของหลักสูตรหนึ่งจากชั้นข้อมูลที่เผยแพร่

    ใช้ยืนยันว่า fixture ยังตรงกับสถานะฐานจริง — การเผยแพร่ข้อมูลใหม่ทำให้คำถามที่
    "ฐานตอบไม่ได้" กลายเป็นตอบได้ ชุดทดสอบจึงต้องรู้ตัวและบอกเหตุ ไม่ใช่ตกแบบไม่มีคำอธิบาย
    """
    from sqlalchemy import text as _sql

    from app.db.session import SessionLocal

    with SessionLocal() as db:
        credits = db.execute(_sql(
            "SELECT count(*) FROM mko.v_live_values "
            "WHERE course_title = :t AND field_key = 'total_credits'"), {"t": course_title}).scalar()
        careers = db.execute(_sql(
            "SELECT count(*) FROM mko.v_live_list_items "
            "WHERE course_title = :t AND item_type = 'career'"), {"t": course_title}).scalar()
    return int(credits or 0), int(careers or 0)


# ---------------------------------------------------------------- 1
print("1. ข้อมูลที่เผยแพร่และตรวจแล้วต้องมาก่อนแคช")
CACHE_HIT = {
    "status": "answered",
    "reply": "คำตอบเก่าในแคชซึ่งผิดแล้ว: หลักสูตรนี้เรียน 999 หน่วยกิต",
    "citations": [],
}
got, calls, _t = ask("หลักสูตรวิทยาการคอมพิวเตอร์ พ.ศ. 2561 ต้องเรียนทั้งหมดกี่หน่วยกิต")
check("ตอบจากฐานข้อมูล ไม่ใช่คำตอบเก่าในแคช", "999" not in got, got[:130])
check("ได้ตัวเลขจากฐาน", "130" in got, got[:130])
check("มีที่มาของเอกสาร", "ที่มา:" in got, got[:130])
check("timing log บอกว่าใช้ด่านฐาน ไม่ใช่ cache_hit",
      "structured_fast_early" in timing_line() and "cache_hit" not in timing_line(),
      timing_line()[:150])

# คำถามที่ชั้นข้อมูลที่เผยแพร่ตอบไม่ได้จริง — ชั้นนั้นมีเฉพาะหน่วยกิต ปีฉบับ อาชีพ
# วัตถุประสงค์ คุณสมบัติผู้สมัคร และรายวิชา ไม่มีเรื่องทุนการศึกษาเลย
#
# 14 ต.ค. 2569 — fixture เดิมใช้ "วิชาบังคับของวิทยาการคอมพิวเตอร์ 2566" ซึ่งหลังเผยแพร่
# รายวิชา (ขั้น C) ฐานตอบได้เองแล้ว ด่านแคชจึงไม่ถูกเรียกและข้อนี้ไม่ได้ทดสอบอะไร
# จึงตรวจเพิ่มว่าด่านแคชถูกเรียกจริง ซึ่งเป็นหลักฐานว่าทุกด่านก่อนหน้าตอบไม่ได้
# ถ้าวันหนึ่งมีข้อมูลทุนการศึกษาเข้าฐาน ข้อนี้จะตกที่บรรทัดนี้พร้อมบอกเหตุ ไม่ผ่านเงียบ ๆ
CACHE_ASKED.clear()
got, calls, _t = ask("หลักสูตรวิทยาการคอมพิวเตอร์ พ.ศ. 2566 มีทุนการศึกษาอะไรบ้าง")
check("คำถามนี้ฐานตอบไม่ได้จริง — ไหลมาถึงด่านแคช", bool(CACHE_ASKED),
      f"ด่านแคชถูกเรียก {len(CACHE_ASKED)} ครั้ง · ได้: {got[:90]}")
check("คำถามที่ฐานตอบไม่ได้ ยังใช้แคชได้ตามเดิม", "999" in got, got[:130])
check("และไม่เรียกโมเดลเพราะใช้แคช", calls == [], f"เรียก {calls}")
CACHE_HIT = None

# ---------------------------------------------------------------- 2
print()
print("2. คำถามหลายหัวข้อต้องตอบครบจากฐาน")
got, calls, took = ask("หลักสูตรวิทยาการคอมพิวเตอร์ พ.ศ. 2566 เรียนกี่หน่วยกิต และจบไปทำงานอะไรได้บ้าง")
check("มีจำนวนหน่วยกิต", "130" in got, got[:120])
check("มีคำว่าไม่น้อยกว่า", "ไม่น้อยกว่า" in got, got[:120])
check("มีรายการอาชีพ", "อาชีพ" in got, got[:200])
check("อ้างที่มาของทั้งสองส่วน", got.count("ที่มา:") >= 2, f"พบ {got.count('ที่มา:')} ครั้ง")
check("ไม่เรียกโมเดล", calls == [], f"เรียก {calls}")
check("ตอบเร็วกว่า 5 วินาที", took <= 5.0, f"{took:.2f}s")

# สาขาที่ฐานมีหน่วยกิตแต่ยังไม่มีอาชีพที่ผ่านการตรวจ — ยืนยันสถานะนี้จากฐานก่อนถาม
# ไม่ใช่เชื่อว่ายังเป็นอย่างเดิม · fixture เดิมใช้คณิตศาสตร์ 2564 ซึ่งขั้น C เผยแพร่อาชีพ
# ไปแล้ว 5 ข้อ ข้อนี้จึงตกเพราะข้อมูลเปลี่ยน ไม่ใช่เพราะโค้ดพัง
NO_CAREER = "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาเทคโนโลยีสารสนเทศ (พ.ศ. 2561)"
HAS_CREDITS, HAS_CAREERS = _db_state(NO_CAREER)
check(f"fixture ถูกต้อง: {NO_CAREER[-9:]} มีหน่วยกิตในฐาน", HAS_CREDITS > 0,
      f"แถวหน่วยกิต {HAS_CREDITS}")
check("fixture ถูกต้อง: สาขานี้ยังไม่มีอาชีพที่ผ่านการตรวจในฐาน", HAS_CAREERS == 0,
      f"แถวอาชีพ {HAS_CAREERS} — ถ้าเผยแพร่อาชีพของสาขานี้แล้ว ต้องเปลี่ยน fixture ไม่ใช่เปลี่ยนผลที่คาด")
got, calls, _t = ask("หลักสูตรเทคโนโลยีสารสนเทศ พ.ศ. 2561 เรียนกี่หน่วยกิต และจบไปทำงานอะไรได้บ้าง")
check("ตอบส่วนที่มีข้อมูล (หน่วยกิต)", "127" in got, got[:140])
check("บอกชัดว่าส่วนอาชีพยังไม่มีข้อมูล",
      "ยังไม่พบข้อมูล" in got and "อาชีพ" in got, got[-220:])
check("ไม่ลากอาชีพของฉบับ 2566 มาตอบแทน", "2566" not in got, got[-220:])
check("ไม่เรียกโมเดล", calls == [], f"เรียก {calls}")

# 14 ต.ค. 2569 — คุณสมบัติผู้เข้าศึกษา (admission) เข้า USER_FACING_FIELDS แล้ว ข้อนี้จึงไม่ใช่
# กรณี "มีหัวข้อที่ไม่เปิดให้ตอบจากฐานปนอยู่" อีก · วิทยาการคอมพิวเตอร์ยังไม่มีข้อมูลคุณสมบัติ
# ที่ผ่านการตรวจ พฤติกรรมที่ต้องการคือตอบหัวข้อที่ฐานมี แล้วบอกชัดว่าอีกหัวข้อยังไม่มีข้อมูล
# (รายละเอียดของหัวข้อนี้อยู่ใน tests/test_admission_from_db.py)
got, calls, _t = ask("วิทยาการคอมพิวเตอร์ 2566 เรียนกี่หน่วยกิต และคุณสมบัติผู้สมัครมีอะไรบ้าง")
check("ตอบหน่วยกิตจากฐานได้", "130" in got, got[:160])
check("บอกชัดว่าส่วนคุณสมบัติยังไม่มีข้อมูลที่ผ่านการตรวจ",
      "ยังไม่พบข้อมูลคุณสมบัติผู้สมัคร" in got, got[-200:])
check("ไม่เรียกโมเดล", calls == [], f"เรียก {calls}")

# ---------------------------------------------------------------- 3
print()
print("3. คำถามต่อเนื่องต้องจำหลักสูตร ปี และระดับปริญญา โดยไม่เรียกโมเดล")
PRIOR_CS61 = [
    {"role": "user", "content": "หลักสูตรวิทยาการคอมพิวเตอร์ พ.ศ. 2561 ต้องเรียนทั้งหมดกี่หน่วยกิต"},
    {"role": "assistant", "content": "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาการคอมพิวเตอร์ "
                                     "(พ.ศ. 2561) มีจำนวนหน่วยกิตรวมตลอดหลักสูตร ไม่น้อยกว่า 130 "
                                     "หน่วยกิต\nที่มา: cs61.pdf หน้า 6"},
]
got, calls, took = ask("แล้วปี 2566 ล่ะ", PRIOR_CS61)
check('"แล้วปี 2566 ล่ะ" ตอบเป็นฉบับ 2566', "2566" in got, got[:130])
check('ไม่ตอบเป็นฉบับ 2561', "2561" not in got, got[:130])
check("ไม่เรียกโมเดล (เดิมเสีย 30 วินาทีกับโมเดลก่อน)", calls == [], f"เรียก {calls}")
check("ตอบเร็วกว่า 5 วินาที", took <= 5.0, f"{took:.2f}s")

got, calls, took = ask("สาขานี้เรียนกี่หน่วยกิต", PRIOR_CS61)
check('"สาขานี้" ตอบเป็นฉบับ 2561 ตามบริบท', "2561" in got, got[:140])
check('"สาขานี้" ไม่ลากฉบับ 2566 เข้ามา (ช่องว่างเดิม)', "2566" not in got, got[:140])
check("ไม่เรียกโมเดล", calls == [], f"เรียก {calls}")

PRIOR_MASTER = [
    {"role": "user", "content": "หลักสูตรปริญญาโทการจัดการเทคโนโลยีการเกษตรเรียนกี่หน่วยกิต"},
    {"role": "assistant", "content": "หลักสูตรวิทยาศาสตรมหาบัณฑิต สาขาวิชาการจัดการเทคโนโลยี"
                                     "การเกษตรและบริหารทรัพยากรชุมชน (พ.ศ. 2568) มีจำนวนหน่วยกิต"
                                     "รวมตลอดหลักสูตร ไม่น้อยกว่า 36 หน่วยกิต"},
]
got, calls, _t = ask("สาขานี้มีวัตถุประสงค์อะไร", PRIOR_MASTER)
check('"สาขานี้" จำระดับปริญญาโทได้ (ไม่ตอบของตรีหรือเอก)',
      "มหาบัณฑิต" in got or "ปริญญาโท" in got, got[:160])
check("ไม่เรียกโมเดล", calls == [], f"เรียก {calls}")

# ---------------------------------------------------------------- 4
print()
print("4. ปีฉบับที่ไม่มีต้องบอกว่ายังไม่พบในข้อมูลของระบบ พร้อมปีที่มี")
got, calls, _t = ask("หลักสูตรคณิตศาสตร์ พ.ศ. 2554 เรียนกี่หน่วยกิต")
check("บอกว่ายังไม่พบในข้อมูลของระบบ", "ยังไม่พบ" in got and "ข้อมูลของระบบ" in got, got[:200])
check("บอกปีที่มีข้อมูล", "2569" in got and "2564" in got, got[:200])
check("ไม่สรุปว่ามหาวิทยาลัยไม่มีหลักสูตรนั้น",
      "ไม่มีหลักสูตร" not in got and "ไม่เปิดสอน" not in got, got[:200])
check("ไม่เรียกโมเดล", calls == [], f"เรียก {calls}")

got, calls, _t = ask("หลักสูตรวิทยาการคอมพิวเตอร์ พ.ศ. 2599 กี่หน่วยกิต")
check("ปีในอนาคตก็บอกแบบเดียวกัน", "ยังไม่พบ" in got, got[:160])
check("บอกปีที่มีของวิทยาการคอมพิวเตอร์", "2566" in got and "2561" in got, got[:180])

got, calls, _t = ask("หลักสูตรคณิตศาสตร์ พ.ศ. 2564 เรียนกี่หน่วยกิต")
check("ปีที่มีอยู่จริงยังตอบได้ตามปกติ", "130" in got and "ที่มา:" in got, got[:160])
check("ไม่เรียกโมเดล", calls == [], f"เรียก {calls}")

print()
print("4.1 ระดับปริญญาที่ไม่มีก็ต้องไม่พูดแทนมหาวิทยาลัย")
got, calls, _t = ask("หลักสูตรปริญญาเอกวิทยาการคอมพิวเตอร์เรียนกี่หน่วยกิต")
check("บอกว่ายังไม่พบในข้อมูลของระบบ", "ยังไม่พบ" in got, got[:180])
check("ไม่ยืมตัวเลขของระดับอื่น", "130" not in got, got[:180])
check("ไม่เรียกโมเดล", calls == [], f"เรียก {calls}")

# ---------------------------------------------------------------- 5
print()
print("5. timing log ต้องครอบคำขอที่ล้มระหว่างเตรียมคำตอบ")
got, calls, _t = ask("หลักสูตรวิทยาการคอมพิวเตอร์มีเงินเดือนเริ่มต้นของบัณฑิตเท่าไร")
line = timing_line()
check("คำขอนี้ล้มระหว่างเตรียมคำตอบจริง (เรียกโมเดลแล้วล้ม)", calls != [], f"เรียก {calls}")
check("มีบรรทัด timing", bool(line), "ไม่มีบรรทัด timing เลย")
check("บรรทัด timing บอกว่าล้มตอนเตรียม", "ล้มตอนเตรียม" in line, line[:170])

print()
print(f"จุดตรวจ {CHECKS} จุด")
print(f"เรียกแคชทั้งหมด {len(CACHE_ASKED)} ครั้ง · เรียกโมเดลทั้งหมด {len(DEAD.calls)} ครั้ง")
if FAILURES:
    print(f"ตก {len(FAILURES)} จุด")
    for f in FAILURES:
        print("  -", f)
    raise SystemExit(1)
print("ผ่านทั้งหมด")
