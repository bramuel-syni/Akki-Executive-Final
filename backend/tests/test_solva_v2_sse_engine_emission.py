"""Solva v2 — Slice 3a (2026-05-29) synthesizer + SSE wire shape.

End-to-end test that:
  (a) runs the synthesizer against the real `build_payload()` for a
      seeded reference session shape, and
  (b) asserts the SSE event stream contains at minimum:
      • 1 layer.start + ≥1 layer.step.progress + 1 layer.complete per L0..L4
      • 13 slide.ready events (one per locked kind)
      • 1 session.complete

This is the "engine emission" contract the user locked: when the
engine resolves, the stream proves it.
"""
from __future__ import annotations

from services.solva_v2.payload_builder import build_payload
from services.solva_v2.stream_schema import (
    LOCKED_LAYER_IDS,
    LOCKED_SLIDE_KINDS,
    LOCKED_STEP_KINDS,
)
from services.solva_v2.stream_synthesizer import (
    SLIDE_DECK_ORDER,
    SLIDE_KIND_TO_SOURCE_LAYER,
    SLIDE_READY_DESCRIPTIONS,
    synthesize_events,
)


def _seeded_session_shape() -> dict:
    """Minimal session shape that exercises the payload builder without
    requiring Mongo. Carries enough audit-log entries + scenario data
    that all 5 layers and all 13 slides have content to synthesize."""
    return {
        "id": "test-sid-1",
        "account_id": "acct-1",
        "context_id": "ctx-1",
        "status": "completed",
        "submodule": "develop_strategy",
        "intent": "Why is Q3 missing target despite stable pipeline?",
        "user_turns": [
            {"id": "t1", "layer": "framing", "text": "Q3 revenue missed by 14%"},
            {"id": "t2", "layer": "grounding", "text": "Pipeline conversion held steady at 22%"},
            {"id": "t3", "layer": "hypothesis", "text": "FX headwinds get the blame internally"},
            {"id": "t4", "layer": "synthesis", "text": "But pricing experiments coincided"},
            {"id": "t5", "layer": "reflection", "text": "If FX is the cause, what would change?"},
            {"id": "t6", "layer": "reflection", "text": "We'd see a recovery in Q4 once FX normalizes"},
            {"id": "t7", "layer": "reflection", "text": "Hardest to sit with: the timing coincidence"},
        ],
        "reasoning_audit_log": [
            {"id": "a1", "turn_id": "t1", "layer": "framing", "engine": "framing_extractor", "engine_version": "1.0", "output": {"framings": ["Q3 missed", "FX blamed", "Pricing coincides"]}},
            {"id": "a2", "turn_id": "t2", "layer": "grounding", "engine": "candidate_generation", "engine_version": "1.0", "output": {"candidates": []}},
            {"id": "a3", "turn_id": "t3", "layer": "hypothesis", "engine": "tension_detector", "engine_version": "1.0", "output": {"tensions": []}},
            {"id": "a4", "turn_id": "t4", "layer": "synthesis", "engine": "synthesis", "engine_version": "1.0", "output": {}},
            {"id": "a5", "turn_id": "t5", "layer": "reflection", "engine": "reflection", "engine_version": "1.0", "output": {}},
        ],
    }


def test_synthesizer_emits_layer_lifecycle_per_layer():
    """For each of L0..L4 the synthesized sequence must include
    layer.start + at least one layer.step.progress + layer.complete."""
    payload = build_payload(_seeded_session_shape(), context_name="Test Ctx")
    events = synthesize_events(session_id="test-sid-1", payload=payload)
    by_layer: dict[str, list[str]] = {lid: [] for lid in LOCKED_LAYER_IDS}
    for ev in events:
        if ev.step_kind in ("layer.start", "layer.step.progress", "layer.complete"):
            by_layer[ev.layer_id].append(ev.step_kind)
    for lid in LOCKED_LAYER_IDS:
        kinds = by_layer[lid]
        assert "layer.start" in kinds, f"{lid} missing layer.start (got {kinds})"
        assert "layer.complete" in kinds, f"{lid} missing layer.complete"
        assert kinds.count("layer.step.progress") >= 1, (
            f"{lid} missing layer.step.progress (got {kinds})"
        )


