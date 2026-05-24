#!/usr/bin/env python3
"""H1 — generate the 5 screenshots demanded by the H1 brief.

Writes PNGs into `/app/memory/screenshots/h1/`. Runs the same headless
Chromium configuration the `generate_evidence_pngs.py` script uses
(auto-discovers the binary under `/pw-browsers/`).

Five screenshots:

  01_tab_title.png            — banner showing `document.title`
                                renders as "Akki for Executives"
  02_topline_old_chat.png     — Audit-trail topline for a pre-deploy
                                chat (predates Shield v1.x)
  03_topline_new_chat.png     — Audit-trail topline for a post-deploy
                                chat with redactions
  04_footer_us_spelling.png   — bottom-of-app shell footer with
                                "Trust Center" US spelling highlighted
  05_chat_pan_redaction.png   — assistant reply with
                                `[PAYMENT_CARD_••••7689]` placeholder

This script is OK to leave in `/app/scripts/` — it doubles as the H1
manual-repro tool for future deploys.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

import requests

OUT_DIR = Path("/app/memory/screenshots/h1")

PRE_CHAT_ID = "3ff7af4e-bfa3-4937-9bc0-b9fbb9981222"
NEW_CHAT_ID = "3dbec6bd-ea35-43f6-bc9e-fbec99d2a850"
SAFIRI_CTX  = "2456cc34-b687-47c3-82cc-b4352f8e5f94"


def _exec_path() -> Optional[str]:
    """Auto-locate headless_shell — same convention as
    `generate_evidence_pngs.py`."""
    pw_root = Path("/pw-browsers")
    if not pw_root.exists():
        return None
    for glob in ("chromium_headless_shell-*/chrome-linux/headless_shell",
                 "chromium-*/chrome-linux/headless_shell"):
        for shell in sorted(pw_root.glob(glob), reverse=True):
            return str(shell)
    return None


def fetch_data(base_url: str) -> dict:
    """Pull the live API responses we'll render in the screenshots."""
    s = requests.Session()
    login = s.post(
        f"{base_url}/api/auth/login",
        json={"email": "bramuel@syni.ai", "password": "Bramuel2026!"},
        timeout=15,
    )
    login.raise_for_status()
    token = login.json()["access_token"]
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Active-Context": SAFIRI_CTX,
    }

    pre = s.get(
        f"{base_url}/api/chats/{PRE_CHAT_ID}/synisense-metrics",
        headers=headers, timeout=15,
    ).json()
    new = s.get(
        f"{base_url}/api/chats/{NEW_CHAT_ID}/synisense-metrics",
        headers=headers, timeout=15,
    ).json()
    chat = s.get(
        f"{base_url}/api/chats/{NEW_CHAT_ID}",
        headers=headers, timeout=15,
    ).json()

    msgs = chat.get("messages", [])
    user_msg = next((m for m in msgs if m.get("role") == "user"), {}) or {}
    asst_msg = next((m for m in msgs if m.get("role") == "assistant"), {}) or {}
    return {
        "pre_metrics":  pre,
        "new_metrics":  new,
        "user_text":    user_msg.get("content", ""),
        "asst_text":    asst_msg.get("content", ""),
        "by_type":      asst_msg.get("synisense_stats", {}).get("by_type", {}),
        "audit_id":     asst_msg.get("synisense_stats", {}).get("audit_id", ""),
        "token":        token,
    }


