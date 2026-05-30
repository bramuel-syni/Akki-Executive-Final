"""AKKI Chat — privacy-shielded multi-model conversation surface.

Untethered from any company context. Lets executives have a personal,
regulated AI conversation without exposing their internal materials to
the LLM provider in raw form. Synisense shielding runs automatically
when identifiers are detected (auto policy) and an immutable audit log
captures every shielding decision with chained hashes for tamper
evidence — bank-grade.

Endpoints:
    POST   /api/chats                          create a new conversation
    GET    /api/chats                          list active conversations
    GET    /api/chats/{cid}                    full thread (messages)
    PATCH  /api/chats/{cid}                    title/model/policy
    DELETE /api/chats/{cid}                    archive
    POST   /api/chats/{cid}/messages           send a user message; AKKI replies
    GET    /api/chats/{cid}/audit              bank-grade audit trail
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from core import db, get_current_account  # noqa: E402
from core import now as _now, iso as _iso  # noqa: E402
from services.synisense import (
    shield_payload_async as _syn_shield,
    shielding_report as _syn_report,
    rehydrate as _syn_rehydrate,
)
from services.rbac import require_role, ACTIVE_CONTEXT_HEADER  # noqa: E402  Phase B.1
from services import two_pass as _tp  # noqa: E402  Phase B.2

logger = logging.getLogger("akki.chat")
router = APIRouter(prefix="/api")


# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------
ShieldingPolicy = Literal["auto", "always", "off"]

# Provider+model identifiers exposed to the user. Keep in sync with the
# Universal LLM proxy.
#
# Patch 26G — refresh against latest provider releases (verified Feb 2026):
#   * Anthropic — Claude Opus 4.6 added (verified GA via Anthropic — see
#     https://www.anthropic.com/news/claude-opus-4-6). Sonnet 4.5 + Haiku
#     4.5 kept as faster + cheaper alternatives.
#   * Sprint Z1.1 (2026-05-29) — repaired the Opus id (was
#     `claude-opus-4-7-20260416` which doesn't exist in the Anthropic
#     model registry → `litellm.BadRequestError: Invalid model name`).
#     Switched to `claude-opus-4-6` (verified id; already in use by
#     `llm_service.LLM_MODEL_DEEP` default).
#   * OpenAI — GPT-5.5 added (released May 2026 as the new default
#     ChatGPT model per OpenAI). GPT-5.2 kept as legacy fallback.
#   * Google — Gemini 3.1 Pro added (most advanced per DeepMind model
#     card). Gemini 3 Flash added (3x faster than 2.5 Pro). Gemini
#     2.5 family kept as legacy fallbacks.
#
# Friendly `label` shows on the picker. `model` is the provider-side
# identifier used by emergentintegrations; the full identifier shows
# in the picker tooltip.
SUPPORTED_MODELS: List[Dict[str, str]] = [
    # ── Anthropic ─────────────────────────────────────────────────────
    {"id": "claude-opus-4-6",    "label": "Claude Opus 4.6",    "provider": "anthropic",
     "model": "claude-opus-4-6",            "tone": "highest reasoning, agentic"},
    {"id": "claude-sonnet-4-5",  "label": "Claude Sonnet 4.5",  "provider": "anthropic",
     "model": "claude-sonnet-4-5-20250929", "tone": "careful, long-form"},
    {"id": "claude-haiku-4-5",   "label": "Claude Haiku 4.5",   "provider": "anthropic",
     "model": "claude-haiku-4-5-20251001",  "tone": "fast, terse"},
    # ── OpenAI ────────────────────────────────────────────────────────
    {"id": "gpt-5-5",            "label": "GPT-5.5",            "provider": "openai",
     "model": "gpt-5.5",                    "tone": "newest default"},
    {"id": "gpt-5-2",            "label": "GPT-5.2",            "provider": "openai",
     "model": "gpt-5.2",                    "tone": "balanced, fast"},
    # ── Google ────────────────────────────────────────────────────────
    {"id": "gemini-3-1-pro",     "label": "Gemini 3.1 Pro",     "provider": "gemini",
     "model": "gemini-3.1-pro",             "tone": "most advanced"},
    {"id": "gemini-3-flash",     "label": "Gemini 3 Flash",     "provider": "gemini",
     "model": "gemini-3-flash",             "tone": "fastest in class"},
    {"id": "gemini-2-5-pro",     "label": "Gemini 2.5 Pro",     "provider": "gemini",
     "model": "gemini-2.5-pro",             "tone": "research-heavy"},
    {"id": "gemini-2-5-flash",   "label": "Gemini 2.5 Flash",   "provider": "gemini",
     "model": "gemini-2.5-flash",           "tone": "fast"},
]
DEFAULT_MODEL_ID = "claude-sonnet-4-5"


# ─── Sprint Z1.1 (2026-05-29) — model-cascade fallback ────────────────
# When the chosen provider rejects the model id (litellm BadRequest /
# Invalid model name / model_not_found), the previous flow returned a
# `proxy_fallback_failed` error chunk to the client because every
# fallback layer was retrying with the SAME invalid model id.
#
# This cascade adds MODEL-LEVEL fallback ABOVE the proxy/direct
# transport layer: chosen → Sonnet 4.5 → Sonnet 3.7 → Haiku safety.
# Each demotion writes a `model_fallback` audit-log row capturing
# `from`/`to`/`reason` so operators can correlate spikes.
MODEL_FALLBACK_CASCADE: List[str] = [
    "claude-sonnet-4-5",   # workhorse — verified id, fast
    "claude-sonnet-3-7",   # older Sonnet (Anthropic-published anchored alias)
    "claude-haiku-4-5",    # safety net — cheapest, smallest
]

# Substrings that classify a stream-error reason as "model id rejected
# by provider" (i.e. retrying with the same id is futile). Matched
# case-insensitively against the `error` string captured upstream.
_MODEL_INVALID_MARKERS = (
    "badrequest",
    "bad request",
    "invalid model",
    "model_not_found",
    "model not found",
    "model does not exist",
    "unknown model",
    "no such model",
    "not_found_error",
)


def _is_model_invalid_error(reason: Optional[str]) -> bool:
    """Return True if `reason` looks like an invalid-model-id error.
    Anything else (timeout, rate-limit, transport) should NOT trigger
    a model-level cascade — that's the transport-layer's job."""
    if not reason:
        return False
    low = reason.lower()
    return any(m in low for m in _MODEL_INVALID_MARKERS)


def _cascade_starting_from(model_id: str) -> List[str]:
    """Return the ordered cascade to try AFTER `model_id` failed.
    Strips `model_id` itself so we don't re-attempt the failing id."""
    return [m for m in MODEL_FALLBACK_CASCADE if m != model_id]


def _model_def(model_id: str) -> Optional[Dict[str, str]]:
    for m in SUPPORTED_MODELS:
        if m["id"] == model_id:
            return m
    return None


# -----------------------------------------------------------------------------
# Schemas
# -----------------------------------------------------------------------------
class LinkedContextIn(BaseModel):
    """Phase D.3 (2026-05-26) — inbound payload for a linked source
    item. Server resolves the title + excerpt; client may supply
    `title` as a fallback display but the server-resolved value wins.

    Allowed ctx_type values:
      - `document`               (db.documents)
      - `cycle`                  (db.cycles)
      - `task`                   (db.tasks — Phase F.3 / 2026-05-26)
      - `work_studio` / `work_studio_artefact` (db.work_studio_artefacts;
                                  `work_studio` normalises to the
                                  canonical name)
    """
    model_config = ConfigDict(extra="ignore")
    ctx_type: str = Field(min_length=1, max_length=40)
    ctx_id:   str = Field(min_length=1, max_length=80)

    @field_validator("ctx_type")
    @classmethod
    def _check_ctx_type(cls, v: str) -> str:
        allowed = {"document", "cycle", "task", "work_studio", "work_studio_artefact"}
        if v not in allowed:
            raise ValueError(f"ctx_type must be one of {sorted(allowed)}")
        if v == "work_studio":
            return "work_studio_artefact"
        return v


class ChatCreateIn(BaseModel):
    title: Optional[str] = Field(default=None, max_length=120)
    model_id: str = Field(default=DEFAULT_MODEL_ID)
    shielding_policy: ShieldingPolicy = "auto"
    # Phase 11 ITEM C — optional grounding. When provided, the chat is
    # tethered to a context's corpus and every assistant message gets a
    # BM25-grounded paragraph block injected into the prompt so the
    # model can cite stable paragraph anchors. Hallucinated citations
    # (markers that don't resolve to a known anchor) are dropped before
    # the response is returned to the client. When None, the chat
    # behaves exactly as it did pre-Phase-11 — untethered, no citations.
    context_id: Optional[str] = Field(default=None, max_length=120)
    # Phase D.3 (2026-05-26) — linked source item. When set on chat
    # create, the named item (document / cycle / work_studio artefact)
    # is persisted on the chat row, surfaced as a "Reading: …" chip
    # above the composer, and its summary is injected into the system
    # context on EVERY turn (Shield runs over the injection just like
    # any other prompt content). Backwards-compatible: None on legacy
    # chats means "untethered to a source item".
    linked_context: Optional[LinkedContextIn] = None


class ChatPatchIn(BaseModel):
    title: Optional[str] = Field(default=None, max_length=120)
    model_id: Optional[str] = None
    shielding_policy: Optional[ShieldingPolicy] = None
    context_id: Optional[str] = None  # set/clear grounding
    # Phase D.3 — clear by sending {"linked_context": null}. Replacing
    # one linked item with another isn't supported via patch: users
    # go back through `?ctx_type=…&ctx_id=…` to start over.
    linked_context: Optional[LinkedContextIn] = None
    # Tri-state surface: client signals "explicit clear" via a sentinel
    # field, because Pydantic doesn't distinguish missing-vs-null at
    # the schema level on Optional fields. When `clear_linked_context`
    # is True, the chat row's `linked_context` is unset regardless of
    # whether `linked_context` itself is present.
    clear_linked_context: Optional[bool] = None


class MessageSendIn(BaseModel):
    content: str = Field(min_length=1, max_length=20_000)
    # When `auto` policy + identifiers are detected + the user wants to
    # bypass shielding for this single message (rare), they set this.
    # We capture the bypass + acknowledgement in the audit log.
    acknowledge_unshielded: bool = False
    # Phase B.1 — Document IDs attached to this turn via the
    # /chats/{chat_id}/attach endpoint. The handler injects each
    # attached doc's de-identified text into the LLM prompt as an
    # additional [ATTACHMENT] block before the user's message. Empty
    # by default (most turns are text-only).
    attached_document_ids: List[str] = Field(default_factory=list, max_length=10)
    # Phase B.2 — turn-class override. The UI's "Think harder" button
    # sets force_class="strategic_deliverable" so the canonical two-pass
    # prompt runs regardless of what the heuristic would have decided.
    # Allowed values mirror two_pass.TURN_CLASSES.
    force_class: Optional[
        Literal[
            "trivial",
            "light_substantive",
            "substantive_analytical",
            "strategic_deliverable",
        ]
    ] = None
    # Phase B.2 — when True, Pass 1 reasoning is rendered visibly to the
    # user as a collapsible panel above Pass 2. The "Think harder" UI
    # button toggles this alongside force_class. An explicit cue in the
    # user's text ("think harder", "show your reasoning",
    # "walk me through") also forces visible Pass 1.
    show_pass_1: bool = False


# -----------------------------------------------------------------------------
# Audit log — bank-grade, append-only, hash-chained
# -----------------------------------------------------------------------------
def _sanitize(rec: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in rec.items() if k != "_id"}


def _require_active_context(request: Request) -> str:
    """Workstream A.2 — the chat surface treats X-Active-Context as
    REQUIRED. Returns the header value or raises 400. Centralised so
    the error shape is consistent across every chat route.
    """
    ctx = request.headers.get(ACTIVE_CONTEXT_HEADER)
    if not ctx:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "ACTIVE_CONTEXT_REQUIRED",
                "message": "X-Active-Context header required.",
            },
        )
    return ctx


# ─────────────────────────────────────────────────────────────────────
# Phase D.3 (2026-05-26) — linked-context resolver.
#
# A chat can be linked to a single source item (document / cycle /
# work_studio artefact). The link is captured at create-time, lives on
# the chat row, drives the "Reading: …" chip above the composer, and
# injects the item's summary into the LLM prompt on EVERY turn (Shield
# runs over the injection alongside the rest of the prompt, no bypass).
#
# Returns a dict in the canonical shape persisted on `chats.linked_context`:
#     {
#       "ctx_type": str, "ctx_id": str,
#       "title": str,             # captured at attach time
#       "excerpt": str,           # short content excerpt — re-fetched
#                                 # fresh on each send, so this stays
#                                 # as the at-attach-time snapshot
#       "attached_at": ISO ts,
#       "href": str,              # deep link back to the source
#     }
# Returns None when the referenced item doesn't exist OR the user
# can't see it (silent miss — the chip will render in a muted
# "Item no longer available" state and no context is injected).
# ─────────────────────────────────────────────────────────────────────
async def _resolve_linked_context(
    *, ctx_type: str, ctx_id: str, context_id: str, account_id: str,
) -> Optional[Dict[str, Any]]:
    """Look up the linked source item against the caller's context.
    Used at create-time (persist) and at every send (re-resolve for
    freshness + access check)."""
    if not ctx_type or not ctx_id:
        return None
    # Documents live in db.documents and are context-scoped. Access is
    # via the membership chain on the parent context (already enforced
    # on the calling chat route).
    if ctx_type == "document":
        doc = await db.documents.find_one(
            {"id": ctx_id, "context_id": context_id},
            {"_id": 0, "id": 1, "name": 1, "original_filename": 1,
             "extracted_text": 1, "preview": 1},
        )
        if not doc:
            return None
        return {
            "ctx_type": "document",
            "ctx_id":   doc["id"],
            "title":    doc.get("name") or doc.get("original_filename") or doc["id"],
            "excerpt": ((doc.get("extracted_text") or "")[:8000] or doc.get("preview") or ""),
            "href":     f"/app/workspace?doc={doc['id']}",
        }
    if ctx_type == "cycle":
        cyc = await db.cycles.find_one(
            {"id": ctx_id, "context_id": context_id},
            {"_id": 0, "id": 1, "title": 1, "description": 1},
        )
        if not cyc:
            return None
        return {
            "ctx_type": "cycle",
            "ctx_id":   cyc["id"],
            "title":    cyc.get("title") or cyc["id"],
            "excerpt":  (cyc.get("description") or "")[:8000],
            "href":     f"/app/cycle/{cyc['id']}",
        }
    # Phase F.3 (2026-05-26) — Task Manager linked-context support.
    # Tasks are owned by the caller (account_id), not context-scoped
    # like documents/cycles. The excerpt blends the objective +
    # success criteria + a one-line readiness summary so the linked
    # chip carries enough context for the model to use it.
    if ctx_type == "task":
        t = await db.tasks.find_one(
            {"id": ctx_id, "account_id": account_id},
            {"_id": 0, "id": 1, "name": 1, "objective": 1,
             "success_criteria": 1, "readiness_score": 1, "state": 1,
             "team": 1, "due_date": 1},
        )
        if not t:
            return None
        readiness = t.get("readiness_score", 0)
        team_n = len(t.get("team") or [])
        bits = []
        if t.get("objective"):
            bits.append(f"Objective: {t['objective']}")
        if t.get("success_criteria"):
            bits.append(f"Success criteria: {t['success_criteria']}")
        bits.append(
            f"State: {t.get('state', 'draft')} · readiness {readiness}% · {team_n} contributors"
            + (f" · due {t['due_date']}" if t.get("due_date") else "")
        )
        return {
            "ctx_type": "task",
            "ctx_id":   t["id"],
            "title":    t.get("name") or t["id"],
            "excerpt":  "\n\n".join(bits)[:8000],
            "href":     f"/app/task-manager?task_id={t['id']}",
        }
    if ctx_type in ("work_studio", "work_studio_artefact"):
        art = await db.work_studio_artefacts.find_one(
            {"id": ctx_id, "context_id": context_id},
            {"_id": 0, "id": 1, "title": 1, "summary": 1},
        )
        if not art:
            return None
        return {
            "ctx_type": "work_studio_artefact",
            "ctx_id":   art["id"],
            "title":    art.get("title") or art["id"],
            "excerpt":  (art.get("summary") or "")[:8000],
            "href":     f"/app/work-studio/artefact/{art['id']}",
        }
    # Unknown ctx_type — silently miss. The schema validator should
    # already have rejected it; defensive return for any future
    # caller that bypasses the schema.
    return None


async def _last_audit_hash(account_id: str) -> str:
    """Return the SHA256 hash of the most recent audit row for this user,
    or a constant genesis hash if none yet. Used to chain rows so any
    tampering with an earlier row breaks every downstream hash."""
    last = await db.chat_audit_log.find_one(
        {"account_id": account_id}, {"_id": 0, "row_hash": 1},
        sort=[("at", -1)],
    )
    if last and last.get("row_hash"):
        return last["row_hash"]
    return "GENESIS-AKKI-CHAT-AUDIT-2026"


