/**
 * ด่านตรวจตัวตนและสิทธิ์กลางของ webapi
 *
 * ทำไมไฟล์นี้อยู่ที่นี่ ไม่ใช่ใน api/_lib/
 * ------------------------------------
 * `api/` ทั้งโฟลเดอร์เป็นของรีโปหน้าเว็บ ถูกคัดลอกเข้ามาตอน build (ดู Dockerfile)
 * รีโปนี้แก้ไฟล์เหล่านั้นไม่ได้ ด่านกลางจึงต้องอยู่ข้าง server.mjs แล้วบังคับ
 * "ก่อน" ส่งคำขอเข้าฟังก์ชันของหน้าเว็บ — ของเพื่อนยังเป็นของเพื่อนทุกบรรทัด
 *
 * ไฟล์นี้ไม่แทนที่ `api/_lib/adminAuth.js` ที่ฟังก์ชันหลังบ้านเรียกอยู่ มันเป็นด่าน
 * เพิ่มอีกชั้นที่ด้านนอก ผลลัพธ์สำหรับผู้เรียกที่มีสิทธิ์ถูกต้องจึงไม่เปลี่ยน
 *
 * สิ่งที่ไฟล์นี้ตั้งใจ "ไม่" ทำ
 * ---------------------------
 *   - ไม่ถอด JWT ในเครื่องเอง  ถาม Supabase ทุกครั้งผ่าน auth.getUser(token)
 *     เพื่อให้ token ที่ถูกเพิกถอนใช้ไม่ได้ทันที ไม่ต้องรอหมดอายุ
 *   - ไม่เก็บแคชผลตรวจสิทธิ์  การลดสิทธิ์ผู้ใช้ต้องมีผลกับคำขอถัดไปเลย
 *   - ไม่ใช้ service-role key  ใช้ anon key + token ของผู้เรียก เพื่อให้ RLS
 *     ของต้นทางยังบังคับด้วยตัวตนจริงของผู้เรียกอยู่
 *   - ไม่บันทึก token อีเมล หรือ uuid ของผู้ใช้ลง log (ดู describeForLog)
 *
 * คำศัพท์ role/status ที่ใช้ที่นี่มาจากโค้ดจริงของระบบ ไม่ได้ตั้งเอง
 *   role    admin · editor · user      (user เป็นค่าที่ trigger handle_new_user ให้)
 *   status  approved · pending          (หน้า /admin/users สลับสองค่านี้)
 */

/** ระดับสิทธิ์ที่ประกาศกับ route ได้ */
export const PUBLIC = "PUBLIC";
export const PUBLIC_FILTERED = "PUBLIC_FILTERED";
export const AUTHENTICATED = "AUTHENTICATED";
export const EDITOR = "EDITOR";
export const ADMIN = "ADMIN";

export const LEVELS = Object.freeze([PUBLIC, PUBLIC_FILTERED, AUTHENTICATED, EDITOR, ADMIN]);

/** ระดับที่ผู้เรียกไม่ต้องมี token ก็เข้าได้ */
const OPEN_LEVELS = new Set([PUBLIC, PUBLIC_FILTERED]);

/**
 * role ที่ผ่านแต่ละระดับ
 *
 * admin อยู่ในชุดของ EDITOR ด้วยโดยเจตนา — ผู้ดูแลระดับสูงต้องทำสิ่งที่ผู้ช่วยทำได้
 * แต่ editor ไม่อยู่ในชุดของ ADMIN เพราะ RLS ต้นทางให้ DELETE เฉพาะ admin
 * (ดู docs/AUTHORIZATION_USER_MAPPING_DESIGN.md ข้อ 2.2)
 */
const ROLES_FOR_LEVEL = Object.freeze({
  [EDITOR]: Object.freeze(["admin", "editor"]),
  [ADMIN]: Object.freeze(["admin"]),
});

