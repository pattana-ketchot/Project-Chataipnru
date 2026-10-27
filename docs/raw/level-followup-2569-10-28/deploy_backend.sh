#!/usr/bin/env bash
#
# ต่อบริบทเมื่อผู้ใช้ตอบแค่ระดับปริญญา — ส่วน backend
#
# ใช้ (รันบนเซิร์ฟเวอร์):
#   cd /home/ubuntu/level-followup-2569-10-28 && ./deploy_backend.sh
#
# วิธี: build อิมเมจใหม่โดย **ซ้อนไฟล์ทับอิมเมจที่ production ใช้อยู่** (level-2569-10-27)
# ไม่ build จากซอร์สทั้งก้อน เพราะที่ทำงานยังมีงานค้างที่ไม่ได้อยู่ใน production
#
# **scp ไฟล์แล้ว restart ไม่พอ** คอนเทนเนอร์รันโค้ดจากในอิมเมจ ต้อง build ใหม่
# และต้องตรวจในคอนเทนเนอร์จริงว่าได้โค้ดใหม่แล้ว
#
# release นี้ **ไม่แตะข้อมูลและไม่แตะหน้าเว็บ** มีแต่ backend
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="$HERE/backend-release"
REL=/home/ubuntu/release-followup-2569-10-28
BASE_IMAGE=course-advisor-system-backend:level-2569-10-27
NEW_IMAGE=course-advisor-system-backend:followup-2569-10-28
PROJ=/home/ubuntu/course-advisor-system
OUT="$HERE/backend-run-$(date +%Y%m%d-%H%M%S)"

die() { echo "** ล้มเหลว: $* **" >&2; exit 1; }

[ -d "$SRC/files" ]      || die "ไม่พบ $SRC/files"
[ -f "$SRC/Dockerfile" ] || die "ไม่พบ $SRC/Dockerfile"
mkdir -p "$OUT"
echo "บันทึกผลไว้ที่ $OUT"

# ── 0. ไฟล์ที่จะซ้อน ต้องตรงกับที่ตรวจไว้ ──────────────────────────────
echo
echo "[0/6] ตรวจไฟล์ในชุดด้วย SHA-256"
( cd "$SRC" && sha256sum -c SHA256SUMS ) | tee "$OUT/files-verify.txt"
grep -q 'FAILED' "$OUT/files-verify.txt" && die "ไฟล์ในชุดไม่ตรงกับที่บันทึกไว้"

# ── 1. อิมเมจฐานต้องเป็นตัวที่รันอยู่จริง ───────────────────────────────
echo
echo "[1/6] ตรวจอิมเมจฐาน"
running=$(docker inspect course-advisor-system-backend-1 --format '{{.Config.Image}}')
echo "  อิมเมจที่รันอยู่      : $running"
echo "  อิมเมจฐานที่จะซ้อนทับ : $BASE_IMAGE"
[ "$running" = "$BASE_IMAGE" ] || die "อิมเมจที่รันอยู่ไม่ตรงกับฐานที่ชุดนี้ซ้อนไว้ — ต้องสร้างชุดใหม่จากอิมเมจที่รันจริง"
docker inspect "$BASE_IMAGE" --format '{{.Id}}' | tee "$OUT/base-image-id.txt"

# ── 2. build อิมเมจใหม่ ────────────────────────────────────────────────
echo
echo "[2/6] build อิมเมจ $NEW_IMAGE"
mkdir -p "$REL"
cp -r "$SRC"/. "$REL"/
docker build -t "$NEW_IMAGE" "$REL" 2>&1 | tail -10 | tee "$OUT/build.log"
docker inspect "$NEW_IMAGE" --format '{{.Id}}' | tee "$OUT/new-image-id.txt"

# ── 3. ตรวจว่าไฟล์ในอิมเมจใหม่คือไฟล์ของเราจริง ─────────────────────────
echo
echo "[3/6] ตรวจ hash ของไฟล์ที่อยู่ในอิมเมจใหม่"
check_in_image() {
  want=$(sha256sum "$SRC/files/$1" | cut -d' ' -f1)
  got=$(docker run --rm --entrypoint sha256sum "$NEW_IMAGE" "$2" | cut -d' ' -f1)
  echo "  $2"
  echo "     คาด $want"
  echo "     ได้  $got"
  [ "$want" = "$got" ] || die "ไฟล์ $2 ในอิมเมจไม่ตรงกับชุดที่ตรวจไว้"
}
check_in_image course_scope.py /app/backend/app/services/course_scope.py
check_in_image follow_up.py    /app/backend/app/services/follow_up.py

