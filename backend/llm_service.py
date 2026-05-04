"""LLM proxy with Synisense-Shield-bound shielding (Phase A unification).

Phase A — `shield_payload`/`rehydrate`/`shielding_report` were removed
from this module. Every outbound LLM call now routes its prompt through
the three-layer Synisense pipeline (regex → Presidio → LLM fallback)
via `services.synisense.shield_payload_async`. The local regex shield
ladder has been retired.

Public functions kept here:
    call_llm()              — shielded send + reply rehydration
    validate_independent()  — independent-family validator (gemini-flash judge)
    parse_json_response()   — tolerant JSON extractor

LLM tier resolution stays env-driven:
    tier="fast"     → Gemini 2.5 Flash
    tier="standard" → Claude Sonnet 4.5 (default)
    tier="deep"     → Claude Opus 4.6 (env: LLM_MODEL_DEEP)
"""
from __future__ import annotations

import json
import logging
import os
import re
import time as _time
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger("akki.llm")

AKKI_SYSTEM_PROMPT = (
    "You are AKKI — an intelligence layer built for non-executive directors and "
    "operating executives of listed and pre-IPO companies. You sit beside them, "
    "reading their board packs, minutes, and operational data, and telling them "
    "what a sharp, experienced board advisor would notice.\n\n"
    "VOICE & POSTURE\n"
    "— You are a colleague with gravitas, not a tool. Think: a seasoned audit-committee "
    "chair with 25 years in the business. Direct, unsentimental, numerate.\n"
    "— You write in complete sentences with specific numbers. You never pad, never "
    "hedge beyond what the evidence warrants, never use corporate filler like "
    "'leverage', 'synergies', 'going forward', or 'in order to'.\n"
    "— When you notice something that management should be uncomfortable about, you "
    "say so plainly. When something is genuinely good, you say that too.\n"
    "— You ask the single question that reveals board-management gap, not five "
    "polite questions that reveal nothing.\n\n"
    "EVIDENCE DISCIPLINE\n"
    "— Every factual claim ties to a specific number or a specific passage in the "
    "caller's documents. If the documents don't contain the answer, you say so "
    "plainly — you do not invent.\n"
    "— When the data trust is 'weak', you flag it explicitly in that reply.\n"
    "— You cite sources inline as [doc:abc123]. Use the full doc_id you see in "
    "the [CONTEXT] or [DOCUMENTS] block; never invent one.\n\n"
    "WHAT YOU DO NOT DO\n"
    "— You do not apologise or preamble ('Certainly!', 'Great question!', 'I'd be "
    "happy to…'). Start with the substance.\n"
    "— You do not produce bullet-point walls where a paragraph is clearer.\n"
    "— You do not write the pack or the letter for them. You critique, you notice, "
    "you surface the thing they need to see."
)


# ---------------------------------------------------------------------------
# Phase A — Synisense surface mapping for `call_llm`.
#
# Every internal "module" string used at a call site (`module="briefing"`,
# `module="decks.outline"`, `module="solve.synthesis"`, …) gets mapped to
# the Synisense pipeline's allow-listed surface ID so the perf ring buffer
# can group results by product surface. Unknown modules fall back to "chat"
# — the safest mid-strict surface.
# ---------------------------------------------------------------------------
_MODULE_SURFACE_PREFIXES = (
    ("solve.", "solve"),
    ("solve_v2.", "solve_v2"),
    ("solva.", "solve_v2"),
    ("briefing", "briefing"),
    ("decks", "deck"),
    ("report-", "report"),
    ("report_", "report"),
    ("highlights", "report"),
    ("ask", "chat"),
    ("walkin", "chat"),
    ("chat", "chat"),
    ("simulate", "chat"),
    ("lens", "chat"),
    ("learn-", "chat"),
    ("learn_", "chat"),
    ("blog-", "report"),
    ("blog_", "report"),
    ("document.", "ingest"),
    ("minutes_", "ingest"),
    ("studio.", "deck"),
    ("strategic_", "report"),
    ("pre_board", "deck"),
)


