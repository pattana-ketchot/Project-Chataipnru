"""
สวิตช์เลือกผู้ให้บริการจากหลังบ้าน — การตัดสินและการสร้าง connector

    docker exec -w /app/backend -e PYTHONPATH=/app/backend <c> python tests/test_model_switch.py

ที่มา
-----
หน้าผู้ดูแลมีช่องตั้งค่าโมเดลและบันทึกลง `web.ai_settings` สำเร็จมาตั้งแต่ Phase 4
แต่ไม่มีโค้ดใดอ่านค่านั้น `get_llm_connector()` สร้าง connector ครั้งเดียวจาก env
แล้วเก็บเป็น singleton · หลักฐานตรงที่สุดคือฐาน production เก็บ
`model = 'gemini-3.1-flash-lite'` ไว้ตั้งแต่ 25 ส.ค. 2569 ขณะที่ env ใช้
`gemini-3.5-flash-lite` และนั่นคือรุ่นที่ตอบจริงมาตลอด

สิ่งที่ทดสอบ
------------
1. การตัดสิน: ไม่มีค่า / มีแต่ model ไม่มี provider / provider ไม่รองรับ /
   เลือก gemini แต่ไม่มีคีย์ / เลือกครบ / อ่านฐานไม่ได้
2. สร้าง connector ตรงชนิดกับผู้ให้บริการที่เลือก และ embed_model ไม่เคยเปลี่ยน
3. เปลี่ยนค่าแล้วคำขอถัดไปได้ตัวใหม่ โดยไม่ต้อง restart
4. connector ที่แจกไปแล้วไม่ถูกแก้ — คำตอบที่กำลังสตรีมจึงไม่สลับโมเดลกลางทาง
5. เลือก Ollama เป็นตัวหลัก ต้องนับการเรียกจริง และ **ไม่มี** ตัวสำรองไปหา Gemini
6. การอุ่นโมเดลเบื้องหลังไม่ถูกนับเป็นการใช้งาน
"""
import os
import sys
import traceback
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://unused:unused@127.0.0.1:1/unused")
os.environ.setdefault("JWT_SECRET", "ชุดทดสอบไม่ได้ออก token")

from app.services import ai_settings, llm_client, llm_usage  # noqa: E402
from llm.connector import ChatMessage, LLMConnectionError, OllamaConnector  # noqa: E402

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

class FakeDB:
    """คืนแถวของ web.ai_settings หนึ่งแถว หรือโยนข้อผิดพลาดเพื่อจำลองฐานล่ม"""

    def __init__(self, row: dict | None, boom: bool = False) -> None:
        self._row = row
        self._boom = boom

    def execute(self, _stmt):
        if self._boom:
            raise RuntimeError("ฐานข้อมูลล่ม")
        row = self._row
        outer = self

        class _R:
            def mappings(self):
                return self

            def first(self):
                return dict(row) if row is not None else None

        del outer
        return _R()


class FakeLocal:
    """แทน OllamaConnector ในการนับเหตุการณ์ — ไม่ต่อเน็ตเลย"""

    chat_model = "qwen2.5:3b"
    answer_token_cap = 400

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.chat_calls = 0

    def chat(self, *_a, **_k):
        self.chat_calls += 1
        if self.fail:
            raise LLMConnectionError("โมเดลในเครื่องล้ม")
        return "คำตอบจากโมเดลในเครื่อง"

    def chat_stream(self, *_a, **_k):
        self.chat_calls += 1
        if self.fail:
            raise LLMConnectionError("โมเดลในเครื่องล้ม")
        yield "ชิ้น"

    def embed(self, _t):
        return [0.0]

    def embed_batch(self, ts):
        return [[0.0] for _ in ts]


def recorded(fn) -> list[str]:
    """เหตุการณ์ที่ถูกนับระหว่างเรียก fn — อ่านจากตัวนับจริง ไม่ใช่ของปลอม"""
    llm_usage.reset_for_test()
    try:
        fn()
    except Exception:  # noqa: BLE001 — บางเคสตั้งใจให้ล้ม
        pass
    return sorted(e for _day, e in llm_usage.pending_snapshot())


def setenv(**kw) -> None:
    for k, v in kw.items():
        setattr(ai_settings.settings, k, v)
    ai_settings.invalidate()


