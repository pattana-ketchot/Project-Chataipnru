-- ชุด GRAD_PROGRAMS — หลักสูตรโท-เอก · วุฒิที่รับสมัคร · ลิงก์สมัครเรียน
--
-- ต้นทางข้อมูล  https://sci.pnru.ac.th/programs.php  (ตรวจ 27 ต.ค. 2569)
-- ขอบเขต        เพิ่ม 2 แถว + รวมคีย์ใหม่เข้ากับ 12 แถวเดิม
-- ไม่แตะ        about / faculty / documents / logo / careers / highlights ของเดิม
--               และไม่ทับค่า level ที่ผู้ดูแลกรอกไว้แล้ว
--
-- รันทั้งไฟล์ใน transaction เดียว ถ้าด่านตรวจท้ายไฟล์ไม่ผ่าน จะ rollback ทั้งหมด
\set ON_ERROR_STOP on
begin;

create temporary table _before on commit drop as
select id, title, detail from web.site_courses;

\echo '--- ก่อนแก้ ---'
select count(*) as rows_before, count(detail->>'level') as with_level
  from web.site_courses;

\echo '--- เพิ่มหลักสูตรบัณฑิตศึกษา ---'

with added as (
  insert into web.site_courses
         (title, title_en, description, careers, detail, is_published)
  values ($th$(ปริญญาโท) การจัดการเทคโนโลยีการเกษตรและบริหารทรัพยากรชุมชน$th$,
          $th$Master of Science Program in Agricultural Technology Management and Community Resource Administration$th$,
          $th$หลักสูตรระดับบัณฑิตศึกษาที่มุ่งผลิตมหาบัณฑิตที่มีความรู้ ความสามารถ และทักษะขั้นสูงด้านการจัดการเทคโนโลยีการเกษตร การบริหารจัดการทรัพยากรชุมชน และการวิจัยเชิงประยุกต์$th$,
          array[$th$นักวิชาการเกษตร$th$, $th$นักวิชาชีพทางการเกษตร$th$, $th$นักจัดการเทคโนโลยีการเกษตร$th$, $th$นักวางแผนและพัฒนาชุมชน$th$, $th$เจ้าหน้าที่ส่งเสริมการเกษตร$th$, $th$ผู้ประกอบการด้านการเกษตรและธุรกิจเกษตร$th$, $th$นักวิจัย$th$, $th$อาจารย์ในสถาบันการศึกษา$th$, $th$นักวิชาการหรือบุคลากรในหน่วยงานภาครัฐและเอกชนที่เกี่ยวข้องกับการเกษตรและการพัฒนาชุมชน$th$]::text[],
          cast($th${"level": "ปริญญาโท", "duration": "2 ปี (แผน 1 แบบวิชาการ)", "tuition_per_semester": "ภาคพิเศษ (เสาร์-อาทิตย์) 24,000 บาทต่อภาคการศึกษา", "about": "หลักสูตรวิทยาศาสตรมหาบัณฑิต สาขาวิชาการจัดการเทคโนโลยีการเกษตรและบริหารทรัพยากรชุมชน เป็นหลักสูตรระดับบัณฑิตศึกษาที่มุ่งผลิตมหาบัณฑิตที่มีความรู้ ความสามารถ และทักษะขั้นสูงด้านการจัดการเทคโนโลยีการเกษตร การบริหารจัดการทรัพยากรชุมชน และการวิจัยเชิงประยุกต์ สามารถวิเคราะห์ วางแผน และพัฒนานวัตกรรมเพื่อแก้ไขปัญหาและยกระดับคุณภาพชีวิตของชุมชนและสังคมได้อย่างมีประสิทธิภาพ", "qualifications": ["ผู้สมัครต้องสำเร็จการศึกษาระดับปริญญาตรีหรือเทียบเท่าจากสถาบันการศึกษาที่ได้รับการรับรองจากกระทรวงการอุดมศึกษา วิทยาศาสตร์ วิจัยและนวัตกรรม หรือเป็นไปตามข้อบังคับมหาวิทยาลัยราชภัฏพระนครว่าด้วยการศึกษาระดับบัณฑิตศึกษา และเงื่อนไขที่หลักสูตรกำหนด"], "qualifications_note": "ข้อความข้างต้นเป็นข้อมูลสรุปจากหน้าหลักสูตรของคณะ เงื่อนไขฉบับเต็มซึ่งแยกตามแผนการเรียนอยู่ในเล่ม มคอ.2", "full_conditions_url": "https://sci.pnru.ac.th/uploads/programs/9cca29c04de025965ba82bf72700bfb5.pdf", "source_url": "https://sci.pnru.ac.th/program_detail.php?id=26", "source_checked_at": "27 ต.ค. 2569", "documents": [{"name": "เล่มหลักสูตร มคอ.2 (เงื่อนไขการรับสมัครฉบับเต็ม)", "type": "PDF", "url": "https://sci.pnru.ac.th/uploads/programs/9cca29c04de025965ba82bf72700bfb5.pdf"}]}$th$ as jsonb),
          true)
  returning id
)
select id, 'inserted' as action, '' as added_keys from added;

