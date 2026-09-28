"""
Phase 3C — ตัวนำเข้าไฟล์ที่ผู้ดูแลอนุมัติแล้ว (รันครั้งเดียวแล้วจบ)

    python -m pipeline.crawl.approve --max-jobs 1

อ่านการอนุมัติจาก mko.crawl_decisions ที่คนกดไว้ (Phase 3A/3B) ตรวจไฟล์ใน staging
แล้วส่งเข้า pipeline.ingest.run() ตัวเดิมโดยไม่แก้มันเลยแม้บรรทัดเดียว

สิ่งที่โมดูลนี้ไม่ทำ
------------------
ไม่สร้างการอนุมัติเอง · ไม่สร้างหลักสูตรใหม่ · ไม่ดาวน์โหลดอะไรใหม่ · ไม่แก้ crawler ·
ไม่ตั้งเวลาทำงาน · ไม่วนรอ job ใหม่ · ไม่ใช้ needs_review หรือ match_confidence หรือ
crawl_sources.status เป็นหลักฐานการอนุมัติ — หลักฐานเดียวคือแถวใน crawl_decisions
ที่ decision='approve' และ superseded_at IS NULL

ทำไมถือ transaction ไว้ตลอดงาน
------------------------------
backend ปล่อยให้ถอนการอนุมัติได้ตราบใดที่ ingest_finished_at ยังว่าง — ดู
backend/app/services/crawl_review.py:225 ซึ่งตรวจเฉพาะ ingest_finished_at กับ
document_id ไม่ได้ตรวจ ingest_started_at ถ้า worker ยึดงานแล้ว commit ทิ้งไว้
แล้วไปทำงานยาว ๆ คนกดถอนกลางทางได้ และเอกสารจะเข้าคลังความรู้ไปแล้วโดยที่การอนุมัติ
ถูกถอน ซึ่งผิดหลักที่ว่าไม่มีอะไรเข้าคลังโดยไม่มีคนอนุญาต

ที่นี่จึงถือ row lock ของแถว decision ไว้ตั้งแต่ยึดงานจนจบ คำสั่ง UPDATE ของ
/crawl-review/{id}/undo จะรอที่แถวเดียวกันนี้ พอ worker commit เสร็จ คำสั่งถอนจะเห็น
ingest_finished_at แล้วถูกปฏิเสธด้วย 409 ตามเงื่อนไขเดิมของมันเอง — ปิดช่องได้โดย
ไม่ต้องแก้ backend

ราคาที่ยอมจ่าย: คำขอถอนที่เข้ามาระหว่างที่ worker ทำงานจะค้างรอจนงานจบ และ
transaction เปิดค้างนานเท่าเวลาที่ embedding ใช้ ดูหัวข้อข้อจำกัดในรายงาน Phase 3C

การถือ lock นี้ไม่ทำให้ตัวเองค้าง เพราะ pipeline.ingest.run() เปิด connection ของตัวเอง
และแตะแค่ courses / course_documents / course_chunks ไม่แตะ mko.* เลย

crash แล้วกู้อย่างไร
-------------------
ยึดงานอยู่ใน transaction ที่ยังไม่ commit ถ้า worker ตาย transaction ถูกยกเลิก
ingest_started_at จึงไม่เคยถูกบันทึก งานกลับเป็นงานที่ยังไม่มีใครยึดโดยอัตโนมัติ
ไม่มี claim ค้าง ไม่ต้องมีคอลัมน์ lease และไม่ต้องมีตัวเก็บกวาด

ถ้าตายหลัง run() commit ของมันไปแล้วแต่ก่อน worker commit: เอกสารกับ chunk อยู่ในคลัง
แล้วแต่ decision ยังไม่ถูกปิด รอบถัดไปจะยึดงานเดิมได้ แล้ว already_ingested() ใน
pipeline/ingest.py:186 จะเห็น sha ที่ทำเสร็จแล้วและคืนค่าออกมาโดยไม่ embed ซ้ำ
worker จึงหาเอกสารด้วย sha แล้วปิดงานได้ — กู้เองได้และทำซ้ำได้
"""
from __future__ import annotations

