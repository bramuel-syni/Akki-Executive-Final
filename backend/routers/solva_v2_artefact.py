"""Solva v2 — Backend artefact-payload endpoint (Slice 2a).

Exposes the Slice 1 structured payload at:
  GET /api/solva/sessions/{sid}/v2/payload

Frontend `SolvaArtefactV2.jsx` (Slice 2a) fetches this and renders the
15-element slide-paginated artefact. Feature flag gated — when
`solva_v2_enabled_for(account)` returns False, the endpoint returns
HTTP 404 so callers can't accidentally consume v2 with v1 UI.

The payload is built fresh from session state on every call (no
caching) — the deterministic adapter is fast (<10ms) and the freshest
read is preferred while v2 is in active iteration. Slice 7 polish can
introduce a payload cache + invalidation if needed.

Integrity validator runs INLINE before returning the payload — if any
blocking offender is detected, the endpoint returns HTTP 422 with the
structured offender list. Renderers MUST handle 422 gracefully (Slice
2a's `SolvaArtefactV2.jsx` shows a "report under review" placeholder).
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from server import db  # type: ignore
from routers.auth import get_current_account  # type: ignore
from services.solva_v2.feature_flag import solva_v2_enabled_for
from services.solva_v2.payload_builder import build_payload
from services.solva_v2.integrity_validators import validate_artefact


logger = logging.getLogger("solva.v2.artefact_payload")


router = APIRouter(prefix="/api/solva", tags=["solva-v2-artefact"])


@router.get("/sessions/{sid}/v2/payload")
async def get_v2_artefact_payload(
    sid: str,
    account: Dict[str, Any] = Depends(get_current_account),
):
    """Return the Slice 1 `ArtefactPayload` for this session as JSON.

    Gates:
      • Session must exist + belong to the authenticated account
      • Feature flag must be ON for this account (or globally via env)
      • All 4 integrity validators must pass; if not, HTTP 422 with
        offender list

    Response shape:
      {
        "schema_version": "solva.v2.artefact.1.0",
        "session_id": "...",
        "payload": <ArtefactPayload as JSON>,
        "validator_passes": true,
      }
    """
    if not solva_v2_enabled_for(account):
        # Hide the endpoint when the flag is off — callers cannot
        # discover v2 by URL probing.
        raise HTTPException(status_code=404, detail="Solva v2 not enabled")

    rec = await db.solva_v2_sessions.find_one(
        {"id": sid, "account_id": account["id"]}, {"_id": 0},
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Session not found.")

    # Resolve a human-readable context name for the cover slide.
    context_name = "Context"
    cid = rec.get("context_id")
    if cid:
        ctx = await db.contexts.find_one({"id": cid}, {"_id": 0, "name": 1})
        if ctx and ctx.get("name"):
            context_name = ctx["name"]

    try:
        payload = build_payload(rec, context_name=context_name)
    except Exception as exc:  # noqa: BLE001
        logger.exception("solva v2 payload build failed sid=%s", sid)
        raise HTTPException(
            status_code=500,
            detail=f"Payload build failed: {exc}",
        ) from exc

    validation = validate_artefact(payload, rec)
    if not validation.ok:
        # Return structured offender list so callers can render a
        # "report under review" placeholder with the integrity audit
        # surfaced for transparency.
        raise HTTPException(
            status_code=422,
            detail={
                "error": "integrity_validation_failed",
                "blocking_offenders": [
                    {
                        "validator": o.validator,
                        "location": o.location,
                        "message": o.message,
                        "revision_hint": o.revision_hint,
                    }
                    for o in validation.blocking
                ],
            },
        )

    return {
        "schema_version": payload.schema_version,
        "session_id": payload.session_id,
        "payload": payload.model_dump(),
        "validator_passes": True,
    }



# ─────────────────────────────────────────────────────────────────
# Slice 3a — Live reasoning stream SSE endpoint
# ─────────────────────────────────────────────────────────────────

import asyncio  # noqa: E402
import json     # noqa: E402

from fastapi import Request                               # noqa: E402
from fastapi.responses import StreamingResponse           # noqa: E402

from services.streaming.sse import (                      # noqa: E402
    sse_headers,
    encode_event,
    encode_heartbeat,
)
from services.solva_v2.stream_schema import SolvaStreamEvent  # noqa: E402
from services.solva_v2.stream_synthesizer import synthesize_events  # noqa: E402


# Rapid-replay cadence: how long the synthesized event sequence takes
# to flush to the browser EventSource. 5 seconds total budget; events
# distribute uniformly. The frontend ticker animates each event as
# it arrives, so the founder gets the "watched it think" experience
# even on a session that completed minutes ago.
REPLAY_TOTAL_BUDGET_S = 4.0
REPLAY_MIN_GAP_S = 0.08   # never burst faster than 80ms — keeps the
                          # ticker readable on slower devices
REPLAY_MAX_GAP_S = 0.45   # cap any single gap so the deck still feels
                          # alive even if the event count is small


@router.get("/sessions/{sid}/v2/stream")
async def stream_v2_reasoning(
    sid: str,
    request: Request,
    account: Dict[str, Any] = Depends(get_current_account),
):
    """Server-Sent-Events stream of Solva's 5-layer reasoning pass.

    For complete sessions, replays the deterministic synthesized event
    sequence in a 4-second rapid-burst so the founder gets the visceral
    "watch it think" experience whenever they open the artefact.

    For in-flight sessions (status != "completed"), the stream returns
    only the events that have happened so far + closes — live-mode
    instrumentation lands in Slice 3a.next when the 5-layer engine
    pipeline is wired to a per-session asyncio.Queue. Today the engines
    write to the audit log synchronously inside their long-op endpoints,
    so a parallel stream would need a refactor that's outside the
    Slice 3a scope.

    Wire format (one SSE event per emitted SolvaStreamEvent):
        event: solva.reasoning
        data:  <SolvaStreamEvent JSON>

    Closes with:
        event: complete
        data:  {"total_events": N}
    """
    # Same gates as the payload endpoint.
    if not solva_v2_enabled_for(account):
        raise HTTPException(status_code=404, detail="Solva v2 not enabled")

    rec = await db.solva_v2_sessions.find_one(
        {"id": sid, "account_id": account["id"]}, {"_id": 0},
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Session not found.")

    # Resolve context name (mirrors the /v2/payload endpoint).
    context_name = "Context"
    cid = rec.get("context_id")
    if cid:
        ctx = await db.contexts.find_one({"id": cid}, {"_id": 0, "name": 1})
        if ctx and ctx.get("name"):
            context_name = ctx["name"]

    # Build the payload + synthesize the event sequence. If payload
    # build raises, surface as 500 (same as the /v2/payload endpoint).
    try:
        payload = build_payload(rec, context_name=context_name)
    except Exception as exc:  # noqa: BLE001
        logger.exception("solva v2 stream payload build failed sid=%s", sid)
        raise HTTPException(
            status_code=500,
            detail=f"Stream payload build failed: {exc}",
        ) from exc

    events: list[SolvaStreamEvent] = synthesize_events(
        session_id=sid, payload=payload,
    )

    # Compute the inter-event gap based on the synthesized count.
    n_events = len(events)
    if n_events <= 1:
        gap_s = REPLAY_MIN_GAP_S
    else:
        gap_s = REPLAY_TOTAL_BUDGET_S / (n_events - 1)
        if gap_s < REPLAY_MIN_GAP_S:
            gap_s = REPLAY_MIN_GAP_S
        if gap_s > REPLAY_MAX_GAP_S:
            gap_s = REPLAY_MAX_GAP_S

    async def _gen():
        # Initial frame: surface the total expected count so the
        # frontend can render a complete ticker skeleton up front.
        yield encode_event("solva.reasoning.script", {
            "session_id": sid,
            "total_events": n_events,
            "schema_version": "solva.v2.stream.1.0",
        })
        for ev in events:
            # Cancellation check: if the client navigates away the
            # generator must stop emitting.
            try:
                if await request.is_disconnected():
                    return
            except Exception:
                pass  # transient ASGI check failure — keep going

            yield encode_event("solva.reasoning", ev.model_dump())
            await asyncio.sleep(gap_s)

        # Final closure event.
        yield encode_event("complete", {
            "total_events": n_events,
            "schema_version": "solva.v2.stream.1.0",
        })

    return StreamingResponse(_gen(), headers=sse_headers())



# ─────────────────────────────────────────────────────────────────
# PPTX export — queue position 4 (2026-05-29)
# ─────────────────────────────────────────────────────────────────

import time as _time     # noqa: E402
from datetime import datetime as _datetime  # noqa: E402

from fastapi.responses import Response       # noqa: E402

from services.solva_v2.pptx_exporter import build_pptx  # noqa: E402


@router.get("/sessions/{sid}/v2/export.pptx")
async def export_v2_pptx(
    sid: str,
    account: Dict[str, Any] = Depends(get_current_account),
):
    """Stream a native .pptx file rendered from the 16-element
    artefact schema.

    Auth + feature-flag gates mirror `/v2/payload` exactly. On every
    successful export, write a `solva_v2_pptx_export` row to
    `db.audit_log` carrying session id + account id + slide count.
    """
    if not solva_v2_enabled_for(account):
        raise HTTPException(status_code=404, detail="Solva v2 not enabled")

    rec = await db.solva_v2_sessions.find_one(
        {"id": sid, "account_id": account["id"]}, {"_id": 0},
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Session not found.")

    context_name = "Context"
    cid = rec.get("context_id")
    if cid:
        ctx = await db.contexts.find_one({"id": cid}, {"_id": 0, "name": 1})
        if ctx and ctx.get("name"):
            context_name = ctx["name"]

    try:
        payload = build_payload(rec, context_name=context_name)
    except Exception as exc:  # noqa: BLE001
        logger.exception("solva v2 pptx payload build failed sid=%s", sid)
        raise HTTPException(
            status_code=500, detail=f"Payload build failed: {exc}",
        ) from exc

    # Run validators as a soft gate — the .pptx export uses the same
    # truth-source as the on-screen artefact, so blocking offenders
    # should never reach the renderer. Log and proceed so auditors get
    # the export even when validation surfaces a soft warning.
    validation = validate_artefact(payload, rec)
    if not validation.ok:
        logger.warning(
            "solva v2 pptx export with validator offenders sid=%s offenders=%d",
            sid, len(validation.offenders),
        )

    t0 = _time.perf_counter()
    try:
        pptx_bytes = build_pptx(payload, context_name=context_name)
    except Exception as exc:  # noqa: BLE001
        logger.exception("pptx render failed sid=%s", sid)
        raise HTTPException(
            status_code=500, detail=f"PPTX render failed: {exc}",
        ) from exc
    render_ms = int((_time.perf_counter() - t0) * 1000)

    # Audit log — every successful export writes a row that observability
    # can aggregate against to spot abuse / cost / unexpected fan-out.
    try:
        await db.audit_log.insert_one({
            "id": f"solva-pptx-{sid}-{int(_time.time() * 1000)}",
            "kind": "solva_v2_pptx_export",
            "actor_id": account["id"],
            "actor_email": account.get("email"),
            "session_id": sid,
            "context_id": cid,
            "slide_count": 16,
            "bytes": len(pptx_bytes),
            "render_ms": render_ms,
            "validator_passes": validation.ok,
            "ts": _datetime.utcnow().isoformat() + "Z",
        })
    except Exception:  # noqa: BLE001
        logger.exception("pptx audit log insert failed sid=%s", sid)

    # Filename embeds the session id + a yyyy-mm-dd stamp so multiple
    # exports across days don't collide in the founder's Downloads.
    filename = f"solva-{sid[:8]}-{_datetime.utcnow().strftime('%Y-%m-%d')}.pptx"
    return Response(
        content=pptx_bytes,
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "presentationml.presentation"
        ),
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Solva-V2-Slide-Count": "16",
            "X-Solva-V2-Render-Ms": str(render_ms),
        },
    )



# Z2.8 (2026-02) — chair-notes endpoint. Same strings the PPTX
# exporter writes into slide notes; consumed by <ChairNotesStrip>
# when the user toggles `Notes` on the Solva v2 topbar.
from services.solva_v2.chair_notes import chair_notes_dict  # noqa: E402


@router.get("/sessions/{sid}/v2/chair_notes")
async def get_v2_chair_notes(
    sid: str,
    account: Dict[str, Any] = Depends(get_current_account),
):
    if not solva_v2_enabled_for(account):
        raise HTTPException(status_code=404, detail="Solva v2 not enabled")
    rec = await db.solva_v2_sessions.find_one(
        {"id": sid, "account_id": account["id"]}, {"_id": 0},
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Session not found.")
    cid = rec.get("context_id")
    ctx = (await db.contexts.find_one({"id": cid}, {"_id": 0, "name": 1})) if cid else None
    payload = build_payload(rec, context_name=(ctx or {}).get("name") or "Context")
    return {"notes": chair_notes_dict(payload)}

