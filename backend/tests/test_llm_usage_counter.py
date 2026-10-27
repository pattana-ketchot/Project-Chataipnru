"""
ทดสอบตัวนับว่าคำตอบมาจากโมเดลตัวไหน (services/llm_usage.py + llm/gemini.py)

    cd backend && python tests/test_llm_usage_counter.py

ไม่ต่อฐานข้อมูล ไม่ต่อ Google ไม่ใช้คีย์จริง — ใช้ HTTP จำลองและ session จำลองทั้งหมด

สิ่งที่ต้องพิสูจน์ เรียงตามความสำคัญ
----------------------------------
1. ตัวนับห้ามทำให้คำตอบพัง — ฐานข้อมูลล่มหรือ callback พัง ผู้ใช้ต้องยังได้คำตอบ
2. ตัวเลขต้องไม่หายเมื่อเขียนฐานข้อมูลไม่สำเร็จ (ต้องคืนเข้ากองรอ ไม่ใช่ทิ้ง)
3. ชื่อเหตุการณ์ต้องตรงกับที่เอกสารและ query ในไฟล์ migration ใช้ ไม่งั้นนับไปก็อ่านผิด
4. ต้องแยก "ชนเพดานต่อนาที" ออกจาก "โควตารายวัน" และ "ผู้ให้บริการรับไม่ไหว" ได้
   เพราะสามอย่างนี้นำไปสู่คนละข้อสรุป — รายวันแก้ด้วยการเพิ่มโควตา ต่อนาทีแก้ด้วย
   การรอ ส่วน 5xx เป็นเรื่องของผู้ให้บริการที่เราทำอะไรไม่ได้
"""
import os
import sys
import time
import traceback
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://unused:unused@127.0.0.1:1/unused")
os.environ.setdefault("JWT_SECRET", "ชุดทดสอบไม่ได้ออก token")

import httpx

from app.services import llm_usage
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


# ───────────────────────── เครื่องมือจำลอง ─────────────────────────

MSG = [ChatMessage(role="user", content="หน่วยกิตเท่าไหร่")]

QUOTA_DAY = {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED", "message": "quota",
                       "details": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]}}
QUOTA_MINUTE = {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED", "message": "quota",
                          "details": [{"quotaId": "GenerateRequestsPerMinutePerProjectPerModel-FreeTier"},
                                      {"retryDelay": "12s"}]}}
OVERLOAD = {"error": {"code": 503, "status": "UNAVAILABLE",
                      "message": "This model is currently experiencing high demand."}}


def reply(text: str) -> dict:
    return {"candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": "STOP"}]}


def model_of(request: httpx.Request) -> str:
    return request.url.path.rsplit("/", 1)[-1].split(":")[0]


def connector(handler, events: list[str], **kw) -> GeminiConnector:
    c = GeminiConnector(api_key="NOT-A-REAL-KEY", max_retries=1, on_event=events.append, **kw)
    c._client = httpx.Client(base_url="https://example.test/v1beta",
                             transport=httpx.MockTransport(handler))
    return c


class FakeSession:
    """session จำลองที่จดคำสั่งไว้ดูแทนการต่อฐานข้อมูลจริง"""

    def __init__(self, store: list, fail: bool = False) -> None:
        self._store = store
        self._fail = fail
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, _stmt, params):
        if self._fail:
            raise RuntimeError("ฐานข้อมูลล่มในชุดทดสอบ")
        self._store.append(params)

    def commit(self):
        self.committed = True


def use_fake_db(store: list, fail: bool = False):
    """สลับ SessionLocal ของตัวนับเป็นของจำลอง คืนตัวเดิมให้เอาไปคืนที่"""
    original = llm_usage.SessionLocal
    llm_usage.SessionLocal = lambda: FakeSession(store, fail)
    return original


# ───────────── 1. ตัวนับห้ามทำให้คำตอบพัง ─────────────

def test_broken_callback_does_not_break_the_answer() -> None:
    """callback ที่ระเบิดต้องไม่ทำให้ผู้ใช้ไม่ได้คำตอบ — นี่คือกฎข้อแรกของไฟล์นี้"""
    def h(_request):
        return httpx.Response(200, json=reply("คำตอบปกติ"))

    def boom(_event):
        raise RuntimeError("ตัวนับพัง")

    c = GeminiConnector(api_key="NOT-A-REAL-KEY", max_retries=1, on_event=boom)
    c._client = httpx.Client(base_url="https://example.test/v1beta",
                             transport=httpx.MockTransport(h))
    out = c.chat(MSG)
    check("callback พังแล้วยังได้คำตอบ", out == "คำตอบปกติ", repr(out))


