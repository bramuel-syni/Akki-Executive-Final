"""Deep-tier quota inspection endpoint.

Lets the frontend check today's remaining deep-tier budget per surface so it
can render an accurate "X of N remaining today" hint next to deep-mode
toggles. Read-only — increments only happen via call_llm_with_tier on actual
generation.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query

from core import get_current_account
from llm_tier_quota import peek

router = APIRouter(prefix="/api/llm", tags=["llm"])


@router.get("/quota")
async def quota(
    surface: Optional[str] = Query(None),
    account: Dict[str, Any] = Depends(get_current_account),
):
    """Return today's deep-tier usage for a surface (or all surfaces)."""
    return await peek(account["id"], surface)
