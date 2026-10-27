"""
วัดผู้ให้บริการที่ "เขียนคำตอบ" เทียบกัน บนคลังเอกสารและขั้นตอนเดียวกันทุกอย่าง

    python -m eval.groq_candidate_check --provider gemini --out /tmp/gemini.json
    python -m eval.groq_candidate_check --provider groq --model <ชื่อโมเดล> --out /tmp/groq.json
    python -m eval.groq_candidate_check --compare /tmp/gemini.json /tmp/groq.json

**ยังไม่แตะ production** — ตัวนี้เรียก services/chat.py ตรง ๆ ในคอนเทนเนอร์ทดสอบที่ชี้
ฐานข้อมูลทดสอบ ไม่ได้ผ่านเว็บจริงและไม่ได้เปลี่ยนค่าตั้งใด ๆ ของระบบที่ให้บริการอยู่

สิ่งที่คุมให้เหมือนกันระหว่างสองผู้ให้บริการ
------------------------------------------
คลังเอกสารเดียวกัน · ขั้นค้นเอกสารเดียวกัน · พรอมต์เดียวกัน · คำถามชุดเดียวกัน ·
**embedding ทำด้วย Ollama (bge-m3) เสมอทั้งสองกรณี** ต่างกันจุดเดียวคือโมเดลที่เขียนคำตอบ

วิธีวัด
------
    เวลาตอบแรก (TTFT)  เวลาจนตัวอักษรแรกออกมา — ตัวเลขที่ผู้ใช้รู้สึกได้จริง
    เวลารวม            จนคำตอบจบ
    ผลลัพธ์            answered / not_found / refused / provider_error / harness_error
    ที่มา              จำนวนแหล่งอ้างอิงที่ระบบแนบมากับคำตอบ

**ห้ามนับ HTTP 200 ว่าสำเร็จ** ตัวนี้ไม่ได้ดูสถานะ HTTP เลย แต่ดูว่า
  1. มีข้อความคำตอบออกมาจริงไหม
  2. สถานะที่ระบบรายงานตรงกับที่คาดไว้ไหม (answered / not_found)
  3. ข้อความนั้นเป็นข้อความแจ้งข้อผิดพลาดมาตรฐานหรือเปล่า

และแยก "ชนเพดาน/บริการขัดข้อง" ออกจาก "ตอบผิด" เสมอ — ข้อที่ล้มเพราะผู้ให้บริการ
จะถูกนับเป็น provider_error ไม่ใช่คำตอบผิด เพราะมันไม่เคยได้ตอบเลย การนับรวมกัน
ทำให้สรุปว่าโมเดลคุณภาพแย่ทั้งที่ยังไม่รู้
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, "/app/backend")
sys.path.insert(0, "/app")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

QUESTIONS = Path(__file__).with_name("groq_candidate_questions.json")

# ข้อความมาตรฐานที่ระบบส่งเมื่อ "ตอบไม่ได้" — ถ้าเจอข้อความพวกนี้ ห้ามนับว่าตอบสำเร็จ
_SYSTEM_FAILURE_MARKERS = (
    "ระบบตอบไม่ได้ในขณะนี้",
    "ผู้ให้บริการโมเดลใช้ไม่ได้",
    "ระบบใช้เวลาตอบนานเกินเพดาน",
    "ขอไม่ตอบด้วยโมเดลสำรอง",
)
# สำนวนที่แปลว่า "ไม่มีข้อมูล" — ใช้ตัดสินกลุ่มคำถามที่ต้องตอบว่าไม่มี
_DENY_MARKERS = ("ไม่พบข้อมูล", "ไม่มีข้อมูล", "ไม่ได้ระบุ", "ไม่มีการกล่าวถึง",
                 "ไม่ได้กล่าวถึง", "ยังตอบให้ไม่ได้", "ไม่ได้ระบุไว้")
# สำนวนเดาจากความรู้ทั่วไป — ถ้าโผล่ในกลุ่ม "ไม่มีข้อมูล" แปลว่าเดาต่อ
_GUESS_MARKERS = ("โดยทั่วไป", "โดยปกติ", "มักจะ", "ทั่วๆ ไป", "ส่วนใหญ่แล้ว")


def build_connector(provider: str, model: str):
    """
    สร้างตัวเชื่อมต่อที่จะใช้เขียนคำตอบ โดย **คง Ollama ไว้ทำ embedding เสมอ**

    คืน (connector, คำอธิบาย) — ผู้เรียกเอาไปยัดใส่ llm_client._connector
    """
    from app.services import llm_client
    ollama = llm_client._build_ollama()

    if provider == "gemini":
        conn = llm_client.get_llm_connector()
        return conn, f"gemini:{getattr(conn, 'chat_model', '?')}"

    if provider == "groq":
        from llm.groq import GroqConnector, api_key_from_env
        chatter = GroqConnector(api_key=api_key_from_env(), chat_model=model,
                                timeout_s=llm_client.settings.llm_request_timeout_s)
        return llm_client._SplitConnector(embedder=ollama, chatter=chatter), f"groq:{model}"

    if provider == "ollama":
        return ollama, f"ollama:{ollama.chat_model}"

    raise SystemExit(f"ไม่รู้จักผู้ให้บริการ {provider!r}")


def classify(expect: str, status: str, reply: str, must_contain_any: list[str]) -> tuple[str, str]:
    """
    ตัดสินผลของหนึ่งข้อ — คืน (ผล, เหตุผล)

    ลำดับการตัดสินสำคัญ: ตรวจว่าเป็นข้อความแจ้งข้อผิดพลาดของระบบก่อนเสมอ
    ไม่งั้นข้อที่ระบบตอบไม่ได้จะถูกนับเป็น "ตอบแล้วแต่ผิด"
    """
    text = (reply or "").strip()
    if not text:
        return "provider_error", "ไม่มีข้อความคำตอบออกมาเลย"
    for marker in _SYSTEM_FAILURE_MARKERS:
        if marker in text:
            return "provider_error", f"ได้ข้อความแจ้งข้อผิดพลาดของระบบ: {marker}"

    denied = any(m in text for m in _DENY_MARKERS)

    if expect == "not_found":
        if not denied:
            return "wrong", "ต้องบอกว่าไม่มีข้อมูล แต่ตอบเป็นเนื้อหา"
        if any(g in text for g in _GUESS_MARKERS):
            return "wrong", "บอกว่าไม่มีข้อมูลแล้วเดาต่อจากความรู้ทั่วไป"
        return "ok", "ปฏิเสธถูกต้องและหยุด"

    # expect == answered
    if status not in ("answered", "structured", "cached"):
        return "wrong", f"สถานะที่ระบบรายงานคือ {status!r} ไม่ใช่การตอบ"
    if denied and len(text) < 160:
        return "wrong", "ตอบว่าไม่มีข้อมูลทั้งที่เอกสารมี"
    missing = [m for m in must_contain_any if m not in text]
    if must_contain_any and len(missing) == len(must_contain_any):
        return "needs_review", f"ไม่พบคำที่คาดว่าควรมี: {must_contain_any}"
    return "ok", "ตอบเป็นเนื้อหาและสถานะถูกต้อง"


def run_case(case: dict, label: str) -> dict:
    """รันหนึ่งข้อ (อาจมีหลายประโยคถ้าเป็นคำถามต่อเนื่อง) แล้ววัดผลของประโยคสุดท้าย"""
    from app.db.session import SessionLocal
    from app.services.chat import PriorTurn, stream_answer
    from app.services.web_compat import shared_user
    from llm.connector import LLMConnectionError

    turns = case["turns"]
    prior: list = []
    record = {"id": case["id"], "category": case["category"], "expect": case["expect"],
              "turns": turns, "provider": label}

    for index, question in enumerate(turns):
        is_last = index == len(turns) - 1
        started = time.monotonic()
        ttft = None
        parts: list[str] = []
        meta: dict = {}
        error = None
        try:
            with SessionLocal() as db:
                user_id = shared_user(db).id
                for event in stream_answer(db, user_id=user_id, session_id=None,
                                           message=question, prior=list(prior)):
                    kind, parsed = _parse(event)
                    if kind == "meta" and parsed:
                        meta = parsed
                    elif kind == "token" and parsed and parsed.get("t"):
                        if ttft is None:
                            ttft = time.monotonic() - started
                        parts.append(parsed["t"])
                    elif kind == "error":
                        error = parsed.get("detail") if parsed else "error"
        except LLMConnectionError as e:
            error = f"{type(e).__name__}: {str(e)[:160]}"
        except Exception as e:  # noqa: BLE001
            error = f"harness:{type(e).__name__}: {str(e)[:160]}"

        total = time.monotonic() - started
        reply = "".join(parts).strip()
        prior.append(PriorTurn(role="user", content=question))
        prior.append(PriorTurn(role="assistant", content=reply))

        if is_last:
            record.update({
                "status": meta.get("status", "?"),
                "ttft_s": round(ttft, 2) if ttft is not None else None,
                "total_s": round(total, 2),
                "sources": len(meta.get("sources") or []) or (1 if meta.get("source") else 0),
                "citations": len(meta.get("citations") or []),
                "reply": reply,
                "error": error,
            })
            if error and not reply:
                record["result"], record["reason"] = "provider_error", error
            else:
                record["result"], record["reason"] = classify(
                    case["expect"], record["status"], reply, case.get("must_contain_any") or [])
    return record


def _parse(event: str) -> tuple[str | None, dict | None]:
    kind = data = None
    for line in event.split("\n"):
        if line.startswith("event:"):
            kind = line[6:].strip()
        elif line.startswith("data:"):
            try:
                data = json.loads(line[5:].strip())
            except json.JSONDecodeError:
                data = None
    return kind, data


def summarise(records: list[dict]) -> dict:
    from collections import Counter
    results = Counter(r["result"] for r in records)
    timed = [r for r in records if r.get("ttft_s") is not None]
    ttfts = sorted(r["ttft_s"] for r in timed)
    totals = sorted(r["total_s"] for r in records if r.get("total_s") is not None)

    def pick(xs, q):
        return xs[min(int(len(xs) * q), len(xs) - 1)] if xs else None

    return {
        "จำนวนข้อ": len(records),
        "ผล": dict(results),
        "ตอบได้จริง": results["ok"],
        "ตอบผิด": results["wrong"],
        "ต้องอ่านเอง": results["needs_review"],
        "ล้มเพราะผู้ให้บริการ": results["provider_error"],
        "ttft_มัธยฐาน": pick(ttfts, 0.5),
        "ttft_p90": pick(ttfts, 0.9),
        "รวม_มัธยฐาน": pick(totals, 0.5),
        "รวม_p90": pick(totals, 0.9),
        "ข้อที่มีที่มาแนบมา": sum(1 for r in records if (r.get("sources") or 0) > 0),
    }


def compare(a_path: str, b_path: str) -> None:
    a = json.loads(Path(a_path).read_text(encoding="utf-8"))
    b = json.loads(Path(b_path).read_text(encoding="utf-8"))
    print(f"ก: {a['provider']}  ({a_path})")
    print(f"ข: {b['provider']}  ({b_path})")
    print()
    print(f"{'ข้อ':<14}{'หมวด':<14}{'ก':<16}{'ข':<16}{'ก TTFT':>9}{'ข TTFT':>9}")
    by_id = {r["id"]: r for r in b["records"]}
    for ra in a["records"]:
        rb = by_id.get(ra["id"], {})
        print(f"{ra['id']:<14}{ra['category']:<14}{ra['result']:<16}{rb.get('result','-'):<16}"
              f"{ra.get('ttft_s') or '-':>9}{rb.get('ttft_s') or '-':>9}")
    print()
    for name, data in (("ก", a), ("ข", b)):
        print(f"--- สรุปของ {name} ({data['provider']}) ---")
        for k, v in data["summary"].items():
            print(f"    {k}: {v}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=["gemini", "groq", "ollama"])
    ap.add_argument("--model", default="", help="ชื่อโมเดล (จำเป็นสำหรับ groq)")
    ap.add_argument("--out", default="")
    ap.add_argument("--only", default="", help="รันเฉพาะหมวดนี้")
    ap.add_argument("--compare", nargs=2, metavar=("ก", "ข"))
    args = ap.parse_args()

    if args.compare:
        compare(*args.compare)
        return 0
    if not args.provider:
        ap.error("ต้องระบุ --provider หรือ --compare")

    cases = json.loads(QUESTIONS.read_text(encoding="utf-8"))["cases"]
    if args.only:
        cases = [c for c in cases if c["category"] == args.only]

    from app.services import llm_client
    connector, label = build_connector(args.provider, args.model)
    llm_client._connector = connector
    print(f"ผู้ให้บริการที่เขียนคำตอบ: {label}")
    print(f"embedding: ollama:{llm_client.settings.embed_model} (คงเดิมเสมอ)")
    print(f"จำนวนข้อ: {len(cases)}\n")

    records = []
    for case in cases:
        record = run_case(case, label)
        records.append(record)
        mark = {"ok": "ผ่าน", "wrong": "ผิด", "needs_review": "ต้องอ่าน",
                "provider_error": "ผู้ให้บริการล้ม"}.get(record["result"], record["result"])
        print(f"  [{mark}] {record['id']:<14} {record['category']:<12} "
              f"ttft={record.get('ttft_s')}s total={record.get('total_s')}s "
              f"สถานะ={record.get('status')} ที่มา={record.get('sources')}")
        if record["result"] != "ok":
            print(f"      เหตุผล: {record['reason']}")

    out = {"provider": label, "เวลาที่รัน": time.strftime("%Y-%m-%d %H:%M:%S"),
           "summary": summarise(records), "records": records}
    print("\n--- สรุป ---")
    for k, v in out["summary"].items():
        print(f"  {k}: {v}")
    if args.out:
        Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nบันทึกผลที่ {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
