"""
ประเมินคุณภาพ /chat ด้วยชุดคำถามใน eval/questions.json

    python -m eval.chat_eval --api http://127.0.0.1:8000

วัด 3 อย่างตามกลุ่มคำถาม:
  A. ตอบได้จากเอกสาร   -> ต้องตอบ (in_scope และไม่ใช่ข้อความมาตรฐาน)
  B. ไม่มีในเอกสาร      -> ต้องบอกว่าไม่พบข้อมูล "แล้วหยุด" ห้ามเดาต่อ
  C. นอกขอบเขต         -> ต้องถูกปฏิเสธ

การตรวจจับ hallucination ในกลุ่ม B ใช้รูปแบบที่พบจริงจากการทดสอบ: โมเดลจะเขียนว่า
"ไม่มีการกล่าวถึง..." แล้วต่อด้วยคำตอบยาวๆ จากความรู้ทั่วไป จึงนับว่าเข้าข่าย
เมื่อคำตอบ "ทั้งปฏิเสธและยาวเกินปกติ" หรือมีวลีเดาแบบ "โดยทั่วไป/มักจะ"

หมายเหตุ: ตัวชี้วัดนี้เป็น heuristic ไม่ใช่การตัดสินโดยมนุษย์ ใช้เพื่อเทียบก่อน-หลัง
การแก้ระบบเป็นหลัก ควรสุ่มอ่านคำตอบจริงประกอบเสมอ
"""
from __future__ import annotations

import argparse
import json
import secrets
import time
from pathlib import Path

import httpx

_DENY_MARKERS = ("ไม่พบข้อมูล", "ไม่มีข้อมูล", "ไม่ได้ระบุ", "ไม่มีการกล่าวถึง", "ไม่ได้กล่าวถึง", "ยังตอบให้ไม่ได้")
_GUESS_MARKERS = ("โดยทั่วไป", "โดยปกติ", "มักจะ", "ทั่วๆ ไป", "สามารถสรุปความแตกต่าง")
_LONG_REPLY = 250  # ตัวอักษร


def classify(reply: str, status: str) -> str:
    """จัดประเภทคำตอบเป็น answered / not_found / refuse / small_talk / hallucinated"""
    if status == "small_talk":
        return "small_talk"
    if status == "out_of_scope":
        return "refuse"
    if status == "not_found":
        return "not_found"
    # status == "answered": ตรวจว่าเป็นคำตอบที่อิงเอกสารจริง หรือปฏิเสธแล้วเดาต่อ
    denied = any(m in reply for m in _DENY_MARKERS)
    guessed = any(m in reply for m in _GUESS_MARKERS)
    if denied and (len(reply) > _LONG_REPLY or guessed):
        return "hallucinated"  # ปฏิเสธแล้วเดาต่อ — พฤติกรรมที่ต้องกำจัด
    if denied:
        return "not_found"
    if guessed:
        return "hallucinated"
    return "answered"


