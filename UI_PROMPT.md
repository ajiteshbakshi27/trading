# Parakh — prompt for an AI UI builder

Paste everything below the line into v0, Lovable, Bolt or a similar tool.
Build one page at a time if the tool struggles: start with the landing page,
then X-ray, then Check a trade.

---

Design and build the front end for **Parakh**, a web app for Indian retail stock
and F&O traders.

## What Parakh is

Parakh (परख, Hindi for "to test the worth of something") is an AI trading coach.
Tagline: **"Test your trade before the market does."**

It does three things:
1. **Checks a trade idea before the trade.** The user types an idea in plain
   English ("HDFC Bank will rally in 2 weeks, 70% sure"). Parakh tests it against
   price history and shows the odds, the red flags, and what would prove it wrong.
2. **X-rays the user's past trades.** The user uploads a broker tradebook CSV.
   Parakh shows which habits their losses come from, in rupees ("Trades right
   after a loss: 56 trades that together lost ₹13,979").
3. **Scores calibration.** It tracks every saved idea and shows whether the
   user's confidence matches reality ("When you say 80% sure, you are right 54%
   of the time").

Parakh is **not** a tips service. It never says buy, sell or hold, and it gives
no price targets of its own. It only analyses the user's own ideas and trades.
The UI must never look or read like a tips app, a casino, or a get-rich product.

## Who uses it

Indian retail traders aged about 20 to 40, mostly on phones, many of them losing
money in options. They are not finance professionals. Write every label in
simple English. Use ₹ and Indian number formatting (₹1,25,000).

## Look and feel

- Modern, premium, calm. Think Linear, Vercel, Stripe, Zerodha Kite: lots of
  space, sharp type, restrained colour. It should feel like a serious tool that
  respects the user, not a flashy trading terminal.
- Dark theme first, with a light theme toggle.
- One accent colour (emerald green). Use red only for losses and warnings, amber
  for cautions. No neon, no rainbow gradients, no rocket or money emojis, no
  stock-ticker tape, no fake "live profits" counters.
- A clean sans-serif (Inter or Geist). Tabular numerals for every number.
- Subtle motion only: soft fades and number count-ups. Nothing that bounces.
- Mobile first. Every page must work at 375px wide with no sideways scrolling.
  Bottom tab bar on mobile, top nav on desktop.
- Accessible: visible focus rings, good contrast, real buttons and labels.

## Honesty rules the design must show

These are the product's main difference, so make them visible:
- Every data panel carries a small tag: **Live data**, **Simulated data** or
  **Sample data**.
- When there is too little data, show a clear "Not enough data yet (7 of 10
  needed)" state with a progress bar. Never show a score built on too few trades.
- A short disclaimer in every page footer: "Parakh is an analysis and journaling
  tool. It is not a SEBI-registered investment adviser and does not recommend
  buying or selling any security."
- No testimonials, user counts, accuracy percentages or logos that are not real.
  Leave those sections out.

## Pages

**Public (no login)**
1. **Landing page `/`** — hero with the tagline, one line on what it does, two
   buttons: "X-ray your tradebook" and "Check a trade idea". Below: the problem
   (about 9 in 10 Indian F&O traders lose money; they need feedback, not tips),
   three feature blocks (Check, X-ray, Calibration) each with a product
   screenshot-style mock, an "honest by design" section, and a final call to action.
2. **Tradebook X-ray `/xray`** — big upload area plus a "Use a sample tradebook"
   button. Result: a headline card with the biggest finding in large type, four
   stats (closed trades, net P&L, win rate, average win/loss), then a grid of
   habit cards. Each habit card: title, one-line explanation, a status tag
   (Losing habit / Shape of your losses / Not a problem / Too few trades), the
   rupee amount in large type, and small comparison text. End with a sign-up prompt.
3. **Try a check `/try`** — one large text box, three example chips, a "Check it"
   button, then the report (see Check a trade).
4. **Login, Sign up, Forgot password** — email and password, simple and centred.
5. **Public idea page `/t/[slug]`** — a shared, sealed idea with its outcome.

**App (after login)**
6. **Home `/home`** — greeting, today's brief, open ideas, calibration snapshot,
   quick buttons to check a trade or upload trades.
