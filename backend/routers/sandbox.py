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

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, EmailStr, Field

from core import (
    db, now as _now, iso as _iso, write_audit,
    get_current_account,
    create_access_token, create_refresh_token, hash_password,
    set_auth_cookies, sanitize_account, sanitize_context,
)
from fastapi import Depends, Response
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
    objective: Optional[str] = Field(default=None, max_length=400)
    other_sector_name: Optional[str] = Field(default=None, max_length=80)
    other_sector_description: Optional[str] = Field(default=None, max_length=400)
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


class SandboxConvertIn(BaseModel):
    """Payload for converting a sandbox session into a real account.

    Caller is the sandbox user (authenticated via their sandbox JWT). We
    rewrite the disposable account's email/password/name, strip `is_sandbox`,
    flip the context `type` off 'sandbox', and drop the expiry fields.
    """
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=120)
    keep_sandbox: bool = True


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
                "objective": (intake.get("objective") or "").strip() or None,
                "other_sector_name": (intake.get("other_sector_name") or "").strip() or None,
                "other_sector_description": (intake.get("other_sector_description") or "").strip() or None,
                "prospect_email": intake.get("prospect_email"),
                "tutorial_dismissed": False,
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
async def cleanup_expired_sandboxes(
    x_cron_secret: Optional[str] = Header(default=None, alias="X-Cron-Secret"),
):
    """Sweep sandboxes past `hard_delete_at`. Gated by an `X-Cron-Secret`
    header that matches the `AKKI_CRON_SECRET` env var (shared with the
    scheduled-job runner). Anonymous callers are rejected.

    If `AKKI_CRON_SECRET` is unset in the environment we fail closed — the
    endpoint returns 503 so a misconfigured deploy can't be abused."""
    import os as _os
    expected = _os.environ.get("AKKI_CRON_SECRET")
    if not expected:
        raise HTTPException(status_code=503, detail="Cleanup disabled — AKKI_CRON_SECRET not configured.")
    if not x_cron_secret or x_cron_secret != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Cron-Secret header.")
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


class SandboxEmailCaptureIn(BaseModel):
    """Optional mid-exploration email drop — we store it on the context so a
    later drip-email ("Pick up where you left off") can find the session."""
    email: EmailStr


@router.post("/contexts/{context_id}/capture-email")
async def capture_email(
    context_id: str,
    body: SandboxEmailCaptureIn,
    current: Dict[str, Any] = Depends(get_current_account),
):
    ctx = await db.contexts.find_one(
        {"id": context_id, "owner_account_id": current["id"], "type": "sandbox"},
        {"_id": 0},
    )
    if not ctx:
        raise HTTPException(status_code=404, detail="Sandbox context not found")
    await db.contexts.update_one(
        {"id": context_id},
        {"$set": {
            "sandbox_metadata.prospect_email": body.email.lower().strip(),
            "sandbox_metadata.email_captured_at": _iso(_now()),
        }},
    )
    await write_audit(context_id, current["id"], "sandbox.email_captured", "sandbox", context_id,
                      {"email": body.email.lower().strip()})
    # Schedule a pickup-where-you-left-off marker. Actual email delivery ships
    # with §6 Email-in; for now we log the intent and persist the trigger row.
    await db.sandbox_pickups.insert_one({
        "id": str(uuid.uuid4()),
        "context_id": context_id,
        "account_id": current["id"],
        "email": body.email.lower().strip(),
        "send_after": _iso(_now() + timedelta(hours=24)),
        "status": "queued",
        "created_at": _iso(_now()),
    })
    logger.info(f"[sandbox-pickup-queued] ctx={context_id} email={body.email} "
                f"send_after=+24h")
    return {"ok": True}


