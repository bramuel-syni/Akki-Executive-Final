"""Synisense router — Phase 12.1 wiring.

Two public endpoints:

  GET  /api/synisense/status  — real status: pool, model, key version,
                                insecure-fallback flag, last-run ts,
                                ring-buffer perf summary.
  POST /api/synisense/dryrun  — execute the pipeline end-to-end WITHOUT
                                persisting. Returns the locked data
                                contract.

One admin endpoint (superadmin-gated):

  GET  /api/admin/synisense/perf — p50/p95/p99 over the in-memory ring.

The surface-wiring (chat, ingest, Studio, Solva, public-read) lands in
Phase 12.2. That phase replaces TrustPanel's `mock_scaffolding_note`,
the chat redaction hook, the Studio first-save PreviewDrawer, and the
public-read `synisense_version` assertion. Until then, this file only
publishes the engine.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from core import db, get_current_account
from services.synisense import (
    dryrun as pipeline_dryrun,
    get_perf_snapshot,
    get_status_snapshot,
)

router = APIRouter(prefix="/api")


CATEGORIES = [
    {"id": "email", "label": "Email addresses",
     "description": "RFC-5322 style tokens — e.g. director@company.com",
     "example": "alice.mwalo@firstnationalbank.co.ke"},
    {"id": "phone", "label": "Phone numbers",
     "description": "International and national formats.",
     "example": "+44 20 7123 4567"},
    {"id": "person", "label": "Personal names",
     "description": "Stock Presidio NER plus context-seeded chair/board names.",
     "example": "Elena Chowdhury"},
    {"id": "deal_codename", "label": "Deal codenames",
     "description": "Pascal-cased names after 'Project' or 'Operation'.",
     "example": "Project Falcon"},
    {"id": "executive_title", "label": "Executive titles",
     "description": "C-suite titles, NED, chair, SID, company secretary.",
     "example": "Chief Financial Officer"},
    {"id": "financial_figure_large", "label": "Large financial figures",
     "description": "£/$/€ amounts ≥ seven figures.",
     "example": "£42,500,000"},
    {"id": "iban", "label": "IBAN bank accounts",
     "description": "International bank account numbers.",
     "example": "GB33BUKB20201555555555"},
    {"id": "credit_card", "label": "Credit card numbers",
     "description": "Any 13-19 digit sequence in card shape.",
     "example": "4111 1111 1111 1111"},
    {"id": "us_ssn", "label": "US SSNs", "description": "", "example": "123-45-6789"},
    {"id": "uk_nhs", "label": "UK NHS numbers", "description": "", "example": "485 777 3456"},
    {"id": "ip_address", "label": "IP addresses", "description": "", "example": "192.168.1.10"},
    {"id": "url", "label": "URLs", "description": "Any http(s):// link.",
     "example": "https://internal.boards.company.com/audit-pack-Q4.pdf"},
    {"id": "date_time_exact", "label": "Exact dates", "description": "ISO-8601 date strings.",
     "example": "2026-05-02"},
]


# ---------------------------------------------------------------------------
# GET /api/synisense/status
# ---------------------------------------------------------------------------
@router.get("/synisense/status")
async def get_synisense_status(
    current: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    snap = get_status_snapshot()
    last_run = await db.synisense_runs.find_one(
        {}, sort=[("ts", -1)],
        projection={"_id": 0, "ts": 1, "surface": 1, "stats.elapsed_ms": 1},
    )
    perf = get_perf_snapshot()
    return {
        **snap,
        "last_run": last_run,
        "perf_snapshot": {
            "count": perf["count"], "p50": perf["p50"],
            "p95": perf["p95"], "p99": perf["p99"],
        },
        "categories": CATEGORIES,
    }


# ---------------------------------------------------------------------------
# POST /api/synisense/dryrun
# ---------------------------------------------------------------------------
class DryrunIn(BaseModel):
    text: str = Field(..., max_length=20000)
    context_id: Optional[str] = None
    surface: str = Field(default="chat")
    mode: str = Field(default="redact")
    tier_limit: Optional[int] = None
    context_people: Optional[List[str]] = None


@router.post("/synisense/dryrun")
async def synisense_dryrun(
    body: DryrunIn,
    current: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    try:
        out = await pipeline_dryrun(
            body.text,
            context_id=body.context_id or "",
            surface=body.surface,
            mode=body.mode,
            tier_limit=body.tier_limit,
            context_people=body.context_people,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return out


# ---------------------------------------------------------------------------
# GET /api/admin/synisense/perf  (superadmin only)
# ---------------------------------------------------------------------------
async def _require_superadmin(
    current: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    if not current.get("is_superadmin"):
        raise HTTPException(status_code=403, detail="Superadmin only.")
    return current


@router.get("/admin/synisense/perf")
async def get_admin_synisense_perf(
    _admin: Dict[str, Any] = Depends(_require_superadmin),
) -> Dict[str, Any]:
    return {
        "perf": get_perf_snapshot(),
        "status": get_status_snapshot(),
        "as_of": datetime.now(timezone.utc).isoformat(),
    }
