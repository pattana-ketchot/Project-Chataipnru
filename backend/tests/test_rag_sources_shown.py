"""
คำตอบที่มาจากการค้นเอกสารต้องบอกที่มาที่รองรับคำตอบจริงให้ผู้ใช้เห็น

    cd backend && python tests/test_rag_sources_shown.py

ยิงผ่าน /chat-web (เส้นทางของผู้ใช้หน้าเว็บ) และ /chat (เส้นทางที่ตรวจสิทธิ์) โดย
**ปิดแคช** เพื่อให้คำตอบมาจากการค้นจริงทุกครั้ง · ใช้โมเดลจริงเพราะคำตอบสาย RAG
เป็นข้อความที่โมเดลเขียน การแทนด้วยข้อความคงที่จะไม่ได้วัดของจริง

ที่มาของชุดนี้ — ตรวจเมื่อ 14 ต.ค. 2569 พบว่าคำตอบสาย RAG ห้าข้อไม่มีที่มาเลยทั้งใน
ข้อความและ header ทั้งที่ระบบเลือกชิ้นเอกสารไว้แล้ว 20-25 ชิ้น และ citation อันดับหนึ่ง
ของคำถามคุณสมบัติผู้เข้าศึกษา (it66.pdf หน้า 161) ไม่ใช่หน้าที่รองรับคำตอบ (หน้า 16)
"""
import logging
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

CHECKS = 0
FAILURES: list[str] = []
OUTAGES: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    print(("  [ผ่าน] " if ok else "  [ตก]  ") + label + (f" — {detail}" if detail else ""))
    if not ok:
        FAILURES.append(f"{label} — {detail}")


logging.getLogger("course_advisor").addHandler(logging.NullHandler())

from fastapi.testclient import TestClient  # noqa: E402

from app.services import chat as C  # noqa: E402
from app.main import app  # noqa: E402

C.cache_lookup = lambda db, q, v: None     # ปิดแคชอ่าน
C.cache_store = lambda *a, **k: None       # ปิดแคชเขียน
CLIENT = TestClient(app)
SENT: list[float] = []


def ask(message: str, prior: list[dict] | None = None) -> str:
    """ยิงผ่าน /chat-web แล้วคืนข้อความคำตอบทั้งก้อน (รอด่านจำกัดอัตราให้เอง)"""
    while True:
        SENT[:] = [t for t in SENT if time.monotonic() - t < 60.0]
        if len(SENT) < 18:
            break
        time.sleep(2.0)
    SENT.append(time.monotonic())
    msgs = list(prior or []) + [{"role": "user", "content": message}]
    r = CLIENT.post("/chat-web", json={"messages": msgs})
    if r.status_code != 200:
        OUTAGES.append(f"{message[:40]} -> HTTP {r.status_code}")
        return ""
    return r.text


# บรรทัดที่มามีสามรูปตามสถานะการตรวจข้ออ้าง (ดู chat.py::_with_rag_sources)
#   "ที่มา: ..."                                     — ข้ออ้างที่ตรวจได้รองรับครบ
#   "ที่มา (ตรวจแล้วรองรับบางส่วน): ..."               — รองรับบางส่วน
#   "หน้าที่ใกล้เคียงคำตอบ (ยังยืนยันคำตอบไม่ได้): ..." — ยืนยันไม่ได้
# ชุดนี้ตรวจว่า "ที่มาชี้หน้าที่ถูก" จึงต้องอ่านได้ทุกรูป ไม่ใช่เฉพาะรูปแรก
SOURCE_LINE = ("ที่มา:", "ที่มา (", "หน้าที่ใกล้เคียงคำตอบ")


def is_source_line(line: str) -> bool:
    return line.strip().startswith(SOURCE_LINE)


def has_source_line(reply: str) -> bool:
    return any(is_source_line(ln) for ln in reply.split("\n"))


def source_pages(reply: str, filename: str) -> set[int]:
    """เลขหน้าที่บรรทัดที่มาอ้างถึงของไฟล์นั้น"""
    import re
    out = set()
    for line in reply.split("\n"):
        if is_source_line(line):
            for f, pg in re.findall(r"([a-z0-9_]+\.pdf) หน้า (\d+)", line):
                if f == filename:
                    out.add(int(pg))
    return out


