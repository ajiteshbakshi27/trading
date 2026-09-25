"""
QuantPulse AI — verify the live tick WebSocket actually connects under CSP.
Run:  python scripts/check_ws.py
"""
from __future__ import annotations
import json
import os

from playwright.sync_api import sync_playwright

FRONT = os.environ.get("FRONT", "http://localhost:3000")
API = os.environ.get("API", "http://localhost:8000")

with sync_playwright() as pw:
    b = pw.chromium.launch()
    page = b.new_page(viewport={"width": 1440, "height": 900})
    page.set_default_timeout(90_000)

    console: list[str] = []
    page.on("console", lambda m: console.append(f"{m.type}: {m.text[:180]}"))
    page.on("pageerror", lambda e: console.append(f"PAGEERROR: {str(e)[:180]}"))

    page.goto(f"{FRONT}/dashboard", wait_until="domcontentloaded")
    page.wait_for_timeout(6000)

    csp_violations = [c for c in console if "Content Security Policy" in c]
    ws_connected = page.evaluate(
        """() => {
      // The navbar badge flips to LIVE only after the socket opens.
      const nav = document.querySelector('nav');
      return nav ? nav.innerText.includes('LIVE') : false;
    }"""
    )
    killed = [c for c in console if "error" in c.lower() and "favicon" not in c.lower()]

    print(json.dumps({
        "page": "/dashboard",
        "ws_connected_badge": ws_connected,
        "csp_violations": csp_violations,
        "other_errors": killed[:5],
        "console_sample": console[:6],
    }, indent=2))
    b.close()
