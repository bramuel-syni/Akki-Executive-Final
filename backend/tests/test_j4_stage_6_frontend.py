"""J4 (Stage 6) — Frontend behavior tests.

Spec ref: `AKKI_ONBOARDING_SPEC.md` v1.1 §3 Stage 6 + ratified
gaps G29, G30, G31. Anti-source-string-assertion discipline
(closeout §5.8): every test asserts a CONTROL-FLOW CHAIN, not
the mere presence of a literal string in the source.

  J4.F1 — `FirstSession.jsx` Door C (solve) routes the user to
          `/app/solva?starter=<top_of_mind>`. Three anchors in the
          SAME `if (door === "solve")` branch:
            - `intake?.top_of_mind` is the source.
            - `?starter=${encodeURIComponent(starter)}`.
            - `navigate("/app/solva${q}")`.
  J4.F2 — `SolvaApp.jsx` captures `?starter=` once on mount and
          forwards it via the `intakeStarter` prop to
          `SolvaLanding`. Three anchors:
            - `useSearchParams` imported.
            - `params.get("starter")`.
            - `<SolvaLanding ... intakeStarter={...}>`.
  J4.F3 — `SolvaLanding.jsx` `onSelectCard` propagates the starter
          onto the phase-d/session/new URL. Two anchors in the
          SAME function body: `intakeStarter` referenced AND
          `params.set("starter", ...)`.
  J4.F4 — `SolvaPhaseDSession.jsx` boot useEffect reads
          `?starter=` from URL AND falls back to `GET
          /me/first-session` when bare AND sets the framing draft.
          Four anchors in the SAME boot function:
            - `searchParams.get("starter")`.
            - `setDraft(urlStarter)` branch.
            - `api.get("/me/first-session")` fallback.
            - `setDraft(fallback)`.
  J4.F5 — `SolvaPhaseDSession.jsx` POSTs `first-chat-seen` on
          first mount. Two anchors:
            - `api.post(...)` is called.
            - URL contains `/users/me/onboarding-status/first-chat-seen`.
  J4.F6 — G29 verbatim Help tooltip copy. Two anchors must
          coexist in the same JSX wrapper (testid +
          verbatim G29 copy); legacy b48ee23 placeholder copy
          must be ABSENT (anti-regression).
  J4.F7 — Help tooltip DOM-unconditional (closeout §5.1, §5.7).
          The `data-testid="help-tooltip"` element MUST emit WITHOUT
          a `&& (...)` conditional gate immediately preceding it.
          Visibility is governed by `data-tooltip-visible` attribute
          / CSS classes.
  J4.F8 — Onboarding completion has NO non-spec celebration copy.
          The spec §3 Stage 6 does NOT define a celebration string,
          so the implementation MUST NOT introduce one.
  J4.F9 — Anti-regression: the legacy `?intent=` query param is
          gone from FirstSession.jsx Door C solve branch (replaced
          by `?starter=`).
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FIRSTSESSION = REPO / "frontend/src/pages/FirstSession.jsx"
SOLVA_APP = REPO / "frontend/src/pages/SolvaApp.jsx"
SOLVA_LANDING = REPO / "frontend/src/components/solva/SolvaLanding.jsx"
PHASE_D_SESSION = REPO / "frontend/src/pages/SolvaPhaseDSession.jsx"
APPSHELL = REPO / "frontend/src/components/layout/AppShell.jsx"


def _solve_branch(first_session_src: str) -> str:
    """Slice the `if (door === "solve") { ... }` branch out of the
    `choose` useCallback. Lets J4.F1 assert that anchors are colocated
    in the SAME branch rather than merely "present somewhere in the
    file" (which would be source-string assertion — closeout §5.8)."""
    m = re.search(
        r"if\s*\(\s*door\s*===\s*\"solve\"\s*\)\s*\{",
        first_session_src,
    )
    if not m:
        return ""
    start = m.end()
    depth = 1
    i = start
    while i < len(first_session_src) and depth > 0:
        ch = first_session_src[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        i += 1
    return first_session_src[start : i - 1]


def _function_body(src: str, name: str) -> str:
    """Slice the body of an async fn / arrow fn / function named
    `name` from the source. Returns "" if not found. Best-effort
    brace-matched slicing — handles both `function name(` and
    arrow `const name = ... => {`."""
    # Match either `function name(` or `const name = ... => {` or
    # `name = async (...) => {` or `name(` (method shorthand).
    candidates = [
        rf"async\s+function\s+{re.escape(name)}\s*\(",
        rf"function\s+{re.escape(name)}\s*\(",
        rf"const\s+{re.escape(name)}\s*=\s*[^;]*=>\s*\{{",
        rf"\b{re.escape(name)}\s*=\s*useCallback\(",
        rf"\b{re.escape(name)}\s*\(",
    ]
    for pat in candidates:
        m = re.search(pat, src)
        if not m:
            continue
        # Find the next `{` after the match start.
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


# ── J4.F1 — Door C uses ?starter= with intake.top_of_mind ────────────
def test_j4_f1_first_session_solve_door_uses_starter_param_chain():
    """Three-anchor chain in the `if (door === "solve")` branch
    of `FirstSession.jsx::choose`: intake.top_of_mind sourced AND
    `?starter=${...}` AND navigate to /app/solva${q}."""
    src = FIRSTSESSION.read_text(encoding="utf-8")
    branch = _solve_branch(src)
    assert branch, "Could not locate the `door === \"solve\"` branch."
    # Anchor 1 — intake.top_of_mind is the source of the seed.
    assert "intake?.top_of_mind" in branch, (
        "Door C solve branch no longer reads intake?.top_of_mind."
    )
    # Anchor 2 — the URL uses `?starter=` (spec verbatim).
    assert "?starter=" in branch, (
        "Door C solve branch URL no longer uses `?starter=` "
        "(spec §3 Stage 6 step 1 verbatim contract)."
    )
    # Anchor 3 — navigate target is /app/solva (NOT /app/chat).
    assert "navigate(`/app/solva" in branch or 'navigate("/app/solva' in branch, (
        "Door C solve branch navigate target changed away from "
        "/app/solva — spec §3 Stage 6 entry point regression."
    )


# ── J4.F2 — SolvaApp captures ?starter= and forwards via prop ────────
def test_j4_f2_solva_app_captures_starter_and_forwards_to_landing():
    """`SolvaApp.jsx` MUST capture the URL `?starter=` once on mount
    and forward it via the `intakeStarter` prop to `SolvaLanding`."""
    src = SOLVA_APP.read_text(encoding="utf-8")
    # Anchor 1 — useSearchParams imported.
    assert "useSearchParams" in src, (
        "SolvaApp.jsx no longer imports useSearchParams — "
        "URL capture chain broken."
    )
    # Anchor 2 — params.get("starter") referenced.
    assert 'params.get("starter")' in src, (
        "SolvaApp.jsx no longer reads `params.get(\"starter\")`."
    )
    # Anchor 3 — prop forwarded to SolvaLanding.
    assert re.search(r"intakeStarter\s*=\s*\{[^}]*starter[^}]*\}", src) or (
        "intakeStarter={starter}" in src
    ), (
        "SolvaApp.jsx no longer forwards the captured starter to "
        "<SolvaLanding intakeStarter={...}>."
    )


# ── J4.F3 — SolvaLanding propagates starter onto Phase D URL ─────────
def test_j4_f3_solva_landing_forwards_starter_to_phase_d_url():
    """`SolvaLanding.jsx::onSelectCard` MUST reference `intakeStarter`
    and call `params.set("starter", ...)` in the SAME function body."""
    src = SOLVA_LANDING.read_text(encoding="utf-8")
    body = _function_body(src, "onSelectCard")
    assert body, "Could not locate `onSelectCard` function body."
    # Anchor 1 — intakeStarter referenced in the same function body.
    assert "intakeStarter" in body, (
        "SolvaLanding.onSelectCard no longer references intakeStarter."
    )
    # Anchor 2 — params.set("starter", ...) called.
    assert 'params.set("starter"' in body, (
        "SolvaLanding.onSelectCard no longer calls "
        "`params.set(\"starter\", ...)`."
    )


# ── J4.F4 — Phase D boot reads ?starter= AND fallback /me/first-session
def test_j4_f4_phase_d_session_reads_starter_and_sets_draft():
    """`SolvaPhaseDSession.jsx` boot useEffect MUST contain ALL of:
      - `searchParams.get("starter")` (URL path),
      - `setDraft(urlStarter)` (URL-seeded draft),
      - `api.get("/me/first-session")` (fallback path),
      - `setDraft(fallback)` (fallback-seeded draft).
    All four in the SAME function (the boot async function)."""
    src = PHASE_D_SESSION.read_text(encoding="utf-8")
    # Anchor — `api` import from `@/lib/api`.
    assert re.search(r'import\s+\{\s*api\s*\}\s+from\s+"@/lib/api"', src), (
        "SolvaPhaseDSession.jsx no longer imports `api` from "
        "`@/lib/api` — fallback chain broken."
    )
    # Slice the boot function body.
    body = _function_body(src, "boot")
    assert body, "Could not locate `boot` function body."
    # Anchor 1 — URL starter read.
    assert 'searchParams.get("starter")' in body, (
        "Boot no longer reads `searchParams.get(\"starter\")`."
    )
    # Anchor 2 — URL-seeded draft.
    assert "setDraft(urlStarter)" in body, (
        "Boot no longer calls `setDraft(urlStarter)` — URL "
        "starter seeding broken."
    )
    # Anchor 3 — fallback API call.
    assert 'api.get("/me/first-session")' in body, (
        "Boot no longer falls back to `api.get(\"/me/first-session\")`."
    )
    # Anchor 4 — fallback-seeded draft.
    assert "setDraft(fallback)" in body, (
        "Boot no longer calls `setDraft(fallback)` — fallback "
        "starter seeding broken."
    )


# ── J4.F5 — Phase D boot POSTs first-chat-seen ───────────────────────
def test_j4_f5_phase_d_session_posts_first_chat_seen_on_mount():
    """`SolvaPhaseDSession.jsx` boot MUST POST
    `/users/me/onboarding-status/first-chat-seen` so the
    onboarding completion flag rolls true on first chat."""
    src = PHASE_D_SESSION.read_text(encoding="utf-8")
    body = _function_body(src, "boot")
    assert body, "Could not locate `boot` function body."
    # Anchor — api.post(...) to the first-chat-seen endpoint.
    assert (
        'api.post("/users/me/onboarding-status/first-chat-seen")' in body
    ), (
        "Boot no longer POSTs the first-chat-seen endpoint — "
        "onboarding completion accounting broken."
    )


# ── J4.F6 — G29 verbatim Help tooltip copy ───────────────────────────
def test_j4_f6_g29_verbatim_help_tooltip_copy():
    """Spec §6 G29 (ratified): Help tooltip copy verbatim. Two
    anchors must coexist in the same wrapper (testid + verbatim
    copy); legacy b48ee23 placeholder MUST be absent."""
    src = APPSHELL.read_text(encoding="utf-8")
    idx = src.find('data-testid="help-tooltip"')
    assert idx != -1, "help-tooltip testid missing from AppShell.jsx"
    # Slice a wide enough window around the testid to capture the
    # whole tooltip wrapper.
    window = src[idx : idx + 1200]
    assert (
        "Tap Help any time. Akki has a built-in tour of every screen."
        in window
    ), (
        f"G29 verbatim copy missing from help-tooltip wrapper. "
        f"Window: {window[:400]!r}"
    )
    # Anti-regression — legacy b48ee23 copy must be gone.
    assert "Full reference of what Akki can do." not in window, (
        "Legacy b48ee23 help-tooltip copy 'Full reference of what "
        "Akki can do.' still present. J4 G29 refinement not applied."
    )


# ── J4.F7 — Help tooltip renders DOM-unconditionally ─────────────────
def test_j4_f7_help_tooltip_dom_unconditional():
    """G31 + closeout §5.1, §5.7: the help-tooltip root MUST emit
    without a `&& (...)` JSX conditional gate immediately preceding
    it. Visibility is governed by the `data-tooltip-visible`
    attribute / CSS class flip (pointer-events / opacity)."""
    src = APPSHELL.read_text(encoding="utf-8")
    idx = src.find('data-testid="help-tooltip"')
    assert idx != -1, "help-tooltip testid missing from AppShell.jsx"
    # Look ~200 chars before the testid for a `&& (` gate pattern.
    # The legacy version was `{onbStatus?.help_tooltip?.show && (<div ...>`
    # — a chevron-paren gate immediately before the tooltip root.
    window_start = max(0, idx - 250)
    pre = src[window_start:idx]
    suspicious = re.search(
        r"&&\s*\(\s*<\s*div\s+[^>]*$", pre,
    )
    assert suspicious is None, (
        "help-tooltip root appears behind a `&& (` conditional gate "
        "— violates the DOM-unconditional rule (closeout §5.1)."
    )
    # Positive confirmation — the data-tooltip-visible attribute is
    # present (the spec mechanism for show/hide).
    window = src[idx : idx + 800]
    assert "data-tooltip-visible" in window, (
        "help-tooltip wrapper no longer carries "
        "`data-tooltip-visible` attribute — visibility mechanism "
        "regressed."
    )


# ── J4.F8 — No non-spec onboarding-completion celebration copy ───────
def test_j4_f8_no_non_spec_onboarding_celebration_copy():
    """Spec §3 Stage 6 does NOT define a celebration string. The
    implementation MUST NOT introduce one (verbatim-spec-copy
    invariant, closeout §5.3)."""
    forbidden_phrases = [
        "Welcome to Akki",
        "Welcome aboard",
        "You're all set",
        "Congratulations",
        "Onboarding complete",
        "Onboarding is complete",
        "Journey complete",
        "All set!",
    ]
    files_to_check = [
        FIRSTSESSION,
        SOLVA_APP,
        SOLVA_LANDING,
        PHASE_D_SESSION,
        APPSHELL,
    ]
    offenders = []
    for f in files_to_check:
        text = f.read_text(encoding="utf-8")
        for phrase in forbidden_phrases:
            if phrase in text:
                offenders.append((f.name, phrase))
    assert not offenders, (
        f"Non-spec onboarding celebration copy introduced: "
        f"{offenders}. Spec §3 Stage 6 verbatim contract violated."
    )


# ── J4.F9 — Anti-regression: no `?intent=` residue in solve branch ───
def test_j4_f9_no_intent_param_residue_in_solve_branch():
    """Pre-J4, FirstSession.jsx Door C used `?intent=<top_of_mind>`.
    The J4 G30 contract renames this to `?starter=` (spec verbatim).
    No residual `?intent=` query string may remain in the solve
    branch."""
    src = FIRSTSESSION.read_text(encoding="utf-8")
    branch = _solve_branch(src)
    assert branch, "Could not locate the `door === \"solve\"` branch."
    assert "?intent=" not in branch, (
        "Residual `?intent=` query param in Door C solve branch — "
        "J4 G30 rename to `?starter=` is incomplete."
    )
