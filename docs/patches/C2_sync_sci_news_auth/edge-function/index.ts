// Supabase Edge Function: sync-sci-news
//
// ‼ ฉบับเสนอแก้ — ยังไม่ deploy · ดู README.md ในโฟลเดอร์เดียวกัน
//
// การเปลี่ยนแปลงจากฉบับเดิมมีเฉพาะส่วนตรวจสิทธิ์ที่เพิ่มเข้ามาใน Deno.serve()
// ตรรกะการดึงข่าว การแปลง HTML การ dedup และการตัดแถวเก่า **ไม่ถูกแก้แม้แต่บรรทัดเดียว**
//
// ────────────────────────────────────────────────────────────────────────
// ปัญหาที่แก้
// ────────────────────────────────────────────────────────────────────────
// ฉบับเดิมยกเว้น OPTIONS แล้วเข้าสู่การ sync ทันทีสำหรับทุก method ที่เหลือ
// โดยไม่ตรวจว่าผู้เรียกเป็นใคร · ประกอบกับ gateway ตั้ง verify_jwt = true ซึ่ง
// ตรวจแค่ว่า JWT ถูกต้อง ไม่ตรวจ role · และ anon key เป็น JWT ที่ถูกต้องและอยู่ใน
// JavaScript ของหน้าเว็บตามธรรมชาติ → ใครก็เรียกให้ฟังก์ชันนี้ทำงานได้
//
// ฉบับนี้เพิ่มด่านที่ตัวฟังก์ชันเอง รองรับผู้เรียกที่ถูกต้องสองทางเท่านั้น
//
//   ทาง A — ผู้ดูแล : ส่ง access token ของผู้ใช้จริงมาใน Authorization
//                     แล้วฟังก์ชันตรวจ role ∈ {admin, editor} และ status = approved
//   ทาง B — cron    : ส่ง secret เฉพาะงานตั้งเวลามาใน header x-cron-secret
//                     **ไม่ใช้ anon key เป็นหลักฐานสิทธิ์**
//
// ────────────────────────────────────────────────────────────────────────
// สิ่งที่ต้องตั้งค่าเพิ่มก่อน deploy
// ────────────────────────────────────────────────────────────────────────
//   Edge Function secret : SYNC_CRON_SECRET   (สุ่มใหม่ ไม่ซ้ำกับคีย์อื่น)
//   Vault secret         : sync_cron_secret   (ค่าเดียวกัน ให้ pg_cron อ่าน)
//
// ────────────────────────────────────────────────────────────────────────
// ทำไมยังคง verify_jwt = true ไว้
// ────────────────────────────────────────────────────────────────────────
// เอกสารทางการเสนอให้ปิด verify_jwt เมื่อรับผู้เรียกแบบ secret แต่การปิดจะทำให้
// **ด่านเดียวที่เหลือคือโค้ดในฟังก์ชันนี้** ถ้าโค้ดพลาด ฟังก์ชันจะเปิดโล่ง
//
// การคงไว้ทำให้ได้สองชั้น — gateway กันคำขอที่ไม่มี JWT ที่ถูกต้องออกไปก่อน
// แล้วฟังก์ชันตรวจสิทธิ์จริงอีกชั้น · cron ยังส่ง anon key ใน Authorization
// เหมือนเดิมเพื่อผ่านชั้นแรก แต่**สิทธิ์ของ cron มาจาก x-cron-secret เท่านั้น**

import { createClient, type SupabaseClient } from 'https://esm.sh/@supabase/supabase-js@2'

const SOURCE_URL = 'https://sci.pnru.ac.th/sciconnect.php?typeconnect=1'
const DETAIL_URL = 'https://sci.pnru.ac.th/sciconnect_detail.php'
const SOURCE_NAME = 'sci_connect'
const KEEP_LATEST = 15

const ALLOWED_ROLES = ['admin', 'editor']

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type, x-cron-secret',
}

const jsonHeaders = { ...corsHeaders, 'Content-Type': 'application/json' }

function deny(status: number, error: string) {
  return new Response(JSON.stringify({ error }), { status, headers: jsonHeaders })
}

