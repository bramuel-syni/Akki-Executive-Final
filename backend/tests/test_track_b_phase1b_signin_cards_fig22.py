"""Track B Phase B1b lockdowns — O4 + O6 re-dispatch, Fig 20, Fig 22.

R4 (≤10 tests). Coverage:

  1. O4 — Card 1 ("Create your first cycle") handler resolves to
     /app/task-manager (source-text + route-mount assertion)
  2. O4 — no /app/cycle?wizard=1 literal remaining in the door=="cycle"
     handler (regression guard)
  3. O6 — Card 3 ("Try the Demo") handler resolves to /app (Home;
     App.js confirms no /app/home alias)
  4. O6 — no /app/cycle literal remaining in the door=="demo" handler
  5. Fig 20 — ResetPassword "Back to sign-in" navigates to /signin
  6. Fig 20 — ForgotPassword "Back to sign-in" navigates to /signin
  7. Fig 20 — ForgotPassword "Return to sign-in" navigates to /signin
  8. Fig 22 — SessionTimeoutGuard handler gates on `account` truthy
  9. Fig 22 — P0-C OAuth last_activity_at write still present
     (regression — same module patched twice; v1 fix must survive)
 10. Regression — App.js still mounts the canonical routes
     (/app/task-manager + /app + /signin). If any of these drift the
     lockdown breaks loud.
"""
from __future__ import annotations

from pathlib import Path


REPO = Path("/app")
FRONTEND = REPO / "frontend" / "src"
APP_JS = FRONTEND / "App.js"


# ─── O4 — Card 1 → Task Manager ─────────────────────────────────


def test_o4_card1_routes_to_task_manager():
    """The door=='cycle' branch of FirstSession.choose() must
    navigate to /app/task-manager — verbatim ask from Onboarding QA
    item 4: 'I think the user should be redirected to the Task
    Manager Module shown in figure 3'."""
    src = (FRONTEND / "pages" / "FirstSession.jsx").read_text(encoding="utf-8")
    # The handler must navigate to /app/task-manager.
    cycle_branch = src.split('if (door === "cycle")', 1)[1].split("if (door === ", 1)[0]
    assert 'navigate("/app/task-manager")' in cycle_branch, (
        "FirstSession.jsx door=='cycle' branch no longer navigates to "
        "/app/task-manager. Track B Phase B1b regression."
    )


def test_o4_no_legacy_cycle_wizard_literal_in_door_cycle_handler():
    """The previous target /app/cycle?wizard=1&intake_seed=1 must NOT
    appear as a navigate() target inside the door=='cycle' branch.
    Checks the navigate() call only (the explanatory comment retains
    the literal for historical-record purposes; we filter)."""
    src = (FRONTEND / "pages" / "FirstSession.jsx").read_text(encoding="utf-8")
    cycle_branch = src.split('if (door === "cycle")', 1)[1].split("if (door === ", 1)[0]
    # Drop // line comments and /* … */ block comments so we test
    # against ACTIVE source only.
    import re
    code_only = re.sub(r"/\*.*?\*/", "", cycle_branch, flags=re.S)
    code_only = re.sub(r"//[^\n]*", "", code_only)
    assert "/app/cycle?wizard=1" not in code_only, (
        "FirstSession.jsx door=='cycle' branch still has a live "
        "/app/cycle?wizard=1 reference. Track B Phase B1b regression."
    )
    assert "intake_seed=1" not in code_only


# ─── O6 — Card 3 → Home ─────────────────────────────────────────


def test_o6_card3_routes_to_home():
    """The door=='demo' branch must navigate to /app (canonical Home).
    Verbatim ask from Onboarding QA item 6: 'I think the user should
    land on the Home Page'."""
    src = (FRONTEND / "pages" / "FirstSession.jsx").read_text(encoding="utf-8")
    demo_branch = src.split('if (door === "demo")', 1)[1].split("if (door === ", 1)[0]
    # Allow either `navigate("/app")` or `navigate("/app/")` (canonical
    # is the bare form per App.js:435).
    assert 'navigate("/app")' in demo_branch, (
        "FirstSession.jsx door=='demo' branch no longer navigates to "
        "/app (canonical Home). Track B Phase B1b regression."
    )


def test_o6_no_legacy_cycle_literal_in_door_demo_handler():
    """The previous target /app/cycle (Cycle Manager) must NOT appear
    in the door=='demo' branch."""
    src = (FRONTEND / "pages" / "FirstSession.jsx").read_text(encoding="utf-8")
    demo_branch = src.split('if (door === "demo")', 1)[1].split("if (door === ", 1)[0]
    assert 'navigate("/app/cycle")' not in demo_branch, (
        "door=='demo' still navigates to /app/cycle — Track B Phase B1b "
        "O6 re-dispatch has regressed."
    )


