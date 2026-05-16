"""Phase C — Akki Chat audit panel + archived-chats data layer.

This router lands two surfaces:

- `GET /api/chats/{chat_id}/audit-panel?message_id={mid}` — composes
  human-readable copy from `synisense_audit_log`, `synisense_trust_
  receipts`, and `chats.protective_layer_events` for the audit panel
  expander on each assistant message. ALL strings rendered here are
  executive-readable (no enum values, no field names) so the panel
  can show them verbatim.

- `GET /api/chats/{chat_id}/audit-panel/aggregate` — per-conversation
  rolling aggregates (count of LLM calls, total entities shielded,
  mean exposure_reduction, mean dilution).

- `GET /api/chats/archived` — paginated list of archived chats.
- `DELETE /api/chats/{chat_id}/permanent` — hard delete with
  confirmation flag.

Strict `tenant_id == account_id` discipline. All routes require the
caller to own the chat.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from core import db, get_current_account


router = APIRouter(prefix="/api", tags=["chat-audit-panel"])


# ─────────────────────────────────────────────────────────────────────
# Translation tables — raw values → executive-friendly prose.
# ─────────────────────────────────────────────────────────────────────
_ENTITY_LABEL = {
    "PERSON":      "person name",
    "ORG":         "organisation name",
    "GPE":         "place name",
    "PRODUCT":     "product name",
    "NORP":        "demographic reference",
    "FAC":         "facility name",
    "EVENT":       "event name",
    "LAW":         "law / regulation reference",
    "MONEY":       "monetary figure",
    "EMAIL":       "email address",
    "PHONE_E164":  "phone number",
    "IBAN":        "bank account (IBAN)",
    "ACCOUNT_NUM": "account number",
    "DATE_ISO":    "date",
    "IP":          "IP address",
    "URL":         "web address",
    "SSN":         "national identifier",
}

_PROVIDER_PRETTY = {
    "anthropic":      "Anthropic",
    "openai":         "OpenAI",
    "gemini":         "Google Gemini",
    "anthropic:mock": "Anthropic (mock for test)",
    "gemini:mock":    "Google Gemini (mock for test)",
    "openai:mock":    "OpenAI (mock for test)",
}


# ─────────────────────────────────────────────────────────────────────
# Friendly model-name sanitiser — strips API-version date suffixes so
# the audit panel doesn't leak engineering-speak.
#
# Phase C fix bundle (2026-05-13). Each provider has its own date-stamp
# convention; we strip the date stamps and any inert version trailers
# (`-001`, `:mock`, etc.) while preserving the human-recognisable model
# tier (`sonnet-4-5`, `4o`, `2.5-flash`).
#
# The friendly-name map is also used by the Phase D Solva audit panel
# (per the PO's Phase D pre-fold instruction) — `solva.layer_*` purpose
# strings get a human label so the Solva session timeline reads as
# "Frame Audit" / "Triangulation" / etc. rather than enum text.
# ─────────────────────────────────────────────────────────────────────
import re as _re

_MODEL_DATE_SUFFIX = _re.compile(
    r"-\d{8}$"                # ISO-stamped: claude-sonnet-4-5-20250929 → claude-sonnet-4-5
    r"|-\d{4}-\d{2}-\d{2}$"   # dashed-ISO: gpt-4o-2024-08-06 → gpt-4o
    r"|-\d{3}$"               # 3-digit revision: gemini-2.5-flash-001 → gemini-2.5-flash
)


def _friendly_model_name(raw: str) -> str:
    """Strip API-version date suffixes and inert revision trailers from
    a model id so the audit panel reads naturally for an executive."""
    if not raw:
        return ""
    s = str(raw)
    # Mock-mode tag emitted by `llm_router.invoke` when EMERGENT_LLM_KEY
    # is absent — drop for the audit panel (user-visible).
    s = s.replace(":mock", "")
    # Strip date/revision suffix; loop once per pattern in case of stacked
    # `-001-20250929` style trailers.
    prev = None
    while prev != s:
        prev = s
        s = _MODEL_DATE_SUFFIX.sub("", s)
    return s


# ─────────────────────────────────────────────────────────────────────
# Purpose-string friendly labels.
#
# Phase C — chat consumer set today; Phase D Solva inherits the
# solva.* entries (PO-approved fold-in on 2026-05-13). The audit panel
# falls back to the raw purpose string when no friendly label is
# registered, so adding a new label is non-blocking.
# ─────────────────────────────────────────────────────────────────────
_PURPOSE_LABEL = {
    # Chat
    "chat.standard_response":            "Chat reply",
    "chat.session.summarise":            "Conversation summary",
    "chat.streaming.standard_response":  "Chat reply (streamed)",
    "chat.fm_a.hypothesis_detection":    "Hypothesis-check (Detector A)",
    "chat.fm_b.claim_extraction":        "Claim-grounding check (Detector B)",
    "chat.fm_c.consequence_classification": "Consequence check (Detector C)",
    "chat.refusal.compose":              "Refusal compose",
    "chat.thin_input.evidence_list":     "Evidence prompt (thin input)",
    "chat.tools.classify_turn":          "Turn classifier",
    "chat.deliverable.pass1_reasoning":  "Deliverable — Pass 1 reasoning",
    "chat.deliverable.pass2_render":     "Deliverable — Pass 2 render",

    # Solva (Phase D pre-fold per PO 2026-05-13)
    "solva.layer_0.frame_audit":                       "Frame Audit",
    "solva.layer_0.situation_classification":          "Situation Classification",
    "solva.layer_1.candidate_generation":              "Candidate Generation",
    "solva.layer_2.triangulation.claim_extraction":    "Triangulation — Claim Extraction",
    "solva.layer_2.triangulation.entailment_classification": "Triangulation — Entailment",
    "solva.layer_2.tension_detection":                 "Tension Detection",
    "solva.layer_3.scenario_narrative_generation":     "Scenario Narrative",
    "solva.layer_3.synthesis_rendering":               "Synthesis",
    "solva.refusal.compose":                           "Refusal compose",
    "solva.entry.frame_payload":                       "Entry framing",

    # Work Studio / Document Journal / Cycle / Monitor / Pulse
    "work_studio.brief.enhance":                       "Brief — enhance",
    "work_studio.brief.seed":                          "Brief — seed",
    "work_studio.deck.generate":                       "Deck generation",
    "work_studio.report.generate":                     "Report generation",
    "work_studio.minutes.enhance":                     "Minutes — enhance",
    "work_studio.compile.board_pack":                  "Board pack compile",
    "work_studio.sandbox.generate":                    "Sandbox seed",
    "document_journal.commentary.generate":            "Document commentary",
    "document_journal.meta.generate":                  "Document meta",
    "document_journal.summary.generate":               "Document summary",
    "document_journal.evolution_diff":                 "Evolution diff",
    "document_journal.signals.generate":               "Document signals",
    "cycle_manager.agenda.generate":                   "Cycle agenda",
    "cycle_manager.briefing.aggregate":                "Cycle briefing",
    "monitor.objective.status_assessment":             "Objective status",
    "monitor.project.status_assessment":               "Project status",
    "monitor.strategic_goal.update":                   "Strategic goal update",
    "pulse.signal.commentary":                         "Pulse signal commentary",
    "akki.gateway.standard":                           "Gateway call",
    "health.ping":                                     "Health probe",
    # Phase E Sub-task B (2026-05-16) — guardrail labels.
    "solva.guardrails.jailbreak_detection":            "Guardrail — jailbreak detection",
    "solva.guardrails.therapy_detection":              "Guardrail — therapy detection",
    "solva.guardrails.coaching_detection":             "Guardrail — coaching detection",
}


def _friendly_purpose(raw: str) -> str:
    if not raw:
        return ""
    return _PURPOSE_LABEL.get(raw, raw)


def _plural(n: int, singular: str, plural: Optional[str] = None) -> str:
    plural = plural or (singular + "s")
    if n == 1:
        return f"1 {singular}"
    return f"{n} {plural}"


def _summary_to_prose(summary: Dict[str, int]) -> str:
    """`{"PERSON": 3, "MONEY": 2, "EMAIL": 1}` →
    "3 person names, 2 monetary figures, and 1 email address"."""
    if not summary:
        return "no sensitive identifiers"
    parts: List[str] = []
    for k, n in sorted(summary.items(), key=lambda kv: -kv[1]):
        if not n:
            continue
        label = _ENTITY_LABEL.get(k, k.lower().replace("_", " "))
        parts.append(_plural(n, label))
    if not parts:
        return "no sensitive identifiers"
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return parts[0] + " and " + parts[1]
    return ", ".join(parts[:-1]) + ", and " + parts[-1]


def _provider_pretty(provider: str, model: str) -> str:
    base = _PROVIDER_PRETTY.get(provider, provider.capitalize() if provider else "an LLM")
    friendly = _friendly_model_name(model)
    if friendly:
        return f"{base}'s {friendly}"
    return base


# ─────────────────────────────────────────────────────────────────────
# Shared composer — used by BOTH the audit-panel endpoint (UI) and the
# chat-privacy-report PDF (downloadable verifiable artefact).
#
# Returns the natural-language prose pieces + structured references.
# Callers choose which subset to expose:
#   - UI panel:  hides signature + payload_hash (security-by-design).
#   - PDF:       includes signature + payload_hash for tenant
#                self-verification of the HMAC chain.
# ─────────────────────────────────────────────────────────────────────
def compose_audit_entry_prose(
    *,
    audit_row: Dict[str, Any],
    receipt_row: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Pure prose composer for one audit row.

    All callers MUST go through this function so the audit-panel UI
    and the privacy-report PDF stay in lockstep when copy changes.
    """
    summary = audit_row.get("de_id_summary") or {}
    provider = audit_row.get("llm_provider") or ""
    model = audit_row.get("llm_model") or ""
    purpose = audit_row.get("purpose") or ""
    er = audit_row.get("exposure_reduction_score")
    dl = audit_row.get("dilution_score")

    shield_line = (
        f"Synisense shielded {_summary_to_prose(summary)} before any LLM saw your message."
        if summary else
        "No sensitive identifiers were detected in this turn."
    )
    provider_line = (
        f"The redacted content was read by {_provider_pretty(provider, model)}."
        if provider else
        "The redacted content was processed locally (mock mode — no provider call)."
    )

    er_label = (
        "almost all sensitive content shielded" if (er or 0) >= 80 else
        "most sensitive content shielded" if (er or 0) >= 50 else
        "limited shielding (few entities in this turn)"
    )
    dl_label = (
        "most semantic content preserved" if (dl or 0) <= 30 else
        "moderate dilution" if (dl or 0) <= 60 else
        "high dilution"
    )
    er_str = f"{er}%" if isinstance(er, (int, float)) else "—"
    dl_str = f"{dl}%" if isinstance(dl, (int, float)) else "—"
    scores_line = (
        f"Exposure reduction: {er_str} ({er_label}). "
        f"Dilution: {dl_str} ({dl_label})."
    )
    purpose_label = _friendly_purpose(purpose) or "Chat reply"
    purpose_line = f"Purpose: {purpose_label}."

    narrative = " ".join([shield_line, provider_line, scores_line, purpose_line])

    receipt_row = receipt_row or {}
    references = {
        "audit_id":          audit_row.get("audit_id"),
        "consumer":          audit_row.get("consumer_id"),
        "purpose":           purpose,
        "purpose_label":     purpose_label,
        "timestamp":         audit_row.get("timestamp"),
        "trust_receipt_id":  receipt_row.get("receipt_id"),
        "trust_receipt_version": receipt_row.get("version"),
        # Verification fields — kept OUT of the UI audit panel
        # (security-by-design), surfaced ON the PDF so the tenant can
        # verify the HMAC chain themselves.
        "signature":         receipt_row.get("signature"),
        "payload_hash":      receipt_row.get("payload_hash"),
    }

    return {
        "narrative":         narrative,
        "shielding_prose":   shield_line,
        "provider_prose":    provider_line,
        "scores_prose":      scores_line,
        "purpose_prose":     purpose_line,
        "scores": {
            "exposure_reduction":       er,
            "dilution":                 dl,
            "exposure_reduction_label": er_label,
            "dilution_label":           dl_label,
        },
        "references": references,
    }


