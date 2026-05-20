"""Chunk seed script (renamed from `seed_chunk8_overlay.py` 2026-05-18).

Idempotent. Run via:

    cd /app/backend && python scripts/seed_chunks.py

Currently seeds:

  · **Chunk 8 — Document Overlay** (QA-2026-05-16-029…-036).
    Pass A enriches existing `work_studio_exports` rows missing
    chunk-8 fields. Pass B mints one fresh Draft committee_pack per
    bramuel context with ≥1 source doc.

  · **Chunk 9 — Add-a-Contribution** (QA-2026-05-16-017…-021).
    Pass C ensures bramuel's first context-with-documents has at
    least one active cycle + one agenda item + one team member, so
    render-smoke step 10 can hard-assert the attach flow end-to-end.

Future chunks add their own pass functions here — keep them
narrowly-scoped and idempotent (use marker fields per row).

Marker collection: `chunk8_seed_log` (kept under that name to
preserve existing audit-trail continuity; Chunk-9 rows also
append).
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

# Add backend root to path so we can import core / services.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

BRAMUEL_EMAIL = "bramuel@syni.ai"


def _iso(d: datetime) -> str:
    return d.isoformat()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _intel_for_kind(kind: str, source_doc_names: List[str]) -> Dict[str, Any]:
    """Realistic intelligence_report payload sized to the artefact kind.

    Confidence band is tuned to surface all three RAG colours across
    the seed set: committee_pack high, report mid, deck lower.
    """
    if kind == "committee_pack":
        return {
            "confidence_pct": 86,
            "period": "Q3 2025-26",
            "framing": "executive",
            "sources_count": len(source_doc_names),
            "pending_recommendations": 2,
            "sources": [
                {"doc_id": f"doc-{i}", "name": n, "period": "Q3"}
                for i, n in enumerate(source_doc_names)
            ],
            "sections": [
                {"heading": "Capital position", "confidence_pct": 91, "source_doc_ids": source_doc_names[:1]},
                {"heading": "Risk register", "confidence_pct": 78, "source_doc_ids": source_doc_names[:2]},
                {"heading": "Strategy delivery", "confidence_pct": 82, "source_doc_ids": source_doc_names[1:3]},
            ],
            "framing_analysis": (
                "The pack is framed for the audit committee, foregrounding "
                "capital adequacy + the three live risks the CRO flagged at "
                "the May steering meeting."
            ),
            "gaps": [
                "No external auditor letter referenced for Q3.",
                "Liquidity ratio Q3 actuals not yet attached.",
            ],
            "recommendations": [
                {"rank": 1, "text": "Confirm the September capital injection timeline before commit.", "addressed": False},
                {"rank": 2, "text": "Schedule a follow-up review of the strategic deposit-mix shift.", "addressed": False},
            ],
            "audit": {
                "generated_at": _iso(_now()),
                "model_version": "shield-claude-sonnet-4.5",
                "source_document_ids": source_doc_names,
            },
        }
    if kind == "report":
        return {
            "confidence_pct": 72,
            "period": "Q2 2025-26",
            "framing": "executive",
            "sources_count": len(source_doc_names),
            "pending_recommendations": 1,
            "sources": [{"doc_id": f"doc-{i}", "name": n, "period": "Q2"} for i, n in enumerate(source_doc_names)],
            "sections": [
                {"heading": "Executive summary", "confidence_pct": 81, "source_doc_ids": source_doc_names[:1]},
                {"heading": "Market scan", "confidence_pct": 64, "source_doc_ids": source_doc_names[:2]},
            ],
            "framing_analysis": "Standalone executive read; tightening recommended on the market-scan section.",
            "gaps": ["Q2 competitor pricing benchmark not refreshed."],
            "recommendations": [{"rank": 1, "text": "Refresh the pricing benchmark before this report is referenced in board materials.", "addressed": False}],
            "audit": {"generated_at": _iso(_now()), "model_version": "shield-claude-sonnet-4.5",
                      "source_document_ids": source_doc_names},
        }
    if kind == "deck":
        return {
            "confidence_pct": 48,
            "period": "Q3 2025-26",
            "framing": "executive",
            "sources_count": len(source_doc_names),
            "pending_recommendations": 3,
            "sources": [{"doc_id": f"doc-{i}", "name": n} for i, n in enumerate(source_doc_names)],
            "sections": [
                {"heading": "Cover", "confidence_pct": 60, "source_doc_ids": source_doc_names[:1]},
                {"heading": "Numbers", "confidence_pct": 45, "source_doc_ids": source_doc_names[:1]},
                {"heading": "Asks", "confidence_pct": 38, "source_doc_ids": source_doc_names[:1]},
            ],
            "framing_analysis": "Light framing; this deck needs more substantive evidence before board distribution.",
            "gaps": [
                "Q3 actuals not yet folded into the numbers slide.",
                "Customer satisfaction data not attached.",
                "Competitor benchmark missing.",
            ],
            "recommendations": [
                {"rank": 1, "text": "Attach Q3 actuals.", "addressed": False},
                {"rank": 2, "text": "Add customer satisfaction trend chart.", "addressed": False},
                {"rank": 3, "text": "Refresh the competitor benchmark slide.", "addressed": False},
            ],
            "audit": {"generated_at": _iso(_now()), "model_version": "shield-claude-sonnet-4.5",
                      "source_document_ids": source_doc_names},
        }
    # minutes / brief / other → minimal but non-empty.
    return {
        "confidence_pct": 70,
        "period": None,
        "framing": "executive",
        "sources_count": len(source_doc_names),
        "pending_recommendations": 0,
        "sources": [{"doc_id": f"doc-{i}", "name": n} for i, n in enumerate(source_doc_names)],
        "sections": [],
        "framing_analysis": "Standard structure.",
        "gaps": [],
        "recommendations": [],
        "audit": {"generated_at": _iso(_now()), "model_version": "shield-claude-sonnet-4.5",
                  "source_document_ids": source_doc_names},
    }


def _draft_structured_content() -> Dict[str, Any]:
    return {
        "sections": [
            {
                "heading": "Executive summary",
                "paragraphs": [
                    "The committee considered the Q3 results, the September "
                    "capital injection timeline, and the live risks raised by "
                    "the CRO at the May steering session.",
                    "Capital adequacy stood at 14.2% at quarter-end, "
                    "comfortably above the regulatory floor but trending "
                    "down quarter-on-quarter.",
                ],
            },
            {
                "heading": "Capital position",
                "paragraphs": [
                    "CET1 stands at 14.2%, down from 14.6% in Q2. The "
                    "scheduled capital injection in September is expected "
                    "to restore the ratio to 15.4%.",
                    "Provisioning coverage moved to 47% at month-end, "
                    "below the management 50% target and at the floor of "
                    "the regulatory comfort band.",
                ],
            },
            {
                "heading": "Risk register",
                "paragraphs": [
                    "Three active risks: concentration in the top-5 "
                    "borrowers, fraud-incident rate trending up at 3.8% "
                    "month-on-month, and a key-person dependency on the "
                    "CFO role pending succession planning.",
                ],
            },
            {
                "heading": "Strategy delivery",
                "paragraphs": [
                    "Deposit-mix shift on track at 62% retail / 38% "
                    "corporate (target 65/35). Digital-channel adoption "
                    "ahead of plan at 51% monthly actives.",
                ],
            },
        ],
    }


async def _enrich_existing_export(db, row: Dict[str, Any], doc_ids: List[str], doc_names: List[str]) -> Dict[str, Any]:
    """Apply chunk-8 enrichment to a pre-existing export row that's
    missing the new fields. Idempotent — skips if already enriched."""
    aid = row["id"]
    cid = row["context_id"]
    needs_intel = not row.get("intelligence_report")
    needs_sources = not row.get("source_document_ids")
    if not (needs_intel or needs_sources):
        return {"id": aid, "context_id": cid, "skipped": True}
    kind = (row.get("kind") or "report").lower()
    updates: Dict[str, Any] = {"updated_at": _iso(_now())}
    if needs_sources:
        updates["source_document_ids"] = doc_ids[:3]
    if needs_intel:
        updates["intelligence_report"] = _intel_for_kind(kind, doc_names[:3])
    await db.work_studio_exports.update_one(
        {"id": aid, "context_id": cid},
        {"$set": updates},
    )
    return {"id": aid, "context_id": cid, "kind": kind, "skipped": False,
            "updates": list(updates.keys())}


async def _seed_draft_committee_pack(db, context_id: str, account_id: str,
                                     doc_ids: List[str], doc_names: List[str]) -> Dict[str, Any]:
    """Mint one fresh Draft committee_pack so the full editable round-trip
    is exercisable on the live preview. Idempotent via the
    `chunk8_seed_marker` field — re-runs return the existing draft."""
    existing = await db.work_studio_exports.find_one(
        {"context_id": context_id, "chunk8_seed_marker": "draft_committee_pack_v1"},
        {"_id": 0, "id": 1},
    )
    if existing:
        return {"id": existing["id"], "context_id": context_id, "minted": False}
    aid = f"ws-c8-seed-{uuid.uuid4().hex[:8]}"
    now_iso = _iso(_now())
    await db.work_studio_exports.insert_one({
        "id": aid,
        "context_id": context_id,
        "account_id": account_id,
        "kind": "committee_pack",
        "status": "complete",
        "file_name": "Audit Committee Pack — Q3 2025-26.docx",
        "document_title": "Audit Committee Pack — Q3 2025-26",
        "lifecycle_state": "draft",
        "legacy": False,
        "structured_content": _draft_structured_content(),
        "source_document_ids": doc_ids[:3],
        "intelligence_report": _intel_for_kind("committee_pack", doc_names[:3]),
        "chunk8_seed_marker": "draft_committee_pack_v1",
        "created_at": now_iso,
        "updated_at": now_iso,
    })
    return {"id": aid, "context_id": context_id, "minted": True}


async def _seed_chunk9_cycle_fixture(db, context_id: str, account_id: str,
                                     doc_ids: List[str]) -> Dict[str, Any]:
    """Chunk 9 (QA-2026-05-16-017→-021) — ensure the context has at
    least one active cycle + one agenda item + one team member so
    render-smoke step 10 can hard-assert the Add-a-Contribution
    attach flow end-to-end. Idempotent via `chunk9_seed_marker`.

    Data model alignment (verified against `routers/cycles.py` +
    `services/cycle_lifecycle.py`):

      • `db.cycles`         — the master cycle row (status="active").
      • `db.cycle_agendas`  — id == cycle_id (NOT a separate
                              agenda_id); carries `items: [...]` for
                              the contributions tab dropdown.
      • `db.cycle_team`     — agenda_id == cycle_id; status="active";
                              owns_item_ids references the seeded item
                              so PO-decision-#2 eligible-contributors
                              filter resolves.

    Skipped when the context already has ANY active cycle row
    (don't pollute live data — re-run-safe via marker check).
    """
    existing_marker = await db.cycles.find_one(
        {"context_id": context_id, "chunk9_seed_marker": "v1"},
        {"_id": 0, "id": 1},
    )
    if existing_marker:
        return {
            "context_id": context_id,
            "cycle_id": existing_marker.get("id"),
            "minted": False,
            "reason": "already_seeded",
        }

    # Don't trample any existing cycle — only seed when there is NO
    # active cycle in the context.
    existing_any = await db.cycles.find_one(
        {"context_id": context_id, "status": "active"}, {"_id": 0, "id": 1},
    )
    if existing_any:
        return {
            "context_id": context_id, "minted": False,
            "reason": "context_has_active_cycle",
        }

    cycle_id = f"cyc-c9-{uuid.uuid4().hex[:8]}"
    item_id = f"agi-c9-{uuid.uuid4().hex[:8]}"
    member_id = f"tm-c9-{uuid.uuid4().hex[:8]}"
    now_iso = _iso(_now())

    # 1. db.cycles — master row (required by `resolve_implicit_cycle_id`).
    await db.cycles.insert_one({
        "id": cycle_id,
        "context_id": context_id,
        "account_id": account_id,
        "title": "Q3 Capital & Risk Review",
        "status": "active",
        "chunk9_seed_marker": "v1",
        "created_at": now_iso,
        "activated_at": now_iso,
        "closed_at": None,
    })
    # 2. db.cycle_agendas — id == cycle_id, with one item so the
    #    contributions tab's item dropdown has a selectable option.
    await db.cycle_agendas.insert_one({
        "id": cycle_id,
        "cycle_id": cycle_id,
        "context_id": context_id,
        "account_id": account_id,
        "title": "Q3 Capital & Risk Review",
        "items": [{
            "id": item_id,
            "label": "Risk register update",
            "owner_label": "Bramuel Test Contributor",
        }],
        "status": "active",
        "chunk9_seed_marker": "v1",
        "created_at": now_iso,
        "updated_at": now_iso,
    })
    # 3. db.cycle_team — agenda_id MUST equal cycle_id (the GET
    #    /cycle/team query filters on that). status=active is also
    #    required by that filter. owns_item_ids[] keeps PO-decision-#2
    #    eligible-contributors dropdown populated.
    await db.cycle_team.insert_one({
        "id": member_id,
        "agenda_id": cycle_id,
        "cycle_id": cycle_id,
        "context_id": context_id,
        "name": "Bramuel Test Contributor",
        "email": "bramuel-tc@syni.ai",
        "role": "CFO",
        "contribution_description": (
            "Quarterly capital adequacy and provisioning coverage data, "
            "plus a one-page risk-register commentary."
        ),
        "owns_item_ids": [item_id],
        "status": "active",
        "chunk9_seed_marker": "v1",
        "created_at": now_iso,
    })
    return {
        "context_id": context_id,
        "cycle_id": cycle_id,
        "agenda_item_id": item_id,
        "team_member_id": member_id,
        "minted": True,
    }


async def _seed_chunk95_pii_chat_fixture(db, context_id: str, account_id: str) -> Dict[str, Any]:
    """Chunk 9.5 fix-pass (Sx2 verification) — seed one chat per
    bramuel context that contains realistic PII so the e1_tester can
    observe IDENTIFIERS REDACTED > 0 on the Trust Panel without
    needing to manually drive Shield through the live UI.

    Inserts:
      • `db.chats`            — chat row with `created_at` stored as
                                STRING (deliberately exercising the
                                Sx2 type-coercion path). One assistant
                                + one user message.
      • `db.chat_messages`    — two message rows (user + assistant).
      • `db.synisense_runs`   — one chat-surface run with realistic
                                spans (regex won — financial account
                                pattern + person name + currency
                                figure). `ts` stored as a DATETIME
                                (so the Sx2 fix's coercion is what
                                makes the metrics query match).

    Idempotent via `chunk95_pii_chat_marker="v1"` on the chat row.
    """
    existing = await db.chats.find_one(
        {"context_id": context_id, "chunk95_pii_chat_marker": "v1"},
        {"_id": 0, "id": 1},
    )
    if existing:
        return {
            "context_id": context_id, "chat_id": existing["id"],
            "minted": False, "reason": "already_seeded",
        }

    chat_id = f"chat-c95-{uuid.uuid4().hex[:10]}"
    user_msg_id = f"msg-{uuid.uuid4().hex[:10]}"
    asst_msg_id = f"msg-{uuid.uuid4().hex[:10]}"
    run_id = f"sr-c95-{uuid.uuid4().hex[:10]}"
    audit_id = f"aud-c95-{uuid.uuid4().hex[:10]}"
    now_dt = _now()
    now_iso = _iso(now_dt)

    user_text = (
        "Bramuel and Udi are having dinner at Citi Bank, account number "
        "4565789845, discussing a $2.4M deal."
    )
    assistant_text = (
        "Noted. Without disclosing personal account details, I can sketch how "
        "to approach a deal at that scale — what aspect would you like to "
        "explore first: deal structure, capital adequacy implications, or "
        "stakeholder framing?"
    )

    # Chat row. created_at STRING — deliberately exercises the Sx2 fix.
    await db.chats.insert_one({
        "id": chat_id,
        "account_id": account_id,
        "context_id": context_id,
        "title": "Bramuel and Udi — Citi dinner (PII probe)",
        "created_at": now_iso,
        "updated_at": now_iso,
        "message_count": 2,
        "last_message_preview": (assistant_text[:120] + "…")[:140],
        "synisense_audit_ids": [audit_id],
        "chunk95_pii_chat_marker": "v1",
    })

    # User + assistant messages.
    await db.chat_messages.insert_many([
        {"id": user_msg_id, "chat_id": chat_id, "account_id": account_id,
         "context_id": context_id, "role": "user", "content": user_text,
         "content_preview": user_text[:140], "created_at": now_iso},
        {"id": asst_msg_id, "chat_id": chat_id, "account_id": account_id,
         "context_id": context_id, "role": "assistant", "content": assistant_text,
         "content_preview": assistant_text[:140], "created_at": now_iso,
         "model_id": "claude-sonnet-4-5"},
    ])

    # Synisense run — mimics what `services.synisense.shield.client.invoke`
    # would have written for this PII-laden message. THREE detected spans
    # (PERSON · FIN_ACCOUNT · CURRENCY); regex layer won the redaction.
    # `ts` is a real datetime — this is the type that mismatched the
    # STRING `chat.created_at` filter pre-fix.
    await db.synisense_runs.insert_one({
        "id": run_id,
        "audit_id": audit_id,
        "account_id": account_id,
        "context_id": context_id,
        "chat_id": chat_id,
        "message_id": asst_msg_id,
        "surface": "chat",
        "ts": now_dt,                       # BSON Date — type bracket vs chat.created_at STRING
        "provider": "anthropic",
        "model": "claude-sonnet-4-5",
        "spans": [
            {"layer": "regex", "kind": "FIN_ACCOUNT",
             "original": "4565789845", "token": "FIN_1"},
            {"layer": "regex", "kind": "PERSON",
             "original": "Bramuel",   "token": "PERSON_1"},
            {"layer": "regex", "kind": "CURRENCY",
             "original": "$2.4M",     "token": "CURRENCY_1"},
        ],
        "stats": {
            "layer_won": "regex",
            "exposure_reduction": 18.4,
            "dilution": 11.2,
            "input_chars": len(user_text),
            "output_chars": len(assistant_text),
        },
    })

    return {
        "context_id": context_id,
        "chat_id": chat_id,
        "synisense_run_id": run_id,
        "spans_seeded": 3,
        "minted": True,
    }


async def _seed_chunk10_pulse_signal_fixture(db, context_id: str, account_id: str) -> Dict[str, Any]:
    """Chunk 10 (QA-2026-05-16-022..-028) — seed one Pulse signal per
    bramuel context with `comments[]` pre-populated AND a `reasoning`
    field that contains both a document-citation pattern (so QA-026
    stripping is visible) AND multiple distinct points separated by
    `\\n\\n` (so QA-026 bullet formatting kicks in). Idempotent via
    `chunk10_pulse_marker="v1"` on the signal row.

    Hard-asserts in render-smoke step 12 cover:
      • QA-022 — saved comment renders inline on the card
      • QA-024/027 — Saved chip + chip cluster on the drawer
      • QA-026 — reasoning section renders as a `<ul>`, citations stripped
    """
    existing = await db.signals.find_one(
        {"context_id": context_id, "chunk10_pulse_marker": "v1"},
        {"_id": 0, "id": 1},
    )
    if existing:
        return {
            "context_id": context_id, "signal_id": existing["id"],
            "minted": False, "reason": "already_seeded",
        }

    signal_id = f"sig-c10-{uuid.uuid4().hex[:10]}"
    comment_id = f"cm-c10-{uuid.uuid4().hex[:10]}"
    now_dt = _now()
    now_iso = _iso(now_dt)

    await db.signals.insert_one({
        "id": signal_id,
        "context_id": context_id,
        "account_id": account_id,
        "headline": "Capital adequacy buffer thinning vs Q1 baseline",
        "summary": (
            "CET1 ratio drift suggests the capital buffer is "
            "narrowing into a zone the audit committee should flag "
            "before Q3 close. [doc:Q2_capital_pack.pdf]"
        ),
        "body": (
            "CET1 has dropped 80bps quarter-on-quarter while RWA has "
            "grown 4.2%. Headroom against the regulatory minimum is "
            "now 1.6× — historical low for the past 8 quarters. "
            "(source: Q2_capital_pack.pdf)"
        ),
        "reasoning": (
            "The buffer is being eroded by two simultaneous pressures.\n\n"
            "Risk-weighted assets are up 4.2% driven by the H1 lending "
            "campaign in the SME segment — credit risk weights average "
            "75% vs 35% for the retained portfolio. (p. 14)\n\n"
            "Tier-1 capital has stagnated because retained earnings are "
            "being absorbed by the deferred-tax catch-up from the FY25 "
            "restatement. [doc:audit_report.pdf]\n\n"
            "If both trends persist, headroom drops to 1.2× by year-end — "
            "below the board's internal tolerance of 1.5×."
        ),
        "type": "risk",
        "surface_type": "risk",
        "signal_kind": "capital",
        "topic_class": "capital",
        "freshness": "new",
        "confidence": "high",
        "data_trust": "verified",
        "merge_count": 1,
        "state": "active",
        "status": "active",
        "created_at": now_iso,
        "references": [
            {"label": "Q2 capital pack", "doc_id": "stub-doc-1"},
            {"label": "Audit report", "doc_id": "stub-doc-2"},
        ],
        "comments": [{
            "id": comment_id,
            "account_id": account_id,
            "note": "Seeded private note — committee should ask Treasury for the contingency plan ahead of Q3.",
            "created_at": now_iso,
        }],
        "chunk10_pulse_marker": "v1",
    })

    return {
        "context_id": context_id,
        "signal_id": signal_id,
        "comment_id": comment_id,
        "minted": True,
    }


async def _seed_chunk11_monitor_fixture(db, context_id: str, account_id: str) -> Dict[str, Any]:
    """Chunk 11 (QA-2026-05-16-045) — seed one `achieved`-state
    objective per bramuel context so render-smoke step 13 can
    hard-assert the new Achieved tab + count badge. Idempotent via
    `chunk11_monitor_marker="v1"`.
    """
    existing = await db.objectives.find_one(
        {"context_id": context_id, "chunk11_monitor_marker": "v1"},
        {"_id": 0, "id": 1},
    )
    if existing:
        return {
            "context_id": context_id, "objective_id": existing["id"],
            "minted": False, "reason": "already_seeded",
        }
    oid = f"obj-c11-{uuid.uuid4().hex[:10]}"
    now_iso = _iso(_now())
    await db.objectives.insert_one({
        "id": oid,
        "context_id": context_id,
        "account_id": account_id,
        "kind": "objective",
        "title": "Achieved: 100% audit-pack readiness (Chunk 11 seed)",
        "rag_status": "achieved",
        "score": 100,
        "trend": "flat",
        "source": "manual",
        "source_refs": [],
        "owner": {"role": "CFO"},
        "created_at": now_iso,
        "updated_at": now_iso,
        "chunk11_monitor_marker": "v1",
    })
    return {"context_id": context_id, "objective_id": oid, "minted": True}


async def _seed_chunk12_strategic_goal_fixture(db, context_id: str, account_id: str) -> Dict[str, Any]:
    """Chunk 12 (QA-2026-05-16-049) — seed two strategic goals per
    bramuel context so render-smoke step 14 can hard-assert:
      (a) goal with documents in scope → Update flow works
      (b) goal with NO related evidence → no-data short-circuit
          renders the verbatim spec copy

    Pass G — original chunk-12 fixture. Pass H (below) supplements
    with a fixture goal carrying a deterministic
    `seed_origin="chunk_12_no_data"` marker for the fix-pass
    verification path (Gap 1 — tester finding 2026-05-21).

    `gid_a` carries a pre-baked `last_akki_update` so render-smoke
    step 14 can observe the new card-level "Reassessed · …"
    timestamp affordance (Gap 2 — fix-pass) WITHOUT requiring an
    LLM round-trip through Shield.

    Idempotent via `chunk12_strategic_marker="v1"`.
    """
    existing = await db.strategic_goals.find_one(
        {"context_id": context_id, "chunk12_strategic_marker": "v1"},
        {"_id": 0, "id": 1},
    )
    if existing:
        # Idempotent backfill (Chunk 12 fix-pass Gap 2 — 2026-05-21):
        # set `last_akki_update` on the with-evidence row if missing.
        # This was added to the schema after Pass G first ran on
        # 2026-05-21 03:15 UTC; without the backfill, existing rows
        # don't surface the new card-level timestamp affordance and
        # the smoke step can't verify it.
        backfill_iso = _iso(_now())
        await db.strategic_goals.update_many(
            {
                "context_id": context_id,
                "chunk12_strategic_marker": "v1",
                "id": {"$regex": "^goal-c12a-"},
                "last_akki_update": {"$exists": False},
            },
            {"$set": {"last_akki_update": {
                "audit_id": f"backfill-{uuid.uuid4().hex[:10]}",
                "assessed_at": backfill_iso,
                "no_data": False,
                "rationale": "Backfilled baseline assessment (fix-pass Gap 2 — Q3 CET1 ratio trending toward target).",
                "supporting_signal_ids": [],
                "supporting_doc_ids": [],
                "applied_changes": {"current_score": 55, "probability": 50, "status": "at_risk"},
            }}},
        )
        return {
            "context_id": context_id, "goal_id": existing["id"],
            "minted": False, "reason": "already_seeded",
        }
    gid_a = f"goal-c12a-{uuid.uuid4().hex[:8]}"
    gid_b = f"goal-c12b-{uuid.uuid4().hex[:8]}"
    now_iso = _iso(_now())
    # Pre-baked `last_akki_update` for the with-evidence goal so the
    # card-level timestamp surface is observable on initial mount.
    # Mirrors the shape produced by routers/strategic_goal_assessment.py
    # on the success path (see SYSTEM_STATE.md § Chunk 12 contract).
    baked_last_update = {
        "audit_id": f"seeded-audit-{uuid.uuid4().hex[:10]}",
        "assessed_at": now_iso,
        "no_data": False,
        "rationale": "Seeded baseline assessment — Q3 CET1 ratio trending toward target.",
        "supporting_signal_ids": [],
        "supporting_doc_ids": [],
        "applied_changes": {"current_score": 55, "probability": 50, "status": "at_risk"},
    }
    await db.strategic_goals.insert_many([
        {
            "id": gid_a,
            "context_id": context_id, "account_id": account_id,
            "department": "cfo",
            "title": "Lift CET1 capital ratio to 12.5% by Q3 (Chunk 12 seed)",
            "description": "Push regulatory capital headroom against the 1.5× internal tolerance.",
            "category": "revenue",
            "current_score": 55, "target_score": 100, "probability": 50,
            "status": "at_risk", "score_history": [],
            "last_akki_update": baked_last_update,
            "created_at": now_iso, "updated_at": now_iso,
            "chunk12_strategic_marker": "v1",
        },
        {
            "id": gid_b,
            "context_id": context_id, "account_id": account_id,
            "department": "marketing",
            "title": "Improve brand sentiment to 80% positive (Chunk 12 no-data seed)",
            "description": "Reframe public messaging around capital strength.",
            "category": "people",
            "current_score": 42, "target_score": 80, "probability": 35,
            "status": "off_track", "score_history": [],
            "created_at": now_iso, "updated_at": now_iso,
            "chunk12_strategic_marker": "v1",
        },
    ])
    return {
        "context_id": context_id,
        "goal_with_evidence_id": gid_a,
        "goal_without_evidence_id": gid_b,
        "minted": True,
    }


async def _seed_chunk12_no_data_strategic_goal_fixture(
    db, context_id: str, account_id: str,
) -> Dict[str, Any]:
    """Chunk 12 fix-pass (2026-05-21) — Gap 1 closure.

    Tester finding: no goal-without-docs fixture is discoverable in any
    reachable bramuel context, so the no-data UI branch can't be
    end-to-end verified through the live preview UI. Pytest already
    exercises the branch (`test_qa049_update_goal_no_evidence_short_circuit`
    + `_llm_says_irrelevant`); this pass closes the gap for manual
    tester walkthroughs.

    Inserts ONE explicitly-marked goal per bramuel context that:
      • Has `source_document_ids = []` (the schema flag tester targets)
      • Carries `seed_origin = "chunk_12_no_data"` so tester can grep it
      • Has a verbatim recognisable title "QA Chunk 12 — no-data fixture"
      • Does NOT pre-populate `last_akki_update` (so the first Update
        Goal click produces the no-data short-circuit on the LLM path)

    Idempotent via `chunk12_no_data_seed_marker="v1"`.
    """
    existing = await db.strategic_goals.find_one(
        {"context_id": context_id, "chunk12_no_data_seed_marker": "v1"},
        {"_id": 0, "id": 1},
    )
    if existing:
        return {
            "context_id": context_id, "goal_id": existing["id"],
            "minted": False, "reason": "already_seeded",
        }
    gid = f"goal-c12nd-{uuid.uuid4().hex[:8]}"
    now_iso = _iso(_now())
    await db.strategic_goals.insert_one({
        "id": gid,
        "context_id": context_id, "account_id": account_id,
        "department": "cfo",
        "title": "QA Chunk 12 — no-data fixture",
        "description": "Seeded with no linked documents so the Update Goal flow exercises the no-data short-circuit verbatim copy + Document Journal link.",
        "category": "operations",
        "current_score": 30, "target_score": 80, "probability": 25,
        "status": "off_track",
        "score_history": [],
        "source_document_ids": [],
        "seed_origin": "chunk_12_no_data",
        "chunk12_no_data_seed_marker": "v1",
        "created_at": now_iso, "updated_at": now_iso,
    })
    return {
        "context_id": context_id,
        "goal_id": gid,
        "minted": True,
    }


# ----------------------------------------------------------------------
# Pass I — Chunk 14 fix-pass (2026-05-21) — populated Phase D session
# fixture so render-smoke + tester can verify SV-06 (markdown-light
# rendering) and SV-07 (60vh output panel sizing) end-to-end against a
# real session.
#
# Tester finding from Chunk-14 run: 76 Phase D sessions exist for
# bramuel but every reachable one is in `entry` / `layer_1` state with
# no substantive rendered prose. SV-06 / SV-07 acceptance requires a
# session in `done` state with synthesis content that exercises the
# three markdown features (paragraphs · bullets · `**bold**`).
#
# Scope (per dispatch):
#   - Insert ONE fully-populated Phase D session per bramuel context
#     (we honour "or just one context — pick executive_personal" — we
#     pick ALL bramuel contexts because the per-context cost is small
#     and downstream RBAC will gate reachability anyway; the
#     identifiable title makes the fixture easy to grep).
#   - Idempotent via `chunk14_populated_seed_marker="v1"`.
#   - No new collections.
# ----------------------------------------------------------------------

# Verbatim governance-themed sample content from the orchestrator
# dispatch. Used as both the framing baseline and the rendered
# synthesis so SV-06 (paragraphs · `- ` bullets · `1. ` numbered ·
# `**bold**`) renders against deterministic content.
_CHUNK_14_SYNTHESIS_PROSE = """Three governance themes emerged from the prior session:

- Strategic alignment between board and management on **capital allocation priorities**
- Risk appetite ambiguity around emerging market expansion, which requires **explicit board sign-off** per the Risk Charter
- Succession planning for the CFO role — currently **no documented successor**

The Audit Committee should consider three actions:

1. Commission an independent review of the **capital allocation framework**
2. Update the Risk Charter to include emerging market thresholds
3. Mandate a quarterly **CFO succession review**

These actions align with the **2026-2028 strategic horizon** and address the most material **governance gaps** identified."""

# Framing prose — 4 paragraphs of substantive governance content (the
# dispatch requested "3-5 paragraphs of governance-themed content").
_CHUNK_14_FRAMING_PROSE = """We're approaching the Q3 board meeting and I want to think through three governance tensions before the session.

First, the audit committee has flagged that our capital allocation framework hasn't been refreshed since 2024. The current thresholds for material capex decisions feel low given the inflation-adjusted scale of our balance sheet. I'm wondering whether the board should request a refresh ahead of the FY26 budget cycle, or wait until the formal triennial review in 2027.

Second, our risk charter doesn't explicitly address emerging market exposure beyond a single line about "appropriate diversification". Management has been increasingly active in two emerging markets without explicit board sign-off, which feels like a gap. The challenge is that bringing every transaction to the board would slow execution materially.

Third, the CFO has been hinting at retirement within 18-24 months, and we have no documented succession plan. The chair and I have discussed informally but haven't socialised any candidate names. This feels like the most material gap of the three, but also the most politically sensitive."""


async def _seed_chunk14_populated_phase_d_session(
    db, context_id: str, account_id: str,
) -> Dict[str, Any]:
    """Mint ONE fully-populated Phase D session per context.

    Schema mirrors what `routers/solva_phase_d.py::_run_layer_3` produces
    on the natural completion path:
      - `status = "completed"`, `layer_state = "done"`
      - `layer_1.answers` carries 3 answer records (questions_count=3)
      - `layer_2.answers` carries 3 answer records (questions_count=3)
      - `layer_3.rendered_synthesis` carries the markdown-light prose
      - `layer_4.answers` carries 3 reflection answers
      - `completed_at` populated

    Idempotency: `chunk14_populated_seed_marker="v1"`.
    """
    existing = await db.solva_phase_d_sessions.find_one(
        {"context_id": context_id, "chunk14_populated_seed_marker": "v1"},
        {"_id": 0, "session_id": 1},
    )
    if existing:
        return {
            "context_id": context_id, "session_id": existing["session_id"],
            "minted": False, "reason": "already_seeded",
        }
    sid = f"sol-c14p-{uuid.uuid4().hex[:24]}"
    now = _now()

    def _ans(text: str, idx: int) -> Dict[str, Any]:
        return {
            "id": f"ans-{uuid.uuid4().hex[:14]}",
            "text": text,
            "submitted_at": _iso(now),
            # `submitted_index` mirrors the natural-flow shape but is
            # optional — included for forensic traceability.
            "_seed_index": idx,
        }

    layer_1_answers = [
        _ans("The audit committee already flagged the staleness of the capital allocation framework in the Q1 minutes — that gives us cover to act now without it looking like a one-off.", 1),
        _ans("Management has been operating under an implicit risk appetite that isn't documented anywhere. The Q2 emerging-market deal went through without board sign-off, which the chair has privately questioned.", 2),
        _ans("The CFO succession gap is partly because we've avoided the topic, and partly because the obvious internal candidate (Group FC) has only been in the role 14 months. Bringing it forward forces us to either commit or look elsewhere.", 3),
    ]
    layer_2_answers = [
        _ans("If we leave the capital framework unchanged through FY26 and a material acquisition emerges, we'd be relying on the old thresholds — which would either be ignored or trigger an emergency rewrite, both bad governance signals.", 1),
        _ans("On the risk charter, the cleanest fix is to add an emerging-market schedule (specific country thresholds + scale caps) rather than rewrite the whole document. That's defensible in front of the regulator.", 2),
        _ans("For CFO succession, the politically safest path is to commission an external search in parallel with developing the internal candidate — gives optionality and signals due process to the audit committee.", 3),
    ]
    layer_4_answers = [
        _ans("Yes, mildly — I'd hoped one of these would turn out to be a non-issue, but on reflection all three are real. The CFO one was the one I'd been most reluctant to confront.", 1),
        _ans("I'd be wrong about the capital framework if a refresh now would actually introduce more rigidity than the current vague version. Worth pressure-testing with the FD.", 2),
        _ans("If I ignore the diagnosis: six months from now we're either mid-acquisition with the wrong framework, mid-CFO-departure with no plan, or both. Neither is acceptable.", 3),
    ]

    # Layer 2 candidate set + triangulation + tensions — minimal but
    # realistic enough that the session looks "done" from any read path.
    layer_2_obj = {
        "answers": layer_2_answers,
        "questions_count": 3,
        "refined_candidates": [
            {"label": "Refresh capital allocation framework", "rationale": "Audit committee already flagged."},
            {"label": "Add emerging-market schedule to risk charter", "rationale": "Closes the implicit-appetite gap."},
            {"label": "Commission parallel CFO search + internal development", "rationale": "Optionality + due-process signal."},
        ],
        "triangulation_result": {
            "overall_consistency": 0.82,
            "divergences": [],
            "extracted_claims": [
                "Capital allocation thresholds last refreshed in 2024.",
                "Risk charter lacks emerging-market schedule.",
                "No documented CFO succession plan.",
            ],
        },
        "detected_tensions": [
            "Execution speed vs board oversight on emerging-market deals.",
            "Internal development vs external search for CFO succession.",
        ],
        "tension_activation": None,
    }

    await db.solva_phase_d_sessions.insert_one({
        "session_id": sid,
        "user_id": account_id, "account_id": account_id, "context_id": context_id,
        "sub_module": "seek_clarity",
        "status": "completed",
        "layer_state": "done",
        "initial_framing": _CHUNK_14_FRAMING_PROSE,
        "title": "QA Chunk 14 — populated prose fixture",
        "created_at": now, "updated_at": now,
        # `completed_at` populated so the classifier (Chunk 13) routes
        # this to the COMPLETE bucket and the read-only banner fires.
        "completed_at": now,
        "layer_0": {
            "situation_class": "board_governance",
            "situation_class_confidence": 0.85,
            "verdict": "sufficient",
            "dimensions": [],
            "routing_decision": {},
            "carry_forward_caveats": [],
        },
        "layer_1": {
            "answers": layer_1_answers,
            "questions_count": 3,
            "candidate_set": [
                {"label": "Refresh capital allocation framework"},
                {"label": "Update risk charter for emerging markets"},
                {"label": "Document CFO succession plan"},
            ],
        },
        "layer_2": layer_2_obj,
        "layer_3": {
            "scenarios": [],
            "sensitivity_drivers": [],
            "surfaced_tensions": layer_2_obj["detected_tensions"],
            "evidence_trace": [],
            "primary_diagnosis_prose": _CHUNK_14_SYNTHESIS_PROSE,
            "refusal_flag": False,
            "rendered_synthesis": _CHUNK_14_SYNTHESIS_PROSE,
        },
        "layer_4": {
            "answers": layer_4_answers,
            "questions_count": 3,
        },
        "synisense_audit_ids": [],
        "orchestration_audit_log": [],
        "source_handoff": None,
        "seed_attached_references": [],
        "schema_version": 3,
        # Identifiability markers.
        "seed_origin": "chunk_14_populated",
        "chunk14_populated_seed_marker": "v1",
    })
    return {
        "context_id": context_id, "session_id": sid,
        "minted": True,
    }


async def main():
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = cli[os.environ["DB_NAME"]]

    bram = await db.accounts.find_one({"email": BRAMUEL_EMAIL}, {"_id": 0, "id": 1})
    if not bram:
        print(f"[seed-chunk8] {BRAMUEL_EMAIL} not found — nothing to seed.")
        return
    bid = bram["id"]
    contexts = await db.contexts.find(
        {"owner_account_id": bid}, {"_id": 0, "id": 1, "name": 1},
    ).to_list(50)

    enriched: List[Dict[str, Any]] = []
    minted_drafts: List[Dict[str, Any]] = []
    cycle_seeds: List[Dict[str, Any]] = []
    pii_chats: List[Dict[str, Any]] = []
    pulse_signals: List[Dict[str, Any]] = []
    monitor_seeds: List[Dict[str, Any]] = []
    strategic_seeds: List[Dict[str, Any]] = []
    no_data_strategic_seeds: List[Dict[str, Any]] = []
    populated_phase_d_seeds: List[Dict[str, Any]] = []

    for c in contexts:
        cid = c["id"]
        docs = await db.documents.find(
            {"context_id": cid},
            {"_id": 0, "id": 1, "name": 1},
        ).limit(5).to_list(5)
        doc_ids = [d["id"] for d in docs]
        doc_names = [d.get("name") or d["id"] for d in docs]

        # Pass A: enrich existing exports.
        rows = await db.work_studio_exports.find(
            {"context_id": cid}, {"_id": 0},
        ).to_list(200)
        for r in rows:
            if not doc_ids:
                continue  # can't enrich without source docs in the ctx
            res = await _enrich_existing_export(db, r, doc_ids, doc_names)
            if not res.get("skipped"):
                enriched.append(res)

        # Pass B: mint one Draft committee_pack per ctx that has ≥1 doc.
        if doc_ids:
            res = await _seed_draft_committee_pack(db, cid, bid, doc_ids, doc_names)
            if res.get("minted"):
                minted_drafts.append(res)

        # Pass C (Chunk 9): cycle / agenda / team-member seed.
        if doc_ids:
            res = await _seed_chunk9_cycle_fixture(db, cid, bid, doc_ids)
            if res.get("minted"):
                cycle_seeds.append(res)

        # Pass D (Chunk 9.5 fix-pass): PII-laden chat so Trust Panel
        # metrics become observable from the UI for tester verification.
        res = await _seed_chunk95_pii_chat_fixture(db, cid, bid)
        if res.get("minted"):
            pii_chats.append(res)

        # Pass E (Chunk 10): Pulse signal with comments + citations +
        # multi-paragraph reasoning, so render-smoke step 12 can
        # hard-assert QA-022/024/026/027 visuals.
        res = await _seed_chunk10_pulse_signal_fixture(db, cid, bid)
        if res.get("minted"):
            pulse_signals.append(res)

        # Pass F (Chunk 11): Achieved-state objective so render-smoke
        # step 13 can hard-assert the new Achieved tab + count badge.
        res = await _seed_chunk11_monitor_fixture(db, cid, bid)
        if res.get("minted"):
            monitor_seeds.append(res)

        # Pass G (Chunk 12): two strategic goals — one with associated
        # evidence (drives Update flow success), one without (drives
        # no-data short-circuit).
        res = await _seed_chunk12_strategic_goal_fixture(db, cid, bid)
        if res.get("minted"):
            strategic_seeds.append(res)

        # Pass H (Chunk 12 fix-pass 2026-05-21, Gap 1): explicit
        # no-data goal fixture with `seed_origin="chunk_12_no_data"`
        # marker + no linked documents. Lets tester walk the no-data
        # branch end-to-end via the live UI without grepping for the
        # incidental Pass G `gid_b` row.
        res = await _seed_chunk12_no_data_strategic_goal_fixture(db, cid, bid)
        if res.get("minted"):
            no_data_strategic_seeds.append(res)

        # Pass I (Chunk 14 fix-pass 2026-05-21, Gap 1): fully-populated
        # Phase D session with markdown-light synthesis prose so
        # tester + render-smoke step 16 can verify SV-06 (rich text
        # rendering) and SV-07 (60vh output panel sizing) end-to-end.
        # Status=completed → Chunk 13 classifier routes to COMPLETE
        # bucket → read-only banner fires → ProseBlock renders.
        res = await _seed_chunk14_populated_phase_d_session(db, cid, bid)
        if res.get("minted"):
            populated_phase_d_seeds.append(res)

    # Write a seed-log marker for visibility / forensics.
    await db.chunk8_seed_log.insert_one({
        "run_id": uuid.uuid4().hex,
        "applied_at": _iso(_now()),
        "actor": "scripts.seed_chunks",
        "enriched_count": len(enriched),
        "minted_count": len(minted_drafts),
        "cycle_seed_count": len(cycle_seeds),
        "pii_chat_count": len(pii_chats),
        "pulse_signal_count": len(pulse_signals),
        "enriched_sample": enriched[:5],
        "minted_sample": minted_drafts[:5],
        "cycle_seed_sample": cycle_seeds[:5],
        "pii_chat_sample": pii_chats[:5],
        "pulse_signal_sample": pulse_signals[:5],
    })

    print(f"[seed-chunks] enriched {len(enriched)} existing exports across "
          f"{len(contexts)} contexts; minted {len(minted_drafts)} fresh draft "
          f"committee packs; seeded {len(cycle_seeds)} cycle/agenda fixtures; "
          f"seeded {len(pii_chats)} PII chats (Sx2 verification); seeded "
          f"{len(pulse_signals)} Pulse signals (Chunk 10).")
    print("[seed-chunks] Sample artefact IDs for tester to target:")
    for r in (minted_drafts[:3] + enriched[:3]):
        print(f"   - ctx={r['context_id']} aid={r['id']}")
    if cycle_seeds:
        print("[seed-chunks] Sample cycle/agenda fixtures (Chunk 9):")
        for cs in cycle_seeds[:3]:
            print(f"   - ctx={cs['context_id']} cycle={cs['cycle_id']} "
                  f"agenda_item={cs.get('agenda_item_id')} "
                  f"member={cs.get('team_member_id')}")
    if pii_chats:
        print("[seed-chunks] Sample PII chats (Chunk 9.5 Sx2 verification):")
        for pc in pii_chats[:3]:
            print(f"   - ctx={pc['context_id']} chat={pc['chat_id']} "
                  f"spans={pc['spans_seeded']}")
    if pulse_signals:
        print("[seed-chunks] Sample Pulse signals (Chunk 10 -022/-024/-026/-027):")
        for ps in pulse_signals[:3]:
            print(f"   - ctx={ps['context_id']} signal={ps['signal_id']} "
                  f"comment={ps.get('comment_id')}")
    if monitor_seeds:
        print("[seed-chunks] Sample Achieved objectives (Chunk 11 -045):")
        for ms in monitor_seeds[:3]:
            print(f"   - ctx={ms['context_id']} obj={ms['objective_id']}")
    if strategic_seeds:
        print("[seed-chunks] Sample strategic goals (Chunk 12 -049):")
        for ss in strategic_seeds[:3]:
            print(f"   - ctx={ss['context_id']} with-evidence={ss['goal_with_evidence_id']} no-data={ss['goal_without_evidence_id']}")
    if no_data_strategic_seeds:
        print("[seed-chunks] Sample no-data fixtures (Chunk 12 fix-pass Pass H):")
        for ns in no_data_strategic_seeds[:5]:
            print(f"   - ctx={ns['context_id']} goal={ns['goal_id']}")
    if populated_phase_d_seeds:
        print("[seed-chunks] Sample populated Phase D sessions (Chunk 14 fix-pass Pass I):")
        for ps in populated_phase_d_seeds[:5]:
            print(f"   - ctx={ps['context_id']} sid={ps['session_id']}")


if __name__ == "__main__":
    asyncio.run(main())
