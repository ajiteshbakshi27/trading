# Parakh · परख

**Test your trade before the market does.** An AI trading coach for Indian
retail traders: check an idea before you place it, see your real odds, get an
honest autopsy when it goes wrong, and track whether your confidence means
anything.

> Parakh analyses the user's *own* ideas. It is not a SEBI-registered
> investment adviser or research analyst and never recommends buying or
> selling a security.

## What it does

| Feature | Page | What happens |
|---|---|---|
| Check a trade | `/check` | Free-text idea → checklist (trend, momentum, stretch, reward:risk, stop vs noise, target realism, market backdrop, confidence gap), Monte-Carlo pure-chance odds, historical base rate from similar setups, fusion stress test, "what proves you wrong" levels |
| My ideas | `/ideas` | Every check is saved and resolved automatically against NSE prices (target hit / stopped / timed out), with an autopsy |
| Journal | `/journal` | Zerodha Console tradebook CSV import (or any CSV) + Kite Connect daily sync → FIFO round trips, behaviour insights, per-trade autopsy |
| Calibration | `/calibration` | Brier score, reliability by confidence band, trend; withheld below 10 resolved ideas |
| Copilot | every page | Claude with tools over the user's own ideas, journal and calibration (rule-based fallback without a key) |
| Hype radar | `/radar` | Reddit attention on Indian trading subs vs price for your watchlist; Telegram alerts |
| Event impact maps | `/events` | RBI, Budget, results, monsoon, crude, rupee, Fed, SEBI → themes → NSE stocks, with measured moves where past dates exist |
| F&O analyser | `/options` | Multi-leg payoff, breakevens, max P/L, greeks, implied vol, probability of profit |
| Strategy backtests | `/strategy-lab` | Rule builder on NSE history with next-open fills, costs, in/out-of-sample split, parameter sensitivity, overfitting and survivorship warnings |
| Verified track record | `/t/<slug>`, `/leaderboard` | SHA-256-sealed public ideas, verifiable in the browser; leaderboard ranked by calibration |
| Daily brief + PWA | `/home` | Market, open ideas near stop, resolutions, hype, calibration; installable on phones |

Older experiments (US hype dashboard, research loop, model backtest, etc.)
live under **Labs** in the menu.

## Run locally (no keys needed)

```bash
# backend
cd backend
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000      # http://localhost:8000/docs

# frontend (new terminal)
cd frontend
npm install
npm run dev                                     # http://localhost:3000
```

Without keys Parakh runs in **local dev mode**: no sign-in, and if live NSE
prices can't be fetched the app shows a clearly-labelled **simulated** series.
Copy `backend/.env.example` → `backend/.env` and `frontend/.env.example` →
`frontend/.env.local` to turn on real services. **[SETUP.md](SETUP.md)** walks
through Supabase, Claude, Zerodha, Telegram, Render and Vercel.

## Tests

```bash
cd backend && python -m pytest -q        # 79 tests, fully offline
cd frontend && npx tsc --noEmit && npm run build
```
CI runs both on every push (`.github/workflows/ci.yml`).

## Architecture

```
frontend (Next.js 14, Supabase Auth) ──Bearer JWT──▶ backend (FastAPI)
                                                     ├─ app/core/auth.py         Supabase JWT (JWKS / HS256), dev fallback
                                                     ├─ app/core/state_store.py  Redis or memory: rate limits, kill switch, caches
                                                     ├─ app/parakh/              product logic (one module per feature)
                                                     │   thesis_check · theses · autopsy · calibration · journal · kite
                                                     │   hype_radar · india_events · options · strategy_backtest
                                                     │   share · brief · copilot · llm (Claude) · market (NSE data)
                                                     ├─ app/api/parakh.py        /api/parakh/* routes (all user-scoped)
                                                     └─ app/services, app/api/*  research loop + Labs
storage: Postgres (Supabase) or SQLite · cache: Redis (optional)
```

### Integrity rules
- Every number carries its data mode (**live** or **simulated**); simulated data is never presented as real.
- Scores and base rates are withheld below their sample floors.
- Autopsies rank likely explanations; they never claim causation.
- Thesis terms can't be edited after creation; public ideas are sealed with SHA-256.
- Fusion weights are hand-set priors, documented as such.

## Name

*Parakh* (परख) is Hindi for "to test, assay or judge the worth of something", which is what the app does to every trade idea.