def _surface_for_module(module: str) -> str:
    m = (module or "").lower()
    for prefix, surface in _MODULE_SURFACE_PREFIXES:
        if m.startswith(prefix):
            return surface
    return "chat"


def build_prompt_layers(
    module: str, user_query: str,
    context_object: Optional[Dict[str, Any]] = None,
    session_context: Optional[Dict[str, Any]] = None,
    data_trust: Optional[Dict[str, Any]] = None,
    system_override: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "layer_1_system": system_override or AKKI_SYSTEM_PROMPT,
        "layer_2_context_object": context_object or {"note": "Context object empty"},
        "layer_3_module": module,
        "layer_4_session_context": session_context or {},
        "layer_5_data_trust": data_trust or {"overall": "unrated"},
        "layer_6_user_query": user_query,
    }


def _assemble_user_prompt(layers: Dict[str, Any]) -> str:
    ctx_obj = json.dumps(layers["layer_2_context_object"], indent=2, default=str)
    sess = json.dumps(layers["layer_4_session_context"], indent=2, default=str)
    dt = json.dumps(layers["layer_5_data_trust"], indent=2, default=str)
    return (
        f"[MODULE] {layers['layer_3_module']}\n\n"
        f"[CONTEXT OBJECT]\n{ctx_obj}\n\n"
        f"[SESSION CONTEXT]\n{sess}\n\n"
        f"[DATA TRUST]\n{dt}\n\n"
        f"[USER REQUEST]\n{layers['layer_6_user_query']}"
    )


async def call_llm(
    module: str, user_query: str,
    context_object: Optional[Dict[str, Any]] = None,
    session_context: Optional[Dict[str, Any]] = None,
    data_trust: Optional[Dict[str, Any]] = None,
    system_override: Optional[str] = None,
    response_format: str = "text",   # "text" or "json"
    tier: str = "standard",          # "fast" | "standard" | "deep"
) -> Dict[str, Any]:
    """Shielded call. Returns {layers, response, mode, model, tier, sources, shielding, synisense_verified}.

    tier="fast"     → Gemini 2.5 Flash (cheap, validation/extraction)
    tier="standard" → Claude Sonnet 4.5 (default — briefs, signals, chat)
    tier="deep"     → Claude Opus (long-form narrative, decks, ExCo blogs)

    response_format="json" instructs the model to return valid JSON only.
    """
    layers = build_prompt_layers(
        module=module, user_query=user_query,
        context_object=context_object, session_context=session_context,
        data_trust=data_trust, system_override=system_override,
    )
    user_prompt = _assemble_user_prompt(layers)

    # Phase A — Synisense pipeline replaces the legacy in-process regex
    # shield. Surface is mapped from the call site's `module` so the perf
    # ring buffer can group by product surface. context_id is best-effort
    # taken from session_context if the caller passed one.
    from services.synisense import (
        shield_payload_async as _syn_shield,
        shielding_report as _syn_report,
        rehydrate as _syn_rehydrate,
    )
    surface = _surface_for_module(module)
    ctx_id = ""
    if isinstance(session_context, dict):
        ctx_id = str(session_context.get("context_id") or "")
    shielded_prompt, shield_map = await _syn_shield(
        user_prompt, surface=surface, context_id=ctx_id,
    )
    shield_report = _syn_report(shield_map)

    emergent_key = os.environ.get("EMERGENT_LLM_KEY")
    system_msg = layers["layer_1_system"]
    if response_format == "json":
        system_msg += (
            "\n\nIMPORTANT: Respond with valid JSON only. No prose, no code fences, "
            "no markdown. Just the JSON object."
        )

    # Resolve tier → (provider, model). Model ids are env-driven so we can swap
    # in newer model versions (e.g. Opus 4.7) without a code change.
    if tier == "fast":
        provider = "gemini"
        model_id = os.environ.get("LLM_MODEL_FAST", "gemini-2.5-flash")
    elif tier == "deep":
        provider = "anthropic"
        # Opus 4.7 is too new for the Emergent key catalogue today; we ship on
        # 4.6 and flip via env when the catalogue catches up.
        model_id = os.environ.get("LLM_MODEL_DEEP", "claude-opus-4-6")
    else:
        provider = "anthropic"
        model_id = os.environ.get("LLM_MODEL_STANDARD", "claude-sonnet-4-5-20250929")

    if not emergent_key:
        return {
            "layers": layers, "mode": "no-key-fallback",
            "model": model_id, "tier": tier,
            "response": "[LLM unavailable — no key configured]",
            "sources": [],
            "shielding": shield_report,
            "synisense_verified": True,
            "synisense_verification_id": f"local-{uuid.uuid4().hex[:10]}",
        }

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        session_id = (session_context or {}).get("session_id") or str(uuid.uuid4())
        chat = LlmChat(
            api_key=emergent_key,
            session_id=session_id,
            system_message=system_msg,
        ).with_model(provider, model_id)
        msg = UserMessage(text=shielded_prompt)
        raw = await chat.send_message(msg)
        raw_text = raw if isinstance(raw, str) else str(raw)
        rehydrated = _syn_rehydrate(raw_text, shield_map)
        return {
            "layers": layers, "mode": "live",
            "model": model_id, "tier": tier,
            "response": rehydrated,
            "sources": [],
            "shielding": shield_report,
            "synisense_verified": True,
            "synisense_verification_id": f"local-{uuid.uuid4().hex[:10]}",
        }
    except Exception as e:
        logger.exception("LLM call failed")
        return {
            "layers": layers, "mode": "error",
            "model": model_id, "tier": tier,
            "response": f"[LLM error: {type(e).__name__}: {e}]",
            "sources": [],
            "shielding": shield_report,
            "synisense_verified": False,
            "synisense_verification_id": None,
            "error": str(e),
        }


