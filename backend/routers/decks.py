"""Decks — narrative slide-deck generation with budget guardrails.

Three-step pipeline that ensures deep-tier (Opus) calls only fire when
context is sufficient and the user has confirmed the research question.

  1. POST /contexts/{cid}/decks/outline       (STANDARD tier — free of deep budget)
       → Parses intent, surfaces available context (docs/signals/briefs),
         drafts a slide outline + research question + missing-context flags.
         User reviews & may iterate before committing a deep slot.

  2. POST /contexts/{cid}/decks/{outline_id}/generate   (DEEP tier — 1 slot)
       → Consumes a deck-quota slot ONLY after outline is approved.
         Renders the deck against the approved outline.

  3. POST /contexts/{cid}/decks/{deck_id}/quality_check  (FAST tier — free)
       → Scores the deck against the original intent + outline.
         If score < threshold we return refinement guidance rather than
         encouraging an expensive regen.

  4. POST /contexts/{cid}/decks/{deck_id}/feedback       (free)
       → User thumbs (up/down) + optional comment. Drives behaviour
         monitoring on /admin/llm-spend → Deck quality panel.

Telemetry: `deck_telemetry` collection captures outline iterations,
quality scores, regen counts, and user feedback for ops visibility.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core import db, iso, now, write_audit, require_context_membership, get_current_account

logger = logging.getLogger("akki.decks")

router = APIRouter(tags=["decks"])


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class OutlineIn(BaseModel):
    intent: str = Field(min_length=12, max_length=600)
    audience: Optional[str] = Field(None, max_length=120)
    target_slides: Optional[int] = Field(None, ge=4, le=20)
    parent_outline_id: Optional[str] = None  # iterating on a prior outline


class GenerateIn(BaseModel):
    outline_id: str
    confirmed: bool = False
    edits: Optional[Dict[str, Any]] = None  # user tweaks: {research_question, slides[]}


class FeedbackIn(BaseModel):
    rating: str = Field(pattern="^(up|down)$")
    comment: Optional[str] = Field(None, max_length=500)
    will_regenerate: bool = False
    regen_reason: Optional[str] = Field(
        None, pattern="^(audience_drift|weak_research_question|missing_evidence|wrong_tone|other)$"
    )


# ---------------------------------------------------------------------------
# Outline — STANDARD tier; cheap, gets the user to a clear research question
# and shows them which sources will be used. Critical guardrail: the user
# must confirm this before any deep call fires.
# ---------------------------------------------------------------------------
async def _gather_context_signals(context_id: str) -> Dict[str, Any]:
    """Pull a compact summary of available evidence for the LLM to plan against."""
    docs = await db.documents.find(
        {"context_id": context_id, "status": {"$in": ["extracted", "ready"]}},
        {"_id": 0, "id": 1, "name": 1, "doc_type": 1, "created_at": 1, "preview": 1,
         "extracted_chars": 1},
    ).sort("created_at", -1).to_list(length=40)

    signals = await db.signals.find(
        {"context_id": context_id, "status": {"$ne": "archived"}},
        {"_id": 0, "id": 1, "title": 1, "kind": 1, "act_on_status": 1,
         "created_at": 1, "summary": 1},
    ).sort("created_at", -1).to_list(length=30)

    briefs = await db.briefs.find(
        {"context_id": context_id},
        {"_id": 0, "id": 1, "title": 1, "kind": 1, "objective": 1, "created_at": 1,
         "tier": 1},
    ).sort("created_at", -1).to_list(length=20)

    return {"docs": docs, "signals": signals, "briefs": briefs}


def _outline_prompt(intent: str, audience: Optional[str], target_slides: int,
                    ctx_name: str, evidence: Dict[str, Any],
                    learning_hint: Optional[str] = None) -> str:
    docs_block = "\n".join(
        f"- doc[{d['id'][:8]}] {d.get('name','(untitled)')} "
        f"({d.get('doc_type') or 'doc'}, {d.get('extracted_chars',0)} chars)"
        for d in evidence["docs"][:15]
    ) or "  (none)"
    sigs_block = "\n".join(
        f"- signal[{s['id'][:8]}] {s.get('title','(untitled)')} "
        f"({s.get('kind') or 'signal'})"
        for s in evidence["signals"][:15]
    ) or "  (none)"
    briefs_block = "\n".join(
        f"- brief[{b['id'][:8]}] {b.get('title','(untitled)')} ({b.get('kind') or 'brief'})"
        for b in evidence["briefs"][:10]
    ) or "  (none)"

    learning_block = ""
    if learning_hint:
        learning_block = (
            "\nLEARNING FROM THIS USER'S PRIOR DECKS\n"
            f"On their last regenerate they flagged: {learning_hint}.\n"
            "Use this as a corrective hint: tighten the research question, "
            "be sharper about audience, or call out missing evidence "
            "explicitly so they can fix the upstream gap rather than "
            "burning another deep slot.\n"
        )

    return (
        "You are AKKI's deck-planning model. Your job here is NOT to write the "
        "deck. Your job is to plan it cheaply and surface gaps so the user "
        "doesn't burn an expensive deep-tier generation on a weak prompt.\n\n"
        f"CONTEXT: {ctx_name}\n"
        f"AUDIENCE: {audience or 'unspecified — assume board/ExCo'}\n"
        f"TARGET LENGTH: {target_slides} slides.\n"
        f"USER INTENT: {intent}\n"
        + learning_block +
        "\nAVAILABLE EVIDENCE\n"
        "Documents:\n" + docs_block + "\n\n"
        "Signals:\n" + sigs_block + "\n\n"
        "Briefs:\n" + briefs_block + "\n\n"
        "Return STRICT JSON:\n"
        "{\n"
        '  "research_question": "<the one sharp question this deck should answer, in 1 sentence>",\n'
        '  "audience_assumed": "<the audience the planner assumed>",\n'
        '  "evidence_used": [{"id": "<doc/signal/brief id>", "kind": "doc|signal|brief", "why": "<one line>"}],\n'
        '  "missing_context": ["<one line per genuine gap; empty array if none>"],\n'
        '  "context_sufficiency": "sufficient|partial|insufficient",\n'
        '  "slides": [{"n": 1, "title": "<short>", "purpose": "<one line>", "key_points": ["<3-5 bullets>"]}, ...],\n'
        '  "estimated_cost_note": "<1 line, e.g. \\"Deep tier; consumes 1 of 3 daily deck slots\\"">\n'
        "}\n"
        "RULES:\n"
        "1. NEVER invent evidence ids — use only ids from the lists above.\n"
        "2. If `context_sufficiency` is `insufficient` or `partial`, the user "
        "should be discouraged from generating until they upload more docs. "
        "Be specific in `missing_context`.\n"
        "3. Slide count must equal target_slides.\n"
        "4. Be calm, editorial — AKKI house style. No marketing language.\n"
    )


@router.post("/api/contexts/{context_id}/decks/outline")
async def create_outline(
    context_id: str,
    body: OutlineIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Plan a deck cheaply; surface gaps; do NOT consume the deck deep slot."""
    target_slides = body.target_slides or 8
    ctx_name = ctx["context"].get("name") or "the company"
    evidence = await _gather_context_signals(context_id)

    # Look up the most recent regen-reason this user gave on a prior deck
    # so the planner can fold the lesson into this outline (zero deep budget).
    last_regen = await db.decks.find_one(
        {"context_id": context_id,
         "account_id": ctx["account"]["id"],
         "user_feedback.regen_reason": {"$nin": [None, ""]}},
        {"_id": 0, "user_feedback.regen_reason": 1, "user_feedback.comment": 1},
        sort=[("created_at", -1)],
    )
    learning_hint = None
    if last_regen and last_regen.get("user_feedback"):
        reason = last_regen["user_feedback"].get("regen_reason")
        comment = last_regen["user_feedback"].get("comment")
        if reason:
            label = {
                "audience_drift":         "the deck drifted from the audience",
                "weak_research_question": "the research question was too weak",
                "missing_evidence":       "key evidence was missing",
                "wrong_tone":             "the tone was off",
                "other":                  "the deck didn't land",
            }.get(reason, reason)
            learning_hint = label + (f" — user said: \"{comment}\"" if comment else "")

    prompt = _outline_prompt(
        body.intent.strip(), body.audience, target_slides, ctx_name, evidence,
        learning_hint=learning_hint,
    )

    from llm_service import call_llm
    llm_out = await call_llm(
        module="decks.outline",
        user_query=prompt,
        response_format="json",
        tier="standard",   # ← never charges the deep budget
    )
    raw = llm_out.get("response") or "{}"
    parsed = _safe_json(raw)
    if not parsed or "slides" not in parsed:
        raise HTTPException(status_code=502, detail="Outline planner returned malformed response.")

    # Iteration count if iterating on a prior outline.
    iteration = 1
    if body.parent_outline_id:
        parent = await db.deck_outlines.find_one(
            {"id": body.parent_outline_id, "context_id": context_id},
            {"_id": 0, "iteration": 1},
        )
        if parent:
            iteration = (parent.get("iteration") or 1) + 1

    outline_id = str(uuid.uuid4())
    rec = {
        "id": outline_id,
        "context_id": context_id,
        "account_id": ctx["account"]["id"],
        "intent": body.intent.strip(),
        "audience": body.audience,
        "target_slides": target_slides,
        "research_question": parsed.get("research_question"),
        "audience_assumed": parsed.get("audience_assumed"),
        "evidence_used": parsed.get("evidence_used") or [],
        "missing_context": parsed.get("missing_context") or [],
        "context_sufficiency": parsed.get("context_sufficiency") or "partial",
        "slides": parsed.get("slides") or [],
        "estimated_cost_note": parsed.get("estimated_cost_note"),
        "model": llm_out.get("model"),
        "tier": llm_out.get("tier"),
        "iteration": iteration,
        "parent_outline_id": body.parent_outline_id,
        "approved": False,
        "consumed_deck_id": None,
        "learning_hint_used": learning_hint,
        "created_at": iso(now()),
    }
    await db.deck_outlines.insert_one(rec)
    rec.pop("_id", None)
    return rec


