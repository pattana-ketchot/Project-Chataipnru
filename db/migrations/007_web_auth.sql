-- =====================================================================
-- 007_web_auth.sql — ตัวตนและสิทธิ์ผู้ใช้หน้าเว็บ (Phase 4 — ถอด Supabase Auth)
--
-- 005 เว้นเรื่องนี้ไว้โดยตั้งใจ เขียนไว้ว่า "ต้องตัดสินใจเรื่อง auth ก่อนว่าจะให้ตัวตน
-- ผู้ใช้อยู่ที่ใด ถ้าสร้างตอนนี้จะกลายเป็นที่บอกสิทธิ์สองแห่ง ซึ่งเป็นปัญหาเดิมในรูปแบบใหม่"
--
-- การตัดสินใจคือ **public.users เป็นที่เดียวที่บอกตัวตนและสิทธิ์**
--
-- หลักเดียวกับ 001–006
--   - เพิ่มของใหม่ ไม่ DROP ไม่เปลี่ยนชนิดคอลัมน์เดิม
--   - **รันซ้ำได้โดยไม่เปลี่ยนสิทธิ์ของใคร** (ดูหัวข้อถัดไป)
--   - ไม่แตะ mko และไม่แตะ web
--
-- ‼ การรันซ้ำต้องไม่อนุมัติบัญชีที่สมัครหลัง migration
-- --------------------------------------------------
-- รุ่นแรกของไฟล์นี้เขียนเงื่อนไข backfill ว่า
--     WHERE role = 'user' AND status = 'pending' AND created_at < now()
-- ซึ่ง `created_at < now()` **เป็นจริงเสมอ** การรันซ้ำจึงอนุมัติบัญชีที่สมัครใหม่
-- และยังรออนุมัติอยู่ทั้งหมด — เป็นการให้สิทธิ์โดยไม่มีใครกด
--
-- แก้โดยผูก backfill ไว้กับ "ครั้งแรกเท่านั้น" ด้วยตารางบันทึก migration
-- รอบถัดไปข้ามทั้งบล็อก ไม่แตะแถวใดเลย
--
-- ทำไม role เป็นแหล่งความจริง และ is_admin เป็นเงาสะท้อนทางเดียว
-- ------------------------------------------------------------
-- is_admin เป็น boolean ตอบได้แค่ "ใช่หรือไม่ใช่ผู้ดูแล" แต่ระบบจริงมีสามระดับ
-- (admin / editor / user) และมีสถานะการอนุมัติแยกอีกชั้น
--
-- ตรวจโค้ดทั้งรีโปแล้ว **is_admin ถูกอ่านที่เดียวคือ api/deps.py:52 และไม่มีที่ใดเขียนเลย**
-- จึงทำเป็นทางเดียว: เขียนที่ role แล้ว is_admin ตามเสมอ · เขียนที่ is_admin ไม่มีผล
--
-- รุ่นแรกทำสองทาง ซึ่งนอกจากจะไม่จำเป็นแล้วยังกำกวมเมื่อสองค่าขัดกันในคำสั่งเดียว
-- =====================================================================
BEGIN;

