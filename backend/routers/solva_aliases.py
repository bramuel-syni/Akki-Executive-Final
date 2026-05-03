"""Phase 13.1 — `/api/solve/*` → `/api/solva/*` legacy aliases.

Phase 13.1 renamed the Solve product module to Solva. The canonical API
prefix is now `/api/solva/...`. Existing integrations, bookmarks, and
test fixtures that still hit `/api/solve/...` are 308-redirected here so
nothing breaks during transition. Plan to retire these aliases in
Phase 14 (three sessions out, per ROADMAP.md).

308 (Permanent Redirect) is the right semantic: it preserves method and
body across the redirect, so POST + JSON requests replay correctly on
the new URL. `requests`, `axios`, and `curl -L` all honour 308 by
default (since requests 2.18+, axios 0.21+, curl 7.39+).

Why a thin proxy router rather than re-mounting `solva_engine`/`solva`
on a second prefix:
  - 308 redirect is observable on the wire — operators can see the
    legacy path being used in logs, which lets us decide when it is
    safe to retire the alias.
  - We do NOT want to silently double-mount the same handlers, because
    that would obscure migration progress and double the OpenAPI surface.
"""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

router = APIRouter(prefix="/api/solve", tags=["solva-legacy-alias"])


@router.api_route(
    "/{rest_of_path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    include_in_schema=False,
)
async def _legacy_solve_alias(rest_of_path: str, request: Request):
    """Redirect every legacy /api/solve/* call to /api/solva/* with 308."""
    target = f"/api/solva/{rest_of_path}" if rest_of_path else "/api/solva"
    if request.url.query:
        target = f"{target}?{request.url.query}"
    return RedirectResponse(url=target, status_code=308)
