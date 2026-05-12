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
    region: Optional[str] = Query(None, description="ISO-3166 alpha-2 region (or GLOBAL). When omitted, the server resolves it from the user profile / workspace / Accept-Language."),
    diversify: bool = Query(True, description="Round-robin across sources. Set false for pure recency."),
    include_all_regions: bool = Query(False, description="Bypass region filtering — admin/debug only."),
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

    payload = await news_aggregator.query_items(
        db,
        limit=limit,
        since=since,
        source=source,
        region=applied_region,
        diversify=diversify,
        include_all_regions=include_all_regions,
    )

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
