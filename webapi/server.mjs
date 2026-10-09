/**
 * ตัวครอบฟังก์ชันของหน้าเว็บให้รันเป็นบริการเดียวบนเซิร์ฟเวอร์ของเราเอง
 *
 * ฟังก์ชันใน api/ เขียนตามสัญญาแบบเว็บมาตรฐาน คือ `export default { fetch(Request): Response }`
 * ซึ่งเดิมรันบนแพลตฟอร์มไร้เซิร์ฟเวอร์ ไฟล์นี้แปลงคำขอของ Node ให้เป็น Request แล้วส่งเข้า
 * ฟังก์ชันเดิมโดยไม่แก้ตัวฟังก์ชันเลยแม้แต่บรรทัดเดียว — ของเพื่อนยังเป็นของเพื่อนทุกอย่าง
 *
 * เส้นทางที่บริการนี้รับผิดชอบมีเพียง 5 เส้นทาง นอกนั้น Caddy ส่งไป FastAPI เหมือนเดิม
 *
 * ด่านตรวจสิทธิ์กลาง
 * -----------------
 * ทุกเส้นทางต้องประกาศระดับสิทธิ์ไว้ในตาราง ROUTES และไฟล์นี้บังคับให้ "ก่อน" เรียก
 * ฟังก์ชันของหน้าเว็บ เส้นทางที่ไม่ประกาศระดับจะทำให้บริการไม่ยอมเริ่มทำงานเลย
 *
 * ทำไมต้องบังคับที่นี่ ไม่ใช่ปล่อยให้แต่ละฟังก์ชันเรียก requireAdminUser เอง
 * ----------------------------------------------------------------------
 * ของเดิมพึ่งพาว่าคนเขียนฟังก์ชันใหม่จะจำได้ว่าต้องเรียก ลืมที่เดียวคือเส้นทางนั้น
 * เปิดโล่งเงียบ ๆ โดยไม่มีอะไรฟ้อง — รูปแบบเดียวกับที่ FastAPI ฝั่งเราเลือกใช้
 * `require_admin` คลุมทั้ง router แทนการใส่ทีละเส้นทาง (ดู routes/crawl_review.py)
 *
 * ด่านนี้เป็นการ "เพิ่มชั้นนอก" ไม่ได้แทนที่ requireAdminUser ที่ฟังก์ชันหลังบ้าน
 * เรียกอยู่ ผู้เรียกที่มีสิทธิ์ถูกต้องจึงได้ผลลัพธ์เหมือนเดิมทุกอย่าง
 */
import http from "node:http";
import { Readable } from "node:stream";

import {
  EDITOR,
  PUBLIC,
  authorize,
  createRuntimeDeps,
  describeForLog,
  needsAuthContext,
  resolveAuthContext,
  supabaseEnv,
  validateRouteTable,
} from "./auth.mjs";
import { createDatabase } from "./db.mjs";

const PORT = Number(process.env.PORT || 3001);

// เส้นทาง -> ไฟล์ฟังก์ชันของเพื่อน -> ระดับสิทธิ์ที่ต้องมี (พาธเทียบกับโฟลเดอร์นี้)
//
// ระดับที่ตั้งไว้ตรงกับพฤติกรรมที่ระบบมีอยู่จริงวันนี้ ไม่ได้เข้มขึ้นหรือหลวมลง
//   ข่าว Sci Connect สองเส้นทาง  เปิดสาธารณะอยู่แล้ว (หน้าเว็บเรียกโดยไม่ล็อกอิน)
//   /api/admin/* สามเส้นทาง      ของเดิมเรียก requireAdminUser ซึ่งยอม admin+editor
//                                 ที่ status = approved -> ตรงกับระดับ EDITOR ที่นี่
const ROUTES = [
  ["/api/sci-connect-news-detail", "./api/sci-connect-news-detail.js", PUBLIC],
  ["/api/sci-connect-news", "./api/sci-connect-news.js", PUBLIC],
  ["/api/admin/extract-file", "./api/admin/extract-file.js", EDITOR],
  ["/api/admin/ingest", "./api/admin/ingest.js", EDITOR],
  ["/api/admin/sync-sci-news", "./api/admin/sync-sci-news.js", EDITOR],
];

// ---------------------------------------------------------------------
// ตรวจตาราง ROUTES ก่อนเริ่มรับคำขอ
//
// ปฏิเสธตอนเริ่มทำงาน ไม่ใช่ตอนมีคนเรียก — เส้นทางที่ลืมประกาศระดับสิทธิ์ต้องทำให้
// บริการไม่ขึ้นเลย ถ้าปล่อยให้ขึ้นแล้วค่อยพังตอนมีคนเรียก คนที่เจอก่อนอาจเป็นผู้ใช้
// ที่ไม่ควรเข้าถึงเส้นทางนั้น
// ---------------------------------------------------------------------
const undeclared = validateRouteTable(ROUTES);
if (undeclared.length > 0) {
  console.error(
    "[webapi] เส้นทางต่อไปนี้ไม่ได้ประกาศระดับสิทธิ์ที่รู้จัก: " + undeclared.join(", "),
  );
  process.exit(1);
}

