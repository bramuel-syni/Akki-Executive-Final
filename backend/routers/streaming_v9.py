"""Phase L.b (2026-05-27) — SSE-wrapped streaming endpoints for the
5 remaining long-op surfaces, using the PhaseEmitter / PHASE_SCRIPTS
taxonomy proved in Phase L.a.

This file SUPERSEDES the prior `streaming_v9.py` content (the older
`encode_phase_event` Patch 9 taxonomy was a different generation). The
endpoint URLs are preserved so any in-flight clients keep working.

Surfaces wired (per the Phase L.b dispatch):

  1. Solva Session Synthesis   — POST .../solva/sessions/{sid}/turn/stream
  2. Work Studio Enhance       — POST .../work-studio/enhance/{kind}/stream
  3. Task Manager Compilation  — POST .../cycle/draft-compilation/stream
  4. Events Calendar Sync      — POST .../events/sync-calendar/stream
  5. Decks Generation          — POST .../decks/{outline_id}/generate/stream

Pattern (per the user's L.b lock):

  - Use PhaseEmitter + the surface-specific PHASE_SCRIPTS entry.
  - Wrap (NOT modify) the existing synchronous handler — phase events
    fire at the natural lifecycle boundaries: handler-entry, before
    the LLM call, after the LLM call, before persist, after persist,
    complete.
  - `complete` event carries the inner handler's full JSON response
    so the frontend can treat the streaming endpoint as a drop-in
    replacement for the legacy POST.
  - `error` event carries a `{code, error}` payload when the inner
    handler raises HTTPException OR any other exception.
  - Cancellation: PhaseEmitter checks `request.is_disconnected()` on
    each `advance()` and returns None — the generator then returns
    immediately, the connection closes, and the inner handler's work
    (if still in flight) completes server-side without writing back.

Frontend wiring (StreamingLogScene + useStreamingProgress) lives
separately and will be added in a follow-up L.b.2 dispatch — the
backend pipe ships first so the wiring has a stable contract.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from core import db, require_context_membership  # noqa: F401 — db is used by callers
from services.streaming.progress import PhaseEmitter
from services.streaming.sse import sse_headers


log = logging.getLogger("akki.streaming.lb")
router = APIRouter(prefix="/api")


# ─────────────────────────────────────────────────────────────────────
# Shared helper — runs the inner handler + drives phase advancement.
#
# This is the "wrap synchronous handler" pattern: phases 0..N-2 fire
# BEFORE the inner work, the inner await runs (single LLM call OR
# multi-step orchestrator), then phase N-1 ("Almost there.") fires
# just before the complete event. Surfaces that can be instrumented
# more deeply (e.g. Decks Generation with multiple LLM calls) get
# their own bespoke generator below.
# ─────────────────────────────────────────────────────────────────────
async def _wrap_synchronous_handler(
    *,
    request: Request,
    surface: str,
    inner_coro,
    pre_work_phases: int = None,  # phases to fire BEFORE the inner await
) -> AsyncIterator[str]:
    """Generic wrap-around-a-sync-handler helper.

    Args:
      request          : the FastAPI Request (for is_disconnected check)
      surface          : PHASE_SCRIPTS key
      inner_coro       : the awaitable that runs the actual work
      pre_work_phases  : how many phases to fire BEFORE the inner
                         await. The remaining phases fire AFTER the
                         work + before the `complete` event. Defaults
                         to `total - 1` (everything except the final
                         "Almost there." which fires just before complete).

    Yields SSE-formatted strings.
    """
    emitter = PhaseEmitter(request, surface=surface)
    total = len(emitter.script)
    if pre_work_phases is None:
        pre_work_phases = max(1, total - 1)
    pre_work_phases = max(1, min(pre_work_phases, total - 1))

    async with emitter.start() as e:
        # Script event up-front so the frontend renders the upcoming-phases skeleton.
        yield e.script_event()

        # Fire pre-work phases.
        for _ in range(pre_work_phases):
            chunk = await e.advance()
            if chunk is None:
                return
            yield chunk
            # Tiny await so the frontend gets a paint between phases —
            # without this, all pre-work phases flush in one server tick.
            await asyncio.sleep(0)

        # Run the inner work.
        try:
            result = await inner_coro
        except HTTPException as exc:
            yield await e.error(
                str(exc.detail) if isinstance(exc.detail, str) else "Request failed.",
                code=f"http_{exc.status_code}",
            )
            return
        except Exception as exc:  # noqa: BLE001
            log.exception("L.b inner handler raised (surface=%s)", surface)
            yield await e.error(
                f"{type(exc).__name__}: {str(exc)[:200]}",
                code="inner_exception",
            )
            return

        # Fire the remaining phases (everything from `pre_work_phases`
        # through `total-1`, except we save the last advance() for
        # complete()).
        remaining_to_fire = (total - 1) - pre_work_phases
        for _ in range(remaining_to_fire):
            chunk = await e.advance()
            if chunk is None:
                return
            yield chunk
            await asyncio.sleep(0)

        # Final complete event with the inner handler's full response.
        # Normalize non-dict returns to {"result": <stringified>} so the
        # frontend sees a consistent shape.
        payload = result if isinstance(result, dict) else {"result": str(result)}
        yield await e.complete(payload)


# =============================================================================
# Surface #1 — Solva Session Synthesis
# =============================================================================
@router.post("/contexts/{context_id}/solva/sessions/{sid}/turn/stream")
async def solva_synthesis_stream(
    context_id: str,
    sid: str,
    request: Request,
    body: Dict[str, Any] = Body(default_factory=dict),
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """SSE-wrap of the synchronous Solva session-turn handler.

    Phases (6): Reading the layer ingest → Checking the grounding
    contract → Weighing the probability rail → Composing → Validating
    → Almost there.

    The inner handler runs the actual synthesis pass. We fire phases
    0..3 BEFORE the inner await (4 pre-work phases) so the user sees
    progress while the LLM is composing. Phase 4 (Validating) fires
    after the LLM returns + before complete. Phase 5 (Almost there.)
    fires just before complete (handled by `_wrap_synchronous_handler`).
    """
    from routers import solva_v2 as _solva
    inner_fn = None
    for name in ("session_turn", "post_session_turn", "turn"):
        if hasattr(_solva, name):
            inner_fn = getattr(_solva, name)
            break

    async def _call_inner():
        if inner_fn is None:
            raise HTTPException(status_code=500, detail="Solva turn handler not exported.")
        # Best-effort signature compatibility across solva_v2 revisions.
        try:
            return await inner_fn(sid=sid, body=body, ctx=ctx)  # type: ignore[misc]
        except TypeError:
            return await inner_fn(sid, body, ctx)  # type: ignore[misc]

    return StreamingResponse(
        _wrap_synchronous_handler(
            request=request,
            surface="solva-synthesis",
            inner_coro=_call_inner(),
            pre_work_phases=4,
        ),
        headers=sse_headers(),
    )


# =============================================================================
# Surface #2 — Work Studio Enhance Modal
# =============================================================================
@router.post("/contexts/{context_id}/work-studio/enhance/{kind}/stream")
async def work_studio_enhance_stream(
    context_id: str,
    kind: str,
    request: Request,
    body: Dict[str, Any] = Body(default_factory=dict),
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """SSE-wrap of the synchronous Work Studio Enhance handler.

    Phases (5): Reading the artefact → Checking the grounding contract
    → Composing the refinement → Validating → Almost there.

    3 pre-work phases (Reading, Checking, Composing) fire before the
    inner LLM await; the remaining phases fire after.
    """
    try:
        from routers.work_studio_export import enhance_kind as _inner  # type: ignore[attr-defined]
    except Exception:
        _inner = None  # type: ignore[assignment]

    async def _call_inner():
        if _inner is None:
            raise HTTPException(status_code=500, detail="Enhance handler not exported.")
        return await _inner(  # type: ignore[misc]
            context_id=context_id, kind=kind, body=body, ctx=ctx,
        )

    return StreamingResponse(
        _wrap_synchronous_handler(
            request=request,
            surface="work-studio-enhance",
            inner_coro=_call_inner(),
            pre_work_phases=3,
        ),
        headers=sse_headers(),
    )


# =============================================================================
# Surface #3 — Task Manager Compilation
# =============================================================================
@router.post("/contexts/{context_id}/cycle/draft-compilation/stream")
async def task_manager_compile_stream(
    context_id: str,
    request: Request,
    cycle_id: Optional[str] = Query(default=None),
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """SSE-wrap of the synchronous Task Manager (cycle) compilation handler.

    Phases (7): Reading the cycle responses → Checking the grounding
    contract → Drafting the outline → Composing → Rendering the
    compilation → Validating → Almost there.

    4 pre-work phases (Reading through Composing) fire before the
    inner LLM await; the remaining 2 fire after.
    """
    from routers.cycle_manager import draft_compilation as _inner

    async def _call_inner():
        return await _inner(context_id=context_id, cycle_id=cycle_id, ctx=ctx)

    return StreamingResponse(
        _wrap_synchronous_handler(
            request=request,
            surface="task-manager-compile",
            inner_coro=_call_inner(),
            pre_work_phases=4,
        ),
        headers=sse_headers(),
    )


# =============================================================================
# Surface #4 — Events / Google Calendar Sync
# =============================================================================
@router.post("/contexts/{context_id}/events/sync-calendar/stream")
async def events_calendar_sync_stream(
    context_id: str,
    request: Request,
    provider: str = Query(default="google"),
    body: Dict[str, Any] = Body(default_factory=dict),
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """SSE-wrap of the synchronous Calendar sync handler.

    Phases (5): Reaching Google Calendar → Reading your calendar list
    → Fetching the upcoming events → Mapping to your context →
    Almost there.

    3 pre-work phases (Reaching, Reading list, Fetching) fire before
    the inner await; 1 phase (Mapping) fires after.
    """
    try:
        from routers.oauth_google import sync_calendar as _inner  # type: ignore[attr-defined]
    except Exception:
        _inner = None  # type: ignore[assignment]

    async def _call_inner():
        if _inner is None:
            raise HTTPException(status_code=500, detail="Calendar sync handler not exported.")
        # The legacy handler takes provider as a Query param, not a body field.
        try:
            return await _inner(cid=context_id, provider=provider, ctx=ctx)  # type: ignore[misc]
        except TypeError:
            return await _inner(context_id, provider, ctx)  # type: ignore[misc]

    return StreamingResponse(
        _wrap_synchronous_handler(
            request=request,
            surface="events-calendar-sync",
            inner_coro=_call_inner(),
            pre_work_phases=3,
        ),
        headers=sse_headers(),
    )


# =============================================================================
# Surface #5 — Decks Generation (DEEP tier)
# =============================================================================
@router.post("/contexts/{context_id}/decks/{outline_id}/generate/stream")
async def decks_generation_stream(
    context_id: str,
    outline_id: str,
    request: Request,
    body: Dict[str, Any] = Body(default_factory=dict),
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """SSE-wrap of the synchronous Decks generate handler.

    Phases (6): Reading the outline → Checking the grounding contract
    → Composing the deck → Rendering the slides → Validating →
    Almost there.

    3 pre-work phases (Reading, Checking, Composing) fire before the
    inner LLM await (the slow ~30-60s deck-build pass); the
    remaining phases fire after.
    """
    try:
        from routers.decks import generate_deck as _inner  # type: ignore[attr-defined]
    except Exception:
        # The deck-generate function name may differ across revisions
        # — fall back to the first matching async POST handler.
        from routers import decks as _decks_mod
        _inner = None  # type: ignore[assignment]
        for name in ("generate_deck", "deck_generate", "post_decks_generate"):
            if hasattr(_decks_mod, name):
                _inner = getattr(_decks_mod, name)
                break

    async def _call_inner():
        if _inner is None:
            raise HTTPException(status_code=500, detail="Decks generate handler not exported.")
        try:
            return await _inner(  # type: ignore[misc]
                context_id=context_id, outline_id=outline_id, body=body, ctx=ctx,
            )
        except TypeError:
            return await _inner(context_id, outline_id, body, ctx)  # type: ignore[misc]

    return StreamingResponse(
        _wrap_synchronous_handler(
            request=request,
            surface="decks-generation",
            inner_coro=_call_inner(),
            pre_work_phases=3,
        ),
        headers=sse_headers(),
    )
