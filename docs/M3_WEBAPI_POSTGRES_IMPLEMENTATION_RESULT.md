# M3 — WebAPI PostgreSQL Connection · Implementation Result

| | |
|---|---|
| เขียนโค้ด | 2026-10-06 |
| **ทดสอบครบ** | **2026-10-07** — Docker Engine 29.7.2 ทำงานแล้ว |
| **Classification** | **`M3_IMPLEMENTATION_READY_FOR_ROLLOUT`** |
| ชุดทดสอบที่ไม่ต้องใช้ DB | **82/82 ผ่าน** (เดิม 52) |
| **ชุดทดสอบที่ต้องมี PostgreSQL จริง** | **18/18 ผ่าน** — ครบเคส A ถึง I |
| **Build validation** | **ผ่าน** — image มี `server.mjs` `auth.mjs` `db.mjs` ครบและ import ได้ |
| Mutation test | **5 รูปแบบในโค้ด + 2 รูปแบบในสิทธิ์ · จับได้ทั้งหมด** |
| **dependency churn** | **0** — ตรึงให้ตรงกับ image ที่ production รันอยู่เป๊ะ · เพิ่มแค่ `pg` |
| แตะ production | **ไม่มีแม้อย่างเดียว** |
| ของชั่วคราว | **ลบครบ** — คอนเทนเนอร์ 0 · network 0 · image 0 · stub 0 |

```
แก้ production .env   NONE     Deploy Production     NONE     Restart Production  NONE
docker compose up     NONE     Production DB write   NONE     Supabase Write      NONE
ALTER/GRANT/REVOKE    NONE     Data Migration        NONE     แก้ frontend         NONE
Commit / Push / Merge NONE     รหัสผ่านจริงใน source  NONE
```

---

## 1. สถานะของตัวขวางเดิม — ปิดแล้ว

ฉบับก่อนหน้าของเอกสารนี้จัดเป็น **`M3_BLOCKED`** เพราะ Docker Desktop บนเครื่องนี้
ไม่ทำงาน จึงทำข้อ 9 (เทสต์ที่ต้องมี DB จริง) และข้อ 10 (build validation) ไม่ได้

```
docker version  ->  Client 29.7.2 | Server 29.7.2
docker info     ->  containers=4 running=2
```

Docker Engine ทำงานแล้ว · **ทั้งสองข้อทำครบและผ่านทั้งหมด** (ข้อ 10 และ 11)

### 1.1 คอนเทนเนอร์อื่นบนเครื่องนี้ไม่ถูกแตะ

ตรวจก่อนเริ่มว่าเครื่องนี้มีอะไรรันอยู่บ้าง และตั้งชื่อ/พอร์ตของตัวเองให้ไม่ชนกัน

| คอนเทนเนอร์ที่มีอยู่ก่อน | สถานะก่อน | สถานะหลัง |
|---|---|---|
| `course-advisor-system-postgres-1` (สำเนาท้องถิ่น) | Up (healthy) | **Up (healthy) เหมือนเดิม** |
| `course-advisor-system-ollama-1` | Up (healthy) | **Up (healthy) เหมือนเดิม** |
| `mko-local-pg` · `optimistic_khayyam` | Exited | **Exited เหมือนเดิม** |

ของรอบนี้ใช้ชื่อ `m3db` · `m3api` · network `m3net` · พอร์ต `127.0.0.1:55433` และ
`127.0.0.1:35001` ซึ่งไม่ชนกับของเดิม · **ลบครบแล้วทั้งหมด**

## 2. Files changed

### 2.1 ไฟล์ใหม่

| ไฟล์ | บรรทัด | หน้าที่ |
|---|---|---|
| `webapi/db.mjs` | **254** | pool · `resolveLocalUser` · `makeCloser` · `dbEnv` |
| `webapi/db.test.mjs` | **364** | 26 เทสต์ |
| `webapi/package-lock.json` | — | ตรึงเวอร์ชันไลบรารี |

### 2.2 ไฟล์ที่แก้

```
 db/20-roles.sh          |  46 ++++++++++++++   (ค้างจากรอบ provision ไม่ได้แก้รอบนี้)
 docker-compose.prod.yml |  21 ++++++++++
 webapi/Dockerfile       |  11 +++--
 webapi/auth.mjs         | 109 +++++++++++++++++++-----------
 webapi/auth.test.mjs    | 108 ++++++++++++++++++++++++++++------
 webapi/package.json     |   1 +
 webapi/server.mjs       |  61 +++++++++++++++++++
 webapi/server.test.mjs  |  38 ++++++++++++-
 8 files changed, 332 insertions(+), 63 deletions(-)
```

**ไม่แตะ `webapi/api/`** (โค้ดของทีมหน้าเว็บ) และ **ไม่แตะ frontend**

---

## 3. Dependency changes และ lock file

### 3.1 ⚠ dependency churn = **0** — ทำโดยตั้งใจ

`npm install pg` ตรง ๆ จะสร้าง lock ที่ดึงทุกตัวเป็นรุ่นใหม่สุดในช่วง `^` ที่ประกาศไว้
เพราะรีโปไม่เคยมี lock file · ลองแล้วได้ churn จริง

| package | production image | `npm install pg` เฉย ๆ |
|---|---|---|
| @ai-sdk/google | 4.0.77 | 4.0.88 |
| @supabase/supabase-js | 2.117.0 | 2.117.2 |
| ai | 7.0.111 | 7.0.128 |
| mammoth | 1.12.3 | **1.13.0** (ขยับ minor) |

**ไม่รับผลนั้น** — ติดตั้งโดยระบุเวอร์ชันที่ production ใช้อยู่ทุกตัว แล้วคืนช่วง `^`
เดิมใน `package.json` ให้เหมือนก่อนหน้า · lock จึงตรึงของเดิมไว้และเพิ่มแค่ `pg`

### 3.2 ผลหลังตรึง

