"""Synisense Shield — exceptions.

Phase H2.5 (2026-05-24). Centralises the Shield-specific exception
classes so adapter, client, and call sites import the same class
(callers can `except ShieldFailure` without coupling to a particular
adapter module).

`ShieldFailure` is raised when:
  * the de-identifier pipeline throws (Presidio failure, spaCy load
    error, regex pattern error)
  * AND the calling surface is in the chat-family (the legacy
    degraded-open path is reserved for non-chat surfaces, see the
    `_SURFACES_ALLOWING_DEGRADED_OPEN` list in `adapter.py`)

The HTTP layer translates this to a 503 with body
`{"error":"shield_unavailable","action":"retry","message":"..."}`.
"""
from __future__ import annotations


class ShieldFailure(Exception):
    """The Synisense Shield de-identification pipeline failed and the
    calling surface MUST NOT degrade-open. Raised by
    `services.synisense.adapter.shield_payload_async` for chat-family
    surfaces; caught at the route boundary which returns 503."""

    def __init__(self, message: str, *, original: Exception | None = None,
                 surface: str | None = None) -> None:
        super().__init__(message)
        self.original = original
        self.surface = surface

    @property
    def error_class(self) -> str:
        """Name of the underlying exception type (for audit-row metadata)."""
        return type(self.original).__name__ if self.original is not None else "ShieldFailure"