/** สถานะเดียวที่ทำงานที่ต้องมีสิทธิ์ได้ ค่าอื่นทั้งหมดถือว่าไม่ผ่าน */
export const APPROVED_STATUS = "approved";

/** ผู้เรียกที่ไม่ได้ส่ง token มา */
export const ANONYMOUS = Object.freeze({
  authenticated: false,
  userId: null,
  role: null,
  status: null,
  authFailed: false,
});

/**
 * ผู้เรียกที่ "ส่งข้อมูลยืนยันตัวตนมาแต่ใช้ไม่ได้" — header พัง, token ใช้ไม่ได้,
 * หรือตัวตรวจล้ม
 *
 * เป็น anonymous ทุกฟิลด์เหมือนกันเป๊ะ ต่างแค่ธง authFailed ที่บอกว่าเคยมีความพยายาม
 * ยืนยันตัวตนแล้วไม่ผ่าน ไม่ได้ให้สิทธิ์อะไรเพิ่มเลยแม้แต่น้อย
 *
 * ทำไมต้องแยกจาก ANONYMOUS
 * -----------------------
 * เส้นทางสาธารณะต้องทำงานต่อได้ (ให้บริการในฐานะ anonymous) แต่เส้นทางที่ต้องมีสิทธิ์
 * ต้องตอบ 401 — ธงนี้ทำให้ authorize() แยกสองกรณีได้โดยไม่ต้องรู้ว่า route คือระดับไหน
 * ตอนแกะ header
 *
 * ผลลัพธ์ที่ได้เหมือนกันทั้งสองแบบสำหรับระดับที่ต้องมีสิทธิ์ (401) จึงไม่มีช่องให้
 * ใครใช้ธงนี้ไต่สิทธิ์ขึ้นไปได้
 */
export const ANONYMOUS_AUTH_FAILED = Object.freeze({
  authenticated: false,
  userId: null,
  role: null,
  status: null,
  authFailed: true,
});

// ข้อความตอบกลับสั้นที่สุดที่ยังบอกผู้เรียกได้ว่าควรทำอะไรต่อ
//
// ตั้งใจไม่แยกระหว่าง "ไม่ได้ส่ง token" "token เพี้ยน" และ "token หมดอายุ"
// เพราะการแยกให้ชัดคือการบอกผู้โจมตีว่าเดาไปถึงขั้นไหนแล้ว
const UNAUTHORIZED = Object.freeze({ status: 401, body: { error: "Unauthorized" } });
const FORBIDDEN = Object.freeze({ status: 403, body: { error: "Forbidden" } });
const MISCONFIGURED = Object.freeze({
  status: 500,
  body: { error: "Authorization is not configured" },
});

/**
 * แกะ token จาก header Authorization
 *
 * รับเฉพาะรูปแบบ `Bearer <token>` ที่มีช่องว่างคั่นเดียวและ token ไม่ว่าง
 * ชนิดอื่น (Basic, Digest, คำเดียวโดด ๆ, Bearer เปล่า) ถือว่า malformed
 *
 * ทำไม malformed ไม่ถูกปัดเป็น anonymous
 * ------------------------------------
 * ผู้เรียกที่ส่งข้อมูลยืนยันตัวตนที่พังมา ควรได้รู้ว่ามันพัง การกลืนแล้วทำเหมือน
 * ไม่มีใครล็อกอินทำให้เกิดอาการ "หน้าจอยังเหมือนล็อกอินอยู่แต่ทุกอย่างว่างเปล่า"
 * ซึ่งหาสาเหตุยากกว่าการได้ 401 ตรง ๆ มาก
 */
export function parseBearer(headerValue) {
  if (headerValue === null || headerValue === undefined) return { kind: "none" };
  const raw = String(headerValue);
  if (raw.trim() === "") return { kind: "none" };

  const match = /^Bearer[ ]([^\s]+)$/i.exec(raw.trim());
  if (!match) return { kind: "malformed" };
  return { kind: "token", token: match[1] };
}

