# Frontend image (Next.js)
#
#   docker build -f frontend/Dockerfile \
#     --build-arg NEXT_PUBLIC_API_URL=https://your-domain/api -t course-advisor-frontend frontend
#
# สำคัญ: NEXT_PUBLIC_* ถูกฝังลงไฟล์ตอน "build" ไม่ใช่ตอนรัน การตั้ง environment
# ตอน docker run จึงไม่มีผลกับค่านี้ ต้องส่งเป็น --build-arg เท่านั้น
# ถ้าเปลี่ยนโดเมนของ API ต้อง build image ใหม่

# ---------- ขั้นติดตั้ง dependency ----------
FROM node:20-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
# npm ci ติดตั้งตาม lock file เป๊ะๆ (ต่างจาก npm install ที่อาจเลื่อนเวอร์ชัน)
RUN npm ci

# ---------- ขั้น build ----------
FROM node:20-slim AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

ARG NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_TELEMETRY_DISABLED=1

RUN npm run build

# ---------- ขั้นรันจริง ----------
FROM node:20-slim AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

RUN useradd --create-home --uid 1000 nextjs

# standalone มี server.js กับ node_modules เท่าที่จำเป็นมาให้แล้ว
# แต่ไม่รวม static assets กับ public จึงต้องคัดลอกเพิ่มเอง
COPY --from=builder --chown=nextjs:nextjs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nextjs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nextjs /app/public ./public

USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]
