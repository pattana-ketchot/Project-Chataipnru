"""
ทดสอบเพดานเวลารวมต่อคำขอ และการบันทึกเวลาในกรณีล้ม/ยกเลิก

    cd backend && python tests/test_request_budget.py

HTTP จำลองทั้งหมด ไม่ต่อ Google ไม่ต่อฐานข้อมูล ไม่ใช้คีย์จริง
"""
import json
import logging
import sys
import time
import traceback
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import httpx

from llm.connector import (ChatMessage, LLMBudgetExceeded, LLMConnectionError, OllamaConnector,
                           budget_left_s, check_budget, http_timeout, reset_budget, start_budget)
from llm.gemini import GeminiConnector

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


MSG = [ChatMessage(role="user", content="หน่วยกิตเท่าไหร่")]
OVERLOAD = {"error": {"code": 503, "status": "UNAVAILABLE", "message": "high demand"}}


def gemini(handler, **kw) -> GeminiConnector:
    kw.setdefault("max_retries", 1)
    c = GeminiConnector(api_key="NOT-A-REAL-KEY", **kw)
    c._client = httpx.Client(base_url="https://example.test/v1beta",
                             transport=httpx.MockTransport(handler))
    return c


# ───────────── 1. ตัวช่วยนับเวลา ─────────────

def test_budget_helpers() -> None:
    check("ยังไม่ตั้งเพดาน -> ไม่จำกัด", budget_left_s() is None)
    t = start_budget(5)
    left = budget_left_s()
    check("ตั้งแล้วเหลือเวลาใกล้ค่าที่ตั้ง", left is not None and 4.5 < left <= 5.0, str(left))
    check("ยังไม่หมดเวลา -> check_budget ไม่โยน", check_budget("ทดสอบ") is None)
    reset_budget(t)
    check("คืนค่าแล้วกลับเป็นไม่จำกัด", budget_left_s() is None)

    t2 = start_budget(0.001)
    time.sleep(0.02)
    check("ตั้งเพดานติดจริง (เหลือเวลาติดลบ)",
          (budget_left_s() or 0) < 0, f"เหลือ {budget_left_s()}")
    try:
        check_budget("ทดสอบ")
        check("หมดเวลาแล้วต้องโยน", False, "ไม่โยน")
    except LLMConnectionError as e:
        check("หมดเวลาแล้วต้องโยน", True)
        check("ข้อความบอกว่าเกินเพดานและกำลังทำอะไร",
              "เกินเพดาน" in str(e) and "ทดสอบ" in str(e), str(e)[:120])
        check("เป็นชนิดย่อยของ LLMConnectionError (ผู้เรียกเดิมรับมือได้)",
              isinstance(e, LLMConnectionError))
    finally:
        reset_budget(t2)

    t3 = start_budget(0)
    check("ตั้งเพดาน 0 = ปิดการจำกัด", budget_left_s() is None)
    reset_budget(t3)


# ───────────── 2. เพดานตัดการไล่โมเดล ─────────────

def test_budget_stops_model_chain() -> None:
    """ทุกโมเดล 503 และเวลาหมดกลางทาง ต้องหยุดไล่ ไม่ใช่วนต่อจนครบ"""
    seen: list[str] = []

    def h(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path.rsplit("/", 1)[-1].split(":")[0])
        return httpx.Response(503, json=OVERLOAD)

    c = gemini(h)
    t = start_budget(0.001)
    time.sleep(0.02)
    check("ตั้งเพดานติดจริงก่อนไล่โมเดล", (budget_left_s() or 0) < 0, f"เหลือ {budget_left_s()}")
    try:
        c.chat(MSG)
        check("หมดเวลาแล้วต้องไม่ยิงโมเดลเลย", False, f"ยิงไป {seen}")
    except LLMBudgetExceeded:
        check("หมดเวลาแล้วต้องไม่ยิงโมเดลเลย", len(seen) == 0, f"ยิงไป {seen}")
    except LLMConnectionError as e:
        check("หมดเวลาแล้วต้องไม่ยิงโมเดลเลย", False, f"ได้ {type(e).__name__}: {e}")
    finally:
        reset_budget(t)


