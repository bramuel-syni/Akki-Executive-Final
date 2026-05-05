"""Privacy Wall — Phase 2b foundation.

Single source of truth for what crosses context boundaries in this
codebase. Every cross-context surface (Pulse — when it ships in 2c —
plus today's `/api/me/home/stream`, `/api/me/governance*`,
`/api/admin/signals/action-heatmap`) MUST funnel its `documents`,
`signals`, `boardpacks`, `audit_log`, `chat_audit_log`,
`synisense_runs`, `inbound_queue` rows through `project_for_pulse`
before they leave the server.

Background: see `docs/PRIVACY_WALL_DESIGN.md` (threat model,
recommendation: option (a) field-projection guard) and
`docs/PRIVACY_WALL_LEAKAGE_AUDIT.md` (the baseline of what was
leaking before this module shipped).

## What this module gives you

- `project_for_pulse(collection, doc) -> dict` — drops every field
  not in the per-collection allowlist. Unknown collection → raises.
  Drift (a key in neither the allow nor deny list) is logged at WARN
  and — when `STRICT_PRIVACY_WALL_RAISE=true` — escalates to a
  `PrivacyWallDriftError` 500.
- `project_audit_row(row, *, drop_metadata=True)` — TBD-4 (signed
  off 2026-05-05): cross-context audit feed strips the `metadata`
  blob entirely. Per-context audit feeds (called with
  `drop_metadata=False`) keep it raw.
- `redact_for_pulse_text(text)` — placeholder for 2c. Today a no-op
  pass-through so callers can be wired now and 2c can swap the
  implementation in one place.
- `assemble_pulse_prompt(per_context_outputs)` — placeholder for 2c.
  Today raises `NotImplementedError("Phase 2c")` so any premature
  caller fails loudly.
- `PULSE_CLASSIFIER_ENUM` — the locked 4-class signals taxonomy.
  Defined here, NOT enforced on existing rows in 2b (TBD-2 sign-off
  was "define and export only").
- `STRICT_PRIVACY_WALL` (default `true`) — toggles WARN-on-drift.
- `STRICT_PRIVACY_WALL_RAISE` (default `false`) — escalates WARN to
  500 in CI.

## Allowlists

Each collection has an `ALLOW` set (metadata-class — safe to ship
cross-context) and a `DENY` set (content-class — must be dropped).
Together they MUST cover every key that has ever appeared on a real
row in the dev DB; see `tests/test_privacy_wall.py` for the drift
guard. Adding a column to a content collection without updating
both sets is a CI failure.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, FrozenSet, List, Optional, Tuple

logger = logging.getLogger("akki.privacy_wall")

# ─────────────────────────────────────────────────────────────────────
# 4-class Pulse signals enum — TBD-2, signed off 2026-05-05.
# DEFINED only in 2b; not enforced on existing `signals` rows. 2c
# imports this and uses it for the cross-board pattern detector.
# ─────────────────────────────────────────────────────────────────────
PULSE_CLASSIFIER_ENUM: Tuple[str, ...] = (
    "capital",      # Cap-table pressure, funding gap, balance-sheet stress.
    "succession",   # CEO/CFO/board exits, key-person risk, succession gaps.
    "regulatory",   # Compliance drift, supervisory action, policy change.
    "cyber",        # Security incidents, breach indicators, vendor cyber risk.
)


# ─────────────────────────────────────────────────────────────────────
# Per-collection ALLOWLISTS and DENYLISTS.
#
# Discipline:
#   * Every key that has ever appeared on a real row in the dev DB
#     MUST be in either ALLOW or DENY for that collection. The
#     drift test (`tests/test_privacy_wall.py::test_field_drift`)
#     enforces this against either the live preview DB or the
#     embedded fixtures (the union — every key seen in either side
#     must be classified somewhere).
#   * ALLOW = metadata-class, safe to cross context boundaries.
#   * DENY = content-class, must be dropped. Listed explicitly so
#     drift detection can distinguish "field we know about and chose
#     to drop" from "field we've never seen".
#   * No field appears in both sets. CI tests assert disjoint.
# ─────────────────────────────────────────────────────────────────────
_ALLOW_DOCUMENTS: FrozenSet[str] = frozenset({
    "id", "context_id", "created_at", "updated_at", "status",
    "doc_type", "mime_type",
    "data_trust",         # categorical trust tier
    "size_bytes", "extracted_chars", "page_count",  # numeric metadata
    "paragraphs_page_count", "paragraphs_version", "paragraphs_computed_at",
    "synisense_version",
    "journal_commentary_synisense_version",
    "journal_commentary_generated_at",
    "source_channel",      # categorical: "upload" / "inbound_email" / "manual"
})
_DENY_DOCUMENTS: FrozenSet[str] = frozenset({
    "name", "title", "original_filename",      # T3 — deal-codename leak.
    "extracted_text", "preview", "description",
    "paragraphs",                              # full body anchors.
    "journal_commentary", "journal_commentary_redacted",  # LLM output is content.
    "akki_summary",
    "uploaded_by_email", "sender", "attendees",
    "tags",                                    # TBD-1: blocked in 2b.
    "body_redacted",                           # still content-class.
    "trust_score", "trust_tier",               # historical fields, retained for safety.
    "kind",                                    # historical alias of doc_type.
})

_ALLOW_SIGNALS: FrozenSet[str] = frozenset({
    "id", "context_id", "created_at", "updated_at", "status",
    "type",                # categorical
    "confidence",          # numeric
    "data_trust",          # categorical tier
    "shielding_masked",    # bool
    "generated_by",        # categorical: "rule" / "llm" / "manual"
})
_DENY_SIGNALS: FrozenSet[str] = frozenset({
    "headline", "summary", "body", "evidence_excerpt",
    "recommended_actions",
    "references", "sources",      # source URLs / quotes — content-class.
    "topic_class",                 # TBD-2: free-form today; locked enum for 2c.
    "kind", "tone", "signal_type", "category",  # current free-form classifiers.
    "severity",                    # historical / not-yet-canonical.
    "fielded_metric",              # historical, dropped defensively.
    "actor", "actor_email",
})

_ALLOW_BOARDPACKS: FrozenSet[str] = frozenset({
    "id", "context_id", "cycle_id", "cycle_label",
    "created_at", "updated_at",
    "status", "block_status",
    "schema_version",
    "synisense_version", "commentary_synisense_version",
    "synisense_first_accept_at", "synisense_last_accepted_at",
    "synisense_last_accepted_by",
    "classification_at",           # timestamp of when classification was applied.
    "submitted_at",                # timestamp only (the submitter id is content).
    "document_ids",                # plural-of-id: per design doc §2 OK to ship.
})
_DENY_BOARDPACKS: FrozenSet[str] = frozenset({
    "title", "subject",
    "body", "body_redacted", "items", "opening_paragraph",
    "commentary", "commentary_redacted",
    "submission_note",
    "submitted_by",
    "account_id",                  # writer's account
    "synisense", "synisense_last_accepted_histogram",  # may carry span metadata.
    "classification",              # may be dict-shape with reasons[] containing content.
})

# Audit log — ships across user's own contexts. TBD-4 sign-off:
# `metadata` (the free-form blob; the spec called it "details") is
# stripped on cross-context endpoints. Per-context endpoints keep it.
_ALLOW_AUDIT_LOG: FrozenSet[str] = frozenset({
    "id", "created_at", "context_id", "account_id",
    "action", "resource_type", "resource_id",
})
_DENY_AUDIT_LOG: FrozenSet[str] = frozenset({
    "metadata",                    # TBD-4 — free-form blob.
    "details",                     # historical alias, in case any row has it.
    "ip", "ua_sha", "user_agent",  # auditable per-context, not aggregable.
})

# Chat audit log — single-tenant per chat_id + account_id today. Not
# expected to cross context boundaries, but listed here so any future
# debug tool that aggregates over `account_id` is forced through the
# wall.
_ALLOW_CHAT_AUDIT_LOG: FrozenSet[str] = frozenset({
    "id", "at", "account_id", "chat_id", "action",
    "prev_hash", "row_hash",
    "ua_sha",                      # hashed UA — metadata.
})
_DENY_CHAT_AUDIT_LOG: FrozenSet[str] = frozenset({
    "payload",                     # carries the message body for some actions.
    "ip",                          # raw IP — strip cross-context.
})

# Synisense runs — the audit-lite trail of every PII run. Counts +
# layers + categorical entity types are metadata; span character
# offsets and the shield map id reveal where in the original text
# the PII sits, so they're content. TBD-3 sign-off.
_ALLOW_SYNISENSE_RUNS: FrozenSet[str] = frozenset({
    "id", "context_id", "account_id", "ts",
    "surface", "mode",
    "synisense_version",
    "input_sha256",                # fingerprint, not text.
    "stats",                       # counts dict {regex_hits, presidio_hits, llm_hits, latency_ms}.
})
_DENY_SYNISENSE_RUNS: FrozenSet[str] = frozenset({
    "spans",                       # carries entity-type AND offset[s] — content per TBD-3.
    "shield_map_id",               # links back to the encrypted shield store.
    "raw_text", "redacted_text",   # historical fields, dropped defensively.
    "layers_used",                 # historical alias of stats.layers.
    "spans_count", "latency_ms",   # historical aliases — covered by stats.
})

_ALLOW_INBOUND_QUEUE: FrozenSet[str] = frozenset({
    "id", "context_id", "created_at", "status",
    "accepted_at", "accepted_by",     # accepted_by is internal account-id, metadata.
    "accept_via",                     # categorical
    "review_reason",                  # categorical
    "promoted_doc_id",
    "inbound_attachment_count",       # numeric
    "inbound_message_id",             # opaque message-id from the mail provider — metadata.
    "inbound_trust_tier",             # categorical
})
_DENY_INBOUND_QUEUE: FrozenSet[str] = frozenset({
    "inbound_subject",                # subject is content (T3 — codename leak class).
    "inbound_text_preview",           # body preview.
    "inbound_from_email", "inbound_from_name",  # PII.
    "accept_note",                    # may be free-form review note.
    "subject", "sender",              # historical aliases.
})

# Master registry. Add a collection here when wiring a new
# cross-context surface; the sentinel `ProjectionRegistry` checks at
# import-time that ALLOW and DENY are disjoint per collection.
_REGISTRY: Dict[str, Tuple[FrozenSet[str], FrozenSet[str]]] = {
    "documents":       (_ALLOW_DOCUMENTS,       _DENY_DOCUMENTS),
    "signals":         (_ALLOW_SIGNALS,         _DENY_SIGNALS),
    "boardpacks":      (_ALLOW_BOARDPACKS,      _DENY_BOARDPACKS),
    "audit_log":       (_ALLOW_AUDIT_LOG,       _DENY_AUDIT_LOG),
    "chat_audit_log":  (_ALLOW_CHAT_AUDIT_LOG,  _DENY_CHAT_AUDIT_LOG),
    "synisense_runs":  (_ALLOW_SYNISENSE_RUNS,  _DENY_SYNISENSE_RUNS),
    "inbound_queue":   (_ALLOW_INBOUND_QUEUE,   _DENY_INBOUND_QUEUE),
}

# Disjointness invariant — surface at import so a typo can't ship.
for _coll, (_allow, _deny) in _REGISTRY.items():
    _overlap = _allow & _deny
    if _overlap:
        raise RuntimeError(
            f"Privacy Wall configuration error: '{_coll}' has fields "
            f"in both ALLOW and DENY: {sorted(_overlap)}"
        )

# Public read accessors (used by the drift test) — kept module-level
# so callers don't need to know about the underscore-prefixed dict.
COLLECTIONS: Tuple[str, ...] = tuple(_REGISTRY.keys())


def allowed_keys(collection: str) -> FrozenSet[str]:
    if collection not in _REGISTRY:
        raise UnknownCollectionError(collection)
    return _REGISTRY[collection][0]


def denied_keys(collection: str) -> FrozenSet[str]:
    if collection not in _REGISTRY:
        raise UnknownCollectionError(collection)
    return _REGISTRY[collection][1]


# ─────────────────────────────────────────────────────────────────────
# Errors
# ─────────────────────────────────────────────────────────────────────
class PrivacyWallError(Exception):
    """Base — never raise this directly."""


class UnknownCollectionError(PrivacyWallError):
    """Raised when `project_for_pulse` is called with a collection not
    in the registry. Adding a new cross-context surface MUST start
    with adding the collection to `_REGISTRY`."""

    def __init__(self, collection: str) -> None:
        super().__init__(
            f"Privacy Wall has no allowlist for collection '{collection}'. "
            f"Add ALLOW + DENY sets to backend/services/privacy_wall.py:_REGISTRY "
            f"before calling project_for_pulse on this collection."
        )
        self.collection = collection


class PrivacyWallDriftError(PrivacyWallError):
    """Raised when STRICT_PRIVACY_WALL_RAISE=true and a row carries a
    field that is in neither the ALLOW nor the DENY set. Catches
    schema additions that haven't been classified yet."""

    def __init__(self, collection: str, fields: List[str]) -> None:
        super().__init__(
            f"Privacy Wall drift on collection '{collection}': fields "
            f"{sorted(fields)} are in neither ALLOW nor DENY. Classify "
            f"them in backend/services/privacy_wall.py before shipping."
        )
        self.collection = collection
        self.fields = fields


