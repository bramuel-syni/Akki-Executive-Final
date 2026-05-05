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
async def generation_status(session_id: str, response: Response):
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
    # Iter60 follow-up — when the sandbox is ready we ALSO write the
    # access/refresh cookies on the response. This proactively replaces
    # any stale session cookie a returning visitor still had in their
    # browser, so the app heals itself before the next /api/auth/me roundtrip
    # rather than relying on Bearer-first ordering as the only safety net.
    if s["status"] == "ready" and s.get("access_token") and s.get("refresh_token"):
        try:
            set_auth_cookies(response, s["access_token"], s["refresh_token"])
        except Exception as e:  # noqa: BLE001
            logger.warning("[sandbox] failed to set auth cookies on ready response: %s", e)
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
# Sandbox sample doc — AKKI offers a synthesised "this could be your board
# pack" preview the prospect can accept with one click. Smoother first-touch
# than asking them to find and drop a real PDF.
# -----------------------------------------------------------------------------
@router.get("/contexts/{context_id}/sample-doc")
async def sandbox_sample_doc(
    context_id: str,
    current: Dict[str, Any] = Depends(get_current_account),
):
    """Return a tailored sample document the prospect can accept-upload."""
    ctx = await db.contexts.find_one(
        {"id": context_id, "owner_account_id": current["id"]},
        {"_id": 0},
    )
    if not ctx or ctx.get("type") != "sandbox":
        raise HTTPException(status_code=404, detail="Sandbox context not found")
    if (ctx.get("sandbox_metadata") or {}).get("sample_doc_accepted"):
        return {"already_accepted": True}

    meta = ctx.get("sandbox_metadata") or {}
    sector = meta.get("sector") or "financial_services"
    sector_label = (meta.get("other_sector_name") or sector or "").replace("_", " ").title()
    objective = (meta.get("objective") or "").strip() or "operational performance"

    title = f"Q2 {datetime.now(timezone.utc).year} Board Pack — {ctx.get('name') or 'Sample Co'}"
    preview = (
        f"# {title}\n\n"
        f"**Sector**: {sector_label}\n"
        f"**Reporting period**: Q2, this fiscal year\n\n"
        f"## 1. CEO summary\n\n"
        f"Trading was steady through the period. The headline movement is on "
        f"{objective} — see Section 3 for management's read. Cash conversion "
        f"held above the rolling four-quarter average; receivables are tighter.\n\n"
        f"## 2. Operating performance\n\n"
        f"- Revenue: in line with budget, +6% year-on-year.\n"
        f"- Margin: 90 bps below plan, attributed to one-off legal accruals.\n"
        f"- Cash & equivalents: comfortable; covenant headroom unchanged.\n\n"
        f"## 3. {objective.capitalize()} — management view\n\n"
        f"This quarter's drift is consistent with the trajectory flagged in Q1. "
        f"Mitigation actions are in flight; we expect to be back inside band by "
        f"end of next quarter. Risk register updated accordingly (Item 11).\n\n"
        f"## 4. People & governance\n\n"
        f"No changes to senior management. Audit committee met twice; no "
        f"reportable items. Whistleblower channel: zero submissions.\n\n"
        f"## 5. Forward look\n\n"
        f"Order book is healthy. Two strategic decisions are on this board's "
        f"plate this quarter — see appendices A and B. Management requests an "
        f"in-camera item for Section 5b.\n"
    )
    return {
        "context_id": context_id,
        "title": title,
        "filename": f"{title.replace(' ', '-')}.md",
        "preview": preview,
        "word_count": len(preview.split()),
        "already_accepted": False,
    }


class SandboxSampleAccept(BaseModel):
    title: str = Field(..., min_length=4, max_length=200)
    filename: str = Field(..., min_length=4, max_length=200)
    preview: str = Field(..., min_length=80, max_length=20000)


