"""
แหล่งอ้างอิงแบบมีโครงสร้างของเส้นทาง /chat — ช่อง source และ sources

    cd backend && python tests/test_chat_structured_sources.py

ทำไมต้องตรวจแยกจาก /chat-web: เส้นทางหน้าเว็บส่งกลับเป็นข้อความดิบ ที่มาจึงอยู่ใน
ตัวข้อความอย่างเดียว วัดแบบมีโครงสร้างไม่ได้ · ส่วน /chat คืน ChatReply ซึ่งมีช่อง
`source` (ฉบับเดียว) และ `sources` (ครบทุกฉบับที่คำตอบอ้างถึง)

คำตอบจากฐานข้อมูลไม่มี citations เพราะไม่ได้มาจากการค้นเอกสาร — ที่มาอยู่ใน
source/sources การอ่านช่อง citations ช่องเดียวแล้วสรุปว่า "ไม่มีที่มา" จึงผิด

ชุดนี้เรียก answer_question() ซึ่งเป็นตัวสร้าง ChatReply ที่ route ใช้ · ไม่ผ่านชั้น
ตรวจสิทธิ์ของ route (ต้องมีผู้ใช้ที่ล็อกอิน) จึงไม่ได้ทดสอบชั้นนั้นในชุดนี้
"""
import logging
import sys
import uuid
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

    def _die(self, what):
        self.calls.append(what)
        raise LLMConnectionError("จำลองว่าโมเดลใช้ไม่ได้")

    def chat(self, *a, **k):
        return self._die("chat")

    def chat_stream(self, *a, **k):
        return self._die("chat_stream")

    def embed(self, *a, **k):
        return self._die("embed")


logging.getLogger("course_advisor").addHandler(logging.NullHandler())

from sqlalchemy import select, text  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services import chat as C  # noqa: E402
from app.services import llm_client  # noqa: E402

C.cache_lookup = lambda db, q, v: None
C.cache_store = lambda *a, **k: None
DEAD = DeadModel()
llm_client._connector = DEAD

SESSIONS: list[uuid.UUID] = []


def ask(db, user_id, message):
    before = len(DEAD.calls)
    reply = C.answer_question(db, user_id=user_id, session_id=None, message=message)
    SESSIONS.append(reply.session_id)
    return reply, DEAD.calls[before:]


with SessionLocal() as db:
    user_id = db.scalars(select(User.id).limit(1)).first()
    print(f"ใช้ผู้ใช้ที่มีอยู่ในฐานเป็นเจ้าของบทสนทนาทดสอบ: {'พบ' if user_id else 'ไม่พบ'}")

    print()
    print("1. คำถามฉบับเดียว — source ต้องชี้เอกสารฉบับนั้น")
    r, calls = ask(db, user_id, "หลักสูตรวิทยาการคอมพิวเตอร์ พ.ศ. 2561 ต้องเรียนทั้งหมดกี่หน่วยกิต")
    check("citations ว่าง (คำตอบไม่ได้มาจากการค้นเอกสาร)", r.citations == [], str(r.citations)[:80])
    check("source ไม่เป็น None", r.source is not None, str(r.source))
    check("source มี document_id และ page_start",
          bool(r.source) and r.source.get("document_id") and r.source.get("page_start"),
          str(r.source))
    check("sources มีหนึ่งรายการ", len(r.sources) == 1, str(len(r.sources)))
    s = r.sources[0] if r.sources else {}
    check("sources บอกไฟล์และหน้า", s.get("file") == "cs61.pdf" and s.get("page_start") == 6,
          str(s))
    check("sources บอกหลักสูตรที่อ้างถึง", "วิทยาการคอมพิวเตอร์" in (s.get("course_title") or ""),
          str(s.get("course_title")))
    check("ไม่เรียกโมเดล", calls == [], f"เรียก {calls}")

    print()
    print("2. คำถามไม่ระบุปี — sources ต้องครบทุกฉบับที่ตอบ")
    r, calls = ask(db, user_id, "หลักสูตรคณิตศาสตร์ต้องเรียนทั้งหมดกี่หน่วยกิต")
    files = sorted({x.get("file") for x in r.sources})
    check("sources มีสองฉบับ", len(r.sources) == 2, str(len(r.sources)))
    check("ครบทั้ง ma69.pdf และ ma64.pdf", files == ["ma64.pdf", "ma69.pdf"], str(files))
    check("ทุกรายการมีเลขหน้า", all(x.get("page_start") for x in r.sources), str(r.sources)[:150])
    check("ไม่เรียกโมเดล", calls == [], f"เรียก {calls}")

    print()
    print("3. คำถามหลายหัวข้อ — sources ต้องรวมที่มาของทุกหัวข้อและไม่ซ้ำ")
    r, calls = ask(db, user_id,
                   "หลักสูตรวิทยาการคอมพิวเตอร์ พ.ศ. 2566 เรียนกี่หน่วยกิต และจบไปทำงานอะไรได้บ้าง")
    pages = sorted({(x.get("file"), x.get("page_start")) for x in r.sources})
    check("sources มีมากกว่าหนึ่งรายการ", len(r.sources) >= 2, str(len(r.sources)))
    check("ไม่มีรายการซ้ำ", len(pages) == len(r.sources), f"{len(pages)} ไม่ซ้ำ จาก {len(r.sources)}")
    check("ครอบทั้งหน้าหน่วยกิตและหน้าอาชีพของ cs66.pdf",
          {p for f, p in pages if f == "cs66.pdf"} >= {2, 3}, str(pages))
    check("ไม่เรียกโมเดล", calls == [], f"เรียก {calls}")

    print()
    print("4. คำถามเทียบสองฝั่ง — sources ต้องมีที่มาของทั้งสองฝั่ง")
    r, calls = ask(db, user_id, "หลักสูตรวิทยาการคอมพิวเตอร์ฉบับ 2561 กับ 2566 หน่วยกิตต่างกันไหม")
    files = sorted({x.get("file") for x in r.sources})
    check("มีที่มาทั้ง cs61.pdf และ cs66.pdf", files == ["cs61.pdf", "cs66.pdf"], str(files))
    check("ไม่เรียกโมเดล", calls == [], f"เรียก {calls}")

    print()
    print("5. คำถามที่ตอบจากตารางค่าเทอม — ไม่มี source ของเอกสารหลักสูตร")
    r, calls = ask(db, user_id, "ค่าเทอมสาขาวิทยาการคอมพิวเตอร์เท่าไหร่")
    check("source เป็น None (ที่มาอยู่ในตัวข้อความ)", r.source is None, str(r.source))
    check("sources ว่าง", r.sources == [], str(r.sources))
    check("ตัวข้อความบอกที่มา", "ที่มา:" in (r.reply or ""), (r.reply or "")[-90:])
    check("ไม่เรียกโมเดล", calls == [], f"เรียก {calls}")

    db.rollback()

print()
print("บทสนทนาทดสอบที่สร้างขึ้น (เก็บกวาดด้วยสิทธิ์ผู้ดูแลฐานได้):")
print("  delete from chat_sessions where id in ("
      + ", ".join(f"'{s}'" for s in dict.fromkeys(map(str, SESSIONS))) + ")")
print()
print(f"จุดตรวจ {CHECKS} จุด")
if FAILURES:
    print(f"ตก {len(FAILURES)} จุด")
    for f in FAILURES:
        print("  -", f)
    raise SystemExit(1)
print("ผ่านทั้งหมด")
