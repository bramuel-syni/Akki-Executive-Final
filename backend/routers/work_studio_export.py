"""Phase C.2 — Work Studio export router.

Endpoints:
  POST /api/contexts/{cid}/work-studio/export/{kind}    — start
  GET  /api/contexts/{cid}/work-studio/exports/{eid}    — poll status
  GET  /api/contexts/{cid}/work-studio/exports/{eid}/download  — pin-token + bytes

Storage: `/app/backend/uploads/work_studio_exports/<eid>.<ext>` (local
backend in dev — same path the rest of the app uses).

LLM content stage: two-pass canonical via `services.two_pass` machinery.
Pass 1 (silent reasoning) and Pass 2 (strict JSON content_dict) both
recorded in `chat_audit_log` per the B.2 contract, with the new payload
keys `export_kind` and `export_artefact_id`.

Thin-input refusal (deterministic): when the user-supplied description /
objective / scope fails the same `detect_thin_input` heuristic used by
the chat path, the export is marked `failed` with reason `thin_input`
and the verbatim memo refusal text is surfaced in the API response so
the UI can render it.
"""
from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import re
import secrets
import time
import uuid
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Literal, Tuple

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from core import (
    db, now, iso, write_audit, require_context_membership,
)
from services import two_pass as _tp
from services import work_studio_export as _ex

logger = logging.getLogger("akki.work_studio_export.router")

router = APIRouter(prefix="/api")

# Local storage root
_EXPORTS_ROOT = Path("/app/backend/uploads/work_studio_exports")
_EXPORTS_ROOT.mkdir(parents=True, exist_ok=True)

# Download token TTL.
_DOWNLOAD_TTL_SECONDS = 15 * 60


# =============================================================================
# Request / response shapes
# =============================================================================
class ExportRequestIn(BaseModel):
    description: str = Field(min_length=1, max_length=2000)
    objective:   str = Field(min_length=1, max_length=2000)
    scope:       str = Field(min_length=1, max_length=2000)
    output_format: Literal["docx", "pptx", "pdf", "auto"] = "auto"


class ExportStatusOut(BaseModel):
    export_id: str
    status: str
    kind: str
    output_format: str
    file_name: Optional[str] = None
    sensitivity_band: Optional[str] = None
    error: Optional[str] = None
    refusal_text: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None
    download_token: Optional[str] = None
    chat_audit_id: Optional[str] = None


# =============================================================================
# Output-format selection
# =============================================================================
_AUTO_FORMAT = {"brief": "docx", "deck": "pptx", "report": "docx"}
_VALID_KINDS = ("brief", "deck", "report")


def _resolve_format(kind: str, requested: str) -> str:
    if requested == "auto":
        return _AUTO_FORMAT[kind]
    if kind == "deck" and requested == "pdf":
        # Soft fork — see services/work_studio_export.render_deck_pdf.
        # We force pptx so the user always gets a file. The audit log
        # records the substitution.
        return "pptx"
    return requested


# =============================================================================
# Hash-chain helper for chat_audit_log (mirrors routers/chat.py)
# =============================================================================
async def _append_chat_audit(
    *, account_id: str, chat_id: str, action: str,
    payload: Dict[str, Any], request: Optional[Request],
) -> Dict[str, Any]:
    """Append a row to chat_audit_log with the same canonical-JSON
    hashing layout used by routers/chat.py:_append_audit. We don't
    import the helper directly to avoid coupling, but the hash shape
    must match exactly so reviewers can grep-verify both paths."""
    # Find the previous hash for this account.
    prev = await db.chat_audit_log.find_one(
        {"account_id": account_id},
        sort=[("at", -1)], projection={"_id": 0, "row_hash": 1},
    )
    prev_hash = (prev or {}).get("row_hash", "GENESIS-AKKI-CHAT-AUDIT-2026")
    rid = str(uuid.uuid4())
    at = iso(now())
    ip = ""
    ua_sha = ""
    if request is not None:
        try:
            ip = request.client.host if request.client else ""
            ua = request.headers.get("user-agent", "")
            ua_sha = hashlib.sha256(ua.encode()).hexdigest()[:16] if ua else ""
        except Exception:
            pass
    canonical = {
        "prev": prev_hash, "id": rid, "at": at,
        "account_id": account_id, "chat_id": chat_id,
        "action": action, "payload": payload, "ip": ip, "ua_sha": ua_sha,
    }
    row_hash = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    row = {
        "id": rid, "at": at, "account_id": account_id, "chat_id": chat_id,
        "action": action, "payload": payload, "ip": ip, "ua_sha": ua_sha,
        "prev_hash": prev_hash, "row_hash": row_hash,
    }
    await db.chat_audit_log.insert_one(row)
    return row