const handlers = new Map();
const levels = new Map();
for (const [route, file, level] of ROUTES) {
  try {
    const mod = await import(file);
    if (typeof mod.default?.fetch !== "function") {
      console.error(`[webapi] ${file} ไม่มี default.fetch — ข้ามเส้นทาง ${route}`);
      continue;
    }
    handlers.set(route, mod.default.fetch);
    levels.set(route, level);
    console.log(`[webapi] พร้อมให้บริการ ${route} (${level})`);
  } catch (err) {
    console.error(`[webapi] โหลด ${file} ไม่สำเร็จ: ${err.message}`);
  }
}

// ตัวตรวจ token อ่านค่าตั้งค่าจาก env ครั้งเดียวตอนเริ่ม
//
// ไม่พิมพ์ค่าใด ๆ ออกมา บอกแค่ว่าตั้งค่าครบหรือไม่ครบ
const env = supabaseEnv();
const authDeps = env ? createRuntimeDeps(env) : null;
if (!authDeps) {
  console.error(
    "[webapi] ไม่พบค่าตั้งค่าของ Supabase — เส้นทางที่ต้องมีสิทธิ์จะตอบ 500 ทุกครั้ง",
  );
}

// ตัวเชื่อมฐานข้อมูลสำหรับแปลงตัวตน Supabase เป็น public.users.id
//
// คืน null เมื่อตั้งค่าไม่ครบ — เส้นทางสาธารณะยังทำงานได้ตามปกติ เพราะไม่ได้ใช้
// ฐานข้อมูลเลย · เส้นทางที่ต้องเขียนข้อมูลจะปฏิเสธอย่างมีเสียงแทนที่จะเดา
//
// log บอกแค่ว่าต่อไปที่ไหนด้วย user อะไร — **ไม่มีรหัสผ่าน**
const database = createDatabase();
if (database) {
  console.log(`[webapi] ตั้งค่าฐานข้อมูลแล้ว: ${database.describe()}`);
} else {
  console.warn(
    "[webapi] ไม่พบค่าตั้งค่าฐานข้อมูล — แปลงตัวตนผู้เขียนไม่ได้ (เส้นทางสาธารณะยังทำงานปกติ)",
  );
}

/**
 * ตอบกลับสั้น ๆ แบบไม่เปิดเผยอะไรเกินจำเป็น
 *
 * ไม่ส่ง token ไม่ส่งคำตอบดิบจาก Supabase ไม่ส่งรายละเอียดภายใน
 */
function deny(res, status, body) {
  res.statusCode = status;
  res.setHeader("content-type", "application/json; charset=utf-8");
  res.end(JSON.stringify(body));
}

/** แปลงคำขอของ Node ให้เป็น Request มาตรฐาน */
function toRequest(req) {
  const host = req.headers.host || `localhost:${PORT}`;
  const url = new URL(req.url, `http://${host}`);
  const init = { method: req.method, headers: req.headers };
  if (req.method !== "GET" && req.method !== "HEAD") {
    init.body = Readable.toWeb(req);
    init.duplex = "half";
  }
  return new Request(url, init);
}

/** ส่ง Response มาตรฐานกลับออกทางของ Node */
async function send(res, response) {
  res.statusCode = response.status;
  for (const [k, v] of response.headers) res.setHeader(k, v);
  if (!response.body) return res.end();
  for await (const chunk of response.body) res.write(chunk);
  res.end();
}

