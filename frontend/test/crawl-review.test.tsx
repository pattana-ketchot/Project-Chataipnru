/**
 * ทดสอบหน้าคิวตรวจเอกสารหลักสูตร (Phase 3B)
 *
 * จำลองเฉพาะ fetch ระดับเครือข่าย ส่วนหน้าเว็บ สถานะ และการเรียก API เป็นของจริง
 * ทั้งหมด จึงจับได้ทั้งเรื่องที่แสดงผลและเรื่องที่ส่งออกไปให้ backend
 *
 * เก็บทุกคำขอไว้ใน calls เพื่อตรวจสองอย่างที่ดูจากหน้าจอไม่ได้
 *   1. ไม่มี staging_path หรือ decided_by หลุดไปใน body ที่ส่งออก
 *   2. ไม่มีคำขอสร้างหลักสูตรใหม่เลยแม้แต่ครั้งเดียว
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Page from "@/app/crawl-review/page";
import type { QueueItem } from "@/lib/crawl-review";

const TOKEN_KEY = "course_advisor_token";

function json(body: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(body), {
    status, headers: { "Content-Type": "application/json" },
  }));
}

function course(code: string | null, title: string) {
  return { id: `c-${code ?? "none"}`, code, title, provider: null, summary: null, mode: null,
           duration_weeks: null, price: null, currency: "THB", tags: [] };
}

const COURSES = [
  course("cs66", "วิทยาการคอมพิวเตอร์ (พ.ศ. 2566)"),
  course("ma69", "คณิตศาสตร์ (พ.ศ. 2569)"),
  course(null, "หลักสูตรที่ยังไม่มีรหัส"),
];

function item(over: Partial<QueueItem> & { id: string }): QueueItem {
  return {
    source_url: `https://sci.pnru.ac.th/uploads/programs/${over.id}.pdf`,
    page_url: "https://sci.pnru.ac.th/program_detail.php?id=1",
    page_title: `หลักสูตร ${over.id}`,
    link_text: "ดาวน์โหลด",
    course_code: "cs66",
    course_label: "วิทยาการคอมพิวเตอร์ (พ.ศ. 2566)",
    match_confidence: "high",
    match_score: 0.98,
    match_candidates: [],
    needs_review: true,
    review_reason: "ไฟล์ใหม่ ยังไม่มีในคลัง",
    status: "downloaded",
    content_length: 4_718_592,
    file_sha256: "a".repeat(64),
    previous_sha256: null,
    has_staged_file: true,
    last_checked_at: "2026-09-28T01:59:01Z",
    first_seen_at: "2026-09-20T00:00:00Z",
    ...over,
  };
}

const GOOD = item({ id: "good" });
const AMBIG = item({
  id: "ambig", course_code: null, course_label: null, match_confidence: "ambiguous",
  match_candidates: ["วิทยาการคอมพิวเตอร์ (พ.ศ. 2561)", "วิทยาการคอมพิวเตอร์ (พ.ศ. 2566)"],
  file_sha256: "b".repeat(64), review_reason: "ชื่อหลักสูตรตรงกับ 2 ฉบับ",
  content_length: 2_097_152,
});
const NOFILE = item({
  id: "nofile", status: "unchanged", has_staged_file: false, content_length: 1_048_576,
  match_confidence: "ambiguous", course_code: null, file_sha256: "c".repeat(64),
  review_reason: "ชื่อหลักสูตรกำกวม แต่ไม่มีไฟล์ใหม่",
});

function queue(items: QueueItem[]) {
  return {
    counts: {
      total: items.length,
      needs_review: items.filter((i) => i.needs_review).length,
      ambiguous: items.filter((i) => i.match_confidence === "ambiguous" || i.match_confidence === "unknown").length,
      with_staged_file: items.filter((i) => i.has_staged_file).length,
    },
    items,
  };
}

function decision(over: Record<string, unknown> = {}) {
  return {
    id: "d1", crawl_source_id: "good", file_sha256: "a".repeat(64), decision: "approve",
    decided_by: "admin@test.local", decided_at: "2026-09-28T06:00:00Z", note: null,
    course_code: "cs66", course_title: "วิทยาการคอมพิวเตอร์ (พ.ศ. 2566)",
    superseded_at: null, ingest_finished_at: null, document_id: null, ...over,
  };
}

type Call = { url: string; method: string; body: Record<string, unknown> | null; auth: string | null };
let calls: Call[] = [];

/** ตัวจำลองเครือข่าย — routes คืนคำตอบตาม url ที่ขอ */
function net(routes: (url: string, call: Call) => Promise<Response> | undefined) {
  vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
    const url = String(input);
    const headers = new Headers(init?.headers);
    const call: Call = {
      url,
      method: init?.method ?? "GET",
      body: init?.body ? JSON.parse(String(init.body)) : null,
      auth: headers.get("Authorization"),
    };
    calls.push(call);
    return routes(url, call) ?? json({ detail: "not found" }, 404);
  });
}

