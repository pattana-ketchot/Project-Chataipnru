"""
ด่านค่าเทอมต้องไม่ทิ้งคำถามส่วนอื่นในข้อความเดียวกัน

    cd backend && python tests/test_tuition_plus_other_part.py

ที่มาของชุดนี้ — ตรวจทางตอบเร็ว 14 ต.ค. 2569 พบว่า
    "วิทคอมเรียนกี่หน่วยกิต แล้วค่าเทอมเท่าไหร่"
ได้คำตอบเรื่องค่าเทอมอย่างเดียว ส่วนคำถามหน่วยกิตหายไปเงียบ ๆ เพราะด่านค่าเทอม
(ด่าน 0.5) อยู่ก่อนด่านอื่นทั้งหมดและตอบจบในตัว

ยิงผ่าน /chat-web ด้วย TestClient (ปั๊ม generator แบบเดียวกับ uvicorn) โดย
**ปิดแคช** และ **ทำให้โมเดลใช้ไม่ได้** เพื่อให้แน่ใจว่าคำตอบทั้งสองส่วนมาจาก
ข้อมูลจริง ไม่ใช่คำตอบเก่าในแคชและไม่ใช่โมเดลแต่งให้
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

from app.services import chat as C  # noqa: E402
from app.services import llm_client  # noqa: E402
from app.main import app  # noqa: E402

C.cache_lookup = lambda db, q, v: None
C.cache_store = lambda *a, **k: None
DEAD = DeadModel()
llm_client._connector = DEAD

CLIENT = TestClient(app)
SENT: list[float] = []


def ask(message, prior=None):
    # ด่านจำกัดอัตรายอม 20 คำขอ/นาที/IP — รอให้มีที่ว่างก่อนยิง
    while True:
        SENT[:] = [t for t in SENT if time.monotonic() - t < 60.0]
        if len(SENT) < 17:
            break
        time.sleep(60.0 - (time.monotonic() - SENT[0]) + 0.3)
    SENT.append(time.monotonic())
    before = len(DEAD.calls)
    msgs = list(prior or []) + [{"role": "user", "content": message}]
    r = CLIENT.post("/chat-web", json={"messages": msgs})
    return r.text.strip(), DEAD.calls[before:]


FEE = "12,000"
CREDITS = "130"
NOTE = "ยังตอบจากข้อมูลที่ตรวจแล้วไม่ได้"

print("1. ถามหน่วยกิตก่อน แล้วถามค่าเทอม — ต้องได้ทั้งสองส่วน")
got, calls = ask("วิทคอมเรียนกี่หน่วยกิต แล้วค่าเทอมเท่าไหร่")
check("มีคำตอบเรื่องหน่วยกิต", CREDITS in got, got[:150])
check("มีคำว่าไม่น้อยกว่า", "ไม่น้อยกว่า" in got, got[:150])
check("มีคำตอบเรื่องค่าเทอม", FEE in got, got[:150])
check("หน่วยกิตมาก่อนค่าเทอมตามลำดับที่ถาม",
      CREDITS in got and FEE in got and got.index(CREDITS) < got.index(FEE), "")
check("ไม่เรียกโมเดล", calls == [], f"เรียก {calls}")

print()
print("2. ถามค่าเทอมก่อน แล้วถามหน่วยกิต — ต้องได้ทั้งสองส่วน และค่าเทอมมาก่อน")
got, calls = ask("ค่าเทอมวิทคอมเท่าไหร่ แล้วเรียนกี่หน่วยกิต")
check("มีคำตอบเรื่องค่าเทอม", FEE in got, got[:150])
check("มีคำตอบเรื่องหน่วยกิต", CREDITS in got, got[:150])
check("ค่าเทอมมาก่อนหน่วยกิตตามลำดับที่ถาม",
      CREDITS in got and FEE in got and got.index(FEE) < got.index(CREDITS), "")
check("ไม่เรียกโมเดล", calls == [], f"เรียก {calls}")

print()
print("3. ถามค่าเทอมอย่างเดียว — ต้องเหมือนเดิมทุกอย่าง ไม่มีหมายเหตุงอก")
got, calls = ask("ค่าเทอมวิทคอมเท่าไหร่")
check("มีคำตอบเรื่องค่าเทอม", FEE in got, got[:120])
check("ไม่มีหมายเหตุว่ายังไม่ได้ตอบส่วนอื่น", NOTE not in got, got[-120:])
check("ไม่มีคำตอบหน่วยกิตงอกมา", CREDITS not in got, got[:120])
check("ไม่เรียกโมเดล", calls == [], f"เรียก {calls}")

print()
print("4. คำลงท้ายที่ไม่ใช่คำถาม — ต้องไม่ถือเป็นส่วนที่ถูกข้าม")
got, calls = ask("ค่าเทอมวิทคอมเท่าไหร่ ขอบคุณครับ")
check("มีคำตอบเรื่องค่าเทอม", FEE in got, got[:120])
check("ไม่มีหมายเหตุว่ายังไม่ได้ตอบส่วนอื่น", NOTE not in got, got[-140:])
check("ไม่เรียกโมเดล", calls == [], f"เรียก {calls}")

print()
print("5. ส่วนที่เหลือเป็นเรื่องที่ฐานตอบไม่ได้ — ต้องบอกว่ายังไม่ได้ตอบส่วนไหน")
got, calls = ask("ค่าเทอมวิทคอมเท่าไหร่ แล้วมีวิชาอะไรบ้าง")
check("มีคำตอบเรื่องค่าเทอม", FEE in got, got[:120])
check("บอกว่ายังไม่ได้ตอบส่วนที่เหลือ", NOTE in got, got[-200:])
check("อ้างถึงส่วนที่ยังไม่ได้ตอบด้วยข้อความของผู้ใช้", "วิชาอะไรบ้าง" in got, got[-200:])
check("ไม่เรียกโมเดล", calls == [], f"เรียก {calls}")

print()
print("6. คำถามค่าเทอมต่อเนื่อง — ต้องยังทำงานเหมือนเดิม")
prior = [
    {"role": "user", "content": "หลักสูตรวิทยาการคอมพิวเตอร์เรียนกี่หน่วยกิต"},
    {"role": "assistant", "content": "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาการคอมพิวเตอร์ … 130 หน่วยกิต"},
]
got, calls = ask("แล้วค่าเทอมล่ะ", prior)
check("ยังตอบค่าเทอมของสาขาที่คุยอยู่", FEE in got, got[:140])
check("ไม่มีหมายเหตุว่ายังไม่ได้ตอบส่วนอื่น", NOTE not in got, got[-140:])
check("ไม่เรียกโมเดล", calls == [], f"เรียก {calls}")

print()
print("7. ถามค่าเทอมพร้อมอาชีพ — ทั้งสองส่วนมาจากข้อมูลจริง")
got, calls = ask("ค่าเทอมเทคโนโลยีสารสนเทศเท่าไหร่ แล้วจบไปทำงานอะไรได้บ้าง")
check("มีคำตอบเรื่องค่าเทอม", "บาท" in got, got[:140])
check("มีรายการอาชีพ หรือบอกว่ายังไม่ได้ตอบส่วนนั้น",
      ("อาชีพ" in got) or (NOTE in got), got[-220:])
check("ไม่เรียกโมเดล", calls == [], f"เรียก {calls}")

print()
print(f"จุดตรวจ {CHECKS} จุด")
if FAILURES:
    print(f"ตก {len(FAILURES)} จุด")
    for f in FAILURES:
        print("  -", f)
    raise SystemExit(1)
print("ผ่านทั้งหมด")
