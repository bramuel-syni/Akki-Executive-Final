"""Track A Phase 7 (2026-06-05) — Work Studio document-level confidence
scorer.

Compute path for `intelligence_report.confidence_pct` on
`work_studio_exports` rows. Until this lands, only `scripts/seed_chunks.py`
wrote that field (static demo seeds), and real compiled docs shipped
with `confidence_pct: None`. Phase 7 closes the gap.

Architecture:
  1. Compile-time (`_run_export` + `_run_enhance` in routers/work_studio_export.py):
     after the LLM pass returns structured_content + before the row
     flips to status="complete", call `score_confidence()`. If it
     returns a valid score, write it onto `intelligence_report`. If
     it returns `None` (skip / fail), flag the failure and leave
     confidence_pct unset.

  2. Commit-time recompute (`commit_document` in routers/work_studio_overlay.py):
     idempotency-gated by `confidence_scored_at_cache_key` — if the
     structured_content hash matches the cached key, skip the recompute
     entirely (Tightening 4: credit-saver). Else call score again,
     write new confidence_pct + confidence_recomputed_at.

Failure modes (NO silent swallows — Guard Rail 2):
  • shield_invoke timeout / network → log.exception + return None + flag
  • Shield refusal → log.warning + return None + flag
  • malformed JSON → log.exception + return None + flag
  • out-of-range dim scores → log.warning + clamp to [0,100] + proceed
  • empty source_document_ids → log + skip + return None (no flag — not
    a failure, a deliberate refusal of the rubric without sources)

Rubric (Phase 7 Pre-Read §2):
  • source_coverage           weight 40%
  • internal_consistency      weight 25%
  • gap_clarity               weight 20%
  • recommendation_grounding  weight 15%   (defaults to 100 when no recs)

Aggregator is deterministic; weighted average, clamped to [0,100], rounded.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.synisense.shield.client import invoke as shield_invoke

logger = logging.getLogger(__name__)


# Weights — Pre-Read §2.1 (Phase 7).
_WEIGHTS = {
    "source_coverage":           0.40,
    "internal_consistency":      0.25,
    "gap_clarity":               0.20,
    "recommendation_grounding":  0.15,
}

_DIMENSIONS = list(_WEIGHTS.keys())


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def structured_content_hash(structured_content: Optional[Dict[str, Any]]) -> str:
    """SHA-256 over a canonical-sorted JSON serialisation of the
    structured_content. Used as the idempotency key on commit-time
    recompute (Tightening 4)."""
    canonical = json.dumps(
        structured_content or {},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _render_document_for_prompt(structured_content: Dict[str, Any], title: str, kind: str) -> str:
    """Flatten the structured_content into a prompt-friendly string."""
    sections = (structured_content or {}).get("sections") or []
    rendered_sections = []
    for i, s in enumerate(sections):
        heading = s.get("heading") or f"Section {i}"
        paragraphs = s.get("paragraphs") or []
        body = "\n".join(p for p in paragraphs if isinstance(p, str))
        rendered_sections.append(f"## {heading}\n{body}")
    body = "\n\n".join(rendered_sections) or "[empty document]"
    return f"Title: {title or '—'}\nKind: {kind or '—'}\n\n{body}"


def _render_sources_for_prompt(source_blobs: List[Dict[str, Any]]) -> str:
    """source_blobs: list of {id, name, extracted_text}. Capped at 20
    docs, 6000 chars each, per Pre-Read §2.2."""
    if not source_blobs:
        return "[no source documents]"
    blocks = []
    for blob in source_blobs[:20]:
        name = blob.get("name") or blob.get("id") or "source"
        text = (blob.get("extracted_text") or "")[:6000]
        blocks.append(f"--- {name} ---\n{text}")
    return "\n\n".join(blocks)


def _build_score_prompt(
    *,
    document_title: str,
    document_kind: str,
    structured_content: Dict[str, Any],
    source_blobs: List[Dict[str, Any]],
) -> str:
    """Verbatim from Phase 7 Pre-Read §2.2. NEVER edit this without
    re-Pre-Reading the rubric."""
    doc_render = _render_document_for_prompt(
        structured_content, document_title, document_kind,
    )
    sources_render = _render_sources_for_prompt(source_blobs)
    return (
        "You are AKKI's confidence scorer for a Work Studio document. "
        "You will score the document against the source documents it "
        "cites along four dimensions, output a strict-JSON response, "
        "and produce a 1-2 sentence rationale that the user will see "
        "on hover.\n\n"
        "Do NOT introduce external knowledge. You can ONLY use the "
        "document and the source documents below. If you don't have "
        "enough evidence to score a dimension, score it at 50 "
        "(neutral) and note the missing evidence in the rationale.\n\n"
        "Operating preferences apply: no glazing, no hedging weasel "
        "words, lead with the substance. Direct, audit-trail prose. "
        "Voice-lint enforced.\n\n"
        "=== WORK STUDIO DOCUMENT (TO SCORE) ===\n"
        f"{doc_render}\n\n"
        "=== SOURCE DOCUMENTS (allowlisted; the doc was generated from these) ===\n"
        f"{sources_render}\n\n"
        "=== TASK ===\n"
        "Score the document along these 4 dimensions (each 0-100):\n\n"
        "1. source_coverage: What percentage of substantive claims in "
        "the document are explicitly tied to a source document above? "
        "Count inline citations, footnotes, and any '(per [Doc A])' "
        "patterns. 100 = every substantive claim has a citation. "
        "50 = half do. 0 = no claims cite sources.\n\n"
        "2. internal_consistency: Does the document contradict itself "
        "across sections? 100 = no contradictions, sections support "
        "each other coherently. 50 = one or two minor tensions surface "
        "but nothing fatal. 0 = sections contradict at the headline "
        "level.\n\n"
        "3. gap_clarity: Does the document explicitly acknowledge "
        "what it doesn't know? (Missing data, assumptions made, "
        "scenarios refused.) 100 = a clear 'what we don't know' "
        "section + per-claim hedging where evidence is thin. 50 = some "
        "hedging but no consolidated gap section. 0 = doc presents "
        "itself as definitive with no acknowledged uncertainty.\n\n"
        "4. recommendation_grounding: If the document contains "
        "recommendations (numbered actions, 'we should ...', 'the "
        "right move is ...'), are they tied to evidence cited above? "
        "100 = every rec cites its evidence. 0 = recs are evidence-"
        "free assertions. If the document contains NO recommendations, "
        "return 100 (this dimension does not penalise documents that "
        "don't make recs).\n\n"
        "OUTPUT STRICT JSON ONLY (no prose, no fences):\n"
        "{\n"
        '  "source_coverage":           <int 0-100>,\n'
        '  "internal_consistency":      <int 0-100>,\n'
        '  "gap_clarity":               <int 0-100>,\n'
        '  "recommendation_grounding":  <int 0-100>,\n'
        '  "rationale": "<1-2 SENTENCE PROSE EXPLANATION, max 240 chars, surfacing the dominant signal>"\n'
        "}"
    )


def _strip_json_fence(s: str) -> str:
    """Strip ```json … ``` and similar."""
    s = (s or "").strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[-1] if "\n" in s else ""
        if s.endswith("```"):
            s = s[: -3]
        s = s.strip()
    return s


def _clamp(v: Any) -> int:
    try:
        x = int(round(float(v)))
    except (TypeError, ValueError):
        return 50  # mid-rail when we can't parse a score
    return max(0, min(100, x))


def _aggregate(dims: Dict[str, int]) -> int:
    """Weighted average, clamped, rounded."""
    total = 0.0
    for k, w in _WEIGHTS.items():
        total += w * float(dims[k])
    return max(0, min(100, int(round(total))))


async def score_confidence(
    *,
    document_title: str,
    document_kind: str,
    structured_content: Dict[str, Any],
    source_blobs: List[Dict[str, Any]],
    tenant_id: str,
    consumer_id: str = "work_studio_confidence",
) -> Optional[Dict[str, Any]]:
    """Score a Work Studio document's overall confidence via a Shield
    call. Returns a dict with `confidence_pct`, `rationale`,
    `scored_at`, `breakdown`, `cache_key`, `audit_id`, OR `None` on
    skip / failure.

    Returns `None` when:
      • source_blobs is empty (deliberate skip — rubric requires sources)
      • Shield call raises (timeout, refusal, network)
      • response is unparseable as JSON
      • response is missing required dimension keys

    The caller is expected to interpret `None` as "no scorer signal"
    and surface a `confidence_score_failed: true` flag on the doc row
    (except for the empty-sources skip, which is `confidence_score_skipped_no_sources`).
    """
    if not source_blobs:
        logger.info(
            "confidence_score_skipped_no_sources",
            extra={"document_title": document_title, "document_kind": document_kind},
        )
        return None

    prompt = _build_score_prompt(
        document_title=document_title,
        document_kind=document_kind,
        structured_content=structured_content,
        source_blobs=source_blobs,
    )

    try:
        shield_result = await shield_invoke(
            purpose="work_studio.document.confidence_score",
            content=prompt,
            tenant_id=tenant_id,
            consumer_id=consumer_id,
            user_id=tenant_id,
            model_preference="analytical",
            internal_caller=True,
        )
    except Exception:  # noqa: BLE001 — Shield raises one of four
        # SynisenseError subclasses + network errors; we surface all
        # uniformly as "scorer failed". The except is documented in
        # Pre-Read §6.
        logger.exception("confidence_score_shield_error")
        return None

    raw = shield_result.get("response") or ""
    parsed: Optional[Dict[str, Any]] = None
    try:
        parsed = json.loads(_strip_json_fence(raw))
    except (ValueError, TypeError):
        logger.exception(
            "confidence_score_malformed_json",
            extra={"raw_head": raw[:200] if isinstance(raw, str) else None},
        )
        return None

    if not isinstance(parsed, dict):
        logger.warning("confidence_score_response_not_dict", extra={"type": type(parsed).__name__})
        return None

    dims: Dict[str, int] = {}
    for k in _DIMENSIONS:
        if k not in parsed:
            logger.warning("confidence_score_missing_dim", extra={"dim": k})
            return None
        v = parsed[k]
        clamped = _clamp(v)
        if clamped != v:
            logger.warning(
                "confidence_score_out_of_range_or_coerced",
                extra={"dim": k, "received": v, "clamped": clamped},
            )
        dims[k] = clamped

    rationale = (parsed.get("rationale") or "").strip()[:240]

    pct = _aggregate(dims)

    return {
        "confidence_pct":   pct,
        "rationale":        rationale,
        "scored_at":        _now_iso(),
        "breakdown":        dims,
        "cache_key":        structured_content_hash(structured_content),
        "audit_id":         shield_result.get("audit_id"),
    }
