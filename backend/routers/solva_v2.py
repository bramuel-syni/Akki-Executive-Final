"""Solva v2 orchestrator (Phase 15.1).

Seek Clarity sub-module. Layer flow: framing -> grounding -> synthesis ->
reflection, governed by services/solva_v2/state_machine.py.

15.1 lifts the scaffolding into the production orchestration tier:
  - All four reasoning engines are real (candidate_generation, triangulation,
    probability_weighting, refusal). Stubs are gone.
  - Each engine call is shielded under its own sub-surface
    (`solve_v2.<engine>`) so the perf ring buffer and the admin LLM spend
    dashboard can attribute latency and spend per engine.
  - Validator gets a fresh Synisense pass on its input under
    `solve_v2.validator` (closes hardening friction item 2).
  - Probability weighting runs between synthesis and validator and writes
    confidence_pct + confidence_band onto every claim.
  - Cycle handoff routes through Daily Review (`solva_cycle_action` queue
    items) instead of v1's direct write into db.questions.
  - New sessions carry schema_version=2; old POC sessions remain readable
    via the same GET handler.

Out of scope for 15.1 (delivered later per docs/ROADMAP.md):
  - Sub-module picker / 4-tile intake               Phase 15.2
  - Other three sub-modules                         Phase 15.2
  - Tension detector                                Phase 15.2
  - Refusal ladder thresholds / therapy redirect    Phase 15.3
  - Layer 4 Reflection three locked questions      Phase 15.3
  - Citation chips / probability interval polish    Phase 15.3
"""
from __future__ import annotations

import json
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
    LAYERS,
    next_layer,
    assert_can_post_turn,
    InvalidLayerTransition,
    TERMINAL_LAYER,
    record_retry,
    validator_call,
    shielded_call,
    synthetic_audit_entry,
)
from services.solva_v2.grounding_contract import GROUNDING_RETRY_PROMPT, TIER_NAMES
from services.solva_v2.engines import (
    triangulation,
    candidate_generation,
    probability_weighting,
    refusal,
    tension_detector,
    reflection,
)
from services.solva_v2.engines.tension_detector import CrossSessionTensionInputError
from services.solva_v2 import guardrails
from services.solva_v2.submodules import (
    SUBMODULE_NAMES,
    voice_for as submodule_voice_for,
    parse_recommendations_from_synthesis,
    expects_recommendations,
    expects_hypothesis_layer,
    expects_persona_at_intake,
)

logger = logging.getLogger("akki.solva_v2")

router = APIRouter(prefix="/api/solva/v2", tags=["solva_v2"])


# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------
# Phase 15.2: 4 sub-modules now ship. Backwards-compat default at read time
# remains 'seek_clarity' for any session row written before 15.2.
SUBMODULES = list(SUBMODULE_NAMES)
MAX_GROUNDING_RETRIES = 2  # => 3 total attempts on synthesis
SCHEMA_VERSION = 2  # 15.1+ sessions carry this; 15.0 sessions implicitly 1
SYNTHESIS_SURFACE = "solve_v2.synthesis"
HYPOTHESIS_SURFACE = "solve_v2.hypothesis"

# Phase 15.3 — session limits (decision #11)
MAX_TURNS_PER_SESSION = 20             # user turns; hard 422 once reached
MAX_CONCURRENT_ACTIVE = 3              # active+blocked_hard sessions per account at create
STALE_SESSION_AGE_DAYS = 30            # cron auto-abandons after this


# -----------------------------------------------------------------------------
# Pydantic
# -----------------------------------------------------------------------------
class StartV2In(BaseModel):
    cluster_id: str = Field(min_length=2, max_length=80)
    intent: str = Field(min_length=20, max_length=1200)
    context_id: Optional[str] = None
    submodule: str = Field(default="seek_clarity")
    persona: Optional[str] = Field(default=None, max_length=200)  # Phase 15.2 — Get Perspective
    pro_tier: bool = False


class TurnV2In(BaseModel):
    user_text: str = Field(min_length=2, max_length=4000)


class ForkV2In(BaseModel):
    """Phase 15.2 — fork an in-flight or completed session into a new session
    under a different sub-module. The new session inherits intent + accumulated
    user turns + key claims, sets parent_session_id, and starts at framing."""
    to_submodule: str = Field(min_length=4, max_length=40)
    persona: Optional[str] = Field(default=None, max_length=200)


class IntentClassifyIn(BaseModel):
    """Phase 15.2 — single tier=fast LLM classification of the user's intent
    into one of the 4 sub-modules. Fronts the picker's suggestion chip."""
    intent: str = Field(min_length=20, max_length=1200)


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


