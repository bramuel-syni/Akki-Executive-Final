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

import hashlib
import json
import logging
import re
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
from services.solva_v2.opinion_filter import (
    OPINION_FREE_DIRECTIVE,
    enforce_opinion_free,
    scan as scan_for_opinion_phrases,
    retry_reminder as opinion_retry_reminder,
)
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
    # Phase I.2 — `cluster_id` is now optional. When omitted (or when
    # `auto_cluster=True`), the server resolves a cluster from the
    # framing intent via `_resolve_auto_cluster`. The cluster picker is
    # gone from the user surface per the UX brief; clusters remain an
    # internal engineering abstraction used by the engines.
    cluster_id: Optional[str] = Field(default=None, max_length=80)
    auto_cluster: bool = Field(default=True)
    intent: str = Field(min_length=20, max_length=1200)
    context_id: Optional[str] = None
    submodule: str = Field(default="seek_clarity")
    persona: Optional[str] = Field(default=None, max_length=200)  # Phase 15.2 — Get Perspective
    pro_tier: bool = False
    # Phase J.2 — sandbox flag. When true, the orchestrator compresses
    # the flow per Sandbox UX Brief §4.2: framing → 3 grounding questions
    # → PREPARING → ARTEFACT (no Layer-2 depth round). Purely additive;
    # in-product flow is unchanged when sandbox=false.
    sandbox: bool = False
    # Wave 1.1 (UAT pack 2026-05-10) — pre-framing seed from a sibling
    # surface. Carries a {kind, id} pointer so the framing screen can
    # render the source artefact and the audit log records the entry
    # path. Today supported kinds: `document`, `cycle_question`,
    # `solva_artefact`, `pulse_signal`. Additive per preservation
    # rule 8.
    intake_seed: Optional[Dict[str, Any]] = None


class FrameAuditDecisionIn(BaseModel):
    """Wave 2.1 — Layer 0 Frame Audit user choice. After the audit
    screen, the user picks one of three CTAs."""
    decision: str = Field(pattern="^(proceed|get_more|pause)$")


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


# =============================================================================
# Wave 1.1 (UAT pack 2026-05-10) — intake_seed resolver
# =============================================================================
# When the user clicks `<HandoffActions>` "Take into Solva" from a sibling
# surface, we land on /app/solva?seed_kind=<kind>&seed_id=<id>. The picker
# captures those, sends them in the session-create body, and we resolve
# them server-side into a short framing-context summary that the FramingScreen
# renders verbatim under the user's intent input.
#
# Supported kinds today:
#   - document          → fetches db.documents.{name, preview, sensitivity_band}
#   - cycle_question    → fetches db.questions.{title, body, source_doc_id}
#   - solva_artefact    → fetches db.solva_v2_sessions.{intent, synthesis.body[:400]}
#   - pulse_signal      → fetches db.signals.{title, summary}
#
# All resolutions are scoped by account_id + (when provided) context_id; if
# the user can't see the source, we degrade silently to seed_payload=None.

async def _resolve_intake_seed(
    seed: Dict[str, Any],
    *, account_id: str,
    context_id: Optional[str],
) -> Optional[Dict[str, Any]]:
    kind = (seed.get("kind") or "").strip().lower()
    sid = (seed.get("id") or "").strip()
    if not kind or not sid:
        return None

    summary: str = ""
    title: str = ""

    if kind == "document":
        q: Dict[str, Any] = {"id": sid}
        if context_id:
            q["context_id"] = context_id
        doc = await db.documents.find_one(
            q, {"_id": 0, "name": 1, "original_filename": 1, "preview": 1,
                "sensitivity_band": 1, "extracted_text": 1},
        )
        if not doc:
            return None
        title = doc.get("name") or doc.get("original_filename") or "Attached document"
        summary = (doc.get("preview") or doc.get("extracted_text") or "")[:600]

    elif kind == "cycle_question":
        ques = await db.questions.find_one(
            {"id": sid}, {"_id": 0, "title": 1, "body": 1, "source_doc_id": 1, "context_id": 1},
        )
        if not ques:
            return None
        if context_id and ques.get("context_id") and ques["context_id"] != context_id:
            return None
        title = ques.get("title") or "Cycle question"
        summary = (ques.get("body") or "")[:600]

    elif kind == "cycle_contribution":
        # Wave 3.1 (UAT pack) — Cycle Manager contribution → Solva.
        # The user clicked "Take to Solva" on a contribution row;
        # the body text becomes the seed framing context.
        contrib = await db.cycle_contributions.find_one(
            {"id": sid}, {"_id": 0, "title": 1, "body_text": 1, "context_id": 1},
        )
        if not contrib:
            return None
        if context_id and contrib.get("context_id") and contrib["context_id"] != context_id:
            return None
        title = contrib.get("title") or "Cycle contribution"
        summary = (contrib.get("body_text") or "")[:600]

    elif kind == "solva_artefact":
        prior = await db.solva_v2_sessions.find_one(
            {"id": sid, "account_id": account_id},
            {"_id": 0, "intent": 1, "synthesis": 1, "submodule": 1},
        )
        if not prior:
            return None
        title = f"Earlier {(prior.get('submodule') or 'solva').replace('_', ' ').title()} session"
        body = ((prior.get("synthesis") or {}).get("body") or prior.get("intent") or "")
        summary = body[:600]

    elif kind == "pulse_signal":
        sig = await db.signals.find_one(
            {"id": sid}, {"_id": 0, "title": 1, "summary": 1, "context_id": 1},
        )
        if not sig:
            return None
        if context_id and sig.get("context_id") and sig["context_id"] != context_id:
            return None
        title = sig.get("title") or "Pulse signal"
        summary = (sig.get("summary") or "")[:600]

    else:
        return None

    return {
        "kind": kind,
        "id": sid,
        "title": title,
        "summary": summary,
        "resolved_at": iso(now()),
    }


# =============================================================================
# Wave 1.2 (UAT pack 2026-05-10) — synthesis-time refusal trigger
# =============================================================================
# After the existing 3-attempt grounding-contract retry passes (i.e., the
# model produced markers), we ALSO check whether those markers are
# overwhelmingly weak. If yes, AND the session has no attached docs / no
# corpus or comparable claims, we flip status to `refused` and write
# a structured `synthesis_refusal_reasons` payload.
#
# This is DISTINCT from the safety-classifier refusal (`blocked_hard` /
# `blocked_soft` / `therapy_redirect`) — preservation rule 4. The
# synthesis-refusal artefact answers a different question: "we have no
# defensible synthesis to offer; here's what would help."

