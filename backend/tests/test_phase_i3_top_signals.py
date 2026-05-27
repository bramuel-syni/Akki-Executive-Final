"""Phase I.3 — Top Signals rail wiring CI guard (2026-05-27).

Locks the Top Signals contract:

  Backend:
    T1.  Endpoint `/api/me/company-home/top-signals` exists and
         requires auth + membership.
    T2.  Pulse chip — items sorted by severity tier (critical >
         warning > info) then timestamp desc within tier.
    T3.  Monitor chip — sourced from the checklists/submissions/
         reports UNION (per the user-confirmed mid-flight scope
         clarification); items carry `severity=null`; sorted by
         timestamp desc.
    T4.  Documents chip — sourced from `db.documents` sorted by
         updated_at desc; items carry `severity=null`.
    T5.  Unknown chip → 400. Non-member → 403. 60s cache.

  Frontend wire:
    T6.  CompanyHome.jsx fetches `/me/company-home/top-signals` and
         renders `data-testid="top-signal-{chip}-{idx}"` for each
         item.
    T7.  Default selected chip = pulse; clicking a different chip
         calls setChip + refetches.
    T8.  Empty state copy = "Nothing on Monitor yet." (per user's
         brief, NOT generic "no signals" language).
    T9.  Item click → navigate(item.deep_link).
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport


REPO = Path(__file__).resolve().parent.parent.parent
COMPANY_HOME_JSX = REPO / "frontend" / "src" / "pages" / "CompanyHome.jsx"
ROUTER           = REPO / "backend" / "routers" / "company_home.py"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _iso(dt: datetime) -> str:
    return dt.isoformat()


# ═════════════════════════════════════════════════════════════════
# Backend live tests
# ═════════════════════════════════════════════════════════════════

@pytest.fixture
async def i3_actor():
    from core import db, hash_password
    uid = f"i3-{uuid.uuid4().hex[:8]}"
    email = f"i3-{uuid.uuid4().hex[:6]}@example.com"
    pw = "Pw!1234567Abc"
    cid = f"i3-ctx-{uuid.uuid4().hex[:6]}"
    now = datetime.now(timezone.utc)
    now_iso = _iso(now)

    await db.accounts.insert_one({
        "id": uid, "email": email, "password_hash": hash_password(pw),
        "name": "I3 Tester", "tier": "executive",
        "declared_role": "executive", "mfa_enrolled": False,
        "is_superadmin": False, "created_at": now_iso,
    })
    await db.contexts.insert_one({
        "id": cid, "name": "I3 Test Co",
        "type": "executive_personal", "owner_id": uid,
        "created_at": now_iso,
    })
    await db.memberships.insert_one({
        "account_id": uid, "context_id": cid, "status": "active",
        "role": "executive", "created_at": now_iso,
    })

    # ── Seed Pulse: 1 risk + 1 opportunity + 1 unknown-type
    await db.signals.insert_many([
        {"id": "i3-sig-risk", "context_id": cid, "type": "risk",
         "headline": "Risk signal alpha", "summary": "summary risk",
         "created_at": _iso(now - timedelta(hours=1))},
        {"id": "i3-sig-opp", "context_id": cid, "type": "opportunity",
         "headline": "Opportunity signal beta",
         "summary": "summary opp",
         "created_at": _iso(now - timedelta(hours=2))},
        {"id": "i3-sig-misc", "context_id": cid, "type": "trend",
         "headline": "Trend signal gamma",
         "summary": "summary misc",
         "created_at": _iso(now - timedelta(hours=3))},
    ])

    # ── Seed Monitor: 1 checklist + 1 submission + 1 report
    await db.checklists.insert_one({
        "id": "i3-ck-1", "context_id": cid, "status": "active",
        "name": "Q4 risk register review",
        "updated_at": _iso(now - timedelta(minutes=30)),
    })
    await db.submissions.insert_one({
        "id": "i3-sb-1", "context_id": cid, "status": "pending_approval",
        "subject": "Board pack draft",
        "updated_at": _iso(now - timedelta(minutes=20)),
    })
    await db.reports.insert_one({
        "id": "i3-rp-1", "context_id": cid, "status": "in_review",
        "title": "Audit committee minutes",
        "updated_at": _iso(now - timedelta(minutes=10)),
    })

    # ── Seed Documents: 3 docs, varying updated_at
    await db.documents.insert_many([
        {"id": "i3-doc-1", "context_id": cid,
         "name": "Doc Alpha", "doc_type": "PDF",
         "updated_at": _iso(now - timedelta(minutes=5)),
         "created_at": _iso(now - timedelta(days=1))},
        {"id": "i3-doc-2", "context_id": cid,
         "name": "Doc Bravo", "doc_type": "Memo",
         "updated_at": _iso(now - timedelta(minutes=15)),
         "created_at": _iso(now - timedelta(days=2))},
        {"id": "i3-doc-3", "context_id": cid,
         "name": "Doc Charlie", "doc_type": "Spreadsheet",
         "updated_at": _iso(now - timedelta(minutes=25)),
         "created_at": _iso(now - timedelta(days=3))},
    ])

    yield {"uid": uid, "email": email, "password": pw, "cid": cid}

    # ── Teardown
    await db.accounts.delete_one({"id": uid})
    await db.contexts.delete_one({"id": cid})
    await db.memberships.delete_many({"account_id": uid})
    await db.signals.delete_many({"context_id": cid})
    await db.checklists.delete_many({"context_id": cid})
    await db.submissions.delete_many({"context_id": cid})
    await db.reports.delete_many({"context_id": cid})
    await db.documents.delete_many({"context_id": cid})


async def _login(c, actor):
    r = await c.post("/api/auth/login",
                     json={"email": actor["email"], "password": actor["password"]})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ── T1. Auth + membership gate ────────────────────────────────────
@pytest.mark.asyncio
async def test_i3_top_signals_requires_auth():
    from server import app  # noqa: F401
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as c:
        r = await c.get("/api/me/company-home/top-signals?context_id=any&chip=pulse")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_i3_top_signals_blocks_non_member(i3_actor):
    from server import app  # noqa: F401
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as c:
        hdr = await _login(c, i3_actor)
        r = await c.get(
            "/api/me/company-home/top-signals?context_id=not-a-member-ctx&chip=pulse",
            headers=hdr,
        )
    assert r.status_code == 403


# ── T2. Pulse chip — severity-tier-then-time sort ────────────────
@pytest.mark.asyncio
async def test_i3_pulse_chip_sorts_critical_first(i3_actor):
    from server import app  # noqa: F401
    cid = i3_actor["cid"]
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as c:
        hdr = await _login(c, i3_actor)
        r = await c.get(
            f"/api/me/company-home/top-signals?context_id={cid}&chip=pulse",
            headers=hdr,
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["chip"] == "pulse"
    items = body["items"]
    assert len(items) == 3
    # Severity order: risk → critical (rank 0); trend → warning (rank 1);
    # opportunity → info (rank 2).
    assert items[0]["severity"] == "critical"
    assert items[0]["id"] == "signal:i3-sig-risk"
    assert items[1]["severity"] == "warning"
    assert items[1]["id"] == "signal:i3-sig-misc"
    assert items[2]["severity"] == "info"
    assert items[2]["id"] == "signal:i3-sig-opp"
    # Deep link shape.
    assert "signal_id=i3-sig-risk" in items[0]["deep_link"]
    assert f"context_id={cid}" in items[0]["deep_link"]


# ── T3. Monitor chip — union of checklists/submissions/reports ──
@pytest.mark.asyncio
async def test_i3_monitor_chip_unions_checklists_submissions_reports(i3_actor):
    from server import app  # noqa: F401
    cid = i3_actor["cid"]
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as c:
        hdr = await _login(c, i3_actor)
        r = await c.get(
            f"/api/me/company-home/top-signals?context_id={cid}&chip=monitor",
            headers=hdr,
        )
    assert r.status_code == 200
    body = r.json()
    assert body["chip"] == "monitor"
    items = body["items"]
    assert len(items) == 3, f"expected 3 monitor items, got {items}"
    # Sort: timestamp desc — report (10min) > submission (20min) > checklist (30min).
    assert items[0]["id"] == "report:i3-rp-1"
    assert items[1]["id"] == "submission:i3-sb-1"
    assert items[2]["id"] == "checklist:i3-ck-1"
    # Severity is null across (no severity field on these collections).
    for it in items:
        assert it["severity"] is None
    # Subtitle decoration: kind prefix + status.
    assert items[0]["subtitle"].startswith("Report")
    assert items[1]["subtitle"].startswith("Submission")
    assert items[2]["subtitle"] == "Checklist · Active"
    # Deep link shape (focus marker).
    assert "focus=report:i3-rp-1" in items[0]["deep_link"]


# ── T4. Documents chip — recency sort, severity=null ─────────────
@pytest.mark.asyncio
async def test_i3_documents_chip_sorts_by_updated_at_desc(i3_actor):
    from server import app  # noqa: F401
    cid = i3_actor["cid"]
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as c:
        hdr = await _login(c, i3_actor)
        r = await c.get(
            f"/api/me/company-home/top-signals?context_id={cid}&chip=documents",
            headers=hdr,
        )
    assert r.status_code == 200
    body = r.json()
    assert body["chip"] == "documents"
    items = body["items"]
    assert len(items) == 3
    # Sort: updated_at desc.
    assert items[0]["id"] == "document:i3-doc-1"
    assert items[1]["id"] == "document:i3-doc-2"
    assert items[2]["id"] == "document:i3-doc-3"
    # Severity null across.
    for it in items:
        assert it["severity"] is None
    # Deep link → /app/work-studio?doc_id=…
    assert "doc_id=i3-doc-1" in items[0]["deep_link"]


# ── T5. Unknown chip → 400 ───────────────────────────────────────
@pytest.mark.asyncio
async def test_i3_unknown_chip_400(i3_actor):
    from server import app  # noqa: F401
    cid = i3_actor["cid"]
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as c:
        hdr = await _login(c, i3_actor)
        r = await c.get(
            f"/api/me/company-home/top-signals?context_id={cid}&chip=bogus",
            headers=hdr,
        )
    assert r.status_code == 400


# ── Cache TTL effective ─────────────────────────────────────────
@pytest.mark.asyncio
async def test_i3_cache_returns_same_payload_within_ttl(i3_actor):
    from server import app  # noqa: F401
    cid = i3_actor["cid"]
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as c:
        hdr = await _login(c, i3_actor)
        r1 = await c.get(
            f"/api/me/company-home/top-signals?context_id={cid}&chip=pulse",
            headers=hdr,
        )
        r2 = await c.get(
            f"/api/me/company-home/top-signals?context_id={cid}&chip=pulse",
            headers=hdr,
        )
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json() == r2.json()


# ═════════════════════════════════════════════════════════════════
# Frontend wire tests
# ═════════════════════════════════════════════════════════════════

# ── T6. CompanyHome fetches the endpoint and renders the testid pattern
def test_i3_company_home_fetches_top_signals_endpoint():
    src = _read(COMPANY_HOME_JSX)
    assert "/me/company-home/top-signals" in src, (
        "CompanyHome.jsx must fetch /me/company-home/top-signals."
    )
    # Testid pattern: top-signal-{chip}-{idx}.
    assert "top-signal-${chip}-${idx}" in src


# ── T7. Default chip = pulse; setChip on click switches chip ────
def test_i3_pulse_is_default_chip_and_setchip_drives_refetch():
    src = _read(COMPANY_HOME_JSX)
    assert 'useState("pulse")' in src, "default chip must be pulse"
    # The fetch effect depends on `chip` so refetch fires on chip change.
    assert "[cid, chip, topSignals]" in src, (
        "Top-signals useEffect must depend on `chip` (and cid + topSignals "
        "for memoization)."
    )


# ── T8. Empty-state copy ─────────────────────────────────────────
def test_i3_empty_state_copy_is_chip_specific():
    src = _read(COMPANY_HOME_JSX)
    # Monitor chip carries the user-mandated copy verbatim.
    assert "Nothing on Monitor yet." in src, (
        "Empty state copy must include 'Nothing on Monitor yet.' for "
        "the Monitor chip."
    )
    # Documents chip: must NOT use generic 'no signals' phrasing.
    assert "No documents yet." in src, (
        "Documents chip empty state must be 'No documents yet.' "
        "(brief: don't say 'no signals' for Documents)."
    )
    # Pulse chip: 'No pulse updates yet.' — chip-specific.
    assert "No pulse updates yet." in src
    # The old I.1 'Coming soon' placeholder must be gone from the rail body.
    assert src.count("Coming soon") == 0, (
        "Coming soon placeholder must be replaced now that the rail body "
        "is data-wired."
    )


# ── T9. Item click → navigate(item.deep_link) ────────────────────
def test_i3_item_click_navigates_to_deep_link():
    src = _read(COMPANY_HOME_JSX)
    # The handler should pull deep_link off the item and navigate.
    assert "onOpenTopSignalItem" in src
    assert "navigate(item.deep_link)" in src


# ── T10. Router executable code uses the union (not a magical
# `monitor_alerts` collection) ───────────────────────────────────
def test_i3_router_does_not_query_a_monitor_alerts_collection():
    """The brief's `monitor_alerts` naming was clarified mid-flight
    to the live monitor surface's union (checklists + submissions +
    reports). The router must NOT silently introduce or query a
    `monitor_alerts` collection — that would have been a phantom
    schema. Strip Python docstrings before scanning so historical-
    context comments don't trip the guard."""
    src = _read(ROUTER)
    stripped = re.sub(r'"""[\s\S]*?"""', "", src)
    stripped = re.sub(r"'''[\s\S]*?'''", "", stripped)
    stripped = re.sub(r"#[^\n]*", "", stripped)
    assert "monitor_alerts" not in stripped, (
        "`monitor_alerts` reference in executable code — Phase I.3 "
        "clarification ruled this out (use checklists/submissions/"
        "reports union instead)."
    )
    # Confirm the union is actually queried.
    for coll in ("db.checklists.find", "db.submissions.find", "db.reports.find"):
        assert coll in stripped, (
            f"Expected `{coll}` call in monitor chip builder."
        )
