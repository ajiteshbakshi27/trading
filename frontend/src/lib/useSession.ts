"use client";
import { useEffect, useState } from "react";
import { AUTH_EVENT, authReady, readSession, type Session } from "@/lib/auth";

/** Current user + a ready flag; updates on sign-in/out in any tab. */
export function useSession() {
  const [session, setSession] = useState<Session | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let alive = true;
    const sync = () => alive && setSession(readSession());
    authReady().then(() => { if (alive) { sync(); setReady(true); } });
    window.addEventListener(AUTH_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      alive = false;
      window.removeEventListener(AUTH_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);

  return { session, ready };
}
