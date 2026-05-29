"""Solva v2 — Slice 3a (2026-05-29) SSE event schema contract.

Locks the Pydantic event model against drift:
  - Locked layer enum (L0..L4) maps to canonical names
  - Locked step_kind enum
  - Locked 13-kind slide enum on slide.ready events
  - layer_id / layer_name cross-field consistency
  - slide_kind required iff step_kind == slide.ready
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from services.solva_v2.stream_schema import (
    AUDIT_LOG_LAYER_TO_CANONICAL_ID,
    LAYER_ID_TO_NAME,
    LAYER_NAME_TO_ID,
    LOCKED_LAYER_IDS,
    LOCKED_SLIDE_KINDS,
    LOCKED_STEP_KINDS,
    SolvaStreamEvent,
    utc_now_iso,
)


def _ev(**overrides):
    base = dict(
        event_id="evt-1",
        session_id="sid-1",
        layer_id="L1",
        layer_name="surface",
        step_kind="layer.start",
        step_description="Layer 1 Surface — extracting 4 candidate framings",
        slide_kind=None,
        sequence=0,
        timestamp=utc_now_iso(),
    )
    base.update(overrides)
    return SolvaStreamEvent(**base)


def test_locked_layer_enum():
    assert LOCKED_LAYER_IDS == ("L0", "L1", "L2", "L3", "L4")
    assert LAYER_ID_TO_NAME == {
        "L0": "frame_audit",
        "L1": "surface",
        "L2": "depth",
        "L3": "synthesis",
        "L4": "reflection",
    }
    # round-trip
    for lid, name in LAYER_ID_TO_NAME.items():
        assert LAYER_NAME_TO_ID[name] == lid


def test_locked_step_kinds():
    assert LOCKED_STEP_KINDS == (
        "layer.start",
        "layer.step.progress",
        "layer.complete",
        "slide.ready",
        "session.complete",
    )


def test_locked_slide_kinds_match_artefact_schema():
    """The slide-kind enum on stream_schema MUST match the 15-kind
    enum locked on the artefact schema. Slice 4 added bias_inventory;
    Slice 5 added pre_mortem."""
    assert LOCKED_SLIDE_KINDS == frozenset({
        "cover", "headline",
        "tensions_overview", "per_tension",
        "scenarios_overview", "per_scenario_table", "sensitivity",
        "reflection",
        "bias_inventory",
        "pathway", "pre_mortem", "decision_logic", "risk_mitigation",
        "methodological_honesty", "in_closing",
    })


def test_audit_log_rosetta_covers_all_legacy_values():
    """The synthesizer maps legacy audit-log layer values to canonical
    Solva L0..L4. Every legacy value must map."""
    for legacy in ("framing", "grounding", "hypothesis", "synthesis", "reflection"):
        assert legacy in AUDIT_LOG_LAYER_TO_CANONICAL_ID
        assert AUDIT_LOG_LAYER_TO_CANONICAL_ID[legacy] in LOCKED_LAYER_IDS


def test_valid_layer_start_event():
    ev = _ev(layer_id="L1", layer_name="surface", step_kind="layer.start")
    assert ev.layer_id == "L1"
    assert ev.slide_kind is None


def test_valid_slide_ready_event():
    ev = _ev(
        layer_id="L3",
        layer_name="synthesis",
        step_kind="slide.ready",
        slide_kind="headline",
        step_description="Rendered Headline — 3 key findings carried up",
    )
    assert ev.step_kind == "slide.ready"
    assert ev.slide_kind == "headline"


def test_layer_id_outside_locked_enum_rejected():
    with pytest.raises(ValidationError):
        _ev(layer_id="L9")


def test_layer_name_outside_locked_enum_rejected():
    with pytest.raises(ValidationError):
        _ev(layer_id="L1", layer_name="notalayer")


def test_layer_id_and_name_must_pair():
    """layer_id='L1' (surface) must be paired with layer_name='surface'."""
    with pytest.raises(ValidationError):
        _ev(layer_id="L1", layer_name="depth")


def test_step_kind_outside_locked_enum_rejected():
    with pytest.raises(ValidationError):
        _ev(step_kind="layer.thinking_deeply")


def test_slide_ready_requires_slide_kind():
    with pytest.raises(ValidationError):
        _ev(step_kind="slide.ready", slide_kind=None,
            step_description="Rendered cover slide")


def test_non_slide_ready_must_not_carry_slide_kind():
    with pytest.raises(ValidationError):
        _ev(step_kind="layer.start", slide_kind="cover",
            step_description="Layer 0 — gating the framing")


def test_slide_kind_outside_locked_enum_rejected():
    with pytest.raises(ValidationError):
        _ev(step_kind="slide.ready", slide_kind="fake_kind",
            step_description="Rendered some slide")


def test_sequence_must_be_non_negative():
    with pytest.raises(ValidationError):
        _ev(sequence=-1)
