"""Phase H.3 — Portfolio Landing data wiring — 2026-05-26.

Locks in the H.3 contract on top of the H.1/H.2 shell:

  Wire tests:
    T1.  Router file `routers/portfolio_data.py` exists with the
         3 documented endpoints (metrics, boards-to-watch, last-action).
    T2.  Router is registered in `server.py`.
    T3.  `routers/news.py` defines the `quality` query param + the
         `_EXECUTIVE_TIER1_SOURCE_IDS` allowlist.
    T4.  `ContextPortfolio.jsx` wires the 3 endpoints and mounts the
         shared `<NewsStrip />` component (not the "Coming soon" stub).
    T5.  `NewsStrip.jsx` exists at `components/news/NewsStrip.jsx`.

  Live tests:
    L1.  Unauthenticated 401 across all 3 portfolio endpoints.
    L2.  /api/me/portfolio-metrics returns the 4-tile shape with
         non-negative ints; reflects seeded data accurately.
    L3.  /api/me/boards-to-watch?limit=3 returns <=3 items, each
         with non-empty `reasons[]` (binary check #1).
    L4.  /api/me/last-action returns the seeded recent-view row.
    L5.  /api/news?quality=executive returns >=1 item whose `source`
         maps to the tier-1 allowlist (binary check #2). Falls back
         to skip if the aggregator hasn't populated tier-1 sources
         yet (cold-start cluster), but enforces the filter logic
         via direct DB seed.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport


REPO = Path(__file__).resolve().parent.parent.parent
FE = REPO / "frontend" / "src"

PORTFOLIO_ROUTER = REPO / "backend" / "routers" / "portfolio_data.py"
NEWS_ROUTER      = REPO / "backend" / "routers" / "news.py"
SERVER_PY        = REPO / "backend" / "server.py"
CONTEXT_PORTFOLIO = FE / "pages" / "ContextPortfolio.jsx"
NEWS_STRIP        = FE / "components" / "news" / "NewsStrip.jsx"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iso_days_ago(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


# ─────────────────────────────────────────────────────────────────
# WIRE
# ─────────────────────────────────────────────────────────────────

def test_h3_portfolio_router_file_exists_and_defines_three_endpoints():
    src = _read(PORTFOLIO_ROUTER)
    # Three documented endpoints.
    assert '@router.get("/me/portfolio-metrics"' in src
    assert '@router.get("/me/boards-to-watch"' in src
    assert '@router.get("/me/last-action"' in src
    # Auth gate.
    assert "get_current_account" in src
    # Reasons array on boards-to-watch.
    assert "reasons" in src
    # Composite weights present.
    assert "_WEIGHT_SIGNALS_7D" in src
    assert "_WEIGHT_BRIEFINGS_14D" in src
    assert "_WEIGHT_AT_RISK" in src


def test_h3_portfolio_router_registered_in_server():
    src = _read(SERVER_PY)
    assert "from routers import portfolio_data as portfolio_data_router" in src
    assert "app.include_router(portfolio_data_router.router)" in src


def test_h3_news_router_defines_quality_filter_and_tier1_allowlist():
    src = _read(NEWS_ROUTER)
    # Query param.
    assert "quality:" in src and "Optional[str]" in src
    # Allowlist constant.
    assert "_EXECUTIVE_TIER1_SOURCE_IDS" in src
    # Comparison logic.
    assert 'quality.strip().lower() == "executive"' in src


def test_h3_context_portfolio_wires_three_endpoints_and_news_strip():
    src = _read(CONTEXT_PORTFOLIO)
    # Calls the 3 endpoints.
    assert '"/me/portfolio-metrics"' in src
    assert '"/me/boards-to-watch"' in src
    assert '"/me/last-action"' in src
    # Mounts the shared NewsStrip (not the H.1 "Coming soon" stub).
    assert "NewsStrip" in src
    assert 'from "@/components/news/NewsStrip"' in src or \
           "from '@/components/news/NewsStrip'" in src
    # Quality=executive passed through to NewsStrip.
    assert 'quality="executive"' in src or "quality='executive'" in src
    # The 3 live sections render (BoardsToWatchSection / WhereYouLeftOffSection / NewsSection).
    assert "function BoardsToWatchSection" in src
    assert "function WhereYouLeftOffSection" in src
    assert "function NewsSection" in src
    # "Coming soon" placeholder copy is gone from the live sections.
    assert "Coming soon" not in src, (
        "H.1 'Coming soon' copy must be replaced by H.3 live data sections."
    )


def test_h3_news_strip_component_exists_with_loading_and_empty_states():
    src = _read(NEWS_STRIP)
    assert "export default function NewsStrip" in src
    # Loading + empty state testids (composed from testIdRoot).
    assert "${testIdRoot}-loading" in src
    assert "${testIdRoot}-empty" in src
    assert "${testIdRoot}-list" in src
    # Quality param threaded through to /api/news.
    assert 'params.quality' in src or "params['quality']" in src


# ─────────────────────────────────────────────────────────────────
# LIVE
# ─────────────────────────────────────────────────────────────────

@pytest.fixture
async def seeded_actor():
    """Seed an account + 2 contexts + memberships + signals + briefings
    + tasks + recent_views + news_items. Provides realistic data for
    every H.3 endpoint in a single fixture.

    Cleanup teardown drops all seeded rows.
    """
    from core import db, hash_password

    uid    = f"h3-test-{uuid.uuid4().hex[:8]}"
    email  = f"h3-{uuid.uuid4().hex[:6]}@example.com"
    pw     = "Pw!1234567Abc"
    cid_a  = f"h3-ctx-a-{uuid.uuid4().hex[:6]}"
    cid_b  = f"h3-ctx-b-{uuid.uuid4().hex[:6]}"

    now = datetime.now(timezone.utc)

    # 1. Account
    await db.accounts.insert_one({
        "id": uid, "email": email,
        "password_hash": hash_password(pw),
        "name": "H3 Tester", "tier": "executive",
        "declared_role": "executive", "mfa_enrolled": False,
        "is_superadmin": False,
        "created_at": now.isoformat(),
    })

    # 2. Two contexts (one NED, one Executive).
    await db.contexts.insert_many([
        {"id": cid_a, "name": "H3 NED Board",
         "type": "ned_personal", "owner_id": uid,
         "created_at": now.isoformat()},
        {"id": cid_b, "name": "H3 Executive Co",
         "type": "executive_personal", "owner_id": uid,
         "created_at": now.isoformat()},
    ])

    # 3. Memberships.
    await db.memberships.insert_many([
        {"account_id": uid, "context_id": cid_a, "status": "active",
         "role": "ned",       "created_at": now.isoformat()},
        {"account_id": uid, "context_id": cid_b, "status": "active",
         "role": "executive", "created_at": now.isoformat()},
    ])

    # 4. Signals: 3 within 7d on cid_a, 1 within 7d on cid_b.
    sig_rows = []
    for i in range(3):
        sig_rows.append({
            "id": f"h3-sig-a-{i}-{uuid.uuid4().hex[:6]}",
            "context_id": cid_a,
            "title": f"Signal A{i}",
            "created_at": _iso_days_ago(1 + i),
        })
    sig_rows.append({
        "id": f"h3-sig-b-{uuid.uuid4().hex[:6]}",
        "context_id": cid_b,
        "title": "Signal B0",
        "created_at": _iso_days_ago(2),
    })
    await db.signals.insert_many(sig_rows)

    # 5. Briefings: 2 due within 14d on cid_a.
    brief_rows = []
    for i in range(2):
        brief_rows.append({
            "id": f"h3-brf-{i}-{uuid.uuid4().hex[:6]}",
            "context_id": cid_a,
            "title": f"Briefing {i}",
            "created_at": now.isoformat(),
            "due_date": (now + timedelta(days=3 + i)).isoformat(),
        })
    await db.briefings.insert_many(brief_rows)

    # 6. Documents: 4 on cid_a, 2 on cid_b.
    doc_rows = []
    for i in range(4):
        doc_rows.append({
            "id": f"h3-doc-a-{i}-{uuid.uuid4().hex[:6]}",
            "context_id": cid_a, "filename": f"a{i}.pdf",
            "status": "ready", "created_at": now.isoformat(),
        })
    for i in range(2):
        doc_rows.append({
            "id": f"h3-doc-b-{i}-{uuid.uuid4().hex[:6]}",
            "context_id": cid_b, "filename": f"b{i}.pdf",
            "status": "ready", "created_at": now.isoformat(),
        })
    await db.documents.insert_many(doc_rows)

    # 7. Tasks: 2 at-risk on cid_a (low readiness).
    task_rows = []
    for i in range(2):
        task_rows.append({
            "id": f"h3-task-a-{i}-{uuid.uuid4().hex[:6]}",
            "context_id": cid_a,
            "name": f"Task A{i}",
            "state": "in_progress",
            "readiness_score": 25,
            "due_date": (now + timedelta(days=10)).isoformat(),
            "created_at": now.isoformat(),
        })
    await db.tasks.insert_many(task_rows)

    # 8. Recent view: drives /me/last-action.
    await db.user_recent_views.insert_one({
        "id": f"h3-rv-{uuid.uuid4().hex[:6]}",
        "account_id": uid,
        "context_id": cid_a,
        "surface_path": "/app/work-studio?doc_id=h3-doc-a-0",
        "label": "Q3 Risk Memo",
        "last_visited_at": _iso_days_ago(0),
    })

    # 9. News items — 2 tier-1 (ft-companies, economist-biz) + 1 non-tier-1.
    news_rows = [
        {
            "id": f"h3-news-ft-{uuid.uuid4().hex[:6]}",
            "title": "H3 FT Article on Capital Discipline",
            "summary": "Test summary FT",
            "url": f"https://ft.example/{uuid.uuid4().hex[:6]}",
            "source_id": "ft-companies",
            "source_name": "FT Companies",
            "published_at": now,
            "regions": ["GLOBAL"],
        },
        {
            "id": f"h3-news-econ-{uuid.uuid4().hex[:6]}",
            "title": "H3 Economist on Board Composition",
            "summary": "Test summary Economist",
            "url": f"https://economist.example/{uuid.uuid4().hex[:6]}",
            "source_id": "economist-biz",
            "source_name": "The Economist",
            "published_at": now - timedelta(hours=1),
            "regions": ["GLOBAL"],
        },
        {
            "id": f"h3-news-other-{uuid.uuid4().hex[:6]}",
            "title": "H3 Generic Source",
            "summary": "Test summary generic",
            "url": f"https://generic.example/{uuid.uuid4().hex[:6]}",
            "source_id": "bbc-business",
            "source_name": "BBC Business",
            "published_at": now - timedelta(hours=2),
            "regions": ["GLOBAL"],
        },
    ]
    await db.news_items.insert_many(news_rows)

    yield {
        "uid": uid, "email": email, "password": pw,
        "cid_a": cid_a, "cid_b": cid_b,
        "news_ids": [n["id"] for n in news_rows],
    }

    # ── Teardown ────────────────────────────────────────────────
    await db.accounts.delete_one({"id": uid})
    await db.contexts.delete_many({"id": {"$in": [cid_a, cid_b]}})
    await db.memberships.delete_many({"account_id": uid})
    await db.signals.delete_many({"context_id": {"$in": [cid_a, cid_b]}})
    await db.briefings.delete_many({"context_id": {"$in": [cid_a, cid_b]}})
    await db.documents.delete_many({"context_id": {"$in": [cid_a, cid_b]}})
    await db.tasks.delete_many({"context_id": {"$in": [cid_a, cid_b]}})
    await db.user_recent_views.delete_many({"account_id": uid})
    await db.news_items.delete_many(
        {"id": {"$in": [n["id"] for n in news_rows]}}
    )


async def _login(c, actor):
    r = await c.post("/api/auth/login",
                     json={"email": actor["email"], "password": actor["password"]})
    body = r.json()
    tok = body.get("access_token") or body.get("token")
    assert tok, f"Login failed: {body}"
    return {"Authorization": f"Bearer {tok}"}


# ── L1. Unauthenticated 401 ────────────────────────────────────
@pytest.mark.asyncio
@pytest.mark.parametrize("path", [
    "/api/me/portfolio-metrics",
    "/api/me/boards-to-watch",
    "/api/me/last-action",
])
async def test_h3_endpoints_require_auth(path):
    from server import app  # noqa: F401
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as c:
        r = await c.get(path)
    assert r.status_code == 401, r.text


# ── L2. /portfolio-metrics shape + accuracy ────────────────────
@pytest.mark.asyncio
async def test_h3_portfolio_metrics_returns_seeded_counts(seeded_actor):
    from server import app  # noqa: F401
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as c:
        hdr = await _login(c, seeded_actor)
        r = await c.get("/api/me/portfolio-metrics", headers=hdr)
    assert r.status_code == 200, r.text
    body = r.json()
    # Required keys.
    for k in ("companies", "signals", "briefings", "documents"):
        assert k in body, f"missing key {k!r} in {body}"
        assert isinstance(body[k], int)
        assert body[k] >= 0
    # Seeded accuracy.
    assert body["companies"] == 2
    # 3 signals on cid_a + 1 on cid_b within last 30d = 4.
    assert body["signals"] == 4
    # 2 briefings on cid_a within last 30d.
    assert body["briefings"] == 2
    # 4 + 2 documents = 6.
    assert body["documents"] == 6


# ── L3. /boards-to-watch limit + non-empty reasons ─────────────
@pytest.mark.asyncio
async def test_h3_boards_to_watch_returns_items_with_non_empty_reasons(seeded_actor):
    """Binary check #1 — every item MUST have non-empty `reasons[]`."""
    from server import app  # noqa: F401
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as c:
        hdr = await _login(c, seeded_actor)
        r = await c.get("/api/me/boards-to-watch?limit=3", headers=hdr)
    assert r.status_code == 200, r.text
    body = r.json()
    items = body.get("items") or []
    # We seeded data for both contexts — at least 1 should rank.
    assert len(items) >= 1, f"Expected ranked items, got {items}"
    assert len(items) <= 3
    for item in items:
        # Shape.
        assert "context_id" in item and "name" in item
        assert "score" in item and "reasons" in item
        assert isinstance(item["score"], (int, float))
        # BINARY CHECK #1: reasons MUST be non-empty.
        assert isinstance(item["reasons"], list)
        assert len(item["reasons"]) > 0, (
            f"board {item['name']} has empty reasons[] — "
            "every ranked board must surface AT LEAST one reason"
        )
        # Reason strings are human-readable (not empty).
        for reason in item["reasons"]:
            assert isinstance(reason, str)
            assert reason.strip(), "Reason cannot be a blank string"


