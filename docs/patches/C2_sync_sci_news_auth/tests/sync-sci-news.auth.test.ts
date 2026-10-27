// ชุดทดสอบด่านสิทธิ์ของ Edge Function sync-sci-news (ฉบับเสนอแก้)
//
// รันด้วย:  deno test --allow-env --allow-net=esm.sh tests/sync-sci-news.auth.test.ts
//
// ────────────────────────────────────────────────────────────────────────
// วิธีจำลอง
// ────────────────────────────────────────────────────────────────────────
// ดัก globalThis.fetch ชั้นเดียว แล้วแยกเส้นทางตาม URL ซึ่งครอบทั้ง
//   · เว็บข่าวต้นทาง sci.pnru.ac.th
//   · ทุกคำขอที่ supabase-js ยิงออกไป (auth และ REST)
// จึงได้ทดสอบ client จริงโดยไม่ต้องแก้โค้ด production และไม่ต้องต่อเน็ต
//
// ‼ ข้อทดสอบที่สำคัญที่สุดคือ "ไม่ยิงเว็บต้นทางเมื่อสิทธิ์ไม่ผ่าน"
//    เพราะเป็นจุดที่ฉบับเดิมพลาด — ยิง fetch ก่อนตรวจสิทธิ์เสมอ

import { assertEquals } from 'https://deno.land/std@0.224.0/assert/mod.ts'

const SUPABASE_URL = 'https://project.supabase.co'
const ANON_KEY = 'anon-key-for-test'
const SERVICE_KEY = 'service-key-for-test'
const CRON_SECRET = 'cron-secret-for-test'

Deno.env.set('SUPABASE_URL', SUPABASE_URL)
Deno.env.set('SUPABASE_ANON_KEY', ANON_KEY)
Deno.env.set('SUPABASE_SERVICE_ROLE_KEY', SERVICE_KEY)
Deno.env.set('SYNC_CRON_SECRET', CRON_SECRET)

const { handler } = await import('../edge-function/index.ts')

// ───────────────────────────────────────────────────────────────────────
// ตัวจำลอง
// ───────────────────────────────────────────────────────────────────────

const NEWS_HTML = `
<article class="news-card">
  <img src="https://example.test/a.jpg">
  <h2>ข่าวทดสอบหนึ่ง</h2>
  <p>คำอธิบายย่อ</p>
  <div class="card-meta"> <span>2 ก.ย. 2569</span>
  <a class="card-primary-link" href="https://sci.pnru.ac.th/sciconnect_detail.php?slug=one">อ่าน</a>
</article>`

type Call = { url: string; method: string }

interface MockOptions {
  /** แถวที่มีอยู่แล้วในตาราง external_news */
  existing?: string[]
  /** ผลของ auth.getUser — null = token ใช้ไม่ได้ */
  user?: { id: string } | null
  /** โปรไฟล์ที่จะคืนจาก user_profiles — null = ไม่มีแถว */
  profile?: { role: string; status: string } | null
}

