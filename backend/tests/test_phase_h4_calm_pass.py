"""Phase H.4 — Portfolio Landing calm pass + recent-views enrichment
+ news tier-1 expansion (2026-05-27).

Three sub-deliverables verified by this guard:

  H.4.1  Recent-views deep-link enrichment
    - `RecentViewIn` accepts `artefact_id`, `artefact_kind`, `deep_link`.
    - POST `/api/me/recent-views` upserts those fields.
    - GET `/api/me/last-action` returns the persisted `deep_link`
      and `artefact_kind` when present; falls back to surface_path
      classification for legacy rows.

  H.4.2  News tier-1 allowlist expansion
    - `_EXECUTIVE_TIER1_SOURCE_IDS` includes the live NYT source
      AND the reserved paid-API source ids (Nikkei Asia,
      S&P Global, MIT Sloan Review).

  H.4.3  Portfolio Landing A11y / focus calm pass
    - Company card carries aria-label + aria-current + focus-visible
      ring; section row buttons carry aria-label + focus-visible.
    - Segmented tabs carry aria-label + aria-controls + role="tabpanel"
      tabpanel id linkage.
    - Section headings have stable ids the section element references
      via aria-labelledby.
    - Decorative lucide icons inside actionable controls carry
      aria-hidden="true" so screen readers don't double-read.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport


REPO = Path(__file__).resolve().parent.parent.parent
FE = REPO / "frontend" / "src"

HOME_ROUTER       = REPO / "backend" / "routers" / "home.py"
PORTFOLIO_ROUTER  = REPO / "backend" / "routers" / "portfolio_data.py"
NEWS_ROUTER       = REPO / "backend" / "routers" / "news.py"
CONTEXT_PORTFOLIO = FE / "pages" / "ContextPortfolio.jsx"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ═════════════════════════════════════════════════════════════════
# H.4.1 — Recent-views deep-link enrichment
# ═════════════════════════════════════════════════════════════════

def test_h4_recent_view_in_accepts_deep_link_fields():
    src = _read(HOME_ROUTER)
    assert "class RecentViewIn(BaseModel):" in src
    # New optional fields.
    for field in ("artefact_id", "artefact_kind", "deep_link"):
        assert f"{field}:" in src, (
            f"`RecentViewIn` must declare `{field}` for H.4 deep-link "
            "enrichment."
        )


def test_h4_post_recent_view_writes_enrichment_fields():
    src = _read(HOME_ROUTER)
    # The upsert $set block must include the three new fields.
    set_block_re = re.search(
        r'\$set":\s*\{(.*?)\},\s*\n\s*"\$setOnInsert"',
        src, flags=re.DOTALL,
    )
    assert set_block_re, "$set block in post_recent_view not found"
    block = set_block_re.group(1)
    for field in ('"artefact_id"', '"artefact_kind"', '"deep_link"'):
        assert field in block, (
            f"`{field}` not persisted in /me/recent-views POST."
        )


def test_h4_last_action_prefers_persisted_deep_link_over_classification():
    src = _read(PORTFOLIO_ROUTER)
    # The handler must check for persisted_deep_link and persisted_artefact_kind
    # before falling back.
    assert "persisted_artefact_kind" in src or "persisted_deep_link" in src, (
        "last_action handler must prefer persisted enrichment over "
        "surface_path classification when available."
    )
    # Fallback path remains: surface_path → _classify_surface.
    assert "_classify_surface(surface_path)" in src


# ── Live: POST then GET round-trips the deep_link ────────────────
@pytest.fixture
async def h4_actor():
    from core import db, hash_password
    uid = f"h4-{uuid.uuid4().hex[:8]}"
    email = f"h4-{uuid.uuid4().hex[:6]}@example.com"
    pw = "Pw!1234567Abc"
    cid = f"h4-ctx-{uuid.uuid4().hex[:6]}"
    now = _now_iso()
    await db.accounts.insert_one({
        "id": uid, "email": email, "password_hash": hash_password(pw),
        "name": "H4 Tester", "tier": "executive",
        "declared_role": "executive", "mfa_enrolled": False,
        "is_superadmin": False, "created_at": now,
    })
    await db.contexts.insert_one({
        "id": cid, "name": "H4 Test Co",
        "type": "executive_personal", "owner_id": uid,
        "created_at": now,
    })
    await db.memberships.insert_one({
        "account_id": uid, "context_id": cid, "status": "active",
        "role": "executive", "created_at": now,
    })
    yield {"uid": uid, "email": email, "password": pw, "cid": cid}
    await db.accounts.delete_one({"id": uid})
    await db.contexts.delete_one({"id": cid})
    await db.memberships.delete_many({"account_id": uid})
    await db.user_recent_views.delete_many({"account_id": uid})


@pytest.mark.asyncio
async def test_h4_recent_view_deep_link_round_trips_through_last_action(h4_actor):
    from server import app  # noqa: F401
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as c:
        # Login
        r = await c.post("/api/auth/login",
                         json={"email": h4_actor["email"],
                               "password": h4_actor["password"]})
        tok = r.json()["access_token"]
        hdr = {"Authorization": f"Bearer {tok}"}

        # POST a recent view with enriched fields.
        body = {
            "surface_path": "/app/work-studio?doc_id=h4-doc-42",
            "label":        "Q4 Audit Memo",
            "context_id":   h4_actor["cid"],
            "artefact_id":  "h4-doc-42",
            "artefact_kind": "document",
            "deep_link":    "/app/documents/h4-doc-42",
        }
        r = await c.post("/api/me/recent-views", json=body, headers=hdr)
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True

        # GET /api/me/last-action — must echo back the enrichment.
        r = await c.get("/api/me/last-action", headers=hdr)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["artefact_id"] == "h4-doc-42"
        assert data["artefact_kind"] == "document"
        assert data["surface"] == "document"        # H.4 — surface == artefact_kind when persisted
        assert data["deep_link"] == "/app/documents/h4-doc-42"
        assert data["context_id"] == h4_actor["cid"]
        assert data["artefact_title"] == "Q4 Audit Memo"


@pytest.mark.asyncio
async def test_h4_last_action_falls_back_for_legacy_rows(h4_actor):
    """Rows written before H.4 lack the enrichment fields. The
    handler must still resolve them via the H.3 surface-path
    classification path."""
    from core import db
    from server import app  # noqa: F401

    # Seed a LEGACY row directly (no enrichment fields).
    await db.user_recent_views.insert_one({
        "id": f"h4-legacy-{uuid.uuid4().hex[:6]}",
        "account_id": h4_actor["uid"],
        "context_id": h4_actor["cid"],
        "surface_path": "/app/chat?cid=" + h4_actor["cid"],
        "label": "Legacy chat thread",
        "last_visited_at": _now_iso(),
    })

    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as c:
        r = await c.post("/api/auth/login",
                         json={"email": h4_actor["email"],
                               "password": h4_actor["password"]})
        tok = r.json()["access_token"]
        hdr = {"Authorization": f"Bearer {tok}"}
        r = await c.get("/api/me/last-action", headers=hdr)
    assert r.status_code == 200
    data = r.json()
    # Legacy row → classifier sees /chat in surface_path → "chat"
    assert data["surface"] == "chat"
    assert data["artefact_id"] is None
    # deep_link falls back to surface_path.
    assert data["deep_link"] == "/app/chat?cid=" + h4_actor["cid"]


# ═════════════════════════════════════════════════════════════════
# H.4.2 — News tier-1 allowlist expansion
# ═════════════════════════════════════════════════════════════════

def test_h4_news_tier1_allowlist_contains_live_nyt_and_reserved_ids():
    src = _read(NEWS_ROUTER)
    # Live aggregator entries.
    for sid in ("ft-companies", "ft-lex", "economist-biz", "nyt-business"):
        assert f'"{sid}"' in src, (
            f"tier-1 allowlist missing LIVE source `{sid}`."
        )
    # Reserved paid-API entries from H.4 brief.
    for sid in ("nikkei-asia", "sp-global", "mit-sloan-review"):
        assert f'"{sid}"' in src, (
            f"tier-1 allowlist missing RESERVED paid-API source `{sid}`."
        )


# ═════════════════════════════════════════════════════════════════
# H.4.3 — Calm pass: A11y + focus rings on Portfolio Landing
# ═════════════════════════════════════════════════════════════════

def test_h4_company_card_has_aria_label_and_focus_ring():
    src = _read(CONTEXT_PORTFOLIO)
    # Locate the CompanyCard block.
    m = re.search(
        r"function CompanyCard\(.*?\}\s*\)\s*\{(.*?)\n\}\n",
        src, flags=re.DOTALL,
    )
    assert m
    card = m.group(1)
    assert "aria-label={ariaLabel}" in card, "CompanyCard missing aria-label"
    assert "aria-current=" in card, "CompanyCard missing aria-current for the active row"
    assert "focus-visible:ring-2" in card, "CompanyCard missing focus-visible ring"
    # Decorative icon is hidden from AT.
    assert "aria-hidden=\"true\"" in card


def test_h4_segmented_tabs_have_aria_labels_and_tabpanel_linkage():
    src = _read(CONTEXT_PORTFOLIO)
    # role="tablist" has an accessible name.
    assert 'aria-label="Filter companies by your role"' in src
    # Each tab has aria-controls.
    assert 'aria-controls={`portfolio-rail-list-ned`}' in src or \
           "aria-controls={`portfolio-rail-list-ned`}" in src
    assert "aria-controls={`portfolio-rail-list-executive`}" in src
    # Each tab has aria-label with live counts.
    assert "aria-label={`Show NED boards (" in src
    assert "aria-label={`Show executive companies (" in src
    # The visible panel carries role="tabpanel" + id matching aria-controls.
    assert 'role="tabpanel"' in src
    assert "id={`portfolio-rail-list-${tab}`}" in src
    # Focus-visible ring on tab buttons.
    assert "focus-visible:ring-2 focus-visible:ring-inset" in src


def test_h4_section_headings_have_stable_ids_referenced_by_aria_labelledby():
    src = _read(CONTEXT_PORTFOLIO)
    pairs = [
        ("portfolio-boards-heading",   "portfolio-section-boards-to-watch"),
        ("portfolio-resume-heading",   "portfolio-section-where-you-left-off"),
        ("portfolio-news-heading",     "portfolio-section-news"),
    ]
    for heading_id, section_testid in pairs:
        assert f'id="{heading_id}"' in src, f"missing heading id={heading_id}"
        # The <section> with the testid must reference the heading id
        # via aria-labelledby.
        assert f'aria-labelledby="{heading_id}"' in src, (
            f"section `{section_testid}` missing aria-labelledby="
            f"`{heading_id}`."
        )


def test_h4_section_row_buttons_have_focus_visible_rings():
    src = _read(CONTEXT_PORTFOLIO)
    # Boards-to-watch row button.
    assert re.search(
        r"data-testid=\{`boards-to-watch-row-.*?`\}[\s\S]{0,400}focus-visible:ring-2",
        src,
    ) or re.search(
        r"focus-visible:ring-2[\s\S]{0,400}data-testid=\{`boards-to-watch-row-",
        src,
    ), "Boards-to-watch row button missing focus-visible ring."
    # Where-you-left-off Continue button.
    assert "portfolio-section-where-you-left-off-continue" in src
    # Read-more news button.
    assert "portfolio-section-news-read-more" in src
