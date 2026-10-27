#!/usr/bin/env bash
#
# ย้อน backend กลับเป็นอิมเมจของ release 27 ต.ค. (level-2569-10-27)
#
# ใช้ (รันบนเซิร์ฟเวอร์):
#   cd /home/ubuntu/level-followup-2569-10-28 && ./rollback_backend.sh
#
# ย้อนด้วยการสลับ compose override กลับไปตรึงอิมเมจเดิม
# **ไม่ลบอิมเมจใหม่** เผื่อต้อง deploy ซ้ำจะได้ไม่ต้อง build ใหม่
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REL=/home/ubuntu/release-followup-2569-10-28
OLD_IMAGE=course-advisor-system-backend:level-2569-10-27

die() { echo "** ล้มเหลว: $* **" >&2; exit 1; }

docker image inspect "$OLD_IMAGE" >/dev/null 2>&1 || die "ไม่พบอิมเมจเดิม $OLD_IMAGE"
[ -f "$REL/compose.rollback-backend-level.yml" ] || die "ไม่พบไฟล์ rollback ใน $REL"

echo "จะย้อน backend กลับเป็น $OLD_IMAGE"
printf 'พิมพ์ YES เพื่อยืนยัน: '
read -r ok
[ "$ok" = "YES" ] || die "ยกเลิกแล้ว"

ARGS=$(cat "$HERE/compose-args.txt")
# shellcheck disable=SC2086
docker compose $ARGS -f "$REL/compose.rollback-backend-level.yml" up -d --no-build --no-deps backend

sleep 5
now=$(docker inspect course-advisor-system-backend-1 --format '{{.Config.Image}}')
echo "อิมเมจที่รันอยู่ : $now"
[ "$now" = "$OLD_IMAGE" ] || die "ยังไม่กลับเป็นอิมเมจเดิม"

code=$(curl -s -o /dev/null -w '%{http_code}' https://stpnru-advisor.duckdns.org/api/health || true)
echo "/api/health -> $code"

echo
echo "ย้อน backend เรียบร้อย"
echo
echo "ผลที่ตามมา — พฤติกรรมกลับไปเป็นแบบ 27 ต.ค."
echo "  · ด่านถามระดับและการแยกเล่มของ /compare-courses ยังทำงานเหมือนเดิม"
echo "  · แต่เมื่อผู้ใช้ตอบแค่ระดับ คำถามที่เขียนใหม่จะทิ้งหัวข้อที่ถาม"
echo "    ทำให้ตอบว่าไม่พบข้อมูล ทั้งที่เลือกเล่มถูกระดับแล้ว"
echo "  · ไม่ต้องย้อนข้อมูลหรือหน้าเว็บ — release นี้ไม่แตะทั้งสองอย่าง"