# ─────────────────────────────────────────────────────────────────────
# Env flags
# ─────────────────────────────────────────────────────────────────────
def _flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _is_strict() -> bool:
    """`STRICT_PRIVACY_WALL` — when true, drift is logged at WARN.
    Default true in dev/preview/prod; only set false on a one-off if
    you genuinely need the silence."""
    return _flag("STRICT_PRIVACY_WALL", True)


def _is_strict_raise() -> bool:
    """`STRICT_PRIVACY_WALL_RAISE` — when true, drift escalates from
    WARN to a 500. Default false; set true in CI so the drift test
    can fail loudly."""
    return _flag("STRICT_PRIVACY_WALL_RAISE", False)


# ─────────────────────────────────────────────────────────────────────
# project_for_pulse — the wall.
# ─────────────────────────────────────────────────────────────────────
def project_for_pulse(collection: str, doc: Dict[str, Any]) -> Dict[str, Any]:
    """Return ONLY the metadata-class fields of `doc`.

    * Unknown collection → `UnknownCollectionError`.
    * Drift (a field in neither ALLOW nor DENY) is logged at WARN
      under logger `akki.privacy_wall` with the collection name and
      the unknown keys. When `STRICT_PRIVACY_WALL_RAISE=true`, drift
      raises `PrivacyWallDriftError` instead.
    * Returns a fresh dict — never mutates the input.
    """
    if collection not in _REGISTRY:
        raise UnknownCollectionError(collection)
    if not isinstance(doc, dict):
        # Defensive — Motor sometimes hands back BSON `Document` views
        # which aren't strict dicts on older drivers.
        raise TypeError(
            f"project_for_pulse expects a dict, got {type(doc).__name__}"
        )

    allow, deny = _REGISTRY[collection]
    classified = allow | deny
    seen = set(doc.keys())
    drift = seen - classified

    if drift:
        # Always log — strict mode controls whether we also raise.
        logger.warning(
            "privacy_wall_drift collection=%s unknown_fields=%s",
            collection, sorted(drift),
        )
        if _is_strict_raise():
            raise PrivacyWallDriftError(collection, sorted(drift))

    out: Dict[str, Any] = {}
    for k in seen & allow:
        out[k] = doc[k]
    return out


