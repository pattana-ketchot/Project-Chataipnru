// ‼ ฉบับเสนอแก้ของ webapi/api/_lib/adminAuth.js — ยังไม่นำไปใช้
//
// การเปลี่ยนแปลงมีจุดเดียว: เพิ่ม `token` เข้าไปในค่าที่คืนเมื่อผ่านด่าน
// เพื่อให้ผู้เรียกส่ง token ของผู้ใช้ต่อไปยังบริการปลายทางได้ แทนการส่ง anon key
//
// เป็นการเพิ่มฟิลด์อย่างเดียว ผู้เรียกเดิม (extract-file, ingest) ไม่ต้องแก้
// และพฤติกรรมการตรวจสิทธิ์ไม่เปลี่ยน

import { createClient } from '@supabase/supabase-js';

const ADMIN_ROLES = ['admin', 'editor'];

// ตรวจสิทธิ์ผู้เรียกใช้ร่วมกันทุก endpoint ใน api/admin/* — ต้อง login และมี role
// admin/editor สถานะ approved เท่านั้น ใช้ supabase client ที่ scope ด้วย token ของ
// ผู้เรียกเอง (ไม่ใช่ shared key) เพื่อให้ RLS บังคับด้วยตัวตนจริงของผู้เรียกด้วย
export async function requireAdminUser(request) {
  const url = process.env.VITE_SUPABASE_URL;
  const anonKey = process.env.VITE_SUPABASE_ANON_KEY;
  if (!url || !anonKey) {
    return { ok: false, response: Response.json({ error: 'Supabase env vars are missing' }, { status: 500 }) };
  }

  const authHeader = request.headers.get('authorization') || '';
  const token = authHeader.replace(/^Bearer\s+/i, '');
  if (!token) {
    return { ok: false, response: Response.json({ error: 'Missing Authorization token' }, { status: 401 }) };
  }

  const supabase = createClient(url, anonKey, {
    global: { headers: { Authorization: `Bearer ${token}` } },
  });

  const { data: { user }, error: userError } = await supabase.auth.getUser(token);
  if (userError || !user) {
    return { ok: false, response: Response.json({ error: 'Unauthorized' }, { status: 401 }) };
  }

  const { data: profile } = await supabase
    .from('user_profiles')
    .select('role, status')
    .eq('user_id', user.id)
    .single();

  if (!ADMIN_ROLES.includes(profile?.role) || profile?.status !== 'approved') {
    return { ok: false, response: Response.json({ error: 'Forbidden' }, { status: 403 }) };
  }

  // `token` คือ access token ของผู้เรียกที่ผ่านการตรวจแล้ว
  //
  // ⚠ ผู้เรียกที่นำไปส่งต่อต้องส่งไปยังบริการของโปรเจกต์เดียวกันเท่านั้น
  //   ห้ามส่งไปยังปลายทางภายนอก และห้ามบันทึกลง log
  return { ok: true, supabase, user, url, anonKey, token };
}
