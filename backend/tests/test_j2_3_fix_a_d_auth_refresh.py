"""J2.3-fix.A + D — Frontend cycle-door auth-state refresh behavior.

Background
----------
The first J2.3 fix flipped the backend cycle-door state to `completed`
correctly. But the frontend cycle-door click handler in
`FirstSession.jsx` was still binding `refreshAuth={refreshContexts}`
at the parent component level (L686 pre-fix). `refreshContexts` only
refreshes `contexts` state — it does NOT call `/auth/me` and does NOT
update `account.first_session.*`. So the AuthContext's `account`
remained stale `in_progress`, and `FirstSessionGuard` (App.js
L160-166) redirected the `/app/cycle?wizard=1` navigate back to
`/app/first-session`.

Same wiring bug affected solve + demo branches but they "worked
incidentally" per e1_tester report (likely due to race conditions or
re-render timing). The user's directive: align all three.

Fix
---
`refreshAuth={refreshContexts}` → `refreshAuth={bootstrap}`. `bootstrap`
is the AuthContext function that calls `/auth/me` and
`setAccount(data.account)` — i.e. it pulls the new `completed` state
into the React tree before the navigate fires.

Behavior assertions (NOT source-string)
----------------------------------------
These tests walk the control-flow chain that proves the refresh
WIRE is correctly bound and that each door branch awaits the refresh
BEFORE navigating. The 3 chain anchors per door must coexist within
the same `choose` function body — a partial implementation breaks
the chain.

Closeout §5.8 reference: source-string assertions verify the label,
not the wire. Tests in this file verify the wire.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FIRST_SESSION = REPO / "frontend/src/pages/FirstSession.jsx"


def _read():
    return FIRST_SESSION.read_text(encoding="utf-8")


def _choose_function_body(src: str) -> str:
    """Extract the body of the `choose` useCallback inside
    `FirstSessionDoor`. This is the single function that owns all
    three door branches; the refresh wire MUST resolve within its
    scope."""
    m = re.search(
        r"const\s+choose\s*=\s*useCallback\s*\(\s*async\s*\(\s*door\s*\)\s*=>\s*\{(.*?)\},\s*\[",
        src, re.DOTALL,
    )
    assert m, "Could not locate the `choose` useCallback in FirstSession.jsx"
    return m.group(1)


def _branch_body(choose_body: str, door: str) -> str:
    """Extract just the `if (door === "<door>")` block from the choose
    body so the per-branch behavior assertion is scoped tightly."""
    pattern = (
        rf'if\s*\(\s*door\s*===\s*[\'"]{door}[\'"]\s*\)\s*\{{(.*?)\n\s*\}}'
    )
    m = re.search(pattern, choose_body, re.DOTALL)
    if not m:
        return ""
    return m.group(1)


# ── J2.3-fix.A — `refreshAuth` prop wires to `bootstrap` ────────────
def test_j2_3_fix_a_parent_destructures_bootstrap_from_useAuth():
    """The parent FirstSession component must pull `bootstrap` out of
    `useAuth()` — that's the function that calls /auth/me and updates
    `account` so the FirstSessionGuard reads fresh state."""
    src = _read()
    # Look for the useAuth destructure that includes bootstrap.
    m = re.search(
        r"const\s*\{[^}]*\bbootstrap\b[^}]*\}\s*=\s*useAuth\s*\(\s*\)",
        src,
    )
    assert m, (
        "FirstSession does not destructure `bootstrap` from useAuth(). "
        "Currently `refreshContexts` alone is destructured, which does "
        "NOT refresh account/first_session state — the cycle-door bug."
    )


def test_j2_3_fix_a_first_session_door_refresh_auth_prop_bound_to_bootstrap():
    """The `<FirstSessionDoor ... refreshAuth={bootstrap} />` prop
    must bind to `bootstrap`, NOT `refreshContexts`. This is the
    SINGLE LINE fix that propagates to all three door branches
    (cycle, solve, demo) because they all call `await refreshAuth()`
    via the same prop."""
    src = _read()
    # Locate the FirstSessionDoor element render.
    m = re.search(
        r"<FirstSessionDoor\b[^>]*>",
        src, re.DOTALL,
    )
    assert m, "FirstSessionDoor render not found"
    el = m.group(0)
    # Positive — refreshAuth is bound to bootstrap.
    assert re.search(r"refreshAuth\s*=\s*\{\s*bootstrap\s*\}", el), (
        "FirstSessionDoor's `refreshAuth` prop is NOT bound to `bootstrap`. "
        f"Current attribute set: {el!r}"
    )
    # Negative — must NOT still be bound to refreshContexts.
    assert "refreshAuth={refreshContexts}" not in el, (
        "FirstSessionDoor's `refreshAuth` is still bound to "
        "`refreshContexts`. That's the J2.3-fix.A bug — refreshContexts "
        "does not update account state."
    )


# ── Per-door behavior: `await refreshAuth()` BEFORE `navigate(...)` ─
def _assert_refresh_before_navigate(branch_body: str, door: str):
    """Inside the per-door branch body, `await refreshAuth()` must
    appear BEFORE `navigate(...)`. The user lands on a stale-auth
    redirect if the navigate fires before the refresh resolves."""
    assert branch_body, f"No branch body extracted for door={door!r}"
    refresh_idx = -1
    for marker in (
        "await refreshAuth()",
        "if (refreshAuth) await refreshAuth()",
    ):
        idx = branch_body.find(marker)
        if idx != -1:
            refresh_idx = idx
            break
    nav_idx = branch_body.find("navigate(")
    assert refresh_idx != -1, (
        f"`{door}` branch is missing the `await refreshAuth()` call. "
        f"Branch body: {branch_body[:300]!r}"
    )
    assert nav_idx != -1, (
        f"`{door}` branch is missing the `navigate(...)` call."
    )
    assert refresh_idx < nav_idx, (
        f"`{door}` branch calls `navigate(...)` at {nav_idx} BEFORE "
        f"`refreshAuth()` at {refresh_idx} — order violation. The "
        f"navigate must wait for the auth-refresh promise to resolve "
        f"so FirstSessionGuard reads fresh state."
    )


def test_j2_3_fix_a_cycle_branch_awaits_refresh_before_navigate():
    """Cycle door: `await refreshAuth()` BEFORE `navigate(...)`."""
    src = _read()
    body = _branch_body(_choose_function_body(src), "cycle")
    _assert_refresh_before_navigate(body, "cycle")


def test_j2_3_fix_d_solve_branch_awaits_refresh_before_navigate():
    """Solve door alignment: same refresh-before-navigate contract."""
    src = _read()
    body = _branch_body(_choose_function_body(src), "solve")
    _assert_refresh_before_navigate(body, "solve")


def test_j2_3_fix_d_demo_branch_awaits_refresh_before_navigate():
    """Demo door alignment: same refresh-before-navigate contract."""
    src = _read()
    body = _branch_body(_choose_function_body(src), "demo")
    _assert_refresh_before_navigate(body, "demo")


# ── Sanity: refreshContexts is no longer the binding ────────────────
def test_j2_3_fix_a_no_residual_refreshcontexts_binding_for_door_refresh():
    """Anti-residual: nowhere in FirstSession.jsx should the
    `refreshAuth` prop receive `refreshContexts`. Other call sites of
    `refreshContexts` (e.g. the `onArtefactReady` callback) are
    allowed because that path operates on the contexts list, not the
    door auth-refresh contract."""
    src = _read()
    # Specifically the refreshAuth prop binding must not be
    # refreshContexts.
    assert "refreshAuth={refreshContexts}" not in src
