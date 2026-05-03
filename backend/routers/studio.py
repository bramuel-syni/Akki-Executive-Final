"""Studio · cross-artefact endpoints (decks, briefings, reports).

iter64 — the merged Decks + Reports surface needs:
  - Read-receipt tracking on every Studio artefact (deduped per
    account-day, like document_engagement.views).
  - Exposure score derived from reader count + shares + age.
  - A single 'history' endpoint that returns every Studio artefact
    (decks + briefings) for a context with sensitivity + exposure
    surfaced inline so the UI can render the strip.
  - On-demand re-scoring endpoint (sensitivity heuristics may evolve).

Pattern mirrors document_engagement.py so the testing agent + ops can
reason about it the same way. Read-tracking is real for all plans;
"information exposure score" surfaces as a marketing differentiator
but is computed for everyone — the gating happens at UI level if we
need to. (User chose option a — "build it now with a real read-receipt
mechanism + visible exposure score on each generated artifact".)
"""
from __future__ import annotations

import hashlib
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field

from core import JWT_SECRET, db, iso, now, require_context_membership

logger = logging.getLogger("akki.studio")

router = APIRouter(tags=["studio"])

ARTEFACT_KINDS = {"deck", "briefing"}


# ---------------------------------------------------------------------------
# Public sensitivity demo — no auth, no DB write. Powers the landing-page
# "paste a snippet to see how AKKI classifies it" demo.
# Throttled by a tiny in-memory rate limit; not a security boundary, just
# a courtesy so the marketing surface doesn't melt under load.
# ---------------------------------------------------------------------------
_DEMO_LAST_CALL: Dict[str, float] = {}
_DEMO_RATE_WINDOW_S = 1.5  # one call per 1.5s per IP


class DemoSensitivityIn(BaseModel):
    text: str = Field(min_length=4, max_length=4000)


@router.post("/api/public/studio/sensitivity-demo")
async def public_sensitivity_demo(body: DemoSensitivityIn, request: Request):
    import time
    # Rate limit per IP — best-effort, single-process. Sufficient for a
    # marketing-page demo; the scorer itself is regex-only so the cost is
    # microseconds, but we don't want one curl loop hammering it.
    # iter65 — k8s ingress can present multiple proxy nodes; we prefer the
    # X-Forwarded-For first hop when available so the bucket maps to the
    # original caller rather than the changing proxy IP.
    xff = request.headers.get("x-forwarded-for", "") or ""
    ip = xff.split(",")[0].strip() if xff else ""
    if not ip:
        ip = (request.client.host if request.client else "anon") or "anon"
    now_s = time.time()
    last = _DEMO_LAST_CALL.get(ip, 0)
    if now_s - last < _DEMO_RATE_WINDOW_S:
        raise HTTPException(status_code=429, detail="Slow down a moment.")
    _DEMO_LAST_CALL[ip] = now_s

    from studio_sensitivity import score_sensitivity
    fake_artefact = {"intent": body.text, "title": "Demo"}
    result = score_sensitivity(fake_artefact)
    return {"sensitivity": result, "input_chars": len(body.text)}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _utc_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _days_between(start_iso: str, end_iso: Optional[str] = None) -> int:
    try:
        start = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
        end = (datetime.fromisoformat(end_iso.replace("Z", "+00:00"))
               if end_iso else datetime.now(timezone.utc))
        return max(0, (end - start).days)
    except Exception:  # noqa: BLE001
        return 0