| package | production image | lock ใหม่ | ผล |
|---|---|---|---|
| @ai-sdk/google | 4.0.77 | **4.0.77** | ✅ ตรงกัน |
| @supabase/supabase-js | 2.117.0 | **2.117.0** | ✅ ตรงกัน |
| ai | 7.0.111 | **7.0.111** | ✅ ตรงกัน |
| mammoth | 1.12.3 | **1.12.3** | ✅ ตรงกัน |
| pdf-parse | 2.4.5 | **2.4.5** | ✅ ตรงกัน |
| zod | 4.6.5 | **4.6.5** | ✅ ตรงกัน |
| **pg** | — | **8.23.1** | **ใหม่ตัวเดียว** |

```
จำนวนแพ็กเกจ   production image 61   ->   lock ใหม่ 75   (+14 = pg และของที่ pg ต้องใช้)
```

`package.json` เปลี่ยนบรรทัดเดียวคือเพิ่ม `"pg": "^8.23.1"` — ช่วงของตัวอื่นเหมือนเดิมทุกตัว

**deploy นี้จึงเปลี่ยนไลบรารีแค่ตัวเดียว**

### 3.3 Dockerfile ใช้ `npm ci` แทน `npm install`

```diff
-COPY package.json package-lock.json* ./
-RUN npm install --omit=dev --no-audit --no-fund
+COPY package.json package-lock.json ./
+RUN npm ci --omit=dev --no-audit --no-fund
```

| การเปลี่ยน | เหตุผล |
|---|---|
| `npm ci` | **image ได้ไลบรารีชุดเดียวกับที่ทดสอบเป๊ะ ๆ** — ตรงตามข้อ 8 ที่สั่งไว้ |
| ตัด `*` ท้ายชื่อ lock file | ของเดิมเป็น glob → lock หายแล้ว build ยังผ่านแต่ไปดึงรุ่นใหม่เงียบ ๆ · ตอนนี้ **หายแล้วต้องล้มเสียงดัง** |

---

## 4. การแก้บั๊ก `lastIdentity`

### 4.1 ของเดิม

```js
export function createRuntimeDeps(config) {
  const verifier = createSupabaseVerifier(config);
  let lastIdentity = null;                       // ใช้ร่วมกันทุกคำขอ
  return {
    async verifyToken(token) {
      lastIdentity = await verifier.verifyToken(token);
      return lastIdentity ? { userId: lastIdentity.userId } : null;
    },
    async readProfile(userId) {
      return verifier.readProfile(userId, lastIdentity);
    },
  };
}
```

```
A: verifyToken  -> lastIdentity = A
B: verifyToken  -> lastIdentity = B      <-- ทับของ A
A: readProfile  -> ได้ client ของ B
```

### 4.2 ของใหม่ — ไม่เก็บสถานะใด ๆ ไว้เลย

```js
export function createRuntimeDeps(config) {
  const verifier = createSupabaseVerifier(config);
  return {
    async verifyToken(token) {
      return verifier.verifyToken(token);        // คืน identity ทั้งก้อน
    },
    async readProfile(userId, identity) {
      return verifier.readProfile(userId, identity);
    },
  };
}
```

และ `resolveAuthContext` ส่ง identity ของคำขอนั้นต่อให้เอง

```diff
-    profile = await readProfile(identity.userId);
+    profile = await readProfile(identity.userId, identity);
```

**identity เดินทางไปกับค่าที่คืนจากฟังก์ชัน ไม่ใช่ผ่านตัวแปรร่วม**
คำขอแต่ละรายการจึงถือของตัวเองคนละชุดโดยโครงสร้าง ไม่ใช่โดยจังหวะ

### 4.3 เทสต์ที่พิสูจน์

| เทสต์ | วิธี |
|---|---|
| **จำลองลำดับที่เคยทำให้บั๊กโผล่** | A:verify → B:verify → A:readProfile → B:readProfile · `readProfile` ตรวจว่า `identity.boundTo === userId` ถ้าไม่ตรงคืน `null` → A ต้องได้ `role: admin` ของ A และ B ต้องได้ `editor` ของ B |
| **ตรวจโครงสร้างของโค้ด** | อ่าน `auth.mjs` แล้ว assert ว่าไม่มี `let lastIdentity` ใน `createRuntimeDeps` และ `readProfile` รับ `identity` เข้ามา |
| **identity ไม่หลุดเข้า context** | `context` ต้องมีแค่ 4 คีย์ · ของลับใน identity ต้องไม่ปรากฏ |

Mutation: เอา `lastIdentity` กลับมา → **เทสต์ล้มทันที** (ข้อ 7)

---

## 5. DB pool implementation

### 5.1 ค่าตั้ง — ครบตามที่สั่งทุกข้อ

```js
export const POOL_SETTINGS = Object.freeze({
  max: 5,
  min: 0,
  connectionTimeoutMillis: 5_000,
  idleTimeoutMillis: 30_000,
  statement_timeout: 5_000,
  query_timeout: 5_000,
  idle_in_transaction_session_timeout: 10_000,
  application_name: "webapi",
});
```

ตัวเลขทุกตัวอิงของจริงบน production: `max_connections` 100 · สำรองให้ superuser 3
· ใช้อยู่ 8 → **5 จาก 97 ที่ใช้ได้**

### 5.2 env — ใช้แค่ 5 ตัวตามที่อนุมัติ

```js
export function dbEnv(env = process.env) {
  const password = env.ADVISOR_WEB_PASSWORD;
  if (typeof password !== "string" || password === "") return null;   // ไม่มีค่าเริ่มต้นให้ความลับ
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
```

| ข้อห้าม | ผล |
|---|---|
| hardcode password | **ไม่มี** — อ่านจาก env เท่านั้น ไม่มีค่าเริ่มต้น |
| `DATABASE_URL` | **ไม่ใช้** |
| `postgres` superuser | **ไม่ใช้** |
| `advisor_api` | **ไม่ใช้** |