@router.post("/contexts/{context_id}/sample-doc/accept")
async def sandbox_sample_doc_accept(
    context_id: str,
    body: SandboxSampleAccept,
    current: Dict[str, Any] = Depends(get_current_account),
):
    """Materialise the sample as a real document in the sandbox context."""
    ctx = await db.contexts.find_one(
        {"id": context_id, "owner_account_id": current["id"]},
        {"_id": 0},
    )
    if not ctx or ctx.get("type") != "sandbox":
        raise HTTPException(status_code=404, detail="Sandbox context not found")

    doc_id = str(uuid.uuid4())
    now_iso = _iso(_now())
    doc = {
        "id": doc_id,
        "context_id": context_id,
        "account_id": current["id"],
        "name": body.title,
        "original_filename": body.filename,
        "size_bytes": len(body.preview.encode("utf-8")),
        "content_type": "text/markdown",
        "extracted_text": body.preview,
        "status": "ready",
        "trust_level": "trusted",
        "akki_summary": {
            "tldr": body.preview.split("\n\n", 2)[1][:280] if "\n\n" in body.preview else None,
            "source": "sandbox_sample",
        },
        "sandbox_artefact": True,
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    await db.documents.insert_one(doc.copy())
    # Stamp the metadata so the card disappears from the home canvas.
    await db.contexts.update_one(
        {"id": context_id},
        {"$set": {"sandbox_metadata.sample_doc_accepted": True,
                  "sandbox_metadata.sample_doc_id": doc_id,
                  "sandbox_metadata.sample_doc_accepted_at": now_iso}},
    )
    await write_audit(
        context_id, current["id"], "sandbox.sample_doc.accept",
        "document", doc_id, {"title": body.title},
    )
    return {"ok": True, "doc_id": doc_id, "title": body.title}


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

    # Phase 4 — Surface a pre-fill payload so the First Session intake form
    # can be hydrated with what the user already told us during the sandbox
    # intake (role + objective + company name). The user can still edit
    # before submitting; we just save them three keystrokes.
    prefill_first_session: Optional[Dict[str, Any]] = None
    if my_ctx_ids:
        src_ctx = await db.contexts.find_one(
            {"id": {"$in": my_ctx_ids}},
            {"_id": 0, "name": 1, "sandbox_metadata": 1},
        )
        if src_ctx:
            meta = src_ctx.get("sandbox_metadata") or {}
            intake_inputs = meta.get("intake_inputs") or {}
            sandbox_role = (intake_inputs.get("role") or "").lower()
            role_map = {
                "ned": "ned",
                "executive": "executive",
                "both": "dual",
            }
            prefill_first_session = {
                "role": role_map.get(sandbox_role, "executive"),
                "primary_context_name": (src_ctx.get("name") or "")[:80],
                "top_of_mind": (meta.get("objective") or "")[:240],
            }

    return {
        "account": sanitize_account(refreshed_acc),
        "contexts_kept": len(my_ctx_ids) if body.keep_sandbox else 0,
        "access_token": access,
        "prefill_first_session": prefill_first_session,
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


# =============================================================================
# Phase J — Sandbox v2 (UX rebuild per Sandbox UX Brief §3-§10)
#
# A new linear, four-step pre-auth experience anchored on the Phase I Solva v3
# flow + a Work Studio composition demo + a Cycle Manager snapshot. Step 2
# (Pulse) is deferred to Phase D.2; STEP_1_REVEAL skips to STEP_3_STUDIO.
#
# This block is purely additive — the legacy `/api/sandbox/*` endpoints above
# remain untouched and remain reachable from `/sandbox/legacy` for 30-day
# forensic fallback. Sandbox v2 stores its session state in a brand-new
# Mongo collection `sandbox_v2_sessions` (TTL on `expires_at`).
# =============================================================================

SANDBOX_V2_TTL_DAYS = 7
SANDBOX_V2_STATES = [
    "WELCOME",
    "STEP_1_SOLVA", "STEP_1_REVEAL",
    "STEP_2_PULSE", "STEP_2_REVEAL",     # declared, not reachable until Phase D.2
    "STEP_3_STUDIO", "STEP_3_REVEAL",
    "STEP_4_CYCLE", "STEP_4_REVEAL",
    "CLOSING",
]
SANDBOX_V2_ROLES = [
    "ceo", "ned", "company_secretary", "exco_member",
    "government_executive", "regulator", "investor", "other",
]
SANDBOX_V2_ORG_TYPES = [
    "bank", "healthcare", "logistics", "saas",
    "government", "pre_ipo", "listed_corporate", "other",
]


class SandboxV2WelcomeIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    role: Literal[
        "ceo", "ned", "company_secretary", "exco_member",
        "government_executive", "regulator", "investor", "other",
    ]
    org_type: Literal[
        "bank", "healthcare", "logistics", "saas",
        "government", "pre_ipo", "listed_corporate", "other",
    ]
    hope: Optional[str] = Field(default=None, max_length=400)


class SandboxV2PatchIn(BaseModel):
    state: Optional[str] = Field(default=None, max_length=40)
    payload: Optional[Dict[str, Any]] = None


class SandboxV2SaveSendIn(BaseModel):
    email: EmailStr


def _sandbox_v2_default_record(body: SandboxV2WelcomeIn) -> Dict[str, Any]:
    sid = str(uuid.uuid4())
    now_dt = datetime.now(timezone.utc)
    return {
        "id": sid,
        "name": body.name.strip(),
        "role": body.role,
        "org_type": body.org_type,
        "hope": (body.hope or "").strip() or None,
        "state": "WELCOME",
        "solva_session_id": None,
        "studio_state": {"draft_built": False, "added_sentence": None, "refused_sentence": None},
        "cycle_state": {"viewed": False},
        "captured_email": None,
        "created_at": _iso(now_dt),
        "updated_at": _iso(now_dt),
        "expires_at": now_dt + timedelta(days=SANDBOX_V2_TTL_DAYS),
        "exited_at": None,
        "completed_at": None,
        "version": 2,
        "user_agent": None,
    }


def _sanitize_v2(rec: Dict[str, Any]) -> Dict[str, Any]:
    """Drop Mongo `_id` and convert datetime fields to ISO strings."""
    if not rec:
        return rec
    out = {k: v for k, v in rec.items() if k != "_id"}
    expires_at = out.get("expires_at")
    if isinstance(expires_at, datetime):
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        out["expires_at"] = _iso(expires_at)
    return out


def _ensure_aware(dt: Any) -> Any:
    """Normalise a Mongo-returned datetime to a tz-aware UTC instant.
    Motor / PyMongo strips tzinfo from BSON datetimes; this lets us
    compare them safely against `datetime.now(timezone.utc)`."""
    if isinstance(dt, datetime) and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


@router.post("/v2/sessions")
async def sandbox_v2_create_session(body: SandboxV2WelcomeIn, response: Response):
    """Create the Sandbox v2 session AND mint a disposable account + JWT
    so the visitor can call the (auth-gated) Solva v2 endpoints in Step 1
    without ever signing up.

    The disposable account is flagged ``is_sandbox=True`` and tied to the
    sandbox v2 session id via ``sandbox_v2_session_id``. It does not get a
    Mongo `contexts` row (Sandbox v2 doesn't seed a workspace; Step 1 uses
    the unattached Solva flow with ``context_id=None``). The TTL on
    ``sandbox_v2_sessions.expires_at`` (7 days) is the only thing keeping
    the session alive for resume.
    """
    rec = _sandbox_v2_default_record(body)
    await db.sandbox_v2_sessions.insert_one(dict(rec))

    # Disposable account + JWT so Step 1 can call /api/solva/v2/sessions.
    account_id = str(uuid.uuid4())
    disposable_email = f"sandbox-v2+{rec['id']}@akki.local"
    throwaway_password = secrets.token_urlsafe(16)
    declared_role = "ned" if body.role == "ned" else (
        "executive" if body.role in {"ceo", "exco_member", "company_secretary"} else "dual"
    )
    account_doc = {
        "id": account_id,
        "email": disposable_email,
        "name": f"Sandbox v2 visitor ({rec['name']})",
        "declared_role": declared_role,
        "password_hash": hash_password(throwaway_password),
        "mfa_enabled": False,
        "mfa_secret": None,
        "default_context_id": None,
        "is_sandbox": True,
        "sandbox_v2_session_id": rec["id"],
        "created_at": _iso(datetime.now(timezone.utc)),
    }
    await db.accounts.insert_one(account_doc)

    access = create_access_token(account_id, disposable_email)
    refresh = create_refresh_token(account_id)
    try:
        set_auth_cookies(response, access, refresh)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[sandbox-v2] could not set auth cookies: %s", exc)

    # Stamp the disposable account on the v2 record so the resume path
    # can re-issue cookies for a returning visitor.
    await db.sandbox_v2_sessions.update_one(
        {"id": rec["id"]},
        {"$set": {"sandbox_account_id": account_id, "sandbox_email": disposable_email}},
    )

    return {
        "session_id": rec["id"],
        "expires_at": _iso(rec["expires_at"]),
        "state": rec["state"],
        "name": rec["name"],
        "role": rec["role"],
        "org_type": rec["org_type"],
        "hope": rec["hope"],
        # Bearer-fallback for environments where cookies are stripped.
        "access_token": access,
        "refresh_token": refresh,
        "account_id": account_id,
    }


@router.get("/v2/sessions/{sid}")
async def sandbox_v2_get_session(sid: str, response: Response):
    rec = await db.sandbox_v2_sessions.find_one({"id": sid})
    if not rec:
        raise HTTPException(status_code=404, detail="Sandbox session not found.")
    expires_at = _ensure_aware(rec.get("expires_at"))
    if isinstance(expires_at, datetime) and expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="Sandbox session expired.")

    # Re-mint cookies for the disposable account so a returning visitor
    # (after closing the tab and coming back via the resume token) can
    # keep calling the auth-gated Solva v2 endpoints.
    sandbox_account_id = rec.get("sandbox_account_id")
    sandbox_email = rec.get("sandbox_email")
    out = _sanitize_v2(rec)
    if sandbox_account_id and sandbox_email:
        try:
            access = create_access_token(sandbox_account_id, sandbox_email)
            refresh = create_refresh_token(sandbox_account_id)
            set_auth_cookies(response, access, refresh)
            out["access_token"] = access
            out["refresh_token"] = refresh
        except Exception as exc:  # noqa: BLE001
            logger.warning("[sandbox-v2] could not re-mint cookies on resume: %s", exc)
    return out


@router.patch("/v2/sessions/{sid}")
async def sandbox_v2_patch_session(sid: str, body: SandboxV2PatchIn):
    rec = await db.sandbox_v2_sessions.find_one({"id": sid})
    if not rec:
        raise HTTPException(status_code=404, detail="Sandbox session not found.")
    expires_at = _ensure_aware(rec.get("expires_at"))
    if isinstance(expires_at, datetime) and expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="Sandbox session expired.")

    update: Dict[str, Any] = {"updated_at": _iso(datetime.now(timezone.utc))}
    if body.state is not None:
        if body.state not in SANDBOX_V2_STATES:
            raise HTTPException(status_code=422, detail=f"Unknown state '{body.state}'.")
        update["state"] = body.state
        if body.state == "CLOSING":
            update["completed_at"] = _iso(datetime.now(timezone.utc))
    if body.payload:
        # Whitelist payload keys to avoid accidental clobber.
        for key in ("solva_session_id", "studio_state", "cycle_state", "captured_email"):
            if key in body.payload:
                update[key] = body.payload[key]
    await db.sandbox_v2_sessions.update_one({"id": sid}, {"$set": update})
    rec = await db.sandbox_v2_sessions.find_one({"id": sid})
    return _sanitize_v2(rec)


