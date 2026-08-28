"""
วัดความแม่นของการจับคู่สาขา (/match)

    python -m eval.match_eval --api http://127.0.0.1:9000

วัดสองอย่างต่อโปรไฟล์หนึ่งชุด
  1. สาขาที่ควรได้ อยู่อันดับ 1 หรือไม่
  2. สาขาที่ควรติดกลุ่มต้น อยู่ใน 3 อันดับแรกหรือไม่

ทำไมต้องมีชุดวัดนี้แยกจาก chat_eval
-----------------------------------
การจับคู่สาขาไม่มี "คำตอบในเอกสาร" ให้เทียบเหมือนการถาม-ตอบ จึงตรวจด้วยวิธีเดิมไม่ได้
สิ่งที่ต้องพิสูจน์คือ **ลำดับ** ที่ระบบจัดออกมาสมเหตุสมผลไหม ซึ่งวัดได้ก็ต่อเมื่อกำหนด
คำตอบที่ควรจะเป็นไว้ล่วงหน้า

คำตอบในแต่ละโปรไฟล์เขียนด้วยถ้อยคำอย่างที่นักเรียนเลือกจากหน้าเว็บจริง ไม่ใช่คำที่ยกมา
จากเอกสาร มคอ.2 โดยตั้งใจ เพื่อไม่ให้กลายเป็นการวัดว่า "คัดลอกคำมาตรงกันไหม"
"""
from __future__ import annotations

import argparse
import json
import secrets
import time
from pathlib import Path

import httpx


def _short(title: str) -> str:
    """ตัดชื่อเต็มให้เหลือชื่อสาขาเพื่อให้อ่านผลง่าย"""
    name = title.split("สาขาวิชา")[-1]
    return name.split("(")[0].strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:9000")
    ap.add_argument("--out", help="ไฟล์ JSON สำหรับเก็บผลดิบ")
    args = ap.parse_args()

    spec = json.loads((Path(__file__).parent / "match_cases.json").read_text(encoding="utf-8"))
    cases = spec["cases"]

    with httpx.Client(base_url=args.api, timeout=300) as c:
        email = f"match-eval-{secrets.token_hex(4)}@example.com"
        c.post("/auth/register", json={"email": email, "password": "password123"})
        token = c.post("/auth/login", json={"email": email, "password": "password123"}).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        top1 = top3 = 0
        records = []
        for case in cases:
            t0 = time.time()
            r = c.post("/match", headers=headers, json={**case["answers"], "limit": 5})
            if r.status_code != 200:
                print(f'ล้ม HTTP {r.status_code}  {case["name"]}')
                continue
            data = r.json()
            ranked = [_short(m["title"]) for m in data["matches"]]

            want = case["expect_top"]
            hit1 = bool(ranked) and want in ranked[0]
            top1 += hit1
            # ต้องอยู่ใน 3 อันดับแรกด้วย ซึ่งเป็นเกณฑ์ที่ผ่อนกว่าและสะท้อนหน้าเว็บจริง
            # ที่แสดงผลหลายรายการให้ผู้ใช้เลือกเอง
            in3 = any(want in x for x in ranked[:3])
            top3 += in3

            print(f'{"ผ่าน " if hit1 else "ต่าง "} {time.time()-t0:4.1f}s  {case["name"]}')
            print(f'   ควรได้: {want}')
            for i, m in enumerate(data["matches"][:3], 1):
                print(f'   {i}. {m["match_percent"]:3d}%  (คะแนนดิบ {m["score"]:.3f})  {_short(m["title"])}')
            if not hit1:
                print(f'   -> ไม่ตรงอันดับ 1{" แต่ติด 3 อันดับแรก" if in3 else " และไม่ติด 3 อันดับแรก"}')
            for extra in case.get("expect_in_top3", []):
                mark = "ผ่าน" if any(extra in x for x in ranked[:3]) else "ไม่ติด"
                print(f'   ควรติด 3 อันดับแรกด้วย: {extra} -> {mark}')
            records.append({"case": case["name"], "expect": want, "ranked": ranked,
                            "percents": [m["match_percent"] for m in data["matches"]],
                            "profile_text": data["profile_text"]})

        n = len(cases)
        print("\n" + "=" * 60)
        print(f"  อันดับ 1 ถูกต้อง : {top1}/{n}")
        print(f"  ติด 3 อันดับแรก  : {top3}/{n}")

    if args.out:
        Path(args.out).write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  บันทึกผลดิบไว้ที่ {args.out}")


if __name__ == "__main__":
    main()
