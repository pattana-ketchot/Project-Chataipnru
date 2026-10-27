"""
ทดสอบสองเรื่องที่แก้ในรอบนี้ โดยไม่ต้องต่อฐานข้อมูลและไม่ต้องเรียกโมเดล

    cd backend && python tests/test_credit_phrase_and_sources.py

1. คำตอบหน่วยกิตต้องรักษาคำว่า "ไม่น้อยกว่า" ตามที่เอกสารเขียน
2. /chat ต้องส่งที่มาของเอกสารออกมาด้วย (source / sources) สำหรับคำตอบจากฐานข้อมูล
   ซึ่งไม่มี citations เพราะไม่ได้มาจากการค้นเอกสาร

ไม่ใช้ pytest เพราะรีโปนี้ยังไม่มีชุดทดสอบและ pytest ไม่ได้ติดตั้งในเครื่องพัฒนา
— สคริปต์นี้รันเองได้ คืน exit code 1 เมื่อมีข้อตก
"""
import os
import sys
import traceback
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# ค่าที่ Settings บังคับให้มี — ใส่ค่าหลอกเพราะการทดสอบนี้ไม่ต่อฐานข้อมูลและไม่ออก token
# create_engine ไม่เชื่อมต่อตอน import จึงใช้ URL ที่ไม่มีจริงได้
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://u:p@127.0.0.1:1/none")
os.environ.setdefault("JWT_SECRET", "x" * 32)

from app.schemas.chat import ChatReply  # noqa: E402
from app.services.curriculum_facts import (ANSWERED, EditionFact, FactsResult, Source,  # noqa: E402
                                           _compose, _credit_phrase, _says_at_least)
from app.services.structured_shadow import _source_of, _sources_of  # noqa: E402

CHECKS = 0
FAILURES: list[str] = []


def check(label: str, got, want) -> None:
    global CHECKS
    CHECKS += 1
    if got != want:
        FAILURES.append(f"{label}\n     ได้  : {got!r}\n     ต้องได้: {want!r}")


def fact(value: int, quote: str | None, title: str = "หลักสูตร ก (พ.ศ. 2561)",
         file: str = "a.pdf", page: int = 6, course_id: str = "11111111-1111-1111-1111-111111111111"):
    return EditionFact(
        course_id=course_id, course_title=title, edition_year=2561, value_int=value,
        source=Source(file, page, page, quote, document_id="dddddddd-0000-0000-0000-000000000000"),
    )


# ───────────── 1. คำว่า "ไม่น้อยกว่า" ─────────────

def test_keeps_at_least_when_the_document_says_so():
    f = fact(130, "จำนวนหน่วยกิตรวมตลอดหลักสูตรไม่น้อยกว่า 130 หน่วยกิต")
    check("เอกสารเขียนไม่น้อยกว่า", _credit_phrase([f]), "ไม่น้อยกว่า 130 หน่วยกิต")
    check("_says_at_least ตรงกับค่า", _says_at_least(f), True)


def test_tolerates_a_space_before_the_phrase():
    # ของจริงใน en65.pdf, it66.pdf และอีกหลายฉบับมีช่องว่างคั่น
    f = fact(135, "จำนวนหน่วยกิตรวมตลอดหลักสูตร ไม่น้อยกว่า 135 หน่วยกิต")
    check("มีช่องว่างคั่น", _credit_phrase([f]), "ไม่น้อยกว่า 135 หน่วยกิต")


def test_tolerates_a_line_break_between_phrase_and_number():
    # ของจริงใน agri68_master.pdf: 'ไม่น้อยกว่า \n36 \nหน่วยกิต'
    f = fact(36, "จำนวนหน่วยกิตตลอดหลักสูตรไม่น้อยกว่า \n36 \nหน่วยกิต")
    check("ตัดบรรทัดกลางวลี", _credit_phrase([f]), "ไม่น้อยกว่า 36 หน่วยกิต")


def test_plain_number_when_the_document_does_not_say_at_least():
    f = fact(130, "จำนวนหน่วยกิตรวมตลอดหลักสูตร 130 หน่วยกิต")
    check("เอกสารไม่ได้เขียนคำนี้", _credit_phrase([f]), "130 หน่วยกิต")
    check("_says_at_least เป็นเท็จ", _says_at_least(f), False)


def test_does_not_borrow_the_phrase_from_another_number():
    # ข้อความที่ยกมาพูดถึงขั้นต่ำของหมวดวิชา ไม่ใช่หน่วยกิตรวม — ห้ามเติมคำให้เลขรวม
    f = fact(130, "หมวดวิชาเฉพาะ ไม่น้อยกว่า 84 หน่วยกิต")
    check("เลขในข้อความไม่ตรงกับค่าที่เก็บ", _credit_phrase([f]), "130 หน่วยกิต")
    check("_says_at_least ต้องเป็นเท็จ", _says_at_least(f), False)


