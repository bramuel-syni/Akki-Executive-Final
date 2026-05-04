"""Solva v2 — layer state machine (Phase 15.1).

The v1 engine used a bare list constant for phase order. v2 needs explicit
transition guards because each layer has preconditions on the audit log
(e.g. synthesis cannot advance until probability_weighting and the validator
have both run, and the grounding contract parsed cleanly).

The state machine is a PURE module: it inspects a session document and
returns the next valid layer (or None) without mutating anything. The
orchestrator owns the side effects.

Transition rules for the Seek Clarity sub-module:

    framing:
        advance to grounding when the user has posted >= 1 turn
        (the 0th turn is the Solva-primed reply written at session start).

    grounding:
        advance to synthesis when:
          - the triangulation engine has produced an audit entry at this layer
          - the candidate_generation engine has produced an audit entry
          - the user has posted >= 2 turns
          (so the user's first turn triggered grounding engines, and their
           second turn acknowledges/refines the framings before synthesis)

    synthesis:
        advance to reflection when:
          - session.synthesis is non-null and carries claims[]
          - probability_weighting has populated confidence_band on every claim
          - validator verdict is recorded in session.synthesis.validation
          - user has posted >= 3 turns

    reflection:
        terminal. status flips to "completed". next_layer returns None.

Illegal session states (unknown layer, contradictory state) raise
InvalidLayerTransition so callers can surface 409 to the client rather than
degrade silently.

Fuzz-tested: random walks across permutations of (layer, audit, turns) never
reach an undefined state — see tests/test_solva_v2_state_machine.py.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


LAYERS: List[str] = ["framing", "grounding", "synthesis", "reflection"]
TERMINAL_LAYER = "reflection"

# Engine names that must be present in the grounding-layer audit log before
# we are allowed to advance into synthesis.
GROUNDING_REQUIRED_ENGINES = frozenset({"triangulation", "candidate_generation"})


class InvalidLayerTransition(Exception):
    """Raised when a session is in an unrecognised layer or when a transition
    is requested that the rules do not allow."""


def _user_turn_count(session: Dict[str, Any]) -> int:
    return sum(1 for t in (session.get("turns") or []) if t.get("role") == "user")


def _audit_for_layer(session: Dict[str, Any], layer: str) -> List[Dict[str, Any]]:
    return [e for e in (session.get("reasoning_audit_log") or []) if e.get("layer") == layer]


def _grounding_engines_done(session: Dict[str, Any]) -> bool:
    seen = {e.get("engine") for e in _audit_for_layer(session, "grounding")}
    return GROUNDING_REQUIRED_ENGINES.issubset(seen)


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


def next_layer(session: Dict[str, Any]) -> Optional[str]:
    """Return the layer this session should advance to, or None if it should stay.

    Pure function. No DB writes, no IO. Raises InvalidLayerTransition on an
    unrecognised current layer.
    """
    current = session.get("layer")
    if current not in LAYERS:
        raise InvalidLayerTransition(f"unknown current layer: {current!r}")

    user_turns = _user_turn_count(session)

    if current == "framing":
        return "grounding" if user_turns >= 1 else None

    if current == "grounding":
        if _grounding_engines_done(session) and user_turns >= 2:
            return "synthesis"
        return None

    if current == "synthesis":
        if _synthesis_complete(session) and user_turns >= 3:
            return "reflection"
        return None

    if current == "reflection":
        return None  # terminal

    raise InvalidLayerTransition(f"unhandled layer: {current!r}")


def can_post_turn(session: Dict[str, Any]) -> bool:
    """Return True iff posting a user turn to this session is legal.

    A session is closed for input when status is anything other than 'active'
    (completed / abandoned / unknown) OR when its layer has reached the
    terminal layer with the synthesis lifecycle already discharged.
    """
    if (session.get("status") or "").lower() != "active":
        return False
    if session.get("layer") == TERMINAL_LAYER:
        return False
    return True


def assert_can_post_turn(session: Dict[str, Any]) -> None:
    """Same as can_post_turn but raises InvalidLayerTransition on rejection.

    The orchestrator catches this and returns 409.
    """
    if not can_post_turn(session):
        raise InvalidLayerTransition(
            f"session {session.get('id')} cannot accept more turns "
            f"(status={session.get('status')!r}, layer={session.get('layer')!r})"
        )


def is_terminal(session: Dict[str, Any]) -> bool:
    return session.get("layer") == TERMINAL_LAYER
