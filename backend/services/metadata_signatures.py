"""Phase E.0.2 — Cross-board metadata signature derivation.

This module derives, persists, and queries the metadata signatures
that the Pulse cross-board aggregator (E.0.3) reads. Three signature
kinds, all deterministic / regex-or-keyword (NO embeddings, NO LLM
calls — see Phase E.0 audit decision: topic_vector dropped for v1).

  • regulatory_ref — extensible pattern match against the 5 anchor
    statutes (Companies Act 2006 s.172 · GDPR Art.17 · FCA SYSC 4.1 ·
    SEC Rule 10b-5 · IFRS 15) plus widely-used variants.
  • governance_theme — keyword classifier in {audit, risk,
    remuneration, nomination}. Maps to committee ownership.
  • pulse_class — REUSE the locked 4-class enum from
    services/privacy_wall.py:PULSE_CLASSIFIER_ENUM
    {capital, succession, regulatory, cyber}. Persisted at write time
    instead of the existing read-time derivation in routers/pulse.py.

Storage contract — db.context_metadata_signatures rows:
    {
      "id":              UUID4 string,
      "context_id":      str,                 # source board (NEVER exposed cross-context)
      "account_id":      str | None,          # for principal-scoped reads
      "signature_kind":  "regulatory_ref" | "governance_theme" | "pulse_class",
      "signature_value": str,                 # canonical token (matched ref / theme / class)
      "source_artefact_kind":  "signal" | "document" | "chat_message",
      "source_artefact_id":    str,           # opaque to other tenants — FK back inside source ctx
      "content_hash":    str,                 # sha256 of text; cheap dedup
      "created_at":      ISO-8601,
    }

The aggregator (E.0.3) reads ONLY:
    {context_id, signature_kind, signature_value, created_at}
i.e. it never returns source_artefact_id or content_hash to the
calling tenant; those are kept on the row for in-tenant traceability.

Index plan (created at backend boot in server.py):
    {context_id: 1, signature_kind: 1, signature_value: 1}
    {signature_kind: 1, signature_value: 1, created_at: -1}  # cross-tenant lookup
    {context_id: 1, source_artefact_kind: 1, source_artefact_id: 1}  # idempotency
"""
from __future__ import annotations

import hashlib
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("akki.metadata_signatures")


# ─────────────────────────────────────────────────────────────────────
# 1) regulatory_ref — pattern table.
#
# Each row: (canonical_token, regex). Canonical tokens are STABLE
# strings the aggregator joins on across tenants; regex variants
# are non-exhaustive but cover the most common in-text mentions.
# Keep this list extensible — adding a row never breaks existing
# rows because the canonical token is the join key.
# ─────────────────────────────────────────────────────────────────────
_REGULATORY_PATTERNS: List[Tuple[str, re.Pattern]] = [
    # Companies Act 2006 s.172 — UK directors' duties.
    ("Companies Act 2006 s.172",
     re.compile(r"\bcompanies\s+act\s+(?:2006\s+)?s\.?\s*172\b|\bs\.?\s*172\s+companies\s+act\b|\bsection\s+172\b",
                re.I)),
    # GDPR Art.17 — right to erasure.
    ("GDPR Art.17",
     re.compile(r"\bgdpr\s+(?:art(?:icle)?\.?\s*)?17\b|\barticle\s+17\s+gdpr\b|\bright\s+to\s+(?:erasure|be\s+forgotten)\b",
                re.I)),
    # FCA SYSC 4.1 — senior management arrangements.
    ("FCA SYSC 4.1",
     re.compile(r"\bsysc\s*4\.?\s*1\b|\bfca\s+sysc\s*4\b|\bsenior\s+management\s+arrangements\b",
                re.I)),
    # SEC Rule 10b-5 — anti-fraud.
    ("SEC Rule 10b-5",
     re.compile(r"\b(?:sec\s+)?rule\s+10b\s*[-–]?\s*5\b|\bsection\s+10\(b\)\b|\b10b\s*[-–]?\s*5\b",
                re.I)),
    # IFRS 15 — revenue from contracts with customers.
    ("IFRS 15",
     re.compile(r"\bifrs\s+15\b|\bifrs\s+revenue\s+standard\b|\brevenue\s+from\s+contracts\s+with\s+customers\b",
                re.I)),
]


