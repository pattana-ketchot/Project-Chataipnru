# Backend image (FastAPI)
#
# build context ต้องเป็น "root ของ repo" ไม่ใช่ backend/ เพราะ backend import
# แพ็กเกจ llm/ ที่อยู่นอกโฟลเดอร์ตัวเอง (app/services/llm_client.py หา repo root
# จาก parents[3] แล้วเติมเข้า sys.path) โครงสร้างใน image จึงต้องเป็น
#   /app/backend/app/...
#   /app/llm/...
# ให้เหมือนตอนรันบนเครื่อง ไม่งั้น import llm.connector จะพัง
#
#   docker build -f backend/Dockerfile -t course-advisor-backend .

FROM python:3.11-slim

# ไม่เขียน .pyc และไม่ buffer stdout เพื่อให้ log ออกมาทันทีใน docker logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# ติดตั้ง dependency ก่อน copy โค้ด เพื่อให้ layer นี้ถูก cache ไว้
# แก้โค้ดแล้ว build ใหม่จะไม่ต้องลง package ใหม่ทั้งหมด
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ backend/
COPY llm/ llm/

# รันด้วยผู้ใช้ที่ไม่ใช่ root — ถ้าแอปถูกเจาะจะจำกัดความเสียหายได้มากกว่า
RUN useradd --create-home --uid 1000 appuser && chown -R appuser:appuser /app
USER appuser

WORKDIR /app/backend
EXPOSE 8000

# bind 0.0.0.0 เพราะต้องรับ request จากนอก container
# (127.0.0.1 จะเข้าถึงได้แค่ภายใน container เอง)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
