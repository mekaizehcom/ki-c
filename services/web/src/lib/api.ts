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
    request<{
      status: string;
      challenge_id: string;
      enroll_uri: string | null;
      enroll_secret: string | null;
    }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  totpVerify: (challenge_id: string, code: string) =>
    request<{ status: string; user: any }>("/auth/totp/verify", {
      method: "POST",
      body: JSON.stringify({ challenge_id, code }),
    }),
  logout: () => request("/auth/logout", { method: "POST" }),
  me: () => request<any>("/me"),
  agents: () => request<any[]>("/agents"),
  conversations: () => request<any[]>("/conversations"),
  conversation: (id: string) => request<any>(`/conversations/${id}`),
  chat: (body: {
    message: string;
    conversation_id?: string | null;
    agent?: string;
  }) => request<any>("/chat", { method: "POST", body: JSON.stringify(body) }),
  adminSystem: () => request<any>("/admin/system"),
  adminUsers: () => request<any[]>("/admin/users"),
  createUser: (b: any) =>
    request<any>("/admin/users", { method: "POST", body: JSON.stringify(b) }),
  updateUser: (username: string, b: any) =>
    request<any>(`/admin/users/${username}`, { method: "PUT", body: JSON.stringify(b) }),
  adminProviders: () => request<any[]>("/admin/models"),
  setProvider: (p: string, b: any) =>
    request<any>(`/admin/models/${p}`, { method: "PUT", body: JSON.stringify(b) }),
  adminAgents: () => request<any[]>("/admin/agents"),
  setAgent: (name: string, b: any) =>
    request<any>(`/admin/agents/${name}`, { method: "PUT", body: JSON.stringify(b) }),
  adminAudit: () => request<any[]>("/admin/audit?limit=50"),
  reindexFailed: () =>
    request<any>("/admin/vector/reindex-failed", { method: "POST" }),
  listTools: () => request<any[]>("/tools"),
  executeTool: (body: { agent: string; command: string; target?: string | null }) =>
    request<any>("/tools/execute", { method: "POST", body: JSON.stringify(body) }),
  listApprovals: () => request<any[]>("/approvals"),
  approve: (id: string, totp_code?: string) =>
    request<any>(`/approvals/${id}/approve`, {
      method: "POST",
      body: JSON.stringify({ totp_code: totp_code || null }),
    }),
  deny: (id: string) =>
    request<any>(`/approvals/${id}/deny`, { method: "POST" }),
  sandboxHosts: () => request<any[]>("/admin/sandbox/hosts"),
  sandboxUpsert: (label: string, b: { host: string; user: string; port: number; private_key: string; description?: string }) =>
    request<any>(`/admin/sandbox/hosts/${encodeURIComponent(label)}`, {
      method: "PUT", body: JSON.stringify(b),
    }),
  sandboxTest: (label: string) =>
    request<any>(`/admin/sandbox/hosts/${encodeURIComponent(label)}/test`, { method: "POST" }),
  sandboxForget: (label: string) =>
    request<any>(`/admin/sandbox/hosts/${encodeURIComponent(label)}`, { method: "DELETE" }),
  swisschatStatus: () => request<any>("/admin/swisschat"),
  swisschatPair: (pairing_code: string, bot_username = "tessa") =>
    request<any>("/admin/swisschat/pair", {
      method: "POST",
      body: JSON.stringify({ pairing_code, bot_username }),
    }),
  swisschatForget: () =>
    request<any>("/admin/swisschat", { method: "DELETE" }),
  swisschatMe: () => request<any[]>("/swisschat/me"),
  swisschatLink: (code: string, totp_code: string) =>
    request<any>("/swisschat/link", {
      method: "POST",
      body: JSON.stringify({ code, totp_code }),
    }),
  listDocuments: () => request<any[]>("/documents"),
  uploadDocument: async (file: File, visibility = "workspace") => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("visibility", visibility);
    const res = await fetch("/api/documents/upload", {
      method: "POST",
      body: fd,
      credentials: "include",
    });
    const body = await res.json().catch(() => null);
    if (!res.ok) throw new Error((body && body.detail) || `Upload failed (${res.status})`);
    return body;
  },
};

export function chatSocket(): WebSocket {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  return new WebSocket(`${proto}://${location.host}/ws/chat`);
}
