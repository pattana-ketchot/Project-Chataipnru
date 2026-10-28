"""
ตัวสำรองในเครื่องต้องมีเวลาเหลือให้ใช้จริง ไม่ใช่ถูกเพดานเวลาปฏิเสธก่อนยิงคำขอแรก

    cd backend && python tests/test_local_fallback_gets_time.py

HTTP จำลองทั้งหมด ไม่ต่อ Google ไม่ต่อ Ollama ไม่ต่อฐานข้อมูล ไม่ใช้คีย์จริง

ทำไมต้องมีชุดนี้
---------------
ตัวนับของ production เมื่อ 28 ต.ค. 2569 บอกว่า fallback_local_attempt = 10 และ
fallback_local_failed = 10 คือตกมาที่ตัวสำรองสิบครั้งแล้วล้มทั้งสิบครั้ง

ชุดทดสอบเดิมมองไม่เห็นเพราะตัวแทนของเจ้าหลักในชุดทดสอบ (เช่น AllModelsDown ใน
test_model_outage_n1.py) โยนข้อผิดพลาดทันทีโดยไม่กินเวลาเลย ตัวสำรองจึงได้เพดาน
เวลาเต็มจำนวนไปใช้ ซึ่งไม่ใช่สิ่งที่เกิดบนระบบจริง — ของจริงเจ้าหลักใช้เวลาไปก่อน
(ไล่โมเดล รอให้พ้นช่วงพัก) แล้วจึงล้มตอนเพดานเวลาหมด ตัวสำรองที่รับช่วงต่อจึงเจอ
เพดานที่หมดแล้ว และถูกปฏิเสธก่อนยิงคำขอแรก

ชุดนี้จึงเลียน "เจ้าหลักกินเวลาจนหมดเพดานแล้วค่อยล้ม" ซึ่งเป็นพฤติกรรมจริง
"""
import json
import os
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# ชุดนี้ไม่แตะฐานข้อมูลเลย แต่ app.services.llm_usage อ่านค่าตั้งต้นตอน import
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://unused:unused@127.0.0.1:1/unused")
os.environ.setdefault("JWT_SECRET", "ชุดทดสอบไม่ได้ออก token")

import httpx

from llm.connector import (ChatMessage, LLMConnectionError, OllamaConnector, budget_left_s,
                           check_budget, reset_budget, start_budget)

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


MSG = [ChatMessage(role="user", content="สาขานี้มีวิชาบังคับอะไรบ้าง")]
LOCAL_REPLY = '{"can_answer": true}'


class BurnsTheBudgetThenFails:
    """
    เจ้าหลักที่ใช้เวลาไปก่อนแล้วจึงล้ม — แบบเดียวกับที่ GeminiConnector ทำจริง

    ของจริงเวลาหมดไปกับการไล่โมเดลสำรองและการรอให้โมเดลพ้นช่วงพัก (ดู
    GeminiConnector._models_to_try ซึ่ง sleep ได้ถึง max_cooldown_wait_s = 75
    วินาที โดยมีเพดานเวลารวมเป็นตัวตัด) สุดท้ายจึงโยน LLMBudgetExceeded ออกมา
    ซึ่งเป็นลูกของ LLMConnectionError จึงถูกดักเป็น "เจ้าหลักตอบไม่ได้" ตามปกติ
    """

    answer_token_cap = 2048
    chat_model = "gemini-จำลอง"

    def __init__(self) -> None:
        self.calls = 0

    def _burn(self):
        self.calls += 1
        while (left := budget_left_s()) is not None and left > 0:
            time.sleep(min(left, 0.05))
        check_budget("รอให้โมเดลพ้นช่วงพัก")  # โยน LLMBudgetExceeded เมื่อถึงตรงนี้
        raise LLMConnectionError("โมเดล Gemini ทุกตัวใช้ไม่ได้")

    def chat(self, *a, **k):
        return self._burn()

    def chat_stream(self, *a, **k):
        return self._burn()


def mock_ollama(handler) -> OllamaConnector:
    """โมเดลในเครื่องที่ตอบผ่าน MockTransport — ไม่ต้องมี Ollama จริง"""
    c = OllamaConnector(base_url="http://ollama.test", chat_model="qwen2.5:3b", max_retries=0)
    c._client = httpx.Client(base_url="http://ollama.test",
                             transport=httpx.MockTransport(handler))
    return c


