-- =====================================================================
-- C2 — ทดสอบ rollback ของ cron **บนโปรเจกต์ทดสอบเท่านั้น**
--
-- ‼ ห้ามรันบน production
-- ‼ ห้ามรัน 01_update_cron.sql หรือ 02_rollback_cron.sql บนโปรเจกต์ทดสอบ
--    เพราะสองไฟล์นั้นอ้างชื่อ job ของ production ซึ่งไม่มีที่นี่
--
-- ─────────────────────────────────────────────────────────────────────
-- ทำไมต้องมีไฟล์แยก
-- ─────────────────────────────────────────────────────────────────────
-- สภาพโปรเจกต์ทดสอบปัจจุบัน
--   มี     : c2-sync-sci-news-test        (active = false)
--   ไม่มี   : sync-sci-news-every-30-min      <- job ของ production
--   ไม่มี   : sync-sci-news-every-30-min-v2
--
-- 02_rollback_cron.sql จะ raise exception ทันทีที่บรรทัดแรก เพราะหา
-- job ชื่อ sync-sci-news-every-30-min ไม่เจอ
--
-- **นั่นคือพฤติกรรมที่ถูกต้อง** — ล้มเสียงดังดีกว่าทำงานผิดเป้า
-- แต่แปลว่าทดสอบ rollback ด้วยไฟล์นั้นบนโปรเจกต์ทดสอบไม่ได้
--
-- ─────────────────────────────────────────────────────────────────────
-- หลักการของไฟล์นี้
-- ─────────────────────────────────────────────────────────────────────
--   · ใช้ชื่อ job ของโปรเจกต์ทดสอบเท่านั้น
--   · **ไม่เปิด job ค้างไว้** — ทุกขั้นจบด้วย active = false
--   · ไม่แสดงค่า secret ใด ๆ
--   · แยกการทดสอบ cron ออกจาก Edge Function และ webapi โดยสิ้นเชิง
-- =====================================================================

-- ─────────────────────────────────────────────────────────────────────
-- ขั้น 0 — ยืนยันว่ากำลังอยู่บนโปรเจกต์ทดสอบ
-- ─────────────────────────────────────────────────────────────────────

select jobid, jobname, schedule, active
from cron.job
order by jobname;

-- ‼ ต้องเห็น c2-sync-sci-news-test และ **ต้องไม่เห็น** sync-sci-news-every-30-min
--   ถ้าเห็นชื่อหลัง แปลว่ากำลังอยู่บน production -> **หยุดทันที**

do $$
begin
  if exists (select 1 from cron.job where jobname = 'sync-sci-news-every-30-min') then
    raise exception 'พบ job ของ production — ไฟล์นี้ห้ามรันบน production หยุดทันที';
  end if;
  if not exists (select 1 from cron.job where jobname = 'c2-sync-sci-news-test') then
    raise exception 'ไม่พบ job ทดสอบ c2-sync-sci-news-test — สร้างก่อนหรือตรวจชื่อ';
  end if;
  raise notice 'ยืนยันแล้วว่าอยู่บนโปรเจกต์ทดสอบ';
end
$$;

-- บันทึกสถานะตั้งต้นไว้เทียบ
select jobname, active as active_before
from cron.job
where jobname = 'c2-sync-sci-news-test';
-- คาดว่า active_before = false

-- ─────────────────────────────────────────────────────────────────────
-- ขั้น 1 — ทดสอบว่า transaction rollback คืนสถานะ job ได้จริง
-- ─────────────────────────────────────────────────────────────────────
--
-- จงใจให้ล้มกลาง transaction หลังจากเปลี่ยนสถานะ job ไปแล้ว
-- แล้วตรวจว่าสถานะกลับมาเหมือนเดิม
--
-- **ไม่ใช้ job จริงของ production** และ **ไม่ทิ้ง job เปิดค้าง**

do $$
declare
  v_id           bigint;
  v_before       boolean;
  v_after        boolean;
  v_inside       boolean;
  v_caught       boolean := false;
begin
  select jobid, active into v_id, v_before
  from cron.job where jobname = 'c2-sync-sci-news-test';

  raise notice 'สถานะก่อนเริ่ม: active = %', v_before;

  begin
    -- เปลี่ยนสถานะ
    perform cron.alter_job(job_id := v_id, active := not v_before);

    select active into v_inside from cron.job where jobid = v_id;
    raise notice 'ภายใน transaction: active = % (ควรตรงข้ามกับก่อนเริ่ม)', v_inside;

    -- จงใจล้ม
    raise exception 'ทดสอบ: จงใจล้มเพื่อดูว่า rollback คืนสถานะไหม';
  exception
    when others then
      v_caught := true;
      raise notice 'ดักข้อผิดพลาดได้: %', sqlerrm;
  end;

  -- ตรวจหลัง rollback ของบล็อกภายใน
  select active into v_after from cron.job where jobid = v_id;

  if not v_caught then
    raise exception 'ไม่ได้เกิดข้อผิดพลาดตามที่ตั้งใจ — การทดสอบไม่สมบูรณ์';
  end if;

  if v_after is distinct from v_before then
    raise exception 'rollback ไม่คืนสถานะ: ก่อน=% หลัง=%', v_before, v_after;
  end if;

  raise notice 'ผ่าน: rollback คืนสถานะ active = % ได้ถูกต้อง', v_after;
