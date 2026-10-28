#!/usr/bin/env bash
#
# ชุดสวิตช์เลือกโมเดล — ส่วนหน้าเว็บ (หน้าตั้งค่า AI ของผู้ดูแล)
#
# ใช้ (รันบนเซิร์ฟเวอร์):
#   cd /home/ubuntu/switch-release-2569-10-28 && ./deploy_web.sh
#
# ลำดับสำคัญ — วาง assets ให้ครบ ตรวจด้วย SHA-256 ว่าเว็บเสิร์ฟไฟล์ถูกตัวจริง
# แล้วค่อยสลับ index.html เป็นขั้นสุดท้าย
#
# ถ้าสลับ index.html ก่อน คนที่เปิดเว็บช่วงนั้นจะได้หน้าที่ชี้ไปไฟล์ที่ยังไม่มี = จอขาว
#
# **ตรวจด้วย hash ไม่ใช่แค่ HTTP 200** เพราะ 200 บอกแค่ว่ามีไฟล์ตอบมา
# ไม่ได้บอกว่าเนื้อไฟล์ถูกต้อง — ไฟล์ที่คัดลอกไม่ครบ หรือของรุ่นก่อนที่ชื่อชนกัน
# ก็ตอบ 200 ได้เหมือนกัน
#
# bundle เก่าไม่ถูกลบ เพราะ rollback คือการสลับ index.html กลับไปชี้ของเดิม
set -euo pipefail

WEB=/home/ubuntu/course-advisor-system/web
SITE=https://stpnru-advisor.duckdns.org
HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="$HERE/web-release"
OUT="$HERE/web-run-$(date +%Y%m%d-%H%M%S)"

die() { echo "** ล้มเหลว: $* **" >&2; exit 1; }

[ -d "$SRC/assets" ]      || die "ไม่พบ $SRC/assets"
[ -f "$SRC/index.html" ]  || die "ไม่พบ $SRC/index.html"
[ -s "$SRC/SHA256SUMS" ]  || die "ไม่พบ $SRC/SHA256SUMS"
[ -d "$WEB" ]             || die "ไม่พบ $WEB"

mkdir -p "$OUT"
echo "บันทึกผลไว้ที่ $OUT"

# ── 0. ไฟล์ที่จะนำขึ้น ต้องตรงกับที่ตรวจไว้ตอน build ────────────────────
echo
echo "[0/6] ตรวจไฟล์ในชุด release ด้วย SHA-256"
( cd "$SRC" && sha256sum -c SHA256SUMS ) | tee "$OUT/release-verify.txt"
grep -q 'FAILED' "$OUT/release-verify.txt" && die "ไฟล์ในชุด release ไม่ตรงกับที่บันทึกไว้"

# ── 1. สำรองหน้าเว็บเดิม ───────────────────────────────────────────────
echo
echo "[1/6] สำรอง index.html เดิม"
cp "$WEB/index.html" "$OUT/index.html.before"
sha256sum "$OUT/index.html.before" | tee "$OUT/before.sha256"
grep -oE 'assets/index-[^"]+' "$OUT/index.html.before" | tee "$OUT/before-bundles.txt"
ls -la "$WEB/assets" > "$OUT/assets-before.txt"

# ── 2. bundle เดิมต้องยังอยู่ และเนื้อไฟล์ต้องไม่เพี้ยน (ไว้ใช้ rollback) ─
echo
echo "[2/6] ตรวจ bundle เดิมที่ rollback ต้องใช้"
while read -r rel; do
  [ -f "$WEB/$rel" ] || die "ไม่พบ $WEB/$rel — ถ้าหายจะ rollback ไม่ได้"
  sum=$(sha256sum "$WEB/$rel" | cut -d' ' -f1)
  echo "  $rel  $sum"
  echo "$sum  $rel" >> "$OUT/before-bundles.sha256"
done < "$OUT/before-bundles.txt"

