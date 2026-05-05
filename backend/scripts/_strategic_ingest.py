"""Phase L.2 / L.3 — shared strategic-doc ingestion helper.

Used by:
  • backend/scripts/seed_admin_strategic_data.py
  • backend/scripts/seed_julius_opio.py (strategic mirror section)

Behaviour:
  1. Ensure one demo context per pack org_type (naming
     "<Org Display Name> · Demo" when the caller does not pass an
     explicit context mapping).
  2. For each strategic doc, insert a real row into the `documents`
     collection if not already present (idempotent on
     (context_id, title, source="strategic_pack_v1")).
  3. Run Synisense pipeline (surface="ingest") over the body and
     persist `body_redacted` + `synisense_version`.
  4. Score sensitivity via `studio_sensitivity.score_sensitivity` and
     persist `sensitivity_score` / `sensitivity_band` / reasons.
  5. Return a per-run summary with created / skipped / failed counts
     plus a list of spans showing Synisense did run (for the L.4
     "token replacement sample" deliverable).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from core import db, iso as _iso, now as _now
from services.synisense import pipeline as synisense_pipeline
from studio_sensitivity import score_sensitivity
from sandbox_v2_strategic import (
    STRATEGIC_DOCUMENTS, STRATEGIC_ORG_DISPLAY_NAMES,
)

logger = logging.getLogger("akki.seed.strategic")

STRATEGIC_SOURCE_TAG = "strategic_pack_v1"
DEFAULT_CONTEXT_TYPE = "executive_personal"
SYNISENSE_SURFACE = "ingest"

# Map strategic `kind` → the tactical `doc_type` vocabulary used
# elsewhere in the product (Reading View, Signals routing, etc).
_DOC_TYPE_BY_KIND: Dict[str, str] = {
    "strategic_plan":    "strategy_document",
    "framework":         "strategy_document",
    "strategy":          "strategy_document",
    "theory_of_change":  "policy_document",
    "investment_thesis": "strategy_document",
    "political_economy": "policy_document",
}


async def _ensure_demo_context(
    *, owner_account_id: str, org_type: str,
    name_override: Optional[str] = None,
) -> Tuple[Dict[str, Any], str]:
    """Return (context_doc, action) where action ∈ {created, exists}.

    `name_override` lets L.3 pass Julius's own context names ("Julius
    Opio — Sponsored NED Seat") rather than the default
    "<Organisation> · Demo".

    Always reasserts the (account → context) membership so the owner
    can read the context through `require_context_membership`. Without
    this, contexts created by the L.2 admin seed would not surface on
    the login payload (which is keyed off memberships, not ownership)
    nor be readable through `/api/contexts/{cid}/documents`.
    """
    target_name = name_override or f"{STRATEGIC_ORG_DISPLAY_NAMES[org_type]} · Demo"

    existing = await db.contexts.find_one(
        {"owner_account_id": owner_account_id, "name": target_name},
        {"_id": 0},
    )
    if existing:
        await _ensure_membership(owner_account_id, existing["id"])
        return existing, "exists"

    ctx_id = str(uuid.uuid4())
    now = _iso(_now())
    ctx = {
        "id": ctx_id,
        "name": target_name,
        "type": DEFAULT_CONTEXT_TYPE,
        "industry": _industry_for(org_type),
        "jurisdiction": "Kenya",
        "sector": STRATEGIC_ORG_DISPLAY_NAMES[org_type],
        "sponsoring_org_id": None,
        "owner_account_id": owner_account_id,
        "status": "active",
        "progress_state": {
            "onboarding_step": 7,
            "onboarding_completed": True,
            "context_object_version": 1,
        },
        "committees": _DEFAULT_COMMITTEES,
        "created_at": now,
    }
    await db.contexts.insert_one(ctx)
    ctx.pop("_id", None)
    await _ensure_membership(owner_account_id, ctx_id)
    return ctx, "created"


async def _ensure_membership(account_id: str, context_id: str) -> None:
    """Idempotent owner+admin membership for the context."""
    existing = await db.memberships.find_one(
        {"account_id": account_id, "context_id": context_id},
        {"_id": 0, "id": 1},
    )
    if existing:
        return
    await db.memberships.insert_one({
        "id": str(uuid.uuid4()),
        "account_id": account_id,
        "context_id": context_id,
        "role": "executive",
        "sub_role": "admin",
        "provisioning": "personal",
        "data_ownership": "account",
        "status": "active",
        "created_at": _iso(_now()),
    })


def _industry_for(org_type: str) -> str:
    return {
        "bank":        "Banking",
        "healthcare":  "Healthcare",
        "logistics":   "Logistics",
        "technology":  "Technology",
        "government":  "Public Sector",
    }.get(org_type, "General")


_DEFAULT_COMMITTEES: List[Dict[str, Any]] = [
    {"id": "audit",        "name": "Audit Committee",        "your_role": "chair"},
    {"id": "risk",         "name": "Risk Committee",         "your_role": "member"},
    {"id": "nominations",  "name": "Nominations Committee",  "your_role": "member"},
    {"id": "remuneration", "name": "Remuneration Committee", "your_role": "member"},
    {"id": "esg",          "name": "ESG Committee",          "your_role": "member"},
    {"id": "strategy",     "name": "Strategy Committee",     "your_role": "member"},
]


async def _ingest_one_doc(
    *,
    account: Dict[str, Any],
    context: Dict[str, Any],
    strategic_doc: Dict[str, Any],
) -> Dict[str, Any]:
    """Insert the strategic doc as a `documents` row and run the
    Synisense + sensitivity passes. Idempotent on
    (context_id, title, source=STRATEGIC_SOURCE_TAG).
    """
    existing = await db.documents.find_one(
        {
            "context_id": context["id"],
            "name": strategic_doc["title"],
            "source": STRATEGIC_SOURCE_TAG,
        },
        {"_id": 0, "id": 1, "synisense_version": 1, "sensitivity_score": 1},
    )
    if existing:
        return {
            "action": "skipped",
            "doc_id": existing["id"],
            "title": strategic_doc["title"],
            "synisense_version": existing.get("synisense_version"),
            "sensitivity_score": existing.get("sensitivity_score"),
            "spans_sample": [],
        }

    doc_id = str(uuid.uuid4())
    now = _iso(_now())
    body = strategic_doc["body"]

    # ── Synisense run (surface=ingest). Hard-fail the doc if it errors;
    #    the pack must be ingested through the full pipeline per spec. ──
    synisense_out = await synisense_pipeline.run(
        body,
        context_id=context["id"],
        surface=SYNISENSE_SURFACE,
        mode="redact",
        account_id=account["id"],
    )

    # Build a human-legible sample of Synisense replacements. The
    # pipeline's public return is intentionally thin (spans without
    # match_text, to avoid leaking originals into the run record) — so
    # we reconstruct the sample by slicing the body at the detected
    # span offsets and diffing against `redacted_text`.
    _spans_sample: List[Dict[str, Any]] = []
    for sp in (synisense_out.get("spans") or [])[:3]:
        try:
            match = body[sp["start"]:sp["end"]]
        except Exception:  # noqa: BLE001
            match = ""
        _spans_sample.append({
            "entity_type": sp.get("entity_type"),
            "match_text": match,
            "replacement": None,  # the token form lives only in redacted_text
        })

    # ── Sensitivity score ───────────────────────────────────────────────
    sens = score_sensitivity({
        "extracted_text": body,
        "title": strategic_doc["title"],
    })

    # Deployment-level floor: strategic-pack documents are board-internal
    # by definition (every doc in the pack carries a 'Confidential' /
    # 'Restricted Distribution' / 'Highly Confidential' header). The
    # regex scorer does not match those disclosure labels directly, so
    # we lift the classification floor here rather than patching the
    # scorer. The Board's political-economy brief ("Restricted
    # Distribution") floors at `confidential`; everything else floors at
    # `internal`.
    _POLITICAL_KINDS = {"political_economy"}
    floor_band = (
        "confidential" if strategic_doc["kind"] in _POLITICAL_KINDS else "internal"
    )
    _BAND_RANK = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}
    _MIN_SCORE_FOR_BAND = {"public": 0, "internal": 25, "confidential": 50, "restricted": 75}
    cur_rank = _BAND_RANK.get(sens.get("classification", "public"), 0)
    if _BAND_RANK[floor_band] > cur_rank:
        sens["classification"] = floor_band
        sens["label"] = floor_band.capitalize()
        sens["score"] = max(sens.get("score", 0), _MIN_SCORE_FOR_BAND[floor_band])
        reasons = list(sens.get("reasons") or [])
        reasons.append(f"Floor: strategic-pack ({floor_band})")
        sens["reasons"] = reasons
        sens["strategic_pack_floor_applied"] = floor_band

    # ── Persist ─────────────────────────────────────────────────────────
    doc_row: Dict[str, Any] = {
        "id": doc_id,
        "context_id": context["id"],
        "name": strategic_doc["title"],
        "description": "",
        "original_filename": f"{strategic_doc['id']}.txt",
        "mime_type": "text/plain",
        "size_bytes": len(body.encode("utf-8")),
        "storage_key": None,  # corpus-sourced — no file on disk
        "extracted_text": body,
        "extracted_chars": len(body),
        "preview": strategic_doc.get("preview") or body[:200],
        "status": "ready",
        "doc_type": _DOC_TYPE_BY_KIND.get(strategic_doc["kind"], "strategy_document"),
        "doc_kind": strategic_doc["kind"],
        "data_trust": "trusted",
        "source": STRATEGIC_SOURCE_TAG,
        "strategic_pack_id": strategic_doc["id"],
        "uploaded_by": account["id"],
        "uploaded_by_email": account["email"],
        "mentioned_account_ids": [],
        "created_at": now,
        "updated_at": now,
        # Synisense artefacts
        "body_redacted": synisense_out.get("redacted_text"),
        "synisense_version": 1,
        "synisense_run_ts": now,
        "synisense_shield_map_id": synisense_out.get("shield_map_id"),
        # Sensitivity artefacts
        "sensitivity_score": sens.get("score"),
        "sensitivity_band": sens.get("classification"),
        "sensitivity_label": sens.get("label"),
        "sensitivity_reasons": sens.get("reasons"),
    }
    await db.documents.insert_one(doc_row)

    spans_sample = _spans_sample
    # If Synisense produced no spans (shouldn't happen for strategic
    # docs, but defensive), fall back to empty list.

    return {
        "action": "created",
        "doc_id": doc_id,
        "title": strategic_doc["title"],
        "synisense_version": 1,
        "synisense_span_count": len(synisense_out.get("spans") or []),
        "sensitivity_score": sens.get("score"),
        "sensitivity_band": sens.get("classification"),
        "spans_sample": spans_sample,
    }


async def ingest_strategic_documents(
    *,
    account: Dict[str, Any],
    context_name_by_org_type: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Ingest the full 14-doc pack into `account`. When
    `context_name_by_org_type` is provided, the caller-supplied context
    names are used (L.3 passes Julius's existing context names); when
    absent the default "<Organisation> · Demo" naming applies (L.2).
    """
    summary: Dict[str, Any] = {
        "account_id": account["id"],
        "account_email": account["email"],
        "contexts_created": 0,
        "contexts_existing": 0,
        "docs_created": 0,
        "docs_skipped": 0,
        "by_org_type": {},
        "sample_replacements": [],
    }

    for org_type, strategic_docs in STRATEGIC_DOCUMENTS.items():
        override = (context_name_by_org_type or {}).get(org_type)
        ctx, ctx_action = await _ensure_demo_context(
            owner_account_id=account["id"],
            org_type=org_type,
            name_override=override,
        )
        if ctx_action == "created":
            summary["contexts_created"] += 1
        else:
            summary["contexts_existing"] += 1

        org_summary = {
            "context_id": ctx["id"],
            "context_name": ctx["name"],
            "docs": [],
        }
        for sd in strategic_docs:
            result = await _ingest_one_doc(
                account=account, context=ctx, strategic_doc=sd,
            )
            if result["action"] == "created":
                summary["docs_created"] += 1
                # Capture one sample replacement per org_type for the
                # L.4 "Synisense ran" proof.
                if result["spans_sample"] and "sample_replacements" in summary:
                    if not any(s["org_type"] == org_type for s in summary["sample_replacements"]):
                        summary["sample_replacements"].append({
                            "org_type": org_type,
                            "doc_title": result["title"],
                            "span": result["spans_sample"][0],
                        })
            else:
                summary["docs_skipped"] += 1
            org_summary["docs"].append(result)
        summary["by_org_type"][org_type] = org_summary

    return summary
