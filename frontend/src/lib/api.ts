export const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function wsUrl(): string {
  return API.replace(/^http/, "ws") + "/ws/stream";
}

/** fetch + JSON with timeout; throws Error with the backend's detail message. */
export async function api<T = any>(path: string, init?: RequestInit): Promise<T> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 15000);
  try {
    const r = await fetch(`${API}${path}`, { signal: ctrl.signal, ...init });
    let j: any = null;
    try { j = await r.json(); } catch { /* non-JSON */ }
    if (!r.ok) {
      const detail = j?.detail;
      throw new Error(typeof detail === "string" ? detail : `Request failed (${r.status})`);
    }
    return j as T;
  } catch (e: any) {
    if (e?.name === "AbortError") throw new Error("Request timed out");
    throw e instanceof Error ? e : new Error(String(e));
  } finally {
    clearTimeout(timer);
  }
}
