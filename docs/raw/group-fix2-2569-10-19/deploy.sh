#!/bin/bash
# =====================================================================
# Deploy ของ GROUP_QUESTION_FIX2 — รันบนเซิร์ฟเวอร์ production
#
#   bash /home/ubuntu/release-groupfix2/deploy.sh
#
# ลำดับ: ข้อมูลก่อน แล้วค่อยโค้ด
# ------------------------------
# ทดสอบทั้งสองทิศทางบนฐานทดสอบแล้วเมื่อ 19 ต.ค. 2569
#   โค้ดใหม่ + ข้อมูลเก่า  ถูกต้องทุกอย่าง (ป้ายกำกับ choose_group ยังทำงานปกติ)
#   โค้ดเก่า + ข้อมูลใหม่  ไม่ระเบิด แต่ผู้ใช้เห็นค่าดิบ "required_in_group"
#                          และ 4124813 หายจากท้ายรายการวิชาบังคับ
# ลำดับนี้จึงต้องเป็น ข้อมูล -> โค้ด เพื่อให้ช่วงคาบเกี่ยวเป็นแบบที่ถูกต้อง
# (rollback.sh ย้อนด้วยลำดับเดียวกันด้วยเหตุผลเดียวกัน)
#
# ทุกขั้นตรวจผลจริงแล้วคืนสถานะล้มถ้าไม่ตรง ไม่ใช่พิมพ์ข้อความแล้วไปต่อ
# ขั้นเผยแพร่บันทึก publication ID ลงไฟล์ให้ rollback.sh อ้างถึงโดยตรง
# =====================================================================
set -euo pipefail

R=/home/ubuntu/release-groupfix2
DB=course_advisor
PG=course-advisor-system-postgres-1
NET=course-advisor-system_default
OLD_IMAGE=course-advisor-system-backend:counter-2569-10-16
NEW_IMAGE=course-advisor-system-backend:groupfix2-2569-10-19
GROUP='กลุ่มวิชาฝึกประสบการณ์วิชาชีพหรือสหกิจศึกษา'
REVIEWER='GROUP_QUESTION_FIX2 2569-10-19'

# คำสั่งที่รันในคอนเทนเนอร์ เก็บเป็นตัวแปรเดี่ยวบรรทัดเดียว
# ค่า $INGEST_DATABASE_URL และ $REVIEWER ขยายในคอนเทนเนอร์ ไม่ใช่บนเครื่องโฮสต์
# (ตัวแปรของ shell ไม่ขยายซ้อน ค่าที่อยู่ในสตริงนี้จึงไปถึง sh ของคอนเทนเนอร์ตามตัวอักษร)
PUBCMD='python /app/pipeline_in/mko/subjects_db.py --database-url "$INGEST_DATABASE_URL" --subjects /app/pipeline_in/mko/out/cs66_subjects.json --list-items /app/pipeline_in/mko/out/ma64_careers.json --reviewer "$REVIEWER" --publish --allow-production'
VERCMD='python /app/pipeline_in/mko/verify_publish_content.py --database-url "$INGEST_DATABASE_URL"'
IMGLS='cd /app && find . -type f ! -name "*.pyc" ! -path "*/__pycache__/*" -print0 | xargs -0 md5sum | sort -k2'

# ไฟล์นี้ถือค่าเชื่อมต่อของบทบาทงานข้อมูล จึงต้องถูกลบแม้สคริปต์ล้มกลางทาง
# ใช้ trap ไม่ใช่บรรทัดท้ายไฟล์ เพราะ set -e ออกก่อนถึงบรรทัดท้ายได้
# (เจอจริงตอนทดลองเมื่อ 19 ต.ค. 2569 ไฟล์ค้างอยู่เพราะคำสั่งก่อนหน้าคืนสถานะล้ม)
ENVF="$R/.ingest.env"
cleanup() { if [ -f "$ENVF" ]; then shred -u "$ENVF" 2>/dev/null || rm -f "$ENVF"; fi; return 0; }
trap cleanup EXIT

say() { printf '\n=== %s ===\n' "$1"; }
die() { printf 'ล้มเหลว: %s\n' "$1" >&2; exit 1; }
sq()  { docker exec -i "$PG" psql -U postgres -d "$DB" -At -v ON_ERROR_STOP=1 -c "$1"; }

