#!/usr/bin/env bash
#
# ขั้นที่ 1 ของ 3 — เพิ่มคอลัมน์ provider ให้ web.ai_settings ของฐาน production
#
# ใช้ (รันบนเซิร์ฟเวอร์):
#   cd /home/ubuntu/switch-release-2569-10-28 && ./deploy_db.sh
#
# ต้องรันก่อน deploy_backend.sh เพราะโค้ดใหม่อ่านคอลัมน์นี้
# (ถ้า backend ขึ้นก่อน ระบบยังตอบคำถามได้ปกติ เพราะ resolve() ดักข้อผิดพลาดแล้ว
#  ถอยไปใช้ค่าจาก env แต่จะมีบรรทัดเตือนใน log ทุก 10 วินาที จึงเรียงให้ฐานมาก่อน)
#
# **เป็น DDL ล้วน ไม่แก้ข้อมูลในแถวเดิมแม้แต่ค่าเดียว** และตั้งใจให้ migration นี้
# ไม่เปลี่ยนพฤติกรรมของระบบ เพราะโค้ดถือว่าค่าที่บันทึกใช้ได้ก็เมื่อ provider ถูกระบุ
# แถวเดิม (model = 'gemini-3.1-flash-lite', provider = NULL) จึงยังตกไปใช้ค่าจาก env
# เหมือนก่อน ไม่ใช่จู่ ๆ ก็ส่งชื่อรุ่นเก่าที่ไม่มีใครตรวจไปให้ Gemini จริง
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
PG=course-advisor-system-postgres-1
ENVF=/home/ubuntu/course-advisor-system/.env
OUT="$HERE/db-run-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT"

die() { echo "** ล้มเหลว: $* **" >&2; exit 1; }

URL=$(grep -E '^DATABASE_URL=' "$ENVF" | head -1 | cut -d= -f2-)
PSQL_URL=${URL/postgresql+psycopg/postgresql}
case "$PSQL_URL" in
  *"/course_advisor") : ;;
  *) die "DATABASE_URL ไม่ได้ชี้ฐาน production: $PSQL_URL" ;;
esac

# อ่านด้วย role ของ backend (advisor_api) — ใช้ตรวจว่าของจริงที่ backend เห็นเป็นอย่างไร
q() { docker exec "$PG" psql "$PSQL_URL" -v ON_ERROR_STOP=1 "$@"; }
# แก้โครงสร้างต้องใช้เจ้าของตาราง · advisor_api ไม่มีสิทธิ์ DDL บน schema web
# (ลองแล้ว: "permission denied for schema web" / "must be owner of table ai_settings")
qa() { docker exec "$PG" psql -U postgres -d course_advisor -v ON_ERROR_STOP=1 "$@"; }

echo "[1/4] สภาพก่อนแก้"
q -c "select column_name, data_type, is_nullable from information_schema.columns
       where table_schema='web' and table_name='ai_settings' order by ordinal_position" \
  | tee "$OUT/cols-before.txt"
q -c "select * from web.ai_settings" | tee "$OUT/row-before.txt"
BEFORE_ROW=$(q -tAc "select coalesce(model,'(null)') || '|' || coalesce(updated_by::text,'(null)') || '|' || updated_at from web.ai_settings where id=1")
echo "  ลายนิ้วมือของแถวเดิม: $BEFORE_ROW"

if q -tAc "select 1 from information_schema.columns where table_schema='web'
            and table_name='ai_settings' and column_name='provider'" | grep -q 1; then
  echo "  มีคอลัมน์ provider อยู่แล้ว — migration นี้รันซ้ำได้ ไม่ต้องทำอะไรเพิ่ม"
fi

echo
echo "[2/4] สำรองตารางก่อน (ไว้ย้อนด้วย rollback_db.sh)"
qa -c "create table if not exists web.ai_settings_backup_switch as
        select * from web.ai_settings" | tee "$OUT/backup.txt"
qa -c "select count(*) as rows_backed_up from web.ai_settings_backup_switch" | tee -a "$OUT/backup.txt"

echo
echo "[3/4] รัน migration 010"
echo "*** กำลังจะแก้โครงสร้างตาราง web.ai_settings ของ production ***"
printf 'พิมพ์ YES เพื่อยืนยัน: '
read -r ok
[ "$ok" = "YES" ] || die "ยกเลิกแล้ว"

docker exec -i "$PG" psql -U postgres -d course_advisor -v ON_ERROR_STOP=1 \
  < "$HERE/sql/010_ai_settings_provider.sql" > "$OUT/migration.txt" 2>&1 \
  || { cat "$OUT/migration.txt"; die "migration ล้ม — ฐานไม่ถูกแก้ (ทุกคำสั่งอยู่ในทรานแซกชันเดียว)"; }
cat "$OUT/migration.txt"

echo
echo "[4/4] ตรวจผล"
q -c "select column_name, data_type, is_nullable from information_schema.columns
       where table_schema='web' and table_name='ai_settings' order by ordinal_position" \
  | tee "$OUT/cols-after.txt"
q -c "select * from web.ai_settings" | tee "$OUT/row-after.txt"

AFTER_ROW=$(q -tAc "select coalesce(model,'(null)') || '|' || coalesce(updated_by::text,'(null)') || '|' || updated_at from web.ai_settings where id=1")
echo "  ลายนิ้วมือของแถวหลังแก้: $AFTER_ROW"
[ "$BEFORE_ROW" = "$AFTER_ROW" ] || die "ข้อมูลในแถวเปลี่ยน — ต้องไม่เปลี่ยน ให้ย้อนด้วย rollback_db.sh"
echo "  ข้อมูลในแถวเดิมไม่เปลี่ยน"

q -tAc "select coalesce(provider,'(null)') from web.ai_settings where id=1" \
  | sed 's/^/  provider ของแถวเดิม = /'

# role ของ backend ต้องอ่านคอลัมน์ใหม่ได้ ไม่งั้นโค้ดใหม่จะอ่านค่าไม่ได้ทุกคำขอ
echo "  ตรวจว่า role ของ backend (advisor_api) อ่านคอลัมน์ใหม่ได้:"
q -tAc "select coalesce(provider,'(null)') from web.ai_settings where id=1" \
  | sed 's/^/    อ่านได้: /' || die "advisor_api อ่านคอลัมน์ provider ไม่ได้ — ต้องให้สิทธิ์ก่อน"
echo
echo "  provider เป็น NULL แปลว่าระบบยังใช้ค่าจาก env เหมือนก่อน deploy"
echo "  เสร็จขั้นที่ 1 — ต่อด้วย ./deploy_backend.sh"