def test_synthesizer_emits_fifteen_slide_ready_events_in_deck_order():
    """Exactly one slide.ready event per locked kind, emitted in the
    SLIDE_DECK_ORDER sequence. Slice 4 (2026-05-29) added bias_inventory
    (count 13→14). Slice 5 (2026-05-29) added pre_mortem (count 14→15)."""
    payload = build_payload(_seeded_session_shape(), context_name="Test Ctx")
    events = synthesize_events(session_id="test-sid-1", payload=payload)
    ready = [ev for ev in events if ev.step_kind == "slide.ready"]
    assert len(ready) == 15
    rendered_kinds = [ev.slide_kind for ev in ready]
    assert rendered_kinds == list(SLIDE_DECK_ORDER), (
        f"slide.ready order = {rendered_kinds}, expected {SLIDE_DECK_ORDER}"
    )
    # Every slide.ready carries the source layer that earned the slide.
    for ev in ready:
        assert ev.layer_id == SLIDE_KIND_TO_SOURCE_LAYER[ev.slide_kind]
        assert ev.step_description == SLIDE_READY_DESCRIPTIONS[ev.slide_kind]


def test_synthesizer_emits_exactly_one_session_complete_as_final_event():
    payload = build_payload(_seeded_session_shape(), context_name="Test Ctx")
    events = synthesize_events(session_id="test-sid-1", payload=payload)
    session_completes = [ev for ev in events if ev.step_kind == "session.complete"]
    assert len(session_completes) == 1
    assert events[-1].step_kind == "session.complete"


def test_synthesizer_sequence_is_monotonic_and_zero_indexed():
    payload = build_payload(_seeded_session_shape(), context_name="Test Ctx")
    events = synthesize_events(session_id="test-sid-1", payload=payload)
    sequences = [ev.sequence for ev in events]
    assert sequences == list(range(len(events))), (
        "sequence must be zero-indexed monotonic"
    )


def test_synthesizer_uses_canonical_layer_naming_only():
    """Zero events should reference legacy audit-log layer values
    (framing/grounding/hypothesis) as layer_name. All must use canonical
    Solva naming (frame_audit/surface/depth/synthesis/reflection)."""
    payload = build_payload(_seeded_session_shape(), context_name="Test Ctx")
    events = synthesize_events(session_id="test-sid-1", payload=payload)
    canonical = {"frame_audit", "surface", "depth", "synthesis", "reflection"}
    legacy = {"framing", "grounding", "hypothesis"}
    for ev in events:
        assert ev.layer_name in canonical, (
            f"event {ev.sequence}: layer_name={ev.layer_name!r} not canonical"
        )
        assert ev.layer_name not in legacy


def test_every_synthesized_event_passes_step_description_integrity():
    """The synthesizer must NEVER emit a theatrical or imperative
    description. (The Pydantic model already enforces this — if the
    synthesizer composed a forbidden phrase it would crash before
    returning.)"""
    payload = build_payload(_seeded_session_shape(), context_name="Test Ctx")
    events = synthesize_events(session_id="test-sid-1", payload=payload)
    forbidden = ("thinking deeply", "pondering", "hidden tensions",
                 "let me", "would you like", "you should", "you must")
    for ev in events:
        lower = ev.step_description.lower()
        for needle in forbidden:
            assert needle not in lower, (
                f"event {ev.sequence}: leaked forbidden phrase "
                f"{needle!r} in step_description={ev.step_description!r}"
            )


def test_event_count_is_deterministic_for_same_payload():
    """Replay contract: given the same payload, the synthesizer returns
    the same number of events. (Timestamps + event_ids vary, but the
    skeleton is deterministic.)"""
    payload = build_payload(_seeded_session_shape(), context_name="Test Ctx")
    a = synthesize_events(session_id="test-sid-1", payload=payload)
    b = synthesize_events(session_id="test-sid-1", payload=payload)
    assert len(a) == len(b)
    # Layer/step/slide composition must match exactly.
    for ea, eb in zip(a, b):
        assert (ea.layer_id, ea.step_kind, ea.slide_kind) == (eb.layer_id, eb.step_kind, eb.slide_kind)


def test_all_locked_step_kinds_are_emitted():
    """Every locked step_kind must surface at least once in a typical
    session emission."""
    payload = build_payload(_seeded_session_shape(), context_name="Test Ctx")
    events = synthesize_events(session_id="test-sid-1", payload=payload)
    emitted = {ev.step_kind for ev in events}
    assert emitted == set(LOCKED_STEP_KINDS)


def test_all_thirteen_slide_kinds_are_emitted_exactly_once():
    payload = build_payload(_seeded_session_shape(), context_name="Test Ctx")
    events = synthesize_events(session_id="test-sid-1", payload=payload)
    ready_kinds = [ev.slide_kind for ev in events if ev.step_kind == "slide.ready"]
    assert set(ready_kinds) == set(LOCKED_SLIDE_KINDS)
    # And no duplicates
    assert len(ready_kinds) == len(set(ready_kinds))