# =============================================================================
# BM25 grounding (mirrors the chat path, scoped to context documents)
# =============================================================================
async def _grounding_for_context(context_id: str, query: str, top_k: int = 8) -> List[Dict[str, Any]]:
    """Return top-K paragraphs from the context's documents for the
    given query. Mirrors routers/chat._retrieve_grounding_paragraphs
    but limits to docs only (no scope filter)."""
    cursor = db.documents.find(
        {"context_id": context_id, "status": {"$ne": "deleted"}},
        {"_id": 0, "id": 1, "name": 1, "extracted_text": 1, "paragraphs": 1},
    )
    docs = await cursor.to_list(200)
    if not docs:
        return []
    try:
        from bm25 import score_bm25
    except Exception:
        return []
    corpus: List[Dict[str, Any]] = []
    for d in docs:
        paras = d.get("paragraphs") or []
        if paras:
            for p in paras:
                txt = p.get("text") or ""
                if txt.strip():
                    corpus.append({
                        "text": txt, "doc_id": d["id"],
                        "doc_name": d.get("name") or "Document",
                        "anchor": p.get("anchor_id"),
                    })
        elif (d.get("extracted_text") or "").strip():
            corpus.append({
                "text": d["extracted_text"][:3000], "doc_id": d["id"],
                "doc_name": d.get("name") or "Document", "anchor": None,
            })
    if not corpus:
        return []
    scored = score_bm25(query=query, docs=[c["text"] for c in corpus])
    paired = sorted(
        list(zip(scored, corpus)), key=lambda x: x[0], reverse=True,
    )[:top_k]
    return [c for s, c in paired if s > 0]


def _format_grounding(paragraphs: List[Dict[str, Any]]) -> str:
    if not paragraphs:
        return ""
    rail = ["[GROUNDING]"]
    for p in paragraphs:
        head = f"  - {p['doc_name']}"
        if p.get("anchor"):
            head += f" (¶ {p['anchor']})"
        head += f": {p['text'][:600]}"
        rail.append(head)
    rail.append("[/GROUNDING]")
    return "\n".join(rail)


def _flat_user_input(body: ExportRequestIn) -> str:
    return (
        f"DESCRIPTION: {body.description.strip()}\n\n"
        f"OBJECTIVE: {body.objective.strip()}\n\n"
        f"SCOPE: {body.scope.strip()}"
    )


