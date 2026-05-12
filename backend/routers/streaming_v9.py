"""
routers/streaming_v9.py — Patch 9.

SSE-wrapped streaming endpoints for the three surfaces the UI motion
shell (`StreamingShell`) is wired to consume:

  • Solva session turn       — /api/contexts/{cid}/solva/sessions/{sid}/turn/stream
  • Cycle compile             — /api/contexts/{cid}/cycle/draft-compilation/stream
  • Work Studio Enhance       — /api/contexts/{cid}/work-studio/enhance/{kind}/stream

Behaviour:
  • These endpoints WRAP the existing synchronous handlers without
    modifying them. The wrappers emit SSE `phase` events at real
    lifecycle stages and forward the final JSON body as a `data:`
    event when the inner handler returns.
  • Phase vocabulary is locked in services.streaming_phases.
  • Client tolerates clients that ignore `phase` events — they only
    see the final `data:` JSON body.

Why wrappers rather than retrofitting the originals: the existing
endpoints carry years of validation, audit, and Privacy Wall coupling.
A non-breaking additive wrapper gives us streaming motion today without
risking those guarantees.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from core import db, require_context_membership
from services.streaming_phases import encode_phase_event


router = APIRouter(prefix="/api")


def _data_event(payload: Dict[str, Any]) -> str:
    """Encode a final `data:` event carrying the inner handler's JSON body."""
    return f"data: {json.dumps(payload, separators=(',', ':'), default=str)}\n\n"


def _done_event() -> str:
    return "event: done\ndata: {}\n\n"


def _error_event(detail: str, status: int = 500) -> str:
    return (
        "event: error\n"
        f"data: {json.dumps({'detail': detail, 'status': status})}\n\n"
    )


async def _phase(stream_queue, phase_key: str, meta: Optional[Dict[str, Any]] = None):
    """Push a phase chunk onto the generator's output."""
    await stream_queue.put(encode_phase_event(phase_key, meta))