/**
 * หาตัวตนและสิทธิ์ของผู้เรียก
 *
 * คืน { ok: true, context } หรือ { ok: false, status, body }
 *
 * deps รับเข้ามาเพื่อให้ทดสอบได้โดยไม่ต้องยิง Supabase จริง
 *   verifyToken(token)  -> { userId } | null      null = token ใช้ไม่ได้
 *   readProfile(userId) -> { role, status } | null null = ไม่มีแถวใน user_profiles
 *
 * ไม่ใส่ค่าตั้งต้นให้ role หรือ status เมื่อหาโปรไฟล์ไม่เจอ — ปล่อยเป็น null
 * ให้ทุกระดับที่ต้องมีสิทธิ์ปฏิเสธไป ตรงกับที่ api/_lib/adminAuth.js ทำอยู่
 * (ที่นั่นใช้ profile?.role ซึ่งเป็น undefined แล้วตกเกณฑ์ทุกข้อ)
 */
export async function resolveAuthContext(request, deps) {
  const { verifyToken, readProfile } = deps ?? {};
  if (typeof verifyToken !== "function" || typeof readProfile !== "function") {
    return { ok: false, ...MISCONFIGURED };
  }

  const header =
    typeof request?.headers?.get === "function" ? request.headers.get("authorization") : null;
  const parsed = parseBearer(header);

  if (parsed.kind === "none") return { ok: true, context: ANONYMOUS };

  // ข้อมูลยืนยันตัวตนที่ใช้ไม่ได้ -> ลดระดับเป็น anonymous ไม่ใช่ปฏิเสธที่นี่
  //
  // การตัดสินว่าจะยอมรับ anonymous ไหมเป็นหน้าที่ของ authorize() เพียงจุดเดียว
  // ซึ่งเป็นจุดเดียวที่รู้ว่า route ต้องการระดับใด ถ้าปฏิเสธตั้งแต่ที่นี่ เส้นทาง
  // สาธารณะจะใช้งานไม่ได้เพียงเพราะมี header พังติดมา ซึ่งไม่เกี่ยวกับเนื้อหาที่ขอ
  //
  // ความปลอดภัยไม่ลดลง เพราะ context ที่คืนไปเป็น anonymous ทุกฟิลด์ —
  // ไม่มี role ไม่มี status ไม่มี userId จึงไต่สิทธิ์ขึ้นไปไม่ได้
  if (parsed.kind === "malformed") return { ok: true, context: ANONYMOUS_AUTH_FAILED };

  let identity;
  try {
    identity = await verifyToken(parsed.token);
  } catch {
    // ตัวตรวจล้ม (Supabase ล่ม/เน็ตขาด) — ลดระดับเป็น anonymous เช่นเดียวกัน
    // เส้นทางที่ต้องมีสิทธิ์จะได้ 401 จาก authorize() ตามเดิม ไม่ได้ปล่อยผ่าน
    return { ok: true, context: ANONYMOUS_AUTH_FAILED };
  }
  if (!identity?.userId) return { ok: true, context: ANONYMOUS_AUTH_FAILED };

  let profile = null;
  try {
    // ส่ง identity ของคำขอนี้ต่อไปด้วย — ตัวตรวจจะได้ใช้ client ที่ผูกกับ token
    // ของคำขอนี้ ไม่ใช่ของคำขออื่นที่มาทับ (ดูเหตุผลที่ createRuntimeDeps)
    profile = await readProfile(identity.userId, identity);
  } catch {
    // อ่านโปรไฟล์ไม่ได้ = ไม่รู้สิทธิ์ = ต้องไม่เดาว่ามีสิทธิ์
    profile = null;
  }

  return {
    ok: true,
    context: Object.freeze({
      authenticated: true,
      userId: identity.userId,
      role: profile?.role ?? null,
      status: profile?.status ?? null,
    }),
  };
}