def test_budget_does_not_block_a_fast_answer() -> None:
    """เพดานต้องไม่ขัดขวางคำขอที่ตอบได้ทันตามปกติ"""
    def h(request: httpx.Request) -> httpx.Response:
        m = request.url.path.rsplit("/", 1)[-1].split(":")[0]
        if m == "gemini-3.5-flash-lite":
            return httpx.Response(503, json=OVERLOAD)
        return httpx.Response(200, json={"candidates": [
            {"content": {"parts": [{"text": "ตอบได้"}]}, "finishReason": "STOP"}]})

    c = gemini(h)
    t = start_budget(30)
    try:
        check("ตัวหลัก 503 ตัวสำรองว่าง -> ยังได้คำตอบในเพดาน", c.chat(MSG) == "ตอบได้")
        left = budget_left_s()
        check("ใช้เวลาน้อยกว่าเพดานมาก", left is not None and left > 25, str(left))
    finally:
        reset_budget(t)


def test_budget_skips_the_cooldown_wait() -> None:
    """
    ทุกโมเดลติดช่วงพัก และเวลาที่เหลือไม่พอรอ -> ต้องไม่หลับรอ

    ของเดิมจะ time.sleep จนครบ cooldown ซึ่งทำให้คำขอยาวเกินเพดานที่ตั้งไว้
    """
    def h(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json=OVERLOAD)

    c = gemini(h)
    t = start_budget(30)
    try:
        c.chat(MSG)  # รอบนี้ไล่ครบทุกโมเดลแล้วพักไว้ทั้งหมด
    except LLMConnectionError:
        pass
    finally:
        reset_budget(t)

    # รอบที่สอง: ทุกตัวยังติดช่วงพัก และเพดานเหลือน้อยกว่าเวลาที่ต้องรอ
    t2 = start_budget(3)
    t0 = time.perf_counter()
    try:
        c.chat(MSG)
        check("ต้องไม่หลับรอจนครบช่วงพัก", False, "ไม่โยน")
    except LLMConnectionError as e:
        secs = time.perf_counter() - t0
        check("ต้องไม่หลับรอจนครบช่วงพัก", secs < 2.0, f"ใช้ {secs:.1f}s · {type(e).__name__}")
        check("บอกเหตุว่าเวลาไม่พอรอ หรือเกินเพดาน",
              "ไม่พอรอ" in str(e) or "เกินเพดาน" in str(e), str(e)[:140])
    finally:
        reset_budget(t2)


def test_local_model_respects_the_budget() -> None:
    """โมเดลในเครื่องเป็นขั้นที่ช้าสุด ต้องเคารพเพดานด้วย"""
    calls: list[str] = []

    def h(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, json={"message": {"content": "ok"}})

    c = OllamaConnector()
    c._client = httpx.Client(base_url="http://example.test",
                             transport=httpx.MockTransport(h))
    t = start_budget(0.001)
    time.sleep(0.02)
    check("ตั้งเพดานติดจริงก่อนเรียกโมเดลในเครื่อง",
          (budget_left_s() or 0) < 0, f"เหลือ {budget_left_s()}")
    try:
        c.chat(MSG)
        check("หมดเวลาแล้วโมเดลในเครื่องต้องไม่ถูกเรียก", False, f"เรียกไป {calls}")
    except LLMConnectionError:
        check("หมดเวลาแล้วโมเดลในเครื่องต้องไม่ถูกเรียก", calls == [], f"เรียกไป {calls}")
    finally:
        reset_budget(t)

    t2 = start_budget(30)
    try:
        check("ยังมีเวลา -> โมเดลในเครื่องทำงานปกติ", c.chat(MSG) == "ok")
    finally:
        reset_budget(t2)


# ───────────── 3. บรรทัดเวลาต้องไม่กลบข้อผิดพลาดเดิม ─────────────

