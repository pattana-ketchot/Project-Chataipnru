-- ชุดคำสั่งสำหรับสาธิตฐานข้อมูลต่อหน้าอาจารย์
-- วางทีละคำสั่งในช่อง "SQL command" ของ Adminer แล้วกด Execute
-- ทุกคำสั่งเป็น SELECT อย่างเดียว ไม่แก้ข้อมูลใด

-- ─────────────────────────────────────────────────────────────
-- 1. ภาพรวม: ระบบนี้มีกี่ schema กี่ตาราง
--    พูดว่า "ฐานข้อมูลแบ่งเป็นสามส่วนตามหน้าที่ ไม่ได้กองรวมกัน"
-- ─────────────────────────────────────────────────────────────
SELECT table_schema AS "ส่วน",
       count(*) FILTER (WHERE table_type = 'BASE TABLE') AS "ตาราง",
       count(*) FILTER (WHERE table_type = 'VIEW')       AS "วิว"
  FROM information_schema.tables
 WHERE table_schema IN ('public', 'web', 'mko')
 GROUP BY 1 ORDER BY 1;


-- ─────────────────────────────────────────────────────────────
-- 2. หัวใจของระบบถาม-ตอบ: คลังเวกเตอร์
--    พูดว่า "เอกสาร มคอ.2 ถูกตัดเป็นชิ้น แต่ละชิ้นเก็บเลขหน้าไว้ด้วย
--            ระบบจึงบอกได้ว่าคำตอบมาจากหน้าไหน"
-- ─────────────────────────────────────────────────────────────
SELECT count(*)                       AS "จำนวนชิ้นเอกสาร",
       count(DISTINCT document_id)    AS "จำนวนไฟล์",
       min(page_number)               AS "หน้าต่ำสุด",
       max(page_number)               AS "หน้าสูงสุด"
  FROM public.course_chunks;


-- ─────────────────────────────────────────────────────────────
-- 3. ตัวอย่างชิ้นเอกสารจริง พร้อมเลขหน้า
--    พูดว่า "นี่คือข้อมูลที่ AI หยิบไปตอบ ไม่ใช่ความจำของโมเดล"
-- ─────────────────────────────────────────────────────────────
SELECT d.original_filename AS "ไฟล์",
       c.page_number       AS "หน้า",
       regexp_replace(left(c.content, 150), E'[\n\r ]+', ' ', 'g') AS "ข้อความในหน้านั้น"
  FROM public.course_chunks c
  JOIN public.course_documents d ON d.id = c.document_id
 WHERE d.original_filename = 'cs66.pdf'
   AND c.page_number = 19
 ORDER BY c.chunk_index
 LIMIT 3;


-- ─────────────────────────────────────────────────────────────
-- 4. ข้อมูลหลักสูตรที่ผ่านการตรวจรับแล้ว
--    พูดว่า "คำถามบางประเภทตอบจากตรงนี้โดยไม่เรียก AI เลย
--            เพราะเป็นข้อมูลที่คนตรวจรับแล้วและมีเลขหน้าหลักฐานกำกับ"
-- ─────────────────────────────────────────────────────────────
SELECT code        AS "รหัสวิชา",
       name_th     AS "ชื่อวิชา",
       credits     AS "หน่วยกิต",
       requirement AS "ประเภท",
       source_filename || ' หน้า ' || page_start AS "หลักฐาน"
  FROM mko.v_live_subjects
 WHERE 'กลุ่มวิชาฝึกประสบการณ์วิชาชีพหรือสหกิจศึกษา' = ANY(category_path)
 ORDER BY code;


-- ─────────────────────────────────────────────────────────────
-- 5. การออกแบบด้านความปลอดภัย: บัญชีของแอปเขียนอะไรได้บ้าง
--    พูดว่า "บัญชีที่เว็บใช้ แก้คลังเอกสารกับข้อมูลที่ตรวจรับแล้วไม่ได้
--            ต่อให้ถูกเจาะ ก็แก้เนื้อหาหลักสูตรไม่ได้"
-- ─────────────────────────────────────────────────────────────
SELECT 'เขียนได้'   AS "สิทธิ์", n.nspname || '.' || c.relname AS "ตาราง"
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE c.relkind = 'r' AND n.nspname IN ('public', 'web')
   AND has_table_privilege('advisor_api', c.oid, 'UPDATE')
UNION ALL
SELECT 'อ่านได้อย่างเดียว', n.nspname || '.' || c.relname
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE c.relkind = 'r' AND n.nspname = 'public'
   AND c.relname IN ('courses', 'course_documents', 'course_chunks')
   AND NOT has_table_privilege('advisor_api', c.oid, 'UPDATE')
 ORDER BY 1 DESC, 2;


-- ─────────────────────────────────────────────────────────────
-- 6. เผื่ออาจารย์ถามเรื่องความสัมพันธ์ใน ERD
--    พูดว่า "เส้นในไดอะแกรมมาจากข้อบังคับจริงในฐาน ไม่ได้วาดเอง"
-- ─────────────────────────────────────────────────────────────
SELECT tc.relname  AS "ตารางลูก",
       a.attname   AS "คอลัมน์",
       CASE WHEN a.attnotnull THEN 'ต้องมีค่า' ELSE 'ว่างได้' END AS "ค่าว่าง",
       fc.relname  AS "ตารางแม่",
       CASE con.confdeltype WHEN 'c' THEN 'CASCADE' WHEN 'n' THEN 'SET NULL'
            ELSE 'NO ACTION' END AS "เมื่อลบแม่"
  FROM pg_constraint con
  JOIN pg_class tc     ON tc.oid = con.conrelid
  JOIN pg_namespace tn ON tn.oid = tc.relnamespace
  JOIN pg_class fc     ON fc.oid = con.confrelid
  JOIN unnest(con.conkey) WITH ORDINALITY AS k(attnum, ord) ON true
  JOIN pg_attribute a  ON a.attrelid = con.conrelid AND a.attnum = k.attnum
 WHERE con.contype = 'f' AND tn.nspname = 'web'
 ORDER BY 1, 2;
