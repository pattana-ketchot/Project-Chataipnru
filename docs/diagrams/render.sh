#!/bin/bash
# สร้างภาพจากไฟล์ .puml ทุกไฟล์ในโฟลเดอร์นี้
#
#   bash render.sh            สร้างทั้ง PNG และ SVG
#   bash render.sh png        เฉพาะ PNG
#
# ใช้ kroki.io เพราะ planttext.com และ plantuml.com **ไม่มีฟอนต์ไทย**
# (ทดสอบ 19 ต.ค. 2569: plantuml.com ขึ้นกล่องเปล่าทั้งหมด ·
#  planttext.com พยัญชนะขึ้นแต่สระและวรรณยุกต์กลายเป็นกล่อง)
set -u
FORMATS="${1:-png svg}"
for f in *.puml; do
  for fmt in $FORMATS; do
    out="${f%.puml}.$fmt"
    code=$(curl -sS -X POST -H "Content-Type: text/plain" --data-binary "@$f" \
                 -o "$out" -w "%{http_code}" "https://kroki.io/plantuml/$fmt")
    if [ "$code" = "200" ]; then
      printf "  %-28s -> %-28s %s ไบต์\n" "$f" "$out" "$(stat -c %s "$out")"
    else
      printf "  %-28s -> ล้มเหลว (http %s): %s\n" "$f" "$code" "$(head -c 200 "$out")"
      rm -f "$out"
    fi
  done
done
