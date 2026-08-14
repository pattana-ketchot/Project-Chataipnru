-- =====================================================================
-- Course Advisor System — PostgreSQL schema (requires pgvector)
--
-- ออกแบบให้ 3 โดเมนหลักสัมพันธ์กัน:
--   1) courses / course_documents / course_chunks  (ข้อมูลจาก PDF หลักสูตร)
--   2) users / user_profiles / user_requirements   (ผู้ใช้ + ความชอบ)
--   3) recommendations / chat_sessions              (ผลลัพธ์จาก RAG + LLM)
--
-- SECURITY:
--   - รัน migration ด้วย role ที่มีสิทธิ์ DDL เท่านั้น (เช่น `advisor_migrator`)
--   - runtime role ของ backend (`advisor_api`) และ pipeline (`advisor_ingest`)
--     ต้องถูกจำกัดสิทธิ์แยกกัน ดูท้ายไฟล์ (GRANT ตัวอย่าง)
--   - ทุก PK เป็น UUID (ไม่ใช้ sequential integer) เพื่อลดการเดา/enumerate ID
--     จาก URL (เช่น /courses/123 -> /courses/124)
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS vector;     -- pgvector
CREATE EXTENSION IF NOT EXISTS citext;     -- case-insensitive email

-- ปรับตาม embedding model ที่ใช้จริง (nomic-embed-text = 768,
-- bge-m3 = 1024, mxbai-embed-large = 1024 ฯลฯ)
-- ใช้เป็นค่าคงที่เชิงเอกสาร — ต้องตรงกับ EMBED_DIM ใน backend/.env
-- (ที่นี่ hardcode 768 ในชนิดคอลัมน์ตาม pgvector; แก้ตรงนี้ถ้าเปลี่ยนโมเดล)

-- ---------------------------------------------------------------------
-- 1) USERS / PROFILE / REQUIREMENTS
-- ---------------------------------------------------------------------

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           CITEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,             -- bcrypt hash เท่านั้น ห้ามเก็บ plaintext
    full_name       TEXT,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    is_admin        BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- ต้องมี extension citext: CREATE EXTENSION IF NOT EXISTS citext;

CREATE TABLE user_profiles (
    user_id             UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    education_level     TEXT,                  -- e.g. 'high_school','bachelor','master'
    field_of_study      TEXT,
    -- ต้องใส่ double quote: current_role เป็น reserved keyword ของ PostgreSQL
    -- (ฟังก์ชันมาตรฐาน SQL เหมือน current_user) ถ้าไม่ quote จะ syntax error
    -- และ CREATE TABLE ทั้งไฟล์จะหยุดตรงนี้
    -- SQLAlchemy รู้จักคำนี้เป็น reserved word อยู่แล้วจึง quote ให้เองอัตโนมัติ
    -- ฝั่ง ORM/API ไม่ต้องแก้ แต่ถ้าเขียน raw SQL เองต้องใส่ quote ทุกครั้ง
    "current_role"      TEXT,
    career_goal         TEXT,
    skills              JSONB NOT NULL DEFAULT '[]',   -- ["python","data analysis"]
    interests           JSONB NOT NULL DEFAULT '[]',   -- ["ai","cloud"]
    language_preference TEXT DEFAULT 'th',
    metadata            JSONB NOT NULL DEFAULT '{}',   -- ช่องขยายอนาคต
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ความชอบ/เงื่อนไขที่ผู้ใช้ระบุ แยกเป็นแถวเพื่อ query/filter ได้ยืดหยุ่น
-- (แทนที่จะยัดทุกอย่างเป็น JSON ก้อนเดียวใน profile)
CREATE TABLE user_requirements (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    req_type        TEXT NOT NULL,      -- 'budget_max','duration_max_weeks','mode','schedule','location','topic'
    req_value       TEXT NOT NULL,      -- เก็บเป็น text แล้ว cast ตอน query (ยืดหยุ่นสุด)
    priority        SMALLINT NOT NULL DEFAULT 3 CHECK (priority BETWEEN 1 AND 5), -- 1=nice-to-have,5=must-have
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_user_requirements_user ON user_requirements(user_id);
CREATE INDEX idx_user_requirements_type ON user_requirements(req_type);

-- ---------------------------------------------------------------------
-- 2) COURSES / DOCUMENTS / CHUNKS (มาจาก PDF)
-- ---------------------------------------------------------------------

CREATE TABLE courses (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code            TEXT UNIQUE,               -- รหัสหลักสูตร ถ้ามี
    title           TEXT NOT NULL,
    provider        TEXT,                      -- สถาบัน/หน่วยงานที่จัดหลักสูตร
    summary         TEXT,                      -- สรุปสั้น (อาจ generate โดย LLM)
    mode            TEXT,                      -- 'online','onsite','hybrid'
    duration_weeks  NUMERIC,
    price           NUMERIC,
    currency        TEXT DEFAULT 'THB',
    tags            JSONB NOT NULL DEFAULT '[]',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_courses_tags ON courses USING GIN (tags);

-- 1 course อาจมีหลายไฟล์ PDF ตามเวอร์ชัน/ปี
CREATE TABLE course_documents (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id           UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    original_filename   TEXT NOT NULL,
    file_sha256         TEXT NOT NULL,          -- dedupe / integrity check
    storage_path        TEXT NOT NULL,          -- path บน object storage / disk (ไม่ใช่ path ที่ user ควบคุมได้ตรงๆ)
    page_count          INTEGER,
    extraction_status   TEXT NOT NULL DEFAULT 'pending', -- pending|processing|done|failed
    extraction_error    TEXT,
    uploaded_by         UUID REFERENCES users(id),
    uploaded_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (course_id, file_sha256)
);

-- แต่ละ chunk = ส่วนของข้อความหลัง clean+split พร้อม embedding สำหรับ vector search
CREATE TABLE course_chunks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id       UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    document_id     UUID NOT NULL REFERENCES course_documents(id) ON DELETE CASCADE,
    chunk_index     INTEGER NOT NULL,
    page_number     INTEGER,
    content         TEXT NOT NULL,
    token_count     INTEGER,
    -- ต้องตรงกับ EMBED_DIM ใน .env เสมอ (bge-m3 = 1024)
    -- ถ้าไม่ตรง backend จะปฏิเสธการสตาร์ทพร้อมบอกค่าที่ขัดกัน (ดู app/main.py)
    -- เปลี่ยนค่าตรงนี้ต้องสร้าง DB ใหม่และ ingest ใหม่ทั้งหมด เพราะ embedding เดิม
    -- คำนวณจากโมเดลคนละตัว นำมาเทียบกันไม่ได้
    embedding       VECTOR(1024) NOT NULL,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (document_id, chunk_index)
);

-- ANN index สำหรับ similarity search (cosine distance)
CREATE INDEX idx_course_chunks_embedding
    ON course_chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
CREATE INDEX idx_course_chunks_course ON course_chunks(course_id);

-- ---------------------------------------------------------------------
-- 3) RECOMMENDATION LOG / CHAT (audit + ปรับปรุงคุณภาพภายหลัง)
-- ---------------------------------------------------------------------

