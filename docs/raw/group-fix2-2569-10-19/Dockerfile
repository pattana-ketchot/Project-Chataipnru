# ซ้อนเฉพาะสองไฟล์ของ GROUP_QUESTION_FIX2 ทับอิมเมจ production ที่รันอยู่จริง
#
# ทำไมใช้ FROM อิมเมจที่รันอยู่ ไม่ build จากซอร์สทั้งก้อน
# ----------------------------------------------------
# working tree มีงานที่ยังไม่อนุมัติปนอยู่ (เช่น crawl_review ใน main.py และงานฝั่ง
# mko phase 1) การ build ทั้งก้อนจะพางานเหล่านั้นขึ้น production ด้วย
# การซ้อนไฟล์ทับอิมเมจเดิมทำให้ตรวจได้ว่าต่างจากของเดิมกี่ไฟล์ — deploy.sh ขั้นที่ 6
# เทียบ md5 ของทุกไฟล์ในอิมเมจทั้งสองตัว และล้มถ้าไฟล์ที่ต่างไม่ใช่สองไฟล์นี้
FROM course-advisor-system-backend:counter-2569-10-16

COPY --chown=appuser:appuser files/subjects.py /app/backend/app/services/subjects.py
COPY --chown=appuser:appuser files/chat.py     /app/backend/app/services/chat.py
