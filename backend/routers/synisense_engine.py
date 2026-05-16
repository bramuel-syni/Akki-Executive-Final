"""FastAPI router — Synisense Engine (Phase A + Phase F).

Exposes:
- POST /api/v1/engine/signals/query
- POST /api/v1/engine/subscriptions   (stub returns pending)
- GET  /api/v1/engine/signal_types
- POST /api/v1/engine/admin/reseed   (DEV-only)
- POST /api/v1/engine/admin/derive   (Phase F — derive REAL signals
  for the calling tenant. Available to any authenticated account
  for their own tenant; superadmins may target other tenants via
  `?tenant_id={id}`.)

All endpoints scope on the authenticated `account_id` as `tenant_id`.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from core import get_current_account
from services.synisense.config import is_production
from services.synisense.engine import (
    signal_derivation, signal_query, signal_seeder, signal_types, subscription,
)
from services.synisense.models import (
    ErrorEnvelope, SignalQueryRequest, SignalQueryResponse,
    SignalTypeCatalogue, SubscriptionRequest, SubscriptionResponse,
)
from services.synisense.shield import tenant_entities

router = APIRouter(prefix="/api/v1/engine", tags=["synisense-engine"])


@router.post(
    "/signals/query",
    response_model=SignalQueryResponse,
    summary="Paginated signal retrieval. Tenant-scoped.",
)
async def query_signals(
    body: SignalQueryRequest,
    current: Dict[str, Any] = Depends(get_current_account),
) -> Any:
    # Enforce tenant_id := account_id (Phase A binding).
    if body.tenant_id != current["id"]:
        raise HTTPException(
            status_code=401,
            detail=f"tenant_id '{body.tenant_id}' does not match account_id '{current['id']}'.",
        )
    return await signal_query.query(
        tenant_id=body.tenant_id,
        filter_=body.filter, pagination=body.pagination,
    )


@router.post(
    "/subscriptions",
    response_model=SubscriptionResponse,
    summary="Subscription stub — Phase F will wire real delivery.",
)
async def create_subscription(
    body: SubscriptionRequest,
    current: Dict[str, Any] = Depends(get_current_account),
) -> Any:
    if body.tenant_id != current["id"]:
        raise HTTPException(
            status_code=401,
            detail=f"tenant_id '{body.tenant_id}' does not match account_id '{current['id']}'.",
        )
    return await subscription.create(body, tenant_id=body.tenant_id)


@router.get(
    "/signal_types",
    response_model=SignalTypeCatalogue,
    summary="Canonical signal-type catalogue. Public (auth-required, not tenant-scoped).",
)
async def get_signal_types(
    _: Dict[str, Any] = Depends(get_current_account),
) -> Any:
    return SignalTypeCatalogue(signal_types=signal_types.catalogue())


@router.post(
    "/admin/reseed",
    responses={
        403: {"model": ErrorEnvelope, "description": "Disabled in production"},
    },
    summary="DEV-only — reseed signals + tenant entities for the authenticated account.",
)
async def reseed(
    current: Dict[str, Any] = Depends(get_current_account),
) -> Any:
    if is_production():
        raise HTTPException(
            status_code=403,
            detail="admin/reseed is disabled in production",
        )
    tenant_id = current["id"]
    signal_counts = await signal_seeder.seed_for_tenant(tenant_id)
    entity_counts = await tenant_entities.harvest(tenant_id)
    return {
        "tenant_id": tenant_id,
        "signals_seeded": signal_counts,
        "tenant_entities_harvested": entity_counts,
    }


@router.post(
    "/admin/derive",
    summary="Phase F — run REAL signal derivation for the authenticated tenant.",
)
async def derive(
    current: Dict[str, Any] = Depends(get_current_account),
    target_tenant_id: Optional[str] = Query(default=None, alias="tenant_id"),
) -> Any:
    """Runs all 6 derivation rules against the caller's Mongo data and
    persists `derived_from_*` signals. If derivation produces zero
    signals, gracefully falls back to the Phase A seeder.

    Superadmins MAY pass `?tenant_id=…` to derive for another tenant
    (useful for bank-QA reproducing customer-side traces). Non-admins
    always target their own `account_id`.
    """
    tenant_id = current["id"]
    if target_tenant_id and target_tenant_id != current["id"]:
        if (current.get("role") or "").lower() not in {"superadmin", "owner"}:
            raise HTTPException(
                status_code=403,
                detail="Only superadmins may derive for other tenants.",
            )
        tenant_id = target_tenant_id

    result = await signal_derivation.derive_or_seed_for_tenant(tenant_id)
    return {
        "tenant_id": tenant_id,
        "derived": result["derived"],
        "fallback_used": result["fallback_used"],
        "seeded": result["seeded"],
        "total_derived": sum(result["derived"].values()),
    }
