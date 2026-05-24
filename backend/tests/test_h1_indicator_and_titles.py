"""H1 — honest indicator + browser tab title (2026-05-24).

Three contract guards:

1. `GET /api/chats/{chat_id}/synisense-metrics` returns the new copy
   for the three scenarios:
     a) Chat predates Shield v1.x AND has no shield activity     →
        "This conversation predates Shield v1.x. Counters and audit
        trail begin from …" + `pre_shield_v1: true`
     b) Chat is POST-cutoff AND has zero shield activity         →
        "No identifiers needed shielding in this conversation yet."
        + `pre_shield_v1: false`. The old "Synisense Shield is on
        standby" copy MUST be gone.
     c) Chat is POST-cutoff AND has shield activity              →
        Normal storyline. (Covered by existing tests in QA chunk 9.5.)
2. `frontend/public/index.html` carries "Akki for Executives" as the
   default <title>, og:title, og:site_name, and twitter:title.
3. FE strings — "Trust Center" (US) appears wherever "Trust centre"
   used to. We assert by source inspection because the strings live
   in JSX leaves.

Run independently:
    pytest tests/test_h1_indicator_and_titles.py -v
"""
from __future__ import annotations

import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
import pytest_asyncio

sys.path.insert(0, "/app/backend")
from server import app  # noqa: E402
from routers import synisense_metrics  # noqa: E402

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        yield c


async def _register(client: httpx.AsyncClient):
    email = f"h1-indicator-{uuid.uuid4().hex[:10]}@example.com"
    pw = "H1-Indicator-2026!"
    r = await client.post("/api/auth/register", json={
        "email": email, "password": pw, "name": "H1 Indicator",
    })
    assert r.status_code == 200, (r.status_code, r.text[:300])
    body = r.json()
    token = body["access_token"]
    me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    me_body = me.json()
    ctx_id = me_body["contexts"][0]["id"]
    account_id = me_body["account"]["id"]
    return token, ctx_id, account_id


# ─────────────────────────────────────────────────────────────────────
# 1a. Pre-cutoff chat → "predates Shield v1.x" indicator
# ─────────────────────────────────────────────────────────────────────
async def test_pre_shield_v1_chat_returns_honest_indicator(client):
    """A chat with `created_at` BEFORE the configured cutoff and zero
    shield activity returns the "predates Shield v1.x" storyline AND
    sets `pre_shield_v1: true`."""
    token, ctx_id, account_id = await _register(client)
    hdrs = {"Authorization": f"Bearer {token}", "X-Active-Context": ctx_id}

    created = await client.post(
        "/api/chats", json={"title": "Pre-v1 chat"}, headers=hdrs,
    )
    assert created.status_code in (200, 201)
    chat_id = created.json()["id"]

    # Force the chat's created_at to BEFORE the cutoff. Mongo directly
    # so we sidestep the API's auto-now timestamping.
    from core import db  # noqa: PLC0415 — lazy import keeps the fixture import light.
    cutoff_str = synisense_metrics._SHIELD_V1_DEPLOY_TIMESTAMP_STR
    cutoff = synisense_metrics._coerce_to_datetime(cutoff_str)
    pre_cutoff = (cutoff - timedelta(days=14)).isoformat()
    res = await db.chats.update_one(
        {"id": chat_id, "account_id": account_id},
        {"$set": {"created_at": pre_cutoff}},
    )
    assert res.modified_count == 1

    r = await client.get(
        f"/api/chats/{chat_id}/synisense-metrics", headers=hdrs,
    )
    assert r.status_code == 200, (r.status_code, r.text[:200])
    body = r.json()
    assert body["identifiers_redacted"] == 0
    assert body["model_calls"] == 0
    assert body.get("pre_shield_v1") is True, body
    assert "predates Shield v1.x" in body["storyline"], body["storyline"]
    # The misleading copy MUST be gone.
    assert "on standby" not in body["storyline"], body["storyline"]
    assert "Nothing has needed redaction" not in body["storyline"], body["storyline"]


