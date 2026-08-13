import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "@/app/page";
const user = { id: "u1", email: "learner@example.com", full_name: "มิน", created_at: "2026-01-01T00:00:00Z" };
function json(body: unknown, status = 200) { return Promise.resolve(new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } })); }
describe("authentication journey", () => {
  beforeEach(() => vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const url = String(input);
    if (url.endsWith("/auth/login")) return json({ access_token: "access", refresh_token: "refresh" });
    if (url.endsWith("/users/me")) return json(user);
    if (url.endsWith("/users/me/profile")) return json({ education_level: null, field_of_study: null, current_role: null, career_goal: null, skills: [], interests: [], language_preference: "th", updated_at: "2026-01-01T00:00:00Z" });
    return json({ detail: "not found" }, 404);
  }));
  it("logs in and continues to the questionnaire", async () => {
    render(<App />);
    fireEvent.click(screen.getAllByRole("button", { name: "เข้าสู่ระบบ" })[0]);
    fireEvent.change(screen.getByLabelText("อีเมล"), { target: { value: "learner@example.com" } });
    fireEvent.change(screen.getByLabelText(/^รหัสผ่าน/), { target: { value: "password123" } });
    fireEvent.click(screen.getAllByRole("button", { name: "เข้าสู่ระบบ" })[1]);
    await waitFor(() => expect(screen.getByRole("heading", { name: "มารู้จักคุณให้มากขึ้น" })).toBeInTheDocument());
    expect(window.localStorage.getItem("course_advisor_token")).toBe("access");
  });
});
