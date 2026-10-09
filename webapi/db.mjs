/**
 * การเชื่อมต่อ PostgreSQL ของ webapi และการแปลงตัวตน Supabase เป็นผู้ใช้ของเรา
 *
 * ทำไมบริการนี้ต้องต่อฐานข้อมูลเอง
 * --------------------------------
 * webapi ยืนยันตัวตนด้วย Supabase แต่คอลัมน์ created_by / updated_by ของตารางใน
 * schema `web` เป็น FK ไป public.users(id) ของฐานข้อมูลเรา ซึ่งเป็น uuid คนละชุด
 * กับ auth.users ของ Supabase · ต้องมีคนแปลงระหว่างสองฝั่ง และที่เดียวที่รู้คำตอบคือ
 * คอลัมน์ public.users.supabase_user_id ที่ migration 006 สร้างไว้
 *
 * ใช้ role ไหน
 * -----------
 * `advisor_web` เท่านั้น — ไม่ใช่ `postgres` และไม่ใช่ `advisor_api`
 *
 * `advisor_web` มีสิทธิ์อ่าน public.users แค่สามคอลัมน์ (id, is_active,
 * supabase_user_id) ระดับคอลัมน์ ไม่มี SELECT ระดับตาราง จึงอ่าน email หรือ
 * password_hash ไม่ได้เลยแม้โค้ดจะเขียนผิด · ดู docs/MIGRATION_006_*.md
 *
 * ข้อห้ามที่บังคับด้วยฐานข้อมูล ไม่ใช่ด้วยวินัยของคนเขียนโค้ด
 * --------------------------------------------------------
 * ต่อให้มีใครเพิ่ม fallback ด้วย email ในอนาคต query นั้นจะถูกฐานข้อมูลปฏิเสธด้วย
 * permission denied ไม่ใช่ทำงานเงียบ ๆ แล้วจับคู่ผิดคน
 */
import pgDefault from "pg";

/** เหตุผลที่การแปลงตัวตนไม่ผ่าน — ใช้อ้างอิงในเอกสาร ใน log และในชุดทดสอบ */
export const DATABASE_NOT_CONFIGURED = "DATABASE_NOT_CONFIGURED";
export const ACCOUNT_NOT_LINKED = "ACCOUNT_NOT_LINKED";
export const ACCOUNT_INACTIVE = "ACCOUNT_INACTIVE";
export const MAPPING_AMBIGUOUS = "MAPPING_AMBIGUOUS";
export const IDENTITY_LOOKUP_FAILED = "IDENTITY_LOOKUP_FAILED";

/**
 * SQL ของตัวแปลงตัวตน
 *
 * ประกาศเป็นค่าคงที่ที่ export ออกไป เพื่อให้ชุดทดสอบยืนยันได้ว่า
 *   1. ใช้ $1 เป็น parameter ไม่ใช่การต่อสตริง
 *   2. ไม่มีคำว่า email อยู่ในนั้นเลย (กัน fallback ที่ห้ามไว้)
 * ถ้าวันหนึ่งมีคนแก้ SQL นี้ ชุดทดสอบจะล้มทันที
 */
export const RESOLVER_SQL =
  "SELECT id, is_active, supabase_user_id FROM public.users WHERE supabase_user_id = $1";

/**
 * ค่าตั้งของ pool
 *
 * ตัวเลขทุกตัวมาจากของจริงบน production ไม่ใช่ค่าที่เดา
 * (max_connections = 100 · สำรองให้ superuser 3 · ใช้อยู่จริงราว 8)
 */
export const POOL_SETTINGS = Object.freeze({
  // 5 จาก 97 ที่ใช้ได้ — เหลือที่ให้ backend และ ingest worker เหลือเฟือ
  max: 5,
  // ไม่จอง connection ไว้ตอนไม่มีทราฟฟิก
  min: 0,
  // ต่อไม่ได้ใน 5 วินาที = ยอมแพ้ ดีกว่าค้างจนคำขอหมดเวลาไปเอง
  connectionTimeoutMillis: 5_000,
  // คืน connection ที่ว่างนานกลับไปให้เซิร์ฟเวอร์
  idleTimeoutMillis: 30_000,
  // ค่าตั้งต้นของเซิร์ฟเวอร์เป็น 0 (ไม่จำกัด) — ถ้าไม่ตั้งเอง query ที่ค้าง
  // จะถือ connection ไว้ตลอดกาล
  statement_timeout: 5_000,
  query_timeout: 5_000,
  idle_in_transaction_session_timeout: 10_000,
  // ทำให้สืบได้จาก pg_stat_activity ว่า connection ไหนเป็นของบริการนี้
  application_name: "webapi",
});