function installMock(opts: MockOptions = {}) {
  const calls: Call[] = []
  const original = globalThis.fetch

  globalThis.fetch = ((input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url
    const method = (init?.method ?? (input instanceof Request ? input.method : 'GET')).toUpperCase()
    calls.push({ url, method })

    const json = (body: unknown, status = 200) =>
      Promise.resolve(new Response(JSON.stringify(body), {
        status,
        headers: { 'Content-Type': 'application/json' },
      }))

    // ── เว็บข่าวต้นทาง ───────────────────────────────────────────────
    if (url.startsWith('https://sci.pnru.ac.th/sciconnect.php')) {
      return Promise.resolve(new Response(NEWS_HTML, { status: 200 }))
    }
    if (url.startsWith('https://sci.pnru.ac.th/sciconnect_detail.php')) {
      return Promise.resolve(new Response('<p class="lead">x</p><div>เนื้อหาเต็ม</div><div class="source-action">', { status: 200 }))
    }

    // ── auth.getUser ────────────────────────────────────────────────
    if (url.includes('/auth/v1/user')) {
      if (!opts.user) return json({ message: 'invalid token' }, 401)
      return json({ id: opts.user.id, aud: 'authenticated' })
    }

    // ── REST: user_profiles ─────────────────────────────────────────
    if (url.includes('/rest/v1/user_profiles')) {
      // .single() ตั้ง Accept เป็น application/vnd.pgrst.object+json
      // PostgREST จึงคืน **object เดี่ยว** ไม่ใช่ array
      // และคืน 406 พร้อม error body เมื่อไม่พบแถว
      if (!opts.profile) {
        return json({ code: 'PGRST116', message: 'JSON object requested, multiple (or no) rows returned' }, 406)
      }
      return json(opts.profile)
    }

    // ── REST: external_news ─────────────────────────────────────────
    if (url.includes('/rest/v1/external_news')) {
      if (method === 'POST') return json([{ id: 'new-1' }])
      if (method === 'DELETE') return json([])
      // select ที่มี .in('detail_url', ...) คือการเช็คซ้ำ
      if (url.includes('detail_url=in.')) {
        return json((opts.existing ?? []).map((u) => ({ detail_url: u })))
      }
      return json([{ id: 'row-1', detail_url: 'https://sci.pnru.ac.th/sciconnect_detail.php?slug=one', published_at: '2026-09-02' }])
    }

    throw new Error(`คำขอที่ไม่ได้จำลองไว้: ${method} ${url}`)
  }) as typeof fetch

  return {
    calls,
    restore: () => { globalThis.fetch = original },
    /** ยิงเว็บต้นทางไปแล้วกี่ครั้ง */
    upstreamCalls: () => calls.filter((c) => c.url.includes('sci.pnru.ac.th')).length,
  }
}

function post(headers: Record<string, string> = {}) {
  return new Request('https://project.supabase.co/functions/v1/sync-sci-news', {
    method: 'POST',
    headers,
  })
}

// ───────────────────────────────────────────────────────────────────────
// method
// ───────────────────────────────────────────────────────────────────────

Deno.test('OPTIONS ผ่านได้โดยไม่ต้องมีสิทธิ์ และไม่แตะเว็บต้นทาง', async () => {
  const mock = installMock()
  try {
    const res = await handler(new Request('https://x/', { method: 'OPTIONS' }))
    assertEquals(res.status, 200)
    assertEquals(mock.upstreamCalls(), 0)
  } finally { mock.restore() }
})

Deno.test('GET ถูกปฏิเสธด้วย 405 — ฉบับเดิมรับ GET แล้ว sync เลย', async () => {
  const mock = installMock()
  try {
    const res = await handler(new Request('https://x/', { method: 'GET' }))
    assertEquals(res.status, 405)
    assertEquals(res.headers.get('Allow'), 'POST, OPTIONS')
    assertEquals(mock.upstreamCalls(), 0)
  } finally { mock.restore() }
})

// ───────────────────────────────────────────────────────────────────────
// ทาง B — cron secret
// ───────────────────────────────────────────────────────────────────────

Deno.test('cron secret ถูกต้อง -> sync ทำงาน', async () => {
  const mock = installMock({ existing: [] })
  try {
    const res = await handler(post({ 'x-cron-secret': CRON_SECRET }))
    assertEquals(res.status, 200)
    const body = await res.json()
    assertEquals(body.parsed, 1)
    assertEquals(body.inserted, 1)
  } finally { mock.restore() }
})

Deno.test('cron secret ผิด -> 401 และไม่ยิงเว็บต้นทาง', async () => {
  const mock = installMock()
  try {
    const res = await handler(post({ 'x-cron-secret': 'wrong-secret-value' }))
    assertEquals(res.status, 401)
    assertEquals(mock.upstreamCalls(), 0)
  } finally { mock.restore() }
})

Deno.test('ส่ง cron secret มาแต่ฟังก์ชันยังไม่ตั้งค่า -> 503 ไม่ใช่ปล่อยผ่าน', async () => {
  const mock = installMock()
  Deno.env.delete('SYNC_CRON_SECRET')
  try {
    const res = await handler(post({ 'x-cron-secret': 'any-value' }))
    assertEquals(res.status, 503)
    assertEquals(mock.upstreamCalls(), 0)
  } finally {
    Deno.env.set('SYNC_CRON_SECRET', CRON_SECRET)
    mock.restore()
  }
})

// ───────────────────────────────────────────────────────────────────────
// ทาง A — token ของผู้ใช้
// ───────────────────────────────────────────────────────────────────────

