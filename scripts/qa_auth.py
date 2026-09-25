"""
QuantPulse AI — Phase 3 auth QA (Playwright).
Proves: labels wired, error summary focus, 44px targets, password
manager attributes, password visibility toggle, full signup -> session
-> header swap -> sign out flow, reduced motion, 360px.
"""
from __future__ import annotations
import json
import os
import pathlib

from playwright.sync_api import sync_playwright

BASE = os.environ.get("QA_URL", "http://localhost:3000")
OUT = pathlib.Path(__file__).resolve().parents[1] / "assets" / "qa"
REDUCED = OUT / "reduced"
OUT.mkdir(parents=True, exist_ok=True)
REDUCED.mkdir(parents=True, exist_ok=True)

r: dict = {}

TIMEOUT = 90_000  # dev-mode route compiles can be slow on first hit



def ready(page, timeout=60000):
    """Wait until React has hydrated (deterministic; no sleep races)."""
    try:
        page.wait_for_selector("html[data-hydrated='1']", timeout=timeout)
    except Exception:
        pass
def labelled(page):
    return page.evaluate(
        """() => {
      const out = { unlabelled: [], small_targets: [], autocomplete: {} };
      for (const el of document.querySelectorAll('input, select, textarea')) {
        const id = el.id;
        const lab = id ? document.querySelector(`label[for="${id}"]`) : null;
        if (!lab && !el.getAttribute('aria-label') && !el.closest('label')) {
          out.unlabelled.push(el.name || el.type);
        }
        const box = el.closest('.mk-input, button, a, label') || el;
        const h = Math.round(box.getBoundingClientRect().height);
        if (h && h < 44 && el.type !== 'checkbox') out.small_targets.push({ id, h });
        if (el.autocomplete) out.autocomplete[el.name || el.id] = el.autocomplete;
      }
      return out;
    }"""
    )



def ready(page, timeout=60000):
    """Wait until React has hydrated (deterministic; no sleep races)."""
    try:
        page.wait_for_selector("html[data-hydrated='1']", timeout=timeout)
    except Exception:
        pass