/**
 * อ่านค่าตั้งค่าจาก environment
 *
 * คืน null เมื่อไม่มีรหัสผ่าน — ตั้งค่าไม่ครบคือ "ต่อฐานข้อมูลไม่ได้"
 * ไม่ใช่ "ต่อด้วยค่าเริ่มต้นบางอย่าง"
 *
 * ค่าที่ไม่ใช่ความลับมีค่าเริ่มต้นได้ เพราะมันคือค่าที่ยืนยันแล้วจาก compose จริง
 * ส่วนรหัสผ่าน **ไม่มีค่าเริ่มต้นเด็ดขาด**
 */
export function dbEnv(env = process.env) {
  const password = env.ADVISOR_WEB_PASSWORD;
  if (typeof password !== "string" || password === "") return null;

  const port = Number.parseInt(env.WEBAPI_DB_PORT ?? "5432", 10);
  if (!Number.isInteger(port) || port <= 0 || port > 65535) return null;

  return {
    host: env.WEBAPI_DB_HOST || "postgres",
    port,
    database: env.WEBAPI_DB_NAME || "course_advisor",
    user: env.WEBAPI_DB_USER || "advisor_web",
    password,
  };
}

/**
 * ข้อความบรรยายการเชื่อมต่อสำหรับใส่ใน log
 *
 * **ไม่มีรหัสผ่าน** — ตั้งใจให้เรียกใช้ได้อย่างปลอดภัยทุกที่
 */
export function describeConnection(config) {
  if (!config) return "ไม่ได้ตั้งค่า";
  return `${config.user}@${config.host}:${config.port}/${config.database}`;
}

/**
 * สร้าง pool
 *
 * รับตัวสร้างเข้ามาได้เพื่อให้ชุดทดสอบใส่ของปลอมแทนได้โดยไม่ต้องมีฐานข้อมูลจริง
 */
export function createPool(config, PoolCtor = pgDefault.Pool) {
  const pool = new PoolCtor({ ...config, ...POOL_SETTINGS });

  // ถ้าไม่ดักไว้ error ของ client ที่ว่างอยู่จะกลายเป็น unhandled error
  // แล้วทำให้ทั้งกระบวนการตาย ทั้งที่เส้นทางสาธารณะยังให้บริการได้
  if (typeof pool.on === "function") {
    pool.on("error", (err) => {
      console.error("[webapi] pool ของฐานข้อมูลผิดพลาด:", err?.message ?? err);
    });
  }
  return pool;
}

/**
 * ตัวปิด pool ที่เรียกซ้ำได้
 *
 * `pool.end()` ของ pg เรียกซ้ำแล้วจะ reject — ตัวครอบนี้จึงจำว่าปิดไปแล้ว
 * เพราะเส้นทางปิดโปรแกรมอาจถูกกระตุ้นสองครั้ง (SIGTERM แล้ว SIGINT ตามมา)
 */
export function makeCloser(pool) {
  let closed = false;
  let pending = null;
  return async function closePool() {
    if (closed) return false;
    closed = true;
    pending = Promise.resolve(pool?.end?.());
    await pending;
    return true;
  };
}

/**
 * แปลงตัวตนของผู้ใช้ Supabase เป็น public.users.id ของฐานข้อมูลเรา
 *
 * ปฏิเสธเมื่อไม่แน่ใจเสมอ (fail closed) — ทุกเส้นทางที่ไม่ใช่ "เจอหนึ่งคนและยังใช้งานอยู่"
 * คือการปฏิเสธ ไม่มีการเดา ไม่มีการเลือกแถวแรก ไม่มีการสร้างผู้ใช้ใหม่
 */