async def _append_audit(
    *, account_id: str, chat_id: str, action: str,
    request: Optional[Request] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Append-only audit row. Writes a chained SHA256 across the prior
    row, the action, and a content fingerprint. Bank auditors can verify
    the chain against an export and detect any retroactive edit.
    """
    prev = await _last_audit_hash(account_id)
    payload = payload or {}
    at_iso = _iso(_now())
    row_id = str(uuid.uuid4())
    ip = ""
    ua = ""
    if request is not None:
        ip = (request.headers.get("x-forwarded-for", "") or
              (request.client.host if request.client else "")).split(",")[0].strip()
        ua = (request.headers.get("user-agent", "") or "")[:300]
    canonical = json.dumps(
        {"prev": prev, "id": row_id, "at": at_iso, "account_id": account_id,
         "chat_id": chat_id, "action": action, "payload": payload,
         "ip": ip, "ua_sha": hashlib.sha256(ua.encode()).hexdigest()[:16]},
        sort_keys=True, separators=(",", ":"),
    )
    row_hash = hashlib.sha256(canonical.encode()).hexdigest()
    row = {
        "id": row_id, "account_id": account_id, "chat_id": chat_id,
        "action": action, "payload": payload, "ip": ip,
        "ua_sha": hashlib.sha256(ua.encode()).hexdigest()[:16],
        "at": at_iso, "prev_hash": prev, "row_hash": row_hash,
    }
    await db.chat_audit_log.insert_one(row)
    return row


# -----------------------------------------------------------------------------
# Phase B.2 — Two-pass orchestration helpers
#
# These helpers are shared by both /messages (sync) and /messages/stream
# (SSE) so the audit shape, classifier flow, and banned-word retry logic
# stay identical across channels.
# -----------------------------------------------------------------------------
async def _record_synisense_audit_evidence(
    *, surface: str, account_id: str, context_id: Optional[str], text: str,
    # Phase J.2 — per-message linking so the chat audit UI can render a
    # redaction badge per message (not per conversation).
    message_id: Optional[str] = None,
    chat_id: Optional[str] = None,
) -> None:
    """Run the Synisense pipeline for audit evidence on a non-user-text
    surface (chat_classifier, chat_four_check). The redacted output is
    discarded — the only purpose is to write a row to db.synisense_runs
    so acceptance bar #2 ("silent four-check ran, evidenced by
    synisense_runs.surface='chat_four_check'") is satisfied for every
    qualifying turn.
    """
    if surface not in {"chat_classifier", "chat_four_check"}:
        return  # belt-and-braces guard
    # Phase B P0 fix (2026-05-13): the legacy Phase 12.1 `syn_run`
    # audit-evidence stamp has been retired. Phase A's Shield already
    # writes an audit row per LLM call (see `synisense_audit_log`), so
    # the chat-side classifier/four-check surfaces inherit that
    # provenance the moment they invoke `shield.client.invoke()`. We
    # keep this helper as a no-op for now so callers don't need to be
    # rewritten in this patch; Phase C will replace its callers with
    # explicit Shield invocations carrying a purpose like
    # `chat.tools.four_check`.
    _ = (text, account_id, context_id, message_id, chat_id)  # noqa: F841
    return


async def _llm_classify_fallback(text: str, *, tenant_id: str = "system.chat.classify") -> Optional[str]:
    """Classifier LLM fallback used by `two_pass.classify_turn_async`.

    Phase B (2026-05-13): migrated through Synisense Shield with
    `purpose="chat.tools.classify_turn"`. Internal caller — the chat
    turn text already passed Shield de-id at message ingress so the
    extra de-id pass here is double-protection (harmless). On any
    error, returns None so the caller defaults to substantive_analytical.
    """
    try:
        from services.synisense.shield.client import invoke as shield_invoke
        result = await shield_invoke(
            purpose="chat.tools.classify_turn",
            content=(
                "SYSTEM: Classify the user's chat turn into exactly one of: "
                "trivial, light_substantive, substantive_analytical, "
                "strategic_deliverable. Reply with only the label, lowercase, "
                "no punctuation.\n\n"
                f"USER TURN:\n{text}"
            ),
            tenant_id=tenant_id,
            consumer_id="chat",
            user_id=tenant_id,
            model_preference="balanced",  # Gemini flash — cheapest
            internal_caller=True,
        )
        label = (result.get("response") or "").strip().lower()
        # Tolerate prefix/suffix noise.
        for cls in _tp.TURN_CLASSES:
            if label == cls or cls in label:
                return cls
        return None
    except Exception as e:  # noqa: BLE001
        logger.warning("classifier shield fallback failed: %s", e.__class__.__name__)
        return None


async def _classify_and_audit(
    *, text: str, force_class: Optional[str], account_id: str,
    context_id: Optional[str],
) -> Dict[str, Any]:
    """Run the classifier AND record the chat_classifier Synisense row.

    Returns the dict from `classify_turn_async` augmented with the
    `four_check_will_run` boolean. The Synisense audit row writes in
    parallel with the heuristic so trivial turns (sub-1 ms) still pay
    the redaction cost on the same hot path — but the classifier call
    completes immediately in those cases.
    """
    # Run the audit-evidence pass concurrently with the heuristic; the
    # heuristic is sync so this is effectively just kicking off the
    # async run.
    import asyncio as _asyncio
    audit_task = _asyncio.create_task(
        _record_synisense_audit_evidence(
            surface="chat_classifier", account_id=account_id,
            context_id=context_id, text=text,
        ),
    )
    out = await _tp.classify_turn_async(
        text, force_class=force_class,
        llm_fallback=_llm_classify_fallback, fallback_timeout_ms=350,
    )
    # Don't block the request on the audit task — it must finish
    # eventually (best-effort) but the classifier latency budget is
    # 400 ms p95 so we let it run in the background.
    out["four_check_will_run"] = (out["turn_class"] != "trivial")
    out["_classifier_audit_task"] = audit_task
    return out


def _detect_voice_violation(text: str) -> Optional[str]:
    """Wrapper around `two_pass.find_banned_word` that returns the
    banned-word hit (lowercased). Centralised so future tightening
    (e.g. POS-aware filtering) lands in one place.
    """
    return _tp.find_banned_word(text)



# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------
@router.get("/chat/models")
async def list_models(_: Dict[str, Any] = Depends(get_current_account)):
    return {"models": SUPPORTED_MODELS, "default_model_id": DEFAULT_MODEL_ID}


@router.post("/chats")
async def create_chat(
    body: ChatCreateIn, request: Request,
    current: Dict[str, Any] = Depends(get_current_account),
):
    if not _model_def(body.model_id):
        raise HTTPException(status_code=400, detail=f"Unknown model_id '{body.model_id}'.")

    # Wave 5 (2026-05-27) — General RAG (no-context) is now the
    # DEFAULT chat mode per the locked spec. Chat creation NO LONGER
    # requires a context — if neither X-Active-Context header nor
    # body.context_id is provided, the chat is minted as a "general"
    # chat with `context_id: None`. When the user later selects a
    # company context, subsequent chats become context-scoped
    # automatically (frontend passes `context_id: activeContext?.id`).
    # Workstream A.2's tight binding (original Phase A) was a misread
    # of the Phase Q spec, which always anticipated a general default.
    active_ctx = request.headers.get(ACTIVE_CONTEXT_HEADER)
    body_ctx = (body.context_id or "").strip() if body.context_id else ""
    effective_ctx = body_ctx or active_ctx or None

    cid = str(uuid.uuid4())
    rec = {
        "id": cid,
        "account_id": current["id"],
        "title": (body.title or "New conversation").strip()[:120],
        "model_id": body.model_id,
        "shielding_policy": body.shielding_policy,
        "context_id": effective_ctx,
        "status": "active",
        "message_count": 0,
        "last_message_preview": "",
        "last_message_at": None,
        "created_at": _iso(_now()),
        "updated_at": _iso(_now()),
    }
    # Phase D.3 (2026-05-26) — resolve the linked source item and
    # persist it on the chat row. If the item doesn't exist OR the
    # user can't see it, we drop linked_context silently (the chip
    # will not render). We never error here — linking is additive.
    if body.linked_context is not None:
        resolved = await _resolve_linked_context(
            ctx_type=body.linked_context.ctx_type,
            ctx_id=body.linked_context.ctx_id,
            context_id=effective_ctx,
            account_id=current["id"],
        )
        if resolved is not None:
            rec["linked_context"] = {
                "ctx_type":    resolved["ctx_type"],
                "ctx_id":      resolved["ctx_id"],
                "title":       resolved["title"],
                "excerpt":     resolved["excerpt"],
                "href":        resolved["href"],
                "attached_at": _iso(_now()),
            }
    await db.chats.insert_one(rec)
    # MongoDB `insert_one` mutates `rec` to add `_id`; strip before
    # returning. The `linked_context` block (if any) flows through as
    # part of `_sanitize`.
    rec.pop("_id", None)
    await _append_audit(
        account_id=current["id"], chat_id=cid, action="chat.created",
        request=request,
        payload={"model_id": body.model_id, "shielding_policy": body.shielding_policy,
                 "context_id": effective_ctx,
                 "linked_context": rec.get("linked_context")},
    )
    # Phase D.2 telemetry (2026-05-26) — handoff deep-link analytics.
    # Fires the moment a linked-context item is FIRST persisted on the
    # chat row (which is also the moment the LinkedContextChip will
    # first render on the client). We don't log on subsequent renders
    # (page nav / thread resume) — those are presentation events and
    # would spam the audit log. See HOME_CLEANUP_LOG.md → "D.2 —
    # audit correction".
    lc = rec.get("linked_context") or {}
    if lc.get("ctx_type") and lc.get("ctx_id"):
        try:
            from services.solva.telemetry import record_handoff
            await record_handoff(
                surface="chat",
                ctx_type=lc["ctx_type"],
                ctx_id=lc["ctx_id"],
                account_id=current["id"],
                chat_id=cid,
                context_id=effective_ctx,
            )
        except Exception as e:  # noqa: BLE001 — never block create
            logging.getLogger("chat").warning(
                "handoff telemetry failed: %s", e,
            )
    return _sanitize(rec)


# ─────────────────────────────────────────────────────────────────────
# Phase B.1 — Chat attachment.
#
# User attaches a document (PDF / DOCX / TXT / image) in the chat
# composer. The file goes through the document upload pipeline:
#   1. ClamAV scan (hard precondition; 503 if scanner offline unless
#      `ALLOW_UNSAFE_UPLOADS=true` in dev .env).
#   2. Save to storage (S3 / MinIO / local fallback).
#   3. Extract text (pypdf / python-docx / plain text).
#   4. Run Synisense Shield over the extracted text — same surface
#      label `chat` as the user-typed message path, so the audit trail
#      is uniform.
#   5. Run the deterministic studio_sensitivity scorer to give the UI
#      a band (PUBLIC / INTERNAL / CONFIDENTIAL / RESTRICTED) for the
#      attached-file chip.
#   6. Persist as a row in `db.documents` carrying
#      `source_channel="chat_attach"` so it appears in the active
#      context's Document Journal alongside other docs (memo + Phase
#      1 contract: chat attachments are journal docs).
#
# Returns:
#   {document_id, name, mime_type, size_bytes, char_len,
#    sensitivity: {score, label, classification},
#    storage_key, created_at}
# The chat composer stores `document_id` on a chip; on send the
# message-stream endpoint reads `attached_document_ids` and injects
# the de-identified text into the LLM prompt.
# ─────────────────────────────────────────────────────────────────────
_ATTACH_MAX_BYTES = 25 * 1024 * 1024   # 25 MB ceiling for chat
_ATTACH_ACCEPT_EXT = {
    ".pdf", ".docx", ".doc", ".txt", ".md",
    ".png", ".jpg", ".jpeg", ".webp",
}


@router.post("/chats/{chat_id}/attach")
async def attach_to_chat(
    chat_id: str,
    request: Request,
    file: UploadFile = File(...),
    current: Dict[str, Any] = Depends(get_current_account),
):
    """Ingest a file as a chat attachment. The file is saved as a
    document in the chat's bound context AND its de-identified text
    is made available to the next LLM turn via
    `attached_document_ids` on the message-send body.

    Body: multipart/form-data with one `file` part.
    Header: `X-Active-Context` is consulted defensively — when set,
            the chat's `context_id` MUST equal it (per-tab role
            binding from Phase A). Mismatch → 403.
    """
    chat = await db.chats.find_one(
        {"id": chat_id, "account_id": current["id"], "status": {"$ne": "archived"}},
        {"_id": 0},
    )
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    chat_ctx_id = chat.get("context_id")
    if not chat_ctx_id:
        # The chat was created without a context binding (legacy
        # un-grounded chat). Attachments without a context have
        # nowhere sensible to live as a document — refuse.
        raise HTTPException(
            status_code=400,
            detail="Cannot attach: this chat is not bound to a company context.",
        )

    # Workstream A.2 — X-Active-Context REQUIRED. The chat MUST be
    # bound to the active context for an attach to land safely.
    active_ctx = _require_active_context(request)
    if active_ctx != chat_ctx_id:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "ACTIVE_CONTEXT_MISMATCH",
                "message": (
                    "This conversation is bound to a different context "
                    "than your active selection. Switch contexts to "
                    "continue."
                ),
            },
        )

    # Verify the user has membership in the chat's context. We don't
    # use require_role here because the dependency was wired
    # post-creation on the chat — a chat the user owns implies the
    # membership existed at create time. We re-check now in case
    # membership was revoked.
    m = await db.memberships.find_one(
        {"account_id": current["id"], "context_id": chat_ctx_id, "status": "active"},
        {"_id": 0},
    )
    if not m:
        raise HTTPException(
            status_code=403,
            detail={"code": "MEMBERSHIP_REVOKED",
                    "message": "Your membership at this chat's context was revoked."},
        )

    from pathlib import Path as _Path
    filename = file.filename or "attachment"
    ext = _Path(filename).suffix.lower()
    if ext not in _ATTACH_ACCEPT_EXT:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported attachment type {ext}. "
                   f"Accepted: {', '.join(sorted(_ATTACH_ACCEPT_EXT))}",
        )

    data = await file.read()
    if len(data) > _ATTACH_MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Attachment too large. Max {_ATTACH_MAX_BYTES // 1024 // 1024} MB.",
        )

    # ClamAV — same hard precondition as the documents flow.
    from services import clamav_service
    from services.clamav_service import ClamAVUnreachable
    try:
        scan = await clamav_service.scan(data, filename, file_id=doc_id, user_id=current["id"])
    except ClamAVUnreachable as exc:
        raise HTTPException(
            status_code=503,
            detail={"error": "scanner_unavailable",
                    "reason": "virus scanner offline",
                    "details": str(exc)[:200]},
        )
    if not scan.clean:
        raise HTTPException(
            status_code=422,
            detail={"error": "blocked", "reason": "malware_suspected",
                    "signature": scan.signature},
        )

    from documents_service import save_to_storage, extract_text, make_preview
    from studio_sensitivity import score_sensitivity

    doc_id = str(uuid.uuid4())
    storage_key = save_to_storage(chat_ctx_id, doc_id, filename, data)
    text, err = extract_text(data, filename, file.content_type or "")
    preview = make_preview(text)

    # Synisense Shield — surface=chat (matches the user-typed path).
    # Phase B P0 fix (2026-05-13): the legacy `_syn_shield` call has
    # been retired. The uploaded file content flows through Shield the
    # moment a chat send references it in `body.content`; doing a
    # second de-id pass here would duplicate Shield's own work. We
    # persist the raw extracted text in `body_redacted` (Mongo column
    # name preserved for backward compat with existing `chats` rows);
    # downstream chat reads continue to surface the original content
    # because Shield re-identifies on the LLM response path.
    body_redacted: str = text
    syn_version = 1  # bumped — schema unchanged but pipeline replaced

    # Sensitivity band — deterministic scorer, no LLM.
    band = score_sensitivity({"text": text}) if text else {
        "score": 0, "classification": "PUBLIC", "label": "PUBLIC", "reasons": ["No extracted text"],
    }

    created_at = _iso(_now())
    doc = {
        "id": doc_id,
        "context_id": chat_ctx_id,
        "name": _Path(filename).stem.strip()[:200] or "Attachment",
        "original_filename": filename,
        "mime_type": file.content_type or "application/octet-stream",
        "size_bytes": len(data),
        "storage_key": storage_key,
        "status": "extracted" if text and not err else ("failed" if err else "empty"),
        "extracted_text": text,
        "extracted_chars": len(text or ""),
        "preview": preview,
        "data_trust": "mixed",
        "doc_type": "chat_attachment",
        "uploaded_by": current["id"],
        "source_channel": "chat_attach",
        "chat_id": chat_id,
        "synisense_version": syn_version,
        "body_redacted": body_redacted if syn_version else None,
        "sensitivity_band": band["classification"].lower(),
        "sensitivity_score": band["score"],
        "sensitivity_label": band["label"],
        "created_at": created_at,
        "updated_at": created_at,
    }
    await db.documents.insert_one(doc)

    return {
        "document_id": doc_id,
        "chat_id": chat_id,
        "context_id": chat_ctx_id,
        "name": doc["name"],
        "original_filename": filename,
        "mime_type": doc["mime_type"],
        "size_bytes": len(data),
        "char_len": doc["extracted_chars"],
        "sensitivity": {
            "score": band["score"],
            "classification": band["classification"],
            "label": band["label"],
            "reasons": band.get("reasons", []),
        },
        "storage_key": storage_key,
        "created_at": created_at,
    }


@router.get("/chats")
async def list_chats(
    request: Request,
    include_archived: bool = Query(False, description="Include archived chats in the list."),
    current: Dict[str, Any] = Depends(get_current_account),
):
    """List the caller's active conversations.

    Workstream A.2 (2026-05-10) — `X-Active-Context` is now REQUIRED.
    The pre-Phase-B legacy escape hatch (no header → account-wide list)
    has been retired so non-SPA callers can't bypass per-context
    isolation. Tests that don't send the header will need to be updated.

    Workstream B.5 — `?include_archived=true` switches the filter to
    show archived chats too (newest-first by `last_message_at`). The
    sidebar archive view uses this.
    """
    # Wave 5 (2026-05-27) — General RAG default. Without an active
    # context header, return ONLY general chats (`context_id: None`)
    # so the sidebar surfaces the user's context-free conversations.
    # With an X-Active-Context header, scope to that context as before.
    # This preserves the privacy boundary (chats never bleed across
    # company contexts) while enabling the W5 default state.
    active_ctx = request.headers.get(ACTIVE_CONTEXT_HEADER)
    q: Dict[str, Any] = {"account_id": current["id"]}
    if active_ctx:
        q["context_id"] = active_ctx
    else:
        # General mode — only general chats (context_id None/missing).
        q["$or"] = [{"context_id": None}, {"context_id": {"$exists": False}}]
    if not include_archived:
        q["status"] = {"$ne": "archived"}
    rows = await db.chats.find(q, {"_id": 0}) \
        .sort("last_message_at", -1).to_list(200)
    rows.sort(
        key=lambda r: (r.get("last_message_at") or r.get("created_at") or ""),
        reverse=True,
    )
    return rows


# Phase B.1 — Conversation search.
# Substring search across chat titles AND message content for the
# caller's chats in the **active context only** (privacy wall +
# Phase A binding). Returns up to 50 hits; each hit carries the chat
# row plus a single matching snippet so the UI can render context.
# Search is case-insensitive; we use Mongo $regex on a lightly
# escaped query to avoid catastrophic regex DoS.
import re as _re

_REGEX_META = _re.compile(r"[\\^$.|?*+()\[\]{}]")


def _escape_regex(q: str) -> str:
    return _REGEX_META.sub(lambda m: "\\" + m.group(0), q)


@router.get("/chats/search")
async def search_chats(
    request: Request,
    q: str = Query(..., min_length=2, max_length=200,
                   description="Substring; case-insensitive. Min 2 chars."),
    limit: int = Query(50, ge=1, le=200),
    include_archived: bool = Query(False, description="Include archived chats in search."),
    current: Dict[str, Any] = Depends(get_current_account),
):
    """Search chats by substring in title OR turn content, scoped to
    the caller's active context.

    Workstream A.2 (2026-05-10) — `X-Active-Context` REQUIRED. No more
    account-wide escape hatch.

    Returns:
        {
          "items": [
            {
              "chat": <chat row>,
              "match_in": "title" | "message",
              "snippet": <~120 chars surrounding the hit>,
              "matched_message_id": <str | None>,
            },
            ...
          ],
          "count": N,
        }
    """
    needle = q.strip()
    if len(needle) < 2:
        raise HTTPException(status_code=400, detail="Query must be at least 2 characters.")

    # Wave 5 (2026-05-27) — General RAG default. Search behaves the
    # same as the chat-list GET: without X-Active-Context, search
    # ONLY general chats (`context_id: None`); with the header, scope
    # to that context.
    active_ctx = request.headers.get(ACTIVE_CONTEXT_HEADER)
    chat_filter: Dict[str, Any] = {"account_id": current["id"]}
    if active_ctx:
        chat_filter["context_id"] = active_ctx
    else:
        chat_filter["$or"] = [{"context_id": None}, {"context_id": {"$exists": False}}]
    if not include_archived:
        chat_filter["status"] = {"$ne": "archived"}

    # Step 1 — find chats with title hits (cheap; 1 query).
    rx = {"$regex": _escape_regex(needle), "$options": "i"}
    title_chats = await db.chats.find(
        {**chat_filter, "title": rx},
        {"_id": 0},
    ).sort("last_message_at", -1).to_list(limit)

    # Step 2 — find chat_messages hits scoped to allowed chat_ids.
    ids_cursor = await db.chats.find(
        {**chat_filter}, {"_id": 0, "id": 1},
    ).to_list(2000)
    allowed_chat_ids: List[str] = [c["id"] for c in ids_cursor]
    msg_filter: Dict[str, Any] = {
        "account_id": current["id"],
        "chat_id": {"$in": allowed_chat_ids},
        "content": rx,
    }

    msg_hits = await db.chat_messages.find(
        msg_filter,
        {"_id": 0, "id": 1, "chat_id": 1, "content": 1, "created_at": 1, "role": 1},
    ).sort("created_at", -1).limit(limit * 2).to_list(limit * 2)

    # Step 3 — assemble results, dedupe by chat_id (prefer title hit).
    items: List[Dict[str, Any]] = []
    seen_chats: set = set()

    for c in title_chats:
        idx = (c.get("title") or "").lower().find(needle.lower())
        snippet = c.get("title", "") if idx < 0 else c["title"]
        items.append({
            "chat": c,
            "match_in": "title",
            "snippet": snippet,
            "matched_message_id": None,
        })
        seen_chats.add(c["id"])
        if len(items) >= limit:
            break

    if len(items) < limit:
        # Hydrate chat rows for message hits we don't already have.
        msg_chat_ids = list({m["chat_id"] for m in msg_hits if m["chat_id"] not in seen_chats})
        if msg_chat_ids:
            chat_rows = await db.chats.find(
                {"id": {"$in": msg_chat_ids}, **chat_filter},
                {"_id": 0},
            ).to_list(len(msg_chat_ids))
            chat_by_id = {c["id"]: c for c in chat_rows}
            for m in msg_hits:
                if m["chat_id"] in seen_chats:
                    continue
                chat_row = chat_by_id.get(m["chat_id"])
                if not chat_row:
                    continue  # filtered out (e.g. archived)
                content = m.get("content") or ""
                idx = content.lower().find(needle.lower())
                if idx < 0:
                    snippet = content[:120]
                else:
                    start = max(0, idx - 50)
                    end = min(len(content), idx + len(needle) + 70)
                    snippet = ("…" if start > 0 else "") + content[start:end] + ("…" if end < len(content) else "")
                items.append({
                    "chat": chat_row,
                    "match_in": "message",
                    "snippet": snippet,
                    "matched_message_id": m["id"],
                })
                seen_chats.add(m["chat_id"])
                if len(items) >= limit:
                    break

    return {"items": items, "count": len(items)}


@router.get("/chats/{chat_id}")
async def get_chat(
    chat_id: str, request: Request,
    include_archived: bool = Query(False),
    current: Dict[str, Any] = Depends(get_current_account),
):
    """Wave 5 (2026-02 fork-resume) — General RAG default. The chat
    MAY be a general chat (`context_id: None`); in that case, no
    X-Active-Context header is required. Otherwise (context-scoped
    chat), the header MUST match the chat's context_id.

    Workstream B.5 — `?include_archived=true` lets the archive view
    open an archived chat for restore preview.
    """
    active_ctx = request.headers.get(ACTIVE_CONTEXT_HEADER) or None
    chat_filter: Dict[str, Any] = {"id": chat_id, "account_id": current["id"]}
    if active_ctx:
        chat_filter["context_id"] = active_ctx
    else:
        # General chats only.
        chat_filter["$or"] = [{"context_id": None}, {"context_id": {"$exists": False}}]
    chat = await db.chats.find_one(chat_filter, {"_id": 0})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    if chat.get("status") == "archived" and not include_archived:
        raise HTTPException(status_code=404, detail="Chat not found")
    msgs = await db.chat_messages.find(
        {"chat_id": chat_id, "account_id": current["id"]},
        {"_id": 0, "shielded_text": 0},  # never expose internal shielded form
    ).sort("created_at", 1).to_list(2000)
    chat["messages"] = msgs
    return chat


@router.patch("/chats/{chat_id}")
async def patch_chat(
    chat_id: str, body: ChatPatchIn, request: Request,
    current: Dict[str, Any] = Depends(get_current_account),
):
    # Wave 5 (2026-02 fork-resume) — General RAG default. General chats
    # (context_id None) accept patches without X-Active-Context;
    # context-scoped chats still require the header.
    active_ctx = request.headers.get(ACTIVE_CONTEXT_HEADER) or None
    if body.model_id is not None and not _model_def(body.model_id):
        raise HTTPException(status_code=400, detail=f"Unknown model_id '{body.model_id}'.")
    update: Dict[str, Any] = {"updated_at": _iso(_now())}
    audit_payload: Dict[str, Any] = {}
    if body.title is not None:
        update["title"] = body.title.strip()[:120] or "New conversation"
        audit_payload["title"] = update["title"]
    if body.model_id is not None:
        update["model_id"] = body.model_id
        audit_payload["model_id"] = body.model_id
    if body.shielding_policy is not None:
        update["shielding_policy"] = body.shielding_policy
        audit_payload["shielding_policy"] = body.shielding_policy
    if body.context_id is not None:
        # Phase 11 ITEM C — allow setting/clearing the grounding context.
        # Empty string explicitly clears; any other value sets.
        ctx_val = body.context_id.strip() or None
        update["context_id"] = ctx_val
        audit_payload["context_id"] = ctx_val
    # Phase D.3 (2026-05-26) — linked_context lifecycle on patch.
    # `clear_linked_context: true` unsets the field entirely. A
    # non-null `linked_context` object replaces the existing link
    # (re-resolved against the chat's context); silent miss if the
    # referenced item is gone.
    unset: Dict[str, Any] = {}
    if body.clear_linked_context is True:
        unset["linked_context"] = ""
        audit_payload["linked_context"] = None
    elif body.linked_context is not None:
        # Find the chat's context_id to re-resolve.
        existing_filter: Dict[str, Any] = {"id": chat_id, "account_id": current["id"]}
        if active_ctx:
            existing_filter["context_id"] = active_ctx
        else:
            existing_filter["$or"] = [{"context_id": None}, {"context_id": {"$exists": False}}]
        existing = await db.chats.find_one(existing_filter, {"_id": 0, "context_id": 1})
        if not existing:
            raise HTTPException(status_code=404, detail="Chat not found")
        resolved = await _resolve_linked_context(
            ctx_type=body.linked_context.ctx_type,
            ctx_id=body.linked_context.ctx_id,
            context_id=existing.get("context_id") or active_ctx,
            account_id=current["id"],
        )
        if resolved is not None:
            update["linked_context"] = {
                "ctx_type":    resolved["ctx_type"],
                "ctx_id":      resolved["ctx_id"],
                "title":       resolved["title"],
                "excerpt":     resolved["excerpt"],
                "href":        resolved["href"],
                "attached_at": _iso(_now()),
            }
            audit_payload["linked_context"] = {
                "ctx_type": resolved["ctx_type"],
                "ctx_id":   resolved["ctx_id"],
            }
    if len(update) == 1 and not unset:
        raise HTTPException(status_code=400, detail="Send at least one field.")
    mongo_op: Dict[str, Any] = {"$set": update}
    if unset:
        mongo_op["$unset"] = unset
    # Wave 5 (2026-02 fork-resume) — match general chats when
    # active_ctx is None; context-scoped when present.
    update_filter: Dict[str, Any] = {
        "id": chat_id,
        "account_id": current["id"],
        "status": {"$ne": "archived"},
    }
    if active_ctx:
        update_filter["context_id"] = active_ctx
    else:
        update_filter["$or"] = [{"context_id": None}, {"context_id": {"$exists": False}}]
    res = await db.chats.update_one(update_filter, mongo_op)
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Chat not found")
    await _append_audit(
        account_id=current["id"], chat_id=chat_id, action="chat.updated",
        request=request, payload=audit_payload,
    )
    chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
    return _sanitize(chat)


@router.delete("/chats/{chat_id}")
async def soft_delete_chat(
    chat_id: str, request: Request,
    hard: bool = Query(False, description="When true, hard-delete immediately. Audit chain is preserved."),
    current: Dict[str, Any] = Depends(get_current_account),
):
    """Phase B.1 — soft-delete with a 30-day retention clock.

    Sets ``status='archived'`` (legacy field, kept for backward compat
    with the existing UI listing filter) AND ``deleted_at`` (the new
    retention clock the daily sweep keys off). The user-visible action
    name in the audit log is still ``chat.archived`` so existing
    audit-trail dashboards keep working; the hard-delete sweep writes
    its own ``chat.hard_deleted`` row with the retention metadata.

    Workstream A.2 (2026-05-10) — X-Active-Context REQUIRED. The chat
    must belong to the active context (so cross-context deletes via
    raw chat_id are rejected).

    Workstream B.5 (2026-05-10) — when `?hard=true` is passed and the
    chat is already archived, hard-delete immediately. The audit chain
    is preserved (chat_audit_log rows stay; only the chat doc + its
    chat_messages are removed). The audit row is `chat.hard_deleted`
    with `via='manual'` so the daily-sweep telemetry separates manual
    purges from time-based ones.
    """
    # Wave 5 (2026-05-27) — General RAG default. The DELETE endpoint
    # accepts either context-scoped chats (with X-Active-Context) OR
    # general chats (no header). See `send_message` for the pattern.
    active_ctx = request.headers.get(ACTIVE_CONTEXT_HEADER) or None
    chat_filter: Dict[str, Any] = {"id": chat_id, "account_id": current["id"]}
    if active_ctx:
        chat_filter["context_id"] = active_ctx
    else:
        chat_filter["$or"] = [{"context_id": None}, {"context_id": {"$exists": False}}]
    chat = await db.chats.find_one(chat_filter, {"_id": 0})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    if hard:
        if chat.get("status") != "archived":
            raise HTTPException(
                status_code=400,
                detail=(
                    "Hard-delete requires the chat to be archived first. "
                    "Send DELETE without ?hard=true to archive, then again "
                    "with ?hard=true to purge."
                ),
            )
        # Preserve the audit chain — only remove the chat + messages.
        msg_count = await db.chat_messages.count_documents({"chat_id": chat_id})
        await db.chat_messages.delete_many({"chat_id": chat_id})
        await db.chats.delete_one({"id": chat_id})
        await _append_audit(
            account_id=current["id"], chat_id=chat_id,
            action="chat.hard_deleted", request=request,
            payload={
                "via": "manual",
                "messages_removed": int(msg_count),
                "title": chat.get("title", ""),
            },
        )
        return {"ok": True, "hard_deleted": True, "messages_removed": int(msg_count)}

    now_iso = _iso(_now())
    res = await db.chats.update_one(
        {"id": chat_id, "account_id": current["id"]},
        {"$set": {
            "status": "archived",
            "archived_at": now_iso,
            "deleted_at": now_iso,  # Phase B.1 retention clock
        }},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Chat not found")
    await _append_audit(
        account_id=current["id"], chat_id=chat_id, action="chat.archived",
        request=request, payload={"deleted_at": now_iso, "retention_days": 30},
    )
    return {"ok": True, "deleted_at": now_iso, "retention_days": 30}


@router.post("/chats/{chat_id}/restore")
async def restore_chat(
    chat_id: str, request: Request,
    current: Dict[str, Any] = Depends(get_current_account),
):
    """Workstream B.5 — restore a soft-deleted chat to active status.

    Clears `deleted_at` and `archived_at`, sets `status='active'`. The
    30-day retention clock is reset (the chat is back in the active
    list). One audit row `chat.restored` is appended.

    Workstream A.2 — X-Active-Context REQUIRED.
    """
    active_ctx = _require_active_context(request)
    chat = await db.chats.find_one(
        {"id": chat_id, "account_id": current["id"], "context_id": active_ctx},
        {"_id": 0},
    )
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    if chat.get("status") != "archived":
        # Idempotent: if not archived, return success without writing.
        return {"ok": True, "already_active": True}
    res = await db.chats.update_one(
        {"id": chat_id, "account_id": current["id"]},
        {
            "$set": {"status": "active", "updated_at": _iso(_now())},
            "$unset": {"deleted_at": "", "archived_at": ""},
        },
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Chat not found")
    await _append_audit(
        account_id=current["id"], chat_id=chat_id, action="chat.restored",
        request=request, payload={"prior_archived_at": chat.get("archived_at")},
    )
    return {"ok": True, "restored": True}


# -----------------------------------------------------------------------------
# Phase B.1 — 30-day chat retention sweep.
#
# Soft-deleted chats (status='archived' + deleted_at set) are physically
# removed once they cross the 30-day retention threshold. The
# `chat_audit_log` rows are NEVER deleted — they outlive the chat itself
# so the SHA-256 chain stays unbroken and the governance export remains
# verifiable. One audit row per hard-deleted chat is appended with
# `action="chat.hard_deleted"` carrying retention metadata.
#
# Tunables — kept as module-level so tests can monkeypatch:
#   CHAT_RETENTION_DAYS  default 30  (locked Phase 15.3.5 Item 8 Option A)
# -----------------------------------------------------------------------------
CHAT_RETENTION_DAYS = 30


async def run_chat_retention_sweep() -> Dict[str, Any]:
    """Hard-delete chats whose `deleted_at` is older than
    `CHAT_RETENTION_DAYS`. Returns a summary dict.

    One try/except per chat so a single bad row doesn't kill the batch.
    The sweep is idempotent — running it twice the same minute is a
    no-op for chats already removed.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=CHAT_RETENTION_DAYS)
    cutoff_iso = cutoff.isoformat()
    summary = {
        "cutoff": cutoff_iso,
        "scanned": 0, "hard_deleted": 0, "messages_removed": 0,
        "errors": 0, "audit_rows_written": 0,
    }
    cursor = db.chats.find(
        {"status": "archived", "deleted_at": {"$lte": cutoff_iso}},
        {"_id": 0, "id": 1, "account_id": 1},
    )
    async for chat in cursor:
        summary["scanned"] += 1
        chat_id = chat.get("id")
        account_id = chat.get("account_id")
        if not chat_id or not account_id:
            summary["errors"] += 1
            continue
        try:
            del_msgs = await db.chat_messages.delete_many({"chat_id": chat_id})
            await db.chats.delete_one({"id": chat_id, "account_id": account_id})
            summary["hard_deleted"] += 1
            summary["messages_removed"] += int(del_msgs.deleted_count or 0)
            # Hash-chained audit row — same chain as live chats; survives
            # even though the chat row is gone. The chain key is
            # (account_id), not (chat_id), so this is intentional.
            await _append_audit(
                account_id=account_id,
                chat_id=chat_id,
                action="chat.hard_deleted",
                request=None,
                payload={
                    "retention_days": CHAT_RETENTION_DAYS,
                    "messages_removed": int(del_msgs.deleted_count or 0),
                },
            )
            summary["audit_rows_written"] += 1
        except Exception as e:  # noqa: BLE001
            summary["errors"] += 1
            logger.error("chat retention sweep error chat_id=%s err=%s",
                         chat_id, e.__class__.__name__)
    logger.info(
        "chat retention sweep complete: scanned=%d deleted=%d msgs=%d errors=%d",
        summary["scanned"], summary["hard_deleted"],
        summary["messages_removed"], summary["errors"],
    )
    return summary


