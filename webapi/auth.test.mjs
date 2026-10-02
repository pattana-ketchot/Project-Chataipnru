/**
 * ชุดตรวจด่านสิทธิ์ของ webapi
 *
 *     node --test webapi/
 *
 * ไม่แตะ Supabase จริงแม้ครั้งเดียว
 * -------------------------------
 * resolveAuthContext รับ verifyToken / readProfile เข้ามาเป็นพารามิเตอร์ ชุดนี้จึงส่ง
 * ตัวปลอมที่ตอบจากตารางในไฟล์นี้เอง ไม่มี token จริง ไม่มีคีย์ ไม่มีการต่อเน็ต
 * และไม่ต้องติดตั้ง @supabase/supabase-js เพื่อรันชุดนี้
 *
 * token ทุกตัวในไฟล์นี้เป็นสตริงสมมติที่ตั้งชื่อให้อ่านรู้ว่าแทนใคร
 * ไม่ใช่ token ของใครจริง และไม่ใช่รูปแบบ JWT ด้วยซ้ำ
 */
import assert from "node:assert/strict";
import test from "node:test";

import {
  ADMIN,
  ANONYMOUS,
  ANONYMOUS_AUTH_FAILED,
  APPROVED_STATUS,
  AUTHENTICATED,
  EDITOR,
  LEVELS,
  PUBLIC,
  PUBLIC_FILTERED,
  ACTIVE_USER_MAPPING_REQUIRED,
  authorFieldsFor,
  authorize,
  describeForLog,
  isPrivileged,
  needsAuthContext,
  parseBearer,
  resolveAuthContext,
  resolveAuthorId,
  stripAuthorFields,
  validateRouteTable,
} from "./auth.mjs";

// ---- โลกสมมติ: ใครถือ token อะไร และมี role/status อะไร ----
const USERS = {
  "token-admin-approved": { userId: "u-admin", role: "admin", status: "approved" },
  "token-editor-approved": { userId: "u-editor", role: "editor", status: "approved" },
  "token-user-approved": { userId: "u-user", role: "user", status: "approved" },
  "token-admin-pending": { userId: "u-admin-pending", role: "admin", status: "pending" },
  "token-editor-pending": { userId: "u-editor-pending", role: "editor", status: "pending" },
  // ผู้ใช้ที่ยืนยันตัวตนได้แต่ไม่มีแถวใน user_profiles เลย
  "token-no-profile": { userId: "u-ghost", role: null, status: null, missingProfile: true },
};

const deps = {
  async verifyToken(token) {
    const found = USERS[token];
    return found ? { userId: found.userId } : null;
  },
  async readProfile(userId) {
    const found = Object.values(USERS).find((u) => u.userId === userId);
    if (!found || found.missingProfile) return null;
    return { role: found.role, status: found.status };
  },
};

/** คำขอปลอมที่มีแค่ headers.get() ซึ่งเป็นสิ่งเดียวที่ด่านใช้ */
const requestWith = (authorization) => ({
  headers: { get: (name) => (name.toLowerCase() === "authorization" ? authorization : null) },
});

/** ลัดขั้นตอน: จาก header ไปถึงคำตัดสินของระดับหนึ่ง */
async function verdictFor(authorization, level) {
  const resolved = await resolveAuthContext(requestWith(authorization), deps);
  if (!resolved.ok) return { status: resolved.status, body: resolved.body };
  const decided = authorize(resolved.context, level);
  return decided.ok ? { status: 200 } : { status: decided.status, body: decided.body };
}

const bearer = (token) => `Bearer ${token}`;

// =====================================================================
// 10 ข้อที่กำหนดไว้
// =====================================================================

test("1. ไม่มี token แล้วเรียกเส้นทางที่ต้องมีสิทธิ์ ได้ 401", async () => {
  for (const level of [AUTHENTICATED, EDITOR, ADMIN]) {
    const got = await verdictFor(null, level);
    assert.equal(got.status, 401, `ระดับ ${level}`);
    assert.deepEqual(got.body, { error: "Unauthorized" });
  }
});

