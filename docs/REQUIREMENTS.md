# Requirement Document — Course Advisor System

## เป้าหมาย

ช่วยผู้เรียนค้นหาและเปรียบเทียบหลักสูตรที่สอดคล้องกับพื้นฐาน เป้าหมาย ความสนใจ และข้อจำกัด ผู้ใช้หลักคือผู้เรียน/ผู้เปลี่ยนสายงาน ส่วนผู้ดูแลข้อมูลใช้ ingestion CLI

## Functional requirements

| ID | Requirement | สถานะ |
|---|---|---|
| FR-01 | สมัครสมาชิกและเข้าสู่ระบบด้วย JWT | พร้อมใช้ |
| FR-02 | อ่าน/แก้โปรไฟล์การศึกษา อาชีพ เป้าหมาย ทักษะ ความสนใจ | พร้อมใช้ |
| FR-03 | เพิ่มข้อกำหนดพร้อม priority 1–5 | พร้อมใช้ |
| FR-04 | แสดงและกรองรายการหลักสูตร | พร้อมใช้; กรองใน browser |
| FR-05 | semantic search จาก vector chunks | API พร้อมใช้ |
| FR-06 | แนะนำด้วย profile + requirements + คำถามเพิ่มเติม | พร้อมใช้ |
| FR-07 | แสดงคะแนน เหตุผล และ chunk citations | API พร้อม; UI แสดงคะแนน/เหตุผล |
| FR-08 | นำเข้า PDF: extract, clean, chunk, embed | พร้อมผ่าน CLI |
| FR-09 | บันทึก session/messages/recommendations | schema/service รองรับ |
| FR-10 | แก้ไข/ลบ requirement และ refresh token | ยังไม่รองรับ |
| FR-11 | Admin UI สำหรับ ingestion | นอก scope รุ่นนี้ |

## Non-functional requirements

- Security: bcrypt, JWT expiry, validation, parameterized SQL, CORS และ rate limit
- Privacy: เก็บเท่าที่จำเป็น; production ต้องกำหนด retention/encryption/PII access
- Accessibility: keyboard focus, labels, semantic heading และ ARIA status/error
- Responsive: มือถือ แท็บเล็ต desktop
- Reliability: loading/error/empty state และไม่เปิดเผย stack trace
- Maintainability: TypeScript strict, typed API client และ automated tests

## Acceptance criteria

1. ผู้ใช้สมัคร/เข้าสู่ระบบแล้วเข้าสู่แบบสอบถามได้
2. แบบสอบถามบันทึก profile/requirement พร้อม bearer token
3. คำถามไม่เกิน 1,000 ตัวอักษรได้รับไม่เกิน 5 คำแนะนำ
4. คำแนะนำมีชื่อ คะแนน เหตุผล และ API มี cited chunk IDs
5. 401/409/429/network failure แสดงข้อความและหน้าไม่ crash
6. `npm test` และ `npm run build` ผ่านก่อน release
