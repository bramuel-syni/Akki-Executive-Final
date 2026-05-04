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

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from core import db, get_current_account  # noqa: E402
from core import now as _now, iso as _iso  # noqa: E402
from services.synisense import (
    shield_payload_async as _syn_shield,
    shielding_report as _syn_report,
    rehydrate as _syn_rehydrate,
)

logger = logging.getLogger("akki.chat")
router = APIRouter(prefix="/api")


# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------
ShieldingPolicy = Literal["auto", "always", "off"]

# Provider+model identifiers exposed to the user. Keep in sync with the
# Emergent LLM Key playbook.
SUPPORTED_MODELS: List[Dict[str, str]] = [
    {"id": "claude-sonnet-4-5",  "label": "Claude Sonnet 4.5",  "provider": "anthropic",
     "model": "claude-sonnet-4-5-20250929", "tone": "careful, long-form"},
    {"id": "claude-haiku-4-5",   "label": "Claude Haiku 4.5",   "provider": "anthropic",
     "model": "claude-haiku-4-5-20251001",  "tone": "fast, terse"},
    {"id": "gpt-5-2",            "label": "GPT-5.2",            "provider": "openai",
     "model": "gpt-5.2",                    "tone": "balanced, fast"},
    {"id": "gemini-2-5-pro",     "label": "Gemini 2.5 Pro",     "provider": "gemini",
     "model": "gemini-2.5-pro",             "tone": "research-heavy"},
    {"id": "gemini-2-5-flash",   "label": "Gemini 2.5 Flash",   "provider": "gemini",
     "model": "gemini-2.5-flash",           "tone": "fastest"},
]
DEFAULT_MODEL_ID = "claude-sonnet-4-5"


def _model_def(model_id: str) -> Optional[Dict[str, str]]:
    for m in SUPPORTED_MODELS:
        if m["id"] == model_id:
            return m
    return None


# -----------------------------------------------------------------------------
# Schemas
# -----------------------------------------------------------------------------
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


class ChatPatchIn(BaseModel):
    title: Optional[str] = Field(default=None, max_length=120)
    model_id: Optional[str] = None
    shielding_policy: Optional[ShieldingPolicy] = None
    context_id: Optional[str] = None  # set/clear grounding


class MessageSendIn(BaseModel):
    content: str = Field(min_length=1, max_length=20_000)
    # When `auto` policy + identifiers are detected + the user wants to
    # bypass shielding for this single message (rare), they set this.
    # We capture the bypass + acknowledgement in the audit log.
    acknowledge_unshielded: bool = False


# -----------------------------------------------------------------------------
# Audit log — bank-grade, append-only, hash-chained
# -----------------------------------------------------------------------------
def _sanitize(rec: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in rec.items() if k != "_id"}


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
    cid = str(uuid.uuid4())
    rec = {
        "id": cid,
        "account_id": current["id"],
        "title": (body.title or "New conversation").strip()[:120],
        "model_id": body.model_id,
        "shielding_policy": body.shielding_policy,
        "context_id": body.context_id,  # Phase 11 ITEM C — optional grounding
        "status": "active",
        "message_count": 0,
        "last_message_preview": "",
        "last_message_at": None,
        "created_at": _iso(_now()),
        "updated_at": _iso(_now()),
    }
    await db.chats.insert_one(rec)
    await _append_audit(
        account_id=current["id"], chat_id=cid, action="chat.created",
        request=request,
        payload={"model_id": body.model_id, "shielding_policy": body.shielding_policy,
                 "context_id": body.context_id},
    )
    return _sanitize(rec)


@router.get("/chats")
async def list_chats(current: Dict[str, Any] = Depends(get_current_account)):
    rows = await db.chats.find(
        {"account_id": current["id"], "status": {"$ne": "archived"}},
        {"_id": 0},
    ).sort("last_message_at", -1).to_list(200)
    # last_message_at can be None on a freshly-created empty chat — the
    # mongo sort puts those at the bottom of a desc sort. Re-sort with
    # a fallback to created_at so empty chats appear above ancient ones.
    rows.sort(
        key=lambda r: (r.get("last_message_at") or r.get("created_at") or ""),
        reverse=True,
    )
    return rows


