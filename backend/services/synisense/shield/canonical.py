"""Synisense Shield — canonical chat ShieldOutcome mint (H2.5 follow-up).

Background
----------
Before this module, the chat-family streaming path had three surfaces
reporting Shield activity, each fed by a different engine:

  * ``db.chat_audit_log``           ← legacy ``adapter.shield_payload_async``
                                      (``synisense-pipeline`` vocabulary,
                                      lowercase ``by_category`` keys)
  * ``db.synisense_audit_log``      ← ``shield.client.prepare_for_streaming``
                                      (``synisense-shield-v1``,
                                      UPPERCASE ``de_id_summary`` keys)
  * ``db.synisense_runs``           ← ``adapter.shield_payload_async`` again,
                                      but with ``account_id=None`` and a
                                      phantom ``message_id`` so the
                                      ``/synisense-metrics`` aggregation
                                      never matched the row.

Independent ``e1_tester`` runs caught all three lying about the same turn:

  * Sync:               5 entities, ``CREDIT_CARD`` (uppercase),
                        ``synisense-shield-v1``
  * Stream envelope:    1 entity,   ``card`` (lowercase),
                        ``synisense-pipeline``
  * Stream Shield audit:2 entities, ``CREDIT_CARD`` (uppercase)

Same input, three different counts, two different vocabularies. The
``audit_invariant_violations`` collection couldn't catch this because the
divergence was BY DESIGN — three engines computing three answers.

Fix
---
``mint_chat_outcome()`` runs **one** ``deidentifier.deidentify(user_text)``
pass and persists a ``synisense_runs`` row keyed on the correct
``(account_id, chat_id, message_id, surface="chat")`` so:

  * The chat envelope (``user_msg.shielding``) reads from this outcome.
  * The chat_audit row's ``identifiers_detected`` / ``by_category`` /
    ``shielded_for_llm`` derive from this outcome.
  * ``/api/chats/{id}/synisense-metrics`` and per-message
    ``/synisense-runs`` aggregate over the same row this outcome wrote.
  * The Shield audit row (written separately by
    ``prepare_for_streaming.finalize`` on the FULL prompt) carries
    UPPERCASE ``de_id_summary`` keys → category vocabulary parity.

All three surfaces now agree on the boolean *"did Shield detect
identifiers this turn?"* AND on the category vocabulary
(``CREDIT_CARD``, ``PERSON``, ``EMAIL`` … UPPERCASE).

Non-goals
---------
This mint does NOT replace ``prepare_for_streaming``. The LLM-bound
``full_prompt`` (which carries history + grounding from earlier turns)
still goes through Shield's streaming wrapper so prior-turn PII in
history gets re-redacted. That wrapper writes its own
``synisense_audit_log`` row — its counts are a superset of this mint's
counts (history identifiers are added), but the BOOLEAN agrees.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from services.synisense.shield import deidentifier
from services.synisense.shield.exceptions import ShieldFailure

logger = logging.getLogger("akki.synisense.shield.canonical")

SHIELDED_BY = "synisense-shield-v1"
_CHAT_SURFACE = "chat"


@dataclass(frozen=True)
class ChatShieldOutcome:
    """Single source of truth for "what did Shield do to the user's
    current message this turn?" Every surface that reports per-turn
    Shield activity (chat_audit_log, synisense_runs, user_msg.shielding)
    derives its counts from this object."""

    redacted_text: str
    token_map: Dict[str, str]
    de_id_summary: Dict[str, int]   # UPPERCASE keys
    identifiers_masked: int
    shielded_by: str = SHIELDED_BY

    @property
    def by_category(self) -> Dict[str, int]:
        # Alias the legacy `by_category` shape onto `de_id_summary`.
        # Keys stay UPPERCASE for parity with `synisense_audit_log`.
        return dict(self.de_id_summary)

    def envelope(self) -> Dict[str, Any]:
        """The dict shape ``user_msg.shielding`` expects.

        Matches the legacy ``_syn_report(shield_map)`` contract so the
        chat UI's redaction badge keeps rendering unchanged."""
        return {
            "identifiers_masked": self.identifiers_masked,
            "by_category": self.by_category,
            "shielded_by": self.shielded_by,
        }


async def mint_chat_outcome(
    *,
    user_text: str,
    tenant_id: str,
    account_id: str,
    chat_id: str,
    message_id: str,
    context_id: Optional[str] = None,
) -> ChatShieldOutcome:
    """Run Shield's de-identifier on ``user_text`` and persist a
    ``synisense_runs`` row so ``/synisense-metrics`` finds the
    activity. Returns the canonical outcome.

    Fail-closed: any ``ServiceUnavailable`` from the de-identifier
    raises ``ShieldFailure``. The caller is the chat route, which
    translates to HTTP 503 + writes an
    ``audit_invariant_violations`` ``shield_failure_at_entry`` row.
    """
    try:
        deid_result = await deidentifier.deidentify(
            user_text or "", tenant_id=tenant_id,
        )
    except Exception as exc:  # noqa: BLE001 — translated to ShieldFailure
        raise ShieldFailure(
            f"Synisense Shield de-identifier failed: "
            f"{type(exc).__name__}: {str(exc)[:200]}",
            original=exc, surface=_CHAT_SURFACE,
        ) from exc

    de_id_summary = dict(deid_result.de_id_summary or {})
    identifiers_masked = sum(int(v) for v in de_id_summary.values())

    outcome = ChatShieldOutcome(
        redacted_text=deid_result.redacted_text,
        token_map=dict(deid_result.token_map or {}),
        de_id_summary=de_id_summary,
        identifiers_masked=identifiers_masked,
    )

    # Persist a synisense_runs row mirroring `pipeline.run()`'s shape
    # so `/synisense-metrics` and `/synisense-runs` aggregate over the
    # same source of truth as the chat audit + envelope.
    #
    # Spans: synthesized one-per-token from `de_id_summary` because
    # `DeIdResult` doesn't surface per-span offsets. The metrics query
    # only uses `$size` of the spans array — it does not read
    # individual spans — so a length-correct array is sufficient.
    spans = []
    for entity_type, count in de_id_summary.items():
        for _ in range(int(count or 0)):
            spans.append({
                "entity_type": entity_type,
                "source": "synisense-shield-v1",
                "confidence": None,
            })

    try:
        from core import db
        await db.synisense_runs.insert_one({
            "id": str(uuid.uuid4()),
            "context_id": context_id or "",
            "account_id": account_id,
            "chat_id": chat_id,
            "message_id": message_id,
            "surface": _CHAT_SURFACE,
            "mode": "redact",
            "ts": datetime.now(timezone.utc),
            "spans": spans,
            "stats": {
                "layer_won": "synisense-shield-v1",
                "elapsed_ms": int(deid_result.elapsed_ms or 0),
            },
            "synisense_version": SHIELDED_BY,
        })
    except Exception as exc:  # noqa: BLE001 — non-fatal, log & continue
        logger.warning(
            "synisense_runs persist failed (chat mint): %s: %s",
            type(exc).__name__, str(exc)[:200],
        )

    return outcome


__all__ = ["ChatShieldOutcome", "mint_chat_outcome", "SHIELDED_BY"]
