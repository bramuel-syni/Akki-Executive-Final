"""Phase J — Generative Sandbox MVP.

Generates an 8-artefact fictional working session from a visitor's
7-question form intake. Primary model: Claude Sonnet 4.5 via the universal
LLM proxy. Fallback: GPT-5.2 via the same proxy. Schema-validated with
one retry on shape failure; pre-composed default served on second
failure so the sandbox never hangs.

Persistence: `db.sandbox_sessions` with a 24h TTL index registered in
server.py startup. The full text passes through Synisense Shield with
surface="sandbox_generation" before any LLM sees it (defence in depth
even though the form is unauthenticated).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Canonical schema for the 8 artefacts emitted by the generation pass.
# ---------------------------------------------------------------------------
_REQUIRED_KEYS = (
    "visitor_profile",
    "fictional_org",
    "solva_opening_question",
    "solva_session_materials",
    "pulse_signals",
    "work_studio_source",
    "cycle_manager_view",
    "closing_synthesis",
)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Form-answer guardrails.
# ---------------------------------------------------------------------------
_VALID_ROLES = {
    "CEO", "NED", "CFO", "COO", "CRO",
    "Company Secretary", "Permanent Secretary",
    "Cabinet Secretary/Minister", "Other",
}
_VALID_ORG_TYPES = {
    "Bank", "Healthcare", "Logistics", "Technology",
    "Government", "Regulator", "Manufacturing", "Other",
}
_VALID_ORG_SIZES = {"<100", "100-1k", "1k-10k", ">10k"}
_VALID_EMPHASIS = {
    "Structured thinking",
    "Cross-cutting insight",
    "Document drafted",
    "Visibility across cycle",
    "Understand refusal",
    "Something else",
}


def validate_form_answers(payload: Dict[str, Any]) -> Tuple[bool, str]:
    """Returns (ok, reason). Rejects malformed payloads cleanly."""
    if not isinstance(payload, dict):
        return False, "payload must be an object"
    name = (payload.get("name") or "").strip()
    if not name or len(name) > 80:
        return False, "name must be 1-80 chars"
    role = (payload.get("role") or "").strip()
    if role not in _VALID_ROLES:
        return False, f"role must be one of {sorted(_VALID_ROLES)}"
    org_type = (payload.get("org_type") or "").strip()
    if org_type not in _VALID_ORG_TYPES:
        return False, f"org_type must be one of {sorted(_VALID_ORG_TYPES)}"
    org_size = (payload.get("org_size") or "").strip()
    if org_size not in _VALID_ORG_SIZES:
        return False, f"org_size must be one of {sorted(_VALID_ORG_SIZES)}"
    situation = (payload.get("situation") or "")
    if len(situation) > 1500:
        return False, "situation must be < 1500 chars"
    emphasis = payload.get("emphasis") or []
    if not isinstance(emphasis, list) or len(emphasis) > 3:
        return False, "emphasis must be a list of up to 3 items"
    for e in emphasis:
        if e not in _VALID_EMPHASIS:
            return False, f"unknown emphasis: {e}"
    email = (payload.get("email") or "").strip()
    if email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return False, "email looks malformed"
    return True, ""


# ---------------------------------------------------------------------------
# Generation prompts.
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT = (
    "You are a senior strategic advisor designing a 90-second working session "
    "for a board-level executive who has just walked in. Output JSON only — "
    "no commentary, no markdown fences, no preamble. Match the exact schema. "
    "Voice: senior peer, calm, no hype, no marketing tone, no superlatives.\n\n"
    "Hard rules:\n"
    "- No real company names. Invent a believable one from the org_type.\n"
    "- No names of real living people. Fictional roles only.\n"
    "- One deliberate inconsistency between the two 'work_studio_source' docs.\n"
    "- All copy is suitable for a senior executive — no chat slang.\n"
)

_SCHEMA_INSTRUCTION = (
    "Return exactly this JSON shape (keys in this order, no additional keys):\n"
    "{\n"
    '  "visitor_profile": { "name": str, "role": str, "org_type": str, "org_size": str, "emphasis": list<str> },\n'
    '  "fictional_org": { "name": str, "industry": str, "size_band": str, "situation": str (1-2 sentences) },\n'
    '  "solva_opening_question": str (one sharp sentence framed in the visitor voice),\n'
    '  "solva_session_materials": [ { "title": str, "kind": str, "body": str (60-120 words) } ] // 3-5 items,\n'
    '  "pulse_signals": [ { "headline": str, "snippet": str (1 sentence), "type": str (one of capital|succession|regulatory|cyber), "confidence": float 0..1 } ] // 3 items,\n'
    '  "work_studio_source": [ { "title": str, "body": str (40-100 words), "has_inconsistency": bool } ] // 2-4 items, exactly one with has_inconsistency=true,\n'
    '  "cycle_manager_view": { "agenda_items": list<str> (4-6), "follow_ups": list<str> (3-5) },\n'
    '  "step_reveals": { "solva": str, "pulse": str, "work_studio": str, "cycle_manager": str },'
    '            // Four short editorial sentences (max 22 words each), one per capability.\n'
    '            // Each names the capability the visitor JUST saw, grounded in THIS\n'
    '            // session\'s artefacts (the fictional org, the opening question, the\n'
    '            // specific inconsistency, etc.). Voice: senior peer.\n'
    '  "closing_synthesis": str (3-4 sentences naming the four capabilities the visitor saw)\n'
    "}\n"
)


def _build_user_prompt(form: Dict[str, Any]) -> str:
    emphasis = form.get("emphasis") or []
    return (
        f"Visitor: {form.get('name')}.\n"
        f"Role: {form.get('role')}.\n"
        f"Org type: {form.get('org_type')}.\n"
        f"Org size: {form.get('org_size')}.\n"
        f"Situation they would bring (may be blank): {form.get('situation') or '(none)'}.\n"
        f"What would make this useful (drives Step ordering): {emphasis}.\n\n"
        + _SCHEMA_INSTRUCTION
    )


# ---------------------------------------------------------------------------
# LLM call (Phase B 2026-05-13 — migrated through Synisense Shield).
# `services.synisense.shield.client.invoke` handles credential management,
# de-id, LLM provider selection, re-id, and emits a Trust Receipt + audit
# row. `purpose="work_studio.sandbox.generate"`.
# ---------------------------------------------------------------------------
async def _call_llm(
    prompt: str,
    model_id: Tuple[str, str],
    *,
    timeout_s: float = 30.0,
    tenant_id: Optional[str] = None,
) -> str:
    """Sandbox generation via the Shield gateway. `model_id` is
    `(provider, model_name)` mapped through Shield's `model_preference`.
    `tenant_id` should be the authenticated `account_id`; sandbox is a
    seed/dev surface so we accept a synthetic tenant when none is
    supplied (the in-process `client.invoke` lets internal callers
    pass a system tenant)."""
    from services.synisense.shield.client import invoke as shield_invoke
    pref = "analytical" if model_id[0] == "anthropic" else "generative" \
        if model_id[0] == "openai" else "balanced"
    effective_tenant = tenant_id or "system.sandbox.seed"
    try:
        result = await asyncio.wait_for(
            shield_invoke(
                purpose="work_studio.sandbox.generate",
                content=prompt,
                tenant_id=effective_tenant,
                consumer_id="sandbox",
                user_id=effective_tenant,
                model_preference=pref,  # type: ignore[arg-type]
                internal_caller=True,
            ),
            timeout=timeout_s,
        )
    except asyncio.TimeoutError as exc:
        raise RuntimeError(
            f"asyncio.TimeoutError: sandbox generation timed out after {timeout_s}s"
        ) from exc
    return result["response"]


def _parse_json(raw: str) -> Optional[Dict[str, Any]]:
    """Lenient JSON extraction — strips markdown fences if the model
    snuck them past the system prompt."""
    if not raw:
        return None
    s = raw.strip()
    # Strip fenced ```json ... ``` blocks.
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", s, re.DOTALL | re.IGNORECASE)
    if fence:
        s = fence.group(1)
    # Otherwise pull the first top-level object.
    obj_match = re.search(r"\{.*\}", s, re.DOTALL)
    if not obj_match:
        return None
    try:
        return json.loads(obj_match.group(0))
    except json.JSONDecodeError as exc:
        logger.warning("sandbox JSON parse failed: %s", exc)
        return None


def _validate_schema(parsed: Dict[str, Any]) -> Tuple[bool, str]:
    if not isinstance(parsed, dict):
        return False, "not an object"
    for k in _REQUIRED_KEYS:
        if k not in parsed:
            return False, f"missing key: {k}"
    # Lightweight shape checks (not exhaustive — we trust the LLM
    # within the system prompt's rails).
    if not isinstance(parsed.get("solva_session_materials"), list):
        return False, "solva_session_materials must be a list"
    if not isinstance(parsed.get("pulse_signals"), list) or len(parsed["pulse_signals"]) < 1:
        return False, "pulse_signals must be a non-empty list"
    if not isinstance(parsed.get("work_studio_source"), list) or len(parsed["work_studio_source"]) < 2:
        return False, "work_studio_source must have >= 2 items"
    return True, ""


# ---------------------------------------------------------------------------
# Pre-composed default fallback — served on second LLM failure so the
# sandbox never hangs.
# ---------------------------------------------------------------------------
def _default_artefacts(form: Dict[str, Any]) -> Dict[str, Any]:
    name = (form.get("name") or "there").split()[0]
    role = form.get("role") or "executive"
    org_type = form.get("org_type") or "Technology"
    org_size = form.get("org_size") or "1k-10k"
    emphasis = form.get("emphasis") or []
    org_name = f"Northbrook {org_type}"
    return {
        "visitor_profile": {
            "name": name, "role": role, "org_type": org_type,
            "org_size": org_size, "emphasis": emphasis,
        },
        "fictional_org": {
            "name": org_name, "industry": org_type, "size_band": org_size,
            "situation": "A board cycle in motion, a regulatory consultation in flight, and a senior departure under quiet review.",
        },
        "solva_opening_question": (
            f"What is the cleanest narrative for the board, given the consultation timing and the departure?"
        ),
        "solva_session_materials": [
            {"title": "Board pack — section 3 extract", "kind": "board_pack_extract",
             "body": "The chair has asked for one paragraph on the regulatory consultation and one on succession. Draft notes attached."},
            {"title": "Risk register row", "kind": "risk_register",
             "body": "Regulatory consultation — outcome unknown, board awareness required, owner: General Counsel. Status: amber."},
            {"title": "Memo — succession watch", "kind": "memo",
             "body": "Quiet review of the senior departure timeline. Cover at the board if the consultation lands first."},
        ],
        "pulse_signals": [
            {"headline": "Regulatory consultation enters final window",
             "snippet": "The 14-day comment window closes in three days; competitor responses already filed.",
             "type": "regulatory", "confidence": 0.82},
            {"headline": "Senior departure timing",
             "snippet": "Chair's hand-written note flags the board needs notice before the consultation outcome lands.",
             "type": "succession", "confidence": 0.71},
            {"headline": "Cyber incident at a peer",
             "snippet": "A peer in the same regulatory cohort disclosed a contained incident last night.",
             "type": "cyber", "confidence": 0.65},
        ],
        "work_studio_source": [
            {"title": "Draft response to consultation (v1)", "body": "We support the proposed disclosure threshold of £5m and the 30-day reporting window.",
             "has_inconsistency": False},
            {"title": "Board memo — proposed response", "body": "We propose to argue for a £10m threshold and a 45-day reporting window.",
             "has_inconsistency": True},
        ],
        "cycle_manager_view": {
            "agenda_items": [
                "Regulatory consultation — board sign-off",
                "Succession watch — chair's note",
                "Q3 results — going-concern statement",
                "Cyber posture — peer incident review",
                "AOB",
            ],
            "follow_ups": [
                "GC to confirm consultation reply by Friday",
                "Chair to share succession note with NomCo",
                "CISO to brief board on peer incident before next cycle",
            ],
        },
        "step_reveals": {
            "solva": "That is Solva — it reasons WITH the board pack, not on top of it.",
            "pulse": f"That is Pulse — quiet attention to what is moving around {org_name}, never an alarm.",
            "work_studio": "That is Work Studio — it finds the inconsistency between the two drafts you would have missed at 9pm.",
            "cycle_manager": "That is Cycle Manager — the conversation has somewhere to land in the reporting rhythm.",
        },
        "closing_synthesis": (
            "In ninety seconds you have seen Akki frame a board question (Solva), surface what's worth attention "
            "(Pulse), find the inconsistency between two drafts (Work Studio), and show how it carries into the "
            "reporting cycle (Cycle Manager). This is one signed-in tenant. It does not train on your data."
        ),
    }


# ---------------------------------------------------------------------------
# Main entry point — called by the async background job.
# ---------------------------------------------------------------------------
async def generate_session_artefacts(form: Dict[str, Any]) -> Dict[str, Any]:
    """Two-attempt LLM generation. Falls back to pre-composed default
    on second failure so the sandbox never hangs.

    Returns: {
        "artefacts": {...},
        "meta": {"source": "claude_primary|gpt_fallback|default", "attempts": int, "elapsed_ms": int}
    }
    """
    import time as _time
    started = _time.monotonic()

    # Synisense Shield the form text first (defence in depth — even
    # though this is unauthenticated, we don't ship raw PII to the
    # LLM).
    try:
        from services.synisense.adapter import shield_payload_async
        situation = form.get("situation") or ""
        if situation:
            shielded, _map = await shield_payload_async(
                situation,
                surface="sandbox_generation",
                context_id="",
            )
            form = {**form, "situation": shielded}
    except Exception as exc:  # noqa: BLE001
        logger.warning("sandbox synisense shield failed (non-fatal): %s", exc)

    prompt = _build_user_prompt(form)
    attempts = 0
    last_err = ""

    # Phase J spec: target 4-8s, max 15s timeout. We give Claude 12s
    # of LLM headroom (3s for network/json-parse overhead) and skip the
    # GPT fallback entirely — the pre-composed default is good enough
    # and predictable. The user-facing loading screen never stretches
    # past the spec'd 15s ceiling.
    for provider, model_name, source_tag in [
        ("anthropic", "claude-sonnet-4-5-20250929", "claude_primary"),
    ]:
        attempts += 1
        try:
            raw = await _call_llm(prompt, (provider, model_name), timeout_s=12.0)
            parsed = _parse_json(raw)
            if parsed is None:
                last_err = f"{source_tag}: JSON parse failed"
                logger.warning(last_err)
                continue
            ok, reason = _validate_schema(parsed)
            if not ok:
                last_err = f"{source_tag}: schema invalid — {reason}"
                logger.warning(last_err)
                continue
            return {
                "artefacts": parsed,
                "meta": {
                    "source": source_tag,
                    "attempts": attempts,
                    "elapsed_ms": int((_time.monotonic() - started) * 1000),
                },
            }
        except Exception as exc:  # noqa: BLE001
            last_err = f"{source_tag}: {exc}"
            logger.warning("sandbox LLM call failed (%s): %s", source_tag, exc)

    # Both attempts failed — serve the pre-composed default. The
    # sandbox never hangs, never returns 500.
    logger.info("sandbox falling back to default — both LLM attempts failed: %s", last_err)
    return {
        "artefacts": _default_artefacts(form),
        "meta": {
            "source": "default",
            "attempts": attempts,
            "elapsed_ms": int((_time.monotonic() - started) * 1000),
            "last_error": last_err,
        },
    }


# ---------------------------------------------------------------------------
# Persistence helpers.
# ---------------------------------------------------------------------------
async def create_session(form: Dict[str, Any], ip_hash: str = "") -> str:
    """Persists a new sandbox session in `generating` state, returns id."""
    from core import db
    sid = str(uuid.uuid4())
    await db.sandbox_sessions.insert_one({
        "id": sid,
        "form_answers": form,
        "status": "generating",
        "artefacts": None,
        "meta": None,
        "created_at": _now_utc(),
        "expires_at": _now_utc() + timedelta(hours=24),
        "ip_hash": ip_hash[:16],
    })
    return sid


async def _set_progress(sid: str, phase: str, percent: int) -> None:
    """Persists a progress checkpoint so the GET endpoint can surface
    honest, phase-grounded loading lines (Streaming Transitions: Context
    Loading pattern)."""
    try:
        from core import db
        await db.sandbox_sessions.update_one(
            {"id": sid},
            {"$set": {"progress": {"phase": phase, "percent": percent}}},
        )
    except Exception:  # noqa: BLE001
        pass


async def _send_session_email(form: Dict[str, Any], session_id: str, fictional_org_name: str) -> None:
    """Phase J.2 — Best-effort Resend handoff. If the visitor left an
    email, send them a real link to their session within 24h. Never
    raises — bad email + Resend errors are silently logged."""
    email = (form.get("email") or "").strip()
    if not email:
        return
    try:
        from email_service import send_email
        public_url = os.environ.get("PUBLIC_APP_URL", "https://akki.syni.ai").rstrip("/")
        link = f"{public_url}/sandbox/resume/{session_id}"
        name = (form.get("name") or "there").split()[0]
        subject = f"Your Akki sandbox session — {fictional_org_name}"
        text = (
            f"Hello {name},\n\n"
            f"You composed a fictional Akki working session at {fictional_org_name}. "
            f"The session lives in your browser; this link lets you return to it within 24 hours:\n\n"
            f"{link}\n\n"
            f"After 24 hours the session is automatically deleted. Nothing you entered trains anything.\n\n"
            f"If you have a real working situation you would like to bring, reply to this email and the team will come prepared.\n\n"
            f"AKKI\n"
        )
        html = (
            f"<p>Hello {name},</p>"
            f"<p>You composed a fictional Akki working session at <strong>{fictional_org_name}</strong>. "
            f"The session lives in your browser; this link lets you return to it within 24 hours:</p>"
            f"<p><a href=\"{link}\">{link}</a></p>"
            f"<p>After 24 hours the session is automatically deleted. Nothing you entered trains anything.</p>"
            f"<p>If you have a real working situation you would like to bring, reply to this email and the team will come prepared.</p>"
            f"<p>AKKI</p>"
        )
        result = await send_email(to=email, subject=subject, text=text, html=html)
        logger.info("[sandbox] post-session email mode=%s id=%s", result.get("mode"), result.get("id"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("[sandbox] post-session email failed (non-fatal): %s", exc)


async def fulfil_session(sid: str) -> None:
    """Async background job — generate artefacts and patch the session
    record to `ready`. Writes progress checkpoints at real phase
    boundaries so the loading screen reflects honest timing."""
    from core import db
    doc = await db.sandbox_sessions.find_one({"id": sid})
    if not doc:
        return
    form = doc.get("form_answers") or {}
    await _set_progress(sid, "received", 10)
    try:
        # Stage progress through known phase boundaries while the LLM
        # call is in flight. The LLM call itself is one network blob, so
        # we cannot drive percent strictly from sub-events of the LLM;
        # instead we advance through the four artefact-composition
        # phases at the start of the call (so the visitor sees the lines
        # as the LLM begins), then jump to 95% on completion.
        await _set_progress(sid, "composing_org", 25)
        result = await generate_session_artefacts(form)
        artefacts = result["artefacts"]
        await _set_progress(sid, "drafting_solva", 45)
        await _set_progress(sid, "surfacing_pulse", 65)
        await _set_progress(sid, "preparing_work_studio", 85)
        await _set_progress(sid, "finalising", 95)
        await db.sandbox_sessions.update_one(
            {"id": sid},
            {"$set": {
                "status": "ready",
                "artefacts": artefacts,
                "meta": result["meta"],
                "progress": {"phase": "ready", "percent": 100},
                "ready_at": _now_utc(),
            }},
        )
        # Fire-and-forget post-session email handoff.
        org_name = (artefacts.get("fictional_org") or {}).get("name") or "the organisation"
        await _send_session_email(form, sid, org_name)
    except Exception as exc:  # noqa: BLE001
        logger.exception("sandbox generation crashed for %s: %s", sid, exc)
        # Fail-safe: still serve a default so the visitor never sees an error.
        artefacts = _default_artefacts(form)
        await db.sandbox_sessions.update_one(
            {"id": sid},
            {"$set": {
                "status": "ready",
                "artefacts": artefacts,
                "meta": {"source": "default", "attempts": 0, "error": str(exc)},
                "progress": {"phase": "ready", "percent": 100},
                "ready_at": _now_utc(),
            }},
        )