with added as (
  insert into web.site_courses
         (title, title_en, description, careers, detail, is_published)
  values ($th$(ปริญญาเอก) การจัดการเทคโนโลยีการเกษตรและบริหารทรัพยากรชุมชน$th$,
          $th$Doctor of Philosophy Program in Agricultural Technology Management and Community Resource Administration$th$,
          $th$หลักสูตรที่พัฒนาขึ้นเพื่อสร้างนักวิจัยและผู้เชี่ยวชาญระดับสูงที่มีความสามารถในการบูรณาการองค์ความรู้ด้านวิทยาศาสตร์การเกษตร เทคโนโลยี นวัตกรรม การจัดการทรัพยากร และการพัฒนาชุมชน$th$,
          array[$th$นักวิจัยด้านการจัดการเทคโนโลยีการเกษตรและบริหารทรัพยากรชุมชน$th$, $th$นักวิชาการเกษตร$th$, $th$นักวิชาการโรคพืช$th$, $th$นักกีฏวิทยา$th$, $th$นักวิชาการส่งเสริมการเกษตร$th$, $th$นักวิชาการสหกรณ์$th$, $th$นักวิชาการประมง$th$, $th$นักวางแผนและบริหารโครงการ$th$, $th$นักบริหารงานการเกษตรสมัยใหม่$th$, $th$ผู้เชี่ยวชาญด้านนวัตกรรมการเกษตร$th$, $th$อาจารย์และนักวิชาการในสถาบันอุดมศึกษา$th$, $th$ผู้บริหารหน่วยงานภาครัฐและเอกชนด้านเกษตรและชุมชน$th$]::text[],
          cast($th${"level": "ปริญญาเอก", "duration": "3 ปี แผน 1.1 และแผน 2.1", "about": "หลักสูตรปรัชญาดุษฎีบัณฑิต สาขาวิชาการจัดการเทคโนโลยีการเกษตรและบริหารทรัพยากรชุมชน เป็นหลักสูตรที่พัฒนาขึ้นเพื่อสร้างนักวิจัยและผู้เชี่ยวชาญระดับสูงที่มีความสามารถในการบูรณาการองค์ความรู้ด้านวิทยาศาสตร์การเกษตร เทคโนโลยี นวัตกรรม การจัดการทรัพยากร และการพัฒนาชุมชน เพื่อตอบสนองต่อการเปลี่ยนแปลงของภาคเกษตรและสังคมโลก", "qualifications": ["สำเร็จการศึกษาระดับปริญญาโทหรือเทียบเท่าจากสถาบันการศึกษาที่ได้รับการรับรอง", "มีคุณสมบัติตามข้อบังคับมหาวิทยาลัยราชภัฏพระนครว่าด้วยการศึกษาระดับบัณฑิตศึกษา", "ผ่านเกณฑ์การคัดเลือกและเงื่อนไขที่หลักสูตรกำหนด"], "qualifications_note": "ข้อความข้างต้นเป็นข้อมูลสรุปจากหน้าหลักสูตรของคณะ เงื่อนไขฉบับเต็มซึ่งแยกตามแผนการเรียนอยู่ในเล่ม มคอ.2", "full_conditions_url": "https://sci.pnru.ac.th/uploads/programs/24d048df23fb5ffcb042453161c9e5c8.pdf", "source_url": "https://sci.pnru.ac.th/program_detail.php?id=27", "source_checked_at": "27 ต.ค. 2569", "documents": [{"name": "เล่มหลักสูตร มคอ.2 (เงื่อนไขการรับสมัครฉบับเต็ม)", "type": "PDF", "url": "https://sci.pnru.ac.th/uploads/programs/24d048df23fb5ffcb042453161c9e5c8.pdf"}]}$th$ as jsonb),
          true)
  returning id
)
select id, 'inserted' as action, '' as added_keys from added;

