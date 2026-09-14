-- =====================================================================
-- 001_mko_structured.sql — ข้อมูลเชิงโครงสร้างจากเอกสาร มคอ. (Phase 1)
--
-- ดูการออกแบบเต็มใน docs/MKO_STRUCTURED_DATA_DESIGN.md
--
-- หลักของ migration นี้:
--   - สร้างเฉพาะ schema `mko` ไม่ ALTER / DROP / เขียนข้อมูลในตาราง public ใดๆ
--     (อ้างถึง public.courses / public.course_documents ผ่าน FOREIGN KEY เท่านั้น)
--     ย้อนกลับได้ด้วย DROP SCHEMA mko CASCADE โดย course_chunks และ embedding ไม่ถูกแตะ
--   - รันซ้ำได้ (IF NOT EXISTS / CREATE OR REPLACE)
--   - ฐานข้อมูลบังคับเองว่า "ค่าที่มีข้อมูลต้องมีหลักฐาน" และ "หลักฐานต้องเป็นข้อความที่อยู่ในหน้านั้นจริง"
--     ไม่ฝากไว้กับโค้ดฝั่งสกัดข้อมูลอย่างเดียว
--
-- รันด้วยบัญชีที่มีสิทธิ์ DDL:
--   psql -v ON_ERROR_STOP=1 -U postgres -d course_advisor -f db/migrations/001_mko_structured.sql
-- =====================================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS mko;

CREATE TABLE IF NOT EXISTS mko.schema_migrations (
    version     TEXT PRIMARY KEY,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- ข้อความรายหน้า — input ของการสกัดข้อมูล (สร้างด้วย pipeline/pages.py ซึ่งใช้ขั้นตอนเดียวกับตอนทำ chunk)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS mko.document_pages (
    document_id       UUID NOT NULL REFERENCES public.course_documents(id) ON DELETE CASCADE,
    page_number       INTEGER NOT NULL CHECK (page_number >= 1),
    text_raw          TEXT NOT NULL,            -- หลังเติม OCR ก่อนทำความสะอาด
    text_clean        TEXT NOT NULL,            -- ข้อความที่ตัวสกัดอ่าน และข้อความที่หลักฐานต้องยกมาจาก
    text_source       TEXT NOT NULL CHECK (text_source IN ('text_layer', 'ocr', 'text_layer+ocr', 'plain_text')),
    is_toc            BOOLEAN NOT NULL DEFAULT FALSE,
    encoding_suspect  BOOLEAN NOT NULL DEFAULT FALSE,   -- พบรูปอักษรที่เพี้ยนจากฟอนต์ เช่น "กำร"
    text_sha256       TEXT NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (document_id, page_number)
);

-- ---------------------------------------------------------------------
-- การสกัดแต่ละรอบ — ย้อนดูได้ว่าค่ามาจากตัวสกัดรุ่นไหน
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS mko.extraction_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID NOT NULL REFERENCES public.course_documents(id) ON DELETE CASCADE,
    parser_version  TEXT NOT NULL,
    template_type   TEXT NOT NULL CHECK (template_type IN ('tqf2', 'std2565', 'brief', 'web_page', 'unknown')),
    status          TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'done', 'failed')),
    summary         JSONB NOT NULL DEFAULT '{}',
    error           TEXT,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_extraction_runs_document ON mko.extraction_runs (document_id, started_at DESC);

-- ---------------------------------------------------------------------
-- ขอบเขตหัวข้อในเอกสาร (หมวด, หัวข้อย่อย, ภาคผนวก)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS mko.document_sections (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id        UUID NOT NULL REFERENCES mko.extraction_runs(id) ON DELETE CASCADE,
    document_id   UUID NOT NULL REFERENCES public.course_documents(id) ON DELETE CASCADE,
    section_key   TEXT NOT NULL,                -- เช่น chapter.1, general.careers, appendix
    heading_text  TEXT,
    page_start    INTEGER NOT NULL,
    page_end      INTEGER NOT NULL,
    is_appendix   BOOLEAN NOT NULL DEFAULT FALSE,
    CHECK (page_end >= page_start)
);
CREATE INDEX IF NOT EXISTS idx_document_sections_run ON mko.document_sections (run_id, section_key);

