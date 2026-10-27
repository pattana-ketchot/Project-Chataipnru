"""
ตอบคำถามรายวิชาจากข้อมูลที่ตรวจรับแล้ว — ผ่าน /chat-web และ /chat จริง

    # ต้องชี้ DATABASE_URL ไปฐานที่รัน migration 002 และเผยแพร่ข้อมูลรายวิชาแล้ว
    cd backend && DATABASE_URL=...course_advisor_test python tests/test_subjects_from_db.py

ครอบ
    - รหัส/ชื่อวิชา หน่วยกิต และข้อกำหนด (required / elective / choose_group)
    - วิชาบังคับก่อน และการแยก "เอกสารไม่ได้ระบุ" ออกจาก "ข้อมูลยังไม่ครบ"
    - รายการวิชาบังคับต้องไม่นับวิชาในกลุ่มที่ต้องเลือกว่าเป็นวิชาบังคับ
    - หลักสูตรที่ยังไม่มีข้อมูลรายวิชา ต้องไม่สรุปว่าไม่มีรายวิชา
    - คำถามต่อเนื่อง และกรณีโมเดลใช้ไม่ได้
    - `/chat` พร้อมเข้าสู่ระบบด้วย bearer token และตรวจช่อง sources

**ไม่สร้างบัญชีและไม่แตะรหัสผ่าน** — ออก access token ให้ผู้ใช้ที่มีอยู่แล้วในฐานด้วย
โมดูล security ของแอปเอง จึงผ่านด่าน get_current_user จริงโดยไม่ต้องใช้รหัสผ่านใคร
"""
import logging
import os
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

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select, text  # noqa: E402

from app.core.security import create_access_token  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services import chat as C  # noqa: E402
from app.services import llm_client  # noqa: E402
from app.main import app  # noqa: E402

C.cache_lookup = lambda db, q, v: None          # ปิดแคชทุกรอบของชุดนี้
C.cache_store = lambda *a, **k: None
DEAD = DeadModel()
llm_client._connector = DEAD
CLIENT = TestClient(app)
SENT: list[float] = []

with SessionLocal() as db:
    dbname = db.execute(text("SELECT current_database()")).scalar_one()
    n_subj = db.execute(text("SELECT count(*) FROM mko.v_live_subjects")).scalar_one()
    n_pre = db.execute(text("SELECT count(*) FROM mko.v_live_subject_prerequisites")).scalar_one()
    user_id = db.scalars(select(User.id).limit(1)).first()
    db.rollback()

print(f"ฐานข้อมูล: {dbname} · รายวิชาในวิวที่ระบบอ่าน {n_subj} แถว · วิชาบังคับก่อน {n_pre} แถว")
check("ไม่ใช่ฐาน production", dbname != "course_advisor", f"ต่ออยู่กับ {dbname}")
check("ฐานนี้มีข้อมูลรายวิชาให้ทดสอบ", n_subj > 0, f"{n_subj} แถว")
print()


def web(message, prior=None):
    while True:
        SENT[:] = [t for t in SENT if time.monotonic() - t < 60.0]
        if len(SENT) < 17:
            break
        time.sleep(60.0 - (time.monotonic() - SENT[0]) + 0.3)
    SENT.append(time.monotonic())
    before = len(DEAD.calls)
    msgs = list(prior or []) + [{"role": "user", "content": message}]
    t0 = time.perf_counter()
    r = CLIENT.post("/chat-web", json={"messages": msgs})
    return r.text.strip(), DEAD.calls[before:], time.perf_counter() - t0


# ---------------------------------------------------------------- 1
print("1. ถามด้วยรหัสวิชา (r1-03)")
got, calls, took = web("วิชา 4121202 ชื่อว่าอะไร")
check("ได้ชื่อวิชาถูกต้อง", "การเขียนโปรแกรมภาษาคอมพิวเตอร์" in got, got[:150])
check("บอกหน่วยกิต", "3 หน่วยกิต" in got, got[:150])
check("บอกข้อกำหนดว่าเป็นวิชาบังคับ", "วิชาบังคับ" in got, got[:200])
check("อ้างที่มาเป็นไฟล์และหน้า", "cs66.pdf หน้า 16" in got, got[-120:])
check("ไม่เรียกโมเดล", calls == [], f"เรียก {calls}")
check("ตอบเร็วกว่า 5 วินาที", took <= 5.0, f"{took:.2f}s")