/**
 * ตัดสินว่า context นี้ผ่านระดับที่ route ต้องการไหม
 *
 * คืน { ok: true } หรือ { ok: false, status, body }
 */
export function authorize(context, level) {
  if (!LEVELS.includes(level)) {
    // ระดับที่ไม่รู้จักต้องปฏิเสธ ไม่ใช่ปล่อยผ่าน — ดูเหตุผลใน server.mjs
    return { ok: false, ...FORBIDDEN };
  }
  // เส้นทางสาธารณะผ่านได้เสมอ รวมถึงกรณีที่ผู้เรียกส่งข้อมูลยืนยันตัวตนพังมา
  // ผู้เรียกนั้นได้บริการในฐานะ anonymous ไม่ได้สิทธิ์อะไรเพิ่ม
  if (OPEN_LEVELS.has(level)) return { ok: true };

  const ctx = context ?? ANONYMOUS;
  // ทั้ง "ไม่ได้ส่งอะไรมา" และ "ส่งมาแต่ใช้ไม่ได้" ได้ 401 เหมือนกันที่ระดับนี้
  if (!ctx.authenticated) return { ok: false, ...UNAUTHORIZED };
  if (level === AUTHENTICATED) return { ok: true };

  // ต้องเป็น approved เท่านั้น ค่าอื่น (pending หรือค่าที่ยังไม่เคยพบ) ไม่ผ่าน
  if (ctx.status !== APPROVED_STATUS) return { ok: false, ...FORBIDDEN };

  const allowed = ROLES_FOR_LEVEL[level];
  if (!allowed || !allowed.includes(ctx.role)) return { ok: false, ...FORBIDDEN };
  return { ok: true };
}

/**
 * ระดับนี้ต้องหาตัวตนของผู้เรียกไหม
 *
 * PUBLIC ไม่ต้อง — context ไม่เคยถูกใช้ตัดสินอะไรที่ระดับนั้น การข้ามไปเลยทำให้
 * เส้นทางสาธารณะไม่ต้องรอผลตรวจ token จาก Supabase แม้ผู้เรียกจะส่ง header มา
 * ซึ่งสำคัญตอน Supabase ล่ม — เนื้อหาสาธารณะต้องไม่ช้าหรือล่มตามไปด้วย
 *
 * PUBLIC_FILTERED ต้องหา เพราะต้องรู้ว่าจะกรองข้อมูลให้คนทั่วไปไหม
 */
export function needsAuthContext(level) {
  return level !== PUBLIC;
}

/**
 * ตรวจว่าทุกเส้นทางในตารางประกาศระดับสิทธิ์ที่รู้จัก
 *
 * คืนรายชื่อเส้นทางที่ไม่ผ่าน (ว่าง = ผ่านหมด)
 *
 * แยกออกมาจาก server.mjs เพื่อให้ทดสอบได้โดยไม่ต้องเริ่มเซิร์ฟเวอร์จริง —
 * กฎข้อนี้คือสิ่งที่กันไม่ให้เส้นทางใหม่หลุดออกไปโดยไม่มีด่าน จึงต้องมีข้อตรวจคุ้ม
 */
export function validateRouteTable(routes) {
  if (!Array.isArray(routes)) return ["<ตาราง route ไม่ใช่ array>"];
  const bad = [];
  for (const entry of routes) {
    if (!Array.isArray(entry) || entry.length < 3) {
      bad.push(String(entry?.[0] ?? "<ไม่มีเส้นทาง>"));
      continue;
    }
    const [route, , level] = entry;
    if (typeof route !== "string" || route === "" || !LEVELS.includes(level)) {
      bad.push(typeof route === "string" && route !== "" ? route : "<ไม่มีเส้นทาง>");
    }
  }
  return bad;
}

/** สะดวกสำหรับ route ที่อยากรู้ว่าควรกรองข้อมูลให้คนทั่วไปไหม */
export function isPrivileged(context) {
  return authorize(context, EDITOR).ok;
}

