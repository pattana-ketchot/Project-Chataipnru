"""
ทดสอบสองเรื่องที่แก้เมื่อ 2569-10-14 — รันในคอนเทนเนอร์ที่ต่อฐานจริง

    docker exec -w /app/backend -e PYTHONPATH=/app/backend <c> python tests/test_degree_level_and_gate_order.py

1. ระดับปริญญา — ห้ามตอบคนละระดับ และห้ามถอยไปใช้เล่มอื่นเมื่อไม่มีระดับที่ถาม
2. ลำดับด่าน — คำถามข้อเท็จจริงที่ฐานตอบได้ ต้องไม่เรียกโมเดลเลย ส่วนคำถามขอคำแนะนำ
   และคำถามผสมข้อเท็จจริง+คำแนะนำ ต้องยังไหลไปด่านขอคำแนะนำตามเดิม

**จำลองว่าโมเดลใช้ไม่ได้เลย** จึงพิสูจน์ได้ว่าข้อใดเรียกโมเดลและข้อใดไม่เรียก
"""
import sys
import time
import traceback

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import select, text

from app.db.session import SessionLocal
from app.models.chat import ChatSession
from app.models.course import Course
from app.services import chat as C
from app.services.course_scope import (degree_level_label, degree_levels_of, missing_degree_level,
                                       requested_degree_level, resolve_scope, resolve_scopes)
from app.services.structured_intent import detect
from app.services.web_compat import shared_user

from llm.connector import LLMConnectionError

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
        raise LLMConnectionError("จำลอง: โมเดลใช้ไม่ได้")

    def chat(self, *a, **k):
        return self._die("chat")

    def chat_stream(self, *a, **k):
        return self._die("chat_stream")

    def embed(self, *a, **k):
        return self._die("embed")


with SessionLocal() as db:
    USER_ID = shared_user(db).id
    probe = ChatSession(user_id=USER_ID)
    db.add(probe)
    db.commit()
    db.refresh(probe)
    SESSION_ID = probe.id
    TITLES = dict(db.execute(select(Course.id, Course.title)).all())

print(f"บทสนทนาทดสอบ {SESSION_ID}\n")


GAPS = []


def known_gap(label, still_broken, detail=""):
    """
    บันทึกช่องว่างที่รู้แล้วและพิสูจน์แล้วว่ามีมาก่อนการแก้ชุดนี้ (ยืนยันกับ image ของ
    production แล้วว่าได้ผลเหมือนกัน) นับแยกจากจุดตรวจ เพื่อไม่ให้ไปเพิ่มคะแนนผ่าน
    และไม่ให้ชุดทดสอบแดงด้วยเรื่องที่ไม่ได้อยู่ในขอบเขตการแก้รอบนี้

    ถ้าวันหนึ่งมีใครแก้จนหาย ข้อนี้จะบอกให้มาลบทิ้ง ไม่ปล่อยให้ค้างเงียบ
    """
    GAPS.append((label, still_broken))
    state = "ยังเป็นอยู่" if still_broken else "หายแล้ว -> ลบข้อนี้ออกได้"
    print(f"  [ช่องว่างที่รู้แล้ว/{state}] {label}" + (f" — {detail}" if detail else ""))


def prepare(message, prior=None):
    spy = DeadModel()
    real = C.get_llm_connector
    C.get_llm_connector = lambda: spy  # type: ignore[assignment]
    t0 = time.perf_counter()
    out = exc = None
    try:
        with SessionLocal() as db:
            try:
                out = C.prepare_answer(db, USER_ID, SESSION_ID, message, prior)
            finally:
                db.rollback()
    except Exception as e:  # noqa: BLE001
        exc = e
    finally:
        C.get_llm_connector = real  # type: ignore[assignment]
    return out, exc, spy.calls, time.perf_counter() - t0


AGRI = {
    "bachelor": ("หลักสูตรปริญญาตรีการจัดการเทคโนโลยีการเกษตรเรียนกี่หน่วยกิต", "130", "atm.pdf"),
    "master": ("หลักสูตรปริญญาโทการจัดการเทคโนโลยีการเกษตรเรียนกี่หน่วยกิต", "36", "agri68_master.pdf"),
    "doctoral": ("หลักสูตรปริญญาเอกการจัดการเทคโนโลยีการเกษตรเรียนกี่หน่วยกิต", "48", "agri68_phd.pdf"),
}

