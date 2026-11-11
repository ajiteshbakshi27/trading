"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Wordmark } from "./Logo";
import { API } from "@/lib/api";

const COLUMNS = [
  {
    title: "Product",
    links: [
      { label: "Check a trade", href: "/check" },
      { label: "Journal", href: "/journal" },
      { label: "Calibration", href: "/calibration" },
      { label: "Hype radar", href: "/radar" },
      { label: "F&O analyser", href: "/options" },
      { label: "Leaderboard", href: "/leaderboard" },
    ],
  },
  {
    title: "Data",
    links: [
      { label: "NSE daily prices (Yahoo Finance)", href: "https://finance.yahoo.com", external: true },
      { label: "Zerodha Kite Connect", href: "https://kite.trade", external: true },
      { label: "r/IndianStreetBets", href: "https://reddit.com/r/IndianStreetBets", external: true },
      { label: "Claude by Anthropic", href: "https://www.anthropic.com/claude", external: true },
    ],
  },
  {
    title: "Resources",
    links: [
      { label: "API reference", href: `${API}/docs`, external: true },
      { label: "How it works", href: "/#how" },
      { label: "Risk disclosure", href: "/legal" },
    ],
  },
];

export default function SiteFooter() {
  const [status, setStatus] = useState<"checking" | "up" | "down">("checking");

  useEffect(() => {
    let dead = false;
    const ping = async () => {
      try {
        const ctrl = new AbortController();
        const t = setTimeout(() => ctrl.abort(), 5000);
        const r = await fetch(`${API}/health`, { signal: ctrl.signal });
        clearTimeout(t);
        if (!dead) setStatus(r.ok ? "up" : "down");
      } catch {
        if (!dead) setStatus("down");
      }
    };
    ping();
    const id = setInterval(ping, 15000);
    return () => { dead = true; clearInterval(id); };
  }, []);

  return (
    <footer className="border-t border-hairline">
      <div className="mx-auto max-w-6xl px-6 py-16">
        <div className="grid gap-12 md:grid-cols-[1.4fr_repeat(3,1fr)]">
          <div>
            <Wordmark className="text-[15px]" />
            <p className="mt-4 max-w-xs text-sm leading-relaxed text-fg-muted">
              A trading terminal for people who read the order book before the headline.
              Paper trading by default; not investment advice.
            </p>
            <div className="mt-6 flex items-center gap-2 text-xs text-fg-muted">
              <span
                aria-hidden
                className={`h-2 w-2 rounded-full ${
                  status === "up"
                    ? "bg-accent shadow-[0_0_12px_var(--color-accent)]"
                    : status === "down"
                      ? "bg-destructive"
                      : "bg-fg-muted"
                }`}
              />
              <span className="tnum">
                {status === "up" ? "API operational" : status === "down" ? "API unreachable" : "checking API"}
              </span>
            </div>
          </div>

          {COLUMNS.map((col) => (
            <nav key={col.title} aria-label={col.title}>
              <h2 className="section-label">{col.title}</h2>
              <ul className="mt-4 space-y-1">
                {col.links.map((l) => (
                  <li key={l.label}>
                    {"external" in l && l.external ? (
                      <a
                        href={l.href}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex min-h-11 items-center text-sm text-fg-muted transition-colors duration-fast hover:text-fg"
                      >
                        {l.label}
                      </a>
                    ) : (
                      <Link
                        href={l.href}
                        className="inline-flex min-h-11 items-center text-sm text-fg-muted transition-colors duration-fast hover:text-fg"
                      >
                        {l.label}
                      </Link>
                    )}
                  </li>
                ))}
              </ul>
            </nav>
          ))}
        </div>

        <div className="mt-14 flex flex-col gap-3 border-t border-hairline pt-6 text-xs text-fg-muted sm:flex-row sm:items-center sm:justify-between">
          <p>© 2026 Parakh. Analysis, not investment advice. Data is end-of-day unless marked otherwise.</p>
          <p className="tnum">Quotes: Alpaca IEX · Alpha Vantage · Sentiment: Reddit · X</p>
        </div>
      </div>
    </footer>
  );
}
