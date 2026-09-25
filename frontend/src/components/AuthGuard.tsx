"use client";
import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { readSession } from "@/lib/auth";

/**
 * Demo guard. Off by default so the terminal stays usable with zero keys;
 * enable with NEXT_PUBLIC_REQUIRE_AUTH=1 to require a session.
 *
 * Renders children during SSR and on first paint (no shell flash, nav is
 * always in the server HTML) and only blocks client-side once it knows
 * there is no session and the guard is actually required.
 */
export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [allowed, setAllowed] = useState(true);
  const required = process.env.NEXT_PUBLIC_REQUIRE_AUTH === "1";

  useEffect(() => {
    if (readSession()) {
      setAllowed(true);
      return;
    }
    if (!required) {
      setAllowed(true);
      return;
    }
    setAllowed(false);
    router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [pathname, router]);

  if (!allowed) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center text-sm text-slate-400" aria-busy>
        Redirecting to sign in…
      </div>
    );
  }
  return <>{children}</>;
}
