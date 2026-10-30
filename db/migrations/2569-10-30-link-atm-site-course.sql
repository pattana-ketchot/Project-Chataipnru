-- เติม course_id ให้แถว "เทคโนโลยีการเกษตรสมัยใหม่" ของหน้าเว็บ (30 ต.ค. 2569)
--
-- ทำไม
-- ----
-- แถวบนเว็บชื่อ "เทคโนโลยีการเกษตรสมัยใหม่" แต่เล่มในคลังชื่อ "…สาขาวิชาการจัดการ
-- เทคโนโลยีการเกษตรสมัยใหม่ (พ.ศ. 2564)" การเทียบด้วยชื่อจึงไม่เจอ และทุกหน้าที่ถาม
-- ข้อมูลหลักสูตรด้วยชื่อ (หน้ารายละเอียด ตารางเปรียบเทียบ คำสรุปของ AI) ได้ค่าว่าง
-- ทั้งที่เอกสาร atm.pdf (255 หน้า) อยู่ในคลังครบ
--
-- คอลัมน์ course_id มีไว้สำหรับกรณีนี้โดยตรง (ดูหมายเหตุใน
-- backend/app/api/routes/web_compat.py: _course_for_site_title) และฐานทดสอบผูกคู่นี้
-- ไว้แล้วด้วยรหัสเดียวกันเป๊ะ — สคริปต์นี้คือการเติมสิ่งที่ production ขาดไป
--
-- ขอบเขต
-- ------
-- แตะแถวเดียวคือ id = eb3812e5-24ee-42f9-9448-bc538deb207f และแก้เฉพาะเมื่อยังว่าง
-- ถ้าจำนวนแถวที่แก้ไม่เท่ากับ 1 หรือหลังแก้มีแถวอื่นผูกไปเล่มเดียวกัน จะยกเลิกทั้งชุด
--
-- คืนค่าเดิมด้วย 2569-10-30-link-atm-site-course-rollback.sql

BEGIN;

\echo 'ค่าก่อนแก้:'
SELECT s.id, s.title, coalesce(s.course_id::text, '(ว่าง)') AS course_id
  FROM web.site_courses s
 WHERE s.id = 'eb3812e5-24ee-42f9-9448-bc538deb207f';

DO $$
DECLARE n integer;
BEGIN
    UPDATE web.site_courses
       SET course_id = '1bcfb69c-a88f-4652-8799-c3d9fb6aa11d',
           updated_at = now()
     WHERE id = 'eb3812e5-24ee-42f9-9448-bc538deb207f'
       AND title = 'เทคโนโลยีการเกษตรสมัยใหม่'
       AND course_id IS NULL;

    GET DIAGNOSTICS n = ROW_COUNT;
    IF n <> 1 THEN
        RAISE EXCEPTION 'ต้องแก้ 1 แถว แต่แก้ไป % แถว — ยกเลิกทั้งชุด', n;
    END IF;

    -- เล่มปลายทางต้องมีอยู่จริงและยังเปิดใช้งาน
    SELECT count(*) INTO n FROM courses
     WHERE id = '1bcfb69c-a88f-4652-8799-c3d9fb6aa11d' AND is_active;
    IF n <> 1 THEN
        RAISE EXCEPTION 'ไม่พบเล่มปลายทางที่ยังเปิดใช้งาน (พบ % แถว)', n;
    END IF;

    -- ห้ามมีแถวอื่นบนเว็บผูกไปเล่มเดียวกันโดยไม่ตั้งใจ
    SELECT count(*) INTO n FROM web.site_courses
     WHERE course_id = '1bcfb69c-a88f-4652-8799-c3d9fb6aa11d';
    IF n <> 1 THEN
        RAISE EXCEPTION 'หลังแก้มีแถวผูกไปเล่มนี้ % แถว — ยกเลิกทั้งชุด', n;
    END IF;
END $$;

\echo 'ค่าหลังแก้:'
SELECT s.id, s.title, s.course_id, c.title AS linked_course
  FROM web.site_courses s JOIN courses c ON c.id = s.course_id
 WHERE s.id = 'eb3812e5-24ee-42f9-9448-bc538deb207f';

COMMIT;
