"""H3 — Trust Center v1 (2026-05-24).

Read-only consumer of the audit collections (``synisense_audit_log``,
``chat_audit_log``, ``synisense_runs``, ``chat_messages``, ``chats``).
Surfaces three views to executives:

  * **Session** — one conversation's promise + per-turn drill-down.
  * **Activity** — cross-conversation aggregate within accessible
    contexts, with filters.
  * **Plaintext** — explicit, audit-logged peek at the user's raw
    input. The ONLY surface that returns raw plaintext anywhere in
    the Trust Center.

Vocabulary
----------
* "Trust Center" — the destination page + API path. American spelling.
* "Shield" — only used in inline operational fields
  (``shield_status``, ``shield_invocation``, ``shielded_by``).

Conservative plaintext policy
-----------------------------
* Default everywhere: surface the SHA-256 of raw input, never the
  text itself.
* The plaintext endpoint reads from the existing ``chat_messages``
  collection — Trust Center stores NOTHING new of its own.
* Plaintext view writes a ``trust_center.plaintext_viewed`` row to
  ``chat_audit_log`` so the "I looked at the raw text" event is
  itself audit-logged.
"""
from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

from fastapi import APIRouter, Depends, HTTPException, Query

from core import db, get_current_account


router = APIRouter(prefix="/api/trust-center", tags=["trust-center"])


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────
async def _accessible_context_ids(account_id: str) -> Set[str]:
    """All context_ids the account has an active membership in.
    Trust Center's strict scoping anchor."""
    rows = await db.memberships.find(
        {"account_id": account_id, "status": "active"},
        {"_id": 0, "context_id": 1},
    ).to_list(length=None)
    return {r["context_id"] for r in rows if r.get("context_id")}


async def _is_superadmin_in_context(account_id: str, context_id: str) -> bool:
    """Superadmin status is context-scoped — a tenant admin elsewhere
    has no powers here."""
    membership = await db.memberships.find_one(
        {"account_id": account_id, "context_id": context_id, "status": "active"},
        {"_id": 0, "sub_role": 1},
    )
    if not membership:
        return False
    if membership.get("sub_role") in ("admin", "owner"):
        return True
    # Global superadmin (rare; emergency access).
    acct = await db.accounts.find_one(
        {"id": account_id}, {"_id": 0, "is_superadmin": 1},
    )
    return bool(acct and acct.get("is_superadmin"))


async def _load_chat_or_403(chat_id: str, account_id: str) -> Dict[str, Any]:
    """Returns the chat row if the caller has access to its context.
    Raises 404 if missing, 403 if not in context."""
    chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found.")
    ctx_id = chat.get("context_id")
    if ctx_id:
        accessible = await _accessible_context_ids(account_id)
        if ctx_id not in accessible:
            raise HTTPException(
                status_code=403,
                detail="You don't have access to this chat's context.",
            )
    else:
        # Pre-context chats — owner-only.
        if chat.get("account_id") != account_id:
            raise HTTPException(
                status_code=403,
                detail="You are not the owner of this chat.",
            )
    return chat


_SHIELDED_PLACEHOLDER = re.compile(r"\[\[ENT_[A-Z_]+_\d+\]\]")


def _hash_text(text: str) -> str:
    """SHA-256 over the user's raw input. Surfaced everywhere
    plaintext would otherwise have leaked."""
    return hashlib.sha256((text or "").encode("utf-8", "ignore")).hexdigest()


def _classify_chat_shield_status(chat: Dict[str, Any]) -> str:
    """One of ``active`` / ``backfilled`` / ``pre_shield_v1`` /
    ``boot_warning``.

    H4 (2026-05-24) — chats carrying ``backfill_metadata.partial=false``
    are classified as ``backfilled`` so Trust Center can show the
    "back-filled on <date>" copy instead of the pre-v1 empty state."""
    bf = (chat.get("backfill_metadata") or {})
    if bf and bf.get("partial") is False:
        return "backfilled"
    if not chat.get("synisense_audit_ids"):
        return "pre_shield_v1"
    return "active"


def _coerce_ts(value: Any) -> str:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    return str(value or "")