def test_missing_quote_falls_back_to_plain_number():
    check("ไม่มีข้อความที่ยกมา", _credit_phrase([fact(124, None)]), "124 หน่วยกิต")
    bare = EditionFact(course_id="c", course_title="t", edition_year=None, value_int=124, source=None)
    check("ไม่มีที่มาเลย", _credit_phrase([bare]), "124 หน่วยกิต")


def test_merged_editions_need_every_quote_to_agree():
    with_phrase = fact(130, "จำนวนหน่วยกิตรวมตลอดหลักสูตรไม่น้อยกว่า 130 หน่วยกิต", title="ก (2561)")
    without = fact(130, "จำนวนหน่วยกิตรวมตลอดหลักสูตร 130 หน่วยกิต", title="ก (2566)")
    check("ทุกฉบับเขียนตรงกัน", _credit_phrase([with_phrase, with_phrase]), "ไม่น้อยกว่า 130 หน่วยกิต")
    check("มีฉบับที่ไม่ได้เขียน", _credit_phrase([with_phrase, without]), "130 หน่วยกิต")


# ───────────── 2. ข้อความคำตอบทั้งก้อน ─────────────

def test_single_edition_answer_text():
    f = fact(130, "จำนวนหน่วยกิตรวมตลอดหลักสูตรไม่น้อยกว่า 130 หน่วยกิต",
             title="หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาการคอมพิวเตอร์ (พ.ศ. 2561)",
             file="cs61.pdf", page=6)
    answer, others = _compose("total_credits", "วิทยาการคอมพิวเตอร์", [f], [])
    # เว้นวรรคก่อน "ไม่น้อยกว่า" — เอกสารต้นทางเขียนทั้งสองแบบ (cs61.pdf เขียน
    # "รวมตลอดหลักสูตร ไม่น้อยกว่า" มีช่องว่าง ส่วน ma69.pdf เขียนติดกัน) จึงไม่ต้อง
    # ไล่ให้ตรงตัวอักษรกับฉบับใดฉบับหนึ่ง ความหมายและคำครบคือสิ่งที่ต้องรักษา
    check(
        "คำตอบฉบับเดียว",
        answer,
        "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาการคอมพิวเตอร์ (พ.ศ. 2561) "
        "มีจำนวนหน่วยกิตรวมตลอดหลักสูตร ไม่น้อยกว่า 130 หน่วยกิต\nที่มา: cs61.pdf หน้า 6",
    )
    check("ไม่มีฉบับอื่น", others, [])


def test_two_editions_with_different_values():
    ma69 = fact(124, "จำนวนหน่วยกิตรวมตลอดหลักสูตรไม่น้อยกว่า 124 หน่วยกิต",
                title="หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาคณิตศาสตร์ (พ.ศ. 2569)",
                file="ma69.pdf", page=1, course_id="22222222-2222-2222-2222-222222222222")
    ma64 = fact(130, "จ ำนวนหน่วยกิตที่เรียนตลอดหลักสูตร \n \nจำนวนหน่วยกิตรวมตลอดหลักสูตรไม่น้อยกว่า 130 หน่วยกิต",
                title="หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาคณิตศาสตร์ (พ.ศ. 2564)",
                file="ma64.pdf", page=6, course_id="33333333-3333-3333-3333-333333333333")
    answer, _ = _compose("total_credits", "คณิตศาสตร์", [ma69, ma64], [])
    check(
        "คำตอบสองฉบับ",
        answer,
        "จำนวนหน่วยกิตรวมตลอดหลักสูตรของคณิตศาสตร์ แยกตามหลักสูตร\n"
        "- หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาคณิตศาสตร์ (พ.ศ. 2569): ไม่น้อยกว่า 124 หน่วยกิต\n"
        "- หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาคณิตศาสตร์ (พ.ศ. 2564): ไม่น้อยกว่า 130 หน่วยกิต\n"
        "ที่มา: ma69.pdf หน้า 1; ma64.pdf หน้า 6",
    )


def test_other_fields_are_untouched():
    # แก้เฉพาะ total_credits — ปีของหลักสูตรต้องได้ข้อความเดิมทุกตัวอักษร
    f = fact(2561, "หลักสูตรปรับปรุง พ.ศ. 2561", title="หลักสูตร ก")
    answer, _ = _compose("edition_year", "ก", [f], [])
    check("edition_year ไม่เปลี่ยน", answer, "หลักสูตร ก เป็นหลักสูตรฉบับ พ.ศ. 2561\nที่มา: a.pdf หน้า 6")


