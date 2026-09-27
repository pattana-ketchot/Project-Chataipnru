-- =====================================================================
-- 003_crawl_sources.sql — สถานะของลิงก์ PDF ที่ crawler เฝ้าดู (Phase 2)
--
-- ดูการวิเคราะห์ใน docs/AUTOMATED_INGESTION_ANALYSIS.md
-- ผลสำรวจรอบแรกใน docs/CRAWL_PDF_DISCOVERY_REPORT.md
--
-- หลักเดียวกับ 001 และ 002:
--   - สร้างเฉพาะของใหม่ใน schema `mko` ไม่ ALTER ไม่ DROP ตารางใดๆ
--   - ไม่แตะ course_documents, course_chunks หรืออะไรใน public
--   - รันซ้ำได้ (IF NOT EXISTS)
--
-- ทำไมอยู่ใน mko ไม่ใช่ public
-- ---------------------------
-- public เก็บข้อมูลที่ระบบใช้ตอบคำถาม ส่วน mko เก็บข้อมูลกระบวนการทำงานและหลักฐาน
-- สถานะการ crawl เป็นข้อมูลกระบวนการ ไม่เคยถูกอ่านตอนตอบผู้ใช้
--
-- ทำไมไม่ให้สิทธิ์ DELETE
-- ----------------------
-- ประวัติการตรวจต้องไม่หาย แม้เว็บคณะถอดลิงก์ออกแล้ว การไม่ให้สิทธิ์ตั้งแต่ระดับ
-- ฐานข้อมูลปลอดภัยกว่าการหวังว่าโค้ดจะไม่เผลอสั่งลบ
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS mko.crawl_sources (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- ที่มาของลิงก์
    source_url         TEXT NOT NULL UNIQUE,
    page_url           TEXT,
    page_title         TEXT,               -- หัวเรื่องของหน้าที่พบลิงก์ ใช้เดาหลักสูตร
    link_text          TEXT,

    -- การจับคู่หลักสูตร — เก็บความมั่นใจไว้ด้วย ไม่ใช่เก็บแค่ผลลัพธ์
    course_code        TEXT,
    course_label       TEXT,
    match_confidence   TEXT CHECK (match_confidence IS NULL OR
                                   match_confidence IN ('high', 'medium', 'ambiguous', 'unknown')),
    match_score        NUMERIC(4,3) CHECK (match_score IS NULL OR
                                           (match_score >= 0 AND match_score <= 1)),
    -- ชื่อหลักสูตรทุกตัวที่ได้คะแนนเท่ากัน มากกว่าหนึ่งแปลว่าเลือกเองไม่ได้
    match_candidates   JSONB NOT NULL DEFAULT '[]'::jsonb,

    -- ธงรอคนตรวจ แยกจาก status เพราะเป็นคนละเรื่อง
    -- status บอกว่าไฟล์เดินทางไปถึงไหนแล้ว ส่วนธงนี้บอกว่าคนต้องเข้ามาดูก่อนไปต่อ
    -- ไฟล์หนึ่งเป็น downloaded และ needs_review พร้อมกันได้
    needs_review       BOOLEAN NOT NULL DEFAULT false,
    review_reason      TEXT,

    -- วงจรชีวิตของไฟล์
    --   new        พบลิงก์ครั้งแรก ยังไม่ได้เทียบอะไร
    --   unchanged  เทียบแล้วเหมือนของเดิมทุกอย่าง
    --   changed    URL เดิมแต่เนื้อไฟล์เปลี่ยน
    --   downloaded โหลดเก็บไว้ที่ staging แล้ว รออนุมัติ
    --   ingested   นำเข้าคลังความรู้แล้ว (Phase 3 เท่านั้นที่ตั้งค่านี้)
    --   ignored    คนดูแล้วบอกว่าไม่เกี่ยวข้อง ไม่ต้องถามอีก
    --   error      ดึงไม่สำเร็จ
    status             TEXT NOT NULL DEFAULT 'new'
                       CHECK (status IN ('new', 'unchanged', 'changed',
                                         'downloaded', 'ingested', 'ignored', 'error')),
    last_checked_at    TIMESTAMPTZ,
    last_error         TEXT,
    error_count        INTEGER NOT NULL DEFAULT 0 CHECK (error_count >= 0),

    -- ลายนิ้วมือฝั่งเซิร์ฟเวอร์ปลายทาง ใช้ข้ามการโหลดในรอบถัดไป
    http_etag          TEXT,
    http_last_modified TEXT,
    content_length     BIGINT CHECK (content_length IS NULL OR content_length >= 0),

    -- ลายนิ้วมือของเนื้อไฟล์ — ตัวชี้ขาดว่าซ้ำหรือไม่
    file_sha256        TEXT CHECK (file_sha256 IS NULL OR file_sha256 ~ '^[0-9a-f]{64}$'),
    previous_sha256    TEXT CHECK (previous_sha256 IS NULL OR previous_sha256 ~ '^[0-9a-f]{64}$'),
    staging_path       TEXT,               -- ที่เก็บไฟล์ที่รออนุมัติ

    -- ผูกกับเอกสารในคลัง ถ้าเคยนำเข้าแล้ว
    -- SET NULL เพราะลบเอกสารแล้วประวัติการ crawl ต้องไม่หายตาม
    document_id        UUID REFERENCES public.course_documents(id) ON DELETE SET NULL,

    -- การอนุมัติของคน
    approved_at        TIMESTAMPTZ,
    approved_by        TEXT,
    approval_note      TEXT,

    first_seen_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- อนุมัติแล้วต้องรู้ว่าใครอนุมัติเสมอ จะมีแค่เวลาโดยไม่มีชื่อไม่ได้
    CONSTRAINT crawl_sources_approval_complete
        CHECK ((approved_at IS NULL) = (approved_by IS NULL)),
    -- เก็บไฟล์ไว้ที่ staging แล้วต้องรู้ลายนิ้วมือของไฟล์นั้นเสมอ
    CONSTRAINT crawl_sources_staged_has_hash
        CHECK (staging_path IS NULL OR file_sha256 IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_crawl_sources_status
    ON mko.crawl_sources (status);
CREATE INDEX IF NOT EXISTS idx_crawl_sources_checked
    ON mko.crawl_sources (last_checked_at DESC);
CREATE INDEX IF NOT EXISTS idx_crawl_sources_course
    ON mko.crawl_sources (course_code);
-- ดัชนีบางส่วน — คิวงานของคนตรวจมีไม่กี่แถว ไม่ต้องทำดัชนีทั้งตาราง
CREATE INDEX IF NOT EXISTS idx_crawl_sources_needs_review
    ON mko.crawl_sources (last_checked_at DESC) WHERE needs_review;

DROP TRIGGER IF EXISTS trg_crawl_sources_updated_at ON mko.crawl_sources;
CREATE TRIGGER trg_crawl_sources_updated_at
    BEFORE UPDATE ON mko.crawl_sources
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- วิวสำหรับคิวงานของคนตรวจ — เห็นเฉพาะแถวที่ต้องตัดสินใจ
CREATE OR REPLACE VIEW mko.v_crawl_pending AS
SELECT id, source_url, page_url, page_title,
       course_code, course_label, match_confidence, match_score, match_candidates,
       needs_review, review_reason, status,
       content_length, file_sha256, previous_sha256, staging_path,
       last_checked_at, first_seen_at
FROM mko.crawl_sources
WHERE status IN ('new', 'changed', 'downloaded', 'error')
   OR needs_review
ORDER BY needs_review DESC, last_checked_at DESC NULLS LAST;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'advisor_ingest') THEN
        GRANT USAGE ON SCHEMA mko TO advisor_ingest;
        -- ไม่ให้ DELETE โดยตั้งใจ ประวัติการตรวจต้องไม่หาย
        GRANT SELECT, INSERT, UPDATE ON mko.crawl_sources TO advisor_ingest;
        GRANT SELECT ON mko.v_crawl_pending TO advisor_ingest;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'advisor_api') THEN
        -- backend อ่านคิวงานได้อย่างเดียว เผื่อทำหน้าแสดงผลให้ผู้ดูแลในอนาคต
        GRANT USAGE ON SCHEMA mko TO advisor_api;
        GRANT SELECT ON mko.v_crawl_pending TO advisor_api;
    END IF;
END;
$$;

INSERT INTO mko.schema_migrations (version) VALUES ('003_crawl_sources')
    ON CONFLICT (version) DO NOTHING;

COMMIT;