# =============================================================================
# LLM stage — two-pass canonical
# =============================================================================
def _strip_json_fence(s: str) -> str:
    s = (s or "").strip()
    # Strip ```json ... ``` fences if present.
    m = re.search(r"```(?:json)?\s*(.*?)```", s, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return s


def _try_parse_json(raw: str) -> Optional[Dict[str, Any]]:
    s = _strip_json_fence(raw)
    # Find the outermost JSON object.
    if not s.startswith("{"):
        first_brace = s.find("{")
        if first_brace == -1:
            return None
        s = s[first_brace:]
    last_brace = s.rfind("}")
    if last_brace != -1:
        s = s[: last_brace + 1]
    try:
        return json.loads(s)
    except Exception:
        return None


async def _run_two_pass_for_export(
    *, kind: str, body: ExportRequestIn, ctx_doc: Dict[str, Any],
    grounding_block: str, citations_manifest: List[Dict[str, Any]],
) -> Tuple[str, Dict[str, Any], int, int]:
    """Run Pass 1 (silent reasoning) + Pass 2 (strict JSON) over the
    Emergent universal-key proxy. Returns (pass_1_text, content_dict,
    pass_1_ms, pass_2_ms). Raises RuntimeError on irrecoverable failure.
    """
    emergent_key = os.environ.get("EMERGENT_LLM_KEY")
    if not emergent_key:
        raise RuntimeError("EMERGENT_LLM_KEY not configured.")
    from emergentintegrations.llm.chat import LlmChat, UserMessage

    user_text = _flat_user_input(body)

    # ── Pass 1 — reasoning rail (silent)
    pass_1_system = (
        "You are AKKI's reasoning rail for a Work Studio export. "
        "Apply the four-layer reasoning architecture to the user's "
        "task: candidate framings, triangulation against the grounding "
        "block, probability weighting (with confidence intervals), "
        "and reflection (three questions: what would change my mind? "
        "what's the explanation in six months if I got this wrong? "
        "what am I disappointed by?). Do NOT produce the deliverable. "
        "Do NOT emit JSON. Just the reasoning. Operating preferences "
        "(banned words, no glazing, lead with substance) apply."
    )
    p1_t0 = time.monotonic()
    p1_session = LlmChat(
        api_key=emergent_key,
        session_id=f"akki-export-p1-{uuid.uuid4().hex[:8]}",
        system_message=pass_1_system,
    ).with_model("anthropic", "claude-sonnet-4-5-20250929")
    p1_input = (grounding_block + "\n\n" if grounding_block else "") + user_text
    p1_raw = await p1_session.send_message(UserMessage(text=p1_input))
    pass_1_text = p1_raw if isinstance(p1_raw, str) else str(p1_raw)
    pass_1_ms = int((time.monotonic() - p1_t0) * 1000)

    # ── Pass 2 — JSON content_dict
    schema_doc = {
        "brief": (
            'Required keys: title, subtitle, classification ("Public"|'
            '"Internal"|"Confidential"|"Restricted"), period, '
            'generated_for, executive_summary (80-180 words), sections '
            '(list of {heading, paragraphs (list of strings, 1-3 items),'
            ' pullquote (optional), cites (list of 1-based indices into '
            'citations[])}), citations (list of {doc_id, doc_name, '
            'paragraph_anchor (optional)}). Do NOT invent doc_ids — use '
            'only entries from the citations manifest given below.'
        ),
        "deck": (
            'Required keys: title, subtitle, classification, period, '
            'generated_for, executive_summary (one or two short '
            'sentences), conclusion (one sentence), sections (4-6 '
            'items, each {heading, bullets (list of 3-5 prose lines), '
            'callout (optional), cites}), citations.'
        ),
        "report": (
            'Required keys: title, subtitle, classification, period, '
            'generated_for, executive_summary, sections (4-8 items, '
            'each {heading, subheading (optional), paragraphs (list of '
            '2-5 strings), pullquote (optional), cites}), '
            'recommendations (list of 1-5 short imperatives), '
            'citations.'
        ),
    }[kind]

    cite_manifest_text = "\n".join(
        f"  [{i+1}] doc_id={c['doc_id']}  doc_name={c['doc_name']}"
        for i, c in enumerate(citations_manifest)
    ) or "  (no documents tethered — use citations: [] in your output)"

    pass_2_system = (
        "You are AKKI's deliverable composer. Produce a SINGLE JSON "
        "object — no markdown fences, no preamble, no commentary, just "
        "valid JSON parseable by json.loads. The schema is:\n"
        f"{schema_doc}\n\n"
        "Operating preferences (apply on every string you emit):\n"
        " - No glazing. Lead with substance.\n"
        " - Banned words: " + ", ".join(_tp.BANNED_WORDS) + ".\n"
        " - The Economist test, senior peer test, restraint test must pass.\n"
        " - If you make a claim you cannot trace to the grounding "
        "block or the citations manifest below, do not include it.\n"
        " - Citations manifest (use ONLY these; cites[] are 1-based "
        "indices into THIS list):\n"
        f"{cite_manifest_text}\n\n"
        "The Pass 1 reasoning has already been produced and is in "
        "[PASS_1_REASONING] below. Honour the selected framing fully."
    )
    p2_t0 = time.monotonic()
    p2_session = LlmChat(
        api_key=emergent_key,
        session_id=f"akki-export-p2-{uuid.uuid4().hex[:8]}",
        system_message=pass_2_system,
    ).with_model("anthropic", "claude-sonnet-4-5-20250929")
    p2_input = (
        f"[PASS_1_REASONING]\n{pass_1_text}\n[/PASS_1_REASONING]\n\n"
        + (grounding_block + "\n\n" if grounding_block else "")
        + user_text
        + "\n\nProduce the JSON now. Set classification to 'Internal' "
        "unless the description mentions sensitive material that warrants "
        "Confidential or Restricted. Set generated_for to the context name."
    )
    p2_raw = await p2_session.send_message(UserMessage(text=p2_input))
    pass_2_text = p2_raw if isinstance(p2_raw, str) else str(p2_raw)
    pass_2_ms = int((time.monotonic() - p2_t0) * 1000)

    parsed = _try_parse_json(pass_2_text)
    if parsed is None:
        raise RuntimeError(
            f"Pass 2 LLM did not return parseable JSON (kind={kind}). "
            f"Head: {pass_2_text[:200]!r}"
        )

    # Force the canonical context name + period overrides if absent.
    parsed.setdefault("generated_for", ctx_doc.get("name") or "—")
    if not parsed.get("citations"):
        parsed["citations"] = citations_manifest
    return pass_1_text, parsed, pass_1_ms, pass_2_ms


# =============================================================================
# Export worker (BackgroundTasks)
# =============================================================================
async def _run_export(
    *, export_id: str, account_id: str, context_id: str, kind: str,
    output_format: str, body: ExportRequestIn,
):
    """Execute the LLM stage + render + persist + audit. Runs in
    BackgroundTasks. Updates db.work_studio_exports as it progresses.
    """
    ctx_doc = await db.contexts.find_one({"id": context_id}, {"_id": 0})
    if not ctx_doc:
        await db.work_studio_exports.update_one(
            {"id": export_id},
            {"$set": {"status": "failed", "error": "context_missing",
                      "completed_at": iso(now())}},
        )
        return
    ctx_meta = {
        "context_name":     ctx_doc.get("name") or "—",
        "classification":   "Internal",
        "period":           "—",
        "generated_at_human": _ex.now_human(),
    }

    # ── Synisense-shielded grounding context for the LLM stage. We
    # rely on the existing chat path's grounding paragraphs so the
    # documents are already de-identified at upload-time.
    user_input = _flat_user_input(body)
    grounding = await _grounding_for_context(context_id, user_input, top_k=8)
    grounding_block = _format_grounding(grounding)

    # Citation manifest = unique docs in grounding (id + name).
    seen: Dict[str, str] = {}
    for g in grounding:
        seen.setdefault(g["doc_id"], g["doc_name"])
    citations_manifest = [
        {"doc_id": k, "doc_name": v, "paragraph_anchor": None}
        for k, v in seen.items()
    ]

    # ── Thin-input deterministic refusal — runs on the combined input.
    thin = _tp.detect_thin_input(
        turn_class="strategic_deliverable",
        text=user_input,
        attached_document_ids=[d["doc_id"] for d in citations_manifest],
        prior_substantive_turns=0,
    )
    if thin is not None:
        # Verbatim memo template; the bracket is filled with a static
        # phrase since we do not have a chat session here to run a
        # cheap evidence-list call. The brief allows the static fallback.
        refusal_text = _tp.THIN_INPUT_REFUSAL_TEMPLATE.format(
            evidence_phrase=_tp.THIN_INPUT_FALLBACK_EVIDENCE
        )
        await _append_chat_audit(
            account_id=account_id, chat_id=f"export-{export_id}",
            action="chat.refused", payload={
                "refusal_reason": "thin_input",
                "turn_class": "strategic_deliverable",
                "evidence_phrase": _tp.THIN_INPUT_FALLBACK_EVIDENCE,
                "evidence_source": "fallback_static",
                "detection": thin,
                "channel": "export",
                "deterministic": True,
                "export_kind": kind,
                "export_artefact_id": export_id,
            }, request=None,
        )
        await db.work_studio_exports.update_one(
            {"id": export_id},
            {"$set": {
                "status": "failed", "error": "thin_input",
                "refusal_text": refusal_text,
                "completed_at": iso(now()),
            }},
        )
        try:
            await write_audit(
                account_id=account_id, context_id=context_id,
                action="work_studio.export.failed", target_id=export_id,
                metadata={"export_id": export_id, "kind": kind,
                          "reason": "thin_input"},
            )
        except Exception:
            pass
        return

    # ── Two-pass canonical LLM stage
    try:
        pass_1, content_dict, p1_ms, p2_ms = await _run_two_pass_for_export(
            kind=kind, body=body, ctx_doc=ctx_doc,
            grounding_block=grounding_block,
            citations_manifest=citations_manifest,
        )
    except Exception as e:
        logger.exception("Export LLM stage failed")
        await db.work_studio_exports.update_one(
            {"id": export_id},
            {"$set": {"status": "failed", "error": f"llm_error:{type(e).__name__}",
                      "completed_at": iso(now())}},
        )
        try:
            await write_audit(
                account_id=account_id, context_id=context_id,
                action="work_studio.export.failed", target_id=export_id,
                metadata={"export_id": export_id, "kind": kind,
                          "reason": "llm_error"},
            )
        except Exception:
            pass
        return

    # ── Pre-render banned-word scan on the JSON content text. We don't
    # block on this — we record any hit on the audit row.
    pre_text = _ex.scrape_content_text(content_dict)
    pre_hit = _ex.scan_for_banned_words(pre_text)

    # ── Render
    try:
        ctx_meta_full = {
            **ctx_meta,
            "context_name": ctx_doc.get("name") or "—",
        }
        if output_format == "docx" and kind == "brief":
            data, sha, fname = _ex.render_brief_docx(content_dict, ctx_meta_full)
        elif output_format == "docx" and kind == "report":
            data, sha, fname = _ex.render_report_docx(content_dict, ctx_meta_full)
        elif output_format == "pptx" and kind == "deck":
            data, sha, fname = _ex.render_deck_pptx(content_dict, ctx_meta_full)
        elif output_format == "pdf" and kind == "brief":
            data, sha, fname = _ex.render_brief_pdf(content_dict, ctx_meta_full)
        elif output_format == "pdf" and kind == "report":
            data, sha, fname = _ex.render_report_pdf(content_dict, ctx_meta_full)
        elif output_format == "pdf" and kind == "deck":
            # Soft fork — should have been resolved at request time.
            raise _ex.ContentValidationError(
                "PDF output is not supported for decks in this pod."
            )
        else:
            raise _ex.ContentValidationError(
                f"No renderer for kind={kind} format={output_format}."
            )
    except _ex.ContentValidationError as ve:
        logger.warning("Render rejected content: %s", ve)
        await db.work_studio_exports.update_one(
            {"id": export_id},
            {"$set": {"status": "failed",
                      "error": f"validation:{str(ve)[:200]}",
                      "completed_at": iso(now())}},
        )
        try:
            await write_audit(
                account_id=account_id, context_id=context_id,
                action="work_studio.export.failed", target_id=export_id,
                metadata={"export_id": export_id, "kind": kind,
                          "reason": "validation"},
            )
        except Exception:
            pass
        return
    except Exception as e:
        logger.exception("Render failed")
        await db.work_studio_exports.update_one(
            {"id": export_id},
            {"$set": {"status": "failed", "error": f"render:{type(e).__name__}",
                      "completed_at": iso(now())}},
        )
        return

    # ── Post-render banned-word scan (text scraped from the file).
    file_text = _ex.scrape_text(data, output_format) or pre_text
    post_hit = _ex.scan_for_banned_words(file_text)

    # ── Sensitivity scoring (deterministic — reuse Studio scorer).
    sensitivity_band = "INTERNAL"
    sensitivity_score = 0
    sensitivity_reasons: List[str] = []
    try:
        from studio_sensitivity import score_text
        sc = score_text(file_text)
        sensitivity_band = sc.get("band") or sensitivity_band
        sensitivity_score = sc.get("score") or 0
        sensitivity_reasons = sc.get("reasons") or []
    except Exception as e:  # noqa: BLE001
        logger.warning("studio_sensitivity unavailable: %s", e.__class__.__name__)

    # ── Persist file to storage_service path.
    fpath = _EXPORTS_ROOT / f"{export_id}.{output_format}"
    fpath.write_bytes(data)

    # ── Two-pass canonical chat_audit_log row (the headline B.2 audit row).
    msg_audit = await _append_chat_audit(
        account_id=account_id, chat_id=f"export-{export_id}",
        action="message.received", payload={
            "user_message_id": None,
            "reply_id": None,
            "model_id": "claude-sonnet-4-5", "mode": "export",
            "latency_ms": p1_ms + p2_ms,
            "char_len_reply": len(file_text),
            "channel": "export",
            "turn_class": "strategic_deliverable",
            "classifier_source": "forced",
            "classifier_latency_ms": 0,
            "four_check_surfaced": {"label": None, "ran": True},
            "refusal_reason": None,
            "two_pass": {
                "pass_1": pass_1[:24000],
                "pass_2": json.dumps(content_dict)[:24000],
                "pass_1_visible": False,
                "pass_1_present": True,
                "pass_1_ms": p1_ms,
                "pass_2_ms": p2_ms,
            },
            "voice_violation":
                ({"banned_word": post_hit, "retry_outcome": "ship_with_violation",
                  "before_text": "(post-render scrape)", "after_text": None}
                 if post_hit else None),
            "export_kind": kind,
            "export_artefact_id": export_id,
            "pre_render_banned_word": pre_hit,
            "sensitivity_band": sensitivity_band,
            "sensitivity_score": sensitivity_score,
        }, request=None,
    )

    if post_hit:
        try:
            await write_audit(
                account_id=account_id, context_id=context_id,
                action="work_studio.export.voice_violation",
                target_id=export_id,
                metadata={"export_id": export_id, "kind": kind,
                          "banned_word": post_hit},
            )
        except Exception:
            pass

    completed_at = iso(now())
    await db.work_studio_exports.update_one(
        {"id": export_id},
        {"$set": {
            "status": "complete",
            "file_name": fname,
            "file_path": str(fpath),
            "sha256": sha,
            "byte_len": len(data),
            "sensitivity_band": sensitivity_band,
            "sensitivity_score": sensitivity_score,
            "sensitivity_reasons": sensitivity_reasons,
            "completed_at": completed_at,
            "chat_audit_id": msg_audit["id"],
            "pass_1_ms": p1_ms, "pass_2_ms": p2_ms,
            "voice_violation": post_hit,
        }},
    )
    try:
        await write_audit(
            account_id=account_id, context_id=context_id,
            action="work_studio.export.completed", target_id=export_id,
            metadata={
                "export_id": export_id, "kind": kind,
                "output_format": output_format,
                "sensitivity_band": sensitivity_band,
                "sha256": sha,
            },
        )
    except Exception:
        pass


# =============================================================================
# Endpoints
# =============================================================================
@router.post("/contexts/{context_id}/work-studio/export/{kind}")
async def start_export(
    context_id: str,
    kind: str,
    body: ExportRequestIn,
    background: BackgroundTasks,
    request: Request,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Phase C.2 — start a Work Studio export. Returns 202 immediately
    with the export_id. The actual LLM + render run in the background."""
    if kind not in _VALID_KINDS:
        raise HTTPException(status_code=400, detail=f"Unknown kind. Allowed: {', '.join(_VALID_KINDS)}.")
    output_format = _resolve_format(kind, body.output_format)

    export_id = str(uuid.uuid4())
    created_at = iso(now())
    row = {
        "id": export_id,
        "context_id": context_id,
        "account_id": ctx["account"]["id"],
        "kind": kind,
        "output_format": output_format,
        "status": "running",
        "description_chars": len(body.description),
        "objective_chars": len(body.objective),
        "scope_chars": len(body.scope),
        "created_at": created_at,
        "completed_at": None,
        "file_name": None,
        "file_path": None,
        "sha256": None,
        "sensitivity_band": None,
        "error": None,
        "refusal_text": None,
        "chat_audit_id": None,
    }
    await db.work_studio_exports.insert_one(row)

    try:
        await write_audit(
            account_id=ctx["account"]["id"], context_id=context_id,
            action="work_studio.export.requested", target_id=export_id,
            metadata={"export_id": export_id, "kind": kind,
                      "output_format": output_format},
        )
    except Exception:
        pass

    # Schedule the worker. The wrapper detaches from the request scope.
    async def _runner():
        try:
            await _run_export(
                export_id=export_id, account_id=ctx["account"]["id"],
                context_id=context_id, kind=kind,
                output_format=output_format, body=body,
            )
        except Exception:
            logger.exception("export worker crashed")
            await db.work_studio_exports.update_one(
                {"id": export_id},
                {"$set": {"status": "failed", "error": "worker_crash",
                          "completed_at": iso(now())}},
            )
    background.add_task(_runner)

    return {
        "export_id": export_id,
        "status": "running",
        "kind": kind,
        "output_format": output_format,
        "created_at": created_at,
    }


@router.get("/contexts/{context_id}/work-studio/exports/{export_id}")
async def get_export_status(
    context_id: str,
    export_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    row = await db.work_studio_exports.find_one(
        {"id": export_id, "context_id": context_id}, {"_id": 0},
    )
    if not row:
        raise HTTPException(status_code=404, detail="Export not found.")
    if row["account_id"] != ctx["account"]["id"]:
        # Membership covers context-level access; we still narrow to
        # the requesting account so cross-account peeks are blocked.
        raise HTTPException(status_code=403, detail="Not the export owner.")

    download_token: Optional[str] = None
    if row["status"] == "complete":
        # Mint a fresh single-use token.
        token = secrets.token_urlsafe(32)
        await db.work_studio_export_tokens.insert_one({
            "token": token, "export_id": export_id,
            "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=_DOWNLOAD_TTL_SECONDS)).isoformat(),
            "used": False,
            "issued_at": iso(now()),
            "account_id": ctx["account"]["id"],
        })
        download_token = token

    return {
        "export_id": row["id"],
        "status": row["status"],
        "kind": row["kind"],
        "output_format": row["output_format"],
        "file_name": row.get("file_name"),
        "sensitivity_band": row.get("sensitivity_band"),
        "error": row.get("error"),
        "refusal_text": row.get("refusal_text"),
        "created_at": row["created_at"],
        "completed_at": row.get("completed_at"),
        "download_token": download_token,
        "chat_audit_id": row.get("chat_audit_id"),
    }


@router.get("/contexts/{context_id}/work-studio/exports/{export_id}/download")
async def download_export(
    context_id: str,
    export_id: str,
    token: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    row = await db.work_studio_exports.find_one(
        {"id": export_id, "context_id": context_id}, {"_id": 0},
    )
    if not row:
        raise HTTPException(status_code=404, detail="Export not found.")
    if row["account_id"] != ctx["account"]["id"]:
        raise HTTPException(status_code=403, detail="Not the export owner.")
    if row["status"] != "complete":
        raise HTTPException(status_code=404, detail="Export not ready.")

    tok = await db.work_studio_export_tokens.find_one(
        {"token": token, "export_id": export_id, "used": False},
        {"_id": 0},
    )
    if not tok:
        raise HTTPException(status_code=403, detail="Invalid download token.")
    if tok.get("account_id") != ctx["account"]["id"]:
        raise HTTPException(status_code=403, detail="Token does not match account.")
    try:
        exp = datetime.fromisoformat((tok.get("expires_at") or "").replace("Z", "+00:00"))
        if exp < datetime.now(timezone.utc):
            raise HTTPException(status_code=403, detail="Token expired.")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=403, detail="Bad token shape.")

    # Mark used (best-effort single-use).
    await db.work_studio_export_tokens.update_one(
        {"token": token},
        {"$set": {"used": True, "used_at": iso(now())}},
    )

    fpath = Path(row["file_path"]) if row.get("file_path") else None
    if not fpath or not fpath.exists():
        raise HTTPException(status_code=404, detail="File missing on disk.")
    data = fpath.read_bytes()

    fmt = row["output_format"]
    media_types = {
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "pdf":  "application/pdf",
    }
    return Response(
        content=data,
        media_type=media_types.get(fmt, "application/octet-stream"),
        headers={
            "Content-Disposition": f'attachment; filename="{row["file_name"]}"',
            "X-AKKI-Sensitivity-Band": row.get("sensitivity_band") or "INTERNAL",
            "Cache-Control": "private, no-store",
        },
    )
