-- คืนค่าเดิมของแถว "เทคโนโลยีการเกษตรสมัยใหม่" (course_id กลับไปเป็น NULL)
--
-- ค่าเดิมก่อนแก้คือ NULL ตามที่บันทึกไว้เมื่อ 30 ต.ค. 2569
-- แก้เฉพาะเมื่อค่าปัจจุบันเป็นรหัสที่สคริปต์ติดตั้งใส่ไว้เท่านั้น ถ้ามีใครเปลี่ยนเป็นค่าอื่น
-- ภายหลัง จะยกเลิกทั้งชุดแทนการเขียนทับ

BEGIN;

\echo 'ค่าก่อนคืน:'
SELECT s.id, s.title, coalesce(s.course_id::text, '(ว่าง)') AS course_id
  FROM web.site_courses s
 WHERE s.id = 'eb3812e5-24ee-42f9-9448-bc538deb207f';

DO $$
DECLARE n integer;
BEGIN
    UPDATE web.site_courses
       SET course_id = NULL,
           updated_at = now()
     WHERE id = 'eb3812e5-24ee-42f9-9448-bc538deb207f'
       AND course_id = '1bcfb69c-a88f-4652-8799-c3d9fb6aa11d';

    GET DIAGNOSTICS n = ROW_COUNT;
    IF n <> 1 THEN
        RAISE EXCEPTION 'ต้องคืน 1 แถว แต่คืนไป % แถว — ยกเลิกทั้งชุด', n;
    END IF;
END $$;

\echo 'ค่าหลังคืน:'
SELECT s.id, s.title, coalesce(s.course_id::text, '(ว่าง)') AS course_id
  FROM web.site_courses s
 WHERE s.id = 'eb3812e5-24ee-42f9-9448-bc538deb207f';

COMMIT;