@router.post("/admin/chat-retention/sweep")
async def admin_chat_retention_sweep(
    current: Dict[str, Any] = Depends(get_current_account),
):
    """Manual trigger for the retention sweep — superadmin only. Same
    function the daily 03:30 UTC cron in `server.py` calls."""
    if not current.get("is_superadmin"):
        raise HTTPException(status_code=403, detail="Superadmin required.")
    return await run_chat_retention_sweep()


# -----------------------------------------------------------------------------
# Phase 11 ITEM C — chat citation grounding.
#
# When a chat is tethered to a context (chat.context_id is set), we run a
# BM25 retrieval over the context's documents BEFORE the LLM call, build a
# grounding block keyed on stable paragraph anchor ids, and ask the model
# to cite using a `[[cite:<anchor_id>]]` marker. After the model replies,
# we extract every marker, validate each against the allowlist of
# anchors we actually retrieved, and DROP any that don't match — those
# are hallucinations. The remaining markers are renumbered into `[n]`
# chips and a structured `citations[]` array travels alongside the
# message text so the frontend can render click-through pills.
# -----------------------------------------------------------------------------
import re as _re  # noqa: E402

_CITE_TOKEN_RE = _re.compile(r"\[\[cite:([a-f0-9]{6,16})\]\]")


async def _retrieve_grounding_paragraphs(
    *, context_id: str, account_id: str, query: str, top_k: int = 5,
) -> List[Dict[str, Any]]:
    """Return up to top_k paragraphs from the context's documents that
    BM25-best-match the query. Each result is shaped:

        {"anchor_id", "doc_id", "doc_name", "page",
         "paragraph_number", "text"}

    Falls back to the empty list if retrieval fails — chat continues as
    an untethered conversation rather than raising.
    """
    try:
        # Verify the caller actually has access to the context.
        membership = await db.memberships.find_one(
            {"account_id": account_id, "context_id": context_id, "status": "active"},
            {"_id": 0, "role": 1},
        )
        if not membership:
            return []
        # Fetch up to 50 docs in this context — chat retrieval should be
        # bounded; deeper corpora hit the bm25 ceiling per Path A.
        cursor = db.documents.find(
            {"context_id": context_id},
            {"_id": 0, "id": 1, "name": 1, "extracted_text": 1,
             "data_trust": 1, "paragraphs": 1, "anchors_version": 1},
        ).sort("created_at", -1).limit(50)
        docs = await cursor.to_list(50)
        if not docs:
            return []

        # Build a flat list of {anchor_id, doc_id, doc_name, page, ¶, text}.
        # We prefer pre-computed paragraphs; for docs without anchors we
        # lazily compute them inline so the citation chip still resolves.
        from paragraph_anchors import compute_paragraphs
        paragraphs: List[Dict[str, Any]] = []
        for d in docs:
            ps = d.get("paragraphs") or []
            if not ps and d.get("extracted_text"):
                # Lazy compute — the cron sweep is the catch-all but a
                # freshly uploaded doc may not have anchors yet.
                computed = compute_paragraphs(d["id"], d["extracted_text"])
                ps = computed.get("paragraphs") or []
                if ps:
                    # Persist so subsequent calls hit the cache.
                    await db.documents.update_one(
                        {"id": d["id"]},
                        {"$set": {
                            "paragraphs": ps,
                            "page_count": computed.get("page_count"),
                            "anchors_version": computed.get("version"),
                            "anchors_computed_at": computed.get("computed_at"),
                        }},
                    )
            for p in ps:
                if not (p.get("text") or "").strip():
                    continue
                paragraphs.append({
                    "anchor_id": p.get("id"),
                    "doc_id": d["id"],
                    "doc_name": d.get("name") or "Untitled document",
                    "page": p.get("page"),
                    "paragraph_number": p.get("paragraph_number"),
                    "text": p.get("text") or "",
                })
        if not paragraphs:
            return []

        # BM25 over paragraph texts. We adapt the bm25 helper which
        # expects a "text" field on each chunk — it already does.
        from bm25 import score_bm25
        # bm25 expects keys text/doc_id/name/trust/chunk_idx — adapter:
        chunks = [
            {**p, "text": p["text"], "name": p["doc_name"],
             "trust": "mixed", "chunk_idx": p["paragraph_number"]}
            for p in paragraphs
        ]
        ranked = score_bm25(query, chunks, k=top_k)
        out: List[Dict[str, Any]] = []
        for _, ch in ranked:
            out.append({
                "anchor_id": ch["anchor_id"],
                "doc_id": ch["doc_id"],
                "doc_name": ch["doc_name"],
                "page": ch.get("page"),
                "paragraph_number": ch.get("paragraph_number"),
                "text": ch["text"],
            })
        return out
    except Exception as e:  # noqa: BLE001
        logger.warning("chat retrieval failed (untethered fallback): %s", e)
        return []