test("1b. ไม่มี token แต่เรียกเส้นทางสาธารณะ ผ่านได้", async () => {
  for (const level of [PUBLIC, PUBLIC_FILTERED]) {
    assert.equal((await verdictFor(null, level)).status, 200, `ระดับ ${level}`);
  }
});

test("2. token ที่ใช้ไม่ได้ ได้ 401", async () => {
  const got = await verdictFor(bearer("token-ที่ไม่มีในระบบ"), EDITOR);
  assert.equal(got.status, 401);
  assert.deepEqual(got.body, { error: "Unauthorized" });
});

// =====================================================================
// C2 — ข้อมูลยืนยันตัวตนที่ใช้ไม่ได้ ต้องไม่ทำให้เส้นทางสาธารณะใช้งานไม่ได้
//
// เดิมด่านนี้ตอบ 401 ทุกระดับเมื่อ header พังหรือ token ใช้ไม่ได้ ซึ่งทำให้เนื้อหา
// สาธารณะใช้งานไม่ได้เพียงเพราะมี header ติดมา — เป็น breaking behavior ใหม่ที่
// ไม่จำเป็นกับงาน foundation จึงเปลี่ยนให้ "ลดระดับเป็น anonymous" แทน
//
// ข้อสำคัญ: ลดระดับได้แค่เป็น anonymous เท่านั้น ห้ามได้สิทธิ์ใด ๆ
// =====================================================================

const BROKEN_CREDENTIALS = [
  ["header พัง: Basic", "Basic dXNlcjpwYXNz"],
  ["header พัง: Bearer เปล่า", "Bearer"],
  ["header พัง: ไม่มีคำว่า Bearer", "token-admin-approved"],
  ["header พัง: ช่องว่างเกิน", "Bearer  token-admin-approved"],
  ["token ที่ไม่มีในระบบ", "Bearer token-ที่ไม่มีในระบบ"],
];

test("C2 ข้อ 1-2. PUBLIC + header พัง หรือ token ใช้ไม่ได้ ยังผ่าน", async () => {
  for (const [label, header] of BROKEN_CREDENTIALS) {
    const got = await verdictFor(header, PUBLIC);
    assert.equal(got.status, 200, label);
  }
});

test("C2 ข้อ 3-4. PUBLIC_FILTERED + header พัง หรือ token ใช้ไม่ได้ ยังผ่านในฐานะ anonymous", async () => {
  for (const [label, header] of BROKEN_CREDENTIALS) {
    const resolved = await resolveAuthContext(requestWith(header), deps);
    assert.equal(resolved.ok, true, label);
    assert.equal(authorize(resolved.context, PUBLIC_FILTERED).ok, true, label);

    // ต้องเป็น anonymous จริง ๆ ไม่ใช่แค่ผ่านด่าน
    assert.equal(resolved.context.authenticated, false, label);
    assert.equal(resolved.context.role, null, label);
    assert.equal(resolved.context.status, null, label);
    assert.equal(resolved.context.userId, null, label);

    // และต้องไม่ได้สิทธิ์พิเศษ -> endpoint ที่กรองข้อมูลจะกรองให้คนทั่วไป
    assert.equal(isPrivileged(resolved.context), false, label);
  }
});

test("C2 ข้อ 5-8. AUTHENTICATED / EDITOR / ADMIN + header พัง หรือ token ใช้ไม่ได้ ยังได้ 401", async () => {
  for (const [label, header] of BROKEN_CREDENTIALS) {
    for (const level of [AUTHENTICATED, EDITOR, ADMIN]) {
      const got = await verdictFor(header, level);
      assert.equal(got.status, 401, `${label} ที่ระดับ ${level}`);
      assert.deepEqual(got.body, { error: "Unauthorized" });
    }
  }
});

test("C2 ข้อมูลยืนยันตัวตนที่ใช้ไม่ได้ เพิ่ม role หรือ status ให้ตัวเองไม่ได้", async () => {
  for (const [label, header] of BROKEN_CREDENTIALS) {
    const resolved = await resolveAuthContext(requestWith(header), deps);
    // context ที่ได้ต้องเท่ากับ anonymous ทุกฟิลด์ที่ใช้ตัดสินสิทธิ์
    const { authenticated, userId, role, status } = resolved.context;
    assert.deepEqual(
      { authenticated, userId, role, status },
      { authenticated: false, userId: null, role: null, status: null },
      label,
    );
    // แก้ค่าเพื่อไต่สิทธิ์ไม่ได้ เพราะ context ถูก freeze
    assert.throws(() => {
      "use strict";
      resolved.context.role = "admin";
    }, TypeError, label);
  }
});