@router.get("/chats/{chat_id}")
async def get_chat(chat_id: str, current: Dict[str, Any] = Depends(get_current_account)):
    chat = await db.chats.find_one(
        {"id": chat_id, "account_id": current["id"]}, {"_id": 0},
    )
    if not chat or chat.get("status") == "archived":
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
    if len(update) == 1:
        raise HTTPException(status_code=400, detail="Send at least one field.")
    res = await db.chats.update_one(
        {"id": chat_id, "account_id": current["id"], "status": {"$ne": "archived"}},
        {"$set": update},
    )
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
    current: Dict[str, Any] = Depends(get_current_account),
):
    """Phase B.1 — soft-delete with a 30-day retention clock.

    Sets ``status='archived'`` (legacy field, kept for backward compat
    with the existing UI listing filter) AND ``deleted_at`` (the new
    retention clock the daily sweep keys off). The user-visible action
    name in the audit log is still ``chat.archived`` so existing
    audit-trail dashboards keep working; the hard-delete sweep writes
    its own ``chat.hard_deleted`` row with the retention metadata.
    """
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
    chat = await db.chats.find_one(
        {"id": chat_id, "account_id": current["id"], "status": {"$ne": "archived"}},
        {"_id": 0},
    )
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    model_def = _model_def(chat["model_id"]) or _model_def(DEFAULT_MODEL_ID)
    policy: ShieldingPolicy = chat.get("shielding_policy", "auto")

    # ── Phase 12.2 / Phase A — Synisense pre-LLM hook (the only shield
    # path on this surface). The user's text flows through the
    # three-layer pipeline (regex → Presidio → LLM fallback) which
    # produces a redacted projection AND a span list we can use to
    # rebuild a process-local `{token: original}` map for rehydration
    # of the model's reply. The legacy in-process regex shield was
    # retired in Phase A.
    text = body.content.strip()
    original_text_for_shield = text
    syn_stats: Dict[str, Any] = {"spans_redacted": 0, "by_type": {}, "elapsed_ms": 0}
    shield_map: Dict[str, str] = {}
    shielded_text = text
    try:
        from services.synisense import run as syn_run
        from services.synisense.pipeline import current_version as _syn_version
        syn_out = await syn_run(
            text=text,
            context_id=chat.get("context_id") or "",
            surface="chat",
            mode="redact",
            account_id=current["id"],
        )
        shielded_text = syn_out["redacted_text"]
        # Phase A — chat keeps the redacted projection in `text` for
        # downstream prompt assembly (history block, system prompt) but
        # also retains an explicit `shielded_text` so the policy gate
        # logic below can decide whether to send the redacted or raw
        # version to the LLM. The shield_map reconstructed here lets
        # rehydrate(...) restore real values in the reply post-call.
        text = shielded_text
        spans = syn_out.get("spans") or []
        for s in spans:
            token = s.get("replacement")
            if not token:
                continue
            try:
                original = original_text_for_shield[int(s["start"]):int(s["end"])]
            except (KeyError, ValueError, TypeError):
                continue
            shield_map[token] = original
        # Build a stats summary safe to persist on the message record.
        by_type: Dict[str, int] = {}
        for s in spans:
            t = s.get("entity_type") or "UNKNOWN"
            by_type[t] = by_type.get(t, 0) + 1
        syn_stats = {
            "spans_redacted": len(spans),
            "by_type": by_type,
            "elapsed_ms": int(syn_out.get("stats", {}).get("elapsed_ms") or 0),
            # Phase 12.2 closeout BUG 3 — engine version was being read
            # from a non-existent field on the response stats; the engine
            # exposes it via `current_version()` at module level.
            "version": _syn_version(),
        }
        # Audit row per turn (no text, no spans, just counts + types).
        try:
            from core import write_audit
            await write_audit(
                context_id=chat.get("context_id"),
                account_id=current["id"],
                action="synisense.chat.ran",
                resource_type="chat_message",
                resource_id=None,
                metadata={
                    "surface": "chat",
                    "spans_redacted": len(spans),
                    "entity_types": list(by_type.keys()),
                    "elapsed_ms": syn_stats["elapsed_ms"],
                },
            )
        except Exception:  # noqa: BLE001
            pass
    except Exception as e:  # noqa: BLE001
        # Phase A — chat preserves the historical degradation contract:
        # if Synisense fails, the message still goes through unshielded
        # (with a loud warn). Solva v2 surfaces use the strict adapter
        # at services.solva_v2.llm_adapter.shielded_call which DOES
        # refuse on the same condition. Future hardening could promote
        # chat to the strict path if ops sees zero degraded calls in
        # production.
        logger.warning(
            "synisense chat hook failed (degraded — proceeding with raw "
            "input as shield_map=empty): %s", e.__class__.__name__,
        )

    detected = _syn_report(shield_map)
    has_identifiers = detected["identifiers_masked"] > 0

    # ── Decide whether THIS message goes shielded.
    if policy == "always":
        will_shield = True
        bypass_reason = None
    elif policy == "off":
        # Even with policy=off, if a sensitive identifier is detected and
        # the user has not acknowledged the bypass, refuse the send. This
        # prevents a "policy=off" footgun from leaking PII to a provider.
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
    else:  # auto — the default
        if has_identifiers:
            # The auto policy ALWAYS shields when something is detected.
            # The user can acknowledge a bypass per message; that gets
            # logged with full provenance for audit.
            if body.acknowledge_unshielded:
                will_shield = False
                bypass_reason = "user_bypass_acknowledged"
            else:
                will_shield = True
                bypass_reason = None
        else:
            will_shield = False
            bypass_reason = "no_identifiers"

    # ── Persist the user message FIRST (so we have a provable record
    # even if the LLM call fails).
    msg_id = str(uuid.uuid4())
    user_at = _iso(_now())
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
    history_lines: List[str] = []
    for m in prior:
        role = "USER" if m.get("role") == "user" else "AKKI"
        # Re-shield prior user messages defensively — we don't want to
        # reveal earlier identifiers to the LLM if shielding was on then.
        # Phase A — historical messages are already stored as the
        # redacted projection (`text = syn_out["redacted_text"]` at
        # message-send time), so this re-shield is a belt-and-braces
        # second pass through the Synisense pipeline. If the historical
        # row pre-dates Phase A and contains raw PII, this catches it.
        c = m.get("content") or ""
        if m.get("role") == "user":
            try:
                c_shielded, _ = await _syn_shield(c, surface="chat",
                                                  context_id=chat.get("context_id") or "")
            except Exception:  # noqa: BLE001
                c_shielded = c
            history_lines.append(f"{role}: {c_shielded}")
        else:
            history_lines.append(f"{role}: {c}")
    history_block = "\n\n".join(history_lines)

    sent_to_llm = shielded_text if will_shield else text

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
    if grounding_block:
        full_prompt_parts.append(grounding_block)
    if history_block:
        full_prompt_parts.append(history_block)
    full_prompt_parts.append(f"USER: {sent_to_llm}")
    full_prompt = "\n\n".join(full_prompt_parts)

    # ── LLM call. Using the EMERGENT_LLM_KEY playbook directly so we can
    # pick the model per chat (the global call_llm hardcodes claude).
    emergent_key = os.environ.get("EMERGENT_LLM_KEY")
    started_ms = time.monotonic()
    if not emergent_key:
        reply_text = "(LLM unavailable — no key configured.)"
        mode = "no-key-fallback"
    else:
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            chat_session = LlmChat(
                api_key=emergent_key,
                session_id=f"akki-chat-{chat_id}",
                system_message=system_msg,
            ).with_model(model_def["provider"], model_def["model"])
            raw = await chat_session.send_message(UserMessage(text=full_prompt))
            raw_text = raw if isinstance(raw, str) else str(raw)
            reply_text = _syn_rehydrate(raw_text, shield_map) if will_shield else raw_text
            mode = "live"
        except Exception as e:
            logger.exception("Chat LLM call failed")
            reply_text = f"(LLM error: {type(e).__name__}.)"
            mode = "error"
    latency_ms = int((time.monotonic() - started_ms) * 1000)

    # ── Persist the assistant message.
    # Phase 11 ITEM C — extract & validate citation markers. Hallucinated
    # markers (those not in the retrieval allowlist) are dropped before
    # the reply ever reaches the client; surviving markers become
    # numbered chips with structured citation entries that the frontend
    # renders as click-through pills into the Reading Viewer.
    cleaned_reply, citations = _process_citations(reply_text, grounding_paragraphs)

    reply_id = str(uuid.uuid4())
    reply_at = _iso(_now())
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
    chat = await db.chats.find_one(
        {"id": chat_id, "account_id": current["id"], "status": {"$ne": "archived"}},
        {"_id": 0},
    )
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    model_def = _model_def(chat["model_id"]) or _model_def(DEFAULT_MODEL_ID)
    policy: ShieldingPolicy = chat.get("shielding_policy", "auto")

    # Same Synisense pre-LLM hook as the sync path. Kept inline rather
    # than refactored into a shared helper because the prep includes
    # several short-circuiting decisions (acknowledgement gate, history
    # block) that would clutter a generator signature.
    text = body.content.strip()
    original_text_for_shield = text
    syn_stats: Dict[str, Any] = {"spans_redacted": 0, "by_type": {}, "elapsed_ms": 0}
    shield_map: Dict[str, str] = {}
    shielded_text = text
    try:
        from services.synisense import run as syn_run
        from services.synisense.pipeline import current_version as _syn_version
        syn_out = await syn_run(
            text=text,
            context_id=chat.get("context_id") or "",
            surface="chat", mode="redact",
            account_id=current["id"],
        )
        shielded_text = syn_out["redacted_text"]
        text = shielded_text
        spans = syn_out.get("spans") or []
        for s in spans:
            tok = s.get("replacement")
            if not tok:
                continue
            try:
                shield_map[tok] = original_text_for_shield[int(s["start"]):int(s["end"])]
            except (KeyError, ValueError, TypeError):
                continue
        by_type: Dict[str, int] = {}
        for s in spans:
            t = s.get("entity_type") or "UNKNOWN"
            by_type[t] = by_type.get(t, 0) + 1
        syn_stats = {
            "spans_redacted": len(spans),
            "by_type": by_type,
            "elapsed_ms": int(syn_out.get("stats", {}).get("elapsed_ms") or 0),
            "version": _syn_version(),
        }
    except Exception as e:  # noqa: BLE001
        logger.warning("synisense chat stream hook failed: %s", e.__class__.__name__)

    detected = _syn_report(shield_map)
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
    msg_id = str(uuid.uuid4())
    user_at = _iso(_now())
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

    # Build prior + grounding (same as sync).
    prior = await db.chat_messages.find(
        {"chat_id": chat_id, "account_id": current["id"], "id": {"$ne": msg_id}},
        {"_id": 0, "role": 1, "content": 1, "shielded": 1},
    ).sort("created_at", 1).to_list(2000)
    history_lines: List[str] = []
    for m in prior:
        role = "USER" if m.get("role") == "user" else "AKKI"
        c = m.get("content") or ""
        if m.get("role") == "user":
            try:
                c_sh, _ = await _syn_shield(c, surface="chat",
                                            context_id=chat.get("context_id") or "")
            except Exception:  # noqa: BLE001
                c_sh = c
            history_lines.append(f"{role}: {c_sh}")
        else:
            history_lines.append(f"{role}: {c}")
    history_block = "\n\n".join(history_lines)
    sent_to_llm = shielded_text if will_shield else text

    grounding_paragraphs: List[Dict[str, Any]] = []
    grounding_block = ""
    if chat.get("context_id"):
        grounding_paragraphs = await _retrieve_grounding_paragraphs(
            context_id=chat["context_id"], account_id=current["id"],
            query=text, top_k=5,
        )
        grounding_block = _format_grounding_block(grounding_paragraphs)

    system_msg = (
        "You are AKKI, a calm, editorial intelligence partner for executives "
        "and non-executive directors. Tone: precise, neutral, no hype, "
        "Economist-style cadence. When tokens like [EMAIL_1] or [PERSON_3] "
        "appear, treat each as a stable referent — reason about it without "
        "asking the user what it means; the system will rehydrate the "
        "real value before the user reads your reply."
    )
    if grounding_paragraphs:
        system_msg += (
            " A [GROUNDING] block follows containing extracted paragraphs "
            "from the user's documents. Cite ONLY using the inline marker "
            "[[cite:<anchor_id>]] where <anchor_id> appears in the block. "
            "Never invent anchor ids. If the answer is not in the grounding "
            "block, say so plainly rather than guessing."
        )

    full_prompt_parts: List[str] = []
    if grounding_block:
        full_prompt_parts.append(grounding_block)
    if history_block:
        full_prompt_parts.append(history_block)
    full_prompt_parts.append(f"USER: {sent_to_llm}")
    full_prompt = "\n\n".join(full_prompt_parts)

    request_account = current  # closures capture this at the inner scope
    request_obj = request

    async def _event_gen():
        import asyncio as _asyncio
        emergent_key = os.environ.get("EMERGENT_LLM_KEY")
        started_ms = time.monotonic()
        raw_text = ""
        mode = "live"

        # Run the LLM call in a worker thread so we don't block the event
        # loop; the SDK is sync. Once we get the full reply, we chunk it
        # back to the client. This is the documented "coarse-chunk
        # fallback" — the SDK doesn't expose a streaming primitive yet.
        if not emergent_key:
            raw_text = "(LLM unavailable — no key configured.)"
            mode = "no-key-fallback"
        else:
            try:
                from emergentintegrations.llm.chat import LlmChat, UserMessage
                chat_session = LlmChat(
                    api_key=emergent_key,
                    session_id=f"akki-chat-{chat_id}",
                    system_message=system_msg,
                ).with_model(model_def["provider"], model_def["model"])
                raw = await chat_session.send_message(UserMessage(text=full_prompt))
                raw_text = raw if isinstance(raw, str) else str(raw)
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

        # Chunk the SHIELDED reply (final-rehydrate strategy — see
        # module-level comment). ~40-token = ~200-char chunks.
        CHUNK_CHARS = 220
        for i in range(0, len(raw_text), CHUNK_CHARS):
            chunk = raw_text[i:i + CHUNK_CHARS]
            yield (
                "data: " + json.dumps({"type": "delta", "text": chunk}) + "\n\n"
            )
            # Tiny gap so the client renders progressively rather than
            # painting all chunks in one frame.
            await _asyncio.sleep(0.02)

        latency_ms = int((time.monotonic() - started_ms) * 1000)
        # Now do the final rehydrate + citation post-processing on the
        # COMPLETE shielded reply, exactly once.
        rehydrated = _syn_rehydrate(raw_text, shield_map) if will_shield else raw_text
        cleaned_reply, citations = _process_citations(rehydrated, grounding_paragraphs)

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
        }
        await db.chat_messages.insert_one(assistant_msg)

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

        yield (
            "data: " + json.dumps({
                "type": "message",
                "message_id": reply_id,
                "assistant_text": cleaned_reply,
                "model": chat["model_id"],
                "audit_id": audit_row["id"] if audit_row else None,
                "citations": citations,
                "shielding": detected,
                "will_shield": will_shield,
                "bypass_reason": bypass_reason,
                "latency_ms": latency_ms,
            }) + "\n\n"
        )
        yield "data: " + json.dumps({"type": "done"}) + "\n\n"

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