# ─────────────────────────────────────────────────────────────────────
# 1b. Post-cutoff chat with zero activity → neutral indicator
# ─────────────────────────────────────────────────────────────────────
async def test_post_cutoff_zero_activity_chat_uses_neutral_copy(client):
    """A chat created AFTER the cutoff with zero shield activity should
    show the neutral "No identifiers needed shielding ... yet" copy and
    `pre_shield_v1: false`. The old "on standby" copy MUST be gone."""
    token, ctx_id, account_id = await _register(client)
    hdrs = {"Authorization": f"Bearer {token}", "X-Active-Context": ctx_id}

    created = await client.post(
        "/api/chats", json={"title": "Post-v1 clean"}, headers=hdrs,
    )
    assert created.status_code in (200, 201)
    chat_id = created.json()["id"]

    # Force the chat's created_at to AFTER the cutoff (now is fine).
    from core import db  # noqa: PLC0415
    post_cutoff = datetime.now(timezone.utc).isoformat()
    await db.chats.update_one(
        {"id": chat_id, "account_id": account_id},
        {"$set": {"created_at": post_cutoff}},
    )

    r = await client.get(
        f"/api/chats/{chat_id}/synisense-metrics", headers=hdrs,
    )
    assert r.status_code == 200, (r.status_code, r.text[:200])
    body = r.json()
    assert body["identifiers_redacted"] == 0
    assert body["model_calls"] == 0
    assert body.get("pre_shield_v1") is False, body
    assert body["storyline"] == (
        "No identifiers needed shielding in this conversation yet."
    ), body["storyline"]
    assert "on standby" not in body["storyline"], body["storyline"]


# ─────────────────────────────────────────────────────────────────────
# 1c. Storyline regression — the OLD "on standby" copy must be GONE
# from every emitted storyline (comments referencing the historical
# string are still allowed; they explain why the change exists).
# ─────────────────────────────────────────────────────────────────────
def test_zero_activity_storyline_no_longer_says_on_standby():
    """`_build_storyline(0, 0, {})` was the source of the misleading
    'Synisense Shield is on standby' copy. It must now return the
    neutral message."""
    out = synisense_metrics._build_storyline(0, 0, {})
    assert "on standby" not in out, out
    assert "Nothing has needed redaction" not in out, out
    assert out == "No identifiers needed shielding in this conversation yet."


def test_pre_v1_storyline_says_predates_shield():
    """`_pre_shield_v1_storyline()` returns the honest 'predates Shield
    v1.x' prose with the configured cutoff date."""
    out = synisense_metrics._pre_shield_v1_storyline()
    assert "predates Shield v1.x" in out, out
    assert "on standby" not in out, out


# ─────────────────────────────────────────────────────────────────────
# 2. Browser tab title + OG/Twitter cards in public/index.html
# ─────────────────────────────────────────────────────────────────────
def test_browser_tab_title_is_akki_for_executives():
    src = Path("/app/frontend/public/index.html").read_text(encoding="utf-8")
    assert "<title>Akki for Executives</title>" in src, (
        "frontend/public/index.html must set <title>Akki for Executives</title>"
    )
    # The default <title> tag must NOT be the old Emergent placeholder.
    # We scope to the actual <title> element rather than the whole file
    # because a comment may legitimately reference the historical default.
    import re
    title_match = re.search(r"<title>([^<]*)</title>", src)
    assert title_match is not None, "no <title> element found"
    assert title_match.group(1) == "Akki for Executives", (
        f"unexpected <title> value: {title_match.group(1)!r}"
    )


def test_open_graph_and_twitter_cards_present():
    src = Path("/app/frontend/public/index.html").read_text(encoding="utf-8")
    expected_meta = [
        '<meta property="og:title" content="Akki for Executives" />',
        '<meta property="og:site_name" content="Akki for Executives" />',
        '<meta name="twitter:title" content="Akki for Executives" />',
    ]
    for tag in expected_meta:
        assert tag in src, f"Missing meta tag: {tag}"


# ─────────────────────────────────────────────────────────────────────
# 3. US-spelling "Trust Center" replaced "Trust centre" in the two
# known surfaces (AppShell footer link + TenantSettings card label).
# ─────────────────────────────────────────────────────────────────────
def test_trust_center_us_spelling_in_appshell_footer():
    src = Path("/app/frontend/src/components/layout/AppShell.jsx").read_text(encoding="utf-8")
    assert "Trust Center →" in src, "AppShell footer must read 'Trust Center →'"
    assert "Trust centre" not in src, (
        "British spelling 'Trust centre' must NOT appear in AppShell anymore."
    )


def test_trust_center_us_spelling_in_tenant_settings():
    src = Path("/app/frontend/src/pages/TenantSettings.jsx").read_text(encoding="utf-8")
    assert "Trust Center" in src, "TenantSettings must read 'Trust Center'"
    assert "Trust centre" not in src, (
        "British spelling 'Trust centre' must NOT appear in TenantSettings anymore."
    )