ค่าเริ่มต้นของ `user` เป็น `advisor_web` และเทสต์ยืนยันค่านี้ — ถ้ามีใครเปลี่ยนเป็น
role อื่นในอนาคต เทสต์จะล้ม

### 5.3 สองอย่างที่เพิ่มเองนอกเหนือจากที่สั่ง พร้อมเหตุผล

| สิ่งที่เพิ่ม | เหตุผล |
|---|---|
| **`pool.on("error", …)`** | ถ้าไม่ดัก error ของ client ที่ว่างอยู่จะกลายเป็น unhandled error แล้ว **ทั้งกระบวนการตาย** ทั้งที่เส้นทางสาธารณะยังให้บริการได้ |
| **ตรวจพอร์ตใน `dbEnv`** | `Number.parseInt("ไม่ใช่ตัวเลข")` ได้ `NaN` ซึ่ง `pg` จะตีความเป็นพอร์ตเริ่มต้นเงียบ ๆ · ตั้งค่าผิดควรกลายเป็น "ไม่ได้ตั้งค่า" ไม่ใช่ "ต่อไปที่อื่น" |

---

## 6. Identity resolver implementation

### 6.1 SQL — ประกาศเป็นค่าคงที่ที่ export ออกมา

```js
export const RESOLVER_SQL =
  "SELECT id, is_active, supabase_user_id FROM public.users WHERE supabase_user_id = $1";
```

export ออกมาเพื่อให้เทสต์ยืนยันได้ว่า **ใช้ `$1`** และ **ไม่มีคำว่า `email` อยู่เลย**
ถ้ามีใครแก้ SQL นี้ในอนาคต เทสต์จะล้มทันที

### 6.2 ตารางการตัดสิน — fail closed ครบทุกทาง

| สภาพ | ผล |
|---|---|
| 1 แถว · `is_active === true` | ✅ `{ ok: true, localUserId }` |
| 0 แถว | ❌ `ACCOUNT_NOT_LINKED` |
| > 1 แถว | ❌ `MAPPING_AMBIGUOUS` + `console.error` — **ไม่เลือกแถวแรก** |
| `is_active` ไม่ใช่ `true` เป๊ะ ๆ | ❌ `ACCOUNT_INACTIVE` |
| query โยน error | ❌ `IDENTITY_LOOKUP_FAILED` — ไม่ส่งรายละเอียดภายในออกไป |
| ไม่มี pool | ❌ `DATABASE_NOT_CONFIGURED` |
| `supabaseUserId` ไม่ใช่สตริงที่ใช้ได้ | ❌ `ACCOUNT_NOT_LINKED` — **ไม่ไปแตะฐานข้อมูลเลย** |

> `is_active !== true` เป๊ะ ๆ ไม่ใช่ `!is_active` — เทสต์ยิง `null` `undefined` `"true"`
> `1` `0` เข้าไปทั้งหมด · ค่าอย่าง `"true"` (สตริง) เป็น truthy ซึ่งจะผ่านถ้าเขียนหลวม

### 6.3 ข้อห้าม 5 ข้อ — บังคับทั้งในโค้ดและในฐานข้อมูล

| ห้าม | ด่านในโค้ด | ด่านในฐานข้อมูล |
|---|---|---|
| fallback ด้วยอีเมล | เทสต์ assert ว่า SQL ไม่มีคำว่า `email` | **`advisor_web` อ่าน `email` ไม่ได้** (`42501`) |
| fallback เป็น admin | เทสต์ assert ว่า SQL ไม่มี `is_admin` | อ่าน `is_admin` ไม่ได้เช่นกัน |
| Supabase uuid เป็น local id | resolver คืน `row.id` เท่านั้น | — |
| สร้างผู้ใช้ใหม่ | เทสต์ assert ว่าไฟล์ไม่มี `INSERT INTO` | **ไม่มีสิทธิ์ INSERT** |
| เชื่อ author id จาก body | `stripAuthorFields()` ของเดิม | — |

**สามข้อแรกไม่ได้พึ่งวินัยของคนเขียนโค้ดอย่างเดียว** — ต่อให้มีใครเขียน fallback
ในอนาคต ฐานข้อมูลจะปฏิเสธเอง

### 6.4 `resolveAuthorId` ปลดจาก stub แล้ว

```js
export async function resolveAuthorId(context, resolver) {
  if (!context?.authenticated || !context?.userId) return { ok:false, reason:"NOT_AUTHENTICATED", … };
  if (typeof resolver?.resolveLocalUser !== "function")
    return { ok:false, reason: ACTIVE_USER_MAPPING_REQUIRED, … };   // ไม่ได้ต่อ resolver = เขียนไม่ได้
  const found = await resolver.resolveLocalUser(context.userId);
  if (!found?.ok) return { ok:false, reason: found?.reason ?? "IDENTITY_LOOKUP_FAILED", … };
  return { ok: true, id: found.localUserId };
}
```

`authorFieldsFor(mode, context, resolver)` กลายเป็น async ตามไปด้วย · พฤติกรรมเดิม
ที่ต้องคงไว้ยังอยู่ครบ — **`update` แตะแค่ `updated_by` ห้ามแตะ `created_by`**

---

## 7. Tests

### 7.1 จำนวน

| ไฟล์ | ก่อน | หลัง |
|---|---|---|
| `auth.test.mjs` | 42 | **46** |
| `server.test.mjs` | 10 | **10** |
| **`db.test.mjs`** | — | **26** |
| **รวม** | **52** | **82 · ผ่านทั้งหมด** |

### 7.2 ความครอบคลุมเทียบกับที่สั่ง