// เทียบความลับแบบใช้เวลาคงที่ เพื่อไม่ให้เดาทีละตัวอักษรจากเวลาที่ตอบกลับได้
function timingSafeEqual(a: string, b: string): boolean {
  const enc = new TextEncoder()
  const ba = enc.encode(a)
  const bb = enc.encode(b)
  // ความยาวต่างกันถือว่าไม่ตรง แต่ยังวนครบเพื่อให้เวลาไม่ผันตามความยาวที่ตรงกัน
  let diff = ba.length ^ bb.length
  const len = Math.max(ba.length, bb.length)
  for (let i = 0; i < len; i++) {
    diff |= (ba[i] ?? 0) ^ (bb[i] ?? 0)
  }
  return diff === 0
}

/**
 * ตรวจสิทธิ์ผู้เรียก — ต้องเรียกก่อนแตะเครือข่ายภายนอกหรือฐานข้อมูลเสมอ
 *
 * คืน { ok: true, via } เมื่อผ่าน · คืน { ok: false, response } เมื่อไม่ผ่าน
 */
async function authorize(req: Request, env: {
  supabaseUrl: string
  anonKey: string
  serviceKey: string
  cronSecret: string | undefined
}): Promise<{ ok: true; via: 'cron' | 'user' } | { ok: false; response: Response }> {
  // ── ทาง B — cron ────────────────────────────────────────────────────
  const presentedSecret = req.headers.get('x-cron-secret')
  if (presentedSecret) {
    if (!env.cronSecret) {
      // ตั้งค่าไม่ครบ ถือว่าไม่ผ่าน ไม่ใช่ปล่อยผ่าน
      return { ok: false, response: deny(503, 'cron secret is not configured') }
    }
    if (timingSafeEqual(presentedSecret, env.cronSecret)) {
      return { ok: true, via: 'cron' }
    }
    // ส่ง header มาแต่ค่าไม่ตรง → ปฏิเสธทันที ไม่ตกไปเส้นทางผู้ใช้
    return { ok: false, response: deny(401, 'invalid cron secret') }
  }

  // ── ทาง A — ผู้ดูแล ─────────────────────────────────────────────────
  const authHeader = req.headers.get('authorization') ?? ''
  const token = authHeader.replace(/^Bearer\s+/i, '').trim()
  if (!token) {
    return { ok: false, response: deny(401, 'missing credentials') }
  }

  // anon key เป็น JWT ที่ถูกต้องและผ่าน getUser() ไม่ได้ (ไม่มี sub ของผู้ใช้)
  // จึงตกที่นี่โดยอัตโนมัติ — ตั้งใจให้ anon key ใช้เป็นหลักฐานสิทธิ์ไม่ได้
  const anonClient = createClient(env.supabaseUrl, env.anonKey)
  const { data: userData, error: userError } = await anonClient.auth.getUser(token)
  if (userError || !userData?.user) {
    return { ok: false, response: deny(401, 'unauthorized') }
  }

  // อ่าน role/status ด้วย service client โดยอ้างอิง id ที่ยืนยันจาก JWT แล้ว
  //
  // ใช้ service client โดยตั้งใจ เพื่อให้ผลไม่ผูกกับ RLS policy ที่อาจเปลี่ยน
  // ภายหลัง — ตัวตนของผู้เรียกมาจาก JWT ที่ตรวจแล้วข้างบน ไม่ได้มาจาก RLS
  const adminClient = createClient(env.supabaseUrl, env.serviceKey)
  const { data: profile, error: profileError } = await adminClient
    .from('user_profiles')
    .select('role, status')
    .eq('user_id', userData.user.id)
    .single()

  if (profileError || !profile) {
    return { ok: false, response: deny(403, 'forbidden') }
  }
  if (!ALLOWED_ROLES.includes(profile.role) || profile.status !== 'approved') {
    return { ok: false, response: deny(403, 'forbidden') }
  }

  return { ok: true, via: 'user' }
}

function decodeEntities(str: string): string {
  return str
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#0?39;/g, "'")
    .replace(/&nbsp;/g, ' ')
}

function cleanText(str: string): string {
  return decodeEntities(str).replace(/\s+/g, ' ').trim()
}

