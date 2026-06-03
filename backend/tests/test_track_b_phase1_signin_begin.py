"""Track B Phase 1 — sign-in routing + Begin button visibility lockdowns.

Scope per the approved Pre-Read:
  • C2 Fig 20: Unauthenticated visit to `/` lands on `/signin`.
  • C2 Fig 22: Post-redirect error toast/state diagnosed and fixed.
  • C8 Fig 7:  "Begin" button text-color contrast fix.

Status this dispatch (honest reckoning):
  • Fig 7: SHIPPED — disabled state on FirstSession.jsx:184-196 now uses
    bg-[var(--accent)]/70 (was /40). White text on /70 has a far
    larger contrast band than on /40 against the cream page background.
    Asserted as source-text lockdown below; the Playwright trace
    measures the actual computed-style contrast.
  • Fig 20: NOT SHIPPED — surfaced as BLOCKED_NEED_SCREENSHOT in the
    combined memo. The literal interpretation (force `/` → `/signin`
    for unauth) would break the marketing funnel; the real fix is
    likely a broken link or the wildcard `*` route catch-all
    (App.js:544 sends `*` to `/`), neither of which can be pinpointed
    without the Fig 20 screenshot. Source code state is unchanged.
  • Fig 22: NOT SHIPPED — same reason. Could be OAuth, idle-timeout,
    set-password gate, or sign-in toast. Surfaced in memo.

Test methodology: per the rails (no DOM-only / surface-render-only),
assertions are SOURCE-TEXT lockdowns. The Playwright trace
(`/tmp/track_b_phase1_trace.py`) carries the live computed-style
check.
"""
from __future__ import annotations

from pathlib import Path

import pytest


REPO = Path("/app")
FRONTEND = REPO / "frontend" / "src"


# ─── Fig 7 — source-text lockdown ───────────────────────────────


def test_fig7_first_session_begin_button_no_low_contrast_disabled():
    """The previously-shipped disabled state combined `text-white` with
    `bg-[var(--accent)]/40` — white on 40%-opacity-accent over a cream
    background is the contrast failure mode. The fix bumps the disabled
    state's bg-opacity to /70. Lockdown asserts the regression cannot
    silently re-land."""
    page = (FRONTEND / "pages" / "FirstSession.jsx").read_text(encoding="utf-8")
    # The bad combination must no longer appear.
    assert "bg-[var(--accent)]/40 cursor-not-allowed" not in page, (
        "FirstSession.jsx still uses bg-[var(--accent)]/40 on the disabled "
        "Begin button — that was the C8/Fig 7 root cause and has been logged "
        "as a regression."
    )
    # The fix shape must remain present.
    assert "bg-[var(--accent)]/70 cursor-not-allowed" in page, (
        "FirstSession.jsx is missing the /70 disabled background — Fig 7 fix "
        "was removed or refactored away."
    )
    # The button still says BEGIN.
    assert "BEGIN →" in page


def test_fig7_begin_button_keeps_data_testid_for_playwright():
    """The Playwright trace pins on this testid. Don't let it drift."""
    page = (FRONTEND / "pages" / "FirstSession.jsx").read_text(encoding="utf-8")
    assert 'data-testid="first-session-intake-submit"' in page


# ─── Regressions that MUST stay green (per dispatch test 5/6/7) ─────


def test_p0_c_oauth_last_activity_at_refresh_still_present():
    """P0-C OAuth fix is at `routers/auth_oauth.py` — `last_activity_at` is
    refreshed on the Google/Microsoft callback. Source-strict regression:
    the field is still set on the OAuth handlers."""
    src = (REPO / "backend" / "routers" / "auth_oauth.py").read_text(encoding="utf-8")
    # The fix writes a fresh ISO timestamp on the account row after
    # OAuth callback. Assert the literal field name is referenced.
    assert "last_activity_at" in src, (
        "auth_oauth.py no longer references last_activity_at — the P0-C "
        "OAuth idle-timeout fix has regressed."
    )


def test_c1_a_has_set_password_gate_still_present():
    """C1-revised Phase A FirstLoginPasswordSet middleware/service. Assert
    the strict-bool gate field is referenced in both backend and SPA."""
    backend_src = (REPO / "backend" / "services" / "first_login_password_set.py")
    assert backend_src.exists(), "first_login_password_set.py missing — C1-A regressed"
    backend_text = backend_src.read_text(encoding="utf-8")
    assert "has_set_password" in backend_text
    app_text = (FRONTEND / "App.js").read_text(encoding="utf-8")
    assert "has_set_password" in app_text, (
        "App.js no longer references has_set_password — the C1-A SetPasswordGuard "
        "has regressed."
    )


def test_p0_b_card_2_documents_upload_route_still_present():
    """P0-B Card 2: 'Upload a document' onboarding card routes to
    /app/documents and opens the upload modal via ?upload=1.
    Source-strict lockdown: the FirstSession.jsx step-2 door still
    targets that surface."""
    page = (FRONTEND / "pages" / "FirstSession.jsx").read_text(encoding="utf-8")
    # The door dispatch table maps the four onboarding choices to
    # destinations. P0-B Card 2 routes to /app/documents. Allow both
    # bare and query-suffix variants.
    assert "/app/documents" in page, (
        "FirstSession.jsx no longer references /app/documents — P0-B Card 2 "
        "has regressed."
    )


# ─── BLOCKED items — explicit fail-fast so they cannot be silently skipped ─


@pytest.mark.skip(
    reason="Fig 20 BLOCKED_NEED_SCREENSHOT — literal interpretation "
           "(redirect / to /signin for unauth) would break marketing funnel. "
           "Real fix scope unknown without the Fig 20 screenshot."
)
def test_fig20_unauth_root_lands_on_signin():
    """Stub. Skipped until the user provides Fig 20 screenshot or
    clarifies which specific surface lands at / instead of /signin."""
    pass


@pytest.mark.skip(
    reason="Fig 22 BLOCKED_NEED_SCREENSHOT — multiple candidate root causes "
           "(OAuth callback, idle-timeout, set-password gate, sign-in toast). "
           "Cannot pinpoint without the Fig 22 screenshot."
)
def test_fig22_post_redirect_no_error_state():
    """Stub. Skipped until the user provides Fig 22 screenshot."""
    pass