| ข้อ | เคส | ที่ไหน | สถานะ |
|---|---|---|---|
| A | ต่อ DB สำเร็จ | disposable | ✅ **ผ่าน** |
| B | รหัสผ่านผิดถูกปฏิเสธ | disposable | ✅ **ผ่าน** (`28P01`) |
| C | uuid ที่ผูกไว้ → ผู้ใช้หนึ่งคนที่ active | `db.test.mjs` + disposable | ✅ **ผ่านทั้งสองชั้น** |
| D | uuid ที่ไม่รู้จัก → `ACCOUNT_NOT_LINKED` | `db.test.mjs` + disposable | ✅ |
| E | ผู้ใช้ถูกปิด → `ACCOUNT_INACTIVE` | `db.test.mjs` + disposable | ✅ |
| F | input แบบ SQL injection ยังเป็น parameter | `db.test.mjs` + disposable | ✅ **4 รูปแบบ + ของจริง** |
| G | อ่าน `email` ไม่ได้ | disposable | ✅ **ผ่าน** (`42501`) |
| H | `UPDATE public.users` ไม่ได้ | disposable | ✅ **ผ่าน** (`42501`) |
| I | ปิด pool ซ้ำได้ | `db.test.mjs` | ✅ |
| J | เทสต์เดิมไม่ถดถอย | ทั้งชุด | ✅ **56 เทสต์เดิมผ่านครบ** |
| + | 2 แถว → `MAPPING_AMBIGUOUS` | `db.test.mjs` | ✅ |
| + | DB error → `IDENTITY_LOOKUP_FAILED` | `db.test.mjs` | ✅ |
| + | ไม่ได้ตั้งค่า DB | `db.test.mjs` | ✅ |
| + | ไม่มี fallback email / admin | `db.test.mjs` | ✅ |
| + | Dockerfile `COPY db.mjs` | `db.test.mjs` | ✅ |
| + | `pg` อยู่ใน dependencies | `db.test.mjs` | ✅ |
| + | concurrency regression | `db.test.mjs` | ✅ |

### 7.3 ⚠ Mutation test — พิสูจน์ว่าเทสต์ล้มได้จริง

เทสต์ที่ไม่เคยเห็นมันล้ม คือเทสต์ที่ยังไม่รู้ว่าตรวจอะไรอยู่

| # | จงใจทำให้ผิด | ผล |
|---|---|---|
| M1 | เลือกแถวแรกเมื่อเจอหลายแถว (ลบด่าน `rows.length > 1`) | ✅ **จับได้ 1 ข้อ** |
| M2 | เปลี่ยน `is_active !== true` เป็น `!is_active` | ✅ **จับได้ 1 ข้อ** |
| M3 | ต่อค่าเข้าไปใน SQL ตรง ๆ แทนการใช้ `$1` | ✅ **จับได้ 1 ข้อ** |
| M4 | ลบ `db.mjs` ออกจาก `COPY` ของ Dockerfile | ✅ **จับได้ 1 ข้อ** |
| M5 | เอา `let lastIdentity` กลับมา | ✅ **จับได้ 1 ข้อ** |
| — | คืนสภาพเดิม | ✅ **82/82 ผ่าน** |

### 7.4 ⚠ ต้องแก้ harness ของ `server.test.mjs` ด้วย

`server.mjs` นำเข้า `./db.mjs` แล้ว · harness เดิมคัดลอกเข้าโฟลเดอร์ชั่วคราวแค่สองไฟล์
→ **เซิร์ฟเวอร์ทดสอบไม่ขึ้นเลย** และเทสต์ทั้ง 10 ข้อล้ม

แก้สองอย่าง

| แก้ | เหตุผล |
|---|---|
| คัดลอก `db.mjs` ไปด้วย | ไม่งั้น import ไม่เจอ |
| **วาง `pg` ปลอมใน `node_modules` ของโฟลเดอร์ชั่วคราว** | โฟลเดอร์นั้นอยู่นอกต้นไม้ของ `webapi` จึงหา `pg` จริงไม่เจอ · ของปลอม **โยน error ถ้ามีใครสร้าง pool จริง** ซึ่งเป็นสิ่งที่ต้องการ เพราะเส้นทางที่ชุดนี้ทดสอบไม่ควรแตะฐานข้อมูลเลย |

---

## 8. server.mjs — pool · shutdown · healthz

### 8.1 Graceful shutdown (เดิมไม่มีเลย)

```js
let closing = false;
async function shutdown(signal) {
  if (closing) return;                    // docker compose down อาจส่งซ้ำ
  closing = true;
  const hardStop = setTimeout(() => process.exit(1), 10_000);
  hardStop.unref();
  server.close(async () => {              // หยุดรับคำขอใหม่ -> รอคำขอที่ค้างให้จบ
    if (database) await database.close(); // -> ค่อยคืน connection
    clearTimeout(hardStop);
    process.exit(0);
  });
}
process.on("SIGTERM", () => shutdown("SIGTERM"));
process.on("SIGINT", () => shutdown("SIGINT"));
```

ครบทั้ง 4 ข้อที่สั่ง: SIGTERM · SIGINT · `server.close()` ก่อน `closePool()` · กันซ้ำ · timeout 10 วินาที

### 8.2 `/healthz`

```json
{ "status": "ok", "authConfigured": true, "dbConfigured": true, "db": "unknown", "routes": [ … ] }
```

| การตัดสิน | เหตุผล |
|---|---|
| **`status` ไม่ขึ้นกับฐานข้อมูล** | Docker `HEALTHCHECK` ตัดสินจากเส้นทางนี้ · ถ้าปล่อยให้ล้มเพราะ DB ล่ม คอนเทนเนอร์จะถูกมองว่าพัง ทั้งที่ **สองเส้นทางสาธารณะยังทำงานได้และไม่ใช้ DB เลย** |
| **`db` ไม่ยิง query ไปถาม** | `HEALTHCHECK` ตั้ง timeout 5 วินาที · ถ้า `/healthz` รอฐานข้อมูลที่ค้าง จะพากันพัง · จึงรายงาน **ผลจริงครั้งล่าสุดที่สังเกตได้** (`unknown` จนกว่าจะมีคนใช้) |

### 8.3 ไม่แสดงของต้องห้าม

