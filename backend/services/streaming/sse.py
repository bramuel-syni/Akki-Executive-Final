"""Phase L.a (2026-05-27) — SSE helper for the streaming-progress pipe.

The pipe is server→client only (events flow from the long-op endpoint
out to the browser EventSource). Each long-op endpoint that opts into
the pipe accepts a `?stream=1` query param; when set, the endpoint
returns a `StreamingResponse(media_type="text/event-stream")` instead
of its normal JSON response, with the final-result payload emitted as
the LAST event (`event: complete`).

**Ingress note:** the L.a probe verified that the deployment ingress
passes SSE through with no buffering at 1-second cadence. We
still set `X-Accel-Buffering: no` + `Cache-Control: no-transform` as
defence-in-depth against any future ingress that turns buffering on.

**Cancellation:** every emit checks `request.is_disconnected()` and
short-circuits if the client navigated away. The long-op endpoint
should propagate the cancellation by checking `emitter.cancelled`
between major work steps and skipping the persistence step.

**Heartbeat:** `:heartbeat` comments are emitted every 15s during long
stretches between phase boundaries so the EventSource never drops the
connection (default browser EventSource timeout is 90s on most pods).
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Optional

from fastapi import Request


log = logging.getLogger("akki.streaming.sse")


_SSE_HEADERS = {
    "Cache-Control":     "no-cache, no-transform",
    "X-Accel-Buffering": "no",
    "Connection":        "keep-alive",
    "Content-Type":      "text/event-stream; charset=utf-8",
}


def sse_headers() -> Dict[str, str]:
    """Headers to pass to FastAPI's `StreamingResponse(..., headers=...)`."""
    return dict(_SSE_HEADERS)


def encode_event(event: str, data: Any) -> str:
    """Encode a single SSE event in the wire format the browser
    EventSource expects:

        event: <event_name>
        data: <json-payload>
        \n

    The trailing blank line is the event delimiter."""
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def encode_heartbeat() -> str:
    """SSE comment line — keeps the connection alive without firing a
    client-side `onmessage` handler."""
    return f": heartbeat {int(time.time())}\n\n"


class SSEStream:
    """Yielding context manager for SSE long-op endpoints.

    Usage:
        async def long_op(request: Request, stream: int = 0):
            if not stream:
                return await _legacy_json_path()
            async def gen():
                async with SSEStream(request) as s:
                    async for evt in s.heartbeat_loop():
                        yield evt
                    # caller emits via s.emit(...)
            return StreamingResponse(gen(), headers=sse_headers())

    The recommended pattern is `PhaseEmitter` (see `progress.py`) which
    composes SSEStream with a static phase script.
    """

    HEARTBEAT_INTERVAL_S = 15.0

    def __init__(self, request: Request):
        self.request = request
        self._cancelled = False
        self._closed = False

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    async def is_disconnected(self) -> bool:
        if self._cancelled:
            return True
        try:
            if await self.request.is_disconnected():
                self._cancelled = True
                return True
        except Exception:
            # Treat any check failure as not-disconnected — the next
            # emit will retry. Don't abort the stream on transient
            # failures.
            pass
        return False

    async def emit(self, event: str, data: Any) -> Optional[str]:
        """Returns the wire-format string for the generator to yield,
        or None if the client has disconnected."""
        if await self.is_disconnected():
            return None
        return encode_event(event, data)

    async def heartbeat(self) -> Optional[str]:
        if await self.is_disconnected():
            return None
        return encode_heartbeat()