def compose_aggregate_footer(
    *,
    llm_call_count: int,
    message_count: int,
    avg_exposure_reduction: Optional[float],
    avg_dilution: Optional[float],
) -> str:
    """One-line conversation roll-up used in the PDF footer + the
    aggregate-strip UI."""
    head = (
        f"Across this conversation, Synisense governed "
        f"{_plural(llm_call_count, 'LLM call')} "
        f"across {_plural(message_count, 'message')}."
    )
    if avg_exposure_reduction is not None and avg_dilution is not None:
        head += (
            f" Average exposure reduction: {round(avg_exposure_reduction, 1)}%. "
            f"Average dilution: {round(avg_dilution, 1)}%."
        )
    return head


def _intervention_prose(event: Optional[Dict[str, Any]]) -> str:
    """Render the protective-layer event in executive language."""
    if not event:
        return ("Protective layer ran. No interventions fired — the "
                "assistant's reply is grounded in the materials in this session.")
    fired = event.get("detectors_fired") or []
    intv = event.get("intervention_type") or "none"
    text = event.get("intervention_text")
    if intv == "none" or not fired:
        return ("Protective layer ran. No interventions fired — the "
                "assistant's reply is grounded in the materials in this session.")
    if intv == "hypothesis_test":
        return ("Detector A fired — your question was a hypothesis with thin grounding. "
                "Akki proposed a framing question first so the answer would rest on something "
                "specific. " + (text or ""))
    if intv == "annotation":
        anchors = event.get("annotation_anchors") or []
        anchors_text = (
            "Annotated phrases: " + "; ".join(f"\"{a}\"" for a in anchors)
            if anchors else ""
        )
        return ("Detector B fired — Akki flagged one or more factual claims in the reply as "
                "general-practice references worth verifying against your data. " + anchors_text)
    if intv == "solva_handoff_offered":
        return ("Detector C fired — this question carries strategic consequence and the session "
                "evidence is thin. Akki offered a handoff to Solva for structured reasoning. "
                + (text or ""))
    if intv == "consequence_check":
        return "A consequence check was offered for this turn. " + (text or "")
    return text or "Protective layer ran."