/** เส้นทางมาตรฐาน: คิวหนึ่งชุด หลักสูตรหนึ่งชุด */
function standard(items: QueueItem[], extra?: (url: string, call: Call) => Promise<Response> | undefined) {
  net((url, call) => {
    const hit = extra?.(url, call);
    if (hit) return hit;
    if (url.includes("/crawl-review/pending")) return json(queue(items));
    if (url.endsWith("/courses")) return json(COURSES);
    return undefined;
  });
}

beforeEach(() => {
  calls = [];
  window.localStorage.setItem(TOKEN_KEY, "admin-token");
  // jsdom ไม่มีสองตัวนี้ — หน้าเว็บใช้เปิดไฟล์ PDF ที่ดึงมาพร้อม token
  Object.defineProperty(URL, "createObjectURL", { configurable: true, value: vi.fn(() => "blob:pdf") });
  Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: vi.fn() });
  vi.spyOn(window, "open").mockReturnValue({} as Window);
});

describe("สิทธิ์เข้าถึง", () => {
  it("ยังไม่เข้าสู่ระบบ: ไม่เรียกคิวเลย และขอให้เข้าสู่ระบบก่อน", async () => {
    window.localStorage.removeItem(TOKEN_KEY);
    standard([GOOD]);
    render(<Page />);
    await waitFor(() => expect(screen.getByRole("heading", { name: "คิวตรวจเอกสารหลักสูตร" })).toBeInTheDocument());
    expect(screen.getByLabelText("อีเมล")).toBeInTheDocument();
    expect(calls.some((c) => c.url.includes("/crawl-review"))).toBe(false);
  });

  it("ผู้ใช้ที่ไม่ใช่ผู้ดูแล: backend ตอบ 403 แล้วหน้าเว็บบอกว่าไม่มีสิทธิ์", async () => {
    standard([], (url) => url.includes("/crawl-review/pending")
      ? json({ detail: "admin only" }, 403) : undefined);
    render(<Page />);
    await waitFor(() => expect(screen.getByRole("heading", { name: "ไม่มีสิทธิ์เข้าถึง" })).toBeInTheDocument());
    expect(screen.getByText(/ต้องเป็นผู้ดูแลระบบ/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /อนุมัติ/ })).not.toBeInTheDocument();
  });

  it("token หมดอายุ: ลบ token แล้วกลับไปหน้าเข้าสู่ระบบ", async () => {
    standard([], (url) => url.includes("/crawl-review/pending")
      ? json({ detail: "token expired" }, 401) : undefined);
    render(<Page />);
    await waitFor(() => expect(screen.getByLabelText("รหัสผ่าน")).toBeInTheDocument());
    expect(window.localStorage.getItem(TOKEN_KEY)).toBeNull();
  });

  it("เข้าสู่ระบบสำเร็จแล้วเห็นคิว", async () => {
    window.localStorage.removeItem(TOKEN_KEY);
    standard([GOOD], (url) => url.endsWith("/auth/login")
      ? json({ access_token: "fresh", refresh_token: "r" }) : undefined);
    render(<Page />);
    await waitFor(() => expect(screen.getByLabelText("อีเมล")).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText("อีเมล"), { target: { value: "admin@test.local" } });
    fireEvent.change(screen.getByLabelText("รหัสผ่าน"), { target: { value: "password123" } });
    fireEvent.click(screen.getByRole("button", { name: "เข้าสู่ระบบ" }));
    await waitFor(() => expect(screen.getByText("หลักสูตร good")).toBeInTheDocument());
    expect(window.localStorage.getItem(TOKEN_KEY)).toBe("fresh");
    expect(calls.find((c) => c.url.includes("/crawl-review/pending"))?.auth).toBe("Bearer fresh");
  });

  it("ส่ง token ไปกับทุกคำขอของคิว", async () => {
    standard([GOOD]);
    render(<Page />);
    await waitFor(() => expect(screen.getByText("หลักสูตร good")).toBeInTheDocument());
    for (const c of calls.filter((x) => x.url.includes("/crawl-review")))
      expect(c.auth).toBe("Bearer admin-token");
  });
});

