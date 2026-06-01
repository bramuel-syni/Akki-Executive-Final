"""P5.16 — Inbox-routing classifier (deterministic-v1).

v1 ships the deterministic path. The LLM-shielded round-trip
(`shielded_call` via `services.solva_v2.llm_adapter`) is scaffolded
behind `INBOX_ROUTING_LLM_ENABLED=false`. We flip the flag in a
separate validation cycle once we've audited the deterministic
calibration on live admin-inbox traffic.

Classifier inputs:
  • `admin_inbox_messages` row (the canonical inbound record)

Classifier outputs (ClassificationEnvelope):
  • route_kind, confidence, rationale, target_hint, citations[]
  • Always at least 1 citation pointing back to the source message_id.
  • Rationale validated by `validate_no_imperatives` BEFORE return.
  • Score → band via `calibrate_band` from `confidence.py`.

Route-kind decision tree (deterministic-v1, in priority order):
  1. The inbound dispatcher already routed it
     (`routing_result` in {task_reply, cycle_reply, context_doc})
     → mirror the dispatcher decision in `route_kind` with HIGH
        confidence; we trust the existing pipeline.
  2. Subject prefix verbs (case-insensitive):
        "task:" / "todo:" / "action required:"  → task_create
        "cycle:" / "update:" / "weekly:"          → cycle_update
        "signal:" / "fyi:" / "for info:"          → signal_post
  3. Body-keyword density (Hamming-style score on a curated
     vocabulary per route-kind).
  4. Sender tier — the inbound dispatcher classified the sender
     as `owner`/`reportee`/`unknown` via `_classify_sender_tier`.
     Known senders get a +0.15 bump; unknowns get a -0.10 penalty.
  5. Length floor — bodies < 80 chars degrade to low (insufficient
     signal to decide anything).

Tenant inference:
  • For known-sender messages, the dispatcher already resolved
    `account_id` (via `mailbox_hash` → accounts.inbound_token).
    The classifier inherits that decision and writes it into
    `target_hint.account_id`.
  • For unknown senders OR messages with no account context (e.g.
    addressed to `hello@inbound.akki.syni.ai`), `target_hint.account_id`
    stays empty and `route_kind` cannot be `cycle_update` /
    `task_create` (no tenant to write into). It falls through to
    `discussion_only` or `unclassified`.
"""
from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Tuple

from core import db
from .schema import (
    ClassificationCitation,
    ClassificationEnvelope,
    TargetHint,
    ROUTE_KINDS,
)
from .confidence import calibrate_band
from .refuse_to_decide import (
    RefuseToDecideViolation,
    validate_no_imperatives,
    safe_neutral_fallback,
)
from .citation_resolver import (
    CitationUnverifiable,
    InboxRoutingCitationResolver,
)


class ClassifierFailure(RuntimeError):
    """Raised when classification cannot complete and we must
    surface `unclassified` to the caller."""


def is_llm_enabled() -> bool:
    """Env-flag check. v1 default is `false` — deterministic path
    only. Flipping the flag enables the shielded-LLM round-trip in
    a future validation cycle."""
    return os.environ.get("INBOX_ROUTING_LLM_ENABLED", "false").strip().lower() == "true"


# ── Subject-prefix verb table ───────────────────────────────────
# Each entry: (regex, route_kind, score_boost)
_SUBJECT_PREFIX_RULES: List[Tuple[re.Pattern, str, float]] = [
    (re.compile(r"^\s*(?:action\s+required|action:)", re.IGNORECASE),  "task_create",     0.55),
    (re.compile(r"^\s*(?:task|todo)\s*:", re.IGNORECASE),              "task_create",     0.50),
    (re.compile(r"^\s*(?:cycle|weekly|monthly)\s*:", re.IGNORECASE),   "cycle_update",    0.50),
    (re.compile(r"^\s*update\s*:", re.IGNORECASE),                     "cycle_update",    0.40),
    (re.compile(r"^\s*(?:signal|fyi|for\s+info)\s*:", re.IGNORECASE),  "signal_post",     0.50),
    (re.compile(r"^\s*re\s*:", re.IGNORECASE),                         "discussion_only", 0.25),
    (re.compile(r"^\s*fwd?\s*:", re.IGNORECASE),                       "discussion_only", 0.25),
]


# ── Body-keyword vocabulary per route-kind ──────────────────────
# Used for the body-keyword density score. Tokens chosen for low
# false-positive rate on executive correspondence; revise as
# false-positives surface.
_BODY_KEYWORDS: Dict[str, List[str]] = {
    "task_create": [
        "by friday", "by monday", "deadline", "deliverable", "follow up",
        "complete", "owner", "due", "action item", "next steps",
    ],
    "cycle_update": [
        "this week", "last week", "weekly", "cycle", "operating",
        "kpi", "metric", "review",
    ],
    "signal_post": [
        "noticed", "observed", "concern", "watch out", "trend",
        "saw that", "data point", "anomaly",
    ],
    "discussion_only": [
        "thoughts", "question", "wondering", "fyi", "for info",
        "context", "background",
    ],
}


