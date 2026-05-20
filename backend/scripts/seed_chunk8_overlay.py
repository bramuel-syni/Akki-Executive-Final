"""Chunk 8 — Document Overlay seed enrichment + Draft sample.

Idempotent. Run via:

    cd /app/backend && python scripts/seed_chunk8_overlay.py

Two-pass:
  Pass A — enrich every existing `work_studio_exports` row owned by
           bramuel@syni.ai that's missing chunk-8 fields. Adds a
           realistic `intelligence_report`, attaches up to 3
           context documents as `source_document_ids`, and (only
           for non-legacy committed rows that already have a
           rendered binary) leaves `legacy=True` if the row had no
           structured_content captured at compile-time.
  Pass B — mint one fresh Draft committee_pack in the first context
           with ≥1 source document so the full editable round-trip
           is exercisable.

Marker collection: `chunk8_seed_log` — captures `{run_id, scope,
artefact_ids, applied_at}` to make re-runs visible without breaking
idempotency.
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

    # Write a seed-log marker for visibility / forensics.
    await db.chunk8_seed_log.insert_one({
        "run_id": uuid.uuid4().hex,
        "applied_at": _iso(_now()),
        "actor": "scripts.seed_chunk8_overlay",
        "enriched_count": len(enriched),
        "minted_count": len(minted_drafts),
        "enriched_sample": enriched[:5],
        "minted_sample": minted_drafts[:5],
    })

    print(f"[seed-chunk8] enriched {len(enriched)} existing exports across "
          f"{len(contexts)} contexts; minted {len(minted_drafts)} fresh draft "
          f"committee packs.")
    print("[seed-chunk8] Sample artefact IDs for tester to target:")
    for r in (minted_drafts[:3] + enriched[:5]):
        print(f"   - ctx={r['context_id']} aid={r['id']}")


if __name__ == "__main__":
    asyncio.run(main())
