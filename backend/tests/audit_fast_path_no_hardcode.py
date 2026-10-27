"""
ตรวจว่าทางตอบเร็วตอบจาก "ข้อมูลจริง" ไม่ใช่การผูกคำถามที่เคยทดสอบกับคำตอบสำเร็จรูป

    cd backend && python tests/audit_fast_path_no_hardcode.py

วิธีตรวจ
-------
1. **ปิดแคชคำตอบ** แทน cache_lookup/cache_store ด้วยตัวที่ไม่ทำอะไร เพื่อให้แน่ใจว่า
   ทุกคำตอบประกอบขึ้นใหม่จากฐานข้อมูล ไม่ใช่หยิบคำตอบเก่าที่เคยเขียนไว้
2. **ทำให้โมเดลใช้ไม่ได้** ตัวเชื่อมต่อปลอมนับทุกการเรียกแล้วโยนข้อผิดพลาดทันที
   ถ้าคำตอบยังออกมาถูกต้องโดยนับได้ 0 ครั้ง แปลว่าคำตอบนั้นมาจากข้อมูลจริง ๆ
   และถ้าคำถามไหนต้องใช้โมเดล จะเห็นชัดว่าใช้ไม่ได้ ไม่ใช่เดาคำตอบมาให้
3. **ยิงผ่าน /chat-web ด้วย TestClient** ซึ่งปั๊ม generator แบบเดียวกับ uvicorn
   ไม่ใช่เรียก prepare_answer() ตรง ๆ
4. ใช้ **คำถามใหม่ที่ไม่เคยอยู่ในชุดทดสอบใด** หลายสำนวน สลับปี สลับหลักสูตร
   สลับระดับปริญญา ถามข้อมูลที่ไม่มี และถามหลายเรื่องพร้อมกัน
5. แต่ละข้อแสดงเส้นทางที่ตอบจาก timing log จริง (แคช / ฐานข้อมูล / โมเดล)
   พร้อมหลักสูตรและปีที่ระบบเลือก และแถวข้อมูลต้นทางจาก view ที่เผยแพร่แล้ว

**ความเร็วไม่ใช่หลักฐานว่าคำตอบถูก** ทุกข้อจึงต้องเทียบตัวเลขกับ quote ที่ยกมาจาก
เอกสารซึ่งเก็บอยู่ในฐานข้อมูล และข้อที่สำคัญต้องเปิด PDF หน้าจริงเทียบอีกชั้น
"""
import json
import logging
import re
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from llm.connector import LLMConnectionError  # noqa: E402


class DeadModel:
    """ตัวเชื่อมต่อที่ใช้ไม่ได้ · นับทุกการเรียกแล้วโยนทันที"""

    answer_token_cap = 2048

    def __init__(self) -> None:
        self.calls: list[str] = []

    def _die(self, what: str):
        self.calls.append(what)
        raise LLMConnectionError("จำลองว่าโมเดลใช้ไม่ได้ (ตรวจว่าคำตอบมาจากข้อมูลจริง)")

    def chat(self, *a, **k):
        return self._die("chat")

    def chat_stream(self, *a, **k):
        return self._die("chat_stream")

    def embed(self, *a, **k):
        return self._die("embed")


class Timing(logging.Handler):
    """เก็บบรรทัด timing ของ /chat-web ไว้อ่านเส้นทางที่ตอบจริง"""

    def __init__(self):
        super().__init__()
        self.lines: list[str] = []

    def emit(self, record):
        try:
            msg = record.getMessage()
            if "timing /chat-web" in msg:
                self.lines.append(msg)
        except Exception:
            pass


TIMING = Timing()
logging.getLogger("course_advisor").addHandler(TIMING)

from fastapi.testclient import TestClient  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.services import chat as C  # noqa: E402
from app.services import llm_client  # noqa: E402
from app.services import structured_intent as SI  # noqa: E402
from app.services.curriculum_facts import lookup as facts_lookup  # noqa: E402
from app.main import app  # noqa: E402

