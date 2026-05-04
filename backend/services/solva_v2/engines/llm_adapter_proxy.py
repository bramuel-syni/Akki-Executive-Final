"""Local proxy so engine modules can import synthetic_audit_entry and
shielded_call without a circular import against services.solva_v2.llm_adapter.
Keeps the engine code barnacle-free of absolute service-path imports."""
from ..llm_adapter import (
    synthetic_audit_entry,
    shielded_call,
    SHIELD_BYPASS_REASONS,
)

__all__ = [
    "synthetic_audit_entry",
    "shielded_call",
    "SHIELD_BYPASS_REASONS",
]
