#!/bin/bash
# =====================================================================
# สร้าง least-privilege role สำหรับ backend และ pipeline
#
# ไฟล์นี้ถูก mount เข้า /docker-entrypoint-initdb.d/ และรัน "ครั้งเดียว"
# ตอน volume ของ postgres ยังว่าง โดยรันหลัง 10-schema.sql (เรียงตามชื่อไฟล์)
#
# ทำไมเป็น .sh ไม่ใช่ .sql:
#   ไฟล์ .sql ใน initdb ไม่รองรับการอ่าน environment variable — ถ้าจะใส่รหัสผ่าน
#   ต้อง hardcode ลงไฟล์ที่ commit เข้า git ซึ่งห้ามทำ สคริปต์นี้อ่านรหัสผ่านจาก
#   env (ส่งมาจาก docker-compose.yml -> .env) แทน
#
# SECURITY:
#   - ใช้ psql variable แบบ :'name' ซึ่ง quote ค่าให้อัตโนมัติ ไม่ใช่การต่อ string
#     เข้า SQL ตรงๆ (กัน SQL injection จากรหัสผ่านที่มีอักขระพิเศษ)
#   - advisor_api: ไม่มีสิทธิ์เขียนตาราง courses/course_chunks (เป็นงานของ pipeline)
#   - advisor_ingest: ไม่มีสิทธิ์แตะตาราง users/recommendations เลย
#   - ทั้งคู่ไม่มีสิทธิ์ DDL (CREATE/DROP/ALTER) — migration ต้องรันด้วย superuser
# =====================================================================
set -euo pipefail

: "${ADVISOR_API_PASSWORD:?ต้องตั้งค่า ADVISOR_API_PASSWORD ใน .env ก่อน docker compose up}"
: "${ADVISOR_INGEST_PASSWORD:?ต้องตั้งค่า ADVISOR_INGEST_PASSWORD ใน .env ก่อน docker compose up}"

psql -v ON_ERROR_STOP=1 \
     -v api_password="$ADVISOR_API_PASSWORD" \
     -v ingest_password="$ADVISOR_INGEST_PASSWORD" \
     --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-'EOSQL'

    -- ---------------------------------------------------------------
    -- advisor_api — role ของ FastAPI backend
    -- ---------------------------------------------------------------
    CREATE ROLE advisor_api LOGIN PASSWORD :'api_password';

    GRANT USAGE ON SCHEMA public TO advisor_api;

    -- ข้อมูลผู้ใช้: อ่าน/เขียนได้
    GRANT SELECT, INSERT, UPDATE ON users, user_profiles TO advisor_api;
    -- requirements: ลบได้ด้วย (endpoint แก้/ลบ requirement)
    GRANT SELECT, INSERT, UPDATE, DELETE ON user_requirements TO advisor_api;
    -- ประวัติการสนทนา/คำแนะนำ: เขียนเพิ่มได้
    GRANT SELECT, INSERT, UPDATE ON chat_sessions, chat_messages, recommendations TO advisor_api;

    -- ข้อมูลหลักสูตร: อ่านอย่างเดียว — การเขียนเป็นหน้าที่ของ pipeline เท่านั้น
    GRANT SELECT ON courses, course_documents, course_chunks TO advisor_api;

    -- ---------------------------------------------------------------
    -- advisor_ingest — role ของ pipeline นำเข้า PDF
    -- ---------------------------------------------------------------
    CREATE ROLE advisor_ingest LOGIN PASSWORD :'ingest_password';

    GRANT USAGE ON SCHEMA public TO advisor_ingest;
    GRANT SELECT, INSERT, UPDATE ON courses, course_documents TO advisor_ingest;
    -- ต้องมีสิทธิ์ DELETE เฉพาะ course_chunks เพราะการนำเข้าเอกสารเล่มเดิมซ้ำ
    -- (เช่น หลังจากเติมข้อความจาก OCR) ต้องล้าง chunk ชุดเก่าของเล่มนั้นก่อน
    -- ไม่งั้นจะได้เนื้อหาซ้ำสองชุดในคลัง และชนกับ unique (document_id, chunk_index)
    GRANT SELECT, INSERT, UPDATE, DELETE ON course_chunks TO advisor_ingest;
    -- ไม่ให้สิทธิ์ users/user_profiles/recommendations โดยเจตนา:
    -- pipeline ไม่มีเหตุผลต้องอ่านข้อมูลส่วนบุคคลของผู้ใช้เลย