describe("คิวและสถานะหน้าจอ", () => {
  it("แสดงตัวนับ ข้อมูลของรายการ และเหตุผลที่ต้องตรวจ", async () => {
    standard([GOOD, AMBIG, NOFILE]);
    render(<Page />);
    await waitFor(() => expect(screen.getByText("หลักสูตร good")).toBeInTheDocument());
    expect(screen.getByText("รอตรวจทั้งหมด").nextSibling).toHaveTextContent("3");
    expect(screen.getByText("มีไฟล์ให้เปิดดู").nextSibling).toHaveTextContent("2");
    expect(screen.getByText("จับคู่ไม่ชัด").nextSibling).toHaveTextContent("2");
    expect(screen.getByText(GOOD.source_url)).toBeInTheDocument();
    expect(screen.getByText("ไฟล์ใหม่ ยังไม่มีในคลัง")).toBeInTheDocument();
    expect(screen.getByText("4.5 MB")).toBeInTheDocument();
    // แสดงลายนิ้วมือแบบย่อ ไม่แสดงทั้งค่า
    expect(screen.getAllByText(/^a{16}…$/).length).toBeGreaterThan(0);
  });

  it("คิวว่าง: บอกว่าไม่มีรายการรอตรวจ", async () => {
    standard([]);
    render(<Page />);
    await waitFor(() => expect(screen.getByText(/ไม่มีรายการรอตรวจ/)).toBeInTheDocument());
  });

  it("กำลังโหลด: แสดงสถานะให้เห็น", async () => {
    let release: (r: Response) => void = () => {};
    standard([], (url) => url.includes("/crawl-review/pending")
      ? new Promise<Response>((r) => { release = r; }) : undefined);
    render(<Page />);
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("กำลังโหลดคิว…"));
    release(new Response(JSON.stringify(queue([])), { status: 200, headers: { "Content-Type": "application/json" } }));
    await waitFor(() => expect(screen.getByText(/ไม่มีรายการรอตรวจ/)).toBeInTheDocument());
  });

  it("API พัง: แสดงข้อความผิดพลาด ไม่ใช่หน้าว่าง", async () => {
    standard([], (url) => url.includes("/crawl-review/pending")
      ? json({ detail: "อะไรก็ไม่รู้พัง" }, 500) : undefined);
    render(<Page />);
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("อะไรก็ไม่รู้พัง"));
  });

  it("โหลดคิวใหม่: ยิงคำขอไปใหม่", async () => {
    standard([GOOD]);
    render(<Page />);
    await waitFor(() => expect(screen.getByText("หลักสูตร good")).toBeInTheDocument());
    const before = calls.filter((c) => c.url.includes("/crawl-review/pending")).length;
    fireEvent.click(screen.getByRole("button", { name: /โหลดคิวใหม่/ }));
    await waitFor(() => expect(calls.filter((c) => c.url.includes("/crawl-review/pending")).length).toBe(before + 1));
  });
});

