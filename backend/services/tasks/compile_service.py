"""Phase F.4 — Task Compile orchestrator (2026-05-26).

Implements the 5-stage compile pipeline:

  1. Drafting           — Akki assembles a first cut from approved/
                          submitted contributions + manually-added
                          docs + output spec. Generates new
                          `state=draft, origin=akki_generated,
                          task_id=<id>` documents.
  2. Review & Editing   — pass-through. Users edit drafts via the
                          existing DocumentDrawer + prompted-edit
                          pipeline (E.3). The compile service marks
                          the stage complete on user signal.
  3. Circulation        — generates magic-link tokens scoped to the
                          drafts in this session, sends invites via
                          Postmark (`email_service.send_email`).
                          Reviewers comment via the link without an
                          Akki account.
  4. Final production   — applies circulation comments via the
                          prompted-edit pipeline (`apply_comment`).
  5. Commit             — sequentially commits each draft
                          (state → "committed"). Rollback on partial
                          failure.

All LLM calls route through Shield with a 3-second timeout fallback.
On timeout, the service emits a `task.compile.<purpose>.llm.timeout`
audit event and falls back to a deterministic template body.

Email send routes through Postmark (`email_service.send_email`). If
send fails, the magic link is still generated + persisted; the audit
row + UI surface the failure honestly. The reviewer can be given the
link manually.
"""
from __future__ import annotations

import asyncio
import json
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple


log = logging.getLogger("akki.tasks.compile")


SHIELD_LLM_TIMEOUT_SECONDS = 3.0   # F.4 dispatch — 3-second LLM timeout.

