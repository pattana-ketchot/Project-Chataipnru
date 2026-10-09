-- =====================================================================
-- 006_web_identity_mapping.sql — เส้นเชื่อมตัวตนหน้าเว็บ และสิทธิ์ของ advisor_web
--
-- ดูการออกแบบใน docs/B1_ACTIVE_USER_MAPPING_FINAL_DECISION.md
-- สิทธิ์ของ role ดูที่ docs/B1_ADVISOR_WEB_ROLE_DESIGN.md
-- ผลการตรวจ role จริงดูที่ docs/B1_ADVISOR_WEB_PROVISION_RESULT.md
--
-- หลักเดียวกับ 001–005:
--   - ไม่ DROP อะไรทั้งสิ้น
--   - ไม่แตะข้อมูลแม้แถวเดียว
--   - รันซ้ำได้
--   - ไม่แตะ schema mko
--
-- ไฟล์นี้ทำสองเรื่องที่แยกจากกันไม่ได้
--   1. เพิ่มที่เก็บ "ตัวตนฝั่ง Supabase" ลงใน public.users
--   2. ให้สิทธิ์ advisor_web เท่าที่ endpoint ที่ล็อกไว้ต้องใช้จริง
-- เรื่องที่สองต้องการเรื่องแรก เพราะ advisor_web ต้องอ่าน supabase_user_id
-- เพื่อแปลงผู้ใช้ Supabase เป็นผู้ใช้ของฐานข้อมูลนี้
--
-- ทำไม supabase_user_id อยู่ใน public.users ไม่ใช่ตารางใหม่
-- --------------------------------------------------------
-- ความสัมพันธ์เป็นหนึ่งต่อหนึ่ง และเป็นคุณสมบัติของผู้ใช้คนนั้นเอง ไม่ใช่ข้อเท็จจริง
-- ที่มีหลายแถวต่อผู้ใช้หนึ่งคน ตารางแยกจะเพิ่ม JOIN ให้ทุก query ที่ต้องแปลงตัวตน
-- โดยไม่ได้อะไรกลับมา และยังเปิดโอกาสให้เกิดแถวกำพร้า
--
-- เอกสารออกแบบเคยพิจารณาตาราง web.user_identity_map แล้วตัดทิ้งด้วยเหตุผลนี้
--
-- ทำไมเป็น NULL ได้ และทำไมไม่มี DEFAULT
-- ---------------------------------------
-- ผู้ใช้ 198 คนในฐานข้อมูลนี้ไม่มีใครมีตัวตนฝั่ง Supabase มาก่อน การบังคับ NOT NULL
-- จะทำให้ ALTER TABLE ล้มทันที และการใส่ DEFAULT จะเท่ากับยัดค่าปลอมให้ทุกแถว
-- ซึ่งเลวร้ายกว่าไม่มีค่า เพราะค่าปลอมหน้าตาเหมือนค่าจริง
--
-- NULL ที่นี่มีความหมายชัดเจน: "ผู้ใช้คนนี้ยังไม่มีตัวตนฝั่ง Supabase ที่จับคู่ไว้"
--
-- ทำไมเป็น partial unique index ไม่ใช่ UNIQUE ธรรมดา
-- ---------------------------------------------------
-- UNIQUE ธรรมดาใน PostgreSQL ยอมให้มีหลาย NULL อยู่แล้ว จึงได้ผลเหมือนกันในทางปฏิบัติ
-- แต่ partial index เขียนเจตนาออกมาตรง ๆ ว่า "ข้อห้ามซ้ำบังคับเฉพาะค่าที่ไม่ใช่ NULL"
-- และไม่เก็บแถว NULL ไว้ใน index เลย ซึ่งสำคัญเพราะวันนี้ 198 แถวเป็น NULL ทั้งหมด
--
-- รูปแบบเดียวกับ uq_site_courses_course และ uq_external_news_slug ใน 005
--
-- ทำไมไม่มี FOREIGN KEY ไป Supabase
-- ---------------------------------
-- auth.users ของ Supabase อยู่คนละฐานข้อมูลคนละเครื่อง PostgreSQL ไม่มีทางบังคับ
-- ความถูกต้องข้ามฐานข้อมูลได้ การประกาศ FK ที่บังคับใช้ไม่ได้จะสร้างความมั่นใจปลอม
-- ความถูกต้องของค่านี้เป็นหน้าที่ของขั้นตอน mapping ที่ต้องขออนุมัติแยก
--
-- ทำไมต้องหยุดถ้าไม่มี advisor_web — ต่างจาก 002–005
-- ---------------------------------------------------
-- 005 ใช้ IF EXISTS แล้วข้ามเงียบ ๆ ถ้าไม่มี role เพราะตอนนั้นสิทธิ์เป็นของแถม
-- ที่ให้เมื่อมี role อยู่แล้ว ถ้าไม่มีก็แค่ไม่ได้สิทธิ์ ไม่มีอะไรพัง
--
-- ไฟล์นี้ตรงกันข้าม — สิทธิ์ของ advisor_web คือเหตุผลครึ่งหนึ่งที่ migration นี้มีอยู่
-- ถ้าข้ามเงียบ ๆ จะได้ฐานข้อมูลที่ ledger บอกว่า "006 ลงแล้ว" แต่ webapi ต่อไม่ได้
-- และไม่มีใครรู้จนกว่าจะ deploy แล้วพัง จึง RAISE EXCEPTION เพื่อให้ทั้ง transaction
-- ถอนกลับ และคนรันเห็นสาเหตุทันทีตั้งแต่ตอน apply
--
-- migration นี้ไม่สร้าง role ให้เอง เพราะการสร้าง role ต้องมีรหัสผ่านซึ่งเป็นความลับ
-- ที่ต้องไม่อยู่ในไฟล์ที่ commit ลง repository
--
-- สิ่งที่ตั้งใจยังไม่ทำในไฟล์นี้
-- ----------------------------
-- 1. ไม่เติมค่า supabase_user_id ให้ผู้ใช้คนใด — เป็น data migration ที่ต้องขออนุมัติแยก
-- 2. ไม่ REVOKE อะไรจาก advisor_api หรือ advisor_ingest
-- 3. ไม่ให้ DELETE แก่ advisor_web บนตารางใด — หลักเดียวกับ 002, 004 และ 005
-- =====================================================================
BEGIN;

