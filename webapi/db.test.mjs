/**
 * ชุดตรวจชั้นฐานข้อมูลของ webapi (M3)
 *
 *     cd webapi && npm test
 *
 * ชุดนี้ไม่ต้องมี PostgreSQL จริง
 * -----------------------------
 * `createIdentityResolver` รับ pool เข้ามาเป็นพารามิเตอร์ จึงใส่ของปลอมที่ตอบ
 * ตามที่กำหนดได้ · สิ่งที่พิสูจน์ที่นี่คือ **ตรรกะการตัดสิน** ว่าเมื่อไหร่ยอมรับและ
 * เมื่อไหร่ปฏิเสธ ซึ่งไม่ต้องใช้ฐานข้อมูลก็พิสูจน์ได้ และพิสูจน์ได้ครบกว่าด้วย
 * (เคส "เจอสองแถว" สร้างในฐานข้อมูลจริงไม่ได้เพราะมี unique index กันอยู่)
 *
 * ส่วนที่ต้องใช้ฐานข้อมูลจริง — สิทธิ์ของ advisor_web และการต่อด้วยรหัสผ่านผิด —
 * อยู่ในคอนเทนเนอร์ทิ้งแยกต่างหาก ดู docs/M3_WEBAPI_POSTGRES_IMPLEMENTATION_RESULT.md
 *
 * ไม่มีรหัสผ่านจริง ไม่มี uuid จริง ไม่มีอีเมลจริงในไฟล์นี้
 */
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import {
  ACCOUNT_INACTIVE,
  ACCOUNT_NOT_LINKED,
  DATABASE_NOT_CONFIGURED,
  IDENTITY_LOOKUP_FAILED,
  MAPPING_AMBIGUOUS,
  POOL_SETTINGS,
  RESOLVER_SQL,
  createIdentityResolver,
  createPool,
  dbEnv,
  describeConnection,
  makeCloser,
} from "./db.mjs";
import { resolveAuthContext } from "./auth.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));

/** uuid สมมติ ไม่ใช่ของผู้ใช้จริงคนใด */
const FAKE_SUPABASE_ID = "11111111-2222-3333-4444-555555555555";
const FAKE_LOCAL_ID = "99999999-8888-7777-6666-555555555555";

/** pool ปลอมที่ตอบตามที่กำหนด และจำว่าถูกเรียกด้วยอะไร */
function fakePool(answer) {
  const calls = [];
  return {
    calls,
    async query(sql, params) {
      calls.push({ sql, params });
      if (answer instanceof Error) throw answer;
      return answer;
    },
  };
}

const activeRow = { id: FAKE_LOCAL_ID, is_active: true, supabase_user_id: FAKE_SUPABASE_ID };

// =====================================================================
// C · D · E — ผลการแปลงตัวตนแต่ละกรณี
// =====================================================================

test("C — เจอหนึ่งคนและยังใช้งานอยู่ ถือว่าสำเร็จ", async () => {
  const resolver = createIdentityResolver(fakePool({ rows: [activeRow] }));
  const got = await resolver.resolveLocalUser(FAKE_SUPABASE_ID);
  assert.equal(got.ok, true);
  assert.equal(got.localUserId, FAKE_LOCAL_ID);
});

test("D — ไม่เจอใครเลย ปฏิเสธด้วย ACCOUNT_NOT_LINKED", async () => {
  const resolver = createIdentityResolver(fakePool({ rows: [] }));
  const got = await resolver.resolveLocalUser(FAKE_SUPABASE_ID);
  assert.equal(got.ok, false);
  assert.equal(got.reason, ACCOUNT_NOT_LINKED);
  assert.equal("localUserId" in got, false, "ปฏิเสธแล้วต้องไม่มี id ติดมา");
});

