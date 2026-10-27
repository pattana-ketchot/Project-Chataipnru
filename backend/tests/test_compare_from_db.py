"""
ตอบคำถามเปรียบเทียบข้อเท็จจริงจากฐาน โดยไม่สรุปเกินกว่าที่เทียบได้

    cd backend && python tests/test_compare_from_db.py

ที่มา — ชุด 37 ข้อเมื่อ 14 ต.ค. 2569 ข้อ c1-02
    "หลักสูตรวิทยาการคอมพิวเตอร์ฉบับ 2561 กับ 2566 หน่วยกิตต่างกันไหม"
ตอบว่าไม่พบข้อมูล ทั้งที่ฐานมีค่าทั้งสองฝั่ง (130 เท่ากัน) เพราะ detect() ติด
คำเชิงเทียบและ multiple_years จึงไม่รับ แล้วเส้นทางเอกสารก็ตอบไม่ได้

กติกาที่ชุดนี้บังคับ
    - ตอบทั้งสองฝั่งพร้อมที่มาของแต่ละฝั่ง
    - ถ้าเท่ากัน ต้องกำกับว่า "เท่ากันเฉพาะตัวเลขนี้" ห้ามสรุปว่าหลักสูตรเหมือนกัน
    - ถ้าไม่ระบุปีและมีหลายฉบับ ต้องแสดงแยกปี ไม่เลือกฉบับใดฉบับหนึ่งมาตอบแทน
    - คำถามเทียบที่ต้องตีความเนื้อหา ต้องไม่ถูกชั้นข้อมูลคว้าไปตอบ
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


def ask(message):
    while True:
        SENT[:] = [t for t in SENT if time.monotonic() - t < 60.0]
        if len(SENT) < 17:
            break
        time.sleep(60.0 - (time.monotonic() - SENT[0]) + 0.3)
    SENT.append(time.monotonic())
    before = len(DEAD.calls)
    r = CLIENT.post("/chat-web", json={"messages": [{"role": "user", "content": message}]})
    return r.text.strip(), DEAD.calls[before:]


CAVEAT = "ไม่ได้หมายความว่ารายวิชา"

print("1. เทียบสองฉบับของหลักสูตรเดียว — ค่าเท่ากัน")
got, calls = ask("หลักสูตรวิทยาการคอมพิวเตอร์ฉบับ 2561 กับ 2566 หน่วยกิตต่างกันไหม")
check("พูดถึงฉบับ 2561", "2561" in got, got[:140])
check("พูดถึงฉบับ 2566", "2566" in got, got[:140])
check("มีตัวเลขหน่วยกิต", "130" in got, got[:140])
check("อ้างที่มาของทั้งสองฝั่ง", got.count("ที่มา:") >= 2, f"พบ {got.count('ที่มา:')} ครั้ง")
check("สรุปว่าเท่ากัน", "เท่ากัน" in got, got[-220:])
check("ไม่สรุปว่าหลักสูตรเหมือนกันทั้งหมด", CAVEAT in got, got[-260:])
check("ไม่เรียกโมเดล", calls == [], f"เรียก {calls}")

print()
print("2. สำนวนอื่นของคำถามเดียวกัน")
for q in ("วิทยาการคอมพิวเตอร์ 2561 กับ 2566 หน่วยกิตเท่ากันไหม",
          "เทียบหน่วยกิตหลักสูตรวิทยาการคอมพิวเตอร์ พ.ศ. 2561 กับ พ.ศ. 2566"):
    got, calls = ask(q)
    ok = "130" in got and "2561" in got and "2566" in got
    check(f"{q[:44]} ตอบทั้งสองฝั่ง", ok, got[:120])
    check("   ไม่เรียกโมเดล", calls == [], f"เรียก {calls}")

print()
print("3. เทียบสองหลักสูตร — ฝั่งที่มีหลายฉบับต้องแสดงแยกปี ไม่เลือกให้เอง")
got, calls = ask("คณิตศาสตร์กับวิทยาการคอมพิวเตอร์ หน่วยกิตต่างกันไหม")
check("พูดถึงคณิตศาสตร์", "คณิตศาสตร์" in got, got[:160])
check("พูดถึงวิทยาการคอมพิวเตอร์", "วิทยาการคอมพิวเตอร์" in got, got[:160])
check("ฝั่งคณิตศาสตร์แสดงแยกปี (2569 และ 2564)",
      "2569" in got and "2564" in got, got[:300])
check("ไม่เรียกโมเดล", calls == [], f"เรียก {calls}")

print()
print("4. เทียบที่ต้องตีความเนื้อหา — ชั้นข้อมูลต้องไม่คว้าไปตอบ")
# ทั้งสองหลักสูตรมีอยู่จริง และคำถามถาม "ยังไง" ซึ่งต้องใช้เนื้อหาเอกสาร
got, calls = ask("วิทยาการคอมพิวเตอร์กับเทคโนโลยีสารสนเทศ ต่างกันยังไง")
check("ไปเส้นทางเอกสาร (เรียกโมเดล) ไม่ใช่ตอบจากฐาน", calls != [], f"เรียก {calls}")
check("ไม่มีข้อความสรุปการเทียบตัวเลขงอกมา", "เท่ากันทั้งสองฝั่ง" not in got, got[:160])

print()
print("4.1 เทียบที่อีกฝั่งยังไม่มีในข้อมูล — ตอบจากฐาน ไม่ต้องพึ่งโมเดล")
# ข้อตรวจนี้เคยยืนยันว่าคำถามนี้ "ต้องไปเรียกโมเดล" ซึ่งเป็นพฤติกรรมเดิมที่ตอบว่า
# "ไม่พบข้อมูล" (ชุด 37 ข้อ a1-04) · เปลี่ยนโดยเจตนาเมื่อ 14 ต.ค. 2569 ให้ตอบจากฐาน
# ว่าอีกฝั่งยังไม่พบในข้อมูลของระบบ ดู course_scope.more_specific_unknown_name()
got, calls = ask("คณิตศาสตร์ กับ คณิตศาสตร์ประยุกต์ ต่างกันไหม")
check("บอกว่าอีกฝั่งยังไม่พบในข้อมูลของระบบ",
      "ยังไม่พบหลักสูตรคณิตศาสตร์ประยุกต์ ในข้อมูลของระบบ" in got, got[:170])
check("ไม่สรุปแทนมหาวิทยาลัย", "ไม่มีหลักสูตร" not in got, got[:170])
check("ไม่เรียกโมเดล", calls == [], f"เรียก {calls}")
check("ไม่มีตัวเลขหน่วยกิตที่ไม่ได้ถาม", "130" not in got, got[:160])

print()
print("5. คำถามหัวข้อเดียวฝั่งเดียวต้องไม่เปลี่ยนพฤติกรรม")
got, calls = ask("หลักสูตรวิทยาการคอมพิวเตอร์ พ.ศ. 2566 เรียนกี่หน่วยกิต")
check("ยังตอบฉบับเดียวตามเดิม", "2566" in got and "2561" not in got, got[:140])
check("ไม่มีข้อความสรุปการเทียบงอกมา", "เท่ากันทั้งสองฝั่ง" not in got, got[:160])
check("ไม่เรียกโมเดล", calls == [], f"เรียก {calls}")

print()
print(f"จุดตรวจ {CHECKS} จุด")
if FAILURES:
    print(f"ตก {len(FAILURES)} จุด")
    for f in FAILURES:
        print("  -", f)
    raise SystemExit(1)
print("ผ่านทั้งหมด")