| ห้ามแสดง | ที่ทำ |
|---|---|
| password | `describeConnection()` คืน `advisor_web@postgres:5432/course_advisor` — **มีเทสต์ assert ว่าไม่มีรหัสผ่าน** |
| token · email · uuid | ไม่มีจุดใดใน `db.mjs` หรือ `server.mjs` ที่ log ค่าพวกนี้ · error ของ resolver ส่งแค่ `message` ของ driver |

---

## 9. Dockerfile และ compose

### 9.1 Dockerfile

```diff
-COPY package.json package-lock.json* ./
-RUN npm install --omit=dev --no-audit --no-fund
+COPY package.json package-lock.json ./
+RUN npm ci --omit=dev --no-audit --no-fund
...
-COPY server.mjs auth.mjs ./
+COPY server.mjs auth.mjs db.mjs ./
```

**เทสต์อัตโนมัติสองข้อ** อ่านไฟล์ Dockerfile เองแล้ว assert

| เทสต์ | ตรวจอะไร |
|---|---|
| `Dockerfile คัดลอก db.mjs เข้า image` | บรรทัด `COPY` ที่มี `server.mjs` ต้องมี `auth.mjs` และ `db.mjs` ด้วย |
| `Dockerfile ใช้ npm ci กับ lock file ที่ไม่ใช่ glob` | ต้องมี `npm ci` และต้องไม่มี `package-lock.json*` |

### 9.2 compose — **แก้เฉพาะในรีโป ไม่แตะ production**

```yaml
  webapi:
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      …เดิม 3 ตัว…
      WEBAPI_DB_HOST: postgres
      WEBAPI_DB_PORT: "5432"
      WEBAPI_DB_NAME: course_advisor
      WEBAPI_DB_USER: advisor_web
      ADVISOR_WEB_PASSWORD: ${ADVISOR_WEB_PASSWORD:?ต้องตั้งค่าใน .env}
```

| ข้อสังเกตเรื่อง syntax | |
|---|---|
| `WEBAPI_DB_PORT: "5432"` | **ต้องใส่เครื่องหมายคำพูด** — YAML จะอ่าน `5432` เป็นตัวเลข แล้ว compose ต้องการสตริงสำหรับค่า environment |
| `${ADVISOR_WEB_PASSWORD:?…}` | บังคับให้ต้องมีใน `.env` · **ต่างจาก `db/20-roles.sh`** ที่ต้องเป็นทางเลือกเพราะถูก mount โดย compose ทั้งสามชุดรวม e2e · ส่วน service `webapi` มีอยู่ในไฟล์เดียว จึงบังคับได้โดยไม่กระทบใคร |

---

## 10. Build validation — **ผ่าน**

### 10.1 การ build

```
docker build -t webapi:m3-local .      ->  BUILD_EXIT = 0
```

> `webapi/api/` ไม่ได้อยู่ในรีโป (gitignore บรรทัด 49) จึงวาง stub 5 ไฟล์ไว้ชั่วคราว
> เพื่อให้ `COPY api ./api` ทำงานได้ · **ลบทิ้งแล้วหลังทดสอบ** และ `git status`
> ยืนยันว่าไม่มีไฟล์หลงเหลือ

### 10.2 ไฟล์ใน image

```
/app
├── api
├── auth.mjs          <-- ต้องมี
├── db.mjs            <-- ต้องมี (ของใหม่รอบนี้)
├── node_modules
├── package-lock.json
├── package.json
└── server.mjs        <-- ต้องมี
```

| ข้อตรวจ | ผล |
|---|---|
| `server.mjs` | ✅ มี |
| `auth.mjs` | ✅ มี |
| **`db.mjs`** | ✅ **มี** |
| **ไฟล์ `*.test.mjs` หลุดเข้า image ไหม** | ✅ **0 ไฟล์** |
| `package-lock.json` | ✅ มี (มาจาก `npm ci`) |

### 10.3 Node import ได้จริงใน image

```
docker run --rm webapi:m3-local node -e "Promise.all([import('./db.mjs'), import('./auth.mjs')]) …"

db.mjs   export 13 รายการ · RESOLVER_SQL ใช้ $1: true
auth.mjs export 23 รายการ
pg โหลดได้: true
IMPORT_EXIT = 0
```

| ข้อตรวจ | ผล |
|---|---|
| `import('./db.mjs')` | ✅ สำเร็จ |
| `import('./auth.mjs')` | ✅ สำเร็จ |
| `pg` อยู่ใน image | ✅ **8.23.1** — ตรงกับที่ lock file ตรึงไว้ |
| Node ใน image | `v22.23.3` |

### 10.4 ⚠ ทดสอบพฤติกรรมจริงของ image ด้วย ไม่ใช่แค่ว่าไฟล์อยู่ครบ

**ก. รันโดย*ไม่*ตั้งค่าฐานข้อมูล — เส้นทางสาธารณะต้องไม่พัง**

```json
{"status":"ok","authConfigured":true,"dbConfigured":false,"db":"not-configured","routes":[…]}
```

```
[webapi] ไม่พบค่าตั้งค่าฐานข้อมูล — แปลงตัวตนผู้เขียนไม่ได้ (เส้นทางสาธารณะยังทำงานปกติ)
[webapi] ฟังที่พอร์ต 3001 · 5 เส้นทาง
```

| ข้อตรวจ | ผล |
|---|---|
| คอนเทนเนอร์ขึ้นได้ทั้งที่ไม่มีค่าฐานข้อมูล | ✅ |
| **`GET /api/sci-connect-news` (PUBLIC)** | ✅ **200** |
| `POST /api/admin/ingest` ไม่มี token | ✅ **401** |

**ข. รันโดยต่อฐานข้อมูลทดสอบจริง**

```
[webapi] ตั้งค่าฐานข้อมูลแล้ว: advisor_web@m3db:5432/web_test
```

| ข้อตรวจ | ผล |
|---|---|
| `dbConfigured` | ✅ **true** |
| `db` | `unknown` — **ถูกต้อง** เพราะยังไม่มีคำขอใดไปถึง resolver |
| **log มีรหัสผ่านไหม** | ✅ **ไม่มี** — บอกแค่ `user@host:port/db` |