# ─── Fig 20 — Reset/Forgot password buttons → /signin ───────────


def test_fig20_reset_password_back_button_navigates_to_signin():
    src = (FRONTEND / "pages" / "ResetPassword.jsx").read_text(encoding="utf-8")
    assert 'navigate("/signin")' in src, (
        "ResetPassword.jsx no longer navigates to /signin — Fig 20 fix regressed."
    )
    # Hyphenated form must be GONE (the 404 → wildcard → / chain).
    assert 'navigate("/sign-in")' not in src, (
        "ResetPassword.jsx still uses /sign-in (with hyphen) which 404s into "
        "the marketing redirect. Fig 20 v1 regression."
    )


def test_fig20_forgot_password_both_navigations_target_signin():
    src = (FRONTEND / "pages" / "ForgotPassword.jsx").read_text(encoding="utf-8")
    needle = 'navigate("/signin")'
    count = src.count(needle)
    # Both occurrences must be /signin.
    assert count == 2, (
        f"ForgotPassword.jsx expected 2 occurrences of {needle}, "
        f"found {count}. Track B Phase B1b regression."
    )
    # Hyphenated form must be GONE.
    assert 'navigate("/sign-in")' not in src


# ─── Fig 22 — SessionTimeoutGuard handler gated on account ──────


def test_fig22_session_event_handler_gates_on_account():
    """The handler that opens the re-auth modal on session_idle_timeout
    must early-return when there's no current account. This prevents
    the modal from surfacing during /oauth/callback bootstrap when a
    stale token from a prior session is sitting in localStorage."""
    src = (FRONTEND / "components" / "SessionTimeoutGuard.jsx").read_text(encoding="utf-8")
    # Find the handler block for akki:session-event.
    assert 'addEventListener("akki:session-event"' in src
    # Extract the handler function definition. The gate must read
    # `if (!account) return;`.
    handler_block = src.split('addEventListener("akki:session-event"', 1)[0]
    # We want to be sure the `account`-truthy gate landed inside the
    # `const handler = (e) => { ... }` of the session-event useEffect.
    # The handler is defined immediately above the addEventListener
    # call inside the same useEffect; we string-match within the
    # ~last 1500 chars of the pre-listener slice.
    nearby = handler_block[-1500:]
    assert "if (!account) return;" in nearby, (
        "SessionTimeoutGuard.jsx session-event handler missing the "
        "`if (!account) return;` gate — Fig 22 v2 root-cause fix has "
        "regressed; stale localStorage tokens on /oauth/callback will "
        "again surface the misleading 'Re-enter your password' modal."
    )
    # And the useEffect's deps array must include `account`.
    # (Without that, the handler closes over a stale `account` snapshot.)
    assert ", [account])" in src or ",[account])" in src, (
        "SessionTimeoutGuard.jsx session-event useEffect must depend on "
        "`account` so the handler sees the current auth state."
    )


def test_fig22_p0c_oauth_last_activity_at_write_still_present():
    """Regression — the v1 P0-C fix is at auth_oauth.py and writes
    `last_activity_at` post-OAuth. Track B Phase B1b adds a frontend-
    side gate; the backend write must remain in place."""
    src = (REPO / "backend" / "routers" / "auth_oauth.py").read_text(encoding="utf-8")
    # Two writes: Google /finish + Microsoft callback. Both must persist.
    assert src.count('"last_activity_at": datetime.now(timezone.utc).isoformat()') >= 2, (
        "auth_oauth.py no longer writes last_activity_at on the OAuth "
        "handlers — P0-C v1 has regressed."
    )


# ─── Regression — canonical routes still mounted ────────────────


def test_canonical_routes_still_mounted_in_app_js():
    """Track B Phase B1b pins the three target routes — /app/task-manager
    (O4), /app (O6), /signin (Fig 20). Any drift on these in App.js
    would silently break the fixes above."""
    app = APP_JS.read_text(encoding="utf-8")
    assert '<Route path="/app/task-manager"' in app, (
        "App.js no longer mounts /app/task-manager — Track B Phase B1b O4 "
        "route-target dependency missing."
    )
    assert '<Route path="/app"' in app, (
        "App.js no longer mounts /app — Track B Phase B1b O6 route-target "
        "dependency missing."
    )
    assert '<Route path="/signin"' in app, (
        "App.js no longer mounts /signin — Fig 20 route-target dependency "
        "missing."
    )