say "0. ตรวจสภาพก่อนเริ่ม"
cur=$(docker inspect course-advisor-system-backend-1 --format '{{.Config.Image}}')
[ "$cur" = "$OLD_IMAGE" ] || die "อิมเมจที่รันอยู่คือ $cur ไม่ใช่ $OLD_IMAGE"
for f in 009_subject_required_in_group.sql 10-cache-invalidate.sql 20-cache-restore.sql Dockerfile compose.pin-backend-groupfix2.yml files/subjects.py files/chat.py pipeline/mko/subjects_db.py pipeline/mko/verify_publish_content.py pipeline/mko/out/cs66_subjects.json pipeline/mko/out/ma64_careers.json; do
  [ -f "$R/$f" ] || die "ไฟล์ของ release หาย: $f"
done
echo "  อิมเมจปัจจุบัน: $cur"
echo "  ไฟล์ของ release ครบ"

say "1. สำรองฐานข้อมูล"
mkdir -p /home/ubuntu/backups
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
OUT=/home/ubuntu/backups/${DB}_pre_groupfix2_$STAMP.dump
docker exec -i "$PG" pg_dump -U postgres -Fc -d "$DB" > "$OUT"
[ -s "$OUT" ] || die "ไฟล์สำรองว่าง"
docker exec -i "$PG" pg_restore --list /dev/stdin < "$OUT" > /dev/null || die "ไฟล์สำรองอ่านไม่ออก"
echo "$OUT" > "$R/BACKUP_PATH"
echo "  สำรองไว้ที่ $OUT ($(stat -c %s "$OUT") ไบต์ · ตรวจด้วย pg_restore --list แล้ว)"

say "2. บันทึกสถานะก่อนเผยแพร่"
BEFORE_PUB=$(sq "select id from mko.v_live_publication")
[ -n "$BEFORE_PUB" ] || die "อ่าน publication ปัจจุบันไม่ได้"
echo "$BEFORE_PUB" > "$R/PUBLICATION_BEFORE"
echo "  publication ก่อน: $BEFORE_PUB"
echo "  4124813 ตอนนี้  : $(sq "select requirement from mko.v_live_subjects where code='4124813'")"
sq "select requirement||' '||count(*)||' วิชา '||sum(credits)||' หน่วยกิต' from mko.v_live_subjects group by requirement order by 1" | sed 's/^/  ก่อน: /'

say "3. รัน migration 009 (ขยายค่าที่ข้อบังคับยอมรับ)"
docker exec -i "$PG" psql -q -U postgres -d "$DB" -v ON_ERROR_STOP=1 < "$R/009_subject_required_in_group.sql"
def=$(sq "select pg_get_constraintdef(oid) from pg_constraint where conname='published_subjects_requirement_check'")
case "$def" in
  *required_in_group*) echo "  ข้อบังคับรับค่าใหม่แล้ว" ;;
  *) die "ข้อบังคับยังไม่รับ required_in_group: $def" ;;
esac

say "4. เผยแพร่ข้อมูลรายวิชาชุดใหม่"
# บทบาทที่ใช้เขียน: advisor_ingest — advisor_api ของแอปอ่านได้อย่างเดียวบน production
# ส่งค่าเชื่อมต่อผ่าน --env-file ไม่ใช่บรรทัดคำสั่ง เพื่อไม่ให้ค่าโผล่ใน ps หรือ log
umask 077
grep -E '^INGEST_DATABASE_URL=' /home/ubuntu/course-advisor-system/.env | head -1 > "$ENVF"
[ -s "$ENVF" ] || die "หา INGEST_DATABASE_URL ใน .env ไม่พบ"
grep -qE "/$DB\$" "$ENVF" || die "INGEST_DATABASE_URL ไม่ได้ชี้ฐาน $DB"
# ส่ง --list-items ด้วยเหมือนรอบที่เผยแพร่ครั้งก่อน เพื่อให้จุดตรวจรายการอาชีพ
# ใช้เกณฑ์เข้มเดิม (ครบเท่าจำนวนที่ส่ง) ไม่ใช่เกณฑ์สำรองที่เทียบกับยอดก่อนเผยแพร่
if ! docker run --rm --network "$NET" --env-file "$ENVF" -v "$R/pipeline:/app/pipeline_in:ro" -e PYTHONPATH=/app/backend -e REVIEWER="$REVIEWER" --entrypoint sh "$OLD_IMAGE" -c "$PUBCMD" 2>&1 | tee "$R/publish.log"; then
  die "ตัวเผยแพร่คืนสถานะล้มเหลว — ดู $R/publish.log (ตัวมันเองย้อนรายการที่เพิ่มให้แล้ว)"