**ค. ด่านตรวจสิทธิ์ยังทำงานเหมือนเดิม**

```
POST /api/admin/ingest  ไม่มี token      -> 401  · log: ปฏิเสธ … ผู้เรียก: anonymous
POST /api/admin/ingest  token ปลอม       -> 401  · log: ปฏิเสธ … ผู้เรียก: anonymous (auth failed)
```

token ที่ตรวจไม่ผ่านถูก**ลดระดับเป็น anonymous** แล้วให้ `authorize()` ปฏิเสธ
ตรงกับสัญญาที่ตั้งไว้ตั้งแต่รอบ authorization · **log ไม่มี token ไม่มีอีเมล ไม่มี uuid**

**ง. Graceful shutdown**

```
docker stop -t 15 m3api
[webapi] ได้รับ SIGTERM — กำลังปิดอย่างเรียบร้อย
exit code ของคอนเทนเนอร์: 0
```

ออกด้วย **exit 0** ไม่ใช่ 137 → **ปิดเองก่อนถูก SIGKILL จริง** ไม่ใช่แค่มีโค้ดเขียนไว้

### 10.5 ข้อสังเกตจากการ build

| เรื่อง | ระดับ |
|---|---|
| **ไม่มี `.dockerignore`** → build context ส่ง `node_modules` 133 MB ไปทุกครั้ง | **ช้าเฉย ๆ ไม่กระทบความถูกต้อง** เพราะ Dockerfile `COPY` เฉพาะไฟล์ที่ระบุ · แต่ถ้าวันหนึ่งมีใครเขียน `COPY . .` จะกลายเป็นปัญหาทันที |
| Node ใน image `v22.23.3` แต่ production รัน `v22.23.2` | base image `node:22-alpine` ขยับ patch เอง · **เป็นผลของการ build ใหม่ ไม่ใช่ของการแก้โค้ด** และจะเกิดกับการ build ใด ๆ ก็ตาม |

---

## 11. Disposable DB test — **ผ่าน 18/18**

### 11.1 สภาพแวดล้อม

คอนเทนเนอร์ทิ้ง `m3db` (`pgvector/pgvector:pg16`) ผูกที่ `127.0.0.1:55433`
ตั้งเหมือน production ทุกขั้น

```
db/schema.sql
CREATE ROLE advisor_api / advisor_ingest  (+ GRANT บน public.users ตาม 20-roles.sh)
migration 001 -> 002 -> 003 -> 004 -> 005
CREATE ROLE advisor_web  (รหัสผ่านทิ้ง)
migration 006
บังคับ scram-sha-256 ใน pg_hba.conf
ผู้ใช้ทดสอบ 2 คน — คนหนึ่ง active คนหนึ่ง inactive  (ผูก supabase_user_id ทั้งคู่)
```

> ⚠ **ต้องบังคับ `scram-sha-256` ก่อน** ไม่งั้นเคส B จะผ่านทั้งที่รหัสผ่านผิด เพราะ
> image ตั้ง `trust` ให้ loopback — บทเรียนจากรอบ `advisor_web` provision

สคริปต์นำเข้า `db.mjs` **จากไฟล์จริงในรีโป** ไม่ใช่สำเนา จึงทดสอบของที่จะ deploy จริง

### 11.2 ผล

| เคส | ข้อตรวจ | ผล |
|---|---|---|
| **A** | ต่อด้วย `advisor_web` + รหัสผ่านถูก | ✅ |
| **A** | `current_user` เป็น `advisor_web` จริง | ✅ |
| **B** | **รหัสผ่านผิดถูกปฏิเสธ** | ✅ `28P01` |
| **C** | uuid ที่ผูกไว้ → ผู้ใช้หนึ่งคนที่ยังใช้งานอยู่ | ✅ |
| **D** | uuid ที่ไม่รู้จัก → `ACCOUNT_NOT_LINKED` | ✅ |
| **E** | ผู้ใช้ที่ถูกปิด → `ACCOUNT_INACTIVE` | ✅ |
| **F** | `' OR '1'='1` ไม่คืนผู้ใช้ออกมา | ✅ |
| **F** | และถูกปฏิเสธเพราะ **ชนิดไม่ใช่ uuid** ไม่ใช่เพราะ query เพี้ยน | ✅ |
| **G** | `SELECT email` | ✅ **`42501`** |
| **G** | `SELECT *` | ✅ **`42501`** |
| **G** | สามคอลัมน์ที่ resolver ใช้ อ่านได้ | ✅ |
| **H** | `UPDATE public.users` | ✅ **`42501`** |
| **H** | `DELETE public.users` | ✅ **`42501`** |
| **H** | `INSERT public.users` | ✅ **`42501`** |
| — | `application_name` ถึงเซิร์ฟเวอร์จริง | ✅ `webapi` |
| — | `statement_timeout` ถึงเซิร์ฟเวอร์จริง | ✅ `5s` |
| **I** | ปิด pool ครั้งแรก | ✅ |
| **I** | ปิดซ้ำไม่ทำอะไรและไม่พัง | ✅ |

```
ผ่าน 18 ข้อ · ไม่ผ่าน 0 ข้อ   ·   EXIT = 0
```

### 11.3 ⚠ ข้อความที่พิสูจน์ว่า F ทำงานถูกจริง

```
[webapi] ค้นหาตัวตนในฐานข้อมูลไม่สำเร็จ: invalid input syntax for type uuid: "' OR '1'='1"
```

ฐานข้อมูลปฏิเสธเพราะ **ค่าที่ส่งมาไม่ใช่ uuid** ไม่ใช่เพราะ SQL พัง →
ยืนยันว่าค่าเดินทางเป็น **parameter** จริง และชนิดของคอลัมน์เป็นด่านอีกชั้น

### 11.4 ⚠ Mutation test บนสิทธิ์จริง — พิสูจน์ว่า G และ H ไม่ได้ผ่านด้วยเหตุผลที่ผิด