test("E — เจอแต่บัญชีถูกปิด ปฏิเสธด้วย ACCOUNT_INACTIVE", async () => {
  const resolver = createIdentityResolver(fakePool({ rows: [{ ...activeRow, is_active: false }] }));
  const got = await resolver.resolveLocalUser(FAKE_SUPABASE_ID);
  assert.equal(got.ok, false);
  assert.equal(got.reason, ACCOUNT_INACTIVE);
  assert.equal("localUserId" in got, false);
});

test("is_active ที่ไม่ใช่ true เป๊ะ ๆ ก็ถือว่าปิด", async () => {
  // null / undefined / "true" ล้วนไม่ใช่ true — ต้องไม่ถูกตีความว่าเปิดใช้งาน
  for (const value of [null, undefined, "true", 1, 0]) {
    const resolver = createIdentityResolver(fakePool({ rows: [{ ...activeRow, is_active: value }] }));
    const got = await resolver.resolveLocalUser(FAKE_SUPABASE_ID);
    assert.equal(got.ok, false, `is_active = ${String(value)}`);
    assert.equal(got.reason, ACCOUNT_INACTIVE);
  }
});

test("เจอสองแถว ปฏิเสธด้วย MAPPING_AMBIGUOUS — ห้ามเลือกแถวแรก", async () => {
  const resolver = createIdentityResolver(
    fakePool({ rows: [activeRow, { ...activeRow, id: "ไม่ควรถูกเลือก" }] }),
  );
  const got = await resolver.resolveLocalUser(FAKE_SUPABASE_ID);
  assert.equal(got.ok, false);
  assert.equal(got.reason, MAPPING_AMBIGUOUS);
  assert.equal("localUserId" in got, false);
});

test("ฐานข้อมูลผิดพลาด ปฏิเสธด้วย IDENTITY_LOOKUP_FAILED และไม่รั่วรายละเอียดภายใน", async () => {
  const resolver = createIdentityResolver(fakePool(new Error("connection refused ที่ 10.1.2.3")));
  const got = await resolver.resolveLocalUser(FAKE_SUPABASE_ID);
  assert.equal(got.ok, false);
  assert.equal(got.reason, IDENTITY_LOOKUP_FAILED);
  assert.ok(!/10\.1\.2\.3/.test(JSON.stringify(got)), "ห้ามส่งรายละเอียดภายในออกไปหาผู้เรียก");
});

test("ไม่ได้ตั้งค่าฐานข้อมูล ปฏิเสธด้วย DATABASE_NOT_CONFIGURED", async () => {
  const resolver = createIdentityResolver(null);
  const got = await resolver.resolveLocalUser(FAKE_SUPABASE_ID);
  assert.equal(got.ok, false);
  assert.equal(got.reason, DATABASE_NOT_CONFIGURED);
});

test("ไม่มีรหัสผู้ใช้ให้ค้นหา ปฏิเสธโดยไม่ไปแตะฐานข้อมูล", async () => {
  const pool = fakePool({ rows: [activeRow] });
  const resolver = createIdentityResolver(pool);
  for (const value of ["", null, undefined, 123, {}]) {
    const got = await resolver.resolveLocalUser(value);
    assert.equal(got.ok, false, String(value));
    assert.equal(got.reason, ACCOUNT_NOT_LINKED);
  }
  assert.equal(pool.calls.length, 0, "ค่าที่ใช้ไม่ได้ต้องไม่ถูกส่งไปถามฐานข้อมูล");
});

// =====================================================================
// F — ค่าที่ผู้ใช้ส่งมาต้องเป็น parameter เสมอ
// =====================================================================

test("F — ค่าหน้าตาเหมือน SQL ยังคงเป็น parameter และ SQL ไม่เปลี่ยนรูป", async () => {
  const attacks = [
    "' OR '1'='1",
    "' OR 1=1 --",
    "'; DROP TABLE public.users; --",
    `${FAKE_SUPABASE_ID}' UNION SELECT email FROM public.users --`,
  ];
  for (const attack of attacks) {
    const pool = fakePool({ rows: [] });
    const resolver = createIdentityResolver(pool);
    const got = await resolver.resolveLocalUser(attack);

    assert.equal(got.ok, false, attack);
    assert.equal(pool.calls.length, 1);
    const { sql, params } = pool.calls[0];
    assert.equal(sql, RESOLVER_SQL, "SQL ต้องไม่เปลี่ยนรูปตามค่าที่ส่งเข้ามา");
    assert.deepEqual(params, [attack], "ค่าต้องเดินทางเป็น parameter เท่านั้น");
    assert.ok(!sql.includes(attack), "ค่าต้องไม่ถูกต่อเข้าไปในตัว SQL");
  }
});

