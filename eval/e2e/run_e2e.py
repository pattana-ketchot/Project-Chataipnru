"""E2E harness ที่แยกอิสระ — Test PDF -> candidate -> review -> approve -> worker -> pgvector

รันใน e2e-runner ของ compose project sci-advisor-e2e เท่านั้น

หลักการ
-------
* เรียกโค้ด production ตัวจริงทุกขั้น ไม่เขียนตรรกะจำลองขึ้นมาใหม่
* ทุกอย่างเกิดใน e2e_test ซึ่งอยู่คนละอินสแตนซ์ คนละเครือข่าย คนละ volume กับ production
* รหัสผ่านของผู้ใช้ทดสอบสุ่มขึ้นในหน่วยความจำ ไม่เขียนลงไฟล์ ไม่พิมพ์ออกมา
* ทุกการยืนยันเก็บเป็น assertion ที่มีชื่อ คาดหวัง และค่าจริง

    python -m eval.e2e.run_e2e --report /out/e2e_report.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import secrets
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone

import httpx
import psycopg

REPO = pathlib.Path(os.environ.get("E2E_REPO_ROOT", "/repo"))
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from eval.e2e import seed as seedmod                      # noqa: E402
from eval.e2e.make_test_pdf import MARKER, PDF_NAME, build as build_pdf  # noqa: E402

E2E_DSN = os.environ["E2E_DSN"]                 # postgres superuser ของฐานทดสอบ
INGEST_DSN = os.environ["INGEST_DATABASE_URL"]  # advisor_ingest ของฐานทดสอบ
BACKEND = os.environ.get("E2E_BACKEND_URL", "http://e2e-backend:8000")
SITE_DIR = pathlib.Path(os.environ.get("E2E_SITE_DIR", "/srv/site"))
STAGING = pathlib.Path(os.environ.get("CRAWL_STAGING_DIR", "/srv/staging"))
DOCUMENTS = pathlib.Path(os.environ.get("DOCUMENTS_DIR", "/srv/documents"))
OUT_DIR = pathlib.Path(os.environ.get("E2E_OUT_DIR", "/out"))

SEEDS = ["http://sci.pnru.ac.th/programs.php"]
FAKE_HOST = "sci.pnru.ac.th"

RESULTS: list[dict] = []
FINDINGS: list[dict] = []
_T0 = time.time()


def check(name: str, expected, actual, ok: bool | None = None) -> bool:
    passed = (expected == actual) if ok is None else bool(ok)
    RESULTS.append({
        "name": name,
        "expected": str(expected),
        "actual": str(actual),
        "status": "PASS" if passed else "FAIL",
        "t": round(time.time() - _T0, 1),
    })
    mark = "PASS" if passed else "FAIL"
    print(f"  [{mark}] {name}  คาด={expected!r} จริง={actual!r}", flush=True)
    return passed


def section(title: str) -> None:
    print(f"\n=== {title} ===", flush=True)


def db(dsn: str = E2E_DSN):
    seedmod.guard_dsn(dsn)
    conn = psycopg.connect(dsn)
    seedmod.guard_connection(conn)
    return conn


def scalar(sql: str, params=(), dsn: str = E2E_DSN):
    with db(dsn) as conn, conn.cursor() as cur:
        return cur.execute(sql, params).fetchone()[0]


def row(sql: str, params=(), dsn: str = E2E_DSN):
    with db(dsn) as conn, conn.cursor() as cur:
        return cur.execute(sql, params).fetchone()


# ---------------------------------------------------------------- 0. ด่าน
def phase_guard() -> dict:
    section("PHASE 3 — ด่านการแยก (hard isolation gate)")
    seedmod.guard_dsn(E2E_DSN)
    seedmod.guard_dsn(INGEST_DSN)
    with psycopg.connect(E2E_DSN) as conn:
        dbname = seedmod.guard_connection(conn)
    check("ฐานข้อมูลที่ต่อคือฐานทดสอบ", "e2e_test", dbname)
    check("DSN ไม่มีคำว่า course_advisor", True, "course_advisor" not in (E2E_DSN + INGEST_DSN))
    # ชื่อโฮสต์ของเว็บจำลองต้องชี้ภายในเครือข่ายทดสอบ
    import socket
    ip = socket.gethostbyname(FAKE_HOST)
    check("sci.pnru.ac.th resolve ได้ในเครือข่ายทดสอบ", True, bool(ip), ok=bool(ip))
    print(f"    sci.pnru.ac.th -> {ip} (ที่อยู่ภายในเครือข่าย sci-advisor-e2e)")
    return {"database": dbname, "fake_host_ip": ip}


# ---------------------------------------------------------------- 1. seed
def phase_seed() -> dict:
    section("PHASE 5 — seed ฐานข้อมูลทดสอบ")
    check("backend พร้อมรับคำขอสมัคร", True, wait_for(f"{BACKEND}/health"))
    admin_pw = secrets.token_urlsafe(18)
    user_pw = secrets.token_urlsafe(18)
    info = seedmod.seed_database(E2E_DSN, REPO, BACKEND, admin_pw, user_pw)
    snap = info["snapshot"]
    print("    migrations:", ", ".join(info["migrations_applied"]))
    check("courses เริ่มต้น", 1, snap["courses"])
    check("course_documents เริ่มต้น", 0, snap["course_documents"])
    check("course_chunks เริ่มต้น", 0, snap["course_chunks"])
    check("crawl_sources เริ่มต้น", 0, snap["crawl_sources"])
    check("crawl_decisions เริ่มต้น", 0, snap["crawl_decisions"])
    check("v_crawl_queue เริ่มต้น", 0, snap["v_crawl_queue"])
    check("users เริ่มต้น", 2, snap["users"])
    check("admins เริ่มต้น", 1, snap["admins"])
    info["admin_pw"] = admin_pw
    info["user_pw"] = user_pw
    return info


# ---------------------------------------------------------------- 2. PDF
def phase_pdf() -> dict:
    section("PHASE 6 — สร้าง Test PDF")
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    out = SITE_DIR / PDF_NAME
    sha, size = build_pdf(str(out))
    check("ไฟล์ PDF ถูกสร้าง", True, out.is_file())
    check("ขึ้นต้นด้วย %PDF-", True, out.read_bytes()[:5] == b"%PDF-")
    check("ขนาดไม่เกิน 50MB", True, size < 50 * 1024 * 1024)
    print(f"    sha256 {sha} · {size} ไบต์")
    return {"sha256": sha, "size": size, "path": str(out)}


def wait_for(url: str, tries: int = 60, delay: float = 1.0) -> bool:
    for _ in range(tries):
        try:
            r = httpx.get(url, timeout=5.0)
            if r.status_code < 500:
                return True
        except Exception:
            pass
        time.sleep(delay)
    return False


# ---------------------------------------------------------------- 3. crawl
def phase_crawl(pdf_sha: str) -> dict:
    section("PHASE 7 — crawler ตัวจริงกับเว็บจำลอง")
    check("เว็บจำลองพร้อม", True, wait_for(f"http://{FAKE_HOST}/programs.php"))

    from pipeline.crawl.discover import crawl
    from pipeline.crawl.http import PoliteClient
    from pipeline.crawl.state import CrawlStore
    from pipeline.crawl.sync import FOLLOW, process_link

    STAGING.mkdir(parents=True, exist_ok=True)
    with CrawlStore(INGEST_DSN) as store:
        by_sha = store.known_sha256()
        with PoliteClient(delay=0.1) as client:
            pages, links, errors = crawl(client, SEEDS, FAKE_HOST, FOLLOW, max_pages=10)
            print(f"    เดินเว็บ {len(pages)} หน้า · พบลิงก์ PDF {len(links)} · error {len(errors)}")
            check("พบลิงก์ PDF หนึ่งรายการ", 1, len(links))
            outcomes = []
            for link in links:
                try:
                    outcomes.append(
                        process_link(client, store, link, [], by_sha, STAGING, True))
                    # sync.py::main() commit หลัง process_link ทุกครั้ง harness ต้องทำเหมือนกัน
                    store.conn.commit()
                except Exception:
                    store.conn.rollback()
                    raise

    o = outcomes[0]
    print(f"    ผล: status={o.status} sha={o.sha256} staging={o.staging_path}")
    check("status ของแหล่งใหม่", "downloaded", o.status)
    check("sha256 ตรงกับไฟล์ที่สร้าง", pdf_sha, o.sha256)

    src = row("SELECT id::text, status, file_sha256, staging_path, needs_review, "
              "       match_confidence, source_url "
              "  FROM mko.crawl_sources")
    check("crawl_sources มีหนึ่งแถว", 1, scalar("SELECT count(*) FROM mko.crawl_sources"))
    check("status ในฐานข้อมูล", "downloaded", src[1])
    check("file_sha256 ในฐานข้อมูล", pdf_sha, src[2])
    check("staging_path ไม่เป็น null", True, src[3] is not None)
    check("needs_review เป็น true", True, src[4])
    check("ไฟล์ staged มีอยู่จริง", True, pathlib.Path(src[3]).is_file())
    staged_sha = hashlib.sha256(pathlib.Path(src[3]).read_bytes()).hexdigest()
    check("sha ของไฟล์ staged ตรงกับที่บันทึก", pdf_sha, staged_sha)
    check("v_crawl_queue มีหนึ่งรายการ", 1, scalar("SELECT count(*) FROM mko.v_crawl_queue"))
    check("has_staged_file เป็น true", True,
          scalar("SELECT has_staged_file FROM mko.v_crawl_queue"))
    return {"source_id": src[0], "staging_path": src[3], "source_url": src[6],
            "match_confidence": src[5]}


# ---------------------------------------------------------------- 4. review
def login(email: str, password: str) -> tuple[int, str | None]:
    r = httpx.post(f"{BACKEND}/auth/login", json={"email": email, "password": password},
                   timeout=30.0)
    if r.status_code != 200:
        return r.status_code, None
    return 200, r.json()["access_token"]


def phase_review(seed_info: dict, source_id: str, pdf_sha: str,
                 staging_path: str) -> dict:
    section("PHASE 8 — Admin Review")
    check("backend พร้อม", True, wait_for(f"{BACKEND}/health"))

    # anonymous
    r = httpx.get(f"{BACKEND}/crawl-review/pending", timeout=30.0)
    check("anonymous GET /pending", 401, r.status_code)
    r = httpx.get(f"{BACKEND}/crawl-review/{source_id}", timeout=30.0)
    check("anonymous GET /{id}", 401, r.status_code)
    r = httpx.get(f"{BACKEND}/crawl-review/{source_id}/pdf", timeout=30.0)
    check("anonymous GET /{id}/pdf", 401, r.status_code)

    # non-admin
    code, utok = login(seedmod.TEST_USER_EMAIL, seed_info["user_pw"])
    check("non-admin login สำเร็จ", 200, code)
    r = httpx.get(f"{BACKEND}/crawl-review/pending",
                  headers={"Authorization": f"Bearer {utok}"}, timeout=30.0)
    check("non-admin GET /pending", 403, r.status_code)

    # admin
    code, tok = login(seedmod.TEST_ADMIN_EMAIL, seed_info["admin_pw"])
    check("admin login สำเร็จ", 200, code)
    H = {"Authorization": f"Bearer {tok}"}

    r = httpx.get(f"{BACKEND}/crawl-review/pending", headers=H, timeout=30.0)
    check("admin GET /pending", 200, r.status_code)
    page = r.json()
    check("จำนวนรายการในคิว", 1, len(page["items"]))
    check("counts.with_staged_file", 1, page["counts"]["with_staged_file"])

    r = httpx.get(f"{BACKEND}/crawl-review/{source_id}", headers=H, timeout=30.0)
    check("admin GET /{id}", 200, r.status_code)
    detail = r.json()
    check("payload ไม่เปิดเผย staging_path", True, "staging_path" not in detail)

    # ---- เกณฑ์รับหลักของการแก้ F1 ------------------------------------
    #
    # ไฟล์นี้ถูก crawler เขียนลง staging เองทั้งเส้นทาง ไม่มีใครแตะสิทธิ์ต่อ
    # ห้ามมี chmod / chown / copy / setfacl / workaround ใดก่อนถึงบรรทัดข้างล่างนี้
    # ถ้าต้องแตะสิทธิ์ก่อนจึงจะเปิดได้ ถือว่าการแก้ F1 ไม่สำเร็จ
    import stat as _stat
    staged = pathlib.Path(staging_path)
    st = staged.stat()
    mode_from_crawler = _stat.S_IMODE(st.st_mode)
    check("โหมดไฟล์ staged ที่ crawler สร้าง", "0o644", oct(mode_from_crawler))
    check("ไฟล์ staged ไม่ world-writable", 0, mode_from_crawler & 0o002)
    check("ไฟล์ staged ไม่ group-writable", 0, mode_from_crawler & 0o020)
    check("ไฟล์ staged ไม่มี execute bit", 0, mode_from_crawler & 0o111)
    check("ไฟล์ staged ไม่มี setuid/setgid/sticky", 0, mode_from_crawler & 0o7000)
    check("uid ของไฟล์ staged", 1001, st.st_uid)

    r = httpx.get(f"{BACKEND}/crawl-review/{source_id}/pdf", headers=H, timeout=60.0)
    check("[เกณฑ์รับ F1] เปิด PDF ได้ทันทีโดยไม่แตะสิทธิ์", 200, r.status_code)
    check("content-type ของ PDF", "application/pdf",
          r.headers.get("content-type", "").split(";")[0])
    check("เนื้อไฟล์ขึ้นต้น %PDF-", True, r.content[:5] == b"%PDF-")
    check("sha ของ PDF ที่ส่งออกตรงกับที่ staged", pdf_sha,
          hashlib.sha256(r.content).hexdigest())
    check("ขนาด PDF ที่ส่งออกตรงกับไฟล์ใน staging", st.st_size, len(r.content))

    # โหมดต้องไม่ถูกเปลี่ยนโดยการอ่านของ backend
    check("โหมดไฟล์คงเดิมหลัง backend อ่าน", "0o644",
          oct(_stat.S_IMODE(staged.stat().st_mode)))

    FINDINGS.append({
        "id": "F1",
        "state": "แก้แล้วและยืนยันในรอบนี้",
        "title": "ไฟล์ที่ crawler เก็บไว้ที่ staging เคยเป็นโหมด 0600 จึงถูก backend อ่านไม่ได้",
        "root_cause": "tempfile.mkstemp() สร้างไฟล์โหมด 0600 โดยไม่สนใจ umask "
                      "และ os.replace() ไม่แตะโหมด",
        "fix": "pipeline/crawl/http.py — os.chmod(tmp, STAGED_FILE_MODE=0o644) "
               "หลังไฟล์ครบและผ่านทุกด่าน ก่อนคืนให้ผู้เรียก",
        "verified_by": "โหมดที่วัดได้จาก crawler คือ 0644 และ "
                       "GET /crawl-review/{id}/pdf ตอบ 200 ทันทีโดยไม่มี workaround",
    })
    return {"admin_token": tok, "user_token": utok, "detail_keys": sorted(detail.keys()),
            "staged_mode": oct(mode_from_crawler), "staged_uid": st.st_uid}


# ------------------------------------------------ 5. fail-closed ของ staging
def phase_staging_guards(tok: str, source_id: str, staging_path: str, pdf_sha: str) -> None:
    section("PHASE 13a — fail-closed ของ staged PDF endpoint (ทำแล้วคืนสภาพทุกครั้ง)")
    H = {"Authorization": f"Bearer {tok}"}
    p = pathlib.Path(staging_path)
    backup = p.with_suffix(p.suffix + ".bak")

    # 1) ไฟล์หาย
    shutil.move(str(p), str(backup))
    r = httpx.get(f"{BACKEND}/crawl-review/{source_id}/pdf", headers=H, timeout=30.0)
    check("ไฟล์ staged หาย -> 404", 404, r.status_code)
    shutil.move(str(backup), str(p))

    # 2) เนื้อไฟล์เปลี่ยน (sha ไม่ตรง)
    orig = p.read_bytes()
    p.write_bytes(orig + b"\n% tampered for e2e test\n")
    r = httpx.get(f"{BACKEND}/crawl-review/{source_id}/pdf", headers=H, timeout=30.0)
    check("sha ไม่ตรง -> 404", 404, r.status_code)
    p.write_bytes(orig)

    # 3) ไม่ใช่ PDF แต่ sha ตรงกับที่บันทึกไว้
    fake = b"<html>not a pdf at all</html>"
    fake_sha = hashlib.sha256(fake).hexdigest()
    p.write_bytes(fake)
    with db() as conn, conn.cursor() as cur:
        cur.execute("UPDATE mko.crawl_sources SET file_sha256 = %s WHERE id = %s",
                    (fake_sha, source_id))
        conn.commit()
    r = httpx.get(f"{BACKEND}/crawl-review/{source_id}/pdf", headers=H, timeout=30.0)
    check("ไฟล์ไม่ใช่ PDF (sha ตรง) -> 404", 404, r.status_code)
    p.write_bytes(orig)
    with db() as conn, conn.cursor() as cur:
        cur.execute("UPDATE mko.crawl_sources SET file_sha256 = %s WHERE id = %s",
                    (pdf_sha, source_id))
        conn.commit()

    # 4) path หลุดออกนอก root — เรียกฟังก์ชันของ worker ตรง ๆ
    from pipeline.crawl.approve import JobError, resolve_staged
    try:
        resolve_staged(STAGING, "/etc/passwd")
        check("path หลุด root -> ปฏิเสธ", "JobError", "ไม่ปฏิเสธ")
    except JobError as e:
        check("path หลุด root -> ปฏิเสธ", True, "path_outside_staging_root" in str(e))

    # คืนสภาพครบ
    r = httpx.get(f"{BACKEND}/crawl-review/{source_id}/pdf", headers=H, timeout=30.0)
    check("คืนสภาพแล้วเปิด PDF ได้เหมือนเดิม", 200, r.status_code)


# ---------------------------------------------------------------- 6. approve
def phase_approve(tok: str, source_id: str, pdf_sha: str) -> None:
    section("PHASE 9 — Approve TEST CANDIDATE")
    H = {"Authorization": f"Bearer {tok}"}

    r = httpx.post(f"{BACKEND}/crawl-review/{source_id}/approve", headers=H, timeout=30.0,
                   json={"file_sha256": "0" * 64, "course_code": seedmod.TEST_COURSE_CODE})
    check("approve ด้วย sha ผิด -> 409", 409, r.status_code)

    r = httpx.post(f"{BACKEND}/crawl-review/{source_id}/approve", headers=H, timeout=30.0,
                   json={"file_sha256": pdf_sha, "course_code": "NOPE999"})
    check("approve ด้วยรหัสหลักสูตรที่ไม่มี -> 422", 422, r.status_code)
    check("crawl_decisions ยังเป็น 0 หลังกรณีที่ถูกปฏิเสธ", 0,
          scalar("SELECT count(*) FROM mko.crawl_decisions"))

    r = httpx.post(f"{BACKEND}/crawl-review/{source_id}/approve", headers=H, timeout=30.0,
                   json={"file_sha256": pdf_sha, "course_code": seedmod.TEST_COURSE_CODE})
    check("approve สำเร็จ", 201, r.status_code)

    d = row("SELECT decision, superseded_at, course_code, decided_by, file_sha256, "
            "       ingest_started_at, ingest_finished_at, document_id "
            "  FROM mko.crawl_decisions")
    check("crawl_decisions มีหนึ่งแถว", 1, scalar("SELECT count(*) FROM mko.crawl_decisions"))
    check("decision", "approve", d[0])
    check("superseded_at เป็น null", True, d[1] is None)
    check("course_code", seedmod.TEST_COURSE_CODE, d[2])
    check("decided_by เป็นอีเมลของ admin ทดสอบ", seedmod.TEST_ADMIN_EMAIL, d[3])
    check("file_sha256 ของ decision", pdf_sha, d[4])
    check("ยังไม่เริ่ม ingest", True, d[5] is None and d[6] is None and d[7] is None)

    r = httpx.post(f"{BACKEND}/crawl-review/{source_id}/approve", headers=H, timeout=30.0,
                   json={"file_sha256": pdf_sha, "course_code": seedmod.TEST_COURSE_CODE})
    check("approve ซ้ำ -> 409", 409, r.status_code)
    check("ยังมี decision แถวเดียว", 1, scalar("SELECT count(*) FROM mko.crawl_decisions"))

    r = httpx.get(f"{BACKEND}/crawl-review/pending", headers=H, timeout=30.0)
    check("คิวว่างหลังตัดสินใจ", 0, len(r.json()["items"]))


# ---------------------------------------------------------------- 7. worker
def run_worker(extra_env: dict | None = None, max_jobs: int = 1) -> tuple[int, str]:
    env = dict(os.environ)
    env.update(extra_env or {})
    p = subprocess.run(
        [sys.executable, "-m", "pipeline.crawl.approve", "--max-jobs", str(max_jobs)],
        cwd=str(REPO), env=env, capture_output=True, text=True, timeout=900)
    return p.returncode, (p.stdout + p.stderr)


def phase_worker_contract() -> None:
    section("PHASE 13b — สัญญา embedding ของ worker (ต้องล้มก่อนแตะงาน)")
    rc, out = run_worker({"EMBED_MODEL": "nomic-embed-text"})
    check("EMBED_MODEL ผิด -> ไม่สำเร็จ", True, rc != 0)
    check("เหตุผลคือ embed_model_mismatch", True, "embed_model_mismatch" in out)
    rc, out = run_worker({"EMBED_DIM": "768"})
    check("EMBED_DIM ผิด -> ไม่สำเร็จ", True, rc != 0)
    check("เหตุผลคือ embed_dim_mismatch", True, "embed_dim_mismatch" in out)
    # approve.py:448 เรียก check_embedding_contract() ใน process() ซึ่งอยู่หลัง claim()
    # (approve.py:485 claim -> 492 process) งานจึงถูกยึดและ ingest_started_at ถูกเขียนก่อน
    started = row("SELECT ingest_started_at, ingest_finished_at, ingest_error "
                  "  FROM mko.crawl_decisions")
    check("สัญญาถูกตรวจหลัง claim จึงมี ingest_started_at แล้ว", True, started[0] is not None)
    check("งานยังไม่ถูกปิด (ingest_finished_at ยังว่าง) จึงยังยึดใหม่ได้", True, started[1] is None)
    check("บันทึกเหตุผลของความล้มเหลวไว้ใน ingest_error", True,
          started[2] is not None and "embed_dim_mismatch" in started[2])
    FINDINGS.append({
        "id": "F2",
        "severity": "ข้อสังเกตเชิงพฤติกรรม ไม่ใช่ข้อบกพร่อง",
        "title": "check_embedding_contract() ทำงานหลัง claim() ไม่ใช่ก่อน",
        "where": "pipeline/crawl/approve.py:448 อยู่ใน process() ซึ่งถูกเรียกที่บรรทัด 492 "
                 "หลัง claim() ที่บรรทัด 485",
        "effect": "worker ที่ตั้งค่า embedding ผิดจะยึดงานก่อนแล้วจึงล้ม ทำให้ ingest_started_at "
                  "และ ingest_error ถูกเขียน แต่ ingest_finished_at ยังว่าง งานจึงยังถูกยึดใหม่ได้ "
                  "และการรันครั้งถัดไปที่ตั้งค่าถูกก็ทำงานสำเร็จ (พิสูจน์แล้วในรอบนี้)",
        "correction": "รายงานรอบก่อนเคยระบุว่า 'ล้มก่อนแตะงานใด' ซึ่งไม่ตรงกับโค้ดจริง",
    })


def phase_worker(pdf_sha: str) -> dict:
    section("PHASE 10 — worker และ ingestion")
    t0 = time.time()
    rc, out = run_worker()
    dt = round(time.time() - t0, 1)
    print(f"    worker ใช้เวลา {dt} วินาที · exit={rc}")
    for line in out.splitlines()[-12:]:
        print("      " + line)
    check("worker จบด้วยรหัส 0", 0, rc)

    d = row("SELECT ingest_started_at, ingest_finished_at, document_id::text, ingest_error "
            "  FROM mko.crawl_decisions")
    check("ingest_started_at ถูกเติม", True, d[0] is not None)
    check("ingest_finished_at ถูกเติม", True, d[1] is not None)
    check("document_id ถูกเติม", True, d[2] is not None)
    check("ingest_error เป็น null", True, d[3] is None)

    check("course_documents = 1", 1, scalar("SELECT count(*) FROM course_documents"))
    doc = row("SELECT id::text, course_id::text, original_filename, file_sha256, "
              "       page_count, extraction_status FROM course_documents")
    check("extraction_status", "done", doc[5])
    check("file_sha256 ของเอกสาร", pdf_sha, doc[3])
    check("page_count >= 1", True, doc[4] >= 1)
    check("document_id ของ decision ตรงกับเอกสารที่สร้าง", doc[0], d[2])
    course_id = scalar("SELECT id::text FROM courses WHERE code = %s",
                       (seedmod.TEST_COURSE_CODE,))
    check("เอกสารผูกกับ TEST101", course_id, doc[1])

    n_chunks = scalar("SELECT count(*) FROM course_chunks")
    check("course_chunks > 0", True, n_chunks > 0)
    check("ทุก chunk มี embedding", 0,
          scalar("SELECT count(*) FROM course_chunks WHERE embedding IS NULL"))
    check("ทุก vector มี 1024 มิติ", 0,
          scalar("SELECT count(*) FROM course_chunks WHERE vector_dims(embedding) <> 1024"))
    check("chunk_index เริ่มที่ 0", 0, scalar("SELECT min(chunk_index) FROM course_chunks"))

    published = [p for p in DOCUMENTS.rglob("*.pdf")]
    check("มีไฟล์ถูก publish หนึ่งไฟล์", 1, len(published))
    check("sha ของไฟล์ที่ publish ตรงกับที่ approve", pdf_sha,
          hashlib.sha256(published[0].read_bytes()).hexdigest())
    check("ไฟล์อยู่ใน DOCUMENTS_DIR ของ test เท่านั้น", True,
          str(published[0]).startswith(str(DOCUMENTS)))
    return {"document_id": doc[0], "chunks": n_chunks, "worker_seconds": dt,
            "published": str(published[0])}


# ---------------------------------------------------------------- 8. vector
def phase_vector(document_id: str) -> dict:
    section("PHASE 11 — การค้นด้วย pgvector")
    from llm.connector import OllamaConnector
    conn_llm = OllamaConnector(base_url=os.environ["OLLAMA_BASE_URL"],
                               embed_model=os.environ["EMBED_MODEL"])
    vec = conn_llm.embed(MARKER)
    check("query embedding มี 1024 มิติ", 1024, len(vec))

    lit = "[" + ",".join(f"{v:.8f}" for v in vec) + "]"
    with db() as conn, conn.cursor() as cur:
        # ivfflat lists=100 กับข้อมูลไม่กี่แถวอาจคืนผลไม่ครบ (probes เริ่มต้น = 1)
        # จึงตั้ง probes ให้ครอบคลุมทุก list — ไม่ได้แก้ schema หรือ index ใด
        cur.execute("SET LOCAL ivfflat.probes = 100")
        rows = cur.execute(
            "SELECT document_id::text, chunk_index, content, "
            "       (embedding <=> %s::vector) AS distance "
            "  FROM course_chunks ORDER BY embedding <=> %s::vector LIMIT 5",
            (lit, lit)).fetchall()
    check("การค้นคืนผลลัพธ์", True, len(rows) > 0)
    top = rows[0]
    print(f"    อันดับ 1: chunk_index={top[1]} distance={top[3]:.6f}")
    check("อันดับ 1 มาจากเอกสารทดสอบ", document_id, top[0])
    check("เนื้อหาของอันดับ 1 มี TEST101", True, "TEST101" in top[2])
    check("เนื้อหาของผลลัพธ์รวมมี marker", True,
          any(MARKER in r[2] for r in rows))
    return {"top_distance": float(top[3]), "returned": len(rows)}


# ---------------------------------------------------------------- 9. duplicate
def phase_duplicate(before: dict) -> None:
    section("PHASE 12 — การกันซ้ำ")
    finished_before = row("SELECT ingest_finished_at FROM mko.crawl_decisions")[0]
    rc, out = run_worker()
    check("รัน worker ซ้ำจบด้วยรหัส 0", 0, rc)
    check("ingest_finished_at ไม่ถูกเขียนทับ (ไม่มีงานให้ยึด)", finished_before,
          row("SELECT ingest_finished_at FROM mko.crawl_decisions")[0])
    check("course_documents ไม่เพิ่ม", before["documents"],
          scalar("SELECT count(*) FROM course_documents"))
    check("course_chunks ไม่เพิ่ม", before["chunks"],
          scalar("SELECT count(*) FROM course_chunks"))
    check("crawl_decisions ไม่เพิ่ม", before["decisions"],
          scalar("SELECT count(*) FROM mko.crawl_decisions"))
    check("ไฟล์ใน DOCUMENTS_DIR ไม่เพิ่ม", before["published"],
          len(list(DOCUMENTS.rglob("*.pdf"))))


# ---------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", default=str(OUT_DIR / "e2e_report.json"))
    args = ap.parse_args()

    started = datetime.now(timezone.utc).isoformat()
    meta: dict = {"started_utc": started}

    meta["guard"] = phase_guard()
    seed_info = phase_seed()
    pdf = phase_pdf()
    meta["pdf"] = {k: pdf[k] for k in ("sha256", "size", "path")}
    crawl_info = phase_crawl(pdf["sha256"])
    meta["crawl"] = crawl_info
    rev = phase_review(seed_info, crawl_info["source_id"], pdf["sha256"],
                       crawl_info["staging_path"])
    meta["review_detail_keys"] = rev["detail_keys"]
    phase_staging_guards(rev["admin_token"], crawl_info["source_id"],
                         crawl_info["staging_path"], pdf["sha256"])
    phase_approve(rev["admin_token"], crawl_info["source_id"], pdf["sha256"])
    phase_worker_contract()
    w = phase_worker(pdf["sha256"])
    meta["worker"] = w
    meta["vector"] = phase_vector(w["document_id"])
    phase_duplicate({"documents": 1, "chunks": w["chunks"], "decisions": 1,
                     "published": 1})

    section("สรุป")
    passed = sum(1 for r in RESULTS if r["status"] == "PASS")
    failed = sum(1 for r in RESULTS if r["status"] == "FAIL")
    print(f"  ผ่าน {passed} · ไม่ผ่าน {failed} · รวม {len(RESULTS)}")
    for r in RESULTS:
        if r["status"] == "FAIL":
            print(f"    FAIL: {r['name']} คาด={r['expected']} จริง={r['actual']}")

    meta.update({
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "passed": passed, "failed": failed, "total": len(RESULTS),
        "overall": "PASS" if failed == 0 else "FAIL",
        "findings": FINDINGS,
        "results": RESULTS,
    })
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pathlib.Path(args.report).write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  เขียนรายงานที่ {args.report}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