@router.post("/v2/sessions/{sid}/exit")
async def sandbox_v2_exit_session(sid: str):
    rec = await db.sandbox_v2_sessions.find_one({"id": sid})
    if not rec:
        raise HTTPException(status_code=404, detail="Sandbox session not found.")
    await db.sandbox_v2_sessions.update_one(
        {"id": sid},
        {"$set": {
            "exited_at": _iso(datetime.now(timezone.utc)),
            "updated_at": _iso(datetime.now(timezone.utc)),
        }},
    )
    expires_at = _ensure_aware(rec.get("expires_at"))
    return {
        "ok": True,
        "preserved_until": _iso(expires_at) if isinstance(expires_at, datetime) else rec.get("expires_at"),
    }


# ---------------------------------------------------------------------------
# Phase J.5 — corpus selectors (read-only, no auth, deterministic)
# ---------------------------------------------------------------------------
@router.get("/v2/sessions/{sid}/opening-question")
async def sandbox_v2_opening_question(sid: str):
    """Return a calibrated Solva opening question for the visitor (Step 1)."""
    from sandbox_v2_corpus import pick_opening_question, stable_seed
    rec = await db.sandbox_v2_sessions.find_one({"id": sid})
    if not rec:
        raise HTTPException(status_code=404, detail="Sandbox session not found.")
    seed = stable_seed(rec.get("id", "") or "", rec.get("role", "") or "")
    return {"question": pick_opening_question(rec["role"], rec["org_type"], seed=seed)}


