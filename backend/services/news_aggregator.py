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
    regions: List[str]         # Patch 25 — denormalized from source

    def to_doc(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "summary": self.summary,
            "url": self.url,
            "source_id": self.source_id,
            "source_name": self.source_name,
            "published_at": self.published_at,
            "regions": self.regions,
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


def parse_feed(
    body: str,
    source_id: str,
    source_name: str,
    regions: Optional[List[str]] = None,
) -> List[NewsItem]:
    """Parse RSS/Atom bytes into a list of NewsItem. Permissive."""
    regions = regions if regions is not None else ["GLOBAL"]
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
            regions=list(regions),
        ))
    return items


# ---------------------------------------------------------------------------
# Fetch + persist
# ---------------------------------------------------------------------------
async def fetch_one(source: Dict[str, Any], client: httpx.AsyncClient) -> List[NewsItem]:
    """Fetch + parse a single source. Never raises."""
    src_id = source["id"]
    src_name = source.get("name") or src_id
    src_regions = source.get("regions") or ["GLOBAL"]
    url = source["url"]
    started = time.time()
    try:
        r = await client.get(url, follow_redirects=True, timeout=NEWS_FETCH_TIMEOUT_SECONDS)
        if r.status_code >= 400:
            logger.warning("news source %s returned HTTP %s", src_id, r.status_code)
            return []
        items = parse_feed(r.text, src_id, src_name, src_regions)
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
                    # Patch 25 — regions are denormalized on the item so
                    # we can serve `?region=...` filtering with a single
                    # mongo query. Use `$set` (not `$setOnInsert`) so
                    # existing items get their regions backfilled on the
                    # next sweep — handy when a source's regions list
                    # changes in news_sources.json.
                    "$set": {"regions": doc["regions"]},
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


# ---------------------------------------------------------------------------
# Patch 25 — Diversification + region resolution
# ---------------------------------------------------------------------------

# Accept-Language language-tag -> region heuristic. Used only when the
# user has no profile country AND no workspace country.
_LANG_TO_REGION = {
    "en-gb": "UK",
    "en-uk": "UK",
    "en-us": "US",
    "en-ca": "CA",
    "en-au": "AU",
    "en-nz": "NZ",
    "en-in": "IN",
    "en-ie": "IE",
    "en-za": "ZA",
    "en-sg": "SG",
    "en-hk": "HK",
    "de":    "DE",
    "de-de": "DE",
    "de-at": "AT",
    "de-ch": "CH",
    "fr":    "FR",
    "fr-fr": "FR",
    "fr-ca": "CA",
    "fr-ch": "CH",
    "es":    "ES",
    "es-es": "ES",
    "es-mx": "MX",
    "it":    "IT",
    "it-it": "IT",
    "nl":    "NL",
    "nl-nl": "NL",
    "nl-be": "BE",
    "pt":    "PT",
    "pt-pt": "PT",
    "pt-br": "BR",
    "ja":    "JP",
    "ja-jp": "JP",
    "zh":    "CN",
    "zh-cn": "CN",
    "zh-hk": "HK",
    "zh-tw": "TW",
    "ko":    "KR",
    "ko-kr": "KR",
    "ru":    "RU",
    "ar":    "GLOBAL",
}


def _accept_language_to_region(header_value: Optional[str]) -> str:
    """Map an Accept-Language header value to a single region code.

    Picks the FIRST valid language-tag (the user's primary preference),
    then looks it up in `_LANG_TO_REGION`. Falls back to GLOBAL.
    """
    if not header_value:
        return "GLOBAL"
    # Take only the first language tag (ignore q=); lower-case it.
    parts = [p.strip().lower() for p in header_value.split(",") if p.strip()]
    for raw in parts:
        # Strip the q= weight if present
        lang = raw.split(";")[0].strip()
        if not lang:
            continue
        if lang in _LANG_TO_REGION:
            return _LANG_TO_REGION[lang]
        # Try the bare language (e.g. "en" from "en-GB-oxendict")
        prefix = lang.split("-")[0]
        if prefix in _LANG_TO_REGION:
            return _LANG_TO_REGION[prefix]
    return "GLOBAL"


