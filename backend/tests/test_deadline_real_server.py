"""
ยืนยันเพดานเวลารวมด้วย **HTTP server จริง** ที่ค้างจริงและสตรีมจริง

    cd backend && python tests/test_deadline_real_server.py

ต่างจาก test_request_budget.py ที่ใช้ MockTransport (ไม่มี I/O จริง timeout จึงไม่ทำงาน
และตรวจได้แค่ค่า request.extensions) · ชุดนี้เปิดเซิร์ฟเวอร์จริงบน 127.0.0.1 แล้ววัดเวลา
ตั้งแต่เริ่มจนหยุดด้วย perf_counter

สามพฤติกรรมของปลายทางที่ทดสอบ
    /hang          รับคำขอแล้วไม่ตอบอะไรเลย
    /trickle       ส่งข้อมูลทีละน้อยต่อเนื่องไม่หยุด (read timeout ไม่เคยชน)
    /then-silent   ส่งข้อมูลก้อนแรกแล้วเงียบไปเฉย ๆ

ค่าคลาดเคลื่อนที่ยอมรับ
    เพดานสั้น (3 วินาที)  ต้องจบใน 3 + 2.5 = 5.5 วินาที
    เพดานจริง (30 วินาที) ต้องจบใน 30 + 3 = 33 วินาที และไม่เร็วกว่า 27 วินาที
ที่ต้องเผื่อเพราะ: การตรวจเพดานเกิดเป็นจุด ๆ ไม่ใช่ตัวจับเวลาที่ขัดจังหวะได้ทุกเสี้ยววินาที
และ httpx ต้องใช้เวลาปิดการเชื่อมต่อ
"""
import json
import socket
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import httpx

from llm.connector import (ChatMessage, LLMConnectionError, OllamaConnector, budget_left_s,
                           reset_budget, start_budget)

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


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_a):  # เงียบ ไม่ให้ log ของเซิร์ฟเวอร์ปนกับผลทดสอบ
        pass

    def _read_body(self):
        n = int(self.headers.get("content-length") or 0)
        if n:
            self.rfile.read(n)

    def do_POST(self):  # noqa: N802
        self._read_body()
        path = self.path
        if path.startswith("/hang"):
            # รับคำขอแล้วไม่ตอบอะไรเลย — client ต้องเลิกเอง
            while not STOP.wait(0.2):
                pass
            return
        if path.startswith("/trickle"):
            self.send_response(200)
            self.send_header("content-type", "application/x-ndjson")
            self.send_header("transfer-encoding", "chunked")
            self.end_headers()
            i = 0
            while not STOP.is_set():
                line = json.dumps({"message": {"content": f"c{i}"}}) + "\n"
                data = line.encode()
                try:
                    self.wfile.write(b"%x\r\n%s\r\n" % (len(data), data))
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    return
                i += 1
                time.sleep(0.2)
            return
        if path.startswith("/then-silent"):
            self.send_response(200)
            self.send_header("content-type", "application/x-ndjson")
            self.send_header("transfer-encoding", "chunked")
            self.end_headers()
            data = (json.dumps({"message": {"content": "ก้อนแรก"}}) + "\n").encode()
            try:
                self.wfile.write(b"%x\r\n%s\r\n" % (len(data), data))
                self.wfile.flush()
            except OSError:
                return
            # ส่งก้อนแรกแล้วเงียบ — ไม่ปิดการเชื่อมต่อ ไม่ส่งอะไรอีก
            while not STOP.wait(0.2):
                pass
            return
        self.send_response(404)
        self.send_header("content-length", "0")
        self.end_headers()


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