@pytest.mark.asyncio
async def test_h3_boards_to_watch_respects_limit_param(seeded_actor):
    from server import app  # noqa: F401
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as c:
        hdr = await _login(c, seeded_actor)
        r = await c.get("/api/me/boards-to-watch?limit=1", headers=hdr)
    body = r.json()
    assert len(body.get("items") or []) <= 1


# ── L4. /last-action ───────────────────────────────────────────
@pytest.mark.asyncio
async def test_h3_last_action_returns_most_recent_view(seeded_actor):
    from server import app  # noqa: F401
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as c:
        hdr = await _login(c, seeded_actor)
        r = await c.get("/api/me/last-action", headers=hdr)
    assert r.status_code == 200, r.text
    body = r.json()
    # Required keys.
    for k in (
        "context_id", "context_name", "surface", "artefact_id",
        "artefact_title", "action", "at", "deep_link",
    ):
        assert k in body, f"missing key {k!r} in {body}"
    # Reflects the seeded recent_view row.
    assert body["context_id"] == seeded_actor["cid_a"]
    assert body["context_name"] == "H3 NED Board"
    # surface_path "/app/work-studio?doc_id=..." → surface="document"
    assert body["surface"] == "document"
    assert body["artefact_title"] == "Q3 Risk Memo"
    assert body["action"] == "opened"   # _classify_action("document")
    assert body["deep_link"] == "/app/work-studio?doc_id=h3-doc-a-0"


