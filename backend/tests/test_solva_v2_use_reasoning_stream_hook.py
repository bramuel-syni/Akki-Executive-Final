"""Solva v2 — Slice 3b (2026-05-29) source-strict contracts for the
frontend reasoning-stream hook + ticker + per-slide state plumbing.

Source-strict guards complement the optional Playwright runtime tests
(progressive-render + ticker visual). The source layer is what CI
runs unconditionally; runtime tests are nice-to-have when a real
preview URL is available.
"""
from __future__ import annotations

import re
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
HOOK = REPO / "frontend" / "src" / "hooks" / "useSolvaReasoningStream.js"
TICKER = REPO / "frontend" / "src" / "components" / "solva" / "artefact_v2" / "SolvaReasoningTicker.jsx"
ORCH = REPO / "frontend" / "src" / "components" / "solva" / "artefact_v2" / "SolvaArtefactV2.jsx"
SHELL = REPO / "frontend" / "src" / "components" / "solva" / "artefact_v2" / "SlideShell.jsx"
SLIDES = REPO / "frontend" / "src" / "components" / "solva" / "artefact_v2" / "slides"


# ─────────────────────────────────────────────────────────────────
# A. useSolvaReasoningStream — hook surface contract
# ─────────────────────────────────────────────────────────────────


def test_hook_exists_and_default_exports():
    assert HOOK.is_file(), "useSolvaReasoningStream.js must exist."
    src = HOOK.read_text(encoding="utf-8")
    assert "export default function useSolvaReasoningStream" in src


def test_hook_parses_locked_three_event_types():
    """The hook MUST handle exactly the 3 wire event names from Slice 3a:
        solva.reasoning.script · solva.reasoning · complete
    """
    src = HOOK.read_text(encoding="utf-8")
    for evname in ("solva.reasoning.script", "solva.reasoning", "complete"):
        assert f'ev.event === "{evname}"' in src or f"'{evname}'" in src, (
            f"Hook must branch on event name {evname!r}."
        )


def test_hook_state_shape_carries_all_locked_fields():
    """The hook's exported state shape must include the contract fields
    enumerated in the Slice 3b brief."""
    src = HOOK.read_text(encoding="utf-8")
    for field in (
        "events",
        "currentLayer",
        "currentLayerName",
        "currentStep",
        "slideReadyMap",
        "totalEvents",
        "isComplete",
        "status",
        "error",
        "replayMode",
    ):
        assert field in src, f"Hook state must carry {field!r}."


def test_hook_supports_replay_zero_url_override():
    """The hook MUST honor the `?replay=0` URL override by bypassing
    the SSE call and marking every slide ready up front."""
    src = HOOK.read_text(encoding="utf-8")
    assert "_isReplayBypass" in src
    assert "_resolveReplayMode" in src, (
        "Hook must use the `_resolveReplayMode()` helper to surface the "
        "URL override as a discrete string mode."
    )
    assert 'sp.get("replay")' in src
    # Bypass path mark slides ready
    assert "_emptySlideMap(true)" in src


def test_hook_resolves_replay_mode_to_discrete_string():
    """Slice 3b correction (2026-05-29): the hook MUST resolve the
    `?replay` URL param to one of three discrete string modes —
    'replay' (default + ?replay=1/true/on/yes), 'instant' (?replay=0/
    false/off/no), or 'live' (reserved for in-flight broadcast,
    parked). The artefact root surfaces this verbatim as
    `data-solva-v2-replay-mode`."""
    src = HOOK.read_text(encoding="utf-8")
    assert 'return "instant"' in src
    assert 'return "replay"' in src
    # The default-when-no-param branch must return "replay" not false.
    assert 'if (!sp.has("replay")) return "replay"' in src


def test_hook_does_not_force_all_slides_ready_on_event_complete():
    """Slice 3b correction (2026-05-29): the hook MUST NOT short-circuit
    the slide-state machine by force-flipping all 13 slides to ready
    when the SSE wire-close event fires. Each slide must transition
    strictly via its own slide.ready event so the visual progression
    stays coherent with the ticker's layer-by-layer narration.

    The synthesizer emits all 13 slide.ready events BEFORE
    session.complete arrives, so the map naturally populates without
    needing the safety net."""
    src = HOOK.read_text(encoding="utf-8")
    # Locate the event:"complete" branch
    m = re.search(r'ev\.event === "complete"\s*\)\s*\{([\s\S]*?)\}\s*else if', src)
    assert m, "Could not locate the event:complete branch in the hook."
    branch = m.group(1)
    # The branch must NOT contain a slideReadyMap mass-update.
    assert "LOCKED_SLIDE_KINDS.reduce" not in branch, (
        "The event:complete branch must NOT force all slides ready. "
        "Slice 3b correction (2026-05-29) requires each slide to flip "
        "via its own slide.ready event for visual coherence."
    )
    assert "slideReadyMap" not in branch, (
        "The event:complete branch must NOT mutate slideReadyMap."
    )