# Thresholds — kept easy to tune. The contract permits comparable +
# corpus + user_assertion + domain_prior + speculation; "thin" means
# the resolved tiers are dominated by speculation+domain_prior with
# zero corpus AND zero comparable.
_THIN_DOMINANT_FRACTION = 0.70
_THIN_DOMINANT_TIERS = ("speculation", "domain_prior")
_STRONG_TIERS = ("corpus", "comparable")


def _should_synthesis_refuse(
    *,
    tier_distribution: Dict[str, int],
    has_attached_docs: bool,
    has_grounding_paragraphs: bool,
) -> bool:
    """Returns True iff synthesis is too thin to defend.

    Bypass: when there ARE attached docs or grounding paragraphs (the
    user has supplied evidence), trust the existing pipeline. The
    refusal is for the truly ungrounded case where the model could
    only speculate.
    """
    if has_attached_docs or has_grounding_paragraphs:
        return False
    total = sum(int(v or 0) for v in (tier_distribution or {}).values())
    if total < 3:
        # Too few claims to draw conclusions from the distribution.
        # Don't trigger the refusal on tiny synthesis bodies.
        return False
    weak = sum(int(tier_distribution.get(t, 0) or 0) for t in _THIN_DOMINANT_TIERS)
    strong = sum(int(tier_distribution.get(t, 0) or 0) for t in _STRONG_TIERS)
    return strong == 0 and (weak / total) >= _THIN_DOMINANT_FRACTION


# Task-specific "what would help" templates. Keyed by submodule, each
# entry is a list of concrete evidence types the user could supply to
# unblock the synthesis. Deterministic; no LLM call.
_WHAT_WOULD_HELP_BY_SUBMODULE: Dict[str, List[str]] = {
    "seek_clarity": [
        "any document or memo where the situation is described in concrete terms",
        "minutes from the meeting where this surfaced",
        "a written brief from whoever first raised it",
    ],
    "develop_strategy": [
        "the financials behind the options being considered",
        "minutes or correspondence covering the prior round of debate",
        "a comparable case where a similar choice was made (and what happened)",
        "a stakeholder map identifying who supports each path and why",
    ],
    "simulate_hypothesis": [
        "a written version of the hypothesis with at least one falsifiable claim",
        "the data or analysis the hypothesis rests on",
        "comparable cases that succeeded or failed under the same conditions",
    ],
    "get_perspective": [
        "the existing framing or memo you want perspectives on",
        "a list of stakeholders whose views matter for this decision",
        "any prior boardroom or executive correspondence on the topic",
    ],
}


def _what_would_help_template(submodule: str) -> List[str]:
    return _WHAT_WOULD_HELP_BY_SUBMODULE.get(
        submodule, _WHAT_WOULD_HELP_BY_SUBMODULE["seek_clarity"],
    )


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
# Phase I.2 — keyword heuristic that maps intent text to one of the 12
# Solve clusters. Deterministic (no LLM call), so tests are stable and
# we save spend on every session start. The cluster is an internal
# engineering hint (it shapes phase_hints + banned_terms in the engine
# prompts); it is NOT user-visible per the v3 UX brief. Order matters
# in `_AUTO_CLUSTER_KEYWORDS`: the first matching cluster wins, so the
# more specific buckets are listed first.
_AUTO_CLUSTER_KEYWORDS: List[tuple[str, tuple[str, ...]]] = [
    ("ceo_succession",         ("succession", "successor", "ceo retire", "incoming ceo", "outgoing ceo", "next ceo")),
    ("founder_transition",     ("founder", "founders", "founding ceo", "step back", "step down", "exit the founder")),
    ("ma_thesis",              ("acquisition", "acquire ", "acquired", "merger", "m&a", "buyout", "target company", "deal thesis")),
    ("regulatory_change",      ("regulator", "regulation", "regulatory", "compliance ", "licence", "license", "supervisory")),
    ("tech_debt_or_outage",    ("outage", "downtime", "tech debt", "technical debt", "system failure", "platform incident", "cyber", "breach")),
    ("people_conduct",         ("misconduct", "harassment", "whistleblow", "ethics", "fraud", "conduct issue", "investigation", "resignation under")),
    ("performance_management", ("performance review", "underperforming", "performance management", "kpi miss", "missed targets", "delivery slip")),
    ("capital_allocation",     ("capital allocation", "buyback", "dividend", "balance sheet", "leverage", "raise capital", "rights issue", "debt facility")),
    ("risk_blindspot",         ("blind spot", "blindspot", "risk register", "risk we missed", "unhedged", "exposure", "tail risk")),
    ("board_dynamics",         ("chair ", "chairman", "the board ", "ned ", "non-executive", "boardroom", "board pack", "board dynamics")),
    ("strategy_drift",         ("strategy", "strategic drift", "five-year plan", "5-year plan", "lost focus", "drifted", "vision")),
    ("revenue_underperformance", ("revenue", "topline", "top line", "sales miss", "missed", "shortfall", "guidance miss")),
]
_AUTO_CLUSTER_DEFAULT = "revenue_underperformance"