def test_record_never_raises_when_database_is_down() -> None:
    llm_usage.reset_for_test()
    original = use_fake_db([], fail=True)
    try:
        llm_usage.record("gemini_ok")
        llm_usage.record("gemini_ok")
        llm_usage.flush()   # บังคับให้ชนฐานข้อมูลที่ล่มอยู่ตรงนี้เลย
        check("ฐานข้อมูลล่มแล้ว record() กับ flush() ไม่โยนข้อผิดพลาด", True)
    except Exception as e:  # noqa: BLE001
        check("ฐานข้อมูลล่มแล้ว record() ไม่โยนข้อผิดพลาด", False, repr(e))
    finally:
        llm_usage.SessionLocal = original


# ───────────── 2. ตัวเลขต้องไม่หาย ─────────────

def test_failed_write_returns_counts_to_the_queue() -> None:
    llm_usage.reset_for_test()
    original = use_fake_db([], fail=True)
    try:
        for _ in range(3):
            llm_usage.record("fallback_local")
        llm_usage.flush()
        pending = llm_usage.pending_snapshot()
        total = sum(pending.values())
        check("เขียนไม่สำเร็จแล้วตัวเลขยังอยู่ครบ", total == 3, f"เหลือ {total} จาก 3 · {pending}")
    finally:
        llm_usage.SessionLocal = original
        llm_usage.reset_for_test()


def test_successful_write_clears_the_queue_and_sums_per_event() -> None:
    llm_usage.reset_for_test()
    written: list[dict] = []
    original = use_fake_db(written)
    try:
        for _ in range(5):
            llm_usage.record("gemini_ok")
        llm_usage.record("fallback_local")
        llm_usage.flush()
        by_event: dict[str, int] = {}
        for w in written:
            by_event[w["event"]] = by_event.get(w["event"], 0) + w["n"]
        check("นับครบทุกครั้งที่เรียก ไม่ขาดไม่เกิน",
              by_event.get("gemini_ok") == 5, f"{written}")
        check("นับเหตุการณ์อื่นแยกกัน", by_event.get("fallback_local") == 1, f"{written}")
        # 6 ครั้งที่นับ ต้องกลายเป็นคำสั่งเขียนไม่เกิน 2 ก้อน (เหตุการณ์ละก้อน)
        check("รวมเป็นก้อน ไม่ใช่เขียนทีละครั้ง", len(written) <= 2, f"{len(written)} ก้อน: {written}")
        check("เขียนสำเร็จแล้วกองรอว่าง", llm_usage.pending_snapshot() == {},
              str(llm_usage.pending_snapshot()))
        check("วันที่อยู่ในรูปแบบ YYYY-MM-DD",
              all(len(w["day"]) == 10 and w["day"][4] == "-" for w in written), f"{written}")
    finally:
        llm_usage.SessionLocal = original
        llm_usage.reset_for_test()


def test_event_name_is_capped() -> None:
    llm_usage.reset_for_test()
    original = use_fake_db([])
    try:
        llm_usage.record("gemini_backup:" + "ก" * 200)
        names = [event for _day, event in llm_usage.pending_snapshot()]
        longest = max((len(n) for n in names), default=0)
        check("ชื่อเหตุการณ์ถูกตัดไม่ให้ยาวเกินกำหนด",
              longest <= llm_usage.MAX_EVENT_LEN, f"ยาวสุด {longest}")
    finally:
        llm_usage.SessionLocal = original
        llm_usage.reset_for_test()


# ───────────── 2.5 ตัวนับต้องไม่ถ่วงใคร ─────────────

class HangingSession(FakeSession):
    """ฐานข้อมูลที่ค้าง — ของจริงเคยค้างเกินสองนาทีตอนต่อไม่ได้"""

    def execute(self, _stmt, params):
        time.sleep(30)