def split(primary, fallback):
    """ประกอบ _SplitConnector เองแทนการเรียก get_llm_connector เพื่อไม่ต้องมีคีย์จริง"""
    from app.services.llm_client import _SplitConnector
    return _SplitConnector(fallback, primary)


# ───────────── 1. เส้นทางไม่สตรีม ─────────────

def test_fallback_is_reached_with_time_to_spare() -> None:
    """
    เจ้าหลักกินเพดานเวลาจนหมดแล้วล้ม ตัวสำรองต้องยังได้ยิงคำขอจริง

    นี่คือข้อที่ล้มก่อนแก้ — ตัวสำรองถูก check_budget ปฏิเสธก่อนถึง HTTP
    """
    from app.services import llm_usage
    llm_usage.reset_for_test()
    seen: list[float] = []

    def answers(request: httpx.Request) -> httpx.Response:
        seen.append(budget_left_s() or 0.0)
        return httpx.Response(200, json={"message": {"role": "assistant", "content": LOCAL_REPLY}})

    primary = BurnsTheBudgetThenFails()
    conn = split(primary, mock_ollama(answers))
    start_budget(2.0)
    try:
        out = conn.chat(MSG, temperature=0.0, json_mode=True)
        err = ""
    except LLMConnectionError as e:
        out, err = "", f"{type(e).__name__}: {e}"
    finally:
        reset_budget()

    check("เจ้าหลักถูกเรียกจริง", primary.calls == 1, f"calls={primary.calls}")
    check("ตัวสำรองได้ยิงคำขอจริง", len(seen) == 1, f"ยิงไป {len(seen)} ครั้ง · err={err}")
    check("ตัวสำรองได้เวลาไปใช้มากกว่าศูนย์", bool(seen) and seen[0] > 0,
          f"เหลือ {seen[0] if seen else 0:.2f} วินาทีตอนถูกเรียก")
    check("ได้คำตอบจากตัวสำรอง", out == LOCAL_REPLY, f"out={out!r} err={err}")

    counted = {event: n for (_day, event), n in llm_usage.pending_snapshot().items()}
    check("นับว่าตัวสำรองตอบสำเร็จ", counted.get("fallback_local_ok") == 1, str(counted))
    check("ไม่นับว่าตัวสำรองล้ม", "fallback_local_failed" not in counted, str(counted))


# ───────────── 2. เส้นทางสตรีม ─────────────

def test_stream_fallback_is_reached_with_time_to_spare() -> None:
    """เส้นทางสตรีมต้องกันเวลาให้ตัวสำรองเหมือนกัน — หน้าเว็บใช้เส้นทางนี้"""
    from app.services import llm_usage
    llm_usage.reset_for_test()
    seen: list[float] = []

    def streams(request: httpx.Request) -> httpx.Response:
        seen.append(budget_left_s() or 0.0)
        body = json.dumps({"message": {"content": "คำตอบจากโมเดลในเครื่อง"}, "done": True})
        return httpx.Response(200, content=(body + "\n").encode())

    primary = BurnsTheBudgetThenFails()
    conn = split(primary, mock_ollama(streams))
    start_budget(2.0)
    try:
        chunks = list(conn.chat_stream(MSG, temperature=0.0))
        err = ""
    except LLMConnectionError as e:
        chunks, err = [], f"{type(e).__name__}: {e}"
    finally:
        reset_budget()

    check("ตัวสำรองได้ยิงคำขอสตรีมจริง", len(seen) == 1, f"ยิงไป {len(seen)} ครั้ง · err={err}")
    check("ได้ตัวอักษรจากตัวสำรอง", chunks == ["คำตอบจากโมเดลในเครื่อง"], f"{chunks!r} err={err}")


# ───────────── 3. เพดานรวมยังต้องทำงาน ─────────────

