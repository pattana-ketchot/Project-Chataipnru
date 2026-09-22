# บริการเสริมสำหรับฟังก์ชันของหน้าเว็บที่ต้องรันฝั่งเซิร์ฟเวอร์
#
# รับผิดชอบเพียง 5 เส้นทาง คือ ข่าว Sci Connect 2 เส้นทาง และงานหลังบ้าน 3 เส้นทาง
# เส้นทางอื่นทั้งหมดยังเป็นของ FastAPI เหมือนเดิม ไม่มีการเปลี่ยนแปลง
#
# ไม่คัดลอก api/chat.js · api/compare-courses.js · api/recommend-major.js เข้ามา
# โดยตั้งใจ เพราะสามเส้นทางนั้น FastAPI ของเราเป็นผู้ตอบ

FROM node:22-alpine

WORKDIR /app

# ติดตั้งไลบรารีก่อน เพื่อให้ชั้นนี้ถูกใช้ซ้ำเมื่อโค้ดเปลี่ยนแต่ไลบรารีไม่เปลี่ยน
COPY package.json package-lock.json* ./
RUN npm install --omit=dev --no-audit --no-fund

# โค้ดของเพื่อน คัดลอกมาทั้งอย่างโดยไม่แก้ไข
COPY api ./api
# ตัวครอบที่แปลงคำขอของ Node ให้เป็นรูปแบบที่ฟังก์ชันเดิมรับได้
COPY server.mjs ./

# ไม่รันด้วยสิทธิ์ผู้ดูแลระบบ
USER node

EXPOSE 3001

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:3001/healthz').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["node", "server.mjs"]