def test_record_does_not_wait_for_the_database() -> None:
    """คำขอที่บังเอิญเป็นคนจุดชนวนการเขียน ต้องไม่ค้างตามฐานข้อมูลไปด้วย"""
    llm_usage.reset_for_test()
    original = llm_usage.SessionLocal
    llm_usage.SessionLocal = lambda: HangingSession([])
    try:
        # ทำให้ถึงกำหนดเขียนทันที แล้ววัดว่า record() คืนค่าเร็วแค่ไหน
        llm_usage._last_flush = time.monotonic() - llm_usage.FLUSH_EVERY_S - 1
        started = time.monotonic()
        llm_usage.record("gemini_ok")
        took = time.monotonic() - started
        check("record() ไม่รอฐานข้อมูลที่ค้าง", took < 1.0, f"ใช้เวลา {took:.2f} วินาที")
    finally:
        llm_usage.SessionLocal = original
        llm_usage.reset_for_test()


def test_shutdown_gives_up_instead_of_blocking() -> None:
    """ปิดระบบต้องไม่ถูกถ่วงโดยตัวนับ — docker ให้เวลาปิดแค่ 10 วินาที"""
    llm_usage.reset_for_test()
    original = llm_usage.SessionLocal
    llm_usage.SessionLocal = lambda: HangingSession([])
    try:
        llm_usage.start_flusher()
        llm_usage.record("gemini_ok")
        started = time.monotonic()
        llm_usage.stop_flusher()          # เส้นทางเดียวกับที่ lifespan ของแอปเรียก
        took = time.monotonic() - started
        check("ตอนปิดรอไม่เกินเพดานที่ตั้งไว้",
              took < llm_usage.EXIT_FLUSH_TIMEOUT_S + 2.0, f"ใช้เวลา {took:.2f} วินาที")
    finally:
        llm_usage.SessionLocal = original
        llm_usage.reset_for_test()


# ───────────── 2.6 เขียนตามเวลา แม้ไม่มีเหตุการณ์ใหม่ ─────────────

def test_flusher_writes_on_schedule_without_new_events() -> None:
    """
    นับครั้งเดียวแล้วเงียบไปเลย ข้อมูลต้องถูกเขียนตามเวลา ไม่ต้องรอคำขอถัดไป

    นี่คือพฤติกรรมจริงของระบบนี้: คำถามมาเป็นช่วง ๆ แล้วเงียบไปเป็นชั่วโมง
    ถ้าการเขียนต้องอาศัยคำขอถัดไปเป็นคนจุดชนวน ตัวเลขช่วงท้ายจะค้างอยู่ในหน่วยความจำ
    """
    llm_usage.reset_for_test()
    written: list[dict] = []
    original = use_fake_db(written)
    interval = llm_usage.FLUSH_EVERY_S
    try:
        llm_usage.FLUSH_EVERY_S = 0.3
        llm_usage.start_flusher()
        llm_usage.record("gemini_ok")     # นับครั้งเดียว แล้วไม่ทำอะไรอีกเลย

        deadline = time.monotonic() + 5.0
        while not written and time.monotonic() < deadline:
            time.sleep(0.05)

        check("เขียนเองตามเวลาโดยไม่ต้องมีเหตุการณ์ใหม่", bool(written), f"{written}")
        if written:
            check("เขียนค่าที่นับไว้จริง",
                  written[0]["event"] == "gemini_ok" and written[0]["n"] == 1, f"{written}")
        check("กองรอว่างหลังเขียน", llm_usage.pending_snapshot() == {},
              str(llm_usage.pending_snapshot()))
    finally:
        llm_usage.FLUSH_EVERY_S = interval
        llm_usage.reset_for_test()
        llm_usage.SessionLocal = original


def test_record_does_not_touch_the_database_while_the_flusher_runs() -> None:
    """คำขอของผู้ใช้ต้องไม่มีงานฐานข้อมูลของตัวนับติดอยู่เลยแม้แต่ครั้งเดียว"""
    llm_usage.reset_for_test()
    opened: list[str] = []
    original = llm_usage.SessionLocal

    def spy():
        opened.append("เปิด session")
        return FakeSession([])

    llm_usage.SessionLocal = spy
    interval = llm_usage.FLUSH_EVERY_S
    try:
        llm_usage.FLUSH_EVERY_S = 60.0    # ยาวพอที่เธรดจะไม่ตื่นระหว่างทดสอบ
        llm_usage.start_flusher()
        for _ in range(50):
            llm_usage.record("gemini_ok")
        check("record() ไม่เปิด session ฐานข้อมูลเลย", opened == [], f"เปิด {len(opened)} ครั้ง")
        check("ตัวเลขยังอยู่ในกองรอครบ",
              sum(llm_usage.pending_snapshot().values()) == 50,
              str(llm_usage.pending_snapshot()))
    finally:
        llm_usage.FLUSH_EVERY_S = interval
        llm_usage.reset_for_test()
        llm_usage.SessionLocal = original


