# NEXT SESSION — read this first, then CLAUDE.md

Written at the end of the first (cloud) session on 2026-11-11 so the next session
knows exactly what the owner asked for, what was done, and what to do next.

## What the owner told Claude (in their words, summarised)
1. "Check what features can be added to make it much better, what the problems are
   and their solutions — make it a really great idea / startup."
2. "Go on with whatever you are saying but do it faster. Fix all the problems in the
   two tables and the product points. Your recommendation is good, we will do it.
   Do all the core features of version 1 and version 2. Cut or hide whatever you want."
3. "Business model — we'll discuss later, whenever you think is the time."
4. "India-focused version for now — better to test it here."
5. "Do weeks 1–2 but faster than the suggested plan."
6. "Move the whole project from C: to D: to keep C: free" (C: lags when full).
7. "Suggest and put a new name better than QuantPulse AI that suits the idea." → **Parakh**.
8. "Make sure you remember everything from this chat in the new session."
9. "I will NOT push from my PC — I'll tell you to push in the next session."
10. The owner moved the folder to **D:** manually (cut & paste) and will open the next
    session from that D: folder.

## What was done in session 1
- Full review of the old QuantPulse AI repo (problems + solutions + startup features).
- Built the whole Parakh product: backend + frontend + tests + CI + docs.
  Details are in `CLAUDE.md` ("What is built"). 79 backend tests pass; frontend
  type-check + build pass; every page was clicked through in a browser with no errors.
- Commits on branch `claude/project-review-improvements-oz3vbw`:
  `24204ac` backend · `64775ea` frontend/CI/docs/mover · `d404f48` CLAUDE.md · (+ this file).
- **The push to GitHub FAILED** in the cloud (HTTP 403: the Claude GitHub App had no
  access to `ajiteshbakshi27/trading`). The owner received `parakh.bundle` to carry the
  commits to their PC.

## DO THIS FIRST in the next session (owner's explicit instruction)
1. Confirm you are in the D: project folder (e.g. `D:\Parakh\parakh`) and that it is a
   git repo: `git status`.
2. If `backend/app/parakh/` or `CLAUDE.md` is missing, the bundle hasn't been applied.
   Ask the owner where `parakh.bundle` was saved (usually `%USERPROFILE%\Downloads`), then:
   ```
   git fetch <path>\parakh.bundle claude/project-review-improvements-oz3vbw:claude/project-review-improvements-oz3vbw
   git checkout claude/project-review-improvements-oz3vbw
   ```
   If git complains about uncommitted/untracked files, show the owner what they are
   before touching anything — don't delete their files.
3. **Push the branch** (the owner asked Claude to do this):
   `git push -u origin claude/project-review-improvements-oz3vbw`
   Don't open a pull request unless the owner asks.
4. The C:→D: move is already done by the owner, so skip the move script. Optionally
   check that nothing project-related is left on C: (`C:\Users\dellg15\quantpulse-ai`)
   and **ask before deleting** anything.
5. Run it locally and check that **live NSE data** works (Yahoo was blocked in the cloud):
   backend `uvicorn app.main:app --reload --port 8000`, frontend `npm run dev`,
   open http://localhost:3000/check — the report should NOT say "Simulated data".
   Tip for the owner's C: drive: set caches on D:
   `npm config set cache D:\Parakh\.npm-cache`, `pip config set global.cache-dir D:\Parakh\.pip-cache`.

## Then continue (future plan, in order)
1. Help the owner turn on real services per `SETUP.md`: Supabase (auth + DB),
   ANTHROPIC_API_KEY (copilot), Zerodha Kite Connect, Telegram bot, Reddit API;
   deploy backend to Render and frontend to Vercel.
2. Close the known gaps (listed in `CLAUDE.md` → "Open items"): split legacy
   `backend/app/main.py` into routers; remove synthetic evidence from the Labs model
   backtest; confirm F&O lot sizes; WhatsApp alerts (optional).
3. Beta-test with a few Indian traders; collect feedback.
4. When near launch: **raise the business-model discussion** (owner postponed it),
   a SEBI legal review, licensed NSE data, and a trademark/domain check for "Parakh".

## How to work with this owner
- Move fast; act rather than write long plans. Plain, simple language.
- Windows PC; keep everything on D:, not C:.
- Update `CLAUDE.md` (and this file) at the end of each session so memory carries over.
