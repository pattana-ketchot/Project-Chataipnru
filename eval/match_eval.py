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

        top1 = top3 = skipped = 0
        records = []
        gaps: list[tuple[int, bool]] = []
        for case in cases:
            t0 = time.time()
            r = c.post("/match", headers=headers, json={**case["answers"], "limit": 5})
            if r.status_code != 200:
                print(f'ล้ม HTTP {r.status_code}  {case["name"]}')
                continue
            data = r.json()
            ranked = [_short(m["title"]) for m in data["matches"]]

            want = case["expect_top"]
            if not want:
                # โปรไฟล์ที่จงใจไม่ชี้ไปทางไหน ไม่มีคำตอบถูก จึงไม่นับรวมคะแนน
                # แต่รายงานเปอร์เซ็นต์อันดับ 1 ไว้ดู ถ้ายังสูงเท่าโปรไฟล์ที่ชัดเจน
                # แปลว่าตัวเลขไม่ได้สะท้อนความมั่นใจจริง ซึ่งเป็นข้อมูลสำคัญกว่าผ่าน/ไม่ผ่าน
                top = data["matches"][0] if data["matches"] else None
                print(f'ข้าม  {time.time()-t0:4.1f}s  {case["name"]}')
                if top:
                    print(f'   อันดับ 1 ได้ {top["match_percent"]}%  {_short(top["title"])}'
                          f'   <- ควรต่ำกว่าโปรไฟล์ที่ชัดเจน')
                skipped += 1
                records.append({"case": case["name"], "expect": None, "ranked": ranked,
                                "percents": [m["match_percent"] for m in data["matches"]]})
                continue

            hit1 = bool(ranked) and want in ranked[0]
            top1 += hit1
            # ต้องอยู่ใน 3 อันดับแรกด้วย ซึ่งเป็นเกณฑ์ที่ผ่อนกว่าและสะท้อนหน้าเว็บจริง
            # ที่แสดงผลหลายรายการให้ผู้ใช้เลือกเอง
            in3 = any(want in x for x in ranked[:3])
            top3 += in3

            # ช่องว่างระหว่างอันดับ 1 กับ 3 บอกความมั่นใจ ซึ่งเกณฑ์ผ่าน/ไม่ผ่านจับไม่ได้
            # โปรไฟล์ที่ชัดเจนควรทิ้งห่าง ส่วนโปรไฟล์ที่กำกวมควรเกาะกลุ่มกัน
            pcts = [m["match_percent"] for m in data["matches"]]
            gap = pcts[0] - pcts[2] if len(pcts) >= 3 else 0

            print(f'{"ผ่าน " if hit1 else "ต่าง "} {time.time()-t0:4.1f}s  {case["name"]}   ห่าง 1→3 = {gap} จุด')
            print(f'   ควรได้: {want}')
            for i, m in enumerate(data["matches"][:3], 1):
                print(f'   {i}. {m["match_percent"]:3d}%  (คะแนนดิบ {m["score"]:.3f})  {_short(m["title"])}')
            if not hit1:
                print(f'   -> ไม่ตรงอันดับ 1{" แต่ติด 3 อันดับแรก" if in3 else " และไม่ติด 3 อันดับแรก"}')
            for extra in case.get("expect_in_top3", []):
                mark = "ผ่าน" if any(extra in x for x in ranked[:3]) else "ไม่ติด"
                print(f'   ควรติด 3 อันดับแรกด้วย: {extra} -> {mark}')
            records.append({"case": case["name"], "expect": want, "ranked": ranked,
                            "percents": pcts, "gap_1_to_3": gap,
                            "profile_text": data["profile_text"]})
            gaps.append((gap, hit1))

        n = len(cases) - skipped
        print("\n" + "=" * 60)
        print(f"  อันดับ 1 ถูกต้อง : {top1}/{n}")
        print(f"  ติด 3 อันดับแรก  : {top3}/{n}")
        if skipped:
            print(f"  (ไม่นับ {skipped} โปรไฟล์ที่จงใจไม่มีคำตอบถูก)")
        if gaps:
            hit = [g for g, ok in gaps if ok]
            miss = [g for g, ok in gaps if not ok]
            # ถ้าข้อที่ตอบถูกทิ้งห่างมากกว่าข้อที่ตอบผิดอย่างเป็นระบบ แปลว่าเปอร์เซ็นต์
            # ใช้เป็นสัญญาณเตือนได้ว่าผลลัพธ์ไหนควรให้ผู้ใช้พิจารณาหลายตัวเลือก
            if hit:
                print(f"  ห่าง 1→3 เฉลี่ย เมื่อตอบถูก : {sum(hit)/len(hit):.1f} จุด")
            if miss:
                print(f"  ห่าง 1→3 เฉลี่ย เมื่อตอบผิด : {sum(miss)/len(miss):.1f} จุด")

    if args.out:
        Path(args.out).write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  บันทึกผลดิบไว้ที่ {args.out}")


if __name__ == "__main__":
    main()