async def _resolve_artefact(context_id: str, kind: str, artefact_id: str) -> Dict[str, Any]:
    if kind not in ARTEFACT_KINDS:
        raise HTTPException(status_code=400, detail=f"Unsupported artefact kind: {kind}")
    coll = db.decks if kind == "deck" else db.briefings
    doc = await coll.find_one({"id": artefact_id, "context_id": context_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail=f"{kind.title()} not found.")
    return doc


# ---------------------------------------------------------------------------
# Read receipt — POST /api/contexts/{cid}/studio/{kind}/{aid}/view
# ---------------------------------------------------------------------------
@router.post("/api/contexts/{context_id}/studio/{kind}/{artefact_id}/view")
async def record_view(
    context_id: str,
    kind: str,
    artefact_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    artefact = await _resolve_artefact(context_id, kind, artefact_id)
    today = _utc_today()
    account_id = ctx["account"]["id"]
    is_owner = artefact.get("account_id") == account_id or artefact.get("created_by") == account_id

    # Upsert one row per (artefact, account, day). Duplicate insert hits the
    # unique index and the resulting Mongo retry pattern gives us idempotency.
    res = await db.studio_views.find_one_and_update(
        {"artefact_kind": kind, "artefact_id": artefact_id,
         "context_id": context_id, "account_id": account_id, "day_utc": today},
        {"$inc": {"view_count": 1},
         "$setOnInsert": {
             "id": str(uuid.uuid4()),
             "first_viewed_at": iso(now()),
             "is_owner": is_owner,
         },
         "$set": {"last_viewed_at": iso(now())}},
        upsert=True,
        return_document=True,
        projection={"_id": 0},
    )
    return {
        "ok": True,
        "deduped": (res or {}).get("view_count", 1) > 1,
        "is_owner": is_owner,
    }


# ---------------------------------------------------------------------------
# Engagement summary — GET /api/contexts/{cid}/studio/{kind}/{aid}/engagement
# ---------------------------------------------------------------------------
@router.get("/api/contexts/{context_id}/studio/{kind}/{artefact_id}/engagement")
async def get_engagement(
    context_id: str,
    kind: str,
    artefact_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    artefact = await _resolve_artefact(context_id, kind, artefact_id)

    # All views — owner views excluded from unique_readers but included in
    # view_count so the artefact creator can see their own check-ins.
    views = await db.studio_views.find(
        {"artefact_kind": kind, "artefact_id": artefact_id, "context_id": context_id},
        {"_id": 0},
    ).to_list(length=500)

    non_owner_views = [v for v in views if not v.get("is_owner")]
    unique_readers = len({v["account_id"] for v in non_owner_views})
    total_view_count = sum((v.get("view_count") or 1) for v in views)

    # iter66 — plan gating. Free users see the COUNT of unique readers
    # (so they understand exposure) but not the full PII list.
    # Pro/Team accounts see the full readers[] with names + emails.
    plan = (ctx["account"].get("plan") or "free").lower()
    show_full_readers = plan in ("pro", "team")

    readers: List[Dict[str, Any]] = []
    if show_full_readers:
        # Pull reader display names (best-effort, public-safe fields only).
        reader_account_ids = list({v["account_id"] for v in non_owner_views})
        reader_docs = await db.accounts.find(
            {"id": {"$in": reader_account_ids}},
            {"_id": 0, "id": 1, "name": 1, "email": 1},
        ).to_list(length=200) if reader_account_ids else []
        reader_map = {a["id"]: a for a in reader_docs}
        for v in non_owner_views:
            a = reader_map.get(v["account_id"], {})
            readers.append({
                "account_id": v["account_id"],
                "name": a.get("name") or "—",
                "email": a.get("email") or "—",
                "first_viewed_at": v.get("first_viewed_at"),
                "last_viewed_at": v.get("last_viewed_at"),
                "view_count": v.get("view_count", 1),
            })
        readers.sort(key=lambda r: r.get("last_viewed_at") or "", reverse=True)

    # Shares: reuse existing shares collection for briefings; for decks
    # we look at studio_shares (recorded explicitly when a user shares a
    # deck out via the studio share endpoint, optional — defaults to 0).
    shares = await db.studio_shares.count_documents(
        {"artefact_kind": kind, "artefact_id": artefact_id, "context_id": context_id}
    )
    external_shares = await db.studio_shares.count_documents(
        {"artefact_kind": kind, "artefact_id": artefact_id, "context_id": context_id, "external": True}
    )

    # Compute exposure score
    days = _days_between(artefact.get("created_at") or iso(now()))
    from studio_sensitivity import exposure_score
    expo = exposure_score(
        unique_readers=unique_readers,
        share_count=shares,
        external_share_count=external_shares,
        days_since_creation=days,
    )

    return {
        "artefact_kind": kind,
        "artefact_id": artefact_id,
        "view_count": total_view_count,
        "unique_readers": unique_readers,
        "readers": readers,
        "readers_locked": not show_full_readers,
        "plan": plan,
        "share_count": shares,
        "external_share_count": external_shares,
        "exposure": expo,
        "days_since_creation": days,
        "sensitivity": artefact.get("sensitivity"),
    }


# ---------------------------------------------------------------------------
# Share record — POST /api/contexts/{cid}/studio/{kind}/{aid}/share
# ---------------------------------------------------------------------------
class ShareIn(BaseModel):
    to_email: str = Field(min_length=4, max_length=120)
    to_name: Optional[str] = Field(default=None, max_length=120)
    message: Optional[str] = Field(default=None, max_length=600)
    external: bool = Field(default=False, description="True if recipient is outside the org")


@router.post("/api/contexts/{context_id}/studio/{kind}/{artefact_id}/share")
async def record_share(
    context_id: str,
    kind: str,
    artefact_id: str,
    body: ShareIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    await _resolve_artefact(context_id, kind, artefact_id)
    rec = {
        "id": str(uuid.uuid4()),
        "artefact_kind": kind,
        "artefact_id": artefact_id,
        "context_id": context_id,
        "shared_by": ctx["account"]["id"],
        "to_email": body.to_email.strip().lower(),
        "to_name": body.to_name,
        "message": body.message,
        "external": bool(body.external),
        "created_at": iso(now()),
    }
    await db.studio_shares.insert_one(rec)
    rec.pop("_id", None)
    return rec


# ---------------------------------------------------------------------------
# Re-score — POST /api/contexts/{cid}/studio/{kind}/{aid}/rescore
# ---------------------------------------------------------------------------
@router.post("/api/contexts/{context_id}/studio/{kind}/{artefact_id}/rescore")
async def rescore_sensitivity(
    context_id: str,
    kind: str,
    artefact_id: str,
    use_llm: bool = False,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Re-score an artefact's sensitivity. `use_llm=true` invokes the LLM
    tiebreaker (iter66) — only escalates when regex returns the ambiguous
    'internal' band; never downgrades. Costs one standard-tier LLM call
    when triggered."""
    artefact = await _resolve_artefact(context_id, kind, artefact_id)
    if use_llm:
        from studio_sensitivity import score_sensitivity_with_llm_tiebreaker
        sensitivity = await score_sensitivity_with_llm_tiebreaker(artefact)
    else:
        from studio_sensitivity import score_sensitivity
        sensitivity = score_sensitivity(artefact)
    coll = db.decks if kind == "deck" else db.briefings
    await coll.update_one(
        {"id": artefact_id, "context_id": context_id},
        {"$set": {"sensitivity": sensitivity, "sensitivity_rescored_at": iso(now())}},
    )
    return {"sensitivity": sensitivity, "artefact_kind": kind, "artefact_id": artefact_id}


@router.post("/api/contexts/{context_id}/studio/backfill_sensitivity")
async def backfill_sensitivity(
    context_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """One-shot backfill — score every deck + briefing in a context that
    doesn't already carry a sensitivity record. Idempotent: artefacts
    that already have `sensitivity` are skipped. Useful after iter64 ships
    so the UI can render the strip on day-1 without waiting for a regen."""
    from studio_sensitivity import score_sensitivity
    scored = {"decks": 0, "briefings": 0}

    async for d in db.decks.find(
        {"context_id": context_id, "sensitivity": {"$exists": False}},
        {"_id": 0},
    ):
        sens = score_sensitivity(d)
        await db.decks.update_one(
            {"id": d["id"], "context_id": context_id},
            {"$set": {"sensitivity": sens, "sensitivity_rescored_at": iso(now())}},
        )
        scored["decks"] += 1

    async for b in db.briefings.find(
        {"context_id": context_id, "sensitivity": {"$exists": False}, "status": {"$ne": "archived"}},
        {"_id": 0},
    ):
        sens = score_sensitivity(b)
        await db.briefings.update_one(
            {"id": b["id"], "context_id": context_id},
            {"$set": {"sensitivity": sens, "sensitivity_rescored_at": iso(now())}},
        )
        scored["briefings"] += 1

    return {"ok": True, "scored": scored}


# ---------------------------------------------------------------------------
# History — GET /api/contexts/{cid}/studio/history
# Returns every deck + briefing for a context with sensitivity + exposure
# folded in, sorted newest-first. Single endpoint the Studio history strip
# can hit.
# ---------------------------------------------------------------------------
@router.get("/api/contexts/{context_id}/studio/history")
async def studio_history(
    context_id: str,
    limit: int = 30,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    items: List[Dict[str, Any]] = []

    decks_cursor = db.decks.find(
        {"context_id": context_id},
        {"_id": 0, "id": 1, "title": 1, "intent": 1, "subtitle": 1,
         "created_at": 1, "tier": 1, "sensitivity": 1, "audience": 1,
         "research_question": 1, "account_id": 1},
    ).sort("created_at", -1).limit(limit)
    async for d in decks_cursor:
        items.append({**d, "kind": "deck"})

    briefings_cursor = db.briefings.find(
        {"context_id": context_id, "status": {"$ne": "archived"}},
        {"_id": 0, "id": 1, "title": 1, "version": 1, "opening_paragraph": 1,
         "items": 1, "created_at": 1, "sensitivity": 1, "role": 1,
         "mode": 1, "created_by": 1},
    ).sort("created_at", -1).limit(limit)
    async for b in briefings_cursor:
        items.append({
            "id": b.get("id"),
            "title": b.get("title"),
            "intent": (b.get("opening_paragraph") or "")[:200],
            "subtitle": f"{len(b.get('items') or [])} items · v{b.get('version', 1)}",
            "created_at": b.get("created_at"),
            "tier": "standard",
            "sensitivity": b.get("sensitivity"),
            "audience": b.get("role"),
            "research_question": None,
            "account_id": b.get("created_by"),
            "kind": "briefing",
            "mode": b.get("mode"),
        })

    items.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    items = items[:limit]

    # Cheap fan-out for engagement: for each item we tally view + share
    # counts in a single aggregate pass (one query per collection).
    artefact_ids = [i["id"] for i in items]
    if artefact_ids:
        # Group views by (kind, id, account_id) → unique_readers per artefact
        view_pipeline = [
            {"$match": {"artefact_id": {"$in": artefact_ids}, "context_id": context_id,
                        "is_owner": {"$ne": True}}},
            {"$group": {"_id": {"kind": "$artefact_kind", "id": "$artefact_id",
                                 "acct": "$account_id"}}},
            {"$group": {"_id": {"kind": "$_id.kind", "id": "$_id.id"},
                         "unique_readers": {"$sum": 1}}},
        ]
        readers_by_id: Dict[str, int] = {}
        async for row in db.studio_views.aggregate(view_pipeline):
            readers_by_id[row["_id"]["id"]] = row["unique_readers"]

        share_pipeline = [
            {"$match": {"artefact_id": {"$in": artefact_ids}, "context_id": context_id}},
            {"$group": {"_id": {"id": "$artefact_id"},
                         "shares": {"$sum": 1},
                         "external_shares": {"$sum": {"$cond": ["$external", 1, 0]}}}},
        ]
        shares_by_id: Dict[str, Dict[str, int]] = {}
        async for row in db.studio_shares.aggregate(share_pipeline):
            shares_by_id[row["_id"]["id"]] = {
                "shares": row.get("shares", 0),
                "external_shares": row.get("external_shares", 0),
            }

        from studio_sensitivity import exposure_score
        for it in items:
            uniq = readers_by_id.get(it["id"], 0)
            sh = shares_by_id.get(it["id"], {}).get("shares", 0)
            ext_sh = shares_by_id.get(it["id"], {}).get("external_shares", 0)
            days = _days_between(it.get("created_at") or iso(now()))
            it["exposure"] = exposure_score(
                unique_readers=uniq, share_count=sh,
                external_share_count=ext_sh, days_since_creation=days,
            )
            it["unique_readers"] = uniq

    return {"items": items, "count": len(items)}


# ---------------------------------------------------------------------------
# Share with the chair — email a Studio artefact with a tracked deep-link.
# POST /api/contexts/{cid}/studio/{kind}/{aid}/share-email
#
# Pattern:
#   1. Auth caller records a studio_shares row (external=true).
#   2. We sign a JWT { kind, aid, cid, email, sid } with 14-day TTL.
#   3. Email via Resend carries a tracked link:
#        {FRONTEND_URL}/api/public/studio/track/{token}
#      which, on click, records a studio_views row keyed on
#      account_id = 'external:<sha256(email)>' (synthetic) so the same
#      recipient opening multiple times still counts once in unique_readers.
#      Then redirects to the in-app deep link (decks or briefings).
#
# Exposure score picks up the new reader automatically via the existing
# aggregation — no scorer changes needed.
# ---------------------------------------------------------------------------
_SHARE_TOKEN_TTL_DAYS = 30
_SHARE_TOKEN_ALGO = "HS256"


def _external_account_id(email: str) -> str:
    h = hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()[:24]
    return f"external:{h}"


def _sign_share_token(payload: Dict[str, Any]) -> str:
    exp = datetime.now(timezone.utc) + timedelta(days=_SHARE_TOKEN_TTL_DAYS)
    body = {**payload, "exp": int(exp.timestamp()), "purpose": "studio_share"}
    return jwt.encode(body, JWT_SECRET, algorithm=_SHARE_TOKEN_ALGO)


def _decode_share_token(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[_SHARE_TOKEN_ALGO])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=410, detail="This share link has expired.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=400, detail="Invalid share link.")
    if payload.get("purpose") != "studio_share":
        raise HTTPException(status_code=400, detail="Invalid share link.")
    return payload


def _render_share_artefact_email_html(
    *,
    recipient_name: Optional[str],
    sender_name: str,
    context_name: str,
    artefact_kind: str,
    artefact_title: str,
    sensitivity_label: Optional[str],
    message: Optional[str],
    tracked_url: str,
) -> str:
    kind_label = "deck" if artefact_kind == "deck" else "briefing"
    greet = f"Hi {recipient_name}," if recipient_name else "Hi,"
    msg_html = ""
    if message and message.strip():
        safe = message.strip().replace("\n", "<br>")
        msg_html = (
            '<tr><td style="padding:0 36px 12px 36px;">'
            f'<p style="margin:0 0 4px 0;font-size:11px;text-transform:uppercase;letter-spacing:0.12em;color:#8b6f47;font-weight:600;">A note from {sender_name}</p>'
            f'<p style="margin:0 0 4px 0;font-size:15px;line-height:1.55;color:#2A2622;font-style:italic;">“{safe}”</p>'
            '</td></tr>'
        )
    sens_chip = ""
    if sensitivity_label:
        sens_chip = (
            f'<span style="display:inline-block;margin-left:6px;padding:2px 8px;border:1px solid #E8E0D0;'
            f'font-size:10px;text-transform:uppercase;letter-spacing:0.14em;color:#8B2E2B;">'
            f'{sensitivity_label}</span>'
        )
    return f"""
<!doctype html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#F7F3EA;font-family:-apple-system,BlinkMacSystemFont,Helvetica,Arial,sans-serif;color:#2A2622;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#F7F3EA;padding:40px 20px;">
    <tr><td align="center">
      <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;background:#ffffff;border:1px solid #E8E0D0;">
        <tr><td style="padding:32px 36px 16px 36px;border-bottom:3px solid #8B2E2B;">
          <p style="margin:0;font-size:11px;text-transform:uppercase;letter-spacing:0.18em;color:#8B2E2B;font-weight:600;">AKKI · Studio share{sens_chip}</p>
          <h1 style="margin:10px 0 0 0;font-family:Georgia,serif;font-size:24px;line-height:1.25;color:#1a1a1a;font-weight:normal;">{artefact_title}</h1>
          <p style="margin:6px 0 0 0;font-size:12.5px;color:#8b6f47;">{context_name} · {kind_label}</p>
        </td></tr>
        <tr><td style="padding:22px 36px 4px 36px;font-size:15px;line-height:1.6;color:#2A2622;">
          <p style="margin:0 0 12px 0;">{greet}</p>
          <p style="margin:0 0 12px 0;"><strong>{sender_name}</strong> has shared this {kind_label} with you through AKKI. Follow the link below to read it — your visit will be recorded so {sender_name} knows you've seen it.</p>
        </td></tr>
        {msg_html}
        <tr><td style="padding:12px 36px 28px 36px;">
          <a href="{tracked_url}" style="display:inline-block;padding:12px 22px;background:#8B2E2B;color:#ffffff;text-decoration:none;font-size:14px;font-weight:500;letter-spacing:0.02em;border-radius:4px;">Open the {kind_label}</a>
          <p style="margin:14px 0 0 0;font-size:11.5px;color:#8b6f47;line-height:1.55;">This link is valid for 14 days. Do not forward — it's tagged to you.</p>
        </td></tr>
        <tr><td style="padding:18px 36px;border-top:1px solid #E8E0D0;background:#F9F6EE;">
          <p style="margin:0;font-size:11px;color:#8b6f47;line-height:1.5;">
            AKKI is the third party in this conversation. {sender_name} reviewed this before it was sent.
            AKKI doesn't read the content on your behalf — it only records that you opened it.
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>
"""


class ShareEmailIn(BaseModel):
    to_email: EmailStr
    to_name: Optional[str] = Field(default=None, max_length=120)
    message: Optional[str] = Field(default=None, max_length=600)


@router.post("/api/contexts/{context_id}/studio/{kind}/{artefact_id}/share-email")
async def share_artefact_by_email(
    context_id: str,
    kind: str,
    artefact_id: str,
    body: ShareEmailIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Email an artefact with a tracked deep link. Recipient clicks →
    records a view (external reader) + redirects to the in-app surface.
    External readers increment unique_readers and feed into exposure score."""
    artefact = await _resolve_artefact(context_id, kind, artefact_id)

    # Record the share first — source of truth even if email send fails.
    share_id = str(uuid.uuid4())
    share_rec = {
        "id": share_id,
        "artefact_kind": kind,
        "artefact_id": artefact_id,
        "context_id": context_id,
        "shared_by": ctx["account"]["id"],
        "to_email": body.to_email.lower(),
        "to_name": body.to_name,
        "message": body.message,
        "external": True,
        "delivery": "email",
        "created_at": iso(now()),
        "email_status": "pending",
    }
    await db.studio_shares.insert_one(share_rec)

    # Sign the tracking token.
    token = _sign_share_token({
        "kind": kind,
        "aid": artefact_id,
        "cid": context_id,
        "email": body.to_email.lower(),
        "sid": share_id,
    })

    frontend_url = (os.environ.get("FRONTEND_URL") or "").rstrip("/")
    # Public read-only viewer route — no auth required. Non-AKKI directors
    # can read the artefact inline; the viewer records the view via
    # /api/public/studio/read/{token} on mount.
    tracked_url = f"{frontend_url}/shared/{token}"

    # Resolve title + context label for the email body.
    artefact_title = artefact.get("title") or artefact.get("intent") or "Your shared document"
    ctx_doc = await db.contexts.find_one({"id": context_id}, {"_id": 0, "name": 1}) or {}
    context_name = ctx_doc.get("name") or "AKKI"
    sensitivity_label = (artefact.get("sensitivity") or {}).get("label")
    sender_name = ctx["account"].get("name") or ctx["account"].get("email") or "A colleague"
    sender_email = ctx["account"].get("email")

    # Fire email (Resend). email_service never raises.
    from email_service import send_email, configured as email_configured
    html = _render_share_artefact_email_html(
        recipient_name=body.to_name,
        sender_name=sender_name,
        context_name=context_name,
        artefact_kind=kind,
        artefact_title=artefact_title,
        sensitivity_label=sensitivity_label,
        message=body.message,
        tracked_url=tracked_url,
    )
    subject = f"{sender_name} shared a {kind} with you: {artefact_title}"
    send_res = await send_email(
        to=[body.to_email],
        subject=subject,
        html=html,
        reply_to=sender_email,
        from_executive_name=sender_name,
        tags=[{"name": "surface", "value": "studio_share"},
              {"name": "kind", "value": kind}],
    )

    # Persist outcome on the share record.
    await db.studio_shares.update_one(
        {"id": share_id},
        {"$set": {
            "email_status": send_res.get("mode") or "unknown",
            "email_send_id": send_res.get("id"),
            "email_error": send_res.get("error"),
            "email_configured": email_configured(),
        }},
    )

    return {
        "ok": bool(send_res.get("ok")) or send_res.get("mode") == "noop",
        "share_id": share_id,
        "email_mode": send_res.get("mode"),
        "email_configured": email_configured(),
        "tracked_url": tracked_url if not email_configured() else None,
        "to_email": body.to_email.lower(),
    }


# ---------------------------------------------------------------------------
# Public click tracker — GET /api/public/studio/track/{token}
# No auth. Records an external-reader view, redirects to in-app surface.
# ---------------------------------------------------------------------------
@router.get("/api/public/studio/track/{token}")
async def public_track_share(token: str, request: Request):
    payload = _decode_share_token(token)
    kind = payload.get("kind")
    aid = payload.get("aid")
    cid = payload.get("cid")
    email = (payload.get("email") or "").lower()
    if kind not in ARTEFACT_KINDS or not aid or not cid or not email:
        raise HTTPException(status_code=400, detail="Invalid share link.")

    # Artefact may have been deleted since the share was sent.
    artefact = await db.decks.find_one({"id": aid, "context_id": cid}, {"_id": 0, "id": 1}) \
        if kind == "deck" \
        else await db.briefings.find_one({"id": aid, "context_id": cid}, {"_id": 0, "id": 1})
    if not artefact:
        raise HTTPException(status_code=404, detail="This document is no longer available.")

    # Record the view. External readers collapse to one synthetic account_id
    # derived from the email hash, so re-opens dedupe just like logged-in users.
    today = _utc_today()
    account_id = _external_account_id(email)
    await db.studio_views.find_one_and_update(
        {"artefact_kind": kind, "artefact_id": aid,
         "context_id": cid, "account_id": account_id, "day_utc": today},
        {"$inc": {"view_count": 1},
         "$setOnInsert": {
             "id": str(uuid.uuid4()),
             "first_viewed_at": iso(now()),
             "is_owner": False,
             "is_external": True,
             "external_email": email,
         },
         "$set": {"last_viewed_at": iso(now())}},
        upsert=True,
    )

    # Mark the share as opened (first-open only).
    sid = payload.get("sid")
    if sid:
        await db.studio_shares.update_one(
            {"id": sid, "first_opened_at": {"$exists": False}},
            {"$set": {"first_opened_at": iso(now())}},
        )
    await db.studio_shares.update_one(
        {"id": sid} if sid else {"artefact_kind": kind, "artefact_id": aid, "to_email": email},
        {"$set": {"last_opened_at": iso(now())},
         "$inc": {"open_count": 1}},
    )

    # Redirect to the public read-only viewer. Both AKKI users and
    # non-AKKI directors land on the same surface — no signin wall.
    # AKKI users see an additional "Open in AKKI" affordance on the
    # viewer to jump into the full app surface if they want it.
    frontend_url = (os.environ.get("FRONTEND_URL") or "").rstrip("/")
    redirect = f"{frontend_url}/shared/{token}"
    return RedirectResponse(url=redirect, status_code=302)


# ---------------------------------------------------------------------------
# Public read-only artefact viewer — GET /api/public/studio/read/{token}
# No auth. Records an external-reader view (idempotent per day) AND returns
# the public-safe artefact content so the /shared/:token page can render.
# This removes the signin-wall friction introduced by iter68's share flow.
# ---------------------------------------------------------------------------
@router.get("/api/public/studio/read/{token}")
async def public_read_share(token: str, request: Request):
    payload = _decode_share_token(token)
    kind = payload.get("kind")
    aid = payload.get("aid")
    cid = payload.get("cid")
    email = (payload.get("email") or "").lower()
    sid = payload.get("sid")
    if kind not in ARTEFACT_KINDS or not aid or not cid or not email:
        raise HTTPException(status_code=400, detail="Invalid share link.")

    # Pull the full artefact (we only return public-safe fields below).
    coll = db.decks if kind == "deck" else db.briefings
    artefact = await coll.find_one({"id": aid, "context_id": cid}, {"_id": 0})
    if not artefact:
        raise HTTPException(status_code=404, detail="This document is no longer available.")

    # Record the view (idempotent per day per synthetic account).
    today = _utc_today()
    account_id = _external_account_id(email)
    await db.studio_views.find_one_and_update(
        {"artefact_kind": kind, "artefact_id": aid,
         "context_id": cid, "account_id": account_id, "day_utc": today},
        {"$inc": {"view_count": 1},
         "$setOnInsert": {
             "id": str(uuid.uuid4()),
             "first_viewed_at": iso(now()),
             "is_owner": False,
             "is_external": True,
             "external_email": email,
         },
         "$set": {"last_viewed_at": iso(now())}},
        upsert=True,
    )

    # Mark the share record as opened.
    if sid:
        await db.studio_shares.update_one(
            {"id": sid, "first_opened_at": {"$exists": False}},
            {"$set": {"first_opened_at": iso(now())}},
        )
        await db.studio_shares.update_one(
            {"id": sid},
            {"$set": {"last_opened_at": iso(now())},
             "$inc": {"open_count": 1}},
        )

    # Resolve sharer + context display fields.
    share_rec = await db.studio_shares.find_one({"id": sid}, {"_id": 0}) if sid else None
    sharer_name = None
    if share_rec:
        sharer = await db.accounts.find_one(
            {"id": share_rec.get("shared_by")}, {"_id": 0, "name": 1, "email": 1}
        ) or {}
        sharer_name = sharer.get("name") or sharer.get("email")
    ctx_doc = await db.contexts.find_one({"id": cid}, {"_id": 0, "name": 1}) or {}
    context_name = ctx_doc.get("name") or "AKKI"

    # ── Phase 12.2 ITEM E — assert the artefact has been Synisense-screened
    # BEFORE we project content. A snapshot without `synisense_version` predates
    # Phase 12 and was never run through the in-house de-id pipeline — refuse
    # to serve it externally. The author must re-save in Studio (which now runs
    # the pipeline silently post-first-accept) before the share works. 410
    # (Gone) rather than 404 because the link IS valid; the snapshot is not
    # yet ready. This check sits BEFORE projection so we never even build a
    # response that could leak the original body.
    if not (artefact.get("synisense_version") or 0) >= 1:
        raise HTTPException(
            status_code=410,
            detail="Pending review — the author has not yet completed security screening for this share.",
        )

    # Phase 12.2 closeout BUG 2 — public-read MUST project from the redacted
    # projection (`body_redacted`), never from the original `opening_paragraph`
    # / `items[].body` / `slides[].body_md` fields. Those carry the editable
    # original; the redacted version is the authoritative external surface.
    # If `body_redacted` is somehow missing despite `synisense_version >= 1`,
    # we refuse rather than fall back to the original. Belt-and-braces.
    redacted_body = (artefact.get("body_redacted") or "").strip()
    if not redacted_body:
        raise HTTPException(
            status_code=410,
            detail="Pending review — redacted projection missing for this snapshot.",
        )

    # Public-safe content projection. We deliberately do NOT leak
    # audience, missing_context, or other internal production metadata,
    # AND we never serve the original (un-redacted) body fields.
    if kind == "deck":
        content = {
            "title": artefact.get("title") or "Shared deck",
            "subtitle": artefact.get("subtitle"),
            "research_question": artefact.get("research_question"),
            # Phase 12.2 closeout BUG 2 — slides body_md projected from the
            # flat redacted concatenation. Per-slide redaction is not persisted
            # today; serving the flat redacted body in a single slide preserves
            # the public reader's render shape without leaking originals.
            "slides": [
                {"n": 1,
                 "title": artefact.get("title") or "Shared deck",
                 "body_md": redacted_body},
            ],
        }
    else:
        content = {
            "title": artefact.get("title") or "Shared briefing",
            # Phase 12.2 closeout BUG 2 — opening_paragraph is now the redacted
            # flat projection. items[] is intentionally empty in the public
            # surface because per-item redaction is not persisted; the redacted
            # concatenation already covers the same ground in the same order.
            "opening_paragraph": redacted_body,
            "items": [],
        }

    payload_jwt_exp = payload.get("exp")
    expires_at_iso = (
        datetime.fromtimestamp(int(payload_jwt_exp), tz=timezone.utc).isoformat()
        if payload_jwt_exp else None
    )

    response_payload = {
        "kind": kind,
        "artefact_id": aid,
        "context_id": cid,
        "context_name": context_name,
        "shared_with_email": email,
        "shared_by_name": sharer_name,
        "share_message": (share_rec or {}).get("message"),
        "created_at": artefact.get("created_at"),
        "sensitivity": artefact.get("sensitivity"),
        "content": content,
        "watermark": {
            "label": "AKKI share · read-only",
            "recipient": email,
            "expires_at": expires_at_iso,
        },
    }

    # ── Phase 11 ITEM A — hard assertion that the response never leaks
    # un-redacted internal production metadata. This fires as a 500 (not
    # a 4xx) because leaking un-redacted content past this boundary is a
    # server-side contract violation, not a client mistake. Denylist is
    # exhaustive against the fields we know carry internal context
    # (audience, speaker notes, model telemetry, account ids, review
    # chains, validator payloads, quota state, etc.). If we ever add a
    # new internal field, this assertion must be updated in tandem.
    _assert_public_safe(response_payload)

    return response_payload


# Keys that must NEVER appear (at any depth) in a public read response.
# Centralised here so the set is auditable. Keep alphabetised.
_PUBLIC_READ_DENYLIST = frozenset({
    "account_id",
    "audience",
    "audience_assumed",
    "chain",
    # Phase 12.2 ITEM E — shield-map cryptographic envelope keys. These
    # MUST never appear in any public response, at any depth, regardless
    # of how the artefact got into the snapshot. Each key alone is
    # enough to compromise the de-id contract.
    "dek_nonce",
    "dek_wrapped",
    "encrypted_original",
    "events",
    "envelope",
    "inbound_token",
    "missing_context",
    "model",
    "model_id",
    "original_payload",
    "outline_id",
    "password_hash",
    "quality_check",
    "quota",
    "shield_map",
    "speaker_notes",
    "synisense_key",
    "tier",
    "user_feedback",
    "validation",
    "validator_model",
    "validator_provider",
})


def _assert_public_safe(obj: Any, *, path: str = "$") -> None:
    """Walk the response object and raise 500 if any key at any depth
    matches the denylist. This is a hard boundary check — we do not want
    a silent leak of internal production metadata through the public
    Chair view. The fast-path is a single recursive walk; the cost is
    negligible compared to the DB reads upstream."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in _PUBLIC_READ_DENYLIST:
                logger.error(
                    "public read would leak denylisted key %s at %s — refusing",
                    k, path,
                )
                raise HTTPException(
                    status_code=500,
                    detail="Shared view redaction contract violated. Refusing to leak internal metadata.",
                )
            _assert_public_safe(v, path=f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _assert_public_safe(v, path=f"{path}[{i}]")