@router.get("/v2/sessions/{sid}/fallback-situation")
async def sandbox_v2_fallback_situation(sid: str):
    """Empty-framing fallback (brief §4.5)."""
    from sandbox_v2_corpus import pick_fallback_situation
    rec = await db.sandbox_v2_sessions.find_one({"id": sid})
    if not rec:
        raise HTTPException(status_code=404, detail="Sandbox session not found.")
    return {"situation": pick_fallback_situation(rec["role"], rec["org_type"])}


@router.get("/v2/sessions/{sid}/studio-sources")
async def sandbox_v2_studio_sources(sid: str):
    """Pre-loaded Step 3 source-material chips."""
    from sandbox_v2_corpus import pick_studio_sources
    rec = await db.sandbox_v2_sessions.find_one({"id": sid})
    if not rec:
        raise HTTPException(status_code=404, detail="Sandbox session not found.")
    return {"sources": pick_studio_sources(rec["role"], rec["org_type"])}


@router.get("/v2/sessions/{sid}/cycle-snapshot")
async def sandbox_v2_cycle_snapshot(sid: str):
    """Step 4 read-only Cycle Manager snapshot (brief §7)."""
    from sandbox_v2_corpus import pick_cycle_snapshot
    rec = await db.sandbox_v2_sessions.find_one({"id": sid})
    if not rec:
        raise HTTPException(status_code=404, detail="Sandbox session not found.")
    return {"snapshot": pick_cycle_snapshot(rec["role"], rec["org_type"])}