-- ---------------------------------------------------------------------
-- หลักฐาน — ข้อความที่ยกมาจากหน้าต้นฉบับ
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS mko.evidence (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id       UUID NOT NULL REFERENCES mko.extraction_runs(id) ON DELETE CASCADE,
    document_id  UUID NOT NULL,
    page_start   INTEGER NOT NULL,
    page_end     INTEGER NOT NULL,
    section_id   UUID REFERENCES mko.document_sections(id) ON DELETE SET NULL,
    quote        TEXT NOT NULL CHECK (length(btrim(quote)) > 0),
    method       TEXT NOT NULL CHECK (method IN ('regex', 'table_parser', 'list_parser', 'llm_span', 'manual')),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (page_end >= page_start),
    FOREIGN KEY (document_id, page_start) REFERENCES mko.document_pages (document_id, page_number) ON DELETE CASCADE,
    FOREIGN KEY (document_id, page_end) REFERENCES mko.document_pages (document_id, page_number) ON DELETE CASCADE
);

-- ข้อความที่ยกมาต้องอยู่ในข้อความของหน้าที่อ้างจริง (หน้าติดกันต่อด้วยขึ้นบรรทัดใหม่หนึ่งบรรทัด)
-- เป็นด่านสุดท้ายที่กันค่าที่ไม่มีที่มา แม้โค้ดสกัดข้อมูลจะมีบั๊ก
CREATE OR REPLACE FUNCTION mko.check_evidence_quote() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    source TEXT;
BEGIN
    SELECT string_agg(text_clean, E'\n' ORDER BY page_number) INTO source
      FROM mko.document_pages
     WHERE document_id = NEW.document_id
       AND page_number BETWEEN NEW.page_start AND NEW.page_end;
    IF source IS NULL OR strpos(source, NEW.quote) = 0 THEN
        RAISE EXCEPTION 'evidence quote is not in document % pages %-%', NEW.document_id, NEW.page_start, NEW.page_end;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_evidence_quote ON mko.evidence;
CREATE TRIGGER trg_evidence_quote
    BEFORE INSERT OR UPDATE ON mko.evidence
    FOR EACH ROW EXECUTE FUNCTION mko.check_evidence_quote();

-- ---------------------------------------------------------------------
-- สาขา (ตัวตนที่ข้ามปี) และหลักสูตรรายฉบับปี
--
-- curricula สร้างเป็น draft ตอนสกัดข้อมูล ช่องแบบมีชนิดจะเติมตอน publish จากค่าที่ verified แล้วเท่านั้น (Phase 2)
-- UNIQUE (program_id, edition_year_be) กันไม่ให้สองฉบับปีเดียวกันของสาขาเดียวกันปนกัน
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS mko.programs (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name_th       TEXT NOT NULL,
    name_en       TEXT,
    degree_level  TEXT NOT NULL CHECK (degree_level IN ('bachelor', 'master', 'doctoral')),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (name_th, degree_level)
);

CREATE TABLE IF NOT EXISTS mko.curricula (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id            UUID NOT NULL UNIQUE REFERENCES public.courses(id) ON DELETE CASCADE,
    program_id           UUID REFERENCES mko.programs(id),
    edition_year_be      SMALLINT CHECK (edition_year_be BETWEEN 2500 AND 2700),
    revision_type        TEXT CHECK (revision_type IN ('new', 'revised')),
    template_type        TEXT CHECK (template_type IN ('tqf2', 'std2565', 'brief', 'web_page', 'unknown')),
    primary_document_id  UUID REFERENCES public.course_documents(id),
    program_name_th      TEXT,
    program_name_en      TEXT,
    degree_name_th       TEXT,
    degree_name_en       TEXT,
    degree_abbr_th       TEXT,
    degree_abbr_en       TEXT,
    degree_level         TEXT CHECK (degree_level IN ('bachelor', 'master', 'doctoral')),
    total_credits        SMALLINT CHECK (total_credits BETWEEN 1 AND 400),
    study_years          NUMERIC(3, 1),
    language             TEXT,
    status               TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'in_review', 'published')),
    published_at         TIMESTAMPTZ,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (program_id, edition_year_be)
);