# --- ปิดแคช ---
CACHE_LOOKUPS = []


def _no_cache(db, question, version):
    CACHE_LOOKUPS.append(question)
    return None


def _no_store(*a, **k):
    return None


C.cache_lookup = _no_cache
C.cache_store = _no_store

# --- ทำให้โมเดลใช้ไม่ได้ ---
DEAD = DeadModel()
llm_client._connector = DEAD

CLIENT = TestClient(app)

# คำถามทั้งหมดด้านล่าง "ไม่เคยอยู่ในชุดทดสอบหรือ gold ใด" ตั้งใจเขียนใหม่ทุกข้อ
# รูปแบบ: (รหัส, กลุ่ม, คำถาม, สิ่งที่ต้องเป็นจริงถ้าระบบตอบถูก)
QUESTIONS = [
    # ก. สำนวนใหม่ของคำถามหน่วยกิต — คำย่อ ภาษาอังกฤษ เลขไทย
    ("A1", "สำนวนใหม่", "วิทคอมต้องเก็บหน่วยกิตทั้งหมดเท่าไร", "ต้องได้หน่วยกิตของวิทยาการคอมพิวเตอร์"),
    ("A2", "สำนวนใหม่", "อยากทราบว่าสาขาคณิตศาสตร์เรียนทั้งหมดกี่หน่วยกิตครับ", "ต้องได้หน่วยกิตของคณิตศาสตร์"),
    ("A3", "สำนวนใหม่", "cs 2561 หน่วยกิตรวมเท่าไหร่", "คำย่ออังกฤษ + ปี ต้องได้ฉบับ 2561"),
    ("A4", "สำนวนใหม่", "หลักสูตรเทคโนโลยีสารสนเทศ พ.ศ. ๒๕๖๖ กี่หน่วยกิต", "เลขไทยต้องใช้ได้"),
    # ข. สลับปี
    ("B1", "สลับปี", "วิทยาการคอมพิวเตอร์ 2566 กี่หน่วยกิต", "ต้องอ้างเอกสารฉบับ 2566"),
    ("B2", "สลับปี", "วิทยาการคอมพิวเตอร์ 2561 กี่หน่วยกิต", "ต้องอ้างเอกสารฉบับ 2561 ไม่ใช่ 2566"),
    ("B3", "สลับปี", "หลักสูตรคณิตศาสตร์ พ.ศ. 2554 เรียนกี่หน่วยกิต", "ปีที่ไม่มี ห้ามเอาปีอื่นมาตอบเงียบ ๆ"),
    # ค. สลับระดับปริญญา
    ("C1", "ระดับปริญญา", "ปริญญาโทการจัดการเทคโนโลยีการเกษตร หน่วยกิตเท่าไร", "ต้องได้ของปริญญาโท ไม่ใช่ตรี"),
    ("C2", "ระดับปริญญา", "ปริญญาเอกการจัดการเทคโนโลยีการเกษตรและบริหารทรัพยากรชุมชนเรียนกี่หน่วยกิต", "ต้องได้ของปริญญาเอก"),
    ("C3", "ระดับปริญญา", "ปริญญาโทคณิตศาสตร์เรียนกี่หน่วยกิต", "ระดับที่ไม่มี ห้ามยืมตัวเลขของตรี"),
    # ง. หัวข้ออื่นที่ฐานข้อมูลมี และหัวข้อที่ตั้งใจไม่เปิดให้ตอบ
    ("D1", "หัวข้ออื่น", "จบคณิตศาสตร์ไปประกอบอาชีพอะไรได้บ้าง", "รายการอาชีพของคณิตศาสตร์"),
    ("D2", "หัวข้ออื่น", "หลักสูตรเทคโนโลยีสารสนเทศมีจุดมุ่งหมายอะไร", "วัตถุประสงค์ของ IT"),
    ("D3", "หัวข้ออื่น", "คุณสมบัติผู้สมัครเข้าเรียนวิทยาการคอมพิวเตอร์มีอะไรบ้าง",
     "admission ไม่อยู่ใน USER_FACING_FIELDS จึงไม่ควรตอบจากฐาน"),
    # จ. ข้อมูลที่ไม่มี
    ("E1", "ไม่มีข้อมูล", "หลักสูตรวิทยาการคอมพิวเตอร์มีเงินเดือนเริ่มต้นของบัณฑิตเท่าไร", "ไม่มีข้อมูลนี้ ห้ามเดา"),
    ("E2", "ไม่มีข้อมูล", "สาขาฟิสิกส์ควอนตัมเรียนกี่หน่วยกิต", "คณะไม่มีสาขานี้ ต้องบอกตรง ๆ"),
    # ฉ. ถามหลายเรื่องพร้อมกัน — จุดที่เสี่ยงตอบไม่ครบ
    ("F1", "หลายเรื่อง", "วิทยาการคอมพิวเตอร์ 2566 เรียนกี่หน่วยกิต และจบไปทำงานอะไรได้บ้าง",
     "ต้องตอบทั้งหน่วยกิตและอาชีพ"),
    ("F2", "หลายเรื่อง", "คณิตศาสตร์กับวิทยาการคอมพิวเตอร์ อันไหนหน่วยกิตมากกว่า",
     "ต้องพูดถึงทั้งสองหลักสูตร"),
    ("F3", "หลายเรื่อง", "วิทคอมเรียนกี่หน่วยกิต แล้วค่าเทอมเท่าไหร่",
     "ข้อมูลสองแหล่ง (ฐานหลักสูตร + ตารางค่าเทอม) ต้องตอบทั้งคู่"),
    ("F4", "หลายเรื่อง", "เทคโนโลยีสารสนเทศ 2566 กี่หน่วยกิต และมีวัตถุประสงค์อะไร",
     "สองหัวข้อของหลักสูตรเดียว"),
    # ช. ข้อเท็จจริงผสมคำแนะนำ และนอกเรื่อง
    ("G1", "ผสมคำแนะนำ", "วิทคอมเรียนกี่หน่วยกิต แล้วแนะนำสาขาที่เหมาะกับคนชอบวาดรูปด้วย",
     "ห้ามตอบแค่หน่วยกิตแล้วทิ้งส่วนคำแนะนำ"),
    ("G2", "นอกเรื่อง", "พรุ่งนี้ฝนตกไหม", "ต้องบอกว่าตอบได้เฉพาะเรื่องหลักสูตร"),
]