describe("เปิดไฟล์ PDF", () => {
  it("เปิดได้: ดึงไฟล์พร้อม token แล้วเปิดเป็น blob", async () => {
    standard([GOOD], (url) => url.includes("/pdf")
      ? Promise.resolve(new Response("%PDF-1.4 x", { status: 200, headers: { "Content-Type": "application/pdf" } }))
      : undefined);
    render(<Page />);
    await waitFor(() => expect(screen.getByText("หลักสูตร good")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: /เปิดไฟล์/ }));
    await waitFor(() => expect(window.open).toHaveBeenCalledWith("blob:pdf", "_blank"));
    const call = calls.find((c) => c.url.includes("/pdf"));
    expect(call?.auth).toBe("Bearer admin-token");
    expect(call?.url).toContain(`/crawl-review/${GOOD.id}/pdf`);
  });

  it("เปิดไม่ได้ (404): บอกเหตุผลและไม่เปิดแท็บใหม่", async () => {
    standard([GOOD], (url) => url.includes("/pdf")
      ? json({ detail: "ไม่พบเอกสารที่ขอ" }, 404) : undefined);
    render(<Page />);
    await waitFor(() => expect(screen.getByText("หลักสูตร good")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: /เปิดไฟล์/ }));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/เปิดไฟล์ไม่ได้/));
    expect(window.open).not.toHaveBeenCalled();
  });

  it("ไม่มีไฟล์ในคิว: ปุ่มถูกปิดและบอกว่าอนุมัติไม่ได้", async () => {
    standard([NOFILE]);
    render(<Page />);
    await waitFor(() => expect(screen.getByText("หลักสูตร nofile")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: /ไม่มีไฟล์/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: /อนุมัติ/ })).toBeDisabled();
    expect(screen.getByText(/ไม่มีไฟล์รออนุมัติ จึงอนุมัติไม่ได้/)).toBeInTheDocument();
  });
});