# ───────────────────── 1. การตัดสินว่าจะใช้อะไร ─────────────────────

def test_no_row_uses_env() -> None:
    """ยังไม่มีแถวเลย — ใช้ค่าจาก env และบอกว่าที่มาคือ env"""
    setenv(llm_provider="gemini", gemini_model="gemini-3.5-flash-lite",
           gemini_api_key="k", llm_model="qwen2.5:3b")
    c = ai_settings.resolve(FakeDB(None))
    check("ไม่มีแถว -> ใช้ผู้ให้บริการจาก env", c.provider == "gemini", c.provider)
    check("ไม่มีแถว -> ใช้รุ่นจาก env", c.model == "gemini-3.5-flash-lite", c.model)
    check("ไม่มีแถว -> ที่มาคือ env", c.source == "env", c.source)
    check("ไม่มีแถว -> ไม่ถือว่าทำตามค่าที่บันทึก", c.honoured is False, str(c.honoured))


def test_saved_model_without_provider_is_not_used() -> None:
    """
    แถวเดิมของ production — มี model แต่ไม่มี provider

    ต้องไม่ถูกนำไปใช้ ไม่งั้นแค่ deploy โค้ดนี้ ระบบจะเริ่มส่งชื่อรุ่นที่ไม่เคย
    ถูกตรวจ (gemini-3.1-flash-lite) ไปให้ผู้ให้บริการจริงทันที
    """
    setenv(llm_provider="gemini", gemini_model="gemini-3.5-flash-lite", gemini_api_key="k")
    c = ai_settings.resolve(FakeDB({"provider": None, "model": "gemini-3.1-flash-lite"}))
    check("มีแต่ model ไม่มี provider -> ยังใช้รุ่นจาก env",
          c.model == "gemini-3.5-flash-lite", c.model)
    check("มีแต่ model ไม่มี provider -> ที่มายังเป็น env", c.source == "env", c.source)
    check("บอกค่าที่บันทึกไว้กลับไปด้วย", c.saved_model == "gemini-3.1-flash-lite",
          str(c.saved_model))
    check("มีคำอธิบายว่าทำไมค่าที่บันทึกยังไม่มีผล", "ไม่ได้ระบุผู้ให้บริการ" in c.note, c.note)


def test_saved_choice_is_used() -> None:
    """เลือกครบทั้งเจ้าและรุ่น — ต้องใช้ตามนั้น"""
    setenv(llm_provider="gemini", gemini_model="gemini-3.5-flash-lite", gemini_api_key="k")
    c = ai_settings.resolve(FakeDB({"provider": "ollama", "model": "llama3.2:3b"}))
    check("เลือก ollama -> ใช้ ollama", c.provider == "ollama", c.provider)
    check("เลือกรุ่น -> ใช้รุ่นนั้น", c.model == "llama3.2:3b", c.model)
    check("ที่มาคือค่าที่บันทึก", c.source == "db", c.source)
    check("ถือว่าทำตามค่าที่บันทึก", c.honoured is True, c.note)


def test_saved_provider_without_model_uses_provider_default() -> None:
    """เลือกเจ้าแต่ไม่ระบุรุ่น — ใช้รุ่นตั้งต้นของเจ้านั้นจาก env ไม่ใช่รุ่นของเจ้าอื่น"""
    setenv(llm_provider="gemini", gemini_model="gemini-3.5-flash-lite",
           llm_model="qwen2.5:3b", gemini_api_key="k")
    c = ai_settings.resolve(FakeDB({"provider": "ollama", "model": None}))
    check("เลือก ollama ไม่ระบุรุ่น -> ได้รุ่นของ ollama", c.model == "qwen2.5:3b", c.model)
    check("มีคำอธิบายว่าใช้รุ่นตั้งต้น", "รุ่นตั้งต้น" in c.note, c.note)