# ---------------------------------------------------------------------------
# Generate — DEEP tier (Opus). Only fires after outline is approved.
# Consumes 1 deck-quota slot per call.
# ---------------------------------------------------------------------------
def _generate_prompt(outline: Dict[str, Any], ctx_name: str) -> str:
    slides_block = "\n".join(
        f"- Slide {s['n']}: {s.get('title','')} — {s.get('purpose','')}\n"
        f"  Key points: {'; '.join(s.get('key_points') or [])}"
        for s in outline.get("slides") or []
    )
    return (
        "Generate the full slide deck for AKKI in the calm, editorial house "
        "style. Each slide is a markdown block with a title and 3-6 bullet "
        "lines or a short paragraph. Use the approved outline; do not invent "
        "new slides or merge them.\n\n"
        f"CONTEXT: {ctx_name}\n"
        f"AUDIENCE: {outline.get('audience_assumed') or 'board/ExCo'}\n"
        f"RESEARCH QUESTION: {outline.get('research_question') or ''}\n\n"
        "APPROVED OUTLINE:\n" + slides_block + "\n\n"
        "Return STRICT JSON:\n"
        "{\n"
        '  "title": "<deck title, max 90 chars>",\n'
        '  "subtitle": "<single line, max 120 chars>",\n'
        '  "slides": [{"n": 1, "title": "<short>", "body_md": "<markdown body>"}, ...],\n'
        '  "speaker_notes": ["<one note per slide, 1-2 sentences each>"]\n'
        "}\n"
    )


