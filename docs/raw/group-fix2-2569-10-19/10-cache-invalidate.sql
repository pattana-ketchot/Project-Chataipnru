-- =====================================================================
-- ล้างเฉพาะแถวแคชที่เกี่ยวกับคำตอบที่ release นี้เปลี่ยน
--
-- ทำไมต้องล้างด้วยมือ
-- ------------------
-- แคชผูกกับ corpus_version = "<จำนวน chunk>@<เวลา chunk ล่าสุด>/k<TOP_K>/v<รุ่นตรรกะ>"
-- และการหยิบแคชมาใช้ตรงทั้ง question_key และ corpus_version (answer_cache.py บรรทัด 109)
-- release นี้ **ไม่ได้เพิ่ม chunk** และ **ไม่ได้ขยับรุ่นตรรกะ** (_LOGIC_VERSION ยังเป็น 34)
-- corpus_version จึงเท่าเดิม แถวแคชเดิมยังถูกหยิบมาใช้ ผู้ใช้ที่ถามคำถามเดิม
-- จะยังได้คำตอบก่อนแก้
--
-- ทำไมไม่ล้างทั้งตาราง
-- -------------------
-- วัดบน production เมื่อ 19 ต.ค. 2569: ตารางมี 183 แถว ตรงเกณฑ์นี้ 12 แถว (6.6%)
-- ส่วนที่เหลือเป็นคำถามที่ release นี้ไม่ได้แตะเลย การล้างทั้งตารางทำให้คำถามเหล่านั้น
-- ต้องเรียกโมเดลใหม่ทั้งหมดโดยไม่จำเป็น — เปลืองโควตาและทำให้ผู้ใช้รอนาน
--
-- เกณฑ์การเลือกแถว — มาจากสองการเปลี่ยนแปลงของ release นี้
-- -----------------------------------------------------
-- 1) subjects.py: คำถามระดับกลุ่มไม่ถูกลดเหลือการค้นวิชาเดียว + ป้ายกำกับ
--    requirement ค่าใหม่ -> แถวที่คำถามหรือคำตอบแตะกลุ่มฝึกประสบการณ์/สหกิจ
--    หรือสามรหัสวิชาในกลุ่มนั้น
-- 2) chat.py: การเติมหน้าอ้างอิงที่ยืนยันข้ออ้างที่ยังค้าง -> แถวที่คำตอบเดิม
--    มีท้ายข้อความว่า "ยังยืนยันไม่ได้จากหน้าที่อ้าง" เพราะแถวเหล่านี้คือแถวที่
--    การเติมหน้าอาจเปลี่ยนสถานะข้ออ้างและเปลี่ยนบรรทัดที่มา
--    (วัดได้ 7 แถวที่รุ่นที่ใช้อยู่ — ถ้าไม่ล้าง ผู้ใช้จะยังเห็นคำเตือนเดิม
--     ทั้งที่ระบบยืนยันข้ออ้างนั้นได้แล้ว)
--
-- เกณฑ์นี้ไม่กรองด้วย corpus_version เพราะเลขรุ่นที่ใช้อยู่อาจเปลี่ยนได้
-- ก่อนถึงเวลา deploy การผูกเลขรุ่นไว้ตายตัวจะทำให้พลาดแถวที่ควรล้าง
-- ผลคือจะล้างแถวรุ่นเก่าที่หยิบมาใช้ไม่ได้ติดไปด้วย (วัดได้ 1 แถว) ซึ่งไม่มีผลเสีย
-- และถูกสำรองไว้เหมือนแถวอื่น
--
-- รันด้วย superuser · การสำรองอยู่ในไฟล์นี้เอง (ขั้นที่ 1) ไม่ต้องรันอะไรก่อน
-- คืนค่าได้ด้วย 20-cache-restore.sql
-- =====================================================================
\set ON_ERROR_STOP on
BEGIN;