\echo '--- เติมข้อมูลหลักสูตรปริญญาตรี ---'

-- คณิตศาสตร์
with before as (
  select id, coalesce(detail, '{}'::jsonb) as d
    from web.site_courses where title = $th$คณิตศาสตร์$th$
), upd as (
  update web.site_courses c
     set detail = coalesce(c.detail, '{}'::jsonb)
                || cast($th${"qualifications": ["ม.6 หรือเทียบเท่าทุกแผนการเรียน"], "admission_conditions": ["ใช้เกรดเฉลี่ยสะสม/หน่วยกิตสะสม อย่างน้อย 4 - 5 ภาคการศึกษา ในการสมัครเรียน"], "source_url": "https://sci.pnru.ac.th/program_detail.php?id=2", "source_checked_at": "27 ต.ค. 2569"}$th$ as jsonb)
                || case when coalesce(c.detail->>'level', '') = ''
                        then jsonb_build_object('level', $th$ปริญญาตรี$th$)
                        else '{}'::jsonb end
    from before b
   where c.id = b.id
  returning c.id, b.d as old_detail
)
select id, 'updated' as action,
       coalesce((select string_agg(k, ',' order by k)
                   from unnest(array[$th$qualifications$th$, $th$admission_conditions$th$, $th$source_url$th$, $th$source_checked_at$th$, $th$level$th$]::text[]) k
                  where not (old_detail ? k)), '') as added_keys
  from upd;

-- เทคโนโลยีสารสนเทศ
with before as (
  select id, coalesce(detail, '{}'::jsonb) as d
    from web.site_courses where title = $th$เทคโนโลยีสารสนเทศ$th$
), upd as (
  update web.site_courses c
     set detail = coalesce(c.detail, '{}'::jsonb)
                || cast($th${"qualifications": ["ม.6 หรือเทียบเท่าทุกแผน การเรียนและเกรดเฉลี่ยสะสม 2.00 ขึ้นไป"], "admission_conditions": ["ใช้เกรดเฉลี่ยสะสม/หน่วยกิตสะสม อย่างน้อย 4-5 ภาคการศึกษา ในการสมัครเรียน"], "source_url": "https://sci.pnru.ac.th/program_detail.php?id=8", "source_checked_at": "27 ต.ค. 2569"}$th$ as jsonb)
                || case when coalesce(c.detail->>'level', '') = ''
                        then jsonb_build_object('level', $th$ปริญญาตรี$th$)
                        else '{}'::jsonb end
    from before b
   where c.id = b.id
  returning c.id, b.d as old_detail
)
select id, 'updated' as action,
       coalesce((select string_agg(k, ',' order by k)
                   from unnest(array[$th$qualifications$th$, $th$admission_conditions$th$, $th$source_url$th$, $th$source_checked_at$th$, $th$level$th$]::text[]) k
                  where not (old_detail ? k)), '') as added_keys
  from upd;

-- วิทยาการคอมพิวเตอร์
with before as (
  select id, coalesce(detail, '{}'::jsonb) as d
    from web.site_courses where title = $th$วิทยาการคอมพิวเตอร์$th$
), upd as (
  update web.site_courses c
     set detail = coalesce(c.detail, '{}'::jsonb)
                || cast($th${"qualifications": ["ม.6 หรือเทียบเท่าทุกแผนการเรียน เกรดเฉลี่ยสะสม 2.00 ขึ้นไป"], "source_url": "https://sci.pnru.ac.th/program_detail.php?id=10", "source_checked_at": "27 ต.ค. 2569"}$th$ as jsonb)
                || case when coalesce(c.detail->>'level', '') = ''
                        then jsonb_build_object('level', $th$ปริญญาตรี$th$)
                        else '{}'::jsonb end
    from before b
   where c.id = b.id
  returning c.id, b.d as old_detail
)
select id, 'updated' as action,
       coalesce((select string_agg(k, ',' order by k)
                   from unnest(array[$th$qualifications$th$, $th$admission_conditions$th$, $th$source_url$th$, $th$source_checked_at$th$, $th$level$th$]::text[]) k
                  where not (old_detail ? k)), '') as added_keys
  from upd;