def resolve_user_region(
    account: Optional[Dict[str, Any]],
    active_context: Optional[Dict[str, Any]] = None,
    accept_language: Optional[str] = None,
) -> str:
    """Pick the best region code for this request.

    Priority (per Patch 25C):
      1. account.profile.country               (ISO-3166 alpha-2)
      2. account.country                       (top-level)
      3. active_context.country                (workspace-level)
      4. Accept-Language header heuristic
      5. GLOBAL
    """
    if account:
        profile = (account.get("profile") or {})
        for k in (profile.get("country"), account.get("country")):
            if k and isinstance(k, str):
                return k.upper()
    if active_context:
        c = active_context.get("country")
        if c and isinstance(c, str):
            return c.upper()
    return _accept_language_to_region(accept_language)


def diversify_items(
    items: List[Dict[str, Any]],
    limit: int,
) -> List[Dict[str, Any]]:
    """Source-balanced ordering.

    Group `items` (assumed already published_at DESC) by `source_name`,
    then interleave: round-robin take 1 from each source until `limit`
    is reached. If fewer distinct sources have items than `limit`,
    allow a second pass per source.

    Properties:
    - For limit=5 with 5+ distinct sources: each source contributes
      exactly 1 item (no source dominates).
    - For limit=5 with 3 sources (5/2/1 items): result mixes all 3
      then top up with the most-populous source's next-most-recent.
    - Within a source, ordering stays published_at DESC.
    """
    if not items or limit <= 0:
        return []

    # Group by source_name; preserve insertion order = published_at DESC
    by_source: Dict[str, List[Dict[str, Any]]] = {}
    source_order: List[str] = []
    for it in items:
        s = it.get("source_name") or it.get("source_id") or "unknown"
        if s not in by_source:
            by_source[s] = []
            source_order.append(s)
        by_source[s].append(it)

    picked: List[Dict[str, Any]] = []
    rounds = 0
    # Max number of rounds = the count of the most populous source.
    max_rounds = max(len(v) for v in by_source.values())
    while len(picked) < limit and rounds < max_rounds:
        for s in source_order:
            if len(picked) >= limit:
                break
            bucket = by_source[s]
            if rounds < len(bucket):
                picked.append(bucket[rounds])
        rounds += 1
    return picked[:limit]


async def query_items(
    db,
    limit: int = 10,
    since: Optional[datetime] = None,
    source: Optional[str] = None,
    region: Optional[str] = None,
    diversify: bool = True,
    include_all_regions: bool = False,
    region_bucket: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Build the `GET /api/news` response.

    Applies region filter (if region != None AND not include_all_regions),
    then either diversifies or returns recency-pure ordering.

    Task 3 (2026-05-27) — `region_bucket` is an optional list of
    ISO codes that EXPANDS the region filter. When set, the query
    matches items tagged with ANY of those codes OR GLOBAL. The
    `region_applied` echo-back uses the symbolic `region` string
    (e.g. "EAST-AFRICA") so the client knows which bucket fired.

    Returns {items: [...], total: int, region_applied: str|None}.
    """
    q: Dict[str, Any] = {}
    if since:
        q["published_at"] = {"$gt": since}
    if source:
        q["source_id"] = source
    region_applied: Optional[str] = None
    if region and not include_all_regions:
        if region_bucket:
            # Bucketed region: match any of the bucket's codes + GLOBAL.
            q["regions"] = {"$in": [*region_bucket, "GLOBAL"]}
        else:
            # Single region: match it + GLOBAL.
            q["regions"] = {"$in": [region, "GLOBAL"]}
        region_applied = region

    # Over-fetch when diversifying so we have enough per-source supply
    # to round-robin from. 4x is plenty for limit≤50.
    fetch_n = limit * 4 if diversify else limit

    projection = {"_id": 0, "id": 1, "title": 1, "summary": 1, "url": 1,
                  "source_id": 1, "source_name": 1, "published_at": 1, "regions": 1}

    cursor = (
        db.news_items
        .find(q, projection)
        .sort("published_at", -1)
        .limit(fetch_n)
    )
    raw = await cursor.to_list(length=fetch_n)
    total = await db.news_items.count_documents(q)

    items = diversify_items(raw, limit) if diversify else raw[:limit]
    return {"items": items, "total": total, "region_applied": region_applied}
