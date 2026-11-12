import Link from "next/link";
import { ArrowRight } from "lucide-react";
import SiteHeader from "@/components/marketing/SiteHeader";
import SiteFooter from "@/components/marketing/SiteFooter";
import Reveal from "@/components/marketing/Reveal";

const STEPS = [
  { k: "01", title: "Check before you trade", body: "Type your idea the way you'd say it — “Bank Nifty will rally after RBI, two weeks, 70% sure.” Parakh tests it against trend, momentum, daily noise, the odds of hitting your target before your stop, and how similar setups played out in the same stock." },
  { k: "02", title: "It tracks itself", body: "Every idea is priced, saved and resolved automatically against real NSE prices — target hit, stopped out, or timed out. No editing after the fact, no selective memory." },
  { k: "03", title: "Learn why you lost", body: "Each loss gets an autopsy: stop inside normal noise, fighting the trend, chasing a stretched move, a results-day gap, or a market-wide fall. One clear lesson per trade." },
  { k: "04", title: "Know your real odds", body: "Your calibration score shows whether “80% sure” actually means 80%. It's the habit that separates traders who last from the ones who don't." },
];

const FEATURES = [
  ["Journal with Zerodha", "Import your Console tradebook or connect Kite. Parakh pairs buys and sells, then shows the habits costing you money — like holding losers four times longer than winners."],
  ["Hype radar", "Reddit chatter on Indian trading subs versus what price is doing, for your watchlist. Telegram alerts when the crowd and the chart disagree."],
  ["Event impact maps", "RBI policy, the Budget, results season, crude, the rupee: which stocks each event tends to touch, and how they actually moved last time."],
  ["F&O analyser", "Payoff, breakevens, worst case, greeks and a realistic probability of profit for any Nifty or Bank Nifty options position — before you place it."],
  ["Honest backtests", "Simple rules on real NSE history, with next-day fills, costs, out-of-sample tests and loud warnings when results are too good to be true."],
  ["Verified track record", "Share a sealed idea link anyone can verify. The leaderboard ranks traders by calibration, not by screenshots of profits."],
];

export default function LandingPage() {
  return (
    <>
      <SiteHeader />
      <main>
        <section className="mx-auto max-w-6xl px-6 pb-24 pt-28 md:pt-36">
          <p className="section-label">Parakh · परख — to test, to judge</p>
          <h1 className="mt-5 max-w-3xl text-[clamp(2.4rem,5.2vw,4rem)] font-semibold leading-[1.05] tracking-[-0.03em]">
            Test your trade before the market does.
          </h1>
          <p className="mt-6 max-w-xl text-base leading-relaxed text-fg-muted">
            An AI trading coach for Indian markets. Check an idea before you place it, see your real odds,
            and get an honest autopsy when it goes wrong — so the next trade is better than the last.
          </p>
          <div className="mt-9 flex flex-wrap gap-3">
            <Link href="/signup" className="mk-btn mk-btn-primary">Check your first trade free <ArrowRight className="h-4 w-4" /></Link>
            <Link href="/xray" className="mk-btn mk-btn-ghost">X-ray your tradebook</Link>
            <Link href="/try" className="mk-btn mk-btn-ghost">Try a trade check</Link>
          </div>
          <p className="mt-6 text-xs text-fg-muted">Not tips. Not advice. A second opinion on your own ideas, backed by data.</p>
        </section>

        <section id="how" className="scroll-mt-24 border-y border-hairline bg-surface/40">
          <div className="mx-auto max-w-6xl px-6 py-24">
            <Reveal>
              <p className="section-label">How it works</p>
              <h2 className="mt-4 max-w-[30rem] text-3xl font-semibold tracking-[-0.02em]">Most traders don&apos;t need more tips. They need feedback.</h2>
            </Reveal>
            <div className="mt-14 grid gap-px overflow-hidden rounded-2xl border border-hairline bg-[var(--color-hairline)] md:grid-cols-2">
              {STEPS.map((s, i) => (
                <Reveal key={s.k} delay={i * 0.05} className="bg-bg">
                  <div className="h-full px-6 py-9">
                    <span className="tnum text-xs text-fg-muted">{s.k}</span>
                    <h3 className="mt-3 text-lg font-semibold">{s.title}</h3>
                    <p className="mt-2 text-sm leading-relaxed text-fg-muted">{s.body}</p>
                  </div>
                </Reveal>
              ))}
            </div>
          </div>
        </section>

        <section id="features" className="mx-auto max-w-6xl scroll-mt-24 px-6 py-24">
          <Reveal>
            <p className="section-label">Everything in one place</p>
            <h2 className="mt-4 text-3xl font-semibold tracking-[-0.02em]">Built for how Indians actually trade.</h2>
          </Reveal>
          <div className="mt-12 grid gap-4 md:grid-cols-3">
            {FEATURES.map(([t, b], i) => (
              <Reveal key={t} delay={i * 0.04}>
                <div className="mk-card h-full px-6 py-7">
                  <h3 className="font-semibold">{t}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-fg-muted">{b}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </section>

        <section id="honesty" className="scroll-mt-24 border-y border-hairline bg-surface/40">
          <div className="mx-auto grid max-w-6xl gap-10 px-6 py-24 md:grid-cols-2">
            <Reveal>
              <p className="section-label">Honest by design</p>
              <h2 className="mt-4 text-3xl font-semibold tracking-[-0.02em]">No fake accuracy numbers.</h2>
            </Reveal>
            <ul className="space-y-4 text-sm leading-relaxed text-fg-muted">
              <li><b className="text-fg">Every number is labelled.</b> Live NSE data, or simulated when a feed is down — never mixed up.</li>
              <li><b className="text-fg">Small samples stay quiet.</b> Scores and base rates appear only after enough real outcomes.</li>
              <li><b className="text-fg">Explanations, not excuses.</b> Autopsies rank what likely went wrong; they don&apos;t claim to prove it.</li>
              <li><b className="text-fg">Your data is yours.</b> Read-only broker access; Parakh never places orders.</li>
            </ul>
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-6 py-24">
          <div className="mk-card flex flex-col items-start gap-6 px-8 py-12 md:flex-row md:items-center md:justify-between md:px-12">
            <div>
              <h2 className="max-w-[26rem] text-2xl font-semibold tracking-[-0.02em]">Your next trade deserves a second opinion.</h2>
              <p className="mt-2 text-sm text-fg-muted">Free to start. Takes 30 seconds.</p>
            </div>
            <Link href="/signup" className="mk-btn mk-btn-primary">Create a free account <ArrowRight className="h-4 w-4" /></Link>
          </div>
          <p className="mt-8 text-[11px] leading-relaxed text-fg-muted">
            Parakh is an analysis and journaling tool, not a SEBI-registered investment adviser or research analyst, and does not
            recommend buying or selling securities. Trading involves risk of loss.
          </p>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