def test_total_wait_stays_bounded() -> None:
    """
    กันเวลาให้ตัวสำรองต้องไม่กลายเป็นการต่อเวลาคำขอไม่จำกัด

    เพดานเวลารวมมีไว้กันคำขอที่ผู้ใช้รอเจ็ดนาที (13 ต.ค. 2569) การกันเวลาจึงต้อง
    แบ่งจากเพดานเดิม ไม่ใช่เพิ่มเพดานใหม่ทับ
    """
    def hangs(request: httpx.Request) -> httpx.Response:
        while (left := budget_left_s()) is not None and left > 0:
            time.sleep(min(left, 0.05))
        raise httpx.ReadTimeout("โมเดลในเครื่องไม่ยอมตอบ", request=request)

    primary = BurnsTheBudgetThenFails()
    conn = split(primary, mock_ollama(hangs))
    t0 = time.monotonic()
    start_budget(2.0)
    try:
        conn.chat(MSG, temperature=0.0)
        raised = ""
    except LLMConnectionError as e:
        raised = type(e).__name__
    finally:
        reset_budget()
    spent = time.monotonic() - t0

    check("ตัวสำรองที่ค้างก็ยังล้มในที่สุด", raised != "", f"raised={raised!r}")
    check("เวลารวมไม่เกินเพดานที่ตั้งไว้มากนัก", spent < 4.0, f"ใช้ไป {spent:.1f} วินาที")


# ───────────── 4. สตรีมที่ถูกปั๊มทีละ step เหมือน stream_answer ─────────────

def test_stream_survives_being_pumped_step_by_step() -> None:
    """
    เส้นทางจริงตั้งเพดานเดิมซ้ำทุก step การกันเวลาต้องยังได้ผลใต้เงื่อนไขนั้น

    stream_answer เรียก apply_budget(deadline) ก่อน next() ทุกครั้ง เพราะ Starlette
    ปั๊ม generator ทีละ step และแต่ละ step ได้ "สำเนาใหม่" ของบริบท (ดู
    connector.start_budget) การตั้ง ContextVar ไว้ใน generator จึงถูกทับได้ทุก step
    ชุดนี้ปั๊มแบบเดียวกันเพื่อให้เห็นพฤติกรรมนั้น แทนการเรียก list() รอบเดียวซึ่ง
    ทำงานในบริบทเดียวและมองไม่เห็นปัญหา
    """
    from llm.connector import apply_budget
    seen: list[float] = []

    def streams(request: httpx.Request) -> httpx.Response:
        seen.append(budget_left_s() or 0.0)
        body = json.dumps({"message": {"content": "คำตอบจากโมเดลในเครื่อง"}, "done": True})
        return httpx.Response(200, content=(body + "\n").encode())

    primary = BurnsTheBudgetThenFails()
    conn = split(primary, mock_ollama(streams))
    deadline = start_budget(2.0)
    chunks: list[str] = []
    inner = conn.chat_stream(MSG, temperature=0.0)
    try:
        while True:
            apply_budget(deadline)  # เหมือนที่ stream_answer ทำก่อนทุก step
            try:
                chunks.append(next(inner))
            except StopIteration:
                break
        err = ""
    except LLMConnectionError as e:
        err = f"{type(e).__name__}: {e}"
    finally:
        inner.close()
        reset_budget()

    check("ตัวสำรองได้ยิงคำขอจริงแม้เพดานถูกตั้งซ้ำทุก step", len(seen) == 1,
          f"ยิงไป {len(seen)} ครั้ง · err={err}")
    check("ได้ตัวอักษรจากตัวสำรอง", chunks == ["คำตอบจากโมเดลในเครื่อง"], f"{chunks!r} err={err}")


def main() -> int:
    for fn in (test_fallback_is_reached_with_time_to_spare,
               test_stream_fallback_is_reached_with_time_to_spare,
               test_total_wait_stays_bounded,
               test_stream_survives_being_pumped_step_by_step):
        print(f"\n{fn.__name__}")
        fn()
    print(f"\nตรวจ {CHECKS} ข้อ · ตก {len(FAILURES)} ข้อ")
    for f in FAILURES:
        print(f"  - {f}")
    # ต้องพิมพ์คำว่า "ผ่านทั้งหมด" ด้วย เพราะ deploy_backend.sh ตัดสินว่าชุดไหนผ่าน
    # จากการ grep คำนี้ใน log ไม่ได้ดูรหัสออกของโปรเซส — ชุดอื่นทุกชุดพิมพ์แบบนี้
    if not FAILURES:
        print("ผ่านทั้งหมด")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
