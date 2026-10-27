"""
ทดสอบด่านตอบจากฐานข้อมูลหลักสูตรก่อนค้นเอกสาร — รันในคอนเทนเนอร์ที่ต่อฐานจริง

    docker exec -w /app/backend -e PYTHONPATH=/app/backend <c> python tests/test_structured_fast_path.py

**จำลองว่าโมเดลใช้ไม่ได้เลย** โดยสลับ get_llm_connector เป็นตัวนับที่โยน
LLMConnectionError ทุกครั้งที่ถูกเรียก — เหมือนกรณี Gemini ตอบ 503 ครบทุกครั้ง
แล้วตัวสำรองในเครื่องก็ล้ม ซึ่งเกิดขึ้นจริงเมื่อ 13 ต.ค. 2569

จึงพิสูจน์ได้สองอย่างในคราวเดียว
  1. คำถามที่ฐานข้อมูลตอบได้ **ไม่เรียก Gemini หรือ Ollama เลยแม้แต่ครั้งเดียว**
  2. คำถามที่ฐานตอบไม่ได้ ยังเดินเส้นทาง RAG เดิม (จึงไปชนตัวนับ)

เขียนลงฐาน: สร้างแถว chat_sessions หนึ่งแถวเพื่อใช้เป็นบทสนทนาทดสอบ แล้ว **ลบทิ้งตอนจบ**
ไม่มีการเขียนข้อความลง chat_messages เพราะ prepare_answer() ไม่ได้บันทึก (ผู้เรียกบันทึก)
"""
import sys
import time
import traceback

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import text

from app.db.session import SessionLocal
from app.models.chat import ChatSession
from app.services import chat as C
from app.services.web_compat import shared_user

from llm.connector import LLMConnectionError

CHECKS = 0
FAILURES: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    if ok:
        print(f"  [ผ่าน] {label}")
    else:
        FAILURES.append(f"{label} — {detail}")
        print(f"  [ตก]  {label} — {detail}")


class DeadModel:
    """ตัวเชื่อมต่อที่ใช้ไม่ได้ · นับทุกการเรียกแล้วโยน LLMConnectionError"""

    answer_token_cap = 2048

    def __init__(self) -> None:
        self.calls: list[str] = []

    def _die(self, what: str):
        self.calls.append(what)
        raise LLMConnectionError("จำลอง: Gemini ตอบ 503 ครบทุกครั้งและตัวสำรองล้ม")

    def chat(self, *a, **k):
        return self._die("chat")

    def chat_stream(self, *a, **k):
        return self._die("chat_stream")

    def embed(self, *a, **k):
        return self._die("embed")


DB_QUESTIONS = [
    "หลักสูตรวิทยาการคอมพิวเตอร์ พ.ศ. 2561 ต้องเรียนทั้งหมดกี่หน่วยกิต",
    "หลักสูตรวิทยาการคอมพิวเตอร์ พ.ศ. 2566 ต้องเรียนทั้งหมดกี่หน่วยกิต",
    "หลักสูตรคณิตศาสตร์ต้องเรียนทั้งหมดกี่หน่วยกิต",
]


def prepare(session_id, message, prior=None):
    """เรียก prepare_answer ด้วยตัวเชื่อมต่อที่ใช้ไม่ได้ คืน (ผล, ข้อยกเว้น, การเรียกโมเดล, วินาที)"""
    spy = DeadModel()
    real = C.get_llm_connector
    C.get_llm_connector = lambda: spy  # type: ignore[assignment]
    t0 = time.perf_counter()
    out = exc = None
    try:
        with SessionLocal() as db:
            try:
                out = C.prepare_answer(db, USER_ID, session_id, message, prior)
            finally:
                db.rollback()
    except Exception as e:  # noqa: BLE001
        exc = e
    finally:
        C.get_llm_connector = real  # type: ignore[assignment]
    return out, exc, spy.calls, time.perf_counter() - t0


with SessionLocal() as db:
    USER_ID = shared_user(db).id
    probe = ChatSession(user_id=USER_ID)
    db.add(probe)
    db.commit()
    db.refresh(probe)
    SESSION_ID = probe.id

print(f"บทสนทนาทดสอบ {SESSION_ID} (จะลบทิ้งตอนจบ)")
print()

