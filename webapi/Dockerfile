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
#
# ใช้ npm ci ไม่ใช่ npm install เพื่อให้ image ได้ไลบรารีชุดเดียวกับที่ทดสอบเป๊ะ ๆ
# และไม่ใส่ * ท้ายชื่อ lock file อีกต่อไป — ถ้าไฟล์หาย build ต้องล้มเสียงดัง
# ไม่ใช่เงียบ ๆ แล้วไปดึงรุ่นใหม่กว่าที่ไม่เคยมีใครทดสอบ
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --no-audit --no-fund

# โค้ดของเพื่อน คัดลอกมาทั้งอย่างโดยไม่แก้ไข
COPY api ./api
# ตัวครอบที่แปลงคำขอของ Node ให้เป็นรูปแบบที่ฟังก์ชันเดิมรับได้ และด่านตรวจสิทธิ์กลาง
#
# auth.mjs ต้องมาด้วยเสมอ — server.mjs นำเข้ามันตั้งแต่บรรทัดแรก ถ้าลืมคัดลอก
# คอนเทนเนอร์จะพังตอนเริ่มทำงาน ไม่ใช่ตอนมีคนเรียก
#
# ไม่คัดลอก *.test.mjs เข้า image โดยเจตนา ชุดทดสอบไม่ใช่ของที่ต้องรันใน production
# db.mjs ก็เช่นเดียวกับ auth.mjs — server.mjs นำเข้ามันตั้งแต่บรรทัดแรก
COPY server.mjs auth.mjs db.mjs ./

# ไม่รันด้วยสิทธิ์ผู้ดูแลระบบ
USER node

EXPOSE 3001

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:3001/healthz').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["node", "server.mjs"]