@router.get("/v2/sessions/{sid}/pulse-signals")
async def sandbox_v2_pulse_signals(sid: str):
    """Step 2 Pulse signals — content ingested now per Phase D.2's
    forthcoming UI. Pack §"Inter-connection within a context": signals'
    citations resolve to Step 3 source documents."""
    from sandbox_v2_corpus import pick_pulse_signals
    rec = await db.sandbox_v2_sessions.find_one({"id": sid})
    if not rec:
        raise HTTPException(status_code=404, detail="Sandbox session not found.")
    return {"signals": pick_pulse_signals(rec["role"], rec["org_type"])}


@router.get("/v2/sessions/{sid}/composed-draft")
async def sandbox_v2_composed_draft(sid: str):
    """Step 3 — the verbatim 4-paragraph composed draft for the user's
    routed (role, org_type)."""
    from sandbox_v2_corpus import pick_composed_draft
    rec = await db.sandbox_v2_sessions.find_one({"id": sid})
    if not rec:
        raise HTTPException(status_code=404, detail="Sandbox session not found.")
    return {"draft": pick_composed_draft(rec["role"], rec["org_type"])}


# ---------------------------------------------------------------------------
# Phase J.3 — Studio "add a sentence" provenance check.
#
# Deterministic keyword-overlap heuristic — accepts the user-typed
# sentence iff at least one keyword from any loaded source chip
# appears in the typed text (case-insensitive, after light stop-word
# trimming). No LLM call: we want sandbox latency to stay tight and
# the demo to stay reproducible.
# ---------------------------------------------------------------------------
class SandboxV2AddSentenceIn(BaseModel):
    sentence: str = Field(min_length=2, max_length=400)


