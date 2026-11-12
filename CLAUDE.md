# CLAUDE.md — Parakh project memory

Read this first in every session. It records what the owner and Claude decided
and where the work stands. Keep it updated at the end of each session.

**Starting a new session? Open `NEXT_SESSION.md` first.** It has the owner's
exact instructions, what's done, and the first steps (apply the bundle if needed,
then push the branch, which the owner explicitly asked Claude to do).

## The product (decided)
- **Name:** Parakh (परख = "to test / judge the worth of"). Formerly "QuantPulse AI".
  Tagline: "Test your trade before the market does."
- **Positioning:** AI trading coach for **Indian retail traders** (India-first test market).
  It checks the user's OWN trade ideas before they trade, tracks outcomes honestly,
  explains losses (autopsy) and measures calibration. **Not tips, not advice.**
- **Regulatory stance:** analysis + journaling tool, NOT a SEBI-registered adviser /
  research analyst. Never output buy/sell/hold recommendations or our own price
  targets. Disclaimers on every page. Get a lawyer's SEBI review before public launch.
- **Integrity rules:** every number labelled live vs simulated; sample floors before
  scores; autopsies rank likely causes, never claim causation; theses immutable;
  public ideas SHA-256 sealed; no random inputs in signals.
- **Business model:** deliberately postponed — owner wants to discuss it later
  (raise it when the product is near launch). Earlier suggestion: freemium,
  Pro ≈ ₹499–999/month (broker sync, unlimited autopsies, copilot, alerts), later B2B.

## Owner preferences
- Wants things done **fast**; prefers action over long plans.
- Windows PC (Dell, user `dellg15`). Keep **C: drive free** — project should live on
  **D:\Parakh\parakh**. Original folder: `C:\Users\dellg15\quantpulse-ai`.
- Use simple language; owner is not deeply technical in infra.

## What is built (branch `claude/project-review-improvements-oz3vbw`, commits 24204ac, 64775ea)
Backend (FastAPI, `backend/app/parakh/*`, routes `backend/app/api/parakh.py` → `/api/parakh/*`):
thesis_check (idea parser Claude/rules, checklist, Monte-Carlo odds, analogues, fusion
stress), theses (auto-resolve), autopsy, calibration (Brier, floor 10), journal (Zerodha
tradebook CSV, FIFO round trips, insights, IST times), kite (Zerodha Kite Connect,
encrypted tokens), copilot (Claude tool loop, model `claude-opus-5-5`, fallbacks="default"),
hype_radar (Indian subreddits + Telegram), india_events, options (BS/greeks/IV/POP),
strategy_backtest (next-open fills, costs, OOS, sensitivity, warnings), share (seal +
leaderboard), brief, market (yfinance `.NS`, simulated fallback + circuit breaker), universe (NSE list).
Core: `app/core/auth.py` (Supabase JWT JWKS/HS256; dev user only outside production;
`require_admin` via ADMIN_EMAILS), `app/core/state_store.py` (Redis or memory).
Frontend (Next.js 14): Supabase Auth (`src/lib/auth.ts`, dev mode when no env), pages
/home /check /ideas /ideas/[id] /journal /calibration /radar /events /options
/strategy-lab /leaderboard /settings /broker/zerodha /t/[slug] /reset-password;
old pages under "Labs" menu; PWA; components in `src/components/parakh/`.
Also: CI `.github/workflows/ci.yml`, `README.md`, `SETUP.md` (go-live steps),
`render.yaml` (API + 2 cron jobs + Redis), `tools/windows/MOVE-TO-D-DRIVE.bat` + `.ps1`.
Tests: `cd backend && python -m pytest -q` → 79 pass. `cd frontend && npx tsc --noEmit && npm run build` pass.
E2E clicked through all pages in Playwright with zero console errors.

## Open items / next steps (in order)
1. **Push to GitHub.** Cloud session got 403 (Claude GitHub App lacked access).
   From the PC: `git push -u origin claude/project-review-improvements-oz3vbw`.
2. **Move project C: → D:\Parakh\parakh** (owner asked Claude to do this in the PC
   session). Script: `tools/windows/move-to-d-drive.ps1` (copies, verifies, deletes C:
   only on "YES"; skips .next/__pycache__). Untested on Windows — run carefully.
3. Verify **live NSE data** from the PC (Yahoo was blocked in the cloud; only the
   simulated fallback was tested).
4. Turn on real services per `SETUP.md`: Supabase, ANTHROPIC_API_KEY, Kite, Telegram,
   Reddit; deploy Render + Vercel. None were tested with real keys yet.
5. Known gaps: WhatsApp alerts not done (Telegram only); SENSEX (BSE) lot size unverified;
   name/trademark/domain check for "Parakh" not done.
6. Later: business model discussion; SEBI legal review; licensed NSE data for commercial launch.

## Run locally
backend: `cd backend && pip install -r requirements-dev.txt && uvicorn app.main:app --reload --port 8000`
frontend: `cd frontend && npm install && npm run dev` → http://localhost:3000 (dev mode needs no keys)

## Session 2 log (2026-11-11)
- Bundle applied (branch `claude/project-review-improvements-oz3vbw`); owner's local Indian-stock
  edits saved on `backup/local-edits-before-parakh` and merged in. Backend tests: 94 pass,
  1 fails only because `PyJWT` isn't installed locally (`pip install -r backend/requirements.txt`).