export function createIdentityResolver(pool) {
  // สถานะล่าสุดที่ "สังเกตได้จริง" จากการใช้งาน ไม่ใช่จากการยิง query ถามสุขภาพ
  //
  // ⚠ ทำไม /healthz ไม่ยิง SELECT 1 ไปถามฐานข้อมูล
  // Docker HEALTHCHECK ตั้ง timeout ไว้ 5 วินาที ถ้า /healthz รอฐานข้อมูลที่ค้างอยู่
  // คอนเทนเนอร์จะถูกตัดสินว่า unhealthy ทั้งที่เส้นทางสาธารณะสองเส้นทางยังทำงานได้
  // และไม่ได้ใช้ฐานข้อมูลเลย · จึงรายงานสิ่งที่สังเกตได้แทนการไปถามใหม่
  let lastOutcome = "unknown";
  return {
    /** "unknown" ก่อนมีใครใช้ · "up"/"down" ตามผลจริงครั้งล่าสุด */
    status: () => lastOutcome,

    async resolveLocalUser(supabaseUserId) {
      if (!pool) {
        return {
          ok: false,
          reason: DATABASE_NOT_CONFIGURED,
          detail: "ยังไม่ได้ตั้งค่าการเชื่อมต่อฐานข้อมูล",
        };
      }
      // ค่าที่ไม่ใช่สตริงไม่ควรเดินทางมาถึงที่นี่ — ถ้ามาถึงแปลว่าผู้เรียกผิดสัญญา
      // จึงปฏิเสธ ไม่ใช่พยายามแปลงให้
      if (typeof supabaseUserId !== "string" || supabaseUserId === "") {
        return {
          ok: false,
          reason: ACCOUNT_NOT_LINKED,
          detail: "ไม่มีรหัสผู้ใช้ Supabase ที่ใช้ค้นหาได้",
        };
      }

      let rows;
      try {
        // ส่งเป็น parameter เสมอ — ค่าที่หน้าตาเหมือน SQL จึงเป็นได้แค่ข้อความค้นหา
        // ไม่มีทางกลายเป็นคำสั่ง · และคอลัมน์เป็นชนิด uuid ค่าที่ไม่ใช่ uuid
        // จะได้ error ไม่ใช่ผลลัพธ์ที่ดูเหมือนจริง
        const result = await pool.query(RESOLVER_SQL, [supabaseUserId]);
        rows = result?.rows ?? [];
        lastOutcome = "up";
      } catch (err) {
        // ไม่ส่งรายละเอียดภายในออกไปหาผู้เรียก และไม่บันทึก uuid ลง log
        lastOutcome = "down";
        console.error("[webapi] ค้นหาตัวตนในฐานข้อมูลไม่สำเร็จ:", err?.message ?? err);
        return {
          ok: false,
          reason: IDENTITY_LOOKUP_FAILED,
          detail: "ติดต่อฐานข้อมูลเพื่อยืนยันตัวตนไม่ได้",
        };
      }

      if (rows.length === 0) {
        return {
          ok: false,
          reason: ACCOUNT_NOT_LINKED,
          detail: "บัญชีนี้ยังไม่ได้เชื่อมกับผู้ใช้ในระบบ",
        };
      }
      if (rows.length > 1) {
        // ไม่ควรเกิดเพราะมี partial unique index บน supabase_user_id อยู่แล้ว
        // ถ้าเกิดแปลว่าข้อสมมติพังไปแล้ว ต้องมีคนมาดู ไม่ใช่เลือกแถวแรกไปใช้
        console.error(
          `[webapi] พบผู้ใช้ ${rows.length} แถวสำหรับตัวตนเดียว — ปฏิเสธและต้องตรวจสอบ`,
        );
        return {
          ok: false,
          reason: MAPPING_AMBIGUOUS,
          detail: "พบผู้ใช้มากกว่าหนึ่งคนสำหรับตัวตนเดียว",
        };
      }

      const row = rows[0];
      if (row?.is_active !== true) {
        return {
          ok: false,
          reason: ACCOUNT_INACTIVE,
          detail: "บัญชีนี้ถูกปิดการใช้งาน",
        };
      }
      if (!row?.id) {
        return {
          ok: false,
          reason: IDENTITY_LOOKUP_FAILED,
          detail: "แถวที่พบไม่มีรหัสผู้ใช้",
        };
      }

      return { ok: true, localUserId: String(row.id) };
    },
  };
}

/**
 * ประกอบทุกอย่างสำหรับใช้งานจริง
 *
 * คืน null เมื่อตั้งค่าไม่ครบ — ผู้เรียกต้องรับมือกับ null ไม่ใช่ได้ของปลอมที่
 * ดูเหมือนใช้งานได้
 */
export function createDatabase(env = process.env, PoolCtor = pgDefault.Pool) {
  const config = dbEnv(env);
  if (!config) return null;
  const pool = createPool(config, PoolCtor);
  const resolver = createIdentityResolver(pool);
  return {
    pool,
    config: { ...config, password: undefined },
    describe: () => describeConnection(config),
    resolver,
    status: () => resolver.status(),
    close: makeCloser(pool),
  };
}
