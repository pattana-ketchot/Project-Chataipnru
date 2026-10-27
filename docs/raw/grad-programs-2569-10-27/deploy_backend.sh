#!/usr/bin/env bash
#
# ชุด GRAD_PROGRAMS — ส่วน backend (ด่านถามระดับ + การจับคู่เอกสารตามระดับ)
#
# ใช้ (รันบนเซิร์ฟเวอร์):
#   cd /home/ubuntu/grad-programs-2569-10-27 && ./deploy_backend.sh
#
# วิธี: build อิมเมจใหม่โดย **ซ้อนไฟล์ทับอิมเมจที่ production ใช้อยู่**
# ไม่ build จากซอร์สทั้งก้อน เพราะที่ทำงานมีงานค้างที่ยังไม่ผ่านการตรวจปนอยู่
#
# **scp ไฟล์แล้ว restart ไม่พอ** คอนเทนเนอร์รันโค้ดจากในอิมเมจ ต้อง build ใหม่
# และต้องตรวจในคอนเทนเนอร์จริงว่าได้โค้ดใหม่แล้ว
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="$HERE/backend-release"
REL=/home/ubuntu/release-level-2569-10-27
BASE_IMAGE=course-advisor-system-backend:counter-2569-10-16
NEW_IMAGE=course-advisor-system-backend:level-2569-10-27
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
echo "  อิมเมจที่รันอยู่ : $running"
echo "  อิมเมจฐานที่จะซ้อนทับ : $BASE_IMAGE"
[ "$running" = "$BASE_IMAGE" ] || die "อิมเมจที่รันอยู่ไม่ตรงกับฐานที่ชุดนี้ซ้อนไว้ — ต้องสร้างชุดใหม่จากอิมเมจที่รันจริง"
docker inspect "$BASE_IMAGE" --format '{{.Id}}' | tee "$OUT/base-image-id.txt"

# ── 2. build อิมเมจใหม่ ────────────────────────────────────────────────
echo
echo "[2/6] build อิมเมจ $NEW_IMAGE"
mkdir -p "$REL"
cp -r "$SRC"/. "$REL"/
docker build -t "$NEW_IMAGE" "$REL" 2>&1 | tail -15 | tee "$OUT/build.log"
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
check_in_image course_scope.py       /app/backend/app/services/course_scope.py
check_in_image chat.py               /app/backend/app/services/chat.py
check_in_image web_compat_service.py /app/backend/app/services/web_compat.py
check_in_image web_compat_route.py   /app/backend/app/api/routes/web_compat.py

# ── 4. รันชุดทดสอบในอิมเมจใหม่ บนฐานทดสอบ ก่อนสลับ production ──────────
echo
echo "[4/6] รันชุดทดสอบในอิมเมจใหม่ (ฐานทดสอบ)"
URL=$(grep -E "^DATABASE_URL=" "$PROJ/.env" | head -1 | cut -d= -f2-)
TESTURL=$(echo "$URL" | sed "s|/course_advisor$|/course_advisor_test|")
for t in test_compare_degree_level test_level_clarify_followup; do
  echo "  --- $t ---"
  docker run --rm --network course-advisor-system_default \
    --env-file "$PROJ/.env" -e DATABASE_URL="$TESTURL" \
    -e PYTHONPATH=/app/backend -w /app/backend \
    --entrypoint python "$NEW_IMAGE" "tests/$t.py" 2>&1 | tee "$OUT/$t.log" | tail -3
  grep -q 'ผ่านทั้ง' "$OUT/$t.log" || die "$t ไม่ผ่าน ดู $OUT/$t.log"
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
# ถ้าไม่ใส่ compose อาจแตะบริการที่ backend พึ่งพา ซึ่งไม่ได้อยู่ในขอบเขตของ release นี้
UPARGS="up -d --no-build --no-deps backend"

echo "  --- dry-run: ดูว่าจะแตะบริการใดบ้าง ---"
# shellcheck disable=SC2086
docker compose $ARGS -f "$REL/compose.pin-backend-level.yml" $UPARGS --dry-run 2>&1 | tee "$OUT/compose-dryrun.log"
# ชื่อคอนเทนเนอร์ของบริการอื่นต้องไม่โผล่ในผล dry-run
for other in postgres ollama caddy frontend webapi; do
  if grep -qiE "course-advisor-system-${other}-1" "$OUT/compose-dryrun.log"; then
    die "dry-run บอกว่าจะแตะบริการ $other ด้วย — หยุดก่อน"
  fi
done
echo "  dry-run: ไม่แตะบริการอื่น"

# shellcheck disable=SC2086
docker compose $ARGS -f "$REL/compose.pin-backend-level.yml" $UPARGS 2>&1 | tee "$OUT/compose-up.log"

# ── 6. ตรวจว่าคอนเทนเนอร์ที่รันอยู่ได้โค้ดใหม่จริง ──────────────────────
echo
echo "[6/6] ตรวจในคอนเทนเนอร์ที่รันจริง"
sleep 5
now=$(docker inspect course-advisor-system-backend-1 --format '{{.Config.Image}}')
echo "  อิมเมจที่รันอยู่ : $now"
[ "$now" = "$NEW_IMAGE" ] || die "คอนเทนเนอร์ยังใช้อิมเมจเดิม"

for f in app/services/course_scope.py app/services/chat.py \
         app/services/web_compat.py app/api/routes/web_compat.py; do
  got=$(docker exec course-advisor-system-backend-1 sha256sum "/app/backend/$f" | cut -d' ' -f1)
  echo "  $f  $got"
done | tee "$OUT/in-container.sha256"

code=$(curl -s -o /dev/null -w '%{http_code}' https://stpnru-advisor.duckdns.org/api/health || true)
echo "  /api/health -> $code"

echo
echo "สำเร็จ"
echo "  ย้อนกลับด้วย : ./rollback_backend.sh"
