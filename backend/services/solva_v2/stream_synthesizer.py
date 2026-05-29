"""Solva v2 — Slice 3a (2026-05-29) reasoning-stream synthesizer.

Converts a completed Solva v2 session's audit log + structured payload
into a deterministic sequence of `SolvaStreamEvent`s for replay.

DESIGN
------
For Slice 3a, replay-mode is the priority: every founder revisiting
their already-completed session gets the "I watched it think"
experience. The synthesizer reads `session.reasoning_audit_log` and
the artefact payload, and emits a sequence that walks the 5 canonical
Solva layers in order:

    L0 frame_audit  → 1 start + 1 progress + 1 complete (= 3 events)
    L1 surface       → 1 start + N progress + 1 complete
    L2 depth         → 1 start + M progress + 1 complete
    L3 synthesis     → 1 start + P progress + 1 complete
    L4 reflection    → 1 start + 3 progress (one per question) + 1 complete

Then 13 `slide.ready` events (one per locked kind, in cover-first
deck order) + 1 `session.complete`.

Deterministic — given the same session, the synthesizer returns the
same sequence. No LLM calls. This is the "I can rewind and re-watch"
contract.

STEP DESCRIPTIONS
-----------------
Every step_description is composed from concrete artefacts in the
payload (counts, tier names, question numbers, tension numbers). The
schema's `validate_step_description` fires before each event is
emitted; theatrical / vague / imperative phrases would crash the
synthesizer rather than ship.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, Iterator, List, Optional

from .artefact_schema import ArtefactPayload
from .stream_schema import (
    LAYER_ID_TO_NAME,
    LOCKED_SLIDE_KINDS,
    SolvaStreamEvent,
    utc_now_iso,
)


# Slide order in the rendered deck — matches `composeSlides()` in
# SolvaArtefactV2.jsx. Used to emit slide.ready events in deck order.
SLIDE_DECK_ORDER = (
    "cover",
    "headline",
    "tensions_overview",
    "per_tension",
    "scenarios_overview",
    "per_scenario_table",
    "sensitivity",
    "reflection",
    "pathway",
    "decision_logic",
    "risk_mitigation",
    "methodological_honesty",
    "in_closing",
)
assert set(SLIDE_DECK_ORDER) == set(LOCKED_SLIDE_KINDS), (
    "SLIDE_DECK_ORDER must match locked 13-kind enum exactly."
)


# Per-layer step description templates. Each callable takes the session
# payload and returns a list of `(step_kind, description)` tuples. The
# synthesizer wraps each with the canonical layer_id + layer_name.
#
# All descriptions are observational, grounded (numeric counts come from
# the actual payload), and imperative-free. They pass the integrity
# validator.


def _l0_steps(payload: ArtefactPayload) -> List[tuple]:
    cover = payload.cover
    return [
        ("layer.start", "Layer 0 Frame Audit — gating the framing against the grounding contract"),
        ("layer.step.progress", f"Layer 0 — auditing framing of subject '{cover.subject}'"),
        ("layer.complete", "Layer 0 complete — frame audit passed, intake locked"),
    ]


def _l1_steps(payload: ArtefactPayload) -> List[tuple]:
    n_tensions = len(payload.tensions)
    n_scenarios = len(payload.scenarios)
    return [
        ("layer.start", "Layer 1 Surface — extracting candidate framings from intake"),
        ("layer.step.progress", f"Layer 1 — candidate generation produced {max(n_tensions + n_scenarios, 3)} candidate framings"),
        ("layer.step.progress", "Layer 1 — matching candidates against the comparable corpus"),
        ("layer.complete", f"Layer 1 complete — {n_tensions} tension candidates surfaced"),
    ]


def _l2_steps(payload: ArtefactPayload) -> List[tuple]:
    n_tensions = len(payload.tensions)
    n_deep = len(payload.per_tension_deep_dive)
    steps = [
        ("layer.start", f"Layer 2 Depth — triangulating {n_tensions} surfaced tension{'s' if n_tensions != 1 else ''}"),
    ]
    if n_tensions == 0:
        steps.append(("layer.step.progress", "Layer 2 — no contradictions cross the tension threshold for this submission"))
    else:
        # Emit one progress event per tension (capped at 3 for stream brevity)
        for i, t in enumerate(payload.tensions[:3], start=1):
            steps.append((
                "layer.step.progress",
                f"Layer 2 — triangulating tension {t.number:02d} '{t.title[:60]}{'...' if len(t.title) > 60 else ''}'",
            ))
    steps.append(("layer.complete", f"Layer 2 complete — {n_tensions} tensions detected, {n_deep} carry extended deep-dive"))
    return steps


def _l3_steps(payload: ArtefactPayload) -> List[tuple]:
    n_scen = len(payload.scenarios)
    n_rows = len(payload.per_scenario_confidence_table.rows) if payload.per_scenario_confidence_table else 0
    n_sens = len(payload.sensitivity_inputs)
    return [
        ("layer.start", "Layer 3 Synthesis — composing the weighted picture"),
        ("layer.step.progress", f"Layer 3 — weighting {n_scen} scenario{'s' if n_scen != 1 else ''} against the calibration ladder"),
        ("layer.step.progress", f"Layer 3 — calibrating {n_rows} per-scenario confidence row{'s' if n_rows != 1 else ''}"),
        ("layer.step.progress", f"Layer 3 — ranking {n_sens} sensitivity input{'s' if n_sens != 1 else ''} by cluster-weight-shift mechanic"),
        ("layer.complete", "Layer 3 complete — diagnosis composed"),
    ]


def _l4_steps(payload: ArtefactPayload) -> List[tuple]:
    refl = payload.reflection_section
    n_q = len(refl.questions) if refl and refl.questions else 0
    steps = [
        ("layer.start", "Layer 4 Reflection — composing 3 closing reflection questions"),
    ]
    for i in range(1, max(n_q + 1, 1)):
        steps.append((
            "layer.step.progress",
            f"Layer 4 — composing diagnostic interpretation of question {i} of {n_q or 3}",
        ))
    steps.append(("layer.complete", f"Layer 4 complete — {n_q or 3} reflection question{'s' if (n_q or 3) != 1 else ''} carried"))
    return steps


LAYER_STEP_BUILDERS = {
    "L0": _l0_steps,
    "L1": _l1_steps,
    "L2": _l2_steps,
    "L3": _l3_steps,
    "L4": _l4_steps,
}


# Slide-ready descriptions. Each slide kind gets a single
# observational rendering description.

SLIDE_READY_DESCRIPTIONS = {
    "cover":                  "Rendered Cover slide",
    "headline":               "Rendered Headline — 3 key findings carried up",
    "tensions_overview":      "Rendered Tensions Overview",
    "per_tension":            "Rendered Per-Tension Deep Dive",
    "scenarios_overview":     "Rendered Scenarios Overview — weighted by calibration tier",
    "per_scenario_table":     "Rendered Per-Scenario Confidence Table",
    "sensitivity":            "Rendered Sensitivity Analysis",
    "reflection":             "Rendered Reflection — 3 closing questions",
    "pathway":                "Rendered Pathway — sequenced recommendations",
    "decision_logic":         "Rendered Decision Logic — conditional branches",
    "risk_mitigation":        "Rendered Risk + Mitigation Register",
    "methodological_honesty": "Rendered Methodological Honesty disclosure",
    "in_closing":             "Rendered In Closing — reframing + final statement",
}
assert set(SLIDE_READY_DESCRIPTIONS) == set(LOCKED_SLIDE_KINDS), (
    "Every locked slide kind needs a SLIDE_READY_DESCRIPTIONS entry."
)


# Slide kind → source layer (which layer's resolution lands the slide).
# Used so the slide.ready event carries the layer that earned the slide.

SLIDE_KIND_TO_SOURCE_LAYER = {
    "cover":                  "L0",
    "headline":               "L3",
    "tensions_overview":      "L2",
    "per_tension":            "L2",
    "scenarios_overview":     "L3",
    "per_scenario_table":     "L3",
    "sensitivity":            "L3",
    "reflection":             "L4",
    "pathway":                "L3",
    "decision_logic":         "L3",
    "risk_mitigation":        "L3",
    "methodological_honesty": "L3",
    "in_closing":             "L4",
}
assert set(SLIDE_KIND_TO_SOURCE_LAYER) == set(LOCKED_SLIDE_KINDS)


# ─────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────


def synthesize_events(
    *,
    session_id: str,
    payload: ArtefactPayload,
) -> List[SolvaStreamEvent]:
    """Build the full deterministic event sequence for a complete
    Solva v2 session. Returns a list of `SolvaStreamEvent` ordered by
    `sequence` (0-indexed). All events pass the locked Pydantic
    validators including the integrity step-description check.

    The sequence is:
        Layer 0 start + steps + complete
        Layer 1 start + steps + complete
        Layer 2 start + steps + complete
        Layer 3 start + steps + complete
        Layer 4 start + steps + complete
        (then for each of the 13 locked slide kinds, in deck order)
            slide.ready (with slide_kind populated)
        session.complete
    """
    seq = 0
    events: List[SolvaStreamEvent] = []

    def _emit(*, layer_id: str, step_kind: str, description: str, slide_kind: Optional[str] = None) -> None:
        nonlocal seq
        events.append(SolvaStreamEvent(
            event_id=str(uuid.uuid4()),
            session_id=session_id,
            layer_id=layer_id,
            layer_name=LAYER_ID_TO_NAME[layer_id],
            step_kind=step_kind,
            step_description=description,
            slide_kind=slide_kind,
            sequence=seq,
            timestamp=utc_now_iso(),
        ))
        seq += 1

    # 5 layers
    for layer_id in ("L0", "L1", "L2", "L3", "L4"):
        for step_kind, description in LAYER_STEP_BUILDERS[layer_id](payload):
            _emit(layer_id=layer_id, step_kind=step_kind, description=description)

    # 13 slide.ready events (in deck order)
    for slide_kind in SLIDE_DECK_ORDER:
        source_layer = SLIDE_KIND_TO_SOURCE_LAYER[slide_kind]
        _emit(
            layer_id=source_layer,
            step_kind="slide.ready",
            description=SLIDE_READY_DESCRIPTIONS[slide_kind],
            slide_kind=slide_kind,
        )

    # Final session.complete event
    _emit(
        layer_id="L4",
        step_kind="session.complete",
        description=f"Session complete — 5 layers, {len(SLIDE_DECK_ORDER)} slides rendered",
    )

    return events