บทเรียนจากรอบก่อน: บน production เคยมีข้อตรวจ `UPDATE` ที่ "ผ่าน" เพราะ
`default_transaction_read_only` ไม่ใช่เพราะสิทธิ์ · รอบนี้จึงพิสูจน์ด้วยการให้สิทธิ์จริง

| จงใจทำให้ผิด | ผล |
|---|---|
| `GRANT SELECT ON public.users TO advisor_web` (ระดับตาราง) | ✅ **G ล้ม 2 ข้อ** — อ่าน `email` และ `SELECT *` ได้ |
| เพิ่ม `GRANT UPDATE ON public.users` | ✅ **H ล้มเพิ่มอีก 1 ข้อ** |
| `REVOKE` แล้วคืนสิทธิ์ระดับคอลัมน์เดิม | ✅ **กลับมา 18/18** |

---

## 12. Regression

| ชุด | ก่อนรอบนี้ | หลังรอบนี้ |
|---|---|---|
| `auth.test.mjs` | 42 ผ่าน | **46 ผ่าน** |
| `server.test.mjs` | 10 ผ่าน | **10 ผ่าน** |
| **รวมของเดิม** | **52 ผ่าน** | **56 ผ่าน · ไม่มีข้อใดล้ม** |

เทสต์เดิม 4 ข้อที่เคย assert ว่า `resolveAuthorId` ปฏิเสธเสมอ **ถูกเขียนใหม่** ให้ตรงกับ
สัญญาใหม่ — ไม่ได้ลบทิ้ง · ข้อที่ยังต้องจริงเหมือนเดิมยังอยู่ครบ (ไม่ยืนยันตัวตนต้อง
ปฏิเสธ · mode ผิดต้องปฏิเสธ · ปฏิเสธแล้วต้องไม่คืน `fields`)

---

## 13. Git diff summary

```
 db/20-roles.sh          |  46 ++++++++++++++   <- ค้างจากรอบ provision
 docker-compose.prod.yml |  21 ++++++++++
 webapi/Dockerfile       |  11 +++--
 webapi/auth.mjs         | 109 +++++++++++++++++++-----------
 webapi/auth.test.mjs    | 108 ++++++++++++++++++++++++++++------
 webapi/package.json     |   1 +
 webapi/server.mjs       |  61 +++++++++++++++++++
 webapi/server.test.mjs  |  38 ++++++++++++-
 8 files changed, 332 insertions(+), 63 deletions(-)

ไฟล์ใหม่  webapi/db.mjs (254)  webapi/db.test.mjs (364)  webapi/package-lock.json
```

**ยังไม่ commit** — HEAD ยังเป็น `cf4fb16`

---

## 14. Remaining blockers

### 14.1 ไม่มีตัวขวางของการ implementation เหลืออยู่

| # | เรื่องที่เคยค้าง | สถานะ |
|---|---|---|
| 1 | Docker Desktop ไม่ทำงาน | ✅ **ปิดแล้ว** — ทดสอบครบทั้งข้อ 9 และ 10 |

### 14.2 สิ่งที่ต้องทำก่อน deploy — ไม่ใช่ตัวขวางของรอบนี้

| # | เรื่อง | ใครทำ |
|---|---|---|
| 1 | **`ADVISOR_WEB_PASSWORD` ยังไม่อยู่ใน production `.env`** | เจ้าของ — **รอบแยก** (compose ตั้ง `:?` ไว้ ถ้าไม่มี service จะไม่ขึ้น) |
| 2 | **คัดลอก `webapi/api/` จากรีโปหน้าเว็บก่อน build** | ขั้นตอนตอน deploy |
| 3 | **เก็บ image เดิมไว้ก่อน build ใหม่** (`docker tag`) | ขั้นตอนตอน deploy — จำเป็นสำหรับการถอนกลับ |
| 4 | ยังไม่ commit อะไรเลยตั้งแต่ `cf4fb16` | รออนุมัติ |

### 14.3 ⚠ เรื่องที่ต้องรู้ก่อนกด deploy

**deploy นี้ไม่ใช่ "เพิ่มแค่ pool"** — image ที่รัน production อยู่เป็นของ **2026-09-22**
ซึ่งยังไม่มี `auth.mjs` เลย · การ deploy จะพา **authorization foundation (`cf4fb16`)**
ขึ้นไปเป็นครั้งแรกพร้อมกัน

| สิ่งที่จะเปลี่ยนไปพร้อมกัน | ผลที่ต้องเฝ้าดู |
|---|---|
| ด่านตรวจสิทธิ์กลางเริ่มบังคับ | `/api/admin/*` ถูกตรวจ **สองชั้น** (ด่านกลาง + `requireAdminUser` เดิม) |
| `validateRouteTable` + `process.exit(1)` | ROUTES ไม่ครบ → **คอนเทนเนอร์ไม่ขึ้นเลย** |
| `/healthz` รูปแบบใหม่ | เพิ่ม `authConfigured` · `dbConfigured` · `db` · `routes[].level` |
| pool + resolver ของ M3 | ของใหม่จริงของรอบนี้ |

production **ไม่ได้เปิดโล่งอยู่** — handler ทั้งสามเรียก `requireAdminUser` เองอยู่แล้ว
(ตรวจโค้ดในคอนเทนเนอร์จริงแล้วในรอบ design) · ด่านกลางเป็นชั้นเพิ่ม

## 15. Final classification

# `M3_IMPLEMENTATION_READY_FOR_ROLLOUT`

