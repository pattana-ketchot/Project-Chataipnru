#!/usr/bin/env bash
#
# ขั้นที่ 2 ของ 3 — สวิตช์เลือกโมเดลจากหลังบ้าน ส่วน backend
#
# ใช้ (รันบนเซิร์ฟเวอร์):
#   cd /home/ubuntu/switch-release-2569-10-28 && ./deploy_backend.sh
#
# ต้องรัน ./deploy_db.sh มาก่อน (คอลัมน์ provider ต้องมีอยู่แล้ว)
#
# วิธี: build อิมเมจใหม่โดย **ซ้อนไฟล์ทับอิมเมจที่ production ใช้อยู่** (followup-2569-10-28)
# ไม่ build จากซอร์สทั้งก้อน เพราะที่ทำงานมีงานค้างที่ยังไม่ได้ปล่อยปนอยู่ — ดู Dockerfile
#
# **scp ไฟล์แล้ว restart ไม่พอ** คอนเทนเนอร์รันโค้ดจากในอิมเมจ ต้อง build ใหม่
# และต้องตรวจในคอนเทนเนอร์จริงว่าได้โค้ดใหม่แล้ว
#
# release นี้ **ไม่แตะข้อมูลหลักสูตรและไม่แตะหน้าเว็บ**
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="$HERE/backend-release"
REL=/home/ubuntu/release-switch-2569-10-28
BASE_IMAGE=course-advisor-system-backend:followup-2569-10-28
NEW_IMAGE=course-advisor-system-backend:switch-2569-10-28
PROJ=/home/ubuntu/course-advisor-system
PG=course-advisor-system-postgres-1
OUT="$HERE/backend-run-$(date +%Y%m%d-%H%M%S)"

die() { echo "** ล้มเหลว: $* **" >&2; exit 1; }

[ -d "$SRC/files" ]      || die "ไม่พบ $SRC/files"
[ -f "$SRC/Dockerfile" ] || die "ไม่พบ $SRC/Dockerfile"
mkdir -p "$OUT"
echo "บันทึกผลไว้ที่ $OUT"

# ── 0. ไฟล์ที่จะซ้อน ต้องตรงกับที่ตรวจไว้ ──────────────────────────────
echo
echo "[0/7] ตรวจไฟล์ในชุดด้วย SHA-256"
( cd "$SRC" && sha256sum -c SHA256SUMS ) > "$OUT/files-verify.txt" 2>&1
cat "$OUT/files-verify.txt"
grep -q 'FAILED' "$OUT/files-verify.txt" && die "ไฟล์ในชุดไม่ตรงกับที่บันทึกไว้"

