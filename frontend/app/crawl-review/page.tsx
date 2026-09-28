"use client";
/**
 * หน้าตรวจไฟล์หลักสูตรที่ crawler พบ — สำหรับผู้ดูแลเท่านั้น (Phase 3B)
 *
 * ทำอะไร: แสดงคิวจาก mko.v_crawl_queue · เปิดไฟล์ให้ดู · อนุมัติ / ไม่เกี่ยวข้อง / ถอน
 * ไม่ทำอะไร: ไม่นำเข้าคลังความรู้ ไม่สร้าง embedding ไม่สร้างหลักสูตรใหม่
 *
 * สิทธิ์ตัดสินที่ backend ไม่ใช่ที่นี่
 * ----------------------------------
 * หน้านี้ไม่ได้ตรวจว่าใครเป็นผู้ดูแล — UserOut ของ /users/me ไม่มีฟิลด์ is_admin
 * และตั้งใจไม่เพิ่ม เพราะการให้หน้าเว็บตัดสินเองไม่มีประโยชน์ด้านความปลอดภัยเลย
 * ที่นี่ยิงคำขอไปแล้วแปล 401/403 ที่ backend ตอบกลับเป็นข้อความให้คนอ่าน
 * คนที่ไม่ใช่ผู้ดูแลจะเห็นข้อความว่าไม่มีสิทธิ์ ไม่ใช่เห็นคิวแล้วกดไม่ได้
 *
 * ทำไมเปิด PDF ด้วย blob ไม่ใช่ window.open ตรง ๆ
 * ----------------------------------------------
 * GET /crawl-review/{id}/pdf ต้องมี Authorization header ซึ่งแท็บใหม่หรือ iframe
 * ส่งไปไม่ได้ จึงต้องดึงไฟล์มาด้วย fetch ที่แนบ token แล้วทำเป็น blob URL เปิดแทน
 * ผลที่ยอมรับ: ไฟล์ถูกโหลดเข้าหน่วยความจำทั้งก้อน (เพดาน 50 MB จาก crawler) และ
 * ตัวอ่าน PDF ขอเฉพาะช่วงไบต์ไม่ได้ ซึ่งรับได้เพราะเป็นเครื่องมือภายในของผู้ดูแล
 *
 * ไม่มี staging_path ที่ใดในหน้านี้
 * -------------------------------
 * backend ไม่ส่งมาให้ และที่นี่ก็ไม่ประกอบ path ของไฟล์เอง การเปิดไฟล์ใช้ id เท่านั้น
 */
import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, FileText, RefreshCw, XCircle } from "lucide-react";
import { SiteNav } from "@/components/site-nav";
import { ApiError, api } from "@/lib/api";
import { CONFIDENCE_TEXT, formatBytes, mustChooseCourse, review } from "@/lib/crawl-review";
import type { QueueItem, QueuePage } from "@/lib/crawl-review";
import type { Course } from "@/lib/types";

const TOKEN_KEY = "course_advisor_token";

type Notice = { kind: "ok" | "warn" | "err"; text: string };
type Pending = { id: string; action: "approve" | "ignore" | "undo" };

/** แปลข้อผิดพลาดจาก backend เป็นข้อความที่คนอ่านได้ */
function message(err: unknown): string {
  if (!(err instanceof ApiError)) return "เชื่อมต่อระบบไม่ได้";
  if (err.status === 401) return "เซสชันหมดอายุ กรุณาเข้าสู่ระบบอีกครั้ง";
  if (err.status === 403) return "บัญชีนี้ไม่มีสิทธิ์ดูคิวตรวจเอกสาร ต้องเป็นผู้ดูแลระบบ";
  if (err.status === 429) return "ส่งคำขอบ่อยเกินไป กรุณารอสักครู่";
  return err.message;
}

