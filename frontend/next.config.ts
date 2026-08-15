import type { NextConfig } from "next";

// ที่อยู่ของ backend ในมุมของ "เซิร์ฟเวอร์ Next" ไม่ใช่ของเบราว์เซอร์
// ตอนรันบนเครื่อง = 127.0.0.1:8000 / ตอนอยู่ใน Docker = http://backend:8000
const BACKEND_ORIGIN = process.env.BACKEND_ORIGIN ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // "standalone" ให้ next build รวมเฉพาะไฟล์ที่ต้องใช้ตอนรันจริงไว้ที่
  // .next/standalone ทำให้ image ไม่ต้องแบก node_modules ทั้งก้อน
  // (ขนาดต่างกันหลายร้อย MB) — ใช้โดย frontend/Dockerfile
  output: "standalone",

  // ส่งต่อ /api/* ไปยัง backend จากฝั่งเซิร์ฟเวอร์
  //
  // ทำไมต้องมี: เดิมเบราว์เซอร์เรียก API ที่ http://127.0.0.1:8000 ตรงๆ ซึ่งใช้ได้
  // เฉพาะตอนเปิดบนเครื่องเดียวกับที่รัน backend พอเปิดจากเครื่องอื่น (หรือผ่าน
  // tunnel) เบราว์เซอร์จะไปเรียก 127.0.0.1 ของ "เครื่องคนดู" ซึ่งไม่มีอะไรอยู่
  // หน้าเว็บจึงโหลดขึ้นแต่ล็อกอินไม่ได้
  //
  // พอ proxy ผ่าน Next แล้วเบราว์เซอร์เห็นแค่ origin เดียว จึงไม่ต้องตั้ง CORS
  // และเปลี่ยนโดเมนกี่ครั้งก็ไม่ต้อง build ใหม่ (ต่างจากการฝัง URL เต็มไว้ใน bundle)
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${BACKEND_ORIGIN}/:path*` }];
  },
};
export default nextConfig;
