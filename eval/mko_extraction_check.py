"""
ตรวจการสกัดข้อมูล มคอ. Phase 1 (docs/MKO_STRUCTURED_DATA_DESIGN.md)

    python -m eval.mko_extraction_check

ส่วนแรกทดสอบกฎด้วยข้อความตัวอย่าง ไม่ต้องมีฐานข้อมูล
ส่วนที่สองอ่านผลล่าสุดจากฐานข้อมูล local (bash scripts/mko_local_db.sh แล้ว python -m pipeline.mko.run)
เทียบกับ eval/mko_gold.json ถ้าเชื่อมต่อฐานข้อมูล local ไม่ได้ ส่วนที่สองจะถูกข้ามพร้อมบอกเหตุผล

เกณฑ์ผ่านของ Phase 1
    - หน่วยกิตรวมถูกทุกฉบับ หรือเป็น needs_review
    - ไม่มีค่าผิดที่ได้สถานะ verified
    - ทุกค่ามีหลักฐานที่เป็นข้อความในหน้าต้นฉบับจริง
    - field ที่เอกสารไม่มีต้องไม่มีค่า (ไม่เดา)
"""
from __future__ import annotations

import os
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]

from pipeline.mko.decide import AUTO_DOCUMENTS, AUTO_TWO_LOCATIONS, consolidate_course  # noqa: E402
from pipeline.mko.doc import PAGE_JOIN, DocText, Page, suspect_encoding  # noqa: E402
from pipeline.mko.extract import extract_document  # noqa: E402
from pipeline.mko.normalize import FoldedText, fold  # noqa: E402
from pipeline.mko.templates import build_sections, detect_template  # noqa: E402
from pipeline.mko.toc import is_toc_page, looks_like_table_of_contents  # noqa: E402

TITLE = "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาตัวอย่างศึกษา (พ.ศ. 2566)"

TQF_PAGES = [
    "หลักสูตรวิทยาศาสตรบัณฑิต\nสาขาวิชาตัวอย่างศึกษา\nหลักสูตรปรับปรุง พุทธศักราช 2566",
    "สารบัญ\nหมวดที่ 1 ข้อมูลทั่วไป ........ 1\n4. จำนวนหน่วยกิตที่เรียนตลอดหลักสูตร ........ 1\n"
    "8. อาชีพที่สามารถประกอบได้หลังสำเร็จการศึกษา ....... 2",
    "หมวดที่ 1\nข้อมูลทั่วไป\n1. รหัสและชื่อหลักสูตร\nรหัสหลักสูตร : 25501501100000\n"
    "ภาษาไทย : หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาตัวอย่างศึกษา\n"
    "ภาษาอังกฤษ : Bachelor of Science Program in Example Studies\n"
    "2. ชื่อปริญญาและสาขาวิชา\nชื่อเต็ม (ภาษาไทย) : วิทยาศาสตรบัณฑิต (ตัวอย่างศึกษา)\n"
    "ชื่อย่อ (ภาษาไทย) : วท.บ. (ตัวอย่างศึกษา)\nชื่อเต็ม (ภาษาอังกฤษ) : Bachelor of Science (Example Studies)\n"
    "ชื่อย่อ (ภาษาอังกฤษ) : B.Sc. (Example Studies)\n3. วิชาเอก\n-\n"
    "4. จำนวนหน่วยกิตที่เรียนตลอดหลักสูตร\nจำนวนหน่วยกิตรวมตลอดหลักสูตร ไม่น้อยกว่า 130 หน่วยกิต\n5. รูปแบบของหลักสูตร",
    "6. สถานภาพของหลักสูตรและการพิจารณาอนุมัติ\n"
    "6.1 หลักสูตรปรับปรุง พ.ศ. 2566 ปรับปรุงจากหลักสูตรวิทยาศาสตรบัณฑิต พ.ศ. 2561\n7. ความพร้อมในการเผยแพร่\n"
    "8. อาชีพที่สามารถประกอบได้หลังสำเร็จการศึกษา\n8.1 นักตัวอย่าง\n8.2 นักทดสอบระบบ\n"
    "8.3 นักวิเคราะห์ข้อมูล ตามประกาศ พ.ศ. 2558.1\n9. ชื่อ-สกุล ตำแหน่ง",
    "หมวดที่ 2 ข้อมูลเฉพาะของหลักสูตร\n1.3 วัตถุประสงค์ของหลักสูตร\nเพื่อผลิตบัณฑิตให้มีคุณลักษณะ ดังนี้\n"
    "1.3.1 มีความรู้ตัวอย่าง\n1.3.2 มีทักษะตัวอย่าง\n2. แผนพัฒนาและปรับปรุง\n1. ปรับปรุงหลักสูตร",
    "หมวดที่ 3 ระบบการจัดการศึกษา การดำเนินการ และโครงสร้างของหลักสูตร\n2.2 คุณสมบัติของผู้เข้าศึกษา\n"
    "จะต้องเป็นผู้สำเร็จการศึกษาระดับมัธยมศึกษาตอนปลายหรือเทียบเท่า\n2.3 ปัญหาของนักศึกษาแรกเข้า\n"
    "3.1.1 จำนวนหน่วยกิต\nจำนวนหน่วยกิตรวมตลอดหลักสูตรไม่น้อยกว่า 130 หน่วยกิต\n3.1.2 โครงสร้างหลักสูตร",
    "ภาคผนวก\nตารางเปรียบเทียบหลักสูตรเดิม\nจำนวนหน่วยกิตรวมตลอดหลักสูตร ไม่น้อยกว่า 120 หน่วยกิต\n"
    "8. อาชีพที่สามารถประกอบได้หลังสำเร็จการศึกษา\n8.1 อาชีพจากภาคผนวก",
]


