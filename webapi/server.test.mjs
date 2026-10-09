/**
 * ชุดตรวจระดับ HTTP จริงของ server.mjs
 *
 *     node --test webapi/server.test.mjs
 *
 * ทำไมต้องมีชุดนี้แยกจาก auth.test.mjs
 * -----------------------------------
 * auth.test.mjs พิสูจน์ว่า "ตรรกะการตัดสินสิทธิ์ถูก" แต่ไม่ได้พิสูจน์ว่า server.mjs
 * เรียกใช้ตรรกะนั้นจริงก่อนส่งคำขอเข้าฟังก์ชัน ด่านที่ถูกต้องแต่ไม่ถูกเรียกใช้ก็ไม่กันอะไร
 * ชุดนี้จึงยิง HTTP เข้าเซิร์ฟเวอร์ที่รันอยู่จริง และตรวจว่า handler **ไม่ถูกเรียก**
 * เมื่อผู้เรียกไม่มีสิทธิ์
 *
 * ของจริง `api/` มาจากรีโปหน้าเว็บ ถูกคัดลอกเข้าตอน build (ดู Dockerfile) รีโปนี้
 * จึงไม่มีไฟล์เหล่านั้น ชุดนี้สร้างโฟลเดอร์ชั่วคราวที่มี handler ปลอมซึ่งบันทึกว่า
 * ตัวเองถูกเรียกหรือไม่ แล้วคัดลอก server.mjs กับ auth.mjs เข้าไปรันที่นั่น
 *
 * ไม่มี token จริง ไม่มีคีย์จริง ไม่ต่อ Supabase
 * ค่า env ที่ตั้งให้เป็นค่าสมมติ และ @supabase/supabase-js ไม่ได้ติดตั้งในรีโปนี้
 * ตัวตรวจ token จึงล้มทุกครั้ง ซึ่งเป็นสิ่งที่ต้องการ — ใช้พิสูจน์ว่าระบบ fail closed
 */
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { cp, mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test, { after, before } from "node:test";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const PORT = 56421;
const BASE = `http://127.0.0.1:${PORT}`;

// ค่าของ header HTTP ต้องเป็น latin-1 เท่านั้น (fetch โยน TypeError ถ้ามีอักขระ > 255)
// token สมมติจึงต้องเป็น ASCII — ห้ามใส่ภาษาไทยลงใน header
const FAKE_TOKEN = "not-a-real-token";

// handler ปลอมบันทึกการถูกเรียกลงไฟล์ เพื่อให้ชุดทดสอบอ่านได้จากนอกโปรเซส
const STUB = (name) => `export default {
  async fetch(request) {
    const { appendFileSync } = await import("node:fs");
    appendFileSync(process.env.CALL_LOG, ${JSON.stringify(name)} + "\\n");
    return Response.json({ handler: ${JSON.stringify(name)} });
  },
};
`;

let dir;
let child;
let callLog;

async function waitForServer(deadlineMs = 15000) {
  const until = Date.now() + deadlineMs;
  while (Date.now() < until) {
    try {
      const res = await fetch(`${BASE}/healthz`);
      if (res.ok) return;
    } catch {
      // ยังไม่ขึ้น
    }
    await new Promise((r) => setTimeout(r, 120));
  }
  throw new Error("เซิร์ฟเวอร์ทดสอบไม่ขึ้นภายในเวลาที่กำหนด");
}

const calls = async () => {
  try {
    return (await readFile(callLog, "utf8")).split("\n").filter(Boolean);
  } catch {
    return [];
  }
};

/**
 * วาง pg ปลอมไว้ใน node_modules ของโฟลเดอร์ทดสอบ
 *
 * ชุดนี้ไม่ได้ทดสอบฐานข้อมูลเลย และไม่ได้ตั้ง ADVISOR_WEB_PASSWORD ด้วย
 * db.mjs จึงไม่สร้าง pool อะไรทั้งสิ้น แต่ import ของมันต้องหาโมดูลเจอ
 *
 * ใช้ของปลอมแทนการคัดลอก node_modules จริงเพราะเร็วกว่ามากและทำให้เห็นชัดว่า
 * เส้นทางที่ทดสอบอยู่ไม่แตะฐานข้อมูล · ถ้าวันหนึ่งโค้ดเริ่มเรียก pg จริงในเส้นทางนี้
 * ของปลอมจะพังเสียงดัง ซึ่งเป็นสิ่งที่ต้องการ
 */
async function stubPg(root) {
  const dir = path.join(root, "node_modules", "pg");
  await mkdir(dir, { recursive: true });
  await writeFile(
    path.join(dir, "package.json"),
    JSON.stringify({ name: "pg", version: "0.0.0-stub", main: "index.js" }),
  );
  await writeFile(
    path.join(dir, "index.js"),
    [
      "class Pool {",
      "  constructor() {",
      "    throw new Error('ชุดทดสอบนี้ไม่ควรสร้าง pool จริง');",
      "  }",
      "}",
      "module.exports = { Pool };",
      "module.exports.default = { Pool };",
      "",
    ].join("\n"),
  );
}

before(async () => {
  dir = await mkdtemp(path.join(tmpdir(), "webapi-authz-"));
  callLog = path.join(dir, "calls.log");
  await writeFile(callLog, "");

  await mkdir(path.join(dir, "api", "admin"), { recursive: true });
  for (const name of ["sci-connect-news", "sci-connect-news-detail"]) {
    await writeFile(path.join(dir, "api", `${name}.js`), STUB(name));
  }
  for (const name of ["extract-file", "ingest", "sync-sci-news"]) {
    await writeFile(path.join(dir, "api", "admin", `${name}.js`), STUB(`admin/${name}`));
  }
  for (const file of ["server.mjs", "auth.mjs", "db.mjs"]) {
    await cp(path.join(HERE, file), path.join(dir, file));
  }
  await writeFile(path.join(dir, "package.json"), JSON.stringify({ type: "module" }));
  await stubPg(dir);

  child = spawn(process.execPath, ["server.mjs"], {
    cwd: dir,
    env: {
      ...process.env,
      PORT: String(PORT),
      CALL_LOG: callLog,
      // ค่าสมมติ ไม่ใช่ของโปรเจกต์จริง — มีไว้ให้ด่านถือว่า "ตั้งค่าครบ"
      VITE_SUPABASE_URL: "http://supabase.test.invalid",
      VITE_SUPABASE_ANON_KEY: "not-a-real-anon-key-for-tests-only",
    },
    stdio: ["ignore", "pipe", "pipe"],
  });
  child.stdout.resume();
  child.stderr.resume();
  await waitForServer();
});

after(async () => {
  // ต้องรอให้โปรเซสลูกออกก่อนลบโฟลเดอร์ — Windows ล็อก cwd ของโปรเซสที่ยังอยู่
  // แล้ว rmdir จะล้มด้วย EBUSY ทำให้ชุดทดสอบตกทั้งที่ข้อตรวจผ่านหมด
  if (child && child.exitCode === null && child.signalCode === null) {
    const exited = new Promise((resolve) => child.once("exit", resolve));
    child.kill("SIGKILL");
    await Promise.race([exited, new Promise((r) => setTimeout(r, 3000))]);
  }
  if (!dir) return;
  // ความล้มเหลวของการเก็บกวาดต้องไม่ถูกรายงานเป็นข้อตรวจที่ไม่ผ่าน
  for (let attempt = 0; attempt < 5; attempt += 1) {
    try {
      await rm(dir, { recursive: true, force: true });
      return;
    } catch {
      await new Promise((r) => setTimeout(r, 200));
    }
  }
  console.warn(`[test] ลบโฟลเดอร์ชั่วคราวไม่สำเร็จ: ${dir}`);
});

// =====================================================================

test("healthz ประกาศระดับสิทธิ์ของทุกเส้นทาง", async () => {
  const body = await (await fetch(`${BASE}/healthz`)).json();
  assert.equal(body.status, "ok");
  assert.equal(body.authConfigured, true);
  const byRoute = Object.fromEntries(body.routes.map((r) => [r.route, r.level]));
  assert.deepEqual(byRoute, {
    "/api/sci-connect-news-detail": "PUBLIC",
    "/api/sci-connect-news": "PUBLIC",
    "/api/admin/extract-file": "EDITOR",
    "/api/admin/ingest": "EDITOR",
    "/api/admin/sync-sci-news": "EDITOR",
  });
});

test("เส้นทางสาธารณะ เรียกได้โดยไม่ต้องมี token และ handler ถูกเรียกจริง", async () => {
  const before = (await calls()).length;
  const res = await fetch(`${BASE}/api/sci-connect-news`);
  assert.equal(res.status, 200);
  assert.deepEqual(await res.json(), { handler: "sci-connect-news" });
  assert.equal((await calls()).length, before + 1, "handler ต้องถูกเรียก");
});

test("C2 เส้นทางสาธารณะ + header พัง หรือ token ใช้ไม่ได้ ยังได้ 200 และ handler ถูกเรียก", async () => {
  // ข้อนี้คือหัวใจของ C2 — เนื้อหาสาธารณะต้องไม่ถูกปิดเพราะ header ที่ติดมา
  for (const authorization of [
    "Basic dXNlcjpwYXNz",
    "Bearer",
    "no-bearer-prefix",
    `Bearer ${FAKE_TOKEN}`,
  ]) {
    const before = (await calls()).length;
    const res = await fetch(`${BASE}/api/sci-connect-news`, { headers: { authorization } });
    assert.equal(res.status, 200, authorization);
    assert.deepEqual(await res.json(), { handler: "sci-connect-news" });
    assert.equal((await calls()).length, before + 1, `handler ต้องถูกเรียก (${authorization})`);
  }
});

test("เส้นทาง EDITOR ไม่มี token ได้ 401 และ handler ไม่ถูกเรียกเลย", async () => {
  const before = await calls();
  for (const route of ["/api/admin/ingest", "/api/admin/extract-file", "/api/admin/sync-sci-news"]) {
    const res = await fetch(`${BASE}${route}`, { method: "POST" });
    assert.equal(res.status, 401, route);
    assert.deepEqual(await res.json(), { error: "Unauthorized" });
  }
  // ข้อสำคัญที่สุดของชุดนี้ — ด่านต้องกันก่อนถึงฟังก์ชัน ไม่ใช่กันทีหลัง
  assert.deepEqual(await calls(), before, "handler ต้องไม่ถูกเรียกแม้ครั้งเดียว");
});

test("เส้นทาง EDITOR ที่มี token ซึ่งตรวจไม่ผ่าน ได้ 401 และ handler ไม่ถูกเรียก", async () => {
  // ตัวตรวจจะล้มเพราะ @supabase/supabase-js ไม่ได้ติดตั้งในรีโปนี้
  // ผลที่ต้องได้คือ "ปฏิเสธ" ไม่ใช่ "ปล่อยผ่านเพราะตรวจไม่ได้"
  const before = await calls();
  const res = await fetch(`${BASE}/api/admin/ingest`, {
    method: "POST",
    headers: { authorization: `Bearer ${FAKE_TOKEN}` },
  });
  assert.equal(res.status, 401);
  assert.deepEqual(await res.json(), { error: "Unauthorized" });
  assert.deepEqual(await calls(), before, "handler ต้องไม่ถูกเรียก");
});

test("header ผิดรูปแบบ ได้ 401 และ handler ไม่ถูกเรียก", async () => {
  const before = await calls();
  for (const authorization of ["Basic abc", "Bearer", "no-bearer-prefix", "Bearer a b"]) {
    const res = await fetch(`${BASE}/api/admin/ingest`, {
      method: "POST",
      headers: { authorization },
    });
    assert.equal(res.status, 401, authorization);
  }
  assert.deepEqual(await calls(), before);
});

test("ค่าใน body ที่อ้างว่าเป็น admin ไม่ทำให้ผ่าน", async () => {
  const before = await calls();
  const res = await fetch(`${BASE}/api/admin/ingest`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ role: "admin", status: "approved", user_id: "u-admin" }),
  });
  assert.equal(res.status, 401);
  assert.deepEqual(await calls(), before, "handler ต้องไม่ถูกเรียก");
});

