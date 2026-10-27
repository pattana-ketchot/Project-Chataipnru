"""
ทดสอบว่า 503 ของ Gemini ทำให้ย้ายไปโมเดลสำรอง ไม่ใช่ตกไปใช้โมเดลในเครื่อง

    cd backend && python tests/test_gemini_overload_fallback.py

ใช้ HTTP จำลองทั้งหมด ไม่ต่อ Google ไม่ใช้คีย์จริง ไม่ต่อฐานข้อมูล

ที่มา: 13 ต.ค. 2569 `gemini-3.5-flash-lite` ตอบ 503 "This model is currently
experiencing high demand" ทุกครั้ง 15/15 ขณะที่ `gemini-3.5-flash` ตอบ 200 ใน 1.5 วินาที
แต่โค้ดย้ายโมเดลเมื่อเจอ 429 เท่านั้น คำขอจึงตกไปใช้ qwen บน CPU (27 วินาทีต่อครั้ง)
"""
import os
import sys
import traceback
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import httpx

from llm.connector import ChatMessage, LLMConnectionError
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


OVERLOAD_BODY = {
    "error": {"code": 503, "status": "UNAVAILABLE",
              "message": "This model is currently experiencing high demand. "
                         "Spikes in demand are usually temporary."}
}
QUOTA_BODY = {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED", "message": "quota"}}


def reply(text: str) -> dict:
    return {"candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": "STOP"}]}


def model_of(request: httpx.Request) -> str:
    # เส้นทางคือ /v1beta/models/<ชื่อ>:generateContent
    return request.url.path.rsplit("/", 1)[-1].split(":")[0]


def connector(handler, **kw) -> GeminiConnector:
    """
    ตัวเชื่อมต่อที่ยิงเข้า HTTP จำลอง

    คีย์ปลอมต้องเป็น ASCII เพราะตัวเชื่อมต่อส่งคีย์ไปใน HTTP header
    ซึ่งเข้ารหัสอักขระไทยไม่ได้ (httpx โยน UnicodeEncodeError ตอนสร้าง client)
    """
    c = GeminiConnector(api_key="NOT-A-REAL-KEY", max_retries=1, **kw)
    c._client = httpx.Client(base_url="https://example.test/v1beta",
                             transport=httpx.MockTransport(handler))
    return c


MSG = [ChatMessage(role="user", content="หน่วยกิตเท่าไหร่")]


# ───────────── 1. 503 ของตัวหลัก -> ย้ายไปตัวสำรอง ─────────────

def test_overload_moves_to_fallback_model() -> None:
    seen: list[str] = []

    def h(request: httpx.Request) -> httpx.Response:
        m = model_of(request)
        seen.append(m)
        if m == "gemini-3.5-flash-lite":
            return httpx.Response(503, json=OVERLOAD_BODY)
        return httpx.Response(200, json=reply(f"ตอบจาก {m}"))

    c = connector(h)
    out = c.chat(MSG)
    check("ได้คำตอบจากโมเดลสำรอง", out == "ตอบจาก gemini-3.1-flash-lite", f"{out!r} · ยิงไป {seen}")
    check("ยิงรวมน้อยครั้ง (ย้ายทันที ไม่วนซ้ำ)", len(seen) == 2, f"ยิง {len(seen)} ครั้ง: {seen}")
    check("ลองตัวหลักก่อนแล้วจึงย้าย", seen[0] == "gemini-3.5-flash-lite", str(seen))
    # 5xx ย้ายโมเดลทันที ไม่ลองซ้ำตัวเดิม — เหตุผลอยู่ใน _chat_one_model
    check("ไม่ลองซ้ำตัวที่ 503 เลย",
          seen.count("gemini-3.5-flash-lite") == 1, f"ยิง {seen.count('gemini-3.5-flash-lite')} ครั้ง")


def test_second_call_skips_the_parked_model() -> None:
    """ตัวที่เพิ่ง 503 ถูกพักไว้ คำขอถัดไปต้องเริ่มที่ตัวสำรองทันที ไม่เสียเวลาอีก"""
    seen: list[str] = []

    def h(request: httpx.Request) -> httpx.Response:
        m = model_of(request)
        seen.append(m)
        if m == "gemini-3.5-flash-lite":
            return httpx.Response(503, json=OVERLOAD_BODY)
        return httpx.Response(200, json=reply("ok"))

    c = connector(h)
    c.chat(MSG)
    first_round = len(seen)
    seen.clear()
    c.chat(MSG)
    check("คำขอที่สองไม่กลับไปยิงตัวที่ถูกพัก",
          "gemini-3.5-flash-lite" not in seen, str(seen))
    check("คำขอที่สองยิงน้อยครั้งกว่าคำขอแรก", len(seen) < first_round, f"{len(seen)} vs {first_round}")


