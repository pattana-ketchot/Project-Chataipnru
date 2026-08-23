#!/usr/bin/env bash
# สลับผู้ให้บริการโมเดลที่ใช้เขียนคำตอบ แล้วเปิด backend ใหม่
#
#   bash scripts/set_llm_provider.sh gemini    # ใช้ Gemini (จะถามหา API key)
#   bash scripts/set_llm_provider.sh ollama    # กลับไปใช้โมเดลในเครื่อง
#
# ตัว API key รับผ่านการพิมพ์ตอนรัน ไม่ใช่ผ่าน argument โดยตั้งใจ เพราะ argument
# จะถูกบันทึกลง ~/.bash_history และมองเห็นได้จาก `ps` ของผู้ใช้อื่นบนเครื่องเดียวกัน
set -euo pipefail

cd "$(dirname "$0")/.."
COMPOSE="docker compose -f docker-compose.prod.yml"
PROVIDER="${1:-}"

if [ "$PROVIDER" != "gemini" ] && [ "$PROVIDER" != "ollama" ]; then
    echo "ใช้: bash scripts/set_llm_provider.sh [gemini|ollama]" >&2
    exit 1
fi

[ -f .env ] || { echo "ไม่พบไฟล์ .env" >&2; exit 1; }

# เขียนค่าลง .env: แทนที่บรรทัดเดิมถ้ามี ไม่งั้นต่อท้าย
set_env() {
    local key="$1" value="$2"
    if grep -q "^${key}=" .env; then
        # ใช้ | เป็นตัวคั่นเพราะค่าที่ใส่อาจมี / อยู่ข้างใน
        sed -i "s|^${key}=.*|${key}=${value}|" .env
    else
        printf '%s=%s\n' "$key" "$value" >> .env
    fi
}

if [ "$PROVIDER" = "gemini" ]; then
    # -s ปิดการแสดงผลตอนพิมพ์ กันคนที่มองจอข้างๆ เห็นคีย์
    printf 'วาง GEMINI_API_KEY แล้วกด Enter (จะไม่แสดงบนจอ): '
    read -rs GEMINI_KEY
    echo

    # ตัดช่องว่างและอักขระขึ้นบรรทัดใหม่ที่ติดมากับการวาง
    #
    # จำเป็นเพราะการคัดลอกจากเบราว์เซอร์บน Windows มัก
    # พ่วง CR (\r) มาด้วย ซึ่งใส่ลงหัวข้อความ HTTP ไม่ได้ตามข้อกำหนดของโปรโตคอล
    # อาการที่ได้คือ 401 จาก Google ซึ่งชี้ไปผิดทางว่าคีย์ไม่ถูกต้อง
    GEMINI_KEY=$(printf '%s' "$GEMINI_KEY" | tr -d '[:space:]')

    [ -n "$GEMINI_KEY" ] || { echo "ไม่ได้ใส่คีย์ ยกเลิก" >&2; exit 1; }

    # ไม่ตรวจรูปร่างของคีย์ ให้ Google เป็นคนตัดสินอย่างเดียว
    #
    # เคยใส่เงื่อนไขว่าต้องขึ้นต้นด้วย "AIza" ซึ่งเป็นรูปแบบเก่า ปัจจุบัน AI Studio
    # ออกคีย์ที่ขึ้นต้นด้วย "AQ." ด้วย คำเตือนนั้นจึงชี้ผิดและทำให้เข้าใจว่าคีย์ที่ถูก
    # เป็นคีย์ผิด การยิงทดสอบจริงข้างล่างตอบได้แม่นกว่าและไม่ล้าสมัยตามรูปแบบคีย์

    # ทดสอบกับ Google ก่อนบันทึก จะได้รู้ผลทันทีแทนที่จะไปเจอตอนผู้ใช้ถามคำถาม
    echo "กำลังตรวจสอบคีย์กับ Google..."
    HTTP_CODE=$(curl -s -o /tmp/gemini_check.$$ -w '%{http_code}' -m 20 \
        -H "x-goog-api-key: $GEMINI_KEY" \
        "https://generativelanguage.googleapis.com/v1beta/models" || echo 000)
    if [ "$HTTP_CODE" != "200" ]; then
        echo "คีย์ใช้ไม่ได้ (Google ตอบรหัส $HTTP_CODE) — ไม่ได้บันทึกอะไรลงไฟล์" >&2
        # ตัดข้อความออกมาเฉพาะบรรทัด message ไม่พ่นคำตอบทั้งก้อนซึ่งอาจมีคีย์ปนอยู่
        grep -o '"message"[^,]*' /tmp/gemini_check.$$ 2>/dev/null | head -1 >&2 || true
        rm -f /tmp/gemini_check.$$
        echo "" >&2
        echo "คัดลอกคีย์ด้วยปุ่มคัดลอกที่ https://aistudio.google.com/apikey" >&2
        echo "ถ้ายังไม่ผ่าน ให้วางลงโปรแกรมแก้ข้อความก่อนเพื่อดูว่าคลิปบอร์ดมีค่าที่ถูกจริง" >&2
        exit 1
    fi
    rm -f /tmp/gemini_check.$$
    echo "คีย์ใช้งานได้"

    set_env GEMINI_API_KEY "$GEMINI_KEY"
    set_env GEMINI_MODEL "${GEMINI_MODEL:-gemini-2.5-flash}"
    set_env LLM_PROVIDER gemini
    chmod 600 .env
    echo "ตั้งให้ใช้ Gemini แล้ว"
else
    set_env LLM_PROVIDER ollama
    echo "ตั้งให้ใช้โมเดลในเครื่องแล้ว"
    echo "หมายเหตุ: คีย์เดิมยังอยู่ใน .env ลบเองได้ถ้าไม่ใช้แล้ว"
fi

echo "กำลังเปิด backend ใหม่..."
$COMPOSE up -d backend

# รอให้พร้อมก่อนบอกว่าสำเร็จ ไม่งั้นผู้ใช้จะเปิดเว็บตอนที่ยังไม่ทันขึ้น
for _ in $(seq 1 20); do
    if curl -fs -m 5 http://localhost/api/health >/dev/null 2>&1; then
        echo "พร้อมใช้งาน — ลองถามคำถามได้ที่หน้าเว็บ"
        exit 0
    fi
    sleep 3
done

echo "backend ยังไม่ตอบ ตรวจ log ด้วย:" >&2
echo "  $COMPOSE logs backend --tail 30" >&2
exit 1