/**
 * ข้อมูลที่ปลอดภัยพอจะเขียนลง log
 *
 * ไม่มี token ไม่มีอีเมล ไม่มี uuid — uuid ของผู้ใช้เป็นตัวระบุตัวบุคคลที่ตามรอยได้
 * ข้าม log ไปเลยดีกว่าใส่แล้วต้องมาลบทีหลัง
 */
export function describeForLog(context) {
  const ctx = context ?? ANONYMOUS;
  // แยก "ไม่ได้ส่งอะไรมา" ออกจาก "ส่งมาแต่ใช้ไม่ได้" เพื่อให้ตามรอยปัญหา token
  // ฝั่งผู้เรียกได้ โดยไม่เปิดเผยตัว token หรือเหตุผลที่ไม่ผ่าน
  if (!ctx.authenticated) return ctx.authFailed ? "anonymous (auth failed)" : "anonymous";
  return `authenticated role=${ctx.role ?? "none"} status=${ctx.status ?? "none"}`;
}

// ---------------------------------------------------------------------
// ตัวตรวจจริงที่คุยกับ Supabase
//
// นำเข้า @supabase/supabase-js แบบ dynamic ภายในฟังก์ชัน ไม่ใช่ที่หัวไฟล์
// เพื่อให้ชุดทดสอบนำเข้าไฟล์นี้ได้โดยไม่ต้องติดตั้งไลบรารี — ชุดทดสอบส่ง
// verifyToken/readProfile ปลอมเข้ามาเอง จึงไม่เคยแตะ Supabase จริงเลย
// ---------------------------------------------------------------------
export function supabaseEnv(env = process.env) {
  const url = env.VITE_SUPABASE_URL;
  const anonKey = env.VITE_SUPABASE_ANON_KEY;
  if (!url || !anonKey) return null;
  return { url, anonKey };
}

export function createSupabaseVerifier(config) {
  const { url, anonKey } = config;

  // client หนึ่งตัวต่อหนึ่ง token — ห้ามใช้ร่วมกันข้ามคำขอ เพราะ header
  // Authorization ติดไปกับ client ไม่ใช่ติดไปกับ query
  const clientFor = async (token) => {
    const { createClient } = await import("@supabase/supabase-js");
    return createClient(url, anonKey, {
      auth: { persistSession: false, autoRefreshToken: false },
      global: { headers: { Authorization: `Bearer ${token}` } },
    });
  };

  return {
    async verifyToken(token) {
      const supabase = await clientFor(token);
      const {
        data: { user },
        error,
      } = await supabase.auth.getUser(token);
      if (error || !user) return null;
      // เก็บ client ไว้ให้ readProfile ใช้ซ้ำ เพื่อให้การอ่านโปรไฟล์ถูกบังคับด้วย
      // RLS ในนามผู้เรียกเอง ไม่ใช่ในนามของบริการ
      return { userId: user.id, supabase };
    },

    async readProfile(userId, identity) {
      const supabase = identity?.supabase ?? (await clientFor(""));
      const { data, error } = await supabase
        .from("user_profiles")
        .select("role, status")
        .eq("user_id", userId)
        .single();
      if (error || !data) return null;
      return { role: data.role ?? null, status: data.status ?? null };
    },
  };
}