def test_timing_log_never_masks_the_real_error() -> None:
    import app.services.chat as C

    class Boom(RuntimeError):
        pass

    broken = type("Broken", (), {"parts": lambda self: 1 / 0, "elapsed_ms": lambda self: 0.0})()
    p = C.Prepared(session_id=None, status="answered", search_query="q", best_score=0.0,
                   citations=[], canned="x", messages=[], stages=broken)
    try:
        C._log_timing("/chat", C._Stages(), p, "คำถาม", "ok")
        check("บรรทัดเวลาที่ล้มเองต้องไม่โยนออกมา", True)
    except Exception as e:  # noqa: BLE001
        check("บรรทัดเวลาที่ล้มเองต้องไม่โยนออกมา", False, f"{type(e).__name__}: {e}")

    # p เป็น None ได้เมื่อ prepare_answer ล้มก่อนคืนค่า
    try:
        C._log_timing("/chat", C._Stages(), None, "คำถาม", "ล้ม:Boom")
        check("รับ p=None ได้", True)
    except Exception as e:  # noqa: BLE001
        check("รับ p=None ได้", False, f"{type(e).__name__}: {e}")


def test_cancelled_request_is_recorded() -> None:
    """
    ผู้ใช้ปิดแท็บกลางคำตอบ -> generator ถูกปิด -> GeneratorExit

    ต้องบันทึกบรรทัดเวลาไว้ด้วย outcome ที่บอกว่าถูกยกเลิก และต้องไม่กลืน GeneratorExit
    """
    import app.services.chat as C

    logged: list[str] = []

    class Catch(logging.Handler):
        def emit(self, record):
            # getMessage() ใส่ args ให้เรียบร้อยแล้ว การ % ซ้ำจะโยนข้อผิดพลาด
            logged.append(record.getMessage())

    handler = Catch()
    C.logger.addHandler(handler)
    C.logger.setLevel(logging.INFO)

    outer = C._Stages()
    p = C.Prepared(session_id=None, status="answered", search_query="q", best_score=0.0,
                   citations=[], canned="x", messages=[])

    def fake_stream():
        outcome = "ok"
        try:
            yield "ชิ้นแรก"
            yield "ชิ้นสอง"
        except BaseException as exc:  # noqa: BLE001 — โครงเดียวกับ stream_answer
            outcome = f"ล้ม:{type(exc).__name__}"
            raise
        finally:
            C._log_timing("/chat-web", outer, p, "คำถาม", outcome)

    gen = fake_stream()
    next(gen)          # รับชิ้นแรกแล้วเลิกอ่าน
    gen.close()        # เหมือนผู้ใช้ปิดแท็บ

    C.logger.removeHandler(handler)
    timing = [m for m in logged if m.startswith("timing")]
    check("มีบรรทัดเวลาแม้คำขอถูกยกเลิก", bool(timing), str(logged)[:160])
    check("outcome บอกว่าถูกยกเลิก (GeneratorExit)",
          bool(timing) and "GeneratorExit" in timing[0], timing[0][:160] if timing else "")


# ───────────── 4. บังคับเพดานกับคำขอ HTTP ที่กำลังค้าง ─────────────

def test_http_timeout_follows_the_remaining_budget() -> None:
    """timeout ของคำขอ HTTP แต่ละครั้งต้องไม่เกินเวลาที่เหลือ"""
    check("ไม่ตั้งเพดาน -> ใช้ค่าตั้งต้น", http_timeout(120.0, "x") == 120.0)
    t = start_budget(5)
    try:
        got = http_timeout(120.0, "x")
        check("เหลือ 5 วินาที -> timeout ต้องไม่เกิน 5", got <= 5.0, str(got))
        check("และต้องมากกว่า 0", got > 0, str(got))
    finally:
        reset_budget(t)
    t2 = start_budget(0.001)
    time.sleep(0.02)
    try:
        http_timeout(120.0, "x")
        check("หมดเวลาแล้ว http_timeout ต้องโยน", False, "ไม่โยน")
    except LLMConnectionError:
        check("หมดเวลาแล้ว http_timeout ต้องโยน", True)
    finally:
        reset_budget(t2)


