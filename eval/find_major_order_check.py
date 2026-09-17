"""
ตรวจว่าคำตอบแบบสอบถาม "ค้นหาสาขาที่เหมาะกับคุณ" ชุดเดียวกันได้ข้อความค้นหาเดียวกัน ไม่ว่ากดเลือกลำดับไหน

เหตุที่ต้องมี: หน้าเว็บเก็บตัวเลือกที่เลือกได้หลายข้อตามลำดับที่ผู้ใช้กด แล้วหลังบ้านนำลำดับนั้นไปต่อเป็น
ข้อความที่ถูกแปลงเป็นเวกเตอร์ตรงๆ คำตอบชุดเดียวกันที่กดคนละลำดับจึงได้เวกเตอร์ต่างกัน และเปอร์เซ็นต์ของ
ทุกสาขาขยับพร้อมกัน

ตรวจทั้งที่ฟังก์ชัน canonical_labels และที่เส้นทาง /recommend-major จริง (แทนการจัดอันดับด้วยตัวดักคำตอบ
จึงไม่เรียกฐานข้อมูล โมเดล embedding หรือ Gemini)

    python -m eval.find_major_order_check
"""
from __future__ import annotations

import itertools
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
os.environ.setdefault("JWT_SECRET", "local-test-only")
# ต้องมีค่าเพื่อให้โหลดการตั้งค่าได้ ชุดนี้ไม่เชื่อมต่อฐานข้อมูลจริง
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres@127.0.0.1:55432/course_advisor")

from app.api.routes import web_compat as routes  # noqa: E402
from app.services.program_match import build_match_query, build_profile_text  # noqa: E402
from app.services.web_compat import OPTION_LABELS, canonical_labels, labels_of  # noqa: E402


class _Captured(Exception):
    def __init__(self, answers: dict) -> None:
        self.answers = answers


class _Payload:
    """แทน WebRecommendRequest — เส้นทางอ่านแค่ .answers ก่อนเรียกการจัดอันดับ"""

    def __init__(self, answers: dict) -> None:
        self.answers = answers
        self.courses = []


def endpoint_answers(web_answers: dict) -> dict:
    """คำตอบที่ /recommend-major ส่งเข้า match_programs จริง"""
    def capture(db, answers, limit):
        raise _Captured(answers)

    original = routes.match_programs
    routes.match_programs = capture
    try:
        routes.recommend_major_web(_Payload(web_answers), db=None)
    except _Captured as c:
        return c.answers
    finally:
        routes.match_programs = original
    raise AssertionError("recommend_major_web ไม่ได้เรียก match_programs")


def query_of(web_answers: dict) -> str:
    return build_match_query(endpoint_answers(web_answers))


BASE = {
    "track": "sci-math",
    "subjects": ["คณิตศาสตร์", "คอมพิวเตอร์"],
    "interests": ["tech", "health"],
    "skills": ["math", "creative"],
    "goals": ["career-growth", "high-income"],
    "environment": "office",
}


class SubjectOrderChecks(unittest.TestCase):
    """A — ตัวอย่างที่กำหนด"""

    def test_สลับลำดับวิชาได้ข้อความค้นหาเดียวกันทุกตัวอักษร(self):
        a = query_of({**BASE, "subjects": ["คณิตศาสตร์", "คอมพิวเตอร์"]})
        b = query_of({**BASE, "subjects": ["คอมพิวเตอร์", "คณิตศาสตร์"]})
        self.assertEqual(a, b)

    def test_ทุกการเรียงสับเปลี่ยนของวิชาได้ผลเดียวกัน(self):
        subjects = ["ศิลปะ", "คณิตศาสตร์", "คอมพิวเตอร์", "เคมี"]
        queries = {query_of({**BASE, "subjects": list(p)}) for p in itertools.permutations(subjects)}
        self.assertEqual(len(queries), 1)


class MultiSelectOrderChecks(unittest.TestCase):
    """B — interests / skills / goals"""

    def _assert_order_free(self, field: str) -> None:
        codes = list(OPTION_LABELS[field])[:4]
        queries = {query_of({**BASE, field: list(p)}) for p in itertools.permutations(codes)}
        self.assertEqual(len(queries), 1, field)

    def test_interests(self):
        self._assert_order_free("interests")

    def test_skills(self):
        self._assert_order_free("skills")

    def test_goals(self):
        self._assert_order_free("goals")

    def test_ทุกข้อสลับพร้อมกันได้ผลเดียวกัน(self):
        reversed_all = {k: list(reversed(v)) if isinstance(v, list) else v for k, v in BASE.items()}
        self.assertEqual(query_of(BASE), query_of(reversed_all))

    def test_ข้อความประกอบเหตุผลก็คงที่ด้วย(self):
        reversed_all = {k: list(reversed(v)) if isinstance(v, list) else v for k, v in BASE.items()}
        self.assertEqual(
            build_profile_text(endpoint_answers(BASE)),
            build_profile_text(endpoint_answers(reversed_all)),
        )

    def test_เรียงตามลำดับตัวเลือกใน_OPTION_LABELS(self):
        codes = list(OPTION_LABELS["interests"])
        self.assertEqual(
            canonical_labels("interests", list(reversed(codes))),
            list(OPTION_LABELS["interests"].values()),
        )


