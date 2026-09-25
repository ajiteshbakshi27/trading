/**
 * Demo session layer — fake JWT in localStorage.
 * NOT real auth: the signature is decorative and the token is readable.
 * Swap `issueSession` for a server call when a real IdP exists.
 */
"use client";

const KEY = "qp.session";
const WEEK = 7 * 24 * 60 * 60 * 1000;

export type Session = { email: string; name: string; iat: number; exp: number };

function b64url(input: string): string {
  const bytes = new TextEncoder().encode(input);
  let bin = "";
  bytes.forEach((b) => (bin += String.fromCharCode(b)));
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function randomSegment(): string {
  const a = new Uint8Array(24);
  crypto.getRandomValues(a);
  let bin = "";
  a.forEach((b) => (bin += String.fromCharCode(b)));
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export const AUTH_EVENT = "qp:auth";

function announce() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(AUTH_EVENT));
  }
}

export function issueSession(email: string, name: string): Session {
  const now = Date.now();
  const header = b64url(JSON.stringify({ alg: "none", typ: "JWT" }));
  const payload = b64url(
    JSON.stringify({ email, name, iat: Math.floor(now / 1000), exp: Math.floor((now + WEEK) / 1000) })
  );
  const token = `${header}.${payload}.${randomSegment()}`;
  const s: Session = { email, name, iat: now, exp: now + WEEK };
  try {
    localStorage.setItem(KEY, JSON.stringify({ ...s, token }));
  } catch {
    /* private mode */
  }
  announce();
  return s;
}

export function readSession(): Session | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return null;
    const s = JSON.parse(raw) as Session;
    if (!s?.exp || s.exp < Date.now()) {
      localStorage.removeItem(KEY);
      return null;
    }
    return s;
  } catch {
    return null;
  }
}

export function clearSession(): void {
  try {
    localStorage.removeItem(KEY);
  } catch {
    /* noop */
  }
  announce();
}