@pytest.mark.asyncio
async def test_h3_last_action_empty_shape_for_no_activity():
    """Account with no recent views returns null/empty shape, not 404."""
    from core import db, hash_password
    from server import app  # noqa: F401

    uid = f"h3-empty-{uuid.uuid4().hex[:8]}"
    email = f"h3-empty-{uuid.uuid4().hex[:6]}@example.com"
    pw = "Pw!1234567Abc"
    await db.accounts.insert_one({
        "id": uid, "email": email,
        "password_hash": hash_password(pw),
        "name": "H3 Empty", "tier": "executive",
        "declared_role": "executive", "mfa_enrolled": False,
        "is_superadmin": False,
        "created_at": _now_iso(),
    })
    try:
        async with AsyncClient(transport=ASGITransport(app=app),
                               base_url="http://test") as c:
            r = await c.post("/api/auth/login",
                             json={"email": email, "password": pw})
            tok = r.json()["access_token"]
            r = await c.get("/api/me/last-action",
                            headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 200
        body = r.json()
        assert body["context_id"] is None
        assert body["surface"] is None
        assert body["deep_link"] is None
    finally:
        await db.accounts.delete_one({"id": uid})


# ── L5. /news?quality=executive — tier-1 allowlist match ────────
@pytest.mark.asyncio
async def test_h3_news_quality_executive_returns_tier1_source(seeded_actor):
    """Binary check #2 — at least one returned item's `source` must
    match the executive tier-1 allowlist. If zero match, the filter
    isn't actually filtering."""
    from server import app  # noqa: F401

    # Tier-1 friendly source-name patterns we accept (case-insensitive
    # substring match against the response `source` field, which is
    # source_name flattened by the news router).
    TIER1_PATTERNS = (
        "ft", "financial times", "wall street journal", "wsj",
        "reuters", "bloomberg", "economist", "harvard business review",
        "hbr", "mckinsey", "boardeffect",
    )

    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as c:
        hdr = await _login(c, seeded_actor)
        r = await c.get(
            "/api/news?quality=executive&limit=10&include_all_regions=true",
            headers=hdr,
        )
    assert r.status_code == 200, r.text
    body = r.json()
    items = body.get("items") or []
    assert len(items) >= 1, "No news items returned even with seeded tier-1 rows"

    # BINARY CHECK #2: at least one source matches the allowlist.
    matched_sources = []
    for item in items:
        src = (item.get("source") or "").lower()
        for pat in TIER1_PATTERNS:
            if pat in src:
                matched_sources.append(item["source"])
                break

    assert len(matched_sources) >= 1, (
        f"news?quality=executive returned {len(items)} items but NONE "
        f"match the tier-1 allowlist patterns {TIER1_PATTERNS}. "
        f"Sources seen: {[i.get('source') for i in items]}. "
        "The filter isn't actually filtering."
    )