-- ---------------------------------------------------------------------
-- 1. ที่เก็บตัวตนฝั่ง Supabase
-- ---------------------------------------------------------------------
ALTER TABLE public.users
    ADD COLUMN IF NOT EXISTS supabase_user_id UUID;

COMMENT ON COLUMN public.users.supabase_user_id IS
    'UUID ของผู้ใช้ใน Supabase Auth ที่จับคู่กับผู้ใช้แถวนี้ — NULL แปลว่ายังไม่ได้จับคู่ ไม่ใช่ FK เพราะอยู่คนละฐานข้อมูล';

CREATE UNIQUE INDEX IF NOT EXISTS uq_users_supabase_user_id
    ON public.users (supabase_user_id) WHERE supabase_user_id IS NOT NULL;

-- ---------------------------------------------------------------------
-- 2. ด่านตรวจก่อนให้สิทธิ์
--
-- ต้องหยุดทั้ง transaction ถ้าไม่มี role ไม่ใช่ข้ามไปเงียบ ๆ เหตุผลอยู่ในหัวไฟล์
-- ---------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'advisor_web') THEN
        RAISE EXCEPTION 'ไม่พบ role advisor_web — migration 006 ให้สิทธิ์ใครไม่ได้'
            USING HINT = 'สร้าง role ก่อนด้วยขั้นตอนใน docs/B1_ADVISOR_WEB_PROVISION_RESULT.md ข้อ 10.1 แล้วจึง apply ไฟล์นี้ใหม่',
                  ERRCODE = 'undefined_object';
    END IF;
END;
$$;

