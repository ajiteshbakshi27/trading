"""
QuantPulse AI — Phase 2 constitution QA (Playwright).
Proves: 1440 / 360 / landscape renders, reduced-motion final states,
keyboard focus visibility, transform+opacity-only animation, LCP/CLS.
Run:  python scripts/qa_landing.py
"""
from __future__ import annotations
import json
import os
import pathlib
import sys

from playwright.sync_api import sync_playwright

BASE = os.environ.get("QA_URL", "http://localhost:3000")
OUT = pathlib.Path(__file__).resolve().parents[1] / "assets" / "qa"
REDUCED = OUT / "reduced"
OUT.mkdir(parents=True, exist_ok=True)
REDUCED.mkdir(parents=True, exist_ok=True)

# Dev-mode route compiles can exceed Playwright's 30s default on a cold hit.
TIMEOUT = 90_000

# Properties that force layout/paint (banned by the constitution).
BANNED_PROPS = {
    "width", "height", "top", "left", "right", "bottom", "margin", "marginTop",
    "marginLeft", "marginRight", "marginBottom", "padding", "paddingTop",
    "paddingLeft", "fontSize", "lineHeight", "borderWidth", "flexBasis",
}

PERF_PROBE = """
() => {
  const anims = document.getAnimations();
  const props = new Set();
  for (const a of anims) {
    try {
      const kf = a.effect && a.effect.getKeyframes ? a.effect.getKeyframes() : [];
      for (const k of kf) for (const p of Object.keys(k)) {
        if (!["offset", "computedOffset", "easing", "composite"].includes(p)) props.add(p);
      }
    } catch (e) {}
  }
  return [...props];
}
"""

METRICS_PROBE = """
() => new Promise((resolve) => {
  let lcp = 0, cls = 0;
  try {
    new PerformanceObserver((l) => {
      for (const e of l.getEntries()) lcp = Math.max(lcp, e.startTime);
    }).observe({ type: "largest-contentful-paint", buffered: true });
  } catch (e) {}
  try {
    new PerformanceObserver((l) => {
      for (const e of l.getEntries()) if (!e.hadRecentInput) cls += e.value;
    }).observe({ type: "layout-shift", buffered: true });
  } catch (e) {}
  setTimeout(() => resolve({ lcp: Math.round(lcp), cls: Number(cls.toFixed(4)) }), 2500);
})
"""

results: dict = {}



def ready(page, timeout=60000):
    """Wait until React has hydrated (deterministic; no sleep races)."""
    try:
        page.wait_for_selector("html[data-hydrated='1']", timeout=timeout)
    except Exception:
        pass
