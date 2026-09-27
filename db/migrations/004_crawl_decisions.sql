-- =====================================================================
-- 004_crawl_decisions.sql — การตัดสินใจของคนต่อไฟล์ที่ crawler พบ (Phase 3A)
--
-- ดูแบบใน docs/AUTOMATED_INGESTION_PHASE3_DESIGN.md
--
-- หลักเดียวกับ 001–003:
--   - สร้างเฉพาะของใหม่ใน schema `mko` ไม่ ALTER ไม่ DROP ตารางหรือวิวใด
--   - ไม่แตะ courses, course_documents, course_chunks หรืออะไรใน public
--   - ไม่แก้ v_crawl_pending ของ 003 (ยังเป็นของ crawler เหมือนเดิม)
--   - รันซ้ำได้ (IF NOT EXISTS / CREATE OR REPLACE)
--
-- ทำไมต้องมีตารางนี้แยกจาก crawl_sources
-- --------------------------------------
-- pipeline/crawl/state.py::upsert() เขียน status และ needs_review ทับทุกรอบที่ crawl
-- ไม่มีเงื่อนไข ถ้าเก็บผลอนุมัติไว้ในคอลัมน์ของ crawl_sources การ crawl รอบถัดไปจะลบทิ้ง
-- แถวที่คนกด "ไม่เกี่ยวข้อง" จะกลับเข้าคิวอีก และแถวที่นำเข้าแล้วแต่จับคู่หลักสูตรกำกวม
-- จะติดค้างในคิวตลอดไปเพราะ needs_review ถูกตั้งเป็น true ใหม่ทุกรอบ
--
-- แยกออกมาเป็นอีกตารางแล้ว crawler เขียนทับไม่ได้เพราะอยู่คนละตาราง และ backend
-- ไม่ต้องมีสิทธิ์เขียน crawl_sources เลย — ดูส่วนสิทธิ์ท้ายไฟล์
--
-- ทำไมผูกกับ file_sha256 ไม่ใช่ผูกกับลิงก์
-- ----------------------------------------
-- หลักเดียวกับ mko.review_decisions ใน 002 ที่ผูกกับ (เอกสาร, field, ค่า) ไม่ใช่กับ
-- แถวของรอบสกัด — คนอนุมัติ "เนื้อไฟล์นี้" ไม่ใช่ "URL นี้ตลอดไป" ถ้าคณะอัปโหลด
-- ไฟล์ใหม่ทับ URL เดิม sha จะเปลี่ยน การอนุมัติเดิมจึงไม่ครอบของใหม่โดยอัตโนมัติ
-- และแถวนั้นกลับเข้าคิวให้คนดูอีกครั้ง ซึ่งเป็นสิ่งที่ต้องการ
--
-- ทำไมถอนด้วย superseded_at ไม่ใช่ DELETE
-- ---------------------------------------
-- ประวัติว่าใครตัดสินอะไรเมื่อไหร่ต้องไม่หาย และไม่ได้ให้สิทธิ์ DELETE ไว้ตั้งแต่ระดับ
-- ฐานข้อมูล การถอนคือการเพิ่มเวลา superseded_at ให้แถวเดิม แล้วแถวนั้นหมดสภาพ
-- เป็นการตัดสินใจที่ใช้อยู่ ทำให้ตัดสินใหม่ได้ — หลักเดียวกับ 002
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS mko.crawl_decisions (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    crawl_source_id  UUID NOT NULL REFERENCES mko.crawl_sources(id) ON DELETE CASCADE,

    -- ลายนิ้วมือของไฟล์ที่คนตัดสิน — ตัวผูกการตัดสินใจกับเนื้อไฟล์
    -- NOT NULL โดยตั้งใจ: แถวที่ยังโหลดไฟล์ไม่สำเร็จ (status='error', file_sha256 IS NULL)
    -- ยังไม่มีอะไรให้ตัดสิน ต้องรอให้ crawl ได้ไฟล์มาก่อน
    file_sha256      TEXT NOT NULL CHECK (file_sha256 ~ '^[0-9a-f]{64}$'),

    decision         TEXT NOT NULL CHECK (decision IN ('approve', 'ignore')),
    -- อีเมลของผู้ใช้ที่ล็อกอิน มาจากฝั่งเซิร์ฟเวอร์เท่านั้น ไม่รับจาก request body
    decided_by       TEXT NOT NULL CHECK (length(btrim(decided_by)) > 0),
    decided_at       TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    note             TEXT,

    -- หลักสูตรที่ "คนยืนยัน" ไม่ใช่ที่ระบบเดา — Phase 3 v1 ต้องเป็นรหัสที่มีอยู่แล้ว
    -- ใน public.courses การตรวจทำที่ชั้นแอป (backend ไม่มีสิทธิ์สร้าง course)
    course_code      TEXT,
    course_title     TEXT,

    -- ผลการนำเข้า — Phase 3B (ingest-worker) เท่านั้นที่เขียนสามคอลัมน์นี้
    ingest_started_at  TIMESTAMPTZ,
    ingest_finished_at TIMESTAMPTZ,
    ingest_error       TEXT,
    document_id        UUID REFERENCES public.course_documents(id) ON DELETE SET NULL,

    -- การถอนการตัดสินใจ
    superseded_at    TIMESTAMPTZ,
    superseded_by    TEXT,

    CONSTRAINT crawl_decisions_supersede_complete
        CHECK ((superseded_at IS NULL) = (superseded_by IS NULL)),
    -- อนุมัติต้องระบุหลักสูตรเสมอ ส่วน "ไม่เกี่ยวข้อง" ไม่ต้อง
    CONSTRAINT crawl_decisions_approve_has_course
        CHECK (decision <> 'approve' OR course_code IS NOT NULL),
    CONSTRAINT crawl_decisions_finished_after_started
        CHECK (ingest_finished_at IS NULL OR ingest_started_at IS NOT NULL),
    -- นำเข้าแล้วต้องเป็นการอนุมัติ ไม่ใช่การ ignore
    CONSTRAINT crawl_decisions_only_approve_ingests
        CHECK (decision = 'approve' OR (ingest_started_at IS NULL AND document_id IS NULL))
);