# ─────────────────────────────────────────────────────────────────────
# 2) governance_theme — keyword classifier.
#
# Maps text → one of {audit, risk, remuneration, nomination}. Picks
# the BEST match (highest hit count); falls back to no theme rather
# than guessing.
# ─────────────────────────────────────────────────────────────────────
_GOVERNANCE_THEME_PATTERNS: Dict[str, re.Pattern] = {
    "audit": re.compile(
        r"\b(audit|auditor|external\s+audit|internal\s+audit|"
        r"audit\s+committee|big\s+four|kpmg|pwc|ey|deloitte|"
        r"financial\s+statements|going\s+concern)\b", re.I),
    "risk": re.compile(
        r"\b(risk\s+committee|risk\s+register|risk\s+appetite|"
        r"enterprise\s+risk|operational\s+risk|risk\s+management|"
        r"key\s+risk|emerging\s+risk|risk\s+exposure)\b", re.I),
    "remuneration": re.compile(
        r"\b(remuneration|comp(?:ensation)?\s+committee|exec(?:utive)?\s+pay|"
        r"bonus|long[-\s]?term\s+incentive|ltip|share\s+option|"
        r"vesting|salary\s+review|pay\s+ratio)\b", re.I),
    "nomination": re.compile(
        r"\b(nomination|nominations\s+committee|board\s+composition|"
        r"director\s+search|board\s+evaluation|skills\s+matrix|"
        r"diversity\s+(?:and\s+inclusion|policy)|board\s+refresh|"
        r"succession\s+planning)\b", re.I),
}


# ─────────────────────────────────────────────────────────────────────
# 3) pulse_class — reuse the locked 4-class enum.
#
# Same regex as routers/pulse.py:_TOPIC_PATTERNS, hoisted here so the
# write-time derivation is a single source of truth. routers/pulse.py
# can be migrated to call this in a follow-up; for now both
# implementations exist (pulse.py's version stays for legacy rows
# without a persisted signature).
# ─────────────────────────────────────────────────────────────────────
_PULSE_CLASS_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("capital",     re.compile(r"\b(covenant|capital|headroom|cash|liquidity|"
                               r"funding|concentration|exposure|debt|gearing|"
                               r"runway|burn\s+rate|cap\s+table)\b", re.I)),
    ("succession",  re.compile(r"\b(succession|leadership|departure|ceo|cfo|coo|"
                               r"chair|board\-?level|talent|key\s+person|"
                               r"resignation|interim)\b", re.I)),
    ("regulatory",  re.compile(r"\b(regulator|regulation|compliance|disclosure|"
                               r"breach.*regulation|sanction|sox|pcaob|ifrs|"
                               r"gaap|fca|sec\b|gdpr|hipaa|ccpa)\b", re.I)),
    ("cyber",       re.compile(r"\b(cyber|ransomware|breach|incident|data\s+leak|"
                               r"phishing|attack|exploit|vulnerab|zero[-\s]day)\w*",
                               re.I)),
]


# ─────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────
def derive_regulatory_refs(text: str) -> List[str]:
    """Return the canonical tokens of every anchor regulatory ref
    found in `text`. De-duplicated, deterministic order."""
    if not text:
        return []
    out: List[str] = []
    seen: set = set()
    for token, pat in _REGULATORY_PATTERNS:
        if pat.search(text) and token not in seen:
            out.append(token)
            seen.add(token)
    return out


def derive_governance_themes(text: str) -> List[str]:
    """Return every governance theme (∈ {audit, risk, remuneration,
    nomination}) that fires on `text`. Multi-label by design — a
    single signal can be both a 'risk' and an 'audit' theme. Ordered
    by descending hit count so callers can take [0] for a single
    label if they want."""
    if not text:
        return []
    scored: List[Tuple[str, int]] = []
    for theme, pat in _GOVERNANCE_THEME_PATTERNS.items():
        n = len(pat.findall(text))
        if n:
            scored.append((theme, n))
    scored.sort(key=lambda x: (-x[1], x[0]))
    return [t for t, _ in scored]


def derive_pulse_classes(text: str) -> List[str]:
    """Return the locked-enum 4-class tags that fire on `text`.
    Multi-label — a signal about an FCA-mandated CFO departure is
    both 'regulatory' AND 'succession'."""
    if not text:
        return []
    out: List[str] = []
    seen: set = set()
    for label, pat in _PULSE_CLASS_PATTERNS:
        if pat.search(text) and label not in seen:
            out.append(label)
            seen.add(label)
    return out


