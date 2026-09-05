"use client";
/**
 * หน้าทดลองระบบจับคู่สาขา (/match) — เครื่องมือสำหรับทดสอบ ไม่ใช่หน้าจริงของระบบ
 *
 * มีไว้ให้ลองกดเล่นได้โดยไม่ต้องเขียนโค้ดหรือใช้หน้า /api/docs ที่พิมพ์ JSON ภาษาไทยยาก
 * และใช้เป็นตัวอย่างการเรียก API ให้คนทำหน้าเว็บจริงดูได้ด้วย
 *
 * วางไว้ในระบบที่ deploy อยู่แล้วโดยตั้งใจ เพราะการเรียกจากไฟล์ HTML ในเครื่องจะติด CORS
 * (backend อนุญาตเฉพาะ origin ของหน้าเว็บนี้) แต่เรียกจากที่นี่เป็น origin เดียวกัน
 */
import { useEffect, useState } from "react";
import { SiteNav } from "@/components/site-nav";

const OPTIONS = {
  study_track: ["วิทย์-คณิต", "ศิลป์-คำนวณ", "ศิลป์-ภาษา", "ปวช.-ปวส.", "อื่นๆ"],
  favorite_subjects: ["คณิตศาสตร์", "คอมพิวเตอร์", "ฟิสิกส์", "เคมี", "ชีววิทยา", "ศิลปะ",
                      "คหกรรม", "เกษตร", "สุขศึกษา", "ภาษา", "สังคมศึกษา"],
  interests: ["เทคโนโลยีและคอมพิวเตอร์", "วิทยาศาสตร์และการทดลอง", "คณิตศาสตร์และการวิเคราะห์",
              "ธุรกิจและการจัดการ", "เกษตรและสิ่งแวดล้อม", "อาหารและโภชนาการ",
              "การออกแบบและสื่อสร้างสรรค์", "สุขภาพและการแพทย์"],
  aptitudes: ["ชอบวิเคราะห์ แยกแยะ และหาสาเหตุของปัญหา", "ถนัดตัวเลข การคิดคำนวณ และการแก้โจทย์ปัญหา",
              "ชอบเขียนโค้ด พัฒนาโปรแกรม และแก้บั๊ก", "ถนัดการเขียน เรียบเรียง และสื่อสารความคิด",
              "ชอบทดลอง สังเกต และค้นหาคำตอบด้วยตนเอง", "ชอบคิดไอเดียใหม่ ๆ ออกแบบ สร้างสรรค์ผลงาน",
              "ถนัดการทำงานเป็นทีม ประสานงาน และช่วยเหลือผู้อื่น", "ถนัดการพูด นำเสนอข้อมูลต่อหน้าคนหมู่มาก"],
  career_goal: ["ทำงานในองค์กรขนาดใหญ่", "เป็นผู้ประกอบการ เจ้าของธุรกิจ",
                "ทำงานที่เกี่ยวข้องกับการวิจัยและพัฒนา", "ทำงานเพื่อสังคมและสิ่งแวดล้อม",
                "ทำงานอิสระ / ฟรีแลนซ์", "ศึกษาต่อในระดับที่สูงขึ้น"],
  work_environment: ["ทำงานในออฟฟิศ", "ทำงานภาคสนาม", "ทำงานที่ไหนก็ได้ (ยืดหยุ่นเวลา)",
                     "ทำงานเป็นทีม", "ทำงานเดี่ยว โฟกัสกับงาน"],
} as const;

type Match = {
  course_id: string; title: string; score: number;
  match_percent: number; rationale: string;
};
type Result = { profile_text: string; model_used: string; confidence: string; matches: Match[] };

/** ตัดชื่อเต็มให้เหลือชื่อสาขา เพื่อให้การ์ดอ่านง่าย */
function shortTitle(title: string) {
  return title.split("สาขาวิชา").pop()!.split("(")[0].trim();
}

function Chips({ options, picked, onToggle, single = false }: {
  options: readonly string[]; picked: string[];
  onToggle: (v: string) => void; single?: boolean;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((o) => {
        const on = picked.includes(o);
        return (
          <button key={o} type="button" onClick={() => onToggle(o)}
            aria-pressed={on}
            className={`rounded-full border px-4 py-2 text-sm transition ${
              on ? "border-sage bg-sage text-white" : "border-ink/15 bg-white hover:border-sage"}`}>
            {o}
          </button>
        );
      })}
      {single && <span className="self-center text-xs text-ink/40">เลือกได้ข้อเดียว</span>}
    </div>
  );
}