import argparse
import hashlib
import logging
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import psycopg  # noqa: E402
from psycopg.rows import dict_row  # noqa: E402

from llm.connector import LLMConnectionError, OllamaConnector  # noqa: E402
from pipeline.extract_pdf import InvalidPdfError, extract_pdf  # noqa: E402

logger = logging.getLogger("pipeline.crawl.approve")

# สัญญาของ embedding ที่คลังความรู้ชุดนี้ใช้ — db/schema.sql:122 ประกาศ VECTOR(1024)
# และ docker-compose.prod.yml:74-75 ตั้ง bge-m3 / 1024
# pipeline/ingest.py ไม่ได้ตรวจสองค่านี้เลย (อ่านแค่ EMBED_MODEL ที่บรรทัด 179 และมี
# ค่าเริ่มต้นเป็น nomic-embed-text ซึ่งให้เวกเตอร์ 768 มิติ) ถ้าหลุดเข้ามาจะพังตอน
# insert หลัง embedding เสร็จไปแล้วเป็นชั่วโมง ที่นี่จึงกันไว้ก่อนเริ่ม
REQUIRED_EMBED_MODEL = "bge-m3"
REQUIRED_EMBED_DIM = 1024

# ความยาวสูงสุดของข้อความผิดพลาดที่เก็บลงฐานข้อมูล
_ERROR_MAX = 300


class JobError(Exception):
    """งานนี้ทำไม่ได้ — ข้อความต้องปลอดภัยพอที่จะเก็บลงฐานข้อมูลและใส่ใน log

    ห้ามใส่ที่อยู่ไฟล์ในเครื่อง DSN token หรือเนื้อ PDF ลงในข้อความนี้
    """


@dataclass(frozen=True)
class Job:
    decision_id: str
    crawl_source_id: str
    approved_sha256: str
    course_code: str
    course_title: str | None
    staging_path: str | None
    source_sha256: str | None
    source_status: str
    source_url: str


# ---- สัญญาของ embedding ---------------------------------------------------
def check_embedding_contract(conn: psycopg.Connection) -> None:
    """ตรวจสามชั้นก่อนเริ่ม embedding — ผิดชั้นใดให้หยุดก่อนเขียนอะไรลงคลังความรู้

    1. ค่าใน environment ที่ pipeline.ingest.run() จะอ่านจริง
    2. มิติของคอลัมน์ในฐานข้อมูล — ใช้ query เดียวกับด่านที่ backend มีอยู่แล้ว
       (backend/app/main.py:32-35) เพื่อไม่ให้มีสองความจริง
    3. ความยาวของเวกเตอร์ที่โมเดลคืนมาจริง — ข้อ 1 พิสูจน์แค่ว่าตั้งค่าไว้ถูก
       ไม่ได้พิสูจน์ว่าโมเดลที่ตอบกลับมาให้เวกเตอร์ขนาดนั้นจริง
    """
    model = os.environ.get("EMBED_MODEL")
    if model != REQUIRED_EMBED_MODEL:
        raise JobError(f"embed_model_mismatch: ต้องเป็น {REQUIRED_EMBED_MODEL} "
                       f"แต่ EMBED_MODEL = {model!r}")

    raw_dim = os.environ.get("EMBED_DIM")
    if raw_dim is None or not raw_dim.isdigit() or int(raw_dim) != REQUIRED_EMBED_DIM:
        raise JobError(f"embed_dim_mismatch: ต้องเป็น {REQUIRED_EMBED_DIM} "
                       f"แต่ EMBED_DIM = {raw_dim!r}")

    with conn.cursor() as cur:
        cur.execute("SELECT atttypmod AS dim FROM pg_attribute "
                    "WHERE attrelid = 'course_chunks'::regclass AND attname = 'embedding'")
        row = cur.fetchone()
    db_dim = row["dim"] if row else None
    if db_dim != REQUIRED_EMBED_DIM:
        raise JobError(f"embed_dim_mismatch: คอลัมน์ course_chunks.embedding = {db_dim} "
                       f"แต่สัญญาคือ {REQUIRED_EMBED_DIM}")

    base_url = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    try:
        vector = OllamaConnector(base_url=base_url, embed_model=model).embed("ตรวจมิติ")
    except LLMConnectionError as e:
        raise JobError(f"embed_probe_failed: {type(e).__name__}") from e
    if len(vector) != REQUIRED_EMBED_DIM:
        raise JobError(f"embed_probe_mismatch: โมเดลคืนเวกเตอร์ {len(vector)} มิติ "
                       f"แต่สัญญาคือ {REQUIRED_EMBED_DIM}")


