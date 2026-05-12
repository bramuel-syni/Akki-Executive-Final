# News Feed Options — Home 1 News Strip

> Drafted 2026-05-12 by Patch 15-19 sprint.
> Current state in code: Home 1's "News & signals" strip is rendered from `/app/frontend/src/data/mock_news.json` (5 sample headlines, marked clearly with `data-testid="home1-news-mock-badge"` + the "Curated · sample feed" label). The user needs to choose a real source before this can ship.

---

## Decision context

What this strip is **for**: a 5–8 headline strip on Home 1 (the portfolio entry surface), showing senior-relevant business / governance / FTSE / regulator news that an executive would want to glance at before opening a context. Not a full news reader — just a "what should I know this morning" peek.

What it must **not** be: a click-out farm, a TikTok-style scroll, or anything dominating the Home 1 surface. Five rows max, each ≤2 lines, with source attribution.

---

## Option A — NewsAPI.org

**What**: Off-the-shelf JSON REST API aggregating ~150,000 news sources. Has a `top-headlines` endpoint with `category=business` filter.

**Pros**:
- Easy integration (single API call, well-documented).
- Includes major sources: Reuters, FT, Bloomberg, BBC, The Times, The Economist, WSJ.
- Source citation included in every response (we'd preserve it).

**Cons**:
- Free tier is **developer-only**: 100 requests/day, NO production traffic allowed in their TOS. Production must be on the paid tier.
- Paid tier: $449/month for "Business" plan (100k requests/day). $799/month for "Advanced".
- Some FT/Bloomberg headlines are paywalled at the source — the headline shows, but click-through hits a paywall (acceptable for a senior audience).

**Latency**: ~150ms p95 from EU regions. They have global edge.

**Free-tier safe usage**: cache the response server-side for 30 minutes and serve all users from cache. With AKKI's expected initial volume (<500 portfolio loads/day), 100 requests/day with 30-min caching is *almost* enough — but their TOS still forbids production use.

**Verdict**: Reliable but **expensive at $449/mo minimum** for production.

---

## Option B — Bing News Search API (Azure Cognitive Services)

**What**: Microsoft's news search endpoint inside Azure Cognitive Services. Returns articles + thumbnails + categories.

**Pros**:
- Free tier: **1,000 transactions/month**. With 30-min server-side caching, that's 1 request every 43 min — comfortably enough for AKKI's volume.
- Pricing tiers go up smoothly: S1 = $4 per 1,000 transactions, S2 = $3.50 per 1,000.
- Latency excellent (~80ms p95 from UK South).
- Same region as your Azure stack — keeps egress costs down.

**Cons**:
- Bing has slightly fewer governance-specific sources than NewsAPI (focused on consumer + tech news by default; you can constrain to specific outlets via the `originalCategory` filter).
- Microsoft has periodically restructured the Cognitive Services pricing — keep a quarterly review note.

**Latency**: ~80ms p95 from UK South.

**Pricing (UK South, as of 2026-Q2)**:
- Free F0: 1k tx/month forever — fine for AKKI's initial 6-12 months.
- S1: $4 per 1k tx. At 50 tx/day from caching (1 req per 30 min) → 1.5k tx/mo → $6/mo.

**Verdict**: **Best balance of cost + quality + latency** for AKKI's scale.

---

## Option C — RSS aggregator (self-hosted)

**What**: We curate a list of authoritative RSS feeds, run a daily aggregator (Python `feedparser` in a Kubernetes CronJob), dedupe + rank by recency, expose `/api/me/news` returning the top 8 headlines.

Recommended source list (all have RSS):
- Reuters Business: https://www.reuters.com/finance/markets/rss
- Reuters Business: https://feeds.reuters.com/reuters/businessNews
- BBC Business: http://feeds.bbci.co.uk/news/business/rss.xml
- FT Front Page (Headlines, free RSS — full text gated): https://www.ft.com/rss/home
- Financial Reporting Council UK: https://www.frc.org.uk/news-and-events/rss
- ICAEW Insights: https://www.icaew.com/insights/rss
- Institute of Directors news: https://www.iod.com/news/rss
- Bank of England news: https://www.bankofengland.co.uk/rss/news
- HMT (Treasury): https://www.gov.uk/government/organisations/hm-treasury.atom

**Pros**:
- Zero recurring cost. Full editorial control. No third-party data leakage.
- Easy to add/remove sources without a release.

**Cons**:
- We own the operational risk (a feed goes dark = strip goes empty).
- Headline quality varies — RSS often gives the title only, no image or summary.
- Aggregator code = ~200 lines + a cron job + a small Mongo collection (`news_cache`).

**Latency**: Zero (already-cached in Mongo when AKKI hits it).

**Verdict**: **Most aligned with AKKI's senior/governance audience** — sources are exactly what an audit-committee chair would actually want. Operational cost is low if we keep the source list short.

---

## Option D — Curated editorial feed (manual)

**What**: A trusted human (you, or an AKKI editorial intern) writes 5 headlines twice a week into a CMS or a simple JSON file. AKKI reads from that file.

**Pros**:
- Highest signal-to-noise.
- Perfectly tunable to AKKI's audience.
- Doubles as marketing: each headline can carry an AKKI commentary.

**Cons**:
- Operationally expensive: 2-3 hours of editorial time per week. Stops if the editor goes on holiday.
- Risk of staleness if no one updates it for 2+ weeks.

**Verdict**: **Best as a Phase 2 supplement** to Option B/C, not as the primary feed. The first 6 months of usage data will tell you whether bespoke editorial is worth the time.

---

## My recommendation

**Phase 1 — ship in the next 2 weeks**: **Option C (self-hosted RSS aggregator)**.
- Zero API cost.
- Sources are exactly right for a governance/executive audience (Reuters, BBC, FT, BoE, FRC, ICAEW, IoD).
- Same infrastructure as the rest of AKKI — no new external dependency.
- ~1 backend day to wire: Python CronJob that hits 8 RSS feeds every 30 min, parses with `feedparser`, dedupes by URL, writes top 30 into `news_cache` collection. New endpoint `GET /api/news/feed?limit=8` reads from cache.

**Phase 2 — when volume + revenue justify**: **Option B (Bing News Search)** as a complement.
- Free tier covers AKKI for months.
- Add it as a "Trending" tab alongside the curated/RSS feed.

**Skip**: Option A (NewsAPI — too expensive for the value) and Option D (manual editorial — too operationally fragile).

---

## What to give me back

If you go with the recommended **Option C (RSS)**:
```
NEWS_FEED_OPTION:     C-rss
NEWS_FEED_SOURCES:    confirm the 9 sources listed above, OR send your edited list
NEWS_FEED_REFRESH:    30                 (minutes — 30 is a good default)
NEWS_FEED_TOPN:       8                  (headlines to surface on Home 1)
```

If you go with **Option B (Bing News Search)**:
```
NEWS_FEED_OPTION:               B-bing
AZURE_COGNITIVE_API_KEY:        <from Azure portal -> Cognitive Services -> Keys & Endpoint>
AZURE_COGNITIVE_ENDPOINT:       https://<resource-name>.cognitiveservices.azure.com/
NEWS_FEED_QUERY:                "(business OR governance OR regulatory) UK"  (or your preferred query)
NEWS_FEED_CACHE_MINUTES:        30
```

If you go with **Option A (NewsAPI)**:
```
NEWS_FEED_OPTION:               A-newsapi
NEWSAPI_KEY:                    <from https://newsapi.org/account>
NEWSAPI_CATEGORY:                business
NEWSAPI_COUNTRY:                 gb
NEWSAPI_CACHE_MINUTES:           30
NEWSAPI_TIER:                    business|advanced
```

If you go with **Option D (manual editorial)**:
```
NEWS_FEED_OPTION:               D-manual
EDITORIAL_CMS_URL:              <where you'll publish the feed, or "google sheet">
EDITORIAL_FETCH_URL:            <publicly-readable URL AKKI can poll>
EDITORIAL_REFRESH_MINUTES:      120
```

— end of news-feed options doc —
