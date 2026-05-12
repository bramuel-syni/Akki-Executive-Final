"""News feed endpoint (Patch 21, 2026-05-12).

Reads from the `news_items` collection populated by
`services/news_aggregator.py`. Auth-required (everything in AKKI is
auth-gated), but no per-context scoping — this is curated content.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from core import db, get_current_account

router = APIRouter(prefix="/api", tags=["news"])


class NewsItemOut(BaseModel):
    id: str
    title: str
    summary: str
    url: str
    source: str            # source_name flattened for the frontend
    published_at: datetime


class NewsFeedOut(BaseModel):
    items: List[NewsItemOut]
    total: int


@router.get("/news", response_model=NewsFeedOut)
async def get_news(
    limit: int = Query(10, ge=1, le=50, description="Max items to return"),
    since: Optional[datetime] = Query(None, description="Filter to items published after this ISO8601 timestamp"),
    source: Optional[str] = Query(None, description="Filter to a single source_id"),
    _: Dict[str, Any] = Depends(get_current_account),
) -> NewsFeedOut:
    """Return the latest N news items, newest first.

    The aggregator (services/news_aggregator.py) populates `news_items`
    every ~30 min via an asyncio task started at app boot. If the
    collection is empty (cold start), this endpoint returns
    `{items: [], total: 0}` — the frontend renders an editorial
    fallback line *"News updating — check back shortly."*
    """
    q: Dict[str, Any] = {}
    if since:
        q["published_at"] = {"$gt": since}
    if source:
        q["source_id"] = source

    cursor = (
        db.news_items
        .find(q, {"_id": 0, "id": 1, "title": 1, "summary": 1, "url": 1, "source_name": 1, "published_at": 1})
        .sort("published_at", -1)
        .limit(limit)
    )
    raw = await cursor.to_list(length=limit)
    total = await db.news_items.count_documents(q)

    items = [
        NewsItemOut(
            id=r["id"],
            title=r["title"],
            summary=r.get("summary", ""),
            url=r["url"],
            source=r.get("source_name", r.get("source_id", "")),
            published_at=r["published_at"] if isinstance(r["published_at"], datetime) else datetime.fromisoformat(r["published_at"]),
        )
        for r in raw
    ]
    return NewsFeedOut(items=items, total=total)
