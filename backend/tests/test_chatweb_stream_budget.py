"""
ยืนยันว่าเส้นทาง /chat-web **ที่ถูกปั๊มแบบเดียวกับ production** ทำงานถูกและเพดานเวลาถูกบังคับ

    cd backend && python tests/test_chatweb_stream_budget.py

ทำไมต้องมีชุดนี้แยกจากชุดอื่น
---------------------------
ชุดทดสอบที่มีอยู่เรียก prepare_answer() หรือ connector ตรงๆ จึงรันในบริบท (Context)
เดียวตลอด · แต่ของจริง Starlette ปั๊ม generator ของ stream_answer ทีละ step ผ่าน
threadpool และแต่ละ step ได้บริบทสำเนาใหม่ ความต่างนี้ทำให้บั๊กจริงหลุดมาได้:

    14 ต.ค. 2569 — ทุกคำขอตอบเนื้อหาถูกต้องครบแล้วต่อท้ายด้วย "ระบบตอบไม่ได้ในขณะนี้"
    เพราะ reset_budget() ใช้ token ของ ContextVar ที่สร้างใน step แรก แล้ว reset ใน
    step หลังไม่ได้ (ValueError: was created in a different Context) · ล้ม 19/19 คำขอ
    และที่ร้ายกว่านั้นคือค่าเพดานก็มองไม่เห็นข้าม step เพดานเวลาจึงไม่เคยถูกบังคับ
    ระหว่างอ่านสตรีมจากโมเดล ซึ่งเป็นช่วงที่กินเวลาที่สุด

TestClient ของ FastAPI ปั๊ม generator ด้วยกลไกเดียวกับ uvicorn จึงจับเรื่องนี้ได้
ส่วนปลายทางโมเดลใช้ HTTP server จริงที่สตรีมจริงไม่หยุด (read timeout ไม่เคยชน)
"""
import json
import logging
import uuid
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

CHECKS = 0
FAILURES: list[str] = []
STOP = threading.Event()


def check(label: str, ok: bool, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    if ok:
        print(f"  [ผ่าน] {label}" + (f" — {detail}" if detail else ""))
    else:
        FAILURES.append(f"{label} — {detail}")
        print(f"  [ตก]  {label} — {detail}")


# ---- ปลายทางโมเดลปลอมที่สตรีมจริงไม่หยุด ----
class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_a):
        pass

    def do_POST(self):  # noqa: N802
        n = int(self.headers.get("content-length") or 0)
        body = self.rfile.read(n) if n else b"{}"
        # นับคำขอที่ปลายทางโมเดลได้รับจริง — ใช้ยืนยันว่าคำถามของ fixture เข้าถึงโมเดล
        # ไม่ใช่ถูกด่านก่อนหน้าตอบไปแล้ว (ดูเหตุที่ต้องตรวจข้อนี้ในหัวข้อ 2)
        try:
            streaming = bool(json.loads(body).get("stream"))
        except Exception:  # noqa: BLE001 — ปลายทางปลอม ไม่ต้องเข้มกับ body ที่อ่านไม่ออก
            streaming = True
        HITS.append("stream" if streaming else "once")
        # ด่านตรวจเอกสารเรียกแบบไม่สตรีมแล้วรอคำตอบทั้งก้อน · ถ้าปลายทางไม่ตอบคำขอแบบนี้
        # เพดานจะหมดที่ขั้นเตรียมคำตอบ และชุดนี้จะไม่เคยทดสอบ "การอ่านสตรีมจากโมเดล"
        # ซึ่งเป็นจุดที่บั๊ก ContextVar เดิมอยู่ · จึงตอบคำขอแบบไม่สตรีมให้จบทันที
        if not streaming:
            payload = json.dumps({"message": {"content": json.dumps(
                {"can_answer": True, "reason": "เอกสารมีข้อเท็จจริงที่ถาม (ปลายทางทดสอบ)"},
                ensure_ascii=False)}}).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            self.wfile.flush()
            return
        self.send_response(200)
        self.send_header("content-type", "application/x-ndjson")
        self.send_header("transfer-encoding", "chunked")
        self.end_headers()
        i = 0
        while not STOP.is_set():
            data = (json.dumps({"message": {"content": f"c{i} "}}) + "\n").encode()
            try:
                self.wfile.write(b"%x\r\n%s\r\n" % (len(data), data))
                self.wfile.flush()
            except OSError:
                return
            i += 1
            time.sleep(0.25)


HITS: list[str] = []


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


