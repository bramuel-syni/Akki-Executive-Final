"""
services/streaming_phases.py — Patch 9.

Standard helper for emitting `phase` events on Server-Sent Event streams.
Adoption surfaces: Solva (4 modes), Cycle compile, Work Studio Enhance.

Phase vocabulary (locked order):
    reading_context → shielding_input → reasoning → drafting → refining → complete

Client-side label mapping lives in `frontend/src/components/streaming/StreamingShell.jsx`.

The helper is intentionally a thin formatter — endpoints stay in control of
WHEN to emit (we never auto-fire phases the user can't actually observe).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional


PHASE_VOCABULARY = (
    "reading_context",
    "shielding_input",
    "reasoning",
    "drafting",
    "refining",
    "complete",
)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def encode_phase_event(phase_key: str, meta: Optional[Dict[str, Any]] = None) -> str:
    """Return the SSE-encoded `phase` event string ready to yield.

    Format (matches the brief):
        event: phase
        data: {"phase": "...", "ts": "ISO8601", "meta": {...}}
        (blank line terminator)
    """
    if phase_key not in PHASE_VOCABULARY:
        # Refuse to emit unknown phases — surfaces must use the locked
        # vocabulary so the client motion stays predictable.
        raise ValueError(
            f"Unknown phase_key {phase_key!r}. Allowed: {PHASE_VOCABULARY}"
        )
    payload = {
        "phase": phase_key,
        "ts": _iso_now(),
        "meta": meta or {},
    }
    return f"event: phase\ndata: {json.dumps(payload, separators=(',', ':'))}\n\n"


async def emit_phase(stream, phase_key: str, meta: Optional[Dict[str, Any]] = None) -> None:
    """Best-effort phase emission for endpoints that hold a writable stream.

    `stream` is anything with an async `write` method (e.g. an asyncio
    StreamWriter, or our internal phase-buffer used in tests). For
    StreamingResponse generators that `yield` strings, callers should
    use `encode_phase_event(...)` directly and `yield` the result.
    """
    chunk = encode_phase_event(phase_key, meta)
    if stream is None:
        return
    write = getattr(stream, "write", None)
    if write is None:
        return
    res = write(chunk)
    if hasattr(res, "__await__"):
        await res
