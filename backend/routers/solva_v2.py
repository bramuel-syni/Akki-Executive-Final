"""Solva v2 orchestrator (Phase 15.0 POC).

Single sub-module scope: Seek Clarity. Layer flow:
    framing -> grounding -> synthesis -> reflection

Gated behind `account.solva_v2_poc=true`. v1 Solva (routers/solva_engine.py)
is untouched and continues to serve all accounts.

Out of scope for 15.0 (delivered later per docs/ROADMAP.md):
  - Sub-module picker / 4-tile intake               Phase 15.2
  - Real candidate_generation/probability_weighting Phase 15.1
  - Layer 4 Reflection three locked questions       Phase 15.3
  - Tension detector / cross-module invocation      Phase 15.2
  - Refusal ladder thresholds / therapy redirect    Phase 15.3
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core import db, get_current_account, iso, now
from services.solva_v2 import (
    GROUNDING_CONTRACT_PROMPT,
    parse,
    summarise_tier_distribution,
)
from services.solva_v2.grounding_contract import GROUNDING_RETRY_PROMPT, TIER_NAMES
from services.solva_v2.llm_adapter import shielded_call, synthetic_audit_entry
from services.solva_v2.engines import (
    triangulation,
    candidate_generation,
    probability_weighting,
    refusal,
)

logger = logging.getLogger("akki.solva_v2")

router = APIRouter(prefix="/api/solva/v2", tags=["solva_v2"])


# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------
LAYERS: List[str] = ["framing", "grounding", "synthesis", "reflection"]
SUBMODULES = ["seek_clarity"]  # 15.0 ships exactly one

MAX_GROUNDING_RETRIES = 2  # => 3 total attempts on synthesis


# -----------------------------------------------------------------------------
# Pydantic
# -----------------------------------------------------------------------------
class StartV2In(BaseModel):
    cluster_id: str = Field(min_length=2, max_length=80)
    intent: str = Field(min_length=20, max_length=1200)
    context_id: Optional[str] = None
    submodule: str = Field(default="seek_clarity")
    pro_tier: bool = False


class TurnV2In(BaseModel):
    user_text: str = Field(min_length=2, max_length=4000)


# -----------------------------------------------------------------------------
# Feature flag dependency
# -----------------------------------------------------------------------------
async def require_solva_v2_flag(
    account: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    """Gate every /api/solva/v2/* endpoint on the POC flag."""
    aid = account.get("id") if isinstance(account, dict) else None
    if not aid:
        raise HTTPException(status_code=401, detail="Authentication required.")
    # Read flag LIVE from DB so a fresh flip takes effect without re-login.
    fresh = await db.accounts.find_one(
        {"id": aid}, {"_id": 0, "solva_v2_poc": 1, "is_superadmin": 1}
    )
    if not fresh or not bool(fresh.get("solva_v2_poc")):
        raise HTTPException(
            status_code=403,
            detail="Solva v2 POC is not enabled for this account.",
        )
    return account


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _next_layer(current: str) -> Optional[str]:
    try:
        i = LAYERS.index(current)
    except ValueError:
        return None
    if i >= len(LAYERS) - 1:
        return None
    return LAYERS[i + 1]


async def _is_pro(account: Dict[str, Any]) -> bool:
    """LIVE read of account plan (mirrors v1 posture — stale cache guard)."""
    aid = account.get("id") if isinstance(account, dict) else None
    if not aid:
        return False
    fresh = await db.accounts.find_one(
        {"id": aid},
        {"_id": 0, "plan": 1, "solve_pro": 1, "subscription_status": 1},
    )
    src = fresh or account
    plan = (src.get("plan") or "free").lower()
    sub = (src.get("subscription_status") or "").lower()
    if plan in ("pro", "team") and sub in ("", "active", "trialing"):
        return True
    return bool(src.get("solve_pro"))


async def _append_turn(
    sid: str,
    *,
    role: str,
    text: str,
    layer: str,
    model: Optional[str] = None,
    tier: Optional[str] = None,
) -> Dict[str, Any]:
    turn = {
        "id": str(uuid.uuid4()),
        "role": role,
        "layer": layer,
        "text": text,
        "model": model,
        "tier": tier,
        "created_at": iso(now()),
    }
    await db.solva_v2_sessions.update_one(
        {"id": sid},
        {"$push": {"turns": turn}, "$set": {"updated_at": iso(now())}},
    )
    return turn


async def _append_audit(sid: str, entries: List[Dict[str, Any]]) -> None:
    if not entries:
        return
    await db.solva_v2_sessions.update_one(
        {"id": sid},
        {"$push": {"reasoning_audit_log": {"$each": entries}},
         "$set": {"updated_at": iso(now())}},
    )


def _base_system_prompt(cluster: Dict[str, Any], layer: str, intent: str) -> str:
    hint = (cluster.get("phase_hints") or {}).get(
        # Map v2 layer names to v1 phase_hint keys for continuity.
        {"framing": "surface", "grounding": "depth",
         "synthesis": "synthesis", "reflection": "lockin"}.get(layer, "surface"),
        "",
    )
    banned = (cluster.get("banned_terms") or [])
    banned_block = ", ".join(banned) if banned else "(none specified)"
    return (
        "You are AKKI Solva \u2014 a structured-pause facilitator for board-grade "
        "problems. Single sub-module: Seek Clarity. You walk the user one layer "
        "at a time (Framing \u2192 Grounding \u2192 Synthesis \u2192 Reflection). "
        "You do NOT lecture. You ask the questions a sharp counterpart would ask.\n\n"
        f"CURRENT LAYER: {layer.upper()}.\n"
        f"LAYER INSTRUCTION: {hint}\n"
        f"USER INTENT: {intent}\n"
        f"CLUSTER: {cluster.get('label')}\n"
        f"BANNED TERMS (never use): {banned_block}\n\n"
        "TONE: Calm, editorial. Serif voice if you were speaking. No marketing "
        "language. No false certainty. Acknowledge the user's framing before "
        "pressing it.\n"
    )


# -----------------------------------------------------------------------------
# Layer generators
# -----------------------------------------------------------------------------
async def _run_framing(
    session: Dict[str, Any],
    cluster: Dict[str, Any],
    account_id: str,
    turn_id: str,
    transcript: str,
) -> Dict[str, Any]:
    system_msg = _base_system_prompt(cluster, "framing", session["intent"]) + (
        "\n\nOUTPUT FORMAT: 2\u20133 short sentences. Acknowledge what the user "
        "has named, then ask ONE specific sharpening question. Do NOT attempt "
        "diagnosis yet \u2014 this is Framing, not Synthesis."
    )
    user_query = (
        f"The user has opened a Seek Clarity session.\n\nIntent: {session['intent']}\n\n"
        f"Conversation so far:\n{transcript or '(no prior turns)'}\n\n"
        "Generate the Framing layer response now."
    )
    result = await shielded_call(
        engine="llm_primary",
        layer="framing",
        turn_id=turn_id,
        prompt=user_query,
        system_override=system_msg,
        tier="standard",
        surface="solve_v2",
        account_id=account_id,
        session_id=session["id"],
        context_id=session.get("context_id"),
    )
    return {
        "text": result.text,
        "model": result.model,
        "tier": result.tier_served,
        "audit_entries": [result.reasoning_audit_entry],
    }


async def _run_grounding(
    session: Dict[str, Any],
    cluster: Dict[str, Any],
    account_id: str,
    turn_id: str,
) -> Dict[str, Any]:
    # sector_tag comes from the linked context if any
    sector_tag: Optional[str] = None
    ctx_id = session.get("context_id")
    if ctx_id:
        ctx_doc = await db.contexts.find_one(
            {"id": ctx_id}, {"_id": 0, "sector": 1, "industry": 1}
        )
        if ctx_doc:
            sector_tag = (ctx_doc.get("sector") or ctx_doc.get("industry") or "").lower() or None

    tri = await triangulation.run(
        session=session, turn_id=turn_id, layer="grounding",
        cluster_id=cluster["id"], sector_tag=sector_tag, limit=3,
    )
    cands = await candidate_generation.run(
        session=session, turn_id=turn_id, layer="grounding",
        intent=session["intent"], cluster=cluster,
        comparables=tri["output"]["comparables"],
    )
    summary_text = (
        f"Grounding picked {tri['output']['comparable_count']} comparables "
        f"(cluster={cluster['id']}, sector={sector_tag or 'any'}) and "
        f"{cands['output']['candidate_count']} candidate framing(s) "
        f"(stub \u2014 real in 15.1). Proceeding to Synthesis."
    )
    return {
        "text": summary_text,
        "model": None,
        "tier": None,
        "comparables": tri["output"]["comparables"],
        "candidates": cands["output"]["candidates"],
        "audit_entries": [tri["audit_entry"], cands["audit_entry"]],
    }


async def _run_synthesis(
    session: Dict[str, Any],
    cluster: Dict[str, Any],
    account_id: str,
    turn_id: str,
    transcript: str,
    comparables: List[Dict[str, Any]],
    candidates: List[Dict[str, Any]],
    requested_tier: str,
) -> Dict[str, Any]:
    """Synthesis runs the LLM, enforces the grounding contract, and runs the
    independent-family validator on the final accepted body."""
    audit_entries: List[Dict[str, Any]] = []

    # Build system prompt: base + format + grounding contract + comparables
    comparable_block = triangulation.format_for_prompt(comparables)
    candidate_block = ""
    if candidates:
        cand_lines = "\n".join(
            f"  - {c.get('text','')}" for c in candidates if isinstance(c, dict)
        )
        candidate_block = (
            "\n\nCANDIDATE FRAMINGS (from the Grounding layer; weigh before "
            "writing the diagnosis):\n" + cand_lines
        )

    system_base = _base_system_prompt(cluster, "synthesis", session["intent"]) + (
        "\n\nOUTPUT FORMAT: 250\u2013350 words. One orientation sentence. "
        "Two short analysis paragraphs. One closing diagnosis sentence. "
        "If you reference comparable diagnoses, name them inline."
    )
    system_msg = system_base + candidate_block + comparable_block + GROUNDING_CONTRACT_PROMPT

    base_user_query = (
        f"Conversation so far:\n{transcript or '(no prior turns)'}\n\n"
        "Generate the SYNTHESIS layer response now. Follow the OUTPUT FORMAT "
        "exactly, and tag every assertive sentence with exactly one tier marker."
    )

    # Iterative enforcement loop
    current_user_query = base_user_query
    last_result = None
    last_parse = None
    for attempt in range(MAX_GROUNDING_RETRIES + 1):
        result = await shielded_call(
            engine="llm_primary",
            layer="synthesis",
            turn_id=turn_id,
            prompt=current_user_query,
            system_override=system_msg,
            tier=requested_tier,
            surface="solve_v2",
            account_id=account_id,
            session_id=session["id"],
            context_id=session.get("context_id"),
            run_validator=False,  # validator runs once on the ACCEPTED body below
            extra_output={"grounding_attempt": attempt + 1},
        )
        audit_entries.append(result.reasoning_audit_entry)
        parse_res = parse(result.text)
        last_result = result
        last_parse = parse_res
        if parse_res.valid:
            # Annotate the winning audit entry with tier_labels observed
            audit_entries[-1]["tier_labels"] = sorted({c.tier for c in parse_res.claims})
            audit_entries[-1]["output"]["grounding_accepted"] = True
            audit_entries[-1]["output"]["claim_count"] = len(parse_res.claims)
            break
        # Mark this attempt as a rejected violation
        audit_entries[-1]["output"]["grounding_accepted"] = False
        audit_entries[-1]["output"]["untagged_count"] = len(parse_res.untagged_sentences)
        audit_entries[-1]["output"]["malformed_count"] = len(parse_res.malformed_markers)
        # Prepare retry prompt
        retry_body = GROUNDING_RETRY_PROMPT.format(
            untagged=parse_res.untagged_sentences[:5],
            malformed=[m.get("bad_tier") for m in parse_res.malformed_markers[:5]],
            valid_tiers=TIER_NAMES,
        )
        current_user_query = base_user_query + retry_body

    if not last_parse or not last_parse.valid:
        # Hard failure — surface structured error to caller
        return {
            "grounding_violation": True,
            "audit_entries": audit_entries,
            "untagged_sentences": last_parse.untagged_sentences if last_parse else [],
            "malformed_markers": last_parse.malformed_markers if last_parse else [],
            "raw_text": last_result.text if last_result else "",
        }

    # Valid body — run probability_weighting stub (pass-through)
    pw = await probability_weighting.run(
        session=session, turn_id=turn_id, layer="synthesis",
        claims=[c.to_dict() for c in last_parse.claims],
    )
    audit_entries.append(pw["audit_entry"])

    # Run independent-family validator on the stripped synthesis text.
    # Use shielded_call-style bookkeeping: synisense hook already ran on the
    # prompt; validator operates on the LLM's output.
    from llm_service import validate_independent
    try:
        validation = await validate_independent(
            kind="solve_v2_synthesis",
            content=last_parse.stripped_text,
            objective=session.get("intent"),
            surface="solve_v2",
            account_id=account_id,
        )
    except Exception as exc:
        logger.warning("solva_v2 validator wrapper failed: %s", exc)
        validation = {
            "verdict": "qualified", "confidence": 0,
            "notes": [f"Validator wrapper error ({exc.__class__.__name__})."],
            "validator_provider": "n/a", "validator_model": "n/a",
        }
    validator_entry = await synthetic_audit_entry(
        engine="validator",
        layer="synthesis",
        turn_id=turn_id,
        output={
            "validator_verdict": validation.get("verdict"),
            "validator_confidence": validation.get("confidence"),
            "validator_provider": validation.get("validator_provider"),
            "validator_model": validation.get("validator_model"),
            "content_length": len(last_parse.stripped_text),
        },
        tier_labels=[],
        engine_version="validator@phase11",
        latency_ms=0,
    )
    audit_entries.append(validator_entry)

    return {
        "grounding_violation": False,
        "text": last_result.text,  # raw body with markers; stripped version below
        "stripped_text": last_parse.stripped_text,
        "claims": [c.to_dict() for c in last_parse.claims],
        "tier_distribution": summarise_tier_distribution(last_parse.claims),
        "model": last_result.model,
        "tier": last_result.tier_served,
        "validation": validation,
        "audit_entries": audit_entries,
    }


async def _run_reflection(
    session: Dict[str, Any],
    turn_id: str,
) -> Dict[str, Any]:
    """Layer 4 placeholder — Phase 15.3 replaces this with three locked questions."""
    entry = await synthetic_audit_entry(
        engine="llm_primary",
        layer="reflection",
        turn_id=turn_id,
        output={"placeholder": True, "phase": "15.3"},
        tier_labels=[],
        engine_version="reflection@0.0-placeholder",
        latency_ms=0,
    )
    return {
        "text": "Reflection layer arrives in Phase 15.3. Session complete.",
        "model": None,
        "tier": None,
        "audit_entries": [entry],
    }


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------
@router.post("/sessions")
async def start_session(
    body: StartV2In,
    account: Dict[str, Any] = Depends(require_solva_v2_flag),
):
    if body.submodule not in SUBMODULES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown submodule. 15.0 supports only: {SUBMODULES}.",
        )
    cluster = await db.solve_clusters.find_one({"id": body.cluster_id}, {"_id": 0})
    if not cluster:
        raise HTTPException(status_code=404, detail="Unknown cluster.")

    session_id = str(uuid.uuid4())
    is_pro_account = await _is_pro(account)
    rec = {
        "id": session_id,
        "account_id": account["id"],
        "context_id": body.context_id,
        "version": 2,
        "submodule": "seek_clarity",
        "cluster_id": body.cluster_id,
        "cluster_label": cluster.get("label"),
        "intent": body.intent.strip(),
        "layer": LAYERS[0],
        "layer_index": 0,
        "status": "active",
        "pro_tier": bool(body.pro_tier),
        "pro_account": is_pro_account,
        "turns": [],
        "reasoning_audit_log": [],
        "synthesis": None,
        "lockin": None,
        "started_at": iso(now()),
        "updated_at": iso(now()),
        "completed_at": None,
    }
    await db.solva_v2_sessions.insert_one(rec)

    # Prime framing turn immediately (mirrors v1 posture)
    solve_turn_id = str(uuid.uuid4())
    # Refusal stub at turn boundary
    ref = await refusal.run(
        session=rec, turn_id=solve_turn_id, layer="framing", user_text=body.intent,
    )
    out = await _run_framing(rec, cluster, account["id"], solve_turn_id, transcript="")
    audits = [ref["audit_entry"]] + out["audit_entries"]

    solve_turn = {
        "id": solve_turn_id,
        "role": "solva",
        "layer": "framing",
        "text": out["text"],
        "model": out["model"],
        "tier": out["tier"],
        "created_at": iso(now()),
    }
    await db.solva_v2_sessions.update_one(
        {"id": session_id},
        {"$push": {
            "turns": solve_turn,
            "reasoning_audit_log": {"$each": audits},
        },
         "$set": {"updated_at": iso(now())}},
    )
    rec["turns"].append(solve_turn)
    rec["reasoning_audit_log"].extend(audits)
    rec.pop("_id", None)
    return rec


@router.get("/sessions")
async def list_sessions(
    status: Optional[str] = None,
    account: Dict[str, Any] = Depends(require_solva_v2_flag),
):
    q: Dict[str, Any] = {"account_id": account["id"], "version": 2}
    if status:
        q["status"] = status
    rows = await db.solva_v2_sessions.find(
        q,
        {"_id": 0, "id": 1, "cluster_id": 1, "cluster_label": 1, "intent": 1,
         "layer": 1, "layer_index": 1, "status": 1, "submodule": 1,
         "started_at": 1, "updated_at": 1, "completed_at": 1},
    ).sort("updated_at", -1).to_list(length=100)
    return {"items": rows, "count": len(rows)}


@router.get("/sessions/{sid}")
async def get_session(
    sid: str,
    account: Dict[str, Any] = Depends(require_solva_v2_flag),
):
    rec = await db.solva_v2_sessions.find_one(
        {"id": sid, "account_id": account["id"]}, {"_id": 0}
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Session not found.")
    return rec


@router.get("/sessions/{sid}/reasoning-log")
async def get_reasoning_log(
    sid: str,
    account: Dict[str, Any] = Depends(require_solva_v2_flag),
):
    rec = await db.solva_v2_sessions.find_one(
        {"id": sid, "account_id": account["id"]},
        {"_id": 0, "id": 1, "layer": 1, "status": 1, "reasoning_audit_log": 1},
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Session not found.")
    return {
        "session_id": rec["id"],
        "current_layer": rec.get("layer"),
        "status": rec.get("status"),
        "entry_count": len(rec.get("reasoning_audit_log") or []),
        "entries": rec.get("reasoning_audit_log") or [],
    }


@router.post("/sessions/{sid}/abandon")
async def abandon_session(
    sid: str,
    account: Dict[str, Any] = Depends(require_solva_v2_flag),
):
    rec = await db.solva_v2_sessions.find_one(
        {"id": sid, "account_id": account["id"]}, {"_id": 0, "id": 1}
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Session not found.")
    await db.solva_v2_sessions.update_one(
        {"id": sid, "account_id": account["id"]},
        {"$set": {"status": "abandoned", "updated_at": iso(now())}},
    )
    return {"ok": True}


@router.post("/sessions/{sid}/turn")
async def post_turn(
    sid: str,
    body: TurnV2In,
    account: Dict[str, Any] = Depends(require_solva_v2_flag),
):
    rec = await db.solva_v2_sessions.find_one(
        {"id": sid, "account_id": account["id"]}, {"_id": 0}
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Session not found.")
    if rec.get("status") != "active":
        raise HTTPException(status_code=409, detail=f"Session is {rec['status']}.")

    cluster = await db.solve_clusters.find_one({"id": rec["cluster_id"]}, {"_id": 0})
    if not cluster:
        raise HTTPException(status_code=410, detail="Cluster has been removed.")

    current_layer = rec["layer"]
    user_turn_id = str(uuid.uuid4())

    # User turn persisted FIRST so audit entries can FK back to it.
    user_turn = {
        "id": user_turn_id,
        "role": "user",
        "layer": current_layer,
        "text": body.user_text.strip(),
        "model": None,
        "tier": None,
        "created_at": iso(now()),
    }
    await db.solva_v2_sessions.update_one(
        {"id": sid},
        {"$push": {"turns": user_turn}, "$set": {"updated_at": iso(now())}},
    )
    rec["turns"].append(user_turn)

    # Refusal stub at every turn boundary
    ref = await refusal.run(
        session=rec, turn_id=user_turn_id, layer=current_layer,
        user_text=body.user_text,
    )
    all_audits: List[Dict[str, Any]] = [ref["audit_entry"]]

    # Build transcript once
    transcript_lines = []
    for t in rec.get("turns", []):
        prefix = "User" if t["role"] == "user" else "Solva"
        transcript_lines.append(f"{prefix} ({t.get('layer','?')}): {t.get('text','')}")
    transcript = "\n".join(transcript_lines)

    solve_turn_id = str(uuid.uuid4())
    update_fields: Dict[str, Any] = {"updated_at": iso(now())}
    solve_text = ""
    solve_model: Optional[str] = None
    solve_tier: Optional[str] = None
    grounding_violation_payload: Optional[Dict[str, Any]] = None

    if current_layer == "framing":
        # Advance from framing -> grounding happens here: we generate the
        # grounding summary (engines run) and that becomes the Solva turn.
        # Note: framing layer ALREADY had a primed reply at session start; the
        # first user turn at `framing` layer triggers grounding engines.
        out = await _run_grounding(rec, cluster, account["id"], solve_turn_id)
        all_audits.extend(out["audit_entries"])
        solve_text = out["text"]
        # Park comparables + candidates in temp field for synthesis use
        rec["_grounding_comparables"] = out["comparables"]
        rec["_grounding_candidates"] = out["candidates"]
        update_fields["_grounding_comparables"] = out["comparables"]
        update_fields["_grounding_candidates"] = out["candidates"]

    elif current_layer == "grounding":
        # User gave feedback on grounding; proceed to synthesis.
        tier_req = "deep" if rec.get("pro_tier") and rec.get("pro_account") else "standard"
        comparables = rec.get("_grounding_comparables") or []
        candidates = rec.get("_grounding_candidates") or []
        out = await _run_synthesis(
            rec, cluster, account["id"], solve_turn_id, transcript,
            comparables=comparables, candidates=candidates, requested_tier=tier_req,
        )
        all_audits.extend(out["audit_entries"])
        if out.get("grounding_violation"):
            # Persist audit entries (even on failure) and the user turn; then
            # surface a structured 422.
            await _append_audit(sid, all_audits)
            logger.warning(
                "solva_v2 grounding contract violation sid=%s account=%s",
                sid, account["id"],
            )
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "grounding_contract_violation",
                    "message": "Model failed grounding contract after 3 attempts.",
                    "untagged_sentences": out.get("untagged_sentences", []),
                    "malformed_markers": out.get("malformed_markers", []),
                },
            )
        # Persist synthesis record + advance pointer
        synthesis_record = {
            "body": out["text"],  # raw body with inline markers preserved
            "stripped_text": out["stripped_text"],
            "claims": out["claims"],
            "tier_distribution": out["tier_distribution"],
            "model": out["model"],
            "tier": out["tier"],
            "generated_at": iso(now()),
            "validation": out["validation"],
        }
        update_fields["synthesis"] = synthesis_record
        rec["synthesis"] = synthesis_record
        solve_text = out["text"]
        solve_model = out["model"]
        solve_tier = out["tier"]

    elif current_layer == "synthesis":
        # User gave feedback on synthesis; reflection is terminal in 15.0
        # (Phase 15.3 turns this into a three-question exchange). Emit the
        # placeholder and flip to completed in the same write so the client
        # need not post a no-op turn to close.
        out = await _run_reflection(rec, solve_turn_id)
        all_audits.extend(out["audit_entries"])
        solve_text = out["text"]
        lockin_record = {
            "body": out["text"],
            "model": out["model"],
            "tier": out["tier"],
            "generated_at": iso(now()),
            "placeholder": True,
        }
        update_fields["lockin"] = lockin_record
        update_fields["status"] = "completed"
        update_fields["completed_at"] = iso(now())
        update_fields["layer"] = "reflection"
        update_fields["layer_index"] = LAYERS.index("reflection")
        rec["lockin"] = lockin_record
        rec["status"] = "completed"
        rec["layer"] = "reflection"
        rec["layer_index"] = update_fields["layer_index"]

    elif current_layer == "reflection":
        # No further layer — this should not be reachable on an active session.
        raise HTTPException(status_code=409, detail="Session is at Reflection — no further turns.")

    # Advance layer pointer (skip for synthesis which already set completed)
    if current_layer not in ("synthesis", "reflection"):
        advance_to = _next_layer(current_layer)
        if advance_to is None:
            update_fields["status"] = "completed"
            update_fields["completed_at"] = iso(now())
            rec["status"] = "completed"
        else:
            update_fields["layer"] = advance_to
            update_fields["layer_index"] = LAYERS.index(advance_to)
            rec["layer"] = advance_to
            rec["layer_index"] = update_fields["layer_index"]

    # Persist the Solva turn + audit log + state updates atomically.
    solve_turn = {
        "id": solve_turn_id,
        "role": "solva",
        "layer": current_layer,
        "text": solve_text or "(empty)",
        "model": solve_model,
        "tier": solve_tier,
        "created_at": iso(now()),
    }
    rec["turns"].append(solve_turn)
    rec["reasoning_audit_log"] = (rec.get("reasoning_audit_log") or []) + all_audits
    await db.solva_v2_sessions.update_one(
        {"id": sid, "account_id": account["id"]},
        {"$push": {
            "turns": solve_turn,
            "reasoning_audit_log": {"$each": all_audits},
        },
         "$set": update_fields},
    )
    rec.pop("_id", None)
    return rec


# -----------------------------------------------------------------------------
# Admin endpoint (superadmin-only) — flip the POC flag on an account by email.
# -----------------------------------------------------------------------------
class FlagFlipIn(BaseModel):
    email: str = Field(min_length=3, max_length=240)
    enabled: bool = True


admin_router = APIRouter(prefix="/api/admin/solva-v2", tags=["solva_v2_admin"])


@admin_router.post("/flag")
async def flip_flag(
    body: FlagFlipIn,
    account: Dict[str, Any] = Depends(get_current_account),
):
    if not account.get("is_superadmin"):
        raise HTTPException(status_code=403, detail="Superadmin required.")
    target = await db.accounts.find_one(
        {"email": body.email.lower().strip()}, {"_id": 0, "id": 1, "email": 1}
    )
    if not target:
        raise HTTPException(status_code=404, detail="Account not found.")
    await db.accounts.update_one(
        {"id": target["id"]},
        {"$set": {"solva_v2_poc": bool(body.enabled)}},
    )
    return {"ok": True, "email": target["email"], "solva_v2_poc": bool(body.enabled)}


@admin_router.get("/flag")
async def read_flag(
    email: str,
    account: Dict[str, Any] = Depends(get_current_account),
):
    if not account.get("is_superadmin"):
        raise HTTPException(status_code=403, detail="Superadmin required.")
    target = await db.accounts.find_one(
        {"email": email.lower().strip()}, {"_id": 0, "email": 1, "solva_v2_poc": 1}
    )
    if not target:
        raise HTTPException(status_code=404, detail="Account not found.")
    return {
        "email": target["email"],
        "solva_v2_poc": bool(target.get("solva_v2_poc", False)),
    }
