-- =====================================================================
-- C2 — เปลี่ยน cron job ให้ส่ง secret เฉพาะงานตั้งเวลา
--
-- ‼ ยังไม่รันบน production — ไฟล์นี้ไว้ตรวจทานก่อน
--
-- หลักการ
--   · ค่า secret อ่านจาก Vault ตอนรัน **ไม่เคยปรากฏในไฟล์นี้หรือใน log**
--   · **ไม่บันทึก headers ลงที่ใดเลย** เพราะมี apikey และ x-cron-secret อยู่
--   · ตรวจเงื่อนไขให้ครบก่อน แล้วจึงเปลี่ยน
--   · ปิด job เดิมและสร้าง job ใหม่อยู่ใน transaction เดียว — ล้มแล้วย้อนทั้งหมด
--   · job เดิมถูกปิด ไม่ได้ถูกลบ เพื่อให้ย้อนกลับได้
--
-- ─────────────────────────────────────────────────────────────────────
-- ผลทดสอบที่นำมาปรับสคริปต์นี้
-- ─────────────────────────────────────────────────────────────────────
--   · การทดสอบ pg_net **แบบเรียกครั้งเดียวด้วยมือ** ด้วย
--     timeout_milliseconds = 30000 ได้ request_id = 7 · status_code = 200
--     · timed_out = false · error_msg = null
--   · ค่า timeout เดิมของ job คือ 5000 ms
--
--   ‼ **ค่า 30000 ms ยังไม่เคยผ่าน scheduler จริง** — ยืนยันมาจากการเรียก
--     ครั้งเดียวด้วยมือเท่านั้น · ต้องทดสอบผ่าน scheduler ในโปรเจกต์ทดสอบก่อน
-- =====================================================================

-- ─────────────────────────────────────────────────────────────────────
-- ขั้น 0 — ตรวจก่อน (อ่านอย่างเดียว ไม่แสดงค่า secret)
-- ─────────────────────────────────────────────────────────────────────

-- 0.1 job ปัจจุบัน · ดูเฉพาะ metadata ไม่ดู command เพราะมีคีย์อยู่ข้างใน
select jobid, jobname, schedule, active, database, username,
       length(command) as command_len
from cron.job
where jobname like '%sync-sci-news%'
order by jobname;

-- 0.2 secret ที่ต้องใช้ — ตรวจว่ามีครบไหม **ไม่ดึงค่า**
select name, (decrypted_secret is not null and length(decrypted_secret) > 0) as usable
from vault.decrypted_secrets
where name in ('project_url', 'anon_key', 'sync_cron_secret')
order by name;
-- ต้องเห็นครบ 3 แถว usable = true ทุกแถว · ถ้ายังไม่มี sync_cron_secret ทำขั้น 1

-- 0.3 ส่วนขยายที่ต้องมี
select extname, extversion
from pg_extension
where extname in ('pg_cron', 'pg_net', 'supabase_vault')
order by extname;
-- จดเวอร์ชัน pg_net ไว้ · ใช้หาชื่อตารางผลตอบกลับในขั้น 5

-- 0.4 ชื่อตารางผลตอบกลับของ pg_net — **อย่าเดา**
select table_name
from information_schema.tables
where table_schema = 'net'
order by table_name;
-- ชื่อที่พบบ่อยคือ _http_response · ถ้าไม่ตรงให้แก้ขั้น 5 ตามของจริง

-- ─────────────────────────────────────────────────────────────────────
-- ขั้น 1 — สร้าง secret ใน Vault (ทำครั้งเดียว ถ้ายังไม่มี)
-- ─────────────────────────────────────────────────────────────────────
--
-- ‼ อย่าพิมพ์ค่าลงในไฟล์นี้ · รันในหน้า SQL Editor แล้วล้างออกจากประวัติ
--   ค่าต้องเป็นค่าเดียวกับ Edge Function secret ชื่อ SYNC_CRON_SECRET
--
-- สร้างค่าในเครื่องตัวเอง (ไม่ใช่ในฐานข้อมูล):   openssl rand -hex 32
--
--   select vault.create_secret('<ค่าที่สุ่มได้>', 'sync_cron_secret',
--                              'secret สำหรับ cron เรียก Edge Function sync-sci-news');
--
-- แล้วตรวจด้วยคำสั่ง 0.2 (ดูแค่ usable)

-- ─────────────────────────────────────────────────────────────────────
-- ขั้น 2 — ตารางบันทึก request_id เพื่อจับคู่ผลตอบกลับ
-- ─────────────────────────────────────────────────────────────────────
--
-- เก็บเฉพาะ request_id และเวลา **ไม่เก็บ headers ไม่เก็บ body ไม่เก็บ secret**
-- จำเป็นเพราะ net.http_post คืน request_id แล้วจบ · ถ้าไม่เก็บไว้จะจับคู่
-- ผลตอบกลับได้แค่โดยประมาณจากช่วงเวลา