test("SQL ของ resolver ใช้ $1 และไม่มีคำว่า email อยู่เลย", () => {
  assert.ok(RESOLVER_SQL.includes("$1"), "ต้องใช้ parameter ไม่ใช่ต่อสตริง");
  assert.ok(!/email/i.test(RESOLVER_SQL), "ห้ามมี fallback ด้วยอีเมล");
  assert.ok(!/is_admin/i.test(RESOLVER_SQL), "ห้ามมี fallback เป็นผู้ดูแลระบบ");
  assert.ok(!/INSERT|UPDATE|DELETE/i.test(RESOLVER_SQL), "ตัวแปลงตัวตนต้องอ่านอย่างเดียว");
  assert.ok(/WHERE\s+supabase_user_id\s*=\s*\$1/i.test(RESOLVER_SQL));
});

test("ไฟล์ db.mjs ไม่มี fallback ที่ห้ามไว้", async () => {
  const src = await readFile(path.join(HERE, "db.mjs"), "utf8");
  const statements = src
    .split("\n")
    .filter((line) => !line.trimStart().startsWith("*") && !line.trimStart().startsWith("//"))
    .join("\n");
  assert.ok(!/\bauto[-_]?create\b/i.test(statements));
  assert.ok(!/INSERT\s+INTO/i.test(statements), "ห้ามสร้างผู้ใช้ใหม่");
  assert.ok(!/\bfrom\s+public\.users\b[\s\S]*\bemail\b/i.test(statements));
});

// =====================================================================
// I — ปิด pool ซ้ำได้
// =====================================================================

test("I — closePool เรียกซ้ำได้ และ pool.end ถูกเรียกครั้งเดียว", async () => {
  let ends = 0;
  const close = makeCloser({
    async end() {
      ends += 1;
    },
  });
  assert.equal(await close(), true, "ครั้งแรกต้องปิดจริง");
  assert.equal(await close(), false, "ครั้งที่สองต้องไม่ทำอะไร");
  assert.equal(await close(), false);
  assert.equal(ends, 1, "pool.end ต้องถูกเรียกครั้งเดียว");
});

test("closePool ไม่พังเมื่อไม่มี pool", async () => {
  const close = makeCloser(null);
  assert.equal(await close(), true);
  assert.equal(await close(), false);
});

// =====================================================================
// การตั้งค่า
// =====================================================================

test("dbEnv คืน null เมื่อไม่มีรหัสผ่าน — ไม่มีค่าเริ่มต้นให้ความลับ", () => {
  assert.equal(dbEnv({}), null);
  assert.equal(dbEnv({ ADVISOR_WEB_PASSWORD: "" }), null);
  assert.equal(dbEnv({ WEBAPI_DB_HOST: "postgres" }), null);
});

test("dbEnv ใช้ค่าเริ่มต้นที่ยืนยันมาจาก compose จริงสำหรับค่าที่ไม่ลับ", () => {
  const got = dbEnv({ ADVISOR_WEB_PASSWORD: "ไม่ใช่รหัสผ่านจริง" });
  assert.equal(got.host, "postgres");
  assert.equal(got.port, 5432);
  assert.equal(got.database, "course_advisor");
  assert.equal(got.user, "advisor_web");
});