def test_missing_editions_line_is_kept():
    f = fact(130, "จำนวนหน่วยกิตรวมตลอดหลักสูตรไม่น้อยกว่า 130 หน่วยกิต")
    answer, _ = _compose("total_credits", "ก", [f], ["หลักสูตร ก (พ.ศ. 2552)"])
    check("บอกฉบับที่ยังไม่มีข้อมูล", "ยังไม่มีข้อมูลที่ผ่านการตรวจของ หลักสูตร ก (พ.ศ. 2552)" in answer, True)


# ───────────── 3. ที่มาของเอกสาร ─────────────

def test_sources_lists_every_edition():
    ma69 = fact(124, "ไม่น้อยกว่า 124 หน่วยกิต", title="คณิตศาสตร์ (พ.ศ. 2569)",
                file="ma69.pdf", page=1, course_id="22222222-2222-2222-2222-222222222222")
    ma64 = fact(130, "ไม่น้อยกว่า 130 หน่วยกิต", title="คณิตศาสตร์ (พ.ศ. 2564)",
                file="ma64.pdf", page=6, course_id="33333333-3333-3333-3333-333333333333")
    result = FactsResult(ANSWERED, "total_credits", facts=[ma69, ma64])

    check("คำตอบสองฉบับยังไม่มีปุ่มเปิดเอกสาร (เหมือนเดิม)", _source_of(result), (None, None))

    got = _sources_of(result)
    check("มีที่มาครบสองฉบับ", len(got), 2)
    check("ฉบับแรก", (got[0]["file"], got[0]["page_start"], got[0]["course_title"]),
          ("ma69.pdf", 1, "คณิตศาสตร์ (พ.ศ. 2569)"))
    check("ฉบับที่สอง", (got[1]["file"], got[1]["page_start"], got[1]["course_title"]),
          ("ma64.pdf", 6, "คณิตศาสตร์ (พ.ศ. 2564)"))
    check("มี course_id ให้แยกฉบับที่หน่วยกิตเท่ากัน",
          got[0]["course_id"], "22222222-2222-2222-2222-222222222222")


def test_single_edition_keeps_the_document_button():
    f = fact(130, "ไม่น้อยกว่า 130 หน่วยกิต", file="cs61.pdf", page=6)
    result = FactsResult(ANSWERED, "total_credits", facts=[f])
    check("ฉบับเดียวยังได้ปุ่มเปิดเอกสาร", _source_of(result),
          ("dddddddd-0000-0000-0000-000000000000", 6))
    check("และอยู่ใน sources ด้วย", [s["file"] for s in _sources_of(result)], ["cs61.pdf"])


def test_facts_without_a_source_are_skipped():
    bare = EditionFact(course_id="c", course_title="t", edition_year=None, value_int=1, source=None)
    result = FactsResult(ANSWERED, "total_credits", facts=[bare])
    check("ไม่มีที่มา = ไม่ใส่ในรายการ", _sources_of(result), ())


# ───────────── 4. รูปแบบ response ของ /chat ─────────────

def test_chat_reply_carries_the_source_fields():
    reply = ChatReply(
        session_id="44444444-4444-4444-4444-444444444444",
        reply="ไม่น้อยกว่า 130 หน่วยกิต", search_query="q", top_score=0.7,
        status="answered", in_scope=True, citations=[],
        source={"document_id": "d", "page_start": 6},
        sources=[{"file": "cs61.pdf", "page_start": 6}],
    )
    body = reply.model_dump(mode="json")
    check("มีคีย์ source", body["source"], {"document_id": "d", "page_start": 6})
    check("มีคีย์ sources", body["sources"], [{"file": "cs61.pdf", "page_start": 6}])


def test_chat_reply_defaults_keep_old_callers_working():
    reply = ChatReply(
        session_id="44444444-4444-4444-4444-444444444444",
        reply="x", search_query="q", top_score=0.0,
        status="answered", in_scope=True, citations=[],
    )
    body = reply.model_dump(mode="json")
    check("source ตั้งต้นเป็น None", body["source"], None)
    check("sources ตั้งต้นเป็นรายการว่าง", body["sources"], [])


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    errors = 0
    for t in tests:
        try:
            t()
        except Exception:  # noqa: BLE001
            errors += 1
            FAILURES.append(f"{t.__name__} โยน exception\n{traceback.format_exc()}")

    print(f"ชุดทดสอบ {len(tests)} ชุด · จุดตรวจ {CHECKS} จุด")
    if FAILURES:
        print(f"ตก {len(FAILURES)} จุด")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("ผ่านทั้งหมด")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