def route_of(stages: str, source: str, calls: int) -> str:
    if "cache_hit" in stages:
        return "แคช"
    if "structured_fast_early" in stages:
        return "ฐานข้อมูล (ด่าน 0.718 ก่อนเรียกโมเดล)"
    if "structured_fast" in stages:
        return "ฐานข้อมูล (ด่าน 0.95)"
    if calls == 0:
        return "ด่านตรวจ/ตารางข้อมูล (ไม่เรียกโมเดล)"
    return f"โมเดล (พยายามเรียก {calls} ครั้ง)"


SENT: list[float] = []


def ask(q: str) -> dict:
    # ด่านจำกัดอัตราของ /chat-web ยอม 20 คำขอ/นาที/IP · รอให้มีที่ว่างก่อนยิง
    # ไม่งั้นข้อท้าย ๆ จะได้ 429 ซึ่งไม่เกี่ยวกับคุณภาพคำตอบ (เจอกับ G2 รอบแรก)
    while True:
        SENT[:] = [t for t in SENT if time.monotonic() - t < 60.0]
        if len(SENT) < 17:
            break
        time.sleep(60.0 - (time.monotonic() - SENT[0]) + 0.3)
    SENT.append(time.monotonic())
    before = len(DEAD.calls)
    TIMING.lines.clear()
    t0 = time.perf_counter()
    r = CLIENT.post("/chat-web", json={"messages": [{"role": "user", "content": q}]})
    took = time.perf_counter() - t0
    calls = DEAD.calls[before:]
    line = TIMING.lines[-1] if TIMING.lines else ""
    stages = line.split("|")[1] if line.count("|") >= 2 else ""
    m = re.search(r"source=(\S+)", line)
    return {
        "reply": r.text.strip(), "status": r.status_code, "took": took,
        "calls": calls, "stages": stages.strip(),
        "source": m.group(1) if m else "-",
        "route": route_of(stages, m.group(1) if m else "", len(calls)),
    }


