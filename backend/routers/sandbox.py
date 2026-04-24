"""Sandbox — pre-auth evaluation entry for AKKI.

A prospect hits /sandbox, answers 4 questions, we return a session_id. The
frontend drives a 60-second streaming narrative using the server-provided
stages, and polls /status until ready. When generation completes we:
  1. create a disposable account (sandbox+<id>@akki.local),
  2. create a `type: sandbox` context with `sandbox_metadata`,
  3. seed documents + signals + briefings parameterised for their answers,
  4. return an access JWT so the sandbox user is auto-logged-in.

No sign-up required up front. Sandbox is hard-deleted on day 22.
"""
from __future__ import annotations

import asyncio
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field

from core import (
    db, now as _now, iso as _iso, write_audit,
    create_access_token, create_refresh_token, hash_password,
)
from sandbox_service import (
    pick_template, build_seed_payload, resolve_stage_texts,
    sandbox_expiry_defaults, REGION_PROFILES,
)

logger = logging.getLogger("akki.sandbox")

router = APIRouter(prefix="/api/sandbox")

SandboxSector = Literal[
    "financial_services", "saas", "logistics", "healthcare",
    "manufacturing", "retail", "real_estate", "other",
]
SandboxRole = Literal["ned", "executive", "both"]
SandboxRegion = Literal[
    "east_africa", "west_africa", "southern_africa", "north_africa",
    "europe", "north_america", "middle_east", "asia_pacific",
]


# -----------------------------------------------------------------------------
# Schemas
# -----------------------------------------------------------------------------
class SandboxIntakeIn(BaseModel):
    company_name: str = Field(min_length=1, max_length=120)
    sector: SandboxSector
    role: SandboxRole
    region: SandboxRegion
    prospect_email: Optional[EmailStr] = None  # optional — captured later if missing


class SandboxFinaliseIn(BaseModel):
    session_id: str


# -----------------------------------------------------------------------------
# Session store (in-memory for Phase 1 — fine because sessions live ≤ 60s)
# -----------------------------------------------------------------------------
_sessions: Dict[str, Dict[str, Any]] = {}


# -----------------------------------------------------------------------------
# POST /generate — kick off a session (returns streaming stages + session_id)
# -----------------------------------------------------------------------------
@router.post("/generate")
async def start_generation(body: SandboxIntakeIn):
    session_id = secrets.token_urlsafe(12)
    stages = resolve_stage_texts(body.model_dump())
    _sessions[session_id] = {
        "session_id": session_id,
        "intake": body.model_dump(),
        "stages": stages,
        "started_at": _iso(_now()),
        "status": "generating",
        "context_id": None,
        "account_id": None,
        "access_token": None,
    }
    # Kick off the real seed job in the background — by the time the frontend
    # finishes its ~55-60s stage narration, data is ready.
    asyncio.create_task(_seed_sandbox(session_id))

    return {
        "session_id": session_id,
        "stages": stages,
        "total_ms": stages[-1]["max_ms"] if stages else 60000,
    }