-- สาขาวิชาเทคโนโลยีอาหารและความเป็นผู้ประกอบการสมัยใหม่
with before as (
  select id, coalesce(detail, '{}'::jsonb) as d
    from web.site_courses where title = $th$สาขาวิชาเทคโนโลยีอาหารและความเป็นผู้ประกอบการสมัยใหม่$th$
), upd as (
  update web.site_courses c
     set detail = coalesce(c.detail, '{}'::jsonb)
                || cast($th${"qualifications": ["ม.6 หรือเทียบเท่า ทุกแผนการเรียน"], "admission_conditions": ["ใช้เกรดเฉลี่ยสะสม/หน่วยกิตสะสม อย่างน้อย 5-6 ภาคการศึกษา ในการสมัครเรียน"], "source_url": "https://sci.pnru.ac.th/program_detail.php?id=11", "source_checked_at": "27 ต.ค. 2569"}$th$ as jsonb)
                || case when coalesce(c.detail->>'level', '') = ''
                        then jsonb_build_object('level', $th$ปริญญาตรี$th$)
                        else '{}'::jsonb end
    from before b
   where c.id = b.id
  returning c.id, b.d as old_detail
)
select id, 'updated' as action,
       coalesce((select string_agg(k, ',' order by k)
                   from unnest(array[$th$qualifications$th$, $th$admission_conditions$th$, $th$source_url$th$, $th$source_checked_at$th$, $th$level$th$]::text[]) k
                  where not (old_detail ? k)), '') as added_keys
  from upd;

-- การจัดการสิ่งแวดล้อมและทรัพยากรธรรมชาติ
with before as (
  select id, coalesce(detail, '{}'::jsonb) as d
    from web.site_courses where title = $th$การจัดการสิ่งแวดล้อมและทรัพยากรธรรมชาติ$th$
), upd as (
  update web.site_courses c
     set detail = coalesce(c.detail, '{}'::jsonb)
                || cast($th${"qualifications": ["ม.6 หรือเทียบเท่าทุกแผนการเรียน"], "admission_conditions": ["ใช้เกรดเฉลี่ยสะสม/หน่วยกิตสะสม อย่างน้อย 5-6 ภาคการศึกษา ในการสมัครเรียน"], "source_url": "https://sci.pnru.ac.th/program_detail.php?id=12", "source_checked_at": "27 ต.ค. 2569"}$th$ as jsonb)
                || case when coalesce(c.detail->>'level', '') = ''
                        then jsonb_build_object('level', $th$ปริญญาตรี$th$)
                        else '{}'::jsonb end
    from before b
   where c.id = b.id
  returning c.id, b.d as old_detail
)
select id, 'updated' as action,
       coalesce((select string_agg(k, ',' order by k)
                   from unnest(array[$th$qualifications$th$, $th$admission_conditions$th$, $th$source_url$th$, $th$source_checked_at$th$, $th$level$th$]::text[]) k
                  where not (old_detail ? k)), '') as added_keys
  from upd;

-- วิทยาศาสตร์เครื่องสำอาง
with before as (
  select id, coalesce(detail, '{}'::jsonb) as d
    from web.site_courses where title = $th$วิทยาศาสตร์เครื่องสำอาง$th$
), upd as (
  update web.site_courses c
     set detail = coalesce(c.detail, '{}'::jsonb)
                || cast($th${"qualifications": ["ม.6 แผนการเรียนวิทย์ - คณิต ,ศิลป์ - คำนวณ"], "admission_conditions": ["ใช้เกรดเฉลี่ยสะสม/หน่วยกิตสะสม อย่างน้อย 4-5 ภาคการศึกษา ในการสมัครเรียน"], "source_url": "https://sci.pnru.ac.th/program_detail.php?id=14", "source_checked_at": "27 ต.ค. 2569"}$th$ as jsonb)
                || case when coalesce(c.detail->>'level', '') = ''
                        then jsonb_build_object('level', $th$ปริญญาตรี$th$)
                        else '{}'::jsonb end
    from before b
   where c.id = b.id
  returning c.id, b.d as old_detail
)
select id, 'updated' as action,
       coalesce((select string_agg(k, ',' order by k)
                   from unnest(array[$th$qualifications$th$, $th$admission_conditions$th$, $th$source_url$th$, $th$source_checked_at$th$, $th$level$th$]::text[]) k
                  where not (old_detail ? k)), '') as added_keys
  from upd;