def test_hook_uses_locked_fourteen_slide_kinds():
    """The hook's LOCKED_SLIDE_KINDS array must enumerate exactly the
    14 contract kinds (13 original + bias_inventory from Slice 4),
    matching artefact_schema."""
    src = HOOK.read_text(encoding="utf-8")
    for kind in (
        "cover", "headline",
        "tensions_overview", "per_tension",
        "scenarios_overview", "per_scenario_table", "sensitivity",
        "reflection", "bias_inventory",
        "pathway", "decision_logic", "risk_mitigation",
        "methodological_honesty", "in_closing",
    ):
        assert f'"{kind}"' in src, f"Hook LOCKED_SLIDE_KINDS missing {kind!r}."


def test_hook_aborts_in_flight_request_on_unmount():
    src = HOOK.read_text(encoding="utf-8")
    assert "AbortController" in src
    assert "abort()" in src


# ─────────────────────────────────────────────────────────────────
# B. SlideShell — per-slide state attribute contract
# ─────────────────────────────────────────────────────────────────


def test_slide_shell_carries_slide_state_attribute():
    src = SHELL.read_text(encoding="utf-8")
    assert "data-solva-v2-slide-state" in src, (
        "SlideShell root must carry the data-solva-v2-slide-state attribute "
        "so the tester can probe loading → ready transitions."
    )
    # The default state for an unspecified slideState must be "ready"
    # so existing tests (Slice 2b multi-viewport probe etc.) keep passing.
    assert 'slideState = "ready"' in src


def test_slide_shell_renders_skeleton_when_loading():
    src = SHELL.read_text(encoding="utf-8")
    assert "SlideSkeleton" in src
    assert 'showSkeleton ? <SlideSkeleton />' in src
    assert 'solva-v2-slide-skeleton' in src


def test_slide_skeleton_uses_brand_purple_short_name_utilities():
    """Wave 4.2.followup.2 — skeleton tints MUST use `bg-ned-purple/N`
    short-name utilities. The hex-CSS-var-with-opacity-modifier
    syntax (`bg-[var(--ned-purple)]/15`) silently fails."""
    src = SHELL.read_text(encoding="utf-8")
    assert "bg-ned-purple/" in src, "Skeleton must use bg-ned-purple/N short-name."
    # And must NOT use the broken hex-var-with-opacity form
    assert not re.search(
        r"bg-\[var\(--ned-purple\)\]/\d+", src
    ), "Skeleton must NOT use bg-[var(--ned-purple)]/N (silently fails)."


# ─────────────────────────────────────────────────────────────────
# C. Every slide threads slideState through to SlideShell
# ─────────────────────────────────────────────────────────────────


def test_all_fourteen_slides_thread_slide_state_to_shell():
    files = list(SLIDES.glob("*.jsx"))
    assert len(files) == 14
    offenders = []
    for path in files:
        src = path.read_text(encoding="utf-8")
        if "slideState" not in src:
            offenders.append(f"{path.name} does not destructure slideState")
        elif "slideState={slideState}" not in src:
            offenders.append(f"{path.name} does not forward slideState to SlideShell")
    assert not offenders, "Slide-state plumbing gaps:\n  " + "\n  ".join(offenders)


# ─────────────────────────────────────────────────────────────────
# D. Orchestrator — hook subscription + ticker mount + identity stamp
# ─────────────────────────────────────────────────────────────────


def test_orchestrator_subscribes_to_reasoning_stream():
    src = ORCH.read_text(encoding="utf-8")
    assert "import useSolvaReasoningStream" in src
    assert "useSolvaReasoningStream(sessionId" in src


def test_orchestrator_mounts_reasoning_ticker():
    src = ORCH.read_text(encoding="utf-8")
    assert "import SolvaReasoningTicker" in src
    assert "<SolvaReasoningTicker" in src


def test_orchestrator_root_carries_identity_stamp():
    """Slice 3b additive — locked attribute that any downstream audit
    tool (e1_tester, identity-audit pytest, CMS scans) can read as a
    positive identity signal."""
    src = ORCH.read_text(encoding="utf-8")
    assert 'data-solva-v2-identity-stamp="solva-canonical"' in src


def test_orchestrator_replay_mode_attr_reflects_resolved_mode():
    """Slice 3b correction (2026-05-29): the artefact root's
    `data-solva-v2-replay-mode` attribute MUST reflect the hook's
    resolved `replayMode` string verbatim (not a boolean coerce). The
    URL `?replay=0` must surface as `data-solva-v2-replay-mode="instant"`
    on the artefact root, not `"replay"`."""
    src = ORCH.read_text(encoding="utf-8")
    assert "data-solva-v2-replay-mode={stream.replayMode}" in src, (
        "Artefact root must surface `stream.replayMode` directly. The "
        "prior boolean-coerce code (`stream.replayMode ? 'replay' : "
        "'live'`) collapsed the 'instant' bypass state into 'replay', "
        "breaking the tester's URL-override probe."
    )


