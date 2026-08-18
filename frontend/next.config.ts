import type { NextConfig } from "next";

// ที่อยู่ของ backend อ่านจาก BACKEND_ORIGIN ใน app/api/[...path]/route.ts

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // "standalone" ให้ next build รวมเฉพาะไฟล์ที่ต้องใช้ตอนรันจริงไว้ที่
  // .next/standalone ทำให้ image ไม่ต้องแบก node_modules ทั้งก้อน
  // (ขนาดต่างกันหลายร้อย MB) — ใช้โดย frontend/Dockerfile
  output: "standalone",

  // /api/* ถูกส่งต่อไป backend โดย app/api/[...path]/route.ts ไม่ใช่ rewrites()
  //
  // ต้องส่งต่อจากฝั่งเซิร์ฟเวอร์เสมอ เพราะถ้าให้เบราว์เซอร์เรียก backend ตรงๆ
  // หน้าเว็บจะใช้ได้เฉพาะบนเครื่องเดียวกับที่รัน backend พอเปิดจากเครื่องอื่น
  // เบราว์เซอร์จะไปเรียก 127.0.0.1 ของ "เครื่องคนดู" ซึ่งไม่มีอะไรอยู่ หน้าเว็บ
  // จึงโหลดขึ้นแต่ล็อกอินไม่ได้ พอส่งต่อผ่านเซิร์ฟเวอร์แล้วเบราว์เซอร์เห็น origin
  // เดียว จึงไม่ต้องตั้ง CORS ด้วย
  //
  // ที่เลิกใช้ rewrites เพราะมันอ่านคำตอบจนครบก้อนก่อนส่งต่อ ซึ่งทำลายการทยอยส่ง
  // ของ /chat/stream ทั้งหมด (ดูตัวเลขที่วัดได้ในไฟล์ route.ts)
};
export default nextConfig;