test("C2 ANONYMOUS_AUTH_FAILED ให้สิทธิ์เท่ากับ ANONYMOUS เป๊ะ", () => {
  // ธง authFailed มีไว้เพื่อบอกเล่าใน log เท่านั้น ห้ามมีผลต่อการตัดสินสิทธิ์
  for (const level of LEVELS) {
    assert.equal(
      authorize(ANONYMOUS_AUTH_FAILED, level).ok,
      authorize(ANONYMOUS, level).ok,
      `ระดับ ${level} ต้องให้ผลเหมือนกัน`,
    );
  }
  assert.equal(isPrivileged(ANONYMOUS_AUTH_FAILED), false);
});

test("C2 ตัวตรวจ token ล้ม (Supabase ล่ม) — เส้นทางสาธารณะยังใช้ได้ เส้นทางที่ต้องมีสิทธิ์ยังได้ 401", async () => {
  const broken = {
    async verifyToken() {
      throw new Error("เชื่อมต่อไม่ได้");
    },
    async readProfile() {
      return null;
    },
  };
  const resolved = await resolveAuthContext(
    requestWith(bearer("token-admin-approved")),
    broken,
  );
  assert.equal(resolved.ok, true, "ต้องไม่ปฏิเสธที่ชั้นนี้");
  assert.equal(resolved.context.authenticated, false);
  assert.equal(resolved.context.authFailed, true);

  assert.equal(authorize(resolved.context, PUBLIC).ok, true, "สาธารณะยังใช้ได้");
  assert.equal(authorize(resolved.context, PUBLIC_FILTERED).ok, true);
  for (const level of [AUTHENTICATED, EDITOR, ADMIN]) {
    assert.equal(authorize(resolved.context, level).status, 401, `ระดับ ${level}`);
  }
});

test("C2 PUBLIC ไม่ต้องหาตัวตนเลย แต่ระดับอื่นต้องหา", () => {
  // PUBLIC ข้ามการตรวจ token ไปเลย -> เนื้อหาสาธารณะไม่ช้าหรือล่มตาม Supabase
  assert.equal(needsAuthContext(PUBLIC), false);
  for (const level of [PUBLIC_FILTERED, AUTHENTICATED, EDITOR, ADMIN]) {
    assert.equal(needsAuthContext(level), true, `ระดับ ${level}`);
  }
});

test("3. ผู้ใช้ทั่วไปที่ล็อกอินแล้ว เรียกเส้นทาง EDITOR ได้ 403", async () => {
  const got = await verdictFor(bearer("token-user-approved"), EDITOR);
  assert.equal(got.status, 403);
  assert.deepEqual(got.body, { error: "Forbidden" });
});

test("3b. ผู้ใช้ทั่วไปเรียกเส้นทาง ADMIN ได้ 403", async () => {
  assert.equal((await verdictFor(bearer("token-user-approved"), ADMIN)).status, 403);
});

test("3c. ผู้ใช้ทั่วไปยังผ่านระดับ AUTHENTICATED ได้", async () => {
  assert.equal((await verdictFor(bearer("token-user-approved"), AUTHENTICATED)).status, 200);
});

test("4. editor ที่ approved เรียกเส้นทาง EDITOR ได้", async () => {
  assert.equal((await verdictFor(bearer("token-editor-approved"), EDITOR)).status, 200);
});

test("5. editor เรียกเส้นทาง ADMIN ได้ 403", async () => {
  const got = await verdictFor(bearer("token-editor-approved"), ADMIN);
  assert.equal(got.status, 403);
  assert.deepEqual(got.body, { error: "Forbidden" });
});

test("6. admin ที่ approved เรียกเส้นทาง EDITOR ได้ (admin ต้องผ่านระดับของ editor ด้วย)", async () => {
  assert.equal((await verdictFor(bearer("token-admin-approved"), EDITOR)).status, 200);
});

