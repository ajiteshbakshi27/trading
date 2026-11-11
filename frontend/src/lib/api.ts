import { authHeaders } from "@/lib/auth";

export const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function wsUrl(): string {
  return API.replace(/^http/, "ws") + "/ws/stream";
}

/** fetch + JSON with timeout and auth; throws Error with the backend's detail message. */
export async function api<T = any>(path: string, init?: RequestInit): Promise<T> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 45000);
  try {
    const auth = await authHeaders();
    const headers: Record<string, string> = { ...auth, ...((init?.headers as Record<string, string>) || {}) };
    if (init?.body && typeof init.body === "string" && !headers["Content-Type"]) {
      headers["Content-Type"] = "application/json";
    }
    const r = await fetch(`${API}${path}`, { ...init, signal: ctrl.signal, headers });
    let j: any = null;
    try { j = await r.json(); } catch { /* non-JSON */ }
    if (!r.ok) {
      const detail = j?.detail;
      const msg = typeof detail === "string" ? detail
        : Array.isArray(detail) ? detail.map((d: any) => d?.msg).filter(Boolean).join("; ")
        : `Request failed (${r.status})`;
      throw new Error(msg);
    }
    return j as T;
  } catch (e: any) {
    if (e?.name === "AbortError") throw new Error("Request timed out");
    if (e instanceof TypeError) throw new Error("Can't reach the Parakh server. Is the backend running?");
    throw e instanceof Error ? e : new Error(String(e));
  } finally {
    clearTimeout(timer);
  }
}

/** POST JSON helper. */
export function post<T = any>(path: string, body: unknown, method = "POST"): Promise<T> {
  return api<T>(path, { method, body: JSON.stringify(body) });
}
