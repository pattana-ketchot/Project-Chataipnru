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


class EvaluationUnavailable(RuntimeError):
    pass


def save_records(path: str | None, records: list[dict]) -> None:
    if path:
        target = Path(path)
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(target)


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


def question_and_expectation(item, group_expect: str) -> tuple[str, str]:
    """
    ข้อความคำถาม และผลที่คาดหวังของ "ข้อนั้น" ซึ่งอาจไม่ตรงกับของกลุ่ม

    เดิมทุกข้อในกลุ่มถูกตัดสินด้วยค่าเดียวกัน ซึ่งใช้ได้จนกระทั่งพฤติกรรมที่ถูกต้อง
    ของบางข้อเปลี่ยนไป — คำถามถึง "สาขาคอมพิวเตอร์ธุรกิจ" เคยควรตอบว่าไม่พบข้อมูล
    เพราะไม่มีเอกสารของสาขานี้ แต่ตอนนี้ระบบรู้รายชื่อสาขาที่คณะเปิดจริง จึงตอบได้ว่า
    คณะไม่มีสาขานี้แล้วแสดงรายการที่มี ซึ่งเป็นคำตอบที่ถูกต้องกว่าและเป็นสิ่งที่ตั้งใจ
    ให้เกิด การบังคับให้ทั้งกลุ่มคาดหวังค่าเดียวจึงกลายเป็นการนับพฤติกรรมที่ถูกว่าตก

    ทางเลือกอื่นคือย้ายข้อนั้นออกไปตั้งกลุ่มใหม่ แต่จะทำให้เทียบคะแนนกับผลรอบก่อน
    ไม่ได้เลย การให้ระบุค่าคาดหวังรายข้อไว้ตรงนั้นอ่านง่ายกว่า และบังคับให้ต้องเขียน
    เหตุผลกำกับไว้ด้วย
    """
    if isinstance(item, str):
        return item, group_expect
    return item["q"], item.get("expect", group_expect)


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
            # 429 มาจากตัวจำกัดของเราเอง ไม่ใช่จากผู้ให้บริการโมเดล
            #
            # /chat จำกัด 30 คำขอต่อนาทีต่อหนึ่งบัญชี และชุดประเมินยิงทั้ง 118 ข้อจาก
            # บัญชีเดียว พอคำตอบมาจากแคชซึ่งเร็วมาก จึงทะลุเพดานของตัวเองภายในไม่กี่
            # สิบวินาที นี่คือสัญญาณว่า "ช้าลงหน่อย" ไม่ใช่ "บริการใช้ไม่ได้"
            #
            # เดิมหยุดทั้งชุดตรงนี้ ทำให้การประเมินจบที่ 30 จาก 118 ข้อแล้วรายงานว่า
            # ประเมินไม่ครบ ซึ่งอ่านแล้วเหมือนระบบมีปัญหา ทั้งที่ระบบตอบได้ปกติทุกข้อ
            # และเสียคำตอบที่คำนวณมาแล้วไปเปล่าๆ
            if r.status_code == 429:
                if attempt < attempts:
                    print("      (ชนเพดานคำขอของชุดประเมินเอง รอ 60 วินาทีแล้วถามต่อ)")
                    time.sleep(60)
                    continue
                raise EvaluationUnavailable("HTTP 429 ซ้ำหลายครั้ง")
            # 503 คือฝั่งโมเดลตอบไม่ได้จริง รอแล้วยิงต่อก็ได้ผลเหมือนเดิม และคะแนน
            # ที่วัดต่อจากนั้นจะไม่ใช่คะแนนของระบบที่ทำงานปกติ
            if r.status_code == 503:
                raise EvaluationUnavailable("HTTP 503")
            if r.status_code == 200:
                data = r.json()
                if any(marker in data.get("reply", "") for marker in (
                    "ระบบหลักตอบไม่ได้ชั่วคราว", "ยังเขียนคำอธิบายประกอบให้ไม่ได้",
                    "ระบบตอบไม่ได้ในขณะนี้",
                )):
                    raise EvaluationUnavailable("degraded reply")
                return data
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
            group_expect = group["expect"]
            hits = 0
            print(f'\n=== กลุ่ม {group["id"]}: {group["name"]} (คาดหวัง: {group_expect}) ===')
            for item in group["questions"]:
                q, expect = question_and_expectation(item, group_expect)
                t0 = time.time()
                # ทุกคำถามเริ่ม session ใหม่ เพื่อไม่ให้ประวัติของข้อก่อนหน้ารบกวนผล
                try:
                    d = _ask_with_retry(c, headers, q)
                except EvaluationUnavailable as exc:
                    save_records(args.out, records)
                    print(f"หยุด: {exc}; ประเมินไม่ครบ ({len(records)}/{total_questions}) — ไม่ใช่คะแนนชุดเต็ม")
                    raise SystemExit(2) from exc
                if d is None:
                    records.append({"group": group["id"], "question": q, "expect": expect,
                                    "got": "error", "score": 0.0, "seconds": 0, "reply": ""})
                    save_records(args.out, records)
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
                save_records(args.out, records)
                # บอกให้เห็นตอนอ่านผลว่าข้อนี้ใช้เกณฑ์ต่างจากกลุ่ม จะได้ไม่งงว่าทำไม
                # ข้อที่ตอบได้ถึงนับว่าผ่านในกลุ่มที่คาดหวังว่าไม่พบข้อมูล
                note = "" if expect == group_expect else f" (เกณฑ์เฉพาะข้อ: {expect})"
                print(f'  {"ผ่าน" if ok else "ไม่ผ่าน"}  [{got:<13}] {d["top_score"]:.3f} {time.time()-t0:4.0f}s  {q}{note}')
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
        save_records(args.out, records)
        print(f"  บันทึกผลดิบไว้ที่ {args.out}")


if __name__ == "__main__":
    main()