fi
grep -q "ผ่านทั้งหมด" "$R/publish.log" || die "ไม่พบคำว่า ผ่านทั้งหมด ใน publish.log — ถือว่าไม่ผ่าน"

AFTER_PUB=$(sq "select id from mko.v_live_publication")
[ "$AFTER_PUB" != "$BEFORE_PUB" ] || die "publication ไม่เปลี่ยน แปลว่าไม่ได้เผยแพร่จริง"
echo "$AFTER_PUB" > "$R/PUBLICATION_AFTER"
echo "  publication หลัง: $AFTER_PUB"

say "5. ตรวจเนื้อหาหลังเผยแพร่ว่าของเดิมไม่หาย"
# verify_publish_content.py ยังไม่รู้จักค่า required_in_group จุดตรวจที่ไล่ชื่อค่า
# จึงตกหนึ่งข้อ "โดยคาด" — ขั้นนี้ไม่ปิดข้อความเตือนนั้น แต่ยืนยันว่า
#   (ก) ข้อที่ตกมีข้อเดียว  (ข) ข้อที่ตกคือข้อนั้นจริง  (ค) ข้ออื่นผ่านหมด
# ถ้าตกข้ออื่นเพิ่ม หรือข้อที่ตกไม่ใช่ข้อนี้ ให้หยุด
# การแก้ไฟล์ตัวตรวจเป็นงานแยกตามรายงาน ไม่รวมในรอบนี้
set +e
docker run --rm --network "$NET" --env-file "$ENVF" -v "$R/pipeline:/app/pipeline_in:ro" -e PYTHONPATH=/app/backend --entrypoint sh "$OLD_IMAGE" -c "$VERCMD" > "$R/verify-publish.log" 2>&1
vrc=$?
set -e
cat "$R/verify-publish.log"
n_fail=$(grep -c 'ไม่ผ่าน]' "$R/verify-publish.log" || true)
[ "$vrc" = "1" ] || die "ตัวตรวจเนื้อหาคืนสถานะ $vrc (คาด 1 จากข้อที่ตกโดยคาด)"
[ "$n_fail" = "1" ] || die "ข้อที่ตกมี $n_fail ข้อ ไม่ใช่ 1 ข้อ"
grep 'ไม่ผ่าน]' "$R/verify-publish.log" | grep -q 'required_in_group' || die "ข้อที่ตกไม่ใช่ข้อที่ไล่ชื่อค่า requirement — หยุดไว้ก่อน"
grep -q 'ไม่มีแถวหาย — หาย 0 แถว' "$R/verify-publish.log" || die "มีค่าเดี่ยวหาย"
grep -q 'หาย/เปลี่ยน 0 แถว' "$R/verify-publish.log" || die "รายการเดิม (รวมรายการอาชีพ) เปลี่ยน"
echo "  ของเดิมอยู่ครบ · ตกเฉพาะข้อที่ไล่ชื่อค่า requirement ตามที่คาด"
cleanup

say "6. ตรวจข้อมูลที่เผยแพร่"
req=$(sq "select requirement from mko.v_live_subjects where code='4124813'")
[ "$req" = "required_in_group" ] || die "4124813 เป็น $req ไม่ใช่ required_in_group"
n_req=$(sq "select count(*) from mko.v_live_subjects where requirement='required'")
c_req=$(sq "select sum(credits) from mko.v_live_subjects where requirement='required'")
[ "$n_req" = "35" ] && [ "$c_req" = "96" ] || die "ยอดวิชาบังคับเป็น $n_req วิชา $c_req หน่วยกิต ไม่ใช่ 35/96"
n_grp=$(sq "select count(*) from mko.v_live_subjects where '$GROUP' = any(category_path)")
[ "$n_grp" = "3" ] || die "กลุ่มฝึกประสบการณ์มี $n_grp วิชา ไม่ใช่ 3"
c_grp=$(sq "select sum(credits) from mko.v_live_subjects where '$GROUP' = any(category_path)")
[ "$c_grp" = "13" ] || die "หน่วยกิตรวมของกลุ่มเป็น $c_grp ไม่ใช่ 13"
echo "  4124813 = required_in_group"
echo "  วิชาบังคับ $n_req วิชา $c_req หน่วยกิต (เท่าก่อนเผยแพร่)"
echo "  กลุ่มฝึกประสบการณ์ $n_grp วิชา $c_grp หน่วยกิต"
sq "select requirement||' '||count(*)||' วิชา '||sum(credits)||' หน่วยกิต' from mko.v_live_subjects group by requirement order by 1" | sed 's/^/  หลัง: /'