def _ask_with_retry(client: httpx.Client, headers: dict, question: str, attempts: int = 3):
    """
    ถาม /chat พร้อมลองใหม่เมื่อฝั่งโมเดลล้มชั่วคราว

    จำเป็นเพราะการยิงคำถามติดกันหลายสิบข้อกดดัน VRAM จนตัวรันโมเดลของ Ollama
    ถูกฆ่ากลางคัน (ตอบ 500 "model runner has unexpectedly stopped") บนการ์ด 8GB
    ที่ต้องแบ่งหน่วยความจำให้จอภาพด้วย ผู้ใช้จริงถามทีละคำถามจึงไม่เจออาการนี้
    แต่ชุดประเมินยิงรัวจึงเจอ — หยุดพักแล้วลองใหม่ให้โมเดลโหลดกลับเข้า VRAM ได้
    """
    for attempt in range(1, attempts + 1):
        try:
            r = client.post("/chat", headers=headers, json={"message": question})
            if r.status_code == 200:
                return r.json()
        except httpx.HTTPError:
            pass
        if attempt < attempts:
            time.sleep(30)
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:9000")
    ap.add_argument("--out", help="ไฟล์ JSON สำหรับเก็บผลดิบไว้เทียบภายหลัง")
    # ชุดเต็ม 109 คำถามใช้เวลาราว 25-30 นาที และกดดัน VRAM จนตัวรันโมเดลอาจถูกฆ่า
    # จึงเลือกรันเฉพาะกลุ่มที่สนใจได้ เช่น --groups A8,A9 ตอนแก้เรื่องการค้นหา
    ap.add_argument("--groups", help="รันเฉพาะกลุ่มที่ระบุ คั่นด้วยจุลภาค เช่น A8,A9,B")
    args = ap.parse_args()

    spec = json.loads((Path(__file__).parent / "questions.json").read_text(encoding="utf-8"))

    if args.groups:
        wanted = {g.strip().upper() for g in args.groups.split(",")}
        spec["groups"] = [g for g in spec["groups"] if g["id"].upper() in wanted]
        if not spec["groups"]:
            raise SystemExit(f"ไม่พบกลุ่มที่ระบุ: {args.groups}")

    total_questions = sum(len(g["questions"]) for g in spec["groups"])
    print(f"จะทดสอบ {total_questions} คำถาม จาก {len(spec['groups'])} กลุ่ม")

    with httpx.Client(base_url=args.api, timeout=600) as c:
        email = f"eval-{secrets.token_hex(4)}@example.com"
        c.post("/auth/register", json={"email": email, "password": "password123"})
        token = c.post("/auth/login", json={"email": email, "password": "password123"}).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        records, totals = [], {}
        for group in spec["groups"]:
            expect = group["expect"]
            hits = 0
            print(f'\n=== กลุ่ม {group["id"]}: {group["name"]} (คาดหวัง: {expect}) ===')
            for q in group["questions"]:
                t0 = time.time()
                # ทุกคำถามเริ่ม session ใหม่ เพื่อไม่ให้ประวัติของข้อก่อนหน้ารบกวนผล
                d = _ask_with_retry(c, headers, q)
                if d is None:
                    records.append({"group": group["id"], "question": q, "expect": expect,
                                    "got": "error", "score": 0.0, "seconds": 0, "reply": ""})
                    # ไม่ต้องนับอะไรเพิ่ม จำนวนข้อทั้งหมดนับจาก len(group["questions"]) อยู่แล้ว
                    # เดิมมีบรรทัด total += 1 ซึ่งอ้างถึงตัวแปรที่ไม่เคยประกาศ ทำให้ทั้งการรัน
                    # ล้มตอนที่เรียกโมเดลไม่สำเร็จ — คือพังตอนที่ต้องการผลลัพธ์มากที่สุดพอดี
                    print(f'  ข้ามไป [error        ] เรียกโมเดลไม่สำเร็จ  {q}')
                    continue
                got = classify(d["reply"], d["status"])
                ok = got == expect
                hits += ok
                records.append({"group": group["id"], "question": q, "expect": expect, "got": got,
                                "score": d["top_score"], "seconds": round(time.time() - t0, 1),
                                "reply": d["reply"]})
                print(f'  {"ผ่าน" if ok else "ไม่ผ่าน"}  [{got:<13}] {d["top_score"]:.3f} {time.time()-t0:4.0f}s  {q}')
                if not ok:
                    print(f'          -> {d["reply"][:170]}')
            totals[group["id"]] = (hits, len(group["questions"]))

        print("\n" + "=" * 60)
        total_ok = sum(h for h, _ in totals.values())
        total_n = sum(n for _, n in totals.values())
        for gid, (h, n) in totals.items():
            print(f"  กลุ่ม {gid}: {h}/{n}")
        print(f"  รวม: {total_ok}/{total_n}")
        halluc = sum(1 for r in records if r["got"] == "hallucinated")
        print(f"  คำตอบที่เข้าข่ายแต่งข้อมูล: {halluc}")

    if args.out:
        Path(args.out).write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  บันทึกผลดิบไว้ที่ {args.out}")


if __name__ == "__main__":
    main()
