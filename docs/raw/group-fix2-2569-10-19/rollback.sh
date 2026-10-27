#!/bin/bash
# =====================================================================
# ย้อน GROUP_QUESTION_FIX2 — รันบนเซิร์ฟเวอร์ production
#
#   bash /home/ubuntu/release-groupfix2/rollback.sh
#   RESTORE_CACHE=no bash /home/ubuntu/release-groupfix2/rollback.sh   # ไม่คืนแคช
#
# อ้าง publication ID ของ release นี้โดยตรง
# ----------------------------------------
# อ่าน id จาก $R/PUBLICATION_AFTER ที่ deploy.sh เขียนไว้ แล้วส่งให้ตัวย้อนด้วย --id
# ไม่ใช้คำว่า "ชุดล่าสุด" เพราะถ้ามีการเผยแพร่ชุดอื่นแทรกเข้ามาหลัง deploy
# การลบชุดล่าสุดจะไปลบของคนอื่น
#
# ลำดับ: ข้อมูลก่อน แล้วค่อยโค้ด
# ------------------------------
# ทดสอบทั้งสองทิศทางบนฐานทดสอบแล้วเมื่อ 19 ต.ค. 2569
#   โค้ดใหม่ + ข้อมูลเก่า  ถูกต้องทุกอย่าง (ป้ายกำกับ choose_group ยังทำงานปกติ)
#   โค้ดเก่า + ข้อมูลใหม่  ไม่ระเบิด แต่ผู้ใช้เห็นค่าดิบ "required_in_group"
#                          และ 4124813 หายจากท้ายรายการวิชาบังคับ
# ย้อนข้อมูลก่อนจึงไม่ผ่านสถานะที่ผู้ใช้เห็นค่าดิบเลย
# =====================================================================
set -euo pipefail

R=/home/ubuntu/release-groupfix2
DB=course_advisor
PG=course-advisor-system-postgres-1
OLD_IMAGE=course-advisor-system-backend:counter-2569-10-16
GROUP='กลุ่มวิชาฝึกประสบการณ์วิชาชีพหรือสหกิจศึกษา'
# ตัวย้อนการเผยแพร่ที่ใช้มาแล้วในรอบก่อน — รับ --id จึงลบเฉพาะชุดที่ระบุ
ROLLBACK_PUBLISH=/home/ubuntu/release-fix-8c3cfbe/rollback_publish.sh

say() { printf '\n=== %s ===\n' "$1"; }
die() { printf 'ล้มเหลว: %s\n' "$1" >&2; exit 1; }
sq()  { docker exec -i "$PG" psql -U postgres -d "$DB" -At -v ON_ERROR_STOP=1 -c "$1"; }

say "0. ยืนยันว่าชุดที่จะลบคือของ release นี้"
[ -f "$R/PUBLICATION_AFTER" ]  || die "ไม่พบ $R/PUBLICATION_AFTER — deploy ยังไม่ถึงขั้นเผยแพร่ หรือไฟล์หาย"
[ -f "$R/PUBLICATION_BEFORE" ] || die "ไม่พบ $R/PUBLICATION_BEFORE"
[ -f "$ROLLBACK_PUBLISH" ]     || die "ไม่พบตัวย้อนการเผยแพร่: $ROLLBACK_PUBLISH"
THIS_PUB=$(tr -d ' \t\r\n' < "$R/PUBLICATION_AFTER")
PREV_PUB=$(tr -d ' \t\r\n' < "$R/PUBLICATION_BEFORE")
[ -n "$THIS_PUB" ] || die "PUBLICATION_AFTER ว่าง"
[ -n "$PREV_PUB" ] || die "PUBLICATION_BEFORE ว่าง"
[ "$THIS_PUB" != "$PREV_PUB" ] || die "id ก่อนและหลังเหมือนกัน — ไฟล์ที่จดไว้ผิด"
echo "  จะลบชุด : $THIS_PUB"
echo "  กลับไปชุด: $PREV_PUB"
live=$(sq "select id from mko.v_live_publication")
[ "$live" = "$THIS_PUB" ] || die "ระบบใช้ชุด $live อยู่ ไม่ใช่ $THIS_PUB — หยุดไว้ก่อน อย่าลบมั่ว"
n_prev=$(sq "select count(*) from mko.publications where id = '$PREV_PUB'")
[ "$n_prev" = "1" ] || die "ไม่พบชุดเดิม $PREV_PUB ที่จะกลับไป (พบ $n_prev แถว)"

say "1. ย้อนข้อมูล (ลูกถูกลบตาม ON DELETE CASCADE)"
bash "$ROLLBACK_PUBLISH" --db production --id "$THIS_PUB"
echo
echo "  หมายเหตุ: บรรทัด 'เกณฑ์ตรวจรับหลังย้อน ... subjects 0' ที่ตัวย้อนพิมพ์ไว้"
echo "  เป็นเกณฑ์ของรอบที่เพิ่งเริ่มเผยแพร่รายวิชา ไม่ใช่ของรอบนี้ — เกณฑ์ของรอบนี้ตรวจต่อข้างล่าง"