def test_orchestrator_computes_per_slide_state_attribute():
    """The orchestrator must compute slideState per slide from the
    hook's slideReadyMap (loading until the slide.ready event fires)."""
    src = ORCH.read_text(encoding="utf-8")
    assert "stream.slideReadyMap" in src
    # Three states recognised
    assert "loading" in src
    assert '"ready"' in src
    assert '"placeholder"' in src
    # isPlaceholder branch — the empty-arc per_tension placeholder
    # surfaces as slideState="placeholder" once the slide.ready arrives.
    assert "isPlaceholder" in src


def test_orchestrator_hook_called_before_early_returns():
    """React rules-of-hooks: useSolvaReasoningStream must be called
    UNCONDITIONALLY before any early-return branch (loading / error /
    integrity_failed). The hook call line must precede the first
    `if (state.status === "loading")` branch."""
    src = ORCH.read_text(encoding="utf-8")
    hook_idx = src.find("useSolvaReasoningStream(sessionId")
    early_idx = src.find('if (state.status === "loading")')
    assert 0 < hook_idx < early_idx, (
        "useSolvaReasoningStream(sessionId, ...) must be called before "
        "the loading early-return so React's rules-of-hooks holds."
    )


# ─────────────────────────────────────────────────────────────────
# E. Live ticker — Slice 3b visual contract
# ─────────────────────────────────────────────────────────────────


def test_ticker_renders_layer_display_names():
    """The ticker MUST convert canonical layer_name to a founder-readable
    label (Frame Audit / Surface / Depth / Synthesis / Reflection). No
    theatricalisation."""
    src = TICKER.read_text(encoding="utf-8")
    for friendly in ("Frame Audit", "Surface", "Depth", "Synthesis", "Reflection"):
        assert f'"{friendly}"' in src, (
            f"Ticker must include the friendly layer display name {friendly!r}."
        )


def test_ticker_collapse_pill_uses_solva_canonical_copy():
    """On session.complete the ticker collapses to a compact pill with
    EXACTLY the locked copy: 'Session complete · 5 layers · 14 slides'."""
    src = TICKER.read_text(encoding="utf-8")
    assert "Session complete · 5 layers · 14 slides" in src


def test_ticker_two_stage_post_complete_lifecycle():
    """First 30s after session.complete → pill. After 30s → icon-button
    stub (Slice 3b ships the stub; the side-panel re-open lands in
    Slice 7). The 30s window was set in the Slice 3b correction
    (2026-05-29) after the tester reported the prior 8s window was
    too short — late-arriving viewers reliably saw only the post-pill
    icon. Trust pillar 1 needs the pill visible long enough that a
    returning founder catches it."""
    src = TICKER.read_text(encoding="utf-8")
    assert "postCompleteStage" in src
    assert '"pill"' in src
    assert '"icon"' in src
    assert "30_000" in src or "30000" in src, (
        "Pill duration must be 30 seconds (was 8s before the Slice 3b "
        "correction)."
    )


def test_ticker_uses_brand_purple_short_name_utilities():
    """Wave 4.2.followup.2 — ticker tints MUST use `*-ned-purple/N`
    short-name utilities, never `bg-[var(--ned-purple)]/N`."""
    src = TICKER.read_text(encoding="utf-8")
    # Positive
    assert "ned-purple/" in src or "border-ned-purple" in src
    # Negative
    assert not re.search(r"bg-\[var\(--ned-purple\)\]/\d+", src)
    assert not re.search(r"border-\[var\(--ned-purple\)\]/\d+", src)


def test_ticker_does_not_theatricalise():
    """The ticker is the most exposed surface for theatricality drift.
    Source-strict guard against forbidden phrases."""
    src = TICKER.read_text(encoding="utf-8")
    forbidden = (
        "thinking deeply", "pondering", "looking deeply",
        "let me", "would you like", "you should", "you must",
        "intuiting", "channeling", "sensing the",
    )
    lower = src.lower()
    for needle in forbidden:
        assert needle not in lower, f"Ticker must not contain {needle!r}."


def test_ticker_carries_locked_testids():
    """Tester contract — ticker exposes its sub-elements via data-testid."""
    src = TICKER.read_text(encoding="utf-8")
    for tid in (
        "solva-v2-ticker",
        "solva-v2-ticker-step",
        "solva-v2-ticker-layer-label",
        "solva-v2-ticker-pill",
        "solva-v2-ticker-pill-text",
        "solva-v2-ticker-log-icon",
    ):
        assert f'data-testid="{tid}"' in src, f"Ticker missing testid={tid!r}."