# ---------------------------------------------------------------- 2
print()
print("2. วิชาบังคับก่อน")
got, calls, _t = web("วิชาระบบฐานข้อมูลของวิทยาการคอมพิวเตอร์มีวิชาบังคับก่อนไหม")
check("อ้างรหัสวิชาที่ถาม (r1-04 ต้องมี 4122204)", "4122204" in got, got[:200])
check("บอกว่าเอกสารที่ตรวจแล้วไม่ได้ระบุ",
      "เอกสารที่ตรวจแล้วไม่ได้ระบุวิชาบังคับก่อนของวิชานี้" in got, got[:300])
check("อ้างหน้าคำอธิบายของวิชานี้เองเป็นหลักฐานการตรวจ (หน้า 39)",
      "หน้า 39" in got, got[:300])
check("ไม่สรุปว่าข้อมูลยังไม่ครบ (เพราะมีหลักฐานว่าตรวจวิชานี้แล้ว)",
      "ยังสรุปไม่ได้" not in got, got[:300])
check("**ไม่อ้างจำนวนแถวของวิชาอื่นเป็นหลักฐาน**",
      "รายการ แต่ไม่มีรายการของวิชานี้" not in got, got[:300])
check("ไม่เรียกโมเดล", calls == [], f"เรียก {calls}")

got, calls, _t = web("วิชา 4121204 มีวิชาบังคับก่อนอะไร")
check("วิชาที่มีบังคับก่อนจริง ตอบรหัสที่ต้องเรียนมาก่อน", "4121202" in got, got[:200])
check("บอกชื่อวิชาที่ต้องเรียนมาก่อน",
      "การเขียนโปรแกรมภาษาคอมพิวเตอร์ 1" in got, got[:240])
check("อ้างที่มาหน้าคำอธิบายรายวิชา", "หน้า 40" in got, got[-140:])
check("ไม่เรียกโมเดล", calls == [], f"เรียก {calls}")

print()
print("2.1 นำเข้าวิชาบังคับก่อนเพียงบางรายการ — วิชาที่ยังไม่ได้ตรวจต้องไม่ถูกสรุปว่า")
print("    'เอกสารไม่ได้ระบุ' · ข้อมูลจริงของ cs66.pdf เป็นการนำเข้าบางส่วนอยู่แล้ว")
print("    (ตรวจคำอธิบายได้ 49 จาก 82 วิชา — ที่เหลือไม่มีคำอธิบายในเล่มนี้)")
with SessionLocal() as db2:
    stat = db2.execute(text("""
        SELECT count(*) FILTER (WHERE prereq_checked_page IS NOT NULL) AS checked,
               count(*) FILTER (WHERE prereq_checked_page IS NULL) AS unchecked
          FROM mko.v_live_subjects
    """)).mappings().one()
    db2.rollback()
check("ฐานทดสอบอยู่ในสภาพ 'นำเข้าบางส่วน' จริง",
      stat["checked"] > 0 and stat["unchecked"] > 0,
      f"ตรวจแล้ว {stat['checked']} · ยังไม่ตรวจ {stat['unchecked']}")

# วิชาศึกษาทั่วไปที่ไม่มีคำอธิบายในเล่มนี้
got, calls, _t = web("วิชา 0010102 มีวิชาบังคับก่อนไหม")
check("วิชาที่ยังไม่ได้ตรวจ -> บอกว่ายังสรุปไม่ได้",
      "ยังสรุปไม่ได้" in got, got[:300])
check("บอกว่ายังไม่มีหลักฐานว่าตรวจคำอธิบายของวิชานี้",
      "ยังไม่มีหลักฐานว่าได้ตรวจคำอธิบายรายวิชาของวิชานี้" in got, got[:300])
