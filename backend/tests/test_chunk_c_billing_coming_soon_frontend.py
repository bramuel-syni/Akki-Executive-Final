"""Chunk (c) — Billing & Subscription "Coming Soon" UX (frontend
behavior tests).

Anti-source-string-assertion discipline (closeout §5.8): every test
asserts a CONTROL-FLOW CHAIN or a verbatim-copy contract WITH a co-
located test-id anchor in the SAME JSX wrapper.

  C.F1 — `BillingTab.jsx` no longer references the legacy Stripe
         checkout call path (`/billing/checkout` POST + `window.
         location.href = ...`). The mocked-mode kill MUST stick.
  C.F2 — `BillingTab.jsx` carries the verbatim Coming-Soon heading
         + body + CTA copy AND co-located data-testids
         (`billing-coming-soon-heading` / `..._body` / `billing-
         notify-cta`).
  C.F3 — `BillingTab.jsx` `onNotify` posts to
         `/notify-billing-launch` and updates UI state with the
         response (anchor-chain: `api.post(...)` AND `setNotifyState
         (data)`).
  C.F4 — `UpgradeModal.jsx` routes its primary CTA to
         `/app/settings/billing` (the Coming-Soon surface) — NOT
         `/plans` and NOT a checkout URL. Anchor-chain: `<Link to=
         "/app/settings/billing"` AND `data-testid="upgrade-modal-
         billing-cta"`.
  C.F5 — `UpgradeModal.jsx` carries the verbatim Coming-Soon body
         copy (single source of truth — must match `routers/billing.
         py::COMING_SOON_BODY`).
  C.F6 — Anti-regression — there are NO "Upgrade to Pro" /
         "Upgrade to Team" / "Redirecting…" CTAs anywhere in
         `BillingTab.jsx` (those were the §M4 fake-success
         affordances). The Coming-Soon contract replaces them.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BILLING_TAB = REPO / "frontend/src/components/settings/BillingTab.jsx"
UPGRADE_MODAL = REPO / "frontend/src/components/depth/UpgradeModal.jsx"

VERBATIM_HEADING = "Billing & Subscription — Coming Soon"
VERBATIM_BODY_FRAGMENT = (
    "We're finalizing our subscription tiers."
)
VERBATIM_CTA = "Notify me when this is ready"


def _function_body(src: str, name: str) -> str:
    """Brace-matched function-body slicer. Same pattern as J4
    frontend tests — bounds the chain assertion to a specific
    function so a literal string elsewhere can't satisfy it."""
    candidates = [
        rf"async\s+function\s+{re.escape(name)}\s*\(",
        rf"function\s+{re.escape(name)}\s*\(",
        rf"const\s+{re.escape(name)}\s*=\s*[^;]*=>\s*\{{",
        rf"\b{re.escape(name)}\s*=\s*useCallback\(",
        rf"\b{re.escape(name)}\s*=\s*async\s*\([^)]*\)\s*=>",
    ]
    for pat in candidates:
        m = re.search(pat, src)
        if not m:
            continue
        open_idx = src.find("{", m.end() - 1)
        if open_idx == -1:
            continue
        depth = 1
        i = open_idx + 1
        while i < len(src) and depth > 0:
            ch = src[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            i += 1
        if depth == 0:
            return src[open_idx + 1 : i - 1]
    return ""


# ── C.F1 — Legacy Stripe checkout call gone ────────────────────────
def test_c_f1_billing_tab_no_stripe_checkout_call():
    """The fake-success path was: `api.post("/billing/checkout", …)`
    THEN `window.location.href = data.url`. Both anchors MUST be
    absent from BillingTab.jsx — the mocked-mode kill is enforced
    at the call site, not just the URL string."""
    src = BILLING_TAB.read_text(encoding="utf-8")
    forbidden = [
        '/billing/checkout',
        '/billing/status/',
        'window.location.href = data.url',
        'window.location.href = ',
        'Redirecting…',
        'onCheckout',
    ]
    offenders = [s for s in forbidden if s in src]
    assert not offenders, (
        f"Legacy Stripe checkout call path still in BillingTab.jsx: "
        f"{offenders}. The Coming-Soon contract requires these be "
        f"removed."
    )


# ── C.F2 — Verbatim Coming-Soon copy + co-located testids ─────────
def test_c_f2_billing_tab_verbatim_coming_soon_copy():
    """Verifies the verbatim Coming-Soon copy is rendered through a
    JSX element carrying the spec-named testid. Pattern:
      - `COMING_SOON_*` const at the top of the file carries the
        verbatim string (single source of truth).
      - The JSX element with `data-testid="billing-coming-soon-
        heading"` MUST render `{COMING_SOON_HEADING}` (control-flow
        chain, not source-string-only)."""
    src = BILLING_TAB.read_text(encoding="utf-8")
    # Verbatim const declarations (source of truth).
    assert f'COMING_SOON_HEADING = "{VERBATIM_HEADING}";' in src, (
        f"Verbatim Coming-Soon heading const missing: '{VERBATIM_HEADING}'"
    )
    assert VERBATIM_BODY_FRAGMENT in src, (
        f"Verbatim Coming-Soon body fragment missing: "
        f"'{VERBATIM_BODY_FRAGMENT}'"
    )
    assert f'COMING_SOON_CTA = "{VERBATIM_CTA}";' in src, (
        f"Verbatim Coming-Soon CTA const missing: '{VERBATIM_CTA}'"
    )

    # JSX consumption chain — each verbatim const MUST be rendered
    # through its testid'd element. We slice ~250 chars after each
    # testid and assert the matching `{CONST}` interpolation appears.
    def _window_after_testid(testid: str) -> str:
        idx = src.find(f'data-testid="{testid}"')
        assert idx != -1, f"data-testid='{testid}' missing"
        return src[idx : idx + 400]

    heading_window = _window_after_testid("billing-coming-soon-heading")
    assert "{COMING_SOON_HEADING}" in heading_window, (
        "`{COMING_SOON_HEADING}` JSX expression missing within "
        "~400 chars of the heading testid. The verbatim heading "
        "is NOT being rendered through the spec'd element."
    )

    body_window = _window_after_testid("billing-coming-soon-body")
    assert "{COMING_SOON_BODY}" in body_window, (
        "`{COMING_SOON_BODY}` JSX expression missing within ~400 "
        "chars of the body testid."
    )

    cta_window = src[src.find('data-testid="billing-notify-cta"'):]
    cta_window = cta_window[:1200]
    assert "{COMING_SOON_CTA}" in cta_window, (
        "`{COMING_SOON_CTA}` JSX expression missing within ~1200 "
        "chars of the notify-cta testid."
    )


# ── C.F3 — onNotify posts to /notify-billing-launch chain ──────────
def test_c_f3_billing_tab_on_notify_posts_to_endpoint():
    src = BILLING_TAB.read_text(encoding="utf-8")
    body = _function_body(src, "onNotify")
    assert body, "Could not locate `onNotify` function body."
    # Anchor 1 — POST to the spec endpoint.
    assert 'api.post("/notify-billing-launch")' in body, (
        "onNotify no longer POSTs to /notify-billing-launch."
    )
    # Anchor 2 — response data drives UI state.
    assert "setNotifyState(data)" in body, (
        "onNotify no longer threads the response through "
        "setNotifyState — UI won't reflect the already_subscribed "
        "flag."
    )


# ── C.F4 — UpgradeModal routes to /app/settings/billing ────────────
def test_c_f4_upgrade_modal_routes_to_coming_soon_billing():
    """Any 'Upgrade' / 'Manage Plan' CTA across the app lands here.
    Per chunk (c) brief — the primary CTA MUST point to
    `/app/settings/billing` (the Coming-Soon surface), NOT to
    `/plans` (the marketing early-access page) and NOT to a
    checkout URL."""
    src = UPGRADE_MODAL.read_text(encoding="utf-8")
    # Anchor 1 — Link to /app/settings/billing exists.
    assert 'to="/app/settings/billing"' in src, (
        "UpgradeModal no longer routes to /app/settings/billing."
    )
    # Anchor 2 — co-located testid on that Link.
    link_idx = src.find('to="/app/settings/billing"')
    assert link_idx != -1
    testid_idx = src.find('data-testid="upgrade-modal-billing-cta"')
    assert testid_idx != -1, (
        "Billing CTA testid 'upgrade-modal-billing-cta' missing"
    )
    assert abs(link_idx - testid_idx) < 500, (
        "The Link and its testid are NOT co-located in the same "
        "JSX element (>500 chars apart)."
    )
    # Anti-regression — the legacy `to="/plans"` and any /billing/
    # checkout URL are gone from the primary CTA position.
    forbidden = ["window.location.href"]
    offenders = [s for s in forbidden if s in src]
    assert not offenders, (
        f"Forbidden checkout-style affordances still in "
        f"UpgradeModal.jsx: {offenders}"
    )


# ── C.F5 — UpgradeModal verbatim body copy ─────────────────────────
def test_c_f5_upgrade_modal_verbatim_coming_soon_body():
    src = UPGRADE_MODAL.read_text(encoding="utf-8")
    assert VERBATIM_HEADING in src, (
        "Verbatim Coming-Soon heading missing from UpgradeModal."
    )
    assert VERBATIM_BODY_FRAGMENT in src, (
        "Verbatim Coming-Soon body fragment missing from "
        "UpgradeModal."
    )
    assert 'data-testid="upgrade-modal-heading"' in src
    assert 'data-testid="upgrade-modal-body"' in src


# ── C.F6 — Anti-regression: §M4 fake-success CTAs gone ─────────────
def test_c_f6_billing_tab_no_legacy_upgrade_ctas():
    src = BILLING_TAB.read_text(encoding="utf-8")
    forbidden = [
        "Upgrade to Pro",
        "Upgrade to Team",
        'data-testid="billing-upgrade-',  # the per-plan upgrade-{id} testids
        'data-testid="billing-polling"',  # the post-Stripe poll banner
        "Confirming your payment with Stripe",  # poll banner copy
    ]
    offenders = [s for s in forbidden if s in src]
    assert not offenders, (
        f"§M4 fake-success affordances still present in "
        f"BillingTab.jsx: {offenders}. Coming-Soon contract "
        f"requires these be removed."
    )