# ─────────────────────────────────────────────────────────────────────
# Audit panel — single message.
# ─────────────────────────────────────────────────────────────────────
@router.get("/chats/{chat_id}/audit-panel")
async def get_audit_panel(
    chat_id: str,
    message_id: str = Query(..., description="The assistant message_id whose audit to render."),
    current: Dict[str, Any] = Depends(get_current_account),
):
    """Returns the natural-language audit panel data for one assistant
    message. Resolves the right Shield audit row by indexing into the
    chat session's `synisense_audit_ids` array using the assistant
    message's position in `chat_messages`."""
    chat = await db.chats.find_one(
        {"id": chat_id, "account_id": current["id"]},
        {"_id": 0, "synisense_audit_ids": 1, "protective_layer_events": 1},
    )
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found.")

    audit_ids: List[str] = chat.get("synisense_audit_ids") or []
    events: List[Dict[str, Any]] = chat.get("protective_layer_events") or []

    # Resolve the audit_id for this message by counting assistant
    # messages up to (and including) `message_id`. The N-th assistant
    # message corresponds to the N-th audit_id appended on chat send.
    assistant_msgs = await db.chat_messages.find(
        {"chat_id": chat_id, "account_id": current["id"], "role": "assistant"},
        {"_id": 0, "id": 1, "created_at": 1, "model_label": 1},
    ).sort("created_at", 1).to_list(length=500)
    pos = next((i for i, m in enumerate(assistant_msgs) if m.get("id") == message_id), None)
    if pos is None:
        raise HTTPException(status_code=404, detail="Message not found in this chat.")
    audit_id = audit_ids[pos] if pos < len(audit_ids) else None

    # Match the protective event by message_id.
    matching_event = next(
        (e for e in events if e.get("message_id") == message_id), None,
    )

    # Audit row + trust receipt.
    audit_row: Dict[str, Any] = {}
    receipt: Dict[str, Any] = {}
    if audit_id:
        audit_row = await db.synisense_audit_log.find_one(
            {"audit_id": audit_id, "tenant_id": current["id"]},
            {"_id": 0},
        ) or {}
        receipt = await db.synisense_trust_receipts.find_one(
            {"audit_id": audit_id, "tenant_id": current["id"]},
            {"_id": 0, "payload_hash": 0},
        ) or {}

    # Compose prose via the shared composer so the UI panel + the
    # downloadable PDF stay in lockstep (Phase E Sub-task H fix bundle).
    composed = compose_audit_entry_prose(audit_row=audit_row, receipt_row=receipt)

    return {
        "message_id": message_id,
        "audit_id": audit_id,
        "shielding_prose":  composed["shielding_prose"],
        "provider_prose":   composed["provider_prose"],
        "scores":           composed["scores"],
        "references": {
            "purpose":               composed["references"]["purpose"],
            "purpose_label":         composed["references"]["purpose_label"],
            "consumer":              composed["references"]["consumer"],
            "audit_id":              composed["references"]["audit_id"],
            "trust_receipt_id":      composed["references"]["trust_receipt_id"],
            "trust_receipt_version": composed["references"]["trust_receipt_version"],
            # `signature` + `payload_hash` are intentionally NOT
            # surfaced on the UI panel — they belong to the
            # downloadable PDF for self-verification (security-by-
            # design).
        },
        "protective_layer_prose": _intervention_prose(matching_event),
        "protective_event": matching_event,
        # Phase C fix bundle (2026-05-13) — `raw_de_id_summary` was
        # exposed on the user-visible payload as a future leak hazard
        # (raw enum keys would surface if anything started rendering
        # it). Removed. The structured breakdown remains available
        # internally via `synisense_audit_log` for admin tooling.
    }