test("7. admin ที่ approved เรียกเส้นทาง ADMIN ได้", async () => {
  assert.equal((await verdictFor(bearer("token-admin-approved"), ADMIN)).status, 200);
});

test("8. role มีสิทธิ์แต่ status ไม่ใช่ approved ได้ 403 ทุกระดับที่ต้องมีสิทธิ์", async () => {
  for (const token of ["token-admin-pending", "token-editor-pending"]) {
    for (const level of [EDITOR, ADMIN]) {
      const got = await verdictFor(bearer(token), level);
      assert.equal(got.status, 403, `${token} ที่ระดับ ${level}`);
    }
  }
});

test("8b. status ที่ไม่ใช่ approved ยังผ่านระดับ AUTHENTICATED ได้ (ล็อกอินได้ แต่ทำอะไรไม่ได้)", async () => {
  assert.equal((await verdictFor(bearer("token-admin-pending"), AUTHENTICATED)).status, 200);
});

test("8c. status ค่าอื่นที่ยังไม่เคยพบในระบบก็ไม่ผ่าน (ปฏิเสธเป็นค่าตั้งต้น)", () => {
  for (const status of ["rejected", "inactive", "APPROVED", " approved", "", null, undefined]) {
    const ctx = { authenticated: true, userId: "u", role: "admin", status };
    assert.equal(authorize(ctx, ADMIN).ok, false, `status ${JSON.stringify(status)}`);
  }
  // ยืนยันว่าค่าที่ถูกต้องยังผ่าน ไม่ใช่ปฏิเสธทุกอย่าง
  assert.equal(
    authorize({ authenticated: true, userId: "u", role: "admin", status: APPROVED_STATUS }, ADMIN).ok,
    true,
  );
});

test("9. ค่าใน request body เปลี่ยนสิทธิ์ไม่ได้", async () => {
  // ด่านอ่านจาก header เท่านั้น ไม่เคยอ่าน body — ข้อนี้พิสูจน์ว่า context ที่ได้
  // ไม่ขึ้นกับสิ่งที่ผู้เรียกส่งมาใน body เลย
  const resolved = await resolveAuthContext(requestWith(bearer("token-user-approved")), deps);
  assert.equal(resolved.ok, true);
  assert.equal(resolved.context.role, "user");

  // จำลองว่าผู้เรียกส่ง role=admin มาใน body แล้วเอาไปรวมกับ context
  const forged = { ...resolved.context, role: "admin" };
  assert.equal(authorize(resolved.context, ADMIN).ok, false, "ของจริงต้องไม่ผ่าน");
  assert.equal(authorize(forged, ADMIN).ok, true, "ถ้าเชื่อ body จะผ่าน — จึงห้ามเชื่อ");

  // และ context ที่ด่านคืนมาเป็น object ที่แก้ไม่ได้ จึงไม่มีใครเขียนทับกลางทางได้
  assert.throws(() => {
    "use strict";
    resolved.context.role = "admin";
  }, TypeError);
});

test("9b. คอลัมน์ผู้เขียนที่ส่งมาใน body ถูกตัดออกทั้งหมด", () => {
  const { value, removed } = stripAuthorFields({
    title: "ข่าวทดสอบ",
    created_by: "u-ปลอม",
    updated_by: "u-ปลอม",
    status: "published",
  });
  assert.deepEqual(removed.sort(), ["created_by", "updated_by"]);
  assert.deepEqual(value, { title: "ข่าวทดสอบ", status: "published" });
  assert.equal("created_by" in value, false);
  assert.equal("updated_by" in value, false);
});

test("10. header Authorization ที่ผิดรูปแบบ ได้ 401", async () => {
  const bad = [
    "Basic dXNlcjpwYXNz",
    "Bearer",
    "Bearer ",
    "Bearer  token-admin-approved", // ช่องว่างสองช่อง
    "Bearer token-admin-approved extra",
    "token-admin-approved", // ไม่มีคำว่า Bearer
    "Bearertoken-admin-approved",
  ];
  for (const header of bad) {
    const got = await verdictFor(header, EDITOR);
    assert.equal(got.status, 401, `header ${JSON.stringify(header)}`);
    assert.deepEqual(got.body, { error: "Unauthorized" });
  }
});

