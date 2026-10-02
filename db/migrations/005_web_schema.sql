-- =====================================================================
-- 005_web_schema.sql — ที่อยู่ใหม่ของข้อมูลหน้าเว็บ (Phase 4 — รวมฐานข้อมูล)
--
-- ดูผลการศึกษาความเป็นไปได้ใน docs/DATABASE_CONSOLIDATION_AUDIT.md
-- และภาพปลายทางใน docs/TARGET_ARCHITECTURE.md
--
-- หลักเดียวกับ 001–004:
--   - สร้างเฉพาะของใหม่ ไม่ ALTER ไม่ DROP ตารางหรือวิวใด
--   - ไม่แตะ public.courses, course_documents, course_chunks, users
--   - ไม่แตะอะไรใน schema mko
--   - รันซ้ำได้ (IF NOT EXISTS)
--
-- ไฟล์นี้สร้าง "ที่ว่าง" อย่างเดียว ไม่ย้ายข้อมูลแม้แถวเดียว
-- การนำข้อมูลเข้าเป็นขั้นตอนแยกที่ต้องขออนุมัติเอง
--
-- ทำไมเป็น schema แยก ไม่ยัดลง public
-- ------------------------------------
-- 1. public กับ mko ทำงานอยู่จริงกับข้อมูลจริง (9,039 chunk · 56 FK · 68 check)
--    การไม่แตะเลยทำให้ความเสี่ยงต่อ RAG, crawler และ chat เป็นศูนย์
-- 2. ชื่อชนกันสองคู่ — ฝั่งหน้าเว็บมีทั้ง courses และ user_profiles ซึ่ง public
--    ก็มีทั้งคู่และ "ความหมายคนละอย่าง" การยัดรวมต้องเปลี่ยนชื่อหรือรวมตาราง
--    ซึ่งทั้งสองทางแตะของที่ใช้งานอยู่
-- 3. ถอนกลับได้ด้วย DROP SCHEMA web CASCADE คำสั่งเดียว ไม่กระทบอะไรเลย
-- 4. mko มี 19 FK ชี้เข้า public อยู่แล้ว พิสูจน์ว่าโครงหลาย schema ในฐานเดียว
--    ใช้งานได้ดีในโปรเจกต์นี้
--
-- ทำไมชื่อ site_courses ไม่ใช่ courses
-- -----------------------------------
-- public.courses เก็บ "ข้อเท็จจริงของหลักสูตร" ที่ pipeline สกัดมาจากเอกสาร มคอ.
-- ส่วนตารางนี้เก็บ "ของที่เอาไว้แสดงบนหน้าเว็บ" — โลโก้ คำบรรยาย อาชีพที่ทำได้
-- สองอย่างนี้คนละเรื่องกัน ตั้งชื่อให้ต่างกันเพื่อให้คนอ่าน query แล้วรู้ทันทีว่า
-- กำลังอ่านอะไรอยู่ ไม่ต้องจำว่า schema ไหนคืออันไหน
--
-- สิ่งที่ได้เพิ่มจากการรวม: คอลัมน์ course_id
-- ------------------------------------------
-- ปัจจุบันข้อมูลสองฝั่งอยู่คนละฐานข้อมูลจึงเชื่อมกันไม่ได้เลย หน้าเว็บแสดงหลักสูตร
-- จากชุดหนึ่ง แต่ AI ตอบคำถามจากอีกชุดหนึ่ง โดยไม่มีอะไรรับประกันว่าพูดถึงหลักสูตร
-- เดียวกัน คอลัมน์นี้คือสิ่งที่การรวมฐานข้อมูลให้มาจริง ๆ นอกเหนือจากผังที่ดูง่ายขึ้น
--
-- ความสัมพันธ์ที่ประกาศไว้ และที่เพิ่มเข้ามา
-- --------------------------------------
-- schema ต้นทางมี foreign key 7 เส้น check constraint 2 ตัว และ unique 4 ตัว
-- (ที่มา: supabase_schema.sql ในรีโปของหน้าเว็บ ซึ่งเป็น snapshot ที่ดึงจากโปรเจกต์จริง
-- แบบ read-only ไม่เกิน 2026-09-23)
--
-- ของเดิม created_by / updated_by ชี้ไป auth.users และ user_profiles ของระบบนั้น
-- ที่นี่ชี้ไป public.users แทน เพราะเป็นตารางผู้ใช้ของฐานข้อมูลปลายทาง
-- และเพิ่ม site_courses.course_id ซึ่งไม่เคยมีในทั้งสองฝั่ง
--
-- หมายเหตุประวัติ: เอกสารรุ่นก่อนหน้าเคยระบุว่าต้นทางมี "FK 0 · CHECK 0 · UNIQUE 1"
-- ซึ่งผิด ตัวเลขนั้นมาจาก docs/database/schema.json ที่ parse constraint ระดับคอลัมน์
-- ไม่ได้ ดูรายละเอียดใน docs/SUPABASE_PRE_MIGRATION_AUDIT.md ข้อ 12
--
-- ทำไม created_by / updated_by เป็น NULL ได้
-- ------------------------------------------
-- ของเดิมอ้างถึงผู้ใช้ในระบบ auth ของหน้าเว็บ ซึ่งเป็นคนละชุดกับ public.users
-- (ยืนยันแล้วว่าไม่มีเส้นเชื่อมกันเลย) ตอนนำข้อมูลเข้าจึงจะมีบางแถวที่หาเจ้าของ
-- ไม่เจอ ปล่อยให้เป็น NULL ได้ดีกว่าทิ้งแถวนั้นหรือยัดเจ้าของผิดคน
-- และ ON DELETE SET NULL เพราะการลบบัญชีผู้ใช้ไม่ควรลบข่าวที่เขาเคยเขียน
--
-- เรื่องเวลา
-- ---------
-- ต้นทางใช้ TIMESTAMP WITH TIME ZONE ทุกคอลัมน์เวลา และที่นี่ใช้ timestamptz
-- ซึ่งเป็นชนิดเดียวกัน การย้ายจึงไม่ต้องตีความหรือระบุเขตเวลาเพิ่ม
--
-- หมายเหตุประวัติ: เอกสารรุ่นก่อนหน้าเคยระบุว่าต้นทางเป็น TIMESTAMP ไม่มีเขตเวลา
-- และเตือนว่าเวลาอาจคลาด 7 ชั่วโมงถ้าเดาผิด ข้อนั้นผิด ไม่มีความเสี่ยงดังกล่าว
--
-- สิ่งที่ตั้งใจยังไม่สร้างในไฟล์นี้
-- --------------------------------
-- 1. ตาราง role/สิทธิ์ของผู้ใช้หน้าเว็บ — ต้องตัดสินใจเรื่อง auth ก่อนว่าจะให้
--    ตัวตนผู้ใช้อยู่ที่ใด ถ้าสร้างตอนนี้จะกลายเป็น "ที่บอกสิทธิ์สองแห่ง" ซึ่งเป็น
--    ปัญหาเดิมในรูปแบบใหม่ (public.users.is_admin มีอยู่แล้ว)
-- 2. ตารางเก็บ chunk/embedding ของหน้าเว็บ — ของเดิมเป็น vector 768 มิติจากโมเดล
--    คนละตัวกับที่ระบบนี้ใช้ (bge-m3 1024 มิติ) ย้ายค่าเวกเตอร์ตรง ๆ ไม่ได้
--    ต้องสร้าง embedding ใหม่ทั้งหมด ซึ่งเป็นการตัดสินใจแยกเพราะคำตอบของระบบ
--    จะเปลี่ยนและต้องวัดคุณภาพใหม่
-- =====================================================================
BEGIN;

