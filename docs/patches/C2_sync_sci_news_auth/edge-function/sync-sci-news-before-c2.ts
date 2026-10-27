// Supabase Edge Function: sync-sci-news
//
// Fetches the SCI Connect news list page, parses out title/description/
// image_url/detail_url/published_text for each item (same parsing approach
// already used in api/sci-connect-news.js — reused, not reinvented, just
// ported to Deno since Edge Functions can't import that Node module
// directly), then saves the ones that are new into the external_news table.
// The frontend (api/sci-connect-news.js + api/sci-connect-news-detail.js)
// reads only from this table now — it never hits sci.pnru.ac.th directly —
// so this function is the only thing that talks to the source site.
//
// - detail_url is the dedup key (matches the table's UNIQUE constraint) —
//   items already in the table are skipped, only new ones are inserted.
// - For each genuinely new item, its detail page is also fetched once to
//   pick up `facebook_url` and the fuller body description (the list card's
//   <p> is a short excerpt) — same parsing approach as
//   api/sci-connect-news-detail.js. This only runs for new items (usually
//   0-2 per run), not the whole list, to keep load on the source low.
// - After a successful insert of at least one new item, the table is pruned
//   back down to the 15 newest rows (by published_at). If nothing new came
//   in this run, nothing is deleted or modified. If the upstream fetch
//   fails, we return early before touching the table at all — old rows are
//   never deleted just because the source site was unreachable.

import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

const SOURCE_URL = 'https://sci.pnru.ac.th/sciconnect.php?typeconnect=1'
const DETAIL_URL = 'https://sci.pnru.ac.th/sciconnect_detail.php'
const SOURCE_NAME = 'sci_connect'
const KEEP_LATEST = 15

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
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

// Thai Buddhist-calendar abbreviated date ("2 ก.ย. 2569") -> ISO date string
// ("2026-09-02") for the published_at column. Returns null if unparseable —
// the row still gets saved, just without a sortable date.
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

// Ported from api/sci-connect-news-detail.js's parseDetail().
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

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders })
  }

  try {
    const res = await fetch(SOURCE_URL)
    if (!res.ok) {
      return new Response(
        JSON.stringify({ error: `upstream returned ${res.status}` }),
        { status: 502, headers: { ...corsHeaders, 'Content-Type': 'application/json' } },
      )
    }

    const html = await res.text()
    const parsed = parseNewsCards(html).filter((item) => item.detail_url)

    const supabase = createClient(
      Deno.env.get('SUPABASE_URL')!,
      Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!,
    )

    // Which of the parsed items already exist? (dedup by detail_url)
    const { data: existingRows, error: selectError } = await supabase
      .from('external_news')
      .select('detail_url')
      .in('detail_url', parsed.map((item) => item.detail_url))

    if (selectError) throw selectError

    const existingUrls = new Set((existingRows || []).map((row) => row.detail_url))
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

    // Read back the current table, newest-first (nulls last, so an
    // unparseable date never outranks a real one).
    const { data: allNews, error: listError } = await supabase
      .from('external_news')
      .select('*')
      .order('published_at', { ascending: false, nullsFirst: false })

    if (listError) throw listError

    // Only prune when this run actually added something new — an empty/failed
    // sync must never delete existing rows.
    let deleted = 0
    if (inserted > 0 && (allNews?.length ?? 0) > KEEP_LATEST) {
      const idsToDelete = allNews.slice(KEEP_LATEST).map((row) => row.id)

      const { error: deleteError, count } = await supabase
        .from('external_news')
        .delete({ count: 'exact' })
        .in('id', idsToDelete)

      if (deleteError) throw deleteError
      deleted = count ?? idsToDelete.length
    }

    return new Response(
      JSON.stringify({
        parsed: parsed.length,
        already_existed: existingUrls.size,
        inserted,
        deleted,
        total_in_table: (allNews?.length ?? 0) - deleted,
        news: allNews.slice(0, KEEP_LATEST),
      }),
      { headers: { ...corsHeaders, 'Content-Type': 'application/json' } },
    )
  } catch (err) {
    return new Response(
      JSON.stringify({ error: String(err) }),
      { status: 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' } },
    )
  }
})
