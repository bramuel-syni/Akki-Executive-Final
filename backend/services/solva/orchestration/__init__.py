"""Phase D orchestration tier — state machine + sub-module router."""
from .state_machine import (
    advance,
    can_advance_to,
    is_terminal,
    InvalidLayerTransition,
)
from .shield_invoker import (
    invoke_via_shield,
    ShieldInvokeResult,
    DEFAULT_CONSUMER_ID,
)

__all__ = [
    "advance",
    "can_advance_to",
    "is_terminal",
    "InvalidLayerTransition",
    "invoke_via_shield",
    "ShieldInvokeResult",
    "DEFAULT_CONSUMER_ID",
]