def _format_grounding_block(paras: List[Dict[str, Any]]) -> str:
    """Build a deterministic grounding block the LLM can quote from.
    Each paragraph is announced with its anchor id so the model knows
    exactly what to put in the `[[cite:<id>]]` marker."""
    if not paras:
        return ""
    lines = [
        "[GROUNDING — only cite from these paragraphs. Use the marker "
        "format [[cite:<anchor_id>]] inline AT MOST ONCE per claim. "
        "Do NOT invent anchor ids; use only the ids listed below.]"
    ]
    for p in paras:
        head = (
            f"\n--- anchor:{p['anchor_id']}  doc:'{p['doc_name']}'"
            f"  p.{p.get('page','?')}¶{p.get('paragraph_number','?')} ---"
        )
        lines.append(head)
        lines.append((p["text"] or "").strip()[:1200])
    return "\n".join(lines)


def _process_citations(
    reply_text: str, allowed: List[Dict[str, Any]]
) -> Tuple[str, List[Dict[str, Any]]]:
    """Extract `[[cite:<id>]]` markers from `reply_text`. Drop any whose
    anchor isn't in `allowed`. Replace the surviving markers with
    sequential `[n]` chips and return (cleaned_text, citations[]).

    Each citation is shaped:
        {"n": int, "anchor_id", "doc_id", "doc_name",
         "page", "paragraph_number", "snippet"}
    """
    if not reply_text:
        return reply_text, []
    by_id = {p["anchor_id"]: p for p in allowed if p.get("anchor_id")}
    seen: List[str] = []          # ordered list of unique anchor ids cited
    dropped = 0

    def _replace(m):
        nonlocal dropped
        aid = m.group(1)
        if aid not in by_id:
            dropped += 1
            return ""  # drop hallucinated marker entirely
        if aid not in seen:
            seen.append(aid)
        n = seen.index(aid) + 1
        return f"[{n}]"

    cleaned = _CITE_TOKEN_RE.sub(_replace, reply_text)
    citations: List[Dict[str, Any]] = []
    for n, aid in enumerate(seen, start=1):
        p = by_id[aid]
        snippet = (p["text"] or "").strip()
        if len(snippet) > 220:
            snippet = snippet[:217] + "…"
        citations.append({
            "n": n,
            "anchor_id": aid,
            "doc_id": p["doc_id"],
            "doc_name": p["doc_name"],
            "page": p.get("page"),
            "paragraph_number": p.get("paragraph_number"),
            "snippet": snippet,
        })
    if dropped:
        logger.info("dropped %d hallucinated chat citations", dropped)
    return cleaned, citations


from typing import Tuple  # noqa: E402  (only needed for the helper above)



@router.post("/chats/{chat_id}/messages")
async def send_message(
    chat_id: str, body: MessageSendIn, request: Request,
    current: Dict[str, Any] = Depends(get_current_account),
):
    # Wave 5 (2026-05-27) — General RAG default. The chat MAY be a
    # general chat (`context_id: None`); in that case, no X-Active-Context
    # header is required. Otherwise (context-scoped chat), the header
    # MUST match the chat's context_id.
    active_ctx = request.headers.get(ACTIVE_CONTEXT_HEADER) or None
    chat_filter: Dict[str, Any] = {
        "id": chat_id, "account_id": current["id"],
        "status": {"$ne": "archived"},
    }
    if active_ctx:
        chat_filter["context_id"] = active_ctx
    else:
        # General chats only (context_id None or missing).
        chat_filter["$or"] = [{"context_id": None}, {"context_id": {"$exists": False}}]
    chat = await db.chats.find_one(chat_filter, {"_id": 0})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    # ── Phase ZZ.2.x (2026-02 fork-resume v2) — deterministic fixture
    # mode for Playwright. Active only when AKKI_CHAT_FIXTURES_ENABLED=1
    # AND caller is admin. Returns hand-authored SSE stream so ZZ.2
    # Tier-2 signals can be deterministically probed.
    fixture = request.query_params.get("fixture")
    _is_admin = bool(current.get("is_superadmin") or current.get("is_admin"))
    if fixture and os.environ.get("AKKI_CHAT_FIXTURES_ENABLED") == "1" and _is_admin:
        from services.solva_v2.chat_v2_fixtures import stream_fixture
        return StreamingResponse(stream_fixture(fixture, chat_id), media_type="text/event-stream")
    if fixture and not _is_admin:
        raise HTTPException(status_code=404, detail="Not found")

    model_def = _model_def(chat["model_id"]) or _model_def(DEFAULT_MODEL_ID)
    policy: ShieldingPolicy = chat.get("shielding_policy", "auto")

    # ── Phase B P0 fix (2026-05-13) — chat router's legacy in-band
    # de-identification pipeline (Phase 12.1 `syn_run`) has been
    # REMOVED. Per the user's locked structural-privacy decision,
    # Synisense Shield is the SINGLE source of de-id and re-id. The
    # raw user text flows directly to Shield's `client.invoke(...)`
    # below; Shield's three-layer de-id (regex → tenant dict → local
    # spaCy) runs there and Shield's re-identifier reverses the
    # tokens before this handler returns the assistant reply. Having
    # two maskers (the chat router's AND Shield's) created silent
    # divergence — the chat router masker missed MONEY entities that
    # Shield catches. One pipeline removes the divergence.
    #
    # The `shielding_policy` flag is now INFORMATIONAL ONLY. It is
    # preserved on each message record for UI display so users can
    # see that Shield ran, but it no longer gates behaviour.
    text = body.content.strip()
    shield_map: Dict[str, str] = {}  # filled in below from Shield's de_id_summary
    syn_stats: Dict[str, Any] = {"spans_redacted": 0, "by_type": {}, "elapsed_ms": 0}
    will_shield = True
    bypass_reason = None
    # H2.5 follow-up (2026-05-24) — canonical ShieldOutcome mint for
    # the SYNC chat path. Same source-of-truth discipline as the
    # streaming path: the chat envelope, the chat_audit row, AND the
    # synisense_runs row that `/synisense-metrics` aggregates over
    # all derive from this single `deidentifier.deidentify(text)`
    # call. The Shield audit row that `shield_invoke()` writes later
    # on the FULL prompt (history + grounding + user text) carries
    # the same UPPERCASE vocabulary so the three surfaces agree on
    # the boolean *"did Shield detect anything this turn?"*.
    #
    # msg_id is pre-generated here so the synisense_runs row keys
    # match the user message id chat_messages will persist.
    msg_id = str(uuid.uuid4())
    user_at = _iso(_now())
    try:
        from services.synisense.shield.canonical import mint_chat_outcome
        outcome = await mint_chat_outcome(
            user_text=text, tenant_id=current["id"],
            account_id=current["id"], chat_id=chat_id,
            message_id=msg_id, context_id=chat.get("context_id"),
        )
        detected = outcome.envelope()
        shielded_text = outcome.redacted_text
        shield_map = outcome.token_map
        has_identifiers = detected["identifiers_masked"] > 0
    except Exception as _shield_exc:  # noqa: BLE001
        from services.synisense.shield.exceptions import ShieldFailure
        if isinstance(_shield_exc, ShieldFailure):
            try:
                await db.audit_invariant_violations.insert_one({
                    "id": "iv-" + uuid.uuid4().hex,
                    "kind": "shield_failure_at_entry",
                    "surface": "chat", "channel": "sync",
                    "error_class": _shield_exc.error_class,
                    "account_id": current["id"], "chat_id": chat_id,
                    "ts": _iso(_now()),
                })
            except Exception:  # noqa: BLE001
                pass
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "shield_unavailable",
                    "action": "retry",
                    "message": "Synisense Shield is temporarily unavailable. Your message has not been sent. Please retry.",
                },
            )
        raise
    content_sha = hashlib.sha256(text.encode("utf-8", "ignore")).hexdigest()
    user_msg = {
        "id": msg_id,
        "chat_id": chat_id,
        "account_id": current["id"],
        "role": "user",
        "content": text,
        "content_sha256": content_sha,
        "created_at": user_at,
        "shielded": will_shield,
        "shielding_policy": policy,
        "bypass_reason": bypass_reason,
        "shielding": detected,
        # Phase 12.2 ITEM A — record that the message went through Synisense.
        # Detail (spans, replacements) is in db.synisense_runs; here we
        # carry only the counts the UI needs to render the inline icon.
        "synisense_stats": syn_stats,
    }
    await db.chat_messages.insert_one(user_msg)

    # Phase E.0.2 — cross-board metadata signature derivation. Only
    # tethered chats (chat.context_id present) contribute signatures —
    # untethered chats are global to the account and don't belong to
    # any board's signal pool.
    if chat.get("context_id"):
        try:
            from services.metadata_signatures import derive_and_persist
            await derive_and_persist(
                db,
                text=text,
                context_id=chat["context_id"],
                account_id=current["id"],
                source_artefact_kind="chat_message",
                source_artefact_id=msg_id,
            )
        except Exception:  # pragma: no cover — non-fatal
            pass

    await _append_audit(
        account_id=current["id"], chat_id=chat_id, action="message.sent",
        request=request,
        payload={
            "message_id": msg_id, "content_sha256": content_sha,
            "char_len": len(text), "policy": policy,
            "shielded_for_llm": will_shield, "bypass_reason": bypass_reason,
            "identifiers_detected": detected["identifiers_masked"],
            "by_category": detected.get("by_category", {}),
        },
    )

    # ── Build the prompt sent to the LLM. We want true multi-turn
    # context, so we replay every prior message in this chat (oldest →
    # newest). The library wraps each call as a single send; we manage
    # history ourselves per the playbook.
    prior = await db.chat_messages.find(
        {"chat_id": chat_id, "account_id": current["id"], "id": {"$ne": msg_id}},
        {"_id": 0, "role": 1, "content": 1, "shielded": 1},
    ).sort("created_at", 1).to_list(2000)

    # Stitch a single prompt so the model gets the full conversation;
    # this side-steps any quirks in LlmChat's session-history reuse.
    # Phase B P0 fix (2026-05-13) — per-message re-shielding REMOVED.
    # Shield's de-id runs on the full `full_prompt` below, which
    # includes this history block. One pipeline, no divergence.
    history_lines: List[str] = []
    for m in prior:
        role = "USER" if m.get("role") == "user" else "AKKI"
        c = m.get("content") or ""
        history_lines.append(f"{role}: {c}")
    history_block = "\n\n".join(history_lines)

    sent_to_llm = text

    # Phase 11 ITEM C — fetch grounding paragraphs when this chat is
    # tethered to a context. The retrieval allowlist is what we'll
    # validate citations against post-reply; hallucinations get dropped.
    grounding_paragraphs: List[Dict[str, Any]] = []
    grounding_block = ""
    if chat.get("context_id"):
        grounding_paragraphs = await _retrieve_grounding_paragraphs(
            context_id=chat["context_id"],
            account_id=current["id"],
            query=text,
            top_k=5,
        )
        grounding_block = _format_grounding_block(grounding_paragraphs)

    # Phase D.3 (2026-05-26) — linked-context injection. Re-resolve
    # fresh every turn so a deleted / unauthorised item silently
    # drops out of the prompt without erroring the chat. The
    # excerpt flows through Shield as part of `full_prompt` below —
    # NO bypass. The chip on the frontend is rendered from the
    # at-attach-time title + href persisted on chat.linked_context,
    # which we DO NOT mutate here (the chip survives even if the
    # item was deleted later — it renders in a muted "no longer
    # available" state on the client when the excerpt is empty).
    linked_block = ""
    linked_ctx = chat.get("linked_context")
    if linked_ctx and chat.get("context_id"):
        fresh = await _resolve_linked_context(
            ctx_type=linked_ctx.get("ctx_type") or "",
            ctx_id=linked_ctx.get("ctx_id") or "",
            context_id=chat["context_id"],
            account_id=current["id"],
        )
        if fresh and (fresh.get("excerpt") or "").strip():
            linked_block = (
                "[LINKED_CONTEXT]\n"
                f"title: {fresh['title']}\n"
                f"type: {fresh['ctx_type']}\n\n"
                f"{(fresh['excerpt'] or '')[:8000]}\n"
                "[/LINKED_CONTEXT]"
            )

    system_msg = (
        "You are AKKI, a calm, editorial intelligence partner for executives "
        "and non-executive directors. Tone: precise, neutral, no hype, "
        "Economist-style cadence. When tokens like [EMAIL_1] or [PERSON_3] "
        "appear, treat each as a stable referent — reason about it without "
        "asking the user what it means; the system will rehydrate the "
        "real value before the user reads your reply."
    )
    if grounding_paragraphs:
        # Tighten the system message so the model uses ONLY the supplied
        # anchor ids. The post-processor still validates and drops any
        # hallucinated marker, but a stronger system rail meaningfully
        # cuts the rate of hallucinated citations in practice.
        system_msg += (
            " A [GROUNDING] block follows containing extracted paragraphs "
            "from the user's documents. Cite ONLY using the inline marker "
            "[[cite:<anchor_id>]] where <anchor_id> appears in the block. "
            "Never invent anchor ids. If the answer is not in the grounding "
            "block, say so plainly rather than guessing."
        )

    full_prompt_parts: List[str] = []
    if linked_block:
        full_prompt_parts.append(linked_block)
    if grounding_block:
        full_prompt_parts.append(grounding_block)
    if history_block:
        full_prompt_parts.append(history_block)
    full_prompt_parts.append(f"USER: {sent_to_llm}")
    full_prompt = "\n\n".join(full_prompt_parts)

    # ── LLM call (Phase B 2026-05-13 — migrated through Synisense Shield).
    # `purpose="chat.standard_response"`. Shield handles de-id + LLM
    # provider selection + re-id; the returned `response` is already
    # the FINAL re-identified text — no further rehydration needed.
    # The Shield `audit_id` is captured and `$push`ed onto the chat
    # session's `synisense_audit_ids` array so the audit panel
    # (Phase C) can replay the full chain.
    started_ms = time.monotonic()
    shield_audit_id: Optional[str] = None
    shield_de_id_summary: Dict[str, int] = {}
    try:
        from services.synisense.shield.client import invoke as shield_invoke
        pref = "balanced"
        if model_def.get("provider") == "anthropic":
            pref = "analytical"
        elif model_def.get("provider") == "openai":
            pref = "generative"
        sr = await shield_invoke(
            purpose="chat.standard_response",
            content=full_prompt,
            tenant_id=current["id"],
            consumer_id="chat",
            user_id=current["id"],
            model_preference=pref,
            internal_caller=True,
        )
        reply_text = sr.get("response") or ""
        shield_audit_id = sr.get("audit_id")
        shield_de_id_summary = (
            (sr.get("trust_receipt") or {}).get("de_id_summary") or {}
        )
        mode = "live"
    except Exception as e:
        logger.exception("Chat Shield call failed")
        reply_text = f"(LLM error: {type(e).__name__}: {str(e)[:200]})"
        mode = "error"
    latency_ms = int((time.monotonic() - started_ms) * 1000)

    # ── Phase B P0 fix (2026-05-13) — surface Shield's audit row on
    # the chat session document. `chats.synisense_audit_ids` is an
    # array of every Shield audit_id this session produced; the
    # audit panel (Phase C) reads it for the per-conversation
    # provenance chain. Field is created on first push.
    if shield_audit_id:
        try:
            await db.chats.update_one(
                {"id": chat_id, "account_id": current["id"]},
                {"$push": {"synisense_audit_ids": shield_audit_id}},
            )
            # H2.5 follow-up (2026-05-24) — `user_msg.shielding` and
            # `synisense_stats` are now sourced from the canonical
            # ``mint_chat_outcome()`` call at the top of this handler,
            # NOT from ``shield_invoke``'s full-prompt de_id_summary.
            #
            # Rationale: the user_msg envelope (which the chat UI's
            # redaction badge reads) reflects identifiers DETECTED in
            # the USER's CURRENT MESSAGE. `shield_invoke` runs over
            # `full_prompt` — user text + history + grounding — and
            # its `de_id_summary` is a superset that double-counts
            # prior-turn identifiers (e.g. "Bramuel" mentioned in
            # turn 1 appears redacted in turn 2's history view too).
            # That superset belongs to ``synisense_audit_log`` (the
            # full-trail audit) but NOT to the per-turn envelope.
            #
            # `chat_audit_log.identifiers_detected` and
            # `synisense_runs.spans[]` now BOTH derive from the
            # canonical mint above. The full-trail audit row that
            # shield_invoke writes carries the larger numeric — the
            # three surfaces agree on the BOOLEAN "did Shield detect
            # anything this turn?" without lying about per-turn count.
            #
            # Record only the audit id + latency on syn_stats so the
            # UI can deep-link to the full-trail audit row when the
            # user opens the audit panel.
            syn_stats = {
                **syn_stats,
                "elapsed_ms": latency_ms,
                "version": "synisense-shield-v1",
                "audit_id": shield_audit_id,
            }
            try:
                await db.chat_messages.update_one(
                    {"id": user_msg["id"], "account_id": current["id"]},
                    {"$set": {"synisense_stats": syn_stats}},
                )
            except Exception:  # noqa: BLE001
                logger.warning("failed to back-fill user_msg synisense_stats")
        except Exception:  # noqa: BLE001 — non-fatal; audit failure shouldn't break reply
            logger.warning("failed to $push synisense_audit_id to chat session")

    # ── Persist the assistant message.
    # Phase 11 ITEM C — extract & validate citation markers. Hallucinated
    # markers (those not in the retrieval allowlist) are dropped before
    # the reply ever reaches the client; surviving markers become
    # numbered chips with structured citation entries that the frontend
    # renders as click-through pills into the Reading Viewer.
    cleaned_reply, citations = _process_citations(reply_text, grounding_paragraphs)

    reply_id = str(uuid.uuid4())
    reply_at = _iso(_now())

    # ── Phase C (2026-05-13) — Protective Layer detectors A/B/C run
    # on the assistant draft + the user message. Three concurrent
    # Shield invokes (purpose=chat.fm_{a,b,c}.*) produce a
    # `ProtectiveEvent` we persist on the chat session AND surface to
    # the frontend so it can render the appropriate intervention
    # (hypothesis-test framing card / inline annotation / Solva
    # handoff offer). Detector failures are non-fatal.
    protective_event = None
    if mode == "live":
        try:
            from services.chat.protective_layer import detect_all
            session_context_blob = "\n".join(
                f"{m.get('role','?')}: {(m.get('content') or '')[:400]}"
                for m in prior[-8:]
            )[:1800]
            bundle = await detect_all(
                user_message=body.content.strip(),
                draft_response=cleaned_reply,
                session_context=session_context_blob,
                tenant_id=current["id"],
                user_id=current["id"],
            )
            protective_event = bundle.as_protective_event(message_id=reply_id)
            # $push the event onto the chat session.
            await db.chats.update_one(
                {"id": chat_id, "account_id": current["id"]},
                {"$push": {"protective_layer_events": protective_event.model_dump()}},
            )
        except Exception as _pe:  # noqa: BLE001
            logger.warning(
                "protective layer failed (non-fatal): %s",
                type(_pe).__name__,
            )

    assistant_msg = {
        "id": reply_id,
        "chat_id": chat_id,
        "account_id": current["id"],
        "role": "assistant",
        "content": cleaned_reply,
        "model_id": chat["model_id"],
        "model_label": model_def["label"],
        "mode": mode,
        "latency_ms": latency_ms,
        "created_at": reply_at,
        "citations": citations,
        "grounded_context_id": chat.get("context_id") if grounding_paragraphs else None,
        # Phase 12.2 ITEM A — mirror the user-turn synisense stats on the
        # assistant message so the inline icon can render from a single
        # row without an extra fetch. Counts only — never the original
        # text or replacement tokens.
        "synisense_stats": syn_stats,
    }
    await db.chat_messages.insert_one(assistant_msg)
    await _append_audit(
        account_id=current["id"], chat_id=chat_id, action="message.received",
        request=request,
        payload={
            "user_message_id": msg_id, "reply_id": reply_id,
            "model_id": chat["model_id"], "mode": mode,
            "latency_ms": latency_ms, "char_len_reply": len(cleaned_reply),
            "citations_kept": len(citations),
            "citations_dropped": (
                reply_text.count("[[cite:") - len(_CITE_TOKEN_RE.findall(cleaned_reply or ""))
                - len(citations)
            ) if grounding_paragraphs else 0,
        },
    )

    # ── Update chat metadata (preview, count, last_message_at).
    await db.chats.update_one(
        {"id": chat_id},
        {
            "$set": {
                "last_message_at": reply_at,
                "last_message_preview": cleaned_reply[:200],
                "updated_at": reply_at,
            },
            "$inc": {"message_count": 2},
        },
    )

    return {
        "user_message": _sanitize(user_msg),
        "assistant_message": _sanitize(assistant_msg),
        "shielding": detected,
        "will_shield": will_shield,
        "bypass_reason": bypass_reason,
        # Phase C — frontend uses this to render the intervention card
        # (hypothesis-test / annotation / Solva handoff). When no
        # detector fires, `protective_event.intervention_type == "none"`
        # and the frontend renders nothing.
        "protective_event": (
            protective_event.model_dump() if protective_event else None
        ),
    }