-- คอมพิวเตอร์แอนิเมชันและมัลติมีเดีย
with before as (
  select id, coalesce(detail, '{}'::jsonb) as d
    from web.site_courses where title = $th$คอมพิวเตอร์แอนิเมชันและมัลติมีเดีย$th$
), upd as (
  update web.site_courses c
     set detail = coalesce(c.detail, '{}'::jsonb)
                || cast($th${"qualifications": ["เป็นผู้สำเร็จการศึกษาระดับมัธยมศึกษาตอนปลายหรือเทียบเท่า ตามหลักสูตรของกระทรวงศึกษาธิการหรือเทียบเท่า หรือเป็นไปตามข้อบังคับ ระเบียบ และประกาศของมหาวิทยาลัยราชภัฏพระนคร"], "source_url": "https://sci.pnru.ac.th/program_detail.php?id=15", "source_checked_at": "27 ต.ค. 2569"}$th$ as jsonb)
                || case when coalesce(c.detail->>'level', '') = ''
                        then jsonb_build_object('level', $th$ปริญญาตรี$th$)
                        else '{}'::jsonb end
    from before b
   where c.id = b.id
  returning c.id, b.d as old_detail
)
select id, 'updated' as action,
       coalesce((select string_agg(k, ',' order by k)
                   from unnest(array[$th$qualifications$th$, $th$admission_conditions$th$, $th$source_url$th$, $th$source_checked_at$th$, $th$level$th$]::text[]) k
                  where not (old_detail ? k)), '') as added_keys
  from upd;

-- การแพทย์แผนไทยประยุกต์
with before as (
  select id, coalesce(detail, '{}'::jsonb) as d
    from web.site_courses where title = $th$การแพทย์แผนไทยประยุกต์$th$
), upd as (
  update web.site_courses c
     set detail = coalesce(c.detail, '{}'::jsonb)
                || cast($th${"qualifications": ["มัธยมศึกษาตอนปลายแผนการเรียนวิทยาศาสตร์-คณิตศาสตร์เกรดเฉลี่ยไม่น้อยกว่า 2.50"], "admission_conditions": ["ใช้เกรดเฉลี่ยสะสม/หน่วยกิตสะสม อย่างน้อย 4-5 ภาคการศึกษา ในการสมัครเรียน"], "source_url": "https://sci.pnru.ac.th/program_detail.php?id=17", "source_checked_at": "27 ต.ค. 2569"}$th$ as jsonb)
                || case when coalesce(c.detail->>'level', '') = ''
                        then jsonb_build_object('level', $th$ปริญญาตรี$th$)
                        else '{}'::jsonb end
    from before b
   where c.id = b.id
  returning c.id, b.d as old_detail
)
select id, 'updated' as action,
       coalesce((select string_agg(k, ',' order by k)
                   from unnest(array[$th$qualifications$th$, $th$admission_conditions$th$, $th$source_url$th$, $th$source_checked_at$th$, $th$level$th$]::text[]) k
                  where not (old_detail ? k)), '') as added_keys
  from upd;

