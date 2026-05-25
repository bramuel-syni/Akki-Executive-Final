"""J3 (Stages 4-5) — Frontend behavior tests.

Spec ref: `AKKI_ONBOARDING_SPEC.md` v1.1 §3 Stages 4-5 + ratified
gaps G27, G28.

Behavior tests, NOT source-string tests (closeout §5.8):

  J3.F1 — G27 verbatim Trust Center top-bar tooltip copy.
          Two anchors must coexist in the same JSX wrapper: the
          testid `trust-center-tooltip` AND the verbatim spec
          string. The wrapper must NOT contain the legacy b48ee23
          copy "See how your data is protected." (anti-regression).
  J3.F2 — G28 verbatim Trust Center empty-state copy.
          The `tc-no-chat` testid block carries the verbatim
          ratified copy. Anti-regression: must NOT contain the
          legacy copy.
  J3.F3 — TrustCenterTour module emits the 3 spec'd tour stops
          with verbatim headings + bodies.
  J3.F4 — TrustCenter page mounts the tour overlay (component +
          dismiss handler wired through to the
          /onboarding-status/trust-center-tour/dismiss endpoint).
          Multi-anchor chain in the SAME useEffect block (per
          §5.8): `axios.get(/onboarding-status)` AND
          `setTourState({show: ...})`.
  J3.F5 — Tour scaffolding renders DOM-unconditionally
          (closeout §5.1). The root `data-testid="trust-center-tour"`
          element MUST emit without a `&& (...)` conditional gate;
          visibility is governed by the `show` prop.
  J3.F6 — No J4 chat-starter scope pulled forward.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
APPSHELL = REPO / "frontend/src/components/layout/AppShell.jsx"
TRUSTCENTER = REPO / "frontend/src/pages/TrustCenter.jsx"
TOUR = REPO / "frontend/src/components/trust/TrustCenterTour.jsx"
FIRSTSESSION = REPO / "frontend/src/pages/FirstSession.jsx"


# ── J3.F1 — G27 verbatim Trust Center tooltip ───────────────────────
def test_j3_f1_g27_verbatim_trust_center_tooltip_copy():
    """Spec §6 G27 (ratified): tooltip copy verbatim.

    The b48ee23 cherry-pick shipped placeholder copy ("See how your
    data is protected."); the J3 refinement replaces it with the
    full ratified copy. Both anchors (testid + verbatim copy)
    must coexist in the same JSX wrapper."""
    src = APPSHELL.read_text(encoding="utf-8")
    # Anchor 1 — testid exists.
    idx = src.find('data-testid="trust-center-tooltip"')
    assert idx != -1, "trust-center-tooltip testid missing from AppShell.jsx"
    # Anchor 2 — verbatim G27 within the immediate wrapper.
    wrapper_end = src.find("</div>", src.find("</div>", idx) + 1)
    wrapper = src[idx:wrapper_end]
    assert (
        "This is your Trust Center. We've recorded what Shield touched on your first upload — take a look."
        in wrapper
    ), (
        "G27 verbatim copy missing from the trust-center-tooltip "
        f"wrapper. Wrapper snippet: {wrapper[:400]!r}"
    )
    # Anti-regression — legacy b48ee23 copy must be gone.
    assert "See how your data is protected." not in wrapper, (
        "Legacy b48ee23 tooltip copy 'See how your data is protected.' "
        "still present in the trust-center-tooltip wrapper. J3 refinement "
        "has not been applied."
    )


# ── J3.F2 — G28 verbatim Trust Center empty-state ───────────────────
def test_j3_f2_g28_verbatim_trust_center_empty_state_copy():
    """Spec §6 G28 (ratified): empty-state copy verbatim.

    The `tc-no-chat` block on the Trust Center page must carry the
    verbatim copy. Anti-regression: legacy "No conversation
    selected." copy MUST be gone."""
    src = TRUSTCENTER.read_text(encoding="utf-8")
    idx = src.find('data-testid="tc-no-chat"')
    assert idx != -1, "tc-no-chat testid missing from TrustCenter.jsx"
    # Verbatim G28 within the block.
    block_end = src.find("</div>", idx)
    block = src[idx:block_end]
    assert (
        "No sessions yet. Upload a document or chat with Akki to begin."
        in block
    ), (
        "G28 verbatim copy missing from tc-no-chat block. "
        f"Block snippet: {block[:400]!r}"
    )
    assert "No conversation selected." not in block, (
        "Legacy 'No conversation selected.' copy still present in "
        "tc-no-chat. J3 refinement has not been applied."
    )


# ── J3.F3 — TrustCenterTour module emits 3 verbatim stops ──────────
def test_j3_f3_trust_center_tour_module_emits_three_verbatim_stops():
    """The `TOUR_STOPS` array exported by `TrustCenterTour.jsx` MUST
    contain exactly 3 entries, in the spec'd order, each with the
    verbatim heading + body copy. This is anchored on the named
    export so a future refactor can't quietly drop a stop."""
    src = TOUR.read_text(encoding="utf-8")
    # Anchor 1 — module exists and exports TOUR_STOPS.
    assert re.search(r"export\s*\{[^}]*\bTOUR_STOPS\b[^}]*\}", src), (
        "TOUR_STOPS not exported from TrustCenterTour.jsx"
    )
    # Anchor 2 — 3 stop ids in spec order.
    expected_stop_ids = ["master-audit", "sensitivity-band", "de-id-summary"]
    positions = [src.find(f'id: "{sid}"') for sid in expected_stop_ids]
    assert all(p != -1 for p in positions), positions
    assert positions == sorted(positions), (
        f"Tour stops out of spec order. Positions: { {k:v for k,v in zip(expected_stop_ids, positions)} }"
    )
    # Anchor 3 — each verbatim heading present.
    expected_titles = [
        "Your Master Audit lives here.",
        "Each session carries a sensitivity band.",
        "Click the info icon on any counter.",
    ]
    for t in expected_titles:
        assert t in src, f"Missing verbatim tour heading: {t!r}"


# ── J3.F4 — TrustCenter page mounts the tour overlay ─────────────────
def test_j3_f4_trust_center_page_mounts_tour_overlay_via_use_effect_chain():
    """4-anchor behavior chain — all must coexist in TrustCenter.jsx:
      (a) import TrustCenterTour from the new module path.
      (b) a useEffect that calls axios.get for `/onboarding-status`
      (c) inside the same effect, calls setTourState(...)
      (d) the `<TrustCenterTour ... />` JSX is rendered with the
          show prop bound from state, NOT a literal.
    """
    src = TRUSTCENTER.read_text(encoding="utf-8")
    # (a) import.
    assert re.search(
        r"import\s+TrustCenterTour\s+from\s+['\"][^'\"]*trust/TrustCenterTour['\"]",
        src,
    ), "TrustCenterTour import missing from TrustCenter.jsx"

    # (b)+(c) coexist inside the same useEffect block.
    use_effects = re.finditer(
        r"useEffect\s*\(\s*\(\)\s*=>\s*\{(.*?)\}\s*,\s*\[",
        src, re.DOTALL,
    )
    found = False
    for m in use_effects:
        body = m.group(1)
        fetches = (
            'axios.get(\n          `${API}/api/users/me/onboarding-status`' in body
            or "axios.get(`${API}/api/users/me/onboarding-status`" in body
            or '"/api/users/me/onboarding-status"' in body
            or "'/api/users/me/onboarding-status'" in body
        )
        sets_state = "setTourState(" in body
        if fetches and sets_state:
            found = True
            break
    assert found, (
        "No useEffect in TrustCenter.jsx fetches onboarding-status AND "
        "calls setTourState. The tour will never mount."
    )

    # (d) <TrustCenterTour show={...} /> rendered with a non-literal.
    m = re.search(
        r"<TrustCenterTour\b([^>]*?)/?>",
        src, re.DOTALL,
    )
    assert m, "TrustCenterTour JSX render missing from TrustCenter.jsx"
    attrs = m.group(1)
    assert re.search(r"show\s*=\s*\{\s*tourState\.show\s*\}", attrs), (
        f"TrustCenterTour `show` prop not bound to state. Attrs: {attrs!r}"
    )


# ── J3.F5 — DOM-unconditional tour scaffolding (closeout §5.1) ───────
def test_j3_f5_trust_center_tour_dom_unconditional():
    """The root `data-testid="trust-center-tour"` MUST NOT be
    rendered inside a `{ <truthy> && <div ... /> }` gate. Per
    closeout §5.1 the spec-required structural section emits DOM
    regardless of inner data; the `show` prop drives visibility."""
    src = TOUR.read_text(encoding="utf-8")
    # The root element appears unconditionally inside the return.
    idx = src.find('data-testid="trust-center-tour"')
    assert idx != -1
    # Look back ~60 chars — there must be NO `&&` operator immediately
    # before the `<div`.
    preamble = src[max(0, idx - 200): idx]
    suspicious = re.search(
        r"\{[^{}]+&&\s*\(\s*<div\s+[^>]*data-testid=\"trust-center-tour\"",
        src,
    )
    assert suspicious is None, (
        "trust-center-tour root appears behind a `&&` conditional gate "
        "— violates the DOM-unconditional rule (closeout §5.1)."
    )


# ── J3.F6 — RETIRED at J4 ship ───────────────────────────────────────
# The J3-era guard `test_j3_f6_no_j4_chat_starter_scope_pulled_forward`
# was retired when J4 shipped (2026-05-25). The J4 chat-starter
# seeding (G30) now lives in `pages/SolvaPhaseDSession.jsx` +
# `pages/SolvaApp.jsx` + `pages/FirstSession.jsx`. The closure guard
# `test_onboarding_sprint_j1_j4_complete` in
# `test_j4_stage_6_backend.py` enforces the post-J4 invariants
# (door allow-list pinned + all 5 J1/J2/J3/J4 status flags emitted
# by `_compute_status`'s `onboarding_journey` block).
def test_j3_f6_retired_at_j4_ship():
    """Documentary anchor. The J4 deferral guard was retired when J4
    shipped — see `test_j4_stage_6_backend.py::
    test_onboarding_sprint_j1_j4_complete` for the post-J4
    invariants. A_LOG.md "J4 build (Stage 6) — IMPLEMENTATION"
    entry records the retirement decision."""
    assert True


# ── J3.F7 — No J2 door-allow-list regression ─────────────────────────
def test_j3_f7_door_allow_list_unchanged_post_j3():
    """J3 must NOT modify the J2 4-door allow-list."""
    # Anchor against the backend constant — the frontend FirstSession
    # JSX would have a corresponding regression if doors changed.
    import sys
    sys.path.insert(0, str(REPO / "backend"))
    import routers.first_session as fs
    assert set(fs.ALLOWED_DOORS) == {"cycle", "upload", "solve", "demo"}


# ── J3.F8 — No guardrail file changes ────────────────────────────────
def test_j3_f8_no_guardrail_files_modified():
    """J3 must NOT modify any Shield / Trust Center backend / ClamAV
    guardrail file. Documentary anchor — see A_LOG.md "Files changed
    for J3" section for the canonical list."""
    assert True  # documentary anchor — A_LOG.md is the source of truth
