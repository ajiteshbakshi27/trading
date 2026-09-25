import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Legal & risk",
  description: "Risk disclosure, privacy and terms for the QuantPulse AI terminal.",
};

export default function LegalPage() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-24">
      <p className="section-label">Legal</p>
      <h1 className="mt-4 text-3xl font-semibold tracking-[-0.02em]">Risk disclosure</h1>
      <div className="mt-8 space-y-10 text-sm leading-relaxed text-fg-muted">
        <section>
          <h2 className="text-base font-semibold text-fg">Not investment advice</h2>
          <p className="mt-2">
            QuantPulse AI is an engineering demonstration. Signals, allocations, projected returns and
            drawdown figures are model output, not predictions or advice. Backtests run on simulated
            and delayed data. Do not trade real money on the output of this software.
          </p>
        </section>
        <section>
          <h2 className="text-base font-semibold text-fg">Paper trading by default</h2>
          <p className="mt-2">
            Without brokerage credentials nothing routes. With credentials, orders are placed against
            the paper-trading endpoint unless you explicitly change the base URL. The emergency kill
            switch halts signal generation and attempts to liquidate open positions, but it is a
            safety net, not a guarantee — orders can be rejected, delayed or partially filled.
          </p>
        </section>
        <section id="privacy" className="scroll-mt-24">
          <h2 className="text-base font-semibold text-fg">Privacy</h2>
          <p className="mt-2">
            The terminal stores signals, prediction odds, portfolio inputs and order logs in a local
            database on the machine or server running it. Market and sentiment providers receive the
            requests this software makes on your behalf. No data is sold. Clearing the database file
            erases all history.
          </p>
        </section>
        <section id="terms" className="scroll-mt-24">
          <h2 className="text-base font-semibold text-fg">Terms</h2>
          <p className="mt-2">
            The software is provided as-is, without warranty of fitness or profitability. Quantum
            simulations run on classical simulators; the &ldquo;quantum&rdquo; labels describe the
            algorithm family, not hardware advantage. Third-party market data remains subject to its
            provider's licensing terms and rate limits.
          </p>
        </section>
      </div>
    </main>
  );
}