# ---- ตรวจไฟล์ใน staging -------------------------------------------------
def staging_root() -> Path:
    """โฟลเดอร์ staging จาก environment — ไม่มีค่าแปลว่าปิด ไม่ถอยไปใช้ cwd

    ชื่อตัวแปรเดียวกับที่ backend ใช้ (backend/app/core/config.py::crawl_staging_dir)
    เพื่อให้ทั้งสองฝั่งชี้ที่เดียวกันเสมอ
    """
    raw = (os.environ.get("CRAWL_STAGING_DIR") or "").strip()
    if not raw:
        raise JobError("staging_dir_unset: ไม่ได้ตั้ง CRAWL_STAGING_DIR")
    root = Path(raw).resolve()
    if not root.is_dir():
        raise JobError("staging_dir_invalid: CRAWL_STAGING_DIR ไม่ใช่โฟลเดอร์ที่มีอยู่")
    return root


def resolve_staged(root: Path, staging_path: str | None) -> Path:
    """คลี่ที่อยู่ไฟล์แล้วยืนยันว่าอยู่ใต้ root จริง

    ใช้ Path.resolve() แล้วเทียบด้วย is_relative_to ไม่ใช่เทียบสตริงนำหน้า เพราะ
    การเทียบสตริงหลุดได้ทั้งจาก ../ จาก symlink/junction ที่ชี้ออกนอก และจากโฟลเดอร์
    ข้างเคียงที่ชื่อขึ้นต้นเหมือนกัน (เช่น /srv/staging-old เทียบกับ /srv/staging)
    """
    if not staging_path:
        raise JobError("staged_path_missing: แถวนี้ไม่มีที่อยู่ไฟล์ใน staging")
    resolved = Path(staging_path).resolve()
    if not resolved.is_relative_to(root):
        raise JobError("path_outside_staging_root: ที่อยู่ไฟล์ชี้ออกนอกโฟลเดอร์ที่อนุญาต")
    if not resolved.exists():
        raise JobError("staged_file_missing: ไม่พบไฟล์ที่ฐานข้อมูลอ้างถึง")
    if not resolved.is_file():
        raise JobError("staged_not_regular_file: ที่อยู่นี้ไม่ใช่ไฟล์ปกติ")
    return resolved


def validate_pdf(path: Path, approved_sha: str, source_sha: str | None) -> int:
    """ตรวจไฟล์ด้วยตัวตรวจเดิมของ pipeline แล้วยืนยันลายนิ้วมือสองฝั่ง คืนจำนวนหน้า

    ใช้ pipeline.extract_pdf.extract_pdf() ซึ่งเป็นตัวเดียวกับที่ run() จะเรียก จึงได้
    ด่านเดิมครบชุด: ขนาดไฟล์ในช่วงที่ยอมรับ · ลายเซ็น %PDF- · เปิดด้วย fitz ได้จริง ·
    ไม่ใช่ไฟล์ที่ใส่รหัส · และ sha256 คิดจาก bytes ชุดเดียวกับที่ parse
    ถ้าผ่านที่นี่ก็จะผ่านตอน run() เรียกเช่นกัน เพราะเป็นโค้ดเส้นเดียวกัน
    """
    try:
        doc = extract_pdf(path)
    except InvalidPdfError as e:
        # ข้อความของ InvalidPdfError มีที่อยู่ไฟล์อยู่ในบางกรณี จึงไม่เอามาต่อ
        raise JobError(f"pdf_invalid: {type(e).__name__}") from e
    except Exception as e:
        raise JobError(f"pdf_unreadable: {type(e).__name__}") from e

    if doc.file_sha256 != approved_sha:
        raise JobError("sha_mismatch_decision: เนื้อไฟล์ไม่ตรงกับที่ผู้ดูแลอนุมัติ")
    if source_sha is not None and doc.file_sha256 != source_sha:
        raise JobError("sha_mismatch_source: เนื้อไฟล์ไม่ตรงกับที่บันทึกไว้ในแถวต้นทาง")
    if doc.page_count <= 0:
        raise JobError("pdf_no_pages: เปิดได้แต่ไม่มีหน้า")
    return doc.page_count