CREATE SCHEMA IF NOT EXISTS web;

COMMENT ON SCHEMA web IS
    'ข้อมูลของหน้าเว็บที่ย้ายมาจากฐานข้อมูลเดิมของทีมออกแบบ — แยกจาก public (ข้อเท็จจริงของหลักสูตรและ RAG) และ mko (การสกัดข้อมูลเชิงโครงสร้าง)';

-- ---------------------------------------------------------------------
-- หลักสูตรในมุมของหน้าเว็บ
--
-- careers กับ detail เป็น NULL ได้ตามต้นทาง
-- -------------------------------------
-- ตรวจ production จริงแล้ว (SUPABASE_LIVE_VERIFICATION ข้อ 10 / M2) จาก 12 แถว:
--
--   detail IS NULL            = 11   <- NOT NULL จะทำให้ import ล้ม 11 แถว
--   careers IS NULL           = 0
--   careers = '{}' (ว่าง)      = 12
--
-- สองคอลัมน์นี้จึงเป็น nullable ด้วยเหตุผลต่างกัน และต้องไม่สับสน
--
--   detail   ข้อมูลจริงบังคับ — เป็น NULL 11 ใน 12 แถว ถ้าคง NOT NULL ไว้
--            การ INSERT ... SELECT จากต้นทางตรง ๆ จะล้ม (DEFAULT ไม่ช่วย
--            เพราะค่า NULL ถูกส่งเข้ามาจริง ไม่ใช่การละคอลัมน์)
--
--   careers  ข้อมูลจริง "ไม่" บังคับ — ไม่มีแถวใดเป็น NULL เลย ที่ทำเป็น nullable
--            เพราะต้นทางประกาศ `careers TEXT[]` แบบ nullable และไม่มี DEFAULT
--            ปลายทางจึงสะท้อนต้นทางให้ตรง ไม่ใช่เพราะข้อมูลชุดนี้ต้องการ
--
-- ไม่ใส่ DEFAULT '{}' ให้ careers เพราะต้นทางก็ไม่มี — แถว 12 แถวที่เป็น '{}'
-- เกิดจากแอปเขียนค่านั้นลงไปเอง ไม่ใช่ค่าเริ่มต้นของฐานข้อมูล
--
-- ค่าว่างกับ NULL มีความหมายต่างกันด้วย — NULL คือ "ยังไม่ได้กรอก"
-- ส่วน '{}' คือ "กรอกแล้วว่าไม่มี" การแปลง NULL เป็น '{}' ตอนนำเข้าจะทำให้
-- แยกสองอย่างนี้ไม่ออกอีกต่อไป จึงห้ามใช้ COALESCE(detail, '{}') ตอน import
--
-- is_published ไม่มีคอลัมน์ต้นทาง
-- ----------------------------
-- public.courses ไม่มี is_published / published / status / visible (M3)
-- และ RLS ของต้นทางเปิดให้ทุกคนอ่าน courses แบบไร้เงื่อนไข (USING true)
-- ต่างจาก news ที่กรองด้วย status = 'published' — แปลว่าของจริงหลักสูตร
-- เผยแพร่หมดทุกอัน DEFAULT TRUE จึงให้ผลตรงกับของจริง แต่ต้องรู้ว่า
-- คอลัมน์นี้เป็นของใหม่ที่ไฟล์นี้เพิ่มเข้ามา ไม่มีข้อมูลต้นทางจะย้ายลงไป
--
-- course_id เป็น UNIQUE แบบยอมให้ NULL ซ้ำได้ (partial unique index ด้านล่าง)
-- เพราะหลักสูตรที่ยังจับคู่กับ public.courses ไม่ได้ต้องเก็บไว้ได้ และหนึ่งหลักสูตร
-- จริงต้องผูกกับแถวแสดงผลได้ไม่เกินหนึ่งแถว
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS web.site_courses (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id     UUID REFERENCES public.courses(id) ON DELETE SET NULL,
    title         VARCHAR(255) NOT NULL,
    title_en      VARCHAR(255),
    description   TEXT,
    logo_url      TEXT,
    careers       TEXT[],
    detail        JSONB,
    is_published  BOOLEAN      NOT NULL DEFAULT TRUE,
    created_by    UUID REFERENCES public.users(id) ON DELETE SET NULL,
    updated_by    UUID REFERENCES public.users(id) ON DELETE SET NULL,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_site_courses_course
    ON web.site_courses (course_id) WHERE course_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_site_courses_published
    ON web.site_courses (is_published) WHERE is_published;

COMMENT ON COLUMN web.site_courses.course_id IS
    'เชื่อมกับหลักสูตรจริงใน public.courses — NULL ได้ถ้ายังจับคู่ไม่ได้ สิ่งนี้ไม่เคยมีตอนอยู่คนละฐานข้อมูล';

-- ---------------------------------------------------------------------
-- ข่าวที่ทีมเขียนเอง
--
-- ความกว้างของ title ตามต้นทาง: VARCHAR(500)
-- -----------------------------------------
-- ตรวจ production แล้ว (ข้อ 5.1 / M5) ต้นทางเป็น varchar(500) สามคอลัมน์
-- คือ news.title, external_news.title, knowledge_articles.title
-- รุ่นก่อนของไฟล์นี้ตั้งทั้งสามเป็น VARCHAR(255) ซึ่ง "แคบกว่าต้นทางครึ่งหนึ่ง"
--
-- ข้อมูลชุดปัจจุบันยังไม่ชน (ยาวสุด news 74 · external_news 120 ·
-- knowledge_articles ไม่มีแถว) จึง import ผ่านทุกแถว แต่เป็นหนี้ที่ยังไม่ถึง
-- กำหนดชำระ: วันที่มีข่าวชื่อยาวเกิน 255 ต้นทางจะรับได้แต่ปลายทางจะไม่รับ
-- และจะพังตอน sync ไม่ใช่ตอน migrate ซึ่งหายากกว่ามาก
--
-- หมายเหตุ: courses.title และ courses.title_en ต้นทางเป็น varchar(255) อยู่แล้ว
-- site_courses จึงคง 255 ไว้ตามเดิม ไม่ได้ขยายทั้งไฟล์แบบเหมารวม
--
-- status มี CHECK เพราะโค้ดฝั่งหน้าเว็บกรองด้วยค่านี้ ถ้าพิมพ์ผิดแม้ตัวเดียว
-- ข่าวจะหายไปจากหน้าเว็บโดยไม่มีอะไรฟ้อง — ให้ฐานข้อมูลฟ้องตั้งแต่ตอนเขียน
--
-- ตรวจต้นทางแล้ว — รายการค่าไม่ต้องแก้ (เคยเป็น PENDING DECISION)
-- -----------------------------------------------------------
-- รันบน production จริงแล้ว (SUPABASE_LIVE_VERIFICATION ข้อ 2 / M1):
--
--   SELECT status, count(*) FROM public.news GROUP BY status
--   -> published  3     ไม่พบ draft  ไม่พบ archived
--
-- และต้นทาง "ไม่มี" CHECK บนคอลัมน์นี้เลย (ฐานทั้งหมดมี CHECK แค่ 2 ตัว คือ
-- ai_settings_singleton และ rag_documents_source_type_check) ชนิดต้นทางเป็น
-- VARCHAR(20) NOT NULL DEFAULT 'published'
--
-- ผลต่อไฟล์นี้: CHECK สามค่าข้างล่าง "ไม่บล็อก" ข้อมูลชุดนี้ ทุกแถวผ่าน
-- และ VARCHAR(50) ที่นี่กว้างกว่า VARCHAR(20) ของต้นทาง จึงไม่ตัดค่า
--
-- ทำไมคง CHECK ไว้ทั้งที่ต้นทางไม่มี
-- ---------------------------------
-- ที่ต้นทาง คอลัมน์นี้ไม่ใช่แค่ธงแสดงผล มันเป็น "ขอบเขตความปลอดภัย" —
-- RLS policy ที่ให้คนทั่วไปอ่าน news ใช้เงื่อนไข USING (status = 'published')
-- ตรง ๆ ถ้าค่าพิมพ์ผิดแม้ตัวเดียว แถวนั้นจะหายจากสายตาคนทั่วไปทันที
-- และเมื่อย้ายมาปลายทาง การกรองนี้จะไปอยู่ที่โค้ดแอป ซึ่งพลาดได้ง่ายกว่า
-- การให้ฐานข้อมูลปฏิเสธค่าที่ไม่รู้จักตั้งแต่ตอนเขียนจึงยังคุ้ม
--
-- 'archived' ยังไม่มีหลักฐานว่ามีอยู่จริง (UNVERIFIED — ดู U2 ของรายงาน)
-- ข้อมูลไม่ได้พิสูจน์ว่ามี และไม่ได้พิสูจน์ว่าไม่มี มันแค่ยังไม่ถูกใช้
-- คงไว้เป็นค่าเผื่ออนาคต ความเสี่ยงต่อข้อมูลชุดนี้เป็นศูนย์
-- ถ้าภายหลังยืนยันได้ว่าแอปไม่เคยเขียนค่านี้ จะตัดออกก็ได้ แต่ไม่ด่วน
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS web.news (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title         VARCHAR(500) NOT NULL,
    description   TEXT,
    category      VARCHAR(100),
    published_on  DATE,
    image_url     TEXT,
    status        VARCHAR(50)  NOT NULL DEFAULT 'published'
                  CHECK (status IN ('published', 'draft', 'archived')),
    created_by    UUID REFERENCES public.users(id) ON DELETE SET NULL,
    updated_by    UUID REFERENCES public.users(id) ON DELETE SET NULL,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_news_published
    ON web.news (published_on DESC NULLS LAST) WHERE status = 'published';

-- ---------------------------------------------------------------------
-- ข่าวที่ดึงมาจากภายนอก (SCI Connect)
--
-- กุญแจของตารางนี้ยึดตามต้นทาง ไม่ใช่ตามที่เดาเอง
--
--   detail_url  NOT NULL UNIQUE          <- กุญแจธรรมชาติจริงของต้นทาง
--   slug        nullable + partial unique <- ต้นทางให้เป็น NULL ได้
--   source      NOT NULL                  <- ต้นทางบังคับ
--
-- รุ่นแรกของไฟล์นี้ตั้ง slug เป็น NOT NULL UNIQUE และปล่อย detail_url กับ source
-- ให้ว่างได้ ซึ่งกลับด้านกับต้นทาง — ที่นี่แก้ให้ตรงกับต้นทางแล้ว
--
-- ข้อควรระวังเวลาอ่านย้อนหลัง: ตรวจ production แล้ว (ข้อ 3 / M8) ข้อมูลจริง
-- 15 แถว "ไม่มีแถวใด slug เป็น NULL เลย" และ detail_url ไม่ซ้ำ 15/15
-- การแก้ครั้งนั้นจึงถูกเพราะตรงกับ "ชนิดที่ต้นทางประกาศ" ไม่ใช่เพราะข้อมูล
-- บังคับ — อย่าอ่านคอมเมนต์เดิมแล้วเข้าใจว่าเคยมีแถว slug NULL อยู่จริง
--
-- partial unique บน slug รักษาเจตนาเดิมไว้ครบ คือ slug ที่ "มีค่า" ต้องไม่ซ้ำ
-- เพราะหน้ารายละเอียดค้นด้วย .eq('slug', slug).maybeSingle() ซึ่งถ้าซ้ำจะได้ผล
-- ไม่แน่นอน แต่แถวที่ยังไม่มี slug ก็ยังเก็บได้
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS web.external_news (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug            VARCHAR(255),
    title           VARCHAR(500) NOT NULL,
    description     TEXT,
    image_url       TEXT,
    detail_url      TEXT         NOT NULL UNIQUE,
    facebook_url    TEXT,
    source          VARCHAR(100) NOT NULL,
    published_at    TIMESTAMPTZ,
    published_text  VARCHAR(255),
    synced_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_external_news_slug
    ON web.external_news (slug) WHERE slug IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_external_news_published
    ON web.external_news (published_at DESC NULLS LAST);

COMMENT ON COLUMN web.external_news.published_text IS
    'ข้อความวันที่ตามที่เว็บต้นทางแสดง เก็บไว้ดิบ ๆ เพราะบางรายการไม่ใช่วันที่ที่ parse ได้';

-- ---------------------------------------------------------------------
-- บทความ / คลังความรู้
--
-- file_path, file_name, file_size เก็บข้อมูลของไฟล์แนบ ของเดิมไฟล์จริงอยู่ใน
-- ที่เก็บไฟล์ของผู้ให้บริการเดิม การย้ายฐานข้อมูลไม่ได้ย้ายไฟล์ตามมาด้วย
-- ต้องตัดสินใจแยกว่าไฟล์จะไปอยู่ที่ใด แล้วค่อยแก้ค่าในคอลัมน์นี้
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS web.knowledge_articles (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title       VARCHAR(500) NOT NULL,
    content     TEXT,
    file_path   TEXT,
    file_name   TEXT,
    file_size   BIGINT CHECK (file_size IS NULL OR file_size >= 0),
    created_by  UUID REFERENCES public.users(id) ON DELETE SET NULL,
    updated_by  UUID REFERENCES public.users(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

COMMENT ON COLUMN web.knowledge_articles.file_path IS
    'ที่อยู่ไฟล์แนบ — ค่าที่ย้ายมายังชี้ไปที่เก็บไฟล์เดิม ต้องแก้เมื่อย้ายไฟล์แล้ว';

-- ---------------------------------------------------------------------
-- ตั้งค่าโมเดลของหน้าเว็บ — ตารางแถวเดียว
--
-- บังคับ id = 1 ด้วย CHECK ไม่ใช่แค่ตั้งค่าเริ่มต้น เพราะโค้ดฝั่งหน้าเว็บอ่านด้วย
-- .eq('id', 1).single() ซึ่งจะล้มถ้ามีแถวที่สอง ให้ฐานข้อมูลกันไว้แทนที่จะหวังว่า
-- ทุกคนที่เขียนโค้ดในอนาคตจะรู้กติกานี้
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS web.ai_settings (
    id          SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    model       VARCHAR(255) NOT NULL,
    updated_by  UUID REFERENCES public.users(id) ON DELETE SET NULL,
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- การรักษา updated_at
--
-- ต้นทางมี trigger ทำงานนี้ให้ 4 ตัว (update_courses_updated_at,
-- update_news_updated_at, update_knowledge_articles_updated_at,
-- update_user_profiles_updated_at) รุ่นแรกของไฟล์นี้ประกาศคอลัมน์ updated_at ไว้
-- แต่ไม่มีอะไรรักษาค่าเลย ค่าจึงค้างอยู่ที่เวลาที่แถวถูกสร้างตลอดไป
-- ซึ่งเป็นการถอยหลังจากพฤติกรรมเดิมโดยไม่มีอะไรฟ้อง
--
-- ทำไมเป็น BEFORE UPDATE เท่านั้น ไม่ใช่ BEFORE INSERT OR UPDATE
-- ------------------------------------------------------------
-- ตอนนำข้อมูลเข้าต้องคง created_at และ updated_at เดิมของแต่ละแถวไว้
-- ถ้า trigger ทำงานตอน INSERT ด้วย ค่าเวลาเดิมทั้งหมดจะถูกเขียนทับด้วยเวลาที่นำเข้า
-- ประวัติว่าแถวไหนแก้ล่าสุดเมื่อไหร่จะหายทั้งตาราง
--
-- ai_settings ได้ trigger ด้วยทั้งที่ต้นทางไม่มี เพราะต้นทางปล่อยให้แอปเป็นคนตั้งค่า
-- ซึ่งพึ่งพาว่าทุกคนที่เขียนโค้ดต่อจากนี้จะจำได้ การให้ฐานข้อมูลทำเองเชื่อถือได้กว่า
-- และเพิ่มที่ UPDATE อย่างเดียวจึงไม่กระทบการนำเข้า
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION web.touch_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $fn$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$fn$;

COMMENT ON FUNCTION web.touch_updated_at() IS
    'ตั้ง updated_at = now() ก่อนการ UPDATE ทุกครั้ง — ไม่ทำงานตอน INSERT เพื่อให้นำเข้าข้อมูลเก่าได้โดยคงเวลาเดิม';

CREATE OR REPLACE TRIGGER trg_site_courses_updated_at
    BEFORE UPDATE ON web.site_courses
    FOR EACH ROW EXECUTE FUNCTION web.touch_updated_at();

CREATE OR REPLACE TRIGGER trg_news_updated_at
    BEFORE UPDATE ON web.news
    FOR EACH ROW EXECUTE FUNCTION web.touch_updated_at();

CREATE OR REPLACE TRIGGER trg_knowledge_articles_updated_at
    BEFORE UPDATE ON web.knowledge_articles
    FOR EACH ROW EXECUTE FUNCTION web.touch_updated_at();

CREATE OR REPLACE TRIGGER trg_ai_settings_updated_at
    BEFORE UPDATE ON web.ai_settings
    FOR EACH ROW EXECUTE FUNCTION web.touch_updated_at();

-- ---------------------------------------------------------------------
-- สิทธิ์
--
-- backend อ่านได้ทุกตาราง และเขียนได้เฉพาะตารางที่หน้าผู้ดูแลแก้ไขจริง
-- ไม่ให้ DELETE แก่ใคร — หลักเดียวกับ 002 และ 004 คือการลบต้องเป็นการตัดสินใจ
-- ที่ทำด้วยมือโดยผู้มีสิทธิ์ระดับ owner ไม่ใช่สิ่งที่โค้ดทำได้เอง
--
-- external_news เป็นข้อมูลที่ดึงมาจากภายนอก ตัวดึงข้อมูลเป็นคนเขียน ไม่ใช่ backend
-- ---------------------------------------------------------------------
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'advisor_api') THEN
        GRANT USAGE ON SCHEMA web TO advisor_api;
        GRANT SELECT ON ALL TABLES IN SCHEMA web TO advisor_api;
        GRANT INSERT, UPDATE ON web.site_courses, web.news,
                                web.knowledge_articles, web.ai_settings TO advisor_api;
        GRANT EXECUTE ON FUNCTION web.touch_updated_at() TO advisor_api;
        GRANT SELECT ON web.external_news TO advisor_api;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'advisor_ingest') THEN
        GRANT USAGE ON SCHEMA web TO advisor_ingest;
        GRANT SELECT ON ALL TABLES IN SCHEMA web TO advisor_ingest;
        -- ตัวดึงข่าวจากภายนอกเขียนตารางนี้ตารางเดียว
        GRANT INSERT, UPDATE ON web.external_news TO advisor_ingest;
        GRANT EXECUTE ON FUNCTION web.touch_updated_at() TO advisor_ingest;
    END IF;
END;
$$;

INSERT INTO mko.schema_migrations (version) VALUES ('005_web_schema')
    ON CONFLICT (version) DO NOTHING;

COMMIT;
