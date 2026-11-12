# Parakh — startup and hackathon plan

Written 2026-11-12. This is Claude's honest assessment, not a guarantee. Numbers
marked "estimate" are guesses to be tested with real users.

## 1. Is this a good startup idea?

**Yes as a starting point, with one big unproven question.**

What is strong:
- **Real, large problem.** SEBI's own studies say about 9 in 10 individual F&O
  traders in India lose money. They do not lack tips; they lack feedback.
- **Clear difference.** Journals (TradesViz, Tradezella, Edgewonk) look at trades
  *after* they happen. Parakh checks the idea *before* the trade and then scores
  how well the trader's confidence matches reality. Nobody mainstream in India does that.
- **Honest by design.** Live vs simulated labels, sample floors, no tips. That is
  rare in this market and it is also what keeps Parakh outside SEBI adviser rules.
- **It is already built.** Most startups at this stage have slides.

The unproven question:
- **Will losing traders pay for a mirror?** People who lose money usually want a
  tip, not a tool that tells them they are overconfident. This is the one thing
  that decides whether Parakh is a business. Only real users can answer it.

So the next months should be about answering that question cheaply, not about
building more features.

## 2. Problems today, and the fix for each

| # | Problem | Fix |
|---|---------|-----|
| 1 | Nobody outside has used it. | Deploy, then get 10 real traders on it. |
| 2 | A new user must sign up before seeing any value. | Allow a few idea checks without login. |
| 3 | The best feature (calibration) needs 10+ finished ideas, so it takes weeks to show anything. | Make the tradebook upload the first step: instant report from trades the user already made. |
| 4 | Still a lot of pages (15 main + Labs). | For launch, show 4: Check, Journal, Calibration, Home. Keep the rest under More. |
| 5 | Price data is Yahoo (delayed, not licensed for commercial use). | Fine for hackathons and testing. Buy licensed NSE data before charging money. |
| 6 | Free Gemini has daily limits and Google may train on free-tier prompts. | Fine for now. Use a paid AI key before real users upload real trades. |
| 7 | Users are asked to upload their tradebook to an unknown site. | Add a plain privacy page and a "delete all my data" button. |
| 8 | SEBI: analysis tools are fine, advice is not. The line must hold in every sentence the AI writes. | Keep the guardrails; add automated tests that scan AI output for buy/sell wording; lawyer review before launch. |
| 9 | Name not checked. | Trademark and domain search for "Parakh" before printing anything. |
| 10 | Tables were open through Supabase's public API. | **Fixed 2026-11-12**: row level security is now switched on at startup. |

## 3. Features that would make it much better

Ranked by value for effort. The first three matter most.

1. **Tradebook X-ray (the hook).** Upload a Zerodha CSV, get a one-page report in
   under a minute: each bad habit with its rupee cost. "Trades taken within 30
   minutes of a loss cost you ₹41,200 this year." The journal already finds these
   patterns; it needs the rupee cost per pattern and a shareable card.
2. **Pre-trade gate using the trader's own record.** When checking an idea, show:
   "Your last 8 Bank Nifty option buys: 2 wins, average loss ₹3,100." Personal
   history is more convincing than any model.
3. **My rules + discipline score.** The trader writes their own rules (max 2% risk,
   no trade after 2 losses, max 3 trades a day). Parakh scores how often they kept
   them. This rewards discipline, not profit, which is honest and habit-forming.
4. **Telegram bot as the front door.** Send the idea as text (later a voice note)
   in English or Hinglish, get the check back in the chat. Indian traders already
   live in Telegram.
5. **Daily brief + weekly report card.** One morning message; one shareable weekly
   card showing calibration and discipline streak (never profit).
6. **Position-size check.** "This trade risks 9% of your capital. Your usual is 2%."
7. **Hindi / Hinglish interface.**
8. **Zerodha sync.** Removes manual upload. Needs a paid Kite Connect plan, so
   wait until there are users.
9. **Educator dashboard (B2B).** A trading teacher sees their students'
   calibration and discipline. This is also a sales channel: one educator brings
   hundreds of students.

Do not add: tips, signals, copy trading, "AI picks", profit leaderboards. They
break the regulatory position and the brand.

## 4. Business model

The earlier review suggested freemium, and that is still the right shape.

- **Free:** one Tradebook X-ray, 5 idea checks a month, basic journal.
- **Pro, about ₹499/month or ₹3,999/year (estimate):** unlimited checks, full
  calibration history, rules and discipline score, Telegram alerts, copilot,
  broker sync.
- **Educators (B2B), later:** per-student pricing for a class dashboard.
- **Brokers (B2B), much later:** brokers are under SEBI pressure to reduce retail
  losses. A "risk coach" they can offer clients is a real sale, but slow.

Rough scale (estimate): 1,000 Pro users is about ₹5 lakh a month. The first real
goal is far smaller: **10 people who pay anything at all.**

Avoid broker referral commissions tied to how much users trade. Earning more when
users trade more is the opposite of what Parakh promises.

## 5. Making it hackathon-ready

Judges see a project for 3 to 5 minutes. They reward a clear story, one moment
that surprises them, and a demo that does not break.

What to build:
1. **Public link** (Render + Vercel) so judges can open it on their phone.
2. **One-click demo account** filled with realistic sample trades and ideas, so
   calibration and the X-ray show real-looking results immediately.
3. **Sample tradebook button** on the Journal page (no file hunting on stage).
4. **Try without login** for the idea check.
5. **Tradebook X-ray** (feature 1 above). This is the "wow" moment.
6. **Backup:** a 2-minute screen recording in case the wifi dies. The app's
   simulated mode already works offline and is labelled.

The 3-minute story:
1. "9 in 10 Indian F&O traders lose money. They do not need more tips."
2. Upload a tradebook → the X-ray shows what bad habits cost in rupees.
3. Type an idea in plain English → Parakh checks it and shows what would prove it wrong.
4. Show the calibration chart: "says 80% sure, right 54% of the time."
5. Close on honesty: every number labelled live or simulated; no advice, by design.

Good tracks to enter: fintech, AI, financial literacy / social impact.

## 6. Order of work (steady, not rushed)

**Phase 1 — hackathon-ready**
1. Deploy to Render + Vercel.
2. Try-without-login idea check.
3. Demo account + sample tradebook.
4. Tradebook X-ray with rupee costs.
5. Demo script, updated slides, backup video.

**Phase 2 — first 10 real users**
6. Privacy page + delete-my-data.
7. Pre-trade gate with the trader's own record.
8. My rules + discipline score.
9. Telegram bot + daily brief.
10. Talk to every user. Change the plan based on what they say.

**Phase 3 — turn it into a business (only if Phase 2 shows people care)**
11. Payments (Razorpay), Pro plan.
12. Zerodha sync, Hindi.
13. Paid AI key, licensed data, SEBI lawyer review, trademark.
14. Educator dashboard.
