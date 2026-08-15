#!/usr/bin/env bash
# สำรองฐานข้อมูลทั้งก้อนเป็นไฟล์ .sql.gz
#
#   bash scripts/backup_db.sh
#
# ทำไมต้องมี: ข้อมูลใน volume ของ postgres มีทั้งบัญชีผู้ใช้ บทสนทนา และ
# course_chunks 7,301 แถวที่ใช้เวลา ingest ประมาณ 20 นาที ถ้า volume เสียหาย
# หรือเผลอสั่ง `docker compose down -v` จะหายทั้งหมดในคำสั่งเดียว
#
# ใช้ pg_dump ไม่ใช่การคัดลอกโฟลเดอร์ข้อมูลของ postgres โดยตรง เพราะการคัดลอก
# ไฟล์ขณะเซิร์ฟเวอร์กำลังเขียนอยู่จะได้ข้อมูลที่ไม่สอดคล้องกัน (torn state)
# ส่วน pg_dump อ่านจาก snapshot ที่สอดคล้องกันเสมอแม้มีคนใช้งานอยู่
set -euo pipefail

cd "$(dirname "$0")/.."

BACKUP_DIR="${BACKUP_DIR:-backups}"
KEEP="${KEEP:-10}"          # เก็บไฟล์ล่าสุดกี่ชุด
DB_NAME="course_advisor"
DB_USER="postgres"

mkdir -p "$BACKUP_DIR"
stamp=$(date +%Y%m%d_%H%M%S)
outfile="$BACKUP_DIR/${DB_NAME}_${stamp}.sql.gz"

echo "กำลังสำรองฐานข้อมูล -> $outfile"

# -T ปิด TTY ไม่งั้น output จะมีอักขระควบคุมปนจนไฟล์เสีย
# --clean --if-exists ให้ไฟล์ที่ได้สั่งลบของเดิมก่อนสร้างใหม่ตอน restore
docker compose exec -T postgres \
    pg_dump --username="$DB_USER" --dbname="$DB_NAME" --clean --if-exists \
    | gzip > "$outfile"

# ถ้า pg_dump ล้มกลางทางไฟล์จะเล็กผิดปกติ ตรวจไว้กันเก็บไฟล์เสียโดยไม่รู้ตัว
size=$(wc -c < "$outfile")
if [ "$size" -lt 10000 ]; then
    echo "ผิดพลาด: ไฟล์สำรองเล็กผิดปกติ ($size ไบต์) — น่าจะ dump ไม่สำเร็จ" >&2
    rm -f "$outfile"
    exit 1
fi

echo "สำเร็จ: $(du -h "$outfile" | cut -f1)"

# ลบไฟล์เก่าเกินจำนวนที่ตั้งไว้
count=$(ls -1 "$BACKUP_DIR"/${DB_NAME}_*.sql.gz 2>/dev/null | wc -l)
if [ "$count" -gt "$KEEP" ]; then
    ls -1t "$BACKUP_DIR"/${DB_NAME}_*.sql.gz | tail -n +$((KEEP + 1)) | while read -r old; do
        echo "ลบไฟล์เก่า: $old"
        rm -f "$old"
    done
fi

echo "ไฟล์สำรองที่มีอยู่ $(ls -1 "$BACKUP_DIR"/${DB_NAME}_*.sql.gz | wc -l) ชุด"
