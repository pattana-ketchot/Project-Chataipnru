"""
ทดสอบตัวนำเข้าไฟล์ที่อนุมัติแล้ว — Phase 3C (pipeline/crawl/approve.py)

    python eval/crawl_ingest_worker_check.py \
        --database-url postgresql://<owner>@HOST:PORT/crawl_test \
        --ingest-url   postgresql://<ingest-role>@HOST:PORT/crawl_test \
        --api-url      postgresql://<api-role>@HOST:PORT/crawl_test

ต้องเป็นฐานข้อมูลทดสอบที่แยกจาก production เท่านั้น
------------------------------------------------
มีด่านสองชั้นก่อนแตะข้อมูลใด
  1. ชื่อฐานข้อมูลใน URL ต้องอยู่ในรายการที่อนุญาต และห้ามมีคำว่า course_advisor
  2. ถาม current_database() จากเซิร์ฟเวอร์จริงแล้วเทียบซ้ำ ก่อน truncate หรือ seed
ไม่มีการถอยไปใช้ DATABASE_URL หรือ INGEST_DATABASE_URL ที่ตั้งไว้ในเครื่อง เพราะสองค่านั้น
ชี้ไป production ได้ สคริปต์นี้จะไม่เดาปลายทางเอง

สิ่งที่ทดสอบจริงกับ PostgreSQL
-----------------------------
การยึดงานด้วย FOR UPDATE SKIP LOCKED · การที่คำสั่งถอนถูกบล็อกจริง · CHECK constraint ·
partial unique index · ON CONFLICT ของ course_documents · สิทธิ์ของ role · เงื่อนไข
affected rows · transaction boundary ของ pipeline.ingest.run() ตัวจริง

สิ่งที่แทนด้วยตัวปลอม
--------------------
เฉพาะ "การคำนวณเวกเตอร์" เท่านั้น — แทน pipeline.ingest.embed_chunks ด้วยตัวที่คืน
เวกเตอร์ 1024 มิติ และแทน OllamaConnector ที่ worker ใช้ตรวจมิติ จึงไม่ติดต่อบริการ
embedding ใด ๆ และไม่ดาวน์โหลดโมเดล ส่วนการ extract/clean/chunk/insert เป็นของจริงทั้งหมด
นี่ไม่ใช่การยืนยันแบบ end-to-end กับโมเดลจริง — ดูข้อจำกัดในรายงาน Phase 3C
"""
from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ชื่อฐานข้อมูลที่ยอมให้ทดสอบ — ต้องตั้งก่อน import อย่างอื่นที่แตะฐานข้อมูล
ALLOWED_DB_NAMES = {"crawl_test", "ingest_worker_test"}
FORBIDDEN_IN_URL = "course_advisor"


def db_name_of(url: str) -> str:
    return url.rsplit("/", 1)[-1].split("?")[0]