-- ---------------------------------------------------------------------
-- ค่าที่สกัดได้ก่อนเผยแพร่ — คิวให้คนตรวจ
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS mko.field_values (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    curriculum_id  UUID NOT NULL REFERENCES mko.curricula(id) ON DELETE CASCADE,
    run_id         UUID NOT NULL REFERENCES mko.extraction_runs(id) ON DELETE CASCADE,
    document_id    UUID NOT NULL REFERENCES public.course_documents(id) ON DELETE CASCADE,
    field_key      TEXT NOT NULL,
    value_text     TEXT,
    value_int      INTEGER,
    status         TEXT NOT NULL CHECK (status IN ('candidate', 'needs_review', 'verified', 'rejected', 'not_found', 'not_applicable')),
    reason         TEXT,
    confidence     NUMERIC(4, 3) CHECK (confidence BETWEEN 0 AND 1),
    evidence_id    UUID REFERENCES mko.evidence(id),
    reviewed_by    TEXT,
    reviewed_at    TIMESTAMPTZ,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- ค่าที่หาไม่เจอหรือไม่มีในรูปแบบเอกสารต้องไม่มีค่า ส่วนค่าอื่นทุกค่าต้องมีทั้งค่าและหลักฐาน
    CONSTRAINT field_value_evidence_rule CHECK (
        (status IN ('not_found', 'not_applicable') AND value_text IS NULL AND value_int IS NULL AND evidence_id IS NULL)
        OR (status NOT IN ('not_found', 'not_applicable') AND evidence_id IS NOT NULL
            AND (value_text IS NOT NULL OR value_int IS NOT NULL))
    ),
    -- verified ต้องบอกได้ว่าใครหรือกฎใดเป็นผู้ยืนยัน
    CONSTRAINT field_value_verified_reviewer CHECK (status <> 'verified' OR reviewed_by IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS idx_field_values_lookup ON mko.field_values (curriculum_id, field_key, status);
CREATE INDEX IF NOT EXISTS idx_field_values_run ON mko.field_values (run_id);

-- หลักฐานเพิ่มเติมของค่าเดียวกัน เช่น หน่วยกิตที่ยืนยันจากสองตำแหน่งในเล่ม
CREATE TABLE IF NOT EXISTS mko.field_value_evidence (
    field_value_id  UUID NOT NULL REFERENCES mko.field_values(id) ON DELETE CASCADE,
    evidence_id     UUID NOT NULL REFERENCES mko.evidence(id) ON DELETE CASCADE,
    PRIMARY KEY (field_value_id, evidence_id)
);

-- ---------------------------------------------------------------------
-- รายการข้อความตามต้นฉบับ: ปรัชญา วัตถุประสงค์ อาชีพ คุณสมบัติผู้เข้าศึกษา
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS mko.list_items (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    curriculum_id  UUID NOT NULL REFERENCES mko.curricula(id) ON DELETE CASCADE,
    run_id         UUID NOT NULL REFERENCES mko.extraction_runs(id) ON DELETE CASCADE,
    document_id    UUID NOT NULL REFERENCES public.course_documents(id) ON DELETE CASCADE,
    item_type      TEXT NOT NULL CHECK (item_type IN ('philosophy', 'objective', 'career', 'admission')),
    seq            SMALLINT NOT NULL CHECK (seq >= 1),
    text           TEXT NOT NULL CHECK (length(btrim(text)) > 0),
    status         TEXT NOT NULL CHECK (status IN ('candidate', 'needs_review', 'verified', 'rejected')),
    reason         TEXT,
    evidence_id    UUID NOT NULL REFERENCES mko.evidence(id),
    reviewed_by    TEXT,
    reviewed_at    TIMESTAMPTZ,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (run_id, item_type, seq),
    CONSTRAINT list_item_verified_reviewer CHECK (status <> 'verified' OR reviewed_by IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS idx_list_items_lookup ON mko.list_items (curriculum_id, item_type, status);

-- ---------------------------------------------------------------------
-- เตรียมไว้สำหรับรายวิชาและ PLO (ยังไม่มีตัวสกัดใน Phase 1)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS mko.credit_groups (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    curriculum_id  UUID NOT NULL REFERENCES mko.curricula(id) ON DELETE CASCADE,
    run_id         UUID NOT NULL REFERENCES mko.extraction_runs(id) ON DELETE CASCADE,
    parent_id      UUID REFERENCES mko.credit_groups(id) ON DELETE CASCADE,
    seq            SMALLINT NOT NULL,
    name_th        TEXT NOT NULL,
    min_credits    SMALLINT,
    status         TEXT NOT NULL CHECK (status IN ('candidate', 'needs_review', 'verified', 'rejected')),
    reason         TEXT,
    evidence_id    UUID NOT NULL REFERENCES mko.evidence(id),
    reviewed_by    TEXT,
    reviewed_at    TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS mko.subjects (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    curriculum_id            UUID NOT NULL REFERENCES mko.curricula(id) ON DELETE CASCADE,
    run_id                   UUID NOT NULL REFERENCES mko.extraction_runs(id) ON DELETE CASCADE,
    code                     TEXT NOT NULL,             -- เก็บเป็นข้อความเพราะรหัสขึ้นต้นด้วย 0 ได้ เช่น 0010102
    name_th                  TEXT,
    name_en                  TEXT,
    credits                  SMALLINT,
    hours_pattern            TEXT,                      -- เช่น 3(3-0-6)
    lecture_hours            SMALLINT,
    practice_hours           SMALLINT,
    self_study_hours         SMALLINT,
    credit_group_id          UUID REFERENCES mko.credit_groups(id) ON DELETE SET NULL,
    description_th           TEXT,
    description_en           TEXT,
    status                   TEXT NOT NULL CHECK (status IN ('candidate', 'needs_review', 'verified', 'rejected')),
    reason                   TEXT,
    listing_evidence_id      UUID REFERENCES mko.evidence(id),
    description_evidence_id  UUID REFERENCES mko.evidence(id),
    reviewed_by              TEXT,
    reviewed_at              TIMESTAMPTZ,
    UNIQUE (run_id, code),
    CHECK (listing_evidence_id IS NOT NULL OR description_evidence_id IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS mko.learning_outcomes (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    curriculum_id  UUID NOT NULL REFERENCES mko.curricula(id) ON DELETE CASCADE,
    run_id         UUID NOT NULL REFERENCES mko.extraction_runs(id) ON DELETE CASCADE,
    framework      TEXT NOT NULL CHECK (framework IN ('PLO', 'SubPLO', 'YLO', 'TQF_domain')),
    code           TEXT,
    parent_id      UUID REFERENCES mko.learning_outcomes(id) ON DELETE CASCADE,
    seq            SMALLINT NOT NULL,
    text           TEXT NOT NULL,
    status         TEXT NOT NULL CHECK (status IN ('candidate', 'needs_review', 'verified', 'rejected')),
    reason         TEXT,
    evidence_id    UUID NOT NULL REFERENCES mko.evidence(id),
    reviewed_by    TEXT,
    reviewed_at    TIMESTAMPTZ
);

-- ---------------------------------------------------------------------
-- Views สำหรับผู้อ่าน (Phase 2 ขึ้นไป) — เห็นเฉพาะหลักสูตรที่ publish แล้วและค่าที่ verified
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW mko.v_published_curricula AS
    SELECT * FROM mko.curricula WHERE status = 'published';

CREATE OR REPLACE VIEW mko.v_published_field_values AS
    SELECT fv.*
      FROM mko.field_values fv
      JOIN mko.curricula c ON c.id = fv.curriculum_id
     WHERE c.status = 'published' AND fv.status = 'verified';

CREATE OR REPLACE VIEW mko.v_published_list_items AS
    SELECT li.*
      FROM mko.list_items li
      JOIN mko.curricula c ON c.id = li.curriculum_id
     WHERE c.status = 'published' AND li.status = 'verified';

-- ---------------------------------------------------------------------
-- สิทธิ์ — ให้เฉพาะเมื่อ role มีอยู่ (ฐานข้อมูลที่ติดตั้งจาก db/20-roles.sh)
-- ---------------------------------------------------------------------
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'advisor_ingest') THEN
        GRANT USAGE ON SCHEMA mko TO advisor_ingest;
        GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA mko TO advisor_ingest;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'advisor_api') THEN
        GRANT USAGE ON SCHEMA mko TO advisor_api;
        GRANT SELECT ON mko.v_published_curricula, mko.v_published_field_values, mko.v_published_list_items TO advisor_api;
    END IF;
END;
$$;

INSERT INTO mko.schema_migrations (version) VALUES ('001_mko_structured') ON CONFLICT (version) DO NOTHING;

COMMIT;
