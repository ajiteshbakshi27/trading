/**
 * Parakh auth.
 *
 * Production: Supabase Auth (email + password, email confirmation, password
 * reset). The access token is sent to the backend as a Bearer token and
 * verified there.
 *
 * Local dev (no NEXT_PUBLIC_SUPABASE_* vars): a local profile is kept in
 * localStorage and requests carry an X-Parakh-Dev-User header. The backend
 * only honours that header when it is NOT in production.
 */
"use client";
import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const SB_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || "";
const SB_ANON = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "";
export const AUTH_MODE: "supabase" | "dev" = SB_URL && SB_ANON ? "supabase" : "dev";
export const AUTH_EVENT = "parakh:auth";

const DEV_KEY = "parakh.dev-session";

export type Session = { email: string; name: string; userId: string };

let client: SupabaseClient | null = null;
let cached: Session | null = null;
let readyPromise: Promise<void> | null = null;

function announce() {
  if (typeof window !== "undefined") window.dispatchEvent(new Event(AUTH_EVENT));
}

export function supabase(): SupabaseClient | null {
  if (AUTH_MODE !== "supabase" || typeof window === "undefined") return null;
  if (!client) {
    client = createClient(SB_URL, SB_ANON, { auth: { persistSession: true, autoRefreshToken: true } });
    client.auth.onAuthStateChange((_e, s) => {
      cached = s?.user
        ? { email: s.user.email || "", userId: s.user.id,
            name: (s.user.user_metadata?.name as string) || (s.user.email || "").split("@")[0] }
        : null;
      announce();
    });
  }
  return client;
}

/** Resolves once the persisted Supabase session (if any) has been loaded. */
export function authReady(): Promise<void> {
  if (AUTH_MODE === "dev" || typeof window === "undefined") return Promise.resolve();
  if (!readyPromise) {
    readyPromise = supabase()!.auth.getSession().then(({ data }) => {
      const u = data.session?.user;
      cached = u ? { email: u.email || "", userId: u.id,
                     name: (u.user_metadata?.name as string) || (u.email || "").split("@")[0] } : null;
      announce();
    });
  }
  return readyPromise;
}

function devId(email: string): string {
  return (email.split("@")[0] || "dev-user").toLowerCase().replace(/[^a-z0-9_.-]/g, "").slice(0, 40) || "dev-user";
}

export function readSession(): Session | null {
  if (typeof window === "undefined") return null;
  if (AUTH_MODE === "supabase") return cached;
  try {
    const raw = localStorage.getItem(DEV_KEY);
    return raw ? (JSON.parse(raw) as Session) : null;
  } catch {
    return null;
  }
}

export async function signIn(email: string, password: string): Promise<void> {
  if (AUTH_MODE === "supabase") {
    const { error } = await supabase()!.auth.signInWithPassword({ email, password });
    if (error) throw new Error(error.message);
    return;
  }
  const s: Session = { email, name: email.split("@")[0], userId: devId(email) };
  try { localStorage.setItem(DEV_KEY, JSON.stringify(s)); } catch { /* private mode */ }
  announce();
}

/** Returns true when the user must confirm their email before signing in. */
export async function signUp(email: string, password: string, name: string): Promise<boolean> {
  if (AUTH_MODE === "supabase") {
    const { data, error } = await supabase()!.auth.signUp({
      email, password,
      options: { data: { name }, emailRedirectTo: `${window.location.origin}/login` },
    });
    if (error) throw new Error(error.message);
    return !data.session;
  }
  await signIn(email, password);
  return false;
}

export async function resetPassword(email: string): Promise<void> {
  if (AUTH_MODE !== "supabase") return;
  const { error } = await supabase()!.auth.resetPasswordForEmail(email, {
    redirectTo: `${window.location.origin}/reset-password`,
  });
  if (error) throw new Error(error.message);
}

export async function updatePassword(password: string): Promise<void> {
  if (AUTH_MODE !== "supabase") throw new Error("Password reset needs Supabase configured.");
  const { error } = await supabase()!.auth.updateUser({ password });
  if (error) throw new Error(error.message);
}

export async function clearSession(): Promise<void> {
  if (AUTH_MODE === "supabase") {
    await supabase()?.auth.signOut();
  } else {
    try { localStorage.removeItem(DEV_KEY); } catch { /* noop */ }
  }
  cached = null;
  announce();
}

/** Headers that identify the caller to the Parakh backend. */
export async function authHeaders(): Promise<Record<string, string>> {
  if (typeof window === "undefined") return {};
  if (AUTH_MODE === "supabase") {
    await authReady();
    const { data } = await supabase()!.auth.getSession();
    const t = data.session?.access_token;
    return t ? { Authorization: `Bearer ${t}` } : {};
  }
  const s = readSession();
  return { "X-Parakh-Dev-User": s?.userId || "dev-user" };
}
