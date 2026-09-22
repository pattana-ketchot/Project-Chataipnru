/**
 * ตัวครอบฟังก์ชันของหน้าเว็บให้รันเป็นบริการเดียวบนเซิร์ฟเวอร์ของเราเอง
 *
 * ฟังก์ชันใน api/ เขียนตามสัญญาแบบเว็บมาตรฐาน คือ `export default { fetch(Request): Response }`
 * ซึ่งเดิมรันบนแพลตฟอร์มไร้เซิร์ฟเวอร์ ไฟล์นี้แปลงคำขอของ Node ให้เป็น Request แล้วส่งเข้า
 * ฟังก์ชันเดิมโดยไม่แก้ตัวฟังก์ชันเลยแม้แต่บรรทัดเดียว — ของเพื่อนยังเป็นของเพื่อนทุกอย่าง
 *
 * เส้นทางที่บริการนี้รับผิดชอบมีเพียง 5 เส้นทาง นอกนั้น Caddy ส่งไป FastAPI เหมือนเดิม
 */
import http from "node:http";
import { Readable } from "node:stream";

const PORT = Number(process.env.PORT || 3001);

// เส้นทาง -> ไฟล์ฟังก์ชันของเพื่อน (พาธเทียบกับโฟลเดอร์นี้)
const ROUTES = [
  ["/api/sci-connect-news-detail", "./api/sci-connect-news-detail.js"],
  ["/api/sci-connect-news", "./api/sci-connect-news.js"],
  ["/api/admin/extract-file", "./api/admin/extract-file.js"],
  ["/api/admin/ingest", "./api/admin/ingest.js"],
  ["/api/admin/sync-sci-news", "./api/admin/sync-sci-news.js"],
];

const handlers = new Map();
for (const [route, file] of ROUTES) {
  try {
    const mod = await import(file);
    if (typeof mod.default?.fetch !== "function") {
      console.error(`[webapi] ${file} ไม่มี default.fetch — ข้ามเส้นทาง ${route}`);
      continue;
    }
    handlers.set(route, mod.default.fetch);
    console.log(`[webapi] พร้อมให้บริการ ${route}`);
  } catch (err) {
    console.error(`[webapi] โหลด ${file} ไม่สำเร็จ: ${err.message}`);
  }
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
    res.setHeader("content-type", "application/json; charset=utf-8");
    res.end(JSON.stringify({ status: "ok", routes: [...handlers.keys()] }));
    return;
  }

  const entry = [...handlers.entries()].find(([route]) => path === route || path.startsWith(route + "/"));
  if (!entry) {
    res.statusCode = 404;
    res.setHeader("content-type", "application/json; charset=utf-8");
    res.end(JSON.stringify({ error: "not found" }));
    return;
  }

  try {
    await send(res, await entry[1](toRequest(req)));
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
