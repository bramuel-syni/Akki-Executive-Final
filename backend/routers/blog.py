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
from fastapi.responses import Response
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

# ---------------------------------------------------------------------------
# Persona prompt — applied to every weekly auto-generation. Distilled from
# the user-supplied Medium ghostwriter brief. The cron runs the four phases
# (intake → structure → draft → self-critique) inside one call and saves the
# revised draft so a human can publish it after review.
# ---------------------------------------------------------------------------
PERSONA_PROMPT = """You are a Medium ghostwriter for an African-market operator who thinks
in systems, challenges convention, and is allergic to imported templates.
Your finished article must have a realistic shot at a 50%+ read ratio.

AUTHOR PERSONA
- Thinks structurally and integrative — connects B2C, B2B, internal teams,
  infrastructure into one thesis. Never lists features.
- Commercially serious. Demands post-grant viability and unit economics.
  Stress-tests whether a thesis survives without subsidy.
- Impatient with corporate softeners, hedging, polish. Wants specifics,
  declarative claims, peers not students.
- POV: African operator building institution-grade products, betting that
  local nuance with global rigour is the moat.

PHASE 1 — INTAKE (do internally before writing)
Pick a non-obvious angle. If your first instinct is generic ("AI is the
future", "consistency matters"), STOP and find something contrarian but
truthful. Define a specific target reader (e.g. "CFOs of mid-cap African
financial services" not "executives interested in AI"). Identify the
"lessons that stick" — what should the reader walk away believing?

PHASE 2 — STRUCTURE
Choose ONE title that creates a curiosity gap (no "How I…" or "X lessons
from Y" formulas unless the specifics are unusually strong). 4-6 H2
section headers. A specific opening hook (number/scene/claim, never a
definition). A concrete payoff the reader leaves with.

PHASE 3 — DRAFT (the article body)
VOICE: First-person, conversational not casual. No throat-clearing intros.
No "it's important to note", "at the end of the day", "in today's
fast-paced world". Cut every sentence that adds no meaning.

STRUCTURE: Open with a specific scene/number/claim. H2 every 200-400 words.
Short paragraphs (1-4 sentences). A bolded line or pulled quote every
400-600 words for scan-ability. Close with a specific takeaway, never
"what do you think? comment below".

CONTENT RULES: Every claim needs a concrete anchor — a number, name,
date, or example. If you can't anchor it, cut it. No invented statistics.
No "studies show" without a specific study. Replace adjectives with
specifics ("went from 12% to 41%" not "huge improvement"). If you find
yourself writing a list of generic tips, stop — write an argument.

WHAT TO AVOID: em-dash overuse, "It's not X, it's Y", "—and that's the
point" tics (these read as AI now). Header questions like "Why Does This
Matter?". Conclusions that summarise what you just said. Sentences that
could appear in any article on this topic.

PHASE 4 — SELF-CRITIQUE
Before returning, audit: which sentence has the highest bounce risk? Are
there 3 sentences that could appear in any article on this topic — rewrite
or cut them. Count concrete details (numbers, names, scenes); if under 5
in the whole piece, rewrite. Flag any AI-tells. Then deliver the revised
version.
"""