export default function MatchTestPage() {
  const [token, setToken] = useState<string | null>(null);
  const [answers, setAnswers] = useState<Record<string, string[]>>({});
  const [extra, setExtra] = useState("");
  const [result, setResult] = useState<Result | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // สร้างบัญชีชั่วคราวให้อัตโนมัติ เพราะหน้านี้มีไว้ทดสอบ ไม่ควรให้ต้องสมัครก่อนทุกครั้ง
  useEffect(() => {
    (async () => {
      const email = `try-${Math.random().toString(36).slice(2, 8)}@example.com`;
      const body = JSON.stringify({ email, password: "password123" });
      const h = { "Content-Type": "application/json" };
      try {
        await fetch("/api/auth/register", { method: "POST", headers: h, body });
        const r = await fetch("/api/auth/login", { method: "POST", headers: h, body });
        setToken((await r.json()).access_token);
      } catch {
        setError("เชื่อมต่อระบบไม่ได้");
      }
    })();
  }, []);

  const toggle = (key: string, value: string, single = false) =>
    setAnswers((a) => {
      const cur = a[key] ?? [];
      if (single) return { ...a, [key]: cur.includes(value) ? [] : [value] };
      return { ...a, [key]: cur.includes(value) ? cur.filter((x) => x !== value) : [...cur, value] };
    });

  async function submit() {
    setLoading(true); setError(""); setResult(null);
    try {
      const res = await fetch("/api/match", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          study_track: answers.study_track?.[0] ?? null,
          favorite_subjects: answers.favorite_subjects ?? [],
          interests: answers.interests ?? [],
          aptitudes: answers.aptitudes ?? [],
          career_goal: answers.career_goal ?? [],
          work_environment: answers.work_environment ?? [],
          extra: extra || null,
          limit: 5,
        }),
      });
      if (!res.ok) {
        setError((await res.json()).detail ?? "เกิดข้อผิดพลาด");
        return;
      }
      setResult(await res.json());
    } catch {
      setError("เรียกระบบไม่สำเร็จ กรุณาลองใหม่");
    } finally {
      setLoading(false);
    }
  }

  const sections: [string, keyof typeof OPTIONS, boolean][] = [
    ["1. สายการเรียน", "study_track", true],
    ["2. วิชาที่ชอบ", "favorite_subjects", false],
    ["3. ความสนใจ", "interests", false],
    ["4. ความถนัด", "aptitudes", false],
    ["5. เป้าหมายอาชีพ", "career_goal", false],
    ["6. สภาพแวดล้อมการทำงาน", "work_environment", false],
  ];

  // เมื่อมีผลลัพธ์แล้วให้แทนที่แบบสอบถามทั้งหน้า ไม่ใช่ต่อท้ายด้านล่าง
  //
  // เดิมแสดงผลต่อท้ายฟอร์มซึ่งยาวเจ็ดข้อ ผู้ใช้จึงไม่เห็นว่ามีอะไรเปลี่ยนเพราะผลอยู่นอกจอ
  // และเข้าใจว่าระบบค้าง — แบบร่างของหน้าเว็บจริงก็แยกผลลัพธ์เป็นขั้นตอนต่างหากเช่นกัน
  if (result) {
    return (
      <><SiteNav active="/match"/><main className="mx-auto max-w-4xl px-5 py-10">
        <span className="inline-flex rounded-full bg-lime px-3 py-1 text-xs font-black">หน้าทดลองระบบ</span>
        <h1 className="mt-4 text-3xl font-black">สาขาที่แนะนำสำหรับคุณ</h1>

        {result.confidence === "low" && (
          <div className="mt-4 rounded-2xl bg-lime/40 p-4 text-sm">
            <strong>ผลลัพธ์ใกล้เคียงกันมาก</strong> แนะนำให้ดูหลายสาขาประกอบกัน
            ไม่ควรยึดอันดับ 1 อย่างเดียว
          </div>
        )}

        <div className="mt-5 space-y-3">
          {result.matches.map((m, i) => (
            <article key={m.course_id} className="panel p-5">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-xs font-black text-sage">อันดับ {i + 1}</p>
                  <h3 className="mt-1 text-lg font-black">{shortTitle(m.title)}</h3>
                </div>
                <div className="shrink-0 text-right">
                  <div className="text-2xl font-black">{m.match_percent}%</div>
                  <div className="text-xs text-ink/45">ดิบ {m.score.toFixed(3)}</div>
                </div>
              </div>
              <div className="mt-3 h-2 w-full rounded-full bg-ink/10">
                <div className="h-2 rounded-full bg-sage" style={{ width: `${m.match_percent}%` }} />
              </div>
              {m.rationale && <p className="mt-3 text-sm leading-6 text-ink/65">{m.rationale}</p>}
            </article>
          ))}
        </div>

        {/* เปิดให้เห็นว่าระบบเข้าใจคำตอบว่าอย่างไร ช่วยหาสาเหตุเวลาผลดูแปลก */}
        <details className="panel mt-4 p-5 text-sm">
          <summary className="cursor-pointer font-bold text-sage">ระบบเข้าใจคำตอบของคุณว่าอย่างไร</summary>
          <p className="mt-3 text-ink/65">{result.profile_text}</p>
          <p className="mt-2 text-xs text-ink/45">
            ความมั่นใจ: {result.confidence} · โมเดล: {result.model_used}
          </p>
        </details>

        <div className="mt-6 flex gap-3">
          <button className="btn-secondary" onClick={() => setResult(null)}>ย้อนกลับไปแก้คำตอบ</button>
          <button className="btn-primary" onClick={() => { setAnswers({}); setExtra(""); setResult(null); }}>
            เริ่มทำใหม่
          </button>
        </div>
      </main></>
    );
  }

  return (
    <><SiteNav active="/match"/><main className="mx-auto max-w-4xl px-5 py-10">
      <span className="inline-flex rounded-full bg-lime px-3 py-1 text-xs font-black">หน้าทดลองระบบ</span>
      <h1 className="mt-4 text-3xl font-black">ค้นหาสาขาที่เหมาะกับคุณ</h1>
      <p className="mt-2 text-sm text-ink/55">
        กดเลือกคำตอบแล้วกดปุ่มด้านล่าง ไม่ต้องตอบครบทุกข้อ — ลองตอบน้อยๆ หรือตอบกำกวมดูก็ได้
        ระบบจะบอกเองว่ามั่นใจแค่ไหน
      </p>

      <div className="panel mt-6 space-y-6 p-6 md:p-8">
        {sections.map(([label, key, single]) => (
          <div key={key}>
            <p className="mb-3 font-bold">{label}</p>
            <Chips options={OPTIONS[key]} picked={answers[key] ?? []}
                   onToggle={(v) => toggle(key, v, single)} single={single} />
          </div>
        ))}

        <div>
          <p className="mb-3 font-bold">7. อยากเล่าอะไรเพิ่มเติมไหม</p>
          <input className="field" value={extra} maxLength={1000}
                 onChange={(e) => setExtra(e.target.value)}
                 placeholder="เช่น ชอบแต่งรูปทำคลิป แต่ก็ลองเขียนเว็บบ้าง ยังไม่รู้ว่าเก่งอันไหน" />
          <p className="mt-2 text-xs text-ink/45">
            ช่องนี้มีผลกับผลลัพธ์มากที่สุด เพราะเป็นคำพูดของผู้ใช้เองไม่ใช่ตัวเลือกสำเร็จรูป
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button className="btn-primary" onClick={submit} disabled={loading || !token}>
            {loading ? "กำลังวิเคราะห์…" : "ดูสาขาที่เหมาะกับฉัน"}
          </button>
          <button className="btn-secondary" onClick={() => { setAnswers({}); setExtra(""); setResult(null); }}>
            ล้างคำตอบ
          </button>
          {!token && !error && <span className="text-sm text-ink/45">กำลังเตรียมระบบ…</span>}
        </div>

        {error && <div role="alert" className="rounded-2xl bg-red-50 p-4 text-sm text-red-700">{error}</div>}
      </div>

    </main></>
  );
}