# ── 3. วาง assets ใหม่ (ยังไม่แตะ index.html) ───────────────────────────
echo
echo "[3/6] วางไฟล์ assets ใหม่"
for f in "$SRC/assets"/*; do
  name="$(basename "$f")"
  want=$(sha256sum "$f" | cut -d' ' -f1)
  if [ -e "$WEB/assets/$name" ]; then
    have=$(sha256sum "$WEB/assets/$name" | cut -d' ' -f1)
    if [ "$have" = "$want" ]; then
      echo "  ข้าม $name (มีอยู่แล้วและ hash ตรง)"
      continue
    fi
    # ชื่อเดียวกันแต่เนื้อต่าง = ของเดิมเพี้ยนหรือเป็นคนละ build ต้องหยุดให้คนดู
    die "$name มีอยู่แล้วแต่เนื้อไฟล์ไม่ตรง (บนเครื่อง $have / ชุดนี้ $want)"
  fi
  cp "$f" "$WEB/assets/.$name.tmp"
  mv "$WEB/assets/.$name.tmp" "$WEB/assets/$name"
  got=$(sha256sum "$WEB/assets/$name" | cut -d' ' -f1)
  [ "$got" = "$want" ] || die "คัดลอก $name แล้ว hash ไม่ตรง ($got)"
  echo "  วาง $name  $got"
done

# ── 4. ไฟล์ที่เว็บเสิร์ฟจริง ต้อง hash ตรงกับที่เพิ่งวาง ─────────────────
echo
echo "[4/6] ดึงไฟล์ผ่านเว็บจริงมาตรวจ hash"
for f in "$SRC/assets"/*; do
  name="$(basename "$f")"
  want=$(sha256sum "$f" | cut -d' ' -f1)
  code=$(curl -s -o "$OUT/served-$name" -w '%{http_code}' "$SITE/assets/$name")
  [ "$code" = "200" ] || die "โหลด $name ไม่ได้ (HTTP $code) ยังไม่สลับ index.html"
  got=$(sha256sum "$OUT/served-$name" | cut -d' ' -f1)
  echo "  $name  HTTP $code  $got"
  [ "$got" = "$want" ] || die "เว็บเสิร์ฟ $name ด้วยเนื้อไฟล์คนละตัว ($got) ยังไม่สลับ index.html"
done

# ── 5. สลับ index.html เป็นขั้นสุดท้าย ─────────────────────────────────
echo
echo "[5/6] สลับ index.html"
# เขียนไฟล์ชั่วคราวแล้ว mv เพื่อให้การสลับเป็นจังหวะเดียว
# ถ้า cp ทับตรง ๆ คนที่โหลดพอดีจังหวะนั้นอาจได้ไฟล์ครึ่งเดียว
cp "$SRC/index.html" "$WEB/.index.html.new"
mv "$WEB/.index.html.new" "$WEB/index.html"
sha256sum "$WEB/index.html" | tee "$OUT/after.sha256"

# ── 6. ตรวจว่าเว็บเสิร์ฟ index.html ตัวใหม่จริง ────────────────────────
echo
echo "[6/6] ตรวจหน้าแรกที่เว็บเสิร์ฟ"
sleep 1
code=$(curl -s -o "$OUT/served-index.html" -w '%{http_code}' "$SITE/")
echo "  หน้าแรก -> HTTP $code"
[ "$code" = "200" ] || die "หน้าแรกตอบ $code"

want_sum=$(sha256sum "$SRC/index.html" | cut -d' ' -f1)
got_sum=$(sha256sum "$OUT/served-index.html" | cut -d' ' -f1)
echo "  hash ที่คาด : $want_sum"
echo "  hash ที่ได้  : $got_sum"
[ "$want_sum" = "$got_sum" ] || die "หน้าแรกที่เสิร์ฟไม่ใช่ไฟล์ของ release นี้ (อาจติดแคช) ดู $OUT/served-index.html"

grep -oE 'assets/index-[^"]+' "$OUT/served-index.html" | tee "$OUT/after-bundles.txt"

echo
echo "สำเร็จ"
echo "  ย้อนกลับด้วย : ./rollback_web.sh --run $OUT"
