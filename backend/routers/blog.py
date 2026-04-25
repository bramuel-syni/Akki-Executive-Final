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
  - POST /api/blog/subscribe                 — public, captures email
  - GET  /api/blog/subscribers               — admin
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

from core import db, get_current_account, now as _now, iso as _iso, write_audit
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


@router.post("/posts/{slug}/publish")
async def publish_post(
    slug: str,
    current: Dict[str, Any] = Depends(_require_admin),
):
    res = await db.blog_posts.update_one(
        {"slug": slug, "status": "draft"},
        {"$set": {"status": "published", "published_at": _iso(_now())}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Draft not found.")
    rec = await db.blog_posts.find_one({"slug": slug}, {"_id": 0})
    await write_audit(None, current["id"], "blog.published", "blog_post", rec["id"], {"slug": slug})
    return rec


@router.delete("/posts/{slug}")
async def delete_post(
    slug: str,
    current: Dict[str, Any] = Depends(_require_admin),
):
    res = await db.blog_posts.delete_one({"slug": slug})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Post not found.")
    return {"ok": True}


@router.get("/subscribers")
async def list_subscribers(
    current: Dict[str, Any] = Depends(_require_admin),
):
    cursor = db.blog_subscribers.find(
        {"status": "active"}, {"_id": 0},
    ).sort("subscribed_at", -1).limit(2000)
    return {"subscribers": await cursor.to_list(length=2000)}
