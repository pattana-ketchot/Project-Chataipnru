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