def test_all_models_overloaded_raises_clear_error() -> None:
    def h(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json=OVERLOAD_BODY)

    c = connector(h)
    try:
        c.chat(MSG)
        check("ทุกโมเดล 503 ต้องโยน LLMConnectionError", False, "ไม่โยน")
    except LLMConnectionError as e:
        check("ทุกโมเดล 503 ต้องโยน LLMConnectionError", True)
        check("ข้อความบอกว่าใช้ไม่ได้ทุกตัว", "ทุกตัวใช้ไม่ได้" in str(e), str(e)[:120])


# ───────────── 2. พฤติกรรมเดิมต้องไม่เปลี่ยน ─────────────

def test_quota_still_moves_model() -> None:
    seen: list[str] = []

    def h(request: httpx.Request) -> httpx.Response:
        m = model_of(request)
        seen.append(m)
        if m == "gemini-3.5-flash-lite":
            return httpx.Response(429, json=QUOTA_BODY)
        return httpx.Response(200, json=reply("ok"))

    c = connector(h)
    check("429 ยังย้ายโมเดลเหมือนเดิม", c.chat(MSG) == "ok", str(seen))
    check("429 ไม่ลองซ้ำตัวเดิม", seen.count("gemini-3.5-flash-lite") == 1, str(seen))


def test_client_error_does_not_move_model() -> None:
    """4xx คือเราส่งผิดเอง ย้ายโมเดลก็ได้ผลเท่าเดิม ต้องโยนออกทันที"""
    seen: list[str] = []

    def h(request: httpx.Request) -> httpx.Response:
        seen.append(model_of(request))
        return httpx.Response(400, json={"error": {"code": 400, "message": "bad request"}})

    c = connector(h)
    try:
        c.chat(MSG)
        check("400 ต้องโยนออกทันที", False, "ไม่โยน")
    except LLMConnectionError:
        check("400 ต้องโยนออกทันที", True)
        check("400 ไม่ไล่ยิงโมเดลอื่น", len(set(seen)) == 1, str(seen))


def test_not_found_explains_the_model_name() -> None:
    def h(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": {"code": 404, "message": "not found"}})

    c = connector(h)
    try:
        c.chat(MSG)
        check("404 ต้องโยนออกและบอกชื่อโมเดล", False, "ไม่โยน")
    except LLMConnectionError as e:
        check("404 ต้องโยนออกและบอกชื่อโมเดล", "GEMINI_MODEL" in str(e), str(e)[:120])


# ───────────── 3. เส้นทางสตรีม ─────────────

def test_stream_overload_moves_to_fallback() -> None:
    seen: list[str] = []

    def h(request: httpx.Request) -> httpx.Response:
        m = model_of(request)
        seen.append(m)
        if m == "gemini-3.5-flash-lite":
            return httpx.Response(503, json=OVERLOAD_BODY)
        body = 'data: {"candidates":[{"content":{"parts":[{"text":"สวัสดี"}]}}]}\n\n'
        return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})

    c = connector(h)
    got = "".join(c.chat_stream(MSG))
    check("สตรีมย้ายไปตัวสำรองได้", got == "สวัสดี", f"{got!r} · ยิงไป {seen}")
    check("สตรีมลองตัวหลักก่อน", seen[0] == "gemini-3.5-flash-lite", str(seen))


def test_stream_all_overloaded_raises() -> None:
    def h(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json=OVERLOAD_BODY)

    c = connector(h)
    try:
        list(c.chat_stream(MSG))
        check("สตรีมที่ 503 ทุกตัวต้องโยน", False, "ไม่โยน")
    except LLMConnectionError:
        check("สตรีมที่ 503 ทุกตัวต้องโยน", True)


# ───────────── 4. คีย์ต้องไม่หลุดออกมาใน repr ─────────────

def test_api_key_is_not_in_repr() -> None:
    c = GeminiConnector(api_key="SECRET-MUST-NOT-APPEAR")
    r = repr(c)
    check("ค่าคีย์ไม่อยู่ใน repr", "SECRET-MUST-NOT-APPEAR" not in r, r[:120])
    check("ชื่อฟิลด์ api_key ไม่อยู่ใน repr", "api_key" not in r, r[:120])
    check("ยังอ่านชื่อโมเดลจาก repr ได้", "chat_model" in r, r[:120])
    check("ยังสร้างด้วย api_key= ได้ปกติ", c.api_key == "SECRET-MUST-NOT-APPEAR")


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
