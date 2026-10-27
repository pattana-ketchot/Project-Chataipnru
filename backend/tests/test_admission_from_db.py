"""
คุณสมบัติผู้เข้าศึกษาต้องมาจากข้อมูลที่ตรวจรับแล้ว ไม่ใช่จากภาคผนวกข้อบังคับของมหาวิทยาลัย

    cd backend && python tests/test_admission_from_db.py

ที่มาของชุดนี้ — วัดข้อ r1-07 ของชุด 37 ข้อ 13 รอบเมื่อ 14 ต.ค. 2569 (เส้นทางเอกสาร)
    คำตอบครบตาม gold                    10/13
    ตอบไม่ครบ (ขาด ปวส./ปริญญาตรี)        3/13
    ดึงเงื่อนไขจาก it66.pdf หน้า 161 มาตอบ  1/13  ← ภาคผนวกข้อบังคับของมหาวิทยาลัย
                                                  (ประวัติอาชญากรรม) ไม่ใช่ของหลักสูตร

ข้อมูลที่ตรวจรับแล้วของ IT ฉบับ 2566 มีครบ 3 ข้อจาก it66.pdf หน้า 16 (ผู้ตรวจเป็นคน)
จึงย้ายหัวข้อนี้มาตอบจากฐาน และเมื่อฐานไม่มีข้อมูลให้ "ระบุชัดว่าไม่มี" แทนการเดาจากเอกสาร

**โมเดลถูกทำให้ใช้ไม่ได้ทั้งชุด** คำตอบใดที่ออกมาได้จึงมาจากข้อมูลที่ตรวจรับแล้วเท่านั้น
และตรวจสถานะฐานก่อนถามทุกครั้ง เพื่อให้ข้อที่ตกบอกได้ว่าเป็น fixture ล้าสมัยหรือโค้ดพัง
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


logging.getLogger("course_advisor").addHandler(logging.NullHandler())

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text as sql  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.services import chat as C  # noqa: E402
from app.services import llm_client  # noqa: E402

C.cache_lookup = lambda db, q, v: None
C.cache_store = lambda *a, **k: None
DEAD = DeadModel()
llm_client._connector = DEAD
CLIENT = TestClient(app)

IT66 = "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาเทคโนโลยีสารสนเทศ (พ.ศ. 2566)"
IT61 = "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาเทคโนโลยีสารสนเทศ (พ.ศ. 2561)"
CS66 = "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาการคอมพิวเตอร์ (พ.ศ. 2566)"
SCOPE = "ไม่ใช่ประกาศรับสมัครของปีปัจจุบัน"


def ask(message: str):
    before = len(DEAD.calls)
    t0 = time.perf_counter()
    r = CLIENT.post("/chat-web", json={"messages": [{"role": "user", "content": message}]})
    return r.text.strip(), DEAD.calls[before:], time.perf_counter() - t0


def admission_rows(course_title: str) -> tuple[int, set]:
    with SessionLocal() as db:
        rows = db.execute(sql(
            "SELECT page_start FROM mko.v_live_list_items "
            "WHERE course_title = :t AND item_type = 'admission'"), {"t": course_title}).all()
    return len(rows), {r[0] for r in rows}


print("0. สถานะฐานที่ fixture พึ่งพา — ตรวจก่อนถาม")
n66, pages66 = admission_rows(IT66)
n61, _ = admission_rows(IT61)
ncs, _ = admission_rows(CS66)
check("IT ฉบับ 2566 มีข้อมูลคุณสมบัติ 3 ข้อ", n66 == 3, f"{n66} ข้อ")
check("ข้อมูลนั้นมาจากหน้า 16", pages66 == {16}, str(pages66))
check("IT ฉบับ 2561 ยังไม่มีข้อมูล", n61 == 0, f"{n61} ข้อ")
check("วิทยาการคอมพิวเตอร์ยังไม่มีข้อมูล", ncs == 0, f"{ncs} ข้อ")

print()
print("1. ข้อ r1-07 (ไม่ระบุปี) — ตอบจากข้อมูลที่ตรวจรับแล้ว ครบทุกข้อ")
got, calls, took = ask("คุณสมบัติผู้เข้าศึกษาของเทคโนโลยีสารสนเทศคืออะไร")
check("ไม่เรียกโมเดลเลย", calls == [], f"เรียก {calls}")
check("ตอบเร็วกว่า 5 วินาที", took <= 5.0, f"{took:.2f}s")
check("มีผู้จบ ม.ปลาย", "มัธยมศึกษาตอนปลาย" in got, got[:120])
check("มีผู้จบ ปวส.", "ปวส" in got, got[:200])
check("มีผู้จบปริญญาตรี", "ปริญญาตรี" in got, got[:200])
check("อ้างที่มา it66.pdf หน้า 16", "it66.pdf หน้า 16" in got, got[-200:])
check("บอกฉบับที่ยังไม่มีข้อมูลที่ผ่านการตรวจ", IT61 in got, got[-260:])
check("มีหมายเหตุบอกขอบเขตของคำตอบ", SCOPE in got, got[-200:])
check("ไม่ดึงเงื่อนไขจากภาคผนวก (ประวัติอาชญากรรม)", "จำคุก" not in got, got[:200])
check("ไม่อ้างหน้า 161", "หน้า 161" not in got, got[-200:])

print()
print("2. ระบุปี 2566 — ได้รายการเดียวกัน")
got, calls, _t = ask("หลักสูตรเทคโนโลยีสารสนเทศ พ.ศ. 2566 คุณสมบัติผู้สมัครมีอะไรบ้าง")
check("ไม่เรียกโมเดล", calls == [], f"เรียก {calls}")
check("มีทั้ง ปวส. และปริญญาตรี", "ปวส" in got and "ปริญญาตรี" in got, got[:200])
check("อ้างที่มา it66.pdf หน้า 16", "it66.pdf หน้า 16" in got, got[-160:])

print()
print("3. ระบุปี 2561 (ฉบับที่ยังไม่มีข้อมูล) — ต้องระบุชัด ไม่ยืมของฉบับอื่น")
got, calls, _t = ask("หลักสูตรเทคโนโลยีสารสนเทศ พ.ศ. 2561 คุณสมบัติผู้สมัครมีอะไรบ้าง")
check("ไม่เรียกโมเดล", calls == [], f"เรียก {calls}")
check("บอกว่ายังไม่พบข้อมูลที่ผ่านการตรวจ", "ยังไม่พบข้อมูลคุณสมบัติผู้เข้าศึกษา" in got, got[:160])
check("ระบุฉบับที่ถาม (2561)", "2561" in got, got[:160])
check("ชี้ฉบับที่ระบบมีข้อมูล (2566)", "2566" in got, got[:300])
check("ไม่ยืมรายการของฉบับ 2566 มาตอบ", "ปวส" not in got, got[:300])
check("บอกว่าไม่ตอบจากข้อบังคับทั่วไปของมหาวิทยาลัย",
      "ไม่ตอบจากข้อบังคับทั่วไป" in got, got[:300])

print()
print("4. สำนวนอื่นของคำถามเดียวกัน — ต้องได้คำตอบจากฐานเหมือนกัน")
for q in ("ใครสมัครเรียนเทคโนโลยีสารสนเทศได้",
          "สมัครเรียนเทคโนโลยีสารสนเทศ ต้องจบอะไรมา",
          "หลักสูตรเทคโนโลยีสารสนเทศรับผู้จบ ปวส. ไหม"):
    got, calls, _t = ask(q)
    ok = calls == [] and "ปวส" in got and "it66.pdf หน้า 16" in got
    check(f"ตอบจากฐานได้: {q}", ok, f"เรียก {calls} · {got[:110]}")

print()
print("5. สาขาที่ยังไม่มีข้อมูล — ระบุชัด ไม่ตอบจากภาคผนวก")
got, calls, _t = ask("คุณสมบัติของผู้เข้าศึกษาหลักสูตรวิทยาการคอมพิวเตอร์มีอะไรบ้าง")
check("ไม่เรียกโมเดล", calls == [], f"เรียก {calls}")
check("บอกว่ายังไม่พบข้อมูลที่ผ่านการตรวจ", "ยังไม่พบข้อมูลคุณสมบัติผู้เข้าศึกษา" in got, got[:160])
check("ไม่ตอบด้วยเงื่อนไขจากภาคผนวก", "จำคุก" not in got and "โรคติดต่อ" not in got, got[:200])
check("แนะช่องทางที่ถูกต้องแทน", "ประกาศรับสมัคร" in got, got[-160:])

print()
print("6. ชื่อสาขาที่มีหลายระดับปริญญา — ถามกลับ ไม่เลือกระดับแทนผู้ใช้")
got, calls, _t = ask("คุณสมบัติผู้เข้าศึกษาของการจัดการเทคโนโลยีการเกษตรและบริหารทรัพยากรชุมชนคืออะไร")
check("ไม่เรียกโมเดล", calls == [], f"เรียก {calls}")
check("บอกว่ามีหลายระดับปริญญา", "หลายระดับปริญญา" in got, got[:160])
check("ขอให้ระบุระดับ", "ระบุระดับ" in got, got[:160])

print()
print("7. ฉบับที่ไม่มีอยู่ — ต้องไม่ถอยไปใช้ฉบับอื่น")
got, calls, _t = ask("หลักสูตรเทคโนโลยีสารสนเทศ พ.ศ. 2570 คุณสมบัติผู้สมัครมีอะไรบ้าง")
check("ไม่เรียกโมเดล", calls == [], f"เรียก {calls}")
# ด่านปีฉบับที่ไม่มี (0.716) ตอบก่อนด่านนี้ด้วยถ้อยคำมาตรฐานของระบบ พร้อมไล่ปีที่มีข้อมูล
# ซึ่งดีกว่าข้อความของด่าน admission_gap จึงตรวจถ้อยคำนั้น ไม่ใช่บังคับให้เป็นของด่านใหม่
check("บอกว่ายังไม่พบฉบับ 2570 ในข้อมูลของระบบ",
      "ยังไม่พบ" in got and "2570" in got and "ข้อมูลของระบบ" in got, got[:160])
check("ไล่ปีที่มีข้อมูลให้ผู้ใช้เลือก", "2566" in got, got[:200])
check("ไม่ตอบด้วยรายการของฉบับ 2566", "ปวส" not in got, got[:200])

print()
print("8. คำถามสองหัวข้อ — ตอบครบทั้งสอง และบอกส่วนที่ไม่มีอย่างตรงกับพฤติกรรมจริง")
got, calls, _t = ask("หลักสูตรเทคโนโลยีสารสนเทศ พ.ศ. 2566 เรียนกี่หน่วยกิต และคุณสมบัติผู้สมัครมีอะไรบ้าง")
check("ไม่เรียกโมเดล", calls == [], f"เรียก {calls}")
check("มีหน่วยกิต", "130" in got, got[:140])
check("มีรายการคุณสมบัติ", "ปวส" in got, got[:300])
check("อ้างที่มาของทั้งสองส่วน", got.count("ที่มา:") >= 2, f"{got.count('ที่มา:')} ครั้ง")

got, calls, _t = ask("วิทยาการคอมพิวเตอร์ 2566 เรียนกี่หน่วยกิต และคุณสมบัติผู้สมัครมีอะไรบ้าง")
check("ไม่เรียกโมเดล", calls == [], f"เรียก {calls}")
check("ตอบหน่วยกิตได้", "130" in got, got[:140])
check("บอกว่าส่วนคุณสมบัติยังไม่มีข้อมูล",
      "ยังไม่พบข้อมูลคุณสมบัติผู้สมัคร" in got, got[-220:])
check("ไม่สัญญาว่าจะไปค้นเอกสารให้ (เพราะด่านนี้ไม่ตอบจากเอกสาร)",
      "ค้นจากเอกสารหลักสูตรให้" not in got, got[-220:])

print()
print(f"จุดตรวจ {CHECKS} จุด · เรียกโมเดลทั้งหมด {len(DEAD.calls)} ครั้ง (ต้องเป็น 0)")
if FAILURES:
    print(f"ตก {len(FAILURES)} จุด")
    for f in FAILURES:
        print("  -", f)
    raise SystemExit(1)
print("ผ่านทั้งหมด")
