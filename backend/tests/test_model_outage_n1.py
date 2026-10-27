"""
n1-05 / n1-06 — พฤติกรรมตอนผู้ให้บริการโมเดลล่มทุกโมเดล

    cd backend && python tests/test_model_outage_n1.py

สองข้อนี้อยู่ในชุด 37 ข้อแต่รันร่วมกับข้ออื่นไม่ได้ เพราะต้องจำลองให้โมเดลล่มทั้งหมด
จึงแยกมารันเป็นชุดของตัวเอง (ปิดแคชด้วย เพื่อให้คำตอบมาจากข้อมูลจริงเท่านั้น)

เกณฑ์ตามที่ gold กำหนด
    n1-05  คำถามที่ต้องค้นเอกสาร -> ต้องบอกว่าบริการขัดข้องอย่างชัดเจน
           ห้ามเดารายวิชาหรือตอบด้วยความรู้ทั่วไป และต้องไม่เกินเพดานเวลา
    n1-06  คำถามที่ตอบจากฐานได้ -> ต้องยังตอบได้ พร้อมที่มา เพราะไม่เรียกโมเดลเลย

แยกให้ชัดระหว่าง "บริการขัดข้อง" กับ "ข้อมูลขาด" กับ "คำตอบผิด":
ชุดนี้ทดสอบเฉพาะกรณีบริการขัดข้อง — ข้อที่ตอบจากฐานได้ต้องไม่ถูกกระทบเลย
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


class AllModelsDown:
    """ผู้ให้บริการล่มทุกโมเดล — เลียนผลลัพธ์ที่ปลายทางตอบ 503 ครบทุกตัว"""

    answer_token_cap = 2048

    def __init__(self) -> None:
        self.calls: list[str] = []

    def _die(self, what: str):
        self.calls.append(what)
        raise LLMConnectionError(
            "โมเดล Gemini ทุกตัวใช้ไม่ได้ (โควตาหมดหรือรับไม่ไหว) ล่าสุด: จำลอง 503")

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
DOWN = AllModelsDown()
llm_client._connector = DOWN
CLIENT = TestClient(app)


def ask(message):
    before = len(DOWN.calls)
    t0 = time.perf_counter()
    r = CLIENT.post("/chat-web", json={"messages": [{"role": "user", "content": message}]})
    return r.text.strip(), DOWN.calls[before:], time.perf_counter() - t0


SERVICE = ("ระบบหลักตอบไม่ได้", "ขอไม่ตอบด้วยโมเดลสำรอง", "ระบบ AI ยังไม่พร้อม",
           "ระบบตอบไม่ได้ในขณะนี้", "เกินเพดาน", "ขัดข้อง", "ลองใหม่")

# fixture เดิมถาม "วิชาบังคับของวิทยาการคอมพิวเตอร์ 2566" ซึ่งหลังเผยแพร่รายวิชา (ขั้น C)
# ฐานข้อมูลตอบได้เองโดยไม่เรียกโมเดล · ข้อนี้จึงตก 4 จุดเพราะ "ไม่มีบริการขัดข้องให้เห็น"
# ไม่ใช่เพราะพฤติกรรมตอนโมเดลล่มเปลี่ยน (คำตอบจากฐานตอนโมเดลล่มคือสิ่งที่ n1-06 ต้องการ)
#
# จึงเปลี่ยนไปใช้คำถามที่ชั้นข้อมูลที่เผยแพร่ไม่มีให้ตอบจริง: ระยะเวลาการศึกษา ไม่ได้อยู่ใน
# ชั้นข้อมูลนั้นเลย (มีเฉพาะหน่วยกิต ปีฉบับ อาชีพ วัตถุประสงค์ คุณสมบัติผู้สมัคร รายวิชา)
# คำถามนี้คือข้อ r1-06 ของชุด 37 ข้อ ซึ่งวัดแล้วว่าเดินเส้นทาง RAG จริง
print("n1-05 คำถามที่ต้องค้นเอกสาร ขณะโมเดลล่มทุกตัว")
got, calls, took = ask("หลักสูตรวิทยาการคอมพิวเตอร์เรียนกี่ปี")
hit = [m for m in SERVICE if m in got]
check("คำถามนี้ต้องพึ่งโมเดลจริง (ฐานตอบไม่ได้)", calls != [], f"เรียก {calls}")
check("บอกสถานะบริการขัดข้องอย่างชัดเจน", bool(hit), f"เจอ {hit} · {got[:140]}")
# ข้อเท็จจริงสองข้อนี้อยู่ในระเบียบที่อ้างใน cs61.pdf หน้า 129 — ระบบจะรู้ได้ต้องอ่านเอกสาร
# ตอนที่อ่านไม่ได้เลยแล้วยังพูดออกมา คือการตอบจากความรู้ทั่วไปของโมเดล
check("ไม่เดาระยะเวลาการศึกษาจากความรู้ทั่วไป",
      "6 ภาคการศึกษา" not in got and "8 ปีการศึกษา" not in got, got[:140])
check("ไม่อ้างที่มาของเอกสารทั้งที่อ่านเอกสารไม่ได้", "ที่มา:" not in got, got[:140])
check("ไม่เกินเพดานเวลา 30 วินาที (เผื่อ 5)", took <= 35.0, f"{took:.2f}s")

print()
print('n1-05ก "บริการขัดข้อง" ต้องไม่ถูกรายงานเป็น "ไม่มีข้อมูลในเอกสาร"')
# ข้อ n1-01 ถามเรื่องทุนการศึกษา ซึ่งเอกสารไม่มีจริง (gold ตรวจแล้ว) คำตอบปกติคือ
# "ไม่พบข้อมูลนี้ในเอกสารหลักสูตร" · แต่ตอนโมเดลล่ม ระบบยังไม่ได้อ่านเอกสารเลย
# การตอบว่าเอกสารไม่มีจึงเป็นการสรุปแทนเอกสารโดยไม่มีหลักฐาน ต้องบอกว่าขัดข้องเท่านั้น
got, calls, took = ask("หลักสูตรวิทยาการคอมพิวเตอร์มีทุนการศึกษาอะไรบ้าง")
hit = [m for m in SERVICE if m in got]
check("บอกสถานะบริการขัดข้อง", bool(hit), f"เจอ {hit} · {got[:140]}")
check("ไม่สรุปว่าเอกสารไม่มีข้อมูลนี้", "ไม่พบข้อมูลนี้ในเอกสารหลักสูตร" not in got, got[:140])
check("ไม่เดารายชื่อทุน", not any(w in got for w in ("กยศ", "ทุนเรียนดี", "ทุนละ")), got[:140])

print()
print("n1-06 คำถามที่ตอบจากฐานได้ ขณะโมเดลล่มทุกตัว")
got, calls, took = ask("หลักสูตรคณิตศาสตร์ต้องเรียนทั้งหมดกี่หน่วยกิต")
check("ยังตอบได้", "หน่วยกิต" in got, got[:120])
check("มีตัวเลขของฉบับ 2569 (124)", "124" in got, got[:160])
check("มีตัวเลขของฉบับ 2564 (130)", "130" in got, got[:160])
check("คงคำว่าไม่น้อยกว่า", "ไม่น้อยกว่า" in got, got[:160])
check("ไม่มีข้อความบริการขัดข้อง", "ขัดข้อง" not in got, got[:160])
check("อ้างที่มาครบสองไฟล์", "ma69.pdf" in got and "ma64.pdf" in got, got[-160:])
check("ไม่เรียกโมเดลเลย", calls == [], f"เรียก {calls}")
check("ตอบเร็วกว่า 5 วินาที", took <= 5.0, f"{took:.2f}s")

print()
print(f"จุดตรวจ {CHECKS} จุด")
print(f"เรียกโมเดลทั้งหมด {len(DOWN.calls)} ครั้ง (ล้มทุกครั้งตามที่จำลอง)")
if FAILURES:
    print(f"ตก {len(FAILURES)} จุด")
    for f in FAILURES:
        print("  -", f)
    raise SystemExit(1)
print("ผ่านทั้งหมด")