export default function CrawlReviewPage() {
  const [token, setToken] = useState<string | null>(null);
  const [checking, setChecking] = useState(true);
  const [queue, setQueue] = useState<QueuePage | null>(null);
  const [courses, setCourses] = useState<Course[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [forbidden, setForbidden] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [choice, setChoice] = useState<Record<string, string>>({});
  const [reason, setReason] = useState<Record<string, string>>({});
  const [confirm, setConfirm] = useState<Pending | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async (t: string) => {
    setLoading(true); setError(""); setForbidden(false);
    try {
      setQueue(await review.pending(t));
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) setForbidden(true);
      else if (err instanceof ApiError && err.status === 401) { setToken(null); window.localStorage.removeItem(TOKEN_KEY); }
      setError(message(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const saved = window.localStorage.getItem(TOKEN_KEY);
    setChecking(false);
    if (!saved) return;
    setToken(saved);
    void load(saved);
    // รายชื่อหลักสูตรใช้เส้นทาง /courses เดิมที่มีอยู่แล้ว ไม่ได้เพิ่มเส้นทางใหม่
    api.courses().then(setCourses).catch(() => setCourses([]));
  }, [load]);

  async function signIn(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setError(""); setLoading(true);
    try {
      const pair = await api.login(String(f.get("email")), String(f.get("password")));
      window.localStorage.setItem(TOKEN_KEY, pair.access_token);
      setToken(pair.access_token);
      await load(pair.access_token);
      api.courses().then(setCourses).catch(() => setCourses([]));
    } catch (err) {
      setError(err instanceof ApiError && err.status === 401
        ? "อีเมลหรือรหัสผ่านไม่ถูกต้อง" : message(err));
    } finally {
      setLoading(false);
    }
  }

  async function openPdf(item: QueueItem) {
    if (!token) return;
    setNotice(null);
    try {
      // ต้องแนบ token จึงใช้ fetch ไม่ใช่ window.open ตรง ๆ (ดูหัวไฟล์)
      const res = await fetch((process.env.NEXT_PUBLIC_API_URL ?? "") + review.pdfPath(item.id),
                              { headers: { Authorization: `Bearer ${token}` } });
      if (!res.ok) {
        setNotice({ kind: "err", text: res.status === 404
          ? "เปิดไฟล์ไม่ได้ — ไฟล์อาจไม่อยู่ในที่เก็บแล้ว เนื้อไฟล์ไม่ตรงกับที่บันทึกไว้ หรือไม่ใช่ PDF"
          : message(new ApiError(res.status, "เปิดไฟล์ไม่ได้")) });
        return;
      }
      const url = URL.createObjectURL(await res.blob());
      const opened = window.open(url, "_blank");
      if (!opened) setNotice({ kind: "warn", text: "เบราว์เซอร์ปิดกั้นการเปิดแท็บใหม่ กรุณาอนุญาตแล้วลองอีกครั้ง" });
      // ปล่อยหน่วยความจำคืนหลังแท็บใหม่อ่านไฟล์ไปแล้ว
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch {
      setNotice({ kind: "err", text: "เปิดไฟล์ไม่ได้ กรุณาลองใหม่" });
    }
  }

  async function decide(item: QueueItem, action: Pending["action"]) {
    if (!token || !item.file_sha256) return;
    setBusy(item.id); setNotice(null); setConfirm(null);
    try {
      if (action === "approve") {
        const code = choice[item.id] || item.course_code || "";
        const d = await review.approve(token, item.id, { file_sha256: item.file_sha256, course_code: code });
        setNotice({ kind: "ok", text: `อนุมัติแล้ว — ผูกกับ ${d.course_title ?? d.course_code} · ยังไม่นำเข้าคลังความรู้จนกว่าจะรันตัวนำเข้า` });
      } else if (action === "ignore") {
        await review.ignore(token, item.id, { file_sha256: item.file_sha256, reason: reason[item.id] || "ไม่เกี่ยวข้องกับหลักสูตร" });
        setNotice({ kind: "ok", text: "บันทึกว่าไม่เกี่ยวข้องแล้ว รายการออกจากคิว" });
      } else {
        await review.undo(token, item.id, { file_sha256: item.file_sha256 });
        setNotice({ kind: "ok", text: "ถอนการตัดสินใจแล้ว รายการกลับเข้าคิว" });
      }
    } catch (err) {
      // 409 = ไฟล์เปลี่ยนไปแล้ว หรือมีการตัดสินใจอยู่แล้ว — ห้ามส่งซ้ำอัตโนมัติ
      // ต้องให้คนเปิดไฟล์ดูใหม่ก่อนตัดสินใจอีกครั้ง
      if (err instanceof ApiError && err.status === 409) {
        setNotice({ kind: "warn", text: `${err.message} — โหลดคิวใหม่ให้แล้ว กรุณาเปิดไฟล์ตรวจอีกครั้งก่อนตัดสินใจ` });
      } else {
        setNotice({ kind: "err", text: message(err) });
      }
    } finally {
      setBusy(null);
      // โหลดคิวใหม่ทุกครั้งหลังตัดสินใจ ไม่ลบแถวออกจากหน้าจอเอง
      // เพื่อให้สิ่งที่เห็นเป็นสถานะจริงจากเซิร์ฟเวอร์ ไม่ใช่สิ่งที่เราเดาว่าน่าจะเป็น
      if (token) await load(token);
    }
  }

  const nav = <SiteNav active="/crawl-review" />;
  const wrap = (children: React.ReactNode) => <main className="min-h-screen bg-cream/40">{nav}{children}</main>;

  if (checking) return wrap(<Status text="กำลังตรวจสอบสิทธิ์…" />);

  if (!token) return wrap(
    <section className="mx-auto max-w-md px-5 py-16">
      <div className="panel p-7 md:p-10">
        <p className="text-sm font-bold text-sage">เฉพาะผู้ดูแลระบบ</p>
        <h1 className="mt-2 text-3xl font-black">คิวตรวจเอกสารหลักสูตร</h1>
        <p className="mt-2 text-sm text-ink/55">เข้าสู่ระบบด้วยบัญชีผู้ดูแลเพื่อดูไฟล์ที่รอการตรวจ</p>
        {error && <div role="alert" className="mt-5 rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</div>}
        <form className="mt-7 space-y-4" onSubmit={signIn}>
          <label><span className="label">อีเมล</span>
            <input className="field" name="email" type="email" autoComplete="email" required /></label>
          <label><span className="label">รหัสผ่าน</span>
            <input className="field" name="password" type="password" autoComplete="current-password" required /></label>
          <button className="btn-primary w-full" disabled={loading}>{loading ? "กำลังเข้าสู่ระบบ…" : "เข้าสู่ระบบ"}</button>
        </form>
      </div>
    </section>);

  if (forbidden) return wrap(
    <section className="mx-auto max-w-2xl px-5 py-16">
      <div className="panel p-8 text-center">
        <XCircle className="mx-auto text-coral" size={36} />
        <h1 className="mt-4 text-2xl font-black">ไม่มีสิทธิ์เข้าถึง</h1>
        <p className="mt-2 text-sm text-ink/60">{error}</p>
        <button className="btn-secondary mt-6" onClick={() => {
          window.localStorage.removeItem(TOKEN_KEY); setToken(null); setForbidden(false); setError("");
        }}>เข้าสู่ระบบด้วยบัญชีอื่น</button>
      </div>
    </section>);

  const items = queue?.items ?? [];
  const pickable = courses.filter((c) => c.code);

  return wrap(
    <section className="mx-auto max-w-5xl px-5 py-8 md:py-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm font-bold text-sage">เครื่องมือผู้ดูแล</p>
          <h1 className="mt-1 text-3xl font-black md:text-4xl">คิวตรวจเอกสารหลักสูตร</h1>
          <p className="mt-2 text-sm text-ink/55">
            ไฟล์ที่ระบบพบบนเว็บคณะและรอให้คนตัดสินใจ — การอนุมัติยังไม่นำเข้าคลังความรู้
          </p>
        </div>
        <button className="btn-secondary" onClick={() => token && load(token)} disabled={loading}>
          <RefreshCw size={16} className={loading ? "animate-spin" : ""} />โหลดคิวใหม่
        </button>
      </div>

      {queue && <dl className="mt-6 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Count label="รอตรวจทั้งหมด" value={queue.counts.total} />
        <Count label="ต้องให้คนดู" value={queue.counts.needs_review} />
        <Count label="จับคู่ไม่ชัด" value={queue.counts.ambiguous} />
        <Count label="มีไฟล์ให้เปิดดู" value={queue.counts.with_staged_file} />
      </dl>}

      {notice && <div role="status" className={`mt-6 flex items-start gap-3 rounded-2xl p-4 text-sm ${
        notice.kind === "ok" ? "bg-lime/40 text-ink"
          : notice.kind === "warn" ? "bg-amber-50 text-amber-900" : "bg-red-50 text-red-700"}`}>
        {notice.kind === "ok" ? <CheckCircle2 size={18} className="mt-0.5 shrink-0" />
          : <AlertTriangle size={18} className="mt-0.5 shrink-0" />}
        <span>{notice.text}</span>
      </div>}

      {error && !forbidden && <div role="alert" className="mt-6 rounded-2xl bg-red-50 p-4 text-sm text-red-700">{error}</div>}

      {loading && !queue && <Status text="กำลังโหลดคิว…" />}
      {queue && items.length === 0 && !loading && <div className="panel mt-6 grid min-h-48 place-items-center p-8 text-center text-sm text-ink/55">
        ไม่มีรายการรอตรวจ — ระบบตรวจเว็บคณะแล้วไม่พบเอกสารใหม่หรือเอกสารที่เปลี่ยนแปลง
      </div>}

      <div className="mt-6 space-y-5">
        {items.map((item) => {
          const needCourse = mustChooseCourse(item);
          const picked = choice[item.id] || (needCourse ? "" : item.course_code ?? "");
          const blocked = needCourse && !choice[item.id];
          const working = busy === item.id;
          return (
            <article key={item.id} className="panel p-5 md:p-6">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <Tag tone={item.status === "error" ? "bad" : "info"}>{item.status}</Tag>
                    {item.needs_review && <Tag tone="warn">ต้องให้คนดู</Tag>}
                    {item.match_confidence && <Tag tone={needCourse ? "warn" : "ok"}>
                      {CONFIDENCE_TEXT[item.match_confidence] ?? item.match_confidence}
                    </Tag>}
                  </div>
                  <h2 className="mt-2 break-words text-lg font-black">{item.page_title ?? "ไม่มีหัวเรื่องของหน้า"}</h2>
                  <p className="mt-1 break-all text-xs text-ink/50">{item.source_url}</p>
                  {item.page_url && <a className="mt-1 inline-block break-all text-xs font-bold text-sage underline"
                                       href={item.page_url} target="_blank" rel="noreferrer noopener">หน้าที่พบลิงก์นี้</a>}
                </div>
                <button className="btn-secondary shrink-0" onClick={() => openPdf(item)} disabled={!item.has_staged_file}>
                  <FileText size={16} />{item.has_staged_file ? "เปิดไฟล์" : "ไม่มีไฟล์"}
                </button>
              </div>

              <dl className="mt-4 grid gap-x-6 gap-y-2 text-sm md:grid-cols-2">
                <Row label="หลักสูตรที่ระบบจับคู่">{item.course_label ?? "ระบุไม่ได้"}{item.course_code ? ` (${item.course_code})` : ""}</Row>
                <Row label="ขนาดไฟล์">{formatBytes(item.content_length)}</Row>
                <Row label="ลายนิ้วมือไฟล์">{item.file_sha256 ? <code className="text-xs">{item.file_sha256.slice(0, 16)}…</code> : "ยังไม่มี"}</Row>
                <Row label="ตรวจล่าสุด">{item.last_checked_at ? new Date(item.last_checked_at).toLocaleString("th-TH") : "ยังไม่เคย"}</Row>
                {item.previous_sha256 && <Row label="ลายนิ้วมือเดิม"><code className="text-xs">{item.previous_sha256.slice(0, 16)}…</code></Row>}
                {item.review_reason && <div className="md:col-span-2"><Row label="เหตุผลที่ต้องตรวจ">{item.review_reason}</Row></div>}
              </dl>

              {needCourse && <div className="mt-4 rounded-2xl bg-cream p-4">
                <label><span className="label">ต้องเลือกหลักสูตรก่อนอนุมัติ</span>
                  <select className="field" value={picked}
                          aria-label={`เลือกหลักสูตรสำหรับ ${item.page_title ?? item.source_url}`}
                          onChange={(e) => setChoice((c) => ({ ...c, [item.id]: e.target.value }))}>
                    <option value="">— เลือกหลักสูตรที่มีอยู่ในระบบ —</option>
                    {pickable.map((c) => <option key={c.id} value={c.code as string}>{c.title} ({c.code})</option>)}
                  </select>
                </label>
                {item.match_candidates.length > 0 && <p className="mt-2 text-xs text-ink/55">
                  ระบบเดาได้หลายชื่อ: {item.match_candidates.join(" · ")} — เลือกให้ตรงกับที่เปิดดูในไฟล์
                </p>}
                {pickable.length === 0 && <p className="mt-2 text-xs text-red-700">
                  ยังโหลดรายชื่อหลักสูตรไม่ได้ จึงอนุมัติไม่ได้ กรุณาโหลดหน้าใหม่
                </p>}
              </div>}

              {confirm?.id === item.id ? (
                <div className="mt-4 rounded-2xl border border-ink/15 p-4">
                  {confirm.action === "approve" && <>
                    <p className="text-sm font-bold">ยืนยันการอนุมัติ</p>
                    <p className="mt-1 text-sm text-ink/65">
                      จะผูกไฟล์นี้กับหลักสูตร <b>{pickable.find((c) => c.code === picked)?.title ?? picked}</b>
                      {" "}และบันทึกว่าคุณอนุญาตแล้ว — ยังไม่มีอะไรเข้าคลังความรู้ในขั้นนี้
                    </p>
                  </>}
                  {confirm.action === "ignore" && <>
                    <p className="text-sm font-bold">ยืนยันว่าไม่เกี่ยวข้อง</p>
                    <label className="mt-2 block"><span className="label">เหตุผล</span>
                      <input className="field" aria-label="เหตุผลที่ไม่เกี่ยวข้อง"
                             value={reason[item.id] ?? ""} placeholder="เช่น เป็นใบปลิว ไม่ใช่ มคอ.2"
                             onChange={(e) => setReason((r) => ({ ...r, [item.id]: e.target.value }))} /></label>
                  </>}
                  {confirm.action === "undo" && <>
                    <p className="text-sm font-bold">ยืนยันการถอน</p>
                    <p className="mt-1 text-sm text-ink/65">รายการจะกลับเข้าคิวให้ตรวจใหม่</p>
                  </>}
                  <div className="mt-4 flex flex-wrap gap-3">
                    <button className="btn-primary" disabled={working} onClick={() => decide(item, confirm.action)}>
                      {working ? "กำลังบันทึก…" : "ยืนยัน"}
                    </button>
                    <button className="btn-secondary" onClick={() => setConfirm(null)}>ยกเลิก</button>
                  </div>
                </div>
              ) : (
                <div className="mt-4 flex flex-wrap gap-3">
                  <button className="btn-primary" disabled={blocked || working || !item.has_staged_file || !item.file_sha256}
                          onClick={() => setConfirm({ id: item.id, action: "approve" })}>
                    <CheckCircle2 size={16} />อนุมัติ
                  </button>
                  <button className="btn-secondary" disabled={working || !item.file_sha256}
                          onClick={() => setConfirm({ id: item.id, action: "ignore" })}>
                    <XCircle size={16} />ไม่เกี่ยวข้อง
                  </button>
                  <button className="btn-secondary" disabled={working || !item.file_sha256}
                          onClick={() => setConfirm({ id: item.id, action: "undo" })}>ถอนการตัดสินใจล่าสุด</button>
                </div>
              )}
              {blocked && <p className="mt-2 text-xs text-ink/55">ต้องเลือกหลักสูตรก่อนจึงจะกดอนุมัติได้</p>}
              {!item.has_staged_file && <p className="mt-2 text-xs text-ink/55">
                ไม่มีไฟล์รออนุมัติ จึงอนุมัติไม่ได้ — ทำได้เพียงบันทึกว่าไม่เกี่ยวข้อง
              </p>}
            </article>
          );
        })}
      </div>
    </section>);
}

function Status({ text }: { text: string }) {
  return <div role="status" className="mx-auto grid min-h-64 max-w-5xl place-items-center px-5 text-sm text-ink/50">{text}</div>;
}

function Count({ label, value }: { label: string; value: number }) {
  return <div className="panel px-4 py-3">
    <dt className="text-xs font-bold text-ink/50">{label}</dt>
    <dd className="mt-0.5 text-2xl font-black">{value}</dd>
  </div>;
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className="flex flex-wrap gap-x-2">
    <dt className="text-ink/50">{label}:</dt><dd className="font-bold">{children}</dd>
  </div>;
}

function Tag({ tone, children }: { tone: "ok" | "warn" | "bad" | "info"; children: React.ReactNode }) {
  const cls = { ok: "bg-lime/50", warn: "bg-amber-100 text-amber-900", bad: "bg-red-100 text-red-700", info: "bg-cream" }[tone];
  return <span className={`rounded-full px-3 py-1 text-xs font-bold ${cls}`}>{children}</span>;
}
