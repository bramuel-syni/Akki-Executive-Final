"""Health · Shield readiness probe.

H2.5 follow-up Part B (2026-05-24). Lightweight unauthenticated
endpoint at ``GET /api/healthz/shield`` that lets ops + load balancers
verify Shield's spaCy NER pipeline is ready WITHOUT re-running the
load on every hit. Reads the cached warmup snapshot set by
``services.synisense.shield.deidentifier.warmup_or_die()`` at FastAPI
startup.

Response shape::

    {
      "ready": true | false,
      "model_loaded": true | false,
      "model_name": "en_core_web_sm" | "en_core_web_trf" | null,
      "model_version": "3.8.0" | null,
      "last_warmup_at": "<iso 8601>" | null,
      "last_warmup_duration_ms": 234 | null,
      "last_warmup_error": null | "<class>: <msg>"
    }

When ``ready=false`` the endpoint returns **HTTP 503** so external
probes treat it as unhealthy. Same shape on 503 — body always
carries the diagnostic state.
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from services.synisense.shield import deidentifier as _shield_deid

router = APIRouter(prefix="/api/healthz", tags=["healthz"])


@router.get("/shield")
async def healthz_shield():
    """Read-only Shield readiness snapshot. No auth — designed for
    Kubernetes ``readinessProbe`` / external monitors.

    Returns the warmup snapshot from
    ``deidentifier.get_warmup_state()``. If ``ready=false``, HTTP
    code is 503 so probes mark the pod unhealthy; otherwise 200.
    """
    state = _shield_deid.get_warmup_state()
    status = 200 if state.get("ready") else 503
    return JSONResponse(status_code=status, content=state)