EOSQL

echo "20-roles.sh: สร้าง role advisor_api และ advisor_ingest เรียบร้อย"

# ---------------------------------------------------------------------
# advisor_web — role ของ webapi (บริการที่รับคำขอจากหน้าเว็บ)
#
# ทำไมเป็น "ทางเลือก" ไม่ใช่บังคับแบบสองตัวข้างบน
# ---------------------------------------------------
# ไฟล์นี้ถูก mount โดย compose สามไฟล์ — docker-compose.yml (dev),
# docker-compose.prod.yml (production) และ eval/e2e/docker-compose.e2e.yml
# และยังไม่มีไฟล์ใดส่ง ADVISOR_WEB_PASSWORD มา
# ถ้าใช้ "${VAR:?}" แบบสองตัวข้างบน ทุกสภาพแวดล้อมจะไม่ยอมเริ่มทำงานทันที
# รวมถึงชุดทดสอบ e2e ที่ตั้งรหัสผ่านไว้แค่สองตัว
#
# จึงข้ามไปอย่างมีเสียงเมื่อไม่ได้ตั้งค่า แทนที่จะล้มทั้งการเริ่มต้นฐานข้อมูล
# เมื่อ compose ทั้งสามไฟล์ส่งตัวแปรนี้มาแล้ว จะเปลี่ยนเป็นบังคับก็ได้
#
# ** ไม่ให้สิทธิ์ตารางหรือ schema ใด ๆ ที่นี่ **
# GRANT ของ advisor_web อยู่ใน migration 006 ตามหลัก "role = infrastructure,
# grant = migration" ที่ไฟล์นี้กับ 005 ตั้งไว้แล้ว
# (ดู docs/B1_ADVISOR_WEB_ROLE_DESIGN.md ข้อ 7)
#
# production ไม่ได้ role จากไฟล์นี้ เพราะ initdb รันเฉพาะตอน data directory ว่าง
# ซึ่ง production ไม่ใช่ -> ต้องสร้างด้วยขั้น provisioning แยกครั้งเดียว
# ---------------------------------------------------------------------
if [ -n "${ADVISOR_WEB_PASSWORD:-}" ]; then
    psql -v ON_ERROR_STOP=1 \
         -v web_password="$ADVISOR_WEB_PASSWORD" \
         --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-'EOSQL'

        -- ตรวจก่อนสร้างเพื่อให้รันซ้ำได้ — ไม่ใช้ DO $$ … $$ เพราะ psql
        -- ไม่แทนค่าตัวแปร :'web_password' ข้างใน dollar-quoted string
        SELECT NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'advisor_web')
            AS need_web_role \gset

        \if :need_web_role
            CREATE ROLE advisor_web LOGIN PASSWORD :'web_password'
                NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
        \else
            \echo 'advisor_web มีอยู่แล้ว — ไม่สร้างซ้ำและไม่เปลี่ยนรหัสผ่าน'
        \endif

EOSQL
    echo "20-roles.sh: จัดการ role advisor_web เรียบร้อย (ยังไม่ให้สิทธิ์ตาราง — อยู่ใน migration 006)"
else
    echo "20-roles.sh: ไม่พบ ADVISOR_WEB_PASSWORD จึงข้ามการสร้าง advisor_web" >&2
    echo "20-roles.sh: webapi จะต่อฐานข้อมูลไม่ได้จนกว่าจะตั้งตัวแปรนี้แล้วสร้าง role" >&2
fi