function parseNewsCards(html: string) {
  const cards = html.match(/<article class="news-card">[\s\S]*?<\/article>/g) || []

  return cards.map((card) => {
    const image = card.match(/<img src="([^"]+)"/)
    const title = card.match(/<h2>([\s\S]*?)<\/h2>/)
    const description = card.match(/<p>([\s\S]*?)<\/p>/)
    const date = card.match(/<div class="card-meta">\s*<span>([\s\S]*?)<\/span>/)
    const link = card.match(/<a class="card-primary-link" href="([^"]+)"/)

    return {
      title: title ? cleanText(title[1]) : '',
      description: description ? cleanText(description[1]) : '',
      image_url: image ? image[1] : null,
      detail_url: link ? link[1] : null,
      published_text: date ? cleanText(date[1]) : '',
    }
  })
}

const TH_MONTHS = ['ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.', 'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.']

function parseThaiDate(text: string): string | null {
  const match = text.trim().match(/^(\d{1,2})\s+(\S+)\s+(\d{4})$/)
  if (!match) return null

  const [, day, monthTh, yearBE] = match
  const monthIndex = TH_MONTHS.indexOf(monthTh)
  if (monthIndex === -1) return null

  const yearCE = parseInt(yearBE, 10) - 543
  return `${yearCE}-${String(monthIndex + 1).padStart(2, '0')}-${day.padStart(2, '0')}`
}

function extractSlug(detailUrl: string): string | null {
  try {
    return new URL(detailUrl).searchParams.get('slug')
  } catch {
    return null
  }
}

function parseDetailPage(html: string): { description: string | null; facebook_url: string | null } {
  const content = html.match(/<p class="lead">[\s\S]*?<\/p>\s*<div>([\s\S]*?)<\/div>\s*<div class="source-action">/)
  const description = content
    ? cleanText(content[1].replace(/<br\s*\/?>/gi, '\n').replace(/<[^>]+>/g, ''))
    : null

  const facebook = html.match(/<a class="btn btn-gold" href="([^"]+)"/)

  return {
    description,
    facebook_url: facebook ? decodeEntities(facebook[1]) : null,
  }
}

async function fetchDetail(slug: string) {
  try {
    const res = await fetch(`${DETAIL_URL}?slug=${encodeURIComponent(slug)}`)
    if (!res.ok) return null
    return parseDetailPage(await res.text())
  } catch {
    return null
  }
}

/**
 * ตรรกะ sync เดิมทั้งหมด แยกออกมาเป็นฟังก์ชันเพื่อให้ทดสอบได้โดยไม่ต้องผ่าน HTTP
 * เนื้อในไม่ถูกแก้จากฉบับเดิม
 */
