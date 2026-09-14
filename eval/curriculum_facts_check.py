"""
ตรวจขั้นตรวจ ขั้นเผยแพร่ และบริการอ่านข้อมูลหลักสูตร (curriculum_facts) กับฐานข้อมูล local — MKO Phase 2

    python -m eval.curriculum_facts_check

ต้องมีฐานข้อมูล local ที่สกัดแล้ว (pipeline.mko.run) และเผยแพร่แล้วอย่างน้อยหนึ่งครั้ง (pipeline.mko.publish)

PublishedFactsChecks        อ่านการเผยแพร่ครั้งล่าสุด ไม่แก้ฐานข้อมูล
ReviewPublishWorkflowChecks ทำงานใน transaction เดียวแล้ว rollback ทุกข้อ ไม่ทิ้งผลตรวจหรือการเผยแพร่ไว้

ไม่ผูกชื่อหลักสูตรไว้ในโค้ด หลักสูตรที่ใช้ทดสอบเลือกจากข้อมูลในฐานข้อมูล ค่าที่ถูกต้องมาจาก eval/mko_gold.json
"""
from __future__ import annotations

import csv
import json
import os
import sys
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres@127.0.0.1:55432/course_advisor")
os.environ.setdefault("JWT_SECRET", "local-test-only")
_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "backend"))
sys.path.insert(0, str(_ROOT))

import psycopg  # noqa: E402
from psycopg.rows import dict_row, tuple_row  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.services.course_scope import _distinctive_name  # noqa: E402
from app.services.curriculum_facts import ANSWERED, NO_DATA, lookup  # noqa: E402
from app.services.structured_intent import STRUCTURED, StructuredIntent, detect  # noqa: E402

MKO_URL = os.environ.get("MKO_DATABASE_URL", "postgresql://postgres@127.0.0.1:55432/course_advisor")
GOLD = json.loads((_ROOT / "eval" / "mko_gold.json").read_text(encoding="utf-8"))["documents"]


def intent(field, name, ids, year=None):
    return StructuredIntent(STRUCTURED, "test", field, name, tuple(ids), year)


class PublishedFactsChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = SessionLocal()
        if cls.db.execute(text("SELECT count(*) FROM mko.v_live_publication")).scalar() == 0:
            raise AssertionError("ยังไม่มีการเผยแพร่ใน local — รัน python -m pipeline.mko.publish --by <ชื่อ> ก่อน")
        cls.values = cls.db.execute(text("SELECT * FROM mko.v_live_values")).mappings().all()
        cls.items = cls.db.execute(text("SELECT * FROM mko.v_live_list_items ORDER BY course_id, item_type, seq")).mappings().all()
        cls.courses = cls.db.execute(text("SELECT id, title FROM public.courses WHERE is_active")).mappings().all()
        cls.by_name = defaultdict(list)
        for c in cls.courses:
            cls.by_name[_distinctive_name(c["title"])].append(c["id"])
        cls.value_of = {(v["course_id"], v["field_key"]): v for v in cls.values}

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def name_of(self, course_id):
        return next(name for name, ids in self.by_name.items() if course_id in ids)

    def test_published_values_match_gold(self):
        checked = 0
        for v in self.values:
            expected = GOLD.get(v["source_filename"], {}).get(v["field_key"])
            if expected is None:
                continue
            got = v["value_int"] if v["value_int"] is not None else v["value_text"]
            with self.subTest(file=v["source_filename"], field=v["field_key"]):
                self.assertEqual(" ".join(str(got).split()).lower(), " ".join(str(expected).split()).lower())
            checked += 1
        self.assertGreaterEqual(checked, 40)

    def test_every_published_value_is_a_verified_extraction_with_its_evidence(self):
        bad = self.db.execute(text(
            """
            WITH latest AS (
                SELECT DISTINCT ON (document_id) id FROM mko.extraction_runs WHERE status = 'done'
                 ORDER BY document_id, started_at DESC)
            SELECT v.source_filename, v.field_key FROM mko.v_live_values v
             WHERE NOT EXISTS (
                SELECT 1 FROM mko.field_values fv JOIN latest l ON l.id = fv.run_id
                  JOIN mko.evidence e ON e.id = fv.evidence_id
                 WHERE fv.document_id = v.document_id AND fv.field_key = v.field_key AND fv.status = 'verified'
                   AND fv.value_int IS NOT DISTINCT FROM v.value_int AND fv.value_text IS NOT DISTINCT FROM v.value_text
                   AND e.quote = v.quote AND e.page_start = v.page_start AND e.page_end = v.page_end)
            """
        )).all()
        self.assertEqual(bad, [])

    def test_published_lists_are_complete_and_verified(self):
        grouped = defaultdict(list)
        for i in self.items:
            grouped[(i["course_id"], i["item_type"])].append(i["seq"])
        self.assertTrue(grouped)
        for key, seqs in grouped.items():
            with self.subTest(key=key):
                self.assertEqual(seqs, list(range(1, len(seqs) + 1)))

    def test_lookup_returns_the_published_value_with_its_source(self):
        for v in (v for v in self.values if v["field_key"] == "total_credits"):
            with self.subTest(course=v["course_title"]):
                result = lookup(self.db, intent("total_credits", self.name_of(v["course_id"]), [v["course_id"]]))
                self.assertEqual(result.status, ANSWERED)
                self.assertEqual(len(result.facts), 1)
                fact = result.facts[0]
                self.assertEqual((fact.value_int, fact.source.file, fact.source.page_start, fact.source.quote),
                                 (v["value_int"], v["source_filename"], v["page_start"], v["quote"]))
                self.assertIn(f"{v['value_int']} หน่วยกิต", result.answer)
                self.assertIn(f"ที่มา: {v['source_filename']}", result.answer)

    def test_same_programme_editions_are_not_mixed(self):
        tested = 0
        for name, ids in self.by_name.items():
            published = [cid for cid in ids if (cid, "total_credits") in self.value_of and (cid, "edition_year") in self.value_of]
            years = {self.value_of[(cid, "edition_year")]["value_int"] for cid in published}
            if len(published) < 2 or len(years) < 2:
                continue
            tested += 1
            for cid in published:
                year = self.value_of[(cid, "edition_year")]["value_int"]
                with self.subTest(programme=name, year=year):
                    result = lookup(self.db, intent("total_credits", name, ids, year))
                    self.assertEqual([f.course_id for f in result.facts], [str(cid)])
                    self.assertEqual(result.facts[0].value_int, self.value_of[(cid, "total_credits")]["value_int"])
            everything = lookup(self.db, intent("total_credits", name, ids))
            self.assertEqual({f.course_id: f.value_int for f in everything.facts},
                             {str(cid): self.value_of[(cid, "total_credits")]["value_int"] for cid in published})
            self.assertEqual([f.edition_year for f in everything.facts], sorted((f.edition_year for f in everything.facts), reverse=True))
        self.assertGreaterEqual(tested, 3)

    def test_year_without_an_edition_is_no_data(self):
        name, ids = next(iter(self.by_name.items()))
        result = lookup(self.db, intent("total_credits", name, ids, 2400))
        self.assertEqual((result.status, result.answer, result.facts), (NO_DATA, None, []))

    def test_field_without_published_data_is_no_data(self):
        published_lists = {(i["course_id"], i["item_type"]) for i in self.items}
        for name, ids in self.by_name.items():
            if not any((cid, "career") in published_lists for cid in ids):
                result = lookup(self.db, intent("careers", name, ids))
                self.assertEqual((result.status, result.answer), (NO_DATA, None))
                return
        self.skipTest("ทุกหลักสูตรมีรายการอาชีพที่เผยแพร่แล้ว")

    def test_lists_answer_one_edition_in_document_order(self):
        by_course = defaultdict(list)
        for i in self.items:
            if i["item_type"] == "objective":
                by_course[i["course_id"]].append(i["text"])
        self.assertTrue(by_course)
        for cid, texts in by_course.items():
            with self.subTest(course=cid):
                result = lookup(self.db, intent("objectives", self.name_of(cid), [cid]))
                self.assertEqual(result.status, ANSWERED)
                self.assertEqual(len(result.facts), 1)
                self.assertEqual(result.facts[0].items, texts)

    def test_questions_end_to_end(self):
        """คำถามสร้างจากชื่อและปีของหลักสูตรที่เผยแพร่ ผ่าน detect แล้ว lookup ต้องได้ค่าของฉบับนั้น"""
        for v in (v for v in self.values if v["field_key"] == "total_credits"):
            year_row = self.value_of.get((v["course_id"], "edition_year"))
            if year_row is None:
                continue
            name, year = self.name_of(v["course_id"]), year_row["value_int"]
            with self.subTest(course=v["course_title"]):
                found = detect(self.db, f"หลักสูตร{name} พ.ศ. {year} ต้องเรียนทั้งหมดกี่หน่วยกิต")
                result = lookup(self.db, found)
                self.assertEqual(result.status, ANSWERED)
                self.assertTrue(all(f.edition_year == year for f in result.facts))
                self.assertIn((str(v["course_id"]), v["value_int"]), {(f.course_id, f.value_int) for f in result.facts})


