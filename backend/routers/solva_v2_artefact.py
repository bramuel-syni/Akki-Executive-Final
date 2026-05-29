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