// =====================================================================
// การแกะ header
// =====================================================================

test("parseBearer แยกสามกรณีได้ถูก", () => {
  assert.deepEqual(parseBearer(null), { kind: "none" });
  assert.deepEqual(parseBearer(undefined), { kind: "none" });
  assert.deepEqual(parseBearer(""), { kind: "none" });
  assert.deepEqual(parseBearer("   "), { kind: "none" });
  assert.deepEqual(parseBearer("Bearer abc"), { kind: "token", token: "abc" });
  assert.deepEqual(parseBearer("bearer abc"), { kind: "token", token: "abc" });
  assert.deepEqual(parseBearer("BEARER abc"), { kind: "token", token: "abc" });
  assert.deepEqual(parseBearer("  Bearer abc  "), { kind: "token", token: "abc" });
  assert.equal(parseBearer("Bearer").kind, "malformed");
  assert.equal(parseBearer("Basic abc").kind, "malformed");
});

test("ไม่มีแถวใน user_profiles = ไม่มีสิทธิ์ (ไม่เดาค่าตั้งต้นให้)", async () => {
  // ตรงกับที่ api/_lib/adminAuth.js ทำอยู่ — ที่นั่นใช้ profile?.role ซึ่งเป็น
  // undefined แล้วตกเกณฑ์ทุกข้อ ด่านนี้ต้องไม่หลวมกว่านั้น
  assert.equal((await verdictFor(bearer("token-no-profile"), EDITOR)).status, 403);
  assert.equal((await verdictFor(bearer("token-no-profile"), ADMIN)).status, 403);
  // แต่ยังถือว่าล็อกอินแล้ว
  assert.equal((await verdictFor(bearer("token-no-profile"), AUTHENTICATED)).status, 200);
});

test("ตัวตรวจ token ล้ม ต้องไม่กลายเป็นผู้ใช้ที่มีสิทธิ์", async () => {
  // เดิมข้อนี้คาด 401 จาก resolveAuthContext โดยตรง ตอนนี้การปฏิเสธย้ายไปอยู่ที่
  // authorize() เพื่อให้เส้นทางสาธารณะไม่ล่มตาม (ดูชุด C2 ข้างบน)
  // สิ่งที่ต้องไม่เปลี่ยนคือ "ล้มแล้วต้องไม่ได้สิทธิ์" ซึ่งข้อนี้ยังคุ้มอยู่
  const broken = {
    async verifyToken() {
      throw new Error("เชื่อมต่อไม่ได้");
    },
    async readProfile() {
      return null;
    },
  };
  const resolved = await resolveAuthContext(requestWith(bearer("token-admin-approved")), broken);
  assert.equal(resolved.context.authenticated, false);
  assert.equal(resolved.context.role, null);
  assert.equal(authorize(resolved.context, EDITOR).status, 401);
  assert.equal(authorize(resolved.context, ADMIN).status, 401);
});

test("อ่าน user_profiles ไม่ได้ ต้องไม่เดาว่ามีสิทธิ์", async () => {
  const broken = {
    async verifyToken() {
      return { userId: "u-admin" };
    },
    async readProfile() {
      throw new Error("อ่านตารางไม่ได้");
    },
  };
  const resolved = await resolveAuthContext(requestWith(bearer("x")), broken);
  assert.equal(resolved.ok, true);
  assert.equal(resolved.context.authenticated, true);
  assert.equal(resolved.context.role, null);
  assert.equal(authorize(resolved.context, EDITOR).ok, false);
});

test("ไม่ส่ง deps มา ต้องได้ 500 ไม่ใช่ปล่อยผ่าน", async () => {
  for (const bad of [undefined, {}, { verifyToken: () => null }]) {
    const resolved = await resolveAuthContext(requestWith(bearer("x")), bad);
    assert.equal(resolved.ok, false);
    assert.equal(resolved.status, 500);
  }
});

// =====================================================================
// ระดับสิทธิ์
// =====================================================================

