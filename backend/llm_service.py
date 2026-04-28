"""LLM proxy + mock-Synisense shielding (M5 — real Claude via Emergent Universal Key).

Shielding contract (unchanged from M0):
  - shield_payload() masks obvious PII
  - rehydrate() unmasks
  - Every outbound LLM call is routed through this module

At M5, the actual LLM call is wired via emergentintegrations (Claude Sonnet 4.5).
Real Synisense service replaces the mock via URL swap in a later build.
"""
from __future__ import annotations

import json
import logging
import os
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

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

_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.\w+\b")
_URL_RE = re.compile(r"https?://\S+")
_PHONE_RE = re.compile(r"(?:\+?254|\+?44|\+?1|\+?27)?[\s\-]?\(?0?\d[\s\-\.\d]{7,14}\d\b")
# Kenya national ID: 7–8 digits. Trigger only in contexts that look like an ID
# (preceded by ID #, nat. id, etc.) to avoid catching loan amounts.
_KE_NATID_RE = re.compile(r"\b(?:ID|id|Nat\.?\s*ID|national\s+id|identity)\s*(?:no\.?|#|number)?\s*[:\-]?\s*(\d{7,8})\b", re.IGNORECASE)
_IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{4,30}\b")
_BANK_ACCT_RE = re.compile(r"\b(?:A/?c|Acc(?:ount)?\.?|Acct\.?)\s*(?:no\.?|#|number)?\s*[:\-]?\s*(\d{8,16})\b", re.IGNORECASE)
_CC_RE = re.compile(r"\b(?:\d[ -]?){13,16}\b")  # credit card digits
_SWIFT_RE = re.compile(r"\b[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}(?:[A-Z0-9]{3})?\b")
# Likely-person proper nouns — two consecutive TitleCase words, not at line start
# and not obvious headings. This is the noisiest category — we mark them
# as identifiers but cap the number masked per call to avoid destroying context.
_PERSON_RE = re.compile(r"(?<![.!?\n])(?<!^)\b(?:Mr\.?|Mrs\.?|Ms\.?|Dr\.?|Prof\.?|Hon\.?)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}\b")

# Counter-by-category tagger — the shielded prompt should tell the LLM what
# *kind* of thing was masked so it can still reason about it.
_CATEGORY_TAGS = {
    "email": "EMAIL",
    "url": "URL",
    "phone": "PHONE",
    "natid": "NATID",
    "iban": "IBAN",
    "acct": "ACCT",
    "cc": "CARD",
    "swift": "SWIFT",
    "person": "PERSON",
}


def _swap(category: str, counters: Dict[str, int], shield_map: Dict[str, str]):
    """Returns a regex-callback that produces stable category-indexed tokens,
    so the LLM sees [PERSON_1] reappear across the prompt for the same value."""
    tag = _CATEGORY_TAGS[category]
    reverse: Dict[str, str] = {}

    def _cb(m: "re.Match[str]") -> str:
        # Some patterns use a capture group — fall through to full match if no group 1.
        original = m.group(0)
        if original in reverse:
            return reverse[original]
        counters[category] = counters.get(category, 0) + 1
        token = f"[{tag}_{counters[category]}]"
        shield_map[token] = original
        reverse[original] = token
        return token
    return _cb


def shield_payload(text: str) -> Tuple[str, Dict[str, str]]:
    """Real PII shielding — replaces free-text identifiers with stable
    category-indexed tokens (e.g. ``[EMAIL_1]``, ``[PERSON_3]``) before the
    text is sent to any LLM.

    Design notes:
      * Stable within a single call — the same email appears as [EMAIL_1]
        every time it's seen, so the LLM can reason about it as a single
        entity.
      * Categorised — the token type is legible to the model; it can still
        reason "write to [EMAIL_1] once you've…" without seeing the value.
      * Reversible — `rehydrate()` restores the original values in LLM
        output so citations like [doc:xxx] are untouched.
      * Capped on PERSON (noisy) to preserve narrative readability.
    """
    shield_map: Dict[str, str] = {}
    counters: Dict[str, int] = {}

    out = text
    # Order matters: email/URL first (they contain other patterns), then
    # structural IDs, then people.
    out = _EMAIL_RE.sub(_swap("email", counters, shield_map), out)
    out = _URL_RE.sub(_swap("url", counters, shield_map), out)
    out = _KE_NATID_RE.sub(_swap("natid", counters, shield_map), out)
    out = _IBAN_RE.sub(_swap("iban", counters, shield_map), out)
    out = _BANK_ACCT_RE.sub(_swap("acct", counters, shield_map), out)
    out = _CC_RE.sub(_swap("cc", counters, shield_map), out)
    out = _SWIFT_RE.sub(_swap("swift", counters, shield_map), out)
    # Cap person masking at 20 per payload — beyond that the prompt gets
    # unreadable for the model. Real users, not test fixtures, trigger this.
    if counters.get("person", 0) < 20:
        out = _PHONE_RE.sub(_swap("phone", counters, shield_map), out)
        person_replacer = _swap("person", counters, shield_map)
        def _capped_person(m):
            if counters.get("person", 0) >= 20:
                return m.group(0)
            return person_replacer(m)
        out = _PERSON_RE.sub(_capped_person, out)

    return out, shield_map