# ---- หลักสูตรที่มีอยู่แล้วเท่านั้น ---------------------------------------
def lock_existing_course(conn: psycopg.Connection, course_code: str) -> tuple[str, str]:
    """หาหลักสูตรจากรหัสที่ผู้ดูแลยืนยัน และตรึงแถวไว้ตลอดงาน คืน (id, title)

    ล็อกด้วย FOR SHARE เพราะ get_or_create_course() ใน pipeline/ingest.py:104 จะสร้าง
    หลักสูตรใหม่ถ้าหารหัสนั้นไม่เจอ (บรรทัด 111-115) ถ้าใครลบหลักสูตรทิ้งระหว่างที่เรา
    ตรวจแล้วกับตอนที่ run() ค้นหา สาขานั้นจะถูกสร้างขึ้นใหม่เงียบ ๆ ซึ่งห้ามเกิด
    การตรึงแถวทำให้คำสั่งลบต้องรอจนงานจบ run() จึงเห็นแถวเดิมและเข้าทางที่ใช้ของเดิม
    เสมอ — พิสูจน์ได้ว่าไม่มีการสร้างหลักสูตรใหม่โดยไม่ต้องแก้ ingest.py

    FOR SHARE ใช้ได้ด้วยสิทธิ์ของ advisor_ingest ที่มี UPDATE บน courses อยู่แล้ว
    (db/20-roles.sh:53) และไม่กันการอ่านธรรมดาของ run()
    """
    with conn.cursor() as cur:
        cur.execute("SELECT id::text AS id, title FROM courses WHERE code = %s FOR SHARE",
                    (course_code,))
        row = cur.fetchone()
    if row is None:
        raise JobError("course_not_found: ไม่มีหลักสูตรรหัสนี้ในระบบ")
    return row["id"], row["title"]


# ---- หาเอกสารที่นำเข้าสำเร็จ --------------------------------------------
def completed_document(conn: psycopg.Connection, sha256: str, course_id: str) -> str:
    """หา course_documents ที่ทำเสร็จแล้วของ sha นี้ในหลักสูตรนี้ ต้องเจอแถวเดียว

    ต้องกรองด้วย course_id ด้วย ไม่ใช่ sha เดียว เพราะไฟล์เนื้อเดียวกันอยู่ได้หลาย
    หลักสูตร (unique key ของ course_documents คือ (course_id, file_sha256) —
    db/migrations ของ schema เดิม) ถ้าค้นด้วย sha อย่างเดียวแล้วหยิบแถวแรก
    จะผูกเอกสารของหลักสูตรอื่นเข้ากับการอนุมัตินี้โดยไม่มีใครรู้
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id::text AS id, course_id::text AS course_id, extraction_status
              FROM course_documents WHERE file_sha256 = %s
        """, (sha256,))
        rows = cur.fetchall()

    mine = [r for r in rows if r["course_id"] == course_id]
    done = [r for r in mine if r["extraction_status"] == "done"]

    if len(done) > 1:
        raise JobError(f"document_ambiguous: พบเอกสารที่ทำเสร็จ {len(done)} แถวของ sha เดียวกัน")
    if done:
        return done[0]["id"]

    if mine:
        status = mine[0]["extraction_status"]
        raise JobError(f"document_not_done: มีแถวเอกสารแล้วแต่สถานะยังเป็น {status!r}")
    if rows:
        # sha นี้เคยนำเข้าไปแล้วในหลักสูตรอื่น already_ingested() ที่ ingest.py:186 จึง
        # คืนค่าออกไปโดยไม่สร้างอะไรให้หลักสูตรที่อนุมัติไว้ ต้องให้คนมาตัดสิน
        raise JobError("document_course_conflict: เนื้อไฟล์นี้อยู่ในคลังแล้วแต่คนละหลักสูตร")
    raise JobError("document_not_found: run() จบแล้วแต่ไม่พบเอกสารที่ทำเสร็จของ sha นี้")


