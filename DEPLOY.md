# Put Parakh on the internet (free plans)

Two free accounts are needed. You create them yourself; Claude cannot sign up
or type keys for you. Use "Sign in with GitHub" on both, so no new password.

- **Render** runs the backend (the Python server).
- **Vercel** runs the website (the Next.js front end).

Time: about 30 minutes. Do the steps in this order.

## Before you start
Open `backend/.env` in Notepad and keep it open. You will copy values from it.
Never paste these values into a chat, a screenshot or GitHub.

## Step 1 — Backend on Render
1. Go to render.com → **Get Started** → sign in with GitHub.
2. **New** → **Blueprint** → choose the repo `ajiteshbakshi27/trading`.
3. Branch: `claude/project-review-improvements-oz3vbw`.
4. Render reads `render.yaml` and shows one service: `parakh-api` (Free).
5. It asks for values. Copy these from `backend/.env`:

   | Render asks for | Copy from `backend/.env` |
   |---|---|
   | `SUPABASE_URL` | `SUPABASE_URL` |
   | `SUPABASE_ANON_KEY` | `SUPABASE_ANON_KEY` |
   | `DATABASE_URL` | `DATABASE_URL` |
   | `GEMINI_API_KEY` | `GEMINI_API_KEY` |
   | `TOKEN_ENCRYPTION_KEY` | `TOKEN_ENCRYPTION_KEY` |
   | `CRON_SECRET` | `CRON_SECRET` |
   | `ADMIN_EMAILS` | your own email |
   | `PUBLIC_APP_URL` | type `http://localhost:3000` for now (fixed in Step 3) |
   | `CORS_ORIGINS` | type `http://localhost:3000` for now (fixed in Step 3) |
   | everything else | leave empty |

6. Click **Apply**. The first build takes 3 to 6 minutes.
7. When it says **Live**, copy the address at the top. It looks like
   `https://parakh-api.onrender.com`. Open `<that address>/health` in the
   browser. You should see `"status":"ok"` (or similar).

## Step 2 — Website on Vercel
1. Go to vercel.com → sign in with GitHub.
2. **Add New** → **Project** → import `ajiteshbakshi27/trading`.
3. **Root Directory**: click Edit and choose `frontend`. (Important.)
4. Open **Environment Variables** and add three:

   | Name | Value |
   |---|---|
   | `NEXT_PUBLIC_API_URL` | the Render address from Step 1 (no `/` at the end) |
   | `NEXT_PUBLIC_SUPABASE_URL` | copy from `frontend/.env.local` |
   | `NEXT_PUBLIC_SUPABASE_ANON_KEY` | copy from `frontend/.env.local` |

5. Before you click Deploy: Vercel builds the `main` branch by default. In
   **Settings → Git → Production Branch**, set it to
   `claude/project-review-improvements-oz3vbw` (or ask Claude to merge the
   branch into `main` first).
6. Click **Deploy**. Copy the website address, like `https://parakh.vercel.app`.

## Step 3 — Connect the two
1. Render → `parakh-api` → **Environment**. Change both `PUBLIC_APP_URL` and
   `CORS_ORIGINS` to your Vercel address (no `/` at the end). Save. Render
   restarts by itself.
2. Supabase → **Authentication → URL Configuration**:
   - **Site URL** = your Vercel address.
   - **Redirect URLs** → add `<vercel address>/login` and
     `<vercel address>/reset-password`.

## Step 4 — Check it works
Open your Vercel address and try, in order:
1. `/xray` → **Use a sample tradebook** → a report appears.
2. `/try` → click an example → **Check it** → a report with "Live data".
3. `/sample-score` → the chart appears.
4. **Sign up** with your email → confirm the email → log in → Home opens.

If a page says it cannot reach the server, wait one minute and reload. The
free Render server sleeps when nobody uses it, and takes up to a minute to
wake. **Open the site 5 minutes before any demo.**

## Step 5 (optional) — Daily jobs
Open ideas are marked hit or stopped by a daily job. On the free plan this
runs from GitHub:
GitHub → the repo → **Settings → Secrets and variables → Actions → New
repository secret**. Add two:
- `PARAKH_API_URL` = your Render address
- `PARAKH_CRON_SECRET` = the `CRON_SECRET` value from `backend/.env`

GitHub only runs scheduled jobs from the default branch (`main`), so this
starts working after the branch is merged into `main`.

## What the free plans do not give you
- The backend sleeps when idle (slow first load).
- Rate limits and caches reset when the server restarts.
- The free Gemini key has daily limits. Enough for a demo, not for many users.
Move to paid plans only when real users arrive.
