"""
ตรวจสวิตช์เลือกโมเดลรวมกับ patch ตัวสำรองในเครื่อง ผ่าน API จริง

    python eval/model_switch_api_check.py --api http://127.0.0.1:8099 --mode prod
    python eval/model_switch_api_check.py --api http://127.0.0.1:8099 --mode slow

**ยิงเฉพาะเครื่อง local** ต้องใส่ --allow-remote ถ้าจะยิงที่อื่น เพราะชุดนี้เขียนฐานข้อมูล
(ล้างแคชคำตอบ อ่านตัวนับ) และตั้งค่าสวิตช์ จึงห้ามไปโดน production โดยไม่ตั้งใจ

สองโหมด
-------
prod  ค่าเหมือน production (RAG_TIME_BUDGET_S=30 · CHAT_TOP_K=25)
      ตอบคำถามที่ต้องอ้างอิงเอกสารด้วยโมเดลในเครื่องไม่ทันเพดาน — ชุดนี้ยืนยันว่า
      "ไม่ทัน" จริง และยืนยันว่าสวิตช์ยังทำงานถูก (ไม่แอบไปใช้เจ้าอื่น)
slow  เพดานกว้างพอให้โมเดลในเครื่องเขียนจบ (RAG_TIME_BUDGET_S=300 · CHAT_TOP_K=8)
      **ไม่ใช่ข้อเสนอให้เปลี่ยนค่าของ production** มีไว้เพื่อดูคำตอบที่โมเดลในเครื่อง
      เขียนจริง ซึ่งโหมด prod ไม่มีให้ดูเลยเพราะตายก่อนทุกครั้ง

ข้อจำกัดของชุดนี้
----------------
เครื่องที่รันไม่มี GEMINI_API_KEY จึงตรวจฝั่ง Gemini ได้แค่ "การตัดสิน" (เลือกไว้แต่
ไม่มีคีย์ → ไม่ยอมใช้ และบอกเหตุผล) ตรวจไม่ได้ว่าคำตอบจาก Gemini ออกมาหน้าตาอย่างไร
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import httpx

CHECKS = 0
FAILURES: list[str] = []

# คอนเทนเนอร์ฐานข้อมูล — **ชื่อเดียวกันทั้งเครื่อง local และเซิร์ฟเวอร์ production**
# docker exec ที่ไม่ได้ผ่าน ssh จึงยิงโดนของ local เงียบ ๆ และบนเซิร์ฟเวอร์ก็ยิงโดน
# คอนเทนเนอร์ของ production ตรง ๆ · ตัวที่กันไม่ให้แตะข้อมูลจริงคือ "ชื่อฐาน" ข้างล่าง
PG = os.getenv("SWITCH_CHECK_PG", "course-advisor-system-postgres-1")

# ชุดนี้ **เขียน** ฐานข้อมูล: ล้าง chat_answer_cache และตั้ง/ลบแถว web.ai_settings
# จึงรับได้เฉพาะฐานที่ชื่อลงท้าย _test (ดู require_test_db) ห้ามชี้ไปที่ course_advisor
DB = os.getenv("SWITCH_CHECK_DB", "course_advisor_test")


def require_test_db() -> None:
    """
    หยุดทันทีถ้าฐานที่ชี้ไม่ใช่ฐานทดสอบ — กันการล้างแคชของ production โดยไม่ตั้งใจ

    ตรวจทั้งชื่อฐานที่ใช้กับ docker exec และชื่อฐานใน DSN เพราะสองทางนี้ตั้งแยกกันได้
    """
    names = [DB]
    if dsn := os.getenv("SWITCH_CHECK_DSN"):
        names.append((urlparse(dsn).path or "").lstrip("/"))
    for name in names:
        if not name.endswith("_test"):
            raise SystemExit(
                "ปฏิเสธ: ชุดนี้เขียนฐานข้อมูล (ล้างแคชคำตอบ ตั้งค่าสวิตช์) จึงรับได้เฉพาะฐาน"
                f"ที่ชื่อลงท้าย _test · ได้รับ {name!r}"
            )

# คำถามที่ต้องให้โมเดลตอบจากเอกสาร ไม่ใช่คำถามที่ฐานหลักสูตรตอบได้เอง
# (คำถามอย่าง "คุณสมบัติผู้สมัคร" ตอบจากฐานได้ answer_model จะเป็น null
#  แล้วชุดทดสอบจะดูเหมือนผ่านทั้งที่ไม่เคยแตะโมเดลเลย)
DOC_QUESTIONS = [
    "หลักสูตรวิทยาการคอมพิวเตอร์เรียนเกี่ยวกับอะไร",
    "หลักสูตรวิทยาการคอมพิวเตอร์มีวิชาอะไรบ้าง",
    "สาขาสาธารณสุขศาสตร์มีวิชาบังคับอะไรบ้าง",
]


def check(label: str, ok: bool, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    if ok:
        print(f"  [ผ่าน] {label}" + (f" — {detail}" if detail else ""))
    else:
        FAILURES.append(f"{label} — {detail}")
        print(f"  [ตก]  {label} — {detail}")


def psql(sql: str) -> str:
    """
    สั่ง SQL กับฐานทดสอบ — ผ่าน psycopg เมื่อมี SWITCH_CHECK_DSN ไม่งั้นผ่าน docker exec

    ต้องมีทางผ่าน DSN เพราะตอนรันในคอนเทนเนอร์ทดสอบบนเซิร์ฟเวอร์จะไม่มี docker CLI
    ให้เรียก (และไม่ควรมี) ส่วนตอนรันบนเครื่องพัฒนา docker exec สะดวกกว่าเพราะไม่ต้อง
    ส่งรหัสผ่านฐานข้อมูลเข้ามา
    """
    dsn = os.getenv("SWITCH_CHECK_DSN")
    if dsn:
        import psycopg  # นำเข้าเมื่อใช้จริง เพื่อให้เส้นทาง docker exec ไม่ต้องมี psycopg
        with psycopg.connect(dsn, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute(sql)
            if cur.description is None:
                return ""
            return "\n".join("|".join("" if v is None else str(v) for v in row) for row in cur.fetchall())
    out = subprocess.run(["docker", "exec", PG, "psql", "-U", "postgres", "-d", DB, "-t", "-A", "-c", sql],
                         capture_output=True, text=True, encoding="utf-8")
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip()[:300])
    return (out.stdout or "").strip()


def usage() -> dict[str, int]:
    """ตัวนับของวันนี้บนฐานทดสอบ · เธรดเบื้องหลังเขียนทุก 30 วินาที จึงสั่ง flush ก่อนอ่าน"""
    rows = psql("select event, n from public.llm_usage_daily where day = current_date")
    return {r.split("|")[0]: int(r.split("|")[1]) for r in rows.splitlines() if "|" in r}


def token() -> str:
    """ออก access token ของผู้ดูแลเอง — ชุดนี้ตั้ง JWT_SECRET ของเซิร์ฟเวอร์ทดสอบเอง"""
    os.environ.setdefault("DATABASE_URL", f"postgresql+psycopg://postgres@127.0.0.1:5432/{DB}")
    from app.core.security import create_access_token
    uid = psql("select id from users where email = 'switch-check@test.local'")
    if not uid:
        raise RuntimeError("ไม่พบผู้ใช้ switch-check@test.local บนฐานทดสอบ")
    return create_access_token(uid)


class Api:
    def __init__(self, base: str, tok: str) -> None:
        self.base = base.rstrip("/")
        self.h = {"Authorization": f"Bearer {tok}"}
        self.c = httpx.Client(timeout=400)

    def get_settings(self) -> dict:
        r = self.c.get(f"{self.base}/site-admin/ai-settings", headers=self.h)
        r.raise_for_status()
        return r.json()

    def put_settings(self, provider=None, model=None) -> httpx.Response:
        return self.c.put(f"{self.base}/site-admin/ai-settings", headers=self.h,
                          json={"provider": provider, "model": model})

    def ask(self, q: str) -> tuple[int, dict | str, float]:
        psql("truncate table chat_answer_cache")  # แคชต้องไม่กลบผลของการสลับโมเดล
        t0 = time.monotonic()
        r = self.c.post(f"{self.base}/chat", headers=self.h, json={"message": q})
        spent = time.monotonic() - t0
        try:
            return r.status_code, r.json(), spent
        except json.JSONDecodeError:
            return r.status_code, r.text[:300], spent

    def ask_stream(self, q: str) -> tuple[list[dict], float]:
        """
        เส้นทางสตรีมแบบ SSE (/chat/stream) — คืนเหตุการณ์ทั้งหมด

        ใช้เส้นทางนี้ไม่ใช่ /chat-web เพราะ /chat-web คืน "ข้อความดิบ" ให้หน้าเว็บ
        ต่อเข้ากล่องแชทตรง ๆ จึงไม่มีเหตุการณ์ done และไม่มีช่อง answer_model ให้ตรวจ
        ทั้งสองเส้นทางเดินตรรกะเดียวกันผ่าน stream_answer()
        """
        psql("truncate table chat_answer_cache")
        t0 = time.monotonic()
        events: list[dict] = []
        with self.c.stream("POST", f"{self.base}/chat/stream", headers=self.h,
                           json={"message": q}) as r:
            name = ""
            for line in r.iter_lines():
                if line.startswith("event:"):
                    name = line.split(":", 1)[1].strip()
                elif line.startswith("data:"):
                    try:
                        events.append({"event": name, **json.loads(line.split(":", 1)[1].strip())})
                    except json.JSONDecodeError:
                        events.append({"event": name, "raw": line[:120]})
        return events, time.monotonic() - t0


# ───────────── 1. สภาพตั้งต้น — ยังไม่เลือก ─────────────

def section_env_default(api: Api) -> None:
    print("\n=== 1. ยังไม่เลือก — ใช้ค่าจาก environment ===")
    psql("delete from web.ai_settings where id = 1")
    v = api.get_settings()
    raw = json.dumps(v, ensure_ascii=False)
    check("ไม่มีค่าที่บันทึก", v["saved"]["provider"] is None, str(v["saved"]))
    check("ที่ใช้จริงมาจาก env", v["effective"]["source"] == "env", str(v["effective"]))
    check("ไม่ถือว่าทำตามค่าที่บันทึก", v["effective"]["honoured"] is False, str(v["effective"]))
    check("ไม่มีคีย์ปนออกมาในคำตอบ", "api_key" not in raw and "AIza" not in raw)
    check("บอกแค่ว่ามีคีย์หรือไม่", isinstance(v["defaults"]["has_gemini_key"], bool),
          f"has_gemini_key={v['defaults']['has_gemini_key']}")
    check("embedding ยังเป็น bge-m3 และเปลี่ยนไม่ได้",
          v["embedding"]["model"].startswith("bge-m3") and v["embedding"]["changeable"] is False,
          str(v["embedding"]))
    check("ผู้ให้บริการที่รองรับมีสองเจ้าเท่าเดิม", sorted(v["providers"]) == ["gemini", "ollama"],
          str(v["providers"]))


# ───────────── 2. เลือก Gemini ที่ไม่มีคีย์ ─────────────

def section_gemini_without_key(api: Api) -> None:
    print("\n=== 2. เลือก Gemini บนเครื่องที่ไม่มีคีย์ — ต้องไม่ยอมใช้ และบอกเหตุผล ===")
    before = usage()
    r = api.put_settings(provider="gemini")
    check("บันทึกตัวเลือกได้", r.status_code == 200, f"HTTP {r.status_code} {r.text[:120]}")
    v = api.get_settings()
    check("ค่าที่บันทึกคือ gemini", v["saved"]["provider"] == "gemini", str(v["saved"]))
    check("ที่ใช้จริงไม่ใช่ gemini", v["effective"]["provider"] != "gemini", str(v["effective"]))
    check("ไม่ถือว่าทำตามค่าที่บันทึก", v["effective"]["honoured"] is False, str(v["effective"]))
    check("มีคำอธิบายว่าทำไมยังไม่มีผล", bool(v["effective"]["note"]), str(v["effective"]["note"]))
    after = usage()
    check("ไม่มีการเรียก Gemini เกิดขึ้นเลย",
          all(not k.startswith("gemini") or after.get(k, 0) == before.get(k, 0) for k in after),
          f"ก่อน={before} หลัง={after}")


# ───────────── 3. เลือก Ollama — เปลี่ยนทันทีโดยไม่ restart ─────────────

def section_pick_ollama(api: Api, model: str) -> None:
    print(f"\n=== 3. เลือก Ollama ({model}) — ค่าที่ใช้จริงเปลี่ยนทันทีโดยไม่ restart ===")
    r = api.put_settings(provider="ollama", model=model)
    check("บันทึกตัวเลือกได้", r.status_code == 200, f"HTTP {r.status_code} {r.text[:120]}")
    v = api.get_settings()
    check("ที่ใช้จริงเป็น ollama ทันที", v["effective"]["provider"] == "ollama", str(v["effective"]))
    check("รุ่นที่ใช้จริงคือรุ่นที่เลือก", v["effective"]["model"] == model, str(v["effective"]))
    check("ที่มาคือค่าที่บันทึก", v["effective"]["source"] == "db", str(v["effective"]))
    check("ทำตามค่าที่บันทึก", v["effective"]["honoured"] is True, str(v["effective"]))
    check("embedding ไม่เปลี่ยนตามสวิตช์", v["embedding"]["model"].startswith("bge-m3"),
          str(v["embedding"]))


# ───────────── 4. ถามจริงด้วยโมเดลในเครื่อง ─────────────

def section_ask_prod(api: Api) -> None:
    print("\n=== 4. โหมด prod — ถามคำถามที่ต้องอ้างอิงเอกสารด้วยโมเดลในเครื่อง ===")
    before = usage()
    answered = 0
    for q in DOC_QUESTIONS:
        code, body, spent = api.ask(q)
        model = body.get("answer_model") if isinstance(body, dict) else None
        status = body.get("status") if isinstance(body, dict) else None
        if code == 200 and model:
            answered += 1
        print(f"    · {q[:46]:46s} HTTP {code} · {spent:5.1f}s · status={status} · answer_model={model}")
    after = usage()
    check("โมเดลในเครื่องถูกเรียกจริง",
          after.get("local_primary_attempt", 0) > before.get("local_primary_attempt", 0),
          f"ก่อน={before.get('local_primary_attempt', 0)} หลัง={after.get('local_primary_attempt', 0)}")
    check("ไม่มีคำตอบใดมาจาก Gemini",
          after.get("gemini_ok", 0) == before.get("gemini_ok", 0),
          f"gemini_ok ก่อน={before.get('gemini_ok', 0)} หลัง={after.get('gemini_ok', 0)}")
    print(f"    สรุป: โมเดลในเครื่องเขียนคำตอบจบ {answered} จาก {len(DOC_QUESTIONS)} คำถาม")
    return answered


def section_ask_slow(api: Api, model: str) -> None:
    print("\n=== 4. โหมด slow — เพดานกว้างพอให้โมเดลในเครื่องเขียนจบ ===")
    before = usage()
    code, body, spent = api.ask(DOC_QUESTIONS[0])
    got = body.get("answer_model") if isinstance(body, dict) else None
    status = body.get("status") if isinstance(body, dict) else None
    print(f"    · HTTP {code} · {spent:.1f}s · status={status} · answer_model={got}")
    check("ได้คำตอบจากโมเดลในเครื่องจริง", code == 200 and got == f"ollama:{model}",
          f"answer_model={got} status={status}")
    after = usage()
    check("นับว่าโมเดลในเครื่องตอบสำเร็จ",
          after.get("local_primary_ok", 0) > before.get("local_primary_ok", 0),
          f"ก่อน={before.get('local_primary_ok', 0)} หลัง={after.get('local_primary_ok', 0)}")
    check("ไม่มีการเรียก Gemini เลย", after.get("gemini_ok", 0) == before.get("gemini_ok", 0))


# ───────────── 5. เปลี่ยนค่าระหว่างที่คำขอกำลังทำงาน ─────────────

def section_switch_midflight(api: Api, first: str, second: str) -> None:
    print(f"\n=== 5. สลับรุ่นระหว่างที่คำขอกำลังทำงาน ({first} -> {second}) ===")
    api.put_settings(provider="ollama", model=first)
    box: dict = {}

    def run() -> None:
        code, body, spent = api.ask(DOC_QUESTIONS[0])
        box["code"], box["body"], box["spent"] = code, body, spent

    t = threading.Thread(target=run)
    t.start()
    time.sleep(8)
    r = api.put_settings(provider="ollama", model=second)
    switched_at = time.monotonic()
    check("สลับรุ่นได้ระหว่างคำขอกำลังทำงาน", r.status_code == 200, f"HTTP {r.status_code}")
    v = api.get_settings()
    check("ค่าที่ใช้จริงเปลี่ยนทันที", v["effective"]["model"] == second, str(v["effective"]))
    t.join(400)
    got = box.get("body", {}).get("answer_model") if isinstance(box.get("body"), dict) else None
    print(f"    · คำขอที่ค้างอยู่: HTTP {box.get('code')} · {box.get('spent', 0):.1f}s · answer_model={got}")
    check("คำขอที่กำลังทำงานไม่ถูกสลับกลางทาง", got == f"ollama:{first}",
          f"answer_model={got} (ต้องเป็น ollama:{first})")
    # คำขอถัดไปต้องได้รุ่นใหม่ โดยไม่ต้อง restart
    code2, body2, _ = api.ask(DOC_QUESTIONS[1])
    got2 = body2.get("answer_model") if isinstance(body2, dict) else None
    check("คำขอถัดไปได้รุ่นใหม่โดยไม่ restart", got2 == f"ollama:{second}",
          f"answer_model={got2} (ต้องเป็น ollama:{second})")
    api.put_settings(provider="ollama", model=first)


# ───────────── 6. เส้นทางสตรีมของหน้าเว็บ ─────────────

def section_stream(api: Api, model: str) -> None:
    print("\n=== 6. เส้นทางสตรีมที่หน้าเว็บใช้ (/chat-web) ===")
    events, spent = api.ask_stream(DOC_QUESTIONS[2])
    names = [e["event"] for e in events]
    done = next((e for e in events if e["event"] == "done"), None)
    print(f"    · {spent:.1f}s · เหตุการณ์: {names[:3]}…{names[-1:]} · done={json.dumps(done, ensure_ascii=False)[:160] if done else None}")
    check("ได้เหตุการณ์ meta ก่อนเสมอ", names[:1] == ["meta"], str(names[:3]))
    check("มีเหตุการณ์ done ปิดท้าย", bool(done), str(names[-3:]))
    if done:
        check("done รายงานรุ่นที่เขียนจริง", done.get("answer_model") in (f"ollama:{model}", None),
              f"answer_model={done.get('answer_model')}")


# ───────────── 7. Gemini จริง (ต้องมีคีย์) ─────────────

def section_gemini_real(api: Api) -> None:
    """
    เลือก Gemini แล้วคำตอบต้องมาจาก Gemini จริง — รันได้เฉพาะที่ที่มี GEMINI_API_KEY

    ไม่ข้ามเงียบ ๆ เมื่อไม่มีคีย์ แต่ให้ตก เพราะ "ข้าม" กับ "ผ่าน" ต้องไม่ดูเหมือนกัน
    """
    print("\n=== 7. เลือก Gemini — คำตอบต้องมาจาก Gemini จริง ===")
    v = api.get_settings()
    has_key = v["defaults"]["has_gemini_key"]
    check("เซิร์ฟเวอร์นี้มี GEMINI_API_KEY", bool(has_key),
          "ไม่มีคีย์ — ข้อนี้ยืนยันไม่ได้บนเครื่องนี้ ต้องรันบนเซิร์ฟเวอร์ที่ตั้งคีย์ไว้")
    if not has_key:
        return

    model = v["defaults"]["gemini_model"]
    r = api.put_settings(provider="gemini", model=model)
    check("บันทึกตัวเลือก gemini ได้", r.status_code == 200, f"HTTP {r.status_code}")
    v = api.get_settings()
    check("ที่ใช้จริงเป็น gemini", v["effective"]["provider"] == "gemini", str(v["effective"]))
    check("ทำตามค่าที่บันทึก", v["effective"]["honoured"] is True, str(v["effective"]))
    check("embedding ยังเป็น bge-m3", v["embedding"]["model"].startswith("bge-m3"), str(v["embedding"]))

    before = usage()
    code, body, spent = api.ask(DOC_QUESTIONS[0])
    got = body.get("answer_model") if isinstance(body, dict) else None
    status = body.get("status") if isinstance(body, dict) else None
    print(f"    · HTTP {code} · {spent:.1f}s · status={status} · answer_model={got}")
    after = usage()
    check("คำตอบมาจาก gemini", code == 200 and isinstance(got, str) and got.startswith("gemini:"),
          f"answer_model={got} status={status}")
    check("ตัวนับฝั่ง gemini ขยับ", after.get("gemini_ok", 0) > before.get("gemini_ok", 0),
          f"gemini_ok ก่อน={before.get('gemini_ok', 0)} หลัง={after.get('gemini_ok', 0)}")
    check("ไม่ได้ไปเรียกโมเดลในเครื่องเป็นตัวหลัก",
          after.get("local_primary_attempt", 0) == before.get("local_primary_attempt", 0),
          f"ก่อน={before.get('local_primary_attempt', 0)} หลัง={after.get('local_primary_attempt', 0)}")
    check("ไม่ได้ใช้ตัวสำรองเลย",
          after.get("fallback_local_attempt", 0) == before.get("fallback_local_attempt", 0),
          f"ก่อน={before.get('fallback_local_attempt', 0)} หลัง={after.get('fallback_local_attempt', 0)}")


# ───────────── 8. Gemini ล้มแบบจำลอง — ตัวสำรองต้องได้เวลาใช้จริง ─────────────

def section_fallback_on_outage(api: Api) -> None:
    """
    จำลอง Gemini ล้มแบบ "กินเวลาแล้วค่อยล้ม" แล้วตรวจว่าตัวสำรองในเครื่องได้ทำงานจริง

    วิธีจำลอง **ไม่แก้โค้ด** — รันคอนเทนเนอร์ทดสอบด้วย
        --add-host generativelanguage.googleapis.com:198.51.100.1
    ซึ่งเป็นที่อยู่ในช่วงสำหรับเอกสาร (TEST-NET-2) ที่ไม่มีเส้นทางไปถึง คำขอของ Gemini
    จึงค้างที่การเชื่อมต่อจนชน timeout ที่ http_timeout() บีบไว้ตามเวลาที่เหลือ —
    รูปร่างเดียวกับของจริงที่ Gemini กินเพดานเวลาไปจนหมดแล้วค่อยโยนข้อผิดพลาด

    สิ่งที่ตรวจคือ **fallback_local_ok ต้องขยับ** ไม่ใช่แค่ fallback_local_attempt
    ก่อนมี patch ตัวสำรองจะถูก check_budget ปฏิเสธก่อนยิงคำขอแรก ตัวนับจึงขึ้น
    attempt กับ failed เท่า ๆ กันโดยไม่มีไบต์ใดถึง Ollama (ดู LOCAL_FALLBACK_FIX ข้อ 1)
    """
    print("\n=== 8. Gemini ล้มแบบจำลอง — ตัวสำรองในเครื่องต้องได้เวลาใช้จริง ===")
    # ยืนยันเงื่อนไขก่อน ไม่ใช่สมมติว่าจำลองไว้แล้ว
    blocked = False
    try:
        httpx.get("https://generativelanguage.googleapis.com/", timeout=3)
    except Exception:  # noqa: BLE001 — ต่อไม่ได้คือสิ่งที่ต้องการ
        blocked = True
    check("ปลายทางของ Gemini ถูกจำลองให้ติดต่อไม่ได้", blocked,
          "ต่อถึง generativelanguage.googleapis.com ได้ — ยังไม่ได้ตั้ง --add-host ของคอนเทนเนอร์ทดสอบ")
    if not blocked:
        return

    v = api.get_settings()
    r = api.put_settings(provider="gemini", model=v["defaults"]["gemini_model"])
    check("เลือก gemini ไว้สำหรับการจำลอง", r.status_code == 200, f"HTTP {r.status_code}")

    before = usage()
    code, body, spent = api.ask(DOC_QUESTIONS[0])
    reply = body.get("reply") if isinstance(body, dict) else str(body)
    print(f"    · HTTP {code} · {spent:.1f}s · reply[:70]={str(reply)[:70]!r}")
    after = usage()

    def grew(event: str) -> int:
        return after.get(event, 0) - before.get(event, 0)

    check("ไม่มีคำตอบใดมาจาก Gemini", grew("gemini_ok") == 0, f"gemini_ok +{grew('gemini_ok')}")
    check("ตกมาที่ตัวสำรองในเครื่องจริง", grew("fallback_local_attempt") > 0,
          f"fallback_local_attempt +{grew('fallback_local_attempt')}")
    check("ตัวสำรองได้ทำงานจบอย่างน้อยหนึ่งขั้น (ผลของ patch)", grew("fallback_local_ok") > 0,
          f"fallback_local_ok +{grew('fallback_local_ok')} · "
          f"fallback_local_failed +{grew('fallback_local_failed')} — "
          "ถ้า ok เป็น 0 และ failed เท่ากับ attempt คือยังถูกเพดานเวลาปฏิเสธก่อนยิงคำขอแรก")
    print(f"    ตัวนับที่ขยับ: " + ", ".join(
        f"{k} +{grew(k)}" for k in sorted(set(before) | set(after)) if grew(k)))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:8099")
    ap.add_argument("--mode", choices=["prod", "slow", "server", "gemini", "outage"], default="prod")
    ap.add_argument("--model", default="qwen2.5:3b")
    ap.add_argument("--second-model", default="qwen3:8b")
    ap.add_argument("--allow-remote", action="store_true")
    a = ap.parse_args()

    host = urlparse(a.api).hostname or ""
    if host not in ("127.0.0.1", "localhost", "::1") and not a.allow_remote:
        print(f"ปฏิเสธ: --api ชี้ไปที่ {host} ซึ่งไม่ใช่เครื่อง local (ใส่ --allow-remote ถ้าตั้งใจ)")
        return 2

    require_test_db()
    api = Api(a.api, token())
    print(f"ฐาน {DB} · {a.api} · โหมด {a.mode}")
    try:
        # สามโหมดนี้คือข้อที่เครื่อง local ยืนยันไม่ได้ ไม่รันซ้ำส่วนที่ผ่านแล้ว
        #
        # แยก gemini กับ outage เพราะต้องรันในคอนเทนเนอร์ต่างกัน (คอนเทนเนอร์ของ outage
        # ตั้ง --add-host ให้ต่อ Gemini ไม่ได้) ถ้ารวมเป็นโหมดเดียว ข้อของอีกฝั่งจะตก
        # ตามสภาพแวดล้อมเสมอ แล้วคนอ่านผลต้องเดาว่าข้อไหนตกเพราะอะไร
        if a.mode in ("server", "gemini"):
            section_gemini_real(api)
        if a.mode in ("server", "outage"):
            section_fallback_on_outage(api)
        if a.mode in ("server", "gemini", "outage"):
            return finish()
        section_env_default(api)
        section_gemini_without_key(api)
        section_pick_ollama(api, a.model)
        if a.mode == "prod":
            section_ask_prod(api)
        else:
            section_ask_slow(api, a.model)
            section_switch_midflight(api, a.model, a.second_model)
            section_stream(api, a.model)
    finally:
        psql("delete from web.ai_settings where id = 1")

    return finish()


def finish() -> int:
    print(f"\nตรวจ {CHECKS} ข้อ · ตก {len(FAILURES)} ข้อ")
    for f in FAILURES:
        print(f"  - {f}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
