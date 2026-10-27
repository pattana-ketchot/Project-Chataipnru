"""
รูปแบบสตรีม SSE ต้องไม่เปลี่ยนเพราะการเติมบรรทัดที่มาและเหตุการณ์ sources

    cd backend && python tests/test_sse_format.py

ที่มาของชุดนี้ — รอบ 13/14 เติมสองอย่างเข้าไปในเส้นทางสตรีม
    1. token ก้อนสุดท้ายที่มีบรรทัดที่มา (ขึ้นบรรทัดใหม่สองครั้งแล้วตามด้วย "ที่มา: ...")
    2. เหตุการณ์ใหม่ชื่อ sources ที่ส่งที่มาแบบมีโครงสร้าง

ทั้งสองอย่างต้องไม่ทำให้ผู้รับเดิมพัง · ผู้รับเดิมที่รู้จักเพียง meta/token/done
(เช่น /chat-web ซึ่งแกะเฉพาะ token ออกเป็นข้อความล้วน) ต้องยังได้คำตอบครบทุกตัวอักษร
และลำดับเหตุการณ์ต้องเป็น meta -> token... -> [sources] -> done เสมอ

ยิงผ่าน route จริงด้วย TestClient ไม่เรียก _stream_answer_events ตรงๆ เพราะบั๊กที่เคย
เจอ (ContextVar ข้าม step) มองไม่เห็นเมื่อเรียกฟังก์ชันตรงๆ

ขั้นค้นเอกสารใช้ embedding ของจริง ส่วนขั้นคุยใช้ปลายทางปลอมที่ตอบข้อความซึ่งคัดมาจาก
เนื้อหาในเอกสารจริง เพื่อให้ชั้นเลือกหลักฐานและชั้นตรวจข้ออ้างทำงานแบบเดียวกับของจริง
โดยผลไม่แกว่งตามโมเดล
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

CHECKS = 0
FAILURES: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    if ok:
        print(f"  [ผ่าน] {label}" + (f" — {detail}" if detail else ""))
    else:
        FAILURES.append(f"{label} — {detail}")
        print(f"  [ตก]  {label} — {detail}")


from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.core.security import create_access_token  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services import chat as C  # noqa: E402
from app.services import llm_client  # noqa: E402

# แคชต้องปิด ไม่งั้นคำตอบที่ได้คือของเดิมในแคชซึ่งไม่ผ่านชั้นเลือกหลักฐานใหม่
C.cache_lookup = lambda db, q, v: None
C.cache_store = lambda *a, **k: None

EMBEDDER = llm_client._build_ollama()


class FakeChatter:
    """ปลายทางคุยที่ตอบคงที่ — ด่านตรวจเอกสารผ่าน และคำตอบสตรีมเป็นหลายก้อน"""

    answer_token_cap = 2048

    def __init__(self, answer: str) -> None:
        self.answer = answer
        self.calls: list[str] = []

    def chat(self, *a, **k):
        self.calls.append("chat")
        return json.dumps(
            {"can_answer": True, "reason": "เอกสารมีข้อเท็จจริงที่ถาม (ปลายทางทดสอบ)"},
            ensure_ascii=False,
        )

    def chat_stream(self, *a, **k):
        self.calls.append("chat_stream")
        step = max(1, len(self.answer) // 4)
        for i in range(0, len(self.answer), step):
            yield self.answer[i:i + step]


def events_of(body: str) -> list[tuple[str, dict]]:
    """แกะสตรีม SSE เป็นรายการ (ชื่อเหตุการณ์, ข้อมูล) ตามลำดับที่ได้รับ"""
    out = []
    for block in body.split("\n\n"):
        name, data = None, None
        for line in block.splitlines():
            if line.startswith("event: "):
                name = line[len("event: "):]
            elif line.startswith("data: "):
                data = json.loads(line[len("data: "):])
        if name is not None:
            out.append((name, data if data is not None else {}))
    return out


def order_is_valid(names: list[str]) -> tuple[bool, str]:
    """meta หนึ่งครั้งนำหน้า · token ติดกันเป็นช่วงเดียว · sources (ถ้ามี) ก่อน done ท้ายสุด"""
    if not names or names[0] != "meta":
        return False, f"เหตุการณ์แรกคือ {names[:1]}"
    if names.count("meta") != 1:
        return False, f"มี meta {names.count('meta')} ครั้ง"
    if names[-1] != "done":
        return False, f"เหตุการณ์สุดท้ายคือ {names[-1]}"
    if names.count("done") != 1:
        return False, f"มี done {names.count('done')} ครั้ง"
    if names.count("sources") > 1:
        return False, f"มี sources {names.count('sources')} ครั้ง"
    body = names[1:-1]
    tokens = [i for i, n in enumerate(body) if n == "token"]
    if tokens and tokens != list(range(tokens[0], tokens[-1] + 1)):
        return False, "เหตุการณ์ token ไม่ติดกันเป็นช่วงเดียว"
    if "sources" in body and tokens and body.index("sources") < tokens[-1]:
        return False, "sources มาก่อน token ตัวสุดท้าย"
    unknown = sorted(set(names) - {"meta", "token", "sources", "done"})
    if unknown:
        return False, f"มีเหตุการณ์ที่ไม่รู้จัก {unknown}"
    return True, ""


META_KEYS = {"session_id", "status", "search_query", "top_score", "in_scope",
             "citations", "source", "sources"}
RAG_Q = "หลักสูตรวิทยาการคอมพิวเตอร์ พ.ศ. 2566 มีการฝึกประสบการณ์วิชาชีพอย่างไร"

with SessionLocal() as db:
    user_id = db.scalars(select(User.id).limit(1)).first()
    assert user_id is not None, "ต้องมีผู้ใช้ในฐานข้อมูลเพื่อยิงเส้นทางที่ตรวจสิทธิ์"
    AUTH = {"Authorization": f"Bearer {create_access_token(str(user_id))}"}

    # ข้อความคำตอบปลอมคัดมาจากเนื้อหาจริงของชิ้นที่การค้นให้คะแนนสูงสุด เพื่อให้
    # ชั้นเลือกหลักฐานต้องเลือกหน้านั้นได้ และชั้นตรวจข้ออ้างต้องยืนยันได้ครบ
    TOP = C._retrieve(db, EMBEDDER, RAG_Q)[0]
    EXCERPT = " ".join(TOP.content.split())[:160]

CLIENT = TestClient(app)
print(f"ชิ้นหลักฐานที่คัดข้อความมา: หน้า {TOP.page_number} ของ {TOP.course_title}")

print()
print("1. คำตอบจากฐานข้อมูล (ไม่เรียกโมเดล) — ลำดับและคีย์ของเหตุการณ์ต้องเหมือนเดิม")
r = CLIENT.post("/chat/stream", headers=AUTH,
                json={"message": "หลักสูตรวิทยาการคอมพิวเตอร์ พ.ศ. 2561 ต้องเรียนทั้งหมดกี่หน่วยกิต"})
check("ได้สถานะ 200", r.status_code == 200, f"code={r.status_code}")
check("ชนิดข้อมูลเป็น text/event-stream",
      "text/event-stream" in r.headers.get("content-type", ""), r.headers.get("content-type", ""))
evs = events_of(r.text)
names = [n for n, _ in evs]
ok, why = order_is_valid(names)
check("ลำดับเหตุการณ์ถูกต้อง", ok, why or " -> ".join(names))
meta = next((d for n, d in evs if n == "meta"), {})
check("meta มีคีย์เดิมครบ", META_KEYS <= set(meta), f"ขาด {sorted(META_KEYS - set(meta))}")
check("meta.status = answered", meta.get("status") == "answered", str(meta.get("status")))
check("meta.top_score เป็นตัวเลข", isinstance(meta.get("top_score"), (int, float)),
      str(meta.get("top_score")))
text_only = "".join(d.get("t", "") for n, d in evs if n == "token")
check("ผู้รับที่อ่านเฉพาะ token ได้คำตอบครบ", "130" in text_only and "ที่มา:" in text_only,
      text_only[:120].replace("\n", " / "))
check("ที่มาของคำตอบจากฐานอยู่ในข้อความเหมือนเดิม", "cs61.pdf" in text_only,
      text_only[-90:].replace("\n", " / "))

print()
print("2. คำตอบจากการค้นเอกสาร — token ก้อนที่มาและเหตุการณ์ sources")
FAKE = FakeChatter(EXCERPT)
real = llm_client._connector
llm_client._connector = llm_client._SplitConnector(embedder=EMBEDDER, chatter=FAKE)
try:
    r = CLIENT.post("/chat/stream", headers=AUTH, json={"message": RAG_Q})
    check("ได้สถานะ 200", r.status_code == 200, f"code={r.status_code}")
    evs = events_of(r.text)
    names = [n for n, _ in evs]
    ok, why = order_is_valid(names)
    check("ลำดับเหตุการณ์ถูกต้อง", ok, why or " -> ".join(names))
    check("ขั้นเขียนคำตอบเรียกปลายทางโมเดลจริง", "chat_stream" in FAKE.calls, str(FAKE.calls))
    meta = next((d for n, d in evs if n == "meta"), {})
    check("meta มีคีย์เดิมครบ", META_KEYS <= set(meta), f"ขาด {sorted(META_KEYS - set(meta))}")
    check("meta.citations ไม่ว่าง (คำตอบนี้มาจากการค้น)", bool(meta.get("citations")),
          str(len(meta.get("citations") or [])))
    toks = [d.get("t", "") for n, d in evs if n == "token"]
    check("คำตอบถูกทยอยส่งหลายก้อน", len(toks) >= 3, f"{len(toks)} ก้อน")
    stream_text = "".join(toks)
    check("ผู้รับที่อ่านเฉพาะ token ได้ทั้งคำตอบและบรรทัดที่มา",
          EXCERPT[:40] in stream_text and "ที่มา" in stream_text,
          stream_text[-120:].replace("\n", " / "))
    check("บรรทัดที่มาเป็นก้อนสุดท้ายและขึ้นบรรทัดใหม่สองครั้ง",
          toks[-1].startswith("\n\n") and "ที่มา" in toks[-1], repr(toks[-1][:60]))
    src_ev = next((d for n, d in evs if n == "sources"), None)
    check("มีเหตุการณ์ sources", src_ev is not None, "")
    rows = (src_ev or {}).get("sources") or []
    check("sources เป็นรายการที่มีไฟล์และหน้า",
          bool(rows) and all(x.get("file") and x.get("page_start") for x in rows), str(rows)[:160])
    check("หน้าที่อ้างคือหน้าของชิ้นที่ข้อความมาจากจริง",
          any(x.get("page_start") == TOP.page_number for x in rows),
          f"ได้ {[x.get('page_start') for x in rows]} ต้องมี {TOP.page_number}")
    check("ทุกรายการบอกสถานะการตรวจข้ออ้าง",
          all("claim_status" in x for x in rows), str([x.get("claim_status") for x in rows]))
    check("ข้ออ้างของคำตอบที่คัดจากเอกสารต้องรองรับได้ครบ",
          all(x.get("claim_status") in ("รองรับครบ", "ไม่มีข้ออ้างที่ตรวจได้") for x in rows),
          str([(x.get("claim_status"), x.get("unverified_claims")) for x in rows]))

    print()
    print("3. /chat-web (ข้อความล้วน) ต้องได้ข้อความเดียวกับที่ประกอบจาก token")
    w = CLIENT.post("/chat-web", json={"messages": [{"role": "user", "content": RAG_Q}]})
    check("ได้สถานะ 200", w.status_code == 200, f"code={w.status_code}")
    check("ชนิดข้อมูลยังเป็น text/plain",
          "text/plain" in w.headers.get("content-type", ""), w.headers.get("content-type", ""))
    check("ไม่มีเศษรูปแบบ SSE หลุดไปหน้าเว็บ",
          "event:" not in w.text and "data:" not in w.text, w.text[:120])
    check("หน้าเว็บได้บรรทัดที่มาด้วย", "ที่มา" in w.text, w.text[-120:].replace("\n", " / "))
    check("ข้อความที่หน้าเว็บได้ตรงกับที่ประกอบจาก token", w.text.strip() == stream_text.strip(),
          f"เว็บ {len(w.text.strip())} ตัวอักษร · สตรีม {len(stream_text.strip())} ตัวอักษร")
finally:
    llm_client._connector = real

print()
print(f"จุดตรวจ {CHECKS} จุด")
if FAILURES:
    print(f"ตก {len(FAILURES)} จุด")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("ผ่านทั้งหมด")