# ───────────── 3–4. ชื่อเหตุการณ์ของ Gemini ─────────────

def test_primary_success_counts_as_gemini_ok() -> None:
    events: list[str] = []
    c = connector(lambda r: httpx.Response(200, json=reply("ok")), events)
    c.chat(MSG)
    check("ตัวหลักตอบได้ นับเป็น gemini_ok", events == ["gemini_ok"], str(events))


def test_backup_model_is_named_in_the_event() -> None:
    events: list[str] = []

    def h(request):
        if model_of(request) == "gemini-3.5-flash-lite":
            return httpx.Response(429, json=QUOTA_DAY)
        return httpx.Response(200, json=reply("ok"))

    c = connector(h, events)
    c.chat(MSG)
    check("โควตารายวันของตัวหลักถูกนับพร้อมชื่อโมเดล",
          "gemini_quota_day:gemini-3.5-flash-lite" in events, str(events))
    check("ตัวสำรองที่ตอบได้ถูกนับพร้อมชื่อโมเดล",
          "gemini_backup:gemini-3.1-flash-lite" in events, str(events))
    check("ไม่นับเป็น gemini_ok เมื่อคนตอบคือตัวสำรอง", "gemini_ok" not in events, str(events))


def test_per_minute_limit_is_separated_from_daily_quota() -> None:
    """แยกสองอย่างนี้ไม่ออก = ตัดสินใจเรื่องผู้ให้บริการผิด (ดู docstring ข้อ 4)"""
    events: list[str] = []

    def h(request):
        if model_of(request) == "gemini-3.5-flash-lite":
            return httpx.Response(429, json=QUOTA_MINUTE)
        return httpx.Response(200, json=reply("ok"))

    c = connector(h, events)
    c.chat(MSG)
    check("429 ต่อนาทีถูกนับเป็น quota_minute",
          "gemini_quota_minute:gemini-3.5-flash-lite" in events, str(events))
    check("429 ต่อนาทีไม่ถูกนับเป็น quota_day",
          not any(e.startswith("gemini_quota_day") for e in events), str(events))


def test_overload_is_its_own_event() -> None:
    events: list[str] = []

    def h(request):
        if model_of(request) == "gemini-3.5-flash-lite":
            return httpx.Response(503, json=OVERLOAD)
        return httpx.Response(200, json=reply("ok"))

    c = connector(h, events)
    c.chat(MSG)
    check("503 ถูกนับเป็น overload ไม่ใช่โควตา",
          "gemini_overload:gemini-3.5-flash-lite" in events, str(events))


def test_all_models_failing_is_counted_once() -> None:
    events: list[str] = []
    c = connector(lambda r: httpx.Response(429, json=QUOTA_DAY), events)
    try:
        c.chat(MSG)
    except LLMConnectionError:
        pass
    check("ทุกโมเดลล้มแล้วนับ gemini_all_failed หนึ่งครั้ง",
          events.count("gemini_all_failed") == 1, str(events))
    check("นับโควตาของทุกโมเดลที่ลอง",
          sum(1 for e in events if e.startswith("gemini_quota_day:")) == 4, str(events))


def test_stream_counts_the_model_that_answered() -> None:
    events: list[str] = []

    def h(request):
        return httpx.Response(200, text='data: {"candidates":[{"content":{"parts":[{"text":"ก"}]}}]}\n\n')

    c = connector(h, events)
    list(c.chat_stream(MSG))
    check("สตรีมสำเร็จจากตัวหลัก นับเป็น gemini_ok", events == ["gemini_ok"], str(events))


# ───────────── 5. ชั้นตกไปใช้โมเดลในเครื่อง ─────────────

class FakeLocal:
    """โมเดลในเครื่องจำลอง — สนใจแค่ว่าถูกเรียกหรือไม่"""
    answer_token_cap = 512

    def chat(self, *_a, **_kw):
        return "คำตอบจากโมเดลในเครื่อง"

    def chat_stream(self, *_a, **_kw):
        yield "คำตอบจากโมเดลในเครื่อง"


