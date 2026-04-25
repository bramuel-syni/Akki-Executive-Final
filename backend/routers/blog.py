"""Exco360 — AKKI's perspective on AI's role in modern executive success.

Editorial blog series. AKKI composes weekly research-driven posts. Public
read endpoints are open; compose/publish are admin-only. Article shape:
slug, title, dek (sub-headline), kicker (e.g. 'Vol 1 · Issue 4'), body
(markdown), tags, hero_quote, sources[], read_minutes, status, published_at.

Phase-2 endpoints in this module:
  - GET  /api/blog/posts                     — public, lists published posts
  - GET  /api/blog/posts/{slug}              — public read
  - POST /api/blog/compose                   — admin/superadmin, generates a
                                               new draft using the LLM with a
                                               curated brief. Returns the draft.
  - POST /api/blog/posts/{slug}/publish      — admin, flips draft → published
                                               and fans the email_intro out
                                               to every active subscriber via
                                               Resend.
  - POST /api/blog/subscribe                 — public, captures email
  - GET  /api/blog/subscribers               — admin
  - POST /api/blog/cron/weekly               — internal cron endpoint, gated
                                               by `X-Cron-Secret`, composes
                                               the next issue as a DRAFT (admin
                                               must publish — keeps a human
                                               in the loop on what the world
                                               sees in AKKI's voice).
"""
from __future__ import annotations

import logging
import os
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, EmailStr, Field

from core import db, get_current_account, now as _now, iso as _iso, write_audit
from email_service import (
    configured as resend_configured,
    send_email,
)
from llm_service import call_llm as llm_call_llm, parse_json_response

logger = logging.getLogger("akki.blog")

router = APIRouter(prefix="/api/blog")


SERIES_NAME = "Exco360"
SERIES_TAGLINE = "AKKI's perspective on AI's role in modern executive success."


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class ComposeIn(BaseModel):
    topic: str = Field(min_length=8, max_length=280,
                       description="What this week's article should cover")
    audience_hint: Optional[str] = Field(default="NEDs and operating executives", max_length=120)


class SubscribeIn(BaseModel):
    email: EmailStr
    name: Optional[str] = Field(default=None, max_length=120)
    role: Optional[str] = Field(default=None, max_length=80,
                                description="self-declared, e.g. NED / CFO / CEO")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slugify(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9\s-]", "", s).strip().lower()
    s = re.sub(r"\s+", "-", s)
    return s[:80] or f"exco360-{uuid.uuid4().hex[:6]}"


async def _next_volume_issue() -> Dict[str, int]:
    """Compute the next Vol/Issue from existing published posts. Issue resets
    on the first post of each calendar year (volume increment)."""
    last = await db.blog_posts.find_one(
        {"status": "published"}, {"_id": 0, "volume": 1, "issue": 1, "published_at": 1},
        sort=[("published_at", -1)],
    )
    year = _now().year
    base_year = 2026  # Vol 1 = 2026
    target_volume = max(1, year - base_year + 1)
    if not last:
        return {"volume": target_volume, "issue": 1}
    if last.get("volume", 1) < target_volume:
        return {"volume": target_volume, "issue": 1}
    return {"volume": last.get("volume", 1), "issue": (last.get("issue") or 0) + 1}


# ---------------------------------------------------------------------------
# Public endpoints
# ---------------------------------------------------------------------------

@router.get("/posts")
async def list_posts(limit: int = 20, include_drafts: bool = False):
    q: Dict[str, Any] = {} if include_drafts else {"status": "published"}
    cursor = db.blog_posts.find(
        q,
        {"_id": 0, "body": 0},  # exclude long body in listing
    ).sort("published_at", -1).limit(min(max(limit, 1), 50))
    return {"posts": await cursor.to_list(length=50), "series": SERIES_NAME, "tagline": SERIES_TAGLINE}


@router.get("/posts/{slug}")
async def get_post(slug: str):
    p = await db.blog_posts.find_one({"slug": slug}, {"_id": 0})
    if not p or p.get("status") != "published":
        raise HTTPException(status_code=404, detail="Post not found.")
    # Bump read counter, fire-and-forget
    await db.blog_posts.update_one({"slug": slug}, {"$inc": {"reads": 1}})
    return p


