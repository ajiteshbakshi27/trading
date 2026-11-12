import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Privacy and risk",
  description: "What Parakh stores, who else sees it, how to delete it, and the risk disclosure.",
};

function Section({ id, title, children }: { id?: string; title: string; children: React.ReactNode }) {
  return (
    <section id={id} className="scroll-mt-24">
      <h2 className="text-base font-semibold text-fg">{title}</h2>
      <div className="mt-2 space-y-2">{children}</div>
    </section>
  );
}

export default function LegalPage() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-24">
      <p className="section-label">Privacy and risk</p>
      <h1 className="mt-4 text-3xl font-semibold tracking-[-0.02em]">Your data, in plain words</h1>
      <p className="mt-3 text-sm text-fg-muted">
        Parakh is an early product. This page says what it does today. It has not yet been reviewed by a lawyer.
      </p>
      <div className="mt-8 space-y-10 text-sm leading-relaxed text-fg-muted">
        <Section id="privacy" title="What Parakh stores">
          <ul className="list-disc space-y-1 pl-5">
            <li>Your login email (kept by Supabase, our login provider). Parakh never sees your password.</li>
            <li>The trade ideas you save, and the report made for each one.</li>
            <li>The trades you import into your Journal, from a file or from Zerodha.</li>
            <li>Your settings, watchlist, your own trading rules, and a log of alerts sent to you.</li>
            <li>If you connect Zerodha: a read-only access token, stored encrypted. Parakh cannot place orders.</li>
          </ul>
          <p>
            The free trial pages (Tradebook X-ray, Check a trade, Sample score) store nothing. A file you upload
            there is read once to make the report and is not saved.
          </p>
        </Section>

        <Section title="Who else sees it">
          <ul className="list-disc space-y-1 pl-5">
            <li><b>Supabase</b> hosts the login and the database.</li>
            <li>
              <b>The AI provider</b> (Google Gemini or Anthropic Claude) receives the idea you type so it can be
              read, and, when you use the copilot, your question plus a summary of your own ideas and trades.
              On a free AI plan the provider may use this text to improve its products.
            </li>
            <li><b>Yahoo Finance</b> receives the stock symbol when prices are fetched. Nothing about you.</li>
            <li><b>Telegram</b> receives your alerts, only if you add your chat ID.</li>
          </ul>
          <p>Parakh does not sell your data and shows no ads.</p>
        </Section>

        <Section title="What is public">
          <p>
            Nothing, unless you choose it. An idea becomes public only when you press Publish on it. Then the idea,
            its result and your public handle appear on its share page and the leaderboard. Your trades are never public.
          </p>
        </Section>

        <Section id="delete" title="Download or delete your data">
          <p>
            Go to Settings, then Your data. You can download everything Parakh stores about you as one file, or
            delete all of it at once. Deleting is immediate and cannot be undone. It removes your ideas, trades,
            rules, settings, alerts and broker connection. Your login email stays with Supabase until the login
            itself is removed; write to us and we will remove it.
          </p>
        </Section>

        <Section id="risk" title="Not investment advice">
          <p>
            Parakh is an analysis and journaling tool. It is not a SEBI-registered investment adviser or research
            analyst. It does not recommend buying, selling or holding any security, and it gives no price targets
            of its own. It tests the ideas you bring and shows patterns in your own trades.
          </p>
          <p>
            Odds, past similar setups and backtests describe history. They do not guarantee any future result.
            Trading in shares and derivatives can lose money, including more than you expect.
          </p>
        </Section>

        <Section title="Data labels">
          <p>
            Every screen says where its numbers come from: Live data (delayed NSE prices through Yahoo Finance),
            Simulated data (shown when live prices are unavailable; do not trade on it) or Sample data (invented
            for demonstration). Scores are withheld when there are too few trades or ideas to be meaningful.
          </p>
        </Section>

        <Section id="terms" title="Terms">
          <p>
            The software is provided as it is, without any warranty. Market data belongs to its providers and is
            subject to their terms. You are responsible for your own trading decisions.
          </p>
        </Section>
      </div>
    </main>
  );
}
