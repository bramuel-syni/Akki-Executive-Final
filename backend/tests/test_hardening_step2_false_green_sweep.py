"""Hardening Step 2 — Phase B fixes (anti-false-green tests).

Spec ref: `memory/sprints/FALSE_GREEN_AUDIT_LEDGER.md` §"Phase A —
Triage outcome" — 4 real false-green sites confirmed.

Tests written using the anchor-chain pattern from closeout §5.8.
Every test asserts a CONTROL-FLOW CHAIN colocated in the SAME
function body or JSX wrapper, NOT a single source-string match.

Fixes covered:
  S2.A — `AppShell.jsx:432` — trust-center-tooltip DOM-unconditional
         (P1/T2.3 false-green fix, mirrors J4 G31 pattern).
  S2.B — `FirstSession.jsx::onIntakeSubmitted` — `bootstrap()` after
         intake POST (P3/J2.3 recurrence on intake path).
  S2.C — `FirstSession.jsx::onArtefactReady` — `bootstrap()` after
         `/me/first-session/complete` POST (P3/J2.3 recurrence on
         complete path).
  S2.D — `FirstSession.jsx::onSkip` — `bootstrap()` after skip POST
         (P3/J2.3 recurrence on skip path).
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
APPSHELL = REPO / "frontend/src/components/layout/AppShell.jsx"
FIRSTSESSION = REPO / "frontend/src/pages/FirstSession.jsx"


def _function_body(src: str, name: str) -> str:
    """Brace-matched JS function-body slicer. Same pattern as J4
    frontend tests — bounds the chain assertion to a specific
    function so a literal string elsewhere can't satisfy it."""
    candidates = [
        rf"const\s+{re.escape(name)}\s*=\s*useCallback\(",
        rf"const\s+{re.escape(name)}\s*=\s*async\s*\(",
        rf"const\s+{re.escape(name)}\s*=\s*\(",
        rf"async\s+function\s+{re.escape(name)}\s*\(",
        rf"function\s+{re.escape(name)}\s*\(",
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


def _strip_js_comments(src: str) -> str:
    """Remove `// line` and `/* block */` JS comments so anti-
    regression assertions don't trip on documentation text that
    references the deleted symbol.

    NOTE: line-comments are stripped FIRST. A line comment like
    `// FirstSessionGuard at /app/*` contains a literal `/*` that
    would otherwise be parsed as a block-comment open and consume
    code through to the next `*/`. Order matters."""
    # Line comments first — eliminates the `/*` substrings that
    # sometimes appear inside `// ...` comment text (URL refs, etc.)
    # so the block-comment regex below can't mis-match across them.
    src = re.sub(r"//[^\n]*", "", src)
    # Block comments next.
    src = re.sub(r"/\*[\s\S]*?\*/", "", src)
    return src


# ── S2.A — trust-center-tooltip DOM-unconditional ────────────────────
def test_s2_a_trust_center_tooltip_dom_unconditional():
    """`AppShell.jsx` trust-center-tooltip MUST emit without a JSX
    `&& (` conditional gate immediately preceding the testid. The
    visibility flips via `data-tooltip-visible` + CSS class fold,
    mirroring the J4 G31 pattern for help-tooltip."""
    src = APPSHELL.read_text(encoding="utf-8")
    idx = src.find('data-testid="trust-center-tooltip"')
    assert idx != -1, "trust-center-tooltip testid missing from AppShell.jsx"

    # Anchor 1 — no `&& (` JSX gate immediately preceding the testid.
    # Same window-size as the J4 G31 enforcement (J4.F7).
    window_start = max(0, idx - 250)
    pre = src[window_start:idx]
    suspicious = re.search(r"&&\s*\(\s*<\s*div\s+[^>]*$", pre)
    assert suspicious is None, (
        "trust-center-tooltip root appears behind a `&& (` "
        "conditional gate — violates the DOM-unconditional rule "
        "(closeout §5.7). The J4 G31 fix for help-tooltip is the "
        "reference pattern."
    )

    # Anchor 2 — `data-tooltip-visible` attribute is present on the
    # wrapper. This is the visibility mechanism in the spec'd pattern.
    window = src[idx : idx + 800]
    assert "data-tooltip-visible" in window, (
        "trust-center-tooltip wrapper missing `data-tooltip-visible` "
        "attribute — visibility mechanism not wired."
    )

    # Anchor 3 — the CSS class flip is `pointer-events-auto opacity-100`
    # vs `pointer-events-none invisible opacity-0` (the spec'd shape).
    assert "pointer-events-auto" in window, (
        "trust-center-tooltip wrapper missing `pointer-events-auto` "
        "in the visible-state CSS — class flip not wired."
    )
    assert "pointer-events-none" in window, (
        "trust-center-tooltip wrapper missing `pointer-events-none` "
        "in the hidden-state CSS — class flip not wired."
    )


# ── S2.B — onIntakeSubmitted calls bootstrap() ───────────────────────
def test_s2_b_on_intake_submitted_calls_bootstrap():
    """`FirstSession.jsx::onIntakeSubmitted` MUST call `bootstrap()`
    after the intake POST so the AuthContext's `account.first_session`
    is fresh. Three anchors in the SAME `useCallback` body:
      - `setState(newState)` is the first action.
      - `bootstrap()` is invoked (the correct refresh, not the
        former `refreshContexts()`).
      - the `useCallback` dep array carries `bootstrap`.

    Anti-regression: the former `refreshContexts()` must NOT be the
    sole refresh — it doesn't touch `account` state."""
    src = FIRSTSESSION.read_text(encoding="utf-8")
    body_raw = _function_body(src, "onIntakeSubmitted")
    assert body_raw, "Could not locate `onIntakeSubmitted` function body."
    body = _strip_js_comments(body_raw)
    assert "setState(newState)" in body, (
        "`setState(newState)` no longer the first action in "
        "onIntakeSubmitted — local state seed broken."
    )
    assert "bootstrap()" in body, (
        "onIntakeSubmitted no longer calls `bootstrap()` — the "
        "AuthContext's `account.first_session.{intake,current_step}` "
        "will go stale after the intake POST. J2.3 pattern recurrence."
    )
    # Anti-regression on the broken refresh path. Comments stripped
    # first so documentation references to the deleted helper don't
    # false-fail the assertion.
    assert "refreshContexts()" not in body, (
        "onIntakeSubmitted still calls `refreshContexts()` — that "
        "helper only refreshes the contexts list, NOT account state. "
        "Replace with `bootstrap()` per Step-2 Phase B."
    )


# ── S2.C — onArtefactReady calls bootstrap() ────────────────────────
def test_s2_c_on_artefact_ready_calls_bootstrap():
    """`FirstSession.jsx::onArtefactReady` MUST call `bootstrap()`
    after `POST /me/first-session/complete`. Four anchors in the
    SAME `useCallback` body:
      - the POST URL `/me/first-session/complete` appears.
      - `setState(data.state)` updates local state from the response.
      - `bootstrap()` is invoked.
      - the `useCallback` dep array references `bootstrap`.

    Anti-regression: `refreshContexts()` must NOT be the sole
    refresh."""
    src = FIRSTSESSION.read_text(encoding="utf-8")
    body_raw = _function_body(src, "onArtefactReady")
    assert body_raw, "Could not locate `onArtefactReady` function body."
    body = _strip_js_comments(body_raw)
    assert '"/me/first-session/complete"' in body, (
        "`onArtefactReady` no longer POSTs `/me/first-session/complete`."
    )
    assert "setState(data.state)" in body, (
        "`onArtefactReady` no longer updates local state from the "
        "/complete response — local state seed broken."
    )
    assert "bootstrap()" in body, (
        "`onArtefactReady` no longer calls `bootstrap()` — the "
        "AuthContext's `account.first_session.status: completed` "
        "won't roll forward, FirstSessionGuard may bounce. J2.3 "
        "pattern recurrence."
    )
    assert "refreshContexts()" not in body, (
        "`onArtefactReady` still calls `refreshContexts()` — "
        "insufficient. Replace with `bootstrap()` per Step-2 Phase B."
    )


# ── S2.D — onSkip calls bootstrap() ─────────────────────────────────
def test_s2_d_on_skip_calls_bootstrap():
    """`FirstSession.jsx::onSkip` MUST call `bootstrap()` after
    `POST /me/first-session/skip`. Three anchors in the SAME
    `useCallback` body:
      - `api.post("/me/first-session/skip")` is invoked.
      - `bootstrap()` is invoked.
      - `navigate("/app", { replace: true })` is the final step.

    Anti-regression: `refreshContexts()` must NOT be the sole
    refresh — `account.first_session.status: skipped` would stay
    stale and FirstSessionGuard would bounce."""
    src = FIRSTSESSION.read_text(encoding="utf-8")
    body_raw = _function_body(src, "onSkip")
    assert body_raw, "Could not locate `onSkip` function body."
    body = _strip_js_comments(body_raw)
    assert '"/me/first-session/skip"' in body, (
        "`onSkip` no longer POSTs `/me/first-session/skip`."
    )
    assert "bootstrap()" in body, (
        "`onSkip` no longer calls `bootstrap()` — the "
        "AuthContext's `account.first_session.status: skipped` "
        "won't roll forward, FirstSessionGuard may bounce. J2.3 "
        "pattern recurrence."
    )
    assert "refreshContexts()" not in body, (
        "`onSkip` still calls `refreshContexts()` — insufficient. "
        "Replace with `bootstrap()` per Step-2 Phase B."
    )
    assert 'navigate("/app", { replace: true })' in body, (
        "`onSkip` no longer navigates home — UX regression."
    )


# ── S2.E — bootstrap is destructured from useAuth() at module top ───
def test_s2_e_first_session_landing_destructures_bootstrap():
    """`FirstSessionLanding`'s `useAuth()` destructure MUST carry
    `bootstrap` so the three callbacks above can invoke it.

    Cross-file anchor — confirms the import chain at the call site,
    not a literal string match elsewhere."""
    src = FIRSTSESSION.read_text(encoding="utf-8")
    # The top-level FirstSession component is the default export.
    component_re = re.search(
        r"export\s+default\s+function\s+FirstSession\s*\(", src,
    )
    assert component_re, "Top-level FirstSession component missing"
    component_idx = component_re.start()
    window = src[component_idx : component_idx + 3000]
    m = re.search(
        r"const\s*\{\s*([^}]+)\s*\}\s*=\s*useAuth\(\)", window,
    )
    assert m, (
        "`useAuth()` destructure missing inside the top-level "
        "FirstSession component."
    )
    destructured = {s.strip() for s in m.group(1).split(",") if s.strip()}
    assert "bootstrap" in destructured, (
        f"`bootstrap` not destructured from useAuth() in "
        f"FirstSession. Destructured: {sorted(destructured)}"
    )


# ── S2.F — Phase C ESLint rules pin the B3 pattern ──────────────────
CRACO_CONFIG = REPO / "frontend/craco.config.js"


def test_s2_f_craco_eslint_pins_b3_pattern():
    """Phase C — `react/jsx-no-undef` + `no-undef` MUST be enabled
    at the craco level so future cherry-picks can't smuggle the B3
    pattern back in without breaking the build. The MCP lint tool's
    config doesn't read craco, but `webpack`'s eslint-loader does."""
    src = CRACO_CONFIG.read_text(encoding="utf-8")
    # Both rules wired as `error` (not `warn`) so build fails.
    assert re.search(
        r'"react/jsx-no-undef":\s*"error"', src,
    ), "craco.config.js missing `react/jsx-no-undef: error` rule"
    assert re.search(
        r'"no-undef":\s*"error"', src,
    ), "craco.config.js missing `no-undef: error` rule"


# ── S2.G — AttachDocumentModal `Search` icon import (B3 caught) ────
ATTACH_DOC = REPO / "frontend/src/components/solva/AttachDocumentModal.jsx"


def test_s2_g_attach_document_modal_imports_search_icon():
    """B3 false-green caught by Phase C ESLint rules — the
    `<Search />` icon at line ~201 inside the journal-tab JSX
    referenced an undeclared symbol. Pin the fix.

    Anchor chain: the `Search` lucide icon is imported from
    `lucide-react` AND used in JSX. Without the import the
    journal tab would have thrown `ReferenceError` on render."""
    src = ATTACH_DOC.read_text(encoding="utf-8")
    m = re.search(
        r'import\s*\{\s*([^}]+)\s*\}\s*from\s*"lucide-react"', src,
    )
    assert m, "lucide-react import missing"
    imported = {s.strip() for s in m.group(1).split(",") if s.strip()}
    assert "Search" in imported, (
        f"`Search` lucide icon not imported in AttachDocumentModal "
        f"but it's used in JSX at the journal-tab search field. "
        f"Imported: {sorted(imported)}"
    )
    # Anti-regression — `<Search` is actually used in JSX (proves the
    # import isn't dead).
    assert re.search(r"<\s*Search\b", src), (
        "`Search` icon imported but not used in JSX — dead import."
    )


# ── S2.H — WorkStudio top-level component has `useNavigate` ─────────
WORK_STUDIO = REPO / "frontend/src/pages/WorkStudio.jsx"


def test_s2_h_work_studio_top_level_has_use_navigate():
    """B3 false-green caught by Phase C ESLint rules — the top-level
    `WorkStudio` component called `navigate(...)` inside a
    `<DocumentCardsSection onOpenDocument>` callback at line ~669
    but never called `useNavigate()` itself. The `navigate` symbol
    in scope at line 213 belongs to the SIBLING `BriefDrawer`
    component, not to `WorkStudio`. Pin the fix.

    Anchor chain: the top-level `WorkStudio` function body MUST
    contain a `const navigate = useNavigate();` call BEFORE the
    `<DocumentCardsSection onOpenDocument` JSX where the callback
    references it."""
    src = WORK_STUDIO.read_text(encoding="utf-8")
    body = _function_body(src, "WorkStudio")
    assert body, "Top-level `WorkStudio` function body missing"
    body_stripped = _strip_js_comments(body)
    assert "const navigate = useNavigate();" in body_stripped, (
        "Top-level WorkStudio component no longer calls "
        "`useNavigate()`. The line-669 navigate(...) call site "
        "would throw `ReferenceError` at runtime."
    )
