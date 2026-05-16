"""Layer state machine — deterministic transitions.

Sessions move through exactly this sequence:

    entry → framing → layer_0 → layer_1 → layer_2 → layer_3 → layer_4 → done

`refused` and `abandoned` are terminal states reachable from any
active state via `refusal_logic` or operator action.

The state machine is a pure-function module: no I/O, no LLM, no Mongo.
"""
from __future__ import annotations

from typing import Tuple

from ..schemas import LAYER_SEQUENCE, TERMINAL_STATES


class InvalidLayerTransition(RuntimeError):
    """Raised when caller tries to advance from layer A → layer B and
    the transition is not legal."""


def is_terminal(state: str) -> bool:
    return state in TERMINAL_STATES or state == "done"


def _index(state: str) -> int:
    try:
        return LAYER_SEQUENCE.index(state)
    except ValueError as exc:
        raise InvalidLayerTransition(
            f"Unknown layer state: {state}"
        ) from exc


def can_advance_to(current: str, target: str) -> bool:
    """True iff `target` is exactly the next state after `current`.

    Hard rule (brief §3.0): users cannot skip ahead. The state machine
    advances one step at a time.
    """
    if current in TERMINAL_STATES:
        return False
    try:
        ci = _index(current)
        ti = _index(target)
    except InvalidLayerTransition:
        return False
    return ti == ci + 1


def advance(current: str) -> Tuple[str, bool]:
    """Compute the next state. Returns `(next_state, became_terminal)`.

    Raises `InvalidLayerTransition` when called from a terminal state.
    """
    if current in TERMINAL_STATES:
        raise InvalidLayerTransition(
            f"Cannot advance from terminal state: {current}"
        )
    if current == "done":
        raise InvalidLayerTransition("Cannot advance from 'done'.")
    ci = _index(current)
    nxt = LAYER_SEQUENCE[ci + 1]
    return nxt, nxt == "done"
