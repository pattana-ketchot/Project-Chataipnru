/**
 * ส่งต่อ /api/* ไปยัง backend โดยไม่พักข้อมูลไว้ระหว่างทาง
 *
 * ทำไมไม่ใช้ rewrites() ใน next.config.ts เหมือนเดิม
 * ------------------------------------------------
 * rewrites อ่านคำตอบจาก backend จนครบก้อนก่อนแล้วค่อยส่งต่อให้เบราว์เซอร์ ซึ่งใช้ได้
 * กับคำตอบธรรมดา แต่ทำลายการทยอยส่งของ /chat/stream ทั้งหมด วัดได้ชัดเจน:
 *
 *   เรียก backend ตรงๆ          ตัวอักษรแรกที่  3.5 วิ   จบที่ 68.7 วิ
 *   เรียกผ่าน rewrites          ทุกอย่างมาพร้อมกันที่ 47 วิ
 *
 * ตัวส่งต่อที่เขียนเองคืน response.body ซึ่งเป็นสายข้อมูลต่อตรง เบราว์เซอร์จึงได้
 * ข้อความทันทีที่โมเดลเขียนออกมาแต่ละส่วน
 *
 * ผลพลอยได้: อ่าน BACKEND_ORIGIN ตอนรันจริง ไม่ใช่ตอน build เหมือน rewrites
 * จึงเปลี่ยนที่อยู่ backend ได้โดยไม่ต้อง build image ใหม่
 */
import type { NextRequest } from "next/server";

const BACKEND_ORIGIN = process.env.BACKEND_ORIGIN ?? "http://127.0.0.1:9000";

// บอก Next ว่าห้ามแคชและห้ามพยายาม render ล่วงหน้า — ทุกคำขอต้องวิ่งไป backend จริง
export const dynamic = "force-dynamic";

async function proxy(request: NextRequest, path: string[]): Promise<Response> {
  const url = new URL(request.url);
  const target = `${BACKEND_ORIGIN}/${path.join("/")}${url.search}`;

  const headers = new Headers();
  // ส่งต่อเฉพาะหัวข้อความที่ backend ต้องใช้จริง ไม่ยกมาทั้งชุดเพราะ host กับ
  // accept-encoding ของ Next จะทำให้ backend ตอบผิดรูปแบบ
  for (const name of ["authorization", "content-type", "accept"]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }

  // อ่าน body ให้ครบก่อนส่ง — คำขอเป็น JSON สั้นๆ ทั้งหมด การพักไว้จึงไม่กระทบอะไร
  // และเลี่ยงข้อกำหนดเรื่อง duplex ของ fetch ฝั่ง Node เมื่อส่ง body เป็นสายข้อมูล
  const body = request.method === "GET" || request.method === "HEAD" ? undefined : await request.arrayBuffer();

  let upstream: Response;
  try {
    upstream = await fetch(target, { method: request.method, headers, body, redirect: "manual" });
  } catch {
    return Response.json({ detail: "เชื่อมต่อระบบเบื้องหลังไม่ได้ กรุณาลองใหม่อีกครั้งครับ" }, { status: 502 });
  }

  const out = new Headers();
  for (const name of ["content-type", "cache-control"]) {
    const value = upstream.headers.get(name);
    if (value) out.set(name, value);
  }
  // ห้ามใส่ content-length เพราะคำตอบแบบสตรีมไม่รู้ความยาวล่วงหน้า
  return new Response(upstream.body, { status: upstream.status, headers: out });
}

type Ctx = { params: Promise<{ path: string[] }> };

export async function GET(request: NextRequest, ctx: Ctx) {
  return proxy(request, (await ctx.params).path);
}
export async function POST(request: NextRequest, ctx: Ctx) {
  return proxy(request, (await ctx.params).path);
}
export async function PUT(request: NextRequest, ctx: Ctx) {
  return proxy(request, (await ctx.params).path);
}
export async function DELETE(request: NextRequest, ctx: Ctx) {
  return proxy(request, (await ctx.params).path);
}