class ReviewPublishWorkflowChecks(unittest.TestCase):
    """ทุกข้อทำใน transaction ของ psycopg แล้ว rollback — ฐานข้อมูล local ไม่เปลี่ยน"""

    def setUp(self):
        from pipeline.mko import publish, review

        self.review, self.publish = review, publish
        self.conn = psycopg.connect(MKO_URL, row_factory=dict_row)
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.conn.rollback()
        self.conn.close()
        self.tmp.cleanup()

    def session_on_same_transaction(self) -> Session:
        """SQLAlchemy session บน connection เดียวกัน เพื่อให้ backend เห็นข้อมูลที่ยังไม่ commit"""
        self.conn.row_factory = tuple_row
        engine = create_engine("postgresql+psycopg://", creator=lambda: self.conn, poolclass=StaticPool,
                               pool_reset_on_return=None)
        engine.dialect.do_rollback = lambda dbapi_connection: None  # rollback จริงทำใน tearDown ครั้งเดียว
        return Session(engine)

    def export(self, statuses=("candidate", "needs_review")) -> list[dict]:
        path = Path(self.tmp.name) / "queue.csv"
        self.review.export_queue(self.conn, path, statuses)
        with path.open(encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))

    def apply(self, rows: list[dict], reviewer="test-reviewer"):
        path = Path(self.tmp.name) / "decisions.csv"
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=self.review.CSV_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
        return self.review.apply_file(self.conn, path, reviewer)

    def field_status(self, row: dict):
        document_id = row["review_key"].split("|")[0]
        return self.conn.execute(
            """
            WITH latest AS (SELECT DISTINCT ON (document_id) id FROM mko.extraction_runs WHERE status = 'done'
                             ORDER BY document_id, started_at DESC)
            SELECT fv.status, fv.reviewed_by, fv.run_id, fv.document_id FROM mko.field_values fv JOIN latest l ON l.id = fv.run_id
             WHERE fv.document_id = %s AND fv.field_key = %s
            """,
            (document_id, row["field"]),
        ).fetchone()

    def test_queue_holds_only_unverified_values_with_evidence(self):
        rows = self.export()
        self.assertTrue(rows)
        self.assertEqual({r["status"] for r in rows} - {"candidate", "needs_review"}, set())
        self.assertTrue(all(r["review_key"] and r["file"] and r["decision"] == "" for r in rows))
        self.assertTrue(all(r["quote"] and r["pages"] for r in rows))

    def test_human_verified_list_is_published_and_answered(self):
        row = next(r for r in self.export() if r["field"] == "careers" and r["status"] == "candidate")
        result = self.apply([{**row, "decision": "ผ่าน", "note": "ตรวจกับหน้าต้นฉบับ"}])
        self.assertEqual((result["recorded"], result["applied"], result["stale_rows"]), (1, 1, []))
        status = self.field_status(row)
        self.assertEqual((status["status"], status["reviewed_by"]), ("verified", "human:test-reviewer"))
        items = self.conn.execute(
            "SELECT text, status FROM mko.list_items WHERE run_id = %s AND item_type = 'career' ORDER BY seq",
            (status["run_id"],),
        ).fetchall()
        self.assertTrue(items and all(i["status"] == "verified" for i in items))

        summary = self.publish.publish(self.conn, "test-publisher", human_only=True)
        self.assertEqual(summary["policy"], "verified_human_only")
        self.assertEqual(summary["values_by_field"], {})
        self.assertEqual(summary["list_items_by_type"], {"career": len(items)})

        course_id = self.conn.execute("SELECT course_id FROM public.course_documents WHERE id = %s",
                                      (status["document_id"],)).fetchone()["course_id"]
        title = self.conn.execute("SELECT title FROM public.courses WHERE id = %s", (course_id,)).fetchone()["title"]
        db = self.session_on_same_transaction()
        answer = lookup(db, intent("careers", _distinctive_name(title), [course_id]))
        self.assertEqual(answer.status, ANSWERED)
        self.assertEqual(answer.facts[0].items, [i["text"] for i in items])
        self.assertEqual(answer.facts[0].reviewed_by, "human:test-reviewer")
        # การเผยแพร่แบบคนตรวจเท่านั้นไม่มีหน่วยกิตที่กฎอัตโนมัติยืนยัน จึงต้องไม่มีคำตอบหน่วยกิต
        self.assertEqual(lookup(db, intent("total_credits", _distinctive_name(title), [course_id])).status, NO_DATA)

    def test_rejected_value_is_not_published(self):
        row = next(r for r in self.export(("verified",)) if r["field"] == "total_credits")
        self.apply([{**row, "decision": "ไม่ผ่าน", "note": "ทดสอบ"}])
        self.assertEqual(self.field_status(row)["status"], "rejected")
        self.publish.publish(self.conn, "test-publisher")
        document_id = row["review_key"].split("|")[0]
        published = self.conn.execute(
            """
            SELECT count(*) AS n FROM mko.v_live_values
             WHERE document_id = %s AND field_key = 'total_credits'
            """,
            (document_id,),
        ).fetchone()["n"]
        self.assertEqual(published, 0)

    def test_decision_is_not_reused_when_the_extracted_value_changes(self):
        row = next(r for r in self.export() if r["field"] == "careers" and r["status"] == "candidate")
        self.apply([{**row, "decision": "ผ่าน"}])
        status = self.field_status(row)
        # จำลองการสกัดรอบใหม่ที่ได้รายการต่างไปจากที่คนตรวจไว้
        self.conn.execute("UPDATE mko.list_items SET text = text || ' (ฉบับแก้)', status = 'candidate', reviewed_by = NULL "
                          "WHERE run_id = %s AND item_type = 'career' AND seq = 1", (status["run_id"],))
        self.conn.execute("UPDATE mko.field_values SET status = 'candidate', reviewed_by = NULL, reviewed_at = NULL "
                          "WHERE run_id = %s AND field_key = 'careers'", (status["run_id"],))
        result = self.review.reapply(self.conn)
        self.assertTrue(any("careers" in s for s in result["stale"]))
        self.assertEqual(self.field_status(row)["status"], "candidate")

    def test_invalid_decision_file_records_nothing(self):
        rows = self.export()
        before = self.conn.execute("SELECT count(*) AS n FROM mko.review_decisions").fetchone()["n"]
        with self.assertRaises(SystemExit):
            self.apply([{**rows[0], "decision": "ผ่าน"}, {**rows[1], "decision": "อาจจะ"}])
        after = self.conn.execute("SELECT count(*) AS n FROM mko.review_decisions").fetchone()["n"]
        self.assertEqual(before, after)
        self.assertEqual(self.field_status(rows[0])["status"], rows[0]["status"])

    def test_reviewer_name_is_required(self):
        with self.assertRaises(SystemExit):
            self.apply([{**self.export()[0], "decision": "ผ่าน"}], reviewer="  ")

    def test_rollback_latest_restores_the_previous_publication(self):
        previous = self.conn.execute("SELECT id FROM mko.v_live_publication").fetchone()
        created = self.publish.publish(self.conn, "test-publisher")
        self.assertEqual(str(self.conn.execute("SELECT id FROM mko.v_live_publication").fetchone()["id"]),
                         created["publication_id"])
        self.publish.rollback_latest(self.conn)
        now = self.conn.execute("SELECT id FROM mko.v_live_publication").fetchone()
        self.assertEqual(now, previous)


if __name__ == "__main__":
    unittest.main(verbosity=1)