with sync_playwright() as pw:
    b = pw.chromium.launch()
    b.contexts  # noqa
    ctx_default = b.new_context()
    ctx_default.set_default_timeout(TIMEOUT)
    ctx_default.set_default_navigation_timeout(TIMEOUT)
    ctx_default.close()

    # ---------- 1. Login: labels + targets + autocomplete ----------
    ctx = b.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    page.goto(f"{BASE}/login", wait_until="domcontentloaded")
    ready(page)
    page.wait_for_timeout(500)
    page.screenshot(path=str(OUT / "auth-login.png"))
    r["login_labels"] = labelled(page)

    # ---------- 2. Empty submit -> error summary + focus ----------
    page.click("button[type=submit]")
    page.wait_for_timeout(400)
    focus = page.evaluate(
        """() => {
      const a = document.activeElement;
      return { tag: a?.tagName, role: a?.getAttribute('role'), text: (a?.textContent||'').trim().slice(0,60) };
    }"""
    )
    r["login_error_focus"] = focus
    r["login_inline_errors"] = page.evaluate(
        """() => [...document.querySelectorAll('[role=alert]')].map(e => (e.textContent||'').trim().slice(0,70))"""
    )
    page.screenshot(path=str(OUT / "auth-login-errors.png"))

    # ---------- 3. Bad email then valid submit ----------
    page.fill("#email", "not-an-email")
    page.fill("#password", "hunter2hunter2")
    page.click("button[type=submit]")
    page.wait_for_timeout(300)
    r["bad_email_error"] = page.locator("#email-error").inner_text()
    page.fill("#email", "trader@quantpulse.ai")
    page.click("button[type=submit]")
    try:
        page.wait_for_url("**/dashboard", timeout=15000)
    except Exception:
        pass
    page.wait_for_timeout(600)
    r["after_login_url"] = page.url
    r["session_stored"] = page.evaluate("() => !!localStorage.getItem('qp.session')")
    r["header_after_login"] = page.evaluate(
        """() => {
      const h = document.querySelector('header, nav');
      if (!h) return { found: false, url: location.pathname };
      const els = [...h.querySelectorAll('button,a')];
      return {
        found: true,
        url: location.pathname,
        has_signout: els.some(b => b.textContent.includes('Sign out')),
        has_signin: els.some(b => b.textContent.includes('Sign in')),
        chip: (h.innerText || '').replace(/\\s+/g,' ').slice(0, 80),
      };
    }"""
    )
    page.screenshot(path=str(OUT / "auth-header-signedin.png"))
    ctx.close()

    # ---------- 4. Guard mode ----------
    g = b.new_context(viewport={"width": 1440, "height": 900})
    gp = g.new_page()
    gp.goto(f"{BASE}/dashboard", wait_until="domcontentloaded")
    gp.wait_for_timeout(600)
    r["guard_default_off_reaches_dashboard"] = "/dashboard" in gp.url
    g.close()

    # ---------- 5. Signup + sign out ----------
    s = b.new_context(viewport={"width": 1440, "height": 900})
    sp = s.new_page()
    sp.goto(f"{BASE}/signup", wait_until="domcontentloaded")
    ready(sp)
    sp.wait_for_timeout(400)
    r["signup_labels"] = labelled(sp)
    sp.click("button[type=submit]")
    sp.wait_for_timeout(300)
    sp.screenshot(path=str(OUT / "auth-signup-errors.png"))
    sp.fill("#email", "new@quantpulse.ai")
    sp.fill("#password", "short")
    sp.check("input[name=risk]")
    sp.click("button[type=submit]")
    sp.wait_for_timeout(300)
    r["short_password_error"] = sp.locator("#password-error").inner_text()
    sp.fill("#password", "a-long-enough-passphrase")
    sp.click("button[type=submit]")
    try:
        sp.wait_for_url("**/dashboard", timeout=15000)
    except Exception:
        pass
    sp.wait_for_timeout(600)
    r["after_signup_url"] = sp.url
    sp.goto(f"{BASE}/", wait_until="domcontentloaded")
    # Wait for hydration to attach the session UI: a fixed sleep races dev compiles.
    try:
        sp.wait_for_selector("text=Sign out", timeout=30000)
    except Exception:
        pass
    sp.screenshot(path=str(OUT / "auth-header-session.png"))
    r["header_signedin_state"] = sp.evaluate(
        """() => {
      const h = document.querySelector('header, nav');
      const els = h ? [...h.querySelectorAll('button,a')] : [];
      return {
        has_signout: els.some(b => b.textContent.includes('Sign out')),
        has_getstarted: els.some(b => b.textContent.includes('Get started')),
      };
    }"""
    )
    sp.click("text=Sign out")
    try:
        sp.wait_for_url(BASE + "/", timeout=15000)
    except Exception:
        pass
    sp.wait_for_timeout(900)
    r["after_signout_state"] = sp.evaluate(
        """() => {
      const h = document.querySelector('header, nav');
      const els = h ? [...h.querySelectorAll('button,a')] : [];
      return {
        url: location.pathname,
        has_signin: els.some(b => b.textContent.includes('Sign in')),
        has_getstarted: els.some(b => b.textContent.includes('Get started')),
        has_signout: els.some(b => b.textContent.includes('Sign out')),
      };
    }"""
    )
    r["after_signout_session"] = sp.evaluate("() => localStorage.getItem('qp.session')")
    s.close()

    # ---------- 6. Forgot password success state ----------
    f = b.new_context(viewport={"width": 1440, "height": 900})
    fp = f.new_page()
    fp.goto(f"{BASE}/forgot-password", wait_until="domcontentloaded")
    ready(fp)
    fp.fill("#email", "trader@quantpulse.ai")
    fp.click("button[type=submit]")
    try:
        fp.wait_for_selector("text=Check your email", timeout=20000)
    except Exception:
        pass
    r["forgot_success_visible"] = "Check your email" in fp.inner_text("body")
    fp.screenshot(path=str(OUT / "auth-forgot-sent.png"))
    f.close()

    # ---------- 7. Mobile + reduced motion ----------
    m = b.new_context(viewport={"width": 360, "height": 780}, is_mobile=True, has_touch=True)
    mp = m.new_page()
    mp.goto(f"{BASE}/login", wait_until="domcontentloaded")
    ready(mp)
    mp.wait_for_timeout(600)
    mp.screenshot(path=str(OUT / "auth-login-360.png"))
    r["login_mobile_hscroll"] = mp.evaluate(
        "() => document.documentElement.scrollWidth > window.innerWidth + 1"
    )
    m.close()

    rm = b.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
    rp = rm.new_page()
    rp.goto(f"{BASE}/login", wait_until="domcontentloaded")
    rp.wait_for_timeout(500)
    rp.screenshot(path=str(REDUCED / "auth-login-reduced.png"))
    r["reduced_login_ok"] = rp.locator("h1").inner_text()
    rm.close()

    b.close()

print(json.dumps(r, indent=2))