class BrokenLocal(FakeLocal):
    """โมเดลในเครื่องที่ล้ม — เกิดได้จริงเมื่อเพดานเวลาของคำขอหมดก่อนเขียนจบ"""

    def __init__(self, after_first_chunk: bool = False) -> None:
        self.after_first_chunk = after_first_chunk

    def chat(self, *_a, **_kw):
        raise LLMConnectionError("โมเดลในเครื่องล้มในชุดทดสอบ")

    def chat_stream(self, *_a, **_kw):
        if self.after_first_chunk:
            yield "ครึ่งเดียว"
        raise LLMConnectionError("โมเดลในเครื่องล้มในชุดทดสอบ")


class FakeCloud:
    answer_token_cap = 2048
    chat_model = "gemini-ปลอม"

    def __init__(self, fail: bool, fail_after_first_chunk: bool = False) -> None:
        self.fail = fail
        self.fail_after_first_chunk = fail_after_first_chunk

    def chat(self, *_a, **_kw):
        if self.fail:
            raise LLMConnectionError("เจ้าหลักล้มในชุดทดสอบ")
        return "คำตอบจากคลาวด์"

    def chat_stream(self, *_a, **_kw):
        if self.fail_after_first_chunk:
            yield "เริ่มแล้ว"
            raise LLMConnectionError("ล้มกลางคัน")
        if self.fail:
            raise LLMConnectionError("เจ้าหลักล้มในชุดทดสอบ")
        yield "คำตอบจากคลาวด์"


def split(cloud) -> object:
    from app.services.llm_client import _SplitConnector
    return _SplitConnector(embedder=FakeLocal(), chatter=cloud)


def recorded(fn) -> list[str]:
    """เก็บชื่อเหตุการณ์ที่ _SplitConnector นับระหว่างเรียก fn"""
    from app.services import llm_client
    seen: list[str] = []
    original = llm_client.llm_usage.record
    llm_client.llm_usage.record = seen.append
    try:
        fn()
    finally:
        llm_client.llm_usage.record = original
    return seen


def test_fallback_to_local_counts_attempt_and_success() -> None:
    c = split(FakeCloud(fail=True))
    out: list = []
    seen = recorded(lambda: out.append(c.chat(MSG)))
    check("นับทั้งการพยายามเรียกและผลสำเร็จ",
          seen == ["fallback_local_attempt", "fallback_local_ok"], str(seen))
    check("ผู้ใช้ยังได้คำตอบ", out == ["คำตอบจากโมเดลในเครื่อง"], str(out))


def test_fallback_failure_is_not_counted_as_success() -> None:
    """ถ้านับรวมเป็นตัวเดียว ความล้มเหลวจะถูกนับเป็นความสำเร็จ — นี่คือเหตุผลที่แยก"""
    c = split(FakeCloud(fail=True))
    c._fallback = BrokenLocal()

    def call():
        try:
            c.chat(MSG)
        except LLMConnectionError:
            pass

    seen = recorded(call)
    check("ตัวสำรองล้มแล้วนับ fallback_local_failed",
          seen == ["fallback_local_attempt", "fallback_local_failed"], str(seen))
    check("ไม่นับเป็นสำเร็จ", "fallback_local_ok" not in seen, str(seen))


def test_declined_fallback_is_counted_separately() -> None:
    c = split(FakeCloud(fail=True))

    def call():
        try:
            c.chat(MSG, allow_fallback=False)
        except LLMConnectionError:
            pass

    seen = recorded(call)
    check("ขั้นที่ห้ามใช้ตัวสำรองนับเป็น fallback_declined", seen == ["fallback_declined"], str(seen))


def test_stream_fallback_counts_success_only_when_the_stream_ends() -> None:
    c = split(FakeCloud(fail=True))
    out: list = []
    seen = recorded(lambda: out.extend(c.chat_stream(MSG)))
    check("สตรีมสำรองจบตามปกติแล้วนับสำเร็จ",
          seen == ["fallback_local_attempt", "fallback_local_ok"], str(seen))
    check("ผู้ใช้ยังได้คำตอบจากสตรีมสำรอง", out == ["คำตอบจากโมเดลในเครื่อง"], str(out))


def test_stream_fallback_failing_after_first_chunk_is_a_failure() -> None:
    """เริ่มส่งตัวอักษรแรกได้ไม่ใช่สำเร็จ — ผู้ใช้ที่ได้คำตอบครึ่งเดียวคือคนที่ไม่ได้คำตอบ"""
    c = split(FakeCloud(fail=True))
    c._fallback = BrokenLocal(after_first_chunk=True)
    out: list = []

    def call():
        try:
            out.extend(c.chat_stream(MSG))
        except LLMConnectionError:
            pass

    seen = recorded(call)
    check("สตรีมสำรองล้มกลางคันแล้วนับ fallback_local_failed",
          seen == ["fallback_local_attempt", "fallback_local_failed"], str(seen))
    check("ส่งตัวอักษรที่เขียนได้ออกไปตามปกติ", out == ["ครึ่งเดียว"], str(out))


