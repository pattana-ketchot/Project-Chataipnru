"""
อ่านรายชื่อโมเดลที่ **บัญชีนี้** ใช้ได้จริง แล้ววัดเพดานโควตาของแต่ละตัวจากของจริง

    python -m eval.groq_models_probe                 # อ่านรายชื่อ + วัดโควตา + เสนอตัวที่ควรใช้
    python -m eval.groq_models_probe --list-only     # อ่านรายชื่ออย่างเดียว ไม่ยิงโมเดล

ทำไมต้องวัดเอง ไม่อ่านจากเอกสาร
------------------------------
หน้าเอกสารของ Groq ไม่ได้บอกเพดานของบัญชีเรา มันบอกให้ไปดูหน้า /settings/limits
ของบัญชีตัวเอง และที่สำคัญกว่านั้น **หน้าเอกสารขัดกันเอง** — ตรวจเมื่อ 16 ต.ค. 2569
พบว่า `llama-3.1-8b-instant` และ `llama-3.3-70b-versatile` ยังอยู่ในตารางโมเดล
สถานะ production แต่หน้า deprecations ระบุวันปิดเป็น 16/08/26 ซึ่งผ่านมาแล้วสองเดือน

ของจริงมีอยู่ที่เดียวคือคำตอบของ API ตัวนี้จึงยิงคำขอเล็กที่สุดเท่าที่ทำได้ไปที่แต่ละ
โมเดล แล้วอ่าน header `x-ratelimit-*` ที่ Groq แนบกลับมา

ราคาของการวัด: คำขอละ 1 โทเคนต่อโมเดล — กินโควตาน้อยมากแต่ได้ตัวเลขจริง

SECURITY: อ่านคีย์จากตัวแปรสภาพแวดล้อมเท่านั้น และไม่พิมพ์ค่าคีย์ออกมาไม่ว่ากรณีใด
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, "/app/backend")
sys.path.insert(0, "/app")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# โมเดลที่ไม่ใช่ "เขียนคำตอบ" — ตัดออกตั้งแต่ต้น ไม่ต้องเสียโควตายิง
_NOT_CHAT = ("whisper", "tts", "orpheus", "prompt-guard", "guard", "safeguard")


def is_chat_model(model_id: str) -> bool:
    low = model_id.lower()
    return not any(word in low for word in _NOT_CHAT)


def probe_one(key: str, model_id: str, timeout_s: int = 30) -> dict:
    """
    ยิงคำขอเล็กที่สุดไปหนึ่งครั้ง เพื่อดูว่า "ใช้ได้จริงไหม" และเพดานเป็นเท่าไร

    คืนผลเป็น dict เสมอ ไม่โยนข้อยกเว้น เพราะเป้าหมายคือสำรวจให้ครบทุกตัว
    """
    import httpx
    from llm.groq import QUOTA_HEADERS, _BASE_URL

    out: dict = {"model": model_id}
    started = time.monotonic()
    try:
        with httpx.Client(base_url=_BASE_URL, timeout=timeout_s,
                          headers={"Authorization": f"Bearer {key}",
                                   "Content-Type": "application/json"}) as client:
            resp = client.post("/chat/completions", json={
                "model": model_id,
                "messages": [{"role": "user", "content": "hi"}],
                "max_completion_tokens": 1,
                "temperature": 0,
            })
        out["http"] = resp.status_code
        out["seconds"] = round(time.monotonic() - started, 2)
        out["quota"] = {k: resp.headers[k] for k in QUOTA_HEADERS if k in resp.headers}
        if resp.status_code == 200:
            out["ok"] = True
        else:
            out["ok"] = False
            try:
                body = resp.json()
                out["error"] = (body.get("error") or {}).get("message", "")[:160]
            except Exception:  # noqa: BLE001
                out["error"] = resp.text[:160]
    except Exception as e:  # noqa: BLE001
        out.update({"ok": False, "http": None, "seconds": round(time.monotonic() - started, 2),
                    "error": f"{type(e).__name__}: {str(e)[:160]}", "quota": {}})
    return out


def _as_int(value: str | None) -> int | None:
    """แปลงค่าจาก header เป็นตัวเลข — Groq ส่งมาเป็นสตริง และบางตัวมีหน่วยต่อท้าย"""
    if not value:
        return None
    digits = "".join(ch for ch in value if ch.isdigit())
    return int(digits) if digits else None


def recommend(results: list[dict]) -> tuple[str | None, str]:
    """
    เลือกโมเดลที่เหมาะกับโควตาฟรีที่สุด — คืน (ชื่อโมเดล, เหตุผล)

    กฎการเลือก เรียงตามลำดับความสำคัญ
      1. ต้องยิงผ่านจริง (HTTP 200) — ตัวที่เอกสารบอกว่ามีแต่ยิงไม่ผ่าน ไม่นับ
      2. ต้องไม่ใช่โมเดลสถานะ preview (ผู้เรียกเป็นคนบอกว่าตัวไหน preview)
      3. เอาตัวที่ "โทเคนต่อนาที" สูงสุด เพราะคอขวดของระบบนี้คือ TPM ไม่ใช่ RPM —
         หนึ่งคำถามของผู้ใช้เรียกโมเดลหลายครั้งและแต่ละครั้งแนบเอกสารยาว
      4. ถ้าเท่ากัน เอาตัวที่ตอบเร็วกว่าในการยิงสำรวจ
    """
    usable = [r for r in results if r.get("ok") and not r.get("preview")]
    if not usable:
        return None, "ไม่มีโมเดลสถานะ production ตัวใดที่ยิงผ่านเลย"

    def tpm(r: dict) -> int:
        return _as_int((r.get("quota") or {}).get("x-ratelimit-limit-tokens")) or 0

    usable.sort(key=lambda r: (-tpm(r), r.get("seconds") or 99))
    best = usable[0]
    detail = f"โทเคนต่อนาที {tpm(best) or 'ไม่ทราบ'} · ยิงสำรวจใช้เวลา {best.get('seconds')} วินาที"
    return best["model"], detail


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list-only", action="store_true")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    from llm.groq import api_key_from_env, list_models
    key = api_key_from_env()
    print("อ่านคีย์จากตัวแปรสภาพแวดล้อมแล้ว (ไม่แสดงค่า)\n")

    models = list_models(key)
    print(f"=== โมเดลที่บัญชีนี้เรียกใช้ได้ ({len(models)} รายการจาก API) ===")
    for m in sorted(models, key=lambda x: x.get("id", "")):
        flags = []
        if m.get("context_window"):
            flags.append(f"context={m['context_window']}")
        if m.get("max_completion_tokens"):
            flags.append(f"max_out={m['max_completion_tokens']}")
        if m.get("owned_by"):
            flags.append(f"โดย {m['owned_by']}")
        print(f"  {m.get('id','?'):<42} {' · '.join(flags)}")

    chat_models = [m.get("id") for m in models if m.get("id") and is_chat_model(m["id"])]
    print(f"\nคัดเฉพาะที่ใช้เขียนคำตอบได้: {len(chat_models)} ตัว")
    if args.list_only:
        return 0

    print("\n=== ยิงสำรวจตัวละ 1 โทเคน เพื่ออ่านเพดานโควตาจริงของบัญชีนี้ ===")
    results = []
    for model_id in chat_models:
        r = probe_one(key, model_id)
        results.append(r)
        q = r.get("quota") or {}
        line = (f"  {model_id:<42} http={r.get('http')} "
                f"{'ใช้ได้' if r.get('ok') else 'ใช้ไม่ได้'} {r.get('seconds')}s")
        if q:
            line += (f" · คำขอ/วัน={q.get('x-ratelimit-limit-requests','?')}"
                     f" · โทเคน/นาที={q.get('x-ratelimit-limit-tokens','?')}")
        print(line)
        if not r.get("ok") and r.get("error"):
            print(f"      {r['error']}")

    print("\n  หมายเหตุ: สถานะ preview/production อ่านจากเอกสารของ Groq ไม่ใช่จาก API")
    print("  ให้ทำเครื่องหมาย preview ในไฟล์ผลก่อนใช้ recommend() ถ้าต้องการให้มันคัดออก")

    name, why = recommend(results)
    print(f"\n=== เสนอให้ใช้: {name or '(ไม่มี)'} ===\n  {why}")

    if args.out:
        Path(args.out).write_text(json.dumps(
            {"เวลาที่รัน": time.strftime("%Y-%m-%d %H:%M:%S"),
             "models": models, "probe": results, "recommended": name},
            ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nบันทึกผลที่ {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