# ─────────────────────────────────────────────────────────────────────
# Audit panel — per-conversation aggregate strip.
# ─────────────────────────────────────────────────────────────────────
@router.get("/chats/{chat_id}/audit-panel/aggregate")
async def get_audit_panel_aggregate(
    chat_id: str,
    current: Dict[str, Any] = Depends(get_current_account),
):
    """Rolling aggregate across every Shield invoke this chat made.
    Powers the pinned strip at the top of the chat surface."""
    chat = await db.chats.find_one(
        {"id": chat_id, "account_id": current["id"]},
        {"_id": 0, "synisense_audit_ids": 1, "message_count": 1, "title": 1},
    )
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found.")

    audit_ids: List[str] = chat.get("synisense_audit_ids") or []
    if not audit_ids:
        return {
            "message_count": chat.get("message_count", 0),
            "llm_calls": 0,
            "identifiers_shielded": 0,
            "average_exposure_reduction": None,
            "average_dilution": None,
            "headline_prose": "No LLM calls have been made in this conversation yet.",
        }

    rows = await db.synisense_audit_log.find(
        {"audit_id": {"$in": audit_ids}, "tenant_id": current["id"]},
        {"_id": 0, "exposure_reduction_score": 1, "dilution_score": 1,
         "de_id_summary": 1},
    ).to_list(length=len(audit_ids) + 5)

    total_entities = 0
    er_sum = 0.0
    dl_sum = 0.0
    er_n = dl_n = 0
    for r in rows:
        for n in (r.get("de_id_summary") or {}).values():
            total_entities += int(n)
        if isinstance(r.get("exposure_reduction_score"), (int, float)):
            er_sum += float(r["exposure_reduction_score"])
            er_n += 1
        if isinstance(r.get("dilution_score"), (int, float)):
            dl_sum += float(r["dilution_score"])
            dl_n += 1
    er_avg = round(er_sum / er_n, 1) if er_n else None
    dl_avg = round(dl_sum / dl_n, 1) if dl_n else None

    head = (
        f"This conversation: {chat.get('message_count', 0)} messages · "
        f"Synisense shielded {_plural(total_entities, 'identifier')} "
        f"across {_plural(len(rows), 'LLM call')}."
    )
    if er_avg is not None and dl_avg is not None:
        head += f" Average exposure reduction: {er_avg}% · Average dilution: {dl_avg}%."

    return {
        "message_count": chat.get("message_count", 0),
        "llm_calls": len(rows),
        "identifiers_shielded": total_entities,
        "average_exposure_reduction": er_avg,
        "average_dilution": dl_avg,
        "headline_prose": head,
    }


