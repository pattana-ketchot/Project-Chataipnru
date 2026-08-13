import type { Course, Profile, RecommendResponse, Requirement, User } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
export class ApiError extends Error { constructor(public status: number, message: string) { super(message); this.name = "ApiError"; } }

export async function apiFetch<T>(path: string, init: RequestInit = {}, token?: string | null): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body) headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${API_URL}${path}`, { ...init, headers });
  if (!response.ok) {
    let message = "เกิดข้อผิดพลาด กรุณาลองใหม่";
    try { const body = await response.json(); message = body.detail ?? message; } catch { /* non-JSON error */ }
    throw new ApiError(response.status, message);
  }
  return response.json() as Promise<T>;
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
  recommend: (token: string, extra_query: string) => apiFetch<RecommendResponse>("/recommend", { method: "POST", body: JSON.stringify({ top_k_chunks: 12, top_n_courses: 5, extra_query: extra_query || null }) }, token)
};