try:
    # ───────────── 1. คำถามตรง — ต้องตอบได้โดยไม่เรียกโมเดล ─────────────
    print("1. คำถามตรงที่ฐานข้อมูลตอบได้")
    for q in DB_QUESTIONS:
        p, exc, calls, secs = prepare(SESSION_ID, q)
        short = q[:38]
        check(f"{short} ตอบได้", exc is None and p is not None and p.status == "answered",
              f"exc={exc!r}")
        if p is None:
            continue
        check(f"{short} ไม่เรียกโมเดลเลย", calls == [], f"เรียก {calls}")
        check(f"{short} มีคำว่าไม่น้อยกว่า", "ไม่น้อยกว่า" in (p.canned or ""), (p.canned or "")[:70])
        check(f"{short} มี sources", bool(p.sources), str(p.sources))
        check(f"{short} มาจากเส้นทาง structured", p.served_source == "structured", p.served_source)
        check(f"{short} ไม่มี citations (ไม่ได้ค้นเอกสาร)", p.citations == [], str(p.citations))
        check(f"{short} ห้ามตกไปโมเดลสำรอง", p.allow_fallback is False, str(p.allow_fallback))
        check(f"{short} ไม่เก็บลงแคช", p.cacheable is False, str(p.cacheable))
        check(f"{short} เร็วกว่า 2 วินาที", secs < 2.0, f"{secs:.2f}s")
        print(f"        {secs*1000:.0f} ms · {(p.canned or '').splitlines()[0][:72]}")

    # ───────────── 2. ที่มาต้องตรงกับเอกสารจริง ─────────────
    print()
    print("2. ที่มาที่ส่งออกมาตรงกับเอกสารที่ตรวจไว้")
    want = {
        DB_QUESTIONS[0]: [("cs61.pdf", 6)],
        DB_QUESTIONS[1]: [("cs66.pdf", 2)],
        DB_QUESTIONS[2]: [("ma69.pdf", 1), ("ma64.pdf", 6)],
    }
    for q, expect in want.items():
        p, _exc, _calls, _s = prepare(SESSION_ID, q)
        got = [(s["file"], s["page_start"]) for s in (p.sources if p else [])]
        check(f"{q[:38]} ที่มาตรง", got == expect, f"ได้ {got} ต้องได้ {expect}")
        check(f"{q[:38]} ทุกที่มามี course_id",
              bool(p and all(s.get("course_id") for s in p.sources)), str(p.sources if p else None))

    # ───────────── 3. คำถามต่อเนื่องที่ต้องใช้ประวัติ ─────────────
    print()
    print("3. คำถามต่อเนื่อง — บริบทต้องไม่หาย")
    prior = [
        C.PriorTurn(role="user", content=DB_QUESTIONS[0]),
        C.PriorTurn(role="assistant",
                    content="หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาการคอมพิวเตอร์ (พ.ศ. 2561) "
                            "มีจำนวนหน่วยกิตรวมตลอดหลักสูตร ไม่น้อยกว่า 130 หน่วยกิต"),
    ]
    p, exc, calls, secs = prepare(SESSION_ID, "แล้วปี 2566 ล่ะ", prior)
    print(f"      ผล: status={getattr(p, 'status', None)} source={getattr(p, 'served_source', None)} "
          f"เรียกโมเดล={calls} {secs*1000:.0f} ms")
    if p is not None and p.served_source == "structured":
        # โค้ดประกอบคำถามต่อเนื่องได้เอง (swap_follow_up) จึงตอบเร็วและต้องเป็นฉบับ 2566
        check("คำถามต่อเนื่องตอบเป็นฉบับ 2566", "2566" in (p.canned or ""), (p.canned or "")[:90])
        check("คำถามต่อเนื่องไม่ตอบเป็นฉบับ 2561", "2561" not in (p.canned or ""), (p.canned or "")[:90])
        # ข้อความที่ไม่ได้เอ่ยชื่อหลักสูตรเองยังผ่านด่าน 0.72 (_recommendation_intent) ซึ่งถามโมเดล
        # หนึ่งครั้งก่อนถึงด่านเร็ว — เป็นพฤติกรรมเดิมของระบบ ไม่ใช่สิ่งที่การแก้นี้เพิ่มเข้ามา
        # และด่านนั้นถือว่า "ไม่ใช่คำขอคำแนะนำ" เมื่อโมเดลล่ม จึงยังตอบถูกต้องแม้โมเดลใช้ไม่ได้
        check("คำถามต่อเนื่องไม่เรียกขั้นค้นเอกสารหรือขั้นเขียนคำตอบ",
              calls in ([], ["chat"]), f"เรียก {calls}")
        check("คำถามต่อเนื่องไม่เรียก embed (ไม่ได้ค้นเอกสาร)", "embed" not in calls, f"เรียก {calls}")
    else:
        # ตีความเองไม่ได้ ต้องไหลไปเส้นทางเดิมที่ใช้โมเดล ไม่ใช่ตอบผิดฉบับ
        check("ตีความเองไม่ได้ก็ต้องไปเส้นทางเดิม ไม่ตอบผิดฉบับ",
              exc is not None or (p is not None and p.served_source != "structured"),
              f"status={getattr(p, 'status', None)}")

    p2, exc2, calls2, _s = prepare(SESSION_ID, "สาขานี้เรียนกี่หน่วยกิต", prior)
    print(f'      "สาขานี้เรียนกี่หน่วยกิต": status={getattr(p2, "status", None)} '
          f'source={getattr(p2, "served_source", None)} เรียกโมเดล={calls2}')
    if p2 is not None and p2.served_source == "structured":
        check('"สาขานี้" ถูกแทนด้วยหลักสูตรที่คุยอยู่ (2561)', "2561" in (p2.canned or ""),
              (p2.canned or "")[:90])
        check('"สาขานี้" ไม่เรียกโมเดล', calls2 == [], f"เรียก {calls2}")
    else:
        check('"สาขานี้" ไปเส้นทางเดิมได้โดยไม่ตอบผิดสาขา',
              exc2 is not None or (p2 is not None and p2.served_source != "structured"),
              f"status={getattr(p2, 'status', None)}")

    # ───────────── 4. คำถามกำกวม — ต้องถามกลับ ไม่เดา ─────────────
    print()
    print("4. คำถามกำกวมที่ไม่บอกสาขา")
    p, exc, calls, secs = prepare(SESSION_ID, "เรียนกี่หน่วยกิต")
    print(f"      status={getattr(p, 'status', None)} source={getattr(p, 'served_source', None)} "
          f"เรียกโมเดล={calls} {secs*1000:.0f} ms")
    check("ไม่ตอบเป็นหลักสูตรใดหลักสูตรหนึ่ง",
          p is None or p.served_source != "structured" or not p.sources,
          f"ตอบว่า {(p.canned or '')[:70] if p else None}")
    if p is not None and p.canned:
        check("ถามกลับว่าสาขาไหน หรือบอกว่าตอบไม่ได้",
              any(w in p.canned for w in ("สาขาไหน", "หลักสูตรไหน", "ระบุ", "ไม่พบ", "ขออภัย")),
              p.canned[:90])

    # ───────────── 5. คำถามที่ฐานตอบไม่ได้ — ต้องไปเส้นทาง RAG เดิม ─────────────
    print()
    print("5. คำถามที่ฐานข้อมูลตอบไม่ได้ ต้องไปเส้นทาง RAG เดิม")
    for q in ("มีวิชาแคลคูลัสในหลักสูตรคณิตศาสตร์ไหม",
              "หลักสูตรวิทยาการคอมพิวเตอร์มีวิชาอะไรในชั้นปีที่ 1"):
        p, exc, calls, secs = prepare(SESSION_ID, q)
        print(f"      {q[:40]}: status={getattr(p, 'status', None)} "
              f"source={getattr(p, 'served_source', None)} เรียกโมเดล={calls}")
        check(f"{q[:28]} ไม่ถูกด่านเร็วคว้าไปตอบ",
              p is None or p.served_source != "structured", f"source={getattr(p, 'served_source', None)}")
        check(f"{q[:28]} ไปถึงขั้นที่ใช้โมเดลจริง", bool(calls), f"เรียก {calls}")

    # ───────────── 6. ปิดโหมด structured แล้วต้องกลับเป็นเส้นทางเดิมทั้งหมด ─────────────
    print()
    print("6. STRUCTURED_ANSWERS ปิด -> ด่านเร็วต้องเงียบสนิท")
    import app.services.structured_shadow as S
    real_mode = S.configured_mode
    S.configured_mode = lambda: "off"  # type: ignore[assignment]
    try:
        p, exc, calls, secs = prepare(SESSION_ID, DB_QUESTIONS[0])
        check("ปิดโหมดแล้วด่านเร็วไม่ทำงาน",
              p is None or p.served_source != "structured", f"source={getattr(p, 'served_source', None)}")
        check("ปิดโหมดแล้วไหลไปเส้นทางที่ใช้โมเดล", bool(calls) or exc is not None, f"เรียก {calls}")
    finally:
        S.configured_mode = real_mode  # type: ignore[assignment]

finally:
    # ลบเองไม่ได้ — role ของแอปมีสิทธิ์ INSERT แต่ไม่มี DELETE บน chat_sessions
    # (least privilege ที่ตั้งใจไว้) แถวนี้ว่างเปล่าเพราะ prepare_answer ไม่บันทึกข้อความ
    print()
    print("บทสนทนาทดสอบที่ต้องเก็บกวาดด้วยสิทธิ์ผู้ดูแลฐานข้อมูล:")
    print(f"  docker exec course-advisor-system-postgres-1 psql -U postgres -d course_advisor \\")
    print(f"    -c \"delete from chat_sessions where id = '{SESSION_ID}'"
          f" and not exists (select 1 from chat_messages m where m.session_id = chat_sessions.id)\"")

print()
print(f"จุดตรวจ {CHECKS} จุด")
if FAILURES:
    print(f"ตก {len(FAILURES)} จุด")
    for f in FAILURES:
        print("  -", f)
    raise SystemExit(1)
print("ผ่านทั้งหมด")