-- ---------------------------------------------------------------------
-- 1. สิทธิ์และสถานะบัญชี
-- ---------------------------------------------------------------------
ALTER TABLE public.users
    ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'user',
    ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS email_verified_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS failed_login_count SMALLINT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS locked_until TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ,
    -- รูปแบบการเก็บรหัสผ่าน — ดูหัวข้อ 5
    ADD COLUMN IF NOT EXISTS password_scheme TEXT NOT NULL DEFAULT 'bcrypt_sha256';

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'users_role_check') THEN
        ALTER TABLE public.users
            ADD CONSTRAINT users_role_check CHECK (role IN ('admin', 'editor', 'user'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'users_status_check') THEN
        ALTER TABLE public.users
            ADD CONSTRAINT users_status_check CHECK (status IN ('pending', 'approved', 'rejected'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'users_password_scheme_check') THEN
        ALTER TABLE public.users
            ADD CONSTRAINT users_password_scheme_check
            CHECK (password_scheme IN ('bcrypt_sha256', 'bcrypt'));
    END IF;
END;
$$;

COMMENT ON COLUMN public.users.role IS
    'แหล่งความจริงของสิทธิ์ — admin/editor/user · is_admin เป็นเงาสะท้อนทางเดียว เขียนที่ is_admin ไม่มีผล';
COMMENT ON COLUMN public.users.status IS
    'สถานะการอนุมัติ — ต้องเป็น approved จึงเข้าส่วนผู้ดูแลได้ บัญชีใหม่เป็น pending เสมอ';
COMMENT ON COLUMN public.users.password_scheme IS
    'bcrypt_sha256 = ของระบบนี้ · bcrypt = นำเข้าจาก Supabase และยังไม่ได้เข้าสู่ระบบหลังย้าย';

-- ---------------------------------------------------------------------
-- 2. บันทึกสภาพเดิมไว้ถอนกลับ — ก่อนแตะข้อมูลใด ๆ
--
-- ถอนกลับด้วยการคืนค่าจากตารางนี้ ไม่ใช่การเดาว่า "ค่าเดิมน่าจะเป็นอะไร"
-- ตารางนี้ **ไม่ถูกเขียนซ้ำ** ในการรันรอบถัดไป มิฉะนั้นจะบันทึกสภาพหลังย้ายทับของเดิม
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.migration_007_user_backup (
    user_id     UUID PRIMARY KEY REFERENCES public.users(id) ON DELETE CASCADE,
    is_admin    BOOLEAN NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.migration_007_user_backup IS
    'สภาพ is_admin ก่อน 007 — ใช้ถอนกลับ ลบได้เมื่อแน่ใจว่าไม่ต้องถอนแล้ว';

-- ---------------------------------------------------------------------
-- 3. แปลงผู้ใช้เดิม — **ครั้งแรกเท่านั้น**
--
-- ผู้ใช้ที่มีอยู่ก่อนไฟล์นี้ถือว่าอนุมัติแล้ว เพราะพวกเขาใช้งานระบบอยู่จริง
-- การตั้งเป็น pending จะตัดสิทธิ์คนที่เคยเข้าได้
--
-- รอบถัดไปบล็อกนี้ถูกข้ามทั้งก้อน บัญชีที่สมัครหลังจากนี้จึงยังเป็น pending ตามเดิม
-- ---------------------------------------------------------------------
DO $$
DECLARE
    v_first_run BOOLEAN;
    v_rows      INTEGER;
BEGIN
    SELECT NOT EXISTS (SELECT 1 FROM mko.schema_migrations WHERE version = '007_web_auth')
      INTO v_first_run;

    IF NOT v_first_run THEN
        RAISE NOTICE '007 เคยรันแล้ว — ข้ามขั้นแปลงผู้ใช้เดิม ไม่แตะสิทธิ์ของใคร';
        RETURN;
    END IF;

    INSERT INTO public.migration_007_user_backup (user_id, is_admin)
    SELECT id, is_admin FROM public.users
    ON CONFLICT (user_id) DO NOTHING;
    GET DIAGNOSTICS v_rows = ROW_COUNT;
    RAISE NOTICE 'บันทึกสภาพเดิมไว้ % แถว', v_rows;

    UPDATE public.users
       SET role   = CASE WHEN is_admin THEN 'admin' ELSE 'user' END,
           status = 'approved';
    GET DIAGNOSTICS v_rows = ROW_COUNT;
    RAISE NOTICE 'แปลงผู้ใช้เดิม % แถว เป็น approved', v_rows;
END;
$$;

-- ---------------------------------------------------------------------
-- 4. is_admin เป็นเงาสะท้อนของ role — ทางเดียว
--
-- เขียนที่ role แล้ว is_admin ตามเสมอ · เขียนที่ is_admin อย่างเดียวไม่มีผล
-- เพราะ trigger เขียนทับด้วยค่าที่คำนวณจาก role ทุกครั้ง
--
-- ไม่กำกวมเมื่อสองค่าถูกเขียนขัดกันในคำสั่งเดียว — role ชนะเสมอ
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.sync_user_admin_flag() RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $$
BEGIN
    NEW.is_admin := (NEW.role = 'admin');
    RETURN NEW;
END;
$$;

COMMENT ON FUNCTION public.sync_user_admin_flag() IS
    'is_admin := (role = admin) ทุกครั้งที่เขียนแถว — role เป็นแหล่งความจริงทางเดียว';

DROP TRIGGER IF EXISTS trg_sync_user_admin_flag ON public.users;
CREATE TRIGGER trg_sync_user_admin_flag
    BEFORE INSERT OR UPDATE ON public.users
    FOR EACH ROW EXECUTE FUNCTION public.sync_user_admin_flag();

-- ทำให้แถวที่ค่าขัดกันอยู่ตรงกัน — ปลอดภัยที่จะรันซ้ำและแตะเฉพาะแถวที่ไม่ตรง
--
-- `SET role = role` ตรงนี้ทำงานได้เพราะ trigger คำนวณ is_admin ใหม่ทุกครั้งที่เขียนแถว
-- ไม่ได้พึ่งเงื่อนไข IS DISTINCT FROM แบบรุ่นแรกซึ่งไม่เคยเป็นจริง
UPDATE public.users
   SET role = role
 WHERE is_admin IS DISTINCT FROM (role = 'admin');

-- ---------------------------------------------------------------------
-- 5. ทะเบียน refresh token — ทำให้ "ออกจากระบบ" และ "ถอนสิทธิ์" มีผลจริง
--
-- JWT ที่ออกไปแล้วเรียกคืนไม่ได้ การถอนสิทธิ์คนที่ถูกปลดจึงทำไม่ได้เลยถ้าไม่มีทะเบียนนี้
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.auth_sessions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    -- sha256 ของ refresh token — ไม่เก็บค่าดิบ
    token_hash  TEXT NOT NULL UNIQUE,
    user_agent  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at  TIMESTAMPTZ NOT NULL,
    revoked_at  TIMESTAMPTZ,
    CHECK (expires_at > created_at)
);

CREATE INDEX IF NOT EXISTS idx_auth_sessions_user
    ON public.auth_sessions (user_id) WHERE revoked_at IS NULL;

-- ---------------------------------------------------------------------
-- 6. token ใช้ครั้งเดียว — รีเซ็ตรหัสผ่าน และยืนยันอีเมล
--
-- เก็บเป็น sha256 ไม่เก็บค่าดิบ ฐานข้อมูลรั่วแล้วต้องรีเซ็ตรหัสผ่านของใครไม่ได้
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.auth_tokens (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    purpose     TEXT NOT NULL CHECK (purpose IN ('password_reset', 'email_verify')),
    token_hash  TEXT NOT NULL UNIQUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at  TIMESTAMPTZ NOT NULL,
    used_at     TIMESTAMPTZ,
    CHECK (expires_at > created_at)
);

CREATE INDEX IF NOT EXISTS idx_auth_tokens_lookup
    ON public.auth_tokens (user_id, purpose) WHERE used_at IS NULL;

-- ---------------------------------------------------------------------
-- 7. สิทธิ์ของ role ในฐานข้อมูล
--
-- advisor_api เป็นตัวที่ FastAPI ใช้ · advisor_web (webapi) ไม่ได้สิทธิ์เพิ่ม
-- เพราะหลังย้ายเสร็จ webapi จะถูกเลิกใช้
-- ---------------------------------------------------------------------
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'advisor_api') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON public.auth_sessions TO advisor_api;
        GRANT SELECT, INSERT, UPDATE, DELETE ON public.auth_tokens   TO advisor_api;
    END IF;
END;
$$;

INSERT INTO mko.schema_migrations (version) VALUES ('007_web_auth')
    ON CONFLICT (version) DO NOTHING;

COMMIT;

-- =====================================================================
-- ถอนกลับ — คืนค่าจากหลักฐาน ไม่ใช่จากการเดา
-- =====================================================================
-- ‼ is_admin **ถูกเปลี่ยนจริง** โดย trigger และขั้นแปลงผู้ใช้เดิม
--    (รุ่นแรกของไฟล์นี้เขียนว่า "ไม่เคยถูกแตะ" ซึ่งผิด)
--    จึงต้องคืนค่าจาก public.migration_007_user_backup
--
-- ถอนตามลำดับนี้
--
-- BEGIN;
-- DROP TRIGGER IF EXISTS trg_sync_user_admin_flag ON public.users;
--
-- -- คืน is_admin จากที่บันทึกไว้ (ต้องทำหลัง DROP TRIGGER ไม่งั้นถูกเขียนทับ)
-- UPDATE public.users u
--    SET is_admin = b.is_admin
--   FROM public.migration_007_user_backup b
--  WHERE b.user_id = u.id AND u.is_admin IS DISTINCT FROM b.is_admin;
--
-- -- ตรวจก่อนไปต่อ: ต้องได้ 0 แถว
-- SELECT count(*) AS ยังไม่ตรง
--   FROM public.users u JOIN public.migration_007_user_backup b ON b.user_id = u.id
--  WHERE u.is_admin IS DISTINCT FROM b.is_admin;
--
-- DROP FUNCTION IF EXISTS public.sync_user_admin_flag();
-- DROP TABLE IF EXISTS public.auth_tokens;
-- DROP TABLE IF EXISTS public.auth_sessions;
-- ALTER TABLE public.users
--     DROP COLUMN IF EXISTS role,
--     DROP COLUMN IF EXISTS status,
--     DROP COLUMN IF EXISTS email_verified_at,
--     DROP COLUMN IF EXISTS failed_login_count,
--     DROP COLUMN IF EXISTS locked_until,
--     DROP COLUMN IF EXISTS last_login_at,
--     DROP COLUMN IF EXISTS password_scheme;
-- DELETE FROM mko.schema_migrations WHERE version = '007_web_auth';
-- -- เก็บ migration_007_user_backup ไว้จนแน่ใจว่าไม่ต้องถอนอีก
-- COMMIT;
--
-- ผู้ใช้ที่สมัครหลัง migration ไม่มีแถวใน backup — is_admin ของพวกเขาเป็น false
-- จากค่าตั้งต้นอยู่แล้ว จึงไม่ต้องคืนค่า
-- =====================================================================