@router.post("/subscribe")
async def subscribe(body: SubscribeIn):
    """Capture an email subscription for the Exco360 list. Idempotent — same
    email re-subscribes silently (no duplicate, no error)."""
    email = body.email.lower().strip()
    existing = await db.blog_subscribers.find_one({"email": email}, {"_id": 0, "id": 1})
    if existing:
        return {"ok": True, "already_subscribed": True}
    rec = {
        "id": str(uuid.uuid4()),
        "email": email,
        "name": (body.name or "").strip() or None,
        "role": (body.role or "").strip() or None,
        "subscribed_at": _iso(_now()),
        "status": "active",
        "source": "blog_subscribe_form",
    }
    await db.blog_subscribers.insert_one(rec.copy())
    return {"ok": True, "already_subscribed": False}


# ---------------------------------------------------------------------------
# Admin endpoints — compose + publish + cross-post copy generators
# ---------------------------------------------------------------------------

async def _require_admin(current: Dict[str, Any] = Depends(get_current_account)) -> Dict[str, Any]:
    if not current.get("is_superadmin"):
        raise HTTPException(status_code=403, detail="Superadmin only.")
    return current


@router.post("/compose")
async def compose(
    body: ComposeIn,
    current: Dict[str, Any] = Depends(_require_admin),
):
    """LLM-driven composition for the next Exco360 article. Persists as a
    draft. Returns the full draft for review."""
    vi = await _next_volume_issue()
    prompt = (
        f"You are writing the next instalment of '{SERIES_NAME} — {SERIES_TAGLINE}'. "
        f"This is Volume {vi['volume']}, Issue {vi['issue']}.\n\n"
        f"Topic for this issue:\n    « {body.topic} »\n\n"
        f"Audience: {body.audience_hint or 'NEDs and operating executives'}.\n\n"
        f"Write 700-1,100 words. Voice: AKKI — a sharp, sober colleague with governance experience. "
        f"Specific. Numerate where useful. Cite real authorities (NACD, IoD, NIST, EU AI Act, FCA, CBK, "
        f"ISO 42001, Stanford HAI, MIT). No hype. No tool-marketing. Land at least one practical "
        f"'questions to take to the room' bullet list.\n\n"
        f"Return JSON:\n{{\n"
        f'  "title": "<= 90 chars, declarative, surprising",\n'
        f'  "dek": "1-sentence sub-headline, <= 180 chars",\n'
        f'  "hero_quote": "1-sentence pull-quote that distills the piece",\n'
        f'  "tags": ["3-5 short slugs"],\n'
        f'  "body": "Markdown. 4-7 sections with ## headings. Include a 3-bullet \'Questions for the boardroom\' near the end.",\n'
        f'  "sources": ["3-5 plausible primary-source URLs"],\n'
        f'  "linkedin_post": "180-280 word LinkedIn post that previews the article in AKKI voice and links to it. Include 2-3 hashtags.",\n'
        f'  "twitter_post": "<= 270 chars, sharp, no thread",\n'
        f'  "email_intro": "120-200 word intro for the weekly Exco360 newsletter that frames why this issue matters."\n'
        f"}}\n"
    )
    llm_out = await llm_call_llm(
        module="blog-compose",
        user_query=prompt,
        context_object=None,
        session_context={"session_id": f"blog-{current['id']}"},
        data_trust={"overall": "trusted"},
        response_format="json",
    )
    parsed = parse_json_response(llm_out.get("response", ""))
    if not isinstance(parsed, dict) or not parsed.get("body"):
        logger.warning("Blog compose parse failed. mode=%s response_head=%s",
                       llm_out.get("mode"), (llm_out.get("response") or "")[:600])
        raise HTTPException(status_code=502, detail=f"LLM did not produce an article. Mode={llm_out.get('mode')}.")

    title = (parsed.get("title") or body.topic)[:120]
    slug = _slugify(f"vol{vi['volume']}-iss{vi['issue']}-{title}")
    rec = {
        "id": str(uuid.uuid4()),
        "slug": slug,
        "series": SERIES_NAME,
        "volume": vi["volume"],
        "issue": vi["issue"],
        "kicker": f"{SERIES_NAME} · Vol {vi['volume']} · Issue {vi['issue']}",
        "title": title,
        "dek": (parsed.get("dek") or "")[:300],
        "hero_quote": (parsed.get("hero_quote") or "")[:300],
        "tags": (parsed.get("tags") or [])[:8],
        "body": (parsed.get("body") or "")[:18000],
        "sources": (parsed.get("sources") or [])[:8],
        "linkedin_post": (parsed.get("linkedin_post") or "")[:1800],
        "twitter_post": (parsed.get("twitter_post") or "")[:300],
        "email_intro": (parsed.get("email_intro") or "")[:1500],
        "read_minutes": max(2, len((parsed.get("body") or "").split()) // 220),
        "status": "draft",
        "reads": 0,
        "created_at": _iso(_now()),
        "created_by": current["id"],
        "published_at": None,
    }
    await db.blog_posts.insert_one(rec.copy())
    await write_audit(None, current["id"], "blog.composed", "blog_post", rec["id"],
                      {"title": title, "slug": slug, "vol": vi["volume"], "issue": vi["issue"]})
    return {k: v for k, v in rec.items() if k != "_id"}


def _frontend_origin() -> str:
    return (os.environ.get("FRONTEND_URL") or "https://akki.ai").rstrip("/")


def _newsletter_html(*, post: Dict[str, Any], post_url: str) -> str:
    """Render the newsletter body sent to Exco360 subscribers when an issue
    is published. Editorial cream/oxblood/Georgia inline-CSS layout — same
    voice as the on-AKKI reader."""
    intro = post.get("email_intro") or post.get("dek") or ""
    return f"""
<!doctype html><html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#F7F3EA;font-family:-apple-system,Helvetica,Arial,sans-serif;color:#2A2622;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#F7F3EA;padding:36px 18px;">
    <tr><td align="center">
      <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;background:#fff;border:1px solid #E8E0D0;">
        <tr><td style="padding:30px 36px 18px 36px;border-bottom:3px solid #8B2E2B;">
          <p style="margin:0;font-size:11px;text-transform:uppercase;letter-spacing:0.18em;color:#8B2E2B;font-weight:600;">{post.get('kicker', 'Exco360')}</p>
          <h1 style="margin:8px 0 0 0;font-family:Georgia,serif;font-size:26px;line-height:1.2;color:#1a1a1a;font-weight:normal;">{post.get('title', 'New issue')}</h1>
          {f'<p style="margin:10px 0 0 0;font-family:Georgia,serif;font-size:15px;line-height:1.55;color:#2A2622;font-style:italic;">{post.get("dek", "")}</p>' if post.get("dek") else ''}
        </td></tr>
        <tr><td style="padding:24px 36px;font-family:Georgia,serif;font-size:15.5px;line-height:1.7;color:#2A2622;">
          {''.join(f'<p style="margin:0 0 14px 0;">{p.strip()}</p>' for p in (intro or '').split(chr(10)) if p.strip())}
        </td></tr>
        <tr><td style="padding:8px 36px 28px 36px;">
          <a href="{post_url}" style="display:inline-block;padding:11px 22px;background:#1A2B4C;color:#fff;text-decoration:none;font-family:-apple-system,sans-serif;font-size:14px;font-weight:500;border-radius:4px;">Read the issue →</a>
          <p style="margin:14px 0 0 0;font-family:-apple-system,sans-serif;font-size:12px;color:#8b6f47;">{post.get('read_minutes', 6)} min read</p>
        </td></tr>
        <tr><td style="padding:18px 36px;border-top:1px solid #E8E0D0;background:#F9F6EE;">
          <p style="margin:0;font-family:-apple-system,sans-serif;font-size:11px;color:#8b6f47;line-height:1.55;">
            You're getting this because you subscribed to Exco360 — AKKI's perspective on AI's role in modern executive success. One short editorial in your inbox each week.
            <br><br>If this isn't useful, just reply with "unsubscribe" and we'll remove you the same day.
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>
"""


async def _fan_out_to_subscribers(post: Dict[str, Any]) -> Dict[str, Any]:
    """Send the published issue to every active subscriber. Best-effort —
    failures are tracked per recipient and returned but don't block publish."""
    if not resend_configured():
        return {"ok": False, "skipped": "Resend not configured", "sent": 0, "failed": 0}
    subs = await db.blog_subscribers.find(
        {"status": "active"}, {"_id": 0, "email": 1, "name": 1},
    ).to_list(length=10000)
    if not subs:
        return {"ok": True, "sent": 0, "failed": 0, "note": "no active subscribers"}

    post_url = f"{_frontend_origin()}/blog/{post['slug']}"
    subject = f"{post.get('kicker', 'Exco360')} — {post.get('title', '')}"
    html = _newsletter_html(post=post, post_url=post_url)

    sent = 0
    failed = 0
    failed_emails: List[str] = []
    # Resend's sandbox blocks non-verified domains; we use BCC-style 1:1
    # sends to keep delivery clean and per-recipient personalised. For 100s
    # of subscribers Resend handles the throughput fine; for 1000s we'd batch.
    for s in subs:
        res = await send_email(
            to=[s["email"]],
            subject=subject,
            html=html,
            from_executive_name=None,  # send as plain "AKKI" for newsletters
            tags=[{"name": "kind", "value": "exco360"},
                  {"name": "slug", "value": post["slug"][:24]}],
        )
        if res.get("ok"):
            sent += 1
        else:
            failed += 1
            failed_emails.append(s["email"])
    return {"ok": failed == 0, "sent": sent, "failed": failed,
            "failed_emails": failed_emails[:20]}


@router.post("/posts/{slug}/publish")
async def publish_post(
    slug: str,
    current: Dict[str, Any] = Depends(_require_admin),
):
    """Publish + fan-out to subscribers. Returns the post enriched with a
    `newsletter` summary so the admin sees how many were notified."""
    res = await db.blog_posts.update_one(
        {"slug": slug, "status": "draft"},
        {"$set": {"status": "published", "published_at": _iso(_now())}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Draft not found.")
    rec = await db.blog_posts.find_one({"slug": slug}, {"_id": 0})
    fanout = await _fan_out_to_subscribers(rec)
    await db.blog_posts.update_one({"slug": slug}, {"$set": {"newsletter": fanout}})
    rec["newsletter"] = fanout
    await write_audit(None, current["id"], "blog.published", "blog_post", rec["id"],
                      {"slug": slug, "subscribers_sent": fanout.get("sent", 0)})
    return rec


# ---------------------------------------------------------------------------
# Weekly cron — composes the next Exco360 issue as a DRAFT (admin must
# publish manually so a human stays in the loop on what AKKI says publicly).
# ---------------------------------------------------------------------------

# Default rotating topic seeds — picked deterministically by ISO week so a
# weekly trigger never hits the same topic twice in a 12-week window.
_TOPIC_SEEDS = [
    "Why audit committees should ask about model drift this quarter",
    "What 'human in the loop' actually looks like in practice — three patterns NEDs should learn to distinguish",
    "The AI vendor due-diligence questions that separate boards who'll regret their procurement from those who won't",
    "Capital allocation in the age of AI: what's a one-year payback now, and what isn't",
    "Why every risk register should now have a model-risk section — and what belongs in it",
    "ESG meets AI: the disclosure questions regulators are signalling",
    "Reporting cycles in the age of agentic AI — what board secretaries should be tracking",
    "Why most AI governance frameworks are written for engineers, not directors",
    "The 'red team' question every board should put to management this year",
    "AI in customer-facing workflows: what's the directors' duty when the model lies?",
    "Vendor lock-in and AI: how to negotiate exit rights into your model contracts",
    "AI's quiet effect on M&A: due diligence has changed in ways most boards haven't noticed",
]


def _topic_for_this_week() -> str:
    iso_week = _now().isocalendar()[1]
    return _TOPIC_SEEDS[iso_week % len(_TOPIC_SEEDS)]


@router.post("/cron/weekly")
async def cron_weekly(
    x_cron_secret: Optional[str] = Header(default=None, alias="X-Cron-Secret"),
):
    """Compose the next Exco360 issue as a DRAFT. Idempotent within a single
    ISO week — if a draft already exists for this week's topic, returns it
    instead of re-composing. Gated by AKKI_CRON_SECRET env var so only the
    scheduled-job runner can hit it."""
    expected = os.environ.get("AKKI_CRON_SECRET")
    if not expected:
        raise HTTPException(status_code=503, detail="Cron disabled — AKKI_CRON_SECRET not configured.")
    if not x_cron_secret or x_cron_secret != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Cron-Secret header.")

    topic = _topic_for_this_week()
    # Idempotency: if a draft already exists for this exact topic this ISO
    # week, return it instead of LLM-composing a duplicate.
    iso_week = _now().isocalendar()[1]
    existing = await db.blog_posts.find_one(
        {"status": "draft", "topic_seed": topic, "iso_week": iso_week},
        {"_id": 0},
    )
    if existing:
        return {"ok": True, "already_drafted_for_week": True, "post": existing}

    vi = await _next_volume_issue()
    prompt = (
        f"You are writing the next instalment of '{SERIES_NAME} — {SERIES_TAGLINE}'. "
        f"This is Volume {vi['volume']}, Issue {vi['issue']}.\n\n"
        f"Topic for this issue:\n    « {topic} »\n\n"
        f"Audience: NEDs and operating executives.\n\n"
        f"Write 700-1,100 words. Voice: AKKI — a sharp, sober colleague with governance experience. "
        f"Specific. Numerate where useful. Cite real authorities (NACD, IoD, NIST, EU AI Act, FCA, CBK, "
        f"ISO 42001, Stanford HAI, MIT). No hype. No tool-marketing.\n\n"
        f"Return JSON:\n{{\n"
        f'  "title": "<= 90 chars",\n'
        f'  "dek": "1-sentence sub-headline",\n'
        f'  "hero_quote": "1-sentence pull-quote",\n'
        f'  "tags": ["3-5 short slugs"],\n'
        f'  "body": "Markdown. 4-7 sections. Include a 3-bullet \'Questions for the boardroom\' near the end.",\n'
        f'  "sources": ["3-5 plausible primary-source URLs"],\n'
        f'  "linkedin_post": "180-280 word LinkedIn post",\n'
        f'  "twitter_post": "<= 270 chars",\n'
        f'  "email_intro": "120-200 word newsletter intro"\n'
        f"}}\n"
    )
    llm_out = await llm_call_llm(
        module="blog-cron",
        user_query=prompt,
        context_object=None,
        session_context={"session_id": f"blog-cron-w{iso_week}"},
        data_trust={"overall": "trusted"},
        response_format="json",
    )
    parsed = parse_json_response(llm_out.get("response", ""))
    if not isinstance(parsed, dict) or not parsed.get("body"):
        logger.warning("Cron compose parse failed; mode=%s head=%s",
                       llm_out.get("mode"), (llm_out.get("response") or "")[:600])
        raise HTTPException(status_code=502, detail=f"LLM did not produce an article. Mode={llm_out.get('mode')}.")

    title = (parsed.get("title") or topic)[:120]
    slug = _slugify(f"vol{vi['volume']}-iss{vi['issue']}-{title}")
    rec = {
        "id": str(uuid.uuid4()),
        "slug": slug,
        "series": SERIES_NAME,
        "volume": vi["volume"],
        "issue": vi["issue"],
        "kicker": f"{SERIES_NAME} · Vol {vi['volume']} · Issue {vi['issue']}",
        "title": title,
        "dek": (parsed.get("dek") or "")[:300],
        "hero_quote": (parsed.get("hero_quote") or "")[:300],
        "tags": (parsed.get("tags") or [])[:8],
        "body": (parsed.get("body") or "")[:18000],
        "sources": (parsed.get("sources") or [])[:8],
        "linkedin_post": (parsed.get("linkedin_post") or "")[:1800],
        "twitter_post": (parsed.get("twitter_post") or "")[:300],
        "email_intro": (parsed.get("email_intro") or "")[:1500],
        "read_minutes": max(2, len((parsed.get("body") or "").split()) // 220),
        "status": "draft",
        "reads": 0,
        "topic_seed": topic,
        "iso_week": iso_week,
        "created_at": _iso(_now()),
        "created_by": None,
        "created_via": "cron",
        "published_at": None,
    }
    await db.blog_posts.insert_one(rec.copy())
    return {"ok": True, "post": rec}


@router.delete("/posts/{slug}")
async def delete_post(
    slug: str,
    current: Dict[str, Any] = Depends(_require_admin),
):
    res = await db.blog_posts.delete_one({"slug": slug})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Post not found.")
    return {"ok": True}


@router.get("/admin/posts/{slug}")
async def get_post_admin(
    slug: str,
    current: Dict[str, Any] = Depends(_require_admin),
):
    """Full post fetch for the admin surface — returns drafts + published alike,
    body included. Used by the BlogAdmin 'Copy for Medium' action."""
    p = await db.blog_posts.find_one({"slug": slug}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Post not found.")
    return p


@router.get("/subscribers")
async def list_subscribers(
    current: Dict[str, Any] = Depends(_require_admin),
):
    cursor = db.blog_subscribers.find(
        {"status": "active"}, {"_id": 0},
    ).sort("subscribed_at", -1).limit(2000)
    return {"subscribers": await cursor.to_list(length=2000)}