def make_doc(pages_text, name="sample.pdf", sources=None) -> DocText:
    pages = []
    for number, text in enumerate(pages_text, start=1):
        source = (sources or {}).get(number, "text_layer")
        pages.append(Page(number, text, source, is_toc_page(text), suspect_encoding(text, min_count=5)))
    return DocText(name, pages)


def by_field(extraction):
    out = {}
    for d in extraction.scalars:
        out.setdefault(d.field_key, []).append(d)
    for d in extraction.lists:
        out[d.field_key] = [d]
    return out


class NormalizeAndTocChecks(unittest.TestCase):
    def test_หัวข้อที่ฟอนต์เพี้ยนค้นเจอและชี้กลับข้อความต้นฉบับได้(self):
        original = "หมวดที่ ๓\nระบบกำรจัดกำรศึกษำ"
        folded = FoldedText.of(original)
        m = folded.search(re.escape(fold("หมวดที่ 3 ระบบการจัดการศึกษา")))
        self.assertIsNotNone(m)
        start, end = folded.span(m.start(), m.end())
        self.assertEqual(original[start:end], original)

    def test_กฎสารบัญเหมือนของ_backend(self):
        from app.services.program_match import _looks_like_table_of_contents
        samples = [
            "8. อาชีพที่สามารถประกอบได้หลังสำเร็จการศึกษา ....... 2 9. ชื่อ ....... 3 10. สถานที่ ...... 4",
            "8.1 นักพัฒนาซอฟต์แวร์ 8.2 นักวิเคราะห์ระบบ 8.3 นักพัฒนาเว็บไซต์",
            "หมวดที่ 1 1 2 3 4 5 6 7",
            "",
        ]
        for text in samples:
            self.assertEqual(looks_like_table_of_contents(text), _looks_like_table_of_contents(text), text)

    def test_ร่องรอยฟอนต์เพี้ยน(self):
        self.assertTrue(suspect_encoding("ระบบกำรจัดกำรศึกษำ"))
        self.assertFalse(suspect_encoding("หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาศาสตร์เครื่องสำอาง"))

    def test_ตัวคั่นหน้าตรงกับ_trigger_ของฐานข้อมูล(self):
        migration = (ROOT / "db" / "migrations" / "001_mko_structured.sql").read_text(encoding="utf-8")
        self.assertEqual(PAGE_JOIN, "\n")
        self.assertIn("string_agg(text_clean, E'\\n' ORDER BY page_number)", migration)


