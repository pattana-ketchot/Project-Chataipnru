"""
ทดสอบคิวตรวจและการอนุมัติไฟล์จาก crawler (Phase 3A)

    python eval/crawl_approval_check.py --database-url postgresql://... [--api-url postgresql://...]

--database-url  ต่อด้วย role ที่เขียนได้ ใช้เตรียมข้อมูลและตรวจผลในฐานข้อมูล
--api-url       ต่อด้วย role ที่มีสิทธิ์เท่ากับ advisor_api ใช้รัน API จริง
                ถ้าไม่ระบุ API จะใช้ connection เดียวกับข้างบน และข้อทดสอบเรื่องสิทธิ์
                จะถูกข้ามพร้อมแจ้งให้ทราบ

ทดสอบกับฐานข้อมูลจริง ไม่ใช่ของปลอม
-----------------------------------
สิ่งที่ต้องพิสูจน์คือ CHECK constraint, partial unique index ที่กันสองคนกดพร้อมกัน,
column-level GRANT และวิว v_crawl_queue ซึ่งของปลอมพิสูจน์แทนไม่ได้เลย
ต้องเป็น PostgreSQL ที่ลง migration 003 และ 004 แล้ว

⚠️ ต้องชี้ไปที่ฐานข้อมูลทดสอบเท่านั้น สคริปต์นี้ลบและเขียนข้อมูลในตาราง users,
   courses, course_documents, mko.crawl_sources, mko.crawl_decisions
   มีด่านกันไว้ไม่ให้เผลอรันใส่ course_advisor

ทดสอบ API ผ่าน router จริง
-------------------------
ประกอบ FastAPI ขึ้นมาใหม่แล้ว include_router ตัวจริงจาก
backend/app/api/routes/crawl_review.py ไม่ได้ import app.main ทั้งก้อน เพราะ lifespan
ของ main จะเปิดงาน warmup ที่ยิงหา Ollama ซึ่งไม่เกี่ยวกับสิ่งที่ทดสอบและทำให้เทสต์ช้า
ตัว auth, require_admin, JWT และ session ฐานข้อมูลเป็นของจริงทั้งหมด
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
import tempfile
import uuid
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for p in (str(_ROOT), str(_ROOT / "backend")):
    if p not in sys.path:
        sys.path.insert(0, p)


def sqlalchemy_url(url: str) -> str:
    """บังคับ driver psycopg3 ให้ SQLAlchemy

    SQLAlchemy เลือก psycopg2 เป็นค่าเริ่มต้นสำหรับ postgresql:// ซึ่งโปรเจคนี้ไม่ได้ลง
    (ดู backend/requirements.txt ที่ใช้ psycopg[binary]) ส่วน psycopg.connect() รับ
    postgresql+psycopg:// ไม่ได้ จึงต้องมีสองรูปแบบจาก URL เดียวที่ผู้ใช้ส่งมา
    """
    if url.startswith("postgresql+"):
        return url
    return url.replace("postgresql://", "postgresql+psycopg://", 1)


def raw_url(url: str) -> str:
    """รูปแบบที่ psycopg.connect() รับ"""
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def bootstrap_env(database_url: str, staging: Path) -> None:
    """ต้องตั้ง env ก่อน import app.* เพราะ get_settings ถูก lru_cache ไว้"""
    os.environ["DATABASE_URL"] = sqlalchemy_url(database_url)
    os.environ.setdefault("JWT_SECRET", "crawl-approval-check-secret-not-for-production")
    os.environ["CRAWL_STAGING_DIR"] = str(staging)
    os.environ["WARMUP_INTERVAL_MINUTES"] = "0"


PDF = b"%PDF-1.4 staged curriculum document " + b"0" * 4096
NOT_PDF = b"<html><head><title>404</title></head><body>no</body></html>"


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", required=True, help="role ที่เขียนได้ ใช้เตรียมข้อมูล")
    ap.add_argument("--api-url", default=None, help="role ที่สิทธิ์เท่ากับ advisor_api")
    args = ap.parse_args()

    if "course_advisor" in args.database_url or (args.api_url and "course_advisor" in args.api_url):
        raise SystemExit("ปฏิเสธ: สคริปต์นี้ลบข้อมูล ห้ามชี้ไปที่ course_advisor")

    staging_root = Path(tempfile.mkdtemp(prefix="crawl_staging_"))
    outside = Path(tempfile.mkdtemp(prefix="crawl_outside_"))
    bootstrap_env(args.database_url, staging_root)

    import psycopg  # noqa: E402
    from fastapi import FastAPI  # noqa: E402
    from fastapi.testclient import TestClient  # noqa: E402
    from sqlalchemy import create_engine, text  # noqa: E402
    from sqlalchemy.orm import sessionmaker  # noqa: E402

    from app.api.routes import crawl_review as route  # noqa: E402
    from app.core.security import create_access_token, hash_password  # noqa: E402
    from app.db.session import get_db  # noqa: E402

    c = Checks()
    print(f"ฐานข้อมูลทดสอบ: {args.database_url.split('@')[-1]}")
    print(f"staging: {staging_root}\nนอก staging: {outside}")
    print(f"API ใช้ role: {'แยก (ตรวจสิทธิ์ได้)' if args.api_url else 'เดียวกับที่เตรียมข้อมูล (ข้ามข้อสิทธิ์)'}")

    # ---- เตรียมไฟล์ใน staging ------------------------------------------
    good = staging_root / "aaaa11112222_good.pdf"
    good.write_bytes(PDF)
    ambig = staging_root / "bbbb11112222_ambiguous.pdf"
    ambig.write_bytes(PDF + b"ambiguous")
    tampered = staging_root / "cccc11112222_tampered.pdf"
    tampered.write_bytes(PDF + b"tampered")
    notpdf = staging_root / "dddd11112222_notpdf.pdf"
    notpdf.write_bytes(NOT_PDF)
    escape_target = outside / "secret.pdf"
    escape_target.write_bytes(PDF + b"outside")

    link = staging_root / "eeee11112222_link.pdf"
    symlink_kind = "symlink"
    try:
        link.symlink_to(escape_target)
    except (OSError, NotImplementedError):
        # Windows ต้องมีสิทธิ์พิเศษจึงสร้าง symlink ของไฟล์ได้ แต่ junction ของโฟลเดอร์
        # สร้างได้โดยไม่ต้องมีสิทธิ์ และ Path.resolve() คลายมันเหมือนกัน จึงพิสูจน์
        # เรื่องเดียวกันคือ "ทางที่ชี้ออกนอกโฟลเดอร์ต้องถูกปฏิเสธ"
        import subprocess
        junction = staging_root / "jjjj_escape"
        r = subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), str(outside)],
                           capture_output=True)
        if r.returncode == 0:
            link = junction / "secret.pdf"
            symlink_kind = "junction ของโฟลเดอร์"
        else:
            symlink_kind = ""

    # ---- เตรียมฐานข้อมูล ------------------------------------------------
    admin_id, user_id, inactive_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    rows: dict[str, uuid.UUID] = {}
    with psycopg.connect(raw_url(args.database_url), autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM mko.crawl_decisions")
        cur.execute("DELETE FROM mko.crawl_sources")
        cur.execute("DELETE FROM course_documents")
        cur.execute("DELETE FROM courses")
        cur.execute("DELETE FROM users")
        for uid, email, admin, active in [
            (admin_id, "admin@test.local", True, True),
            (user_id, "user@test.local", False, True),
            (inactive_id, "gone@test.local", True, False),
        ]:
            cur.execute("INSERT INTO users (id, email, password_hash, is_admin, is_active) "
                        "VALUES (%s, %s, %s, %s, %s)",
                        (uid, email, hash_password("x" * 12), admin, active))
        cur.execute("INSERT INTO courses (code, title) VALUES "
                    "('cs66','หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาการคอมพิวเตอร์ (พ.ศ. 2566)'),"
                    "('ma69','หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาคณิตศาสตร์ (พ.ศ. 2569)')")

        def add(key: str, *, status: str, needs_review: bool, sha256: str | None,
                staging_path: str | None, confidence: str | None, candidates: str = "[]") -> None:
            cur.execute("""
                INSERT INTO mko.crawl_sources
                    (source_url, page_url, page_title, status, needs_review, review_reason,
                     file_sha256, staging_path, match_confidence, match_candidates,
                     course_code, last_checked_at)
                VALUES (%s, 'https://sci.pnru.ac.th/program_detail.php?id=1', %s, %s, %s,
                        'ทดสอบ', %s, %s, %s, %s::jsonb, 'cs66', now())
                RETURNING id
            """, (f"https://sci.pnru.ac.th/uploads/programs/{key}.pdf", f"หลักสูตร {key}",
                  status, needs_review, sha256, staging_path, confidence, candidates))
            rows[key] = cur.fetchone()[0]

        add("good", status="downloaded", needs_review=True, sha256=sha(PDF),
            staging_path=str(good), confidence="high")
        add("ambig", status="downloaded", needs_review=True, sha256=sha(PDF + b"ambiguous"),
            staging_path=str(ambig), confidence="ambiguous",
            candidates='["วิทยาการคอมพิวเตอร์ (พ.ศ. 2561)","วิทยาการคอมพิวเตอร์ (พ.ศ. 2566)"]')
        add("nofile", status="unchanged", needs_review=True, sha256=sha(PDF + b"nofile"),
            staging_path=None, confidence="ambiguous")
        add("traversal", status="downloaded", needs_review=True, sha256=sha(PDF + b"outside"),
            staging_path=str(staging_root / ".." / outside.name / "secret.pdf"), confidence="high")
        add("symlink", status="downloaded", needs_review=True, sha256=sha(PDF + b"outside"),
            staging_path=str(link), confidence="high")
        add("missing", status="downloaded", needs_review=True, sha256=sha(PDF + b"missing"),
            staging_path=str(staging_root / "ffff11112222_missing.pdf"), confidence="high")
        add("mismatch", status="downloaded", needs_review=True, sha256=sha(PDF + b"different"),
            staging_path=str(tampered), confidence="high")
        add("notpdf", status="downloaded", needs_review=True, sha256=sha(NOT_PDF),
            staging_path=str(notpdf), confidence="high")
        add("nosha", status="error", needs_review=True, sha256=None,
            staging_path=None, confidence=None)

    # ---- ประกอบแอปด้วย router จริง ------------------------------------
    app = FastAPI()
    app.include_router(route.router)

    api_engine = create_engine(sqlalchemy_url(args.api_url or args.database_url), pool_pre_ping=True)
    ApiSession = sessionmaker(bind=api_engine, autoflush=False, autocommit=False)

    def override_db():
        db = ApiSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app, raise_server_exceptions=False)

    admin_h = {"Authorization": f"Bearer {create_access_token(str(admin_id))}"}
    user_h = {"Authorization": f"Bearer {create_access_token(str(user_id))}"}
    gone_h = {"Authorization": f"Bearer {create_access_token(str(inactive_id))}"}

    def sid(key: str) -> str:
        return str(rows[key])

    # =================================================================
    print("\n[1] การยืนยันตัวตนและสิทธิ์")
    r = client.get("/crawl-review/pending")
    c.check("ไม่ส่ง token: 401", r.status_code == 401, str(r.status_code))
    r = client.get("/crawl-review/pending", headers={"Authorization": "Bearer not-a-real-token"})
    c.check("token ปลอม: 401", r.status_code == 401, str(r.status_code))
    r = client.get("/crawl-review/pending", headers=user_h)
    c.check("ผู้ใช้ทั่วไป (is_admin=false): 403", r.status_code == 403, str(r.status_code))
    r = client.get("/crawl-review/pending", headers=gone_h)
    c.check("บัญชีที่ปิดใช้งาน: 401", r.status_code == 401, str(r.status_code))
    r = client.post(f"/crawl-review/{sid('good')}/approve",
                    json={"file_sha256": sha(PDF), "course_code": "cs66"}, headers=user_h)
    c.check("ผู้ใช้ทั่วไปกดอนุมัติ: 403", r.status_code == 403, str(r.status_code))
    r = client.get("/crawl-review/pending", headers=admin_h)
    c.check("ผู้ดูแล: 200", r.status_code == 200, f"{r.status_code} {r.text[:120]}")

    # =================================================================
    print("\n[2] คิวรอตรวจ")
    q = client.get("/crawl-review/pending", headers=admin_h).json()
    c.check("คิวมีครบ 9 รายการ", q["counts"]["total"] == 9, str(q["counts"]))
    c.check("นับรายการที่มีไฟล์ให้ดูได้ถูก", q["counts"]["with_staged_file"] == 7,
            str(q["counts"]["with_staged_file"]))
    c.check("นับรายการกำกวมได้ถูก", q["counts"]["ambiguous"] == 2, str(q["counts"]["ambiguous"]))
    body = client.get("/crawl-review/pending", headers=admin_h).text
    for leak in ("staging_path", "/tmp", str(staging_root), "last_error", "http_etag"):
        c.check(f"คิวไม่รั่ว {leak!r}", leak not in body)
    c.check("คิวบอกแค่ว่ามีไฟล์หรือไม่", all("has_staged_file" in i for i in q["items"]))
    item = next(i for i in q["items"] if i["id"] == sid("ambig"))
    c.check("ส่งตัวเลือกหลักสูตรของรายการกำกวมมาให้", len(item["match_candidates"]) == 2,
            str(item["match_candidates"]))

    r = client.get(f"/crawl-review/{sid('good')}", headers=admin_h)
    c.check("ดูรายการเดียว: 200", r.status_code == 200, str(r.status_code))
    c.check("รายการเดียวไม่รั่ว staging_path", "staging_path" not in r.text)
    r = client.get(f"/crawl-review/{uuid.uuid4()}", headers=admin_h)
    c.check("รายการที่ไม่มีอยู่: 404", r.status_code == 404, str(r.status_code))

    # =================================================================
    print("\n[3] เปิดดู PDF")
    r = client.get(f"/crawl-review/{sid('good')}/pdf", headers=admin_h)
    c.check("ไฟล์ปกติ: 200", r.status_code == 200, f"{r.status_code} {r.text[:80]}")
    c.check("ไฟล์ปกติ: เป็น PDF", r.headers.get("content-type") == "application/pdf",
            str(r.headers.get("content-type")))
    c.check("ไฟล์ปกติ: เนื้อตรงกับที่เก็บไว้", r.content == PDF)
    c.check("ไฟล์ปกติ: เปิดในเบราว์เซอร์ ไม่บังคับดาวน์โหลด",
            "inline" in r.headers.get("content-disposition", ""),
            str(r.headers.get("content-disposition")))

    for key, label in [("traversal", "path traversal (..)"), ("missing", "ไฟล์หายจาก staging"),
                       ("mismatch", "sha256 ไม่ตรง"), ("notpdf", "ไม่ใช่ PDF"),
                       ("nofile", "ไม่มี staging_path")]:
        r = client.get(f"/crawl-review/{sid(key)}/pdf", headers=admin_h)
        c.check(f"{label}: 404", r.status_code == 404, str(r.status_code))
        c.check(f"{label}: ไม่รั่วที่อยู่ไฟล์", str(staging_root) not in r.text and "/tmp" not in r.text)

    if symlink_kind:
        r = client.get(f"/crawl-review/{sid('symlink')}/pdf", headers=admin_h)
        c.check(f"{symlink_kind} ชี้ออกนอก staging: 404", r.status_code == 404, str(r.status_code))
        c.check(f"{symlink_kind}: ไม่ส่งเนื้อไฟล์ข้างนอกออกไป", b"outside" not in r.content)
    else:
        c.skip("ทางเชื่อมที่ชี้ออกนอก staging", "ระบบนี้สร้างทั้ง symlink และ junction ไม่ได้")

    r = client.get(f"/crawl-review/{sid('good')}/pdf", headers=user_h)
    c.check("ผู้ใช้ทั่วไปเปิด PDF: 403", r.status_code == 403, str(r.status_code))

    # =================================================================
    print("\n[4] อนุมัติ")
    r = client.post(f"/crawl-review/{sid('good')}/approve",
                    json={"file_sha256": sha(PDF)}, headers=admin_h)
    c.check("ไม่ส่ง course_code: 422", r.status_code == 422, str(r.status_code))
    r = client.post(f"/crawl-review/{sid('ambig')}/approve",
                    json={"file_sha256": sha(PDF + b"ambiguous")}, headers=admin_h)
    c.check("รายการกำกวมไม่เลือกหลักสูตร: 422", r.status_code == 422, str(r.status_code))
    r = client.post(f"/crawl-review/{sid('good')}/approve",
                    json={"file_sha256": sha(PDF), "course_code": "ไม่มีรหัสนี้"}, headers=admin_h)
    c.check("หลักสูตรที่ไม่มีในระบบ: 422", r.status_code == 422, str(r.status_code))
    r = client.post(f"/crawl-review/{sid('good')}/approve",
                    json={"file_sha256": "0" * 64, "course_code": "cs66"}, headers=admin_h)
    c.check("sha ล้าสมัย: 409", r.status_code == 409, f"{r.status_code} {r.text[:120]}")
    r = client.post(f"/crawl-review/{sid('good')}/approve",
                    json={"file_sha256": "ไม่ใช่แฮช", "course_code": "cs66"}, headers=admin_h)
    c.check("sha ผิดรูปแบบ: 422", r.status_code == 422, str(r.status_code))
    r = client.post(f"/crawl-review/{sid('nofile')}/approve",
                    json={"file_sha256": sha(PDF + b"nofile"), "course_code": "cs66"}, headers=admin_h)
    c.check("ไม่มีไฟล์รออนุมัติ: 409", r.status_code == 409, f"{r.status_code} {r.text[:120]}")
    r = client.post(f"/crawl-review/{sid('nosha')}/approve",
                    json={"file_sha256": "0" * 64, "course_code": "cs66"}, headers=admin_h)
    c.check("แถวที่ยังไม่มี sha: 409", r.status_code == 409, str(r.status_code))

    r = client.post(f"/crawl-review/{sid('good')}/approve",
                    json={"file_sha256": sha(PDF), "course_code": "cs66",
                          "note": "ตรวจแล้วเป็น มคอ.2 ฉบับจริง"}, headers=admin_h)
    c.check("หลักสูตรที่มีอยู่จริง: 201", r.status_code == 201, f"{r.status_code} {r.text[:160]}")
    d = r.json() if r.status_code == 201 else {}
    c.check("บันทึกเป็น approve", d.get("decision") == "approve", str(d.get("decision")))
    c.check("decided_by เป็นอีเมลจาก token ฝั่งเซิร์ฟเวอร์",
            d.get("decided_by") == "admin@test.local", str(d.get("decided_by")))
    c.check("เก็บชื่อหลักสูตรจากฐานข้อมูล ไม่ใช่จาก client",
            (d.get("course_title") or "").startswith("หลักสูตรวิทยาศาสตรบัณฑิต"),
            str(d.get("course_title")))
    c.check("ยังไม่มีการนำเข้า", d.get("document_id") is None and d.get("ingest_finished_at") is None)

    r2 = client.post(f"/crawl-review/{sid('good')}/approve",
                     json={"file_sha256": sha(PDF), "course_code": "cs66"}, headers=admin_h)
    c.check("อนุมัติซ้ำ: 409", r2.status_code == 409, f"{r2.status_code} {r2.text[:120]}")

    q = client.get("/crawl-review/pending", headers=admin_h).json()
    c.check("อนุมัติแล้วหายจากคิว", sid("good") not in [i["id"] for i in q["items"]])
    c.check("คิวเหลือ 8 รายการ", q["counts"]["total"] == 8, str(q["counts"]["total"]))
    r = client.get(f"/crawl-review/{sid('good')}", headers=admin_h)
    c.check("ดูรายการที่ตัดสินแล้ว: 404", r.status_code == 404, str(r.status_code))

    # ส่ง decided_by มาใน body ต้องไม่มีผล
    r = client.post(f"/crawl-review/{sid('ambig')}/approve",
                    json={"file_sha256": sha(PDF + b"ambiguous"), "course_code": "ma69",
                          "decided_by": "someone.else@evil.test"}, headers=admin_h)
    c.check("ส่ง decided_by มาใน body: ถูกเมิน", r.status_code == 201, str(r.status_code))
    if r.status_code == 201:
        c.check("decided_by ยังเป็นเจ้าของ token",
                r.json()["decided_by"] == "admin@test.local", r.json()["decided_by"])

    # =================================================================
    print("\n[5] ไม่เกี่ยวข้อง (ignore)")
    r = client.post(f"/crawl-review/{sid('nofile')}/ignore",
                    json={"file_sha256": sha(PDF + b"nofile"), "reason": "เป็นใบปลิว ไม่ใช่ มคอ.2"},
                    headers=admin_h)
    c.check("ignore รายการที่ไม่มีไฟล์: 201", r.status_code == 201, f"{r.status_code} {r.text[:120]}")
    if r.status_code == 201:
        j = r.json()
        c.check("บันทึกเป็น ignore", j["decision"] == "ignore", j["decision"])
        c.check("ignore ไม่ต้องมีหลักสูตร", j["course_code"] is None, str(j["course_code"]))
    r = client.post(f"/crawl-review/{sid('nofile')}/ignore",
                    json={"file_sha256": sha(PDF + b"nofile"), "reason": "ซ้ำ"}, headers=admin_h)
    c.check("ignore ซ้ำ: 409", r.status_code == 409, str(r.status_code))
    r = client.post(f"/crawl-review/{sid('missing')}/ignore",
                    json={"file_sha256": sha(PDF + b"missing")}, headers=admin_h)
    c.check("ignore ไม่ใส่เหตุผล: 422", r.status_code == 422, str(r.status_code))
    q = client.get("/crawl-review/pending", headers=admin_h).json()
    c.check("ignore แล้วหายจากคิว", sid("nofile") not in [i["id"] for i in q["items"]])

    # =================================================================
    print("\n[6] ถอนการตัดสินใจ (undo)")
    r = client.post(f"/crawl-review/{sid('good')}/undo",
                    json={"file_sha256": sha(PDF)}, headers=admin_h)
    c.check("ถอนก่อนนำเข้า: 200", r.status_code == 200, f"{r.status_code} {r.text[:120]}")
    if r.status_code == 200:
        c.check("บันทึกเวลาที่ถอน", r.json()["superseded_at"] is not None)
    q = client.get("/crawl-review/pending", headers=admin_h).json()
    c.check("ถอนแล้วกลับเข้าคิว", sid("good") in [i["id"] for i in q["items"]])
    r = client.post(f"/crawl-review/{sid('good')}/undo",
                    json={"file_sha256": sha(PDF)}, headers=admin_h)
    c.check("ถอนซ้ำ: 404", r.status_code == 404, str(r.status_code))
    r = client.post(f"/crawl-review/{sid('good')}/approve",
                    json={"file_sha256": sha(PDF), "course_code": "cs66"}, headers=admin_h)
    c.check("ถอนแล้วอนุมัติใหม่ได้: 201", r.status_code == 201, f"{r.status_code} {r.text[:120]}")

    # นำเข้าแล้วถอนไม่ได้ — จำลองว่า worker ของ Phase 3B ทำงานเสร็จ
    with psycopg.connect(raw_url(args.database_url), autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("""
            INSERT INTO course_documents (course_id, original_filename, file_sha256, storage_path, page_count)
            VALUES ((SELECT id FROM courses WHERE code='cs66'), 'good.pdf', %s, '/srv/staging/good.pdf', 10)
            RETURNING id""", (sha(PDF),))
        doc_id = cur.fetchone()[0]
        cur.execute("""UPDATE mko.crawl_decisions
                          SET ingest_started_at = now(), ingest_finished_at = now(), document_id = %s
                        WHERE crawl_source_id = %s AND superseded_at IS NULL""", (doc_id, rows["good"]))
    r = client.post(f"/crawl-review/{sid('good')}/undo",
                    json={"file_sha256": sha(PDF)}, headers=admin_h)
    c.check("ถอนหลังนำเข้าแล้ว: 409", r.status_code == 409, f"{r.status_code} {r.text[:120]}")

    # =================================================================
    print("\n[7] ข้อบังคับของฐานข้อมูล")
    with psycopg.connect(raw_url(args.database_url)) as conn:
        for name, sql in [
            ("CHECK กันคำตัดสินที่ไม่รู้จัก",
             f"INSERT INTO mko.crawl_decisions (crawl_source_id, file_sha256, decision, decided_by) "
             f"VALUES ('{rows['ambig']}', '{'a'*64}', 'ลบทิ้ง', 'x@y.z')"),
            ("CHECK กัน sha256 ผิดรูปแบบ",
             f"INSERT INTO mko.crawl_decisions (crawl_source_id, file_sha256, decision, decided_by) "
             f"VALUES ('{rows['ambig']}', 'ไม่ใช่แฮช', 'ignore', 'x@y.z')"),
            ("CHECK บังคับว่า approve ต้องมีหลักสูตร",
             f"INSERT INTO mko.crawl_decisions (crawl_source_id, file_sha256, decision, decided_by) "
             f"VALUES ('{rows['ambig']}', '{'b'*64}', 'approve', 'x@y.z')"),
            ("CHECK บังคับว่าถอนแล้วต้องรู้ว่าใครถอน",
             f"INSERT INTO mko.crawl_decisions (crawl_source_id, file_sha256, decision, decided_by, superseded_at) "
             f"VALUES ('{rows['ambig']}', '{'c'*64}', 'ignore', 'x@y.z', now())"),
            ("CHECK ห้าม ignore มีผลการนำเข้า",
             f"INSERT INTO mko.crawl_decisions (crawl_source_id, file_sha256, decision, decided_by, ingest_started_at) "
             f"VALUES ('{rows['ambig']}', '{'d'*64}', 'ignore', 'x@y.z', now())"),
            ("CHECK บังคับว่าต้องมีชื่อผู้ตัดสิน",
             f"INSERT INTO mko.crawl_decisions (crawl_source_id, file_sha256, decision, decided_by) "
             f"VALUES ('{rows['ambig']}', '{'e'*64}', 'ignore', '   ')"),
        ]:
            try:
                with conn.cursor() as cur:
                    cur.execute(sql)
                conn.rollback()
                c.check(name, False, "ฐานข้อมูลยอมรับข้อมูลที่ควรถูกปฏิเสธ")
            except psycopg.errors.Error:
                conn.rollback()
                c.check(name, True)

        # partial unique index — แถวที่สองของ (source, sha) เดียวกันต้องไม่ผ่าน
        #
        # ทดสอบสองแบบ เพราะสองแบบพิสูจน์คนละเรื่อง
        #   แบบ A  แถวแรก commit แล้ว แถวที่สองต้องได้ UniqueViolation ทันที
        #   แบบ B  แถวแรกยังไม่ commit แถวที่สองต้องรอ ไม่ใช่ผ่านไปเลย
        #
        # แบบ B ต้องตั้ง lock_timeout ไว้ ไม่งั้นการทดสอบจะค้างรอไปตลอด — ตัวที่สองรอ
        # ให้ตัวแรกตัดสินใจก่อนว่าจะ commit หรือ rollback ซึ่งเป็นพฤติกรรมที่ถูกต้อง
        # ของ unique index และเป็นเหตุผลว่าทำไมสองคนกดพร้อมกันแล้วสำเร็จได้คนเดียว
        q = ("INSERT INTO mko.crawl_decisions (crawl_source_id, file_sha256, decision, "
             "decided_by, course_code) VALUES (%s, %s, 'approve', %s, 'cs66')")
        with psycopg.connect(raw_url(args.database_url), autocommit=True) as first:
            with first.cursor() as cur:
                cur.execute(q, (rows["mismatch"], "f" * 64, "a@t.local"))
            # แบบ A
            try:
                with psycopg.connect(raw_url(args.database_url), autocommit=True) as second,                         second.cursor() as cur:
                    cur.execute(q, (rows["mismatch"], "f" * 64, "b@t.local"))
                c.check("A. แถวที่ commit แล้ว กันแถวซ้ำได้", False, "ยอมรับทั้งสองแถว")
            except psycopg.errors.UniqueViolation:
                c.check("A. แถวที่ commit แล้ว กันแถวซ้ำได้", True)
            # แบบ B — แถวแรกค้างอยู่ใน transaction ที่ยังไม่จบ
            with psycopg.connect(raw_url(args.database_url)) as holder, holder.cursor() as hc:
                hc.execute("DELETE FROM mko.crawl_decisions WHERE file_sha256 = %s", ("f" * 64,))
                hc.execute(q, (rows["mismatch"], "f" * 64, "c@t.local"))   # ยังไม่ commit
                try:
                    with psycopg.connect(raw_url(args.database_url), autocommit=True) as rival,                             rival.cursor() as rc:
                        rc.execute("SET lock_timeout = '1500ms'")
                        rc.execute(q, (rows["mismatch"], "f" * 64, "d@t.local"))
                    c.check("B. สองคนกดพร้อมกัน สำเร็จได้คนเดียว", False,
                            "ตัวที่สองผ่านไปได้ทั้งที่ตัวแรกยังค้างอยู่")
                except (psycopg.errors.LockNotAvailable, psycopg.errors.QueryCanceled,
                        psycopg.errors.UniqueViolation):
                    c.check("B. สองคนกดพร้อมกัน สำเร็จได้คนเดียว", True)
                holder.rollback()
            with first.cursor() as cur:
                cur.execute("DELETE FROM mko.crawl_decisions WHERE file_sha256 = %s", ("f" * 64,))

        # ไม่มีใครมีสิทธิ์ DELETE
        # role ที่ backend ใช้ต้องไม่มี DELETE เลย (role ที่เตรียมข้อมูลในเทสต์มีได้ เป็น
        # เจ้าของฐานข้อมูลทดสอบ ไม่ใช่ role ที่ production ใช้)
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM information_schema.role_table_grants "
                        "WHERE table_schema='mko' AND table_name IN ('crawl_decisions','crawl_sources') "
                        "AND privilege_type='DELETE' "
                        "AND grantee IN ('advisor_api','advisor_ingest','crawl_test_api')")
            n = cur.fetchone()[0]
        conn.rollback()
        c.check("ไม่ให้สิทธิ์ DELETE แก่ role ที่ backend/pipeline ใช้", n == 0, f"พบ {n} รายการ")

    # =================================================================
    print("\n[8] สิทธิ์ของ role ที่ backend ใช้")
    if not args.api_url:
        for n in ("อ่านคิวได้", "เขียน course_documents ไม่ได้", "เขียน course_chunks ไม่ได้",
                  "เขียน crawl_sources ไม่ได้", "แก้เนื้อการตัดสินใจไม่ได้"):
            c.skip(f"role: {n}", "ไม่ได้ระบุ --api-url")
    else:
        with psycopg.connect(raw_url(args.api_url)) as conn:
            def denied(name: str, sql: str) -> None:
                try:
                    with conn.cursor() as cur:
                        cur.execute(sql)
                    conn.rollback()
                    c.check(name, False, "role นี้ทำได้ ซึ่งไม่ควรทำได้")
                except psycopg.errors.InsufficientPrivilege:
                    conn.rollback()
                    c.check(name, True)
                except psycopg.errors.Error as e:
                    conn.rollback()
                    c.check(name, False, f"ถูกปฏิเสธด้วยเหตุอื่น: {type(e).__name__}")

            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM mko.v_crawl_queue")
                c.check("role: อ่านคิวได้", cur.fetchone()[0] >= 0)
            conn.rollback()
            denied("role: เขียน course_documents ไม่ได้",
                   "UPDATE course_documents SET page_count = 1")
            denied("role: เขียน course_chunks ไม่ได้",
                   "DELETE FROM course_chunks WHERE true")
            denied("role: เพิ่ม courses ไม่ได้",
                   "INSERT INTO courses (code, title) VALUES ('new1','x')")
            denied("role: เขียน mko.crawl_sources ไม่ได้",
                   "UPDATE mko.crawl_sources SET status = 'ingested'")
            denied("role: แก้เนื้อการตัดสินใจไม่ได้",
                   "UPDATE mko.crawl_decisions SET decision = 'ignore'")
            denied("role: แก้ผลการนำเข้าไม่ได้",
                   "UPDATE mko.crawl_decisions SET document_id = NULL")
            denied("role: ลบการตัดสินใจไม่ได้",
                   "DELETE FROM mko.crawl_decisions WHERE true")
            denied("role: อ่านคอลัมน์ที่ไม่ได้ให้สิทธิ์ไม่ได้",
                   "SELECT last_error FROM mko.crawl_sources")

    client.close()
    sys.exit(0 if c.report() else 1)


if __name__ == "__main__":
    main()