PORT = free_port()
SERVER = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
SERVER.daemon_threads = True
threading.Thread(target=SERVER.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{PORT}"
print(f"เปิดเซิร์ฟเวอร์ทดสอบที่ {BASE}\n")

MSG = [ChatMessage(role="user", content="หน่วยกิตเท่าไหร่")]


def connector(path: str, timeout_s: float = 120, retries: int = 0) -> OllamaConnector:
    """ตัวเชื่อมต่อที่ยิงไปยังเส้นทางที่ระบุของเซิร์ฟเวอร์ทดสอบ"""
    c = OllamaConnector(base_url=BASE + path, timeout_s=timeout_s, max_retries=retries)
    return c


def measure(fn) -> tuple[float, BaseException | None]:
    t0 = time.perf_counter()
    err = None
    try:
        fn()
    except BaseException as exc:  # noqa: BLE001
        err = exc
    return time.perf_counter() - t0, err


SHORT = 3.0
SHORT_TOL = 2.5


def test_hanging_server_stops_near_the_budget() -> None:
    """ปลายทางรับคำขอแล้วไม่ตอบอะไรเลย — ต้องเลิกใกล้เพดาน ไม่รอ timeout 120 วินาที"""
    c = connector("/hang", timeout_s=120)
    t = start_budget(SHORT)
    secs, err = measure(lambda: c.chat(MSG))
    reset_budget(t)
    check("ปลายทางค้าง: หยุดใกล้เพดาน", secs <= SHORT + SHORT_TOL,
          f"ใช้ {secs:.1f}s (เพดาน {SHORT}s เผื่อ {SHORT_TOL}s)")
    check("ปลายทางค้าง: ไม่รอ timeout 120 วินาที", secs < 30, f"ใช้ {secs:.1f}s")
    check("ปลายทางค้าง: โยนข้อผิดพลาดออกมา", isinstance(err, LLMConnectionError),
          f"{type(err).__name__ if err else 'ไม่โยน'}")


def test_trickling_stream_stops_near_the_budget() -> None:
    """สตรีมส่งทีละน้อยต่อเนื่อง — read timeout ไม่เคยชน ต้องถูกตัดด้วยเพดาน"""
    c = connector("/trickle", timeout_s=120)
    got: list[str] = []

    def run():
        for chunk in c.chat_stream(MSG):
            got.append(chunk)

    t = start_budget(SHORT)
    secs, err = measure(run)
    reset_budget(t)
    check("สตรีมต่อเนื่อง: หยุดใกล้เพดาน", secs <= SHORT + SHORT_TOL,
          f"ใช้ {secs:.1f}s · ได้ {len(got)} ชิ้น")
    check("สตรีมต่อเนื่อง: ได้ข้อมูลจริงก่อนถูกตัด", len(got) > 0, f"{len(got)} ชิ้น")
    check("สตรีมต่อเนื่อง: โยนข้อผิดพลาดออกมา", isinstance(err, LLMConnectionError),
          f"{type(err).__name__ if err else 'ไม่โยน'}")


def test_non_streaming_call_against_trickle() -> None:
    """
    **ทางที่ไม่สตรีมก็ต้องถูกเพดานตัด** — ช่องที่ชุดนี้เคยพลาด

    ก่อนหน้านี้ชุดนี้ทดสอบ /trickle กับ chat_stream() อย่างเดียว ส่วน chat() และ
    embed() ซึ่งเป็นทางที่ขั้นเขียนคำถามใหม่ ขั้นตรวจเอกสาร และการฝังเวกเตอร์ใช้
    ยังเรียก client.post() ตรงๆ อยู่ · timeout ของ httpx เป็นเวลารอข้อมูลก้อนถัดไป
    ปลายทางที่ทยอยส่งไม่หยุดจึงทำให้คำขอค้างไม่จำกัด แม้ตั้งเพดานรวมไว้แล้ว
    เจอจริงเมื่อ 14 ต.ค. 2569: คำขอ /chat-web หนึ่งคำขอค้างเกินสิบนาทีด้วยเพดาน 6 วินาที
    """
    c = connector("/trickle", timeout_s=120)

    t = start_budget(SHORT)
    secs, err = measure(lambda: c.chat(MSG))
    reset_budget(t)
    check("ไม่สตรีม (chat): หยุดใกล้เพดาน", secs <= SHORT + SHORT_TOL,
          f"ใช้ {secs:.1f}s (เพดาน {SHORT}s เผื่อ {SHORT_TOL}s)")
    check("ไม่สตรีม (chat): ไม่รอ timeout 120 วินาที", secs < 30, f"ใช้ {secs:.1f}s")
    check("ไม่สตรีม (chat): โยนข้อผิดพลาดออกมา", isinstance(err, LLMConnectionError),
          f"{type(err).__name__ if err else 'ไม่โยน'}")

    t = start_budget(SHORT)
    secs, err = measure(lambda: c.embed(["ทดสอบ"]))
    reset_budget(t)
    check("ไม่สตรีม (embed): หยุดใกล้เพดาน", secs <= SHORT + SHORT_TOL, f"ใช้ {secs:.1f}s")
    check("ไม่สตรีม (embed): โยนข้อผิดพลาดออกมา", isinstance(err, LLMConnectionError),
          f"{type(err).__name__ if err else 'ไม่โยน'}")


def test_stream_that_goes_silent_after_first_chunk() -> None:
    """
    ส่งข้อมูลก่อน deadline แล้วเงียบ — กรณีที่เจ้าของโครงการระบุ

    ก้อนแรกมาถึงแล้ว (started=True) แล้วปลายทางเงียบไปเฉย ๆ โดยไม่ปิดการเชื่อมต่อ
    ต้องเลิกใกล้เพดาน ไม่ค้างรอจน read timeout ของตัวเชื่อมต่อ
    """
    c = connector("/then-silent", timeout_s=120)
    got: list[str] = []

    def run():
        for chunk in c.chat_stream(MSG):
            got.append(chunk)

    t = start_budget(SHORT)
    secs, err = measure(run)
    reset_budget(t)
    check("ส่งแล้วเงียบ: ได้ก้อนแรกจริง", len(got) >= 1, f"ได้ {got[:2]}")
    check("ส่งแล้วเงียบ: หยุดใกล้เพดาน", secs <= SHORT + SHORT_TOL,
          f"ใช้ {secs:.1f}s (เพดาน {SHORT}s เผื่อ {SHORT_TOL}s)")
    check("ส่งแล้วเงียบ: ไม่รอ timeout 120 วินาที", secs < 30, f"ใช้ {secs:.1f}s")


def test_real_thirty_second_budget() -> None:
    """
    เพดานจริงที่ระบบใช้คือ 30 วินาที — ยืนยันกับปลายทางที่ค้างจริง

    เทสต์นี้ใช้เวลาราว 30 วินาทีโดยธรรมชาติของสิ่งที่วัด
    """
    c = connector("/hang", timeout_s=120)
    t = start_budget(30.0)
    secs, err = measure(lambda: c.chat(MSG))
    reset_budget(t)
    check("เพดาน 30 วินาที: จบไม่เกิน 33 วินาที", secs <= 33.0, f"ใช้ {secs:.1f}s")
    check("เพดาน 30 วินาที: ไม่เลิกเร็วกว่า 27 วินาที (ไม่ตัดก่อนเวลา)",
          secs >= 27.0, f"ใช้ {secs:.1f}s")
    check("เพดาน 30 วินาที: โยนข้อผิดพลาด", isinstance(err, LLMConnectionError),
          f"{type(err).__name__ if err else 'ไม่โยน'}")


def test_no_budget_means_the_connector_timeout_applies() -> None:
    """ไม่ตั้งเพดาน -> ใช้ timeout ของตัวเชื่อมต่อตามเดิม (ตั้งสั้นไว้เพื่อให้เทสต์เร็ว)"""
    check("ไม่มีเพดานค้างจากเทสต์ก่อน", budget_left_s() is None, str(budget_left_s()))
    c = connector("/hang", timeout_s=2)
    secs, err = measure(lambda: c.chat(MSG))
    check("ไม่ตั้งเพดาน: เลิกตาม timeout ของตัวเชื่อมต่อ", 1.0 <= secs <= 6.0, f"ใช้ {secs:.1f}s")
    check("ไม่ตั้งเพดาน: ยังโยนข้อผิดพลาด", isinstance(err, LLMConnectionError),
          f"{type(err).__name__ if err else 'ไม่โยน'}")


def main() -> int:
    order = [
        test_hanging_server_stops_near_the_budget,
        test_trickling_stream_stops_near_the_budget,
        test_non_streaming_call_against_trickle,
        test_stream_that_goes_silent_after_first_chunk,
        test_no_budget_means_the_connector_timeout_applies,
        test_real_thirty_second_budget,
    ]
    try:
        for t in order:
            print(t.__name__)
            try:
                t()
            except Exception:  # noqa: BLE001
                FAILURES.append(f"{t.__name__} ล้มกลางคัน\n{traceback.format_exc()}")
                print(f"  [ตก]  ล้มกลางคัน\n{traceback.format_exc()}")
            print()
    finally:
        STOP.set()
        SERVER.shutdown()

    print(f"ชุดทดสอบ {len(order)} ชุด · จุดตรวจ {CHECKS} จุด")
    if FAILURES:
        print(f"ตก {len(FAILURES)} จุด")
        for f in FAILURES:
            print("  -", f)
        return 1
    print("ผ่านทั้งหมด")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