def test_unknown_provider_falls_back_to_env() -> None:
    """provider ที่ไม่รองรับ (เช่นแก้ในฐานด้วยมือ) — ใช้ env และบอกเหตุผล"""
    setenv(llm_provider="ollama", llm_model="qwen2.5:3b")
    c = ai_settings.resolve(FakeDB({"provider": "openai", "model": "gpt-4o-mini"}))
    check("provider ไม่รองรับ -> ใช้ env", c.provider == "ollama", c.provider)
    check("provider ไม่รองรับ -> ไม่เอารุ่นของมันมาใช้", c.model == "qwen2.5:3b", c.model)
    check("provider ไม่รองรับ -> แจ้งเหตุผล", "ไม่รองรับ" in c.note, c.note)


def test_gemini_without_key_is_reported_not_pretended() -> None:
    """
    เลือก Gemini แต่เซิร์ฟเวอร์ไม่มีคีย์

    ต้องบอกว่าของจริงคือโมเดลในเครื่อง ไม่ใช่รายงานว่าใช้ Gemini อยู่
    """
    setenv(llm_provider="ollama", llm_model="qwen2.5:3b", gemini_api_key="",
           gemini_model="gemini-3.5-flash-lite")
    c = ai_settings.resolve(FakeDB({"provider": "gemini", "model": "gemini-3.5-flash-lite"}))
    check("ไม่มีคีย์ -> ที่ใช้จริงคือโมเดลในเครื่อง", c.provider == "ollama", c.provider)
    check("ไม่มีคีย์ -> ยังบอกว่าผู้ดูแลเลือก gemini ไว้",
          c.saved_provider == "gemini", str(c.saved_provider))
    check("ไม่มีคีย์ -> ไม่ถือว่าทำตามที่เลือก", c.honoured is False, c.note)
    check("ไม่มีคีย์ -> แจ้งว่าต้องตั้งคีย์", "GEMINI_API_KEY" in c.note, c.note)


def test_db_error_does_not_break_answering() -> None:
    """อ่านฐานไม่ได้ — ต้องตอบคำถามต่อได้ด้วยค่าจาก env"""
    setenv(llm_provider="gemini", gemini_model="gemini-3.5-flash-lite", gemini_api_key="k")
    c = ai_settings.resolve(FakeDB(None, boom=True))
    check("ฐานล่ม -> ยังได้ตัวเลือกจาก env", c.provider == "gemini", c.provider)
    check("ฐานล่ม -> แจ้งว่าอ่านค่าที่บันทึกไม่ได้", "อ่านค่าที่บันทึกไม่ได้" in c.note, c.note)


def test_bad_env_provider_does_not_crash() -> None:
    """env ตั้งผิดเอง — ถอยไปโมเดลในเครื่อง ไม่ใช่ล้มตอนสร้าง connector"""
    setenv(llm_provider="chatgpt", llm_model="qwen2.5:3b")
    c = ai_settings.env_default()
    check("LLM_PROVIDER ผิด -> ใช้ ollama", c.provider == "ollama", c.provider)


# ───────────── 2-4. สร้าง connector และเปลี่ยนได้โดยไม่ restart ─────────────

def _with_choice(choice: ai_settings.Choice):
    """สั่งให้ ai_settings.current() คืนตัวเลือกที่กำหนด — จำลองค่าที่บันทึกในฐาน"""
    ai_settings.current = lambda: choice  # type: ignore[assignment]