| เกณฑ์ที่สั่งไว้ | ผล |
|---|---|
| เพิ่ม `pg` · สร้าง `db.mjs` ตามสเปกทุกค่า | ✅ |
| resolver fail closed ครบ 6 กรณี · ห้าม fallback 5 ข้อ | ✅ |
| แก้บั๊ก `lastIdentity` + concurrency regression test | ✅ |
| ปลด `resolveAuthorId` จาก stub | ✅ |
| `server.mjs` — pool · graceful shutdown · `/healthz` | ✅ **พิสูจน์ใน image จริงด้วย exit 0 ตอน SIGTERM** |
| Dockerfile `COPY db.mjs` + assertion อัตโนมัติ | ✅ |
| compose source + `depends_on` | ✅ |
| lock file · **dependency churn = 0** | ✅ |
| **เทสต์ที่ไม่ต้องใช้ DB** | ✅ **82/82** |
| **เทสต์ที่ต้องมี DB จริง (A–I)** | ✅ **18/18** |
| **Build validation (ข้อ 10)** | ✅ **ไฟล์ครบ · import ได้ · pg 8.23.1 ใน image** |
| mutation test | ✅ **5 ในโค้ด + 2 ในสิทธิ์ · จับได้ทั้งหมด** |
| ลบของชั่วคราว | ✅ **คอนเทนเนอร์ 0 · network 0 · image 0 · stub 0** |
| regression หลังลบของชั่วคราว | ✅ **82/82** |
| แตะ production | ✅ **ไม่มีแม้อย่างเดียว** |

**ไม่ใช่ `M3_BLOCKED`** — ตัวขวางเดิมปิดแล้ว
**ไม่ใช่ `M3_IMPLEMENTATION_FAILED`** — ไม่มีข้อตรวจใดไม่ผ่าน

## 16. Exact next step

```
1. อนุมัติ commit  (ค้างมาตั้งแต่ cf4fb16)
     db/20-roles.sh · db/migrations/006 · eval/web_identity_mapping_check.py
     webapi/{db.mjs, db.test.mjs, package-lock.json, และไฟล์ที่แก้ 5 ไฟล์}
     docker-compose.prod.yml · เอกสาร 8 ฉบับ

2. รอบแยก — เพิ่ม ADVISOR_WEB_PASSWORD ลง production .env
     เจ้าของรันเองด้วย read -rsp บนเซิร์ฟเวอร์ (ขั้นตอนอยู่ใน M3 design ข้อ 8.3)
     ตรวจความยาว 64 · ไม่เขียนทับของเดิม · grep -c ต้องได้ 1

3. รอบแยก — deploy
     docker tag ของเดิมเป็น webapi:before-m3   <-- ทำก่อน build เสมอ
     คัดลอก webapi/api/ จากรีโปหน้าเว็บ
     docker compose build webapi
     ตรวจ image ว่ามี server.mjs auth.mjs db.mjs ครบก่อน up
     docker compose up -d webapi
     ตรวจ /healthz -> authConfigured:true · dbConfigured:true
     ตรวจ pg_stat_activity -> application_name=webapi · usename=advisor_web
     ยิงเส้นทาง PUBLIC 2 เส้นทาง -> ต้อง 200
     เฝ้าดู log 10 นาที

4. รอบแยก — endpoint ที่เขียนข้อมูลจริง + ปิด G3_API_ENFORCEMENT_PENDING_B1
```

### 16.1 ขอบเขตที่ต้องพูดให้ชัด

**M3 ยังไม่ทำให้มีใครเขียนข้อมูลได้** — ทั้ง 5 เส้นทางที่ `webapi` รับผิดชอบวันนี้
ไม่มีเส้นทางใดเขียน `web.site_courses` หรือ `web.news` · `authorFieldsFor()` จึงยัง
ไม่มีผู้เรียก

M3 ทำให้ **เครื่องมือพร้อม** — การสร้าง endpoint เขียนข้อมูลเป็นรอบแยก

## บันทึกการเข้าถึงข้อมูลในรอบนี้

| ระบบ | การเข้าถึง |
|---|---|
| production | **ไม่ได้แตะเลยในรอบนี้** — ไม่มีทั้งอ่านและเขียน |
| Supabase | **ไม่ได้เข้าถึงเลย** |
| ไฟล์ในรีโป | แก้ 8 ไฟล์ · สร้างใหม่ 3 ไฟล์ · **ไม่แตะ `webapi/api/` และ frontend** |
| npm | ติดตั้งไลบรารีลง `webapi/node_modules` และสร้าง lock file |
| git | ไม่ commit ไม่ push |

---

## STOP

# `M3_IMPLEMENTATION_READY_FOR_ROLLOUT`

```
เทสต์ที่ไม่ต้องใช้ DB     82/82 ผ่าน
เทสต์ที่ต้องมี DB จริง    18/18 ผ่าน  (A ถึง I ครบ)
build validation        image มี server.mjs auth.mjs db.mjs ครบ · import ได้ · pg 8.23.1
พฤติกรรมของ image       PUBLIC 200 แม้ไม่มี DB · EDITOR ไม่มี token 401 · SIGTERM ออก exit 0
mutation test           5 ในโค้ด + 2 ในสิทธิ์ · จับได้ทั้งหมด
dependency churn        0 — เพิ่มแค่ pg@8.23.1
ของชั่วคราว              ลบครบ — คอนเทนเนอร์ 0 · network 0 · image 0 · stub 0
production              ไม่ได้แตะเลยทั้งอ่านและเขียน
```

**ไม่ commit · ไม่ push · ไม่ deploy · ไม่แตะ production .env** — HEAD ยังเป็น `cf4fb16`

เรื่องที่รอการตัดสินใจ

1. **อนุมัติ commit** — ค้างสะสมมาทั้งชุดตั้งแต่ `db/20-roles.sh` จนถึงรอบนี้
2. **รอบแยก**: เพิ่ม `ADVISOR_WEB_PASSWORD` ลง production `.env`
   ⚠ compose ตั้ง `:?` ไว้ — **ถ้าไม่มีตัวแปรนี้ service `webapi` จะไม่ขึ้น**
   จึงต้องทำ**ก่อน** deploy ไม่ใช่หลัง
3. **รอบแยก**: deploy — ⚠ เป็น deploy ที่พา authorization foundation ขึ้นไปด้วย
   เป็นครั้งแรก ไม่ใช่ deploy ที่เพิ่มแค่ pool (ข้อ 14.3)