def test_hanging_endpoint_is_cut_at_the_remaining_budget() -> None:
    """
    เริ่มคำขอตอนเหลือ 1 วินาที — timeout ที่ส่งไปกับคำขอ HTTP ต้องถูกบีบตามเวลาที่เหลือ
    ไม่ใช่ timeout เดิมของตัวเชื่อมต่อ (120 วินาที)

    นี่คือกรณีที่เจ้าของโครงการชี้ว่าเพดานยังไม่บังคับจริง · ตรวจจากค่า timeout ที่ httpx
    แนบไปกับคำขอ (request.extensions) เพราะ MockTransport ไม่มี I/O จริงจึงจับเวลาไม่ได้
    """
    seen_timeouts: list[float | None] = []

    def h(request: httpx.Request) -> httpx.Response:
        tmo = request.extensions.get("timeout") or {}
        seen_timeouts.append(tmo.get("read"))
        return httpx.Response(200, json={"message": {"content": "ok"}})

    c = OllamaConnector(timeout_s=120, max_retries=0)
    c._client = httpx.Client(base_url="http://example.test",
                             transport=httpx.MockTransport(h), timeout=120)

    t = start_budget(1.0)
    try:
        c.chat(MSG)
    finally:
        reset_budget(t)
    check("มีการส่ง timeout ไปกับคำขอ", len(seen_timeouts) == 1, str(seen_timeouts))
    got = seen_timeouts[0]
    check("timeout ถูกบีบให้ไม่เกินเวลาที่เหลือ 1 วินาที",
          got is not None and got <= 1.0, f"ได้ {got}")
    check("ไม่ใช่ timeout เดิม 120 วินาที", got != 120, f"ได้ {got}")

    # เทียบกับกรณีไม่ตั้งเพดาน — ต้องได้ค่าเดิมของตัวเชื่อมต่อ
    seen_timeouts.clear()
    c.chat(MSG)
    check("ไม่ตั้งเพดาน -> ใช้ timeout เดิมของตัวเชื่อมต่อ",
          seen_timeouts and seen_timeouts[0] == 120, str(seen_timeouts))


def test_slow_trickling_stream_is_cut_by_the_budget() -> None:
    """
    สตรีมที่ทยอยส่งข้อมูลเรื่อย ๆ ไม่เคยชน read timeout แต่ยืดเวลารวมได้ไม่จำกัด
    ต้องถูกตัดด้วยการตรวจเพดานระหว่างอ่าน
    """
    def trickle(request: httpx.Request) -> httpx.Response:
        def gen():
            for i in range(200):
                time.sleep(0.05)   # ส่งทีละน้อยแต่ต่อเนื่อง — read timeout ไม่เคยชน
                payload = {"message": {"content": "ชิ้น" + str(i)}}
                yield (json.dumps(payload, ensure_ascii=False) + chr(10)).encode()
        return httpx.Response(200, content=gen(),
                              headers={"content-type": "application/x-ndjson"})

    c = OllamaConnector(timeout_s=120)
    c._client = httpx.Client(base_url="http://example.test",
                             transport=httpx.MockTransport(trickle))
    t = start_budget(1.0)
    t0 = time.perf_counter()
    got = []
    try:
        for chunk in c.chat_stream(MSG):
            got.append(chunk)
        check("สตรีมที่ยืดเวลาต้องถูกตัด", False, f"อ่านจบเองโดยได้ {len(got)} ชิ้น")
    except LLMConnectionError:
        secs = time.perf_counter() - t0
        check("สตรีมที่ยืดเวลาต้องถูกตัดเมื่อเกินเพดาน", secs < 4.0, f"ใช้ {secs:.1f}s")
        check("ได้ข้อความบางส่วนก่อนถูกตัด (พิสูจน์ว่าสตรีมเดินจริง)", len(got) > 0, f"{len(got)} ชิ้น")
        check("ไม่ได้อ่านครบทั้ง 200 ชิ้น", len(got) < 200, f"{len(got)} ชิ้น")
    finally:
        reset_budget(t)


