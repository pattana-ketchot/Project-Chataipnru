import type { ChatReply, Course, Profile, RecommendResponse, Requirement, User } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
export class ApiError extends Error { constructor(public status: number, message: string) { super(message); this.name = "ApiError"; } }

/** ใช้เมื่อคำขอขาดหรือ gateway ล้ม ซึ่งเกือบทุกครั้งคือโมเดลกำลังโหลดเข้า VRAM */
const SLOW_HINT = "ระบบ AI กำลังเตรียมโมเดล คำถามแรกหลังเปิดระบบหรือเว้นว่างนานอาจใช้เวลาถึง 2 นาที กรุณารอสักครู่แล้วถามใหม่อีกครั้งครับ";

export async function apiFetch<T>(path: string, init: RequestInit = {}, token?: string | null): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body) headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, { ...init, headers });
  } catch {
    // fetch โยน error เมื่อการเชื่อมต่อขาด ซึ่งเกิดได้เมื่อคำขอใช้เวลานานมาก
    // (เช่น Ollama กำลังโหลดโมเดลกลับเข้า VRAM ซึ่งวัดได้ถึง 118 วินาที)
    // แล้ว proxy ตัดการเชื่อมต่อทิ้ง — ต้องบอกผู้ใช้ให้ตรงว่าเกิดอะไรขึ้น
    throw new ApiError(0, SLOW_HINT);
  }
  if (!response.ok) {
    // proxy ที่ล้มจะคืนหน้า HTML ไม่ใช่ JSON จึงอ่าน detail ไม่ได้ ต้องมีข้อความสำรอง
    let message = response.status >= 502 ? SLOW_HINT : "เกิดข้อผิดพลาด กรุณาลองใหม่";
    try { const body = await response.json(); message = body.detail ?? message; } catch { /* non-JSON error */ }
    throw new ApiError(response.status, message);
  }
  return response.json() as Promise<T>;
}

/** ข้อมูลสรุปของเทิร์น ส่งมาก่อนตัวอักษรแรกของคำตอบ */
export type ChatMeta = Omit<ChatReply, "reply">;

/**
 * ถาม /chat/stream แล้วเรียก callback ทุกครั้งที่ได้ข้อความส่วนใหม่
 *
 * ใช้แทน api.chat บนหน้าเว็บเพื่อลดเวลารอที่ผู้ใช้รู้สึก — เซิร์ฟเวอร์ที่รันด้วย CPU
 * เขียนคำตอบเสร็จใน 30-40 วินาที แต่ตัวอักษรแรกออกมาตั้งแต่ราว 5 วินาที
 *
 * อ่านตามรูปแบบ Server-Sent Events: แต่ละเหตุการณ์คั่นด้วยบรรทัดว่าง จึงต้องพัก
 * ข้อมูลที่อ่านมาไม่ครบไว้ใน buffer เพราะขอบเขตของ chunk ที่เครือข่ายส่งมาไม่ได้
 * ตรงกับขอบเขตของเหตุการณ์
 */
export async function chatStream(
  token: string,
  message: string,
  session_id: string | null,
  handlers: { onMeta(meta: ChatMeta): void; onToken(text: string): void },
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ message, session_id }),
    });
  } catch {
    throw new ApiError(0, SLOW_HINT);
  }
  if (!response.ok || !response.body) {
    let detail = response.status >= 502 ? SLOW_HINT : "เกิดข้อผิดพลาด กรุณาลองใหม่";
    try { detail = (await response.json()).detail ?? detail; } catch { /* non-JSON error */ }
    throw new ApiError(response.status, detail);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let cut: number;
    while ((cut = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, cut);
      buffer = buffer.slice(cut + 2);
      const event = block.match(/^event: (.+)$/m)?.[1];
      const raw = block.match(/^data: (.*)$/m)?.[1];
      if (!event || raw === undefined) continue;
      const data = JSON.parse(raw);
      if (event === "meta") handlers.onMeta(data as ChatMeta);
      else if (event === "token") handlers.onToken(data.t as string);
      // ข้อผิดพลาดที่เกิดกลางสตรีมส่งเป็น HTTP status ไม่ได้ เพราะหัวข้อความออกไปแล้ว
      else if (event === "error") throw new ApiError(503, data.detail ?? SLOW_HINT);
    }
  }
}

export const api = {
  register: (data: { email: string; password: string; full_name?: string }) => apiFetch<User>("/auth/register", { method: "POST", body: JSON.stringify(data) }),
  login: (email: string, password: string) => apiFetch<{ access_token: string; refresh_token: string }>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  me: (token: string) => apiFetch<User>("/users/me", {}, token),
  profile: (token: string) => apiFetch<Profile>("/users/me/profile", {}, token),
  saveProfile: (token: string, data: Profile) => apiFetch<Profile>("/users/me/profile", { method: "PUT", body: JSON.stringify(data) }, token),
  requirements: (token: string) => apiFetch<Requirement[]>("/users/me/requirements", {}, token),
  addRequirement: (token: string, data: { req_type: string; req_value: string; priority: number }) => apiFetch<Requirement>("/users/me/requirements", { method: "POST", body: JSON.stringify(data) }, token),
  courses: () => apiFetch<Course[]>("/courses"),
  recommend: (token: string, extra_query: string) => apiFetch<RecommendResponse>("/recommend", { method: "POST", body: JSON.stringify({ top_k_chunks: 12, top_n_courses: 5, extra_query: extra_query || null }) }, token),
  // session_id = null คือเริ่มบทสนทนาใหม่ ส่งค่าที่ backend คืนมากลับไปเพื่อคุยต่อในบทสนทนาเดิม
  chat: (token: string, message: string, session_id: string | null) => apiFetch<ChatReply>("/chat", { method: "POST", body: JSON.stringify({ message, session_id }) }, token)
};
