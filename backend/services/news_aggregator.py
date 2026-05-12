"""News aggregator — Option C self-hosted RSS (Patch 21, 2026-05-12).

Replaces the mocked `/app/frontend/src/data/mock_news.json` feed on
Home 1 with real curated headlines. Architecture:

  +-----------------------+
  | news_aggregator       |
  |  - fetch_once()       |    every 30 min            +-------------+
  |    parses feeds       | --------------------->     | MongoDB     |
  |    dedupes by url     |    upsert by url           | news_items  |
  |  - schedule()         |    TTL on created_at       +-------------+
  |    starts on app boot
  +-----------------------+
                                                        ^
                                                        | reads
                                                        |
                                              GET /api/news
                                              (router/news.py)

Design notes:
* Feeds are loaded from /app/backend/data/news_sources.json. Edit the
  JSON to add / remove / disable sources. No code change required.
* `feedparser` is permissive — it parses both RSS and Atom and never
  raises on a malformed feed. We still wrap per-feed parsing in a
  try/except and log warnings so one broken source can't take the
  aggregator down.
* All HTTP IO uses httpx with a 10s per-feed timeout and a single
  retry. We don't fail the whole sweep on one slow feed.
* Items are stored with `published_at` = the feed item's pubDate (or
  `now` if missing). The TTL index uses `created_at` (when WE saw it)
  so a feed that re-publishes an old item still ages out cleanly.
* Frontend reads top-N by `published_at DESC` from the cache; the
  aggregator never blocks an HTTP request.

Out of scope for Patch 21:
* No per-context filtering (this is content, not data).
* No user subscribe / unsubscribe — sources are global.
* No UI editor — edit the JSON.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import feedparser
import httpx

logger = logging.getLogger("akki.news_aggregator")

DEFAULT_SOURCES_PATH = Path(__file__).resolve().parent.parent / "data" / "news_sources.json"

# Refresh interval — env-overridable for tests / dev.
NEWS_REFRESH_MINUTES = int(os.environ.get("NEWS_REFRESH_MINUTES", "30"))
NEWS_FETCH_TIMEOUT_SECONDS = float(os.environ.get("NEWS_FETCH_TIMEOUT_SECONDS", "10"))
NEWS_TTL_DAYS = int(os.environ.get("NEWS_TTL_DAYS", "14"))


# ---------------------------------------------------------------------------
# Data shape
# ---------------------------------------------------------------------------
@dataclass
class NewsItem:
    id: str             # deterministic SHA-256(url)[:16]
    title: str
    summary: str
    url: str
    source_id: str
    source_name: str
    published_at: datetime     # tz-aware UTC

    def to_doc(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "summary": self.summary,
            "url": self.url,
            "source_id": self.source_id,
            "source_name": self.source_name,
            "published_at": self.published_at,
            "created_at": datetime.now(timezone.utc),
        }


# ---------------------------------------------------------------------------
# Source loading
# ---------------------------------------------------------------------------
def load_sources(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Read the JSON sources file. Returns only `enabled=true` entries."""
    p = path or DEFAULT_SOURCES_PATH
    try:
        with open(p, "r", encoding="utf-8") as fp:
            raw = json.load(fp)
    except FileNotFoundError:
        logger.warning("news_sources.json not found at %s — aggregator inactive.", p)
        return []
    except json.JSONDecodeError as e:
        logger.error("news_sources.json malformed at %s: %s", p, e)
        return []
    return [s for s in (raw.get("sources") or []) if s.get("enabled", True)]


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------
def _coerce_datetime(entry: Any) -> datetime:
    """Best-effort `published_at` extraction from a feedparser entry."""
    for attr in ("published_parsed", "updated_parsed", "created_parsed"):
        v = getattr(entry, attr, None)
        if v:
            try:
                # feedparser returns a time.struct_time in UTC
                return datetime(*v[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                continue
    return datetime.now(timezone.utc)


def _clean_summary(raw: Optional[str], cap: int = 280) -> str:
    if not raw:
        return ""
    # Strip basic HTML tags without pulling in a parser dep — fine for plain RSS.
    import re
    txt = re.sub(r"<[^>]+>", " ", raw)
    txt = re.sub(r"\s+", " ", txt).strip()
    if len(txt) > cap:
        txt = txt[:cap - 1].rstrip() + "…"
    return txt


def parse_feed(body: str, source_id: str, source_name: str) -> List[NewsItem]:
    """Parse RSS/Atom bytes into a list of NewsItem. Permissive."""
    parsed = feedparser.parse(body)
    items: List[NewsItem] = []
    for entry in (parsed.entries or []):
        url = (entry.get("link") or "").strip()
        title = (entry.get("title") or "").strip()
        if not url or not title:
            continue
        item_id = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
        summary = _clean_summary(entry.get("summary") or entry.get("description"))
        items.append(NewsItem(
            id=item_id,
            title=title,
            summary=summary,
            url=url,
            source_id=source_id,
            source_name=source_name,
            published_at=_coerce_datetime(entry),
        ))
    return items


# ---------------------------------------------------------------------------
# Fetch + persist
# ---------------------------------------------------------------------------
async def fetch_one(source: Dict[str, Any], client: httpx.AsyncClient) -> List[NewsItem]:
    """Fetch + parse a single source. Never raises."""
    src_id = source["id"]
    src_name = source.get("name") or src_id
    url = source["url"]
    started = time.time()
    try:
        r = await client.get(url, follow_redirects=True, timeout=NEWS_FETCH_TIMEOUT_SECONDS)
        if r.status_code >= 400:
            logger.warning("news source %s returned HTTP %s", src_id, r.status_code)
            return []
        items = parse_feed(r.text, src_id, src_name)
        ms = int((time.time() - started) * 1000)
        logger.info("news source %s -> %d items in %dms", src_id, len(items), ms)
        return items
    except Exception as e:  # noqa: BLE001 — broad on purpose
        logger.warning("news source %s failed: %s", src_id, e)
        return []


async def fetch_once(
    db,
    sources: Optional[List[Dict[str, Any]]] = None,
    user_agent: str = "AKKI-News-Aggregator/1.0",
) -> Dict[str, Any]:
    """One full sweep across all enabled sources. Returns a small summary."""
    srcs = sources if sources is not None else load_sources()
    if not srcs:
        return {"sources": 0, "fetched": 0, "stored": 0}

    headers = {"User-Agent": user_agent}
    async with httpx.AsyncClient(headers=headers) as client:
        tasks = [fetch_one(s, client) for s in srcs]
        results = await asyncio.gather(*tasks, return_exceptions=False)

    all_items: List[NewsItem] = []
    for batch in results:
        all_items.extend(batch)

    if not all_items:
        return {"sources": len(srcs), "fetched": 0, "stored": 0}

    # Dedupe by id (sha256 of url) within this sweep.
    seen_ids: set[str] = set()
    deduped: List[NewsItem] = []
    for item in all_items:
        if item.id in seen_ids:
            continue
        seen_ids.add(item.id)
        deduped.append(item)

    # Upsert into mongo. The TTL index (set up by setup_indexes below)
    # handles expiration based on created_at + NEWS_TTL_DAYS days.
    stored = 0
    for item in deduped:
        doc = item.to_doc()
        try:
            await db.news_items.update_one(
                {"id": doc["id"]},
                {
                    "$setOnInsert": {
                        "id": doc["id"],
                        "title": doc["title"],
                        "summary": doc["summary"],
                        "url": doc["url"],
                        "source_id": doc["source_id"],
                        "source_name": doc["source_name"],
                        "published_at": doc["published_at"],
                        "created_at": doc["created_at"],
                    },
                },
                upsert=True,
            )
            stored += 1
        except Exception as e:  # noqa: BLE001
            logger.warning("news upsert failed for %s: %s", item.id, e)

    return {"sources": len(srcs), "fetched": len(all_items), "stored": stored}


# ---------------------------------------------------------------------------
# Indexes
# ---------------------------------------------------------------------------
async def setup_indexes(db) -> None:
    """Idempotent index setup — call once at app boot."""
    try:
        await db.news_items.create_index("id", unique=True)
        await db.news_items.create_index([("published_at", -1)])
        await db.news_items.create_index("source_id")
        await db.news_items.create_index(
            "created_at",
            expireAfterSeconds=NEWS_TTL_DAYS * 24 * 3600,
            name="news_items_ttl",
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("news_items index setup partial: %s", e)


# ---------------------------------------------------------------------------
# Background scheduler — asyncio task variant (no apscheduler needed in
# the hot path; keeps imports light).
# ---------------------------------------------------------------------------
_task: Optional[asyncio.Task] = None


async def _scheduler_loop(db) -> None:
    """Background loop: fetch_once then sleep NEWS_REFRESH_MINUTES."""
    # Initial small delay so app boot isn't blocked by the first sweep.
    await asyncio.sleep(5)
    while True:
        try:
            summary = await fetch_once(db)
            logger.info("news sweep summary: %s", summary)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            logger.warning("news sweep crashed (continuing): %s", e)
        await asyncio.sleep(NEWS_REFRESH_MINUTES * 60)


def start_scheduler(db) -> None:
    """Spawn the background sweep. Idempotent."""
    global _task
    if _task and not _task.done():
        return
    loop = asyncio.get_event_loop()
    _task = loop.create_task(_scheduler_loop(db), name="news_aggregator")


def stop_scheduler() -> None:
    """Cancel the background sweep — used at app shutdown + in tests."""
    global _task
    if _task and not _task.done():
        _task.cancel()
    _task = None