# ---- นำไฟล์ไปไว้ที่เก็บเอกสาร -------------------------------------------
def publish_document(sha256: str, source: Path, filename: str) -> str:
    """วางสำเนา PDF ไว้ใน DOCUMENTS_DIR เพื่อให้ /documents/{id}/pdf เปิดได้

    backend หาไฟล์ด้วย sha256 จากการสแกนโฟลเดอร์ ไม่ได้ใช้ storage_path ในฐานข้อมูล
    (backend/app/services/document_store.py:94-98) ชื่อไฟล์จึงไม่สำคัญต่อการค้น
    แต่ยังใช้ชื่อเดิมของไฟล์ใน staging เพื่อให้คนเปิดโฟลเดอร์แล้วรู้ว่าไฟล์ไหนคืออะไร

    คืนที่อยู่ที่วางไว้ (ใช้ใน log ฝั่งผู้รัน ไม่ได้เก็บลงฐานข้อมูล)
    ไม่ย้ายและไม่ลบไฟล์ต้นทางใน staging
    """
    raw = (os.environ.get("DOCUMENTS_DIR") or "").strip()
    if not raw:
        raise JobError("documents_dir_unset: ไม่ได้ตั้ง DOCUMENTS_DIR")
    root = Path(raw).resolve()
    if not root.is_dir():
        raise JobError("documents_dir_invalid: DOCUMENTS_DIR ไม่ใช่โฟลเดอร์ที่มีอยู่")

    # มีไฟล์เนื้อเดียวกันอยู่แล้วให้ใช้ของเดิม ไม่เขียนซ้ำ
    for existing in sorted(root.rglob("*.pdf")):
        if not existing.is_file():
            continue
        try:
            if _sha256_of(existing) == sha256:
                return str(existing)
        except OSError:
            continue

    target = root / filename
    if target.exists():
        # ชื่อซ้ำแต่เนื้อไม่เหมือน (ถ้าเหมือนจะเจอในลูปข้างบนไปแล้ว) ห้ามเขียนทับของคนอื่น
        target = root / f"{sha256[:12]}_{filename}"
        if target.exists():
            raise JobError("publish_name_collision: มีไฟล์ชื่อเดียวกันอยู่แล้วแต่เนื้อต่างกัน")

    # เขียนลงชื่อชั่วคราวในโฟลเดอร์เดียวกันแล้ว replace เพื่อให้ตัวที่ไปสแกนเจอ
    # ไฟล์ที่สมบูรณ์เท่านั้น ไม่เคยเจอไฟล์ครึ่ง ๆ
    tmp = target.with_name(f".publish_{sha256[:12]}_{target.name}")
    try:
        shutil.copyfile(source, tmp)
        os.replace(tmp, target)
    except OSError as e:
        Path(tmp).unlink(missing_ok=True)
        raise JobError(f"publish_failed: {type(e).__name__}") from e

    if not target.is_relative_to(root):        # ด่านซ้ำ กันชื่อไฟล์ที่พาหลุดออกนอก
        target.unlink(missing_ok=True)
        raise JobError("publish_outside_root: ปลายทางหลุดออกนอกโฟลเดอร์เอกสาร")
    return str(target)


def _sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


# ---- ฐานข้อมูล ----------------------------------------------------------
CLAIM_SQL = """
    SELECT d.id::text                AS decision_id,
           d.crawl_source_id::text   AS crawl_source_id,
           d.file_sha256             AS approved_sha256,
           d.course_code             AS course_code,
           d.course_title            AS course_title,
           s.staging_path            AS staging_path,
           s.file_sha256             AS source_sha256,
           s.status                  AS source_status,
           s.source_url              AS source_url
      FROM mko.crawl_decisions d
      JOIN mko.crawl_sources  s ON s.id = d.crawl_source_id
     WHERE d.superseded_at     IS NULL
       AND d.decision          =  'approve'
       AND d.ingest_finished_at IS NULL
       AND d.id <> ALL(%(skip)s::uuid[])
     ORDER BY d.decided_at, d.id
       FOR UPDATE OF d SKIP LOCKED
     LIMIT 1
"""


