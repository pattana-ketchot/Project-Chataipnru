# อิมเมจของตัวนำเข้าเอกสารที่อนุมัติแล้ว — รันครั้งเดียวแล้วจบ (Phase 3C/3D)
#
# build context ต้องเป็น "root ของ repo" เพราะ pipeline import แพ็กเกจ llm/ ที่อยู่นอก
# โฟลเดอร์ตัวเอง (llm/connector.py ใช้โดย pipeline/embed.py และ pipeline/crawl/approve.py)
# โครงสร้างใน image จึงต้องเป็น
#   /app/pipeline/...
#   /app/llm/...
# ให้เหมือนตอนรันบนเครื่อง ไม่งั้น pipeline/crawl/approve.py ที่เติม parents[2] เข้า
# sys.path จะหา llm.connector ไม่เจอ
#
#   docker build -f pipeline/Dockerfile \
#     --build-arg GIT_REVISION=<commit> \
#     -t course-advisor-system-ingest-worker:<tag> .
#
# ทำไมต้องมีอิมเมจนี้แยกจาก backend
# --------------------------------
# อิมเมจ backend ไม่มี PyMuPDF (ตรวจด้วย pip metadata แล้ว) แต่ pipeline/extract_pdf.py
# ต้องใช้ `import fitz` ทั้งในตัวตรวจของ worker และใน pipeline.ingest.run() เอง
# การเพิ่ม PyMuPDF เข้า backend ไม่เหมาะ เพราะ backend ไม่ได้ใช้และจะทำให้อิมเมจของ
# บริการที่เปิดสู่อินเทอร์เน็ตใหญ่ขึ้นโดยไม่มีเหตุ
#
# ทำไมไม่ใส่ scheduler หรือ entrypoint ที่วนรอ
# -------------------------------------------
# worker ออกแบบให้ทำงานจำนวนจำกัดแล้วจบ (pipeline/crawl/approve.py::work) การรันเป็น
# บริการค้างจะขัดกับข้อกำหนดของ Phase 3 ที่ห้ามตั้งเวลาทำงานอัตโนมัติ
# คอนเทนเนอร์นี้จึงตั้งใจให้รันด้วย `docker run --rm` ทีละครั้ง

FROM python:3.11-slim

# ต้องส่งเข้ามาตอน build เพื่อผูกอิมเมจกับ revision ที่ตรวจสอบย้อนกลับได้
# (อิมเมจ backend ที่ใช้อยู่ไม่มี label นี้ จึงพิสูจน์ไม่ได้ว่ามาจาก commit ไหน)
ARG GIT_REVISION=unknown
LABEL org.opencontainers.image.revision="${GIT_REVISION}"
LABEL org.opencontainers.image.title="SCI Advisor approved-curriculum ingest worker"
LABEL org.opencontainers.image.description="one-shot worker: approved crawl decision -> pipeline.ingest.run"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# ติดตั้ง dependency ก่อน copy โค้ด เพื่อให้ layer นี้ถูก cache ไว้
COPY pipeline/requirements.txt pipeline/requirements.txt
RUN pip install --no-cache-dir -r pipeline/requirements.txt

COPY pipeline/ pipeline/
COPY llm/ llm/

# uid/gid 1001 ให้ตรงกับผู้ใช้ ubuntu บนเซิร์ฟเวอร์ ซึ่งเป็นเจ้าของโฟลเดอร์
# documents/ และ staging/ ที่จะ mount เข้ามา ไฟล์ที่ worker เขียนจึงมีเจ้าของเดียวกับ
# ไฟล์เดิมทั้งหมด และด้วย umask ปกติจะเป็น mode 644 ซึ่ง backend (uid 1000) อ่านได้
#
# เปลี่ยนได้ตอนรันด้วย --user ถ้าเซิร์ฟเวอร์ปลายทางใช้ uid อื่น
RUN groupadd --gid 1001 worker && useradd --uid 1001 --gid 1001 --create-home worker
USER worker

# ค่าตั้งต้นคือทำงานหนึ่งงานแล้วจบ ผู้เรียกระบุ --max-jobs เองได้
CMD ["python", "-u", "-m", "pipeline.crawl.approve", "--max-jobs", "1"]
