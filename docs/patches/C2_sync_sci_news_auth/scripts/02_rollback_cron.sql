-- =====================================================================
-- C2 Rollback — คืน cron job เดิม
--
-- ‼ ยังไม่รันบน production — ไฟล์นี้ไว้ตรวจทานก่อน
--
-- ไม่แตะค่า secret ใด ๆ และไม่แสดงค่าใด ๆ
-- ไม่ลบตาราง c2_sync_runs โดยปริยาย (ดูขั้น 5 ถ้าต้องการลบ)
-- =====================================================================

-- ─────────────────────────────────────────────────────────────────────
-- ขั้น 0 — ตรวจสภาพก่อนย้อน
-- ─────────────────────────────────────────────────────────────────────

select jobid, jobname, schedule, active
from cron.job
where jobname like '%sync-sci-news%'
order by jobname;
-- ดูว่ามี job อะไรอยู่บ้างและสถานะเป็นอย่างไร ก่อนตัดสินใจว่าจะย้อนแบบไหน

-- ─────────────────────────────────────────────────────────────────────
-- ขั้น 1 — ย้อนแบบ all-or-nothing
-- ─────────────────────────────────────────────────────────────────────
--
-- ใช้ได้เมื่อ **ยังไม่ได้รันขั้น 6 ของ 01_update_cron.sql** (job เดิมยังไม่ถูกลบ)

begin;

do $$
declare
  v_old_id bigint;
  v_new_id bigint;
begin
  select jobid into v_old_id from cron.job where jobname = 'sync-sci-news-every-30-min';
  select jobid into v_new_id from cron.job where jobname = 'sync-sci-news-every-30-min-v2';

  if v_old_id is null then
    raise exception 'ไม่พบ job เดิมชื่อ sync-sci-news-every-30-min%s',
      case when exists (select 1 from cron.job where jobname = 'c2-sync-sci-news-test')
        then E'
  พบ c2-sync-sci-news-test แปลว่าน่าจะกำลังอยู่บนโปรเจกต์ทดสอบ'
             || E'
  ‼ ไฟล์นี้สำหรับ production เท่านั้น — ใช้ 03_test_rollback_on_test_project.sql แทน'
        else E'
  อาจถูก unschedule ไปแล้ว — ดูขั้น 4' end;
  end if;

  if v_new_id is not null then
    perform cron.alter_job(job_id := v_new_id, active := false);
  else
    raise notice 'ไม่พบ job ใหม่ — อาจยังไม่เคยสร้าง หรือถูกลบไปแล้ว';
  end if;

  perform cron.alter_job(job_id := v_old_id, active := true);

  -- ตรวจผลก่อน commit
  if not (select active from cron.job where jobid = v_old_id) then
    raise exception 'เปิด job เดิมไม่สำเร็จ — ยกเลิกทั้งหมด';
  end if;

  if v_new_id is not null and (select active from cron.job where jobid = v_new_id) then
    raise exception 'ปิด job ใหม่ไม่สำเร็จ — ยกเลิกทั้งหมด';
  end if;

  raise notice 'ย้อนกลับสำเร็จ — ตรวจผลด้วยขั้น 2 และ 3';
end
$$;

commit;

-- ─────────────────────────────────────────────────────────────────────
-- ขั้น 2 — ตรวจสถานะ job
-- ─────────────────────────────────────────────────────────────────────

select jobid, jobname, schedule, active
from cron.job
where jobname like '%sync-sci-news%'
order by jobname;
-- ต้องเห็น: ตัวเดิม active = true · ตัวใหม่ active = false

-- ─────────────────────────────────────────────────────────────────────
-- ขั้น 3 — ตรวจว่ารันผ่านในรอบถัดไป
-- ─────────────────────────────────────────────────────────────────────
--
-- job เดิมไม่ได้บันทึก request_id จึงจับคู่ผลตอบกลับตรง ๆ ไม่ได้
-- ให้ดูตามช่วงเวลาแทน · **ห้าม select *** เพราะ headers มี secret

select id as request_id, status_code, timed_out, error_msg, created
from net._http_response
where created > now() - interval '1 hour'
order by created desc
limit 5;
-- ต้องเห็น status_code = 200

-- ─────────────────────────────────────────────────────────────────────
-- ขั้น 4 — ถ้า job เดิมถูกลบไปแล้ว
-- ─────────────────────────────────────────────────────────────────────
--
-- ต้องสร้างใหม่จากนิยามเดิมที่ **บันทึกไว้ก่อนเปลี่ยน** (README ข้อ "ก่อนลงมือ")
--
-- นิยามเดิมโดยย่อ: POST ไปที่ <project_url>/functions/v1/sync-sci-news
-- พร้อม header apikey และ Authorization ที่อ่าน anon_key จาก Vault
-- body '{}' · timeout เดิม 5000 ms · **ไม่มี x-cron-secret**
--
-- ‼ ถ้า Edge Function ถูก deploy เป็นฉบับใหม่แล้ว job เดิมจะได้ 401
--    เพราะฉบับใหม่ไม่รับ anon key เป็นหลักฐานสิทธิ์
--    → ต้องย้อน Edge Function กลับเป็นฉบับเดิมด้วย (README ข้อ 8)

-- ─────────────────────────────────────────────────────────────────────
-- ขั้น 5 — ลบตารางบันทึก request_id (ไม่บังคับ)
-- ─────────────────────────────────────────────────────────────────────
--
-- **ไม่แนะนำให้ลบทันที** — เก็บไว้ช่วยสืบย้อนว่าช่วงที่ผ่านมาเกิดอะไรขึ้น
-- ตารางนี้ไม่มี secret และ anon/authenticated เข้าถึงไม่ได้
--
-- ถ้าแน่ใจแล้วจึงรัน:
--
--   drop table if exists public.c2_sync_runs;
