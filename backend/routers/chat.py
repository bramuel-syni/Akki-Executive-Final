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
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from core import db, get_current_account  # noqa: E402
from core import now as _now, iso as _iso  # noqa: E402
from llm_service import shield_payload, shielding_report, rehydrate

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


class ChatPatchIn(BaseModel):
    title: Optional[str] = Field(default=None, max_length=120)
    model_id: Optional[str] = None
    shielding_policy: Optional[ShieldingPolicy] = None


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
        payload={"model_id": body.model_id, "shielding_policy": body.shielding_policy},
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
async def archive_chat(
    chat_id: str, request: Request,
    current: Dict[str, Any] = Depends(get_current_account),
):
    res = await db.chats.update_one(
        {"id": chat_id, "account_id": current["id"]},
        {"$set": {"status": "archived", "archived_at": _iso(_now())}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Chat not found")
    await _append_audit(
        account_id=current["id"], chat_id=chat_id, action="chat.archived",
        request=request, payload={},
    )
    return {"ok": True}


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

    # ── Detect identifiers ALWAYS — this drives both the auto policy and
    # the pre-send confirmation surface. We do NOT log the raw content.
    text = body.content.strip()
    shielded_text, shield_map = shield_payload(text)
    detected = shielding_report(shield_map)
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
        c = m.get("content") or ""
        if m.get("role") == "user":
            c_shielded, _ = shield_payload(c)
            history_lines.append(f"{role}: {c_shielded}")
        else:
            history_lines.append(f"{role}: {c}")
    history_block = "\n\n".join(history_lines)

    sent_to_llm = shielded_text if will_shield else text

    system_msg = (
        "You are AKKI, a calm, editorial intelligence partner for executives "
        "and non-executive directors. Tone: precise, neutral, no hype, "
        "Economist-style cadence. When tokens like [EMAIL_1] or [PERSON_3] "
        "appear, treat each as a stable referent — reason about it without "
        "asking the user what it means; the system will rehydrate the "
        "real value before the user reads your reply."
    )

    full_prompt = (
        (history_block + "\n\n" if history_block else "")
        + f"USER: {sent_to_llm}"
    )

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
            reply_text = rehydrate(raw_text, shield_map) if will_shield else raw_text
            mode = "live"
        except Exception as e:
            logger.exception("Chat LLM call failed")
            reply_text = f"(LLM error: {type(e).__name__}.)"
            mode = "error"
    latency_ms = int((time.monotonic() - started_ms) * 1000)

    # ── Persist the assistant message.
    reply_id = str(uuid.uuid4())
    reply_at = _iso(_now())
    assistant_msg = {
        "id": reply_id,
        "chat_id": chat_id,
        "account_id": current["id"],
        "role": "assistant",
        "content": reply_text,
        "model_id": chat["model_id"],
        "model_label": model_def["label"],
        "mode": mode,
        "latency_ms": latency_ms,
        "created_at": reply_at,
    }
    await db.chat_messages.insert_one(assistant_msg)
    await _append_audit(
        account_id=current["id"], chat_id=chat_id, action="message.received",
        request=request,
        payload={
            "user_message_id": msg_id, "reply_id": reply_id,
            "model_id": chat["model_id"], "mode": mode,
            "latency_ms": latency_ms, "char_len_reply": len(reply_text),
        },
    )

    # ── Update chat metadata (preview, count, last_message_at).
    await db.chats.update_one(
        {"id": chat_id},
        {
            "$set": {
                "last_message_at": reply_at,
                "last_message_preview": reply_text[:200],
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
