// ชุดทดสอบฝั่ง webapi ของ patch C2
//
// รันด้วย:  node --test tests/webapi-sync-sci-news.test.mjs
//           (ต้องรันจากโฟลเดอร์ที่ resolve @supabase/supabase-js ได้ — ดู TEST_STATUS.md)
//
// ────────────────────────────────────────────────────────────────────────
// สิ่งที่ทดสอบ
// ────────────────────────────────────────────────────────────────────────
//   1. requireAdminUser คืน `token` ของผู้เรียกกลับมาด้วย (ฟิลด์ที่เพิ่มใน patch)
//   2. sync-sci-news ส่ง **token ของผู้ใช้** ไปที่ Edge Function ไม่ใช่ anon key
//   3. `apikey` ยังเป็น anon key เหมือนเดิม
//   4. เส้นทางปฏิเสธยังทำงาน (401 / 403 / 405)
//   5. ไม่มี token หรือ secret รั่วออกทาง log
//
// วิธีจำลอง — ดัก globalThis.fetch ชั้นเดียว แยกเส้นทางตาม URL
// ครอบทั้งคำขอที่ supabase-js ยิง (auth, REST) และคำขอไปยัง Edge Function

import { test } from 'node:test';
import assert from 'node:assert/strict';

const URL_BASE = 'https://project.supabase.co';
const ANON = 'anon-key-for-test';
const USER_TOKEN = 'user-access-token-for-test';

process.env.VITE_SUPABASE_URL = URL_BASE;
process.env.VITE_SUPABASE_ANON_KEY = ANON;

const { requireAdminUser } = await import('../api/_lib/adminAuth.js');
const syncRoute = (await import('../api/admin/sync-sci-news.js')).default;

// ───────────────────────────────────────────────────────────────────────
// ตัวจำลอง
// ───────────────────────────────────────────────────────────────────────

function installMock({ user = { id: 'u1' }, profile = { role: 'admin', status: 'approved' }, edgeStatus = 200 } = {}) {
  const original = globalThis.fetch;
  const calls = [];

  globalThis.fetch = (input, init = {}) => {
    const url = typeof input === 'string' ? input : input?.url ?? String(input);
    const headers = init.headers ?? {};
    calls.push({ url, method: (init.method ?? 'GET').toUpperCase(), headers });

    const json = (body, status = 200) =>
      Promise.resolve(new Response(JSON.stringify(body), {
        status,
        headers: { 'Content-Type': 'application/json' },
      }));

    if (url.includes('/auth/v1/user')) {
      if (!user) return json({ message: 'invalid token' }, 401);
      return json({ id: user.id, aud: 'authenticated' });
    }

    if (url.includes('/rest/v1/user_profiles')) {
      // .single() -> PostgREST คืน object เดี่ยว · 406 เมื่อไม่พบแถว
      if (!profile) return json({ code: 'PGRST116', message: 'no rows' }, 406);
      return json(profile);
    }

    if (url.includes('/functions/v1/sync-sci-news')) {
      if (edgeStatus !== 200) return json({ error: 'edge rejected' }, edgeStatus);
      return json({ parsed: 1, inserted: 1, deleted: 0 });
    }

    throw new Error(`คำขอที่ไม่ได้จำลองไว้: ${url}`);
  };

  return {
    calls,
    restore: () => { globalThis.fetch = original; },
    edgeCall: () => calls.find((c) => c.url.includes('/functions/v1/sync-sci-news')),
  };
}

function req(method = 'POST', token = USER_TOKEN) {
  const headers = new Headers();
  if (token) headers.set('authorization', `Bearer ${token}`);
  return new Request('https://site.test/api/admin/sync-sci-news', { method, headers });
}

// จับ console.error ไว้ตรวจว่าไม่มีอะไรรั่ว
function captureErrors(fn) {
  const original = console.error;
  const lines = [];
  console.error = (...args) => lines.push(args.map(String).join(' '));
  return Promise.resolve(fn()).finally(() => { console.error = original; }).then((r) => [r, lines]);
}

// ───────────────────────────────────────────────────────────────────────
// 1. requireAdminUser คืน token
// ───────────────────────────────────────────────────────────────────────

test('requireAdminUser คืน token ของผู้เรียกกลับมาด้วย', async () => {
  const mock = installMock();
  try {
    const auth = await requireAdminUser(req());
    assert.equal(auth.ok, true);
    assert.equal(auth.token, USER_TOKEN, 'token ต้องตรงกับที่ส่งมาใน Authorization');
    assert.equal(auth.anonKey, ANON);
    assert.equal(auth.url, URL_BASE);
  } finally { mock.restore(); }
});