check("**ไม่สรุปว่าเอกสารไม่ได้ระบุ**",
      "เอกสารที่ตรวจแล้วไม่ได้ระบุ" not in got, got[:300])
check("ไม่เรียกโมเดล", calls == [], f"เรียก {calls}")

# วิชาของคณะที่ปรากฏเฉพาะในหน้ารายการ ไม่มีคำอธิบายในเล่ม
got, calls, _t = web("วิชา 4124509 มีวิชาบังคับก่อนไหม")
check("วิชาของคณะที่ไม่มีคำอธิบายในเล่ม -> ยังสรุปไม่ได้",
      "ยังสรุปไม่ได้" in got, got[:300])
check("**ไม่สรุปว่าเอกสารไม่ได้ระบุ**",
      "เอกสารที่ตรวจแล้วไม่ได้ระบุ" not in got, got[:300])
check("ยังตอบชื่อวิชาได้ตามปกติ", "สารสนเทศควอนตัม" in got, got[:140])
check("ไม่เรียกโมเดล", calls == [], f"เรียก {calls}")

# ---------------------------------------------------------------- 3
print()
print("3. รายการวิชาบังคับ (r1-01) — ต้องไม่นับวิชาในกลุ่มที่ต้องเลือกว่าเป็นวิชาบังคับ")
got, calls, took = web("หลักสูตรวิทยาการคอมพิวเตอร์ พ.ศ. 2566 มีวิชาบังคับอะไรบ้าง")
check("มีคำว่ากลุ่มวิชาบังคับ (ตามเกณฑ์ r1-01)", "กลุ่มวิชาบังคับ" in got, got[:160])
check("อ้างฉบับ 2566", "2566" in got, got[:160])
check("ไม่ลากฉบับ 2561 เข้ามา", "2561" not in got, got[:160])
check("ไม่พูดถึงวิชาบังคับก่อน (ตามเกณฑ์ r1-01)", "วิชาบังคับก่อน" not in got, got[:400])
check("มีกลุ่มวิชาแกนและกลุ่มวิชาเฉพาะด้าน",
      "กลุ่มวิชาแกน" in got and "กลุ่มวิชาเฉพาะด้าน" in got, got[:300])
# ท้ายรายการต้องบอกให้ครบสามอย่าง: ยอดข้างบนไม่รวมกลุ่มไหน · วิชาใดในกลุ่มนั้นต้องเรียน
# · และวิชาใดเป็นตัวเลือก — เดิมบอกรวมเป็นประโยคเดียวว่า "ไม่ใช่วิชาที่ต้องเรียนทุกวิชา"
# ซึ่งอ่านแล้วเข้าใจว่าทั้งกลุ่มเป็นของให้เลือก (19 ต.ค. 2569: 4124813 ต้องเรียนจริง)
check("บอกว่ายอดข้างบนไม่รวมกลุ่มที่เล่มนับแยก",
      "ยอดข้างบนไม่รวม" in got and "กลุ่มวิชาฝึกประสบการณ์วิชาชีพหรือสหกิจศึกษา" in got,
      got[-420:])
check("ระบุวิชาที่ต้องเรียนในกลุ่มนั้นพร้อมวงเล็บกำกับ",
      "4124813" in got and "(ต้องเรียน)" in got, got[-420:])
check("ระบุวิชาที่เป็นตัวเลือกแยกจากวิชาที่ต้องเรียน",
      "เลือกจาก:" in got and "4124814" in got and "4124815" in got, got[-420:])
check("ไม่เอาวิชาฝึกประสบการณ์มานับเป็นวิชาบังคับ",
      "รวมวิชาบังคับ 35 วิชา" in got, got[-400:])
check("อ้างที่มา", "cs66.pdf" in got, got[-160:])
check("ไม่เรียกโมเดล", calls == [], f"เรียก {calls}")
check("ตอบเร็วกว่า 5 วินาที", took <= 5.0, f"{took:.2f}s")