def test_connector_type_matches_provider() -> None:
    setenv(llm_provider="gemini", gemini_api_key="k", gemini_model="gemini-3.5-flash-lite",
           llm_model="qwen2.5:3b", embed_model="bge-m3",
           ollama_base_url="http://127.0.0.1:11434", llm_request_timeout_s=5)
    real_current = ai_settings.current
    try:
        llm_client.reset_connectors_for_test()
        _with_choice(ai_settings.Choice("gemini", "gemini-3.5-flash-lite", "db",
                                        "gemini", "gemini-3.5-flash-lite"))
        c1 = llm_client.get_llm_connector()
        check("เลือก gemini -> ได้ตัวที่แยกเจ้า embedding กับเจ้าเขียนคำตอบ",
              isinstance(c1, llm_client._SplitConnector), type(c1).__name__)
        check("เลือก gemini -> รุ่นที่ใช้เขียนคำตอบตรงกับที่เลือก",
              c1.chat_model == "gemini-3.5-flash-lite", c1.chat_model)
        check("เลือก gemini -> ฝั่ง embedding ยังเป็น bge-m3",
              c1._embedder.embed_model == "bge-m3", c1._embedder.embed_model)

        _with_choice(ai_settings.Choice("ollama", "llama3.2:3b", "db", "ollama", "llama3.2:3b"))
        c2 = llm_client.get_llm_connector()
        check("เลือก ollama -> ได้ตัวที่ใช้โมเดลในเครื่องเป็นตัวหลัก",
              isinstance(c2, llm_client._LocalPrimary), type(c2).__name__)
        check("เลือก ollama -> รุ่นที่ใช้เขียนคำตอบตรงกับที่เลือก",
              c2.chat_model == "llama3.2:3b", c2.chat_model)
        check("เลือก ollama -> ฝั่ง embedding ยังเป็น bge-m3",
              c2._local.embed_model == "bge-m3", c2._local.embed_model)
        check("เปลี่ยนค่าแล้วได้ connector ตัวใหม่โดยไม่ต้อง restart", c1 is not c2, "ตัวเดิม")

        # ตัวเดิมที่แจกไปแล้วต้องไม่ถูกแก้ ไม่งั้นคำตอบที่กำลังสตรีมจะสลับโมเดลกลางทาง
        check("connector ที่แจกไปแล้วยังชี้ผู้ให้บริการเดิม",
              c1.chat_model == "gemini-3.5-flash-lite", c1.chat_model)

        _with_choice(ai_settings.Choice("gemini", "gemini-3.5-flash-lite", "db",
                                        "gemini", "gemini-3.5-flash-lite"))
        c3 = llm_client.get_llm_connector()
        check("สลับกลับได้ และใช้ตัวเดิมซ้ำ (ไม่สร้าง httpx client ใหม่)", c3 is c1, "ตัวใหม่")
    finally:
        ai_settings.current = real_current  # type: ignore[assignment]
        llm_client.reset_connectors_for_test()


def test_connector_cache_is_bounded() -> None:
    """ผู้ดูแลเปลี่ยนชื่อรุ่นได้ไม่จำกัดครั้ง แคชต้องไม่โตไม่หยุด"""
    setenv(llm_provider="ollama", llm_model="qwen2.5:3b", embed_model="bge-m3",
           ollama_base_url="http://127.0.0.1:11434", llm_request_timeout_s=5)
    real_current = ai_settings.current
    try:
        llm_client.reset_connectors_for_test()
        for i in range(llm_client.MAX_CACHED_CONNECTORS + 3):
            name = f"m{i}"
            _with_choice(ai_settings.Choice("ollama", name, "db", "ollama", name))
            llm_client.get_llm_connector()
        check("จำนวน connector ที่เก็บไว้ไม่เกินเพดาน",
              len(llm_client._connectors) <= llm_client.MAX_CACHED_CONNECTORS,
              str(len(llm_client._connectors)))
    finally:
        ai_settings.current = real_current  # type: ignore[assignment]
        llm_client.reset_connectors_for_test()


# ───────────── 5-6. การนับเมื่อโมเดลในเครื่องเป็นตัวหลัก ─────────────

MSG = [ChatMessage(role="user", content="หน่วยกิตเท่าไหร่")]


def test_local_primary_success_is_counted() -> None:
    c = llm_client._LocalPrimary(FakeLocal())
    seen = recorded(lambda: c.chat(MSG))
    check("ตอบได้ -> นับทั้งเรียกและสำเร็จ",
          seen == ["local_primary_attempt", "local_primary_ok"], str(seen))


def test_local_primary_failure_is_not_counted_as_success() -> None:
    c = llm_client._LocalPrimary(FakeLocal(fail=True))
    seen = recorded(lambda: c.chat(MSG))
    check("ล้ม -> ไม่นับเป็นสำเร็จ",
          seen == ["local_primary_attempt", "local_primary_failed"], str(seen))