# ── 4. รันชุดทดสอบในอิมเมจใหม่ บนฐานทดสอบ ก่อนสลับ production ──────────
echo
echo "[4/6] รันชุดทดสอบในอิมเมจใหม่ (ฐานทดสอบ)"
URL=$(grep -E "^DATABASE_URL=" "$PROJ/.env" | head -1 | cut -d= -f2-)
TESTURL=$(echo "$URL" | sed "s|/course_advisor$|/course_advisor_test|")
for t in test_level_followup_answer test_level_clarify_followup test_compare_degree_level test_degree_level_and_gate_order; do
  echo "  --- $t ---"
  docker run --rm --network course-advisor-system_default \
    --env-file "$PROJ/.env" -e DATABASE_URL="$TESTURL" \
    -e PYTHONPATH=/app/backend -w /app/backend \
    --entrypoint python "$NEW_IMAGE" "tests/$t.py" 2>&1 | tee "$OUT/$t.log" | tail -3
  grep -qE 'ผ่านทั้ง|ผ่านทั้งหมด' "$OUT/$t.log" || die "$t ไม่ผ่าน ดู $OUT/$t.log"
done

# ── 5. สลับ production ────────────────────────────────────────────────
echo
echo "[5/6] สลับอิมเมจของ production"
echo "*** กำลังจะ restart backend ของ production ***"
printf 'พิมพ์ YES เพื่อยืนยัน: '
read -r ok
[ "$ok" = "YES" ] || die "ยกเลิกแล้ว"

ARGS=$(cat "$HERE/compose-args.txt")

# --no-deps = แตะเฉพาะ backend ไม่ไปสร้าง/รีสตาร์ต postgres ollama caddy frontend webapi
UPARGS="up -d --no-build --no-deps backend"

echo "  --- dry-run: ดูว่าจะแตะบริการใดบ้าง ---"
# shellcheck disable=SC2086
docker compose $ARGS -f "$REL/compose.pin-backend-followup.yml" $UPARGS --dry-run 2>&1 | tee "$OUT/compose-dryrun.log"
for other in postgres ollama caddy frontend webapi; do
  if grep -qiE "course-advisor-system-${other}-1" "$OUT/compose-dryrun.log"; then
    die "dry-run บอกว่าจะแตะบริการ $other ด้วย — หยุดก่อน"
  fi
done
echo "  dry-run: ไม่แตะบริการอื่น"

# shellcheck disable=SC2086
docker compose $ARGS -f "$REL/compose.pin-backend-followup.yml" $UPARGS 2>&1 | tee "$OUT/compose-up.log"

# ── 6. ตรวจว่าคอนเทนเนอร์ที่รันอยู่ได้โค้ดใหม่จริง ──────────────────────
echo
echo "[6/6] ตรวจในคอนเทนเนอร์ที่รันจริง"
sleep 5
now=$(docker inspect course-advisor-system-backend-1 --format '{{.Config.Image}}')
echo "  อิมเมจที่รันอยู่ : $now"
[ "$now" = "$NEW_IMAGE" ] || die "คอนเทนเนอร์ยังใช้อิมเมจเดิม"

# เทียบ hash ในคอนเทนเนอร์กับค่าที่คาดจริง ไม่ใช่แค่พิมพ์ออกมาให้ดู
# **ห้ามใช้ไพป์ไป tee** เพราะ die ในไพป์ทำงานในซับเชลล์ สคริปต์จะไม่หยุดจริง
: > "$OUT/in-container.sha256"
check_in_container() {
  want=$(sha256sum "$SRC/files/$1" | cut -d' ' -f1)
  # $2 เป็นพาธเต็มในคอนเทนเนอร์อยู่แล้ว ห้ามเติม /app/backend ซ้ำ
  got=$(docker exec course-advisor-system-backend-1 sha256sum "$2" | cut -d' ' -f1)
  printf '%s  %s\n' "$got" "$2" >> "$OUT/in-container.sha256"
  echo "  $2"
  echo "     คาด $want"
  echo "     ได้  $got"
  [ "$want" = "$got" ] || die "คอนเทนเนอร์ที่รันอยู่ใช้ไฟล์ $2 คนละตัวกับชุดที่ตรวจไว้"
}
check_in_container course_scope.py /app/backend/app/services/course_scope.py
check_in_container follow_up.py    /app/backend/app/services/follow_up.py

# health ต้องเป็น 200 จริง ไม่ใช่พิมพ์ค่าแล้วบอกว่าสำเร็จต่อ
# ลองซ้ำเพราะคอนเทนเนอร์เพิ่งเริ่ม แต่ถ้าครบแล้วยังไม่ 200 ต้องหยุดและให้ย้อนกลับ
code=""
for i in $(seq 1 20); do
  code=$(curl -s -o /dev/null -w '%{http_code}' https://stpnru-advisor.duckdns.org/api/health || true)
  [ "$code" = "200" ] && break
  sleep 2
done
echo "  /api/health -> ${code:-ไม่ตอบ}"
[ "$code" = "200" ] || die "health check ไม่ใช่ 200 (ได้ ${code:-ไม่ตอบ}) — ย้อนกลับด้วย ./rollback_backend.sh"

echo
echo "สำเร็จ"
echo "  ย้อนกลับด้วย : ./rollback_backend.sh"