print("== 1. คำตอบสาย RAG ต้องมีบรรทัดที่มา และต้องเป็นหน้าที่รองรับคำตอบ ==")
CASES = [
    ("คุณสมบัติผู้เข้าศึกษาของเทคโนโลยีสารสนเทศคืออะไร", "it66.pdf", {16}, {161}),
    ("หลักสูตรวิทยาการคอมพิวเตอร์เรียนกี่ปี", "cs61.pdf", {129, 128, 130}, set()),
]
for q, fname, want, forbid in CASES:
    reply = ask(q)
    if not reply:
        print(f"  [ข้าม] {q[:46]} — บริการขัดข้อง")
        continue
    pages = source_pages(reply, fname)
    check(f"มีบรรทัดที่มา — {q[:40]}", has_source_line(reply), reply[-120:].replace("\n", " "))
    check(f"ที่มาอ้าง {fname} หน้าใน {sorted(want)}", bool(pages & want), f"ได้ {sorted(pages) or 'ไม่มี'}")
    if forbid:
        check(f"ไม่อ้างหน้า {sorted(forbid)} ที่ไม่ได้รองรับคำตอบ", not (pages & forbid), f"ได้ {sorted(pages)}")

print("== 2. คำตอบที่สังเคราะห์จากหลายเอกสารต้องบอกที่มาหลายเล่ม ==")
reply = ask("วิทยาการคอมพิวเตอร์กับเทคโนโลยีสารสนเทศต่างกันอย่างไร")
if reply:
    import re
    files = {f for line in reply.split("\n") if is_source_line(line)
             for f in re.findall(r"([a-z0-9_]+\.pdf)", line)}
    check("ที่มามีเอกสารของทั้งสองหลักสูตร", len({f[:2] for f in files}) >= 2, f"ได้ {sorted(files)}")
else:
    print("  [ข้าม] บริการขัดข้อง")

print("== 3. ค่าเทอมต้องมีหน่วย ค่าแรกเข้า วันที่ข้อมูล และไม่สรุปสถานะเปิดรับ ==")
fee = ask("ค่าเทอมสาขาวิทยาการคอมพิวเตอร์เท่าไหร่")
check("มี 12,000 และ 14,000", "12,000" in fee and "14,000" in fee, fee[:80])
check("บอกหน่วยต่อภาคการศึกษา", "ต่อภาคการศึกษา" in fee)
check("บอกค่าธรรมเนียมแรกเข้า 4,500", "4,500" in fee)
check("บอกวันที่ของข้อมูล 13 พฤศจิกายน 2568", "13 พฤศจิกายน 2568" in fee)
check("ไม่เรียกวันนั้นว่าวันที่ออกประกาศ", "ไม่ใช่วันที่ออกประกาศ" in fee)
check("มีลิงก์ต้นทาง", "acade.pnru.ac.th" in fee)
check("ไม่สรุปว่าไม่เปิดรับภาคเสาร์-อาทิตย์", "ไม่เปิดรับภาคเสาร์-อาทิตย์" not in fee)
check("ไม่มีเลข 22,000 จาก มคอ.", "22,000" not in fee)

print("== 4. สาขาที่ประกาศมีแต่ระบบเคยไม่มีข้อมูล ==")
cook = ask("ค่าเทอมการประกอบอาหารและการบริการอาหารเท่าไหร่")
check("ตอบค่าเทอมได้ ไม่บอกว่าไม่มีในประกาศ",
      "12,000" in cook and "ไม่มีข้อมูลค่าเทอมในประกาศ" not in cook, cook[:90])

print("== 5. คำถามต่อเนื่องเรื่องค่าเทอมต้องไม่ถามกลับว่าสาขาอะไร ==")
prior = [{"role": "user", "content": "หลักสูตรวิทยาการคอมพิวเตอร์ พ.ศ. 2566 ต้องเรียนกี่หน่วยกิต"},
         {"role": "assistant", "content": "ไม่น้อยกว่า 130 หน่วยกิต"}]
follow = ask("แล้วค่าเทอมล่ะ", prior)
check("ตอบค่าเทอมของสาขาเดิม", "12,000" in follow, follow[:90])
check("ไม่ถามกลับว่าสาขาอะไร", "สาขาอะไร" not in follow)

print()
print(f"จุดตรวจ {CHECKS} จุด · ตก {len(FAILURES)} · บริการขัดข้อง {len(OUTAGES)}")
for f in FAILURES:
    print("  -", f)
for o in OUTAGES:
    print("  (ขัดข้อง)", o)
raise SystemExit(1 if FAILURES else 0)