say "7. build อิมเมจโดยซ้อนเฉพาะสองไฟล์"
docker build -t "$NEW_IMAGE" -f "$R/Dockerfile" "$R" > "$R/build.log" 2>&1 || { tail -20 "$R/build.log"; die "build ไม่สำเร็จ"; }
docker run --rm --entrypoint sh "$OLD_IMAGE" -c "$IMGLS" > /tmp/imgls_old.txt
docker run --rm --entrypoint sh "$NEW_IMAGE" -c "$IMGLS" > /tmp/imgls_new.txt
diff /tmp/imgls_old.txt /tmp/imgls_new.txt > "$R/image-delta.diff" || true
changed=$(awk '/^[<>]/ {print $3}' "$R/image-delta.diff" | sort -u)
printf '%s\n' "$changed" | sed 's/^/  ต่าง: /'
[ "$(printf '%s\n' "$changed" | grep -c .)" = "2" ] || die "ไฟล์ที่ต่างไม่ใช่ 2 ไฟล์"
printf '%s\n' "$changed" | grep -q './backend/app/services/subjects.py' || die "ไม่พบ subjects.py ในรายการที่ต่าง"
printf '%s\n' "$changed" | grep -q './backend/app/services/chat.py' || die "ไม่พบ chat.py ในรายการที่ต่าง"
docker image inspect "$NEW_IMAGE" --format '{{.Id}}' > "$R/IMAGE_ID"
echo "  อิมเมจใหม่: $(cat "$R/IMAGE_ID")"

say "8. ขึ้นโค้ด"
# compose-args.txt สะสม -f ของทุก release ที่ตรึงอิมเมจไว้ ไฟล์ท้ายสุดชนะไฟล์ก่อนหน้า
# จึงต่อ pin ของรอบนี้เข้าไปท้ายสุดได้เลย ไม่ต้องถอด pin เก่า
cd /home/ubuntu/course-advisor-system
ARGS=$(cat /home/ubuntu/release-counter/compose-args.txt)
docker compose -p course-advisor-system $ARGS -f "$R/compose.pin-backend-groupfix2.yml" up -d --no-build --no-deps backend
sleep 8
now=$(docker inspect course-advisor-system-backend-1 --format '{{.Config.Image}}')
[ "$now" = "$NEW_IMAGE" ] || die "อิมเมจหลังขึ้นคือ $now"
docker logs --since 120s course-advisor-system-backend-1 2>&1 | grep -q "Application startup complete" || die "แอปยังไม่พร้อมรับคำขอ"
echo "  ขึ้นแล้ว: $now"

say "9. บันทึก compose-args ชุดใหม่"
# ถ้าไม่บันทึก คำสั่ง docker compose up ครั้งต่อไปที่อ่าน compose-args เดิม
# จะดึง backend กลับเป็นอิมเมจของ release ตัวนับโดยไม่มีใครรู้ตัว
printf '%s -f %s/compose.pin-backend-groupfix2.yml\n' "$ARGS" "$R" > "$R/compose-args.txt"
grep -q 'compose.pin-backend-groupfix2.yml' "$R/compose-args.txt" || die "เขียน compose-args ใหม่ไม่สำเร็จ"
echo "  ใช้ไฟล์นี้ต่อจากนี้: $R/compose-args.txt"

say "10. ล้างแคชเฉพาะแถวที่เกี่ยวข้อง (สำรองก่อนลบในสคริปต์เดียวกัน)"
docker exec -i "$PG" psql -q -U postgres -d "$DB" < "$R/10-cache-invalidate.sql" 2>&1 | tee "$R/cache.log"
if grep -q 'ERROR' "$R/cache.log"; then die "สคริปต์แคชมีข้อผิดพลาด — ดู $R/cache.log"; fi
echo "  ล้างแคชเรียบร้อย (สำรองอยู่ในตาราง public.chat_answer_cache_bak_groupfix2)"

say "เสร็จ — ไปตรวจรับตามเกณฑ์ในรายงาน"
echo "  publication ก่อน  : $BEFORE_PUB"
echo "  publication หลัง  : $AFTER_PUB"
echo "  ไฟล์สำรองฐานข้อมูล: $OUT"
echo "  compose-args ที่ใช้: $R/compose-args.txt"
echo "  ย้อนกลับ          : bash $R/rollback.sh"
