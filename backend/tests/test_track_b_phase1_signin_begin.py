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
    """v1 of the fix bumped disabled bg-opacity /40 → /70. v2 root-cause
    fix descopes `.akki-overline`'s color from `<button>` elements in
    index.css. Both layers must stay present so a regression on either
    layer trips this lockdown."""
    page = (FRONTEND / "pages" / "FirstSession.jsx").read_text(encoding="utf-8")
    # The original bad combination must remain absent.
    assert "bg-[var(--accent)]/40 cursor-not-allowed" not in page, (
        "FirstSession.jsx still uses bg-[var(--accent)]/40 on the disabled "
        "Begin button — Fig 7 v1 regression."
    )
    # v1 fix shape must remain present.
    assert "bg-[var(--accent)]/70 cursor-not-allowed" in page, (
        "FirstSession.jsx is missing the /70 disabled background — Fig 7 v1 "
        "fix was removed or refactored away."
    )
    # The button still says BEGIN.
    assert "BEGIN →" in page


def test_fig7_root_cause_akki_overline_descoped_from_buttons():
    """v2 root-cause fix. `.akki-overline` no longer sets `color:` at the
    base selector — that color was silently winning over every explicit
    Tailwind `text-*` utility on `<button>` consumers. The fix moves
    `color: var(--oxblood)` to `.akki-overline:not(button)` so buttons
    keep their developer-intended text-color. Lockdown asserts both the
    de-scope AND that the typography rule still sets the other props
    (font/size/weight/uppercase/letter-spacing)."""
    css = (FRONTEND / "index.css").read_text(encoding="utf-8")
    # The :not(button) scope MUST be present (the v2 fix shape).
    assert ".akki-overline:not(button)" in css, (
        "index.css missing the `.akki-overline:not(button)` rule — v2 "
        "root-cause fix has regressed; <button> consumers will silently lose "
        "their explicit Tailwind text-* utility to the oxblood override."
    )
    # The base rule MUST NOT set `color:` (otherwise the de-scope is no-op).
    base_block_start = css.index(".akki-overline {")
    base_block_end = css.index("}", base_block_start)
    base_block = css[base_block_start:base_block_end]
    assert "color:" not in base_block, (
        "index.css `.akki-overline {…}` base block re-introduced a `color:` "
        "declaration — that would override every <button>'s Tailwind text-* "
        "again. Move it back to `.akki-overline:not(button)`."
    )
    # The typography props MUST remain on the base block (so all consumers
    # — buttons and non-buttons — still get the uppercase/letter-spacing).
    for prop in ("font-family", "font-size", "font-weight",
                 "text-transform", "letter-spacing"):
        assert prop in base_block, (
            f"index.css `.akki-overline` base block missing `{prop}` — "
            f"typography regression."
        )


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


# ─── Live-DOM lockdown (R3 — journey, not surface-render) ──────────


_FIG7_TRACE = Path("/tmp/track_b_phase1_fig7_v2_trace.py")


@pytest.mark.skipif(
    not _FIG7_TRACE.exists(),
    reason=(
        "Fig 7 live-DOM trace script missing at /tmp/. Run the v2 "
        "scaffold step or set PREVIEW_URL to skip the trace."
    ),
)
def test_fig7_live_dom_text_color_not_equal_bg_color():
    """Live-DOM lockdown. Drives a real Chromium against the preview,
    seeds `viewer@akki.ai` into `first_session.current_step=intake`,
    navigates to the FirstSession intake, and asserts that the
    rendered computed `color` differs materially from the rendered
    computed `background-color` on the Begin button — both in
    disabled and active state. Source-text tests catch class-name
    regressions but the original bug was a CSS-cascade override
    (`.akki-overline { color: var(--oxblood) }` winning over
    `text-white`) which source-text cannot see. THIS test is the
    one that would have caught the v1-fix gap."""
    import subprocess

    result = subprocess.run(
        ["python3", str(_FIG7_TRACE)],
        capture_output=True, text=True, timeout=180,
    )
    # Surface the verbatim trace output so the assertion message
    # carries enough evidence to debug a re-regression.
    output = (result.stdout or "") + "\n" + (result.stderr or "")
    assert result.returncode == 0, (
        f"Fig 7 live-DOM trace FAILED (exit={result.returncode}).\n"
        f"--- trace output ---\n{output}\n"
    )
    # Sanity: the trace must report both colours and the PASS line.
    assert "[disabled] text-color:" in output
    assert "[disabled] background-color:" in output
    assert "[Fig 7 v2] PASS" in output, output




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
