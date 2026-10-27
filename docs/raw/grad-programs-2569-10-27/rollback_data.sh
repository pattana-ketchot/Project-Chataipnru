#!/usr/bin/env bash
#
# ย้อนชุด GRAD_PROGRAMS — ส่วนข้อมูล
#
# ใช้:  ./rollback_data.sh --db course_advisor_test --run /path/to/run-YYYYmmdd-HHMMSS
#
# หลักการ: ถอนเฉพาะสิ่งที่ release นี้ใส่เข้าไป
#   - แถวที่ release นี้เพิ่ม  -> ลบทิ้ง
#   - แถวเดิมที่เติมคีย์ให้     -> ถอนเฉพาะ "คีย์ที่เพิ่งเพิ่ม" ตามที่ deploy บันทึกไว้
#
# **งานที่ผู้ดูแลแก้เพิ่มหลัง deploy จะไม่ถูกแตะ** เพราะไม่ได้คืนทั้งตารางจากไฟล์สำรอง
# และไม่ได้ถอนคีย์ที่มีอยู่ก่อน release นี้
set -euo pipefail

CONTAINER=course-advisor-system-postgres-1
die() { echo "** ล้มเหลว: $* **" >&2; exit 1; }

DB=""; RUN=""
while [ $# -gt 0 ]; do
  case "$1" in
    --db)  DB="${2:-}"; shift 2 ;;
    --run) RUN="${2:-}"; shift 2 ;;
    *) die "ไม่รู้จักตัวเลือก $1" ;;
  esac
done
[ -n "$DB" ]  || die "ต้องระบุ --db"
[ -n "$RUN" ] || die "ต้องระบุ --run (โฟลเดอร์ที่ deploy_data.sh สร้าง)"
F="$RUN/touched.txt"
[ -s "$F" ] || die "ไม่พบ $F"

psqlq() { docker exec -i "$CONTAINER" psql -U postgres -d "$DB" -v ON_ERROR_STOP=1 -At "$@"; }

n_ins=$(grep -c '|inserted|' "$F" || true)
n_upd=$(grep -c '|updated|' "$F" || true)
echo "ฐานข้อมูล : $DB"
echo "จะลบแถวใหม่ $n_ins แถว · ถอนคีย์ออกจากแถวเดิม $n_upd แถว"
if [ "$DB" = "course_advisor" ]; then
  printf 'พิมพ์ YES เพื่อยืนยัน: '
  read -r ok
  [ "$ok" = "YES" ] || die "ยกเลิกแล้ว"
fi

before=$(psqlq -c "select count(*) from web.site_courses")

# รายการรหัสของแถวที่ต้องลบ
ins_arr="array[$(grep '|inserted|' "$F" | cut -d'|' -f1 | sed "s/.*/'&'/" | paste -sd, -)]::uuid[]"

# ตาราง (รหัสแถว, คีย์ที่ต้องถอน) สำหรับแถวเดิม — ข้ามแถวที่ไม่มีคีย์ใหม่เลย
rows=""
while IFS='|' read -r id action keys; do
  [ "$action" = "updated" ] || continue
  [ -n "$keys" ] || continue
  karr="array[$(echo "$keys" | tr ',' '\n' | sed "s/.*/'&'/" | paste -sd, -)]::text[]"
  rows="${rows}${rows:+,}('$id'::uuid, $karr)"
done < "$F"

{
  echo "begin;"
  echo
  echo "-- ลบเฉพาะแถวที่ release นี้สร้าง และต้องยังเป็นแถวของรอบนี้จริง"
  echo "delete from web.site_courses"
  echo " where id = any ($ins_arr)"
  echo "   and detail->>'source_checked_at' = '27 ต.ค. 2569';"
  echo
  if [ -n "$rows" ]; then
    echo "-- ถอนเฉพาะคีย์ที่ release นี้เพิ่ม คีย์อื่นและงานที่แก้เพิ่มทีหลังไม่ถูกแตะ"
    echo "update web.site_courses c"
    echo "   set detail = c.detail - v.keys"
    echo "  from (values $rows) as v(id, keys)"
    echo " where c.id = v.id;"
  else
    echo "-- ไม่มีคีย์ที่ต้องถอน"
  fi
  echo
  echo "\\echo '--- หลังย้อนกลับ ---'"
  echo "select coalesce(detail->>'level','(ว่าง)') as lvl, count(*) as n"
  echo "  from web.site_courses group by coalesce(detail->>'level','(ว่าง)') order by 1;"
  echo "select 'qualifications = '||count(*) from web.site_courses where detail ? 'qualifications';"
  echo
  echo "commit;"
} > "$RUN/rollback.generated.sql"

echo "คำสั่งที่จะรันอยู่ใน $RUN/rollback.generated.sql"
docker exec -i "$CONTAINER" psql -U postgres -d "$DB" -v ON_ERROR_STOP=1 \
  --pset=border=2 -f - < "$RUN/rollback.generated.sql"

after=$(psqlq -c "select count(*) from web.site_courses")
echo
echo "แถวก่อนย้อน $before -> หลังย้อน $after"
[ "$((before - after))" = "$n_ins" ] || die "ลบไป $((before - after)) แถว ไม่ใช่ $n_ins"

echo
echo "ย้อนกลับเรียบร้อย"
echo "ถ้าผลยังไม่ถูกต้อง ใช้ไฟล์สำรองเต็ม: $RUN/site_courses-before.sql"
echo "  (คืนทั้งตาราง — จะทับงานที่ผู้ดูแลแก้หลัง deploy ด้วย ใช้เป็นทางสุดท้าย)"