class DuplicateChecks(unittest.TestCase):
    """C — ตัวซ้ำไม่เปลี่ยนความหมายของข้อความค้นหา"""

    def test_ตัวซ้ำถูกตัด(self):
        self.assertEqual(
            query_of({**BASE, "subjects": ["คณิตศาสตร์", "คอมพิวเตอร์", "คณิตศาสตร์"],
                      "interests": ["tech", "tech", "health"]}),
            query_of(BASE),
        )

    def test_รหัสกับข้อความไทยของตัวเลือกเดียวกันนับเป็นข้อเดียว(self):
        self.assertEqual(canonical_labels("interests", ["tech", "เทคโนโลยีและคอมพิวเตอร์"]),
                         ["เทคโนโลยีและคอมพิวเตอร์"])

    def test_ส่งข้อความไทยมาแทนรหัสได้ผลเดียวกับรหัส(self):
        self.assertEqual(canonical_labels("skills", ["ชอบเขียนโค้ด พัฒนาโปรแกรม", "math"]),
                         canonical_labels("skills", ["math", "creative"]))


class UnknownValueChecks(unittest.TestCase):
    """D — ค่าที่ไม่รู้จักเรียงคงที่ และไม่มีคำตอบหาย"""

    def test_ค่าที่ไม่รู้จักเรียงคงที่ทุกลำดับ(self):
        values = ["zeta-new-option", "tech", "อื่นๆ", "alpha-new-option"]
        results = {tuple(canonical_labels("interests", list(p))) for p in itertools.permutations(values)}
        self.assertEqual(len(results), 1)

    def test_ตัวเลือกที่รู้จักมาก่อน_ค่าที่ไม่รู้จักต่อท้าย(self):
        self.assertEqual(
            canonical_labels("interests", ["zeta-new-option", "health", "alpha-new-option", "tech"]),
            ["เทคโนโลยีและคอมพิวเตอร์", "คณิตศาสตร์และการวิเคราะห์", "alpha-new-option", "zeta-new-option"],
        )

    def test_ไม่มีคำตอบหาย(self):
        values = ["health", "ค่าใหม่", "tech", "another"]
        self.assertEqual(sorted(canonical_labels("interests", values)),
                         sorted(labels_of("interests", values)))

    def test_ข้อที่ไม่มีตารางเรียงตามตัวอักษร(self):
        self.assertEqual(canonical_labels("subjects", ["คอมพิวเตอร์", "คณิตศาสตร์"]),
                         sorted(["คอมพิวเตอร์", "คณิตศาสตร์"]))

    def test_ไม่มีคำตอบได้รายการว่าง(self):
        self.assertEqual(canonical_labels("goals", None), [])
        self.assertEqual(canonical_labels("goals", []), [])


class UnchangedChecks(unittest.TestCase):
    """E — คำตอบที่เรียงตามลำดับมาตรฐานอยู่แล้วได้ข้อความค้นหาเดิมทุกตัวอักษร"""

    EXPECTED = (
        "ชอบวิชา คณิตศาสตร์, คอมพิวเตอร์ "
        "สนใจด้าน เทคโนโลยีและคอมพิวเตอร์, คณิตศาสตร์และการวิเคราะห์ "
        "ถนัด ชอบวิเคราะห์ แยกแยะ และหาสาเหตุของปัญหา, ชอบเขียนโค้ด พัฒนาโปรแกรม "
        "เป้าหมายอาชีพคือ ทำงานในบริษัทขนาดใหญ่, เป็นเจ้าของธุรกิจ"
    )

    def test_ข้อความค้นหาของคำตอบที่เรียงมาตรฐานไม่เปลี่ยน(self):
        self.assertEqual(query_of(BASE), self.EXPECTED)

    def test_ตรงกับการแปลแบบเดิมที่ไม่เรียง(self):
        before_fix = build_match_query({
            "favorite_subjects": labels_of("subjects", BASE["subjects"]),
            "interests": labels_of("interests", BASE["interests"]),
            "aptitudes": labels_of("skills", BASE["skills"]),
            "career_goal": labels_of("goals", BASE["goals"]),
        })
        self.assertEqual(query_of(BASE), before_fix)

    def test_ข้อเลือกเดียวยังแปลเหมือนเดิม(self):
        answers = endpoint_answers(BASE)
        self.assertEqual(answers["study_track"], "วิทย์-คณิต")
        self.assertEqual(answers["work_environment"], ["ทำงานในออฟฟิศ"])
        self.assertIsNone(endpoint_answers({**BASE, "track": None})["study_track"])
        self.assertEqual(endpoint_answers({**BASE, "environment": None})["work_environment"], [])


if __name__ == "__main__":
    unittest.main()