begin;

create table if not exists public.c2_sync_runs (
  request_id bigint primary key,
  queued_at  timestamptz not null default now()
);

comment on table public.c2_sync_runs is
  'request_id ของ net.http_post ที่ cron ยิงไป sync-sci-news · ไม่เก็บ headers หรือ secret';

-- ปิดไม่ให้ผู้ใช้เว็บเข้าถึง — เป็นตารางสำหรับงานระบบเท่านั้น
alter table public.c2_sync_runs enable row level security;
revoke all on table public.c2_sync_runs from anon, authenticated;
-- ไม่สร้าง policy ใด ๆ -> anon และ authenticated อ่านไม่ได้แม้จะมี grant หลงเหลือ

commit;

-- ─────────────────────────────────────────────────────────────────────
-- ขั้น 3 — เปลี่ยน job แบบ all-or-nothing
-- ─────────────────────────────────────────────────────────────────────

begin;

do $$
declare
  v_old_id   bigint;
  v_missing  text;
  v_new_cnt  int;
begin
  -- ตรวจ 1: job เดิมต้องมีอยู่และยังเปิดอยู่
  select jobid into v_old_id
  from cron.job
  where jobname = 'sync-sci-news-every-30-min';

  if v_old_id is null then
    raise exception 'ไม่พบ job เดิมชื่อ sync-sci-news-every-30-min — หยุดก่อน%s',
      case when exists (select 1 from cron.job where jobname = 'c2-sync-sci-news-test')
        then E'
  พบ c2-sync-sci-news-test แปลว่าน่าจะกำลังอยู่บนโปรเจกต์ทดสอบ'
             || E'
  ‼ ไฟล์นี้สำหรับ production เท่านั้น — ใช้ 03_test_rollback_on_test_project.sql แทน'
        else E'
  ตรวจชื่อ job จากขั้น 0.1 อีกครั้ง' end;
  end if;

  if not (select active from cron.job where jobid = v_old_id) then
    raise exception 'job เดิมถูกปิดอยู่แล้ว — อาจมีคนเปลี่ยนไปก่อนหน้านี้ หยุดก่อนเพื่อตรวจสถานะ';
  end if;

  -- ตรวจ 2: secret ครบทั้งสาม
  select string_agg(needed, ', ')
    into v_missing
  from unnest(array['project_url', 'anon_key', 'sync_cron_secret']) as needed
  where not exists (
    select 1 from vault.decrypted_secrets v
    where v.name = needed
      and v.decrypted_secret is not null
      and length(v.decrypted_secret) > 0
  );

  if v_missing is not null then
    raise exception 'secret ใน Vault ไม่ครบ: % — สร้างให้ครบก่อน (ขั้น 1)', v_missing;
  end if;

  -- ตรวจ 3: ต้องยังไม่มี job ใหม่ชื่อนี้
  select count(*) into v_new_cnt
  from cron.job
  where jobname = 'sync-sci-news-every-30-min-v2';

  if v_new_cnt > 0 then
    raise exception 'มี job ชื่อ sync-sci-news-every-30-min-v2 อยู่แล้ว — เคยรันสคริปต์นี้ไปหรือยัง';
  end if;

  -- ตรวจ 4: ต้องมี pg_net
  if not exists (select 1 from pg_extension where extname = 'pg_net') then
    raise exception 'ไม่พบส่วนขยาย pg_net — job ใหม่เรียก net.http_post ไม่ได้';
  end if;

  -- ตรวจ 5: ต้องมีตารางบันทึก request_id จากขั้น 2
  if to_regclass('public.c2_sync_runs') is null then
    raise exception 'ไม่พบตาราง public.c2_sync_runs — รันขั้น 2 ก่อน';
  end if;

  raise notice 'ตรวจเงื่อนไขครบ — job เดิม jobid=% จะถูกปิด', v_old_id;

  -- ปิดของเดิม
  perform cron.alter_job(job_id := v_old_id, active := false);

  -- สร้างของใหม่
  --
  -- Authorization ยังส่ง anon key เพื่อให้ผ่าน gateway (verify_jwt = true)
  -- แต่ **สิทธิ์จริงมาจาก x-cron-secret เท่านั้น** ตามที่ฟังก์ชันตรวจ
  --
  -- timeout_milliseconds = 30000 (เดิม 5000)
  --   ‼ ค่านี้ยืนยันจากการเรียก pg_net ด้วยมือครั้งเดียวเท่านั้น
  --     **ยังไม่เคยผ่าน scheduler** — ดูหัวเรื่องของไฟล์
  --
  -- บันทึก request_id ลง c2_sync_runs เพื่อจับคู่ผลตอบกลับในขั้น 5
  --   ‼ **ไม่บันทึก headers** เพราะมี apikey และ x-cron-secret อยู่
  perform cron.schedule(
    'sync-sci-news-every-30-min-v2',
    '*/30 * * * *',
    $cron$
    insert into public.c2_sync_runs(request_id)
    select net.http_post(
      url     := (select decrypted_secret from vault.decrypted_secrets where name = 'project_url')
                 || '/functions/v1/sync-sci-news',
      headers := jsonb_build_object(
        'Content-Type',   'application/json',
        'apikey',         (select decrypted_secret from vault.decrypted_secrets where name = 'anon_key'),
        'Authorization',  'Bearer ' || (select decrypted_secret from vault.decrypted_secrets where name = 'anon_key'),
        'x-cron-secret',  (select decrypted_secret from vault.decrypted_secrets where name = 'sync_cron_secret')
      ),
      body    := '{}'::jsonb,
      timeout_milliseconds := 30000
    );
    $cron$
  );

  -- ตรวจผลก่อน commit
  if not exists (
    select 1 from cron.job
    where jobname = 'sync-sci-news-every-30-min-v2' and active
  ) then
    raise exception 'สร้าง job ใหม่ไม่สำเร็จหรือไม่ active — ยกเลิกทั้งหมด';
  end if;

  if (select active from cron.job where jobid = v_old_id) then
    raise exception 'ปิด job เดิมไม่สำเร็จ — ยกเลิกทั้งหมด';
  end if;

  raise notice 'เปลี่ยนสำเร็จ — ตรวจผลหลัง commit ด้วยขั้น 4 และ 5';
