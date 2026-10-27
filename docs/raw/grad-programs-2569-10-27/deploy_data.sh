#!/usr/bin/env bash
#
# ชุด GRAD_PROGRAMS — ส่วนข้อมูล
#
# ใช้:  ./deploy_data.sh --db course_advisor_test      (ฐานทดสอบ)
#       ./deploy_data.sh --db course_advisor           (production — ถามยืนยันก่อน)
#
# รันบนเซิร์ฟเวอร์ ไม่ใช่บนเครื่องตัวเอง
# คอนเทนเนอร์ชื่อเดียวกันมีทั้งสองที่ รันผิดที่จะโดนฐานผิดตัวโดยไม่มีอะไรเตือน
set -euo pipefail

CONTAINER=course-advisor-system-postgres-1
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/run-$(date +%Y%m%d-%H%M%S)"

die() { echo "** ล้มเหลว: $* **" >&2; exit 1; }

DB=""
while [ $# -gt 0 ]; do
  case "$1" in
    --db) DB="${2:-}"; shift 2 ;;
    *) die "ไม่รู้จักตัวเลือก $1" ;;
  esac
done
[ -n "$DB" ] || die "ต้องระบุ --db"

psqlq() { docker exec -i "$CONTAINER" psql -U postgres -d "$DB" -v ON_ERROR_STOP=1 -At "$@"; }

# ไม่ใส่ -i เพราะคำสั่งนี้ไม่ต้องใช้ stdin และ -i จะกลืนค่าที่ไว้ให้ read ตอบยืนยัน
echo "ฐานข้อมูลปลายทาง : $DB"
docker exec "$CONTAINER" psql -U postgres -lqt | cut -d'|' -f1 | grep -qw "$DB" \
  || die "ไม่พบฐานข้อมูล $DB"

if [ "$DB" = "course_advisor" ]; then
  echo
  echo "*** นี่คือฐานข้อมูล production ***"
  printf 'พิมพ์ YES เพื่อยืนยัน: '
  read -r ok
  [ "$ok" = "YES" ] || die "ยกเลิกแล้ว"
fi

mkdir -p "$OUT"
echo "บันทึกผลไว้ที่ $OUT"

# ── 1. สำรองตารางก่อนแตะ ───────────────────────────────────────────────
echo
echo "[1/4] สำรอง web.site_courses"
docker exec -i "$CONTAINER" pg_dump -U postgres -d "$DB" \
  -t web.site_courses --data-only --column-inserts > "$OUT/site_courses-before.sql"
[ -s "$OUT/site_courses-before.sql" ] || die "ไฟล์สำรองว่าง"
sha256sum "$OUT/site_courses-before.sql" | tee "$OUT/backup.sha256"
echo "  $(grep -c '^INSERT' "$OUT/site_courses-before.sql") แถว"

# ── 2. รันสคริปต์ข้อมูล ────────────────────────────────────────────────
echo
echo "[2/4] เพิ่มและเติมข้อมูล"
docker exec -i "$CONTAINER" psql -U postgres -d "$DB" -v ON_ERROR_STOP=1 \
  --pset=border=2 --pset=footer=off -f - < "$HERE/grad_programs.sql" 2>&1 | tee "$OUT/apply.log"
grep -q 'passed all 7 checks' "$OUT/apply.log" || die "ด่านตรวจไม่ผ่าน ดู $OUT/apply.log"
grep -q '^COMMIT' "$OUT/apply.log" || die "ไม่ได้ commit"

# ── 3. เก็บรหัสแถวและคีย์ที่ release นี้เพิ่ม ให้ rollback ใช้ ───────────
echo
echo "[3/4] บันทึกรหัสแถวที่แก้"
# ทุกคำสั่งใน grad_programs.sql คืน (id, action, added_keys)
# added_keys = คีย์ที่ "เพิ่งเพิ่ม" ให้แถวนั้น คีย์ที่มีอยู่ก่อนแล้วไม่นับ
# rollback จึงถอนเฉพาะของ release นี้ ไม่แตะงานที่ผู้ดูแลแก้เพิ่มทีหลัง
grep -oE '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12} *\| *(inserted|updated) *\|[^|]*' \
  "$OUT/apply.log" | sed 's/ *| */|/g; s/ *$//' > "$OUT/touched.txt" || true
n_ins=$(grep -c '|inserted|' "$OUT/touched.txt" || true)
n_upd=$(grep -c '|updated|' "$OUT/touched.txt" || true)
echo "  แถวใหม่ $n_ins · แถวที่เติมข้อมูล $n_upd"
[ "$n_ins" = "2" ]  || die "แถวใหม่ $n_ins ไม่ใช่ 2"
[ "$n_upd" = "12" ] || die "แถวที่เติมข้อมูล $n_upd ไม่ใช่ 12"

# ── 4. ตรวจผลสุดท้าย ───────────────────────────────────────────────────
echo
echo "[4/4] ตรวจผล"
psqlq -c "select coalesce(detail->>'level','(ว่าง)')||' = '||count(*)
            from web.site_courses
           group by coalesce(detail->>'level','(ว่าง)') order by 1;" | tee "$OUT/after.txt"
psqlq -c "select 'qualifications = '||count(*) from web.site_courses where detail ? 'qualifications';" | tee -a "$OUT/after.txt"
psqlq -c "select 'admission_conditions = '||count(*) from web.site_courses where detail ? 'admission_conditions';" | tee -a "$OUT/after.txt"

got=$(psqlq -c "select count(*) from web.site_courses")
[ "$got" = "14" ] || die "แถวทั้งหมด $got ไม่ใช่ 14"

echo
echo "สำเร็จ"
echo "  ไฟล์สำรอง   : $OUT/site_courses-before.sql"
echo "  รหัสแถวที่แก้ : $OUT/touched.txt"
echo "  ย้อนกลับด้วย : ./rollback_data.sh --db $DB --run $OUT"