test("ระดับที่ไม่รู้จักต้องถูกปฏิเสธ ไม่ใช่ปล่อยผ่าน", () => {
  const admin = { authenticated: true, userId: "u", role: "admin", status: "approved" };
  for (const level of ["SUPERUSER", "public", "", null, undefined]) {
    const got = authorize(admin, level);
    assert.equal(got.ok, false, `ระดับ ${JSON.stringify(level)}`);
    assert.equal(got.status, 403);
  }
});

test("ANONYMOUS ผ่านได้แค่ระดับสาธารณะ", () => {
  assert.equal(authorize(ANONYMOUS, PUBLIC).ok, true);
  assert.equal(authorize(ANONYMOUS, PUBLIC_FILTERED).ok, true);
  for (const level of [AUTHENTICATED, EDITOR, ADMIN]) {
    const got = authorize(ANONYMOUS, level);
    assert.equal(got.ok, false, `ระดับ ${level}`);
    assert.equal(got.status, 401);
  }
});

test("context ที่เป็น null ถือเป็น anonymous ไม่ใช่ error", () => {
  assert.equal(authorize(null, PUBLIC).ok, true);
  assert.equal(authorize(null, EDITOR).status, 401);
  assert.equal(authorize(undefined, ADMIN).status, 401);
});

test("isPrivileged ตรงกับระดับ EDITOR", () => {
  const mk = (role, status) => ({ authenticated: true, userId: "u", role, status });
  assert.equal(isPrivileged(mk("admin", "approved")), true);
  assert.equal(isPrivileged(mk("editor", "approved")), true);
  assert.equal(isPrivileged(mk("user", "approved")), false);
  assert.equal(isPrivileged(mk("admin", "pending")), false);
  assert.equal(isPrivileged(ANONYMOUS), false);
  assert.equal(isPrivileged(null), false);
});

test("validateRouteTable จับเส้นทางที่ไม่ประกาศระดับสิทธิ์", () => {
  // ตารางที่ถูกต้อง
  assert.deepEqual(
    validateRouteTable([
      ["/a", "./a.js", PUBLIC],
      ["/b", "./b.js", EDITOR],
      ["/c", "./c.js", ADMIN],
    ]),
    [],
  );

  // ขาดระดับไปเลย
  assert.deepEqual(validateRouteTable([["/a", "./a.js"]]), ["/a"]);
  // ระดับที่ไม่รู้จัก
  assert.deepEqual(validateRouteTable([["/a", "./a.js", "SUPERUSER"]]), ["/a"]);
  assert.deepEqual(validateRouteTable([["/a", "./a.js", "public"]]), ["/a"]);
  assert.deepEqual(validateRouteTable([["/a", "./a.js", null]]), ["/a"]);
  // เส้นทางว่างหรือไม่ใช่สตริง
  assert.deepEqual(validateRouteTable([["", "./a.js", PUBLIC]]), ["<ไม่มีเส้นทาง>"]);
  // รายการที่ไม่ใช่ array
  assert.deepEqual(validateRouteTable([{ route: "/a" }]), ["<ไม่มีเส้นทาง>"]);
  // ไม่ใช่ตาราง
  assert.equal(validateRouteTable(null).length, 1);
  assert.equal(validateRouteTable("ไม่ใช่ตาราง").length, 1);
  // รายงานทุกเส้นทางที่ผิด ไม่ใช่หยุดที่ตัวแรก
  assert.deepEqual(
    validateRouteTable([
      ["/ok", "./ok.js", PUBLIC],
      ["/bad1", "./bad1.js"],
      ["/bad2", "./bad2.js", "NOPE"],
    ]),
    ["/bad1", "/bad2"],
  );
});

test("LEVELS ประกาศครบและไม่ซ้ำ", () => {
  assert.deepEqual([...new Set(LEVELS)], [...LEVELS]);
  for (const level of [PUBLIC, PUBLIC_FILTERED, AUTHENTICATED, EDITOR, ADMIN]) {
    assert.ok(LEVELS.includes(level), `${level} ต้องอยู่ใน LEVELS`);
  }
});

// =====================================================================
// ไม่รั่วข้อมูลลับ
// =====================================================================