say "2. ตรวจว่าข้อมูลกลับไปเป็นก่อน release นี้จริง"
live=$(sq "select id from mko.v_live_publication")
[ "$live" = "$PREV_PUB" ] || die "หลังย้อนแล้วระบบใช้ชุด $live ไม่ใช่ $PREV_PUB"
req=$(sq "select requirement from mko.v_live_subjects where code='4124813'")
[ "$req" = "choose_group" ] || die "4124813 เป็น $req ไม่ใช่ choose_group"
n_new=$(sq "select count(*) from mko.v_live_subjects where requirement='required_in_group'")
[ "$n_new" = "0" ] || die "ยังมี $n_new วิชาที่ใช้ค่า required_in_group อยู่"
n_req=$(sq "select count(*) from mko.v_live_subjects where requirement='required'")
c_req=$(sq "select sum(credits) from mko.v_live_subjects where requirement='required'")
[ "$n_req" = "35" ] && [ "$c_req" = "96" ] || die "ยอดวิชาบังคับเป็น $n_req วิชา $c_req หน่วยกิต ไม่ใช่ 35/96"
n_grp=$(sq "select count(*) from mko.v_live_subjects where '$GROUP' = any(category_path)")
[ "$n_grp" = "3" ] || die "กลุ่มฝึกประสบการณ์มี $n_grp วิชา ไม่ใช่ 3"
echo "  ชุดที่ใช้อยู่ : $live"
echo "  4124813      : $req"
echo "  วิชาบังคับ    : $n_req วิชา $c_req หน่วยกิต"
echo "  กลุ่มฝึกประสบการณ์: $n_grp วิชา · ไม่มีแถวใดใช้ค่า required_in_group แล้ว"

say "3. ย้อนโค้ดกลับอิมเมจเดิม"
# compose-args ชุดเดิม (ก่อน deploy.sh ขั้นที่ 9) ลงท้ายด้วย pin ของ release ตัวนับอยู่แล้ว
# ยังต่อไฟล์ย้อนไว้ท้ายสุดอีกชั้นเพื่อให้เห็นเจตนาชัด ไม่ต้องเดาว่า pin ตัวไหนชนะ
cd /home/ubuntu/course-advisor-system
ARGS=$(cat /home/ubuntu/release-counter/compose-args.txt)
docker compose -p course-advisor-system $ARGS -f "$R/compose.rollback-backend-groupfix2.yml" up -d --no-build --no-deps backend
sleep 8
now=$(docker inspect course-advisor-system-backend-1 --format '{{.Config.Image}}')
[ "$now" = "$OLD_IMAGE" ] || die "อิมเมจหลังย้อนคือ $now ไม่ใช่ $OLD_IMAGE"
docker logs --since 120s course-advisor-system-backend-1 2>&1 | grep -q "Application startup complete" || die "แอปยังไม่พร้อมรับคำขอ"
echo "  ย้อนแล้ว: $now"

say "4. เลิกใช้ compose-args ที่ชี้อิมเมจของรอบนี้"
# ถ้าปล่อยไว้ คำสั่ง docker compose up ครั้งต่อไปที่อ่านไฟล์นั้นจะดึงอิมเมจที่เพิ่งย้อนกลับมาอีก
if [ -f "$R/compose-args.txt" ]; then
  mv "$R/compose-args.txt" "$R/compose-args.rolledback.txt"
  echo "  ย้ายเป็น $R/compose-args.rolledback.txt แล้ว"
  echo "  ไฟล์ที่ใช้ต่อจากนี้: /home/ubuntu/release-counter/compose-args.txt"
else
  echo "  ไม่มีไฟล์ compose-args ของรอบนี้ (deploy ยังไม่ถึงขั้นที่ 9)"
fi

say "5. คืนแคชที่ลบไปตอน deploy"
# ไม่บังคับ — ถ้าไม่คืน แคชจะค่อย ๆ สร้างใหม่เองจากการใช้งานจริง
# ซึ่งปลอดภัยกว่าถ้าไม่แน่ใจว่าคำตอบที่สำรองไว้ยังถูกต้อง
if [ "${RESTORE_CACHE:-yes}" = "yes" ]; then
  docker exec -i "$PG" psql -q -U postgres -d "$DB" < "$R/20-cache-restore.sql" 2>&1 | tee "$R/cache-restore.log"
  if grep -q 'ERROR' "$R/cache-restore.log"; then die "คืนแคชไม่สำเร็จ — ดู $R/cache-restore.log"; fi
  echo "  คืนแคชแล้ว"
else
  echo "  ข้ามตามที่สั่ง (RESTORE_CACHE=no) — แคชจะสร้างใหม่เองจากการใช้งาน"
fi

say "เสร็จ"
echo "  ไม่ต้องย้อน migration 009 — ข้อบังคับที่ยอมรับค่าเพิ่มไม่กระทบข้อมูลที่ย้อนแล้ว"
echo "  และการย้อนข้อบังคับโดยยังมีแถวใช้ค่านั้นอยู่จะล้มเอง"
echo "  ถ้าต้องการย้อนจริง คำสั่งอยู่ท้ายไฟล์ $R/009_subject_required_in_group.sql"
echo "  ถ้าตัวเลขข้างบนไม่ตรง อย่าทำอะไรต่อ ให้กู้จากไฟล์สำรองที่ $(cat "$R/BACKUP_PATH" 2>/dev/null || echo 'ระบุไว้ใน BACKUP_PATH')"