# -----------------------------------------------------------------------------
# Sandbox tutorial — first-run guided card. Returns the user's stated objective,
# the seeded first briefing, and a suggested chat opener so the user has a
# guaranteed first action when they land.
# -----------------------------------------------------------------------------
@router.get("/contexts/{context_id}/tutorial")
async def sandbox_tutorial(
    context_id: str,
    current: Dict[str, Any] = Depends(get_current_account),
):
    ctx = await db.contexts.find_one(
        {"id": context_id, "owner_account_id": current["id"]},
        {"_id": 0},
    )
    if not ctx:
        raise HTTPException(status_code=404, detail="Context not found")

    # Tutorial fires for sandbox contexts AND seeded real contexts.
    meta = ctx.get("sandbox_metadata") or ctx.get("seeded_metadata") or {}
    if not meta:
        return {"context_id": context_id, "dismissed": True, "objective": None,
                "first_briefing": None, "first_signal_headline": None,
                "suggested_chat_opener": None, "steps": []}

    objective = meta.get("objective") or ""
    dismissed = bool(meta.get("tutorial_dismissed"))

    # First seeded briefing (most recent).
    brief = await db.briefings.find_one(
        {"context_id": context_id, "sandbox_artefact": True},
        {"_id": 0, "id": 1, "title": 1, "opening_paragraph": 1},
        sort=[("created_at", 1)],
    )

    # First seeded signal headline (for the suggested chat opener).
    sig = await db.signals.find_one(
        {"context_id": context_id, "sandbox_artefact": True},
        {"_id": 0, "headline": 1},
        sort=[("created_at", 1)],
    )

    # Suggested opener — anchored to objective when available, else to the
    # most cutting first signal.
    if objective:
        opener = f"What's the sharpest question I should ask given my objective: \"{objective[:160]}\"?"
    elif sig:
        opener = f"Walk me through this: {sig['headline']}"
    else:
        opener = "What are the highlights of the latest board pack?"

    return {
        "context_id": context_id,
        "dismissed": dismissed,
        "objective": objective or None,
        "first_briefing": {
            "id": brief["id"], "title": brief["title"],
            "opening_paragraph": brief["opening_paragraph"],
        } if brief else None,
        "first_signal_headline": sig["headline"] if sig else None,
        "suggested_chat_opener": opener,
        "steps": [
            {"key": "read_brief", "title": "Read your first briefing",
             "blurb": "AKKI has already drafted what to bring to the next committee.",
             "cta": "Open the brief", "href": "/app/briefings"},
            {"key": "ask_chat", "title": "Ask AKKI one sharp question",
             "blurb": "Chat is your primary surface — try the suggested opener.",
             "cta": "Open Chat", "href": "/app/chat"},
            {"key": "scan_signals", "title": "Scan the signals on your radar",
             "blurb": "Risks, opportunities, and gaps AKKI surfaced from the pack.",
             "cta": "Open Signals", "href": "/app/highlights"},
        ],
    }


class TutorialDismissIn(BaseModel):
    dismissed: bool = True


@router.post("/contexts/{context_id}/tutorial/dismiss")
async def dismiss_tutorial(
    context_id: str,
    body: TutorialDismissIn,
    current: Dict[str, Any] = Depends(get_current_account),
):
    ctx = await db.contexts.find_one(
        {"id": context_id, "owner_account_id": current["id"]},
        {"_id": 0, "id": 1, "type": 1},
    )
    if not ctx:
        raise HTTPException(status_code=404, detail="Context not found")
    # Stamp the right metadata branch depending on context flavour.
    set_field = "sandbox_metadata.tutorial_dismissed" if ctx.get("type") == "sandbox" \
        else "seeded_metadata.tutorial_dismissed"
    await db.contexts.update_one(
        {"id": context_id},
        {"$set": {set_field: bool(body.dismissed)}},
    )
    return {"ok": True, "dismissed": bool(body.dismissed)}


# -----------------------------------------------------------------------------
# Objective-delivery follow-up — surfaces ~24h after the sandbox/seeded
# context was generated. Asks the user "Did AKKI deliver on your objective?"
# and stores the answer as a per-sector conversion KPI (the doc's exact ask:
# "we use this to measure later whether AKKI delivered on it").
# -----------------------------------------------------------------------------
class ObjectiveCheckAnswerIn(BaseModel):
    answer: str = Field(pattern=r"^(yes|partial|no|skip)$")
    note: Optional[str] = Field(default=None, max_length=400)