def claim(conn: psycopg.Connection, skip: list[str]) -> Job | None:
    """ยึดงานถัดไปหนึ่งงาน หรือคืน None ถ้าไม่มีงานที่ยึดได้

    ยึดทีละงานโดยตั้งใจ ถ้ายึดหลายงานใน transaction เดียวแล้วไปทำงานยาวกับงานแรก
    งานที่เหลือจะถูกล็อกไว้เฉย ๆ ทำให้ worker ตัวอื่นหยิบไปทำไม่ได้ทั้งที่ว่างอยู่

    SKIP LOCKED ข้ามแถวที่ worker ตัวอื่นถืออยู่ ส่วน skip คือรายการงานที่รอบนี้
    ทำไปแล้ว (สำเร็จหรือพลาด) กันหยิบซ้ำภายในโปรเซสเดียวกันจนวนไม่จบ

    ตั้ง ingest_started_at ใน transaction เดียวกัน ค่าจึงยังไม่ปรากฏต่อผู้อื่นจนกว่าจะ
    commit — เจ้าของงานที่จริงคือ row lock ไม่ใช่คอลัมน์นี้ ผลพลอยได้คือถ้า worker ตาย
    transaction ถูกยกเลิกและงานกลับเป็นงานว่างทันที ไม่มี claim ค้างให้ต้องเก็บกวาด
    """
    with conn.cursor() as cur:
        cur.execute(CLAIM_SQL, {"skip": skip})
        row = cur.fetchone()
        if row is None:
            return None
        cur.execute("""
            UPDATE mko.crawl_decisions
               SET ingest_started_at = clock_timestamp(), ingest_error = NULL
             WHERE id = %s AND superseded_at IS NULL AND ingest_finished_at IS NULL
        """, (row["decision_id"],))
        if cur.rowcount != 1:
            raise JobError("claim_lost: แถวเปลี่ยนสถานะระหว่างยึดงาน")
    return Job(**row)