// ใช้ SupabaseClient<any, any, any> เพราะโปรเจกต์นี้ไม่ได้ generate type ของ schema
// ถ้าวันหนึ่งมี generated types ให้เปลี่ยนเป็นชนิดนั้นแทน
export async function runSync(supabase: SupabaseClient<any, any, any>) {
  const res = await fetch(SOURCE_URL)
  if (!res.ok) {
    return {
      status: 502,
      body: { error: `upstream returned ${res.status}` },
    }
  }

  const html = await res.text()
  // type guard เพื่อให้ TypeScript รู้ว่าหลังกรองแล้ว detail_url ไม่เป็น null
  const parsed = parseNewsCards(html)
    .filter((item): item is typeof item & { detail_url: string } => item.detail_url !== null)

  const { data: existingRows, error: selectError } = await supabase
    .from('external_news')
    .select('detail_url')
    .in('detail_url', parsed.map((item) => item.detail_url))

  if (selectError) throw selectError

  const existingUrls = new Set((existingRows || []).map((row: { detail_url: string }) => row.detail_url))
  const newItems = parsed.filter((item) => !existingUrls.has(item.detail_url))

  let inserted = 0
  if (newItems.length > 0) {
    const rows = await Promise.all(
      newItems.map(async (item) => {
        const slug = extractSlug(item.detail_url)
        const detail = slug ? await fetchDetail(slug) : null

        return {
          title: item.title,
          description: detail?.description || item.description,
          image_url: item.image_url,
          detail_url: item.detail_url,
          published_text: item.published_text,
          published_at: parseThaiDate(item.published_text),
          source: SOURCE_NAME,
          slug,
          facebook_url: detail?.facebook_url ?? null,
        }
      }),
    )

    const { error: insertError, count } = await supabase
      .from('external_news')
      .insert(rows, { count: 'exact' })

    if (insertError) throw insertError
    inserted = count ?? rows.length
  }

  const { data: allNews, error: listError } = await supabase
    .from('external_news')
    .select('*')
    .order('published_at', { ascending: false, nullsFirst: false })

  if (listError) throw listError

  let deleted = 0
  if (inserted > 0 && (allNews?.length ?? 0) > KEEP_LATEST) {
    const idsToDelete = allNews!.slice(KEEP_LATEST).map((row: { id: string }) => row.id)

    const { error: deleteError, count } = await supabase
      .from('external_news')
      .delete({ count: 'exact' })
      .in('id', idsToDelete)

    if (deleteError) throw deleteError
    deleted = count ?? idsToDelete.length
  }

  return {
    status: 200,
    body: {
      parsed: parsed.length,
      already_existed: existingUrls.size,
      inserted,
      deleted,
      total_in_table: (allNews?.length ?? 0) - deleted,
      news: (allNews ?? []).slice(0, KEEP_LATEST),
    },
  }
}

/**
 * ตัวจัดการคำขอ แยกออกจาก Deno.serve เพื่อให้ทดสอบได้โดยไม่ต้องเปิดพอร์ต
 */
export async function handler(req: Request): Promise<Response> {
  // CORS preflight — ไม่แตะข้อมูลและไม่ต้องมีสิทธิ์
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders })
  }

  // ── รับเฉพาะ POST ───────────────────────────────────────────────────
  // ฉบับเดิมรับทุก method ที่ไม่ใช่ OPTIONS รวมถึง GET ซึ่งทำให้เรียกจากแถบ
  // ที่อยู่ของเบราว์เซอร์ได้ด้วย
  if (req.method !== 'POST') {
    return new Response(JSON.stringify({ error: 'method not allowed' }), {
      status: 405,
      headers: { ...jsonHeaders, Allow: 'POST, OPTIONS' },
    })
  }

  const supabaseUrl = Deno.env.get('SUPABASE_URL')
  const anonKey = Deno.env.get('SUPABASE_ANON_KEY')
  const serviceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')
  const cronSecret = Deno.env.get('SYNC_CRON_SECRET')

  if (!supabaseUrl || !anonKey || !serviceKey) {
    return deny(503, 'function is not configured')
  }

  // ‼ ตรวจสิทธิ์ก่อนแตะเครือข่ายภายนอกและก่อนแตะฐานข้อมูล
  //   ฉบับเดิมยิง fetch ไปยัง sci.pnru.ac.th ก่อนเสมอ ทำให้ผู้เรียกที่ไม่มีสิทธิ์
  //   ยังก่อภาระให้เว็บต้นทางได้
  const auth = await authorize(req, { supabaseUrl, anonKey, serviceKey, cronSecret })
  if (!auth.ok) return auth.response

  try {
    const supabase = createClient(supabaseUrl, serviceKey)
    const result = await runSync(supabase)
    return new Response(JSON.stringify(result.body), {
      status: result.status,
      headers: jsonHeaders,
    })
  } catch (err) {
    // ไม่ส่งรายละเอียดภายในออกไปหาผู้เรียก
    console.error('[sync-sci-news] failed', err)
    return deny(500, 'sync failed')
  }
}

// เปิดเซิร์ฟเวอร์เฉพาะเมื่อไฟล์นี้ถูกรันเป็นโปรแกรมหลักเท่านั้น
//
// ถ้าไม่มีเงื่อนไขนี้ การ `import` ไฟล์นี้จากชุดทดสอบจะเปิดพอร์ตขึ้นมาด้วย
// ทำให้เทสต์ค้างหรือชนพอร์ตกันเอง
if (import.meta.main) {
  Deno.serve(handler)
}