def test_retry_plus_cooldown_cannot_exceed_the_budget() -> None:
    """การลองซ้ำบวกการพักรอรวมกันต้องไม่เกินเพดาน"""
    calls: list[float] = []

    def h(request: httpx.Request) -> httpx.Response:
        calls.append(time.perf_counter())
        return httpx.Response(503, json=OVERLOAD)

    c = gemini(h, max_retries=2)
    t = start_budget(2.0)
    t0 = time.perf_counter()
    try:
        c.chat(MSG)
        check("ทุกโมเดล 503 ภายใต้เพดาน -> ต้องโยน", False, "ไม่โยน")
    except LLMConnectionError as e:
        secs = time.perf_counter() - t0
        check("retry + cooldown รวมกันไม่เกินเพดาน (เผื่อ 1 วินาที)", secs < 3.0,
              f"ใช้ {secs:.1f}s · ยิง {len(calls)} ครั้ง · {type(e).__name__}")
    finally:
        reset_budget(t)


def test_context_is_reset_on_success_failure_and_cancel() -> None:
    """คืนค่า context ทุกทางออก — สำเร็จ ล้ม และยกเลิก"""
    def ok(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": {"content": "ok"}})

    c = OllamaConnector()
    c._client = httpx.Client(base_url="http://example.test", transport=httpx.MockTransport(ok))

    t = start_budget(30)
    c.chat(MSG)
    reset_budget(t)
    check("สำเร็จแล้วคืนค่าได้", budget_left_s() is None)

    def boom(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "x"})

    c2 = OllamaConnector()
    c2._client = httpx.Client(base_url="http://example.test", transport=httpx.MockTransport(boom))
    t2 = start_budget(30)
    try:
        c2.chat(MSG)
    except LLMConnectionError:
        pass
    finally:
        reset_budget(t2)
    check("ล้มแล้วคืนค่าได้", budget_left_s() is None)

    # ยกเลิก: เลียนโครงของ stream_answer ที่คืนค่าใน finally
    def flow():
        tok = start_budget(30)
        try:
            yield "a"
            yield "b"
        finally:
            reset_budget(tok)

    g = flow()
    next(g)
    g.close()
    check("ยกเลิกกลางคันแล้วคืนค่าได้", budget_left_s() is None)


def test_exception_identity_through_the_real_import_path() -> None:
    """
    ชนิดข้อยกเว้นต้องเป็นตัวเดียวกันเมื่อมองจากเส้นทาง import ที่โค้ดจริงใช้

    แพ็กเกจ llm ถูก import ได้สองทาง (llm.connector และผ่าน sys.path ที่ llm_client
    เติมให้) ถ้ากลายเป็นคลาสสองตัว การดักจับในโค้ดจริงจะพลาด
    """
    import app.services.chat as C
    from llm.connector import LLMBudgetExceeded as Direct

    seen = C.LLMConnectionError
    check("LLMConnectionError ที่ chat.py ใช้ เป็นตัวแม่ของ LLMBudgetExceeded",
          issubclass(Direct, seen), f"{Direct} vs {seen}")

    mod = sys.modules.get("llm.connector")
    check("มี llm.connector ใน sys.modules", mod is not None)
    check("คลาสจาก sys.modules เป็นตัวเดียวกับที่ import ตรง",
          mod is not None and mod.LLMBudgetExceeded is Direct)

    raised = None
    try:
        t = start_budget(0.001)
        time.sleep(0.02)
        check_budget("ทดสอบเส้นทาง import")
    except C.LLMConnectionError as e:
        raised = e
    finally:
        reset_budget(t)
    check("โค้ดจริงที่ดักจับ LLMConnectionError จับข้อยกเว้นเพดานได้",
          isinstance(raised, Direct), str(type(raised)))


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        print(t.__name__)
        try:
            t()
        except Exception:  # noqa: BLE001
            FAILURES.append(f"{t.__name__} โยน exception\n{traceback.format_exc()}")
            print(f"  [ตก]  ชุดนี้ล้มกลางคัน\n{traceback.format_exc()}")
        print()
    print(f"ชุดทดสอบ {len(tests)} ชุด · จุดตรวจ {CHECKS} จุด")
    if FAILURES:
        print(f"ตก {len(FAILURES)} จุด")
        for f in FAILURES:
            print("  -", f)
        return 1
    print("ผ่านทั้งหมด")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
