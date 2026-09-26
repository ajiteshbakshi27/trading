"""
Capture screenshots of all QuantPulse pages for the presentation.
Run with both servers up:  python scripts/capture_screenshots.py
"""
from __future__ import annotations

import os
from playwright.sync_api import sync_playwright

PAGES = [
    ("01-landing", "/"),
    ("02-dashboard", "/dashboard"),
    ("03-information-flow", "/information-flow"),
    ("04-thesis-lab", "/thesis-lab"),
    ("05-model-autopsy", "/model-autopsy"),
    ("06-research-lab", "/research-lab"),
    ("07-backtest", "/backtest"),
    ("08-portfolio", "/portfolio"),
    ("09-demo", "/demo"),
    ("10-allocator", "/allocator"),
    ("11-charts", "/charts"),
    ("12-prediction-bets", "/prediction-bets"),
    ("13-hft-orderbook", "/hft-orderbook"),
    ("14-quantum-analytics", "/quantum-analytics"),
]

OUT = os.path.join(os.path.dirname(__file__), "..", "assets", "presentation")


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        for name, path in PAGES:
            try:
                page.goto(f"http://localhost:3000{path}", wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(3000)
                page.screenshot(path=os.path.join(OUT, f"{name}.png"), full_page=False)
                print(f"  captured {name}")
            except Exception as e:
                print(f"  FAILED {name}: {e}")
        browser.close()
    print(f"\nScreenshots saved to {os.path.abspath(OUT)}")


if __name__ == "__main__":
    main()
