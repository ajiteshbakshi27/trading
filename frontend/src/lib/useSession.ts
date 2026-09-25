"use client";
import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { AUTH_EVENT, readSession } from "@/lib/auth";

/**
 * Session state for the demo auth layer.
 * Re-reads on route change and on the qp:auth event so sign-in/out
 * updates every header without a full reload.
 */
export function useSession() {
  const [session, setSession] = useState<{ email: string; name: string } | null>(null);
  const [ready, setReady] = useState(false);
  const pathname = usePathname();

  useEffect(() => {
    const sync = () => {
      const s = readSession();
      setSession(s ? { email: s.email, name: s.name } : null);
      setReady(true);
    };
    sync();
    window.addEventListener(AUTH_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(AUTH_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, [pathname]);

  return { session, ready };
}
