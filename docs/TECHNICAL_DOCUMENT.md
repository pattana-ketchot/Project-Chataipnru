# Technical Document — Course Advisor System

## ภาพรวม

ระบบช่วยผู้เรียนค้นหาหลักสูตรจากโปรไฟล์ ข้อจำกัด และคำถามภาษาธรรมชาติด้วย Retrieval-Augmented Generation (RAG) ข้อมูลจาก PDF จะถูกทำความสะอาด แบ่งส่วน สร้าง embedding และเก็บใน PostgreSQL/pgvector

| ส่วน | เทคโนโลยี | หน้าที่ |
|---|---|---|
| Web UI | Next.js, React, TypeScript, Tailwind | Auth, แบบสอบถาม, หลักสูตร และคำแนะนำ |
| API | FastAPI, Pydantic, SQLAlchemy | validation, JWT และ business API |
| Data | PostgreSQL, pgvector | ผู้ใช้ หลักสูตร chunks และประวัติ |
| AI — ค้นเอกสาร | Ollama + bge-m3 (1,024 มิติ) | แปลงข้อความเป็นเวกเตอร์ ทำงานในเครื่องเสมอ |
| AI — เขียนคำตอบ | Gemini Flash Lite หรือ Ollama + Qwen | เลือกได้ด้วยค่า `LLM_PROVIDER` และสลับกลับได้ตลอด |
| Ingestion | Python | extract → clean → chunk → embed → persist |

## Runtime flow

1. `POST /auth/login` คืน access token; Frontend ส่งผ่าน `Authorization: Bearer`
2. แบบสอบถามบันทึกด้วย `PUT /users/me/profile` และ `POST /users/me/requirements`
3. Frontend ส่ง `POST /recommend` พร้อม `extra_query`
4. Backend รวม profile/requirements เป็น query ขอ embedding จาก Ollama แล้วค้น chunks จาก pgvector
5. RAG service ประกอบ prompt โดยแยกเอกสารเป็น untrusted context ให้ LLM จัดอันดับและอธิบาย
6. Backend บันทึก recommendation และคืน course, score, rationale และ citations

## API ที่ Frontend ใช้

| Method/Path | Auth | การใช้งาน |
|---|---:|---|
| `POST /auth/register`, `/auth/login` | ไม่ | สมัครและเข้าสู่ระบบ |
| `GET /users/me` | ใช่ | ข้อมูลผู้ใช้ |
| `GET`, `PUT /users/me/profile` | ใช่ | อ่าน/แก้โปรไฟล์ |
| `GET`, `POST /users/me/requirements` | ใช่ | อ่าน/เพิ่มข้อจำกัด |
| `GET /courses` | ไม่ | รายการหลักสูตร |
| `POST /search` | ใช่ | semantic search |
| `POST /recommend` | ใช่ | คำแนะนำด้วย RAG |

OpenAPI อยู่ที่ `http://localhost:8000/docs` ใน development

## Error, security และ testing

- UI แปล 401, 409, 429 และรองรับ loading/error/empty state
- Pydantic จำกัดข้อมูล, SQLAlchemy ใช้ parameterized query, JWT มี expiry และ endpoint AI มี rate limit
- Ollama/PostgreSQL bind ที่ localhost; ห้าม commit `.env`
- Production ควรเปลี่ยน token storage เป็น secure HttpOnly cookie/BFF, ใช้ TLS, secret manager, distributed rate limiter และ refresh-token rotation
- Unit test ตรวจ API request/auth/error; integration test จำลอง API แล้วทดสอบ login journey ผ่าน DOM

## ข้อจำกัดปัจจุบัน

- `/recommend` เป็น request/response ไม่ใช่ streaming chat
- requirements ยังไม่มีแก้ไข/ลบ จึงอาจซ้ำเมื่อส่งแบบสอบถามหลายครั้ง
- ยังไม่มี refresh endpoint และ Admin UI สำหรับ ingestion