end
$$;

commit;

-- ─────────────────────────────────────────────────────────────────────
-- ขั้น 4 — ตรวจหลัง commit (metadata เท่านั้น)
-- ─────────────────────────────────────────────────────────────────────

select jobid, jobname, schedule, active, length(command) as command_len
from cron.job
where jobname like '%sync-sci-news%'
order by jobname;
-- ต้องเห็น
--   sync-sci-news-every-30-min      active = false
--   sync-sci-news-every-30-min-v2   active = true

-- ─────────────────────────────────────────────────────────────────────
-- ขั้น 5 — ตรวจผล HTTP จริง (ไม่ใช่แค่ job_run_details)
-- ─────────────────────────────────────────────────────────────────────
--
-- ‼ cron.job_run_details ที่ขึ้น succeeded ยืนยันเพียงว่า **คำสั่ง SQL ทำงานจบ**
--   ไม่ได้ยืนยันว่า HTTP สำเร็จ เพราะ net.http_post เป็นแบบคิว
--
-- จับคู่ด้วย request_id ที่บันทึกไว้ในขั้น 2
--
-- ‼ **ห้าม select *** จากตารางผลตอบกลับ เพราะคอลัมน์ headers มี secret
--   เลือกเฉพาะคอลัมน์ที่ปลอดภัยเท่านั้น

select
  r.request_id,
  r.queued_at,
  h.status_code,
  h.timed_out,
  h.error_msg,
  left(coalesce(h.content, ''), 200) as body_preview
from public.c2_sync_runs r
left join net._http_response h on h.id = r.request_id
order by r.queued_at desc
limit 10;

-- เกณฑ์
--   status_code = 200 · timed_out = false · error_msg = null   -> sync สำเร็จจริง
--   status_code = 401                                          -> secret ไม่ตรง หรือ gateway ปฏิเสธ
--   status_code = 403                                          -> ผ่าน gateway แต่ด่านในฟังก์ชันปฏิเสธ
--   status_code = 502                                          -> เว็บข่าวต้นทางล้ม (ฟังก์ชันทำงานถูก)
--   timed_out = true                                           -> เกิน 30000 ms · ต้องพิจารณาเพิ่ม
--   h เป็น null ทั้งแถว                                          -> ยังไม่ได้ส่ง หรือ worker ของ pg_net ไม่ทำงาน

-- ─────────────────────────────────────────────────────────────────────
-- ขั้น 6 — ลบ job เดิม (ทำภายหลัง ไม่ใช่วันเดียวกัน)
-- ─────────────────────────────────────────────────────────────────────
--
-- รันเมื่อยืนยันจากขั้น 5 แล้วว่า job ใหม่ได้ status_code = 200 ติดต่อกันหลายรอบ
--
--   select cron.unschedule('sync-sci-news-every-30-min');