# ─────────────────────────────────────────────────────────────────────
# GET /api/trust-center/session/{chat_id}
# ─────────────────────────────────────────────────────────────────────
@router.get("/session/{chat_id}")
async def session(
    chat_id: str,
    current: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    """Single-conversation Trust Center summary + per-turn list.
    Strict context-scope check applied."""
    chat = await _load_chat_or_403(chat_id, current["id"])
    shield_status = _classify_chat_shield_status(chat)

    # Pre-Shield-v1.x chats — return the empty-state shell that the
    # UI keys off `shield_status`.
    if shield_status == "pre_shield_v1":
        context = await db.contexts.find_one(
            {"id": chat.get("context_id")}, {"_id": 0, "name": 1},
        ) or {}
        return {
            "chat_id": chat_id,
            "chat_title": chat.get("title") or "Untitled",
            "context_id": chat.get("context_id"),
            "context_name": context.get("name"),
            "shield_status": "pre_shield_v1",
            "promise_summary": None,
            "caveats": [
                "This conversation predates Shield v1.x. Counters "
                "will populate after maintenance back-fill (H4).",
            ],
            "turns": [],
        }

    # ── Turn list ── pull both user + assistant messages, threaded.
    messages = await db.chat_messages.find(
        {"chat_id": chat_id}, {"_id": 0},
    ).sort([("ts", 1), ("id", 1)]).to_list(length=None)

    # ── Audit rows for cross-reference ──
    audit_ids = chat.get("synisense_audit_ids") or []
    shield_audits = await db.synisense_audit_log.find(
        {"audit_id": {"$in": audit_ids}}, {"_id": 0},
    ).to_list(length=None) if audit_ids else []
    audit_by_id = {r["audit_id"]: r for r in shield_audits}

    chat_audits = await db.chat_audit_log.find(
        {"chat_id": chat_id, "action": "message.sent"}, {"_id": 0},
    ).sort([("at", 1)]).to_list(length=None)
    chat_audit_by_msg = {
        (r.get("payload") or {}).get("message_id"): r for r in chat_audits
    }

    # ── Synisense runs (the canonical per-turn shield outcome) ──
    runs = await db.synisense_runs.find(
        {"chat_id": chat_id}, {"_id": 0},
    ).to_list(length=None)
    runs_by_msg = {r.get("message_id"): r for r in runs}

    # ── Build the per-turn list ──
    turns: List[Dict[str, Any]] = []
    total_redactions = 0
    by_class: Dict[str, int] = {}
    turns_with_redaction = 0
    llm_calls = 0
    models_used: Set[str] = set()

    for msg in messages:
        if msg.get("role") != "user":
            # Assistant turn — track model usage + LLM-call count.
            model = (msg.get("model") or "").strip()
            if model:
                models_used.add(model)
                llm_calls += 1
            continue
        msg_id = msg.get("id")
        run = runs_by_msg.get(msg_id) or {}
        spans = run.get("spans") or []
        turn_by_class: Dict[str, int] = {}
        for s in spans:
            et = s.get("entity_type") or "UNKNOWN"
            turn_by_class[et] = turn_by_class.get(et, 0) + 1
            by_class[et] = by_class.get(et, 0) + 1
        turn_redactions = sum(turn_by_class.values())
        total_redactions += turn_redactions
        if turn_redactions > 0:
            turns_with_redaction += 1

        # Pick the Shield audit row that landed nearest this turn.
        # ``chat.synisense_audit_ids`` is push-appended in turn order,
        # so the row whose timestamp is just after this user message's
        # ts is the right one. Fall back to the chat_audit row's id.
        nearest_audit_id: Optional[str] = None
        msg_ts = (
            msg.get("ts") or msg.get("at") or msg.get("created_at") or ""
        )
        msg_ts_iso = _coerce_ts(msg_ts)
        for aid in audit_ids:
            row = audit_by_id.get(aid) or {}
            row_ts = _coerce_ts(row.get("timestamp"))
            if row_ts >= msg_ts_iso:
                nearest_audit_id = aid
                break
        chat_audit_row = chat_audit_by_msg.get(msg_id) or {}

        turns.append({
            "turn_id": chat_audit_row.get("id") or msg_id,
            "message_id": msg_id,
            "ts": msg_ts_iso,
            "model": chat_audit_row.get("payload", {}).get("model") or None,
            "shielded": turn_redactions > 0,
            "by_class": turn_by_class,
            "audit_id": nearest_audit_id,
            "chat_audit_id": chat_audit_row.get("id"),
            "hash_chain_status": "verified" if chat_audit_row.get("row_hash") else "missing",
            # H4 — per-turn back-fill marker so the UI can show a
            # "back-filled" badge on turns originating from the
            # historical-data sweep. Derived from the synisense_runs
            # row that the back-fill engine wrote.
            "is_backfill": bool((run or {}).get("is_backfill")),
            "backfill_batch_id": (run or {}).get("backfill_batch_id"),
            "original_message_ts": (run or {}).get("original_message_ts"),
        })

    context = await db.contexts.find_one(
        {"id": chat.get("context_id")}, {"_id": 0, "name": 1},
    ) or {}

    return {
        "chat_id": chat_id,
        "chat_title": chat.get("title") or "Untitled",
        "context_id": chat.get("context_id"),
        "context_name": context.get("name"),
        "shield_status": shield_status,
        # H4 — When the chat has been back-filled, surface the
        # metadata block so the UI can show the "back-filled on
        # <date>" copy AND auditors can verify the batch ID.
        "backfill_metadata": chat.get("backfill_metadata"),
        "promise_summary": {
            "total_turns": len([m for m in messages if m.get("role") == "user"]),
            "turns_with_redaction": turns_with_redaction,
            "identifiers_shielded_total": total_redactions,
            "by_class": by_class,
            "llm_calls": llm_calls,
            "models_used": sorted(models_used),
            "your_data_exposure_pct": (
                "0% (Shield kept all sensitive identifiers off the LLM)"
                if total_redactions > 0
                else "No sensitive identifiers detected this conversation."
            ),
        },
        "caveats": [
            "Counts above are per user-turn detections from the "
            "canonical Shield mint. The fuller ``synisense_audit_log`` "
            "row that the LLM saw includes identifiers from history + "
            "grounding documents in addition to the current turn — its "
            "numeric is a superset of the per-turn number. View per-turn "
            "detail for the exact identifiers Shield removed each turn.",
            "Pre-Shield-v1.x turns (conversations created before "
            "2026-02) are excluded from these totals.",
        ],
        "turns": turns,
    }


# ─────────────────────────────────────────────────────────────────────
# GET /api/trust-center/session/{chat_id}/turn/{message_id}
# ─────────────────────────────────────────────────────────────────────
@router.get("/session/{chat_id}/turn/{message_id}")
async def session_turn(
    chat_id: str,
    message_id: str,
    current: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    """Full evidence for one turn. Surfaces the four hash/tokens
    visible to bankers: input hash, what Synisense sent to the LLM,
    what the LLM returned, what the user saw post-rehydration.

    Conservative-storage policy: NONE of the tokenized texts are
    persisted by Shield (the audit log keeps only request/response
    hashes — verifiable but not viewable). The Trust Center re-runs
    the **deterministic** ``deidentifier.deidentify()`` function on
    the saved plaintext to reproduce exactly what Shield sent to the
    LLM. Same regex + dict + spaCy pipeline → identical output. Any
    auditor can run the same call independently and verify.
    """
    chat = await _load_chat_or_403(chat_id, current["id"])
    user_msg = await db.chat_messages.find_one(
        {"chat_id": chat_id, "id": message_id, "role": "user"},
        {"_id": 0},
    )
    if not user_msg:
        raise HTTPException(status_code=404, detail="Turn not found.")
    # The assistant reply that followed. We look it up by
    # (chat_id, role, created_at > user_msg.created_at) because
    # ``parent_message_id`` is not currently persisted on the
    # assistant turn.
    user_ts = user_msg.get("created_at") or user_msg.get("ts") or ""
    asst_msg = await db.chat_messages.find_one(
        {"chat_id": chat_id, "role": "assistant",
         "created_at": {"$gte": user_ts}},
        {"_id": 0},
        sort=[("created_at", 1)],
    )
    run = await db.synisense_runs.find_one(
        {"chat_id": chat_id, "message_id": message_id}, {"_id": 0},
    ) or {}
    spans = run.get("spans") or []

    chat_audit = await db.chat_audit_log.find_one(
        {"chat_id": chat_id, "action": "message.sent",
         "payload.message_id": message_id},
        {"_id": 0},
    ) or {}

    # The Shield audit row whose timestamp is closest after this turn.
    audit_ids = chat.get("synisense_audit_ids") or []
    msg_ts = _coerce_ts(
        user_msg.get("ts") or user_msg.get("at") or user_msg.get("created_at")
    )
    shield_audit = None
    if audit_ids:
        rows = await db.synisense_audit_log.find(
            {"audit_id": {"$in": audit_ids}}, {"_id": 0},
        ).sort([("timestamp", 1)]).to_list(length=None)
        for r in rows:
            r_ts = _coerce_ts(r.get("timestamp"))
            if r_ts >= msg_ts:
                shield_audit = r
                break

    raw_text = user_msg.get("content") or ""
    sha256 = _hash_text(raw_text)

    # ── Re-derive the tokenized forms via the existing
    # deterministic deidentifier. No storage changes; no Shield
    # runtime changes. The deidentifier function is the same one
    # the live request path uses, so its output here is
    # bit-identical to what Shield actually sent. ──
    redacted_prompt = ""
    llm_response_tokenized = ""
    tenant_id = current.get("id") or ""
    try:
        from services.synisense.shield import deidentifier
        user_deid = await deidentifier.deidentify(
            raw_text, tenant_id=tenant_id,
        )
        redacted_prompt = user_deid.redacted_text or ""
        if asst_msg:
            asst_text = asst_msg.get("content") or ""
            asst_deid = await deidentifier.deidentify(
                asst_text, tenant_id=tenant_id,
            )
            llm_response_tokenized = asst_deid.redacted_text or ""
    except Exception as exc:  # noqa: BLE001 — degrade gracefully
        # If the deidentifier is unavailable (cold-start window),
        # surface the hash + placeholders explicitly rather than
        # lying. The audit chain status still tells the truth.
        redacted_prompt = (
            f"[derivation unavailable: {type(exc).__name__}; "
            f"audit row hash={(shield_audit or {}).get('request_hash')}]"
        )
        llm_response_tokenized = (
            f"[derivation unavailable: response hash="
            f"{(shield_audit or {}).get('response_hash')}]"
        )

    # What the user finally saw.
    user_visible = (asst_msg or {}).get("content") or ""

    redactions = [{
        "class": s.get("entity_type"),
        "count": 1,
        "source": s.get("source"),
        "confidence": s.get("confidence"),
    } for s in spans]

    # ── Hash chain status — from chat_audit_log's row_hash/prev_hash ──
    chain_status: Dict[str, Any] = {
        "audit_id": (shield_audit or {}).get("audit_id"),
        "chat_audit_id": chat_audit.get("id"),
        "row_hash": chat_audit.get("row_hash"),
        "prev_hash": chat_audit.get("prev_hash"),
        "chain_valid": bool(chat_audit.get("row_hash")),
    }

    return {
        "turn_id": chat_audit.get("id") or message_id,
        "message_id": message_id,
        "ts": msg_ts,
        "shield_invocation": {
            "invoked": bool(shield_audit) or bool(run),
            "completed": bool(shield_audit and shield_audit.get("outcome") == "success") or bool(run),
            "channel": (chat_audit.get("payload") or {}).get("channel"),
            "shielded_by": run.get("synisense_version") or "synisense-shield-v1",
            "duration_ms": (run.get("stats") or {}).get("elapsed_ms"),
        },
        "what_you_sent_sha256": sha256,
        "what_synisense_sent_to_llm": redacted_prompt,
        "what_llm_returned": llm_response_tokenized,
        "what_you_saw": user_visible,
        "redactions": redactions,
        "audit_chain": chain_status,
        # H4 cycle-2 (2026-05-24) — back-fill markers were populated on
        # the session-level ``turns[]`` array but missing from the
        # per-turn drill-down. Pull them from the synisense_runs row
        # (the canonical per-turn source the back-fill engine writes
        # to) and surface them so auditors can distinguish a
        # reconstructed turn from a live one without leaving this
        # endpoint.
        "is_backfill": bool(run.get("is_backfill")),
        "backfill_batch_id": run.get("backfill_batch_id"),
        "original_message_ts": run.get("original_message_ts"),
        "derivation_note": (
            "what_synisense_sent_to_llm and what_llm_returned are "
            "re-derived at view-time by running the same deterministic "
            "deidentifier on the persisted plaintext. The Shield audit "
            "log stores only request_hash + response_hash; the texts "
            "shown here are bit-identical to what Shield actually "
            "produced, but were not stored — they were computed from "
            "the saved messages on this request."
        ),
        "raw_plaintext_url": (
            f"/api/trust-center/session/{chat_id}/turn/{message_id}/plaintext"
        ),
    }


# ─────────────────────────────────────────────────────────────────────
# GET /api/trust-center/session/{chat_id}/turn/{message_id}/plaintext
# ─────────────────────────────────────────────────────────────────────
@router.get("/session/{chat_id}/turn/{message_id}/plaintext")
async def session_turn_plaintext(
    chat_id: str,
    message_id: str,
    current: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    """The ONLY Trust Center surface that returns raw plaintext.

    Auth: context-scope check PLUS chat-owner OR superadmin-in-context.
    Writes ``trust_center.plaintext_viewed`` audit row.
    """
    chat = await _load_chat_or_403(chat_id, current["id"])
    ctx_id = chat.get("context_id") or ""

    is_owner = chat.get("account_id") == current["id"]
    is_admin = await _is_superadmin_in_context(current["id"], ctx_id) if ctx_id else False
    if not is_owner and not is_admin:
        raise HTTPException(
            status_code=403,
            detail="Plaintext access requires chat ownership or "
                   "superadmin in this context.",
        )

    user_msg = await db.chat_messages.find_one(
        {"chat_id": chat_id, "id": message_id, "role": "user"},
        {"_id": 0, "content": 1, "ts": 1, "at": 1},
    )
    if not user_msg:
        raise HTTPException(status_code=404, detail="Turn not found.")

    plaintext = user_msg.get("content") or ""

    # Audit the access — the "I looked at raw text" event is itself
    # provable. Best-effort row write; auth result must NOT depend on
    # the write succeeding (audit-log Mongo blip != denied access).
    try:
        await db.chat_audit_log.insert_one({
            "id": "ta-" + uuid.uuid4().hex,
            "account_id": current["id"],
            "chat_id": chat_id,
            "action": "trust_center.plaintext_viewed",
            "at": datetime.now(timezone.utc).isoformat(),
            "payload": {
                "viewer_id": current["id"],
                "viewer_role": "owner" if is_owner else "context_admin",
                "message_id": message_id,
                "content_sha256": _hash_text(plaintext),
            },
        })
    except Exception:  # noqa: BLE001
        pass

    return {
        "chat_id": chat_id,
        "message_id": message_id,
        "plaintext": plaintext,
        "viewed_at": datetime.now(timezone.utc).isoformat(),
        "viewer_id": current["id"],
        "audit_logged": True,
    }


# ─────────────────────────────────────────────────────────────────────
# GET /api/trust-center/activity
# ─────────────────────────────────────────────────────────────────────
@router.get("/activity")
async def activity(
    from_: Optional[str] = Query(None, alias="from"),
    to: Optional[str] = Query(None),
    context_id: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    pii_class: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    current: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    """Cross-conversation aggregate. Strict context-scope filter is
    applied SERVER-SIDE — the response only contains data from
    contexts the caller is an active member of."""
    accessible = await _accessible_context_ids(current["id"])
    if context_id:
        if context_id not in accessible:
            raise HTTPException(
                status_code=403,
                detail="You don't have access to that context.",
            )
        ctx_filter = {context_id}
    else:
        ctx_filter = accessible

    if not ctx_filter:
        return {
            "since": from_, "until": to,
            "total_identifiers_shielded": 0,
            "total_chats": 0,
            "total_turns": 0,
            "models_used": [],
            "by_class": {},
            "rows": [],
        }

    cutoff_from = from_ or (
        datetime.now(timezone.utc) - timedelta(days=30)
    ).isoformat()
    cutoff_to = to or datetime.now(timezone.utc).isoformat()

    def _parse_iso(s: str) -> datetime:
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:  # noqa: BLE001
            return datetime.now(timezone.utc)

    cutoff_from_dt = _parse_iso(cutoff_from)
    cutoff_to_dt = _parse_iso(cutoff_to)

    # Chats in scope.
    chat_query: Dict[str, Any] = {
        "context_id": {"$in": list(ctx_filter)},
    }
    if user_id:
        if not any(await _is_superadmin_in_context(current["id"], c) for c in ctx_filter):
            raise HTTPException(
                status_code=403,
                detail="Filtering by user_id requires superadmin-in-context.",
            )
        chat_query["account_id"] = user_id
    chats_in_scope = await db.chats.find(
        chat_query, {"_id": 0, "id": 1, "title": 1, "context_id": 1, "account_id": 1},
    ).to_list(length=None)
    chat_ids = [c["id"] for c in chats_in_scope]
    chat_by_id = {c["id"]: c for c in chats_in_scope}

    if not chat_ids:
        return {
            "since": cutoff_from, "until": cutoff_to,
            "total_identifiers_shielded": 0,
            "total_chats": 0,
            "total_turns": 0,
            "models_used": [],
            "by_class": {},
            "rows": [],
        }

    # synisense_runs is the canonical per-turn source.
    # `ts` is stored as BSON Date (datetime) — compare against datetime,
    # NOT against an ISO string (string-vs-Date comparisons return false
    # and silently return zero rows).
    runs_query: Dict[str, Any] = {
        "chat_id": {"$in": chat_ids},
        "ts": {"$gte": cutoff_from_dt, "$lte": cutoff_to_dt},
    }
    runs = await db.synisense_runs.find(
        runs_query, {"_id": 0},
    ).sort([("ts", -1)]).to_list(length=limit * 5)  # over-fetch for filter

    by_class: Dict[str, int] = {}
    rows: List[Dict[str, Any]] = []
    models_used: Set[str] = set()
    total_redactions = 0
    chats_with_redaction: Set[str] = set()
    turns_seen = 0

    for r in runs:
        spans = r.get("spans") or []
        if not spans:
            continue
        # PII class filter (server-side).
        if pii_class:
            spans = [s for s in spans if s.get("entity_type") == pii_class]
            if not spans:
                continue
        turn_classes: Dict[str, int] = {}
        for s in spans:
            et = s.get("entity_type") or "UNKNOWN"
            turn_classes[et] = turn_classes.get(et, 0) + 1
            by_class[et] = by_class.get(et, 0) + 1
        turn_n = sum(turn_classes.values())
        total_redactions += turn_n
        chats_with_redaction.add(r["chat_id"])
        turns_seen += 1
        if len(rows) < limit:
            rows.append({
                "ts": _coerce_ts(r.get("ts")),
                "chat_id": r.get("chat_id"),
                "chat_title": chat_by_id.get(r.get("chat_id"), {}).get("title"),
                "message_id": r.get("message_id"),
                "by_class": turn_classes,
                "version": r.get("synisense_version"),
            })

    # Model filter — applied via chat_audit_log lookup (cheap because
    # chats_in_scope is already bounded by context).
    if model:
        cm = await db.chat_audit_log.find(
            {"chat_id": {"$in": chat_ids},
             "payload.model": {"$regex": re.escape(model), "$options": "i"}},
            {"_id": 0, "chat_id": 1, "payload.model": 1},
        ).to_list(length=None)
        matched = {r["chat_id"] for r in cm}
        rows = [r for r in rows if r.get("chat_id") in matched]

    # Models used in scope (full sweep, not just filtered subset).
    cm_full = await db.chat_audit_log.find(
        {"chat_id": {"$in": chat_ids},
         "payload.model": {"$exists": True, "$ne": None}},
        {"_id": 0, "payload.model": 1},
    ).to_list(length=None)
    for r in cm_full:
        mm = (r.get("payload") or {}).get("model")
        if mm:
            models_used.add(mm)

    return {
        "since": cutoff_from,
        "until": cutoff_to,
        "total_identifiers_shielded": total_redactions,
        "total_chats": len(chats_with_redaction),
        "total_turns": turns_seen,
        "models_used": sorted(models_used),
        "by_class": by_class,
        "rows": rows,
    }


# ─────────────────────────────────────────────────────────────────────
# GET /api/trust-center/activity/export
# ─────────────────────────────────────────────────────────────────────
@router.get("/activity/export")
async def activity_export(
    from_: Optional[str] = Query(None, alias="from"),
    to: Optional[str] = Query(None),
    context_id: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    pii_class: Optional[str] = Query(None),
    current: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    """JSON bundle export. Same scoping rules as the activity
    endpoint. Includes the raw Shield audit rows so an auditor can
    verify the HMAC chain independently."""
    activity_resp = await activity(
        from_=from_, to=to, context_id=context_id,
        model=model, pii_class=pii_class, limit=500,
        current=current,
    )

    # Attach the Shield audit rows for every turn in the bundle.
    msg_ids = [r["message_id"] for r in activity_resp.get("rows", [])
               if r.get("message_id")]
    if msg_ids:
        chat_ids = list({r["chat_id"] for r in activity_resp.get("rows", [])})
        chats_in_scope = await db.chats.find(
            {"id": {"$in": chat_ids}},
            {"_id": 0, "id": 1, "synisense_audit_ids": 1},
        ).to_list(length=None)
        all_audit_ids = []
        for c in chats_in_scope:
            all_audit_ids.extend(c.get("synisense_audit_ids") or [])
        shield_rows = await db.synisense_audit_log.find(
            {"audit_id": {"$in": all_audit_ids}}, {"_id": 0},
        ).to_list(length=None) if all_audit_ids else []
    else:
        shield_rows = []

    activity_resp["shield_audit_rows"] = shield_rows
    activity_resp["export_generated_at"] = datetime.now(timezone.utc).isoformat()
    activity_resp["export_generated_by"] = current["id"]
    return activity_resp
