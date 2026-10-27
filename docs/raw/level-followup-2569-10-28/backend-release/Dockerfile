# ซ้อนเฉพาะไฟล์ของ release นี้ทับอิมเมจที่ production ใช้อยู่
#
# ฐานคืออิมเมจของ release 27 ต.ค. ที่ deploy ไปแล้ว ไม่ build จากซอร์สทั้งก้อน
# เพราะที่ทำงานของ backend ยังมีงานค้างจากรอบก่อนที่ไม่ได้อยู่ใน production
#
# diff เทียบอิมเมจฐานอยู่ที่ ../backend-vs-image-level.diff (เพิ่ม 78 · ลบ 9 บรรทัด)
FROM course-advisor-system-backend:level-2569-10-27

COPY --chown=appuser:appuser files/course_scope.py /app/backend/app/services/course_scope.py
COPY --chown=appuser:appuser files/follow_up.py    /app/backend/app/services/follow_up.py

# ชุดทดสอบของ release นี้ และชุดเดิมที่ปรับเกณฑ์ให้ยืนยันผลแทนเส้นทาง
COPY --chown=appuser:appuser files/test_level_followup_answer.py  /app/backend/tests/test_level_followup_answer.py
COPY --chown=appuser:appuser files/test_level_clarify_followup.py /app/backend/tests/test_level_clarify_followup.py
COPY --chown=appuser:appuser files/test_compare_degree_level.py   /app/backend/tests/test_compare_degree_level.py