class TqfExtractionChecks(unittest.TestCase):
    def setUp(self):
        self.doc = make_doc(TQF_PAGES)
        self.extraction = extract_document(self.doc, TITLE)
        self.fields = by_field(self.extraction)

    def value(self, key):
        decisions = self.fields[key]
        self.assertEqual(len(decisions), 1, decisions)
        return decisions[0]

    def test_รูปแบบและหมวด(self):
        self.assertEqual(self.extraction.template, "tqf2")
        keys = [s.key for s in self.extraction.sections]
        self.assertEqual(keys, ["front", "chapter.1", "chapter.2", "chapter.3", "appendix"])
        self.assertEqual(self.extraction.body_end, self.doc.page_start(6))

    def test_หน่วยกิตยืนยันจากสองหน้าและไม่เอาตัวเลขในภาคผนวก(self):
        credits = self.value("total_credits")
        self.assertEqual((credits.value_int, credits.status, credits.reviewed_by), (130, "verified", AUTO_TWO_LOCATIONS))
        pages = {self.doc.page_at(ev.start).page_number for ev in credits.evidence}
        self.assertEqual(pages, {3, 6})

    def test_ปีไม่เอาปีของหลักสูตรที่ปรับปรุงมา(self):
        year = self.value("edition_year")
        self.assertEqual((year.value_int, year.status), (2566, "verified"))
        self.assertEqual(self.value("revision_type").value_text, "revised")

    def test_ชื่อและปริญญา(self):
        self.assertEqual(self.value("program_name_th").value_text, "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาตัวอย่างศึกษา")
        self.assertEqual(self.value("program_name_en").value_text, "Bachelor of Science Program in Example Studies")
        self.assertEqual(self.value("degree_abbr_th").value_text, "วท.บ. (ตัวอย่างศึกษา)")
        self.assertEqual(self.value("degree_abbr_en").value_text, "B.Sc. (Example Studies)")
        self.assertEqual(self.value("degree_level").value_text, "bachelor")
        self.assertEqual(self.value("program_name_th").status, "candidate")

    def test_อาชีพหยุดที่ข้อ9_และไม่นับเลขกลางข้อความ(self):
        careers = self.value("careers")
        self.assertEqual([i.text for i in careers.items],
                         ["นักตัวอย่าง", "นักทดสอบระบบ", "นักวิเคราะห์ข้อมูล ตามประกาศ พ.ศ. 2558.1"])
        self.assertEqual(careers.status, "candidate")

    def test_วัตถุประสงค์ไม่รวมข้อความนำและหยุดที่หัวข้อถัดไป(self):
        objectives = self.value("objectives")
        self.assertEqual([i.text for i in objectives.items], ["มีความรู้ตัวอย่าง", "มีทักษะตัวอย่าง"])

    def test_คุณสมบัติผู้เข้าศึกษาหยุดก่อน_2_3(self):
        admission = self.value("admission")
        self.assertEqual([i.text for i in admission.items],
                         ["จะต้องเป็นผู้สำเร็จการศึกษาระดับมัธยมศึกษาตอนปลายหรือเทียบเท่า"])

    def test_หลักฐานทุกค่าเป็นข้อความในหน้าจริง(self):
        for d in self.extraction.scalars:
            for ev in d.evidence:
                a, b = self.doc.trimmed(ev.start, ev.end)
                pages = self.doc.pages_of(a, b)
                source = PAGE_JOIN.join(p.text for p in pages)
                self.assertIn(self.doc.slice(a, b), source, d.field_key)


