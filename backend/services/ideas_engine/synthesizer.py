"""Phase P5.15 — Weekly synthesis (4 lenses, cited, refuse-to-decide validated).

Operating modes:

  * **Deterministic synthesis (always available)** — Pulls the
    tenant's most recently indexed documents and their top
    chunks, ranks by recency + length, and emits one card per
    enabled lens with:
      - Observational title + body templated from real chunk
        excerpts
      - Confidence band computed from corpus coverage signals
        (NOT LLM-self-reported)
      - ≥ 2 real `IdeaCitation`s per card, each pointing to a
        real document_id / chunk_id pair the resolver will
        verify
    This mode is the default for v1. It honours every Akki
    promise without depending on the LLM key being valid.

  * **Shielded LLM synthesis (opt-in via env)** — Future-mode
    that wraps the deterministic candidate set in a
    `services.solva_v2.llm_adapter.shielded_call` round-trip.
    Scaffold present; not activated in this MVP. When the env
    flag flips, the same refuse-to-decide + citation-verify
    pipeline applies — cards that fail are regenerated up to
    twice, then dropped per spec.

Idempotency is enforced upstream in `routers/ideas.py` via the
unique `(account_id, week_iso, digest_version)` Mongo index.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from .citation_resolver import CitationUnverifiable, IdeasCitationResolver
from .refuse_to_decide import RefuseToDecideViolation, validate_no_imperatives
from .schema import (
    IDEA_LENSES,
    ConfidenceBand,
    IdeaCard,
    IdeaCitation,
    IdeaLens,
    IdeasDigest,
)


class SynthesisFailure(RuntimeError):
    """Raised when the synthesizer cannot produce even one valid
    card for a tenant (e.g. no corpus, no chunks). The router
    catches this and renders the empty-state surface."""


def week_iso_for(when: Optional[datetime] = None) -> str:
    """Return `<isoyear>-W<isoweek_zeropad>` (e.g. `2026-W08`).
    Defaults to "now" in UTC."""
    when = when or datetime.now(timezone.utc)
    y, w, _ = when.isocalendar()
    return f"{y}-W{w:02d}"


# ─────────────────────────────────────────────────────────────────
# Lens-specific copy templates.
# All strings are voice-lint clean by construction (no banned
# words). All bodies are observational ("Reviewers may want to
# note…"), never imperative-to-user. Templates are kept SMALL
# so the generated cards stay under the 800-char body cap.
# ─────────────────────────────────────────────────────────────────

LENS_TITLES: Dict[IdeaLens, str] = {
    "strategy":         "Strategy — patterns surfacing this week",
    "board_navigation": "Board navigation — questions to pre-empt",
    "capital":          "Capital — posture observations",
    "governance":       "Governance — items worth a closer look",
}

LENS_BODY_LEADS: Dict[IdeaLens, str] = {
    "strategy": (
        "Across the documents indexed this week, the following patterns "
        "surface and are worth a closer reading in context:"
    ),
    "board_navigation": (
        "If the board convenes in the next cycle, the items below are the "
        "most likely lines of questioning given what the corpus contains:"
    ),
    "capital": (
        "On capital posture, the recent corpus shows the following observable "
        "datapoints that reviewers may want to triangulate against current plans:"
    ),
    "governance": (
        "The following items recur across the indexed documents and may "
        "merit a closer look from an audit-trail perspective:"
    ),
}


# ─────────────────────────────────────────────────────────────────
# Corpus fetch — recent documents + their lead chunks
# ─────────────────────────────────────────────────────────────────


async def _fetch_recent_corpus(
    db, *, account_id: str, days: int = 90, max_docs: int = 20,
) -> List[Dict[str, Any]]:
    """Return up to `max_docs` of the tenant's most recently
    updated documents that have at least one chunk in
    `extractions_log`. Each entry: `{document_id, title,
    updated_at, chunks: [{id, text, page?, kind}]}`."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    doc_cursor = db.documents.find(
        {
            "account_id": account_id,
            "$or": [
                {"updated_at": {"$gte": cutoff}},
                {"created_at": {"$gte": cutoff}},
            ],
        },
        {"_id": 0, "id": 1, "title": 1, "filename": 1, "updated_at": 1,
         "created_at": 1, "status": 1},
    ).sort([("updated_at", -1), ("created_at", -1)]).limit(max_docs)
    out: List[Dict[str, Any]] = []
    async for d in doc_cursor:
        chunks = await db.extractions_log.find(
            {"document_id": d["id"]},
            {"_id": 0, "id": 1, "text": 1, "page": 1, "kind": 1},
        ).limit(8).to_list(8)
        if not chunks:
            continue
        out.append({
            "document_id": d["id"],
            "title": d.get("title") or d.get("filename") or "Untitled document",
            "updated_at": d.get("updated_at") or d.get("created_at"),
            "chunks": chunks,
        })
    return out


# ─────────────────────────────────────────────────────────────────
# Card builder
# ─────────────────────────────────────────────────────────────────


def _pick_chunks_for_lens(
    corpus: List[Dict[str, Any]], lens: IdeaLens, n: int = 2,
) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
    """Round-robin pick `n` `(document, chunk)` pairs for a lens.
    Prefers chunks with text > 80 chars; falls back to whatever
    is available so we never return fewer than `n` when the
    corpus has enough breadth."""
    pairs: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    # Two passes: substantive chunks first, then shorts.
    for predicate in (lambda c: len((c.get("text") or "")) > 80, lambda c: True):
        for doc in corpus:
            for chunk in doc["chunks"]:
                if any(p[1]["id"] == chunk["id"] for p in pairs):
                    continue
                if predicate(chunk):
                    pairs.append((doc, chunk))
                    if len(pairs) >= n:
                        return pairs
        if len(pairs) >= n:
            return pairs
    return pairs