try:
    # ───────────── 1. ตัวกรองระดับปริญญาในระดับฟังก์ชัน ─────────────
    print("1. ตัวกรองระดับปริญญา")
    with SessionLocal() as db:
        for level, (q, _credits, _file) in AGRI.items():
            check(f"อ่านระดับจากคำถาม {level} ได้", requested_degree_level(q) == level,
                  str(requested_degree_level(q)))
            scopes = resolve_scopes(db, q)
            ids = [c for sc in scopes for c in sc.course_ids]
            levels = degree_levels_of(ids, TITLES)
            check(f"ขอบเขตของคำถาม {level} เหลือเฉพาะระดับนั้น", levels == {level},
                  f"ได้ {levels} จาก {[TITLES[i][:40] for i in ids]}")
        db.rollback()

    print()
    print("1.1 ระดับที่หลักสูตรนั้นไม่มี")
    with SessionLocal() as db:
        gap = missing_degree_level(db, "หลักสูตรปริญญาเอกวิทยาการคอมพิวเตอร์เรียนกี่หน่วยกิต")
        check("วิทยาการคอมพิวเตอร์ไม่มีปริญญาเอก -> ตรวจพบ", gap is not None, str(gap))
        if gap:
            check("บอกระดับที่ขอได้ถูก", gap[1] == "doctoral", str(gap))
            check("แปลงชื่อระดับเป็นภาษาไทยได้", degree_level_label(gap[1]) == "ปริญญาเอก",
                  degree_level_label(gap[1]))
        check("ระดับที่มีอยู่จริง -> ไม่ถือว่าขาด",
              missing_degree_level(db, AGRI["master"][0]) is None,
              str(missing_degree_level(db, AGRI["master"][0])))
        check("ไม่ระบุระดับ -> ไม่ถือว่าขาด",
              missing_degree_level(db, "การจัดการเทคโนโลยีการเกษตรเรียนกี่หน่วยกิต") is None)
        db.rollback()

    # ───────────── 2. คำตอบจริงของทั้งสามระดับ ─────────────
    print()
    print("2. ตอบให้ตรงระดับที่ถาม (จำลองโมเดลล่ม)")
    for level, (q, credits, src) in AGRI.items():
        p, exc, calls, secs = prepare(q)
        got = (p.canned or "") if p else ""
        other = [c for lv, (_q, c, _f) in AGRI.items() if lv != level]
        check(f"{level}: ตอบได้", p is not None and p.status == "answered", f"exc={exc!r}")
        check(f"{level}: มีหน่วยกิตที่ถูก ({credits})", credits in got, got[:90])
        check(f"{level}: ไม่มีหน่วยกิตของระดับอื่น ({', '.join(other)})",
              all(c not in got for c in other), got[:90])
        check(f"{level}: ที่มาเป็นไฟล์ที่ถูก ({src})",
              bool(p and any(src in (s.get("file") or "") for s in p.sources)),
              str(p.sources if p else None))
        check(f"{level}: ไม่เรียกโมเดลเลย", calls == [], f"เรียก {calls}")
        print(f"        {secs*1000:.0f} ms · {got.splitlines()[0][:76] if got else ''}")

    print()
    print("2.1 ระบุระดับที่ไม่มี -> ต้องบอกว่ายังไม่พบในข้อมูลของระบบ ไม่เดาเล่มอื่น")
    p, exc, calls, _s = prepare("หลักสูตรปริญญาเอกวิทยาการคอมพิวเตอร์เรียนกี่หน่วยกิต")
    got = (p.canned or "") if p else ""
    # ถ้อยคำเปลี่ยนเมื่อ 14 ต.ค. 2569 จาก "คณะ...ไม่มีหลักสูตร..." เป็น "ยังไม่พบ...
    # ในข้อมูลของระบบ" เพราะฐานนี้เก็บเฉพาะเล่มที่นำเข้าและตรวจรับแล้ว การสรุปแทน
    # มหาวิทยาลัยทั้งแห่งจากข้อมูลเท่านี้เป็นการพูดเกินกว่าที่ระบบรู้
    check("ตอบว่ายังไม่พบในข้อมูลของระบบ", "ยังไม่พบ" in got and "ข้อมูลของระบบ" in got, got[:120])
    check("ไม่สรุปแทนมหาวิทยาลัยว่าไม่มีหลักสูตรนั้น", "ไม่มีหลักสูตร" not in got, got[:120])
    check("บอกระดับที่ขอ", "ปริญญาเอก" in got, got[:110])
    check("ไม่หยิบหน่วยกิตของเล่มอื่นมาตอบ", "130" not in got, got[:110])
    check("ไม่เรียกโมเดล", calls == [], f"เรียก {calls}")

    print()
    print("2.2 ไม่ระบุระดับ แต่สาขานั้นมีหลายระดับ -> ต้องไม่เดาเล่มใดเล่มหนึ่ง")
    p, exc, calls, _s = prepare("การจัดการเทคโนโลยีการเกษตรเรียนกี่หน่วยกิต")
    got = (p.canned or "") if p else ""
    src = getattr(p, "served_source", None) if p else None
    print(f"      source={src} เรียกโมเดล={calls} คำตอบ={got[:80]!r}")
    if src == "structured":
        picked = [c for c in ("130", "36", "48") if c in got]
        check("ถ้าตอบจากฐาน ต้องไม่เลือกระดับเดียวแบบเงียบ ๆ", len(picked) != 1,
              f"ตอบเฉพาะ {picked}")
    else:
        check("ไม่ตอบจากฐานโดยเดาระดับ -> ไปเส้นทางอื่น", True, f"source={src}")

    # ───────────── 3. ลำดับด่าน ─────────────
    print()
    print("3. ลำดับด่าน — ข้อเท็จจริงต้องไม่เรียกโมเดล")
    for q in ("หลักสูตรวิทยาการคอมพิวเตอร์มีฉบับปีอะไรบ้าง",
              "วัตถุประสงค์ของหลักสูตรคณิตศาสตร์คืออะไร",
              "จบวิทยาการคอมพิวเตอร์แล้วทำงานอะไรได้บ้าง"):
        p, exc, calls, secs = prepare(q)
        check(f"{q[:34]} ตอบได้", p is not None and p.status == "answered", f"exc={exc!r}")
        check(f"{q[:34]} ไม่เรียกโมเดลเลย", calls == [], f"เรียก {calls}")
        check(f"{q[:34]} เร็วกว่า 2 วินาที", secs < 2.0, f"{secs:.2f}s")

    print()
    print("3.1 คำถามขอคำแนะนำ ต้องยังไหลไปด่านขอคำแนะนำ (ซึ่งเรียกโมเดล)")
    for q in ("อยากทำงานสายคอมพิวเตอร์ ควรเรียนสาขาไหนดี",
              "ชอบคณิตศาสตร์และการคำนวณ แนะนำสาขาให้หน่อย"):
        p, exc, calls, _s = prepare(q)
        check(f"{q[:34]} ไม่ถูกด่านฐานคว้าไปตอบ",
              p is None or p.served_source != "structured",
              f"source={getattr(p, 'served_source', None)}")
        check(f"{q[:34]} ไปถึงด่านที่เรียกโมเดล", bool(calls), f"เรียก {calls}")

    print()
    print("3.2 คำถามผสมข้อเท็จจริง+คำแนะนำ ต้องไม่ตอบแค่ข้อเท็จจริงแล้วทิ้งคำแนะนำ")
    for q in ("หลักสูตรวิทยาการคอมพิวเตอร์เรียนกี่หน่วยกิต และเหมาะกับคนชอบเขียนโปรแกรมไหม",
              "คณิตศาสตร์เรียนกี่หน่วยกิต ควรเรียนไหม"):
        p, exc, calls, _s = prepare(q)
        check(f"{q[:40]} ไม่ถูกด่านฐานคว้าไปตอบ",
              p is None or p.served_source != "structured",
              f"source={getattr(p, 'served_source', None)} canned={(p.canned or '')[:60] if p else None!r}")
        check(f"{q[:40]} ไปถึงด่านที่จัดการส่วนคำแนะนำ", bool(calls), f"เรียก {calls}")

    print()
    print("3.3 ตัวกรองคำขอคำแนะนำ (ไม่เรียกโมเดล ตรวจเฉพาะข้อความ)")
    for q, want in (("หลักสูตรคณิตศาสตร์เรียนกี่หน่วยกิต", False),
                    ("จบวิทคอมทำงานอะไรได้", False),
                    ("วัตถุประสงค์ของหลักสูตรคณิตศาสตร์คืออะไร", False),
                    ("ควรเรียนวิทคอมหรือไอทีดี", True),
                    ("สนใจงานด้านข้อมูล แนะนำสาขา", True),
                    ("วิทคอมเรียนกี่หน่วยกิต และเหมาะกับใคร", True)):
        check(f"_asks_for_advice({q[:30]}…) = {want}", C._asks_for_advice(q) is want,
              str(C._asks_for_advice(q)))

    # ───────────── 4. ของเดิมต้องไม่พัง ─────────────
    print()
    print("4. คำถามที่เคยผ่านต้องยังผ่าน")
    for q, must in (("หลักสูตรวิทยาการคอมพิวเตอร์ พ.ศ. 2561 ต้องเรียนทั้งหมดกี่หน่วยกิต", "130"),
                    ("หลักสูตรวิทยาการคอมพิวเตอร์ พ.ศ. 2566 ต้องเรียนทั้งหมดกี่หน่วยกิต", "130"),
                    ("หลักสูตรคณิตศาสตร์ต้องเรียนทั้งหมดกี่หน่วยกิต", "124"),
                    ("หลักสูตรเทคโนโลยีสารสนเทศ พ.ศ. 2566 เรียนกี่หน่วยกิต", "130"),
                    ("หลักสูตรเทคโนโลยีสารสนเทศ พ.ศ. 2561 เรียนกี่หน่วยกิต", "127")):
        p, exc, calls, secs = prepare(q)
        got = (p.canned or "") if p else ""
        check(f"{q[:40]} ยังตอบได้", must in got, f"{got[:80]} exc={exc!r}")
        check(f"{q[:40]} ยังมีคำว่าไม่น้อยกว่า", "ไม่น้อยกว่า" in got, got[:80])
        check(f"{q[:40]} ยังไม่เรียกโมเดล", calls == [], f"เรียก {calls}")

    print()
    print("4.1 คำถามต่อเนื่องและคำอ้างอิงต้องยังทำงาน")
    prior = [
        C.PriorTurn(role="user", content="หลักสูตรวิทยาการคอมพิวเตอร์ พ.ศ. 2561 ต้องเรียนทั้งหมดกี่หน่วยกิต"),
        C.PriorTurn(role="assistant", content="… (พ.ศ. 2561) … ไม่น้อยกว่า 130 หน่วยกิต"),
    ]
    p, exc, calls, _s = prepare("แล้วปี 2566 ล่ะ", prior)
    got = (p.canned or "") if p else ""
    check("คำถามต่อเนื่องยังตอบเป็นฉบับ 2566", "2566" in got, got[:90])
    check("คำถามต่อเนื่องไม่ตอบเป็นฉบับ 2561", "2561" not in got, got[:90])
    p, exc, calls, _s = prepare("สาขานี้เรียนกี่หน่วยกิต", prior)
    got = (p.canned or "") if p else ""
    check('"สาขานี้" ยังตอบถึงฉบับ 2561', "2561" in got, got[:110])
    # เคยเป็นช่องว่างที่รู้แล้ว (บันทึกไว้ 13 ต.ค. 2569): คำตอบลากฉบับ 2566 เข้ามาด้วย
    # เพราะ _context_programme คืนเฉพาะ "ชื่อสาขา" ไม่เก็บปีที่กำลังคุย
    # แก้แล้วเมื่อ 14 ต.ค. 2569 ด้วย _context_edition() ซึ่งพาปีและระดับปริญญาจาก
    # บทสนทนาไปด้วย จึงเลื่อนขึ้นเป็นข้อตรวจเต็มตัว
    check('"สาขานี้" ไม่ลากฉบับ 2566 เข้ามาด้วย', "2566" not in got, got[:110])

    print()
    print("4.2 ด่านอื่นต้องยังมาก่อนด่านฐานข้อมูล")
    p, _e, calls, _s = prepare("สวัสดีครับ")
    check("คำทักทายยังเข้าด่านทักทาย", p is not None and p.status == "small_talk",
          str(getattr(p, "status", None)))
    p, _e, calls, _s = prepare("ค่าเทอมสาขาวิทยาการคอมพิวเตอร์เท่าไหร่")
    got = (p.canned or "") if p else ""
    check("คำถามค่าเทอมยังเข้าด่านค่าเทอม ไม่ใช่ด่านฐานหน่วยกิต",
          p is not None and "หน่วยกิต" not in got, got[:80])
    p, _e, calls, _s = prepare("คณะวิทยาศาสตร์และเทคโนโลยีเปิดสอนสาขาอะไรบ้าง")
    got = (p.canned or "") if p else ""
    check("คำถามรายชื่อหลักสูตรยังเข้าด่านรายการ",
          "วิทยาการคอมพิวเตอร์" in got and "คณิตศาสตร์" in got, got[:80])

finally:
    print()
    print("บทสนทนาทดสอบที่ต้องเก็บกวาดด้วยสิทธิ์ผู้ดูแลฐานข้อมูล:")
    print(f"  delete from chat_sessions where id = '{SESSION_ID}'")

print()
print(f"จุดตรวจ {CHECKS} จุด")
if GAPS:
    print(f"ช่องว่างที่รู้แล้ว {len(GAPS)} ข้อ (นับแยก ไม่รวมในจุดตรวจ ยืนยันแล้วว่ามีใน production เดิม)")
    for _label, _still in GAPS:
        print(f"  - {_label}" + ("" if _still else "  <- หายแล้ว ลบข้อตรวจนี้ออกได้"))
if FAILURES:
    print(f"ตก {len(FAILURES)} จุด")
    for f in FAILURES:
        print("  -", f)
    raise SystemExit(1)
print("ผ่านทั้งหมด")
