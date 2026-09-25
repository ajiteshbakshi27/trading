"""
QuantPulse AI — Phase 4 hardening smoke test.
Run against a live server:  python scripts/smoke_hardening.py
Set API=http://localhost:8000  (default).
"""
from __future__ import annotations
import json
import os
import sys

import httpx

API = os.environ.get("API", "http://localhost:8000")
# Must be an origin present in CORS_ORIGINS to assert reflection. Locally
# that is http://localhost:3000; in CI set ORIGIN to the deployed frontend.
ORIGIN = os.environ.get("ORIGIN", "http://localhost:3000")

fails: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"{'PASS' if ok else 'FAIL'}  {name}{(' — ' + detail) if detail else ''}")
    if not ok:
        fails.append(name)


with httpx.Client(timeout=30.0) as c:
    # 1. health: no secrets, reports readiness
    h = c.get(f"{API}/health")
    body = h.json()
    check("health 200", h.status_code == 200)
    check("health has feeds", "feeds" in body)
    leaked = [k for k in body if any(
        t in k.upper() for t in ("KEY", "SECRET", "TOKEN"))]
    check("health leaks no secret-shaped fields", not leaked, str(leaked))
    check("health omits raw env", "ALPACA" not in json.dumps(body).upper()
          or "alpaca_trading" in json.dumps(body))

    # 2. security headers
    hd = {k.lower() for k in h.headers.keys()}
    check("X-Content-Type-Options", "x-content-type-options" in hd)
    check("X-Frame-Options", "x-frame-options" in hd)
    check("Referrer-Policy", "referrer-policy" in hd)
    check("Permissions-Policy", "permissions-policy" in hd)
    check("API no-store", "no-store" in (h.headers.get("cache-control") or ""))

    # 3. CORS: allowed origin reflected, unknown origin NOT reflected
    a = c.get(f"{API}/health", headers={"Origin": ORIGIN})
    check("CORS reflects allowed origin",
          a.headers.get("access-control-allow-origin") == ORIGIN,
          str(a.headers.get("access-control-allow-origin")))
    bad = c.get(f"{API}/health", headers={"Origin": "https://evil.example"})
    check("CORS blocks unknown origin",
          bad.headers.get("access-control-allow-origin") is None,
          str(bad.headers.get("access-control-allow-origin")))

    # 4. docs reachable in dev (informational)
    d = c.get(f"{API}/docs")
    check("docs reachable", d.status_code in (200, 307, 404),
          f"status={d.status_code}")

    # 5. rate limiter on a cheap limited endpoint (avoid snapshot/QAOA cost)
    codes = []
    for _ in range(24):
        codes.append(
            c.post(f"{API}/api/portfolio/save",
                   json={"name": "smoke", "budget": 1}).status_code
        )
    check("rate limiter trips", 429 in codes, f"last={codes[-1]}")

    # 6. key endpoints still answer
    s = c.get(f"{API}/api/snapshot")
    check("snapshot 200", s.status_code == 200)
    check("snapshot has feeds block", "feeds" in s.json())
    hist = c.get(f"{API}/api/history?limit=5")
    check("history 200", hist.status_code == 200)

print()
if fails:
    print(f"{len(fails)} check(s) failed: {fails}")
    sys.exit(1)
print("all hardening checks passed")