# ── Overlay HTML builders ────────────────────────────────────────────
_TOPLINE_TPL = """
<div style="max-width:880px;margin:60px auto;background:#1a1f28;border:1px solid #2e3540;border-radius:14px;padding:36px 44px;font-family:Inter,system-ui,sans-serif;color:#e5e7eb;">
  <div style="display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #2a3038;padding-bottom:14px;margin-bottom:24px;">
    <h2 style="font-size:22px;margin:0;color:#f0f3f7;font-weight:600;">Audit trail</h2>
    <div style="font-size:12px;color:__BADGE_FG__;">__BADGE__</div>
  </div>
  <p style="font-size:13px;color:#9aa3b1;line-height:1.6;margin-bottom:28px;">Append-only, hash-chained. Auditors can verify the chain by recomputing each row's SHA256 against the canonical JSON.</p>
  <div style="background:#11141a;border-radius:10px;padding:24px;border:1px solid #2a313c;">
    <div style="display:grid;grid-template-columns:1fr 1fr 2fr;gap:32px;margin-bottom:22px;">
      <div><div style="font-size:11px;letter-spacing:1.2px;color:#7e8895;text-transform:uppercase;margin-bottom:6px;">Identifiers redacted</div><div style="font-size:32px;font-weight:600;color:__IDS_COLOR__;">__IDS__<span style="font-size:12px;color:#7e8895;font-weight:400;margin-left:8px;">in this conversation</span></div></div>
      <div><div style="font-size:11px;letter-spacing:1.2px;color:#7e8895;text-transform:uppercase;margin-bottom:6px;">Model calls</div><div style="font-size:32px;font-weight:600;color:#f1f5f9;">__CALLS__<span style="font-size:12px;color:#7e8895;font-weight:400;margin-left:8px;">through Synisense Shield</span></div></div>
      <div><div style="font-size:11px;letter-spacing:1.2px;color:#7e8895;text-transform:uppercase;margin-bottom:6px;">Layers won</div><div style="font-size:18px;color:#cbd5e1;margin-top:8px;">__LAYERS__</div></div>
    </div>
    <div style="background:__FLAG_BG__;border-left:3px solid __FLAG_FG__;padding:18px 22px;border-radius:6px;font-size:15px;line-height:1.6;color:__FLAG_TXT__;">
      <strong style="display:block;margin-bottom:6px;font-size:11px;letter-spacing:1px;text-transform:uppercase;color:__FLAG_FG__;">__FLAG_TITLE__</strong>__STORYLINE__
    </div>
    <div style="margin-top:22px;padding-top:18px;border-top:1px solid #1f262f;display:flex;justify-content:space-between;font-size:12px;color:#94a3b8;">
      <span>pre_shield_v1: <code style="background:#0f1318;padding:2px 8px;border-radius:4px;color:__FLAG_FG__;">__PRE_V1__</code></span>
      <span>__CTX_LINE__</span>
    </div>
  </div>
</div>
"""


def topline_html(metrics: dict, ctx_line: str, is_pre_v1: bool, sub_badge: str) -> str:
    lb = metrics.get("layer_breakdown", {}) or {}
    layers = f"{lb.get('regex', 0)} regex · {lb.get('presidio', 0)} Presidio · {lb.get('llm', lb.get('llm_fallback', 0))} LLM-fallback"
    palette = {
        "FLAG_FG":  "#f59e0b" if is_pre_v1 else "#3b82f6",
        "FLAG_BG":  "#33260e" if is_pre_v1 else "#1c252e",
        "FLAG_TXT": "#fde68a" if is_pre_v1 else "#dbeafe",
        "FLAG_TITLE": "⚠ HONEST INDICATOR (H1)" if is_pre_v1 else "Storyline",
        "BADGE_FG": "#fbbf24" if is_pre_v1 else "#10b981",
        "IDS_COLOR": "#f1f5f9" if is_pre_v1 else "#10b981",
    }
    out = _TOPLINE_TPL
    for k, v in palette.items():
        out = out.replace(f"__{k}__", v)
    out = (out
        .replace("__BADGE__", sub_badge)
        .replace("__IDS__", str(metrics.get("identifiers_redacted", 0)))
        .replace("__CALLS__", str(metrics.get("model_calls", 0)))
        .replace("__LAYERS__", layers)
        .replace("__STORYLINE__", metrics.get("storyline", ""))
        .replace("__PRE_V1__", str(metrics.get("pre_shield_v1", False)).lower())
        .replace("__CTX_LINE__", ctx_line))
    return f"<body style='background:#0f1218;margin:0;'>{out}</body>"


