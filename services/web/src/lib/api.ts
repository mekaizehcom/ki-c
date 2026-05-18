// Same-origin API client. Dev: Vite proxies /api -> tessa-api.
// Prod: nginx routes /api -> tessa-api.

export type ApiError = { detail: string };

async function request<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...opts,
    headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
    credentials: "include",
  });
  const text = await res.text();
  const body = text ? JSON.parse(text) : null;
  if (!res.ok) {
    throw new Error((body && body.detail) || `Request failed (${res.status})`);
  }
  return body as T;
}

export const api = {
  login: (username: string, password: string) =>
    request<{ status: string; challenge_id: string; enroll_uri: string | null }>(
      "/auth/login",
      { method: "POST", body: JSON.stringify({ username, password }) }
    ),
  totpVerify: (challenge_id: string, code: string) =>
    request<{ status: string; user: any }>("/auth/totp/verify", {
      method: "POST",
      body: JSON.stringify({ challenge_id, code }),
    }),
  logout: () => request("/auth/logout", { method: "POST" }),
  me: () => request<any>("/me"),
};