_TOPIC_SEEDS = [
    "Opportunity: the AI-procurement asymmetry African boards keep losing — and the three contract clauses that close it",
    "Risk: model-risk registers your audit committee should refuse to sign without",
    "Compliance: what the EU AI Act actually means for a Nairobi or Lagos board (and what it doesn't)",
    "Adoption management: the leadership move that separates AI rollouts that compound from those that stall",
    "Growth as an executive: why pattern-matchers plateau and systems-thinkers compound",
    "Opportunity: the strategic-finance lever AI unlocks that most CFOs aren't pulling",
    "Risk: the vendor lock-in trap hiding in your AI procurement, and the exit clause to demand",
    "Compliance: the disclosure obligations that turn an AI deployment into a board-level matter",
    "Adoption management: the three friction points that kill AI rollouts in mid-cap African corporates",
    "Growth as an executive: how to develop conviction in a market with poor benchmarks",
    "Opportunity: the data-asset most boards are still treating as a cost",
    "Risk: why agentic AI changes your cybersecurity posture, and what to brief the chair",
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
        f"{PERSONA_PROMPT}\n\n"
        f"This is Volume {vi['volume']}, Issue {vi['issue']} of '{SERIES_NAME} — "
        f"{SERIES_TAGLINE}'.\n\n"
        f"Topic to write on: « {topic} »\n\n"
        f"Audience: NEDs and operating executives in African mid-cap and "
        f"large-cap businesses. Length: 1,200-1,800 words.\n\n"
        f"Return STRICT JSON ONLY:\n{{\n"
        f'  "title": "<= 90 chars; specific curiosity gap; no \\"How I…\\" formulas",\n'
        f'  "dek": "1-sentence sub-headline, <= 180 chars",\n'
        f'  "hero_quote": "1-sentence pull-quote that distills the piece",\n'
        f'  "tags": ["3-5 short slugs"],\n'
        f'  "body": "Markdown. Open with a specific scene/number/claim. 4-6 ## H2 sections. Short paragraphs (1-4 sentences). A **bolded sentence** every 400-600 words. Close with a specific takeaway, no comment-bait CTA.",\n'
        f'  "sources": ["3-5 real primary-source URLs (NACD, IoD, NIST, FCA, CBK, EU AI Act, ISO 42001, Stanford HAI, MIT, etc.)"],\n'
        f'  "linkedin_post": "180-280 word LinkedIn preview in author voice; 2-3 hashtags",\n'
        f'  "twitter_post": "<= 270 chars, sharp, no thread",\n'
        f'  "email_intro": "120-200 word newsletter intro framing why this issue matters now"\n'
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

    # Notify admins so they can review + one-click publish.
    try:
        admins = await db.accounts.find(
            {"is_superadmin": True}, {"_id": 0, "email": 1, "name": 1},
        ).to_list(20)
        review_url = f"{_frontend_origin()}/blog/admin?slug={slug}"
        for a in admins:
            await send_email(
                to=a["email"],
                subject=f"AKKI: weekly draft ready — {title}",
                html=(
                    f"<div style=\"font-family:Georgia,serif;max-width:560px;margin:0 auto;padding:32px 24px;"
                    f"background:#f5efe6;color:#1a1f2e;\">"
                    f"<p style=\"font-size:11px;letter-spacing:0.2em;text-transform:uppercase;color:#7a6a52;"
                    f"margin:0 0 16px 0;\">Exco360 · Weekly draft</p>"
                    f"<h1 style=\"font-size:24px;line-height:1.25;margin:0 0 12px 0;font-weight:normal;\">"
                    f"{title}</h1>"
                    f"<p style=\"font-size:14px;color:#4a4a4a;margin:0 0 24px 0;font-style:italic;\">"
                    f"{(parsed.get('dek') or '').strip()[:200]}</p>"
                    f"<p style=\"font-size:13px;line-height:1.7;color:#3a3a3a;margin:0 0 24px 0;\">"
                    f"AKKI auto-drafted this article using the Medium ghostwriter persona. "
                    f"Read the draft, edit if you need to, and publish when you're ready. "
                    f"Subscribers will receive it on publish.</p>"
                    f"<a href=\"{review_url}\" style=\"display:inline-block;background:#722f37;color:#fff;"
                    f"padding:12px 24px;text-decoration:none;font-size:13px;letter-spacing:0.05em;\">"
                    f"Review and publish &rarr;</a>"
                    f"<p style=\"font-size:11px;color:#7a6a52;margin:32px 0 0 0;\">"
                    f"Draft created automatically. No subscribers were emailed yet.</p>"
                    f"</div>"
                ),
                text=f"AKKI weekly draft ready: {title}\n\nReview at: {review_url}",
            )
    except Exception as e:  # noqa: BLE001 — best-effort notification
        logger.warning("Cron admin notification failed: %s", e)

    return {"ok": True, "post": rec, "admins_notified": True}


@router.post("/seed/launch-10")
async def seed_launch_articles(
    current: Dict[str, Any] = Depends(_require_admin),
):
    """One-shot seed: composes 10 launch articles across opportunity, risk,
    compliance, adoption-management, and growth-as-an-executive (2 each)
    using the persona prompt. Returns immediately with how many were
    queued; the LLM calls run sequentially and persist as drafts.

    Idempotent: skips topics that already have a draft on this server."""
    SEED_TOPICS = [
        ("opportunity", "The AI procurement asymmetry African boards keep losing — and the three contract clauses that close it"),
        ("opportunity", "The data asset most boards still treat as a cost — and the three reframings that change it"),
        ("risk", "Model-risk registers your audit committee should refuse to sign without"),
        ("risk", "Why agentic AI changes your cybersecurity posture, and what to brief the chair this quarter"),
        ("compliance", "What the EU AI Act actually means for a Nairobi or Lagos board (and what it doesn't)"),
        ("compliance", "The disclosure obligations that turn an AI deployment into a board-level matter"),
        ("adoption", "The leadership move that separates AI rollouts that compound from those that stall"),
        ("adoption", "The three friction points that kill AI rollouts in mid-cap African corporates"),
        ("growth", "Why pattern-matchers plateau and systems-thinkers compound — what executives can change about how they think"),
        ("growth", "How to develop conviction in a market with poor benchmarks"),
    ]

    composed: List[Dict[str, Any]] = []
    skipped: List[str] = []

    for category, topic in SEED_TOPICS:
        # Idempotency: if a draft or published post with the same topic
        # already exists, skip.
        existing = await db.blog_posts.find_one(
            {"topic_seed": topic}, {"_id": 0, "slug": 1, "title": 1},
        )
        if existing:
            skipped.append(topic)
            continue

        vi = await _next_volume_issue()
        prompt = (
            f"{PERSONA_PROMPT}\n\n"
            f"This is Volume {vi['volume']}, Issue {vi['issue']} of "
            f"'{SERIES_NAME} — {SERIES_TAGLINE}'.\n\n"
            f"Category: {category}\n"
            f"Topic to write on: « {topic} »\n\n"
            f"Audience: NEDs and operating executives in African mid-cap "
            f"and large-cap businesses. Length: 1,200-1,800 words.\n\n"
            f"Return STRICT JSON ONLY:\n{{\n"
            f'  "title": "<= 90 chars",\n'
            f'  "dek": "1-sentence sub-headline",\n'
            f'  "hero_quote": "1-sentence pull-quote",\n'
            f'  "tags": ["3-5 short slugs"],\n'
            f'  "body": "Markdown. Open with a specific scene/number/claim. 4-6 ## H2 sections. Short paragraphs.",\n'
            f'  "sources": ["3-5 real primary-source URLs"],\n'
            f'  "linkedin_post": "180-280 words",\n'
            f'  "twitter_post": "<= 270 chars",\n'
            f'  "email_intro": "120-200 words"\n'
            f"}}\n"
        )
        try:
            llm_out = await llm_call_llm(
                module="blog-seed",
                user_query=prompt,
                context_object=None,
                session_context={"session_id": f"blog-seed-{category}"},
                data_trust={"overall": "trusted"},
                response_format="json",
            )
            parsed = parse_json_response(llm_out.get("response", ""))
            if not isinstance(parsed, dict) or not parsed.get("body"):
                logger.warning("Seed compose failed for %s", topic)
                continue
        except Exception as e:  # noqa: BLE001
            logger.warning("Seed compose threw for %s: %s", topic, e)
            continue

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
            "category": category,
            "status": "draft",
            "reads": 0,
            "topic_seed": topic,
            "created_at": _iso(_now()),
            "created_by": current["id"],
            "created_via": "seed",
            "published_at": None,
        }
        await db.blog_posts.insert_one(rec.copy())
        composed.append({"slug": slug, "title": title, "category": category})

    return {"composed": composed, "skipped_existing": skipped, "total_drafts_now": len(composed)}


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


