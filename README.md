# QuantPulse AI

Quantum + HFT + Sentiment + Prediction-market trading agent platform with a
closed-loop research engine: **trace information → form a thesis → attack it →
measure the outcome → explain failures → test which sources deserve trust.**

## Quickstart (no API keys needed — mock feeds built in)

### Backend
```bash
cd quantpulse-ai/backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
- REST: `GET http://localhost:8000/api/snapshot`
- WS: `ws://localhost:8000/ws/stream`
- Docs: `http://localhost:8000/docs`

### Frontend
```bash
cd quantpulse-ai/frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```
Open `http://localhost:3000`.

## The Research Loop

Five features, one closed loop — not five isolated demos:

```
MarketEvent → Evidence → Signal → Thesis → Stress → Prediction
            → Outcome → Autopsy → Experiment → model evidence
```

Every stage calls the **same** `services.fusion.fuse()` function, so a stress
delta, an ablation delta and the dashboard number are directly comparable.

### Feature 1 — Information Propagation (`/information-flow`)
Builds a timestamped chain per event: `EVENT → NEWS → PREDICTION → REDDIT → X
→ ORDER FLOW → PRICE`. In LIVE mode lags come from observed first-crossing
timestamps; without credentials they come from a deterministic scenario and
are labelled SIMULATED. Ordering is a fact; causation is never asserted.

### Feature 2 — Thesis Stress Lab (`/thesis-lab`)
A thesis is a testable hypothesis, not a BUY/SELL label. Seven named
perturbation rules (sentiment deterioration, order-flow reversal,
prediction-market disagreement, volatility expansion, liquidity
deterioration, momentum reversal, conflicting source) re-run the same fusion
on perturbed evidence. Robustness = share of scenarios where the original
direction survives above the neutral floor.

### Feature 3 — Event → Asset Transmission (`/api/events/{id}/assets`)
`EVENT → THEME → ASSET` graph. Relationships are typed by `RelationKind`
(`observed`, `historical`, `correlated`, `associated`, `potentially affected`)
— causal vocabulary is deliberately absent. Historical response statistics
stay `null` until enough comparable resolved events exist.

### Feature 4 — Prediction Failure Autopsy (`/model-autopsy`)
When a prediction resolves incorrectly, each stored feature is compared with
what was observed, and a failure mode is ranked by rule agreement with a
likelihood — never as proven causation. Aggregate performance is withheld
until 20 resolved observations exist.

### Feature 5 — Adaptive Signal Tournament (`/research-lab`)
Controlled ablations of the fusion model over one shared window. Arms differ
only in which features are enabled. Results carry sample sizes; thin cells
report INSUFFICIENT DATA. No "winner" labels are produced.

### Demo (`/demo`)
A deterministic, self-contained walkthrough of the complete loop on synthetic
data. Takes 2–3 minutes. Every record is labelled SIMULATED SCENARIO.

## Research Integrity

- **LIVE** — real credentialed feeds.
- **SIMULATED** — deterministic synthetic scenario (demo only).
- **MOCK** — no credentials; seeded simulator.
- **BACKTEST** — replayed historical window.
- **INSUFFICIENT DATA** — sample floor not met; no numbers reported.

The platform never claims causation it has not demonstrated, never fabricates
model performance, and never claims quantum advantage unless experimentally
demonstrated. Fusion weights are documented as **configured priors**, not
fitted parameters.

## Architecture

### Core
- `quantum_hft/hft_engine.py` — L2 simulator, Order Flow Imbalance (Cont 2014), latency-arb, VWAP/TWAP.
- `quantum_hft/qaoa_optimizer.py` — PennyLane QAOA (p=2) portfolio selection + classical fallback.
- `quantum_hft/quantum_risk.py` — Sharpe/Sortino/VaR/CVaR + QAE Monte-Carlo proxy.
- `agents/sentiment_agent.py` — Reddit/X mock + live hooks, VADER/lexicon scoring.
- `agents/prediction_agent.py` — crowd vs quantum fair odds, edge detector.
- `agents/betting_engine.py` — BET_FOR on alignment; BET_AGAINST when euphoria (>90%) diverges from OFI.
- `trading/` — Alpaca paper wrapper (mock when keys absent) + backtester (HFT vs sentiment vs buy-hold).

### Research loop
- `models/` — unified domain: `MarketEvent`, `Evidence`, `Signal`, `Thesis`,
  `StressTest`, `PredictionRecord`, `PredictionOutcome`, `Autopsy`,
  `ExperimentSpec`, `ExperimentResult`, `TournamentMatrix`.
- `services/fusion.py` — the single `fuse()` function shared by signals,
  stress tests and tournament ablations.
- `services/feed_layer.py` — normalized feed boundary; no service grows its
  own Reddit/X/Alpaca client.
- `services/information_propagation.py` — event detection + chain building.
- `services/thesis_stress.py` — thesis construction + 7 perturbation rules.
- `services/event_transmission.py` — theme taxonomy + event→asset graph.
- `services/prediction_autopsy.py` — resolution + failure analysis.
- `services/signal_tournament.py` — ablation arms + metric computation.
- `services/closed_loop.py` — orchestrator: event → … → experiment.
- `services/scenarios.py` — deterministic `NVDA_EVENT_001` demo scenario.
- `api/` — FastAPI routers for each feature.

