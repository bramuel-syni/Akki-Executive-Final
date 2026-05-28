"""Phase L.b (2026-05-27) — SSE-wrapped streaming endpoints for the
5 remaining long-op surfaces, using the PhaseEmitter / PHASE_SCRIPTS
taxonomy proved in Phase L.a.

Phase L.b.3 (2026-05-27, fork-resume) — backend reconciliation. The
L.b.2 close-out shipped the visual contract via timer-driven phase
walks (`usePhasedTimer`); L.b.3 swaps each surface to real
backend-driven SSE so the phase events reflect the actual inner
handler's lifecycle.

Per-surface reconciliations applied:

  1. **Solva Synthesis** — URL changed from
     `/api/contexts/{cid}/solva/sessions/{sid}/turn/stream` to
     `/api/solva/v2/sessions/{sid}/turn/stream` matching the legacy
     account-scoped `post_turn` signature. Body coerced from dict →
     `TurnV2In`.
  2. **Work Studio Enhance** — endpoint accepts MULTIPART (`Form` +
     `UploadFile`) matching the legacy `start_enhance`, then runs the
     enhance worker inline so SSE phases bracket the work.
  3. **Task Manager Compile** — calls the new blocking variant
     (`cycle_manager.draft_compilation_blocking`) instead of the
     202+job_id `draft_compilation` — preserves the job-queue path for
     non-streaming callers (cron, worker re-runs) but feeds the SSE
     wrap a single awaitable.
  4. **Calendar Sync** — adapter passes `me=ctx["account"]` to match
     the inner `sync_calendar` signature (was passing `ctx=`).
  5. **Decks Generation** — body coerced from dict → `GenerateIn`.

Pattern (unchanged from L.b):

  - Use PhaseEmitter + the surface-specific PHASE_SCRIPTS entry.
  - Wrap the existing synchronous handler — phases fire at lifecycle
    boundaries.
  - `complete` event carries the inner handler's full JSON response.
  - `error` event carries `{code, error}` on any HTTPException / Exception.
  - Cancellation honoured via `request.is_disconnected()`.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, AsyncIterator, Dict, Optional

from fastapi import (
    APIRouter, Body, Depends, File, Form, HTTPException, Query, Request,
    UploadFile,
)
from fastapi.responses import StreamingResponse

from core import db, iso, now, get_current_account, require_context_membership, write_audit
from services.streaming.progress import PhaseEmitter
from services.streaming.sse import sse_headers


log = logging.getLogger("akki.streaming.lb")
router = APIRouter(prefix="/api")


# ─────────────────────────────────────────────────────────────────────
# Shared helper — runs the inner handler + drives phase advancement.
# ─────────────────────────────────────────────────────────────────────
async def _wrap_synchronous_handler(
    *,
    request: Request,
    surface: str,
    inner_coro,
    pre_work_phases: int = None,
) -> AsyncIterator[str]:
    """Generic wrap-around-a-sync-handler helper."""
    emitter = PhaseEmitter(request, surface=surface)
    total = len(emitter.script)
    if pre_work_phases is None:
        pre_work_phases = max(1, total - 1)
    pre_work_phases = max(1, min(pre_work_phases, total - 1))

    async with emitter.start() as e:
        yield e.script_event()

        for _ in range(pre_work_phases):
            chunk = await e.advance()
            if chunk is None:
                return
            yield chunk
            await asyncio.sleep(0)

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

        remaining_to_fire = (total - 1) - pre_work_phases
        for _ in range(remaining_to_fire):
            chunk = await e.advance()
            if chunk is None:
                return
            yield chunk
            await asyncio.sleep(0)

        payload = result if isinstance(result, dict) else {"result": str(result)}
        yield await e.complete(payload)


# =============================================================================
# Surface #1 — Solva Session Synthesis
# Account-scoped URL matches legacy `post_turn`. Body coerced to TurnV2In.
# =============================================================================
@router.post("/solva/v2/sessions/{sid}/turn/stream")
async def solva_synthesis_stream(
    sid: str,
    request: Request,
    body: Dict[str, Any] = Body(default_factory=dict),
    account: Dict[str, Any] = Depends(get_current_account),
):
    """SSE-wrap of the synchronous Solva session-turn handler.

    Phases (6): Reading the layer ingest → Checking the grounding
    contract → Weighing the probability rail → Composing → Validating
    → Almost there.
    """
    from routers.solva_v2 import post_turn as _inner, TurnV2In

    async def _call_inner():
        try:
            turn_body = TurnV2In(**(body or {}))
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=422, detail=f"Invalid turn body: {exc}")
        return await _inner(sid=sid, body=turn_body, account=account)

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
# Accepts MULTIPART (Form + UploadFile) matching the legacy `start_enhance`.
# Resolves source bytes, inserts the export row, runs `_run_enhance` inline.
# =============================================================================
@router.post("/contexts/{context_id}/work-studio/enhance/{kind}/stream")
async def work_studio_enhance_stream(
    context_id: str,
    kind: str,
    request: Request,
    instructions: str = Form(...),
    output_format: str = Form("auto"),
    source_artefact_id: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """SSE-wrap of the Work Studio Enhance flow.

    Phases (5): Reading the artefact → Checking the grounding contract
    → Composing the refinement → Validating → Almost there.

    Inline runner: resolves source → inserts row → runs `_run_enhance`
    in-process so SSE phases bracket the actual two-pass LLM work.
    The `complete` event carries the final export row (status,
    download_token, continue_chat_id, etc.).
    """
    from routers.work_studio_export import (
        _resolve_enhance_source, _resolve_format, _ENHANCE_KINDS,
        _is_thin_enhance_shape, _emit_thin_refusal, _append_chat_audit,
        _run_enhance,
    )

    # Validate upfront so we surface 4xx as HTTPException (caught by wrap → error event).
    if kind not in _ENHANCE_KINDS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown enhance kind. Allowed: {', '.join(_ENHANCE_KINDS)}.",
        )
    if not instructions or not instructions.strip():
        raise HTTPException(status_code=400, detail="instructions is required.")
    fmt = _resolve_format(
        kind,
        output_format if output_format in ("docx", "pptx", "pdf", "auto") else "auto",
    )

    # Resolve source bytes BEFORE entering the SSE generator (so 4xx
    # surface as HTTP responses, not as phase-error events).
    source_bytes, source_filename, source_label = await _resolve_enhance_source(
        context_id=context_id,
        account_id=ctx["account"]["id"],
        kind=kind,
        file=file,
        source_artefact_id=source_artefact_id,
    )

    export_id = str(uuid.uuid4())
    created_at = iso(now())
    row = {
        "id": export_id,
        "context_id": context_id,
        "account_id": ctx["account"]["id"],
        "kind": kind,
        "output_format": fmt,
        "status": "running",
        "source": "enhance",
        "instructions_chars": len(instructions),
        "source_label": source_label,
        "source_filename": source_filename,
        "source_artefact_id": source_artefact_id,
        "created_at": created_at,
        "completed_at": None,
        "file_name": None,
        "file_path": None,
        "sha256": None,
        "sensitivity_band": None,
        "error": None,
        "refusal_text": None,
        "chat_audit_id": None,
    }
    await db.work_studio_exports.insert_one(row)

    try:
        await write_audit(
            account_id=ctx["account"]["id"], context_id=context_id,
            action="work_studio.enhance.requested", target_id=export_id,
            metadata={"export_id": export_id, "kind": kind,
                      "output_format": fmt, "source_label": source_label,
                      "source_filename": source_filename,
                      "via": "stream"},
        )
    except Exception:
        pass

    try:
        await _append_chat_audit(
            account_id=ctx["account"]["id"],
            chat_id=f"enhance-{export_id}", action="enhance.requested",
            payload={
                "export_kind": f"enhance_{kind}",
                "export_artefact_id": export_id,
                "source_label": source_label,
                "source_filename": source_filename,
                "instructions_preview": instructions[:200],
                "output_format": fmt,
                "channel": "enhance",
                "deterministic": True,
                "via": "stream",
            }, request=None,
        )
    except Exception:
        log.warning("enhance.requested audit-append failed (non-fatal)")

    # Thin-input deterministic refusal (pre-LLM).
    thin_shape = _is_thin_enhance_shape(instructions)
    if thin_shape is not None:
        await _emit_thin_refusal(
            export_id=export_id, account_id=ctx["account"]["id"],
            context_id=context_id, kind=kind, source="enhance",
            detection={**thin_shape, "stage": "pre_llm_enhance"},
        )
        raise HTTPException(status_code=400, detail={
            "code": "thin_input",
            "export_id": export_id,
            "error": "thin_input",
        })

    async def _call_inner():
        # Run the worker inline; the row is updated server-side as it
        # progresses. We re-read the row at the end for the complete payload.
        await _run_enhance(
            export_id=export_id,
            account_id=ctx["account"]["id"],
            context_id=context_id,
            kind=kind,
            output_format=fmt,
            instructions=instructions,
            source_data=source_bytes,
            source_filename=source_filename,
            source_label=source_label,
        )
        final = await db.work_studio_exports.find_one(
            {"id": export_id}, {"_id": 0},
        )
        return final or {"export_id": export_id, "status": "unknown"}

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
# Uses the new blocking variant; legacy job-queue path preserved.
# =============================================================================
@router.post("/contexts/{context_id}/cycle/draft-compilation/stream")
async def task_manager_compile_stream(
    context_id: str,
    request: Request,
    cycle_id: Optional[str] = Query(default=None),
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """SSE-wrap of the Task Manager (cycle) compile flow.

    Phases (7): Reading the cycle responses → Checking the grounding
    contract → Drafting the outline → Composing → Rendering the
    compilation → Validating → Almost there.
    """
    from routers.cycle_manager import draft_compilation_blocking as _inner

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
# Adapter passes `me=ctx["account"]` to match the inner signature.
# =============================================================================
@router.post("/contexts/{context_id}/events/sync-calendar/stream")
async def events_calendar_sync_stream(
    context_id: str,
    request: Request,
    provider: str = Query(default="google"),
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """SSE-wrap of the Calendar sync handler.

    Phases (5): Reaching Google Calendar → Reading your calendar list
    → Fetching the upcoming events → Mapping to your context →
    Almost there.
    """
    from routers.oauth_google import sync_calendar as _inner

    async def _call_inner():
        return await _inner(cid=context_id, provider=provider, me=ctx["account"])

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
# Body coerced from dict → `GenerateIn` Pydantic model.
# =============================================================================
@router.post("/contexts/{context_id}/decks/{outline_id}/generate/stream")
async def decks_generation_stream(
    context_id: str,
    outline_id: str,
    request: Request,
    body: Dict[str, Any] = Body(default_factory=dict),
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """SSE-wrap of the Decks generate handler.

    Phases (6): Reading the outline → Checking the grounding contract
    → Composing the deck → Rendering the slides → Validating →
    Almost there.
    """
    from routers.decks import generate_deck as _inner, GenerateIn

    async def _call_inner():
        body_with_outline = {**(body or {})}
        body_with_outline.setdefault("outline_id", outline_id)
        try:
            gen_body = GenerateIn(**body_with_outline)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=422, detail=f"Invalid generate body: {exc}")
        return await _inner(
            context_id=context_id,
            outline_id=outline_id,
            body=gen_body,
            ctx=ctx,
        )

    return StreamingResponse(
        _wrap_synchronous_handler(
            request=request,
            surface="decks-generation",
            inner_coro=_call_inner(),
            pre_work_phases=3,
        ),
        headers=sse_headers(),
    )