PORT = free_port()
SERVER = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
SERVER.daemon_threads = True
threading.Thread(target=SERVER.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{PORT}"


class Capture(logging.Handler):
    """เก็บ log ของ course_advisor ไว้ตรวจว่ามี/ไม่มีการล้มกลางสตรีม"""

    def __init__(self):
        super().__init__()
        self.lines: list[str] = []

    def emit(self, record):
        try:
            text = record.getMessage()
            if record.exc_info:
                import traceback
                text += " | " + "".join(traceback.format_exception(*record.exc_info))
            self.lines.append(f"{record.levelname}:{text}")
        except Exception:
            pass


CAP = Capture()
logging.getLogger("course_advisor").addHandler(CAP)

from fastapi.testclient import TestClient  # noqa: E402

from app.services import llm_client  # noqa: E402
from llm import connector as connector_mod  # noqa: E402
from llm.connector import OllamaConnector  # noqa: E402
from app.main import app  # noqa: E402

CLIENT = TestClient(app)


def post(message: str, prior=None) -> tuple[int, str, float]:
    msgs = list(prior or []) + [{"role": "user", "content": message}]
    t0 = time.perf_counter()
    r = CLIENT.post("/chat-web", json={"messages": msgs})
    return r.status_code, r.text, time.perf_counter() - t0


# ข้อความที่ระบบใช้บอกว่าตอบไม่ได้ — ต้องตรงกับ _SERVICE_MARKERS ของ eval/run_suite30.py
# ไม่งั้นชุดนี้กับชุดประเมินจะตัดสินคนละอย่างกับคำตอบเดียวกัน
SERVICE_TEXT = ("ระบบหลักตอบไม่ได้", "ขอไม่ตอบด้วยโมเดลสำรอง", "ระบบ AI ยังไม่พร้อม",
                "ระบบตอบไม่ได้ในขณะนี้", "เกินเพดาน", "ขัดข้องชั่วคราว",
                "ขัดข้อง กรุณาลองใหม่", "ไม่ได้รับคำตอบจาก AI")

try:
    print("1. คำถามที่ตอบจากฐานข้อมูล ต้องไม่มีข้อความบริการขัดข้องต่อท้าย")
    print("   (บั๊กเดิมทำให้ทุกคำขอมีข้อความนี้ต่อท้ายคำตอบที่ถูกต้องแล้ว)")
    CAP.lines.clear()
    code, body, took = post("หลักสูตรวิทยาการคอมพิวเตอร์ พ.ศ. 2561 ต้องเรียนทั้งหมดกี่หน่วยกิต")
    check("ได้สถานะ 200", code == 200, f"code={code}")
    check("มีตัวเลขหน่วยกิตถูกต้อง", "130" in body, body[:120])
    check("ยังมีคำว่าไม่น้อยกว่า", "ไม่น้อยกว่า" in body, body[:120])
    check("มีที่มา", "ที่มา:" in body, body[:120])
    found = [m for m in SERVICE_TEXT if m in body]
    check("ไม่มีข้อความบริการขัดข้องต่อท้าย", not found, f"เจอ {found} · {body[-140:]}")
    broke = [ln for ln in CAP.lines if "ล้มกลางคัน" in ln or "different Context" in ln]
    check("ไม่มี log ว่าล้มกลางสตรีม", not broke, (broke[0][:200] if broke else ""))
    check("ตอบเร็วตามเป้าคำถามจากฐาน (<=5s)", took <= 5.0, f"{took:.2f}s")

    print()
    print("2. เพดานเวลาต้องถูกบังคับข้าม step ของการสตรีม (ปลายทางสตรีมจริงไม่หยุด)")
    BUDGET = 6.0
    TOL = 4.0
    real = llm_client._connector
    saved_default = connector_mod._DEFAULT_BUDGET_S
    connector_mod._DEFAULT_BUDGET_S = BUDGET
    # ฝังเฉพาะฝั่งคุย ส่วนฝั่ง embedding ยังเป็นของจริง เพื่อให้การค้นเอกสารทำงานได้
    llm_client._connector = llm_client._SplitConnector(
        embedder=llm_client._build_ollama(),
        chatter=OllamaConnector(base_url=BASE, timeout_s=120, max_retries=0),
    )
    try:
        CAP.lines.clear()
        # ต่อรหัสสุ่มท้ายคำถามเพื่อให้แคชคำตอบไม่มีทางมีข้อนี้
        #
        # รอบแรกที่เขียนชุดนี้ ข้อนี้ผ่านฉลุยใน 0.02 วินาทีโดยไม่เคยแตะโมเดล เพราะ
        # คำถามเดิมมีอยู่ในแคชคำตอบแล้ว (timing log ขึ้น cache_hit) ซึ่งแปลว่าชุดทดสอบ
        # ไม่ได้ทดสอบอะไรเลย · ด้านล่างจึงตรวจซ้ำด้วยว่า timing log ต้องไม่มี cache_hit
        nonce = uuid.uuid4().hex[:6]
        HITS.clear()
        # คำถามที่ชั้นข้อมูลที่เผยแพร่ตอบไม่ได้จริง (ไม่มีข้อมูลทุนการศึกษาในฐาน) จึงต้อง
        # ไหลไปถึงขั้นเรียกโมเดล · คำถามเดิมคือ "วิชาบังคับของวิทยาการคอมพิวเตอร์ 2566"
        # ซึ่งหลังเผยแพร่รายวิชา (ขั้น C) ฐานตอบได้เองใน 20 มิลลิวินาที ไม่เคยแตะโมเดล
        # ข้อนี้จึงตกที่ "ไม่จบเร็วกว่าเพดาน" และ "บอกผู้ใช้ว่าบริการขัดข้อง" เพราะ
        # ไม่มีอะไรให้บังคับเพดานอีกแล้ว ไม่ใช่เพราะเพดานเวลาพัง
        code, body, took = post(
            f"หลักสูตรวิทยาการคอมพิวเตอร์ พ.ศ. 2566 มีทุนการศึกษาอะไรบ้าง (ตรวจระบบ {nonce})")
        check("ไม่ได้ผ่านเพราะแคช — ต้องไม่มี cache_hit ใน timing log",
              not any("cache_hit" in ln for ln in CAP.lines),
              next((ln[:110] for ln in CAP.lines if "cache_hit" in ln), ""))
        # ข้อนี้คือเงื่อนไขที่ทำให้ชุดนี้ทดสอบเพดานได้จริง: ถ้าไม่มีคำขอถึงปลายทางโมเดล
        # การ "ผ่าน" ข้ออื่นด้านล่างจะไม่ได้พิสูจน์ว่าเพดานถูกบังคับระหว่างอ่านสตรีม
        check("คำถามนี้เข้าถึงโมเดลจริง — ปลายทางโมเดลได้รับคำขอ", bool(HITS),
              f"คำขอที่ปลายทางโมเดล {HITS} · ได้: {body[:90]}")
        # เพดานต้องถูกบังคับระหว่าง "อ่านสตรีมคำตอบ" ไม่ใช่แค่ระหว่างด่านที่เรียกโมเดลแบบรอทั้งก้อน
        check("เพดานถูกบังคับระหว่างอ่านสตรีมคำตอบ (ไม่ใช่ล้มก่อนถึงขั้นสตรีม)",
              "stream" in HITS, f"คำขอที่ปลายทางโมเดล {HITS}")
        check("ได้สถานะ 200 (ไม่ใช่ 500)", code == 200, f"code={code}")
        check(f"จบภายในเพดาน {BUDGET:g}s + ผ่อน {TOL:g}s", took <= BUDGET + TOL, f"{took:.2f}s")
        check("ไม่จบเร็วกว่าเพดานอย่างผิดสังเกต", took >= BUDGET * 0.5, f"{took:.2f}s")
        check("บอกผู้ใช้ว่าบริการขัดข้อง ไม่เงียบและไม่เดาคำตอบ",
              any(m in body for m in SERVICE_TEXT), body[-160:])
        ctx = [ln for ln in CAP.lines if "different Context" in ln]
        check("ไม่มี ValueError เรื่องข้ามบริบท", not ctx, (ctx[0][:200] if ctx else ""))
        # สาเหตุที่บันทึกต้องชี้ว่าเป็นเพดานเวลา ไม่ใช่ความล้มเหลวทั่วไป · บันทึกได้สองรูป
        # ตามจุดที่เพดานตัด และทั้งสองรูปตรวจย้อนหลังได้เท่ากัน
        #   ตัดระหว่างด่านที่เรียกโมเดลแบบรอทั้งก้อน -> ชั้น RAG log "เกินเพดานที่ตั้งไว้"
        #                                             แล้วลองโมเดลสำรอง (ซึ่งถูกตัดทันทีเช่นกัน)
        #   ตัดระหว่างอ่านสตรีมคำตอบ                 -> บรรทัด timing ลงท้าย
        #                                             outcome=ล้ม:LLMBudgetExceeded
        budget_log = [ln for ln in CAP.lines
                      if "เกินเพดานที่ตั้งไว้" in ln or "LLMBudgetExceeded" in ln]
        check("สาเหตุที่บันทึกคือเกินเพดานเวลา", bool(budget_log),
              (budget_log[0][:160] if budget_log else
               (CAP.lines[-1][:200] if CAP.lines else "ไม่มี log")))
        # เมื่อเพดานหมดแล้ว การลองโมเดลสำรองต้องไม่กินเวลาเพิ่ม (ตรวจจากเวลารวมข้างบน)
        check("ลองโมเดลสำรองหลังหมดเพดานแล้วไม่ยืดเวลาออกไป", took <= BUDGET + TOL,
              f"{took:.2f}s")
    finally:
        llm_client._connector = real
        connector_mod._DEFAULT_BUDGET_S = saved_default

    print()
    print("3. หลังเคสเกินเพดาน คำขอถัดไปต้องกลับมาตอบได้ปกติ (เพดานไม่รั่วข้ามคำขอ)")
    CAP.lines.clear()
    code, body, took = post("หลักสูตรเทคโนโลยีสารสนเทศ พ.ศ. 2566 เรียนกี่หน่วยกิต")
    check("ได้สถานะ 200", code == 200, f"code={code}")
    check("ตอบได้ มีที่มา", "ที่มา:" in body, body[:120])
    found = [m for m in SERVICE_TEXT if m in body]
    check("ไม่มีข้อความบริการขัดข้อง", not found, f"เจอ {found}")
finally:
    STOP.set()
    SERVER.shutdown()

print()
print(f"จุดตรวจ {CHECKS} จุด")
if FAILURES:
    print(f"ตก {len(FAILURES)} จุด")
    for f in FAILURES:
        print("  -", f)
    raise SystemExit(1)
print("ผ่านทั้งหมด")
