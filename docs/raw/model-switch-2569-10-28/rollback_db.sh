#!/usr/bin/env bash
#
# ย้อนขั้นที่ 1 — เอาคอลัมน์ provider ออกจาก web.ai_settings ของ production
#
# ต้องย้อน backend ก่อน (./rollback_backend.sh) เพราะโค้ดใหม่อ่านคอลัมน์นี้
# ถ้าตัดคอลัมน์ทิ้งขณะที่โค้ดใหม่ยังรันอยู่ resolve() จะดักข้อผิดพลาดแล้วถอยไปใช้ค่า
# จาก env ซึ่งยังตอบคำถามได้ แต่ผู้ดูแลจะตั้งค่าไม่ได้และ log จะมีบรรทัดเตือนตลอด
#
# ข้อมูลในคอลัมน์ model/updated_by/updated_at ไม่ถูกแตะเลยทั้งตอน deploy และตอนย้อน
# ค่าที่ผู้ดูแลตั้งไว้ในคอลัมน์ provider จะหายไปตามคอลัมน์ ซึ่งถูกต้องตามที่ควร
# เพราะโค้ดเก่าไม่รู้จักค่านั้นอยู่แล้ว
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
PG=course-advisor-system-postgres-1
ENVF=/home/ubuntu/course-advisor-system/.env
OUT="$HERE/db-rollback-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT"

die() { echo "** ล้มเหลว: $* **" >&2; exit 1; }

URL=$(grep -E '^DATABASE_URL=' "$ENVF" | head -1 | cut -d= -f2-)
PSQL_URL=${URL/postgresql+psycopg/postgresql}
q() { docker exec "$PG" psql "$PSQL_URL" -v ON_ERROR_STOP=1 "$@"; }
# แก้โครงสร้างต้องใช้เจ้าของตาราง · advisor_api ไม่มีสิทธิ์ DDL บน schema web
# (ลองแล้ว: "permission denied for schema web" / "must be owner of table ai_settings")
qa() { docker exec "$PG" psql -U postgres -d course_advisor -v ON_ERROR_STOP=1 "$@"; }

echo "[1/3] สภาพก่อนย้อน"
q -c "select * from web.ai_settings" | tee "$OUT/row-before.txt"
running=$(docker inspect course-advisor-system-backend-1 --format '{{.Config.Image}}')
echo "  อิมเมจ backend ที่รันอยู่: $running"
case "$running" in
  *switch-2569-10-28)
    echo "  ** backend ยังเป็นรุ่นที่ใช้คอลัมน์นี้ — ให้รัน ./rollback_backend.sh ก่อน **"
    printf 'ยืนยันว่าจะย้อนฐานก่อนอยู่ดี พิมพ์ YES-ANYWAY: '
    read -r ok2
    [ "$ok2" = "YES-ANYWAY" ] || die "ยกเลิกแล้ว"
    ;;
esac

echo
echo "[2/3] ตัดคอลัมน์ provider ออก"
echo "*** กำลังจะแก้โครงสร้างตาราง web.ai_settings ของ production ***"
printf 'พิมพ์ YES เพื่อยืนยัน: '
read -r ok
[ "$ok" = "YES" ] || die "ยกเลิกแล้ว"

# ไม่คืน NOT NULL ของ model ถ้าตอนนี้มีแถวที่ model เป็น NULL อยู่ (ผู้ดูแลเลือก
# ผู้ให้บริการแล้วไม่ระบุรุ่น) — เติมค่าเดิมจากตารางสำรองก่อน แล้วจึงคืนเงื่อนไข
qa -c "update web.ai_settings s
         set model = coalesce(s.model, b.model, 'gemini-3.5-flash-lite')
        from web.ai_settings_backup_switch b
       where s.id = b.id and s.model is null" | tee "$OUT/restore-model.txt"
qa -c "alter table web.ai_settings drop constraint if exists ai_settings_provider_known" \
  | tee -a "$OUT/restore-model.txt"
qa -c "alter table web.ai_settings drop column if exists provider" | tee -a "$OUT/restore-model.txt"
qa -c "alter table web.ai_settings alter column model set not null" | tee -a "$OUT/restore-model.txt"

echo
echo "[3/3] ตรวจผล"
q -c "select column_name, data_type, is_nullable from information_schema.columns
       where table_schema='web' and table_name='ai_settings' order by ordinal_position" \
  | tee "$OUT/cols-after.txt"
q -c "select * from web.ai_settings" | tee "$OUT/row-after.txt"
echo
echo "  ตารางสำรอง web.ai_settings_backup_switch ยังอยู่ ลบเองเมื่อมั่นใจแล้ว:"
echo "    drop table web.ai_settings_backup_switch;"
