# ซ้อนเฉพาะไฟล์ของ release นี้ทับอิมเมจที่ production ใช้อยู่
#
# ฐานคืออิมเมจของ release 28 ต.ค. 2569 (ต่อบริบทระดับปริญญา) ที่ deploy ไปแล้ว
# **ไม่ build จากซอร์สทั้งก้อน** เพราะที่ทำงานของ backend มีงานค้างที่ยังไม่ได้ปล่อย
# สองก้อนปนอยู่ และทั้งสองก้อนจะถูกพาขึ้น production ไปด้วยถ้า build ทั้งก้อน:
#
#   1. routes/crawl_review.py (คิวตรวจไฟล์จาก crawler) — ไม่มีในอิมเมจนี้
#      main.py ของที่ทำงาน import มันอยู่ ถ้าคัดลอกไปซ้อน backend จะขึ้นไม่ได้เลย
#      (ImportError: cannot import name 'crawl_review') — เจอจริงตอนทดสอบรอบแรก
#   2. ชั้นเติมหน้าหลักฐานใน services/chat.py (ราว 70 บรรทัด จากรอบ 19 ต.ค.)
#
# ไฟล์ในโฟลเดอร์ files/ จึงสร้างจาก "ไฟล์ในอิมเมจฐาน" แล้วปะเฉพาะการแก้ของรอบนี้
# ไม่ใช่คัดลอกมาจากที่ทำงาน · diff เทียบอิมเมจฐานอยู่ที่ ../vs-prod-image.diff
FROM course-advisor-system-backend:followup-2569-10-28

# ตัวตัดสินว่าคำขอใหม่จะใช้ผู้ให้บริการและรุ่นไหน (ไฟล์ใหม่)
COPY --chown=appuser:appuser files/ai_settings.py  /app/backend/app/services/ai_settings.py
# สร้าง connector ตามตัวเลือก + นับการใช้โมเดลในเครื่องเป็นตัวหลัก + การตรวจสองขั้น
COPY --chown=appuser:appuser files/llm_client.py   /app/backend/app/services/llm_client.py
# บอกชื่อโมเดลที่ถูกสั่งให้เขียนคำตอบ กลับไปในคำตอบและในเหตุการณ์ done
COPY --chown=appuser:appuser files/chat_service.py /app/backend/app/services/chat.py
COPY --chown=appuser:appuser files/chat_schema.py  /app/backend/app/schemas/chat.py
# ผูกแคชคำตอบไว้กับโมเดลที่เขียนคำตอบ ไม่งั้นสลับโมเดลแล้วคำถามเดิมได้คำตอบของเจ้าเดิม
COPY --chown=appuser:appuser files/answer_cache.py /app/backend/app/services/answer_cache.py
# เส้นทางของผู้ดูแล: อ่าน/บันทึก provider + ปุ่มตรวจที่ยิงคำขอจริง
COPY --chown=appuser:appuser files/site_admin.py   /app/backend/app/api/routes/site_admin.py
# งานอุ่นโมเดลเบื้องหลังต้องตามสวิตช์ ไม่ถือ connector ตัวเดิมตลอดอายุเซิร์ฟเวอร์
COPY --chown=appuser:appuser files/main.py         /app/backend/app/main.py

# ชุดทดสอบของ release นี้
COPY --chown=appuser:appuser files/test_model_switch.py /app/backend/tests/test_model_switch.py
# ชุดเดิมของตัวนับ — อยู่ในที่ทำงานแต่ยังไม่เคยถูก deploy · ครอบส่วนที่รอบนี้แตะ
COPY --chown=appuser:appuser files/test_llm_usage_counter.py /app/backend/tests/test_llm_usage_counter.py
