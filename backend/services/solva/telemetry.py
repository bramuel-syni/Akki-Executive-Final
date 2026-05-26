"""Solva telemetry — variant cycle + key emission counters.

Two purposes:

1. **Variant-cycle depth** (`solva_variant_seen`) — per-user, per-question-key,
   tracks which variant strings a user has seen. When the user completes the
   cycle (saw every variant the bank holds for that key) we emit a log event
   `solva.variant.cycle_complete` so analytics can see who is exhausting the
   bank and where we need more content.

2. **Question-key usage frequency** (`solva_key_emissions`) — per-emission row
   capturing `{question_key, emitted_at, account_id}`. Drives the admin
   endpoint `GET /api/admin/solva/key-usage?since=…`.

Both counters write through this module so the call site (the Phase D
session router) stays tiny.

Phase D.2 audit correction (2026-05-26) — instrumentation added after the
Julius-aopio bug surfaced. See HOME_CLEANUP_LOG.md → "D.2 — audit
correction" for the full root-cause writeup.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

from core import db


log = logging.getLogger("solva.telemetry")


# ─────────────────────────────────────────────────────────────────────
# (i) Variant-cycle depth — solva_variant_seen
# ─────────────────────────────────────────────────────────────────────
async def record_variant_seen(
    *,
    user_id: str,
    question_key: str,
    variant_label: str,
    total_variants_in_bank: int,
) -> None:
    """Upsert one row capturing that the user has seen this variant.

    Idempotent: the same (user_id, question_key, variant_label) tuple is
    a unique key — repeated emissions don't create duplicate rows. We
    capture the LATEST `seen_at` on every call so the analytics surface
    can show cycle progress over time.

    Emits the `solva.variant.cycle_complete` event the moment the user
    has seen every variant in the bank for that key.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    # Upsert by (user_id, question_key, variant_label).
    await db.solva_variant_seen.update_one(
        {
            "user_id":       user_id,
            "question_key":  question_key,
            "variant_label": variant_label,
        },
        {
            "$set": {
                "user_id":       user_id,
                "question_key":  question_key,
                "variant_label": variant_label,
                "seen_at":       now_iso,
            },
            "$setOnInsert": {
                "first_seen_at": now_iso,
            },
        },
        upsert=True,
    )
    # Cycle-complete detection. Cheap count(); only fires once per
    # (user_id, question_key) by gating on a separate event_log row.
    seen_count = await db.solva_variant_seen.count_documents({
        "user_id":      user_id,
        "question_key": question_key,
    })
    if seen_count >= total_variants_in_bank > 0:
        already_logged = await db.audit_log.find_one({
            "account_id": user_id,
            "action":     "solva.variant.cycle_complete",
            "resource_id": question_key,
        }, {"_id": 0, "id": 1})
        if not already_logged:
            import uuid as _uuid  # local import to avoid cycle
            await db.audit_log.insert_one({
                "id":            str(_uuid.uuid4()),
                "context_id":    None,
                "account_id":    user_id,
                "action":        "solva.variant.cycle_complete",
                "resource_type": "solva_question_key",
                "resource_id":   question_key,
                "metadata": {
                    "variants_in_bank": total_variants_in_bank,
                    "variants_seen":    seen_count,
                },
                "created_at": now_iso,
            })


async def get_variants_seen(
    *,
    user_id: str,
    question_key: str,
) -> List[str]:
    """Return the list of variant labels a user has already seen for
    a question key. Useful for analytics dashboards and the audit
    cycle-complete check. Excludes `_id` from the projection."""
    rows = await db.solva_variant_seen.find(
        {"user_id": user_id, "question_key": question_key},
        {"_id": 0, "variant_label": 1},
    ).to_list(length=100)
    return [r["variant_label"] for r in rows if r.get("variant_label")]


# ─────────────────────────────────────────────────────────────────────
# (ii) Question-key usage frequency — solva_key_emissions
# ─────────────────────────────────────────────────────────────────────
async def record_key_emission(
    *,
    question_key: str,
    account_id: str,
) -> None:
    """Append-only row per emission. Keeps the schema flat so the
    admin endpoint can `$group` by question_key without a join."""
    await db.solva_key_emissions.insert_one({
        "question_key": question_key,
        "account_id":   account_id,
        "emitted_at":   datetime.now(timezone.utc).isoformat(),
    })


# ─────────────────────────────────────────────────────────────────────
# (iii) Handoff deep-link analytics — reuse audit_log
# ─────────────────────────────────────────────────────────────────────
async def record_handoff(
    *,
    surface: str,           # "chat" or "solva"
    ctx_type: str,          # "document" / "cycle" / "work_studio_artefact" / ...
    ctx_id: str,
    account_id: str,
    chat_id:     Optional[str] = None,
    session_id:  Optional[str] = None,
    context_id:  Optional[str] = None,
) -> None:
    """Log a `handoff.<surface>_attached.<ctx_type>` action into the
    existing `audit_log` collection. Surface-agnostic on purpose — Chat
    and Solva both invoke this with their respective parent_id.

    Phase D.3-post-test analytics — fires the moment a linked-context
    item is FIRST persisted on a chat/session row, which is also the
    moment the LinkedContextChip will first render. We don't log on
    subsequent renders (page nav / resume) — those are presentation
    events, not handoffs, and would spam the audit log."""
    import uuid as _uuid
    action = f"handoff.{surface}_attached.{ctx_type}"
    await db.audit_log.insert_one({
        "id":            str(_uuid.uuid4()),
        "context_id":    context_id,
        "account_id":    account_id,
        "action":        action,
        "resource_type": f"solva_session" if surface == "solva" else "chat",
        "resource_id":   session_id or chat_id,
        "metadata": {
            "ctx_type": ctx_type,
            "ctx_id":   ctx_id,
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
    })


__all__ = [
    "record_variant_seen",
    "get_variants_seen",
    "record_key_emission",
    "record_handoff",
]