def _meta_branch(ctx: Dict[str, Any]) -> tuple[Dict[str, Any], str]:
    """Return (metadata_dict, dotted_field_prefix) for the right metadata
    bucket (sandbox vs seeded)."""
    if ctx.get("type") == "sandbox":
        return ctx.get("sandbox_metadata") or {}, "sandbox_metadata"
    return ctx.get("seeded_metadata") or {}, "seeded_metadata"


@router.get("/contexts/{context_id}/objective-check")
async def get_objective_check(
    context_id: str,
    current: Dict[str, Any] = Depends(get_current_account),
):
    """Frontend hits this on home load. Returns whether the follow-up should
    be shown (eligible=True only when ≥24h after generation, an objective
    was captured, and the user hasn't already answered or dismissed)."""
    ctx = await db.contexts.find_one(
        {"id": context_id, "owner_account_id": current["id"]},
        {"_id": 0},
    )
    if not ctx:
        raise HTTPException(status_code=404, detail="Context not found")

    meta, _ = _meta_branch(ctx)
    if not meta:
        return {"eligible": False}

    objective = (meta.get("objective") or "").strip()
    if not objective:
        return {"eligible": False}

    check = meta.get("objective_check") or {}
    if check.get("answered_at") or check.get("dismissed"):
        return {"eligible": False, "answered": bool(check.get("answered_at")),
                "answer": check.get("answer")}

    generated_at = meta.get("generated_at")
    eligible = False
    if generated_at:
        try:
            gdt = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
            eligible = (_now() - gdt) >= timedelta(hours=24)
        except (ValueError, TypeError):
            eligible = False

    return {
        "eligible": eligible,
        "objective": objective,
        "generated_at": generated_at,
        "answered": False,
    }


@router.post("/contexts/{context_id}/objective-check")
async def answer_objective_check(
    context_id: str,
    body: ObjectiveCheckAnswerIn,
    current: Dict[str, Any] = Depends(get_current_account),
):
    """Persist the user's answer. `skip` flips dismissed=True so we never
    re-show; yes/partial/no record the answer + optional free-text note."""
    ctx = await db.contexts.find_one(
        {"id": context_id, "owner_account_id": current["id"]},
        {"_id": 0},
    )
    if not ctx:
        raise HTTPException(status_code=404, detail="Context not found")

    meta, prefix = _meta_branch(ctx)
    if not meta or not (meta.get("objective") or "").strip():
        raise HTTPException(status_code=400, detail="No objective captured for this context.")

    now_iso = _iso(_now())
    if body.answer == "skip":
        await db.contexts.update_one(
            {"id": context_id},
            {"$set": {f"{prefix}.objective_check": {
                "dismissed": True, "dismissed_at": now_iso,
            }}},
        )
        return {"ok": True, "dismissed": True}

    payload = {
        "answered_at": now_iso,
        "answer": body.answer,
        "note": (body.note or "").strip() or None,
    }
    await db.contexts.update_one(
        {"id": context_id},
        {"$set": {f"{prefix}.objective_check": payload}},
    )
    await write_audit(
        context_id, current["id"], "sandbox.objective_answered", "context", context_id,
        {"answer": body.answer,
         "sector": (meta.get("intake_inputs") or {}).get("sector")},
    )
    return {"ok": True, **payload}