test("dbEnv ปฏิเสธพอร์ตที่ใช้ไม่ได้ แทนที่จะเงียบ ๆ ใช้ค่าเริ่มต้น", () => {
  for (const port of ["ไม่ใช่ตัวเลข", "0", "70000", "-1"]) {
    assert.equal(dbEnv({ ADVISOR_WEB_PASSWORD: "x", WEBAPI_DB_PORT: port }), null, port);
  }
});

test("describeConnection ไม่มีรหัสผ่านอยู่ในข้อความ", () => {
  const secret = "รหัสผ่านที่ต้องไม่โผล่";
  const text = describeConnection({
    host: "postgres",
    port: 5432,
    database: "course_advisor",
    user: "advisor_web",
    password: secret,
  });
  assert.ok(!text.includes(secret), "ข้อความสำหรับ log ต้องไม่มีรหัสผ่าน");
  assert.equal(text, "advisor_web@postgres:5432/course_advisor");
});

test("ค่าตั้งของ pool ตรงตามที่ออกแบบไว้", () => {
  assert.equal(POOL_SETTINGS.max, 5);
  assert.equal(POOL_SETTINGS.connectionTimeoutMillis, 5_000);
  assert.equal(POOL_SETTINGS.idleTimeoutMillis, 30_000);
  assert.equal(POOL_SETTINGS.statement_timeout, 5_000);
  assert.equal(POOL_SETTINGS.query_timeout, 5_000);
  assert.equal(POOL_SETTINGS.idle_in_transaction_session_timeout, 10_000);
  assert.equal(POOL_SETTINGS.application_name, "webapi");
});

test("createPool ส่งค่าตั้งทั้งหมดต่อให้ pool และดัก error ของ client ที่ว่างอยู่", () => {
  let got = null;
  let handled = null;
  class FakePool {
    constructor(config) {
      got = config;
    }
    on(event, handler) {
      handled = event;
      handler(new Error("ทดสอบ"));
    }
  }
  createPool({ host: "h", port: 1, database: "d", user: "u", password: "p" }, FakePool);
  assert.equal(got.max, 5);
  assert.equal(got.application_name, "webapi");
  assert.equal(got.user, "u");
  assert.equal(handled, "error", "ต้องดัก error ไม่งั้นทั้งกระบวนการตาย");
});

// =====================================================================
// การตั้งค่าที่ต้องไม่หลุด — ตรวจตัวไฟล์เอง
// =====================================================================

test("Dockerfile คัดลอก db.mjs เข้า image", async () => {
  const dockerfile = await readFile(path.join(HERE, "Dockerfile"), "utf8");
  const copyLine = dockerfile
    .split("\n")
    .find((line) => line.startsWith("COPY") && line.includes("server.mjs"));
  assert.ok(copyLine, "ต้องมีบรรทัด COPY ที่คัดลอก server.mjs");
  for (const file of ["server.mjs", "auth.mjs", "db.mjs"]) {
    assert.ok(copyLine.includes(file), `บรรทัด COPY ต้องมี ${file} ไม่งั้นคอนเทนเนอร์พังตอนขึ้น`);
  }
});

test("Dockerfile ใช้ npm ci กับ lock file ที่ไม่ใช่ glob", async () => {
  const dockerfile = await readFile(path.join(HERE, "Dockerfile"), "utf8");
  assert.ok(/npm ci\b/.test(dockerfile), "ต้องใช้ npm ci เพื่อให้ได้ไลบรารีชุดเดียวกับที่ทดสอบ");
  assert.ok(!/package-lock\.json\*/.test(dockerfile), "ห้ามใช้ glob — lock file หายต้องล้มเสียงดัง");
});

test("pg อยู่ใน dependencies ไม่ใช่ devDependencies", async () => {
  const pkg = JSON.parse(await readFile(path.join(HERE, "package.json"), "utf8"));
  assert.ok(pkg.dependencies?.pg, "pg ต้องอยู่ใน dependencies เพราะ image ติดตั้งด้วย --omit=dev");
  assert.equal(pkg.devDependencies?.pg, undefined);
});