test('requireAdminUser ไม่คืน token เมื่อไม่ผ่านด่าน', async () => {
  const mock = installMock({ profile: { role: 'user', status: 'approved' } });
  try {
    const auth = await requireAdminUser(req());
    assert.equal(auth.ok, false);
    assert.equal(auth.token, undefined);
    assert.equal(auth.response.status, 403);
  } finally { mock.restore(); }
});

// ───────────────────────────────────────────────────────────────────────
// 2. ส่ง token ของผู้ใช้ ไม่ใช่ anon key  ← หัวใจของ patch
// ───────────────────────────────────────────────────────────────────────

test('‼ ส่ง Authorization เป็น token ของผู้ใช้ ไม่ใช่ anon key', async () => {
  const mock = installMock();
  try {
    const res = await syncRoute.fetch(req());
    assert.equal(res.status, 200);

    const edge = mock.edgeCall();
    assert.ok(edge, 'ต้องมีการเรียก Edge Function');
    assert.equal(edge.headers.Authorization, `Bearer ${USER_TOKEN}`);
    assert.notEqual(edge.headers.Authorization, `Bearer ${ANON}`, 'ต้องไม่ส่ง anon key เป็น bearer');
  } finally { mock.restore(); }
});

test('apikey ยังเป็น anon key เหมือนเดิม', async () => {
  const mock = installMock();
  try {
    await syncRoute.fetch(req());
    assert.equal(mock.edgeCall().headers.apikey, ANON);
  } finally { mock.restore(); }
});

test('ส่ง method POST และ body ว่างไปยัง Edge Function', async () => {
  const mock = installMock();
  try {
    await syncRoute.fetch(req());
    assert.equal(mock.edgeCall().method, 'POST');
  } finally { mock.restore(); }
});

// ───────────────────────────────────────────────────────────────────────
// 3. เส้นทางปฏิเสธ
// ───────────────────────────────────────────────────────────────────────

test('GET -> 405 และไม่เรียก Edge Function', async () => {
  const mock = installMock();
  try {
    const res = await syncRoute.fetch(req('GET'));
    assert.equal(res.status, 405);
    assert.equal(mock.edgeCall(), undefined);
  } finally { mock.restore(); }
});

test('ไม่มี token -> 401 และไม่เรียก Edge Function', async () => {
  const mock = installMock();
  try {
    const res = await syncRoute.fetch(req('POST', null));
    assert.equal(res.status, 401);
    assert.equal(mock.edgeCall(), undefined);
  } finally { mock.restore(); }
});

test('role = user -> 403 และไม่เรียก Edge Function', async () => {
  const mock = installMock({ profile: { role: 'user', status: 'approved' } });
  try {
    const res = await syncRoute.fetch(req());
    assert.equal(res.status, 403);
    assert.equal(mock.edgeCall(), undefined);
  } finally { mock.restore(); }
});

test('status ไม่ approved -> 403', async () => {
  const mock = installMock({ profile: { role: 'admin', status: 'pending' } });
  try {
    const res = await syncRoute.fetch(req());
    assert.equal(res.status, 403);
  } finally { mock.restore(); }
});

test('ไม่มีแถวใน user_profiles -> 403', async () => {
  const mock = installMock({ profile: null });
  try {
    const res = await syncRoute.fetch(req());
    assert.equal(res.status, 403);
  } finally { mock.restore(); }
});

// ───────────────────────────────────────────────────────────────────────
// 4. Edge Function ปฏิเสธ -> webapi คืน 502
// ───────────────────────────────────────────────────────────────────────

test('Edge Function คืน 401 -> webapi คืน 502 และไม่รั่ว token ลง log', async () => {
  const mock = installMock({ edgeStatus: 401 });
  try {
    const [res, logs] = await captureErrors(() => syncRoute.fetch(req()));
    assert.equal(res.status, 502);
    const joined = logs.join('\n');
    assert.ok(!joined.includes(USER_TOKEN), 'log ต้องไม่มี token');
    assert.ok(!joined.includes(ANON), 'log ต้องไม่มี anon key');
  } finally { mock.restore(); }
});

// ───────────────────────────────────────────────────────────────────────
// 5. ไม่รั่วค่าออกทางผลลัพธ์
// ───────────────────────────────────────────────────────────────────────

test('ผลลัพธ์ที่ส่งกลับผู้เรียกไม่มี token หรือ anon key', async () => {
  const mock = installMock();
  try {
    const res = await syncRoute.fetch(req());
    const text = await res.text();
    assert.ok(!text.includes(USER_TOKEN));
    assert.ok(!text.includes(ANON));
  } finally { mock.restore(); }
});