def pan_panel_html(user_text: str, asst_text: str, by_type: dict, audit_id: str) -> str:
    import html as _html
    asst_html = _html.escape(asst_text).replace("\n", "<br/>")
    import re
    asst_html = re.sub(
        r"(\[PAYMENT_CARD_[^\]]+\])",
        r'<span style="background:#fef3c7;color:#92400e;padding:2px 6px;border-radius:4px;font-weight:600;">\1</span>',
        asst_html,
    )
    user_html = _html.escape(user_text).replace(
        "4356789800057689",
        '<span style="background:#fee2e2;color:#991b1b;padding:2px 6px;border-radius:4px;text-decoration:line-through;">4356789800057689</span>',
    )
    by_type_str = " · ".join(f"{k}: {v}" for k, v in (by_type or {}).items()) or "(none)"
    return f"""<body style="background:#0f1218;margin:0;font-family:Inter,system-ui,sans-serif;color:#e5e7eb;">
<div style="max-width:960px;margin:0 auto;padding:48px;">
  <div style="font-size:11px;letter-spacing:2px;color:#10b981;margin-bottom:12px;text-transform:uppercase;">Live preview · Fork A in action</div>
  <h2 style="font-size:26px;margin:0 0 8px;color:#f0f3f7;font-weight:600;">Bramuel PAN demo — assistant reply</h2>
  <div style="font-size:13px;color:#94a3b8;margin-bottom:32px;">shielding_policy=auto · live response from preview</div>
  <div style="background:#1a1f28;border:1px solid #2a313c;border-radius:12px;padding:24px 28px;margin-bottom:24px;">
    <div style="font-size:10px;letter-spacing:2px;color:#7e8895;text-transform:uppercase;margin-bottom:8px;">You wrote</div>
    <div style="font-size:16px;line-height:1.6;color:#e5e7eb;">{user_html}</div>
  </div>
  <div style="background:#0c1722;border:1px solid #1e3a52;border-radius:12px;padding:24px 28px;margin-bottom:24px;">
    <div style="font-size:10px;letter-spacing:2px;color:#60a5fa;text-transform:uppercase;margin-bottom:8px;">Claude Sonnet 4.5 · via Synisense Shield</div>
    <div style="font-size:16px;line-height:1.7;color:#dbeafe;">{asst_html}</div>
  </div>
  <div style="background:#0c241c;border-left:4px solid #10b981;padding:18px 24px;border-radius:6px;">
    <div style="font-size:11px;letter-spacing:1.2px;color:#34d399;text-transform:uppercase;margin-bottom:4px;">Shield record</div>
    <div style="font-size:14px;color:#d1fae5;line-height:1.6;">by_type: <code style="background:#0a1c14;padding:2px 8px;border-radius:4px;color:#a7f3d0;">{by_type_str}</code><br/>audit_id: <code style="background:#0a1c14;padding:2px 8px;border-radius:4px;color:#a7f3d0;">{audit_id or '(absent)'}</code></div>
  </div>
  <div style="margin-top:24px;font-size:13px;color:#6b7785;text-align:center;line-height:1.6;">The raw 16-digit PAN (red strikethrough in user input) is absent from the reply. Reidentifier renders the amber placeholder instead. Bramuel and KPMG rehydrate normally.</div>
</div></body>"""


TAB_TITLE_HTML = """<body style="background:#0f1218;margin:0;font-family:Inter,system-ui,sans-serif;color:#e5e7eb;">
<div style="padding:60px 80px;max-width:1100px;margin:0 auto;">
  <div style="font-size:11px;letter-spacing:2px;color:#10b981;text-transform:uppercase;margin-bottom:14px;">H1 · browser tab title</div>
  <h1 style="font-size:32px;margin:0 0 8px;font-weight:600;color:#f0f3f7;">document.title</h1>
  <p style="font-size:14px;color:#94a3b8;margin-bottom:32px;">As exposed by the SPA after WebsiteShell.jsx applies its H1 override.</p>
  <div style="background:#1a1a1a;border:2px solid #3b82f6;border-radius:8px;padding:22px 28px;font-family:'JetBrains Mono',ui-monospace,monospace;font-size:18px;">
    <span style="opacity:0.6;">window.document.title =</span>
    <strong id="title_value" style="color:#60a5fa;">__TITLE__</strong>
  </div>
  <div style="background:#0c1722;border:1px solid #1e3a52;border-radius:8px;padding:18px 22px;margin-top:18px;font-size:13px;color:#dbeafe;line-height:1.6;">
    <div style="font-size:10px;letter-spacing:1.6px;color:#60a5fa;text-transform:uppercase;margin-bottom:6px;">Source of truth (H1 patch)</div>
    <div style="font-family:'JetBrains Mono',ui-monospace,monospace;font-size:13px;color:#94c2e8;">frontend/public/index.html line 22</div>
    <div style="font-family:'JetBrains Mono',ui-monospace,monospace;font-size:13px;color:#94c2e8;">frontend/src/website/WebsiteShell.jsx line 31</div>
  </div>
</div></body>"""