/**
 * ประกอบ deps สำหรับใช้งานจริง — ส่ง identity ที่ได้จาก verifyToken ต่อให้
 * readProfile เพื่อให้ใช้ client ตัวเดียวกัน (หนึ่งคำขอ = หนึ่ง client)
 *
 * ⚠ ทำไมห้ามเก็บ identity ไว้ในตัวแปรร่วมของ closure
 * --------------------------------------------------
 * รุ่นก่อนหน้าเก็บไว้ใน `let lastIdentity` ซึ่งใช้ร่วมกันทุกคำขอ · คำขอสองรายการ
 * ที่ทับเวลากันจะทับค่ากันเอง
 *
 *     A: verifyToken  -> lastIdentity = A
 *     B: verifyToken  -> lastIdentity = B      <-- ทับของ A
 *     A: readProfile  -> ได้ client ของ B
 *
 * ผลคือ A อ่านโปรไฟล์ของตัวเองด้วย client ของ B แล้ว RLS คืนศูนย์แถว →
 * ผู้ใช้ที่มีสิทธิ์ถูกปฏิเสธแบบสุ่มเมื่อมีคนใช้พร้อมกัน
 *
 * (ไม่ใช่ช่องทางไต่สิทธิ์ เพราะ userId ส่งเข้ามาตรง ๆ และ RLS บังคับในนามผู้เรียก
 * แต่เป็นบั๊กจริงที่โผล่เฉพาะตอนมีทราฟฟิกพร้อมกัน ซึ่งหายากที่สุด)
 *
 * วิธีแก้: ไม่เก็บสถานะใด ๆ ไว้ที่นี่เลย · identity เดินทางไปกับค่าที่คืนจาก
 * verifyToken แล้ว resolveAuthContext ส่งต่อให้ readProfile เอง
 * ทุกคำขอจึงถือ identity ของตัวเองคนละชุด
 */
export function createRuntimeDeps(config) {
  const verifier = createSupabaseVerifier(config);
  return {
    async verifyToken(token) {
      // คืน identity ทั้งก้อนรวม client ที่ผูกกับ token นี้ — ไม่เก็บไว้ที่ใด
      return verifier.verifyToken(token);
    },
    async readProfile(userId, identity) {
      return verifier.readProfile(userId, identity);
    },
  };
}

// ---------------------------------------------------------------------
// สัญญาเรื่องผู้เขียนข้อมูล (created_by / updated_by)
//
// เขียนได้แล้วตั้งแต่ M3 — ก่อนหน้านี้ปฏิเสธเสมอโดยตั้งใจ
// ---------------------------------------------------------------------

/** รหัสที่ใช้อ้างอิงกรณี "ยังไม่ได้ต่อตัวแปลงตัวตน" ในเอกสารและใน log */
export const ACTIVE_USER_MAPPING_REQUIRED = "B1_ACTIVE_USER_MAPPING_REQUIRED";

/**
 * แปลงตัวตนของผู้เรียก (Supabase) ไปเป็น public.users.id ของ PostgreSQL
 *
 * ประวัติของฟังก์ชันนี้
 * -------------------
 * รุ่นก่อนปฏิเสธทุกครั้งพร้อมเหตุผลว่า auth.users.id ของ Supabase กับ
 * public.users.id ของเราเป็น uuid คนละชุดที่ไม่มีเส้นเชื่อมกัน การเอาค่าหนึ่ง
 * ไปใส่อีกที่คือการชี้ไปผู้ใช้ที่ไม่มีอยู่ หรือแย่กว่านั้นคือชี้ไปผู้ใช้คนอื่น
 *
 * เส้นเชื่อมนั้นมีแล้ว — คอลัมน์ public.users.supabase_user_id จาก migration 006
 * และการจับคู่ของผู้ใช้จริงที่ยืนยันแล้ว (S1_MAPPING_APPLIED_VERIFIED)
 * ฟังก์ชันนี้จึงถามฐานข้อมูลแทนการเดา
 *
 * สิ่งที่ยังห้ามเหมือนเดิมทุกข้อ
 * ---------------------------
 *   - ห้าม fallback ด้วยอีเมล (และ advisor_web อ่านคอลัมน์ email ไม่ได้อยู่แล้ว)
 *   - ห้าม fallback เป็นผู้ดูแลระบบ
 *   - ห้ามใช้ Supabase uuid เป็น local id ตรง ๆ
 *   - ห้ามสร้างผู้ใช้ใหม่ (และ advisor_web ไม่มีสิทธิ์ INSERT อยู่แล้ว)
 *   - ห้ามเชื่อค่าจาก request body
 *
 * ปฏิเสธเมื่อไม่แน่ใจเสมอ — ทุกเส้นทางที่ไม่ใช่ "เจอหนึ่งคนและยังใช้งานอยู่"
 * คือการปฏิเสธ
 */