print()
print("3.1 รายการวิชาเลือก")
got, calls, _t = web("หลักสูตรวิทยาการคอมพิวเตอร์ พ.ศ. 2566 มีวิชาเลือกอะไรบ้าง")
check("บอกว่าเป็นวิชาเลือก", "วิชาเลือก" in got, got[:140])
check("มีจำนวนรวม", "รวมวิชาเลือก" in got, got[-240:])
check("ไม่เรียกโมเดล", calls == [], f"เรียก {calls}")

print()
print("3.2 วิชาในกลุ่มที่ต้องเลือก (choose_group) ต้องไม่ถูกเรียกว่าวิชาบังคับ")
got, calls, _t = web("วิชา 4124814 ชื่อว่าอะไร")
check("ได้ชื่อวิชา", "ฝึกประสบการณ์วิชาชีพ" in got, got[:160])
check("ข้อกำหนดบอกว่าเป็นวิชาในกลุ่มที่ต้องเลือก",
      "กลุ่มที่ต้องเลือกให้ครบหน่วยกิตขั้นต่ำ" in got, got[:240])
check("ไม่เรียกว่าวิชาบังคับ", "· วิชาบังคับ" not in got, got[:240])
check("ไม่เรียกโมเดล", calls == [], f"เรียก {calls}")

# ---------------------------------------------------------------- 4
print()
print("4. หลักสูตรที่ยังไม่มีข้อมูลรายวิชา — ห้ามสรุปว่าไม่มีรายวิชา")
got, calls, _t = web("หลักสูตรคณิตศาสตร์ พ.ศ. 2564 มีวิชาบังคับอะไรบ้าง")
check("ไม่ตอบรายการวิชาจากฐาน (ไม่มีข้อมูลของหลักสูตรนี้)",
      "กลุ่มวิชาแกน" not in got, got[:160])
check("ไม่สรุปว่าหลักสูตรนี้ไม่มีรายวิชา",
      "ไม่มีวิชา" not in got and "ไม่มีรายวิชา" not in got, got[:200])
check("ไหลไปเส้นทางเอกสารตามเดิม (เรียกโมเดล)", calls != [], f"เรียก {calls}")

print()
print("4.1 รหัสวิชาที่ไม่มีในข้อมูล — ต้องใช้ถ้อยคำ ยังไม่พบในข้อมูลของระบบ")
got, calls, _t = web("วิชา 9999999 ชื่อว่าอะไร")
check("บอกว่ายังไม่พบในข้อมูลของระบบ",
      "ยังไม่พบรายวิชารหัส 9999999 ในข้อมูลของระบบ" in got, got[:200])
check("ไม่สรุปแทนคณะว่าไม่มีวิชานี้", "ไม่มีวิชา" not in got, got[:200])
check("ไม่เรียกโมเดล", calls == [], f"เรียก {calls}")

# ---------------------------------------------------------------- 5
print()
print("5. คำถามต่อเนื่อง")
PRIOR = [
    {"role": "user", "content": "หลักสูตรวิทยาการคอมพิวเตอร์ พ.ศ. 2566 ต้องเรียนกี่หน่วยกิต"},
    {"role": "assistant", "content": "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาการคอมพิวเตอร์ "
                                     "(พ.ศ. 2566) มีจำนวนหน่วยกิตรวมตลอดหลักสูตร "
                                     "ไม่น้อยกว่า 130 หน่วยกิต\nที่มา: cs66.pdf หน้า 2"},
]
got, calls, _t = web("สาขานี้มีวิชาบังคับอะไรบ้าง", PRIOR)
check("คำถามต่อเนื่องได้รายการวิชาบังคับของหลักสูตรที่คุยอยู่",
      "กลุ่มวิชาบังคับ" in got and "2566" in got, got[:200])
check("ไม่เรียกโมเดล", calls == [], f"เรียก {calls}")