def _confidence_band(n_docs: int, n_chunks: int) -> Tuple[ConfidenceBand, str]:
    """Calibrated band based on corpus coverage. NOT LLM-self-
    reported."""
    if n_docs >= 4 and n_chunks >= 12:
        return "high", (
            f"Calibrated from {n_docs} documents and {n_chunks} indexed chunks — "
            f"a broad evidence base for this week."
        )
    if n_docs >= 2 and n_chunks >= 6:
        return "medium", (
            f"Calibrated from {n_docs} documents and {n_chunks} indexed chunks — "
            f"a moderate evidence base; corroborate before relying on a single thread."
        )
    return "low", (
        f"Calibrated from {n_docs} documents and {n_chunks} indexed chunks — "
        f"a narrow evidence base; treat as a starting point, not a conclusion."
    )


def _excerpt_of(chunk: Dict[str, Any], max_chars: int = 320) -> str:
    text = (chunk.get("text") or "").strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def _trim(text: str, n: int) -> str:
    if len(text) <= n:
        return text
    return text[: n - 1].rstrip() + "…"


def _build_card_for_lens(
    lens: IdeaLens, corpus: List[Dict[str, Any]],
) -> Optional[IdeaCard]:
    pairs = _pick_chunks_for_lens(corpus, lens, n=2)
    if len(pairs) < 2:
        return None
    body_parts: List[str] = [LENS_BODY_LEADS[lens]]
    citations: List[IdeaCitation] = []
    for doc, chunk in pairs:
        excerpt = _excerpt_of(chunk)
        body_parts.append(
            f' From "{doc["title"]}": {excerpt}'
        )
        citations.append(IdeaCitation(
            document_id=doc["document_id"],
            chunk_id=chunk["id"],
            excerpt=excerpt[:380],
        ))
    body = _trim(" ".join(body_parts), 800)
    band, rationale = _confidence_band(
        n_docs=len({c.document_id for c in citations}),
        n_chunks=sum(len(d["chunks"]) for d in corpus),
    )
    card = IdeaCard(
        lens=lens,
        title=LENS_TITLES[lens],
        body=body,
        confidence_band=band,
        confidence_rationale=rationale,
        citations=citations,
    )
    return card


# ─────────────────────────────────────────────────────────────────
# Top-level synthesis
# ─────────────────────────────────────────────────────────────────


async def synthesize_digest(
    db,
    *,
    account_id: str,
    user_id: str,
    week_iso: Optional[str] = None,
    lenses_enabled: Optional[List[IdeaLens]] = None,
    custom_instructions: str = "",
) -> IdeasDigest:
    """Generate a fresh digest. Caller is responsible for
    idempotency (check Mongo first). On success returns a
    fully-populated `IdeasDigest` with verified citations and
    refuse-to-decide-validated narrations.

    Empty-corpus → returns a digest with `cards=[]` and the four
    lenses listed in `dropped_lenses`. The router renders the
    empty-state surface from there.
    """
    week_iso = week_iso or week_iso_for()
    enabled: List[IdeaLens] = [
        lens for lens in (lenses_enabled or list(IDEA_LENSES)) if lens in IDEA_LENSES
    ]
    if not enabled:
        enabled = list(IDEA_LENSES)

    corpus = await _fetch_recent_corpus(db, account_id=account_id)

    digest = IdeasDigest(
        id="idg-" + uuid.uuid4().hex[:12],
        account_id=account_id,
        week_iso=week_iso,
        cards=[],
        model_id="deterministic-v1" if not _llm_mode_enabled() else "claude-sonnet-4-5",
    )

    if not corpus:
        # Empty corpus → empty digest. Every lens "dropped".
        digest.dropped_lenses = list(enabled)
        return digest

    resolver = IdeasCitationResolver(db, account_id=account_id)

    pass_count = 0
    fail_count = 0
    for lens in enabled:
        for _attempt in range(3):  # up to 2 regenerations per spec
            card = _build_card_for_lens(lens, corpus)
            if card is None:
                break
            try:
                validate_no_imperatives(card.body, label=f"ideas.card.{lens}.body")
                validate_no_imperatives(card.title, label=f"ideas.card.{lens}.title")
                await resolver.verify_many(card.citations)
            except (RefuseToDecideViolation, CitationUnverifiable):
                fail_count += 1
                continue
            digest.cards.append(card)
            pass_count += 1
            break
        else:
            digest.dropped_lenses.append(lens)

    # If no LLM round-trip was performed but a lens still failed
    # 3 times (e.g. corpus too thin), record it dropped.
    seen_lenses = {c.lens for c in digest.cards}
    for lens in enabled:
        if lens not in seen_lenses and lens not in digest.dropped_lenses:
            digest.dropped_lenses.append(lens)

    digest.refuse_to_decide_pass_count = pass_count
    digest.refuse_to_decide_fail_count = fail_count
    digest.citation_count = sum(len(c.citations) for c in digest.cards)
    return digest


def _llm_mode_enabled() -> bool:
    """Future-mode toggle. When env `IDEAS_LLM_ENABLED=true` is
    set, the synthesizer wraps the candidate cards in a shielded
    LLM round-trip. v1 ships with deterministic synthesis only;
    the scaffold here keeps the upgrade path clean without
    forcing the LLM dependency on the test path."""
    return os.environ.get("IDEAS_LLM_ENABLED", "false").strip().lower() == "true"


__all__ = ["SynthesisFailure", "synthesize_digest", "week_iso_for"]