def test_viewer_closing_the_page_is_counted_as_neither() -> None:
    """ปิดหน้าเว็บกลางคันไม่ใช่ทั้งความสำเร็จและความล้มเหลวของโมเดล"""
    c = split(FakeCloud(fail=True))
    seen: list[str] = []

    def call():
        gen = c.chat_stream(MSG)
        next(gen)        # รับก้อนแรกแล้วทิ้ง generator ไปเลย
        gen.close()      # เบราว์เซอร์ปิดการเชื่อมต่อ -> GeneratorExit

    seen = recorded(call)
    check("ปิดกลางคันนับแค่การพยายามเรียก",
          seen == ["fallback_local_attempt"], str(seen))


def test_every_call_ends_with_exactly_one_terminal_event() -> None:
    """
    ตัวหารของทุกสัดส่วนคือผลรวมของเหตุการณ์ปลายทาง ถ้าหนึ่งการเรียกนับปลายทาง
    สองครั้ง (หรือศูนย์ครั้ง) สูตรในรายงานจะผิดทันที
    """
    terminal = {"gemini_ok", "fallback_local_attempt", "fallback_declined",
                "stream_failed_midway"}

    def count_terminal(seen: list[str]) -> int:
        return sum(1 for e in seen if e in terminal or e.startswith("gemini_backup:"))

    cases = []

    def run(label, fn):
        cases.append((label, count_terminal(recorded(fn))))

    ok = split(FakeCloud(fail=False))
    run("คลาวด์ตอบได้", lambda: ok.chat(MSG))

    down = split(FakeCloud(fail=True))
    run("ตกไปตัวสำรอง", lambda: down.chat(MSG))

    def declined():
        try:
            down.chat(MSG, allow_fallback=False)
        except LLMConnectionError:
            pass

    run("ไม่ยอมใช้ตัวสำรอง", declined)

    midway = split(FakeCloud(fail=True, fail_after_first_chunk=True))

    def mid():
        try:
            list(midway.chat_stream(MSG))
        except LLMConnectionError:
            pass

    run("สตรีมล้มกลางคัน", mid)

    # กรณี "คลาวด์ตอบได้" นับโดย GeminiConnector ซึ่งถูกแทนด้วยของจำลองในชุดนี้
    # จึงได้ 0 ที่ชั้นนี้ — ตรวจแยกใน test_primary_success_counts_as_gemini_ok
    for label, n in cases:
        expected = 0 if label == "คลาวด์ตอบได้" else 1
        check(f"{label}: นับเหตุการณ์ปลายทาง {expected} ครั้ง", n == expected, f"นับได้ {n}")


def test_stream_failing_midway_is_counted_and_not_swapped() -> None:
    c = split(FakeCloud(fail=True, fail_after_first_chunk=True))
    out: list = []

    def call():
        try:
            out.extend(c.chat_stream(MSG))
        except LLMConnectionError:
            pass

    seen = recorded(call)
    check("ล้มหลังส่งตัวอักษรแรกแล้วนับ stream_failed_midway",
          seen == ["stream_failed_midway"], str(seen))
    check("ไม่สลับไปโมเดลในเครื่องกลางคัน",
          out == ["เริ่มแล้ว"], str(out))


def test_successful_cloud_call_is_not_counted_twice() -> None:
    """ตัวนับฝั่ง _SplitConnector ต้องไม่นับซ้ำกับที่ GeminiConnector นับไปแล้ว"""
    c = split(FakeCloud(fail=False))
    seen = recorded(lambda: c.chat(MSG))
    check("คลาวด์ตอบได้ ชั้นนี้ไม่นับอะไรเพิ่ม", seen == [], str(seen))


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        print(f"\n{t.__name__}")
        try:
            t()
        except Exception:  # noqa: BLE001
            FAILURES.append(f"{t.__name__} โยนข้อผิดพลาด")
            traceback.print_exc()
    print(f"\nตรวจทั้งหมด {CHECKS} จุด")
    if FAILURES:
        print(f"ตก {len(FAILURES)} จุด")
        for f in FAILURES:
            print("  -", f)
        return 1
    print("ผ่านทั้งหมด")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
