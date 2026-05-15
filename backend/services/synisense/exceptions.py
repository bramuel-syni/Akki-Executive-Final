"""Synisense Phase A — exception hierarchy.

Maps to the four error classes from the brief (Section 5, Table 5):
- AUTH_DENIED          → 401
- PURPOSE_INVALID      → 422
- GOVERNANCE_REFUSED   → 451 (legally unavailable — closest fit to "we refuse on governance grounds")
- SERVICE_UNAVAILABLE  → 503

Error responses surface as `{type(exc).__name__}: {str(exc)[:300]}` per
the Chunk 3 authenticity rule — no raw `repr(exc)` leaks.
"""
from __future__ import annotations


class SynisenseError(Exception):
    """Base. Carries the brief's error-class string in `.class_name`
    so HTTP wrappers can produce the canonical {AUTH_DENIED, ...}
    error code field without dispatching on Python type names."""
    status_code: int = 500
    class_name: str = "SYNISENSE_ERROR"


class AuthDenied(SynisenseError):
    status_code = 401
    class_name = "AUTH_DENIED"


class PurposeInvalid(SynisenseError):
    status_code = 422
    class_name = "PURPOSE_INVALID"


class GovernanceRefused(SynisenseError):
    status_code = 451
    class_name = "GOVERNANCE_REFUSED"


class ServiceUnavailable(SynisenseError):
    status_code = 503
    class_name = "SERVICE_UNAVAILABLE"


def format_error(exc: BaseException) -> str:
    """Canonical {type(exc).__name__}: {str(exc)[:300]} formatter.
    Used everywhere we want to surface an exception to a consumer or
    audit log without leaking raw repr() artefacts."""
    return f"{type(exc).__name__}: {str(exc)[:300]}"