def finalize(conn: psycopg.Connection, job: Job, document_id: str) -> str:
    """ปิดงานให้สำเร็จใน transaction เดียวกับที่ถือ lock อยู่ คืนบันทึกสถานะของต้นทาง

    อัปเดต crawl_sources แบบมีเงื่อนไขว่า file_sha256 ต้องยังเป็นค่าที่อนุมัติไว้ ถ้า
    crawler โหลดไฟล์ใหม่ทับระหว่างที่ทำงาน แถวต้นทางตอนนี้พูดถึงเนื้อไฟล์คนละชุด
    การไปตั้ง ingested ให้มันจะเท่ากับใช้การอนุมัติเก่ารับรองของใหม่ จึงไม่ทำ
    แต่ก็ปิด decision ให้สำเร็จ เพราะงานที่ทำไปแล้วถูกต้องและต้องไม่ถูกทำซ้ำ
    """
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE mko.crawl_sources
               SET status = 'ingested', document_id = %(doc)s
             WHERE id = %(sid)s AND file_sha256 = %(sha)s
        """, {"doc": document_id, "sid": job.crawl_source_id, "sha": job.approved_sha256})
        source_updated = cur.rowcount == 1

        note = None if source_updated else "source_sha_changed_after_ingest"
        cur.execute("""
            UPDATE mko.crawl_decisions
               SET document_id = %(doc)s,
                   ingest_finished_at = clock_timestamp(),
                   ingest_error = %(note)s
             WHERE id = %(did)s AND superseded_at IS NULL AND ingest_finished_at IS NULL
        """, {"doc": document_id, "note": note, "did": job.decision_id})
        if cur.rowcount != 1:
            raise JobError("finalize_lost: แถวการอนุมัติเปลี่ยนสถานะก่อนปิดงาน")
    return "ingested" if source_updated else "source เปลี่ยนไฟล์แล้ว จึงไม่ตั้ง ingested"


def record_error(database_url: str, decision_id: str, detail: str) -> bool:
    """บันทึกความผิดพลาดในอีก transaction หนึ่ง เพราะของเดิมถูก rollback ไปแล้ว

    ทำแบบเดียวกับ transaction C ใน pipeline/ingest.py:221 — ต้องเปิดใหม่ เพราะเขียน
    อะไรลง transaction ที่ล้มไปแล้วไม่ได้ คืน True ถ้าบันทึกได้จริง
    """
    try:
        with psycopg.connect(database_url, row_factory=dict_row) as conn, conn.cursor() as cur:
            cur.execute("""
                UPDATE mko.crawl_decisions
                   SET ingest_started_at = coalesce(ingest_started_at, clock_timestamp()),
                       ingest_error = %s
                 WHERE id = %s AND superseded_at IS NULL AND ingest_finished_at IS NULL
            """, (detail[:_ERROR_MAX], decision_id))
            return cur.rowcount == 1
    except psycopg.Error as e:
        logger.error("บันทึกข้อผิดพลาดของงานไม่ได้: %s", type(e).__name__)
        return False


# ---- ทำงานหนึ่งงาน ------------------------------------------------------
def process(conn: psycopg.Connection, job: Job, scratch: Path) -> str:
    """ตรวจ นำเข้า แล้วปิดงาน — ทุก path ที่ล้มเหลวโยน JobError ออกไป

    ลำดับตั้งใจให้ของที่ถูกที่สุดและไม่มีผลข้างเคียงมาก่อนของที่แพง
        ตรวจไฟล์ -> ตรึงหลักสูตร -> ตรวจสัญญา embedding -> คัดลอกเป็นสำเนาส่วนตัว
        -> run() -> หาเอกสาร -> วางไฟล์ในที่เก็บ -> ปิดงาน
    """
    root = staging_root()
    staged = resolve_staged(root, job.staging_path)

    # ทำสำเนาส่วนตัว "ก่อน" ตรวจ แล้วตรวจกับสำเนานั้น
    #
    # ลำดับนี้สำคัญ ถ้าตรวจไฟล์ใน staging ก่อนแล้วค่อยคัดลอก จะเหลือช่องว่างที่ไฟล์
    # ถูกสลับได้ระหว่างสองขั้น (crawler เขียนโฟลเดอร์นั้นอยู่) แล้วเราจะได้แค่ "ตรวจจับ"
    # การสลับ ไม่ได้ป้องกันมัน — งานที่ควรสำเร็จจะกลายเป็นงานล้มเหลวเพราะจับเวลาไม่ดี
    #
    # ทำสำเนาก่อนแล้วตรวจสำเนา ทำให้ bytes ที่ผ่านการตรวจกับ bytes ที่ run() อ่าน
    # (ingest.py:182 อ่านไฟล์เองอีกครั้ง) เป็นไฟล์เดียวกันที่อยู่ในโฟลเดอร์ของ worker
    # ซึ่งไม่มีใครอื่นเขียนได้ การสลับไฟล์ใน staging หลังจากนี้จึงไม่มีผลใด
    #
    # คงชื่อไฟล์เดิมไว้ เพราะ run() ใช้ Path(pdf_path).name เป็น original_filename
    # (ingest.py:207) ถ้าเปลี่ยนชื่อ ชื่อเอกสารในคลังจะกลายเป็นชื่อไฟล์ชั่วคราว
    private = scratch / staged.name
    try:
        shutil.copyfile(staged, private)
    except OSError as e:
        raise JobError(f"snapshot_failed: {type(e).__name__}") from e

    validate_pdf(private, job.approved_sha256, job.source_sha256)

    course_id, course_title = lock_existing_course(conn, job.course_code)
    check_embedding_contract(conn)

    from pipeline.ingest import run as ingest_run     # นำเข้าตอนใช้ ตัวเดิม ไม่แก้

    try:
        ingest_run(str(private), title=course_title, course_code=job.course_code, provider=None)
    except SystemExit as e:
        # run() ใช้ SystemExit เมื่อไม่มี INGEST_DATABASE_URL (ingest.py:174) ซึ่งจะฆ่า
        # โปรเซสทั้งตัวถ้าไม่ดัก และรวม exit code 0 ด้วย เพราะ SystemExit(0) ก็ยังหมายถึง
        # ว่า run() ไม่ได้ทำงานให้จบ
        raise JobError(f"ingest_systemexit: code={e.code!r}") from e
    except Exception as e:
        raise JobError(f"ingest_failed: {type(e).__name__}") from e

    # run() คืน None เสมอ (ingest.py:170) การไม่โยน exception จึงไม่ใช่หลักฐานว่าสำเร็จ
    # หลักฐานคือมีแถวเอกสารที่ extraction_status='done' ของ sha และหลักสูตรนี้
    document_id = completed_document(conn, job.approved_sha256, course_id)
    publish_document(job.approved_sha256, private, staged.name)
    return finalize(conn, job, document_id)


def work(database_url: str, max_jobs: int) -> tuple[int, int]:
    """ทำงานไม่เกิน max_jobs งานแล้วจบ คืน (สำเร็จ, ล้มเหลว)

    ไม่มีการวนรอ ไม่มี sleep ไม่มีการเฝ้าคิว — หมดงานที่ยึดได้ก็ออก
    """
    done = failed = 0
    seen: list[str] = []
    with tempfile.TemporaryDirectory(prefix="ingest_worker_") as tmp:
        scratch = Path(tmp)
        while done + failed < max_jobs:
            conn = psycopg.connect(database_url, row_factory=dict_row)
            try:
                # ไม่รอ lock นานเกินจำเป็น ถ้ามี worker อื่นถืออยู่ SKIP LOCKED จะข้ามให้
                # อยู่แล้ว เพดานนี้กันกรณีรออย่างอื่นค้าง เช่นคำสั่งถอนที่ยังไม่จบ
                with conn.cursor() as cur:
                    cur.execute("SET lock_timeout = '5s'")
                job = claim(conn, seen)
                if job is None:
                    conn.rollback()
                    break
                seen.append(job.decision_id)
                logger.info("ยึดงาน decision=%s source=%s", job.decision_id, job.source_url)
                try:
                    outcome = process(conn, job, scratch)
                except JobError as e:
                    conn.rollback()
                    saved = record_error(database_url, job.decision_id, str(e))
                    logger.error("งานล้มเหลว decision=%s: %s (บันทึกผล: %s)",
                                 job.decision_id, e, "สำเร็จ" if saved else "ไม่สำเร็จ")
                    failed += 1
                    if not saved:
                        raise
                else:
                    conn.commit()
                    done += 1
                    logger.info("งานสำเร็จ decision=%s · %s", job.decision_id, outcome)
            finally:
                conn.close()
    return done, failed


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Phase 3C — นำไฟล์ที่ผู้ดูแลอนุมัติแล้วเข้าคลังความรู้ (รันครั้งเดียวแล้วจบ)")
    ap.add_argument("--database-url", default=os.environ.get("INGEST_DATABASE_URL"),
                    help="ค่าเริ่มต้นอ่านจาก INGEST_DATABASE_URL (role advisor_ingest)")
    ap.add_argument("--max-jobs", type=int, default=1,
                    help="จำนวนงานสูงสุดในรอบนี้ (ค่าเริ่มต้น 1)")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not args.database_url:
        raise SystemExit("ต้องระบุ --database-url หรือตั้ง INGEST_DATABASE_URL")
    if args.max_jobs < 1:
        raise SystemExit("--max-jobs ต้องมากกว่าศูนย์")

    # run() อ่าน INGEST_DATABASE_URL จาก environment เอง (ingest.py:172) จึงต้องตรงกับ
    # ที่ worker ใช้ ไม่งั้นจะตรวจฐานหนึ่งแต่เขียนอีกฐานหนึ่ง
    os.environ["INGEST_DATABASE_URL"] = args.database_url

    done, failed = work(args.database_url, args.max_jobs)
    logger.info("---- สรุป ---- สำเร็จ %d · ล้มเหลว %d", done, failed)
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