test("describeForLog ไม่มี token อีเมล หรือ uuid ของผู้ใช้", () => {
  const ctx = {
    authenticated: true,
    userId: "3fe27ab3-0000-0000-0000-ba0118c3eceb",
    role: "admin",
    status: "approved",
  };
  const line = describeForLog(ctx);
  assert.equal(line.includes(ctx.userId), false, "ต้องไม่มี uuid");
  assert.equal(/@/.test(line), false, "ต้องไม่มีอีเมล");
  assert.equal(/Bearer|token/i.test(line), false, "ต้องไม่มี token");
  assert.equal(line, "authenticated role=admin status=approved");
  assert.equal(describeForLog(ANONYMOUS), "anonymous");
  assert.equal(describeForLog(null), "anonymous");

  // แยก "ไม่ได้ส่งอะไรมา" ออกจาก "ส่งมาแต่ใช้ไม่ได้" ได้ โดยไม่เปิดเผย token
  const failed = describeForLog(ANONYMOUS_AUTH_FAILED);
  assert.equal(failed, "anonymous (auth failed)");
  assert.equal(/Bearer|token|@/i.test(failed), false);
});

test("ข้อความตอบกลับไม่มีรายละเอียดภายใน", async () => {
  const bodies = [
    (await verdictFor(null, EDITOR)).body,
    (await verdictFor(bearer("token-ไม่มีจริง"), EDITOR)).body,
    (await verdictFor(bearer("token-user-approved"), ADMIN)).body,
  ];
  for (const body of bodies) {
    assert.deepEqual(Object.keys(body), ["error"], "ต้องมีคีย์ error เดียว");
    const text = JSON.stringify(body);
    assert.equal(/token|Bearer|supabase|jwt|uuid|sql/i.test(text), false, text);
  }
});

// =====================================================================
// สัญญาเรื่องผู้เขียนข้อมูล — ต้องปฏิเสธ ไม่ใช่เดา
// =====================================================================

test("resolveAuthorId ปฏิเสธเสมอ และบอกเหตุผลด้วยรหัสที่ตามรอยได้", () => {
  const got = resolveAuthorId({
    authenticated: true,
    userId: "u-admin",
    role: "admin",
    status: "approved",
  });
  assert.equal(got.ok, false);
  assert.equal(got.reason, ACTIVE_USER_MAPPING_REQUIRED);
  assert.equal("id" in got, false, "ต้องไม่คืน id ออกมาเลย");
});

test("authorFieldsFor ยังเขียนผู้เขียนไม่ได้ ทั้ง create และ update", () => {
  const admin = { authenticated: true, userId: "u-admin", role: "admin", status: "approved" };
  for (const mode of ["create", "update"]) {
    const got = authorFieldsFor(mode, admin);
    assert.equal(got.ok, false, `mode ${mode}`);
    assert.equal(got.reason, ACTIVE_USER_MAPPING_REQUIRED);
    assert.equal("fields" in got, false, "ต้องไม่คืนคอลัมน์ที่จะเขียนออกมา");
  }
});

test("authorFieldsFor ไม่ยอมทำงานถ้าไม่มีตัวตนที่ยืนยันแล้ว", () => {
  assert.equal(authorFieldsFor("create", ANONYMOUS).reason, "NOT_AUTHENTICATED");
  assert.equal(authorFieldsFor("create", null).reason, "NOT_AUTHENTICATED");
});

test("authorFieldsFor ปฏิเสธ mode ที่ไม่รู้จัก", () => {
  const admin = { authenticated: true, userId: "u", role: "admin", status: "approved" };
  assert.equal(authorFieldsFor("upsert", admin).reason, "UNKNOWN_WRITE_MODE");
  assert.equal(authorFieldsFor("delete", admin).ok, false);
});

test("stripAuthorFields ไม่พังกับค่าที่ไม่ใช่ object", () => {
  for (const value of [null, undefined, 1, "x", [1, 2]]) {
    const got = stripAuthorFields(value);
    assert.deepEqual(got.removed, []);
    assert.deepEqual(got.value, value);
  }
});

test("stripAuthorFields ไม่แก้ object เดิมของผู้เรียก", () => {
  const original = { title: "a", created_by: "u" };
  stripAuthorFields(original);
  assert.equal(original.created_by, "u", "ต้องคืน object ใหม่ ไม่แก้ของเดิม");
});