@router.post("/api/contexts/{context_id}/decks/{outline_id}/generate")
async def generate_deck(
    context_id: str,
    outline_id: str,
    body: GenerateIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    if not body.confirmed:
        raise HTTPException(
            status_code=400,
            detail="Deck generation requires explicit confirmation that the outline is approved.",
        )
    outline = await db.deck_outlines.find_one(
        {"id": outline_id, "context_id": context_id},
        {"_id": 0},
    )
    if not outline:
        raise HTTPException(status_code=404, detail="Outline not found.")
    if outline.get("consumed_deck_id"):
        raise HTTPException(
            status_code=409,
            detail="This outline has already produced a deck. Iterate the outline to make a new one.",
        )

    # Apply user edits to the outline before generating (research question
    # tweak, slide titles, etc.). Edits are versioned ON the outline record
    # so re-runs and admin telemetry can see exactly what was generated.
    edits_applied = {}
    if body.edits:
        if body.edits.get("research_question"):
            outline["research_question"] = body.edits["research_question"][:280]
            edits_applied["research_question"] = outline["research_question"]
        if body.edits.get("slides"):
            outline["slides"] = body.edits["slides"]
            edits_applied["slides_edited"] = True
        if body.edits.get("audience_assumed"):
            outline["audience_assumed"] = body.edits["audience_assumed"]
            edits_applied["audience_assumed"] = outline["audience_assumed"]

    ctx_name = ctx["context"].get("name") or "the company"
    prompt = _generate_prompt(outline, ctx_name)

    from llm_tier_quota import call_llm_with_tier
    llm_out, quota_state = await call_llm_with_tier(
        surface="deck",
        account_id=ctx["account"]["id"],
        requested_tier="deep",
        call_args={
            "module": "decks.generate",
            "user_query": prompt,
            "response_format": "json",
        },
    )
    raw = llm_out.get("response") or "{}"
    parsed = _safe_json(raw)
    if not parsed or "slides" not in parsed:
        raise HTTPException(status_code=502, detail="Deck generator returned malformed response.")

    deck_id = str(uuid.uuid4())
    rec = {
        "id": deck_id,
        "context_id": context_id,
        "account_id": ctx["account"]["id"],
        "outline_id": outline_id,
        "intent": outline.get("intent"),
        "research_question": outline.get("research_question"),
        "audience": outline.get("audience_assumed") or outline.get("audience"),
        "title": (parsed.get("title") or "Untitled deck")[:120],
        "subtitle": (parsed.get("subtitle") or "")[:200],
        "slides": parsed.get("slides") or [],
        "speaker_notes": parsed.get("speaker_notes") or [],
        "model": llm_out.get("model"),
        "model_id": llm_out.get("model"),
        "tier": llm_out.get("tier"),
        "quota": quota_state,
        "quality_check": None,
        "user_feedback": None,
        "regen_count": 0,
        "created_at": iso(now()),
    }
    # Iter64 — auto-score sensitivity on every saved artefact (Studio
    # surface contract). Deterministic regex-based scoring; no LLM call.
    try:
        from studio_sensitivity import score_sensitivity
        rec["sensitivity"] = score_sensitivity(rec)
    except Exception as e:  # noqa: BLE001
        logger.warning("Sensitivity scoring failed for deck %s: %s", deck_id, e)
        rec["sensitivity"] = None

    # Phase 11 ITEM B — independent-model validator. Best-effort and
    # non-blocking. The validator helper is contracted to ALWAYS return a
    # dict (even on cap, timeout, no-key, or exception) — null here would
    # mean we lost the diagnostic trail entirely. We therefore default to
    # a "qualified-with-reason" fallback when the import or call site
    # itself raises, so the persisted state is honest about why we
    # couldn't get a real verdict.
    validation_payload = {
        "verdict": "qualified", "confidence": 0,
        "notes": ["Validator wrapper failed before call; treat with normal scrutiny."],
        "validator_provider": "n/a", "validator_model": "n/a",
    }
    try:
        from llm_service import validate_independent
        slide_concat = "\n\n".join(
            f"{s.get('title','')}\n{s.get('body_md','')}"
            for s in (rec.get("slides") or [])
        )
        validation_payload = await validate_independent(
            kind="deck",
            content=slide_concat,
            objective=rec.get("research_question") or rec.get("intent"),
            surface="deck",
            account_id=ctx["account"]["id"],
        )
        logger.info(
            "deck validator persisted event=persisted surface=deck deck_id=%s "
            "verdict=%s provider=%s",
            deck_id,
            validation_payload.get("verdict"),
            validation_payload.get("validator_provider"),
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "deck validator wrapper failed event=wrapper_exception surface=deck "
            "deck_id=%s exc=%s reason=%s",
            deck_id, e.__class__.__name__, str(e)[:200],
        )
        validation_payload = {
            "verdict": "qualified", "confidence": 0,
            "notes": [f"Validator wrapper error ({e.__class__.__name__}); treat with normal scrutiny."],
            "validator_provider": "n/a", "validator_model": "n/a",
        }
    rec["validation"] = validation_payload
    await db.decks.insert_one(rec)
    rec.pop("_id", None)

    # Mark outline as consumed.
    await db.deck_outlines.update_one(
        {"id": outline_id, "context_id": context_id},
        {"$set": {
            "approved": True,
            "consumed_deck_id": deck_id,
            "approved_at": iso(now()),
            "edits_applied": edits_applied or None,
            # Snapshot the post-edit research_question / slides on the outline
            # so admin & history views show what was actually generated.
            "research_question": outline.get("research_question"),
            "slides": outline.get("slides"),
            "audience_assumed": outline.get("audience_assumed"),
        }},
    )

    # Telemetry — used by /admin/llm/spend → deck quality panel.
    await db.deck_telemetry.insert_one({
        "id": str(uuid.uuid4()),
        "deck_id": deck_id,
        "outline_id": outline_id,
        "context_id": context_id,
        "account_id": ctx["account"]["id"],
        "outline_iterations": outline.get("iteration") or 1,
        "context_sufficiency": outline.get("context_sufficiency"),
        "tier_served": llm_out.get("tier"),
        "quota_downgraded": (quota_state or {}).get("downgraded", False),
        "created_at": iso(now()),
    })

    await write_audit(
        context_id, ctx["account"]["id"],
        "deck.generated", "deck", deck_id,
        {"slides": len(rec["slides"]), "tier": rec["tier"],
         "outline_iterations": outline.get("iteration") or 1},
    )
    return rec


# ---------------------------------------------------------------------------
# Quality check — FAST tier; scores deck against original intent + outline.
# Critical: this gives the user a soft refine path that costs ZERO deep
# budget. Without it, dissatisfied users would burn their daily slots
# regenerating.
# ---------------------------------------------------------------------------
def _quality_prompt(deck: Dict[str, Any]) -> str:
    slides = "\n\n".join(
        f"### Slide {s.get('n')}: {s.get('title','')}\n{s.get('body_md','')}"
        for s in (deck.get("slides") or [])
    )
    return (
        "You are AKKI's deck quality auditor. Score how well this deck answers "
        "the user's research question, and surface concrete refinements the user "
        "could make WITHOUT regenerating.\n\n"
        f"USER INTENT: {deck.get('intent')}\n"
        f"RESEARCH QUESTION: {deck.get('research_question')}\n"
        f"AUDIENCE: {deck.get('audience')}\n\n"
        "DECK CONTENT:\n" + slides + "\n\n"
        "Return STRICT JSON:\n"
        "{\n"
        '  "score": 0-100,\n'
        '  "answers_research_question": true|false,\n'
        '  "narrative_coherence": "strong|adequate|weak",\n'
        '  "evidence_density": "high|medium|low",\n'
        '  "audience_fit": "well-matched|partial|mismatched",\n'
        '  "strengths": ["<bullet>", "<bullet>"],\n'
        '  "weaknesses": ["<bullet>", "<bullet>"],\n'
        '  "free_refinements": ["<edit-not-regenerate guidance>", "..."],\n'
        '  "recommend_regenerate": true|false,\n'
        '  "regenerate_reason": "<one line if recommend_regenerate; else null>"\n'
        "}\n"
        "RULES: Recommend regeneration ONLY if score < 55 AND the issues "
        "cannot be fixed by the user editing slides directly."
    )


@router.post("/api/contexts/{context_id}/decks/{deck_id}/quality_check")
async def quality_check(
    context_id: str,
    deck_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    deck = await db.decks.find_one(
        {"id": deck_id, "context_id": context_id},
        {"_id": 0},
    )
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found.")

    from llm_service import call_llm
    llm_out = await call_llm(
        module="decks.quality_check",
        user_query=_quality_prompt(deck),
        response_format="json",
        tier="fast",   # ← Gemini Flash, free of deep budget
    )
    parsed = _safe_json(llm_out.get("response") or "{}")
    if not parsed or "score" not in parsed:
        raise HTTPException(status_code=502, detail="Quality auditor returned malformed response.")

    score = int(parsed.get("score") or 0)
    qc = {
        "score": score,
        "answers_research_question": bool(parsed.get("answers_research_question")),
        "narrative_coherence": parsed.get("narrative_coherence"),
        "evidence_density": parsed.get("evidence_density"),
        "audience_fit": parsed.get("audience_fit"),
        "strengths": parsed.get("strengths") or [],
        "weaknesses": parsed.get("weaknesses") or [],
        "free_refinements": parsed.get("free_refinements") or [],
        "recommend_regenerate": bool(parsed.get("recommend_regenerate")),
        "regenerate_reason": parsed.get("regenerate_reason"),
        "checked_at": iso(now()),
        "model": llm_out.get("model"),
    }
    await db.decks.update_one(
        {"id": deck_id, "context_id": context_id},
        {"$set": {"quality_check": qc}},
    )
    await db.deck_telemetry.update_one(
        {"deck_id": deck_id},
        {"$set": {"quality_score": score,
                  "quality_recommends_regen": qc["recommend_regenerate"]}},
    )
    return {"ok": True, "deck_id": deck_id, "quality_check": qc}


# ---------------------------------------------------------------------------
# Feedback — user signals satisfaction. Cheap, never spends deep budget.
# Drives the admin behaviour-monitoring panel.
# ---------------------------------------------------------------------------
@router.post("/api/contexts/{context_id}/decks/{deck_id}/feedback")
async def feedback(
    context_id: str,
    deck_id: str,
    body: FeedbackIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    deck = await db.decks.find_one(
        {"id": deck_id, "context_id": context_id},
        {"_id": 0, "id": 1},
    )
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found.")

    fb = {
        "rating": body.rating,
        "comment": body.comment,
        "will_regenerate": body.will_regenerate,
        "regen_reason": body.regen_reason,
        "submitted_at": iso(now()),
        "submitted_by": ctx["account"]["id"],
    }
    await db.decks.update_one(
        {"id": deck_id, "context_id": context_id},
        {"$set": {"user_feedback": fb}},
    )
    await db.deck_telemetry.update_one(
        {"deck_id": deck_id},
        {"$set": {"user_rating": body.rating,
                  "user_will_regenerate": body.will_regenerate,
                  "user_regen_reason": body.regen_reason}},
    )
    return {"ok": True, "deck_id": deck_id, "feedback": fb}


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------
@router.get("/api/contexts/{context_id}/decks")
async def list_decks(
    context_id: str,
    limit: int = 30,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    items = await db.decks.find(
        {"context_id": context_id},
        # Phase 11 ITEM B closeout — the list serializer must include
        # `validation` (the badge on `/app/decks` is rendered straight
        # from the list response, not the detail endpoint) and
        # `sensitivity` (the SensitivityChip on each row reads it from
        # here too). Both fields are full sub-documents — boto3-shape
        # projection inclusion lets Mongo return the entire nested
        # object without us having to enumerate sub-keys.
        {"_id": 0, "id": 1, "title": 1, "subtitle": 1, "research_question": 1,
         "audience": 1, "tier": 1, "model_id": 1,
         "created_at": 1, "quality_check.score": 1, "user_feedback.rating": 1,
         "validation": 1, "sensitivity": 1},
    ).sort("created_at", -1).to_list(length=max(1, min(limit, 100)))
    return {"items": items, "count": len(items)}


@router.get("/api/contexts/{context_id}/decks/{deck_id}")
async def get_deck(
    context_id: str,
    deck_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    deck = await db.decks.find_one(
        {"id": deck_id, "context_id": context_id},
        {"_id": 0},
    )
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found.")
    return deck


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _safe_json(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    s = text.strip()
    # Strip code fences if the model returned them despite instructions.
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```\s*$", "", s)
    try:
        return json.loads(s)
    except Exception:  # noqa: BLE001
        # Last-ditch — try to find the first JSON object.
        m = re.search(r"\{.*\}", s, re.DOTALL)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except Exception:  # noqa: BLE001
            return None



# ---------------------------------------------------------------------------
# Context resolver — iter65 deep-link helper.
# Given just a deck_id, returns the context_id the deck belongs to (only if
# the calling user is a member of that context). Used by the frontend to
# auto-switch active context when a /app/decks/{deck_id} deep link points
# to a deck in a context different from the user's currently-active one.
# ---------------------------------------------------------------------------
@router.get("/api/decks/{deck_id}/context")
async def resolve_deck_context(
    deck_id: str,
    account: Dict[str, Any] = Depends(get_current_account),
):
    deck = await db.decks.find_one({"id": deck_id}, {"_id": 0, "id": 1, "context_id": 1})
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found.")
    member = await db.memberships.find_one(
        {"context_id": deck["context_id"], "account_id": account["id"], "status": "active"},
        {"_id": 0, "role": 1},
    )
    if not member:
        raise HTTPException(status_code=403, detail="Not a member of this deck's context.")
    return {"deck_id": deck["id"], "context_id": deck["context_id"]}
