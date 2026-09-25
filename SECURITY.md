# Security notes — QuantPulse AI

## Rotate any key that has been pasted into a chat, commit, or log

Two credentials have been handled in plaintext in this project's chat history.
Treat both as **compromised** and rotate before deploying:

| Credential | Where it was exposed | Action |
|---|---|---|
| `ALPACA_SECRET_KEY` (value pasted in chat) | OpenCode conversation, `backend/.env` | Revoke in Alpaca → API Keys → delete the pair, issue a new one. The key ID currently in `.env` does not pair with it (stream auth fails with `402 auth failed`). |
| `FINANCIAL_DATA_API_KEY` (Alpha Vantage) | `backend/.env` | Rotate if this repo ever becomes public. Free tier, low blast radius. |

Rules that follow from this:
- Never commit `.env`. `.gitignore` covers `.env`, `.env.*` (except `.env.example`), `*.pem`, `*.key`.
- Secrets live only in the hosting provider's env vars (Render dashboard / Vercel project settings), never in the repo.
- Frontend code must never import a secret. Only `NEXT_PUBLIC_*` values reach the browser, and those are public by definition.

## What is already enforced in code

- **CORS is an explicit allowlist.** `CORS_ORIGINS` (comma-separated or JSON) is the only source. A wildcard is never combined with credentials.
- **Rate limiting** on `/api/allocate`, `/api/trade`, `/api/kill-switch`, `/api/copilot`, `/api/portfolio*`: 20 requests/minute per IP, in-process (single worker by design).
- **Security headers** on every response: `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`. `Cache-Control: no-store` on `/api/*` and `/health`.
- **`/health` never returns secrets** — only `live`/`mock` feed flags, environment, db backend, halt state.
- **Frontend CSP** via `next.config.js` headers, `frame-ancestors 'none'`, `poweredByHeader: false`, no production source maps.

## Known limitations (be honest about these in production)

1. **Auth is a demo.** `/login` issues a fake JWT in `localStorage`. It is not authentication. Set `NEXT_PUBLIC_REQUIRE_AUTH=1` to at least gate the app routes, but real protection requires a server-side IdP and token verification.
2. **Rate limiting is in-process.** Multiple workers or multiple instances each keep their own buckets. Use Redis (already a Render service in `render.yaml`) for shared limits.
3. **No API authentication.** Anyone who can reach the backend can call `/api/trade` (it will route to the paper account if keys exist). Put the API behind an auth proxy or add a shared-secret check before real-money use.
4. **Paper-only by default.** `ALPACA_BASE_URL` must stay `https://paper-api.alpaca.markets`. The kill switch is a safety net, not a guarantee: orders can be rejected or partially filled.
5. **`/docs` is public** when the app is running. Disable by setting `ENVIRONMENT=production` and guarding the docs route, or accept it for a demo deployment.

## Pre-deploy checklist

```powershell
# backend tests
cd quantpulse-ai/backend
python -m py_compile app/main.py app/config.py app/database.py

# hardening smoke (server must be running)
python ../scripts/smoke_hardening.py

# frontend
cd ../frontend
node scripts/validate-tokens.cjs
npm run build
```

Then: Render Blueprint → paste env vars → verify `/health` → Vercel with
`NEXT_PUBLIC_API_URL` → set `CORS_ORIGINS` to the Vercel origin → re-verify.