# ---------------------------------------------------------------- 6
print()
print("6. a1-04 — คำถามเทียบที่อีกฝั่งยังไม่มีในข้อมูล")
for q in ("คณิตศาสตร์ กับ คณิตศาสตร์ประยุกต์ ต่างกันไหม",
          "วิทคอม กับ คณิตศาสตร์ประยุกต์ ต่างกันไหม",
          "เทียบคณิตศาสตร์ประยุกต์ กับ คณิตศาสตร์"):
    got, calls, _t = web(q)
    check(f"{q[:38]} -> บอกว่ายังไม่พบในข้อมูลของระบบ",
          "ยังไม่พบหลักสูตรคณิตศาสตร์ประยุกต์ ในข้อมูลของระบบ" in got, got[:170])
    check("   ไม่สรุปแทนมหาวิทยาลัย", "ไม่มีหลักสูตร" not in got, got[:170])
    check("   ไม่เรียกโมเดล", calls == [], f"เรียก {calls}")

print()
print("6.1 ชื่อที่มีคำร่วมกันต้องไม่ถูกจับผิด")
got, calls, _t = web("คณิตศาสตร์กับวิทยาการคอมพิวเตอร์ หน่วยกิตต่างกันไหม")
check("ยังตอบเทียบสองหลักสูตรตามปกติ", "เทียบจำนวนหน่วยกิต" in got, got[:140])
check("ไม่บอกว่ายังไม่พบหลักสูตร", "ยังไม่พบหลักสูตร" not in got, got[:140])
got, calls, _t = web("หลักสูตรวิทยาการคอมพิวเตอร์ฉบับ 2561 กับ 2566 หน่วยกิตต่างกันไหม")
check("เทียบสองฉบับยังทำงาน", "เท่ากัน" in got, got[-200:])
check("ไม่บอกว่ายังไม่พบหลักสูตร", "ยังไม่พบหลักสูตร" not in got, got[:140])
got, calls, _t = web("หลักสูตรวิทยาการคอมพิวเตอร์มีวิชาบังคับอะไรบ้าง")
check("คำถามที่ไม่ใช่การเทียบไม่ถูกด่านนี้แตะ", "ยังไม่พบหลักสูตร" not in got, got[:140])

# ---------------------------------------------------------------- 7
print()
print("7. /chat พร้อมเข้าสู่ระบบ (bearer token) และช่อง sources")
token = create_access_token(str(user_id))
r = CLIENT.post("/chat", json={"message": "วิชา 4121202 ชื่อว่าอะไร"})
check("ไม่มี token -> 401", r.status_code == 401, f"ได้ {r.status_code}")
before = len(DEAD.calls)
r = CLIENT.post("/chat", json={"message": "วิชา 4121202 ชื่อว่าอะไร"},
                headers={"Authorization": f"Bearer {token}"})
calls = DEAD.calls[before:]
check("มี token -> 200", r.status_code == 200, f"ได้ {r.status_code} {r.text[:120]}")
body = r.json() if r.status_code == 200 else {}
check("คำตอบมีชื่อวิชา", "การเขียนโปรแกรมภาษาคอมพิวเตอร์" in (body.get("reply") or ""),
      (body.get("reply") or "")[:120])
check("citations ว่าง (ไม่ได้มาจากการค้นเอกสาร)", body.get("citations") == [],
      str(body.get("citations"))[:80])
srcs = body.get("sources") or []
check("sources ไม่ว่าง", bool(srcs), str(srcs)[:120])
check("sources บอกไฟล์และหน้า",
      bool(srcs) and srcs[0].get("file") == "cs66.pdf" and srcs[0].get("page_start") == 16,
      str(srcs[:1]))
check("sources บอกหลักสูตรที่อ้างถึง",
      bool(srcs) and "วิทยาการคอมพิวเตอร์" in (srcs[0].get("course_title") or ""),
      str(srcs[:1]))
check("ไม่เรียกโมเดล", calls == [], f"เรียก {calls}")

before = len(DEAD.calls)
r = CLIENT.post("/chat", json={"message": "วิชา 4121204 มีวิชาบังคับก่อนอะไร"},
                headers={"Authorization": f"Bearer {token}"})
body = r.json() if r.status_code == 200 else {}
srcs = body.get("sources") or []
files = sorted({s.get("file") for s in srcs})
pages = sorted({s.get("page_start") for s in srcs})
check("sources ของคำตอบวิชาบังคับก่อนมีทั้งหน้ารายการและหน้าคำอธิบาย",
      files == ["cs66.pdf"] and 16 in pages and 40 in pages, f"{files} {pages}")