### Data model
11 research tables (SQLModel): `market_events`, `event_evidence`, `signals`,
`theses`, `thesis_stress_tests`, `predictions`, `prediction_outcomes`,
`prediction_autopsies`, `experiments`, `experiment_results`, `model_versions`.
Every record carries `created_at`, `updated_at`, `data_mode`, `model_version`.
Additive migrations only — no destructive schema changes.

## API Endpoints

### Research
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/information/events` | List detected events |
| POST | `/api/information/events/detect` | Run detection over current snapshot |
| GET | `/api/information/events/{id}` | One event + evidence |
| GET | `/api/information/propagation/{id}` | Timestamped layer chain |
| GET | `/api/information/propagation/{id}/node/{layer}` | Node detail |
| POST | `/api/thesis/create` | Fuse evidence into a thesis |
| POST | `/api/thesis/{id}/stress-test` | Perturb + re-fuse under 7 rules |
| GET | `/api/thesis/{id}` | Thesis + latest stress test |
| GET | `/api/events` | List events |
| GET | `/api/events/{id}` | One event |
| GET | `/api/events/{id}/assets` | Event → theme → asset graph |
| GET | `/api/assets/{symbol}/events` | Events touching this asset |
| GET | `/api/predictions` | List predictions |
| GET | `/api/predictions/{id}` | One prediction + outcome |
| POST | `/api/predictions/{id}/resolve` | Measure against realized price |
| GET | `/api/predictions/{id}/autopsy` | Failure analysis |
| GET | `/api/model/failure-analysis` | Aggregate (withheld below floor) |
| POST | `/api/experiments` | Create ablation spec |
| GET | `/api/experiments` | List experiments |
| GET | `/api/experiments/{id}` | One experiment + result |
| POST | `/api/experiments/{id}/run` | Run the arm |
| GET | `/api/experiments/{id}/results` | Experiment results |
| GET | `/api/experiments/matrix` | Rows=arms, columns=regimes |
| GET | `/api/demo` | Scenario definition |
| POST | `/api/demo/run` | Walk the complete loop |
| GET | `/api/research/cycle` | Run loop over live snapshot |
| GET | `/api/research/overview` | Signals, model evidence, feed status |
| GET | `/api/research/signals` | Recent fused signals |
| GET | `/api/research/evidence` | Evidence records |

## Testing
```bash
cd backend
python -m pytest tests/test_research_loop.py -v
```
36 tests covering: event creation, propagation, signal generation, thesis
creation, stress scenarios, prediction creation, resolution, failure autopsy,
experiment creation, reproducibility, mock-mode operation, missing
credentials, and data-mode integrity.

## Env (optional live keys)
Copy `backend/.env.example` → `backend/.env` and fill Alpaca/Reddit/Twitter keys.

## Deploy: laptop backend + Vercel frontend (+ optional Supabase DB)

The backend runs on your laptop; the frontend is hosted on Vercel and calls
your laptop from the browser. This works for you on your own machine while
the backend is running — other visitors would need a public tunnel URL
(e.g. `ngrok http 8000`) as `NEXT_PUBLIC_API_URL` instead.

### 1. Supabase (database, optional — SQLite file works locally)
1. Create project at supabase.com → Settings → API: copy URL, `anon` key, `service_role` key.
2. Settings → Database: copy the Postgres connection string → `DATABASE_URL`.
3. Tables are auto-created by the backend on first boot (`init_db`).

### 2. Laptop (backend — always running while you use the site)
1. Fill `backend/.env` (keys optional; empty = honest mock fallback).
2. Start: `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1`
   from `backend/`. Verify `http://localhost:8000/health`.
3. Optional live Indian stocks: run `npx wrangler dev --port 5000` in
   `Indian-Stock-Market-API/` (defaults are already wired: no config needed).
4. In `backend/.env`, replace `<your-app>` in `CORS_ORIGINS` with your real
   Vercel app name after step 3 below, then restart the backend.

### 3. Vercel (frontend)
1. Vercel → New Project → same repo, **Root Directory = `quantpulse-ai/frontend`**.
2. Env vars: `NEXT_PUBLIC_API_URL=http://localhost:8000`,
   `NEXT_PUBLIC_REQUIRE_AUTH=0`, then Deploy.
3. Back in `backend/.env`, set `CORS_ORIGINS=...https://<app>.vercel.app`
   and restart the backend.

### 4. Verify production
- `GET /api/feeds/status` shows `live` per configured key.
- Dashboard + `/prediction-bets` (red edges) + `/allocator` load data.
- `GET /api/history` row count grows; `POST /api/allocate` returns a plan.

> Legacy alternative: `render.yaml` still pins a Render backend blueprint
> (`NEXT_PUBLIC_API_URL=https://<svc>.onrender.com`). Unused in the
> laptop-backend setup; free tier sleeps when idle.