CREATE TABLE chat_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at        TIMESTAMPTZ
);

CREATE TABLE chat_messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK (role IN ('user','assistant','system')),
    content         TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_chat_messages_session ON chat_messages(session_id);

CREATE TABLE recommendations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    course_id       UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    session_id      UUID REFERENCES chat_sessions(id) ON DELETE SET NULL,
    score           NUMERIC NOT NULL,          -- ลำดับความเหมาะสม (0-1)
    rationale       TEXT,                      -- คำอธิบายจาก LLM ว่าทำไมแนะนำ
    retrieved_chunk_ids UUID[] NOT NULL DEFAULT '{}', -- อ้างอิงกลับไป course_chunks เพื่อ traceability
    model_used      TEXT,                      -- e.g. 'qwen2.5:7b'
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_recommendations_user ON recommendations(user_id);

-- ---------------------------------------------------------------------
-- Trigger: ให้ updated_at อัปเดตอัตโนมัติทุกครั้งที่มีการแก้ไขแถว
--
-- ทำไมต้องใช้ trigger ไม่ใช่ onupdate ฝั่ง SQLAlchemy:
--   `DEFAULT now()` มีผลตอน INSERT เท่านั้น ถ้าไม่มี trigger คอลัมน์ updated_at
--   จะเท่ากับ created_at ตลอดไปแม้แก้ข้อมูลกี่ครั้งก็ตาม
--   และตาราง courses ถูกเขียนโดย pipeline ผ่าน psycopg ตรงๆ ไม่ผ่าน ORM
--   ถ้าพึ่ง onupdate ของ SQLAlchemy อย่างเดียวจะครอบไม่ถึง — ทำที่ชั้น DB
--   จึงครอบคลุมทุกทางเข้าถึงข้อมูล และเป็นแหล่งความจริงเพียงที่เดียว
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_user_profiles_updated_at
    BEFORE UPDATE ON user_profiles
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_courses_updated_at
    BEFORE UPDATE ON courses
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------
-- Least-privilege role
-- ---------------------------------------------------------------------
-- ย้ายไปที่ db/20-roles.sh แล้ว (รันต่อจากไฟล์นี้โดย docker-entrypoint-initdb.d)
-- เหตุผล: ต้องอ่านรหัสผ่านจาก environment variable ซึ่งไฟล์ .sql ทำไม่ได้
-- จึงต้องเป็นเชลล์สคริปต์ ไม่งั้นต้อง hardcode รหัสผ่านลงไฟล์ที่ commit เข้า git