# ── 1. ฐานข้อมูลต้องพร้อมแล้ว ─────────────────────────────────────────
echo
echo "[1/7] ตรวจว่า migration ขั้นที่ 1 ลงแล้ว"
URL=$(grep -E '^DATABASE_URL=' "$PROJ/.env" | head -1 | cut -d= -f2-)
PSQL_URL=${URL/postgresql+psycopg/postgresql}
TESTURL=${URL/\/course_advisor/\/course_advisor_test}
has=$(docker exec "$PG" psql "$PSQL_URL" -tAc \
  "select count(*) from information_schema.columns where table_schema='web'
    and table_name='ai_settings' and column_name='provider'")
echo "  คอลัมน์ provider ใน production = $has"
[ "$has" = "1" ] || die "ยังไม่มีคอลัมน์ provider — ต้องรัน ./deploy_db.sh ก่อน"

# ── 2. อิมเมจฐานต้องเป็นตัวที่รันอยู่จริง ───────────────────────────────
echo
echo "[2/7] ตรวจอิมเมจฐาน"
running=$(docker inspect course-advisor-system-backend-1 --format '{{.Config.Image}}')
echo "  อิมเมจที่รันอยู่      : $running"
echo "  อิมเมจฐานที่จะซ้อนทับ : $BASE_IMAGE"
[ "$running" = "$BASE_IMAGE" ] || die "อิมเมจที่รันอยู่ไม่ตรงกับฐานที่ชุดนี้ซ้อนไว้ — ต้องสร้างชุดใหม่จากอิมเมจที่รันจริง"
docker inspect "$BASE_IMAGE" --format '{{.Id}}' | tee "$OUT/base-image-id.txt"

# ── 3. build อิมเมจใหม่ ────────────────────────────────────────────────
echo
echo "[3/7] build อิมเมจ $NEW_IMAGE"
mkdir -p "$REL"
cp -r "$SRC"/. "$REL"/
docker build -t "$NEW_IMAGE" "$REL" 2>&1 | tail -12 | tee "$OUT/build.log"
docker inspect "$NEW_IMAGE" --format '{{.Id}}' | tee "$OUT/new-image-id.txt"

# ── 4. ตรวจว่าไฟล์ในอิมเมจใหม่คือไฟล์ของเราจริง ─────────────────────────
echo
echo "[4/7] ตรวจ hash ของไฟล์ที่อยู่ในอิมเมจใหม่"
check_in_image() {  # check_in_image <ไฟล์ใน files/> <path เต็มในอิมเมจ>
  want=$(sha256sum "$SRC/files/$1" | cut -d' ' -f1)
  got=$(docker run --rm --entrypoint sha256sum "$NEW_IMAGE" "$2" | cut -d' ' -f1)
  echo "  $2"
  echo "     คาด $want"
  echo "     ได้  $got"
  [ "$want" = "$got" ] || die "ไฟล์ $2 ในอิมเมจไม่ตรงกับชุดที่ตรวจไว้"
}
check_in_image ai_settings.py       /app/backend/app/services/ai_settings.py
check_in_image llm_client.py        /app/backend/app/services/llm_client.py
check_in_image chat_service.py      /app/backend/app/services/chat.py
check_in_image chat_schema.py       /app/backend/app/schemas/chat.py
check_in_image answer_cache.py      /app/backend/app/services/answer_cache.py
check_in_image site_admin.py        /app/backend/app/api/routes/site_admin.py
check_in_image main.py              /app/backend/app/main.py
check_in_image test_model_switch.py /app/backend/tests/test_model_switch.py
check_in_image test_llm_usage_counter.py /app/backend/tests/test_llm_usage_counter.py

# ── 5. รันชุดทดสอบในอิมเมจใหม่ บนฐานทดสอบ ก่อนสลับ production ──────────
echo
echo "[5/7] รันชุดทดสอบในอิมเมจใหม่ (ฐานทดสอบ ไม่ mount ไฟล์ใด)"
# ชุดที่ครอบส่วนที่รอบนี้แตะ: สวิตช์ · ตัวนับ · ตัวสำรองเมื่อเจ้าหลักล่ม ·
# รูปแบบ SSE และเพดานเวลาของการสตรีม (เพราะเพิ่มช่องในเหตุการณ์ done)
for t in test_model_switch test_llm_usage_counter test_gemini_overload_fallback \
         test_model_outage_n1 test_sse_format test_chatweb_stream_budget \
         test_request_budget; do
  echo "  --- $t ---"
  docker run --rm --network course-advisor-system_default \
    --env-file "$PROJ/.env" -e DATABASE_URL="$TESTURL" \
    -e PYTHONPATH=/app/backend -w /app/backend \
    --entrypoint python "$NEW_IMAGE" "tests/$t.py" > "$OUT/$t.log" 2>&1
  tail -3 "$OUT/$t.log"
  grep -qE 'ผ่านทั้งหมด|ผ่านทั้ง' "$OUT/$t.log" || die "$t ไม่ผ่าน ดู $OUT/$t.log"
done

# ── 6. สลับ production ────────────────────────────────────────────────
echo
echo "[6/7] สลับอิมเมจของ production"
echo "*** กำลังจะ restart backend ของ production ***"
printf 'พิมพ์ YES เพื่อยืนยัน: '
read -r ok
[ "$ok" = "YES" ] || die "ยกเลิกแล้ว"

ARGS=$(cat "$HERE/compose-args.txt")
UPARGS="up -d --no-build --no-deps backend"

echo "  --- dry-run: ดูว่าจะแตะบริการใดบ้าง ---"
# shellcheck disable=SC2086
docker compose $ARGS -f "$REL/compose.pin-backend-switch.yml" $UPARGS --dry-run 2>&1 \
  | tee "$OUT/compose-dryrun.log"
for other in postgres ollama caddy frontend webapi; do
  if grep -qiE "course-advisor-system-${other}-1" "$OUT/compose-dryrun.log"; then
    die "dry-run บอกว่าจะแตะบริการ $other ด้วย — หยุดก่อน"
  fi
done
echo "  dry-run: ไม่แตะบริการอื่น"

# shellcheck disable=SC2086
docker compose $ARGS -f "$REL/compose.pin-backend-switch.yml" $UPARGS 2>&1 \
  | tee "$OUT/compose-up.log"

# ── 7. ตรวจว่าคอนเทนเนอร์ที่รันอยู่ได้โค้ดใหม่จริง ──────────────────────
echo
echo "[7/7] ตรวจในคอนเทนเนอร์ที่รันจริง"
sleep 5
now=$(docker inspect course-advisor-system-backend-1 --format '{{.Config.Image}}')
echo "  อิมเมจที่รันอยู่ : $now"
[ "$now" = "$NEW_IMAGE" ] || die "คอนเทนเนอร์ยังใช้อิมเมจเดิม"

# เทียบ hash ในคอนเทนเนอร์กับค่าที่คาดจริง ไม่ใช่แค่พิมพ์ออกมาให้ดู
# **ห้ามใช้ไพป์ไป tee** เพราะ die ในไพป์ทำงานในซับเชลล์ สคริปต์จะไม่หยุดจริง
: > "$OUT/in-container.sha256"
check_in_container() {  # check_in_container <ไฟล์ใน files/> <path เต็ม>
  want=$(sha256sum "$SRC/files/$1" | cut -d' ' -f1)
  got=$(docker exec course-advisor-system-backend-1 sha256sum "$2" | cut -d' ' -f1)
  printf '%s  %s\n' "$got" "$2" >> "$OUT/in-container.sha256"
  echo "  $2 -> ${got:0:16}"
  [ "$want" = "$got" ] || die "ไฟล์ $2 ในคอนเทนเนอร์ไม่ตรงกับชุดที่ตรวจไว้"
}
check_in_container ai_settings.py  /app/backend/app/services/ai_settings.py
check_in_container llm_client.py   /app/backend/app/services/llm_client.py
check_in_container chat_service.py /app/backend/app/services/chat.py
check_in_container chat_schema.py  /app/backend/app/schemas/chat.py
check_in_container answer_cache.py /app/backend/app/services/answer_cache.py
check_in_container site_admin.py   /app/backend/app/api/routes/site_admin.py
check_in_container main.py         /app/backend/app/main.py

echo
echo "  health ของ backend:"
code=$(curl -s -o "$OUT/health.json" -w '%{http_code}' http://127.0.0.1:8000/health || true)
echo "    HTTP $code"
cat "$OUT/health.json" 2>/dev/null; echo
# หยุดเมื่อไม่ใช่ 200 แทนการพิมพ์ว่าสำเร็จต่อ
[ "$code" = "200" ] || die "health ไม่ใช่ 200 — ให้ย้อนด้วย ./rollback_backend.sh"

echo "  เว็บจริงยังตอบ:"
site=$(curl -s -o /dev/null -w '%{http_code}' https://stpnru-advisor.duckdns.org/ || true)
echo "    หน้าแรก HTTP $site"
[ "$site" = "200" ] || die "เว็บจริงไม่ตอบ 200 — ให้ย้อนด้วย ./rollback_backend.sh"

echo
echo "  ค่าที่ระบบใช้ตอบอยู่จริงตอนนี้ (ต้องยังเป็น env เพราะ provider ยัง NULL):"
docker exec "$PG" psql "$PSQL_URL" -c "select id, provider, model from web.ai_settings" \
  | tee "$OUT/ai-settings-after.txt"

echo
echo "เสร็จขั้นที่ 2 — ต่อด้วย ./deploy_web.sh"
echo "ถ้าต้องย้อน: ./rollback_backend.sh"