def project_many(collection: str, docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convenience — `project_for_pulse` over a list."""
    return [project_for_pulse(collection, d) for d in docs]


# ─────────────────────────────────────────────────────────────────────
# Audit-row projection — TBD-4 sign-off.
# ─────────────────────────────────────────────────────────────────────
def project_audit_row(
    row: Dict[str, Any],
    *,
    drop_metadata: bool = True,
) -> Dict[str, Any]:
    """Project an `audit_log` row.

    * `drop_metadata=True` (the default — TBD-4): the free-form
      `metadata` blob is dropped. Use on cross-context endpoints
      (`/api/me/governance/audit*`).
    * `drop_metadata=False`: full row, raw `metadata` retained. Use on
      per-context endpoints (`/api/contexts/{cid}/audit-log`) where
      the caller has explicit context membership.

    Both modes still go through the projection allowlist — drift
    detection applies.
    """
    projected = project_for_pulse("audit_log", row)
    if not drop_metadata:
        # Re-attach the metadata field IF the source row had one. We
        # don't synthesise a missing one.
        if "metadata" in row:
            projected["metadata"] = row["metadata"]
    return projected


# ─────────────────────────────────────────────────────────────────────
# 2c placeholders — wired now so callers can be set up; bodies land
# in 2c. Calling either of these today is a programmer error.
# ─────────────────────────────────────────────────────────────────────
def redact_for_pulse_text(text: Optional[str]) -> Optional[str]:
    """Phase 2c placeholder. Today a no-op pass-through so wiring can
    happen ahead of the real implementation. Callers should treat it
    as opaque — DO NOT depend on identity behaviour."""
    return text


def assemble_pulse_prompt(per_context_outputs: List[Dict[str, Any]]) -> str:
    """Phase 2c placeholder. Will assemble a metadata-only prompt from
    per-context summaries. Today raises NotImplementedError so
    nothing accidentally builds a multi-context LLM prompt before the
    wall has the prompt-isolation contract test in 2c."""
    raise NotImplementedError(
        "assemble_pulse_prompt is a Phase 2c surface — not callable in 2b."
    )