-- ---------------------------------------------------------------------
-- 1. สำรองแถวที่จะลบไว้ทั้งแถว (ไม่ใช่แค่คีย์) เพื่อให้ใส่กลับได้ครบ
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS public.chat_answer_cache_bak_groupfix2;

CREATE TABLE public.chat_answer_cache_bak_groupfix2 AS
SELECT * FROM public.chat_answer_cache
 WHERE question_key LIKE '%สหกิจ%'
    OR question_key LIKE '%ฝึกประสบการณ์%'
    OR question_key LIKE '%ฝึกงาน%'
    OR reply LIKE '%4124813%'
    OR reply LIKE '%4124814%'
    OR reply LIKE '%4124815%'
    OR reply LIKE '%กลุ่มวิชาฝึกประสบการณ์%'
    OR reply LIKE '%ยังยืนยันไม่ได้จากหน้าที่อ้าง%';

-- ---------------------------------------------------------------------
-- 2. ลบเฉพาะแถวที่สำรองไว้ — ผูกกับตารางสำรองโดยตรง ไม่ใช้เงื่อนไขซ้ำ
--    เพื่อให้สิ่งที่ลบกับสิ่งที่สำรองเป็นชุดเดียวกันแน่นอน
-- ---------------------------------------------------------------------
DO $$
DECLARE
    n_backup   bigint;
    n_before   bigint;
    n_deleted  bigint;
    n_after    bigint;
BEGIN
    SELECT count(*) INTO n_backup FROM public.chat_answer_cache_bak_groupfix2;
    SELECT count(*) INTO n_before FROM public.chat_answer_cache;

    IF n_backup = 0 THEN
        RAISE EXCEPTION 'ไม่พบแถวแคชที่ตรงเกณฑ์เลย — ตรวจว่าต่อฐานถูกตัวหรือยัง';
    END IF;
    -- กันพลาด: ถ้าเงื่อนไขกวาดเกินครึ่งตาราง แปลว่าเงื่อนไขผิด ไม่ใช่ข้อมูลผิด
    IF n_backup > n_before / 2 THEN
        RAISE EXCEPTION 'เงื่อนไขกวาด % จาก % แถว ซึ่งกว้างเกินไป — หยุดไว้ก่อน',
                        n_backup, n_before;
    END IF;

    DELETE FROM public.chat_answer_cache c
     USING public.chat_answer_cache_bak_groupfix2 b
     WHERE c.question_key = b.question_key AND c.corpus_version = b.corpus_version;
    GET DIAGNOSTICS n_deleted = ROW_COUNT;

    SELECT count(*) INTO n_after FROM public.chat_answer_cache;

    IF n_deleted <> n_backup THEN
        RAISE EXCEPTION 'ลบ % แถว แต่สำรองไว้ % แถว — ไม่ตรงกัน', n_deleted, n_backup;
    END IF;
    IF n_after <> n_before - n_backup THEN
        RAISE EXCEPTION 'เหลือ % แถว แต่ควรเหลือ %', n_after, n_before - n_backup;
    END IF;

    RAISE NOTICE 'สำรอง % แถว · ลบ % แถว · ก่อน % แถว · เหลือ % แถว',
                 n_backup, n_deleted, n_before, n_after;
END;
$$;

COMMIT;

-- ---------------------------------------------------------------------
-- 3. รายงานสิ่งที่ลบไป เพื่อแนบในรายงาน deploy
-- ---------------------------------------------------------------------
SELECT left(question_key, 56) AS "คีย์คำถามที่ลบ",
       right(corpus_version, 3) AS "รุ่น",
       status, hits,
       to_char(last_used_at, 'YYYY-MM-DD') AS "ใช้ล่าสุด"
  FROM public.chat_answer_cache_bak_groupfix2
 ORDER BY last_used_at DESC;

SELECT count(*) AS "แถวแคชที่เหลือทั้งตาราง" FROM public.chat_answer_cache;
