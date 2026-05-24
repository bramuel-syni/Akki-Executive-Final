"""Synisense — `shield_payload`-shape adapter (Phase 12.3 close).

The legacy `backend/llm_service.shield_payload` function returned
``(shielded_text, shield_map_dict)`` where the dict mapped tokens
(`[EMAIL_1]`, `[PHONE_2]`, …) back to the original strings, so callers
could later run `rehydrate(reply_text, shield_map_dict)` to restore PII
in the model's response. That contract is wide and entrenched: chat,
briefings, decks, lens, simulate, signals_ask, prepare, plays, blog,
walkin, learn, pipeline, misc — every surface that calls the LLM
relies on it (most via `llm_service.call_llm`).

The three-layer Synisense pipeline (`pipeline.run` / `pipeline.dryrun`)
is more capable but returns a different envelope:
``{redacted_text, spans[start,end,replacement,...], stats, shield_map_id}``.
This module bridges the two so the legacy callsites can migrate off the
regex shield with no behavioural change in their rehydrate path.

Why this shape, not a refactor of every caller:
  - Phase A scope is "unify shielding without breaking surfaces".
  - Refactoring 14 routers to consume `spans + shield_map_id` would be a
    Phase B-sized blast radius.
  - This adapter is a 30-line shim. It funnels every call through
    `pipeline.dryrun(...)` (same engine: regex → Presidio → LLM
    fallback) and reconstructs the `{token: original}` projection from
    the input text + span offsets so `rehydrate(...)` keeps working.

Mode choice — dryrun, NOT run:
  - dryrun does NOT persist the reversible map to MongoDB.
  - The reversibility we need is **process-local** (the same Python
    request rehydrates its own reply); we do not need server-side
    `unshield(shield_map_id)` for chat-style flows.
  - Skipping persistence saves a Mongo write per LLM call and keeps the
    `db.synisense_shield_maps` TTL collection focused on the surfaces
    that actually need server-side reversal (public_read, studio share).
  - dryrun still records to the perf ring buffer and (via _execute) the
    LLM fallback budget — i.e. the 3-layer engine is fully exercised.

Token shape compatibility:
  - Legacy `shield_payload` produced `[EMAIL_1]`, `[PHONE_1]`, `[IBAN_1]`,
    `[ACCT_1]`, `[CC_1]`, `[SWIFT_1]`, `[NATID_1]`, `[URL_1]`, `[PERSON_1]`.
  - Synisense pipeline produces tokens via `_short_label(entity_type)` →
    `[EMAIL_n]`, `[PHONE_n]`, `[IBAN_n]`, `[CARD_n]`, `[URL_n]`,
    `[PERSON_n]`, `[ORG_n]`, `[LOC_n]`, `[DATE_n]`, … — superset of the
    legacy shape; `rehydrate(text, dict)` is a pure substring replace,
    so any token shape works as long as the dict round-trips.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from . import pipeline as _pipeline
from .shield.exceptions import ShieldFailure

logger = logging.getLogger("akki.synisense.adapter")


# H2.5 (2026-05-24) — Surfaces that are still allowed to degrade open
# when the de-id pipeline raises. Chat-family is INTENTIONALLY excluded
# (chat must fail-closed; the route translates the raised
# `ShieldFailure` into HTTP 503). This list mirrors the
# `services.solva_v2.llm_adapter.shielded_call` discipline — strict by
# default, explicit opt-out only.
_SURFACES_ALLOWING_DEGRADED_OPEN: frozenset[str] = frozenset({
    # Background / batch / admin surfaces where degraded-open is
    # historically expected and the worst case is "no redaction badge
    # rendered" rather than "raw PII reaches the LLM".
    "ingest",      # document ingestion (already pre-redacted at upload)
    "briefing",    # batch briefing generation
    "deck",        # deck export pre-pass
    "report",      # admin report generator
    "enhance",     # work-studio export enhance step
    "sandbox",     # admin sandbox demo-content generator
})


async def shield_payload_async(
    text: str,
    *,
    surface: str = "chat",
    context_id: str = "",
    context_people: Optional[List[str]] = None,
    # Phase J.2 — when chat-family callers pass message_id (+ chat_id +
    # account_id), the call routes to the persisting `pipeline.run()`
    # so the chat audit UI can render a per-message redaction badge.
    # Backward compatible — omitting these kwargs preserves the existing
    # non-persisting `dryrun` behaviour.
    message_id: Optional[str] = None,
    chat_id: Optional[str] = None,
    account_id: Optional[str] = None,
) -> Tuple[str, Dict[str, str]]:
    """Drop-in replacement for `llm_service.shield_payload`.

    Returns ``(shielded_text, shield_map)`` where ``shield_map`` maps
    each replacement token (e.g. ``[EMAIL_1]``) back to the original
    span text. Suitable for ``rehydrate(reply, shield_map)``.

    Surface is required so the perf ring buffer can group results.
    Defaults to ``chat``; pass ``briefing|deck|report|ingest`` etc. when
    you know the call site. Solva v2 callers should keep using the
    strict ``services.solva_v2.llm_adapter.shielded_call`` instead —
    that path goes through ``pipeline.run`` (persists) and refuses on
    Synisense errors.
    """
    if not text:
        return "", {}

    try:
        # Phase J.2 — chat-family callers that pass message_id get the
        # persisting `run()` path so per-message audit metrics work.
        # Everything else keeps the cheaper non-persisting `dryrun`.
        if message_id and surface.startswith("chat"):
            out = await _pipeline.run(
                text=text,
                context_id=context_id or "",
                surface=surface,
                mode="redact",
                account_id=account_id,
                context_people=context_people,
                message_id=message_id,
                chat_id=chat_id,
            )
        else:
            out = await _pipeline.dryrun(
                text=text,
                context_id=context_id or "",
                surface=surface,
                mode="redact",
                context_people=context_people,
            )
    except Exception as exc:  # noqa: BLE001
        # H2.5 (2026-05-24) — surface-aware fail mode. Chat-family
        # and any other surface NOT explicitly enumerated in
        # `_SURFACES_ALLOWING_DEGRADED_OPEN` now FAIL CLOSED: raise
        # `ShieldFailure` so the route returns 503 instead of shipping
        # raw text to the LLM. The legacy degraded-open behaviour
        # remains for background / batch / admin surfaces where the
        # downstream LLM call already operates on pre-redacted text
        # (ingest), or where the operator has explicitly opted in
        # (briefing/deck/report/enhance/sandbox).
        logger.error(
            "synisense.adapter: pipeline failed surface=%s err=%s",
            surface, exc,
        )
        if surface not in _SURFACES_ALLOWING_DEGRADED_OPEN:
            raise ShieldFailure(
                f"Synisense Shield pipeline failed for surface={surface!r}",
                original=exc, surface=surface,
            ) from exc
        return text, {}

    redacted: str = out.get("redacted_text") or text
    spans: List[Dict[str, Any]] = out.get("spans") or []

    # Reconstruct {replacement_token: original_text} from spans + the
    # original input. Each span carries start/end offsets into `text`;
    # the original substring is text[start:end]. Within one run, the
    # pipeline's replacement assignment is deterministic per
    # (entity_type, match_text), so the same email appears as the same
    # token everywhere it occurs — i.e. a single key per real value.
    shield_map: Dict[str, str] = {}
    for s in spans:
        token = s.get("replacement")
        if not token:
            continue
        try:
            original = text[int(s["start"]):int(s["end"])]
        except (KeyError, ValueError, TypeError):
            continue
        # If two distinct spans collide on the same token (shouldn't
        # happen — assignment is by (entity_type, match_text)), the
        # later one wins; we accept that since `rehydrate` is a flat
        # substring substitution, not a positional one.
        shield_map[token] = original
    return redacted, shield_map


def shielding_report(shield_map: Dict[str, str]) -> Dict[str, Any]:
    """UI-friendly bucket counts. NEVER returns the values, only the
    token category counts. Same contract as the legacy
    `llm_service.shielding_report`."""
    by_cat: Dict[str, int] = {}
    for token in shield_map.keys():
        # token shape: "[<LABEL>_<n>]" (or "[<LABEL>]" for unique)
        inner = token.strip("[]")
        cat = inner.rsplit("_", 1)[0].lower()
        by_cat[cat] = by_cat.get(cat, 0) + 1
    return {
        "identifiers_masked": len(shield_map),
        "by_category": by_cat,
        "shielded_by": "synisense-pipeline",
    }


def rehydrate(text: str, shield_map: Dict[str, str]) -> str:
    """Pure-python token → original substring replace. Same contract as
    the legacy `llm_service.rehydrate`. Idempotent if `shield_map` is
    empty (returns text unchanged)."""
    if not shield_map:
        return text
    out = text
    # Replace longer tokens first so [PERSON_10] is not partially
    # consumed by a [PERSON_1] substring replace. Length-desc sort.
    for token, original in sorted(shield_map.items(), key=lambda kv: -len(kv[0])):
        out = out.replace(token, original)
    return out


__all__ = ["shield_payload_async", "shielding_report", "rehydrate"]
