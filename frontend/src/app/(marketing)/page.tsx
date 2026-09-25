import Link from "next/link";
import { ArrowRight } from "lucide-react";
import Hero from "@/components/marketing/Hero";
import SiteHeader from "@/components/marketing/SiteHeader";
import SiteFooter from "@/components/marketing/SiteFooter";
import TickerMarquee from "@/components/marketing/TickerMarquee";
import StatBand from "@/components/marketing/StatBand";
import Reveal from "@/components/marketing/Reveal";

const LENSES = [
  {
    k: "01",
    title: "Quantum weights",
    body: "QAOA portfolio selection in PennyLane picks the basket from expected return against a real covariance matrix, and hands back whole-share orders instead of a theory.",
  },
  {
    k: "02",
    title: "HFT execution",
    body: "Order-flow imbalance on L2 depth, latency-arbitrage detection across simulated venues, and VWAP/TWAP slicing with slippage priced in before anything routes.",
  },
  {
    k: "03",
    title: "Crowd fades",
    body: "Reddit and X sentiment scored against order flow. When 90% of the crowd is bullish and the tape disagrees, that divergence is the trade.",
  },
];

const GUARDS = [
  ["Drawdown trip", "5% peak-to-trough halts signal generation and liquidates through Alpaca."],
  ["Position sizing", "Caps exposure per name and per day from config, not from gut."],
  ["Pre-trade costs", "Brokerage, spread slippage and a gains-tax estimate on every order."],
  ["Paper default", "Keys are optional. Without them nothing routes — the desk still runs."],
];

export default function LandingPage() {
  return (
    <>
      <SiteHeader />
      <main>
        <Hero />
        <TickerMarquee />

        {/* Desk — three lenses */}
        <section id="desk" className="mx-auto max-w-6xl scroll-mt-24 px-6 py-28">
          <Reveal>
            <p className="section-label">The desk</p>
            <h2 className="mt-4 max-w-[28rem] text-3xl font-semibold tracking-[-0.02em]">
              Three lenses on the same tape.
            </h2>
            <p className="mt-4 max-w-[42rem] text-fg-muted">
              Most tools pick one. The edge is in the disagreement between them — so all three run
              on one clock, and the signal card shows its reasoning.
            </p>
          </Reveal>

          <div className="mt-16 grid gap-px overflow-hidden rounded-2xl border border-hairline bg-[var(--color-hairline)] md:grid-cols-3">
            {LENSES.map((l, i) => (
              <Reveal key={l.k} delay={i * 0.06} className="bg-bg">
                <div className="h-full px-6 py-10">
                  <span className="tnum text-xs text-fg-muted">{l.k}</span>
                  <h3 className="mt-4 text-lg font-semibold">{l.title}</h3>
                  <p className="mt-3 text-sm leading-relaxed text-fg-muted">{l.body}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </section>

        {/* Runtime — proof, not testimonials */}
        <section id="runtime" className="scroll-mt-24 border-y border-hairline bg-surface/40">
          <div className="mx-auto max-w-6xl px-6 py-28">
            <Reveal>
              <p className="section-label">Runtime</p>
              <h2 className="mt-4 max-w-[28rem] text-3xl font-semibold tracking-[-0.02em]">
                What actually runs.
              </h2>
            </Reveal>
            <Reveal delay={0.08} className="mt-12">
              <StatBand />
            </Reveal>
            <Reveal delay={0.12} className="mt-10 max-w-[42rem] text-sm leading-relaxed text-fg-muted">
              Every number on this site comes from the same API the terminal uses:{" "}
              <code className="rounded bg-surface-2 px-1.5 py-0.5 text-fg">/api/snapshot</code> for
              signals, <code className="rounded bg-surface-2 px-1.5 py-0.5 text-fg">/api/history</code>{" "}
              for what fired before, and a websocket for the live tape. Mock feeds stand in only
              when a key is missing — the UI always tells you which one you are looking at.
            </Reveal>
          </div>
        </section>

        {/* Risk — the part that stops you */}
        <section id="risk" className="mx-auto max-w-6xl scroll-mt-24 px-6 py-28">
          <div className="grid gap-16 md:grid-cols-2">
            <Reveal>
              <p className="section-label">Risk</p>
              <h2 className="mt-4 text-3xl font-semibold tracking-[-0.02em]">
                Built to stop you.
              </h2>
              <p className="mt-4 max-w-[34rem] text-fg-muted">
                A kill switch is only useful if it actually fires. These gates are wired to the
                same process that generates signals, not to a dashboard toggle.
              </p>
            </Reveal>
            <ul className="space-y-px overflow-hidden rounded-2xl border border-hairline bg-[var(--color-hairline)]">
              {GUARDS.map(([k, v], i) => (
                <Reveal as="li" key={k} delay={i * 0.05} className="bg-bg">
                  <div className="px-6 py-6">
                    <div className="text-sm font-semibold">{k}</div>
                    <p className="mt-1 text-sm text-fg-muted">{v}</p>
                  </div>
                </Reveal>
              ))}
            </ul>
          </div>
        </section>

        {/* CTA */}
        <section className="mx-auto max-w-6xl px-6 pb-28">
          <Reveal>
            <div className="mk-card flex flex-col items-start gap-8 px-8 py-14 md:flex-row md:items-center md:justify-between md:px-14">
              <div>
                <h2 className="max-w-[24rem] text-2xl font-semibold tracking-[-0.02em]">
                  Open the desk and watch the tape argue with itself.
                </h2>
                <p className="mt-3 text-sm text-fg-muted">No keys required. Nothing routes without them.</p>
              </div>
              <div className="flex flex-wrap gap-3">
                <Link href="/dashboard" className="mk-btn mk-btn-primary">
                  Open live terminal <ArrowRight className="h-4 w-4" />
                </Link>
                <a
                  href={process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}
                  target="_blank"
                  rel="noreferrer"
                  className="mk-btn mk-btn-ghost"
                >
                  Read the API
                </a>
              </div>
            </div>
          </Reveal>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
