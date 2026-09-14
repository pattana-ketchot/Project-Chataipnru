#!/usr/bin/env bash
# ฐานข้อมูล local สำหรับพัฒนาการสกัดข้อมูล มคอ. (Phase 1 ของ docs/MKO_STRUCTURED_DATA_DESIGN.md)
#
#   bash scripts/mko_local_db.sh
#
# ไม่เกี่ยวกับ production และไม่ใช้ฐานข้อมูล dev เดิมของ docker-compose.yml:
#   - คอนเทนเนอร์แยกชื่อ mko-local-pg ใช้ volume ของตัวเอง ฟังเฉพาะ 127.0.0.1
#   - ใช้ trust auth เพราะเข้าได้จากเครื่องนี้เท่านั้น ไม่ต้องมีรหัสผ่านในไฟล์ใดๆ
#
# ข้อมูลตั้งต้นอยู่ใน backups/mko_local/ (อยู่ใน .gitignore) ได้มาจาก production แบบอ่านอย่างเดียว:
#   public_schema.sql            pg_dump --schema=public --schema-only --no-owner --no-privileges
#   courses_documents_data.sql   pg_dump --data-only -t public.courses -t public.course_documents
# ไม่มีข้อมูลผู้ใช้ บทสนทนา หรือ chunk ติดมา
set -euo pipefail

cd "$(dirname "$0")/.."

NAME="${MKO_LOCAL_CONTAINER:-mko-local-pg}"
PORT="${MKO_LOCAL_PORT:-55432}"
DATA_DIR="backups/mko_local"

if ! docker ps -a --format '{{.Names}}' | grep -qx "$NAME"; then
    echo "สร้างคอนเทนเนอร์ $NAME ที่ 127.0.0.1:$PORT"
    docker run -d --name "$NAME" \
        -p "127.0.0.1:${PORT}:5432" \
        -e POSTGRES_DB=course_advisor \
        -e POSTGRES_HOST_AUTH_METHOD=trust \
        -v mko_local_pgdata:/var/lib/postgresql/data \
        pgvector/pgvector:pg16 >/dev/null
elif ! docker ps --format '{{.Names}}' | grep -qx "$NAME"; then
    docker start "$NAME" >/dev/null
fi

for _ in $(seq 1 60); do
    docker exec "$NAME" pg_isready -U postgres -d course_advisor >/dev/null 2>&1 && break
    sleep 1
done

psql_local() {
    docker exec -i "$NAME" psql -v ON_ERROR_STOP=1 -q -U postgres -d course_advisor "$@"
}

has_courses=$(psql_local -Atc "SELECT to_regclass('public.courses') IS NOT NULL")
if [ "$has_courses" != "t" ]; then
    for f in public_schema.sql courses_documents_data.sql; do
        [ -f "$DATA_DIR/$f" ] || { echo "ไม่พบ $DATA_DIR/$f" >&2; exit 1; }
    done
    echo "สร้างตาราง public และข้อมูลหลักสูตรตั้งต้น"
    psql_local <<'SQL'
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS citext;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'advisor_api') THEN CREATE ROLE advisor_api NOLOGIN; END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'advisor_ingest') THEN CREATE ROLE advisor_ingest NOLOGIN; END IF;
END $$;
SQL
    # ตัดคำสั่งสร้าง schema public ออก เพราะฐานข้อมูลใหม่มี schema นี้อยู่แล้ว (pg_dump ใส่มาให้เสมอ)
    grep -v '^CREATE SCHEMA public;$' "$DATA_DIR/public_schema.sql" | psql_local
    psql_local < "$DATA_DIR/courses_documents_data.sql"
fi

for migration in db/migrations/*.sql; do
    echo "migration: $migration"
    psql_local < "$migration"
done

psql_local -Atc "SELECT 'courses=' || (SELECT count(*) FROM public.courses) || ' documents=' || (SELECT count(*) FROM public.course_documents) || ' migrations=' || (SELECT string_agg(version, ',') FROM mko.schema_migrations)"