# ─────────────────────────────────────────────────────────────────────
# Archived chats — list + permanent delete.
# (Existing /restore endpoint lives in routers/chat.py.)
# ─────────────────────────────────────────────────────────────────────
@router.get("/chats/archived")
async def list_archived_chats(
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    current: Dict[str, Any] = Depends(get_current_account),
):
    """User's archived chats, most recently archived first."""
    cursor = db.chats.find(
        {"account_id": current["id"], "status": "archived"},
        {"_id": 0, "id": 1, "title": 1, "archived_at": 1,
         "message_count": 1, "last_message_preview": 1,
         "model_label": 1},
    ).sort("archived_at", -1).skip(skip).limit(limit)
    rows = await cursor.to_list(length=limit)
    total = await db.chats.count_documents(
        {"account_id": current["id"], "status": "archived"},
    )
    return {"items": rows, "total": total, "limit": limit, "skip": skip}


@router.delete("/chats/{chat_id}/permanent")
async def permanent_delete_chat(
    chat_id: str,
    body: Dict[str, Any] = Body(default_factory=dict),
    current: Dict[str, Any] = Depends(get_current_account),
):
    """Hard delete a chat. Requires `{"confirm": true}` in the body to
    guard against accidental cascade."""
    if not body.get("confirm"):
        raise HTTPException(
            status_code=400,
            detail="Permanent delete requires {\"confirm\": true} in the request body.",
        )
    chat = await db.chats.find_one(
        {"id": chat_id, "account_id": current["id"]},
        {"_id": 0, "id": 1, "status": 1},
    )
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found.")
    await db.chats.delete_one({"id": chat_id, "account_id": current["id"]})
    await db.chat_messages.delete_many({"chat_id": chat_id, "account_id": current["id"]})
    return {"ok": True, "deleted": chat_id}