-- ไฟล์หนึ่งมีการตัดสินใจที่ยังใช้อยู่ได้ครั้งเดียว
-- กันสองคนกดพร้อมกันที่ระดับฐานข้อมูล ไม่ใช่แค่ที่ระดับโค้ด — สองคำขอที่มาถึงพร้อมกัน
-- ตัวที่สองจะได้ 23505 ไม่ใช่ทั้งสองตัวสำเร็จ
CREATE UNIQUE INDEX IF NOT EXISTS uq_crawl_decisions_active
    ON mko.crawl_decisions (crawl_source_id, file_sha256) WHERE superseded_at IS NULL;

-- คิวงานของ ingest-worker ใน Phase 3B — อนุมัติแล้ว ยังไม่ได้นำเข้า
CREATE INDEX IF NOT EXISTS idx_crawl_decisions_todo
    ON mko.crawl_decisions (decided_at)
    WHERE superseded_at IS NULL AND decision = 'approve' AND ingest_finished_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_crawl_decisions_source
    ON mko.crawl_decisions (crawl_source_id);

-- ---------------------------------------------------------------------
-- คิวงานของคนตรวจ
--
-- ต่างจาก v_crawl_pending ของ 003 สองเรื่อง
--   1. กรองแถวที่มีการตัดสินใจที่ยังใช้อยู่ออก — คนกดแล้วต้องหายจากคิว และต้องไม่
--      กลับมาเมื่อ crawler รอบถัดไปตั้ง needs_review ใหม่
--   2. ไม่มี staging_path — ที่อยู่ไฟล์บนเซิร์ฟเวอร์ไม่ควรออกไปถึงเบราว์เซอร์
--      บอกแค่ว่ามีไฟล์ให้เปิดดูหรือไม่
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW mko.v_crawl_queue AS
SELECT s.id, s.source_url, s.page_url, s.page_title, s.link_text,
       s.course_code, s.course_label, s.match_confidence, s.match_score, s.match_candidates,
       s.needs_review, s.review_reason, s.status,
       s.content_length, s.file_sha256, s.previous_sha256,
       (s.staging_path IS NOT NULL) AS has_staged_file,
       s.last_checked_at, s.first_seen_at
  FROM mko.crawl_sources s
 WHERE (s.status IN ('new', 'changed', 'downloaded', 'error') OR s.needs_review)
   AND NOT EXISTS (
        SELECT 1 FROM mko.crawl_decisions d
         WHERE d.crawl_source_id = s.id
           AND d.file_sha256 = s.file_sha256
           AND d.superseded_at IS NULL)
 ORDER BY s.needs_review DESC, s.last_checked_at DESC NULLS LAST;

-- ---------------------------------------------------------------------
-- สิทธิ์
--
-- backend (advisor_api) บันทึก "เจตนาของคน" ได้เท่านั้น ทำ ingestion ไม่ได้
--   - เขียน mko.crawl_sources ไม่ได้เลย  -> เปลี่ยนสถานะไฟล์ไม่ได้
--   - เขียน course_documents / course_chunks ไม่ได้ (จาก 20-roles.sh เดิม)
--   - แก้เนื้อการตัดสินใจที่บันทึกแล้วไม่ได้ แก้ได้แค่สองคอลัมน์ของการถอน
--   - แตะผลการนำเข้า (ingest_*, document_id) ไม่ได้ นั่นเป็นของ worker
--
-- SELECT แบบระบุคอลัมน์บน crawl_sources จำเป็นสำหรับ endpoint เปิดดู PDF ซึ่งต้องรู้
-- staging_path กับ file_sha256 ของแถวนั้น ให้เฉพาะสี่คอลัมน์ที่ต้องใช้จริง
-- แม้เขียนโค้ดผิดก็อ่าน approved_by, last_error หรือ http_etag ไม่ได้
-- ---------------------------------------------------------------------
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'advisor_api') THEN
        GRANT USAGE ON SCHEMA mko TO advisor_api;
        GRANT SELECT ON mko.v_crawl_queue TO advisor_api;
        GRANT SELECT (id, file_sha256, staging_path, status) ON mko.crawl_sources TO advisor_api;
        GRANT SELECT, INSERT ON mko.crawl_decisions TO advisor_api;
        GRANT UPDATE (superseded_at, superseded_by) ON mko.crawl_decisions TO advisor_api;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'advisor_ingest') THEN
        -- worker ของ Phase 3B อ่านคิวและบันทึกผลการนำเข้า
        GRANT SELECT ON mko.v_crawl_queue TO advisor_ingest;
        GRANT SELECT, INSERT, UPDATE ON mko.crawl_decisions TO advisor_ingest;
    END IF;
    -- ไม่ให้ DELETE แก่ใครทั้งสิ้น ประวัติการตัดสินใจต้องลบไม่ได้
END;
$$;

INSERT INTO mko.schema_migrations (version) VALUES ('004_crawl_decisions')
    ON CONFLICT (version) DO NOTHING;

COMMIT;