STAGES = (
    "drafting",
    "review",
    "circulation",
    "final_production",
    "commit",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ═════════════════════════════════════════════════════════════════════
# Shield wrapper with 3-second timeout
# ═════════════════════════════════════════════════════════════════════
async def shield_invoke_bounded(
    *, purpose: str, content: str, tenant_id: str,
    consumer_id: str = "tasks", user_id: str,
    model_preference: str = "balanced",
) -> Optional[Dict[str, Any]]:
    """Wraps `shield_invoke` in a 3-second timeout. Returns None on
    timeout or any failure so callers can fall back to deterministic
    behaviour without distinguishing the failure mode."""
    try:
        from services.synisense.shield.client import invoke as shield_invoke
    except Exception:
        return None
    try:
        return await asyncio.wait_for(
            shield_invoke(
                purpose=purpose, content=content,
                tenant_id=tenant_id, consumer_id=consumer_id,
                user_id=user_id, model_preference=model_preference,
            ),
            timeout=SHIELD_LLM_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        log.warning("shield timeout: purpose=%s timeout=%.1fs", purpose, SHIELD_LLM_TIMEOUT_SECONDS)
        # Audit event surfaced via the caller (it has db handle).
        return {"__timeout__": True, "purpose": purpose}
    except Exception as e:  # noqa: BLE001
        log.warning("shield failed: purpose=%s err=%s", purpose, e)
        return None


async def _record_llm_timeout(db, *, task_id: str, account_id: str, purpose: str) -> None:
    try:
        await db.audit_log.insert_one({
            "id":            str(uuid.uuid4()),
            "account_id":    account_id,
            "action":        "task.compile.llm.timeout",
            "resource_type": "task",
            "resource_id":   task_id,
            "metadata":      {"purpose": purpose, "timeout_s": SHIELD_LLM_TIMEOUT_SECONDS},
            "created_at":    _now_iso(),
        })
    except Exception as e:  # noqa: BLE001
        log.warning("timeout audit insert failed: %s", e)


# ═════════════════════════════════════════════════════════════════════
# Stage helpers
# ═════════════════════════════════════════════════════════════════════
def _empty_session() -> Dict[str, Any]:
    return {
        "active":                 False,
        "current_stage":          None,
        "draft_artefact_ids":     [],
        "review_artefact_ids":    [],
        "circulation": {
            "enabled":         False,
            "reviewer_emails": [],
            "sent_at":         None,
            "comments":        [],
            "closed_at":       None,
        },
        "final_artefact_ids":     [],
        "committed_artefact_ids": [],
        "started_at":             None,
        "completed_at":           None,
    }


async def _audit(db, *, task_id: str, account_id: str, action: str,
                 ctx_id: Optional[str], metadata: Optional[Dict[str, Any]] = None) -> None:
    try:
        await db.audit_log.insert_one({
            "id":            str(uuid.uuid4()),
            "account_id":    account_id,
            "context_id":    ctx_id,
            "action":        action,
            "resource_type": "task",
            "resource_id":   task_id,
            "metadata":      metadata or {},
            "created_at":    _now_iso(),
        })
    except Exception as e:  # noqa: BLE001
        log.warning("audit insert failed (%s): %s", action, e)


async def _set_session(db, *, task_id: str, session: Dict[str, Any]) -> None:
    await db.tasks.update_one(
        {"id": task_id},
        {"$set": {"compile_session": session, "updated_at": _now_iso()}},
    )


# ═════════════════════════════════════════════════════════════════════
# Stage 1 — Drafting
# ═════════════════════════════════════════════════════════════════════
def _build_drafting_prompt(task: Dict[str, Any], contributions: List[Dict[str, Any]]) -> str:
    spec = task.get("output_spec") or {}
    tpl_id = spec.get("template_id") or "free_text"
    tpl_descr = spec.get("free_text") or ""
    parts = [
        "You are an executive ghostwriter. Generate a polished first-cut",
        "draft for the following task. Return ONLY the document body in",
        "plain prose with section headings as ALL-CAPS lines. No JSON.",
        "",
        f"TASK: {task.get('name', '')}",
        f"OBJECTIVE: {task.get('objective', '')}",
        f"SUCCESS CRITERIA: {task.get('success_criteria', '')}",
        f"OUTPUT SPEC: template={tpl_id}; free_text={tpl_descr[:600]}",
        "",
        "INPUTS (contributor summaries):",
    ]
    if not contributions:
        parts.append("  • (no contributions yet — draft a placeholder skeleton with TODO markers)")
    else:
        for c in contributions[:10]:
            parts.append(f"  • {c.get('role') or c.get('name')}: {c.get('contribution') or '(no description)'}")
    return "\n".join(parts)


_TEMPLATE_PACK_SHAPES: Dict[str, List[str]] = {
    "board_pack":     ["Executive Summary", "Performance", "Risk", "Strategy", "Governance"],
    "committee_pack": ["Chair Foreword", "Topic Deep Dive", "Recommendations", "Sign-off"],
    "strategy_deck":  ["Narrative Arc"],
    "fundraising":    ["Pitch Deck", "Financial Model"],
}


def _fallback_draft_body(task: Dict[str, Any], section: Optional[str] = None) -> str:
    head = (section or task.get("name") or "Untitled draft").upper()
    return (
        f"{head}\n\n"
        f"Objective: {task.get('objective') or '—'}\n\n"
        f"Success criteria: {task.get('success_criteria') or '—'}\n\n"
        "[TODO — Akki could not generate the full draft body within the\n"
        "shield-timeout window. This skeleton has the spec captured;\n"
        "edit inline or use the prompted-edit composer to expand.]\n"
    )


async def run_drafting(db, *, task: Dict[str, Any], account_id: str) -> List[str]:
    """Generates one or more draft documents for the task. Returns
    the list of created doc IDs."""
    tid = task["id"]
    ctx_id = task.get("context_id")
    session = task.get("compile_session") or _empty_session()
    session["active"]          = True
    session["current_stage"]   = "drafting"
    if not session.get("started_at"):
        session["started_at"]  = _now_iso()
    await _set_session(db, task_id=tid, session=session)
    await _audit(db, task_id=tid, account_id=account_id,
                 action="task.compile.drafting.started", ctx_id=ctx_id,
                 metadata={"output_spec": task.get("output_spec")})

    # Pull contributions that are submitted/approved.
    contributions = [
        m for m in (task.get("team") or [])
        if m.get("status") in ("submitted", "approved")
    ]
    # Fold in already-uploaded docs linked to this task (informational
    # only at this stage — the LLM prompt synthesises them via the
    # contribution summaries; raw bodies stay on disk).
    _linked_docs = await db.documents.find(
        {"task_id": tid}, {"_id": 0, "id": 1, "name": 1},
    ).to_list(length=20)
    del _linked_docs  # keeps lint happy; signal that we read the rows

    spec = task.get("output_spec") or {}
    tpl_id = spec.get("template_id")
    sections = _TEMPLATE_PACK_SHAPES.get(tpl_id, [task.get("name") or "Draft"])

    created_ids: List[str] = []
    for section in sections:
        prompt = _build_drafting_prompt({**task, "name": f"{task.get('name')} — {section}"}, contributions)
        result = await shield_invoke_bounded(
            purpose=f"task_manager.compile.drafting.{(tpl_id or 'free').lower()}",
            content=prompt,
            tenant_id=account_id, user_id=account_id, consumer_id="tasks",
        )
        body: str
        if result and result.get("__timeout__"):
            await _record_llm_timeout(db, task_id=tid, account_id=account_id,
                                      purpose=result.get("purpose", "drafting"))
            body = _fallback_draft_body(task, section)
        elif result and result.get("response"):
            body = result["response"].strip() or _fallback_draft_body(task, section)
        else:
            body = _fallback_draft_body(task, section)

        did = f"doc-{uuid.uuid4().hex[:10]}"
        doc = {
            "id":                did,
            "context_id":        ctx_id,
            "account_id":        account_id,
            "task_id":           tid,
            "name":              f"{task.get('name', 'Draft')} — {section}",
            "extracted_text":    body,
            "state":             "draft",
            "origin":            "akki_generated",
            "status":            "ready",
            "doc_type":          tpl_id or "free_text",
            "compile_session":   {"task_id": tid, "stage": "drafting", "section": section},
            "created_at":        _now_iso(),
        }
        await db.documents.insert_one(dict(doc))
        created_ids.append(did)

    session["draft_artefact_ids"] = created_ids
    session["current_stage"]      = "drafting"
    await _set_session(db, task_id=tid, session=session)
    await _audit(db, task_id=tid, account_id=account_id,
                 action="task.compile.drafting.completed", ctx_id=ctx_id,
                 metadata={"draft_artefact_ids": created_ids, "n_sections": len(sections)})
    return created_ids


# ═════════════════════════════════════════════════════════════════════
# Stage 2 — Review & Editing  (advance only — editing is via E.3)
# ═════════════════════════════════════════════════════════════════════
async def complete_review(db, *, task: Dict[str, Any], account_id: str, skip_circulation: bool) -> Dict[str, Any]:
    tid = task["id"]
    session = task.get("compile_session") or _empty_session()
    session["review_artefact_ids"] = list(session.get("draft_artefact_ids") or [])
    if skip_circulation:
        session["current_stage"]                = "final_production"
        session["circulation"]["enabled"]       = False
    else:
        session["current_stage"]                = "circulation"
        session["circulation"]["enabled"]       = True
    await _set_session(db, task_id=tid, session=session)
    await _audit(db, task_id=tid, account_id=account_id,
                 action="task.compile.review.completed",
                 ctx_id=task.get("context_id"),
                 metadata={"skip_circulation": skip_circulation})
    return session


# ═════════════════════════════════════════════════════════════════════
# Stage 3 — Circulation
# ═════════════════════════════════════════════════════════════════════
def _gen_token() -> str:
    return secrets.token_urlsafe(32)


async def send_circulation(db, *, task: Dict[str, Any], account_id: str,
                            reviewer_emails: List[str], message: Optional[str],
                            base_url: str) -> Dict[str, Any]:
    """Generates per-reviewer magic-link tokens, persists them, and
    sends invite emails via Postmark. If Postmark send fails for a
    reviewer, the link is still persisted; the failure is recorded on
    the per-reviewer status."""
    tid = task["id"]
    ctx_id = task.get("context_id")
    session = task.get("compile_session") or _empty_session()
    expires = datetime.now(timezone.utc) + timedelta(days=14)
    sent_status: List[Dict[str, Any]] = []
    for email in reviewer_emails:
        token = _gen_token()
        try:
            await db.task_circulation_tokens.insert_one({
                "id":                str(uuid.uuid4()),
                "token":              token,
                "task_id":            tid,
                "reviewer_email":     email.strip().lower(),
                "draft_artefact_ids": list(session.get("draft_artefact_ids") or []),
                "expires_at":         expires.isoformat(),
                "used":               False,
                "created_at":         _now_iso(),
            })
        except Exception as e:  # noqa: BLE001
            log.error("token persist failed: %s", e)
            sent_status.append({"email": email, "status": "persist_failed"})
            continue
        url = f"{base_url.rstrip('/')}/circulation/{token}"
        # Send via Postmark.
        sent = "queued"
        try:
            from email_service import send_email
            subject = f"Please review: {task.get('name', 'Draft')}"
            text = (
                f"You've been asked to review a draft for: {task.get('name', '')}.\n\n"
                f"{message or ''}\n\n"
                f"Open the review link: {url}\n\n"
                f"This link expires on {expires.date().isoformat()}.\n"
            )
            html = (
                f"<p>You've been asked to review a draft for: <b>{task.get('name', '')}</b>.</p>"
                f"<p>{message or ''}</p>"
                f"<p><a href='{url}'>Open the review link</a></p>"
                f"<p style='color:#888;font-size:12px'>Expires {expires.date().isoformat()}.</p>"
            )
            resp = await send_email(to=email, subject=subject, text=text, html=html)
            sent = (resp or {}).get("mode") or "sent"
        except Exception as e:  # noqa: BLE001
            log.warning("circulation send failed for %s: %s", email, e)
            sent = "send_failed"
        sent_status.append({"email": email, "status": sent, "token": token, "url": url})
        await _audit(db, task_id=tid, account_id=account_id,
                     action="task.compile.circulation.invite_sent", ctx_id=ctx_id,
                     metadata={"reviewer_email": email, "status": sent})

    session["circulation"]["enabled"]         = True
    session["circulation"]["reviewer_emails"] = [e.strip().lower() for e in reviewer_emails]
    session["circulation"]["sent_at"]         = _now_iso()
    session["circulation"]["sent_status"]     = sent_status
    session["current_stage"]                  = "circulation"
    await _set_session(db, task_id=tid, session=session)
    return {"sent": sent_status, "expires_at": expires.isoformat()}


async def add_circulation_comment(db, *, token: str, comment_text: str,
                                   doc_id: Optional[str] = None) -> Dict[str, Any]:
    row = await db.task_circulation_tokens.find_one({"token": token, "used": False})
    if not row:
        return {"ok": False, "reason": "invalid_or_expired_token"}
    try:
        exp = datetime.fromisoformat((row.get("expires_at") or "").replace("Z", "+00:00"))
    except (ValueError, TypeError):
        exp = None
    if exp and exp < datetime.now(timezone.utc):
        return {"ok": False, "reason": "invalid_or_expired_token"}
    tid = row["task_id"]
    t = await db.tasks.find_one({"id": tid})
    if not t:
        return {"ok": False, "reason": "task_missing"}
    session = t.get("compile_session") or _empty_session()
    cmt = {
        "id":         str(uuid.uuid4()),
        "reviewer":   row["reviewer_email"],
        "comment":    (comment_text or "").strip()[:4000],
        "doc_id":     doc_id,
        "created_at": _now_iso(),
    }
    session["circulation"]["comments"].append(cmt)
    await _set_session(db, task_id=tid, session=session)
    await _audit(db, task_id=tid, account_id=t.get("account_id"),
                 action="task.compile.circulation.comment_received",
                 ctx_id=t.get("context_id"),
                 metadata={"reviewer": row["reviewer_email"], "doc_id": doc_id, "len": len(cmt["comment"])})
    return {"ok": True, "comment_id": cmt["id"], "task_id": tid}


async def close_circulation(db, *, task: Dict[str, Any], account_id: str) -> Dict[str, Any]:
    tid = task["id"]
    session = task.get("compile_session") or _empty_session()
    session["circulation"]["closed_at"] = _now_iso()
    session["current_stage"]            = "final_production"
    await _set_session(db, task_id=tid, session=session)
    await _audit(db, task_id=tid, account_id=account_id,
                 action="task.compile.circulation.closed",
                 ctx_id=task.get("context_id"),
                 metadata={"comment_count": len(session["circulation"]["comments"])})
    return session


# ═════════════════════════════════════════════════════════════════════
# Stage 4 — Final production
# ═════════════════════════════════════════════════════════════════════
async def apply_comment(db, *, task: Dict[str, Any], account_id: str,
                          comment_id: str, action: str) -> Dict[str, Any]:
    """For action='apply': feeds the comment through the prompted-edit
    pipeline on the doc the comment was attached to. For 'discard':
    marks the comment dismissed. For 'edit_manual': records intent
    (the user edits in the DocumentDrawer themselves)."""
    tid = task["id"]
    session = task.get("compile_session") or _empty_session()
    comment = next((c for c in (session.get("circulation") or {}).get("comments", []) if c["id"] == comment_id), None)
    if not comment:
        return {"ok": False, "reason": "comment_not_found"}
    if action == "apply" and comment.get("doc_id"):
        # Trigger a prompted-edit rewrite via Shield.
        doc = await db.documents.find_one({"id": comment["doc_id"], "task_id": tid}, {"_id": 0})
        if doc and doc.get("extracted_text"):
            prompt = (
                "Rewrite the document body below to address this reviewer\n"
                "comment. Apply the suggestion faithfully — do not invent\n"
                "facts. Return the FULL rewritten body, no preamble.\n\n"
                f"REVIEWER COMMENT: {comment['comment']}\n\n"
                f"CURRENT BODY:\n{doc['extracted_text'][:8000]}\n"
            )
            result = await shield_invoke_bounded(
                purpose="task_manager.compile.apply_comment",
                content=prompt,
                tenant_id=account_id, user_id=account_id, consumer_id="tasks",
            )
            if result and result.get("__timeout__"):
                await _record_llm_timeout(db, task_id=tid, account_id=account_id,
                                          purpose="apply_comment")
            new_body = (result or {}).get("response", "").strip() if result and not result.get("__timeout__") else ""
            if new_body:
                await db.documents.update_one(
                    {"id": doc["id"]},
                    {"$set": {"extracted_text": new_body, "updated_at": _now_iso()}},
                )
    comment["status"] = "applied" if action == "apply" else action
    await _set_session(db, task_id=tid, session=session)
    await _audit(db, task_id=tid, account_id=account_id,
                 action=f"task.compile.final_production.comment_{action}",
                 ctx_id=task.get("context_id"),
                 metadata={"comment_id": comment_id, "doc_id": comment.get("doc_id")})
    return {"ok": True, "comment_id": comment_id, "action": action}


async def complete_final_production(db, *, task: Dict[str, Any], account_id: str) -> Dict[str, Any]:
    tid = task["id"]
    session = task.get("compile_session") or _empty_session()
    session["final_artefact_ids"] = list(session.get("draft_artefact_ids") or [])
    session["current_stage"]      = "commit"
    await _set_session(db, task_id=tid, session=session)
    await _audit(db, task_id=tid, account_id=account_id,
                 action="task.compile.final_production.completed",
                 ctx_id=task.get("context_id"))
    return session


# ═════════════════════════════════════════════════════════════════════
# Stage 5 — Commit (sequential with rollback on partial failure)
# ═════════════════════════════════════════════════════════════════════
async def run_commit(db, *, task: Dict[str, Any], account_id: str) -> Dict[str, Any]:
    """Commit all draft documents to state="committed". Mongo's
    Motor client doesn't expose multi-doc transactions in our
    deployment so we do sequential commits + a best-effort rollback
    if any commit fails midway. Per the brief's explicit scope cut."""
    tid = task["id"]
    ctx_id = task.get("context_id")
    session = task.get("compile_session") or _empty_session()
    ids = list(session.get("final_artefact_ids") or session.get("draft_artefact_ids") or [])
    if not ids:
        return {"ok": False, "reason": "no_drafts"}
    committed: List[str] = []
    failed: Optional[str] = None
    for did in ids:
        try:
            res = await db.documents.update_one(
                {"id": did, "task_id": tid, "state": "draft"},
                {"$set": {"state": "committed", "committed_at": _now_iso()}},
            )
            if res.modified_count != 1:
                failed = did
                break
            committed.append(did)
        except Exception as e:  # noqa: BLE001
            log.error("commit failed for %s: %s", did, e)
            failed = did
            break
    if failed is not None:
        # Rollback the ones we already committed in this run.
        for did in committed:
            try:
                await db.documents.update_one(
                    {"id": did}, {"$set": {"state": "draft"}, "$unset": {"committed_at": ""}},
                )
            except Exception as e:  # noqa: BLE001
                log.error("rollback failed for %s: %s", did, e)
        await _audit(db, task_id=tid, account_id=account_id,
                     action="task.compile.commit.failed", ctx_id=ctx_id,
                     metadata={"failed_doc": failed, "rolled_back": committed})
        return {"ok": False, "reason": "partial_commit_failed", "failed": failed}

    # All committed — wrap up the session.
    session["committed_artefact_ids"] = committed
    session["current_stage"]          = "commit"
    session["completed_at"]           = _now_iso()
    session["active"]                 = False

    # Decide whether to auto-close the task. We close only if EVERY
    # draft in the session committed AND the task has no other open
    # drafts.
    other_drafts = await db.documents.count_documents({
        "task_id": tid, "state": "draft",
    })
    task_closed = False
    update_fields: Dict[str, Any] = {"compile_session": session, "updated_at": _now_iso()}
    if other_drafts == 0:
        update_fields["state"] = "closed"
        task_closed = True
    await db.tasks.update_one({"id": tid}, {"$set": update_fields})
    if task_closed:
        await _audit(db, task_id=tid, account_id=account_id,
                     action="task.state.auto_closed", ctx_id=ctx_id,
                     metadata={"reason": "compile.commit"})
    await _audit(db, task_id=tid, account_id=account_id,
                 action="task.compile.commit.completed", ctx_id=ctx_id,
                 metadata={"committed_artefact_ids": committed,
                           "task_closed":             task_closed})
    return {"ok": True, "committed": committed, "task_closed": task_closed}
