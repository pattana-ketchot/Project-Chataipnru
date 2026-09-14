-- =====================================================================
-- 002_mko_review_publish.sql — ขั้นตรวจ ขั้นเผยแพร่ และบันทึกผลโหมด shadow (Phase 2)
--
-- ดูการออกแบบใน docs/MKO_STRUCTURED_DATA_DESIGN.md
--
-- หลักเดียวกับ 001:
--   - สร้างเฉพาะตาราง/view ใหม่ใน schema `mko` ไม่ ALTER / DROP ตารางใดๆ ไม่แตะ course_chunks
--   - รันซ้ำได้ (IF NOT EXISTS / CREATE OR REPLACE)
--
-- สิ่งที่เพิ่ม
--   review_decisions      ผลการตรวจของคน ผูกกับ (เอกสาร, field, ค่า) ไม่ผูกกับแถวของรอบสกัด ผลตรวจจึงไม่หายเมื่อสกัดใหม่
--   publications          การเผยแพร่แต่ละครั้ง
--   published_values      ค่าที่เผยแพร่ พร้อมไฟล์ หน้า และข้อความที่ยกมา (ภาพถ่ายของข้อมูล ณ ตอนเผยแพร่)
--   published_list_items  รายการที่เผยแพร่ พร้อมที่มา
--   v_live_*              ข้อมูลของการเผยแพร่ครั้งล่าสุด — สิ่งเดียวที่ backend อ่านได้
--   shadow_answers        บันทึกผลโหมด shadow: คำตอบจากฐานข้อมูลเทียบกับคำตอบที่ผู้ใช้ได้รับจริง
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS mko.review_decisions (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id      UUID NOT NULL REFERENCES public.course_documents(id) ON DELETE CASCADE,
    document_sha256  TEXT NOT NULL,
    field_key        TEXT NOT NULL,
    value_key        TEXT NOT NULL,   -- ค่าที่ตรวจในรูปที่ใช้เทียบ (ตัวเลข, ข้อความที่ fold แล้ว หรือแฮชของรายการ)
    shown_value      TEXT,            -- ค่าที่ผู้ตรวจเห็นตอนตัดสิน
    decision         TEXT NOT NULL CHECK (decision IN ('verified', 'rejected')),
    reviewer         TEXT NOT NULL CHECK (length(btrim(reviewer)) > 0),
    note             TEXT,
    decided_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    superseded_at    TIMESTAMPTZ
);
-- การตัดสินที่ยังมีผลมีได้หนึ่งรายการต่อ (เอกสาร, field, ค่า)
CREATE UNIQUE INDEX IF NOT EXISTS uq_review_decisions_active
    ON mko.review_decisions (document_id, field_key, value_key) WHERE superseded_at IS NULL;