7. **Check a trade `/check`** — text box and optional exact levels (symbol,
   direction, days, confidence, target, stop). Report: a checklist score out of
   100, a list of checks each marked OK / Caution / Red flag, odds bars (chance
   of target before stop), past similar setups, and a "What would prove you
   wrong" box.
8. **My ideas `/ideas`** and **idea detail `/ideas/[id]`** — list with status
   pills (Open, Target hit, Stopped out, Timed out); detail shows the original
   report, the outcome, and an autopsy of likely causes.
9. **Journal `/journal`** — upload CSV, connect Zerodha, stats row, the X-ray
   report, table of closed trades with an "Autopsy" action on each row.
10. **Calibration `/calibration`** — the signature chart: stated confidence on
    the x-axis, actual hit rate on the y-axis, with the diagonal "perfect" line.
    A one-sentence verdict above it.
11. **Hype radar `/radar`** — watchlist table: social attention versus price move.
12. **Events `/events`** — Indian market events (RBI policy, Budget, results)
    with the sectors and stocks each one touches.
13. **F&O analyser `/options`** — payoff diagram, greeks, probability of profit.
14. **Strategy backtests `/strategy-lab`** — pick a rule, see results with
    warnings when a result looks too good to be true.
15. **Leaderboard `/leaderboard`** — ranked by calibration, never by profit.
16. **Settings `/settings`** — profile, alerts (Telegram), connected broker,
    delete my data.
17. **Copilot** — a chat button fixed at the bottom right on every app page.
    The user asks about their own ideas and trades in plain language.

## Components to design well

Stat tile, status pill, data-mode tag, habit card, checklist row, odds bar,
calibration chart, empty state, "not enough data" state, loading skeleton, error
box, upload dropzone, primary and ghost buttons, data table that turns into
stacked cards on mobile.

## Technical requirements

- **Next.js 14 (App Router), TypeScript, Tailwind CSS.** Icons: lucide-react.
  Charts: Recharts. No other UI framework is required; shadcn/ui is fine.
- Build presentational components that take data through props. Do not invent a
  backend. Use realistic mock data in the same shapes as below, clearly marked
  "Sample data" in the UI.
- All data comes from an existing REST API at `NEXT_PUBLIC_API_URL`. Keep every
  fetch in one file (`lib/api.ts`) so it can be swapped for the real client.
  Main endpoints:
  - `POST /api/parakh/public/xray?sample=1` and `POST /api/parakh/public/xray` (file upload)
  - `POST /api/parakh/public/check` and `POST /api/parakh/check` with `{ idea, save }`
  - `GET /api/parakh/theses`, `GET /api/parakh/theses/{id}`
  - `GET /api/parakh/journal`, `GET /api/parakh/journal/xray`, `POST /api/parakh/journal/import`
  - `GET /api/parakh/calibration`, `GET /api/parakh/leaderboard`, `GET /api/parakh/brief`
  - `POST /api/parakh/copilot` with `{ question, history }`
- Auth is Supabase email + password. Leave a clear place for the session and
  do not build your own auth.

X-ray response shape, for the mock:

```json
{
  "sample": true,
  "sample_label": "Sample tradebook: invented trades for demonstration.",
  "stats": { "win_rate": 0.488, "avg_win": 310, "avg_loss": -420 },
  "xray": {
    "status": "ok",
    "headline": "Trades right after a loss: 56 trades that together lost ₹13,979.",
    "n_trips": 201, "net_pnl": -14008, "pattern_floor": 5,
    "period": { "from": "2026-08-03", "to": "2026-10-23" },
    "patterns": [
      { "id": "revenge", "title": "Trades right after a loss",
        "what": "Entered within 30 minutes of closing a losing trade, on the same day.",
        "kind": "habit", "status": "leak", "n": 56, "net_pnl": -13979,
        "win_rate": 0.375, "avg_pnl": -250, "avg_pnl_other_trades": 0 }
    ],
    "caveat": "This shows where your losses cluster. It does not prove you would have kept the money by skipping these trades."
  }
}
```

## What good looks like

A first-time visitor on a phone understands in five seconds what Parakh does,
taps "Use a sample tradebook", and sees a clear, slightly uncomfortable truth
about trading habits in rupees. Nothing on the screen promises profit.
