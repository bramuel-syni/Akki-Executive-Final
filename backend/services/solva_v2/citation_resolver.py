"""Solva v2 — Citation realness resolver (Sprint Z.2.B, 2026-02).

User directive (Issue 2 / Scope A): the integrity validators must
verify that each `SourceCitation.source_input_id` resolves to a real
record — embedded in the session, a known coarse-layer tag, or a
DB-level canonical store. Citations that cannot be resolved trip a new
`citation_unverifiable` failure reason.

Two resolution surfaces:

  (1) Embedded session arrays — `reasoning_audit_log`, `user_turns`,
      `attached_docs`, `comparables`. These are the hot path. The
      session is already fully denormalised into the document the
      validator receives, so embedded resolution is O(1) set lookup.

  (2) DB-level canonical stores — for citations whose id has been
      elided from the session embed (rare, but happens for cross-
      session document/comparable references). Looked up via async
      motor in a batch prefetch by the caller; the resolver itself
      stays SYNC so it can run inside the existing
      `validate_artefact(...)` sync interface without breaking other
      callers.

Resolution order per citation:

  embedded_<kind>  →  coarse_layer_tag  →  db_<collection>  →  unresolved

Returns `ResolutionResult` carrying the strategy that succeeded (or
`"unresolved"`) so callers can surface a debuggable failure payload.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple


# ─────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────


# Coarse-layer tags accepted as valid citation ids. Mirrors the set
# already used by `bias_inventory_citation_lint` so all citation
# validators share the same surface.
COARSE_LAYER_TAGS: frozenset = frozenset({
    "L0", "L1", "L2", "L3", "L4",
    "frame_audit", "surface", "depth", "synthesis", "reflection",
    "framing", "grounding", "hypothesis",  # legacy
})


# DB-level canonical stores indexed by `source_kind`. When a citation
# isn't found embedded in the session, the resolver tries each store
# in order. `documents` carries the `attached_doc` kind because
# cross-session document references can omit the session's local
# `attached_docs[]` mirror but still point to a real document.
DB_STORES_BY_KIND: Dict[str, Tuple[str, ...]] = {
    "audit_log":    ("extractions_log", "chat_audit_log", "audit_log"),
    "attached_doc": ("documents",),
    "comparable":   ("solva_v1_comparables_archive",),
    # `user_turn` and `corpus` have no DB-level canonical store other
    # than the embedded array / coarse tags — so no DB fallback.
    "user_turn":    (),
    "corpus":       (),
}


# Embedded session arrays indexed by `source_kind`.
EMBEDDED_FIELDS_BY_KIND: Dict[str, str] = {
    "audit_log":    "reasoning_audit_log",
    "user_turn":    "user_turns",
    "attached_doc": "attached_docs",
    "comparable":   "comparables",
    # `corpus` citations historically use coarse tags or audit_log refs.
}


# ─────────────────────────────────────────────────────────────────
# Result type
# ─────────────────────────────────────────────────────────────────


@dataclass
class ResolutionResult:
    citation_id: str
    source_kind: str
    resolved: bool
    strategy: str  # one of: embedded_<kind>, coarse_layer_tag, db_<coll>, unresolved


# ─────────────────────────────────────────────────────────────────
# Embedded-index helper
# ─────────────────────────────────────────────────────────────────


def build_embedded_index(session: Dict[str, Any]) -> Dict[str, Set[str]]:
    """Build the set of citation ids resolvable via the session's
    embedded arrays, keyed by source_kind. Sync, pure, O(N) on the
    session arrays."""
    out: Dict[str, Set[str]] = {}
    for kind, field_name in EMBEDDED_FIELDS_BY_KIND.items():
        ids: Set[str] = set()
        for entry in (session.get(field_name) or []):
            if isinstance(entry, dict) and entry.get("id"):
                ids.add(str(entry["id"]))
        out[kind] = ids
    return out


def collect_citation_refs(payload) -> Dict[str, Set[str]]:
    """Walk an `ArtefactPayload` and collect every (source_kind →
    {citation_id}) reference. Used by the router to pre-batch a
    motor query against the DB-level stores before running the sync
    validator.

    Returns a dict keyed by source_kind whose values are the distinct
    citation ids referenced. Empty kinds are included with an empty
    set so callers can iterate uniformly.
    """
    out: Dict[str, Set[str]] = {kind: set() for kind in EMBEDDED_FIELDS_BY_KIND.keys()}
    out.setdefault("corpus", set())

    def _add_citations(citations) -> None:
        for c in (citations or []):
            kind = getattr(c, "source_kind", None)
            cid = getattr(c, "source_input_id", None)
            if kind and cid:
                out.setdefault(kind, set()).add(str(cid))

    # Walk every payload section that carries SourceCitation lists.
    for kf in (payload.headline.key_findings or []):
        _add_citations(kf.source_citations)
    for s in (payload.scenarios or []):
        _add_citations(s.supporting_evidence)
    for si in (payload.sensitivity_inputs or []):
        _add_citations(si.source_citations)
    for p in (payload.pathway or []):
        _add_citations(p.source_citations)
    # Tension deep dives carry SourceCitation lists; the TensionSlide
    # itself does NOT — its EvidenceBlock carries only a single
    # audit-log id (not a SourceCitation list).
    for dd in (getattr(payload, "per_tension_deep_dive", None) or []):
        _add_citations(dd.additional_citations)
    return out


# ─────────────────────────────────────────────────────────────────
# Sync resolver
# ─────────────────────────────────────────────────────────────────


class CitationResolver:
    """Sync resolver that walks: embedded → coarse-tag → pre-resolved DB
    sets → unresolved. Constructed once per validate_artefact call.

    Pre-resolved DB id sets must be supplied by the caller — the
    resolver does NOT issue DB queries itself, so it can stay sync
    and side-effect-free.
    """

    def __init__(
        self,
        session: Dict[str, Any],
        *,
        db_resolved_ids: Optional[Dict[str, Set[str]]] = None,
    ) -> None:
        self._embedded = build_embedded_index(session)
        self._db_resolved: Dict[str, Set[str]] = db_resolved_ids or {}

    def resolve(
        self,
        citation_id: str,
        source_kind: Optional[str] = None,
    ) -> ResolutionResult:
        if not citation_id:
            return ResolutionResult("", source_kind or "", False, "unresolved_empty_id")

        # Stringify (some payloads carry int-like ids).
        cid = str(citation_id)

        # (1) Coarse-layer tag whitelist — accepted regardless of kind.
        if cid in COARSE_LAYER_TAGS:
            return ResolutionResult(cid, source_kind or "", True, "coarse_layer_tag")

        # (2) Embedded — try the kind-specific bucket first; if no
        # kind specified, sweep all buckets.
        if source_kind:
            if cid in self._embedded.get(source_kind, set()):
                return ResolutionResult(cid, source_kind, True, f"embedded_{source_kind}")
        else:
            for k, ids in self._embedded.items():
                if cid in ids:
                    return ResolutionResult(cid, k, True, f"embedded_{k}")

        # (3) DB-resolved (pre-fetched by the caller).
        if source_kind:
            if cid in self._db_resolved.get(source_kind, set()):
                return ResolutionResult(cid, source_kind, True, f"db_{source_kind}")
        else:
            for k, ids in self._db_resolved.items():
                if cid in ids:
                    return ResolutionResult(cid, k, True, f"db_{k}")

        return ResolutionResult(cid, source_kind or "", False, "unresolved")

    def has_embedded_kind(self, kind: str) -> bool:
        """True iff the session embeds at least one id of `kind`. Used
        by the honesty patch in `_build_scenarios` to decide whether
        the kind is available as a source-of-independence."""
        return bool(self._embedded.get(kind))

    @property
    def embedded(self) -> Dict[str, Set[str]]:
        """Read-only access to the embedded id index — used by the
        builder honesty patch to pick distinct independent citations."""
        return dict(self._embedded)


# ─────────────────────────────────────────────────────────────────
# Async batch prefetch (motor)
# ─────────────────────────────────────────────────────────────────


async def prefetch_db_resolved(
    payload,
    motor_db,
) -> Dict[str, Set[str]]:
    """Async batch prefetch — for each `source_kind` that has a DB-
    level store, run one `$in` query and build the resolved set.
    Called by the router before invoking the sync validator.
    """
    refs = collect_citation_refs(payload)
    resolved: Dict[str, Set[str]] = {}
    for kind, ids in refs.items():
        if not ids:
            continue
        stores = DB_STORES_BY_KIND.get(kind, ())
        if not stores:
            continue
        kind_resolved: Set[str] = set()
        ids_list = list(ids)
        for coll in stores:
            # Some collections use `id`, others use `_id` — try `id`
            # first since that's the canonical app-level convention
            # in this codebase.
            cursor = motor_db[coll].find(
                {"id": {"$in": ids_list}}, {"_id": 0, "id": 1},
            )
            async for row in cursor:
                if row.get("id"):
                    kind_resolved.add(str(row["id"]))
            # Fall through to next store for any ids still missing —
            # the order in DB_STORES_BY_KIND is the priority.
            remaining = [i for i in ids_list if i not in kind_resolved]
            if not remaining:
                break
            ids_list = remaining
        if kind_resolved:
            resolved[kind] = kind_resolved
    return resolved


__all__ = [
    "COARSE_LAYER_TAGS",
    "DB_STORES_BY_KIND",
    "EMBEDDED_FIELDS_BY_KIND",
    "ResolutionResult",
    "build_embedded_index",
    "collect_citation_refs",
    "CitationResolver",
    "prefetch_db_resolved",
]
