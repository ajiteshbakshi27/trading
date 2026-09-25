# QuantPulse AI

Quantum + HFT + Sentiment + Prediction-market trading agent platform.

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

## Architecture
- `quantum_hft/hft_engine.py` — L2 simulator, Order Flow Imbalance (Cont 2014), latency-arb, VWAP/TWAP.
- `quantum_hft/qaoa_optimizer.py` — PennyLane QAOA (p=2) portfolio selection + classical fallback.
- `quantum_hft/quantum_risk.py` — Sharpe/Sortino/VaR/CVaR + QAE Monte-Carlo proxy.
- `agents/sentiment_agent.py` — Reddit/X mock + live hooks, VADER/lexicon scoring.
- `agents/prediction_agent.py` — crowd vs quantum fair odds, edge detector.
- `agents/betting_engine.py` — BET_FOR on alignment; BET_AGAINST when euphoria (>90%) diverges from OFI.
- `trading/` — Alpaca paper wrapper (mock when keys absent) + backtester (HFT vs sentiment vs buy-hold).

## Env (optional live keys)
Copy `backend/.env.example` → `backend/.env` and fill Alpaca/Reddit/Twitter keys.

## Deploy: Render (backend) + Vercel (frontend) + Supabase (DB)

### 1. Supabase (database)
1. Create project at supabase.com → Settings → API: copy URL, `anon` key, `service_role` key.
2. Settings → Database: copy the Postgres connection string → `DATABASE_URL`.
3. Tables are auto-created by the backend on first boot (`init_db`).

### 2. Render (backend, via `render.yaml` Blueprint)
1. Push this repo to GitHub. Render → New → Blueprint → select repo.
2. Paste secrets: `ALPACA_*`, `REDDIT_*`, `TWITTER_BEARER_TOKEN`, `KALSHI_API_KEY`,
   `DATABASE_URL`, `SUPABASE_*` (mark secrets secret). Redis is provisioned by the blueprint.
3. Deploy → verify `https://<svc>.onrender.com/health` and `/docs`.
4. Note: free tier sleeps when idle (first request slow; WS disconnects on sleep).

### 3. Vercel (frontend)
1. Vercel → New Project → same repo, **Root Directory = `frontend`**.
2. Env var: `NEXT_PUBLIC_API_URL=https://<svc>.onrender.com`, then Deploy.
3. Back in Render, set `CORS_ORIGINS=https://<app>.vercel.app` and redeploy backend.

### 4. Verify production
- `GET /api/feeds/status` shows `live` per configured key.
- Dashboard + `/prediction-bets` (red edges) + `/allocator` load data.
- `GET /api/history` row count grows; `POST /api/allocate` returns a plan.
