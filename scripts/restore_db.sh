#!/usr/bin/env bash
# กู้ฐานข้อมูลกลับจากไฟล์สำรอง
#
#   bash scripts/restore_db.sh backups/course_advisor_20260815_120000.sql.gz
#
# คำเตือน: คำสั่งนี้ "เขียนทับ" ข้อมูลปัจจุบันทั้งหมด เพราะไฟล์สำรองถูกสร้างด้วย
# --clean ซึ่งจะสั่งลบตารางเดิมก่อนสร้างใหม่ ควรสำรองของปัจจุบันไว้ก่อนเสมอ
set -euo pipefail

cd "$(dirname "$0")/.."

if [ $# -lt 1 ]; then
    echo "ใช้: bash scripts/restore_db.sh <ไฟล์สำรอง .sql.gz>" >&2
    echo "" >&2
    echo "ไฟล์ที่มีอยู่:" >&2
    ls -1t backups/*.sql.gz 2>/dev/null >&2 || echo "  (ไม่มีไฟล์สำรอง)" >&2
    exit 1
fi

infile="$1"
[ -f "$infile" ] || { echo "ไม่พบไฟล์: $infile" >&2; exit 1; }

echo "จะกู้ข้อมูลจาก $infile ทับฐานข้อมูลปัจจุบัน"
read -r -p "พิมพ์ yes เพื่อยืนยัน: " confirm
[ "$confirm" = "yes" ] || { echo "ยกเลิก"; exit 1; }

gunzip -c "$infile" | docker compose exec -T postgres \
    psql --username=postgres --dbname=course_advisor

echo "กู้ข้อมูลเสร็จแล้ว — ตรวจผล:"
docker compose exec -T postgres psql -U postgres -d course_advisor -t -c \
    "SELECT 'courses='||(SELECT count(*) FROM courses)||
            ' chunks='||(SELECT count(*) FROM course_chunks)||
            ' users='||(SELECT count(*) FROM users);"
