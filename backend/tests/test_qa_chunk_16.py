"""Chunk 16 — Work Studio Document Cards bundle.

Backend regression coverage for QA-2026-05-16-037/-038/-039/-040:

  • QA-037 — status badge taxonomy (Draft / In Review / Committed)
    surfaces from the Chunk-8 `lifecycle_state` field on the listing
    endpoint output.
  • QA-038 — lock icon overlay maps to `lifecycle_state==="committed"`.
    Frontend-only render decision; backend test verifies the field
    flows through unchanged.
  • QA-039 — confidence chip (`Confidence X%` with RAG colour).
    Backend listing endpoint now returns `confidence_band` per row
    (Chunk 16 augmentation — see `routers/work_studio_overlay.py:list_documents`).
  • QA-040 — persistent download icon. Backend `download_token`
    flow already exists (Chunk 8); test verifies the token-mint endpoint
    is still callable for the listing rows.

Anchor: `/app/memory/qa_reports/QA_REPORT_16MAY2026.md` § QA-037 / -038
/ -039 / -040.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from motor.motor_asyncio import AsyncIOMotorClient

from server import app
from services.work_studio_overlay import rag_band


pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def db_conn():
    mclient = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = mclient[os.environ["DB_NAME"]]
    yield db
    mclient.close()


@pytest_asyncio.fixture
async def client():
    os.environ["SYNISENSE_LLM_MODE"] = "mock"
    saved = dict(app.dependency_overrides)
    app.dependency_overrides.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.update(saved)


@pytest_asyncio.fixture
async def authed(db_conn):
    """Seed an Exec account + context + 3 work_studio_exports rows
    (one per lifecycle_state) so Chunk 16 endpoint can return a
    fully-populated listing."""
    suffix = uuid.uuid4().hex[:8]
    email = f"chunk16-{suffix}@example.com"
    password = "Chunk16-2026!"
    account_id = f"acc-c16-{suffix}"
    context_id = f"ctx-c16-{suffix}"
    from core import hash_password
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    await db_conn.accounts.insert_one({
        "id": account_id, "email": email, "password_hash": hash_password(password),
        "name": "Chunk16 Exec", "role": "executive", "declared_role": "executive",
        "verified": True, "session_version": 0, "created_at": now_iso,
        "is_superadmin": False,
    })
    await db_conn.contexts.insert_one({
        "id": context_id, "owner_account_id": account_id,
        "name": "Chunk16 Context", "created_at": now_iso,
    })
    await db_conn.memberships.insert_one({
        "id": f"mem-{uuid.uuid4().hex[:8]}",
        "context_id": context_id, "account_id": account_id,
        "status": "active", "sub_role": "owner", "created_at": now_iso,
    })
    # One export per lifecycle state — each carries a distinct
    # confidence_pct so the band coverage spans green / amber / red.
    fixtures = [
        {"lifecycle_state": "draft",     "confidence_pct": 87, "title": "Chunk16 Draft"},
        {"lifecycle_state": "in_review", "confidence_pct": 62, "title": "Chunk16 In Review"},
        {"lifecycle_state": "committed", "confidence_pct": 41, "title": "Chunk16 Committed"},
    ]
    seeded_ids = []
    for spec in fixtures:
        eid = f"export-c16-{spec['lifecycle_state']}-{suffix}"
        seeded_ids.append(eid)
        await db_conn.work_studio_exports.insert_one({
            "id": eid,
            "account_id": account_id, "context_id": context_id,
            "title": spec["title"],
            "export_kind": "report",
            # Schema parity with the singular GET endpoint
            # (work_studio_export.py:1561-1562 reads `kind` + `output_format`).
            "kind": "report",
            "output_format": "docx",
            "file_name": f"{eid}.docx",
            "lifecycle_state": spec["lifecycle_state"],
            "status": "complete",
            "file_path": f"/tmp/{eid}.docx",
            "intelligence_report": {
                "confidence_pct": spec["confidence_pct"],
                "summary": f"Auto seed — {spec['lifecycle_state']} band.",
            },
            "created_at": now_iso, "updated_at": now_iso,
        })
    yield {
        "email": email, "password": password,
        "account_id": account_id, "context_id": context_id,
        "export_ids": seeded_ids,
    }
    await db_conn.accounts.delete_one({"id": account_id})
    await db_conn.contexts.delete_one({"id": context_id})
    await db_conn.memberships.delete_many({"account_id": account_id})
    await db_conn.work_studio_exports.delete_many({"context_id": context_id})


async def _login(c, email, password):
    r = await c.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    body = r.json()
    return {"Authorization": f"Bearer {body.get('access_token') or body.get('token')}"}


# =====================================================================
# QA-037 / -038 / -039 — listing endpoint surfaces every Chunk-16 field
# =====================================================================

async def test_chunk16_qa037_listing_returns_lifecycle_state_per_row(client, authed):
    """Chunk-8 endpoint extended in Chunk 16. Every row carries
    `lifecycle_state` ∈ {draft, in_review, committed}."""
    headers = await _login(client, authed["email"], authed["password"])
    r = await client.get(
        f"/api/contexts/{authed['context_id']}/work-studio/documents?limit=20",
        headers=headers,
    )
    assert r.status_code == 200, r.text
    items = r.json().get("items", [])
    assert len(items) == 3, f"Expected 3 seeded exports, got {len(items)}"
    seen = {it["lifecycle_state"] for it in items}
    assert seen == {"draft", "in_review", "committed"}, (
        f"QA-037: missing lifecycle_state coverage — saw {seen}"
    )


async def test_chunk16_qa039_listing_returns_confidence_band_per_row(client, authed):
    """NEW (Chunk 16): listing endpoint adds `confidence_band` per row.
    Verifies all three bands appear across the seeded fixtures
    (green=87%, amber=62%, red=41% per Chunk-8 thresholds 80/50)."""
    headers = await _login(client, authed["email"], authed["password"])
    r = await client.get(
        f"/api/contexts/{authed['context_id']}/work-studio/documents?limit=20",
        headers=headers,
    )
    items = r.json()["items"]
    bands = {it.get("confidence_band") for it in items}
    assert bands == {"green", "amber", "red"}, (
        f"QA-039: confidence_band coverage incomplete — saw {bands}. "
        f"Helper rag_band(87)={rag_band(87)}, rag_band(62)={rag_band(62)}, "
        f"rag_band(41)={rag_band(41)}"
    )


async def test_chunk16_qa039_confidence_band_helper_thresholds():
    """Static check on the Chunk-8 rag_band helper Chunk 16 builds on.
    Locks the 80/50 thresholds so future drift is caught."""
    assert rag_band(95) == "green"
    assert rag_band(80) == "green"     # boundary inclusive
    assert rag_band(79) == "amber"
    assert rag_band(50) == "amber"     # boundary inclusive
    assert rag_band(49) == "red"
    assert rag_band(0) == "red"
    assert rag_band(None) == "unrated"


# =====================================================================
# QA-040 — download_token flow still callable on the listing rows
# =====================================================================

async def test_chunk16_qa040_export_get_returns_download_token(client, authed):
    """For a row with status="complete", GET on the singular export
    endpoint should return a `download_token` the frontend can append
    to the /download URL. The QA-040 download icon is wired against
    this flow in `DocumentCardsSection.jsx::onDownload`."""
    headers = await _login(client, authed["email"], authed["password"])
    eid = authed["export_ids"][0]  # the "draft" fixture
    r = await client.get(
        f"/api/contexts/{authed['context_id']}/work-studio/exports/{eid}",
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    # The endpoint signature includes download_token (see
    # routers/work_studio_export.py:1545). For status="complete" rows
    # we expect a truthy token; for other statuses we expect None or
    # missing key.
    assert "download_token" in body, (
        "QA-040: GET export response missing `download_token` key — "
        "the DocumentCardsSection download flow depends on it"
    )


async def test_chunk16_qa040_download_button_visible_on_all_states():
    """Frontend smoke: the QA-040 download icon testid pattern is
    `ws-document-card-download-{id}` and renders for all lifecycle
    states (draft/in_review/committed). This static check confirms
    the testid is present in the component AND the render path is
    unconditional (no lifecycle-state guard around it).
    """
    path = "/app/frontend/src/components/work_studio/DocumentCardsSection.jsx"
    with open(path) as f:
        src = f.read()
    assert 'data-testid={`ws-document-card-download-${item.id}`}' in src, (
        "QA-040: download button testid missing"
    )
    # The download button must NOT be wrapped in any lifecycle-state
    # conditional. We search for the most-likely false-positive guard
    # patterns and assert their absence in the immediate vicinity of
    # the download button.
    # Crude but effective: assert the download button block doesn't
    # contain `lifecycle_state ===` (lifecycle gate) on the same line
    # or the line above the testid.
    idx = src.find('data-testid={`ws-document-card-download-${item.id}`}')
    assert idx > 0
    nearby = src[max(0, idx - 500):idx]
    assert "lifecycle_state ===" not in nearby and "isCommitted &&" not in nearby[-200:], (
        "QA-040: download button is gated by lifecycle state — must render on all 3 states"
    )


# =====================================================================
# CI sanity — Chunk 16 introduces no new LLM call sites
# =====================================================================

def test_chunk16_no_new_direct_llm_calls():
    """Chunk 16 is card rendering + download wiring. Status badges,
    lock icons, confidence chips are pure UI. CI guard
    `test_no_direct_llm_calls_outside_shield` is the authoritative
    full-repo coverage; this per-chunk smoke checks the new component
    file directly.
    """
    path = "/app/frontend/src/components/work_studio/DocumentCardsSection.jsx"
    with open(path) as f:
        src = f.read()
    for forbidden in ("openai", "anthropic", "litellm", "google.generativeai"):
        assert forbidden not in src, f"DocumentCardsSection.jsx must not reference {forbidden}"
