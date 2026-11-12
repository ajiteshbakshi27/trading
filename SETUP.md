# Parakh — going live (step by step)

Everything below is optional; do it in this order when you're ready.

## 1. Supabase (sign-in + database) — free tier is fine
1. supabase.com → New project (region: Mumbai `ap-south-1`).
2. **Authentication → Providers → Email**: on. Under **URL Configuration** set
   Site URL to your Vercel URL and add `<vercel-url>/login` and
   `<vercel-url>/reset-password` to Redirect URLs.
3. **Project Settings → API**: copy *Project URL* and the *anon public* key.
4. **Project Settings → Database → Connection string (URI)**: copy it.
5. Backend env: `SUPABASE_URL`, `DATABASE_URL`. Frontend env:
   `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`.
   (Only if your project still uses the legacy JWT secret: also set `SUPABASE_JWT_SECRET`.)
   Tables are created automatically on first boot.

## 2. AI model (copilot, idea parsing, autopsy narratives)
Pick one. If both are set, Claude is used.
- **Free:** Google Gemini. aistudio.google.com/apikey → Create API key → set
  `GEMINI_API_KEY` on the backend (`GEMINI_MODEL` defaults to `gemini-3.5-flash-lite`).
  The free tier has daily limits, and Google may use free-tier prompts to improve
  its models, so don't rely on it for private user data at launch.
- **Paid:** Claude. console.anthropic.com → API keys → set `ANTHROPIC_API_KEY`.

Without either, Parakh uses its rule-based parser and copilot.

## 3. Zerodha Kite Connect (trade sync)
1. developers.kite.trade → create an app. Redirect URL:
   `https://<your-vercel-app>/broker/zerodha`.
2. Backend env: `KITE_API_KEY`, `KITE_API_SECRET`, and a `TOKEN_ENCRYPTION_KEY`:
   `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
3. Kite sessions expire every morning and `/trades` returns only today's
   trades, so users import their Console tradebook CSV for history.

## 4. Telegram alerts
@BotFather → `/newbot` → set `TELEGRAM_BOT_TOKEN`. Users paste their chat ID in Settings.

## 5. Reddit (live hype radar)
reddit.com/prefs/apps → create "script" app → `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`.

## 6. Backend on Render
Render → New → Blueprint → this repo (`render.yaml`). Fill every `sync: false`
value, including `CRON_SECRET` (any long random string) and, on the two cron
jobs, `API_URL` = your Render service URL. Set `ENVIRONMENT=production`
(already in the blueprint). In production the server refuses requests until
Supabase is configured.

## 7. Frontend on Vercel
Vercel → New Project → this repo, **Root Directory = `frontend`**. Env:
`NEXT_PUBLIC_API_URL=https://<render-service>.onrender.com`,
`NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`. Then put the
Vercel URL into the backend's `CORS_ORIGINS` and `PUBLIC_APP_URL`.

## 8. Check it
- `GET <api>/api/parakh/me` → `auth_mode: "supabase"` and the features you enabled.
- Sign up, check an idea, upload a tradebook CSV, open Settings → Server features.

## Before a public launch
- Get a lawyer's view on SEBI rules. Parakh is designed as an analysis and
  journaling tool (users test their own ideas; no tips, no recommendations), but
  confirm this before marketing it.
- Market data: Yahoo Finance end-of-day data is fine for a beta. For a
  commercial launch, licence NSE data (e.g. through a broker API or an
  authorised vendor).