def _base_system_prompt(
    cluster: Dict[str, Any],
    layer: str,
    intent: str,
    submodule: str = "seek_clarity",
    persona: Optional[str] = None,
    tensions: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Build the system prompt for a (submodule, layer) pair.

    Phase 15.2: voice header dispatched through services.solva_v2.submodules
    so each sub-module gets its own framing/synthesis voice. The cluster
    hint, banned terms, and current-layer block are unchanged across
    sub-modules. Tensions (when present) are injected into synthesis
    prompts so the LLM acknowledges them in its diagnosis.
    """
    hint = (cluster.get("phase_hints") or {}).get(
        # Map v2 layer names to v1 phase_hint keys for continuity.
        # `hypothesis` is a 15.2-only layer with no v1 analogue; reuse depth.
        {"framing": "surface", "grounding": "depth", "hypothesis": "depth",
         "synthesis": "synthesis", "reflection": "lockin"}.get(layer, "surface"),
        "",
    )
    banned = (cluster.get("banned_terms") or [])
    banned_block = ", ".join(banned) if banned else "(none specified)"

    voice = submodule_voice_for(submodule, layer, persona=persona)

    tensions_block = ""
    if tensions:
        sev_order = {"high": 0, "medium": 1, "low": 2}
        sorted_t = sorted(tensions, key=lambda t: sev_order.get(t.get("severity", "low"), 9))
        lines = "\n".join(
            f"  - [{t.get('severity', 'medium').upper()} | "
            f"{t.get('contradiction_source', 'unknown')}] {t.get('description', '')}"
            for t in sorted_t[:5]
        )
        tensions_block = (
            "\n\nDETECTED TENSIONS (from the hypothesis layer; acknowledge "
            "explicitly in your diagnosis where they bear on the conclusion):\n"
            + lines
        )

    return (
        voice + "\n\n"
        f"CURRENT LAYER: {layer.upper()}.\n"
        f"LAYER INSTRUCTION: {hint}\n"
        f"USER INTENT: {intent}\n"
        f"CLUSTER: {cluster.get('label')}\n"
        f"BANNED TERMS (never use): {banned_block}\n"
        + tensions_block
        + "\n\nTONE: Calm, editorial. Serif voice if you were speaking. No marketing "
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
    """Run triangulation (real, deterministic) + candidate_generation (real LLM).

    Returns either {violation: False, ...} on success or {violation: True, ...}
    if candidate_generation could not satisfy its validator after one retry.
    """
    sector_tag: Optional[str] = None
    ctx_id = session.get("context_id")
    if ctx_id:
        ctx_doc = await db.contexts.find_one(
            {"id": ctx_id}, {"_id": 0, "sector": 1, "industry": 1}
        )
        if ctx_doc:
            sector_tag = (ctx_doc.get("sector") or ctx_doc.get("industry") or "").lower() or None

    audit_entries: List[Dict[str, Any]] = []

    tri = await triangulation.run(
        session=session, turn_id=turn_id, layer="grounding",
        cluster_id=cluster["id"], sector_tag=sector_tag, limit=3,
    )
    audit_entries.append(tri["audit_entry"])

    cands = await candidate_generation.run(
        session=session, turn_id=turn_id, layer="grounding",
        intent=session["intent"], cluster=cluster,
        comparables=tri["output"]["comparables"],
    )
    audit_entries.extend(cands["audit_entries"])
    # Record retry events for the admin dashboard.
    if len(cands["audit_entries"]) > 1:
        for _ in range(len(cands["audit_entries"]) - 1):
            await record_retry(
                surface="solve_v2.candidate_generation",
                account_id=account_id,
                reason="validator_rejected",
            )

    if cands.get("violation"):
        return {
            "violation": True,
            "reason": cands.get("reason", "candidate_generation_failed"),
            "audit_entries": audit_entries,
        }

    candidates = cands["output"]["candidates"]
    summary_text = (
        f"Grounding picked {tri['output']['comparable_count']} comparables "
        f"(cluster={cluster['id']}, sector={sector_tag or 'any'}) and "
        f"{len(candidates)} candidate framing(s). Proceeding to Synthesis."
    )
    return {
        "violation": False,
        "text": summary_text,
        "model": None,
        "tier": None,
        "comparables": tri["output"]["comparables"],
        "comparable_empty_reason": tri["output"].get("empty_reason"),
        "candidates": candidates,
        "audit_entries": audit_entries,
    }


async def _run_hypothesis(
    session: Dict[str, Any],
    cluster: Dict[str, Any],
    account_id: str,
    turn_id: str,
    user_turns: List[Dict[str, Any]],
    triangulation_output: Dict[str, Any],
    candidates: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Phase 15.2 — Simulate Hypothesis hypothesis-layer step.

    Single engine: tension_detector. Single-session by hard contract — the
    detector asserts inputs share session_id (decision #7). If zero
    tensions are detected the audit entry still lands with `tensions: []`
    and synthesis proceeds normally.

    Returns:
      {
        "text": str   — Solva-side reply summarising tensions
        "tensions": list — passes through to synthesis prompt
        "audit_entries": list
      }
    """
    audit_entries: List[Dict[str, Any]] = []
    try:
        td = await tension_detector.run(
            session=session,
            turn_id=turn_id,
            user_turns=user_turns,
            triangulation_output=triangulation_output,
            candidate_hypotheses=candidates,
        )
    except CrossSessionTensionInputError as exc:
        # This must NEVER happen in production — the orchestrator only ever
        # passes single-session inputs. Surface as 500 with an audit entry
        # so the breach is visible.
        logger.error(
            "tension_detector cross-session breach sid=%s: %s",
            session["id"], exc,
        )
        raise HTTPException(
            status_code=500,
            detail={"error": "tension_detector_cross_session_breach", "message": str(exc)},
        ) from exc
    audit_entries.append(td["audit_entry"])
    tensions = td["output"]["tensions"]

    if tensions:
        # Build a one-sentence Solva turn that names the top tension.
        bullet_lines = "\n".join(
            f"  \u2022 [{t.get('severity','medium').upper()} | "
            f"{t.get('contradiction_source')}] {t.get('description')}"
            for t in tensions[:3]
        )
        summary_text = (
            f"Detected {len(tensions)} tension(s) between the candidate "
            f"hypotheses and the established grounding. Most material:\n"
            f"{bullet_lines}\n\n"
            "Confirm I should weigh these explicitly when I synthesise the "
            "diagnosis, or correct any I have miscast."
        )
    else:
        summary_text = (
            "No material tensions detected between the candidate hypotheses "
            "and the established grounding. Proceeding to Synthesis."
        )
    return {
        "text": summary_text,
        "tensions": tensions,
        "audit_entries": audit_entries,
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
    submodule: str = "seek_clarity",
    persona: Optional[str] = None,
    tensions: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Synthesis runs the LLM (sub-surface solve_v2.synthesis), enforces the
    grounding contract via retry loop, runs probability_weighting on the
    parsed claims, and runs the independent-family validator with its OWN
    fresh Synisense pass under sub-surface solve_v2.validator.

    Phase 15.2: submodule + persona + tensions are passed to the system
    prompt. develop_strategy post-processes the LLM body to extract a
    `recommendations[]` array. simulate_hypothesis injects the tension
    detector's findings into the synthesis prompt so the LLM acknowledges
    them.
    """
    audit_entries: List[Dict[str, Any]] = []

    # Build system prompt: base + format + comparables + candidate framings + grounding contract
    comparable_block = triangulation.format_for_prompt(comparables)
    candidate_block = ""
    if candidates:
        cand_lines = "\n".join(
            f"  - [{c.get('tentative_tier_hint','?')}] {c.get('hypothesis','')}"
            for c in candidates if isinstance(c, dict)
        )
        candidate_block = (
            "\n\nCANDIDATE FRAMINGS (from the Grounding layer; weigh before "
            "writing the diagnosis. The tier hint indicates where each "
            "framing's grounding is expected to come from.):\n" + cand_lines
        )

    system_base = _base_system_prompt(
        cluster, "synthesis", session["intent"],
        submodule=submodule, persona=persona, tensions=tensions,
    ) + (
        "\n\nOUTPUT FORMAT: 250\u2013350 words. One orientation sentence. "
        "Two short analysis paragraphs. One closing diagnosis sentence. "
        "If you reference comparable diagnoses, name them inline."
    )
    if expects_recommendations(submodule):
        system_base += (
            "\n\nADDITIONAL OUTPUT (Develop Strategy): after the diagnosis "
            "paragraphs, write 2\u20134 numbered recommendations on their own "
            "lines, each starting with 'Recommendation N:' followed by a "
            "single-sentence concrete action with its tier marker. Each "
            "recommendation must be testable and timeline-bounded."
        )
    system_msg = system_base + candidate_block + comparable_block + GROUNDING_CONTRACT_PROMPT

    base_user_query = (
        f"Conversation so far:\n{transcript or '(no prior turns)'}\n\n"
        "Generate the SYNTHESIS layer response now. Follow the OUTPUT FORMAT "
        "exactly, and tag every assertive sentence with exactly one tier marker."
    )

    # Iterative grounding-contract enforcement loop
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
            surface=SYNTHESIS_SURFACE,  # Phase 15.1: solve_v2.synthesis
            account_id=account_id,
            session_id=session["id"],
            context_id=session.get("context_id"),
            run_validator=False,  # validator runs once on the ACCEPTED body via validator_call
            extra_output={"grounding_attempt": attempt + 1},
        )
        audit_entries.append(result.reasoning_audit_entry)
        parse_res = parse(result.text)
        last_result = result
        last_parse = parse_res
        if parse_res.valid:
            audit_entries[-1]["tier_labels"] = sorted({c.tier for c in parse_res.claims})
            audit_entries[-1]["output"]["grounding_accepted"] = True
            audit_entries[-1]["output"]["claim_count"] = len(parse_res.claims)
            break
        audit_entries[-1]["output"]["grounding_accepted"] = False
        audit_entries[-1]["output"]["untagged_count"] = len(parse_res.untagged_sentences)
        audit_entries[-1]["output"]["malformed_count"] = len(parse_res.malformed_markers)
        # Record retry
        await record_retry(
            surface=SYNTHESIS_SURFACE,
            account_id=account_id,
            reason="grounding_contract_violation",
        )
        retry_body = GROUNDING_RETRY_PROMPT.format(
            untagged=parse_res.untagged_sentences[:5],
            malformed=[m.get("bad_tier") for m in parse_res.malformed_markers[:5]],
            valid_tiers=TIER_NAMES,
        )
        current_user_query = base_user_query + retry_body

    if not last_parse or not last_parse.valid:
        return {
            "grounding_violation": True,
            "audit_entries": audit_entries,
            "untagged_sentences": last_parse.untagged_sentences if last_parse else [],
            "malformed_markers": last_parse.malformed_markers if last_parse else [],
            "raw_text": last_result.text if last_result else "",
        }

    # Phase 15.1: probability_weighting is a REAL engine that assigns
    # confidence_pct + confidence_band to every claim before the validator.
    raw_claims = [c.to_dict() for c in last_parse.claims]
    pw = await probability_weighting.run(
        session=session, turn_id=turn_id, layer="synthesis",
        claims=raw_claims, comparables=comparables,
    )
    audit_entries.extend(pw["audit_entries"])
    if not pw["output"].get("invariant_valid", False) and len(pw["audit_entries"]) > 1:
        await record_retry(
            surface="solve_v2.probability_weighting",
            account_id=account_id,
            reason="invariant_violation",
        )
    weighted_claims = pw["output"]["claims"]
    pw_violations = pw["output"]["violations"]

    # Phase 15.1: validator_call runs FRESH Synisense pass under
    # sub-surface solve_v2.validator. No more upstream run_id reuse.
    val = await validator_call(
        content=last_parse.stripped_text,
        objective=session.get("intent"),
        layer="synthesis",
        turn_id=turn_id,
        account_id=account_id,
        context_id=session.get("context_id"),
    )
    validation = val["validation"]
    audit_entries.append(val["audit_entry"])

    # Phase 15.2 — develop_strategy post-processing: pull recommendations[]
    # out of the synthesis body. The recommendations are TEXT only; their
    # confidence bands come from the per-claim probability_weighting pass
    # (each numbered recommendation is itself a claim with a tier marker).
    recommendations: List[Dict[str, Any]] = []
    if expects_recommendations(submodule):
        recommendations = parse_recommendations_from_synthesis(last_result.text or "")

    return {
        "grounding_violation": False,
        "text": last_result.text,
        "stripped_text": last_parse.stripped_text,
        "claims": weighted_claims,  # carries confidence_pct / confidence_band
        "tier_distribution": summarise_tier_distribution(last_parse.claims),
        "probability_weighting_violations": pw_violations,
        "model": last_result.model,
        "tier": last_result.tier_served,
        "validation": validation,
        "audit_entries": audit_entries,
        "recommendations": recommendations,  # Phase 15.2 — develop_strategy
    }


async def _run_reflection(
    session: Dict[str, Any],
    turn_id: str,
    account_id: str,
) -> Dict[str, Any]:
    """Phase 15.3 — Layer 4 Reflection.

    Three locked questions (LOCKED_QUESTIONS), each answered by a
    shielded LLM call at sub-surface `solve_v2.reflection`, tier=fast.
    Each response is tier-marked per the grounding contract and emitted
    as its own audit entry under engine='reflection'. The session's
    `reflection` field is populated with the question/answer triplet.
    """
    intent = (session.get("intent") or "").strip()
    synthesis_body = ((session.get("synthesis") or {}).get("body") or "").strip()
    out = await reflection.run(
        session=session,
        turn_id=turn_id,
        intent=intent,
        synthesis_body=synthesis_body,
        account_id=account_id,
    )
    return {
        "text": out["body"],
        "model": out["model"],
        "tier": out["tier"],
        "audit_entries": out["audit_entries"],
        "responses": out["responses"],
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
            detail=f"Unknown submodule. Supported: {SUBMODULES}.",
        )
    if expects_persona_at_intake(body.submodule) and not (body.persona or "").strip():
        raise HTTPException(
            status_code=422,
            detail=(
                "submodule 'get_perspective' requires a persona at intake "
                "(Chair / fellow NED / Investor / Regulator / Auditor / "
                "free text)."
            ),
        )
    cluster = await db.solve_clusters.find_one({"id": body.cluster_id}, {"_id": 0})
    if not cluster:
        raise HTTPException(status_code=404, detail="Unknown cluster.")

    # Phase 15.3 — concurrent active session limit (decision #11).
    active_count = await db.solva_v2_sessions.count_documents(
        {"account_id": account["id"], "status": "active"},
    )
    if active_count >= MAX_CONCURRENT_ACTIVE:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "too_many_active_sessions",
                "message": (
                    "Too many active Solva v2 sessions. Abandon one before "
                    "starting another."
                ),
                "limit": MAX_CONCURRENT_ACTIVE,
                "active_count": active_count,
            },
        )

    session_id = str(uuid.uuid4())
    is_pro_account = await _is_pro(account)
    rec = {
        "id": session_id,
        "account_id": account["id"],
        "context_id": body.context_id,
        "version": 2,
        "schema_version": SCHEMA_VERSION,
        "submodule": body.submodule,  # Phase 15.2 — persisted
        "persona": (body.persona or "").strip() or None,  # 15.2 get_perspective
        "parent_session_id": None,  # 15.2 — set when session is forked
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
        "reflection": None,             # Phase 15.3 — three-question record
        "lockin": None,
        "jailbreak_soft_count": 0,      # Phase 15.3 — refusal ladder counter
        "started_at": iso(now()),
        "updated_at": iso(now()),
        "completed_at": None,
    }
    await db.solva_v2_sessions.insert_one(rec)

    # Prime framing turn immediately (mirrors v1 posture)
    solve_turn_id = str(uuid.uuid4())
    # Refusal classifier (real LLM call in 15.1) at turn boundary.
    # Phase 15.3: also runs the guardrail ladder. If the intent itself
    # triggers therapy_redirect / soft_block / hard_block, we do NOT prime
    # the framing layer — we return the locked guardrail message instead.
    ref = await refusal.run(
        session=rec, turn_id=solve_turn_id, layer="framing", user_text=body.intent,
    )
    decision = guardrails.evaluate(session=rec, refusal_output=ref["output"])
    if decision.action != "continue":
        guard_audit = await synthetic_audit_entry(
            engine=guardrails.ENGINE,
            engine_version=guardrails.ENGINE_VERSION,
            layer="framing",
            turn_id=solve_turn_id,
            output=decision.audit_output,
            tier_labels=[],
            shield_required=False,
            shield_bypassed_reason="deterministic_only",
            latency_ms=0,
        )
        guard_solve_turn = {
            "id": solve_turn_id,
            "role": "solva",
            "layer": "framing",
            "text": decision.user_visible_message,
            "model": None,
            "tier": None,
            "guardrail_action": decision.action,
            "learn_link": decision.learn_link,
            "created_at": iso(now()),
        }
        guard_update: Dict[str, Any] = {"updated_at": iso(now())}
        if decision.increment_soft_count:
            guard_update["jailbreak_soft_count"] = 1
        if decision.new_status:
            guard_update["status"] = decision.new_status
            guard_update["blocked_at"] = iso(now())
        await db.solva_v2_sessions.update_one(
            {"id": session_id},
            {"$push": {
                "turns": guard_solve_turn,
                "reasoning_audit_log": {"$each": [ref["audit_entry"], guard_audit]},
            },
             "$set": guard_update},
        )
        rec["turns"].append(guard_solve_turn)
        rec["reasoning_audit_log"].extend([ref["audit_entry"], guard_audit])
        if decision.increment_soft_count:
            rec["jailbreak_soft_count"] = 1
        if decision.new_status:
            rec["status"] = decision.new_status
        rec.pop("_id", None)
        return rec

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
    # Phase 15.2 — backwards compat: sessions written before 15.2 may not
    # carry submodule. Default at read time so the client never has to handle
    # a null submodule field.
    if not rec.get("submodule"):
        rec["submodule"] = "seek_clarity"
    return rec


@router.post("/sessions/{sid}/fork")
async def fork_session(
    sid: str,
    body: ForkV2In,
    account: Dict[str, Any] = Depends(require_solva_v2_flag),
):
    """Phase 15.2 — fork a session into a new sub-module.

    Inherits intent + accumulated user turns from the parent. Sets
    parent_session_id on the child so the lineage is auditable. Starts at
    framing layer with status=active. Does NOT abandon the parent — the
    user can keep walking the parent if they want to.
    """
    parent = await db.solva_v2_sessions.find_one(
        {"id": sid, "account_id": account["id"]}, {"_id": 0}
    )
    if not parent:
        raise HTTPException(status_code=404, detail="Parent session not found.")
    target = (body.to_submodule or "").strip()
    if target not in SUBMODULES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown to_submodule. Supported: {SUBMODULES}.",
        )
    if expects_persona_at_intake(target) and not (body.persona or "").strip():
        raise HTTPException(
            status_code=422,
            detail=(
                "Forking into 'get_perspective' requires a persona. Send "
                "{'to_submodule': 'get_perspective', 'persona': '<...>'}."
            ),
        )

    cluster = await db.solve_clusters.find_one(
        {"id": parent.get("cluster_id")}, {"_id": 0},
    )
    if not cluster:
        raise HTTPException(status_code=409, detail="Parent cluster not found.")

    new_id = str(uuid.uuid4())
    is_pro_account = await _is_pro(account)
    inherited_user_turns = [
        {**t, "id": str(uuid.uuid4())} for t in (parent.get("turns") or [])
        if t.get("role") == "user"
    ]
    rec = {
        "id": new_id,
        "account_id": account["id"],
        "context_id": parent.get("context_id"),
        "version": 2,
        "schema_version": SCHEMA_VERSION,
        "submodule": target,
        "persona": (body.persona or "").strip() or None,
        "parent_session_id": parent["id"],
        "cluster_id": parent["cluster_id"],
        "cluster_label": parent.get("cluster_label"),
        "intent": parent["intent"],
        "layer": LAYERS[0],
        "layer_index": 0,
        "status": "active",
        "pro_tier": parent.get("pro_tier", False),
        "pro_account": is_pro_account,
        "turns": inherited_user_turns,
        "reasoning_audit_log": [],
        "synthesis": None,
        "lockin": None,
        "started_at": iso(now()),
        "updated_at": iso(now()),
        "completed_at": None,
        "fork_metadata": {
            "parent_submodule": parent.get("submodule") or "seek_clarity",
            "inherited_turn_count": len(inherited_user_turns),
            "parent_status_at_fork": parent.get("status"),
        },
    }
    await db.solva_v2_sessions.insert_one(rec)
    rec.pop("_id", None)
    return rec


@router.post("/intent/classify")
async def classify_intent(
    body: IntentClassifyIn,
    account: Dict[str, Any] = Depends(require_solva_v2_flag),
):
    """Phase 15.2 — soft-suggest the most-fitting sub-module for a user's
    intent. Single tier=fast LLM call. Returns
        {submodule: <one of 4>, confidence: 0.0-1.0, reason: str}
    Front-end shows the chip when confidence >= 0.6 and hides otherwise.
    """
    from llm_tier_quota import call_llm_with_tier

    sys = (
        "You are a 4-way classifier for AKKI Solva sub-modules. Read the "
        "user's intent and pick the BEST sub-module. Output strict JSON.\n\n"
        "Sub-modules:\n"
        "  - seek_clarity        : the user wants to UNDERSTAND a problem; "
        "diagnose first, before deciding what to do.\n"
        "  - develop_strategy    : the user wants to DECIDE what to do; "
        "they're past diagnosis and want a recommendation.\n"
        "  - simulate_hypothesis : the user is asking a 'what-if?'; they want "
        "to explore scenarios for an unsettled question.\n"
        "  - get_perspective     : the user wants to know what a specific "
        "STAKEHOLDER (chair / NED / investor / regulator / auditor) would think.\n\n"
        "Output JSON: {\"submodule\": \"<name>\", \"confidence\": <0.0-1.0>, "
        "\"reason\": \"<one sentence>\"}. "
        "Confidence is your subjective sureness. Below 0.6, the front-end "
        "hides the suggestion entirely \u2014 default to 0.5 if unsure."
    )
    try:
        llm_resp, _meta = await call_llm_with_tier(
            surface="solve_v2.intent_classify",
            account_id=account["id"],
            requested_tier="fast",
            call_args={
                "module": "solve_v2.intent_classify",
                "user_query": f"Intent:\n{body.intent.strip()}",
                "system_override": sys,
                "response_format": "json",
            },
        )
        raw = (llm_resp or {}).get("response") or ""
    except Exception as exc:  # noqa: BLE001
        logger.warning("intent_classify llm failure: %s", exc)
        return {"submodule": "seek_clarity", "confidence": 0.0,
                "reason": "classifier unavailable; defaulting to seek_clarity",
                "error": str(exc)[:200]}

    import re as _re
    m = _re.search(r"\{.*\}", raw, _re.DOTALL)
    if not m:
        return {"submodule": "seek_clarity", "confidence": 0.0,
                "reason": "classifier returned no parseable JSON"}
    try:
        parsed = json.loads(m.group(0))
    except Exception:  # noqa: BLE001
        return {"submodule": "seek_clarity", "confidence": 0.0,
                "reason": "classifier JSON parse failed"}
    submod = parsed.get("submodule") or "seek_clarity"
    if submod not in SUBMODULES:
        submod = "seek_clarity"
    try:
        conf = float(parsed.get("confidence") or 0.0)
    except Exception:  # noqa: BLE001
        conf = 0.0
    conf = max(0.0, min(1.0, conf))
    return {
        "submodule": submod,
        "confidence": conf,
        "reason": (parsed.get("reason") or "").strip()[:240],
    }


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


# -----------------------------------------------------------------------------
# Phase 15.3 — stale-session cron. APScheduler hits this daily at 04:00 UTC.
# Marks active sessions with updated_at older than STALE_SESSION_AGE_DAYS as
# abandoned, with a recorded `abandoned_reason="stale_30d"`. Intended to be
# idempotent — running twice in the same day produces the same DB state.
# -----------------------------------------------------------------------------
from fastapi import Header  # noqa: E402  (used only here for cron-secret header)


@router.post("/cron/stale-session-sweep")
async def stale_session_sweep(
    x_cron_secret: Optional[str] = Header(default=None, alias="X-Cron-Secret"),
):
    import os as _os
    from datetime import datetime as _dt, timedelta as _td, timezone as _tz
    expected = _os.environ.get("AKKI_CRON_SECRET")
    if not expected or x_cron_secret != expected:
        raise HTTPException(status_code=403, detail="Cron secret missing or invalid.")

    cutoff = _dt.now(_tz.utc) - _td(days=STALE_SESSION_AGE_DAYS)
    cutoff_iso = cutoff.isoformat().replace("+00:00", "Z")
    result = await db.solva_v2_sessions.update_many(
        {"status": "active", "updated_at": {"$lt": cutoff_iso}},
        {"$set": {
            "status": "abandoned",
            "abandoned_reason": "stale_30d",
            "abandoned_at": iso(now()),
            "updated_at": iso(now()),
        }},
    )
    logger.info(
        "solva_v2 stale_session_sweep cutoff=%s matched=%s modified=%s",
        cutoff_iso, result.matched_count, result.modified_count,
    )
    return {
        "ok": True,
        "cutoff": cutoff_iso,
        "matched": result.matched_count,
        "modified": result.modified_count,
    }


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

    # Phase 15.3 — hard-block sessions are terminal: 409 immediately.
    if rec.get("status") == "blocked_hard":
        raise HTTPException(
            status_code=409,
            detail=(
                "This Solva v2 session has been hard-blocked by the refusal "
                "ladder and cannot accept further turns."
            ),
        )

    # Phase 15.3 — 20-turn ceiling (decision #11). Count user turns only.
    user_turn_total = sum(1 for t in (rec.get("turns") or []) if t.get("role") == "user")
    if user_turn_total >= MAX_TURNS_PER_SESSION:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "session_turn_limit",
                "message": "Session turn limit reached",
                "limit": MAX_TURNS_PER_SESSION,
            },
        )

    # Phase 15.1: state machine owns transition legality.
    try:
        assert_can_post_turn(rec)
    except InvalidLayerTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))

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

    # Phase 15.1: refusal classifier. Phase 15.3: feeds the ladder.
    ref = await refusal.run(
        session=rec, turn_id=user_turn_id, layer=current_layer,
        user_text=body.user_text,
    )
    all_audits: List[Dict[str, Any]] = [ref["audit_entry"]]

    # Phase 15.3 — guardrail ladder. Pure-deterministic decision off the
    # refusal output + session counters. Three possible interceptions:
    #   * therapy_redirect — locked sentence + Learn link, session active
    #   * soft_block       — locked reframe sentence, session active,
    #                        jailbreak_soft_count++, layer NOT advanced
    #   * hard_block       — locked refusal, session flips to blocked_hard,
    #                        layer NOT advanced
    decision = guardrails.evaluate(session=rec, refusal_output=ref["output"])
    if decision.action != "continue":
        guard_audit = await synthetic_audit_entry(
            engine=guardrails.ENGINE,
            engine_version=guardrails.ENGINE_VERSION,
            layer=current_layer,
            turn_id=user_turn_id,
            output=decision.audit_output,
            tier_labels=[],
            shield_required=False,
            shield_bypassed_reason="deterministic_only",
            latency_ms=0,
        )
        all_audits.append(guard_audit)

        guard_solve_turn_id = str(uuid.uuid4())
        guard_solve_turn = {
            "id": guard_solve_turn_id,
            "role": "solva",
            "layer": current_layer,
            "text": decision.user_visible_message,
            "model": None,
            "tier": None,
            "guardrail_action": decision.action,
            "learn_link": decision.learn_link,
            "created_at": iso(now()),
        }
        guard_update: Dict[str, Any] = {"updated_at": iso(now())}
        if decision.increment_soft_count:
            guard_update["jailbreak_soft_count"] = int(
                rec.get("jailbreak_soft_count") or 0
            ) + 1
        if decision.new_status:
            guard_update["status"] = decision.new_status
            guard_update["blocked_at"] = iso(now())
        await db.solva_v2_sessions.update_one(
            {"id": sid, "account_id": account["id"]},
            {"$push": {
                "turns": guard_solve_turn,
                "reasoning_audit_log": {"$each": all_audits},
            },
             "$set": guard_update},
        )
        rec.setdefault("turns", []).append(guard_solve_turn)
        rec.setdefault("reasoning_audit_log", []).extend(all_audits)
        if decision.increment_soft_count:
            rec["jailbreak_soft_count"] = guard_update["jailbreak_soft_count"]
        if decision.new_status:
            rec["status"] = decision.new_status
        rec.pop("_id", None)
        return rec

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

    if current_layer == "framing":
        # Advance from framing -> grounding: triangulation + candidate_generation
        # run here; their summary becomes the Solva turn. Phase 15.1: real
        # candidate_generation can fail validator; surface 422 if so.
        out = await _run_grounding(rec, cluster, account["id"], solve_turn_id)
        all_audits.extend(out["audit_entries"])
        if out.get("violation"):
            await _append_audit(sid, all_audits)
            logger.warning(
                "solva_v2 candidate_generation violation sid=%s account=%s reason=%s",
                sid, account["id"], out.get("reason"),
            )
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "candidate_generation_failed",
                    "message": (
                        "Candidate-generation engine could not satisfy its "
                        "validator after one retry."
                    ),
                    "reason": out.get("reason"),
                },
            )
        solve_text = out["text"]
        # Park comparables + candidates in temp field for synthesis use
        rec["_grounding_comparables"] = out["comparables"]
        rec["_grounding_candidates"] = out["candidates"]
        update_fields["_grounding_comparables"] = out["comparables"]
        update_fields["_grounding_candidates"] = out["candidates"]

    elif current_layer == "grounding":
        # User gave feedback on grounding. Phase 15.2: dispatch by submodule.
        submodule = rec.get("submodule") or "seek_clarity"
        if expects_hypothesis_layer(submodule):
            # simulate_hypothesis: run the tension detector + scenario step
            # at this turn. Synthesis runs at the next turn (current_layer
            # will then be 'hypothesis').
            comparables = rec.get("_grounding_comparables") or []
            candidates = rec.get("_grounding_candidates") or []
            tri_output = {"comparables": comparables}
            user_turns = [t for t in rec.get("turns", []) if t.get("role") == "user"]
            out = await _run_hypothesis(
                rec, cluster, account["id"], solve_turn_id,
                user_turns=user_turns,
                triangulation_output=tri_output,
                candidates=candidates,
            )
            all_audits.extend(out["audit_entries"])
            solve_text = out["text"]
            update_fields["_hypothesis_tensions"] = out["tensions"]
            rec["_hypothesis_tensions"] = out["tensions"]
        else:
            # seek_clarity / develop_strategy / get_perspective: synthesis
            # happens at the grounding -> synthesis transition turn.
            tier_req = "deep" if rec.get("pro_tier") and rec.get("pro_account") else "standard"
            comparables = rec.get("_grounding_comparables") or []
            candidates = rec.get("_grounding_candidates") or []
            persona = rec.get("persona")
            out = await _run_synthesis(
                rec, cluster, account["id"], solve_turn_id, transcript,
                comparables=comparables, candidates=candidates, requested_tier=tier_req,
                submodule=submodule, persona=persona, tensions=None,
            )
            all_audits.extend(out["audit_entries"])
            if out.get("grounding_violation"):
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
            synthesis_record = {
                "body": out["text"],
                "stripped_text": out["stripped_text"],
                "claims": out["claims"],
                "tier_distribution": out["tier_distribution"],
                "probability_weighting_violations": out.get("probability_weighting_violations", []),
                "model": out["model"],
                "tier": out["tier"],
                "generated_at": iso(now()),
                "validation": out["validation"],
                "recommendations": out.get("recommendations", []),
            }
            update_fields["synthesis"] = synthesis_record
            rec["synthesis"] = synthesis_record
            solve_text = out["text"]
            solve_model = out["model"]
            solve_tier = out["tier"]

    elif current_layer == "hypothesis":
        # Phase 15.2 — simulate_hypothesis only. User has given feedback on
        # the detected tensions; proceed to synthesis with the tensions
        # injected into the prompt context.
        submodule = rec.get("submodule") or "seek_clarity"
        tier_req = "deep" if rec.get("pro_tier") and rec.get("pro_account") else "standard"
        comparables = rec.get("_grounding_comparables") or []
        candidates = rec.get("_grounding_candidates") or []
        tensions = rec.get("_hypothesis_tensions") or []
        persona = rec.get("persona")
        out = await _run_synthesis(
            rec, cluster, account["id"], solve_turn_id, transcript,
            comparables=comparables, candidates=candidates, requested_tier=tier_req,
            submodule=submodule, persona=persona, tensions=tensions,
        )
        all_audits.extend(out["audit_entries"])
        if out.get("grounding_violation"):
            await _append_audit(sid, all_audits)
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "grounding_contract_violation",
                    "message": "Model failed grounding contract after 3 attempts.",
                    "untagged_sentences": out.get("untagged_sentences", []),
                    "malformed_markers": out.get("malformed_markers", []),
                },
            )
        synthesis_record = {
            "body": out["text"],
            "stripped_text": out["stripped_text"],
            "claims": out["claims"],
            "tier_distribution": out["tier_distribution"],
            "probability_weighting_violations": out.get("probability_weighting_violations", []),
            "model": out["model"],
            "tier": out["tier"],
            "generated_at": iso(now()),
            "validation": out["validation"],
            "tensions": tensions,
            "recommendations": out.get("recommendations", []),
        }
        update_fields["synthesis"] = synthesis_record
        rec["synthesis"] = synthesis_record
        solve_text = out["text"]
        solve_model = out["model"]
        solve_tier = out["tier"]

    elif current_layer == "synthesis":
        # Phase 15.3 — Layer 4 Reflection. Three locked questions, each
        # answered by a tier-marked, validator-checked LLM call. Replaces
        # the 15.0/15.1/15.2 placeholder.
        out = await _run_reflection(rec, solve_turn_id, account["id"])
        all_audits.extend(out["audit_entries"])
        solve_text = out["text"]
        solve_model = out["model"]
        solve_tier = out["tier"]
        reflection_record = {
            "questions": reflection.LOCKED_QUESTIONS,
            "responses": out["responses"],
            "engine_version": reflection.ENGINE_VERSION,
            "model": out["model"],
            "tier": out["tier"],
            "generated_at": iso(now()),
        }
        update_fields["reflection"] = reflection_record
        update_fields["status"] = "completed"
        update_fields["completed_at"] = iso(now())
        update_fields["layer"] = "reflection"
        update_fields["layer_index"] = LAYERS.index("reflection")
        rec["reflection"] = reflection_record
        rec["status"] = "completed"
        rec["layer"] = "reflection"
        rec["layer_index"] = update_fields["layer_index"]

    elif current_layer == "reflection":
        # No further layer — this should not be reachable on an active session.
        raise HTTPException(status_code=409, detail="Session is at Reflection — no further turns.")

    # Advance layer pointer (skip for synthesis which already set completed)
    if current_layer not in ("synthesis", "reflection"):
        # Phase 15.1: route through the formal state machine. `rec` already
        # carries the new user turn + this turn's audit entries, which is
        # the post-turn snapshot the state machine inspects.
        advance_to = next_layer(rec)
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
    # Strip private grounding scratchpad fields before returning to client.
    rec.pop("_grounding_comparables", None)
    rec.pop("_grounding_candidates", None)
    return rec


# -----------------------------------------------------------------------------
# Phase 15.1 — Cycle handoff via Daily Review queue.
# v1's /api/solva/sessions/{sid}/handoff/cycle wrote db.questions directly.
# v2 first writes a Daily Review queue item of kind "solva_cycle_action";
# the user approves/rejects/edits via Daily Review's existing handlers.
# Briefing and Decks handoffs are out of scope for 15.1 — they stay v1-style.
# -----------------------------------------------------------------------------
async def _draft_cycle_questions_from_session(rec: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    synth = rec.get("synthesis") or {}
    claims = synth.get("claims") or []
    seed_claims = [
        c for c in claims
        if isinstance(c, dict) and c.get("tier") in {"corpus", "comparable"}
    ][:3]
    for i, c in enumerate(seed_claims, start=1):
        text = (c.get("text") or "").strip()
        if not text:
            continue
        if not text.endswith("?"):
            text = f"What does the evidence say about: {text.rstrip('.')}? "
        out.append({
            "id": str(uuid.uuid4()),
            "ordinal": i,
            "text": text,
            "category": "strategic",
            "source_tier": c.get("tier"),
            "confidence_band": c.get("confidence_band"),
        })
    if not out:
        body = (synth.get("stripped_text") or "").strip()[:280]
        if body:
            out.append({
                "id": str(uuid.uuid4()),
                "ordinal": 1,
                "text": f"Press the executive on: {body}",
                "category": "strategic",
                "source_tier": "domain_prior",
                "confidence_band": None,
            })
    return out


class HandoffCycleIn(BaseModel):
    note: Optional[str] = Field(default=None, max_length=400)


@router.post("/sessions/{sid}/handoff/cycle")
async def handoff_cycle_via_review(
    sid: str,
    body: HandoffCycleIn,
    account: Dict[str, Any] = Depends(require_solva_v2_flag),
):
    rec = await db.solva_v2_sessions.find_one(
        {"id": sid, "account_id": account["id"]}, {"_id": 0}
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Session not found.")
    if rec.get("status") != "completed":
        raise HTTPException(
            status_code=409,
            detail="Session must reach Reflection before cycle handoff.",
        )
    existing = await db.solve_handoffs.find_one(
        {"session_id": sid, "target": "cycle"}, {"_id": 0, "id": 1, "review_queue_id": 1}
    )
    if existing:
        return {
            "ok": True,
            "review_queue_id": existing.get("review_queue_id"),
            "idempotent": True,
        }

    questions = await _draft_cycle_questions_from_session(rec)
    if not questions:
        raise HTTPException(
            status_code=422,
            detail="Session synthesis carries no claims fit for cycle questions.",
        )

    queue_id = str(uuid.uuid4())
    handoff_id = str(uuid.uuid4())
    review_item = {
        "id": queue_id,
        "kind": "solva_cycle_action",
        "account_id": account["id"],
        "context_id": rec.get("context_id"),
        "session_id": sid,
        "cluster_id": rec.get("cluster_id"),
        "cluster_label": rec.get("cluster_label"),
        "questions": questions,
        "status": "pending_review",
        "note": (body.note or "").strip(),
        "audit_entry_count": len(rec.get("reasoning_audit_log") or []),
        "created_at": iso(now()),
        "reviewed_at": None,
    }
    await db.solva_cycle_handoff_queue.insert_one(review_item)

    await db.solve_handoffs.insert_one({
        "id": handoff_id,
        "session_id": sid,
        "account_id": account["id"],
        "target": "cycle",
        "status": "pending_review",
        "review_queue_id": queue_id,
        "created_at": iso(now()),
    })
    return {"ok": True, "review_queue_id": queue_id, "idempotent": False, "questions": questions}


# -----------------------------------------------------------------------------
# Phase 15.1 — reasoning-log/summary projection (compressed view per turn).
# 15.3 drawer renders this. No raw prompts, no internal identifiers.
# -----------------------------------------------------------------------------
@router.get("/sessions/{sid}/reasoning-log/summary")
async def reasoning_log_summary(
    sid: str,
    account: Dict[str, Any] = Depends(require_solva_v2_flag),
):
    rec = await db.solva_v2_sessions.find_one(
        {"id": sid, "account_id": account["id"]},
        {
            "_id": 0,
            "id": 1, "layer": 1, "status": 1, "submodule": 1,
            "reasoning_audit_log": 1, "synthesis": 1, "turns": 1,
        },
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Session not found.")

    audit = rec.get("reasoning_audit_log") or []
    turns: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    retry_counts: Dict[str, int] = {}
    for e in audit:
        tid = e.get("turn_id")
        if not tid:
            continue
        if tid not in turns:
            order.append(tid)
            turns[tid] = {
                "turn_id": tid,
                "layers": [],
                "engines": [],
                "tiers_cited": set(),
                "validator_verdict": None,
                "retry_count": 0,
                "shield_runs": 0,
                "shield_bypassed_runs": 0,
            }
        bucket = turns[tid]
        layer = e.get("layer")
        if layer and layer not in bucket["layers"]:
            bucket["layers"].append(layer)
        engine = e.get("engine")
        if engine and engine not in bucket["engines"]:
            bucket["engines"].append(engine)
        for t in (e.get("tier_labels") or []):
            bucket["tiers_cited"].add(t)
        key = f"{tid}:{engine}"
        retry_counts[key] = retry_counts.get(key, 0) + 1
        if e.get("shield_required"):
            bucket["shield_runs"] += 1
        else:
            bucket["shield_bypassed_runs"] += 1
        if engine == "validator":
            bucket["validator_verdict"] = (e.get("output") or {}).get("validator_verdict")

    for tid, bucket in turns.items():
        retries = sum(max(0, retry_counts.get(f"{tid}:{eng}", 1) - 1) for eng in bucket["engines"])
        bucket["retry_count"] = retries
        bucket["tiers_cited"] = sorted(bucket["tiers_cited"])

    synth = rec.get("synthesis") or {}
    claims = synth.get("claims") or []
    confidence_bands = {"Unlikely": 0, "Possible": 0, "Likely": 0, "High-conviction": 0}
    for c in claims:
        band = (c or {}).get("confidence_band")
        if band in confidence_bands:
            confidence_bands[band] += 1

    return {
        "session_id": rec["id"],
        "current_layer": rec.get("layer"),
        "status": rec.get("status"),
        "turn_count": len(order),
        "turns": [turns[t] for t in order],
        "confidence_distribution": confidence_bands,
        "tier_distribution": synth.get("tier_distribution") or {},
        "validator_verdict": (synth.get("validation") or {}).get("verdict"),
    }

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
