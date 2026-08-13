import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "@/lib/api";
afterEach(() => vi.restoreAllMocks());
describe("API client", () => {
  it("sends credentials to the login endpoint", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ access_token: "access", refresh_token: "refresh" }), { status: 200, headers: { "Content-Type": "application/json" } }));
    await expect(api.login("learner@example.com", "password123")).resolves.toMatchObject({ access_token: "access" });
    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/auth/login", expect.objectContaining({ method: "POST" }));
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toEqual({ email: "learner@example.com", password: "password123" });
  });
  it("adds a bearer token and exposes API errors", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ detail: "token expired" }), { status: 401, headers: { "Content-Type": "application/json" } }));
    await expect(api.me("expired")).rejects.toEqual(expect.objectContaining<ApiError>({ status: 401, message: "token expired" }));
    const headers = fetchMock.mock.calls[0][1]?.headers as Headers;
    expect(headers.get("Authorization")).toBe("Bearer expired");
  });
});
