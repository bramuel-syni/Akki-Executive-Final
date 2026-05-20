"""Monitor — "Update goal" status assessment endpoint (Phase F, 2026-05-16).

User clicks "Update goal" on a Monitor objective/project card. Akki:
  1. Queries the Synisense Engine for relevant signals (anomaly_flag,
     compliance_trigger, operational_health) for this tenant/context.
  2. Pulls the 5 most recent documents in the same context.
  3. Calls Shield with purpose `monitor.objective.status_assessment`
     (or `monitor.project.status_assessment`) passing the structured
     signals + doc summaries.
  4. Persists the new status, rationale, supporting signal/doc IDs,
     and the audit_id on the objective/project record.
  5. Returns the assessment payload + audit_id for the UI to render.

The status is NOT manually overridable (locked PO default) — the
endpoint always assigns a data-driven status. The supporting
rationale is always visible to the user.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from core import db, iso as _iso, now as _now, require_context_membership
from services.synisense.engine.signal_seeder import SIGNAL_COLLECTION
from services.synisense.shield.client import invoke as shield_invoke

log = logging.getLogger("monitor.status_assessment")

router = APIRouter(prefix="/api")

_KIND = ("objective", "project")
# QA-2026-05-16-047 (2026-05-18) — extended status vocabulary so the
# Akki-driven assessment can return Not Started (no relevant data),
# Achieved, plus the existing on_track / at_risk / off_track. Manual
# creates now default to Not Started (red is no longer the silent
# default — see the create modal frontend change).
_RAG = ("red", "amber", "green", "not_started", "achieved")
_STATUS_LABELS = {
    "green": "on_track",
    "amber": "at_risk",
    "red": "off_track",
    "not_started": "not_started",
    "achieved": "achieved",
}
_STATUS_REVERSE = {v: k for k, v in _STATUS_LABELS.items()}


def _coll(kind: str):
    if kind == "objective":
        return db.objectives
    if kind == "project":
        return db.projects
    raise HTTPException(status_code=400, detail="Unknown kind.")


class StatusAssessmentBody(BaseModel):
    model_config = ConfigDict(extra="ignore")
    # No body fields needed — the assessment is fully derived from
    # engine signals + recent documents. We still accept an optional
    # `note` so future UX could let the user pass a hint.
    note: Optional[str] = None


async def _gather_engine_signals(
    tenant_id: str, context_id: str,
) -> List[Dict[str, Any]]:
    """Pull the most relevant signals for this status assessment.

    Filters on tenant_id; picks signals scoped to this context_id OR
    tenant-wide signals (context_id None). Returns at most 12.
    """
    cursor = db[SIGNAL_COLLECTION].find(
        {
            "tenant_id": tenant_id,
            "signal_type": {"$in": [
                "anomaly_flag", "compliance_trigger", "operational_health",
                "churn_risk",
            ]},
            "$or": [{"context_id": context_id}, {"context_id": None}],
        },
        {"_id": 0},
    ).sort([("created_at", -1)]).limit(12)
    return [s async for s in cursor]


async def _gather_recent_docs(
    context_id: str, account_id: str,
) -> List[Dict[str, Any]]:
    cursor = db.documents.find(
        {"context_id": context_id, "account_id": account_id},
        {"_id": 0, "id": 1, "title": 1, "summary": 1, "created_at": 1},
    ).sort([("created_at", -1)]).limit(5)
    return [d async for d in cursor]


def _format_assessment_prompt(
    *, item: Dict[str, Any], item_kind: str,
    signals: List[Dict[str, Any]], docs: List[Dict[str, Any]],
) -> str:
    """Compose the deterministic, structured prompt sent to Shield.

    The prompt is INTENTIONALLY constrained: ask for a single JSON
    object with `status`, `rationale`, `supporting_signal_ids`,
    `supporting_doc_ids`. The LLM is constrained, not free-roaming.
    """
    sig_lines = []
    for s in signals[:10]:
        payload = s.get("payload") or {}
        sig_lines.append(
            f"- signal_id={s.get('signal_id')} "
            f"type={s.get('signal_type')} "
            f"category={s.get('signal_category')} "
            f"confidence={s.get('confidence', 0):.2f} "
            f"payload={json.dumps(payload, default=str)[:240]}"
        )
    doc_lines = []
    for d in docs:
        doc_lines.append(
            f"- doc_id={d.get('id')} title={(d.get('title') or '')[:80]!r} "
            f"summary={(d.get('summary') or '')[:200]!r}"
        )

    return (
        f"You are Akki, assessing the status of a Monitor {item_kind}.\n"
        f"{item_kind.capitalize()}: {item.get('title', '')!r}\n"
        f"Current RAG: {item.get('rag_status', '—')}\n"
        f"Owner role: {item.get('owner_role') or '—'}\n"
        f"\n"
        f"Recent engine signals (most recent first):\n"
        + ("\n".join(sig_lines) if sig_lines else "(none)") + "\n"
        "\n"
        "Recent documents (most recent first):\n"
        + ("\n".join(doc_lines) if doc_lines else "(none)") + "\n"
        "\n"
        "Assess the status. Return ONLY one JSON object with these "
        "exact keys:\n"
        '{"status": "not_started" | "on_track" | "at_risk" | "off_track" | "achieved", '
        '"confidence": <float 0..1>, '
        '"rationale": "<2-3 sentences>", '
        '"supporting_signal_ids": [<signal_id>, ...], '
        '"supporting_doc_ids": [<doc_id>, ...]}\n'
        "Use 'not_started' ONLY when neither signals nor documents "
        "contain ANY material relevant to this item — in which case "
        "supporting_signal_ids and supporting_doc_ids must be empty "
        "and the rationale must say so plainly. Use 'achieved' when "
        "the evidence clearly shows the target/outcome has been "
        "delivered. Do not add commentary outside the JSON."
    )


_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse_assessment_response(
    response_text: str,
    *, signal_ids: List[str], doc_ids: List[str],
) -> Dict[str, Any]:
    """Parse the LLM's JSON. Defends against extra prose / mock-mode
    echo by extracting the first {...} block. Falls back to a safe
    deterministic shape if parsing fails so the endpoint never 500s
    on a flaky LLM response."""
    match = _JSON_RE.search(response_text or "")
    if match:
        try:
            parsed = json.loads(match.group(0))
            status = parsed.get("status")
            if status not in ("not_started", "on_track", "at_risk", "off_track", "achieved"):
                raise ValueError(f"bad status: {status}")
            return {
                "status": status,
                "confidence": float(parsed.get("confidence", 0.6)),
                "rationale": str(parsed.get("rationale", ""))[:1000] or
                             "Status assessed from engine signals + recent documents.",
                "supporting_signal_ids": [
                    sid for sid in (parsed.get("supporting_signal_ids") or [])
                    if sid in signal_ids
                ],
                "supporting_doc_ids": [
                    did for did in (parsed.get("supporting_doc_ids") or [])
                    if did in doc_ids
                ],
            }
        except (ValueError, TypeError) as exc:
            log.info(
                "monitor.status_assessment: LLM JSON parse failed (%s), "
                "falling back to heuristic", type(exc).__name__,
            )
    # Heuristic fallback: scan for the phrase in the response.
    lowered = (response_text or "").lower()
    if "not_started" in lowered or "not started" in lowered:
        status = "not_started"
    elif "achieved" in lowered:
        status = "achieved"
    elif "off_track" in lowered or "off track" in lowered:
        status = "off_track"
    elif "at_risk" in lowered or "at risk" in lowered:
        status = "at_risk"
    else:
        status = "on_track"
    return {
        "status": status,
        "confidence": 0.55,
        "rationale": (
            "Heuristic assessment from response prose (LLM did not return "
            "structured JSON). Engine signals + recent documents informed "
            "this read."
        ),
        "supporting_signal_ids": signal_ids[:3],
        "supporting_doc_ids": doc_ids[:3],
    }


@router.post("/contexts/{context_id}/monitor/{kind}/{rid}/update-status")
async def update_status_assessment(
    context_id: str,
    kind: str,
    rid: str,
    body: StatusAssessmentBody,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Akki-driven status reassessment (non-overridable)."""
    if kind not in _KIND:
        raise HTTPException(status_code=400, detail="Unknown kind.")
    account = ctx["account"]
    coll = _coll(kind)
    item = await coll.find_one(
        {"id": rid, "context_id": context_id, "deleted_at": {"$exists": False}},
        {"_id": 0},
    )
    if not item:
        raise HTTPException(status_code=404, detail="Not found.")

    signals = await _gather_engine_signals(
        tenant_id=account["id"], context_id=context_id,
    )
    docs = await _gather_recent_docs(
        context_id=context_id, account_id=account["id"],
    )

    # QA-2026-05-16-047 (2026-05-18) — "If Akki finds no relevant
    # material, it does not assign a status." Short-circuit here so
    # we don't burn a Shield call for a no-data assessment. The
    # frontend renders the no-data message + Document Journal link.
    if not signals and not docs:
        no_data_payload = {
            "id": rid,
            "kind": kind,
            "rag_status": item.get("rag_status") or "not_started",
            "status": "no_data",
            "no_data": True,
            "message": (
                f"No relevant documents or data found for this {kind}. "
                f"Please upload a document containing information about "
                f"this {kind} so Akki can assess its status."
            ),
            "assessment": None,
        }
        return no_data_payload

    purpose = f"monitor.{kind}.status_assessment"
    prompt = _format_assessment_prompt(
        item=item, item_kind=kind, signals=signals, docs=docs,
    )

    shield_result = await shield_invoke(
        purpose=purpose,
        content=prompt,
        tenant_id=account["id"],
        consumer_id="monitor",
        user_id=account["id"],
        model_preference="analytical",
        internal_caller=True,
    )

    assessment = _parse_assessment_response(
        shield_result["response"],
        signal_ids=[s["signal_id"] for s in signals],
        doc_ids=[d["id"] for d in docs],
    )

    # Map status → rag_status.
    new_rag = _STATUS_REVERSE.get(assessment["status"]) or item.get("rag_status") or "amber"
    last_akki_assessment = {
        "status": assessment["status"],
        "rag_status": new_rag,
        "confidence": round(assessment["confidence"], 3),
        "rationale": assessment["rationale"],
        "supporting_signal_ids": assessment["supporting_signal_ids"],
        "supporting_doc_ids": assessment["supporting_doc_ids"],
        "audit_id": shield_result["audit_id"],
        "assessed_at": _iso(_now()),
    }

    await coll.update_one(
        {"id": rid, "context_id": context_id},
        {"$set": {
            "rag_status": new_rag,
            "last_akki_assessment": last_akki_assessment,
            "updated_at": _iso(_now()),
        }},
    )

    return {
        "id": rid,
        "kind": kind,
        "rag_status": new_rag,
        "status": assessment["status"],
        "assessment": last_akki_assessment,
    }