const server = http.createServer(async (req, res) => {
  const path = (req.url || "").split("?")[0];

  if (path === "/healthz") {
    // ประกาศระดับสิทธิ์ของแต่ละเส้นทางออกมาด้วย เพื่อให้ตรวจได้จากภายนอกว่าเส้นทางไหน
    // ถูกคุ้มอยู่ระดับใด โดยไม่ต้องอ่านโค้ด — ไม่ใช่ความลับ เป็นสัญญาที่เปิดเผยได้
    res.setHeader("content-type", "application/json; charset=utf-8");
    res.end(
      JSON.stringify({
        // status สะท้อนเฉพาะว่า HTTP server ยังรับคำขอได้ — **ห้ามขึ้นกับฐานข้อมูล**
        // Docker HEALTHCHECK ตัดสินจากเส้นทางนี้ ถ้าปล่อยให้ล้มเพราะฐานข้อมูลล่ม
        // คอนเทนเนอร์จะถูกมองว่าพัง ทั้งที่สองเส้นทางสาธารณะยังให้บริการได้ปกติ
        status: "ok",
        authConfigured: Boolean(authDeps),
        dbConfigured: Boolean(database),
        // "unknown" จนกว่าจะมีคนใช้จริงครั้งแรก — ไม่ยิง query ถามเองเพื่อไม่ให้
        // เส้นทางนี้ช้าตามฐานข้อมูล
        db: database ? database.status() : "not-configured",
        routes: [...handlers.keys()].map((route) => ({ route, level: levels.get(route) })),
      }),
    );
    return;
  }

  const entry = [...handlers.entries()].find(([route]) => path === route || path.startsWith(route + "/"));
  if (!entry) {
    // 404 ก่อนตรวจสิทธิ์โดยเจตนา — เส้นทางที่บริการนี้ไม่รับผิดชอบไม่ใช่ความลับ
    // Caddy เป็นผู้ตัดสินว่าคำขอไหนมาถึงที่นี่อยู่แล้ว
    deny(res, 404, { error: "not found" });
    return;
  }

  const [route, handler] = entry;
  const level = levels.get(route);
  const request = toRequest(req);

  // ---- ด่านตรวจสิทธิ์ ----
  if (level !== PUBLIC && !authDeps) {
    // ตั้งค่าไม่ครบ = ตรวจสิทธิ์ไม่ได้ = ต้องไม่ปล่อยผ่าน
    deny(res, 500, { error: "Authorization is not configured" });
    return;
  }

  let context = null;
  if (authDeps && needsAuthContext(level)) {
    const resolved = await resolveAuthContext(request, authDeps);
    if (!resolved.ok) {
      // เหลือเฉพาะกรณีตั้งค่าไม่ครบ (500) — ข้อมูลยืนยันตัวตนที่ใช้ไม่ได้ถูกลดระดับ
      // เป็น anonymous ไปแล้วใน resolveAuthContext ไม่ได้ปฏิเสธที่นี่
      deny(res, resolved.status, resolved.body);
      return;
    }
    context = resolved.context;
  }

  const verdict = authorize(context, level);
  if (!verdict.ok) {
    // บันทึกเฉพาะเส้นทางกับระดับสิทธิ์ที่เห็น — ไม่มี token ไม่มีอีเมล ไม่มี uuid
    console.warn(`[webapi] ปฏิเสธ ${path} (${level}) — ผู้เรียก: ${describeForLog(context)}`);
    deny(res, verdict.status, verdict.body);
    return;
  }

  try {
    await send(res, await handler(request));
  } catch (err) {
    console.error(`[webapi] ${path} ล้มเหลว:`, err);
    if (!res.headersSent) {
      res.statusCode = 500;
      res.setHeader("content-type", "application/json; charset=utf-8");
    }
    res.end(JSON.stringify({ error: "internal error" }));
  }
});

server.listen(PORT, "0.0.0.0", () => {
  console.log(`[webapi] ฟังที่พอร์ต ${PORT} · ${handlers.size} เส้นทาง`);
});

// ---------------------------------------------------------------------
// ปิดอย่างเรียบร้อย
//
// ก่อนมี pool ของฐานข้อมูล การถูก SIGKILL ไม่ทำให้เสียอะไร จึงไม่เคยมีส่วนนี้
// ตอนนี้มี connection ค้างอยู่ฝั่ง PostgreSQL ที่ควรคืนให้เรียบร้อย
//
// ลำดับสำคัญ: หยุดรับคำขอใหม่ -> รอคำขอที่ทำอยู่ให้จบ -> ค่อยปิด pool
// ถ้าปิด pool ก่อน คำขอที่กำลังทำงานจะพังกลางคัน
// ---------------------------------------------------------------------
let closing = false;
async function shutdown(signal) {
  // docker compose down อาจส่งสัญญาณซ้ำ — ครั้งที่สองต้องไม่เริ่มงานซ้อน
  if (closing) return;
  closing = true;
  console.log(`[webapi] ได้รับ ${signal} — กำลังปิดอย่างเรียบร้อย`);

  // Docker ส่ง SIGKILL หลัง stop_grace_period (ค่าตั้งต้น 10 วินาที)
  // ออกเองก่อนถูกฆ่าดีกว่า เพราะอย่างน้อยได้พยายามคืน connection แล้ว
  const hardStop = setTimeout(() => {
    console.error("[webapi] ปิดไม่ทันใน 10 วินาที — ออกแบบบังคับ");
    process.exit(1);
  }, 10_000);
  hardStop.unref();

  server.close(async () => {
    try {
      if (database) await database.close();
    } catch (err) {
      console.error("[webapi] ปิด pool ไม่สำเร็จ:", err?.message ?? err);
    }
    clearTimeout(hardStop);
    process.exit(0);
  });
}

process.on("SIGTERM", () => shutdown("SIGTERM"));
process.on("SIGINT", () => shutdown("SIGINT"));
