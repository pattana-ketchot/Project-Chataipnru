"use client";
/**
 * หน้าทดลองระบบเปรียบเทียบสาขา (/compare) — เครื่องมือสำหรับทดสอบ ไม่ใช่หน้าจริง
 *
 * เหตุผลที่ต้องอยู่ในระบบที่ deploy แล้ว เหมือนกับหน้า /match: backend รับเฉพาะ
 * origin นี้ การเปิดไฟล์ HTML จากเครื่องตัวเองจะถูก CORS ปฏิเสธ
 */
import { useEffect, useState } from "react";

type Course = { id: string; title: string };
type Row = { dimension: string; values: string[] };
type Result = { programs: { course_id: string; title: string }[]; rows: Row[]; summary: string };

const MAX_PICK = 4;

/** ตัดชื่อเต็มให้เหลือชื่อสาขา แต่คงปีการศึกษาไว้ เพราะบางสาขามีสองฉบับให้เลือก */
function shortTitle(title: string) {
  const name = title.split("สาขาวิชา").pop()!.replace(/^หลักสูตร/, "");
  const year = title.match(/25\d{2}/)?.[0];
  return `${name.split("(")[0].trim()}${year ? ` (${year})` : ""}`;
}

export default function CompareTestPage() {
  const [token, setToken] = useState<string | null>(null);
  const [courses, setCourses] = useState<Course[]>([]);
  const [picked, setPicked] = useState<string[]>([]);
  const [result, setResult] = useState<Result | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      try {
        setCourses(await (await fetch("/api/courses")).json());
        // บัญชีชั่วคราว — หน้านี้มีไว้ทดสอบ ไม่ควรต้องสมัครก่อนทุกครั้ง
        const email = `try-${Math.random().toString(36).slice(2, 8)}@example.com`;
        const body = JSON.stringify({ email, password: "password123" });
        const h = { "Content-Type": "application/json" };
        await fetch("/api/auth/register", { method: "POST", headers: h, body });
        const r = await fetch("/api/auth/login", { method: "POST", headers: h, body });
        setToken((await r.json()).access_token);
      } catch {
        setError("เชื่อมต่อระบบไม่ได้");
      }
    })();
  }, []);

  const toggle = (id: string) =>
    setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : p.length >= MAX_PICK ? p : [...p, id]));

  async function submit() {
    setLoading(true); setError(""); setResult(null);
    try {
      const res = await fetch("/api/compare", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ course_ids: picked }),
      });
      if (!res.ok) { setError((await res.json()).detail ?? "เกิดข้อผิดพลาด"); return; }
      setResult(await res.json());
    } catch {
      setError("เรียกระบบไม่สำเร็จ กรุณาลองใหม่");
    } finally {
      setLoading(false);
    }
  }

  if (result) {
    const names = result.programs.map((p) => shortTitle(p.title));
    return (
      <main className="mx-auto max-w-6xl px-5 py-10">
        <span className="inline-flex rounded-full bg-lime px-3 py-1 text-xs font-black">หน้าทดลองระบบ</span>
        <h1 className="mt-4 text-3xl font-black">เปรียบเทียบสาขา</h1>

        {/* ตารางต้องเลื่อนแนวนอนได้เองเมื่อเทียบ 4 สาขา ไม่ใช่ดันให้ทั้งหน้าเลื่อน */}
        <div className="panel mt-6 overflow-x-auto">
          <table className="w-full min-w-[720px] text-sm">
            <thead>
              <tr className="border-b border-ink/10">
                <th className="p-4 text-left font-black">หัวข้อ</th>
                {names.map((n) => <th key={n} className="p-4 text-left font-black">{n}</th>)}
              </tr>
            </thead>
            <tbody>
              {result.rows.map((row) => (
                <tr key={row.dimension} className="border-b border-ink/5 align-top">
                  <td className="p-4 font-bold text-sage">{row.dimension}</td>
                  {row.values.map((v, i) => (
                    <td key={i} className={`p-4 leading-6 ${v.startsWith("ไม่พบ") ? "text-ink/35" : "text-ink/75"}`}>
                      {v}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {result.summary && (
          <div className="panel mt-4 p-5">
            <p className="font-black text-sage">สรุปความต่าง</p>
            <p className="mt-2 text-sm leading-6 text-ink/75">{result.summary}</p>
          </div>
        )}

        <p className="mt-4 text-xs text-ink/45">
          ช่องสีจางคือหัวข้อที่เอกสาร มคอ.2 ของหลักสูตรนั้นไม่ได้ระบุไว้ ระบบจะไม่เดาให้
        </p>

        <div className="mt-6 flex gap-3">
          <button className="btn-secondary" onClick={() => setResult(null)}>เลือกสาขาใหม่</button>
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-5xl px-5 py-10">
      <span className="inline-flex rounded-full bg-lime px-3 py-1 text-xs font-black">หน้าทดลองระบบ</span>
      <h1 className="mt-4 text-3xl font-black">เปรียบเทียบสาขา</h1>
      <p className="mt-2 text-sm text-ink/55">
        เลือก 2-4 สาขาที่อยากเทียบ ({picked.length}/{MAX_PICK})
      </p>

      <div className="panel mt-6 p-6">
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {courses.map((c) => {
            const on = picked.includes(c.id);
            const full = !on && picked.length >= MAX_PICK;
            return (
              <button key={c.id} type="button" onClick={() => toggle(c.id)} disabled={full}
                aria-pressed={on}
                className={`rounded-2xl border p-3 text-left text-sm transition ${
                  on ? "border-sage bg-sage text-white"
                     : full ? "border-ink/10 bg-white text-ink/30"
                            : "border-ink/15 bg-white hover:border-sage"}`}>
                {shortTitle(c.title)}
              </button>
            );
          })}
        </div>

        <div className="mt-6 flex items-center gap-3">
          <button className="btn-primary" onClick={submit} disabled={loading || picked.length < 2 || !token}>
            {loading ? "กำลังเปรียบเทียบ…" : "เปรียบเทียบ"}
          </button>
          <button className="btn-secondary" onClick={() => setPicked([])}>ล้างที่เลือก</button>
          {picked.length < 2 && <span className="text-sm text-ink/45">เลือกอย่างน้อย 2 สาขา</span>}
        </div>

        {error && <div role="alert" className="mt-4 rounded-2xl bg-red-50 p-4 text-sm text-red-700">{error}</div>}
      </div>
    </main>
  );
}