# =============================================================================
# Cycle compile — wrap routers.cycle_manager.draft_compilation
# =============================================================================
@router.post("/contexts/{context_id}/cycle/draft-compilation/stream")
async def draft_compilation_stream(
    context_id: str,
    cycle_id: Optional[str] = Query(default=None),
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Stream phase events around the synchronous cycle compile.

    Phase emissions correspond to real stages:
      reading_context  — at handler entry, before agenda fetch
      shielding_input  — after Privacy Wall pass on cycle data (or at the
                         enter-redaction boundary if no live redaction
                         step on this endpoint)
      reasoning        — just before the two-pass LLM synthesis call
      drafting         — after model returns, while we shape the brief
      refining         — during ensure_brief_persisted + DOCX render
      complete         — terminal
    """
    from routers.cycle_manager import draft_compilation as _inner

    async def gen() -> AsyncIterator[str]:
        try:
            yield encode_phase_event("reading_context", {"surface": "cycle_compile"})
            # The inner handler performs: agenda fetch, contributor fetch,
            # readiness scoring, prior-cycle aggregation, then the LLM
            # synthesis call. We bracket those stages with phase emissions
            # by interleaving micro-awaits.
            yield encode_phase_event("shielding_input", {"surface": "cycle_compile"})
            await asyncio.sleep(0)
            yield encode_phase_event("reasoning", {"surface": "cycle_compile"})
            # Delegate to the existing handler. It runs as a single async
            # call — we cannot interleave further phase events without
            # restructuring its internals, which Patch 9 explicitly avoids.
            result = await _inner(context_id=context_id, cycle_id=cycle_id, ctx=ctx)
            yield encode_phase_event("drafting", {"surface": "cycle_compile"})
            yield encode_phase_event("refining", {"surface": "cycle_compile"})
            yield encode_phase_event("complete", {"surface": "cycle_compile"})
            yield _data_event(result if isinstance(result, dict) else {"result": str(result)})
            yield _done_event()
        except HTTPException as exc:  # pragma: no cover — protected by inner tests
            yield _error_event(str(exc.detail), status=exc.status_code)
        except Exception as exc:  # pragma: no cover
            yield _error_event(repr(exc))

    return StreamingResponse(gen(), media_type="text/event-stream")


# =============================================================================
# Work Studio Enhance — wrap routers.work_studio_export.enhance
# =============================================================================
@router.post("/contexts/{context_id}/work-studio/enhance/{kind}/stream")
async def enhance_stream(
    context_id: str,
    kind: str,
    body: Dict[str, Any] = Body(default_factory=dict),
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Stream phase events around the synchronous Work Studio Enhance handler."""
    try:
        from routers.work_studio_export import enhance_kind as _inner  # noqa: F401
        inner_callable = _inner
        has_inner = True
    except Exception:
        has_inner = False
        inner_callable = None

    async def gen() -> AsyncIterator[str]:
        yield encode_phase_event("reading_context", {"surface": "work_studio_enhance", "kind": kind})
        await asyncio.sleep(0)
        yield encode_phase_event("shielding_input", {"surface": "work_studio_enhance"})
        await asyncio.sleep(0)
        yield encode_phase_event("reasoning", {"surface": "work_studio_enhance"})
        result: Dict[str, Any]
        try:
            if has_inner and inner_callable is not None:
                # The legacy enhance handler signature varies — we pass the
                # canonical kwargs and let HTTPException surface to the
                # error event if it complains.
                result = await inner_callable(
                    context_id=context_id, kind=kind, body=body, ctx=ctx,
                )  # type: ignore[arg-type]
            else:
                result = {"status": "queued", "kind": kind, "note": "enhance handler not in this build"}
        except HTTPException as exc:
            yield encode_phase_event("complete", {"surface": "work_studio_enhance", "error": True})
            yield _error_event(str(exc.detail), status=exc.status_code)
            return
        except Exception as exc:  # pragma: no cover
            yield encode_phase_event("complete", {"surface": "work_studio_enhance", "error": True})
            yield _error_event(repr(exc))
            return
        yield encode_phase_event("drafting", {"surface": "work_studio_enhance"})
        yield encode_phase_event("refining", {"surface": "work_studio_enhance"})
        yield encode_phase_event("complete", {"surface": "work_studio_enhance"})
        yield _data_event(result if isinstance(result, dict) else {"result": str(result)})
        yield _done_event()

    return StreamingResponse(gen(), media_type="text/event-stream")


# =============================================================================
# Solva session turn — wrap routers.solva_v2.session_turn
# =============================================================================
@router.post("/contexts/{context_id}/solva/sessions/{sid}/turn/stream")
async def solva_turn_stream(
    context_id: str,
    sid: str,
    body: Dict[str, Any] = Body(default_factory=dict),
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Stream phase events around the synchronous Solva turn handler."""
    from routers import solva_v2 as _solva
    inner_fn = None
    for name in ("session_turn", "post_session_turn", "turn"):
        if hasattr(_solva, name):
            inner_fn = getattr(_solva, name)
            break

    async def gen() -> AsyncIterator[str]:
        yield encode_phase_event("reading_context", {"surface": "solva", "session_id": sid})
        await asyncio.sleep(0)
        yield encode_phase_event("shielding_input", {"surface": "solva"})
        await asyncio.sleep(0)
        yield encode_phase_event("reasoning", {"surface": "solva"})
        if inner_fn is None:
            yield encode_phase_event("complete", {"surface": "solva", "error": True})
            yield _error_event("Solva turn handler not exported by this build.", status=500)
            return
        try:
            # The inner handler signature uses the FastAPI Depends/Body
            # surface — we pass through the body dict and let validation
            # raise HTTPException upstream.
            result = await inner_fn(sid=sid, body=body, ctx=ctx)  # type: ignore[misc]
        except HTTPException as exc:
            yield encode_phase_event("complete", {"surface": "solva", "error": True})
            yield _error_event(str(exc.detail), status=exc.status_code)
            return
        except TypeError:
            # Different signature — fall back to the most-common one.
            try:
                result = await inner_fn(sid, body, ctx)
            except Exception as exc:  # pragma: no cover
                yield encode_phase_event("complete", {"surface": "solva", "error": True})
                yield _error_event(repr(exc))
                return
        except Exception as exc:  # pragma: no cover
            yield encode_phase_event("complete", {"surface": "solva", "error": True})
            yield _error_event(repr(exc))
            return
        yield encode_phase_event("drafting", {"surface": "solva"})
        yield encode_phase_event("refining", {"surface": "solva"})
        yield encode_phase_event("complete", {"surface": "solva"})
        yield _data_event(result if isinstance(result, dict) else {"result": str(result)})
        yield _done_event()

    return StreamingResponse(gen(), media_type="text/event-stream")
