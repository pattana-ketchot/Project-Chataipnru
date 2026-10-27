#!/usr/bin/env bash
#
# ย้อน backend กลับเป็นอิมเมจของ release ก่อนหน้า (counter-2569-10-16)
#
# ใช้ (รันบนเซิร์ฟเวอร์):
#   cd /home/ubuntu/grad-programs-2569-10-27 && ./rollback_backend.sh
#
# ย้อนด้วยการสลับ compose override กลับไปตรึงอิมเมจเดิม
# **ไม่ลบอิมเมจใหม่** เผื่อต้อง deploy ซ้ำจะได้ไม่ต้อง build ใหม่
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REL=/home/ubuntu/release-level-2569-10-27
OLD_IMAGE=course-advisor-system-backend:counter-2569-10-16
PROJ=/home/ubuntu/course-advisor-system

die() { echo "** ล้มเหลว: $* **" >&2; exit 1; }

docker image inspect "$OLD_IMAGE" >/dev/null 2>&1 || die "ไม่พบอิมเมจเดิม $OLD_IMAGE"
[ -f "$REL/compose.rollback-backend-counter.yml" ] || die "ไม่พบไฟล์ rollback ใน $REL"

echo "จะย้อน backend กลับเป็น $OLD_IMAGE"
printf 'พิมพ์ YES เพื่อยืนยัน: '
read -r ok
[ "$ok" = "YES" ] || die "ยกเลิกแล้ว"

ARGS=$(cat "$HERE/compose-args.txt")
# shellcheck disable=SC2086
docker compose $ARGS -f "$REL/compose.rollback-backend-counter.yml" up -d --no-build --no-deps backend

sleep 5
now=$(docker inspect course-advisor-system-backend-1 --format '{{.Config.Image}}')
echo "อิมเมจที่รันอยู่ : $now"
[ "$now" = "$OLD_IMAGE" ] || die "ยังไม่กลับเป็นอิมเมจเดิม"

code=$(curl -s -o /dev/null -w '%{http_code}' https://stpnru-advisor.duckdns.org/api/health || true)
echo "/api/health -> $code"

echo
echo "ย้อน backend เรียบร้อย"
echo
echo "ผลที่ตามมา — พฤติกรรมกลับไปเป็นแบบเดิม"
echo "  · ถามโดยไม่ระบุระดับ จะไม่ถูกถามกลับ แต่ตกไปเส้นทางเอกสารที่ค้นจากทั้งสองเล่ม"
echo "  · /compare-courses จะเลือกเล่มเดียวให้ทั้งสองคอลัมน์ เมื่อเทียบโทกับเอกของสาขาเดียวกัน"
echo "  ถ้าข้อมูลหลักสูตรโท-เอกขึ้น production แล้ว ควรย้อนข้อมูลด้วย:"
echo "     ./rollback_data.sh --db course_advisor --run <โฟลเดอร์ของ deploy_data.sh>"
