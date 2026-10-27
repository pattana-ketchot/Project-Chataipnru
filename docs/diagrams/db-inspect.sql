-- ดูโครงสร้างฐานข้อมูล course_advisor ด้วยตัวเอง
-- ทุกคำสั่งในไฟล์นี้เป็น SELECT อย่างเดียว ไม่แก้ข้อมูลใด
--
-- วิธีรัน (จากเครื่องของคุณ)
--   scp -i ~/.ssh/oci.key db-inspect.sql ubuntu@<เซิร์ฟเวอร์>:/tmp/
--   ssh -i ~/.ssh/oci.key ubuntu@<เซิร์ฟเวอร์> \
--     'docker exec -i course-advisor-system-postgres-1 psql -U postgres -d course_advisor -f /dev/stdin < /tmp/db-inspect.sql'

\pset border 2

\echo ===== 1. schema มีอะไรบ้าง และมีกี่ตาราง กี่วิว =====
SELECT table_schema AS "schema",
       count(*) FILTER (WHERE table_type = 'BASE TABLE') AS "ตาราง",
       count(*) FILTER (WHERE table_type = 'VIEW')       AS "วิว"
  FROM information_schema.tables
 WHERE table_schema IN ('public', 'web', 'mko')
 GROUP BY 1 ORDER BY 1;

\echo
\echo ===== 2. ทุกตารางมีกี่แถว =====
SELECT n.nspname AS "schema", c.relname AS "ตาราง",
       (xpath('/row/c/text()',
              query_to_xml(format('select count(*) as c from %I.%I', n.nspname, c.relname),
                           false, true, '')))[1]::text::bigint AS "แถว"
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE c.relkind = 'r' AND n.nspname IN ('public', 'web', 'mko')
 ORDER BY 1, 2;

\echo
\echo ===== 3. primary key ของทุกตาราง =====
SELECT n.nspname || '.' || c.relname AS "ตาราง",
       coalesce(string_agg(a.attname, ', ' ORDER BY k.ord), '(ไม่มี PK)') AS "primary key"
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
  LEFT JOIN pg_constraint con ON con.conrelid = c.oid AND con.contype = 'p'
  LEFT JOIN unnest(con.conkey) WITH ORDINALITY AS k(attnum, ord) ON true
  LEFT JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = k.attnum
 WHERE c.relkind = 'r' AND n.nspname IN ('public', 'web', 'mko')
 GROUP BY 1 ORDER BY 1;

\echo
\echo ===== 4. foreign key ทั้งหมด พร้อมบอกว่าคอลัมน์ null ได้ไหม =====
\echo (ใช้กำหนดทิศทางและ cardinality ใน ERD)
SELECT tn.nspname || '.' || tc.relname       AS "ตารางลูก",
       a.attname                              AS "คอลัมน์",
       CASE WHEN a.attnotnull THEN 'NOT NULL' ELSE 'null ได้' END AS "ค่าว่าง",
       fn.nspname || '.' || fc.relname        AS "ตารางแม่",
       CASE con.confdeltype WHEN 'c' THEN 'CASCADE' WHEN 'n' THEN 'SET NULL'
            WHEN 'a' THEN 'NO ACTION' WHEN 'r' THEN 'RESTRICT'
            ELSE con.confdeltype::text END    AS "on delete"
  FROM pg_constraint con
  JOIN pg_class tc     ON tc.oid = con.conrelid
  JOIN pg_namespace tn ON tn.oid = tc.relnamespace
  JOIN pg_class fc     ON fc.oid = con.confrelid
  JOIN pg_namespace fn ON fn.oid = fc.relnamespace
  JOIN unnest(con.conkey) WITH ORDINALITY AS k(attnum, ord) ON true
  JOIN pg_attribute a  ON a.attrelid = con.conrelid AND a.attnum = k.attnum
 WHERE con.contype = 'f' AND tn.nspname IN ('public', 'web', 'mko')
 ORDER BY 1, 2;

\echo
\echo ===== 5. บทบาทที่แอปใช้ และเขียนตารางไหนได้บ้าง =====
SELECT n.nspname || '.' || c.relname AS "เขียนได้ที่"
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE c.relkind = 'r' AND n.nspname IN ('public', 'web', 'mko')
   AND (has_table_privilege('advisor_api', c.oid, 'INSERT')
     OR has_table_privilege('advisor_api', c.oid, 'UPDATE')
     OR has_table_privilege('advisor_api', c.oid, 'DELETE'))
 ORDER BY 1;

\echo
\echo ===== 6. คลังเวกเตอร์ของระบบถาม-ตอบ =====
SELECT a.attname AS "คอลัมน์", format_type(a.atttypid, a.atttypmod) AS "ชนิด"
  FROM pg_attribute a
 WHERE a.attrelid = 'public.course_chunks'::regclass AND a.attnum > 0 AND NOT a.attisdropped
 ORDER BY a.attnum;
SELECT indexname AS "ดัชนี", indexdef AS "นิยาม"
  FROM pg_indexes WHERE schemaname = 'public' AND tablename = 'course_chunks';

\echo
\echo ===== 7. วิวที่ระบบถาม-ตอบอ่านจริง =====
SELECT table_name AS "วิวใน schema mko"
  FROM information_schema.views WHERE table_schema = 'mko' ORDER BY 1;