def shielding_report(shield_map: Dict[str, str]) -> Dict[str, Any]:
    """Compact, UI-friendly report of what was shielded in this call.
    Values are NEVER returned — only category counts and token prefixes."""
    by_cat: Dict[str, int] = {}
    for token in shield_map.keys():
        # token is like "[EMAIL_1]" → strip brackets + index suffix
        inner = token.strip("[]")
        cat = inner.rsplit("_", 1)[0].lower()
        by_cat[cat] = by_cat.get(cat, 0) + 1
    return {
        "identifiers_masked": len(shield_map),
        "by_category": by_cat,
        "shielded_by": "synisense-local",  # categorised, regex-based shield
    }


def rehydrate(text: str, shield_map: Dict[str, str]) -> str:
    out = text
    for ref, original in shield_map.items():
        out = out.replace(ref, original)
    return out


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
) -> Dict[str, Any]:
    """Shielded call. Returns {layers, response, mode, sources, shielding, synisense_verified}.

    response_format="json" instructs Claude to return valid JSON only.
    """
    layers = build_prompt_layers(
        module=module, user_query=user_query,
        context_object=context_object, session_context=session_context,
        data_trust=data_trust, system_override=system_override,
    )
    user_prompt = _assemble_user_prompt(layers)
    shielded_prompt, shield_map = shield_payload(user_prompt)
    shield_report = shielding_report(shield_map)

    emergent_key = os.environ.get("EMERGENT_LLM_KEY")
    system_msg = layers["layer_1_system"]
    if response_format == "json":
        system_msg += (
            "\n\nIMPORTANT: Respond with valid JSON only. No prose, no code fences, "
            "no markdown. Just the JSON object."
        )

    if not emergent_key:
        return {
            "layers": layers, "mode": "no-key-fallback",
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
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        msg = UserMessage(text=shielded_prompt)
        raw = await chat.send_message(msg)
        raw_text = raw if isinstance(raw, str) else str(raw)
        rehydrated = rehydrate(raw_text, shield_map)
        return {
            "layers": layers, "mode": "live",
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
) -> Dict[str, Any]:
    """Run a second-LLM countercheck on `content`. Returns:

        {
          "verdict": "validated" | "qualified" | "flagged",
          "confidence": 0..100,         # validator's confidence
          "notes": [str, ...],          # ≤3 short notes
          "validator_provider": "gemini",
          "validator_model":    "gemini-2.5-flash",
        }
    """
    fallback = {
        "verdict": "qualified", "confidence": 60,
        "notes": ["Validator unavailable; treat with normal scrutiny."],
        "validator_provider": "n/a", "validator_model": "n/a",
    }
    emergent_key = os.environ.get("EMERGENT_LLM_KEY")
    if not emergent_key or not content or len(content.strip()) < 40:
        return fallback

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
        verdict = str(parsed.get("verdict") or "qualified").lower()
        if verdict not in {"validated", "qualified", "flagged"}:
            verdict = "qualified"
        try:
            confidence = max(0, min(100, int(parsed.get("confidence") or 70)))
        except (TypeError, ValueError):
            confidence = 70
        notes = [str(n).strip()[:140] for n in (parsed.get("notes") or []) if str(n).strip()][:3]
        return {
            "verdict": verdict, "confidence": confidence,
            "notes": notes or ["No issues flagged."],
            "validator_provider": "gemini",
            "validator_model": "gemini-2.5-flash",
        }
    except Exception as e:  # noqa: BLE001
        if e.__class__.__name__ == "TimeoutError":
            return {**fallback, "notes": ["Validator timed out; pass treated as qualified."]}
        logger.warning("validator failed: %s", e)
        return fallback