CREATE TABLE IF NOT EXISTS mko.publications (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    published_at    TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    published_by    TEXT NOT NULL CHECK (length(btrim(published_by)) > 0),
    policy          TEXT NOT NULL CHECK (policy IN ('verified_any', 'verified_human_only')),
    parser_version  TEXT NOT NULL,
    summary         JSONB NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS mko.published_values (
    publication_id   UUID NOT NULL REFERENCES mko.publications(id) ON DELETE CASCADE,
    course_id        UUID NOT NULL REFERENCES public.courses(id) ON DELETE CASCADE,
    field_key        TEXT NOT NULL,
    value_text       TEXT,
    value_int        INTEGER,
    document_id      UUID NOT NULL REFERENCES public.course_documents(id) ON DELETE CASCADE,
    source_filename  TEXT NOT NULL,
    page_start       INTEGER NOT NULL,
    page_end         INTEGER NOT NULL,
    quote            TEXT NOT NULL CHECK (length(btrim(quote)) > 0),
    reviewed_by      TEXT NOT NULL,
    PRIMARY KEY (publication_id, course_id, field_key),
    CHECK (value_text IS NOT NULL OR value_int IS NOT NULL),
    CHECK (page_end >= page_start)
);

CREATE TABLE IF NOT EXISTS mko.published_list_items (
    publication_id   UUID NOT NULL REFERENCES mko.publications(id) ON DELETE CASCADE,
    course_id        UUID NOT NULL REFERENCES public.courses(id) ON DELETE CASCADE,
    item_type        TEXT NOT NULL CHECK (item_type IN ('objective', 'career', 'admission')),
    seq              SMALLINT NOT NULL CHECK (seq >= 1),
    text             TEXT NOT NULL CHECK (length(btrim(text)) > 0),
    document_id      UUID NOT NULL REFERENCES public.course_documents(id) ON DELETE CASCADE,
    source_filename  TEXT NOT NULL,
    page_start       INTEGER NOT NULL,
    page_end         INTEGER NOT NULL,
    reviewed_by      TEXT NOT NULL,
    PRIMARY KEY (publication_id, course_id, item_type, seq),
    CHECK (page_end >= page_start)
);

-- การเผยแพร่ที่มีผลคือครั้งล่าสุดเสมอ ย้อนกลับได้ด้วยการลบการเผยแพร่ครั้งล่าสุด (ลบเฉพาะในตาราง mko)
CREATE OR REPLACE VIEW mko.v_live_publication AS
    SELECT id, published_at, published_by, policy, parser_version
      FROM mko.publications
     ORDER BY published_at DESC
     LIMIT 1;

CREATE OR REPLACE VIEW mko.v_live_values AS
    SELECT v.publication_id, v.course_id, c.title AS course_title, v.field_key, v.value_text, v.value_int,
           v.document_id, v.source_filename, v.page_start, v.page_end, v.quote, v.reviewed_by
      FROM mko.published_values v
      JOIN mko.v_live_publication p ON p.id = v.publication_id
      JOIN public.courses c ON c.id = v.course_id
     WHERE c.is_active;

CREATE OR REPLACE VIEW mko.v_live_list_items AS
    SELECT i.publication_id, i.course_id, c.title AS course_title, i.item_type, i.seq, i.text,
           i.document_id, i.source_filename, i.page_start, i.page_end, i.reviewed_by
      FROM mko.published_list_items i
      JOIN mko.v_live_publication p ON p.id = i.publication_id
      JOIN public.courses c ON c.id = i.course_id
     WHERE c.is_active;

CREATE TABLE IF NOT EXISTS mko.shadow_answers (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    mode                  TEXT NOT NULL CHECK (mode IN ('shadow', 'replay')),
    question              TEXT NOT NULL,
    interpreted_question  TEXT,
    has_history           BOOLEAN NOT NULL DEFAULT FALSE,
    intent_field          TEXT,
    route                 TEXT NOT NULL CHECK (route IN ('structured', 'rag')),
    route_reason          TEXT NOT NULL,
    course_ids            UUID[] NOT NULL DEFAULT '{}',
    structured_status     TEXT NOT NULL CHECK (structured_status IN ('answered', 'no_data', 'not_applicable')),
    structured_answer     TEXT,
    facts                 JSONB NOT NULL DEFAULT '[]',
    publication_id        UUID REFERENCES mko.publications(id) ON DELETE SET NULL,
    served_status         TEXT,
    served_reply          TEXT,
    comparison            TEXT NOT NULL CHECK (comparison IN ('agree', 'partial', 'disagree', 'served_no_answer', 'unclear', 'not_compared')),
    comparison_detail     JSONB NOT NULL DEFAULT '{}',
    latency_ms            INTEGER
);
CREATE INDEX IF NOT EXISTS idx_shadow_answers_created ON mko.shadow_answers (created_at DESC);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'advisor_ingest') THEN
        GRANT USAGE ON SCHEMA mko TO advisor_ingest;
        GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA mko TO advisor_ingest;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'advisor_api') THEN
        GRANT USAGE ON SCHEMA mko TO advisor_api;
        -- backend อ่านได้เฉพาะข้อมูลที่เผยแพร่แล้ว และเขียนได้เฉพาะบันทึกผลโหมด shadow
        GRANT SELECT ON mko.v_live_publication, mko.v_live_values, mko.v_live_list_items TO advisor_api;
        GRANT INSERT ON mko.shadow_answers TO advisor_api;
    END IF;
END;
$$;

INSERT INTO mko.schema_migrations (version) VALUES ('002_mko_review_publish') ON CONFLICT (version) DO NOTHING;

COMMIT;
