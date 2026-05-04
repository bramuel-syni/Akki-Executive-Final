"""Solva v2 — layer state machine (Phase 15.1, extended in Phase 15.2).

Phase 15.1 introduced a 4-layer flow for the Seek Clarity sub-module:
    framing → grounding → synthesis → reflection

Phase 15.2 generalises this to per-sub-module flows:
    seek_clarity        : framing → grounding → synthesis → reflection
    develop_strategy    : framing → grounding → synthesis → reflection
    get_perspective     : framing → grounding → synthesis → reflection
    simulate_hypothesis : framing → grounding → hypothesis → synthesis → reflection

`hypothesis` is an additional layer where a scenario-expansion step + the
tension detector run before synthesis. State machine treats it as a
distinct gate: advance to synthesis only when the hypothesis layer's
required engines have produced audit entries.

The state machine is a PURE module: it inspects a session document and
returns the next valid layer (or None) without mutating anything.

Fuzz-tested: random walks across permutations of (submodule, layer,
audit, turns) never reach an undefined state — see
tests/test_solva_v2_state_machine.py.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

# All layer names in the universe.
LAYERS: List[str] = ["framing", "grounding", "hypothesis", "synthesis", "reflection"]
TERMINAL_LAYER = "reflection"

# Per-sub-module ordered layer flow. Phase 15.2: simulate_hypothesis adds
# the `hypothesis` layer between grounding and synthesis. The other three
# sub-modules share the 15.1 four-layer flow.
LAYER_ORDER_BY_SUBMODULE: Dict[str, List[str]] = {
    "seek_clarity":        ["framing", "grounding", "synthesis", "reflection"],
    "develop_strategy":    ["framing", "grounding", "synthesis", "reflection"],
    "get_perspective":     ["framing", "grounding", "synthesis", "reflection"],
    "simulate_hypothesis": ["framing", "grounding", "hypothesis", "synthesis", "reflection"],
}
DEFAULT_SUBMODULE = "seek_clarity"

# Engine names that must be present in the grounding-layer audit log before
# we are allowed to advance out of grounding.
GROUNDING_REQUIRED_ENGINES = frozenset({"triangulation", "candidate_generation"})

# Engine names that must be present in the hypothesis-layer audit log
# (simulate_hypothesis only) before we are allowed to advance into synthesis.
HYPOTHESIS_REQUIRED_ENGINES = frozenset({"tension_detector"})


class InvalidLayerTransition(Exception):
    """Raised when a session is in an unrecognised layer or when a transition
    is requested that the rules do not allow."""


def _resolve_submodule(session: Dict[str, Any]) -> str:
    """Phase 15.2: backwards compat read-time default. Sessions written
    before 15.2 carry submodule=None / missing."""
    sm = session.get("submodule") or DEFAULT_SUBMODULE
    return sm if sm in LAYER_ORDER_BY_SUBMODULE else DEFAULT_SUBMODULE


def _flow_for(session: Dict[str, Any]) -> List[str]:
    return LAYER_ORDER_BY_SUBMODULE[_resolve_submodule(session)]


def _user_turn_count(session: Dict[str, Any]) -> int:
    return sum(1 for t in (session.get("turns") or []) if t.get("role") == "user")


def _audit_for_layer(session: Dict[str, Any], layer: str) -> List[Dict[str, Any]]:
    return [e for e in (session.get("reasoning_audit_log") or []) if e.get("layer") == layer]


def _grounding_engines_done(session: Dict[str, Any]) -> bool:
    seen = {e.get("engine") for e in _audit_for_layer(session, "grounding")}
    return GROUNDING_REQUIRED_ENGINES.issubset(seen)


def _hypothesis_engines_done(session: Dict[str, Any]) -> bool:
    seen = {e.get("engine") for e in _audit_for_layer(session, "hypothesis")}
    return HYPOTHESIS_REQUIRED_ENGINES.issubset(seen)


def _synthesis_complete(session: Dict[str, Any]) -> bool:
    synth = session.get("synthesis") or {}
    if not synth.get("claims"):
        return False
    # Probability weighting must have populated confidence_band on every claim.
    if not all((c or {}).get("confidence_band") is not None for c in synth["claims"]):
        return False
    # Validator verdict recorded.
    if not (synth.get("validation") or {}).get("verdict"):
        return False
    return True


def _next_in_flow(flow: List[str], current: str) -> Optional[str]:
    """Return the layer that comes after `current` in the given flow,
    or None if `current` is the last layer in the flow."""
    if current not in flow:
        return None
    idx = flow.index(current)
    if idx + 1 >= len(flow):
        return None
    return flow[idx + 1]


def next_layer(session: Dict[str, Any]) -> Optional[str]:
    """Return the layer this session should advance to, or None if it should stay.

    Pure function. No DB writes, no IO. Raises InvalidLayerTransition on an
    unrecognised current layer.
    """
    flow = _flow_for(session)
    current = session.get("layer")
    if current not in LAYERS:
        raise InvalidLayerTransition(f"unknown current layer: {current!r}")
    if current not in flow:
        # Layer is valid in the universe but not in this submodule's flow
        # (e.g. a session somehow landed at `hypothesis` while submodule
        # is `seek_clarity`). Treat as illegal.
        raise InvalidLayerTransition(
            f"layer {current!r} is not part of submodule "
            f"{_resolve_submodule(session)!r} flow"
        )

    user_turns = _user_turn_count(session)

    if current == "framing":
        return _next_in_flow(flow, current) if user_turns >= 1 else None

    if current == "grounding":
        if _grounding_engines_done(session) and user_turns >= 2:
            return _next_in_flow(flow, current)
        return None

    if current == "hypothesis":
        # Phase 15.2 — simulate_hypothesis only.
        if _hypothesis_engines_done(session):
            return _next_in_flow(flow, current)
        return None

    if current == "synthesis":
        if _synthesis_complete(session) and user_turns >= 3:
            return _next_in_flow(flow, current)
        return None

    if current == "reflection":
        return None  # terminal

    raise InvalidLayerTransition(f"unhandled layer: {current!r}")


def can_post_turn(session: Dict[str, Any]) -> bool:
    """Return True iff posting a user turn to this session is legal."""
    if (session.get("status") or "").lower() != "active":
        return False
    if session.get("layer") == TERMINAL_LAYER:
        return False
    return True


def assert_can_post_turn(session: Dict[str, Any]) -> None:
    if not can_post_turn(session):
        raise InvalidLayerTransition(
            f"session {session.get('id')} cannot accept more turns "
            f"(status={session.get('status')!r}, layer={session.get('layer')!r})"
        )


def is_terminal(session: Dict[str, Any]) -> bool:
    return session.get("layer") == TERMINAL_LAYER


def submodule_of(session: Dict[str, Any]) -> str:
    """Public helper for the orchestrator: resolve the session's submodule
    with backwards-compat fallback."""
    return _resolve_submodule(session)