- Rename finished: folder is now `D:\Parakh\parakh`; `design-system/parakh`; `backend/parakh.db`;
  remaining code/doc/.env mentions replaced. GitHub repo NOT renamed (still `ajiteshbakshi27/trading`).
- `git push` was blocked by the permission system; still NOT pushed.
- Live NSE data verified from the PC (RELIANCE quote + 30d history came back `live`).
- `main.py` split: now ~155 lines (wiring only). Endpoints in `app/api/{system,snapshot,trading,history}.py`,
  shared singletons in `app/core/runtime.py`. Fixed bug: `/api/predictions/history` was shadowed (404).
- Labs model backtest no longer fabricates social/news/order-flow evidence: price-momentum only,
  deterministic, no look-ahead, output lists `evidence_layers` / `not_backtested`. Honest result on
  real NVDA 1y: ~47% directional accuracy (below coin flip) — expected, not a bug.
- Tests: 110 pass (excluding the PyJWT-dependent one). `tsc --noEmit` clean.
- Tournament: no more silent synthetic data. Order: stored evidence -> real price momentum -> empty
  (INSUFFICIENT DATA). Synthetic set only via `allow_synthetic=True` (used by the labelled demo scenario).
- F&O lot sizes verified from NSE `fo_mktlots.csv` (2026-11-11): NIFTY 65, BANKNIFTY 30, FINNIFTY 60,
  MIDCPNIFTY 120 (were 75/35/65/140). SENSEX 20 unverified. Re-check each NSE circular.
- PyJWT installed; `npm install` run (was missing `@supabase/supabase-js`); full `npm run build` passes.
  Caches for pip/npm are on `D:\Parakh\.pip-cache` and `.npm-cache`. Tests: 113 pass.
- Fixed a flaky tournament test: the labelled demo (`allow_synthetic=True`) must be offline and purely
  synthetic; it had started using live prices. Regression test added. `/api/parakh/options/lots` now returns
  `unverified: ["SENSEX"]` (BSE blocks automated lookups; check the BSE circular by hand).
- E2E on live data verified: idea check (HDFCBANK, `data_mode: live`, "recommend" appears only in the
  disclaimer) and strategy backtest (RELIANCE, live). Tests: 115 pass.

## Session 3 log (2026-11-12)
- Env files prepared: empty slots for every key in `backend/.env` and `frontend/.env.local`;
  `CRON_SECRET` and `TOKEN_ENCRYPTION_KEY` generated into `backend/.env`.
- Owner does NOT want to pay for an Anthropic key yet → added **Google Gemini** as a free AI
  provider (`app/parakh/gemini.py`, plain httpx REST, key in header). `llm.provider()` picks
  Claude if `ANTHROPIC_API_KEY` is set, else Gemini if `GEMINI_API_KEY`, else rules.
  `/api/parakh/me` features now include `"ai": "claude"|"gemini"|null`. Tests: `tests/test_gemini.py`.
- **Real services now connected and verified:** Supabase Auth (`auth_mode: "supabase"`), Supabase
  Postgres (21 tables created), Gemini (`gemini-3.5-flash-lite`; `gemini-flash-latest` hung).
  Real copilot call worked (live RELIANCE quote via tools). ANTHROPIC key deliberately empty.
- Security fix: Supabase exposes `public` tables over REST to the anon key. `database._lock_public_api()`
  now enables RLS on every table at startup (no policies; backend connects as owner). Verified 401.
- `tests/conftest.py` now BLANKS service env vars (empty overrides `.env`); popping was not enough
  once real keys were in `.env`. Tests: 120 pass.
- **`STARTUP_PLAN.md`** written: startup assessment, problems/fixes, feature ranking, business model,
  hackathon prep, phased order. Owner wants to go **slower and more carefully** now, aim for a real
  startup, and use Parakh in hackathons. Next build step = Phase 1 of that file.
- **Phase 1 started.** Built: Tradebook X-ray (`app/parakh/xray.py`: habit leaks in rupees; a leak
  must lose money AND do worse per trade than the user's other trades; loss-only groups are
  "loss_shape", never leaks; floors 20 trips / 5 per habit; never claims money "would be saved"),
  deterministic sample tradebook (`app/parakh/sample.py`, labelled invented), no-login routes
  `/api/parakh/public/{xray,check,sample-tradebook.csv}` (IP rate-limited, nothing stored),
  public pages `/xray` and `/try` (route group `(public)`), X-ray on the Journal page.
  Tests: 133 pass; `npm run build` passes. NOT yet clicked through in a browser.
- Zerodha Kite: Personal plan is free (own account only); Connect is ₹500/month and needed for
  other users. Decision: owner's own account for demos now, multi-user sync in Phase 3.
- Owner dislikes the current UI. `UI_PROMPT.md` is a prompt for an external AI UI builder
  (v0/Lovable); owner will generate a UI in parallel. Any new UI must keep the API contract.
- Phase 1 still to do: deploy (Render + Vercel), demo account with seeded ideas for the
  calibration chart, demo script/slides, backup video.
- Still off: Kite, Telegram, Reddit, Redis (memory store). Not deployed.