@router.post("/convert")
async def convert_sandbox(
    body: SandboxConvertIn,
    response: Response,
    current: Dict[str, Any] = Depends(get_current_account),
):
    """Migrate the caller's sandbox account into a real, persistent account.

    After conversion:
      · Disposable email is rewritten to the real one + password updated.
      · The `is_sandbox` flag and sandbox_session_id are stripped from account.
      · Each of the user's sandbox-typed contexts is flipped to a real type
        (ned_personal / executive_personal based on the membership role),
        `sandbox_metadata.converted_at` is stamped, and expires_at /
        read_only_until / hard_delete_at are cleared so the sweeper skips it.
    """
    if not current.get("is_sandbox"):
        raise HTTPException(status_code=400, detail="Not a sandbox account — nothing to convert.")

    new_email = body.email.lower().strip()
    # Email uniqueness — bail cleanly if it's already in use by a different account
    existing = await db.accounts.find_one({"email": new_email, "id": {"$ne": current["id"]}}, {"_id": 0, "id": 1})
    if existing:
        raise HTTPException(status_code=409, detail="That email is already registered. Sign in instead.")

    # 1. Rewrite the account
    await db.accounts.update_one(
        {"id": current["id"]},
        {
            "$set": {
                "email": new_email,
                "name": body.name.strip(),
                "password_hash": hash_password(body.password),
            },
            "$unset": {"is_sandbox": "", "sandbox_session_id": ""},
        },
    )

    # 2. Flip sandbox contexts to real ones (only if keep_sandbox)
    my_ctx_ids: List[str] = []
    async for m in db.memberships.find(
        {"account_id": current["id"], "status": "active"},
        {"_id": 0, "context_id": 1, "role": 1},
    ):
        my_ctx_ids.append(m["context_id"])
        real_type = "ned_personal" if m.get("role") == "ned" else "executive_personal"
        if body.keep_sandbox:
            await db.contexts.update_one(
                {"id": m["context_id"], "type": "sandbox"},
                {
                    "$set": {
                        "type": real_type,
                        "sandbox_metadata.converted_at": _iso(_now()),
                    },
                    "$unset": {
                        "sandbox_metadata.expires_at": "",
                        "sandbox_metadata.read_only_until": "",
                        "sandbox_metadata.hard_delete_at": "",
                    },
                },
            )
        else:
            # Discard the explored sandbox entirely on conversion
            await db.documents.delete_many({"context_id": m["context_id"]})
            await db.signals.delete_many({"context_id": m["context_id"]})
            await db.briefings.delete_many({"context_id": m["context_id"]})
            await db.context_objects.delete_many({"context_id": m["context_id"]})
            await db.memberships.delete_many({"context_id": m["context_id"]})
            await db.contexts.delete_one({"id": m["context_id"], "type": "sandbox"})

    # 3. Rotate tokens + set real cookies so the user is cleanly logged in
    access = create_access_token(current["id"], new_email)
    refresh = create_refresh_token(current["id"])
    set_auth_cookies(response, access, refresh)

    await write_audit(
        None, current["id"], "sandbox.converted", "account", current["id"],
        {"email": new_email, "kept_sandbox": body.keep_sandbox,
         "contexts_migrated": len(my_ctx_ids)},
    )
    refreshed_acc = await db.accounts.find_one({"id": current["id"]}, {"_id": 0})
    return {
        "account": sanitize_account(refreshed_acc),
        "contexts_kept": len(my_ctx_ids) if body.keep_sandbox else 0,
        "access_token": access,
    }



# -----------------------------------------------------------------------------
# Authenticated "Add company" — same 5-question journey as the public sandbox,
# but creates a REAL context (not type=sandbox) owned by the current account.
# Reuses the same template seeding so the user gets the populated experience
# from second one. The doc was explicit: there is no good reason for the
# Sandbox onboarding flow and Add-company flow to be different.
# -----------------------------------------------------------------------------
class SeededContextIn(BaseModel):
    company_name: str = Field(min_length=1, max_length=120)
    sector: SandboxSector
    role: SandboxRole
    region: SandboxRegion
    objective: Optional[str] = Field(default=None, max_length=400)
    other_sector_name: Optional[str] = Field(default=None, max_length=80)
    other_sector_description: Optional[str] = Field(default=None, max_length=400)
    seed_data: bool = True