# ---------------------------------------------------------------------------
# Public RSS feed — for Medium "Stories Import" and any other feed reader.
# Medium polls the feed; new items become drafts in the user's Medium account.
# ---------------------------------------------------------------------------
@router.get("/rss", response_class=Response)
async def rss_feed():
    """Atom feed of the most recent 30 published posts."""
    posts = await db.blog_posts.find(
        {"status": "published"}, {"_id": 0},
    ).sort("published_at", -1).limit(30).to_list(30)

    site = _frontend_origin()
    feed_self = f"{site}/api/blog/rss"
    feed_link = f"{site}/blog"

    def esc(s: str) -> str:
        return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    items_xml = []
    for p in posts:
        url = f"{site}/blog/{p['slug']}"
        published = p.get("published_at") or p.get("created_at") or _iso(_now())
        # Markdown body wrapped in CDATA so feed readers (incl. Medium) can render it.
        body_md = (p.get("body") or "").strip()
        items_xml.append(
            f"<entry>"
            f"<id>{url}</id>"
            f"<title>{esc(p.get('title') or '')}</title>"
            f"<link href=\"{url}\"/>"
            f"<updated>{published}</updated>"
            f"<published>{published}</published>"
            f"<author><name>AKKI</name></author>"
            f"<summary>{esc(p.get('dek') or '')}</summary>"
            f"<content type=\"html\"><![CDATA[{body_md}]]></content>"
            + "".join(f"<category term=\"{esc(t)}\"/>" for t in (p.get("tags") or []))
            + "</entry>"
        )

    feed = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<feed xmlns="http://www.w3.org/2005/Atom">'
        f'<id>{feed_self}</id>'
        f'<title>{SERIES_NAME} — {SERIES_TAGLINE}</title>'
        f'<subtitle>AKKI · for executives</subtitle>'
        f'<link rel="self" href="{feed_self}"/>'
        f'<link rel="alternate" href="{feed_link}"/>'
        f'<updated>{_iso(_now())}</updated>'
        + "".join(items_xml)
        + '</feed>'
    )
    return Response(content=feed, media_type="application/atom+xml")