_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "of", "to", "for",
    "in", "on", "at", "by", "from", "with", "as", "is", "was", "were", "be",
    "been", "are", "this", "that", "these", "those", "it", "its", "we", "our",
    "they", "their", "you", "your", "i", "me", "my",
}


def _tokens(text: str) -> List[str]:
    out: List[str] = []
    buf = []
    for ch in (text or "").lower():
        if ch.isalnum():
            buf.append(ch)
        else:
            if buf:
                tok = "".join(buf)
                if tok and tok not in _STOPWORDS and len(tok) > 2:
                    out.append(tok)
                buf = []
    if buf:
        tok = "".join(buf)
        if tok and tok not in _STOPWORDS and len(tok) > 2:
            out.append(tok)
    return out


@router.post("/v2/sessions/{sid}/studio/add-sentence")
async def sandbox_v2_add_sentence(sid: str, body: SandboxV2AddSentenceIn):
    """Accept the user-typed sentence iff its tokens overlap with the
    keywords of any loaded source chip; refuse otherwise.

    Refusal voice is per-context: the Bank context uses the pack's
    verbatim refusal copy; other contexts use the same FT cadence
    parameterised in `sandbox_v2_corpus.pick_provenance_refusal`.
    """
    from sandbox_v2_corpus import pick_studio_sources, pick_provenance_refusal

    rec = await db.sandbox_v2_sessions.find_one({"id": sid})
    if not rec:
        raise HTTPException(status_code=404, detail="Sandbox session not found.")
    sources = pick_studio_sources(rec["role"], rec["org_type"])

    typed_tokens = set(_tokens(body.sentence))
    matched_sources: List[Dict[str, Any]] = []
    for src in sources:
        kws = {kw.lower() for kw in (src.get("keywords") or [])}
        if typed_tokens & kws:
            matched_sources.append({"id": src["id"], "title": src["title"], "kind": src["kind"]})

    if matched_sources:
        # Persist the accepted sentence onto the session record so the
        # state machine reducer can rehydrate from server-side truth.
        await db.sandbox_v2_sessions.update_one(
            {"id": sid},
            {"$set": {
                "studio_state.added_sentence": body.sentence,
                "studio_state.refused_sentence": None,
                "updated_at": _iso(datetime.now(timezone.utc)),
            }},
        )
        return {
            "accepted": True,
            "citation": {"sources": matched_sources[:3]},
            "sentence": body.sentence,
        }

    refusal_voice = pick_provenance_refusal(rec["role"], rec["org_type"])
    await db.sandbox_v2_sessions.update_one(
        {"id": sid},
        {"$set": {
            "studio_state.refused_sentence": body.sentence,
            "studio_state.added_sentence": None,
            "updated_at": _iso(datetime.now(timezone.utc)),
        }},
    )
    return {
        "accepted": False,
        "reason": "no_source",
        "message": refusal_voice,
    }