export async function resolveAuthorId(context, resolver) {
  if (!context?.authenticated || !context?.userId) {
    return { ok: false, reason: "NOT_AUTHENTICATED", detail: "ไม่มีตัวตนที่ยืนยันแล้ว" };
  }
  if (typeof resolver?.resolveLocalUser !== "function") {
    // ไม่ได้ต่อตัวแปลงตัวตนไว้ = แปลงไม่ได้ = เขียนไม่ได้
    // ไม่ใช่ "ลองเดาดูก่อน"
    return {
      ok: false,
      reason: ACTIVE_USER_MAPPING_REQUIRED,
      detail: "ยังไม่ได้ต่อตัวแปลงตัวตนกับฐานข้อมูล จึงยังเขียน created_by / updated_by ไม่ได้",
    };
  }

  const found = await resolver.resolveLocalUser(context.userId);
  if (!found?.ok) {
    return {
      ok: false,
      reason: found?.reason ?? "IDENTITY_LOOKUP_FAILED",
      detail: found?.detail ?? "แปลงตัวตนไม่สำเร็จ",
    };
  }
  return { ok: true, id: found.localUserId };
}

export function stripAuthorFields(payload) {
  if (payload === null || typeof payload !== "object" || Array.isArray(payload)) {
    return { value: payload, removed: [] };
  }
  const removed = [];
  const value = {};
  for (const [key, item] of Object.entries(payload)) {
    if (key === "created_by" || key === "updated_by") {
      removed.push(key);
      continue;
    }
    value[key] = item;
  }
  return { value, removed };
}

/**
 * เตรียมคอลัมน์ผู้เขียนสำหรับการเขียนข้อมูล
 *
 * mode "create" ต้องตั้งทั้งสองคอลัมน์ · mode "update" ตั้งแต่ updated_by
 * และ **ห้ามแตะ created_by เลย** แม้จะตั้งจาก token ก็ไม่ได้
 *
 * เหตุผลที่ UPDATE ห้ามแตะ created_by
 * ---------------------------------
 * แถว legacy มี created_by เป็น NULL ซึ่งมีความหมายว่า "ยังแมปผู้เขียนเดิมไม่ได้"
 * ถ้า UPDATE เขียนค่าลงไป ความหมายจะกลายเป็น "คนที่เพิ่งมาแก้เป็นคนสร้าง" ซึ่งไม่จริง
 * เป็นการยัดเจ้าของผิดคนแบบเดียวกับที่ห้ามไว้ตอน migration เพียงแต่เกิดภายหลัง
 *
 * ต้องส่ง resolver มาด้วย — ถ้าไม่ส่ง resolveAuthorId จะปฏิเสธด้วย
 * ACTIVE_USER_MAPPING_REQUIRED แทนที่จะเดาค่าผู้เขียน
 */
export async function authorFieldsFor(mode, context, resolver) {
  if (mode !== "create" && mode !== "update") {
    return { ok: false, reason: "UNKNOWN_WRITE_MODE", detail: `mode ${mode} ไม่รู้จัก` };
  }
  if (!context?.authenticated) {
    return { ok: false, reason: "NOT_AUTHENTICATED", detail: "ไม่มีตัวตนที่ยืนยันแล้ว" };
  }

  const mapped = await resolveAuthorId(context, resolver);
  if (!mapped.ok) return mapped;

  return mode === "create"
    ? { ok: true, fields: { created_by: mapped.id, updated_by: mapped.id } }
    : { ok: true, fields: { updated_by: mapped.id } };
}