def test_local_primary_has_no_cloud_fallback() -> None:
    """
    เลือกโมเดลในเครื่องแล้วล้ม ต้องแจ้งข้อผิดพลาด ไม่แอบไปเรียก Gemini

    การเลือกโมเดลในเครื่องคือการเลือกไม่ส่งคำถามของผู้ใช้ออกนอกเครื่อง ถ้าตกไปหา
    เจ้าบนคลาวด์เองตอนมีปัญหา ระบบจะละเมิดเงื่อนไขนั้นเงียบ ๆ
    """
    local = FakeLocal(fail=True)
    c = llm_client._LocalPrimary(local)
    raised = ""
    try:
        c.chat(MSG)
    except LLMConnectionError as e:
        raised = str(e)
    check("ล้มแล้วโยนข้อผิดพลาดออกมา", "โมเดลในเครื่องล้ม" in raised, raised)
    check("ไม่มีคำสั่งห้ามตัวสำรองให้ต้องส่ง (เพราะไม่มีตัวสำรอง)",
          llm_client.no_fallback_kwargs(c, False) == {},
          str(llm_client.no_fallback_kwargs(c, False)))


def test_local_primary_stream_counts_only_when_finished() -> None:
    c = llm_client._LocalPrimary(FakeLocal())
    seen = recorded(lambda: list(c.chat_stream(MSG)))
    check("สตรีมจนจบ -> นับสำเร็จ",
          seen == ["local_primary_attempt", "local_primary_ok"], str(seen))

    c2 = llm_client._LocalPrimary(FakeLocal(fail=True))
    seen2 = recorded(lambda: list(c2.chat_stream(MSG)))
    check("สตรีมล้ม -> นับล้ม",
          seen2 == ["local_primary_attempt", "local_primary_failed"], str(seen2))


def test_warmup_is_not_counted_as_usage() -> None:
    """
    งานอุ่นโมเดลยิงทุก 20 นาทีไม่ว่ามีผู้ใช้หรือไม่ ถ้านับรวมจะบวกวันละ 72 ครั้ง
    แล้วสถิติจะตอบคำถาม "ผู้ใช้ได้คำตอบจากโมเดลไหน" ผิดทั้งหมด
    """
    local = FakeLocal()
    c = llm_client._LocalPrimary(local)
    seen = recorded(c.warm_chat)
    check("อุ่นโมเดล -> ไม่นับอะไรเลย", seen == [], str(seen))
    check("อุ่นโมเดล -> แตะโมเดลจริง", local.chat_calls == 1, str(local.chat_calls))


def test_embed_model_never_comes_from_the_switch() -> None:
    """สวิตช์เปลี่ยนได้แค่โมเดลที่เขียนคำตอบ — เวกเตอร์ของเอกสารทั้งคลังผูกกับ bge-m3"""
    setenv(embed_model="bge-m3", llm_model="qwen2.5:3b",
           ollama_base_url="http://127.0.0.1:11434", llm_request_timeout_s=5)
    built = llm_client._build_ollama("llama3.2:3b")
    check("ตั้งรุ่นเขียนคำตอบได้", built.chat_model == "llama3.2:3b", built.chat_model)
    check("รุ่น embedding ยังมาจาก env", built.embed_model == "bge-m3", built.embed_model)
    check("เป็น OllamaConnector ตัวจริง", isinstance(built, OllamaConnector),
          type(built).__name__)
    built.close()