end
$$;

-- ตรวจซ้ำจากภายนอกว่าสถานะไม่เปลี่ยน
select jobname, active as active_after_test
from cron.job
where jobname = 'c2-sync-sci-news-test';
-- ต้องเท่ากับ active_before จากขั้น 0

-- ─────────────────────────────────────────────────────────────────────
-- ขั้น 2 — ทดสอบวงจร เปิด -> ปิด โดยไม่ให้ sync วนโดยไม่จำเป็น
-- ─────────────────────────────────────────────────────────────────────
--
-- ‼ ขั้นนี้ทำให้ job ทำงานจริงหนึ่งรอบ **ถ้าทิ้งไว้ข้ามรอบตาราง**
--   จึงเปิดและปิดในคำสั่งเดียวกัน ไม่ทิ้งค้าง
--
-- ถ้าต้องการให้มันรันจริงเพื่อดูผล ให้ใช้ขั้น 3 แทน

do $$
declare
  v_id bigint;
begin
  select jobid into v_id from cron.job where jobname = 'c2-sync-sci-news-test';

  perform cron.alter_job(job_id := v_id, active := true);
  if not (select active from cron.job where jobid = v_id) then
    raise exception 'เปิดไม่สำเร็จ';
  end if;
  raise notice 'เปิดสำเร็จ';

  perform cron.alter_job(job_id := v_id, active := false);
  if (select active from cron.job where jobid = v_id) then
    raise exception 'ปิดไม่สำเร็จ — ‼ job ยังเปิดค้าง ต้องปิดด้วยมือทันที';
  end if;
  raise notice 'ปิดกลับสำเร็จ — ไม่มี job เปิดค้าง';
end
$$;

select jobname, active
from cron.job
where jobname = 'c2-sync-sci-news-test';
-- ต้องได้ active = false

-- ─────────────────────────────────────────────────────────────────────
-- ขั้น 3 — ถ้าต้องการให้ job รันจริงเพิ่มอีกรอบ (ทำเมื่อจำเป็นเท่านั้น)
-- ─────────────────────────────────────────────────────────────────────
--
-- ‼ ทำแยกเป็นสองคำสั่ง และ **ตั้งนาฬิกาเตือนตัวเองให้กลับมาปิด**
--   ตารางคือทุก 30 นาที ถ้าลืมปิดจะยิงเว็บต้นทางเรื่อย ๆ
--
-- เปิด:
--   select cron.alter_job(
--     job_id := (select jobid from cron.job where jobname = 'c2-sync-sci-news-test'),
--     active := true);
--
-- รอหนึ่งรอบแล้วดูผล (ขั้น 4) จากนั้น **ปิดทันที**:
--   select cron.alter_job(
--     job_id := (select jobid from cron.job where jobname = 'c2-sync-sci-news-test'),
--     active := false);

-- ─────────────────────────────────────────────────────────────────────
-- ขั้น 4 — ดูผล HTTP จริงที่ job บันทึกไว้
-- ─────────────────────────────────────────────────────────────────────
--
-- ‼ **ห้าม select *** เพราะคอลัมน์ headers มี apikey และ x-cron-secret

select
  r.request_id,
  r.queued_at,
  h.status_code,
  h.timed_out,
  h.error_msg,
  left(coalesce(h.content, ''), 120) as body_preview
from public.c2_sync_runs r
left join net._http_response h on h.id = r.request_id
order by r.queued_at desc
limit 10;

-- เกณฑ์: status_code = 200 · timed_out = false · error_msg = null

-- ─────────────────────────────────────────────────────────────────────
-- ขั้น 5 — คืนสภาพโปรเจกต์ทดสอบ
-- ─────────────────────────────────────────────────────────────────────

-- 5.1 ปิด job ให้แน่ใจ (รันได้ซ้ำไม่มีผลเสีย)
select cron.alter_job(
  job_id := (select jobid from cron.job where jobname = 'c2-sync-sci-news-test'),
  active := false
);

select jobname, active from cron.job where jobname = 'c2-sync-sci-news-test';
-- ต้องได้ active = false

-- 5.2 ถ้าต้องการลบ job ทดสอบทิ้ง (ไม่บังคับ)
--   select cron.unschedule('c2-sync-sci-news-test');

-- 5.3 ถ้าต้องการลบตารางบันทึก (ไม่แนะนำ — เก็บไว้ดูประวัติได้ และไม่มี secret)
--   drop table if exists public.c2_sync_runs;