class StatusRuleChecks(unittest.TestCase):
    def test_ค่าขัดกันเป็น_needs_review_ทุกค่า(self):
        pages = list(TQF_PAGES)
        pages[5] = pages[5].replace("ไม่น้อยกว่า 130", "ไม่น้อยกว่า 127")
        credits = by_field(extract_document(make_doc(pages), TITLE))["total_credits"]
        self.assertEqual(sorted(d.value_int for d in credits), [127, 130])
        self.assertTrue(all(d.status == "needs_review" for d in credits))

    def test_หน้าที่มี_OCR_ไม่ถูกยืนยัน(self):
        doc = make_doc(TQF_PAGES, sources={3: "text_layer+ocr", 6: "text_layer+ocr"})
        credits = by_field(extract_document(doc, TITLE))["total_credits"][0]
        self.assertEqual(credits.status, "needs_review")
        self.assertIn("OCR", credits.reason)

    def test_พบตำแหน่งเดียวเป็น_candidate(self):
        pages = list(TQF_PAGES)
        pages[5] = pages[5].split("3.1.1")[0]
        credits = by_field(extract_document(make_doc(pages), TITLE))["total_credits"][0]
        self.assertEqual((credits.value_int, credits.status), (130, "candidate"))

    def test_ไม่มีหัวข้อไม่เดาและไม่ไปเอาจากภาคผนวก(self):
        pages = list(TQF_PAGES)
        pages[3] = pages[3].split("8. อาชีพ")[0]
        careers = by_field(extract_document(make_doc(pages), TITLE))["careers"][0]
        self.assertEqual((careers.status, careers.items), ("not_found", []))

    def test_ปีไม่ตรงกับชื่อหลักสูตรในระบบ(self):
        extraction = extract_document(make_doc(TQF_PAGES), "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาตัวอย่างศึกษา (พ.ศ. 2561)")
        year = by_field(extraction)["edition_year"][0]
        self.assertEqual(year.status, "needs_review")

    def test_ชื่อไม่ตรงกับหลักสูตรในระบบ(self):
        extraction = extract_document(make_doc(TQF_PAGES), "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาอื่น (พ.ศ. 2566)")
        self.assertEqual(by_field(extraction)["program_name_th"][0].status, "needs_review")

    def test_ข้อความฟอนต์เพี้ยนเป็น_needs_review(self):
        pages = list(TQF_PAGES)
        pages[2] = pages[2].replace("หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาตัวอย่างศึกษา",
                                    "หลักสูตรวิทยำศำสตรบัณฑิต สำขำวิชำตัวอย่ำงศึกษำ")
        name = by_field(extract_document(make_doc(pages), TITLE))["program_name_th"][0]
        self.assertEqual(name.status, "needs_review")

    def test_เอกสารของหลักสูตรเดียวกันตรงกันยกระดับ_และไม่ตรงกันเป็น_needs_review(self):
        full = extract_document(make_doc(TQF_PAGES), TITLE)
        brief = extract_document(make_doc(BRIEF_PAGES, "sample_brief.pdf"), TITLE)
        consolidate_course([full, brief])
        name_en = [d for ex in (full, brief) for d in ex.scalars if d.field_key == "program_name_en"]
        self.assertTrue(all(d.status == "verified" and d.reviewed_by == AUTO_DOCUMENTS for d in name_en))

        other = extract_document(make_doc([BRIEF_PAGES[0].replace("130", "127")], "other_brief.pdf"), TITLE)
        full2 = extract_document(make_doc(TQF_PAGES), TITLE)
        consolidate_course([full2, other])
        credits = [d for ex in (full2, other) for d in ex.scalars if d.field_key == "total_credits"]
        self.assertTrue(all(d.status == "needs_review" for d in credits))


BRIEF_PAGES = [
    "1\nหลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาตัวอย่างศึกษา\nBachelor of Science Program in Example Studies\n"
    "วท.บ. (ตัวอย่างศึกษา) B.Sc. (Example Studies)\nหลักสูตรปรับปรุง พ.ศ. 2566\nปรัชญา\nมุ่งผลิตบัณฑิตตัวอย่าง\n"
    "วัตถุประสงค์ของหลักสูตร เพื่อผลิตบัณฑิตที่มีคุณลักษณะดังต่อไปนี้\n1 มีความรู้ตัวอย่าง\n"
    "ในการประกอบอาชีพ 2 ปี\n2. มีทักษะตัวอย่าง\nจำนวนหน่วยกิต\nจำนวนหน่วยกิตรวมตลอดหลักสูตรไม่น้อยกว่า 130 หน่วยกิต",
]


