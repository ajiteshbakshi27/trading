"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useGSAP } from "@gsap/react";
import { useRouter } from "next/navigation";
import { Wordmark } from "./Logo";
import { useSession } from "@/lib/useSession";
import { clearSession } from "@/lib/auth";

gsap.registerPlugin(ScrollTrigger, useGSAP);

const NAV = [
  { href: "/#desk", label: "Desk" },
  { href: "/#runtime", label: "Runtime" },
  { href: "/#risk", label: "Risk" },
];

export default function SiteHeader() {
  const [scrolled, setScrolled] = useState(false);
  const root = useRef<HTMLElement>(null);
  const router = useRouter();
  const { session } = useSession();

  const signOut = () => {
    clearSession();
    router.push("/");
    router.refresh();
  };

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useGSAP(
    () => {
      gsap.from(".site-header-in", { y: -12, opacity: 0, duration: 0.7, ease: "expo.out" });
    },
    { scope: root }
  );

  return (
    <header ref={root} className="fixed inset-x-0 top-0 z-50">
      {/* background layer: opacity only, never layout */}
      <div
        aria-hidden
        className={`pointer-events-none absolute inset-0 border-b border-transparent transition-opacity duration-base ease-out ${
          scrolled ? "bg-bg/85 opacity-100 backdrop-blur-xl" : "opacity-0"
        }`}
      />
      <div className="site-header-in relative mx-auto flex h-16 max-w-6xl items-center gap-6 px-6">
        <Link href="/" className="inline-flex min-h-11 items-center text-[15px]" aria-label="QuantPulse AI home">
          <Wordmark />
        </Link>
        <nav className="hidden items-center gap-6 text-sm text-fg-muted md:flex" aria-label="Primary">
          {NAV.map((n) => (
            <a key={n.href} href={n.href} className="inline-flex min-h-11 items-center transition-colors duration-fast hover:text-fg">
              {n.label}
            </a>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <a
            href={process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}
            target="_blank"
            rel="noreferrer"
            className="mk-btn mk-btn-ghost hidden sm:inline-flex"
          >
            Docs
          </a>
          {session ? (
            <>
              <Link
                href="/dashboard"
                className="hidden items-center gap-2 rounded-full border border-hairline px-3 py-1.5 text-xs text-fg-muted sm:inline-flex sm:min-h-11"
              >
                <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-accent" />
                {session.name}
              </Link>
              <button onClick={signOut} className="mk-btn mk-btn-ghost">
                Sign out
              </button>
            </>
          ) : (
            <>
              <Link href="/login" className="mk-btn mk-btn-ghost">
                Sign in
              </Link>
              <Link href="/signup" className="mk-btn mk-btn-primary">
                Get started
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
