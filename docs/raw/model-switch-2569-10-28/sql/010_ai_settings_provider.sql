-- 010: ให้ตารางตั้งค่า AI บอกได้ว่าจะใช้ผู้ให้บริการเจ้าไหน
--
-- ปัญหาเดิม: ตาราง web.ai_settings มีแต่คอลัมน์ model และไม่มีโค้ดไหนอ่านมันเลย
-- หน้าผู้ดูแลจึงบันทึกสำเร็จโดยที่โมเดลที่ตอบจริงยังมาจาก env (LLM_PROVIDER /
-- GEMINI_MODEL) เท่านั้น ค่าในตารางกับค่าที่ใช้งานจริงไม่ตรงกันมาตลอด
--
-- การเปลี่ยนแปลงที่นี่เป็น DDL ล้วน ไม่แก้ข้อมูลในแถวเดิมแม้แต่ค่าเดียว
-- ตั้งใจให้การ deploy migration นี้ "ไม่เปลี่ยนพฤติกรรมของระบบ" เพราะฝั่งโค้ด
-- จะถือว่าค่าที่บันทึกใช้ได้ก็เมื่อ provider ถูกระบุไว้ (ดู services/ai_settings.py)
-- แถวเดิมที่มี model แต่ไม่มี provider จึงยังตกไปใช้ค่าจาก env เหมือนก่อน
-- ไม่ใช่ว่าจู่ ๆ ก็ส่งชื่อโมเดลเก่าที่ไม่มีใครตรวจไปให้ผู้ให้บริการจริง
--
-- provider NULL = ยังไม่เลือก ให้ใช้ค่าจาก env
-- model    NULL = เลือกผู้ให้บริการแล้วแต่ไม่ระบุรุ่น ให้ใช้รุ่นตั้งต้นของเจ้านั้นจาก env
-- จึงต้องปลด NOT NULL ของ model ออก เพื่อให้ "เลือกเจ้า แต่ใช้รุ่นตั้งต้น" เขียนลงได้

alter table web.ai_settings
    add column if not exists provider varchar(16);

alter table web.ai_settings
    alter column model drop not null;

do $$
begin
    if not exists (
        select 1 from pg_constraint
         where conrelid = 'web.ai_settings'::regclass
           and conname  = 'ai_settings_provider_known'
    ) then
        alter table web.ai_settings
            add constraint ai_settings_provider_known
            check (provider is null or provider in ('gemini', 'ollama'));
    end if;
end $$;

comment on column web.ai_settings.provider is
    'ผู้ให้บริการที่ใช้เขียนคำตอบ: gemini | ollama · NULL = ใช้ค่าจาก env (LLM_PROVIDER)';
comment on column web.ai_settings.model is
    'ชื่อรุ่นของผู้ให้บริการใน provider · NULL = ใช้รุ่นตั้งต้นจาก env · ใช้ได้เมื่อ provider ไม่ใช่ NULL';