describe("เลือกหลักสูตรและอนุมัติ", () => {
  it("รายการกำกวม: กดอนุมัติไม่ได้จนกว่าจะเลือกหลักสูตร", async () => {
    standard([AMBIG]);
    render(<Page />);
    await waitFor(() => expect(screen.getByText("หลักสูตร ambig")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: /อนุมัติ/ })).toBeDisabled();
    expect(screen.getByText(/ต้องเลือกหลักสูตรก่อนจึงจะกดอนุมัติได้/)).toBeInTheDocument();
    // ตัวเลือกมาจากหลักสูตรที่มีอยู่จริง และตัวที่ไม่มีรหัสถูกคัดออก
    const select = screen.getByLabelText(/เลือกหลักสูตรสำหรับ/);
    expect(select).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /วิทยาการคอมพิวเตอร์ \(พ.ศ. 2566\) \(cs66\)/ })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: /ยังไม่มีรหัส/ })).not.toBeInTheDocument();
    // ชื่อที่ระบบเดาได้แสดงเป็นข้อมูลประกอบ ไม่ใช่ตัวเลือกที่กดอนุมัติได้เอง
    expect(screen.getByText(/ระบบเดาได้หลายชื่อ/)).toBeInTheDocument();

    fireEvent.change(select, { target: { value: "cs66" } });
    await waitFor(() => expect(screen.getByRole("button", { name: /อนุมัติ/ })).toBeEnabled());
  });

  it("อนุมัติสำเร็จ: ต้องยืนยันก่อน ส่ง sha กับรหัสหลักสูตร แล้วโหลดคิวใหม่", async () => {
    let round = 0;
    net((url, call) => {
      if (url.includes("/crawl-review/pending")) { round += 1; return json(queue(round === 1 ? [GOOD] : [])); }
      if (url.endsWith("/courses")) return json(COURSES);
      if (url.includes("/approve")) return json(decision(), 201);
      return undefined;
    });
    render(<Page />);
    await waitFor(() => expect(screen.getByText("หลักสูตร good")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /อนุมัติ/ }));
    expect(screen.getByText("ยืนยันการอนุมัติ")).toBeInTheDocument();
    // ยังไม่ส่งอะไรออกไปจนกว่าจะกดยืนยัน
    expect(calls.some((c) => c.url.includes("/approve"))).toBe(false);

    fireEvent.click(screen.getByRole("button", { name: "ยืนยัน" }));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/อนุมัติแล้ว/));
    const sent = calls.find((c) => c.url.includes("/approve"));
    expect(sent?.method).toBe("POST");
    expect(sent?.body).toEqual({ file_sha256: "a".repeat(64), course_code: "cs66" });
    expect(screen.getByRole("status")).toHaveTextContent(/ยังไม่นำเข้าคลังความรู้/);
    // โหลดคิวใหม่หลังตัดสินใจ แล้วรายการหายไป
    await waitFor(() => expect(screen.queryByText("หลักสูตร good")).not.toBeInTheDocument());
    expect(round).toBe(2);
  });

  it("ยกเลิกการยืนยัน: ไม่ส่งคำขอ", async () => {
    standard([GOOD]);
    render(<Page />);
    await waitFor(() => expect(screen.getByText("หลักสูตร good")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: /อนุมัติ/ }));
    fireEvent.click(screen.getByRole("button", { name: "ยกเลิก" }));
    expect(screen.queryByText("ยืนยันการอนุมัติ")).not.toBeInTheDocument();
    expect(calls.some((c) => c.url.includes("/approve"))).toBe(false);
  });

  it("ไฟล์เปลี่ยนไปแล้ว (409): เตือน ไม่ส่งซ้ำอัตโนมัติ และโหลดคิวใหม่", async () => {
    let approves = 0, pendings = 0;
    net((url) => {
      if (url.includes("/crawl-review/pending")) { pendings += 1; return json(queue([GOOD])); }
      if (url.endsWith("/courses")) return json(COURSES);
      if (url.includes("/approve")) { approves += 1; return json({ detail: "ไฟล์เปลี่ยนไปแล้วหลังจากที่คุณเปิดดู กรุณาโหลดคิวใหม่" }, 409); }
      return undefined;
    });
    render(<Page />);
    await waitFor(() => expect(screen.getByText("หลักสูตร good")).toBeInTheDocument());
    const before = pendings;
    fireEvent.click(screen.getByRole("button", { name: /อนุมัติ/ }));
    fireEvent.click(screen.getByRole("button", { name: "ยืนยัน" }));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/ไฟล์เปลี่ยนไปแล้ว/));
    expect(screen.getByRole("status")).toHaveTextContent(/เปิดไฟล์ตรวจอีกครั้งก่อนตัดสินใจ/);
    expect(approves).toBe(1);                 // ห้าม retry เอง
    expect(pendings).toBe(before + 1);        // แต่ต้องโหลดคิวใหม่
  });

  it("ตัดสินใจซ้ำ (409): แจ้งว่ามีการตัดสินใจอยู่แล้ว", async () => {
    standard([GOOD], (url) => url.includes("/approve")
      ? json({ detail: "รายการนี้มีการตัดสินใจที่ยังใช้อยู่แล้ว" }, 409) : undefined);
    render(<Page />);
    await waitFor(() => expect(screen.getByText("หลักสูตร good")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: /อนุมัติ/ }));
    fireEvent.click(screen.getByRole("button", { name: "ยืนยัน" }));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/มีการตัดสินใจที่ยังใช้อยู่แล้ว/));
  });

  it("หลักสูตรที่ไม่มีในระบบ (422): แสดงข้อความจาก backend ไม่สร้างหลักสูตรเอง", async () => {
    standard([GOOD], (url) => url.includes("/approve")
      ? json({ detail: "ไม่มีหลักสูตรรหัส 'zz99' ในระบบ ต้องเลือกจากหลักสูตรที่มีอยู่แล้วเท่านั้น" }, 422) : undefined);
    render(<Page />);
    await waitFor(() => expect(screen.getByText("หลักสูตร good")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: /อนุมัติ/ }));
    fireEvent.click(screen.getByRole("button", { name: "ยืนยัน" }));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/ต้องเลือกจากหลักสูตรที่มีอยู่แล้ว/));
  });
});

