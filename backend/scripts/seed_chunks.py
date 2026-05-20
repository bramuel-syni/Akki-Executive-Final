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


if __name__ == "__main__":
    asyncio.run(main())
