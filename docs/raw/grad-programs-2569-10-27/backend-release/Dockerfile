# ซ้อนเฉพาะไฟล์ของ release นี้ทับอิมเมจ production ปัจจุบัน
#
# ใช้ FROM อิมเมจที่รันอยู่จริง ไม่ build จากซอร์สทั้งก้อน
#
# รอบนี้สำคัญ เพราะที่ทำงานของ backend มีงานค้างจากรอบก่อนที่ยังไม่ขึ้น production
# อยู่ราว 250 บรรทัด ถ้า build จากที่ทำงาน งานเหล่านั้นจะขึ้นไปด้วยโดยไม่ได้ตรวจ
#
# ไฟล์ใน files/ สร้างโดยเอาไฟล์จากอิมเมจนี้มาเป็นฐาน แล้วใส่เฉพาะ patch ของรอบนี้
# diff เทียบอิมเมจอยู่ที่ ../backend-vs-prod-image.diff (เพิ่ม 136 · ลบ 9 บรรทัด)
FROM course-advisor-system-backend:counter-2569-10-16

COPY --chown=appuser:appuser files/course_scope.py       /app/backend/app/services/course_scope.py
COPY --chown=appuser:appuser files/chat.py               /app/backend/app/services/chat.py
COPY --chown=appuser:appuser files/web_compat_service.py /app/backend/app/services/web_compat.py
COPY --chown=appuser:appuser files/web_compat_route.py   /app/backend/app/api/routes/web_compat.py

# ชุดทดสอบของ release นี้ — ติดไปกับอิมเมจเพื่อให้รันตรวจซ้ำได้ในคอนเทนเนอร์จริง
COPY --chown=appuser:appuser files/test_compare_degree_level.py   /app/backend/tests/test_compare_degree_level.py
COPY --chown=appuser:appuser files/test_level_clarify_followup.py /app/backend/tests/test_level_clarify_followup.py