describe("ไม่เกี่ยวข้องและถอนการตัดสินใจ", () => {
  it("บันทึกว่าไม่เกี่ยวข้อง: ต้องยืนยันและส่งเหตุผล", async () => {
    standard([GOOD], (url) => url.includes("/ignore")
      ? json(decision({ decision: "ignore", course_code: null, course_title: null }), 201) : undefined);
    render(<Page />);
    await waitFor(() => expect(screen.getByText("หลักสูตร good")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: /ไม่เกี่ยวข้อง/ }));
    expect(screen.getByText("ยืนยันว่าไม่เกี่ยวข้อง")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("เหตุผลที่ไม่เกี่ยวข้อง"), { target: { value: "เป็นใบปลิว" } });
    fireEvent.click(screen.getByRole("button", { name: "ยืนยัน" }));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/บันทึกว่าไม่เกี่ยวข้องแล้ว/));
    expect(calls.find((c) => c.url.includes("/ignore"))?.body)
      .toEqual({ file_sha256: "a".repeat(64), reason: "เป็นใบปลิว" });
  });

  it("ถอนการตัดสินใจ: ส่ง sha ปัจจุบันและบอกว่ากลับเข้าคิว", async () => {
    standard([GOOD], (url) => url.includes("/undo")
      ? json(decision({ superseded_at: "2026-09-28T07:00:00Z" })) : undefined);
    render(<Page />);
    await waitFor(() => expect(screen.getByText("หลักสูตร good")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: /ถอนการตัดสินใจล่าสุด/ }));
    expect(screen.getByText("ยืนยันการถอน")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "ยืนยัน" }));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/ถอนการตัดสินใจแล้ว/));
    expect(calls.find((c) => c.url.includes("/undo"))?.body).toEqual({ file_sha256: "a".repeat(64) });
  });
});

describe("ความปลอดภัย", () => {
  it("ไม่มี staging_path หรือที่อยู่ไฟล์บนเซิร์ฟเวอร์ปรากฏในหน้าจอ", async () => {
    standard([GOOD, AMBIG, NOFILE]);
    const { container } = render(<Page />);
    await waitFor(() => expect(screen.getByText("หลักสูตร good")).toBeInTheDocument());
    const html = container.innerHTML;
    for (const leak of ["staging_path", "staging/", "/srv/", "/tmp/", "C:\\", ".part_"])
      expect(html).not.toContain(leak);
  });

  it("ไม่ส่ง staging_path, decided_by หรือ path ใด ๆ ออกไปกับคำขอ", async () => {
    standard([GOOD], (url) => url.includes("/approve") ? json(decision(), 201) : undefined);
    render(<Page />);
    await waitFor(() => expect(screen.getByText("หลักสูตร good")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: /อนุมัติ/ }));
    fireEvent.click(screen.getByRole("button", { name: "ยืนยัน" }));
    await waitFor(() => expect(calls.some((c) => c.url.includes("/approve"))).toBe(true));
    for (const c of calls) {
      const keys = Object.keys(c.body ?? {});
      expect(keys).not.toContain("staging_path");
      expect(keys).not.toContain("decided_by");
      expect(keys).not.toContain("path");
    }
  });

  it("ไม่มีคำขอสร้างหลักสูตรใหม่เลย", async () => {
    standard([AMBIG], (url) => url.includes("/approve") ? json(decision(), 201) : undefined);
    render(<Page />);
    await waitFor(() => expect(screen.getByText("หลักสูตร ambig")).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText(/เลือกหลักสูตรสำหรับ/), { target: { value: "ma69" } });
    fireEvent.click(screen.getByRole("button", { name: /อนุมัติ/ }));
    fireEvent.click(screen.getByRole("button", { name: "ยืนยัน" }));
    await waitFor(() => expect(calls.some((c) => c.url.includes("/approve"))).toBe(true));
    // เรียก /courses ได้เฉพาะแบบอ่าน ไม่มี POST/PUT/DELETE ไปที่นั้นเลย
    for (const c of calls.filter((x) => x.url.endsWith("/courses")))
      expect(c.method).toBe("GET");
    expect(calls.some((c) => c.method !== "GET" && c.url.includes("/courses"))).toBe(false);
    // รหัสที่ส่งไปเป็นรหัสที่คนเลือกจากรายการจริง
    expect(calls.find((c) => c.url.includes("/approve"))?.body).toMatchObject({ course_code: "ma69" });
  });

  it("ไม่ประกอบที่อยู่ไฟล์เอง — เรียก PDF ด้วย id เท่านั้น", async () => {
    standard([GOOD], (url) => url.includes("/pdf")
      ? Promise.resolve(new Response("%PDF-", { status: 200 })) : undefined);
    render(<Page />);
    await waitFor(() => expect(screen.getByText("หลักสูตร good")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: /เปิดไฟล์/ }));
    await waitFor(() => expect(calls.some((c) => c.url.includes("/pdf"))).toBe(true));
    expect(calls.find((c) => c.url.includes("/pdf"))?.url).toBe(`/crawl-review/${GOOD.id}/pdf`);
  });
});