def chosen(db, q: str) -> str:
    """หลักสูตรและปีที่ชั้นข้อมูลเลือก พร้อมแถวต้นทางที่ใช้ตอบ (อ่านอย่างเดียว)"""
    try:
        intent = SI.detect(db, q)
    except Exception as exc:
        return f"detect ล้ม: {type(exc).__name__}"
    if intent.route != SI.STRUCTURED:
        return f"ชั้นข้อมูลไม่รับ (route={intent.route} reason={intent.reason})"
    try:
        res = facts_lookup(db, intent)
    except Exception as exc:
        return f"lookup ล้ม: {type(exc).__name__}"
    rows = []
    for f in getattr(res, "facts", []) or []:
        src = f.source
        rows.append(
            f"      · {f.course_title[:46]} | ฉบับ {f.edition_year}"
            f" | ค่า={f.value_int if f.value_int is not None else ((f.value_text or '') or f'{len(f.items)} รายการ')[:28]}"
            + (f" | {src.file} หน้า {src.page_start}" if src else " | ไม่มีที่มา")
            + (f"\n        quote: {(src.quote or '')[:96]}" if src and src.quote else "")
        )
    head = (f"field={intent.field} · ปีที่ระบุในคำถาม={intent.year_be or 'ไม่ระบุ'}"
            f" · หลักสูตรที่เลือก {len(intent.course_ids)} เล่ม · status={res.status}")
    return head + ("\n" + "\n".join(rows) if rows else "\n      (ไม่มีแถวข้อมูล)")


print("=" * 104)
print("ตรวจทางตอบเร็ว: ปิดแคช + ทำให้โมเดลใช้ไม่ได้ + คำถามใหม่ทั้งหมด")
print("=" * 104)
print()

RESULTS = []
with SessionLocal() as db:
    for code, group, q, expect in QUESTIONS:
        got = ask(q)
        RESULTS.append((code, group, q, expect, got))
        print(f"[{code}] {group}")
        print(f"  คำถาม     : {q}")
        print(f"  สิ่งที่ต้องเป็น: {expect}")
        print(f"  เส้นทาง    : {got['route']}   (source={got['source']}, stages: {got['stages'] or '-'})")
        print(f"  เวลา       : {got['took']:.2f}s   HTTP {got['status']}   เรียกโมเดล: {got['calls'] or 'ไม่เรียก'}")
        print(f"  คำตอบ     : {got['reply'][:600].replace(chr(10), chr(10) + '              ')}")
        print(f"  ชั้นข้อมูลเลือก: {chosen(db, q)}")
        print()
    db.rollback()

print("=" * 104)
print(f"เรียกแคชทั้งหมด {len(CACHE_LOOKUPS)} ครั้ง และถูกบังคับให้ไม่เจอทุกครั้ง (แคชปิดสนิท)")
print(f"เรียกโมเดลทั้งหมด {len(DEAD.calls)} ครั้ง: {DEAD.calls}")
print("=" * 104)

out = Path("/out/audit_fast_path.json") if Path("/out").is_dir() else Path("audit_fast_path.json")
out.write_text(json.dumps([
    {"id": c, "group": g, "q": q, "expect": e,
     "reply": r["reply"], "route": r["route"], "source": r["source"],
     "stages": r["stages"], "took_s": round(r["took"], 2), "model_calls": r["calls"]}
    for c, g, q, e, r in RESULTS
], ensure_ascii=False, indent=2), encoding="utf-8")
print(f"บันทึกผลดิบไว้ที่ {out}")