# ---------------------------------------------------------------------------
# Phase J.4 — Save & send (Resend in test mode; degrades to a noop log
# when RESEND_API_KEY is absent).
#
# Behaviour:
#   • Persists the captured email on the sandbox session.
#   • Builds a resume URL (PUBLIC_APP_URL + /sandbox/resume?token=<sid>).
#   • If a Solva session was created in Step 1, fetches the existing
#     /api/solva/v2/sessions/{sid}/export.pdf and attaches it.
#   • Calls email_service.send_email and surfaces the resulting `mode`
#     verbatim — including the new `test_mode_restricted` value the
#     UI uses to show the friendly "test-mode constraint" notice.
# ---------------------------------------------------------------------------
@router.post("/v2/sessions/{sid}/save-and-send")
async def sandbox_v2_save_and_send(sid: str, body: SandboxV2SaveSendIn):
    rec = await db.sandbox_v2_sessions.find_one({"id": sid})
    if not rec:
        raise HTTPException(status_code=404, detail="Sandbox session not found.")

    await db.sandbox_v2_sessions.update_one(
        {"id": sid},
        {"$set": {
            "captured_email": str(body.email),
            "updated_at": _iso(datetime.now(timezone.utc)),
        }},
    )

    import os as _os
    public_base = (
        _os.environ.get("PUBLIC_APP_URL")
        or _os.environ.get("FRONTEND_URL")
        or "https://akki.ai"
    ).rstrip("/")
    resume_url = f"{public_base}/sandbox/resume?token={sid}"

    # Build the email body. The PDF attachment is best-effort; if the
    # Solva export is unavailable we still send the resume link.
    attachments: List[Dict[str, Any]] = []
    solva_sid = rec.get("solva_session_id")
    if solva_sid:
        try:
            solva_rec = await db.solva_v2_sessions.find_one(
                {"id": solva_sid}, {"_id": 0},
            )
            if solva_rec:
                from solva_artefact_export import build_pdf
                # build_pdf is sync + CPU-bound (WeasyPrint). Push to a
                # thread so we don't block the event loop.
                import asyncio as _asyncio
                pdf_bytes = await _asyncio.to_thread(build_pdf, solva_rec)
                if pdf_bytes:
                    import base64 as _b64
                    attachments.append({
                        "filename": "akki-sandbox-session.pdf",
                        "content": _b64.b64encode(pdf_bytes).decode("ascii"),
                    })
        except Exception as exc:  # noqa: BLE001
            logger.info("[sandbox-v2] could not attach Solva PDF for sid=%s: %s", sid, exc)

    delivery_mode: str = "noop"
    delivery_message: Optional[str] = None
    delivery_id: Optional[str] = None

    try:
        from email_service import send_email
        from os import environ
        if environ.get("RESEND_API_KEY"):
            html = (
                f"<p>Hi {rec.get('name', '')},</p>"
                f"<p>Your Akki Sandbox session is saved for the next 7 days. "
                f"You can pick up where you left off: <a href='{resume_url}'>{resume_url}</a>.</p>"
                "<p>The synthesis Solva produced is attached; the architecture is real, "
                "the data is calibrated.</p><p>— The Akki team</p>"
            )
            email_resp = await send_email(
                to=[str(body.email)],
                subject="Your Akki Sandbox session — saved.",
                html=html,
                tags=[{"name": "campaign", "value": "sandbox-v2-save-and-send"}],
                attachments=attachments or None,
            )
            if isinstance(email_resp, dict):
                delivery_mode = email_resp.get("mode", "unknown")
                delivery_id = email_resp.get("id")
                if delivery_mode == "test_mode_restricted":
                    delivery_message = (
                        "Resend is in test mode in this environment, so we can only "
                        "deliver to the registered test address. Your session is still "
                        "saved — bookmark the resume link above."
                    )
        else:
            delivery_mode = "noop"
            logger.info("[sandbox-v2] RESEND_API_KEY missing — save-and-send logged only sid=%s", sid)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[sandbox-v2] save-and-send email failed: %s", exc)
        delivery_mode = "error"
        delivery_message = "We couldn't send the email just now — your session is still saved."

    return {
        "ok": delivery_mode in {"sent", "noop"},
        "email": str(body.email),
        "resume_url": resume_url,
        "delivery_mode": delivery_mode,
        "delivery_id": delivery_id,
        "message": delivery_message,
        "attachment_count": len(attachments),
    }