async def _resolve_auto_cluster(intent: str) -> str:
    """Return a cluster id chosen for this intent text.

    Falls back to ``_AUTO_CLUSTER_DEFAULT`` when no keyword matches; if
    that cluster does not exist in the DB (operator deleted it), the
    next one in the seed taxonomy is picked. Never raises — start_session
    will 404 above if every fallback fails to resolve.
    """
    text = (intent or "").lower()
    candidate: Optional[str] = None
    for cid, kws in _AUTO_CLUSTER_KEYWORDS:
        if any(k in text for k in kws):
            candidate = cid
            break
    if candidate is None:
        candidate = _AUTO_CLUSTER_DEFAULT
    # Confirm the chosen cluster exists; if it doesn't (custom DB), pick
    # any active cluster as a last resort so the session can still start.
    exists = await db.solva_clusters.find_one({"id": candidate}, {"_id": 0, "id": 1})
    if exists:
        return candidate
    fallback = await db.solva_clusters.find_one({}, {"_id": 0, "id": 1})
    return (fallback or {}).get("id") or _AUTO_CLUSTER_DEFAULT


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
        # Wave 1.7 (UAT pack 2026-05-10) — explicit voice anti-list per
        # the Solva spec. These rules are read alongside the per-submodule
        # voice header, NOT replacing it. They tighten the existing
        # editorial tone with the spec's specific prohibitions.
        "\nCOACH VOICE (these are non-negotiable):\n"
        "- Use \"we\" \u2014 this is a partnership, not a probe.\n"
        "- Be declarative. Avoid hedging language (\"perhaps\", \"maybe\", \"I think\").\n"
        "- Allow silences after meaty questions \u2014 do not fill them.\n"
        "- Reference back to what the user said earlier when relevant.\n"
        "- Take credit on the user's behalf for insights they surfaced.\n"
        "- Use occasional warmth sparingly, when earned.\n"
        "\nNEVER:\n"
        "- Apologize. If you misunderstood, restate.\n"
        "- Sycophant. (\"Great question!\" is forbidden.)\n"
        "- Moralize. The user is an adult professional.\n"
        "- Lecture. The user knows their domain.\n"
        "- Soften language excessively. Direct is respectful.\n"
        "- Perform empathy beyond a brief acknowledgement when the situation is genuinely hard.\n"
        "- Compliment unprompted.\n"
        "- Gamify with levels, XP, or progress streaks.\n"
        "\nLAYER TRANSITIONS:\n"
        "- Peer-voiced. (\"OK \u2014 we have what we need on the surface. Now let's "
        "get into where these candidates hold up and where they don't.\")\n"
        "- Reference what just happened (\"you flagged X\" / \"we narrowed to three options\").\n"
        "- Brief. One or two sentences max.\n"
        "- Never patronising. (\"Great work!\" is forbidden \u2014 see SYCOPHANCE above.)\n"
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
        relax_responsiveness=bool(session.get("redirect_recovery")),
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
        # Phase B.2 — same numbered-recommendation structure for both
        # develop_strategy and simulate_hypothesis. For strategy these are
        # strategic moves; for hypothesis these are the actions /
        # monitoring steps under the most defensible scenario.
        if submodule == "simulate_hypothesis":
            label = "Hypothesis"
            shape = (
                "after the diagnosis paragraphs, write 2\u20134 numbered "
                "recommendations on their own lines, each starting with "
                "'Recommendation N:' followed by a single-sentence concrete "
                "action OR leading-indicator under the most defensible "
                "scenario, with its tier marker. Each recommendation must "
                "be testable and timeline-bounded."
            )
        else:
            label = "Strategy"
            shape = (
                "after the diagnosis paragraphs, write 2\u20134 numbered "
                "recommendations on their own lines, each starting with "
                "'Recommendation N:' followed by a single-sentence concrete "
                "action with its tier marker. Each recommendation must be "
                "testable and timeline-bounded."
            )
        system_base += f"\n\nADDITIONAL OUTPUT ({label}): {shape}"
    system_msg = system_base + candidate_block + comparable_block + GROUNDING_CONTRACT_PROMPT

    # Phase 15.3.5 — no-opinion directive prepended to every Solva v2 LLM
    # call. The `get_perspective` synthesis layer deliberately voices a
    # persona (Chair, NED, Investor, etc.) and the persona's first-person
    # is intentional product behaviour — bypass the directive there only.
    apply_opinion_filter = (submodule != "get_perspective")
    if apply_opinion_filter:
        system_msg = enforce_opinion_free(system_msg)

    base_user_query = (
        f"Conversation so far:\n{transcript or '(no prior turns)'}\n\n"
        "Generate the SYNTHESIS layer response now. Follow the OUTPUT FORMAT "
        "exactly, and tag every assertive sentence with exactly one tier marker."
    )

    # Iterative grounding-contract enforcement loop
    current_user_query = base_user_query
    last_result = None
    last_parse = None
    opinion_hits: List[str] = []  # Phase 15.3.5 — populated on opinion-filter retries
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

        # Phase 15.3.5 — no-opinion filter. Run on the PARSED stripped text
        # so tier markers don't false-trigger. Only when the filter applies
        # (i.e. NOT in get_perspective synthesis where persona-voice is
        # deliberate). On hit, force a retry with a sharpened reminder.
        opinion_hits = []
        if apply_opinion_filter:
            opinion_hits = scan_for_opinion_phrases(parse_res.stripped_text)
            audit_entries[-1]["output"]["opinion_phrases_hit"] = list(opinion_hits)

        if parse_res.valid and not opinion_hits:
            audit_entries[-1]["tier_labels"] = sorted({c.tier for c in parse_res.claims})
            audit_entries[-1]["output"]["grounding_accepted"] = True
            audit_entries[-1]["output"]["claim_count"] = len(parse_res.claims)
            break

        # Either grounding-contract failed OR opinion filter caught a hit.
        if not parse_res.valid:
            audit_entries[-1]["output"]["grounding_accepted"] = False
            audit_entries[-1]["output"]["untagged_count"] = len(parse_res.untagged_sentences)
            audit_entries[-1]["output"]["malformed_count"] = len(parse_res.malformed_markers)
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
        else:
            # Grounding passed; opinion filter caught it. Retry with a
            # sharpened opinion-free reminder appended.
            audit_entries[-1]["output"]["grounding_accepted"] = True
            audit_entries[-1]["output"]["opinion_blocked"] = True
            await record_retry(
                surface=SYNTHESIS_SURFACE,
                account_id=account_id,
                reason="opinion_language_blocked",
            )
            current_user_query = base_user_query + "\n\n" + opinion_retry_reminder(opinion_hits)

    if not last_parse or not last_parse.valid:
        return {
            "grounding_violation": True,
            "audit_entries": audit_entries,
            "untagged_sentences": last_parse.untagged_sentences if last_parse else [],
            "malformed_markers": last_parse.malformed_markers if last_parse else [],
            "raw_text": last_result.text if last_result else "",
        }

    # Phase 15.3.5 — opinion-filter exhausted retries. Hard-fail with 422.
    if apply_opinion_filter and opinion_hits:
        return {
            "opinion_violation": True,
            "phrases_hit": opinion_hits,
            "audit_entries": audit_entries,
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
    account: Dict[str, Any] = Depends(get_current_account),
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

    # Phase I.2 — auto-resolve cluster from intent when not provided.
    # The Solva v3 UX brief deprecates the user-facing cluster picker
    # but the engines still rely on cluster phase_hints + banned_terms,
    # so we resolve one server-side. `auto_cluster=True` (default) +
    # missing `cluster_id` triggers the resolver. If both are provided
    # we honour the explicit cluster_id (forensic / API-direct callers).
    resolved_cluster_id = (body.cluster_id or "").strip() or None
    if resolved_cluster_id is None and body.auto_cluster:
        resolved_cluster_id = await _resolve_auto_cluster(body.intent)
    if not resolved_cluster_id:
        raise HTTPException(
            status_code=422,
            detail=(
                "cluster_id required when auto_cluster=False. Either pass "
                "auto_cluster=true (default) or supply cluster_id."
            ),
        )
    cluster = await db.solva_clusters.find_one({"id": resolved_cluster_id}, {"_id": 0})
    if not cluster:
        raise HTTPException(status_code=404, detail="Unknown cluster.")

    # Phase 15.3 — concurrent active session limit (decision #11).
    # 2026-05-10 A.0 — at-cap behaviour relaxed: instead of hard-blocking
    # the user (which surfaces as "Could not start session." when the
    # client's error handler can't unwrap the structured detail), we
    # auto-abandon the oldest active session. The cap exists to bound
    # concurrent live state, not to deny new framings; an oldest-active
    # session at-cap is almost always an abandoned tab.
    active_count = await db.solva_v2_sessions.count_documents(
        {"account_id": account["id"], "status": "active"},
    )
    if active_count >= MAX_CONCURRENT_ACTIVE:
        await db.solva_v2_sessions.find_one_and_update(
            {"account_id": account["id"], "status": "active"},
            {"$set": {"status": "abandoned", "abandoned_reason": "auto_evicted_at_cap",
                      "completed_at": iso(now()), "updated_at": iso(now())}},
            sort=[("started_at", 1)],
        )

    session_id = str(uuid.uuid4())
    is_pro_account = await _is_pro(account)

    # Wave 1.1 (UAT pack) — resolve intake_seed payload (kind+id) into a
    # short framing context block that is shown alongside the user's
    # framing on the FramingScreen. Persisted on the session for audit.
    seed_in: Optional[Dict[str, Any]] = body.intake_seed or None
    seed_payload: Optional[Dict[str, Any]] = None
    if seed_in and isinstance(seed_in, dict):
        try:
            seed_payload = await _resolve_intake_seed(
                seed_in, account_id=account["id"],
                context_id=body.context_id,
            )
        except Exception:  # noqa: BLE001
            # Seed resolution must never fail session creation. Worst
            # case: the user sees no seed-block on framing.
            logger.warning("intake_seed resolution failed kind=%s id=%s",
                           seed_in.get("kind"), seed_in.get("id"))

    rec = {
        "id": session_id,
        "account_id": account["id"],
        "context_id": body.context_id,
        "version": 2,
        "schema_version": SCHEMA_VERSION,
        "submodule": body.submodule,  # Phase 15.2 — persisted
        "persona": (body.persona or "").strip() or None,  # 15.2 get_perspective
        "parent_session_id": None,  # 15.2 — set when session is forked
        "cluster_id": resolved_cluster_id,
        "cluster_label": cluster.get("label"),
        "cluster_resolution": "auto" if (body.cluster_id or "").strip() == "" else "explicit",
        "intent": body.intent.strip(),
        "layer": LAYERS[0],
        "layer_index": 0,
        "status": "active",
        "pro_tier": bool(body.pro_tier),
        "pro_account": is_pro_account,
        # Phase J.2 — sandbox flag persisted on the session doc so the
        # orchestrator's hypothesis-layer transition can short-circuit it.
        "sandbox": bool(body.sandbox),
        # Wave 1.1 — intake_seed (kind, id, summary) for audit + framing UI.
        "intake_seed": seed_payload,
        # Wave 2.1 — Layer 0 Frame Audit summary; populated AFTER the
        # framing screen submission, BEFORE the grounding flow. Null
        # on creation; the frame_audit engine writes here.
        "frame_audit_summary": None,
        # Wave 1.2 — synthesis-time refusal metadata. Populated only
        # when status=='refused' (distinct from blocked_*). Null
        # otherwise.
        "synthesis_refusal_reasons": None,
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
        # Phase 15.3 fix — therapy_redirect leaves the session active,
        # so the next user turn drives the same layer's engines. The
        # candidate_generation engine's responsiveness validator is
        # fragile against context drift introduced by the redirect+pivot;
        # set a one-shot flag the orchestrator consumes on the very next
        # turn to relax the validator.
        if decision.action == "therapy_redirect":
            guard_update["redirect_recovery"] = True
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
        if decision.action == "therapy_redirect":
            rec["redirect_recovery"] = True
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


# =============================================================================
# Wave 2.1 (UAT pack 2026-05-10) — Layer 0 Frame Audit endpoints
# =============================================================================
# Two endpoints, called in this order:
#   1. POST /sessions/{sid}/frame-audit
#        Runs the deterministic frame_audit engine against the
#        session's framing text, persists the result on the session
#        AND in the reasoning_audit_log. Idempotent: returns the
#        existing summary if one already exists, so refreshing the
#        screen doesn't mint duplicate audit rows.
#   2. POST /sessions/{sid}/frame-audit-decision  {decision}
#        Records the user's choice (proceed / get_more / pause).
#        - proceed:   no-op for the session record beyond an audit row;
#                     the orchestrator continues to the existing
#                     framing engine on the next /turn call.
#        - get_more:  status remains "active"; the screen returns
#                     the user to the framing input with the audit
#                     observations rendered above. (Frontend-driven.)
#        - pause:     status flips to "paused". Resumable later.

@router.post("/sessions/{sid}/frame-audit")
async def run_frame_audit(
    sid: str,
    account: Dict[str, Any] = Depends(get_current_account),
):
    rec = await db.solva_v2_sessions.find_one(
        {"id": sid, "account_id": account["id"]}, {"_id": 0},
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Session not found.")
    if rec.get("status") not in {"active", None}:
        raise HTTPException(status_code=409, detail=f"Session is {rec.get('status')}; frame audit unavailable.")

    if rec.get("frame_audit_summary"):
        # Idempotent: don't mint duplicate audit rows on a refresh.
        return {"frame_audit": rec["frame_audit_summary"], "cached": True}

    # Use the lazy import to avoid pulling the engine at module load
    # time; it's only on the framing path.
    from services.solva_v2.engines.frame_audit import (
        audit_framing, audit_to_audit_log_row,
    )

    framing_text = (rec.get("intent") or "").strip()
    seed_payload = rec.get("intake_seed")
    has_attached_docs = bool(seed_payload and seed_payload.get("kind") == "document")

    audit_res = audit_framing(
        submodule=rec.get("submodule") or "seek_clarity",
        framing_text=framing_text,
        has_attached_docs=has_attached_docs,
        seed_payload=seed_payload,
    )
    summary = audit_res.to_dict()
    audit_row = audit_to_audit_log_row(
        audit_res,
        framing_text=framing_text,
        submodule=rec.get("submodule") or "seek_clarity",
        iso_now=iso(now()),
    )
    await db.solva_v2_sessions.update_one(
        {"id": sid, "account_id": account["id"]},
        {
            "$set": {"frame_audit_summary": summary, "updated_at": iso(now())},
            "$push": {"reasoning_audit_log": audit_row},
        },
    )
    return {"frame_audit": summary, "cached": False}


@router.post("/sessions/{sid}/frame-audit-decision")
async def frame_audit_decision(
    sid: str,
    body: FrameAuditDecisionIn,
    account: Dict[str, Any] = Depends(get_current_account),
):
    rec = await db.solva_v2_sessions.find_one(
        {"id": sid, "account_id": account["id"]}, {"_id": 0},
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Session not found.")
    if rec.get("status") not in {"active", "paused", None}:
        raise HTTPException(status_code=409, detail=f"Session is {rec.get('status')}; decision unavailable.")

    decision = body.decision
    audit_row = {
        "engine": "frame_audit_decision",
        "engine_version": "frame_audit@1.0",
        "tier": "deterministic",
        "model": "deterministic",
        "input_sha": "",
        "output_sha": "",
        "shielded": False,
        "latency_ms": 0,
        "tier_label": decision,
        "ts": iso(now()),
    }
    update: Dict[str, Any] = {"updated_at": iso(now())}

    if decision == "pause":
        update["status"] = "paused"
        update["paused_at"] = iso(now())
    elif decision == "get_more":
        # No status change. The frontend keeps the user on the
        # framing screen with the audit observations visible.
        update["status"] = "active"
    elif decision == "proceed":
        # Resume from paused if applicable.
        update["status"] = "active"

    await db.solva_v2_sessions.update_one(
        {"id": sid, "account_id": account["id"]},
        {"$set": update, "$push": {"reasoning_audit_log": audit_row}},
    )
    return {"ok": True, "decision": decision, "status": update.get("status", rec.get("status"))}


# =============================================================================
# Wave 1.5 (UAT pack 2026-05-10) — Continue-in-Chat from a Solva artefact
# =============================================================================
# Mints a chat tethered to the active context with the artefact summary
# pre-rendered as a synthetic document. The frontend picks up the
# returned chat_id and navigates to /app/chat?chat_id=<id>. The
# `services.continue_chat.create_continue_chat` helper used here is the
# same one Work Studio + Cycle Manager use, so the audit shape is
# consistent across all four "continue in chat" entry points.

@router.post("/sessions/{sid}/continue-chat")
async def solva_continue_in_chat(
    sid: str,
    account: Dict[str, Any] = Depends(get_current_account),
):
    rec = await db.solva_v2_sessions.find_one(
        {"id": sid, "account_id": account["id"]}, {"_id": 0},
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Session not found.")
    if rec.get("status") not in {"complete", "refused", "blocked_hard", "blocked_soft"}:
        raise HTTPException(
            status_code=400,
            detail="Session has no completed artefact yet. Continue the session first.",
        )
    context_id = rec.get("context_id")
    if not context_id:
        raise HTTPException(status_code=400, detail="Session is not bound to a context.")

    # Build a short synthetic document body the chat can ground on.
    submodule = rec.get("submodule") or "seek_clarity"
    pretty = submodule.replace("_", " ").title()
    intent = (rec.get("intent") or "").strip()
    syn = rec.get("synthesis") or {}
    body_text_parts = [f"Solva {pretty} session", f"Original framing: {intent}"]
    if syn.get("body"):
        body_text_parts.append(syn["body"])
    if rec.get("status") == "refused":
        wwh = (rec.get("synthesis_refusal_reasons") or {}).get("what_would_help") or []
        if wwh:
            body_text_parts.append("What would help:\n" + "\n".join(f"  - {x}" for x in wwh))
    extracted_text = "\n\n".join(body_text_parts)[:4000]

    file_name = f"Solva {pretty} — {(intent[:60] or 'session')}.txt"

    from services.continue_chat import create_continue_chat
    chat_id, doc_id = await create_continue_chat(
        account_id=account["id"],
        context_id=context_id,
        kind="solva_artefact",
        source="solva_artefact",
        export_id=sid,
        file_name=file_name,
        file_path="",
        output_format="txt",
        extracted_text=extracted_text,
        sensitivity_band="INTERNAL",
    )
    return {"ok": True, "chat_id": chat_id, "doc_id": doc_id}


@router.get("/sessions")
async def list_sessions(
    status: Optional[str] = None,
    q: Optional[str] = None,
    account: Dict[str, Any] = Depends(get_current_account),
):
    """List sessions for the caller. Wave 3.3 (UAT pack) — added an
    optional `q` substring filter against `intent` (case-insensitive)
    so the new sessions-list page can search."""
    qfilter: Dict[str, Any] = {"account_id": account["id"], "version": 2}
    if status:
        qfilter["status"] = status
    if q and (q := q.strip()):
        qfilter["intent"] = {"$regex": re.escape(q), "$options": "i"}
    rows = await db.solva_v2_sessions.find(
        qfilter,
        {"_id": 0, "id": 1, "cluster_id": 1, "cluster_label": 1, "intent": 1,
         "layer": 1, "layer_index": 1, "status": 1, "submodule": 1,
         "started_at": 1, "updated_at": 1, "completed_at": 1},
    ).sort("updated_at", -1).to_list(length=100)
    return {"items": rows, "count": len(rows)}


# =============================================================================
# Workstream B (UAT pack 2 — 2026-05-10) — in-session document attach
# =============================================================================
# Replaces the W3.2 stub. The user can attach documents from the active
# context's Document Journal at session start (FramingScreen) AND at any
# active layer. Attached docs are listed on the session record under
# `attached_documents: [{id, title, attached_at}]` and flow into the
# grounding stage via the existing _retrieve_grounding_paragraphs path.
#
# Hard cap: 5 attachments per session (UI matches; backend enforces).

class AttachDocumentIn(BaseModel):
    document_id: str = Field(min_length=1, max_length=120)


_MAX_SESSION_ATTACHMENTS = 5


@router.post("/sessions/{sid}/attach-document")
async def attach_session_document(
    sid: str,
    body: AttachDocumentIn,
    account: Dict[str, Any] = Depends(get_current_account),
):
    rec = await db.solva_v2_sessions.find_one(
        {"id": sid, "account_id": account["id"]}, {"_id": 0},
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Session not found.")
    if rec.get("status") not in {"active", "paused", None}:
        raise HTTPException(status_code=409, detail=f"Session is {rec.get('status')}; attach unavailable.")

    context_id = rec.get("context_id")
    if not context_id:
        raise HTTPException(status_code=400, detail="Session is not bound to a context.")

    doc = await db.documents.find_one(
        {"id": body.document_id, "context_id": context_id},
        {"_id": 0, "id": 1, "name": 1, "original_filename": 1, "preview": 1,
         "extracted_text": 1, "sensitivity_band": 1},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found in this context.")

    existing = list(rec.get("attached_documents") or [])
    if any(a.get("id") == body.document_id for a in existing):
        return {"ok": True, "attached_documents": existing, "already_attached": True}
    if len(existing) >= _MAX_SESSION_ATTACHMENTS:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {_MAX_SESSION_ATTACHMENTS} attachments per session.",
        )

    attached_at = iso(now())
    chip = {
        "id": doc["id"],
        "title": doc.get("name") or doc.get("original_filename") or "Document",
        "attached_at": attached_at,
        "preview": (doc.get("preview") or doc.get("extracted_text") or "")[:300],
    }
    new_attached = existing + [chip]

    audit_row = {
        "engine": "document_attach",
        "engine_version": "document_attach@1.0",
        "tier": "deterministic",
        "model": "deterministic",
        "input_sha": hashlib.sha256(f"{sid}|{doc['id']}".encode()).hexdigest(),
        "output_sha": "",
        "shielded": False,
        "latency_ms": 0,
        "tier_label": "attached",
        "document_id": doc["id"],
        "document_title": chip["title"],
        "ts": attached_at,
    }

    await db.solva_v2_sessions.update_one(
        {"id": sid, "account_id": account["id"]},
        {
            "$set": {"attached_documents": new_attached, "updated_at": attached_at},
            "$push": {"reasoning_audit_log": audit_row},
        },
    )
    return {"ok": True, "attached_documents": new_attached, "already_attached": False}


@router.delete("/sessions/{sid}/attached-documents/{document_id}")
async def detach_session_document(
    sid: str,
    document_id: str,
    account: Dict[str, Any] = Depends(get_current_account),
):
    rec = await db.solva_v2_sessions.find_one(
        {"id": sid, "account_id": account["id"]}, {"_id": 0},
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Session not found.")
    if rec.get("status") not in {"active", "paused", None}:
        raise HTTPException(status_code=409, detail=f"Session is {rec.get('status')}; detach unavailable.")
    existing = list(rec.get("attached_documents") or [])
    new_attached = [a for a in existing if a.get("id") != document_id]
    audit_row = {
        "engine": "document_detach",
        "engine_version": "document_attach@1.0",
        "tier": "deterministic",
        "model": "deterministic",
        "input_sha": hashlib.sha256(f"{sid}|{document_id}".encode()).hexdigest(),
        "output_sha": "",
        "shielded": False,
        "latency_ms": 0,
        "tier_label": "detached",
        "document_id": document_id,
        "ts": iso(now()),
    }
    await db.solva_v2_sessions.update_one(
        {"id": sid, "account_id": account["id"]},
        {
            "$set": {"attached_documents": new_attached, "updated_at": iso(now())},
            "$push": {"reasoning_audit_log": audit_row},
        },
    )
    return {"ok": True, "attached_documents": new_attached}


# =============================================================================
# Workstream B.2 (UAT pack 2 — 2026-05-10) — Take to Cycle from Solva artefact
# =============================================================================
# Mints a `cycle_question` row from a completed Solva session and
# returns the question_id so the frontend can navigate to Cycle Manager
# with `?question_id=` for highlight-and-scroll. Replaces the
# previous "Coming soon" toast stub.

@router.post("/sessions/{sid}/take-to-cycle")
async def take_to_cycle(
    sid: str,
    account: Dict[str, Any] = Depends(get_current_account),
):
    rec = await db.solva_v2_sessions.find_one(
        {"id": sid, "account_id": account["id"]}, {"_id": 0},
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Session not found.")
    if rec.get("status") not in {"complete", "refused"}:
        raise HTTPException(
            status_code=400,
            detail="Session has no completed artefact yet.",
        )
    context_id = rec.get("context_id")
    if not context_id:
        raise HTTPException(status_code=400, detail="Session is not bound to a context.")

    # Resolve the active cycle for the context (or refuse with a clear
    # error the SPA can convert to a guidance toast).
    config = await db.cycle_configs.find_one(
        {"context_id": context_id}, {"_id": 0, "current_cycle_id": 1, "current_cycle_label": 1},
    )
    cycle_id = (config or {}).get("current_cycle_id")
    if not cycle_id:
        raise HTTPException(status_code=400, detail={"code": "NO_ACTIVE_CYCLE",
                                                     "message": "Start a cycle in Cycle Manager first."})

    # Build the question text from the artefact. Prefer the synthesis
    # diagnosis paragraph; fall back to the framing intent.
    syn = rec.get("synthesis") or {}
    syn_body = (syn.get("stripped_text") or syn.get("body") or "").strip()
    intent = (rec.get("intent") or "").strip()
    submodule = rec.get("submodule") or "seek_clarity"
    pretty = submodule.replace("_", " ").title()

    # Short text (~280 chars) — first sentence of synthesis preferred.
    short_text = syn_body or intent or "Solva session question"
    for delim in (". ", "? ", "! ", "\n"):
        idx = short_text.find(delim)
        if 0 < idx < 240:
            short_text = short_text[: idx + 1].strip()
            break
    short_text = short_text[:280].rstrip(" .;:")

    question_id = str(uuid.uuid4())
    full_text_parts = [
        f"From a Solva {pretty} session.",
        f"Original framing: {intent}" if intent else "",
        syn_body[:1500] if syn_body else "",
    ]
    if rec.get("status") == "refused":
        wwh = (rec.get("synthesis_refusal_reasons") or {}).get("what_would_help") or []
        if wwh:
            full_text_parts.append("What would help (per Solva refusal):\n" + "\n".join(f"  - {x}" for x in wwh))

    question_doc = {
        "id": question_id,
        "context_id": context_id,
        "cycle_id": cycle_id,
        "title": f"Solva → {pretty}",
        "body": short_text,
        "body_full": "\n\n".join([p for p in full_text_parts if p]),
        "source": "solva",
        "source_solva_session_id": sid,
        "source_artefact_kind": submodule,
        "linked_session_id": sid,
        "status": "open",
        "created_by": account["id"],
        "created_at": iso(now()),
    }
    await db.questions.insert_one(question_doc)

    # Audit row on the Solva session.
    audit_row = {
        "engine": "take_to_cycle",
        "engine_version": "take_to_cycle@1.0",
        "tier": "deterministic",
        "model": "deterministic",
        "input_sha": hashlib.sha256(f"{sid}|{question_id}".encode()).hexdigest(),
        "output_sha": "",
        "shielded": False,
        "latency_ms": 0,
        "tier_label": "handoff",
        "cycle_id": cycle_id,
        "cycle_question_id": question_id,
        "ts": iso(now()),
    }
    await db.solva_v2_sessions.update_one(
        {"id": sid, "account_id": account["id"]},
        {"$push": {"reasoning_audit_log": audit_row}},
    )

    return {
        "ok": True,
        "cycle_id": cycle_id,
        "cycle_question_id": question_id,
    }


@router.get("/sessions/{sid}")
async def get_session(
    sid: str,
    account: Dict[str, Any] = Depends(get_current_account),
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
    account: Dict[str, Any] = Depends(get_current_account),
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

    cluster = await db.solva_clusters.find_one(
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
    account: Dict[str, Any] = Depends(get_current_account),
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
    account: Dict[str, Any] = Depends(get_current_account),
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
    account: Dict[str, Any] = Depends(get_current_account),
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
    account: Dict[str, Any] = Depends(get_current_account),
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

    # Phase 15.3 fix — capture the one-shot redirect_recovery flag at the
    # top of the turn so it's consumed regardless of which branch fires
    # below (continue / soft_block / hard_block / therapy_redirect_again).
    # Engines downstream still see the True value on the in-memory `rec`;
    # the DB write at the end of the turn always clears it.
    consumed_redirect_recovery = bool(rec.get("redirect_recovery"))

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

    cluster = await db.solva_clusters.find_one({"id": rec["cluster_id"]}, {"_id": 0})
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
        # Phase 15.3 fix — therapy_redirect leaves the session active and
        # the user is expected to pivot. The next turn re-runs whatever
        # layer's engines were dispatched. Set a one-shot recovery flag
        # so the candidate_generation engine relaxes its responsiveness
        # validator on that follow-on turn (the redirect+pivot sequence
        # legitimately introduces vocabulary drift).
        if decision.action == "therapy_redirect":
            guard_update["redirect_recovery"] = True
        elif consumed_redirect_recovery:
            # Soft/hard block on the recovery turn — still consume the flag.
            guard_update["redirect_recovery"] = False
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
        if decision.action == "therapy_redirect":
            rec["redirect_recovery"] = True
        elif consumed_redirect_recovery:
            rec["redirect_recovery"] = False
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
    # `consumed_redirect_recovery` is captured at the top of post_turn so
    # it's already correct here. Mirror to update_fields so DB clears.
    if consumed_redirect_recovery:
        update_fields["redirect_recovery"] = False
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
            # Phase B.3 — opinion-filter exhaustion is symmetric to a
            # grounding-contract failure: the orchestrator MUST NOT fall
            # through to populate `synthesis_record["body"] = out["text"]`
            # because `out` carries `opinion_violation=True` and no
            # `text` key. Raise 422 with the canonical detail shape so
            # the SPA + the no-opinion adversarial test corpus can both
            # consume the same envelope.
            if out.get("opinion_violation"):
                await _append_audit(sid, all_audits)
                logger.warning(
                    "solva_v2 opinion-filter exhaustion sid=%s account=%s phrases=%s",
                    sid, account["id"], out.get("phrases_hit", []),
                )
                raise HTTPException(
                    status_code=422,
                    detail={
                        "code": "opinion_violation",
                        "error": "opinion_violation",
                        "message": (
                            "Model produced opinion-laden output across all "
                            "retry attempts; refusing to surface a first-person "
                            "view per the no-opinion principle."
                        ),
                        "phrases_hit": out.get("phrases_hit", []),
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

            # Wave 1.2 (UAT pack) — synthesis-time refusal trigger.
            # After the 3-attempt grounding contract has passed (so we
            # have legal markers), check whether the resolved tiers
            # are too thin to defend a synthesis. If yes, swap the
            # synthesis_record body for a refusal payload and flip the
            # session status to "refused". The 3-attempt retry loop
            # is preserved upstream (preservation rule 1).
            _has_corpus_input = bool(comparables) or bool(candidates)
            _has_attached_docs = bool(rec.get("intake_seed"))
            if _should_synthesis_refuse(
                tier_distribution=out.get("tier_distribution", {}),
                has_attached_docs=_has_attached_docs,
                has_grounding_paragraphs=_has_corpus_input,
            ):
                _refusal_reasons = {
                    "refusal_kind": "synthesis_refusal",
                    "tier_distribution": out.get("tier_distribution", {}),
                    "what_would_help": _what_would_help_template(submodule),
                    "submodule": submodule,
                    "had_attached_docs": _has_attached_docs,
                    "had_grounding_paragraphs": _has_corpus_input,
                    "refused_at": iso(now()),
                }
                # Append a dedicated audit row so the reasoning log
                # tells a coherent "we tried to synthesise, then
                # refused" story. Engine name is `synthesis_refusal`
                # (distinct from `refusal` which is the safety
                # classifier — preservation rule 4).
                all_audits.append({
                    "engine": "synthesis_refusal",
                    "engine_version": "synthesis_refusal@1.0",
                    "tier": out.get("tier", "standard"),
                    "model": out.get("model", ""),
                    "input_sha": "",
                    "output_sha": "",
                    "shielded": False,
                    "latency_ms": 0,
                    "tier_label": "refusal",
                    "tier_distribution": out.get("tier_distribution", {}),
                    "what_would_help": _refusal_reasons["what_would_help"],
                    "ts": iso(now()),
                })
                synthesis_record["refused"] = True
                synthesis_record["refusal_reasons"] = _refusal_reasons
                update_fields["synthesis"] = synthesis_record
                update_fields["synthesis_refusal_reasons"] = _refusal_reasons
                update_fields["status"] = "refused"
                update_fields["completed_at"] = iso(now())
                rec["synthesis"] = synthesis_record
                rec["synthesis_refusal_reasons"] = _refusal_reasons
                rec["status"] = "refused"

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
        # Phase B.3 — symmetric handling for opinion-filter exhaustion
        # on the simulate_hypothesis -> synthesis turn.
        if out.get("opinion_violation"):
            await _append_audit(sid, all_audits)
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "opinion_violation",
                    "error": "opinion_violation",
                    "message": (
                        "Model produced opinion-laden output across all "
                        "retry attempts; refusing to surface a first-person "
                        "view per the no-opinion principle."
                    ),
                    "phrases_hit": out.get("phrases_hit", []),
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
    # Phase 15.3 fix — mirror the DB-side redirect_recovery clear on the
    # in-memory rec we're about to return so the API response accurately
    # reflects post-turn state.
    if consumed_redirect_recovery:
        rec["redirect_recovery"] = False
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
    account: Dict[str, Any] = Depends(get_current_account),
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
    existing = await db.solva_handoffs.find_one(
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

    await db.solva_handoffs.insert_one({
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
    account: Dict[str, Any] = Depends(get_current_account),
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


# -----------------------------------------------------------------------------
# Phase I.3 — Artefact reasoning shaping endpoint.
#
# The Artefact view's "How Solva reasoned this" expandable consumes a
# pre-shaped projection of `reasoning_audit_log`. This endpoint groups
# audit entries by engine into the 4 sections described in brief §5.4:
#     1. The candidates Solva considered.
#     2. What the triangulation found.
#     3. How the probabilities were weighted.
#     4. The full reasoning audit log (compressed; raw prompts excluded).
# -----------------------------------------------------------------------------
@router.get("/sessions/{sid}/artefact-reasoning")
async def artefact_reasoning(
    sid: str,
    account: Dict[str, Any] = Depends(get_current_account),
):
    rec = await db.solva_v2_sessions.find_one(
        {"id": sid, "account_id": account["id"]},
        {
            "_id": 0,
            "id": 1, "layer": 1, "status": 1, "submodule": 1,
            "reasoning_audit_log": 1, "synthesis": 1,
        },
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Session not found.")

    audit = rec.get("reasoning_audit_log") or []
    candidates: List[Dict[str, Any]] = []
    triangulation_findings: List[Dict[str, Any]] = []
    weighting: Dict[str, Any] = {}
    log_entries: List[Dict[str, Any]] = []

    for e in audit:
        if not isinstance(e, dict):
            continue
        engine = (e.get("engine") or "").lower()
        out = e.get("output") or {}
        # 1) Candidates the engine considered
        if engine == "candidate_generation":
            for c in (out.get("candidates") or []):
                if isinstance(c, dict):
                    candidates.append({
                        "hypothesis": c.get("hypothesis") or c.get("text") or "",
                        "tentative_tier": c.get("tentative_tier_hint") or c.get("tier") or "",
                        "weight": c.get("weight"),
                    })
        # 2) Triangulation findings (divergences + comparable signals)
        elif engine == "triangulation":
            divergences = out.get("divergences") or out.get("findings") or []
            for d in divergences:
                if isinstance(d, dict):
                    triangulation_findings.append({
                        "summary": d.get("summary") or d.get("description") or "",
                        "severity": d.get("severity") or "",
                        "source": d.get("source") or "",
                    })
                else:
                    triangulation_findings.append({"summary": str(d), "severity": "", "source": ""})
        # 3) Probability weighting breakdown
        elif engine == "probability_weighting":
            breakdown = out.get("aggregation_breakdown") or out.get("breakdown")
            if breakdown:
                weighting["breakdown"] = breakdown
            if out.get("violations"):
                weighting["violations"] = out["violations"]
        # 4) Compressed audit row for the full log
        log_entries.append({
            "ts":     e.get("ts") or e.get("created_at") or "",
            "engine": e.get("engine") or "",
            "engine_version": e.get("engine_version") or "",
            "layer":  e.get("layer") or "",
            "tiers_cited": e.get("tier_labels") or [],
            "verdict": (out.get("verdict") or out.get("validator_verdict") or ""),
            "shield_required": bool(e.get("shield_required")),
            "latency_ms": e.get("latency_ms"),
        })

    synth = rec.get("synthesis") or {}
    return {
        "session_id":      rec["id"],
        "submodule":       rec.get("submodule") or "seek_clarity",
        "status":          rec.get("status"),
        "candidates":      candidates,
        "triangulation":   triangulation_findings,
        "weighting":       weighting,
        "tier_distribution": synth.get("tier_distribution") or {},
        "log_entries":     log_entries,
    }


# -----------------------------------------------------------------------------
# Phase I.4 — PDF / DOCX export of the Solva artefact (or refusal artefact).
# Both endpoints are auth-gated; the file is built in-process by
# ``solva_artefact_export``. WeasyPrint + python-docx do not need any
# external service. Refusal sessions automatically use the 4-section
# refusal anatomy (brief §5.5).
# -----------------------------------------------------------------------------
def _safe_filename_part(text: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", text or "")
    return cleaned.strip("-")[:60] or "session"


@router.get("/sessions/{sid}/export.pdf")
async def export_session_pdf(
    sid: str,
    account: Dict[str, Any] = Depends(get_current_account),
):
    from fastapi.responses import Response

    rec = await db.solva_v2_sessions.find_one(
        {"id": sid, "account_id": account["id"]}, {"_id": 0},
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Session not found.")

    try:
        from solva_artefact_export import build_pdf
        pdf_bytes = build_pdf(rec)
    except Exception as exc:  # noqa: BLE001
        logger.exception("solva v2 export.pdf failed sid=%s", sid)
        raise HTTPException(
            status_code=500,
            detail=f"PDF export failed: {exc}",
        ) from exc

    filename = f"solva-{_safe_filename_part(rec.get('submodule') or 'session')}-{sid[:8]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Solva-Artefact": "refusal" if rec.get("status") in {"refused", "blocked_hard", "blocked_soft"} else "standard",
        },
    )


@router.get("/sessions/{sid}/export.docx")
async def export_session_docx(
    sid: str,
    account: Dict[str, Any] = Depends(get_current_account),
):
    from fastapi.responses import Response

    rec = await db.solva_v2_sessions.find_one(
        {"id": sid, "account_id": account["id"]}, {"_id": 0},
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Session not found.")

    try:
        from solva_artefact_export import build_docx
        docx_bytes = build_docx(rec)
    except Exception as exc:  # noqa: BLE001
        logger.exception("solva v2 export.docx failed sid=%s", sid)
        raise HTTPException(
            status_code=500,
            detail=f"DOCX export failed: {exc}",
        ) from exc

    filename = f"solva-{_safe_filename_part(rec.get('submodule') or 'session')}-{sid[:8]}.docx"
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Solva-Artefact": "refusal" if rec.get("status") in {"refused", "blocked_hard", "blocked_soft"} else "standard",
        },
    )