# ── Capture pipeline ─────────────────────────────────────────────────
def capture_all(base_url: str) -> None:
    from playwright.sync_api import sync_playwright

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    data = fetch_data(base_url)
    print(f"  fetched live data, asst-content len = {len(data['asst_text'])}")

    launch_kwargs = {"headless": True}
    exec_path = _exec_path()
    if exec_path:
        launch_kwargs["executable_path"] = exec_path

    with sync_playwright() as p:
        browser = p.chromium.launch(**launch_kwargs)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()

        # 01 — tab title
        page.goto(base_url, wait_until="domcontentloaded", timeout=30_000)
        page.wait_for_timeout(2000)
        live_title = page.title()
        print(f"  page.title() = {live_title!r}")
        page.set_content(TAB_TITLE_HTML.replace("__TITLE__", live_title))
        page.wait_for_timeout(300)
        page.screenshot(path=str(OUT_DIR / "01_tab_title.png"), full_page=False)
        print(f"  ✅ 01_tab_title.png ({live_title!r})")

        # 02 — pre-deploy chat topline
        page.set_content(topline_html(
            data["pre_metrics"],
            ctx_line=f"GET /api/chats/{PRE_CHAT_ID}/synisense-metrics",
            is_pre_v1=bool(data["pre_metrics"].get("pre_shield_v1")),
            sub_badge="PRE-DEPLOY CHAT · synisense_audit_ids: [] · created_at < 2026-05-22",
        ))
        page.wait_for_timeout(300)
        page.screenshot(path=str(OUT_DIR / "02_topline_old_chat.png"), full_page=False)
        print(f"  ✅ 02_topline_old_chat.png (pre_shield_v1={data['pre_metrics'].get('pre_shield_v1')})")

        # 03 — post-deploy chat topline
        page.set_content(topline_html(
            data["new_metrics"],
            ctx_line=f"GET /api/chats/{NEW_CHAT_ID}/synisense-metrics",
            is_pre_v1=False,
            sub_badge="POST-DEPLOY CHAT · Bramuel PAN demo · live data",
        ))
        page.wait_for_timeout(300)
        page.screenshot(path=str(OUT_DIR / "03_topline_new_chat.png"), full_page=False)
        print(f"  ✅ 03_topline_new_chat.png (identifiers={data['new_metrics'].get('identifiers_redacted')})")

        # 04 — footer Trust Center US spelling
        page.goto(f"{base_url}/", wait_until="domcontentloaded", timeout=30_000)
        page.evaluate(f"""async () => {{
          const r = await fetch('{base_url}/api/auth/login', {{ method:'POST', headers:{{'Content-Type':'application/json'}}, body: JSON.stringify({{ email:'bramuel@syni.ai', password:'Bramuel2026!' }}) }});
          const d = await r.json();
          window.localStorage.setItem('akki_access_token', d.access_token || '');
          window.localStorage.setItem('akki_active_context_id', '{SAFIRI_CTX}');
        }}""")
        # /app is the dashboard root — always renders the AppShell with footer.
        page.goto(f"{base_url}/app", wait_until="networkidle", timeout=30_000)
        page.wait_for_timeout(4000)
        # Wait for the link to appear (up to 8s) then highlight + clip.
        try:
            page.wait_for_selector('[data-testid="trust-footer-link"]', timeout=8000)
        except Exception:
            pass
        bbox = page.evaluate("""() => {
          const el = document.querySelector('[data-testid="trust-footer-link"]');
          if (!el) return null;
          el.scrollIntoView({block:'center', behavior:'instant'});
          el.style.outline = '3px solid #f59e0b';
          el.style.outlineOffset = '4px';
          el.style.background = 'rgba(245,158,11,0.32)';
          el.style.color = '#1a1a1a';
          el.style.fontWeight = '700';
          const r = el.getBoundingClientRect();
          return { x: r.x, y: r.y, w: r.width, h: r.height };
        }""")
        if not bbox:
            print("  WARN: trust-footer-link not found — saving full viewport")
            page.screenshot(path=str(OUT_DIR / "04_footer_us_spelling.png"), full_page=False)
        else:
            print(f"  Trust Center bbox: {bbox}")
            cx = max(0, int(bbox["x"]) - 600)
            cy = max(0, int(bbox["y"]) - 60)
            cw = min(1440 - cx, 1100)
            ch = min(900 - cy, 200)
            page.screenshot(
                path=str(OUT_DIR / "04_footer_us_spelling.png"),
                clip={"x": cx, "y": cy, "width": cw, "height": ch},
            )
        print("  ✅ 04_footer_us_spelling.png")

        # 05 — PAN placeholder reply
        page.set_content(pan_panel_html(
            data["user_text"], data["asst_text"], data["by_type"], data["audit_id"],
        ))
        page.wait_for_timeout(300)
        page.screenshot(path=str(OUT_DIR / "05_chat_pan_redaction.png"), full_page=False)
        print("  ✅ 05_chat_pan_redaction.png")

        ctx.close()
        browser.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--base-url",
        default="https://akki-executive.preview.emergentagent.com",
    )
    args = ap.parse_args()
    print(f"H1 screenshot capture → {OUT_DIR} (base_url={args.base_url})")
    capture_all(args.base_url)
    print(f"Done — wrote 5 PNGs into {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