# ── Dispatcher routing_result → route_kind mirror table ─────────
# When the existing inbound dispatcher has already routed a message
# we trust the decision and mirror it with high confidence.
_DISPATCHER_MIRROR: Dict[str, str] = {
    "task_reply":   "task_create",      # task contributor reply → task surface
    "cycle_reply":  "cycle_update",     # cycle-alias reply → cycle surface
    "context_doc":  "discussion_only",  # document attached as context
    # routing_result of "no_match" / "pending" / "quarantine" / "error"
    # falls through to the heuristic decision tree.
}


def _short_body(text: str, n: int = 200) -> str:
    """Whitespace-normalised first `n` chars of the body."""
    return " ".join((text or "").split())[:n]


def _excerpt(text: str, n: int = 240) -> str:
    """Whitespace-normalised, length-capped excerpt for citation."""
    s = " ".join((text or "").split())
    return s[:n] if s else ""


def _score_route_kind(*, subject: str, body_head: str, route_kind: str) -> float:
    """Body-keyword density score for one route-kind, in [0.0, 0.5].
    Per-keyword hit adds 0.08, capped at 0.5 to leave headroom for
    subject-prefix + sender-tier bumps."""
    haystack = (subject + " " + body_head).lower()
    score = 0.0
    for kw in _BODY_KEYWORDS.get(route_kind, []):
        if kw in haystack:
            score += 0.08
    return min(0.5, score)


def _resolve_route_kind(*, subject: str, body: str,
                         routing_result: str) -> Tuple[str, float, str]:
    """Return `(route_kind, raw_score, signal_reason)`.

    The function does NOT clamp/calibrate the score — caller passes
    it through `calibrate_band` after applying any cross-cutting
    adjustments (sender tier, length floor, tenant absence)."""
    # 1. Dispatcher already routed.
    mirrored = _DISPATCHER_MIRROR.get(routing_result or "")
    if mirrored:
        return (mirrored, 0.85, f"dispatcher_routing_result={routing_result!r}")

    body_head = _short_body(body)

    # 2. Subject-prefix verbs.
    for rx, kind, boost in _SUBJECT_PREFIX_RULES:
        if rx.search(subject or ""):
            keyword_score = _score_route_kind(subject=subject,
                                              body_head=body_head,
                                              route_kind=kind)
            return (kind, boost + keyword_score, f"subject_prefix_rule={rx.pattern!r}")

    # 3. Body-keyword density across all route_kinds — winner-take-all.
    scores = {
        rk: _score_route_kind(subject=subject, body_head=body_head, route_kind=rk)
        for rk in ("task_create", "cycle_update", "signal_post", "discussion_only")
    }
    best_rk, best_score = max(scores.items(), key=lambda kv: kv[1])
    if best_score <= 0.0:
        return ("unclassified", 0.0, "no_signal")
    return (best_rk, best_score, "body_keyword_density")


def _build_rationale(*, route_kind: str, signal_reason: str,
                     score_band: str) -> str:
    """Observational, voice-lint clean, ≤240 chars.

    The rationale describes WHAT signal drove the classification,
    NOT what the admin should do. Refuse-to-decide validation runs
    on the result; a fallback kicks in if the templated string
    somehow trips the validator (defence-in-depth)."""
    pretty_kind = {
        "task_create":     "task creation",
        "cycle_update":    "cycle update",
        "signal_post":     "pulse signal",
        "discussion_only": "discussion-only attachment",
        "unclassified":    "unclassified",
    }.get(route_kind, route_kind)
    pretty_signal = {
        "no_signal":            "no recognisable route-kind signal in the message",
        "body_keyword_density": "body keyword density matched the route-kind vocabulary",
        "subject_prefix_rule":  "subject carried a route-kind prefix verb",
    }.get(signal_reason.split("=")[0], signal_reason)

    if signal_reason.startswith("dispatcher_routing_result"):
        pretty_signal = "the inbound dispatcher had already routed this message"

    out = (
        f"Classification: {pretty_kind} at {score_band} confidence — "
        f"{pretty_signal}."
    )
    try:
        validate_no_imperatives(out, label="inbox_classifier_rationale")
    except RefuseToDecideViolation:
        out = safe_neutral_fallback()
    return out[:240]