class OtherTemplateChecks(unittest.TestCase):
    def test_ใบสรุปหลักสูตร(self):
        doc = make_doc(BRIEF_PAGES, "sample_brief.pdf")
        extraction = extract_document(doc, TITLE)
        fields = by_field(extraction)
        self.assertEqual(extraction.template, "brief")
        self.assertEqual(fields["degree_abbr_th"][0].value_text, "วท.บ. (ตัวอย่างศึกษา)")
        self.assertEqual(fields["degree_abbr_en"][0].value_text, "B.Sc. (Example Studies)")
        self.assertEqual(fields["degree_name_th"][0].status, "not_found")
        self.assertEqual(fields["total_credits"][0].value_int, 130)
        self.assertEqual([i.text for i in fields["objectives"][0].items],
                         ["มีความรู้ตัวอย่าง ในการประกอบอาชีพ 2 ปี", "มีทักษะตัวอย่าง"])
        self.assertEqual(fields["careers"][0].status, "not_found")
        self.assertEqual(fields["admission"][0].status, "not_found")

    def test_หน้าเว็บ(self):
        pages = [
            "หลักสูตรสาธารณสุขศาสตรบัณฑิต สาขาวิชาตัวอย่างศึกษา\nBachelor of Public Health Program in Example Studies",
            "ข้อมูลสำคัญ\nจำนวนหน่วยกิตรวมตลอดหลักสูตร: 129 หน่วยกิต",
            "อาชีพที่สามารถประกอบได้หลังสำเร็จการศึกษา\nผู้สำเร็จการศึกษาสามารถประกอบอาชีพได้ เช่น\n- นักตัวอย่าง\n- นักทดสอบ",
        ]
        extraction = extract_document(make_doc(pages, "sample_web.txt", sources={1: "plain_text", 2: "plain_text", 3: "plain_text"}), TITLE)
        fields = by_field(extraction)
        self.assertEqual(extraction.template, "web_page")
        self.assertEqual(fields["total_credits"][0].value_int, 129)
        self.assertEqual(fields["edition_year"][0].status, "not_found")
        self.assertEqual([i.text for i in fields["careers"][0].items], ["นักตัวอย่าง", "นักทดสอบ"])

    def test_เกณฑ์_2565_คุณสมบัติหมวด6_และวัตถุประสงค์หยุดที่_PLO(self):
        pages = [
            "หลักสูตรวิทยาศาสตรมหาบัณฑิต สาขาวิชาตัวอย่างศึกษา\nหลักสูตรใหม่ พ.ศ. 2566",
            "หมวดที่ 1 ข้อมูลทั่วไป\n4. จำนวนหน่วยกิตที่เรียนตลอดหลักสูตร\nจำนวนหน่วยกิตตลอดหลักสูตรไม่น้อยกว่า \n36 \nหน่วยกิต\n5. รูปแบบ",
            "หมวดที่ 2 ปรัชญา วัตถุประสงค์ และผลลัพธ์การเรียนรู้\n1.3 วัตถุประสงค์ของหลักสูตร\n1.3.1 มีความรู้\n1.3.2 มีทักษะ\n"
            "2. ผลลัพธ์การเรียนรู้ระดับหลักสูตร (PLOs)\nPLO 1 บูรณาการความรู้",
            "หมวดที่ 3 โครงสร้างหลักสูตร รายวิชา และหน่วยกิต\n1.1 จำนวนหน่วยกิต\nจำนวนหน่วยกิตรวมตลอดหลักสูตรไม่น้อยกว่า 36 หน่วยกิต\n1.2 โครงสร้างหลักสูตร",
            "หมวดที่ 6 คุณสมบัติของผู้เข้าศึกษา\n1. คุณสมบัติของผู้เข้าศึกษา\nให้เป็นไปตามข้อบังคับของมหาวิทยาลัยและมีคุณสมบัติดังนี้\n"
            "1.1 แผน 1\n1.1.1 สำเร็จปริญญาตรี\n1.2 แผน 2\n1.2.1 มีประสบการณ์\n2. การคัดเลือกผู้เข้าศึกษา",
        ]
        extraction = extract_document(make_doc(pages), "หลักสูตรวิทยาศาสตรมหาบัณฑิต สาขาวิชาตัวอย่างศึกษา (พ.ศ. 2566)")
        fields = by_field(extraction)
        self.assertEqual(extraction.template, "std2565")
        self.assertEqual((fields["total_credits"][0].value_int, fields["total_credits"][0].status), (36, "verified"))
        self.assertEqual([i.text for i in fields["objectives"][0].items], ["มีความรู้", "มีทักษะ"])
        admission = [i.text for i in fields["admission"][0].items]
        self.assertEqual(len(admission), 3)
        self.assertTrue(admission[1].startswith("แผน 1") and "สำเร็จปริญญาตรี" in admission[1])
        self.assertEqual(fields["revision_type"][0].value_text, "new")

    def test_ชื่อปริญญาพร้อมอักษรย่อในวงเล็บของใบสรุป(self):
        pages = [
            "~ 1 ~\nหลักสูตรตัวอย่างประยุกต์บัณฑิต\nBachelor of Applied Example Program\n"
            "ตัวอย่างประยุกต์บัณฑิต (ตอป.บ.)\nBachelor of Applied Example (B.AE.)\nหลักสูตรปรับปรุง พุทธศักราช 2565\nปรัชญา\n"
            "วัตถุประสงค์ของหลักสูตร\n1. มีความรู้\nจำนวนหน่วยกิต\nจำนวนหน่วยกิตรวมตลอดหลักสูตรไม่น้อยกว่า 147 หน่วยกิต",
        ]
        fields = by_field(extract_document(make_doc(pages, "x_brief.pdf"), "หลักสูตรตัวอย่างประยุกต์บัณฑิต (พ.ศ. 2565)"))
        self.assertEqual(fields["degree_name_th"][0].value_text, "ตัวอย่างประยุกต์บัณฑิต")
        self.assertEqual(fields["degree_abbr_th"][0].value_text, "ตอป.บ.")
        self.assertEqual(fields["degree_name_en"][0].value_text, "Bachelor of Applied Example")
        self.assertEqual(fields["degree_abbr_en"][0].value_text, "B.AE.")

    def test_หัวกระดาษและเลขหน้าของหน้าถัดไปไม่ติดมากับข้อสุดท้าย(self):
        pages = list(TQF_PAGES)
        pages[3] = pages[3].split("9. ชื่อ")[0]
        pages.insert(4, "มคอ. 2\n 12 \n9. ชื่อ-สกุล ตำแหน่งทางวิชาการ")
        careers = by_field(extract_document(make_doc(pages), TITLE))["careers"][0]
        self.assertEqual(careers.items[-1].text, "นักวิเคราะห์ข้อมูล ตามประกาศ พ.ศ. 2558.1")
        self.assertEqual(careers.status, "candidate")

    def test_เลขข้อข้ามหรือซ้ำยังแยกข้อได้แต่ต้องให้คนตรวจ(self):
        pages = list(TQF_PAGES)
        pages[3] = ("8. อาชีพที่สามารถประกอบได้หลังสำเร็จการศึกษา\n8.1 นักหนึ่ง\n8.2 นักสอง\n8.4 นักสาม\n8.4 นักสี่\n"
                    "9. ชื่อ-สกุล ตำแหน่ง")
        careers = by_field(extract_document(make_doc(pages), TITLE))["careers"][0]
        self.assertEqual([i.text for i in careers.items], ["นักหนึ่ง", "นักสอง", "นักสาม", "นักสี่"])
        self.assertEqual(careers.status, "needs_review")
        self.assertIn("เลขข้อ", careers.reason)

    def test_ไม่รู้จักรูปแบบ_ทุกค่าเป็น_not_found(self):
        extraction = extract_document(make_doc(["เอกสารอื่นที่ไม่ใช่ มคอ. จำนวน 130 หน่วยกิต"]), TITLE)
        self.assertEqual(extraction.template, "unknown")
        self.assertTrue(all(d.status == "not_found" for d in extraction.scalars))
        self.assertTrue(all(d.status == "not_found" for d in extraction.lists))