# -----------------------------------------------------------------------------
# GET /generate/{session_id}/status — progress poll
# -----------------------------------------------------------------------------
@router.get("/generate/{session_id}/status")
async def generation_status(session_id: str):
    s = _sessions.get(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Sandbox session not found or expired")
    payload = {
        "session_id": session_id,
        "status": s["status"],
        "ready": s["status"] == "ready",
        "stages": s["stages"],
        "context_id": s.get("context_id"),
        "access_token": s.get("access_token") if s["status"] == "ready" else None,
        "error": s.get("error"),
    }
    # Schedule session expiry 90s after we first report ready — keeps the
    # in-memory dict bounded under heavy sandbox traffic.
    if s["status"] == "ready" and "expire_task" not in s:
        async def _expire():
            await asyncio.sleep(90)
            _sessions.pop(session_id, None)
        s["expire_task"] = asyncio.create_task(_expire())
    return payload


# -----------------------------------------------------------------------------
# Internal — seed the sandbox in the background
# -----------------------------------------------------------------------------
async def _seed_sandbox(session_id: str):
    s = _sessions.get(session_id)
    if not s:
        return
    try:
        intake = s["intake"]
        company_name = intake["company_name"].strip()
        sector = intake["sector"]
        region = intake["region"]
        role = intake["role"]

        # 1. Create the disposable sandbox account
        account_id = str(uuid.uuid4())
        disposable_email = f"sandbox+{session_id}@akki.local"
        now_dt = _now()
        expires_at, read_only_until, hard_delete_at = sandbox_expiry_defaults()
        # Short pseudo-random password — never displayed, never logged, JWT is the only access path.
        throwaway_password = secrets.token_urlsafe(16)

        account_doc = {
            "id": account_id,
            "email": disposable_email,
            "name": f"Sandbox visitor ({company_name})",
            "declared_role": "dual" if role == "both" else ("ned" if role == "ned" else "executive"),
            "password_hash": hash_password(throwaway_password),
            "mfa_enabled": False,
            "mfa_secret": None,
            "default_context_id": None,
            "is_sandbox": True,
            "sandbox_session_id": session_id,
            "created_at": _iso(now_dt),
        }
        await db.accounts.insert_one(account_doc)

        # 2. Create the sandbox context
        context_id = str(uuid.uuid4())
        region_profile = REGION_PROFILES.get(region) or REGION_PROFILES["east_africa"]
        ctx_doc = {
            "id": context_id,
            "name": company_name,
            "type": "sandbox",
            "industry": intake.get("sector"),
            "jurisdiction": region_profile.get("primary_country"),
            "sector": pick_template(sector)["sector_hint"],
            "sponsoring_org_id": None,
            "owner_account_id": account_id,
            "status": "active",
            "progress_state": {
                "onboarding_step": 7,
                "onboarding_completed": True,
                "context_object_version": 1,
            },
            "committees": [
                {**c, "id": f"committee-{uuid.uuid4().hex[:6]}"}
                for c in pick_template(sector)["committees"]
            ],
            "sandbox_metadata": {
                "template_id": pick_template(sector)["id"],
                "intake_inputs": intake,
                "prospect_email": intake.get("prospect_email"),
                "generated_at": _iso(now_dt),
                "expires_at": _iso(expires_at),
                "read_only_until": _iso(read_only_until),
                "hard_delete_at": _iso(hard_delete_at),
            },
            "created_at": _iso(now_dt),
        }
        await db.contexts.insert_one(ctx_doc)

        await db.memberships.insert_one({
            "id": str(uuid.uuid4()),
            "account_id": account_id,
            "context_id": context_id,
            "role": "ned" if role == "ned" else "executive",
            "sub_role": "admin",
            "provisioning": "sandbox",
            "data_ownership": "sandbox",
            "status": "active",
            "created_at": _iso(now_dt),
        })

        await db.accounts.update_one(
            {"id": account_id}, {"$set": {"default_context_id": context_id}}
        )

        # 3. Seed a context_object so the onboarded-state UI renders fully
        co_doc = {
            "id": str(uuid.uuid4()),
            "context_id": context_id,
            "version": 1,
            "industry": sector,
            "sector": pick_template(sector)["sector_hint"],
            "jurisdiction": region_profile.get("primary_country"),
            "role": "ned" if role == "ned" else "executive",
            "answers": {
                "q1_role": {
                    "ned": "Independent Director",
                    "executive": "CEO / Operating Executive",
                    "both": "Dual-role leader",
                }.get(role, "Executive"),
                "q3_focus_areas": f"Key {pick_template(sector)['sector_hint']} themes — risk, capital, strategy",
                "q6_lens_preference": "Generalist · board-chair lens",
                "q7_analytical_style": "Reads the pack; wants sharp questions for the chair.",
            },
            "step": 7,
            "completed": True,
            "created_by": account_id,
            "created_at": _iso(now_dt),
            "updated_at": _iso(now_dt),
        }
        await db.context_objects.insert_one(co_doc)

        # 4. Seed documents + signals + briefings
        template = pick_template(sector)
        seeds = build_seed_payload(
            context_id=context_id, template=template, intake=intake,
            owner_account_id=account_id,
        )
        if seeds["documents"]:
            await db.documents.insert_many(seeds["documents"])
        if seeds["signals"]:
            await db.signals.insert_many(seeds["signals"])
        if seeds["briefings"]:
            await db.briefings.insert_many(seeds["briefings"])

        # 5. Mint the access + refresh tokens so frontend can log the prospect in
        access = create_access_token(account_id, disposable_email)
        refresh = create_refresh_token(account_id)

        # 6. Mark the session ready
        s["status"] = "ready"
        s["context_id"] = context_id
        s["account_id"] = account_id
        s["access_token"] = access
        s["refresh_token"] = refresh

        await write_audit(
            context_id, account_id, "sandbox.generated", "sandbox", session_id,
            {"template_id": template["id"], "sector": sector, "region": region, "role": role},
        )
        logger.info(f"[sandbox] session={session_id} context={context_id} ready "
                    f"(docs={len(seeds['documents'])}, signals={len(seeds['signals'])}, "
                    f"briefings={len(seeds['briefings'])})")

    except Exception as e:
        logger.exception(f"[sandbox] session={session_id} seed failed: {e}")
        # Roll back any half-seeded artefacts so orphans don't linger until
        # the daily sweep. Tolerant: each step is independently try/ignored.
        ctx_id = s.get("context_id")
        acc_id = s.get("account_id")
        try:
            if ctx_id:
                await db.documents.delete_many({"context_id": ctx_id})
                await db.signals.delete_many({"context_id": ctx_id})
                await db.briefings.delete_many({"context_id": ctx_id})
                await db.context_objects.delete_many({"context_id": ctx_id})
                await db.memberships.delete_many({"context_id": ctx_id})
                await db.contexts.delete_one({"id": ctx_id})
            if acc_id:
                await db.accounts.delete_one({"id": acc_id, "is_sandbox": True})
        except Exception:
            logger.exception(f"[sandbox] session={session_id} rollback also failed")
        s["status"] = "error"
        s["error"] = str(e)


# -----------------------------------------------------------------------------
# GET /templates — public endpoint listing available sector templates (meta only)
# -----------------------------------------------------------------------------
@router.get("/templates")
async def list_templates():
    """Surface which sectors have polished templates vs fall back to generic."""
    from sandbox_service import SECTOR_TO_TEMPLATE, TEMPLATES
    return [
        {
            "sector": s,
            "template_id": tid,
            "label": TEMPLATES[tid]["label"],
            "is_polished": tid != "generic_diversified",
        }
        for s, tid in SECTOR_TO_TEMPLATE.items()
    ]


# -----------------------------------------------------------------------------
# Cleanup helper — called by a cron elsewhere, exposed for testing
# -----------------------------------------------------------------------------
@router.post("/cleanup/expired")
async def cleanup_expired_sandboxes():
    """Admin-ish endpoint — sweep contexts past hard_delete_at. No auth for now
    since there's no real PII in sandboxes and this is trivial to rate-limit."""
    now_iso_str = _iso(_now())
    cursor = db.contexts.find(
        {
            "type": "sandbox",
            "sandbox_metadata.hard_delete_at": {"$lt": now_iso_str},
            "status": {"$ne": "deleted"},
        },
        {"_id": 0, "id": 1, "owner_account_id": 1},
    )
    swept = 0
    async for ctx in cursor:
        cid = ctx["id"]
        await db.documents.delete_many({"context_id": cid})
        await db.signals.delete_many({"context_id": cid})
        await db.briefings.delete_many({"context_id": cid})
        await db.context_objects.delete_many({"context_id": cid})
        await db.memberships.delete_many({"context_id": cid})
        await db.contexts.update_one({"id": cid}, {"$set": {"status": "deleted"}})
        if ctx.get("owner_account_id"):
            await db.accounts.delete_one({"id": ctx["owner_account_id"], "is_sandbox": True})
        swept += 1
    return {"swept": swept}