Deno.test('‼ anon key เป็น bearer -> 401 (นี่คือช่องที่ปิด)', async () => {
  // จำลองว่า getUser ปฏิเสธ เพราะ anon key ไม่มี sub ของผู้ใช้
  const mock = installMock({ user: null })
  try {
    const res = await handler(post({ Authorization: `Bearer ${ANON_KEY}` }))
    assertEquals(res.status, 401)
    assertEquals(mock.upstreamCalls(), 0)
  } finally { mock.restore() }
})

Deno.test('ไม่ส่งอะไรมาเลย -> 401', async () => {
  const mock = installMock()
  try {
    const res = await handler(post())
    assertEquals(res.status, 401)
    assertEquals(mock.upstreamCalls(), 0)
  } finally { mock.restore() }
})

Deno.test('token ใช้ได้แต่ role = user -> 403', async () => {
  const mock = installMock({ user: { id: 'u1' }, profile: { role: 'user', status: 'approved' } })
  try {
    const res = await handler(post({ Authorization: 'Bearer user-token' }))
    assertEquals(res.status, 403)
    assertEquals(mock.upstreamCalls(), 0)
  } finally { mock.restore() }
})

Deno.test('admin แต่ status ยังไม่ approved -> 403', async () => {
  const mock = installMock({ user: { id: 'u1' }, profile: { role: 'admin', status: 'pending' } })
  try {
    const res = await handler(post({ Authorization: 'Bearer user-token' }))
    assertEquals(res.status, 403)
    assertEquals(mock.upstreamCalls(), 0)
  } finally { mock.restore() }
})

Deno.test('ไม่มีแถวใน user_profiles -> 403 (ไม่เดาว่ามีสิทธิ์)', async () => {
  const mock = installMock({ user: { id: 'u1' }, profile: null })
  try {
    const res = await handler(post({ Authorization: 'Bearer user-token' }))
    assertEquals(res.status, 403)
    assertEquals(mock.upstreamCalls(), 0)
  } finally { mock.restore() }
})

Deno.test('admin + approved -> sync ทำงาน', async () => {
  const mock = installMock({ user: { id: 'u1' }, profile: { role: 'admin', status: 'approved' }, existing: [] })
  try {
    const res = await handler(post({ Authorization: 'Bearer admin-token' }))
    assertEquals(res.status, 200)
    const body = await res.json()
    assertEquals(body.inserted, 1)
  } finally { mock.restore() }
})

Deno.test('editor + approved -> sync ทำงาน', async () => {
  const mock = installMock({ user: { id: 'u2' }, profile: { role: 'editor', status: 'approved' }, existing: [] })
  try {
    const res = await handler(post({ Authorization: 'Bearer editor-token' }))
    assertEquals(res.status, 200)
  } finally { mock.restore() }
})

// ───────────────────────────────────────────────────────────────────────
// ตรรกะ sync เดิมต้องไม่เปลี่ยนพฤติกรรม
// ───────────────────────────────────────────────────────────────────────

Deno.test('ข่าวที่มีอยู่แล้วไม่ถูกเพิ่มซ้ำ', async () => {
  const mock = installMock({
    existing: ['https://sci.pnru.ac.th/sciconnect_detail.php?slug=one'],
  })
  try {
    const res = await handler(post({ 'x-cron-secret': CRON_SECRET }))
    const body = await res.json()
    assertEquals(body.already_existed, 1)
    assertEquals(body.inserted, 0)
    // ไม่มีของใหม่ -> ต้องไม่ลบอะไร
    assertEquals(body.deleted, 0)
  } finally { mock.restore() }
})

Deno.test('เว็บต้นทางล้ม -> 502 และไม่แตะฐานข้อมูล', async () => {
  const original = globalThis.fetch
  const dbCalls: string[] = []
  globalThis.fetch = ((input: RequestInfo | URL) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url
    if (url.includes('sci.pnru.ac.th')) {
      return Promise.resolve(new Response('', { status: 503 }))
    }
    if (url.includes('/rest/v1/')) dbCalls.push(url)
    return Promise.resolve(new Response('[]', { status: 200, headers: { 'Content-Type': 'application/json' } }))
  }) as typeof fetch

  try {
    const res = await handler(post({ 'x-cron-secret': CRON_SECRET }))
    assertEquals(res.status, 502)
    assertEquals(dbCalls.length, 0)
  } finally { globalThis.fetch = original }
})
