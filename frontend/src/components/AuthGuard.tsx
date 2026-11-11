"use client";
import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { AUTH_MODE } from "@/lib/auth";
import { useSession } from "@/lib/useSession";

/**
 * With Supabase configured every app route needs a signed-in user (the
 * backend enforces it too). In local dev mode the app works without signing
 * in — requests are attributed to a local dev user.
 */
export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { session, ready } = useSession();
  const required = AUTH_MODE === "supabase";

  useEffect(() => {
    if (required && ready && !session) router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [required, ready, session, pathname, router]);

  if (required && (!ready || !session)) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center text-sm text-slate-400" aria-busy>
        {ready ? "Redirecting to sign in…" : "Loading…"}
      </div>
    );
  }
  return <>{children}</>;
}