def parse_json_response(text: str) -> Optional[Any]:
    """Best-effort JSON extraction from LLM response."""
    if not text:
        return None
    # Strip code fences if Claude included them
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    # Find first { or [ and last } or ]
    try:
        return json.loads(t)
    except Exception:
        pass
    first = min([i for i in [t.find("{"), t.find("[")] if i >= 0], default=-1)
    last = max(t.rfind("}"), t.rfind("]"))
    if first >= 0 and last > first:
        try:
            return json.loads(t[first:last + 1])
        except Exception:
            return None
    return None


# -----------------------------------------------------------------------------
# Independent-model validator — a real second-LLM pass that countersigns
# a piece of generated content. We deliberately route the validator to a
# DIFFERENT provider family from the drafter (drafter = Claude Sonnet 4.5
# → validator = Gemini 2.5 Flash) so the verdict isn't just one model
# nodding at itself.
#
# Returns a small structured verdict the UI can present alongside the
# ValidatedBadge. Soft-fails closed (verdict="qualified", note="validator
# unavailable") rather than blowing up the parent endpoint — the pass is
# additive, never gating.
# -----------------------------------------------------------------------------
async def validate_independent(
    *, kind: str, content: str,
    objective: Optional[str] = None,
    timeout_seconds: float = 12.0,
    surface: Optional[str] = None,
    account_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Run a second-LLM countercheck on `content`. Returns:

        {
          "verdict": "validated" | "qualified" | "flagged",
          "confidence": 0..100,         # validator's confidence
          "notes": [str, ...],          # ≤3 short notes
          "validator_provider": "gemini",
          "validator_model":    "gemini-2.5-flash",
        }

    Phase 11 ITEM B — `surface` and `account_id` are advisory only,
    consumed by `_validator_soft_cap_ok()` to enforce a daily soft cap
    on validator calls. The cap is intentionally a *soft* one: when the
    cap is tripped we return the `fallback` verdict and log the skip,
    never block the parent endpoint. This preserves the invariant that
    validation is additive, never gating — even under cap pressure, the
    drafter output still reaches the user.
    """
    fallback = {
        "verdict": "qualified", "confidence": 60,
        "notes": ["Validator unavailable; treat with normal scrutiny."],
        "validator_provider": "n/a", "validator_model": "n/a",
    }
    started_at = _time.monotonic()
    emergent_key = os.environ.get("EMERGENT_LLM_KEY")
    if not emergent_key:
        logger.warning(
            "validator skipped event=skipped surface=%s reason=no_emergent_key "
            "provider=n/a elapsed_ms=%d account=%s",
            surface, int((_time.monotonic() - started_at) * 1000), account_id,
        )
        return {**fallback, "notes": ["Validator key not configured; treat with normal scrutiny."]}
    if not content or len(content.strip()) < 40:
        logger.warning(
            "validator skipped event=skipped surface=%s reason=content_too_short "
            "len=%d provider=n/a elapsed_ms=%d account=%s",
            surface, len((content or "").strip()),
            int((_time.monotonic() - started_at) * 1000), account_id,
        )
        return {**fallback, "notes": ["Content too short for second-pass review."]}

    # Phase 11 ITEM B — daily soft cap. Persisted counter per UTC day.
    # When the cap is tripped we short-circuit to the fallback and log.
    # Cap bypass is intentional on surface == "briefing" because
    # briefings are the highest-trust surface and have shipped with a
    # real validator since iter50; we don't want a noisy cap to start
    # qualifying previously-validated briefings.
    if surface and surface != "briefing":
        cap_ok = await _validator_soft_cap_ok(surface=surface)
        if not cap_ok:
            logger.warning(
                "validator skipped event=cap_tripped surface=%s reason=daily_soft_cap "
                "provider=n/a elapsed_ms=%d account=%s",
                surface, int((_time.monotonic() - started_at) * 1000), account_id,
            )
            return {
                **fallback,
                "notes": ["Daily validator cap reached; read with normal scrutiny."],
            }

    instruction = (
        "You are an independent verifier — a different model from the one "
        "that drafted the content below. Read the draft carefully and judge: "
        "(a) Does it overreach beyond what it could reasonably ground? "
        "(b) Are claims internally consistent? (c) Is the tone calm, "
        "specific, and useful for an executive? Be honest, not polite.\n\n"
        f"Kind: {kind}\n"
        + (f"Drafter's objective: {objective}\n" if objective else "")
        + "\nDRAFT TO VERIFY:\n"
        + content[:6000]
        + "\n\nReturn STRICT JSON ONLY: "
          "{\"verdict\": \"validated\"|\"qualified\"|\"flagged\","
          "\"confidence\": 0..100,"
          "\"notes\": [\"<<≤3 short notes (≤14 words each)>>\"]}"
    )

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(
            api_key=emergent_key,
            session_id=f"validator-{uuid.uuid4().hex[:10]}",
            system_message=(
                "You are AKKI's second-pass validator. Independent of the drafter. "
                "Be terse. JSON only. Never invent facts. If the draft is fine, say so."
            ),
        ).with_model("gemini", "gemini-2.5-flash")
        msg = UserMessage(text=instruction)
        import asyncio as _asyncio
        raw = await _asyncio.wait_for(chat.send_message(msg), timeout=timeout_seconds)
        parsed = parse_json_response(raw if isinstance(raw, str) else str(raw)) or {}
        if not parsed:
            logger.warning(
                "validator empty event=empty_response surface=%s reason=parse_failed "
                "provider=gemini elapsed_ms=%d account=%s",
                surface, int((_time.monotonic() - started_at) * 1000), account_id,
            )
            return {
                **fallback,
                "validator_provider": "gemini", "validator_model": "gemini-2.5-flash",
                "notes": ["Validator returned an unparseable response; treat with normal scrutiny."],
            }
        verdict = str(parsed.get("verdict") or "qualified").lower()
        if verdict not in {"validated", "qualified", "flagged"}:
            verdict = "qualified"
        try:
            confidence = max(0, min(100, int(parsed.get("confidence") or 70)))
        except (TypeError, ValueError):
            confidence = 70
        notes = [str(n).strip()[:140] for n in (parsed.get("notes") or []) if str(n).strip()][:3]
        elapsed = int((_time.monotonic() - started_at) * 1000)
        logger.info(
            "validator ok event=ok surface=%s verdict=%s confidence=%d "
            "provider=gemini elapsed_ms=%d account=%s",
            surface, verdict, confidence, elapsed, account_id,
        )
        return {
            "verdict": verdict, "confidence": confidence,
            "notes": notes or ["No issues flagged."],
            "validator_provider": "gemini",
            "validator_model": "gemini-2.5-flash",
        }
    except Exception as e:  # noqa: BLE001
        elapsed = int((_time.monotonic() - started_at) * 1000)
        if e.__class__.__name__ == "TimeoutError":
            logger.warning(
                "validator timeout event=timeout surface=%s reason=%ss "
                "provider=gemini elapsed_ms=%d account=%s",
                surface, timeout_seconds, elapsed, account_id,
            )
            return {**fallback, "notes": ["Validator timed out; pass treated as qualified."]}
        logger.warning(
            "validator failed event=exception surface=%s reason=%s "
            "exc=%s provider=gemini elapsed_ms=%d account=%s",
            surface, e.__class__.__name__, str(e)[:200], elapsed, account_id,
        )
        return {**fallback, "notes": [f"Validator error ({e.__class__.__name__}); treat with normal scrutiny."]}


# -----------------------------------------------------------------------------
# Phase 11 ITEM B — validator soft-cap. Persisted counter per UTC day so we
# never accidentally rack up a six-figure Gemini bill if one surface loops.
# The cap is advisory only: `validate_independent()` short-circuits to the
# `qualified` fallback when tripped, and the drafter's output still ships.
# -----------------------------------------------------------------------------
_VALIDATOR_DEFAULT_DAILY_CAP = 200


async def _validator_soft_cap_ok(*, surface: str) -> bool:
    """Return True if the validator may run for `surface` today. Increments
    the counter before the call so the cap is strictly enforced even under
    concurrency — the unique compound index on (day_utc, surface) means
    two parallel increments don't double-count."""
    try:
        from core import db
        from datetime import datetime as _dt, timezone as _tz
        day = _dt.now(_tz.utc).strftime("%Y-%m-%d")
        cap = int(os.environ.get("VALIDATOR_DAILY_SOFT_CAP", _VALIDATOR_DEFAULT_DAILY_CAP))
        # Atomically increment + read. `find_one_and_update` with upsert
        # returns the POST-update doc when `return_document=AFTER`.
        from pymongo import ReturnDocument
        doc = await db.llm_validator_usage.find_one_and_update(
            {"day_utc": day, "surface": surface},
            {"$inc": {"count": 1},
             "$setOnInsert": {"day_utc": day, "surface": surface,
                              "created_at": _dt.now(_tz.utc).isoformat()}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        current = int((doc or {}).get("count") or 1)
        if current > cap:
            # Roll the increment back so the counter doesn't run away
            # across retries once we're over cap. Best-effort; if it
            # fails we still return False.
            try:
                await db.llm_validator_usage.update_one(
                    {"day_utc": day, "surface": surface},
                    {"$inc": {"count": -1}},
                )
            except Exception:  # noqa: BLE001
                pass
            return False
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning("validator soft-cap check failed (allowing call): %s", e)
        return True