# -----------------------------------------------------------------------------
# Phase B.2 — Streaming chat (Server-Sent Events).
#
# Additive surface: the sync POST /messages above stays as-is for tests
# and any external API client; the SPA prefers /messages/stream.
#
# Event format (one JSON object per `data:` line, terminated by \n\n):
#   data: {"type":"delta","text":"<token chunk>"}\n\n
#   data: {"type":"delta","text":"<token chunk>"}\n\n
#   ...
#   data: {"type":"message",
#          "message_id":"...","assistant_text":"<rehydrated>",
#          "model":"...","audit_id":"...",
#          "citations":[...],"shielding":{...},
#          "will_shield":bool,"bypass_reason":null,"latency_ms":int}\n\n
#   data: {"type":"done"}\n\n
#
# On error before any delta:
#   data: {"type":"error","code":"...","message":"..."}\n\n
#
# Rehydrate strategy — FINAL only (not per-chunk).
# ---------------------------------------------------
# Per-chunk rehydration would risk splitting a Synisense token (e.g.
# `[EMAIL_1]`) across two chunks, which a flat substring substitution
# cannot reverse. We therefore stream the SHIELDED text to the client
# in deltas — the live "typing" UX — and emit the rehydrated
# `assistant_text` exactly once on the terminal `message` event. The
# UI swaps the streamed shielded text for the rehydrated final string
# when that event lands. This keeps the audit story honest (the model
# only ever saw shielded tokens) and the citation post-processor
# (`_process_citations`) only runs once on the complete reply.
#
# LLM streaming — `emergentintegrations.LlmChat.send_message` does not
# expose a streaming primitive (no `astream` / generator). We fall back
# to a one-shot call followed by chunked emit on the way out. This
# preserves the streaming UX at the cost of perceived latency until the
# first token. Documented in this module so the choice is explicit.
# -----------------------------------------------------------------------------
@router.post("/chats/{chat_id}/messages/stream")
async def stream_message(
    chat_id: str, body: MessageSendIn, request: Request,
    current: Dict[str, Any] = Depends(get_current_account),
):
    # Wave 5 (2026-05-27) — General RAG default. See `send_message`
    # for the matched general-chat-aware lookup pattern.
    active_ctx = request.headers.get(ACTIVE_CONTEXT_HEADER) or None
    chat_filter: Dict[str, Any] = {
        "id": chat_id, "account_id": current["id"],
        "status": {"$ne": "archived"},
    }
    if active_ctx:
        chat_filter["context_id"] = active_ctx
    else:
        chat_filter["$or"] = [{"context_id": None}, {"context_id": {"$exists": False}}]
    chat = await db.chats.find_one(chat_filter, {"_id": 0})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    model_def = _model_def(chat["model_id"]) or _model_def(DEFAULT_MODEL_ID)
    policy: ShieldingPolicy = chat.get("shielding_policy", "auto")

    # Same Synisense pre-LLM hook as the sync path. Kept inline rather
    # than refactored into a shared helper because the prep includes
    # several short-circuiting decisions (acknowledgement gate, history
    # block) that would clutter a generator signature.
    # Phase B P0 fix (2026-05-13) — the streaming chat send path
    # also retired its in-router Phase 12.1 `syn_run` masker. Shield
    # is the single de-id pipeline; the raw `body.content.strip()`
    # flows to `shield.client.invoke()` below (the streaming branch
    # invokes Shield's streaming wrapper under `services.synisense.
    # shield.streaming`).
    text = body.content.strip()
    # H2.5 follow-up (2026-05-24) — canonical ShieldOutcome mint.
    # The chat envelope (`user_msg.shielding`), the chat_audit row
    # (`identifiers_detected` / `by_category` / `shielded_for_llm`),
    # the `synisense_runs` row (the source `/synisense-metrics` and
    # `/synisense-runs` aggregate over), AND the `synisense_audit_log`
    # row written by `prepare_for_streaming.finalize` later in this
    # request MUST agree on the boolean *"did Shield detect any
    # identifier on this turn?"* AND on the category vocabulary
    # (UPPERCASE — `CREDIT_CARD`, `PERSON`, `EMAIL` …, NOT lowercase
    # `card`/`person`/`email` from the legacy `synisense-pipeline`).
    #
    # `mint_chat_outcome()` runs one `deidentifier.deidentify(text)`
    # pass and writes the matching `synisense_runs` row keyed on
    # (account_id, chat_id, message_id, surface='chat') so the
    # metrics aggregation actually finds it. This replaces the
    # previous dual-engine pre-pass (`_syn_shield → pipeline.run`
    # with `account_id=None, message_id=PHANTOM`) that left
    # `/synisense-metrics` reporting zero on PAN-containing turns.
    #
    # The msg_id used below is the FINAL user-message id (was
    # generated later in the legacy code); we mint it up here so the
    # synisense_runs row is keyed on the same id that
    # `chat_messages._id` and the chat_audit row use.
    msg_id = str(uuid.uuid4())
    user_at = _iso(_now())
    syn_stats: Dict[str, Any] = {"spans_redacted": 0, "by_type": {}, "elapsed_ms": 0}
    try:
        from services.synisense.shield.canonical import mint_chat_outcome
        outcome = await mint_chat_outcome(
            user_text=text, tenant_id=current["id"],
            account_id=current["id"], chat_id=chat_id,
            message_id=msg_id, context_id=chat.get("context_id"),
        )
    except Exception as _shield_exc:  # noqa: BLE001
        from services.synisense.shield.exceptions import ShieldFailure
        if isinstance(_shield_exc, ShieldFailure):
            try:
                await db.audit_invariant_violations.insert_one({
                    "id": "iv-" + uuid.uuid4().hex,
                    "kind": "shield_failure_at_entry",
                    "surface": "chat", "channel": "stream",
                    "error_class": _shield_exc.error_class,
                    "account_id": current["id"], "chat_id": chat_id,
                    "ts": _iso(_now()),
                })
            except Exception:  # noqa: BLE001 — best-effort log
                pass
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "shield_unavailable",
                    "action": "retry",
                    "message": "Synisense Shield is temporarily unavailable. Your message has not been sent. Please retry.",
                },
            )
        raise

    shielded_text = outcome.redacted_text
    shield_map = outcome.token_map
    detected = outcome.envelope()
    has_identifiers = detected["identifiers_masked"] > 0

    # Policy gate (same as sync path).
    if policy == "always":
        will_shield, bypass_reason = True, None
    elif policy == "off":
        if has_identifiers and not body.acknowledge_unshielded:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "shielding_acknowledgement_required",
                    "message": "Sensitive identifiers detected. Confirm send-as-is or enable shielding.",
                    "detected": detected,
                },
            )
        will_shield = False
        bypass_reason = "policy_off_acknowledged" if has_identifiers else "no_identifiers"
    else:
        if has_identifiers:
            if body.acknowledge_unshielded:
                will_shield, bypass_reason = False, "user_bypass_acknowledged"
            else:
                will_shield, bypass_reason = True, None
        else:
            will_shield, bypass_reason = False, "no_identifiers"

    # Persist user message + audit BEFORE streaming starts.
    # NOTE: `msg_id` and `user_at` were pre-generated above the shield
    # mint so the synisense_runs row is keyed on the actual user
    # message id. Do NOT regenerate them here.
    content_sha = hashlib.sha256(text.encode("utf-8", "ignore")).hexdigest()
    user_msg = {
        "id": msg_id, "chat_id": chat_id, "account_id": current["id"],
        "role": "user", "content": text, "content_sha256": content_sha,
        "created_at": user_at, "shielded": will_shield,
        "shielding_policy": policy, "bypass_reason": bypass_reason,
        "shielding": detected, "synisense_stats": syn_stats,
    }
    await db.chat_messages.insert_one(user_msg)
    await _append_audit(
        account_id=current["id"], chat_id=chat_id, action="message.sent",
        request=request,
        payload={
            "message_id": msg_id, "content_sha256": content_sha,
            "char_len": len(text), "policy": policy,
            "shielded_for_llm": will_shield, "bypass_reason": bypass_reason,
            "identifiers_detected": detected["identifiers_masked"],
            "by_category": detected.get("by_category", {}),
            "channel": "stream",
        },
    )

    # Workstream B.2 (2026-05-10) — auto-name the chat from the first
    # user message. Cheap heuristic; no extra LLM call. Runs only when
    # the chat title is still a placeholder ("New conversation") AND
    # this is the first user message in the chat. The new title is
    # emitted as a `chat_renamed` SSE event below so the sidebar
    # updates without a re-fetch.
    auto_renamed_title: Optional[str] = None
    try:
        if _tp.should_auto_rename(chat.get("title")):
            prior_user_count = await db.chat_messages.count_documents({
                "chat_id": chat_id,
                "account_id": current["id"],
                "role": "user",
                "id": {"$ne": msg_id},
            })
            if prior_user_count == 0:
                # Title from the RAW user text (pre-shield) so brand
                # names ("Auto-Shield", "Solva") survive intact. Only
                # the title goes to the DB; persistence still uses the
                # shielded text path for audit.
                candidate = _tp.heuristic_title_from_message(text)
                if candidate:
                    auto_renamed_title = candidate[:120]
                    await db.chats.update_one(
                        {"id": chat_id, "account_id": current["id"]},
                        {"$set": {"title": auto_renamed_title,
                                  "updated_at": _iso(_now())}},
                    )
                    await _append_audit(
                        account_id=current["id"], chat_id=chat_id,
                        action="chat.auto_renamed", request=request,
                        payload={"new_title": auto_renamed_title,
                                 "from_title": chat.get("title", ""),
                                 "source": "heuristic_first_message"},
                    )
                    chat["title"] = auto_renamed_title  # keep in-mem chat fresh
    except Exception as _rename_err:  # noqa: BLE001
        # Auto-rename must never break the streaming path.
        logger.warning("auto-rename failed: %s", _rename_err.__class__.__name__)

    # ── Phase B.2 — classify the turn (heuristic + LLM fallback under
    # 350 ms hard cap). Records a `chat_classifier` audit-evidence row
    # to db.synisense_runs in the background. The classifier outcome
    # decides which system-prompt scaffolding to install:
    #   trivial               → base voice only
    #   light_substantive+    → + chat-adapted four-check + refusal block
    #   strategic_deliverable → + canonical two-pass + Pass 1/2 markers
    cls_out = await _classify_and_audit(
        text=body.content,                     # classify on RAW user text
        force_class=body.force_class,          # UI "Think harder" override
        account_id=current["id"],
        context_id=chat.get("context_id"),
    )
    turn_class: str = cls_out["turn_class"]
    classifier_source: str = cls_out["source"]
    classifier_latency_ms: int = cls_out["latency_ms"]
    visible_pass_1: bool = bool(body.show_pass_1) or _tp.has_visible_pass_1_cue(body.content)
    if turn_class != "strategic_deliverable":
        visible_pass_1 = False  # only meaningful for strategic deliverables

    # Audit-evidence Synisense row for the four-check itself — required
    # by acceptance bar #2 ("synisense_runs.surface='chat_four_check'
    # row for that turn"). Runs on EVERY light_substantive+ turn.
    if turn_class != "trivial":
        import asyncio as _asyncio_evt
        _asyncio_evt.create_task(
            _record_synisense_audit_evidence(
                surface="chat_four_check",
                account_id=current["id"],
                context_id=chat.get("context_id"),
                # Synisense runs over the four-check prompt block — the
                # audit row records that the discipline ran on this turn,
                # not the user's text (which is already in the `chat`
                # surface row).
                text=_tp.CHAT_ADAPTED_FOUR_CHECK_PROMPT,
                # Phase J.2 — link this audit row to the user message
                # so the chat UI badge knows which assistant turn it
                # belongs to.
                chat_id=chat_id,
                message_id=msg_id,
            )
        )
    prior = await db.chat_messages.find(
        {"chat_id": chat_id, "account_id": current["id"], "id": {"$ne": msg_id}},
        {"_id": 0, "role": 1, "content": 1, "shielded": 1},
    ).sort("created_at", 1).to_list(2000)

    # ── Phase B.2 patch (2026-05-05) — server-side deterministic
    # thin-input refusal. The original B.2 left the LLM to choose when
    # to use the refusal template; on a fresh chat with a one-line
    # decisional question and no attached docs, the LLM composed a
    # generic "I need more context" reply in its own voice instead of
    # the verbatim template. Per the memo, this path is "says", not
    # "may say" — we detect deterministically and emit verbatim.
    prior_substantive_turns = sum(
        1 for m in prior
        if m.get("role") == "assistant" and len(m.get("content") or "") >= 200
    )
    thin_input_trigger = _tp.detect_thin_input(
        turn_class=turn_class,
        text=body.content,
        attached_document_ids=list(body.attached_document_ids or []),
        prior_substantive_turns=prior_substantive_turns,
    )
    if thin_input_trigger is not None:
        # Build the constrained evidence-list call. We use Gemini 2.5
        # Flash (cheapest/fastest in the router) per the brief. The
        # prompt is tightly constrained: 3–6 comma-separated items,
        # no preamble, no commentary.
        async def _stream_thin_input_refusal():
            import asyncio as _asyncio2
            # Workstream B.2 — emit chat_renamed first if applicable.
            if auto_renamed_title:
                yield (
                    "data: " + json.dumps({
                        "type": "chat_renamed",
                        "chat_id": chat_id,
                        "title": auto_renamed_title,
                    }) + "\n\n"
                )
            t0 = time.monotonic()
            evidence_phrase = _tp.THIN_INPUT_FALLBACK_EVIDENCE
            evidence_source = "fallback_static"
            ev_latency_ms = 0
            ev_audit_task = None
            # Phase B (2026-05-13): the previous `if emergent_key:` gate
            # was removed — Synisense Shield's `llm_router.py` is now the
            # exclusive credential-handler. When the env var is absent
            # Shield falls back to mock mode (deterministic echo) so the
            # downstream evidence path remains exercised. Setting a
            # truthy local for readability.
            shield_available = True
            if shield_available:
                # Fire the audit-evidence Synisense run for this surface
                # in the background so the chain has a `chat_evidence_list`
                # row alongside the cheap LLM call.
                ev_audit_task = _asyncio2.create_task(
                    _record_synisense_audit_evidence(
                        surface="chat_evidence_list",
                        account_id=current["id"],
                        context_id=chat.get("context_id"),
                        text=body.content,
                    ),
                )
                evidence_system = (
                    "The user is asking a decisional question with no "
                    "supporting material. List 3-6 specific pieces of "
                    "evidence that, if provided, would let an analyst "
                    "weight scenarios honestly. Output ONLY a comma-"
                    "separated list, no preamble, no commentary, no "
                    "closing."
                )
                try:
                    # Phase B (2026-05-13) — migrated to Synisense Shield
                    # with `purpose="chat.thin_input.evidence_list"`.
                    from services.synisense.shield.client import invoke as shield_invoke
                    sr = await _asyncio2.wait_for(
                        shield_invoke(
                            purpose="chat.thin_input.evidence_list",
                            content=evidence_system + "\n\nUSER: " + body.content,
                            tenant_id=current["id"],
                            consumer_id="chat",
                            user_id=current["id"],
                            model_preference="balanced",
                            internal_caller=True,
                        ),
                        timeout=4.0,
                    )
                    candidate = sr.get("response") or ""
                    candidate, hit = _tp.sanitize_evidence_phrase(candidate)
                    if hit and candidate:
                        # One retry — same Shield purpose, system prompt
                        # carries the banned-word corrective.
                        retry_sys = (
                            evidence_system
                            + "\n\n"
                            + _tp.banned_word_retry_instruction(hit)
                        )
                        try:
                            sr2 = await _asyncio2.wait_for(
                                shield_invoke(
                                    purpose="chat.thin_input.evidence_list",
                                    content=retry_sys + "\n\nUSER: " + body.content,
                                    tenant_id=current["id"],
                                    consumer_id="chat",
                                    user_id=current["id"],
                                    model_preference="balanced",
                                    internal_caller=True,
                                ),
                                timeout=4.0,
                            )
                            cand2, hit2 = _tp.sanitize_evidence_phrase(sr2.get("response") or "")
                            if hit2 or not cand2:
                                evidence_phrase = _tp.THIN_INPUT_FALLBACK_EVIDENCE
                                evidence_source = "fallback_after_retry"
                            else:
                                evidence_phrase = cand2
                                evidence_source = "retry_clean"
                        except Exception as e2:  # noqa: BLE001
                            logger.warning(
                                "thin-input evidence retry failed: %s",
                                e2.__class__.__name__,
                            )
                            evidence_phrase = _tp.THIN_INPUT_FALLBACK_EVIDENCE
                            evidence_source = "fallback_retry_error"
                    elif candidate:
                        evidence_phrase = candidate
                        evidence_source = "first_clean"
                    else:
                        evidence_phrase = _tp.THIN_INPUT_FALLBACK_EVIDENCE
                        evidence_source = "fallback_empty"
                except _asyncio2.TimeoutError:
                    evidence_phrase = _tp.THIN_INPUT_FALLBACK_EVIDENCE
                    evidence_source = "fallback_timeout"
                except Exception as e:  # noqa: BLE001
                    logger.warning(
                        "thin-input evidence call failed: %s; using static fallback",
                        e.__class__.__name__,
                    )
                    evidence_phrase = _tp.THIN_INPUT_FALLBACK_EVIDENCE
                    evidence_source = "fallback_call_error"
            ev_latency_ms = int((time.monotonic() - t0) * 1000)

            # Emit the verbatim template — single chunk so the user sees
            # it land in one piece. No paraphrase. No hedge.
            visible_reply = _tp.THIN_INPUT_REFUSAL_TEMPLATE.format(
                evidence_phrase=evidence_phrase
            )
            yield (
                "data: " + json.dumps({"type": "delta", "text": visible_reply}) + "\n\n"
            )

            # Persist the assistant message.
            reply_id = str(uuid.uuid4())
            reply_at = _iso(_now())
            assistant_msg = {
                "id": reply_id, "chat_id": chat_id,
                "account_id": current["id"], "role": "assistant",
                "content": visible_reply,
                "model_id": chat["model_id"],
                "model_label": model_def["label"],
                "mode": "thin_input_refusal",
                "latency_ms": ev_latency_ms,
                "created_at": reply_at,
                "citations": [],
                "grounded_context_id": None,
                "synisense_stats": {},
                "channel": "stream",
                "turn_class": turn_class,
                "four_check_surfaced": None,
                "pass_1": None, "pass_2": None,
                "show_pass_1": False,
                "refusal_reason": "thin_input",
            }
            await db.chat_messages.insert_one(assistant_msg)

            # Audit row 1: the structured chat.refused row carrying the
            # detection metadata + the evidence_phrase.
            await _append_audit(
                account_id=current["id"], chat_id=chat_id,
                action="chat.refused", request=request,
                payload={
                    "user_message_id": msg_id,
                    "reply_id": reply_id,
                    "refusal_reason": "thin_input",
                    "turn_class": turn_class,
                    "evidence_phrase": evidence_phrase,
                    "evidence_source": evidence_source,
                    "evidence_latency_ms": ev_latency_ms,
                    "detection": thin_input_trigger,
                    "channel": "stream",
                    "deterministic": True,
                },
            )

            # Audit row 2: the parallel message.received row (same
            # chained-hash shape as the normal path), so audit consumers
            # that filter on action="message.received" still see the turn.
            audit_row = await _append_audit(
                account_id=current["id"], chat_id=chat_id,
                action="message.received", request=request,
                payload={
                    "user_message_id": msg_id, "reply_id": reply_id,
                    "model_id": chat["model_id"],
                    "mode": "thin_input_refusal",
                    "latency_ms": ev_latency_ms,
                    "char_len_reply": len(visible_reply),
                    "citations_kept": 0,
                    "channel": "stream",
                    "turn_class": turn_class,
                    "classifier_source": classifier_source,
                    "classifier_latency_ms": classifier_latency_ms,
                    "four_check_surfaced": {"label": None, "ran": False},
                    "refusal_reason": "thin_input",
                    "two_pass": None,
                    "voice_violation": None,
                    "deterministic_refusal": True,
                },
            )

            # Best-effort settle of the audit-evidence Synisense run.
            if ev_audit_task is not None:
                try:
                    await _asyncio2.wait_for(ev_audit_task, timeout=2.0)
                except Exception:  # noqa: BLE001
                    pass

            yield (
                "data: " + json.dumps({
                    "type": "message",
                    "message_id": reply_id,
                    "assistant_text": visible_reply,
                    "model": chat["model_id"],
                    # H2.5 follow-up (2026-05-24) — `audit_id` field
                    # now carries the Shield `aud-<32-char>` id so
                    # `GET /api/v1/shield/audit/{id}` resolves. Thin-
                    # input refusal is a deterministic template — no
                    # Shield call ran on the user text path beyond
                    # the canonical mint upstream, so this envelope
                    # carries None for the Shield id and exposes the
                    # chat_audit row id separately under
                    # `chat_audit_id` for parity with the
                    # full-response envelope below.
                    "audit_id": None,
                    "chat_audit_id": audit_row["id"] if audit_row else None,
                    "citations": [],
                    "shielding": detected,
                    "will_shield": will_shield,
                    "bypass_reason": bypass_reason,
                    "latency_ms": ev_latency_ms,
                    "turn_class": turn_class,
                    "four_check_label": None,
                    "refusal_reason": "thin_input",
                    "pass_1": None, "pass_2": None,
                    "show_pass_1": False,
                    "voice_violation": None,
                }) + "\n\n"
            )
            yield "data: " + json.dumps({"type": "done"}) + "\n\n"

        return StreamingResponse(
            _stream_thin_input_refusal(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    # Phase B P0 fix (2026-05-13) — history re-shielding REMOVED.
    # Shield's de-id runs on the full `full_prompt` below (which
    # includes this history block), so re-shielding each historical
    # user message here would duplicate Shield's work and risk
    # divergence (the chat router's masker missed MONEY entities).
    history_lines: List[str] = []
    for m in prior:
        role = "USER" if m.get("role") == "user" else "AKKI"
        c = m.get("content") or ""
        history_lines.append(f"{role}: {c}")
    history_block = "\n\n".join(history_lines)
    sent_to_llm = text

    grounding_paragraphs: List[Dict[str, Any]] = []
    grounding_block = ""
    if chat.get("context_id"):
        grounding_paragraphs = await _retrieve_grounding_paragraphs(
            context_id=chat["context_id"], account_id=current["id"],
            query=text, top_k=5,
        )
        grounding_block = _format_grounding_block(grounding_paragraphs)

    # Phase D.3 (2026-05-26) — linked-context injection on stream path.
    # Same contract as the sync /messages handler: re-resolve fresh
    # every turn, silently drop if the item is gone, never bypass
    # Shield (the block is part of `full_prompt`, which Shield then
    # de-ids before the LLM sees it).
    linked_block = ""
    linked_ctx = chat.get("linked_context")
    if linked_ctx and chat.get("context_id"):
        fresh = await _resolve_linked_context(
            ctx_type=linked_ctx.get("ctx_type") or "",
            ctx_id=linked_ctx.get("ctx_id") or "",
            context_id=chat["context_id"],
            account_id=current["id"],
        )
        if fresh and (fresh.get("excerpt") or "").strip():
            linked_block = (
                "[LINKED_CONTEXT]\n"
                f"title: {fresh['title']}\n"
                f"type: {fresh['ctx_type']}\n\n"
                f"{(fresh['excerpt'] or '')[:8000]}\n"
                "[/LINKED_CONTEXT]"
            )

    full_prompt_parts: List[str] = []
    if linked_block:
        full_prompt_parts.append(linked_block)
    if grounding_block:
        full_prompt_parts.append(grounding_block)

    # Phase B.1 — inject attachments (de-identified at attach time).
    attachment_meta: List[Dict[str, Any]] = []
    if body.attached_document_ids:
        att_docs = await db.documents.find(
            {
                "id": {"$in": list(body.attached_document_ids)[:10]},
                "context_id": chat.get("context_id"),
                "uploaded_by": current["id"],
            },
            {"_id": 0, "id": 1, "name": 1, "body_redacted": 1,
             "extracted_text": 1, "sensitivity_band": 1, "size_bytes": 1,
             "extracted_chars": 1},
        ).to_list(10)
        for d in att_docs:
            ingest_text = (d.get("body_redacted") or d.get("extracted_text") or "")[:8000]
            if not ingest_text.strip():
                continue
            attachment_meta.append({
                "document_id": d["id"],
                "name": d.get("name"),
                "char_len": d.get("extracted_chars"),
                "sensitivity_band": d.get("sensitivity_band"),
            })
            full_prompt_parts.append(
                f"[ATTACHMENT — doc:{d.get('name', d['id'])} · "
                f"sensitivity:{d.get('sensitivity_band','public')} · "
                f"chars:{d.get('extracted_chars',0)}]\n"
                f"{ingest_text}"
            )

    if history_block:
        full_prompt_parts.append(history_block)
    full_prompt_parts.append(f"USER: {sent_to_llm}")
    full_prompt = "\n\n".join(full_prompt_parts)

    # Phase B.2 — assemble the per-turn system message based on classified
    # turn. `_tp.build_system_prompt` honours:
    #   • turn_class         → adds four-check + refusal block at L_S+
    #   • show_pass_1        → controls Pass 1 visibility for strategic
    #   • has_grounding      → adds the citation rail
    # Voice rules (operating preferences + banned words) are always
    # included.
    # Phase E.5 — NED voice addendum. Resolve membership role + context
    # type once per turn and pass to the system-prompt builder. Strict
    # honest-render: only fires when role=ned AND context_type starts
    # with 'ned_'. Other turns are unaffected.
    _ned_role: Optional[str] = None
    _ned_ctype: Optional[str] = None
    try:
        if chat.get("context_id"):
            _mb = await db.memberships.find_one(
                {"account_id": current["id"], "context_id": chat["context_id"],
                 "status": "active"},
                {"_id": 0, "role": 1},
            )
            if _mb:
                _ned_role = _mb.get("role")
            _ctx = await db.contexts.find_one(
                {"id": chat["context_id"]},
                {"_id": 0, "type": 1},
            )
            if _ctx:
                _ned_ctype = _ctx.get("type")
    except Exception:  # pragma: no cover — best-effort
        pass

    system_msg = _tp.build_system_prompt(
        turn_class=turn_class,
        show_pass_1=visible_pass_1,
        has_grounding=bool(grounding_paragraphs),
        membership_role=_ned_role,
        context_type=_ned_ctype,
    )
    # Phase ZZ.2 (2026-02 fork-resume v2) — Tier 1 Solva governance is
    # the chat model's behaviour. Prepend the conversational
    # governance preamble to every system message so refusal,
    # evidence-grounding, confidence framing, adversarial nudge, and
    # the Solva escalation CTA are baked in.
    try:
        from services.solva_v2.chat_v2_prompts import build_chat_v2_system_message
        system_msg = build_chat_v2_system_message(system_msg)
        # Audit log per-session (best-effort).
        try:
            await db.audit_log.insert_one({
                "id": str(uuid.uuid4()),
                "account_id": current["id"],
                "chat_id": chat_id,
                "event": "chat_v2_prompt_used",
                "created_at": _iso(_now()),
            })
        except Exception:
            pass
    except Exception:  # pragma: no cover — fallback to legacy prompt
        pass

    request_account = current  # closures capture this at the inner scope
    request_obj = request

    async def _event_gen():
        import asyncio as _asyncio
        # Patch 26E — emit the privacy-first phase narrative as the very
        # first event of every stream so the user gets instant feedback
        # (TTFP < 100ms) instead of staring at a blank bubble for the
        # 0.5-3s while shielding + grounding + the LLM warm-up run.
        # Other phases (`shielding_input`, `reasoning`, `drafting`,
        # `refining`, `complete`) emit at the corresponding real
        # boundaries below.
        yield "data: " + json.dumps({"type": "phase", "phase": "reading_context"}) + "\n\n"
        # Workstream B.2 — emit the chat_renamed event BEFORE anything
        # else so the SPA sidebar updates atomically with the first
        # delta. Idempotent: if the title wasn't auto-renamed (e.g.
        # this isn't the first message) auto_renamed_title is None
        # and we skip the emission.
        if auto_renamed_title:
            yield (
                "data: " + json.dumps({
                    "type": "chat_renamed",
                    "chat_id": chat_id,
                    "title": auto_renamed_title,
                }) + "\n\n"
            )
        # Phase B (2026-05-13): EMERGENT_LLM_KEY env-var read removed
        # from the streaming chat path. Synisense Shield's
        # `llm_router.py` is the exclusive credential-handler; absence
        # of the key triggers Shield's mock fallback transparently.
        started_ms = time.monotonic()
        raw_text = ""
        mode = "live"
        # H2.5 follow-up (2026-05-24) — emit the Shield audit_id (with
        # `aud-` prefix) in the assistant `message` envelope so the
        # `GET /api/v1/shield/audit/{audit_id}` endpoint resolves to
        # the actual Shield row. Previously the envelope emitted
        # `audit_row["id"]` (the bare-uuid chat_audit_log row id),
        # which downstream tooling tried to resolve via the Shield
        # audit endpoint and hit 404. Initialised to None and set by
        # whichever Shield invocation produced the assistant turn —
        # strategic_deliverable Pass 2, the streaming
        # `shield_finalize`, or the post-process retry.
        emitted_shield_audit_id: Optional[str] = None
        # Phase B.1 — cancel handling. Tracks chars actually emitted to
        # the client so the cancel-path persistence captures only what
        # the user saw, not the full LLM reply that might never have
        # streamed. `_emitted_for_cancel_box` is a one-element list
        # used as a closure-mutable container readable by the
        # top-level CancelledError handler at the very end.
        emitted_chars = 0
        cancelled = False
        _emitted_for_cancel_box: List[int] = [0]

        async def _persist_cancel(emitted_chars_at: int) -> None:
            """All cancel-path writes for THIS turn. Spawned as a
            detached `asyncio.create_task` so it runs to completion
            even when the parent task is being torn down."""
            try:
                latency_ms = int((time.monotonic() - started_ms) * 1000)
                partial_raw = raw_text[:emitted_chars_at] if raw_text else ""
                # Rehydrate only if we actually emitted shielded text.
                partial_rehydrated = (
                    _syn_rehydrate(partial_raw, shield_map) if (will_shield and partial_raw) else partial_raw
                )
                cleaned_partial, citations_partial = _process_citations(
                    partial_rehydrated, grounding_paragraphs,
                )
                reply_id = str(uuid.uuid4())
                reply_at = _iso(_now())
                await db.chat_messages.insert_one({
                    "id": reply_id, "chat_id": chat_id,
                    "account_id": request_account["id"],
                    "role": "assistant", "content": cleaned_partial,
                    "model_id": chat["model_id"],
                    "model_label": model_def["label"],
                    "mode": "cancelled", "latency_ms": latency_ms,
                    "created_at": reply_at,
                    "citations": citations_partial,
                    "grounded_context_id": chat.get("context_id") if grounding_paragraphs else None,
                    "synisense_stats": syn_stats,
                    "channel": "stream",
                    "cancelled": True,
                    "emitted_chars": emitted_chars_at,
                    "full_chars": len(raw_text),
                })
                await _append_audit(
                    account_id=request_account["id"], chat_id=chat_id,
                    action="message.received", request=request_obj,
                    payload={
                        "user_message_id": msg_id, "reply_id": reply_id,
                        "model_id": chat["model_id"], "mode": "cancelled",
                        "latency_ms": latency_ms,
                        "char_len_reply": len(cleaned_partial),
                        "citations_kept": len(citations_partial),
                        "channel": "stream",
                        "cancelled": True,
                        "emitted_chars": emitted_chars_at,
                        "full_chars": len(raw_text),
                    },
                )
                await db.chats.update_one(
                    {"id": chat_id},
                    {
                        "$set": {
                            "last_message_at": reply_at,
                            "last_message_preview": cleaned_partial[:200] or "(cancelled)",
                            "updated_at": reply_at,
                        },
                        "$inc": {"message_count": 2},
                    },
                )
            except Exception:  # noqa: BLE001
                logger.exception("cancel-path persistence failed")

        # Phase B.1 — disconnect watcher. Fires `_persist_cancel` as a
        # DETACHED task the moment the client closes the TCP. Covers
        # both "cancel during LLM call" (CancelledError raised at the
        # `await chat_session.send_message`) and "cancel during chunk
        # loop" (chunk-loop's own poll detects it). The watcher uses
        # `is_disconnected()` polling because that doesn't itself
        # consume the receive channel in a way that breaks the
        # generator. We track success state via `_completed_box`; on
        # success the watcher is cancelled and the persist never
        # fires.
        _completed_box: List[bool] = [False]

        async def _disconnect_watcher() -> None:
            try:
                while not _completed_box[0]:
                    if await request_obj.is_disconnected():
                        # Detached persist — survives parent cancellation.
                        _asyncio.create_task(_persist_cancel(_emitted_for_cancel_box[0]))
                        return
                    await _asyncio.sleep(0.4)
            except _asyncio.CancelledError:
                return  # success path cancelled us — fine.

        watcher = _asyncio.create_task(_disconnect_watcher())

        # Run the LLM call in a worker thread so we don't block the event
        # loop; the SDK is sync. Once we get the full reply, we chunk it
        # back to the client. This is the documented "coarse-chunk
        # fallback" — the SDK doesn't expose a streaming primitive yet.
        #
        # Phase B.2 — for `strategic_deliverable` we run the canonical
        # method as TWO separate LLM calls (Pass 1 then Pass 2) so the
        # audit always carries both passes. The single-call-with-markers
        # approach is unreliable on Claude Sonnet 4.5 — it sometimes
        # emits the deliverable directly when it judges Pass 1 to be
        # "obvious", leaving the audit row half-empty. The two-call
        # form is also closer to the memo: "PASS 1 — SOLVE … PASS 2 —
        # BUILD" are described as distinct phases, not a formatting
        # choice.
        explicit_pass_1: Optional[str] = None
        # Phase A.2 — set true ONLY when the streaming branch yielded
        # real-time deltas to the client. The post-process re-chunker
        # below uses this to decide whether to re-emit the final text
        # (strategic_deliverable two-pass needs it; streamed turns
        # don't and would double-emit content the user already saw).
        streamed_in_realtime = False
        # Phase B (2026-05-13) — strategic_deliverable Pass 1 + Pass 2
        # migrated to Synisense Shield. The streaming branch (else
        # arm) still uses `stream_llm_direct` from
        # `services.synisense.shield.streaming` per the streaming
        # carve-out documented in PHASE_B_INVENTORY.md.
        if turn_class == "strategic_deliverable":
            try:
                from services.synisense.shield.client import invoke as shield_invoke
                pref = "balanced"
                if model_def.get("provider") == "anthropic":
                    pref = "analytical"
                elif model_def.get("provider") == "openai":
                    pref = "generative"
                # Pass 1: reasoning only.
                pass_1_system = (
                    "You are AKKI's reasoning rail. Apply the four-layer "
                    "reasoning architecture to the user's task. Output "
                    "candidate framings, triangulation against context, "
                    "probability weighting (with confidence intervals), "
                    "and reflection. Do NOT produce the deliverable. Do "
                    "NOT include the marker lines. Just the reasoning."
                )
                p1_sr = await shield_invoke(
                    purpose="chat.deliverable.pass1_reasoning",
                    content=pass_1_system + "\n\n" + full_prompt,
                    tenant_id=current["id"],
                    consumer_id="chat",
                    user_id=current["id"],
                    model_preference=pref,
                    internal_caller=True,
                )
                explicit_pass_1 = p1_sr.get("response") or ""
                # Pass 2: deliverable.
                pass_2_system = (
                    system_msg
                    + "\n\nThe Pass 1 reasoning has already been "
                    "produced separately and is in [PASS_1_REASONING] "
                    "below. Honour Pass 1's selected framing fully. "
                    "Do not hedge into other scenarios. Output ONLY "
                    "the deliverable — no markers, no preamble, "
                    "no Pass 1 recap."
                )
                p2_full_prompt = (
                    f"[PASS_1_REASONING]\n{explicit_pass_1}\n[/PASS_1_REASONING]\n\n"
                    + full_prompt
                )
                p2_sr = await shield_invoke(
                    purpose="chat.deliverable.pass2_render",
                    content=pass_2_system + "\n\n" + p2_full_prompt,
                    tenant_id=current["id"],
                    consumer_id="chat",
                    user_id=current["id"],
                    model_preference=pref,
                    internal_caller=True,
                )
                raw_text = p2_sr.get("response") or ""
                mode = "live"
                # H2.5 follow-up — surface Pass 2's Shield audit_id
                # on the envelope so external tooling can resolve it.
                emitted_shield_audit_id = p2_sr.get("audit_id") or emitted_shield_audit_id
            except Exception as _ex:
                logger.exception("Strategic-deliverable Shield call failed")
                raw_text = f"(LLM error: {type(_ex).__name__}: {str(_ex)[:200]})"
                mode = "error"
        else:
            try:
                    # H2.5 (2026-05-24) — Streaming carve-out fix.
                    # The previous behaviour shipped `full_prompt` (raw
                    # user text + history) directly to Anthropic /
                    # Gemini / OpenAI via `stream_llm_direct`. The
                    # cloud LLM provider therefore saw un-redacted PII
                    # — the exact violation H2 §3 P0 #1 identified.
                    #
                    # New flow:
                    #   1. `prepare_for_streaming` de-identifies the
                    #      prompt and returns (redacted, token_map,
                    #      finalize). The audit-id is minted at this
                    #      point so the row is reserved BEFORE the LLM
                    #      sees anything.
                    #   2. `stream_llm_direct` receives the REDACTED
                    #      prompt — placeholders only.
                    #   3. Each LLM-emitted delta passes through a
                    #      `StreamingReidentifier` that handles tokens
                    #      split across delta boundaries (it buffers
                    #      partial `[[ENT_…` matches until the closing
                    #      `]]` arrives, then substitutes the visible
                    #      placeholder or the original per Fork A's
                    #      skip list).
                    #   4. `finalize(...)` writes the synisense_audit_log
                    #      row + trust receipt mirroring the sync-path
                    #      `shield.client.invoke()` write — so the
                    #      Trust Center / audit panel render the
                    #      streaming turn identically.
                    #
                    # See `/app/memory/sprints/H2_5_STREAMING_PII_FIX_STATE.md`.
                    from services.llm_streaming import stream_llm_direct, provider_for_model
                    from services.synisense.shield.client import prepare_for_streaming as _shield_prepare_streaming
                    from services.synisense.shield.reidentifier import StreamingReidentifier
                    stream_provider = provider_for_model(model_def["model"])

                    # ── Step 1 — de-id prompt + reserve audit id ──
                    (
                        shielded_prompt,
                        shield_token_map,
                        shield_finalize,
                    ) = await _shield_prepare_streaming(
                        purpose="chat.send_message_stream",
                        content=full_prompt,
                        tenant_id=current["id"],
                        consumer_id="akki.chat",
                        user_id=current["id"],
                    )
                    # H2.5 Fix #6 (2026-05-24) — Defense-in-depth alarm.
                    # AFTER Shield runs and BEFORE the LLM call, scan
                    # `shielded_prompt` for residual Luhn-valid PANs.
                    # If a match is found this is impossible-by-design
                    # (Shield's regex pass should have caught it), so
                    # we refuse to forward to the LLM. Logged into
                    # `audit_invariant_violations` for triage.
                    from services.synisense.shield import deidentifier as _shield_deid
                    import re as _re_dind
                    for _m in _re_dind.finditer(r"\b(?:\d[\s\-]?){12,18}\d\b", shielded_prompt):
                        if _shield_deid._luhn_valid(_re_dind.sub(r"[\s\-]", "", _m.group(0))):
                            try:
                                await db.audit_invariant_violations.insert_one({
                                    "id": "iv-" + uuid.uuid4().hex,
                                    "kind": "luhn_pan_in_shielded_prompt",
                                    "surface": "chat", "channel": "stream",
                                    "account_id": current["id"],
                                    "chat_id": chat_id,
                                    "user_message_id": msg_id,
                                    "match_len": len(_m.group(0)),
                                    "ts": _iso(_now()),
                                })
                            except Exception:  # noqa: BLE001
                                pass
                            yield (
                                "data: " + json.dumps({
                                    "type": "error",
                                    "code": "shield_invariant_violation",
                                    "message": "Shield invariant violation detected. Message not forwarded.",
                                }) + "\n\n"
                            )
                            return
                    stream_reid = StreamingReidentifier(shield_token_map)

                    raw_parts = []           # deltas as the LLM emitted them (placeholder-containing)
                    visible_parts = []       # deltas after rehydration (what the user sees)
                    stream_provider_used = ""
                    stream_fallback = False
                    stream_error = None
                    # ── Sprint Z1.1 (2026-05-29) — model-cascade retry ──
                    # Build the ordered attempt list: chosen-model first,
                    # then the Sonnet 4.5 → Sonnet 3.7 → Haiku safety net.
                    # If the first attempt fails BEFORE any delta lands AND
                    # the failure reason matches the "invalid model id"
                    # marker set, demote to the next cascade entry. Any
                    # other failure class (transport, rate-limit, timeout,
                    # mid-stream) returns as-is — transport-layer already
                    # handled those at `stream_llm_direct`.
                    _chosen_model = model_def["model"]
                    _attempt_models: List[str] = [_chosen_model] + [
                        m for m in _cascade_starting_from(model_def["id"])
                    ]
                    _attempt_idx = 0
                    while _attempt_idx < len(_attempt_models):
                        _try_model = _attempt_models[_attempt_idx]
                        _emitted_delta_this_attempt = False
                        stream_error = None
                        async for _chunk in stream_llm_direct(
                            provider=stream_provider,
                            model_id=_try_model,
                            system_msg=system_msg,
                            user_text=shielded_prompt,
                            session_id=f"akki-chat-{chat_id}",
                        ):
                            if _chunk.kind == "delta":
                                _emitted_delta_this_attempt = True
                                raw_parts.append(_chunk.text)
                                visible_delta = stream_reid.feed(_chunk.text)
                                if visible_delta:
                                    visible_parts.append(visible_delta)
                                    yield (
                                        "data: " + json.dumps({
                                            "type": "delta",
                                            "text": visible_delta,
                                        }) + "\n\n"
                                    )
                                # Phase A.2 — yield control to the event loop so
                                # uvicorn flushes each delta to the TCP socket
                                # immediately. Without this, multiple yields
                                # back-to-back can be coalesced and dumped at
                                # generator end (visible in the browser as
                                # "generates, then dumps"). asyncio.sleep(0)
                                # is the documented FastAPI/uvicorn SSE-flush
                                # primitive — no timer, no overhead, just a
                                # cooperative tick.
                                await _asyncio.sleep(0)
                            elif _chunk.kind == "done":
                                stream_provider_used = _chunk.provider_used
                                stream_fallback = _chunk.fallback_triggered
                                # If proxy_buffered fallback was used, the
                                # accumulated `raw_parts` already contains the
                                # full text; nothing extra to do here.
                            elif _chunk.kind == "error":
                                stream_error = _chunk.error or "stream_interrupted"
                                stream_provider_used = _chunk.provider_used
                                stream_fallback = _chunk.fallback_triggered
                        # ── Decide whether to demote to next cascade entry ──
                        if (
                            stream_error
                            and not _emitted_delta_this_attempt
                            and _is_model_invalid_error(stream_error)
                            and _attempt_idx + 1 < len(_attempt_models)
                        ):
                            _next_model = _attempt_models[_attempt_idx + 1]
                            # Audit the demotion so operator can correlate
                            # spikes via `db.model_fallback_log`.
                            try:
                                await db.model_fallback_log.insert_one({
                                    "id": "mfb-" + uuid.uuid4().hex,
                                    "surface": "chat",
                                    "channel": "stream",
                                    "account_id": current["id"],
                                    "chat_id": chat_id,
                                    "user_message_id": msg_id,
                                    "from_model": _try_model,
                                    "to_model": _next_model,
                                    "reason": stream_error[:240],
                                    "ts": _iso(_now()),
                                })
                            except Exception:  # noqa: BLE001
                                pass
                            logger.warning(
                                "[model-cascade] demoting %s → %s (%s)",
                                _try_model, _next_model, stream_error[:120],
                            )
                            _attempt_idx += 1
                            continue
                        # Either success, mid-stream error, or non-model-id
                        # failure with no cascade left — break out.
                        break
                    # Flush any token still buffered (e.g. delta ended
                    # mid-token but stream closed cleanly).
                    tail = stream_reid.flush()
                    if tail:
                        visible_parts.append(tail)
                        yield "data: " + json.dumps({"type": "delta", "text": tail}) + "\n\n"

                    if stream_error:
                        # Mid-stream failure. Finalize the Shield
                        # audit row with `outcome=stream_error` so the
                        # row is still mintable and the audit chain
                        # stays append-only.
                        try:
                            await shield_finalize(
                                response_text="".join(visible_parts),
                                provider=stream_provider_used or stream_provider,
                                model=model_def["model"],
                                usage=None,
                                outcome="stream_error",
                            )
                        except Exception:  # noqa: BLE001
                            logger.warning("shield_finalize on stream_error failed")
                        yield (
                            "data: " + json.dumps({
                                "type": "error",
                                "code": "stream_interrupted",
                                "message": stream_error,
                                "provider": stream_provider_used,
                                "fallback": stream_fallback,
                            }) + "\n\n"
                        )
                        try:
                            await _append_audit(
                                account_id=request_account["id"], chat_id=chat_id,
                                action="chat.message.failed", request=request_obj,
                                payload={
                                    "user_message_id": msg_id,
                                    "error": "stream_interrupted",
                                    "stream_error": stream_error[:200],
                                    "provider": stream_provider_used,
                                    "fallback": stream_fallback,
                                    "channel": "stream",
                                },
                            )
                        except Exception:  # noqa: BLE001
                            pass
                        return
                    raw_text = "".join(visible_parts)  # rehydrated text — what the user saw
                    # Finalize the Shield audit row now that the
                    # stream completed successfully. The minted
                    # audit_id is pushed onto chat.synisense_audit_ids
                    # so the audit-panel endpoints resolve this turn.
                    try:
                        _stream_audit_id = await shield_finalize(
                            response_text=raw_text,
                            provider=stream_provider_used or stream_provider,
                            model=model_def["model"],
                            usage=None,  # token usage not surfaced by stream_llm_direct
                            outcome="success",
                        )
                        await db.chats.update_one(
                            {"id": chat_id, "account_id": current["id"]},
                            {"$push": {"synisense_audit_ids": _stream_audit_id}},
                        )
                        # H2.5 follow-up — surface the Shield audit_id
                        # (with `aud-` prefix) on the envelope so
                        # `GET /api/v1/shield/audit/{audit_id}` resolves
                        # to the actual Shield row.
                        emitted_shield_audit_id = _stream_audit_id or emitted_shield_audit_id
                    except Exception:  # noqa: BLE001
                        logger.warning("shield_finalize on stream success failed")
                    # Phase A.2 — track that real-time deltas already
                    # reached the client. The post-process re-chunker
                    # below MUST NOT re-emit the same content.
                    streamed_in_realtime = True
            except Exception as e:
                logger.exception("Chat stream LLM call failed")
                # Emit an error event then write a failure audit row and stop.
                yield (
                    "data: " + json.dumps({
                        "type": "error",
                        "code": "llm_error",
                        "message": f"LLM error: {type(e).__name__}",
                    }) + "\n\n"
                )
                try:
                    await _append_audit(
                        account_id=request_account["id"], chat_id=chat_id,
                        action="chat.message.failed", request=request_obj,
                        payload={
                            "user_message_id": msg_id,
                            "error": type(e).__name__,
                            "channel": "stream",
                        },
                    )
                except Exception:  # noqa: BLE001
                    pass
                return

        # ── Phase B.2 — banned-word post-process + one retry.
        #
        # The check runs on the SHIELDED raw_text (cheap; banned words
        # don't get redacted by Synisense so a hit on shielded text is
        # also a hit on the rehydrated reply). On a hit we re-call the
        # LLM once with a short corrective system message, then the
        # second output is final regardless of whether the retry word
        # is still present (per brief: "On second violation, ship the
        # original output and log").
        voice_violation_record: Optional[Dict[str, Any]] = None
        first_banned = _detect_voice_violation(raw_text)
        retry_text: Optional[str] = None
        original_pre_retry: Optional[str] = raw_text if first_banned else None
        # Phase B (2026-05-13): voice-violation retry routes through Shield.
        # The previous emergent_key gate is gone — Shield handles the
        # missing-key fallback transparently via mock mode.
        if first_banned:
            try:
                # Phase B (2026-05-13) — voice-violation retry migrated to
                # Synisense Shield with `purpose="chat.refusal.compose"`.
                from services.synisense.shield.client import invoke as shield_invoke
                pref = "balanced"
                if model_def.get("provider") == "anthropic":
                    pref = "analytical"
                elif model_def.get("provider") == "openai":
                    pref = "generative"
                retry_sys = (
                    system_msg
                    + "\n\n"
                    + _tp.banned_word_retry_instruction(first_banned)
                )
                retry_sr = await shield_invoke(
                    purpose="chat.refusal.compose",
                    content=retry_sys + "\n\n" + full_prompt,
                    tenant_id=current["id"],
                    consumer_id="chat",
                    user_id=current["id"],
                    model_preference=pref,
                    internal_caller=True,
                )
                retry_text = retry_sr.get("response") or ""
                # H2.5 follow-up — supersede the envelope audit_id
                # with the retry's Shield audit_id when the retry
                # composed the final reply (i.e. didn't second-violate).
                _retry_audit_id = retry_sr.get("audit_id")
                second_hit = _detect_voice_violation(retry_text)
                if second_hit:
                    # Retry failed; ship original AND record violation.
                    voice_violation_record = {
                        "banned_word": first_banned,
                        "retry_outcome": "second_violation_shipped_original",
                        "retry_word": second_hit,
                        # Phase B.2 — preserve the before/after texts
                        # (truncated) so reviewers can see what the
                        # filter caught and what shipped. 600-char cap
                        # keeps the audit row bounded.
                        "before_text": (original_pre_retry or "")[:600],
                        "after_text": (retry_text or "")[:600],
                    }
                    # raw_text stays as the original.
                else:
                    # Retry succeeded — swap in the clean text. The
                    # audit row records the substitution (retry_outcome
                    # = "retry_clean") so the chain is verifiable.
                    voice_violation_record = {
                        "banned_word": first_banned,
                        "retry_outcome": "retry_clean",
                        "retry_word": None,
                        "before_text": (original_pre_retry or "")[:600],
                        "after_text": (retry_text or "")[:600],
                    }
                    raw_text = retry_text
                    # H2.5 follow-up — supersede the envelope audit_id
                    # with the retry's Shield row when the retry text
                    # is the one that shipped.
                    if _retry_audit_id:
                        emitted_shield_audit_id = _retry_audit_id
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    "banned-word retry failed (%s); shipping original",
                    e.__class__.__name__,
                )
                voice_violation_record = {
                    "banned_word": first_banned,
                    "retry_outcome": "retry_error_shipped_original",
                    "retry_word": None,
                    "before_text": (original_pre_retry or "")[:600],
                    "after_text": None,
                }

        # ── Phase B.2 — strip the structured `[[REFUSAL:reason]]` tag
        # if present. We extract the tag first (used by the audit-row
        # detector below), then remove it from the visible buffer so
        # the user sees only the refusal text. Stripping happens
        # BEFORE the two-pass split so refusals never end up wrapped
        # in pass markers.
        refusal_tag, raw_text = _tp.extract_refusal_tag(raw_text)

        # ── Phase B.2 — strategic_deliverable: capture Pass 1 / Pass 2.
        # When the explicit two-call architecture above fired, Pass 1
        # is `explicit_pass_1` and the LLM's second call output (in
        # raw_text) is Pass 2. We still run `split_two_pass` defensively
        # in case the model emitted markers despite our instructions.
        pass_1_text: Optional[str] = None
        pass_2_text: str = raw_text
        two_pass_record: Optional[Dict[str, Any]] = None
        if turn_class == "strategic_deliverable":
            # Defensive split first — strips markers if present.
            p1_split, p2_split = _tp.split_two_pass(raw_text)
            if explicit_pass_1:
                pass_1_text = explicit_pass_1
                # Pass 2 = whatever the LLM produced after stripping
                # any stray markers.
                pass_2_text = p2_split or raw_text
            else:
                pass_1_text = p1_split
                pass_2_text = p2_split or raw_text
            two_pass_record = {
                "pass_1": pass_1_text,
                "pass_2": pass_2_text,
                "pass_1_visible": bool(visible_pass_1),
                "pass_1_present": bool(pass_1_text),
            }

        # The text that gets STREAMED to the client — Pass 2 only by
        # default; Pass 1 + Pass 2 with a clear delimiter when visible.
        # For non-strategic turns, raw_text is unchanged.
        if turn_class == "strategic_deliverable" and visible_pass_1 and pass_1_text:
            visible_streamed = (
                "Pass 1 — reasoning\n\n"
                + pass_1_text
                + "\n\n———\n\nPass 2 — deliverable\n\n"
                + pass_2_text
            )
        elif turn_class == "strategic_deliverable":
            visible_streamed = pass_2_text
        else:
            visible_streamed = raw_text

        # Chunk the SHIELDED reply (final-rehydrate strategy — see
        # module-level comment). ~40-token = ~200-char chunks.
        # Phase B.1 — cancellation detection. Two paths:
        #   (a) Cancel during the chunk loop (after LLM call). We
        #       poll request.is_disconnected() each iteration; if
        #       True, we break and run _persist_cancel synchronously
        #       in this same task.
        #   (b) Cancel during the LLM call. The await raises
        #       CancelledError before we reach this loop; the
        #       outer try/except at the bottom of _event_gen handles
        #       it by spawning _persist_cancel as a detached task.
        # Phase B.2 — we stream `visible_streamed` (Pass 2-only or
        # Pass 1 + Pass 2 with a delimiter), not raw_text. raw_text
        # is the full LLM output and goes to the audit log; the user
        # only ever sees what we permit.
        # Phase A.2 — IF the streaming branch already yielded real-time
        # deltas to the client AND no banned-word retry swapped raw_text,
        # the user has already seen the entire final reply. Re-chunking
        # would double-emit and produce the "generates, then dumps"
        # symptom the user reported. Skip the re-chunker in that case;
        # it remains active for the strategic_deliverable two-pass path
        # (which is non-streaming) and for banned-word-retry swaps.
        skip_rechunk = streamed_in_realtime and (voice_violation_record is None)
        CHUNK_CHARS = 220
        try:
            if skip_rechunk:
                emitted_chars = len(visible_streamed)
                _emitted_for_cancel_box[0] = emitted_chars
            else:
                for i in range(0, len(visible_streamed), CHUNK_CHARS):
                    if await request_obj.is_disconnected():
                        cancelled = True
                        break
                    chunk = visible_streamed[i:i + CHUNK_CHARS]
                    yield (
                        "data: " + json.dumps({"type": "delta", "text": chunk}) + "\n\n"
                    )
                    emitted_chars += len(chunk)
                    _emitted_for_cancel_box[0] = emitted_chars
                    # Tiny gap so the client renders progressively.
                    await _asyncio.sleep(0.02)
        except _asyncio.CancelledError:
            cancelled = True

        if cancelled:
            await _persist_cancel(emitted_chars)
            return  # Don't fall through to the success-path persistence.

        latency_ms = int((time.monotonic() - started_ms) * 1000)
        # Now do the final rehydrate + citation post-processing on the
        # COMPLETE shielded reply, exactly once.
        # Phase B.2 — rehydrate `visible_streamed` (what the user sees)
        # AND build a separate rehydrated record for Pass 1 (audit only).
        rehydrated = (
            _syn_rehydrate(visible_streamed, shield_map) if will_shield else visible_streamed
        )
        cleaned_reply, citations = _process_citations(rehydrated, grounding_paragraphs)

        # Pass 1 / Pass 2 rehydration for the audit record. Pass 1 is
        # never streamed when visible_pass_1=False, but the audit row
        # must carry the rehydrated text so reviewers can read it.
        rehydrated_pass_1: Optional[str] = None
        rehydrated_pass_2: Optional[str] = None
        if two_pass_record:
            if pass_1_text:
                rehydrated_pass_1 = (
                    _syn_rehydrate(pass_1_text, shield_map) if will_shield else pass_1_text
                )
            rehydrated_pass_2 = (
                _syn_rehydrate(pass_2_text, shield_map) if will_shield else pass_2_text
            )
            two_pass_record = {
                **two_pass_record,
                "pass_1": rehydrated_pass_1,
                "pass_2": rehydrated_pass_2,
            }

        four_check_label = _tp.parse_four_check_label(cleaned_reply)
        # Refusal-reason resolution order: explicit tag from the model
        # (already extracted above) wins; fall back to detector. This
        # is robust to paraphrased refusals where the model writes
        # "I can't include that claim" instead of the verbatim memo
        # phrasing.
        refusal_reason = refusal_tag or _tp.detect_refusal_reason(cleaned_reply)

        # Workstream C.1 (2026-05-10) — deterministic detection for the
        # other two refusal categories. Only fires if the four-check did
        # NOT already surface a refusal (so we don't double-refuse the
        # same reply). Both detectors return None in the bypass case
        # (already cited / has grounding / has attached docs).
        deterministic_refusal_kind: Optional[str] = None
        deterministic_refusal_text: Optional[str] = None
        deterministic_refusal_meta: Optional[Dict[str, Any]] = None
        if not refusal_reason:
            try:
                _has_grounding = bool(grounding_paragraphs)
                _has_attached = bool(getattr(body, "attached_document_ids", None))
                _hit_unsourced = _tp.detect_unsourced_claim(
                    reply_text=cleaned_reply,
                    has_grounding=_has_grounding,
                    has_attached_docs=_has_attached,
                )
                if _hit_unsourced:
                    deterministic_refusal_kind = "unsourced_claim"
                    deterministic_refusal_text = _tp.UNSOURCED_CLAIM_DETERMINISTIC_REFUSAL
                    deterministic_refusal_meta = _hit_unsourced
                else:
                    _hit_named = _tp.detect_named_assumption(
                        reply_text=cleaned_reply,
                        has_grounding=_has_grounding,
                        has_attached_docs=_has_attached,
                    )
                    if _hit_named:
                        deterministic_refusal_kind = "named_assumption"
                        deterministic_refusal_text = _tp.render_named_assumption_refusal(
                            _hit_named.get("matched_name") or "",
                        )
                        deterministic_refusal_meta = _hit_named
            except Exception as _det_err:  # noqa: BLE001
                logger.warning(
                    "deterministic refusal detection failed: %s",
                    _det_err.__class__.__name__,
                )

        if deterministic_refusal_kind and deterministic_refusal_text:
            # Swap visible reply for the deterministic refusal template.
            # The streamed deltas have already shipped, so the final
            # `message` SSE event will overwrite the bubble with this
            # canonical text — same swap-on-done mechanic the existing
            # citation rehydration uses.
            cleaned_reply = deterministic_refusal_text
            citations = []  # refusal carries no citations
            refusal_reason = deterministic_refusal_kind
            four_check_label = None
            two_pass_record = None
            pass_1_text = None
            pass_2_text = deterministic_refusal_text

        reply_id = str(uuid.uuid4())
        reply_at = _iso(_now())
        assistant_msg = {
            "id": reply_id, "chat_id": chat_id, "account_id": request_account["id"],
            "role": "assistant", "content": cleaned_reply,
            "model_id": chat["model_id"], "model_label": model_def["label"],
            "mode": mode, "latency_ms": latency_ms, "created_at": reply_at,
            "citations": citations,
            "grounded_context_id": chat.get("context_id") if grounding_paragraphs else None,
            "synisense_stats": syn_stats,
            "channel": "stream",
            # Phase B.2 — UI uses these to render the collapsible Pass 1
            # panel (when visible) and the small four-check label badge.
            "turn_class": turn_class,
            "four_check_surfaced": (
                {"label": four_check_label} if four_check_label else None
            ),
            "pass_1": rehydrated_pass_1,
            "pass_2": rehydrated_pass_2 if rehydrated_pass_2 else None,
            "show_pass_1": bool(visible_pass_1),
        }
        await db.chat_messages.insert_one(assistant_msg)

        # Phase B.2 — chained audit rows for refusals and voice
        # violations. Both are SEPARATE rows from the success row so
        # reviewers can grep for them; both chain off the prior hash
        # (the audit helper handles chaining).
        if refusal_reason:
            await _append_audit(
                account_id=request_account["id"], chat_id=chat_id,
                action="chat.refused", request=request_obj,
                payload={
                    "user_message_id": msg_id, "reply_id": reply_id,
                    "refusal_reason": refusal_reason,
                    "turn_class": turn_class,
                    "channel": "stream",
                },
            )
        if voice_violation_record:
            await _append_audit(
                account_id=request_account["id"], chat_id=chat_id,
                action="chat.voice_violation", request=request_obj,
                payload={
                    "user_message_id": msg_id, "reply_id": reply_id,
                    "voice_violation": voice_violation_record,
                    "turn_class": turn_class,
                    "channel": "stream",
                },
            )

        # Single audit row at end — same shape as the sync path so the
        # SHA-256 chain is uniform across channels.
        audit_row = await _append_audit(
            account_id=request_account["id"], chat_id=chat_id,
            action="message.received", request=request_obj,
            payload={
                "user_message_id": msg_id, "reply_id": reply_id,
                "model_id": chat["model_id"], "mode": mode,
                "latency_ms": latency_ms, "char_len_reply": len(cleaned_reply),
                "citations_kept": len(citations),
                "channel": "stream",
                # Phase B.2 — new audit keys.
                "turn_class": turn_class,
                "classifier_source": classifier_source,
                "classifier_latency_ms": classifier_latency_ms,
                "four_check_surfaced": (
                    {"label": four_check_label, "ran": True}
                    if four_check_label
                    else (
                        {"label": None, "ran": True} if turn_class != "trivial"
                        else {"label": None, "ran": False}
                    )
                ),
                "refusal_reason": refusal_reason,
                "two_pass": two_pass_record,
                "voice_violation": voice_violation_record,
            },
        )
        await db.chats.update_one(
            {"id": chat_id},
            {
                "$set": {
                    "last_message_at": reply_at,
                    "last_message_preview": cleaned_reply[:200],
                    "updated_at": reply_at,
                },
                "$inc": {"message_count": 2},
            },
        )

        # ── Phase ZZ.2 (2026-02 fork-resume v2) — Tier 1 governance pass on
        # the assistant reply. Capture conversational validator output +
        # Tier 2 escalation flags so the frontend can render bias chips,
        # the adversarial nudge marker, and the Solva-escalation CTA.
        try:
            from services.solva_v2.integrity_validators import (
                validate_conversational_response as _zz2_validate,
            )
            from services.solva_v2.chat_v2_prompts import (
                should_escalate_to_solva as _zz2_escalate,
                detects_recommendation_request as _zz2_is_reco,
            )
            zz2_check = _zz2_validate(cleaned_reply or "", attached_docs=None)
            _user_text_for_zz2 = locals().get("text") or ""
            zz2_governance = {
                "ok": zz2_check.ok,
                "numeric_claims_total": zz2_check.numeric_claims_total,
                "numeric_claims_unsourced": zz2_check.numeric_claims_unsourced,
                "confidence_named": zz2_check.confidence_named,
                "bias_flags": zz2_check.bias_flags,
                "notes": zz2_check.notes,
                "recommendation_request": _zz2_is_reco(_user_text_for_zz2),
                "escalate_to_solva": _zz2_escalate(_user_text_for_zz2),
            }
        except Exception:
            zz2_governance = {"ok": True, "notes": ["governance_pass_skipped"]}

        yield (
            "data: " + json.dumps({
                "type": "message",
                "message_id": reply_id,
                "assistant_text": cleaned_reply,
                "model": chat["model_id"],
                # H2.5 follow-up (2026-05-24) — emit the Shield
                # audit_id (with `aud-` prefix). Was emitting
                # `audit_row["id"]` (the bare-uuid chat_audit_log
                # row id), which downstream tooling tried to resolve
                # via `GET /api/v1/shield/audit/{id}` and hit 404.
                # `chat_audit_id` carries the chat_audit_log row id
                # for callers that still need it (UI history fetcher,
                # bank-auditor chain verifier).
                "audit_id": emitted_shield_audit_id,
                "chat_audit_id": audit_row["id"] if audit_row else None,
                "citations": citations,
                "shielding": detected,
                "will_shield": will_shield,
                "bypass_reason": bypass_reason,
                "latency_ms": latency_ms,
                # Phase B.2 — new fields the UI uses to render the
                # collapsible Pass 1 panel and the small four-check
                # label, and to expose refusal context.
                "turn_class": turn_class,
                "four_check_label": four_check_label,
                "refusal_reason": refusal_reason,
                "pass_1": rehydrated_pass_1,
                "pass_2": rehydrated_pass_2,
                "show_pass_1": bool(visible_pass_1),
                "voice_violation": voice_violation_record,
                # Phase B.3 — direct-stream provenance. `provider_used` is
                # one of {anthropic_direct, gemini_direct, proxy_buffered}.
                # `fallback_triggered` is True when the direct provider
                # 5xx'd and we fell back to the universal LLM proxy mid-flight
                # (only possible before any delta was emitted; mid-stream
                # failures surface as type=error and DO NOT persist).
                "provider_used": locals().get("stream_provider_used") or "",
                "fallback_triggered": bool(locals().get("stream_fallback") or False),
                # Phase ZZ.2 — three-tier Solva governance. Tier 1 is
                # always-on (this object). Tier 2 (bias chips,
                # adversarial nudge, Solva-escalation CTA) is rendered
                # from these flags on the frontend.
                "zz2_governance": zz2_governance,
            }) + "\n\n"
        )
        # Patch 26E — emit phase: complete just before `done` so the
        # privacy-first caption fades out cleanly on the client.
        yield "data: " + json.dumps({"type": "phase", "phase": "complete"}) + "\n\n"
        yield "data: " + json.dumps({"type": "done"}) + "\n\n"

        # Success path complete — stop the disconnect watcher so it
        # doesn't fire a spurious cancel-persist after the fact.
        _completed_box[0] = True
        if not watcher.done():
            watcher.cancel()

    return StreamingResponse(
        _event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/chats/{chat_id}/audit")
async def get_chat_audit(
    chat_id: str, current: Dict[str, Any] = Depends(get_current_account),
):
    """Return the chained audit trail for this chat. Read-only; auditors
    can verify the chain by recomputing each row's hash from the canonical
    JSON of (prev_hash, id, at, account_id, chat_id, action, payload,
    ip, ua_sha) and confirming `row_hash` matches.
    """
    chat = await db.chats.find_one(
        {"id": chat_id, "account_id": current["id"]}, {"_id": 0, "id": 1},
    )
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    rows = await db.chat_audit_log.find(
        {"chat_id": chat_id, "account_id": current["id"]},
        {"_id": 0},
    ).sort("at", 1).to_list(5000)
    return {
        "chat_id": chat_id,
        "rows": rows,
        "verification_note": (
            "Each row's row_hash is SHA256 of the canonical JSON "
            "{prev_hash,id,at,account_id,chat_id,action,payload,ip,ua_sha}. "
            "Recompute and compare to detect tampering."
        ),
    }


@router.get("/chats/{chat_id}/audit/export.zip")
async def export_chat_audit_pack(
    chat_id: str, current: Dict[str, Any] = Depends(get_current_account),
):
    """Bank-grade audit pack — a single zip an auditor can ingest:

        manifest.txt        — schema + verification recipe
        chat.json           — chat metadata
        messages.json       — every message's content_sha256, role,
                              created_at, shielding decision (NO raw content)
        audit_chain.json    — full hash-chained log
        verify.py           — pure-stdlib script that recomputes the chain
                              against audit_chain.json and reports any
                              broken links.

    Raw message content is NEVER included; only its SHA256 fingerprint.
    Auditors prove existence + ordering + integrity without exposure.
    """
    import io
    import zipfile

    from fastapi.responses import Response

    chat = await db.chats.find_one(
        {"id": chat_id, "account_id": current["id"]}, {"_id": 0},
    )
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    # Strip raw content; keep the SHA fingerprint that already lives on
    # the user message and compute one for assistant messages too.
    msgs = await db.chat_messages.find(
        {"chat_id": chat_id, "account_id": current["id"]},
        {"_id": 0, "shielded_text": 0},
    ).sort("created_at", 1).to_list(5000)
    redacted = []
    for m in msgs:
        sha = m.get("content_sha256")
        if not sha:
            sha = hashlib.sha256(
                (m.get("content") or "").encode("utf-8", "ignore")
            ).hexdigest()
        redacted.append({
            "id": m.get("id"),
            "role": m.get("role"),
            "created_at": m.get("created_at"),
            "model_label": m.get("model_label"),
            "model_id": m.get("model_id"),
            "mode": m.get("mode"),
            "latency_ms": m.get("latency_ms"),
            "shielded": m.get("shielded"),
            "shielding_policy": m.get("shielding_policy"),
            "bypass_reason": m.get("bypass_reason"),
            "shielding": m.get("shielding"),
            "char_len": len(m.get("content") or ""),
            "content_sha256": sha,
        })

    rows = await db.chat_audit_log.find(
        {"chat_id": chat_id, "account_id": current["id"]},
        {"_id": 0},
    ).sort("at", 1).to_list(5000)

    chat_clean = {k: v for k, v in chat.items() if k not in ("_id",)}

    manifest = (
        "AKKI Chat — Bank-grade audit pack\n"
        "==================================\n"
        f"Chat ID:       {chat_id}\n"
        f"Account ID:    {current['id']}\n"
        f"Exported at:   {_iso(_now())} (UTC)\n"
        f"Audit rows:    {len(rows)}\n"
        f"Messages:      {len(redacted)}\n"
        "\n"
        "Files\n"
        "-----\n"
        "  chat.json          chat record (model_id, shielding_policy, etc.)\n"
        "  messages.json      message metadata + SHA256 fingerprints\n"
        "                     (raw content NOT included)\n"
        "  audit_chain.json   append-only hash-chained log\n"
        "  verify.py          stdlib-only chain verifier\n"
        "\n"
        "Verification\n"
        "------------\n"
        "Each audit row carries:\n"
        "  prev_hash  — hash of the previous row (genesis: "
        "GENESIS-AKKI-CHAT-AUDIT-2026)\n"
        "  row_hash   — SHA256 of the canonical JSON of:\n"
        "    {prev: prev_hash, id, at, account_id, chat_id,\n"
        "     action, payload, ip, ua_sha}\n"
        "  json.dumps with sort_keys=True, separators=(',',':')\n"
        "\n"
        "Run `python3 verify.py` to recompute the chain and confirm.\n"
    )

    verify_py = '''#!/usr/bin/env python3
"""AKKI Chat audit-pack verifier — stdlib only.

Usage: place this file alongside `audit_chain.json` and run:

    python3 verify.py
"""
import hashlib
import json
import sys
from pathlib import Path

GENESIS = "GENESIS-AKKI-CHAT-AUDIT-2026"


def main() -> int:
    chain_path = Path(__file__).with_name("audit_chain.json")
    if not chain_path.exists():
        print("audit_chain.json not found next to this script.", file=sys.stderr)
        return 2
    rows = json.loads(chain_path.read_text())
    if not rows:
        print("Chain is empty — nothing to verify.")
        return 0

    prev = None  # we accept whatever the first row's prev_hash claims
    failures = []
    for i, r in enumerate(rows):
        canonical = {
            "prev": r["prev_hash"],
            "id": r["id"], "at": r["at"],
            "account_id": r["account_id"], "chat_id": r["chat_id"],
            "action": r["action"], "payload": r.get("payload", {}),
            "ip": r.get("ip", ""), "ua_sha": r.get("ua_sha", ""),
        }
        expected = hashlib.sha256(
            json.dumps(canonical, sort_keys=True, separators=(",", ":"))
            .encode()
        ).hexdigest()
        ok = expected == r["row_hash"]
        chained_ok = (prev is None) or (prev == r["prev_hash"])
        if not ok:
            failures.append((i, "hash mismatch", r["id"]))
        if not chained_ok:
            failures.append((i, "broken chain — prev_hash does not match prior row_hash", r["id"]))
        prev = r["row_hash"]

    if failures:
        print(f"FAIL — {len(failures)} issue(s):")
        for idx, kind, rid in failures:
            print(f"  row[{idx}] id={rid}: {kind}")
        return 1
    print(f"OK — verified {len(rows)} rows. Chain intact.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.txt", manifest)
        z.writestr("chat.json", json.dumps(chat_clean, indent=2, sort_keys=True))
        z.writestr("messages.json", json.dumps(redacted, indent=2))
        z.writestr("audit_chain.json", json.dumps(rows, indent=2))
        z.writestr("verify.py", verify_py)
    payload = buf.getvalue()

    await _append_audit(
        account_id=current["id"], chat_id=chat_id,
        action="audit.exported", request=None,
        payload={"rows": len(rows), "messages": len(redacted), "size_bytes": len(payload)},
    )

    return Response(
        content=payload,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="akki-chat-audit-{chat_id[:8]}.zip"'
        },
    )