-- เทคโนโลยีการเกษตรสมัยใหม่
with before as (
  select id, coalesce(detail, '{}'::jsonb) as d
    from web.site_courses where title = $th$เทคโนโลยีการเกษตรสมัยใหม่$th$
), upd as (
  update web.site_courses c
     set detail = coalesce(c.detail, '{}'::jsonb)
                || cast($th${"qualifications": ["ม.6 หรือเทียบเท่าทุกแผนการเรียน"], "admission_conditions": ["ใช้เกรดเฉลี่ยสะสม/หน่วยกิตสะสม อย่างน้อย 4-5 ภาคการศึกษา ในการสมัครเรียน"], "source_url": "https://sci.pnru.ac.th/program_detail.php?id=19", "source_checked_at": "27 ต.ค. 2569"}$th$ as jsonb)
                || case when coalesce(c.detail->>'level', '') = ''
                        then jsonb_build_object('level', $th$ปริญญาตรี$th$)
                        else '{}'::jsonb end
    from before b
   where c.id = b.id
  returning c.id, b.d as old_detail
)
select id, 'updated' as action,
       coalesce((select string_agg(k, ',' order by k)
                   from unnest(array[$th$qualifications$th$, $th$admission_conditions$th$, $th$source_url$th$, $th$source_checked_at$th$, $th$level$th$]::text[]) k
                  where not (old_detail ? k)), '') as added_keys
  from upd;

-- เทคโนโลยีผลิตภัณฑ์ชีวภาพกับการประกอบธุรกิจ
with before as (
  select id, coalesce(detail, '{}'::jsonb) as d
    from web.site_courses where title = $th$เทคโนโลยีผลิตภัณฑ์ชีวภาพกับการประกอบธุรกิจ$th$
), upd as (
  update web.site_courses c
     set detail = coalesce(c.detail, '{}'::jsonb)
                || cast($th${"qualifications": ["ม.6 หรือเทียบเท่า (ทุกแผนการเรียน) และ กศน. เกรดเฉลี่ยขั้นต่ำ 2.50"], "admission_conditions": ["ใช้เกรดเฉลี่ยสะสม/หน่วยกิตสะสม อย่างน้อย 5-6 ภาคการศึกษา ในการสมัครเรียน"], "source_url": "https://sci.pnru.ac.th/program_detail.php?id=23", "source_checked_at": "27 ต.ค. 2569"}$th$ as jsonb)
                || case when coalesce(c.detail->>'level', '') = ''
                        then jsonb_build_object('level', $th$ปริญญาตรี$th$)
                        else '{}'::jsonb end
    from before b
   where c.id = b.id
  returning c.id, b.d as old_detail
)
select id, 'updated' as action,
       coalesce((select string_agg(k, ',' order by k)
                   from unnest(array[$th$qualifications$th$, $th$admission_conditions$th$, $th$source_url$th$, $th$source_checked_at$th$, $th$level$th$]::text[]) k
                  where not (old_detail ? k)), '') as added_keys
  from upd;

-- สาขาวิชาการประกอบอาหารและการบริการอาหาร
with before as (
  select id, coalesce(detail, '{}'::jsonb) as d
    from web.site_courses where title = $th$สาขาวิชาการประกอบอาหารและการบริการอาหาร$th$
), upd as (
  update web.site_courses c
     set detail = coalesce(c.detail, '{}'::jsonb)
                || cast($th${"qualifications": ["สำเร็จการศึกษาระดับมัธยมศึกษาตอนปลาย หรือเทียบเท่า ทุกแผนการเรียน โดยมีคะแนนเฉลี่ยสะสมไม่ต่ำกว่า 2.00", "ผู้สำเร็จการศึกษาระดับประกาศนียบัตรวิชาชีพชั้นสูง อนุปริญญา หรือปริญญาตรี สามารถสมัครเข้าศึกษาโดยการเทียบโอนได้ ตามระเบียบของมหาวิทยาลัย", "ผู้สมัครต้องมีคุณสมบัติครบถ้วนตามเกณฑ์การรับสมัครและเงื่อนไขที่มหาวิทยาลัยราชภัฏพระนครกำหนด"], "source_url": "https://sci.pnru.ac.th/program_detail.php?id=24", "source_checked_at": "27 ต.ค. 2569"}$th$ as jsonb)
                || case when coalesce(c.detail->>'level', '') = ''
                        then jsonb_build_object('level', $th$ปริญญาตรี$th$)
                        else '{}'::jsonb end
    from before b
   where c.id = b.id
  returning c.id, b.d as old_detail
)
select id, 'updated' as action,
       coalesce((select string_agg(k, ',' order by k)
                   from unnest(array[$th$qualifications$th$, $th$admission_conditions$th$, $th$source_url$th$, $th$source_checked_at$th$, $th$level$th$]::text[]) k
                  where not (old_detail ? k)), '') as added_keys
  from upd;