def test_one_request_uses_one_provider_end_to_end() -> None:
    """
    ขั้นเขียนคำตอบต้องใช้ connector ตัวเดียวกับที่ขั้นก่อนหน้าใช้

    หนึ่งคำขอเรียกโมเดลหลายขั้น (เขียนคำถามใหม่ · ด่านตรวจขอบเขต · ด่านตรวจหลักฐาน ·
    เขียนคำตอบ) ถ้าขั้นเขียนคำตอบไปขอ connector ใหม่เอง แล้วผู้ดูแลเปลี่ยนค่าระหว่างนั้น
    คำขอเดียวจะใช้เจ้าหนึ่งตรวจหลักฐานแล้วใช้อีกเจ้าเขียนคำตอบ — คำตอบถูกเขียนบน
    คำตัดสินของโมเดลอื่น

    เจอจากการทดสอบผ่าน API เมื่อ 28 ต.ค. 2569: เริ่มคำขอตอนเลือก ollama แล้วสลับเป็น
    gemini กลางคำขอ คำตอบที่ได้รายงาน answer_model = gemini:gemini-3.5-flash-lite
    """
    import uuid as _uuid

    import app.services.chat as C

    pinned = FakeLocal()                     # ตัวที่ขั้นก่อนหน้าใช้
    fresh = FakeLocal()                      # ตัวที่จะได้ถ้าไปขอใหม่ (ต้องไม่ถูกเรียก)
    sid = _uuid.uuid4()
    prepared = C.Prepared(
        session_id=sid,
        status="answered",
        search_query="หน่วยกิตเท่าไหร่",
        best_score=0.5,
        citations=[],
        retrieved=(),
        canned=None,
        messages=[ChatMessage(role="user", content="หน่วยกิตเท่าไหร่")],
        allow_fallback=False,
        cacheable=False,
        corpus_version="v-test",
        stages=C._Stages(),
        interpreted="หน่วยกิตเท่าไหร่",
        has_history=False,
        connector=llm_client._LocalPrimary(pinned),
    )
    saved = (C.prepare_answer, C._with_structured, C._persist, C.cache_store,
             C._with_rag_sources, C.shadow_submit, C.get_llm_connector)
    try:
        C.prepare_answer = lambda *a, **k: prepared              # type: ignore[assignment]
        C._with_structured = lambda p, m: p                      # type: ignore[assignment]
        C._persist = lambda *a, **k: None                         # type: ignore[assignment]
        C.cache_store = lambda *a, **k: None                      # type: ignore[assignment]
        C._with_rag_sources = lambda db, p, t: (t, [])            # type: ignore[assignment]
        C.shadow_submit = lambda **k: None                        # type: ignore[assignment]
        C.get_llm_connector = lambda: llm_client._LocalPrimary(fresh)  # type: ignore[assignment]
        reply = C.answer_question(None, _uuid.uuid4(), sid, "หน่วยกิตเท่าไหร่")
    finally:
        (C.prepare_answer, C._with_structured, C._persist, C.cache_store,
         C._with_rag_sources, C.shadow_submit, C.get_llm_connector) = saved

    check("ขั้นเขียนคำตอบเรียกตัวที่ขั้นก่อนหน้าใช้", pinned.chat_calls == 1,
          str(pinned.chat_calls))
    check("ไม่ไปขอ connector ใหม่เองกลางคำขอ", fresh.chat_calls == 0, str(fresh.chat_calls))
    check("answer_model รายงานตัวที่เขียนจริง",
          reply.answer_model == "ollama:qwen2.5:3b", str(reply.answer_model))


def test_canned_answer_reports_no_model() -> None:
    """คำตอบสำเร็จรูปไม่ได้เรียกโมเดล answer_model จึงต้องเป็น None"""
    import uuid as _uuid

    import app.services.chat as C

    never = FakeLocal()
    sid = _uuid.uuid4()
    prepared = C.Prepared(
        session_id=sid, status="answered", search_query="q", best_score=0.0,
        citations=[], retrieved=(), canned="ตอบจากฐานข้อมูลหลักสูตร",
        messages=[], allow_fallback=False, cacheable=False, corpus_version="v-test",
        stages=C._Stages(), interpreted="q", has_history=False,
        connector=llm_client._LocalPrimary(never),
    )
    saved = (C.prepare_answer, C._with_structured, C._persist, C.cache_store,
             C._with_rag_sources, C.shadow_submit)
    try:
        C.prepare_answer = lambda *a, **k: prepared              # type: ignore[assignment]
        C._with_structured = lambda p, m: p                      # type: ignore[assignment]
        C._persist = lambda *a, **k: None                         # type: ignore[assignment]
        C.cache_store = lambda *a, **k: None                      # type: ignore[assignment]
        C._with_rag_sources = lambda db, p, t: (t, [])            # type: ignore[assignment]
        C.shadow_submit = lambda **k: None                        # type: ignore[assignment]
        reply = C.answer_question(None, _uuid.uuid4(), sid, "คำถาม")
    finally:
        (C.prepare_answer, C._with_structured, C._persist, C.cache_store,
         C._with_rag_sources, C.shadow_submit) = saved

    check("คำตอบสำเร็จรูปไม่เรียกโมเดลเลย", never.chat_calls == 0, str(never.chat_calls))
    check("answer_model เป็น None", reply.answer_model is None, str(reply.answer_model))
    check("ยังได้ข้อความคำตอบตามเดิม", reply.reply == "ตอบจากฐานข้อมูลหลักสูตร", reply.reply)


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
