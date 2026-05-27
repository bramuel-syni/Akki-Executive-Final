"""Phase L.a (2026-05-27) — `PhaseEmitter` for the streaming-progress pipe.

Each long-op endpoint that opts into Phase L declares its `surface`
key (one of the 7 locked surfaces) and instantiates a `PhaseEmitter`.
The emitter advances through a static script (`PHASE_SCRIPTS[surface]`),
yielding SSE-formatted strings at every phase boundary. The endpoint's
async generator simply iterates the emitter and yields each chunk.

The static script is the canonical source of truth for visible labels
+ icon hints. When a new surface lands (R.5, L.b, etc.), its phase
script is added here AND the visual reference doc
(`/app/memory/sprints/PHASE_L_VISUAL_REFERENCE.md`) is updated.

**Voice contract** (carried from Phase K):
- "Reading your <inputs>" (phase 1) — orientation
- "Checking the grounding contract" (phase 2) — Synisense / FAR gate
- "Composing." / "Drafting." / "Rendering." (middle phases) — work
- "Validating." (penultimate) — post-write checks
- "Almost there." (final) — return / persist

**Icon hints:** each phase declares a semantic icon key (`book`,
`shield-check`, `pen-tool`, `check-square`). The frontend maps these
to lucide-react icons. NOT decorative — semantically reflects the
phase's nature.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, AsyncIterator, Dict, List, Optional

from fastapi import Request

from .sse import SSEStream, encode_event, encode_heartbeat


log = logging.getLogger("akki.streaming.progress")


# ─────────────────────────────────────────────────────────────────────
# PHASE SCRIPTS — locked at L.a; L.b extends; future phases append.
#
# Adding a script: pick a surface key, define ordered phase list with
# `label` + `icon` keys. Each label is the verbatim visible line.
# ─────────────────────────────────────────────────────────────────────
PHASE_SCRIPTS: Dict[str, List[Dict[str, str]]] = {

    # L.a Surface #1 — Solva Frame Audit (5 phases)
    "solva-frame-audit": [
        {"label": "Reading your framing.",         "icon": "book-open"},
        {"label": "Checking the grounding contract.", "icon": "shield-check"},
        {"label": "Mapping the layer-0 ingest.",   "icon": "map"},
        {"label": "Composing.",                    "icon": "pen-tool"},
        {"label": "Validating.",                   "icon": "check-square"},
    ],

    # L.a Surface #3 — Work Studio Compilation Wizard (7 phases)
    "work-studio-compile": [
        {"label": "Reading the cycle inputs.",     "icon": "book-open"},
        {"label": "Checking the grounding contract.", "icon": "shield-check"},
        {"label": "Drafting the outline.",         "icon": "list"},
        {"label": "Composing.",                    "icon": "pen-tool"},
        {"label": "Rendering the artefact.",       "icon": "file-text"},
        {"label": "Validating.",                   "icon": "check-square"},
        {"label": "Almost there.",                 "icon": "sparkles"},
    ],
}


# ─────────────────────────────────────────────────────────────────────
# PhaseEmitter
# ─────────────────────────────────────────────────────────────────────
class PhaseEmitter:
    """Emits SSE events as the long-op advances through its phase script.

    Usage inside the long-op endpoint:
        async def my_long_op(request: Request, stream: int = 0):
            if not stream:
                return await _legacy_json_path()
            async def gen():
                emitter = PhaseEmitter(request, surface="work-studio-compile")
                async with emitter.start() as e:
                    yield e.script_event()              # 'script' event lists all phases up-front
                    yield await e.advance()             # phase 1
                    await heavy_work_1()
                    yield await e.advance()             # phase 2
                    await heavy_work_2()
                    ...
                    yield await e.complete({"result": payload})
            return StreamingResponse(gen(), headers=sse_headers())

    The frontend EventSource receives:
        1) `event: script` — JSON list of {label, icon} entries
        2) `event: phase`  — JSON {index, label, icon} when each phase starts
        3) `event: complete` — JSON {result: <legacy-json-payload>}

    `advance()` checks `request.is_disconnected()` before emitting and
    returns None if cancelled (the generator should `return` immediately).
    """

    def __init__(self, request: Request, surface: str):
        if surface not in PHASE_SCRIPTS:
            raise KeyError(
                f"Unknown surface {surface!r}; known: {sorted(PHASE_SCRIPTS)}. "
                f"Add the phase script to PHASE_SCRIPTS in services/streaming/progress.py."
            )
        self.surface = surface
        self.script: List[Dict[str, str]] = PHASE_SCRIPTS[surface]
        self._stream = SSEStream(request)
        self._index = -1
        self._started_at: Optional[float] = None

    @property
    def cancelled(self) -> bool:
        return self._stream.cancelled

    def start(self):
        """Context-manager entry. Captured start timestamp + opens the stream."""
        self._started_at = time.time()
        # Reset index; the first advance() will move to 0.
        self._index = -1
        # Return self in an async-context-manager shape.
        emitter = self
        class _Ctx:
            async def __aenter__(_self):  # noqa
                return emitter
            async def __aexit__(_self, *a):  # noqa
                # Nothing to clean up at the stream layer — `gen()` ends and
                # FastAPI closes the connection. Cancellation is honoured
                # via `is_disconnected()` checks on each advance.
                return False
        return _Ctx()

    def script_event(self) -> str:
        """One-shot dump of the full phase script — sent BEFORE any
        `advance()` so the frontend can render the upcoming-phases
        skeleton (greyed-out future phases). This is the
        Claude-reference contract: multi-line progressive reveal needs
        to know what's COMING in addition to what's done."""
        return encode_event("script", {
            "surface": self.surface,
            "phases": self.script,
            "total":  len(self.script),
        })

    async def advance(self) -> Optional[str]:
        """Move to the next phase and emit the `phase` event."""
        if await self._stream.is_disconnected():
            return None
        self._index += 1
        if self._index >= len(self.script):
            log.warning("PhaseEmitter advance overran script (surface=%s, index=%d)",
                        self.surface, self._index)
            return None
        phase = self.script[self._index]
        return encode_event("phase", {
            "index":      self._index,
            "label":      phase["label"],
            "icon":       phase.get("icon"),
            "total":      len(self.script),
            "elapsed_ms": int((time.time() - (self._started_at or time.time())) * 1000),
        })

    async def complete(self, result: Any) -> str:
        """Emit the final `complete` event with the long-op's payload.

        The frontend treats `complete` as the cue to (a) flip the
        last phase to a checkmark, (b) navigate to the content
        surface, (c) close the EventSource."""
        # Always emit complete, even if cancelled — clients that are
        # still connected get the result; disconnected ones harmlessly
        # ignore.
        return encode_event("complete", {
            "index":      max(self._index, len(self.script) - 1),
            "total":      len(self.script),
            "elapsed_ms": int((time.time() - (self._started_at or time.time())) * 1000),
            "result":     result,
        })

    async def error(self, message: str, code: str = "internal_error") -> str:
        """Emit an `error` event. Frontend renders the error in the log
        and stops advancing."""
        return encode_event("error", {
            "code":  code,
            "error": message,
        })

    async def heartbeat(self) -> Optional[str]:
        """Comment-line heartbeat (SSE-spec compliant) — keeps the
        connection open during long stretches between phase
        boundaries."""
        if await self._stream.is_disconnected():
            return None
        return encode_heartbeat()
