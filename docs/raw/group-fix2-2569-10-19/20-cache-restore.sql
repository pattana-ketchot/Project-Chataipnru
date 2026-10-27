-- =====================================================================
-- คืนแถวแคชที่ลบไปในขั้น 10 — ใช้คู่กับการย้อน release
--
-- ใช้เมื่อย้อนโค้ดและข้อมูลกลับแล้ว และต้องการให้คำถามเดิมได้คำตอบเดิมทันที
-- โดยไม่ต้องให้ผู้ใช้รอการเรียกโมเดลใหม่
--
-- **ไม่จำเป็นต้องรันก็ได้** ถ้าไม่รัน แคชจะค่อย ๆ สร้างใหม่เองจากการใช้งานจริง
-- ซึ่งปลอดภัยกว่าในกรณีที่ไม่แน่ใจว่าคำตอบเดิมยังถูกต้องอยู่หรือไม่
--
-- รันด้วย superuser
-- =====================================================================
\set ON_ERROR_STOP on
BEGIN;

DO $$
DECLARE
    n_backup   bigint;
    n_before   bigint;
    n_inserted bigint;
BEGIN
    IF to_regclass('public.chat_answer_cache_bak_groupfix2') IS NULL THEN
        RAISE EXCEPTION 'ไม่มีตารางสำรอง chat_answer_cache_bak_groupfix2 — ไม่มีอะไรให้คืน';
    END IF;

    SELECT count(*) INTO n_backup FROM public.chat_answer_cache_bak_groupfix2;
    SELECT count(*) INTO n_before FROM public.chat_answer_cache;

    -- แถวที่ถูกสร้างใหม่หลัง deploy อาจมีคีย์ซ้ำกับของเดิม — ของเดิมคือสิ่งที่ต้องการคืน
    -- จึงเขียนทับด้วยค่าจากตารางสำรอง
    INSERT INTO public.chat_answer_cache AS c
         (question_key, corpus_version, status, reply, citations, hits, created_at, last_used_at)
    SELECT question_key, corpus_version, status, reply, citations, hits, created_at, last_used_at
      FROM public.chat_answer_cache_bak_groupfix2
        ON CONFLICT (question_key) DO UPDATE
       SET corpus_version = excluded.corpus_version,
           status         = excluded.status,
           reply          = excluded.reply,
           citations      = excluded.citations,
           hits           = excluded.hits,
           created_at     = excluded.created_at,
           last_used_at   = excluded.last_used_at;
    GET DIAGNOSTICS n_inserted = ROW_COUNT;

    IF n_inserted <> n_backup THEN
        RAISE EXCEPTION 'คืน % แถว แต่สำรองไว้ % แถว — ไม่ตรงกัน', n_inserted, n_backup;
    END IF;

    RAISE NOTICE 'คืนแคช % แถว · ก่อนคืน % แถว · หลังคืน % แถว',
                 n_inserted, n_before, (SELECT count(*) FROM public.chat_answer_cache);
END;
$$;

COMMIT;

-- ลบตารางสำรองทิ้งเมื่อแน่ใจแล้ว (ไม่รันอัตโนมัติ)
--   DROP TABLE public.chat_answer_cache_bak_groupfix2;
