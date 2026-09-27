"""
ตรวจคำถามค่าเทอม: ถามตรง ถามต่อในบทสนทนา ชื่อย่อทุกแบบ และตัวเลขมาจากตารางประกาศค่าเทอม

เหตุที่ต้องมี: ผู้ใช้ถาม "ค่าเทอมเท่าไหร่" ต่อด้วย "ของ comsci" แล้วได้ภาพรวมหลักสูตรแทนค่าเทอม
และ "ค่าเทอมของวิทย์คอม" ได้ช่วงค่าเทอมรวมทุกสาขา เพราะตารางคำย่อมีแค่ "วิทคอม"

ข้อที่ต้องเรียกโมเดลและฐานข้อมูล (การส่งคำถามต่อเนื่องไปตารางค่าเทอม คำถามตีความแล้วตรงกันทุกขั้น)
ตรวจด้วยการถามระบบจริง ไฟล์นี้ตรวจส่วนที่ตัดสินด้วยโค้ดล้วน

    python -m eval.tuition_followup_check
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import app.services.chat as chat  # noqa: E402
from app.services import tuition  # noqa: E402
from app.services.query_expansion import ALIASES  # noqa: E402

PROGRAMS = tuition._data()["programs"]


def programmes_in(text: str) -> set[str]:
    """ชื่อในตารางค่าเทอมที่ข้อความนี้เอ่ยถึง ทั้งชื่อในประกาศและชื่อใหม่ของสาขาเดียวกัน"""
    target = tuition._normalise(text)
    return {p["name"] for p in PROGRAMS if any(tuition._normalise(n) in target for n in [p["name"], *p.get("aliases", [])])}


class DirectQuestionChecks(unittest.TestCase):
    def test_ชื่อในตารางและชื่อใหม่ทุกชื่อหาสาขาเจอ(self):
        for p in PROGRAMS:
            for name in [p["name"], *p.get("aliases", [])]:
                for q in (f"ค่าเทอม{name}เท่าไหร่", f"สาขา{name} ค่าเทอมเทอมละเท่าไหร่"):
                    found = tuition.find_program(q)
                    self.assertIsNotNone(found, q)
                    self.assertEqual(found["name"], p["name"], q)

    def test_คำย่อทุกตัวหาสาขาเจอ_หรือขอให้ระบุเมื่อไม่มีในตารางค่าเทอม(self):
        """ตารางคำย่อครอบสาขาที่มีเอกสารหลักสูตร ซึ่งกว้างกว่าประกาศค่าเทอม

        เดิมข้อนี้บังคับว่าคำย่อทุกตัวต้องมีแถวค่าเทอม แต่มีสาขาที่มีเอกสารหลักสูตร
        จริงและประกาศค่าเทอมไม่ครอบ (การประกอบอาหารและการบริการอาหาร
        สาธารณสุขศาสตร์ การจัดการเทคโนโลยีการเกษตรและบริหารทรัพยากรชุมชน)
        สิ่งที่ต้องรับประกันคือกรณีนั้นต้องหาไม่เจอแล้วขอให้ผู้ใช้ระบุสาขา
        ห้ามไปโดนค่าเทอมของสาขาอื่นที่ชื่อคล้ายกัน
        """
        for alias, full in ALIASES.items():
            expected = programmes_in(full)
            for q in (f"ค่าเทอม{alias}เท่าไหร่", f"ค่าเทอมของ {alias} เท่าไหร่"):
                found = tuition.find_program(q)
                if expected:
                    self.assertIsNotNone(found, q)
                    self.assertIn(found["name"], expected, q)
                else:
                    self.assertIsNone(found, f"{q} -> {found and found['name']!r} ซึ่งเป็นสาขาอื่น")
                    self.assertIn("ระบุชื่อสาขา", tuition.answer(q), q)

    def test_ชื่อย่อที่สะกดตามคำเต็ม(self):
        """ผู้ใช้จริงพิมพ์ "วิทย์คอม" แล้วได้ช่วงค่าเทอมรวม"""
        for q in ("ค่าเทอมของวิทย์คอม", "วิทย์คอมค่าเทอมเท่าไหร่", "ค่าเทอมอนิเมชันเท่าไหร่"):
            self.assertIsNotNone(tuition.find_program(q), q)
        self.assertEqual(tuition.find_program("ค่าเทอมของวิทย์คอม")["name"], "วิทยาการคอมพิวเตอร์")

    def test_วิทย์คอมเป็นชื่อย่อของวิทยาการคอมพิวเตอร์ทุกขั้น(self):
        """ตารางคำย่อใช้ร่วมกันทั้งการค้นเอกสาร การระบุสาขาในบทสนทนา และตารางค่าเทอม"""
        from app.services.course_scope import programmes_named
        from app.services.query_expansion import expand_query

        names = ["วิทยาการคอมพิวเตอร์", "เทคโนโลยีสารสนเทศ", "คณิตศาสตร์"]
        for q in ("วิทย์คอมเรียนกี่หน่วยกิต", "อยากเรียนวิทย์คอม", "ค่าเทอมของวิทย์คอม"):
            self.assertIn("วิทยาการคอมพิวเตอร์", expand_query(q), q)
            self.assertEqual(programmes_named(q, names, from_assistant=False), ["วิทยาการคอมพิวเตอร์"], q)

    def test_ตัวเลขในคำตอบตรงกับตารางประกาศทุกสาขา(self):
        for p in PROGRAMS:
            reply = tuition.answer(f"ค่าเทอม{p['name']}เท่าไหร่")
            self.assertIn(f"ภาคปกติ {p['regular']:,} บาท", reply)
            if p["weekend"]:
                self.assertIn(f"ภาคเสาร์-อาทิตย์ {p['weekend']:,} บาท", reply)
            else:
                self.assertIn("ไม่เปิดรับภาคเสาร์-อาทิตย์", reply)
            self.assertIn(f"ที่มา: {tuition._data()['_source']}", reply)
            # ตัวเลขงบประมาณต่อหัวจาก มคอ.2 ต้องไม่ปนมา
            for budget in ("22,000", "24,000"):
                self.assertNotIn(budget, reply)

    def test_ไม่บอกสาขาและไม่มีบริบทให้ขอให้ระบุสาขา_ไม่เดา(self):
        reply = tuition.answer("ค่าเทอมเท่าไหร่")
        self.assertIn("ลองระบุชื่อสาขา", reply)
        self.assertIsNone(tuition.find_program("ค่าเทอมเท่าไหร่"))


class AskWhichProgrammeChecks(unittest.TestCase):
    """ถามข้อเท็จจริงด้วยชื่อย่อต้องไม่ถูกถามกลับว่าสาขาไหน แต่ไม่บอกสาขาเลยยังต้องถามกลับ"""

    def setUp(self):
        self.saved = chat._PROGRAM_NAMES
        chat._PROGRAM_NAMES = ["วิทยาการคอมพิวเตอร์", "เทคโนโลยีสารสนเทศ", "คณิตศาสตร์", "การแพทย์แผนไทยประยุกต์"]

    def tearDown(self):
        chat._PROGRAM_NAMES = self.saved

    def test_ชื่อย่อไม่ถูกถามกลับ(self):
        for q in ("วิทคอมเรียนกี่หน่วยกิต", "วิทย์คอมเรียนกี่หน่วยกิต", "comsci มีวิชาอะไรบ้าง",
                  "ไอทีจบไปทำงานอะไรได้", "คณิตเรียนกี่หน่วยกิต", "แพทย์แผนไทยมีวิชาอะไรบ้าง"):
            self.assertFalse(chat._needs_a_program_named(None, q), q)

    def test_ชื่อเต็มไม่ถูกถามกลับ(self):
        self.assertFalse(chat._needs_a_program_named(None, "วิทยาการคอมพิวเตอร์เรียนกี่หน่วยกิต"))

    def test_ไม่บอกสาขายังถามกลับ(self):
        for q in ("เรียนจบแล้วทำอาชีพอะไรได้บ้าง", "มีวิชาอะไรบ้าง", "เรียนกี่หน่วยกิต"):
            self.assertTrue(chat._needs_a_program_named(None, q), q)


class FollowUpInterpretationChecks(unittest.TestCase):
    def setUp(self):
        self.saved = (chat._context_programme, chat._condense)
        self.condense_calls = []
        self.context = None
        chat._context_programme = lambda db, history: self.context

        def fake_condense(connector, history, message, programme=None):
            self.condense_calls.append(message)
            return "ค่าเทอมหลักสูตรวิทยาการคอมพิวเตอร์เท่าไหร่"

        chat._condense = fake_condense
        self.history = [SimpleNamespace(role="user", content="วิทคอมเรียนกี่หน่วยกิต"),
                        SimpleNamespace(role="assistant", content="...")]

    def tearDown(self):
        chat._context_programme, chat._condense = self.saved

    def test_ไม่มีบทสนทนาใช้ข้อความเดิม(self):
        self.assertEqual(chat._tuition_question(None, None, [], "ค่าเทอมเท่าไหร่"), "ค่าเทอมเท่าไหร่")
        self.assertEqual(self.condense_calls, [])

    def test_บอกสาขามาเองไม่ใช้บริบท(self):
        """เปลี่ยนสาขากลางแชท: สาขาในข้อความต้องชนะสาขาในบทสนทนา"""
        self.context = "วิทยาการคอมพิวเตอร์"
        q = "แล้วค่าเทอมแพทย์แผนไทยล่ะ"
        self.assertEqual(chat._tuition_question(None, None, self.history, q), q)
        self.assertEqual(tuition.find_program(q)["name"], "การแพทย์แผนไทยประยุกต์")

    def test_ไม่บอกสาขาใช้สาขาจากบทสนทนาโดยไม่เรียกโมเดล(self):
        self.context = "วิทยาการคอมพิวเตอร์"
        asked = chat._tuition_question(None, None, self.history, "แล้วค่าเทอมล่ะ")
        self.assertEqual(tuition.find_program(asked)["name"], "วิทยาการคอมพิวเตอร์")
        self.assertEqual(self.condense_calls, [])

    def test_บริบทกำกวมให้ขอระบุสาขา_ไม่เดา(self):
        """ทดสอบก่อน deploy: หลังแนะนำหลายสาขา ขั้นเขียนคำถามใหม่เลือกสาขาแรกเองแล้วได้ค่าเทอมของสาขานั้น"""
        self.context = None
        asked = chat._tuition_question(None, None, self.history, "ค่าเทอมเท่าไหร่")
        self.assertEqual(asked, "ค่าเทอมเท่าไหร่")
        self.assertEqual(self.condense_calls, [])
        self.assertIn("ลองระบุชื่อสาขา", tuition.answer(asked))

    def test_คำตอบค่าเทอมไม่เก็บลงแคช_และไม่มีข้อความให้โมเดลเขียนต่อ(self):
        import uuid
        p = chat._tuition_reply(uuid.uuid4(), "ค่าเทอมวิทคอมเท่าไหร่")
        self.assertFalse(p.cacheable)
        self.assertEqual(p.messages, [])
        self.assertIn("12,000", p.canned)


if __name__ == "__main__":
    unittest.main(verbosity=2)
