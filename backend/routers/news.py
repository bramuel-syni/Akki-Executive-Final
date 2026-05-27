"""News feed endpoint (Patch 21 + Patch 25, 2026-05-12).

Reads from the `news_items` collection populated by
`services/news_aggregator.py`. Auth-required (everything in AKKI is
auth-gated), but no per-context scoping — this is curated content.

Patch 25 adds:
* Source-balanced diversification (round-robin across sources) so the
  feed never repeats the same source on consecutive headlines unless
  there's no alternative.
* Region filtering. If the caller passes `?region=UK`, only items
  tagged UK or GLOBAL come back. If they omit it, the server resolves
  the region from (profile country | active workspace country |
  Accept-Language | GLOBAL fallback).
* `?diversify=false` and `?include_all_regions=true` for debugging.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel

from core import db, get_current_account
from services import news_aggregator

router = APIRouter(prefix="/api", tags=["news"])


class NewsItemOut(BaseModel):
    id: str
    title: str
    summary: str
    url: str
    source: str            # source_name flattened for the frontend
    published_at: datetime
    regions: List[str]


class NewsFeedOut(BaseModel):
    items: List[NewsItemOut]
    total: int
    region_applied: Optional[str] = None  # resolved or echoed-back region


@router.get("/news", response_model=NewsFeedOut)
async def get_news(
    limit: int = Query(10, ge=1, le=50, description="Max items to return"),
    since: Optional[datetime] = Query(None, description="Filter to items published after this ISO8601 timestamp"),
    source: Optional[str] = Query(None, description="Filter to a single source_id"),
    region: Optional[str] = Query(None, description="ISO-3166 alpha-2 region (or GLOBAL, or the bucket `EAST-AFRICA`). When omitted, the server resolves it from the user profile / workspace / Accept-Language. Task 3: KE/UG/TZ/RW auto-expand to the EAST-AFRICA bucket (Nairobi/Kampala/Dar/Kigali + pan-Africa)."),
    diversify: bool = Query(True, description="Round-robin across sources. Set false for pure recency."),
    include_all_regions: bool = Query(False, description="Bypass region filtering — admin/debug only."),
    quality: Optional[str] = Query(
        None,
        description=(
            "Quality tier filter. `executive` narrows to the tier-1 "
            "executive-grade allowlist (FT, The Economist, Bloomberg, "
            "Reuters, HBR, McKinsey Insights, BoardEffect — plus the "
            "existing curated set). Omit (default) for the full curated "
            "feed. Forward-compatible with future tiers."
        ),
    ),
    accept_language: Optional[str] = Header(None, alias="Accept-Language"),
    account: Dict[str, Any] = Depends(get_current_account),
) -> NewsFeedOut:
    """Return curated news items, diversified by source, region-filtered.

    The aggregator (services/news_aggregator.py) populates `news_items`
    every ~30 min via an asyncio task started at app boot. If the
    collection is empty (cold start), this endpoint returns
    `{items: [], total: 0}` — the frontend renders an editorial
    fallback line.
    """
    # Resolve the region to apply.
    if region:
        applied_region: Optional[str] = region.upper()
    elif include_all_regions:
        applied_region = None
    else:
        applied_region = news_aggregator.resolve_user_region(
            account=account,
            # active_context not threaded here — we keep this endpoint
            # context-agnostic. Workspace-country fallback only kicks
            # in once accounts carry it explicitly (currently none do).
            active_context=None,
            accept_language=accept_language,
        )
        # Task 3 (2026-05-27) — When the resolved country is one of
        # the East-Africa Community states, default the filter to the
        # EAST-AFRICA bucket so the user sees Nairobi/Kampala/Dar/
        # Kigali-relevant items without passing `?region=` explicitly.
        # Other regions (UK / US / EU / GLOBAL) keep their existing
        # single-region semantics.
        if applied_region in _EAST_AFRICA_COUNTRIES:
            applied_region = "EAST-AFRICA"

    # Task 3 — Translate region bucket → list of constituent ISO
    # codes BEFORE the DB query, so MongoDB sees a flat `$in` filter.
    region_bucket: Optional[List[str]] = None
    if applied_region:
        bucket = _REGION_BUCKETS.get(applied_region.upper())
        if bucket:
            region_bucket = bucket

    payload = await news_aggregator.query_items(
        db,
        limit=limit,
        since=since,
        source=source,
        region=applied_region,
        diversify=diversify,
        include_all_regions=include_all_regions,
        region_bucket=region_bucket,
    )

    # H.3 quality filter (2026-05-26) — when ?quality=executive is
    # passed, restrict to the tier-1 allowlist. Applied AFTER the
    # aggregator query to keep diversification + region logic
    # unchanged. The aggregator's existing curated source set (FT,
    # Economist, BBC, NYT, SCMP, Al-Jazeera, BoE) is already
    # executive-grade; the executive tier additionally enables the
    # FT/Economist subset (highest signal-density for board work)
    # while keeping the broader set as fallback when the tier-1
    # subset returns < `limit` items.
    if quality and quality.strip().lower() == "executive":
        tier1_ids = _EXECUTIVE_TIER1_SOURCE_IDS
        tier1_items = [r for r in payload["items"] if r.get("source_id") in tier1_ids]
        # Fallback: if tier-1 subset is thin, keep the unfiltered set
        # so the UI never renders empty. Operator can tighten later.
        if len(tier1_items) >= max(3, limit // 2):
            payload["items"] = tier1_items[:limit]

    items = [
        NewsItemOut(
            id=r["id"],
            title=r["title"],
            summary=r.get("summary", ""),
            url=r["url"],
            source=r.get("source_name", r.get("source_id", "")),
            published_at=r["published_at"] if isinstance(r["published_at"], datetime) else datetime.fromisoformat(r["published_at"]),
            regions=r.get("regions", ["GLOBAL"]),
        )
        for r in payload["items"]
    ]
    return NewsFeedOut(
        items=items,
        total=payload["total"],
        region_applied=payload["region_applied"],
    )


# H.3 — Executive-tier source allowlist (2026-05-26).
# Task 3 (2026-05-27) — Africa expansion + cleanup.
#
# Removed the reserved paid-API IDs (Bloomberg/Reuters-business/
# WSJ-business/HBR/McKinsey-Insights/BoardEffect/Nikkei-Asia/S&P/MIT-
# Sloan) from the live allowlist. They never matched any aggregator
# entry and were silently inflating the apparent tier-1 size without
# contributing items, defeating the strict-filter math. They are
# documented in `_FUTURE_PAID_TIER1_IDS` below for the day the operator
# wires a paid-tier news adapter (NewsAPI Premium, Refinitiv, etc).
#
# What's IN the live tier-1 set now (free + executive-grade):
#   • FT (Companies + Lex), Economist Business, NYT Business
#   • BBC Africa, Quartz Africa, Business Daily Africa, The East
#     African, Nation Africa, The Standard (Kenya) — for the
#     East-Africa user base.
#
# Used by the ?quality=executive filter. Fallback to the full curated
# set kicks in when the tier-1 subset is thin (< max(3, limit//2)).
_EXECUTIVE_TIER1_SOURCE_IDS = frozenset({
    # ── Global executive press ───────────────────────────────────
    "ft-companies",     # FT Companies (RSS, live)
    "ft-lex",           # FT Lex column (RSS, live)
    "economist-biz",    # The Economist — Business (RSS, live)
    "nyt-business",     # NYT Business (RSS, live)
    # ── Africa / East-Africa executive press (Task 3) ────────────
    "bbc-africa",
    "quartz-africa",
    "businessdaily-africa",
    "the-east-african",
    "nation-africa",
    "standard-kenya",
})

# Future paid-tier additions (reserved IDs). When an operator wires a
# paid news adapter, add these ids to the live aggregator + uncomment
# / add them to `_EXECUTIVE_TIER1_SOURCE_IDS`. Until then they're
# code-archaeology, not runtime filter contributors.
_FUTURE_PAID_TIER1_IDS = frozenset({
    "bloomberg",          # Bloomberg Terminal API
    "reuters-business",   # Refinitiv Eikon
    "wsj-business",       # WSJ Pro
    "hbr",                # HBR API
    "mckinsey-insights",  # McKinsey CMS feed
    "boardeffect",        # BoardEffect content syndication
    "nikkei-asia",        # Nikkei Asia paid feed
    "sp-global",          # S&P Global Market Intelligence
    "mit-sloan-review",   # MIT SMR paid feed
})


# Task 3 (2026-05-27) — Region bucket: when the caller asks for
# `region=east-africa`, we expand it to the union of KE, UG, TZ, RW,
# and AF (pan-Africa) so the query matches every Africa-tagged item.
# Same idea as how applied_region="UK" implicitly matches GLOBAL.
_REGION_BUCKETS: Dict[str, List[str]] = {
    "EAST-AFRICA": ["KE", "UG", "TZ", "RW", "AF"],
    "EAST_AFRICA": ["KE", "UG", "TZ", "RW", "AF"],   # accept both spellings
}

# Task 3 — When the user's resolved country is one of these, default
# the region filter to EAST-AFRICA so they see local-relevant news
# without having to pass `?region=` explicitly.
_EAST_AFRICA_COUNTRIES = frozenset({"KE", "UG", "TZ", "RW"})