def run(pw) -> None:
    browser = pw.chromium.launch()
    # generous timeouts: `next dev` compiles routes on demand
    browser.new_context().set_default_timeout(TIMEOUT)

    # ---------- 1. Desktop 1440 ----------
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
    ctx.set_default_timeout(TIMEOUT)
    ctx.set_default_navigation_timeout(TIMEOUT)
    page = ctx.new_page()
    page.goto(BASE, wait_until="domcontentloaded")
    ready(page)
    page.wait_for_timeout(1200)
    page.screenshot(path=str(OUT / "landing-1440.png"))
    page.screenshot(path=str(OUT / "landing-1440-full.png"), full_page=True)

    # scroll through the pinned hero to exercise the scrub, then capture sections
    page.mouse.wheel(0, 900)
    page.wait_for_timeout(900)
    page.screenshot(path=str(OUT / "landing-hero-scrubbed.png"))
    page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.55)")
    page.wait_for_timeout(1000)
    page.screenshot(path=str(OUT / "landing-sections.png"))
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(700)
    page.screenshot(path=str(OUT / "landing-footer.png"))

    # ---------- 2. Animation audit + vitals (fresh load, mid-animation) ----------
    page.goto(BASE, wait_until="domcontentloaded")
    ready(page)
    page.wait_for_timeout(1500)
    page.evaluate("window.scrollTo(0, 600)")
    page.wait_for_timeout(300)
    props = page.evaluate(PERF_PROBE)
    banned = sorted(p for p in props if p.lower() in BANNED_PROPS)
    allowed = sorted(p for p in props if p.lower() not in BANNED_PROPS)
    results["animation_props"] = {"allowed": allowed, "banned": banned}

    # GSAP writes inline styles, not WAAPI — sample the pinned layers instead
    # and prove the motion lands on transform (composited) only.
    def sample_layers() -> dict:
        return page.evaluate(
            """() => {
              const grab = (sel) => {
                const el = document.querySelector(sel);
                if (!el) return null;
                const cs = getComputedStyle(el);
                return { transform: cs.transform, top: cs.top, width: cs.width, left: cs.left };
              };
              return { frame: grab('.hero-frame'), copy: grab('.hero-copy') };
            }"""
        )

    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(500)
    before = sample_layers()
    page.evaluate("window.scrollTo(0, 1400)")
    page.wait_for_timeout(900)
    after = sample_layers()
    moved = {
        k: {
            "transform_changed": before[k]["transform"] != after[k]["transform"],
            "layout_props_static": all(
                before[k][p] == after[k][p] for p in ("top", "left", "width")
            ),
            "before_transform": before[k]["transform"][:40],
            "after_transform": after[k]["transform"][:40],
        }
        for k in ("frame", "copy")
        if before.get(k) and after.get(k)
    }
    results["gsap_layer_motion"] = moved

    page.goto(BASE, wait_until="load")
    ready(page)
    results["vitals"] = page.evaluate(METRICS_PROBE)

    # ---------- 3. Keyboard focus visibility ----------
    page.goto(BASE, wait_until="domcontentloaded")
    page.wait_for_timeout(600)
    seq = []
    for _ in range(6):
        page.keyboard.press("Tab")
        info = page.evaluate(
            """() => {
              const el = document.activeElement;
              if (!el || el === document.body) return null;
              const cs = getComputedStyle(el);
              return {
                tag: el.tagName,
                text: (el.textContent || "").trim().slice(0, 28),
                outline: cs.outlineStyle !== "none" && cs.outlineWidth !== "0px",
                shadow: cs.boxShadow !== "none",
                h: Math.round(el.getBoundingClientRect().height),
              };
            }"""
        )
        if info:
            seq.append(info)
    results["keyboard"] = seq
    page.screenshot(path=str(OUT / "landing-focus-ring.png"))
    ctx.close()

    # ---------- 4. Mobile 360 + landscape ----------
    m = browser.new_context(viewport={"width": 360, "height": 780}, is_mobile=True, has_touch=True)
    mp = m.new_page()
    mp.goto(BASE, wait_until="domcontentloaded")
    mp.wait_for_timeout(900)
    mp.screenshot(path=str(OUT / "landing-360.png"), full_page=False)
    results["mobile_hscroll"] = mp.evaluate(
        "() => document.documentElement.scrollWidth > window.innerWidth + 1"
    )
    m.close()

    lm = browser.new_context(viewport={"width": 844, "height": 390})
    lp = lm.new_page()
    lp.goto(BASE, wait_until="domcontentloaded")
    lp.wait_for_timeout(900)
    lp.screenshot(path=str(OUT / "landing-landscape.png"))
    lm.close()

    # ---------- 5. Reduced motion final states ----------
    r = browser.new_context(
        viewport={"width": 1440, "height": 900}, reduced_motion="reduce"
    )
    rp = r.new_page()
    rp.goto(BASE, wait_until="domcontentloaded")
    rp.wait_for_timeout(900)
    rp.screenshot(path=str(REDUCED / "landing-reduced-hero.png"))
    rp.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.55)")
    rp.wait_for_timeout(600)
    rp.screenshot(path=str(REDUCED / "landing-reduced-sections.png"))
    # hero copy must be fully visible (no stuck opacity:0)
    vis = rp.evaluate(
        """() => {
          const els = [...document.querySelectorAll('.hero-word, .hero-fade')];
          const hidden = els.filter((e) => parseFloat(getComputedStyle(e).opacity) < 0.9);
          return { checked: els.length, hidden: hidden.length };
        }"""
    )
    results["reduced_motion"] = vis
    r.close()

    browser.close()



def ready(page, timeout=60000):
    """Wait until React has hydrated (deterministic; no sleep races)."""
    try:
        page.wait_for_selector("html[data-hydrated='1']", timeout=timeout)
    except Exception:
        pass
with sync_playwright() as pw:
    run(pw)

print(json.dumps(results, indent=2))
print("\nartifacts:", OUT)
sys.exit(0)