test("เส้นทางที่ไม่รู้จัก ได้ 404", async () => {
  const res = await fetch(`${BASE}/api/ไม่มีเส้นทางนี้`);
  assert.equal(res.status, 404);
  assert.deepEqual(await res.json(), { error: "not found" });
});

test("เส้นทางที่ไม่ประกาศระดับสิทธิ์ ทำให้บริการไม่ยอมเริ่มทำงาน", async () => {
  // กฎสำคัญที่สุดของด่านนี้ — ถ้าบริการยังขึ้นได้ทั้งที่มีเส้นทางไม่ประกาศระดับ
  // เส้นทางนั้นจะเปิดโล่ง และคนที่เจอก่อนอาจเป็นผู้ใช้ที่ไม่ควรเข้าถึง
  const alt = await mkdtemp(path.join(tmpdir(), "webapi-undeclared-"));
  try {
    await mkdir(path.join(alt, "api", "admin"), { recursive: true });
    await writeFile(path.join(alt, "api", "oops.js"), STUB("oops"));
    for (const file of ["server.mjs", "auth.mjs", "db.mjs"]) {
      await cp(path.join(HERE, file), path.join(alt, file));
    }
    await writeFile(path.join(alt, "package.json"), JSON.stringify({ type: "module" }));
    await stubPg(alt);

    // เพิ่มเส้นทางที่ "ไม่มีระดับสิทธิ์" เข้าไปในตาราง
    const src = await readFile(path.join(alt, "server.mjs"), "utf8");
    const broken = src.replace(
      "const ROUTES = [",
      'const ROUTES = [\n  ["/api/oops", "./api/oops.js"],',
    );
    assert.notEqual(broken, src, "ต้องแก้ตาราง ROUTES ได้");
    await writeFile(path.join(alt, "server.mjs"), broken);

    const proc = spawn(process.execPath, ["server.mjs"], {
      cwd: alt,
      env: { ...process.env, PORT: String(PORT + 1), CALL_LOG: path.join(alt, "calls.log") },
      stdio: ["ignore", "pipe", "pipe"],
    });
    let stderr = "";
    proc.stderr.on("data", (chunk) => {
      stderr += String(chunk);
    });
    proc.stdout.resume();

    const code = await new Promise((resolve) => proc.once("exit", resolve));
    assert.equal(code, 1, "ต้องออกด้วยรหัส 1 ไม่ใช่เริ่มรับคำขอ");
    assert.match(stderr, /\/api\/oops/, "ต้องบอกชื่อเส้นทางที่ผิดใน stderr");
  } finally {
    for (let attempt = 0; attempt < 5; attempt += 1) {
      try {
        await rm(alt, { recursive: true, force: true });
        break;
      } catch {
        await new Promise((r) => setTimeout(r, 200));
      }
    }
  }
});

test("ข้อความตอบกลับไม่มี token ไม่มีคีย์ ไม่มีรายละเอียดภายใน", async () => {
  const responses = [
    await fetch(`${BASE}/api/admin/ingest`, { method: "POST" }),
    await fetch(`${BASE}/api/admin/ingest`, {
      method: "POST",
      headers: { authorization: `Bearer ${FAKE_TOKEN}` },
    }),
    await fetch(`${BASE}/api/ไม่มีเส้นทางนี้`),
  ];
  for (const res of responses) {
    const text = await res.text();
    assert.equal(
      /supabase|anon|jwt|Bearer|stack|at Object|not-a-real/i.test(text),
      false,
      text,
    );
  }
});
