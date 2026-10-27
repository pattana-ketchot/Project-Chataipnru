"""
/compare-courses ต้องเลือกเอกสารตามระดับปริญญา — ตรวจพบและแก้เมื่อ 2569-10-27

    docker exec -w /app/backend -e PYTHONPATH=/app/backend <c> python tests/test_compare_degree_level.py

ปัญหาที่เจอ
-----------
คณะมีสาขาที่ชื่อและปีเดียวกันแต่คนละระดับปริญญา (การจัดการเทคโนโลยีการเกษตรและ
บริหารทรัพยากรชุมชน พ.ศ. 2568 มีทั้งปริญญาโทและปริญญาเอก)

`normalise_title()` ตัดชื่อปริญญาออกเพื่อให้เทียบชื่อข้ามสองฐานข้อมูลได้ ผลคือ
เล่มโทกับเล่มเอกได้คีย์เดียวกัน `match_by_title()` จึงคืน **เล่มเดียวกัน** ให้ทั้งสอง
รายการ การเปรียบเทียบ "โท vs เอก" จึงเป็นการเอาเล่มโทมาเทียบกับตัวเอง
โดยไม่มีอะไรบอกผู้ใช้

เรื่องนี้ไม่โผล่มาก่อน เพราะหลักสูตรบัณฑิตศึกษาเพิ่งถูกเพิ่มเข้าหน้าเว็บ
ก่อนหน้านี้ผู้ใช้เลือกเปรียบเทียบได้เฉพาะปริญญาตรีซึ่งมีระดับเดียว

สิ่งที่ทดสอบ
------------
1. ส่ง level มา -> ได้เล่มของระดับนั้น และสองรายการต้องเป็นคนละเล่ม
2. ชื่อขึ้นต้นด้วย "(ปริญญาโท)" โดยไม่ส่ง level -> อ่านระดับจากชื่อได้
3. ไม่บอกระดับเลยทั้งที่สาขานั้นมีหลายระดับ -> **จับคู่ไม่ได้** ไม่ใช่เดาเล่มให้
4. สาขาที่มีระดับเดียว (ปริญญาตรี) -> ทำงานเหมือนเดิม ไม่ถูกกระทบ
5. ระบุปีฉบับพร้อมระดับ -> ได้เล่มที่ตรงทั้งปีและระดับ
"""
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.db.session import SessionLocal
from app.services.course_scope import degree_level_of, degree_of_title
from app.services.web_compat import match_by_title

AGRI = "การจัดการเทคโนโลยีการเกษตรและบริหารทรัพยากรชุมชน"

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


def level_of(course) -> str | None:
    return degree_level_of(degree_of_title(course.title))


def run(db, sent):
    matched, unmatched = match_by_title(db, sent)
    picked = {item["id"]: course for item, course in matched}
    missed = {item["id"] for item in unmatched}
    return picked, missed


def main() -> int:
    with SessionLocal() as db:
        # หลักสูตรที่ทดสอบต้องมีอยู่จริงในคลัง ไม่งั้นผลที่ "ผ่าน" ไม่ได้แปลว่าอะไร
        probe, _ = run(db, [{"id": "m", "title": AGRI, "level": "ปริญญาโท"},
                            {"id": "d", "title": AGRI, "level": "ปริญญาเอก"}])
        if len(probe) != 2:
            print("** ข้ามการทดสอบ: คลังนี้ไม่มีหลักสูตรโทและเอกของ %s **" % AGRI)
            return 0

        print("1. ส่ง level มาพร้อมชื่อที่เหมือนกันทุกตัวอักษร")
        picked, missed = run(db, [{"id": "m", "title": AGRI, "level": "ปริญญาโท"},
                                  {"id": "d", "title": AGRI, "level": "ปริญญาเอก"}])
        check("จับคู่ได้ทั้งสองรายการ", len(picked) == 2 and not missed, str(sorted(missed)))
        check("เป็นเอกสารคนละเล่ม", len({c.id for c in picked.values()}) == 2)
        check("รายการโทได้เล่มระดับ master", level_of(picked["m"]) == "master",
              picked["m"].title)
        check("รายการเอกได้เล่มระดับ doctoral", level_of(picked["d"]) == "doctoral",
              picked["d"].title)

        print()
        print("2. ไม่ส่ง level แต่ชื่อมีวงเล็บระดับอยู่")
        picked, missed = run(db, [{"id": "m", "title": "(ปริญญาโท) " + AGRI},
                                  {"id": "d", "title": "(ปริญญาเอก) " + AGRI}])
        check("จับคู่ได้ทั้งสองรายการ", len(picked) == 2 and not missed, str(sorted(missed)))
        check("เป็นเอกสารคนละเล่ม", len({c.id for c in picked.values()}) == 2)
        check("อ่านระดับจากชื่อได้ถูก",
              level_of(picked.get("m")) == "master" and level_of(picked.get("d")) == "doctoral")

        print()
        print("3. ไม่บอกระดับเลย ทั้งที่สาขานั้นมีหลายระดับ")
        picked, missed = run(db, [{"id": "m", "title": AGRI}, {"id": "d", "title": AGRI}])
        # ต้องไม่เดาเล่มให้ — ผู้เรียกจะได้เห็น unmatched แล้วไปบอกผู้ใช้ให้ระบุระดับ
        check("ถือว่าจับคู่ไม่ได้ ไม่ใช่หยิบเล่มใดเล่มหนึ่งมาให้",
              not picked and missed == {"m", "d"},
              "ได้ %d เล่ม" % len(picked))

        print()
        print("4. สาขาที่มีระดับเดียว ต้องไม่ถูกกระทบ")
        for name in ("วิทยาการคอมพิวเตอร์", "คณิตศาสตร์", "การแพทย์แผนไทยประยุกต์"):
            picked, missed = run(db, [{"id": "x", "title": name}])
            check("จับคู่ %s ได้โดยไม่ต้องบอกระดับ" % name,
                  len(picked) == 1 and not missed,
                  picked["x"].title if picked else "ไม่เจอ")

        print()
        print("5. ระบุปีฉบับพร้อมระดับ")
        picked, missed = run(db, [
            {"id": "m", "title": AGRI + " (พ.ศ. 2568)", "level": "ปริญญาโท"},
            {"id": "d", "title": AGRI + " (พ.ศ. 2568)", "level": "ปริญญาเอก"}])
        check("ได้เล่มที่ตรงทั้งปีและระดับ",
              len({c.id for c in picked.values()}) == 2
              and level_of(picked.get("m")) == "master"
              and level_of(picked.get("d")) == "doctoral",
              str(sorted(missed)))
        check("ปีที่ได้คือ 2568",
              all("2568" in c.title for c in picked.values()))

    print()
    print("=" * 70)
    if FAILURES:
        print("ตก %d จาก %d ข้อ" % (len(FAILURES), CHECKS))
        for f in FAILURES:
            print("   - %s" % f)
        return 1
    print("ผ่านทั้ง %d ข้อ" % CHECKS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
