#!/usr/bin/env bash
#
# ย้อนหน้าเว็บกลับเป็นรุ่นก่อน deploy
#
# ใช้ (รันบนเซิร์ฟเวอร์):
#   ./rollback_web.sh --run /home/ubuntu/switch-release-2569-10-28/web-run-YYYYmmdd-HHMMSS
#
# คืนเฉพาะ index.html ที่สำรองไว้ ซึ่งชี้ไป bundle ชุดเดิมที่ยังอยู่ใน assets
# **ไม่ลบไฟล์ assets ของรุ่นใหม่** เพราะการลบไม่ช่วยอะไรและทำให้ deploy ซ้ำต้องอัปใหม่
set -euo pipefail

WEB=/home/ubuntu/course-advisor-system/web
SITE=https://stpnru-advisor.duckdns.org

die() { echo "** ล้มเหลว: $* **" >&2; exit 1; }

RUN=""
while [ $# -gt 0 ]; do
  case "$1" in
    --run) RUN="${2:-}"; shift 2 ;;
    *) die "ไม่รู้จักตัวเลือก $1" ;;
  esac
done
[ -n "$RUN" ] || die "ต้องระบุ --run (โฟลเดอร์ที่ deploy_web.sh สร้าง)"
SAVED="$RUN/index.html.before"
[ -s "$SAVED" ] || die "ไม่พบ $SAVED"

echo "จะคืน index.html จาก $SAVED"
echo "ไฟล์นั้นชี้ไป:"
grep -oE 'assets/index-[^"]+' "$SAVED" | sed 's/^/  /'

# bundle ที่ไฟล์สำรองชี้ ต้องยังอยู่จริง ไม่งั้นคืนไปแล้วเว็บขาว
while read -r rel; do
  [ -f "$WEB/$rel" ] || die "ไม่พบ $WEB/$rel — คืนไปแล้วเว็บจะขาว"
done < <(grep -oE 'assets/index-[^"]+' "$SAVED")

cp "$SAVED" "$WEB/.index.html.rb"
mv "$WEB/.index.html.rb" "$WEB/index.html"

sleep 1
code=$(curl -s -o /tmp/rb-index.html -w '%{http_code}' "$SITE/")
echo "หน้าแรก -> HTTP $code"
[ "$code" = "200" ] || die "หน้าแรกตอบ $code"

want=$(grep -oE 'assets/index-[^"]+' "$SAVED" | sort)
got=$(grep -oE 'assets/index-[^"]+' /tmp/rb-index.html | sort)
[ "$want" = "$got" ] || die "หน้าแรกยังไม่ใช่รุ่นเดิม"

echo
echo "ย้อนหน้าเว็บเรียบร้อย"
echo
echo "ถ้าต้องการกลับทั้งชุด ย้อนข้อมูลด้วย:"
echo "  ./rollback_data.sh --db course_advisor --run <โฟลเดอร์ของ deploy_data.sh>"
echo
echo "ลำดับเลือกตามสาเหตุที่ต้องย้อน — ทั้งสองลำดับไม่ทำให้เว็บพัง"
echo "  หน้าเว็บมีปัญหา  -> ย้อนหน้าเว็บก่อน (ที่เพิ่งทำ) แล้วค่อยย้อนข้อมูล"
echo "     ระหว่างทาง: เว็บรุ่นเก่า + ข้อมูลรุ่นใหม่ — เว็บเก่าไม่รู้จักช่องใหม่ จึงไม่แสดง"
echo "     แต่ยังเห็นหลักสูตรโท-เอกอยู่"
echo "  ข้อมูลมีปัญหา    -> ย้อนข้อมูลก่อน แล้วค่อยย้อนหน้าเว็บ"
echo "     ระหว่างทาง: เว็บรุ่นใหม่ + ข้อมูลรุ่นเก่า — หัวข้อคุณสมบัติหายไปเพราะไม่มีข้อมูล"
echo "     และกลับเหลือ 12 หลักสูตร"