-- ---------------------------------------------------------------------
-- 3. สิทธิ์บน public.users — ระดับคอลัมน์เท่านั้น
--
-- webapi ต้องการจาก public.users แค่สามอย่าง
--   id                 เอาไว้เขียนลง created_by / updated_by ของตารางใน web
--   is_active          เอาไว้ปฏิเสธผู้ใช้ที่ถูกปิดบัญชี
--   supabase_user_id   เอาไว้แปลงผู้ใช้ Supabase เป็นผู้ใช้ของฐานข้อมูลนี้
--
-- ไม่ให้ SELECT ระดับตาราง เพราะจะทำให้อ่าน email กับ password_hash ได้ทันที
-- การให้ระดับคอลัมน์ทำให้ SELECT * ถูกปฏิเสธด้วย ซึ่งเป็นผลพลอยได้ที่ต้องการ —
-- โค้ดที่เผลอเขียน SELECT * จะพังตั้งแต่ทดสอบ ไม่ใช่หลุดข้อมูลออกไปเงียบ ๆ
--
-- รูปแบบเดียวกับ GRANT SELECT (id, file_sha256, staging_path, status)
-- ON mko.crawl_sources ใน 004
--
-- ไม่ให้ INSERT / UPDATE / DELETE เลย — การสร้างและแก้ไขบัญชีผู้ใช้เป็นงานของ
-- advisor_api ไม่ใช่ของบริการที่รับคำขอจากหน้าเว็บ
-- ---------------------------------------------------------------------
GRANT SELECT (id, is_active, supabase_user_id) ON public.users TO advisor_web;

-- ---------------------------------------------------------------------
-- 4. สิทธิ์บน schema web — ตามตาราง endpoint ที่ล็อกไว้
--
-- อ่านได้ทุกตาราง เขียนได้เฉพาะตารางที่หน้าผู้ดูแลแก้ไขจริง
--
-- ai_settings ให้ UPDATE แต่ไม่ให้ INSERT เพราะเป็นตารางค่าตั้งแถวเดียว
-- การเพิ่มแถวใหม่คือการสร้างชุดค่าตั้งคู่ขนาน ซึ่งเป็นสิ่งที่ไม่ควรเกิดจากโค้ด
--
-- external_news อ่านอย่างเดียว เพราะเป็นข้อมูลที่ตัวดึงข่าวภายนอกเป็นคนเขียน
-- (advisor_ingest) ไม่ใช่บริการหน้าเว็บ
--
-- ไม่ให้ DELETE บนตารางใดเลย — หลักเดียวกับ 002, 004 และ 005 คือการลบต้องเป็น
-- การตัดสินใจที่ทำด้วยมือโดยผู้มีสิทธิ์ระดับ owner ไม่ใช่สิ่งที่โค้ดทำได้เอง
-- การซ่อนเนื้อหาจากหน้าเว็บทำได้ด้วย is_published / status อยู่แล้ว
-- ---------------------------------------------------------------------
GRANT USAGE ON SCHEMA web TO advisor_web;

GRANT SELECT, INSERT, UPDATE ON web.site_courses        TO advisor_web;
GRANT SELECT, INSERT, UPDATE ON web.news                TO advisor_web;
GRANT SELECT, INSERT, UPDATE ON web.knowledge_articles  TO advisor_web;
GRANT SELECT,         UPDATE ON web.ai_settings         TO advisor_web;
GRANT SELECT                 ON web.external_news       TO advisor_web;

-- trigger ตั้ง updated_at ทำงานด้วยสิทธิ์ของผู้เรียก จึงต้องให้ EXECUTE
-- ไม่เช่นนั้น UPDATE ทุกครั้งจะถูกปฏิเสธที่ตัว trigger
GRANT EXECUTE ON FUNCTION web.touch_updated_at() TO advisor_web;

INSERT INTO mko.schema_migrations (version) VALUES ('006_web_identity_mapping')
    ON CONFLICT (version) DO NOTHING;

COMMIT;
