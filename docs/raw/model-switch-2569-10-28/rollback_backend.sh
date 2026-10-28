#!/usr/bin/env bash
#
# ย้อน backend กลับเป็นอิมเมจของ release 28 ต.ค. (followup-2569-10-28)
#
# ใช้ (รันบนเซิร์ฟเวอร์):
#   cd /home/ubuntu/switch-release-2569-10-28 && ./rollback_backend.sh
#
# ย้อนด้วยการสลับ compose override กลับไปตรึงอิมเมจเดิม
# **ไม่ลบอิมเมจใหม่** เผื่อต้อง deploy ซ้ำจะได้ไม่ต้อง build ใหม่
#
# ย้อน backend แล้ว **ไม่จำเป็นต้องย้อนฐาน** คอลัมน์ provider ที่เพิ่มไว้เป็นคอลัมน์
# ที่โค้ดเก่าไม่รู้จัก มันจึงอยู่เฉย ๆ ได้โดยไม่กระทบอะไร (ดู rollback_db.sh ถ้าจะเอาออก)
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REL=/home/ubuntu/release-switch-2569-10-28
OLD_IMAGE=course-advisor-system-backend:followup-2569-10-28
PG=course-advisor-system-postgres-1

die() { echo "** ล้มเหลว: $* **" >&2; exit 1; }

docker image inspect "$OLD_IMAGE" >/dev/null 2>&1 || die "ไม่พบอิมเมจเดิม $OLD_IMAGE"
[ -f "$REL/compose.rollback-backend-followup.yml" ] || die "ไม่พบไฟล์ rollback ใน $REL"

echo "จะย้อน backend กลับเป็น $OLD_IMAGE"
printf 'พิมพ์ YES เพื่อยืนยัน: '
read -r ok
[ "$ok" = "YES" ] || die "ยกเลิกแล้ว"

ARGS=$(cat "$HERE/compose-args.txt")
# shellcheck disable=SC2086
docker compose $ARGS -f "$REL/compose.rollback-backend-followup.yml" \
  up -d --no-build --no-deps backend

sleep 5
now=$(docker inspect course-advisor-system-backend-1 --format '{{.Config.Image}}')
echo "อิมเมจที่รันอยู่ : $now"
[ "$now" = "$OLD_IMAGE" ] || die "ยังไม่กลับเป็นอิมเมจเดิม"

code=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/health || true)
echo "/health -> $code"
[ "$code" = "200" ] || die "health ไม่ใช่ 200 หลังย้อน — ต้องดูด้วยมือ"
site=$(curl -s -o /dev/null -w '%{http_code}' https://stpnru-advisor.duckdns.org/ || true)
echo "หน้าแรกของเว็บจริง -> $site"

echo
echo "ย้อน backend เรียบร้อย"
echo
echo "ผลที่ตามมา — พฤติกรรมกลับไปเป็นแบบก่อนรอบนี้"
echo "  · หน้าตั้งค่า AI จะบันทึกได้เหมือนเดิม แต่ค่าที่บันทึกไม่ถูกนำไปใช้อีกครั้ง"
echo "    โมเดลที่เขียนคำตอบจะกลับไปมาจาก env (LLM_PROVIDER / GEMINI_MODEL) เท่านั้น"
echo "  · ถ้าหน้าเว็บรุ่นใหม่ขึ้นไปแล้ว ให้ย้อนหน้าเว็บด้วย (./rollback_web.sh --run ...)"
echo "    เพราะหน้ารุ่นใหม่ส่งช่อง provider และเรียกเส้นทาง /ai-settings/check ที่โค้ดเก่าไม่มี"
echo "  · ไม่ต้องย้อนข้อมูลหลักสูตร — release นี้ไม่แตะข้อมูลหลักสูตรเลย"
echo
echo "  ค่าในตารางตั้งค่า (คอลัมน์ provider ยังอยู่ แต่ไม่มีใครอ่าน):"
URL=$(grep -E '^DATABASE_URL=' /home/ubuntu/course-advisor-system/.env | head -1 | cut -d= -f2-)
docker exec "$PG" psql "${URL/postgresql+psycopg/postgresql}" \
  -c "select id, provider, model from web.ai_settings" || true
