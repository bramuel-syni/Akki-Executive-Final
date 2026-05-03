"""Local proxy so engine modules can import synthetic_audit_entry without a
circular import against services.solva_v2.llm_adapter. Keeps the engine code
barnacle-free of absolute service-path imports."""
from ..llm_adapter import synthetic_audit_entry

__all__ = ["synthetic_audit_entry"]
