#!/usr/bin/env bash
# ติดตั้งระบบบนเซิร์ฟเวอร์ Linux ที่เพิ่งสร้างใหม่ (ทดสอบกับ Oracle Cloud ARM)
#
#   bash scripts/setup_server.sh
#
# ทำอะไรบ้าง
#   1. ติดตั้ง Docker ถ้ายังไม่มี
#   2. เปิดพอร์ต 80 ใน iptables (Oracle ปิดไว้ทุกพอร์ตโดยค่าเริ่มต้น)
#   3. สร้าง .env พร้อมรหัสผ่านสุ่ม ถ้ายังไม่มี
#   4. build และเปิดระบบ
#   5. ดึงโมเดลลง Ollama
#
# ไม่ได้ทำให้: การกู้ข้อมูลหลักสูตร — ดูขั้นตอนใน docs/DEPLOY_ORACLE_CLOUD.md
# เพราะต้องอัปโหลดไฟล์สำรองจากเครื่องพัฒนาขึ้นมาก่อน
set -euo pipefail

cd "$(dirname "$0")/.."

step() { echo ""; echo "=== $* ==="; }

# ---------------------------------------------------------------- 1. Docker
step "1/5 ตรวจ Docker"
if command -v docker >/dev/null 2>&1; then
    echo "มี Docker อยู่แล้ว: $(docker --version)"
else
    echo "ยังไม่มี Docker กำลังติดตั้ง..."
    curl -fsSL https://get.docker.com | sudo sh
    # ให้ผู้ใช้ปัจจุบันสั่ง docker ได้โดยไม่ต้อง sudo
    sudo usermod -aG docker "$USER"
    echo ""
    echo "ติดตั้ง Docker เสร็จแล้ว — ต้อง logout แล้ว login ใหม่ก่อนใช้งานได้"
    echo "จากนั้นรันสคริปต์นี้อีกครั้ง"
    exit 0
fi

# ---------------------------------------------------------------- 2. firewall
step "2/5 เปิดพอร์ต 80"
# Oracle ใส่กฎ REJECT ไว้ใน iptables ของเครื่องเอง นอกเหนือจาก Security List
# ฝั่งคลาวด์ ถ้าเปิดแค่ฝั่งคลาวด์อย่างเดียวจะยังเข้าไม่ได้ และไม่มีข้อความบอก
if sudo iptables -C INPUT -p tcp --dport 80 -j ACCEPT 2>/dev/null; then
    echo "เปิดไว้แล้ว"
else
    # แทรกไว้บนสุดเพื่อให้มาก่อนกฎ REJECT ที่ Oracle ใส่ไว้
    sudo iptables -I INPUT 1 -p tcp --dport 80 -j ACCEPT
    if command -v netfilter-persistent >/dev/null 2>&1; then
        sudo netfilter-persistent save
    elif [ -d /etc/iptables ]; then
        sudo sh -c 'iptables-save > /etc/iptables/rules.v4'
    else
        echo "หมายเหตุ: บันทึกกฎถาวรไม่ได้ กฎจะหายเมื่อรีบูต"
        echo "ติดตั้ง iptables-persistent เพื่อให้กฎอยู่ถาวร"
    fi
    echo "เปิดพอร์ต 80 แล้ว"
fi
echo "อย่าลืมเปิด Ingress Rule พอร์ต 80 ใน Security List ฝั่ง Oracle ด้วย"

# ---------------------------------------------------------------- 3. .env
step "3/5 เตรียมไฟล์ตั้งค่า"
if [ -f .env ]; then
    echo "มี .env อยู่แล้ว ไม่เขียนทับ"
else
    gen() { head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n'; }
    api_pw=$(gen); ingest_pw=$(gen)
    cat > .env <<EOF
# สร้างอัตโนมัติโดย scripts/setup_server.sh — ห้าม commit เข้า git
POSTGRES_PASSWORD=$(gen)
ADVISOR_API_PASSWORD=$api_pw
ADVISOR_INGEST_PASSWORD=$ingest_pw
JWT_SECRET=$(gen)

DATABASE_URL=postgresql+psycopg://advisor_api:$api_pw@postgres:5432/course_advisor
INGEST_DATABASE_URL=postgresql://advisor_ingest:$ingest_pw@postgres:5432/course_advisor

OLLAMA_BASE_URL=http://ollama:11434
LLM_MODEL=qwen2.5:7b
EMBED_MODEL=bge-m3
EMBED_DIM=1024
EOF
    chmod 600 .env
    echo "สร้าง .env พร้อมรหัสผ่านสุ่มแล้ว"
fi

# ---------------------------------------------------------------- 4. build
step "4/5 build และเปิดระบบ (ครั้งแรกใช้เวลา 10-20 นาที)"
docker compose -f docker-compose.prod.yml up -d --build

# ---------------------------------------------------------------- 5. models
step "5/5 ดึงโมเดล (ประมาณ 6GB)"
echo "รอ Ollama พร้อมรับคำสั่ง..."
for _ in $(seq 1 30); do
    if docker compose -f docker-compose.prod.yml exec -T ollama ollama list >/dev/null 2>&1; then
        break
    fi
    sleep 5
done
for m in bge-m3 qwen2.5:7b; do
    echo "ดึง $m ..."
    docker compose -f docker-compose.prod.yml exec -T ollama ollama pull "$m"
done

# backend ตรวจมิติเวกเตอร์ตอนเริ่มทำงาน ถ้าตอนนั้นยังไม่มีโมเดลมันจะล้มแล้ววนรีสตาร์ท
# พอโมเดลมาครบแล้วจึงสั่งเริ่มใหม่ให้ผ่านการตรวจในรอบเดียว
docker compose -f docker-compose.prod.yml restart backend

step "เสร็จแล้ว"
docker compose -f docker-compose.prod.yml ps
echo ""
echo "เปิดเว็บที่ http://$(curl -s -m 5 ifconfig.me || echo '<IP ของเครื่อง>')"
echo ""
echo "ขั้นต่อไป: กู้ข้อมูลหลักสูตร มิฉะนั้นระบบจะไม่มีข้อมูลให้ค้น"
echo "  ดู docs/DEPLOY_ORACLE_CLOUD.md หัวข้อ 'นำข้อมูลขึ้นเซิร์ฟเวอร์'"
