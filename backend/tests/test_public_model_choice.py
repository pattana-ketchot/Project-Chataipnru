"""
ผู้ใช้หน้าเว็บเลือกโมเดลเองได้ — รับเฉพาะ id ที่อนุญาต และตัวเลือกต้องได้เพดานเวลาของตัวเอง

    cd backend && python tests/test_public_model_choice.py

ไม่ต่อฐานข้อมูล ไม่ต่อโมเดล — แทน stream_answer กับ connector_for ด้วยของจับพฤติกรรม

ทำไมต้องมีชุดนี้
---------------
สองข้อที่พังแล้วจะไม่มีใครเห็นจนกว่าจะสาย

1. ถ้ารับ "ชื่อรุ่น" จากหน้าเว็บตรง ๆ ใครก็สั่งให้เซิร์ฟเวอร์ไปเรียกรุ่นไหนก็ได้
   ชุดนี้จึงยืนยันว่า id นอกรายการถูกปฏิเสธและถอยไปใช้ค่าของผู้ดูแล ไม่ใช่ทำตาม
2. ตัวเลือกโมเดลในเครื่องต้องได้เพดานเวลาของตัวเอง — วัดแล้วว่าบนเครื่องที่ไม่มี
   การ์ดจอมันใช้เวลาหลักนาที ถ้าใช้เพดาน 30 วินาทีเท่าคลาวด์คือรับประกันว่าไม่มี
   วันตอบทัน ปุ่มจะมีไว้ให้กดแล้วพังเท่านั้น
"""
import os
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://unused:unused@127.0.0.1:1/unused")
os.environ.setdefault("JWT_SECRET", "ชุดทดสอบไม่ได้ออก token")
os.environ.setdefault("GEMINI_API_KEY", "คีย์ปลอมสำหรับชุดทดสอบ")

from fastapi.testclient import TestClient  # noqa: E402

from app.api.routes import web_compat  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.services import ai_settings  # noqa: E402

CHECKS = 0
FAILURES: list[str] = []


@contextmanager
def _local_choice_on():
    """เปิดสวิตช์ชั่วคราวในชุดทดสอบ แล้วคืนค่าเดิมเสมอ"""
    before = os.environ.get("PUBLIC_LOCAL_CHOICE")
    os.environ["PUBLIC_LOCAL_CHOICE"] = "1"
    try:
        yield
    finally:
        if before is None:
            os.environ.pop("PUBLIC_LOCAL_CHOICE", None)
        else:
            os.environ["PUBLIC_LOCAL_CHOICE"] = before


