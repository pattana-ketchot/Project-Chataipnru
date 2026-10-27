// ‼ ฉบับเสนอแก้ของ webapi/api/admin/sync-sci-news.js — ยังไม่นำไปใช้
//
// ────────────────────────────────────────────────────────────────────────
// การเปลี่ยนแปลงจากฉบับเดิม
// ────────────────────────────────────────────────────────────────────────
// เดิม  : Authorization: Bearer <anon key>   -> Edge Function เห็นแค่ anon key
//         จึงแยกไม่ออกว่าผู้เรียกเป็นผู้ดูแลจริงหรือเป็นใครก็ได้ที่หยิบ anon key
//         จาก JavaScript ของหน้าเว็บไป
//
// ใหม่  : Authorization: Bearer <access token ของผู้ใช้ที่ผ่านด่านแล้ว>
//         -> Edge Function ตรวจ role/status ของผู้ใช้คนนั้นได้ด้วยตัวเอง
//
// คอมเมนต์เดิมที่อธิบายว่า Edge Function ไม่ตรวจ role ถูกปรับให้ตรงกับของใหม่
import { requireAdminUser } from '../_lib/adminAuth.js';

export default {
  async fetch(request) {
    if (request.method !== 'POST') {
      return new Response('Method Not Allowed', { status: 405 });
    }

    // ด่านที่หนึ่ง — ตรวจที่ webapi ก่อน เพื่อให้ผู้เรียกที่ไม่มีสิทธิ์ไม่ไปถึง
    // Edge Function เลย (ลดภาระและทำให้ log ของเราเห็นการปฏิเสธ)
    const auth = await requireAdminUser(request);
    if (!auth.ok) return auth.response;

    try {
      const res = await fetch(`${auth.url}/functions/v1/sync-sci-news`, {
        method: 'POST',
        headers: {
          // ส่ง token ของผู้ใช้ต่อไป ไม่ใช่ anon key
          //
          // ด่านที่สอง — Edge Function จะตรวจ role/status จาก token นี้อีกชั้น
          // ทำให้การเรียกตรงไปที่ Edge Function ด้วย anon key ไม่ผ่านอีกต่อไป
          Authorization: `Bearer ${auth.token}`,
          // apikey ยังเป็น anon key เพราะเป็นสิ่งที่ gateway ของ Supabase ต้องการ
          // เพื่อระบุโปรเจกต์ ไม่ใช่หลักฐานสิทธิ์
          apikey: auth.anonKey,
          'Content-Type': 'application/json',
        },
        body: '{}',
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'sync-sci-news returned an error');

      return Response.json(data);
    } catch (err) {
      // ไม่บันทึก token หรือรายละเอียดภายในลง log
      console.error('[admin/sync-sci-news] failed', err?.message ?? err);
      return Response.json({ error: 'บังคับอัปเดตข่าวไม่สำเร็จ' }, { status: 502 });
    }
  },
};