test("package-lock.json ตรึงเวอร์ชันของ pg ไว้", async () => {
  const lock = JSON.parse(await readFile(path.join(HERE, "package-lock.json"), "utf8"));
  const entry = lock.packages?.["node_modules/pg"];
  assert.ok(entry?.version, "lock file ต้องตรึงเวอร์ชันของ pg");
  assert.ok(/^\d+\.\d+\.\d+$/.test(entry.version), `เวอร์ชันต้องเป็นค่าที่ตรึงแล้ว ได้ ${entry.version}`);
});

// =====================================================================
// บั๊ก lastIdentity — ตัวตนของคำขอหนึ่งต้องถูกคำขออื่นทับไม่ได้
// =====================================================================

test("auth.mjs ไม่เก็บ identity ไว้ในตัวแปรร่วมของ closure อีกต่อไป", async () => {
  const src = await readFile(path.join(HERE, "auth.mjs"), "utf8");
  const body = src.slice(src.indexOf("export function createRuntimeDeps"));
  const impl = body.slice(0, body.indexOf("\n}\n") + 3);
  assert.ok(!/\blet\s+lastIdentity\b/.test(impl), "ห้ามมีตัวแปรร่วมที่คำขออื่นทับได้");
  assert.ok(
    /readProfile\(userId,\s*identity\)/.test(impl),
    "readProfile ต้องรับ identity ของคำขอนั้นเข้ามาตรง ๆ",
  );
});

test("คำขอสองรายการที่ทับเวลากัน ต่างคนต่างใช้ identity ของตัวเอง", async () => {
  // จำลองลำดับที่เคยทำให้บั๊กเก่าโผล่
  //   A: verifyToken  ->  B: verifyToken  ->  A: readProfile  ->  B: readProfile
  // ถ้ายังเก็บ identity ไว้ในตัวแปรร่วม A จะได้ของ B
  const order = [];
  const profiles = { "user-A": "admin", "user-B": "editor" };

  const deps = {
    async verifyToken(token) {
      const userId = token === "token-A" ? "user-A" : "user-B";
      order.push(`verify:${userId}`);
      // ให้ A รอ เพื่อให้ B แทรกเข้ามาระหว่างกลางได้จริง
      await new Promise((r) => setTimeout(r, userId === "user-A" ? 20 : 0));
      return { userId, boundTo: userId };
    },
    async readProfile(userId, identity) {
      order.push(`profile:${userId}`);
      // จุดชี้ขาด: identity ที่ได้มาต้องเป็นของผู้ใช้คนเดียวกับ userId
      if (identity?.boundTo !== userId) return null;
      return { role: profiles[userId], status: "approved" };
    },
  };

  const request = (token) => ({ headers: { get: () => `Bearer ${token}` } });
  const [a, b] = await Promise.all([
    resolveAuthContext(request("token-A"), deps),
    resolveAuthContext(request("token-B"), deps),
  ]);

  assert.equal(a.context.userId, "user-A");
  assert.equal(a.context.role, "admin", "A ต้องได้สิทธิ์ของ A ไม่ใช่ของ B");
  assert.equal(b.context.userId, "user-B");
  assert.equal(b.context.role, "editor", "B ต้องได้สิทธิ์ของ B");
  assert.ok(order.length === 4, `ลำดับที่เกิดขึ้นจริง: ${order.join(" ")}`);
});

test("identity ไม่หลุดออกไปอยู่ใน context ที่ส่งต่อให้ด่านตรวจสิทธิ์", async () => {
  const deps = {
    async verifyToken() {
      return { userId: "user-A", supabase: { ความลับ: "ไม่ควรหลุด" } };
    },
    async readProfile() {
      return { role: "admin", status: "approved" };
    },
  };
  const got = await resolveAuthContext({ headers: { get: () => "Bearer t" } }, deps);
  assert.deepEqual(Object.keys(got.context).sort(), ["authenticated", "role", "status", "userId"]);
  assert.ok(!JSON.stringify(got.context).includes("ไม่ควรหลุด"));
});