def check(label: str, ok: bool, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    if ok:
        print(f"  [ผ่าน] {label}")
    else:
        FAILURES.append(f"{label} — {detail}")
        print(f"  [ตก]  {label} — {detail}")


# ───────────── 1. รายการตัวเลือก ─────────────

def test_options_list() -> None:
    print("\ntest_options_list")
    ids = [c["id"] for c in ai_settings.public_choices()]
    check("ค่าตั้งต้นให้เลือกได้เฉพาะสองตัวของ Gemini (ไม่มีโมเดลในเครื่อง)",
          ids == ["fast", "detailed"], str(ids))
    with _local_choice_on():
        ids_on = [c["id"] for c in ai_settings.public_choices()]
    check("เปิด PUBLIC_LOCAL_CHOICE แล้วจึงเห็นตัวเลือกในเครื่อง",
          ids_on == ["fast", "detailed", "local"], str(ids_on))
    default = [c["id"] for c in ai_settings.public_choices() if c["default"]]
    check("มีค่าตั้งต้นเดียว และเป็นตัวที่เร็วที่สุด", default == ["fast"], str(default))
    one = ai_settings.public_choices()[0]
    check("ทุกตัวเลือกบอกชื่อรุ่นจริงที่จะถูกเรียก", bool(one["model"]), str(one))
    check("ทุกตัวเลือกมีคำอธิบายกำกับ",
          all(c["hint"] for c in ai_settings.public_choices()))

    real_key = ai_settings.has_gemini_key
    try:
        ai_settings.has_gemini_key = lambda: False
        ids_nokey = [c["id"] for c in ai_settings.public_choices()]
        check("เซิร์ฟเวอร์ที่ไม่มีคีย์ไม่เห็นตัวเลือกของ Gemini", ids_nokey == [], str(ids_nokey))
        with _local_choice_on():
            ids_nokey_on = [c["id"] for c in ai_settings.public_choices()]
        check("ไม่มีคีย์แต่เปิดตัวเลือกในเครื่อง -> เหลือตัวในเครื่องตัวเดียว",
              ids_nokey_on == ["local"], str(ids_nokey_on))
    finally:
        ai_settings.has_gemini_key = real_key


# ───────────── 2. แปลง id เป็นตัวเลือกจริง ─────────────

def test_choice_resolution() -> None:
    print("\ntest_choice_resolution")
    check("ปิดอยู่ -> ยิง model_choice=local ตรง ๆ ก็ไม่ได้ผล",
          ai_settings.public_choice("local") is None,
          "คำขอที่ส่งมาตรงต้องถูกปฏิเสธเหมือนกัน ไม่ใช่แค่ซ่อนจากรายการ")
    with _local_choice_on():
        picked = ai_settings.public_choice("local")
    check("เปิดแล้ว id ที่อนุญาต -> ได้ตัวเลือกคืนมา", picked is not None)
    if picked:
        choice, budget = picked
        check("local ชี้ไปที่โมเดลในเครื่อง", choice.provider == "ollama", str(choice))
        check("local ได้เพดานเวลาของตัวเอง ไม่ใช่ค่าตั้งต้น",
              budget is not None and budget >= 120, f"budget={budget}")
        check("ที่มาของตัวเลือกระบุว่ามาจากผู้ใช้", choice.source == "user", choice.source)

    fast = ai_settings.public_choice("fast")
    check("fast ชี้ไปที่ gemini", fast is not None and fast[0].provider == "gemini")
    check("fast ใช้เพดานเวลาตั้งต้นของระบบ", fast is not None and fast[1] is None)

    for bad in ("", None, "ไม่มีตัวนี้", "gemini-3.6-flash", "../../etc/passwd"):
        check(f"ปฏิเสธ id ที่ไม่อยู่ในรายการ: {bad!r}", ai_settings.public_choice(bad) is None)


# ───────────── 3. เส้นทางของหน้าเว็บ ─────────────

class _Spy:
    """จดว่า stream_answer ถูกเรียกด้วยอะไร โดยไม่แตะโมเดลหรือฐานข้อมูลจริง"""

    def __init__(self) -> None:
        self.kwargs: dict = {}

    def __call__(self, db, **kwargs):
        self.kwargs = kwargs
        yield 'event: done\ndata: {"answer_model": null}\n\n'


def test_route_passes_the_choice() -> None:
    print("\ntest_route_passes_the_choice")
    app.dependency_overrides[get_db] = lambda: None
    spy = _Spy()
    real_stream, real_conn = web_compat.stream_answer, web_compat.connector_for
    real_user = web_compat.shared_user
    web_compat.stream_answer = spy
    web_compat.connector_for = lambda choice: f"connector:{choice.provider}/{choice.model}"
    # เส้นทางนี้หาผู้ใช้ร่วมจากฐานก่อนเริ่มสตรีม ชุดนี้ไม่ต่อฐานจึงแทนด้วยของปลอม
    web_compat.shared_user = lambda db: SimpleNamespace(id=uuid.uuid4())
    client = TestClient(app)
    try:
        r = client.get("/ai-options")
        check("GET /ai-options ตอบ 200", r.status_code == 200, str(r.status_code))
        check("คืนรายการตัวเลือกให้หน้าเว็บ (สองตัวตามค่าตั้งต้น)",
              len(r.json().get("options", [])) == 2, r.text[:160])

        body = {"messages": [{"role": "user", "content": "สาขานี้เรียนอะไร"}], "model_choice": "local"}
        client.post("/chat-web", json=body)
        check("ปิดอยู่ -> คำขอที่ขอ local ไม่ได้ connector ของในเครื่อง",
              spy.kwargs.get("connector") is None, str(spy.kwargs.get("connector")))
        check("ปิดอยู่ -> ไม่ได้เพดานเวลาของในเครื่องด้วย",
              spy.kwargs.get("budget_s") is None, str(spy.kwargs.get("budget_s")))

        spy.kwargs = {}
        with _local_choice_on():
            client.post("/chat-web", json=body)
        check("เปิดแล้ว -> เลือก local ได้ connector ของในเครื่อง",
              "ollama" in str(spy.kwargs.get("connector")), str(spy.kwargs.get("connector")))
        check("เปิดแล้ว -> ได้เพดานเวลาของตัวเลือกนั้น",
              (spy.kwargs.get("budget_s") or 0) >= 120, str(spy.kwargs.get("budget_s")))

        spy.kwargs = {}
        body["model_choice"] = "ไม่มีตัวนี้"
        client.post("/chat-web", json=body)
        check("id ที่ไม่รู้จัก -> ถอยไปใช้ค่าของผู้ดูแล ไม่ใช่ error",
              spy.kwargs.get("connector") is None and spy.kwargs.get("budget_s") is None,
              str(spy.kwargs))

        spy.kwargs = {}
        client.post("/chat-web", json={"messages": body["messages"]})
        check("ไม่ส่งตัวเลือกมาเลย -> ใช้ค่าของผู้ดูแลเหมือนเดิม",
              spy.kwargs.get("connector") is None, str(spy.kwargs))
    finally:
        web_compat.stream_answer, web_compat.connector_for = real_stream, real_conn
        web_compat.shared_user = real_user
        app.dependency_overrides.clear()


def main() -> int:
    for fn in (test_options_list, test_choice_resolution, test_route_passes_the_choice):
        fn()
    print(f"\nตรวจ {CHECKS} ข้อ · ตก {len(FAILURES)} ข้อ")
    for f in FAILURES:
        print(f"  - {f}")
    if not FAILURES:
        print("ผ่านทั้งหมด")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
