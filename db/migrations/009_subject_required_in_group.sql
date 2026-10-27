-- =====================================================================
-- 009: เพิ่มค่า requirement ที่สี่ — 'required_in_group'
--
-- ปัญหาที่แก้
-- ----------
-- cs66.pdf หน้า 19 เขียนกลุ่ม 2.4 ไว้แบบนี้
--
--     2.4) กลุ่มวิชาฝึกประสบการณ์วิชาชีพหรือสหกิจศึกษา ไม่น้อยกว่า 7 หน่วยกิต
--          4124813 การเตรียมความพร้อมฝึกประสบการณ์วิชาชีพและสหกิจศึกษา   2(90)
--          ให้เลือกรายวิชาต่อไปนี้ ไม่น้อยกว่า 5 หน่วยกิต
--          4124814 การฝึกประสบการณ์วิชาชีพวิทยาการคอมพิวเตอร์            5(450)
--          4124815 สหกิจศึกษา                                          6(540)
--
-- บรรทัด "ให้เลือกรายวิชาต่อไปนี้" อยู่ **หลัง** 4124813 กติกาการเลือกจึงใช้กับ
-- 4124814 และ 4124815 เท่านั้น ส่วน 4124813 เป็นวิชาที่ต้องเรียน
-- (2 + อย่างน้อย 5 = ไม่น้อยกว่า 7 ซึ่งตรงกับหัวข้อกลุ่มพอดี)
--
-- ของเดิมมีค่าให้เลือกสามค่า จึงต้องยัด 4124813 เป็น 'choose_group' ซึ่งแสดงผลว่า
-- "วิชาในกลุ่มที่ต้องเลือกให้ครบหน่วยกิตขั้นต่ำ" — ผิดจากเล่ม
--
-- ทำไมไม่ใช้ 'required' ที่มีอยู่แล้ว
-- --------------------------------
-- 'required' ในระบบนี้มีความหมายผูกกับยอดที่เล่มพิมพ์ไว้ คือ
--     ศึกษาทั่วไปบังคับ 24 + กลุ่มวิชาแกน 18 + กลุ่มวิชาเฉพาะด้าน 54 = 96 หน่วยกิต
-- (35 วิชา) ซึ่งเป็นยอดที่ขั้นตรวจรับใน pipeline/mko/subjects_db.py ใช้ยืนยันความถูกต้อง
--
-- เล่มนับกลุ่มฝึกประสบการณ์ฯ แยกต่างหาก (ไม่น้อยกว่า 7) ไม่ได้รวมอยู่ใน 96
-- ถ้าเปลี่ยน 4124813 เป็น 'required' ยอดจะกลายเป็น 36 วิชา 98 หน่วยกิต
-- ซึ่ง **ไม่ตรงกับตัวเลขใดที่พิมพ์อยู่ในเล่ม** เท่ากับสร้างตัวเลขใหม่ที่ไม่มีหลักฐาน
--
-- ค่าที่สี่จึงแยกสองเรื่องออกจากกัน: "ต้องเรียนไหม" กับ "อยู่ในกลุ่มที่มีเพดานขั้นต่ำไหม"
--
-- รันซ้ำได้ · ไม่แตะข้อมูลที่มีอยู่ · ย้อนกลับได้ด้วยคำสั่งท้ายไฟล์
-- =====================================================================
BEGIN;

ALTER TABLE mko.published_subjects
    DROP CONSTRAINT IF EXISTS published_subjects_requirement_check;

ALTER TABLE mko.published_subjects
    ADD CONSTRAINT published_subjects_requirement_check
    CHECK (requirement IN ('required', 'elective', 'choose_group', 'required_in_group'));

-- ตารางฝั่งสกัดใช้ค่าชุดเดียวกัน — ตั้งให้ตรงกันไว้ก่อน แม้ตอนนี้ยังไม่มีแถว
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_constraint
                WHERE conname = 'subjects_requirement_check'
                  AND conrelid = 'mko.subjects'::regclass) THEN
        ALTER TABLE mko.subjects DROP CONSTRAINT subjects_requirement_check;
        ALTER TABLE mko.subjects ADD CONSTRAINT subjects_requirement_check
            CHECK (requirement IN ('required', 'elective', 'choose_group', 'required_in_group'));
    END IF;
END;
$$;

INSERT INTO mko.schema_migrations (version) VALUES ('009_subject_required_in_group')
    ON CONFLICT (version) DO NOTHING;

COMMIT;

-- =====================================================================
-- ย้อนกลับ
--
-- ต้องเปลี่ยนแถวที่ใช้ค่าใหม่กลับก่อน ไม่งั้นข้อบังคับเดิมจะสร้างไม่ได้
--
--   BEGIN;
--   UPDATE mko.published_subjects SET requirement = 'choose_group'
--    WHERE requirement = 'required_in_group';
--   ALTER TABLE mko.published_subjects DROP CONSTRAINT published_subjects_requirement_check;
--   ALTER TABLE mko.published_subjects ADD CONSTRAINT published_subjects_requirement_check
--       CHECK (requirement IN ('required', 'elective', 'choose_group'));
--   DELETE FROM mko.schema_migrations WHERE version = '009_subject_required_in_group';
--   COMMIT;
-- =====================================================================