-- สาขาวิชาสาธารณสุขศาสตร์
with before as (
  select id, coalesce(detail, '{}'::jsonb) as d
    from web.site_courses where title = $th$สาขาวิชาสาธารณสุขศาสตร์$th$
), upd as (
  update web.site_courses c
     set detail = coalesce(c.detail, '{}'::jsonb)
                || cast($th${"qualifications": ["เป็นผู้สำเร็จการศึกษาระดับมัธยมศึกษาตอนปลายหรือเทียบเท่าตามหลักสูตรของกระทรวงศึกษาธิการ หรือเป็นไปตามข้อบังคับ ระเบียบ และประกาศของมหาวิทยาลัยราชภัฏพระนคร"], "source_url": "https://sci.pnru.ac.th/program_detail.php?id=25", "source_checked_at": "27 ต.ค. 2569"}$th$ as jsonb)
                || case when coalesce(c.detail->>'level', '') = ''
                        then jsonb_build_object('level', $th$ปริญญาตรี$th$)
                        else '{}'::jsonb end
    from before b
   where c.id = b.id
  returning c.id, b.d as old_detail
)
select id, 'updated' as action,
       coalesce((select string_agg(k, ',' order by k)
                   from unnest(array[$th$qualifications$th$, $th$admission_conditions$th$, $th$source_url$th$, $th$source_checked_at$th$, $th$level$th$]::text[]) k
                  where not (old_detail ? k)), '') as added_keys
  from upd;


\echo '--- หลังแก้ ---'
select coalesce(detail->>'level', '(ว่าง)') as lvl, count(*) as n
  from web.site_courses group by coalesce(detail->>'level', '(ว่าง)') order by 1;

\echo '--- แถวเดิมที่คีย์นอกเหนือจากที่ release นี้เพิ่ม เปลี่ยนไป (ต้องว่าง) ---'
select b.title
  from _before b join web.site_courses a on a.id = b.id
 where (a.detail - array[$th$qualifications$th$, $th$admission_conditions$th$, $th$source_url$th$, $th$source_checked_at$th$, $th$level$th$]::text[])
       is distinct from (coalesce(b.detail, '{}'::jsonb) - array[$th$qualifications$th$, $th$admission_conditions$th$, $th$source_url$th$, $th$source_checked_at$th$, $th$level$th$]::text[]);

do $chk$
declare
  n_all int; n_ba int; n_ma int; n_phd int; n_qual int; n_cond int; n_touched int;
begin
  select count(*) into n_all from web.site_courses;
  select count(*) into n_ba  from web.site_courses where detail->>'level' = $th$ปริญญาตรี$th$;
  select count(*) into n_ma  from web.site_courses where detail->>'level' = $th$ปริญญาโท$th$;
  select count(*) into n_phd from web.site_courses where detail->>'level' = $th$ปริญญาเอก$th$;
  select count(*) into n_qual from web.site_courses where detail ? 'qualifications';
  select count(*) into n_cond from web.site_courses where detail ? 'admission_conditions';
  select count(*) into n_touched
    from _before b join web.site_courses a on a.id = b.id
   where (a.detail - array[$th$qualifications$th$, $th$admission_conditions$th$, $th$source_url$th$, $th$source_checked_at$th$, $th$level$th$]::text[])
         is distinct from (coalesce(b.detail, '{}'::jsonb) - array[$th$qualifications$th$, $th$admission_conditions$th$, $th$source_url$th$, $th$source_checked_at$th$, $th$level$th$]::text[]);

  if n_all  <> 14 then raise exception 'rows %, want 14', n_all; end if;
  if n_ba   <> 12 then raise exception 'bachelor %, want 12', n_ba; end if;
  if n_ma   <> 1  then raise exception 'master %, want 1', n_ma; end if;
  if n_phd  <> 1  then raise exception 'doctoral %, want 1', n_phd; end if;
  if n_qual <> 14 then raise exception 'qualifications %, want 14', n_qual; end if;
  if n_cond <> 8  then raise exception 'admission_conditions %, want 8', n_cond; end if;
  if n_touched <> 0 then raise exception 'other keys changed on % rows', n_touched; end if;
  raise notice 'passed all 7 checks';
end
$chk$;

commit;