class SafetyChecks(unittest.TestCase):
    def test_migration_ไม่เขียนตาราง_public(self):
        sql = (ROOT / "db" / "migrations" / "001_mko_structured.sql").read_text(encoding="utf-8")
        body = re.sub(r"--[^\n]*", "", sql)
        for statement in re.findall(r"\b(?:ALTER|DROP|TRUNCATE|INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+(?:TABLE\s+)?(?:IF\s+EXISTS\s+)?([\w.]+)", body, re.I):
            self.assertFalse(statement.lower().startswith("public."), statement)
        self.assertNotIn("course_chunks", body)

    def test_ตัวสกัดไม่เรียกโมเดลภาษาและไม่เขียน_course_chunks(self):
        for path in (ROOT / "pipeline" / "mko").glob("*.py"):
            source = path.read_text(encoding="utf-8")
            code = "\n".join(line for line in source.splitlines() if not line.strip().startswith("#"))
            for forbidden in ("import httpx", "from llm", "import llm", "gemini", "OllamaConnector", "generateContent"):
                self.assertNotIn(forbidden, code, f"{path.name}: {forbidden}")
            self.assertIsNone(re.search(r"(INSERT INTO|UPDATE|DELETE FROM)\s+(public\.)?course_chunks", code), path.name)

    def test_run_ปฏิเสธฐานข้อมูลที่ไม่ใช่เครื่องนี้(self):
        from pipeline.mko.run import database_url
        with self.assertRaises(SystemExit):
            database_url("postgresql://advisor_ingest:x@db.example.org:5432/course_advisor")
        self.assertTrue(database_url("postgresql://postgres@127.0.0.1:55432/course_advisor"))