check("ไม่เรียกโมเดล", DEAD.calls[before:] == [], f"เรียก {DEAD.calls[before:]}")

# ---------------------------------------------------------------- 8
print()
print("8. คำถามระดับกลุ่มต้องไม่ถูกยุบเหลือวิชาเดียว")
#
# ที่มา: ใช้งานจริง 19 ต.ค. 2569 — ถามขอรายชื่อ 3 วิชาในกลุ่มฝึกประสบการณ์/สหกิจ
# พร้อมเงื่อนไขและหน่วยกิตขั้นต่ำ แต่ระบบตอบรายละเอียดของ 4124815 สหกิจศึกษา วิชาเดียว
#
# สาเหตุ: ชื่อกลุ่ม "ฝึกประสบการณ์วิชาชีพหรือสหกิจศึกษา" มีชื่อวิชา "สหกิจศึกษา" อยู่ข้างใน
# ขั้นจับคู่ด้วยชื่อจึงเจอวิชานั้นแล้วตอบวิชาเดียว
#
# เงื่อนไขของกลุ่ม (ไม่น้อยกว่า 7 หน่วยกิต และให้เลือกไม่น้อยกว่า 5 หน่วยกิต) **ไม่ได้อยู่ใน
# ข้อมูลที่มีโครงสร้าง** อยู่ในเนื้อความเอกสารเท่านั้น คำถามแบบนี้จึงต้องไหลไปเส้นทางเอกสาร
ONE_SUBJECT_SHAPE = "6 หน่วยกิต · 6(540)"
for q in ("กลุ่มวิชาฝึกประสบการณ์วิชาชีพหรือสหกิจศึกษาของวิทยาการคอมพิวเตอร์ 2566 มีวิชาอะไรบ้าง",
          "วิทยาการคอมพิวเตอร์ 2566 กลุ่มสหกิจศึกษาต้องเรียนกี่หน่วยกิต และเลือกวิชาอะไรได้บ้าง",
          "ขอรายชื่อวิชาในกลุ่มฝึกประสบการณ์วิชาชีพหรือสหกิจศึกษาของวิทคอม 2566"):
    got, calls, _t = web(q)
    head = q[:40]
    check(f"[{head}] ไม่ตอบเป็นรายละเอียดวิชาเดียว",
          ONE_SUBJECT_SHAPE not in got, got[:160])
    check(f"[{head}] ไหลไปเส้นทางเอกสาร (เรียกโมเดล)", calls != [], f"เรียก {calls}")

# คำถามรายวิชาเดี่ยวต้องยังตอบจากฐานข้อมูลเหมือนเดิม ไม่ถูกตัวกรองกลุ่มกินไปด้วย
got, calls, _t = web("วิชา 4124815 กี่หน่วยกิต")
check("ถามวิชาเดียวด้วยรหัส ยังตอบจากฐานข้อมูล", "สหกิจศึกษา" in got and "6 หน่วยกิต" in got, got[:160])
check("ถามวิชาเดียวด้วยรหัส ไม่เรียกโมเดล", calls == [], f"เรียก {calls}")

got, calls, _t = web("วิชาสหกิจศึกษาของวิทยาการคอมพิวเตอร์ 2566 กี่หน่วยกิต")
check("ถามวิชาเดียวด้วยชื่อ ยังตอบจากฐานข้อมูล", "6 หน่วยกิต" in got, got[:160])
check("ถามวิชาเดียวด้วยชื่อ ไม่เรียกโมเดล", calls == [], f"เรียก {calls}")

print()
print(f"จุดตรวจ {CHECKS} จุด")
print(f"เรียกโมเดลทั้งหมด {len(DEAD.calls)} ครั้ง (ควรมีเฉพาะข้อที่ต้องไหลไปเส้นทางเอกสาร)")
if FAILURES:
    print(f"ตก {len(FAILURES)} จุด")
    for f in FAILURES:
        print("  -", f)
    raise SystemExit(1)
print("ผ่านทั้งหมด")