def _content_hash(text: str) -> str:
    """Stable sha256 of the input text. Used as the dedup key on
    (context_id, source_artefact_kind, source_artefact_id) — same
    artefact rewritten with same text doesn't double-create signatures."""
    return hashlib.sha256((text or "").encode("utf-8", errors="ignore")).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _make_row(
    *,
    context_id: str,
    account_id: Optional[str],
    signature_kind: str,
    signature_value: str,
    source_artefact_kind: str,
    source_artefact_id: str,
    content_hash: str,
    now: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "context_id": context_id,
        "account_id": account_id,
        "signature_kind": signature_kind,
        "signature_value": signature_value,
        "source_artefact_kind": source_artefact_kind,
        "source_artefact_id": source_artefact_id,
        "content_hash": content_hash,
        "created_at": now or _now_iso(),
    }


async def derive_and_persist(
    db: Any,
    *,
    text: str,
    context_id: str,
    account_id: Optional[str],
    source_artefact_kind: str,
    source_artefact_id: str,
) -> Dict[str, Any]:
    """Derive all 3 signature kinds for `text` and upsert into
    `db.context_metadata_signatures`. Returns a count summary —
    used by tests + the aggregator's freshness probe.

    Idempotency: existing rows with the same
    (context_id, source_artefact_kind, source_artefact_id, signature_kind, signature_value)
    are NOT duplicated. We rely on the
    `(context_id, source_artefact_kind, source_artefact_id)` index
    + an in-memory delete-then-insert per call (small N, simpler
    than upsert-many).
    """
    if not text or not text.strip():
        return {"regulatory_ref": 0, "governance_theme": 0, "pulse_class": 0}
    if source_artefact_kind not in ("signal", "document", "chat_message", "boardpack"):
        raise ValueError(f"unsupported source_artefact_kind: {source_artefact_kind!r}")

    refs   = derive_regulatory_refs(text)
    themes = derive_governance_themes(text)
    classes = derive_pulse_classes(text)
    chash  = _content_hash(text)
    now_s  = _now_iso()

    rows: List[Dict[str, Any]] = []
    for ref in refs:
        rows.append(_make_row(
            context_id=context_id, account_id=account_id,
            signature_kind="regulatory_ref", signature_value=ref,
            source_artefact_kind=source_artefact_kind,
            source_artefact_id=source_artefact_id,
            content_hash=chash, now=now_s,
        ))
    for theme in themes:
        rows.append(_make_row(
            context_id=context_id, account_id=account_id,
            signature_kind="governance_theme", signature_value=theme,
            source_artefact_kind=source_artefact_kind,
            source_artefact_id=source_artefact_id,
            content_hash=chash, now=now_s,
        ))
    for klass in classes:
        rows.append(_make_row(
            context_id=context_id, account_id=account_id,
            signature_kind="pulse_class", signature_value=klass,
            source_artefact_kind=source_artefact_kind,
            source_artefact_id=source_artefact_id,
            content_hash=chash, now=now_s,
        ))

    # Idempotent rewrite — drop any prior rows for this artefact, then
    # insert the freshly-derived set. Cheap (N is tiny per artefact).
    try:
        await db.context_metadata_signatures.delete_many({
            "context_id": context_id,
            "source_artefact_kind": source_artefact_kind,
            "source_artefact_id": source_artefact_id,
        })
        if rows:
            await db.context_metadata_signatures.insert_many(rows)
    except Exception:
        # Non-fatal — derivation is a side-effect on the write path,
        # never blocking the artefact's own persistence.
        logger.exception(
            "metadata_signatures derivation failed (non-fatal): "
            "ctx=%s kind=%s id=%s",
            context_id, source_artefact_kind, source_artefact_id,
        )

    return {
        "regulatory_ref": len(refs),
        "governance_theme": len(themes),
        "pulse_class": len(classes),
    }


# Sentinel marker — wired in tests to detect that the derivation
# fired on a write path. Tests can `import` the module and bind
# this to assert call-shape without monkey-patching.
__all__ = (
    "derive_regulatory_refs",
    "derive_governance_themes",
    "derive_pulse_classes",
    "derive_and_persist",
)