async def classify_message(
    message: Dict[str, Any],
    *,
    caller_account_id: Optional[str] = None,
) -> ClassificationEnvelope:
    """Classify one admin_inbox_messages row.

    `message` is the Mongo row shape (see `routers/admin_inbox.py`
    docstring). `caller_account_id` is informational — it does NOT
    affect classification output (the classifier is global). The
    routing endpoint enforces tenant ownership when it actually
    writes into a tenant surface.
    """
    if not isinstance(message, dict) or not message.get("id"):
        raise ClassifierFailure("classify_message requires a message dict with 'id'")

    message_id = message["id"]
    subject = message.get("subject") or ""
    text_body = message.get("text_body") or message.get("body_snippet") or ""
    routing_result = message.get("routing_result") or ""

    # Route-kind decision.
    route_kind, raw_score, signal_reason = _resolve_route_kind(
        subject=subject, body=text_body, routing_result=routing_result,
    )

    # Sender-tier bump / penalty.
    from_email = (message.get("from_email") or "").lower()
    sender_account = None
    if from_email:
        sender_account = await db.accounts.find_one(
            {"email": from_email}, {"_id": 0, "id": 1, "email": 1},
        )
    if sender_account:
        raw_score += 0.15  # known sender
    else:
        raw_score -= 0.10  # unknown sender

    # Length floor — very short bodies cannot carry useful structure.
    body_len = len(text_body.strip())
    if body_len < 80:
        raw_score = min(raw_score, 0.20)

    # Tenant absence — `cycle_update` and `task_create` REQUIRE a tenant.
    target_account_id: Optional[str] = None
    if sender_account:
        target_account_id = sender_account["id"]
    if route_kind in ("cycle_update", "task_create") and not target_account_id:
        # Demote to discussion_only when we have no tenant to write to.
        route_kind = "discussion_only"
        raw_score = min(raw_score, 0.30)
        signal_reason = "no_tenant_for_create_routes"

    confidence = calibrate_band(raw_score)

    # Build target hint (tenant-scoped + route-kind specific).
    target_hint = TargetHint(account_id=target_account_id)
    if route_kind == "task_create":
        target_hint.task_title = (subject or "Inbound task")[:200]
        target_hint.due_hint = _extract_due_hint(text_body)
    elif route_kind == "cycle_update":
        # Caller can fill `company_id` / `cycle_id` after lookup; we
        # leave hint shape open here.
        pass
    elif route_kind == "signal_post":
        target_hint.signal_kind = _signal_kind_from_body(text_body)

    # Build citation (always points at the source message_id).
    citation_excerpt = _excerpt(text_body) or _excerpt(subject) or "(empty body)"
    citations = [ClassificationCitation(
        message_id=message_id,
        excerpt=citation_excerpt,
        field="body" if text_body else "subject",
    )]

    # Verify citation against Mongo (defence-in-depth — the message
    # MUST still exist when we classify, else the row was deleted
    # mid-flight).
    resolver = InboxRoutingCitationResolver()
    try:
        await resolver.verify_many(citations)
    except CitationUnverifiable as e:
        raise ClassifierFailure(
            f"classifier citation failed: {e}"
        ) from e

    rationale = _build_rationale(
        route_kind=route_kind,
        signal_reason=signal_reason,
        score_band=confidence,
    )

    envelope = ClassificationEnvelope(
        message_id=message_id,
        route_kind=route_kind,  # type: ignore[arg-type]
        confidence=confidence,
        rationale=rationale,
        target_hint=target_hint,
        citations=citations,
        model_id="deterministic-v1",
        shield_invoke_id=None,
    )
    return envelope


# ── Tiny helpers ────────────────────────────────────────────────


_DUE_HINT_PATTERNS: List[re.Pattern] = [
    re.compile(r"by\s+(?:end\s+of\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)", re.IGNORECASE),
    re.compile(r"by\s+(\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)", re.IGNORECASE),
    re.compile(r"(?:due|deadline)\s+(?:on\s+)?(?:the\s+)?(\d{1,2}(?:st|nd|rd|th)?\s+\w+)", re.IGNORECASE),
]


def _extract_due_hint(text: str) -> Optional[str]:
    if not text:
        return None
    for rx in _DUE_HINT_PATTERNS:
        m = rx.search(text)
        if m:
            return m.group(0)[:80]
    return None


def _signal_kind_from_body(text: str) -> str:
    if not text:
        return "observation"
    haystack = text.lower()
    if any(kw in haystack for kw in ("concern", "worried", "risk")):
        return "concern"
    if any(kw in haystack for kw in ("opportunity", "upside", "chance")):
        return "opportunity"
    return "observation"


__all__ = [
    "ClassifierFailure",
    "classify_message",
    "is_llm_enabled",
]