def guard(urls: dict[str, str]) -> None:
    for label, url in urls.items():
        if not url:
            continue
        if FORBIDDEN_IN_URL in url:
            raise SystemExit(f"ปฏิเสธ: {label} มีคำว่า {FORBIDDEN_IN_URL!r} — ห้ามชี้ไปฐานข้อมูลจริง")
        name = db_name_of(url)
        if name not in ALLOWED_DB_NAMES:
            raise SystemExit(f"ปฏิเสธ: {label} ชี้ไปฐานข้อมูล {name!r} "
                             f"ซึ่งไม่อยู่ในรายการที่อนุญาต {sorted(ALLOWED_DB_NAMES)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", required=True, help="role ที่เขียนได้ ใช้เตรียมข้อมูลและตรวจผล")
    ap.add_argument("--ingest-url", required=True, help="role ที่สิทธิ์เท่ากับ advisor_ingest — worker ใช้ตัวนี้")
    ap.add_argument("--api-url", default=None, help="role ที่สิทธิ์เท่ากับ advisor_api — ใช้ตรวจว่าเขียนคลังไม่ได้")
    args = ap.parse_args()
    guard({"--database-url": args.database_url, "--ingest-url": args.ingest_url,
           "--api-url": args.api_url or ""})

    import psycopg
    from psycopg.rows import dict_row

    # ด่านชั้นสอง: ถามเซิร์ฟเวอร์เองว่าเรากำลังคุยกับฐานข้อมูลชื่ออะไร
    for label, url in (("--database-url", args.database_url), ("--ingest-url", args.ingest_url)):
        with psycopg.connect(url) as c, c.cursor() as cur:
            cur.execute("SELECT current_database()")
            actual = cur.fetchone()[0]
        if actual not in ALLOWED_DB_NAMES:
            raise SystemExit(f"ปฏิเสธ: {label} ต่อจริงไปที่ {actual!r}")

    staging = Path(tempfile.mkdtemp(prefix="w_staging_"))
    documents = Path(tempfile.mkdtemp(prefix="w_documents_"))
    outside = Path(tempfile.mkdtemp(prefix="w_outside_"))

    os.environ["INGEST_DATABASE_URL"] = args.ingest_url
    os.environ["EMBED_MODEL"] = "bge-m3"
    os.environ["EMBED_DIM"] = "1024"
    os.environ["CRAWL_STAGING_DIR"] = str(staging)
    os.environ["DOCUMENTS_DIR"] = str(documents)
    os.environ.pop("OCR_TEXT_JSON", None)

    import fitz

    from pipeline import ingest as ingest_mod
    from pipeline.crawl import approve as W

    print(f"ฐานข้อมูลทดสอบ: {db_name_of(args.database_url)} @ {args.database_url.split('@')[-1].split('/')[0]}")
    print(f"staging: {staging}\ndocuments: {documents}\nนอก staging: {outside}")

    # ---- ตัวปลอมของ embedding -------------------------------------------
    calls = {"embed": 0, "run": 0}
    real_run = ingest_mod.run

    def fake_embed(connector, chunks, batch_log_every: int = 20):
        calls["embed"] += 1
        return [[0.001 * (i % 7) for _ in range(1024)] for i, _ in enumerate(chunks)]

    def counted_run(*a, **kw):
        calls["run"] += 1
        return real_run(*a, **kw)

    class FakeConnector:
        dim = 1024

        def __init__(self, base_url: str = "", embed_model: str = "", **_: object) -> None:
            self.embed_model = embed_model

        def embed(self, text: str) -> list[float]:
            return [0.0] * FakeConnector.dim

    ingest_mod.embed_chunks = fake_embed
    ingest_mod.run = counted_run
    W.OllamaConnector = FakeConnector

    # ---- ไฟล์ทดสอบ ------------------------------------------------------
    def make_pdf(marker: str) -> bytes:
        doc = fitz.open()
        for page_no in range(2):
            page = doc.new_page()
            body = " ".join(f"{marker} หลักสูตรวิทยาศาสตรบัณฑิต บรรทัดที่ {i}" for i in range(40))
            page.insert_text((60, 80), f"หน้า {page_no + 1} {marker}")
            page.insert_textbox(fitz.Rect(50, 110, 550, 780), body, fontsize=9)
        raw = doc.tobytes()
        doc.close()
        return raw

    def sha(b: bytes) -> str:
        return hashlib.sha256(b).hexdigest()

    PDF_A, PDF_B = make_pdf("ALPHA"), make_pdf("BETA")
    NOT_PDF = b"<html><body>not a pdf at all</body></html>"
    FAKE_PDF = b"%PDF-1.4 but the rest is garbage " + b"\x00" * 900

    c = Checks()

    # ---- เตรียมข้อมูล ---------------------------------------------------
    def reset() -> dict[str, str]:
        with psycopg.connect(args.database_url, autocommit=True, row_factory=dict_row) as conn, \
                conn.cursor() as cur:
            cur.execute("DELETE FROM mko.crawl_decisions")
            cur.execute("DELETE FROM mko.crawl_sources")
            cur.execute("DELETE FROM course_chunks")
            cur.execute("DELETE FROM course_documents")
            cur.execute("DELETE FROM courses")
            cur.execute("INSERT INTO courses (code, title) VALUES "
                        "('cs66','วิทยาการคอมพิวเตอร์ (พ.ศ. 2566)'),"
                        "('ma69','คณิตศาสตร์ (พ.ศ. 2569)') RETURNING id")
            cur.execute("SELECT code, id::text AS id FROM courses")
            ids = {r["code"]: r["id"] for r in cur.fetchall()}
        for p in list(staging.iterdir()) + list(documents.iterdir()):
            if p.is_file():
                p.unlink()
            elif p.is_dir():
                pass
        calls["embed"] = calls["run"] = 0
        FakeConnector.dim = 1024
        os.environ["EMBED_MODEL"] = "bge-m3"
        os.environ["EMBED_DIM"] = "1024"
        os.environ["CRAWL_STAGING_DIR"] = str(staging)
        os.environ["DOCUMENTS_DIR"] = str(documents)
        return ids

    def stage(name: str, body: bytes) -> Path:
        p = staging / name
        p.write_bytes(body)
        return p

    def seed(*, url: str, staging_path: str | None, source_sha: str | None,
             decision: str | None = "approve", approved_sha: str | None = None,
             course_code: str | None = "cs66", superseded: bool = False,
             finished: bool = False, status: str = "downloaded") -> dict[str, str]:
        """ใส่แถวต้นทางหนึ่งแถวและ (ถ้าระบุ) การตัดสินใจหนึ่งแถว คืน id ทั้งสอง"""
        with psycopg.connect(args.database_url, autocommit=True, row_factory=dict_row) as conn, \
                conn.cursor() as cur:
            cur.execute("""
                INSERT INTO mko.crawl_sources
                    (source_url, page_title, status, needs_review, file_sha256, staging_path,
                     match_confidence, course_code, last_checked_at)
                VALUES (%s, 'หน้าหลักสูตร', %s, true, %s, %s, 'high', 'cs66', now())
                RETURNING id::text AS id
            """, (url, status, source_sha, staging_path))
            sid = cur.fetchone()["id"]
            did = None
            if decision is not None:
                cur.execute("""
                    INSERT INTO mko.crawl_decisions
                        (crawl_source_id, file_sha256, decision, decided_by, course_code,
                         course_title, superseded_at, superseded_by,
                         ingest_started_at, ingest_finished_at, document_id)
                    VALUES (%(sid)s, %(sha)s, %(dec)s, 'admin@test.local', %(code)s,
                            'ชื่อจากตอนอนุมัติ',
                            CASE WHEN %(sup)s THEN now() END,
                            CASE WHEN %(sup)s THEN 'admin@test.local' END,
                            CASE WHEN %(fin)s THEN now() END,
                            CASE WHEN %(fin)s THEN now() END,
                            NULL)
                    RETURNING id::text AS id
                """, {"sid": sid, "sha": approved_sha or source_sha, "dec": decision,
                      "code": course_code if decision == "approve" else None,
                      "sup": superseded, "fin": finished})
                did = cur.fetchone()["id"]
        return {"source": sid, "decision": did}

    def row(table: str, key: str) -> dict:
        with psycopg.connect(args.database_url, row_factory=dict_row) as conn, conn.cursor() as cur:
            cur.execute(f"SELECT * FROM mko.{table} WHERE id = %s", (key,))
            return cur.fetchone() or {}

    def counts() -> dict[str, int]:
        with psycopg.connect(args.database_url, row_factory=dict_row) as conn, conn.cursor() as cur:
            cur.execute("SELECT (SELECT count(*) FROM courses) AS courses,"
                        "       (SELECT count(*) FROM course_documents) AS documents,"
                        "       (SELECT count(*) FROM course_chunks) AS chunks")
            return dict(cur.fetchone())

    def work(max_jobs: int = 1) -> tuple[int, int]:
        return W.work(args.ingest_url, max_jobs)

    def safe(text: str | None) -> bool:
        """ข้อความผิดพลาดต้องไม่มีที่อยู่ไฟล์ในเครื่อง DSN หรือรหัสผ่าน"""
        if not text:
            return True
        bad = [str(staging), str(documents), str(outside), "/tmp", "C:\\", "postgresql://",
               args.ingest_url.split("@")[0], "Traceback"]
        return not any(b and b in text for b in bad)

    # =================================================================
    print("\n[1] ทางปกติ — อนุมัติแล้ว ไฟล์ถูก หลักสูตรมีอยู่")
    ids = reset()
    stage("aaa111_ok.pdf", PDF_A)
    k = seed(url="https://sci.pnru.ac.th/uploads/programs/ok.pdf",
             staging_path=str(staging / "aaa111_ok.pdf"), source_sha=sha(PDF_A))
    before = counts()
    ok, bad = work()
    d = row("crawl_decisions", k["decision"]); s = row("crawl_sources", k["source"])
    after = counts()
    c.check("ทำสำเร็จหนึ่งงาน", (ok, bad) == (1, 0), f"{ok}/{bad}")
    c.check("เรียก run() ของ pipeline เดิม", calls["run"] == 1, str(calls["run"]))
    c.check("คำนวณเวกเตอร์หนึ่งครั้ง", calls["embed"] == 1, str(calls["embed"]))
    c.check("ตั้ง document_id ในการตัดสินใจ", d.get("document_id") is not None)
    c.check("ตั้ง ingest_started_at", d.get("ingest_started_at") is not None)
    c.check("ตั้ง ingest_finished_at", d.get("ingest_finished_at") is not None)
    c.check("ล้าง ingest_error", d.get("ingest_error") is None, str(d.get("ingest_error")))
    c.check("ต้นทางเป็น ingested", s.get("status") == "ingested", str(s.get("status")))
    c.check("ต้นทางผูก document_id เดียวกัน",
            str(s.get("document_id")) == str(d.get("document_id")))
    c.check("เอกสารเพิ่มหนึ่งฉบับ", after["documents"] == before["documents"] + 1, str(after))
    c.check("มี chunk เข้าคลัง", after["chunks"] > before["chunks"], str(after))
    c.check("หลักสูตรไม่เพิ่ม", after["courses"] == before["courses"], str(after))
    published = sorted(p.name for p in documents.iterdir() if p.is_file())
    c.check("วางไฟล์ไว้ในที่เก็บเอกสาร", published == ["aaa111_ok.pdf"], str(published))
    c.check("ไฟล์ใน staging ยังอยู่ ไม่ถูกย้าย", (staging / "aaa111_ok.pdf").is_file())
    c.check("ไฟล์ที่วางมีเนื้อตรงกับต้นฉบับ",
            (documents / "aaa111_ok.pdf").read_bytes() == PDF_A if published else False)

    print("\n[1b] เรียกซ้ำหลังสำเร็จ")
    ok2, bad2 = work()
    c.check("ไม่มีงานให้ทำแล้ว", (ok2, bad2) == (0, 0), f"{ok2}/{bad2}")
    c.check("ไม่เรียก run() ซ้ำ", calls["run"] == 1, str(calls["run"]))
    c.check("ไม่คำนวณเวกเตอร์ซ้ำ", calls["embed"] == 1, str(calls["embed"]))
    c.check("จำนวนเอกสาร/chunk ไม่เพิ่ม", counts() == after, str(counts()))

    # =================================================================
    print("\n[2] งานที่ต้องไม่ถูกนำเข้า")
    for label, kw in [
        ("ไม่มีการอนุมัติเลย", {"decision": None}),
        ("เป็น ignore", {"decision": "ignore"}),
        ("ถูกถอนไปแล้ว", {"superseded": True}),
        ("ทำเสร็จไปแล้ว", {"finished": True}),
    ]:
        ids = reset()
        stage("bbb222_x.pdf", PDF_A)
        seed(url=f"https://sci.pnru.ac.th/uploads/programs/{label}.pdf",
             staging_path=str(staging / "bbb222_x.pdf"), source_sha=sha(PDF_A), **kw)
        base = counts()
        ok, bad = work()
        c.check(f"{label}: ไม่ยึดงาน", (ok, bad) == (0, 0), f"{ok}/{bad}")
        c.check(f"{label}: ไม่เรียก run()", calls["run"] == 0, str(calls["run"]))
        c.check(f"{label}: ไม่คำนวณเวกเตอร์", calls["embed"] == 0, str(calls["embed"]))
        c.check(f"{label}: คลังความรู้ไม่เปลี่ยน", counts() == base, str(counts()))
        c.check(f"{label}: ไม่วางไฟล์ในที่เก็บ",
                not [p for p in documents.iterdir() if p.is_file()])

    # =================================================================
    print("\n[3] ซ้ำ — sha เดิม ข้ามต้นทาง และข้ามหลักสูตร")
    ids = reset()
    stage("ccc333_one.pdf", PDF_A)
    stage("ccc333_two.pdf", PDF_A)          # เนื้อเดียวกัน คนละไฟล์
    k1 = seed(url="https://sci.pnru.ac.th/uploads/programs/one.pdf",
              staging_path=str(staging / "ccc333_one.pdf"), source_sha=sha(PDF_A))
    k2 = seed(url="https://sci.pnru.ac.th/uploads/programs/two.pdf",
              staging_path=str(staging / "ccc333_two.pdf"), source_sha=sha(PDF_A))
    ok, bad = work(max_jobs=2)
    c.check("sha เดียวกันสองต้นทาง หลักสูตรเดียวกัน: สำเร็จทั้งสอง", (ok, bad) == (2, 0), f"{ok}/{bad}")
    c.check("คำนวณเวกเตอร์ครั้งเดียว (ตัวที่สองถูกกันด้วย sha)", calls["embed"] == 1, str(calls["embed"]))
    st = counts()
    c.check("มีเอกสารฉบับเดียว", st["documents"] == 1, str(st))
    d1, d2 = row("crawl_decisions", k1["decision"]), row("crawl_decisions", k2["decision"])
    c.check("ทั้งสองการตัดสินใจผูกเอกสารฉบับเดียวกัน",
            d1.get("document_id") is not None and d1["document_id"] == d2.get("document_id"))

    ids = reset()
    stage("ddd444_conflict.pdf", PDF_A)
    with psycopg.connect(args.database_url, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO course_documents (course_id, original_filename, file_sha256,"
                    " storage_path, page_count, extraction_status) VALUES"
                    " ((SELECT id FROM courses WHERE code='ma69'), 'other.pdf', %s, 'x', 2, 'done')",
                    (sha(PDF_A),))
    k = seed(url="https://sci.pnru.ac.th/uploads/programs/conflict.pdf",
             staging_path=str(staging / "ddd444_conflict.pdf"), source_sha=sha(PDF_A),
             course_code="cs66")
    ok, bad = work()
    d = row("crawl_decisions", k["decision"]); s = row("crawl_sources", k["source"])
    c.check("sha เดิมอยู่คนละหลักสูตร: เป็นงานล้มเหลว", (ok, bad) == (0, 1), f"{ok}/{bad}")
    c.check("บันทึกว่าเป็นความขัดแย้งของหลักสูตร",
            "document_course_conflict" in (d.get("ingest_error") or ""), str(d.get("ingest_error")))
    c.check("ไม่ปิดงาน", d.get("ingest_finished_at") is None)
    c.check("ต้นทางไม่เป็น ingested", s.get("status") != "ingested", str(s.get("status")))
    c.check("ข้อความผิดพลาดปลอดภัย", safe(d.get("ingest_error")))

    ids = reset()
    stage("eee555_dup.pdf", PDF_A)
    k = seed(url="https://sci.pnru.ac.th/uploads/programs/dup.pdf",
             staging_path=str(staging / "eee555_dup.pdf"), source_sha=sha(PDF_A))
    try:
        with psycopg.connect(args.database_url, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO mko.crawl_decisions (crawl_source_id, file_sha256, decision,"
                        " decided_by, course_code) VALUES (%s, %s, 'approve', 'b@t', 'cs66')",
                        (k["source"], sha(PDF_A)))
        c.check("ดัชนีกันการอนุมัติซ้ำที่ยังใช้อยู่", False, "ฐานข้อมูลยอมรับสองแถว")
    except psycopg.errors.UniqueViolation:
        c.check("ดัชนีกันการอนุมัติซ้ำที่ยังใช้อยู่", True)

    # =================================================================
    print("\n[4] ยึดงานพร้อมกันสองตัว")
    ids = reset()
    stage("fff666_a.pdf", PDF_A); stage("fff666_b.pdf", PDF_B)
    ka = seed(url="https://sci.pnru.ac.th/uploads/programs/a.pdf",
              staging_path=str(staging / "fff666_a.pdf"), source_sha=sha(PDF_A))
    kb = seed(url="https://sci.pnru.ac.th/uploads/programs/b.pdf",
              staging_path=str(staging / "fff666_b.pdf"), source_sha=sha(PDF_B))
    w1 = psycopg.connect(args.ingest_url, row_factory=dict_row)
    w2 = psycopg.connect(args.ingest_url, row_factory=dict_row)
    w3 = psycopg.connect(args.ingest_url, row_factory=dict_row)
    try:
        for conn in (w1, w2, w3):
            with conn.cursor() as cur:
                cur.execute("SET lock_timeout = '2s'")
        j1 = W.claim(w1, [])
        j2 = W.claim(w2, [])
        c.check("สองตัวยึดได้คนละงาน", j1 and j2 and j1.decision_id != j2.decision_id,
                f"{j1 and j1.decision_id} / {j2 and j2.decision_id}")
        j3 = W.claim(w3, [])
        c.check("ตัวที่สามไม่ได้งาน เพราะทั้งสองแถวถูกล็อกอยู่", j3 is None, str(j3))
        c.check("งานที่ยึดได้ครอบทั้งสองแถว",
                {j1.decision_id, j2.decision_id} == {ka["decision"], kb["decision"]})

        # คำสั่งถอนของ backend ต้องถูกบล็อกที่แถวเดียวกัน
        blocked = False
        with psycopg.connect(args.api_url or args.database_url) as api, api.cursor() as cur:
            cur.execute("SET lock_timeout = '800ms'")
            try:
                cur.execute("""UPDATE mko.crawl_decisions
                                  SET superseded_at = now(), superseded_by = 'admin@test.local'
                                WHERE id = %s AND superseded_at IS NULL
                                  AND ingest_finished_at IS NULL""", (j1.decision_id,))
            except (psycopg.errors.LockNotAvailable, psycopg.errors.QueryCanceled):
                blocked = True
            api.rollback()
        c.check("คำสั่งถอนถูกบล็อกตลอดที่ worker ถืองานอยู่", blocked,
                "คำสั่งถอนผ่านไปได้ทั้งที่ worker ยังทำงาน")
    finally:
        w1.rollback(); w2.rollback(); w3.rollback()
        w1.close(); w2.close(); w3.close()

    with psycopg.connect(args.ingest_url, row_factory=dict_row) as after_release:
        with after_release.cursor() as cur:
            cur.execute("SET lock_timeout = '2s'")
        j = W.claim(after_release, [])
        c.check("ปล่อย lock แล้วยึดงานได้อีก", j is not None)
        after_release.rollback()
    c.check("ยกเลิก transaction แล้วไม่มี claim ค้าง",
            row("crawl_decisions", ka["decision"]).get("ingest_started_at") is None)

    # =================================================================
    print("\n[5] แข่งกับการถอนและกับ crawler")
    ids = reset()
    stage("ggg777_race.pdf", PDF_A)
    k = seed(url="https://sci.pnru.ac.th/uploads/programs/race.pdf",
             staging_path=str(staging / "ggg777_race.pdf"), source_sha=sha(PDF_A))
    # crawler เปลี่ยน sha ของต้นทางหลัง worker ยึดงาน
    conn = psycopg.connect(args.ingest_url, row_factory=dict_row)
    try:
        job = W.claim(conn, [])
        with psycopg.connect(args.database_url, autocommit=True) as other, other.cursor() as cur:
            cur.execute("UPDATE mko.crawl_sources SET file_sha256 = %s WHERE id = %s",
                        (sha(PDF_B), k["source"]))
        with psycopg.connect(args.database_url, autocommit=True) as other, other.cursor() as cur:
            cur.execute("INSERT INTO course_documents (course_id, original_filename, file_sha256,"
                        " storage_path, page_count, extraction_status) VALUES"
                        " ((SELECT id FROM courses WHERE code='cs66'), 'race.pdf', %s, 'x', 2, 'done')"
                        " RETURNING id::text", (sha(PDF_A),))
            doc_id = cur.fetchone()[0]
        note = W.finalize(conn, job, doc_id)
        conn.commit()
    finally:
        conn.close()
    d = row("crawl_decisions", k["decision"]); s = row("crawl_sources", k["source"])
    c.check("ต้นทางเปลี่ยนไฟล์แล้ว: ไม่ตั้ง ingested ให้ของใหม่",
            s.get("status") != "ingested", str(s.get("status")))
    c.check("ต้นทางเปลี่ยนไฟล์แล้ว: ไม่ผูก document_id ให้ต้นทาง", s.get("document_id") is None)
    c.check("ปิดการตัดสินใจไว้ ไม่ให้ทำซ้ำ", d.get("ingest_finished_at") is not None)
    c.check("ทำเครื่องหมายให้คนมาดู",
            d.get("ingest_error") == "source_sha_changed_after_ingest", str(d.get("ingest_error")))
    c.check("ข้อความที่บันทึกปลอดภัย", safe(d.get("ingest_error")))

    # =================================================================
    print("\n[6] ความปลอดภัยของที่อยู่ไฟล์")
    junction_made = False
    for label, mk in [
        ("ไม่มีไฟล์", lambda: str(staging / "not_here.pdf")),
        ("เป็นโฟลเดอร์", lambda: str((staging / "adir").mkdir(exist_ok=True) or (staging / "adir"))),
        ("ออกนอกด้วย ..", lambda: str(staging / ".." / outside.name / "x.pdf")),
        ("absolute นอก root", lambda: str(outside / "x.pdf")),
        ("โฟลเดอร์ข้างเคียงชื่อขึ้นต้นเหมือนกัน", lambda: str(Path(str(staging) + "-sibling") / "x.pdf")),
        ("ที่อยู่ว่าง", lambda: None),
    ]:
        ids = reset()
        (outside / "x.pdf").write_bytes(PDF_A)
        Path(str(staging) + "-sibling").mkdir(exist_ok=True)
        (Path(str(staging) + "-sibling") / "x.pdf").write_bytes(PDF_A)
        k = seed(url=f"https://sci.pnru.ac.th/uploads/programs/p-{label}.pdf",
                 staging_path=mk(), source_sha=sha(PDF_A))
        base = counts()
        ok, bad = work()
        d = row("crawl_decisions", k["decision"])
        c.check(f"{label}: เป็นงานล้มเหลว", (ok, bad) == (0, 1), f"{ok}/{bad}")
        c.check(f"{label}: ไม่เรียก run()", calls["run"] == 0, str(calls["run"]))
        c.check(f"{label}: คลังไม่เปลี่ยน", counts() == base)
        c.check(f"{label}: ข้อความผิดพลาดปลอดภัย", safe(d.get("ingest_error")),
                str(d.get("ingest_error")))

    ids = reset()
    os.environ["CRAWL_STAGING_DIR"] = ""
    stage("hhh888_noroot.pdf", PDF_A)
    k = seed(url="https://sci.pnru.ac.th/uploads/programs/noroot.pdf",
             staging_path=str(staging / "hhh888_noroot.pdf"), source_sha=sha(PDF_A))
    ok, bad = work()
    d = row("crawl_decisions", k["decision"])
    c.check("ไม่ตั้ง CRAWL_STAGING_DIR: ล้มเหลวแบบปิดประตู", (ok, bad) == (0, 1), f"{ok}/{bad}")
    c.check("ไม่ตั้ง CRAWL_STAGING_DIR: บอกสาเหตุ",
            "staging_dir_unset" in (d.get("ingest_error") or ""), str(d.get("ingest_error")))
    os.environ["CRAWL_STAGING_DIR"] = str(staging)

    # ทางเชื่อมที่ชี้ออกนอก root
    ids = reset()
    (outside / "secret.pdf").write_bytes(PDF_B)
    link = staging / "iii999_link.pdf"
    try:
        link.symlink_to(outside / "secret.pdf")
        junction_made = True
        kind = "symlink"
    except (OSError, NotImplementedError):
        j = staging / "jjj_escape"
        r = subprocess.run(["cmd", "/c", "mklink", "/J", str(j), str(outside)], capture_output=True)
        if r.returncode == 0:
            link = j / "secret.pdf"
            junction_made = True
            kind = "junction ของโฟลเดอร์"
    if junction_made:
        k = seed(url="https://sci.pnru.ac.th/uploads/programs/link.pdf",
                 staging_path=str(link), source_sha=sha(PDF_B))
        base = counts()
        ok, bad = work()
        d = row("crawl_decisions", k["decision"])
        c.check(f"{kind} ชี้ออกนอก root: ล้มเหลว", (ok, bad) == (0, 1), f"{ok}/{bad}")
        c.check(f"{kind}: บอกว่าออกนอกโฟลเดอร์",
                "path_outside_staging_root" in (d.get("ingest_error") or ""), str(d.get("ingest_error")))
        c.check(f"{kind}: คลังไม่เปลี่ยน", counts() == base)
    else:
        c.skip("ทางเชื่อมที่ชี้ออกนอก root", "ระบบนี้สร้างทั้ง symlink และ junction ไม่ได้")

    # ไฟล์ถูกสลับหลังตรวจ — สำเนาส่วนตัวต้องทำให้ run() ได้ของที่ตรวจแล้ว
    ids = reset()
    target = stage("kkk000_swap.pdf", PDF_A)
    k = seed(url="https://sci.pnru.ac.th/uploads/programs/swap.pdf",
             staging_path=str(target), source_sha=sha(PDF_A))
    original_validate = W.validate_pdf

    def validate_then_swap(path, approved, source_sha):
        pages = original_validate(path, approved, source_sha)
        target.write_bytes(PDF_B)          # สลับไฟล์ทันทีหลังตรวจผ่าน
        return pages

    W.validate_pdf = validate_then_swap
    ok, bad = work()
    W.validate_pdf = original_validate
    d = row("crawl_decisions", k["decision"])
    with psycopg.connect(args.database_url, row_factory=dict_row) as conn, conn.cursor() as cur:
        cur.execute("SELECT file_sha256, original_filename FROM course_documents")
        docs = cur.fetchall()
    c.check("ไฟล์ถูกสลับหลังตรวจ: ยังสำเร็จด้วยเนื้อที่ตรวจแล้ว", (ok, bad) == (1, 0), f"{ok}/{bad}")
    c.check("เอกสารที่เข้าคลังคือ sha ที่อนุมัติ ไม่ใช่ไฟล์ที่ถูกสลับมา",
            len(docs) == 1 and docs[0]["file_sha256"] == sha(PDF_A),
            str([r["file_sha256"][:12] for r in docs]))
    c.check("ชื่อไฟล์เดิมถูกรักษาไว้",
            docs and docs[0]["original_filename"] == "kkk000_swap.pdf",
            str(docs and docs[0]["original_filename"]))

    # =================================================================
    print("\n[7] ลายนิ้วมือและรูปแบบไฟล์")
    for label, body, src_sha, app_sha, expect in [
        ("sha ไม่ตรงกับที่อนุมัติ", PDF_A, sha(PDF_A), sha(PDF_B), "sha_mismatch_decision"),
        ("sha ไม่ตรงกับต้นทาง", PDF_A, sha(PDF_B), sha(PDF_A), "sha_mismatch_source"),
        ("ไม่ใช่ PDF", NOT_PDF, sha(NOT_PDF), sha(NOT_PDF), "pdf_invalid"),
        ("ขึ้นต้น %PDF- แต่เนื้อเสีย", FAKE_PDF, sha(FAKE_PDF), sha(FAKE_PDF), "pdf_"),
    ]:
        ids = reset()
        stage("lll111_f.pdf", body)
        k = seed(url=f"https://sci.pnru.ac.th/uploads/programs/f-{label}.pdf",
                 staging_path=str(staging / "lll111_f.pdf"),
                 source_sha=src_sha, approved_sha=app_sha)
        base = counts()
        ok, bad = work()
        d = row("crawl_decisions", k["decision"])
        c.check(f"{label}: เป็นงานล้มเหลว", (ok, bad) == (0, 1), f"{ok}/{bad}")
        c.check(f"{label}: บอกสาเหตุถูก", expect in (d.get("ingest_error") or ""),
                str(d.get("ingest_error")))
        c.check(f"{label}: ไม่เรียก run()", calls["run"] == 0, str(calls["run"]))
        c.check(f"{label}: คลังไม่เปลี่ยน", counts() == base)
        c.check(f"{label}: ข้อความปลอดภัย", safe(d.get("ingest_error")))

    # =================================================================
    print("\n[8] หลักสูตรต้องมีอยู่จริง")
    for label, code in [("รหัสที่ไม่มีในระบบ", "zz99"), ("หลักสูตรถูกลบไปแล้ว", "gone")]:
        ids = reset()
        stage("mmm222_c.pdf", PDF_A)
        if code == "gone":
            with psycopg.connect(args.database_url, autocommit=True) as conn, conn.cursor() as cur:
                cur.execute("INSERT INTO courses (code, title) VALUES ('gone','จะถูกลบ')")
        k = seed(url=f"https://sci.pnru.ac.th/uploads/programs/c-{label}.pdf",
                 staging_path=str(staging / "mmm222_c.pdf"), source_sha=sha(PDF_A),
                 course_code=code)
        if code == "gone":
            with psycopg.connect(args.database_url, autocommit=True) as conn, conn.cursor() as cur:
                cur.execute("DELETE FROM courses WHERE code = 'gone'")
        base = counts()
        ok, bad = work()
        d = row("crawl_decisions", k["decision"])
        c.check(f"{label}: เป็นงานล้มเหลว", (ok, bad) == (0, 1), f"{ok}/{bad}")
        c.check(f"{label}: บอกว่าไม่พบหลักสูตร",
                "course_not_found" in (d.get("ingest_error") or ""), str(d.get("ingest_error")))
        c.check(f"{label}: ไม่สร้างหลักสูตรใหม่", counts()["courses"] == base["courses"],
                f'{counts()["courses"]} != {base["courses"]}')
        c.check(f"{label}: ไม่เรียก run()", calls["run"] == 0, str(calls["run"]))

    # หลักสูตรถูกตรึงไว้ระหว่างงาน ลบไม่ได้จนงานจบ
    ids = reset()
    stage("nnn333_lock.pdf", PDF_A)
    seed(url="https://sci.pnru.ac.th/uploads/programs/lock.pdf",
         staging_path=str(staging / "nnn333_lock.pdf"), source_sha=sha(PDF_A))
    conn = psycopg.connect(args.ingest_url, row_factory=dict_row)
    try:
        job = W.claim(conn, [])
        W.lock_existing_course(conn, "cs66")
        deleting_blocked = False
        with psycopg.connect(args.database_url) as other, other.cursor() as cur:
            cur.execute("SET lock_timeout = '800ms'")
            try:
                cur.execute("DELETE FROM courses WHERE code = 'cs66'")
            except (psycopg.errors.LockNotAvailable, psycopg.errors.QueryCanceled):
                deleting_blocked = True
            other.rollback()
        c.check("ตรึงหลักสูตรไว้แล้วลบไม่ได้จนงานจบ", deleting_blocked,
                "ลบหลักสูตรได้ทั้งที่ worker กำลังใช้")
    finally:
        conn.rollback(); conn.close()

    # =================================================================
    print("\n[9] สัญญาของ embedding")
    for label, setup, expect in [
        ("EMBED_MODEL ผิด", lambda: os.environ.__setitem__("EMBED_MODEL", "nomic-embed-text"),
         "embed_model_mismatch"),
        ("EMBED_MODEL ไม่ได้ตั้ง", lambda: os.environ.pop("EMBED_MODEL", None), "embed_model_mismatch"),
        ("EMBED_DIM ผิด", lambda: os.environ.__setitem__("EMBED_DIM", "768"), "embed_dim_mismatch"),
        ("โมเดลคืนเวกเตอร์ผิดมิติ", lambda: setattr(FakeConnector, "dim", 768), "embed_probe_mismatch"),
    ]:
        ids = reset()
        stage("ooo444_e.pdf", PDF_A)
        k = seed(url=f"https://sci.pnru.ac.th/uploads/programs/e-{label}.pdf",
                 staging_path=str(staging / "ooo444_e.pdf"), source_sha=sha(PDF_A))
        setup()
        base = counts()
        ok, bad = work()
        d = row("crawl_decisions", k["decision"])
        c.check(f"{label}: เป็นงานล้มเหลว", (ok, bad) == (0, 1), f"{ok}/{bad}")
        c.check(f"{label}: บอกสาเหตุถูก", expect in (d.get("ingest_error") or ""),
                str(d.get("ingest_error")))
        c.check(f"{label}: ไม่เรียก run() และไม่ embed",
                calls["run"] == 0 and calls["embed"] == 0, f'{calls["run"]}/{calls["embed"]}')
        c.check(f"{label}: คลังไม่เปลี่ยน", counts() == base)

    # =================================================================
    print("\n[10] run() ล้มเหลวแบบต่าง ๆ")
    for label, boom, expect in [
        ("run โยน exception", RuntimeError("พังกลางทาง"), "ingest_failed"),
        ("run โยน SystemExit(0)", SystemExit(0), "ingest_systemexit"),
        ("run โยน SystemExit(2)", SystemExit(2), "ingest_systemexit"),
    ]:
        ids = reset()
        stage("ppp555_b.pdf", PDF_A)
        k = seed(url=f"https://sci.pnru.ac.th/uploads/programs/b-{label}.pdf",
                 staging_path=str(staging / "ppp555_b.pdf"), source_sha=sha(PDF_A))

        def exploding(*a, **kw):
            calls["run"] += 1
            raise boom

        ingest_mod.run = exploding
        base = counts()
        ok, bad = work()
        ingest_mod.run = counted_run
        d = row("crawl_decisions", k["decision"]); s = row("crawl_sources", k["source"])
        c.check(f"{label}: เป็นงานล้มเหลว ไม่ทำให้โปรเซสตาย", (ok, bad) == (0, 1), f"{ok}/{bad}")
        c.check(f"{label}: บันทึกสาเหตุ", expect in (d.get("ingest_error") or ""),
                str(d.get("ingest_error")))
        c.check(f"{label}: ไม่ปิดงาน", d.get("ingest_finished_at") is None)
        c.check(f"{label}: ต้นทางไม่เป็น ingested", s.get("status") != "ingested")
        c.check(f"{label}: คลังไม่เปลี่ยน", counts() == base)
        c.check(f"{label}: ข้อความปลอดภัย", safe(d.get("ingest_error")))

    # =================================================================
    print("\n[11] run() ไม่พัง แต่หลักฐานไม่ครบ")
    for label, faker, expect in [
        ("ไม่มีเอกสารเลย", lambda *a, **kw: None, "document_not_found"),
        ("extraction ยังไม่เสร็จ", "pending", "document_not_done"),
    ]:
        ids = reset()
        stage("qqq666_n.pdf", PDF_A)
        k = seed(url=f"https://sci.pnru.ac.th/uploads/programs/n-{label}.pdf",
                 staging_path=str(staging / "qqq666_n.pdf"), source_sha=sha(PDF_A))
        if faker == "pending":
            def half_done(pdf_path, title, course_code, provider):
                calls["run"] += 1
                with psycopg.connect(args.database_url, autocommit=True) as conn, conn.cursor() as cur:
                    cur.execute("INSERT INTO course_documents (course_id, original_filename,"
                                " file_sha256, storage_path, page_count, extraction_status)"
                                " VALUES ((SELECT id FROM courses WHERE code=%s), 'n.pdf', %s,"
                                " 'x', 2, 'processing')", (course_code, sha(PDF_A)))
            ingest_mod.run = half_done
        else:
            ingest_mod.run = lambda *a, **kw: calls.__setitem__("run", calls["run"] + 1)
        base = counts()
        ok, bad = work()
        ingest_mod.run = counted_run
        d = row("crawl_decisions", k["decision"]); s = row("crawl_sources", k["source"])
        c.check(f"{label}: ไม่ปิดงาน", (ok, bad) == (0, 1) and d.get("ingest_finished_at") is None,
                f"{ok}/{bad}")
        c.check(f"{label}: บอกสาเหตุถูก", expect in (d.get("ingest_error") or ""),
                str(d.get("ingest_error")))
        c.check(f"{label}: ต้นทางไม่เป็น ingested", s.get("status") != "ingested")
        c.check(f"{label}: ไม่ผูก document_id", d.get("document_id") is None)

    # =================================================================
    print("\n[12] ลองใหม่หลังล้มเหลว และกู้หลังล้มกลางทาง")
    ids = reset()
    stage("rrr777_retry.pdf", PDF_A)
    k = seed(url="https://sci.pnru.ac.th/uploads/programs/retry.pdf",
             staging_path=str(staging / "rrr777_retry.pdf"), source_sha=sha(PDF_A))
    ingest_mod.run = lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("รอบแรกพัง"))
    work()
    d1 = row("crawl_decisions", k["decision"])
    c.check("รอบแรกล้มเหลวและบันทึกไว้", d1.get("ingest_error") is not None)
    ingest_mod.run = counted_run
    ok, bad = work()
    d2 = row("crawl_decisions", k["decision"]); s2 = row("crawl_sources", k["source"])
    c.check("ลองใหม่แล้วสำเร็จ", (ok, bad) == (1, 0), f"{ok}/{bad}")
    c.check("ล้างข้อความผิดพลาดเมื่อสำเร็จ", d2.get("ingest_error") is None, str(d2.get("ingest_error")))
    c.check("ปิดงานและตั้งต้นทางเป็น ingested",
            d2.get("ingest_finished_at") is not None and s2.get("status") == "ingested")

    # ล้มหลัง run() commit แล้วแต่ก่อนปิดงาน — รอบถัดไปต้องกู้เองโดยไม่ embed ซ้ำ
    ids = reset()
    stage("sss888_crash.pdf", PDF_A)
    k = seed(url="https://sci.pnru.ac.th/uploads/programs/crash.pdf",
             staging_path=str(staging / "sss888_crash.pdf"), source_sha=sha(PDF_A))
    original_finalize = W.finalize
    W.finalize = lambda *a, **kw: (_ for _ in ()).throw(W.JobError("crash_before_finalize"))
    ok, bad = work()
    W.finalize = original_finalize
    d = row("crawl_decisions", k["decision"])
    mid = counts()
    c.check("ล้มก่อนปิดงาน: งานล้มเหลวแต่เอกสารเข้าคลังไปแล้ว",
            (ok, bad) == (0, 1) and mid["documents"] == 1, f'{ok}/{bad} {mid}')
    c.check("ล้มก่อนปิดงาน: ยังไม่ผูก document_id", d.get("document_id") is None)
    embeds_before = calls["embed"]
    ok, bad = work()
    d = row("crawl_decisions", k["decision"]); s = row("crawl_sources", k["source"])
    c.check("รอบถัดไปกู้งานได้เอง", (ok, bad) == (1, 0), f"{ok}/{bad}")
    c.check("กู้แล้วไม่คำนวณเวกเตอร์ซ้ำ", calls["embed"] == embeds_before, str(calls["embed"]))
    c.check("กู้แล้วไม่เพิ่มเอกสาร", counts()["documents"] == mid["documents"], str(counts()))
    c.check("กู้แล้วไม่เพิ่ม chunk", counts()["chunks"] == mid["chunks"], str(counts()))
    c.check("กู้แล้วปิดงานครบ",
            d.get("ingest_finished_at") is not None and s.get("status") == "ingested")

    # =================================================================
    print("\n[13] ที่เก็บเอกสาร")
    ids = reset()
    stage("ttt999_pub.pdf", PDF_A)
    (documents / "already_there.pdf").write_bytes(PDF_A)      # เนื้อเดียวกัน ชื่อต่าง
    k = seed(url="https://sci.pnru.ac.th/uploads/programs/pub.pdf",
             staging_path=str(staging / "ttt999_pub.pdf"), source_sha=sha(PDF_A))
    ok, bad = work()
    files = sorted(p.name for p in documents.iterdir() if p.is_file())
    c.check("มีไฟล์เนื้อเดียวกันอยู่แล้ว: ใช้ของเดิม ไม่เขียนเพิ่ม",
            (ok, bad) == (1, 0) and files == ["already_there.pdf"], f"{ok}/{bad} {files}")

    ids = reset()
    stage("uuu000_col.pdf", PDF_A)
    (documents / "uuu000_col.pdf").write_bytes(PDF_B)          # ชื่อซ้ำ เนื้อต่าง
    k = seed(url="https://sci.pnru.ac.th/uploads/programs/col.pdf",
             staging_path=str(staging / "uuu000_col.pdf"), source_sha=sha(PDF_A))
    ok, bad = work()
    files = sorted(p.name for p in documents.iterdir() if p.is_file())
    c.check("ชื่อซ้ำเนื้อต่าง: ไม่เขียนทับ ใช้ชื่อใหม่", (ok, bad) == (1, 0) and len(files) == 2,
            f"{ok}/{bad} {files}")
    c.check("ไฟล์เดิมยังเป็นเนื้อเดิม",
            (documents / "uuu000_col.pdf").read_bytes() == PDF_B)

    ids = reset()
    stage("vvv111_fail.pdf", PDF_A)
    k = seed(url="https://sci.pnru.ac.th/uploads/programs/failpub.pdf",
             staging_path=str(staging / "vvv111_fail.pdf"), source_sha=sha(PDF_A))
    os.environ["DOCUMENTS_DIR"] = ""
    ok, bad = work()
    d = row("crawl_decisions", k["decision"]); s = row("crawl_sources", k["source"])
    os.environ["DOCUMENTS_DIR"] = str(documents)
    c.check("ไม่ตั้ง DOCUMENTS_DIR: ไม่ปิดงาน", (ok, bad) == (0, 1), f"{ok}/{bad}")
    c.check("ไม่ตั้ง DOCUMENTS_DIR: บอกสาเหตุ",
            "documents_dir_unset" in (d.get("ingest_error") or ""), str(d.get("ingest_error")))
    c.check("ไม่ตั้ง DOCUMENTS_DIR: ต้นทางไม่เป็น ingested", s.get("status") != "ingested")
    embeds_before = calls["embed"]
    ok, bad = work()
    c.check("ลองวางไฟล์ใหม่แล้วสำเร็จโดยไม่ embed ซ้ำ",
            (ok, bad) == (1, 0) and calls["embed"] == embeds_before,
            f'{ok}/{bad} embed={calls["embed"]} (เดิม {embeds_before})')

    # =================================================================
    print("\n[14] สิทธิ์ของ role")
    if not args.api_url:
        c.skip("role ของ backend เขียนคลังความรู้ไม่ได้", "ไม่ได้ระบุ --api-url")
    else:
        with psycopg.connect(args.api_url) as api:
            for label, sql in [
                ("เพิ่ม course_documents ไม่ได้",
                 "INSERT INTO course_documents (course_id, original_filename, file_sha256,"
                 " storage_path) VALUES (gen_random_uuid(),'x','y','z')"),
                ("แก้ course_documents ไม่ได้", "UPDATE course_documents SET page_count = 1"),
                ("เพิ่ม course_chunks ไม่ได้",
                 "INSERT INTO course_chunks (course_id, document_id, chunk_index, content, embedding)"
                 " VALUES (gen_random_uuid(), gen_random_uuid(), 0, 'x', array_fill(0::real,"
                 " ARRAY[1024])::vector)"),
                ("ลบ course_chunks ไม่ได้", "DELETE FROM course_chunks WHERE true"),
                ("แก้ ingest_finished_at ไม่ได้",
                 "UPDATE mko.crawl_decisions SET ingest_finished_at = now()"),
                ("แก้ crawl_sources ไม่ได้", "UPDATE mko.crawl_sources SET status = 'ingested'"),
            ]:
                try:
                    with api.cursor() as cur:
                        cur.execute(sql)
                    api.rollback()
                    c.check(f"role backend: {label}", False, "ทำได้ ซึ่งไม่ควรทำได้")
                except psycopg.errors.InsufficientPrivilege:
                    api.rollback()
                    c.check(f"role backend: {label}", True)
                except psycopg.errors.Error as e:
                    api.rollback()
                    c.check(f"role backend: {label}", False, f"ถูกปฏิเสธด้วยเหตุอื่น: {type(e).__name__}")

    # ---- เก็บของ --------------------------------------------------------
    for d_ in (staging, documents, outside, Path(str(staging) + "-sibling")):
        try:
            for p in sorted(d_.rglob("*"), reverse=True):
                if p.is_file() or p.is_symlink():
                    p.unlink(missing_ok=True)
            for p in sorted(d_.rglob("*"), reverse=True):
                if p.is_dir():
                    p.rmdir()
            d_.rmdir()
        except OSError:
            pass
    sys.exit(0 if c.report() else 1)


class Checks:
    def __init__(self) -> None:
        self.passed: list[str] = []
        self.failed: list[tuple[str, str]] = []
        self.skipped: list[str] = []

    def check(self, name: str, ok: bool, detail: str = "") -> None:
        (self.passed.append(name) if ok else self.failed.append((name, detail)))
        print(f"  {'ผ่าน  ' if ok else 'ไม่ผ่าน'} {name}" + (f"  — {detail}" if detail and not ok else ""))

    def skip(self, name: str, why: str) -> None:
        self.skipped.append(name)
        print(f"  ข้าม   {name}  — {why}")

    def report(self) -> bool:
        print(f"\n---- สรุป ----\n  ผ่าน {len(self.passed)} · ไม่ผ่าน {len(self.failed)}"
              f" · ข้าม {len(self.skipped)}")
        for n, d in self.failed:
            print(f"  ไม่ผ่าน: {n} — {d}")
        return not self.failed


if __name__ == "__main__":
    main()