def _local_connection():
    try:
        import psycopg
        from psycopg.rows import dict_row
        url = os.environ.get("MKO_DATABASE_URL", "postgresql://postgres@127.0.0.1:55432/course_advisor")
        return psycopg.connect(url, connect_timeout=3, row_factory=dict_row)
    except Exception as exc:  # noqa: BLE001
        return exc


class LocalDatabaseChecks(unittest.TestCase):
    """ผลจริงของทั้ง 31 เอกสารในฐานข้อมูล local"""

    @classmethod
    def setUpClass(cls):
        conn = _local_connection()
        if isinstance(conn, Exception):
            raise unittest.SkipTest(f"ต่อฐานข้อมูล local ไม่ได้ ({type(conn).__name__}) — รัน scripts/mko_local_db.sh และ pipeline.mko.run ก่อน")
        cls.conn = conn
        from pipeline.mko.gold import LATEST_VALUES_SQL, compare, load_gold
        cls.rows = conn.execute(LATEST_VALUES_SQL).fetchall()
        if not any(r["field_key"] for r in cls.rows):
            raise unittest.SkipTest("ฐานข้อมูล local ยังไม่มีผลการสกัด — รัน python -m pipeline.mko.run ก่อน")
        cls.verdicts = compare(cls.rows, load_gold())

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def verdicts_for(self, field_key):
        return [v for v in self.verdicts if v.field_key == field_key]

    def test_สกัดครบทุกเอกสารและไม่มีรอบที่ล้มเหลว(self):
        files = {r["file"] for r in self.rows}
        self.assertEqual(len(files), 31)
        self.assertEqual([r["file"] for r in self.rows if r["run_status"] != "done"], [])

    def test_หน่วยกิตรวมถูกทุกฉบับหรือเป็น_needs_review(self):
        verdicts = self.verdicts_for("total_credits")
        self.assertEqual(len(verdicts), 31)
        bad = [(v.file, v.expected, v.got, v.verdict) for v in verdicts if v.verdict not in ("correct", "needs_review")]
        self.assertEqual(bad, [])

    def test_ปีหลักสูตรถูกหรือเป็น_needs_review(self):
        bad = [(v.file, v.expected, v.got, v.verdict) for v in self.verdicts_for("edition_year")
               if v.verdict not in ("correct", "needs_review")]
        self.assertEqual(bad, [])

    def test_ไม่มีค่าผิดที่ได้_verified(self):
        self.assertEqual([(v.file, v.field_key, v.expected, v.got) for v in self.verdicts if v.wrong_verified], [])

    def test_ไม่มีค่าผิดที่เป็น_candidate(self):
        self.assertEqual([(v.file, v.field_key, v.expected, v.got) for v in self.verdicts if v.verdict == "wrong"], [])

    def test_field_ที่เอกสารไม่มีต้องไม่มีค่า(self):
        self.assertEqual([(v.file, v.field_key, v.got) for v in self.verdicts if v.verdict == "unexpected_value"], [])

    def test_ทุกค่ามีหลักฐานที่อยู่ในหน้าต้นฉบับจริง(self):
        missing = self.conn.execute(
            """
            SELECT count(*) AS n FROM mko.field_values
             WHERE status NOT IN ('not_found', 'not_applicable') AND evidence_id IS NULL
            """
        ).fetchone()["n"]
        self.assertEqual(missing, 0)
        mismatched = self.conn.execute(
            """
            SELECT count(*) AS n
              FROM mko.evidence e
             WHERE strpos((SELECT string_agg(p.text_clean, E'\\n' ORDER BY p.page_number)
                             FROM mko.document_pages p
                            WHERE p.document_id = e.document_id
                              AND p.page_number BETWEEN e.page_start AND e.page_end), e.quote) = 0
            """
        ).fetchone()["n"]
        self.assertEqual(mismatched, 0)

    def test_จำนวนข้อของรายการถูกหรือเป็น_needs_review(self):
        bad = [(v.file, v.field_key, v.expected, v.got, v.verdict) for v in self.verdicts
               if v.field_key in ("objectives", "careers", "admission") and v.verdict not in ("correct", "needs_review")]
        self.assertEqual(bad, [])

    def test_ข้อสุดท้ายไม่มีหัวกระดาษของหน้าถัดไป(self):
        from pipeline.mko.gold import load_gold, normalise
        for file, expectations in load_gold().items():
            expected = expectations.get("careers_last_item")
            if expected is None:
                continue
            row = self.conn.execute(
                """
                SELECT li.text FROM mko.list_items li
                  JOIN public.course_documents d ON d.id = li.document_id
                  JOIN LATERAL (SELECT id FROM mko.extraction_runs r WHERE r.document_id = d.id
                                 ORDER BY started_at DESC LIMIT 1) latest ON latest.id = li.run_id
                 WHERE d.original_filename = %s AND li.item_type = 'career'
                 ORDER BY li.seq DESC LIMIT 1
                """,
                (file,),
            ).fetchone()
            self.assertIsNotNone(row, file)
            self.assertEqual(normalise(row["text"]), normalise(expected), file)
        leaked = self.conn.execute(
            "SELECT count(*) AS n FROM mko.list_items WHERE text ~ 'มคอ\\.?\\s*2'"
        ).fetchone()["n"]
        self.assertEqual(leaked, 0)

    def test_verified_มาจากกฎที่กำหนดเท่านั้น(self):
        reviewers = {r["reviewed_by"] for r in self.rows if r["status"] == "verified"}
        self.assertTrue(reviewers <= {AUTO_TWO_LOCATIONS, AUTO_DOCUMENTS}, reviewers)

    def test_หลักสูตรเดียวกันต่างปีไม่ปนกัน(self):
        credits = {r["file"]: r["value_int"] for r in self.rows
                   if r["field_key"] == "total_credits" and r["status"] in ("candidate", "verified")}
        self.assertEqual((credits.get("ma64.pdf"), credits.get("ma69.pdf")), (130, 124))
        titles = {r["file"]: r["course_title"] for r in self.rows}
        self.assertNotEqual(titles["ma64.pdf"], titles["ma69.pdf"])
        count = self.conn.execute("SELECT count(*) AS n FROM mko.curricula").fetchone()["n"]
        self.assertEqual(count, 24)


if __name__ == "__main__":
    unittest.main(verbosity=2)