@router.post("/contexts/seeded")
async def create_seeded_context(
    body: SeededContextIn,
    current: Dict[str, Any] = Depends(get_current_account),
):
    """Create a real (non-sandbox) context for the authenticated user, then
    optionally seed it with the same sector-template artefacts the public
    sandbox uses. Returns the new context id so the frontend can switch into it.
    """
    intake = body.model_dump()
    company_name = intake["company_name"].strip()
    sector = intake["sector"]
    region = intake["region"]
    role = intake["role"]

    region_profile = REGION_PROFILES.get(region) or REGION_PROFILES["east_africa"]
    template = pick_template(sector)

    real_type = "ned_personal" if role == "ned" else "executive_personal"
    context_id = str(uuid.uuid4())
    now_dt = _now()

    ctx_doc = {
        "id": context_id,
        "name": company_name,
        "type": real_type,
        "industry": sector,
        "jurisdiction": region_profile.get("primary_country"),
        "sector": template["sector_hint"],
        "sponsoring_org_id": None,
        "owner_account_id": current["id"],
        "status": "active",
        "progress_state": {
            "onboarding_step": 7,
            "onboarding_completed": True,
            "context_object_version": 1,
        },
        "committees": [
            {**c, "id": f"committee-{uuid.uuid4().hex[:6]}"}
            for c in template["committees"]
        ],
        "seeded_metadata": {
            "template_id": template["id"],
            "intake_inputs": intake,
            "objective": (intake.get("objective") or "").strip() or None,
            "other_sector_name": (intake.get("other_sector_name") or "").strip() or None,
            "other_sector_description": (intake.get("other_sector_description") or "").strip() or None,
            "tutorial_dismissed": False,
            "generated_at": _iso(now_dt),
        },
        "created_at": _iso(now_dt),
    }
    await db.contexts.insert_one(ctx_doc)

    await db.memberships.insert_one({
        "id": str(uuid.uuid4()),
        "account_id": current["id"],
        "context_id": context_id,
        "role": "ned" if role == "ned" else "executive",
        "sub_role": "admin",
        "provisioning": "self_serve_seeded",
        "data_ownership": "personal",
        "status": "active",
        "created_at": _iso(now_dt),
    })

    co_doc = {
        "id": str(uuid.uuid4()),
        "context_id": context_id,
        "version": 1,
        "industry": sector,
        "sector": template["sector_hint"],
        "jurisdiction": region_profile.get("primary_country"),
        "role": "ned" if role == "ned" else "executive",
        "answers": {
            "q1_role": {
                "ned": "Independent Director",
                "executive": "CEO / Operating Executive",
                "both": "Dual-role leader",
            }.get(role, "Executive"),
            "q3_focus_areas": f"Key {template['sector_hint']} themes — risk, capital, strategy",
            "q6_lens_preference": "Generalist · board-chair lens",
            "q7_analytical_style": "Reads the pack; wants sharp questions for the chair.",
        },
        "step": 7,
        "completed": True,
        "created_by": current["id"],
        "created_at": _iso(now_dt),
        "updated_at": _iso(now_dt),
    }
    await db.context_objects.insert_one(co_doc)

    if body.seed_data:
        seeds = build_seed_payload(
            context_id=context_id, template=template, intake=intake,
            owner_account_id=current["id"],
        )
        if seeds["documents"]:
            await db.documents.insert_many(seeds["documents"])
        if seeds["signals"]:
            await db.signals.insert_many(seeds["signals"])
        if seeds["briefings"]:
            await db.briefings.insert_many(seeds["briefings"])

    await write_audit(
        context_id, current["id"], "context.seeded", "context", context_id,
        {"template_id": template["id"], "sector": sector, "region": region, "role": role,
         "seeded": bool(body.seed_data)},
    )

    new_ctx = await db.contexts.find_one({"id": context_id}, {"_id": 0})
    return {"context": sanitize_context(new_ctx) if new_ctx else None,
            "context_id": context_id}
